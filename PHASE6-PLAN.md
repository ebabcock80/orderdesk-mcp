# Phase 6: User Management + Optional Public Signup

**Status:** In Progress (Started: October 18, 2025)  
**Estimated Duration:** ~25 hours (updated from 20h)  
**Priority:** High (user requested)  
**Linear Issue:** EBA-13

---

## 🎯 **Phase Overview**

Implement comprehensive user management for master key holders, plus optional public signup flow with email verification. The signup feature can be toggled on/off, making the system flexible for both private and public deployments.

**Key Requirements:**
1. ✅ Public signup is **OPTIONAL** (can be enabled/disabled)
2. ✅ Master key holders can **manage other users**
3. ✅ Users can be **deleted with all their data** (cascade delete)
4. ✅ Email verification for new signups
5. ✅ Secure master key generation

---

## 📋 **Components Breakdown**

### **Component 1: User Management UI** (8h) - **PRIORITY 1**
**For master key holders to manage users**

**Features:**
1. User list page (all tenants)
2. User details page (stores, activity, created date)
3. Delete user button (with confirmation)
4. Cascade delete (user + stores + audit logs + sessions)
5. User statistics (store count, last active)
6. Search/filter users
7. User activity timeline

**Routes:**
- `GET /webui/users` - List all users (admin only)
- `GET /webui/users/{id}` - User details
- `POST /webui/users/{id}/delete` - Delete user and all data
- `GET /webui/users/{id}/stores` - User's stores

**Database:**
- Already have Tenant table
- Add cascade delete support
- Track last_login, last_activity

**Security:**
- Only master key holders can access
- Confirmation dialog for deletion
- Audit log all user management actions
- Cannot delete yourself

---

### **Component 2: Optional Public Signup** (8h) - **PRIORITY 2**
**Togglable via ENABLE_PUBLIC_SIGNUP env var**

**Features:**
1. Signup form (email input)
2. Master key generation (cryptographically secure)
3. Email verification (magic link, 15-min expiry)
4. One-time master key display (copy, download)
5. Rate limiting (3 signups/hour per IP)
6. Email templates (welcome, verification)
7. Signup success page

**Routes:**
- `GET /webui/signup` - Signup form (only if enabled)
- `POST /webui/signup` - Process signup
- `GET /webui/verify/{token}` - Verify email
- `GET /webui/signup/complete` - Show master key once

**Configuration:**
```bash
ENABLE_PUBLIC_SIGNUP=false  # Default: disabled (private mode)
REQUIRE_EMAIL_VERIFICATION=true  # Default: true for security
```

**Flow:**
1. User enters email
2. System generates secure master key
3. Sends verification email with magic link
4. User clicks link
5. System creates tenant
6. Shows master key ONCE (must save)
7. Redirects to login

---

### **Component 3: Email Service** (4h) - **PRIORITY 2**

**Features:**
1. Email service abstraction (multi-provider)
2. SMTP provider (default, via aiosmtplib)
3. Email templates (Jinja2)
4. Verification link generation
5. Error handling and retries

**Providers:**
- SMTP (default)
- SendGrid (optional)
- Postmark (optional)
- Configurable via environment

**Templates:**
- Welcome email with verification link
- Master key notification
- Account created notification

**File Structure:**
```
mcp_server/
├── email/
│   ├── __init__.py
│   ├── service.py         # Email service abstraction
│   ├── providers.py       # SMTP, SendGrid, etc.
│   └── templates/
│       ├── verify_email.html
│       ├── welcome.html
│       └── master_key.html
```

---

### **Component 4: Master Key Management** (5h) - **PRIORITY 3**

**Features:**
1. Master key generation (secure random, 64 chars)
2. Master key validation (strength check)
3. Master key rotation (for existing users)
4. Master key display (one-time, copy/download)
5. Master key recovery warning (cannot recover!)

**Security:**
- Use `secrets.token_urlsafe(48)` for generation
- Display only once (never stored plaintext)
- Warning about saving it securely
- Download as .txt file option
- Copy to clipboard button

---

## 🗂️ **Enhanced Directory Structure**

```
mcp_server/
├── webui/
│   ├── routes.py           # Add user management routes
│   ├── auth.py
│   ├── forms.py            # Signup, user management forms (NEW)
│   └── middleware.py
├── email/                  # NEW package
│   ├── __init__.py
│   ├── service.py
│   ├── providers.py
│   └── templates/
│       ├── verify_email.html
│       ├── welcome.html
│       └── master_key.html
├── templates/
│   ├── users/              # NEW
│   │   ├── list.html
│   │   ├── details.html
│   │   └── delete_confirm.html
│   ├── signup/             # NEW
│   │   ├── form.html
│   │   ├── verify.html
│   │   ├── complete.html
│   │   └── success.html
│   └── ...
```

---

## 🔐 **Security Features**

**User Management:**
- Only master key holders can access user management
- Audit log all user management actions
- Confirmation required for user deletion
- Cannot delete yourself (prevent lockout)
- Display user's stores before deletion

**Public Signup:**
- Rate limiting (3 signups/hour per IP)
- Email verification required (prevent spam)
- CSRF protection on signup form
- Secure master key generation (64 chars, cryptographically secure)
- One-time master key display (cannot recover)

