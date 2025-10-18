"""MCP Server implementation for OrderDesk API."""

import asyncio
import json
import logging
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from mcp_server.services.orderdesk import OrderDeskService
from mcp_server.utils.logging import logger

# Configure logging
logging.basicConfig(level=logging.INFO)

# Create MCP server instance
server = Server("orderdesk-mcp")

# Initialize OrderDesk service
orderdesk_service = OrderDeskService()


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="health_check",
            description="Check the health status of the OrderDesk server",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="list_stores",
            description="List all stores (simplified - no tenant system)",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="create_store",
            description="Create a new store with OrderDesk credentials",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {
                        "type": "string",
                        "description": "Unique identifier for the store",
                    },
                    "api_key": {
                        "type": "string",
                        "description": "OrderDesk API key for the store",
                    },
                    "name": {
                        "type": "string",
                        "description": "Display name for the store",
                    },
                },
                "required": ["store_id", "api_key", "name"],
            },
        ),
        types.Tool(
            name="delete_store",
            description="Delete a store by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {
                        "type": "string",
                        "description": "ID of the store to delete",
                    },
                    "api_key": {
                        "type": "string",
                        "description": "OrderDesk API key for the store",
                    },
                },
                "required": ["store_id", "api_key"],
            },
        ),
        types.Tool(
            name="list_orders",
            description="List orders for a specific store",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "ID of the store"},
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of orders to return",
                        "default": 50,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of orders to skip",
                        "default": 0,
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by order status",
                    },
                    "folder_id": {
                        "type": "string",
                        "description": "Filter by folder ID",
                    },
                },
                "required": ["store_id", "api_key"],
            },
        ),
        types.Tool(
            name="get_order",
            description="Get a specific order by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "ID of the store"},
                    "order_id": {"type": "string", "description": "ID of the order"},
                },
                "required": ["store_id", "api_key", "order_id"],
            },
        ),
        types.Tool(
            name="create_order",
            description="Create a new order",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "ID of the store"},
                    "order_data": {
                        "type": "object",
                        "description": "Order data to create",
                    },
                },
                "required": ["store_id", "api_key", "order_data"],
            },
        ),
        types.Tool(
            name="update_order",
            description="Update an existing order",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "ID of the store"},
                    "order_id": {"type": "string", "description": "ID of the order"},
                    "order_data": {
                        "type": "object",
                        "description": "Updated order data",
                    },
                },
                "required": ["store_id", "api_key", "order_id", "order_data"],
            },
        ),
        types.Tool(
            name="delete_order",
            description="Delete an order by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "ID of the store"},
                    "order_id": {"type": "string", "description": "ID of the order"},
                },
                "required": ["store_id", "api_key", "order_id"],
            },
        ),
        types.Tool(
            name="mutate_order",
            description="Mutate an order using the full order update workflow",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "ID of the store"},
                    "order_id": {"type": "string", "description": "ID of the order"},
                    "mutator": {
                        "type": "string",
                        "description": "Description of the mutation to perform",
                    },
                },
                "required": ["store_id", "api_key", "order_id", "mutator"],
            },
        ),
        types.Tool(
            name="list_products",
            description="List products for a store",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "ID of the store"},
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of products to return",
                        "default": 50,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of products to skip",
                        "default": 0,
                    },
                    "search": {
                        "type": "string",
                        "description": "Search term for products",
                    },
                },
                "required": ["store_id", "api_key"],
            },
        ),
        types.Tool(
            name="get_product",
            description="Get a specific product by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "ID of the store"},
                    "product_id": {
                        "type": "string",
                        "description": "ID of the product",
                    },
                },
                "required": ["store_id", "api_key", "product_id"],
            },
        ),
        types.Tool(
            name="list_customers",
            description="List customers for a store",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "ID of the store"},
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of customers to return",
                        "default": 50,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of customers to skip",
                        "default": 0,
                    },
                    "search": {
                        "type": "string",
                        "description": "Search term for customers",
                    },
                },
                "required": ["store_id", "api_key"],
            },
        ),
        types.Tool(
            name="get_customer",
            description="Get a specific customer by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "ID of the store"},
                    "customer_id": {
                        "type": "string",
                        "description": "ID of the customer",
                    },
                },
                "required": ["store_id", "api_key", "customer_id"],
            },
        ),
        types.Tool(
            name="list_folders",
            description="List all folders for a store",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "ID of the store"},
                    "api_key": {
                        "type": "string",
                        "description": "OrderDesk API key for the store",
                    },
                },
                "required": ["store_id", "api_key"],
            },
        ),
        types.Tool(
            name="create_folder",
            description="Create a new folder",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "ID of the store"},
                    "name": {"type": "string", "description": "Name of the folder"},
                    "description": {
                        "type": "string",
                        "description": "Description of the folder",
                    },
                },
                "required": ["store_id", "api_key", "name"],
            },
        ),
        types.Tool(
            name="list_webhooks",
            description="List webhooks for a store",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "ID of the store"}
                },
                "required": ["store_id", "api_key"],
            },
        ),
        types.Tool(
            name="create_webhook",
            description="Create a new webhook",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "ID of the store"},
                    "url": {"type": "string", "description": "Webhook URL"},
                    "events": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Events to listen for",
                    },
                    "secret": {
                        "type": "string",
                        "description": "Webhook secret for validation",
                    },
                },
                "required": ["store_id", "api_key", "url", "events"],
            },
        ),
        types.Tool(
            name="get_reports",
            description="Get reports for a store",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "ID of the store"},
                    "type": {
                        "type": "string",
                        "description": "Type of report to generate",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date for the report (YYYY-MM-DD)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date for the report (YYYY-MM-DD)",
                    },
                },
                "required": ["store_id", "api_key"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    """Handle tool calls."""
    try:
        logger.info(f"Tool called: {name} with arguments: {arguments}")

        # OrderDesk API doesn't use tenant_id - we'll use the store_id directly
        # The tenant_id concept was from our multi-tenant architecture, but OrderDesk is simpler

        if name == "health_check":
            result = {"status": "ok", "message": "OrderDesk MCP Server is healthy"}

        elif name == "list_stores":
            # For now, return a simple response since we don't have a tenant system
            result = {
                "stores": [],
                "message": "No tenant system - use create_store to add a store",
            }

        elif name == "create_store":
            # Store the store credentials directly without tenant system
            result = await orderdesk_service.create_store_simple(
                arguments["store_id"], arguments["api_key"], arguments["name"]
            )

        elif name == "delete_store":
            result = {"message": "Store deletion not implemented in simplified mode"}

        elif name == "list_orders":
            result = await orderdesk_service.list_orders_direct(
                arguments["store_id"],
                arguments["api_key"],
                limit=arguments.get("limit", 50),
                offset=arguments.get("offset", 0),
                status=arguments.get("status"),
                folder_id=arguments.get("folder_id"),
            )

        elif name == "get_order":
            result = await orderdesk_service.get_order_direct(
                arguments["store_id"], arguments["api_key"], arguments["order_id"]
            )

        elif name == "create_order":
            result = await orderdesk_service.create_order_direct(
                arguments["store_id"], arguments["api_key"], arguments["order_data"]
            )

        elif name == "update_order":
            result = await orderdesk_service.update_order_direct(
                arguments["store_id"],
                arguments["api_key"],
                arguments["order_id"],
                arguments["order_data"],
            )

        elif name == "delete_order":
            result = await orderdesk_service.delete_order_direct(
                arguments["store_id"], arguments["api_key"], arguments["order_id"]
            )

        elif name == "mutate_order":
            result = await orderdesk_service.mutate_order_direct(
                arguments["store_id"],
                arguments["api_key"],
                arguments["order_id"],
                arguments["mutator"],
            )

        elif name == "list_products":
            result = await orderdesk_service.list_products_direct(
                arguments["store_id"],
                arguments["api_key"],
                search=arguments.get("search"),
                limit=arguments.get("limit", 50),
                offset=arguments.get("offset", 0),
            )

        elif name == "get_product":
            result = await orderdesk_service.get_product_direct(
                arguments["store_id"], arguments["api_key"], arguments["product_id"]
            )

        elif name == "list_customers":
            result = await orderdesk_service.list_customers_direct(
                arguments["store_id"],
                arguments["api_key"],
                search=arguments.get("search"),
                limit=arguments.get("limit", 50),
                offset=arguments.get("offset", 0),
            )

        elif name == "get_customer":
            result = await orderdesk_service.get_customer_direct(
                arguments["store_id"], arguments["api_key"], arguments["customer_id"]
            )

        elif name == "list_folders":
            result = await orderdesk_service.list_folders_direct(
                arguments["store_id"], arguments["api_key"]
            )

        elif name == "create_folder":
            result = await orderdesk_service.create_folder_direct(
                arguments["store_id"],
                arguments["api_key"],
                arguments["name"],
                arguments.get("description"),
            )

        elif name == "list_webhooks":
            result = await orderdesk_service.list_webhooks_direct(
                arguments["store_id"], arguments["api_key"]
            )

        elif name == "create_webhook":
            result = await orderdesk_service.create_webhook_direct(
                arguments["store_id"],
                arguments["api_key"],
                arguments["url"],
                arguments["events"],
                arguments.get("secret"),
            )

        elif name == "get_reports":
            result = await orderdesk_service.get_reports_direct(
                arguments["store_id"],
                arguments["api_key"],
                arguments.get("type"),
                arguments.get("start_date"),
                arguments.get("end_date"),
            )

        else:
            result = {"error": f"Unknown tool: {name}"}

        # Return plain JSON string that Claude can parse
        return [
            types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))
        ]

    except Exception as e:
        logger.error(f"Error calling tool {name}: {str(e)}")
        return [
            types.TextContent(
                type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False)
            )
        ]


async def main():
    """Main entry point for the MCP server."""
    logger.info("Starting OrderDesk MCP Server")

    # Initialize database tables
    try:
        from mcp_server.models.database import create_tables

        create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise

    # Run the server using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        # Create a simple notification options object with tools_changed attribute

        # Create a custom notification options object
        class CustomNotificationOptions:
            def __init__(self):
                self.tools_changed = False

        notification_options = CustomNotificationOptions()

        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="orderdesk-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=notification_options,
                    experimental_capabilities=None,
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
