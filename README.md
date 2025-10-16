# OrderDesk MCP Multi-Tenant API Gateway

A multi-tenant REST API gateway for OrderDesk with master key authentication, designed to work with or without Cloudflare. This server provides a secure, scalable way to manage multiple OrderDesk stores through a single API endpoint.

## Features

- **Multi-tenant Architecture**: Each master key represents a tenant with multiple OrderDesk stores
- **Master Key Authentication**: Secure authentication using bearer tokens
- **Full Order Mutation Workflow**: Fetch → Mutate → Full Update with concurrency safety
- **Encrypted Storage**: Store API keys encrypted with per-tenant derived keys
- **Multi-backend Caching**: Memory, SQLite, or Redis caching with TTL
- **Proxy Support**: Works with Cloudflare Tunnel, reverse proxies, or direct deployment
- **Structured Logging**: JSON logs with correlation IDs and request tracking
- **Prometheus Metrics**: Built-in metrics endpoint for monitoring
- **Docker Ready**: Multi-stage Docker build with health checks

## Quick Start

### Using Docker Compose

1. **Clone and setup**:
   ```bash
   git clone https://github.com/ebabcock80/orderdesk-mcp.git
   cd orderdesk-mcp
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Generate encryption key**:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   # Add the output to MCP_KMS_KEY in .env
   ```

4. **Start the server**:
   ```bash
   docker-compose up -d
   ```

5. **Verify health**:
   ```bash
   curl http://localhost:8080/health
   ```

### Using Cloudflare Tunnel

If you have an existing Cloudflare Tunnel configured:

```bash
# Get container IP
docker inspect orderdesk-mcp-mcp-1 | grep IPAddress

# Route traffic through tunnel
cloudflared tunnel route ip <container_ip> <port>
```

## Architecture

### Multi-Tenancy Model

- **Master Key**: Each tenant has a unique master key for authentication
- **Stores**: Each tenant can register multiple OrderDesk stores
- **Encryption**: API keys are encrypted using per-tenant derived keys
- **Isolation**: Complete data isolation between tenants

### Full Order Update Workflow

OrderDesk requires complete order objects for updates. This server implements:

1. **Fetch**: Retrieve current order from OrderDesk
2. **Mutate**: Apply changes to a copy in memory
3. **Update**: Upload the complete modified order object
4. **Retry**: Handle concurrent updates with exponential backoff

## API Reference

### Authentication

All requests require a master key in the Authorization header:

```bash
Authorization: Bearer <MASTER_KEY>
```

### Store Management

#### Create Store
```bash
POST /stores
Content-Type: application/json

{
  "store_id": "your-store-id",
  "api_key": "your-api-key",
  "label": "My Store"
}
```

#### List Stores
```bash
GET /stores
```

#### Delete Store
```bash
DELETE /stores/{store_id}
```

### Order Operations

#### List Orders
```bash
GET /stores/{store_id}/orders?limit=50&folder_id=123
```

#### Get Order
```bash
GET /stores/{store_id}/orders/{order_id}
```

#### Create Order
```bash
POST /stores/{store_id}/orders
Content-Type: application/json

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

#### Update Order (Full Object)
```bash
PUT /stores/{store_id}/orders/{order_id}
Content-Type: application/json

{
  # Complete order object
}
```

### Order Mutations

#### Generic Mutation
```bash
POST /stores/{store_id}/orders/{order_id}:mutate
Content-Type: application/json

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

#### Move to Folder
```bash
POST /stores/{store_id}/orders/{order_id}/move-folder
Content-Type: application/json

{
  "folder_id": 456
}
```

#### Add Items
```bash
POST /stores/{store_id}/orders/{order_id}/add-items
Content-Type: application/json

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

#### Update Address
```bash
POST /stores/{store_id}/orders/{order_id}/update-address
Content-Type: application/json

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

