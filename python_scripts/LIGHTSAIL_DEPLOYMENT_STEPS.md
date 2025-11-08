# AWS Lightsail Bot Manager - Quick Deployment Guide

## 🎯 Prerequisites Checklist

Before starting, ensure you have:

- [ ] AWS Lightsail instance running Ubuntu 20.04+ (minimum 2GB RAM recommended)
- [ ] SSH key pair configured for the instance
- [ ] Instance public IP address noted down
- [ ] MetaTrader 5 terminal installed on the instance (or ready to install)
- [ ] Supabase project URL and service role key from your Lovable project

---

## 📦 Step 1: Prepare Your Local Files

From your project directory:

```bash
# Navigate to python_scripts directory
cd python_scripts

# Verify all required files are present
ls -la
# Should see: bot_wrapper.py, hybrid_trading_bot.py, bot_manager_http.py, 
# requirements.txt, deploy_to_lightsail.sh
```

---

## 🚀 Step 2: Upload Files to Lightsail

Replace `YOUR_LIGHTSAIL_IP` with your actual instance IP address:

```bash
# Upload all Python scripts to Lightsail
scp bot_wrapper.py ubuntu@YOUR_LIGHTSAIL_IP:/tmp/
scp hybrid_trading_bot.py ubuntu@YOUR_LIGHTSAIL_IP:/tmp/
scp bot_manager_http.py ubuntu@YOUR_LIGHTSAIL_IP:/tmp/
scp requirements.txt ubuntu@YOUR_LIGHTSAIL_IP:/tmp/
scp deploy_to_lightsail.sh ubuntu@YOUR_LIGHTSAIL_IP:/tmp/

# SSH into your instance
ssh ubuntu@YOUR_LIGHTSAIL_IP
```

---

## 🔧 Step 3: Run Initial Setup

Once connected via SSH:

```bash
# Navigate to temp directory
cd /tmp

# Make deployment script executable
chmod +x deploy_to_lightsail.sh

# Run the deployment script (this will install dependencies)
./deploy_to_lightsail.sh

# This script will:
# - Update system packages
# - Install Python 3.9+
# - Create /opt/trading-bot directory
# - Set up Python virtual environment
# - Install requirements (MetaTrader5, pandas, supabase, etc.)
```

---

## 🌐 Step 4: Set Up HTTP Bot Manager

Install Flask and create the HTTP service:

```bash
# Activate virtual environment
cd /opt/trading-bot
source venv/bin/activate

# Install Flask and Gunicorn
pip install flask gunicorn

# Copy the HTTP manager script
cp /tmp/bot_manager_http.py /opt/trading-bot/
```

---

## ⚙️ Step 5: Create Systemd Service

Create the service file for automatic bot management:

```bash
# Create the service file
sudo nano /etc/systemd/system/bot-manager-http.service
```

Paste this content (replace `YOUR_SECURE_SECRET_HERE` with a strong random secret):

```ini
[Unit]
Description=Trading Bot HTTP Manager
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/trading-bot
Environment="PATH=/opt/trading-bot/venv/bin"
Environment="BOT_MANAGER_SECRET=YOUR_SECURE_SECRET_HERE"
Environment="PORT=8080"
ExecStart=/opt/trading-bot/venv/bin/gunicorn -w 4 -b 0.0.0.0:8080 bot_manager_http:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Generate a secure secret:**
```bash
# Generate a random 32-character secret
openssl rand -hex 16
# Copy this output and use it as your BOT_MANAGER_SECRET
```

Save and exit (Ctrl+X, then Y, then Enter).

---

## 🔥 Step 6: Configure Lightsail Firewall

1. Go to [AWS Lightsail Console](https://lightsail.aws.amazon.com/)
2. Click on your instance
3. Go to **Networking** tab
4. Under **IPv4 Firewall**, click **Add rule**
5. Add:
   - **Application**: Custom
   - **Protocol**: TCP
   - **Port range**: 8080
   - **Restrict to IP addresses** (optional but recommended): Add your Supabase IP or leave open
6. Click **Create**

---

## ▶️ Step 7: Start the Bot Manager Service

```bash
# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable bot-manager-http

# Start the service
sudo systemctl start bot-manager-http

# Check service status
sudo systemctl status bot-manager-http
```

You should see `active (running)` in green.

---

## 🧪 Step 8: Test the Bot Manager

### Test from Lightsail instance (local):
```bash
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "active_bots": 0
}
```

### Test from your local machine:
```bash
curl http://YOUR_LIGHTSAIL_IP:8080/health
```

If this fails, verify:
- Firewall rule is configured (Step 6)
- Service is running: `sudo systemctl status bot-manager-http`
- Check logs: `sudo journalctl -u bot-manager-http -n 50`

---

## 🔐 Step 9: Configure Supabase Secrets

You need to add these secrets to your Lovable project. You should have already done this, but verify:

1. **LIGHTSAIL_BOT_MANAGER_URL**
   - Value: `http://YOUR_LIGHTSAIL_IP:8080`

2. **BOT_MANAGER_SECRET**
   - Value: The same secret you used in Step 5 (from `openssl rand -hex 16`)

