"""
Order management endpoints and MCP tools.

Implements both HTTP endpoints (for WebUI) and MCP tools (for AI agents).

MCP Tools:
- orders.get - Fetch single order by ID
- orders.list - List orders with pagination and filtering
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from mcp_server.models.common import NotFoundError, OrderDeskError, ValidationError
from mcp_server.models.database import get_db
from mcp_server.models.orderdesk import (
    AddItemsRequest,
    AddNoteRequest,
    MoveFolderRequest,
    OrderMutation,
    UpdateAddressRequest,
)
from mcp_server.services.cache import cache_manager
from mcp_server.services.orderdesk_client import OrderDeskClient
from mcp_server.services.session import get_context, get_tenant_key, require_auth
from mcp_server.services.store import StoreService
from mcp_server.utils.logging import logger

router = APIRouter()


async def mutate_order_full(
    client: OrderDeskClient,
    store_id: str,
    order_id: str,
    mutator: callable,
    tenant_id: str,
) -> dict[str, Any]:
    """
    Apply a mutation to an order using the full-object update workflow.

    Args:
        client: OrderDesk client
        store_id: Store ID
        order_id: Order ID
        mutator: Function that takes an order dict and returns modified order dict
        tenant_id: Tenant ID (for logging/tracking)

    Returns:
        Updated order
    """
    # Fetch current order
    current_order = await client.fetch_full_order(order_id)

    # Apply mutator
    modified_order = mutator(current_order)

    # Calculate changes (difference between current and modified)
    changes = {}
    for key, value in modified_order.items():
        if key not in current_order or current_order[key] != value:
            changes[key] = value

    # Use update_order_with_retry for conflict resolution
    return await client.update_order_with_retry(order_id, changes)


async def get_orderdesk_client(request: Request, store_id: str, db: Session) -> OrderDeskClient:
    """Get OrderDesk client for the specified store."""
    tenant_id = request.state.tenant_id
    store_service = StoreService(db)

    # Get tenant key from context (set during auth)
    tenant_key = get_tenant_key()
    if not tenant_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Get store
    store = await store_service.resolve_store(tenant_id, store_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found",
        )

    # Get decrypted credentials
    store_id_actual, api_key = await store_service.get_decrypted_credentials(store, tenant_key)
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
    except OrderDeskError as e:
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
    except OrderDeskError as e:
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
    except OrderDeskError as e:
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
    except OrderDeskError as e:
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
    except OrderDeskError as e:
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
    except OrderDeskError as e:
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
    except OrderDeskError as e:
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
    except OrderDeskError as e:
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
    except OrderDeskError as e:
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
    except OrderDeskError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add note: {str(e)}",
        )


# ============================================================================
# MCP Tools - Order Operations
# ============================================================================

class GetOrderParams(BaseModel):
    """Parameters for orders.get tool."""
    order_id: str = Field(..., description="OrderDesk order ID")
    store_identifier: str | None = Field(
        None,
        description="Store ID or name (optional if active store is set)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "order_id": "123456",
                "store_identifier": "production"
            }
        }


class ListOrdersParams(BaseModel):
    """Parameters for orders.list tool."""
    store_identifier: str | None = Field(
        None,
        description="Store ID or name (optional if active store is set)"
    )
    limit: int = Field(
        50,
        ge=1,
        le=100,
        description="Number of orders to return (1-100, default 50)"
    )
    offset: int = Field(
        0,
        ge=0,
        description="Number of orders to skip (default 0)"
    )
    folder_id: int | None = Field(
        None,
        description="Filter by folder ID"
    )
    status: str | None = Field(
        None,
        description="Filter by status (e.g., 'open', 'completed', 'cancelled')"
    )
    search: str | None = Field(
        None,
        description="Search query (searches order ID, email, name, etc.)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "store_identifier": "production",
                "limit": 50,
                "offset": 0,
                "status": "open"
            }
        }


# MCP Tool Implementations

async def get_order_mcp(params: GetOrderParams, db: Session = Depends(get_db)) -> dict:
    """
    Get a single order by ID.

    MCP Tool: orders.get

    Fetches complete order information including items, customer details,
    shipping information, and all order metadata.

    Args:
        order_id: OrderDesk order ID
        store_identifier: Store ID or name (optional if active store set)

    Returns:
        {
            "status": "success",
            "order": {
                "id": "123456",
                "source_id": "ORDER-001",
                "email": "customer@example.com",
                "order_total": 29.99,
                "date_added": "2025-10-18T12:00:00Z",
                "order_items": [...],
                ...
            }
        }

    Raises:
        NotFoundError: If order or store not found
        AuthError: If not authenticated
    """
    tenant_id = require_auth()
    tenant_key = get_tenant_key()

    try:
        store_service = StoreService(db)

        # Resolve store (by identifier or active store)
        if params.store_identifier:
            store = await store_service.resolve_store(tenant_id, params.store_identifier)
        else:
            # Use active store from session
            context = get_context()
            if not context.active_store_id:
                raise ValidationError(
                    "No store specified and no active store set. Use stores.use_store first or provide store_identifier.",
                    missing_fields=["store_identifier"]
                )
            store = await store_service.get_store(tenant_id, context.active_store_id)

        if not store:
            raise NotFoundError("Store", params.store_identifier or "active")

        # Get decrypted credentials
        store_id, api_key = await store_service.get_decrypted_credentials(store, tenant_key)

        # Check cache first
        cache_key = f"orders/{params.order_id}"
        cached = await cache_manager.get(tenant_id, store.store_id, cache_key)
        if cached:
            logger.info(
                "Order fetched from cache",
                tenant_id=tenant_id,
                store_id=store.store_id,
                order_id=params.order_id
            )
            return {
                "status": "success",
                "order": cached,
                "cached": True
            }

        # Create OrderDesk client
        async with OrderDeskClient(store_id, api_key) as client:
            # Fetch order
            order = await client.get_order(params.order_id)

            # Cache the result (15 seconds TTL for orders)
            await cache_manager.set(tenant_id, store.store_id, cache_key, order)

            logger.info(
                "Order fetched successfully",
                tenant_id=tenant_id,
                store_id=store.store_id,
                order_id=params.order_id
            )

            return {
                "status": "success",
                "order": order,
                "cached": False
            }

    except (NotFoundError, ValidationError):
        raise
    except OrderDeskError as e:
        if e.code == "NOT_FOUND":
            raise NotFoundError("Order", params.order_id)
        raise
    except Exception as e:
        logger.error("Failed to fetch order", error=str(e))
        raise ValidationError(f"Failed to fetch order: {str(e)}")


async def list_orders_mcp(params: ListOrdersParams, db: Session = Depends(get_db)) -> dict:
    """
    List orders with pagination and filtering.

    MCP Tool: orders.list

    Retrieves a paginated list of orders with optional filtering by
    folder, status, and search query.

    Args:
        store_identifier: Store ID or name (optional if active store set)
        limit: Page size (1-100, default 50)
        offset: Starting position (default 0)
        folder_id: Filter by folder ID (optional)
        status: Filter by status (optional)
        search: Search query (optional)

    Returns:
        {
            "status": "success",
            "orders": [
                {
                    "id": "123456",
                    "source_id": "ORDER-001",
                    "email": "customer@example.com",
                    "order_total": 29.99,
                    ...
                }
            ],
            "pagination": {
                "count": 50,
                "limit": 50,
                "offset": 0,
                "page": 1,
                "has_more": true
            }
        }

    Pagination:
        - Use offset to get next pages: offset=0, 50, 100, ...
        - has_more indicates if more results exist
        - count shows results in current page

    Raises:
        ValidationError: If parameters invalid
        NotFoundError: If store not found
        AuthError: If not authenticated
    """
    tenant_id = require_auth()
    tenant_key = get_tenant_key()

    try:
        store_service = StoreService(db)

        # Resolve store (by identifier or active store)
        if params.store_identifier:
            store = await store_service.resolve_store(tenant_id, params.store_identifier)
        else:
            # Use active store from session
            context = get_context()
            if not context.active_store_id:
                raise ValidationError(
                    "No store specified and no active store set. Use stores.use_store first or provide store_identifier.",
                    missing_fields=["store_identifier"]
                )
            store = await store_service.get_store(tenant_id, context.active_store_id)

        if not store:
            raise NotFoundError("Store", params.store_identifier or "active")

        # Get decrypted credentials
        store_id, api_key = await store_service.get_decrypted_credentials(store, tenant_key)

        # Build cache parameters (for cache key generation)
        cache_params = {
            "limit": params.limit,
            "offset": params.offset,
        }
        if params.folder_id is not None:
            cache_params["folder_id"] = params.folder_id
        if params.status:
            cache_params["status"] = params.status
        if params.search:
            cache_params["search"] = params.search

        # Check cache first
        cached = await cache_manager.get(tenant_id, store.store_id, "orders", cache_params)
        if cached:
            logger.info(
                "Orders fetched from cache",
                tenant_id=tenant_id,
                store_id=store.store_id,
                count=cached.get("count", 0)
            )
            return {
                "status": "success",
                "orders": cached.get("orders", []),
                "pagination": cached.get("pagination", {}),
                "cached": True
            }

        # Create OrderDesk client
        async with OrderDeskClient(store_id, api_key) as client:
            # Fetch orders
            response = await client.list_orders(
                limit=params.limit,
                offset=params.offset,
                folder_id=params.folder_id,
                status=params.status,
                search=params.search
            )

            # Prepare response
            result = {
                "orders": response["orders"],
                "pagination": {
                    "count": response["count"],
                    "limit": response["limit"],
                    "offset": response["offset"],
                    "page": response["page"],
                    "has_more": response["has_more"]
                }
            }

            # Cache the result (15 seconds TTL for orders)
            await cache_manager.set(tenant_id, store.store_id, "orders", result, cache_params)

            logger.info(
                "Orders listed successfully",
                tenant_id=tenant_id,
                store_id=store.store_id,
                count=response["count"],
                page=response["page"]
            )

            return {
                "status": "success",
                **result,
                "cached": False
            }

    except (NotFoundError, ValidationError):
        raise
    except OrderDeskError as e:
        logger.error("OrderDesk API error", error=str(e), code=e.code)
        raise ValidationError(f"Failed to list orders: {e.message}")
    except Exception as e:
        logger.error("Failed to list orders", error=str(e))
        raise ValidationError(f"Failed to list orders: {str(e)}")


# ============================================================================
# MCP Tool Registration (for MCP server)
# ============================================================================

class CreateOrderParams(BaseModel):
    """Parameters for orders.create tool."""
    order_data: dict[str, Any] = Field(..., description="Order data including email and items")
    store_identifier: str | None = Field(
        None,
        description="Store ID or name (optional if active store is set)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "order_data": {
                    "email": "customer@example.com",
                    "order_items": [
                        {
                            "name": "Product A",
                            "quantity": 2,
                            "price": 14.99
                        }
                    ],
                    "shipping_method": "USPS First Class"
                },
                "store_identifier": "production"
            }
        }


class UpdateOrderParams(BaseModel):
    """Parameters for orders.update tool."""
    order_id: str = Field(..., description="OrderDesk order ID")
    changes: dict[str, Any] = Field(..., description="Partial changes to apply")
    store_identifier: str | None = Field(
        None,
        description="Store ID or name (optional if active store is set)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "order_id": "123456",
                "changes": {
                    "email": "newemail@example.com",
                    "customer_notes": "Please ship ASAP"
                },
                "store_identifier": "production"
            }
        }


class DeleteOrderParams(BaseModel):
    """Parameters for orders.delete tool."""
    order_id: str = Field(..., description="OrderDesk order ID")
    store_identifier: str | None = Field(
        None,
        description="Store ID or name (optional if active store is set)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "order_id": "123456",
                "store_identifier": "production"
            }
        }


# Additional MCP Tool Implementations

async def create_order_mcp(params: CreateOrderParams, db: Session = Depends(get_db)) -> dict:
    """
    Create a new order.

    MCP Tool: orders.create

    Creates a new order in OrderDesk with the provided data.

    Args:
        order_data: Order data (email and items required)
        store_identifier: Store ID or name (optional if active store set)

    Returns:
        {
            "status": "success",
            "order": {
                "id": "123456",
                "source_id": "ORDER-001",
                ...
            }
        }

    Raises:
        ValidationError: If required fields missing
        NotFoundError: If store not found
    """
    tenant_id = require_auth()
    tenant_key = get_tenant_key()

    try:
        store_service = StoreService(db)

        # Resolve store
        if params.store_identifier:
            store = await store_service.resolve_store(tenant_id, params.store_identifier)
        else:
            context = get_context()
            if not context.active_store_id:
                raise ValidationError(
                    "No store specified and no active store set.",
                    missing_fields=["store_identifier"]
                )
            store = await store_service.get_store(tenant_id, context.active_store_id)

        if not store:
            raise NotFoundError("Store", params.store_identifier or "active")

        # Get decrypted credentials
        store_id, api_key = await store_service.get_decrypted_credentials(store, tenant_key)

        # Create OrderDesk client
        async with OrderDeskClient(store_id, api_key) as client:
            # Create order
            order = await client.create_order(params.order_data)

            # Invalidate cache (new order affects list queries)
            await cache_manager.invalidate_pattern(f"{tenant_id}:{store.store_id}:orders")

            logger.info(
                "Order created successfully",
                tenant_id=tenant_id,
                store_id=store.store_id,
                order_id=order.get("id")
            )

            return {
                "status": "success",
                "order": order
            }

    except (NotFoundError, ValidationError):
        raise
    except OrderDeskError as e:
        logger.error("Failed to create order", error=str(e), code=e.code)
        raise ValidationError(f"Failed to create order: {e.message}")
    except Exception as e:
        logger.error("Failed to create order", error=str(e))
        raise ValidationError(f"Failed to create order: {str(e)}")


async def update_order_mcp(params: UpdateOrderParams, db: Session = Depends(get_db)) -> dict:
    """
    Update an order with safe merge workflow.

    MCP Tool: orders.update

    Uses the full-object update workflow to prevent data loss:
    1. Fetch current order state
    2. Merge your changes
    3. Upload complete object
    4. Retry on conflicts (up to 5 times)

    Args:
        order_id: OrderDesk order ID
        changes: Partial changes to apply
        store_identifier: Store ID or name (optional if active store set)

    Returns:
        {
            "status": "success",
            "order": {
                "id": "123456",
                ...
            },
            "retries": 0
        }

    Raises:
        ConflictError: If conflicts persist after 5 retries
        NotFoundError: If order or store not found
    """
    tenant_id = require_auth()
    tenant_key = get_tenant_key()

    try:
        store_service = StoreService(db)

        # Resolve store
        if params.store_identifier:
            store = await store_service.resolve_store(tenant_id, params.store_identifier)
        else:
            context = get_context()
            if not context.active_store_id:
                raise ValidationError(
                    "No store specified and no active store set.",
                    missing_fields=["store_identifier"]
                )
            store = await store_service.get_store(tenant_id, context.active_store_id)

        if not store:
            raise NotFoundError("Store", params.store_identifier or "active")

        # Get decrypted credentials
        store_id, api_key = await store_service.get_decrypted_credentials(store, tenant_key)

        # Create OrderDesk client
        async with OrderDeskClient(store_id, api_key) as client:
            # Update with automatic conflict resolution
            order = await client.update_order_with_retry(params.order_id, params.changes)

            # Invalidate cache for this order and list queries
            await cache_manager.delete(f"{tenant_id}:{store.store_id}:orders/{params.order_id}")
            await cache_manager.invalidate_pattern(f"{tenant_id}:{store.store_id}:orders")

            logger.info(
                "Order updated successfully",
                tenant_id=tenant_id,
                store_id=store.store_id,
                order_id=params.order_id
            )

            return {
                "status": "success",
                "order": order
            }

    except (NotFoundError, ValidationError):
        raise
    except OrderDeskError as e:
        if e.code == "NOT_FOUND":
            raise NotFoundError("Order", params.order_id)
        logger.error("Failed to update order", error=str(e), code=e.code)
        raise ValidationError(f"Failed to update order: {e.message}")
    except Exception as e:
        logger.error("Failed to update order", error=str(e))
        raise ValidationError(f"Failed to update order: {str(e)}")


async def delete_order_mcp(params: DeleteOrderParams, db: Session = Depends(get_db)) -> dict:
    """
    Delete an order.

    MCP Tool: orders.delete

    Permanently deletes an order from OrderDesk.

    Args:
        order_id: OrderDesk order ID
        store_identifier: Store ID or name (optional if active store set)

    Returns:
        {
            "status": "success",
            "message": "Order 123456 deleted successfully"
        }

    Raises:
        NotFoundError: If order or store not found
    """
    tenant_id = require_auth()
    tenant_key = get_tenant_key()

    try:
        store_service = StoreService(db)

        # Resolve store
        if params.store_identifier:
            store = await store_service.resolve_store(tenant_id, params.store_identifier)
        else:
            context = get_context()
            if not context.active_store_id:
                raise ValidationError(
                    "No store specified and no active store set.",
                    missing_fields=["store_identifier"]
                )
            store = await store_service.get_store(tenant_id, context.active_store_id)

        if not store:
            raise NotFoundError("Store", params.store_identifier or "active")

        # Get decrypted credentials
        store_id, api_key = await store_service.get_decrypted_credentials(store, tenant_key)

        # Create OrderDesk client
        async with OrderDeskClient(store_id, api_key) as client:
            # Delete order
            await client.delete_order(params.order_id)

            # Invalidate cache for this order and list queries
            await cache_manager.delete(f"{tenant_id}:{store.store_id}:orders/{params.order_id}")
            await cache_manager.invalidate_pattern(f"{tenant_id}:{store.store_id}:orders")

            logger.info(
                "Order deleted successfully",
                tenant_id=tenant_id,
                store_id=store.store_id,
                order_id=params.order_id
            )

            return {
                "status": "success",
                "message": f"Order {params.order_id} deleted successfully"
            }

    except (NotFoundError, ValidationError):
        raise
    except OrderDeskError as e:
        if e.code == "NOT_FOUND":
            raise NotFoundError("Order", params.order_id)
        logger.error("Failed to delete order", error=str(e), code=e.code)
        raise ValidationError(f"Failed to delete order: {e.message}")
    except Exception as e:
        logger.error("Failed to delete order", error=str(e))
        raise ValidationError(f"Failed to delete order: {str(e)}")


MCP_TOOLS = {
    "orders.get": {
        "function": get_order_mcp,
        "params_schema": GetOrderParams,
        "description": "Fetch a single order by ID with complete details"
    },
    "orders.list": {
        "function": list_orders_mcp,
        "params_schema": ListOrdersParams,
        "description": "List orders with pagination and filtering options"
    },
    "orders.create": {
        "function": create_order_mcp,
        "params_schema": CreateOrderParams,
        "description": "Create a new order in OrderDesk"
    },
    "orders.update": {
        "function": update_order_mcp,
        "params_schema": UpdateOrderParams,
        "description": "Update an order with safe merge workflow (fetch → merge → upload)"
    },
    "orders.delete": {
        "function": delete_order_mcp,
        "params_schema": DeleteOrderParams,
        "description": "Delete an order from OrderDesk"
    }
}
