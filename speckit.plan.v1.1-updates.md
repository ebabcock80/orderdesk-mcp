# Plan Updates for v1.1 - WebUI Integration

**Status:** Summary of Required Updates  
**Date:** October 17, 2025

This document summarizes the changes needed to `speckit.plan` to incorporate the optional WebUI component.

---

## Phase Renumbering

**Old Structure:** Phases 0-6  
**New Structure:** Phases 0-7

- Phase 0-4: Unchanged (Bootstrap, Auth, Orders Read, Orders Mutate, Ancillary Resources)
- **Phase 5: EXPANDED** - Now includes WebUI Admin & API Test Console
- **Phase 6: NEW** - Public Signup (optional)
- **Phase 7: RENAMED** - Was Phase 6 (Docs & Examples)

---

## Phase 5: Optional HTTP Adapter & WebUI (EXPANDED)

Replace existing Phase 5 content with:

**Goal:** Add optional HTTP transport, WebUI admin interface, API Test Console, and trace viewer.

### New Tasks to Add:

#### 5.7 WebUI Foundation
- [ ] Create `webui/` package structure
- [ ] Implement session management (JWT tokens, secure cookies)
- [ ] Implement CSRF protection middleware
- [ ] Implement rate limiting for WebUI (login: 5/min, signup: 2/min)
- [ ] Choose tech stack (per clarify doc Q6):
  - Server-rendered (Jinja2) OR
  - HTMX + Tailwind OR
  - React/Vite SPA
- [ ] Write tests: `tests/test_webui_security.py`

#### 5.8 WebUI Login (Magic Link)
- [ ] Implement `webui/routes/auth.py`:
  - `POST /auth/login` - Send magic link to email
  - `GET /auth/verify/{token}` - Verify magic link, create session
  - `POST /auth/logout` - Destroy session
- [ ] Implement `services/email.py`:
  - Email provider abstraction (SMTP, SendGrid, Postmark per clarify doc Q4)
  - Magic link generation (secure random token)
  - Token hashing and storage
  - 15-minute expiry
- [ ] Create email templates (`webui/templates/emails/`):
  - `login_magic_link.html`
  - `login_magic_link.txt`
- [ ] Write tests: `tests/test_webui_auth.py`

#### 5.9 WebUI Store Management
- [ ] Implement `webui/routes/stores.py`:
  - `GET /stores` - List user's stores
  - `GET /stores/new` - Store registration form
  - `POST /stores` - Register new store
  - `GET /stores/{id}` - Store details
  - `POST /stores/{id}/edit` - Update store metadata
  - `POST /stores/{id}/test` - Test store credentials
  - `POST /stores/{id}/delete` - Delete store registration
- [ ] Create HTML templates:
  - `webui/templates/stores/list.html`
  - `webui/templates/stores/new.html`
  - `webui/templates/stores/detail.html`
- [ ] Write tests: `tests/test_webui_stores.py`

#### 5.10 API Test Console
- [ ] Implement `webui/routes/console.py`:
  - `GET /console` - API test console UI
  - `POST /console/execute` - Execute API call
  - `GET /console/schemas` - Get tool schemas
  - `GET /console/templates` - List saved templates
  - `POST /console/templates` - Save request template
- [ ] Console features:
  - Store selector dropdown
  - Tool/endpoint selector
  - Dynamic parameter form (from JSON schema OR hand-crafted per clarify doc Q23)
  - Execute button
  - Response display:
    - Status code and message
    - Response body (syntax-highlighted JSON)
    - Duration (ms)
    - Correlation ID
    - Request/response headers (redacted)
    - Copy as cURL button
    - Save as template button
- [ ] Create templates:
  - `webui/templates/console/index.html`
  - `webui/templates/console/response.html`
- [ ] Write tests: `tests/test_api_console.py`

#### 5.11 Trace Viewer
- [ ] Implement `webui/routes/traces.py`:
  - `GET /traces` - Trace viewer UI
  - `GET /api/traces` - Query audit logs (JSON API)
  - Filters:
    - Tenant (auto-filtered to current user)
    - Store
    - Tool name
    - Status (success/error)
    - Date range
    - Full-text search (optional per clarify doc Q21)
- [ ] Display fields:
  - Timestamp
  - Tool name
  - Store
  - Status (success/error badge)
  - Duration (ms)
  - Correlation ID (clickable to see details)
  - Request parameters (redacted)
  - Error message (if error)
- [ ] Create templates:
  - `webui/templates/traces/index.html`
  - `webui/templates/traces/detail.html`
