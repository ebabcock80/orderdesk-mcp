"""Order management endpoints with full mutation workflow."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from mcp_server.models.database import get_db
from mcp_server.models.orderdesk import (
    AddItemsRequest,
    AddNoteRequest,
    MoveFolderRequest,
    OrderMutation,
    UpdateAddressRequest,
)
from mcp_server.services.cache import cache_manager
from mcp_server.services.orderdesk import OrderDeskAPIError, OrderDeskClient, mutate_order_full
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


@router.get("/stores/{store_id}/orders")
async def list_orders(
    store_id: str,
    request: Request,
    db: Session = Depends(get_db),
    limit: int | None = Query(None, ge=1, le=100),
    offset: int | None = Query(None, ge=0),
    folder_id: int | None = Query(None),
    status: str | None = Query(None),
):
    """List orders for a store with optional filters."""
    try:
        tenant_id = request.state.tenant_id

        # Check cache first
        params = {"limit": limit, "offset": offset, "folder_id": folder_id, "status": status}
        cached = await cache_manager.get(tenant_id, store_id, "orders", params)
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
        if folder_id:
            query_params["folder_id"] = folder_id
        if status:
            query_params["status"] = status

        # Fetch from OrderDesk API
        result = await client.list_orders(params=query_params, tenant_id=tenant_id)

        # Cache the result
        await cache_manager.set(tenant_id, store_id, "orders", result, params)

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
            detail=f"Failed to list orders: {str(e)}",
        )


@router.get("/stores/{store_id}/orders/{order_id}")
async def get_order(
    store_id: str,
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Get a single order."""
    try:
        tenant_id = request.state.tenant_id

        # Check cache first
        cached = await cache_manager.get(tenant_id, store_id, f"orders/{order_id}")
        if cached:
            return cached

        # Get OrderDesk client
        client = await get_orderdesk_client(request, store_id, db)

        # Fetch from OrderDesk API
        result = await client.get_order(order_id, tenant_id=tenant_id)

        # Cache the result
        await cache_manager.set(tenant_id, store_id, f"orders/{order_id}", result)

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
            detail=f"Failed to get order: {str(e)}",
        )


@router.post("/stores/{store_id}/orders")
async def create_order(
    store_id: str,
    order_data: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
):
    """Create a new order."""
    try:
        tenant_id = request.state.tenant_id

        # Get OrderDesk client
        client = await get_orderdesk_client(request, store_id, db)

        # Create order via OrderDesk API
        result = await client.create_order(order_data, tenant_id=tenant_id)

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
            detail=f"Failed to create order: {str(e)}",
        )


@router.put("/stores/{store_id}/orders/{order_id}")
async def update_order(
    store_id: str,
    order_id: str,
    order_data: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
):
    """Update an order (full object replacement)."""
    try:
        tenant_id = request.state.tenant_id

        # Get OrderDesk client
        client = await get_orderdesk_client(request, store_id, db)

        # Update order via OrderDesk API
        result = await client.update_order(order_id, order_data, tenant_id=tenant_id)

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
            detail=f"Failed to update order: {str(e)}",
        )


