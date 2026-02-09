"""Sandboxed subprocess execution framework for review agents."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

import pydantic as pd

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_TOOLS = [
    "ty",
    "ruff",
    "black",
    "pytest",
    "mypy",
    "bandit",
    "pip-audit",
]

BLOCKED_SHELL_CHARACTERS = {
    "|",
    ";",
    "`",
    "$(",
    "&",
    "&&",
    "||",
    ">",
    "<",
    "*",
    "?",
}

TOOLS_WITH_FIX_FLAG = {"ruff", "black", "ty"}


class SecurityError(Exception):
    """Raised when a command violates security rules."""


class CommandTimeoutError(Exception):
    """Raised when a command exceeds the timeout limit."""


class CommandExecutionError(Exception):
    """Raised when a command fails to execute."""


class ParsedResult(pd.BaseModel):
    """Result of parsing command output."""

    findings: List[Dict[str, Any]] = pd.Field(default_factory=list)
    errors: List[str] = pd.Field(default_factory=list)
    files_modified: List[str] = pd.Field(default_factory=list)

    model_config = pd.ConfigDict(extra="forbid")


class ExecutionResult(pd.BaseModel):
    """Result of executing a command."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    timeout: bool
    parsed_findings: List[Dict[str, Any]] = pd.Field(default_factory=list)
    files_modified: List[str] = pd.Field(default_factory=list)
    duration_seconds: float

    model_config = pd.ConfigDict(extra="forbid")


class CommandExecutor:
    """Execute commands with security guardrails and resource limits."""

    def __init__(self, allowed_tools: List[str] | None = None, repo_root: Path | None = None, max_concurrent: int = 4):
        self.allowed_tools = allowed_tools or DEFAULT_ALLOWED_TOOLS
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def validate_command(self, command: str) -> bool:
        if not command.strip():
            return False

        command_start = command.strip().split()[0]
        if command_start not in self.allowed_tools:
            return False

        for blocked in BLOCKED_SHELL_CHARACTERS:
            if blocked in command and not self._is_in_quotes(command, blocked):
                return False

        return True

    def _is_in_quotes(self, command: str, char: str) -> bool:
        idx = command.find(char)
        if idx == -1:
            return False

        in_single_quote = False
        in_double_quote = False

        for i, c in enumerate(command):
            if c == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
            elif c == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
            elif i == idx and (in_single_quote or in_double_quote):
                return True

        return False

    def _validate_working_directory(self, cwd: str) -> bool:
        if Path(cwd).is_absolute():
            return False

        resolved_path = (self.repo_root / cwd).resolve()
        try:
            resolved_path.relative_to(self.repo_root)
            return True
        except ValueError:
            return False

    async def execute(self, command: str, timeout: int = 30, cwd: str = ".", allow_fix: bool = False) -> ExecutionResult:
        if not self.validate_command(command):
            command_start = command.strip().split()[0]
            if command_start not in self.allowed_tools:
                raise SecurityError(f"Tool '{command_start}' is not in whitelist: {self.allowed_tools}")

            for blocked in BLOCKED_SHELL_CHARACTERS:
                if blocked in command:
                    raise SecurityError(f"Command contains blocked characters: {blocked}")

        if not self._validate_working_directory(cwd):
            raise SecurityError(f"Invalid working directory: {cwd}")

        full_cwd = self.repo_root / cwd

        command_parts = shlex.split(command)
        tool_name = command_parts[0]

        if allow_fix and tool_name in TOOLS_WITH_FIX_FLAG:
            command_parts.append("--fix")

        start_time = time.time()

        async with self._semaphore:
            try:
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: subprocess.run(
                            command_parts,
                            shell=False,
                            cwd=full_cwd,
                            capture_output=True,
                            text=True,
                            timeout=timeout,
                        ),
                    ),
                    timeout=timeout,
                )

                duration = time.time() - start_time

                parsed = self.parse_output(result.stdout, tool_name)

                return ExecutionResult(
                    command=command,
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    timeout=False,
                    parsed_findings=parsed.findings,
                    files_modified=parsed.files_modified,
                    duration_seconds=duration,
                )

            except (asyncio.TimeoutError, subprocess.TimeoutExpired):
                raise CommandTimeoutError(f"Command '{command}' timed out after {timeout} seconds")
            except Exception as e:
                raise CommandExecutionError(f"Command failed: {e}")

    def parse_output(self, output: str, tool_type: str) -> ParsedResult:
        if not output:
            return ParsedResult()

        if tool_type == "ruff":
            return self._parse_ruff_output(output)
        elif tool_type == "pytest":
            return self._parse_pytest_output(output)
        elif tool_type == "mypy":
            return self._parse_mypy_output(output)
        else:
            return ParsedResult()

    def _parse_ruff_output(self, output: str) -> ParsedResult:
        findings = []
        errors = []
        files_modified = []

        output = output.strip()

        if output.startswith("["):
            try:
                items = json.loads(output)
                for item in items:
                    finding = {
                        "filename": item.get("filename", ""),
                        "line": item.get("location", {}).get("row", 0),
                        "column": item.get("location", {}).get("column", 0),
                        "code": item.get("code", ""),
                        "message": item.get("message", ""),
                    }
                    findings.append(finding)
                return ParsedResult(findings=findings, errors=errors, files_modified=files_modified)
            except json.JSONDecodeError:
                pass

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue

            if line.startswith("Found") and "error" in line.lower():
                errors.append(line)
            elif "fixed" in line.lower() or "reformatted" in line.lower():
                files_modified.append(line)
            else:
                try:
                    parts = re.split(r"[:\s]+", line, maxsplit=4)
                    if len(parts) >= 2 and parts[0].endswith(".py"):
                        finding = {"filename": parts[0], "line": parts[1], "raw": line}
                        if len(parts) >= 4:
                            finding["code"] = parts[3]
                        findings.append(finding)
                except Exception:
                    continue

        return ParsedResult(findings=findings, errors=errors, files_modified=files_modified)

    def _parse_pytest_output(self, output: str) -> ParsedResult:
        findings = []
        errors = []

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue

            if "FAILED" in line:
                parts = line.split("::")
                if len(parts) >= 2:
                    finding = {"file": parts[0], "test": parts[1], "status": "FAILED"}
                    findings.append(finding)
                    errors.append(line)
            elif "PASSED" in line:
                parts = line.split("::")
                if len(parts) >= 2:
                    finding = {"file": parts[0], "test": parts[1], "status": "PASSED"}
                    findings.append(finding)

        return ParsedResult(findings=findings, errors=errors)

    def _parse_mypy_output(self, output: str) -> ParsedResult:
        findings = []
        errors = []

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue

            if ": error:" in line or ": warning:" in line:
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    finding = {
                        "file": parts[0],
                        "line": parts[1],
                        "message": parts[2].strip(),
                        "raw": line,
                    }
                    findings.append(finding)
                    if "error" in line:
                        errors.append(line)

        return ParsedResult(findings=findings, errors=errors)
