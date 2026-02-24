"""
Edge case: Conflicting requirements and ambiguous code.

STRESS TEST: Tests agent decision making on ambiguous cases.
EXPECTED BEHAVIOR:
- Should handle tradeoffs appropriately
- Should make reasonable decisions on ambiguous code
- Should NOT crash on conflicting signals
"""

from typing import Optional, List
from dataclasses import dataclass


@dataclass
class Config:
    debug: bool = True  # Is this a bug? Depends on environment
    timeout: int = 30  # Is 30 seconds good? Depends on use case
    retries: int = 3  # Is 3 retries good? Depends on use case


def flexible_validation(data: dict, strict: bool = False) -> bool:
    """
    Conflicting signals:
    - If strict=True, may reject valid data (false positive)
    - If strict=False, may accept invalid data (false negative)
    What should the agent recommend?
    """
    if strict:
        return all(k in data for k in ["name", "email", "phone", "address"])
    else:
        return len(data) > 0


# Is this caching good or bad?
# Good: Performance improvement
# Bad: Memory usage, stale data
_cache: dict = {}


def get_with_cache(key: str) -> Optional[str]:
    if key in _cache:
        return _cache[key]
    value = expensive_fetch(key)
    _cache[key] = value
    return value


def expensive_fetch(key: str) -> Optional[str]:
    return f"value_{key}"


# Is this abstraction good or bad?
# Good: DRY principle
# Bad: Over-engineering for simple cases
class AbstractFactoryBuilderSingleton:
    _instance: Optional["AbstractFactoryBuilderSingleton"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def create_factory(self, factory_type: str):
        if factory_type == "A":
            return FactoryA()
        elif factory_type == "B":
            return FactoryB()
        raise ValueError(f"Unknown factory type: {factory_type}")


class FactoryA:
    def create(self) -> str:
        return "A"


class FactoryB:
    def create(self) -> str:
        return "B"


# Is this good error handling or over-cautious?
def safe_divide(a: float, b: float) -> Optional[float]:
    try:
        if b == 0:
            return None  # Silent failure? Or raise?
        return a / b
    except TypeError:
        return None  # Catch too broad?
    except Exception:
        return None  # Definitely too broad


# Is this good logging or noise?
def process_item(item: dict) -> dict:
    print(f"Processing item: {item}")  # Debug logging
    print(f"Item keys: {list(item.keys())}")  # More debug logging
    print(f"Item values: {list(item.values())}")  # Even more debug logging
    result = {"processed": True, **item}
    print(f"Result: {result}")  # Final debug logging
    return result


# Is this security or usability concern?
def login(username: str, password: str) -> bool:
    if len(password) < 12:
        return False  # Too strict?
    if not any(c.isupper() for c in password):
        return False  # Too strict?
    if not any(c.islower() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    if not any(c in "!@#$%^&*" for c in password):
        return False  # Too strict?
    return authenticate(username, password)


def authenticate(username: str, password: str) -> bool:
    return True  # Placeholder


# Is this good design or code smell?
class GodObject:
    """Does everything - good for small projects, bad for large."""

    def __init__(self):
        self.data = {}
        self.cache = {}
        self.config = {}
        self.logs = []

    def create(self, item):
        pass

    def read(self, id):
        pass

    def update(self, id, data):
        pass

    def delete(self, id):
        pass

    def validate(self, data):
        pass

    def transform(self, data):
        pass

    def log(self, message):
        pass

    def cache_get(self, key):
        pass

    def cache_set(self, key, value):
        pass

    def send_email(self, to, subject, body):
        pass

    def process_payment(self, amount):
        pass


# Expected review findings:
# These are AMBIGUOUS cases - agent should:
# 1. Acknowledge tradeoffs
# 2. Make reasonable recommendations
# 3. Not over-flag opinionated choices
# 4. Focus on actual bugs over style preferences