@router.delete("/stores/{store_id}/orders/{order_id}")
async def delete_order(
    store_id: str,
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete an order."""
    try:
        tenant_id = request.state.tenant_id

        # Get OrderDesk client
        client = await get_orderdesk_client(request, store_id, db)

        # Delete order via OrderDesk API
        result = await client.delete_order(order_id, tenant_id=tenant_id)

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
            detail=f"Failed to delete order: {str(e)}",
        )


@router.post("/stores/{store_id}/orders/{order_id}:mutate")
async def mutate_order(
    store_id: str,
    order_id: str,
    mutation: OrderMutation,
    request: Request,
    db: Session = Depends(get_db),
):
    """Apply mutations to an order using the full update workflow."""
    try:
        tenant_id = request.state.tenant_id

        # Get OrderDesk client
        client = await get_orderdesk_client(request, store_id, db)

        def mutator(order: dict[str, Any]) -> dict[str, Any]:
            """Apply mutation operations to the order."""
            for operation in mutation.operations:
                op_type = operation.get("op")
                path = operation.get("path")
                value = operation.get("value")

                if op_type == "replace":
                    # Navigate to the path and replace the value
                    keys = path.split(".")
                    current = order
                    for key in keys[:-1]:
                        if key not in current:
                            current[key] = {}
                        current = current[key]
                    current[keys[-1]] = value
                elif op_type == "add":
                    # Add a new field
                    keys = path.split(".")
                    current = order
                    for key in keys[:-1]:
                        if key not in current:
                            current[key] = {}
                        current = current[key]
                    current[keys[-1]] = value
                elif op_type == "remove":
                    # Remove a field
                    keys = path.split(".")
                    current = order
                    for key in keys[:-1]:
                        if key not in current:
                            return order  # Path doesn't exist
                        current = current[key]
                    if keys[-1] in current:
                        del current[keys[-1]]

            return order

        # Apply mutation using full update workflow
        result = await mutate_order_full(
            client, store_id, order_id, mutator, tenant_id=tenant_id
        )

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
            detail=f"Failed to mutate order: {str(e)}",
        )


@router.post("/stores/{store_id}/orders/{order_id}/move-folder")
async def move_order_to_folder(
    store_id: str,
    order_id: str,
    move_request: MoveFolderRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Move an order to a different folder."""
    try:
        tenant_id = request.state.tenant_id

        # Get OrderDesk client
        client = await get_orderdesk_client(request, store_id, db)

        def mutator(order: dict[str, Any]) -> dict[str, Any]:
            """Update the folder_id."""
            if move_request.folder_id is not None:
                order["folder_id"] = move_request.folder_id
            return order

        # Apply mutation using full update workflow
        result = await mutate_order_full(
            client, store_id, order_id, mutator, tenant_id=tenant_id
        )

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
            detail=f"Failed to move order: {str(e)}",
        )


@router.post("/stores/{store_id}/orders/{order_id}/add-items")
async def add_items_to_order(
    store_id: str,
    order_id: str,
    add_request: AddItemsRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Add items to an order."""
    try:
        tenant_id = request.state.tenant_id

        # Get OrderDesk client
        client = await get_orderdesk_client(request, store_id, db)

        def mutator(order: dict[str, Any]) -> dict[str, Any]:
            """Add items to the order."""
            if "items" not in order:
                order["items"] = []

            # Convert Pydantic models to dicts
            new_items = [item.dict() for item in add_request.items]
            order["items"].extend(new_items)

            # Update quantity total
            if order.get("quantity_total"):
                order["quantity_total"] += sum(item.get("quantity", 0) for item in new_items)

            return order

        # Apply mutation using full update workflow
        result = await mutate_order_full(
            client, store_id, order_id, mutator, tenant_id=tenant_id
        )

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
            detail=f"Failed to add items: {str(e)}",
        )


@router.post("/stores/{store_id}/orders/{order_id}/update-address")
async def update_order_address(
    store_id: str,
    order_id: str,
    address_request: UpdateAddressRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Update an order's address (shipping, customer, or return)."""
    try:
        tenant_id = request.state.tenant_id

        # Get OrderDesk client
        client = await get_orderdesk_client(request, store_id, db)

        def mutator(order: dict[str, Any]) -> dict[str, Any]:
            """Update the specified address."""
            address_type = address_request.address_type.lower()
            address_data = address_request.address.dict()

            if address_type == "shipping":
                order["shipping"] = address_data
            elif address_type == "customer":
                order["customer"] = address_data
            elif address_type == "return":
                order["return_address"] = address_data
            else:
                raise ValueError(f"Invalid address type: {address_type}")

            return order

        # Apply mutation using full update workflow
        result = await mutate_order_full(
            client, store_id, order_id, mutator, tenant_id=tenant_id
        )

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
            detail=f"Failed to update address: {str(e)}",
        )


@router.post("/stores/{store_id}/orders/{order_id}/add-note")
async def add_note_to_order(
    store_id: str,
    order_id: str,
    note_request: AddNoteRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Add a note to an order."""
    try:
        tenant_id = request.state.tenant_id

        # Get OrderDesk client
        client = await get_orderdesk_client(request, store_id, db)

        def mutator(order: dict[str, Any]) -> dict[str, Any]:
            """Add a note to the order."""
            if "notes" not in order:
                order["notes"] = []

            new_note = {
                "note": note_request.note,
                "type": note_request.note_type,
                "date_added": "2024-01-01 00:00:00",  # Will be set by OrderDesk
            }
            order["notes"].append(new_note)

            return order

        # Apply mutation using full update workflow
        result = await mutate_order_full(
            client, store_id, order_id, mutator, tenant_id=tenant_id
        )

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
            detail=f"Failed to add note: {str(e)}",
        )
