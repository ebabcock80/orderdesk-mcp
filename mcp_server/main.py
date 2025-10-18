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
from mcp_server.utils.metrics import (
    REQUEST_COUNT,
    REQUEST_DURATION,
)
from mcp_server.utils.proxy import (
    get_cloudflare_ray,
    get_real_client_ip,
    should_add_hsts,
)
from mcp_server.webui import router as webui_router


def provision_admin_user():
    """
    Provision admin user if ADMIN_MASTER_KEY is set in environment.

    This ensures guaranteed access for development/testing.
    """
    if not settings.admin_master_key:
        return

    from mcp_server.auth.crypto import hash_master_key, verify_master_key
    from mcp_server.models.database import Tenant, get_db

    logger.info(
        "admin_provisioning",
        message="ADMIN_MASTER_KEY detected - provisioning admin account",
    )

    # Get database session
    db = next(get_db())

    try:
        # Check if any tenant matches the admin master key (synchronously)
        # We'll hash the key and check all tenants to see if it already exists
        tenants = db.query(Tenant).all()

        for tenant in tenants:
            # Verify if this tenant has the admin master key
            if verify_master_key(settings.admin_master_key, tenant.master_key_hash):
                logger.info(
                    "admin_provisioning",
                    message="Admin account already exists",
                    tenant_id=tenant.id,
                    email=tenant.email or "No email",
                )
                return

        # Admin doesn't exist, create it
        master_key_hash, salt = hash_master_key(settings.admin_master_key)

        admin = Tenant(
            master_key_hash=master_key_hash,
            salt=salt,
            email="admin@localhost",  # Default admin email
            email_verified=True,  # Pre-verified
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        logger.info(
            "admin_provisioning",
            message="Admin account created successfully",
            tenant_id=admin.id,
            email=admin.email,
        )

    except Exception as e:
        logger.error("admin_provisioning_error", error=str(e))
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("application_startup", message="Starting OrderDesk MCP Server")

    # Create database tables
    create_tables()
    logger.info("database_initialized", message="Database tables created")

    # Provision admin user if ADMIN_MASTER_KEY is set
    provision_admin_user()

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

# WebUI (Phase 5 - optional)
if settings.enable_webui:
    app.include_router(webui_router)
    logger.info("WebUI enabled", path="/webui")

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


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors with HTML for WebUI, JSON for API."""
    # Return HTML for WebUI requests
    if settings.enable_webui and request.url.path.startswith("/webui"):
        from fastapi.templating import Jinja2Templates

        templates = Jinja2Templates(directory="mcp_server/templates")
        return templates.TemplateResponse(
            "error_404.html", {"request": request}, status_code=404
        )

    # JSON for API requests
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "NOT_FOUND",
                "message": f"Resource not found: {request.url.path}",
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

    # Return HTML for WebUI requests
    if settings.enable_webui and request.url.path.startswith("/webui"):
        from fastapi.templating import Jinja2Templates

        templates = Jinja2Templates(directory="mcp_server/templates")
        return templates.TemplateResponse(
            "error_500.html",
            {"request": request, "error_id": request_id},
            status_code=500,
        )

    # JSON for API requests
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
