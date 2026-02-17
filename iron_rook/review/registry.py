"""Reviewer registry for agent composition.

This module provides a factory/registry seam for managing reviewer agents.
It enables dynamic registration and composition of reviewers while preserving
default behavior for backward compatibility.

Usage:
    # Get default core reviewers
    core_reviewers = ReviewerRegistry.get_core_reviewers()

    # Get all reviewers (core + optional)
    all_reviewers = ReviewerRegistry.get_all_reviewers()

    # Get specific reviewer by name
    reviewer_class = ReviewerRegistry.get_reviewer("security")
    reviewer = reviewer_class()

    # Register custom reviewer
    ReviewerRegistry.register("custom_review", CustomReviewer)

Feature Flags:
    Feature flags control the rollout of new features and can be configured
    via environment variables or programmatic configuration.

    FEATURE_ENABLE_SECOND_WAVE_DELEGATION (default: True):
        Enable/disable second-wave delegation follow-up agents.
        When False, only initial agents run; delegation requests are logged but not executed.

    FEATURE_ENABLE_BUDGET_TRACKING (default: True):
        Enable/disable budget tracking for delegation limits.
        When False, no limits are enforced on delegated actions (use with caution).

    FEATURE_MAX_DELEGATED_ACTIONS (default: 30):
        Override the default maximum number of delegated actions.
        Can be configured via environment variable FEATURE_MAX_DELEGATED_ACTIONS.

Monitoring Hooks:
    Monitoring hooks allow tracking of delegation and budget usage for observability.
    Set custom hooks via ReviewerRegistry.set_monitoring_hook().

    on_delegation_requested(agent: str, reason: str, priority: str):
        Called when a delegation request is parsed from agent output.

    on_delegation_executed(agent: str, budget_used: int, budget_remaining: int):
        Called when a delegated agent is executed.

    on_delegation_skipped(agent: str, reason: str):
        Called when a delegation request is skipped (budget exceeded, unknown agent, etc.).

    on_budget_exceeded(action_type: str, budget_used: int, budget_limit: int):
        Called when a budget limit is reached.
"""

from __future__ import annotations

import os
import logging
from typing import Dict, List, Type, Optional, Callable
from dataclasses import dataclass, field

from iron_rook.review.base import BaseReviewerAgent

logger = logging.getLogger(__name__)


# Feature flags for gradual rollout
FEATURE_ENABLE_SECOND_WAVE_DELEGATION = os.getenv(
    "FEATURE_ENABLE_SECOND_WAVE_DELEGATION", "true"
).lower() in ("true", "1", "yes")

FEATURE_ENABLE_BUDGET_TRACKING = os.getenv("FEATURE_ENABLE_BUDGET_TRACKING", "true").lower() in (
    "true",
    "1",
    "yes",
)

FEATURE_MAX_DELEGATED_ACTIONS = int(os.getenv("FEATURE_MAX_DELEGATED_ACTIONS", "30"))


@dataclass
class MonitoringHooks:
    """Monitoring hooks for tracking delegation and budget usage."""

    on_delegation_requested: Optional[Callable[[str, str, str], None]] = field(default=None)
    on_delegation_executed: Optional[Callable[[str, int, int], None]] = field(default=None)
    on_delegation_skipped: Optional[Callable[[str, str], None]] = field(default=None)
    on_budget_exceeded: Optional[Callable[[str, int, int], None]] = field(default=None)


