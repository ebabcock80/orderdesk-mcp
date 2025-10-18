# OrderDesk MCP Server

[![CI](https://github.com/ebabcock80/orderdesk-mcp/workflows/CI/badge.svg)](https://github.com/ebabcock80/orderdesk-mcp/actions)
[![Tests](https://img.shields.io/badge/tests-71%20passing-success)](https://github.com/ebabcock80/orderdesk-mcp/actions)
[![Coverage](https://img.shields.io/badge/coverage-59%25-green)](https://github.com/ebabcock80/orderdesk-mcp/actions)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A native Model Context Protocol (MCP) server for OrderDesk integration with AI assistants like Claude and LM Studio. This server provides direct access to OrderDesk APIs through MCP tools, enabling seamless order management, product catalog access, and customer data operations.

**Status:** ✅ **Production-Ready Alpha** | **CI:** 🟢 **All Checks Passing** | **Tests:** 71/71 (100%)

## 🚀 Features

### Core MCP Features
- **Native MCP Protocol**: Direct integration with Claude, LM Studio, and other MCP-compatible AI assistants
- **Safe Order Updates**: Fetch → Merge → Update workflow prevents data loss
- **Direct OrderDesk Integration**: Simplified architecture using store_id + api_key authentication
- **Comprehensive API Coverage**: Orders, products, customers, folders, webhooks, and reports
- **JSON Response Formatting**: Properly formatted responses for AI assistant parsing
- **Docker Ready**: Multi-stage Docker build with health checks
- **Persistent Storage**: SQLite database with volume mounting for data persistence

### 🎨 NEW: WebUI Admin Interface (Phase 5) ⭐
- **Professional Dashboard**: Visual overview of stores, API status, and quick actions
- **Store Management**: Full CRUD operations for OrderDesk store registrations
- **Interactive API Console**: Test all 13 MCP tools directly from your browser
- **Secure Authentication**: JWT sessions with master key login
- **Mobile Responsive**: Works on desktop, tablet, and mobile
- **Real-time Feedback**: Instant response display with syntax highlighting
- **Request History**: Track your last 10 API requests
- **Settings Page**: View configuration and system information

**Access the WebUI:** Set `ENABLE_WEBUI=true` in `.env` and visit `http://localhost:8000/webui`

## 🛠️ Implemented MCP Tools (13 Total)

**v0.1.0-alpha** includes 13 fully functional MCP tools:

### Tenant & Store Management (6 Tools)
- `tenant.use_master_key` - Authenticate with master key (auto-provision support)
- `stores.register` - Register OrderDesk store with encrypted credentials
- `stores.list` - List all stores for authenticated tenant
- `stores.use_store` - Set active store for session
- `stores.delete` - Remove store registration
- `stores.resolve` - Debug tool for store lookup

### Order Operations (5 Tools)
- `orders.get` - Fetch single order by ID (15s cache)
- `orders.list` - List orders with pagination and filtering (15s cache)
- `orders.create` - Create new order in OrderDesk
- `orders.update` - Update order with safe merge workflow (5 retries on conflict)
- `orders.delete` - Delete order from OrderDesk

### Product Operations (2 Tools)
- `products.get` - Fetch single product by ID (60s cache)
- `products.list` - List products with search and pagination (60s cache)

### Coming in Future Phases
- Customer operations (Phase 7+)
- Webhook management (Phase 5+)
- Folder operations (Phase 7+)
- Reports (Phase 7+)

## ✅ CI/CD Status

**All GitHub Actions Checks Passing:** 🟢

| Check | Status | Details |
|-------|--------|---------|
| **Lint & Format** | ✅ Passing | ruff + black (0 errors) |
| **Type Check** | ✅ Passing | mypy (0 errors) |
| **Unit Tests** | ✅ Passing | 71/71 tests (100%) |
| **Coverage** | ✅ Passing | 59% (threshold: 55%) |
| **Docker Build** | ✅ Passing | Multi-stage build successful |

**View Results:** [GitHub Actions](https://github.com/ebabcock80/orderdesk-mcp/actions)

**Quality Metrics:**
- 🎯 **100% test pass rate** (71/71 tests)
- 🎯 **0 linting errors** (ruff + black)
- 🎯 **0 type errors** (mypy)
- 🎯 **59% code coverage** (MCP tools well-tested)
- 🎯 **Production-ready** for alpha deployment

## 🚀 Quick Start

### Prerequisites

- **Docker**: Install Docker Desktop or Docker Engine
- **OrderDesk Account**: Active OrderDesk account with API access
- **AI Assistant**: Claude Desktop, LM Studio, or other MCP-compatible client

### Step 1: Clone and Build

```bash
# Clone the repository
git clone https://github.com/ebabcock80/orderdesk-mcp.git
cd orderdesk-mcp

# Build the Docker image
docker build -t orderdesk-mcp:latest .
```

### Step 2: Generate Encryption Key

```bash
# Generate a secure encryption key
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Copy the output - you'll need this for MCP_KMS_KEY
```

### Step 3: Run the MCP Server

```bash
# Create data directory for persistent storage
mkdir -p data

# Run the MCP server with persistent data
docker run --rm -i \
  -v $(pwd)/data:/app/data \
  -e SERVER_MODE=mcp \
  -e MCP_KMS_KEY="YOUR_GENERATED_KEY_HERE" \
  -e DATABASE_URL="sqlite:///./data/app.db" \
  -e LOG_LEVEL=info \
  orderdesk-mcp:latest
```

### Step 4: Configure Your AI Assistant

#### For Claude Desktop
Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "orderdesk": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/path/to/your/data:/app/data",
        "-e", "SERVER_MODE=mcp",
        "-e", "MCP_KMS_KEY=YOUR_GENERATED_KEY_HERE",
        "-e", "DATABASE_URL=sqlite:///./data/app.db",
        "-e", "LOG_LEVEL=info",
        "orderdesk-mcp:latest"
      ]
    }
  }
}
```

#### For LM Studio
Create a configuration file:
```json
{
  "mcpServers": {
    "orderdesk": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/path/to/your/data:/app/data",
        "-e", "SERVER_MODE=mcp",
        "-e", "MCP_KMS_KEY=YOUR_GENERATED_KEY_HERE",
        "-e", "DATABASE_URL=sqlite:///./data/app.db",
        "-e", "LOG_LEVEL=info",
        "orderdesk-mcp:latest"
      ]
    }
  }
}
```

### Step 5: Test the Connection

Once configured, your AI assistant should be able to use OrderDesk tools. Try asking:

- "List my OrderDesk stores"
- "Show me recent orders"
- "Create a new order folder"

## 🔧 Critical Features

### Safe Order Updates
The server implements a critical safety feature for order updates:
1. **Fetch**: Retrieves the complete current order data
2. **Merge**: Applies your changes to the existing data
3. **Update**: Sends the complete updated order back to OrderDesk

This prevents data loss that can occur with partial updates.

### JSON Response Formatting
All MCP tool responses are properly formatted as valid JSON that AI assistants can parse and understand, eliminating parsing errors.

### Direct OrderDesk Integration
- Simplified authentication using `store_id` + `api_key`
- No complex tenant management required
- Direct access to all OrderDesk API endpoints

## 📋 Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SERVER_MODE` | Server mode: `mcp` or `api` | `mcp` | No |
| `MCP_KMS_KEY` | Base64-encoded encryption key (32+ bytes) | - | Yes |
| `DATABASE_URL` | SQLite database URL | `sqlite:///./data/app.db` | No |
| `LOG_LEVEL` | Logging level | `info` | No |
| `TRUST_PROXY` | Trust proxy headers | `false` | No |
| `AUTO_PROVISION_TENANT` | Auto-create tenants | `true` | No |

## 🏗️ Architecture

### MCP Server Implementation
- **Native MCP Protocol**: Direct stdio communication with AI assistants
- **Tool Registration**: All OrderDesk operations exposed as MCP tools
- **Safe Updates**: Fetch-merge-update pattern for order modifications
- **Error Handling**: Comprehensive error responses with proper JSON formatting

## 📖 Usage Guide

### Getting Started with OrderDesk

1. **First, add your OrderDesk store**:
   ```
   "Add my OrderDesk store with ID 42174 and API key abc123"
   ```

2. **List your stores to verify**:
   ```
   "Show me all my OrderDesk stores"
   ```

3. **Browse your orders**:
   ```
   "List my recent orders from OrderDesk"
   "Show me pending orders"
   "Get orders from folder 123"
   ```

### Common Use Cases

#### Order Management
```
"Get details for order 12345"
"Update order 12345 status to shipped with tracking number 1Z999AA1234567890"
"Move order 12345 to the 'Shipped' folder"
"Add a note to order 12345: 'Customer requested expedited shipping'"
```

#### Product Operations
```
"List all products in my store"
"Search for products containing 'widget'"
"Get details for product ID 5678"
```

#### Customer Management
```
"List all customers"
"Search for customer 'john@example.com'"
"Get customer details for ID 999"
```

#### Folder Organization
```
"List all order folders"
"Create a new folder called 'Priority Orders'"
"Move order 12345 to the 'Priority Orders' folder"
```

### Advanced Operations

#### Safe Order Updates
The server automatically handles safe order updates:
- Fetches the complete current order data
- Merges your changes with existing data
- Sends the complete updated order back to OrderDesk
- Prevents data loss from partial updates

#### Batch Operations
```
"List the last 100 orders"
"Show me all orders from the last 30 days"
"Get all pending orders in folder 456"
```

## 🔧 MCP Tool Reference

### Store Management

#### Create Store
```json
{
  "tool": "create_store",
  "arguments": {
    "store_id": "your-store-id",
    "api_key": "your-api-key",
    "name": "My Store"
  }
}
```

#### List Stores
```json
{
  "tool": "list_stores",
  "arguments": {}
}
```

### Order Operations

#### List Orders
```json
{
  "tool": "list_orders",
  "arguments": {
    "store_id": "your-store-id",
    "api_key": "your-api-key",
    "limit": 50,
    "offset": 0,
    "status": "pending",
    "folder_id": 123
  }
}
```

#### Get Order
```json
{
  "tool": "get_order",
  "arguments": {
    "store_id": "your-store-id",
    "api_key": "your-api-key",
    "order_id": 12345
  }
}
```

#### Update Order (Safe)
```json
{
  "tool": "update_order",
  "arguments": {
    "store_id": "your-store-id",
    "api_key": "your-api-key",
    "order_id": 12345,
    "order_data": {
      "status": "shipped",
      "tracking_number": "1Z999AA1234567890"
    }
  }
}
```

## 🚀 Recent Updates

### Critical Fixes (Latest Release)
- ✅ **JSON Response Formatting**: Fixed Claude parsing errors with proper JSON formatting
- ✅ **Safe Order Updates**: Implemented fetch-merge-update workflow to prevent data loss
- ✅ **Simplified Architecture**: Removed tenant complexity, direct store_id + api_key authentication
- ✅ **Native MCP Protocol**: Full MCP server implementation for AI assistant integration

### Key Improvements
- 🔧 **Error Handling**: Comprehensive error responses with proper JSON structure
- 🔧 **Tool Registration**: All OrderDesk operations available as MCP tools
- 🔧 **Database Persistence**: SQLite with volume mounting for data persistence
- 🔧 **Docker Optimization**: Multi-stage build with proper caching

## 📚 Documentation

- **API Documentation**: Available at `/docs` when running in API mode
- **MCP Tools**: All tools documented with proper schemas and examples
- **Configuration**: Environment variables and setup instructions
- **Docker**: Complete containerization with volume support

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🔧 Troubleshooting

### Common Issues

#### Docker Connection Problems
```bash
# Check if Docker is running
docker --version

# Verify the image was built correctly
docker images | grep orderdesk-mcp

# Check container logs
docker logs <container_id>
```

#### MCP Server Not Starting
```bash
# Verify environment variables
echo $MCP_KMS_KEY
echo $DATABASE_URL

# Check data directory permissions
ls -la data/

# Test with verbose logging
docker run --rm -i \
  -v $(pwd)/data:/app/data \
  -e SERVER_MODE=mcp \
  -e MCP_KMS_KEY="your-key" \
  -e LOG_LEVEL=debug \
  orderdesk-mcp:latest
```

#### OrderDesk API Errors
- **401 Unauthorized**: Check your `store_id` and `api_key`
- **404 Not Found**: Verify the endpoint exists in OrderDesk API v2
- **500 Server Error**: Check OrderDesk service status

#### Data Persistence Issues
```bash
# Ensure data directory exists and is writable
mkdir -p data
chmod 755 data

# Check database file
ls -la data/app.db
```

### Getting Help

1. **Check the logs**: Look for error messages in the Docker container logs
2. **Verify configuration**: Ensure all environment variables are set correctly
3. **Test connectivity**: Try a simple tool call like `health_check`
4. **Check OrderDesk**: Verify your OrderDesk account and API credentials

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/ebabcock80/orderdesk-mcp/issues)
- **Documentation**: This README and inline code comments
- **MCP Integration**: See tool schemas and examples above
- **OrderDesk API**: [OrderDesk API Documentation](https://app.orderdesk.me/api-docs)

### Contributing

Found a bug or want to add a feature? We welcome contributions!

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and test them
4. Commit your changes: `git commit -m 'Add amazing feature'`
5. Push to the branch: `git push origin feature/amazing-feature`
6. Open a Pull Request

### License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.