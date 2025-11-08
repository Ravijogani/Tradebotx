# Complete Deployment Guide for AWS Lightsail

## Overview
This guide walks you through deploying the trading bot system on AWS Lightsail with MT5.

## Architecture
```
User Dashboard → Supabase Edge Function → HTTP Request → AWS Lightsail Bot Manager → Python Trading Bots → MT5 → Supabase Database
```

## Prerequisites
- ✅ AWS Lightsail instance (Ubuntu 20.04+)
- ✅ MT5 Terminal installed and configured
- ✅ SSH access to the instance
- ✅ Gemini API key (already added to Supabase)

---

## Step 1: Deploy to AWS Lightsail

### 1.1 Upload Files to Lightsail
```bash
# From your local machine, upload files
scp -r python_scripts/* ubuntu@YOUR_LIGHTSAIL_IP:/tmp/

# SSH into your instance
ssh ubuntu@YOUR_LIGHTSAIL_IP
```

### 1.2 Run Deployment Script
```bash
cd /tmp
chmod +x deploy_to_lightsail.sh
./deploy_to_lightsail.sh
```

### 1.3 Configure Environment
```bash
# Edit the systemd service with your credentials
sudo nano /etc/systemd/system/trading-bot-manager.service

# Replace these values:
# - SUPABASE_URL with your Supabase URL
# - SUPABASE_SERVICE_ROLE_KEY with your service role key
```

### 1.4 Start Bot Manager Service
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable trading-bot-manager

# Start the service
sudo systemctl start trading-bot-manager

# Check status
sudo systemctl status trading-bot-manager

# View logs
sudo journalctl -u trading-bot-manager -f
```

---

## Step 2: Configure HTTP Bot Manager (Recommended)

The HTTP-based manager allows direct communication from Supabase edge functions.

### 2.1 Install Flask
```bash
cd /opt/trading-bot
source venv/bin/activate
pip install flask gunicorn
```

### 2.2 Create Systemd Service for HTTP Manager
```bash
sudo nano /etc/systemd/system/bot-manager-http.service
```

Add this content:
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

### 2.3 Start HTTP Manager
```bash
sudo systemctl daemon-reload
sudo systemctl enable bot-manager-http
sudo systemctl start bot-manager-http
sudo systemctl status bot-manager-http
```

### 2.4 Configure Lightsail Firewall
1. Go to AWS Lightsail console
2. Select your instance
3. Go to "Networking" tab
4. Add custom rule: Port 8080, TCP
5. Save

### 2.5 Test Connection
```bash
# From another machine or your local computer
curl http://YOUR_LIGHTSAIL_IP:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "active_bots": 0
}
```

---

## Step 3: Configure Supabase Secrets

You need to add these secrets to Supabase:

1. **LIGHTSAIL_BOT_MANAGER_URL**
   - Value: `http://YOUR_LIGHTSAIL_IP:8080`

2. **BOT_MANAGER_SECRET**
   - Value: Same secure secret you used in Step 2.2

Go to your Lovable project and run:
```
Add LIGHTSAIL_BOT_MANAGER_URL and BOT_MANAGER_SECRET secrets
```

---

## Step 4: Update Edge Functions

The `trigger-bot` edge function needs to be called instead of `start-trading-bot`.

Update your frontend code to call the new endpoint.

---

## Step 5: Test the System

### 5.1 Start a Bot via Dashboard
1. Log in to your dashboard
2. Go to Strategy Selection
3. Click "Start Strategy"
4. Check bot manager logs:
```bash
sudo journalctl -u bot-manager-http -f
```

### 5.2 Monitor Bot Activity
```bash
# Check bot manager status
curl -H "Authorization: Bearer YOUR_SECRET" \
  http://YOUR_LIGHTSAIL_IP:8080/bot/status

# Check Supabase trades table
# Should see new trades appearing in real-time
```

### 5.3 Stop a Bot
1. Click "Stop Strategy" in dashboard
2. Verify bot stops in logs

---

## Step 6: Production Checklist

- [ ] Use HTTPS instead of HTTP (setup nginx reverse proxy with SSL)
- [ ] Configure proper firewall rules (restrict port 8080 to Supabase IP only)
- [ ] Set up monitoring (Datadog, CloudWatch, or custom)
- [ ] Configure log rotation
- [ ] Set up automated backups of trade data
- [ ] Test bot restart after crashes
- [ ] Test MT5 reconnection after disconnects
- [ ] Set up alerting for bot failures
- [ ] Configure resource limits (CPU, memory)
- [ ] Document recovery procedures

---

## Troubleshooting

### Bot Manager Won't Start
```bash
# Check service status
sudo systemctl status bot-manager-http

# Check logs
sudo journalctl -u bot-manager-http -n 100

# Check if port is in use
sudo netstat -tulpn | grep 8080
```

### Bot Can't Connect to MT5
```bash
# Check MT5 is running
ps aux | grep terminal

# Check MT5 login credentials
# Verify in /opt/trading-bot/bot_wrapper.py
```

### Bot Not Syncing to Supabase
```bash
# Check Supabase credentials
echo $SUPABASE_URL
echo $SUPABASE_SERVICE_ROLE_KEY

# Test connection
python3 -c "from supabase import create_client; print('OK')"
```

### HTTP Manager Connection Issues
```bash
# Check firewall
sudo ufw status

# Check if service is listening
curl http://localhost:8080/health

# Check from external IP
curl http://YOUR_LIGHTSAIL_IP:8080/health
```

---

## Security Recommendations

1. **Use HTTPS**: Set up nginx reverse proxy with Let's Encrypt SSL
2. **Restrict Access**: Only allow Supabase IPs to access port 8080
3. **Rotate Secrets**: Change BOT_MANAGER_SECRET regularly
4. **Encrypt MT5 Credentials**: Consider using AWS Secrets Manager
5. **Monitor Logs**: Set up alerts for suspicious activity
6. **Backup Data**: Regular backups of trade database
7. **Update Dependencies**: Keep Python packages up to date

---

## Monitoring & Maintenance

### Daily Checks
- Bot manager service is running
- Bots are syncing trades to Supabase
- MT5 connection is stable
- No error spikes in logs

### Weekly Checks
- Review trade performance
- Check disk space usage
- Update Python dependencies
- Review security logs

### Monthly Checks
- Rotate secrets
- Update system packages
- Review and optimize bot parameters
- Analyze profitability metrics

---

## Support

If you encounter issues:
1. Check logs: `sudo journalctl -u bot-manager-http -f`
2. Test connection: `curl http://YOUR_IP:8080/health`
3. Verify MT5 is running and logged in
4. Check Supabase connectivity
5. Review edge function logs in Lovable Cloud dashboard
