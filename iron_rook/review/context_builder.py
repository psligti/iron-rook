"""Context builder interface and default implementation for review agents.

This module provides the seam for building ReviewContext objects, allowing
customization of context construction logic (e.g., filtering, discovery,
fallback behavior) while maintaining a consistent interface for the orchestrator.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import ReviewInputs
from iron_rook.review.discovery import EntryPointDiscovery

logger = logging.getLogger(__name__)


class ContextBuilder(ABC):
    """Abstract interface for building ReviewContext for review agents.

    Implementations can customize how ReviewContext is constructed, including:
    - Entry point discovery and filtering
    - Fallback behavior when discovery fails
    - Context enrichment strategies

    The default implementation (DefaultContextBuilder) mirrors the original
    orchestrator behavior to ensure backward compatibility.
    """

    @abstractmethod
    async def build(
        self,
        inputs: ReviewInputs,
        agent: BaseReviewerAgent,
    ) -> ReviewContext:
        """Build ReviewContext for a specific agent.

        Args:
            inputs: ReviewInputs with review parameters
            agent: BaseReviewerAgent to build context for

        Returns:
            ReviewContext populated with review data (filtered changed_files)
        """
        pass


class DefaultContextBuilder(ContextBuilder):
    """Default context builder implementation mirroring orchestrator behavior.

    This implementation preserves the original orchestrator context building logic:
    1. Discovers entry points relevant to the agent's patterns
    2. Filters changed_files to only those containing discovered entry points
    3. Falls back to is_relevant_to_changes() if discovery fails

    This ensures backward compatibility with existing behavior while providing
    an injectable seam for customization.
    """

    def __init__(self, discovery: EntryPointDiscovery | None = None):
        """Initialize default context builder.

        Args:
            discovery: EntryPointDiscovery instance for context filtering.
                        Defaults to None (creates new instance if needed).
        """
        self.discovery = discovery or EntryPointDiscovery()

    async def build(
        self,
        inputs: ReviewInputs,
        agent: BaseReviewerAgent,
    ) -> ReviewContext:
        """Build ReviewContext for a specific agent.

        This method performs intelligent context filtering using entry point discovery:
        1. Discovers entry points relevant to the agent's patterns
        2. Filters changed_files to only those containing discovered entry points
        3. Falls back to is_relevant_to_changes() if discovery fails

        Args:
            inputs: ReviewInputs with review parameters
            agent: BaseReviewerAgent to build context for

        Returns:
            ReviewContext populated with review data (filtered changed_files)
        """
        from iron_rook.review.utils.git import get_changed_files, get_diff

        agent_name = agent.__class__.__name__

        all_changed_files = await get_changed_files(
            inputs.repo_root, inputs.base_ref, inputs.head_ref
        )

        entry_points = await self.discovery.discover_entry_points(
            agent_name=agent_name,
            repo_root=inputs.repo_root,
            changed_files=all_changed_files,
        )

        if entry_points is not None:
            ep_file_set = {ep.file_path for ep in entry_points}
            filtered_files = [f for f in all_changed_files if f in ep_file_set]
            logger.info(
                f"[{agent_name}] Entry point discovery found {len(entry_points)} entry points, "
                f"filtered to {len(filtered_files)}/{len(all_changed_files)} files"
            )
            changed_files = filtered_files
        else:
            logger.info(
                f"[{agent_name}] Entry point discovery returned None, "
                f"using is_relevant_to_changes() fallback"
            )
            if agent.is_relevant_to_changes(all_changed_files):
                changed_files = all_changed_files
            else:
                changed_files = []
                logger.info(
                    f"[{agent_name}] Agent not relevant to changes, skipping review"
                )

        diff = await get_diff(inputs.repo_root, inputs.base_ref, inputs.head_ref)

        return ReviewContext(
            changed_files=changed_files,
            diff=diff,
            repo_root=inputs.repo_root,
            base_ref=inputs.base_ref,
            head_ref=inputs.head_ref,
            pr_title=inputs.pr_title,
            pr_description=inputs.pr_description,
        )
