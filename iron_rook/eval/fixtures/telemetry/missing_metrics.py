"""
Missing telemetry fixture - evaluates telemetry reviewer's ability to detect
missing observability, metrics, logging, and tracing.
"""

import time
from typing import Any, Dict, List, Optional


class DataProcessor:
    """Data processor with minimal observability."""

    def __init__(self, config: dict):
        self.config = config
        self._cache = {}
        # MISSING: metrics initialization
        # MISSING: logger initialization
        # MISSING: tracer initialization

    def process(self, items: List[dict]) -> Dict[str, Any]:
        # MISSING: span creation for tracing
        # MISSING: start time for latency metrics
        # MISSING: log entry for processing start

        results = []
        errors = 0

        for item in items:
            try:
                # MISSING: per-item span
                result = self._transform(item)
                results.append(result)
                # MISSING: success counter increment
            except Exception as e:
                errors += 1
                # MISSING: error logging with context
                # MISSING: error counter increment
                # MISSING: error details in trace

        # MISSING: processing duration metric
        # MISSING: items processed count metric
        # MISSING: error rate metric
        # MISSING: log entry for processing complete

        return {"items": results, "errors": errors}

    def _transform(self, item: dict) -> dict:
        # MISSING: any observability
        return {k: v for k, v in item.items() if v is not None}

    def get_from_cache(self, key: str) -> Optional[Any]:
        # MISSING: cache hit/miss metrics
        # MISSING: cache access logging
        return self._cache.get(key)

    def set_in_cache(self, key: str, value: Any, ttl: int = 3600) -> None:
        # MISSING: cache size metrics
        # MISSING: cache write logging
        self._cache[key] = value


class APIClient:
    """API client with minimal observability."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        # MISSING: HTTP client with tracing middleware

    def fetch(self, endpoint: str, params: dict = None) -> dict:
        # MISSING: span for HTTP request
        # MISSING: request start time
        # MISSING: log request details

        import requests

        response = requests.get(f"{self.base_url}/{endpoint}", params=params)

        # MISSING: response status code metric
        # MISSING: response latency metric
        # MISSING: response size metric
        # MISSING: error handling with proper logging

        return response.json()

    def post(self, endpoint: str, data: dict) -> dict:
        # MISSING: All observability
        import requests

        response = requests.post(f"{self.base_url}/{endpoint}", json=data)
        return response.json()


class DatabaseRepository:
    """Database operations without observability."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    def find_by_id(self, table: str, id: int) -> Optional[dict]:
        # MISSING: query duration metric
        # MISSING: query logging
        # MISSING: connection pool metrics
        # MISSING: span for DB query
        pass  # Implementation omitted

    def insert(self, table: str, data: dict) -> int:
        # MISSING: write latency metric
        # MISSING: write counter
        # MISSING: error handling with metrics
        pass

    def update(self, table: str, id: int, data: dict) -> bool:
        # MISSING: All observability
        pass


def background_task(items: List[dict]) -> None:
    """Background processing without observability."""
    # MISSING: task start logging
    # MISSING: task duration metric
    # MISSING: active tasks gauge

    processor = DataProcessor({})
    result = processor.process(items)

    # MISSING: task completion logging
    # MISSING: task success/failure counter
    pass


# What should be added:

METRICS_EXAMPLE = """
from prometheus_client import Counter, Histogram, Gauge

# Counters
requests_total = Counter(
    'processor_requests_total',
    'Total number of processing requests',
    ['status']  # success, error
)

items_processed = Counter(
    'processor_items_total',
    'Total items processed',
    ['operation']  # transform, validate
)

# Histograms
processing_duration = Histogram(
    'processor_duration_seconds',
    'Time spent processing',
    ['operation'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

# Gauges
cache_size = Gauge(
    'processor_cache_items',
    'Number of items in cache'
)

active_tasks = Gauge(
    'processor_active_tasks',
    'Number of active background tasks'
)
"""

LOGGING_EXAMPLE = """
import structlog

logger = structlog.get_logger()

def process(self, items: List[dict]) -> Dict[str, Any]:
    logger.info("processing_started", item_count=len(items))
    
    # ... processing ...
    
    logger.info(
        "processing_completed",
        item_count=len(results),
        error_count=errors,
        duration_ms=duration * 1000
    )
"""

TRACING_EXAMPLE = """
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def process(self, items: List[dict]) -> Dict[str, Any]:
    with tracer.start_as_current_span("process") as span:
        span.set_attribute("item_count", len(items))
        
        for item in items:
            with tracer.start_as_current_span("transform_item"):
                result = self._transform(item)
        
        span.set_attribute("result_count", len(results))
        span.set_attribute("error_count", errors)
"""


# Expected review findings:
# 1. DataProcessor - no metrics for processing operations
# 2. DataProcessor - no structured logging
# 3. DataProcessor - no tracing spans
# 4. DataProcessor - no cache hit/miss metrics
# 5. APIClient - no request latency metrics
# 6. APIClient - no HTTP status code metrics
# 7. APIClient - no request/response logging
# 8. DatabaseRepository - no query duration metrics
# 9. background_task - no task lifecycle metrics
# 10. Recommend adding: Prometheus metrics, structlog, OpenTelemetry
