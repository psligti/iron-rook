"""
Type hints fixture - evaluates linting reviewer's ability to detect
missing or incorrect type annotations.
"""

from typing import Any, Dict, List, Optional


class DataStore:
    """A data store with various type hint issues."""

    def __init__(self, config):  # MISSING: config: dict
        self.config = config  # MISSING: self.config: dict
        self._data = {}  # MISSING: self._data: Dict[str, Any]

    def get(self, key):  # MISSING: key: str, return -> Optional[Any]
        return self._data.get(key)

    def set(self, key, value):  # MISSING: key: str, value: Any, return -> None
        self._data[key] = value

    def delete(self, key):  # MISSING: key: str, return -> bool
        if key in self._data:
            del self._data[key]
            return True
        return False

    def get_all(self):  # MISSING: return -> Dict[str, Any]
        return self._data.copy()


def process_items(items):  # MISSING: items: List[dict], return -> List[dict]
    """Process a list of items."""
    results = []  # MISSING: results: List[dict]
    for item in items:  # MISSING: item: dict
        processed = {  # MISSING: processed: dict
            "id": item.get("id"),
            "value": item.get("value"),
        }
        results.append(processed)
    return results


def find_user(users, user_id):  # MISSING: types for all params and return
    for user in users:
        if user.get("id") == user_id:
            return user
    return None


class TypedProcessor:
    """Processor with incorrect type hints."""

    def __init__(self) -> None:
        self.count = 0  # MISSING: self.count: int

    def process(self, data: str) -> str:  # WRONG: data should be List[dict]
        """Process data."""
        # This will fail at runtime - data is expected to be a list
        return data[0]  # WRONG: returning dict, not str

    def count_items(self, items: List) -> int:  # INCOMPLETE: List[what?]
        return len(items)

    def get_config(self) -> Dict:  # INCOMPLETE: Dict[what, what?]
        return {"timeout": 30, "retries": 3}

    def merge(self, *dicts: Dict[str, Any]) -> Any:  # INCONSISTENT: return should be dict
        result = {}
        for d in dicts:
            result.update(d)
        return result


# Function with partially correct hints
def validate_email(
    email: str,  # CORRECT
    domains,  # MISSING: domains: List[str]
    allow_plus=True,  # MISSING: allow_plus: bool = True
):  # MISSING: -> bool
    """Check if email is valid and domain is allowed."""
    if "@" not in email:
        return False

    _, domain = email.split("@", 1)
    return domain in domains


# Using Any when specific type would be better
def transform(data: Any) -> Any:  # OVERLY GENERIC
    """Transform data - too generic!"""
    if isinstance(data, dict):
        return {k.upper(): v for k, v in data.items()}
    elif isinstance(data, list):
        return [x * 2 for x in data]
    return data


# Missing Optional for None returns
def get_first(items: List[str]) -> str:  # WRONG: should be Optional[str]
    if not items:
        return None  # Type checker will complain!
    return items[0]


# Missing Union for multiple return types
def parse_value(s: str):  # MISSING: -> Union[int, float, str]
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s


# Expected review findings:
# 1. DataStore.__init__ - missing config: dict
# 2. DataStore.get - missing key: str, return -> Optional[Any]
# 3. DataStore.set - missing key: str, value: Any
# 4. DataStore.delete - missing return -> bool
# 5. process_items - missing all type hints
# 6. find_user - missing all type hints
# 7. TypedProcessor.process - wrong types (List[dict] vs str)
# 8. count_items - incomplete List[?]
# 9. get_config - incomplete Dict[?, ?]
# 10. validate_email - missing domains and return types
# 11. transform - overly generic Any types
# 12. get_first - missing Optional for None return
# 13. parse_value - missing Union for multiple return types
