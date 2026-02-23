"""
Outdated README fixture - evaluates documentation reviewer's ability to detect
documentation that doesn't match current code.
"""

# README.md content (simulated as string for fixture)
README_CONTENT = """
# DataProcessor Library

A simple library for processing structured data.

## Installation

```bash
pip install data-processor
```

## Quick Start

```python
from data_processor import DataProcessor

# Initialize with config
processor = DataProcessor({"required_fields": ["id", "name"]})

# Process your data
data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
result = processor.process(data)
print(result)
```

## API Reference

### `DataProcessor(config: dict)`

Create a new processor instance.

**Parameters:**
- `config` (dict): Configuration dictionary with:
  - `required_fields` (list): Fields that must be present
  - `timeout` (int): Timeout in seconds (default: 30)

### `process(data: list) -> dict`

Process a list of items.

**Returns:** Dictionary with processed items.

### `validate(item: dict) -> bool`

Check if an item is valid.

### `export(items: list, format: str = "json") -> str`

Export items to specified format.

**Supported formats:** json, xml, csv

## Configuration

The library supports the following configuration options:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| required_fields | list | [] | Fields that must be present |
| timeout | int | 30 | Processing timeout |
| cache_enabled | bool | True | Enable caching |
| max_items | int | 1000 | Maximum items per batch |

## Changelog

### v1.0.0 (2023-01-15)
- Initial release
- Basic processing functionality
- JSON export support

### v1.1.0 (2023-03-20)
- Added XML export format
- Added CSV export format
- Improved validation

## License

MIT License
"""


# ACTUAL CODE (has diverged from docs)
class DataProcessor:
    """
    Current implementation - different from README.
    """

    def __init__(self, config: dict):
        # OUTDATED: README says timeout default is 30, but it's not implemented
        # OUTDATED: README says cache_enabled exists, but it doesn't
        # OUTDATED: README says max_items exists, but it doesn't
        self.config = config
        self._cache = {}

    def process(self, data: list) -> dict:
        # OUTDATED: README doesn't mention return structure
        result = []
        for item in data:
            processed = self._transform(item)
            result.append(processed)
        return {"items": result, "count": len(result)}

    def validate(self, item: dict) -> bool:
        # OUTDATED: README doesn't explain what makes valid/invalid
        required = self.config.get("required_fields", [])
        return all(k in item for k in required)

    def export(self, items: list, format: str = "json") -> str:
        # OUTDATED: README says xml and csv are supported - THEY ARE NOT
        if format == "json":
            return json.dumps(items)
        raise ValueError(f"Unsupported format: {format}")  # xml/csv will fail!

    # NEW METHOD NOT IN README
    def _transform(self, item: dict) -> dict:
        return {k: v for k, v in item.items() if v is not None}


# Expected review findings:
# 1. README claims XML/CSV export support but code only supports JSON
# 2. README documents `timeout` config option that doesn't exist
# 3. README documents `cache_enabled` config option that doesn't exist
# 4. README documents `max_items` config option that doesn't exist
# 5. README says version is v1.1.0 but last release was March 2023 (outdated)
# 6. `process()` return structure not documented
# 7. `_transform()` method exists but not documented (internal API)
# 8. Validation rules not explained in README
# 9. No example of error handling in README
# 10. Changelog suggests features that don't work (xml/csv export)


import json
