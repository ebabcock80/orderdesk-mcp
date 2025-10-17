# Task Breakdown: OrderDesk MCP Server + WebUI

**Version:** 1.1  
**Status:** Active Task List  
**Last Updated:** October 17, 2025  
**Format:** [ID] Title — Detail

**Companion Documents:**
- [`speckit.constitution`](./speckit.constitution) - Design principles
- [`speckit.specify`](./speckit.specify) - Technical specification  
- [`speckit.plan`](./speckit.plan) - Implementation plan with phases
- [`speckit.clarify`](./speckit.clarify) - Clarification questions
- [`speckit.checklist`](./speckit.checklist) - Quality validation

---

## Phase 0: Bootstrap & Infrastructure

### Core Platform

**[BOOT-01] Repository Structure** — Scaffold repo: `mcp_server/{auth,models,routers,services,utils,webui}`, `tests/`, `docs/`, `examples/`  
**[BOOT-02] Docker Setup** — Multi-stage Dockerfile, docker-compose.yml with optional Redis, health check  
**[BOOT-03] CI Pipeline** — GitHub Actions: ruff, mypy, pytest, docker build, coverage report, release tags

**[CORE-ENV] Env & Config** — `.env.example` with all vars; Pydantic BaseSettings loader; validation with helpful errors  
**[CORE-LOG] Logging/Tracing** — Structured JSON logs; correlation IDs (UUID4); tenant/store/tool enrichment; secret redaction filter

**[CORE-ERR] Error Envelopes** — Common exception types (OrderDeskError, ValidationError, AuthError, ConflictError, RateLimitError); MCP error format; helpful messages with examples

---

## Phase 1: Auth, Storage, Session

### Security & Cryptography

**[SEC-CRYPTO] HKDF & AES-GCM** — Derive per-tenant keys via HKDF-SHA256; AES-256-GCM encrypt/decrypt helpers; master key hashing (bcrypt/argon2); tests for deterministic derivation, roundtrip, tampering detection

**[SEC-REDACT] Secret Redaction** — Filter for logs (master_key, api_key, password, token, secret, email optional); apply to all log outputs; verify in tests

### Database & Storage

**[DB-SCHEMA] SQLite Schema** — Create tables: tenants (master_key_hash, salt), stores (api_key_ciphertext, tag, nonce, store_name), audit_log (optional); indices on tenant_id, store_name; constraints (UNIQUE tenant_id+store_name); migrations (Alembic optional)

**[DB-WEBUI] WebUI Tables** — Create tables (if ENABLE_WEBUI=true): sessions (session_token, expires_at), magic_links (token_hash, purpose, used), master_key_metadata (prefix, label, revoked); indices

**[DB-INIT] Database Init** — Engine setup from DATABASE_URL; connection pooling; create_all(); test constraints

### Authentication & Context

**[AUTH-MASTER] Master Key Auth** — TenantService: authenticate(master_key), create_tenant(master_key); bearer token parsing; auto-provision toggle (AUTO_PROVISION_TENANT); tests for success/failure/auto-provision

**[CTX-SESSION] Session Context** — SessionContext: set_tenant(), set_active_store(), get_active_store(), clear(); use async context vars; generate correlation_id; tests for isolation and persistence

**[AUTH-RATE] Rate Limiting** — RateLimiter: sliding window per tenant; default 120 RPM (RATE_LIMIT_RPM); Redis or in-memory backend; tests for under/over limit, sliding window

### Store Management

**[STORE-SERVICE] Store Service** — StoreService: register_store(), list_stores(), get_store_by_name(), resolve_store(), delete_store(), get_decrypted_credentials(); tests for CRUD, encryption verification, duplicate prevention

**[STORE-TOOLS] stores.* MCP Tools** — Implement MCP tools: tenant.use_master_key, stores.register, stores.list, stores.delete, stores.use_store, stores.resolve; JSON schemas with required+examples; tests for full workflow

---

