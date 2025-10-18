# Configuration Guide

This directory contains environment-specific configuration templates for the OrderDesk MCP Server.

---

## Environment Templates

### `environments/development.env`
**Purpose:** Local development and testing

**Features:**
- Debug logging enabled
- Relaxed rate limits
- Console email provider (no real emails)
- Memory caching (simple)
- Auto-provisioning enabled
- HTTP cookies allowed (no HTTPS required)

**Usage:**
```bash
cp config/environments/development.env .env
docker-compose up -d
```

### `environments/staging.env`
**Purpose:** Pre-production testing and QA

**Features:**
- Production-like security
- Real SMTP for email testing
- SQLite or Redis caching
- Integration tests enabled
- Trace viewer enabled for debugging
- HTTPS required

**Usage:**
```bash
cp config/environments/staging.env .env
# Update all CHANGE_ME values with real secrets
docker-compose -f docker-compose.staging.yml up -d
```

### `environments/production.env`
**Purpose:** Production deployment

**Features:**
- Maximum security
- Redis caching for multi-instance
- Real SMTP required
- Auto-provisioning disabled
- Trace viewer disabled
- Detailed health checks disabled
- HTTPS required

**Usage:**
```bash
cp config/environments/production.env .env
# Update all CHANGE_ME values with strong, unique secrets
# Deploy with your production orchestration (Docker Compose, K8s, etc.)
```

---

## Quick Setup

### For Development
```bash
# 1. Copy development template
cp config/environments/development.env .env

# 2. Start the server
docker-compose up -d

# 3. Access WebUI
open http://localhost:8080/webui

# 4. Login with admin key
# Default: dev-admin-master-key-change-in-production-VNS09qKDdt
```

### For Staging
```bash
# 1. Copy staging template
cp config/environments/staging.env .env

# 2. Generate unique secrets
echo "MCP_KMS_KEY=$(openssl rand -base64 32)"
echo "ADMIN_MASTER_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
echo "JWT_SECRET_KEY=$(openssl rand -base64 48)"
echo "CSRF_SECRET_KEY=$(openssl rand -base64 32)"

# 3. Update .env with generated secrets
# 4. Configure SMTP settings
# 5. Set PUBLIC_URL to your staging domain

# 6. Deploy
docker-compose -f docker-compose.staging.yml up -d
```

### For Production
```bash
# 1. Copy production template
cp config/environments/production.env .env

# 2. Generate strong, unique secrets (NEVER reuse from dev/staging!)
openssl rand -base64 32  # MCP_KMS_KEY
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'  # ADMIN_MASTER_KEY
openssl rand -base64 48  # JWT_SECRET_KEY
openssl rand -base64 32  # CSRF_SECRET_KEY

# 3. Update ALL secrets in .env
# 4. Configure production SMTP (SendGrid, Postmark, etc.)
# 5. Set PUBLIC_URL to your production domain
# 6. Review security checklist in production.env

# 7. Deploy
docker-compose -f docker-compose.production.yml up -d
```

---

## Environment Comparison

| Setting | Development | Staging | Production |
|---------|-------------|---------|------------|
| **LOG_LEVEL** | DEBUG | INFO | INFO/WARNING |
| **CACHE_BACKEND** | memory | sqlite/redis | redis |
| **AUTO_PROVISION** | ✅ true | ❌ false | ❌ false |
| **COOKIE_SECURE** | ❌ false | ✅ true | ✅ true |
| **TRACE_VIEWER** | ✅ true | ✅ true | ❌ false |
| **DETAILED_HEALTH** | ✅ true | ✅ true | ❌ false |
| **EMAIL_PROVIDER** | console | smtp | smtp |
| **PUBLIC_SIGNUP** | ✅ true | ✅ true | ❌ false* |
| **RATE_LIMITS** | Relaxed (240 RPM) | Standard (120 RPM) | Strict (120 RPM) |
| **SESSION_TIMEOUT** | 24h | 12h | 8h |

\* Set `PUBLIC_SIGNUP` based on deployment model (SaaS vs private)

---

## Security Best Practices

### Key Generation

**MCP_KMS_KEY (32+ bytes, base64):**
```bash
openssl rand -base64 32
```

**ADMIN_MASTER_KEY (48+ characters, URL-safe):**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

**JWT_SECRET_KEY (48+ bytes, base64):**
```bash
openssl rand -base64 48
```

**CSRF_SECRET_KEY (32+ bytes, base64):**
```bash
openssl rand -base64 32
```

### Secret Management

**Development:**
- Secrets in `.env` file (gitignored)
- Shared among team (low-security dev keys OK)

**Staging:**
- Unique secrets (never reuse from dev)
- Store in secure location (1Password, LastPass)
- Rotate monthly

**Production:**
- Strong, unique secrets (never reuse from dev/staging)
- Use secret management service (AWS Secrets Manager, HashiCorp Vault)
- Rotate quarterly or after any breach
- Restrict access to ops team only

---

## Environment Detection

The server automatically detects the environment based on settings:

```python
# In code:
if settings.log_level == "DEBUG":
    environment = "development"
elif settings.enable_trace_viewer == False:
    environment = "production"
else:
    environment = "staging"
```

No explicit `ENVIRONMENT` variable needed - inferred from configuration.

---

## Switching Environments

### Development → Staging
```bash
docker-compose down
cp config/environments/staging.env .env
# Update all secrets
docker-compose -f docker-compose.staging.yml up -d
```

### Staging → Production
```bash
# Stop staging
docker-compose -f docker-compose.staging.yml down

# Backup staging data
cp data/app.db data/app.staging.db

# Switch to production config
cp config/environments/production.env .env
# Update ALL secrets with production values

# Deploy with production compose
docker-compose -f docker-compose.production.yml up -d
```

---

## Troubleshooting

### "Missing required environment variable"
```bash
# Check which variables are required
grep "Field(...," mcp_server/config.py

# Verify your .env file has all required vars
cat .env | grep -E "^(MCP_KMS_KEY|ADMIN_MASTER_KEY)="
```

### "Session cookies not working"
```bash
# For local development, set COOKIE_SECURE=false
# For staging/production with HTTPS, set COOKIE_SECURE=true
```

### "Rate limits too strict for testing"
```bash
# Use development.env for relaxed limits
# Or adjust specific limits in your .env:
RATE_LIMIT_RPM=240
WEBUI_RATE_LIMIT_API_CONSOLE=60
```

---

## Links

- Main README: [../README.md](../README.md)
- Setup Guide: [../docs/SETUP_GUIDE.md](../docs/SETUP_GUIDE.md)
- Deployment Guide: [../docs/DEPLOYMENT-DOCKER.md](../docs/DEPLOYMENT-DOCKER.md)
- Security Audit: [../docs/SECURITY-AUDIT.md](../docs/SECURITY-AUDIT.md)

