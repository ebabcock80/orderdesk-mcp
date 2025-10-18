"""
Product/inventory management endpoints and MCP tools.

Implements both HTTP endpoints (for WebUI) and MCP tools (for AI agents).

MCP Tools:
- products.get - Fetch single product by ID
- products.list - List products with pagination and search
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from mcp_server.models.common import NotFoundError, OrderDeskError, ValidationError
from mcp_server.models.database import get_db
from mcp_server.services.cache import cache_manager
from mcp_server.services.orderdesk_client import OrderDeskClient
from mcp_server.services.session import get_context, get_tenant_key, require_auth
from mcp_server.services.store import StoreService
from mcp_server.utils.logging import logger

router = APIRouter()


async def get_orderdesk_client(
    request: Request, store_id: str, db: Session
) -> OrderDeskClient:
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
    store_id_actual, api_key = await store_service.get_decrypted_credentials(
        store, tenant_key
    )
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
        result = await client.list_inventory_items(
            params=query_params, tenant_id=tenant_id
        )

        # Cache the result
        await cache_manager.set(tenant_id, store_id, "inventory", result, params)

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
    except OrderDeskError as e:
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
    except OrderDeskError as e:
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
        result = await client.update_inventory_item(
            item_id, item_data, tenant_id=tenant_id
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
    except OrderDeskError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete inventory item: {str(e)}",
        )


# ============================================================================
# MCP Tools - Product Operations
# ============================================================================


class GetProductParams(BaseModel):
    """Parameters for products.get tool."""

    product_id: str = Field(..., description="OrderDesk product/inventory item ID")
    store_identifier: str | None = Field(
        None, description="Store ID or name (optional if active store is set)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {"product_id": "product-123", "store_identifier": "production"}
        }
    }


class ListProductsParams(BaseModel):
    """Parameters for products.list tool."""

    store_identifier: str | None = Field(
        None, description="Store ID or name (optional if active store is set)"
    )
    limit: int = Field(
        50, ge=1, le=100, description="Number of products to return (1-100, default 50)"
    )
    offset: int = Field(0, ge=0, description="Number of products to skip (default 0)")
    search: str | None = Field(
        None, description="Search query (searches name, SKU, description, category)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "store_identifier": "production",
                "limit": 50,
                "offset": 0,
                "search": "widget",
            }
        }
    }


# MCP Tool Implementations


async def get_product_mcp(
    params: GetProductParams, db: Session = Depends(get_db)
) -> dict:
    """
    Get a single product by ID.

    MCP Tool: products.get

    Fetches complete product information including price, SKU, quantity,
    weight, category, and description.

    Args:
        product_id: OrderDesk product/inventory item ID
        store_identifier: Store ID or name (optional if active store set)

    Returns:
        {
            "status": "success",
            "product": {
                "id": "product-123",
                "name": "Premium Widget",
                "price": 49.99,
                "sku": "WIDGET-001",
                "quantity": 100,
                ...
            },
            "cached": false
        }

    Raises:
        NotFoundError: If product or store not found
        AuthError: If not authenticated
    """
    tenant_id = require_auth()
    tenant_key = get_tenant_key()

    try:
        store_service = StoreService(db)

        # Resolve store (by identifier or active store)
        if params.store_identifier:
            store = await store_service.resolve_store(
                tenant_id, params.store_identifier
            )
        else:
            context = get_context()
            if not context.active_store_id:
                raise ValidationError(
                    "No store specified and no active store set. Use stores.use_store first or provide store_identifier.",
                    missing_fields=["store_identifier"],
                )
            store = await store_service.get_store(tenant_id, context.active_store_id)

        if not store:
            raise NotFoundError("Store", params.store_identifier or "active")

        # Get decrypted credentials
        store_id, api_key = await store_service.get_decrypted_credentials(
            store, tenant_key
        )

        # Check cache first (60-second TTL for products)
        cache_key = f"products/{params.product_id}"
        cached = await cache_manager.get(tenant_id, store.store_id, cache_key)
        if cached:
            logger.info(
                "Product fetched from cache",
                tenant_id=tenant_id,
                store_id=store.store_id,
                product_id=params.product_id,
            )
            return {"status": "success", "product": cached, "cached": True}

        # Create OrderDesk client
        async with OrderDeskClient(store_id, api_key) as client:
            # Fetch product
            product = await client.get_product(params.product_id)

            # Cache the result (60 seconds TTL for products - longer than orders)
            await cache_manager.set(tenant_id, store.store_id, cache_key, product)

            logger.info(
                "Product fetched successfully",
                tenant_id=tenant_id,
                store_id=store.store_id,
                product_id=params.product_id,
            )

            return {"status": "success", "product": product, "cached": False}

    except (NotFoundError, ValidationError):
        raise
    except OrderDeskError as e:
        if e.code == "NOT_FOUND":
            raise NotFoundError("Product", params.product_id)
        raise
    except Exception as e:
        logger.error("Failed to fetch product", error=str(e))
        raise ValidationError(f"Failed to fetch product: {str(e)}")


async def list_products_mcp(
    params: ListProductsParams, db: Session = Depends(get_db)
) -> dict:
    """
    List products with pagination and search.

    MCP Tool: products.list

    Retrieves a paginated list of products with optional search filtering.
    Products are cached for 60 seconds (longer than orders).

    Args:
        store_identifier: Store ID or name (optional if active store set)
        limit: Page size (1-100, default 50)
        offset: Starting position (default 0)
        search: Search query (optional)

    Returns:
        {
            "status": "success",
            "products": [
                {
                    "id": "product-123",
                    "name": "Premium Widget",
                    "price": 49.99,
                    "sku": "WIDGET-001",
                    "quantity": 100,
                    ...
                }
            ],
            "pagination": {
                "count": 50,
                "limit": 50,
                "offset": 0,
                "page": 1,
                "has_more": true
            },
            "cached": false
        }

    Pagination:
        - Use offset to get next pages: offset=0, 50, 100, ...
        - has_more indicates if more results exist
        - count shows results in current page

    Search:
        - Searches across: name, SKU, description, category
        - Case-insensitive partial match

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
            store = await store_service.resolve_store(
                tenant_id, params.store_identifier
            )
        else:
            context = get_context()
            if not context.active_store_id:
                raise ValidationError(
                    "No store specified and no active store set. Use stores.use_store first or provide store_identifier.",
                    missing_fields=["store_identifier"],
                )
            store = await store_service.get_store(tenant_id, context.active_store_id)

        if not store:
            raise NotFoundError("Store", params.store_identifier or "active")

        # Get decrypted credentials
        store_id, api_key = await store_service.get_decrypted_credentials(
            store, tenant_key
        )

        # Build cache parameters
        cache_params = {
            "limit": params.limit,
            "offset": params.offset,
        }
        if params.search:
            cache_params["search"] = params.search

        # Check cache first (60-second TTL for products)
        cached = await cache_manager.get(
            tenant_id, store.store_id, "products", cache_params
        )
        if cached:
            logger.info(
                "Products fetched from cache",
                tenant_id=tenant_id,
                store_id=store.store_id,
                count=cached.get("count", 0),
            )
            return {
                "status": "success",
                "products": cached.get("products", []),
                "pagination": cached.get("pagination", {}),
                "cached": True,
            }

        # Create OrderDesk client
        async with OrderDeskClient(store_id, api_key) as client:
            # Fetch products
            response = await client.list_products(
                limit=params.limit, offset=params.offset, search=params.search
            )

            # Prepare response
            result = {
                "products": response["products"],
                "pagination": {
                    "count": response["count"],
                    "limit": response["limit"],
                    "offset": response["offset"],
                    "page": response["page"],
                    "has_more": response["has_more"],
                },
            }

            # Cache the result (60 seconds TTL for products - longer than orders)
            await cache_manager.set(
                tenant_id, store.store_id, "products", result, cache_params
            )

            logger.info(
                "Products listed successfully",
                tenant_id=tenant_id,
                store_id=store.store_id,
                count=response["count"],
                page=response["page"],
            )

            return {"status": "success", **result, "cached": False}

    except (NotFoundError, ValidationError):
        raise
    except OrderDeskError as e:
        logger.error("OrderDesk API error", error=str(e), code=e.code)
        raise ValidationError(f"Failed to list products: {e.message}")
    except Exception as e:
        logger.error("Failed to list products", error=str(e))
        raise ValidationError(f"Failed to list products: {str(e)}")


# ============================================================================
# MCP Tool Registration (for MCP server)
# ============================================================================

MCP_TOOLS = {
    "products.get": {
        "function": get_product_mcp,
        "params_schema": GetProductParams,
        "description": "Fetch a single product by ID with complete details (cached 60s)",
    },
    "products.list": {
        "function": list_products_mcp,
        "params_schema": ListProductsParams,
        "description": "List products with pagination and search (cached 60s)",
    },
}
