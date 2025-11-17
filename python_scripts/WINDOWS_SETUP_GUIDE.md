# Complete Windows Server Setup Guide - Step by Step

## 📋 Prerequisites
- Windows Server on AWS Lightsail (or any Windows server)
- Python 3.8+ installed
- Administrator access
- Port 8080 open in firewall

---

## 📦 Step 1: Prepare Files to Upload

Upload these files to your Windows server at `C:\trading-bot\`:

### Required Files:
1. ✅ `bot_manager_http_windows.py` - HTTP server (main)
2. ✅ `bot_wrapper.py` - Individual bot wrapper
3. ✅ `hybrid_trading_bot_multiuser.py` - Trading bot logic
4. ✅ `requirements.txt` - Python dependencies
5. ✅ `run_bot_manager.bat` - Startup script

### File Transfer Methods:
- **Option A**: Remote Desktop → Copy/Paste files
- **Option B**: Use `scp` from your local machine:
  ```bash
  scp -i your-key.pem python_scripts/* Administrator@13.204.20.238:C:\trading-bot\
  ```

---

## 🔧 Step 2: Install Python Dependencies

1. Open **Command Prompt as Administrator**

2. Navigate to bot directory:
   ```cmd
   cd C:\trading-bot
   ```

3. Create virtual environment:
   ```cmd
   python -m venv venv
   ```

4. Activate virtual environment:
   ```cmd
   venv\Scripts\activate.bat
   ```

5. Install dependencies:
   ```cmd
   pip install -r requirements.txt
   ```

6. Verify installation:
   ```cmd
   pip list
   ```

---

## 🔐 Step 3: Set Environment Variable (BOT_MANAGER_SECRET)

**CRITICAL**: The secret MUST match exactly with Lovable Cloud secret.

### Set the secret:
```cmd
setx BOT_MANAGER_SECRET "SKp7MZ4r9Q2b8NF6wX3c1T0vR5L8GJ2"
```

### Verify it was set:
```cmd
echo %BOT_MANAGER_SECRET%
```

⚠️ **Important**: After setting with `setx`, you MUST close and reopen Command Prompt for the change to take effect!

---

## 🚪 Step 4: Configure Windows Firewall

Open **PowerShell as Administrator** and run:

```powershell
# Add firewall rule for port 8080
New-NetFirewallRule -DisplayName "Bot Manager HTTP" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow

# Verify the rule was created
Get-NetFirewallRule -DisplayName "Bot Manager HTTP"
```

---

## ☁️ Step 5: Configure AWS Lightsail Firewall

1. Go to AWS Lightsail Console
2. Select your Windows instance
3. Click **Networking** tab
4. Under **IPv4 Firewall**, click **Add rule**
5. Add:
   - **Application**: Custom
   - **Protocol**: TCP
   - **Port**: 8080
   - **Restrict to**: ☑️ Any IPv4 address
6. Click **Create**

---

## 🚀 Step 6: Start the Bot Manager

### Method A: Manual Start (for testing)

1. Open Command Prompt
2. Navigate to bot directory:
   ```cmd
   cd C:\trading-bot
   ```

3. Run the batch file:
   ```cmd
   run_bot_manager.bat
   ```

4. You should see:
   ```
   ========================================
   Starting Trading Bot Manager
   ========================================
   Port: 8080
   Directory: C:\trading-bot
   
   🚀 BOT MANAGER HTTP SERVER (Windows) STARTING
      Port: 8080
      Secret configured: True
   ```

### Method B: Run as Windows Service (recommended for production)

Create a Windows Service to auto-start the bot manager:

1. Open PowerShell as Administrator

2. Create service:
   ```powershell
   New-Service -Name "TradingBotManager" `
               -BinaryPathName "C:\trading-bot\venv\Scripts\python.exe C:\trading-bot\bot_manager_http_windows.py" `
               -DisplayName "Trading Bot Manager" `
               -Description "HTTP server for managing trading bots" `
               -StartupType Automatic
   ```

3. Start the service:
   ```powershell
   Start-Service -Name "TradingBotManager"
   ```

4. Verify service status:
   ```powershell
   Get-Service -Name "TradingBotManager"
   ```

5. Check service is running:
   ```powershell
   Get-Process python
   ```

---

## 🧪 Step 7: Test the Setup

### Test 1: Local Health Check
```cmd
curl http://localhost:8080/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "active_bots": 0,
  "platform": "windows",
  "secret_configured": true
}
```

### Test 2: Remote Health Check
From your local machine:
```bash
curl http://13.204.20.238:8080/health
```

**Should get same response as above.**

### Test 3: Check Logs
```cmd
type C:\trading-bot\bot_manager.log
```

**Look for:**
- ✅ "BOT MANAGER STARTING"
- ✅ "Secret configured: True"
- ✅ "Serving on http://0.0.0.0:8080"

---

## 🎯 Step 8: Test Bot Start from Dashboard

1. Go to your dashboard: `https://your-app.lovable.app/dashboard`
2. Click **Start Bot**
3. Monitor what happens:

### On Windows Server:
```cmd
# Watch logs in real-time
powershell Get-Content C:\trading-bot\bot_manager.log -Wait -Tail 50
```

### Look for these log messages:
```
🚀 BOT START REQUEST RECEIVED
Request from: <Supabase IP>
📨 Received token: Length=31, First 4=SKp7..., Last 4=...GJ2
🔑 Expected secret: Length=31, First 4=SKp7..., Last 4=...GJ2
✅ Token validated successfully
✅ Bot started successfully for user <user_id>
```

---

## 🔍 Troubleshooting

### Issue 1: "Invalid token" 401 Error

**Symptom:** Edge function logs show 401 error

**Fix:**
1. Verify secret in Command Prompt:
   ```cmd
   echo %BOT_MANAGER_SECRET%
   ```

2. If it doesn't match, set it again:
   ```cmd
   setx BOT_MANAGER_SECRET "SKp7MZ4r9Q2b8NF6wX3c1T0vR5L8GJ2"
   ```

3. **CRITICAL:** Restart the bot manager service or close/reopen Command Prompt

4. Check logs for token comparison:
   ```cmd
   findstr "Received token" C:\trading-bot\bot_manager.log
   findstr "Expected secret" C:\trading-bot\bot_manager.log
   ```

### Issue 2: No Requests Reaching Server

**Symptom:** Health check works locally but not remotely

**Fix:**
1. Check Windows Firewall:
   ```powershell
   Get-NetFirewallRule -DisplayName "Bot Manager HTTP"
   ```

2. Check AWS Lightsail Firewall (see Step 5)

3. Verify server is listening on all interfaces:
   ```powershell
   netstat -an | findstr :8080
   ```
   Should show: `0.0.0.0:8080`

### Issue 3: Bot Script Not Found

**Symptom:** Logs show "Bot script not found"

**Fix:**
1. Verify all files are in `C:\trading-bot\`:
   ```cmd
   dir C:\trading-bot
   ```

2. Make sure these exist:
   - bot_wrapper.py
   - hybrid_trading_bot_multiuser.py
   - bot_manager_http_windows.py

---

## 📊 Monitoring

### View Live Logs:
```powershell
Get-Content C:\trading-bot\bot_manager.log -Wait -Tail 50
```

### Check Running Bots:
```powershell
Get-Process python
```

### Restart Service:
```powershell
Restart-Service -Name "TradingBotManager"
```

### Stop Service:
```powershell
Stop-Service -Name "TradingBotManager"
```

---

## ✅ Success Checklist

- [ ] All 5 files uploaded to `C:\trading-bot\`
- [ ] Python dependencies installed
- [ ] Virtual environment created and activated
- [ ] `BOT_MANAGER_SECRET` environment variable set
- [ ] Windows Firewall rule created for port 8080
- [ ] AWS Lightsail Firewall allows port 8080
- [ ] Bot manager starts without errors
- [ ] Health check works locally (`http://localhost:8080/health`)
- [ ] Health check works remotely (`http://13.204.20.238:8080/health`)
- [ ] Logs show "Secret configured: True"
- [ ] Can start bot from dashboard
- [ ] Bot logs show successful authentication

---

## 🆘 Still Having Issues?

If you've followed all steps and still have issues:

1. **Share these logs:**
   ```cmd
   type C:\trading-bot\bot_manager.log
   ```

2. **Share environment check:**
   ```cmd
   echo %BOT_MANAGER_SECRET%
   echo %PATH%
   python --version
   ```

3. **Share firewall status:**
   ```powershell
   Get-NetFirewallRule -DisplayName "Bot Manager HTTP" | Format-List
   netstat -an | findstr :8080
   ```

---

## 📚 Additional Resources

- [Windows Firewall Configuration](https://docs.microsoft.com/en-us/windows/security/threat-protection/windows-firewall/windows-firewall-with-advanced-security)
- [AWS Lightsail Firewall](https://lightsail.aws.amazon.com/ls/docs/en_us/articles/amazon-lightsail-instance-firewall-rules)
- [Python Virtual Environments](https://docs.python.org/3/tutorial/venv.html)
