# AWS Lightsail Bot Manager - Quick Start (5 Minutes)

## 🚀 Super Quick Deployment

### 1️⃣ Upload Files (2 minutes)
```bash
cd python_scripts
scp *.py requirements.txt deploy_to_lightsail.sh ubuntu@YOUR_LIGHTSAIL_IP:/tmp/
ssh ubuntu@YOUR_LIGHTSAIL_IP
```

### 2️⃣ Run Setup (2 minutes)
```bash
cd /tmp
chmod +x deploy_to_lightsail.sh
./deploy_to_lightsail.sh

cd /opt/trading-bot
source venv/bin/activate
pip install flask gunicorn
cp /tmp/bot_manager_http.py .
```

### 3️⃣ Create Service (1 minute)
```bash
# Generate secret
openssl rand -hex 16  # Copy this output

# Create service
sudo tee /etc/systemd/system/bot-manager-http.service > /dev/null <<EOF
[Unit]
Description=Trading Bot HTTP Manager
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/trading-bot
Environment="PATH=/opt/trading-bot/venv/bin"
Environment="BOT_MANAGER_SECRET=PASTE_YOUR_SECRET_HERE"
Environment="PORT=8080"
ExecStart=/opt/trading-bot/venv/bin/gunicorn -w 4 -b 0.0.0.0:8080 bot_manager_http:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### 4️⃣ Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable bot-manager-http
sudo systemctl start bot-manager-http
sudo systemctl status bot-manager-http
```

### 5️⃣ Configure Firewall
- AWS Console → Lightsail → Your Instance → Networking
- Add rule: TCP Port 8080

### 6️⃣ Test
```bash
curl http://localhost:8080/health
# Should return: {"status": "healthy", "active_bots": 0}
```

### 7️⃣ Update Supabase Secrets
Add these to your Lovable project (already done if you followed earlier steps):
- `LIGHTSAIL_BOT_MANAGER_URL`: `http://YOUR_LIGHTSAIL_IP:8080`
- `BOT_MANAGER_SECRET`: (your generated secret from step 3)

### 8️⃣ Verify
- Go to Admin Dashboard → System Health
- Click "Check Bot Manager Connection"
- Should show "Connected" ✅

---

## ⚡ That's It!

Your bot manager is now running. Test by starting a strategy from the dashboard.

For detailed troubleshooting, see `LIGHTSAIL_DEPLOYMENT_STEPS.md`.
