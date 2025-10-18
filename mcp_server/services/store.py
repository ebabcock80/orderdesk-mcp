"""
Store management service.

Handles:
- Store registration with encrypted API keys
- Store lookup by ID or name
- Store resolution (ID or name → credentials)
- Store CRUD operations

Per specification: One tenant → many stores, lookup by store_name supported.
"""

from sqlalchemy.orm import Session

from mcp_server.auth import crypto
from mcp_server.models.common import NotFoundError, ValidationError
from mcp_server.models.database import Store, Tenant
from mcp_server.utils.logging import logger


class StoreService:
    """
    Service for managing OrderDesk store registrations.

    Per specification:
    - API keys encrypted with AES-256-GCM (separate ciphertext, tag, nonce)
    - Store lookup by friendly name (store_name) or OrderDesk ID (store_id)
    - Tenant isolation (no cross-tenant access)
    """

    def __init__(self, db: Session):
        self.db = db

    async def register_store(
        self,
        tenant_id: str,
        store_id: str,
        api_key: str,
        store_name: str | None = None,
        label: str | None = None,
        tenant_key: bytes | None = None,
    ) -> Store:
        """
        Register new OrderDesk store with encrypted credentials.

        Per specification: Encrypt API key with AES-256-GCM using tenant's derived key.

        Args:
            tenant_id: Tenant ID
            store_id: OrderDesk store ID
            api_key: OrderDesk API key (plaintext, will be encrypted)
            store_name: Friendly name for lookup (defaults to store_id)
            label: Optional label (e.g., "Production", "Staging")
            tenant_key: Pre-derived tenant key (or will derive from tenant)

        Returns:
            Created Store

        Raises:
            ValidationError: If store_name or store_id already exists for tenant
            NotFoundError: If tenant not found
        """
        # Get tenant if key not provided
        if tenant_key is None:
            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                raise NotFoundError("Tenant", tenant_id)
            # Type assertion: SQLAlchemy columns are str values at runtime
            tenant_key = crypto.derive_tenant_key(api_key, str(tenant.salt))

        # Default store_name to store_id
        if not store_name:
            store_name = store_id

        # Check for duplicates
        existing_by_name = (
            self.db.query(Store)
            .filter(Store.tenant_id == tenant_id, Store.store_name == store_name)
            .first()
        )

        if existing_by_name:
            raise ValidationError(
                f"Store name '{store_name}' already exists for this tenant",
                invalid_fields={"store_name": "duplicate"},
            )

        existing_by_id = (
            self.db.query(Store)
            .filter(Store.tenant_id == tenant_id, Store.store_id == store_id)
            .first()
        )

        if existing_by_id:
            raise ValidationError(
                f"Store ID '{store_id}' already registered for this tenant",
                invalid_fields={"store_id": "duplicate"},
            )

        # Encrypt API key with AES-256-GCM
        ciphertext, tag, nonce = crypto.encrypt_api_key(api_key, tenant_key)

        # Create store
        store = Store(
            tenant_id=tenant_id,
            store_id=store_id,
            store_name=store_name,
            label=label,
            api_key_ciphertext=ciphertext,
            api_key_tag=tag,
            api_key_nonce=nonce,
        )

        self.db.add(store)
        self.db.commit()
        self.db.refresh(store)

        logger.info(
            "Store registered",
            tenant_id=tenant_id,
            store_id=store_id,
            store_name=store_name,
        )

        return store

    async def list_stores(self, tenant_id: str) -> list[Store]:
        """
        List all stores for a tenant.

        Per specification: Tenant isolation, no cross-tenant access.
        """
        stores = (
            self.db.query(Store)
            .filter(Store.tenant_id == tenant_id)
            .order_by(Store.created_at.desc())
            .all()
        )

        return stores

    async def get_store(self, tenant_id: str, store_id: str) -> Store | None:
        """
        Get store by OrderDesk store ID.

        Args:
            tenant_id: Tenant ID
            store_id: OrderDesk store ID
        """
        return (
            self.db.query(Store)
            .filter(Store.tenant_id == tenant_id, Store.store_id == store_id)
            .first()
        )

    async def get_store_by_name(self, tenant_id: str, store_name: str) -> Store | None:
        """
        Get store by friendly name (case-insensitive).

        Per specification: Enable lookup by store_name to reduce parameter repetition.
        """
        from sqlalchemy import func
        
        return (
            self.db.query(Store)
            .filter(
                Store.tenant_id == tenant_id, 
                func.lower(Store.store_name) == func.lower(store_name)
            )
            .first()
        )

    async def resolve_store(self, tenant_id: str, identifier: str) -> Store | None:
        """
        Resolve store by ID or name.

        Per specification: Try store_id first, then store_name.

        Args:
            tenant_id: Tenant ID
            identifier: Store ID or store name

        Returns:
            Store if found, None otherwise
        """
        # Try by store_id first
        store = await self.get_store(tenant_id, identifier)
        if store:
            return store

        # Fallback to store_name
        store = await self.get_store_by_name(tenant_id, identifier)
        return store

    async def delete_store(self, tenant_id: str, store_id: str) -> bool:
        """
        Delete store registration.

        Args:
            tenant_id: Tenant ID
            store_id: Store ID (not store_name)

        Returns:
            True if deleted, False if not found
        """
        store = await self.get_store(tenant_id, store_id)
        if not store:
            return False

        self.db.delete(store)
        self.db.commit()

        logger.info(
            "Store deleted",
            tenant_id=tenant_id,
            store_id=store_id,
            store_name=store.store_name,
        )

        return True

    async def get_decrypted_credentials(
        self, store: Store, tenant_key: bytes
    ) -> tuple[str, str]:
        """
        Get decrypted OrderDesk credentials.

        Args:
            store: Store model
            tenant_key: Derived tenant encryption key

        Returns:
            (store_id, api_key) decrypted

        Raises:
            Exception: If decryption fails (tampered data or wrong key)
        """
        # Decrypt API key using AES-256-GCM
        # Type assertions: SQLAlchemy columns are str values at runtime
        api_key = crypto.decrypt_api_key(
            str(store.api_key_ciphertext),
            str(store.api_key_tag),
            str(store.api_key_nonce),
            tenant_key,
        )

        return str(store.store_id), api_key

    async def test_store_credentials(
        self, tenant_id: str, store_id: str, tenant_key: bytes
    ) -> dict:
        """
        Test store credentials with OrderDesk API.

        Calls OrderDesk test endpoint to verify credentials.
        Useful for WebUI "Test Connection" feature.

        Returns:
            {"status": "success"/"error", "message": "..."}
        """
        from mcp_server.services.orderdesk_client import OrderDeskClient

        store = await self.get_store(tenant_id, store_id)
        if not store:
            return {"status": "error", "message": "Store not found"}

        # Decrypt credentials
        try:
            od_store_id, api_key = await self.get_decrypted_credentials(
                store, tenant_key
            )
        except Exception as e:
            logger.error("Decryption failed", error=str(e))
            return {"status": "error", "message": "Failed to decrypt credentials"}

        # Test with OrderDesk API
        try:
            client = OrderDeskClient(od_store_id, api_key)
            result = await client.get("test")

            if result.get("status") == "success":
                return {
                    "status": "success",
                    "message": "Connection successful",
                    "orderdesk_time": result.get("current_date_time"),
                }
            else:
                return {"status": "error", "message": "OrderDesk API returned error"}

        except Exception as e:
            logger.error("OrderDesk API test failed", error=str(e))
            return {"status": "error", "message": f"Connection failed: {str(e)}"}
