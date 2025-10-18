"""Authentication middleware for master key validation."""

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from mcp_server.auth.crypto import get_crypto_manager
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
) -> Tenant | None:
    """Get or create tenant from master key."""
    # Try to find existing tenant
    crypto_manager = get_crypto_manager()
    for tenant in db.query(Tenant).all():
        # Bcrypt hash includes salt, so we only need the hash for verification
        # Type assertion: SQLAlchemy columns are str values at runtime
        if crypto_manager.verify_master_key(master_key, str(tenant.master_key_hash)):
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
    """Authenticate request using master key from Authorization header or query parameter."""
    # Try Authorization header first
    auth_header = request.headers.get("Authorization")
    master_key = None

    if auth_header and auth_header.startswith("Bearer "):
        master_key = auth_header[7:]  # Remove "Bearer " prefix

    # If no header, try query parameter (for mcp-remote compatibility)
    if not master_key:
        master_key = request.query_params.get("token")

    if not master_key:
        raise AuthError(
            "Missing master key in Authorization header or token query parameter"
        )

    # Get database session
    db = next(get_db())
    try:
        # Get tenant from master key
        tenant = await get_tenant_from_master_key(
            master_key,
            db,
            auto_provision=request.app.state.settings.auto_provision_tenant,
        )
        if not tenant:
            raise AuthError("Invalid master key")

        return tenant
    finally:
        db.close()


async def auth_middleware(request: Request, call_next):
    """Authentication middleware."""
    from fastapi.responses import JSONResponse

    # Skip auth for health and docs endpoints
    # Exclude health checks, docs, metrics, and WebUI from auth
    if (
        request.url.path.startswith("/health")
        or request.url.path
        in [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/metrics",
        ]
        or request.url.path.startswith("/webui")
    ):
        response = await call_next(request)
        return response

    try:
        # Authenticate request
        tenant = await authenticate_request(request)

        # Attach tenant to request state
        request.state.tenant = tenant
        request.state.tenant_id = tenant.id

    except AuthError as e:
        # Return 401 response directly (middleware can't use exception handlers)
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": e.message if hasattr(e, "message") else str(e),
                }
            },
        )
    except Exception as e:
        # Convert other errors to 401 responses
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "AUTHENTICATION_ERROR",
                    "message": f"Authentication error: {str(e)}",
                }
            },
        )

    response = await call_next(request)
    return response
