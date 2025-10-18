"""Tests for StoreService (WIP - test isolation issues)."""

import pytest
from sqlalchemy.orm import Session

from mcp_server.auth.crypto import get_crypto_manager
from mcp_server.models.common import ValidationError
from mcp_server.models.database import Tenant
from mcp_server.services.store import StoreService

# Mark all tests in this file as WIP until isolation issues are fixed
pytestmark = pytest.mark.skip(reason="WIP - Test isolation issues to be fixed")


@pytest.fixture
def tenant(db_session: Session) -> Tenant:
    """Create a test tenant."""
    crypto = get_crypto_manager()
    master_key = "test-master-key-for-store-tests"
    hash_value, salt = crypto.hash_master_key(master_key)

    tenant = Tenant(master_key_hash=hash_value, salt=salt)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    return tenant


@pytest.mark.asyncio
async def test_register_store(db_session: Session, tenant: Tenant):
    """Test store registration with encryption."""
    service = StoreService(db_session)

    store = await service.register_store(
        tenant_id=str(tenant.id),
        store_id="12345",
        api_key="test-api-key",
        store_name="Test Store",
        label="Test",
    )

    assert store.id is not None
    assert store.tenant_id == tenant.id
    assert store.store_id == "12345"
    assert store.store_name == "Test Store"
    assert store.label == "Test"
    assert store.api_key_ciphertext is not None
    assert store.api_key_tag is not None
    assert store.api_key_nonce is not None


@pytest.mark.asyncio
async def test_register_store_duplicate_name(db_session: Session, tenant: Tenant):
    """Test that duplicate store names are rejected."""
    service = StoreService(db_session)

    # Register first store
    await service.register_store(
        tenant_id=str(tenant.id),
        store_id="12345",
        api_key="test-api-key",
        store_name="Test Store",
    )

    # Try to register with same name
    with pytest.raises(ValidationError, match="already exists"):
        await service.register_store(
            tenant_id=str(tenant.id),
            store_id="67890",
            api_key="test-api-key-2",
            store_name="Test Store",  # Duplicate name
        )


@pytest.mark.asyncio
async def test_register_store_duplicate_store_id(db_session: Session, tenant: Tenant):
    """Test that duplicate store IDs are rejected."""
    service = StoreService(db_session)

    # Register first store
    await service.register_store(
        tenant_id=str(tenant.id),
        store_id="12345",
        api_key="test-api-key",
        store_name="Store 1",
    )

    # Try to register with same store_id
    with pytest.raises(ValidationError, match="already exists"):
        await service.register_store(
            tenant_id=str(tenant.id),
            store_id="12345",  # Duplicate ID
            api_key="test-api-key-2",
            store_name="Store 2",
        )


@pytest.mark.asyncio
async def test_list_stores(db_session: Session, tenant: Tenant):
    """Test listing stores for a tenant."""
    service = StoreService(db_session)

    # Register multiple stores
    await service.register_store(
        tenant_id=str(tenant.id),
        store_id="12345",
        api_key="key1",
        store_name="Store 1",
    )
    await service.register_store(
        tenant_id=str(tenant.id),
        store_id="67890",
        api_key="key2",
        store_name="Store 2",
    )

    # List stores
    stores = await service.list_stores(str(tenant.id))

    assert len(stores) == 2
    assert stores[0].store_name in ["Store 1", "Store 2"]
    assert stores[1].store_name in ["Store 1", "Store 2"]


@pytest.mark.asyncio
async def test_get_store(db_session: Session, tenant: Tenant):
    """Test getting a store by ID."""
    service = StoreService(db_session)

    # Register store
    created = await service.register_store(
        tenant_id=str(tenant.id),
        store_id="12345",
        api_key="test-key",
        store_name="Test Store",
    )

    # Get store
    store = await service.get_store(str(tenant.id), str(created.id))

    assert store is not None
    assert store.id == created.id
    assert store.store_name == "Test Store"


@pytest.mark.asyncio
async def test_get_store_not_found(db_session: Session, tenant: Tenant):
    """Test getting non-existent store returns None."""
    service = StoreService(db_session)

    store = await service.get_store(str(tenant.id), "99999")

    assert store is None


@pytest.mark.asyncio
async def test_get_store_by_name(db_session: Session, tenant: Tenant):
    """Test getting a store by name."""
    service = StoreService(db_session)

    # Register store
    await service.register_store(
        tenant_id=str(tenant.id),
        store_id="12345",
        api_key="test-key",
        store_name="My Production Store",
    )

    # Get by name
    store = await service.get_store_by_name(str(tenant.id), "My Production Store")

    assert store is not None
    assert store.store_name == "My Production Store"


@pytest.mark.asyncio
async def test_delete_store(db_session: Session, tenant: Tenant):
    """Test deleting a store."""
    service = StoreService(db_session)

    # Register store
    store = await service.register_store(
        tenant_id=str(tenant.id),
        store_id="12345",
        api_key="test-key",
        store_name="Test Store",
    )

    # Delete it
    result = await service.delete_store(str(tenant.id), str(store.id))

    assert result is True

    # Verify it's gone
    deleted = await service.get_store(str(tenant.id), str(store.id))
    assert deleted is None


@pytest.mark.asyncio
async def test_delete_store_not_found(db_session: Session, tenant: Tenant):
    """Test deleting non-existent store returns False."""
    service = StoreService(db_session)

    result = await service.delete_store(str(tenant.id), "99999")

    assert result is False


@pytest.mark.asyncio
async def test_get_decrypted_credentials(db_session: Session, tenant: Tenant):
    """Test decrypting store credentials."""
    service = StoreService(db_session)

    # Register store with known API key
    original_api_key = "my-secret-api-key-12345"
    store = await service.register_store(
        tenant_id=str(tenant.id),
        store_id="12345",
        api_key=original_api_key,
        store_name="Test Store",
    )

    # Get decrypted credentials
    crypto = get_crypto_manager()
    tenant_key = crypto.derive_tenant_key(original_api_key, str(tenant.salt))

    decrypted_store_id, decrypted_api_key = await service.get_decrypted_credentials(
        str(tenant.id), str(store.id), tenant_key
    )

    assert decrypted_store_id == "12345"
    assert decrypted_api_key == original_api_key


@pytest.mark.asyncio
async def test_tenant_isolation(db_session: Session):
    """Test that tenants cannot access each other's stores."""
    service = StoreService(db_session)
    crypto = get_crypto_manager()

    # Create two tenants
    hash1, salt1 = crypto.hash_master_key("key1")
    tenant1 = Tenant(master_key_hash=hash1, salt=salt1)
    db_session.add(tenant1)

    hash2, salt2 = crypto.hash_master_key("key2")
    tenant2 = Tenant(master_key_hash=hash2, salt=salt2)
    db_session.add(tenant2)
    db_session.commit()

    # Register store for tenant1
    store = await service.register_store(
        tenant_id=str(tenant1.id),
        store_id="12345",
        api_key="key",
        store_name="Store 1",
    )

    # Tenant2 should not be able to access tenant1's store
    result = await service.get_store(str(tenant2.id), str(store.id))
    assert result is None

    # Tenant2 should not be able to delete tenant1's store
    deleted = await service.delete_store(str(tenant2.id), str(store.id))
    assert deleted is False

    # Store should still exist for tenant1
    still_there = await service.get_store(str(tenant1.id), str(store.id))
    assert still_there is not None