- [ ] Write tests: `tests/test_trace_viewer.py`

#### 5.12 Audit Service
- [ ] Implement `services/audit.py`:
  - Log all tool calls (MCP and WebUI)
  - Store: tenant_id, store_id, tool_name, params (redacted), status, duration, correlation_id, source ('mcp' or 'webui'), ip_address, user_agent
  - Query API with filters
  - Retention policy (default 90 days per clarify doc Q16)
  - Export (JSON/CSV)
- [ ] Write tests: `tests/test_audit_service.py`

#### 5.13 WebUI Security Hardening
- [ ] Content Security Policy headers
- [ ] HSTS header (if behind HTTPS proxy)
- [ ] X-Frame-Options: DENY
- [ ] X-Content-Type-Options: nosniff
- [ ] Secure session cookie configuration
- [ ] CSRF token validation on all POST/PUT/DELETE
- [ ] Rate limiting per IP and per tenant
- [ ] Input sanitization
- [ ] Write tests: `tests/test_webui_security.py`

### Updated Exit Criteria:

✅ **Must Pass:**
1. stdio transport still works (primary path)
2. `GET /health` returns 200 OK
3. SSE transport functional (if implemented)
4. WebSocket transport functional (if implemented)
5. **WebUI login flow works (email → magic link → session)**
6. **WebUI store management CRUD functional**
7. **API Test Console executes orders.list with all parameters**
8. **API Test Console displays raw request/response**
9. **Trace viewer shows filterable logs**
10. **CSRF protection working on all state-changing requests**
11. **Rate limiting enforced (login: 5/min, signup: 2/min)**
12. Test coverage > 70% for HTTP adapter and WebUI

✅ **Validation:**
```bash
# stdio still primary
echo '{"method":"tools/list"}' | python -m mcp_server.main

# HTTP health check
curl http://localhost:8080/health

# WebUI smoke test (manual)
1. Open http://localhost:8080/
2. Enter email for magic link
3. Click link in email
4. Navigate to stores, register a store
5. Navigate to API console
6. Execute orders.list with limit=10
7. Verify response displays correctly
8. Navigate to traces, filter by tool
9. Verify logs appear

# E2E test (Playwright per clarify doc Q30)
pytest tests/e2e/test_webui_flow.py --headed
```

---

## Phase 6: Optional Public Signup (NEW)

**Goal:** Enable self-service tenant creation with master key issuance and recovery.

**Note:** This phase requires Phase 5 (WebUI) completion. Only implement if `ENABLE_PUBLIC_SIGNUP=true` is desired.

### Tasks:

#### 6.1 Signup Flow
- [ ] Implement `webui/routes/auth.py` additions:
  - `GET /auth/signup` - Signup form
  - `POST /auth/signup` - Send signup magic link
  - `GET /auth/signup/verify/{token}` - Verify email, create tenant
  - Display master key ONCE (cannot be retrieved later)
  - Prompt user to save key securely
- [ ] Generate strong master key (32+ bytes, cryptographically random)
- [ ] Create tenant record (master_key_hash, salt)
- [ ] Email template:
  - `webui/templates/emails/signup_magic_link.html`
- [ ] Write tests: `tests/test_signup.py`

#### 6.2 Master Key Metadata
- [ ] Implement `services/master_key.py`:
  - Store master key prefix (first 8 chars) for identification
  - Store optional label (e.g., "Production Key")
  - Track created_at, last_used_at
  - Support revocation (revoked, revoked_at, revoked_reason)
- [ ] Never store full master key (only hash)
- [ ] Write tests: `tests/test_master_key_metadata.py`

#### 6.3 Master Key Rotation
- [ ] Implement `webui/routes/settings.py`:
  - `GET /settings/keys` - List master keys (show prefix, label, last_used, status)
  - `POST /settings/keys/generate` - Generate new master key
  - Display new key ONCE
  - Grace period: old key valid for 7 days (per clarify doc Q8)
  - `POST /settings/keys/{id}/revoke` - Revoke master key
  - `POST /settings/keys/{id}/label` - Update key label
- [ ] Warn active sessions when key approaching revocation
- [ ] Write tests: `tests/test_key_rotation.py`

#### 6.4 Recovery Mechanism (Optional)
- [ ] Implement account recovery via email:
  - `POST /auth/recover` - Send recovery link
  - `GET /auth/recover/verify/{token}` - Verify and show recovery options
  - Option 1: Generate new master key (old one revoked)
  - Option 2: Display recovery codes (if set during signup)
