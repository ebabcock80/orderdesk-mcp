"""
Tenant authentication and management service.

Handles:
- Master key authentication
- Tenant creation (with auto-provision support)
- Tenant lookup and validation

Per specification: Master Key → Tenant → Stores
"""

from typing import Optional

from sqlalchemy.orm import Session

from mcp_server.auth import crypto
from mcp_server.models.database import Tenant
from mcp_server.models.common import AuthError
from mcp_server.utils.logging import logger


class TenantService:
    """
    Service for managing tenant authentication and lifecycle.
    
    Per specification:
    - Authenticate tenants via master key (bcrypt verification)
    - Auto-provision new tenants (if AUTO_PROVISION_TENANT=true)
    - Tenant isolation (no cross-tenant access)
    """

    def __init__(self, db: Session):
        self.db = db
    
    def authenticate(self, master_key: str) -> Optional[Tenant]:
        """
        Authenticate tenant with master key.
        
        Per specification: Verify master key against stored bcrypt hash.
        
        Args:
            master_key: Tenant's master key (plaintext)
        
        Returns:
            Tenant if authentication succeeds, None otherwise
        """
        # Find tenant by verifying master key against all hashes
        # Note: This is inefficient for many tenants, but acceptable for early versions
        # Future optimization: Index or cache tenant lookups
        tenants = self.db.query(Tenant).all()
        
        for tenant in tenants:
            if crypto.verify_master_key(master_key, tenant.master_key_hash):
                logger.info("Tenant authenticated", tenant_id=tenant.id)
                return tenant
        
        logger.warning("Authentication failed", reason="invalid_master_key")
        return None
    
    def create_tenant(self, master_key: str) -> Tenant:
        """
        Create new tenant with master key.
        
        Per specification:
        - Hash master key with bcrypt
        - Generate random salt for HKDF
        - Store hash and salt (never plaintext master key)
        
        Args:
            master_key: Master key for new tenant
        
        Returns:
            Created Tenant
        
        Raises:
            AuthError: If tenant already exists
        """
        # Check if tenant already exists
        existing = self.authenticate(master_key)
        if existing:
            raise AuthError("Tenant already exists for this master key")
        
        # Hash master key and generate salt
        master_key_hash, salt = crypto.hash_master_key(master_key)
        
        # Create tenant
        tenant = Tenant(
            master_key_hash=master_key_hash,
            salt=salt
        )
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        
        logger.info("Tenant created", tenant_id=tenant.id)
        
        return tenant
    
    def get_tenant_by_id(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID."""
        return self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
    
    def authenticate_or_create(self, master_key: str, auto_provision: bool = False) -> Optional[Tenant]:
        """
        Authenticate tenant or create if auto-provision enabled.
        
        Per specification: AUTO_PROVISION_TENANT toggle controls tenant creation.
        
        Args:
            master_key: Master key
            auto_provision: Whether to create tenant if not found
        
        Returns:
            Tenant if authentication/creation succeeds, None if not found and auto-provision disabled
        """
        # Try to authenticate
        tenant = self.authenticate(master_key)
        if tenant:
            return tenant
        
        # Auto-provision if enabled
        if auto_provision:
            logger.info("Auto-provisioning new tenant")
            return self.create_tenant(master_key)
        
        logger.warning("Tenant not found and auto-provision disabled")
        return None
    
    # Note: Store management methods have been moved to StoreService
    # in mcp_server/services/store.py for better separation of concerns
