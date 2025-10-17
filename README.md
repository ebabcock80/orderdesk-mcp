# OrderDesk MCP Server

A native Model Context Protocol (MCP) server for OrderDesk integration with AI assistants like Claude and LM Studio. This server provides direct access to OrderDesk APIs through MCP tools, enabling seamless order management, product catalog access, and customer data operations.

## 🚀 Features

- **Native MCP Protocol**: Direct integration with Claude, LM Studio, and other MCP-compatible AI assistants
- **Safe Order Updates**: Fetch → Merge → Update workflow prevents data loss
- **Direct OrderDesk Integration**: Simplified architecture using store_id + api_key authentication
- **Comprehensive API Coverage**: Orders, products, customers, folders, webhooks, and reports
- **JSON Response Formatting**: Properly formatted responses for AI assistant parsing
- **Docker Ready**: Multi-stage Docker build with health checks
- **Persistent Storage**: SQLite database with volume mounting for data persistence

## 🛠️ Available MCP Tools

The server provides the following MCP tools for AI assistant integration:

### Store Management
- `create_store` - Add a new OrderDesk store with credentials
- `list_stores` - List all configured stores
- `delete_store` - Remove a store configuration

### Order Operations
- `list_orders` - Retrieve orders with filtering options
- `get_order` - Get detailed order information
- `create_order` - Create a new order
- `update_order` - Update existing order (with safe merge)
- `delete_order` - Remove an order
- `mutate_order` - Safe order mutation workflow

### Product Management
- `list_products` - Browse product catalog
- `get_product` - Get detailed product information

### Customer Operations
- `list_customers` - Retrieve customer list
- `get_customer` - Get detailed customer information

### Folder Management
- `list_folders` - List order folders
- `create_folder` - Create new folders

### Webhooks & Reports
- `list_webhooks` - View configured webhooks
- `create_webhook` - Set up new webhooks
- `get_reports` - Generate OrderDesk reports

## 🚀 Quick Start

### Running the MCP Server

1. **Clone the repository**:
   ```bash
   git clone https://github.com/ebabcock80/orderdesk-mcp.git
   cd orderdesk-mcp
   ```

2. **Build the Docker image**:
   ```bash
   docker build -t orderdesk-mcp:latest .
   ```

3. **Run the MCP server**:
   ```bash
   docker run --rm -i \
     -v $(pwd)/data:/app/data \
     -e SERVER_MODE=mcp \
     -e MCP_KMS_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" \
     -e DATABASE_URL="sqlite:///./data/app.db" \
     -e LOG_LEVEL=info \
     orderdesk-mcp:latest
   ```

4. **Connect with AI Assistant**:
   - Configure your AI assistant (Claude, LM Studio, etc.) to connect to the MCP server
   - Use the available tools to interact with OrderDesk APIs

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

## 🔧 MCP Tool Examples

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

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/ebabcock80/orderdesk-mcp/issues)
- **Documentation**: Check the `/docs` directory for detailed guides
- **MCP Integration**: See tool schemas and examples above