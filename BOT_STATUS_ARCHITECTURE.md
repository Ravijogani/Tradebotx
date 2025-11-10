# Bot Status Architecture - Event-Driven Design

## Problem Solved
Previously, the dashboard showed "Bot Running" immediately when the user clicked start, **even if the Python bot failed to start**. This created a false positive where the UI said "running" but no actual trading bot process existed.

## Solution: Event-Driven Status Updates

The system now works dynamically based on **actual bot status** (PID existence), not just user button clicks.

## Architecture Flow

### 1. User Clicks "Start Bot"
```
User clicks Start → Edge Function called
↓
Database: status = 'starting', is_running = false
↓
UI shows: "Starting..." badge (blue, with spinner)
```

### 2. Python Bot Starts Successfully
```
Python script starts → Gets PID from OS
↓
Bot sends HEARTBEAT to bot_heartbeats table
{
  status: 'running',
  pid: <actual_process_id>,
  last_heartbeat: <current_timestamp>
}
↓
BotStatusSync detects heartbeat
↓
Database: status = 'running', is_running = true, bot_pid = <pid>
↓
UI shows: "Live" badge (green, with pulse animation)
```

### 3. Bot Crashes or Stops
```
Bot process dies → PID removed from system
↓
Heartbeat stops OR status = 'crashed'
↓
BotStatusSync detects (checks every 10 seconds)
  - No heartbeat for >60 seconds = stale
  - OR status = 'crashed'
↓
Database: status = 'crashed', is_running = false, bot_pid = null
↓
UI shows: "Crashed" badge (red) + notification
```

## Database Schema Changes

### `user_strategies` table (new columns)
```sql
status TEXT -- Values: 'stopped', 'starting', 'running', 'stopping', 'crashed'
bot_pid INTEGER -- Actual OS process ID from Python
```

### `bot_heartbeats` table (new column)
```sql
pid INTEGER -- Actual OS process ID
```

## Component Responsibilities

### `start-trading-bot` Edge Function
- Sets `status = 'starting'` (NOT `is_running = true`)
- Calls `trigger-bot` to start Python process
- Returns immediately (doesn't wait for confirmation)

### `BotStatusSync` Component (Background Monitor)
- Runs every **10 seconds** (faster than before)
- Monitors strategies with status = 'starting' or 'running'
- **Key Logic:**
  - If status='starting' AND heartbeat shows 'running' → Set is_running=true
  - If heartbeat is stale (>60s) → Set is_running=false, status='crashed'
  - If heartbeat status='crashed' → Update database immediately
- Listens to real-time heartbeat changes for instant updates

### Python Bot Requirements
The Python bot **MUST** send an initial heartbeat immediately after starting:

```python
# After successful MT5 connection and getting PID
import os
pid = os.getpid()

supabase.table('bot_heartbeats').upsert({
    'user_id': user_id,
    'strategy_id': strategy_id,
    'status': 'running',
    'pid': pid,
    'last_heartbeat': datetime.utcnow().isoformat(),
    'mt5_connected': True
}).execute()
```

## UI Status Indicators

| Status | Badge | Color | Description |
|--------|-------|-------|-------------|
| `stopped` | ○ Stopped | Gray | Bot not running |
| `starting` | ⏳ Starting... | Blue + Spinner | Command sent, waiting for PID |
| `running` | ● Live | Green + Pulse | Bot has active PID and heartbeat |
| `stopping` | ⏳ Stopping... | Orange + Spinner | Stop command sent |
| `crashed` | ⚠ Crashed | Red | Heartbeat lost or error reported |

## Benefits

✅ **Accurate Status**: UI reflects actual bot state, not just user intent  
✅ **PID Tracking**: Shows actual process ID for verification  
✅ **Fast Updates**: 10-second polling + real-time subscription  
✅ **Auto-Recovery**: Detects crashes and updates UI automatically  
✅ **User Confidence**: Clear feedback when bot actually starts vs. when command is sent  

## Testing Checklist

- [ ] Click "Start" → Shows "Starting..." immediately
- [ ] Python bot starts → Within 10s, shows "Live" with PID
- [ ] Kill Python process → Within 70s, shows "Crashed"
- [ ] Restart crashed bot → Transitions correctly through statuses
- [ ] Multiple strategies → Each tracked independently with own PID
