"""
Session context management for MCP requests.

Manages per-request context using async ContextVars:
- tenant_id: Current authenticated tenant
- tenant_key: Derived encryption key (in-memory only, never persisted)
- active_store_id: Currently selected store
- correlation_id: Request tracing ID

Per specification: Context scoped per MCP session, isolated between sessions.
"""

import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

# ============================================================================
# Context Variables (Async-safe, per-request isolation)
# ============================================================================

# Session context for MCP requests
_session_context: ContextVar[Optional["SessionContext"]] = ContextVar(
    'session_context',
    default=None
)


@dataclass
class SessionContext:
    """
    Session context for MCP requests.
    
    Holds authentication state and active store for a single MCP session.
    Per specification: Reduces repetitive parameters, maintains state across tool calls.
    """
    
    tenant_id: Optional[str] = None
    tenant_key: Optional[bytes] = None  # Derived key, in-memory only
    active_store_id: Optional[str] = None
    correlation_id: str = ""
    
    def __post_init__(self):
        """Generate correlation ID if not provided."""
        if not self.correlation_id:
            self.correlation_id = str(uuid.uuid4())


# ============================================================================
# Context Management Functions
# ============================================================================

def get_context() -> SessionContext:
    """
    Get current session context.
    
    Creates new context if none exists.
    """
    ctx = _session_context.get()
    if ctx is None:
        ctx = SessionContext()
        _session_context.set(ctx)
    return ctx


def set_context(ctx: SessionContext) -> None:
    """
    Set session context.
    
    Args:
        ctx: SessionContext to set for current async task
    """
    _session_context.set(ctx)


def clear_context() -> None:
    """Clear session context (on logout or session end)."""
    _session_context.set(None)


def set_tenant(tenant_id: str, tenant_key: bytes) -> None:
    """
    Set authenticated tenant in session context.
    
    Called after successful master key authentication.
    
    Args:
        tenant_id: Authenticated tenant ID
        tenant_key: Derived encryption key for this tenant
    """
    ctx = get_context()
    ctx.tenant_id = tenant_id
    ctx.tenant_key = tenant_key
    
    # Update logging context
    from mcp_server.utils.logging import tenant_id_var, correlation_id_var
    tenant_id_var.set(tenant_id)
    correlation_id_var.set(ctx.correlation_id)


def set_active_store(store_id: str) -> None:
    """
    Set active store in session context.
    
    Called by stores.use_store tool.
    Subsequent tools will use this store if store_name omitted.
    
    Args:
        store_id: Store ID to set as active
    """
    ctx = get_context()
    ctx.active_store_id = store_id
    
    # Update logging context
    from mcp_server.utils.logging import store_id_var
    store_id_var.set(store_id)


def get_active_store() -> Optional[str]:
    """
    Get active store ID from session context.
    
    Returns:
        Active store ID if set, None otherwise
    """
    ctx = get_context()
    return ctx.active_store_id


def get_tenant_id() -> Optional[str]:
    """Get authenticated tenant ID from session context."""
    ctx = get_context()
    return ctx.tenant_id


def get_tenant_key() -> Optional[bytes]:
    """Get tenant encryption key from session context (in-memory only)."""
    ctx = get_context()
    return ctx.tenant_key


def get_correlation_id() -> str:
    """Get correlation ID for current request."""
    ctx = get_context()
    return ctx.correlation_id


def require_auth() -> str:
    """
    Require authenticated tenant.
    
    Raises:
        AuthError: If not authenticated
    
    Returns:
        tenant_id
    """
    from mcp_server.models.common import AuthError
    
    tenant_id = get_tenant_id()
    if not tenant_id:
        raise AuthError("Not authenticated. Call tenant.use_master_key first.")
    return tenant_id


def new_correlation_id() -> str:
    """Generate and set new correlation ID for current request."""
    ctx = get_context()
    ctx.correlation_id = str(uuid.uuid4())
    
    # Update logging context
    from mcp_server.utils.logging import correlation_id_var
    correlation_id_var.set(ctx.correlation_id)
    
    return ctx.correlation_id

