"""
Missing implementation fixture - evaluates requirements reviewer's ability to detect
code that doesn't implement stated requirements.
"""

from dataclasses import dataclass
from typing import List, Optional


# REQUIREMENTS DOCUMENT (simulated)
REQUIREMENTS = """
User Management Requirements:
1. Users must have unique email addresses
2. Passwords must be at least 12 characters with complexity requirements
3. Account lockout after 5 failed login attempts
4. Password reset via email with expiring token (15 min)
5. Two-factor authentication support (TOTP)
6. Session timeout after 30 minutes of inactivity
7. Audit logging of all authentication events
8. Role-based access control with custom roles
"""


@dataclass
class User:
    id: int
    email: str
    password_hash: str
    role: str = "user"


class UserManager:
    """User management implementation - incomplete."""

    def __init__(self):
        self.users: dict[int, User] = {}
        self._next_id = 1

    def create_user(self, email: str, password: str, role: str = "user") -> User:
        """
        Create a new user.

        REQUIREMENT VIOLATIONS:
        - REQ 1: No email uniqueness check
        - REQ 2: No password complexity validation
        """
        # MISSING: Check if email already exists
        # MISSING: Validate password length >= 12
        # MISSING: Validate password complexity (uppercase, lowercase, numbers, symbols)

        user = User(
            id=self._next_id,
            email=email,
            password_hash=self._hash(password),
            role=role,
        )
        self.users[self._next_id] = user
        self._next_id += 1
        return user

    def login(self, email: str, password: str) -> Optional[str]:
        """
        Authenticate user and return session token.

        REQUIREMENT VIOLATIONS:
        - REQ 3: No failed attempt tracking / lockout
        - REQ 6: No session timeout implementation
        - REQ 7: No audit logging
        """
        # MISSING: Track failed attempts per email
        # MISSING: Check if account is locked
        # MISSING: Log login attempt (success or failure)

        for user in self.users.values():
            if user.email == email:
                if user.password_hash == self._hash(password):
                    # MISSING: Reset failed attempts on success
                    # MISSING: Log successful login
                    return self._create_session(user.id)
                else:
                    # MISSING: Increment failed attempts
                    # MISSING: Lock if >= 5 attempts
                    # MISSING: Log failed login
                    pass
        return None

    def request_password_reset(self, email: str) -> Optional[str]:
        """
        Request password reset token.

        REQUIREMENT VIOLATIONS:
        - REQ 4: Token has no expiration
        - REQ 7: No audit logging
        """
        for user in self.users.values():
            if user.email == email:
                # MISSING: Generate expiring token (15 min TTL)
                # MISSING: Send reset email
                # MISSING: Log reset request
                return "reset_token_123"  # Static, never expires
        return None

    def reset_password(self, token: str, new_password: str) -> bool:
        """
        Reset password using token.

        REQUIREMENT VIOLATIONS:
        - REQ 2: No password complexity validation
        - REQ 4: No token expiration check
        """
        # MISSING: Validate token expiration
        # MISSING: Validate new password complexity
        # MISSING: Invalidate token after use
        # MISSING: Log password reset
        return True  # Always succeeds

    def enable_2fa(self, user_id: int) -> Optional[str]:
        """
        Enable two-factor authentication.

        REQUIREMENT VIOLATIONS:
        - REQ 5: Not implemented
        """
        # MISSING: Generate TOTP secret
        # MISSING: Store secret for user
        # MISSING: Return QR code URL
        raise NotImplementedError("2FA not implemented")

    def verify_2fa(self, user_id: int, code: str) -> bool:
        """Verify 2FA code."""
        # MISSING: Verify TOTP code
        raise NotImplementedError("2FA not implemented")

    def check_permission(self, user_id: int, permission: str) -> bool:
        """
        Check if user has permission.

        REQUIREMENT VIOLATIONS:
        - REQ 8: No role-based access control implementation
        """
        # MISSING: Load user roles and permissions
        # MISSING: Check if permission is granted
        return True  # Everyone has every permission

    def create_role(self, name: str, permissions: List[str]) -> None:
        """Create custom role."""
        # MISSING: Role storage
        # MISSING: Permission assignment
        raise NotImplementedError("Custom roles not implemented")

    def _hash(self, password: str) -> str:
        # MISSING: Use proper hashing (bcrypt, argon2)
        return f"hash_{password}"  # Insecure!

    def _create_session(self, user_id: int) -> str:
        # MISSING: Session expiration (30 min)
        # MISSING: Session storage
        return f"session_{user_id}"


# Expected review findings:
# 1. REQ 1 - Email uniqueness not enforced
# 2. REQ 2 - Password complexity not validated (length, character types)
# 3. REQ 3 - No failed login attempt tracking or lockout
# 4. REQ 4 - Password reset tokens don't expire
# 5. REQ 5 - 2FA/TOTP not implemented (NotImplementedError)
# 6. REQ 6 - No session timeout implementation
# 7. REQ 7 - No audit logging of auth events
# 8. REQ 8 - RBAC not implemented (everyone has all permissions)
# 9. Insecure password hashing (not using bcrypt/argon2)
# 10. Custom roles not implemented
