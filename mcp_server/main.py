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
from mcp_server.models.database import create_tables
from mcp_server.routers import health, orders, products, stores  # webhooks - Phase 5+
from mcp_server.utils.logging import logger
from mcp_server.utils.proxy import get_cloudflare_ray, get_real_client_ip, should_add_hsts

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
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
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

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
