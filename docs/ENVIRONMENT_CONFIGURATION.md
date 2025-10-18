# Environment Configuration Guide

Complete guide to configuring the OrderDesk MCP Server for different environments.

---

## Quick Start

### Development
```bash
cp config/environments/development.env .env
docker-compose up -d
```

### Staging
```bash
cp config/environments/staging.env .env
# Update all CHANGE_ME secrets
docker-compose -f docker-compose.staging.yml up -d
```

### Production
```bash
cp config/environments/production.env .env
# Update all CHANGE_ME secrets
docker-compose -f docker-compose.production.yml up -d
```

---

## Environment Files

### Location: `config/environments/`

| File | Purpose | Security Level |
|------|---------|----------------|
| `development.env` | Local development | Low (test keys) |
| `staging.env` | Pre-production QA | Medium (staging keys) |
| `production.env` | Production deployment | High (strong keys) |

---

## Key Differences

### Development vs Staging vs Production

| Setting | Development | Staging | Production |
|---------|-------------|---------|------------|
| **Logging** | DEBUG | INFO | INFO/WARNING |
| **Cache** | memory | sqlite/redis | redis |
| **HTTPS** | Optional | Required | Required |
| **Auto-Provision** | ✅ Enabled | ❌ Disabled | ❌ Disabled |
| **Public Signup** | ✅ Enabled | ✅ Enabled | Conditional |
| **Email Provider** | console | smtp | smtp |
| **Rate Limits** | Relaxed | Standard | Strict |
| **Session Timeout** | 24h | 12h | 8h |
| **Trace Viewer** | ✅ Enabled | ✅ Enabled | ❌ Disabled |
| **Detailed Health** | ✅ Enabled | ✅ Enabled | ❌ Disabled |
| **Cookie Secure** | ❌ false | ✅ true | ✅ true |
| **Trust Proxy** | ❌ false | ✅ true | ✅ true |

---

## Required Secrets

### Generate Strong Secrets

**For all environments, generate unique secrets:**

```bash
# MCP_KMS_KEY (32+ bytes, base64)
openssl rand -base64 32

# ADMIN_MASTER_KEY (48+ characters, URL-safe)
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# JWT_SECRET_KEY (48+ bytes, base64)
openssl rand -base64 48

# CSRF_SECRET_KEY (32+ bytes, base64)
openssl rand -base64 32
```

### ⚠️ Security Requirements

**Development:**
- Test keys OK (included in template)
- Can be shared among team
- Low security risk

**Staging:**
- ⚠️ MUST generate unique keys
- Never reuse development keys
- Medium security - store in 1Password/LastPass
- Rotate monthly

**Production:**
- ⚠️ MUST generate strong, unique keys
- NEVER reuse from dev/staging
- High security - use AWS Secrets Manager or HashiCorp Vault
- Rotate quarterly
- Restrict access to ops team only

---

## Configuration Sections

### 1. Required Encryption Keys

```bash
# Master encryption key - derives per-tenant keys
MCP_KMS_KEY=your-base64-encoded-32-byte-key

# Admin account master key - WebUI login
ADMIN_MASTER_KEY=your-64-character-url-safe-key
```

**Critical:** These keys cannot be recovered if lost. Losing them means losing access to all encrypted data.

---

### 2. Core Server Settings

```bash
PORT=8080                          # Server port
PUBLIC_URL=https://yourdomain.com  # Public URL for MCP config
DATABASE_URL=sqlite:///data/app.db # Database connection
LOG_LEVEL=INFO                     # Logging verbosity
TRUST_PROXY=true                   # Trust X-Forwarded-For headers
AUTO_PROVISION_TENANT=false        # Disable in production
```

---

### 3. WebUI Configuration

```bash
ENABLE_WEBUI=true                  # Enable web interface
JWT_SECRET_KEY=your-jwt-secret     # Session token signing
SESSION_TIMEOUT=28800              # 8 hours
SESSION_COOKIE_SECURE=true         # HTTPS required
SESSION_COOKIE_HTTPONLY=true       # Prevent XSS
SESSION_COOKIE_SAMESITE=Strict     # CSRF protection
CSRF_SECRET_KEY=your-csrf-secret   # CSRF token signing
```

---

### 4. Rate Limiting

