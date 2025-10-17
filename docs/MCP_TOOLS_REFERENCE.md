# OrderDesk MCP Tools Reference

This document provides a comprehensive reference for all available MCP tools in the OrderDesk MCP Server.

## Table of Contents

1. [Store Management](#store-management)
2. [Order Operations](#order-operations)
3. [Product Management](#product-management)
4. [Customer Operations](#customer-operations)
5. [Folder Management](#folder-management)
6. [Webhooks & Reports](#webhooks--reports)
7. [System Tools](#system-tools)

## Store Management

### create_store
Add a new OrderDesk store with credentials.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key
- `name` (string, required): Store name/label

**Example:**
```json
{
  "tool": "create_store",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456",
    "name": "My Store"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Store 'My Store' (42174) created successfully",
  "store_id": "42174"
}
```

### list_stores
List all configured OrderDesk stores.

**Parameters:** None

**Example:**
```json
{
  "tool": "list_stores",
  "arguments": {}
}
```

### delete_store
Remove a store configuration.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID

**Example:**
```json
{
  "tool": "delete_store",
  "arguments": {
    "store_id": "42174"
  }
}
```

## Order Operations

### list_orders
List orders from OrderDesk with optional filtering.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key
- `limit` (integer, optional): Maximum number of orders (default: 50)
- `offset` (integer, optional): Number of orders to skip (default: 0)
- `status` (string, optional): Filter by order status
- `folder_id` (integer, optional): Filter by folder ID

**Example:**
```json
{
  "tool": "list_orders",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456",
    "limit": 25,
    "status": "pending"
  }
}
```

### get_order
Get detailed information about a specific order.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key
- `order_id` (integer, required): Order ID to retrieve

**Example:**
```json
{
  "tool": "get_order",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456",
    "order_id": 12345
  }
}
```

### create_order
Create a new order in OrderDesk.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key
- `order_data` (object, required): Order data to create

**Example:**
```json
{
  "tool": "create_order",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456",
    "order_data": {
      "email": "customer@example.com",
      "shipping": {
        "first_name": "John",
        "last_name": "Doe",
        "address1": "123 Main St",
        "city": "Anytown",
        "state": "CA",
        "postal_code": "12345",
        "country": "US"
      },
      "items": [
        {
          "name": "Product Name",
          "code": "PROD-001",
          "price": 29.99,
          "quantity": 1
        }
      ]
    }
  }
}
```

### update_order
Update an existing order (safely merges with existing data).

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key
- `order_id` (integer, required): Order ID to update
- `order_data` (object, required): Order data to update

**Example:**
```json
{
  "tool": "update_order",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456",
    "order_id": 12345,
    "order_data": {
      "status": "shipped",
      "tracking_number": "1Z999AA1234567890"
    }
  }
}
```

**Note:** This tool automatically fetches the complete order first, merges your changes, and sends the full updated order back to prevent data loss.

### delete_order
Delete an order from OrderDesk.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key
- `order_id` (integer, required): Order ID to delete

**Example:**
```json
{
  "tool": "delete_order",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456",
    "order_id": 12345
  }
}
```

### mutate_order
Safely mutate an order by fetching, modifying, and updating.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key
- `order_id` (integer, required): Order ID to mutate
- `mutator` (string, required): Description of the mutation to perform

**Example:**
```json
{
  "tool": "mutate_order",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456",
    "order_id": 12345,
    "mutator": "Add tracking number 1Z999AA1234567890 and update status to shipped"
  }
}
```

## Product Management

### list_products
List products from OrderDesk catalog.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key
- `search` (string, optional): Search term for products
- `limit` (integer, optional): Maximum number of products (default: 50)
- `offset` (integer, optional): Number of products to skip (default: 0)

**Example:**
```json
{
  "tool": "list_products",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456",
    "search": "widget",
    "limit": 25
  }
}
```

### get_product
Get detailed information about a specific product.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key
- `product_id` (integer, required): Product ID to retrieve

**Example:**
```json
{
  "tool": "get_product",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456",
    "product_id": 5678
  }
}
```

## Customer Operations

### list_customers
List customers from OrderDesk.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key
- `search` (string, optional): Search term for customers
- `limit` (integer, optional): Maximum number of customers (default: 50)
- `offset` (integer, optional): Number of customers to skip (default: 0)

**Example:**
```json
{
  "tool": "list_customers",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456",
    "search": "john@example.com",
    "limit": 25
  }
}
```

### get_customer
Get detailed information about a specific customer.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key
- `customer_id` (integer, required): Customer ID to retrieve

**Example:**
```json
{
  "tool": "get_customer",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456",
    "customer_id": 999
  }
}
```

## Folder Management

### list_folders
List order folders from OrderDesk.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key

**Example:**
```json
{
  "tool": "list_folders",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456"
  }
}
```

### create_folder
Create a new order folder in OrderDesk.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key
- `name` (string, required): Folder name
- `description` (string, optional): Folder description

**Example:**
```json
{
  "tool": "create_folder",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456",
    "name": "Priority Orders",
    "description": "High priority orders requiring immediate attention"
  }
}
```

## Webhooks & Reports

### list_webhooks
List configured webhooks from OrderDesk.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key

**Example:**
```json
{
  "tool": "list_webhooks",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456"
  }
}
```

### create_webhook
Create a new webhook in OrderDesk.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key
- `url` (string, required): Webhook URL
- `events` (array, required): List of events to subscribe to
- `secret` (string, optional): Webhook secret for validation

**Example:**
```json
{
  "tool": "create_webhook",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456",
    "url": "https://your-app.com/webhooks/orderdesk",
    "events": ["order.created", "order.updated"],
    "secret": "your-webhook-secret"
  }
}
```

### get_reports
Generate reports from OrderDesk.

**Parameters:**
- `store_id` (string, required): OrderDesk store ID
- `api_key` (string, required): OrderDesk API key
- `report_type` (string, required): Type of report to generate
- `start_date` (string, optional): Start date (YYYY-MM-DD)
- `end_date` (string, optional): End date (YYYY-MM-DD)

**Example:**
```json
{
  "tool": "get_reports",
  "arguments": {
    "store_id": "42174",
    "api_key": "abc123def456",
    "report_type": "sales",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }
}
```

## System Tools

### health_check
Check the health status of the OrderDesk MCP server.

**Parameters:** None

**Example:**
```json
{
  "tool": "health_check",
  "arguments": {}
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "OrderDesk MCP Server is healthy"
}
```

## Error Handling

All tools return consistent error responses:

```json
{
  "error": "Error description"
}
```

Common error types:
- **Authentication errors**: Invalid store_id or api_key
- **Not found errors**: Resource doesn't exist
- **Validation errors**: Invalid parameters
- **Server errors**: OrderDesk API issues

## Best Practices

1. **Always use update_order for modifications**: It safely merges changes
2. **Use appropriate limits**: Don't request too many records at once
3. **Handle errors gracefully**: Check for error responses
4. **Store credentials securely**: Use the create_store tool to store them
5. **Test with health_check**: Verify server connectivity first

## Rate Limiting

The server implements automatic retry logic with exponential backoff for:
- 429 (Too Many Requests)
- 500, 502, 503, 504 (Server Errors)

Retry delays: 250ms → 1s → 2s (with jitter)
