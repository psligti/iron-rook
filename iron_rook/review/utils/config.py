"""Repository configuration discovery utilities.

This module provides tools for discovering and parsing configuration files
from Python repositories, including linting, testing, and type checking tools.
"""
from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Dict, List, Optional, Any
import configparser

logger = logging.getLogger(__name__)


class RepoConfigDiscovery:
    """Discover and parse repository configuration files.

    This class provides methods to discover common Python project configuration
    files and extract tool commands from them. It supports flexible searching
    for config files and handles missing or malformed configurations gracefully.

    Example:
        >>> discovery = RepoConfigDiscovery("/path/to/repo")
        >>> lint_cmds = discovery.discover_lint_commands()
        >>> test_cmds = discovery.discover_test_commands()
    """

    def __init__(self, repo_root: str = "."):
        """Initialize config discovery for a repository.

        Args:
            repo_root: Path to repository root directory
        """
        self.repo_root = Path(repo_root).resolve()

    def _find_config_file(self, filenames: List[str]) -> Optional[Path]:
        """Find the first matching config file in repository.

        Args:
            filenames: List of filenames to search for

        Returns:
            Path to first found config file, or None if not found
        """
        for filename in filenames:
            config_path = self.repo_root / filename
            if config_path.exists() and config_path.is_file():
                logger.debug(f"Found config file: {config_path}")
                return config_path
        return None

    def _read_file_safely(self, file_path: Path) -> Optional[str]:
        """Read file content safely, handling errors.

        Args:
            file_path: Path to file to read

        Returns:
            File content as string, or None if error occurred
        """
        try:
            return file_path.read_text(encoding="utf-8")
        except (IOError, OSError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to read file {file_path}: {e}")
            return None

    def read_pyproject_toml(self) -> Dict[str, Any]:
        """Parse pyproject.toml for tool configurations.

        Args:
            None (uses self.repo_root)

        Returns:
            Dictionary containing parsed pyproject.toml content, or empty dict
            if file not found or parsing failed
        """
        config_path = self.repo_root / "pyproject.toml"

        if not config_path.exists():
            logger.debug("No pyproject.toml found")
            return {}

        try:
            with open(config_path, "rb") as f:
                content = tomllib.load(f)
            logger.debug(f"Successfully parsed pyproject.toml from {config_path}")
            return content
        except (IOError, OSError, tomllib.TOMLDecodeError) as e:
            logger.warning(f"Failed to parse pyproject.toml {config_path}: {e}")
            return {}

    def _read_setup_cfg(self) -> Dict[str, Any]:
        """Parse setup.cfg for tool configurations.

        Returns:
            Dictionary containing parsed setup.cfg content, or empty dict
            if file not found or parsing failed
        """
        config_path = self.repo_root / "setup.cfg"

        if not config_path.exists():
            return {}

        try:
            parser = configparser.ConfigParser()
            parser.read(config_path, encoding="utf-8")
            result: Dict[str, Any] = {}
            for section in parser.sections():
                result[section] = dict(parser.items(section))
            return result
        except (IOError, OSError, configparser.Error) as e:
            logger.warning(f"Failed to parse setup.cfg {config_path}: {e}")
            return {}

    def _read_tox_ini(self) -> Dict[str, Any]:
        """Parse tox.ini for tool configurations.

        Returns:
            Dictionary containing parsed tox.ini content, or empty dict
            if file not found or parsing failed
        """
        config_path = self.repo_root / "tox.ini"

        if not config_path.exists():
            return {}

        try:
            parser = configparser.ConfigParser()
            parser.read(config_path, encoding="utf-8")
            result: Dict[str, Any] = {}
            for section in parser.sections():
                result[section] = dict(parser.items(section))
            return result
        except (IOError, OSError, configparser.Error) as e:
            logger.warning(f"Failed to parse tox.ini {config_path}: {e}")
            return {}

    def discover_lint_commands(self) -> List[str]:
        """Discover linting commands from project configuration.

        Searches for ruff, black, flake8 configurations in:
        - pyproject.toml
        - setup.cfg
        - .ruff.toml
        - .flake8

        Returns:
            List of discovered lint commands (e.g., ["ruff check", "black ."])
        """
        commands: List[str] = []

        pyproject = self.read_pyproject_toml()

        if "ruff" in pyproject or "tool" in pyproject and "ruff" in pyproject["tool"]:
            ruff_config = pyproject.get("ruff", {})
            if not ruff_config and "tool" in pyproject:
                ruff_config = pyproject["tool"].get("ruff", {})

            commands.append("ruff check")

            if ruff_config.get("line-length") or "format" in ruff_config:
                commands.append("ruff format --check")

        if "black" in pyproject or "tool" in pyproject and "black" in pyproject["tool"]:
            black_config = pyproject.get("black", {})
            if not black_config and "tool" in pyproject:
                black_config = pyproject["tool"].get("black", {})

            if black_config:
                commands.append("black --check .")

        if "flake8" in pyproject or "tool" in pyproject and "flake8" in pyproject["tool"]:
            commands.append("flake8")

        standalone_configs = [".ruff.toml", "ruff.toml", ".flake8", "setup.cfg"]
        found_files = []

        for filename in standalone_configs:
            config_path = self.repo_root / filename
            if config_path.exists():
                found_files.append(filename)

        if ".ruff.toml" in found_files or "ruff.toml" in found_files:
            if "ruff check" not in commands:
                commands.append("ruff check")

        if "setup.cfg" in found_files:
            setup_cfg = self._read_setup_cfg()
            if "flake8" in setup_cfg and "flake8" not in " ".join(commands):
                commands.append("flake8")

        seen = set()
        unique_commands = []
        for cmd in commands:
            if cmd not in seen:
                seen.add(cmd)
                unique_commands.append(cmd)

        logger.debug(f"Discovered lint commands: {unique_commands}")
        return unique_commands

    def discover_test_commands(self) -> List[str]:
        """Discover test commands from project configuration.

        Searches for pytest, tox, nox configurations in:
        - pyproject.toml
        - setup.cfg
        - tox.ini
        - noxfile.py

        Returns:
            List of discovered test commands (e.g., ["pytest", "tox"])
        """
        commands: List[str] = []

        pyproject = self.read_pyproject_toml()

        pytest_config = None

        if "pytest" in pyproject:
            pytest_config = pyproject["pytest"]
        elif "tool" in pyproject and "pytest" in pyproject["tool"]:
            if "ini_options" in pyproject["tool"]["pytest"]:
                pytest_config = pyproject["tool"]["pytest"]["ini_options"]
            else:
                pytest_config = pyproject["tool"]["pytest"]

        if pytest_config:
            commands.append("pytest")

            if pytest_config.get("asyncio_mode"):
                commands.append("pytest --asyncio-mode=auto")

        tox_ini = self._read_tox_ini()
        if tox_ini and "testenv" in tox_ini:
            commands.append("tox")

        noxfile = self.repo_root / "noxfile.py"
        if noxfile.exists():
            commands.append("nox")

        if not commands or "pytest" not in " ".join(commands):
            setup_cfg = self._read_setup_cfg()
            if "tool:pytest" in setup_cfg or "pytest" in setup_cfg:
                commands.insert(0, "pytest")

        seen = set()
        unique_commands = []
        for cmd in commands:
            if cmd not in seen:
                seen.add(cmd)
                unique_commands.append(cmd)

        logger.debug(f"Discovered test commands: {unique_commands}")
        return unique_commands

    def discover_type_check_commands(self) -> List[str]:
        """Discover type checking commands from project configuration.

        Searches for mypy, pyright configurations in:
        - pyproject.toml
        - setup.cfg
        - .mypy.ini
        - mypy.ini
        - pyproject.toml for pyright

        Returns:
            List of discovered type check commands (e.g., ["mypy", "pyright"])
        """
        commands: List[str] = []

        pyproject = self.read_pyproject_toml()

        if "mypy" in pyproject or "tool" in pyproject and "mypy" in pyproject["tool"]:
            mypy_config = pyproject.get("mypy", {})
            if not mypy_config and "tool" in pyproject:
                mypy_config = pyproject["tool"].get("mypy", {})

            mypy_cmd = "mypy"
            if mypy_config.get("strict"):
                mypy_cmd += " --strict"
            commands.append(mypy_cmd)

        if "pyright" in pyproject or "tool" in pyproject and "pyright" in pyproject["tool"]:
            commands.append("pyright")

        mypy_configs = [".mypy.ini", "mypy.ini", ".mypy"]
        found_mypy = False

        for filename in mypy_configs:
            config_path = self.repo_root / filename
            if config_path.exists():
                found_mypy = True
                break

        if found_mypy and "mypy" not in " ".join(commands):
            commands.append("mypy")

        pyright_config = self.repo_root / "pyrightconfig.json"
        if pyright_config.exists() and "pyright" not in " ".join(commands):
            commands.append("pyright")

        seen = set()
        unique_commands = []
        for cmd in commands:
            if cmd not in seen:
                seen.add(cmd)
                unique_commands.append(cmd)

        logger.debug(f"Discovered type check commands: {unique_commands}")
        return unique_commands

    def discover_ci_config(self) -> Dict[str, Any]:
        """Discover CI/CD configuration from workflows.

        Searches for CI workflow files in:
        - .github/workflows/*.yml
        - .github/workflows/*.yaml

        Returns:
            Dictionary containing CI configuration information including
            workflow names and job definitions
        """
        result: Dict[str, Any] = {
            "platforms": [],
            "workflows": {},
            "jobs": {},
        }

        github_workflows_dir = self.repo_root / ".github" / "workflows"

        if github_workflows_dir.exists() and github_workflows_dir.is_dir():
            for workflow_file in github_workflows_dir.glob("*.yml"):
                self._parse_github_workflow(workflow_file, result)
            for workflow_file in github_workflows_dir.glob("*.yaml"):
                self._parse_github_workflow(workflow_file, result)
            result["platforms"].append("github")

        gitlab_ci_file = self.repo_root / ".gitlab-ci.yml"
        if gitlab_ci_file.exists():
            content = self._read_file_safely(gitlab_ci_file)
            if content:
                result["platforms"].append("gitlab")
                result["workflows"]["gitlab"] = {"file": ".gitlab-ci.yml"}

        azure_pipelines = self.repo_root / "azure-pipelines.yml"
        if azure_pipelines.exists():
            content = self._read_file_safely(azure_pipelines)
            if content:
                result["platforms"].append("azure")
                result["workflows"]["azure"] = {"file": "azure-pipelines.yml"}

        logger.debug(f"Discovered CI config: {result}")
        return result

    def _parse_github_workflow(self, workflow_path: Path, result: Dict[str, Any]) -> None:
        """Parse a GitHub Actions workflow file.

        Args:
            workflow_path: Path to workflow YAML file
            result: Result dictionary to populate with workflow info
        """
        content = self._read_file_safely(workflow_path)
        if not content:
            return

        try:
            import yaml
            workflow = yaml.safe_load(content)
        except ImportError:
            result["workflows"][workflow_path.stem] = {
                "file": f".github/workflows/{workflow_path.name}",
                "jobs": [],
            }
            return
        except yaml.YAMLError:
            logger.warning(f"Failed to parse workflow YAML {workflow_path}")
            return

        if not isinstance(workflow, dict):
            return

        workflow_name = workflow.get("name", workflow_path.stem)
        jobs = workflow.get("jobs", {})

        result["workflows"][workflow_name] = {
            "file": f".github/workflows/{workflow_path.name}",
            "name": workflow_name,
            "jobs": list(jobs.keys()) if isinstance(jobs, dict) else [],
        }

        if isinstance(jobs, dict):
            for job_name, job_config in jobs.items():
                result["jobs"][f"{workflow_name}.{job_name}"] = job_config

    def get_all_tool_commands(self) -> Dict[str, List[str]]:
        """Get all discovered tool commands grouped by category.

        Returns:
            Dictionary with keys 'lint', 'test', 'type_check' and lists of commands
        """
        return {
            "lint": self.discover_lint_commands(),
            "test": self.discover_test_commands(),
            "type_check": self.discover_type_check_commands(),
        }