```bash
# API rate limits
RATE_LIMIT_RPM=120                      # Requests per minute

# WebUI rate limits
WEBUI_RATE_LIMIT_LOGIN=5                # Login attempts/min/IP
WEBUI_RATE_LIMIT_SIGNUP=2               # Signup attempts/min/IP
WEBUI_RATE_LIMIT_API_CONSOLE=30         # Console requests/min/user
SIGNUP_RATE_LIMIT_PER_HOUR=3            # Signups/hour/IP
```

**Recommendations:**
- **Development:** Relaxed (240 RPM)
- **Staging:** Standard (120 RPM)
- **Production:** Strict (120 RPM) or adjust based on load

---

### 5. Public Signup (Optional)

```bash
ENABLE_PUBLIC_SIGNUP=false              # Enable email signups
REQUIRE_EMAIL_VERIFICATION=true         # Require verification
SIGNUP_VERIFICATION_EXPIRY=900          # Link expiry (15 min)
```

**When to enable:**
- ✅ SaaS deployment (multi-tenant)
- ❌ Private deployment (single organization)
- ❌ Enterprise deployment (SSO instead)

---

### 6. Email Configuration

```bash
EMAIL_PROVIDER=smtp                     # Provider: console or smtp
SMTP_HOST=smtp.sendgrid.net            # SMTP server
SMTP_PORT=587                          # SMTP port
SMTP_USERNAME=apikey                   # SMTP username
SMTP_PASSWORD=your-api-key             # SMTP password
SMTP_USE_TLS=true                      # Use TLS
SMTP_FROM_EMAIL=noreply@yourdomain.com # Sender email
```

**Recommended Providers:**
- **SendGrid** - 100 emails/day free tier
- **Postmark** - Fast, reliable transactional email
- **AWS SES** - Low cost, high volume
- **Gmail** - Development only (use app-specific password)

---

### 7. Caching Strategy

```bash
CACHE_BACKEND=redis                     # Backend: memory, sqlite, redis
REDIS_URL=redis://redis:6379/0          # Redis connection
CACHE_TTL_ORDERS=15                     # Orders TTL (seconds)
CACHE_TTL_PRODUCTS=60                   # Products TTL (seconds)
CACHE_TTL_CUSTOMERS=60                  # Customers TTL (seconds)
CACHE_TTL_STORE_SETTINGS=300            # Store config TTL (seconds)
```

**Recommendations:**
- **Development:** memory (simple, single instance)
- **Staging:** sqlite or redis (test multi-instance)
- **Production:** redis (required for multi-instance)

---

### 8. Monitoring & Observability

```bash
ENABLE_METRICS=true                     # Prometheus metrics
ENABLE_DETAILED_HEALTH=false            # Hide internals in prod
ENABLE_AUDIT_LOG=true                   # Audit trail
AUDIT_LOG_RETENTION_DAYS=90             # Retention period
ENABLE_TRACE_VIEWER=false               # Disable in prod
```

**Production Recommendations:**
- Enable metrics for Prometheus scraping
- Disable detailed health (security)
- Disable trace viewer (security)
- Keep audit logs for compliance

---

## Environment-Specific Deployment

### Development Deployment

```bash
# 1. Copy development config
cp config/environments/development.env .env

# 2. Start with docker-compose
docker-compose up -d

# 3. Access WebUI
open http://localhost:8080/webui

# 4. Login with default admin key
# dev-admin-master-key-change-in-production-VNS09qKDdt
```

**Features:**
- ✅ Debug logging
- ✅ Console email (no SMTP needed)
- ✅ Memory caching
- ✅ HTTP allowed
- ✅ Auto-provisioning
- ✅ Relaxed rate limits

---

### Staging Deployment

```bash
# 1. Copy staging config
cp config/environments/staging.env .env

# 2. Generate staging secrets
echo "MCP_KMS_KEY=$(openssl rand -base64 32)"
echo "ADMIN_MASTER_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
echo "JWT_SECRET_KEY=$(openssl rand -base64 48)"
echo "CSRF_SECRET_KEY=$(openssl rand -base64 32)"

# 3. Update .env with generated secrets

# 4. Configure SMTP (use real credentials)
# Edit .env:
#   SMTP_HOST=smtp.gmail.com
#   SMTP_USERNAME=your-email@gmail.com
#   SMTP_PASSWORD=your-app-password
#   SMTP_FROM_EMAIL=staging@yourdomain.com

# 5. Set staging domain
# Edit .env:
#   PUBLIC_URL=https://staging.yourdomain.com

# 6. Deploy
docker-compose -f docker-compose.staging.yml up -d

# 7. Verify
curl https://staging.yourdomain.com/health
```