- [ ] Write tests: `tests/test_recovery.py`

#### 6.5 Signup Rate Limiting
- [ ] Per-IP limits: 2 signups per minute (per clarify doc Q11)
- [ ] Email verification (optional, per clarify doc Q5):
  - If `REQUIRE_EMAIL_VERIFICATION=true`, send verification email
  - Tenant account inactive until verified
- [ ] Abuse prevention:
  - Block disposable email domains (optional)
  - Honeypot field (bot detection)
  - reCAPTCHA integration (optional)
- [ ] Write tests: `tests/test_signup_security.py`

### Exit Criteria:

✅ **Must Pass:**
1. Signup flow works (email → magic link → account creation → master key display)
2. Master key displayed ONCE, then never again
3. Master key prefix shown in settings for identification
4. New master key generation works
5. Master key rotation with grace period works
6. Old key becomes invalid after grace period
7. Revoked keys rejected immediately
8. Signup rate limiting enforced (2/min per IP)
9. Email verification works (if enabled)
10. Account recovery flow works (if implemented)
11. Test coverage > 80% for signup flow

✅ **Validation:**
```bash
# E2E signup test
pytest tests/e2e/test_signup_flow.py

# Manual validation:
1. Navigate to /auth/signup
2. Enter email
3. Receive magic link
4. Click link
5. Verify new master key displayed (save it)
6. Verify key NOT displayed again
7. Test master key works for login
8. Generate second key
9. Test both keys work during grace period
10. Revoke old key
11. Verify old key rejected
```

---

## Phase 7: Docs & Examples (RENAMED from Phase 6)

**Goal:** Comprehensive documentation enabling first-run success without maintainer support.

### Additional Tasks for WebUI:

#### 7.7 WebUI Documentation
- [ ] Update README with WebUI instructions:
  - Enable WebUI: `ENABLE_WEBUI=true`
  - SMTP configuration
  - First-time setup walkthrough
  - Screenshots (optional)
- [ ] Create `docs/WEBUI_GUIDE.md`:
  - Features overview
  - Login process
  - Store management
  - API Test Console usage
  - Trace viewer usage
  - Master key management
  - Security best practices
- [ ] Add WebUI environment variables to `.env.example`
- [ ] Create video walkthrough (optional, 3-5 minutes)

#### 7.8 API Test Console Examples
- [ ] Create example request templates:
  - `examples/console/orders_list_paginated.json`
  - `examples/console/orders_mutate_full.json`
  - `examples/console/products_list.json`
  - `examples/console/shipments_create.json`
- [ ] Document how to import templates

### Updated Exit Criteria:

Add to existing Phase 6 exit criteria:
- [ ] WebUI documentation complete (setup, usage, security)
- [ ] WebUI walkthrough enables first use in <2 min
- [ ] API Test Console examples provided
- [ ] Screenshots or video guide available

---

## Updated Cross-Cutting Checklists

Add to existing checklists:

### Security Checklist (for ALL phases):
- [ ] WebUI routes protected by authentication
- [ ] CSRF tokens on all state-changing forms
- [ ] Rate limiting per IP and per tenant
- [ ] Session cookies secure (HttpOnly, Secure, SameSite=Strict)
- [ ] Magic links expire in 15 minutes
- [ ] Master keys never logged or displayed after initial issuance
- [ ] Audit log captures all admin actions

### Testing Checklist (for WebUI phases):
- [ ] Unit tests for services (email, auth, audit)
- [ ] Integration tests for routes
- [ ] E2E tests for full flows (Playwright)
- [ ] Security tests (CSRF, rate limiting, session management)
- [ ] Accessibility tests (WCAG 2.1 Level AA)

---

## Implementation Notes

1. **Decision Required:** Review `speckit.clarify` and answer critical questions before starting Phase 5
2. **Feature Flag:** WebUI disabled by default (`ENABLE_WEBUI=false`)
3. **Phased Approach:** 
   - Phase 5 minimum: HTTP adapter + login + store management + console
   - Phase 6 optional: Public signup
4. **Testing Strategy:** 
   - Unit tests for each service
   - Integration tests for each route
   - E2E tests for critical flows
5. **Documentation:** Update docs as features complete (ongoing from Phase 2)

---

**END OF UPDATE SUMMARY**

**Next Steps:**
1. Answer critical questions in `speckit.clarify`
2. Apply these updates to `speckit.plan`
3. Update `speckit.tasks` with granular WebUI tasks
4. Begin Phase 0 implementation

