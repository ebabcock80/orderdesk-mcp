"""
Tests for database models and schema.

Per specification: Test schema creation, constraints, foreign keys, cascades.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from mcp_server.models.database import (
    Base, Tenant, Store, AuditLog, Session as DBSession,
    MagicLink, MasterKeyMetadata, WebhookEvent,
    init_db
)


@pytest.fixture
def db_engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Create database session for testing."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


class TestTenantModel:
    """Test Tenant model."""
    
    def test_create_tenant(self, db_session):
        """Should create tenant with required fields."""
        tenant = Tenant(
            master_key_hash="hashed-key",
            salt="random-salt"
        )
        db_session.add(tenant)
        db_session.commit()
        
        assert tenant.id is not None
        assert tenant.created_at is not None
    
    def test_tenant_id_is_uuid(self, db_session):
        """Tenant ID should be UUID format."""
        tenant = Tenant(master_key_hash="hash", salt="salt")
        db_session.add(tenant)
        db_session.commit()
        
        # UUID format: 8-4-4-4-12 characters
        assert len(tenant.id) == 36
        assert tenant.id.count('-') == 4


class TestStoreModel:
    """Test Store model."""
    
    def test_create_store(self, db_session):
        """Should create store with all required fields."""
        # Create tenant first
        tenant = Tenant(master_key_hash="hash", salt="salt")
        db_session.add(tenant)
        db_session.commit()
        
        # Create store
        store = Store(
            tenant_id=tenant.id,
            store_id="12345",
            store_name="my-store",
            api_key_ciphertext="encrypted",
            api_key_tag="tag",
            api_key_nonce="nonce"
        )
        db_session.add(store)
        db_session.commit()
        
        assert store.id is not None
        assert store.tenant_id == tenant.id
        assert store.created_at is not None
    
    def test_unique_store_name_per_tenant(self, db_session):
        """Duplicate store_name for same tenant should fail."""
        tenant = Tenant(master_key_hash="hash", salt="salt")
        db_session.add(tenant)
        db_session.commit()
        
        # First store
        store1 = Store(
            tenant_id=tenant.id,
            store_id="123",
            store_name="duplicate-name",
            api_key_ciphertext="enc1",
            api_key_tag="tag1",
            api_key_nonce="nonce1"
        )
        db_session.add(store1)
        db_session.commit()
        
        # Second store with same name
        store2 = Store(
            tenant_id=tenant.id,
            store_id="456",
            store_name="duplicate-name",
            api_key_ciphertext="enc2",
            api_key_tag="tag2",
            api_key_nonce="nonce2"
        )
        db_session.add(store2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_unique_store_id_per_tenant(self, db_session):
        """Duplicate store_id for same tenant should fail."""
        tenant = Tenant(master_key_hash="hash", salt="salt")
        db_session.add(tenant)
        db_session.commit()
        
        store1 = Store(
            tenant_id=tenant.id,
            store_id="duplicate-id",
            store_name="store1",
            api_key_ciphertext="enc1",
            api_key_tag="tag1",
            api_key_nonce="nonce1"
        )
        db_session.add(store1)
        db_session.commit()
        
        store2 = Store(
            tenant_id=tenant.id,
            store_id="duplicate-id",
            store_name="store2",
            api_key_ciphertext="enc2",
            api_key_tag="tag2",
            api_key_nonce="nonce2"
        )
        db_session.add(store2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_different_tenants_can_have_same_store_name(self, db_session):
        """Different tenants can use same store_name."""
        tenant1 = Tenant(master_key_hash="hash1", salt="salt1")
        tenant2 = Tenant(master_key_hash="hash2", salt="salt2")
        db_session.add_all([tenant1, tenant2])
        db_session.commit()
        
        store1 = Store(
            tenant_id=tenant1.id,
            store_id="123",
            store_name="my-store",
            api_key_ciphertext="enc1",
            api_key_tag="tag1",
            api_key_nonce="nonce1"
        )
        store2 = Store(
            tenant_id=tenant2.id,
            store_id="456",
            store_name="my-store",  # Same name, different tenant
            api_key_ciphertext="enc2",
            api_key_tag="tag2",
            api_key_nonce="nonce2"
        )
        db_session.add_all([store1, store2])
        db_session.commit()
        
        assert store1.store_name == store2.store_name
        assert store1.tenant_id != store2.tenant_id
    
    def test_cascade_delete_stores_when_tenant_deleted(self, db_session):
        """Deleting tenant should cascade delete all its stores."""
        tenant = Tenant(master_key_hash="hash", salt="salt")
        db_session.add(tenant)
        db_session.commit()
        
        store = Store(
            tenant_id=tenant.id,
            store_id="123",
            store_name="my-store",
            api_key_ciphertext="enc",
            api_key_tag="tag",
            api_key_nonce="nonce"
        )
        db_session.add(store)
        db_session.commit()
        
        store_id = store.id
        
        # Delete tenant
        db_session.delete(tenant)
        db_session.commit()
        
        # Store should be deleted
        deleted_store = db_session.query(Store).filter(Store.id == store_id).first()
        assert deleted_store is None


class TestAuditLogModel:
    """Test AuditLog model."""
    
    def test_create_audit_log(self, db_session):
        """Should create audit log with all fields."""
        tenant = Tenant(master_key_hash="hash", salt="salt")
        db_session.add(tenant)
        db_session.commit()
        
        log = AuditLog(
            tenant_id=tenant.id,
            store_id="store-123",
            tool_name="stores.register",
            parameters='{"store_id": "[REDACTED]"}',
            status="success",
            duration_ms=150,
            request_id="correlation-123",
            source="mcp"
        )
        db_session.add(log)
        db_session.commit()
        
        assert log.id is not None
        assert log.tenant_id == tenant.id
        assert log.tool_name == "stores.register"
        assert log.source == "mcp"


class TestWebUIModels:
    """Test WebUI-specific models."""
    
    def test_create_session(self, db_session):
        """Should create session record."""
        tenant = Tenant(master_key_hash="hash", salt="salt")
        db_session.add(tenant)
        db_session.commit()
        
        from datetime import datetime, timedelta, timezone
        
        session = DBSession(
            tenant_id=tenant.id,
            session_token="jwt-token-123",
            ip_address="192.168.1.1",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        db_session.add(session)
        db_session.commit()
        
        assert session.id is not None
        assert session.tenant_id == tenant.id
    
    def test_create_magic_link(self, db_session):
        """Should create magic link for signup/login."""
        from datetime import datetime, timedelta, timezone
        
        link = MagicLink(
            email="user@example.com",
            token="secure-token",
            token_hash="sha256-hash",
            purpose="signup",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15)
        )
        db_session.add(link)
        db_session.commit()
        
        assert link.id is not None
        assert link.used == False
        assert link.purpose == "signup"
    
    def test_magic_link_unique_token_hash(self, db_session):
        """Duplicate token_hash should fail."""
        from datetime import datetime, timedelta, timezone
        
        link1 = MagicLink(
            email="user1@example.com",
            token="token1",
            token_hash="duplicate-hash",
            purpose="login",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15)
        )
        db_session.add(link1)
        db_session.commit()
        
        link2 = MagicLink(
            email="user2@example.com",
            token="token2",
            token_hash="duplicate-hash",  # Duplicate
            purpose="login",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15)
        )
        db_session.add(link2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()


# Coverage target: >85%

