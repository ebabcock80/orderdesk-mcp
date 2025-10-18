"""
HTTP MCP Protocol Endpoint

Provides HTTP/SSE interface for MCP protocol, enabling remote connections
from Claude Desktop and other MCP clients via mcp-remote.
"""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mcp_server.auth.middleware import authenticate_request
from mcp_server.models.database import Tenant, get_db
from mcp_server.services.session import set_tenant
from mcp_server.utils.logging import logger

router = APIRouter()


class MCPRequest(BaseModel):
    """MCP JSON-RPC request."""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict[str, Any] | None = None


class MCPResponse(BaseModel):
    """MCP JSON-RPC response."""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


@router.post("/mcp", response_model=None)
async def mcp_http_endpoint(
    request: Request,
    mcp_request: MCPRequest,
    db: Session = Depends(get_db),
):
    """
    HTTP MCP Protocol Endpoint

    Handles MCP protocol over HTTP for remote clients like Claude Desktop.
    Authentication via Authorization header or ?token= query parameter.

    Supported Methods:
    - initialize: Initialize MCP session
    - tools/list: List available tools
    - tools/call: Execute a tool

    Returns:
        MCP JSON-RPC response
    """
    try:
        # Authenticate request (checks Authorization header or ?token= query param)
        tenant = await authenticate_request(request)

        # Set tenant context for this request
        from mcp_server.auth import crypto

        tenant_key = crypto.derive_tenant_key(
            request.query_params.get("token")
            or request.headers.get("Authorization", "").replace("Bearer ", ""),
            str(tenant.salt),
        )
        set_tenant(str(tenant.id), tenant_key)

        logger.info(
            "MCP HTTP request received",
            method=mcp_request.method,
            tenant_id=tenant.id,
        )

        # Handle notifications (no response needed per JSON-RPC 2.0 spec)
        if mcp_request.method.startswith("notifications/"):
            logger.info("Received notification", method=mcp_request.method)
            # Notifications have no id and don't get responses
            return Response(status_code=204)  # No Content

        # Handle different MCP methods
        if mcp_request.method == "initialize":
            result = await handle_initialize(mcp_request.params or {}, tenant, db)
        elif mcp_request.method == "tools/list":
            result = await handle_list_tools(tenant, db)
        elif mcp_request.method == "tools/call":
            result = await handle_call_tool(mcp_request.params or {}, tenant, db)
        elif mcp_request.method == "prompts/list":
            result = {"prompts": []}  # No prompts supported yet
        elif mcp_request.method == "resources/list":
            result = {"resources": []}  # No resources supported yet
        else:
            return {
                "jsonrpc": "2.0",
                "id": mcp_request.id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {mcp_request.method}",
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": mcp_request.id,
            "result": result,
        }

    except Exception as e:
        logger.error(
            "MCP HTTP request failed",
            error=str(e),
            method=mcp_request.method,
        )
        return {
            "jsonrpc": "2.0",
            "id": mcp_request.id,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}",
            },
        }


async def handle_initialize(
    params: dict[str, Any], tenant: Tenant, db: Session
) -> dict[str, Any]:
    """Handle MCP initialize request."""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {},
            "prompts": {},
            "resources": {},
        },
        "serverInfo": {
            "name": "OrderDesk",
            "version": "0.1.0-alpha",
        },
    }


async def handle_list_tools(tenant: Tenant, db: Session) -> dict[str, Any]:
    """Handle MCP tools/list request."""
    from mcp_server.services.store import StoreService

    store_service = StoreService(db)
    stores = await store_service.list_stores(str(tenant.id))

    tools = [
        # Tenant tools
        {
            "name": "tenant_use_master_key",
            "description": "Authenticate with master key (already authenticated)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "master_key": {"type": "string", "description": "Master key"}
                },
                "required": ["master_key"],
            },
        },
        # Store tools
        {
            "name": "stores_list",
            "description": f"List all registered stores (you have {len(stores)} stores)",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "stores_register",
            "description": "Register a new OrderDesk store",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "OrderDesk store ID"},
                    "api_key": {"type": "string", "description": "OrderDesk API key"},
                    "store_name": {
                        "type": "string",
                        "description": "Friendly store name",
                    },
                    "label": {"type": "string", "description": "Optional label"},
                },
                "required": ["store_id", "api_key", "store_name"],
            },
        },
        {
            "name": "stores_use_store",
            "description": "Set active store for subsequent operations",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "identifier": {"type": "string", "description": "Store ID or name"},
                },
                "required": ["identifier"],
            },
        },
        {
            "name": "stores_resolve",
            "description": "Resolve store by ID or name",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "identifier": {"type": "string", "description": "Store ID or name"},
                },
                "required": ["identifier"],
            },
        },
        {
            "name": "stores_delete",
            "description": "Delete a store registration",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "store_identifier": {
                        "type": "string",
                        "description": "Store ID or name",
                    },
                },
                "required": ["store_identifier"],
            },
        },
        # Order tools
        {
            "name": "orders_list",
            "description": "List orders with advanced filtering (folder, customer, dates, etc.)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "store_identifier": {
                        "type": "string",
                        "description": "Store ID or name",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max orders to return (1-500)",
                    },
                    "offset": {"type": "integer", "description": "Pagination offset"},
                    "folder_name": {
                        "type": "string",
                        "description": "Filter by folder name",
                    },
                    "email": {
                        "type": "string",
                        "description": "Filter by customer email",
                    },
                    "search": {"type": "string", "description": "Search query"},
                },
            },
        },
        {
            "name": "orders_get",
            "description": "Get a single order by ID",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "OrderDesk order ID"},
                    "store_identifier": {
                        "type": "string",
                        "description": "Store ID or name",
                    },
                },
                "required": ["order_id"],
            },
        },
        {
            "name": "orders_update",
            "description": "Update an order with safe merge workflow",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "OrderDesk order ID"},
                    "changes": {
                        "type": "object",
                        "description": "Partial changes to apply (JSON object)",
                    },
                    "store_identifier": {
                        "type": "string",
                        "description": "Store ID or name",
                    },
                },
                "required": ["order_id", "changes"],
            },
        },
        # Product tools
        {
            "name": "products_list",
            "description": "List products/inventory items",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "store_identifier": {
                        "type": "string",
                        "description": "Store ID or name",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max products to return",
                    },
                    "search": {"type": "string", "description": "Search query"},
                },
            },
        },
        {
            "name": "products_get",
            "description": "Get a single product by ID",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Product ID"},
                    "store_identifier": {
                        "type": "string",
                        "description": "Store ID or name",
                    },
                },
                "required": ["product_id"],
            },
        },
    ]

    return {"tools": tools}


