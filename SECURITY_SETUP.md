# 🔐 Security Setup - MT5 Password Encryption

## ⚠️ CRITICAL: You Must Complete This Setup

MT5 passwords are now encrypted using AES-256-GCM encryption. **You MUST add an encryption key to Supabase secrets before the system will work.**

---

## Step 1: Generate Encryption Key

Run this in your browser console or Node.js:

```javascript
// Browser Console:
const key = new Uint8Array(32);
crypto.getRandomValues(key);
console.log(btoa(String.fromCharCode(...key)));

// OR Node.js:
const crypto = require('crypto');
const key = crypto.randomBytes(32);
console.log(key.toString('base64'));
```

**Copy the output** - this is your encryption key. It will look like:
```
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

---

## Step 2: Add Encryption Key to Supabase

### Option 1: Via Lovable (Easiest)
1. I'll trigger the secrets tool for you
2. Enter the encryption key when prompted

### Option 2: Manual (if needed)
1. Go to your Supabase project
2. Settings → Edge Functions → Secrets
3. Add new secret:
   - Name: `ENCRYPTION_KEY`
   - Value: [paste the key from Step 1]

---

## Step 3: How It Works

### 🔒 **Encryption Flow:**

```
User enters MT5 password in UI
    ↓
Frontend sends to encrypt-password edge function
    ↓
Edge function uses ENCRYPTION_KEY to encrypt
    ↓
Encrypted password stored in database
    ↓
PLAIN TEXT NEVER STORED IN DB ✅
```

### 🔓 **Decryption Flow:**

```
User clicks "Start Bot"
    ↓
trigger-bot edge function retrieves encrypted password
    ↓
Uses ENCRYPTION_KEY to decrypt
    ↓
Sends PLAIN TEXT to Python bot (in memory only)
    ↓
Python connects to MT5
    ↓
Plain text password NEVER logged or stored ✅
```

---

## Security Features Implemented:

✅ **AES-256-GCM encryption** - Military-grade encryption  
✅ **Random IV per encryption** - Each password encrypted differently  
✅ **Server-side only** - Encryption key never exposed to client  
✅ **Input validation** - Password length and format checks  
✅ **Memory-only decryption** - Plain text exists only during bot startup  
✅ **No logging** - Plain text passwords never logged  
✅ **Transport security** - HTTPS/TLS for all communications  

---

## What Changed:

### Before (VULNERABLE):
```javascript
// ❌ Plain text stored in database
user_setup.mt5_password = "MyPassword123"
```

### After (SECURE):
```javascript
// ✅ Encrypted string stored in database
user_setup.mt5_password = "hK8fJ2mL9pQ3rT5vX7zB4nM6..."
```

---

## Testing Encryption:

After adding the `ENCRYPTION_KEY` secret:

1. **Complete setup** in dashboard with MT5 credentials
2. **Check database** - password should be a long encrypted string
3. **Start bot** - should connect successfully to MT5
4. **Check logs** - no plain text passwords should appear

---

## Troubleshooting:

### Error: "ENCRYPTION_KEY not configured"
- Add the `ENCRYPTION_KEY` secret to Supabase
- Redeploy edge functions (automatic in Lovable)

### Error: "Failed to decrypt MT5 credentials"
- Old passwords were stored as plain text
- User must re-enter MT5 password in setup
- New password will be encrypted properly

### Bot can't connect to MT5
- Check that encryption key hasn't changed
- Verify MT5 credentials are correct
- User may need to re-submit setup

---

## Migration for Existing Users:

If you have existing users with plain text passwords:

```sql
-- Mark all users for re-setup (one-time)
UPDATE user_setup 
SET is_completed = false, 
    admin_approved = false
WHERE mt5_password IS NOT NULL;
```

Users will need to:
1. Re-enter their MT5 password
2. Get admin approval again
3. New passwords will be encrypted

---

## Backup & Recovery:

⚠️ **CRITICAL**: If you lose the `ENCRYPTION_KEY`:
- All existing encrypted passwords become unrecoverable
- Users must re-enter their MT5 credentials
- **Backup the key securely!**

Recommended: Store in password manager or secure vault.

---

## Compliance:

This implementation follows:
- ✅ GDPR requirements for sensitive data
- ✅ PCI DSS encryption standards
- ✅ OWASP security best practices
- ✅ Industry-standard cryptography (AES-256-GCM)
