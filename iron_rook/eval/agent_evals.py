"""Comprehensive evaluation suites for all 11 iron-rook reviewer agents.

Each agent has a dedicated evaluation suite with:
- LLM rubrics for domain-specific evaluation
- Tool call verification graders
- Delegation effectiveness metrics
- Finding quality criteria

Usage:
    from iron_rook.eval.agent_evals import (
        SECURITY_EVAL_SUITE,
        ARCHITECTURE_EVAL_SUITE,
        get_all_agent_suites,
    )

    runner = ReviewEvalRunner()
    summary = await runner.run_suite(SECURITY_EVAL_SUITE)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ash_hawk.types import (
    EvalSuite,
    EvalTask,
    EvalAgentConfig,
    GraderSpec,
    ToolSurfacePolicy,
)

RUBRICS_DIR = Path(__file__).parent / "rubrics"


def _get_judge_config() -> dict[str, str]:
    from dawn_kestrel.core.settings import get_settings

    settings = get_settings()
    default_account = settings.get_default_account()

    if default_account:
        return {
            "judge_provider": default_account.provider_id.value,
            "judge_model": default_account.model,
        }

    return {
        "judge_provider": settings.provider_default,
        "judge_model": settings.model_default,
    }


_JUDGE_CONFIG = _get_judge_config()


def _make_agent_config(reviewer_name: str) -> EvalAgentConfig:
    """Create agent config for iron-rook reviewer using dawn-kestrel settings."""
    settings = _get_settings()
    account = settings.get_default_account()

    if account:
        provider = account.provider_id.value
        model = account.model
    else:
        provider = settings.provider_default
        model = settings.model_default

    return EvalAgentConfig.model_validate(
        {
            "name": reviewer_name,
            "provider": provider,
            "model": model,
            "class": "iron_rook.eval.agent_runner:IronRookRunner",
            "kwargs": {"reviewer": reviewer_name},
        }
    )


def _get_settings():
    from dawn_kestrel.core.settings import get_settings

    return get_settings()


def _make_llm_judge(
    rubric_path: str,
    pass_threshold: float = 0.7,
    weight: float = 0.5,
    n_judges: int = 1,
    confidence_threshold: float = 0.70,
) -> GraderSpec:
    return GraderSpec(
        grader_type="llm_judge",
        config={
            "rubric": "custom",
            "custom_prompt_path": rubric_path,
            "pass_threshold": pass_threshold,
            "n_judges": n_judges,
            "confidence_threshold": confidence_threshold,
            **_JUDGE_CONFIG,
        },
        weight=weight,
        required=True,
    )


def _make_tool_call_grader(expected_tools: list[str], weight: float = 0.15) -> GraderSpec:
    return GraderSpec(
        grader_type="tool_call",
        config={
            "expected_calls": [{"tool": tool, "min_count": 1} for tool in expected_tools],
            "require_all": False,
            "partial_credit": True,
        },
        weight=weight,
        required=False,
    )


def _make_schema_grader(weight: float = 0.15) -> GraderSpec:
    return GraderSpec(
        grader_type="schema",
        config={
            "required_fields": ["agent", "summary", "severity", "findings", "merge_gate"],
            "allow_extra_fields": True,
        },
        weight=weight,
        required=True,
    )


def _make_string_match_grader(
    expected_keywords: list[str], weight: float = 0.1, mode: str = "contains"
) -> GraderSpec:
    return GraderSpec(
        grader_type="string_match",
        config={
            "mode": mode,
            "contains": expected_keywords,
        },
        weight=weight,
        required=False,
    )


def _make_transcript_grader(weight: float = 0.1) -> GraderSpec:
    return GraderSpec(
        grader_type="transcript",
        config={
            "max_turns": 50,
            "min_turns": 1,
            "max_tool_calls": 100,
            "require_no_errors": True,
        },
        weight=weight,
        required=False,
    )


def _make_manual_review_grader(reviewer_instructions: str, weight: float = 0.2) -> GraderSpec:
    return GraderSpec(
        grader_type="manual_review",
        config={
            "reviewer_instructions": reviewer_instructions,
        },
        weight=weight,
        required=False,
    )


def _make_security_graders(
    rubric_path: str,
    expected_tools: list[str],
    expected_keywords: list[str],
    manual_review: bool = False,
    use_multi_judge: bool = True,
) -> list[GraderSpec]:
    n_judges = 2 if use_multi_judge else 1
    graders = [
        _make_llm_judge(
            rubric_path,
            pass_threshold=0.65,
            weight=0.4,
            n_judges=n_judges,
            confidence_threshold=0.65,
        ),
        _make_string_match_grader(expected_keywords, weight=0.1),
        _make_tool_call_grader(expected_tools, weight=0.15),
        _make_schema_grader(weight=0.15),
        _make_transcript_grader(weight=0.1),
    ]
    if manual_review:
        graders.append(
            _make_manual_review_grader(
                "Verify security findings are valid and severity is appropriate",
                weight=0.1,
            )
        )
    return graders


def _make_architecture_graders(
    rubric_path: str,
    expected_tools: list[str],
    expected_keywords: list[str],
    use_multi_judge: bool = True,
) -> list[GraderSpec]:
    n_judges = 2 if use_multi_judge else 1
    return [
        _make_llm_judge(rubric_path, pass_threshold=0.65, weight=0.4, n_judges=n_judges),
        _make_string_match_grader(expected_keywords, weight=0.1),
        _make_tool_call_grader(expected_tools, weight=0.15),
        _make_schema_grader(weight=0.15),
        _make_transcript_grader(weight=0.1),
    ]


def _make_generic_graders(
    rubric_path: str,
    expected_tools: list[str],
    expected_keywords: list[str],
    use_multi_judge: bool = False,
) -> list[GraderSpec]:
    n_judges = 2 if use_multi_judge else 1
    return [
        _make_llm_judge(rubric_path, pass_threshold=0.6, weight=0.4, n_judges=n_judges),
        _make_string_match_grader(expected_keywords, weight=0.1),
        _make_tool_call_grader(expected_tools, weight=0.15),
        _make_schema_grader(weight=0.15),
        _make_transcript_grader(weight=0.1),
    ]


SECURITY_EVAL_SUITE = EvalSuite(
    id="security-review-v1",
    name="Security Review Agent Evaluation",
    description="Evaluates security reviewer on vulnerability detection, severity accuracy, and delegation",
    version="1.0.0",
    tags=["security", "vulnerability", "owasp"],
    tasks=[
        EvalTask(
            id="security-sql-injection",
            description="Detect SQL injection vulnerabilities",
            input={
                "repo_root": "$fixtures/sql-injection",
                "agent": "security",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should detect SQL injection with critical/blocking severity",
            grader_specs=_make_security_graders(
                str(RUBRICS_DIR / "security_review.md"),
                expected_tools=["grep", "read", "ast-grep"],
                expected_keywords=["SQL injection", "parameterized", "f-string", "vulnerability"],
                manual_review=True,
            ),
            tags=["injection", "sql", "critical"],
            fixtures={"fixtures": "./fixtures/security/sql_injection"},
        ),
        EvalTask(
            id="security-hardcoded-secrets",
            description="Detect hardcoded API keys and secrets",
            input={
                "repo_root": "$fixtures/secrets",
                "agent": "security",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should detect hardcoded secrets with blocking severity",
            grader_specs=_make_security_graders(
                str(RUBRICS_DIR / "security_review.md"),
                expected_tools=["grep", "read"],
                expected_keywords=["hardcoded", "secret", "credential", "API key", "password"],
                manual_review=True,
            ),
            tags=["secrets", "credentials", "blocking"],
            fixtures={"fixtures": "./fixtures/security/secrets"},
        ),
        EvalTask(
            id="security-xss",
            description="Detect cross-site scripting vulnerabilities",
            input={
                "repo_root": "$fixtures/xss",
                "agent": "security",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should detect XSS vulnerabilities with proper severity",
            grader_specs=_make_security_graders(
                str(RUBRICS_DIR / "security_review.md"),
                expected_tools=["grep", "read"],
                expected_keywords=[
                    "XSS",
                    "cross-site scripting",
                    "sanitize",
                    "escape",
                    "vulnerability",
                ],
            ),
            tags=["xss", "injection", "web"],
            fixtures={"fixtures": "./fixtures/security/xss"},
        ),
        EvalTask(
            id="security-auth-bypass",
            description="Detect authentication bypass risks",
            input={
                "repo_root": "$fixtures/auth-bypass",
                "agent": "security",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should detect auth vulnerabilities and delegation to auth subagent",
            grader_specs=_make_security_graders(
                str(RUBRICS_DIR / "security_review.md"),
                expected_tools=["grep", "read"],
                expected_keywords=[
                    "authentication",
                    "bypass",
                    "authorization",
                    "session",
                    "vulnerability",
                ],
            ),
            tags=["auth", "authentication", "bypass"],
            fixtures={"fixtures": "./fixtures/security/auth_bypass"},
        ),
    ],
    agent=_make_agent_config("security"),
)


ARCHITECTURE_EVAL_SUITE = EvalSuite(
    id="architecture-review-v1",
    name="Architecture Review Agent Evaluation",
    description="Evaluates architecture reviewer on boundary detection, coupling analysis, and anti-patterns",
    version="1.0.0",
    tags=["architecture", "design", "patterns"],
    tasks=[
        EvalTask(
            id="arch-boundary-violation",
            description="Detect layering and boundary violations",
            input={
                "repo_root": "$fixtures/boundary-violation",
                "agent": "architecture",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should detect improper layer dependencies and boundary violations",
            grader_specs=_make_architecture_graders(
                str(RUBRICS_DIR / "architecture_review.md"),
                expected_tools=["ast-grep", "grep", "read"],
                expected_keywords=["boundary", "layer", "violation", "dependency", "coupling"],
            ),
            tags=["boundaries", "layers", "violation"],
            fixtures={"fixtures": "./fixtures/architecture/boundary_violation"},
        ),
        EvalTask(
            id="arch-circular-deps",
            description="Detect circular dependencies",
            input={
                "repo_root": "$fixtures/circular-deps",
                "agent": "architecture",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should detect circular import/dependency chains",
            grader_specs=_make_architecture_graders(
                str(RUBRICS_DIR / "architecture_review.md"),
                expected_tools=["ast-grep", "grep"],
                expected_keywords=["circular", "dependency", "import", "cycle"],
            ),
            tags=["circular", "dependencies", "coupling"],
            fixtures={"fixtures": "./fixtures/architecture/circular_deps"},
        ),
        EvalTask(
            id="arch-god-object",
            description="Detect god object anti-pattern",
            input={
                "repo_root": "$fixtures/god-object",
                "agent": "architecture",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should identify god objects with too many responsibilities",
            grader_specs=_make_architecture_graders(
                str(RUBRICS_DIR / "architecture_review.md"),
                expected_tools=["ast-grep", "grep", "read"],
                expected_keywords=["god object", "responsibility", "cohesion", "anti-pattern"],
            ),
            tags=["anti-pattern", "god-object", "cohesion"],
            fixtures={"fixtures": "./fixtures/architecture/god_object"},
        ),
    ],
    agent=_make_agent_config("architecture"),
)


DOCUMENTATION_EVAL_SUITE = EvalSuite(
    id="documentation-review-v1",
    name="Documentation Review Agent Evaluation",
    description="Evaluates documentation reviewer on docstring completeness and accuracy",
    version="1.0.0",
    tags=["documentation", "docstrings", "api-docs"],
    tasks=[
        EvalTask(
            id="doc-missing-docstrings",
            description="Detect missing docstrings on public APIs",
            input={
                "repo_root": "$fixtures/missing-docs",
                "agent": "documentation",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should identify public functions/classes lacking docstrings",
            grader_specs=_make_generic_graders(
                str(RUBRICS_DIR / "review_quality.md"),
                expected_tools=["grep", "read", "ast-grep"],
                expected_keywords=["docstring", "missing", "documentation", "public API"],
            ),
            tags=["docstrings", "public-api", "missing"],
            fixtures={"fixtures": "./fixtures/documentation/missing_docs"},
        ),
        EvalTask(
            id="doc-outdated-readme",
            description="Detect outdated README content",
            input={
                "repo_root": "$fixtures/outdated-readme",
                "agent": "documentation",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should identify when code changes require README updates",
            grader_specs=_make_generic_graders(
                str(RUBRICS_DIR / "review_quality.md"),
                expected_tools=["grep", "read"],
                expected_keywords=["readme", "outdated", "documentation", "update"],
            ),
            tags=["readme", "outdated", "usage"],
            fixtures={"fixtures": "./fixtures/documentation/outdated_readme"},
        ),
    ],
    agent=_make_agent_config("documentation"),
)


UNIT_TESTS_EVAL_SUITE = EvalSuite(
    id="unit-tests-review-v1",
    name="Unit Tests Review Agent Evaluation",
    description="Evaluates unit tests reviewer on test adequacy and correctness",
    version="1.0.0",
    tags=["testing", "unit-tests", "coverage"],
    tasks=[
        EvalTask(
            id="tests-missing-coverage",
            description="Detect missing test coverage for new code",
            input={
                "repo_root": "$fixtures/missing-tests",
                "agent": "unit_tests",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should identify code paths lacking test coverage",
            grader_specs=_make_generic_graders(
                str(RUBRICS_DIR / "review_quality.md"),
                expected_tools=["grep", "read", "python"],
                expected_keywords=["coverage", "test", "missing", "unit test"],
            ),
            tags=["coverage", "missing-tests", "adequacy"],
            fixtures={"fixtures": "./fixtures/unit_tests/missing_tests"},
        ),
        EvalTask(
            id="tests-brittle-assertions",
            description="Detect brittle test patterns",
            input={
                "repo_root": "$fixtures/brittle-tests",
                "agent": "unit_tests",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should identify time/randomness/network-dependent tests",
            grader_specs=_make_generic_graders(
                str(RUBRICS_DIR / "review_quality.md"),
                expected_tools=["grep", "read"],
                expected_keywords=["brittle", "flaky", "deterministic", "test"],
            ),
            tags=["brittle", "flaky", "determinism"],
            fixtures={"fixtures": "./fixtures/unit_tests/brittle_tests"},
        ),
    ],
    agent=_make_agent_config("unit_tests"),
)


LINTING_EVAL_SUITE = EvalSuite(
    id="linting-review-v1",
    name="Linting Review Agent Evaluation",
    description="Evaluates linting reviewer on style, formatting, and code quality issues",
    version="1.0.0",
    tags=["linting", "formatting", "style"],
    tasks=[
        EvalTask(
            id="linting-style-violations",
            description="Detect style and formatting violations",
            input={
                "repo_root": "$fixtures/style-violations",
                "agent": "linting",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should detect formatting issues and import problems",
            grader_specs=_make_generic_graders(
                str(RUBRICS_DIR / "review_quality.md"),
                expected_tools=["ruff", "grep", "read"],
                expected_keywords=["style", "formatting", "lint", "violation"],
            ),
            tags=["style", "formatting", "ruff"],
            fixtures={"fixtures": "./fixtures/linting/style_violations"},
        ),
        EvalTask(
            id="linting-type-hints",
            description="Detect missing or incorrect type hints",
            input={
                "repo_root": "$fixtures/type-hints",
                "agent": "linting",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should identify missing type annotations",
            grader_specs=_make_generic_graders(
                str(RUBRICS_DIR / "review_quality.md"),
                expected_tools=["mypy", "grep", "read"],
                expected_keywords=["type", "annotation", "hint", "mypy"],
            ),
            tags=["type-hints", "mypy", "annotations"],
            fixtures={"fixtures": "./fixtures/linting/type_hints"},
        ),
    ],
    agent=_make_agent_config("linting"),
)


PERFORMANCE_EVAL_SUITE = EvalSuite(
    id="performance-review-v1",
    name="Performance Review Agent Evaluation",
    description="Evaluates performance reviewer on complexity, IO, and concurrency issues",
    version="1.0.0",
    tags=["performance", "complexity", "optimization"],
    tasks=[
        EvalTask(
            id="perf-n2-complexity",
            description="Detect O(n^2) or worse complexity",
            input={
                "repo_root": "$fixtures/n2-complexity",
                "agent": "performance",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should detect nested loops with complexity issues",
            grader_specs=_make_generic_graders(
                str(RUBRICS_DIR / "review_quality.md"),
                expected_tools=["ast-grep", "grep", "read"],
                expected_keywords=["complexity", "nested loop", "O(n", "performance"],
            ),
            tags=["complexity", "nested-loops", "performance"],
            fixtures={"fixtures": "./fixtures/performance/n2_complexity"},
        ),
        EvalTask(
            id="perf-io-amplification",
            description="Detect IO amplification patterns",
            input={
                "repo_root": "$fixtures/io-amplification",
                "agent": "performance",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should detect N+1 queries and excessive IO operations",
            grader_specs=_make_generic_graders(
                str(RUBRICS_DIR / "review_quality.md"),
                expected_tools=["grep", "read"],
                expected_keywords=["IO", "N+1", "database", "query", "amplification"],
            ),
            tags=["io", "n+1", "database"],
            fixtures={"fixtures": "./fixtures/performance/io_amplification"},
        ),
    ],
    agent=_make_agent_config("performance"),
)


DEPENDENCIES_EVAL_SUITE = EvalSuite(
    id="dependencies-review-v1",
    name="Dependencies Review Agent Evaluation",
    description="Evaluates dependency reviewer on vulnerabilities and license compliance",
    version="1.0.0",
    tags=["dependencies", "licenses", "vulnerabilities"],
    tasks=[
        EvalTask(
            id="deps-vulnerable-package",
            description="Detect vulnerable dependencies",
            input={
                "repo_root": "$fixtures/vulnerable-deps",
                "agent": "dependencies",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should identify packages with known CVEs",
            grader_specs=_make_generic_graders(
                str(RUBRICS_DIR / "review_quality.md"),
                expected_tools=["grep", "read", "pip-audit"],
                expected_keywords=["CVE", "vulnerability", "dependency", "package"],
            ),
            tags=["cve", "vulnerability", "supply-chain"],
            fixtures={"fixtures": "./fixtures/dependencies/vulnerable_deps"},
        ),
        EvalTask(
            id="deps-license-compliance",
            description="Detect license compliance issues",
            input={
                "repo_root": "$fixtures/license-issues",
                "agent": "dependencies",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should identify incompatible or problematic licenses",
            grader_specs=_make_generic_graders(
                str(RUBRICS_DIR / "review_quality.md"),
                expected_tools=["grep", "read"],
                expected_keywords=["license", "compliance", "legal", "dependency"],
            ),
            tags=["license", "compliance", "legal"],
            fixtures={"fixtures": "./fixtures/dependencies/license_issues"},
        ),
    ],
    agent=_make_agent_config("dependencies"),
)


TELEMETRY_EVAL_SUITE = EvalSuite(
    id="telemetry-review-v1",
    name="Telemetry Review Agent Evaluation",
    description="Evaluates telemetry reviewer on metrics instrumentation and schema",
    version="1.0.0",
    tags=["telemetry", "metrics", "observability"],
    tasks=[
        EvalTask(
            id="telemetry-missing-metrics",
            description="Detect missing metrics instrumentation",
            input={
                "repo_root": "$fixtures/missing-metrics",
                "agent": "telemetry",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should identify code paths lacking metrics",
            grader_specs=_make_generic_graders(
                str(RUBRICS_DIR / "review_quality.md"),
                expected_tools=["grep", "ast-grep", "read"],
                expected_keywords=["metrics", "instrumentation", "telemetry", "observability"],
            ),
            tags=["metrics", "instrumentation", "observability"],
            fixtures={"fixtures": "./fixtures/telemetry/missing_metrics"},
        ),
    ],
    agent=_make_agent_config("telemetry"),
)


REQUIREMENTS_EVAL_SUITE = EvalSuite(
    id="requirements-review-v1",
    name="Requirements Review Agent Evaluation",
    description="Evaluates requirements reviewer on traceability and completeness",
    version="1.0.0",
    tags=["requirements", "traceability", "compliance"],
    tasks=[
        EvalTask(
            id="reqs-missing-implementation",
            description="Detect requirements lacking implementation",
            input={
                "repo_root": "$fixtures/missing-implementation",
                "agent": "requirements",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should identify requirements without corresponding code",
            grader_specs=_make_generic_graders(
                str(RUBRICS_DIR / "review_quality.md"),
                expected_tools=["grep", "read"],
                expected_keywords=["requirement", "implementation", "traceability", "coverage"],
            ),
            tags=["traceability", "implementation", "coverage"],
            fixtures={"fixtures": "./fixtures/requirements/missing_implementation"},
        ),
    ],
    agent=_make_agent_config("requirements"),
)


DIFF_SCOPER_EVAL_SUITE = EvalSuite(
    id="diff-scoper-review-v1",
    name="Diff Scoper Review Agent Evaluation",
    description="Evaluates diff scoper on change classification and routing accuracy",
    version="1.0.0",
    tags=["diff", "scoping", "routing"],
    tasks=[
        EvalTask(
            id="scoper-risk-classification",
            description="Test risk classification accuracy",
            input={
                "repo_root": "$fixtures/risk-changes",
                "agent": "diff_scoper",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should correctly classify risk level and route to appropriate agents",
            grader_specs=_make_generic_graders(
                str(RUBRICS_DIR / "review_quality.md"),
                expected_tools=["git", "grep"],
                expected_keywords=["risk", "classification", "routing", "change"],
            ),
            tags=["risk", "classification", "routing"],
            fixtures={"fixtures": "./fixtures/diff_scoper/risk_changes"},
        ),
    ],
    agent=_make_agent_config("diff_scoper"),
)


CHANGELOG_EVAL_SUITE = EvalSuite(
    id="changelog-review-v1",
    name="Changelog Review Agent Evaluation",
    description="Evaluates changelog reviewer on compliance and completeness",
    version="1.0.0",
    tags=["changelog", "release", "versioning"],
    tasks=[
        EvalTask(
            id="changelog-missing-entry",
            description="Detect missing changelog entries for changes",
            input={
                "repo_root": "$fixtures/missing-changelog",
                "agent": "changelog",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should identify changes requiring changelog updates",
            grader_specs=_make_generic_graders(
                str(RUBRICS_DIR / "review_quality.md"),
                expected_tools=["grep", "read", "git"],
                expected_keywords=["changelog", "release", "entry", "update"],
            ),
            tags=["changelog", "release-notes", "missing"],
            fixtures={"fixtures": "./fixtures/changelog/missing_changelog"},
        ),
    ],
    agent=_make_agent_config("changelog"),
)


ALL_AGENT_SUITES: dict[str, EvalSuite] = {
    "security": SECURITY_EVAL_SUITE,
    "architecture": ARCHITECTURE_EVAL_SUITE,
    "documentation": DOCUMENTATION_EVAL_SUITE,
    "unit_tests": UNIT_TESTS_EVAL_SUITE,
    "linting": LINTING_EVAL_SUITE,
    "performance": PERFORMANCE_EVAL_SUITE,
    "dependencies": DEPENDENCIES_EVAL_SUITE,
    "telemetry": TELEMETRY_EVAL_SUITE,
    "requirements": REQUIREMENTS_EVAL_SUITE,
    "diff_scoper": DIFF_SCOPER_EVAL_SUITE,
    "changelog": CHANGELOG_EVAL_SUITE,
}


def get_agent_suite(agent_name: str) -> EvalSuite | None:
    return ALL_AGENT_SUITES.get(agent_name)


def get_all_agent_suites() -> list[EvalSuite]:
    return list(ALL_AGENT_SUITES.values())


def get_comprehensive_suite() -> EvalSuite:
    all_tasks: list[EvalTask] = []
    for suite in ALL_AGENT_SUITES.values():
        all_tasks.extend(suite.tasks)

    return EvalSuite(
        id="comprehensive-review-v1",
        name="Comprehensive Review Agent Evaluation",
        description="Evaluates all 11 reviewer agents across their capabilities",
        version="1.0.0",
        tags=["comprehensive", "all-agents", "full-eval"],
        tasks=all_tasks,
    )


__all__ = [
    "SECURITY_EVAL_SUITE",
    "ARCHITECTURE_EVAL_SUITE",
    "DOCUMENTATION_EVAL_SUITE",
    "UNIT_TESTS_EVAL_SUITE",
    "LINTING_EVAL_SUITE",
    "PERFORMANCE_EVAL_SUITE",
    "DEPENDENCIES_EVAL_SUITE",
    "TELEMETRY_EVAL_SUITE",
    "REQUIREMENTS_EVAL_SUITE",
    "DIFF_SCOPER_EVAL_SUITE",
    "CHANGELOG_EVAL_SUITE",
    "ALL_AGENT_SUITES",
    "get_agent_suite",
    "get_all_agent_suites",
    "get_comprehensive_suite",
]
