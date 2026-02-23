"""
Missing documentation fixture - evaluates documentation reviewer's ability to detect
missing docstrings, comments, and documentation.
"""

import json
from typing import Any, Dict, List, Optional


class DataProcessor:
    # MISSING: Module-level docstring
    # MISSING: Class docstring

    def __init__(self, config: dict):
        # MISSING: Parameter documentation
        self.config = config
        self._cache = {}

    def process(self, data: List[dict]) -> Dict[str, Any]:
        # MISSING: Docstring explaining what this does
        # MISSING: Parameter and return type descriptions
        # MISSING: Examples
        result = []
        for item in data:
            processed = self._transform(item)
            result.append(processed)
        return {"items": result, "count": len(result)}

    def _transform(self, item: dict) -> dict:
        # MISSING: Even internal methods should have docstrings
        return {k: v for k, v in item.items() if v is not None}

    def validate(self, item: dict) -> bool:
        # MISSING: What validation rules?
        # MISSING: What makes an item valid vs invalid?
        required = self.config.get("required_fields", [])
        return all(k in item for k in required)

    def export(self, items: List[dict], format: str = "json") -> str:
        # MISSING: What formats are supported?
        # MISSING: What happens if format is unsupported?
        if format == "json":
            return json.dumps(items)
        raise ValueError(f"Unsupported format: {format}")


def calculate_statistics(numbers: List[float]) -> dict:
    # MISSING: Module-level function docstring
    # MISSING: What statistics are calculated?
    # MISSING: What's in the returned dict?
    if not numbers:
        return {"mean": 0, "sum": 0, "count": 0}

    total = sum(numbers)
    count = len(numbers)
    mean = total / count

    return {"mean": mean, "sum": total, "count": count}


def merge_configs(*configs: dict) -> dict:
    # MISSING: Docstring
    result = {}
    for config in configs:
        result.update(config)
    return result


class CacheManager:
    """Basic cache - but methods need documentation."""

    def __init__(self, ttl: int = 3600):
        self._data: Dict[str, Any] = {}
        self._ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        # MISSING: What happens if key doesn't exist?
        # MISSING: Is None a valid cached value?
        return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        # MISSING: Does this overwrite existing keys?
        # MISSING: What about TTL handling?
        self._data[key] = value

    def delete(self, key: str) -> bool:
        # MISSING: Return value meaning unclear
        if key in self._data:
            del self._data[key]
            return True
        return False

    def clear(self) -> None:
        # MISSING: Does this clear ALL cache or just expired?
        self._data.clear()


# Expected review findings:
# 1. DataProcessor missing class docstring
# 2. DataProcessor.process missing docstring with params/returns
# 3. DataProcessor.validate missing validation rules documentation
# 4. DataProcessor.export missing supported formats list
# 5. calculate_statistics missing docstring explaining return values
# 6. merge_configs missing docstring
# 7. CacheManager methods missing behavior documentation
# 8. No module-level docstring
# 9. No usage examples
# 10. No parameter descriptions with expected types/values