**To verify secrets are set:**
- Go to your Admin Dashboard in the app
- Click on **System Health** in the sidebar
- Click **Check Bot Manager Connection**
- Should show "Connected" with green status

---

## ✅ Step 10: Test End-to-End

### From the Dashboard:
1. Log in as a user
2. Navigate to **Dashboard**
3. Go to **Strategy Selection**
4. Configure MT5 credentials in setup
5. Click **Start Strategy** on any strategy
6. Check that Active Bots counter increases

### Monitor Bot Manager Logs:
```bash
# Watch logs in real-time
sudo journalctl -u bot-manager-http -f

# You should see:
# - "Started bot for user <user_id> (PID: xxxx)"
# - Bot process starting
```

### Check Database:
- Navigate to **Backend** → **Tables** → **user_strategies**
- Verify `is_running` is `true` for your started bot
- Check **trades** table for new trades appearing

---

## 📊 Monitoring Commands

### Check service status:
```bash
sudo systemctl status bot-manager-http
```

### View recent logs:
```bash
sudo journalctl -u bot-manager-http -n 100
```

### Follow logs in real-time:
```bash
sudo journalctl -u bot-manager-http -f
```

### Check running bot processes:
```bash
ps aux | grep bot_wrapper
```

### Test bot manager API:
```bash
# Health check
curl http://localhost:8080/health

# Status check (requires auth)
curl -H "Authorization: Bearer YOUR_SECRET" \
  http://localhost:8080/bot/status
```

---

## 🐛 Troubleshooting

### Service won't start:
```bash
# Check for syntax errors in service file
sudo systemctl daemon-reload
sudo systemctl status bot-manager-http

# Check detailed logs
sudo journalctl -u bot-manager-http -n 100 --no-pager
```

### Can't connect to port 8080:
```bash
# Check if service is listening
sudo netstat -tulpn | grep 8080

# Check firewall
sudo ufw status

# Test locally first
curl http://localhost:8080/health

# Then test from outside
curl http://YOUR_LIGHTSAIL_IP:8080/health
```

### Bots not starting:
```bash
# Check bot wrapper script exists
ls -la /opt/trading-bot/bot_wrapper.py

# Check Python environment
cd /opt/trading-bot
source venv/bin/activate
python -c "import MetaTrader5; print('MT5 OK')"

# Check logs for errors
sudo journalctl -u bot-manager-http -f
```

### MT5 Connection Issues:
```bash
# Verify MT5 is installed
which terminal64.exe  # or terminal.exe

# Check if Wine is working (for Linux)
wine --version

# Test MT5 initialization
cd /opt/trading-bot
source venv/bin/activate
python -c "import MetaTrader5 as mt5; print(mt5.initialize())"
```

---

## 🔒 Security Hardening (Production)

### 1. Set up HTTPS with Nginx:
```bash
sudo apt install nginx certbot python3-certbot-nginx

# Create nginx config
sudo nano /etc/nginx/sites-available/bot-manager

# Add SSL certificate
sudo certbot --nginx -d your-domain.com
```

### 2. Restrict firewall to Supabase IPs only:
```bash
# Remove public access to port 8080
# Add specific IP ranges in Lightsail console
```

### 3. Enable rate limiting:
Consider using nginx rate limiting to prevent abuse.

### 4. Set up monitoring:
- CloudWatch Logs for AWS
- Datadog or Prometheus for metrics
- Configure alerts for service failures

---

## 📝 Daily Operations

### Start/Stop Service:
```bash
# Start
sudo systemctl start bot-manager-http

# Stop
sudo systemctl stop bot-manager-http

# Restart
sudo systemctl restart bot-manager-http
```

### Update Bot Code:
```bash
# Upload new files
scp bot_wrapper.py ubuntu@YOUR_LIGHTSAIL_IP:/opt/trading-bot/

# Restart service
ssh ubuntu@YOUR_LIGHTSAIL_IP
sudo systemctl restart bot-manager-http
```

### Backup Configuration:
```bash
# Backup service file
sudo cp /etc/systemd/system/bot-manager-http.service ~/bot-manager-backup.service

# Backup bot scripts
cd /opt/trading-bot
tar -czf ~/bot-scripts-backup.tar.gz *.py
```

---

## ✨ Success Checklist

- [ ] Deployment script completed without errors
- [ ] HTTP bot manager service is `active (running)`
- [ ] Health endpoint returns `{"status": "healthy"}`
- [ ] Lightsail firewall allows port 8080
- [ ] Supabase secrets are configured correctly
- [ ] System Health Check shows "Connected"
- [ ] Can start a bot from dashboard
- [ ] Active Bots counter updates
- [ ] Trades appear in database
- [ ] Can stop a bot from dashboard
- [ ] Logs show bot start/stop events

---

## 🆘 Need Help?

### Check logs first:
```bash
sudo journalctl -u bot-manager-http -f
```

### Common issues:
1. **Port 8080 blocked**: Check firewall rules in Lightsail console
2. **Service crashed**: Check logs for Python errors
3. **MT5 not connecting**: Verify MT5 credentials in user setup
4. **Database not syncing**: Check Supabase URL/key are correct

### System Health Dashboard:
Use the Admin Dashboard → System Health to verify all connections.
