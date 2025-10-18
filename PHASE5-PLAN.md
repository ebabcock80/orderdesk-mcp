# Phase 5: WebUI Admin Interface

**Status:** In Progress (Started: October 18, 2025)  
**Estimated Duration:** ~50 hours  
**Priority:** High (requested by user)  
**Linear Issue:** EBA-12

---

## 🎯 **Phase Overview**

Build a professional web-based admin interface for OrderDesk MCP Server with:
- Store management (CRUD operations)
- API Test Console (try all MCP tools)
- Audit log viewer with filtering
- Modern, responsive UI
- Secure authentication

**Tech Stack:**
- **Backend:** FastAPI (already in use)
- **Frontend:** HTMX + Jinja2 templates (server-rendered)
- **Styling:** Tailwind CSS
- **Auth:** Master key login + JWT sessions
- **Security:** CSRF, rate limiting, secure cookies

---

## 📋 **Tasks Breakdown (8 Major Components)**

### **Component 1: WebUI Infrastructure** (8h)
**Tasks:**
1. Set up Jinja2 templates directory structure
2. Configure Tailwind CSS integration
3. Create base HTML template with navigation
4. Add static file serving (CSS, JS)
5. Create WebUI router module
6. Add CSRF protection middleware
7. Implement secure session management
8. Create responsive layout components

**Deliverables:**
- `mcp_server/webui/` package
- `mcp_server/templates/` directory
- `mcp_server/static/` directory
- Base template with Tailwind CSS
- CSRF token generation/validation

---

### **Component 2: Authentication UI** (6h)
**Tasks:**
1. Login page (master key input)
2. JWT session creation
3. Session validation middleware
4. Logout functionality
5. Session timeout handling
6. "Remember me" option (optional)
7. Rate limiting on login attempts
8. Secure cookie configuration

**Deliverables:**
- `/login` page
- `/logout` endpoint
- Session middleware
- Login rate limiting (5 attempts/min)

---

### **Component 3: Dashboard Home** (4h)
**Tasks:**
1. Dashboard layout
2. Store count overview
3. Recent activity feed
4. Quick actions (add store, test API)
5. System health indicators
6. Navigation menu
7. User info display
8. Responsive design

**Deliverables:**
- `/` (dashboard) page
- Activity cards
- Navigation component

---

### **Component 4: Store Management UI** (8h)
**Tasks:**
1. Store list page with table
2. Add store form (name, store_id, api_key)
3. Edit store form
4. Delete store confirmation
5. Test store connection button
6. Store details page
7. Search/filter stores
8. Pagination (if many stores)

**Deliverables:**
- `/stores` page (list)
- `/stores/add` page
- `/stores/edit/{id}` page
- `/stores/{id}` page (details)
- CRUD operations via HTMX

---

### **Component 5: API Test Console** (10h)
**Tasks:**
1. Tool selector dropdown (all 13 MCP tools)
2. Dynamic form generation (per tool params)
3. Request builder UI
4. Execute tool button
5. Response display (JSON formatted)
6. Request history (last 10 requests)
7. Copy request/response buttons
8. Error handling display
9. Performance metrics (duration)
10. Example requests per tool

**Deliverables:**
- `/console` page
- Tool execution endpoint
- JSON formatter
- Request history storage

---

### **Component 6: Audit Log Viewer** (6h)
**Tasks:**
1. Audit log table with pagination
2. Filter by tool name
3. Filter by date range
4. Filter by status (success/error)
5. Search by request ID
6. Expandable row details
7. Export to CSV option
8. Auto-refresh toggle

**Deliverables:**
- `/audit` page
- Filtering controls
- Pagination
- CSV export

---

### **Component 7: Settings Page** (4h)
**Tasks:**
1. Settings overview page
2. Display current configuration
3. Cache backend indicator
4. Rate limits display
5. Session timeout info
6. API connection test
7. System info (version, uptime)
8. Clear cache button (admin)

**Deliverables:**
- `/settings` page
- Configuration display
- Cache management

---

### **Component 8: Polish & UX** (4h)
**Tasks:**
1. Error pages (404, 500)
2. Loading states
3. Toast notifications
4. Form validation feedback
5. Keyboard shortcuts
6. Mobile optimization
7. Accessibility (ARIA labels)
8. Dark mode support (optional)

**Deliverables:**
- Error pages
- Loading spinners
- Toast component
- Mobile-responsive

---

## 🗂️ **Directory Structure**

