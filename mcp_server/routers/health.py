"""
Comprehensive health check endpoints for production monitoring.

Provides:
- /health - Basic uptime check
- /health/ready - Kubernetes readiness probe (checks dependencies)
- /health/live - Kubernetes liveness probe (application alive check)
- /health/detailed - Admin diagnostic endpoint (full system status)
"""

import asyncio
import os
import time
from typing import Any

import psutil
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from mcp_server.config import settings
from mcp_server.models.database import get_engine
from mcp_server.services.cache import cache_manager

router = APIRouter()

# Track application start time for uptime calculation
START_TIME = time.time()


def get_uptime_seconds() -> float:
    """Get application uptime in seconds."""
    return time.time() - START_TIME


async def check_database() -> dict[str, Any]:
    """
    Check database connectivity and health.

    Returns:
        Dict with status, latency, and optional error.
    """
    try:
        start = time.perf_counter()
        engine = get_engine()

        # Test connection with a simple query
        with engine.connect() as conn:
            conn.execute("SELECT 1").fetchone()

        latency_ms = (time.perf_counter() - start) * 1000

        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "url": settings.database_url.split("@")[-1]
            if "@" in settings.database_url
            else "sqlite",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "error_type": type(e).__name__,
        }


async def check_cache() -> dict[str, Any]:
    """
    Check cache backend health.

    Returns:
        Dict with status and backend type.
    """
    try:
        # Test cache read/write
        test_key = "health_check_test"
        test_value = {"timestamp": time.time()}

        start = time.perf_counter()
        await cache_manager.backend.set(test_key, test_value, ttl=5)
        result = await cache_manager.backend.get(test_key)
        await cache_manager.backend.delete(test_key)
        latency_ms = (time.perf_counter() - start) * 1000

        if result is None:
            return {
                "status": "degraded",
                "backend": settings.cache_backend,
                "message": "Cache read/write test failed",
            }

        return {
            "status": "healthy",
            "backend": settings.cache_backend,
            "latency_ms": round(latency_ms, 2),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "backend": settings.cache_backend,
            "error": str(e),
            "error_type": type(e).__name__,
        }


def check_disk_space() -> dict[str, Any]:
    """
    Check available disk space.

    Returns:
        Dict with disk usage statistics.
    """
    try:
        # Get disk usage for the data directory
        data_dir = os.path.dirname(settings.database_url.replace("sqlite:///", ""))
        if not data_dir or data_dir == "sqlite:":
            data_dir = "/app/data"

        # Fallback to root if data_dir doesn't exist
        if not os.path.exists(data_dir):
            data_dir = "/"

        usage = psutil.disk_usage(data_dir)

        # Warn if disk usage > 80%, critical if > 90%
        status_value = "healthy"
        if usage.percent > 90:
            status_value = "critical"
        elif usage.percent > 80:
            status_value = "warning"

        return {
            "status": status_value,
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent_used": round(usage.percent, 1),
            "path": data_dir,
        }
    except Exception as e:
        return {
            "status": "unknown",
            "error": str(e),
            "error_type": type(e).__name__,
        }


def check_memory() -> dict[str, Any]:
    """
    Check memory usage.

    Returns:
        Dict with memory usage statistics.
    """
    try:
        memory = psutil.virtual_memory()
        process = psutil.Process()
        process_memory = process.memory_info()

        # Warn if system memory > 80%, critical if > 90%
        status_value = "healthy"
        if memory.percent > 90:
            status_value = "critical"
        elif memory.percent > 80:
            status_value = "warning"

        return {
            "status": status_value,
            "system_total_mb": round(memory.total / (1024**2), 2),
            "system_used_mb": round(memory.used / (1024**2), 2),
            "system_percent_used": round(memory.percent, 1),
            "process_rss_mb": round(process_memory.rss / (1024**2), 2),
            "process_vms_mb": round(process_memory.vms / (1024**2), 2),
        }
    except Exception as e:
        return {
            "status": "unknown",
            "error": str(e),
            "error_type": type(e).__name__,
        }


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint for uptime monitors.

    Returns:
        Simple status response.

    Status Codes:
        200: Service is running
    """
    return {
        "status": "ok",
        "service": "orderdesk-mcp-server",
        "version": "0.1.0-alpha",
        "uptime_seconds": round(get_uptime_seconds(), 2),
    }


@router.get("/health/live")
async def liveness_check():
    """
    Kubernetes liveness probe.

    Checks if the application process is alive and responsive.
    Does NOT check dependencies (database, cache, etc.).

    Use this for Kubernetes liveness probes to restart unhealthy pods.

    Returns:
        Simple status response.

    Status Codes:
        200: Application is alive
    """
    return {
        "status": "alive",
        "uptime_seconds": round(get_uptime_seconds(), 2),
        "timestamp": time.time(),
    }


@router.get("/health/ready")
async def readiness_check():
    """
    Kubernetes readiness probe.

    Checks if the application is ready to accept traffic by testing:
    - Database connectivity
    - Cache backend availability

    Use this for Kubernetes readiness probes to route traffic.

    Returns:
        Status with dependency checks.

    Status Codes:
        200: Ready to accept traffic
        503: Not ready (dependencies unhealthy)
    """
    # Run checks in parallel
    db_check, cache_check = await asyncio.gather(
        check_database(), check_cache(), return_exceptions=True
    )

    # Handle exceptions from gather
    if isinstance(db_check, Exception):
        db_check = {"status": "unhealthy", "error": str(db_check)}
    if isinstance(cache_check, Exception):
        cache_check = {"status": "unhealthy", "error": str(cache_check)}

    # Determine overall readiness
    is_ready = (
        db_check.get("status") == "healthy"
        and cache_check.get("status") in ["healthy", "degraded"]
    )

    response_data = {
        "status": "ready" if is_ready else "not_ready",
        "checks": {"database": db_check, "cache": cache_check},
        "timestamp": time.time(),
    }

    if is_ready:
        return response_data
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=response_data
        )


@router.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check for admin/debugging.

    Provides comprehensive system status including:
    - Database health
    - Cache backend health
    - Disk space usage
    - Memory usage
    - Application uptime
    - Configuration summary

    Returns:
        Detailed system health report.

    Status Codes:
        200: Always returns 200 (for debugging)
    """
    # Run all checks in parallel
    db_check, cache_check = await asyncio.gather(
        check_database(), check_cache(), return_exceptions=True
    )

    # Handle exceptions from gather
    if isinstance(db_check, Exception):
        db_check = {"status": "unhealthy", "error": str(db_check)}
    if isinstance(cache_check, Exception):
        cache_check = {"status": "unhealthy", "error": str(cache_check)}

    # Sync checks
    disk_check = check_disk_space()
    memory_check = check_memory()

    # Determine overall health
    all_checks = [db_check, cache_check, disk_check, memory_check]
    critical_checks = [db_check, cache_check]

    has_critical_failure = any(
        check.get("status") == "unhealthy" for check in critical_checks
    )
    has_warning = any(
        check.get("status") in ["warning", "degraded"] for check in all_checks
    )

    if has_critical_failure:
        overall_status = "unhealthy"
    elif has_warning:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return {
        "status": overall_status,
        "version": "0.1.0-alpha",
        "uptime_seconds": round(get_uptime_seconds(), 2),
        "timestamp": time.time(),
        "checks": {
            "database": db_check,
            "cache": cache_check,
            "disk": disk_check,
            "memory": memory_check,
        },
        "configuration": {
            "cache_backend": settings.cache_backend,
            "enable_webui": settings.enable_webui,
            "enable_metrics": settings.enable_metrics,
            "log_level": settings.log_level,
        },
    }