**Features:**
- ✅ Production-like security
- ✅ Real SMTP for email testing
- ✅ HTTPS required
- ✅ Integration tests enabled
- ✅ Trace viewer for debugging

---

### Production Deployment

```bash
# 1. Copy production config
cp config/environments/production.env .env

# 2. Generate STRONG, UNIQUE secrets
openssl rand -base64 32  # MCP_KMS_KEY
python3 -c 'import secrets; print(secrets.token_urlsafe(64))'  # ADMIN_MASTER_KEY (extra long!)
openssl rand -base64 64  # JWT_SECRET_KEY (extra long!)
openssl rand -base64 32  # CSRF_SECRET_KEY

# 3. Update ALL secrets in .env (NEVER use dev/staging keys!)

# 4. Configure production SMTP
# Recommended: SendGrid, Postmark, AWS SES
# Edit .env with your provider's credentials

# 5. Set production domain
PUBLIC_URL=https://yourdomain.com

# 6. Review security checklist (in production.env)

# 7. Generate SSL certificates
# Let's Encrypt:
certbot certonly --webroot -w /var/www/certbot \
  -d yourdomain.com -d www.yourdomain.com

# 8. Deploy
docker-compose -f docker-compose.production.yml up -d

# 9. Verify all endpoints
curl https://yourdomain.com/health
curl https://yourdomain.com/health/ready
curl https://yourdomain.com/metrics

# 10. Test MCP connection
# Use WebUI Settings page to generate config
```

**Production Checklist:**
- [ ] All secrets generated and unique
- [ ] SSL/TLS certificates installed
- [ ] nginx configured with your domain
- [ ] SMTP tested and working
- [ ] Redis running and healthy
- [ ] Database backed up
- [ ] Monitoring configured
- [ ] Alerts set up
- [ ] Firewall rules applied
- [ ] Health checks passing

---

## Troubleshooting

### "Missing required environment variable: MCP_KMS_KEY"
```bash
# Make sure .env file exists
ls -la .env

# Make sure MCP_KMS_KEY is set
grep MCP_KMS_KEY .env

# Generate if missing
openssl rand -base64 32
```

### "Session cookies not working"
```bash
# Development (HTTP):
SESSION_COOKIE_SECURE=false

# Staging/Production (HTTPS):
SESSION_COOKIE_SECURE=true
```

### "Rate limits too strict"
```bash
# Adjust in .env:
RATE_LIMIT_RPM=240  # Increase from 120
WEBUI_RATE_LIMIT_API_CONSOLE=60  # Increase from 30
```

### "Emails not sending"
```bash
# Development: Use console provider
EMAIL_PROVIDER=console

# Staging/Production: Configure real SMTP
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.sendgrid.net
SMTP_USERNAME=apikey
SMTP_PASSWORD=your-sendgrid-api-key
```

### "Cache not working in multi-instance"
```bash
# Must use Redis for multi-instance:
CACHE_BACKEND=redis
REDIS_URL=redis://redis:6379/0

# Start Redis:
docker-compose -f docker-compose.production.yml up -d redis
```

---

## Secret Rotation

### Quarterly Rotation (Recommended)

```bash
# 1. Generate new secrets
NEW_KMS=$(openssl rand -base64 32)
NEW_JWT=$(openssl rand -base64 48)
NEW_CSRF=$(openssl rand -base64 32)

# 2. Update .env file
# 3. Restart services (zero-downtime with load balancer)
# 4. Invalidate all sessions (users must re-login)
# 5. Test thoroughly
```

### After Security Incident

1. Immediately rotate ALL secrets
2. Force logout all users
3. Review audit logs
4. Check for unauthorized access
5. Update and redeploy

---

## Links

- [README.md](../README.md) - Main documentation
- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Setup instructions
- [DEPLOYMENT-DOCKER.md](DEPLOYMENT-DOCKER.md) - Docker deployment
- [PRODUCTION-RUNBOOK.md](PRODUCTION-RUNBOOK.md) - Operations guide
- [SECURITY-AUDIT.md](SECURITY-AUDIT.md) - Security documentation

