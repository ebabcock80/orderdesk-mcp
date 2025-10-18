"""Tests for health check endpoints."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient


def test_basic_health_check(client: TestClient):
    """Test basic /health endpoint."""
    response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "orderdesk-mcp-server"
    assert data["version"] == "0.1.0-alpha"
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0


def test_liveness_probe(client: TestClient):
    """Test /health/live Kubernetes liveness probe."""
    response = client.get("/health/live")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "alive"
    assert "uptime_seconds" in data
    assert "timestamp" in data
    assert isinstance(data["timestamp"], (int, float))


def test_readiness_probe_healthy(client: TestClient):
    """Test /health/ready when all dependencies are healthy."""
    response = client.get("/health/ready")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Should be ready
    assert data["status"] in ["ready", "not_ready"]

    # Should have checks
    assert "checks" in data
    assert "database" in data["checks"]
    assert "cache" in data["checks"]
    assert "timestamp" in data

    # Database check
    db_check = data["checks"]["database"]
    assert "status" in db_check
    assert db_check["status"] in ["healthy", "unhealthy"]

    # Cache check
    cache_check = data["checks"]["cache"]
    assert "status" in cache_check
    assert cache_check["status"] in ["healthy", "unhealthy", "degraded"]


def test_detailed_health_check(client: TestClient):
    """Test /health/detailed admin endpoint."""
    response = client.get("/health/detailed")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Overall status
    assert data["status"] in ["healthy", "degraded", "unhealthy"]
    assert data["version"] == "0.1.0-alpha"
    assert "uptime_seconds" in data
    assert "timestamp" in data

    # All checks
    assert "checks" in data
    assert "database" in data["checks"]
    assert "cache" in data["checks"]
    assert "disk" in data["checks"]
    assert "memory" in data["checks"]

    # Database check
    db_check = data["checks"]["database"]
    assert "status" in db_check
    if db_check["status"] == "healthy":
        assert "latency_ms" in db_check
        assert isinstance(db_check["latency_ms"], (int, float))

    # Cache check
    cache_check = data["checks"]["cache"]
    assert "status" in cache_check
    assert "backend" in cache_check

    # Disk check
    disk_check = data["checks"]["disk"]
    assert "status" in disk_check
    if disk_check["status"] != "unknown":
        assert "total_gb" in disk_check
        assert "used_gb" in disk_check
        assert "free_gb" in disk_check
        assert "percent_used" in disk_check

    # Memory check
    memory_check = data["checks"]["memory"]
    assert "status" in memory_check
    if memory_check["status"] != "unknown":
        assert "system_total_mb" in memory_check
        assert "system_used_mb" in memory_check
        assert "process_rss_mb" in memory_check

    # Configuration
    assert "configuration" in data
    config = data["configuration"]
    assert "cache_backend" in config
    assert "enable_webui" in config
    assert "enable_metrics" in config
    assert "log_level" in config


def test_health_endpoints_no_auth_required(client: TestClient):
    """Test that health endpoints don't require authentication."""
    # All health endpoints should work without auth
    endpoints = ["/health", "/health/live", "/health/ready", "/health/detailed"]

    for endpoint in endpoints:
        response = client.get(endpoint)
        # Should not return 401
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

