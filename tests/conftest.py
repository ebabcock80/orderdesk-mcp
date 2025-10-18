"""Pytest configuration and fixtures."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mcp_server.main import app
from mcp_server.models.database import Base, get_db


@pytest.fixture(scope="session")
def test_db():
    """Create a test database."""
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp()

    # Override database URL
    test_db_url = f"sqlite:///{db_path}"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create tables
    Base.metadata.create_all(bind=engine)

    yield TestingSessionLocal

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def db_session(test_db):
    """Get database session for testing."""
    session = test_db()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_db):
    """Get test client."""

    def override_get_db():
        try:
            db = test_db()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def master_key():
    """Generate a test master key."""
    return "test-master-key-12345"


@pytest.fixture
def auth_headers(master_key):
    """Get authentication headers."""
    return {"Authorization": f"Bearer {master_key}"}


@pytest.fixture
def test_store_data():
    """Get test store data."""
    return {
        "store_id": "test-store-123",
        "api_key": "test-api-key-456",
        "label": "Test Store",
    }
