"""
Edge case: Subtle issues that are hard to detect.

STRESS TEST: Tests agent's ability to find non-obvious issues.
EXPECTED BEHAVIOR:
- Should detect at least some subtle issues
- Tests depth of analysis capability
"""

import threading
from typing import Optional
from functools import lru_cache


class Singleton:
    """Subtle bug: Not thread-safe singleton."""

    _instance: Optional["Singleton"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


class ThreadSafeButBuggy:
    """Subtle bug: Double-checked locking without volatile."""

    _instance: Optional["ThreadSafeButBuggy"] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:  # Subtle: not atomic with lock
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance


@lru_cache(maxsize=128)
def expensive_computation(n: int) -> int:
    """Subtle bug: lru_cache on function with side effects."""
    print(f"Computing for {n}")  # Side effect
    return n * 2


class ResourceLeak:
    """Subtle bug: Resource leak in exception path."""

    def process_file(self, path: str) -> str:
        f = open(path)
        data = f.read()
        if "error" in data:
            raise ValueError("Found error")  # BUG: file not closed
        f.close()
        return data


class MutableDefault:
    """Classic subtle bug: mutable default argument."""

    def add_item(self, item: str, items: list = []) -> list:  # BUG
        items.append(item)
        return items


class ClosureCapture:
    """Subtle bug: late binding closure."""

    def create_multipliers(self):
        return [lambda x: x * i for i in range(5)]  # BUG: all use i=4


class IntegerCaching:
    """Subtle bug: relying on integer caching."""

    def compare_ids(self):
        a = 256
        b = 256
        assert a is b  # Works (cached)

        c = 257
        d = 257
        assert c is d  # May fail (not cached) - BUG: using `is` for ints


class DictMutation:
    """Subtle bug: mutating dict during iteration."""

    def filter_dict(self, d: dict) -> dict:
        for key in d:  # RuntimeError in Python 3
            if d[key] < 0:
                del d[key]
        return d


class ExceptionShadowing:
    """Subtle bug: exception variable shadowing."""

    def handle(self):
        try:
            raise ValueError("first")
        except ValueError as e:
            try:
                raise TypeError("second")
            except TypeError as e:  # Shadows outer e
                pass
            # e here might be unexpectedly bound to TypeError in Python 2
            # Fixed in Python 3, but still confusing


class FinallyReturn:
    """Subtle bug: return in finally swallows exceptions."""

    def get_value(self) -> int:
        try:
            raise ValueError("error")
            return 1
        finally:
            return 2  # BUG: swallows the exception


class ClassAttributeShared:
    """Subtle bug: mutable class attribute shared by instances."""

    items: list = []  # Shared by all instances!

    def add(self, item):
        self.items.append(item)


class HashContradiction:
    """Subtle bug: equals without hash consistency."""

    def __init__(self, value: int):
        self.value = value

    def __eq__(self, other):
        return abs(self.value) == abs(other.value)

    def __hash__(self):
        return hash(self.value)  # BUG: inconsistent with __eq__


# Expected review findings:
# 1. ThreadSafeButBuggy - double-checked locking issue
# 2. expensive_computation - lru_cache with side effects
# 3. ResourceLeak.process_file - file not closed on exception
# 4. MutableDefault.add_item - mutable default argument
# 5. ClosureCapture.create_multipliers - late binding closure
# 6. IntegerCaching.compare_ids - using `is` for value comparison
# 7. DictMutation.filter_dict - mutating during iteration
# 8. FinallyReturn.get_value - return in finally
# 9. ClassAttributeShared.items - shared mutable class attribute
# 10. HashContradiction - __eq__ and __hash__ inconsistency
