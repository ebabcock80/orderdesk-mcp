"""Main FastAPI application with middleware and routing."""

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

try:
    from prometheus_client import Counter, Histogram, generate_latest
except ImportError:
    # Fallback for when prometheus_client is not available
    class Counter:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kwargs):
            return self

        def inc(self):
            pass

    class Histogram:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kwargs):
            return self

        def observe(self, value):
            pass

    def generate_latest():
        return b"# Prometheus metrics not available\n"


from starlette.middleware.base import BaseHTTPMiddleware

from mcp_server.auth.middleware import auth_middleware
from mcp_server.config import settings
from mcp_server.models.common import AuthError
from mcp_server.models.database import create_tables
from mcp_server.routers import health, orders, products, stores  # webhooks - Phase 5+
from mcp_server.utils.logging import logger
from mcp_server.utils.proxy import (
    get_cloudflare_ray,
    get_real_client_ip,
    should_add_hsts,
)

# Prometheus metrics - Enhanced for production monitoring
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
)

# MCP tool-specific metrics
MCP_TOOL_CALLS = Counter(
    "mcp_tool_calls_total",
    "Total MCP tool invocations",
    ["tool_name", "status"],
)

MCP_TOOL_DURATION = Histogram(
    "mcp_tool_duration_seconds",
    "MCP tool execution duration",
    ["tool_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Cache performance metrics
CACHE_OPERATIONS = Counter(
    "cache_operations_total",
    "Cache operations (hit/miss/set/invalidate)",
    ["operation", "resource_type"],
)

CACHE_HIT_RATE = Histogram(
    "cache_hit_rate",
    "Cache hit rate percentage",
    ["resource_type"],
    buckets=(0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

# Error tracking metrics
ERROR_COUNT = Counter(
    "errors_total",
    "Total errors by type",
    ["error_type", "error_code"],
)

# Database metrics
DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "Database query duration",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

DB_CONNECTIONS = Counter(
    "db_connections_total",
    "Database connections",
    ["operation"],
)

# Rate limiting metrics
RATE_LIMIT_HITS = Counter(
    "rate_limit_hits_total",
    "Rate limit enforcements",
    ["tenant_id", "limit_type"],
)

# OrderDesk API metrics
ORDERDESK_API_CALLS = Counter(
    "orderdesk_api_calls_total",
    "Calls to OrderDesk API",
    ["endpoint", "method", "status_code"],
)

ORDERDESK_API_DURATION = Histogram(
    "orderdesk_api_duration_seconds",
    "OrderDesk API call duration",
    ["endpoint"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("application_startup", message="Starting OrderDesk MCP Server")

    # Create database tables
    create_tables()
    logger.info("database_initialized", message="Database tables created")

    yield

    # Shutdown
    logger.info("application_shutdown", message="Shutting down OrderDesk MCP Server")


# Create FastAPI app
app = FastAPI(
    title="OrderDesk MCP Multi-Tenant API Gateway",
    description="Multi-tenant REST API gateway for OrderDesk with master key authentication",
    version="0.1.0",
    lifespan=lifespan,
)

# Store settings in app state
app.state.settings = settings


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request logging."""

    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Get real client IP
        client_ip = get_real_client_ip(request)
        request.state.client_ip = client_ip

        # Get Cloudflare Ray ID
        cf_ray = get_cloudflare_ray(request)

        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Log request
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            client_ip=client_ip,
            cf_ray=cf_ray,
            request_id=request_id,
            user_agent=request.headers.get("User-Agent"),
        )

        # Update Prometheus metrics
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
        ).inc()

        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.url.path,
        ).observe(time.time() - start_time)

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add HSTS header if HTTPS
        if should_add_hsts(request):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Add other security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response


# Add middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Add CORS middleware
if settings.allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add authentication middleware (after CORS, before routes)
app.middleware("http")(auth_middleware)

# Include routers
app.include_router(health.router)
app.include_router(stores.router)
app.include_router(orders.router)
app.include_router(products.router)
# Phase 5+ routers (not yet implemented):
# app.include_router(webhooks.router)


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type="text/plain")


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    """Handle authentication errors with 401 response."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    logger.warning(
        "authentication_failed",
        error=str(exc),
        request_id=request_id,
        path=request.url.path,
        method=request.method,
    )

    return JSONResponse(
        status_code=401,
        content={
            "error": {
                "code": "UNAUTHORIZED",
                "message": str(exc.message) if hasattr(exc, "message") else str(exc),
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for consistent error responses."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    logger.error(
        "unhandled_exception",
        error=str(exc),
        request_id=request_id,
        path=request.url.path,
        method=request.method,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred",
                "request_id": request_id,
            }
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "mcp_server.main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.log_level,
        reload=False,
    )
