"""
Boundary violation fixture - evaluates architecture reviewer's ability to detect
layer boundary violations and improper coupling.
"""

from dataclasses import dataclass
from typing import List


# Layer 1: Domain Model (should be pure)
@dataclass
class User:
    id: int
    name: str
    email: str


# Layer 2: Repository (data access)
class UserRepository:
    def __init__(self, db_connection):
        self.db = db_connection

    def find_by_id(self, user_id: int) -> User:
        # ARCHITECTURE VIOLATION: Repository directly handles HTTP concerns
        import requests

        response = requests.get(f"https://api.internal/users/{user_id}")
        return User(**response.json())

    def save(self, user: User) -> None:
        # ARCHITECTURE VIOLATION: Business logic in repository
        if not user.email or "@" not in user.email:
            raise ValueError("Invalid email")
        self.db.execute(
            "UPDATE users SET name=?, email=? WHERE id=?", (user.name, user.email, user.id)
        )


# Layer 3: Service (business logic)
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def get_user(self, user_id: int) -> dict:
        user = self.repo.find_by_id(user_id)
        # ARCHITECTURE VIOLATION: Service directly formats HTTP response
        return {
            "status": "success",
            "data": {"id": user.id, "name": user.name, "email": user.email},
            "meta": {"source": "database"},
        }

    def validate_and_update(self, user_id: int, name: str) -> None:
        # ARCHITECTURE VIOLATION: Service sends emails directly
        import smtplib

        user = self.repo.find_by_id(user_id)
        user.name = name
        self.repo.save(user)

        # Direct email sending from service layer
        smtp = smtplib.SMTP("localhost")
        smtp.sendmail("noreply@example.com", user.email, f"Name updated to {name}")


# Layer 4: Controller (HTTP handling)
class UserController:
    def __init__(self, service: UserService):
        self.service = service

    def get(self, user_id: int):
        # ARCHITECTURE VIOLATION: Controller directly accesses database
        from some_db import get_connection

        db = get_connection()
        result = db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return result.fetchone()


# Expected review findings:
# 1. UserRepository makes HTTP calls (violates repository pattern)
# 2. UserRepository contains business validation logic
# 3. UserService formats HTTP responses (should return domain objects)
# 4. UserService sends emails directly (should use notification service)
# 5. UserController bypasses service layer and accesses database directly