**Master Key Security:**
- Never stored in plaintext (only bcrypt hash)
- Shown only once on signup
- Download option (saves as .txt with warnings)
- Copy to clipboard with security notice
- Clear warning: "Save this now - you cannot recover it"

---

## 📊 **Database Changes**

### **Existing Tenant Table - Add Fields:**
```sql
ALTER TABLE tenants ADD COLUMN email TEXT UNIQUE;  -- Optional, only for signup
ALTER TABLE tenants ADD COLUMN email_verified BOOLEAN DEFAULT false;
ALTER TABLE tenants ADD COLUMN last_login TIMESTAMP;
ALTER TABLE tenants ADD COLUMN last_activity TIMESTAMP;
```

### **Existing MagicLink Table - Already Defined:**
```python
class MagicLink:
    email: str
    token: str
    token_hash: str
    purpose: str  # 'email_verification', 'password_reset', etc.
    tenant_id: int (FK, nullable)
    ip_address: str
    used: bool
    used_at: datetime (nullable)
    expires_at: datetime
    created_at: datetime
```

**Perfect!** Already have what we need in the schema.

---

## 🎨 **UI/UX Flow**

### **User Management (Master Key Holder):**
1. Login with master key
2. Navigate to "Users" in menu
3. See list of all users (email, created, last login, store count)
4. Click user to see details
5. View user's stores
6. Click "Delete User" (shows confirmation)
7. Confirm deletion → Cascade deletes all data
8. Success message → Back to user list

### **Public Signup (If Enabled):**
1. Visit `/webui/signup` (or get 404 if disabled)
2. Enter email address
3. Submit → Receive verification email
4. Click magic link in email
5. System generates master key
6. Display master key with download/copy options
7. User saves master key
8. Redirect to login
9. Login with master key

---

## 🔧 **Environment Variables**

**New Settings:**
```bash
# Public Signup (OPTIONAL - default: disabled)
ENABLE_PUBLIC_SIGNUP=false  # Set to true for public/SaaS mode

# Email Verification (OPTIONAL)
REQUIRE_EMAIL_VERIFICATION=true  # Default: true for security

# Email Service
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-smtp-user
SMTP_PASSWORD=your-smtp-password
SMTP_FROM=noreply@yourdomain.com
SMTP_TLS=true

# Signup Rate Limiting
SIGNUP_RATE_LIMIT=3/hour  # Per IP
SIGNUP_VERIFICATION_EXPIRY=900  # 15 minutes

# Master Key Generation
MASTER_KEY_LENGTH=48  # Results in 64-char URL-safe string
```

---

## 📋 **Implementation Plan**

### **Sprint 1: User Management** (8h) - **START HERE**
**Core admin functionality for master key holders**

1. Add user list page with table
2. Add user details page
3. Add delete user functionality (with cascade)
4. Add user search/filter
5. Test user deletion thoroughly
6. Audit logging for user management

**Deliverables:**
- User management UI (3 pages)
- Delete with cascade
- Audit logging
- Tests

---

### **Sprint 2: Email Service** (4h)
**Email infrastructure for verification**

1. Email service abstraction
2. SMTP provider implementation
3. Email templates (Jinja2)
4. Magic link generation
5. Email sending tests

**Deliverables:**
- Email service module
- SMTP provider
- 3 email templates
- Tests

---

### **Sprint 3: Public Signup** (8h)
**Optional signup flow**

1. Signup form (conditional on ENABLE_PUBLIC_SIGNUP)
2. Master key generation
3. Email verification flow
4. Master key display (one-time)
5. Rate limiting on signup
6. Success/error pages
7. Tests for complete flow

**Deliverables:**
- Signup UI (4 pages)
- Master key generation
- Verification flow
- Tests

---

### **Sprint 4: Polish** (5h)
**Final touches and testing**

1. User management polish
2. Signup flow polish
3. Email template design
4. Security review
5. Integration tests
6. Documentation

**Deliverables:**
- Polished UI
- Complete tests
- Documentation

---

## ✅ **Success Criteria**

**Must Have:**
- ✅ Master key holders can view all users
- ✅ Master key holders can delete users (with cascade)
- ✅ User deletion removes ALL data (stores, audit logs, sessions)
- ✅ Public signup can be enabled/disabled
- ✅ Email verification works
- ✅ Master key displayed once on signup
- ✅ Rate limiting on signup
- ✅ Cannot delete yourself (prevent lockout)

**Should Have:**
- ✅ User search/filter
- ✅ User activity tracking
- ✅ Email templates (professional)
- ✅ Master key download option
- ✅ Audit logging of user management

**Nice to Have:**
- ⏳ Multiple email providers
- ⏳ Email template customization
- ⏳ Bulk user operations

---

## 🚀 **Getting Started**

**Phase 6 Kickoff:**
1. ✅ Linear issue marked "In Progress"
2. → Create PHASE6-PLAN.md (this file)
3. → Start with Sprint 1 (User Management)
4. → Build signup as optional feature

**First Steps:**
1. Add user management routes
2. Create user list UI
3. Implement delete with cascade
4. Test thoroughly

**Estimated:** 8 hours for Sprint 1 (user management)

---

**Status:** ✅ **READY TO START**  
**Next:** Implement user management UI for master key holders  
**Then:** Optional public signup flow

Let's build comprehensive user management! 🚀

