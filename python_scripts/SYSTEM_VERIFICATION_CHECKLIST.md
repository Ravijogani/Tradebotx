# System Verification Checklist

Use this checklist after deployment to verify everything is working.

## ✅ Infrastructure Setup

- [ ] **Lightsail Instance Running**
  ```bash
  ssh ubuntu@YOUR_LIGHTSAIL_IP
  uptime
  ```

- [ ] **Python Environment Setup**
  ```bash
  cd /opt/trading-bot
  source venv/bin/activate
  python --version  # Should be 3.9+
  ```

- [ ] **Dependencies Installed**
  ```bash
  pip list | grep -E "MetaTrader5|supabase|flask|pandas"
  # All should be present
  ```

- [ ] **Bot Scripts Present**
  ```bash
  ls -la /opt/trading-bot/
  # Should see: bot_wrapper.py, bot_manager_http.py, requirements.txt
  ```

---

## ✅ Service Configuration

- [ ] **Systemd Service File Exists**
  ```bash
  cat /etc/systemd/system/bot-manager-http.service
  # Verify BOT_MANAGER_SECRET is set (not default value)
  ```

- [ ] **Service is Active**
  ```bash
  sudo systemctl status bot-manager-http
  # Should show: active (running) in green
  ```

- [ ] **Service Auto-starts on Boot**
  ```bash
  sudo systemctl is-enabled bot-manager-http
  # Should output: enabled
  ```

- [ ] **No Recent Crashes**
  ```bash
  sudo journalctl -u bot-manager-http --since "1 hour ago" | grep -i error
  # Should show no critical errors
  ```

---

## ✅ Network & Connectivity

- [ ] **Service Listening on Port 8080**
  ```bash
  sudo netstat -tulpn | grep 8080
  # Should show gunicorn listening on 0.0.0.0:8080
  ```

- [ ] **Local Health Check Works**
  ```bash
  curl http://localhost:8080/health
  # Should return: {"status":"healthy","active_bots":0}
  ```

- [ ] **External Health Check Works**
  ```bash
  # From your local machine:
  curl http://YOUR_LIGHTSAIL_IP:8080/health
  # Should return same as above
  ```

- [ ] **Firewall Allows Port 8080**
  - Check in AWS Lightsail Console → Networking
  - Custom TCP rule for port 8080 should exist

---

## ✅ Supabase Integration

- [ ] **Secrets Configured in Supabase**
  - Open your Lovable project
  - Go to Admin Dashboard → System Health
  - Verify both secrets exist:
    - `LIGHTSAIL_BOT_MANAGER_URL`
    - `BOT_MANAGER_SECRET`

- [ ] **Bot Manager Connection Test**
  - In Admin Dashboard → System Health
  - Click "Check Bot Manager Connection"
  - Should show: ✅ Connected
  - Response should include: `{ "healthy": true, "url": "http://YOUR_IP:8080", ... }`

- [ ] **Edge Functions Deployed**
  ```bash
  # Check these exist in your Lovable project:
  # - supabase/functions/trigger-bot/index.ts
  # - supabase/functions/stop-trading-bot/index.ts
  # - supabase/functions/verify-bot-manager/index.ts
  ```

---

## ✅ Database Setup

- [ ] **Required Tables Exist**
  - Go to Backend → Tables
  - Verify these tables exist:
    - `strategies` (should have 4 sample strategies)
    - `user_strategies`
    - `user_setup`
    - `trades`
    - `strategy_performance`
    - `user_notifications`

- [ ] **Sample Strategies Loaded**
  - Check `strategies` table
  - Should have 4 strategies: Scalping Pro, Trend Follower, Range Trader, Breakout Hunter

- [ ] **RLS Policies Enabled**
  - All tables should have RLS enabled
  - Check via Backend → Tables → (select table) → Policies

---

## ✅ Bot Lifecycle Testing

### Test Bot Start:

- [ ] **Start Bot from Dashboard**
  1. Log in as a user
  2. Complete user setup (MT5 credentials, account size)
  3. Go to Dashboard → Strategy Selection
  4. Click "Start Strategy" on any strategy
  5. Verify success message appears

- [ ] **Verify Bot Running in Lightsail**
  ```bash
  # SSH to Lightsail
  sudo journalctl -u bot-manager-http -n 20
  # Should see: "Started bot for user <user_id> (PID: xxxx)"
  
  # Check process exists
  ps aux | grep bot_wrapper
  # Should show Python bot process
  ```

- [ ] **Check Database Updates**
  - Go to Backend → Tables → `user_strategies`
  - Find your user's strategy
  - Verify: `is_running = true`, `started_at` has timestamp

- [ ] **Active Bots Counter Updates**
  - Dashboard should show "1 Active Bot"
  - Counter should update in real-time

### Test Bot Stop:

- [ ] **Stop Bot from Dashboard**
  1. Go to Dashboard → Strategy Selection
  2. Click "Stop Strategy"
  3. Verify success message appears