```
mcp_server/
├── webui/
│   ├── __init__.py
│   ├── routes.py           # WebUI endpoints
│   ├── auth.py             # Authentication helpers
│   ├── middleware.py       # CSRF, session validation
│   └── forms.py            # Form models (Pydantic)
├── templates/
│   ├── base.html           # Base template
│   ├── login.html
│   ├── dashboard.html
│   ├── stores/
│   │   ├── list.html
│   │   ├── add.html
│   │   ├── edit.html
│   │   └── details.html
│   ├── console.html
│   ├── audit.html
│   ├── settings.html
│   └── components/
│       ├── nav.html
│       ├── toast.html
│       └── pagination.html
└── static/
    ├── css/
    │   └── tailwind.css
    ├── js/
    │   └── app.js
    └── img/
        └── logo.svg
```

---

## 🔐 **Security Features**

**Authentication:**
- Master key login (not stored in session)
- JWT session tokens (signed, 1h expiry)
- Secure cookies (HttpOnly, Secure, SameSite=Strict)
- Session timeout after inactivity

**CSRF Protection:**
- CSRF token in all forms
- Token validation on all POST/PUT/DELETE
- Token rotation per session

**Rate Limiting:**
- Login: 5 attempts/min per IP
- API Console: 100 requests/min per session
- Form submissions: 10/min per session

**Input Validation:**
- All forms use Pydantic models
- Server-side validation
- Sanitized error messages
- No sensitive data in logs

---

## 🎨 **UI/UX Design Principles**

**Visual:**
- Clean, modern interface (Tailwind CSS)
- Consistent spacing and typography
- Professional color scheme
- Clear visual hierarchy

**Usability:**
- Intuitive navigation
- Minimal clicks to common actions
- Clear feedback on all operations
- Mobile-responsive design

**Performance:**
- Fast page loads (<200ms)
- Optimized static assets
- Lazy loading for large lists
- Minimal JavaScript (HTMX for interactions)

---

## 📊 **Success Criteria**

### **Must Have:**
- ✅ User can log in with master key
- ✅ User can manage stores (CRUD)
- ✅ User can test all 13 MCP tools
- ✅ User can view audit logs
- ✅ Mobile-responsive
- ✅ CSRF protected
- ✅ Rate limited

### **Should Have:**
- ✅ Request history in console
- ✅ Audit log filtering
- ✅ Store connection testing
- ✅ Toast notifications
- ✅ Error handling

### **Nice to Have:**
- ⏳ Dark mode
- ⏳ Keyboard shortcuts
- ⏳ Export audit logs to CSV
- ⏳ Real-time activity updates (SSE)

---

## 🚀 **Implementation Strategy**

### **Sprint 1: Foundation (12h)**
**Focus:** Core infrastructure and authentication
1. ✅ WebUI package structure
2. ✅ Jinja2 + Tailwind setup
3. ✅ Base template
4. ✅ Login page
5. ✅ Session management
6. ✅ CSRF protection

**Goal:** User can log in and see dashboard

---

### **Sprint 2: Store Management (12h)**
**Focus:** Full CRUD for stores
1. ✅ Store list page
2. ✅ Add store form
3. ✅ Edit store form
4. ✅ Delete store
5. ✅ Test connection
6. ✅ Store details page

**Goal:** User can manage stores via web

---

### **Sprint 3: API Console (12h)**
**Focus:** Test all MCP tools
1. ✅ Tool selector
2. ✅ Dynamic form generation
3. ✅ Execute tool
4. ✅ Response display
5. ✅ Request history
6. ✅ Example requests

**Goal:** User can test all tools via web

---

### **Sprint 4: Polish (14h)**
**Focus:** Audit logs, settings, UX
1. ✅ Audit log viewer
2. ✅ Settings page
3. ✅ Error pages
4. ✅ Toast notifications
5. ✅ Mobile optimization
6. ✅ Final polish

**Goal:** Production-ready WebUI

---

## 📝 **Dependencies**

**Completed:**
- ✅ Phase 1: Auth & Storage (tenant, store management backend)
- ✅ Phase 2-4: MCP tools (all 13 tools to test)
- ✅ Audit logging (database schema ready)

**New Dependencies:**
- `jinja2` - Template engine (already in pyproject.toml)
- `python-jose` - JWT tokens (already in pyproject.toml)
- `itsdangerous` - CSRF tokens (new)
- Tailwind CSS (CDN or build)

---

## ✅ **Getting Started**

**Next Steps:**
1. Create WebUI package structure
2. Set up Jinja2 templates
3. Add Tailwind CSS
4. Build login page
5. Implement session management

**Estimated:** Sprint 1 (12 hours) for functional login and dashboard

---

**Status:** ✅ **READY TO START**  
**First Task:** Create WebUI infrastructure  
**Goal:** Production-ready admin interface for OrderDesk MCP Server

Let's build an amazing web interface! 🚀

