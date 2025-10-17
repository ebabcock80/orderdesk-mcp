# OrderDesk MCP Server Setup Guide

This comprehensive guide will walk you through setting up and using the OrderDesk MCP Server with your AI assistant.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [AI Assistant Setup](#ai-assistant-setup)
5. [Testing](#testing)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Usage](#advanced-usage)

## Prerequisites

### Required Software
- **Docker**: Docker Desktop or Docker Engine
- **Python 3.12+**: For generating encryption keys
- **Git**: For cloning the repository

### Required Accounts
- **OrderDesk Account**: Active account with API access
- **AI Assistant**: Claude Desktop, LM Studio, or other MCP-compatible client

### OrderDesk API Setup
1. Log into your OrderDesk account
2. Go to Settings → API
3. Generate an API key
4. Note your Store ID (found in the API settings)

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/ebabcock80/orderdesk-mcp.git
cd orderdesk-mcp
```

### Step 2: Build the Docker Image

```bash
docker build -t orderdesk-mcp:latest .
```

### Step 3: Create Data Directory

```bash
mkdir -p data
chmod 755 data
```

### Step 4: Generate Encryption Key

```bash
# Generate a secure encryption key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Important**: Save this key securely - you'll need it for configuration.

## Configuration

### Environment Variables

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `SERVER_MODE` | Server mode | `mcp` | No |
| `MCP_KMS_KEY` | Encryption key | `abc123...` | Yes |
| `DATABASE_URL` | Database path | `sqlite:///./data/app.db` | No |
| `LOG_LEVEL` | Logging level | `info` | No |

### Docker Run Command

```bash
docker run --rm -i \
  -v $(pwd)/data:/app/data \
  -e SERVER_MODE=mcp \
  -e MCP_KMS_KEY="YOUR_GENERATED_KEY_HERE" \
  -e DATABASE_URL="sqlite:///./data/app.db" \
  -e LOG_LEVEL=info \
  orderdesk-mcp:latest
```

## AI Assistant Setup

### Claude Desktop

1. **Locate your config file**:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

2. **Add the MCP server configuration**:
   ```json
   {
     "mcpServers": {
       "orderdesk": {
         "command": "docker",
         "args": [
           "run", "--rm", "-i",
           "-v", "/absolute/path/to/your/data:/app/data",
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

3. **Restart Claude Desktop**

### LM Studio

1. **Create MCP configuration file**:
   ```json
   {
     "mcpServers": {
       "orderdesk": {
         "command": "docker",
         "args": [
           "run", "--rm", "-i",
           "-v", "/absolute/path/to/your/data:/app/data",
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

2. **Configure LM Studio to use this file**

### Other MCP Clients

For other MCP-compatible clients, use the same Docker command structure in your client's configuration.

## Testing

### Step 1: Verify Server Startup

Run the server manually to check for errors:

```bash
docker run --rm -i \
  -v $(pwd)/data:/app/data \
  -e SERVER_MODE=mcp \
  -e MCP_KMS_KEY="YOUR_KEY" \
  -e LOG_LEVEL=debug \
  orderdesk-mcp:latest
```

Look for:
- "Starting OrderDesk MCP Server..."
- "Database tables created successfully"
- No error messages

### Step 2: Test with AI Assistant

Once configured, test these commands in your AI assistant:

1. **Health Check**:
   ```
   "Check if the OrderDesk MCP server is working"
   ```

2. **Add Store**:
   ```
   "Add my OrderDesk store with ID 42174 and API key abc123"
   ```

3. **List Stores**:
   ```
   "Show me all my OrderDesk stores"
   ```

4. **List Orders**:
   ```
   "List my recent orders from OrderDesk"
   ```

## Troubleshooting

### Common Issues

#### 1. Docker Not Found
```bash
# Check Docker installation
docker --version

# Start Docker Desktop if needed
# On macOS: Open Docker Desktop app
# On Linux: sudo systemctl start docker
```

#### 2. Permission Denied
```bash
# Fix data directory permissions
chmod 755 data
chown -R $USER:$USER data
```

#### 3. MCP Server Not Starting
```bash
# Check environment variables
echo $MCP_KMS_KEY

# Test with verbose logging
docker run --rm -i \
  -v $(pwd)/data:/app/data \
  -e SERVER_MODE=mcp \
  -e MCP_KMS_KEY="your-key" \
  -e LOG_LEVEL=debug \
  orderdesk-mcp:latest
```

#### 4. OrderDesk API Errors

**401 Unauthorized**:
- Check your `store_id` and `api_key`
- Verify the API key is active in OrderDesk

**404 Not Found**:
- Ensure you're using OrderDesk API v2
- Check the endpoint exists

**500 Server Error**:
- Check OrderDesk service status
- Verify your account has API access

#### 5. Data Not Persisting
```bash
# Check data directory
ls -la data/

# Verify database file
ls -la data/app.db

# Check Docker volume mount
docker run --rm -v $(pwd)/data:/app/data alpine ls -la /app/data
```

### Getting Help

1. **Check Logs**: Look for error messages in Docker container logs
2. **Verify Configuration**: Ensure all environment variables are set
3. **Test Connectivity**: Try a simple tool call like `health_check`
4. **Check OrderDesk**: Verify your account and API credentials

## Advanced Usage

### Custom Configuration

#### Using Environment File
Create a `.env` file:
```bash
SERVER_MODE=mcp
MCP_KMS_KEY=your-generated-key
DATABASE_URL=sqlite:///./data/app.db
LOG_LEVEL=info
TRUST_PROXY=false
AUTO_PROVISION_TENANT=true
```

Run with environment file:
```bash
docker run --rm -i \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  orderdesk-mcp:latest
```

#### Custom Database Location
```bash
docker run --rm -i \
  -v /custom/path:/app/data \
  -e DATABASE_URL="sqlite:///./data/custom.db" \
  orderdesk-mcp:latest
```

### Production Deployment

#### Using Docker Compose
Create `docker-compose.yml`:
```yaml
version: '3.8'
services:
  orderdesk-mcp:
    build: .
    environment:
      - SERVER_MODE=mcp
      - MCP_KMS_KEY=${MCP_KMS_KEY}
      - DATABASE_URL=sqlite:///./data/app.db
      - LOG_LEVEL=info
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

Run with:
```bash
docker-compose up -d
```

#### Security Considerations
- Store encryption keys securely
- Use environment variables, not hardcoded values
- Regularly rotate API keys
- Monitor logs for suspicious activity

### Performance Tuning

#### Logging Levels
- `debug`: Verbose logging for development
- `info`: Standard logging for production
- `warning`: Minimal logging for high-performance

#### Database Optimization
- The SQLite database is optimized for small to medium workloads
- For high-volume usage, consider external database options

## Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/ebabcock80/orderdesk-mcp/issues)
- **Documentation**: This guide and the main README
- **OrderDesk API**: [Official OrderDesk API Documentation](https://app.orderdesk.me/api-docs)

## Contributing

We welcome contributions! Please see the main README for contribution guidelines.
