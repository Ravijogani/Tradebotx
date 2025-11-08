# AWS Lightsail Windows Server - Bot Manager Setup Guide

Complete guide for deploying the trading bot manager on **Windows Server** via AWS Lightsail.

---

## 📋 Prerequisites

✅ AWS Lightsail Windows Server instance (running)  
✅ RDP access to the instance  
✅ Python 3.10+ installed on Windows Server  
✅ Basic knowledge of Windows PowerShell/Command Prompt

---

## 🚀 Step-by-Step Deployment

### Step 1: Install Python on Windows Server

1. **RDP into your Lightsail instance**
   - Open Remote Desktop Connection
   - Connect to your Lightsail IP address
   - Login with your credentials

2. **Download Python**
   - Open browser in Windows Server
   - Go to: https://www.python.org/downloads/
   - Download Python 3.10 or newer (64-bit)

3. **Install Python**
   - Run the installer
   - ⚠️ **IMPORTANT:** Check ✅ "Add Python to PATH"
   - Click "Install Now"
   - Wait for installation to complete

4. **Verify Installation**
   - Open Command Prompt (cmd)
   - Run: `python --version`
   - Should show: `Python 3.10.x` or higher

---

### Step 2: Upload Bot Files to Windows Server

**Option A: Direct Copy via RDP**
1. On your local machine, zip these files:
   - `bot_wrapper.py`
   - `hybrid_trading_bot.py`
   - `bot_manager_http_windows.py`
   - `requirements.txt`
   - `install_windows.bat`
   - `run_bot_manager.bat`

2. Copy the zip file through RDP:
   - In RDP session, go to local drives (This PC → Local Disk)
   - Copy the zip file to Desktop
   - Extract it

**Option B: Use AWS Lightsail File Transfer**
1. In Lightsail console → Your instance
2. Click "Connect using RDP"
3. Upload files using the file transfer option

---

### Step 3: Run Installation Script

1. **Open Command Prompt as Administrator**
   - Press Win + X
   - Select "Command Prompt (Admin)" or "PowerShell (Admin)"

2. **Navigate to your files**
   ```cmd
   cd C:\Users\Administrator\Desktop\python_scripts
   ```

3. **Run installation**
   ```cmd
   install_windows.bat
   ```

4. **Wait for completion**
   - Script will create `C:\trading-bot` directory
   - Install all dependencies
   - Set up virtual environment

---

### Step 4: Generate and Set Secret Key

1. **Generate a secure secret** (PowerShell):
   ```powershell
   -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})
   ```
   Copy the output (e.g., `aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW`)

2. **Set environment variable permanently**:
   ```cmd
   setx BOT_MANAGER_SECRET "aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW"
   ```

3. **Set PORT (optional, default is 8080)**:
   ```cmd
   setx PORT "8080"
   ```

4. **Restart Command Prompt** to apply changes

---

### Step 5: Configure Windows Firewall

1. **Open Windows Firewall**
   - Start Menu → "Windows Defender Firewall"
   - Click "Advanced settings"

2. **Create Inbound Rule**
   - Click "Inbound Rules" → "New Rule..."
   - Rule Type: **Port**
   - Protocol: **TCP**
   - Specific local ports: **8080**
   - Action: **Allow the connection**
   - Profile: Check all (Domain, Private, Public)
   - Name: **Trading Bot Manager**
   - Click Finish

---

### Step 6: Configure Lightsail Networking

1. **Go to AWS Lightsail console**
2. **Click your Windows instance**
3. **Go to "Networking" tab**
4. **Under "Firewall", click "Add rule"**
   - Application: **Custom**
   - Protocol: **TCP**
   - Port: **8080**
   - Click "Create"

---

### Step 7: Start Bot Manager

1. **Open Command Prompt**
   ```cmd
   cd C:\trading-bot
   run_bot_manager.bat
   ```

2. **You should see**:
   ```
   ========================================
   Starting Trading Bot Manager
   ========================================
   Port: 8080
   
   🚀 Bot Manager HTTP Server (Windows) starting on port 8080
   Serving on http://0.0.0.0:8080
   ```

3. **Keep this window open** (bot manager is running)

---

### Step 8: Test the Bot Manager

**Test from Windows Server (local)**:
```cmd
curl http://localhost:8080/health
```

**Test from external** (replace with your Lightsail IP):
```bash
curl http://YOUR_LIGHTSAIL_IP:8080/health
```

**Expected response**:
```json
{
  "status": "healthy",
  "active_bots": 0,
  "platform": "windows"
}
```

---

### Step 9: Configure Supabase Secrets

**These should already be set** from earlier, but verify:

1. **LIGHTSAIL_BOT_MANAGER_URL**
   - Value: `http://YOUR_LIGHTSAIL_IP:8080`
   - Example: `http://54.123.45.67:8080`

2. **BOT_MANAGER_SECRET**
   - Value: Your generated secret from Step 4
   - Example: `aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW`

---

### Step 10: Verify from Dashboard

1. **Go to your app's Admin Dashboard**
2. **Navigate to System Health Check**
3. **Click "Check Bot Manager Connection"**
4. **Should show**: ✅ Connected

---

## 🔄 Making Bot Manager Run Automatically

### Option 1: Using Task Scheduler (Recommended)

1. **Open Task Scheduler**
   - Start Menu → "Task Scheduler"

2. **Create New Task**
   - Action → "Create Task" (not "Create Basic Task")
   - Name: **Trading Bot Manager**
   - Check: ✅ "Run whether user is logged on or not"
   - Check: ✅ "Run with highest privileges"