- [ ] **Verify Bot Stopped in Lightsail**
  ```bash
  sudo journalctl -u bot-manager-http -n 20
  # Should see: "Stopped bot for user <user_id>"
  
  ps aux | grep bot_wrapper
  # Should NOT show your bot process anymore
  ```

- [ ] **Check Database Updates**
  - Go to Backend → Tables → `user_strategies`
  - Verify: `is_running = false`, `stopped_at` has timestamp

- [ ] **Active Bots Counter Updates**
  - Dashboard should show "0 Active Bots"

---

## ✅ Monitoring & Notifications

- [ ] **Notifications Created on Bot Start**
  - Start a bot
  - Go to Backend → Tables → `user_notifications`
  - Should see: "Trading Bot Started" notification for your user

- [ ] **Strategy Performance Initialized**
  - After starting a bot
  - Go to Backend → Tables → `strategy_performance`
  - Should see record with `initial_balance` from your account size

- [ ] **Bell Icon Shows Notifications**
  - Click bell icon in dashboard header
  - Should see recent notifications
  - Unread count should show

---

## ✅ Trade Monitoring

- [ ] **Trades Sync to Database**
  - Let bot run for a few minutes (if market is open)
  - Go to Backend → Tables → `trades`
  - Should see new trades appearing

- [ ] **Trade Notifications Created**
  - Check `user_notifications` table
  - Should see "New Trade Executed" notifications

- [ ] **Strategy Performance Updates**
  - After trades close
  - Check `strategy_performance` table
  - Metrics should update: `total_trades`, `winning_trades`, `total_profit_loss`, etc.

---

## ✅ Email System

- [ ] **SMTP Configured**
  - Verify Supabase secrets:
    - `SMTP_HOST`
    - `SMTP_PORT`
    - `SMTP_USER`
    - `SMTP_PASS`
    - `SMTP_FROM`

- [ ] **Welcome Email Sent**
  - Create a new test user account
  - Check email inbox
  - Should receive welcome email with improved design

- [ ] **Bot Start Alert Email**
  - Start a bot
  - Check email inbox
  - Should receive "Bot Started" notification email

---

## ✅ Admin Dashboard

- [ ] **System Health Shows All Green**
  - Admin Dashboard → System Health
  - All checks should pass:
    - ✅ Bot Manager Connected
    - ✅ Database Connected
    - ✅ 4 Available Strategies
    - Shows current active bots count

- [ ] **Can View Running Bots**
  - Admin Dashboard → Bot Monitoring
  - Should show list of running bots with user details

- [ ] **Can Access Admin Features**
  - Admin Dashboard sidebar should show:
    - Analytics
    - Users
    - Subscriptions
    - Strategies
    - Support Tickets
    - System Health

---

## ✅ Performance Metrics

- [ ] **Strategy Performance Displayed**
  - User Dashboard should show Strategy Performance card
  - Shows metrics: Win Rate, Total Trades, ROI, etc.

- [ ] **Trade Journal Accessible**
  - Click "View Trade Journal"
  - Shows list of all trades with P&L

- [ ] **Weekly Performance Calculated**
  - After running bot for a while
  - Performance metrics show accurate calculations
  - Win rate, avg profit/loss calculated correctly

---

## 🎯 Final Production Checklist

Before going live with real users:

- [ ] **HTTPS Configured** (use nginx + Let's Encrypt)
- [ ] **Firewall Restricted** (only allow necessary IPs)
- [ ] **Secrets Rotated** (use strong, unique secrets)
- [ ] **Monitoring Setup** (CloudWatch, Datadog, etc.)
- [ ] **Backup Strategy** (database backups automated)
- [ ] **Logging Configured** (centralized log management)
- [ ] **Rate Limiting** (prevent API abuse)
- [ ] **Error Alerting** (get notified of critical errors)
- [ ] **Load Testing** (test with multiple concurrent bots)
- [ ] **Documentation Updated** (all configs documented)

---

## 📊 Quick Status Commands

```bash
# Service status
sudo systemctl status bot-manager-http

# Recent logs
sudo journalctl -u bot-manager-http -n 50

# Follow logs
sudo journalctl -u bot-manager-http -f

# Running bots
ps aux | grep bot_wrapper

# Port listening
sudo netstat -tulpn | grep 8080

# Health check
curl http://localhost:8080/health

# Bot status (with auth)
curl -H "Authorization: Bearer YOUR_SECRET" \
  http://localhost:8080/bot/status
```

---

## ✅ All Checks Passed?

If all items are checked, your system is ready for use! 🎉

If any checks fail, refer to:
- `LIGHTSAIL_DEPLOYMENT_STEPS.md` for detailed deployment steps
- `QA_ANALYSIS_REPORT.md` for known issues and fixes
- `CRITICAL_ISSUES_FIXED.md` for security fixes applied

---

**Last Verified:** [Date]
**Verified By:** [Your Name]
**Instance IP:** [Your Lightsail IP]
**Project:** TradeBotX
