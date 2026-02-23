"""
Missing tests fixture - evaluates unit test reviewer's ability to detect
untested code paths and missing test coverage.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class User:
    id: int
    name: str
    email: str
    role: str = "user"


class UserService:
    """User management with several untested scenarios."""

    def __init__(self):
        self.users: dict[int, User] = {}
        self._next_id = 1

    def create_user(self, name: str, email: str, role: str = "user") -> User:
        # TESTED: Basic creation works
        # UNTESTED: What if name is empty?
        # UNTESTED: What if email is invalid format?
        # UNTESTED: What if role is not in valid roles?
        user = User(id=self._next_id, name=name, email=email, role=role)
        self.users[self._next_id] = user
        self._next_id += 1
        return user

    def get_user(self, user_id: int) -> Optional[User]:
        # TESTED: Returns user when exists
        # UNTESTED: Returns None when doesn't exist
        return self.users.get(user_id)

    def update_user(self, user_id: int, **kwargs) -> bool:
        # UNTESTED: Entire method has no tests
        if user_id not in self.users:
            return False
        user = self.users[user_id]
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        return True

    def delete_user(self, user_id: int) -> bool:
        # TESTED: Returns True when deleted
        # UNTESTED: Returns False when user doesn't exist
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False

    def find_by_email(self, email: str) -> Optional[User]:
        # UNTESTED: Entire method has no tests
        for user in self.users.values():
            if user.email == email:
                return user
        return None

    def find_by_role(self, role: str) -> List[User]:
        # UNTESTED: Entire method has no tests
        return [u for u in self.users.values() if u.role == role]

    def promote_to_admin(self, user_id: int) -> bool:
        # UNTESTED: Entire method has no tests
        # UNTESTED: What if already admin?
        # UNTESTED: What if user doesn't exist?
        user = self.users.get(user_id)
        if user:
            user.role = "admin"
            return True
        return False


# EXISTING TESTS (in separate test file)
"""
import pytest
from user_service import UserService

class TestUserService:
    def test_create_user(self):
        service = UserService()
        user = service.create_user("Alice", "alice@example.com")
        assert user.name == "Alice"
        assert user.email == "alice@example.com"
    
    def test_get_user_exists(self):
        service = UserService()
        created = service.create_user("Bob", "bob@example.com")
        found = service.get_user(created.id)
        assert found == created
    
    def test_delete_user(self):
        service = UserService()
        user = service.create_user("Charlie", "charlie@example.com")
        result = service.delete_user(user.id)
        assert result is True
"""


# Expected review findings:
# 1. create_user - no validation tests for empty name
# 2. create_user - no validation tests for invalid email format
# 3. create_user - no validation tests for invalid role
# 4. get_user - missing test for non-existent user
# 5. update_user - ENTIRE method untested
# 6. delete_user - missing test for non-existent user
# 7. find_by_email - ENTIRE method untested
# 8. find_by_role - ENTIRE method untested
# 9. promote_to_admin - ENTIRE method untested
# 10. No edge case tests (empty database, concurrent access)
# 11. No error handling tests
# 12. Estimated coverage: ~30%
