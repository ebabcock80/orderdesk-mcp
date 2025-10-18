# Authentication System Explained

**Understanding the different keys in OrderDesk MCP Server**

---

## 🔑 Types of Keys

### **1. Master Key** (Your Login Password)

**What it is:**
- Your personal login password for the WebUI
- 64-character cryptographically secure string
- Like: `VNS09qKDdt-_jC1tai-nIdrq3xUIfxihsCQWC5F1mGUoJmtsEjWwJprFuAztTFHD`

**What it's for:**
- ✅ Logging into the WebUI
- ✅ Authenticating with MCP tools
- ✅ Your personal account access

**How to get one:**
- **Option 1:** Generate it yourself:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
  Then login with it (auto-provisions account on first use)

- **Option 2:** Use public signup (Phase 6):
  - Visit http://localhost:8080/webui/signup
  - Verify your email
  - Master key shown once (save it!)

**Security:**
- Never stored in plaintext
- Hashed with bcrypt before storage
- If you lose it, you lose access (cannot recover)

---

### **2. JWT_SECRET_KEY** (Internal System Secret)

**What it is:**
- Internal secret for signing JWT session tokens
- Lives in `.env` file
- Like: `dGVzdC1qd3Qtc2VjcmV0LWtleS1mb3ItZGV2ZWxvcG1lbnQ...`

**What it's for:**
- ✅ Signing JWT tokens for WebUI sessions
- ✅ Verifying session cookies
- ❌ **NOT for user login**

**How to generate:**
```bash
openssl rand -base64 48
```

**Security:**
- Keep it secret
- Don't share it
- Rotate it periodically in production

---

### **3. MCP_KMS_KEY** (Internal System Secret)

**What it is:**
- Internal key for deriving per-tenant encryption keys
- Lives in `.env` file
- Like: `dGVzdC1rbXMta2V5LWZvci1kZXZlbG9wbWVudC0zMi1ieXRlcy1taW5pbXVt`

**What it's for:**
- ✅ Deriving per-tenant encryption keys (HKDF-SHA256)
- ✅ Encrypting OrderDesk API keys in database
- ❌ **NOT for user login**

**How to generate:**
```bash
openssl rand -base64 32
```

**Security:**
- Keep it secret
- Never rotate it (would invalidate all encrypted data)
- Backup securely

---

## 🎯 Quick Summary

| Key Type | Purpose | Where It Goes | Can You Login With It? |
|----------|---------|---------------|------------------------|
| **Master Key** | User login password | WebUI login form | ✅ **YES!** This is your password |
| JWT_SECRET_KEY | Sign session tokens | `.env` file | ❌ NO - internal use only |
| MCP_KMS_KEY | Encrypt API keys | `.env` file | ❌ NO - internal use only |

---

## 🚀 How to Login

### **Method 1: Generate Your Own Master Key**

```bash
# Step 1: Generate a master key
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# Step 2: Copy the output (64 characters)

# Step 3: Visit the login page
open http://localhost:8080/webui/login

# Step 4: Paste your master key and click "Sign in"
# Your account is auto-created on first login!
```

---

### **Method 2: Use Public Signup** (Phase 6)

```bash
# Step 1: Visit signup page
open http://localhost:8080/webui/signup

# Step 2: Enter your email

# Step 3: Check Docker logs for verification link
docker-compose logs | grep "/webui/verify/" | tail -1

# Step 4: Click the verification link

# Step 5: Save your master key (shown once!)

# Step 6: Login with your master key
```

---

## ❌ Common Mistakes

### **Mistake #1: Using JWT_SECRET_KEY to login**
```
❌ Wrong: Paste JWT_SECRET_KEY in login form
✅ Right: Generate a new master key with secrets.token_urlsafe(48)
```

### **Mistake #2: Using MCP_KMS_KEY to login**
```
❌ Wrong: Paste MCP_KMS_KEY in login form
✅ Right: Generate a new master key with secrets.token_urlsafe(48)
```

### **Mistake #3: Expecting pre-created accounts**
```
❌ Wrong: Looking for default username/password
✅ Right: Create your own master key → Login → Account auto-created
```

---

## 🔐 Security Model

**How it works:**

1. **You generate a master key** (64-char random string)
2. **You login with it** for the first time
3. **System auto-provisions your account:**
   - Hashes your master key (bcrypt)
   - Stores hash in database (NOT the key itself!)
   - Creates your tenant record
   - Generates your encryption salt
4. **Future logins:**
   - You provide master key
   - System hashes it
   - Compares hash to stored hash
   - If match → login successful ✅

**The master key is YOUR password!**
- You create it
- You own it
- You control it
- System never stores it in plaintext

---

## 🎯 Your Master Key from This Session

**Your master key (generated just now):**
```
VNS09qKDdt-_jC1tai-nIdrq3xUIfxihsCQWC5F1mGUoJmtsEjWwJprFuAztTFHD
```

**To login:**
1. Visit: http://localhost:8080/webui/login
2. Paste: `VNS09qKDdt-_jC1tai-nIdrq3xUIfxihsCQWC5F1mGUoJmtsEjWwJprFuAztTFHD`
3. Click: "Sign in"
4. ✅ You're in!

**Save this master key somewhere safe!**

---

## 💡 Pro Tip

**The `.env` file contains:**
- System configuration (ports, timeouts, etc.)
- Internal secrets (JWT, KMS)
- Feature flags (ENABLE_WEBUI, ENABLE_PUBLIC_SIGNUP)

**The `.env` file does NOT contain:**
- User passwords/master keys
- User accounts
- User data

**User data is stored in:**
- SQLite database (`data/app.db`)
- Master keys are bcrypt hashed
- OrderDesk API keys are AES-256-GCM encrypted

---

## 🎉 Ready to Test!

**Use the master key above to login now:**
http://localhost:8080/webui/login

**Or try public signup:**
http://localhost:8080/webui/signup

**Logs are monitoring in background!** ✅

