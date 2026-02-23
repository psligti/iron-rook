"""
Brittle tests fixture - evaluates unit test reviewer's ability to detect
tests that are fragile, overspecified, or implementation-dependent.
"""

import pytest
from unittest.mock import Mock, patch
from typing import List


class DataProcessor:
    """Simple processor for testing."""

    def __init__(self, cache=None):
        self.cache = cache
        self.call_count = 0

    def process(self, items: List[dict]) -> dict:
        self.call_count += 1
        result = []
        for item in items:
            if self.cache and item.get("id") in self.cache:
                result.append(self.cache[item["id"]])
            else:
                processed = {"id": item["id"], "processed": True}
                result.append(processed)
        return {"items": result}

    def get_stats(self) -> dict:
        return {"calls": self.call_count}


# BRITTLE TESTS
class TestDataProcessor:
    """Tests with various brittleness issues."""

    # BRITTLE: Tests implementation details (call_count)
    def test_internal_counter_incremented(self):
        processor = DataProcessor()
        processor.process([{"id": 1}])
        assert processor.call_count == 1  # Tests internal state!

    # BRITTLE: Overspecified - checks too many things
    def test_process_returns_exact_structure(self):
        processor = DataProcessor()
        result = processor.process([{"id": 1}, {"id": 2}])
        assert result == {"items": [{"id": 1, "processed": True}, {"id": 2, "processed": True}]}
        # If we add any field, this test breaks!

    # BRITTLE: Tests private implementation details
    def test_cache_is_checked(self):
        mock_cache = {1: {"id": 1, "cached": True}}
        processor = DataProcessor(cache=mock_cache)
        result = processor.process([{"id": 1}])
        # Asserts about caching behavior - implementation detail
        assert result["items"][0] == {"id": 1, "cached": True}

    # BRITTLE: Hardcoded timing - will fail on slow machines
    def test_process_is_fast(self):
        processor = DataProcessor()
        import time

        start = time.time()
        processor.process([{"id": i} for i in range(100)])
        elapsed = time.time() - start
        assert elapsed < 0.001  # Arbitrary threshold!

    # BRITTLE: Depends on string representation
    def test_stats_format(self):
        processor = DataProcessor()
        processor.process([{"id": 1}])
        stats = str(processor.get_stats())  # Tests __str__ format!
        assert "calls" in stats
        assert stats == "{'calls': 1}"  # Exact string match!

    # BRITTLE: Tests external library behavior
    @patch("json.dumps")
    def test_json_called_correctly(self, mock_dumps):
        import json

        processor = DataProcessor()
        result = processor.process([{"id": 1}])
        # Why test that json.dumps is called? We don't even use it!
        # This is testing our mock setup, not real behavior

    # BRITTLE: Tests order of dictionary items (unstable in older Python)
    def test_result_item_order(self):
        processor = DataProcessor()
        result = processor.process([{"id": 2}, {"id": 1}])
        # Assumes order is preserved
        assert result["items"][0]["id"] == 2
        assert result["items"][1]["id"] == 1

    # BRITTLE: Tests exact error message
    def test_invalid_input_error_message(self):
        processor = DataProcessor()
        with pytest.raises(TypeError) as exc_info:
            processor.process("not a list")  # type: ignore
        assert str(exc_info.value) == "expected list, got str"  # Exact message!

    # BRITTLE: Uses sleep - timing dependent
    def test_cache_expiry(self):
        processor = DataProcessor(cache={1: {"expired": True}})
        import time

        time.sleep(0.1)  # Waits for "expiry"
        result = processor.process([{"id": 1}])
        # Assumes cache expired in 0.1s - brittle!

    # BRITTLE: Tests multiple unrelated things
    def test_everything(self):
        processor = DataProcessor()
        # Create
        result1 = processor.process([{"id": 1}])
        assert result1 is not None
        # Stats
        stats = processor.get_stats()
        assert stats["calls"] == 1
        # Process again
        result2 = processor.process([{"id": 2}])
        assert len(result2["items"]) == 1
        # Internal counter
        assert processor.call_count == 2
        # Tests 5 different things - should be 5 tests!


# Expected review findings:
# 1. test_internal_counter_incremented - tests implementation details
# 2. test_process_returns_exact_structure - overspecified, breaks on additions
# 3. test_cache_is_checked - tests caching strategy (implementation detail)
# 4. test_process_is_fast - timing-dependent, will flake
# 5. test_stats_format - tests string representation, not behavior
# 6. test_json_called_correctly - tests mock behavior, not real code
# 7. test_result_item_order - assumes dict/list ordering
# 8. test_invalid_input_error_message - exact error message matching
# 9. test_cache_expiry - uses sleep, timing-dependent
# 10. test_everything - god test, tests multiple unrelated things
# 11. All tests are fragile to refactoring
# 12. No tests for actual business value/behavior
