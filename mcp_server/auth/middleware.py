"""Authentication middleware for master key validation."""

from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from mcp_server.auth.crypto import crypto_manager
from mcp_server.models.database import Tenant, get_db


class AuthError(HTTPException):
    """Authentication error exception."""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_tenant_from_master_key(
    master_key: str, db: Session, auto_provision: bool = True
) -> Optional[Tenant]:
    """Get or create tenant from master key."""
    # Try to find existing tenant
    for tenant in db.query(Tenant).all():
        if crypto_manager.verify_master_key(master_key, tenant.master_key_hash, tenant.salt):
            return tenant

    # Auto-provision new tenant if enabled
    if auto_provision:
        hashed, salt = crypto_manager.hash_master_key(master_key)
        tenant = Tenant(
            master_key_hash=hashed,
            salt=salt,
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        return tenant

    return None


async def authenticate_request(request: Request) -> Tenant:
    """Authenticate request using master key."""
    # Extract Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AuthError("Missing or invalid Authorization header")

    master_key = auth_header[7:]  # Remove "Bearer " prefix
    if not master_key:
        raise AuthError("Empty master key")

    # Get database session
    db = next(get_db())
    try:
        # Get tenant from master key
        tenant = await get_tenant_from_master_key(
            master_key, db, auto_provision=request.app.state.settings.auto_provision_tenant
        )
        if not tenant:
            raise AuthError("Invalid master key")

        return tenant
    finally:
        db.close()


async def auth_middleware(request: Request, call_next):
    """Authentication middleware."""
    # Skip auth for health and docs endpoints
    if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
        response = await call_next(request)
        return response

    try:
        # Authenticate request
        tenant = await authenticate_request(request)
        
        # Attach tenant to request state
        request.state.tenant = tenant
        request.state.tenant_id = tenant.id
        
    except AuthError:
        # Let auth errors bubble up
        raise
    except Exception as e:
        # Convert other errors to auth errors
        raise AuthError(f"Authentication error: {str(e)}")

    response = await call_next(request)
    return response
