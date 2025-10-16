"""Tenant and store management service."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from mcp_server.auth.crypto import crypto_manager
from mcp_server.models.database import AuditLog, Store, Tenant
from mcp_server.models.orderdesk import StoreCreateRequest, StoreResponse


class TenantService:
    """Service for managing tenants and stores."""

    def __init__(self, db: Session):
        self.db = db

    def create_store(
        self, tenant_id: str, store_data: StoreCreateRequest
    ) -> StoreResponse:
        """Create a new store for a tenant."""
        # Get tenant to derive encryption key
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise ValueError("Tenant not found")

        # Derive tenant key for encryption
        tenant_key = crypto_manager.derive_tenant_key(
            tenant.master_key_hash, tenant.salt.encode("utf-8")
        )

        # Encrypt API key
        encrypted_api_key = crypto_manager.encrypt_api_key(
            store_data.api_key, tenant_key
        )

        # Create store
        store = Store(
            tenant_id=tenant_id,
            store_id=store_data.store_id,
            encrypted_api_key=encrypted_api_key,
            label=store_data.label,
        )
        self.db.add(store)
        self.db.commit()
        self.db.refresh(store)

        # Log audit event
        self._log_audit_event(
            tenant_id, "store_created", f"Store {store_data.store_id} created"
        )

        return StoreResponse(
            id=store.id,
            store_id=store.store_id,
            label=store.label,
            created_at=store.created_at,
        )

    def list_stores(self, tenant_id: str) -> List[StoreResponse]:
        """List all stores for a tenant."""
        stores = (
            self.db.query(Store)
            .filter(Store.tenant_id == tenant_id)
            .order_by(Store.created_at.desc())
            .all()
        )

        return [
            StoreResponse(
                id=store.id,
                store_id=store.store_id,
                label=store.label,
                created_at=store.created_at,
            )
            for store in stores
        ]

    def get_store(self, tenant_id: str, store_id: str) -> Optional[Store]:
        """Get a store by ID for a tenant."""
        return (
            self.db.query(Store)
            .filter(Store.tenant_id == tenant_id, Store.id ==store_id)
            .first()
        )

    def delete_store(self, tenant_id: str, store_id: str) -> bool:
        """Delete a store."""
        store = self.get_store(tenant_id, store_id)
        if not store:
            return False

        self.db.delete(store)
        self.db.commit()

        # Log audit event
        self._log_audit_event(
            tenant_id, "store_deleted", f"Store {store.store_id} deleted"
        )

        return True

    def get_store_credentials(self, tenant_id: str, store_id: str) -> Optional[tuple]:
        """Get decrypted store credentials."""
        store = self.get_store(tenant_id, store_id)
        if not store:
            return None

        # Get tenant to derive encryption key
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return None

        # Derive tenant key for decryption
        tenant_key = crypto_manager.derive_tenant_key(
            tenant.master_key_hash, tenant.salt.encode("utf-8")
        )

        # Decrypt API key
        try:
            api_key = crypto_manager.decrypt_api_key(store.encrypted_api_key, tenant_key)
            return store.store_id, api_key
        except Exception:
            return None

    def _log_audit_event(self, tenant_id: str, action: str, details: str) -> None:
        """Log an audit event."""
        audit_log = AuditLog(
            tenant_id=tenant_id,
            action=action,
            details=details,
        )
        self.db.add(audit_log)
        self.db.commit()