## Phase 2: Order Read Path & Pagination

### OrderDesk HTTP Client

**[HTTP-CLIENT] httpx Client** — OrderDeskClient: async httpx with base URL, headers (ORDERDESK-STORE-ID, ORDERDESK-API-KEY), 30s timeout, connection pooling; error normalization; tests for headers, timeout

**[HTTP-RETRY] Retry Logic** — Retry on 429 (respect X-Retry-After) and 5xx (exponential backoff + jitter); max 3 retries (HTTP_MAX_RETRIES); parse X-Tokens-Remaining; tests for retry scenarios

### OrderDesk Models

**[MODELS-OD] Pydantic Models** — Define models: Address, OrderItem, Order, InventoryItem, Shipment; map ALL fields from OrderDesk API docs; validate against actual OD responses

### Orders Read Operations

**[ORD-READ-GET] orders.get** — Implement orders.get(order_id); cache with 15s TTL; schema with examples; tests for cache hit/miss

**[ORD-READ-LIST] orders.list** — Implement orders.list with OrdersListParams; expose ALL OD filters (folder_id, status, since, sort, limit, page, search); cache list results; tests for default/custom pagination, filters, edge cases

**[ORD-SETTINGS] store.get_settings** — Implement store.get_settings(); cache with 300s TTL; return folders; tests

**[ORD-EXAMPLES] Read Examples** — Create examples: orders_get.json, orders_list.json, orders_list_paginated.json, store_get_settings.json

---

## Phase 3: Full Mutation Pipeline

### Cache Layer

**[CACHE-SERVICE] Cache Service** — CacheService: get(), set(), delete(), delete_pattern(), make_key(); backends: memory (default), Redis (optional); TTL per resource type; tests for backends, TTL, pattern delete

**[CACHE-INVALID] Invalidation Hooks** — Invalidate on writes: order:{id}, orders:list:*, product:{id}, products:list:*; tests for all write paths

### Mutation Engine

**[MUT-ENGINE] Mutation Engine** — MutationEngine: apply_mutation() (deep merge), apply_operations() (typed ops); conflict detection (date_updated comparison); retry loop with exponential backoff + jitter; max 5 retries (MUTATION_MAX_RETRIES); tests for merge logic, operations, retries

**[MUT-OPS] Typed Operations** — Define operations: MoveFolderOp, AddItemsOp, RemoveItemsOp, UpdateAddressOp, SetStatusOp; dispatcher; tests

### Orders Write & Mutate

**[ORD-WRITE] orders.create/update_full/delete** — Implement create, update_full (full replace), delete; cache invalidation; tests

**[ORD-MUTATE] orders.mutate_full** — Implement orders.mutate_full(order_id, mutation? | ops?); use MutationEngine; XOR validation (mutation OR ops); cache invalidation; tests for mutation, ops, concurrent mutations

**[ORD-OPS] Convenience Wrappers** — Implement: orders.move_folder (uses OD batch endpoint), orders.add_items, orders.update_address, orders.create_history; tests

**[MUT-EXAMPLES] Mutation Examples** — Create examples: orders_create.json, orders_mutate_full_mutation.json, orders_mutate_full_ops.json, orders_move_folder.json, orders_add_items.json

---

## Phase 4: Ancillary Resources

### Additional Resources

**[ITEMS-TOOLS] order_items.* Tools** — Implement MCP tools: list, get, create, update, delete; tests

**[SHIP-TOOLS] shipments.* Tools** — Implement MCP tools: list, get, create, update, delete, batch_create; tests

**[PROD-TOOLS] products.* Tools** — Implement MCP tools: list (with ProductsListParams exposing ALL OD params), get, create, update, delete, batch_update; tests

**[FOLD-TOOLS] folders.list Tool** — Implement folders.list (convenience wrapper around store.get_settings); tests

**[ANC-EXAMPLES] Ancillary Examples** — Create examples: order_items_create.json, shipments_create.json, products_list.json, products_create.json

