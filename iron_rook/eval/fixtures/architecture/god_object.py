"""
God object fixture - evaluates architecture reviewer's ability to detect
classes with too many responsibilities (God Object anti-pattern).
"""

import json
import logging
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
import hashlib
import re


@dataclass
class Config:
    """Configuration settings."""

    db_path: str = "app.db"
    smtp_host: str = "localhost"
    api_key: str = ""


class AppManager:
    """
    A class that does EVERYTHING.

    GOD OBJECT ANTI-PATTERN: This class has 20+ responsibilities:
    - User management
    - Authentication
    - Database operations
    - Email sending
    - Logging
    - Caching
    - Configuration
    - API handling
    - File operations
    - Validation
    - Serialization
    - Scheduled tasks
    - Metrics
    - Session management
    - Security
    - Reporting
    - Notifications
    - Search
    - Import/Export
    - Webhooks
    """

    _instance: Optional["AppManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # State for everything
        self.users: Dict[int, dict] = {}
        self.sessions: Dict[str, int] = {}
        self.cache: Dict[str, Any] = {}
        self.config = Config()
        self.logs: List[str] = []
        self.metrics: Dict[str, float] = {}
        self.scheduled_tasks: List[dict] = []
        self.webhooks: List[str] = []

        # Initialize everything
        self._setup_database()
        self._setup_logging()
        self._setup_cache()

    # === USER MANAGEMENT (should be separate class) ===
    def create_user(self, name: str, email: str, password: str) -> int:
        user_id = len(self.users) + 1
        hashed = self._hash_password(password)
        self.users[user_id] = {
            "id": user_id,
            "name": name,
            "email": email,
            "password_hash": hashed,
            "created_at": datetime.now(),
        }
        self._log(f"Created user {user_id}")
        self._update_metric("users_created", 1)
        return user_id

    def get_user(self, user_id: int) -> Optional[dict]:
        return self.users.get(user_id)

    def update_user(self, user_id: int, **kwargs) -> bool:
        if user_id not in self.users:
            return False
        self.users[user_id].update(kwargs)
        self._invalidate_cache(f"user:{user_id}")
        return True

    def delete_user(self, user_id: int) -> bool:
        if user_id in self.users:
            del self.users[user_id]
            self._log(f"Deleted user {user_id}")
            return True
        return False

    def find_users(self, query: str) -> List[dict]:
        return [
            u
            for u in self.users.values()
            if query.lower() in u["name"].lower() or query.lower() in u["email"].lower()
        ]

    # === AUTHENTICATION (should be separate class) ===
    def login(self, email: str, password: str) -> Optional[str]:
        for user in self.users.values():
            if user["email"] == email:
                if user["password_hash"] == self._hash_password(password):
                    session_token = self._generate_token()
                    self.sessions[session_token] = user["id"]
                    self._log(f"User {user['id']} logged in")
                    return session_token
        return None

    def logout(self, token: str) -> bool:
        if token in self.sessions:
            user_id = self.sessions.pop(token)
            self._log(f"User {user_id} logged out")
            return True
        return False

    def validate_token(self, token: str) -> Optional[int]:
        return self.sessions.get(token)

    # === DATABASE (should be separate class) ===
    def _setup_database(self):
        self._db_connected = True

    def execute_query(self, query: str, params: tuple = ()) -> Any:
        self._log(f"Executing: {query}")
        # Simulated database
        return []

    # === EMAIL (should be separate class) ===
    def send_email(self, to: str, subject: str, body: str) -> bool:
        try:
            smtp = smtplib.SMTP(self.config.smtp_host)
            smtp.sendmail("noreply@app.com", to, f"Subject: {subject}\n\n{body}")
            self._log(f"Email sent to {to}")
            return True
        except Exception as e:
            self._log(f"Email failed: {e}")
            return False

    def send_welcome_email(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if user:
            return self.send_email(
                user["email"], "Welcome!", f"Hello {user['name']}, welcome to our app!"
            )
        return False

    # === LOGGING (should use standard logging) ===
    def _setup_logging(self):
        self._log("Application started")

    def _log(self, message: str):
        entry = f"[{datetime.now()}] {message}"
        self.logs.append(entry)

    def get_logs(self, limit: int = 100) -> List[str]:
        return self.logs[-limit:]

    # === CACHING (should be separate class) ===
    def _setup_cache(self):
        self.cache = {}

    def _cache_get(self, key: str) -> Optional[Any]:
        return self.cache.get(key)

    def _cache_set(self, key: str, value: Any, ttl: int = 3600):
        self.cache[key] = value

    def _invalidate_cache(self, pattern: str):
        keys_to_remove = [k for k in self.cache if pattern in k]
        for k in keys_to_remove:
            del self.cache[k]

    # === VALIDATION (should be separate class) ===
    def validate_email(self, email: str) -> bool:
        return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", email))

    def validate_password(self, password: str) -> bool:
        return len(password) >= 8 and any(c.isdigit() for c in password)

    # === SERIALIZATION (should use separate serializers) ===
    def to_json(self, user_id: int) -> str:
        user = self.get_user(user_id)
        if user:
            return json.dumps({k: str(v) for k, v in user.items()})
        return "{}"

    def from_json(self, data: str) -> dict:
        return json.loads(data)

    # === METRICS (should be separate class) ===
    def _update_metric(self, name: str, delta: float):
        self.metrics[name] = self.metrics.get(name, 0) + delta

    def get_metrics(self) -> Dict[str, float]:
        return self.metrics.copy()

    # === FILE OPERATIONS (should be separate class) ===
    def export_users(self, filepath: str) -> bool:
        try:
            with open(filepath, "w") as f:
                json.dump(list(self.users.values()), f, default=str)
            return True
        except Exception:
            return False

    def import_users(self, filepath: str) -> int:
        with open(filepath) as f:
            users = json.load(f)
        count = 0
        for u in users:
            self.create_user(u["name"], u["email"], "temp123")
            count += 1
        return count

    # === SCHEDULING (should be separate class) ===
    def schedule_task(self, name: str, interval: int, callback) -> None:
        self.scheduled_tasks.append(
            {
                "name": name,
                "interval": interval,
                "callback": callback,
            }
        )

    def run_scheduled_tasks(self) -> None:
        for task in self.scheduled_tasks:
            task["callback"]()

    # === WEBHOOKS (should be separate class) ===
    def register_webhook(self, url: str) -> None:
        self.webhooks.append(url)

    def trigger_webhooks(self, event: str, data: dict) -> None:
        import requests

        for url in self.webhooks:
            requests.post(url, json={"event": event, "data": data})

    # === SEARCH (should be separate class) ===
    def search_all(self, query: str) -> dict:
        return {
            "users": self.find_users(query),
            "logs": [l for l in self.logs if query.lower() in l.lower()],
        }

    # === HELPERS ===
    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def _generate_token(self) -> str:
        import uuid

        return str(uuid.uuid4())


# Expected review findings:
# 1. Single class with 20+ distinct responsibilities
# 2. Violates Single Responsibility Principle
# 3. God Object anti-pattern - knows too much, does too much
# 4. Singleton pattern compounds the problem
# 5. Difficult to test - need to mock everything
# 6. High coupling - changing any feature affects the whole class
# 7. Recommendation: Split into UserService, AuthService, EmailService,
#    CacheManager, MetricsCollector, etc.
