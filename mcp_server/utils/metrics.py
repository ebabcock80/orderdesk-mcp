"""
Prometheus metrics for production monitoring.

Provides comprehensive observability into:
- HTTP request performance
- MCP tool execution
- Cache effectiveness
- Database performance
- Error tracking
- Rate limiting
- OrderDesk API calls
"""

import time
from contextlib import asynccontextmanager
from typing import Any

try:
    from prometheus_client import Counter, Gauge, Histogram

    PROMETHEUS_AVAILABLE = True
except ImportError:
    # Fallback for when prometheus_client is not available

    class Counter:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kwargs):
            return self

        def inc(self, amount=1):
            pass

    class Histogram:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kwargs):
            return self

        def observe(self, value):
            pass

    class Gauge:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kwargs):
            return self

        def set(self, value):
            pass

        def inc(self, amount=1):
            pass

        def dec(self, amount=1):
            pass

    PROMETHEUS_AVAILABLE = False


# ============================================================================
# HTTP Request Metrics
# ============================================================================

REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status_code"]
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.075,
        0.1,
        0.25,
        0.5,
        0.75,
        1.0,
        2.5,
        5.0,
        7.5,
        10.0,
    ),
)

REQUEST_IN_PROGRESS = Gauge(
    "http_requests_in_progress", "HTTP requests currently being processed", ["method"]
)


# ============================================================================
# MCP Tool Metrics
# ============================================================================

MCP_TOOL_CALLS = Counter(
    "mcp_tool_calls_total", "Total MCP tool invocations", ["tool_name", "status"]
)

MCP_TOOL_DURATION = Histogram(
    "mcp_tool_duration_seconds",
    "MCP tool execution duration",
    ["tool_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

MCP_TOOL_IN_PROGRESS = Gauge(
    "mcp_tool_calls_in_progress", "MCP tool calls currently executing", ["tool_name"]
)


# ============================================================================
# Cache Performance Metrics
# ============================================================================

CACHE_OPERATIONS = Counter(
    "cache_operations_total",
    "Cache operations (hit/miss/set/invalidate)",
    ["operation", "resource_type"],
)

CACHE_SIZE = Gauge("cache_size_bytes", "Estimated cache size in bytes", ["backend"])

CACHE_ITEMS = Gauge("cache_items_total", "Number of items in cache", ["resource_type"])


# ============================================================================
# Database Metrics
# ============================================================================

DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "Database query duration",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

DB_CONNECTIONS = Counter(
    "db_connections_total", "Database connections", ["operation"]
)

DB_POOL_SIZE = Gauge("db_pool_size", "Database connection pool size")

DB_POOL_AVAILABLE = Gauge(
    "db_pool_available", "Available database connections in pool"
)


# ============================================================================
# Error Tracking Metrics
# ============================================================================

ERROR_COUNT = Counter(
    "errors_total", "Total errors by type", ["error_type", "error_code", "endpoint"]
)

UNHANDLED_EXCEPTIONS = Counter(
    "unhandled_exceptions_total", "Unhandled exceptions", ["exception_type"]
)


# ============================================================================
# Rate Limiting Metrics
# ============================================================================

RATE_LIMIT_HITS = Counter(
    "rate_limit_hits_total", "Rate limit enforcements", ["tenant_id", "limit_type"]
)

RATE_LIMIT_TOKENS_AVAILABLE = Gauge(
    "rate_limit_tokens_available", "Available rate limit tokens", ["tenant_id"]
)


# ============================================================================
# OrderDesk API Metrics
# ============================================================================

ORDERDESK_API_CALLS = Counter(
    "orderdesk_api_calls_total",
    "Calls to OrderDesk API",
    ["endpoint", "method", "status_code"],
)

ORDERDESK_API_DURATION = Histogram(
    "orderdesk_api_duration_seconds",
    "OrderDesk API call duration",
    ["endpoint", "method"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

ORDERDESK_API_RETRIES = Counter(
    "orderdesk_api_retries_total", "OrderDesk API retry attempts", ["reason"]
)


# ============================================================================
# Tenant & Authentication Metrics
# ============================================================================

ACTIVE_TENANTS = Gauge("active_tenants_total", "Number of active tenants")

ACTIVE_STORES = Gauge(
    "active_stores_total", "Number of active stores", ["tenant_id"]
)

AUTH_ATTEMPTS = Counter(
    "auth_attempts_total", "Authentication attempts", ["status"]
)


# ============================================================================
# Helper Functions & Context Managers
# ============================================================================


@asynccontextmanager
async def track_request_duration(method: str, endpoint: str):
    """Context manager to track HTTP request duration."""
    REQUEST_IN_PROGRESS.labels(method=method).inc()
    start_time = time.perf_counter()

    try:
        yield
    finally:
        duration = time.perf_counter() - start_time
        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
        REQUEST_IN_PROGRESS.labels(method=method).dec()


@asynccontextmanager
async def track_mcp_tool(tool_name: str):
    """Context manager to track MCP tool execution."""
    MCP_TOOL_IN_PROGRESS.labels(tool_name=tool_name).inc()
    start_time = time.perf_counter()
    status = "error"

    try:
        yield
        status = "success"
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.perf_counter() - start_time
        MCP_TOOL_DURATION.labels(tool_name=tool_name).observe(duration)
        MCP_TOOL_CALLS.labels(tool_name=tool_name, status=status).inc()
        MCP_TOOL_IN_PROGRESS.labels(tool_name=tool_name).dec()


def record_cache_operation(
    operation: str, resource_type: str, hit: bool | None = None
):
    """Record cache operation (hit, miss, set, invalidate)."""
    CACHE_OPERATIONS.labels(operation=operation, resource_type=resource_type).inc()


def record_db_query(operation: str, duration: float):
    """Record database query execution."""
    DB_QUERY_DURATION.labels(operation=operation).observe(duration)


def record_error(error_type: str, error_code: str, endpoint: str = "unknown"):
    """Record error occurrence."""
    ERROR_COUNT.labels(
        error_type=error_type, error_code=error_code, endpoint=endpoint
    ).inc()


def record_orderdesk_call(
    endpoint: str, method: str, status_code: int, duration: float
):
    """Record OrderDesk API call."""
    ORDERDESK_API_CALLS.labels(
        endpoint=endpoint, method=method, status_code=str(status_code)
    ).inc()
    ORDERDESK_API_DURATION.labels(endpoint=endpoint, method=method).observe(duration)


def record_rate_limit_hit(tenant_id: str, limit_type: str = "api"):
    """Record rate limit enforcement."""
    RATE_LIMIT_HITS.labels(tenant_id=tenant_id, limit_type=limit_type).inc()


def record_auth_attempt(success: bool):
    """Record authentication attempt."""
    status = "success" if success else "failure"
    AUTH_ATTEMPTS.labels(status=status).inc()


# ============================================================================
# Metrics Summary for Health Checks
# ============================================================================


def get_metrics_summary() -> dict[str, Any]:
    """
    Get current metrics summary for health checks.

    Returns summary of key metrics without requiring Prometheus client.
    Useful for debugging and health check endpoints.
    """
    if not PROMETHEUS_AVAILABLE:
        return {"prometheus": "not_available"}

    # Note: This is a simplified summary
    # Full metrics available at /metrics endpoint
    return {
        "prometheus": "available",
        "metrics_endpoint": "/metrics",
        "note": "Full metrics available at Prometheus /metrics endpoint",
    }

