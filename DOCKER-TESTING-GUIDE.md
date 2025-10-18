# Docker Testing Guide - Phase 6 Features

**Container Status:** ✅ Running  
**Health:** ✅ Healthy  
**Access URL:** http://localhost:8080

---

## 🚀 Container is Live!

**Quick Status Check:**
```bash
docker-compose ps
# Should show: Up X seconds (healthy)
```

---

## 🧪 Phase 6 Features to Test

### **1. User Management** (`/webui/users`)

**Test Steps:**
1. Visit http://localhost:8080/webui/login
2. Create a master key manually:
   ```bash
   # Generate a master key
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
3. Register the master key (first time it auto-provisions):
   - Login with the master key
   - Go to Dashboard
4. Navigate to "Users" in the menu
5. See user list with your account
6. Click on your user to see details
7. View activity timeline

**What to Test:**
- ✅ User list displays correctly
- ✅ Search functionality works
- ✅ User details show statistics
- ✅ Activity timeline displays
- ✅ Cannot delete yourself (button disabled)
- ✅ Professional UI rendering

---

### **2. Optional Public Signup** (`/webui/signup`)

**Test Steps (With Email Verification):**
1. Visit http://localhost:8080/webui/signup
2. Enter an email address (e.g., test@example.com)
3. Submit the form
4. See "Check your email" page
5. Check Docker logs for verification email:
   ```bash
   docker-compose logs --tail=50 | grep -A 20 "EMAIL"
   ```
6. Copy the verification link from the console output
7. Visit the verification link in browser
8. See success page with **ONE-TIME master key display**
9. Copy or download the master key
10. Check the "I have saved it" checkbox
11. Click "Continue to Login"
12. Login with the master key you just saved

**What to Test:**
- ✅ Signup form displays
- ✅ Email validation works
- ✅ Verification email sent (check console output)
- ✅ Magic link works
- ✅ Master key generated (64 chars)
- ✅ Master key displayed once with warnings
- ✅ Copy to clipboard works
- ✅ Download as text file works
- ✅ Confirmation required before proceeding
- ✅ Can login with new master key

---

### **3. Email Service** (Console Provider Active)

**Test Steps:**
1. Trigger a signup (as above)
2. Monitor Docker logs:
   ```bash
   docker-compose logs -f
   ```
3. Look for email output in logs

**What to See:**
```
📧 EMAIL (Console Mode)
================================================================================
From: noreply@localhost
To: test@example.com
Subject: Verify your OrderDesk MCP account
--------------------------------------------------------------------------------
HTML BODY:
[Beautiful HTML email with verification link]
================================================================================
```

**What to Test:**
- ✅ Email service initializes
- ✅ Console provider prints emails to logs
- ✅ Email templates render correctly
- ✅ Verification links are generated
- ✅ Master key warnings included

---

### **4. Rate Limiting** (3 signups/hour)

**Test Steps:**
1. Try to sign up 4 times with different emails quickly
2. 4th attempt should show rate limit error
3. Check error message: "Rate limit exceeded..."

**What to Test:**
- ✅ First 3 signups allowed
- ✅ 4th signup blocked
- ✅ Error message clear and helpful
- ✅ Retry message displayed

---

## 📊 Monitoring

### **Watch Logs in Real-Time:**
```bash
docker-compose logs -f
```

### **Check Container Health:**
```bash
docker-compose ps
# Look for: (healthy) status
```

### **Health Endpoint:**
```bash
curl http://localhost:8080/health
# Should return: {"status": "ok", ...}
```

### **Detailed Health:**
```bash
curl http://localhost:8080/health/detailed
# Shows: database, cache, system info
```

---

## 🔍 What to Look For in Logs

### **Successful Startup:**
```json
{"message": "Starting OrderDesk MCP Server", "event": "application_startup"}
{"event": "Initializing database schema"}
{"event": "Database initialized", "tables_created": [...]}
{"message": "Database tables created"}
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8080
```

### **Signup Flow (Console Email):**
```
{"email": "user@example.com", "purpose": "email_verification", "event": "Magic link generated"}
📧 EMAIL (Console Mode)
Subject: Verify your OrderDesk MCP account
[Verification link printed]
```

### **Account Creation:**
```
{"email": "user@example.com", "tenant_id": "...", "event": "Account created via public signup"}
```

### **User Management:**
```
{"user_id": "...", "deleted_by": "...", "event": "User deleted via WebUI"}
```

---

## 🎯 Full Feature Test Checklist

### **User Management:**
- [ ] Login with master key
- [ ] Navigate to Users page
- [ ] See user list with statistics
- [ ] Search users by email
- [ ] View user details
- [ ] See activity timeline
- [ ] View user's stores
- [ ] Try to delete yourself (should be prevented)

### **Public Signup:**
- [ ] Visit signup page
- [ ] Submit with email
- [ ] See verification pending page
- [ ] Check logs for verification email
- [ ] Copy verification link from logs
- [ ] Visit verification link
- [ ] See success page with master key
- [ ] Copy master key
- [ ] Download master key as text
- [ ] Confirm saved checkbox
- [ ] Continue to login
- [ ] Login with new master key

### **Email Service:**
- [ ] Verification email sent to console
- [ ] Welcome email sent to console
- [ ] Email templates render correctly
- [ ] Magic links generated
- [ ] Links work when clicked

### **Rate Limiting:**
- [ ] First 3 signups work
- [ ] 4th signup blocked
- [ ] Error message displayed
- [ ] Reset after 1 hour

---

## 🛑 Troubleshooting

### **Container Keeps Restarting:**
```bash
# Check logs for errors
docker-compose logs --tail=100

# Common issues:
# - Database permission errors
# - Missing .env file
# - Invalid configuration
```

### **Can't Access WebUI:**
```bash
# Check if container is running
docker-compose ps

# Check if port 8080 is accessible
curl http://localhost:8080/health

# Check firewall rules
```

### **Signup Not Working:**
```bash
# Verify ENABLE_PUBLIC_SIGNUP=true in .env
# Check logs for email output
docker-compose logs -f | grep "EMAIL"
```

---

## 🎊 Container Status

**Current Status:**
```
✅ Container: Running
✅ Health: Healthy
✅ Port: 8080 mapped to localhost
✅ Database: Initialized (7 tables)
✅ WebUI: Accessible
✅ Signup: Enabled and working
✅ Email: Console provider active
```

**Access Points:**
- WebUI: http://localhost:8080/webui
- Health: http://localhost:8080/health
- Metrics: http://localhost:8080/metrics
- Signup: http://localhost:8080/webui/signup

---

## 🎉 Ready to Test!

**All Phase 6 features are live and ready to test in Docker!**

1. Visit http://localhost:8080/webui/login
2. Try the signup flow at http://localhost:8080/webui/signup
3. Test user management after logging in
4. Monitor logs with `docker-compose logs -f`

**Happy testing!** 🚀
