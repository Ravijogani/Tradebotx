# 🔍 Complete System Verification Checklist

## **Current Status:**
- ✅ `encrypt-password` function added to config.toml
- ✅ RLS policies fixed for bot_heartbeats and bot_audit_logs
- ✅ Phantom running bot marked as stopped
- ✅ ENCRYPTION_KEY configured in Supabase

---

## **⚠️ CRITICAL GAPS IDENTIFIED:**

### **1. Python Bot is NOT Running** ❌
**Evidence:**
- `user_strategies.is_running = true` (marked as running)
- `bot_heartbeats` table is EMPTY (no bot ever started)
- Started at 10:59:20, but 1.5 hours later - still no heartbeat

**Root Cause:**
- Python bot likely never received the start command
- AWS Lightsail bot manager probably not set up
- OR bot crashed immediately on startup

### **2. AWS Lightsail Bot Manager Not Verified** ⚠️
**Missing:**
- No evidence that bot_manager_http.py is running on Lightsail
- No proof that HTTP endpoint is accessible
- LIGHTSAIL_BOT_MANAGER_URL and BOT_MANAGER_SECRET configured but untested

### **3. Password Encryption Not Tested** ⚠️
**Risk:**
- Existing user setup likely has PLAIN TEXT password
- Encryption function just deployed - never tested
- User needs to re-submit setup for encryption to work

---

## **🧪 Step-by-Step Verification Plan:**

### **PHASE 1: Backend Infrastructure (AWS Lightsail)**

#### **Step 1.1: Verify Lightsail Instance**
```bash
# SSH into your Lightsail instance
ssh username@your-lightsail-ip

# Check if bot manager is running
ps aux | grep bot_manager_http.py

# Check if port 8080 is listening
netstat -tulpn | grep 8080

# Check systemd service status (if using systemd)
sudo systemctl status bot-manager
```

**Expected Result:**
- ✅ Python process running
- ✅ Port 8080 listening
- ✅ Service active

#### **Step 1.2: Test Bot Manager HTTP Endpoint**
```bash
# From your local machine or another server
curl -X GET http://your-lightsail-ip:8080/health \
  -H "Authorization: Bearer YOUR_BOT_MANAGER_SECRET"

# Expected response:
# {"status": "healthy", "active_bots": 0}
```

**If this FAILS:**
- Bot manager is not running
- Firewall blocking port 8080
- Wrong BOT_MANAGER_SECRET

---

### **PHASE 2: Password Encryption Flow**

#### **Step 2.1: Re-submit User Setup**
1. Go to Dashboard → Settings
2. Re-enter MT5 credentials
3. Submit setup

#### **Step 2.2: Verify Encryption Worked**
```sql
-- Check if password is encrypted
SELECT 
  user_id, 
  mt5_account,
  LENGTH(mt5_password) as password_length,
  SUBSTRING(mt5_password, 1, 20) as password_preview
FROM user_setup 
WHERE user_id = '68d5aa6f-d6be-4cb6-a0a3-4f6c46d9e89c';
```

**Expected Result:**
- ✅ `password_length` > 50 (encrypted strings are long)
- ✅ `password_preview` looks like random base64: "hK8fJ2mL9pQ3rT5v..."
- ❌ If password_length < 20, it's still plain text!

#### **Step 2.3: Test Decryption in Edge Function**
```bash
# Call trigger-bot function directly (for testing)
curl -X POST https://yqgqgmzlvbglusupsjpz.supabase.co/functions/v1/trigger-bot \
  -H "Authorization: Bearer YOUR_USER_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "start",
    "strategyId": "64821461-97f3-4554-abb2-4d35facdf9dd",
    "strategyName": "Test Strategy"
  }'
```

**Check Edge Function Logs:**
```
✅ "MT5 password decrypted successfully"
❌ "Failed to decrypt MT5 password"
```

---

### **PHASE 3: Bot Startup Flow**

#### **Step 3.1: Start Bot from Dashboard**
1. Go to Strategies tab
2. Click "Start Strategy"
3. Monitor console for errors

#### **Step 3.2: Verify Bot Started**
```sql
-- Check if heartbeat was created
SELECT * FROM bot_heartbeats 
WHERE user_id = '68d5aa6f-d6be-4cb6-a0a3-4f6c46d9e89c'
ORDER BY created_at DESC 
LIMIT 1;
```

**Expected Result:**
- ✅ Record exists
- ✅ `status = 'running'`
- ✅ `mt5_connected = true`
- ✅ `last_heartbeat` is recent (<30 seconds ago)

#### **Step 3.3: Check Python Bot Logs**
```bash
# On Lightsail instance
tail -f /path/to/bot/logs/bot_wrapper.log

# OR if using systemd
sudo journalctl -u bot-manager -f
```

**Expected Logs:**
```
✅ "🤖 TRADING BOT STARTED FOR USER: ..."
✅ "✅ MT5 connected: ..."
✅ "📊 Equity: $X | Balance: $Y"
❌ "❌ Critical error: ..."
```

---

### **PHASE 4: Real-Time Dashboard Updates**

#### **Step 4.1: Open Dashboard**
- BotHealthIndicator should show green "Running"
- Should NOT show "No heartbeat"