3. **Triggers Tab**
   - Click "New..."
   - Begin the task: **At startup**
   - Click OK

4. **Actions Tab**
   - Click "New..."
   - Action: **Start a program**
   - Program: `C:\trading-bot\venv\Scripts\python.exe`
   - Arguments: `-m waitress --host=0.0.0.0 --port=8080 bot_manager_http:app`
   - Start in: `C:\trading-bot`
   - Click OK

5. **Conditions Tab**
   - Uncheck: ❌ "Start the task only if the computer is on AC power"

6. **Settings Tab**
   - Check: ✅ "If the task fails, restart every: 1 minute"
   - Check: ✅ "Attempt to restart up to: 3 times"

7. **Click OK** and enter admin password if prompted

### Option 2: Using NSSM (Non-Sucking Service Manager)

1. **Download NSSM**
   - Go to: https://nssm.cc/download
   - Download and extract to `C:\nssm`

2. **Install Service**
   ```cmd
   cd C:\nssm\win64
   nssm install TradingBotManager "C:\trading-bot\venv\Scripts\python.exe"
   ```

3. **Configure Service**
   - Application Path: `C:\trading-bot\venv\Scripts\python.exe`
   - Startup Directory: `C:\trading-bot`
   - Arguments: `-m waitress --host=0.0.0.0 --port=8080 bot_manager_http:app`
   - Service Name: `TradingBotManager`
   - Click "Install Service"

4. **Set Environment Variables**
   ```cmd
   nssm set TradingBotManager AppEnvironmentExtra BOT_MANAGER_SECRET=your-secret-here PORT=8080
   ```

5. **Start Service**
   ```cmd
   nssm start TradingBotManager
   ```

---

## 📊 Monitoring & Logs

### View Logs
```cmd
cd C:\trading-bot
type bot_manager.log
```

### Check Service Status (if using Task Scheduler)
```cmd
tasklist | findstr python
```

### Check Service Status (if using NSSM)
```cmd
nssm status TradingBotManager
```

### Stop Service
```cmd
nssm stop TradingBotManager
```

### Restart Service
```cmd
nssm restart TradingBotManager
```

---

## 🔧 Troubleshooting

### Bot Manager Won't Start

**Check Python installation:**
```cmd
python --version
where python
```

**Check dependencies:**
```cmd
cd C:\trading-bot
venv\Scripts\activate
pip list
```

**Reinstall dependencies:**
```cmd
pip install -r requirements.txt --force-reinstall
```

### Port 8080 Already in Use

**Find process using port:**
```cmd
netstat -ano | findstr :8080
```

**Kill process:**
```cmd
taskkill /PID <PID_NUMBER> /F
```

### Connection Refused from Dashboard

1. **Check Windows Firewall**
   - Verify inbound rule for port 8080 exists and is enabled

2. **Check Lightsail Firewall**
   - Verify TCP port 8080 is open in networking settings

3. **Check bot manager is running**
   ```cmd
   curl http://localhost:8080/health
   ```

4. **Check your Lightsail public IP**
   - Use the correct public IP in `LIGHTSAIL_BOT_MANAGER_URL`

### Bot Not Starting

**Check bot logs:**
```cmd
cd C:\trading-bot
type bot_manager.log
```

**Verify MT5 can connect:**
- Ensure MT5 is installed on the Windows Server
- Test MT5 connection manually

---

## 🔒 Security Best Practices

### 1. Strong Secret Key
```cmd
REM Generate strong 64-character secret
powershell -Command "[Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(48))"
```

### 2. Restrict Access
- Only allow specific IPs in Lightsail firewall
- Your app server's IP should be whitelisted

### 3. Use HTTPS (Production)
- Set up a reverse proxy (IIS) with SSL certificate
- Or use Cloudflare Tunnel for secure access

### 4. Regular Updates
```cmd
cd C:\trading-bot
venv\Scripts\activate
pip install --upgrade pip
pip install --upgrade -r requirements.txt
```

### 5. Backup Configuration
```cmd
xcopy C:\trading-bot C:\trading-bot-backup\ /E /I /H
```

---

## ✅ Success Checklist

- [ ] Python installed and in PATH
- [ ] Bot files uploaded to Windows Server
- [ ] Installation script completed successfully
- [ ] BOT_MANAGER_SECRET environment variable set
- [ ] Windows Firewall rule created for port 8080
- [ ] Lightsail firewall rule added for port 8080
- [ ] Bot manager starts without errors
- [ ] Health check responds: `{"status": "healthy"}`
- [ ] External connection works from your app
- [ ] Supabase secrets configured correctly
- [ ] Dashboard shows "Connected" status
- [ ] Bot manager runs automatically on startup

---

## 🎯 Daily Operations

### Start Bot Manager
```cmd
cd C:\trading-bot
run_bot_manager.bat
```

### Stop Bot Manager
Press `Ctrl+C` in the running window

### View Active Bots
```cmd
curl -H "Authorization: Bearer YOUR_SECRET" http://localhost:8080/bot/status
```

### Update Bot Code
```cmd
cd C:\trading-bot
REM Copy new files
venv\Scripts\activate
pip install -r requirements.txt
REM Restart bot manager
```

---

## 🆘 Need Help?

1. **Check logs**: `C:\trading-bot\bot_manager.log`
2. **Verify services**: Task Scheduler or NSSM status
3. **Test connectivity**: Use curl or Postman
4. **Check documentation**: Review error messages carefully

---

## 🎉 You're Done!

Your Windows Server bot manager is now running and ready to receive commands from your trading dashboard!

**Test it**: Go to your dashboard → Select a strategy → Click "Start Bot" 🚀