class ReviewerRegistry:
    """Registry for managing reviewer agent classes.

    Provides factory methods for creating reviewer instances and supports
    dynamic registration of custom reviewers. Default reviewers are registered
    at module import time.

    Thread-safety: This class uses class-level state and is not thread-safe.
    Concurrent modifications should be avoided.

    Feature flags and monitoring hooks can be configured at the class level
    for controlling rollout and observability.
    """

    _registry: Dict[str, Type[BaseReviewerAgent]] = {}
    _core_reviewers: List[str] = []
    _optional_reviewers: List[str] = []
    _monitoring_hooks: MonitoringHooks = MonitoringHooks()

    @classmethod
    def register(
        cls,
        name: str,
        reviewer_class: Type[BaseReviewerAgent],
        is_core: bool = False,
    ) -> None:
        """Register a reviewer class.

        Args:
            name: Unique name for the reviewer (used for CLI selection)
            reviewer_class: Reviewer class to register
            is_core: If True, reviewer is in core set (default: False = optional)

        Raises:
            ValueError: If reviewer name already registered
        """
        if name in cls._registry:
            raise ValueError(f"Reviewer '{name}' already registered")

        cls._registry[name] = reviewer_class

        if is_core:
            if name not in cls._core_reviewers:
                cls._core_reviewers.append(name)
        else:
            if name not in cls._optional_reviewers:
                cls._optional_reviewers.append(name)

    @classmethod
    def get_reviewer(cls, name: str) -> Type[BaseReviewerAgent]:
        """Get reviewer class by name.

        Args:
            name: Registered reviewer name

        Returns:
            Reviewer class

        Raises:
            KeyError: If reviewer name not found in registry
        """
        if name not in cls._registry:
            raise KeyError(
                f"Unknown reviewer: '{name}'. "
                f"Available reviewers: {', '.join(sorted(cls._registry.keys()))}"
            )
        return cls._registry[name]

    @classmethod
    def create_reviewer(cls, name: str) -> BaseReviewerAgent:
        """Create reviewer instance by name.

        Args:
            name: Registered reviewer name

        Returns:
            Reviewer instance

        Raises:
            KeyError: If reviewer name not found in registry
        """
        reviewer_class = cls.get_reviewer(name)
        return reviewer_class()

    @classmethod
    def get_core_reviewers(cls) -> List[BaseReviewerAgent]:
        """Get list of core reviewer instances.

        Returns:
            List of instantiated core reviewers
        """
        return [cls.create_reviewer(name) for name in cls._core_reviewers]

    @classmethod
    def get_all_reviewers(cls) -> List[BaseReviewerAgent]:
        """Get list of all reviewer instances (core + optional).

        Returns:
            List of instantiated reviewers
        """
        all_names = cls._core_reviewers + cls._optional_reviewers
        return [cls.create_reviewer(name) for name in all_names]

    @classmethod
    def get_all_names(cls) -> List[str]:
        """Get list of all registered reviewer names.

        Returns:
            Sorted list of reviewer names
        """
        return sorted(cls._registry.keys())

    @classmethod
    def get_core_names(cls) -> List[str]:
        """Get list of core reviewer names.

        Returns:
            Sorted list of core reviewer names
        """
        return sorted(cls._core_reviewers)

    @classmethod
    def get_optional_names(cls) -> List[str]:
        """Get list of optional reviewer names.

        Returns:
            Sorted list of optional reviewer names
        """
        return sorted(cls._optional_reviewers)

    @classmethod
    def set_monitoring_hooks(cls, hooks: MonitoringHooks) -> None:
        """Set custom monitoring hooks for delegation and budget tracking.

        Args:
            hooks: MonitoringHooks instance with callback functions
        """
        cls._monitoring_hooks = hooks

    @classmethod
    def get_monitoring_hooks(cls) -> MonitoringHooks:
        """Get current monitoring hooks.

        Returns:
            Current MonitoringHooks instance
        """
        return cls._monitoring_hooks

    @classmethod
    def is_second_wave_delegation_enabled(cls) -> bool:
        """Check if second-wave delegation is enabled via feature flag.

        Returns:
            True if second-wave delegation is enabled
        """
        return FEATURE_ENABLE_SECOND_WAVE_DELEGATION

    @classmethod
    def is_budget_tracking_enabled(cls) -> bool:
        """Check if budget tracking is enabled via feature flag.

        Returns:
            True if budget tracking is enabled
        """
        return FEATURE_ENABLE_BUDGET_TRACKING

    @classmethod
    def get_max_delegated_actions(cls) -> int:
        """Get the maximum number of delegated actions allowed.

        Returns:
            Maximum delegated actions from feature flag or default
        """
        return FEATURE_MAX_DELEGATED_ACTIONS


def _register_default_reviewers() -> None:
    """Register all default reviewers at module import time."""
    from iron_rook.review.agents.security import SecurityReviewer
    from iron_rook.review.agents.architecture import ArchitectureReviewer
    from iron_rook.review.agents.documentation import DocumentationReviewer
    from iron_rook.review.agents.telemetry import TelemetryMetricsReviewer
    from iron_rook.review.agents.linting import LintingReviewer
    from iron_rook.review.agents.unit_tests import UnitTestsReviewer
    from iron_rook.review.agents.diff_scoper import DiffScoperReviewer
    from iron_rook.review.agents.requirements import RequirementsReviewer
    from iron_rook.review.agents.performance import PerformanceReliabilityReviewer
    from iron_rook.review.agents.dependencies import DependencyLicenseReviewer
    from iron_rook.review.agents.changelog import ReleaseChangelogReviewer
    from iron_rook.review.skills.delegate_todo import DelegateTodoSkill

    # Register core reviewers
    ReviewerRegistry.register("security", SecurityReviewer, is_core=True)
    ReviewerRegistry.register("architecture", ArchitectureReviewer, is_core=True)
    ReviewerRegistry.register("documentation", DocumentationReviewer, is_core=True)
    ReviewerRegistry.register("telemetry", TelemetryMetricsReviewer, is_core=True)
    ReviewerRegistry.register("linting", LintingReviewer, is_core=True)
    ReviewerRegistry.register("unit_tests", UnitTestsReviewer, is_core=True)

    # Register optional reviewers
    ReviewerRegistry.register("diff_scoper", DiffScoperReviewer, is_core=False)
    ReviewerRegistry.register("requirements", RequirementsReviewer, is_core=False)
    ReviewerRegistry.register("performance", PerformanceReliabilityReviewer, is_core=False)
    ReviewerRegistry.register("dependencies", DependencyLicenseReviewer, is_core=False)
    ReviewerRegistry.register("changelog", ReleaseChangelogReviewer, is_core=False)
    ReviewerRegistry.register("delegate_todo", DelegateTodoSkill, is_core=False)


_register_default_reviewers()
