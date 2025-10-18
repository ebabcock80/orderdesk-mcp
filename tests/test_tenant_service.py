"""Tests for TenantService (WIP - test isolation issues)."""

import pytest
from sqlalchemy.orm import Session

from mcp_server.models.database import Tenant
from mcp_server.services.tenant import TenantService

# Mark all tests in this file as WIP until isolation issues are fixed
pytestmark = pytest.mark.skip(reason="WIP - Test isolation issues to be fixed")


def test_create_tenant(db_session: Session):
    """Test creating a new tenant."""
    service = TenantService(db_session)
    master_key = "my-secure-master-key-32-chars"

    tenant = service.create_tenant(master_key)

    assert tenant.id is not None
    assert tenant.master_key_hash is not None
    assert tenant.salt is not None
    assert len(tenant.salt) == 64  # 32 bytes hex-encoded
    assert tenant.created_at is not None


def test_authenticate_valid_key(db_session: Session):
    """Test authenticating with valid master key."""
    service = TenantService(db_session)
    master_key = "my-secure-master-key-32-chars"

    # Create tenant
    created_tenant = service.create_tenant(master_key)

    # Authenticate with same key
    authenticated_tenant = service.authenticate(master_key)

    assert authenticated_tenant is not None
    assert authenticated_tenant.id == created_tenant.id


def test_authenticate_invalid_key(db_session: Session):
    """Test authenticating with invalid master key."""
    service = TenantService(db_session)
    master_key = "my-secure-master-key-32-chars"

    # Create tenant
    service.create_tenant(master_key)

    # Try to authenticate with wrong key
    result = service.authenticate("wrong-key")

    assert result is None


def test_authenticate_no_tenants(db_session: Session):
    """Test authentication when no tenants exist."""
    service = TenantService(db_session)

    result = service.authenticate("any-key")

    assert result is None


def test_authenticate_multiple_tenants(db_session: Session):
    """Test authentication with multiple tenants."""
    service = TenantService(db_session)

    # Create multiple tenants with different keys
    key1 = "first-master-key"
    key2 = "second-master-key"
    key3 = "third-master-key"

    tenant1 = service.create_tenant(key1)
    tenant2 = service.create_tenant(key2)
    tenant3 = service.create_tenant(key3)

    # Authenticate with each key
    auth1 = service.authenticate(key1)
    auth2 = service.authenticate(key2)
    auth3 = service.authenticate(key3)

    assert auth1 is not None and auth1.id == tenant1.id
    assert auth2 is not None and auth2.id == tenant2.id
    assert auth3 is not None and auth3.id == tenant3.id


def test_authenticate_or_create_existing(db_session: Session):
    """Test authenticate_or_create with existing tenant."""
    service = TenantService(db_session)
    master_key = "existing-key"

    # Create tenant
    original_tenant = service.create_tenant(master_key)

    # Authenticate (should not create new)
    tenant = service.authenticate_or_create(master_key, auto_provision=True)

    assert tenant.id == original_tenant.id

    # Should only be one tenant
    tenant_count = db_session.query(Tenant).count()
    assert tenant_count == 1


def test_authenticate_or_create_new_with_auto_provision(db_session: Session):
    """Test authenticate_or_create creates new tenant when auto_provision=True."""
    service = TenantService(db_session)
    master_key = "new-key"

    # No tenants exist
    assert db_session.query(Tenant).count() == 0

    # Authenticate with auto-provision
    tenant = service.authenticate_or_create(master_key, auto_provision=True)

    assert tenant is not None
    assert tenant.id is not None
    assert db_session.query(Tenant).count() == 1


def test_authenticate_or_create_new_without_auto_provision(db_session: Session):
    """Test authenticate_or_create returns None when auto_provision=False."""
    service = TenantService(db_session)
    master_key = "new-key"

    # No tenants exist
    assert db_session.query(Tenant).count() == 0

    # Authenticate without auto-provision
    tenant = service.authenticate_or_create(master_key, auto_provision=False)

    assert tenant is None
    assert db_session.query(Tenant).count() == 0


def test_master_key_hashing_is_unique(db_session: Session):
    """Test that same key creates different hashes (due to salt)."""
    service = TenantService(db_session)
    master_key = "same-key-for-both"

    tenant1 = service.create_tenant(master_key)
    tenant2 = service.create_tenant(master_key)

    # Different tenants
    assert tenant1.id != tenant2.id

    # Different hashes (different salts)
    assert tenant1.master_key_hash != tenant2.master_key_hash
    assert tenant1.salt != tenant2.salt

    # But both can authenticate
    auth1 = service.authenticate(master_key)
    assert auth1 is not None
    assert auth1.id in [tenant1.id, tenant2.id]  # Will match first one found