---

## Phase 5: Optional HTTP Adapter & WebUI

### HTTP Adapter (Feature-Flagged)

**[HTTP-ADAPT] FastAPI Adapter** — FastAPI app with /health, /metrics (Prometheus); vendor-agnostic MCP transport foundation; feature flag checks

**[HTTP-SSE] SSE Transport** — Implement GET /mcp/sse with master key auth; stream MCP messages; tests

**[HTTP-WS] WebSocket Transport** — Implement WebSocket /mcp/ws with auth; bidirectional MCP messages; tests (optional, can defer)

**[HTTP-WEBHOOK] Webhook Receiver** — Implement POST /webhooks/orderdesk; signature validation (if WEBHOOK_SECRET set); cache invalidation; tests

**[HTTP-PROXY] Proxy Headers** — Parse X-Forwarded-For, CF-Connecting-IP when TRUST_PROXY=true; middleware to inject client_ip into logs; tests

### WebUI Foundation (Feature-Flagged: ENABLE_WEBUI)

**[UI-SHELL] UI Shell & Layout** — Create webui/ package structure; base template with nav (Admin, API Console, Traces, Settings); auth guard middleware; responsive design (mobile-friendly); choose tech stack (HTMX+Tailwind OR React/Vite per clarify doc Q6)

**[UI-SEC-HEADERS] Security Headers** — CSP default-deny; X-Frame-Options: DENY; X-Content-Type-Options: nosniff; HSTS only if TLS upstream; Referrer-Policy: strict-origin-when-cross-origin; tests

**[UI-SEC-CSRF] CSRF Protection** — Generate CSRF tokens; validate on all POST/PUT/DELETE; synchronizer token pattern; token scoped to session; tests

**[UI-SEC-RATE] WebUI Rate Limiting** — Per-IP rate limits: login 5/min, signup 2/min, console 30/min; per-tenant limits; tests

### WebUI Authentication

**[UI-EMAIL] Email Service** — EmailService: send_magic_link(), generate_token(); provider abstraction (SMTP, SendGrid, Postmark per clarify doc Q4); templates for login/signup; 15min expiry; rate limit per recipient; tests

**[UI-SESSION] Session Service** — SessionService: create_session(), validate_session(), destroy_session(); JWT tokens OR session IDs; secure cookie management (HttpOnly, Secure, SameSite=Strict); 24h timeout (SESSION_TIMEOUT); storage (SQLite or Redis); tests

**[UI-AUTH-LOGIN] Login Flow** — Routes: POST /auth/login (send magic link), GET /auth/verify/{token} (verify, create session), POST /auth/logout; templates: login.html, verify.html; tests for full flow

**[UI-AUTH-TESTS] Auth E2E Tests** — Playwright tests: email → magic link → session → logout; token expiry; rate limiting

### WebUI Store Management

**[UI-STORES] Store Admin UI** — Routes: GET /stores (list), GET /stores/new (form), POST /stores (register), GET /stores/{id} (details), POST /stores/{id}/edit (update metadata), POST /stores/{id}/test (test credentials), POST /stores/{id}/delete; templates; never display plaintext API keys (only show "Encrypted"); tests

**[UI-STORES-TESTS] Store CRUD E2E** — Playwright tests: register store → list → edit label → test credentials → delete

### API Test Console

**[UI-CONSOLE-SHELL] Console Shell** — Route: GET /console; template with 3-column layout (store selector, tool selector, parameter form/response); tests

**[UI-CONSOLE-SCHEMA] Schema Explorer** — GET /api/console/schemas; return all MCP tool schemas; group by resource; display in dropdown/autocomplete

**[UI-CONSOLE-FORM] Request Builder** — Dynamic form generation from JSON Schema OR hand-crafted forms (per clarify doc Q23); all documented OD parameters exposed; required fields marked; help text from descriptions; validation; tests

