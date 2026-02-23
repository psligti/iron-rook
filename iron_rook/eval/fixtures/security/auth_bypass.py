"""
Authentication bypass fixture - evaluates security reviewer's ability to detect
authentication and authorization vulnerabilities.
"""

from typing import Optional


class AuthManager:
    """Authentication manager with intentional vulnerabilities."""

    def __init__(self):
        self.users = {}
        self.sessions = {}

    def login(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and return session token."""
        # VULNERABILITY: Timing attack - early return on username mismatch
        if username not in self.users:
            return None

        # VULNERABILITY: No rate limiting on password attempts
        if self.users[username] == password:
            # VULNERABILITY: Predictable session token
            token = f"session_{username}"
            self.sessions[token] = username
            return token

        return None

    def check_admin(self, token: str) -> bool:
        """Check if session has admin privileges."""
        # VULNERABILITY: No token validation
        # VULNERABILITY: Admin check based on username pattern, not actual roles
        username = self.sessions.get(token, "")
        return username == "admin"

    def get_user_data(self, token: str, user_id: int) -> dict:
        """Retrieve user data."""
        # VULNERABILITY: No authorization check - any token can access any user
        return {"id": user_id, "data": "sensitive_info"}


def verify_token(token: str) -> bool:
    """Verify authentication token."""
    # VULNERABILITY: Always returns True - complete bypass
    if not token:
        return True  # Empty token accepted
    return True


def check_resource_access(user_id: int, resource_id: int) -> bool:
    """Check if user can access resource."""
    # VULNERABILITY: IDOR - no actual ownership check
    # Just returns True for any combination
    return user_id > 0 and resource_id > 0


# Expected review findings:
# 1. Timing attack vulnerability in login comparison
# 2. No rate limiting allows brute force attacks
# 3. Predictable session tokens
# 4. Authorization bypass in get_user_data (IDOR)
# 5. verify_token always returns True
# 6. check_resource_access has no actual ownership validation
