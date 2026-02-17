# Iron Rook

PR Review Agent - Multi-agent code review system using dawn-kestrel SDK.

## Overview

Iron Rook provides a comprehensive PR review system that runs multiple specialized agents in parallel to analyze code changes. It uses the dawn-kestrel SDK for agent execution, tool management, and LLM interactions.

## Features

- **Multi-Agent Review**: Runs specialized review agents (security, architecture, documentation, etc.) in parallel
- **Streaming Output**: Real-time progress updates during review execution
- **Delegation**: Second-wave agent delegation for follow-up analysis
- **Budget Control**: Configurable limits on delegation and execution
- **Multiple Output Formats**: JSON, Markdown, or terminal output
- **Extensible**: Easy to register custom reviewers

## Installation

```bash
pip install iron-rook
```

For development with additional dependencies:

```bash
pip install iron-rook[dev]
```

## Usage

### CLI

Run a PR review on the current repository:

```bash
iron-rook review --repo-root /path/to/repo --base-ref main --head-ref HEAD
```

Generate documentation for review agents:

```bash
iron-rook docs --agent security
```

### Python API

```python
from iron_rook.review import PRReviewOrchestrator
from iron_rook.review.registry import ReviewerRegistry

# Get default reviewers
reviewers = ReviewerRegistry.get_core_reviewers()

# Create orchestrator
orchestrator = PRReviewOrchestrator(subagents=reviewers)

# Run review
from iron_rook.review.contracts import ReviewInputs
inputs = ReviewInputs(
    repo_root="/path/to/repo",
    base_ref="main",
    head_ref="HEAD",
)

result = await orchestrator.run_review(inputs)
print(f"Merge decision: {result.merge_decision.decision}")
print(f"Total findings: {result.total_findings}")
```

## Built-in Reviewers

All 11 reviewers are core agents, each specializing in a specific analysis domain:

- **architecture**: Code architecture and design patterns
- **changelog**: Release changelog compliance
- **dependencies**: Dependency and license review
- **diff_scoper**: Change scope and impact analysis
- **documentation**: Documentation completeness and accuracy
- **linting**: Code style and linting checks
- **performance**: Performance and reliability analysis
- **requirements**: Requirements traceability review
- **security**: Security vulnerability analysis (uses FSM + subagent pattern)
- **telemetry**: Telemetry and metrics review
- **unit_tests**: Test coverage and quality

### FSM + Subagent Pattern

The security reviewer uses a Finite State Machine (FSM) architecture with specialized subagents for auth, injection, secrets, and dependency scanning. The FSM orchestrates phases: INTAKE → PLAN_TODOS → DELEGATE → COLLECT → CONSOLIDATE → EVALUATE → DONE, enabling parallel subagent execution and iterative analysis.

## Architecture

Iron Rook uses dawn-kestrel SDK for:

- **Agent Runtime**: Execution framework with tool filtering
- **Tool Registry**: Built-in tool management
- **LLM Client**: Provider-agnostic AI interactions
- **Session Management**: Ephemeral sessions for review operations

## License

MIT License - see LICENSE file for details.