#### **Step 4.2: Wait 30 Seconds**
- Heartbeat should update automatically
- `last_heartbeat` timestamp should change

#### **Step 4.3: Test Trade Sync**
```sql
-- Check if trades are being synced
SELECT * FROM trades 
WHERE user_id = '68d5aa6f-d6be-4cb6-a0a3-4f6c46d9e89c'
ORDER BY opened_at DESC 
LIMIT 5;
```

---

## **🔧 Common Issues & Solutions:**

### **Issue 1: Bot Manager Not Running**
```bash
# Install dependencies
cd python_scripts
pip install -r requirements.txt

# Start bot manager
python3 bot_manager_http.py

# OR with systemd
sudo systemctl start bot-manager
```

### **Issue 2: Encryption Key Mismatch**
```sql
-- Check if key exists
-- (This query won't show the value, just if it exists)
SELECT 1;

-- If you changed the key, all users need to re-enter passwords
UPDATE user_setup SET is_completed = false;
```

### **Issue 3: Port 8080 Blocked**
```bash
# Open firewall on Lightsail
sudo ufw allow 8080/tcp

# OR in AWS Console:
# Networking → Firewall → Add Rule → Custom TCP → 8080
```

### **Issue 4: MT5 Connection Fails**
**Check:**
- MT5 terminal is running
- Account/password/server correct
- MT5 allows API access
- No IP whitelist restrictions

---

## **📊 Success Criteria:**

### **✅ System is Working When:**
1. User can submit setup with encrypted password
2. Database shows long encrypted string (not plain text)
3. Bot manager responds to HTTP health check
4. Bot starts and creates heartbeat within 30 seconds
5. Dashboard shows green "Running" status
6. Heartbeat updates every 30 seconds
7. Trades sync from MT5 to database
8. Dashboard updates in real-time (no refresh needed)
9. Bot can be stopped from dashboard
10. Crash detection works (if bot dies, dashboard updates)

---

## **🚨 Current System State:**

| **Component** | **Status** | **Evidence** |
|---------------|-----------|--------------|
| Encryption Function | ✅ Deployed | Added to config.toml |
| RLS Policies | ✅ Fixed | INSERT/UPDATE allowed |
| ENCRYPTION_KEY | ✅ Set | User configured |
| Bot Manager (Lightsail) | ❓ Unknown | Not verified |
| Python Bot Running | ❌ NO | Empty heartbeats table |
| MT5 Connection | ❓ Unknown | Can't test until bot starts |
| Real-time Updates | ✅ Code Ready | Not tested end-to-end |
| Dashboard Sync | ✅ Code Ready | Not tested end-to-end |

---

## **🎯 Next Steps (IN ORDER):**

1. **Verify Lightsail is set up:**
   - SSH into Lightsail
   - Check bot_manager_http.py is running
   - Test HTTP endpoint with curl

2. **If Lightsail NOT ready:**
   - Follow `python_scripts/DEPLOYMENT_GUIDE.md`
   - Upload scripts to Lightsail
   - Start bot manager service
   - Open port 8080

3. **Re-test password encryption:**
   - User re-submits setup
   - Check database for encrypted string
   - Test decryption in logs

4. **Start bot properly:**
   - Click "Start Strategy"
   - Verify heartbeat created
   - Check Python bot logs
   - Monitor dashboard updates

5. **End-to-end test:**
   - Open position in MT5
   - Wait 10 seconds
   - Check if it appears in dashboard
   - Close position
   - Verify it updates in real-time

---

## **🔐 Security Verification:**

### **Password Encryption:**
```sql
-- ✅ GOOD: Encrypted (length > 50)
'hK8fJ2mL9pQ3rT5vX7zB4nM6cP8qR9tU2wY5xA8bC1dE4fG7h...'

-- ❌ BAD: Plain text (length < 20)
'MyPassword123'
```

### **No Plain Text in Logs:**
```bash
# Search bot logs for passwords
grep -i "password" /path/to/logs/*.log

# Should ONLY see "password decrypted" messages
# Should NEVER see actual password values
```

---

## **🧪 Quick Health Check Command:**

```bash
# Run this to check entire system
curl -X POST https://yqgqgmzlvbglusupsjpz.supabase.co/rest/v1/rpc/system_health_check \
  -H "apikey: YOUR_ANON_KEY" \
  -H "Content-Type: application/json"

# Should return:
# {
#   "bot_manager": "healthy",
#   "active_bots": 0,
#   "encrypted_passwords": true,
#   "heartbeat_fresh": true
# }
```

---

## **📌 Bottom Line:**

**The code is correct**, but the **infrastructure isn't verified**:

1. ✅ **Code:** All security, encryption, real-time sync implemented
2. ❓ **Lightsail:** Bot manager status unknown
3. ❌ **Bot:** Never actually started (no heartbeat proof)
4. ⚠️ **Passwords:** Need re-submission for encryption

**Before declaring "system works":**
- Verify Lightsail bot manager is running
- Test bot actually starts and creates heartbeat
- Confirm encrypted passwords work end-to-end
- Test real-time sync with actual MT5 trades
