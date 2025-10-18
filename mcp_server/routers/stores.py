"""
Store management endpoints and MCP tools.

Implements both HTTP endpoints (for WebUI) and MCP tools (for AI agents).

MCP Tools:
- tenant.use_master_key - Authenticate tenant and establish session
- stores.register - Register OrderDesk store
- stores.list - List tenant's stores
- stores.delete - Remove store registration
- stores.use_store - Set active store for session
- stores.resolve - Resolve store by ID or name (debug tool)
"""


from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from mcp_server.auth import crypto
from mcp_server.config import settings
from mcp_server.models.common import AuthError, NotFoundError, ValidationError
from mcp_server.models.database import get_db
from mcp_server.models.orderdesk import StoreCreateRequest, StoreResponse
from mcp_server.services.session import (
    get_tenant_key,
    require_auth,
    set_active_store,
    set_tenant,
)
from mcp_server.services.store import StoreService
from mcp_server.services.tenant import TenantService
from mcp_server.utils.logging import logger

router = APIRouter()


@router.post("/stores", response_model=StoreResponse, status_code=status.HTTP_201_CREATED)
async def create_store(
    store_data: StoreCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create a new store for the authenticated tenant."""
    try:
        tenant_id = request.state.tenant_id
        tenant_service = TenantService(db)

        # Check if store already exists for this tenant
        existing_stores = tenant_service.list_stores(tenant_id)
        for store in existing_stores:
            if store.store_id == store_data.store_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Store {store_data.store_id} already exists for this tenant",
                )

        return tenant_service.create_store(tenant_id, store_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create store: {str(e)}",
        )


@router.get("/stores", response_model=list[StoreResponse])
async def list_stores(
    request: Request,
    db: Session = Depends(get_db),
):
    """List all stores for the authenticated tenant."""
    try:
        tenant_id = request.state.tenant_id
        tenant_service = TenantService(db)
        return tenant_service.list_stores(tenant_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list stores: {str(e)}",
        )


@router.delete("/stores/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_store(
    store_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete a store."""
    try:
        tenant_id = request.state.tenant_id
        tenant_service = TenantService(db)

        success = tenant_service.delete_store(tenant_id, store_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Store not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete store: {str(e)}",
        )


# ============================================================================
# MCP Tools - Tenant & Store Management
# ============================================================================

class UseMasterKeyParams(BaseModel):
    """Parameters for tenant.use_master_key tool."""
    master_key: str = Field(
        ...,
        description="Your master key (min 16 chars). Keep this secret!",
        min_length=16
    )

    class Config:
        json_schema_extra = {
            "example": {
                "master_key": "your-32-char-master-key-here"
            }
        }


class RegisterStoreParams(BaseModel):
    """
    Parameters for stores.register tool.

    Maps to: Store registration in database with encrypted credentials.
    Docs: See speckit.specify for store management details.
    """
    store_id: str = Field(..., description="OrderDesk store ID from Settings > API")
    api_key: str = Field(..., description="OrderDesk API key from Settings > API")
    store_name: str | None = Field(None, description="Friendly name for lookup (defaults to store_id)")
    label: str | None = Field(None, description="Optional label (e.g., 'Production', 'Staging')")

    class Config:
        json_schema_extra = {
            "example": {
                "store_id": "12345",
                "api_key": "your-orderdesk-api-key",
                "store_name": "my-production-store",
                "label": "Production"
            }
        }


class UseStoreParams(BaseModel):
    """Parameters for stores.use_store tool."""
    identifier: str = Field(..., description="Store ID or store name")

    class Config:
        json_schema_extra = {
            "examples": [
                {"identifier": "12345"},
                {"identifier": "my-production-store"}
            ]
        }


class DeleteStoreParams(BaseModel):
    """Parameters for stores.delete tool."""
    store_id: str = Field(..., description="Store ID to delete")


class ResolveStoreParams(BaseModel):
    """Parameters for stores.resolve tool."""
    identifier: str = Field(..., description="Store ID or store name to resolve")


# MCP Tool Implementations

async def use_master_key(params: UseMasterKeyParams, db: Session = Depends(get_db)) -> dict:
    """
    Authenticate tenant and establish session.

    MCP Tool: tenant.use_master_key

    This is the first tool to call. It authenticates your master key and
    establishes a session for subsequent tool calls.

    Args:
        master_key: Your master key (generated during signup or provided)

    Returns:
        {
            "status": "success",
            "tenant_id": "uuid",
            "stores_count": 3,
            "message": "Authenticated successfully"
        }

    Raises:
        AuthError: If master key is invalid
    """
    try:
        tenant_service = TenantService(db)

        # Authenticate or create tenant (if auto-provision enabled)
        tenant = tenant_service.authenticate_or_create(
            master_key=params.master_key,
            auto_provision=settings.auto_provision_tenant
        )

        if not tenant:
            raise AuthError("Invalid master key and auto-provision disabled")

        # Derive tenant encryption key
        tenant_key = crypto.derive_tenant_key(params.master_key, tenant.salt)

        # Set session context
        set_tenant(tenant.id, tenant_key)

        # Count stores
        stores = await StoreService(db).list_stores(tenant.id)

        logger.info("Master key authentication successful", tenant_id=tenant.id)

        return {
            "status": "success",
            "tenant_id": tenant.id,
            "stores_count": len(stores),
            "message": f"Authenticated successfully. {len(stores)} stores registered."
        }

    except AuthError:
        raise
    except Exception as e:
        logger.error("Master key authentication failed", error=str(e))
        raise AuthError(f"Authentication failed: {str(e)}")


async def register_store(params: RegisterStoreParams, db: Session = Depends(get_db)) -> dict:
    """
    Register OrderDesk store with encrypted credentials.

    MCP Tool: stores.register

    Get your store_id and api_key from OrderDesk Settings > API.

    Args:
        store_id: OrderDesk store ID
        api_key: OrderDesk API key (will be encrypted)
        store_name: Friendly name (optional, defaults to store_id)
        label: Optional label for organization

    Returns:
        {
            "status": "success",
            "store_id": "12345",
            "store_name": "my-store",
            "message": "Store registered successfully"
        }

    Raises:
        AuthError: If not authenticated
        ValidationError: If duplicate store_name or store_id
    """
    tenant_id = require_auth()
    tenant_key = get_tenant_key()

    try:
        store_service = StoreService(db)
        store = await store_service.register_store(
            tenant_id=tenant_id,
            store_id=params.store_id,
            api_key=params.api_key,
            store_name=params.store_name,
            label=params.label,
            tenant_key=tenant_key
        )

        return {
            "status": "success",
            "store_id": store.store_id,
            "store_name": store.store_name,
            "label": store.label,
            "message": f"Store '{store.store_name}' registered successfully"
        }

    except (ValidationError, NotFoundError) as e:
        raise e
    except Exception as e:
        logger.error("Store registration failed", error=str(e))
        raise ValidationError(f"Failed to register store: {str(e)}")


async def list_stores_mcp(db: Session = Depends(get_db)) -> dict:
    """
    List all stores for authenticated tenant.

    MCP Tool: stores.list

    Returns list of registered stores (credentials not included).

    Returns:
        {
            "status": "success",
            "stores": [
                {
                    "store_id": "12345",
                    "store_name": "my-store",
                    "label": "Production",
                    "created_at": "2025-10-17T12:00:00Z"
                }
            ],
            "count": 1
        }
    """
    tenant_id = require_auth()

    try:
        store_service = StoreService(db)
        stores = await store_service.list_stores(tenant_id)

        return {
            "status": "success",
            "stores": [
                {
                    "id": s.id,
                    "store_id": s.store_id,
                    "store_name": s.store_name,
                    "label": s.label,
                    "created_at": s.created_at.isoformat()
                }
                for s in stores
            ],
            "count": len(stores)
        }

    except Exception as e:
        logger.error("Failed to list stores", error=str(e))
        raise ValidationError(f"Failed to list stores: {str(e)}")


async def use_store(params: UseStoreParams, db: Session = Depends(get_db)) -> dict:
    """
    Set active store for session.

    MCP Tool: stores.use_store

    After calling this, subsequent tools will use this store if store_name is omitted.

    Args:
        identifier: Store ID or store name

    Returns:
        {
            "status": "success",
            "store_id": "12345",
            "store_name": "my-store",
            "message": "Active store set to 'my-store'"
        }

    Raises:
        NotFoundError: If store not found
    """
    tenant_id = require_auth()

    try:
        store_service = StoreService(db)
        store = await store_service.resolve_store(tenant_id, params.identifier)

        if not store:
            raise NotFoundError("Store", params.identifier)

        # Set as active store in session
        set_active_store(store.id)

        logger.info(
            "Active store set",
            tenant_id=tenant_id,
            store_id=store.store_id,
            store_name=store.store_name
        )

        return {
            "status": "success",
            "store_id": store.store_id,
            "store_name": store.store_name,
            "message": f"Active store set to '{store.store_name}'"
        }

    except NotFoundError:
        raise
    except Exception as e:
        logger.error("Failed to set active store", error=str(e))
        raise ValidationError(f"Failed to set active store: {str(e)}")


async def delete_store_mcp(params: DeleteStoreParams, db: Session = Depends(get_db)) -> dict:
    """
    Delete store registration.

    MCP Tool: stores.delete

    Removes store from your account. Does not affect OrderDesk.

    Args:
        store_id: Store ID to delete

    Returns:
        {
            "status": "success",
            "message": "Store deleted successfully"
        }

    Raises:
        NotFoundError: If store not found
    """
    tenant_id = require_auth()

    try:
        store_service = StoreService(db)
        success = await store_service.delete_store(tenant_id, params.store_id)

        if not success:
            raise NotFoundError("Store", params.store_id)

        return {
            "status": "success",
            "message": f"Store {params.store_id} deleted successfully"
        }

    except NotFoundError:
        raise
    except Exception as e:
        logger.error("Failed to delete store", error=str(e))
        raise ValidationError(f"Failed to delete store: {str(e)}")


async def resolve_store(params: ResolveStoreParams, db: Session = Depends(get_db)) -> dict:
    """
    Resolve store by ID or name (debug tool).

    MCP Tool: stores.resolve

    Returns store information without credentials.
    Useful for debugging and verifying store resolution logic.

    Args:
        identifier: Store ID or store name

    Returns:
        {
            "status": "success",
            "store_id": "12345",
            "store_name": "my-store",
            "label": "Production"
        }

    Raises:
        NotFoundError: If store not found
    """
    tenant_id = require_auth()

    try:
        store_service = StoreService(db)
        store = await store_service.resolve_store(tenant_id, params.identifier)

        if not store:
            raise NotFoundError("Store", params.identifier)

        return {
            "status": "success",
            "store_id": store.store_id,
            "store_name": store.store_name,
            "label": store.label,
            "resolved_by": "store_id" if params.identifier == store.store_id else "store_name"
        }

    except NotFoundError:
        raise
    except Exception as e:
        logger.error("Failed to resolve store", error=str(e))
        raise ValidationError(f"Failed to resolve store: {str(e)}")


# ============================================================================
# MCP Tool Registration (for MCP server)
# ============================================================================

# Tool definitions will be registered by the MCP server
# Each tool maps to a function above with its parameter schema

MCP_TOOLS = {
    "tenant.use_master_key": {
        "function": use_master_key,
        "params_schema": UseMasterKeyParams,
        "description": "Authenticate tenant using master key and establish session"
    },
    "stores.register": {
        "function": register_store,
        "params_schema": RegisterStoreParams,
        "description": "Register OrderDesk store with encrypted credentials"
    },
    "stores.list": {
        "function": list_stores_mcp,
        "params_schema": None,  # No parameters
        "description": "List all stores for authenticated tenant"
    },
    "stores.use_store": {
        "function": use_store,
        "params_schema": UseStoreParams,
        "description": "Set active store for session (subsequent tools will use this store)"
    },
    "stores.delete": {
        "function": delete_store_mcp,
        "params_schema": DeleteStoreParams,
        "description": "Delete store registration (does not affect OrderDesk)"
    },
    "stores.resolve": {
        "function": resolve_store,
        "params_schema": ResolveStoreParams,
        "description": "Resolve store by ID or name (debug tool)"
    }
}