**[UI-CONSOLE-EXEC] "Try It" Runner** — POST /api/console/execute; intercept request, call OrderDesk API, log to audit, return response; loading indicator; correlation ID; 30s timeout; tests

**[UI-CONSOLE-RESP] Response Display** — Show: status code, status message, response body (syntax-highlighted JSON), duration (ms), correlation ID (linkable to traces), headers (redacted: API keys, show: Content-Type, X-Tokens-Remaining); expandable for large payloads; tests

**[UI-CONSOLE-PAGINATION] Pagination Helpers** — Quick-fill buttons (10/25/50/100); Next/Previous page buttons; "Since" timestamp helper (calendar OR "last hour"); tests

**[UI-CONSOLE-COPY] Copy Functionality** — Buttons: "Copy as cURL" (redact API key with placeholder), "Copy as JSON", "Copy as MCP Tool Call", "Save as Template"; tests

**[UI-CONSOLE-TEMPLATES] Template Management** — Routes: GET /api/console/templates (list), POST /api/console/templates (save), DELETE /api/console/templates/{id}; template CRUD; seed with example templates; tests

**[UI-CONSOLE-TESTS] Console E2E** — Playwright tests: select store → select orders.list → fill params (limit=25) → execute → verify response → copy cURL → save template

### Trace Viewer

**[UI-TRACES] Trace Viewer UI** — Route: GET /traces; template with filter sidebar and table; filters: tenant (auto), store, tool, status, date range, correlation_id; full-text search (optional); tests

**[UI-TRACES-API] Traces Query API** — GET /api/traces; query audit_log with filters; pagination (10/25/50 per page); return: timestamp, tool, store, status, duration, correlation_id; tests

**[UI-TRACES-DETAIL] Trace Detail View** — Modal/page for single trace; show: full request params (redacted), response (if available), error message, stack trace (sanitized), source (MCP/WebUI), IP, user agent, timestamp; tests

**[UI-TRACES-TESTS] Trace Viewer E2E** — Playwright tests: execute API call from console → navigate to traces → filter by tool → click row → verify detail → filter by correlation_id

### Audit Service

**[AUDIT-SERVICE] Audit Service** — AuditService: log_tool_call(), query_logs(); store: tenant_id, store_id, tool_name, params (redacted), status, duration, correlation_id, source ('mcp'|'webui'), ip_address, user_agent; retention policy (90 days default per clarify doc Q16); export (JSON/CSV); tests

**[AUDIT-CLEANUP] Audit Cleanup Job** — Background task to purge old audit logs based on AUDIT_LOG_RETENTION_DAYS; tests

### Settings & Key Management

**[UI-SETTINGS] Settings Page** — Route: GET /settings; template with tabs: Profile, Master Keys, Preferences; tests

**[UI-KEYS-LIST] Master Key Listing** — Display keys: prefix (first 8 chars), label, created_at, last_used_at, status (Active/Expiring/Revoked); never show full key; tests

**[UI-KEYS-GEN] Key Generation** — POST /settings/keys/generate; generate new 32+ byte key; display ONCE with warning; store prefix + metadata; tests

**[UI-KEYS-ROTATE] Key Rotation** — Grace period (7 days per clarify doc Q8); warning banner for expiring keys; tests

**[UI-KEYS-REVOKE] Key Revocation** — POST /settings/keys/{id}/revoke; confirm dialog; revocation reason (optional); tests

**[UI-KEYS-TESTS] Key Management E2E** — Playwright tests: generate key → verify displayed once → verify not visible again → verify prefix in list → rotate → verify grace period → revoke old → verify rejected

---

## Phase 6: Optional Public Signup

### Public Signup (Feature-Flagged: ENABLE_PUBLIC_SIGNUP)

**[SU-MODELS] Signup Models** — Enhance magic_links table with purpose='signup'; enhance master_key_metadata; tests

