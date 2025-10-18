# HTTP MCP Endpoint Guide

## Overview

The OrderDesk MCP Server provides an HTTP endpoint for remote MCP client connections. This enables AI assistants like Claude Desktop and ChatGPT to access your OrderDesk data from anywhere.

**Endpoint:** `POST /mcp`  
**Authentication:** Via `Authorization: Bearer TOKEN` header or `?token=TOKEN` query parameter  
**Protocol:** JSON-RPC 2.0 with MCP extensions  
**Compatible With:** Claude Desktop, ChatGPT, any MCP client

---

## Quick Setup

### 1. Deploy the Server

```bash
# Using Docker Compose (recommended)
docker-compose up -d

# Server will be available at http://localhost:8080
```

### 2. Get Your MCP Configuration

1. Open the WebUI: `http://localhost:8080/webui`
2. Login with your master key
3. Go to **Settings** page
4. Enter your master key in the input field
5. Copy the generated MCP configuration JSON

### 3. Connect Claude Desktop

Paste the configuration into:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "OrderDesk": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://localhost:8080/mcp?token=YOUR_MASTER_KEY_HERE"
      ]
    }
  }
}
```

### 4. Restart Claude Desktop

Close and reopen Claude Desktop. The OrderDesk tools will now be available!

---

## MCP Protocol Methods

The HTTP endpoint supports all standard MCP protocol methods:

### initialize
Negotiate protocol version and capabilities.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 0,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "claude-ai",
      "version": "1.0.0"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 0,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {}
    },
    "serverInfo": {
      "name": "OrderDesk",
      "version": "0.1.0-alpha"
    }
  }
}
```

### tools/list
Get list of available tools.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "stores_list",
        "description": "List all registered stores (you have 2 stores)",
        "inputSchema": {...}
      },
      // ... 10 more tools
    ]
  }
}
```

### tools/call
Execute a tool with parameters.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "orders_list",
    "arguments": {
      "store_identifier": "DR",
      "limit": 10
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{'orders': [...], 'total': 10, ...}"
      }
    ]
  }
}
```

### prompts/list
List available prompts (currently empty).

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "prompts": []
  }
}
```

### resources/list
List available resources (currently empty).

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "resources": []
  }
}
```

### notifications/*
Client notifications (acknowledged with 204 No Content).

**Example:** `notifications/initialized`

---

## Available Tools

All tools use the `service_method` naming format (e.g., `stores_list`, `orders_update`).

### Tenant & Store Management (6)
1. `tenant_use_master_key` - Authenticate (already authenticated via HTTP)
2. `stores_list` - List all registered stores
3. `stores_register` - Register new OrderDesk store
4. `stores_use_store` - Set active store for session
5. `stores_resolve` - Resolve store by ID or name
6. `stores_delete` - Delete store registration

### Order Operations (3)
7. `orders_list` - List orders with advanced filtering
8. `orders_get` - Get single order by ID
9. `orders_update` - Update order with smart merge workflow

### Product Operations (2)
10. `products_list` - List products/inventory items
11. `products_get` - Get single product by ID

---

## Authentication

### Via Query Parameter (Recommended)
```bash
curl -X POST "http://localhost:8080/mcp?token=YOUR_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

### Via Authorization Header
```bash
curl -X POST "http://localhost:8080/mcp" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_MASTER_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

---

## Smart Order Merge Workflow

The `orders_update` tool implements an intelligent merge workflow:

### How It Works

1. **Fetch**: Server retrieves current order from OrderDesk
2. **Merge**: Intelligently combines changes with existing data
   - Appends notes instead of replacing
   - Deduplicates based on content (case-insensitive)
   - Preserves all existing fields
3. **Upload**: Sends complete merged order to OrderDesk
4. **Retry**: Automatic retry on conflicts (up to 5 attempts)

### Example: Adding a Note

**Your Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "orders_update",
    "arguments": {
      "order_id": "342635621",
      "store_identifier": "DR",
      "changes": {
        "order_notes": [
          {
            "content": "Customer requested gift wrap",
            "username": "AI Assistant"
          }
        ]
      }
    }
  }
}
```

**What Happens:**
1. Server fetches order 342635621 (with existing notes)
2. Checks if "Customer requested gift wrap" already exists (case-insensitive)
3. If not a duplicate, appends the new note to existing notes
4. Sends complete order with all notes back to OrderDesk
5. Returns success with order ID

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Order 342635621 updated successfully"
      }
    ]
  }
}
```

