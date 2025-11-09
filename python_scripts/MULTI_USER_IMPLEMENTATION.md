# Multi-User Trading Bot Implementation Guide

## Overview

This system now supports **multiple users** running **independent trading bot instances** with:
- ✅ Per-user MT5 credentials from database
- ✅ Real-time data sync to Supabase
- ✅ Telegram notifications for each user
- ✅ Bot heartbeat monitoring
- ✅ Live dashboard updates
- ✅ Crash detection and auto-recovery

## Architecture

```
Dashboard (User clicks "Start Bot")
    ↓
Edge Function (trigger-bot)
    ↓
Bot Manager HTTP Server (Lightsail/Windows Server)
    ↓
Spawns bot_wrapper.py process for each user
    ↓
Bot runs with user's MT5 credentials
    ↓
Writes trades to Supabase + Sends Telegram notifications
    ↓
Dashboard shows real-time updates
```

## How It Works

### 1. User Starts Bot from Dashboard

When a user clicks "Start Bot" on the dashboard:

1. **Frontend** calls the `trigger-bot` edge function with:
   - `user_id`
   - `strategy_id`
   - `action: "start"`

2. **Edge Function** (`trigger-bot`):
   - Authenticates the user
   - Fetches user's setup from `user_setup` table:
     - MT5 account, password (decrypted), server
     - Account size, risk per trade
     - Telegram chat ID
   - Fetches strategy details from `strategies` table
   - Builds a `botConfig` object with all necessary data
   - Sends POST request to Bot Manager HTTP server

3. **Bot Manager** (`bot_manager_http.py`):
   - Receives the config
   - Validates required fields
   - Spawns a new `bot_wrapper.py` process with the config
   - Tracks the process (PID, user_id, strategy_id)
   - Returns success response

4. **Bot Wrapper** (`bot_wrapper.py`):
   - Parses the config from command line
   - Connects to user's MT5 account
   - Enters main trading loop
   - Syncs trades to Supabase in real-time
   - Sends Telegram notifications
   - Updates bot heartbeat every 30 seconds

### 2. Multi-User Support

Each user gets their **own isolated bot process**:

```python
# Bot Manager tracks: {user_id}_{strategy_id} -> process
running_bots = {
    "user123_strategy456": {
        "process": <subprocess>,
        "pid": 12345,
        "config": {...}
    },
    "user789_strategy456": {
        "process": <subprocess>,
        "pid": 12346,
        "config": {...}
    }
}
```

**Key Points:**
- One process = One MT5 connection = One user
- Processes are independent and isolated
- Each process has its own logs in `Hybrid_AI_Bot_Logs/{user_id}/`
- Crash in one bot doesn't affect others

### 3. Real-Time Data Flow

```
Bot Process
  ↓
[Trade Opened] → Supabase.insert('trades') → Dashboard receives realtime update
  ↓                                        ↓
Telegram notification                    Toast notification
  ↓
[Trade Updated] → Supabase.update('trades') → Dashboard updates position
  ↓
[Trade Closed] → Supabase.update('trades') → Dashboard shows P&L
  ↓
Telegram notification with profit/loss
```

### 4. Bot Heartbeat Monitoring

Every 30 seconds, each bot updates `bot_heartbeats` table:

```javascript
{
  user_id: "user123",
  strategy_id: "strategy456",
  last_heartbeat: "2025-01-10T10:30:00Z",
  status: "running", // or "reconnecting", "crashed", "stopped"
  mt5_connected: true,
  error_message: null
}
```

The `BotStatusSync` component on the dashboard:
- Monitors heartbeats every 30 seconds
- If `last_heartbeat` > 60 seconds old → marks bot as crashed
- Updates `user_strategies.is_running = false`
- Shows toast notification to user

### 5. Telegram Notifications

Each user receives notifications for:

#### Bot Started
```
🟢 Bot Connected

Account: 12345678
Server: Exness-MT5Trial7
Strategy: ICT Scalper Pro
```

#### Trade Opened
```
📈 New Trade Opened

Symbol: EURUSDm
Type: BUY
Entry: 1.09450
Lot Size: 0.5
SL: 1.09250 | TP: 1.09750
Confidence: 85.5%
```

#### Trade Closed
```
💚 Trade Closed

Symbol: EURUSDm
Exit: 1.09650
P&L: $125.50
Reason: TP Hit
```

#### Bot Crashed
```
🔴 Bot Crashed

Failed to reconnect after 5 attempts
Error: MT5 connection timeout
```

## File Structure

```
python_scripts/
├── bot_wrapper.py              # Main per-user bot process
├── bot_manager_http.py         # HTTP server that spawns bots
├── hybrid_trading_bot.py       # (Legacy) Original single-user bot
├── hybrid_trading_bot_multiuser.py # (NEW) Multi-user version with CLI args
├── requirements.txt            # Python dependencies
└── MULTI_USER_IMPLEMENTATION.md # This file
```

## Database Tables Used

### `user_setup`
Stores per-user MT5 credentials and configuration:
- `mt5_account`, `mt5_password` (encrypted), `mt5_server`
- `account_size`, `risk_per_trade`, `max_positions`
- `telegram_chat_id`

### `trades`
Real-time trade data:
- `user_id`, `strategy_id`, `symbol`, `trade_type`
- `entry_price`, `exit_price`, `quantity`, `profit_loss`
- `status` (open/closed), `opened_at`, `closed_at`
- `metadata` (JSON with SL, TP, indicators, AI confidence, etc.)

### `bot_heartbeats`
Bot health monitoring:
- `user_id`, `strategy_id`, `last_heartbeat`
- `status`, `mt5_connected`, `error_message`

