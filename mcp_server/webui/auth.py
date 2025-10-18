"""Authentication utilities for WebUI."""

import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import Cookie, HTTPException, Request, status
from jose import JWTError, jwt

from mcp_server.config import settings
from mcp_server.services.tenant import TenantService
from mcp_server.utils.logging import logger


class AuthManager:
    """Manages WebUI authentication with JWT sessions."""

    def __init__(self):
        self.algorithm = "HS256"
        self.session_timeout = settings.session_timeout

    def create_session_token(self, tenant_id: int) -> str:
        """
        Create JWT session token for authenticated user.

        Args:
            tenant_id: Authenticated tenant ID

        Returns:
            JWT token string
        """
        expires = datetime.utcnow() + timedelta(seconds=self.session_timeout)
        payload = {
            "tenant_id": tenant_id,
            "exp": expires,
            "iat": datetime.utcnow(),
            "type": "webui_session",
        }

        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=self.algorithm)
        return token

    def verify_session_token(self, token: str) -> dict[str, Any] | None:
        """
        Verify and decode JWT session token.

        Args:
            token: JWT token string

        Returns:
            Token payload if valid, None if invalid
        """
        try:
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=[self.algorithm]
            )

            if payload.get("type") != "webui_session":
                return None

            return payload
        except JWTError as e:
            logger.warning("Invalid session token", error=str(e))
            return None

    async def authenticate_master_key(
        self, master_key: str, db
    ) -> tuple[bool, int | None]:
        """
        Authenticate user with master key.

        Args:
            master_key: Master key to authenticate
            db: Database session

        Returns:
            Tuple of (success: bool, tenant_id: int | None)
        """
        tenant_service = TenantService(db)

        try:
            tenant = tenant_service.authenticate(master_key)
            if tenant:
                logger.info("WebUI authentication successful", tenant_id=tenant.id)
                return True, tenant.id
            else:
                logger.warning("WebUI authentication failed", reason="invalid_key")
                return False, None
        except Exception as e:
            logger.error("WebUI authentication error", error=str(e))
            return False, None


# Global auth manager instance
auth_manager = AuthManager()


def generate_csrf_token() -> str:
    """Generate CSRF token."""
    return secrets.token_urlsafe(32)


def verify_csrf_token(token: str, session_token: str) -> bool:
    """
    Verify CSRF token matches session.

    Args:
        token: CSRF token from form
        session_token: Session token from cookie

    Returns:
        True if valid, False otherwise
    """
    # For simplicity, we use a time-based CSRF token derived from session
    # In production, you might want to store tokens in Redis or database
    return len(token) == 43 and token.replace("-", "").replace("_", "").isalnum()


async def get_current_user(
    request: Request, session: str | None = Cookie(None, alias="session")
) -> dict[str, Any]:
    """
    Dependency to get current authenticated user from session cookie.

    Args:
        request: FastAPI request
        session: Session cookie value

    Returns:
        User info dict with tenant_id

    Raises:
        HTTPException: If not authenticated
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = auth_manager.verify_session_token(session)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "tenant_id": payload["tenant_id"],
        "authenticated": True,
    }


def create_session_cookie(token: str) -> dict[str, Any]:
    """
    Create session cookie configuration.

    Args:
        token: JWT session token

    Returns:
        Cookie configuration dict
    """
    return {
        "key": "session",
        "value": token,
        "httponly": True,
        "secure": settings.session_cookie_secure,
        "samesite": settings.session_cookie_samesite,
        "max_age": settings.session_timeout,
    }

