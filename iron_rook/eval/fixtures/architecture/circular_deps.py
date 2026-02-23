"""
Circular dependencies fixture - evaluates architecture reviewer's ability to detect
circular import and dependency cycles.
"""

# Module A: user_manager.py
# This simulates a file that imports from permissions which imports back

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .circular_deps import PermissionManager


class UserManager:
    """Manages user accounts with circular dependency."""

    def __init__(self):
        self.permissions: "PermissionManager" = None  # type: ignore

    def create_user(self, name: str, email: str) -> dict:
        # CIRCULAR: UserManager depends on PermissionManager
        from .circular_deps import PermissionManager

        self.permissions = PermissionManager()

        default_role = self.permissions.get_default_role()
        return {"name": name, "email": email, "role": default_role}

    def can_perform_action(self, user_id: int, action: str) -> bool:
        # CIRCULAR: Calls back to permission manager
        return self.permissions.check_permission(user_id, action)


# Module B: permission_manager.py (in same file for fixture purposes)
class PermissionManager:
    """Manages permissions with circular dependency back to users."""

    def __init__(self):
        self.users: UserManager = None  # type: ignore

    def get_default_role(self) -> str:
        return "user"

    def check_permission(self, user_id: int, action: str) -> bool:
        # CIRCULAR: PermissionManager depends on UserManager
        user = self.users.get_user(user_id)
        return action in user.get("permissions", [])

    def grant_permission(self, user_id: int, permission: str) -> None:
        # CIRCULAR: Calls back to user manager
        user = self.users.get_user(user_id)
        user["permissions"] = user.get("permissions", []) + [permission]
        self.users.update_user(user_id, user)


# Module C: audit_logger.py (third party in cycle)
class AuditLogger:
    """Audit logging with circular dependency."""

    def __init__(self):
        self.users: UserManager = None  # type: ignore
        self.permissions: PermissionManager = None  # type: ignore

    def log_action(self, user_id: int, action: str) -> None:
        # CIRCULAR: Depends on both UserManager and PermissionManager
        user = self.users.get_user(user_id)
        can_act = self.permissions.check_permission(user_id, action)

        print(f"User {user['name']} {'can' if can_act else 'cannot'} {action}")


# The cycle: UserManager -> PermissionManager -> UserManager
# And: AuditLogger -> UserManager, AuditLogger -> PermissionManager

# Expected review findings:
# 1. Circular import between UserManager and PermissionManager
# 2. Runtime imports inside methods to avoid import-time failures
# 3. TYPE_CHECKING guard suggests awareness of circular issue
# 4. Tight coupling makes modules difficult to test independently
# 5. Recommendation: Introduce shared interface/protocol or mediator