**[SU-SIGNUP] Signup Flow** — Routes: GET /auth/signup (form), POST /auth/signup (send magic link), GET /auth/signup/verify/{token} (create tenant, display master key ONCE); email validation; disposable domain blocking (optional); honeypot field; tests

**[SU-DISPLAY] Master Key Display** — Show full key ONCE with clear warning; "I have saved this key" checkbox; mask with copy button; never show again; tests

**[SU-RECOVERY] Account Recovery** — Routes: POST /auth/recover (send recovery link), GET /auth/recover/verify/{token} (show options: generate new key OR display recovery codes); tests (optional, can defer)

**[SU-RATE] Signup Rate Limiting** — 2 signups per IP per minute; email verification (if REQUIRE_EMAIL_VERIFICATION=true); CAPTCHA threshold (optional); tests

**[SU-TESTS] Signup E2E** — Playwright tests: signup → receive magic link → verify → save master key → verify can't see again → test login with key

**[SU-DOCS] Signup Documentation** — Document signup flow, key handling, rotation, recovery in README and docs/WEBUI_GUIDE.md

---

## Phase 7: Documentation & Examples

### Documentation

**[DOC-README] README.md** — Quickstart for MCP (stdio, <5min) and WebUI (if enabled, <2min); master key tenancy explanation; full-order mutations; pagination control; Cloudflare Tunnel setup; troubleshooting; screenshots (optional)

**[DOC-ENDPOINTS] endpoints.md** — Complete MCP tools catalog; each tool: name, description, OD endpoint link, parameters table, example request/response, error cases; organized by resource

**[DOC-OPERATIONS] operations.md** — Full-order update contract (fetch→mutate→upload); retry strategy; caching (what, TTLs, invalidation); rate limiting (tenant, OD API, handling 429)

**[DOC-SETUP] SETUP_GUIDE.md** — Deployment scenarios: local dev, Docker Compose, Railway, Render, Fly.io, Cloudflare Tunnel, Kubernetes; environment variables; security best practices; monitoring

**[DOC-WEBUI] WEBUI_GUIDE.md** — WebUI features overview; login process; store management; API Test Console usage; trace viewer; master key management; security best practices; screenshots; video walkthrough (optional, 3-5min)

**[DOC-ENV] .env.example Complete** — All environment variables with descriptions, types, defaults, security notes; grouped: core, WebUI, email, security, cache, resilience

### Examples

**[EX-MCP] MCP Tool Examples** — Create examples/: tenant_use_master_key.json, stores_register.json, orders_get.json, orders_list.json, orders_list_paginated.json, orders_create.json, orders_mutate_full_mutation.json, orders_mutate_full_ops.json, orders_move_folder.json, products_list.json, shipments_create.json

**[EX-CONSOLE] Console Template Examples** — Create examples/console/: orders_list_paginated.json, orders_mutate_full.json, products_list.json, shipments_create.json; format: description, request, response, notes

**[EX-POSTMAN] Postman Collection** — Export Postman/Thunder Client collection with all HTTP routes (if HTTP adapter enabled); environment variables template; optional

---

## Testing & CI

### Unit Tests

**[TEST-CRYPTO] Crypto Tests** — Test: HKDF deterministic, encrypt/decrypt roundtrip, wrong key fails, tag tampering detected; coverage >95%

**[TEST-AUTH] Auth Tests** — Test: master key validation, auto-provision toggle, rate limiting, session context isolation; coverage >90%

**[TEST-STORE] Store Tests** — Test: register (encryption verified), list (no leakage), lookup by name/ID, resolve both, delete, duplicates rejected; coverage >90%

**[TEST-PAGINATION] Pagination Tests** — Test: default params, custom limit/page, boundary cases (page 0, negative, beyond results), invalid values; coverage >90%

**[TEST-MUTATION] Mutation Tests** — Test: deep merge logic, typed operations, conflict detection, retry with backoff, max retries exceeded; coverage >90%

**[TEST-CACHE] Cache Tests** — Test: set/get/delete, TTL expiry, pattern delete, backends (memory, Redis), invalidation on writes; coverage >85%

