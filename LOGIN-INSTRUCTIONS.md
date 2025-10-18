# Quick Login Instructions

**Admin Account:** ✅ Created  
**Container:** ✅ Running  
**Access:** http://localhost:8080

---

## 🔑 Your Admin Master Key

```
dev-admin-master-key-change-in-production-VNS09qKDdt
```

**This is in your `.env` file as `ADMIN_MASTER_KEY`**

---

## 🚀 Login Steps

1. **Open browser:**  
   http://localhost:8080/webui/login

2. **Paste this master key:**  
   `dev-admin-master-key-change-in-production-VNS09qKDdt`

3. **Click "Sign in"**

4. **✅ You're in!**

---

## 📍 What You'll See After Login

- **Dashboard** - Overview and quick actions
- **Stores** - Register OrderDesk stores
- **Users** ⭐ - User management (Phase 6!)
- **API Console** - Test all 13 MCP tools
- **Settings** - Configuration info

---

## 🎯 Your Admin Account

- **Email:** admin@localhost
- **Master Key:** From `.env` file (`ADMIN_MASTER_KEY`)
- **Auto-created:** On startup
- **Access:** Guaranteed (can't be locked out!)

---

## 🧪 Test Phase 6 Features

### **User Management:**
1. After login, click "Users"
2. See your admin@localhost account
3. View statistics and details

### **Public Signup:**
1. Open incognito window
2. Visit http://localhost:8080/webui/signup
3. Create test account
4. Check logs for verification link
5. Complete signup flow

### **As Admin:**
- View all users
- Delete test users
- Monitor activity
- See statistics

---

## 📧 Finding Verification Links (for Signup Testing)

```bash
docker-compose logs | grep "/webui/verify/" | tail -1
```

Look for a link like:
```
http://localhost:8080/webui/verify/AbCdEf123...XyZ789
```

---

## 🎊 You're All Set!

**Login now:** http://localhost:8080/webui/login  
**Master Key:** `dev-admin-master-key-change-in-production-VNS09qKDdt`

**Docker logs monitoring in background!** ✅
