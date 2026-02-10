"""Ephemeral session management for security review.

This module provides utilities for creating and managing temporary sessions
specifically for security review operations. Sessions are stored in-memory
(ephemeral) and not persisted across review calls.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime
from typing import Dict, Optional, List

from iron_rook.review.base import ReviewContext
from dawn_kestrel.core.models import Session
from dawn_kestrel.core.agent_types import SessionManagerLike
from dawn_kestrel.core.models import Message, Part

logger = logging.getLogger(__name__)

_ephemeral_sessions_by_id: Dict[str, Session] = {}


class EphemeralSessionManager(SessionManagerLike):
    """Session manager for ephemeral (in-memory) review sessions.

    This SessionManagerLike implementation wraps ephemeral session storage
    to provide interface required by AgentRuntime.
    """

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get an ephemeral session by ID."""
        session = get_review_session(session_id)
        if session is None:
            from iron_rook.review.base import ReviewContext

            context = ReviewContext(
                changed_files=[],
                diff="",
                repo_root="",
                pr_title="Security Review",
            )
            session = create_review_session("", context)
        return session

    async def list_messages(self, session_id: str) -> List[Message]:
        """List all messages for a session."""
        return []

    async def add_message(self, message: Message) -> str:
        """Add a message to a session, returns message ID."""
        return "ephemeral"

    async def add_part(self, part: Part) -> str:
        """Add a part to a message, returns part ID."""
        return "ephemeral-part"

    async def release_session(self, session_id: str) -> None:
        """Release a session - cleanup ephemeral session."""
        if session_id in _ephemeral_sessions_by_id:
            del _ephemeral_sessions_by_id[session_id]
            logger.info(f"Released ephemeral review session: {session_id}")
        else:
            logger.debug(f"Session not found for release: {session_id}")


def create_review_session(repo_root: str, context: ReviewContext) -> Session:
    """Create an ephemeral session for security review.

    Sessions are created with a specific ID format and stored in-memory only.
    They are not persisted across review calls.

    Args:
        repo_root: Repository root path (used as project_id and directory)
        context: ReviewContext containing PR information

    Returns:
        Session object with ephemeral lifecycle

    Example:
        >>> context = ReviewContext(
        ...     changed_files=["src/main.py"],
        ...     diff="...",
        ...     repo_root="/path/to/repo",
        ...     pr_title="Fix auth bug"
        ... )
        >>> session = create_review_session("/path/to/repo", context)
        >>> print(session.id)  # security-review-1738900000-a1b2c3d4
    """
    timestamp = int(datetime.now().timestamp())
    random_bytes = secrets.token_hex(4)
    session_id = f"security-review-{timestamp}-{random_bytes}"

    pr_title = context.pr_title or "PR Review"
    title = f"Security Review: {pr_title}"
    slug = title.lower().replace(" ", "-")

    session = Session(
        id=session_id,
        slug=slug,
        project_id=repo_root,
        directory=repo_root,
        parent_id=None,
        title=title,
        version="1.0.0",
        summary=None,
        share=None,
        permission=None,
        revert=None,
    )

    _ephemeral_sessions_by_id[session_id] = session

    logger.info(
        f"Created ephemeral review session: {session_id} (repo_root={repo_root}, title='{title}')"
    )

    return session


def cleanup_review_session(session_id: str, project_id: str) -> bool:
    """Remove an ephemeral review session from in-memory storage.

    Args:
        session_id: ID of the session to cleanup
        project_id: Project ID (repo_root) for validation

    Returns:
        True if session was found and removed, False otherwise

    Example:
        >>> session_id = "security-review-1738900000-a1b2c3d4"
        >>> cleanup_review_session(session_id, "/path/to/repo")
        True
    """
    if session_id in _ephemeral_sessions_by_id:
        session = _ephemeral_sessions_by_id[session_id]

        if session.project_id != project_id:
            logger.warning(
                f"Session {session_id} project_id mismatch: "
                f"expected {project_id}, got {session.project_id}"
            )

        del _ephemeral_sessions_by_id[session_id]
        logger.info(f"Cleaned up ephemeral review session: {session_id}")
        return True

    logger.debug(f"Session not found for cleanup: {session_id}")
    return False


def get_review_session(session_id: str) -> Optional[Session]:
    """Get an ephemeral review session by ID.

    Args:
        session_id: ID of the session to retrieve

    Returns:
        Session object if found, None otherwise

    Example:
        >>> session_id = "security-review-1738900000-a1b2c3d4"
        >>> session = get_review_session(session_id)
        >>> if session:
        ...     print(session.title)
    """
    return _ephemeral_sessions_by_id.get(session_id)