**[TEST-WEBUI-SEC] WebUI Security Tests** — Test: CSRF token validation, rate limiting (login/signup/console), session timeout, cookie flags (HttpOnly, Secure, SameSite); coverage >85%

**[TEST-WEBUI-EMAIL] Email Tests** — Test: magic link generation, token hashing, expiry, one-time use, provider abstraction; coverage >85%

### Integration Tests (Env-Gated)

**[TEST-INT-ORDERS] Orders Integration** — Test with live OrderDesk API (requires ORDERDESK_TEST_STORE_ID, ORDERDESK_TEST_API_KEY): list with pagination, get, create→mutate→delete, move folder; cleanup after each test

**[TEST-INT-PRODUCTS] Products Integration** — Test with live OD API: list with filters, create→update→delete; cleanup

**[TEST-INT-CACHE] Cache Integration** — Test cache hit/miss for reads, invalidation on writes; can use mock OD responses

### E2E Tests (WebUI)

**[TEST-E2E-AUTH] Auth E2E** — Playwright: login flow (email→magic link→session→logout), token expiry, rate limiting

**[TEST-E2E-STORES] Store Management E2E** — Playwright: register store→list→edit label→test credentials→delete

**[TEST-E2E-CONSOLE] Console E2E** — Playwright: select store→select orders.list→fill params (limit=25)→execute→verify response→copy cURL→save template

**[TEST-E2E-TRACES] Traces E2E** — Playwright: execute API call→navigate to traces→filter by tool→click row→verify detail

**[TEST-E2E-SIGNUP] Signup E2E** — Playwright (if ENABLE_PUBLIC_SIGNUP): signup→magic link→save key→verify not visible again→login with key

**[TEST-E2E-KEYS] Key Management E2E** — Playwright: generate key→verify once→rotate→grace period→revoke→verify rejected

### CI/CD

**[CI-SETUP] GitHub Actions Workflow** — Create .github/workflows/ci.yml: jobs for lint (ruff), format (black), typecheck (mypy), test (pytest with coverage), docker build; run on push/PR; branch protection

**[CI-COVERAGE] Coverage Reporting** — pytest-cov with --cov-fail-under=80; coverage report in PR comments; badge in README

**[CI-RELEASE] Release Automation** — Tag releases (v0.x.y); GitHub release with changelog; Docker image push to GHCR and Docker Hub (per clarify doc Q25)

---

## Task Summary

**Total Tasks:** ~150  
**Categories:** 15  
**Estimated Effort:** 350-400 hours

**Breakdown by Phase:**
- **Phase 0:** 12 tasks (~25 hours) - Bootstrap, config, CI
- **Phase 1:** 20 tasks (~50 hours) - Auth, storage, session, stores
- **Phase 2:** 15 tasks (~35 hours) - Orders read, pagination, cache
- **Phase 3:** 15 tasks (~45 hours) - Mutations, retries, convenience ops
- **Phase 4:** 10 tasks (~25 hours) - Ancillary resources
- **Phase 5:** 35 tasks (~90 hours) - HTTP adapter, WebUI (auth, stores, console, traces, settings)
- **Phase 6:** 10 tasks (~25 hours) - Public signup (optional)
- **Phase 7:** 15 tasks (~30 hours) - Documentation, examples
- **Testing:** 18 tasks (~35 hours) - Unit, integration, E2E tests
- **CI/CD:** 3 tasks (~10 hours) - Pipeline, coverage, releases

---

## Universal Acceptance Criteria (All Tasks)

Every task MUST satisfy:

### Code Quality
- ✅ **Type Hints:** Full type annotations on all functions
- ✅ **Docstrings:** Parameter descriptions and return types
- ✅ **Linting:** Passes `ruff check .` with zero errors
- ✅ **Formatting:** Passes `black --check .` with zero errors
- ✅ **Type Checking:** Passes `mypy --strict mcp_server/` with zero errors

