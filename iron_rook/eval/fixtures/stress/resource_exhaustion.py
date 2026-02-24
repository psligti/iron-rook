"""
Edge case: Timeout and resource exhaustion.

STRESS TEST: Tests timeout handling, infinite loop detection.
EXPECTED BEHAVIOR:
- Should detect infinite loops
- Should timeout gracefully
- Should NOT hang forever
"""

import time
from typing import Generator, Any


def infinite_loop() -> None:
    """Obvious infinite loop - easy to detect."""
    while True:
        pass


def subtle_infinite_loop(n: int) -> int:
    """Subtle infinite loop - condition never becomes false."""
    while n > 0:
        n = n + 1  # BUG: n increases, never decreases
    return n


def infinite_recursion(n: int) -> int:
    """Infinite recursion - no base case."""
    return infinite_recursion(n + 1)


def infinite_generator() -> Generator[int, None, None]:
    """Infinite generator - caller might not handle."""
    i = 0
    while True:
        yield i
        i += 1


def slow_operation() -> None:
    """Very slow operation - might timeout."""
    time.sleep(3600)  # 1 hour sleep
    print("Done")


def memory_exhaustion() -> list:
    """Memory exhaustion - will crash."""
    data = []
    while True:
        data.append("x" * 1024 * 1024)  # 1MB each
    return data


def cpu_exhaustion(n: int) -> int:
    """CPU exhaustion - O(n^3) complexity."""
    result = 0
    for i in range(n):
        for j in range(n):
            for k in range(n):
                result += 1
    return result


def exponential_backdoor(n: int) -> int:
    """Exponential time - can freeze on large inputs."""
    if n <= 1:
        return 1
    return exponential_backdoor(n - 1) + exponential_backdoor(n - 2)


class BlockingIO:
    """Blocking I/O - can cause deadlocks."""

    def __init__(self):
        self.data = []

    def read_forever(self, file) -> Any:
        while True:
            chunk = file.read(1024)
            if not chunk:
                break
            self.data.append(chunk)
            time.sleep(0.001)
        return self.data


def busy_wait(condition) -> None:
    """Busy wait - wastes CPU."""
    while not condition():
        pass  # Should use wait/event


class Deadlock:
    """Potential deadlock - lock ordering issue."""

    def __init__(self):
        self.lock_a = threading.Lock()
        self.lock_b = threading.Lock()

    def method1(self):
        with self.lock_a:
            with self.lock_b:
                pass

    def method2(self):
        with self.lock_b:  # Different order - potential deadlock
            with self.lock_a:
                pass


import threading


# Expected review findings:
# 1. infinite_loop - obvious infinite loop
# 2. subtle_infinite_loop - logic error causes infinite loop
# 3. infinite_recursion - no base case
# 4. infinite_generator - no termination
# 5. slow_operation - 1 hour timeout
# 6. memory_exhaustion - unbounded memory
# 7. cpu_exhaustion - O(n^3) complexity
# 8. exponential_backdoor - exponential recursion
# 9. busy_wait - CPU waste
# 10. Deadlock - lock ordering issue