### Deduplication Rules

- **Case-insensitive**: "Gift Wrap" = "gift wrap" = "GIFT WRAP"
- **Whitespace-trimmed**: "  Note  " = "Note"
- **Content-based**: Compares actual note text
- **Preserves original**: Keeps first occurrence, skips duplicates

---

## Advanced Filtering

The `orders_list` tool supports 20+ filter parameters:

```json
{
  "name": "orders_list",
  "arguments": {
    "store_identifier": "DR",
    "limit": 50,
    "folder_name": "Pending Orders",
    "email": "customer@example.com",
    "search_start_date": "2025-01-01",
    "search_end_date": "2025-12-31",
    "customer_first_name": "John",
    "customer_last_name": "Smith",
    "status": "pending",
    "order_by": "date_added",
    "order": "desc"
  }
}
```

**Available Parameters:**
- `folder_id`, `folder_name` - Filter by folder
- `source_id`, `source_name` - Filter by order source
- `search_start_date`, `search_end_date` - Date range for order creation
- `modified_start_date`, `modified_end_date` - Date range for modifications
- `email`, `customer_id` - Customer filters
- `customer_first_name`, `customer_last_name`, `customer_company`, `customer_phone` - Customer details
- `shipping_first_name`, `shipping_last_name`, `shipping_company`, `shipping_phone` - Shipping details
- `order_by` - Sort field (e.g., "date_added", "order_total")
- `order` - Sort direction ("asc" or "desc")
- `status` - Order status filter
- `search` - General search query

---

## Error Handling

### Authentication Errors
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32001,
    "message": "Authentication failed: Invalid master key"
  }
}
```

### Validation Errors
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32002,
    "message": "No store specified and no active store set"
  }
}
```

### Not Found Errors
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "error": {
    "code": -32003,
    "message": "Order 123456 not found"
  }
}
```

---

## Testing

### Manual Testing
Use the included test script:
```bash
./test_mcp_endpoints.sh
```

### Example cURL Commands

**List Tools:**
```bash
curl -X POST "http://localhost:8080/mcp?token=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

**List Stores:**
```bash
curl -X POST "http://localhost:8080/mcp?token=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":2,
    "method":"tools/call",
    "params":{"name":"stores_list","arguments":{}}
  }'
```

**List Orders:**
```bash
curl -X POST "http://localhost:8080/mcp?token=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":3,
    "method":"tools/call",
    "params":{
      "name":"orders_list",
      "arguments":{"store_identifier":"DR","limit":10}
    }
  }'
```

---

## Production Deployment

### Environment Variables

```bash
# Required
MCP_KMS_KEY=your-encryption-key-here  # 32+ bytes, base64 encoded
PUBLIC_URL=https://your-domain.com    # For MCP config generation

# Optional
ENABLE_WEBUI=true                     # Enable web admin interface
LOG_LEVEL=info                        # Logging verbosity
CACHE_BACKEND=memory                  # memory, sqlite, or redis
```

### Docker Compose Example

```yaml
version: '3.8'
services:
  mcp:
    image: orderdesk-mcp:latest
    ports:
      - "8080:8080"
    environment:
      - MCP_KMS_KEY=${MCP_KMS_KEY}
      - PUBLIC_URL=https://your-domain.com
      - ENABLE_WEBUI=true
      - LOG_LEVEL=info
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

### nginx Reverse Proxy

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Important: Don't timeout MCP connections
    proxy_read_timeout 300s;
    proxy_connect_timeout 75s;
}
```

---

## Troubleshooting

### Claude Desktop Can't Connect

1. **Check server is running:**
   ```bash
   curl http://localhost:8080/health
   ```

2. **Verify MCP endpoint:**
   ```bash
   curl -X POST "http://localhost:8080/mcp?token=YOUR_KEY" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
   ```

3. **Check Claude logs:**
   - macOS: `~/Library/Logs/Claude/mcp*.log`
   - Look for connection errors or authentication failures