### Testing
- ✅ **Unit Tests:** Happy path, validation errors, edge cases covered
- ✅ **Test Coverage:** >80% overall, >90% for critical paths
- ✅ **Integration Tests:** Env-gated tests with real OrderDesk API (if credentials provided)
- ✅ **E2E Tests:** Playwright tests for WebUI flows

### API & Schema Quality
- ✅ **Complete Schemas:** JSON Schemas include `required` fields and examples
- ✅ **No Invented Params:** All OrderDesk API options present or documented as unsupported
- ✅ **Pagination Exposed:** All list endpoints expose limit, page, since, sort
- ✅ **Validation Errors:** List missing fields and show minimal valid example

### Security
- ✅ **Secrets Redacted:** master_key, api_key, password, token, secret never in logs
- ✅ **Encryption:** API keys encrypted at rest (AES-256-GCM)
- ✅ **Master Keys:** Hashed with strong algorithm (bcrypt/argon2)
- ✅ **WebUI Security:** CSRF tokens, secure cookies, rate limiting, CSP headers
- ✅ **No Plaintext Display:** Master keys shown once, API keys never shown in UI

### MCP Tools
- ✅ **1:1 Mapping:** Every tool maps to documented OrderDesk API endpoint
- ✅ **Full Options:** All documented OD parameters exposed (filters, pagination, sort)
- ✅ **Examples:** At least one example request per tool
- ✅ **Session Context:** Tools use active store when store_name omitted

### WebUI (if enabled)
- ✅ **Console Complete:** Can execute list/mutate requests with all parameters
- ✅ **Response Display:** Shows raw req/resp (headers redacted), status, duration, timing
- ✅ **Pagination Helpers:** Quick-fill buttons, next/previous, timestamp helper
- ✅ **Copy Functions:** cURL, JSON, MCP tool call available
- ✅ **Trace Correlation:** request_id links console executions to trace viewer

### Observability
- ✅ **Correlation IDs:** Every request has unique UUID in logs
- ✅ **Structured Logs:** JSON format with tenant_id, store_id, tool_name, duration_ms
- ✅ **Audit Trail:** All tool calls logged (MCP and WebUI) with source, IP, user agent

---

## Task Prioritization

### Critical (Must Have for v0.1.0)
- All Phase 0-4 tasks (MCP core functionality)
- CORE-*, SEC-*, DB-*, AUTH-*, STORE-*, HTTP-CLIENT, HTTP-RETRY, ORD-*, MUT-*, CACHE-*, AUDIT-*
- DOC-README, DOC-ENDPOINTS, DOC-OPERATIONS
- TEST-CRYPTO, TEST-AUTH, TEST-STORE, TEST-MUTATION, TEST-CACHE
- CI-SETUP, CI-COVERAGE

### Important (Should Have for v0.2.0)
- Phase 5 tasks (HTTP adapter + WebUI)
- HTTP-ADAPT, HTTP-SSE, UI-*, AUDIT-*
- DOC-WEBUI, EX-CONSOLE
- TEST-WEBUI-*, TEST-E2E-*

### Optional (Nice to Have for v0.3.0+)
- Phase 6 tasks (Public Signup)
- SU-*, HTTP-WS
- TEST-E2E-SIGNUP, TEST-E2E-KEYS
- EX-POSTMAN

---

## Next Steps

1. **Answer Clarification Questions** — Review and answer critical questions in `speckit.clarify` (Q1, Q3, Q4, Q6, Q9, Q11, Q13)
2. **Assign Tasks** — Assign owners to tasks, prioritize critical path
3. **Setup Project Board** — Create GitHub project board with columns: Backlog, In Progress, Review, Done
4. **Begin Phase 0** — Start with BOOT-* and CORE-* tasks
5. **Iterate** — Complete each phase before moving to next; validate exit criteria

---

**END OF TASK BREAKDOWN**

