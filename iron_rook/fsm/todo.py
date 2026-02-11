"""Todo model for FSM-based task tracking.

This module provides Todo class for tracking individual tasks in FSM-based
orchestrators with status, priority, and dependency management.
"""

from typing import List, Literal, Dict, Optional
import pydantic as pd


class Todo(pd.BaseModel):
    """Todo model for tracking individual tasks in FSM-based orchestrators.

    Represents a single task with status, priority, metadata, and dependencies.

    Attributes:
        id: Unique identifier for the todo item
        description: Human-readable description of the task
        priority: Numeric priority (higher values = higher priority)
        status: Current status of the task (pending/in_progress/done/failed)
        metadata: Optional dictionary for additional task information
        dependencies: List of todo IDs this task depends on

    Status Flow:
        pending → in_progress → done
        pending → in_progress → failed
    """

    id: str
    description: str
    priority: int
    status: Literal["pending", "in_progress", "done", "failed"] = "pending"
    metadata: Dict[str, str] = pd.Field(default_factory=dict)
    dependencies: List[str] = pd.Field(default_factory=list)

    model_config = pd.ConfigDict(extra="ignore")

    def __repr__(self) -> str:
        """Return a detailed string representation for debugging.

        Returns:
            String with id, description, status, and priority for quick inspection.
        """
        return (
            f"Todo(id={self.id!r}, description={self.description!r}, "
            f"status={self.status!r}, priority={self.priority})"
        )
