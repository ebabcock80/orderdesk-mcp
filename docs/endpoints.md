# API Endpoints Reference

This document provides a complete reference for all API endpoints in the OrderDesk MCP server.

## Base URL

All endpoints are relative to the server base URL. For local development:
```
http://localhost:8080
```

## Authentication

All endpoints (except `/health`, `/docs`, `/redoc`, `/openapi.json`) require authentication using a master key:

```bash
Authorization: Bearer <MASTER_KEY>
```

## Health Check

### GET /health

Health check endpoint for uptime monitors.

**Response:**
```json
{
  "status": "ok"
}
```

## Store Management

### POST /stores

Create a new store for the authenticated tenant.

**Request Body:**
```json
{
  "store_id": "string",
  "api_key": "string",
  "label": "string (optional)"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "store_id": "string",
  "label": "string",
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Errors:**
- `409 Conflict`: Store already exists for this tenant

### GET /stores

List all stores for the authenticated tenant.

**Response (200):**
```json
[
  {
    "id": "uuid",
    "store_id": "string",
    "label": "string",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### DELETE /stores/{store_id}

Delete a store.

**Response (204):** No content

**Errors:**
- `404 Not Found`: Store not found

## Order Management

### GET /stores/{store_id}/orders

List orders for a store with optional filters.

**Query Parameters:**
- `limit` (int, optional): Number of orders to return (1-100)
- `offset` (int, optional): Number of orders to skip
- `folder_id` (int, optional): Filter by folder ID
- `status` (string, optional): Filter by order status

**Response (200):**
```json
{
  "status": "success",
  "data": [
    {
      "id": "string",
      "email": "customer@example.com",
      "order_total": 29.99,
      "date_added": "2024-01-01T00:00:00Z",
      // ... other order fields
    }
  ]
}
```

### GET /stores/{store_id}/orders/{order_id}

Get a single order.

**Response (200):**
```json
{
  "id": "string",
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
      "id": "string",
      "name": "Product Name",
      "code": "PROD-001",
      "price": 29.99,
      "quantity": 1
    }
  ],
  // ... other order fields
}
```

### POST /stores/{store_id}/orders

Create a new order.

**Request Body:**
```json
{
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
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "id": "string",
    // ... created order data
  }
}
```

### PUT /stores/{store_id}/orders/{order_id}

Update an order (full object replacement).

**Request Body:** Complete order object

**Response (200):**
```json
{
  "status": "success",
  "data": {
    // ... updated order data
  }
}
```

### DELETE /stores/{store_id}/orders/{order_id}

Delete an order.

**Response (200):**
```json
{
  "status": "success",
  "message": "Order deleted"
}
```

## Order Mutations

### POST /stores/{store_id}/orders/{order_id}:mutate

Apply mutations to an order using the full update workflow.

**Request Body:**
```json
{
  "operations": [
    {
      "op": "replace",
      "path": "folder_id",
      "value": 456
    },
    {
      "op": "add",
      "path": "notes",
      "value": [{"note": "Updated by API", "type": "system"}]
    }
  ]
}
```

**Operations:**
- `replace`: Replace a field value
- `add`: Add a new field
- `remove`: Remove a field

**Response (200):**
```json
{
  "status": "success",
  "data": {
    // ... updated order data
  }
}
```

### POST /stores/{store_id}/orders/{order_id}/move-folder

Move an order to a different folder.

**Request Body:**
```json
{
  "folder_id": 456
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    // ... updated order data
  }
}
```

### POST /stores/{store_id}/orders/{order_id}/add-items

Add items to an order.

**Request Body:**
```json
{
  "items": [
    {
      "name": "Additional Product",
      "code": "PROD-002",
      "price": 19.99,
      "quantity": 2
    }
  ]
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    // ... updated order data
  }
}
```

### POST /stores/{store_id}/orders/{order_id}/update-address

Update an order's address.

**Request Body:**
```json
{
  "address_type": "shipping",
  "address": {
    "first_name": "Jane",
    "last_name": "Smith",
    "address1": "456 Oak Ave",
    "city": "Newtown",
    "state": "NY",
    "postal_code": "67890",
    "country": "US"
  }
}
```

**Address Types:**
- `shipping`: Shipping address
- `customer`: Customer address
- `return`: Return address

**Response (200):**
```json
{
  "status": "success",
  "data": {
    // ... updated order data
  }
}
```

### POST /stores/{store_id}/orders/{order_id}/add-note

Add a note to an order.

**Request Body:**
```json
{
  "note": "Customer requested expedited shipping",
  "note_type": "customer_service"
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    // ... updated order data
  }
}
```

## Inventory Management

### GET /stores/{store_id}/inventory

List inventory items for a store.

**Query Parameters:**
- `limit` (int, optional): Number of items to return (1-100)
- `offset` (int, optional): Number of items to skip
- `search` (string, optional): Search term

**Response (200):**
```json
{
  "status": "success",
  "data": [
    {
      "id": "string",
      "name": "Product Name",
      "code": "PROD-001",
      "price": 29.99,
      "stock": 100
    }
  ]
}
```

### GET /stores/{store_id}/inventory/{item_id}

Get a single inventory item.

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "id": "string",
    "name": "Product Name",
    "code": "PROD-001",
    "price": 29.99,
    "stock": 100,
    "variation_list": {
      "Color": "Red",
      "Size": "Large"
    },
    "metadata": {
      "image": "https://example.com/image.jpg"
    }
  }
}
```

### POST /stores/{store_id}/inventory

Create a new inventory item.

**Request Body:**
```json
{
  "name": "New Product",
  "code": "PROD-003",
  "price": 39.99,
  "stock": 100,
  "variation_list": {
    "Color": "Blue",
    "Size": "Medium"
  }
}
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "id": "string",
    // ... created item data
  }
}
```

### PUT /stores/{store_id}/inventory/{item_id}

Update an inventory item.

**Request Body:** Complete item object

**Response (200):**
```json
{
  "status": "success",
  "data": {
    // ... updated item data
  }
}
```

### DELETE /stores/{store_id}/inventory/{item_id}

Delete an inventory item.

**Response (200):**
```json
{
  "status": "success",
  "message": "Inventory item deleted"
}
```

## Webhooks

### POST /webhooks/orderdesk

Receive OrderDesk webhooks.

**Headers:**
- `X-OrderDesk-Signature` (optional): HMAC signature for validation

**Request Body:**
```json
{
  "event_id": "string",
  "event_type": "order_updated",
  "store_id": "string",
  "data": {
    // ... webhook data
  }
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Webhook processed successfully",
  "event_id": "string"
}
```

**Response (200) - Duplicate:**
```json
{
  "status": "duplicate",
  "message": "Event already processed"
}
```

## Metrics

### GET /metrics

Prometheus metrics endpoint.

**Response (200):**
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/health",status_code="200"} 1

# HELP http_request_duration_seconds HTTP request duration in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="GET",endpoint="/health",le="0.1"} 1
```

## Error Responses

All endpoints return consistent error responses:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": {
      // Additional error details
    },
    "request_id": "uuid"
  }
}
```

### Common Error Codes

- `AUTH_REQUIRED`: Missing or invalid authentication
- `STORE_NOT_FOUND`: Store not found or invalid credentials
- `OD_API_429`: OrderDesk API rate limit exceeded
- `OD_API_5XX`: OrderDesk API server error
- `CONCURRENT_UPDATE`: Order was modified concurrently
- `INVALID_MUTATION`: Invalid mutation operations
- `INTERNAL_SERVER_ERROR`: Internal server error

## Rate Limiting

The server implements rate limiting to prevent abuse:

- **Default Limit**: 120 requests per minute per tenant
- **Headers**: Rate limit information in response headers
- **429 Response**: When rate limit exceeded

## Caching

Responses are cached based on endpoint type:

- **Orders**: 15 seconds
- **Products**: 60 seconds
- **Customers**: 5 minutes
- **Store Settings**: 1 hour

Cache is automatically invalidated on writes.
