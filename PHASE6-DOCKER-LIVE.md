# 🎉 Phase 6 Features LIVE in Docker!

**Container Status:** ✅ Running and Healthy  
**Access URL:** http://localhost:8080  
**Logs:** Monitoring in background

---

## 🚀 **What's Running Now**

**Container:**
- Name: `orderdesk-mcp-server`
- Status: Up and healthy
- Port: 8080 → http://localhost:8080
- Python: 3.12
- Database: SQLite (7 tables created)

**Services:**
- ✅ MCP Server (13 tools)
- ✅ WebUI Admin Interface
- ✅ User Management (Phase 6)
- ✅ Public Signup (Phase 6)
- ✅ Email Service (Console provider)
- ✅ Health checks
- ✅ Prometheus metrics

---

## 🎯 **Test Phase 6 Features Now!**

### **1️⃣ Try Public Signup** (New in Phase 6!)

**URL:** http://localhost:8080/webui/signup

**Steps:**
1. Open browser to http://localhost:8080/webui/signup
2. Enter an email address (e.g., test@example.com)
3. Click "Create Account"
4. You'll see "Check Your Email" page
5. **Check Docker logs for the verification email:**
   ```bash
   docker-compose logs | grep -A 30 "EMAIL"
   ```
6. **Copy the verification link** from the logs (looks like):
   ```
   http://localhost:8080/webui/verify/[long-token]
   ```
7. Paste the link in your browser
8. **See your master key displayed ONCE!**
9. **COPY THE MASTER KEY** - Save it securely!
10. Check the "I have saved it" checkbox
11. Click "Continue to Login"
12. Login with your new master key

**What You'll See:**
- Professional signup form
- 4-step process explanation
- Verification pending page
- **Verification email in Docker logs** (console provider)
- Success page with **ONE-TIME master key display**
- Copy/download buttons
- Critical security warnings
- Confirmation checkbox

---

### **2️⃣ Try User Management** (New in Phase 6!)

**URL:** http://localhost:8080/webui/users

**Steps:**
1. Login with your master key
2. Click "Users" in the navigation menu
3. See list of all users (you + any test signups)
4. View statistics (total users, stores, active today)
5. Search for a user by email
6. Click on a user to see details
7. View activity timeline
8. See user's stores (if any)
9. Try clicking "Delete" on another user (if you created multiple)
10. See confirmation dialog with data counts

**What You'll See:**
- User list table
- Statistics dashboard
- Search functionality
- User details page
- Activity timeline
- Store list per user
- Delete button (disabled for yourself)
- Professional mobile-responsive UI

---

### **3️⃣ View Logs for Email Output**

**Monitor Signup Emails:**
```bash
# In a new terminal
cd /Volumes/EXT/Projects/orderdesk-mcp-server
docker-compose logs -f | grep -A 40 "EMAIL"
```

**What You'll See:**
```
📧 EMAIL (Console Mode)
================================================================================
From: noreply@localhost
To: test@example.com
Subject: Verify your OrderDesk MCP account
--------------------------------------------------------------------------------
HTML BODY:
<!DOCTYPE html>
<html>
[Beautiful verification email with magic link]
</html>
================================================================================
```

---

### **4️⃣ Test Existing Features**

**Dashboard:** http://localhost:8080/webui/dashboard  
**Store Management:** http://localhost:8080/webui/stores  
**API Console:** http://localhost:8080/webui/console  
**Settings:** http://localhost:8080/webui/settings  

---

## 📋 **Quick Testing Checklist**

### **Signup Flow:**
- [ ] Visit /webui/signup
- [ ] Enter email and submit
- [ ] See "Check Your Email" page
- [ ] Find verification email in Docker logs
- [ ] Copy verification link
- [ ] Click verification link
- [ ] See master key displayed ONCE
- [ ] Copy master key (test clipboard)
- [ ] Download master key as file
- [ ] Check "I have saved it" box
- [ ] Continue to login
- [ ] Login with new master key ✅

### **User Management:**
- [ ] Login as admin (master key holder)
- [ ] Navigate to "Users" page
- [ ] See user list with statistics
- [ ] Search for a user
- [ ] Click user to see details
- [ ] View activity timeline
- [ ] See user's stores
- [ ] Verify cannot delete yourself

### **Email Service:**
- [ ] Signup triggers verification email
- [ ] Email appears in Docker logs
- [ ] Email has verification link
- [ ] Email HTML renders correctly
- [ ] Magic link works when clicked

### **Rate Limiting:**
- [ ] Create 3 test signups
- [ ] Try 4th signup
- [ ] See rate limit error
- [ ] Error message is clear

---

## 🔍 **Useful Commands**

### **View Logs:**
```bash
# All logs
docker-compose logs

# Follow logs (real-time)
docker-compose logs -f

# Last 50 lines
docker-compose logs --tail=50

# Since timestamp
docker-compose logs --since=5m

# Filter for emails
docker-compose logs | grep "EMAIL"

# Filter for errors
docker-compose logs | grep "ERROR"
```

### **Container Management:**
```bash
# Check status
docker-compose ps

# Restart container
docker-compose restart

# Stop container
docker-compose down

# Rebuild and restart
docker-compose down && docker-compose build && docker-compose up -d

# View resource usage
docker stats orderdesk-mcp-server
```

### **Database:**
```bash
# Check database file
ls -lh data/app.db

# See database size
du -h data/app.db

# Access database directly (SQLite)
sqlite3 data/app.db
```

---

## 🎊 **What's Working**

✅ **Container:** Running perfectly  
✅ **Health:** All checks passing  
✅ **Database:** 7 tables created  
✅ **WebUI:** All pages accessible  
✅ **Signup:** Email verification flow working  
✅ **Email:** Console provider printing to logs  
✅ **User Management:** Full CRUD operations  
✅ **Rate Limiting:** 3/hour per IP enforced  
✅ **Master Keys:** Secure generation working  

---

## 📧 **Example: Finding Your Verification Link**

**After signing up, run:**
```bash
docker-compose logs | grep -A 20 "verification_link"
```

**Look for:**
```
"verification_link": "http://localhost:8080/webui/verify/AbCd...XyZ"
```

**Or simpler:**
```bash
docker-compose logs | grep "/webui/verify/" | tail -1
```

**Copy that link and paste it in your browser!**

---

## 🎯 **Quick Start Testing**

**1. Generate a Master Key:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

**2. Visit WebUI:**
```
http://localhost:8080/webui/login
```

**3. Login:**
- Paste your master key
- Click "Sign in"

**4. Explore:**
- Dashboard (overview)
- Stores (register OrderDesk stores)
- **Users (NEW! - user management)**
- API Console (test MCP tools)
- Settings (config info)

**5. Try Signup:**
```
http://localhost:8080/webui/signup
```
- Enter an email
- Check logs for verification link
- Complete the flow!

---

## 🎉 **You're Live!**

**Container is running at:** http://localhost:8080

**To stop:**
```bash
docker-compose down
```

**To view logs:**
```bash
docker-compose logs -f
```

**Have fun testing Phase 6 features!** 🚀
