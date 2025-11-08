# Trading Bot Deployment Guide

## Overview
This directory contains the Python trading bot scripts that integrate with your Supabase database for real-time trading.

## Files
- `bot_wrapper.py` - Dynamic wrapper that accepts user parameters and syncs with Supabase
- `hybrid_trading_bot.py` - Original AI trading bot (for reference)
- `requirements.txt` - Python dependencies

## How It Works

### 1. User Starts Bot
- User clicks "Start Strategy" in dashboard
- Edge function `start-trading-bot` is called
- User credentials and settings are fetched from `user_setup` table
- Bot configuration is prepared

### 2. Bot Execution
The bot needs to run on a server with:
- Python 3.8+
- MetaTrader 5 platform installed
- Network access to Supabase

### 3. Real-time Data Sync
The bot continuously syncs:
- **Account Balance** → `user_subscriptions.account_balance`
- **Open Positions** → `trades` table (status: 'open')
- **Closed Trades** → `trades` table (status: 'closed')

### 4. Data Flow
```
MT5 Platform ←→ Python Bot ←→ Supabase Database ←→ Web Dashboard
```

## Deployment Options

### Option 1: VPS/Cloud Server (Recommended)
```bash
# Install dependencies
pip install -r requirements.txt

# Run bot with user config
python3 bot_wrapper.py '{
  "user_id": "uuid",
  "strategy_id": "uuid",
  "mt5_account": "12345678",
  "mt5_password": "password",
  "mt5_server": "Server-Name",
  "account_size": 10000,
  "risk_per_trade": 1.0,
  "max_positions": 3,
  "supabase_url": "https://your-project.supabase.co",
  "supabase_service_key": "your-service-key"
}'
```

### Option 2: Docker Container
```dockerfile
FROM python:3.9
RUN pip install -r requirements.txt
CMD ["python3", "bot_wrapper.py"]
```

### Option 3: Process Manager (PM2)
```bash
# Install PM2
npm install -g pm2

# Start bot
pm2 start bot_wrapper.py --interpreter python3 --name "trading-bot-user123"

# Monitor
pm2 logs trading-bot-user123
```

## Database Schema

### trades table
```sql
- user_id (uuid) - Links to user
- strategy_id (uuid) - Strategy being used
- symbol (text) - Trading pair (e.g., 'EURUSDm')
- trade_type (text) - 'BUY' or 'SELL'
- entry_price (numeric) - Entry price
- exit_price (numeric) - Exit price (when closed)
- quantity (numeric) - Position size
- profit_loss (numeric) - P&L in dollars
- status (trade_status) - 'open', 'closed', 'pending'
- opened_at (timestamp) - When opened
- closed_at (timestamp) - When closed
- metadata (jsonb) - Additional data:
  - ticket: MT5 ticket number
  - stop_loss: SL price
  - take_profit: TP price
  - current_price: Current price (for open positions)
  - profit: Unrealized profit
  - swap: Swap fees
  - commission: Commission fees
```

## Features

### ✅ Current Implementation
- Dynamic user configuration
- Real-time balance sync
- Open positions sync
- Closed trades sync
- Remote bot control (start/stop via dashboard)

### 🚧 Next Steps for Full Bot
1. Integrate full AI trading logic from `hybrid_trading_bot.py`
2. Add strategy execution (ICT, SMC, Wyckoff, etc.)
3. Add risk management (stop loss, take profit, trailing stops)
4. Add AI validation via Gemini API
5. Add news filter integration
6. Add performance analytics

## Security Notes

⚠️ **IMPORTANT**:
- Never commit MT5 credentials to git
- Use environment variables for sensitive data
- Service role key should only be used server-side
- Bot should run on secure infrastructure with firewall

## Monitoring

The bot logs all activity including:
- Connection status
- Trade execution
- Sync operations
- Errors and warnings

Monitor logs to ensure bot is running correctly:
```bash
# If using PM2
pm2 logs trading-bot-user123

# If using direct execution
python3 bot_wrapper.py '...' 2>&1 | tee bot.log
```

## Troubleshooting

### Bot won't connect to MT5
- Check MT5 platform is running
- Verify credentials are correct
- Ensure server name matches MT5 server

### Data not syncing to Supabase
- Check internet connection
- Verify Supabase URL and service key
- Check RLS policies allow inserts

### Bot stops unexpectedly
- Check logs for errors
- Verify user didn't stop bot via dashboard
- Check server resources (CPU, memory)
