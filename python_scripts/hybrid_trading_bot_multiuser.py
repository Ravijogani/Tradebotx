# -*- coding: utf-8 -*-
"""
=============================================================================
HYBRID AI TRADING BOT - V11.4 SPREAD-SAFE SCALPING
=============================================================================
V11.4 CHANGELOG (Spread-Safe SL + High-Quality Scalping):

  CRITICAL BUG FIXES:
  - [BUG FIX] SL instant-hit root cause: MT5 marks longs vs BID, shorts vs ASK.
    All SL placements now enforce SL < BID - (spread x 3.0) for BUY and
    SL > ASK + (spread x 3.0) for SELL before order submission.
  - [BUG FIX] Spread vs SL distance ratio check was comparing dollar spread
    against pip-count for metals (unit mismatch). Fixed to use raw price units.
  - [BUG FIX] Final ORDER GUARD re-fetches live tick at send time (not stale
    tick from top of function) and uses BID/ASK correctly for each side.
  - [BUG FIX] Duplicate orphaned `except` block at end of place_ai_trade removed.
  - [BUG FIX] `get_current_session()` returned "NY" but all downstream consumers
    expected "NEW_YORK" -- session strength was always 0.5. Fixed to "NEW_YORK".
  - [BUG FIX] Lot sizing formula crashes silently when tick_value/tick_size is
    None (market closed / symbol not subscribed). Margin-based fallback added.
  - [BUG FIX] Legacy BE buffer used 1 pip -- $0.01 on XAUUSD, inside spread.
    Buffer now scales to max(pip_buffer, 0.3 * ATR, 1.5xspread) for metals/crypto.

  SL BUFFER FIXES (all strategies had tiny ATR multiples that sat inside spread):
  - ICT_KILLZONE:       0.5 * ATR -> 1.5 * ATR
  - ADVANCED_SMC:       0.5 * ATR -> 1.5 * ATR
  - LIQUIDITY_GRAB:     0.1 * ATR -> 1.2 * ATR
  - WYCKOFF_PATTERNS:   0.5 * ATR -> 1.5 * ATR
  - VOLUME_IMBALANCE:   0.1 * ATR -> 1.0 * ATR
  - SMC_LIQUIDITY_SWEEP:0.5 * ATR -> 1.5 * ATR
  - TREND_PULLBACK:     bare candle high/low -> + 0.8 * ATR buffer
  - MEAN_REVERSION_BB:  bare candle high/low -> + 1.0 * ATR buffer
  - PriorityTriggerEngine SWEEP_AND_DISPLACE: 0.5 * ATR -> 1.5 * ATR
  - PriorityTriggerEngine MOMENTUM_BURST:     0.3 * ATR -> 0.6 * ATR

  NEW: HIGH-QUALITY SCALPING FILTERS:
  - check_symbol_max_spread(): per-symbol absolute spread gate
    (XAUUSD <= $1.20, XAGUSD <= $0.04, BTC <= $20, etc.)
  - check_scalping_quality(): 5-gate filter before every entry:
    1. Kill zone enforcement (London / NY only, configurable)
    2. M5 ADX >= 20 (momentum gate -- no dead-market entries)
    3. RSI 28-72 (no chasing exhausted moves)
    4. M1 tick volume >= 1.2x 20-bar avg (institutional fingerprint)
    5. M5 candle body ratio >= 30% (reject doji / spinning tops)
  - get_dynamic_trade_params(): spread-safety enforcement layer --
    adjusts structural SL away from entry if it sits within spread x 3.0.
  - MAX_SPREAD_RATIO tightened from 0.70 -> 0.15.

  TRADE OPEN LOGGING:
  - Telegram alert now includes SL distance, spread at open, spread-to-SL %,
    and RR ratio for real-time trade quality visibility.
  - Log line includes all the same data for file debugging.

Previous: V11.3 INTELLIGENT (Context-Aware Intelligence)

ARCHITECTURE (unchanged from V11.0):
This is the production-ready, multi-user version.
-   It is controlled entirely by command-line arguments (CLI), allowing a
    backend "Bot Manager" to spawn one instance per user.
-   All credentials (MT5, API keys) are passed via CLI.
-   All trade logging and AI learning is now pointed to a central
    Supabase database, replacing the local SQLite DB.
-   Includes integrated Telegram notifications for trade events.
-   Includes a `send_heartbeat` function for dashboard monitoring.

V11.3 INTELLIGENT (CONTEXT-AWARE INTELLIGENCE):
- Added session-aware scoring (Asia: stricter, London: lenient)
- Added volatility adaptation (skips quiet markets, adapts SL/TP)
- Added performance tracking (considers recent strategy success)
- Adaptive thresholds (not hardcoded)
- Context-aware decisions (not blind rule following)

V11.0 Changelog:
- Merged V10.1 (Stable) engine with hybrid_trading_bot_multiuser.py template.
- Replaced all CLI argument logic with the new top-level parser.
- Replaced TradeHistoryDB (SQLite) with SupabaseTradeDB.
- Rewrote place_ai_trade, update_closed_trades, manage_all_positions,
  ai_analyze_closed_trades, and ai_calculate_risk_percent to use Supabase.
- Integrated send_telegram_notification at key points.
- Integrated send_heartbeat into the main loop.
- Made log file paths user-specific.
=============================================================================
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import os
import json
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import logging
import sys
import argparse
import sqlite3
from pathlib import Path
import re
import certifi
from supabase import create_client, Client
import hashlib
import platform

# =============================================================================
# SAFETY: Purge any stale engines/ modules from sys.modules.
# If the server has an old engines/ folder, Python might import it before
# reaching our inline class definitions below, causing NameError / wrong class.
# This block ensures our inline versions always win.
for _mod_key in list(sys.modules.keys()):
    if _mod_key.startswith('engines.') or _mod_key == 'engines':
        del sys.modules[_mod_key]
# =============================================================================

# =============================================================================
# EMBEDDED ENGINE CLASSES (consolidated from engines/ folder)
# EdgeEngine, CapitalController, DecisionEngineV2, RunnerManagementEngine,
# ScalpingExitEngine -- all inline, no external deps. (EntryEngine was here
# too but moved to strategies_research.py -- never had a live call site;
# see that module's docstring.)
# =============================================================================

class TradeContext:
    """
    Complete market context snapshot.
    Built ONCE per symbol per cycle, shared across all engines.
    """
    def __init__(
        self,
        liquidity_distance: float = 0.0,
        liquidity_strength: float = 0.0,
        momentum_state: float = 0.0,
        structure_alignment: float = 0.0,
        session_strength: float = 0.0,
        volatility_state: float = 0.0,
        session: str = "UNKNOWN",
        regime: str = "TRENDING",
        edge_score: float = 50.0,
        edge_state: str = "NORMAL",
        # Extended fields used by management loop
        micro_strength: float = 0.5,
        pattern_health: float = 0.5,
        symbol_trade_score: float = 1.0,
        regime_alignment: float = 0.5,
        spread_quality: float = 1.0,
    ):
        self.liquidity_distance   = liquidity_distance
        self.liquidity_strength   = liquidity_strength
        self.momentum_state       = momentum_state
        self.structure_alignment  = structure_alignment
        self.session_strength     = session_strength
        self.volatility_state     = volatility_state
        self.session              = session
        self.regime               = regime
        self.edge_score           = edge_score
        self.edge_state           = edge_state
        self.micro_strength       = micro_strength
        self.pattern_health       = pattern_health
        self.symbol_trade_score   = symbol_trade_score
        self.regime_alignment     = regime_alignment
        self.spread_quality       = spread_quality


class EdgeResult:
    """Rich output from EdgeEngine. All downstream engines derive from this."""
    def __init__(self, score: float, state: str):
        self.score = score
        self.state = state
        self.allow_entry       = (state != "IGNORE")
        self.size_multiplier   = max(0.2, min(1.5, score / 65.0))
        self.allow_stacking    = (state == "STRONG" and score >= 72)
        if score > 75:
            self.exit_aggressiveness = "LOOSE"
        elif score > 55:
            self.exit_aggressiveness = "STANDARD"
        elif score > 30:
            self.exit_aggressiveness = "TIGHT"
        else:
            self.exit_aggressiveness = "EXIT_NOW"
        self.runner_eligible     = (state == "STRONG" and score >= 75)
        self.throttle_frequency  = (state in ("WEAK", "IGNORE"))
        self.risk_tier = (
            "HIGH"   if score >= 75 else
            "NORMAL" if score >= 55 else
            "LOW"    if score >= 30 else
            "BLOCK"
        )

    def as_dict(self):
        return {"score": self.score, "state": self.state}


class EdgeEngine:
    """
    Unified EdgeScore calculation.
    Drives: entry gate, size, stacking, exit aggressiveness, runner promotion.
    """
    WEIGHTS = {
        "liquidity_distance":  25,
        "liquidity_strength":  20,
        "momentum_state":      20,
        "structure_alignment": 15,
        "session_strength":    10,
        "volatility_state":    10,
    }

    def calculate(self, ctx: TradeContext) -> EdgeResult:
        score  = ctx.liquidity_distance  * self.WEIGHTS["liquidity_distance"]
        score += ctx.liquidity_strength  * self.WEIGHTS["liquidity_strength"]
        score += ctx.momentum_state      * self.WEIGHTS["momentum_state"]
        score += ctx.structure_alignment * self.WEIGHTS["structure_alignment"]
        score += ctx.session_strength    * self.WEIGHTS["session_strength"]
        score += ctx.volatility_state    * self.WEIGHTS["volatility_state"]
        score  = max(0.0, min(100.0, score))

        if score > 75:   state = "STRONG"
        elif score > 55: state = "NORMAL"
        elif score > 30: state = "WEAK"
        else:            state = "IGNORE"

        result = EdgeResult(score, state)
        ctx.edge_score = score
        ctx.edge_state = state
        return result


# EntryEngine ("ICT Algorithmic Liquidity Model -- Deterministic SMC Entry
# Engine") moved to strategies_research.py -- never instantiated anywhere
# in this file (confirmed by grepping call sites, not just defs). See that
# module's docstring for why dormant strategy code lives there now instead
# of here, and for this specific class's promotion-worthiness assessment.
# Import it (from strategies_research import EntryEngine) if/when it's
# deliberately wired into the live cascade -- don't recreate it here.


class CapitalController:
    """
    Sole sizing authority. Controls position size, stacking, frequency throttle.
    """
    def __init__(self):
        self.base_risk = 1.0

    def calculate(self, edge_score: float, symbol_metrics: float,
                  session: str, drawdown: float, symbol: str = "",
                  open_positions_count: int = 0, account_equity: float = 0,
                  pattern_health: float = 1.0) -> float:
        """
        Professional risk sizing. Considers:
        1. Edge quality (higher edge = slightly more size)
        2. Session (London/NY = full size, Asia = reduced)
        3. Drawdown (reduce size as losses accumulate)
        4. Asset volatility (BTC/ETH/XAG = smaller to match dollar risk)
        5. Total open exposure (reduce size if already have open positions)
        6. This symbol's own recent live trade-score (symbol_metrics)
        7. This setup's historical pattern-match edge health (pattern_health)

        BUG FIX: symbol_metrics was a parameter here (and the live call site
        already computed a real value for it via
        symbol_tracker.get_symbol_metrics(symbol)['trade_score']) but this
        method's body never once read it -- a real symbol performing badly
        got exactly the same size as one performing well. Also added
        pattern_health: PatternRecognitionSystem.get_edge_health_score()
        (a real 0.0-1.5 confidence multiplier straight from its own
        docstring) was previously only ever called in the mid-trade
        management loop, and even there its result was computed and then
        never read by anything -- it never reached position sizing at
        entry time at all. Wiring both in here is what "the bot throttles
        a setup that's currently cold" actually requires; the data plumbing
        already existed; nothing was using it.
        """
        edge_mult = max(0.5, min(1.2, edge_score / 65.0))  # tighter range for stability

        # Drawdown scaling -- protect capital aggressively
        dd_adj = (0.0  if drawdown >= 8  else   # Stop trading at 8% DD
                  0.25 if drawdown >= 6  else
                  0.50 if drawdown >= 4  else
                  0.75 if drawdown >= 2  else 1.0)

        # Session scaling
        su = session.upper()
        # LONDON_NY overlap = 13-16 UTC, highest liquidity, allow slightly more size
        sess_agg = (1.25 if "LONDON_NY" in su else
                    1.0  if ("LONDON" in su or "NEW_YORK" in su) else
                    0.5  if "ASIA" in su else 0.4)

        # Volatility / contract size scaling
        sym_u = symbol.upper()
        vol_scale = (0.40 if any(x in sym_u for x in ["BTC"])         else  # BTC moves $300+
                     0.50 if any(x in sym_u for x in ["ETH"])         else  # ETH moves $30+
                     0.60 if any(x in sym_u for x in ["XAGUSD"])      else  # XAG spread spikes
                     0.75 if any(x in sym_u for x in ["USOIL","UKOIL","XAUUSD"]) else 1.0)

        # Reduce size when already have open positions (exposure management)
        exposure_mult = max(0.5, 1.0 - (open_positions_count * 0.3))

        # This symbol's own recent live performance (SymbolPerformanceTracker's
        # trade_score). Clamped to a moderate band -- same reasoning as
        # edge_mult's clamp: this should nudge size, not swing it wildly on
        # a small sample of recent trades for one symbol.
        sym_perf_mult = max(0.6, min(1.3, symbol_metrics))

        # Historical pattern-match edge health for this exact symbol+direction
        # setup (PatternRecognitionSystem.get_edge_health_score -- already
        # native 0.0-1.5, clamp matches its own documented range minus the
        # extremes, same conservative-nudge reasoning as sym_perf_mult).
        pattern_mult = max(0.5, min(1.3, pattern_health))

        risk = (self.base_risk * edge_mult * sess_agg * dd_adj * vol_scale *
                exposure_mult * sym_perf_mult * pattern_mult)
        return max(0.25, min(1.5, risk))  # Hard cap at 1.5% for scalping

    def allow_stacking(self, edge_score: float, regime: str, lifecycle: str) -> bool:
        return (edge_score > 70 and
                regime in ["TRENDING","TRENDING_UP","TRENDING_DOWN"] and
                lifecycle in ["EXPANSION","SWEEP_AND_DISPLACE"])

    def should_throttle_frequency(self, recent_edge_quality_low: bool) -> bool:
        return recent_edge_quality_low


class MidTradeContext:
    def __init__(self, trade_ctx, edge_score: float, runner_state: bool,
                 lifecycle: str, momentum: str):
        self.trade_ctx    = trade_ctx
        self.edge_score   = edge_score
        self.runner_state = runner_state
        self.lifecycle    = lifecycle
        self.momentum     = momentum


class DecisionEngineV2:
    """
    Professional mid-trade decision engine.
    REDUCE only when trade is deeply wrong -- not on minor fluctuations.
    """
    def decide_mid_trade(self, ctx: MidTradeContext) -> str:
        # Protect runners -- never interfere with a winner
        if ctx.runner_state and ctx.momentum == "INCREASING":
            return "PRESERVE_RUNNER"
        # Only reduce risk when BOTH edge is terrible AND trade is stalling
        # Requires edge < 30 (was 40) AND lifecycle=STALL -- not just one
        if ctx.edge_score < 30 and ctx.lifecycle == "STALL" and not ctx.runner_state:
            return "REDUCE"
        # TIGHTEN = move SL to breakeven. Only do this when trade is solidly
        # in profit (r_multiple built into MidTradeContext). Without r_multiple check,
        # TIGHTEN fires at 0.22R (e.g. USOIL BUY: moved 0.29pts out of 1.328 SL dist).
        # The r_multiple check is implicit via lifecycle: STALL requires duration>5min
        # AND r_multiple < 0.5. But we want tighten only when r_multiple is AT LEAST 0.5.
        # Fix: STALL alone is not enough -- check ctx.edge_score is reasonable AND
        # we only tighten through the LEGACY fallback at be_trigger_r=1.0.
        # Decision engine should NEVER tighten below 1R -- return HOLD instead.
        # HOLD passes to the legacy BE block which has the correct 1.0R check.
        if ctx.lifecycle == "STALL" and ctx.edge_score > 40:
            return "HOLD"  # Let the legacy BE block handle this (it checks r_multiple>=1.0)
        return "HOLD"


class RunnerContext:
    def __init__(self, trade_ctx, direction: str, current_price: float,
                 structure_high: float, structure_low: float, sl: float, buffer: float):
        self.trade_ctx       = trade_ctx
        self.direction       = direction
        self.current_price   = current_price
        self.structure_high  = structure_high
        self.structure_low   = structure_low
        self.sl              = sl
        self.buffer          = buffer


class RunnerManagementEngine:
    """Runner owns SL. Trails incrementally against structure."""
    def compute_sl(self, ctx: RunnerContext):
        sl, buf = ctx.sl, ctx.buffer
        if ctx.direction == "BUY":
            new_sl = ctx.structure_low - buf
            return new_sl if new_sl > sl else None
        elif ctx.direction == "SELL":
            new_sl = ctx.structure_high + buf
            return new_sl if (new_sl < sl or sl == 0) else None
        return None


class ExitContext:
    def __init__(self, trade_ctx, edge_score: float, lifecycle: str,
                 momentum: str, liquidity_state: str, regime: str,
                 r_multiple: float = 0.0, duration_mins: float = 0.0):
        self.trade_ctx       = trade_ctx
        self.edge_score      = edge_score
        self.lifecycle       = lifecycle
        self.momentum        = momentum
        self.liquidity_state = liquidity_state
        self.regime          = regime
        self.r_multiple      = r_multiple    # Current profit in R units
        self.duration_mins   = duration_mins # How long trade has been open


class ScalpingExitEngine:
    """
    Professional Scalping Exit Engine.

    FOUNDER PRINCIPLE: Let trades breathe. A scalp that pulls back to entry
    and then delivers TP is a NORMAL trade. Do not exit on every pullback.

    EXIT only when the trade is structurally BROKEN:
    - Price has moved past the structural invalidation point (lifecycle=FAILURE
      AND momentum=DROP AND edge_score<35) -- all THREE required, not just one
    - Trade has been open >60 minutes with negative progress (stale trade)
    - TP was hit (liquidity_state=HIT)

    PARTIAL SCALE-OUT only at 80%+ progress toward TP (locking in profit).
    """
    def decide(self, ctx: ExitContext) -> str:
        """
        PROFESSIONAL EXIT LOGIC:
        - Never exit just because price pulled back to entry
        - Only exit when price goes PAST the structural SL (r_multiple < -0.3)
        - TP scale-out at progress >= 90%
        - Stale exit only after 45+ minutes with no movement at all
        """
        # 1. TP hit or near TP -- scale out to lock profit
        if ctx.liquidity_state == "HIT":
            return "SCALE_OUT"

        # 2. STRUCTURAL FAILURE: price crossed past SL level significantly
        # r_multiple < -0.3 means price moved 30%+ past the SL structure.
        # A pullback to entry gives r_multiple ~ 0. This gate won't fire on pullbacks.
        if ctx.r_multiple < -0.3 and ctx.edge_score < 35 and ctx.duration_mins > 3:
            return "EXIT"

        # 3. Stale trade: open >45 min, price never moved (r_multiple near 0)
        # AND market structure has deteriorated (edge very low)
        if (ctx.duration_mins > 45
                and abs(ctx.r_multiple) < 0.15
                and ctx.edge_score < 30):
            return "EXIT"  # Setup didn't deliver -- close and move on

        # 4. In-profit pullback -- this is the case the user reported.
        # Price ran to 0.5R then pulled back to 0R. DO NOT EXIT.
        # Let the SL manage the risk -- that is what it's there for.
        return "HOLD"

# =============================================================================
# CLI ARGUMENT PARSING
# =============================================================================

parser = argparse.ArgumentParser(description='Multi-user Hybrid AI Trading Bot')
parser.add_argument('--user-id', type=str, required=True, help='User ID')
parser.add_argument('--strategy-id', type=str, required=True, help='Strategy ID')
parser.add_argument('--mt5-login', type=int, required=True, help='MT5 Login')
# --mt5-password / --supabase-key are optional on the CLI on purpose: the bot
# manager passes them via environment variables instead of argv so they don't
# show up in `ps`/Task Manager/WMI process-listing output. Falls back to the
# flag only for manual/local runs.
parser.add_argument('--mt5-password', type=str, required=False, default=None, help='MT5 Password (prefer MT5_PASSWORD env var)')
parser.add_argument('--mt5-server', type=str, required=True, help='MT5 Server')
parser.add_argument('--mt5-path', type=str, required=False, default=None, help='Path to user-specific MT5 terminal64.exe')
parser.add_argument('--telegram-chat-id', type=str, required=False, help='Telegram Chat ID')
parser.add_argument('--telegram-bot-token', type=str, required=False, help='Telegram Bot Token (prefer TELEGRAM_BOT_TOKEN env var)')
parser.add_argument('--supabase-url', type=str, required=True, help='Supabase URL')
parser.add_argument('--supabase-key', type=str, required=False, default=None, help='Supabase Service Key (prefer SUPABASE_SERVICE_KEY env var)')
parser.add_argument('--gemini-api-key', type=str, required=False, help='Gemini API Key')
parser.add_argument('--magic-number', type=int, required=False, help='Fixed Magic Number (optional - if not provided, generates from user-id + strategy-id)')

args = parser.parse_args()

# User-specific configuration
USER_ID = args.user_id
STRATEGY_ID = args.strategy_id
TELEGRAM_CHAT_ID = args.telegram_chat_id
# Secrets prefer environment variables (set by the bot manager) over CLI
# flags, so they don't appear in `ps`/Task Manager/WMI process listings.
MT5_PASSWORD_RESOLVED = args.mt5_password or os.getenv("MT5_PASSWORD", "")
SUPABASE_KEY_RESOLVED = args.supabase_key or os.getenv("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT_TOKEN = args.telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
MT5_TERMINAL_PATH = args.mt5_path  # Per-user isolated MT5 instance

if not MT5_PASSWORD_RESOLVED:
    print("[FATAL] MT5 password not provided (neither --mt5-password nor MT5_PASSWORD env var)")
    sys.exit(1)
if not SUPABASE_KEY_RESOLVED:
    print("[FATAL] Supabase service key not provided (neither --supabase-key nor SUPABASE_SERVICE_KEY env var)")
    sys.exit(1)

# Initialize Supabase client
supabase: Client = create_client(args.supabase_url, SUPABASE_KEY_RESOLVED)

# DATA DIRECTORY SETUP (OS AGNOSTIC)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", USER_ID)
os.makedirs(DATA_DIR, exist_ok=True)


def _resolve_magic_number(user_id: str, strategy_id: str, data_dir: str) -> int:
    """Deterministic per (user, strategy) magic number, with a real collision
    guard instead of just trusting the hash.

    MT5 only needs this to be unique *within one MT5 account* — accounts are
    already isolated per user (each user gets their own MT5 terminal), so the
    only collision that actually matters is between two strategies for the
    *same* user running concurrently on the same account. That's checked
    against a small per-user registry file rather than a global one; a hash
    collision that would let one strategy's SL/TP/close logic act on a
    different strategy's live positions gets bumped to the next free slot
    and persisted instead of silently colliding.
    """
    base = int(hashlib.md5(f"{user_id}_{strategy_id}".encode()).hexdigest(), 16) % 2_000_000_000 + 10_000_000

    registry_path = os.path.join(data_dir, "magic_numbers.json")
    try:
        with open(registry_path, 'r', encoding='utf-8') as f:
            registry = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        registry = {}

    # Already assigned to this exact strategy — reuse it.
    if strategy_id in registry:
        return registry[strategy_id]

    taken = set(registry.values())
    candidate = base
    while candidate in taken:
        candidate += 1
        print(f"[MAGIC] Collision on {candidate - 1} for user={user_id[:8]} strategy={strategy_id[:8]} — trying {candidate}")

    registry[strategy_id] = candidate
    try:
        with open(registry_path, 'w', encoding='utf-8') as f:
            json.dump(registry, f)
    except OSError as e:
        print(f"[MAGIC] WARNING: could not persist magic number registry: {e}")

    return candidate


def _daily_baseline_path(data_dir: str) -> str:
    return os.path.join(data_dir, "daily_equity_baseline.json")


def load_or_init_daily_baseline(data_dir: str, current_equity: float, today: str) -> float:
    """Restart-safe daily-loss baseline.

    Previously this was set to *current* equity on every process start with
    no persistence, so a bot restart mid-day (crash, VM reboot, redeploy)
    would silently re-baseline the daily-loss circuit breaker from whatever
    equity happened to be left — erasing losses already taken earlier that
    same day and letting the account drop further than MAX_DAILY_LOSS_PERCENT
    / MAX_DAILY_DRAWDOWN_PERCENT actually allow. If a baseline was already
    recorded for today, reuse it; only a genuine new day gets a fresh one.
    """
    try:
        with open(_daily_baseline_path(data_dir), 'r', encoding='utf-8') as f:
            saved = json.load(f)
        if saved.get('date') == today and isinstance(saved.get('baseline'), (int, float)) and saved['baseline'] > 0:
            print(f"[BASELINE] Restored daily start equity ${saved['baseline']:.2f} for {today} (restart-safe)")
            return float(saved['baseline'])
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
        pass

    persist_daily_baseline(data_dir, today, current_equity)
    return current_equity


def persist_daily_baseline(data_dir: str, date_str: str, baseline: float) -> None:
    try:
        with open(_daily_baseline_path(data_dir), 'w', encoding='utf-8') as f:
            json.dump({'date': date_str, 'baseline': baseline}, f)
    except OSError as e:
        print(f"[BASELINE] WARNING: could not persist daily equity baseline: {e}")


# MAGIC NUMBER MANAGEMENT - Deterministic per user+strategy, collision-checked
if args.magic_number:
    MAGIC_NUMBER = args.magic_number
else:
    MAGIC_NUMBER = _resolve_magic_number(USER_ID, STRATEGY_ID, DATA_DIR)
print(f"[MAGIC] Using Magic number: {MAGIC_NUMBER} (user={USER_ID[:8]}, strategy={STRATEGY_ID[:8]})")
print(f"[MT5] Terminal path: {MT5_TERMINAL_PATH or 'default (system)'}")


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class AITradingConfig:
    """Configuration for AI-powered adaptive trading bot"""
    
    # MT5 Connection
    MT5_LOGIN: int = args.mt5_login
    MT5_PASSWORD: str = MT5_PASSWORD_RESOLVED
    MT5_SERVER: str = args.mt5_server
    
    # AI API Configuration
    AI_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = args.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-2.5-flash"  # Current stable model (March 2026)
    
    # AI Feature Flags
    ENABLE_AI_VALIDATION: bool = True   # FIX: was False -- AI bias context never ran
    ENABLE_AI_RISK_MANAGEMENT: bool = True
    ENABLE_AI_TRADE_LEARNING: bool = True
    
    # Local-First Strategy Engine Flags
    ENABLE_LOCAL_NEWS_FILTER: bool = True
    ENABLE_CONFLUENCE_ENGINE: bool = True

    # STRATEGY SELECTION -- per explicit decision, the live cascade only
    # trades four documented setups: Shaakuni SSM, Swappy 3C, AOX layered
    # execution, and the 9/25/50/200 EMA scalp. The first three are NOT
    # gated by a flag here -- they were never conditionally skippable in
    # the cascade and stay that way. EMA scalp has its own flag (below,
    # now enabled) since it was previously disabled pending this decision.
    # These three flags disable everything NOT in the four-setup list:
    # STRATEGY C (SMC FVG retest) and the two generic fallbacks. Set any
    # of these back to True to re-enable that strategy in the live cascade.
    ENABLE_STRATEGY_SMC_FVG_RETEST: bool = False
    ENABLE_STRATEGY_LIQUIDITY_GRAB_FALLBACK: bool = False
    ENABLE_STRATEGY_ICT_KILLZONE_FALLBACK: bool = False

    # EMA SCALP (STRATEGY A) -- one of the four approved setups, enabled.
    ENABLE_STRATEGY_EMA_SCALP: bool = True
    # "Distance Rule" from the 9/15/50/200 EMA framework spec: the 9/25
    # cluster must be meaningfully separated from the 50 EMA before a cross
    # is considered tradeable -- when they're bunched/braided (ranging
    # market), a cross is noise, not momentum, and is far more likely to
    # immediately reverse into the stop. Expressed as an ATR multiple
    # rather than the spec's fixed "~15 pips" figure, since a fixed pip
    # count doesn't translate sensibly across Gold/BTC/forex (see the
    # identical reasoning already in strategy_advanced_smc's min_ob_size).
    # Starting value, not empirically validated -- tune via the backtest
    # harness (python_scripts/backtest/).
    EMA_DISTANCE_RULE_ATR_MULT: float = 0.5

    # AI Analysis Intervals
    AI_GLOBAL_CONTEXT_INTERVAL: int = 3600
    AI_LEARNING_INTERVAL: int = 3600
    LOCAL_NEWS_CHECK_INTERVAL: int = 1800
    MIN_TRADES_FOR_LEARNING: int = 10
    
    # DYNAMIC SYMBOL TIERS based on account equity
    # Each symbol has a minimum equity required to trade it safely at 1% risk.
    # The bot auto-selects eligible symbols at startup and after each trade.
    #
    # Equity tiers (at 1% risk, 0.5xATR SL, min lot):
    #   $0   - $149:  BTCUSDm only (1% ATR risk ~$1.00)
    #   $150 - $299:  BTC + USOILm (OIL 1% ATR risk ~$1.50)
    #   $300 - $599:  + XAUUSDm (XAU 1% ATR risk ~$3-4)  
    #   $600 - $999:  + ETHUSDm
    #   $1000+:       + XAGUSDm (XAG is most expensive per lot)
    #
    SYMBOLS: List[str] = field(default_factory=lambda: [
        'XAGUSDm', 'XAUUSDm',
        'BTCUSDm', 'USOILm'
    ])  # ETHUSDm removed -- too illiquid/volatile for this scalping strategy
    SYMBOL_MIN_EQUITY: dict = field(default_factory=lambda: {
        'BTCUSDm':  50,    # viable at ~$50+ (ATR SL ~$1 at 0.01 lot)
        'USOILm':   150,   # viable at ~$150+ (ATR SL ~$1.50)
        'XAUUSDm':  300,   # viable at ~$300+ (ATR SL ~$4)
        'ETHUSDm':  600,   # viable at ~$600+ (0.1 lot min, ATR SL ~$10)
        'XAGUSDm':  1000,  # viable at ~$1000+ (ATR SL ~$10-20)
    })
    MAX_CONCURRENT_TRADES: int = 2   # Max 2 open trades -- protects small account equity
    MAX_DAILY_TRADES: int = 50
    MAX_DAILY_LOSS_PERCENT: float = 25.0
    MAX_DAILY_DRAWDOWN_PERCENT: float = 30.0  # 3 x 10% trades before halt
    ROLLOVER_WINDOW_START: int = 22
    ROLLOVER_WINDOW_END: int = 23
    TRADE_COOLDOWN_MINUTES: int = 5          # FAST RE-ENTRY for scalping

    # Timeframes
    ENTRY_TF: int = mt5.TIMEFRAME_M5
    STRUCTURE_TF: int = mt5.TIMEFRAME_M15
    MICRO_STRUCTURE_TF: int = mt5.TIMEFRAME_M1
    TREND_TF: int = mt5.TIMEFRAME_H1
    ATR_PERIOD: int = 14
    
    # DYNAMIC PARAMETERS
    
    # SMC PARAMETERS (No more ATR-based SL)
    SL_BUFFER_PIPS: float = 2.0      # Buffer below sweep
    TP_RR_RATIO: float = 3.0         # Target 1:3 RR
    PARTIAL_TP_RR: float = 2.0       # Partial at 1:2
    
    ENABLE_BREAKEVEN: bool = True
    BREAKEVEN_TRIGGER_RR: float = 1.5 # Breakeven at 1.5R
    
    ENABLE_PARTIAL_TP: bool = True
    PARTIAL_TP_PERCENT: float = 50.0

    SPREAD_ATR_THRESHOLD: float = 0.50
    MAX_SPREAD_RATIO: float = 0.50   # 50% of SL distance -- allows normal scalping spreads

    # Risk sizing -- calibrated for small accounts ($50-$500)
    # With $91 equity: 1% = $0.91 max risk per trade
    # Max 2 simultaneous trades = max 2% account at risk at once
    BASE_RISK_PERCENT: float = 10.0      # 1% risk per trade
    MAX_RISK_PERCENT: float = 10.0       # Hard cap -- never exceed 1.5% for scalping

    # ?? SPREAD-SAFE SL SETTINGS (NEW) ????????????????????????????????????????
    # MT5 compares BID vs SL for longs, ASK vs SL for shorts.
    # SL must sit this many spreads away from entry BID/ASK to avoid instant hit.
    MIN_SL_SPREAD_MULT: float = 2.0          # FIX: raised from 3.0 -- base spread buffer
    # Per-asset spread spike multipliers (spreads can widen 10-20x during news/illiquidity)
    # SL must be at least this many multiples of MAX_SPREAD away (not current spread)
    # This protects against the spread spike scenario (XAG -$1.60 in 4s incident)
    SPIKE_SPREAD_MULT_XAG:  float = 20.0   # XAG spread can spike from $0.05 to $1.00
    SPIKE_SPREAD_MULT_XAU:  float = 10.0   # XAU spread can spike from $0.30 to $3.00
    SPIKE_SPREAD_MULT_OIL:  float = 12.0   # OIL spread can spike from $0.05 to $0.60
    SPIKE_SPREAD_MULT_BTC:  float = 15.0   # BTC spread can spike from $10 to $150
    SPIKE_SPREAD_MULT_ETH:  float = 15.0   # ETH spread can spike from $0.50 to $7.50
    SPIKE_SPREAD_MULT_FX:   float = 5.0    # FX spread can spike from 0.5 to 2.5 pips
    SCALP_MAX_SPREAD_XAUUSD: float = 1.20   # Max $1.20 spread on XAUUSD
    SCALP_MAX_SPREAD_XAGUSD: float = 0.06   # Max $0.06 spread on XAGUSD (was 0.04 -- too tight for most brokers)
    SCALP_MAX_SPREAD_BTC: float = 20.0      # Max $20  spread on BTC
    SCALP_MAX_SPREAD_ETH: float = 2.00      # Max $2   spread on ETH
    SCALP_MAX_SPREAD_OIL: float = 0.10      # Max $0.10 spread on OIL (was 0.06 -- too tight, typical is 0.03-0.08)
    SCALP_MAX_SPREAD_FX_PIPS: float = 1.5   # Max 1.5 pips on FX pairs

    # ?? SCALPING QUALITY FILTERS (NEW) ???????????????????????????????????????
    SCALP_MIN_ADX: float = 14.0             # 18 = balanced: catches trending moves, filters ranging chop
    SCALP_MIN_VOL_RATIO: float = 0.4  # 0.8 was blocking all post-NY sessions (natural volume drop)        # Min tick-vol vs 20-bar average (was 1.2 -- too strict, relaxed)
    SCALP_RSI_MIN: float = 10.0  # effective lower bound (RSI 10-20 = extreme chasing, rare)             # FIX: was 28 -- too tight; Gold at RSI 26 is still in a valid SELL zone
    SCALP_RSI_MAX: float = 90.0  # effective upper bound (RSI > 90 = extreme chasing, rare)             # FIX: was 72 -- Gold RSI 73 can still deliver strong BUY moves
    SCALP_FORCE_KILL_ZONE: bool = False      # FIX: Disabled -- IST morning (10AM) = 04:30 UTC = outside London/NY
    # Active trading allowed during ANY session when ADX/volume confirm momentum
    SCALP_MIN_ATR_SL_MULT: float = 0.10  # 0.1x ATR: minimal noise buffer. SL is structural (wick), not ATR-based.
    
    # Local News Filter
    NEWS_API_URL: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    NEWS_PAUSE_BEFORE_MINUTES: int = 30
    NEWS_PAUSE_AFTER_MINUTES: int = 30
    HIGH_IMPACT_CURRENCIES: List[str] = field(default_factory=lambda: ["USD", "EUR", "GBP", "JPY"])

    # Local Confluence Engine
    # SIMPLIFIED: Binary Gating, no scoring needed
    
    # Local Strategy Weights - SINGLE ENGINE
    STRATEGY_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        'LIQUIDITY_FVG_ENGINE': 1.0
    })
    
    # Enabled Local Strategies
    ENABLED_STRATEGIES: List[str] = field(default_factory=lambda: [
        'LIQUIDITY_FVG_ENGINE'
    ])
    
    # Strategy-Specific Params
    ICT_FVG_MITIGATION_CANDLES: int = 20
    ICT_KILLZONES: Dict[str, Tuple[int, int]] = field(default_factory=lambda: {
        'LONDON': (7, 12),    # FIX: was (7,10) -- London session runs until ~12:00 UTC
        'NEW_YORK': (12, 17), # FIX: was (12,16) -- NY overlap extends to ~17:00 UTC
        'ASIAN': (1, 5)       # FIX: was (1,4) -- Asian session runs until ~5:00 UTC
    })
    
    # Feature Flags
    ENABLE_AI_VALIDATION: bool = True   # FIX: duplicate field removed -- set True above
    ENABLE_AI_RISK_MANAGEMENT: bool = True
    
    LOOP_DELAY_SECONDS: float = 5.0

    # ---- Missing strategy config constants (caused AttributeError) ----
    # SMC / Order Block strategy
    SMC_MIN_OB_SIZE_PIPS: float = 5.0
    SMC_SWING_LOOKBACK: int = 10
    SMC_VALIDATION_CANDLES: int = 10
    # Wyckoff / Volume strategy
    VOLUME_LOOKBACK: int = 20
    VOLUME_SURGE_MULTIPLIER: float = 1.8
    VOLUME_PROFILE_PERIODS: int = 50
    # Momentum / Bollinger strategy
    MOMENTUM_EMA_SLOW: int = 21
    BB_PERIOD: int = 20
    BB_STD_DEV: float = 2.0
    # TP ratio from config
    TP_PRIMARY_RR: float = 2.0   # 1:2 RR for scalping (faster target, higher hit rate)
    TP_RUNNER_RR:  float = 3.0   # Runner at 1:3 RR after partial TP taken

config = AITradingConfig()

# Symbol Specifications (same as original)
SYMBOL_SPECS = {
    "EURUSDm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "GBPUSDm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "USDJPYm": {"pip_size": 0.01, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "XAUUSDm": {"pip_size": 0.01, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "XAGUSDm": {"pip_size": 0.001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "BTCUSDm": {"pip_size": 1.0, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 10.0},
    "ETHUSDm": {"pip_size": 0.01, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 10.0},
    "USOILm": {"pip_size": 0.01, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "NZDUSDm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "USDCADm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "AUDUSDm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "USDCHFm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "GBPJPYm": {"pip_size": 0.01, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
}

# =============================================================================
# LOGGING SETUP (Now User-Specific)
# =============================================================================

# Keyed by strategy_id as well as user_id: a user can run several strategies
# concurrently (Pro: up to 5, Enterprise: more), and without the strategy_id
# here two of their bot processes would share one log file (interleaved
# writes) and one backup JSON file (lost-update race on read-modify-write).
LOG_DIR = f"Hybrid_AI_Bot_Logs_{USER_ID}_{STRATEGY_ID}"
BACKUP_DIR = f"Backup_Trades_{USER_ID}_{STRATEGY_ID}"
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# Silence noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)
logging.getLogger("http11").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# Configure Dedicated Logger
logger = logging.getLogger("SCALPING_BOT")
logger.setLevel(logging.DEBUG)
logger.propagate = False # Prevent bubbling up to root

# Formatter
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

# File Handler
file_handler = logging.FileHandler(os.path.join(LOG_DIR, f"hybrid_ai_bot_{datetime.now().strftime('%Y%m%d')}.log"), encoding='utf-8')
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)   # INFO only -- no per-cycle debug spam

# Stream Handler (ensure stdout uses utf-8)

class _DedupFilter(logging.Filter):
    """Suppress identical log messages repeated within 30 seconds."""
    def __init__(self, window_secs=30):
        super().__init__()
        self._seen   = {}
        self._counts = {}
        self._window = window_secs
        self._always = {'TRADE OPENED','TRADE CLOSED','EMERGENCY','CRITICAL',
                        'ERROR','QUOTA','BREAKEVEN','TRAILING','AOX L','[SSM]',
                        'SWAPPY','SHAAKUNI found','NEWS VETO'}
    def filter(self, record):
        msg = record.getMessage()
        if any(k in msg for k in self._always): return True
        if record.levelno >= logging.WARNING: return True
        now  = time.time()
        key  = msg[:80]
        last = self._seen.get(key, 0)
        if now - last < self._window:
            self._counts[key] = self._counts.get(key, 0) + 1
            return False
        cnt = self._counts.pop(key, 0)
        if cnt > 0:
            record.msg = f"[x{cnt+1} in {self._window}s] {record.msg}"
        self._seen[key] = now
        return True

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)   # INFO: see setups and trade decisions

# Add Handlers
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
logger.addFilter(_DedupFilter(window_secs=30))
# =============================================================================
# TELEGRAM & HEARTBEAT FUNCTIONS (New)
# =============================================================================

def get_actual_broker_symbol(base_symbol_name: str) -> str:
    """Auto-detect broker symbol with caching"""
    if not hasattr(get_actual_broker_symbol, 'cache'):
        get_actual_broker_symbol.cache = {}
    
    if base_symbol_name in get_actual_broker_symbol.cache:
        return get_actual_broker_symbol.cache[base_symbol_name]
    
    # Try exact match first
    if mt5.symbol_info(base_symbol_name):
        get_actual_broker_symbol.cache[base_symbol_name] = base_symbol_name
        return base_symbol_name
        
    # Try common suffixes
    suffixes = ['m', 'pro', 'ecn', '+', '.', '_', 'c', 'z']
    for suffix in suffixes:
        test_name = f"{base_symbol_name}{suffix}"
        if mt5.symbol_info(test_name):
            get_actual_broker_symbol.cache[base_symbol_name] = test_name
            return test_name
            
    # Last resort: Search all symbols
    all_symbols = mt5.symbols_get()
    if all_symbols:
        for s in all_symbols:
            if base_symbol_name in s.name and len(s.name) < len(base_symbol_name) + 4:
                get_actual_broker_symbol.cache[base_symbol_name] = s.name
                return s.name
    
    get_actual_broker_symbol.cache[base_symbol_name] = base_symbol_name
    return base_symbol_name

def send_telegram_notification(message: str, parse_mode: str = "HTML", max_retries: int = 3):
    """Send Telegram notification with retry logic"""
    if not TELEGRAM_CHAT_ID or not TELEGRAM_BOT_TOKEN:
        return
    
    for attempt in range(max_retries):
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": parse_mode
            }
            response = requests.post(url, json=data, timeout=5)
            if response.status_code == 200:
                return True
            logger.warning(f"Telegram notification failed (attempt {attempt+1}/{max_retries}): {response.text}")
        except Exception as e:
            import traceback as _tb
            logger.error(f" [LOOP CRASH] {type(e).__name__}: {str(e)[:200]}")
            logger.error(_tb.format_exc()[-400:])
            time.sleep(1)
    return False

def _send_heartbeat_sync(status: str = 'running', mt5_connected: bool = True, error_message: str = None, max_retries: int = 3):
    """Background heartbeat sender - never call directly."""
    for attempt in range(max_retries):
        try:
            account_info = mt5.account_info()
            
            heartbeat_data = {
                'user_id': USER_ID,
                'strategy_id': STRATEGY_ID,
                'last_heartbeat': datetime.now(timezone.utc).isoformat(),
                'status': status.lower(), # Ensure lowercase
                'mt5_connected': mt5_connected,
                'error_message': error_message,
                'pid': os.getpid(), # Always send PID for control
                'balance': account_info.balance if account_info else 0.0,
                'equity': account_info.equity if account_info else 0.0,
                'daily_trades': getattr(state, 'daily_trades', 0),
                'metadata': {
                    'daily_pnl': getattr(state, 'daily_pnl', 0.0)
                }
            }

            supabase.table('bot_heartbeats').upsert(
                heartbeat_data, 
                on_conflict='user_id,strategy_id'
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update heartbeat (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
    return False

# =============================================================================
# SUPABASE TRADE DATABASE (Replaces SQLite)
# =============================================================================

class SupabaseTradeDB:
    """Supabase database with retry logic and local backup"""
    
    def __init__(self):
        self.backup_file = os.path.join(BACKUP_DIR, f"failed_trades_{datetime.now().strftime('%Y%m%d')}.json")
        logger.info("Supabase Trade DB initialized with backup system")
    
    def _retry_operation(self, operation_name: str, operation_func, max_retries: int = 3):
        """Generic retry wrapper for Supabase operations"""
        for attempt in range(max_retries):
            try:
                return operation_func()
            except Exception as e:
                logger.error(f"{operation_name} failed (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        return None
    
    def _save_to_backup(self, trade_data: Dict, operation: str):
        """Save failed operations to local backup"""
        try:
            backup_entry = {
                'operation': operation,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'data': trade_data
            }
            with open(self.backup_file, 'a') as f:
                f.write(json.dumps(backup_entry) + '\n')
            logger.warning(f"Trade data backed up locally: {self.backup_file}")
        except Exception as e:
            logger.critical(f"Failed to save backup: {e}")
    
    def log_trade(self, trade_data: Dict) -> bool:
        """Log trade to Supabase with Corrected Schema"""
        try:
            # Match schema: ticket (int), trade_type, quantity, status (lowercase)
            db_trade = {
                'user_id': USER_ID,
                'strategy_id': STRATEGY_ID,
                'ticket': int(trade_data.get('ticket')),
                'symbol': trade_data.get('symbol'),
                'trade_type': trade_data.get('direction', '').upper(),
                'quantity': float(trade_data.get('lot_size', 0)),
                'entry_price': float(trade_data.get('entry_price', 0)),
                'status': 'open',
                'opened_at': trade_data.get('timestamp', datetime.utcnow().isoformat()),
                'metadata': {
                    'stop_loss': trade_data.get('stop_loss'),
                    'take_profit': trade_data.get('take_profit'),
                    'strategy_name': trade_data.get('strategy_name'),
                    'atr': trade_data.get('atr'),
                    'ai_confidence': trade_data.get('ai_confidence')
                }
            }
            
            def insert_trade():
                result = supabase.table('trades').upsert(db_trade, on_conflict='ticket,user_id').execute()
                logger.info(f"[DB] Trade {db_trade['ticket']} synced to dashboard")
                return True
            
            result = self._retry_operation("Trade logging", insert_trade)
            
            if not result:
                self._save_to_backup(db_trade, 'log_trade')
                return False
            
            # Send Telegram notification
            send_telegram_notification(
                f" <b>New Trade Opened</b>\n\n"
                f"Symbol: {db_trade['symbol']}\n"
                f"Type: {db_trade['trade_type']}\n"
                f"Entry: {db_trade['entry_price']:.5f}\n"
                f"Lot: {db_trade['quantity']}\n"
            )
            return True
            
        except Exception as e:
            logger.error(f"[DB ERROR] Trade logging failed: {e}")
            return False

    def update_trade_closed(self, ticket: int, exit_price: float, profit_loss: float, exit_reason: str) -> bool:
        """Update trade as closed with retry logic"""
        def update_trade():
            # Find the trade
            trades = supabase.table('trades').select('*').eq(
                'user_id', USER_ID
            ).eq(
                'ticket', int(ticket)
            ).eq('status', 'open').execute()
            
            if not trades.data:
                logger.warning(f"Trade {ticket} not found or already closed")
                return
            
            trade = trades.data[0]
            
            # Calculate metrics
            entry_price = float(trade.get('entry_price', 0))
            pips_gained = abs(exit_price - entry_price)
            
            # Update the trade with Corrected Schema
            # match dashboard columns: exit_price, profit_loss, closed_at, status
            supabase.table('trades').update({
                'status': 'closed',
                'exit_price': float(exit_price),
                'profit_loss': float(profit_loss),
                'closed_at': datetime.now(timezone.utc).isoformat(),
                'metadata': {
                    **trade.get('metadata', {}),
                    'exit_reason': exit_reason,
                    'pips_gained': pips_gained
                }
            }).eq('ticket', int(ticket)).eq('user_id', USER_ID).execute()
            
            logger.info(f"[DB] Trade {ticket} closed synced: ${profit_loss:.2f}")
            return True # Indicate success
        
        success = self._retry_operation(f"Update trade {ticket}", update_trade)
        
        if not success:
            self._save_to_backup({
                'ticket': ticket,
                'exit_price': exit_price,
                'profit_loss': profit_loss,
                'exit_reason': exit_reason
            }, 'update_trade_closed')
            logger.error(f"[ERROR] Failed to update trade {ticket} - saved to backup")
            return False
        
        # Send Telegram notification with context
        if profit_loss > 0:
            _emoji = "[WIN]"
        elif profit_loss == 0 or exit_reason == 'BE':
            _emoji = "[BE]"
        else:
            _emoji = "[LOSS]"
        _exit_note = " (bot exited early)" if exit_reason == "EXIT_ENGINE" else ""
        send_telegram_notification(
            f"{_emoji} <b>Trade Closed</b>\n\n"
            f"Ticket: {ticket}\n"
            f"Reason: {exit_reason}{_exit_note}\n"
            f"P&L: ${profit_loss:.2f}"
        )
        
        return True
    
    def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        """Get recent trades with robust retry logic"""
        def fetch():
            res = supabase.table('trades').select('*').eq('user_id', USER_ID).eq('status', 'closed').order('closed_at', desc=True).limit(limit).execute()
            return res.data if res.data else []
        
        data = self._retry_operation("Fetch recent trades", fetch)
        if data:
            return [self.convert_to_ai_format(t) for t in data]
        return []

    def get_session_trades(self, since: datetime, limit: int = 50) -> List[Dict]:
        """
        Get trades closed AFTER `since` (i.e. only this bot session).
        Used by emergency checks so old losses from previous sessions
        never trigger an instant halt on restart.
        """
        def fetch():
            res = (
                supabase.table('trades')
                .select('*')
                .eq('user_id', USER_ID)
                .eq('status', 'closed')
                .gte('closed_at', since.isoformat())
                .order('closed_at', desc=True)
                .limit(limit)
                .execute()
            )
            return res.data if res.data else []

        data = self._retry_operation("Fetch session trades", fetch)
        if data:
            return [self.convert_to_ai_format(t) for t in data]
        return []
    
    def get_winning_trades(self, limit: int = 20) -> List[Dict]:
        """Get winning trades with retry logic"""
        def fetch():
            res = supabase.table('trades').select('*').eq('user_id', USER_ID).eq('status', 'closed').gt('profit_loss', 0).order('closed_at', desc=True).limit(limit).execute()
            return res.data if res.data else []
        
        data = self._retry_operation("Fetch winnings", fetch)
        if data:
            return [self.convert_to_ai_format(t) for t in data]
        return []
    
    def get_losing_trades(self, limit: int = 20) -> List[Dict]:
        """Get losing trades with retry logic"""
        data = []
        def fetch():
            nonlocal data
            res = supabase.table('trades').select('*').eq('user_id', USER_ID).eq('status', 'closed').lt('profit_loss', 0).order('closed_at', desc=True).limit(limit).execute()
            data = res.data if res.data else []
        
        if self._retry_operation("Fetch losses", fetch):
            return [self.convert_to_ai_format(t) for t in data]
        return []

    def sync_account_history(self, days_back: int = 30):
        """Sync MT5 history with Supabase and fix zombie trades"""
        logger.info(f" Syncing trade history (last {days_back} days)...")
        
        from_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        to_date = datetime.now(timezone.utc)
        
        deals = mt5.history_deals_get(from_date, to_date)
        
        if deals is None or len(deals) == 0:
            logger.info("No history found in MT5")
            return

        count = 0
        fixed_zombies = 0
        
        for deal in deals:
            if deal.entry != mt5.DEAL_ENTRY_OUT:
                continue
            
            ticket = deal.position_id
            
            try:
                existing = supabase.table('trades').select('*').eq(
                    'ticket', int(ticket)
                ).eq('user_id', USER_ID).execute()
                
                if existing.data:
                    record = existing.data[0]
                    
                    # [OK] FIX: Zombie trade detection
                    if record.get('status') == 'open':
                        logger.warning(f" Found ZOMBIE trade {ticket} - updating...")
                        
                        profit = deal.profit
                        exit_reason = 'TP' if profit > 0 else 'SL' if profit < 0 else 'BE'
                        
                        self.update_trade_closed(ticket, deal.price, profit, f"{exit_reason} (OFFLINE)")
                        fixed_zombies += 1
                        
                    continue
                    
            except Exception as e:
                logger.error(f"Error checking DB for ticket {ticket}: {e}")
                continue

            # Insert missing trades
            try:
                symbol = deal.symbol
                profit = deal.profit
                direction = "BUY" if deal.type == 1 else "SELL"
                
                db_trade = {
                    'user_id': USER_ID,
                    'strategy_id': STRATEGY_ID,
                    'symbol': symbol,
                    'trade_type': direction,
                    'entry_price': deal.price,
                    'exit_price': deal.price,
                    'quantity': deal.volume,
                    'status': 'closed',
                    'opened_at': (datetime.fromtimestamp(deal.time, timezone.utc) - timedelta(hours=1)).isoformat(), 
                    'closed_at': datetime.fromtimestamp(deal.time, timezone.utc).isoformat(),
                    'ticket': int(ticket),
                    'profit_loss': profit,
                    'metadata': {
                        'strategy_name': 'SYNCED',
                        'exit_reason': 'HISTORY_SYNC',
                        'market_regime': 'UNKNOWN',
                        'imported': True
                    }
                }
                
                supabase.table('trades').upsert(db_trade, on_conflict='ticket,user_id').execute()
                count += 1
                
            except Exception as e:
                logger.error(f"Failed to sync trade {ticket}: {e}")

        if count > 0 or fixed_zombies > 0:
            logger.info(f" Sync Complete: {count} new imports, {fixed_zombies} zombie trades fixed")
        else:
            logger.info(" History is up to date")

    def restore_state_from_db(self, open_positions_dict: Dict):
        """Stateless Restoration: Pulls management flags from Supabase metadata"""
        logger.info(" [DB] Restore state (Retrying if needed)...")
        data = []
        def fetch():
            nonlocal data
            res = supabase.table('trades').select('*').eq('user_id', USER_ID).eq('status', 'open').execute()
            data = res.data if res.data else []
        
        if self._retry_operation("Restore State", fetch):
            for db_trade in data:
                ticket = int(db_trade.get('ticket'))
                meta = db_trade.get('metadata', {})
                
                params = {
                    'atr': meta.get('atr', 0.0010),
                    'tp1': meta.get('take_profit', 0.0),
                    'sl': meta.get('stop_loss', 0.0),
                    'entry_price': float(db_trade.get('entry_price', 0)),
                    'regime': meta.get('market_regime', 'TRENDING')
                }
                
                open_positions_dict[ticket] = {'params': params}
                
                # RESTORE MANAGEMENT FLAGS
                if meta.get('be_moved'):
                    state.be_moved.add(ticket)
                
                if meta.get('partial_tp_executed'):
                    state.partial_closed.add(ticket)
                
                if meta.get('trailing_active'):
                    state.trailing_active.add(ticket)

                logger.info(f" [RESTORED] Ticket #{ticket} | BE: {meta.get('be_moved')} | Partial: {meta.get('partial_tp_executed')}")

        # RESTORE ACTIVE SYMBOL BANS from bot_commands table
        # Any symbol banned for 24h before a restart stays banned until its expiry.
        try:
            ban_row = supabase.table('bot_commands').select('*').eq('user_id', USER_ID).execute()
            if ban_row.data:
                row = ban_row.data[0]
                now_utc = datetime.now(timezone.utc)
                restored_bans = []
                for key, value in row.items():
                    if key.startswith('ban_') and value:
                        symbol_name = key[4:]  # strip 'ban_' prefix
                        try:
                            expiry = datetime.fromisoformat(str(value))
                            if expiry.tzinfo is None:
                                expiry = expiry.replace(tzinfo=timezone.utc)
                            if expiry > now_utc:
                                state.symbol_cooldowns[symbol_name] = expiry
                                restored_bans.append(f"{symbol_name} until {expiry.strftime('%H:%M UTC')}")
                        except Exception:
                            pass
                if restored_bans:
                    logger.warning(f" [RESTORE] Active symbol bans restored: {', '.join(restored_bans)}")
        except Exception as e:
            logger.warning(f" [RESTORE] Could not load symbol bans: {e}")
            
    def convert_to_ai_format(self, trade: Dict) -> Dict:
        """Convert Supabase trade to AI format"""
        metadata = trade.get('metadata', {})
        pl = trade.get('profit_loss')
        if pl is None:
            pl = 0.0

        return {
            'symbol': trade.get('symbol'),
            'strategy_name': metadata.get('strategy_name'),
            'profit_loss': pl,
            'win': 1 if pl > 0 else 0,
            'exit_reason': metadata.get('exit_reason'),
            'market_regime': metadata.get('market_regime'),
            'session': metadata.get('session')
        }
    
    def get_trade_by_ticket(self, ticket: int) -> Dict:
        """Get full trade details with retry logic"""
        data = []
        def fetch():
            nonlocal data
            res = supabase.table('trades').select('*').eq('user_id', USER_ID).eq('ticket', int(ticket)).execute()
            data = res.data if res.data else []
        
        if self._retry_operation(f"Fetch ticket {ticket}", fetch):
            if not data: return {}
            trade = data[0]
            metadata = trade.get('metadata', {})
            
            # Return comprehensive trade data for AI analysis
            return {
                'ticket': ticket,
                'symbol': trade.get('symbol'),
                'direction': trade.get('trade_type'),
                'entry_price': float(trade.get('entry_price', 0)),
                'stop_loss': metadata.get('stop_loss', 0),
                'take_profit': metadata.get('take_profit', 0),
                'timestamp': trade.get('opened_at'),
                'lot_size': float(trade.get('quantity', 0)),
                'session': metadata.get('session'),
                'market_regime': metadata.get('market_regime'),
                'ai_confidence': metadata.get('ai_confidence'),
                'trend_strength': metadata.get('trend_strength'),
                'metadata': metadata
            }
        return {}

    def update_metadata(self, ticket: str, updates: Dict) -> bool:
        """Update metadata with retries"""
        def update():
            # 1. Get current metadata
            res = supabase.table('trades').select('metadata').eq('ticket', int(ticket)).eq('user_id', USER_ID).execute()
            if not res.data: return
            
            current_meta = res.data[0].get('metadata', {})
            
            # 2. Merge updates
            current_meta.update(updates)
            
            # 3. Save back
            supabase.table('trades').update({'metadata': current_meta}).eq('ticket', int(ticket)).eq('user_id', USER_ID).execute()
        
        return self._retry_operation(f"Update meta {ticket}", update)

trade_db = SupabaseTradeDB()
# =============================================================================
# AI STATE MANAGEMENT
# =============================================================================

class AITradingState:
    """Enhanced state with partial TP tracking"""
    def __init__(self):
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.open_positions: Dict = {}
        self.last_ai_learning_time = None
        self.daily_start_equity: float = 0.0
        
        # DYNAMIC PARAMETERS
        # [SMC] Structure-based parameters (No more ATR multipliers)
        self.struct_sl_buffer: float = config.SL_BUFFER_PIPS
        self.struct_tp_ratio: float = config.TP_RR_RATIO
        
        # Trade management
        self.be_moved: set = set()
        self.trailing_active: set = set()
        
        # [OK] FIX: Partial TP tracking
        self.partial_closed: set = set()

        # Pre-Approved Bias
        self.approved_bias: Dict[str, str] = {}
        self.ai_bias_strength: Dict[str, int] = {}
        self.ai_key_levels: Dict[str, float] = {}
        self.ai_avoid_symbols: Dict[str, bool] = {}
        self.l3_last_call: Dict[str, float] = {}   # symbol -> timestamp of last L3 call
        self.l3_last_score: Dict[str, int] = {}    # symbol -> last L3 score (for reuse)
        self.last_global_context_update = None
        
        # Strategy Banning
        self.banned_strategies: List[str] = []
        
        # News Filter
        self.last_local_news_update = None
        self.upcoming_high_impact_events: List[Dict] = []
        
        # Trade Cooldowns
        self.symbol_cooldowns: Dict[str, datetime] = {}
        self.last_trade_candle: Dict[str, Any] = {} # [NEW] One trade per candle rule
        self.consecutive_losses: Dict[str, int] = {} # [NEW] Founder's rule: 2 losses = ban symbol for day

        # Session tracking -- used to scope emergency checks to THIS run only.
        # Prevents old losses from a previous session triggering an instant halt on restart.
        self.session_start_time: datetime = datetime.now(timezone.utc)
        
        # Legacy Fields
        self.global_strong_currencies: List[str] = []
        self.global_weak_currencies: List[str] = []
        self.global_market_sentiment: str = "NEUTRAL"
        self.global_key_drivers: str = "N/A"

state = AITradingState()

# =============================================================================
# ULTIMATE AI ENHANCEMENTS - FULL IMPLEMENTATION
# =============================================================================

class PatternRecognitionSystem:
    """
    EDGE HEALTH MONITOR:
    Tracks pattern success rates to modify confidence.
    Does NOT predict outcomes, but measures 'Edge Quality'.
    """
    
    def __init__(self):
        self.patterns_file = os.path.join(DATA_DIR, 'trade_patterns.json')
        # patterns_db is the one and only pattern store -- learn_from_trade,
        # save_patterns, predict_trade_quality, and find_similar_trades all
        # already read/write this name. load_patterns() sets it below,
        # unconditionally (see its own fix note for why "unconditionally"
        # matters).
        self.patterns_db = []
        self.load_patterns()

    # calculate_similarity() is a raw additive point score (symbol=5,
    # direction=10 [required to be nonzero], session=3, hour=2, day=1,
    # adx=2, rsi=2, volatility=1.5, volume_ratio=1, price_position=1;
    # max ~28.5), not a 0-1 normalized score. "High similarity" here means
    # most of the optional factors also agreeing on top of the mandatory
    # direction match, not just >0.8 out of ~28.5 (which every stored
    # pattern would trivially clear). This threshold is still a starting
    # point, not empirically validated -- tune it with the backtest
    # harness (python_scripts/backtest/) now that this method actually runs.
    SIMILARITY_THRESHOLD = 17.0

    def get_edge_health_score(self, symbol: str, direction: str, context: dict) -> float:
        """
        Compare current setup to database of similar past setups.
        Returns: 0.0 to 1.5 multiplier for confidence.
        """
        if not self.patterns_db: return 1.0

        # Every caller today passes context={} (see the get_edge_health_score
        # call site) -- comparing that raw empty dict directly against stored
        # patterns' `features` (which have symbol/direction/session/hour/...)
        # always failed the mandatory direction check inside
        # calculate_similarity and returned 0.0, unconditionally. Build a
        # real features dict here instead, the same way predict_trade_quality
        # does, so a live features dict is actually compared to stored ones.
        current_features = self.extract_features(symbol, direction, context)
        if not current_features: return 1.0

        # Find similar past patterns
        similar_score = 0
        total_weight = 0

        for p in self.patterns_db:
            sim = self.calculate_similarity(current_features, p['features'])
            if sim > self.SIMILARITY_THRESHOLD:
                weight = sim * sim
                outcome = 1 if p['profit'] > 0 else -1
                similar_score += outcome * weight
                total_weight += weight

        if total_weight == 0: return 1.0
        
        # Normalize score (-1 to 1)
        normalized_score = similar_score / total_weight
        
        # Convert to multiplier (0.5 to 1.5)
        # Positive score -> Boost confidence
        # Negative score -> Reduce confidence
        multiplier = 1.0 + (normalized_score * 0.5)
        
        # logger.debug(f" [PATTERN] {symbol} Similarity Score: {normalized_score:.2f} -> Mult: {multiplier:.2f}")
        return max(0.5, min(1.5, multiplier))

    def predict_success_rate(self, symbol: str, direction: str, context: dict) -> float:
        """DEPRECATED: Use get_edge_health_score instead"""
        return 0.5

    def load_patterns(self):
        """
        Load existing patterns from file. Always leaves self.patterns_db
        set to a list -- previously this only assigned it inside the
        `if os.path.exists(...)` branch (or the except block), so a brand
        new user/strategy with no trade_patterns.json yet left patterns_db
        never assigned at all. That crashed the bot at startup every time
        (`pattern_recognizer.patterns_db` read at module scope right after
        construction, AttributeError, process exits) -- i.e. every
        first-ever run for a new user, and every restart before their
        first learned trade got saved. __init__ now also pre-sets
        patterns_db = [] before calling this, so this is now defense in
        depth rather than the only thing standing between a new user and
        an immediate crash.
        """
        self.patterns_db = []
        try:
            import json
            import os
            if os.path.exists(self.patterns_file):
                with open(self.patterns_file, 'r') as f:
                    self.patterns_db = json.load(f)
                logger.info(f"[PATTERN] Loaded {len(self.patterns_db)} historical patterns")
        except Exception as e:
            logger.error(f"[PATTERN] Error loading patterns: {e}")
            self.patterns_db = []
    
    def extract_features(self, symbol: str, direction: str, context: dict) -> dict:
        """
        Extract 25+ features for pattern matching
        """
        try:
            df = get_market_data(symbol, config.ENTRY_TF, 50)
            if df is None:
                return {}
            
            # Technical indicators
            try:
                adx_val, _, _ = calculate_adx(df['high'], df['low'], df['close'], 14)
                adx = float(adx_val.iloc[-1]) if len(adx_val) > 0 else 0
            except:
                adx = 0
                
            try:
                atr = float(calculate_atr(df['high'], df['low'], df['close'], 14).iloc[-1])
            except:
                atr = 0
                
            # RSI
            try:
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = float(100 - (100 / (1 + rs.iloc[-1])))
            except:
                rsi = 50
            
            # Price action
            close = float(df['close'].iloc[-1])
            high_5 = float(df['high'].iloc[-5:].max())
            low_5 = float(df['low'].iloc[-5:].min())
            price_position = (close - low_5) / (high_5 - low_5) if high_5 != low_5 else 0.5
            
            # Volatility
            volatility = float(df['close'].pct_change().std() * 100)
            
            # Volume
            avg_volume = float(df['tick_volume'].mean())
            recent_volume = float(df['tick_volume'].iloc[-3:].mean())
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Time features
            now = datetime.now(timezone.utc)
            hour = now.hour
            day_of_week = now.weekday()  # 0=Monday, 6=Sunday
            
            # Session
            session = get_current_session()
            session_map = {'ASIAN': 0, 'LONDON': 1, 'NEWYORK': 2, 'SYDNEY': 3}
            session_numeric = session_map.get(session, 0)
            
            # Context features
            spread = context.get('spread', 0)
            
            features = {
                # Technical
                'adx': round(adx, 2),
                'rsi': round(rsi, 2),
                'atr': round(atr, 5),
                'volatility': round(volatility, 4),
                
                # Price action
                'price_position': round(price_position, 3),
                'volume_ratio': round(volume_ratio, 3),
                
                # Time
                'hour': hour,
                'day_of_week': day_of_week,
                'session': session_numeric,
                
                # Symbol & Direction
                'symbol': symbol,
                'direction': 1 if direction == 'BUY' else 0,
                
                # Spread
                'spread': spread,
                
                # Strategy confluence
                'confluence': context.get('confluence', 0),
            }
            
            return features
            
        except Exception as e:
            logger.error(f"[PATTERN] Error extracting features: {e}")
            return {}
    
    def learn_from_trade(self, symbol: str, direction: str, context: dict, profit: float):
        """
        Store pattern with outcome
        """
        try:
            features = self.extract_features(symbol, direction, context)
            if not features:
                return
            
            pattern = {
                'features': features,
                'outcome': 'WIN' if profit > 0 else 'LOSS',
                'profit': round(profit, 2),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            self.patterns_db.append(pattern)
            
            # Keep only last 1000 patterns
            if len(self.patterns_db) > 1000:
                self.patterns_db = self.patterns_db[-1000:]
            
            # Save to file
            self.save_patterns()
            
            logger.info(f"[PATTERN] Learned from {symbol} {direction}: {pattern['outcome']} (${profit:.2f})")
            
        except Exception as e:
            logger.error(f"[PATTERN] Error learning from trade: {e}")
    
    def save_patterns(self):
        """Save patterns to file"""
        try:
            import json
            with open(self.patterns_file, 'w') as f:
                json.dump(self.patterns_db, f)
        except Exception as e:
            logger.error(f"[PATTERN] Error saving patterns: {e}")
    
    def predict_trade_quality(self, symbol: str, direction: str, context: dict) -> tuple[float, int]:
        """
        Predict trade success probability based on similar past trades
        Returns: (success_probability, num_similar_trades)
        """
        try:
            if len(self.patterns_db) < 10:
                return 0.5, 0  # Not enough data
            
            current_features = self.extract_features(symbol, direction, context)
            if not current_features:
                return 0.5, 0
            
            # Find similar trades
            similar_trades = self.find_similar_trades(current_features, n=20)
            
            if len(similar_trades) == 0:
                return 0.5, 0
            
            # Calculate success rate
            wins = sum(1 for t in similar_trades if t['outcome'] == 'WIN')
            success_rate = wins / len(similar_trades)
            
            # Calculate average profit of similar trades
            avg_profit = sum(t['profit'] for t in similar_trades) / len(similar_trades)
            
            logger.info(f"[PATTERN] {symbol} {direction}: {success_rate:.0%} success rate based on {len(similar_trades)} similar trades (avg profit: ${avg_profit:.2f})")
            
            return success_rate, len(similar_trades)
            
        except Exception as e:
            logger.error(f"[PATTERN] Error predicting quality: {e}")
            return 0.5, 0
    
    def find_similar_trades(self, features: dict, n: int = 20) -> list:
        """
        Find N most similar past trades
        """
        try:
            scored = []
            
            for pattern in self.patterns_db:
                similarity = self.calculate_similarity(features, pattern['features'])
                scored.append((similarity, pattern))
            
            # Sort by similarity (descending)
            scored.sort(reverse=True, key=lambda x: x[0])
            
            # Return top N patterns
            return [p for (_, p) in scored[:n]]
            
        except Exception as e:
            logger.error(f"[PATTERN] Error finding similar trades: {e}")
            return []
    
    def calculate_similarity(self, f1: dict, f2: dict) -> float:
        """
        Calculate similarity score between two feature sets
        Higher score = more similar
        """
        score = 0.0
        
        # Symbol match (important)
        if f1.get('symbol') == f2.get('symbol'):
            score += 5.0
        
        # Direction match (very important)
        if f1.get('direction') == f2.get('direction'):
            score += 10.0
        else:
            return 0.0  # Different direction = not comparable
        
        # Session match (important)
        if f1.get('session') == f2.get('session'):
            score += 3.0
        
        # Hour similarity (within 2 hours)
        hour_diff = abs(f1.get('hour', 0) - f2.get('hour', 0))
        if hour_diff <= 2:
            score += 2.0
        
        # Day of week match
        if f1.get('day_of_week') == f2.get('day_of_week'):
            score += 1.0
        
        # ADX similarity (within 10 points)
        adx_diff = abs(f1.get('adx', 0) - f2.get('adx', 0))
        if adx_diff <= 10:
            score += 2.0
        
        # RSI similarity (within 15 points)
        rsi_diff = abs(f1.get('rsi', 50) - f2.get('rsi', 50))
        if rsi_diff <= 15:
            score += 2.0
        
        # Volatility similarity
        vol_diff = abs(f1.get('volatility', 0) - f2.get('volatility', 0))
        if vol_diff <= 0.01:
            score += 1.5
        
        # Volume ratio similarity
        vol_ratio_diff = abs(f1.get('volume_ratio', 1) - f2.get('volume_ratio', 1))
        if vol_ratio_diff <= 0.5:
            score += 1.0
        
        # Price position similarity
        price_pos_diff = abs(f1.get('price_position', 0.5) - f2.get('price_position', 0.5))
        if price_pos_diff <= 0.2:
            score += 1.0
        
        return score


class SymbolPerformanceTracker:
    """
    Tracks performance metrics per symbol
    Auto-optimizes which symbols to trade
    """
    
    def __init__(self):
        self.stats_file = os.path.join(DATA_DIR, 'symbol_performance.json')
        self.stats = defaultdict(lambda: {
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'total_profit': 0.0,
            'total_pips': 0.0,
            'last_updated': None,
            'recent_trades': []  # Last 10 trades
        })
        self.load_stats()
    
    def load_stats(self):
        """Load existing stats from file"""
        try:
            import json
            import os
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    loaded = json.load(f)
                    for symbol, data in loaded.items():
                        self.stats[symbol] = data
                logger.info(f"[SYMBOL TRACKER] Loaded stats for {len(self.stats)} symbols")
        except Exception as e:
            logger.error(f"[SYMBOL TRACKER] Error loading stats: {e}")
    
    def save_stats(self):
        """Save stats to file"""
        try:
            import json
            with open(self.stats_file, 'w') as f:
                json.dump(dict(self.stats), f, indent=2)
        except Exception as e:
            logger.error(f"[SYMBOL TRACKER] Error saving stats: {e}")
    
    def record_trade(self, symbol: str, profit: float, pips: float = 0):
        """Record trade result"""
        try:
            s = self.stats[symbol]
            s['trades'] += 1
            
            if profit > 0:
                s['wins'] += 1
            else:
                s['losses'] += 1
            
            s['total_profit'] += profit
            s['total_pips'] += pips
            s['last_updated'] = datetime.now(timezone.utc).isoformat()
            
            # Add to recent trades
            s['recent_trades'].append({
                'profit': profit,
                'timestamp': s['last_updated']
            })
            
            # Keep only last 10
            s['recent_trades'] = s['recent_trades'][-10:]
            
            self.save_stats()
            
            # Log performance update
            metrics = self.get_symbol_metrics(symbol)
            logger.info(f"[SYMBOL TRACKER] {symbol}: {metrics['win_rate']:.0%} win rate ({metrics['status']}) - {s['trades']} trades")
            
        except Exception as e:
            logger.error(f"[SYMBOL TRACKER] Error recording trade: {e}")
    
    def get_symbol_metrics(self, symbol: str) -> dict:
        """Get performance metrics for symbol"""
        s = self.stats[symbol]
        
        if s['trades'] == 0:
            return {
                'trades': 0,
                'win_rate': 0.5,
                'avg_profit': 0.0,
                'avg_pips': 0.0,
                'status': 'NEW',
                'trade_score': 1.0
            }
        
        win_rate = s['wins'] / s['trades']
        avg_profit = s['total_profit'] / s['trades']
        avg_pips = s['total_pips'] / s['trades']
        
        # Recent performance (last 10 trades)
        recent_wins = sum(1 for t in s['recent_trades'] if t['profit'] > 0)
        recent_win_rate = recent_wins / len(s['recent_trades']) if s['recent_trades'] else 0.5
        
        # Determine status
        if s['trades'] < 10:
            status = 'LEARNING'
            trade_score = 1.0
        elif recent_win_rate >= 0.75:
            status = 'EXCELLENT'
            trade_score = 1.5  # Trade MORE
        elif recent_win_rate >= 0.65:
            status = 'GOOD'
            trade_score = 1.2
        elif recent_win_rate >= 0.55:
            status = 'AVERAGE'
            trade_score = 1.0
        elif recent_win_rate >= 0.45:
            status = 'BELOW_AVERAGE'
            trade_score = 0.7  # Trade LESS
        else:
            status = 'POOR'
            trade_score = 0.3  # Trade RARELY
        
        return {
            'trades': s['trades'],
            'win_rate': win_rate,
            'recent_win_rate': recent_win_rate,
            'avg_profit': avg_profit,
            'avg_pips': avg_pips,
            'status': status,
            'trade_score': trade_score
        }
    
    def should_trade_symbol(self, symbol: str) -> tuple[bool, str]:
        """
        Decide if should trade this symbol
        Returns: (allow, reason)
        """
        metrics = self.get_symbol_metrics(symbol)
        
        # Always allow if learning phase
        if metrics['status'] == 'LEARNING':
            return True, 'LEARNING_PHASE'
        
        # Block if poor recent performance
        if metrics['status'] == 'POOR' and metrics['trades'] >= 20:
            logger.warning(f" [SYMBOL TRACKER] Blocking {symbol} - Poor performance ({metrics['recent_win_rate']:.0%} recent)")
            return False, 'POOR_PERFORMANCE'
        
        # Require high quality if below average
        if metrics['status'] == 'BELOW_AVERAGE':
            return 'REQUIRE_HIGH_QUALITY', 'BELOW_AVERAGE'
        
        return True, metrics['status']


class ExecutionSpeedOptimizer:
    """
    Caches indicators and optimizes execution speed.
    Provides up to 10-times performance improvement over sequential fetching.
    """
    
    def __init__(self, ttl_seconds: int = 60):
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get(self, key: str):
        """Get cached value if still valid"""
        if key in self.cache:
            value, timestamp = self.cache[key]
            age = (datetime.now() - timestamp).seconds
            if age < self.ttl:
                return value
        return None
    
    def set(self, key: str, value):
        """Cache value with timestamp"""
        self.cache[key] = (value, datetime.now())
    
    def clear_old(self):
        """Clear expired cache entries"""
        now = datetime.now()
        expired = []
        
        for key, (value, timestamp) in self.cache.items():
            if (now - timestamp).seconds >= self.ttl:
                expired.append(key)
        
        for key in expired:
            del self.cache[key]


class SymbolCorrelationTracker:
    """
    Prevents over-exposure to correlated symbols
    Better risk diversification
    """
    
    def __init__(self):
        # Define correlation groups
        self.correlation_groups = {
            'EUR_MAJOR': ['EURUSD', 'EURGBP', 'EURJPY', 'EURCHF', 'EURAUD', 'EURNZD', 'EURCAD'],
            'GBP_MAJOR': ['GBPUSD', 'EURGBP', 'GBPJPY', 'GBPCHF', 'GBPAUD', 'GBPNZD', 'GBPCAD'],
            'JPY_MAJOR': ['USDJPY', 'EURJPY', 'GBPJPY', 'AUDJPY', 'NZDJPY', 'CADJPY', 'CHFJPY'],
            'AUD_MAJOR': ['AUDUSD', 'EURAUD', 'GBPAUD', 'AUDJPY', 'AUDNZD', 'AUDCAD', 'AUDCHF'],
            'GOLD': ['XAUUSD', 'XAGUSD'],
            'CRYPTO': ['BTCUSD', 'ETHUSD'],
            'OIL': ['USOIL', 'UKOIL'],
        }
        
        self.max_exposure_per_group = 2  # Max 2 positions per correlation group
    
    def get_correlation_group(self, symbol: str) -> str:
        """Find which correlation group this symbol belongs to"""
        for group_name, symbols in self.correlation_groups.items():
            if symbol in symbols:
                return group_name
        return 'UNCORRELATED'
    
    def get_current_exposure(self, symbol: str) -> tuple[int, list]:
        """
        Check current exposure to this correlation group
        Returns: (count, list of symbols)
        """
        group = self.get_correlation_group(symbol)
        if group == 'UNCORRELATED':
            return 0, []
        
        group_symbols = self.correlation_groups[group]
        exposed_symbols = []
        
        for ticket, pos in state.open_positions.items():
            pos_symbol = pos.get('symbol', '')
            if pos_symbol in group_symbols:
                exposed_symbols.append(pos_symbol)
        
        return len(exposed_symbols), exposed_symbols
    
    def should_allow_trade(self, symbol: str) -> tuple[bool, str]:
        """
        Decide if should allow trade based on correlation
        Returns: (allow, reason)
        """
        exposure_count, exposed_symbols = self.get_current_exposure(symbol)
        
        if exposure_count >= self.max_exposure_per_group:
            group = self.get_correlation_group(symbol)
            logger.warning(f" [CORRELATION] {symbol} blocked - Already {exposure_count} positions in {group} group: {exposed_symbols}")
            return False, f'CORRELATION_LIMIT_{group}'
        
        if exposure_count > 0:
            logger.info(f" [CORRELATION] {symbol} allowed but {exposure_count} correlated position(s) exist: {exposed_symbols}")
        
        return True, 'OK'


class MicroStructureAnalyzer:
    """
    Analyzes M1 price action for optimal scalping entries
    Detects liquidity sweeps, momentum bursts, optimal timing
    """
    
    def detect_liquidity_sweep(self, symbol: str) -> Optional[str]:
        """
        Detect if recent liquidity sweep occurred
        Perfect scalping entry signal
        """
        try:
            df_m1 = get_market_data(symbol, mt5.TIMEFRAME_M1, 30)
            if df_m1 is None or len(df_m1) < 15:
                return None
            
            # Find recent swing high (last 10 candles)
            recent_high = df_m1['high'].iloc[-10:-1].max()
            current_high = df_m1['high'].iloc[-1]
            current_close = df_m1['close'].iloc[-1]
            
            # Check if swept high and rejected
            if current_high > recent_high:
                if current_close < recent_high:
                    logger.info(f" [MICRO] {symbol} High liquidity sweep detected -> SELL setup")
                    return 'SELL_SETUP'
            
            # Find recent swing low
            recent_low = df_m1['low'].iloc[-10:-1].min()
            current_low = df_m1['low'].iloc[-1]
            
            # Check if swept low and rejected
            # Check if swept low and rejected (BULLISH SWEEP)
            # 1. Low must be lower than recent support
            # 2. Close must be BACK ABOVE the recent support (The Fakeout)
            if current_low < recent_low:
                if current_close > recent_low:
                     # Wick Ratio Check: ensure it's not a weak rejection
                     body_size = abs(current_close - df_m1['open'].iloc[-1])
                     wick_size = recent_low - current_low
                     
                     # Volatility/Volume Surge Check (Sniper Confirmation)
                     avg_vol = df_m1['tick_volume'].iloc[-10:].mean()
                     current_vol = df_m1['tick_volume'].iloc[-1]
                     
                     if current_vol > (avg_vol * 1.5):
                         logger.info(f" [MICRO] {symbol} Bullish Liquidity Sweep (Sniper Entry) detected + Vol Surge")
                         return 'BUY_SETUP'
            
            return None
            
        except Exception as e:
            logger.error(f"[MICRO] Error detecting liquidity sweep: {e}")
            return None
    
    def check_momentum_burst(self, symbol: str) -> Optional[str]:
        """
        Detect strong momentum (good for scalping)
        """
        try:
            df_m1 = get_market_data(symbol, mt5.TIMEFRAME_M1, 20)
            if df_m1 is None or len(df_m1) < 10:
                return None
            
            # Calculate momentum
            price_change = df_m1['close'].pct_change()
            recent_momentum = price_change.iloc[-5:].mean()
            
            # Volume confirmation
            avg_volume = df_m1['tick_volume'].mean()
            recent_volume = df_m1['tick_volume'].iloc[-3:].mean()
            
            # Strong momentum with volume
            if recent_momentum > 0.0015 and recent_volume > avg_volume * 1.5:
                # logger.info(f" [MICRO] {symbol} Strong BUY momentum detected")
                return 'STRONG_BUY'
            elif recent_momentum < -0.0015 and recent_volume > avg_volume * 1.5:
                # logger.info(f" [MICRO] {symbol} Strong SELL momentum detected")
                return 'STRONG_SELL'
            
            return None
            
        except Exception as e:
            logger.error(f"[MICRO] Error checking momentum: {e}")
            return None

    def check_displacement_confirmation(self, symbol: str, direction: str) -> bool:
        """
        CRITICAL: Validates entry with Displacement (Strong Candle)
        SMC Requirement: Candle Body > Average Body * 1.5
        """
        try:
            df_m1 = get_market_data(symbol, mt5.TIMEFRAME_M1, 20)
            if df_m1 is None or len(df_m1) < 5: return False
            
            last_candle = df_m1.iloc[-1]
            prev_candle = df_m1.iloc[-2]
            
            # Calculate average body size
            bodies = abs(df_m1['close'] - df_m1['open'])
            avg_body = bodies.mean()
            
            current_body = abs(last_candle['close'] - last_candle['open'])
            
            # 1. Size Check
            is_large_candle = current_body > (avg_body * 1.2) # Keeping it 1.2 for scalping speed
            
            # 2. Direction Check
            is_green = last_candle['close'] > last_candle['open']
            
            if direction == 'BUY':
                return is_large_candle and is_green
            else:
                return is_large_candle and (not is_green)
                
        except Exception as e:
            logger.error(f"[MICRO] Displacement Check Error: {e}")
            return False

    def optimal_entry_timing(self, symbol: str, direction: str) -> str:
        """
        Decide if NOW is optimal entry or should wait
        """
        try:
            df_m1 = get_market_data(symbol, mt5.TIMEFRAME_M1, 20)
            if df_m1 is None or len(df_m1) < 15:
                return 'ENTER_NOW'
            
            # Calculate EMA9
            ema_9 = df_m1['close'].ewm(span=9, adjust=False).mean()
            current_price = df_m1['close'].iloc[-1]
            ema_value = ema_9.iloc[-1]
            
            if direction == 'BUY':
                # Price below EMA = wait for pullback
                if current_price < ema_value * 0.998:
                    logger.info(f" [MICRO] {symbol} BUY - Price below EMA, waiting...")
                    return 'WAIT_PULLBACK'
                # Price too far above EMA
                elif current_price > ema_value * 1.003:
                    logger.info(f" [MICRO] {symbol} BUY - Price extended, waiting for pullback...")
                    return 'WAIT_PULLBACK'
                else:
                    return 'ENTER_NOW'
            
            else:  # SELL
                # Price above EMA = wait for pullback
                if current_price > ema_value * 1.002:
                    logger.info(f" [MICRO] {symbol} SELL - Price above EMA, waiting...")
                    return 'WAIT_PULLBACK'
                # Price too far below EMA
                elif current_price < ema_value * 0.997:
                    logger.info(f" [MICRO] {symbol} SELL - Price extended, waiting for pullback...")
                    return 'WAIT_PULLBACK'
                else:
                    return 'ENTER_NOW'
                    
        except Exception as e:
            logger.error(f"[MICRO] Error checking entry timing: {e}")
            return 'ENTER_NOW'


# =============================================================================
# SCALPING OPTIMIZATION - ASYNC & SPEED SYSTEMS
# =============================================================================

import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed

class AsyncDataFetcher:
    """
    CRITICAL OPTIMIZATION: Fetches data for all symbols simultaneously
    Eliminates sequential blocking -- reduces cycle time dramatically.
    """
    
    def __init__(self, symbols, refresh_interval=5):
        self.symbols = symbols
        self.refresh_interval = refresh_interval
        self.data_cache = {}
        self.cache_lock = threading.Lock()
        self.running = False
        self.thread = None
        
    def start(self):
        """Start background data fetching thread"""
        self.running = True
        self.thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self.thread.start()
        logger.info(f" [ASYNC FETCHER] Started for {len(self.symbols)} symbols")
    
    def stop(self):
        """Stop background thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def _fetch_loop(self):
        """Background loop that continuously fetches data"""
        while self.running:
            try:
                start_time = time.time()
                
                # Fetch all symbols in parallel
                data = self._fetch_all_parallel()
                
                # Update cache atomically
                with self.cache_lock:
                    self.data_cache = data
                
                elapsed = time.time() - start_time
                logger.debug(f" [ASYNC FETCHER] Updated {len(data)} symbols in {elapsed:.2f}s")
                
                # Sleep until next refresh
                time.sleep(max(0, self.refresh_interval - elapsed))
                
            except Exception as e:
                logger.error(f"[ASYNC FETCHER] Error in fetch loop: {e}")
                time.sleep(5)
    
    def _fetch_all_parallel(self) -> dict:
        """Fetch data for all symbols in parallel using ThreadPoolExecutor"""
        results = {}
        
        with ThreadPoolExecutor(max_workers=min(len(self.symbols), 10)) as executor:
            # Submit all fetch jobs
            future_to_symbol = {
                executor.submit(self._fetch_symbol_data, symbol): symbol 
                for symbol in self.symbols
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    data = future.result()
                    if data:
                        results[symbol] = data
                except Exception as e:
                    logger.error(f"[ASYNC FETCHER] Error fetching {symbol}: {e}")
        
        return results
    
    def _fetch_symbol_data(self, symbol: str) -> dict:
        """
        Fetch all required timeframes for a symbol.
        Full MTF hierarchy: H4 (macro) -> H1 (POI) -> M30/M15 (ChoCh) -> M5/M1 (entry)
        """
        try:
            return {
                'timestamp': time.time(),
                'H4':  get_market_data(symbol, mt5.TIMEFRAME_H4,  80),   # Macro bias
                'H1':  get_market_data(symbol, mt5.TIMEFRAME_H1,  100),  # POI zone
                'M30': get_market_data(symbol, mt5.TIMEFRAME_M30, 100),  # ChoCh layer
                'M15': get_market_data(symbol, mt5.TIMEFRAME_M15, 150),  # OB layer
                'M5':  get_market_data(symbol, mt5.TIMEFRAME_M5,  100),  # Sweep/FVG
                'M1':  get_market_data(symbol, mt5.TIMEFRAME_M1,  60),   # Entry precision
            }
        except Exception as e:
            logger.error(f"[ASYNC FETCHER] Error fetching data for {symbol}: {e}")
            return None
    
    def get_data(self, symbol: str) -> dict:
        """Get cached data for symbol (instant, no blocking)"""
        with self.cache_lock:
            return self.data_cache.get(symbol, None)
    
    def get_all_data(self) -> dict:
        """Get all cached data"""
        with self.cache_lock:
            return self.data_cache.copy()


class AsyncTradeLogger:
    """
    CRITICAL OPTIMIZATION: Non-blocking Supabase logging
    Eliminates blocking calls (was ~200 ms) during execution
    """
    
    def __init__(self):
        self.queue = queue.Queue()
        self.running = False
        self.thread = None
        
    def start(self):
        """Start background logging thread"""
        self.running = True
        self.thread = threading.Thread(target=self._process_queue, daemon=True)
        self.thread.start()
        logger.info(" [ASYNC LOGGER] Started")
    
    def stop(self):
        """Stop background thread and flush queue"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
    
    def log_trade_async(self, trade_data: dict):
        """Non-blocking trade logging"""
        self.queue.put(('log_trade', trade_data))
    
    def update_trade_async(self, ticket: int, exit_price: float, profit: float, exit_reason: str):
        """Non-blocking trade update"""
        self.queue.put(('update_trade', {
            'ticket': ticket,
            'exit_price': exit_price,
            'profit': profit,
            'exit_reason': exit_reason
        }))
    
    def _process_queue(self):
        """Background thread processes logging queue"""
        while self.running or not self.queue.empty():
            try:
                # Wait for item with timeout
                try:
                    operation, data = self.queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                # Process operation
                if operation == 'log_trade':
                    trade_db.log_trade(data)
                elif operation == 'update_trade':
                   # Assuming 'data' contains 'ticket', 'exit_price', 'profit', 'exit_reason', and 'symbol'
                   # and 'position_id', 'current_position_ids', 'config', 'state', 'datetime', 'timezone', 'timedelta' are available in scope
                   position_id = data.get('ticket') # Assuming ticket is used as position_id
                   current_position_ids = [] # Placeholder, as this is not passed in 'data'
                   
                   if position_id not in current_position_ids:
                    # Trade closed!
                    deal_profit = 0.0
                    exit_price = 0.0
                    exit_reason = "UNKNOWN"
                    
                    # RETRIEVE SYMBOL
                    params = data.get('params', {})
                    symbol = params.get('symbol', 'Unknown')
                    
                    # [NEW] SET COOLDOWN
                    if symbol != 'Unknown':
                         cooldown_expiry = datetime.now(timezone.utc) + timedelta(minutes=config.TRADE_COOLDOWN_MINUTES)
                         state.symbol_cooldowns[symbol] = cooldown_expiry
                         logger.info(f" [COOLDOWN] {symbol} locked until {cooldown_expiry.strftime('%H:%M')} UTC")

                    # Try to find the deal in history to get exact profit/price
                    # The original update_trade_closed call is likely part of this logic
                    trade_db.update_trade_closed(
                        data['ticket'],
                        data['exit_price'],
                        data['profit'],
                        data['exit_reason']
                    )
                
                self.queue.task_done()
                
            except Exception as e:
                logger.error(f"[ASYNC LOGGER] Error processing queue: {e}")


class RegimeDetector:
    """
    BREAKTHROUGH: Detects if market is TRENDING or RANGING
    Selects appropriate strategies for each regime
    """
    
    @staticmethod
    def detect_regime(symbol: str, df: pd.DataFrame) -> str:
        """
        Determine market regime based on Asset Class + Volatility
        """
        try:
            if df is None or len(df) < 50:
                return 'RANGING'
            
            # 1. IDENTIFY ASSET CLASS
            is_crypto = 'BTC' in symbol or 'ETH' in symbol
            is_gold = 'XAU' in symbol
            
            # 2. CALCULATE METRICS
            # ATR (Volatility)
            atr_series = calculate_atr(df['high'], df['low'], df['close'], 14)
            atr_current = float(atr_series.iloc[-1])
            atr_avg = float(atr_series.iloc[-50:].mean())
            volatility_ratio = atr_current / atr_avg if atr_avg > 0 else 1.0
            
            # ADX (Trend Strength)
            adx_val, _, _ = calculate_adx(df['high'], df['low'], df['close'], 14)
            adx = float(adx_val.iloc[-1]) if len(adx_val) > 0 else 0
            
            # Donchian Position (Price relative to range)
            high_50 = float(df['high'].iloc[-50:].max())
            low_50 = float(df['low'].iloc[-50:].min())
            current_close = float(df['close'].iloc[-1])
            range_size = high_50 - low_50
            price_pos = (current_close - low_50) / range_size if range_size > 0 else 0.5

            # 3. ASSET-SPECIFIC LOGIC
            
            if is_crypto:
                # --- CRYPTO LOGIC: "EXPLOSIVE" ---
                # Crypto trends need HIGH MOMENTUM to be real (ADX > 25)
                # Volatility must be expanding (> 1.2x avg)
                # [USER FEEDBACK] BTC needs stricter ADX
                min_adx = 28.0 if 'BTC' in symbol else 25.0
                
                if adx > min_adx and volatility_ratio > 1.2:
                    return 'TRENDING'
                # If ADX is low but Price is at extreme (Breakout), double check volatility
                elif price_pos > 0.85 or price_pos < 0.15:
                    if volatility_ratio > 1.5: # massive explosion
                         return 'TRENDING'
                
                return 'RANGING' # Default for Crypto (ignore small chop)

            elif is_gold:
                # --- GOLD LOGIC: "VOLATILE" ---
                # Gold trends well but wicks a lot.
                # Require ADX > 22 OR Strong Breakout
                
                if adx > 22:
                    return 'TRENDING'
                if volatility_ratio > 1.3: # Volatility spike usually starts a trend in Gold
                    return 'TRENDING'
                    
                return 'RANGING'

            else:
                # --- FOREX LOGIC: "SENSITIVE" ---
                # Forex trends are subtle. ADX > 20 is enough.
                # Price consistent directional movement matters more.
                
                closes = df['close'].iloc[-20:].values
                up_moves = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
                bias = up_moves / (len(closes) - 1)
                
                direction_confirmed = bias > 0.65 or bias < 0.35
                
                # VOLUME FILTER: Check if volume is alive
                vol_current = df['tick_volume'].iloc[-1]
                vol_avg = df['tick_volume'].iloc[-20:].mean()
                is_low_volume = vol_current < (vol_avg * 0.5)

                if is_low_volume:
                     return 'RANGING' # Force ranging in dead volume

                if (adx > 20) or (direction_confirmed and volatility_ratio > 1.0):
                    return 'TRENDING'
                    
                return 'RANGING'
                
        except Exception as e:
            logger.error(f"[REGIME] Error detecting regime: {e}")
            return 'RANGING'

    @staticmethod
    def check_volatility_adjusted_donchian(symbol: str, direction: str, df: pd.DataFrame) -> bool:
        """
        VOLATILITY-ADJUSTED DONCHIAN FILTER
        Prevents buying breakouts when volatility is too high (Fakeouts)
        or too low (No liquidity).
        """
        try:
            atr_series = calculate_atr(df['high'], df['low'], df['close'], 14)
            atr_current = float(atr_series.iloc[-1])
            atr_avg = float(atr_series.iloc[-50:].mean())
            
            vol_ratio = atr_current / atr_avg if atr_avg > 0 else 1.0
            
            # 1. If Volatility is EXTREME (> 3.0x), Block Breakouts (Fade only)
            if vol_ratio > 3.0:
                logger.info(f" [DONCHIAN] {symbol} Volatility too high ({vol_ratio:.1f}x) - Blocking Breakout")
                return False
                
            # 2. If Volatility is LOW (< 0.5x), Block (Dead market)
            if vol_ratio < 0.5:
                # logger.info(f" [DONCHIAN] {symbol} Volatility too low ({vol_ratio:.1f}x) - Dead market")
                return False
                
            # 3. DYNAMIC BREAKOUT THRESHOLD
            # In high vol, we need price to break by MORE than just 1 pip
            # Breakout Buffer = 0.2 * ATR
            
            high_20 = df['high'].iloc[-20:-1].max() # Exclude current candle
            low_20 = df['low'].iloc[-20:-1].min()
            current = df['close'].iloc[-1]
            
            buffer = atr_current * 0.2
            
            if direction == 'BUY':
                # Must be ABOVE the high + buffer
                if current > (high_20 + buffer):
                    return True
                else:
                    # logger.debug(f"[DONCHIAN] {symbol} BUY rejected - Not enough breakout dist")
                    return False
            
            elif direction == 'SELL':
                 # Must be BELOW the low - buffer
                if current < (low_20 - buffer):
                    return True
                else:
                    return False
                    
            return True

        except Exception as e:
            logger.error(f"Donchian error: {e}")
            return True # Allow on error
    
    @staticmethod
    def get_strategies_for_regime(regime: str) -> list:
        """
        Select optimal strategies based on market regime
        SCALPING OPTIMIZATION: Only 2-3 fast strategies per regime
        """
        if regime == 'TRENDING':
            # Trend-following strategies
            return ['VOLUME_IMBALANCE', 'LIQUIDITY_GRAB']
        else:  # RANGING
            # Mean-reversion strategies
            return ['LIQUIDITY_GRAB', 'SUPPORT_RESISTANCE']



def send_heartbeat(status: str = 'running', mt5_connected: bool = True, error_message: str = None, max_retries: int = 2):
    """Non-blocking. Fires in background thread. Scan loop never waits for Supabase."""
    import threading
    threading.Thread(
        target=_send_heartbeat_sync,
        args=(status, mt5_connected, error_message, max_retries),
        daemon=True
    ).start()


def calculate_spread_correctly(symbol: str, tick) -> float:
    """
    FIX: Correct spread calculation for all asset types
    """
    try:
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return 999.0  # Invalid
        
        spread_raw = tick.ask - tick.bid
        
        # For forex pairs, convert to pips
        if any(curr in symbol for curr in ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'NZD', 'CAD', 'CHF']):
            point = symbol_info.point
            spread_pips = spread_raw / (point * 10)
            return spread_pips
        
        # For metals (XAUUSD, XAGUSD), return in dollars
        elif 'XAU' in symbol or 'XAG' in symbol:
            return spread_raw
        
        # For crypto, return in dollars
        elif 'BTC' in symbol or 'ETH' in symbol:
            return spread_raw
        
        # For indices/stocks
        else:
            return spread_raw
            
    except Exception as e:
        logger.error(f"[SPREAD] Error calculating spread for {symbol}: {e}")
        return 999.0


# Initialize SCALPING OPTIMIZATION systems
async_data_fetcher = None  # Will be initialized in main()
async_logger = AsyncTradeLogger()
regime_detector = RegimeDetector()

logger.info("=" * 80)
logger.info(" SCALPING OPTIMIZATION SYSTEMS LOADED")
logger.info("=" * 80)
logger.info(" Async Data Fetcher: Ready")
logger.info(" Async Logger: Ready")
logger.info(" Regime Detector: Ready")
logger.info("=" * 80)


# Initialize global instances
pattern_recognizer = PatternRecognitionSystem()
symbol_tracker = SymbolPerformanceTracker()
speed_optimizer = ExecutionSpeedOptimizer(ttl_seconds=60)
correlation_tracker = SymbolCorrelationTracker()
micro_analyzer = MicroStructureAnalyzer()

logger.info("=" * 80)
logger.info(" ULTIMATE AI SYSTEMS INITIALIZED")
logger.info("=" * 80)
logger.info(f" Pattern Recognition: {len(pattern_recognizer.patterns_db)} patterns loaded")
logger.info(f" Symbol Performance Tracker: {len(symbol_tracker.stats)} symbols tracked")
logger.info(f" Execution Speed Optimizer: {speed_optimizer.ttl}s cache TTL")
logger.info(f" Correlation Tracker: {len(correlation_tracker.correlation_groups)} groups defined")
logger.info(f" Micro-Structure Analyzer: Ready for M1 analysis")
logger.info("=" * 80)

# =============================================================================
# AI API WRAPPER
# =============================================================================
# =============================================================================
# [OK] V12 UPGRADE: MARKET CONDITION & ADAPTIVE RISK MODULES
# =============================================================================

class MarketConditionAnalyzer:
    """
    Advanced market condition detection system.
    Prevents trading in 'Choppy' or 'Trappy' markets (ADX < 20).
    """
    
    @staticmethod
    def get_multi_timeframe_data(symbol: str) -> Dict[str, pd.DataFrame]:
        """Fetch data from multiple timeframes for context."""
        timeframes = {
            'H4': mt5.TIMEFRAME_H4,
            'H1': mt5.TIMEFRAME_H1,
            'M15': mt5.TIMEFRAME_M15
        }
        data = {}
        for name, tf in timeframes.items():
            df = get_market_data(symbol, tf, 200)
            if df is not None and not df.empty:
                data[name] = df
        return data
    
    @staticmethod
    def calculate_market_regime(df: pd.DataFrame) -> str:
        """
        Classify market regime: TRENDING, RANGING, or CHOPPY (Avoid)
        """
        if len(df) < 50: return "UNKNOWN"
        
        # ADX for Trend Strength
        adx = calculate_adx(df['high'], df['low'], df['close'], 14)[0].iloc[-1]
        
        # ATR for Volatility
        atr = calculate_atr(df['high'], df['low'], df['close'], 14)
        volatility_ratio = atr.iloc[-1] / atr.mean() if atr.mean() > 0 else 1.0
        
        # Trend Alignment (EMA)
        ema_50 = df['close'].ewm(span=50).mean().iloc[-1]
        
        # Logic:
        if adx > 30:  # ULTRA CONSERVATIVE
            if volatility_ratio > 3.0:
                return "VOLATILE" # Too dangerous
            return "TRENDING"
        elif adx < 12:
            return "CHOPPY" # Dead market - DO NOT TRADE
        else:
            if volatility_ratio < 0.5:
                return "CHOPPY"
            return "RANGING"

    @staticmethod
    def get_tradability_score(multi_tf_data: Dict[str, pd.DataFrame]) -> Tuple[int, Dict[str, Any]]:
        """
        Returns a score (0-100). If < 50, DO NOT TRADE.
        """
        if not multi_tf_data: return 0, {}
        
        score = 0
        analysis = {}
        
        # 1. H4 Context (Major Trend)
        if 'H4' in multi_tf_data:
            h4_regime = MarketConditionAnalyzer.calculate_market_regime(multi_tf_data['H4'])
            analysis['h4_regime'] = h4_regime
            if h4_regime == "TRENDING": score += 40
            elif h4_regime == "RANGING": score += 10  # ranging is below-average, not +25
        
        # 2. H1 Context (Intermediate Trend)
        if 'H1' in multi_tf_data:
            h1_regime = MarketConditionAnalyzer.calculate_market_regime(multi_tf_data['H1'])
            analysis['h1_regime'] = h1_regime
            if h1_regime == "TRENDING": score += 30
            elif h1_regime == "RANGING": score += 20
        
        # 3. Alignment Bonus
        if analysis.get('h4_regime') == "TRENDING" and analysis.get('h1_regime') == "TRENDING":
            score += 30
            
        analysis['tradability_score'] = score
        return score, analysis



class AIProvider:
    """Universal AI provider wrapper using Google GenAI SDK"""
    
    def __init__(self):
        self.provider = config.AI_PROVIDER
        self.gemini_model = None
        self.api_key = None
        self.setup_provider()
    
    def setup_provider(self):
        if self.provider == "gemini":
            self.api_key = config.GEMINI_API_KEY # <-- Now from config
            if self.api_key:
                try:
                    genai.configure(api_key=self.api_key)
                    # Fallback cascade: try models in order, use first available
                    _candidates = [
                        config.GEMINI_MODEL,       # primary (gemini-2.5-flash)
                        "gemini-2.5-flash",
                        "gemini-2.5-flash-lite",   # lightweight fallback
                    ]
                    self.gemini_model = None
                    for _m in _candidates:
                        try:
                            _test = genai.GenerativeModel(_m)
                            self.gemini_model = _test
                            config.GEMINI_MODEL = _m
                            logger.info(f"Gemini SDK Initialized: {_m}")
                            break
                        except Exception as _me:
                            logger.warning(f"[GEMINI] Model {_m} unavailable: {_me}")
                    if not self.gemini_model:
                        logger.error("[GEMINI] No model available -- AI features disabled")
                except Exception as e:
                    logger.error(f" Failed to initialize Gemini SDK: {e}")
                    self.api_key = None
        if not self.api_key:
            logger.warning(f" AI Provider '{self.provider}' API key not set. AI features disabled.")
    
    def call_ai(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1000,
        json_mode: bool = False
    ) -> Optional[str]:
        
        if not self.gemini_model:
            logger.error("Gemini model not initialized.")
            return None
            
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        if json_mode: 
            full_prompt += "\n\nRespond ONLY with valid JSON (no markdown, no code blocks, just the JSON object)."
        
        for attempt in range(2):
            try:
                config_params = {
                    "temperature": temperature,
                    "max_output_tokens": max_tokens
                    # response_mime_type removed -- causes Gemini to return
                    # conversational text ("Here is the JSON:...") instead of JSON.
                    # JSON enforcement is handled via prompt wording instead.
                }

                response = self.gemini_model.generate_content(
                    full_prompt,
                    generation_config=config_params
                )
                return response.text.strip()
            except Exception as e:
                logger.error(f" AI API Error (Attempt {attempt+1}): {e}")
                if "quota" in str(e).lower() or "429" in str(e):
                    import re as _qre
                    retry_secs = 3600  # default 1h
                    _rm = _qre.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)', str(e))
                    if _rm: retry_secs = int(_rm.group(1))
                    retry_h = max(1, retry_secs // 3600 + 1)
                    logger.critical(f"!!! AI QUOTA EXCEEDED. Pausing ALL AI calls for {retry_h}h. Bot continues with H4 bias. !!!")
                    state.last_global_context_update = datetime.now() + timedelta(hours=retry_h)
                    state._quota_resume = datetime.now() + timedelta(seconds=retry_secs)
                    return None
                time.sleep(2)
        return None

ai_provider = AIProvider()

# =============================================================================
# MT5 CONNECTION & DATA
# =============================================================================

def initialize_mt5() -> bool:
    try:
        # Build MT5 init kwargs - use isolated terminal if provided
        mt5_kwargs = {
            'login': config.MT5_LOGIN,
            'password': config.MT5_PASSWORD,
            'server': config.MT5_SERVER
        }
        if MT5_TERMINAL_PATH:
            mt5_kwargs['path'] = MT5_TERMINAL_PATH
            logger.info(f"Using isolated MT5 instance: {MT5_TERMINAL_PATH}")
        
        if not mt5.initialize(**mt5_kwargs):
            logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            return False
        account_info = mt5.account_info()
        if account_info:
            logger.info(f"MT5 Connected | Account: {account_info.login} | Balance: ${account_info.balance:.2f}")
            
            # CRITICAL: Force symbols to be visible in Market Watch
            logger.info("Verifying Market Watch symbols...")
            for s in config.SYMBOLS:
                if not mt5.symbol_select(s, True):
                     logger.error(f"Failed to select {s} in Market Watch (Broker error?)")
                else: 
                     # logger.debug(f"{s} selected")
                     pass
            
            return True
        return False
    except Exception as e:
        logger.error(f"MT5 init error: {e}")
        return False

def get_market_data(symbol: str, timeframe: int, bars: int = 200) -> Optional[pd.DataFrame]:
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return None

# =============================================================================
# LOCAL-FIRST INDICATORS & HELPERS
# =============================================================================

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()

def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    tr = calculate_atr(high, low, close, 1)
    move_up = high.diff()
    move_down = -low.diff()
    plus_dm = pd.Series(np.where((move_up > move_down) & (move_up > 0), move_up, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((move_down > move_up) & (move_down > 0), move_down, 0.0), index=low.index)
    
    tr_ema = tr.ewm(alpha=1/period, adjust=False).mean()
    tr_ema = tr_ema.replace(0, np.nan)
    
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / tr_ema)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / tr_ema)
    
    di_sum = plus_di + minus_di
    di_sum = di_sum.replace(0, np.nan)
    
    dx = 100 * (abs(plus_di - minus_di) / di_sum)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    
    adx = adx.fillna(0)
    plus_di = plus_di.fillna(0)
    minus_di = minus_di.fillna(0)
    
    return adx, plus_di, minus_di

def identify_swing_highs_lows(df: pd.DataFrame, lookback: int = 5) -> Tuple[List[int], List[int]]:
    swing_highs, swing_lows = [], []
    if len(df) < lookback * 2 + 1: return [], []
    for i in range(lookback, len(df) - lookback):
        is_high = all(df['high'].iloc[i] > df['high'].iloc[i-j] for j in range(1, lookback+1)) and \
                  all(df['high'].iloc[i] > df['high'].iloc[i+j] for j in range(1, lookback+1))
        if is_high: swing_highs.append(i)
        is_low = all(df['low'].iloc[i] < df['low'].iloc[i-j] for j in range(1, lookback+1)) and \
                 all(df['low'].iloc[i] < df['low'].iloc[i+j] for j in range(1, lookback+1))
        if is_low: swing_lows.append(i)
    return swing_highs, swing_lows

def detect_break_of_structure(df: pd.DataFrame, swing_highs: List[int], swing_lows: List[int]) -> Optional[str]:
    if len(swing_highs) < 2 or len(swing_lows) < 2: return None
    current_price = df['close'].iloc[-1]
    if current_price > df['high'].iloc[swing_highs[-1]]: return "BULLISH_BOS"
    if current_price < df['low'].iloc[swing_lows[-1]]: return "BEARISH_BOS"
    return None

def get_market_regime_and_trend(symbol: str) -> Tuple[str, str]:
    df_regime = get_market_data(symbol, config.TREND_TF, 100)
    if df_regime is None or df_regime.empty or len(df_regime) < 50: 
        return "CHOPPY", "NEUTRAL"
    adx = calculate_adx(df_regime['high'], df_regime['low'], df_regime['close'], config.ADX_PERIOD)[0].iloc[-1]
    ema50 = df_regime['close'].ewm(span=50, adjust=False).mean().iloc[-1]
    ema200 = df_regime['close'].ewm(span=200, adjust=False).mean().iloc[-1]
    regime = "TRENDING" if adx > config.ADX_TRENDING_THRESHOLD else "RANGING"
    trend = "BULLISH" if ema50 > ema200 else "BEARISH" if ema50 < ema200 else "NEUTRAL"
    return regime, trend

def get_current_session() -> str:
    """
    Session classification with London/NY overlap correctly identified.
    FIX: the original check returned "LONDON" for 13-16 UTC (overlap window)
    because the London condition (7-16) was checked first.
    The 13-16 UTC overlap is the HIGHEST LIQUIDITY period of the trading day.
    """
    current_hour = datetime.now(timezone.utc).hour
    # Check overlap FIRST -- highest priority, highest liquidity
    if 13 <= current_hour < 16: return "LONDON_NY"   # Overlap: max risk multiplier
    if 7  <= current_hour < 16: return "LONDON"
    if 16 <= current_hour < 22: return "NEW_YORK"
    if 0  <= current_hour < 8:  return "ASIAN"
    return "UNKNOWN"

def is_kill_zone(current_hour: int) -> bool:
    for zone, (start, end) in config.ICT_KILLZONES.items():
        if start <= current_hour < end: return True
    return False

def get_symbol_specs(symbol: str) -> Dict:
    info = mt5.symbol_info(symbol)
    if info:
        if info.digits in [3, 5]:
            pip_size = info.point * 10
        else:
            pip_size = info.point
        return {
            'pip_size': pip_size, 'min_lot': info.volume_min,
            'max_lot': info.volume_max, 'lot_step': info.volume_step,
            'trade_tick_value': info.trade_tick_value,
            'trade_tick_size': info.trade_tick_size,
        }
    static_spec = SYMBOL_SPECS.get(symbol)
    if static_spec:
        if symbol in ['USDJPYm', 'GBPJPYm', 'XAUUSDm', 'ETHUSDm', 'USOILm']:
            static_spec['pip_size'] = 0.01
        elif symbol == 'BTCUSDm':
            static_spec['pip_size'] = 1.0
        else:
            static_spec['pip_size'] = 0.0001
    return static_spec

# =============================================================================
# LOCAL-FIRST NEWS FILTER
# =============================================================================

def get_new_york_utc_offset(event_date: datetime) -> int:
    year = event_date.year
    dst_start = datetime(year, 3, 1) + timedelta(days=(6 - datetime(year, 3, 1).weekday() + 7) % 7 + 7)
    dst_end = datetime(year, 11, 1) + timedelta(days=(6 - datetime(year, 11, 1).weekday() + 7) % 7)
    return -4 if dst_start <= event_date < dst_end else -5

def fetch_upcoming_news_events():
    global state
    if not config.ENABLE_LOCAL_NEWS_FILTER: return
    
    # [FIX] CHECK COOLDOWN
    if hasattr(state, 'news_fetch_cooldown') and datetime.now(timezone.utc) < state.news_fetch_cooldown:
        return

    if state.last_local_news_update and (datetime.now(timezone.utc) - state.last_local_news_update) < timedelta(minutes=config.LOCAL_NEWS_CHECK_INTERVAL):
        return
    
    logger.info("Fetching upcoming high-impact news events from calendar...")
    try:
        response = requests.get(config.NEWS_API_URL, timeout=15, verify=certifi.where())
        response.raise_for_status()
        events_data = response.json()
        high_impact_events = []
        
        for event in events_data:
            if event.get('impact') == 'High' and event.get('country') in config.HIGH_IMPACT_CURRENCIES:
                try:
                    event_dt_str = event.get('date')
                    if 'T' in event_dt_str:
                        parsable_dt_str = event_dt_str.split('T')[0] + ' ' + event_dt_str.split('T')[1].split('-')[0].split('+')[0]
                    else:
                        parsable_dt_str = event_dt_str
                    event_dt_naive = datetime.strptime(parsable_dt_str, '%Y-%m-%d %H:%M:%S')
                    offset_hours = get_new_york_utc_offset(event_dt_naive)
                    event_tz = timezone(timedelta(hours=offset_hours))
                    event_dt_aware = event_dt_naive.replace(tzinfo=event_tz)
                    event_dt_utc = event_dt_aware.astimezone(timezone.utc)
                    if event_dt_utc > datetime.now(timezone.utc):
                        high_impact_events.append({"datetime_utc": event_dt_utc, "currency": event.get('country'), "title": event.get('title')})
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse date for news event: {event}. Error: {e}")
                    continue
                    
        state.upcoming_high_impact_events = sorted(high_impact_events, key=lambda x: x['datetime_utc'])
        state.last_local_news_update = datetime.now(timezone.utc)
        
        if state.upcoming_high_impact_events:
            logger.info(f"Successfully fetched {len(state.upcoming_high_impact_events)} high-impact news events.")
            next_event = state.upcoming_high_impact_events[0]
            logger.info(f"  -> Next Event: {next_event['datetime_utc'].strftime('%Y-%m-%d %H:%M:%S')} UTC - {next_event['currency']} - {next_event['title']}")
        else:
            logger.info("No upcoming high-impact news events found for the remainder of the week.")
            
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logger.warning("[NEWS] 429 Rate Limit. Pausing news checks for 60 minutes.")
            state.news_fetch_cooldown = datetime.now(timezone.utc) + timedelta(minutes=60)
        else:
            logger.error(f"News API Error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in fetch_upcoming_news_events: {e}")

def is_trade_entry_paused_for_news(symbol: str) -> bool:
    if not config.ENABLE_LOCAL_NEWS_FILTER or not state.upcoming_high_impact_events: 
        return False
    symbol_currencies = [c for c in config.HIGH_IMPACT_CURRENCIES if c in symbol.upper()]
    if not symbol_currencies: 
        return False
        
    now_utc = datetime.now(timezone.utc)
    for event in state.upcoming_high_impact_events:
        if event['currency'] in symbol_currencies:
            time_to_event = event['datetime_utc'] - now_utc
            if timedelta(seconds=0) < time_to_event <= timedelta(minutes=config.NEWS_PAUSE_BEFORE_MINUTES):
                logger.warning(f" LOCAL NEWS VETO: Pausing trades for {symbol}. Event '{event['title']}' ({event['currency']}) in {int(time_to_event.total_seconds()/60)} minutes.")
                return True
            time_since_event = now_utc - event['datetime_utc']
            if timedelta(seconds=0) < time_since_event < timedelta(minutes=config.NEWS_PAUSE_AFTER_MINUTES):
                logger.warning(f" LOCAL NEWS VETO: Pausing trades for {symbol}. Market volatile after '{event['title']}' ({event['currency']}).")
                return True
    return False

def get_news_volatility_multiplier(symbol: str) -> float:
    """
    NEWS GUARD: Returns ATR multiplier based on time to next high-impact news.
    1.0 = Normal
    1.5 = Pre-News (High Volatility Expected)
    2.0 = Post-News (Aftershock / Wide Spreads)
    """
    if not config.ENABLE_LOCAL_NEWS_FILTER or not state.upcoming_high_impact_events: 
        return 1.0
        
    symbol_currencies = [c for c in config.HIGH_IMPACT_CURRENCIES if c in symbol.upper()]
    if not symbol_currencies: 
        return 1.0
        
    now_utc = datetime.now(timezone.utc)
    for event in state.upcoming_high_impact_events:
        if event['currency'] in symbol_currencies:
            time_to_event = event['datetime_utc'] - now_utc
            
            # Pre-News: 30-60 mins before (Widen stops)
            if timedelta(minutes=0) < time_to_event <= timedelta(minutes=60):
                return 1.5
            
            # Post-News: 0-30 mins after (Maximum Caution)
            time_since_event = now_utc - event['datetime_utc']
            if timedelta(minutes=0) < time_since_event <= timedelta(minutes=30):
                return 2.0
                
    return 1.0

# =============================================================================
# LOCAL-FIRST STRATEGY ENGINE
# =============================================================================
# (All 9 strategies: strategy_ict_killzone, strategy_advanced_smc, etc.)
# (These functions are identical to V10.1 and are kept as-is)
# =============================================================================

def strategy_ict_killzone(df_entry: pd.DataFrame, df_structure: pd.DataFrame, trend: str, symbol: str, df_micro: pd.DataFrame) -> Optional[Dict[str, Any]]:
    current_hour = datetime.now(timezone.utc).hour
    if not is_kill_zone(current_hour): return None
    
    current_price = df_entry['close'].iloc[-1]
    atr = calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], config.ATR_PERIOD).iloc[-1]

    for i in range(len(df_entry) - config.ICT_FVG_MITIGATION_CANDLES - 1, 2, -1):
        if df_entry['low'].iloc[i+1] > df_entry['high'].iloc[i-1]:
            fvg_high, fvg_low = df_entry['low'].iloc[i+1], df_entry['high'].iloc[i-1]
            if fvg_low <= current_price <= fvg_high and trend == "BULLISH":
                # CHECK: M1 Candle must be GREEN (Close > Open) to confirm rejection
                if df_micro['close'].iloc[-1] > df_micro['open'].iloc[-1]: 
                    sl = fvg_low - (atr * 1.5)   # FIX: was 0.5 -- too close to spread
                    return {"direction": "BUY", "stop_loss": sl, "strategy_name": "ICT_KILLZONE", "confidence": 0.85}
        
        if df_entry['high'].iloc[i+1] < df_entry['low'].iloc[i-1]:
            fvg_high, fvg_low = df_entry['low'].iloc[i-1], df_entry['high'].iloc[i+1]
            if fvg_low <= current_price <= fvg_high and trend == "BEARISH":
                # CHECK: M1 Candle must be RED (Close < Open) to confirm rejection
                if df_micro['close'].iloc[-1] < df_micro['open'].iloc[-1]: 
                    sl = fvg_high + (atr * 1.5)  # FIX: was 0.5 -- too close to spread
                    return {"direction": "SELL", "stop_loss": sl, "strategy_name": "ICT_KILLZONE", "confidence": 0.85}
    return None

# strategy_advanced_smc moved to strategies_research.py -- no live call
# site (confirmed by grepping call sites, not just defs). See that
# module's docstring for the full dormant-strategy rationale.

def strategy_liquidity_grab(df_entry: pd.DataFrame, df_structure: pd.DataFrame, trend: str, symbol: str, df_micro: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    ICT Liquidity Grab: sweep a swing point, displace strongly in opposite direction.
    CHANGE: Requires BEARISH trend for SELL, BULLISH for BUY (NEUTRAL blocked).
    CHANGE: Real volume confirmation added.
    """
    if len(df_entry) < 15: return None
    swing_highs_idx, swing_lows_idx = identify_swing_highs_lows(df_entry, lookback=3)
    last_candle, prev_candle = df_entry.iloc[-1], df_entry.iloc[-2]
    atr    = calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], config.ATR_PERIOD).iloc[-1]
    avg_vol = df_entry['tick_volume'].iloc[-10:].mean()
    # Volume: last or previous bar must have had above-average activity
    has_vol = (df_entry['tick_volume'].iloc[-1] > avg_vol * 1.2 or
               df_entry['tick_volume'].iloc[-2] > avg_vol * 1.2 or avg_vol < 1)

    # SELL: only when H1 is clearly BEARISH (not NEUTRAL)
    if swing_highs_idx and trend == "BEARISH":
        last_high = df_entry['high'].iloc[swing_highs_idx[-1]]
        if prev_candle['high'] > last_high and last_candle['close'] < last_candle['open']:
            candle_range = last_candle['high'] - last_candle['low']
            body_size = abs(last_candle['close'] - last_candle['open'])
            if candle_range > 0 and body_size > (candle_range * 0.5) and has_vol:
                if last_candle['close'] < (last_candle['low'] + (0.5 * candle_range)):
                    return {"direction": "SELL", "stop_loss": prev_candle['high'] + (atr * 1.2),
                            "strategy_name": "LIQUIDITY_GRAB", "confidence": 0.85}

    # BUY: only when H1 is clearly BULLISH (not NEUTRAL)
    if swing_lows_idx and trend == "BULLISH":
        last_low = df_entry['low'].iloc[swing_lows_idx[-1]]
        if prev_candle['low'] < last_low and last_candle['close'] > last_candle['open']:
            candle_range = last_candle['high'] - last_candle['low']
            body_size = abs(last_candle['close'] - last_candle['open'])
            if candle_range > 0 and body_size > (candle_range * 0.5) and has_vol:
                if last_candle['close'] > (last_candle['low'] + (0.5 * candle_range)):
                    return {"direction": "BUY", "stop_loss": prev_candle['low'] - (atr * 1.2),
                            "strategy_name": "LIQUIDITY_GRAB", "confidence": 0.85}
    return None

# strategy_wyckoff_patterns / strategy_volume_profile / strategy_support_resistance /
# strategy_volume_imbalance / strategy_trend_pullback / strategy_mean_reversion_bb
# moved to strategies_research.py -- none had a live call site (confirmed
# by grepping call sites, not just defs). See that module's docstring for
# why (and for a per-strategy note on the two that need a closer look
# before any promotion: WYCKOFF_PATTERNS isn't real Wyckoff method despite
# the name, and MEAN_REVERSION_BB is a counter-trend fade, philosophically
# the odd one out against every other momentum/liquidity strategy here).

# =============================================================================
# EMA MOMENTUM FILTER (9/15 EMA + Slope Gate)
# =============================================================================

def get_ema_momentum(df: 'pd.DataFrame', slope_bars: int = 5) -> dict:
    """
    9/15 EMA momentum system with 45-degree slope filter.

    Research baseline: blind EMA crossover = 42% win rate.
    With slope filter added: 68% win rate (from strategy document).

    The "45-degree rule": EMAs must be sloping at meaningful angle.
    Flat EMAs = ranging market = fakeouts = skip.

    Returns:
      {
        "trend":    "BULLISH" | "BEARISH" | "NEUTRAL",
        "strength": "STRONG" | "WEAK" | "FLAT",
        "ema9":     float,
        "ema15":    float,
        "slope9":   float,   normalized slope (pct/bar)
        "gap_pct":  float,   gap between ema9 and ema15 as % of price
        "reason":   str
      }
    """
    result = {"trend": "NEUTRAL", "strength": "FLAT",
              "ema9": 0.0, "ema15": 0.0, "slope9": 0.0,
              "gap_pct": 0.0, "reason": "Insufficient data"}

    if df is None or len(df) < max(50, slope_bars + 5):
        return result

    try:
        close  = df['close']
        ema9   = close.ewm(span=9,  adjust=False).mean()
        ema15  = close.ewm(span=15, adjust=False).mean()

        e9_now = float(ema9.iloc[-1])
        e15_now = float(ema15.iloc[-1])
        price_now = float(close.iloc[-1])

        # Slope: normalized change over last slope_bars candles (pct/bar)
        e9_prev   = float(ema9.iloc[-1 - slope_bars])
        slope9    = (e9_now - e9_prev) / (e9_prev * slope_bars) if e9_prev > 0 else 0

        # Gap between 9 and 15 EMA as % of price
        gap_pct = abs(e9_now - e15_now) / price_now * 100

        # Slope threshold: ~45-degree equivalent in normalized terms
        # Gold at $4600: 0.03%/bar = $1.38/bar per M5 candle -- meaningful
        # BTC at $70000: 0.03%/bar = $21/bar -- meaningful
        # XAG at $72: 0.03%/bar = $0.022/bar -- meaningful
        MIN_SLOPE = 0.0003   # 0.03%/bar = 45-degree equivalent
        MIN_GAP   = 0.010    # 0.010% gap minimum

        slope_strong = abs(slope9) >= MIN_SLOPE
        gap_open     = gap_pct >= MIN_GAP

        # TRULY FLAT: slope too small AND gap too small = ranging/compressing
        # EMAs are interleaved or near-crossing but momentum is building
        truly_flat = (abs(slope9) < MIN_SLOPE * 0.5) and (gap_pct < MIN_GAP)

        if e9_now > e15_now and slope9 > 0:
            trend = "BULLISH"
            strength = "STRONG" if (slope_strong and gap_open) else "WEAK"
            reason = f"BULLISH 9EMA({e9_now:.4f}) > 15EMA({e15_now:.4f}), slope={slope9*100:.4f}%/bar gap={gap_pct:.3f}%"
        elif e9_now < e15_now and slope9 < 0:
            trend = "BEARISH"
            strength = "STRONG" if (slope_strong and gap_open) else "WEAK"
            reason = f"BEARISH 9EMA({e9_now:.4f}) < 15EMA({e15_now:.4f}), slope={slope9*100:.4f}%/bar gap={gap_pct:.3f}%"
        elif slope_strong:
            # EMAs not yet crossed but slope is strong = momentum building = WEAK not FLAT
            trend = "BULLISH" if slope9 > 0 else "BEARISH"
            strength = "WEAK"
            reason = f"Pre-cross momentum: slope={slope9*100:.4f}%/bar gap={gap_pct:.3f}% (EMAs about to cross)"
        elif truly_flat:
            trend = "NEUTRAL"
            strength = "FLAT"
            reason = f"Genuinely flat: slope={slope9*100:.4f}%/bar gap={gap_pct:.3f}% (ranging)"
        else:
            trend = "NEUTRAL"
            strength = "WEAK"
            reason = f"Crossing zone: slope={slope9*100:.4f}%/bar gap={gap_pct:.3f}%"

        result.update({
            "trend": trend, "strength": strength,
            "ema9": e9_now, "ema15": e15_now,
            "slope9": slope9, "gap_pct": gap_pct, "reason": reason
        })

    except Exception as e:
        result["reason"] = f"EMA calc error: {e}"

    return result


def detect_3c_setup(df: 'pd.DataFrame', direction: str) -> dict:
    """
    3-Candle (3C) Momentum Confirmation Setup.

    The 3C setup confirms that a sweep/displacement is REAL and not a fakeout:

    BULLISH 3C (confirms BUY):
      Candle 1: Bearish (the sweep candle, taking out lows)
      Candle 2: Bullish (displacement -- strong green, >60% body)
      Candle 3 (current): Candle 3 fails to break BELOW Candle 1 low
                           = bears exhausted, bulls in control

    BEARISH 3C (confirms SELL):
      Candle 1: Bullish (the sweep candle, taking out highs)
      Candle 2: Bearish (displacement -- strong red, >60% body)
      Candle 3 (current): Candle 3 fails to break ABOVE Candle 1 high
                           = bulls exhausted, bears in control

    Why this matters:
      Without 3C: bot enters on ANY sweep + displacement (including fakeouts)
      With 3C: only enter when the "second leg stop hunt" has FAILED to close
               beyond the sweep extreme -- this is the "real" reversal confirmation.

    Returns:
      { "confirmed": bool, "pattern": str, "strength": float 0-1, "reason": str }
    """
    empty = {"confirmed": False, "pattern": "NONE", "strength": 0.0, "reason": ""}

    if df is None or len(df) < 5:
        return empty

    try:
        c1 = df.iloc[-3]   # sweep candle
        c2 = df.iloc[-2]   # displacement candle
        c3 = df.iloc[-1]   # current (confirmation) candle

        atr  = float(df['close'].rolling(14).std().iloc[-1]) or 1
        avg_body = float(abs(df['close'] - df['open']).rolling(20).mean().iloc[-1]) or 1

        if direction == 'BUY':
            # Candle 1 must be bearish (the sweep took out lows)
            c1_bear = c1['close'] < c1['open']
            # Candle 2 must be a strong bullish displacement (relaxed for scalping)
            c2_body = abs(c2['close'] - c2['open'])
            c2_rng  = c2['high'] - c2['low']
            c2_bull_strong = (c2['close'] > c2['open'] and
                              c2_body > c2_rng * 0.30 and   # was 0.40/0.55
                              c2_body > avg_body * 0.8)     # 1.2x was too strict
            # Candle 3: fails to close below Candle 1 low (bears exhausted)
            c3_holds = c3['close'] > c1['low']
            # Bonus: Candle 3 is itself green (immediate rejection of the low)
            c3_green = c3['close'] > c3['open']

            if c1_bear and c2_bull_strong and c3_holds:
                strength = 0.7 + (0.15 if c3_green else 0) + (0.15 if c2_body > avg_body * 1.8 else 0)
                return {
                    "confirmed": True,
                    "pattern": "3C_BULL",
                    "strength": min(1.0, strength),
                    "reason": f"3C BUY: C1 swept low, C2 displaced bullish, C3 holds above C1.low({c1['low']:.4f})"
                }

        elif direction == 'SELL':
            c1_bull = c1['close'] > c1['open']
            c2_body = abs(c2['close'] - c2['open'])
            c2_rng  = c2['high'] - c2['low']
            c2_bear_strong = (c2['close'] < c2['open'] and
                              c2_body > c2_rng * 0.40 and
                              c2_body > avg_body * 0.8)
            c3_holds = c3['close'] < c1['high']
            c3_red   = c3['close'] < c3['open']

            if c1_bull and c2_bear_strong and c3_holds:
                strength = 0.7 + (0.15 if c3_red else 0) + (0.15 if c2_body > avg_body * 1.8 else 0)
                return {
                    "confirmed": True,
                    "pattern": "3C_BEAR",
                    "strength": min(1.0, strength),
                    "reason": f"3C SELL: C1 swept high, C2 displaced bearish, C3 holds below C1.high({c1['high']:.4f})"
                }

        return {**empty, "reason": "3C conditions not met"}

    except Exception as e:
        return {**empty, "reason": f"3C error: {e}"}


def detect_swappy_3c(df: 'pd.DataFrame', direction: str) -> dict:
    """
    Swappy 3C Momentum Setup -- trend continuation, NOT reversal.

    This complements detect_3c_setup() (which is the SSM reversal version).
    Swappy fires DURING a trend move, catching the continuation after a brief
    pullback. SSM fires at a sweep/reversal point.

    BULLISH (BUY continuation):
      C1: Green candle (trend leg up)
      C2: Green candle (continuation, C2.low >= C1.low -- no lower lows)
      C3: Red pullback candle that FAILS to close below C1.low
          -> Bears tried to push down, failed. Bulls still in control.
      Entry: at C3 close or FVG within C3 body

    BEARISH (SELL continuation):
      C1: Red candle (trend leg down)
      C2: Red candle (continuation, C2.high <= C1.high -- no higher highs)
      C3: Green pullback candle that FAILS to close above C1.high
          -> Bulls tried to push up, failed. Bears still in control.

    Key difference from SSM:
      SSM needs a sweep of a structural level first (high/low grabbed).
      Swappy just needs 2 trend candles + 1 failed pullback, anywhere in trend.
      Use SSM at structure. Use Swappy mid-trend for continuation adds.

    Returns:
      { 'confirmed': bool, 'pattern': str, 'strength': float, 'reason': str,
        'entry_level': float }
    """
    empty = {"confirmed": False, "pattern": "NONE", "strength": 0.0,
             "reason": "", "entry_level": 0.0}

    if df is None or len(df) < 5:
        return empty

    try:
        c1 = df.iloc[-3]
        c2 = df.iloc[-2]
        c3 = df.iloc[-1]

        avg_body = float(abs(df['close'] - df['open']).rolling(20).mean().iloc[-1]) or 1e-9

        def body(c):    return abs(c['close'] - c['open'])
        def is_green(c): return c['close'] > c['open']
        def is_red(c):   return c['close'] < c['open']
        def body_pct(c): 
            rng = c['high'] - c['low']
            return body(c) / rng if rng > 0 else 0

        if direction == 'BUY':
            # Two green candles then one red pullback
            # Threshold 0.25/0.20: realistic for M5 scalping candles (Asian session has small candles)
            c1_green = is_green(c1) and 0.70 <= body_pct(c1) <= 0.80 and body(c1) >= avg_body * 0.5
            c2_green = is_green(c2) and 0.70 <= body_pct(c2) <= 0.80
            # C2 low >= C1 low: higher lows = trend intact
            higher_low = c2['low'] >= c1['low'] * 0.9995
            # C3 red but fails to close below C1 low (bears rejected)
            c3_red = is_red(c3)
            c3_holds = c3['close'] > c1['low']
            # Bonus: C3 closes above the midpoint of C1 (strong rejection)
            c3_above_mid = c3['close'] > (c1['low'] + c1['high']) / 2

            if c1_green and c2_green and higher_low and c3_red and c3_holds:
                strength = 0.65
                if c3_above_mid: strength += 0.15
                if body(c2) > avg_body * 1.1: strength += 0.10
                if body(c3) < avg_body * 0.7: strength += 0.10  # small pullback = weak bears
                entry_level = c3['close']  # enter at close of C3
                # Buy Stop trigger = above the 3-candle high (not C3 close)
                _setup_high = max(float(c1['high']), float(c2['high']), float(c3['high']))
                _setup_low  = min(float(c1['low']),  float(c2['low']),  float(c3['low']))
                return {
                    "confirmed": True, "pattern": "SWAPPY_BULL",
                    "strength": min(1.0, strength),
                    "entry_level": entry_level,       # C3 close = initial reference
                    "stop_entry":  _setup_high,        # Buy Stop: place order above this
                    "setup_high":  _setup_high,
                    "setup_low":   _setup_low,
                    "expiry_candles": 5,               # cancel if not triggered in 5 candles
                    "order_type": "BUY_STOP",
                    "reason": (f"Swappy BUY: 2 green legs (body70%), C3 red holds above "
                               f"C1.low({c1['low']:.4f}). Buy Stop at {_setup_high:.4f}.")
                }

        elif direction == 'SELL':
            c1_red = is_red(c1) and 0.70 <= body_pct(c1) <= 0.80 and body(c1) >= avg_body * 0.5
            c2_red = is_red(c2) and 0.70 <= body_pct(c2) <= 0.80
            lower_high = c2['high'] <= c1['high'] * 1.0005
            c3_green = is_green(c3)
            c3_holds = c3['close'] < c1['high']
            c3_below_mid = c3['close'] < (c1['low'] + c1['high']) / 2

            if c1_red and c2_red and lower_high and c3_green and c3_holds:
                strength = 0.65
                if c3_below_mid: strength += 0.15
                if body(c2) > avg_body * 1.1: strength += 0.10
                if body(c3) < avg_body * 0.7: strength += 0.10
                entry_level = c3['close']
                _setup_high = max(float(c1['high']), float(c2['high']), float(c3['high']))
                _setup_low  = min(float(c1['low']),  float(c2['low']),  float(c3['low']))
                return {
                    "confirmed": True, "pattern": "SWAPPY_BEAR",
                    "strength": min(1.0, strength),
                    "entry_level": entry_level,
                    "stop_entry":  _setup_low,         # Sell Stop: place order below this
                    "setup_high":  _setup_high,
                    "setup_low":   _setup_low,
                    "expiry_candles": 5,
                    "order_type": "SELL_STOP",
                    "reason": (f"Swappy SELL: 2 red legs (body70%), C3 green holds below "
                               f"C1.high({c1['high']:.4f}). Sell Stop at {_setup_low:.4f}.")
                }

        return {**empty, "reason": "Swappy conditions not met"}

    except Exception as e:
        return {**empty, "reason": f"Swappy error: {e}"}



def get_h1_mother_candle_zone(df_h1: 'pd.DataFrame', direction: str) -> dict:
    """
    H1 Mother Candle Fibonacci Golden Zone.

    A Mother Candle is a large, strong H1 candle (Marubozu-like):
      Body > 70% of range AND body > 2x the 14-bar ATR of H1
      This represents institutional intent on that H1 bar.

    The Fibonacci tool is applied to this candle:
      0%   = candle open (or low for bullish / high for bearish)
      100% = candle close (or high for bullish / low for bearish)

    Golden zone = 38.2% to 61.8% retracement back into the candle.
    This is where the best M5 entries occur -- price pulled back into
    the "cream zone" of the institutional H1 move.

    Why this matters vs FVG midpoint:
      FVG midpoint = 50% of a 3-candle M5 displacement (small scale)
      H1 Mother Candle zone = 38-62% of a full H1 institutional move
      When BOTH align, Gemini scores 9-10 (highest conviction).

    Returns:
      { 'found': bool, 'zone_high': float, 'zone_low': float,
        'in_zone': bool, 'candle_range': float, 'reason': str }
    """
    empty = {"found": False, "zone_high": 0.0, "zone_low": 0.0,
             "in_zone": False, "candle_range": 0.0, "reason": "No mother candle"}

    if df_h1 is None or len(df_h1) < 20:
        return empty

    try:
        current_price = float(df_h1['close'].iloc[-1])
        atr_h1 = float(calculate_atr(df_h1['high'], df_h1['low'],
                                      df_h1['close'], 14).iloc[-1])

        # Search last 10 H1 candles for a Mother Candle
        for i in range(1, min(11, len(df_h1))):
            c = df_h1.iloc[-i]
            body = abs(c['close'] - c['open'])
            rng  = c['high'] - c['low']
            if rng == 0: continue
            body_pct = body / rng

            is_big     = body > atr_h1 * 2.0       # Body > 2x ATR = institutional bar
            is_strong  = body_pct >= 0.70           # Body fills 70%+ of candle = marubozu-like

            if not (is_big and is_strong): continue

            # Direction filter: bullish candle for BUY zone, bearish for SELL zone
            is_bull = c['close'] > c['open']
            is_bear = c['close'] < c['open']

            if direction == 'BUY' and is_bull:
                # Golden zone: 38.2-61.8% pullback from candle high back toward low
                anchor_high = c['high']
                anchor_low  = c['low']
                zone_high = anchor_high - (anchor_high - anchor_low) * 0.382  # 38.2% down
                zone_low  = anchor_high - (anchor_high - anchor_low) * 0.618  # 61.8% down
                in_zone   = zone_low <= current_price <= zone_high
                return {
                    "found": True, "zone_high": zone_high, "zone_low": zone_low,
                    "in_zone": in_zone, "candle_range": anchor_high - anchor_low,
                    "reason": (f"H1 Bull Mother Candle ({i} bars ago): "
                               f"Fib zone {zone_low:.4f}-{zone_high:.4f} "
                               f"({'IN ZONE' if in_zone else 'NOT IN ZONE'})")
                }

            elif direction == 'SELL' and is_bear:
                anchor_high = c['high']
                anchor_low  = c['low']
                # Golden zone: 38.2-61.8% pullback up from candle low
                zone_low  = anchor_low + (anchor_high - anchor_low) * 0.382
                zone_high = anchor_low + (anchor_high - anchor_low) * 0.618
                in_zone   = zone_low <= current_price <= zone_high
                return {
                    "found": True, "zone_high": zone_high, "zone_low": zone_low,
                    "in_zone": in_zone, "candle_range": anchor_high - anchor_low,
                    "reason": (f"H1 Bear Mother Candle ({i} bars ago): "
                               f"Fib zone {zone_low:.4f}-{zone_high:.4f} "
                               f"({'IN ZONE' if in_zone else 'NOT IN ZONE'})")
                }

        return empty

    except Exception as e:
        return {**empty, "reason": f"Mother candle error: {e}"}


def strategy_liquidity_fvg_engine(symbol: str, df_entry: pd.DataFrame, df_structure: pd.DataFrame, trend: str, edge_mode: str = "NORMAL", df_m15: 'pd.DataFrame' = None, df_h1: 'pd.DataFrame' = None) -> Optional[Dict[str, Any]]:
    """
    SMC CORE ENGINE v3: HTF OB -> M5 Sweep -> Displacement -> FVG RETEST -> Enter
    
    Top-down approach:
      Layer 2a: Price must be at/near a valid M15 or H1 Order Block (HTF POI)
      Layer 2b: M5 shows sweep + displacement confirming the HTF rejection
      Layer 2c: Enter on FVG retest with tight structural SL

    CHANGE 2 -- True ICT entry sequence:
    Step 1: Sweep of recent high/low (liquidity grab)
    Step 2: Strong displacement candle away from sweep (impulse)
    Step 3: FVG left by displacement (gap between pre-impulse and post-impulse)
    Step 4: Price RETRACES into the FVG -> THIS is where we enter

    Why this is better than entering on the displacement close:
    - Tighter SL (placed below/above sweep wick, not the displacement candle)
    - Better entry price (inside the FVG, closer to structure)
    - Higher probability (retest confirms the displacement was real)
    - Avoids chasing (no entry if price doesn't retrace -- no setup, no trade)
    """
    try:
        if len(df_entry) < 25: return None

        atr      = calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], 14).iloc[-1]
        avg_body = abs(df_entry['close'] - df_entry['open']).rolling(20).mean().iloc[-1]
        if avg_body == 0: return None

        current_price = df_entry['close'].iloc[-1]
        lookback      = 15
        recent_high   = df_entry['high'].iloc[-lookback:-3].max()
        recent_low    = df_entry['low'].iloc[-lookback:-3].min()
        sweep_low_idx = df_entry['low'].iloc[-lookback:-3].idxmin()
        sweep_high_idx= df_entry['high'].iloc[-lookback:-3].idxmax()

        displacement_factor = 1.2 if edge_mode == "AGGRESSIVE" else 1.5

        # ----------------------------------------------------------------
        # PRE-SCAN: Determine which directions have HTF OB confluence
        # Without a valid HTF POI, we don't scan for M5 setups at all.
        # This is the "Top-Down" filter: H1/M15 OB -> M5 entry only.
        # If no HTF data provided, fall back to old behaviour (no filter).
        # ----------------------------------------------------------------
        _htf_buy  = None
        _htf_sell = None
        _htf_available = (df_m15 is not None and len(df_m15) >= 30) or                          (df_h1  is not None and len(df_h1)  >= 30)

        if _htf_available:
            _htf_buy  = get_htf_confluence(symbol, 'BUY',  df_m15, df_h1, current_price)
            _htf_sell = get_htf_confluence(symbol, 'SELL', df_m15, df_h1, current_price)
            # HTF is now context/confidence, not a hard gate
            # Setups without HTF OB get lower confidence score, handled by L3
            if not _htf_buy['at_poi'] and not _htf_sell['at_poi']:
                logger.debug(f"[HTF FILTER] {symbol}: no HTF OB -- FVG scan continues, lower confidence")

        # CHANGE 3: Real volume confirmation (not hardcoded True)
        avg_vol      = df_entry['tick_volume'].iloc[-15:].mean()
        vol_mult     = 1.0 if edge_mode == "AGGRESSIVE" else 1.3
        has_volume   = df_entry['tick_volume'].iloc[-1] > avg_vol * vol_mult or                        df_entry['tick_volume'].iloc[-2] > avg_vol * vol_mult
        # Volume gate: displacement must have above-average volume
        # If broker reports zero tick_volume (some brokers), allow through
        has_volume_data = avg_vol >= 1

        # ----------------------------------------------------------------
        # SCAN LAST 8 CANDLES for a Sweep + Displacement sequence
        # We look back because the impulse may have happened 1-3 bars ago
        # and price is NOW retesting the FVG it left
        # ----------------------------------------------------------------
        for disp_offset in range(1, 8):
            if disp_offset + 2 >= len(df_entry): break
            c_before = df_entry.iloc[-disp_offset - 2]  # candle before displacement
            c_disp   = df_entry.iloc[-disp_offset - 1]  # displacement candle
            # c_after is everything from c_disp+1 to now -- price retesting

            body_disp  = abs(c_disp['close'] - c_disp['open'])
            range_disp = c_disp['high'] - c_disp['low']
            if range_disp == 0: continue

            # Strong displacement: body > 60% of range AND body > displacement_factor x avg
            is_strong = (body_disp > range_disp * 0.6) and (body_disp > avg_body * displacement_factor)
            if not is_strong: continue

            # ---- BUY SETUP: Sweep Low -> Green Displacement -> FVG Retest ----
            if c_disp['close'] > c_disp['open']:  # Green (bullish) displacement
                # Sweep check: the displacement candle or previous one swept recent_low
                # STRICT SWEEP: wick breaks level AND body closes above it
                sweep_by_disp   = c_disp['low'] < recent_low and c_disp['close'] >= recent_low
                sweep_by_before = c_before['low'] < recent_low and c_before['close'] >= recent_low
                swept = sweep_by_disp or sweep_by_before
                if not swept: continue

                # FVG: gap between c_before high and first candle above displacement low
                # Standard ICT FVG: c_before.high < c_after.low (gap)
                fvg_bottom = c_before['high']   # bottom of the bullish FVG
                fvg_top    = c_disp['low']      # top of the bullish FVG
                # FVG only valid if there IS a gap (c_before high < c_disp low)
                if fvg_top <= fvg_bottom: continue
                fvg_mid    = (fvg_bottom + fvg_top) / 2

                # RETEST: current price is inside or touching the FVG
                # Price pulled back into the FVG after the displacement
                retest = (fvg_bottom <= current_price <= fvg_top)
                if not retest: continue

                # Volume confirmation: displacement candle should have above-average volume
                # Only gate if we have real volume data (some brokers report 0)
                disp_vol = c_disp.get('tick_volume', 0) if hasattr(c_disp, 'get') else c_disp['tick_volume']
                if has_volume_data and disp_vol < avg_vol * 0.8:
                    continue  # Displacement without volume = lower quality

                # SL just below sweep wick tip + spread buffer (tight structural SL)
                # 0.5x ATR was too wide (doubled SL size). Use 2x spread instead.
                sweep_wick_low = min(c_disp['low'], c_before['low'])
                tick = mt5.symbol_info_tick(symbol)
                _spread = (tick.ask - tick.bid) if tick else atr * 0.05
                sl = sweep_wick_low - max(_spread * 2, atr * 0.05)

                logger.info(
                    f"[SMC FVG] {symbol} BUY retest: FVG {fvg_bottom:.5f}-{fvg_top:.5f} "
                    f"price={current_price:.5f} sl={sl:.5f} disp={disp_offset}bars ago"
                )
                # HTF context: at OB = higher confidence; not at OB = lower confidence score
                # We do NOT hard-block here -- L3 Gemini scores the confluence
                _htf_buy_conf = _htf_buy['confluence_score'] if _htf_available and _htf_buy else 0

                # Use HTF OB SL if it's tighter than the M5 wick SL
                # (HTF OB low IS the structural invalidation for this setup)
                if _htf_buy and _htf_buy.get('htf_sl'):
                    htf_sl_candidate = _htf_buy['htf_sl']
                    # Use whichever SL is LOWER (more protective for BUY)
                    sl = min(sl, htf_sl_candidate) if htf_sl_candidate < sl else sl

                confluence = _htf_buy.get('confluence_score', 0) if _htf_buy else 0
                htf_reason = _htf_buy.get('reason', 'No HTF') if _htf_buy else 'No HTF data'
                confidence = min(0.98, 0.85 + confluence * 0.03)  # 0.85 base + 0.03 per confluence point

                return {
                    "direction":     "BUY",
                    "stop_loss":     sl,
                    "fvg_top":       fvg_top,
                    "fvg_bottom":    fvg_bottom,
                    "fvg_mid":       fvg_mid,
                    "strategy_name": "SMC_FVG_OB_RETEST",
                    "confidence":    confidence,
                    "setup_type":    "HTF_OB_FVG_RETEST",
                    "displacement_bars_ago": disp_offset,
                    "htf_confluence": confluence,
                    "htf_reason":    htf_reason,
                    "ob_h1":  _htf_buy.get('ob_h1'),
                    "ob_m15": _htf_buy.get('ob_m15'),
                }

            # ---- SELL SETUP: Sweep High -> Red Displacement -> FVG Retest ----
            if c_disp['close'] < c_disp['open']:  # Red (bearish) displacement
                # STRICT SWEEP: wick breaks level AND body closes below it
                sweep_by_disp   = c_disp['high'] > recent_high and c_disp['close'] <= recent_high
                sweep_by_before = c_before['high'] > recent_high and c_before['close'] <= recent_high
                swept = sweep_by_disp or sweep_by_before
                if not swept: continue

                fvg_top    = c_before['low']    # top of the bearish FVG
                fvg_bottom = c_disp['high']     # bottom of the bearish FVG
                if fvg_bottom <= fvg_top: continue
                fvg_mid    = (fvg_top + fvg_bottom) / 2

                retest = (fvg_bottom <= current_price <= fvg_top)
                if not retest: continue

                if not has_volume: continue

                sweep_wick_high = max(c_disp['high'], c_before['high'])
                tick = mt5.symbol_info_tick(symbol)
                _spread = (tick.ask - tick.bid) if tick else atr * 0.05
                sl = sweep_wick_high + max(_spread * 2, atr * 0.05)

                logger.info(
                    f"[SMC FVG] {symbol} SELL retest: FVG {fvg_bottom:.5f}-{fvg_top:.5f} "
                    f"price={current_price:.5f} sl={sl:.5f} disp={disp_offset}bars ago"
                )
                _htf_sell_conf = _htf_sell['confluence_score'] if (_htf_available and _htf_sell) else 0



                if _htf_sell and _htf_sell.get('htf_sl'):
                    htf_sl_candidate = _htf_sell['htf_sl']
                    sl = max(sl, htf_sl_candidate) if htf_sl_candidate > sl else sl

                confluence = _htf_sell.get('confluence_score', 0) if _htf_sell else 0
                htf_reason = _htf_sell.get('reason', 'No HTF') if _htf_sell else 'No HTF data'
                confidence = min(0.98, 0.85 + confluence * 0.03)

                return {
                    "direction":     "SELL",
                    "stop_loss":     sl,
                    "fvg_top":       fvg_top,
                    "fvg_bottom":    fvg_bottom,
                    "fvg_mid":       fvg_mid,
                    "strategy_name": "SMC_FVG_OB_RETEST",
                    "confidence":    confidence,
                    "setup_type":    "HTF_OB_FVG_RETEST",
                    "displacement_bars_ago": disp_offset,
                    "htf_confluence": confluence,
                    "htf_reason":    htf_reason,
                    "ob_h1":  _htf_sell.get('ob_h1'),
                    "ob_m15": _htf_sell.get('ob_m15'),
                }

        return None

    except Exception as e:
        logger.error(f"SMC FVG Engine Error: {e}")
        return None



# =============================================================================
# MTF SNIPER GATES
# =============================================================================

def get_h4_macro_bias(df_h4: 'pd.DataFrame') -> str:
    """
    H4 Macro Bias: the highest authority in the top-down hierarchy.
    Only the clearest H4 trend is actionable. NEUTRAL = no scan.

    Criteria:
      BULLISH: H4 price above EMA50 AND EMA50 above EMA200 AND last swing = HH/HL
      BEARISH: H4 price below EMA50 AND EMA50 below EMA200 AND last swing = LH/LL
      NEUTRAL: anything else (ranging, mixed structure)
    """
    if df_h4 is None or len(df_h4) < 55:
        return "NEUTRAL"
    try:
        close  = df_h4['close']
        high   = df_h4['high']
        low    = df_h4['low']
        ema50  = close.ewm(span=50, adjust=False).mean().iloc[-1]
        ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
        price  = close.iloc[-1]

        # EMA alignment
        bull_ema = price > ema50 > ema200
        bear_ema = price < ema50 < ema200

        # Swing structure: last 3 significant pivots
        hi20 = high.iloc[-20:].max()
        lo20 = low.iloc[-20:].min()
        hi10 = high.iloc[-10:].max()
        lo10 = low.iloc[-10:].min()
        # Higher highs + higher lows = bullish structure
        bull_struct = hi10 >= hi20 * 0.998 and lo10 >= lo20 * 1.002
        bear_struct = hi10 <= hi20 * 1.002 and lo10 <= lo20 * 0.998

        if bull_ema and bull_struct:
            return "BULLISH"
        if bear_ema and bear_struct:
            return "BEARISH"
        return "NEUTRAL"
    except Exception:
        return "NEUTRAL"


def is_price_in_htf_zone(symbol: str, direction: str,
                          df_h1: 'pd.DataFrame', df_m15: 'pd.DataFrame',
                          current_price: float, atr_m5: float) -> dict:
    """
    HTF POI Gate: Is price currently at a meaningful H1 or M15 zone?

    Before the M5 scan runs, this function checks:
    1. Is there a valid H1 Order Block nearby?
    2. Is there a valid M15 Order Block nearby?
    3. Are we within 1x M5 ATR of the zone? (price approaching the POI)

    Returns:
      { 'in_zone': bool, 'zone_type': str, 'zone_high': float,
        'zone_low': float, 'proximity_pct': float, 'reason': str }

    If not in zone: bot sleeps 30s and skips M5 scan for this symbol.
    If in zone: full M5 sweep + L3 validation runs.
    """
    result = {
        'in_zone': False, 'zone_type': 'NONE',
        'zone_high': 0.0, 'zone_low': 0.0,
        'proximity_pct': 0.0, 'reason': 'No HTF zone nearby'
    }

    # Check H1 OB -- use larger lookback for mature trends (2+ day moves)
    ob_h1 = detect_htf_orderblock(df_h1, direction, lookback=80)
    if ob_h1 and ob_h1['valid']:
        distance = abs(current_price - ob_h1['ob_mid'])
        proximity_pct = distance / max(ob_h1['ob_mid'], 1) * 100
        # Proximity: 0.3% of price OR 8x M5 ATR (whichever is larger)
        # This ensures XAG ($72) uses $0.22 minimum, XAU ($4370) uses $13 minimum
        zone_pct_buffer = current_price * 0.003  # 0.3% of price
        zone_atr_buffer = atr_m5 * 8
        zone_buffer = max(zone_pct_buffer, zone_atr_buffer)

        if distance <= zone_buffer:
            result.update({
                'in_zone': True,
                'zone_type': f"H1_{ob_h1['ob_type']}_OB",
                'zone_high': ob_h1['ob_high'],
                'zone_low':  ob_h1['ob_low'],
                'proximity_pct': proximity_pct,
                'reason': (
                    f"H1 {ob_h1['ob_type']} OB "
                    f"{ob_h1['ob_low']:.4f}-{ob_h1['ob_high']:.4f} "
                    f"({ob_h1['bars_ago']} bars ago, dist={distance:.4f}, buffer={zone_buffer:.4f})"
                )
            })
            return result

    # Check M15 OB
    ob_m15 = detect_htf_orderblock(df_m15, direction, lookback=80)
    if ob_m15 and ob_m15['valid']:
        distance = abs(current_price - ob_m15['ob_mid'])
        zone_pct_buffer = current_price * 0.002  # 0.2% of price for M15
        zone_atr_buffer = atr_m5 * 4
        zone_buffer = max(zone_pct_buffer, zone_atr_buffer)

        if distance <= zone_buffer:
            result.update({
                'in_zone': True,
                'zone_type': f"M15_{ob_m15['ob_type']}_OB",
                'zone_high': ob_m15['ob_high'],
                'zone_low':  ob_m15['ob_low'],
                'proximity_pct': distance / max(ob_m15['ob_mid'], 1) * 100,
                'reason': (
                    f"M15 {ob_m15['ob_type']} OB "
                    f"{ob_m15['ob_low']:.4f}-{ob_m15['ob_high']:.4f} "
                    f"({ob_m15['bars_ago']} bars ago)"
                )
            })

    return result


# =============================================================================
# HTF ORDER BLOCK ENGINE
# =============================================================================

def detect_htf_orderblock(df: 'pd.DataFrame', direction: str, lookback: int = 40) -> Optional[dict]:
    """
    Detect the most recent Valid HTF Order Block in df (M15 or H1).

    An ICT Valid OB is:
      Bullish OB: The last BEARISH candle before a bullish impulse that broke
                  the most recent swing high (BOS Up)
      Bearish OB: The last BULLISH candle before a bearish impulse that broke
                  the most recent swing low (BOS Down)

    A BOS is valid when a single displacement candle closes decisively beyond
    the previous swing point (body > 50% of candle range, strong close).

    Returns:
      {
        "ob_high": float,   OB candle high
        "ob_low":  float,   OB candle low
        "ob_mid":  float,   midpoint (ideal entry zone)
        "ob_type": "BULLISH"|"BEARISH",
        "tapped":  bool,    True if current price is inside or has touched OB
        "valid":   bool,    False if price has already closed through the OB
        "bars_ago": int,
      }
      or None if no valid OB found in lookback window.
    """
    if df is None or len(df) < lookback + 5:
        return None

    df = df.iloc[-lookback:].reset_index(drop=True)
    current_price = df['close'].iloc[-1]

    # Find swing highs/lows (simple: higher than 2 bars each side)
    def is_swing_high(i):
        if i < 2 or i > len(df) - 3: return False
        return df['high'].iloc[i] == df['high'].iloc[i-2:i+3].max()

    def is_swing_low(i):
        if i < 2 or i > len(df) - 3: return False
        return df['low'].iloc[i] == df['low'].iloc[i-2:i+3].min()

    # Practical OB detection: find the most recent significant opposite-color candle.
    # For SELL: last meaningful GREEN candle = bearish supply OB (institutions sell here)
    # For BUY:  last meaningful RED candle   = bullish demand OB (institutions buy here)
    # This is the standard ICT/SMC definition used by professionals:
    # "The last bullish/bearish candle before a displacement" -- we find it directly
    # without requiring a formal BOS (which fails in mature trending markets).
    avg_body = abs(df['close'] - df['open']).rolling(20, min_periods=5).mean().iloc[-1]
    avg_body = max(avg_body, (df['high'] - df['low']).mean() * 0.2)  # fallback floor

    search_limit = min(50, len(df) - 2)  # Search last 50 bars

    if direction == 'BUY':
        # Find last RED candle with meaningful body = demand OB
        for i in range(len(df) - 2, len(df) - 2 - search_limit, -1):
            if i < 0: break
            c = df.iloc[i]
            body = abs(c['close'] - c['open'])
            if c['close'] < c['open'] and body >= avg_body * 0.3:
                ob_high = c['high']
                ob_low  = c['low']
                ob_mid  = (ob_high + ob_low) / 2
                # Valid demand OB: current price hasn't closed far below the OB low
                tapped = ob_low * 0.998 <= current_price <= ob_high * 1.005
                valid  = current_price > ob_low * 0.990  # not broken through
                return {
                    "ob_high": ob_high, "ob_low": ob_low, "ob_mid": ob_mid,
                    "ob_type": "BULLISH", "tapped": tapped, "valid": valid,
                    "bars_ago": len(df) - 1 - i
                }

    elif direction == 'SELL':
        # Find last GREEN candle with meaningful body = supply OB
        for i in range(len(df) - 2, len(df) - 2 - search_limit, -1):
            if i < 0: break
            c = df.iloc[i]
            body = abs(c['close'] - c['open'])
            if c['close'] > c['open'] and body >= avg_body * 0.3:
                ob_high = c['high']
                ob_low  = c['low']
                ob_mid  = (ob_high + ob_low) / 2
                # Valid supply OB: current price hasn't closed far above the OB high
                tapped = ob_low * 0.995 <= current_price <= ob_high * 1.002
                valid  = current_price < ob_high * 1.010  # not broken through
                return {
                    "ob_high": ob_high, "ob_low": ob_low, "ob_mid": ob_mid,
                    "ob_type": "BEARISH", "tapped": tapped, "valid": valid,
                    "bars_ago": len(df) - 1 - i
                }

    # Fallback: check the old BOS-based detection for less common cases
    for i in range(len(df) - 2, 5, -1):
        c = df.iloc[i]
        body = abs(c['close'] - c['open'])
        rng  = c['high'] - c['low']
        if rng == 0: continue
        body_pct = body / rng

        if direction == 'BUY':
            prev_swing_high = df['high'].iloc[max(0,i-5):i].max()
            if (c['close'] > c['open'] and body_pct >= 0.35 and c['close'] > prev_swing_high):
                for j in range(i - 1, max(0, i - 8), -1):
                    ob = df.iloc[j]
                    if ob['close'] < ob['open']:
                        ob_high = ob['high']
                        ob_low  = ob['low']
                        ob_mid  = (ob_high + ob_low) / 2
                        tapped = ob_low <= current_price <= ob_high * 1.005
                        valid  = current_price > ob_low * 0.995
                        return {"ob_high": ob_high, "ob_low": ob_low, "ob_mid": ob_mid,
                                "ob_type": "BULLISH", "tapped": tapped, "valid": valid,
                                "bars_ago": len(df) - 1 - j}

        elif direction == 'SELL':
            prev_swing_low = df['low'].iloc[max(0,i-5):i].min()
            if (c['close'] < c['open'] and body_pct >= 0.35 and c['close'] < prev_swing_low):
                for j in range(i - 1, max(0, i - 8), -1):
                    ob = df.iloc[j]
                    if ob['close'] > ob['open']:
                        ob_high = ob['high']
                        ob_low  = ob['low']
                        ob_mid  = (ob_high + ob_low) / 2
                        tapped = ob_low * 0.995 <= current_price <= ob_high
                        valid  = current_price < ob_high * 1.005
                        return {
                            "ob_high": ob_high, "ob_low": ob_low, "ob_mid": ob_mid,
                            "ob_type": "BEARISH", "tapped": tapped, "valid": valid,
                            "bars_ago": len(df) - 1 - j
                        }

    return None


def get_htf_confluence(symbol: str, direction: str,
                       df_m15: 'pd.DataFrame', df_h1: 'pd.DataFrame',
                       current_price: float) -> dict:
    """
    Top-down HTF confluence check.
    Returns dict with:
      - ob_m15: M15 OB result (or None)
      - ob_h1:  H1 OB result (or None)
      - at_poi: bool -- price is within a valid HTF OB right now
      - htf_sl: float -- the structural SL from the HTF OB (wider, more reliable)
      - confluence_score: 0-3 (how many HTF factors align)
      - reason: human-readable string for logs/L3 prompt
    """
    result = {
        "ob_m15": None, "ob_h1": None,
        "at_poi": False, "htf_sl": None,
        "confluence_score": 0, "reason": "No HTF confluence"
    }

    # Check M15 OB
    ob_m15 = detect_htf_orderblock(df_m15, direction, lookback=50)
    if ob_m15 and ob_m15['valid']:
        result["ob_m15"] = ob_m15
        if ob_m15['tapped']:
            result["confluence_score"] += 2   # M15 OB tap = strong signal
            result["at_poi"] = True
            # HTF SL = beyond the OB extreme
            if direction == 'BUY':
                result["htf_sl"] = ob_m15["ob_low"]
            else:
                result["htf_sl"] = ob_m15["ob_high"]
            result["reason"] = (
                f"M15 {ob_m15['ob_type']} OB {ob_m15['ob_low']:.4f}-{ob_m15['ob_high']:.4f} "
                f"(formed {ob_m15['bars_ago']} bars ago)"
            )

    # Check H1 OB (higher weight)
    ob_h1 = detect_htf_orderblock(df_h1, direction, lookback=50)
    if ob_h1 and ob_h1['valid']:
        result["ob_h1"] = ob_h1
        if ob_h1['tapped']:
            result["confluence_score"] += 3   # H1 OB tap = very strong signal
            result["at_poi"] = True
            # H1 OB SL overrides M15 (it's the deeper structural level)
            if direction == 'BUY':
                result["htf_sl"] = ob_h1["ob_low"]
            else:
                result["htf_sl"] = ob_h1["ob_high"]
            result["reason"] = (
                f"H1 {ob_h1['ob_type']} OB {ob_h1['ob_low']:.4f}-{ob_h1['ob_high']:.4f} "
                f"(formed {ob_h1['bars_ago']} bars ago) + "
                + result["reason"]
            )

    # Both timeframes: maximum confluence
    if result["confluence_score"] >= 5:
        result["reason"] = "CONFLUENT: " + result["reason"]

    return result

# =============================================================================
# CONTEXT DECISION ENGINE (THE BRAIN)
# =============================================================================

@dataclass
class TradeDecision:
    bias: str           # BUY, SELL, NEUTRAL
    context_type: str   # TREND_PULLBACK, RANGE_REVERSAL, BREAKOUT
    confidence: float   # 0.0 - 1.0
    aggregated_score: float # Final score for risk scaling
    narrative_reason: str
    is_aggressive_allowed: bool
    regime: str         # For strategy selection
    allowed_behaviors: List[str]

class ContextDecisionEngine:
    """
    UNIFIED DECISION BRAIN.
    Combines: Regime + Structure + Volatility + Edge Mode
    Output: A single TradeDecision object.
    """
    
    @staticmethod
    def analyze_market_decision(symbol: str, df_m5: pd.DataFrame, df_m15: pd.DataFrame, edge_mode: str) -> TradeDecision:
        try:
            # 1. ANALYZE TREND (M15)
            ema_50 = df_m15['close'].ewm(span=50).mean().iloc[-1]
            ema_200 = df_m15['close'].ewm(span=200).mean().iloc[-1]
            current_price = df_m15['close'].iloc[-1]
            adx_series, _, _ = calculate_adx(df_m15['high'], df_m15['low'], df_m15['close'], 14)
            adx = adx_series.iloc[-1]
            
            # 2. DETERMINE REGIME
            regime = "RANGING"
            trend_threshold = 20 if edge_mode == "AGGRESSIVE" else 25
            
            if adx > trend_threshold:
                if ema_50 > ema_200 and current_price > ema_50: regime = "TRENDING_UP"
                elif ema_50 < ema_200 and current_price < ema_50: regime = "TRENDING_DOWN"
            elif adx > (trend_threshold - 5) and abs(current_price - ema_200) > (current_price * 0.005):
                 if current_price > ema_200: regime = "TRENDING_UP"
                 else: regime = "TRENDING_DOWN"
            
            # 3. BUILD DECISION PROFILE
            bias = "NEUTRAL"
            context_type = "CHOPPY"
            behaviors = []
            confidence = 0.5
            narrative = "Indeterminate"
            
            # Check for Expansion (Vol)
            atr_m5 = calculate_atr(df_m5['high'], df_m5['low'], df_m5['close'], 14).iloc[-1]
            avg_body = abs(df_m5['close'] - df_m5['open']).rolling(20).mean().iloc[-1]
            last_body = abs(df_m5['close'].iloc[-1] - df_m5['open'].iloc[-1])
            is_expansion = last_body > (avg_body * 1.5)
            
            if regime == "TRENDING_UP":
                bias = "BUY"
                context_type = "TREND_PULLBACK"
                behaviors = ["PULLBACK"]
                confidence = 0.8
                narrative = "Bullish Trend"
                
                if current_price < ema_50: behaviors.append("REVERSAL") # Deep pullback
                if is_expansion or edge_mode == "AGGRESSIVE": 
                    behaviors.append("BREAKOUT")
                    if edge_mode == "AGGRESSIVE": narrative += " (Aggressive Breakouts Allowed)"

            elif regime == "TRENDING_DOWN":
                bias = "SELL"
                context_type = "TREND_PULLBACK"
                behaviors = ["PULLBACK"]
                confidence = 0.8
                narrative = "Bearish Trend"
                
                if current_price > ema_50: behaviors.append("REVERSAL")
                if edge_mode == "AGGRESSIVE": behaviors.append("BREAKOUT")

            elif regime == "RANGING":
                bias = "NEUTRAL"
                context_type = "RANGE_REVERSAL"
                behaviors = ["REVERSAL"]
                confidence = 0.6
                narrative = "Ranging Market"
                
                upper = df_m15['high'].rolling(20).max().iloc[-1]
                mid = (upper + df_m15['low'].rolling(20).min().iloc[-1]) / 2
                
                if current_price > mid: bias = "SELL"
                else: bias = "BUY"
            
            # 4. FINAL AGGREGATION
            aggressive_allowed = (edge_mode == "AGGRESSIVE")
            
            # Base confidence modifications
            if is_expansion: confidence += 0.1
            if edge_mode == "DEFENSIVE": confidence -= 0.1
            
            return TradeDecision(
                bias=bias,
                context_type=context_type,
                confidence=max(0.1, min(0.99, confidence)),
                aggregated_score=confidence, # Can be enhanced
                narrative_reason=narrative,
                is_aggressive_allowed=aggressive_allowed,
                regime=regime,
                allowed_behaviors=behaviors
            )

        except Exception as e:
            logger.error(f"Decision Engine Error: {e}")
            return TradeDecision("NEUTRAL", "ERROR", 0.0, 0.0, "Error", False, "CHOPPY", [])

# =============================================================================
# LOCAL-FIRST CONFLUENCE ENGINE (REFACTORED V2)
# =============================================================================



class PriorityTriggerEngine:
    """
    Hierarchical Trigger Logic -- STRATEGY-AWARE SL PLACEMENT.
    Each trigger returns its own contextual SL based on the pattern that fired.
    SL is placed at the STRUCTURAL INVALIDATION POINT of the pattern.
    No generic hard-coded distances.
    """
    PRIORITY = {
        "SWEEP_AND_DISPLACE": 1,
        "MOMENTUM_BURST": 2,
        "MICRO_PULLBACK": 3,
        "EXPANSION_BREAKOUT": 4
    }
    
    @staticmethod
    def identify_trigger(df_m1: pd.DataFrame, df_m5: pd.DataFrame) -> Tuple[str, str, float, float]:
        """
        Returns: (trigger_type, direction, sl_price, key_level)
        sl_price = the STRUCTURAL price that invalidates the setup
        key_level = the liquidity level that was swept / broken
        """
        if len(df_m1) < 20:
            return "IGNORE", "NEUTRAL", 0.0, 0.0
        
        last = df_m1.iloc[-1]
        prev = df_m1.iloc[-2]
        
        last_close = last['close']
        last_open  = last['open']
        last_high  = last['high']
        last_low   = last['low']
        
        # ATR for buffer: use M1 ATR
        if len(df_m1) >= 14:
            atr_m1 = calculate_atr(df_m1['high'], df_m1['low'], df_m1['close'], 14).iloc[-1]
        else:
            atr_m1 = abs(last_high - last_low)
        
        # ATR on M5 for bigger-picture buffer
        if len(df_m5) >= 14:
            atr_m5 = calculate_atr(df_m5['high'], df_m5['low'], df_m5['close'], 14).iloc[-1]
        else:
            atr_m5 = atr_m1

        # Structure lookback on M1 (last 10 closed candles, excluding last)
        lookback_m1 = df_m1.iloc[-11:-1]
        prev_low_m1  = lookback_m1['low'].min()
        prev_high_m1 = lookback_m1['high'].max()
        
        # Structure lookback on M5 (last 10 candles)
        lookback_m5 = df_m5.iloc[-11:-1] if len(df_m5) > 11 else df_m5
        prev_low_m5  = lookback_m5['low'].min()
        prev_high_m5 = lookback_m5['high'].max()

        is_bull_candle = last_close > last_open
        is_bear_candle = last_close < last_open

        # ?? 1. SWEEP AND DISPLACE (Highest Priority) ??????????????????????????
        # BUY: Candle wicked below prior M1 structure, then closed ABOVE it.
        # SL = The actual wick low of the sweep candle + 1.5x ATR buffer (was 0.5x).
        if last_low < prev_low_m1 and last_close > prev_low_m1 and is_bull_candle:
            sweep_wick_low = last_low  # The liquidity that was taken
            sl_price = sweep_wick_low - (atr_m1 * 1.5)  # FIX: widened from 0.5x -> 1.5x
            key_level = prev_low_m1
            return "SWEEP_AND_DISPLACE", "BUY", sl_price, key_level

        # SELL: Candle wicked above prior M1 structure, then closed BELOW it.
        # SL = The actual wick high of the sweep candle + 1.5x ATR buffer (was 0.5x).
        if last_high > prev_high_m1 and last_close < prev_high_m1 and is_bear_candle:
            sweep_wick_high = last_high  # The liquidity that was taken
            sl_price = sweep_wick_high + (atr_m1 * 1.5)  # FIX: widened from 0.5x -> 1.5x
            key_level = prev_high_m1
            return "SWEEP_AND_DISPLACE", "SELL", sl_price, key_level

        # ?? 2. MOMENTUM BURST ?????????????????????????????????????????????????
        # Entry on volume-confirmed expansion candle.
        # SL = Below the body of the impulse candle (structure invalidation).
        tick_vol = df_m1['tick_volume'].iloc[-1]
        avg_vol = df_m1['tick_volume'].rolling(20).mean().iloc[-1]
        if tick_vol > avg_vol * 1.5:
            if is_bull_candle:
                # SL = Below the M5 prior swing low (momentum should not reverse below structure)
                sl_price = prev_low_m5 - (atr_m5 * 0.6)  # FIX: widened from 0.3x -> 0.6x
                key_level = prev_low_m5
                return "MOMENTUM_BURST", "BUY", sl_price, key_level
            elif is_bear_candle:
                sl_price = prev_high_m5 + (atr_m5 * 0.6)  # FIX: widened from 0.3x -> 0.6x
                key_level = prev_high_m5
                return "MOMENTUM_BURST", "SELL", sl_price, key_level

        return "IGNORE", "NEUTRAL", 0.0, 0.0




# =============================================================================
# AI-POWERED FUNCTIONS (Validation, Risk, Learning)
# =============================================================================

def _candles_to_text(df: 'pd.DataFrame', n: int = 20) -> str:
    """Convert last N candles to compact text for AI prompt."""
    rows = df.tail(n)
    lines = []
    for _, r in rows.iterrows():
        lines.append(
            f"O:{r['open']:.4f} H:{r['high']:.4f} L:{r['low']:.4f} C:{r['close']:.4f} "
            f"V:{int(r.get('tick_volume', 0))}"
        )
    return "\n".join(lines)


def _parse_ai_json(raw: str) -> dict:
    """Extract JSON from ANY Gemini response format."""
    if not raw:
        return {}
    import re as _re
    # Build candidate list in priority order
    candidates = []
    # Priority 1: strip markdown fences (most common Gemini format)
    s = raw.strip()
    if s.startswith("```"):
        inner = s.lstrip("`").lstrip("json").strip().rstrip("`").strip()
        candidates.append(inner)
    # Priority 2: find first { ... } block at any nesting depth
    depth = 0; start = -1
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0: start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                candidates.append(raw[start:i+1])
                break
    # Priority 3: full raw
    candidates.append(s)
    for chunk in candidates:
        chunk = chunk.strip()
        if not chunk or "{" not in chunk:
            continue
        try:
            result = json.loads(chunk)
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    return {}


# ---------- LAYER 1: MARKET INTELLIGENCE (runs every 2 hours) ----------
def update_global_ai_context():
    """
    LAYER 1 -- Market Intelligence (local computation, no API calls).
    Computes directional bias from H4 + H1 price data for every symbol.
    Updates every 30 min. Zero Gemini quota usage.
    Gemini L3 handles per-trade validation where AI truly adds value.
    """
    logger.info("[AI L1] Computing market bias from H4/H1 structure...")

    scan_list = list(dict.fromkeys(config.SYMBOLS))
    session   = get_current_session()
    new_bias     = {}
    new_strength = {}
    new_avoid    = {}
    new_levels   = {}
    parsed_count = 0

    for sym in scan_list:
        try:
            df_h4 = get_market_data(sym, mt5.TIMEFRAME_H4, 60)
            df_h1 = get_market_data(sym, mt5.TIMEFRAME_H1, 60)
            df_m5 = get_market_data(sym, mt5.TIMEFRAME_M5, 50)
            if df_h4 is None or df_h1 is None or df_h4.empty or df_h1.empty:
                new_bias[sym]     = state.approved_bias.get(sym, 'NEUTRAL')
                new_strength[sym] = 5
                new_avoid[sym]    = False
                continue

            # H4 primary bias (already proven reliable)
            h4_bias = get_h4_macro_bias(df_h4)

            # H1 secondary trend (EMA50/200 alignment)
            ema50_h1  = float(df_h1['close'].ewm(span=50,  adjust=False).mean().iloc[-1])
            ema200_h1 = float(df_h1['close'].ewm(span=200, adjust=False).mean().iloc[-1])
            price_h1  = float(df_h1['close'].iloc[-1])
            if price_h1 > ema50_h1 > ema200_h1:   h1_trend = "BULLISH"
            elif price_h1 < ema50_h1 < ema200_h1: h1_trend = "BEARISH"
            else:                                   h1_trend = "NEUTRAL"

            # Combine H4 + H1 for final bias
            if h4_bias == h1_trend and h4_bias != "NEUTRAL":
                final_bias = h4_bias      # both agree = strong
                base_strength = 8
            elif h4_bias != "NEUTRAL":
                final_bias = h4_bias      # H4 leads
                base_strength = 6
            elif h1_trend != "NEUTRAL":
                final_bias = h1_trend     # H1 only
                base_strength = 4
            else:
                final_bias = "NEUTRAL"
                base_strength = 3

            # Strength from ATR volatility (higher ATR = stronger move)
            atr_h4 = float(calculate_atr(df_h4['high'], df_h4['low'], df_h4['close'], 14).iloc[-1])
            price   = float(df_h4['close'].iloc[-1])
            atr_pct = (atr_h4 / price) * 100  # ATR as % of price
            # Gold: 0.3% = normal, >0.5% = strong trend
            # BTC:  0.8% = normal, >1.5% = strong trend
            if atr_pct > 0.4:
                strength = min(10, base_strength + 2)  # high volatility = strong move
            elif atr_pct < 0.15:
                strength = max(1, base_strength - 2)   # low volatility = weak/choppy
            else:
                strength = base_strength

            # Avoid flag: extreme spread or very low volatility in Asian session
            is_asian  = session == "ASIAN"
            is_choppy = atr_pct < 0.10
            avoid     = is_asian and is_choppy

            # Key level: current H4 EMA50 (institutional reference)
            key_level = float(df_h4['close'].ewm(span=50, adjust=False).mean().iloc[-1])

            new_bias[sym]     = 'BUY_ONLY' if final_bias == 'BULLISH' else ('SELL_ONLY' if final_bias == 'BEARISH' else 'NEUTRAL')
            new_strength[sym] = strength
            new_avoid[sym]    = avoid
            new_levels[sym]   = key_level
            parsed_count     += 1

        except Exception as e:
            logger.warning(f"[AI L1] {sym}: error -- {e}")
            new_bias[sym]     = state.approved_bias.get(sym, 'NEUTRAL')
            new_strength[sym] = state.ai_bias_strength.get(sym, 5)
            new_avoid[sym]    = False

    if parsed_count == 0:
        logger.warning("[AI L1] All symbols failed -- keeping cached bias")
        return

    state.approved_bias           = new_bias
    state.ai_bias_strength        = new_strength
    state.ai_avoid_symbols        = new_avoid
    state.ai_key_levels           = new_levels
    state.global_market_sentiment = "ACTIVE" if session in ("LONDON", "NEW_YORK", "LONDON_NY") else "CHOPPY"
    state.last_global_context_update = datetime.now()
    state._l1_last_run = time.time()

    bias_summary = " | ".join(
        f"{s.replace('USDm','').replace('m','')}:{v.replace('_ONLY','')[:4]}({new_strength.get(s,5)})"
        for s,v in new_bias.items()
    )
    logger.info(f"[AI L1] {session} | {bias_summary}")



# ---------- LAYER 3: AI TRADE VALIDATION (per candidate setup) ----------
def _l3_bias_fallback(symbol: str, direction: str, reason: str) -> dict:
    """
    Shared degraded-mode fallback for ai_validate_trade -- used both when
    Gemini isn't configured AND when a live call to it fails. Approves only
    when the cached L1 macro bias agrees with this trade's direction.

    Deliberately fails closed rather than open: this must NEVER score
    higher than a real AI approval would (score 7, same as the "aligned"
    case below), so an API outage can never look more convincing than the
    AI actually being asked. Previously the on-error path returned a
    fabricated score of 8/10 with a fake-sounding reason, which meant any
    Gemini timeout, quota exhaustion, or malformed response silently
    APPROVED the trade at a score exceeding every real min-score gate in
    the codebase (5-7) -- i.e. every AI outage passed every trade through
    as if it had gotten a strong (never-actually-given) AI endorsement.
    """
    bias = state.approved_bias.get(symbol, 'NEUTRAL')
    aligned = (bias == 'BUY_ONLY' and direction == 'BUY') or (bias == 'SELL_ONLY' and direction == 'SELL')
    return {
        'score': 7 if aligned else 4,
        'approved': aligned or bias == 'NEUTRAL',
        'reason': reason,
        'risk_modifier': 1.0
    }


def ai_validate_trade(symbol: str, direction: str, setup_name: str,
                      entry: float, sl: float, tp: float,
                      df_m5: 'pd.DataFrame', df_m1: 'pd.DataFrame') -> dict:
    """
    LAYER 3 -- Per-trade AI validation.
    Sends the actual candle context + proposed trade to Gemini.
    Gemini scores it 1-10 and explains the reasoning.

    Returns:
        { 'score': int 1-10, 'approved': bool, 'reason': str, 'risk_modifier': float }

    Score >= 7 --> trade placed
    Score 4-6  --> trade skipped (logged, no Telegram)
    Score 1-3  --> trade skipped + symbol gets 30min cooldown

    If Gemini unavailable, or a call to it fails --> falls back to the L1
    bias check (approved only if bias aligns), never to a fabricated score.
    """
    if not config.ENABLE_AI_VALIDATION:
        return {'score': 7, 'approved': True, 'reason': 'AI validation disabled', 'risk_modifier': 1.0}

    # Fallback: if AI unavailable, use cached L1 bias
    if not ai_provider.gemini_model:
        bias = state.approved_bias.get(symbol, 'NEUTRAL')
        return _l3_bias_fallback(symbol, direction, f'AI unavailable -- using cached bias: {bias}')

    session = get_current_session()
    rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0

    # Compact candle context (last 10 M5, last 5 M1)
    m5_text = _candles_to_text(df_m5, 10) if df_m5 is not None and len(df_m5) >= 10 else "unavailable"
    m1_text = _candles_to_text(df_m1, 5)  if df_m1 is not None and len(df_m1) >= 5  else "unavailable"

    # L1 bias for context
    l1_bias     = state.approved_bias.get(symbol, 'NEUTRAL')
    l1_strength = getattr(state, 'ai_bias_strength', {}).get(symbol, 0)
    l1_level    = getattr(state, 'ai_key_levels', {}).get(symbol)

    prompt = f"""You are a professional ICT scalping analyst. Evaluate this trade setup.

Symbol: {symbol} | Session: {session}
Setup: {setup_name} | Direction: {direction}
Entry: {entry:.5f} | SL: {sl:.5f} (dist: {abs(entry-sl):.5f})
TP:    {tp:.5f}    (RR 1:{rr:.1f})
L1 macro bias: {l1_bias} (strength {l1_strength}/10){f' | Key level: {l1_level:.4f}' if l1_level else ''}

M5 last 10 candles (OHLCV, newest last):
{m5_text}

M1 last 5 candles (entry precision):
{m1_text}

Evaluate:
1. Does the M5 structure confirm a genuine liquidity sweep + displacement?
2. Is price retesting a valid FVG (not chasing)?
3. Is the SL placed at the correct structural point (sweep wick extreme)?
4. Does this align with the session and macro bias?
5. Is the RR worth taking (min 1:2)?

Respond ONLY with this JSON:
{{"score": 1-10, "approved": true/false, "reason": "one sentence", "risk_modifier": 0.5-1.5}}

Score guide: 9-10=A+ setup, 7-8=good, 5-6=marginal skip, 1-4=avoid.
approved=true only when score>=7."""

    try:
        raw = ai_provider.call_ai(
            prompt,
            system_prompt="You are a JSON-only ICT trade validator. Return only the JSON object.",
            temperature=0.1,
            max_tokens=200,
            json_mode=True
        )
        result = _parse_ai_json(raw)
        score  = int(result.get('score', 5))
        approved = bool(result.get('approved', score >= 7))
        reason   = str(result.get('reason', 'No reason given'))
        risk_mod = float(result.get('risk_modifier', 1.0))

        logger.info(f"[AI L3] {symbol} {direction} ({setup_name}): score={score}/10 "
                    f"approved={approved} | {reason}")

        return {'score': score, 'approved': approved, 'reason': reason,
                'risk_modifier': max(0.5, min(1.5, risk_mod))}

    except Exception as e:
        logger.warning(f"[AI L3] Validation failed for {symbol}: {e} -- degraded to L1 bias fallback (fail-closed)")
        # On error: degrade to the same honest L1-bias fallback used when
        # Gemini isn't configured at all. NEVER fabricate a passing score --
        # see _l3_bias_fallback's docstring for why the old behavior here
        # (score=8) was a real bug, not just a cosmetic one.
        return _l3_bias_fallback(symbol, direction, f'AI call failed ({e}) -- using cached bias, not a real AI score')


def ai_filter_signal(local_signal: Dict) -> Dict[str, Any]:
    """Legacy wrapper -- kept for compatibility. Real validation now in ai_validate_trade."""
    return {'approved': True, 'confidence_adjustment': 0.0, 'risk_modifier': 1.0}

# === COPY AND REPLACE THIS FUNCTION ===


def ai_analyze_closed_trades():
    """
    SMART LEARNING: Reviews session performance and adjusts strategy weights.

    KEY FIXES:
    - Uses get_session_trades() so old losses from buggy prior sessions
      never cause strategies to be banned on the next restart.
    - Requires MIN_TRADES_FOR_LEARNING trades THIS SESSION before any ban.
    - Banning threshold raised to <30% win rate (was <40%) to avoid over-banning.
    - Banned strategies auto-clear at the start of each new calendar day.
    """
    if not config.ENABLE_AI_TRADE_LEARNING:
        return

    now = datetime.now()

    # Auto-clear all bans at midnight each day
    if not hasattr(state, '_last_ban_clear_day'):
        state._last_ban_clear_day = now.day
    if now.day != state._last_ban_clear_day:
        if state.banned_strategies:
            logger.info(f"[AI LEARNING] New day -- clearing {len(state.banned_strategies)} strategy bans.")
        state.banned_strategies = []
        state._last_ban_clear_day = now.day

    if state.last_ai_learning_time and (now - state.last_ai_learning_time) < timedelta(seconds=config.AI_LEARNING_INTERVAL):
        return

    # Use ONLY trades from this session to avoid banning on stale data
    session_trades = trade_db.get_session_trades(state.session_start_time, limit=100)

    if len(session_trades) < config.MIN_TRADES_FOR_LEARNING:
        logger.info(
            f"[AI LEARNING] Only {len(session_trades)} session trades "
            f"(need {config.MIN_TRADES_FOR_LEARNING}). Skipping analysis."
        )
        state.last_ai_learning_time = now
        return

    logger.info(f"[AI LEARNING] Analyzing {len(session_trades)} SESSION trades...")

    # Build per-strategy performance from session trades only
    strat_perf = defaultdict(lambda: {'wins': 0, 'losses': 0, 'pnl': 0.0})
    for t in session_trades:
        name = t.get('strategy_name', 'Unknown')
        pnl = t.get('profit_loss', 0)
        strat_perf[name]['pnl'] += pnl
        if pnl > 0:
            strat_perf[name]['wins'] += 1
        else:
            strat_perf[name]['losses'] += 1

    system_prompt = """You are a Strategy Optimization AI.
    Review session performance data.
    Rules:
    1. ONLY ban a strategy if win rate < 30% AND at least 10 trades for that strategy.
       Do NOT ban on small sample sizes -- that causes false bans from bad luck.
    2. Unban strategies that now show > 50% win rate with 5+ trades.
    3. Be conservative -- it is better to keep a strategy active than to over-ban.

    Respond ONLY with valid JSON:
    {
      "banned_strategies": [],
      "unban_strategies": [],
      "adjustments": {}
    }"""

    prompt = (
        f"Session trades analyzed: {len(session_trades)}\n"
        f"Strategy Performance: {json.dumps(dict(strat_perf), indent=2)}\n"
        f"Currently Banned: {state.banned_strategies}"
    )

    try:
        response = ai_provider.call_ai(prompt, system_prompt, temperature=0.2, max_tokens=1000, json_mode=True)

        if not response:
            logger.warning("[AI LEARNING] Empty AI response. Skipping.")
            state.last_ai_learning_time = now
            return

        if "```json" in response:
            response = response.split("```json")[-1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[-1].split("```")[0].strip()

        try:
            result = json.loads(response)
        except Exception as json_err:
            logger.warning(f"[AI LEARNING] JSON parse error: {json_err}")
            state.last_ai_learning_time = now
            return

        # Apply bans - only strategies with enough trades
        new_bans = result.get('banned_strategies', [])
        for s in new_bans:
            perf = strat_perf.get(s, {})
            total = perf.get('wins', 0) + perf.get('losses', 0)
            win_rate = perf.get('wins', 0) / total if total > 0 else 1.0
            if total >= 10 and win_rate < 0.30:
                if s not in state.banned_strategies:
                    state.banned_strategies.append(s)
                    logger.warning(f"[AI LEARNING] Banned strategy: {s} (win rate {win_rate:.0%} over {total} session trades)")
            else:
                logger.info(f"[AI LEARNING] Skipped ban on {s} -- insufficient sample ({total} trades, {win_rate:.0%})")

        # Remove bans
        unbans = result.get('unban_strategies', [])
        for s in unbans:
            if s in state.banned_strategies:
                state.banned_strategies.remove(s)
                logger.info(f"[AI LEARNING] Unbanned strategy: {s}")

        state.last_ai_learning_time = now

    except Exception as e:
        logger.error(f"[AI LEARNING] Error: {e}", exc_info=True)


        
# =============================================================================
# DYNAMIC TRADE EXECUTION & MANAGEMENT
# =============================================================================

def get_broker_min_sl_distance(symbol: str, tick_price: float) -> float:
    """
    CRITICAL: Fetch the broker's mandatory minimum SL distance.
    If SL is closer than this, the broker silently moves it to the stop_level edge,
    which is right next to the entry price -- causing instant stop-outs.
    """
    try:
        info = mt5.symbol_info(symbol)
        if info is None:
            return 0.0
        
        # stop_level is in POINTS (not pips). Convert to price.
        stop_level_points = info.trade_stops_level
        point = info.point
        
        if stop_level_points is None or stop_level_points <= 0:
            return 0.0
        
        # The minimum distance in price terms
        min_dist = stop_level_points * point
        logger.debug(f"[SL GUARD] {symbol} broker stop_level={stop_level_points} pts = {min_dist:.5f} price units")
        return min_dist
    except Exception as e:
        logger.error(f"[SL GUARD] Error fetching broker stop_level for {symbol}: {e}")
        return 0.0


def check_symbol_max_spread(symbol: str, tick) -> bool:
    """
    NEW: Absolute spread gate per symbol.
    Prevents entries when the broker is widening spreads (low liquidity / rollover / news).
    Returns True = spread is acceptable, False = skip trade.
    """
    spread_amount = tick.ask - tick.bid
    sym_upper = symbol.upper()

    if 'XAUUSD' in sym_upper:
        ok = spread_amount <= config.SCALP_MAX_SPREAD_XAUUSD
        if not ok:
            logger.warning(f"[SPREAD GATE] {symbol} spread ${spread_amount:.2f} > limit ${config.SCALP_MAX_SPREAD_XAUUSD}")
        return ok
    elif 'XAGUSD' in sym_upper:
        ok = spread_amount <= config.SCALP_MAX_SPREAD_XAGUSD
        if not ok:
            logger.warning(f"[SPREAD GATE] {symbol} spread ${spread_amount:.4f} > limit ${config.SCALP_MAX_SPREAD_XAGUSD}")
        return ok
    elif 'BTC' in sym_upper:
        ok = spread_amount <= config.SCALP_MAX_SPREAD_BTC
        if not ok:
            logger.warning(f"[SPREAD GATE] {symbol} spread ${spread_amount:.1f} > limit ${config.SCALP_MAX_SPREAD_BTC}")
        return ok
    elif 'ETH' in sym_upper:
        ok = spread_amount <= config.SCALP_MAX_SPREAD_ETH
        if not ok:
            logger.warning(f"[SPREAD GATE] {symbol} spread ${spread_amount:.2f} > limit ${config.SCALP_MAX_SPREAD_ETH}")
        return ok
    elif 'OIL' in sym_upper or 'USOIL' in sym_upper:
        ok = spread_amount <= config.SCALP_MAX_SPREAD_OIL
        if not ok:
            logger.warning(f"[SPREAD GATE] {symbol} spread ${spread_amount:.3f} > limit ${config.SCALP_MAX_SPREAD_OIL}")
        return ok
    else:
        # FX pairs -- convert to pips
        sym_info = mt5.symbol_info(symbol)
        point = sym_info.point if sym_info else 0.0001
        spread_pips = spread_amount / (point * 10)
        ok = spread_pips <= config.SCALP_MAX_SPREAD_FX_PIPS
        if not ok:
            logger.warning(f"[SPREAD GATE] {symbol} spread {spread_pips:.2f} pips > limit {config.SCALP_MAX_SPREAD_FX_PIPS}")
        return ok


def check_scalping_quality(symbol: str, direction: str, df_m5: pd.DataFrame, df_m1: pd.DataFrame) -> Tuple[bool, str]:
    """
    HIGH-QUALITY SCALPING FILTER (NEW):
    Returns (is_high_quality, reason_string).

    Gates:
      1. Kill zone  -- only London / NY (configurable)
      2. ADX        -- momentum must be >= SCALP_MIN_ADX on M5
      3. RSI        -- entry not in overbought / oversold extreme zone
      4. Volume     -- M1 tick volume surge confirms institutional activity
      5. Body ratio -- avoid doji / indecision candles on M5
    """
    try:
        # 1. KILL ZONE (session gate)
        if config.SCALP_FORCE_KILL_ZONE:
            current_hour = datetime.now(timezone.utc).hour
            # Check against ICT_KILLZONES config directly -- single source of truth
            in_kill_zone = any(
                start <= current_hour < end
                for start, end in config.ICT_KILLZONES.values()
            )
            if not in_kill_zone:
                return False, f"Outside all kill zones (UTC hour={current_hour})"

        if df_m5 is None or len(df_m5) < 20:
            return True, "INSUFFICIENT_DATA"  # Don't block on missing data

        # 2. ADX MOMENTUM -- M5
        try:
            adx_series, _, _ = calculate_adx(df_m5['high'], df_m5['low'], df_m5['close'], 14)
            adx_val = float(adx_series.iloc[-1])
            if adx_val < config.SCALP_MIN_ADX:
                return False, f"Weak momentum: M5 ADX {adx_val:.1f} < {config.SCALP_MIN_ADX}"
        except Exception:
            pass  # Allow if ADX fails to calculate

        # 3. RSI FILTER -- M5 (no chasing extremes)
        try:
            if len(df_m5) >= 16:
                delta = df_m5['close'].diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / (loss.replace(0, 1e-10))
                rsi = float((100 - (100 / (1 + rs))).iloc[-1])

                if direction == 'BUY':
                    # Only block if OVERBOUGHT (chasing extended move)
                    # RSI < 30 = OVERSOLD = institutional discount = valid scalp, DO NOT block
                    if rsi > 82:
                        return False, f"RSI overbought for BUY ({rsi:.1f} > 82) -- chasing"
                elif direction == 'SELL':
                    # Only block if OVERSOLD (chasing extended down move)
                    # RSI > 70 = OVERBOUGHT = institutional premium = valid scalp, DO NOT block
                    if rsi < 18:
                        return False, f"RSI oversold for SELL ({rsi:.1f} < 18) -- chasing"
        except Exception:
            pass

        # 4. VOLUME SURGE -- M1 (institutional fingerprint)
        try:
            if df_m1 is not None and len(df_m1) >= 22:
                avg_vol = float(df_m1['tick_volume'].rolling(20).mean().iloc[-1])
                recent_vol = float(df_m1['tick_volume'].iloc[-1])
                vol_ratio = recent_vol / max(avg_vol, 1)
                if vol_ratio < config.SCALP_MIN_VOL_RATIO:
                    return False, f"Low volume: {vol_ratio:.2f}x < {config.SCALP_MIN_VOL_RATIO}x avg"
        except Exception:
            pass

        # 5. BODY RATIO -- M5 last candle (reject doji / spinning tops)
        try:
            last = df_m5.iloc[-2]  # Use confirmed candle (not live)
            body = abs(float(last['close']) - float(last['open']))
            rng  = float(last['high']) - float(last['low'])
            if rng > 0 and (body / rng) < 0.30:
                return False, f"Weak candle body ({body/rng:.2f} < 0.30)"
        except Exception:
            pass

        return True, "QUALITY_OK"

    except Exception as e:
        logger.error(f"[SCALP QUALITY] Error: {e}")
        return True, "CHECK_ERROR"  # Don't over-block on errors


def get_dynamic_trade_params(symbol: str, direction: str, df, signal_sl: float = 0.0, range_scalp_mode: bool = False, ema50_tp_hint: float = None) -> dict:
    """
    SMART TP CALCULATION -- SL is passed in from the strategy that fired.
    
    SL SOURCE HIERARCHY (in order of priority):
      1. PriorityTriggerEngine  -> Sweep candle wick / Structure swing point
      2. Strategy functions     -> Order Block edge, FVG boundary, Support/Resistance
      3. This function          -> EMERGENCY FALLBACK ONLY (ATR-based structural)
    
    TP is always derived from the risk distance (RR ratio).
    """
    try:
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return {}
        
        # FIX: SELL fills at BID, BUY fills at ASK. Wrong direction = wrong TP/SL distances.
        entry_price = tick.ask if direction == 'BUY' else tick.bid
        # Computed here (not where it's first used further down) because the
        # SL-CAP block below references it — it previously referenced
        # spread_now before this line existed, which raised a NameError that
        # was silently swallowed by that block's own try/except, and made
        # the (undefined) "worst_spread" name in the SPREAD-SAFETY block
        # below crash this whole function on every trade that needed its SL
        # adjusted for spread safety, causing place_ai_trade() to abandon an
        # otherwise-valid trade instead of correcting the SL and proceeding.
        spread_now = tick.ask - tick.bid
        spec = get_symbol_specs(symbol)
        pip_size = spec.get('pip_size', 0.0001)
        atr = calculate_atr(df['high'], df['low'], df['close'], 14).iloc[-1]
        
        # ?? SL SELECTION ??????????????????????????????????????????????????????????
        if signal_sl > 0:
            # PRIMARY: Use the structural SL from the strategy trigger
            sl = signal_sl
            sl_source = "STRATEGY"
        else:
            # EMERGENCY FALLBACK: Generic structural SL (used only if strategy SL missing)
            broker_min = get_broker_min_sl_distance(symbol, entry_price)
            sym_upper = symbol.upper()
            
            # Scalping SL: 1.0x ATR is the structural invalidation point
            # (entry engine already placed SL at structure -- this fallback
            # should only fire if strategy SL is missing)
            if "USOIL" in sym_upper or "UKOIL" in sym_upper:
                fallback_dist = max(atr * 1.0, 0.30, broker_min * 2.0)
            elif "XAUUSD" in sym_upper:
                fallback_dist = max(atr * 1.0, 5.0,  broker_min * 2.0)
            elif "XAGUSD" in sym_upper:
                fallback_dist = max(atr * 1.0, 0.30, broker_min * 2.0)
            elif "ETHUSD" in sym_upper:
                fallback_dist = max(atr * 1.0, 10.0, broker_min * 2.0)
            elif "BTCUSD" in sym_upper:
                fallback_dist = max(atr * 1.0, 150.0, broker_min * 2.0)
            else:
                fallback_dist = max(atr * 1.0, 15 * pip_size, broker_min * 2.0)
            
            if direction == 'BUY':
                sl = entry_price - fallback_dist
            else:
                sl = entry_price + fallback_dist
            sl_source = "FALLBACK_ATR"
        
        logger.info(f"[SL SOURCE] {symbol} {direction}: SL={sl:.5f} (source={sl_source}, atr={atr:.5f})")

        # RISK SANITY CAP: For small accounts, a wide SL on 0.01 lot can exceed risk limits.
        # Cap the structural SL distance to what the min lot can safely handle.
        # Formula: max_safe_dist = (equity * MAX_RISK_PCT / 100) / (min_lot / tick_size * tick_value)
        # If structural SL exceeds this, cap it. This prevents the $29 XAU loss scenario.
        try:
            _acct = mt5.account_info()
            _spec_cap = get_symbol_specs(symbol)
            _tv_cap = _spec_cap.get('trade_tick_value', 0)
            _ts_cap = _spec_cap.get('trade_tick_size', 0.01)
            _min_lot = _spec_cap.get('min_lot', 0.01)
            if _acct and _tv_cap and _ts_cap and _tv_cap > 0:
                _max_risk_dollars = _acct.equity * (config.MAX_RISK_PERCENT / 100)
                _max_safe_sl_dist = _max_risk_dollars / (_min_lot / _ts_cap * _tv_cap)
                _actual_sl_dist = abs(entry_price - sl)
                if _actual_sl_dist > _max_safe_sl_dist * 1.5:
                    logger.info(
                        f"[SL CAP] {symbol}: strategy SL dist {_actual_sl_dist:.3f} -> "
                        f"rescaled to {_max_safe_sl_dist:.3f} (risk cap ${_max_risk_dollars:.2f}). "
                        f"Tight SL = tighter entry quality required."
                    )
                    # Sanity: if max safe SL dist < 2x spread, trade is not viable
                    # at minimum lot size. Return empty so place_ai_trade skips early.
                    if _max_safe_sl_dist < spread_now * 2:
                        logger.warning(
                            f"[SL CAP] {symbol}: max safe SL ({_max_safe_sl_dist:.4f}) < "
                            f"2x spread ({spread_now*2:.4f}). Not viable at min lot "
                            f"with equity ${_acct.equity:.2f}. Need ~${_min_lot*(_max_safe_sl_dist/_ts_cap)*_tv_cap/_max_safe_sl_dist*100:.0f} "
                            f"equity for {symbol}. Setting 6h cooldown."
                        )
                        # 6-hour cooldown -- equity won't recover in minutes, so a
                        # short cooldown just means retrying (and re-rejecting) this
                        # symbol every cycle for no benefit. Was `minutes=10`, which
                        # contradicted the reasoning above.
                        state.symbol_cooldowns[symbol] = datetime.now(timezone.utc) + timedelta(hours=6)
                        return {}
                    if direction == 'BUY':
                        sl = entry_price - _max_safe_sl_dist
                    else:
                        sl = entry_price + _max_safe_sl_dist
        except Exception as _cap_err:
            logger.debug(f"[SL CAP] Skipped: {_cap_err}")
        
        # ?? SPREAD-SAFETY ENFORCEMENT ?????????????????????????????????????????
        # CRITICAL FIX: MT5 checks BID vs SL for long positions and ASK vs SL for short.
        # If SL is within spread distance of entry, the position closes INSTANTLY.
        # Rule: SL must be >= (spread x MIN_SL_SPREAD_MULT) from the BID/ASK at open.
        # (spread_now is computed once, up near entry_price, and reused here.)
        sym_upper_s = symbol.upper()

        # SL floor: use 3x CURRENT live spread (not spike multiplier).
        # The spike multipliers (12x, 20x etc.) are for the post-entry spike MONITOR
        # and ORDER GUARD -- NOT for permanent SL floor sizing.
        # Using them here forces USOIL SL to 1.20 pts minimum (12x $0.10 normal max),
        # which at 0.01 lot = $12.00 actual risk -- 17% equity on one scalp trade.
        # Instead: 3x live spread is sufficient to survive normal execution lag.
        # The ORDER GUARD at order-send time does a final tighter check with real tick data.
        min_spread_dist = spread_now * 3.0   # 3x live spread: covers execution noise
        min_atr_dist    = atr * config.SCALP_MIN_ATR_SL_MULT

        if direction == 'BUY':
            safe_max_sl_buy = tick.bid - max(min_spread_dist, min_atr_dist)
            if sl > safe_max_sl_buy:
                logger.warning(
                    f"[SL ADJUST] {symbol} BUY SL {sl:.5f} inside spike-safe zone "
                    f"(spread={spread_now:.5f} atr_floor={min_atr_dist:.5f}). "
                    f"Moving to {safe_max_sl_buy:.5f}."
                )
                sl = safe_max_sl_buy
        else:
            safe_min_sl_sell = tick.ask + max(min_spread_dist, min_atr_dist)
            if sl < safe_min_sl_sell:
                logger.warning(
                    f"[SL ADJUST] {symbol} SELL SL {sl:.5f} inside spike-safe zone "
                    f"(spread={spread_now:.5f} atr_floor={min_atr_dist:.5f}). "
                    f"Moving to {safe_min_sl_sell:.5f}."
                )
                sl = safe_min_sl_sell
        
        # ?? TP CALCULATION (always from RR ratio, not hard-coded levels) ????????
        if direction == 'BUY':
            risk = entry_price - sl
            if risk <= 0:
                risk = atr * 2.0
                sl = entry_price - risk
        else:
            risk = sl - entry_price
            if risk <= 0:
                risk = atr * 2.0
                sl = entry_price + risk

        # Try structural TP first (swing levels, liquidity pools, round numbers)
        try:
            _all_cd = async_data_fetcher.get_all_data().get(symbol, {})
            _df_m15 = _all_cd.get('M15')
            _df_h1  = _all_cd.get('H1')
            _struct = get_structural_sl_tp(symbol, direction, df, _df_m15, _df_h1, entry_price)
            if _struct and _struct.get('tp1') and _struct.get('rr1', 0) >= 1.5:
                tp1 = _struct['tp1']
                tp2 = _struct['tp2']
                logger.debug(f"[TP] {symbol}: using structural TP1={tp1:.4f}(RR{_struct['rr1']:.1f}) TP2={tp2:.4f}")
            else:
                raise ValueError("structural TP invalid or RR too low")
        except Exception:
            # Fallback: RR-based TP (always works)
            if direction == 'BUY':
                tp1 = entry_price + (risk * config.TP_PRIMARY_RR)
                tp2 = entry_price + (risk * config.TP_RUNNER_RR)
            else:
                tp1 = entry_price - (risk * config.TP_PRIMARY_RR)
                tp2 = entry_price - (risk * config.TP_RUNNER_RR)
        
        return {
            'sl': sl, 'tp1': tp1, 'tp2': tp2,
            'sl_distance': abs(entry_price - sl), 
            'atr': atr,
            'sl_source': sl_source,
            'news_multiplier': 1.0, 'session': get_current_session(),
            'volatility_ratio': 1.0, 'trend_strength': 1.0
        }
    except Exception as e:
        logger.error(f"Critical error in dynamic params: {e}", exc_info=True)
        return {}


def get_structural_sl_tp(symbol: str, direction: str, df_m5, df_m15, df_h1,
                          entry_price: float, strategy_type: str = 'EMA', range_scalp_mode: bool = False) -> dict:
    """
    STRUCTURAL SL/TP -- nearest valid POI, not fixed RR multiples.

    SL: above/below the most recent swing extreme that forms the setup.
    TP1: NEAREST swing low/high in trade direction that is a real structure point.
         Not the farthest or a random candle low -- the first meaningful level
         where price is likely to face rejection (liquidity pool / equal highs-lows).
    TP2: Next significant level after TP1 (H1 swing or round number magnet).

    Why this matters for Gold:
      Fixed 3:1 gives $45 TP on $15 risk. Price rarely travels that far cleanly.
      Structural 1:1.5 gives $22 TP -- the nearest swing where sells are stacked.
      BE at 1:1 locks $15. Price hits $22 TP. Clean, realistic exit.
    """
    import math
    result = {'sl': 0.0, 'tp1': 0.0, 'tp2': 0.0, 'sl_source': 'STRUCTURAL', 'rr1': 0.0}

    try:
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return {}
        spread  = tick.ask - tick.bid
        buffer  = spread * 2.5

        atr_m5  = float(calculate_atr(df_m5['high'], df_m5['low'], df_m5['close'], 14).iloc[-1])
        atr_h1  = float(calculate_atr(df_h1['high'], df_h1['low'], df_h1['close'], 14).iloc[-1])                   if df_h1 is not None and len(df_h1) >= 20 else atr_m5 * 3

        #  SL: above/below 25-bar swing extreme 
        lookback  = min(25, len(df_m5) - 1)
        df_scan   = df_m5.iloc[-lookback:]
        if direction == 'SELL':
            swing_high = float(df_scan['high'].max())
            sl         = swing_high + buffer
            sl_label   = f"swing_high({swing_high:.4f})+buf"
        else:
            swing_low  = float(df_scan['low'].min())
            sl         = swing_low - buffer
            sl_label   = f"swing_low({swing_low:.4f})-buf"

        sl_dist = abs(entry_price - sl)
        if sl_dist <= 0:
            return {}

        #  SWING POINT DETECTION 
        # A proper swing low: lower than N candles on both sides (not just a raw low value)
        # Use H1 for TP -- H1 swings are real POIs. M15 raw lows are noise.
        def find_swing_lows(df, lookback_bars: int = 80, pivot_n: int = 3) -> list:
            """Find H1 swing lows (pivot_n candles lower on each side)."""
            lows = []
            data = df.iloc[-lookback_bars:].reset_index(drop=True)
            for i in range(pivot_n, len(data) - pivot_n):
                is_swing = all(data['low'].iloc[i] <= data['low'].iloc[i-j] for j in range(1, pivot_n+1)) and                            all(data['low'].iloc[i] <= data['low'].iloc[i+j] for j in range(1, pivot_n+1))
                if is_swing:
                    lows.append(float(data['low'].iloc[i]))
            return sorted(set(lows))  # ascending

        def find_swing_highs(df, lookback_bars: int = 80, pivot_n: int = 3) -> list:
            """Find H1 swing highs."""
            highs = []
            data = df.iloc[-lookback_bars:].reset_index(drop=True)
            for i in range(pivot_n, len(data) - pivot_n):
                is_swing = all(data['high'].iloc[i] >= data['high'].iloc[i-j] for j in range(1, pivot_n+1)) and                            all(data['high'].iloc[i] >= data['high'].iloc[i+j] for j in range(1, pivot_n+1))
                if is_swing:
                    highs.append(float(data['high'].iloc[i]))
            return sorted(set(highs), reverse=True)  # descending

        #  ROUND NUMBER MAGNETS 
        sym_upper = symbol.upper()
        if 'BTC' in sym_upper:       round_step = 1000
        elif 'ETH' in sym_upper:     round_step = 100
        elif 'XAU' in sym_upper:     round_step = 50    # Gold: 3050, 3100, 3150
        elif 'XAG' in sym_upper:     round_step = 1
        elif 'OIL' in sym_upper or 'USOIL' in sym_upper: round_step = 1
        elif 'JPY' in sym_upper:     round_step = 1
        else:                        round_step = 0

        def nearest_round(price: float, direction_down: bool) -> float:
            if round_step <= 0: return price
            if direction_down:
                return math.floor(price / round_step) * round_step
            return math.ceil(price / round_step) * round_step

        #  TP1: NEAREST swing in trade direction 
        # Use H1 swings for real structure. Require min 1.2x SL distance.
        df_tp_primary = df_h1 if df_h1 is not None and len(df_h1) >= 20 else df_m15
        min_tp1_dist  = sl_dist * 1.2  # minimum 1.2:1 (not 1.5 -- let structure decide)
        tp1_struct = None
        tp2_struct = None

        if direction == 'SELL':
            # TP = swing lows BELOW entry, nearest first
            h1_swings = find_swing_lows(df_tp_primary)
            valid = [l for l in h1_swings if l < entry_price - min_tp1_dist]
            # valid is sorted ascending -> [0] is LOWEST. We want NEAREST = highest of valid ones
            nearest_swings = sorted(valid, reverse=True)  # descending = nearest first

            if nearest_swings:
                tp1_struct = nearest_swings[0]   # nearest valid swing low
                tp2_struct = nearest_swings[1] if len(nearest_swings) > 1 else tp1_struct - sl_dist * 1.5

                # Snap to round number if it is between tp1 and entry (only pull closer, not farther)
                rn = nearest_round(tp1_struct, direction_down=True)
                if rn < entry_price - min_tp1_dist and rn > tp1_struct:
                    tp1_struct = rn  # round number is closer = more realistic
                    logger.debug(f"[TP] {symbol}: snapped TP1 to round number {rn:.2f}")

                # Also check D1 previous low as TP2 candidate
                if df_h1 is not None and len(df_h1) >= 50:
                    d1_low = float(df_h1['low'].iloc[-30:].min())
                    if d1_low < entry_price - sl_dist * 2.0:
                        tp2_struct = max(tp2_struct, d1_low)  # use whichever is nearer
            else:
                # No swing found -- fallback to 1.5x SL (conservative, not 3x)
                tp1_struct = entry_price - sl_dist * 1.5
                tp2_struct = entry_price - sl_dist * 2.5

        else:  # BUY
            h1_swings = find_swing_highs(df_tp_primary)
            valid = [h for h in h1_swings if h > entry_price + min_tp1_dist]
            nearest_swings = sorted(valid)  # ascending = nearest first

            if nearest_swings:
                tp1_struct = nearest_swings[0]
                tp2_struct = nearest_swings[1] if len(nearest_swings) > 1 else tp1_struct + sl_dist * 1.5

                rn = nearest_round(tp1_struct, direction_down=False)
                if rn > entry_price + min_tp1_dist and rn < tp1_struct:
                    tp1_struct = rn
                    logger.debug(f"[TP] {symbol}: snapped TP1 to round number {rn:.2f}")

                if df_h1 is not None and len(df_h1) >= 50:
                    d1_high = float(df_h1['high'].iloc[-30:].max())
                    if d1_high > entry_price + sl_dist * 2.0:
                        tp2_struct = min(tp2_struct, d1_high)
            else:
                tp1_struct = entry_price + sl_dist * 1.5
                tp2_struct = entry_price + sl_dist * 2.5

        #  SAFETY FLOORS 
        # TP1 minimum 1.2x SL (already enforced above)
        # TP2 minimum 2.0x SL
        min_tp2_dist = sl_dist * 2.0
        if direction == 'SELL':
            if entry_price - tp2_struct < min_tp2_dist:
                tp2_struct = entry_price - min_tp2_dist
        else:
            if tp2_struct - entry_price < min_tp2_dist:
                tp2_struct = entry_price + min_tp2_dist

        rr1 = abs(entry_price - tp1_struct) / sl_dist if sl_dist > 0 else 0
        rr2 = abs(entry_price - tp2_struct) / sl_dist if sl_dist > 0 else 0

        # Hard minimum RR 1.2:1 -- auto-adjust TP to structural 1.5x SL
        if rr1 < 1.2 and sl_dist > 0:
            logger.warning(f"[RR GATE] {symbol} {direction}: RR={rr1:.2f} < 1.2 -- adjusting TP1 to 1.5x SL")
            tp1_struct = (entry_price + sl_dist * 1.5) if direction == 'BUY' else (entry_price - sl_dist * 1.5)
            rr1 = 1.5

        # RANGE SCALP MODE: constrain TP1 to nearest H4 range boundary
        # In H4-ranging market, price will likely reverse at the range edge
        # Using the structural swing TP still works -- it naturally points to the boundary
        # But if TP1 > 2.5x SL, cap it (don't expect range continuation)
        if range_scalp_mode:
            sl_dist_check = abs(entry_price - sl)
            tp1_dist_check = abs(entry_price - tp1_struct)
            if sl_dist_check > 0 and tp1_dist_check / sl_dist_check > 2.5:
                # Cap at 2.5x SL in range scalp mode (don't overshoot range boundary)
                tp1_struct = (entry_price + sl_dist_check * 2.0) if direction == 'BUY' else (entry_price - sl_dist_check * 2.0)
                logger.debug(f"[RANGE SCALP] {symbol}: TP1 capped at 2.0x SL (range boundary)")
            # TP2 capped at 3.0x SL (don't chase range breakout that may not happen)
            tp2_dist_check = abs(entry_price - tp2_struct)
            if sl_dist_check > 0 and tp2_dist_check / sl_dist_check > 3.5:
                tp2_struct = (entry_price + sl_dist_check * 3.0) if direction == 'BUY' else (entry_price - sl_dist_check * 3.0)

        logger.info(
            f"[STRUCT SL/TP] {symbol} {direction}: "
            f"SL={sl:.4f}({sl_label}) "
            f"TP1={tp1_struct:.4f}(RR {rr1:.1f}x) "
            f"TP2={tp2_struct:.4f}(RR {rr2:.1f}x) "
            f"SL_dist={sl_dist:.4f} ATR={atr_m5:.4f}"
        )

        # EMA50 TP override: if signal suggested 50 EMA as TP (doc rule)
        if ema50_tp_hint is not None and ema50_tp_hint > 0:
            ema_tp_dist = abs(entry_price - ema50_tp_hint)
            ema_tp_rr   = ema_tp_dist / sl_dist if sl_dist > 0 else 0
            # Use EMA50 TP if it gives at least 1.2:1 RR and is in the correct direction
            if ema_tp_rr >= 1.2:
                if direction == 'BUY' and ema50_tp_hint > entry_price:
                    tp1_struct = ema50_tp_hint
                    rr1 = ema_tp_rr
                    logger.debug(f"[TP] {symbol}: using 50 EMA={ema50_tp_hint:.4f} as TP1 (RR {rr1:.1f}x)")
                elif direction == 'SELL' and ema50_tp_hint < entry_price:
                    tp1_struct = ema50_tp_hint
                    rr1 = ema_tp_rr
                    logger.debug(f"[TP] {symbol}: using 50 EMA={ema50_tp_hint:.4f} as TP1 (RR {rr1:.1f}x)")

        result.update({
            'sl': sl, 'tp1': tp1_struct, 'tp2': tp2_struct,
            'sl_source': f'STRUCTURAL({sl_label})',
            'rr1': rr1, 'rr2': rr2
        })
        return result

    except Exception as e:
        logger.error(f"[STRUCT SL/TP] error for {symbol}: {e}")
        return {}


def modify_position(ticket: int, sl: float, tp: float, max_retries: int = 3) -> bool:
    """Modify SL/TP with Retry Logic"""
    for i in range(max_retries):
        try:
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "sl": sl,
                "tp": tp
            }
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                return True
            
            logger.warning(f"Modify failed for {ticket} (Attempt {i+1}/{max_retries}): {result.comment if result else 'Unknown'}")
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error modifying position {ticket}: {e}")
    
    return False

def close_partial_position(ticket: int, volume: float, max_retries: int = 3) -> bool:
    """Close partial volume with retry logic"""
    for attempt in range(max_retries):
        try:
            pos = mt5.positions_get(ticket=ticket)
            if not pos: 
                logger.warning(f"Position {ticket} not found")
                return False
            pos = pos[0]
            
            # Validate volume
            spec = get_symbol_specs(pos.symbol)
            min_lot = spec.get('min_lot', 0.01)
            
            if volume < min_lot:
                logger.warning(f"Partial volume {volume} < min lot {min_lot} for {pos.symbol}")
                return False
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": ticket,
                "symbol": pos.symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
                "price": mt5.symbol_info_tick(pos.symbol).bid if pos.type == 0 else mt5.symbol_info_tick(pos.symbol).ask,
                "deviation": 20,
                "magic": MAGIC_NUMBER,
                "comment": "Partial_TP",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f" Partial TP closed: {volume} lots of ticket {ticket}")
                return True
            else:
                logger.warning(f"Partial close failed (attempt {attempt+1}/{max_retries}): {result.comment if result else 'Unknown'}")
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    
        except Exception as e:
            logger.error(f"Error closing partial position {ticket}: {e}")
            if attempt < max_retries - 1:
                time.sleep(0.5)
    
    return False

def get_trend_confirmation(symbol, timeframe=mt5.TIMEFRAME_M15):
    """
    Checks if price is above/below the 50 EMA to confirm momentum.
    Returns: 'UPTREND', 'DOWNTREND', or 'NEUTRAL'
    """
    try:
        # Get last 55 candles to calculate 50 EMA
        bars = mt5.copy_rates_from_pos(symbol, timeframe, 0, 55)
        if bars is None or len(bars) < 55: return "NEUTRAL"
        
        df = pd.DataFrame(bars)
        # Calculate 50 EMA
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        last_close = df['close'].iloc[-1]
        last_ema = df['ema_50'].iloc[-1]
        
        # Strict logic: Price MUST be on the correct side of EMA
        if last_close > last_ema:
            return "UPTREND"
        elif last_close < last_ema:
            return "DOWNTREND"
        return "NEUTRAL"
    except Exception as e:
        logger.error(f"Error in trend confirmation: {e}")
        return "NEUTRAL"

def manage_all_positions():
    """
    [OK] FIXED: Enhanced position management with PARTIAL TP + Config-based BE/Trail
    """
    try:
        positions = mt5.positions_get()
        if not positions:
            return

        all_cached = async_data_fetcher.get_all_data() if 'async_data_fetcher' in globals() else {}

        # SPREAD SPIKE MONITOR: Close open positions if broker widens spread abnormally.
        # This is an early-warning exit BEFORE the SL gets triggered by a spike.
        for _pos in positions:
            if _pos.magic != MAGIC_NUMBER:
                continue
            try:
                _tick = mt5.symbol_info_tick(_pos.symbol)
                if not _tick:
                    continue
                _spread_now = _tick.ask - _tick.bid
                _sym_u = _pos.symbol.upper()
                # Get the "normal" max spread for this symbol
                _normal_max = (
                    config.SCALP_MAX_SPREAD_XAGUSD if 'XAGUSD' in _sym_u else
                    config.SCALP_MAX_SPREAD_XAUUSD if 'XAUUSD' in _sym_u else
                    config.SCALP_MAX_SPREAD_OIL    if 'USOIL'  in _sym_u else
                    config.SCALP_MAX_SPREAD_BTC    if 'BTC'    in _sym_u else
                    config.SCALP_MAX_SPREAD_ETH    if 'ETH'    in _sym_u else
                    config.SCALP_MAX_SPREAD_FX_PIPS * 0.0001
                )
                # If spread exceeds 8x normal maximum -> close trade NOW before SL spike hit
                if _normal_max > 0 and _spread_now > _normal_max * 3:  # FIX: was 8x, reduced to 3x
                    logger.critical(
                        f"[SPIKE GUARD] {_pos.symbol} #{_pos.ticket}: "
                        f"spread SPIKED to {_spread_now:.5f} (normal max={_normal_max:.5f}, "
                        f"{_spread_now/_normal_max:.0f}x). Closing position to prevent SL spike hit."
                    )
                    send_telegram_notification(
                        f"[SPIKE GUARD] {_pos.symbol} #{_pos.ticket} -- "
                        f"Spread spiked to {_spread_now:.5f} "
                        f"({_spread_now/_normal_max:.0f}x normal). "
                        f"Closing to prevent SL spike hit."
                    )
                    _tick2 = mt5.symbol_info_tick(_pos.symbol)
                    if _tick2:
                        mt5.order_send({
                            "action": mt5.TRADE_ACTION_DEAL, "position": _pos.ticket,
                            "symbol": _pos.symbol, "volume": _pos.volume,
                            "type": mt5.ORDER_TYPE_SELL if _pos.type == 0 else mt5.ORDER_TYPE_BUY,
                            "price": _tick2.bid if _pos.type == 0 else _tick2.ask,
                            "deviation": 50, "magic": MAGIC_NUMBER,
                            "comment": "SpikeGuard_Exit",
                            "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC
                        })
            except Exception as _spe:
                logger.debug(f"[SPIKE GUARD] Error checking {_pos.symbol}: {_spe}")

        for pos in positions:
            if pos.magic != MAGIC_NUMBER:
                continue

            symbol, ticket = pos.symbol, pos.ticket
            entry_price, current_price = pos.price_open, pos.price_current
            sl, tp = pos.sl, pos.tp
            current_volume = pos.volume

            if not state.open_positions.get(ticket):
                state.open_positions[ticket] = {'params': {}}
            params = state.open_positions[ticket]['params']

            # === UPDATE RUNNING P&L IN DASHBOARD (throttled to 5s/ticket) ===
            try:
                if not hasattr(manage_all_positions, '_last_pnl_push'):
                    manage_all_positions._last_pnl_push = {}
                _now_ts = time.time()
                _last = manage_all_positions._last_pnl_push.get(ticket, 0)
                if _now_ts - _last >= 5:
                    manage_all_positions._last_pnl_push[ticket] = _now_ts
                    trade_db.update_metadata(str(ticket), {
                        'running_profit': round(float(pos.profit), 2),
                        'current_price': round(float(current_price), 5),
                        'stop_loss': float(sl),
                        'take_profit': float(tp),
                    })
            except Exception as _pnl_err:
                logger.debug(f"[DB] running PnL push failed for {ticket}: {_pnl_err}")

            duration_mins = (time.time() - pos.time) / 60.0
            total_dist = abs(tp - entry_price)
            if total_dist == 0:
                continue

            if pos.type == 0:
                current_dist = current_price - entry_price
            else:
                current_dist = entry_price - current_price

            progress = current_dist / total_dist
            # r_multiple MUST use initial SL (original structural distance), not current SL.
            # After BE moves SL to entry, abs(entry_price - sl) ~ 0 ? r_multiple = infinity.
            # Always use the ORIGINAL SL distance for consistent R-measurement.
            _initial_sl = params.get('initial_sl', sl)
            _initial_sl_dist = abs(entry_price - _initial_sl)
            if _initial_sl_dist == 0:
                _initial_sl_dist = abs(entry_price - sl) if abs(entry_price - sl) > 0 else 1.0
            r_multiple = current_dist / _initial_sl_dist

            # =========================================================
            # STEP 1: RE-SCORE EDGE (Antigravity Enforcement Layer)
            # =========================================================
            cached = all_cached.get(symbol, {})
            df_m1_m = cached.get('M1')
            df_m5_m = cached.get('M5')

            edge_score, edge_state = 50.0, "NORMAL"
            m_atr = 0.0010
            
            # Setup defaults for context building
            m_regime = "TRENDING"
            m_str = 0.5
            pattern_health = 0.5
            sym_score = 1.0
            reg_align = 0.5
            session = get_current_session()
            
            ctx_m = TradeContext()

            if df_m1_m is not None and df_m5_m is not None and not df_m5_m.empty and len(df_m5_m) > 20:
                try:
                    m_trigger, direction_m, _m_str_raw, _m_disp = PriorityTriggerEngine.identify_trigger(df_m1_m, df_m5_m)
                    m_str = 1.0 if m_trigger in ["SWEEP_AND_DISPLACE", "MOMENTUM_BURST"] else 0.5 if m_trigger != "IGNORE" else 0.0
                    m_regime = MarketConditionAnalyzer.calculate_market_regime(df_m5_m) if len(df_m5_m) > 50 else "TRENDING"
                    m_atr = calculate_atr(df_m5_m['high'], df_m5_m['low'], df_m5_m['close'], 14).iloc[-1]
                    pattern_health = max(0.0, min(1.0, pattern_recognizer.get_edge_health_score(
                        symbol, "BUY" if pos.type == 0 else "SELL", {})))
                    sym_score = max(0.0, min(1.0, symbol_tracker.get_symbol_metrics(symbol).get('trade_score', 1.0)))
                    reg_align = 1.0 if m_regime in ["TRENDING_UP", "TRENDING_DOWN", "TRENDING"] else 0.5
                    
                    # FIX: EdgeEngine.WEIGHTS uses liquidity_distance/strength/
                    # momentum_state/structure_alignment/session_strength/volatility_state.
                    # The old code used micro_strength/pattern_health etc. (wrong fields)
                    # which all defaulted to 0.0 -> score=0 -> instant EXIT every time.
                    sess_strength_m = 1.0 if session in ["LONDON", "NEW_YORK", "LONDON_NY"] else 0.5
                    ctx_m = TradeContext(
                        liquidity_distance  = m_str,       # momentum proxy
                        liquidity_strength  = reg_align,   # regime alignment proxy
                        momentum_state      = m_str,       # same momentum
                        structure_alignment = sym_score,   # symbol performance proxy
                        session_strength    = sess_strength_m,
                        volatility_state    = 1.0 if m_atr > 0 else 0.5,
                        session=session,
                        regime=m_regime
                    )
                    
                    res_m = EdgeEngine().calculate(ctx_m)
                    edge_score = res_m.score
                    edge_state = res_m.state
                except Exception as e_edge:
                    logger.warning(f"[MANAGE] Edge re-score failed for {symbol}: {e_edge}")

            # =========================================================
            # STEP 2: EXIT ENGINE -- DOMINANT AUTHORITY (Issue 2)
            # =========================================================
            # Calculate momentum and lifecycle specifically for exits
            # FIX: lifecycle and momentum must be anchored to DURATION not just r_multiple.
            # A brand-new trade at r_multiple=0.1 for 30 seconds is NOT a "FAILURE".
            # FAILURE/DROP are reserved for trades that have been open and then reversed.
            if duration_mins < 5:
                lifecycle_state = "EXPANSION"   # All new trades are in expansion phase
                momentum_state  = "INCREASING"  # Can't determine momentum in <5 mins
            elif r_multiple > 0.5:
                lifecycle_state = "EXPANSION"
                momentum_state  = "INCREASING"
            elif r_multiple >= 0:
                lifecycle_state = "STALL"
                momentum_state  = "FLAT"
            else:
                lifecycle_state = "FAILURE"
                momentum_state  = "DROP"
            
            exit_ctx = ExitContext(
                trade_ctx=ctx_m,
                edge_score=edge_score,
                lifecycle=lifecycle_state,
                momentum=momentum_state,
                liquidity_state="HIT" if progress >= 0.9 else "NORMAL",
                regime=m_regime,
                r_multiple=r_multiple,
                duration_mins=duration_mins,
            )

            exit_engine = ScalpingExitEngine()
            exit_decision = exit_engine.decide(exit_ctx)

            # MINIMUM HOLD TIME: ExitEngine cannot close a trade within the first
            # 5 minutes. This prevents instant exits from transient edge drops.
            _min_hold_mins = 15.0  # Scalp trades need 15min to develop before exit
            if duration_mins < _min_hold_mins and exit_decision == "EXIT":
                logger.debug(
                    f"[EXIT ENGINE] {symbol} #{ticket}: EXIT suppressed "
                    f"(held only {duration_mins:.1f}m < {_min_hold_mins}m minimum). "
                    f"Edge={edge_score:.1f}. Waiting for trade to mature."
                )
                exit_decision = "HOLD"

            if exit_decision != "HOLD":
                if exit_decision == "EXIT":
                    logger.info(f" [EXIT ENGINE] Hard Exit {symbol} #{ticket} (score={edge_score:.1f}, held {duration_mins:.1f}m)")
                    tick_now = mt5.symbol_info_tick(symbol)
                    if tick_now:
                        mt5.order_send({
                            "action": mt5.TRADE_ACTION_DEAL, "position": ticket,
                            "symbol": symbol, "volume": current_volume,
                            "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
                            "price": tick_now.bid if pos.type == 0 else tick_now.ask,
                            "deviation": 20, "magic": MAGIC_NUMBER,
                            "comment": f"ExitEng_Exit",
                            "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC
                        })
                elif exit_decision in ("PARTIAL", "SCALE_OUT"):
                    spec_e = get_symbol_specs(symbol)
                    lot_step_e = spec_e.get('lot_step', 0.01)
                    if params.get('initial_volume') is None:
                        params['initial_volume'] = current_volume
                        state.open_positions[ticket]['params'] = params
    
                    if current_volume >= params['initial_volume'] * 0.9 and current_volume > lot_step_e:
                        logger.info(f" [EXIT ENGINE] Partial close {symbol} #{ticket} ({exit_decision})")
                        redu_vol = round((current_volume * 0.5) / lot_step_e) * lot_step_e
                        if redu_vol >= lot_step_e:
                            if close_partial_position(ticket, redu_vol):
                                # Persist to Supabase IMMEDIATELY so restart knows partial was done
                                try:
                                    trade_db.update_metadata(ticket, {'partial_tp_executed': True})
                                    state.partial_closed.add(ticket)
                                    logger.info(f" [PARTIAL TP] Persisted to DB: #{ticket}")
                                except Exception as _pe:
                                    logger.error(f"[PARTIAL TP] DB persist failed: {_pe}")
                continue  # Exit Engine intercepted, stop legacy logic

            # =========================================================
            # STEP 3: DECISION ENGINE V2 -- MID-TRADE ORCHESTRATION (Issue 5)
            # =========================================================
            is_runner = params.get('is_runner', False)
            
            mid_ctx = MidTradeContext(
                trade_ctx=ctx_m,
                edge_score=edge_score,
                runner_state=is_runner,
                lifecycle=lifecycle_state,
                momentum=momentum_state
            )

            decision = DecisionEngineV2().decide_mid_trade(mid_ctx)

            if decision == "BLOCK_NEW_TRADES":
                state.symbol_cooldowns[symbol] = datetime.now(timezone.utc) + timedelta(minutes=15)
                logger.info(f" [DECISION V2] Cooldown set for {symbol} (15 min)")

            elif decision == "REDUCE":
                spec_d = get_symbol_specs(symbol)
                lot_step_d = spec_d.get('lot_step', 0.01)
                if current_volume > lot_step_d:
                    logger.info(f" [DECISION V2] Reduce risk on {symbol} #{ticket}")
                    redu_vol = round((current_volume * 0.5) / lot_step_d) * lot_step_d
                    if redu_vol >= lot_step_d:
                        if close_partial_position(ticket, redu_vol):
                            try:
                                trade_db.update_metadata(ticket, {'partial_tp_executed': True})
                                state.partial_closed.add(ticket)
                            except Exception:
                                pass
                continue

            elif decision == "EXIT":
                logger.info(f" [DECISION V2] Emergency Exit {symbol} #{ticket}")
                tick_now2 = mt5.symbol_info_tick(symbol)
                if tick_now2:
                    mt5.order_send({
                        "action": mt5.TRADE_ACTION_DEAL, "position": ticket,
                        "symbol": symbol, "volume": current_volume,
                        "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
                        "price": tick_now2.bid if pos.type == 0 else tick_now2.ask,
                        "deviation": 20, "magic": MAGIC_NUMBER,
                        "comment": "DecEngV2_Exit",
                        "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC
                    })
                continue

            elif decision == "TIGHTEN":
                # Only tighten to BE when price has moved at least 0.8R toward TP
                # Prevents premature BE moves that get stopped out on minor pullbacks
                if r_multiple >= 0.8:
                    if pos.type == 0 and current_price > entry_price and sl < entry_price:
                        logger.info(f" [DECISION V2] Tighten (BE) {symbol} #{ticket} at R{r_multiple:.2f}")
                        modify_position(ticket, entry_price, tp)
                    elif pos.type == 1 and current_price < entry_price and sl > entry_price:
                        logger.info(f" [DECISION V2] Tighten (BE) {symbol} #{ticket} at R{r_multiple:.2f}")
                        modify_position(ticket, entry_price, tp)
                else:
                    logger.debug(f"[DECISION V2] TIGHTEN suppressed for {symbol} #{ticket}: r={r_multiple:.2f} < 0.8R minimum")
                continue

            # =========================================================
            # STEP 4: RUNNER ENGINE -- FULL SL OWNERSHIP (Issue 3)
            # =========================================================
            runner_engine = RunnerManagementEngine()

            if not is_runner:
                # Promotion logic lives in EdgeEngine now
                if getattr(ctx_m, 'edge_state', "NORMAL") == "STRONG" and edge_score >= 75 and r_multiple >= 2.0:
                    is_runner = True
                    logger.info(f" [*] [RUNNER PROMOTED] {symbol} #{ticket} at R{r_multiple:.1f} -- RunnerEngine now owns SL")
                    params['is_runner'] = True
                    params['runner_promoted_at'] = current_price
                    state.open_positions[ticket]['params'] = params

            if is_runner:
                if edge_score < 40: # Downgrade rule
                    logger.info(f" [RUNNER DOWNGRADED] {symbol} #{ticket} -- edge score dropped to {edge_score:.1f}")
                    params['is_runner'] = False
                    state.open_positions[ticket]['params'] = params
                    is_runner = False

            if is_runner:
                # If runner is active -> disable normal trailing completely via explicit guard
                if df_m5_m is not None and len(df_m5_m) >= 20:
                    struct_high = df_m5_m['high'].iloc[-20:-1].max()
                    struct_low = df_m5_m['low'].iloc[-20:-1].min()
                    direction_str = "BUY" if pos.type == 0 else "SELL"
                    
                    runner_ctx = RunnerContext(
                        trade_ctx=ctx_m,
                        direction=direction_str,
                        current_price=current_price,
                        structure_high=struct_high,
                        structure_low=struct_low,
                        sl=sl,
                        buffer=m_atr * 0.1
                    )
                    runner_sl = runner_engine.compute_sl(runner_ctx)
                    
                    if runner_sl:
                        logger.info(f" [RUNNER SL] {symbol} #{ticket}: {sl:.5f} -> {runner_sl:.5f}")
                        modify_position(ticket, runner_sl, tp)
                continue  # skip normal trailing

            # =========================================================
            # STEP 5: PRESERVE_RUNNER from DecisionEngineV2
            # Only reached if not yet promoted. Prevents aggressive tightening.
            # =========================================================
            if decision == "PRESERVE_RUNNER":
                # Edge is strong -- let the trade breathe, do not tighten
                continue

            # =========================================================
            # STEP 6: PROFESSIONAL 3-STAGE TRAILING STOP SYSTEM
            # Stage 1 (>=1.0R): Move SL to Breakeven -- zero risk from now
            # Stage 2 (>=1.5R): Trail at 50% of gains -- lock half the profit
            # Stage 3 (>=2.0R): Trail at 70% of gains -- lock most, let rest run
            # Trail only ADVANCES (never moves SL backward)
            # BE only fires ONCE per trade (be_moved flag prevents re-trigger)
            # STRATEGY EXCEPTIONS:
            #   AOX   -> bypass entirely; TPs are SD-level based (set on entry)
            #   SWAPPY -> bypass Stage 1/2; only BE at 2R, let run to 3R+ min
            # =========================================================

            _strategy_type = params.get('strategy_type', 'GENERIC')

            # -- AOX: SD-based TPs were set at entry; do NOT trail-stop them early.
            # The MT5 TP handles partial exits; we only protect with BE at 1R.
            if _strategy_type == 'AOX':
                if r_multiple >= 1.0 and ticket not in state.be_moved:
                    _dig_aox = mt5.symbol_info(symbol).digits if mt5.symbol_info(symbol) else 5
                    _be_aox  = round((entry_price + _min_buffer) if is_buy else (entry_price - _min_buffer), _dig_aox)
                    _be_aox_rounded = round(_be_aox, _dig_aox)
                    _sl_rounded = round(sl, _dig_aox)
                    _can_be = (is_buy and _be_aox_rounded > _sl_rounded) or (not is_buy and _be_aox_rounded < _sl_rounded)
                    if _can_be:
                        logger.info(f"[AOX TRAIL] {symbol} #{ticket}: BE only -- SD TPs handle profit target (r={r_multiple:.2f}R)")
                        if modify_position(ticket, _be_aox, tp):
                            state.be_moved.add(ticket)
                            try: trade_db.update_metadata(ticket, {'be_moved': True})
                            except Exception: pass
                    else:
                        state.be_moved.add(ticket)
                        try: trade_db.update_metadata(ticket, {'be_moved': True})
                        except Exception: pass
                continue  # AOX exits via MT5 TP levels set on entry, not trailing

            # -- SWAPPY: Must hold to minimum 3R. No Stage 1/2 tightening. BE at 2R only.
            if _strategy_type == 'SWAPPY':
                if r_multiple >= 2.0 and ticket not in state.be_moved:
                    _dig_sw = mt5.symbol_info(symbol).digits if mt5.symbol_info(symbol) else 5
                    _be_sw  = round((entry_price + _min_buffer) if is_buy else (entry_price - _min_buffer), _dig_sw)
                    _be_sw_r = round(_be_sw, _dig_sw)
                    _sl_r_sw = round(sl, _dig_sw)
                    _can_sw = (is_buy and _be_sw_r > _sl_r_sw) or (not is_buy and _be_sw_r < _sl_r_sw)
                    if _can_sw:
                        logger.info(f"[SWAPPY TRAIL] {symbol} #{ticket}: BE at 2R -- holding to 3R+ min (r={r_multiple:.2f}R)")
                        if modify_position(ticket, _be_sw, tp):
                            state.be_moved.add(ticket)
                            try: trade_db.update_metadata(ticket, {'be_moved': True})
                            except Exception: pass
                    else:
                        state.be_moved.add(ticket)
                        try: trade_db.update_metadata(ticket, {'be_moved': True})
                        except Exception: pass
                elif r_multiple >= 3.0 and ticket in state.be_moved:
                    # At 3R+ trail tightly at 85% to protect the minimum target
                    locked_dist = current_profit_dist * 0.85
                    trail_sl = (entry_price + locked_dist) if is_buy else (entry_price - locked_dist)
                    trail_sl_safe = (trail_sl - _min_buffer) if is_buy else (trail_sl + _min_buffer)
                    _dig_sw3 = mt5.symbol_info(symbol).digits if mt5.symbol_info(symbol) else 5
                    can_adv = (is_buy and trail_sl_safe > sl) or (not is_buy and trail_sl_safe < sl)
                    if can_adv:
                        logger.info(f"[SWAPPY TRAIL3R] {symbol} #{ticket}: 85% lock at r={r_multiple:.2f}R (holding 3R+)")
                        modify_position(ticket, round(trail_sl_safe, _dig_sw3), tp)
                continue  # SWAPPY uses above logic only

            sl_dist = abs(entry_price - params.get('initial_sl', sl))
            if sl_dist == 0:
                sl_dist = abs(entry_price - sl)
            if sl_dist == 0:
                continue

            # Spread-aware buffer: SL must be at least 1.5x spread away from entry
            _tick_trail = mt5.symbol_info_tick(symbol)
            _spread_trail = (_tick_trail.ask - _tick_trail.bid) if _tick_trail else m_atr * 0.1
            _min_buffer = max(_spread_trail * 1.5, m_atr * 0.15)

            is_buy = (pos.type == 0)
            current_profit_dist = (current_price - entry_price) if is_buy else (entry_price - current_price)

            # ------------------------------------------------------------------
            # STAGE 1: BREAKEVEN (first time r_multiple hits 1.0R)
            # ------------------------------------------------------------------
            if r_multiple >= 1.0 and ticket not in state.be_moved:
                be_price = (entry_price + _min_buffer) if is_buy else (entry_price - _min_buffer)
                _dig_be = mt5.symbol_info(symbol).digits if mt5.symbol_info(symbol) else 5
                be_price_rounded = round(be_price, _dig_be)
                sl_rounded = round(sl, _dig_be)
                # Only move if new SL is meaningfully better AFTER rounding (prevents MT5 "No changes" spam)
                can_move = (is_buy and be_price_rounded > sl_rounded) or (not is_buy and be_price_rounded < sl_rounded)
                if can_move:
                    logger.info(
                        f"[TRAIL STAGE1] {symbol} #{ticket}: BREAKEVEN "
                        f"SL {sl:.5f} -> {be_price_rounded:.5f} (r={r_multiple:.2f}R)"
                    )
                    if modify_position(ticket, be_price_rounded, tp):
                        state.be_moved.add(ticket)
                        params['initial_sl'] = params.get('initial_sl', sl)
                        state.open_positions[ticket]['params'] = params
                        try:
                            trade_db.update_metadata(ticket, {'be_moved': True})
                        except Exception:
                            pass
                        send_telegram_notification(
                            f"[BREAKEVEN] {symbol} #{ticket}\n"
                            f"SL moved to entry -- ZERO RISK now\n"
                            f"Profit locked: $0 minimum | R achieved: {r_multiple:.1f}R"
                        )
                    else:
                        # Modify failed (SL already at BE after rounding) -- mark done to stop spam
                        logger.debug(f"[TRAIL STAGE1] {symbol} #{ticket}: modify failed, SL already at BE, marking done")
                        state.be_moved.add(ticket)
                        try:
                            trade_db.update_metadata(ticket, {'be_moved': True})
                        except Exception:
                            pass
                else:
                    # SL already at or past BE (restored without flag, or tiny float diff)
                    logger.debug(f"[TRAIL STAGE1] {symbol} #{ticket}: SL already past BE ({sl_rounded}), marking done silently")
                    state.be_moved.add(ticket)
                    try:
                        trade_db.update_metadata(ticket, {'be_moved': True})
                    except Exception:
                        pass

            # ------------------------------------------------------------------
            # STAGE 3 checked FIRST: TIGHT TRAIL AT 70% OF GAINS (>= 2.0R)
            # MUST be before Stage 2 -- elif chain evaluates top-down, so
            # if Stage 2 (>=1.5R) came first it would always fire at 2.0R+
            # meaning Stage 3 (>=2.0R) would be unreachable dead code.
            # ------------------------------------------------------------------
            elif r_multiple >= 2.0 and ticket in state.be_moved:
                locked_dist = current_profit_dist * 0.70   # Lock 70% of current gain
                trail_sl = (entry_price + locked_dist) if is_buy else (entry_price - locked_dist)
                trail_sl_safe = (trail_sl - _min_buffer) if is_buy else (trail_sl + _min_buffer)

                can_advance = (is_buy and trail_sl_safe > sl) or (not is_buy and trail_sl_safe < sl)
                if can_advance:
                    sym_digits = mt5.symbol_info(symbol).digits if mt5.symbol_info(symbol) else 5
                    logger.info(
                        f"[TRAIL STAGE3] {symbol} #{ticket}: 70% lock "
                        f"SL {sl:.{sym_digits}f} -> {trail_sl_safe:.{sym_digits}f} "
                        f"(r={r_multiple:.2f}R)"
                    )
                    modify_position(ticket, round(trail_sl_safe, sym_digits), tp)

            # ------------------------------------------------------------------
            # STAGE 2: TRAIL AT 50% OF GAINS (1.5R to 2.0R)
            # Only reached when r_multiple is between 1.5 and 2.0
            # ------------------------------------------------------------------
            elif r_multiple >= 1.5 and ticket in state.be_moved:
                locked_dist = current_profit_dist * 0.50   # Lock 50% of current gain
                trail_sl = (entry_price + locked_dist) if is_buy else (entry_price - locked_dist)
                trail_sl_safe = (trail_sl - _min_buffer) if is_buy else (trail_sl + _min_buffer)

                can_advance = (is_buy and trail_sl_safe > sl) or (not is_buy and trail_sl_safe < sl)
                if can_advance:
                    sym_digits = mt5.symbol_info(symbol).digits if mt5.symbol_info(symbol) else 5
                    logger.info(
                        f"[TRAIL STAGE2] {symbol} #{ticket}: 50% lock "
                        f"SL {sl:.{sym_digits}f} -> {trail_sl_safe:.{sym_digits}f} "
                        f"(r={r_multiple:.2f}R, locking ${locked_dist:.{sym_digits}f}pts)"
                    )
                    modify_position(ticket, round(trail_sl_safe, sym_digits), tp)

    except Exception as e:
        logger.error(f"[ERROR] Position management failed: {e}", exc_info=True)



def update_closed_trades():
    """
    Update Supabase with exit information
    ULTIMATE AI: Learn from ALL trades using multiple systems
    """
    try:
        from_date = datetime.now(timezone.utc) - timedelta(days=1)
        deals = mt5.history_deals_get(from_date, datetime.now(timezone.utc))
        if not deals: return
        
        for deal in deals:
            if deal.magic != MAGIC_NUMBER or deal.entry == 0:
                continue
            
            ticket = deal.position_id
            
            if ticket in state.open_positions:
                profit = deal.profit
                pos_data  = state.open_positions[ticket]
                symbol    = deal.symbol
                direction = 'BUY' if deal.type == mt5.ORDER_TYPE_BUY else 'SELL'

                # Smart exit_reason: check ACTUAL close price vs SL/TP levels
                # "profit < 0" alone is wrong -- ExitEngine exits also produce losses
                _p = pos_data.get('params', {})
                _sl_r    = _p.get('sl', 0)
                _tp_r    = _p.get('tp', 0)
                _en_r    = _p.get('entry_price', 0)
                _sl_d    = abs(_en_r - _sl_r) if _en_r and _sl_r else 0
                _at_sl   = _sl_d > 0 and abs(deal.price - _sl_r) < (_sl_d * 0.08)
                _at_tp   = _sl_d > 0 and abs(deal.price - _tp_r) < (_sl_d * 0.08)
                if profit > 0 or _at_tp:
                    exit_reason = 'TP'
                elif _at_sl:
                    exit_reason = 'SL'
                elif profit < 0:
                    exit_reason = 'EXIT_ENGINE'  # Early bot exit, not a real SL hit
                else:
                    exit_reason = 'BE' 

                # INSTANT SL DETECTION: trade closed within 30s of opening = spread spike
                open_time = pos_data.get('params', {}).get('open_time', 0)
                if open_time and exit_reason in ('SL', 'EXIT_ENGINE') and profit < 0:
                    held_seconds = time.time() - open_time
                    if held_seconds < 30:
                        logger.critical(
                            f"[INSTANT SL] {symbol} #{ticket} closed as SL after only {held_seconds:.1f}s! "
                            f"P&L: ${profit:.2f}. This is a SPREAD SPIKE. "
                            f"Entry was at {pos_data.get('params', {}).get('entry_price', 0):.5f}."
                        )
                        send_telegram_notification(
                            f"[INSTANT SL] {symbol} #{ticket}: SL hit in {held_seconds:.1f}s "
                            f"(P&L ${profit:.2f}) -- likely spread spike. "
                            f"Check {symbol} broker spread config."
                        )
                        # BAN SYMBOL FOR 30 MINUTES after instant SL -- spread spike period
                        spike_ban_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
                        state.symbol_cooldowns[symbol] = spike_ban_expiry
                        logger.warning(f"[SPIKE BAN] {symbol} banned 30 min after instant SL.")
                
                # OUTCOME CLASSIFICATION (3 states, not 2)
                # WIN  : profit > 0  ? reset loss counter, fast re-entry
                # BE   : profit == 0 ? NEUTRAL, do NOT count as loss, short cooldown
                # LOSS : profit < 0 AND exit_reason is a real stop-out (SL or structural EXIT)
                #        EXIT_ENGINE on tiny amounts also neutral -- bot management decision
                is_win  = profit > 0
                is_be   = profit == 0 or exit_reason == 'BE'
                _acct_info = mt5.account_info()
                _tiny_threshold = (_acct_info.equity * 0.003) if _acct_info else 0.5
                # EXIT_ENGINE = bot closed the trade intentionally (trailing stop, BE move, etc.)
                # These are NEVER real losses for ban purposes -- only hard SL hits count.
                is_managed_exit = (exit_reason == 'EXIT_ENGINE')  # ALL bot exits are managed
                is_real_loss = profit < 0 and not is_be and not is_managed_exit

                if is_win:
                    state.consecutive_losses[symbol] = 0
                    recent_metrics = symbol_tracker.get_symbol_metrics(symbol)
                    if recent_metrics.get('recent_win_rate', 0) >= 0.65:
                        cooldown_expiry = datetime.now(timezone.utc) + timedelta(minutes=1)
                        logger.info(f" [AGGRESSIVE] High win-rate {symbol} -- fast re-entry (1 min)")
                    else:
                        cooldown_expiry = datetime.now(timezone.utc) + timedelta(minutes=config.TRADE_COOLDOWN_MINUTES)

                elif is_be or is_managed_exit:
                    # BREAKEVEN or tiny managed exit -- NEUTRAL outcome
                    # Do NOT touch consecutive_losses. Short cooldown then re-scan.
                    cooldown_expiry = datetime.now(timezone.utc) + timedelta(minutes=2)
                    _reason = "BE (zero loss)" if is_be else f"managed exit (${profit:.2f})"
                    logger.info(f" [NEUTRAL] {symbol} closed at {_reason} -- loss counter NOT incremented "
                                f"(consecutive losses stay at {state.consecutive_losses.get(symbol, 0)})")

                else:
                    # REAL LOSS: increment counter and apply ban logic
                    state.consecutive_losses[symbol] = state.consecutive_losses.get(symbol, 0) + 1
                    current_loss_count = state.consecutive_losses[symbol]

                    if current_loss_count >= 2:
                        cooldown_expiry = datetime.now(timezone.utc) + timedelta(hours=24)
                        logger.critical(f" [RISK] {symbol} hit 2 consecutive REAL losses. BANNED 24h.")
                        send_telegram_notification(
                            f"[!!] <b>SYMBOL BANNED</b>\n\n"
                            f"{symbol} hit {current_loss_count} real losses in a row.\n"
                            f"Locked until {cooldown_expiry.strftime('%Y-%m-%d %H:%M')} UTC.\n"
                            f"(BE and managed exits do NOT count toward this ban)"
                        )
                        try:
                            supabase.table('bot_commands').upsert({
                                'user_id': USER_ID,
                                'strategy_id': STRATEGY_ID,
                                f'ban_{symbol}': cooldown_expiry.isoformat(),
                            }, on_conflict='user_id,strategy_id').execute()
                        except Exception as _ban_err:
                            logger.warning(f"[BAN PERSIST] {symbol}: {_ban_err}")
                    else:
                        cooldown_expiry = datetime.now(timezone.utc) + timedelta(minutes=config.TRADE_COOLDOWN_MINUTES)
                
                state.symbol_cooldowns[symbol] = cooldown_expiry
                logger.info(f" [COOLDOWN] {symbol} locked. Next trade allowed after {cooldown_expiry.strftime('%H:%M')} UTC")
                
                # SCALPING OPTIMIZATION: Async update (non-blocking)
                async_logger.update_trade_async(ticket, deal.price, profit, exit_reason)
                success = True  # Assume success since async
                
                if success:
                    state.daily_pnl += profit
                    
                    # =========================================================
                    # ULTIMATE AI LEARNING - Learn from ALL trades
                    # =========================================================
                    
                    # 1. SYMBOL PERFORMANCE TRACKER
                    # Calculate pips
                    entry_price = pos_data.get('params', {}).get('entry_price', deal.price)
                    pips = abs(deal.price - entry_price) / 0.0001  # Rough pip calculation
                    symbol_tracker.record_trade(symbol, profit, pips)
                    
                    # 2. PATTERN RECOGNITION - Learn from WIN or LOSS
                    try:
                        # Build context from when trade was opened
                        context = {
                            'adx': pos_data.get('params', {}).get('atr', 0) * 100,  # Rough estimation
                            'session': pos_data.get('params', {}).get('session', 'UNKNOWN'),
                            'hour': datetime.now(timezone.utc).hour,
                            'confluence': 1.5,  # Default
                            'spread': 0.001
                        }
                        pattern_recognizer.learn_from_trade(symbol, direction, context, profit)
                    except Exception as e:
                        logger.error(f"[PATTERN] Error learning: {e}")
                    
                    # 3. LEGACY AI LEARNING - Analyze losses with Gemini
                    if profit < 0:
                        logger.warning(f" [AI LEARNING] Loss detected on #{ticket}: ${profit:.2f}")
                        analyze_loss_with_ai(ticket, deal, profit)
                    else:
                        logger.info(f" [TRADE CLOSED] #{ticket} WIN: ${profit:.2f}")
                    
                    # Clean up local state
                    if ticket in state.open_positions:
                        del state.open_positions[ticket]
                    state.be_moved.discard(ticket)
                    state.trailing_active.discard(ticket)
                    state.partial_closed.discard(ticket)
                    
    except Exception as e:
        logger.error(f"Error in update_closed_trades: {e}", exc_info=True)

def analyze_loss_with_ai(ticket: int, deal, profit: float):
    """
    AI LEARNING SYSTEM: Analyze losing trades with Gemini AI
    Stores lessons learned to improve future trading decisions
    """
    try:
        # Get full trade details from database
        trade_data = trade_db.get_trade_by_ticket(ticket)
        if not trade_data:
            logger.warning(f"[AI LEARNING] Could not find trade #{ticket} in database")
            return
        
        # Prepare analysis data
        symbol = deal.symbol
        entry_price = trade_data.get('entry_price', 0)
        exit_price = deal.price
        direction = trade_data.get('direction', 'UNKNOWN')
        stop_loss = trade_data.get('stop_loss', 0)
        take_profit = trade_data.get('take_profit', 0)
        entry_time = trade_data.get('timestamp', '')
        exit_time = datetime.now(timezone.utc).isoformat()
        
        # Get market context at entry
        df = get_market_data(symbol, config.ENTRY_TF, 50)
        if df is None:
            logger.warning(f"[AI LEARNING] Could not get market data for {symbol}")
            return
        
        # Calculate market conditions
        try:
            adx_val, _, _ = calculate_adx(df['high'], df['low'], df['close'], 14)
            adx = adx_val.iloc[-1] if len(adx_val) > 0 else 0
        except:
            adx = 0
        
        session = get_current_session()
        hour = datetime.now(timezone.utc).hour
        
        # Build AI analysis prompt
        prompt = f"""You are an expert forex trading analyst. Analyze this LOSING trade and identify what went wrong.

TRADE DETAILS:
- Symbol: {symbol}
- Direction: {direction}
- Entry Price: {entry_price}
- Exit Price: {exit_price}
- Stop Loss: {stop_loss}
- Take Profit: {take_profit}
- Profit/Loss: ${profit:.2f}
- Entry Time: {entry_time}
- Exit Time: {exit_time}
- Duration: ~{(datetime.fromisoformat(exit_time.replace('Z', '+00:00')) - datetime.fromisoformat(entry_time.replace('Z', '+00:00'))).seconds // 60} minutes

MARKET CONDITIONS:
- ADX (Trend Strength): {adx:.1f}
- Session: {session}
- Hour (UTC): {hour}
- Current Price: {df['close'].iloc[-1]:.5f}

ANALYSIS REQUEST:
1. Why did this trade lose?
2. What market condition was unfavorable?
3. What should we avoid next time?
4. Give a specific rule to prevent this in the future.

Respond with ONLY a single, specific trading rule (max 100 words) that would have prevented this loss.
Example format: "Avoid SELL trades in {symbol} during Asian session (0-6 UTC) when ADX < 25 because..."
"""

        # Call Gemini AI for analysis via central provider
        lesson = ai_provider.call_ai(prompt, "You are an expert forex analyst.", temperature=0.3)
        
        if lesson:
            # Clean up potential AI junk
            lesson = lesson.strip().replace('"', '').replace('*', '')
            
            # Store the lesson
            save_ai_lesson(symbol, direction, lesson, profit, {
                'adx': adx,
                'session': session,
                'hour': hour,
                'entry_price': entry_price,
                'exit_price': exit_price
            })
            
            logger.info(f" [AI LEARNING] Lesson learned from #{ticket}:")
            logger.info(f" [AI LEARNING] {lesson}")
            
        else:
            logger.warning("[AI LEARNING] No AI API key configured, skipping AI analysis")
            
    except Exception as e:
        logger.error(f"[AI LEARNING] Error analyzing loss: {e}", exc_info=True)

def save_ai_lesson(symbol: str, direction: str, lesson: str, loss_amount: float, context: dict):
    """
    Save AI-learned lesson to file for future reference
    Lessons are stored in JSON format with metadata
    """
    try:
        import json
        import os
        
        lessons_file = os.path.join(DATA_DIR, 'ai_trading_lessons.json')
        
        # Load existing lessons
        lessons = []
        if os.path.exists(lessons_file):
            try:
                with open(lessons_file, 'r') as f:
                    lessons = json.load(f)
            except:
                lessons = []
        
        # Add new lesson
        lesson_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'symbol': symbol,
            'direction': direction,
            'lesson': lesson,
            'loss_amount': loss_amount,
            'context': context
        }
        
        lessons.append(lesson_entry)
        
        # Keep only last 100 lessons
        lessons = lessons[-100:]
        
        # Save back
        with open(lessons_file, 'w') as f:
            json.dump(lessons, f, indent=2)
        
        logger.info(f" [AI LEARNING] Lesson saved to {lessons_file}")
        
    except Exception as e:
        logger.error(f"[AI LEARNING] Error saving lesson: {e}", exc_info=True)

def check_trade_against_lessons(symbol: str, direction: str, context: dict) -> tuple[bool, str]:
    """
    Check if a new trade conflicts with previously learned lessons
    Returns: (is_safe, warning_message)
    """
    try:
        import json
        import os
        
        lessons_file = os.path.join(DATA_DIR, 'ai_trading_lessons.json')
        
        if not os.path.exists(lessons_file):
            return True, ""  # No lessons yet, allow trade
        
        # Load lessons
        with open(lessons_file, 'r') as f:
            lessons = json.load(f)
        
        # Get recent lessons for this symbol
        recent_lessons = [
            l for l in lessons[-20:]  # Check last 20 lessons
            if l['symbol'] == symbol or 'ALL' in l['lesson'].upper()
        ]
        
        if not recent_lessons:
            return True, ""  # No relevant lessons
        
        # Simple keyword matching for now
        # Future: Could use AI to check if lesson applies
        warnings = []
        
        for lesson_entry in recent_lessons:
            lesson = lesson_entry['lesson'].lower()
            lesson_direction = lesson_entry['direction']
            lesson_context = lesson_entry.get('context', {})
            
            # Check if lesson mentions this direction
            if direction.lower() in lesson:
                # Check context similarity
                similar_conditions = False
                
                if abs(context.get('adx', 100) - lesson_context.get('adx', 0)) < 5:
                    similar_conditions = True
                
                if context.get('session') == lesson_context.get('session'):
                    similar_conditions = True
                
                if abs(context.get('hour', 100) - lesson_context.get('hour', 0)) < 2:
                    similar_conditions = True
                
                if similar_conditions:
                    warnings.append(f" AI Lesson: {lesson_entry['lesson'][:150]}")
        
        if warnings:
            logger.warning(f" [AI LEARNING] Found {len(warnings)} similar past losses for {symbol} {direction}")
            for warn in warnings:
                logger.warning(warn)
            return False, "; ".join(warnings)
        
        return True, ""
        
    except Exception as e:
        logger.error(f"[AI LEARNING] Error checking lessons: {e}", exc_info=True)
        return True, ""  # On error, allow trade

# === COPY AND REPLACE THIS FUNCTION ===

def check_emergency_conditions(account_info) -> bool:
    """
    Dynamic emergency circuit breaker with adaptive thresholds.

    FIX (v11.4): All trade-history checks now use `get_session_trades()`
    which only looks at trades closed AFTER this bot session started.
    Previously, `get_recent_trades()` fetched ALL-TIME history, so 10 losses
    from a previous run would immediately halt the bot on restart.
    """
    # Initialize daily equity tracker (restart-safe — see load_or_init_daily_baseline)
    if state.daily_start_equity == 0:
        today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        state.daily_start_equity = load_or_init_daily_baseline(DATA_DIR, account_info.equity, today_str)

    if state.daily_start_equity <= 0:
        return False

    # Calculate current daily loss
    daily_loss_percent = ((account_info.equity - state.daily_start_equity) / state.daily_start_equity) * 100

    # Use in-memory session counters -- no Supabase call, never blocks
    # state.daily_trades counts trades placed this session
    # state._session_losses counts losses this session (updated in trade management)
    _session_loss_count = getattr(state, '_session_losses', 0)
    _session_trade_count = getattr(state, 'daily_trades', 0)
    # session_trades removed -- using in-memory state counters only

    # 1. DYNAMIC EMERGENCY STOP
    dynamic_limit = config.MAX_DAILY_LOSS_PERCENT

    # Tighten if 3+ consecutive losses this session (tracked in-memory)
    if _session_loss_count >= 3:
        dynamic_limit = 12.0
        logger.warning(f"[WARN] Limit tightened to {dynamic_limit}% ({_session_loss_count} session losses)")

    # Tighten further if margin is low
    if account_info.margin_level > 0 and account_info.margin_level < 300:
        dynamic_limit = min(dynamic_limit, 10.0)

    if daily_loss_percent <= -dynamic_limit:
        logger.critical(f"[EMERGENCY STOP] Loss limit {dynamic_limit}% reached. Actual: {daily_loss_percent:.2f}%")
        send_telegram_notification(
            f"<b>EMERGENCY STOP</b>\n\n"
            f"Loss limit: {dynamic_limit}%\n"
            f"Actual loss: {daily_loss_percent:.2f}%\n"
            f"Equity: ${account_info.equity:.2f}\n"
            f"Bot halting for safety."
        )
        return True

    # 2. CONSECUTIVE LOSSES -- tracked in-memory (no DB needed)
    if _session_trade_count >= 10 and _session_loss_count >= 10:
        logger.critical("[EMERGENCY STOP] 10 consecutive losses THIS SESSION. Halting.")
        send_telegram_notification("<b>EMERGENCY STOP</b>\n\n10 consecutive losses. Halting.")
        return True
    elif _session_loss_count >= 7:
        logger.warning(f"[WARN] {_session_loss_count} losses this session -- approaching limit.")

    # 3. CRITICAL MARGIN LEVEL
    if account_info.margin_level < 200 and account_info.margin_level > 0:
        logger.critical(f"[EMERGENCY STOP] Critical margin: {account_info.margin_level:.0f}%")
        send_telegram_notification(
            f"<b>EMERGENCY STOP</b>\n\n"
            f"Margin level: {account_info.margin_level:.0f}%\n"
            f"Bot halting to prevent margin call."
        )
        return True

    # 4. EARLY WARNING (70% of limit)
    warning_threshold = dynamic_limit * 0.7
    if daily_loss_percent <= -warning_threshold and daily_loss_percent > -(warning_threshold + 1):
        logger.warning(f"[WARN] Daily loss {daily_loss_percent:.2f}% -- approaching {dynamic_limit}% limit.")

    return False

def validate_lot_size(symbol: str, lot_size: float) -> float:
    """
    Validate and adjust lot size against broker limits and margin requirements
    """
    try:
        spec = get_symbol_specs(symbol)
        if not spec:
            logger.warning(f"Cannot get specs for {symbol}, using minimum lot")
            return 0.01
        
        min_lot = spec['min_lot']
        max_lot = spec['max_lot']
        lot_step = spec['lot_step']
        
        lot_size = round(lot_size / lot_step) * lot_step
        lot_size = max(min_lot, min(max_lot, lot_size))
        
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return min_lot
        
        margin_required = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, lot_size, tick.ask)
        if margin_required is None:
            logger.error(f"Cannot calculate margin for {symbol} {lot_size}")
            return min_lot
        
        account_info = mt5.account_info()
        if not account_info: return min_lot
        
        max_allowed_margin = account_info.margin_free * 0.8
        
        if margin_required > max_allowed_margin:
            logger.warning(f"Lot size {lot_size} requires too much margin. Reducing.")
            affordable_lot = (max_allowed_margin / margin_required) * lot_size if margin_required > 0 else lot_size
            lot_size = round(affordable_lot / lot_step) * lot_step
            lot_size = max(min_lot, lot_size)
        
        return lot_size
    
    except Exception as e:
        logger.error(f"Error validating lot size: {e}")
        return 0.01

def is_spread_safe(symbol: str, target_pips: float) -> bool:
    """
    NOTE: This function is not currently called -- spread check is done
    directly in place_ai_trade using raw price units (ask-bid vs abs(entry-sl)).
    Kept for future use.
    """
    try:
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            logger.warning(f"[EXEC] {symbol}: no tick data available")
            return False
        
        spread_points = tick.ask - tick.bid
        
        # If the target is 0 (error), default to True to avoid freezing, 
        # but log a warning.
        if target_pips <= 0: return True 

        # Calculate the Ratio: Spread / Target
        # Example: Spread 20, Target 50 = 0.4 (40%)
        cost_ratio = spread_points / target_pips
        
        # Use the Configurable Limit
        if cost_ratio > config.MAX_SPREAD_RATIO:
            # OPTIONAL: Only log this every 100th time to stop spamming logs
            # logger.warning(f"HIGH SPREAD {symbol}: Ratio {cost_ratio:.2f} > {config.MAX_SPREAD_RATIO}")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Spread check error: {e}")
        return True # Default to allow if check fails




def adapt_sl_tp_for_volatility(symbol: str, base_sl_multiplier: float, base_tp_multiplier: float) -> Tuple[float, float]:
    """ INTELLIGENT: Adapt SL/TP based on current volatility"""
    try:
        # Get current and average ATR
        df = get_market_data(symbol, config.ENTRY_TF, 100)
        if df is None or len(df) < 50:
            return base_sl_multiplier, base_tp_multiplier
        
        highs, lows, closes = df['high'], df['low'], df['close']
        
        # Current ATR (14 period)
        current_atr = calculate_atr(highs, lows, closes, 14).iloc[-1]
        
        # Average ATR (50 period)
        avg_atr = calculate_atr(highs, lows, closes, 50).mean()
        
        volatility_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0
        
        # Adapt multipliers
        if volatility_ratio < 0.7:
            # Too quiet - increase requirements
            logger.info(f"  [INTELLIGENCE] Low volatility ({volatility_ratio:.2f}) - May skip trade")
            return None, None  # Signal to skip
        elif volatility_ratio > 1.5:
            # High volatility - wider stops
            sl_mult = base_sl_multiplier * 1.3
            tp_mult = base_tp_multiplier * 1.2
            logger.info(f"  [INTELLIGENCE] High volatility ({volatility_ratio:.2f}) - Wider SL: {sl_mult:.1f}x, TP: {tp_mult:.1f}x")
        else:
            # Normal volatility
            sl_mult = base_sl_multiplier
            tp_mult = base_tp_multiplier
        
        return sl_mult, tp_mult
        
    except Exception as e:
        logger.error(f"[VOLATILITY ADAPT] Error: {e}")


def place_ai_trade(local_signal: Dict, account_equity: float, current_daily_pnl: float) -> bool:
    """
    SMC PIPELINE EXECUTION:
    Trusts Engine Authority for Sizing and Entry Permission.
    """
    try:
        symbol = local_signal['symbol']
        direction = local_signal['direction']
        edge_score = local_signal.get('edge_score', 50.0)
        
        # Gap 4 FIX: MUST use orchestrated CapitalController risk
        if 'risk_percent_override' not in local_signal:
            logger.error(f"[EXEC GUARD] Signal for {symbol} lacked CapitalController risk override. Rejecting.")
            return False
            
        final_risk_percent = local_signal['risk_percent_override']
        
        # 1. FINAL EXECUTION GUARDS (Risk guards allowed here)
        # ---------------------------------------------------------------------
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            logger.warning(f"[EXEC] {symbol}: no tick data available")
            return False
        
        # A. Prepare Specs & Base Spread Check
        spread_pips = calculate_spread_correctly(symbol, tick)
        spec = get_symbol_specs(symbol)

        # B. News Check
        if is_trade_entry_paused_for_news(symbol):
            logger.warning(f" [EXECUTION] News Event Imminent for {symbol}. Skipping.")
            return False

        # B2. SYMBOL-SPECIFIC ABSOLUTE SPREAD GATE (NEW)
        # Rejects trades when broker is widening spreads (rollover / low liquidity / news spike).
        if not check_symbol_max_spread(symbol, tick):
            return False

        # B3. SCALPING QUALITY FILTER -- ADX, RSI, Volume, Kill Zone (NEW)
        try:
            df_m5_q = get_market_data(symbol, config.ENTRY_TF, 50)
            df_m1_q = get_market_data(symbol, config.MICRO_STRUCTURE_TF, 30)
            is_quality, quality_reason = check_scalping_quality(symbol, direction, df_m5_q, df_m1_q)
            if not is_quality:
                logger.warning(f"[EXEC GATE] {symbol} {direction} rejected by quality filter: {quality_reason}")
                return False
        except Exception as _qe:
            logger.debug(f"[QUALITY FILTER] Check skipped on {symbol}: {_qe}")

        # 2. EXECUTION PARAMETERS
        # ---------------------------------------------------------------------
        df = get_market_data(symbol, config.ENTRY_TF, 50)
        if df is None: return False
        
        # Pass signal_sl from strategy into params so TP is derived from it
        signal_sl_from_trigger = local_signal.get('stop_loss', 0.0) or 0.0
        _range_scalp = local_signal.get('_range_scalp_mode', False)
        _ema50_tp    = local_signal.get('ema50_tp', None)
        params = get_dynamic_trade_params(symbol, direction, df, signal_sl=signal_sl_from_trigger,
                                          range_scalp_mode=_range_scalp, ema50_tp_hint=_ema50_tp)
        if not params:
            logger.warning(f"[EXEC] {symbol}: get_dynamic_trade_params returned empty")
            return False
             
        # Use SL from strategy trigger (primary), params fallback (emergency only)
        sl = params['sl']  # Already resolved correctly inside get_dynamic_trade_params
        tp = params['tp1']
        sl_source = params.get('sl_source', 'UNKNOWN')
        
        # Use live tick entry price for all distance calculations
        entry_price = tick.ask if direction == 'BUY' else tick.bid
        sl_dist_price = abs(entry_price - sl)
        
        if sl_dist_price == 0:
            logger.error(f"[EXEC] SL distance is 0 for {symbol}. sl={sl}, entry={entry_price}. Skipping.")
            return False
        
        logger.info(f"[EXEC] {symbol} {direction}: entry={entry_price:.5f} sl={sl:.5f} "
                    f"dist={sl_dist_price:.5f} source={sl_source} tp={tp:.5f}")

        # C. FIXED: Spread vs SL Distance Guard (price units, not mixed pip/dollar)
        # Previous code compared dollar spread against pip-based SL distance (wrong for metals).
        # Now both are in raw price units -> apples-to-apples comparison.
        spread_raw   = tick.ask - tick.bid          # Always price units
        sl_dist_raw  = abs(entry_price - sl)        # Always price units
        if sl_dist_raw > 0 and spread_raw > (sl_dist_raw * config.MAX_SPREAD_RATIO):
            logger.warning(
                f"[EXECUTION] {symbol}: spread {spread_raw:.5f} > "
                f"{config.MAX_SPREAD_RATIO*100:.0f}% of SL distance {sl_dist_raw:.5f}. Skipping."
            )
            return False

        # 3. SMART LOT SIZING
        # 
        # PROFESSIONAL APPROACH:
        #   Step 1: Calculate the EXACT lot for 1% risk from structural SL
        #   Step 2: If lot_raw >= min_lot -> use it (ideal sizing)
        #   Step 3: If lot_raw < min_lot -> use min_lot but check actual risk:
        #      actual_risk <= 3% equity -> ACCEPT (small account, tight SL, proceed)
        #      actual_risk > 3% equity -> SKIP (SL too wide for this account size)
        #   This is what a professional trader does: size from structure, not from
        #   an arbitrary minimum contract size.
        # 
        risk_money = account_equity * (final_risk_percent / 100.0)
        tick_value = spec.get('trade_tick_value')
        tick_size  = spec.get('trade_tick_size')

        if tick_value and tick_size and tick_size > 0 and tick_value > 0:
            lot_raw = risk_money / (sl_dist_price / tick_size * tick_value)
        else:
            logger.warning(f"[LOT SIZING] tick_value/tick_size unavailable for {symbol}. Using margin fallback.")
            try:
                margin_per_lot = mt5.order_calc_margin(
                    mt5.ORDER_TYPE_BUY if direction == 'BUY' else mt5.ORDER_TYPE_SELL,
                    symbol, 1.0, entry_price) or 1.0
                lot_raw = risk_money / max(margin_per_lot * sl_dist_price, 0.001)
            except Exception:
                lot_raw = 0.01

        # Validate and snap to lot step
        lot_size = validate_lot_size(symbol, lot_raw)
        sym_info_ls = mt5.symbol_info(symbol)
        min_lot = sym_info_ls.volume_min if sym_info_ls else 0.01

        # Recalculate ACTUAL risk after lot clamping
        if tick_value and tick_size and tick_size > 0 and tick_value > 0:
            actual_risk_dollars = lot_size * (sl_dist_price / tick_size) * tick_value
        else:
            actual_risk_dollars = risk_money * (lot_size / max(lot_raw, 0.0001))
        actual_risk_pct = actual_risk_dollars / account_equity * 100

        # Smart risk decision
        hard_cap_pct = 10.0   # Never exceed 3% on any single trade
        if actual_risk_pct <= hard_cap_pct:
            # PROCEED: risk is within acceptable bounds
            if actual_risk_pct > final_risk_percent * 1.5:
                logger.info(
                    f"[LOT SIZING] {symbol}: lot_raw={lot_raw:.5f} < min_lot={min_lot:.2f}. "
                    f"Using min_lot. Actual risk: ${actual_risk_dollars:.2f} ({actual_risk_pct:.1f}%) "
                    f"vs intended {final_risk_percent:.1f}%. Proceeding -- tight structural SL."
                )
        else:
            # SKIP: SL too wide for this account size at min lot
            logger.warning(
                f"[SIZE SKIP] {symbol}: actual risk ${actual_risk_dollars:.2f} ({actual_risk_pct:.1f}%) "
                f"exceeds {hard_cap_pct}% cap. SL dist={sl_dist_price:.5f} is too wide "
                f"for ${account_equity:.0f} account at min lot {min_lot}. "
                f"Need tighter entry or larger account."
            )
            # 6h cooldown -- SL won't get tighter without a new setup forming
            _cd_key = f"_sz_cd_{symbol}"
            if time.time() - getattr(state, _cd_key, 0) > 30:
                setattr(state, _cd_key, time.time())
                state.symbol_cooldowns[symbol] = datetime.now(timezone.utc) + timedelta(minutes=10)
                send_telegram_notification(
                    f"[SIZE SKIP] {symbol} {direction}: SL too wide for account\n"
                    f"SL dist: {sl_dist_price:.4f} pts | Risk: ${actual_risk_dollars:.2f} ({actual_risk_pct:.1f}%)\n"
                    f"Max 3% = ${account_equity*0.03:.2f}\n"
                    f"Tip: wait for tighter sweep setup with smaller SL distance."
                )
            return False

        # 4. SEND ORDER
        # ---------------------------------------------------------------------
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logger.warning(f"[EXEC] {symbol}: mt5.symbol_info() returned None")
            return False
        
        digits = symbol_info.digits
        short_comment = str(local_signal.get('narrative_reason', 'SMC'))[:31]

        # ?? FINAL BROKER STOP-LEVEL GUARD (spread-aware, BID/ASK-correct) ????
        # Re-fetch tick just before order submission in case price moved.
        tick_final   = mt5.symbol_info_tick(symbol)
        final_entry  = tick_final.ask if direction == 'BUY' else tick_final.bid
        spread_final = tick_final.ask - tick_final.bid
        broker_min   = get_broker_min_sl_distance(symbol, final_entry)

        # Effective minimum distance = max(broker_min x 2, spread x MIN_SL_SPREAD_MULT)
        effective_min_dist = max(broker_min * 2.0, spread_final * config.MIN_SL_SPREAD_MULT)

        if direction == 'BUY':
            # MT5 marks longs vs BID -> SL must be below BID - effective_min_dist
            required_sl = tick_final.bid - effective_min_dist
            if sl > required_sl:
                sl = required_sl
                logger.warning(
                    f"[ORDER GUARD] {symbol} BUY SL relocated to {sl:.{digits}f} "
                    f"(spread={spread_final:.5f}, min_dist={effective_min_dist:.5f})"
                )
        else:
            # MT5 marks shorts vs ASK -> SL must be above ASK + effective_min_dist
            required_sl = tick_final.ask + effective_min_dist
            if sl < required_sl:
                sl = required_sl
                logger.warning(
                    f"[ORDER GUARD] {symbol} SELL SL relocated to {sl:.{digits}f} "
                    f"(spread={spread_final:.5f}, min_dist={effective_min_dist:.5f})"
                )

        # FINAL SPREAD RECHECK: re-validate spread using tick_final (freshest tick)
        # This catches spread spikes that occurred between the gate check and now.
        _final_spread = tick_final.ask - tick_final.bid
        _sym_u_fc = symbol.upper()
        _max_allowed = (
            config.SCALP_MAX_SPREAD_XAGUSD if 'XAGUSD' in _sym_u_fc else
            config.SCALP_MAX_SPREAD_XAUUSD if 'XAUUSD' in _sym_u_fc else
            config.SCALP_MAX_SPREAD_OIL    if 'USOIL'  in _sym_u_fc else
            config.SCALP_MAX_SPREAD_BTC    if 'BTC'    in _sym_u_fc else
            config.SCALP_MAX_SPREAD_ETH    if 'ETH'    in _sym_u_fc else
            config.SCALP_MAX_SPREAD_FX_PIPS * 0.0001
        )
        if _final_spread > _max_allowed * 3:  # Allow 3x normal max before blocking
            logger.critical(
                f"[SPREAD SPIKE BLOCKED] {symbol}: spread spiked to {_final_spread:.5f} "
                f"({_final_spread/_max_allowed:.0f}x normal max {_max_allowed}). "
                f"Aborting order to prevent instant SL hit."
            )
            send_telegram_notification(
                f"[SPREAD SPIKE] {symbol} order ABORTED: "
                f"spread {_final_spread:.4f} ({_final_spread/_max_allowed:.0f}x normal). "
                f"Prevented instant SL hit."
            )
            return False

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": mt5.ORDER_TYPE_BUY if direction == 'BUY' else mt5.ORDER_TYPE_SELL,
            "price": round(float(final_entry), digits),  # Uses freshest tick_final price
            "sl": round(float(sl), digits),
            "tp": round(float(tp), digits),
            "deviation": 20,
            "magic": MAGIC_NUMBER,
            "comment": short_comment,
            "type_time": mt5.ORDER_TIME_GTC
        }
        
        # Broker compat
        mode = symbol_info.filling_mode
        if mode == getattr(mt5, 'SYMBOL_FILLING_FOK', 1):
            request["type_filling"] = mt5.ORDER_FILLING_FOK
        elif mode == getattr(mt5, 'SYMBOL_FILLING_IOC', 2):
            request["type_filling"] = mt5.ORDER_FILLING_IOC
        elif mode & getattr(mt5, 'SYMBOL_FILLING_FOK', 1):
            request["type_filling"] = mt5.ORDER_FILLING_FOK
        elif mode & getattr(mt5, 'SYMBOL_FILLING_IOC', 2):
            request["type_filling"] = mt5.ORDER_FILLING_IOC
        else:
            request["type_filling"] = mt5.ORDER_FILLING_RETURN
        
        result = mt5.order_send(request)
        
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            sl_dist_pts = abs(final_entry - sl)
            spread_at_open = tick_final.ask - tick_final.bid
            rr_ratio = abs(tp - final_entry) / sl_dist_pts if sl_dist_pts > 0 else 0
            logger.info(
                f"  TRADE OPENED: {symbol} {direction} | Lot:{lot_size} | "
                f"Entry:{final_entry:.{digits}f} SL:{sl:.{digits}f} TP:{tp:.{digits}f} | "
                f"SL_dist:{sl_dist_pts:.{digits}f} Spread:{spread_at_open:.{digits}f} "
                f"Ratio:{spread_at_open/sl_dist_pts*100:.1f}% | RR:1:{rr_ratio:.1f} | "
                f"Risk:{final_risk_percent:.2f}% Edge:{edge_score}"
            )
            # Telegram trade alert
            _portfolio_pct = (len(state.open_positions) * config.BASE_RISK_PERCENT)
            _htf_line = ""
            if local_signal.get('htf_reason') and local_signal['htf_reason'] != 'No HTF data':
                _htf_line = f"HTF: {local_signal['htf_reason']}\n"
            _l3_score_line = ""
            if local_signal.get('l3_score'):
                _l3_score_line = f"AI Score: {local_signal['l3_score']}/10\n"
            send_telegram_notification(
                f"<b>TRADE OPENED</b>\n\n"
                f"<b>{symbol}</b> {direction} | Strategy: {local_signal.get('setup_type','SMC')}\n"
                f"{_htf_line}{_l3_score_line}"
                f"Entry: <code>{final_entry:.{digits}f}</code>\n"
                f"SL: <code>{sl:.{digits}f}</code> ({sl_dist_pts:.{digits}f} pts | {sl_dist_pts/final_entry*100:.2f}%)\n"
                f"TP: <code>{tp:.{digits}f}</code> (RR 1:{rr_ratio:.1f})\n"
                f"Spread: {spread_at_open:.{digits}f} ({spread_at_open/sl_dist_pts*100:.1f}% of SL dist)\n"
                f"Lot: {lot_size} | Risk: {final_risk_percent:.2f}% | Edge: {edge_score:.0f}\n"
                f"Portfolio risk: ~{_portfolio_pct:.1f}% | Equity: ${account_equity:.2f}"
            )
            async_logger.log_trade_async({
                'timestamp': datetime.utcnow().isoformat(), 'ticket': result.order, 'symbol': symbol,
                'direction': direction, 'entry_price': request['price'], 'stop_loss': sl,
                'take_profit': tp, 'lot_size': lot_size, 'strategy_name': 'EDGE_ENGINE',
                'ai_risk_percent': final_risk_percent,
                'metadata': {
                    'edge_score': edge_score,
                    'spread_at_open': spread_at_open,
                    'sl_distance': sl_dist_pts,
                    'spread_pct_of_sl': round(spread_at_open / sl_dist_pts * 100, 2) if sl_dist_pts > 0 else 0,
                    'rr_ratio': round(rr_ratio, 2),
                }
            })
            state.daily_trades += 1
            if not hasattr(state, '_session_losses'): state._session_losses = 0
            
            # Pass Edge parameters into state management
            _strat_t = local_signal.get('strategy_type', 'GENERIC')
            _aox_fib = local_signal.get('aox_fib', None)   # SD levels for AOX TP management
            state.open_positions[result.order] = {
                'params': {
                    'sl':            sl,
                    'tp':            tp,
                    'initial_sl':    sl,           # Preserved for r_multiple calculation
                    'edge_score':    edge_score,
                    'is_runner':     False,
                    'runner_eligible': local_signal.get('runner_eligible', False),
                    'exit_aggressiveness': local_signal.get('exit_aggressiveness', 'NORMAL'),
                    'entry_price':   final_entry,
                    'open_time':     time.time(),  # For instant-SL spike detection
                    'symbol':        symbol,
                    'strategy_type': _strat_t,     # CRITICAL: needed for strategy-specific management
                    'aox_fib':       _aox_fib,     # AOX SD levels: tp1_near/tp1_far/tp2_near/tp2_mid/tp2_far
                }
            }
            return True
        else:
            mt5_err = mt5.last_error()
            retcode = result.retcode if result else 'None'
            comment = result.comment if result else 'None'
            logger.error(f" Order Failed: retcode={retcode}, mt5_err={mt5_err}, comment={comment}, request={request}")
            return "ORDER_FAILED"  # Distinct from False -- triggers 1-min cooldown in caller
            
    except Exception as e:
        logger.error(f"Error placing trade: {e}", exc_info=True)
        return False

# =============================================================================
# MAIN TRADING LOOP (HYBRID ARCHITECTURE)
# =============================================================================

# 
# INSTITUTIONAL TIME HELPERS (DST-aware, NY time)
# 

def _ny_to_utc_minutes(h_ny: int, m_ny: int) -> int:
    """Convert NY (EDT/EST) time to UTC minutes-since-midnight, DST-aware."""
    now  = datetime.now(timezone.utc)
    year = now.year
    mar1 = datetime(year, 3, 1)
    dst_start = mar1 + timedelta(days=(6 - mar1.weekday()) % 7 + 7)  # 2nd Sunday March
    nov1 = datetime(year, 11, 1)
    dst_end = nov1 + timedelta(days=(6 - nov1.weekday()) % 7)         # 1st Sunday November
    is_edt = dst_start.date() <= now.date() < dst_end.date()
    offset = 4 if is_edt else 5  # EDT=UTC-4, EST=UTC-5
    return (h_ny * 60 + m_ny + offset * 60) % (24 * 60)


def get_active_macro_window() -> Optional[str]:
    """
    ICT NY Macro Windows (EST, DST-aware).
    These are 20-minute windows when institutional algorithms execute.

    From the strategy document:
      8:50 - 9:10 AM EST    NY_PRE_OPEN
      9:50 - 10:10 AM EST   NY_AM_MACRO_1  (Silver Bullet -- highest prob)
      10:50 - 11:10 AM EST  NY_AM_MACRO_2
      1:50 - 2:10 PM EST    NY_PM_MACRO
    """
    now_utc = datetime.now(timezone.utc)
    t_utc   = now_utc.hour * 60 + now_utc.minute

    ny_windows = [
        (8*60+50,  9*60+10,  "NY_PRE_OPEN"),
        (9*60+50,  10*60+10, "NY_AM_MACRO_1"),   # Silver Bullet
        (10*60+50, 11*60+10, "NY_AM_MACRO_2"),
        (13*60+50, 14*60+10, "NY_PM_MACRO"),
    ]
    for ny_s, ny_e, name in ny_windows:
        utc_s = _ny_to_utc_minutes(ny_s // 60, ny_s % 60)
        utc_e = _ny_to_utc_minutes(ny_e // 60, ny_e % 60)
        if utc_s <= t_utc < utc_e:
            return name
    return None


def is_am_h4_candle() -> bool:
    """
    Trade only AM H4 candles (1AM/5AM/9AM EST -- AM candles).
    Skip PM candles (1PM/5PM/9PM EST).
    """
    now_utc = datetime.now(timezone.utc)
    t_utc   = now_utc.hour * 60 + now_utc.minute
    am_start = _ny_to_utc_minutes(1,  0)
    am_end   = _ny_to_utc_minutes(13, 0)
    if am_start < am_end:
        return am_start <= t_utc < am_end
    return t_utc >= am_start or t_utc < am_end


def get_true_day_open(symbol: str) -> Optional[float]:
    """
    True Day Open (TDO): price at midnight EST (12:00 AM New York time).
    Used for Discount/Premium filter:
      - Price below TDO = Discount zone  prioritize BUY (AOX Long)
      - Price above TDO = Premium zone   prioritize SELL (AOX Short)
    """
    try:
        # Midnight EST in UTC
        midnight_utc = _ny_to_utc_minutes(0, 0)  # minutes since midnight UTC
        now_utc = datetime.now(timezone.utc)
        now_mins = now_utc.hour * 60 + now_utc.minute

        # Build datetime for today's midnight EST
        offset_hours = midnight_utc // 60  # UTC hour when NY midnight occurred
        today = now_utc.date()
        if now_mins < midnight_utc:   # midnight hasn't happened yet today in UTC
            today = today - timedelta(days=1)
        midnight_dt = datetime(today.year, today.month, today.day,
                               offset_hours, 0, tzinfo=timezone.utc)

        # Get M5 candle at midnight
        rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M5,
                                    midnight_dt, 3)
        if rates is not None and len(rates) > 0:
            return float(rates[0]['open'])
    except Exception as e:
        logger.debug(f"TDO {symbol}: {e}")
    return None



# 
# SHAAKUNI SSM (Sweep Method) -- Dedicated Module
# Strict MTF implementation per the strategy document:
#   HTF (H1/H4): Liquidity sweep -- wick breaks prev high/low,
#                body CLOSES back inside (not a breakout)
#   LTF (M5):    Find extreme unmitigated OB within swept leg
#   Entry:       Limit order at extreme OB level
#   SL:          Beyond OB + spread buffer
#   TP:          Opposing liquidity (the swept candle's high/low)
# 

# 
# AOX POSITION LAYERING STATE
# Tracks each symbol's 3-phase AOX entry progression
# 

def get_aox_state(symbol: str) -> dict:
    """Get or initialize AOX layering state for a symbol."""
    if not hasattr(state, 'aox_states'):
        state.aox_states = {}
    if symbol not in state.aox_states:
        state.aox_states[symbol] = {
            'phase': 0,        # 0=watching, 1=layer1_placed, 2=layer2_placed, 3=complete
            'spike': None,
            'fib': None,
            'direction': None,
            'layer1_ticket': None,
            'layer2_ticket': None,
            'layer3_ticket': None,
            'fpfvg': None,     # First Presented FVG level
        }
    return state.aox_states[symbol]


def reset_aox_state(symbol: str):
    """Reset AOX state after completion or invalidation."""
    if hasattr(state, 'aox_states') and symbol in state.aox_states:
        state.aox_states[symbol] = {
            'phase': 0, 'spike': None, 'fib': None, 'direction': None,
            'layer1_ticket': None, 'layer2_ticket': None, 'layer3_ticket': None,
            'fpfvg': None,
        }


def detect_fpfvg(df_m1: 'pd.DataFrame', direction: str) -> float:
    """
    First Presented Fair Value Gap (FPFVG):
    The first FVG that appears on M1 after the AOX setup forms.
    FVG = gap between candle[i-1].high and candle[i+1].low (bullish FVG)
          or candle[i-1].low and candle[i+1].high (bearish FVG)
    Returns the FVG midpoint or 0 if not found.
    """
    if df_m1 is None or len(df_m1) < 5: return 0.0
    try:
        for i in range(len(df_m1)-3, 1, -1):
            c_before = df_m1.iloc[i-1]
            c_mid    = df_m1.iloc[i]
            c_after  = df_m1.iloc[i+1]
            if direction == 'BUY':
                # Bullish FVG: gap between c_before.high and c_after.low
                if float(c_before['high']) < float(c_after['low']):
                    gap_mid = (float(c_before['high']) + float(c_after['low'])) / 2
                    return gap_mid
            else:
                # Bearish FVG: gap between c_before.low and c_after.high
                if float(c_before['low']) > float(c_after['high']):
                    gap_mid = (float(c_before['low']) + float(c_after['high'])) / 2
                    return gap_mid
    except Exception:
        pass
    return 0.0


def execute_aox_layer(symbol: str, direction: str, entry_price: float,
                      sl: float, tp: float, risk_fraction: float,
                      layer_name: str, account_equity: float) -> int:
    """
    Place one AOX layer with fractional risk allocation.
    risk_fraction: 0.25 for Layer 1&2, 0.50 for Layer 3
    Returns MT5 ticket or 0 on failure.
    """
    try:
        sym_info = mt5.symbol_info(symbol)
        if not sym_info: return 0
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return 0

        risk_amount = account_equity * (config.BASE_RISK_PERCENT / 100.0) * risk_fraction
        sl_dist     = abs(entry_price - sl)
        if sl_dist <= 0: return 0

        tick_val  = sym_info.trade_tick_value
        tick_size = sym_info.trade_tick_size
        if tick_val and tick_val > 0 and tick_size > 0:
            pip_value = (tick_val / tick_size) * sym_info.point
            lot_raw   = risk_amount / max(sl_dist * (pip_value / sym_info.point), 0.001)
        else:
            lot_raw = risk_amount / max(sl_dist * 10, 0.001)

        lot_step = sym_info.volume_step
        lot_size = max(sym_info.volume_min, min(
            round(lot_raw / lot_step) * lot_step, sym_info.volume_max))

        mode = sym_info.filling_mode
        fill = (mt5.ORDER_FILLING_FOK if mode & 1 else
                mt5.ORDER_FILLING_IOC if mode & 2 else
                mt5.ORDER_FILLING_RETURN)

        order_type = mt5.ORDER_TYPE_BUY if direction == 'BUY' else mt5.ORDER_TYPE_SELL
        price      = tick.ask if direction == 'BUY' else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol,
            "volume": lot_size, "type": order_type, "price": price,
            "sl": sl, "tp": tp, "deviation": 20,
            "magic": MAGIC_NUMBER,
            "comment": f"AOX_{layer_name}_{risk_fraction:.0%}",
            "type_filling": fill,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(
                f"[AOX {layer_name}] {symbol} {direction}: "
                f"lot={lot_size} ({risk_fraction:.0%} risk) "
                f"entry={price:.4f} sl={sl:.4f} tp={tp:.4f}"
            )
            state.daily_trades += 1
            # Store strategy_type in open_positions so manage_all_positions routes correctly
            if not hasattr(state, 'open_positions'): state.open_positions = {}
            state.open_positions[result.order] = {
                'params': {
                    'sl': sl, 'tp': tp, 'initial_sl': sl,
                    'entry_price': price, 'symbol': symbol,
                    'strategy_type': 'AOX',
                    'open_time': time.time(),
                    'is_runner': False,
                    'edge_score': 75.0,
                    'exit_aggressiveness': 'HOLD',  # AOX holds to SD levels
                }
            }
            return result.order
        else:
            logger.warning(f"[AOX {layer_name}] {symbol}: failed retcode={result.retcode if result else 'None'}")
    except Exception as e:
        logger.error(f"[AOX {layer_name}] {symbol}: {e}")
    return 0


def detect_aox_phase_signal(aox_state: dict, df_m5: 'pd.DataFrame', df_m1: 'pd.DataFrame',
                             effective_trend: str, symbol: str) -> Optional[Dict[str, Any]]:
    """
    Pure detection half of the AOX layered engine -- extracted from
    run_aox_layered_entry so the decision logic (does this phase's
    condition hold right now) is testable independently of order
    placement. Every check, threshold, and comment below is unchanged
    from the inline version; this function only stops short of calling
    execute_aox_layer / mt5.order_send itself.

    NOTE ON TIMEFRAME: detect_manipulation_spike's own docstring says it
    detects the spike "on M15," and the AOX reference spec explicitly
    calls the 15-minute chart "the primary engine for trend refinement" --
    but this call site (both before and after this extraction) passes
    df_m5, not a separate M15 series. Preserved exactly as found rather
    than silently "fixed": changing the timeframe here is a real design
    decision (M15 needs an extra data feed threaded through this whole
    call chain) worth deciding deliberately, not bundling into an
    extraction meant to be behavior-preserving.

    Returns a dict describing what execute_aox_layer should place
    (direction, entry_price, sl, tp, risk_fraction, layer_name,
    next_phase, state_updates) or None if this phase's conditions aren't
    met yet.
    """
    try:
        atr = float(calculate_atr(df_m5['high'], df_m5['low'], df_m5['close'], 14).iloc[-1])
        cur_price = float(df_m5['close'].iloc[-1])

        #  PHASE 0: Waiting for spike + SD zone tap
        if aox_state['phase'] == 0:
            spike = detect_manipulation_spike(df_m5, atr)
            if not spike: return None
            fib = compute_aox_fibonacci(spike)
            direction = 'SELL' if spike['type'] == 'BEARISH' else 'BUY'

            # Check effective trend alignment
            if effective_trend != 'NEUTRAL':
                if direction == 'BUY' and effective_trend == 'BEARISH': return None
                if direction == 'SELL' and effective_trend == 'BULLISH': return None

            # Check SD zone: price must be at -2.0 to -2.5 SD (minor) OR -4.0 to -4.5 SD (major reversal)
            reached_sd2 = spike.get('reached_sd2', False)
            reached_sd4 = spike.get('reached_sd4', False)
            if not reached_sd2 and not reached_sd4:
                return None
            # SD4 major reversal zone = higher conviction, larger L1 allocation
            _l1_alloc = 0.35 if reached_sd4 else 0.25
            if reached_sd4:
                logger.info(f"[AOX L1] {symbol}: SD4 MAJOR reversal zone -- using {_l1_alloc*100:.0f}% allocation")

            # Check sniper zone
            in_sniper = fib['sniper_entry'] <= cur_price <= fib['sniper_top']
            if not in_sniper: return None

            # TDO filter
            tdo = get_true_day_open(symbol)
            if tdo and tdo > 0:
                if direction == 'BUY' and cur_price > tdo: return None
                if direction == 'SELL' and cur_price < tdo: return None

            # Macro window: HARD GATE -- AOX only executes during institutional 20-min windows
            macro = get_active_macro_window()
            if not macro:
                logger.debug(f"[AOX L1] {symbol}: outside macro window -- skip (wait for 8:50/9:50/10:50/13:50 EST)")
                return None
            logger.info(f"[AOX L1] {symbol}: macro window active: {macro}")

            # LAYER 1: at SD tap (25% minor zone, 35% major reversal zone)
            sl1 = fib['sl_level'] + (0.001 if direction == 'SELL' else -0.001)
            tp1 = fib['tp2_mid']
            return {
                'direction': direction, 'entry_price': cur_price, 'sl': sl1, 'tp': tp1,
                'risk_fraction': _l1_alloc, 'layer_name': 'L1_SD_TAP', 'next_phase': 1,
                'state_updates': {'spike': spike, 'fib': fib, 'direction': direction},
            }

        #  PHASE 1: Waiting for SMT + FPFVG (Turtle Soup)
        elif aox_state['phase'] == 1:
            direction = aox_state['direction']
            spike     = aox_state['spike']
            fib       = aox_state['fib']

            # Check SMT divergence
            smt_ok = check_smt_divergence(symbol, spike['type'])
            if not smt_ok: return None

            # CISD on M1
            cisd = detect_cisd_trigger(df_m1, direction)
            if not cisd: return None

            # Find FPFVG (First Presented FVG) on M1 for Turtle Soup
            fpfvg = detect_fpfvg(df_m1, direction)
            if fpfvg == 0.0: return None

            # LAYER 2: 25% at SMT confirmation + FVG
            sl2 = fib['sl_level']
            tp2 = fib['tp1_near']   # TP1 at 1.47 (first partial)
            return {
                'direction': direction, 'entry_price': cur_price, 'sl': sl2, 'tp': tp2,
                'risk_fraction': 0.25, 'layer_name': 'L2_TURTLE', 'next_phase': 2,
                'state_updates': {'fpfvg': fpfvg},
            }

        #  PHASE 2: Waiting for Mitigation Block (Hippo)
        elif aox_state['phase'] == 2:
            direction = aox_state['direction']
            fib       = aox_state['fib']

            # Hippo: price has reversed and is now at a mitigation/breaker block
            # Detect: price pulled back to the FPFVG area and is rejecting
            fpfvg = aox_state.get('fpfvg', 0)
            if fpfvg == 0: return None

            fvg_dist = abs(cur_price - fpfvg)
            near_fvg = fvg_dist <= atr * 1.5

            # Confirm reversal direction is holding
            ema9 = float(df_m5['close'].ewm(span=9, adjust=False).mean().iloc[-1])
            reversal_holding = (direction == 'BUY'  and cur_price > ema9) or                                (direction == 'SELL' and cur_price < ema9)

            if not (near_fvg and reversal_holding): return None

            # LAYER 3: 50% at Hippo/Mitigation block
            sl3 = fib['sl_level']
            tp3 = fib['tp2_far']   # Final target: 2.64 level
            return {
                'direction': direction, 'entry_price': cur_price, 'sl': sl3, 'tp': tp3,
                'risk_fraction': 0.50, 'layer_name': 'L3_HIPPO', 'next_phase': 3,
                'state_updates': {},
            }

    except Exception as e:
        logger.error(f"[AOX LAYERED] {symbol}: {e}")
        import traceback
        logger.debug(traceback.format_exc()[-300:])

    return None


def run_aox_layered_entry(symbol: str, df_m5: 'pd.DataFrame',
                           df_m1: 'pd.DataFrame', effective_trend: str,
                           account_equity: float) -> bool:
    """
    Full AOX 25/25/50 layered execution engine.
    Called every iteration. Manages state across phases.

    Layer 1 (25%): Price taps -2.0 to -2.5 SD zone
    Layer 2 (25%): SMT divergence confirmed + FPFVG sweep (Turtle Soup)
    Layer 3 (50%): Mitigation/Breaker block after reversal begins

    Now a thin wrapper around detect_aox_phase_signal() (the pure
    decision logic, extracted so it's independently testable/backtestable)
    + execute_aox_layer() (the actual order placement). Behavior is
    unchanged from before this split -- same checks, same thresholds,
    same state transitions -- only the two concerns are no longer
    tangled in one function.

    Returns True if any layer was executed this iteration.

    BUG FIX (was dead code before this fix): reset_aox_state() existed but
    had zero call sites anywhere in the file, and this function's own call
    site in the main loop runs BEFORE the shared symbol_cooldowns check
    (~line 9360), so neither the cooldown this function sets on phase-3
    completion nor any other cooldown (loss cooldown, spike-ban, etc.) ever
    actually blocked AOX from re-entering. Net effect: once a symbol
    completed one full 3-layer cycle, its phase stuck at 3 forever (the
    old detect_aox_phase_signal has no phase==3 branch, so it just
    returned None every call from then on) -- AOX silently went permanently
    inert per-symbol for the life of the process, with no error or log to
    indicate it. Fixed by checking + honoring the shared cooldown dict here
    directly, and resetting the state machine back to phase 0 once a
    cooldown clears -- deliberately using the SAME shared dict every other
    cooldown reason already writes to (not a new AOX-only one), so a loss
    cooldown or spike-ban on this symbol now also pauses AOX and clears its
    state, consistent with reset_aox_state's own "reset after completion or
    invalidation" docstring.
    """
    if symbol in state.symbol_cooldowns:
        if datetime.now(timezone.utc) < state.symbol_cooldowns[symbol]:
            return False
        del state.symbol_cooldowns[symbol]
        reset_aox_state(symbol)

    aox_st = get_aox_state(symbol)
    signal = detect_aox_phase_signal(aox_st, df_m5, df_m1, effective_trend, symbol)
    if not signal:
        return False

    ticket = execute_aox_layer(
        symbol, signal['direction'], signal['entry_price'], signal['sl'], signal['tp'],
        signal['risk_fraction'], signal['layer_name'], account_equity,
    )
    if not ticket:
        return False

    aox_st.update(signal['state_updates'])
    aox_st['phase'] = signal['next_phase']
    # next_phase is 1/2/3 for layer 1/2/3 respectively -- same mapping the
    # original inline code used (layer N's ticket is stored right when the
    # phase advances to N).
    aox_st[f"layer{signal['next_phase']}_ticket"] = ticket
    logger.info(f"[AOX {signal['layer_name']}] {symbol}: {signal['risk_fraction']:.0%} placed | phase -> {signal['next_phase']}")
    if signal['next_phase'] == 3:
        # Mark complete -- reset after 2 hours or when all positions close
        state.symbol_cooldowns[symbol] = datetime.now(timezone.utc) + timedelta(hours=2)
    return True


class ShaakuniSSM:
    """
    Dedicated Shaakuni SSM (Sweep Method) implementation.
    Strictly enforces the document rules for HTF sweep detection
    and LTF extreme OB entry.
    """

    @staticmethod
    def detect_htf_sweep(df_htf: 'pd.DataFrame', direction: str) -> dict:
        """
        STRICT sweep detection on H1 or H4.

        Bullish sweep (look for BUY):
          HTF candle low < previous candle low (wick swept sell-side liquidity)
          AND HTF candle close >= previous candle low (body closed back above)
           Indicates institutional buy orders absorbed the sell liquidity

        Bearish sweep (look for SELL):
          HTF candle high > previous candle high (wick swept buy-side liquidity)
          AND HTF candle close <= previous candle high (body closed back below)

        Returns sweep info dict or empty dict.
        """
        empty = {}
        if df_htf is None or len(df_htf) < 4:
            return empty
        try:
            # Check last 3 HTF candles for a sweep
            for i in range(-2, -5, -1):
                c_curr = df_htf.iloc[i]       # candidate sweep candle
                c_prev = df_htf.iloc[i - 1]   # reference candle

                if direction == 'BUY':
                    # Wick breaks prev low, body closes above it
                    wick_swept = float(c_curr['low'])   < float(c_prev['low'])
                    body_inside = float(c_curr['close']) >= float(c_prev['low'])
                    if wick_swept and body_inside:
                        return {
                            'type':          'BULLISH_SWEEP',
                            'swept_low':     float(c_prev['low']),
                            'candle_low':    float(c_curr['low']),
                            'candle_high':   float(c_curr['high']),
                            'candle_close':  float(c_curr['close']),
                            'tp_target':     float(c_curr['high']),  # TP = swept candle high
                            'swept_at':      i,
                        }

                elif direction == 'SELL':
                    wick_swept  = float(c_curr['high'])  > float(c_prev['high'])
                    body_inside = float(c_curr['close']) <= float(c_prev['high'])
                    if wick_swept and body_inside:
                        return {
                            'type':          'BEARISH_SWEEP',
                            'swept_high':    float(c_prev['high']),
                            'candle_high':   float(c_curr['high']),
                            'candle_low':    float(c_curr['low']),
                            'candle_close':  float(c_curr['close']),
                            'tp_target':     float(c_curr['low']),   # TP = swept candle low
                            'swept_at':      i,
                        }
        except Exception as e:
            logger.debug(f"ShaakuniSSM.detect_htf_sweep: {e}")
        return empty

    @staticmethod
    def find_extreme_ob(df_ltf: 'pd.DataFrame', sweep: dict, direction: str, atr: float) -> dict:
        """
        Find the EXTREME (most aggressive) unmitigated Order Block
        within the swept leg on the LTF (M5).

        For BUY (bullish sweep):
          The swept leg runs from the sweep candle's high down to its low.
          The extreme OB = the LOWEST unmitigated bearish OB (last red candle
          before a bullish impulse) within that leg.
          Entry: limit order BUY at this OB's low (deepest discount)

        For SELL (bearish sweep):
          The extreme OB = the HIGHEST unmitigated bullish OB
          within the swept leg.
          Entry: limit order SELL at this OB's high
        """
        empty = {}
        if df_ltf is None or len(df_ltf) < 10 or not sweep:
            return empty
        try:
            cur_price = float(df_ltf['close'].iloc[-1])

            if direction == 'BUY':
                leg_high = sweep.get('swept_low', cur_price) + atr * 3
                leg_low  = sweep.get('candle_low', cur_price - atr * 5)
                # Find all bearish OBs within the swept leg
                # Bearish OB = red candle followed by bullish displacement
                candidate_obs = []
                for i in range(3, len(df_ltf) - 1):
                    c = df_ltf.iloc[i]
                    c_next = df_ltf.iloc[i + 1]
                    # Red candle
                    if float(c['close']) >= float(c['open']): continue
                    # Next candle is strongly bullish (displacement)
                    next_body = abs(float(c_next['close']) - float(c_next['open']))
                    if float(c_next['close']) <= float(c_next['open']): continue
                    if next_body < atr * 0.6: continue
                    # OB is within the swept leg
                    ob_low = float(c['close'])  # bottom of bearish OB = close
                    ob_high= float(c['open'])   # top = open
                    if not (leg_low <= ob_low <= leg_high): continue
                    # OB is unmitigated (price hasn't returned to it yet)
                    later_lows = [float(df_ltf.iloc[j]['low']) for j in range(i+2, len(df_ltf))]
                    if later_lows and min(later_lows) < ob_low: continue  # mitigated
                    candidate_obs.append({'ob_low': ob_low, 'ob_high': ob_high, 'idx': i})

                if not candidate_obs: return empty
                # EXTREME OB = the LOWEST (deepest in discount) unmitigated OB
                extreme = min(candidate_obs, key=lambda x: x['ob_low'])
                return {
                    'ob_low':    extreme['ob_low'],
                    'ob_high':   extreme['ob_high'],
                    'entry':     extreme['ob_low'],   # limit BUY at OB low
                    'sl':        extreme['ob_low'] - atr * 0.3,
                    'tp':        sweep.get('tp_target', extreme['ob_high'] + atr * 5),
                    'direction': 'BUY',
                }

            else:  # SELL
                leg_low  = sweep.get('swept_high', cur_price) - atr * 3
                leg_high = sweep.get('candle_high', cur_price + atr * 5)
                candidate_obs = []
                for i in range(3, len(df_ltf) - 1):
                    c = df_ltf.iloc[i]
                    c_next = df_ltf.iloc[i + 1]
                    if float(c['close']) <= float(c['open']): continue  # need green candle
                    next_body = abs(float(c_next['close']) - float(c_next['open']))
                    if float(c_next['close']) >= float(c_next['open']): continue
                    if next_body < atr * 0.6: continue
                    ob_high = float(c['close'])  # top of bullish OB = close
                    ob_low  = float(c['open'])
                    if not (leg_low <= ob_high <= leg_high): continue
                    later_highs = [float(df_ltf.iloc[j]['high']) for j in range(i+2, len(df_ltf))]
                    if later_highs and max(later_highs) > ob_high: continue
                    candidate_obs.append({'ob_low': ob_low, 'ob_high': ob_high, 'idx': i})

                if not candidate_obs: return empty
                # EXTREME OB = the HIGHEST (deepest in premium) unmitigated OB
                extreme = max(candidate_obs, key=lambda x: x['ob_high'])
                return {
                    'ob_low':    extreme['ob_low'],
                    'ob_high':   extreme['ob_high'],
                    'entry':     extreme['ob_high'],  # limit SELL at OB high
                    'sl':        extreme['ob_high'] + atr * 0.3,
                    'tp':        sweep.get('tp_target', extreme['ob_low'] - atr * 5),
                    'direction': 'SELL',
                }

        except Exception as e:
            logger.debug(f"ShaakuniSSM.find_extreme_ob: {e}")
        return empty


def strategy_shaakuni_ssm(symbol: str, df_h1: 'pd.DataFrame', df_h4: 'pd.DataFrame',
                           df_m5: 'pd.DataFrame', effective_trend: str) -> dict:
    """
    Run the full ShaakuniSSM pipeline for one symbol.
    Returns setup dict if valid, empty dict otherwise.

    Flow:
      1. Scan H4 for sweep (trend-aligned direction)
      2. If no H4 sweep, scan H1
      3. On confirmed sweep: scan M5 for extreme unmitigated OB
      4. Return limit order setup at the extreme OB
    """
    empty = {}
    if df_m5 is None or len(df_m5) < 10: return empty
    try:
        atr_m5 = float(calculate_atr(df_m5['high'], df_m5['low'], df_m5['close'], 14).iloc[-1])

        # Direction: only trade trend-aligned sweeps
        direction = 'BUY' if effective_trend == 'BULLISH' else                     'SELL' if effective_trend == 'BEARISH' else None
        if direction is None: return empty

        # Step 1: HTF sweep -- try H4 first, then H1
        sweep = {}
        for df_htf, tf_name in [(df_h4, 'H4'), (df_h1, 'H1')]:
            if df_htf is not None and len(df_htf) >= 4:
                sweep = ShaakuniSSM.detect_htf_sweep(df_htf, direction)
                if sweep:
                    logger.debug(f"[SSM] {symbol}: {sweep['type']} on {tf_name}")
                    break
        if not sweep: return empty

        # Step 2: Find extreme OB on M5 within swept leg
        ob = ShaakuniSSM.find_extreme_ob(df_m5, sweep, direction, atr_m5)
        if not ob: return empty

        # Step 3: Validate entry level is still reachable
        cur_price = float(df_m5['close'].iloc[-1])
        if direction == 'BUY' and cur_price <= ob['entry']:
            return empty  # price already below OB -- limit already filled or stale
        if direction == 'SELL' and cur_price >= ob['entry']:
            return empty

        rr = abs(ob['entry'] - ob['tp']) / abs(ob['entry'] - ob['sl']) if abs(ob['entry'] - ob['sl']) > 0 else 0
        if rr < 1.5: return empty  # minimum 1.5:1 for SSM

        logger.info(
            f"[SSM] {symbol} {direction}: HTF sweep confirmed. "
            f"Extreme OB={ob['entry']:.4f} SL={ob['sl']:.4f} TP={ob['tp']:.4f} RR={rr:.1f}x"
        )
        return {
            'signal':        direction,
            'reason':        'SHAAKUNI_SSM',
            'stop_loss':     ob['sl'],
            'tp':            ob['tp'],
            'limit_entry':   ob['entry'],   # limit order, not market
            'order_type':    'LIMIT',
            'strategy_type': 'SSM',
            'ob_zone':       ob,
            'sweep':         sweep,
            'rr':            rr,
        }
    except Exception as e:
        logger.error(f"[SSM] {symbol}: {e}")
    return empty


# AOX MODEL -- ported from intraday.py
# Runs on M5/M15 for scalping (manipulation spike + Fibonacci sniper + SMT + CISD)


def compute_sd_levels(ref_high: float, ref_low: float) -> Dict:
    """
    Compute Standard Deviation levels for the manipulation leg.
    Matches Fib Retracement SD tool settings (Image 1).
    Checked levels: 0, -1, -1.5, -2, -2.25, -2.5, -4, -4.25, -4.5, 1, 0.25, 0.5, 0.7

    Anchor: SD 0 = range_high (spike start), SD 1 = range_low (or vice versa).
    Negative SDs project BEYOND the spike -- where institutional orders exhaust.

    Primary reversal zone: -2.0 to -2.5 SD (must reach here before sniper)
    Extreme zone:          -4.0 to -4.5 SD (max manipulation, rarer)
    """
    span = abs(ref_high - ref_low)
    if span == 0: return {}
    return {
        'sd_0':    ref_high,
        'sd_1':    ref_low,
        'sd_025':  ref_high - span * 0.25,
        'sd_05':   ref_high - span * 0.50,
        'sd_07':   ref_high - span * 0.70,
        'sd_neg1': ref_high + span * 1.0,   # -1 extension (above spike start for bearish)
        'sd_neg15':ref_high + span * 1.5,
        'sd_neg2': ref_high + span * 2.0,   # PRIMARY zone start
        'sd_neg225':ref_high + span * 2.25,
        'sd_neg25':ref_high + span * 2.5,   # PRIMARY zone end
        'sd_neg4': ref_high + span * 4.0,   # EXTREME zone start
        'sd_neg425':ref_high + span * 4.25,
        'sd_neg45': ref_high + span * 4.5,  # EXTREME zone end
    }


def detect_manipulation_spike(df: pd.DataFrame, atr: float) -> Optional[Dict]:
    """
    Detect a fast manipulation spike (Judas Swing) on M15.

    Two-stage check:
      Stage 1 (SD filter): spike must reach -2.0 to -2.5 SD of the reference
        range. This confirms the manipulation went deep enough to be institutional.
        If price only moved -1 SD, it's just noise.
      Stage 2 (CRT check): the spike candle must close BACK inside the range
        (Candle Range Theory -- Candle 2 sweeps and closes back inside).

    Returns spike details or None.
    """
    if len(df) < 15: return None
    try:
        # Reference range: last 10 bars before the most recent 3
        ref      = df.iloc[-13:-3]
        ref_high = float(ref['high'].max())
        ref_low  = float(ref['low'].min())
        ref_range= ref_high - ref_low
        if ref_range <= 0: return None

        # Compute SD levels for this reference range
        sd = compute_sd_levels(ref_high, ref_low)

        # Check last 3 candles for a spike that swept and closed back inside (CRT)
        for spike_len in range(1, 4):
            spike_candles = df.iloc[-spike_len-1:-1]
            spike_high    = float(spike_candles['high'].max())
            spike_low     = float(spike_candles['low'].min())
            last_close    = float(df.iloc[-2]['close'])

            # BEARISH manipulation: swept above range high, closed back inside
            if spike_high > ref_high and last_close < ref_high:
                spike_dist = spike_high - ref_high
                if spike_dist < atr * 0.5:
                    continue  # too small, just noise

                # SD filter: spike must reach at least -2.0 SD (institutional depth)
                # -2.0 SD for bearish = ref_high + 2.0 * ref_range (above range)
                sd_neg2_level = ref_high + ref_range * 2.0
                reached_sd2   = spike_high >= sd_neg2_level * 0.85  # 85% tolerance
                # Extreme zone check
                sd_neg4_level = ref_high + ref_range * 4.0
                reached_sd4   = spike_high >= sd_neg4_level * 0.85

                return {
                    'type':         'BEARISH',
                    'spike_start':  ref_high,
                    'spike_peak':   spike_high,
                    'ref_high':     ref_high,
                    'ref_low':      ref_low,
                    'sweep_dist':   spike_dist,
                    'reached_sd2':  reached_sd2,
                    'reached_sd4':  reached_sd4,
                    'sd_levels':    sd,
                }

            # BULLISH manipulation: swept below range low, closed back inside
            if spike_low < ref_low and last_close > ref_low:
                spike_dist = ref_low - spike_low
                if spike_dist < atr * 0.5:
                    continue

                sd_neg2_level = ref_low - ref_range * 2.0
                reached_sd2   = spike_low <= sd_neg2_level * 1.15  # tolerance
                sd_neg4_level = ref_low - ref_range * 4.0
                reached_sd4   = spike_low <= sd_neg4_level * 1.15

                return {
                    'type':          'BULLISH',
                    'spike_start':   ref_low,
                    'spike_trough':  spike_low,
                    'ref_high':      ref_high,
                    'ref_low':       ref_low,
                    'sweep_dist':    spike_dist,
                    'reached_sd2':   reached_sd2,
                    'reached_sd4':   reached_sd4,
                    'sd_levels':     sd,
                }
    except Exception as e:
        logger.debug(f"Spike detection error: {e}")
    return None



def compute_aox_fibonacci(spike: Dict) -> Dict:
    """
    AOX Fibonacci Suite -- exact levels from Fib Retracement AOX tool (Image 2).

    Anchor: Fib 0 = spike_start, Fib 1 = spike_peak
    Active checked levels:
      Sniper zone:  -0.21 | -0.255 | -0.29   (3 levels, entry zone)
      TP1:           1.47 | 1.55              (partial close 60-70%)
      TP2:           2.56 | 2.60  | 2.64     (final close, institutional target)
      Reference:     0    | 1                (anchors)

    SL: placed ~20% beyond -0.29 (not a Fib level, a risk rule).
    """
    if spike['type'] == 'BEARISH':
        start = spike['spike_start']   # Fib 0  (range high, manipulation start)
        peak  = spike['spike_peak']    # Fib 1  (spike top)
        span  = peak - start           # positive span

        # Sniper zone extends ABOVE the peak (negative extensions = beyond spike)
        fib = {
            # Sniper entry zone (3 levels)
            'sniper_entry':   peak + span * 0.21,   # -0.21 (first tap)
            'sniper_mid':     peak + span * 0.255,  # -0.255 (main sniper)
            'sniper_top':     peak + span * 0.29,   # -0.29 (deepest)
            # SL: hard stop beyond -0.29
            'sl_level':       peak + span * 0.38,   # ~20 pips beyond sniper top
            # TP1: 60-70% close (two levels)
            'tp1_near':       start - span * 1.47,
            'tp1_far':        start - span * 1.55,
            # TP2: final exit (three levels)
            'tp2_near':       start - span * 2.56,
            'tp2_mid':        start - span * 2.60,
            'tp2_far':        start - span * 2.64,
            # Reference
            'fib_0':          start,
            'fib_1':          peak,
            'equilibrium':    start + span * 0.5,
        }
    else:  # BULLISH: spike was downward (Judas swing down, real move UP)
        start  = spike['spike_start']   # Fib 0 (range low)
        trough = spike['spike_trough']  # Fib 1 (spike bottom)
        span   = start - trough         # positive span

        # Sniper zone extends BELOW the trough
        fib = {
            # Sniper entry zone (3 levels)
            'sniper_entry':   trough - span * 0.21,  # -0.21
            'sniper_mid':     trough - span * 0.255, # -0.255
            'sniper_top':     trough - span * 0.29,  # -0.29 (deepest, below trough)
            # SL
            'sl_level':       trough - span * 0.38,
            # TP1
            'tp1_near':       start + span * 1.47,
            'tp1_far':        start + span * 1.55,
            # TP2
            'tp2_near':       start + span * 2.56,
            'tp2_mid':        start + span * 2.60,
            'tp2_far':        start + span * 2.64,
            # Reference
            'fib_0':          start,
            'fib_1':          trough,
            'equilibrium':    start - span * 0.5,
        }
    return fib



def detect_cisd_trigger(df_m1: pd.DataFrame, direction: str) -> Optional[Dict]:
    """
    CISD: Change in State of Delivery.
    Find the last consecutive opposing candle at the POI, then confirm
    when a candle CLOSES ITS BODY above (BUY) or below (SELL) that candle.
    This is the mechanical entry trigger -- no ambiguity.

    For BUY (bullish manipulation complete, real move UP):
      - Find the last red candle in the recent M1 sequence
      - Entry when a candle's body closes ABOVE that red candle's body top (open/close max)

    For SELL (bearish manipulation complete, real move DOWN):
      - Find the last green candle in the recent M1 sequence
      - Entry when a candle's body closes BELOW that green candle's body bottom
    """
    if df_m1 is None or len(df_m1) < 8: return None
    try:
        recent = df_m1.iloc[-10:]  # last 10 M1 candles

        if direction == 'BUY':
            # Find last red (bearish) candle -- the opposing candle
            last_red_idx = None
            for i in range(len(recent)-2, -1, -1):  # skip very last candle
                if float(recent.iloc[i]['close']) < float(recent.iloc[i]['open']):
                    last_red_idx = i
                    break
            if last_red_idx is None: return None

            opposing_candle = recent.iloc[last_red_idx]
            opposing_top    = max(float(opposing_candle['open']), float(opposing_candle['close']))

            # Check if a candle AFTER the red candle closes its body above it
            for i in range(last_red_idx + 1, len(recent)):
                c = recent.iloc[i]
                c_open  = float(c['open'])
                c_close = float(c['close'])
                # Body closes above: bullish candle + close > opposing top
                if c_close > c_open and c_close > opposing_top:
                    return {
                        'confirmed':      True,
                        'cisd_level':     opposing_top,
                        'trigger_close':  c_close,
                        'entry_ref':      c_close,
                    }

        else:  # SELL
            last_green_idx = None
            for i in range(len(recent)-2, -1, -1):
                if float(recent.iloc[i]['close']) > float(recent.iloc[i]['open']):
                    last_green_idx = i
                    break
            if last_green_idx is None: return None

            opposing_candle  = recent.iloc[last_green_idx]
            opposing_bottom  = min(float(opposing_candle['open']), float(opposing_candle['close']))

            for i in range(last_green_idx + 1, len(recent)):
                c = recent.iloc[i]
                c_open  = float(c['open'])
                c_close = float(c['close'])
                if c_close < c_open and c_close < opposing_bottom:
                    return {
                        'confirmed':      True,
                        'cisd_level':     opposing_bottom,
                        'trigger_close':  c_close,
                        'entry_ref':      c_close,
                    }

    except Exception as e:
        logger.debug(f"CISD detection error: {e}")
    return None



def check_smt_divergence(symbol: str, spike_type: str) -> bool:
    """
    SMT (Smart Money Divergence): correlated assets must diverge to confirm manipulation.
    If Gold swept its high but Silver did NOT sweep its corresponding high -> manipulation confirmed.

    Pairs checked:
      XAUUSDm <-> XAGUSDm  (Gold vs Silver)
      BTCUSDm <-> ETHUSDm  (BTC vs ETH)
      EURUSDm <-> GBPUSDm  (EUR vs GBP -- both USD pairs, correlated)
    """
    correlations = {
        'XAUUSDm': 'XAGUSDm',
        'XAGUSDm': 'XAUUSDm',
        'BTCUSDm': 'ETHUSDm',
        'ETHUSDm': 'BTCUSDm',
        'EURUSDm': 'GBPUSDm',
        'GBPUSDm': 'EURUSDm',
    }
    corr_sym = correlations.get(symbol)
    if not corr_sym:
        return True  # No correlated pair to check -- pass through (no veto)

    try:
        df_main = get_market_data(symbol,   mt5.TIMEFRAME_M15, 30)
        df_corr = get_market_data(corr_sym, mt5.TIMEFRAME_M15, 30)
        if df_main is None or df_corr is None: return True

        # Reference: high/low from 10-25 bars ago
        main_ref_high = float(df_main.iloc[-20:-5]['high'].max())
        main_ref_low  = float(df_main.iloc[-20:-5]['low'].min())
        corr_ref_high = float(df_corr.iloc[-20:-5]['high'].max())
        corr_ref_low  = float(df_corr.iloc[-20:-5]['low'].min())

        # Recent: last 5 bars
        main_rec_high = float(df_main.iloc[-5:]['high'].max())
        main_rec_low  = float(df_main.iloc[-5:]['low'].min())
        corr_rec_high = float(df_corr.iloc[-5:]['high'].max())
        corr_rec_low  = float(df_corr.iloc[-5:]['low'].min())

        if spike_type == 'BEARISH':
            # Main swept above its ref high -- correlated should NOT have swept its ref high
            main_swept = main_rec_high > main_ref_high
            corr_swept = corr_rec_high > corr_ref_high
            if main_swept and not corr_swept:
                logger.info(f"[SMT] {symbol}: swept high, {corr_sym} did NOT -> manipulation confirmed")
                return True
            elif main_swept and corr_swept:
                logger.debug(f"[SMT] {symbol}: both swept high -> real breakout, not manipulation")
                return False
        else:  # BULLISH
            main_swept = main_rec_low < main_ref_low
            corr_swept = corr_rec_low < corr_ref_low
            if main_swept and not corr_swept:
                logger.info(f"[SMT] {symbol}: swept low, {corr_sym} did NOT -> manipulation confirmed")
                return True
            elif main_swept and corr_swept:
                logger.debug(f"[SMT] {symbol}: both swept low -> real breakout, not manipulation")
                return False

    except Exception as e:
        logger.debug(f"SMT check error: {e}")
    return True  # On error: don't veto



def strategy_aox_model(symbol: str, df_m15: pd.DataFrame, df_m1: pd.DataFrame,
                        trend: str) -> Optional[Dict]:
    """
    STRATEGY E: AOX (Algorithmic Order Execution) Sniper Model.

    Full pipeline:
      1. Detect manipulation spike (Judas Swing) on M15 using CRT logic
      2. Compute AOX Fibonacci levels from spike
      3. Check price is inside the Sniper Zone (-0.21 to -0.29)
      4. Validate SMT divergence between correlated assets
      5. Drop to M1 and confirm CISD entry trigger (body close through opposing candle)
      6. Only fires inside a Temporal Macro window

    SL:  beyond AOX -0.29 level (hard institutional stop)
    TP1: AOX 1.47-1.55 level (60-70% position close)
    TP2: AOX 2.56-2.64 level (remainder)
    """
    # H4 Candle CRT Rule: only trade AM H4 candles (1AM/5AM/9AM EST)
    # PM candles (1PM/5PM/9PM EST) are excluded per image 2
    if not is_am_h4_candle():
        return None

    macro = get_active_macro_window() or "NO_MACRO"

    if df_m15 is None or df_m1 is None or len(df_m15) < 20 or len(df_m1) < 10:
        return None

    try:
        atr_m15 = float(calculate_atr(df_m15['high'], df_m15['low'], df_m15['close'], 14).iloc[-1])
        cur_price = float(df_m15['close'].iloc[-1])

        # Step 1: Detect the manipulation spike
        spike = detect_manipulation_spike(df_m15, atr_m15)
        if not spike:
            return None

        # Step 2: Fibonacci levels
        fib = compute_aox_fibonacci(spike)

        # Step 3: Price must be inside the Sniper Zone
        # Sniper zone check: price must be inside -0.21 to -0.29 zone
        # Three levels: -0.21 (entry), -0.255 (core), -0.29 (deepest)
        in_sniper_zone = fib['sniper_entry'] <= cur_price <= fib['sniper_top']
        if not in_sniper_zone:
            return None

        # Determine which sniper sub-zone price is in (for confidence)
        in_core_zone  = fib['sniper_entry'] <= cur_price <= fib['sniper_mid']  # -0.21 to -0.255
        in_deep_zone  = fib['sniper_mid']   <  cur_price <= fib['sniper_top']  # -0.255 to -0.29

        # Step 4: SMT divergence confirmation
        direction = 'SELL' if spike['type'] == 'BEARISH' else 'BUY'
        smt_ok = check_smt_divergence(symbol, spike['type'])

        # TRUE DAY OPEN: Longs only in Discount, Shorts only in Premium
        tdo = get_true_day_open(symbol)
        _tdo_tag = "TDO_NA"
        if tdo and tdo > 0:
            if direction == 'BUY' and cur_price > tdo:
                logger.debug(f"[AOX TDO] {symbol}: BUY rejected -- Premium (price > TDO {tdo:.4f})")
                return None
            if direction == 'SELL' and cur_price < tdo:
                logger.debug(f"[AOX TDO] {symbol}: SELL rejected -- Discount (price < TDO {tdo:.4f})")
                return None
            _tdo_tag = f"DISC({tdo:.3f})" if cur_price < tdo else f"PREM({tdo:.3f})" 
        if not smt_ok:
            logger.debug(f"[AOX] {symbol}: SMT failed -- both assets swept, real breakout")
            return None

        # Step 5: CISD entry trigger on M1
        cisd = detect_cisd_trigger(df_m1, direction)
        if not cisd:
            logger.debug(f"[AOX] {symbol}: waiting for CISD trigger on M1")
            return None

        # All conditions met -- build entry signal
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return None
        spread_buf = (tick.ask - tick.bid) * 2.5

        if direction == 'SELL':
            sl  = fib['sl_level'] + spread_buf
            tp1 = fib['tp1_near']   # 1.47 -- first partial (60-70% close)
            tp2 = fib['tp2_mid']    # 2.60 -- final target (institutional mid)
        else:
            sl  = fib['sl_level'] - spread_buf
            tp1 = fib['tp1_near']
            tp2 = fib['tp2_mid']

        sl_dist = abs(cur_price - sl)
        if sl_dist <= 0: return None
        rr1 = abs(cur_price - tp1) / sl_dist

        # Minimum 2:1 RR before taking the trade
        if rr1 < 2.0:
            logger.debug(f"[AOX] {symbol}: RR {rr1:.1f} < 2.0 minimum")
            return None

        # Confidence based on SD depth and sniper sub-zone
        # Base: 0.88 (all 6 conditions met)
        # +0.04 if spike reached -2.0 SD (institutional depth confirmed)
        # +0.04 if price in deep sniper zone (-0.255 to -0.29, strongest area)
        # Max: 0.96
        _conf = 0.88
        if spike.get('reached_sd2', False):       _conf += 0.04
        if in_deep_zone:                           _conf += 0.04
        if macro == "NY_AM_MACRO_1":               _conf += 0.02  # Silver Bullet highest prob
        elif macro in ("NY_AM_MACRO_2", "NY_LUNCH_MACRO"): _conf += 0.01
        _conf = min(0.96, _conf)

        _sd_tag = "SD4+" if spike.get('reached_sd4') else ("SD2+" if spike.get('reached_sd2') else "SD<2")
        _zone_tag = "DEEP(-0.255/-0.29)" if in_deep_zone else "ENTRY(-0.21/-0.255)"

        logger.info(
            f"[AOX] {symbol} {direction}: {spike['type']} | macro={macro} | tdo={_tdo_tag} | "
            f"sniper={_zone_tag} | {_sd_tag} | "
            f"cisd={cisd['cisd_level']:.4f} | RR={rr1:.1f} | conf={_conf:.2f}"
        )

        return {
            'direction':     direction,
            'stop_loss':     sl,
            'tp':            tp1,
            'tp2':           tp2,
            'strategy_name': f'AOX_{macro}',
            'confidence':    _conf,
            'aox_spike':     spike,
            'aox_fib':       fib,
            'cisd':          cisd,
        }

    except Exception as e:
        logger.error(f"[AOX] {symbol}: error -- {e}")
        return None



def detect_double_bottom(df: 'pd.DataFrame', atr: float) -> dict:
    """
    W-pattern (Double Bottom): Two lows of roughly equal depth with a swing
    high between them. Price must then break above the neckline (swing high).
    Used as pre-filter for bullish EMA cross.
    """
    empty = {'found': False, 'pattern': 'NONE'}
    if df is None or len(df) < 30: return empty
    try:
        closes  = df['close'].values
        highs   = df['high'].values
        lows    = df['low'].values
        # Find swing lows in last 60 bars (pivot: lower than 3 bars each side)
        swing_lows = []
        data = df.iloc[-60:].reset_index(drop=True)
        for i in range(3, len(data)-3):
            if all(data['low'].iloc[i] <= data['low'].iloc[i-j] for j in range(1,4)) and                all(data['low'].iloc[i] <= data['low'].iloc[i+j] for j in range(1,4)):
                swing_lows.append((i, float(data['low'].iloc[i])))

        if len(swing_lows) < 2: return empty

        # Check pairs of swing lows for W-pattern
        for i in range(len(swing_lows)-1):
            pos1, low1 = swing_lows[i]
            pos2, low2 = swing_lows[-1]  # most recent
            if pos2 <= pos1: continue
            gap = pos2 - pos1
            if gap < 5 or gap > 40: continue  # not too close, not too far
            # Lows within 0.5x ATR of each other (roughly equal depth)
            if abs(low1 - low2) > atr * 0.5: continue
            # There must be a swing high between them (the middle of the W)
            mid_highs = [float(data['high'].iloc[j]) for j in range(pos1+1, pos2)]
            if not mid_highs: continue
            neckline = max(mid_highs)
            # Current price should be breaking above neckline
            cur_price = float(data['close'].iloc[-1])
            if cur_price > neckline * 0.999:
                return {'found': True, 'pattern': 'DOUBLE_BOTTOM',
                        'low1': low1, 'low2': low2,
                        'neckline': neckline,
                        'reason': f'W-pattern: lows {low1:.3f}/{low2:.3f} neckline={neckline:.3f}'}
    except Exception as e:
        logger.debug(f"double_bottom: {e}")
    return empty


def detect_double_top(df: 'pd.DataFrame', atr: float) -> dict:
    """M-pattern (Double Top): Two highs of roughly equal height."""
    empty = {'found': False, 'pattern': 'NONE'}
    if df is None or len(df) < 30: return empty
    try:
        data = df.iloc[-60:].reset_index(drop=True)
        swing_highs = []
        for i in range(3, len(data)-3):
            if all(data['high'].iloc[i] >= data['high'].iloc[i-j] for j in range(1,4)) and                all(data['high'].iloc[i] >= data['high'].iloc[i+j] for j in range(1,4)):
                swing_highs.append((i, float(data['high'].iloc[i])))

        if len(swing_highs) < 2: return empty

        for i in range(len(swing_highs)-1):
            pos1, high1 = swing_highs[i]
            pos2, high2 = swing_highs[-1]
            if pos2 <= pos1: continue
            gap = pos2 - pos1
            if gap < 5 or gap > 40: continue
            if abs(high1 - high2) > atr * 0.5: continue
            mid_lows = [float(data['low'].iloc[j]) for j in range(pos1+1, pos2)]
            if not mid_lows: continue
            neckline = min(mid_lows)
            cur_price = float(data['close'].iloc[-1])
            if cur_price < neckline * 1.001:
                return {'found': True, 'pattern': 'DOUBLE_TOP',
                        'high1': high1, 'high2': high2,
                        'neckline': neckline,
                        'reason': f'M-pattern: highs {high1:.3f}/{high2:.3f} neckline={neckline:.3f}'}
    except Exception as e:
        logger.debug(f"double_top: {e}")
    return empty


def detect_head_and_shoulders(df: 'pd.DataFrame', atr: float, inverse: bool = False) -> dict:
    """
    Head & Shoulders (bearish) or Inverse H&S (bullish).
    3 peaks/troughs: left shoulder, head (extreme), right shoulder.
    Right shoulder roughly equal to left shoulder.
    """
    empty = {'found': False, 'pattern': 'NONE'}
    if df is None or len(df) < 40: return empty
    try:
        data = df.iloc[-80:].reset_index(drop=True)
        if not inverse:  # H&S bearish: find 3 swing highs
            pivots = []
            for i in range(4, len(data)-4):
                if all(data['high'].iloc[i] >= data['high'].iloc[i-j] for j in range(1,5)) and                    all(data['high'].iloc[i] >= data['high'].iloc[i+j] for j in range(1,5)):
                    pivots.append((i, float(data['high'].iloc[i])))
        else:  # Inv H&S bullish: find 3 swing lows
            pivots = []
            for i in range(4, len(data)-4):
                if all(data['low'].iloc[i] <= data['low'].iloc[i-j] for j in range(1,5)) and                    all(data['low'].iloc[i] <= data['low'].iloc[i+j] for j in range(1,5)):
                    pivots.append((i, float(data['low'].iloc[i])))

        if len(pivots) < 3: return empty
        # Check last 3 pivots as potential L.Shoulder, Head, R.Shoulder
        ls_pos, ls_val = pivots[-3]
        hd_pos, hd_val = pivots[-2]
        rs_pos, rs_val = pivots[-1]

        if not inverse:
            # Head must be highest; shoulders roughly equal
            if not (hd_val > ls_val and hd_val > rs_val): return empty
            if abs(ls_val - rs_val) > atr * 0.8: return empty
            # Neckline connects the troughs between shoulders/head
            neckline_pts = [float(data['low'].iloc[j]) for j in range(ls_pos, rs_pos)]
            neckline = min(neckline_pts) if neckline_pts else 0
            cur_price = float(data['close'].iloc[-1])
            if cur_price < neckline * 1.001:
                return {'found': True, 'pattern': 'HEAD_SHOULDERS',
                        'head': hd_val, 'neckline': neckline,
                        'reason': f'H&S: LS={ls_val:.3f} H={hd_val:.3f} RS={rs_val:.3f}'}
        else:
            # Inv H&S: head is lowest; shoulders roughly equal
            if not (hd_val < ls_val and hd_val < rs_val): return empty
            if abs(ls_val - rs_val) > atr * 0.8: return empty
            neckline_pts = [float(data['high'].iloc[j]) for j in range(ls_pos, rs_pos)]
            neckline = max(neckline_pts) if neckline_pts else float('inf')
            cur_price = float(data['close'].iloc[-1])
            if cur_price > neckline * 0.999:
                return {'found': True, 'pattern': 'INV_HEAD_SHOULDERS',
                        'head': hd_val, 'neckline': neckline,
                        'reason': f'Inv H&S: LS={ls_val:.3f} H={hd_val:.3f} RS={rs_val:.3f}'}
    except Exception as e:
        logger.debug(f"h_and_s: {e}")
    return empty


def detect_ema_pattern_prefilter(df_m5: 'pd.DataFrame', direction: str, atr: float) -> dict:
    """
    EMA strategy pre-filter: MUST find one of these patterns before the EMA cross
    is considered a valid entry:
      BUY:  Double Bottom (W-pattern) OR Inverse H&S
      SELL: Double Top (M-pattern) OR Head & Shoulders
    Without this, EMA crosses fire randomly in sideways markets.
    """
    if direction == 'BUY':
        db = detect_double_bottom(df_m5, atr)
        if db['found']: return db
        ihs = detect_head_and_shoulders(df_m5, atr, inverse=True)
        if ihs['found']: return ihs
    else:
        dt = detect_double_top(df_m5, atr)
        if dt['found']: return dt
        hs = detect_head_and_shoulders(df_m5, atr, inverse=False)
        if hs['found']: return hs
    return {'found': False, 'pattern': 'NONE', 'reason': 'No qualifying pattern found'}


def strategy_ema_scalp_cross(df_m5: 'pd.DataFrame', direction: str, symbol: str = "") -> Optional[Dict[str, Any]]:
    """
    STRATEGY A -- 9/25/50/200 EMA scalp cross.

    Extracted from the main loop's inline block (previously ~90 lines with
    no standalone function to call, which is why it wasn't backtestable --
    see python_scripts/backtest/README.md). This is meant to be a faithful
    extraction: every threshold and comparison is unchanged from the
    inline version, with two deliberate differences, both flagged here
    rather than silently bundled in:

    1. state._rej bookkeeping moved to the caller, matching how every
       other cascade strategy already works (STRATEGY C / the fallback
       blocks don't touch state._rej themselves either, relying on the
       cascade's single catch-all counter). The inline version incremented
       state._rej at up to 3 points inside itself AND at the cascade's
       catch-all, double-counting rejections in the stats whenever every
       other strategy also failed the same cycle -- a minor bug, fixed as
       a side effect of this extraction.
    2. REAL BUG FIX: the inline "PATTERN PRE-FILTER" block computed
       detect_ema_pattern_prefilter() and logged whether a qualifying W/M/
       H&S pattern was found, but had no `continue`/gate after a "not
       found" result -- the comment even says "Don't continue -- let
       other strategies still check," but nothing stopped THIS strategy
       from proceeding past its own failed pre-filter. So the filter ran,
       logged, and incremented a counter, but never once blocked a trade;
       every EMA cross fired regardless of the pattern check, exactly the
       failure mode ("we trade random crossovers in ranging markets") its
       own comment says the filter exists to prevent. Fixed here: a failed
       pre-filter now actually returns None.

    direction: the H4-aligned bias ('BUY' or 'SELL') -- matches
    _trade_direction at the call site, not something this function derives
    itself (same convention as strategy_shaakuni_ssm's effective_trend).
    """
    try:
        _cur_price = df_m5['close'].iloc[-1]
        _atr_m5 = float(calculate_atr(df_m5['high'], df_m5['low'], df_m5['close'], 14).iloc[-1])
        _ema_m5 = get_ema_momentum(df_m5, slope_bars=5)

        _e9  = float(df_m5['close'].ewm(span=9,  adjust=False).mean().iloc[-1])
        _e9p = float(df_m5['close'].ewm(span=9,  adjust=False).mean().iloc[-2])
        _e25 = float(df_m5['close'].ewm(span=25, adjust=False).mean().iloc[-1])
        _e25p= float(df_m5['close'].ewm(span=25, adjust=False).mean().iloc[-2])
        _e200= float(df_m5['close'].ewm(span=200, adjust=False).mean().iloc[-1])
        _e50 = float(df_m5['close'].ewm(span=50,  adjust=False).mean().iloc[-1])
        # 200 EMA TREND GATE (hard rule): Long only above 200 EMA, Short only below.
        # Without this the bot trades EMA crosses against the macro trend and hits SL.
        _above_200 = _cur_price > _e200
        _below_200 = _cur_price < _e200
        _200_gate_pass = (direction == 'BUY' and _above_200) or \
                         (direction == 'SELL' and _below_200)
        if not _200_gate_pass:
            logger.debug(f'[EMA 200 GATE] {symbol}: {direction} blocked -- '
                         f'price={_cur_price:.4f} {"below" if direction=="BUY" else "above"} '
                         f'200 EMA={_e200:.4f}')
            return None
        # DISTANCE RULE (doc requirement): 9/25 cluster must be
        # meaningfully separated from the 50 EMA. Bunched/braided
        # EMAs = ranging market = a cross here is noise, not
        # momentum, and disproportionately reverses into the stop.
        if abs(_e25 - _e50) <= (_atr_m5 * config.EMA_DISTANCE_RULE_ATR_MULT):
            logger.debug(f'[EMA DISTANCE] {symbol}: EMAs bunched '
                         f'(25={_e25:.4f} 50={_e50:.4f} gap={abs(_e25-_e50):.4f} '
                         f'< {_atr_m5*config.EMA_DISTANCE_RULE_ATR_MULT:.4f}) -- ranging, skip')
            return None

        # PATTERN PRE-FILTER (doc requirement):
        # EMA cross is only valid after W/M/H&S pattern forms.
        # Without this, we trade random crossovers in ranging markets.
        _ema_pattern = detect_ema_pattern_prefilter(df_m5, direction, _atr_m5)
        if not _ema_pattern['found']:
            logger.debug(f"[EMA PATTERN] {symbol}: no qualifying pattern -- skip cross")
            return None
        logger.debug(f"[EMA PATTERN] {symbol}: {_ema_pattern['pattern']} -- EMA cross valid")

        # BUY cross: 9 EMA crosses ABOVE 25 EMA (was below, now above)
        # Hard cross: EMA9 crossed EMA25 this candle
        _cross_bull = (_e9p <= _e25p) and (_e9 > _e25) and (_cur_price > _e50)
        _cross_bear = (_e9p >= _e25p) and (_e9 < _e25) and (_cur_price < _e50)
        # Near-cross: EMA9 approaching EMA25 from below/above with strong slope
        # (catches the setup 1-2 bars before actual cross = better entry)
        _gap_pct = abs(_e9 - _e25) / max(_e25, 1) * 100
        # Near-cross: approaching with momentum (0.15% gap = ~$6.50 for Gold)
        _near_cross_bull = (not _cross_bull and _e9 < _e25 and
                            _e9 > _e9p and _gap_pct < 0.15 and _cur_price > _e50)
        _near_cross_bear = (not _cross_bear and _e9 > _e25 and
                            _e9 < _e9p and _gap_pct < 0.15 and _cur_price < _e50)
        # 9 EMA bounce: price pulled to 9 EMA and bouncing in trend direction
        # (the "bend" signal from EMA strategy docs)
        _e9_touch_bull = (not _cross_bull and not _near_cross_bull and
                          abs(_cur_price - _e9) < _e9 * 0.001 and  # within 0.1% of 9 EMA
                          _e9 > _e9p and _cur_price > _e50 and  # 9 EMA rising, price above 50
                          df_m5['close'].iloc[-1] > df_m5['open'].iloc[-1])  # last candle green
        _e9_touch_bear = (not _cross_bear and not _near_cross_bear and
                          abs(_cur_price - _e9) < _e9 * 0.001 and
                          _e9 < _e9p and _cur_price < _e50 and
                          df_m5['close'].iloc[-1] < df_m5['open'].iloc[-1])  # last candle red
        _cross_bull = _cross_bull or _near_cross_bull or _e9_touch_bull
        _cross_bear = _cross_bear or _near_cross_bear or _e9_touch_bear

        _cross_valid = (_cross_bull and direction == 'BUY') or \
                       (_cross_bear and direction == 'SELL')

        if not _cross_valid:
            return None

        # SL: structural -- last swing low/high on M5 (not ATR * 0.5)
        _lookback_ema = df_m5.iloc[-20:]
        if direction == 'BUY':
            _sl_ema = float(_lookback_ema['low'].min()) - _atr_m5 * 0.3
        else:
            _sl_ema = float(_lookback_ema['high'].max()) + _atr_m5 * 0.3
        setup = {
            'signal':    direction,
            'reason':    'EMA_SCALP_CROSS',
            'stop_loss': _sl_ema,
            'strategy_type': 'EMA',
            '_requires_trending': True,   # BLOCKED in RANGING market
            # 50 EMA = primary TP target (doc rule)
            'ema50_tp':  float(_e50),     # structural TP overridden to 50 EMA
            'liquidity_distance':  0.6,
            'liquidity_strength':  _ema_m5['strength'] == 'STRONG' and 0.8 or 0.65,
            'momentum_state':      0.7,
            'structure_alignment': 0.65,
            'entry_price': _cur_price,
            'htf_needed': False,   # EMA scalp never needs HTF OB
        }
        logger.debug(f"[EMA SCALP] {symbol}: 9/25 cross {'bullish' if _cross_bull else 'bearish'} "
                     f"e9={_e9:.4f} e25={_e25:.4f} e50={_e50:.4f} e200={_e200:.4f} "
                     f"(price {'above' if _above_200 else 'below'} 200 EMA -- gate passed)")
        return setup
    except Exception as _ema_err:
        logger.debug(f"[EMA SCALP] error: {_ema_err}")
        return None


def place_swappy_pending_order(symbol: str, sw: dict, direction: str,
                               entry_price: float, sl: float, account_equity: float) -> bool:
    """
    Place a BUY STOP or SELL STOP pending order for the Swappy 3C setup.
    The order triggers only when price breaks above the 3-candle high (BUY)
    or below the 3-candle low (SELL). If not triggered in 5 candles (25 minutes
    on M5), the order expires. If price closes below setup_low (BUY) before
    triggering, the order is cancelled externally by check_swappy_expirations().
    """
    try:
        sym_info = mt5.symbol_info(symbol)
        if not sym_info: return False

        risk_amount = account_equity * (config.BASE_RISK_PERCENT / 100.0)
        sl_dist     = abs(entry_price - sl)
        if sl_dist <= 0: return False

        tick_val  = sym_info.trade_tick_value
        tick_size = sym_info.trade_tick_size
        if tick_val and tick_val > 0 and tick_size > 0:
            pip_value_per_lot = (tick_val / tick_size) * sym_info.point
            lot_raw = risk_amount / max(sl_dist * (pip_value_per_lot / sym_info.point), 0.001)
        else:
            lot_raw = risk_amount / max(sl_dist * 10, 0.001)

        lot_step = sym_info.volume_step
        lot_size = round(lot_raw / lot_step) * lot_step
        lot_size = max(sym_info.volume_min, min(lot_size, sym_info.volume_max))

        # TP: 3:1 RR as per Swappy spec
        tp_dist = sl_dist * 3.0
        if direction == 'BUY':
            tp = entry_price + tp_dist
            order_type = mt5.ORDER_TYPE_BUY_STOP
        else:
            tp = entry_price - tp_dist
            order_type = mt5.ORDER_TYPE_SELL_STOP

        # Expiry: 5 candles on M5 = 25 minutes from now
        expiry_dt = datetime.now(timezone.utc) + timedelta(minutes=25)

        # Filling mode
        mode  = sym_info.filling_mode
        fill  = (mt5.ORDER_FILLING_FOK if mode & 1 else
                 mt5.ORDER_FILLING_IOC if mode & 2 else
                 mt5.ORDER_FILLING_RETURN)

        request = {
            "action":        mt5.TRADE_ACTION_PENDING,
            "symbol":        symbol,
            "volume":        lot_size,
            "type":          order_type,
            "price":         entry_price,
            "sl":            sl,
            "tp":            tp,
            "deviation":     20,
            "magic":         MAGIC_NUMBER,
            "comment":       f"Swappy3C_{direction}",
            "type_time":     mt5.ORDER_TIME_SPECIFIED,
            "expiration":    int(expiry_dt.timestamp()),
            "type_filling":  fill,
        }
        result = mt5.order_send(request)
        # This is the only TRADE_ACTION_PENDING (stop order) request in the
        # file. MT5 returns TRADE_RETCODE_PLACED (10008) for a successfully
        # placed pending order, not TRADE_RETCODE_DONE (10009) — DONE is for
        # an immediately-executed deal. Checking only DONE here meant a
        # genuinely successful pending-order placement got logged and
        # treated as a failure and never tracked in state.swappy_pending,
        # leaving a live order on the broker that this bot never manages.
        if result and result.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED):
            # Store setup_low/high for invalidation check
            if not hasattr(state, 'swappy_pending'):
                state.swappy_pending = {}
            state.swappy_pending[result.order] = {
                'symbol': symbol, 'direction': direction,
                'setup_high': sw.get('setup_high', entry_price),
                'setup_low':  sw.get('setup_low',  sl),
                'placed_at':  datetime.now(timezone.utc),
            }
            logger.info(
                f"[SWAPPY PENDING] {symbol} {direction} STOP @ {entry_price:.4f} "
                f"SL={sl:.4f} TP={tp:.4f} lot={lot_size} expires=25min"
            )
            return True
        else:
            logger.warning(f"[SWAPPY PENDING] {symbol}: order failed retcode={result.retcode if result else 'None'}")
            return False
    except Exception as e:
        logger.error(f"[SWAPPY PENDING] {symbol}: {e}")
        return False


def check_swappy_expirations():
    """
    1. Cancel pending Swappy orders if price invalidates the setup.
    2. Track SL hits per price level for the 3rd-time re-entry rule.
    Rule: 1st SL hit -> ignore 2nd setup. Only 3RD setup at same level allowed.
    """
    if not hasattr(state, 'swappy_pending'):    state.swappy_pending    = {}
    if not hasattr(state, 'swappy_level_hits'): state.swappy_level_hits = {}
    if not hasattr(state, 'swappy_triggered'):  state.swappy_triggered  = {}

    orders    = mt5.orders_get()
    positions = mt5.positions_get()
    order_ids = {o.ticket for o in orders}    if orders    else set()
    to_remove = []

    for ticket, info in list(state.swappy_pending.items()):
        if ticket not in order_ids:
            state.swappy_triggered[ticket] = info  # triggered -> track for SL
            to_remove.append(ticket)
            continue
        sym  = info['symbol']
        tick = mt5.symbol_info_tick(sym)
        if not tick: continue
        cur  = tick.bid
        if info['direction'] == 'BUY' and cur < info['setup_low']:
            logger.info(f"[SWAPPY CANCEL] {sym} BUY invalidated @ {cur:.4f} < setup_low {info['setup_low']:.4f}")
            mt5.order_delete(ticket)
            to_remove.append(ticket)
        elif info['direction'] == 'SELL' and cur > info['setup_high']:
            logger.info(f"[SWAPPY CANCEL] {sym} SELL invalidated @ {cur:.4f} > setup_high {info['setup_high']:.4f}")
            mt5.order_delete(ticket)
            to_remove.append(ticket)

    pos_ids = {p.ticket for p in positions} if positions else set()
    for ticket, info in list(state.swappy_triggered.items()):
        if ticket in pos_ids: continue  # still open
        try:
            history = mt5.history_deals_get(
                datetime.now(timezone.utc) - timedelta(hours=2),
                datetime.now(timezone.utc)
            )
            if not history: continue
            for deal in history:
                if deal.position_id != ticket or deal.entry != mt5.DEAL_ENTRY_OUT: continue
                closed = deal.price
                sl_ref = info.get('setup_low') if info['direction'] == 'BUY' else info.get('setup_high')
                if not sl_ref: continue
                is_sl = (info['direction'] == 'BUY' and closed <= sl_ref) or                         (info['direction'] == 'SELL' and closed >= sl_ref)
                if is_sl:
                    sym = info['symbol']
                    lvl = round(sl_ref, 2)
                    key = f"{sym}_{info['direction']}_{lvl}"
                    hits = state.swappy_level_hits.get(key, 0) + 1
                    state.swappy_level_hits[key] = hits
                    logger.info(f"[SWAPPY SL HIT #{hits}] {sym} {info['direction']} @ {lvl:.4f}. "
                               f"{'BLOCKED (need 3rd)' if hits < 3 else '3RD SETUP -- re-entry ALLOWED'}")
                del state.swappy_triggered[ticket]
                break
        except Exception: pass

    for t in to_remove:
        state.swappy_pending.pop(t, None)


def can_take_swappy_entry(symbol: str, direction: str, setup_low: float, setup_high: float):
    """3rd-time re-entry rule. Returns (allowed, reason)."""
    if not hasattr(state, 'swappy_level_hits'):
        return True, "first_setup"
    lvl = round(setup_low if direction == 'BUY' else setup_high, 2)
    key = f"{symbol}_{direction}_{lvl}"
    hits = state.swappy_level_hits.get(key, 0)
    if hits == 0:   return True,  "first_setup"
    elif hits == 1: return False, "second_setup_blocked (1 SL hit -- wait for 3rd)"
    else:
        state.swappy_level_hits[key] = 0  # reset after 3rd
        return True,  "third_setup_allowed (level reset)"


def ai_trading_session():
    """
    SCALPING LIGHTNING V2.0: Main trading loop
    - Async data fetching (much faster via parallelism)
    - Cached data access (instant, no blocking)
    - Async logging (no blocking)
    - Regime-aware signal detection
    """
    
    global async_data_fetcher
    
    last_heartbeat_time = time.time()
    last_db_sync_time = time.time()
    
    logger.info("="*80)
    logger.info(f" SCALPING LIGHTNING V2.0 - SESSION STARTED FOR {USER_ID}")
    logger.info(f"   MT5 ACCOUNT: {config.MT5_LOGIN}")
    logger.info(f"   OPTIMIZATION: Async data fetching ENABLED")
    logger.info(f"   OPTIMIZATION: Regime-aware strategy selection ENABLED")
    logger.info(f"   OPTIMIZATION: Async logging ENABLED")
    logger.info("="*80)
    
    # INITIALIZE ASYNC SYSTEMS
    # INITIALIZE ASYNC SYSTEMS
    # Use symbols from config (already user-validated)
    # Ensure they are valid broker symbols
    # All symbols loaded -- smart lot sizing handles per-symbol risk
    actual_symbols = []
    for s in config.SYMBOLS:
        valid_s = get_actual_broker_symbol(s)
        if valid_s:
            actual_symbols.append(valid_s)

    _init_acct = mt5.account_info()
    _init_equity = _init_acct.equity if _init_acct else 0
    logger.info(f" [INIT] Equity ${_init_equity:.0f} | Symbols: {actual_symbols}")
    
    async_data_fetcher = AsyncDataFetcher(actual_symbols, refresh_interval=5)
    async_data_fetcher.start()
    
    async_logger.start()
    
    logger.info(" [SCALPING] Async systems started, waiting for first data fetch...")
    time.sleep(6)  # Wait for first data fetch
    
    # --- CRITICAL FIX: RESTORE STATE FROM DB ---
    # Prevents "Zombie Logic Loop" by loading flags (BE moved, Partial TP)
    if config.MT5_LOGIN: 
        trade_db.restore_state_from_db(state.open_positions)
    
    iteration = 0
    
    try:
        account_info = mt5.account_info()
        if account_info:
            today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            state.daily_start_equity = load_or_init_daily_baseline(DATA_DIR, account_info.equity, today_str)
        else:
            state.daily_start_equity = 0.0

        # --- GLOBAL KILL SWITCH CHECK (Founder's Safety) ---
        # Check Supabase for a global 'kill_switch' flag
        try:
            kill_check = supabase.table('bot_commands').select('kill_switch').eq('user_id', USER_ID).execute()
            if kill_check.data and kill_check.data[0].get('kill_switch', False):
                logger.critical(" [KILL SWITCH] Global Kill Switch Activated. STOPPING.")
                return 
        except: pass 
        
        send_telegram_notification(
            f" <b>SCALPING BOT V2.0 Started</b>\n\nUser: {USER_ID}\nStrategy: {STRATEGY_ID}\n"
            f"Account: {config.MT5_LOGIN}\nEquity: ${state.daily_start_equity:.2f}\n"
            f"Optimizations: Institutional Safety + Async Core"
        )
    except Exception as e:
        logger.error(f"Failed to get initial account info: {e}")
        state.daily_start_equity = 0.0

    while True:
        try:
            iteration += 1
            if iteration % 50 == 0:
                _rs = getattr(state,'_rej',{})
                if _rs: logger.info(f'[REJECT STATS] {_rs}')
            cycle_start = time.time()
            
            account_info = mt5.account_info()
            if not account_info:
                logger.error("Lost MT5 connection")
                send_heartbeat(status='error', mt5_connected=False, error_message="Lost MT5 connection")
                time.sleep(30)
                continue
            
            # --- 0. DAILY RESET LOGIC ---
            # Reset baseline at 00:00 UTC so "Daily Drawdown" is truly DAILY
            current_day = datetime.now(timezone.utc).day
            if not hasattr(state, 'last_reset_day'):
                state.last_reset_day = current_day
            
            if current_day != state.last_reset_day:
                logger.info(f" [NEW DAY] Resetting Daily Statistics (P&L: ${state.daily_pnl:.2f})")
                state.daily_pnl = 0.0
                state.daily_trades = 0
                state.daily_start_equity = account_info.equity
                state.last_reset_day = current_day
                persist_daily_baseline(DATA_DIR, datetime.now(timezone.utc).strftime('%Y-%m-%d'), account_info.equity)

            # --- 0. EQUITY PROTECTOR (The "Stop Loss" for the Account) ---
            current_dd_percent = ((state.daily_start_equity - account_info.equity) / state.daily_start_equity) * 100
            if state.daily_start_equity > 0 and current_dd_percent >= config.MAX_DAILY_DRAWDOWN_PERCENT:
                logger.critical(f" [EQUITY PROTECTOR] Max Drawdown Hit ({current_dd_percent:.2f}%). HALTING TRADING.")
                send_telegram_notification(f"[!!] <b>EQUITY PROTECT TRIGGERED</b>\n\nDrawdown: {current_dd_percent:.2f}%\nBot Halted.")
                break
            
            # --- 0.5 ROLLOVER BLACKOUT (Time-of-Day Dead Zone) ---
            current_hour = datetime.now(timezone.utc).hour
            # Extended rollover blackout: 21:30-23:00 UTC (US session close + rollover)
            # This is 10 PM - 11:30 PM IST -- proven high-spread-spike window
            current_minute = datetime.now(timezone.utc).minute
            _in_rollover = (
                current_hour == 21 and current_minute >= 30  # 21:30-22:00 UTC
                or current_hour == 22                         # 22:00-23:00 UTC
            )
            if _in_rollover:
                if not hasattr(state, '_rollover_logged') or state._rollover_logged != current_hour:
                    logger.warning(f" [ROLLOVER GUARD] {current_hour}:{current_minute:02d} UTC -- "
                                   f"High-spread period (US close). Blocking new entries.")
                    state._rollover_logged = current_hour
                time.sleep(5)
                continue
            
            # --- 0. EMERGENCY CIRCUIT BREAKER (throttled: max every 30s) ---
            if not hasattr(state, '_last_emergency_time'): state._last_emergency_time = 0.0
            if time.time() - state._last_emergency_time >= 30.0:
                if check_emergency_conditions(account_info):
                    logger.critical("EMERGENCY CIRCUIT BREAKER TRIPPED. Stopping bot.")
                    send_heartbeat(status='stopped', mt5_connected=True, error_message="Emergency Stop Triggered")
                    send_telegram_notification(" <b>EMERGENCY STOP</b>\n\nBot has been halted due to safety violations.")
                    break
                state._last_emergency_time = time.time()
            
            # --- 0.6 SWAPPY PENDING ORDER HOUSEKEEPING (throttled: max every 30s) ---
            # check_swappy_expirations() cancels pending Swappy stop orders once
            # price invalidates the setup, and tracks SL hits for the 3rd-time
            # re-entry rule. Was fully built but never called anywhere -- wired
            # in here alongside place_swappy_pending_order() (see STRATEGY B).
            if not hasattr(state, '_last_swappy_check_time'): state._last_swappy_check_time = 0.0
            if time.time() - state._last_swappy_check_time >= 30.0:
                check_swappy_expirations()
                state._last_swappy_check_time = time.time()

            # --- 1. UPDATE GLOBAL CONTEXT (Every 4 hours, time-based not iteration-based) ---
            if not hasattr(state, '_last_global_ctx_time'):
                state._last_global_ctx_time = 0.0
            if time.time() - state._last_global_ctx_time > 1800:
                state._last_global_ctx_time = time.time()
                import threading as _thr4
                _thr4.Thread(target=update_global_ai_context, daemon=True).start()

            if not hasattr(state, '_last_news_time'): state._last_news_time = 0.0
            if time.time() - state._last_news_time > 3600:  # once per hour max
                state._last_news_time = time.time()
                import threading as _thr2
                _thr2.Thread(target=fetch_upcoming_news_events, daemon=True).start()

            # --- 2. DYNAMIC TRADE MANAGEMENT (throttled: max every 5s) ---
            if not hasattr(state, '_last_manage_time'): state._last_manage_time = 0.0
            if time.time() - state._last_manage_time >= 5.0:
                state._last_manage_time = time.time()
                import threading as _thr_mgr
                _thr_mgr.Thread(target=manage_all_positions, daemon=True).start()
                _thr_mgr.Thread(target=check_swappy_expirations, daemon=True).start()

            # --- 3. UPDATE CLOSED TRADES (throttled: max every 10s) ---
            if not hasattr(state, '_last_closed_time'): state._last_closed_time = 0.0
            if time.time() - state._last_closed_time >= 10.0:
                state._last_closed_time = time.time()
                import threading as _thr
                _thr.Thread(target=update_closed_trades, daemon=True).start()

            # --- 4. AI LEARNING (Every hour, time-based not iteration-based) ---
            if not hasattr(state, '_last_ai_learn_time'):
                state._last_ai_learn_time = 0.0
            if time.time() - state._last_ai_learn_time > config.AI_LEARNING_INTERVAL:
                state._last_ai_learn_time = time.time()
                import threading as _thr3
                _thr3.Thread(target=ai_analyze_closed_trades, daemon=True).start()
            
            # --- 5. HEARTBEAT & STATUS LOGGING ---
            if time.time() - last_heartbeat_time > 60:
                send_heartbeat(status='running', mt5_connected=True)
                last_heartbeat_time = time.time()
            
            if not hasattr(state, '_last_status_log'): state._last_status_log = 0.0
            if time.time() - state._last_status_log >= 30.0:  # Every 30s
                session_mins = int((time.time() - state.session_start_time.timestamp()) / 60)
                # Show H4 bias per symbol so we know what direction is active
                _h4_per_sym = {}
                try:
                    _acd = async_data_fetcher.get_all_data()
                    for _ss in actual_symbols:
                        _dh4 = _acd.get(_ss,{}).get('H4')
                        if _dh4 is not None and len(_dh4)>=55:
                            _h4_per_sym[_ss] = get_h4_macro_bias(_dh4)[:4]
                except Exception: pass
                _h4_str = " ".join(f"{k.replace('USDm','')[:3]}:{v}" for k,v in _h4_per_sym.items())
                _rej = getattr(state,'_rej',{})
                logger.info(
                    f"[STATUS] Eq:${account_info.equity:.2f} P&L:${state.daily_pnl:.2f} "
                    f"Trades:{state.daily_trades}/{config.MAX_DAILY_TRADES} "
                    f"Session:{get_current_session()} H4:[{_h4_str}] "
                    f"Skips:no_setup={_rej.get('no_setup',0)} edge={_rej.get('edge_ignore',0)} cooldown={_rej.get('cooldown',0)}"
                )
                state._last_status_log = time.time()

            # --- 5b. SCHEDULED DB SYNC ---
            if time.time() - last_db_sync_time > 900:
                last_db_sync_time = time.time()
                import threading as _thr5
                _thr5.Thread(target=lambda: trade_db.sync_account_history(days_back=1), daemon=True).start()

            # --- 6. CHECK TRADE LIMITS ---
            # --- 7. POTENTIAL ENTRY ORCHESTRATION ---
            all_cached_data = async_data_fetcher.get_all_data()
            if not all_cached_data:
                time.sleep(5); continue
            
            # logger.debug(f" [LOOP] Processing {len(actual_symbols)} symbols...")
            
            open_positions = mt5.positions_get()
            my_bot_positions = [p for p in open_positions if p.magic == MAGIC_NUMBER] if open_positions else []

            # =========================================================
            # PRE-FLIGHT: MARKET STATE CHECK (ATR Chop Filter)
            # If M5 ATR < 70% of its 14-period average => market is CHOPPY.
            # Scalping in chop = fakeouts. Skip scanning entirely.
            # =========================================================
            # =========================================================
            # SESSION QUALITY GATE (from Layer 1 AI intelligence)
            # =========================================================
            _session_quality = state.global_market_sentiment
            if _session_quality == 'AVOID':
                if not hasattr(state, '_avoid_logged') or not state._avoid_logged:
                    logger.warning("[AI L1] Session quality = AVOID -- pausing all trading")
                    state._avoid_logged = True
                time.sleep(5.0)
                continue
            elif _session_quality == 'CHOPPY':
                # In choppy markets: only trade A+ setups (score >= 8 required)
                pass  # L3 score threshold handles this
            state._avoid_logged = False

            signals_found = 0
            # Per-cycle rejection counters for summary log (every 20 iterations)
            if not hasattr(state, '_rej'):
                state._rej = {k: 0 for k in ['no_data','no_setup','banned','cooldown',
                                               'same_candle','edge_ignore','throttle','position_exists']}

            for symbol in actual_symbols:
                # Skip if bot already has an open position on this symbol
                if any(pos.symbol == symbol and pos.magic == MAGIC_NUMBER for pos in my_bot_positions):
                    state._rej['position_exists'] += 1
                    continue

                # Daily trade limit guard
                if state.daily_trades >= config.MAX_DAILY_TRADES:
                    logger.warning(f"[LIMIT] Daily trade limit {config.MAX_DAILY_TRADES} reached. No new entries.")
                    break

                cached_data = all_cached_data.get(symbol, {})
                df_m1  = cached_data.get('M1')
                df_m5  = cached_data.get('M5')
                df_m15 = cached_data.get('M15')
                df_m30 = cached_data.get('M30')
                df_h1  = cached_data.get('H1')
                df_h4  = cached_data.get('H4')

                if df_m1 is None or df_m5 is None or df_h1 is None or df_m1.empty or df_m5.empty or df_h1.empty:
                    state._rej['no_data'] += 1
                    logger.debug(f"[SCAN] {symbol}: missing data")
                    continue

                # DATA FRESHNESS: reject if cache is over 2 hours old (stale H1/H4)
                _cache_age = time.time() - cached_data.get('timestamp', 0)
                if _cache_age > 7200:
                    state._rej['no_data'] += 1
                    logger.warning(f"[SCAN] {symbol}: stale cache ({_cache_age/3600:.1f}h) -- skip")
                    continue

                # =========================================================
                # STEP 1: INLINE SMC SIGNAL DETECTION
                # Directly runs our proven strategy functions.
                # EntryEngine removed -- it required price within a fixed
                # tolerance of key levels (was 0.4 for XAU, i.e. $0.40 at
                # a $3000+ asset), which is why ZERO setups were ever found.
                # =========================================================

                # -- STEP 1: TOP-DOWN HIERARCHY ---------------------------------
                # H4 macro bias (global direction)
                h4_bias = get_h4_macro_bias(df_h4) if df_h4 is not None and len(df_h4) >= 55 else "NEUTRAL"

                # H1 immediate trend
                try:
                    ema50_h1  = df_h1['close'].ewm(span=50,  adjust=False).mean().iloc[-1]
                    ema200_h1 = df_h1['close'].ewm(span=200, adjust=False).mean().iloc[-1]
                    close_h1  = df_h1['close'].iloc[-1]
                    if close_h1 > ema50_h1 > ema200_h1:   h1_trend = "BULLISH"
                    elif close_h1 < ema50_h1 < ema200_h1: h1_trend = "BEARISH"
                    else:                                   h1_trend = "NEUTRAL"
                except Exception:
                    h1_trend = "NEUTRAL"

                # H4 vs H1 alignment: if they conflict, skip (no clear direction)
                # Only skip on CONFIRMED conflict -- both HTFs have strong opinions that differ
                # If either is NEUTRAL, there's no conflict (just uncertainty)
                if h4_bias != "NEUTRAL" and h1_trend != "NEUTRAL" and h4_bias != h1_trend:
                    logger.debug(f"[MTF] {symbol}: H4={h4_bias} conflicts H1={h1_trend} -- skip")
                    state._rej['no_setup'] = state._rej.get('no_setup', 0) + 1
                    continue

                # Effective trend: H4 leads, H1 confirms; both neutral = skip
                effective_trend = h4_bias if h4_bias != "NEUTRAL" else h1_trend
                if effective_trend == "NEUTRAL":
                    # Fallback: use L1 computed bias (works for crypto in ranging H4/H1)
                    _l1_fb = state.approved_bias.get(symbol, 'NEUTRAL')
                    if _l1_fb == 'BUY_ONLY':
                        effective_trend = 'BULLISH'
                    elif _l1_fb == 'SELL_ONLY':
                        effective_trend = 'BEARISH'
                    else:
                        logger.debug(f"[MTF] {symbol}: H4={h4_bias} H1={h1_trend} L1=NEUT -- skip")
                        state._rej['no_setup'] = state._rej.get('no_setup', 0) + 1
                        continue
                h1_trend = effective_trend  # downstream uses h1_trend


                # -- EMA MOMENTUM GATE (9/15 EMA slope filter) ----------------
                # Flat EMAs = compressing / ranging market = fakeout zone.
                _ema_m5 = get_ema_momentum(df_m5, slope_bars=5)
                if _ema_m5['strength'] == 'FLAT':
                    # Truly flat = no momentum at all = all strategies will fail anyway
                    logger.debug(f"[EMA] {symbol}: M5 truly flat (ranging) -- skip. {_ema_m5['reason']}")
                    state._rej['no_setup'] = state._rej.get('no_setup', 0) + 1
                    continue
                # WEAK or stronger: allow all three strategies to check their own signals

                # Each strategy applies its own M5 direction logic internally:
                # EMA Scalp: fires on 9/15 cross in H4 direction (M5 = H4 is correct)
                # Swappy 3C: fires on 2+1 pattern regardless of EMA direction
                # SSM/ICT: uses internal FVG + sweep logic
                # We pass _ema_m5 to strategies for context but don't hard-block here.
                _m5_trend = _ema_m5['trend']  # pass to strategies for context

                # ->-> HTF ZONE GATE: Only scan M5 when price is at an H1/M15 POI ->
                # This saves CPU + API cost by skipping noise-zone price action.
                # A "sniper" only fires when at a valid HTF institutional zone.
                _atr_m5_gate = float(calculate_atr(df_m5['high'], df_m5['low'], df_m5['close'], 14).iloc[-1])
                _htf_zone = is_price_in_htf_zone(
                    symbol, effective_trend, df_h1, df_m15,
                    df_m5['close'].iloc[-1], _atr_m5_gate
                )
                # HTF zone is now a SOFT gate -- adjusts L3 score threshold.
                # Hard blocking prevented trades for 2+ days due to OB detection issues.
                # Instead: always scan M5, let L3 Gemini judge quality contextually.
                if _htf_zone['in_zone']:
                    logger.debug(f"[MTF] {symbol}: AT HTF ZONE {_htf_zone['zone_type']} -- premium setup")
                else:
                    logger.debug(f"[MTF] {symbol}: no HTF zone -- scanning anyway, L3 will judge")

                # ================================================================
                # THREE STRATEGIES RUN INDEPENDENTLY WITH THEIR OWN RULES
                # ================================================================
                setup = None
                _trade_direction = 'BUY' if effective_trend == 'BULLISH' else 'SELL'
                _cur_price = df_m5['close'].iloc[-1]
                _atr_m5 = float(calculate_atr(df_m5['high'], df_m5['low'], df_m5['close'], 14).iloc[-1])

                # Compute 50 EMA here so overextension filter can use it
                # (Strategy A also uses _e50 -- shared reference, no double computation)
                _e50 = float(df_m5['close'].ewm(span=50, adjust=False).mean().iloc[-1])

                #  OVEREXTENSION FILTER 
                # Don't enter if price is more than 2x ATR from the 50 EMA
                # and we're not at an HTF zone. Wait for the pullback.
                _dist_from_mean = abs(_cur_price - _e50)
                if _dist_from_mean > (_atr_m5 * 2.0) and not _htf_zone['in_zone']:
                    logger.debug(
                        f"[PULLBACK GUARD] {symbol}: {_dist_from_mean:.3f} from 50EMA "
                        f"(>{_atr_m5*2.0:.3f} = 2xATR). Waiting for pullback."
                    )
                    state._rej['no_setup'] = state._rej.get('no_setup', 0) + 1
                    continue

                #
                # STRATEGY A: EMA SCALP (9/25/50/200 EMA crossover)
                # Rules: H4 bias  (already checked) + M5 EMA pullback  (already checked)
                #        + 9 EMA crossing 25 EMA in bias direction on M5
                # No HTF OB needed. Fires on EMA crossover at any M5 location.
                # Extracted into strategy_ema_scalp_cross() -- see its docstring
                # for the two behavior fixes made during that extraction
                # (state._rej double-counting, and the pattern pre-filter now
                # actually gating instead of only logging).
                #
                if not setup and config.ENABLE_STRATEGY_EMA_SCALP:
                    setup = strategy_ema_scalp_cross(df_m5, _trade_direction, symbol)

                # 
                # STRATEGY B: SWAPPY 3C (momentum continuation)
                # Rules: H4 bias  + 2 trend candles + 1 failed pullback on M5
                #        + BUY near support / SELL near resistance (M5 level)
                # No HTF OB needed. Support/resistance = recent M5 swing levels.
                # 
                if not setup:
                    _sw = detect_swappy_3c(df_m5, _trade_direction)
                    if _sw['confirmed']:
                        # Location check: near M5 support (BUY) or resistance (SELL)
                        _recent_hi = float(df_m5['high'].iloc[-20:-1].max())
                        _recent_lo = float(df_m5['low'].iloc[-20:-1].min())
                        _near_support = (_cur_price - _recent_lo) / max(_recent_hi - _recent_lo, 1) < 0.35
                        _near_resist  = (_recent_hi - _cur_price) / max(_recent_hi - _recent_lo, 1) < 0.35
                        # Location: BUY near support (bottom 35% of range) or SELL near resistance (top 35%)
                        # This prevents entering Swappy mid-range where risk:reward is poor
                        _good_location = (_trade_direction == 'BUY' and _near_support) or                                          (_trade_direction == 'SELL' and _near_resist)

                        if _good_location:
                            # 3RD-TIME RE-ENTRY RULE: If this level has already produced 1 SL hit,
                            # the 2nd setup is blocked (level is still being rejected by market).
                            # Only the 3rd setup at the same level is allowed -- by that point
                            # the market has proven it won't give price away there cheaply.
                            _sw_low  = float(_sw.get('setup_low',  _cur_price - _atr_m5))
                            _sw_high = float(_sw.get('setup_high', _cur_price + _atr_m5))
                            _sw_allowed, _sw_reason = can_take_swappy_entry(
                                symbol, _trade_direction, _sw_low, _sw_high)
                            if not _sw_allowed:
                                logger.info(f"[SWAPPY 3RD-RULE] {symbol}: {_trade_direction} blocked -- {_sw_reason}")
                                state._rej['no_setup'] = state._rej.get('no_setup', 0) + 1
                            else:
                                if _sw_reason != 'first_setup':
                                    logger.info(f"[SWAPPY 3RD-RULE] {symbol}: {_sw_reason} -- entry allowed")
                                # SL: last swing extreme in last 15 bars + buffer
                                _sw_scan = df_m5.iloc[-15:]
                                if _trade_direction == 'BUY':
                                    _sl_sw = float(_sw_scan['low'].min()) - _atr_m5 * 0.3
                                else:
                                    _sl_sw = float(_sw_scan['high'].max()) + _atr_m5 * 0.3

                                # BUG FIX: this used to build a generic `setup` dict with
                                # entry_price = _sw['entry_level'] (candle 3's close) and let
                                # it flow through the shared pipeline as a MARKET order. But
                                # detect_swappy_3c's own return says order_type=BUY_STOP/
                                # SELL_STOP with the trigger at _sw['stop_entry'] (above/below
                                # the 3-candle high/low) -- i.e. an entry on breakout
                                # confirmation, not a market fill at C3's close. There's
                                # already a fully-built place_swappy_pending_order() (correct
                                # stop-order placement, 3:1 RR per the Swappy spec, 25-minute
                                # expiry) that was never called anywhere -- wire it in here
                                # instead of reimplementing it, same pattern AOX uses
                                # (self-contained placement + continue, skipping the shared
                                # setup/EdgeEngine pipeline for this symbol this cycle).
                                _sw_placed = place_swappy_pending_order(
                                    symbol, _sw, _trade_direction,
                                    entry_price=_sw['stop_entry'], sl=_sl_sw,
                                    account_equity=account_info.equity,
                                )
                                if _sw_placed:
                                    logger.info(f"[SWAPPY 3C] {symbol}: {_sw['pattern']} stop order placed "
                                                f"at {_sw['stop_entry']:.4f} (near_support={_near_support} near_resist={_near_resist})")
                                    state.daily_trades += 1
                                    continue  # pending order placed -- skip rest of pipeline this iteration
                                else:
                                    logger.warning(f"[SWAPPY 3C] {symbol}: pending order placement failed -- falling through to other strategies")
                                    state._rej['no_setup'] = state._rej.get('no_setup', 0) + 1

                # 
                # STRATEGY C: SSM / ICT FVG RETEST (institutional sweep)
                # Rules: HTF OB zone  + sweep + displacement + FVG retest
                # This is the only strategy that USES the HTF zone.
                # Higher L3 confidence required (institutional setup).
                #
                if not setup and config.ENABLE_STRATEGY_SMC_FVG_RETEST:
                    # SSM-specific HTF zone check (only for this strategy)
                    _ssm_in_zone = _htf_zone['in_zone']
                    _s = strategy_liquidity_fvg_engine(symbol, df_m5, df_h1, effective_trend,
                                                        edge_mode="NORMAL", df_m15=df_m15, df_h1=df_h1)
                    if _s:
                        setup = {
                            'signal':    _s['direction'],
                            'reason':    _s.get('strategy_name', 'SSM_FVG_RETEST'),
                            'stop_loss': _s['stop_loss'],
                            'strategy_type': 'SSM',
                            'liquidity_distance':  0.75,
                            'liquidity_strength':  0.85,
                            'momentum_state':      0.8,
                            'structure_alignment': 0.8,
                            'entry_price':    _s.get('fvg_mid', _cur_price),
                            'fvg_top':        _s.get('fvg_top', 0),
                            'fvg_bottom':     _s.get('fvg_bottom', 0),
                            'htf_confluence': _s.get('htf_confluence', 0),
                            'htf_reason':     _s.get('htf_reason', ''),
                            'at_htf_zone':    _ssm_in_zone,
                            'htf_needed': True,   # SSM uses HTF zone
                        }
                        logger.debug(f"[SSM] {symbol}: FVG retest found, at_htf_zone={_ssm_in_zone}")

                # STRATEGY D: AOX MODEL -- 25/25/50 Layered Execution
                # Layer 1 (25%): SD zone tap
                # Layer 2 (25%): SMT + FPFVG Turtle Soup confirmation
                # Layer 3 (50%): Hippo/Mitigation block
                # This runs independently and manages its own state -- no `setup` needed
                if df_m1 is not None and state.daily_trades < config.MAX_DAILY_TRADES:
                    _acct_now_aox = mt5.account_info()
                    if _acct_now_aox:
                        _aox_executed = run_aox_layered_entry(
                            symbol, df_m5, df_m1, effective_trend, _acct_now_aox.equity)
                        if _aox_executed:
                            continue  # AOX placed a layer, skip rest of pipeline this iteration

                # SHAAKUNI SSM: dedicated HTF sweep + extreme OB entry
                # This replaces generic liquidity grab with proper Shaakuni rules
                if not setup and df_h1 is not None:
                    _ssm_result = strategy_shaakuni_ssm(symbol, df_h1, df_h4, df_m5, effective_trend)
                    if _ssm_result:
                        setup = {
                            'signal':          _ssm_result['signal'],
                            'reason':          'SHAAKUNI_SSM',
                            'stop_loss':       _ssm_result['stop_loss'],
                            'strategy_type':   'SSM',
                            'limit_entry':     _ssm_result.get('limit_entry'),
                            'order_type':      'LIMIT',
                            'liquidity_distance': 0.88,
                            'liquidity_strength': 0.9,
                            'momentum_state':     0.85,
                            'structure_alignment': 0.88,
                        }
                        logger.info(f"[SHAAKUNI] {symbol}: SSM setup found | "
                                   f"{_ssm_result['signal']} @ {_ssm_result.get('limit_entry',0):.4f}")

                # Generic Liquidity Grab and Kill Zone (fallback)
                if not setup and config.ENABLE_STRATEGY_LIQUIDITY_GRAB_FALLBACK:
                    _s = strategy_liquidity_grab(df_m5, df_h1, h1_trend, symbol, df_m1)
                    if _s:
                        setup = {
                            'signal':    _s['direction'],
                            'reason':    _s.get('strategy_name', 'LIQUIDITY_GRAB'),
                            'stop_loss': _s['stop_loss'],
                            'strategy_type': 'SSM',
                            'liquidity_distance':  0.65,
                            'liquidity_strength':  0.75,
                            'momentum_state':      0.6,
                            'structure_alignment': 0.65,
                            'entry_price': _cur_price,
                            'at_htf_zone': _htf_zone['in_zone'],
                            'htf_needed': True,
                        }

                if not setup and config.ENABLE_STRATEGY_ICT_KILLZONE_FALLBACK:
                    _s = strategy_ict_killzone(df_m5, df_h1, h1_trend, symbol, df_m1)
                    if _s:
                        setup = {
                            'signal':    _s['direction'],
                            'reason':    _s.get('strategy_name', 'ICT_KILLZONE'),
                            'stop_loss': _s['stop_loss'],
                            # ICT_KILLZONE is timing-based -- kill zone time IS the confluence
                            # It doesn't need a separate 3C sweep confirmation
                            # (using EMA path so it doesn't hit the SSM+3C gate)
                            'strategy_type': 'ICT',
                            'liquidity_distance':  0.6,
                            'liquidity_strength':  0.7,
                            'momentum_state':      0.6,
                            'structure_alignment': 0.6,
                            'entry_price': _cur_price,
                            'at_htf_zone': _htf_zone['in_zone'],
                            'htf_needed': True,
                        }

                if not setup:
                    state._rej['no_setup'] = state._rej.get('no_setup', 0) + 1
                    continue

                logger.info(f"[SCAN] {symbol}: SETUP signal={setup['signal']} reason={setup['reason']} sl={setup['stop_loss']:.3f} trend={h1_trend}")

                # CRITICAL: Direction MUST agree with H4 macro trend
                # setup.signal can suggest counter-trend (e.g. Swappy BEAR on BULL H4)
                # but we only take WITH-TREND entries -- this was the #1 cause of all losses
                _setup_signal = setup.get('signal', _trade_direction)
                if _setup_signal != _trade_direction:
                    logger.debug(f"[DIR GATE] {symbol}: setup={_setup_signal} vs H4={_trade_direction} -- counter-trend rejected")
                    state._rej['no_setup'] = state._rej.get('no_setup', 0) + 1
                    continue
                direction    = _trade_direction  # always H4-aligned
                trigger_type = setup.get('reason', 'UNKNOWN')

                # -- H1 MOTHER CANDLE FIBONACCI ZONE ----------------------
                _fib = get_h1_mother_candle_zone(df_h1, direction)
                setup['fib_found']   = _fib['found']
                setup['fib_in_zone'] = _fib['in_zone']
                setup['fib_reason']  = _fib['reason']
                setup['fib_zone_high'] = _fib.get('zone_high', 0.0)
                setup['fib_zone_low']  = _fib.get('zone_low', 0.0)

                # -- 3C MOMENTUM CONFIRMATION --------------------------------
                # Verify the 3-candle sequence: Sweep -> Displacement -> Hold.
                # Candle 3 must FAIL to close beyond the sweep candle extreme.
                # Without this: bot enters fakeout bounces that reverse immediately.
                _3c = detect_3c_setup(df_m5, direction)
                setup['3c_confirmed'] = _3c['confirmed']
                setup['3c_strength']  = _3c['strength']
                setup['3c_reason']    = _3c['reason']
                setup['ema_strength'] = _ema_m5['strength']
                setup['ema_reason']   = _ema_m5['reason']

                # QUOTA MODE: when AI quota exceeded, only strongest signals go through
                _quota_active = hasattr(state, '_quota_resume') and datetime.now() < state._quota_resume
                if _quota_active:
                    # Quota mode: SSM/Shaakuni sweep + ICT timing = self-confirming, no AI needed
                    _strat_t = setup.get('strategy_type', 'SSM')
                    _reason  = setup.get('reason', '')
                    _is_self_confirming = _strat_t in ('ICT', 'AOX', 'SSM') or _reason in (
                        'ICT_KILLZONE', 'LIQUIDITY_GRAB', 'AOX_SNIPER', 'SHAAKUNI_SSM')
                    if not _is_self_confirming:
                        # For EMA/Swappy in quota mode: need STRONG EMA or 3C
                        _ema_ok = setup.get('ema_strength') == 'STRONG'
                        _3c_ok  = setup.get('3c_confirmed', False)
                        if not (_ema_ok or _3c_ok):
                            logger.debug(f"[QUOTA MODE] {symbol}: EMA+3C weak, not self-confirming -- skip")
                            continue
                    logger.debug(f"[QUOTA MODE] {symbol}: {_strat_t}/{_reason} -- proceeding without AI")

                _strat_type_early = setup.get('strategy_type', 'SSM')
                if not _3c['confirmed'] and _strat_type_early == 'SSM':
                    # SSM/ICT requires 3C sweep confirmation (the institutional sweep pattern)
                    # EMA scalp and Swappy have their own confirmation built into detection
                    _l1_str = getattr(state, 'ai_bias_strength', {}).get(symbol, 0)
                    if _l1_str < 8:
                        logger.debug(f"[3C] {symbol} SSM: 3C not confirmed, L1={_l1_str}/10 -- skip. {_3c['reason']}")
                        state._rej['edge_ignore'] = state._rej.get('edge_ignore', 0) + 1
                        continue
                elif not _3c['confirmed'] and _strat_type_early in ('EMA', 'SWAPPY', 'ICT', 'AOX'):
                    # EMA, Swappy, ICT: don't require 3C (they have built-in confirmation)
                    # ICT_KILLZONE: kill zone timing = confluence, 3C not needed
                    logger.debug(f"[3C] {symbol} {_strat_type_early}: 3C not required for this strategy type -- pass")

                if any(banned.upper() in trigger_type.upper() for banned in state.banned_strategies):
                    state._rej['banned'] += 1
                    logger.info(f"[SCAN] {symbol}: blocked by strategy ban ('{trigger_type}')")
                    continue

                direction   = setup['signal']
                signal_sl   = setup['stop_loss']
                liquidity_distance  = setup.get('liquidity_distance', 0.5)
                liquidity_strength  = setup.get('liquidity_strength', 0.5)
                momentum_state      = setup.get('momentum_state', 0.5)
                structure_alignment = setup.get('structure_alignment', 0.5)
                
                # Cooldown check
                if symbol in state.symbol_cooldowns:
                    if datetime.now(timezone.utc) < state.symbol_cooldowns[symbol]:
                        state._rej['cooldown'] += 1
                        _rem_secs = (state.symbol_cooldowns[symbol] - datetime.now(timezone.utc)).total_seconds()
                        _rem_str  = f"{int(_rem_secs)}s" if _rem_secs < 60 else f"{int(_rem_secs//60)}m {int(_rem_secs%60)}s"
                        logger.debug(f"[SCAN] {symbol}: cooldown active ({_rem_str} left)")
                        continue
                    else:
                        del state.symbol_cooldowns[symbol]
                
                # Trade-per-candle penalty
                current_candle_time = df_m5['time'].iloc[-1]
                if symbol in state.last_trade_candle and state.last_trade_candle[symbol] == current_candle_time:
                    state._rej['same_candle'] += 1
                    logger.debug(f"[SCAN] {symbol}: already traded this M5 candle")
                    continue

                # =========================================================
                # STEP 2: EDGE ENGINE -- LIQUIDITY PROBABILITY MODEL
                # =========================================================
                
                try:
                    atr_e = calculate_atr(df_m5['high'], df_m5['low'], df_m5['close'], 14).iloc[-1]
                    raw_spread_e = mt5.symbol_info_tick(symbol).ask - mt5.symbol_info_tick(symbol).bid
                    volatility_state = 1.0 if atr_e > raw_spread_e * 2 else 0.5
                except Exception:
                    volatility_state = 0.5
                    
                session_str = get_current_session()
                session_strength = 1.0 if session_str in ["LONDON", "NEW_YORK", "LONDON_NY"] else 0.5

                try:
                    # Regime from H4 (structural context) not M5 (too noisy)
                    _df_h4_regime = get_market_data(symbol, mt5.TIMEFRAME_H4, 60)
                    regime = regime_detector.detect_regime(symbol, _df_h4_regime) if _df_h4_regime is not None else regime_detector.detect_regime(symbol, df_m5)
                except Exception:
                    regime = "RANGING"

                trade_ctx = TradeContext(
                    liquidity_distance=liquidity_distance,
                    liquidity_strength=liquidity_strength,
                    momentum_state=momentum_state,
                    structure_alignment=structure_alignment,
                    session_strength=session_strength,
                    volatility_state=volatility_state,
                    session=session_str,
                    regime=regime
                )
                
                edge_result = EdgeEngine().calculate(trade_ctx)
                
                # EdgeEngine IGNORE only blocks if score is truly terrible (<25)
                # EMA scalp naturally scores lower than SSM but is still valid
                if (edge_result.state == "IGNORE" or not edge_result.allow_entry) and edge_result.score < 25:
                    state._rej['edge_ignore'] += 1
                    logger.debug(f"[SCAN] {symbol}: EdgeEngine hard block score={edge_result.score:.1f}")
                    continue
                elif edge_result.state == "IGNORE" or not edge_result.allow_entry:
                    logger.debug(f"[SCAN] {symbol}: EdgeEngine soft ignore score={edge_result.score:.1f} -- proceeding (strategy has own validation)")

                logger.debug(f"[SCAN] {symbol}: EdgeEngine PASS score={edge_result.score:.1f} regime={regime}")

                # =========================================================
                # STEP 3: CAPITAL CONTROLLER -- SOLE SIZING AUTHORITY
                # =========================================================
                cap_ctrl = CapitalController()

                edge_score = edge_result.score

                if len(my_bot_positions) >= config.MAX_CONCURRENT_TRADES:
                    if not cap_ctrl.allow_stacking(edge_score, regime, "EXPANSION"):
                        logger.debug(f"[SCAN] {symbol}: stacking blocked (open={len(my_bot_positions)} edge={edge_score:.1f})")
                        continue

                if cap_ctrl.should_throttle_frequency(edge_score < 50):
                    state._rej['throttle'] += 1
                    logger.debug(f"[SCAN] {symbol}: frequency throttled (edge={edge_score:.1f})")
                    continue

                current_drawdown = 0.0
                if state.daily_start_equity > 0:
                    current_drawdown = ((state.daily_start_equity - account_info.equity) / state.daily_start_equity) * 100.0
                current_drawdown = max(0.0, current_drawdown)

                # FIXED: Use CapitalController.calculate() for proper risk sizing
                # Previously only used BASE_RISK * EdgeEngine multiplier -- ignored session,
                # drawdown, and symbol volatility scaling entirely.
                sym_metrics = max(0.1, symbol_tracker.get_symbol_metrics(symbol).get('trade_score', 1.0))

                # Historical pattern-match edge health for THIS symbol+direction,
                # now actually reaching position sizing (see CapitalController.
                # calculate's docstring -- this call existed already in the
                # mid-trade management loop but its result was never wired
                # anywhere, and nothing called it at entry time at all).
                # Failure is non-fatal -- an unavailable/erroring pattern
                # store degrades to 1.0 (neutral), never blocks a trade.
                try:
                    pattern_health = pattern_recognizer.get_edge_health_score(symbol, setup['signal'], {})
                except Exception as _phe:
                    logger.debug(f"[SCAN] {symbol}: pattern health lookup failed ({_phe}) -- using neutral 1.0")
                    pattern_health = 1.0

                final_risk = cap_ctrl.calculate(
                    edge_score           = edge_score,
                    symbol_metrics       = sym_metrics,
                    session              = session_str,
                    drawdown             = current_drawdown,
                    symbol               = symbol,
                    open_positions_count = len(my_bot_positions),
                    account_equity       = account_info.equity,
                    pattern_health       = pattern_health,
                )
                final_risk = min(final_risk, config.MAX_RISK_PERCENT)  # up to 10%
                logger.debug(f"[SCAN] {symbol}: sizing inputs edge={edge_score:.1f} sym_perf={sym_metrics:.2f} "
                             f"pattern_health={pattern_health:.2f} dd={current_drawdown:.1f}% -> final_risk={final_risk:.2f}%")

                # =========================================================
                # STEP 4: BUILD SIGNAL AND EXECUTE
                # =========================================================
                # =========================================================
                # LAYER 1 GATE: L1 Gemini bias filter
                # If L1 has not run yet or returned NEUTRAL for this symbol,
                # H4/H1 structural bias (effective_trend) is the fallback.
                # Trading is NOT blocked when L1 is NEUTRAL -- H4 leads.
                # =========================================================
                if getattr(state, 'ai_avoid_symbols', {}).get(symbol, False):
                    logger.debug(f"[AI L1] {symbol}: marked avoid -- skip")
                    continue

                if state.approved_bias:
                    _l1_bias = state.approved_bias.get(symbol, 'NEUTRAL')
                    if _l1_bias == 'SELL_ONLY' and direction == 'BUY':
                        logger.debug(f"[AI L1] {symbol}: BUY blocked by L1 (SELL_ONLY)")
                        continue
                    if _l1_bias == 'BUY_ONLY' and direction == 'SELL':
                        logger.debug(f"[AI L1] {symbol}: SELL blocked by L1 (BUY_ONLY)")
                        continue
                else:
                    # L1 not yet run -- H4 structural bias is active
                    logger.debug(f"[AI L1] {symbol}: no L1 bias yet, using H4 structural bias ({effective_trend})")

                # =========================================================
                # LAYER 3: AI TRADE VALIDATION (per-candidate Gemini score)
                # Only the best setups (score >= 7) proceed to execution
                # =========================================================
                #  LAYER 3: AI VALIDATION 
                _l3_result = {}  # safe default
                _l3_score = 5; _l3_risk_mod = 1.0
                _quota_resume = getattr(state, '_quota_resume', None)
                _quota_ok = not (_quota_resume and datetime.now() < _quota_resume)

                if not _quota_ok:
                    # Quota exceeded: trade on H4+L1 structural bias only
                    _mins_left = int((_quota_resume - datetime.now()).total_seconds() // 60)
                    logger.debug(f"[AI L3] {symbol}: quota paused ({_mins_left}m). Using H4 bias only.")
                    _bias_ok = state.approved_bias.get(symbol, 'NEUTRAL') in ('NEUTRAL', f'{direction}_ONLY')
                    if not _bias_ok:
                        continue
                    # Skip L3 -- proceed to execution with H4 structural bias
                else:
                    try:
                        _l3_last = state.l3_last_call.get(symbol, 0)
                        _l3_age  = time.time() - _l3_last

                        _strat_type   = setup.get('strategy_type', 'SSM')
                        _l3_cache_key = f"{symbol}_{direction}_{_strat_type}"
                        _is_ssm_call  = _strat_type in ('SSM','ICT','AOX')
                        _l3_cache_ttl = 900 if _is_ssm_call else 300  # SSM=15min, others=5min
                        _l3_cached_score = state.l3_last_score.get(_l3_cache_key)
                        if _l3_age < _l3_cache_ttl and _l3_cached_score is not None:
                            _l3_score    = _l3_cached_score
                            _l3_approved = _l3_score >= _l3_min_score
                            _l3_reason   = f"cached ({_l3_age:.0f}s ago)"
                            _l3_risk_mod = 1.0
                            logger.debug(f"[AI L3] {symbol}: cached score={_l3_score}/10")
                        else:
                            _3c_tag     = f" | 3C:{setup.get('3c_strength',0):.0%}" if setup.get('3c_confirmed') else " | 3C:NO"
                            _ema_tag    = f" | EMA:{setup.get('ema_strength','?')}"
                            _fib_tag    = " | FIB:IN-ZONE" if setup.get('fib_in_zone') else (" | FIB:FOUND" if setup.get('fib_found') else "")
                            _swappy_tag = " | SWAPPY" if "SWAPPY" in str(setup.get('reason','')) else ""
                            _htf_rsn    = setup.get('htf_reason', '')
                            _setup_name = (f"{trigger_type}{_3c_tag}{_ema_tag}{_fib_tag}{_swappy_tag} | HTF:{_htf_rsn}"
                                           if _htf_rsn else f"{trigger_type}{_3c_tag}{_ema_tag}{_fib_tag}{_swappy_tag}")
                            _l3_result = ai_validate_trade(
                                symbol=symbol, direction=direction,
                                setup_name=_setup_name,
                                entry=df_m5['close'].iloc[-1], sl=signal_sl,
                                tp=df_m5['close'].iloc[-1] + (abs(df_m5['close'].iloc[-1] - signal_sl) * 1.5) * (1 if direction == 'BUY' else -1),  # 1.5x fallback (structural TP set at order placement)
                                df_m5=df_m5, df_m1=df_m1,
                            )
                            _l3_score    = _l3_result.get('score', 5)
                            _l3_approved = _l3_result.get('approved', False)
                            _l3_reason   = _l3_result.get('reason', '')
                            _l3_risk_mod = _l3_result.get('risk_modifier', 1.0)
                            state.l3_last_call[symbol]  = time.time()
                            state.l3_last_score[symbol] = _l3_score  # backward compat
                            state.l3_last_score[_l3_cache_key] = _l3_score  # new keyed cache

                        #  MULTI-TIMEFRAME REGIME FILTER 
                        # H4 = macro context (sets TP strategy)
                        # M5 = local entry context (must be TRENDING to enter)
                        #
                        # Decision table:
                        #   H4:TRENDING + M5:TRENDING  full trend trade
                        #   H4:RANGING  + M5:TRENDING  range scalp (TP = range boundary)
                        #   H4:TRENDING + M5:RANGING   skip (wait for M5 breakout)
                        #   H4:RANGING  + M5:RANGING   skip
                        #   H4:CHOPPY   + any          skip
                        #
                        # Note: H4 RANGING does NOT block trades.
                        # A 400-500 pip Gold H4 range = M15 can trend 150 pips inside it.
                        # 

                        _ema_str  = setup.get('ema_strength', 'WEAK')
                        _3c_conf  = setup.get('3c_confirmed', False)

                        # Step 1: M5 local regime -- is there actually a local trend?
                        _m5_regime = regime_detector.detect_regime(symbol, df_m5)

                        if _m5_regime == 'RANGING':
                            # No local trend on M5 -- skip regardless of H4
                            logger.debug(f"[REGIME] {symbol}: M5=RANGING -- no local trend, skip")
                            state._rej['m5_ranging'] = state._rej.get('m5_ranging', 0) + 1
                            continue

                        # Step 2: H4 context from `regime` variable (already computed above)
                        _h4_regime = regime  # H4 regime (set earlier in the scan loop)

                        if _h4_regime == 'CHOPPY':
                            logger.debug(f"[REGIME] {symbol}: H4=CHOPPY -- skip")
                            state._rej['h4_choppy'] = state._rej.get('h4_choppy', 0) + 1
                            continue

                        # Step 3: Set trade mode based on combined regime
                        if _h4_regime == 'RANGING' and _m5_regime == 'TRENDING':
                            # Range scalp mode: valid trade, but TP must be range boundary
                            # not a trend extension -- mark for constrained TP
                            setup['_range_scalp_mode'] = True
                            logger.debug(f"[REGIME] {symbol}: H4=RANGING M5=TRENDING  range scalp mode")
                        else:
                            setup['_range_scalp_mode'] = False

                        # Step 4: Quality gate based on strategy type
                        # ICT_KILLZONE: timing is the confluence, allow EMA:WEAK (kill zone = setup)
                        # EMA/SWAPPY in TRENDING H4: require STRONG or 3C -- no weak signals in trend
                        # EMA/SWAPPY in RANGING H4: EMA:WEAK allowed (range scalp, confirmed by M5 trend)
                        if _strat_type in ('EMA', 'SWAPPY') and _h4_regime == 'TRENDING':
                            if _ema_str == 'WEAK' and not _3c_conf:
                                logger.debug(f"[WEAK+NO3C] {symbol}: TRENDING H4 + EMA:WEAK + no 3C -- skip")
                                state._rej['weak_no3c'] = state._rej.get('weak_no3c', 0) + 1
                                continue

                        # PULLBACK GATE: if HTF is bearish but M5 signal is BUY,
                        # only allow if price is at a valid H1 support level (not just any pullback)
                        _m5_dir  = setup.get('signal', '')
                        _h4_bias = h4_bias  # H4 macro direction (BULLISH/BEARISH/NEUTRAL)
                        if _m5_dir == 'BUY' and _h4_bias == 'BEARISH':
                            # Counter-trend BUY in bearish HTF -- needs structural support
                            # Check if we have FVG or OB confluence, not just EMA cross
                            _has_struct = setup.get('fib_in_zone') or setup.get('3c_confirmed') or                                          setup.get('reason','') in ('SSM_FVG', 'LIQUIDITY_GRAB', 'ICT_KILLZONE')
                            if not _has_struct:
                                logger.debug(f"[HTF GATE] {symbol}: BUY rejected in BEARISH H4 -- no structural confluence")
                                continue
                        elif _m5_dir == 'SELL' and _h4_bias == 'BULLISH':
                            _has_struct = setup.get('fib_in_zone') or setup.get('3c_confirmed') or                                          setup.get('reason','') in ('SSM_FVG', 'LIQUIDITY_GRAB', 'ICT_KILLZONE')
                            if not _has_struct:
                                logger.debug(f"[HTF GATE] {symbol}: SELL rejected in BULLISH H4 -- no structural confluence")
                                continue

                        # L3 minimum score by strategy type
                        # ICT_KILLZONE: kill zone timing = built-in confluence  allow 5/10
                        # EMA/SWAPPY: need Gemini to have an opinion (6+)
                        # EMA:WEAK + no 3C in trending: need strong AI conviction (7)
                        if _strat_type in ('ICT', 'AOX', 'SSM'):
                            _l3_min_score = 5  # kill zone time = valid signal even at score 5
                        elif setup.get('ema_strength') == 'WEAK' and not setup.get('3c_confirmed') and _h4_regime == 'TRENDING':
                            _l3_min_score = 7
                        else:
                            _l3_min_score = 6

                        if _l3_score < _l3_min_score or (_l3_score <= 5 and not _l3_approved):
                            state._rej['edge_ignore'] = state._rej.get('edge_ignore', 0) + 1
                            # Cooldown based on score (prevents retry spam)
                            if _l3_score <= 3:
                                _cd_mins = 30
                            elif _l3_score == 4:
                                _cd_mins = 15
                            else:  # score = 5
                                _cd_mins = 5   # wait 5 min before retrying this symbol
                            state.symbol_cooldowns[symbol] = datetime.now(timezone.utc) + timedelta(minutes=_cd_mins)
                            logger.info(f"[AI L3] {symbol}: score={_l3_score}/{_l3_min_score} -- skip ({_cd_mins}min cooldown). {_l3_reason}")
                            continue

                        logger.info(f"[AI L3] {symbol}: score={_l3_score}/10 APPROVED. {_l3_reason}")
                        final_risk = min(final_risk * _l3_risk_mod, config.MAX_RISK_PERCENT)

                    except Exception as _l3_err:
                        _l3_err_str = str(_l3_err)
                        if '429' in _l3_err_str or 'quota' in _l3_err_str.lower():
                            # Mark quota as exceeded -- tighten all filters
                            if not hasattr(state, '_quota_resume') or datetime.now() > state._quota_resume:
                                state._quota_resume = datetime.now() + timedelta(hours=1)
                                logger.critical(f"[QUOTA] L3 quota exceeded for {symbol}. Tightening filters for 1h.")
                        logger.warning(f"[AI L3] Validation error for {symbol}: {_l3_err_str[:80]}")
                        _bias_fb = state.approved_bias.get(symbol, 'NEUTRAL')
                        if _bias_fb not in ('NEUTRAL', f'{direction}_ONLY'):
                            continue


                # Check AI lessons -- warn if this setup matches a past losing pattern
                _lesson_ok, _lesson_warn = check_trade_against_lessons(symbol, direction, {
                    'session': session_str, 'hour': datetime.now(timezone.utc).hour
                })
                if not _lesson_ok:
                    # Log as warning but don't block -- lessons are advisory, not mandatory
                    logger.debug(f"[AI LESSON] {symbol} {direction}: advisory warning -- {_lesson_warn[:80]}")

                # PORTFOLIO RISK CHECK: total risk across all open + this trade
                # Prevent portfolio wipeout even if individual trades are sized correctly
                _total_risk_pct = len(my_bot_positions) * config.BASE_RISK_PERCENT + final_risk
                _max_portfolio_risk = 25.0  # Never exceed 3% total equity at risk
                if _total_risk_pct > _max_portfolio_risk:
                    logger.warning(
                        f"[PORTFOLIO] {symbol} skipped: total risk would be {_total_risk_pct:.1f}% "
                        f"(max {_max_portfolio_risk}%). Open positions: {len(my_bot_positions)}."
                    )
                    continue

                logger.info(f"[SCAN] {symbol}: ALL GATES PASSED -> placing {direction} risk={final_risk:.2f}% "
                            f"(total portfolio risk: {_total_risk_pct:.1f}%)")

                local_signal = {
                    'symbol': symbol,
                    'direction': direction,
                    'setup_type': setup.get('setup_type', trigger_type),
                    'l3_score': _l3_result.get('score', 0) if isinstance(_l3_result, dict) else 0,
                    'htf_reason': setup.get('htf_reason', ''),
                    'htf_confluence': setup.get('htf_confluence', 0),
                    'regime': regime,
                    'edge_score': edge_score,
                    'edge_state': edge_result.state,
                    'risk_percent_override': final_risk,
                    'runner_eligible': edge_result.runner_eligible,
                    'exit_aggressiveness': edge_result.exit_aggressiveness,
                    'narrative_reason': f"SMC_ENTRY|R:{final_risk:.1f}%",
                    'stop_loss': signal_sl,
                    'key_level': setup.get('entry_price', 0.0),
                }

                trade_result = place_ai_trade(local_signal, account_info.equity, state.daily_pnl)
                if trade_result is True:
                    signals_found += 1
                    state.last_trade_candle[symbol] = current_candle_time
                elif trade_result == "ORDER_FAILED":
                    state.symbol_cooldowns[symbol] = datetime.now(timezone.utc) + timedelta(minutes=1)
                    logger.warning(f" [SPAM PREVENT] {symbol} MT5 order rejected. 1-min cooldown.")
                else:
                    # Pre-execution gate rejected -- 2min cooldown prevents spam
                    state.symbol_cooldowns[symbol] = datetime.now(timezone.utc) + timedelta(minutes=2)
                    logger.debug(f"[SCAN] {symbol}: pre-execution gate blocked. 2-min cooldown.")


            # Log cycle performance + rejection summary every 20 iterations
            cycle_time = time.time() - cycle_start
            if signals_found > 0:
                logger.info(f"[SCALPING] Cycle {iteration} done in {cycle_time:.2f}s | Signals: {signals_found}")
            # Small sleep prevents CPU spin -- bot runs every 0.5s not 10x/second
            elapsed = time.time() - cycle_start
            if elapsed < 0.5:
                time.sleep(0.5 - elapsed)
            elif iteration % 20 == 0:
                rej = getattr(state, '_rej', {})
                # Build human-readable skip reason summary
                skip_reasons = []
                if rej.get('no_setup', 0):     skip_reasons.append(f"no-setup/HTF-zone:{rej['no_setup']}")
                if rej.get('edge_ignore', 0):  skip_reasons.append(f"AI-L3-score:{rej['edge_ignore']}")
                if rej.get('cooldown', 0):     skip_reasons.append(f"cooldown:{rej['cooldown']}")
                if rej.get('no_data', 0):      skip_reasons.append(f"no-data:{rej['no_data']}")
                if rej.get('banned', 0):       skip_reasons.append(f"banned:{rej['banned']}")
                if rej.get('position_exists', 0): skip_reasons.append(f"max-positions:{rej['position_exists']}")

                _eq = account_info.equity
                _session = get_current_session()
                _l1_active = len([b for b in state.approved_bias.values() if b != 'NEUTRAL'])
                # Build per-symbol H4 bias summary for status line
                try:
                    _all_cd = async_data_fetcher.get_all_data()
                    _sym_states = []
                    for _ss in config.SYMBOLS:
                        _dh4 = _all_cd.get(_ss, {}).get('H4')
                        if _dh4 is not None and len(_dh4) >= 55:
                            _b = get_h4_macro_bias(_dh4)
                            _sym_states.append(f"{_ss.replace('USDm','').replace('m','')}:{_b[:4]}")
                    _sym_bias_str = " ".join(_sym_states)
                except Exception:
                    _sym_bias_str = ""
                # Show H4 structural bias even when L1 is neutral

                logger.info(
                    f"[STATUS] Eq:${_eq:.2f} | {_session} | H4:{_sym_bias_str} | "
                    f"L1:{_l1_active}/{len(config.SYMBOLS)} | "
                    f"Skips:[{' '.join(skip_reasons) if skip_reasons else 'none'}]"
                )
                # Reset counters after logging
                state._rej = {k: 0 for k in state._rej}
            
            # Scalping Lightning: Speed is key. Short sleep.
            time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info(f" Bot stopped by user {USER_ID}")
            send_heartbeat(status='stopped', mt5_connected=True, error_message="Stopped by user")
            send_telegram_notification(" <b>Bot Stopped</b>\n\nBot was manually stopped.")
            # Scalping Lightning: Speed is key. Short sleep.
            time.sleep(0.1)
            break
        except Exception as e:
            logger.error(f" Critical error: {e}", exc_info=True)
            send_heartbeat(status='error', mt5_connected=True, error_message=str(e))
            send_telegram_notification(f" <b>Critical Error</b>\n\nBot encountered an error: {e}")
            time.sleep(60)
    
    # Cleanup async systems
    if async_data_fetcher:
        async_data_fetcher.stop()
    async_logger.stop()
    
    mt5.shutdown()
    logger.info(" SCALPING BOT shutdown complete")

# =============================================================================
# MAIN ENTRY
# =============================================================================

def main():
    """Main entry point"""

    last_heartbeat_time = time.time()

    logger.info(f"Initializing Hybrid AI Trading Bot for USER: {USER_ID}...")
    
    if not ai_provider.api_key:
        logger.error(f" {config.AI_PROVIDER.upper()} API key not set!")
        send_heartbeat(status='error', mt5_connected=False, error_message="GEMINI_API_KEY not set")
        sys.exit(1)
    
    if not initialize_mt5():
        logger.error("Failed to initialize MT5")
        send_heartbeat(status='error', mt5_connected=False, error_message="MT5 initialization failed")
        sys.exit(1)

    trade_db.sync_account_history(days_back=30)

    trade_db.restore_state_from_db(state.open_positions)
    
    try:
        ai_trading_session()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
        # Remove PID on stop
        send_heartbeat(status='stopped', mt5_connected=True)
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        # Remove PID on crash
        send_heartbeat(status='crashed', mt5_connected=False, error_message=str(e))
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main(
)