async def handle_call_tool(
    params: dict[str, Any], tenant: Tenant, db: Session
) -> dict[str, Any]:
    """Handle MCP tools/call request by bridging to FastAPI endpoints."""
    tool_name = params.get("name")
    tool_args = params.get("arguments", {})

    if not tool_name:
        raise ValueError("Missing tool name")

    logger.info(
        "MCP tool call",
        tool_name=tool_name,
        tenant_id=tenant.id,
    )

    # Bridge to existing FastAPI tool implementations
    try:
        if tool_name == "tenant_use_master_key":
            return {"content": [{"type": "text", "text": "Already authenticated"}]}

        elif tool_name == "stores_list":
            from mcp_server.routers.stores import list_stores_mcp

            result = await list_stores_mcp(db=db)
            return {"content": [{"type": "text", "text": str(result)}]}

        elif tool_name == "stores_register":
            from mcp_server.routers.stores import RegisterStoreParams, register_store

            params_obj = RegisterStoreParams(**tool_args)
            result = await register_store(params=params_obj, db=db)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Store '{result.get('store_name', 'unknown')}' registered successfully",
                    }
                ]
            }

        elif tool_name == "stores_use_store":
            from mcp_server.routers.stores import UseStoreParams, use_store

            params_obj = UseStoreParams(**tool_args)  # type: ignore[assignment]
            result = await use_store(params=params_obj, db=db)  # type: ignore[arg-type]
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Active store set to '{result.get('store_name', 'unknown')}'",
                    }
                ]
            }

        elif tool_name == "stores_resolve":
            from mcp_server.routers.stores import ResolveStoreParams, resolve_store

            resolve_params = ResolveStoreParams(**tool_args)
            result = await resolve_store(params=resolve_params, db=db)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Store resolved: {result.get('store_name', 'unknown')}",
                    }
                ]
            }

        elif tool_name == "stores_delete":
            from mcp_server.routers.stores import DeleteStoreParams, delete_store_mcp

            delete_params = DeleteStoreParams(**tool_args)
            result = await delete_store_mcp(params=delete_params, db=db)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Store '{result.get('store_name', 'unknown')}' deleted successfully",
                    }
                ]
            }

        elif tool_name == "orders_list":
            from mcp_server.routers.orders import ListOrdersParams, list_orders_mcp

            list_orders_params = ListOrdersParams(**tool_args)
            result = await list_orders_mcp(params=list_orders_params, db=db)
            return {"content": [{"type": "text", "text": str(result)}]}

        elif tool_name == "orders_get":
            from mcp_server.routers.orders import GetOrderParams, get_order_mcp

            get_order_params = GetOrderParams(**tool_args)
            result = await get_order_mcp(params=get_order_params, db=db)
            return {"content": [{"type": "text", "text": str(result)}]}

        elif tool_name == "orders_update":
            from mcp_server.routers.orders import UpdateOrderParams, update_order_mcp

            update_order_params = UpdateOrderParams(**tool_args)
            result = await update_order_mcp(params=update_order_params, db=db)
            order_id = result.get("order", {}).get(
                "id", tool_args.get("order_id", "unknown")
            )
            return {
                "content": [
                    {"type": "text", "text": f"Order {order_id} updated successfully"}
                ]
            }

        elif tool_name == "products_list":
            from mcp_server.routers.products import (
                ListProductsParams,
                list_products_mcp,
            )

            list_products_params = ListProductsParams(**tool_args)
            result = await list_products_mcp(params=list_products_params, db=db)
            return {"content": [{"type": "text", "text": str(result)}]}

        elif tool_name == "products_get":
            from mcp_server.routers.products import GetProductParams, get_product_mcp

            get_product_params = GetProductParams(**tool_args)
            result = await get_product_mcp(params=get_product_params, db=db)
            return {"content": [{"type": "text", "text": str(result)}]}

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    except Exception as e:
        logger.error("Tool execution failed", tool_name=tool_name, error=str(e))
        raise
