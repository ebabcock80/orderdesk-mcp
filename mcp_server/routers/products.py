"""Product/inventory management endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from mcp_server.models.database import get_db
from mcp_server.services.cache import cache_manager
from mcp_server.services.orderdesk import OrderDeskAPIError, OrderDeskClient
from mcp_server.services.tenant import TenantService

router = APIRouter()


async def get_orderdesk_client(request: Request, store_id: str, db: Session) -> OrderDeskClient:
    """Get OrderDesk client for the specified store."""
    tenant_id = request.state.tenant_id
    tenant_service = TenantService(db)

    credentials = tenant_service.get_store_credentials(tenant_id, store_id)
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found or invalid credentials",
        )

    store_id_actual, api_key = credentials
    return OrderDeskClient(store_id_actual, api_key)


@router.get("/stores/{store_id}/inventory")
async def list_inventory_items(
    store_id: str,
    request: Request,
    db: Session = Depends(get_db),
    limit: int | None = Query(None, ge=1, le=100),
    offset: int | None = Query(None, ge=0),
    search: str | None = Query(None),
):
    """List inventory items for a store."""
    try:
        tenant_id = request.state.tenant_id

        # Check cache first
        params = {"limit": limit, "offset": offset, "search": search}
        cached = await cache_manager.get(tenant_id, store_id, "inventory", params)
        if cached:
            return cached

        # Get OrderDesk client
        client = await get_orderdesk_client(request, store_id, db)

        # Build query parameters
        query_params = {}
        if limit:
            query_params["limit"] = limit
        if offset:
            query_params["offset"] = offset
        if search:
            query_params["search"] = search

        # Fetch from OrderDesk API
        result = await client.list_inventory_items(params=query_params, tenant_id=tenant_id)

        # Cache the result
        await cache_manager.set(tenant_id, store_id, "inventory", result, params)

        return result
    except HTTPException:
        raise
    except OrderDeskAPIError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list inventory items: {str(e)}",
        )


@router.get("/stores/{store_id}/inventory/{item_id}")
async def get_inventory_item(
    store_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Get a single inventory item."""
    try:
        tenant_id = request.state.tenant_id

        # Check cache first
        cached = await cache_manager.get(tenant_id, store_id, f"inventory/{item_id}")
        if cached:
            return cached

        # Get OrderDesk client
        client = await get_orderdesk_client(request, store_id, db)

        # Fetch from OrderDesk API
        result = await client.get_inventory_item(item_id, tenant_id=tenant_id)

        # Cache the result
        await cache_manager.set(tenant_id, store_id, f"inventory/{item_id}", result)

        return result
    except HTTPException:
        raise
    except OrderDeskAPIError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get inventory item: {str(e)}",
        )


@router.post("/stores/{store_id}/inventory")
async def create_inventory_item(
    store_id: str,
    item_data: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
):
    """Create a new inventory item."""
    try:
        tenant_id = request.state.tenant_id

        # Get OrderDesk client
        client = await get_orderdesk_client(request, store_id, db)

        # Create item via OrderDesk API
        result = await client.create_inventory_item(item_data, tenant_id=tenant_id)

        # Invalidate cache for this store
        await cache_manager.invalidate_store(tenant_id, store_id)

        return result
    except HTTPException:
        raise
    except OrderDeskAPIError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create inventory item: {str(e)}",
        )


@router.put("/stores/{store_id}/inventory/{item_id}")
async def update_inventory_item(
    store_id: str,
    item_id: str,
    item_data: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
):
    """Update an inventory item."""
    try:
        tenant_id = request.state.tenant_id

        # Get OrderDesk client
        client = await get_orderdesk_client(request, store_id, db)

        # Update item via OrderDesk API
        result = await client.update_inventory_item(item_id, item_data, tenant_id=tenant_id)

        # Invalidate cache for this store
        await cache_manager.invalidate_store(tenant_id, store_id)

        return result
    except HTTPException:
        raise
    except OrderDeskAPIError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update inventory item: {str(e)}",
        )


@router.delete("/stores/{store_id}/inventory/{item_id}")
async def delete_inventory_item(
    store_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete an inventory item."""
    try:
        tenant_id = request.state.tenant_id

        # Get OrderDesk client
        client = await get_orderdesk_client(request, store_id, db)

        # Delete item via OrderDesk API
        result = await client.delete_inventory_item(item_id, tenant_id=tenant_id)

        # Invalidate cache for this store
        await cache_manager.invalidate_store(tenant_id, store_id)

        return result
    except HTTPException:
        raise
    except OrderDeskAPIError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete inventory item: {str(e)}",
        )