4. **Verify configuration format:**
   - Must be valid JSON
   - `npx mcp-remote` requires the full URL with token
   - Server must be accessible from your machine

### Tool Execution Fails

1. **Check authentication:**
   - Master key must match server configuration
   - Token parameter or Authorization header must be present

2. **Verify store setup:**
   - At least one store must be registered
   - Store credentials must be valid
   - Use `stores_list` to verify stores are registered

3. **Check server logs:**
   ```bash
   docker-compose logs -f mcp
   ```

### Duplicate Notes Appearing

This should no longer happen! The server now deduplicates notes automatically.

If you see duplicates:
1. Check the note content (must match exactly, case-insensitive)
2. Verify you're using the latest server version
3. Check logs for "Skipping duplicate note" messages

---

## Performance

### Caching Strategy

- **Orders:** 15-second TTL (fast-changing data)
- **Products:** 60-second TTL (slower-changing data)
- **Store Config:** 1-hour TTL (rarely changes)

### Response Times

- **Cached:** <50ms
- **Uncached:** 500-2000ms (depends on OrderDesk API)
- **With Retry:** Up to 15s (5 retry attempts)

### Rate Limits

- **MCP Endpoint:** No rate limiting (authenticated users only)
- **OrderDesk API:** Respects OrderDesk's rate limits
- **Auto-Retry:** Handles 429 responses with exponential backoff

---

## Security

### Authentication Methods

1. **Query Parameter (Recommended for mcp-remote):**
   ```
   http://your-server.com/mcp?token=YOUR_MASTER_KEY
   ```

2. **Authorization Header:**
   ```
   Authorization: Bearer YOUR_MASTER_KEY
   ```

### Security Features

- ✅ Master key authentication required
- ✅ Per-tenant encryption (AES-256-GCM)
- ✅ Audit logging for all operations
- ✅ Tenant isolation (database-enforced)
- ✅ Secret redaction in logs
- ✅ CSRF protection (for WebUI)

### Production Recommendations

1. **Use HTTPS**: Deploy behind nginx with SSL/TLS
2. **Rotate Keys**: Periodically rotate master keys
3. **Monitor Logs**: Watch for authentication failures
4. **Backup Database**: Regular backups of `data/app.db`
5. **Firewall**: Restrict access to trusted IPs if possible

---

## Examples

### Adding a Store

```bash
curl -X POST "http://localhost:8080/mcp?token=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"tools/call",
    "params":{
      "name":"stores_register",
      "arguments":{
        "store_id":"42174",
        "api_key":"your-orderdesk-api-key",
        "store_name":"My OrderDesk Store"
      }
    }
  }'
```

### Listing Orders

```bash
curl -X POST "http://localhost:8080/mcp?token=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":2,
    "method":"tools/call",
    "params":{
      "name":"orders_list",
      "arguments":{
        "store_identifier":"My OrderDesk Store",
        "limit":10,
        "folder_name":"Pending Orders"
      }
    }
  }'
```

### Updating an Order (Adding a Note)

```bash
curl -X POST "http://localhost:8080/mcp?token=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":3,
    "method":"tools/call",
    "params":{
      "name":"orders_update",
      "arguments":{
        "order_id":"342635621",
        "store_identifier":"DR",
        "changes":{
          "order_notes":[
            {
              "content":"Customer requested expedited shipping",
              "username":"Support Team"
            }
          ]
        }
      }
    }
  }'
```

### Listing Products

```bash
curl -X POST "http://localhost:8080/mcp?token=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":4,
    "method":"tools/call",
    "params":{
      "name":"products_list",
      "arguments":{
        "store_identifier":"DR",
        "limit":20,
        "search":"widget"
      }
    }
  }'
```

---

## Links

- **GitHub Repository:** https://github.com/ebabcock80/orderdesk-mcp
- **CI Status:** See [CI_STATUS.md](../CI_STATUS.md)
- **Testing Guide:** See [TESTING_SUMMARY.md](../TESTING_SUMMARY.md)
- **MCP Specification:** https://spec.modelcontextprotocol.io/
- **OrderDesk API:** https://app.orderdesk.me/api-docs

