# MT5 Multi-User Isolation Setup Guide

## Architecture Overview

```
C:\trading-bot\
├── bot_manager_http_windows.py    # Flask bot manager
├── hybrid_trading_bot_multiuser.py # Scalp strategy
├── intraday.py                     # Intraday strategy
├── swing.py                        # Swing strategy
├── MT5_Instances/                  # ← NEW: Per-user MT5 installations
│   ├── 5e6b929b/                  # User 1 (first 8 chars of UUID)
│   │   └── terminal64.exe         # User 1's isolated MT5
│   ├── a3f2c891/                  # User 2
│   │   └── terminal64.exe
│   └── b7d4e562/                  # User 3
│       └── terminal64.exe
└── venv/
```

## Why This Architecture?

**Problem:** MT5 Python library (`MetaTrader5`) connects to a single terminal per process. When multiple bots try to use the same terminal, you get:
- Login session overrides
- "Terminal not found" errors
- Trade placement in wrong accounts

**Solution:** Each user gets their own **portable MT5 installation**. Each bot process connects to its user's specific `terminal64.exe` via the `path=` parameter in `mt5.initialize()`.

## How It Works

### Flow
```
User clicks "Start Bot" on TradeBotX.pro
    ↓
Edge Function → Bot Manager (Flask)
    ↓
Bot Manager resolves: MT5_Instances/<user_id_short>/terminal64.exe
    ↓
Spawns: python intraday.py --mt5-path "C:\...\terminal64.exe" --mt5-login 12345 ...
    ↓
Bot script calls: mt5.initialize(path="C:\...\terminal64.exe", login=12345, ...)
    ↓
✅ Each user's bot connects to their own MT5 terminal — no conflicts!
```

### Multiple Strategies Per User
When a user runs both scalp and intraday:
- Both bot processes use the **same** `terminal64.exe` (same MT5 instance)
- They use **different magic numbers** to isolate their trades
- Magic numbers are auto-generated from `hash(user_id + strategy_id)`

```
User 1 starts scalp.py   → MT5_Instances/5e6b929b/terminal64.exe (magic: 234567)
User 1 starts intraday.py → MT5_Instances/5e6b929b/terminal64.exe (magic: 891234)
User 2 starts scalp.py   → MT5_Instances/a3f2c891/terminal64.exe (magic: 345678)
```

## Setup Steps

### 1. Create MT5 Template

Install MT5 once on your server. This becomes the "template":

```
C:\trading-bot\MT5_Template\
├── terminal64.exe
├── Config\
├── MQL5\
└── ...
```

**Important:** Log in to MT5 template with any account first so it downloads the broker's server list. Then close it.

### 2. Provision User Instances

**Single user:**
```batch
setup_mt5_instance.bat 5e6b929b "C:\trading-bot\MT5_Template"
```

**Bulk setup (edit user IDs in the script):**
```batch
setup_all_users_mt5.bat "C:\trading-bot\MT5_Template"
```

### 3. Set Environment Variable

```batch
setx MT5_INSTANCES_DIR "C:\trading-bot\MT5_Instances"
```

Or it defaults to `C:\trading-bot\MT5_Instances`.

### 4. Restart Bot Manager

```batch
run_bot_manager.bat
```

The bot manager will now:
- Resolve each user's MT5 path on bot start
- Pass `--mt5-path` to each bot subprocess
- Return clear error if no MT5 instance exists for a user

### 5. Verify

Check the `/mt5/instances` endpoint:
```
curl -H "Authorization: Bearer YOUR_SECRET" http://localhost:8080/mt5/instances
```

## Folder Naming Convention

Bot manager searches for MT5 instances in this order:
1. `MT5_Instances/<first_8_chars_of_user_id>/terminal64.exe`
2. `MT5_Instances/<full_user_id>/terminal64.exe`
3. `MT5_Instances/user_<first_8_chars>/terminal64.exe`

**Recommended:** Use first 8 characters of the user's UUID for folder names.

## Scaling Limits

| Server RAM | Max Concurrent MT5 Instances | Max Users |
|-----------|------|---------|
| 8 GB      | ~10  | 10      |
| 16 GB     | ~25  | 25      |
| 32 GB     | ~50  | 50      |

Each MT5 instance uses ~200-400 MB RAM.

### When to Add Another Server

When you exceed ~20 concurrent MT5 instances:
1. Spin up a second AWS Lightsail/EC2 instance
2. Install the same setup
3. Assign users to servers (e.g., by user ID range)
4. Store server assignment in database

## Troubleshooting

### "No MT5 instance provisioned for this user"
→ Run `setup_mt5_instance.bat` for that user

### "MT5 initialization failed"
→ Check the user's `terminal64.exe` path exists
→ Try launching it manually to verify broker server connectivity
→ Check if another process is locking the same MT5 folder

### Multiple strategies conflict for same user
→ They share the same MT5 instance (correct behavior)
→ Make sure magic numbers are different (auto-generated)
→ Each strategy only manages trades with its own magic number

### Memory issues with many users
→ Monitor RAM usage: `tasklist | findstr terminal`
→ Consider closing MT5 instances for inactive users
→ Scale to larger instance or add servers
