# -*- coding: utf-8 -*-
"""
=============================================================================
 STRUCTURAL SWING PRO -- multi-day D1/H4 structural swing-trading engine
=============================================================================
Why this file exists: the "Structural Swing Pro" strategy row in the
`strategies` table has always pointed its python_script_path at `swing.py`
-- a file that has never existed anywhere in this repo, and isn't on
bot_manager_core.py's ALLOWED_BOT_SCRIPTS allow-list either. Any Pro
customer who selected this strategy got a guaranteed failure the moment
they clicked Start (traced end-to-end during the whole-project audit: the
bot manager rejects the unknown script name, trigger-bot's edge function
surfaces that as an opaque "Bot manager returned 400" error). This file is
the real strategy that row now points to.

Why its own file rather than folded into hybrid_trading_bot_multiuser.py or
intraday.py: those two files don't dispatch on strategy_id at all --
strategy_id is only used for magic-number derivation and DB labeling, so
EVERY strategy defined in a given file runs for EVERY user who launches
that file, regardless of which strategy they picked. Adding a new strategy
into either shared file would have silently bundled it into a tier that
didn't pay for it (Free-tier "Enhanced Scalping Bot" users would start
getting swing trades too, and vice versa). A dedicated script per tier --
which is how intraday.py already relates to hybrid_trading_bot_multiuser.py
-- keeps tier separation real instead of cosmetic. (The dispatch gap in the
two shared files is a separate, disclosed issue, not fixed here.)

Why no AI dependency: this strategy is deliberately fully rule-based and
deterministic (market structure is either there in the OHLC data or it
isn't) -- no google.generativeai import, no API key requirement, one fewer
moving part for a strategy whose whole premise is "structure, not opinion."

STRATEGY
--------
Bias: D1 swing-high/swing-low sequence (find_swing_points + classify_
structure) -- higher-highs AND higher-lows across the most recent two
confirmed swing points each = bullish structure; lower-highs AND
lower-lows = bearish; anything else (including not enough confirmed
points yet) = no trade this bar.

Entry: price pulls back into the 50%-78.6% Fibonacci retracement zone of
the most recent D1 impulse leg IN THE DIRECTION OF BIAS (fib_zone), then an
H4 candle both trades into that zone AND closes back in bias direction
(is_rejection_candle) -- not a blind limit order sitting at the zone with
no confirmation that price actually turned there.

Stop-loss: beyond the structural swing point that started the leg (the
point whose invalidation means the read was wrong), plus a small H4-ATR
buffer so a routine wick doesn't stop the trade out on noise alone.

Take-profit: the nearest opposing D1 structural swing level still ahead of
price (find_nearest_target) -- skipped entirely if that real target implies
less than MIN_RR, rather than inventing an arbitrary multiple.

Timeframes: D1 structure, H4 entries -- no M1/M5 anywhere in this file.
Deliberately infrequent (a handful of setups a week, multi-day holds) --
distinctly different cadence from EMA_SCALP_CROSS/SWAPPY_3C (M5, this repo's
free-tier scalp strategies) or intraday.py's H1/H4 session trades (closed
same day). That cadence difference is the actual point of a "swing" tier,
not just a different label on the same trade frequency.

SAFETY
------
_project_lot_and_risk()/validate_trade_risk() and check_emergency_
conditions() mirror the exact patterns this same audit just found broken
and fixed in intraday.py: real per-trade risk is derived from the lot size
the position will actually get (including the broker's min-lot floor,
which can push real risk above what a naive risk_percent * equity
calculation would show), not an algebraic restatement of the configured
risk_percent that could never fail its own cap check; and the emergency
stop self-heals if its equity baseline is ever unset instead of dividing by
zero and crash-looping silently while the heartbeat keeps reporting
"healthy". Built correctly from day one here rather than needing the same
fix applied twice.

BACKTEST/LIVE PARITY
---------------------
detect_structural_swing_signal() is the single pure, no-lookahead decision
function -- takes only D1/H4 OHLC data in, returns a signal or None, no
mt5.* calls inside it. Both this file's live loop and backtest/
swing_driver.py call this exact function, so a backtest run and a live run
can never silently diverge in what counts as a signal (see engine.py's
module docstring for why this principle runs through the whole harness).
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
import requests
from supabase import create_client, Client

import market_intelligence as mi
import bot_control
import risk_limits
import decision_journal as dj
import structure_tools as st

# =============================================================================
# CLI ARGUMENTS -- identical contract to hybrid_trading_bot_multiuser.py /
# intraday.py: bot_manager_core.py's start_bot() builds the same argv list
# (--user-id/--strategy-id/--mt5-login/--mt5-server/--mt5-path/
# --telegram-chat-id/--supabase-url) for every script on its allow-list, and
# passes secrets via env vars (MT5_PASSWORD/SUPABASE_SERVICE_KEY/
# TELEGRAM_BOT_TOKEN), never argv -- see bot_manager_core.py's start_bot()
# for exactly what gets passed.
# =============================================================================
parser = argparse.ArgumentParser(description='Structural Swing Pro Trading Bot')
parser.add_argument('--user-id', type=str, required=True, help='User ID')
parser.add_argument('--strategy-id', type=str, required=True, help='Strategy ID')
parser.add_argument('--mt5-login', type=int, required=True, help='MT5 Login')
parser.add_argument('--mt5-password', type=str, required=False, default=None, help='MT5 Password (prefer MT5_PASSWORD env var)')
parser.add_argument('--mt5-server', type=str, required=True, help='MT5 Server')
parser.add_argument('--mt5-path', type=str, required=False, default=None, help='Path to user-specific MT5 terminal64.exe')
parser.add_argument('--telegram-chat-id', type=str, required=False, help='Telegram Chat ID')
parser.add_argument('--telegram-bot-token', type=str, required=False, help='Telegram Bot Token (prefer TELEGRAM_BOT_TOKEN env var)')
parser.add_argument('--supabase-url', type=str, required=True, help='Supabase URL')
parser.add_argument('--supabase-key', type=str, required=False, default=None, help='Supabase Service Key (prefer SUPABASE_SERVICE_KEY env var)')

args = parser.parse_args()

USER_ID = args.user_id
STRATEGY_ID = args.strategy_id
TELEGRAM_CHAT_ID = args.telegram_chat_id
MT5_PASSWORD_RESOLVED = args.mt5_password or os.getenv("MT5_PASSWORD", "")
SUPABASE_KEY_RESOLVED = args.supabase_key or os.getenv("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT_TOKEN = args.telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
MT5_TERMINAL_PATH = args.mt5_path

if not MT5_PASSWORD_RESOLVED:
    print("[FATAL] MT5 password not provided (neither --mt5-password nor MT5_PASSWORD env var)")
    sys.exit(1)
if not SUPABASE_KEY_RESOLVED:
    print("[FATAL] Supabase service key not provided (neither --supabase-key nor SUPABASE_SERVICE_KEY env var)")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", USER_ID)
os.makedirs(DATA_DIR, exist_ok=True)


def _resolve_magic_number(user_id: str, strategy_id: str, data_dir: str) -> int:
    """Deterministic per user+strategy magic number, with the same
    per-user collision registry hybrid_trading_bot_multiuser.py and
    intraday.py both use -- MT5 only needs this unique within one account,
    so a small per-user registry is enough to stop two strategies for the
    same user from ever managing each other's positions via a hash
    collision."""
    base = int(hashlib.md5(f"{user_id}_{strategy_id}".encode()).hexdigest(), 16) % 2_000_000_000 + 10_000_000
    registry_path = os.path.join(data_dir, "magic_numbers.json")
    try:
        registry = json.load(open(registry_path)) if os.path.exists(registry_path) else {}
    except Exception:
        registry = {}
    if strategy_id in registry:
        return registry[strategy_id]
    candidate = base
    used = set(registry.values())
    while candidate in used:
        candidate += 1
    registry[strategy_id] = candidate
    try:
        with open(registry_path, "w") as f:
            json.dump(registry, f)
    except Exception:
        pass
    return candidate


MAGIC_NUMBER = _resolve_magic_number(USER_ID, STRATEGY_ID, DATA_DIR)

# =============================================================================
# LOGGING
# =============================================================================
LOG_DIR = Path(f"Swing_Bot_Logs_{USER_ID}")
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"swing_bot_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("structural_swing_pro")

supabase: Client = create_client(args.supabase_url, SUPABASE_KEY_RESOLVED)

# =============================================================================
# CONFIG
# =============================================================================
@dataclass
class SwingTradingConfig:
    MT5_LOGIN: int = args.mt5_login
    MT5_PASSWORD: str = MT5_PASSWORD_RESOLVED
    MT5_SERVER: str = args.mt5_server

    # Full instrument set, matching SYMBOL_SPECS and the other two bots.
    SYMBOLS: List[str] = field(default_factory=lambda: [
        'EURUSDm', 'GBPUSDm', 'USDJPYm', 'XAUUSDm', 'XAGUSDm',
        'BTCUSDm', 'ETHUSDm', 'USOILm', 'NZDUSDm',
        'USDCADm', 'AUDUSDm', 'USDCHFm', 'GBPJPYm'
    ])

    STRUCTURE_TF: int = mt5.TIMEFRAME_D1
    ENTRY_TF: int = mt5.TIMEFRAME_H4

    SWING_LOOKBACK: int = 3          # bars each side for a confirmed fractal pivot
    STRUCTURE_BARS: int = 120        # D1 bars pulled for structure detection
    ENTRY_BARS: int = 60             # H4 bars pulled for the entry trigger

    FIB_ZONE_NEAR: float = 0.5       # zone bound nearer the leg's end (shallow pullback)
    FIB_ZONE_FAR: float = 0.786      # zone bound nearer the leg's start (deep pullback)
    MIN_RR: float = 2.0              # skip a setup if the nearest real target implies less
    SL_BUFFER_ATR_MULT: float = 0.25 # small buffer beyond the structural point, in H4 ATR

    # Deliberately lower base risk than the scalp/intraday tiers -- with
    # multi-day stop distances, the same risk_percent swings more dollars
    # per unit of price movement than a tight intraday stop would.
    BASE_RISK_PERCENT: float = 1.0
    MAX_RISK_PER_TRADE_PERCENT: float = risk_limits.PLATFORM_MAX_RISK_PER_TRADE_PERCENT
    # Sourced from risk_limits.py -- the ceilings the public site promises
    # clients (5% daily / 10% weekly). Were 8.0 / 15.0 here: tighter than
    # the other two bots, still looser than what was advertised.
    MAX_DAILY_LOSS_PERCENT: float = risk_limits.PLATFORM_MAX_DAILY_LOSS_PERCENT
    MAX_DRAWDOWN_PERCENT: float = risk_limits.PLATFORM_MAX_DRAWDOWN_PERCENT
    MAX_WEEKLY_LOSS_PERCENT: float = risk_limits.PLATFORM_MAX_WEEKLY_LOSS_PERCENT
    MAX_CONCURRENT_TRADES: int = 3
    MAX_DAILY_TRADES: int = 3        # a backstop, not expected to bind -- this strategy fires
                                      # rarely by construction (D1 structure changes slowly)
    MAX_POSITION_DURATION_DAYS: float = 20.0  # failsafe: a swing setup unresolved in 20 days
                                               # has likely stopped being the setup that fired it
    BREAKEVEN_TRIGGER_R: float = 1.0 # move SL to entry once price is 1R in favor

    SCAN_INTERVAL_SECONDS: int = 900   # 15 min -- D1/H4 structure doesn't change bar to bar;
                                        # no reason to hammer MT5 every couple seconds
    POSITION_MANAGE_INTERVAL_SECONDS: int = 60
    # 30s, not 60s: both watchdogs (BotStatusSync in the browser and
    # monitor-bot-health) treat a heartbeat older than 90s as a crash, so a
    # 60s cadence left only one beat of margin. One failed send marked a
    # healthy bot crashed and stopped it. See hybrid_trading_bot_multiuser.py.
    HEARTBEAT_INTERVAL: int = 30


config = SwingTradingConfig()

SYMBOL_SPECS = {
    "EURUSDm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "GBPUSDm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "USDJPYm": {"pip_size": 0.01, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "XAUUSDm": {"pip_size": 0.01, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "XAGUSDm": {"pip_size": 0.001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "AUDUSDm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "NZDUSDm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "USDCADm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "USDCHFm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "BTCUSDm": {"pip_size": 1.0, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 10.0},
    # Added so this table covers every symbol in SYMBOLS. Values copied
    # verbatim from hybrid_trading_bot_multiuser.py so the three bots agree on
    # instrument specs -- a symbol that is scanned but missing here would get
    # no spec at sizing time.
    "ETHUSDm": {"pip_size": 0.01, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 10.0},
    "USOILm": {"pip_size": 0.01, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "GBPJPYm": {"pip_size": 0.01, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
}


def get_symbol_specs(symbol: str) -> Dict:
    """Real broker spec when MT5 has it; static fallback table otherwise --
    same fallback shape as intraday.py's get_symbol_specs, kept independent
    here rather than imported (importing a live script for its side effects
    is exactly the fragility backtest/bot_loader.py has to work around)."""
    info = mt5.symbol_info(symbol)
    if info:
        pip_size = info.point * 10 if info.digits in (3, 5) else info.point
        return {
            'pip_size': pip_size,
            'min_lot': info.volume_min,
            'max_lot': info.volume_max,
            'lot_step': info.volume_step,
            'trade_tick_value': info.trade_tick_value,
            'trade_tick_size': info.trade_tick_size,
        }
    return SYMBOL_SPECS.get(symbol, {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0})


def get_market_data(symbol: str, timeframe: int, bars: int) -> Optional[pd.DataFrame]:
    """Fetch market data from MT5 -- same shape/contract as the other two
    bot files' get_market_data, so a backtest-harness replay patch works
    the same way here (see backtest/replay_data.py)."""
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        return df
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return None


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


# =============================================================================
# STRUCTURAL ANALYSIS -- pure functions, no mt5.* calls, no lookahead
# beyond whatever's already in the dataframe passed in. This is what makes
# detect_structural_swing_signal() below safely reusable by both the live
# loop and the backtest harness.
# =============================================================================

def find_swing_points(df: pd.DataFrame, lookback: int = 3) -> Tuple[List[int], List[int]]:
    """
    Fractal swing-point detection: bar i is a confirmed swing high if its
    `high` is the max of the [i-lookback, i+lookback] window, a confirmed
    swing low if its `low` is the min of the same window. Only indices with
    `lookback` bars on BOTH sides are considered, so every point this
    returns is confirmed using bars already present in `df` -- nothing
    here needs a bar that hasn't happened yet relative to df's last row.

    Consecutive duplicate levels (a flat top/bottom spanning several bars)
    are collapsed to their first occurrence so classify_structure doesn't
    see the same physical swing point counted twice.
    """
    highs = df['high'].to_numpy()
    lows = df['low'].to_numpy()
    n = len(df)
    swing_highs: List[int] = []
    swing_lows: List[int] = []
    for i in range(lookback, n - lookback):
        window_h = highs[i - lookback:i + lookback + 1]
        if highs[i] >= window_h.max() and (not swing_highs or highs[swing_highs[-1]] != highs[i]):
            swing_highs.append(i)
        window_l = lows[i - lookback:i + lookback + 1]
        if lows[i] <= window_l.min() and (not swing_lows or lows[swing_lows[-1]] != lows[i]):
            swing_lows.append(i)
    return swing_highs, swing_lows


def classify_structure(df: pd.DataFrame, swing_highs: List[int], swing_lows: List[int]) -> Optional[str]:
    """
    "BULLISH" if the two most recent confirmed swing highs AND the two
    most recent confirmed swing lows both step up (higher-high AND
    higher-low); "BEARISH" if both step down; None (no read) if there
    aren't at least two of each yet, or the sequence disagrees (e.g. a
    higher high but a lower low -- expanding range, not real structure).
    """
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return None
    h_prev, h_last = df['high'].iloc[swing_highs[-2]], df['high'].iloc[swing_highs[-1]]
    l_prev, l_last = df['low'].iloc[swing_lows[-2]], df['low'].iloc[swing_lows[-1]]
    if h_last > h_prev and l_last > l_prev:
        return "BULLISH"
    if h_last < h_prev and l_last < l_prev:
        return "BEARISH"
    return None


def fib_zone(leg_start: float, leg_end: float, near: float, far: float) -> Tuple[float, float]:
    """Price bounds of the retracement zone between `near` and `far` of the
    leg_start->leg_end move (order-independent -- always returns
    (low, high))."""
    diff = leg_end - leg_start
    p_near = leg_end - diff * near
    p_far = leg_end - diff * far
    return (min(p_near, p_far), max(p_near, p_far))


def is_rejection_candle(bar: pd.Series, direction: str) -> bool:
    """A bar that closes back in `direction` occupying at least the top
    (BUY) / bottom (SELL) 60% of its own range -- a simple, checkable
    definition of "price turned here", not just "price touched here"."""
    rng = bar['high'] - bar['low']
    if rng <= 0:
        return False
    if direction == "BUY":
        return bar['close'] > bar['open'] and (bar['close'] - bar['low']) / rng >= 0.6
    return bar['close'] < bar['open'] and (bar['high'] - bar['close']) / rng >= 0.6


def find_nearest_target(df: pd.DataFrame, swing_highs: List[int], swing_lows: List[int],
                         direction: str, entry_price: float) -> Optional[float]:
    """Nearest confirmed opposing D1 structural level still ahead of price
    -- the next real swing high above entry for a BUY, the next real swing
    low below entry for a SELL. None if there isn't one in the visible
    window (caller skips the trade rather than inventing a target)."""
    if direction == "BUY":
        candidates = [df['high'].iloc[i] for i in swing_highs if df['high'].iloc[i] > entry_price]
        return min(candidates) if candidates else None
    candidates = [df['low'].iloc[i] for i in swing_lows if df['low'].iloc[i] < entry_price]
    return max(candidates) if candidates else None


def detect_structural_swing_signal(df_d1: pd.DataFrame, df_h4: pd.DataFrame, symbol: str,
                                    swing_lookback: int = None, fib_near: float = None,
                                    fib_far: float = None, min_rr: float = None,
                                    sl_buffer_atr_mult: float = None) -> Optional[Dict]:
    """
    Pure, no-lookahead decision function -- the single source of truth for
    "is there a structural swing setup right now", called identically by
    the live loop (scan_for_signal, using MT5-fetched df_d1/df_h4) and by
    backtest/swing_driver.py (using HistoricalDataset windows). Neither
    caller does anything this function doesn't -- see the module docstring
    for the full rule set this implements.

    df_d1's LAST row must be the most recently CLOSED D1 bar as of "now";
    df_h4's LAST row must be the most recently closed H4 bar. Callers are
    responsible for that (live: copy_rates_from_pos naturally excludes the
    still-forming bar; backtest: HistoricalDataset.window's strict `<
    as_of` filter) -- this function only ever looks at rows already given
    to it.

    Returns None if there's no tradeable setup, otherwise a dict:
    {direction, entry_price, stop_loss, take_profit, reason}.
    """
    lookback = swing_lookback if swing_lookback is not None else config.SWING_LOOKBACK
    near = fib_near if fib_near is not None else config.FIB_ZONE_NEAR
    far = fib_far if fib_far is not None else config.FIB_ZONE_FAR
    rr_min = min_rr if min_rr is not None else config.MIN_RR
    buf_mult = sl_buffer_atr_mult if sl_buffer_atr_mult is not None else config.SL_BUFFER_ATR_MULT

    if len(df_d1) < (lookback * 2 + 10) or len(df_h4) < 10:
        return None

    swing_highs, swing_lows = find_swing_points(df_d1, lookback)
    structure = classify_structure(df_d1, swing_highs, swing_lows)

    # DECISION JOURNAL -- see python_scripts/decision_journal.py. Same
    # instrumentation carried by the scalping and intraday bots, so all three
    # feed one analysis path (backtest/analyze_journal.py).
    _j = dj.DecisionJournal(symbol, strategy='STRUCTURAL_SWING')
    _j.note(dj.STRUCTURE, 'd1_structure',
            dj.CONFIRMED if structure else dj.VETO,
            (f'D1 structure is {structure} -- higher-highs AND higher-lows (or the '
             f'mirror) across the last two confirmed swings of each' if structure
             else 'D1 swing sequence disagrees (expanding range) or too few pivots yet'),
            value=structure)
    if structure is None:
        _j.decide(False, 'no clean D1 structure')
        dj.record_rejection(_j)
        return None
    direction = "BUY" if structure == "BULLISH" else "SELL"
    _j.direction = direction

    # The most recent impulse leg in the direction of bias: for BULLISH,
    # the move from the last confirmed swing low up to the last confirmed
    # swing high (whichever of those two is more recent defines the leg's
    # end -- the leg must actually be the most recent move, not a stale one).
    if direction == "BUY":
        leg_start_idx, leg_end_idx = swing_lows[-1], swing_highs[-1]
        if leg_end_idx <= leg_start_idx:
            _j.note(dj.STRUCTURE, 'impulse_leg', dj.VETO,
                    'most recent swing high precedes the swing low -- no completed up-leg')
            _j.decide(False, 'stale/ambiguous impulse leg')
            dj.record_rejection(_j)
            return None  # the "high" isn't actually after the "low" -- stale/ambiguous leg
        leg_start = df_d1['low'].iloc[leg_start_idx]
        leg_end = df_d1['high'].iloc[leg_end_idx]
    else:
        leg_start_idx, leg_end_idx = swing_highs[-1], swing_lows[-1]
        if leg_end_idx <= leg_start_idx:
            _j.note(dj.STRUCTURE, 'impulse_leg', dj.VETO,
                    'most recent swing low precedes the swing high -- no completed down-leg')
            _j.decide(False, 'stale/ambiguous impulse leg')
            dj.record_rejection(_j)
            return None
        leg_start = df_d1['high'].iloc[leg_start_idx]
        leg_end = df_d1['low'].iloc[leg_end_idx]

    zone_low, zone_high = fib_zone(leg_start, leg_end, near, far)

    # H4 entry trigger: the most recently closed H4 bar must have traded
    # into the zone AND closed as a rejection candle in bias direction.
    h4_bar = df_h4.iloc[-1]
    touched_zone = h4_bar['low'] <= zone_high and h4_bar['high'] >= zone_low
    _rej_ok = is_rejection_candle(h4_bar, direction)
    _j.note(dj.LOCATION, 'h4_touched_fib_zone',
            dj.CONFIRMED if touched_zone else dj.VETO,
            (f'H4 traded into the {near:.3f}-{far:.3f} Fib retracement zone' if touched_zone
             else 'H4 never reached the Fib retracement zone'))
    _j.note(dj.TRIGGER, 'h4_rejection_candle',
            dj.CONFIRMED if _rej_ok else dj.VETO,
            ('H4 closed back in bias direction -- price actually turned here' if _rej_ok
             else 'H4 touched the zone but did not close as a rejection'))
    if not touched_zone or not is_rejection_candle(h4_bar, direction):
        _j.decide(False, 'no H4 rejection inside the Fib zone')
        dj.record_rejection(_j)
        return None

    entry_price = float(h4_bar['close'])

    atr_h4 = calculate_atr(df_h4['high'], df_h4['low'], df_h4['close'], 14).iloc[-1]
    if pd.isna(atr_h4) or atr_h4 <= 0:
        return None
    buffer = atr_h4 * buf_mult

    # Structural stop: beyond the extreme of the CURRENT pullback (the H4
    # bars from the D1 leg's own end up to and including this trigger bar),
    # not the leg's distant origin. Found via the real-data backtest run:
    # a stop at the full leg's origin makes sl_dist scale with the whole
    # leg's range, which routinely swamped the reward to the next real
    # opposing level and made this strategy's own MIN_RR filter reject
    # nearly every real setup on real XAUUSDm data (every candidate that
    # cleared the zone-touch + rejection-candle bar still failed RR, most
    # by a wide margin). The pullback's own high/low -- often the trigger
    # candle's own wick -- is the point that actually invalidates THIS
    # pullback continuing, which is what the trade is betting on; the
    # leg's origin is what invalidates the D1 BIAS, a materially larger
    # and less relevant move for sizing this specific entry's stop.
    leg_end_time = df_d1['time'].iloc[leg_end_idx]
    pullback_bars = df_h4[df_h4['time'] >= leg_end_time]
    if len(pullback_bars) == 0:
        pullback_bars = df_h4.tail(1)
    if direction == "BUY":
        local_extreme = float(pullback_bars['low'].min())
        stop_loss = local_extreme - buffer
    else:
        local_extreme = float(pullback_bars['high'].max())
        stop_loss = local_extreme + buffer

    sl_dist = abs(entry_price - stop_loss)
    if sl_dist <= 0:
        _j.note(dj.RISK, 'sl_distance', dj.VETO, 'computed stop distance is zero')
        _j.decide(False, 'zero stop distance')
        dj.record_rejection(_j)
        return None

    target = find_nearest_target(df_d1, swing_highs, swing_lows, direction, entry_price)
    _j.note(dj.LIQUIDITY, 'opposing_d1_target',
            dj.CONFIRMED if target is not None else dj.VETO,
            (f'nearest opposing D1 structural level at {target:.5f} used as TP'
             if target is not None else
             'no opposing D1 structural level ahead of price -- no real target to aim at'),
            value=round(target, 5) if target is not None else None)
    if target is None:
        _j.decide(False, 'no opposing D1 structural target')
        dj.record_rejection(_j)
        return None
    reward_dist = abs(target - entry_price)

    # PREMIUM/DISCOUNT (Raja Banks research, market_intelligence.py section
    # 8): this strategy already has its own Fibonacci retracement-zone
    # entry (fib_zone above) -- the OTE equivalent -- but no directional
    # premium/discount read, on the same D1 series already used for
    # structure/leg detection above. A favorable read is one more
    # independent reason this setup deserves the trade, not a new
    # requirement -- loosens the RR floor slightly (never tightens it),
    # same discipline as the change made to Shaakuni SSM this session (see
    # backtest/README.md). Deliberately modest (rr_min - 0.3, floored at
    # 1.0): this strategy's own MIN_RR has previously been found, on real
    # data, to reject nearly every real setup (see the stop-loss comment
    # above) -- and its current real-data trade count is small enough (3
    # trades on the 90-day XAUUSDm sample) that a bold loosening here
    # can't be verified with the same removed-vs-kept rigor used
    # elsewhere; a small, cautious change is the honest match for that.
    equilibrium = mi.compute_equilibrium_zone(df_d1, lookback=lookback)
    pd_conf = mi.premium_discount_confluence(direction, equilibrium)
    effective_rr_min = rr_min
    if equilibrium is not None and pd_conf['favorable']:
        effective_rr_min = max(1.0, rr_min - 0.3)

    _rr = reward_dist / sl_dist
    if equilibrium is not None:
        _j.note(dj.LOCATION, 'premium_discount',
                dj.CONFIRMED if pd_conf['favorable'] else dj.AGAINST,
                pd_conf['reason'], value=equilibrium['zone'])
    else:
        _j.note(dj.LOCATION, 'premium_discount', dj.NEUTRAL,
                'no D1 dealing range established yet')
    _j.measure(rr=round(_rr, 2), min_rr_required=round(effective_rr_min, 2),
               sl_distance=round(sl_dist, 5), atr_h4=round(float(atr_h4), 5))
    if reward_dist / sl_dist < effective_rr_min:
        _j.note(dj.RISK, 'rr_floor', dj.VETO,
                f'RR {_rr:.2f} below the {effective_rr_min:.2f} required')
        _j.decide(False, f'RR {_rr:.2f} < {effective_rr_min:.2f}')
        dj.record_rejection(_j)
        return None
    _j.note(dj.RISK, 'rr_floor', dj.CONFIRMED,
            f'RR {_rr:.2f} clears the {effective_rr_min:.2f} bar')
    _j.decide(True, f'D1 structure + H4 Fib rejection confirmed, RR {_rr:.2f}')

    return {
        'direction': direction,
        'entry_price': entry_price,
        'stop_loss': stop_loss,
        'take_profit': float(target),
        'reason': f"STRUCTURAL_SWING_{structure}_RR{reward_dist / sl_dist:.1f}",
        'equilibrium_zone': equilibrium,
        'journal': _j.to_dict(),
    }


# =============================================================================
# RISK -- same correctness pattern this audit just fixed in intraday.py's
# validate_trade_risk()/place_intraday_trade(): one shared projection that
# derives REAL risk from the lot size the trade will actually get
# (including the broker's min-lot floor), computed once and used both to
# decide whether the trade is allowed and to size it, so the two can never
# diverge.
# =============================================================================

def effective_risk_percent(symbol: str) -> float:
    """
    MARKET INTELLIGENCE INTEGRATION: config.BASE_RISK_PERCENT scaled by
    volatility_target_multiplier() -- standard vol-targeting instead of a
    flat % risked on every trade regardless of how calm or violent the
    instrument currently is. Called by both validate_trade_risk() and
    place_swing_trade() so the risk percent that gets validated is always
    exactly the one actually used for sizing -- same "one shared
    computation, never two" discipline as project_lot_and_risk() itself.
    Falls back to the unscaled base risk (multiplier 1.0) if H4 data isn't
    available -- never blocks a trade over a data hiccup.
    """
    df_h4 = get_market_data(symbol, config.ENTRY_TF, config.ENTRY_BARS)
    multiplier = mi.volatility_target_multiplier(df_h4) if df_h4 is not None else 1.0
    return config.BASE_RISK_PERCENT * multiplier


def project_lot_and_risk(symbol: str, entry_price: float, stop_loss: float,
                          risk_percent: float, account_equity: float) -> Dict[str, float]:
    spec = get_symbol_specs(symbol)
    pip_risk = abs(entry_price - stop_loss) / spec['pip_size']

    tick_val = spec.get('trade_tick_value', 0)
    tick_size = spec.get('trade_tick_size', spec.get('pip_size', 0.0001))
    lot_step = spec.get('lot_step', 0.01)

    intended_risk_amount = account_equity * (risk_percent / 100.0)

    if tick_val and tick_val > 0 and tick_size > 0:
        pip_value_per_lot = (tick_val / tick_size) * spec.get('pip_size', tick_size)
    else:
        pip_value_per_lot = 10.0  # forex fallback -- standard pairs only

    lot_raw = intended_risk_amount / max(pip_risk * pip_value_per_lot, 0.001)
    lot_size = risk_limits.floor_volume_to_step(
        lot_raw, lot_step, spec['min_lot'], spec['max_lot'])

    actual_risk_amount = lot_size * pip_risk * pip_value_per_lot
    actual_risk_percent = (actual_risk_amount / account_equity) * 100 if account_equity > 0 else 0.0

    return {
        'spec': spec, 'pip_risk': pip_risk, 'lot_raw': lot_raw, 'lot_size': lot_size,
        'pip_value_per_lot': pip_value_per_lot,
        'intended_risk_amount': intended_risk_amount, 'intended_risk_percent': risk_percent,
        'actual_risk_amount': actual_risk_amount, 'actual_risk_percent': actual_risk_percent,
    }


def validate_trade_risk(signal: Dict, account_equity: float) -> Tuple[bool, str]:
    """Validates against the REAL risk this trade's lot size will carry
    (via project_lot_and_risk), not the configured risk_percent restated
    algebraically -- see this file's module docstring / intraday.py's
    equivalent fix for why that distinction matters."""
    try:
        symbol = signal['symbol']
        risk_percent = signal.get('risk_percent') or effective_risk_percent(symbol)
        projection = project_lot_and_risk(symbol, signal['entry_price'], signal['stop_loss'],
                                           risk_percent, account_equity)
        actual_risk_percent = projection['actual_risk_percent']
        if projection['lot_size'] <= 0:
            return False, (f"Calculated volume for {symbol} is below broker minimum; "
                           "trade rejected rather than rounding risk upward")
        if projection['lot_raw'] < projection['spec']['min_lot']:
            logger.info(
                f"[RISK] {symbol}: ideal lot {projection['lot_raw']:.5f} < broker min "
                f"{projection['spec']['min_lot']} -- real risk at min_lot is "
                f"{actual_risk_percent:.2f}% vs intended {risk_percent:.2f}%"
            )

        if actual_risk_percent > config.MAX_RISK_PER_TRADE_PERCENT:
            return False, f"Trade risk {actual_risk_percent:.2f}% exceeds per-trade limit {config.MAX_RISK_PER_TRADE_PERCENT}%"

        if state.daily_start_equity > 0:
            current_daily_loss_pct = abs(state.daily_pnl / state.daily_start_equity) * 100
            if current_daily_loss_pct + actual_risk_percent > config.MAX_DAILY_LOSS_PERCENT:
                return False, f"Potential loss {current_daily_loss_pct + actual_risk_percent:.2f}% would exceed daily limit {config.MAX_DAILY_LOSS_PERCENT}%"

        account_info = mt5.account_info()
        if account_info and state.daily_start_equity > 0:
            potential_equity_after_loss = account_info.equity - projection['actual_risk_amount']
            potential_total_drawdown_pct = ((state.daily_start_equity - potential_equity_after_loss) / state.daily_start_equity) * 100
            if potential_total_drawdown_pct > config.MAX_DRAWDOWN_PERCENT:
                return False, f"Potential drawdown {potential_total_drawdown_pct:.2f}% would exceed limit {config.MAX_DRAWDOWN_PERCENT}%"

        open_count = len(state.open_positions)
        if open_count >= config.MAX_CONCURRENT_TRADES:
            return False, f"Max concurrent trades reached ({open_count}/{config.MAX_CONCURRENT_TRADES})"

        # --- CURRENCY CONCENTRATION ---
        # Counting positions does not see that long EURUSD + long GBPUSD +
        # long AUDUSD is one short-USD trade at triple size: three tickets,
        # one macro bet, and one USD rally takes all three stops together.
        # This bot holds for days and had no correlation control of any kind,
        # which mattered little at 6 symbols and matters a great deal at 13
        # (seven of them USD pairs). Nets exposure per currency instead, so a
        # genuine hedge like long EURUSD + long USDCHF still passes.
        _ok, _why = risk_limits.check_currency_exposure(
            symbol, signal.get('direction', 'BUY'), state.open_positions.values()
        )
        if not _ok:
            return False, _why

        if state.daily_trades >= config.MAX_DAILY_TRADES:
            return False, f"Max daily trades reached ({state.daily_trades}/{config.MAX_DAILY_TRADES})"

        logger.info(
            f"[RISK CHECK] {symbol} validated: Risk={actual_risk_percent:.2f}%, "
            f"Pips={projection['pip_risk']:.1f}, Amount=${projection['actual_risk_amount']:.2f}"
        )
        return True, "Risk within acceptable limits"
    except Exception as e:
        logger.error(f"Error validating trade risk: {e}")
        return False, f"Validation error: {e}"


def check_emergency_conditions(account_info) -> bool:
    """Self-healing from day one -- see intraday.py's fixed version /
    this file's module docstring for exactly what bug this structure
    avoids (dividing by an unset daily_start_equity baseline)."""
    if not account_info:
        return False

    if state.daily_start_equity <= 0:
        _today_key = risk_limits.utc_day_key()
        state.daily_start_equity = risk_limits.load_or_init_daily_baseline(
            DATA_DIR, account_info.equity, _today_key)
        state.last_reset_day = _today_key
        logger.warning(
            f"[RISK] daily_start_equity was not set -- restored/initialized "
            f"persistent baseline ${state.daily_start_equity:.2f} for {_today_key}"
        )
        if state.daily_start_equity <= 0:
            return True
        return False

    _eq_drop = state.daily_start_equity - account_info.equity
    daily_loss_amount = -_eq_drop if _eq_drop > 0 else (state.daily_pnl if state.daily_pnl < 0 else 0)
    # Guarded like intraday.py's equivalent: a zero baseline (MT5 not finished
    # logging in, so equity read as 0) raised ZeroDivisionError and killed the
    # session in the scalping bot. Same shape of bug lived here.
    daily_loss_percent = abs(daily_loss_amount / state.daily_start_equity) * 100 if state.daily_start_equity else 0.0

    # Daily / weekly / drawdown ceilings via risk_limits.py -- one shared
    # definition so these can't drift from what the public site promises
    # (this file previously enforced 8%/15% against an advertised 5%/10%,
    # and no weekly limit existed anywhere).
    state.peak_equity = max(getattr(state, 'peak_equity', 0.0) or 0.0,
                            state.daily_start_equity, account_info.equity)
    _verdict = risk_limits.evaluate_risk_limits(
        current_equity=account_info.equity,
        daily_start_equity=state.daily_start_equity,
        weekly_start_equity=getattr(state, 'weekly_start_equity', None),
        peak_equity=state.peak_equity,
        limits=risk_limits.resolve_user_limits(getattr(state, 'user_risk_settings', None)),
    )
    if _verdict.breached:
        logger.critical(f"[EMERGENCY] {_verdict.reason}: {_verdict.detail}")
        send_telegram_message(f"\U0001F6D1 Structural Swing Pro halted: {_verdict.detail}")
        return True

    current_drawdown_pct = ((state.daily_start_equity - account_info.equity) / state.daily_start_equity) * 100 if state.daily_start_equity else 0.0

    if daily_loss_percent >= config.MAX_DAILY_LOSS_PERCENT * 0.7:
        logger.warning(f"[WARNING] Approaching daily loss limit: {daily_loss_percent:.2f}% / {config.MAX_DAILY_LOSS_PERCENT}%")
    if current_drawdown_pct >= config.MAX_DRAWDOWN_PERCENT * 0.7:
        logger.warning(f"[WARNING] Approaching max drawdown: {current_drawdown_pct:.2f}% / {config.MAX_DRAWDOWN_PERCENT}%")

    return False


# =============================================================================
# STATE / DB
# =============================================================================
class SwingTradingState:
    def __init__(self):
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.daily_start_equity = 0.0
        self.open_positions: Dict[int, Dict] = {}
        self.position_open_times: Dict[int, datetime] = {}
        self.be_moved: set = set()
        self.last_reset_day: Optional[str] = None
        self.symbol_cooldowns: Dict[str, datetime] = {}


state = SwingTradingState()


class SupabaseManager:
    def __init__(self):
        self.client = supabase
        self.user_id = USER_ID
        self.strategy_id = STRATEGY_ID

    def record_trade(self, ticket: int, symbol: str, direction: str, lot_size: float,
                      entry_price: float, sl: float, tp: float, strategy: str,
                      opened_at: Optional[datetime] = None) -> None:
        try:
            trade_data = {
                'user_id': self.user_id, 'strategy_id': self.strategy_id,
                'ticket': int(ticket), 'symbol': symbol, 'trade_type': direction,
                'quantity': lot_size, 'entry_price': entry_price, 'status': 'open',
                'opened_at': (opened_at or datetime.now(timezone.utc)).isoformat(),
                'metadata': {'stop_loss': sl, 'take_profit': tp, 'strategy_name': strategy},
            }
            self.client.table('trades').upsert(trade_data, on_conflict='ticket,user_id').execute()
            logger.info(f"[DB] Trade {ticket} synced to dashboard")
        except Exception as e:
            logger.error(f"[DB ERROR] Trade sync failed: {e}")

    def get_open_tickets(self) -> List[int]:
        try:
            response = self.client.table('trades').select('ticket') \
                .eq('user_id', self.user_id).eq('strategy_id', self.strategy_id) \
                .eq('status', 'open').execute()
            return [item['ticket'] for item in response.data] if response.data else []
        except Exception as e:
            logger.error(f"[DB ERROR] Failed to fetch open tickets: {e}")
            return []

    def update_trade_close(self, ticket: int, close_price: float, profit: float) -> None:
        try:
            update_data = {
                'exit_price': float(close_price), 'profit_loss': float(profit),
                'closed_at': datetime.now(timezone.utc).isoformat(), 'status': 'closed',
            }
            self.client.table('trades').update(update_data).eq('ticket', int(ticket)).eq('user_id', self.user_id).execute()
        except Exception as e:
            logger.error(f"[DB ERROR] Close update failed: {e}")

    def update_trade_metadata(self, ticket: int, updates: Dict) -> None:
        """
        Merge keys into a trade's metadata JSONB without clobbering what's
        already there (read-modify-write, same pattern the scalping bot's
        update_metadata uses). Added for the decision-journal close-out:
        exit attribution, MFE/MAE and the management log all land here.

        Best-effort by design -- analytics must never break close bookkeeping,
        so a failure logs and returns rather than propagating.
        """
        try:
            res = self.client.table('trades').select('metadata') \
                .eq('ticket', int(ticket)).eq('user_id', self.user_id).execute()
            if not res.data:
                return
            merged = dict(res.data[0].get('metadata') or {})
            merged.update({k: dj._plain(v) for k, v in updates.items()})
            self.client.table('trades').update({'metadata': merged}) \
                .eq('ticket', int(ticket)).eq('user_id', self.user_id).execute()
        except Exception as e:
            logger.debug(f"[DB] metadata update failed for #{ticket}: {e}")

    def send_heartbeat(self) -> None:
        try:
            account_info = mt5.account_info()
            heartbeat_data = {
                'user_id': self.user_id, 'strategy_id': self.strategy_id,
                'last_heartbeat': datetime.now(timezone.utc).isoformat(), 'status': 'running',
                'mt5_connected': bool(account_info), 'pid': os.getpid(),
                'balance': account_info.balance if account_info else 0,
                'equity': account_info.equity if account_info else 0,
            }
            existing = self.client.table('bot_heartbeats').select('user_id') \
                .eq('user_id', self.user_id).eq('strategy_id', self.strategy_id).execute()
            if existing.data:
                self.client.table('bot_heartbeats').update(heartbeat_data).eq('user_id', self.user_id).eq('strategy_id', self.strategy_id).execute()
            else:
                self.client.table('bot_heartbeats').insert(heartbeat_data).execute()
        except Exception as e:
            logger.error(f"[HEARTBEAT ERROR] {e}")


db_manager = SupabaseManager()


def send_telegram_message(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'},
            timeout=10,
        )
    except Exception as e:
        logger.error(f"[TELEGRAM ERROR] {e}")


# =============================================================================
# ORDER EXECUTION / POSITION MANAGEMENT
# =============================================================================

def scan_for_signal(symbol: str) -> Optional[Dict]:
    """
    MARKET INTELLIGENCE INTEGRATION: auction-theory regime read (see
    market_intelligence.py's module docstring for the full "why" -- ADX/
    EMA-stack regime detection is retail-indicator thinking, not how a
    professional desk actually reads a market) now gates and extends the
    structural swing signal instead of taking it at face value:

    1. A confirmed structural pullback-continuation signal that fires
       while the H4 auction state is IMBALANCE in the OPPOSITE direction
       is a real red flag -- price is still making a genuine initiative
       move against the signal's own direction, not accepting the pullback
       read. Skipped rather than fought.
    2. When there's NO structural continuation setup but the H4 auction
       state reads BALANCE (price rotating inside its own value area --
       the one regime none of this bot's D1/H4 trend logic was ever
       designed for), detect_balance_fade_signal() gets a chance to fire
       instead. Its output is already shaped to match what
       place_swing_trade() expects (direction/stop_loss/take_profit) --
       same dict contract detect_structural_swing_signal() uses -- so no
       adapter is needed.
    """
    df_d1 = get_market_data(symbol, config.STRUCTURE_TF, config.STRUCTURE_BARS)
    df_h4 = get_market_data(symbol, config.ENTRY_TF, config.ENTRY_BARS)
    if df_d1 is None or df_h4 is None:
        return None

    auction = mi.classify_auction_state(df_h4)

    signal = detect_structural_swing_signal(df_d1, df_h4, symbol)
    if signal:
        conflicting = (signal['direction'] == "BUY" and auction["state"] == "IMBALANCE_DOWN") or \
                      (signal['direction'] == "SELL" and auction["state"] == "IMBALANCE_UP")
        if conflicting:
            logger.info(
                f"[AUCTION VETO] {symbol}: structural {signal['direction']} setup rejected -- "
                f"H4 auction state is {auction['state']} (opposing initiative move still active)"
            )
            signal = None

    if signal is None and auction["state"] == "BALANCE":
        signal = mi.detect_balance_fade_signal(df_h4, symbol)

    if signal:
        signal['symbol'] = symbol
        # EFFICIENCY FIX: validate_trade_risk() and place_swing_trade() each
        # independently called effective_risk_percent(symbol), which does
        # its own fresh get_market_data(H4) fetch -- on top of the df_h4
        # already fetched right here. That's 3 separate MT5 round-trips for
        # the identical H4 series per symbol per scan-to-trade cycle instead
        # of 1. df_h4 is already in hand, so compute it once here and hand
        # it down on the signal dict; both call sites fall back to
        # effective_risk_percent(symbol) (unchanged) if it's ever missing.
        signal['risk_percent'] = config.BASE_RISK_PERCENT * mi.volatility_target_multiplier(df_h4)
    return signal


def place_swing_trade(signal: Dict, account_equity: float) -> bool:
    try:
        symbol = signal['symbol']
        direction = signal['direction']

        is_valid, reason = validate_trade_risk(signal, account_equity)
        if not is_valid:
            logger.warning(f"[RISK VETO] Trade rejected for {symbol}: {reason}")
            return False

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            logger.error(f"Cannot get tick data for {symbol}")
            return False
        entry_price = tick.ask if direction == "BUY" else tick.bid

        projection = project_lot_and_risk(symbol, entry_price, signal['stop_loss'],
                                           signal.get('risk_percent') or effective_risk_percent(symbol),
                                           account_equity)
        lot_size = projection['lot_size']
        logger.info(
            f"[LOT] {symbol}: risk=${projection['actual_risk_amount']:.2f} "
            f"pip_risk={projection['pip_risk']:.4f} lot={lot_size}"
        )

        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logger.error(f"Could not get symbol info for {symbol}")
            return False
        digits = symbol_info.digits

        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": round(float(entry_price), digits),
            "sl": round(float(signal['stop_loss']), digits),
            "tp": round(float(signal['take_profit']), digits),
            "deviation": 20,
            "magic": MAGIC_NUMBER,
            "comment": str(f"Swing_{signal['reason']}")[:30],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"[ORDER FAILED] {symbol}: {result.comment if result else 'no result'} "
                         f"({result.retcode if result else '?'})")
            return False

        ticket = result.order
        logger.info(f"[OK] TRADE OPENED: {symbol} {direction} | Lot: {lot_size} | "
                    f"SL: {signal['stop_loss']:.5f} | TP: {signal['take_profit']:.5f}")

        state.open_positions[ticket] = {
            'symbol': symbol, 'direction': direction, 'entry_price': entry_price,
            'stop_loss': signal['stop_loss'], 'take_profit': signal['take_profit'],
            'lot_size': lot_size, 'reason': signal['reason'],
            # Entry reasoning carried on the position so the close-out can
            # persist the complete case (entry + management + exit) together.
            'journal': signal.get('journal'),
        }
        state.position_open_times[ticket] = datetime.now(timezone.utc)
        state.daily_trades += 1
        state.symbol_cooldowns[symbol] = datetime.now(timezone.utc) + timedelta(days=1)

        db_manager.record_trade(ticket, symbol, direction, lot_size, entry_price,
                                 signal['stop_loss'], signal['take_profit'], signal['reason'])
        send_telegram_message(
            f"\U0001F4C8 <b>Structural Swing {direction}</b>\n{symbol} @ {entry_price:.5f}\n"
            f"SL: {signal['stop_loss']:.5f} | TP: {signal['take_profit']:.5f}\n{signal['reason']}"
        )
        return True
    except Exception as e:
        logger.error(f"Error placing swing trade: {e}", exc_info=True)
        return False


def modify_position_sl(position, new_sl: float) -> bool:
    try:
        symbol_info = mt5.symbol_info(position.symbol)
        if not symbol_info:
            return False
        request = {
            "action": mt5.TRADE_ACTION_SLTP, "symbol": position.symbol,
            "position": position.ticket, "sl": round(new_sl, symbol_info.digits), "tp": position.tp,
        }
        result = mt5.order_send(request)
        return bool(result and result.retcode == mt5.TRADE_RETCODE_DONE)
    except Exception as e:
        logger.error(f"[ERROR] Exception modifying SL: {e}")
        return False


def close_position(position) -> bool:
    try:
        symbol = position.symbol
        ticket = position.ticket
        if position.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": position.volume,
            "type": order_type, "position": ticket, "price": price, "deviation": 20,
            "magic": MAGIC_NUMBER, "comment": "Swing_Close",
            "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Failed to close position: {result.comment if result else 'no result'}")
            return False

        profit = 0.0
        try:
            if hasattr(result, 'deal') and result.deal > 0:
                deals = mt5.history_deals_get(ticket=result.deal)
                if deals:
                    profit = deals[0].profit
        except Exception as e:
            logger.error(f"Error fetching close profit: {e}")

        logger.info(f"[OK] Position closed: {symbol} | Ticket: {ticket} | P&L: ${profit:.2f}")
        _pi = state.open_positions.get(ticket)
        if _pi:
            _attribute_and_log_exit(int(ticket), _pi, result.price, profit)
        db_manager.update_trade_close(int(ticket), result.price, profit)
        state.daily_pnl += profit
        state.open_positions.pop(ticket, None)
        state.position_open_times.pop(ticket, None)
        state.be_moved.discard(ticket)
        return True
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        return False


def _record_management(pos_info: Dict, what: str, why: str, **extra) -> None:
    """Append a management action to this position's live journal. Exception-safe
    and return-value-free: instrumentation must never interfere with position
    management. Persisted by sync_closed_trades()/close_position()."""
    try:
        pos_info.setdefault('management', []).append({
            'what': what, 'why': why,
            'at': datetime.now(timezone.utc).isoformat(),
            **{k: dj._plain(v) for k, v in extra.items()},
        })
    except Exception:
        pass


def _attribute_and_log_exit(ticket: int, pos_info: Dict, close_price: float,
                            profit: float) -> None:
    """
    WHY this swing trade ended -- the diagnosis, not just the P&L.

    Swing trades are held for days, so a bad one is expensive and worth
    explaining: the same attribution the scalping bot now produces, using the
    MFE/MAE accumulated in manage_open_positions(). Wrapped so analytics can
    never break close bookkeeping.
    """
    try:
        entry = pos_info.get('entry_price', 0) or 0
        init_sl = pos_info.get('stop_loss', 0) or 0
        exit_reason = 'TP' if profit > 0 else ('BE' if abs(profit) < 1e-9 else 'SL')
        open_time = state.position_open_times.get(ticket)
        held = ((datetime.now(timezone.utc) - open_time).total_seconds()
                if open_time else None)
        attr = dj.attribute_live_exit(
            direction=pos_info.get('direction', 'BUY'),
            entry_price=entry, initial_sl=init_sl,
            take_profit=pos_info.get('take_profit'),
            exit_price=close_price, exit_reason=exit_reason,
            mfe_r=pos_info.get('mfe_r'), mae_r=pos_info.get('mae_r'),
            held_seconds=held, be_moved=(ticket in state.be_moved),
            partial_taken=False,   # this strategy takes no partials by design
        )
        logger.info(f"[WHY CLOSED] {pos_info.get('symbol')} #{ticket} {exit_reason}: {attr}")
        db_manager.update_trade_metadata(ticket, {
            'exit_attribution': attr,
            'mfe_r': round(pos_info.get('mfe_r') or 0.0, 3),
            'mae_r': round(pos_info.get('mae_r') or 0.0, 3),
            'held_seconds': round(held, 1) if held else None,
            'be_moved': ticket in state.be_moved,
            'management': pos_info.get('management', []),
            'journal': pos_info.get('journal'),
        })
    except Exception as e:
        logger.debug(f"[WHY CLOSED] attribution failed for #{ticket}: {e}")


def manage_open_positions() -> None:
    """Breakeven-at-1R and a max-duration failsafe -- deliberately simple
    relative to intraday.py's runner/narrative machinery, matching this
    strategy's own simplicity: a swing trade either works toward its
    structural target or it doesn't, there's no session-based partial
    exit logic to replicate here."""
    positions = mt5.positions_get()
    if not positions:
        return
    for pos in positions:
        if pos.magic != MAGIC_NUMBER:
            continue
        ticket = pos.ticket
        pos_info = state.open_positions.get(ticket)
        if pos_info is None:
            continue

        symbol_name = pos.symbol
        direction = pos_info["direction"]
        entry = pos_info['entry_price']
        sl_dist = abs(entry - pos_info['stop_loss'])
        if sl_dist <= 0:
            continue

        current_price = pos.price_current
        favorable_dist = (current_price - entry) if direction == "BUY" else (entry - current_price)
        r_multiple = favorable_dist / sl_dist

        # MAXIMUM FAVOURABLE / ADVERSE EXCURSION, in R -- consumed by
        # decision_journal.attribute_live_exit() when the trade closes. Without
        # it, a stop-out cannot be diagnosed: "SL" cannot distinguish a trade
        # that reached +2R and gave it back (an exit/management failure) from
        # one that never went our way (an entry failure).
        pos_info['mfe_r'] = max(pos_info.get('mfe_r', 0.0) or 0.0, r_multiple)
        pos_info['mae_r'] = min(pos_info.get('mae_r', 0.0) or 0.0, r_multiple)

        # STRUCTURE CONTEXT -- H4, the timeframe this setup was actually read on.
        _df_mgmt = get_market_data(symbol_name, config.ENTRY_TF, 150)
        _atr_mgmt = 0.0
        _spread_mgmt = 0.0
        if _df_mgmt is not None and len(_df_mgmt) > 20:
            try:
                _atr_mgmt = float(calculate_atr(_df_mgmt['high'], _df_mgmt['low'],
                                                _df_mgmt['close']).iloc[-1])
            except Exception:
                _atr_mgmt = 0.0
        _tick = mt5.symbol_info_tick(symbol_name)
        if _tick:
            _spread_mgmt = float(_tick.ask - _tick.bid)
        _digits = mt5.symbol_info(symbol_name).digits if mt5.symbol_info(symbol_name) else 5
        _initial_sl = pos_info.get('initial_sl') or pos_info['stop_loss']
        _current_sl = float(pos.sl) if pos.sl else _initial_sl

        # BREAKEVEN -- STRUCTURAL, AND NOT AT LITERAL ENTRY.
        #
        # The previous behaviour moved the stop to the exact entry price at
        # 1R. On a swing trade held for days that is worse than it sounds:
        # "entry" does not account for the spread paid on the way in or the
        # swap accrued overnight, so a "breakeven" stop-out is a small loss,
        # and a D1/H4 position routinely retraces well past its entry before
        # continuing -- the whole premise of a structural swing entry is that
        # the level holds, not that price never revisits it.
        #
        # breakeven_plan() only acts once a confirmed higher low (BUY) /
        # lower high (SELL) exists above entry and parks the stop behind that
        # swing, includes a cost buffer over entry when it must use entry as
        # the reference, and refuses any level inside the noise band.
        if ticket not in state.be_moved:
            _be = None
            if _df_mgmt is not None:
                _be = st.breakeven_plan(
                    _df_mgmt, direction, entry, _initial_sl, current_price,
                    _current_sl, _atr_mgmt, _spread_mgmt,
                    trigger_r=config.BREAKEVEN_TRIGGER_R, digits=_digits)
            if _be and modify_position_sl(pos, _be['sl']):
                state.be_moved.add(ticket)
                pos_info['stop_loss'] = _be['sl']
                _record_management(pos_info, 'moved_to_breakeven', _be['reason'],
                                   trigger_r=_be['r'], new_sl=_be['sl'])
                logger.info(
                    f"[BREAKEVEN] {symbol_name} ticket {ticket} -> {_be['sl']:.{_digits}f} "
                    f"at {_be['r']:.2f}R -- {_be['reason']}"
                )
            elif r_multiple >= config.BREAKEVEN_TRIGGER_R:
                logger.debug(
                    f"[BREAKEVEN] {symbol_name} at {r_multiple:.2f}R but no confirmed "
                    f"swing above entry yet -- holding the structural stop."
                )

        # STRUCTURAL TRAIL FROM 2R -- previously absent entirely.
        #
        # Without a trail, a swing that ran to +4R and then reversed gave the
        # whole move back to a stop still sitting at entry. Trailing behind
        # each newly confirmed H4 swing keeps the trade alive for the trend
        # it was opened for while making sure a completed leg is banked.
        # The ratchet floor rises with the move (2R -> +0.5R locked,
        # 3R -> +1.5R, 5R -> +3.0R) and is noise-band checked like every
        # other stop this engine sets.
        elif r_multiple >= 2.0:
            if r_multiple >= 5.0:
                _lock_floor = 3.0
            elif r_multiple >= 3.0:
                _lock_floor = 1.5
            else:
                _lock_floor = 0.5
            _tr = None
            if _df_mgmt is not None:
                _tr = st.structural_trail(
                    _df_mgmt, direction, entry, _initial_sl, current_price,
                    _current_sl, _atr_mgmt, _spread_mgmt,
                    min_lock_r=_lock_floor, digits=_digits)
            if _tr and modify_position_sl(pos, _tr['sl']):
                pos_info['stop_loss'] = _tr['sl']
                _record_management(pos_info, 'structural_trail', _tr['reason'],
                                   trigger_r=round(r_multiple, 2), new_sl=_tr['sl'],
                                   swing=_tr.get('swing'))
                logger.info(
                    f"[TRAIL] {symbol_name} ticket {ticket}: SL -> {_tr['sl']:.{_digits}f} "
                    f"at {r_multiple:.2f}R -- {_tr['reason']}"
                )

        open_time = state.position_open_times.get(ticket)
        if open_time:
            duration_days = (datetime.now(timezone.utc) - open_time).total_seconds() / 86400
            if duration_days >= config.MAX_POSITION_DURATION_DAYS:
                logger.info(f"[TIME] Auto-closing {pos.symbol} after {duration_days:.1f} days (max duration)")
                close_position(pos)


def recover_existing_positions() -> None:
    try:
        positions = mt5.positions_get()
        if not positions:
            logger.info("[RECOVERY] No existing positions found")
            return
        recovered = 0
        for pos in positions:
            if pos.magic != MAGIC_NUMBER:
                continue
            direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
            state.open_positions[pos.ticket] = {
                'symbol': pos.symbol, 'direction': direction, 'entry_price': pos.price_open,
                'stop_loss': pos.sl, 'take_profit': pos.tp, 'lot_size': pos.volume,
                'reason': 'RECOVERED',
            }
            state.position_open_times[pos.ticket] = datetime.now(timezone.utc)
            recovered += 1
        logger.info(f"[RECOVERY] Recovered {recovered} position(s) owned by this strategy")
    except Exception as e:
        logger.error(f"[RECOVERY ERROR] {e}")


def sync_closed_trades() -> None:
    """Catch positions that closed (SL/TP hit) since the last check --
    MT5 doesn't push a notification, so tickets we were tracking that are
    no longer in positions_get() are treated as closed and reconciled
    against the deal history."""
    if not state.open_positions:
        return
    live_tickets = {p.ticket for p in (mt5.positions_get() or []) if p.magic == MAGIC_NUMBER}
    closed_tickets = [t for t in list(state.open_positions.keys()) if t not in live_tickets]
    for ticket in closed_tickets:
        try:
            deals = mt5.history_deals_get(position=ticket)
            profit = sum(d.profit for d in deals) if deals else 0.0
            close_price = deals[-1].price if deals else 0.0
            logger.info(f"[SYNC] Ticket {ticket} closed externally (SL/TP) | P&L: ${profit:.2f}")
            _pi = state.open_positions.get(ticket)
            if _pi:
                _attribute_and_log_exit(ticket, _pi, close_price, profit)
            db_manager.update_trade_close(ticket, close_price, profit)
            state.daily_pnl += profit
        except Exception as e:
            logger.error(f"[SYNC ERROR] ticket {ticket}: {e}")
        finally:
            state.open_positions.pop(ticket, None)
            state.position_open_times.pop(ticket, None)
            state.be_moved.discard(ticket)


def initialize_mt5() -> bool:
    try:
        mt5_kwargs = {'login': config.MT5_LOGIN, 'password': config.MT5_PASSWORD, 'server': config.MT5_SERVER}
        if MT5_TERMINAL_PATH:
            mt5_kwargs['path'] = MT5_TERMINAL_PATH
        if not mt5.initialize(**mt5_kwargs):
            logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            return False
        account_info = mt5.account_info()
        if not account_info:
            return False
        logger.info(f"[OK] MT5 Connected | Account: {account_info.login} | Balance: ${account_info.balance:.2f}")
        for s in config.SYMBOLS:
            if not mt5.symbol_select(s, True):
                logger.error(f"Failed to select {s} in Market Watch")
        return True
    except Exception as e:
        logger.error(f"MT5 init error: {e}")
        return False


# =============================================================================
# MAIN LOOP
# =============================================================================

def swing_trading_session() -> None:
    logger.info("=" * 80)
    logger.info("STRUCTURAL SWING PRO -- SESSION STARTED")
    logger.info(f"   MT5 Account: {config.MT5_LOGIN}")
    logger.info(f"   Structure: D1 | Entries: H4 | Symbols: {', '.join(config.SYMBOLS)}")
    logger.info(f"   Risk/trade: {config.BASE_RISK_PERCENT}% | Max daily trades: {config.MAX_DAILY_TRADES}")
    logger.info("=" * 80)

    recover_existing_positions()

    try:
        account_info = mt5.account_info()
        _today_key = risk_limits.utc_day_key()
        state.daily_start_equity = (risk_limits.load_or_init_daily_baseline(
            DATA_DIR, account_info.equity, _today_key) if account_info else 0.0)
        state.last_reset_day = _today_key
    except Exception as e:
        logger.error(f"Failed to get initial account info: {e}")
        state.daily_start_equity = 0.0

    # HEARTBEAT FIRST -- `is_running=true` must never exist without a fresh
    # bot_heartbeats row behind it. The loop's heartbeat runs on an interval
    # that starts at loop entry, so claiming "running" before the first beat
    # leaves a window where the row says running while the heartbeat looks
    # stale -- exactly the "crashed" verdict BotStatusSync and
    # monitor-bot-health are built to detect. That window killed a live bot
    # nine seconds after it confirmed. See hybrid_trading_bot_multiuser.py.
    db_manager.send_heartbeat()

    # --- CONFIRM STARTED ---
    # Claim user_strategies (is_running=true, bot_pid) now that MT5 is up.
    # start-trading-bot writes is_running=false before launch, meaning "not
    # confirmed yet"; nothing ever confirmed, so without this the bot's first
    # in-loop check_remote_stop read that pre-launch false as a dashboard Stop
    # and shut the process down seconds after boot. See bot_control.py.
    if bot_control.confirm_bot_started(supabase, USER_ID, STRATEGY_ID, os.getpid()):
        logger.info(f"[STARTED] Confirmed running in user_strategies (pid {os.getpid()})")
    else:
        logger.warning("[STARTED] Could not confirm start in user_strategies "
                       "(stopped during launch, or write failed)")

    last_heartbeat = 0.0
    last_scan = 0.0
    last_manage = 0.0

    while True:
        try:
            now = time.time()

            account_info = mt5.account_info()
            if not account_info:
                logger.error("Lost MT5 connection")
                time.sleep(30)
                if not initialize_mt5():
                    logger.error("Failed to reconnect")
                    time.sleep(60)
                continue

            if now - last_heartbeat >= config.HEARTBEAT_INTERVAL:
                last_heartbeat = now
                db_manager.send_heartbeat()

            current_day = risk_limits.utc_day_key()
            if state.last_reset_day is None:
                state.last_reset_day = current_day
            if current_day != state.last_reset_day:
                logger.info(f"[NEW DAY] Resetting daily P&L (was ${state.daily_pnl:.2f}) and trade count")
                state.daily_pnl = 0.0
                state.daily_trades = 0
                state.daily_start_equity = risk_limits.load_or_init_daily_baseline(
                    DATA_DIR, account_info.equity, current_day)
                state.last_reset_day = current_day
            elif state.daily_start_equity <= 0:
                state.daily_start_equity = risk_limits.load_or_init_daily_baseline(
                    DATA_DIR, account_info.equity, current_day)

            # --- WEEKLY BASELINE (restart-safe, rolls on a real ISO week) ---
            # The weekly loss limit the public site advertises had no
            # implementation anywhere before this. See risk_limits.py.
            if account_info:
                _wk = risk_limits.iso_week_key()
                if getattr(state, 'weekly_key', None) != _wk:
                    state.weekly_start_equity, state.weekly_key = risk_limits.load_or_init_weekly_baseline(
                        DATA_DIR, account_info.equity, _wk)
                    logger.info(f"[BASELINE] Weekly start equity ${state.weekly_start_equity:,.2f} for {_wk}")

            if check_emergency_conditions(account_info):
                logger.critical("[ALERT] EMERGENCY STOP TRIGGERED -- shutting down")
                send_telegram_message("\U0001F6A8 Structural Swing Pro: EMERGENCY STOP triggered.")
                break

            # Was: a poll of bot_commands.kill_switch -- a column that has
            # never existed, so the `except: pass` silently swallowed a
            # failure every single cycle and this "kill switch" could never
            # fire. See bot_control.py's module docstring for the full
            # story and why user_strategies.is_running is the right
            # authority (it is what the dashboard actually writes).
            _stop = bot_control.check_remote_stop(supabase, USER_ID, STRATEGY_ID)
            if _stop is not None and _stop.reason == 'false_crash_report':
                # NOT a stop -- see hybrid_trading_bot_multiuser.py. A health
                # sweep declared this process dead while it is alive and
                # reading the row. Put the row back and keep trading.
                _now_fc = time.time()
                if _now_fc - getattr(state, '_last_reassert', 0) > 60:
                    state._last_reassert = _now_fc
                    logger.warning(f"[FALSE CRASH] {_stop.detail}")
                    bot_control.reassert_running(supabase, USER_ID, STRATEGY_ID)
                _stop = None

            if _stop is not None:
                logger.critical(f"[REMOTE STOP] {_stop.reason}: {_stop.detail} -- stopping.")
                send_telegram_message(f"\U0001F6D1 Structural Swing Pro stopped: {_stop.detail}")
                break

            # --- EQUITY SANITY GATE (see hybrid_trading_bot_multiuser.py) ---
            # mt5.account_info() succeeds before the terminal finishes
            # authenticating and reports equity 0.00 in that window. Every risk
            # figure divides by equity, so trading on a zero is either a crash
            # or a meaningless lot size. Placed after the heartbeat and remote
            # stop above, so a waiting bot still reports in and can still be
            # stopped from the dashboard.
            if account_info.equity <= 0:
                _waits = getattr(state, '_zero_equity_waits', 0) + 1
                state._zero_equity_waits = _waits
                if _waits <= 4 or _waits % 20 == 0:
                    logger.warning(
                        f"[EQUITY] MT5 reports equity ${account_info.equity:.2f} -- not trading. "
                        f"Waiting for the terminal to finish logging in (check {_waits}). If this "
                        f"persists the account is unfunded or the MT5 login failed."
                    )
                time.sleep(15)
                continue

            if getattr(state, '_zero_equity_waits', 0):
                logger.info(f"[EQUITY] MT5 now reports equity ${account_info.equity:,.2f} "
                            f"after {state._zero_equity_waits} check(s) -- resuming.")
                state._zero_equity_waits = 0

            if now - last_manage >= config.POSITION_MANAGE_INTERVAL_SECONDS:
                last_manage = now
                sync_closed_trades()
                manage_open_positions()

            if now - last_scan >= config.SCAN_INTERVAL_SECONDS:
                last_scan = now
                for symbol in config.SYMBOLS:
                    cooldown_until = state.symbol_cooldowns.get(symbol)
                    if cooldown_until and datetime.now(timezone.utc) < cooldown_until:
                        continue
                    signal = scan_for_signal(symbol)
                    if signal:
                        logger.info(f"[SIGNAL] {symbol} {signal['direction']} -- {signal['reason']}")
                        place_swing_trade(signal, account_info.equity)

        except KeyboardInterrupt:
            logger.info("[STOP] Bot stopped by user")
            break
        except Exception as e:
            import traceback
            logger.error(f"[CRASH] {type(e).__name__}: {e}")
            logger.error(traceback.format_exc()[-500:])
            time.sleep(10)

        time.sleep(5)

    # EVERY exit path lands here. Marking the row stopped guarantees the
    # dashboard cannot show a running bot for a process that has ended --
    # the failure seen on the scalper on 2026-08-18, where the circuit
    # breaker fired and the UI still read "1 Running" hours later.
    try:
        if bot_control.mark_bot_stopped(supabase, USER_ID, STRATEGY_ID, 'shutdown'):
            logger.info("[STOPPED] user_strategies marked stopped")
        else:
            logger.warning("[STOPPED] could not mark user_strategies stopped")
    except Exception as _e:
        logger.warning(f"[STOPPED] mark_bot_stopped failed: {_e}")
    mt5.shutdown()
    logger.info("[FINISH] Bot shutdown complete")


def main():
    logger.info("[START] Initializing Structural Swing Pro...")
    if not initialize_mt5():
        logger.error("[ERROR] Failed to initialize MT5")
        sys.exit(1)
    try:
        swing_trading_session()
    except KeyboardInterrupt:
        logger.info("[STOP] Bot stopped by user")
    except Exception as e:
        logger.critical(f"[CRASH] Fatal error: {e}", exc_info=True)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
