# Implementation Guide: Completed Features

**Version:** 0.1.0-alpha (Phase 0-1)  
**Last Updated:** October 17, 2025  
**Status:** Foundation Complete, Services Layer Complete

---

## Overview

This guide documents all implemented features in the OrderDesk MCP Server as of Phase 1 completion (77%). It serves as both a reference for developers and validation against the specification.

**Implemented Phases:**
- ✅ Phase 0: Bootstrap & CI (100% complete)
- ✅ Phase 1: Auth, Storage, Session Context (77% complete)

**Total Code:** ~2,000 lines across 18 files

---

## Table of Contents

1. [Configuration System](#configuration-system)
2. [Security & Cryptography](#security--cryptography)
3. [Database Schema](#database-schema)
4. [Session Management](#session-management)
5. [Authentication Services](#authentication-services)
6. [Store Management](#store-management)
7. [Rate Limiting](#rate-limiting)
8. [Logging & Observability](#logging--observability)
9. [Error Handling](#error-handling)
10. [Docker & CI/CD](#docker--cicd)

---

## Configuration System

**File:** `mcp_server/config.py` (190 lines)

### Features

The configuration system uses Pydantic Settings with comprehensive validation:

**60+ Environment Variables Organized in Groups:**

#### Core Server (3 variables)
```python
PORT=8080                    # Server port (1024-65535)
DATABASE_URL=sqlite:///...   # Database connection
LOG_LEVEL=INFO               # Logging level
```

#### Security (4 variables)
```python
MCP_KMS_KEY=...             # Master encryption key (REQUIRED, 32+ bytes)
TRUST_PROXY=false           # Proxy header parsing
RATE_LIMIT_RPM=120          # Per-tenant rate limit
AUTO_PROVISION_TENANT=false # Auto-create tenants
```

#### Cache (5 variables)
```python
CACHE_BACKEND=memory        # memory|redis
REDIS_URL=redis://...       # Redis connection
CACHE_TTL_ORDERS=15         # Orders cache TTL (seconds)
CACHE_TTL_PRODUCTS=60       # Products cache TTL
CACHE_TTL_STORE_SETTINGS=300 # Store settings cache TTL
```

#### Resilience (3 variables)
```python
HTTP_TIMEOUT=30             # HTTP client timeout
HTTP_MAX_RETRIES=3          # Retries for 429/5xx
MUTATION_MAX_RETRIES=5      # Retries for conflicts
```

#### WebUI (40+ variables)
```python
ENABLE_WEBUI=false          # Feature flag
ENABLE_PUBLIC_SIGNUP=false  # Signup mode
JWT_SECRET_KEY=...          # Session signing key
SESSION_TIMEOUT=86400       # 24 hours
MAGIC_LINK_EXPIRY=900       # 15 minutes

# Email
SMTP_HOST=...
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...

# Rate Limits
WEBUI_RATE_LIMIT_LOGIN=5    # 5 attempts/min
WEBUI_RATE_LIMIT_SIGNUP=2   # 2 attempts/min

# Features
ENABLE_TRACE_VIEWER=true
ENABLE_AUDIT_LOG=true
AUDIT_LOG_RETENTION_DAYS=90
```

### Validators

**5 validators ensure configuration safety:**

1. **validate_kms_key** - Ensures MCP_KMS_KEY is 32+ bytes base64
2. **validate_jwt_secret** - Requires JWT_SECRET_KEY when ENABLE_WEBUI=true
3. **validate_samesite** - Cookie SameSite (Strict/Lax/None)
4. **validate_log_level** - Standard levels only
5. **validate_cache_backend** - Supported backends only

**Error Example:**
```python
# If MCP_KMS_KEY is too short:
ValueError: KMS key must be at least 32 bytes when decoded

# If ENABLE_WEBUI=true but no JWT_SECRET_KEY:
ValueError: JWT_SECRET_KEY is required when ENABLE_WEBUI=true
```

---

## Security & Cryptography

**File:** `mcp_server/auth/crypto.py` (242 lines)

### HKDF Key Derivation (HKDF-SHA256)

**Purpose:** Derive per-tenant encryption keys from master key

**Implementation:**
```python
def derive_tenant_key(master_key: str, salt: str) -> bytes:
    """
    Derive 32-byte AES key using HKDF-SHA256.
    
    Formula: HKDF(IKM=master_key, salt=salt, info="orderdesk-mcp-tenant-{salt}", length=32)
    """
    info = f"orderdesk-mcp-tenant-{salt}".encode()
    
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt.encode(),
        info=info,
        backend=default_backend()
    )
    
    return hkdf.derive(master_key.encode())
```

**Properties:**
- Deterministic: Same inputs → same output
- One-way: Cannot reverse to get master_key
- Unique per tenant: Different salt → different key
- Secure: Uses SHA-256, cryptographically strong

### AES-256-GCM Encryption

**Purpose:** Encrypt API keys at rest with authenticated encryption

**Encryption:**
```python
def encrypt_api_key(api_key: str, tenant_key: bytes) -> Tuple[str, str, str]:
    """
    Returns: (ciphertext_b64, tag_b64, nonce_b64)
    
    - Nonce: 12 bytes (96 bits), random per encryption
    - Tag: 16 bytes (128 bits), authentication tag
    - Ciphertext: Variable length, encrypted data
    """
    nonce = os.urandom(12)
    
    cipher = Cipher(
        algorithms.AES(tenant_key),  # 256-bit key
        modes.GCM(nonce),
        backend=default_backend()
    )
    encryptor = cipher.encryptor()
    
    ciphertext = encryptor.update(api_key.encode()) + encryptor.finalize()
    
    return (
        base64.b64encode(ciphertext).decode(),
        base64.b64encode(encryptor.tag).decode(),
        base64.b64encode(nonce).decode()
    )
```

**Decryption:**
```python
def decrypt_api_key(ciphertext: str, tag: str, nonce: str, tenant_key: bytes) -> str:
    """
    Decrypts with tag verification.
    
    Raises: Exception if tag verification fails (data tampered)
    """
    cipher = Cipher(
        algorithms.AES(tenant_key),
        modes.GCM(base64.b64decode(nonce), base64.b64decode(tag)),
        backend=default_backend()
    )
    decryptor = cipher.decryptor()
    
    plaintext = decryptor.update(base64.b64decode(ciphertext)) + decryptor.finalize()
    return plaintext.decode()
```

**Security Properties:**
- Authenticated encryption (GCM mode)
- Tag verification prevents tampering
- Unique nonce per encryption (no nonce reuse)
- 256-bit key strength

### Bcrypt Master Key Hashing

**Purpose:** Securely hash master keys (never store plaintext)

```python
def hash_master_key(master_key: str) -> Tuple[str, str]:
    """
    Returns: (bcrypt_hash, hkdf_salt)
    
    - Uses bcrypt with automatic salt generation
    - Separate salt for HKDF key derivation
    """
    salt = secrets.token_hex(32)  # For HKDF
    hashed = bcrypt.hashpw(master_key.encode(), bcrypt.gensalt())
    return hashed.decode(), salt

def verify_master_key(master_key: str, stored_hash: str) -> bool:
    """Constant-time verification."""
    return bcrypt.checkpw(master_key.encode(), stored_hash.encode())
```

**Security Properties:**
- Bcrypt (adaptive, future-proof)
- Constant-time comparison
- Automatic work factor
- Separate HKDF salt

### Security Flow Diagram

```
User Input: Master Key
    ↓
Bcrypt Hash → Database (tenants.master_key_hash)
    ↓
On auth: bcrypt.checkpw() → Tenant found
    ↓
HKDF Derivation (master_key + salt) → Tenant Key (32 bytes, in-memory)
    ↓
AES-256-GCM Encryption → API Key Storage
    ↓
Database: api_key_ciphertext + api_key_tag + api_key_nonce
```

---

## Database Schema

**File:** `mcp_server/models/database.py` (309 lines)

### Table: `tenants`

**Purpose:** Store tenant authentication information

**Schema:**
```sql
CREATE TABLE tenants (
    id TEXT PRIMARY KEY,              -- UUID
    master_key_hash TEXT NOT NULL,    -- Bcrypt hash (never plaintext)
    salt TEXT NOT NULL,                -- Random salt for HKDF
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    INDEX idx_tenants_master_key_hash (master_key_hash)
);
```

**Security Note:** Never stores plaintext master keys, only bcrypt hashes.

### Table: `stores`

**Purpose:** Store OrderDesk store registrations with encrypted credentials

**Schema:**
```sql
CREATE TABLE stores (
    id TEXT PRIMARY KEY,              -- UUID
    tenant_id TEXT NOT NULL,          -- FK to tenants.id (CASCADE)
    store_id TEXT NOT NULL,           -- OrderDesk store ID
    store_name TEXT NOT NULL,         -- Friendly name for lookup
    label TEXT,                        -- Optional label
    api_key_ciphertext TEXT NOT NULL, -- AES-GCM ciphertext (base64)
    api_key_tag TEXT NOT NULL,        -- GCM authentication tag (base64)
    api_key_nonce TEXT NOT NULL,      -- GCM nonce/IV (base64)
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    UNIQUE (tenant_id, store_name),   -- No duplicate names per tenant
    UNIQUE (tenant_id, store_id),     -- No duplicate IDs per tenant
    INDEX idx_stores_tenant_id (tenant_id),
    INDEX idx_stores_store_name (tenant_id, store_name)
);
```

**Features:**
- Per-specification AES-GCM storage (separate ciphertext, tag, nonce)
- Store lookup by friendly name (store_name)
- Prevents duplicate registrations
- Cascade delete when tenant deleted

### Table: `audit_log`

**Purpose:** Complete audit trail for all operations

**Schema:**
```sql
CREATE TABLE audit_log (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,          -- FK to tenants.id (CASCADE)
    store_id TEXT,                    -- Nullable for tenant-level actions
    tool_name TEXT NOT NULL,          -- MCP tool name or action
    parameters TEXT,                   -- JSON (secrets redacted)
    status TEXT NOT NULL,              -- 'success' or 'error'
    error_message TEXT,
    duration_ms INTEGER,
    request_id TEXT NOT NULL,         -- Correlation ID
    source TEXT NOT NULL,             -- 'mcp' or 'webui'
    ip_address TEXT,                  -- Client IP (WebUI only)
    user_agent TEXT,                  -- Browser UA (WebUI only)
    created_at TIMESTAMP NOT NULL,
    
    INDEX idx_audit_log_tenant_id (tenant_id),
    INDEX idx_audit_log_created_at (created_at),
    INDEX idx_audit_log_request_id (request_id),
    INDEX idx_audit_log_source (source),
    INDEX idx_audit_log_status (status)
);
```

**Used by:** Trace viewer in WebUI, audit compliance

### WebUI Tables

**sessions** - JWT session management (revocable)  
**magic_links** - Passwordless auth tokens (15-min expiry)  
**master_key_metadata** - Key rotation tracking  

All created but unused if `ENABLE_WEBUI=false`.

---

## Session Management

**File:** `mcp_server/services/session.py` (174 lines)

### SessionContext

**Purpose:** Per-request context using async ContextVars

**Implementation:**
```python
@dataclass
class SessionContext:
    tenant_id: Optional[str] = None          # Authenticated tenant
    tenant_key: Optional[bytes] = None       # Derived encryption key (in-memory only)
    active_store_id: Optional[str] = None    # Currently selected store
    correlation_id: str = ""                  # UUID for request tracing
```

**Key Functions:**
```python
get_context() -> SessionContext           # Get current context
set_tenant(tenant_id, tenant_key)        # Set after auth
set_active_store(store_id)               # Set active store
get_active_store() -> Optional[str]      # Get active store
require_auth() -> str                    # Require auth, raise if not
new_correlation_id() -> str              # Generate new ID
```

**Features:**
- Async-safe (uses ContextVar)
- Automatic correlation ID generation
- Integrates with logging context
- Per-request isolation

**Usage Example:**
```python
# After authentication
from mcp_server.services.session import set_tenant, require_auth

set_tenant(tenant.id, tenant_key)

# In subsequent tool calls
tenant_id = require_auth()  # Raises AuthError if not authenticated
```

---

## Authentication Services

**File:** `mcp_server/services/tenant.py` (134 lines)

### TenantService

**Purpose:** Tenant lifecycle and master key authentication

**Methods:**

#### authenticate(master_key) → Tenant | None
```python
"""
Authenticates tenant via master key.

Process:
1. Query all tenants
2. For each: bcrypt.checkpw(master_key, tenant.master_key_hash)
3. Return tenant if match found
4. Log success/failure

Note: O(n) complexity - acceptable for early versions
Future: Add caching or index optimization
"""
```

#### create_tenant(master_key) → Tenant
```python
"""
Creates new tenant.

Process:
1. Check if tenant exists (prevent duplicates)
2. Hash master key with bcrypt
3. Generate random salt for HKDF
4. Store hash and salt (never plaintext)
5. Log tenant creation

Raises: AuthError if tenant already exists
"""
```

#### authenticate_or_create(master_key, auto_provision) → Tenant | None
```python
"""
Authenticate or auto-provision tenant.

Per AUTO_PROVISION_TENANT setting:
- true: Create tenant if not found
- false: Return None if not found

Used by: tenant.use_master_key tool
"""
```

**Security:**
- Never stores plaintext master keys
- Bcrypt constant-time verification
- Comprehensive logging (success/failure)
- Auto-provision toggle for security

---

## Store Management

**File:** `mcp_server/services/store.py` (247 lines)

### StoreService

**Purpose:** OrderDesk store registration and credential management

**Methods:**

#### register_store(...) → Store
```python
"""
Register OrderDesk store with encrypted credentials.

Parameters:
- tenant_id: Tenant ID
- store_id: OrderDesk store ID
- api_key: OrderDesk API key (plaintext, will be encrypted)
- store_name: Friendly name (defaults to store_id)
- label: Optional label
- tenant_key: Pre-derived key (optional)

Process:
1. Validate no duplicates (store_name or store_id)
2. Encrypt API key with AES-256-GCM
3. Store ciphertext, tag, nonce separately
4. Log registration

Raises:
- ValidationError: If duplicate store_name or store_id
- NotFoundError: If tenant not found
"""
```

#### list_stores(tenant_id) → list[Store]
```python
"""
List all stores for tenant.

Features:
- Tenant isolation (filters by tenant_id)
- Ordered by created_at DESC (newest first)
- Never returns decrypted API keys
"""
```

#### get_store_by_name(tenant_id, store_name) → Store | None
```python
"""
Lookup store by friendly name.

Per specification: Enables store lookup by name to reduce
parameter repetition in tool calls.

Example:
- stores.register(store_id="12345", store_name="production")
- Later: orders.list(store_name="production")  ← uses this lookup
"""
```

#### resolve_store(tenant_id, identifier) → Store | None
```python
"""
Resolve store by ID or name.

Strategy:
1. Try by store_id first (exact match)
2. Fallback to store_name
3. Return first match or None

Enables flexible tool calls:
- stores.use_store("12345")          ← by ID
- stores.use_store("production")     ← by name
"""
```

#### get_decrypted_credentials(store, tenant_key) → (str, str)
```python
"""
Decrypt store credentials.

Returns: (store_id, api_key) decrypted

Process:
1. Extract ciphertext, tag, nonce from store
2. Call crypto.decrypt_api_key()
3. Return plaintext credentials

Raises: Exception if decryption fails (tampered data)

Security: Credentials only in memory, never logged
"""
```

#### test_store_credentials(tenant_id, store_id, tenant_key) → dict
```python
"""
Test store connection with OrderDesk API.

Useful for WebUI "Test Connection" button.

Process:
1. Get store from database
2. Decrypt credentials
3. Call OrderDesk /test endpoint
4. Return success/error status

Returns:
{
  "status": "success"/"error",
  "message": "Connection successful",
  "orderdesk_time": "2025-10-17 12:00:00"
}
"""
```

---

## Rate Limiting

**File:** `mcp_server/services/rate_limit.py` (211 lines)

### Token Bucket Algorithm

**Per Q11 decision:** Allow bursts up to 2x rate, then throttle

**Configuration:**
```python
Capacity: 240 tokens (2× base rate of 120 RPM)
Rate: 2 tokens/second (refill rate)
Burst: Can consume up to 240 tokens immediately
Sustained: 120 requests/minute average
```

**Read vs Write Differentiation (Q11):**
```python
Read operations:  consume 1 token
Write operations: consume 2 tokens

Example:
- 100 reads + 20 writes = 100 + 40 = 140 tokens
- Rate limited if sustained over time
```

### RateLimiter Class

**Per-Tenant Limits:**
```python
check_tenant_limit(tenant_id, operation_type='read'|'write') → bool
require_tenant_limit(...)  # Raises RateLimitError if exceeded
```

**Per-IP Limits (WebUI):**
```python
check_ip_limit(ip_address, limit_type='login'|'signup'|'console') → bool
require_ip_limit(...)  # Raises RateLimitError if exceeded

Limits:
- login: 5 attempts/minute
- signup: 2 attempts/minute  
- console: 30 requests/minute
```

**Features:**
- Automatic token refill
- Time-until-available calculation
- Reset capability (for testing)
- Comprehensive logging

**Usage Example:**
```python
from mcp_server.services.rate_limit import get_rate_limiter

rate_limiter = get_rate_limiter()

# Check limit
if not await rate_limiter.check_tenant_limit(tenant_id, "write"):
    raise RateLimitError("Rate limit exceeded")

# Or require (raises automatically)
await rate_limiter.require_tenant_limit(tenant_id, "write")
```

---

## Logging & Observability

**File:** `mcp_server/utils/logging.py` (101 lines)

### Correlation IDs

**Implementation:**
```python
# Context vars for tracing
correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')
tenant_id_var: ContextVar[str] = ContextVar('tenant_id', default='')
store_id_var: ContextVar[str] = ContextVar('store_id', default='')
tool_name_var: ContextVar[str] = ContextVar('tool_name', default='')
```

**Automatically added to all logs:**
```json
{
  "timestamp": "2025-10-17T12:00:00Z",
  "level": "INFO",
  "message": "Tenant authenticated",
  "correlation_id": "abc-123-def-456",
  "tenant_id": "tenant-uuid",
  "store_id": "store-uuid",
  "tool_name": "stores.register"
}
```

### Secret Redaction

**15+ sensitive field patterns:**
```python
REDACTED_FIELDS = {
    'master_key', 'api_key', 'api_key_ciphertext',
    'password', 'token', 'secret', 'authorization',
    'jwt_secret_key', 'session_token', 'csrf_token',
    'smtp_password', 'webhook_secret', 'mcp_kms_key',
    'sendgrid_api_key', 'postmark_server_token'
}
```

**Redaction Function:**
```python
def redact_secrets(data: Any) -> Any:
    """
    Recursively redact sensitive fields.
    
    - Dict keys matching REDACTED_FIELDS → '[REDACTED]'
    - Long strings (>50 chars) with 'key', 'token', 'secret' → masked
    - Preserves data structure
    """
```

**Example:**
```python
# Before redaction:
{"master_key": "abc123def456", "email": "user@example.com"}

# After redaction:
{"master_key": "[REDACTED]", "email": "user@example.com"}
```

---

## Error Handling

**File:** `mcp_server/models/common.py` (184 lines)

### Exception Hierarchy

```
MCPError (base)
├── OrderDeskError (API errors)
├── ValidationError (input validation)
├── AuthError (authentication/authorization)
├── ConflictError (concurrency conflicts)
├── RateLimitError (rate limiting)
└── NotFoundError (resource not found)
```

### MCPError Base Class

```python
class MCPError(Exception):
    """Base exception with MCP error format."""
    
    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
    
    def to_dict(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details
            }
        }
```

### ValidationError (Helpful Errors)

```python
class ValidationError(MCPError):
    """
    Input validation error with helpful details.
    
    Per specification: List missing fields and provide example.
    """
    
    def __init__(
        self,
        message: str,
        missing_fields: list[str] | None = None,
        invalid_fields: dict[str, str] | None = None,
        example: dict | None = None
    ):
        details = {}
        if missing_fields:
            details["missing_fields"] = missing_fields
        if invalid_fields:
            details["invalid_fields"] = invalid_fields
        if example:
            details["example_request"] = example
        
        super().__init__(code="VALIDATION_ERROR", message=message, details=details)
```

**Example Error Response:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Missing required fields",
    "details": {
      "missing_fields": ["store_id", "api_key"],
      "example_request": {
        "store_id": "12345",
        "api_key": "your-api-key",
        "store_name": "my-store"
      }
    }
  }
}
```

### Result Envelope

```python
class Result[T](BaseModel):
    """Standard result envelope for MCP responses."""
    
    status: Literal["success", "error"]
    data: T | None = None
    error: dict | None = None
    
    @classmethod
    def success(cls, data: T) -> "Result[T]":
        return cls(status="success", data=data)
    
    @classmethod
    def failure(cls, error: MCPError) -> "Result[T]":
        return cls(status="error", error=error.to_dict()["error"])
```

---

## Docker & CI/CD

### Docker Configuration

**Dockerfile (65 lines):**
```dockerfile
# Multi-stage build
FROM python:3.11-slim as builder
# Install dependencies

FROM python:3.11-slim as runtime
# Copy packages, create non-root user
USER appuser
VOLUME ["/app/data"]
CMD ["python", "-m", "mcp_server.main"]
```

**Features:**
- Multi-stage build (smaller final image)
- Python 3.11-slim base
- Non-root user (appuser)
- Volume for persistent data
- Health check with fallback
- stdio MCP server by default

**docker-compose.yml (57 lines):**
```yaml
services:
  mcp:
    build: .
    volumes:
      - ./data:/app/data
    ports:
      - "${PORT:-8080}:8080"
    
  redis:
    image: redis:7-alpine
    profiles: ["redis"]  # Optional
```

### CI/CD Pipeline

**GitHub Actions (130 lines):**

**5 Jobs:**
1. **lint** - ruff + black
2. **typecheck** - mypy --strict
3. **test** - pytest with >80% coverage
4. **docker** - Build and smoke test
5. **integration** - Optional with OrderDesk credentials

**Coverage Enforcement:**
```yaml
pytest --cov-fail-under=80
```

**Triggers:**
- Push to main/develop
- Pull requests to main

---

## Usage Examples

### Environment Setup

```bash
# 1. Generate encryption key
export MCP_KMS_KEY=$(openssl rand -base64 32)

# 2. Copy environment template
cp .env.example .env

# 3. Edit .env with your MCP_KMS_KEY

# 4. Run server
docker-compose up
# OR
python -m mcp_server.main
```

### Tenant Authentication Flow

```python
from mcp_server.services.tenant import TenantService
from mcp_server.services.session import set_tenant
from mcp_server.auth.crypto import derive_tenant_key
from mcp_server.models.database import get_session_local

# Get database session
db = next(get_session_local()())

# Authenticate
tenant_service = TenantService(db)
tenant = tenant_service.authenticate_or_create(
    master_key="user-provided-key",
    auto_provision=settings.auto_provision_tenant
)

if tenant:
    # Derive encryption key
    tenant_key = derive_tenant_key(master_key, tenant.salt)
    
    # Set session context
    set_tenant(tenant.id, tenant_key)
    
    print(f"Authenticated as tenant: {tenant.id}")
```

### Store Registration Flow

```python
from mcp_server.services.store import StoreService
from mcp_server.services.session import get_tenant_id, get_tenant_key

# Get context
tenant_id = require_auth()  # Raises if not authenticated
tenant_key = get_tenant_key()

# Register store
store_service = StoreService(db)
store = await store_service.register_store(
    tenant_id=tenant_id,
    store_id="12345",
    api_key="your-orderdesk-api-key",
    store_name="production",
    label="Production Store",
    tenant_key=tenant_key
)

print(f"Store registered: {store.store_name}")

# Later: Retrieve and decrypt
credentials = await store_service.get_decrypted_credentials(store, tenant_key)
store_id, api_key = credentials  # Plaintext, in-memory only
```

### Rate Limiting Flow

```python
from mcp_server.services.rate_limit import get_rate_limiter

rate_limiter = get_rate_limiter()

# Check before operation
await rate_limiter.require_tenant_limit(tenant_id, "write")

# Perform operation...

# If rate limited:
# RateLimitError raised with retry_after seconds
```

---

## Architecture Diagram

### Current Implementation

```
┌─────────────────────────────────────────────────────────┐
│                  Configuration Layer                     │
│  config.py (190 lines, 60+ settings, 5 validators)      │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────v────────────────────────────────────┐
│                   Security Layer                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │ crypto.py (242 lines)                              │ │
│  │ - HKDF-SHA256 key derivation                       │ │
│  │ - AES-256-GCM encryption/decryption                │ │
│  │ - Bcrypt master key hashing                        │ │
│  └────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────┐ │
│  │ logging.py (101 lines)                             │ │
│  │ - Correlation ID generation                        │ │
│  │ - Secret redaction (15+ patterns)                  │ │
│  │ - Structured JSON output                           │ │
│  └────────────────────────────────────────────────────┘ │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────v────────────────────────────────────┐
│                  Database Layer                          │
│  database.py (309 lines, 7 tables)                      │
│  - tenants (master_key_hash, salt)                      │
│  - stores (api_key_ciphertext, tag, nonce, store_name)  │
│  - audit_log (correlation_id, source, status)           │
│  - sessions, magic_links, master_key_metadata (WebUI)   │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────v────────────────────────────────────┐
│                   Service Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ session.py   │  │ tenant.py    │  │  store.py    │  │
│  │ (174 lines)  │  │ (134 lines)  │  │ (247 lines)  │  │
│  │ Context mgmt │  │ Auth service │  │ Store CRUD   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────────────────────┐                       │
│  │      rate_limit.py           │                       │
│  │      (211 lines)             │                       │
│  │   Token bucket algorithm     │                       │
│  └──────────────────────────────┘                       │
└─────────────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│              MCP Tools Layer (Pending)                   │
│  routers/stores.py - 6 tools to implement               │
└─────────────────────────────────────────────────────────┘
```

---

## Specification Compliance Matrix

| Requirement | Specification Reference | Implementation | Status |
|-------------|------------------------|----------------|--------|
| HKDF-SHA256 | speckit.specify line 905 | crypto.py:46-69 | ✅ |
| AES-256-GCM | speckit.specify line 931 | crypto.py:71-137 | ✅ |
| Bcrypt hashing | speckit.constitution line 179 | crypto.py:139-170 | ✅ |
| Master key hash only | Non-negotiable #3 | database.py:49 | ✅ |
| API key encryption | speckit.specify line 706 | database.py:75-78 | ✅ |
| Session context | speckit.specify line 339 | session.py:22-42 | ✅ |
| Store by name lookup | speckit.constitution line 104 | store.py:136-149 | ✅ |
| Rate limiting 120 RPM | Q11 decision | rate_limit.py:54 | ✅ |
| Read/Write diff | Q11 decision | rate_limit.py:109-121 | ✅ |
| Correlation IDs | speckit.constitution line 241 | logging.py:16 | ✅ |
| Secret redaction | speckit.constitution line 182 | logging.py:23-49 | ✅ |
| Audit logging | speckit.specify line 726 | database.py:94-124 | ✅ |

**Compliance:** 12/12 = 100% ✅

---

## Next Implementation Steps

### Remaining Phase 1 (3 tasks):

1. **MCP Tools** (`routers/stores.py`)
   - tenant.use_master_key
   - stores.register/list/delete/use_store/resolve
   - JSON schemas with required + examples

2. **Test Suite** (`tests/`)
   - test_crypto.py
   - test_database.py
   - test_tenant.py
   - test_store.py
   - test_session.py
   - test_rate_limit.py
   - test_store_tools.py (integration)

3. **Validation**
   - All tests pass
   - Coverage >80%
   - MCP workflow functional

**Estimated:** ~14 hours

---

## File Inventory

### Configuration & Infrastructure (Phase 0)
- `.gitignore` (195 lines) - Build artifacts, secrets
- `.dockerignore` (65 lines) - Build context optimization
- `.env.example` (152 lines) - Environment template
- `pyproject.toml` (131 lines) - Dependencies, tooling
- `Dockerfile` (65 lines) - Multi-stage build
- `docker-compose.yml` (57 lines) - Orchestration
- `.github/workflows/ci.yml` (130 lines) - CI pipeline

### Core Application (Phase 0-1)
- `mcp_server/config.py` (190 lines) - Settings
- `mcp_server/utils/logging.py` (101 lines) - Logging
- `mcp_server/models/common.py` (184 lines) - Errors
- `mcp_server/models/database.py` (309 lines) - Schema
- `mcp_server/auth/crypto.py` (242 lines) - Encryption
- `mcp_server/services/session.py` (174 lines) - Context
- `mcp_server/services/tenant.py` (134 lines) - Auth
- `mcp_server/services/store.py` (247 lines) - Stores
- `mcp_server/services/rate_limit.py` (211 lines) - Rate limiting

### Documentation (Generated)
- `PHASE0-COMPLETE.md` (321 lines)
- `PHASE0-VALIDATION-REPORT.md` (343 lines)
- `PHASE1-PROGRESS.md` (279 lines)
- `IMPLEMENTATION-STATUS.md` (479 lines)
- `docs/IMPLEMENTATION-GUIDE.md` (this file)

**Total Files:** 24 files, ~4,300 lines (code + docs)

---

**Implementation Guide Complete**  
**Next:** Continue Phase 1 - MCP Tools Implementation

---