#### Add Note
```bash
POST /stores/{store_id}/orders/{order_id}/add-note
Content-Type: application/json

{
  "note": "Customer requested expedited shipping",
  "note_type": "customer_service"
}
```

### Inventory Management

#### List Inventory
```bash
GET /stores/{store_id}/inventory?limit=50&search=widget
```

#### Get Inventory Item
```bash
GET /stores/{store_id}/inventory/{item_id}
```

#### Create Inventory Item
```bash
POST /stores/{store_id}/inventory
Content-Type: application/json

{
  "name": "New Product",
  "code": "PROD-003",
  "price": 39.99,
  "stock": 100
}
```

#### Update Inventory Item
```bash
PUT /stores/{store_id}/inventory/{item_id}
Content-Type: application/json

{
  "name": "Updated Product Name",
  "price": 44.99,
  "stock": 75
}
```

#### Delete Inventory Item
```bash
DELETE /stores/{store_id}/inventory/{item_id}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | `8080` |
| `TRUST_PROXY` | Trust proxy headers | `true` |
| `LOG_LEVEL` | Logging level | `info` |
| `MCP_KMS_KEY` | 32+ byte base64 encryption key | **Required** |
| `AUTO_PROVISION_TENANT` | Auto-create tenants | `true` |
| `RATE_LIMIT_RPM` | Rate limit per minute | `120` |
| `CACHE_BACKEND` | Cache backend (memory/sqlite/redis) | `memory` |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `WEBHOOK_SECRET` | Webhook validation secret | Optional |
| `ALLOWED_ORIGINS` | CORS allowed origins | Empty |
| `DATABASE_URL` | Database connection URL | `sqlite:///data/app.db` |

### Cache Configuration

- **Memory**: Fast, but lost on restart
- **SQLite**: Persistent, good for single instance
- **Redis**: Distributed, good for multiple instances

### TTL Settings

- Orders: 15 seconds
- Products: 60 seconds
- Customers: 5 minutes
- Store settings: 1 hour

## Monitoring

### Health Check
```bash
GET /health
```

### Metrics
```bash
GET /metrics
```

### Logs
Structured JSON logs include:
- Request/response details
- Tenant and store IDs
- Duration and status codes
- Correlation IDs
- Client IP addresses

## Security

- **Encryption**: All API keys encrypted with per-tenant derived keys
- **Authentication**: Master key validation with Argon2 hashing
- **Headers**: Security headers (HSTS, XSS protection, etc.)
- **CORS**: Configurable origin restrictions
- **Rate Limiting**: Built-in rate limiting
- **Audit Logs**: All tenant actions logged

## Development

### Setup
```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with hot reload
uvicorn mcp_server.main:app --reload
```

### Testing
```bash
# Unit tests
pytest tests/

# Integration tests (requires test credentials)
ORDERDESK_TEST_STORE_ID=xxx ORDERDESK_TEST_API_KEY=xxx pytest tests/test_integration.py
```

## Troubleshooting

### Common Issues

1. **Invalid KMS Key**: Ensure `MCP_KMS_KEY` is 32+ bytes base64 encoded
2. **Database Permissions**: Ensure `/data` directory is writable
3. **Proxy Headers**: Set `TRUST_PROXY=true` when behind a proxy
4. **Rate Limiting**: Check OrderDesk API rate limits

### Logs
```bash
# View logs
docker-compose logs -f mcp

# Check specific errors
docker-compose logs mcp | grep ERROR
```

### Database
```bash
# Access database
sqlite3 data/app.db

# Check tenants
SELECT id, created_at FROM tenants;

# Check stores
SELECT id, store_id, label FROM stores;
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- GitHub Issues: [https://github.com/ebabcock80/orderdesk-mcp/issues](https://github.com/ebabcock80/orderdesk-mcp/issues)
- Documentation: [https://github.com/ebabcock80/orderdesk-mcp/tree/main/docs](https://github.com/ebabcock80/orderdesk-mcp/tree/main/docs)
