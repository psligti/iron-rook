"""CLI command for running PR reviews from the command line."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Literal

import click  # type: ignore[import-not-found]
from rich.console import Console  # type: ignore[import-not-found]

console = Console()


def log_verbose_subagent_info(subagents: list) -> None:
    """Log detailed information about all subagents.

    Args:
        subagents: List of subagent instances
    """
    import logging

    logger = logging.getLogger(__name__)

    if not logger.isEnabledFor(logging.DEBUG):
        return

    logger.info("")
    logger.info("[VERBOSE] ===== SUBAGENT INFORMATION =====")
    logger.info(f"[VERBOSE] Total subagents: {len(subagents)}")

    for idx, agent in enumerate(subagents, 1):
        agent_name = agent.get_agent_name()
        logger.info(f"[VERBOSE]")
        logger.info(f"[VERBOSE] Subagent #{idx}: {agent_name}")
        logger.info(f"[VERBOSE]   Class: {agent.__class__.__name__}")
        logger.info(f"[VERBOSE]   Module: {agent.__class__.__module__}")

        try:
            patterns = agent.get_relevant_file_patterns()
            logger.info(f"[VERBOSE]   Relevant patterns: {len(patterns)}")
            for pattern in patterns[:5]:
                logger.info(f"[VERBOSE]     - {pattern}")
            if len(patterns) > 5:
                logger.info(f"[VERBOSE]     ... and {len(patterns) - 5} more")
        except Exception as e:
            logger.warning(f"[VERBOSE]   Could not get relevant patterns: {e}")

        try:
            tools = agent.get_allowed_tools()
            logger.info(f"[VERBOSE]   Allowed tools: {len(tools)}")
            if tools:
                logger.info(f"[VERBOSE]     {', '.join(tools[:10])}")
                if len(tools) > 10:
                    logger.info(f"[VERBOSE]     ... and {len(tools) - 10} more")
        except Exception as e:
            logger.warning(f"[VERBOSE]   Could not get allowed tools: {e}")

    logger.info("[VERBOSE] ===== END SUBAGENT INFORMATION =====")
    logger.info("")


def log_verbose_result_details(result) -> None:
    """Log detailed information about a review result.

    Args:
        result: ReviewOutput object
    """
    import logging

    logger = logging.getLogger(__name__)

    if not logger.isEnabledFor(logging.DEBUG):
        return

    logger.info("")
    logger.info(f"[VERBOSE] ===== RESULT DETAILS: {result.agent} =====")
    logger.info(f"[VERBOSE] Agent: {result.agent}")
    logger.info(f"[VERBOSE] Severity: {result.severity}")
    logger.info(
        f"[VERBOSE] Summary: {result.summary[:300]}{'...' if len(result.summary) > 300 else ''}"
    )
    logger.info(f"[VERBOSE]")

    logger.info(f"[VERBOSE] Scope:")
    logger.info(f"[VERBOSE]   Relevant files: {len(result.scope.relevant_files)}")
    for file_path in result.scope.relevant_files[:5]:
        logger.info(f"[VERBOSE]     - {file_path}")
    if len(result.scope.relevant_files) > 5:
        logger.info(f"[VERBOSE]     ... and {len(result.scope.relevant_files) - 5} more")

    logger.info(f"[VERBOSE]   Ignored files: {len(result.scope.ignored_files)}")
    logger.info(
        f"[VERBOSE]   Reasoning: {result.scope.reasoning[:200]}{'...' if len(result.scope.reasoning) > 200 else ''}"
    )

    logger.info(f"[VERBOSE]")
    logger.info(f"[VERBOSE] Findings ({len(result.findings)}):")
    for idx, finding in enumerate(result.findings, 1):
        logger.info(f"[VERBOSE]   #{idx} {finding.title}")
        logger.info(f"[VERBOSE]       ID: {finding.id}")
        logger.info(f"[VERBOSE]       Severity: {finding.severity}")
        logger.info(f"[VERBOSE]       Confidence: {finding.confidence}")
        logger.info(f"[VERBOSE]       Owner: {finding.owner}")
        logger.info(f"[VERBOSE]       Estimate: {finding.estimate}")
        logger.info(
            f"[VERBOSE]       Evidence: {finding.evidence[:150]}{'...' if len(finding.evidence) > 150 else ''}"
        )
        logger.info(
            f"[VERBOSE]       Recommendation: {finding.recommendation[:150]}{'...' if len(finding.recommendation) > 150 else ''}"
        )

    logger.info(f"[VERBOSE]")
    logger.info(f"[VERBOSE] Checks ({len(result.checks)}):")
    for idx, check in enumerate(result.checks, 1):
        logger.info(f"[VERBOSE]   #{idx} {check.check_id}")
        logger.info(f"[VERBOSE]       Required: {check.required}")
        logger.info(f"[VERBOSE]       Commands: {len(check.commands)}")

    logger.info(f"[VERBOSE]")
    logger.info(f"[VERBOSE] Skips ({len(result.skips)}):")
    for idx, skip in enumerate(result.skips, 1):
        logger.info(f"[VERBOSE]   #{idx} {skip.check_id}")
        logger.info(
            f"[VERBOSE]       Reason: {skip.skip_reason[:100]}{'...' if len(skip.skip_reason) > 100 else ''}"
        )

    logger.info(f"[VERBOSE]")
    logger.info(f"[VERBOSE] Merge Gate:")
    logger.info(f"[VERBOSE]   Decision: {result.merge_gate.decision}")
    logger.info(f"[VERBOSE]   Must fix: {len(result.merge_gate.must_fix)}")
    for item in result.merge_gate.must_fix[:5]:
        logger.info(f"[VERBOSE]     - {item[:80]}{'...' if len(item) > 80 else ''}")
    if len(result.merge_gate.must_fix) > 5:
        logger.info(f"[VERBOSE]     ... and {len(result.merge_gate.must_fix) - 5} more")

    logger.info(f"[VERBOSE]   Should fix: {len(result.merge_gate.should_fix)}")
    for item in result.merge_gate.should_fix[:5]:
        logger.info(f"[VERBOSE]     - {item[:80]}{'...' if len(item) > 80 else ''}")
    if len(result.merge_gate.should_fix) > 5:
        logger.info(f"[VERBOSE]     ... and {len(result.merge_gate.should_fix) - 5} more")

    logger.info(f"[VERBOSE]   Notes: {len(result.merge_gate.notes_for_coding_agent)}")
    for note in result.merge_gate.notes_for_coding_agent[:3]:
        logger.info(f"[VERBOSE]     - {note[:100]}{'...' if len(note) > 100 else ''}")
    if len(result.merge_gate.notes_for_coding_agent) > 3:
        logger.info(
            f"[VERBOSE]     ... and {len(result.merge_gate.notes_for_coding_agent) - 3} more"
        )

    logger.info(f"[VERBOSE] ===== END RESULT DETAILS =====")
    logger.info("")


async def log_verbose_todos(repo_root: str) -> None:
    """Log todo information from session storage if available.

    Args:
        repo_root: Repository root directory
    """
    import logging
    from pathlib import Path

    logger = logging.getLogger(__name__)

    if not logger.isEnabledFor(logging.DEBUG):
        return

    try:
        from dawn_kestrel.storage.store import TodoStorage

        todo_storage = TodoStorage(Path(repo_root))
        session_id = "review-cli-session"

        todos = await todo_storage.get_todos(session_id)

        if todos:
            logger.info("")
            logger.info("[VERBOSE] ===== TODO LIST =====")
            logger.info(f"[VERBOSE] Total todos: {len(todos)}")

            completed_count = sum(1 for t in todos if t.get("state") == "completed")
            in_progress_count = sum(1 for t in todos if t.get("state") == "in_progress")
            pending_count = sum(1 for t in todos if t.get("state") == "pending")

            logger.info(f"[VERBOSE]   Completed: {completed_count}")
            logger.info(f"[VERBOSE]   In Progress: {in_progress_count}")
            logger.info(f"[VERBOSE]   Pending: {pending_count}")

            for idx, todo in enumerate(todos, 1):
                state = todo.get("state", "unknown")
                priority = todo.get("priority", "medium")
                description = todo.get("description", "")

                logger.info(f"[VERBOSE]")
                logger.info(f"[VERBOSE]   #{idx} [{state.upper()}] [{priority.upper()}]")
                logger.info(
                    f"[VERBOSE]       {description[:150]}{'...' if len(description) > 150 else ''}"
                )

                if todo.get("created_at"):
                    logger.info(f"[VERBOSE]       Created: {todo['created_at']}")
                if todo.get("due_date"):
                    logger.info(f"[VERBOSE]       Due: {todo['due_date']}")

            logger.info("[VERBOSE] ===== END TODO LIST =====")
            logger.info("")
        else:
            logger.info("[VERBOSE] No todos found in session storage")

    except Exception as e:
        logger.warning(f"[VERBOSE] Could not retrieve todos: {e}")


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for review CLI.

    Args:
        verbose: Enable debug level logging
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
    date_format = "%H:%M:%S"

    logging.basicConfig(
        level=log_level, format=log_format, datefmt=date_format, stream=sys.stdout, force=True
    )

    from dawn_kestrel.core.settings import settings

    if settings.debug:
        logging.getLogger().setLevel(logging.DEBUG)


def get_subagents(include_optional: bool = False) -> list[object]:
    """Get list of subagents based on optional flag.

    Args:
        include_optional: If True, include optional subagents

    Returns:
        List of reviewer agents
    """
    from iron_rook.review.registry import ReviewerRegistry

    if include_optional:
        return ReviewerRegistry.get_all_reviewers()
    return ReviewerRegistry.get_core_reviewers()


def format_terminal_progress(agent_name: str, status: str, data: dict) -> None:
    """Format and print progress events to terminal.

    Args:
        agent_name: Name of the agent
        status: Status of the operation (started, completed, error)
        data: Additional data from the progress event
    """
    logger = logging.getLogger(__name__)

    if status == "started":
        console.print(f"[cyan][{agent_name}][/cyan] [dim]Started review...[/dim]")
        logger.info(f"[{agent_name}] Starting review...")
    elif status == "completed":
        console.print(f"[green][{agent_name}][/green] [dim]Completed[/dim]")
        logger.info(f"[{agent_name}] Review completed successfully")
    elif status == "error":
        error_msg = data.get("error", "Unknown error")
        console.print(f"[red][{agent_name}][/red] [dim]Error: {error_msg}[/dim]")
        logger.error(f"[{agent_name}] Error: {error_msg}")


def format_terminal_result(agent_name: str, result) -> None:
    """Format and print result events to terminal.

    Args:
        agent_name: Name of the agent
        result: ReviewOutput from the agent
    """
    if result.severity == "blocking":
        console.print(f"[red][{agent_name}][/red] Found blocking issues")
    elif result.severity == "critical":
        console.print(f"[red][{agent_name}][/red] Found critical issues")
    elif result.severity == "warning":
        console.print(f"[yellow][{agent_name}][/yellow] Found warnings")
    else:
        console.print(f"[green][{agent_name}][/green] No issues found")

    if result.findings:
        console.print(f"  [dim]{len(result.findings)} finding(s)[/dim]")


def format_terminal_error(agent_name: str, error_msg: str) -> None:
    """Format and print error events to terminal.

    Args:
        agent_name: Name of the agent
        error_msg: Error message
    """
    console.print(f"[red][{agent_name}][/red] [dim]Failed: {error_msg}[/dim]")


@click.command()
@click.option(
    "--agent",
    type=str,
    default=None,
    help="Run only a specific agent (default: run all agents).",
)
@click.option(
    "--repo-root",
    type=click.Path(exists=True, path_type=Path),
    default=Path.cwd(),
    help="Repository root directory (default: current directory)",
)
@click.option(
    "--base-ref",
    default="main",
    help="Base git reference (default: main)",
)
@click.option(
    "--head-ref",
    default="HEAD",
    help="Head git reference (default: HEAD)",
)
@click.option(
    "--output",
    type=click.Choice(["json", "markdown", "terminal"]),
    default="terminal",
    help="Output format (default: terminal)",
)
@click.option(
    "--include-optional",
    is_flag=True,
    help="Include optional review subagents",
)
@click.option(
    "--timeout",
    type=int,
    default=300,
    help="Agent timeout in seconds (default: 300)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging to see detailed progress",
)
def review(
    agent: str | None,
    repo_root: Path,
    base_ref: str,
    head_ref: str,
    output: Literal["json", "markdown", "terminal"],
    include_optional: bool,
    timeout: int,
    verbose: bool,
) -> None:
    """Run PR review on a git repository.

    Review analyzes code changes between base-ref and head-ref using
    specialized review agents running in parallel.

    Use --agent to run a single agent, or run all agents by default.

    Progress will be logged to stdout showing:
    - Which agents are starting
    - LLM calls and response sizes
    - Context building progress
    - Any errors or retries occurring
    """

    async def run_review() -> None:
        from iron_rook.review.contracts import ReviewInputs
        from iron_rook.review.orchestrator import PRReviewOrchestrator
        from iron_rook.review.registry import ReviewerRegistry
        from dawn_kestrel.agents.runtime import AgentRuntime
        from dawn_kestrel.agents.builtin import Agent
        from dawn_kestrel.agents.registry import AgentRegistry, create_agent_registry
        from iron_rook.review.utils.session_helper import (
            EphemeralSessionManager,
        )

        setup_logging(verbose)

        available_agents = set(ReviewerRegistry.get_all_names())
        if agent and agent not in available_agents:
            names = ", ".join(sorted(available_agents))
            raise click.ClickException(f"Unknown agent '{agent}'. Available agents: {names}")

        # Register security agent in shared AgentRegistry for AgentRuntime execution
        SECURITY_REVIEWER_AGENT = Agent(
            name="security",
            description="Security reviewer with tool execution support",
            mode="subagent",
            native=False,
            permission=[
                {"permission": "todowrite", "pattern": "*", "action": "allow"},
                {"permission": "todoread", "pattern": "*", "action": "allow"},
                {"permission": "*", "pattern": "*", "action": "deny"},
            ],
        )

        if agent:
            subagents = [ReviewerRegistry.create_reviewer(agent)]
            console.print(f"[cyan]Running only '{agent}' agent...[/cyan]")
        else:
            subagents = get_subagents(include_optional)
            console.print(f"[cyan]Running all {len(subagents)} agents...[/cyan]")

        if verbose:
            log_verbose_subagent_info(subagents)

        session_manager = EphemeralSessionManager()
        agent_registry = create_agent_registry()

        await agent_registry.register_agent(SECURITY_REVIEWER_AGENT)

        orchestrator = PRReviewOrchestrator(
            subagents=subagents,
            use_agent_runtime=True,
            agent_runtime=AgentRuntime(
                agent_registry=agent_registry,
                base_dir=repo_root,
            ),
            session_manager=session_manager,
            agent_registry=agent_registry,
        )

        if verbose:
            await log_verbose_todos(str(repo_root))

        inputs = ReviewInputs(
            repo_root=str(repo_root),
            base_ref=base_ref,
            head_ref=head_ref,
            include_optional=include_optional,
            timeout_seconds=timeout,
        )

        console.print(f"[cyan]Starting PR review...[/cyan]")
        console.print(f"[dim]Repo: {repo_root}[/dim]")
        console.print(f"[dim]Refs: {base_ref} -> {head_ref}[/dim]")
        console.print(f"[dim]Agents: {len(subagents)}[/dim]")
        console.print()

        if output == "terminal":

            async def stream_callback(
                agent_name: str, status: str, data: dict, result=None, error_msg: str | None = None
            ) -> None:
                if status == "started":
                    format_terminal_progress(agent_name, status, data)
                elif status == "completed" and result:
                    format_terminal_result(agent_name, result)
                    if verbose:
                        log_verbose_result_details(result)
                elif status == "error" and error_msg:
                    format_terminal_error(agent_name, error_msg)

            result = await orchestrator.run_review(inputs, stream_callback=stream_callback)
        else:
            result = await orchestrator.run_review(inputs)

        console.print()
        console.print("[cyan]Review complete[/cyan]")
        console.print(f"[dim]Total findings: {result.total_findings}[/dim]")
        console.print(f"[dim]Decision: {result.merge_decision.decision}[/dim]")
        console.print()

        if verbose:
            import logging

            logger = logging.getLogger(__name__)
            logger.info("")
            logger.info("[VERBOSE] ===== FINAL SUMMARY =====")
            logger.info(
                f"[VERBOSE] Initial agents: {len([r for r in result.subagent_results if not r.summary.startswith('Second-wave')])}"
            )
            logger.info(
                f"[VERBOSE] Second-wave agents: {len([r for r in result.subagent_results if r.summary.startswith('Second-wave')])}"
            )
            logger.info(f"[VERBOSE] Total subagent results: {len(result.subagent_results)}")
            logger.info(f"[VERBOSE] Total findings: {result.total_findings}")
            logger.info(f"[VERBOSE] Merge decision: {result.merge_decision.decision}")
            logger.info(
                f"[VERBOSE] Summary: {result.summary[:300]}{'...' if len(result.summary) > 300 else ''}"
            )
            logger.info("[VERBOSE] ===== END FINAL SUMMARY =====")
            logger.info("")

        if output == "json":
            console.print(result.model_dump_json(indent=2))
        elif output == "markdown":
            console.print(result_to_markdown(result))
        elif output == "terminal":
            print_terminal_summary(result)

    try:
        asyncio.run(run_review())
    except KeyboardInterrupt:
        console.print("\n[yellow]Review interrupted[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e))


def result_to_markdown(result) -> str:
    """Convert review result to Markdown format.

    Args:
        result: OrchestratorOutput from review

    Returns:
        Markdown formatted string
    """
    md_lines = [
        "# PR Review Results",
        "",
        f"**Decision:** {result.merge_decision.decision}",
        f"**Total Findings:** {result.total_findings}",
        "",
    ]

    if result.merge_decision.decision == "block":
        md_lines.append("## ⛔ Blocking Issues")
    elif result.merge_decision.decision == "needs_changes":
        md_lines.append("## ⚠️ Required Changes")
    elif result.merge_decision.decision == "approve_with_warnings":
        md_lines.append("## ⚠️ Review With Warnings")

    for finding in result.findings:
        emoji = (
            "🔴"
            if finding.severity == "blocking"
            else "🟠"
            if finding.severity == "critical"
            else "🟡"
        )
        md_lines.extend(
            [
                "",
                f"{emoji} **{finding.title}**",
                f"  - Severity: {finding.severity}",
                f"  - Owner: {finding.owner}",
                f"  - Estimate: {finding.estimate}",
                f"  - Evidence: `{finding.evidence}`",
                f"  - Risk: {finding.risk}",
                f"  - Recommendation: {finding.recommendation}",
            ]
        )
        if finding.suggested_patch:
            md_lines.append(f"  - Suggested patch: `{finding.suggested_patch}`")

    if result.tool_plan.proposed_commands:
        md_lines.extend(
            [
                "",
                "## Tool Plan",
                "",
            ]
        )
        for cmd in result.tool_plan.proposed_commands:
            md_lines.append(f"- `{cmd}`")

    if result.merge_decision.notes_for_coding_agent:
        md_lines.extend(
            [
                "",
                "## Notes for Coding Agent",
                "",
            ]
        )
        for note in result.merge_decision.notes_for_coding_agent:
            md_lines.append(f"- {note}")

    return "\n".join(md_lines)


def print_terminal_summary(result) -> None:
    """Print summary of review results to terminal.

    Args:
        result: OrchestratorOutput from review
    """
    if result.merge_decision.decision == "approve":
        console.print("[green]✅ Review: APPROVED for merge[/green]")
    elif result.merge_decision.decision == "approve_with_warnings":
        console.print("[yellow]⚠️  Review: APPROVED WITH WARNINGS[/yellow]")
    elif result.merge_decision.decision == "needs_changes":
        console.print("[yellow]⚠️  Review: NEEDS CHANGES[/yellow]")
    else:
        console.print("[red]⛔ Review: BLOCKED[/red]")

    console.print()

    if result.merge_decision.must_fix:
        console.print("[red]Must Fix:[/red]")
        for item in result.merge_decision.must_fix[:5]:
            console.print(f"  • {item}")
        if len(result.merge_decision.must_fix) > 5:
            console.print(f"  [dim]...and {len(result.merge_decision.must_fix) - 5} more[/dim]")
        console.print()

    if result.merge_decision.should_fix:
        console.print("[yellow]Should Fix:[/yellow]")
        for item in result.merge_decision.should_fix[:5]:
            console.print(f"  • {item}")
        if len(result.merge_decision.should_fix) > 5:
            console.print(f"  [dim]...and {len(result.merge_decision.should_fix) - 5} more[/dim]")
        console.print()

    console.print(f"[dim]Summary: {result.summary}[/dim]")


@click.command(name="docs")
@click.option(
    "--agent",
    type=str,
    default=None,
    help="Specific agent name (e.g., security, architecture)",
)
@click.option(
    "--all",
    "generate_all",
    is_flag=True,
    help="Generate documentation for all reviewers",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing documentation even if hash matches",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Custom output directory for documentation",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def docs(
    agent: str | None,
    generate_all: bool,
    force: bool,
    output: Path | None,
    verbose: bool,
) -> None:
    """Generate entry point documentation for review agents.

    Analyzes system prompts and extracts patterns to create YAML frontmatter
    documentation for reviewer agents.
    """
    setup_logging(verbose)

    console.print(f"[cyan]Generating reviewer documentation...[/cyan]")
    console.print()

    from iron_rook.review.doc_gen import DocGenAgent
    from iron_rook.review.registry import ReviewerRegistry

    all_agents = {
        name: ReviewerRegistry.create_reviewer(name) for name in ReviewerRegistry.get_all_names()
    }

    doc_gen = DocGenAgent(agents_dir=output)

    agents_to_process = []
    if generate_all:
        agents_to_process = list(all_agents.values())
        console.print(f"[dim]Processing all {len(agents_to_process)} agents[/dim]")
    elif agent:
        if agent not in all_agents:
            console.print(f"[red]Error: Unknown agent '{agent}'[/red]")
            console.print(f"[dim]Available agents: {', '.join(sorted(all_agents.keys()))}[/dim]")
            raise click.ClickException(f"Unknown agent: {agent}")
        agents_to_process = [all_agents[agent]]
        console.print(f"[dim]Processing agent: {agent}[/dim]")
    else:
        console.print("[red]Error: Specify --agent or --all[/red]")
        raise click.ClickException("Must specify --agent or --all")

    console.print()

    results = []
    for reviewer_agent in agents_to_process:
        agent_name = getattr(
            reviewer_agent,
            "get_agent_name",
            lambda: reviewer_agent.__class__.__name__.lower().replace("reviewer", ""),
        )()
        success, message = doc_gen.generate_for_agent(reviewer_agent, force=force)

        if success:
            console.print(f"[green]✓[/green] {agent_name}: {message}")
            results.append((agent_name, True, message))
        else:
            console.print(f"[red]✗[/red] {agent_name}: {message}")
            results.append((agent_name, False, message))

    console.print()

    successes = sum(1 for _, success, _ in results if success)
    failures = len(results) - successes

    if failures == 0:
        console.print(
            f"[green]✓ All {len(results)} documentation(s) generated successfully[/green]"
        )
    else:
        console.print(f"[yellow]⚠ {successes} succeeded, {failures} failed[/yellow]")
        raise click.ClickException(f"{failures} documentation(s) failed to generate")