### `user_strategies`
User's strategy subscriptions:
- `user_id`, `strategy_id`, `is_running`
- `started_at`, `stopped_at`

## Configuration Requirements

### Supabase Secrets

The edge function needs these secrets:
- `LIGHTSAIL_BOT_MANAGER_URL` - HTTP URL of bot manager (e.g., `http://54.123.45.67:8080`)
- `BOT_MANAGER_SECRET` - Shared authentication secret
- `TELEGRAM_BOT_TOKEN` - Telegram bot token for notifications
- `ENCRYPTION_KEY` - For decrypting MT5 passwords

### Bot Manager Environment Variables

On the server running `bot_manager_http.py`:
```bash
export BOT_MANAGER_SECRET="your-secret-here"
export PORT=8080
```

## Deployment Steps

### 1. Server Setup (Lightsail/Windows)

Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Start Bot Manager

#### Linux (with systemd):
```bash
gunicorn -w 4 -b 0.0.0.0:8080 bot_manager_http:app
```

#### Windows:
```bash
python bot_manager_http.py
```

### 3. Configure Firewall

Open port 8080 for incoming connections from Supabase.

### 4. Update Supabase Secrets

In your Lovable project:
- Go to Settings → Secrets
- Update `LIGHTSAIL_BOT_MANAGER_URL` with your server's URL

### 5. Test the System

1. Login to dashboard
2. Complete setup (MT5 credentials)
3. Click "Start Bot" on a strategy
4. Check:
   - Bot Manager logs show bot started
   - Telegram receives "Bot Connected" message
   - Dashboard shows bot as running
   - Heartbeat is updating in database

## Monitoring & Troubleshooting

### Check Running Bots

```bash
curl -H "Authorization: Bearer YOUR_SECRET" \
  http://your-server:8080/bot/status
```

### View Bot Logs

```bash
# Linux
tail -f Hybrid_AI_Bot_Logs/{user_id}/bot_YYYYMMDD.log

# Windows
Get-Content Hybrid_AI_Bot_Logs\{user_id}\bot_YYYYMMDD.log -Wait -Tail 50
```

### Common Issues

#### 1. Bot Not Starting
- **Check:** Bot Manager logs for errors
- **Fix:** Verify MT5 credentials are correct
- **Fix:** Ensure MT5 terminal is installed on server

#### 2. No Telegram Notifications
- **Check:** `telegram_chat_id` is set in `user_setup`
- **Fix:** User must start conversation with bot first
- **Fix:** Verify `TELEGRAM_BOT_TOKEN` secret is correct

#### 3. Trades Not Appearing on Dashboard
- **Check:** Supabase connection in bot logs
- **Fix:** Verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
- **Fix:** Check RLS policies on `trades` table

#### 4. Bot Shows as Crashed
- **Check:** Bot process is still running (check PID)
- **Check:** `bot_heartbeats` table for error messages
- **Fix:** Review bot logs for crash reason
- **Fix:** Restart bot from dashboard

#### 5. Multiple Users, Same Strategy
- **This is supported!** Each user gets their own bot process
- Bot Manager tracks by `{user_id}_{strategy_id}` key
- Processes are completely isolated

## Security Considerations

1. **Password Encryption**: MT5 passwords stored encrypted in database
2. **Bot Manager Auth**: All requests require `BOT_MANAGER_SECRET`
3. **HTTPS**: In production, use HTTPS for Bot Manager (nginx/Apache)
4. **Firewall**: Restrict port 8080 to only Supabase IP ranges
5. **Process Isolation**: Each bot runs as separate process (no shared state)
6. **Secret Rotation**: Regularly rotate `BOT_MANAGER_SECRET`

## Performance & Scaling

### Current Limits
- **Concurrent bots**: Limited by server resources
- **Each bot uses**: ~50-100 MB RAM, minimal CPU
- **Lightsail 2GB instance**: Can handle 10-15 concurrent bots
- **Windows Server 8GB**: Can handle 50+ concurrent bots

### Scaling Strategy
- **Vertical**: Upgrade to larger instance (4GB, 8GB)
- **Horizontal**: Run multiple bot managers on different servers
  - Use load balancer
  - Each server has `BOT_MANAGER_SECRET`
  - Dashboard picks server based on user load

### Optimization Tips
- Increase heartbeat interval to 60s for more bots
- Use connection pooling for Supabase
- Batch trade updates if >10 open positions
- Consider Redis for hot data caching

## Migration from Single-User Bot

If you have the old `hybrid_trading_bot.py` running:

1. **Stop** the old bot
2. **Deploy** new system with `bot_wrapper.py` and `bot_manager_http.py`
3. **Update** edge function to call Bot Manager
4. **Test** with one user first
5. **Migrate** other users gradually

## Next Steps

1. ✅ **Implement full `hybrid_trading_bot_multiuser.py`**
   - Port all 9 trading strategies
   - Add AI validation and learning
   - Include all indicators and signals

2. ✅ **Add Windows-specific bot manager**
   - `bot_manager_http_windows.py` with Windows process handling
   - Windows service configuration

3. ✅ **Enhance error handling**
   - Automatic reconnection on MT5 disconnect
   - Exponential backoff on failures
   - Email alerts for critical errors

4. ✅ **Performance monitoring**
   - Track CPU/memory usage per bot
   - Add metrics endpoint for Grafana
   - Log execution times for optimization

## Support

For issues or questions:
1. Check bot logs first
2. Review Supabase edge function logs
3. Check Bot Manager HTTP server logs
4. Contact system administrator

---

**Last Updated**: 2025-01-10
**Version**: 1.0.0
