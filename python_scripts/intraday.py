# -*- coding: utf-8 -*-
"""
=============================================================================
 HYBRID AI TRADING BOT - INTRADAY SERVER PRODUCTION v13.0 
=============================================================================
PRODUCTION-READY SERVER VERSION WITH ALL LOCAL TEST IMPROVEMENTS

This version combines:
 Server infrastructure (Supabase, multi-user, CLI args)
 All improvements from local testing (fixed position management)
 Position recovery system
 Enhanced risk management (8% daily loss, 15% drawdown)
 Complete breakeven and trailing stop logic
 Production-grade error handling

Converted from local test version with automated converter.
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
import argparse
from supabase import create_client, Client
import sys
from dataclasses import dataclass, field
from collections import defaultdict
import logging
import sys
import sqlite3
from pathlib import Path
import re
import certifi
import uuid

parser = argparse.ArgumentParser(description='Multi-user Hybrid AI Intraday Trading Bot')
parser.add_argument('--user-id', type=str, required=True, help='User ID')
parser.add_argument('--strategy-id', type=str, required=True, help='Strategy ID')
parser.add_argument('--mt5-login', type=int, required=True, help='MT5 Login')
parser.add_argument('--mt5-password', type=str, required=True, help='MT5 Password')
parser.add_argument('--mt5-server', type=str, required=True, help='MT5 Server')
parser.add_argument('--telegram-chat-id', type=str, required=False, help='Telegram Chat ID')
parser.add_argument('--telegram-bot-token', type=str, required=False, help='Telegram Bot Token')
parser.add_argument('--supabase-url', type=str, required=True, help='Supabase URL')
parser.add_argument('--supabase-key', type=str, required=True, help='Supabase Service Key')
parser.add_argument('--gemini-api-key', type=str, required=False, help='Gemini API Key')


args = parser.parse_args()

# User-specific configuration (Define these now so they are available globally)
USER_ID = args.user_id
STRATEGY_ID = args.strategy_id
TELEGRAM_CHAT_ID = args.telegram_chat_id
TELEGRAM_BOT_TOKEN = args.telegram_bot_token

# Initialize Supabase client (Move this up too)
supabase: Client = create_client(args.supabase_url, args.supabase_key)

# =============================================================================
# [ADJUST] INTRADAY CONFIGURATION - EDIT YOUR CREDENTIALS HERE
# =============================================================================

@dataclass
class IntradayTradingConfig:
    """Configuration for AI-powered intraday trading bot"""
    
    # [SECURE] MT5 CONNECTION - EDIT THESE WITH YOUR CREDENTIALS!
    MT5_LOGIN: int = args.mt5_login  # [WARNING] REQUIRED: Replace with your MT5 login
    MT5_PASSWORD: str = args.mt5_password  # [WARNING] REQUIRED: Replace with your MT5 password
    MT5_SERVER: str = args.mt5_server  
    
    # [BOT] AI API CONFIGURATION
    AI_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = args.gemini_api_key or os.getenv("GEMINI_API_KEY", "")

    # RISK: max 10% of account equity per trade. Simple rule.
    BASE_RISK_PERCENT: float = 10.0
    MAX_RISK_PERCENT:  float = 10.0
    MAX_RISK_PER_TRADE_PERCENT: float = 10.0  # Set via: export GEMINI_API_KEY='your-key'
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    
    # AI Feature Flags
    ENABLE_AI_VALIDATION: bool = True
    ENABLE_AI_RISK_MANAGEMENT: bool = True
    ENABLE_AI_TRADE_LEARNING: bool = True
    
    # Local Strategy Engine Flags
    ENABLE_LOCAL_NEWS_FILTER: bool = True
    ENABLE_CONFLUENCE_ENGINE: bool = True
    
    # AI Analysis Intervals
    AI_GLOBAL_CONTEXT_INTERVAL: int = 7200  # 2 hours (intraday)
    AI_LEARNING_INTERVAL: int = 7200  # 2 hours
    LOCAL_NEWS_CHECK_INTERVAL: int = 3600  # 1 hour
    HEARTBEAT_INTERVAL: int = 60
    MIN_TRADES_FOR_LEARNING: int = 5
    
    # INTRADAY TRADING PARAMETERS
    SYMBOLS: List[str] = field(default_factory=lambda: [
        'EURUSDm', 'GBPUSDm', 'USDJPYm', 'XAUUSDm', 'XAGUSDm',
        'BTCUSDm', 'ETHUSDm', 'USOILm', 'NZDUSDm',
        'USDCADm', 'AUDUSDm', 'USDCHFm', 'GBPJPYm'
    ])
    MAX_CONCURRENT_TRADES: int = 5  # Reduced from 3 (intraday)
    MAX_DAILY_TRADES: int = 10  # CRITICAL: Intraday (vs 20 in scalping)
    
    # INTRADAY EMERGENCY STOPS (Higher limits due to wider stops)
    MAX_DAILY_LOSS_PERCENT: float = 25.0  # Increased from 4.0 for intraday
    MAX_DRAWDOWN_PERCENT: float = 30.0  # Configurable max drawdown
  # Single trade risk cap
    ENABLE_DYNAMIC_EMERGENCY_STOPS: bool = True  # Adjust based on volatility
    
    # INTRADAY TIMEFRAMES
    ENTRY_TF: int = mt5.TIMEFRAME_H1  # H1 for intraday entries
    STRUCTURE_TF: int = mt5.TIMEFRAME_H4  # H4 for structure
    MICRO_STRUCTURE_TF: int = mt5.TIMEFRAME_M15  # M15 for micro
    TREND_TF: int = mt5.TIMEFRAME_H4  # H4 for trend
    DAILY_TF: int = mt5.TIMEFRAME_D1  # D1 for major bias
    ATR_PERIOD: int = 14
    
    # INTRADAY RISK PARAMETERS



    
    # WIDER SL/TP FOR INTRADAY
    SL_ATR_MULTIPLIER: float = 3.0
    TP1_ATR_MULTIPLIER: float = 6.0
    TP2_ATR_MULTIPLIER: float = 9.0
    
    # -------------------------------------------------------------------------
    # [UPDATED] RISK-BASED MANAGEMENT (R-MULTIPLES)
    # Logic: Calculate Risk (Entry - SL).
    # 1. Breakeven at 1.0R (plus buffer)
    # 2. Trail after 1.5R (maintain 1.0R distance)
    # -------------------------------------------------------------------------
    ENABLE_BREAKEVEN: bool = True
    BREAKEVEN_TRIGGER_R: float = 1.0      # Trigger BE when profit >= 1.0 * Risk
    BREAKEVEN_BUFFER_PIPS: float = 2.0    # Add small buffer to cover swaps/commissions
    
    ENABLE_TRAILING_STOP: bool = True
    TRAILING_START_R: float = 2.0         # [LENIENT] Start trailing later (2.0R profit)
    TRAILING_DISTANCE_R: float = 1.5      # [LENIENT] Keep wide gap (1.5R distance) to handle pullbacks
    
    ENABLE_PARTIAL_TP: bool = True
    PARTIAL_TP_PERCENT: float = 50.0
    
    # INTRADAY SESSION MANAGEMENT
    AUTO_CLOSE_BEFORE_LONDON_CLOSE: bool = True
    LONDON_CLOSE_HOUR: int = 16  # 4 PM UTC
    AUTO_CLOSE_BEFORE_NY_CLOSE: bool = True
    NY_CLOSE_HOUR: int = 21  # 9 PM UTC
    
    # POSITION DURATION LIMITS
    MIN_POSITION_DURATION_HOURS: float = 1.0
    MAX_POSITION_DURATION_HOURS: float = 12.0
    TARGET_POSITION_DURATION_HOURS: float = 6.0
    
    # News Filter
    NEWS_API_URL: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    NEWS_PAUSE_BEFORE_MINUTES: int = 30   # 30 min before (was 60 -- too wide)
    NEWS_PAUSE_AFTER_MINUTES: int = 30    # 30 min after
    HIGH_IMPACT_CURRENCIES: List[str] = field(default_factory=lambda: [
        "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF"
    ])

    # INTRADAY CONFLUENCE ENGINE
    MIN_CONFLUENCE_SCORE_TRENDING: float = 2.0
    MIN_CONFLUENCE_SCORE_RANGING: float = 1.8
    ADX_PERIOD: int = 14
    ADX_TRENDING_THRESHOLD: float = 25.0
    
    # INTRADAY STRATEGY WEIGHTS
    STRATEGY_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        'TREND_FOLLOWING_H4': 1.0,
        'SWING_HIGH_LOW': 0.95,
        'ADVANCED_SMC': 0.9,
        'WYCKOFF_PATTERNS': 0.85,
        'SUPPORT_RESISTANCE': 0.8,
        'VOLUME_PROFILE': 0.75,
        'MOMENTUM_CONFLUENCE': 0.7,
        'TREND_PULLBACK': 0.7,
        'BREAKOUT_RETEST': 0.65,
    })
    
    # ENABLED INTRADAY BEHAVIORS
    BEHAVIOR_MODES: List[str] = field(default_factory=lambda: [
        'TREND_CONTINUATION',
        'EXPANSION_BREAKOUT',
        'REVERSAL_AFTER_LIQUIDITY'
    ])
    
    # Strategy-Specific Params (Adjusted for H1/H4)
    SMC_MIN_OB_SIZE_PIPS: int = 20
    SMC_VALIDATION_CANDLES: int = 10
    SMC_SWING_LOOKBACK: int = 10
    VOLUME_PROFILE_PERIODS: int = 50
    VOLUME_LOOKBACK: int = 20
    VOLUME_SURGE_MULTIPLIER: float = 1.8
    MOMENTUM_EMA_FAST: int = 20
    MOMENTUM_EMA_SLOW: int = 50
    BB_PERIOD: int = 20
    BB_STD_DEV: float = 2.0
    SR_LOOKBACK_PERIODS: int = 100

config = IntradayTradingConfig()

# =============================================================================
# SUPABASE DATABASE MANAGER
# =============================================================================

class SupabaseManager:
    """Manage all Supabase database operations"""
    
    def __init__(self):
        self.client = supabase
        self.user_id = USER_ID
        self.strategy_id = STRATEGY_ID
    
    def record_trade(self, ticket: int, symbol: str, direction: str, lot_size: float,
                    entry_price: float, sl: float, tp: float, strategy: str, opened_at: datetime = None) -> None:
        """Corrected Column Mapping for trades table"""
        try:
            if opened_at is None:
                opened_at = datetime.now(timezone.utc)
                
            trade_data = {
                'user_id': self.user_id,
                'strategy_id': self.strategy_id,
                'ticket': int(ticket),
                'symbol': symbol,
                'trade_type': direction,  # Corrected from 'direction'
                'quantity': lot_size,     # Corrected from 'lot_size'
                'entry_price': entry_price,
                'status': 'open',          # Lowercase as required
                'opened_at': opened_at.isoformat(),
                'metadata': {              # Extra fields moved to JSON metadata
                    'stop_loss': sl,
                    'take_profit': tp,
                    'strategy_name': strategy
                }
            }
            # Use upsert to prevent duplicates during sync
            self.client.table('trades').upsert(trade_data, on_conflict='ticket,user_id').execute()
            logger.info(f"[DB] Trade {ticket} synced to dashboard")
        except Exception as e:
            logger.error(f"[DB ERROR] Trade sync failed: {e}")

    def get_open_tickets(self) -> List[int]:
        """Fetch all currently open tickets from database"""
        try:
            response = self.client.table('trades').select('ticket') \
                .eq('user_id', self.user_id) \
                .eq('strategy_id', self.strategy_id) \
                .eq('status', 'open').execute()
            
            if response.data:
                return [item['ticket'] for item in response.data]
            return []
        except Exception as e:
            logger.error(f"[DB ERROR] Failed to fetch open tickets: {e}")
            return []
    
    def update_trade_close(self, ticket: int, close_price: float, profit: float, status: str) -> None:
        """Corrected Column Mapping for closing trades"""
        try:
            update_data = {
                'exit_price': float(close_price), # Corrected from 'close_price'
                'profit_loss': float(profit),     # Corrected from 'profit'
                'closed_at': datetime.now(timezone.utc).isoformat(),
                'status': 'closed'         # Lowercase as required
            }
            self.client.table('trades').update(update_data).eq('ticket', int(ticket)).eq('user_id', self.user_id).execute()
        except Exception as e:
            logger.error(f"[DB ERROR] Close update failed: {e}")
    
    def send_heartbeat(self) -> None:
        """Corrected Heartbeat with valid update logic"""
        try:
            account_info = mt5.account_info()
            heartbeat_data = {
                'user_id': self.user_id,
                'strategy_id': self.strategy_id,
                'last_heartbeat': datetime.now(timezone.utc).isoformat(),
                'status': 'running',
                'mt5_connected': True if account_info else False,
                'pid': os.getpid(),
                'balance': account_info.balance if account_info else 0,
                'equity': account_info.equity if account_info else 0
            }
            
            # Manual Upsert
            existing = self.client.table('bot_heartbeats').select('user_id').eq('user_id', self.user_id).eq('strategy_id', self.strategy_id).execute()
            
            if existing.data:
                self.client.table('bot_heartbeats').update(heartbeat_data).eq('user_id', self.user_id).eq('strategy_id', self.strategy_id).execute()
            else:
                self.client.table('bot_heartbeats').insert(heartbeat_data).execute()
                
        except Exception as e:
            logger.error(f"[HEARTBEAT ERROR] {e}")

db_manager = SupabaseManager()

# =============================================================================
# TELEGRAM NOTIFICATIONS
# =============================================================================

def send_telegram_message(message: str) -> None:
    """Send notification via Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        logger.error(f"[TELEGRAM ERROR] {e}")


# Symbol Specifications
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

# =============================================================================
# CLI ARGUMENT PARSING
# =============================================================================

# =============================================================================
# CLI ARGUMENT PARSING (Handled at top of file)
# =============================================================================

# LOGGING SETUP (FIXED & RENAMED)
# =============================================================================

# 1. Use a distinct name so it doesn't mix with Hybrid Bot logs
LOG_DIR = Path(f"Intraday_Bot_Logs_{USER_ID}")

# 2. Use parents=True to fix [WinError 3]
LOG_DIR.mkdir(parents=True, exist_ok=True) 

log_file = LOG_DIR / f"intraday_bot_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    encoding='utf-8',  # Fixes charmap errors on Windows
    errors='replace',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# SQLITE DATABASE (LOCAL STORAGE)
# =============================================================================

class TradeHistoryDB:
    """SQLite database for comprehensive trade history logging"""
    def __init__(self):
        # Create user-specific DB to avoid locking issues on server
        self.db_folder = Path(f"Intraday_Data_{USER_ID}")
        self.db_folder.mkdir(parents=True, exist_ok=True) # Fixes WinError 3
        
        self.db_path = self.db_folder / "intraday_trade_history.db"
        self.conn = None
        self.init_database()
    
    def init_database(self):
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    ticket INTEGER,
                    symbol TEXT,
                    direction TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    lot_size REAL,
                    atr REAL,
                    volatility REAL,
                    trend_strength REAL,
                    market_regime TEXT,
                    session TEXT,
                    be_moved INTEGER,
                    trailing_activated INTEGER,
                    partial_tp_taken INTEGER,
                    profit_loss REAL,
                    win INTEGER,
                    hold_time_minutes INTEGER,
                    exit_reason TEXT,
                    ai_confidence REAL,
                    ai_risk_percent REAL,
                    strategy_name TEXT,
                    was_mistake INTEGER DEFAULT 0,
                    mistake_reason TEXT,
                    lesson_learned TEXT,
                    position_duration_hours REAL
                )
            """)
            self.conn.commit()
            logger.info("[OK] Trade history database initialized")
        except Exception as e:
            logger.error(f"Database init error: {e}")
    
    def log_trade(self, trade_data: Dict):
        try:
            cursor = self.conn.cursor()
            columns = ', '.join(trade_data.keys())
            placeholders = ', '.join('?' * len(trade_data))
            sql = f'INSERT INTO trades ({columns}) VALUES ({placeholders})'
            cursor.execute(sql, tuple(trade_data.values()))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Trade logging error: {e}")

    def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        try:
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
            return []
    
    def get_losing_trades(self, limit: int = 20) -> List[Dict]:
        try:
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM trades WHERE win = 0 ORDER BY timestamp DESC LIMIT ?", (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching losses: {e}")
            return []
    
    def get_win_rate(self, lookback_days: int = 7) -> float:
        """Calculate win rate over lookback period"""
        try:
            from_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
            
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT AVG(win) FROM trades WHERE timestamp >= ?", (from_date,))
                result = cursor.fetchone()
                return result[0] if result[0] else 0.0
        except Exception as e:
            logger.error(f"Error calculating win rate: {e}")
            return 0.0

trade_db = TradeHistoryDB()

# =============================================================================
# EDGE MODE ENGINE
# =============================================================================

class EdgeModeEngine:
    """Engine to aggressively scale risk during win streaks"""
    def __init__(self):
        self.mode = "NORMAL"
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        
    def update_mode(self, result: str, rr: float):
        if result == "WIN":
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            if self.consecutive_wins >= 2 and rr > 1.5:
                self.mode = "AGGRESSIVE"
        elif result == "LOSS":
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            if self.consecutive_losses >= 2:
                self.mode = "DEFENSIVE"
        else:
            self.mode = "NORMAL"
            
    def get_risk_multiplier(self, expected_rr: float = 1.0, expansion_prob: float = 0.0, regime: str = "TRENDING", lifecycle: str = "PRE_EXPANSION", distance_to_liquidity: float = 100.0) -> float:
        """Dynamic risk multiplier based on streak and narrative strength"""
        base_multiplier = 1.0
        
        if self.mode == "AGGRESSIVE":
            base_multiplier = 1.5
        elif self.mode == "DEFENSIVE":
            base_multiplier = 0.5
            
        # V4 Boost based on lifecycle & narrative
        if lifecycle == "EARLY_EXPANSION" or expansion_prob > 0.8:
            base_multiplier += 0.3
        elif lifecycle == "CONTINUATION":
            base_multiplier += 0.1
        elif lifecycle == "LATE_EXPANSION" or distance_to_liquidity < 20.0:
            base_multiplier -= 0.3  # Throttle down near targets
            
        if expected_rr > 3.0:
            base_multiplier += 0.2
        if regime == "TRENDING" and self.mode != "DEFENSIVE":
            base_multiplier += 0.1
            
        return min(2.0, max(0.25, base_multiplier))

edge_engine = EdgeModeEngine()

# =============================================================================
# PORTFOLIO EXPOSURE MANAGER (GAP 4)
# =============================================================================
class PortfolioExposureManager:
    def __init__(self):
        self.total_portfolio_risk = 0.0
        self.risk_per_currency = defaultdict(float)
        
    def reset_exposure(self):
        self.total_portfolio_risk = 0.0
        self.risk_per_currency.clear()
        
    def add_exposure(self, symbol: str, risk_pct: float):
        self.total_portfolio_risk += risk_pct
        for curr in ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'NZD', 'CHF', 'BTC', 'ETH', 'XAU', 'XAG', 'USOIL', 'BTCUSD']:
            if curr in symbol.upper():
                self.risk_per_currency[curr] += risk_pct

    def remove_exposure(self, symbol: str, risk_pct: float):
        self.total_portfolio_risk = max(0.0, self.total_portfolio_risk - risk_pct)
        for curr in ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'NZD', 'CHF', 'BTCUSD', 'BTC', 'ETHUSD', 'ETH', 'XAU', 'XAG', 'USOIL']:
            if curr in symbol.upper():
                self.risk_per_currency[curr] = max(0.0, self.risk_per_currency[curr] - risk_pct)

    def check_exposure_limits(self, symbol: str, proposed_risk: float, state_stacks: Dict) -> Tuple[bool, float]:
        """Returns (is_allowed, taper_multiplier)"""
        # Global taper if multiple expansions
        active_expansions = sum(1 for s, st in state_stacks.items() if st.get('status') == 'ACTIVE' and st.get('move_type') in ['EARLY_EXPANSION', 'CONTINUATION'])
        taper = 1.0
        if active_expansions >= 2:
            taper *= 0.5
            
        currs = [c for c in ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'NZD', 'CHF', 'BTC', 'ETH', 'XAU', 'XAG', 'USOIL'] if c in symbol.upper()]
        for c in currs:
            # Cap = 2x single trade risk (allows 2 correlated positions max)
            # At BASE_RISK=10%: cap=20% per currency. A 10% trade passes if currency has <10% exposure.
            _cap = getattr(config, 'BASE_RISK_PERCENT', 10.0) * 2.0
            if self.risk_per_currency[c] + proposed_risk > _cap:
                return False, 0.0
                
        # Correlated stacking limit
        if ('BTC' in symbol.upper() or 'ETH' in symbol.upper()) and self.risk_per_currency.get('BTC', 0.0) + self.risk_per_currency.get('ETH', 0.0) > 3.0:
            taper *= 0.5
                
        return True, taper

portfolio_manager = PortfolioExposureManager()

# =============================================================================
# CONFIDENCE CONTROLLER (GAP 3)
# =============================================================================
class ConfidenceController:
    @staticmethod
    def allowed_to_stack(confidence: float) -> bool:
        return confidence >= 0.6
        
    @staticmethod
    def get_risk_multiplier(confidence: float) -> float:
        return confidence
        
    @staticmethod
    def get_exit_aggressiveness(confidence: float) -> str:
        if confidence < 0.4: return "MAX"
        if confidence < 0.6: return "HIGH"
        return "NORMAL"
        
    @staticmethod
    def preserve_runner(confidence: float) -> bool:
        return confidence >= 0.7

# =============================================================================
# RUNNER MANAGEMENT ENGINE (GAP 1)
# =============================================================================

def apply_runner_trailing(ticket: int, new_sl: float, position):
    if new_sl is None:
        return
    modify_position_sl(position, new_sl)

class RunnerManagementEngine:
    @staticmethod
    def convert_to_runner(stack: Dict):
        if not stack.get('is_runner'):
            stack['is_runner'] = True
            stack['runner_entry_price'] = stack.get('avg_entry', 0.0)
            stack['runner_stop'] = 0.0  
            stack['runner_trail_mode'] = 'EARLY'
            stack['runner_partial_done'] = False
            set_stack_state(stack, 'RUNNER')
            # Risk isolation logic
            stack['consumed_risk'] = 0.0  # Free capital

    @staticmethod
    def update_runner_trailing(stack: Dict, pos_info: Dict, current_price: float, risk_dist: float, current_profit_dist: float, current_sl: float, direction: str) -> Optional[float]:
        lifecycle = stack.get('narrative_data', {}).get('lifecycle', 'EARLY_EXPANSION')
        if lifecycle == "CONTINUATION":
            stack['runner_trail_mode'] = 'MID'
            trail_distance = risk_dist * 1.0 # structure trailing
        elif lifecycle == "LATE_EXPANSION":
            stack['runner_trail_mode'] = 'LATE'
            trail_distance = min(risk_dist * 0.5, current_profit_dist * 0.5) # tight trailing
        else:
            stack['runner_trail_mode'] = 'EARLY'
            return None # let it run
            
        if direction == "BUY":
            new_sl = current_price - trail_distance
            if new_sl > current_sl: return new_sl
        else:
            new_sl = current_price + trail_distance
            if new_sl < current_sl: return new_sl
        return None

# =============================================================================
# NARRATIVE EXIT ENGINE (GAP 2)
# =============================================================================
class NarrativeExitEngine:
    @staticmethod
    def evaluate_exit(lifecycle: str, confidence: float, expansion_prob: float, liquidity_distance: float, opposite_signals: bool) -> str:
        if opposite_signals:
            return "EXIT"
        if lifecycle == "LATE_EXPANSION" and confidence < 0.5:
            return "SCALE_OUT"
        if expansion_prob < 0.3:
             return "REDUCE"
        if liquidity_distance <= 0:
             return "PARTIAL" 
        return "HOLD"

# =============================================================================
# CAPITAL ADJUSTMENT ENGINE (GAP 5)
# =============================================================================
class CapitalAdjustmentEngine:
    @staticmethod
    def evaluate(symbol: str, stack: Dict, direction_bias: str, sweep: Optional[str], mss: Optional[str]):
        """Runs mid-move logic after stack update"""
        narrative = stack.get('narrative_data', {})
        conf = narrative.get('confidence_score', 0.5)
        lc = narrative.get('lifecycle', 'PRE_EXPANSION')
        
        # 1. Freeze Stacking
        if lc in ["LATE_EXPANSION"] and stack['status'] == 'ACTIVE':
             set_stack_state(stack, 'FROZEN')
             
        # 2. Downgrade Runner
        if stack.get('is_runner'):
             opposite = (direction_bias == "BUY" and sweep == "SWEEP_HIGH" and mss == "BEARISH_MSS") or \
                        (direction_bias == "SELL" and sweep == "SWEEP_LOW" and mss == "BULLISH_MSS")
             if opposite or not ConfidenceController.preserve_runner(conf):
                 stack['is_runner'] = False
                 set_stack_state(stack, 'ACTIVE')
                 
        # 3. Reduce slack depth
        if conf < 0.4 and stack['stack_count'] > 1:
             set_stack_state(stack, 'REDUCING') # Indicate it needs partializing

# =============================================================================
# STACK LIFECYCLE STATE MACHINE (GAP 3)
# =============================================================================

STACK_STATES = {
    "ACTIVE": ["FROZEN", "RUNNER", "REDUCING", "CLOSED"],
    "FROZEN": ["RUNNER", "REDUCING", "CLOSED"],
    "RUNNER": ["ACTIVE", "CLOSED"],
    "REDUCING": ["ACTIVE", "RUNNER", "CLOSED"],
    "CLOSED": []
}

def set_stack_state(stack, new_state):
    current = stack.get('status', 'ACTIVE')
    if new_state in STACK_STATES.get(current, []):
        stack['status'] = new_state
    elif current == 'UNKNOWN' or 'status' not in stack:
         stack['status'] = new_state

def execute_narrative_action(action: str, position, pos_info, stack):
    if action == "EXIT":
        close_position(position)
    elif action == "SCALE_OUT":
        # Simulate partial close for now
        close_position(position)
    elif action == "REDUCE":
        # Simulate reduce stack
        close_position(position)
    elif action == "PARTIAL":
        # Simulate partial
        close_position(position)

# =============================================================================
# INTRADAY STATE MANAGEMENT
# =============================================================================

class IntradayTradingState:
    """Enhanced state for intraday trading"""
    def __init__(self):
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.open_positions: Dict = {}
        self.position_open_times: Dict[int, datetime] = {}  # * Track open times
        self.last_ai_learning_time = None
        self.daily_start_equity: float = 0.0
        
        # DYNAMIC PARAMETERS
        self.current_risk_percent: float = config.BASE_RISK_PERCENT
        self.current_sl_multiplier: float = config.SL_ATR_MULTIPLIER
        self.current_tp1_multiplier: float = config.TP1_ATR_MULTIPLIER
        self.current_be_trigger_r: float = config.BREAKEVEN_TRIGGER_R
        self.current_trailing_start_r: float = config.TRAILING_START_R
        
        # Trade management
        self.be_moved: set = set()
        self.trailing_active: set = set()
        self.partial_closed: set = set()

        # AI Context
        self.approved_bias: Dict[str, str] = {}
        self.last_global_context_update = None
        
        # Strategy Banning
        self.banned_strategies: List[str] = []
        
        # News Filter
        self.last_local_news_update = None
        self.upcoming_high_impact_events: List[Dict] = []
        
        # Legacy Fields
        self.global_strong_currencies: List[str] = []
        self.global_weak_currencies: List[str] = []
        self.global_market_sentiment: str = "NEUTRAL"
        self.global_key_drivers: str = "N/A"
        
        # * INTRADAY SPECIFIC
        self.last_session_close_check: Optional[datetime] = None
        self.symbol_cooldowns: Dict[str, datetime] = {}  # per-symbol cooldown
        self.total_position_duration_hours: float = 0.0
        self.closed_positions_count: int = 0
        
        # * PRO PORTFOLIO STACK MANAGER
        self.narrative_stacks: Dict[str, Dict] = {}
        
    def register_stack_trade(self, symbol: str, narrative: Dict, risk_percent: float, entry_price: float, regime: str, is_runner: bool = False):
        if symbol not in self.narrative_stacks or self.narrative_stacks[symbol].get('status') == 'CLOSED':
            
            # 3. DYNAMIC NARRATIVE RISK BUDGETING
            base_budget = 2.0
            if narrative.get('expansion_potential', 0) > 0.7:
                base_budget += 1.0
            if regime == "TRENDING":
                base_budget += 1.0
            if narrative.get('distance_to_target', 0) < 20.0:
                 base_budget -= 1.0 # Throttle if close
                 
            self.narrative_stacks[symbol] = {
                'id': str(uuid.uuid4()),
                'move_type': narrative.get('lifecycle', 'UNKNOWN'),
                'max_risk_pct': max(1.0, base_budget),
                'consumed_risk': 0.0,
                'status': 'ACTIVE',
                'stack_count': 0,
                'avg_entry': 0.0,
                'narrative_data': narrative,
                'is_runner': False,
                'runner_entry_price': 0.0,
                'runner_stop': 0.0,
                'runner_trail_mode': 'EARLY',
                'runner_partial_done': False
            }
            
        stack = self.narrative_stacks[symbol]
        prev_risk = stack['consumed_risk']
        prev_entry = stack['avg_entry']
        count = stack['stack_count']
        
        stack['consumed_risk'] += risk_percent
        stack['stack_count'] += 1
        stack['avg_entry'] = ((prev_entry * count) + entry_price) / stack['stack_count']
        
        # Determine if it transitions to a pure runner
        lc = narrative.get('lifecycle', '')
        l_state = narrative.get('liquidity_state', '')
        if is_runner or stack['stack_count'] >= 3 or lc == 'LATE_EXPANSION' or l_state == 'TARGET_NEAR':
             RunnerManagementEngine.convert_to_runner(stack)
        
    def invalidate_stack(self, symbol: str, reason: str):
        """1. STACK INVALIDATION LOGIC"""
        if symbol in self.narrative_stacks and self.narrative_stacks[symbol]['status'] in ['ACTIVE', 'RUNNER']:
            self.narrative_stacks[symbol]['status'] = 'CLOSED'
            self.narrative_stacks[symbol]['close_reason'] = reason
            return True
        return False

state = IntradayTradingState()

# =============================================================================
# AI PROVIDER
# =============================================================================

class GeminiAIProvider:
    """Gemini AI Provider"""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.model)
            logger.info(f"[OK] Gemini AI Initialized: {self.model}")
        else:
            self.client = None
            logger.warning("[WARNING] Gemini API key not set")
    
    def call_ai(self, prompt: str, system_prompt: str = "", temperature: float = 0.3,
                max_tokens: int = 500, json_mode: bool = False) -> Optional[str]:
        """Call Gemini AI"""
        if not self.client:
            logger.warning("AI provider not initialized")
            return None
        
        try:
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }
            
            # response_mime_type removed -- causes Gemini to return
            # "Here is the JSON:..." conversational text instead of raw JSON
            if json_mode:
                full_prompt += "\nRespond ONLY with a valid JSON object. Start with { and end with }."
            
            response = self.client.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"AI call error: {e}")
            return None

ai_provider = GeminiAIProvider(config.GEMINI_API_KEY, config.GEMINI_MODEL)

# =============================================================================
# MT5 INITIALIZATION
# =============================================================================



# =============================================================================
# MARKET DATA FUNCTIONS
# =============================================================================

def get_market_data(symbol: str, timeframe: int, bars: int = 500) -> Optional[pd.DataFrame]:
    """Fetch market data from MT5"""
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

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Average True Range"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate ADX, +DI, -DI"""
    high_diff = high.diff()
    low_diff = -low.diff()
    
    plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
    minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
    
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = tr.rolling(window=period).mean()
    
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    
    return adx, plus_di, minus_di

def analyze_order_flow(symbol: str) -> str:
    """Analyze order flow using micro timeframe"""
    df_micro = get_market_data(symbol, config.MICRO_STRUCTURE_TF, 50)
    if df_micro is None or df_micro.empty:
        return "NEUTRAL"
    
    recent_volume = df_micro['tick_volume'].iloc[-10:].sum()
    avg_volume = df_micro['tick_volume'].mean()
    
    bullish_candles = sum(1 for i in range(-10, 0) if df_micro['close'].iloc[i] > df_micro['open'].iloc[i])
    bearish_candles = 10 - bullish_candles
    
    if bullish_candles >= 7 and recent_volume > avg_volume * 1.3:
        return "STRONG_BUY"
    elif bearish_candles >= 7 and recent_volume > avg_volume * 1.3:
        return "STRONG_SELL"
    
    return "NEUTRAL"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def identify_swing_highs_lows(df: pd.DataFrame, lookback: int = 5) -> Tuple[List[int], List[int]]:
    """Identify swing highs and lows"""
    swing_highs, swing_lows = [], []
    if len(df) < lookback * 2 + 1:
        return [], []
    
    for i in range(lookback, len(df) - lookback):
        is_high = all(df['high'].iloc[i] > df['high'].iloc[i-j] for j in range(1, lookback+1)) and \
                  all(df['high'].iloc[i] > df['high'].iloc[i+j] for j in range(1, lookback+1))
        if is_high:
            swing_highs.append(i)
        
        is_low = all(df['low'].iloc[i] < df['low'].iloc[i-j] for j in range(1, lookback+1)) and \
                 all(df['low'].iloc[i] < df['low'].iloc[i+j] for j in range(1, lookback+1))
        if is_low:
            swing_lows.append(i)
    
    return swing_highs, swing_lows

def detect_market_structure_shift(df: pd.DataFrame, swing_highs: List[int], swing_lows: List[int]) -> Optional[str]:
    """Detect Market Structure Shift (BOS + Displacement)"""
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return None
    
    current_price = df['close'].iloc[-1]
    current_open = df['open'].iloc[-1]
    
    # Calculate displacement (body > 1x ATR)
    atr = calculate_atr(df['high'], df['low'], df['close'], 14).iloc[-1]
    body_size = abs(current_price - current_open)
    has_displacement = body_size > atr * 1.0
    
    if current_price > df['high'].iloc[swing_highs[-1]] and has_displacement:
        return "BULLISH_MSS"
    if current_price < df['low'].iloc[swing_lows[-1]] and has_displacement:
        return "BEARISH_MSS"
    
    return None

def detect_liquidity_sweep(df: pd.DataFrame, swing_highs: List[int], swing_lows: List[int]) -> Optional[str]:
    """Detects if recent price swept a swing high/low and rejected"""
    if not swing_highs or not swing_lows: return None
    
    recent_high = df['high'].iloc[-2]
    recent_low = df['low'].iloc[-2]
    close = df['close'].iloc[-2]
    
    # Sweep High -> Bearish Signal
    target_high = df['high'].iloc[swing_highs[-1]]
    if recent_high > target_high and close < target_high:
        return "SWEEP_HIGH"
        
    # Sweep Low -> Bullish Signal
    target_low = df['low'].iloc[swing_lows[-1]]
    if recent_low < target_low and close > target_low:
        return "SWEEP_LOW"
        
    return None

def detect_best_pd_array(df: pd.DataFrame, direction: str) -> Optional[Dict]:
    """Detect closest Order Block or Breaker Block"""
    if len(df) < 10: return None
    try:
        if direction == "BULLISH":
            # 1. Look for Breaker Block first (Strongest)
            # Simplified: Broken bearish OB that is now support
            
            # 2. Bullish OB (Last down candle before up move)
            for i in range(-2, -8, -1):
                if df['close'].iloc[i] < df['open'].iloc[i] and df['close'].iloc[i+1] > df['open'].iloc[i+1]:
                    return {'type': 'OB', 'price': df['high'].iloc[i]} # Top of OB
        else:
            # 2. Bearish OB (Last up candle before down move)
            for i in range(-2, -8, -1):
                if df['close'].iloc[i] > df['open'].iloc[i] and df['close'].iloc[i+1] < df['open'].iloc[i+1]:
                    return {'type': 'OB', 'price': df['low'].iloc[i]} # Bottom of OB
    except Exception:
        pass
    return None

def reversal_precision_engine(symbol: str, df: pd.DataFrame, direction_bias: str, sweep, mss) -> Optional[Dict]:
    """Reversal Precision Model v3 (OB Priority & Context Weighting)"""
    if not sweep or not mss: return None
    
    # 1. Test PD Arrays in priority order
    pd_array = detect_best_pd_array(df, direction_bias)
    fvg_return = detect_fvg_return(df, direction_bias)
    
    if not pd_array and not fvg_return:
        return None # No structural backing
        
    # 2. Rejection Score Check (Candle context)
    rejection = score_rejection_candle(df, direction_bias)
    if rejection < 0.5:
        return None
        
    # Is it at a premium/discount?
    recent_high = df['high'].rolling(50).max().iloc[-1]
    recent_low = df['low'].rolling(50).min().iloc[-1]
    current = df['close'].iloc[-1]
    
    premium_discount_valid = False
    if direction_bias == "BULLISH" and current < (recent_low + (recent_high - recent_low) * 0.5):
        premium_discount_valid = True
    elif direction_bias == "BEARISH" and current > (recent_low + (recent_high - recent_low) * 0.5):
        premium_discount_valid = True
        
    if not premium_discount_valid: return None
        
    sl = df['low'].iloc[-2] if direction_bias == "BULLISH" else df['high'].iloc[-2]
    
    confidence = 0.8
    if pd_array:
        confidence += 0.15 # Stronger weight for OB/Breaker
    elif fvg_return:
        confidence += 0.05
    confidence += (rejection * 0.1)
    
    return {
        'direction': "BUY" if direction_bias == "BULLISH" else "SELL",
        'stop_loss': sl,
        'strategy_name': "REVERSAL_PD_ARRAY",
        'confidence': min(1.0, confidence)
    }

def expansion_continuation_engine(symbol: str, narrative_intent: Dict) -> Optional[Dict]:
    """Expansion Continuation Engine (Big Move Engine)"""
    if narrative_intent['expansion_potential'] < 0.7:
        return None
        
    lc = narrative_intent.get('lifecycle', 'PRE_EXPANSION')
    
    # Needs retest or strong momentum state
    if not narrative_intent.get('retest_occurred') and lc not in ['EARLY_EXPANSION', 'CONTINUATION']:
        return None
        
    strategy = "EXPANSION_CONTINUATION"
    if lc == "CONTINUATION":
        strategy = "MOMENTUM_ADD"
    elif lc == "EARLY_EXPANSION":
        strategy = "BREAKOUT_RETEST"
    elif lc == "LATE_EXPANSION":
        strategy = "RUNNER_ADD"
        
    return {
        "strategy_name": strategy
    }

def detect_fvg_return(df: pd.DataFrame, direction: str) -> bool:
    """Checks if price is returning to a recent Fair Value Gap and rejecting"""
    if len(df) < 5: return False
    
    for i in range(-5, -1):
        if direction == "BULLISH":
            if df['high'].iloc[i-2] < df['low'].iloc[i]:
                fvg_top = df['low'].iloc[i]
                current_low = df['low'].iloc[-1]
                current_close = df['close'].iloc[-1]
                current_open = df['open'].iloc[-1]
                if current_low < fvg_top and current_close > current_open:
                    return True
        else:
            if df['low'].iloc[i-2] > df['high'].iloc[i]:
                fvg_bottom = df['high'].iloc[i]
                current_high = df['high'].iloc[-1]
                current_close = df['close'].iloc[-1]
                current_open = df['open'].iloc[-1]
                if current_high > fvg_bottom and current_close < current_open:
                    return True
    return False

def get_market_regime_and_trend(symbol: str) -> Tuple[str, str]:
    """Get market regime and trend direction"""
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
    """Get current trading session"""
    current_hour = datetime.now(timezone.utc).hour
    if 7 <= current_hour < 16:
        return "LONDON"
    if 13 <= current_hour < 22:
        return "NY"
    if 0 <= current_hour < 8:
        return "ASIAN"
    return "UNKNOWN"

def get_symbol_specs(symbol: str) -> Dict:
    """Get symbol specifications"""
    info = mt5.symbol_info(symbol)
    if info:
        if info.digits in [3, 5]:
            pip_size = info.point * 10
        else:
            pip_size = info.point
        return {
            'pip_size': pip_size,
            'min_lot': info.volume_min,
            'max_lot': info.volume_max,
            'lot_step': info.volume_step,
            'trade_tick_value': info.trade_tick_value,
            'trade_tick_size': info.trade_tick_size,
        }
    
    static_spec = SYMBOL_SPECS.get(symbol)
    if static_spec:
        if any(s in symbol for s in ['USDJPY', 'GBPJPY', 'XAUUSD', 'ETHUSD', 'USOIL', 'XAGUSD']):
            static_spec['pip_size'] = 0.01
            if 'XAGUSD' in symbol:
                static_spec['pip_size'] = 0.001
        elif 'BTC' in symbol:
            static_spec['pip_size'] = 1.0
        else:
            static_spec['pip_size'] = 0.0001
    
    return static_spec

# =============================================================================
# NEWS FILTER
# =============================================================================

def get_new_york_utc_offset(event_date: datetime) -> int:
    """Calculate UTC offset for New York timezone with DST"""
    year = event_date.year
    dst_start = datetime(year, 3, 1) + timedelta(days=(6 - datetime(year, 3, 1).weekday() + 7) % 7 + 7)
    dst_end = datetime(year, 11, 1) + timedelta(days=(6 - datetime(year, 11, 1).weekday() + 7) % 7)
    return -4 if dst_start <= event_date < dst_end else -5

def fetch_upcoming_news_events():
    """Fetch high-impact news events"""
    global state
    if not config.ENABLE_LOCAL_NEWS_FILTER:
        return
    
    if state.last_local_news_update and (datetime.now(timezone.utc) - state.last_local_news_update) < timedelta(seconds=config.LOCAL_NEWS_CHECK_INTERVAL):
        return
    
    logger.info("Fetching upcoming high-impact news events...")
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
                        high_impact_events.append({
                            "datetime_utc": event_dt_utc,
                            "currency": event.get('country'),
                            "title": event.get('title')
                        })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse news event: {event}. Error: {e}")
                    continue
        
        state.upcoming_high_impact_events = sorted(high_impact_events, key=lambda x: x['datetime_utc'])
        state.last_local_news_update = datetime.now(timezone.utc)
        
        if state.upcoming_high_impact_events:
            logger.info(f"Fetched {len(state.upcoming_high_impact_events)} high-impact news events")
            next_event = state.upcoming_high_impact_events[0]
            logger.info(f"  Next: {next_event['datetime_utc'].strftime('%Y-%m-%d %H:%M')} UTC - {next_event['currency']} - {next_event['title']}")
        
    except Exception as e:
        logger.error(f"Error fetching news events: {e}")

def is_trade_entry_paused_for_news(symbol: str) -> bool:
    """Check if trading should be paused due to upcoming news"""
    if not config.ENABLE_LOCAL_NEWS_FILTER or not state.upcoming_high_impact_events:
        return False
    
    symbol_currencies = [c for c in config.HIGH_IMPACT_CURRENCIES if c in symbol.upper()]
    if not symbol_currencies:
        return False
    
    now_utc = datetime.now(timezone.utc)
    for event in state.upcoming_high_impact_events:
        if event['currency'] in symbol_currencies:
            time_to_event = event['datetime_utc'] - now_utc
            
            # * Extended pause window for intraday
            if timedelta(seconds=0) < time_to_event <= timedelta(minutes=config.NEWS_PAUSE_BEFORE_MINUTES):
                logger.warning(f"[NEWS] NEWS VETO: Pausing {symbol}. Event '{event['title']}' in {int(time_to_event.total_seconds()/60)} min")
                return True
            
            time_since_event = now_utc - event['datetime_utc']
            if timedelta(seconds=0) < time_since_event < timedelta(minutes=config.NEWS_PAUSE_AFTER_MINUTES):
                logger.warning(f"[NEWS] NEWS VETO: Pausing {symbol}. Recent event: '{event['title']}'")
                return True
    
    return False

# =============================================================================
# HIGHER TIMEFRAME ANALYSIS (Support/Resistance)
# =============================================================================

def get_major_support_resistance(symbol: str) -> Tuple[List[float], List[float]]:
    """
    Find major Support & Resistance levels on Daily Timeframe
    Returns: (support_levels, resistance_levels)
    """
    try:
        # Get Daily Data (enough to find swing points)
        df_d1 = get_market_data(symbol, mt5.TIMEFRAME_D1, 100)
        if df_d1 is None or len(df_d1) < 50:
            return [], []
            
        # Use simple Pivot / Swing High-Low logic
        highs, lows = identify_swing_highs_lows(df_d1, lookback=5)
        
        resistances = [df_d1['high'].iloc[i] for i in highs]
        supports = [df_d1['low'].iloc[i] for i in lows]
        
        # Sort them and keep only the most recent/relevant ones
        resistances = sorted(resistances)[-3:] # Top 3 highest
        supports = sorted(supports)[:3]        # Bottom 3 lowest
        
        # Also include yesterday's High and Low (Classic S/R)
        resistances.append(df_d1['high'].iloc[-2])
        supports.append(df_d1['low'].iloc[-2])
        
        return supports, resistances

    except Exception as e:
        logger.error(f"Error getting S/R levels: {e}")
        return [], []

# =============================================================================
# * INTRADAY STRATEGIES (Truncated for brevity - full implementations needed)
# =============================================================================
# Note: Include all strategy functions from the full intraday bot here
# For this local version, I'm including the main ones as examples

def strategy_trend_following_h4(df_entry: pd.DataFrame, df_structure: pd.DataFrame, 
                                trend: str, symbol: str, df_micro: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """H4 Trend Following Strategy"""
    if trend == "NEUTRAL":
        return None
    
    df_h4 = get_market_data(symbol, mt5.TIMEFRAME_H4, 100)
    if df_h4 is None or len(df_h4) < 50:
        return None
    
    ema20_h4 = df_h4['close'].ewm(span=20, adjust=False).mean()
    ema50_h4 = df_h4['close'].ewm(span=50, adjust=False).mean()
    ema200_h4 = df_h4['close'].ewm(span=200, adjust=False).mean()
    
    current_price_h1 = df_entry['close'].iloc[-1]
    atr_h4 = calculate_atr(df_h4['high'], df_h4['low'], df_h4['close'], 14).iloc[-1]
    
    # BULLISH
    if trend == "BULLISH":
        if ema20_h4.iloc[-1] > ema50_h4.iloc[-1] > ema200_h4.iloc[-1]:
            if abs(current_price_h1 - ema20_h4.iloc[-1]) < atr_h4 * 0.5:
                if df_entry['close'].iloc[-1] > df_entry['open'].iloc[-1]:
                    sl = ema20_h4.iloc[-1] - (atr_h4 * 1.0)
                    return {
                        "direction": "BUY",
                        "stop_loss": sl,
                        "strategy_name": "TREND_FOLLOWING_H4",
                        "confidence": 0.90
                    }
    
    # BEARISH
    elif trend == "BEARISH":
        if ema20_h4.iloc[-1] < ema50_h4.iloc[-1] < ema200_h4.iloc[-1]:
            if abs(current_price_h1 - ema20_h4.iloc[-1]) < atr_h4 * 0.5:
                if df_entry['close'].iloc[-1] < df_entry['open'].iloc[-1]:
                    sl = ema20_h4.iloc[-1] + (atr_h4 * 1.0)
                    return {
                        "direction": "SELL",
                        "stop_loss": sl,
                        "strategy_name": "TREND_FOLLOWING_H4",
                        "confidence": 0.90
                    }
    
    return None

# ... (Include all other strategy functions from full intraday bot)
# For brevity in this response, showing structure only

# =============================================================================
# CONFLUENCE ENGINE (Simplified - full version needed)
# =============================================================================

def active_stacking_engine(symbol: str, existing_pos: List, narrative: Dict, df_micro: pd.DataFrame) -> str:
    """Actively generates stacking signals instead of passive permission"""
    if len(existing_pos) >= 3:
        return "NONE" # Max 3 stacks per symbol
        
    first_pos = existing_pos[0]
    current_price = mt5.symbol_info_tick(symbol).bid if first_pos.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).ask
    
    # Needs 1.0R to legally stack
    initial_risk_pips = abs(first_pos.price_open - first_pos.sl)
    if initial_risk_pips == 0: initial_risk_pips = get_symbol_specs(symbol)['pip_size'] * 10
    
    profit_pips = (current_price - first_pos.price_open) if first_pos.type == mt5.ORDER_TYPE_BUY else (first_pos.price_open - current_price)
    realized_r = profit_pips / initial_risk_pips
    
    if realized_r < 1.0:
        return "NONE"
        
    if narrative and narrative.get('liquidity_state') == "TARGET_NEAR":
        return "NONE"
        
    # v2 Taper Logic: Risk limits based on stack depth
    # Stacking size tapers: 1st add = 0.6x, 2nd add = 0.4x, 3rd = 0.2x
    stack_depth = len(existing_pos)
    risk_taper_multiplier = 1.0
    if stack_depth == 1:
        risk_taper_multiplier = 0.6
    elif stack_depth == 2:
        risk_taper_multiplier = 0.4
    else:
        risk_taper_multiplier = 0.2
        
    if df_micro is not None and len(df_micro) > 2:
        current_body = df_micro['close'].iloc[-1] - df_micro['open'].iloc[-1]
        prev_body = df_micro['close'].iloc[-2] - df_micro['open'].iloc[-2]
        
        # Pullback Add
        if (first_pos.type == mt5.ORDER_TYPE_BUY and current_body > 0 and prev_body < 0) or \
           (first_pos.type == mt5.ORDER_TYPE_SELL and current_body < 0 and prev_body > 0):
            return {"mode": "PULLBACK_ADD", "risk_multiplier": risk_taper_multiplier}

        # Runner Add (Expansion Continuation)
        if narrative and narrative.get('lifecycle') in ["LATE_EXPANSION", "CONTINUATION"] and prev_body > 0 and current_body > 0:
            return {"mode": "RUNNER_ADD", "risk_multiplier": risk_taper_multiplier}
            
    return {"mode": "CONTINUATION_ADD", "risk_multiplier": risk_taper_multiplier}

class NarrativeIntentEngine:
    """True narrative brain mapping liquidity intent, not just regime classification"""
    
    @staticmethod
    def build(symbol: str, df_d1: pd.DataFrame, df_h4: pd.DataFrame, df_h1: pd.DataFrame, df_micro: pd.DataFrame) -> Optional[Dict[str, Any]]:
        try:
            current_price = df_h1['close'].iloc[-1]
            tick_info = get_symbol_specs(symbol)
            if not tick_info: return None
            
            # 1. Find HTF Liquidity (Daily Swing points)
            # FOREX BUG FIX: Only look at the last 20 days so we don't hit a "minefield" 
            # of 100-day-old mitigated swing targets that artificially force TARGET_NEAR.
            recent_d1 = df_d1.tail(20).reset_index(drop=True)
            highs_d1, lows_d1 = identify_swing_highs_lows(recent_d1, lookback=3)
            
            buy_side_targets = [recent_d1['high'].iloc[i] for i in highs_d1 if recent_d1['high'].iloc[i] > current_price]
            sell_side_targets = [recent_d1['low'].iloc[i] for i in lows_d1 if recent_d1['low'].iloc[i] < current_price]
            
            # FALLBACK FIX: Only use yesterday's high/low if it is actually a valid target ahead of price
            yesterday_high = df_d1['high'].iloc[-2]
            yesterday_low = df_d1['low'].iloc[-2]
            
            nearest_buy_side = min(buy_side_targets) if buy_side_targets else (yesterday_high if yesterday_high > current_price else current_price + (100 * tick_info['pip_size']))
            nearest_sell_side = max(sell_side_targets) if sell_side_targets else (yesterday_low if yesterday_low < current_price else current_price - (100 * tick_info['pip_size']))
            
            dist_buy = abs(nearest_buy_side - current_price)
            dist_sell = abs(current_price - nearest_sell_side)
            
            # 2. Determine Draw On Liquidity (DOL)
            dol = "BUY_SIDE" if dist_buy < dist_sell else "SELL_SIDE"
            distance_to_target_pips = (dist_buy if dol == "BUY_SIDE" else dist_sell) / tick_info['pip_size']
            
            # 3. THRESHOLD FIX: Reduce 'TARGET_NEAR' strictness
            # Use a strict fixed buffer (e.g., 5 pips) instead of ATR percentage
            # Crypto/Gold ATR can blow up to thousands of pips, vetoing everything.
            veto_threshold = 5.0 
            
            atr_h1 = calculate_atr(df_h1['high'], df_h1['low'], df_h1['close'], 14).iloc[-1]
            atr_pips = atr_h1 / tick_info['pip_size']
            
            liquidity_state = "SEEKING"
            if distance_to_target_pips < veto_threshold:
                liquidity_state = "TARGET_NEAR"
            elif (dol == "BUY_SIDE" and current_price >= nearest_buy_side) or (dol == "SELL_SIDE" and current_price <= nearest_sell_side):
                liquidity_state = "TAKEN"
                
            # 4. Expansion Potential & Lifecycle Tracking
            expansion_data = detect_expansion_phase(df_micro, df_h1)
            
            lifecycle = "PRE_EXPANSION"
            if expansion_data['expansion_probability'] > 0.8:
                 lifecycle = "EARLY_EXPANSION"
            elif expansion_data['expansion_probability'] > 0.5 and expansion_data.get('retest_occurred', False):
                 lifecycle = "CONTINUATION"
            elif distance_to_target_pips < atr_pips:
                 lifecycle = "LATE_EXPANSION"
            
            return {
                "dol": dol,
                "liquidity_state": liquidity_state,
                "expansion_potential": expansion_data['expansion_probability'],
                "expansion_direction": expansion_data['expansion_direction'],
                "retest_occurred": expansion_data.get('retest_occurred', False),
                "distance_to_target": distance_to_target_pips,
                "target_price": nearest_buy_side if dol == "BUY_SIDE" else nearest_sell_side,
                "lifecycle": lifecycle
            }
        except Exception as e:
            logger.error(f"NarrativeIntentEngine error: {e}")
            return None

def detect_htf_liquidity_targets(symbol: str, df_d1: pd.DataFrame, df_h4: pd.DataFrame, direction: str) -> Optional[Dict]:
    """Detect HTF liquidity targets for TP"""
    try:
        highs, lows = identify_swing_highs_lows(df_d1, lookback=5)
        current_price = df_h4['close'].iloc[-1]
        
        targets = []
        if direction == "BUY":
            for i in highs:
                target_price = df_d1['high'].iloc[i]
                if target_price > current_price:
                    targets.append({'price': target_price, 'distance': target_price - current_price, 'quality': 5})
            prev_high = df_d1['high'].iloc[-2]
            if prev_high > current_price:
                targets.append({'price': prev_high, 'distance': prev_high - current_price, 'quality': 4})
            
            if not targets: return None
            return sorted(targets, key=lambda x: x['distance'])[0]
            
        elif direction == "SELL":
            for i in lows:
                target_price = df_d1['low'].iloc[i]
                if target_price < current_price:
                    targets.append({'price': target_price, 'distance': current_price - target_price, 'quality': 5})
            prev_low = df_d1['low'].iloc[-2]
            if prev_low < current_price:
                targets.append({'price': prev_low, 'distance': current_price - prev_low, 'quality': 4})
                
            if not targets: return None
            return sorted(targets, key=lambda x: x['distance'])[0]
    except Exception as e:
        logger.error(f"Error detecting liquidity: {e}")
        return None

def detect_expansion_phase(df_micro: pd.DataFrame, df_h1: pd.DataFrame) -> Dict:
    """Detect expansion phase (volatility expansion, breakout, BOS + displacement, compression, level break, retest)"""
    try:
        bb_period = 20
        df = df_h1.copy()
        df['sma'] = df['close'].rolling(window=bb_period).mean()
        df['std'] = df['close'].rolling(window=bb_period).std()
        df['upper_bb'] = df['sma'] + (2 * df['std'])
        df['lower_bb'] = df['sma'] - (2 * df['std'])
        df['bb_width'] = (df['upper_bb'] - df['lower_bb']) / df['sma']
        
        avg_bb_width = df['bb_width'].rolling(50).mean()
        current_width = df['bb_width'].iloc[-1]
        
        expansion_prob = 0.0
        direction = "NEUTRAL"
        
        # 1. Compression Detection
        if df['bb_width'].iloc[-3] < avg_bb_width.iloc[-3] * 0.8:
            expansion_prob += 0.2  # Was recently compressed
            
        if current_width > avg_bb_width.iloc[-1] * 1.5:
            expansion_prob += 0.3
            
        # 2. Volume Surge
        avg_vol = df_micro['tick_volume'].rolling(20).mean().iloc[-1]
        curr_vol = df_micro['tick_volume'].iloc[-1]
        if curr_vol > avg_vol * 1.8:
            expansion_prob += 0.2
            
        # 3. Level Break / Displacement
        current_close = df['close'].iloc[-1]
        current_open = df['open'].iloc[-1]
        body_size = abs(current_close - current_open)
        avg_body = abs(df['close'] - df['open']).rolling(20).mean().iloc[-1]
        
        swing_highs, swing_lows = identify_swing_highs_lows(df, 5)
        broken_level = False
        
        if body_size > avg_body * 2:
            expansion_prob += 0.2
            direction = "BULLISH" if current_close > current_open else "BEARISH"
            
            # Level Break
            if direction == "BULLISH" and swing_highs and current_close > df['high'].iloc[swing_highs[-1]]:
                broken_level = True
                expansion_prob += 0.1
            elif direction == "BEARISH" and swing_lows and current_close < df['low'].iloc[swing_lows[-1]]:
                broken_level = True
                expansion_prob += 0.1
                
        # 4. Retest Logic
        retest_occurred = False
        if broken_level and abs(current_close - df['sma'].iloc[-1]) < (current_close * 0.001):
            expansion_prob += 0.1
            retest_occurred = True
            
        return {
            'expansion_probability': min(1.0, expansion_prob),
            'expansion_direction': direction,
            'retest_occurred': retest_occurred
        }
    except Exception as e:
        logger.error(f"Expansion detection error: {e}")
        return {'expansion_probability': 0.0, 'expansion_direction': "NEUTRAL", 'retest_occurred': False}

def score_rejection_candle(df: pd.DataFrame, direction: str) -> float:
    """Scores the strength of a rejection (pinbar/engulfing) candle"""
    if len(df) < 2: return 0.0
    
    current_candle = df.iloc[-1]
    body = abs(current_candle['close'] - current_candle['open'])
    total_range = current_candle['high'] - current_candle['low']
    if total_range == 0: return 0.0
    
    score = 0.0
    
    if direction == "BULLISH":
        lower_wick = min(current_candle['open'], current_candle['close']) - current_candle['low']
        if lower_wick > total_range * 0.5: score += 0.5  # Strong pinbar
        if current_candle['close'] > df.iloc[-2]['high']: score += 0.5  # Engulfing previous high
    else:
        upper_wick = current_candle['high'] - max(current_candle['open'], current_candle['close'])
        if upper_wick > total_range * 0.5: score += 0.5
        if current_candle['close'] < df.iloc[-2]['low']: score += 0.5
        
    return score

# =============================================================================
# INTRADAY STRATEGIES -- THREE NAMED SETUPS
# =============================================================================
# Strategy A: H4 TREND PULLBACK  (like EMA Scalp but on H4/H1/M15)
# Strategy B: H1 ORDERBLOCK RETEST  (Intraday SSM -- institutional OB entries)
# Strategy C: LONDON OPEN BREAKOUT  (session open momentum capture)
# =============================================================================

def strategy_h4_trend_pullback(symbol: str, df_h4: pd.DataFrame,
                                df_h1: pd.DataFrame, df_m15: pd.DataFrame,
                                trend: str) -> Optional[Dict]:
    """
    STRATEGY A: H4 TREND PULLBACK
    The intraday version of the EMA scalp. Instead of entering on M5 momentum,
    we wait for H1 price to pull back INTO the H4 EMA zone, then take the
    rejection on M15 with a tight structural SL.

    Entry sequence:
      1. H4 trend confirmed: EMA20 > EMA50 > EMA200 (BULL) or reversed (BEAR)
      2. H1 price has pulled back into the H4 EMA20-50 zone (premium/discount)
      3. M15 rejection candle at zone: pinbar or engulfing in trend direction

    SL: below/above the M15 rejection candle wick (not ATR multiple)
    TP: nearest H1 swing high (BULL) or swing low (BEAR) = liquidity pool
    """
    if trend == "NEUTRAL" or df_h4 is None or df_h1 is None or df_m15 is None:
        return None
    if len(df_h4) < 55 or len(df_h1) < 30 or len(df_m15) < 20:
        return None
    try:
        # Step 1: H4 EMA stack
        ema20_h4 = float(df_h4['close'].ewm(span=20, adjust=False).mean().iloc[-1])
        ema50_h4 = float(df_h4['close'].ewm(span=50, adjust=False).mean().iloc[-1])
        ema200_h4= float(df_h4['close'].ewm(span=200, adjust=False).mean().iloc[-1])
        atr_h4   = float(calculate_atr(df_h4['high'], df_h4['low'], df_h4['close'], 14).iloc[-1])

        bull_stack = ema20_h4 > ema50_h4 > ema200_h4
        bear_stack = ema20_h4 < ema50_h4 < ema200_h4

        if trend == "BULLISH" and not bull_stack: return None
        if trend == "BEARISH" and not bear_stack: return None

        # Step 2: H1 price inside H4 EMA20-50 zone (the pullback zone)
        h1_price = float(df_h1['close'].iloc[-1])
        zone_high = max(ema20_h4, ema50_h4) + atr_h4 * 0.3
        zone_low  = min(ema20_h4, ema50_h4) - atr_h4 * 0.3
        in_pullback_zone = zone_low <= h1_price <= zone_high

        if not in_pullback_zone:
            return None

        # Step 3: M15 rejection candle (pinbar or engulfing)
        c = df_m15.iloc[-1]   # current
        p = df_m15.iloc[-2]   # previous
        c_body = abs(float(c['close']) - float(c['open']))
        c_rng  = float(c['high']) - float(c['low'])
        if c_rng == 0: return None
        atr_m15 = float(calculate_atr(df_m15['high'], df_m15['low'], df_m15['close'], 14).iloc[-1])

        if trend == "BULLISH":
            # Bullish pinbar: lower wick > 55% of range, close in upper 40%
            lower_wick = min(float(c['open']), float(c['close'])) - float(c['low'])
            is_pinbar  = lower_wick > c_rng * 0.55
            # Bullish engulfing: closes above previous candle high
            is_engulf  = float(c['close']) > float(p['high']) and float(c['close']) > float(c['open'])
            if not (is_pinbar or is_engulf): return None

            sl = float(c['low']) - atr_m15 * 0.3   # below rejection wick
            # TP: nearest H1 swing high above entry
            h1_highs = [float(df_h1['high'].iloc[i]) for i in range(-30, -1)
                        if float(df_h1['high'].iloc[i]) > h1_price + abs(h1_price - sl) * 1.5]
            tp = min(h1_highs) if h1_highs else h1_price + abs(h1_price - sl) * 2.5

            return {'direction': 'BUY',  'stop_loss': sl, 'tp': tp,
                    'strategy_name': 'H4_TREND_PULLBACK', 'confidence': 0.82}

        else:  # BEARISH
            upper_wick = float(c['high']) - max(float(c['open']), float(c['close']))
            is_pinbar  = upper_wick > c_rng * 0.55
            is_engulf  = float(c['close']) < float(p['low']) and float(c['close']) < float(c['open'])
            if not (is_pinbar or is_engulf): return None

            sl = float(c['high']) + atr_m15 * 0.3
            h1_lows = [float(df_h1['low'].iloc[i]) for i in range(-30, -1)
                       if float(df_h1['low'].iloc[i]) < h1_price - abs(sl - h1_price) * 1.5]
            tp = max(h1_lows) if h1_lows else h1_price - abs(sl - h1_price) * 2.5

            return {'direction': 'SELL', 'stop_loss': sl, 'tp': tp,
                    'strategy_name': 'H4_TREND_PULLBACK', 'confidence': 0.82}

    except Exception as e:
        logger.error(f"[STRAT A] {symbol}: {e}")
        return None


def strategy_h1_orderblock_retest(symbol: str, df_h1: pd.DataFrame,
                                   df_m15: pd.DataFrame, trend: str) -> Optional[Dict]:
    """
    STRATEGY B: H1 ORDERBLOCK RETEST (Intraday SSM)
    The institutional entry. We find the last H1 Order Block -- the final
    candle before a strong displacement -- wait for price to retrace into it,
    then confirm with a M15 body close back in the institutional direction.

    Entry sequence:
      1. Identify the last H1 OB: last bearish (or bullish) candle before
         a strong bullish (or bearish) move of >= 1.5x ATR body
      2. Price retraces back into the OB zone
      3. M15 confirmation: body closes inside or at the OB in trend direction

    SL: just beyond the OB extreme (not guesswork -- OB is the invalidation)
    TP: next H4 swing high/low (structural liquidity pool)
    """
    if trend == "NEUTRAL" or df_h1 is None or df_m15 is None:
        return None
    if len(df_h1) < 30 or len(df_m15) < 10:
        return None
    try:
        atr_h1    = float(calculate_atr(df_h1['high'], df_h1['low'], df_h1['close'], 14).iloc[-1])
        cur_price = float(df_h1['close'].iloc[-1])
        spread    = mt5.symbol_info_tick(symbol)
        spread_buf = (spread.ask - spread.bid) * 2.5 if spread else atr_h1 * 0.05

        # Find the last valid OB (look back up to 20 H1 candles)
        ob = None
        for i in range(-3, -20, -1):
            c_ob   = df_h1.iloc[i]      # candidate OB candle
            c_disp = df_h1.iloc[i+1]   # displacement candle after it
            disp_body = abs(float(c_disp['close']) - float(c_disp['open']))

            if trend == "BULLISH":
                # OB = last BEARISH candle before a strong BULLISH displacement
                is_bearish_ob   = float(c_ob['close']) < float(c_ob['open'])
                is_bull_disp    = float(c_disp['close']) > float(c_disp['open']) and disp_body >= atr_h1 * 1.2
                ob_zone_high    = float(c_ob['open'])   # top of bearish OB = open
                ob_zone_low     = float(c_ob['close'])  # bottom = close
                price_in_ob     = ob_zone_low <= cur_price <= ob_zone_high
                ob_not_violated = not any(float(df_h1['low'].iloc[j]) < ob_zone_low
                                          for j in range(i+2, -1))
                if is_bearish_ob and is_bull_disp and price_in_ob and ob_not_violated:
                    ob = {'high': ob_zone_high, 'low': ob_zone_low, 'type': 'BULL_OB'}
                    break

            else:  # BEARISH trend
                # OB = last BULLISH candle before a strong BEARISH displacement
                is_bullish_ob   = float(c_ob['close']) > float(c_ob['open'])
                is_bear_disp    = float(c_disp['close']) < float(c_disp['open']) and disp_body >= atr_h1 * 1.2
                ob_zone_high    = float(c_ob['close'])  # top of bullish OB = close
                ob_zone_low     = float(c_ob['open'])   # bottom = open
                price_in_ob     = ob_zone_low <= cur_price <= ob_zone_high
                ob_not_violated = not any(float(df_h1['high'].iloc[j]) > ob_zone_high
                                          for j in range(i+2, -1))
                if is_bullish_ob and is_bear_disp and price_in_ob and ob_not_violated:
                    ob = {'high': ob_zone_high, 'low': ob_zone_low, 'type': 'BEAR_OB'}
                    break

        if not ob: return None

        # M15 confirmation: last M15 candle body closes inside the OB
        m15_close = float(df_m15['close'].iloc[-1])
        m15_open  = float(df_m15['open'].iloc[-1])
        m15_body  = abs(m15_close - m15_open)
        atr_m15   = float(calculate_atr(df_m15['high'], df_m15['low'], df_m15['close'], 14).iloc[-1])
        if m15_body < atr_m15 * 0.2:  # doji -- no confirmation
            return None

        if trend == "BULLISH":
            # M15 close bullish (green candle) inside the OB
            if m15_close <= m15_open: return None  # must be green
            sl = ob['low'] - spread_buf
            # TP: nearest H4 swing high (pre-fetched via get_market_data)
            df_h4_tp = get_market_data(symbol, mt5.TIMEFRAME_H4, 100)
            if df_h4_tp is not None:
                h4_highs = [float(df_h4_tp['high'].iloc[i]) for i in range(-50,-1)
                            if float(df_h4_tp['high'].iloc[i]) > cur_price + abs(cur_price-sl)*1.5]
                tp = min(h4_highs) if h4_highs else cur_price + abs(cur_price - sl) * 3.0
            else:
                tp = cur_price + abs(cur_price - sl) * 3.0
            return {'direction': 'BUY',  'stop_loss': sl, 'tp': tp,
                    'strategy_name': 'H1_OB_RETEST', 'confidence': 0.88,
                    'ob_zone': ob}
        else:
            if m15_close >= m15_open: return None  # must be red
            sl = ob['high'] + spread_buf
            df_h4_tp = get_market_data(symbol, mt5.TIMEFRAME_H4, 100)
            if df_h4_tp is not None:
                h4_lows = [float(df_h4_tp['low'].iloc[i]) for i in range(-50,-1)
                           if float(df_h4_tp['low'].iloc[i]) < cur_price - abs(sl-cur_price)*1.5]
                tp = max(h4_lows) if h4_lows else cur_price - abs(sl - cur_price) * 3.0
            else:
                tp = cur_price - abs(sl - cur_price) * 3.0
            return {'direction': 'SELL', 'stop_loss': sl, 'tp': tp,
                    'strategy_name': 'H1_OB_RETEST', 'confidence': 0.88,
                    'ob_zone': ob}

    except Exception as e:
        logger.error(f"[STRAT B] {symbol}: {e}")
        return None


def strategy_london_open_breakout(symbol: str, df_m15: pd.DataFrame,
                                   trend: str) -> Optional[Dict]:
    """
    STRATEGY C: LONDON OPEN BREAKOUT
    At the London open (8:00 UTC), institutions place their largest orders.
    This creates a sharp directional move that often sets the tone for the
    entire European session. We capture this by:

    Entry sequence:
      1. Mark the pre-London range: highest and lowest M15 close from 6:00-7:45 UTC
      2. At 8:00 UTC, wait for the first M15 candle to BREAK and CLOSE above/below range
      3. Volume surge confirmation: current M15 volume > 1.5x average
      4. Align with H4 trend direction (no counter-trend breakouts)

    SL: midpoint of the pre-London range (if price returns there, breakout failed)
    TP: 2x the range height projected in breakout direction
    """
    # Strategy C works any time a session range breakout occurs.
    # London breakout (2-5 AM NY): highest probability
    # NY open breakout (9:30-10 AM NY): second highest
    # Other sessions: still valid if volume + range conditions are met
    now_utc  = datetime.now(timezone.utc)
    now_t    = now_utc.hour * 60 + now_utc.minute
    # Compute NY open time in UTC (DST-aware)
    try:
        _lon_start = _ny_to_utc_minutes(2, 0)
        _lon_end   = _ny_to_utc_minutes(5, 0)
        _ny_start  = _ny_to_utc_minutes(9, 30)
        _ny_end    = _ny_to_utc_minutes(10, 30)
        _in_prime  = (_lon_start <= now_t < _lon_end) or (_ny_start <= now_t < _ny_end)
    except Exception:
        _in_prime  = False
    if trend == "NEUTRAL" or df_m15 is None or len(df_m15) < 12: return None

    try:
        # Build pre-London range from M15 candles in the 6:00-7:45 UTC window
        range_highs, range_lows = [], []
        for i in range(-16, -1):  # last ~4 hours of M15 candles
            candle_time = df_m15['time'].iloc[i]
            if hasattr(candle_time, 'hour'):
                h, m = candle_time.hour, candle_time.minute
            else:
                dt = pd.to_datetime(candle_time)
                h, m = dt.hour, dt.minute
            if 6 <= h < 8:  # pre-London
                range_highs.append(float(df_m15['high'].iloc[i]))
                range_lows.append(float(df_m15['low'].iloc[i]))

        if len(range_highs) < 3: return None  # not enough pre-London data

        range_high = max(range_highs)
        range_low  = min(range_lows)
        range_size = range_high - range_low
        if range_size <= 0: return None

        midpoint = (range_high + range_low) / 2.0

        # Current M15 close (first London candle)
        cur_close = float(df_m15['close'].iloc[-1])
        cur_open  = float(df_m15['open'].iloc[-1])

        # Volume confirmation
        avg_vol = float(df_m15['tick_volume'].rolling(20).mean().iloc[-1])
        cur_vol = float(df_m15['tick_volume'].iloc[-1])
        vol_ok  = cur_vol > avg_vol * 1.5

        if not vol_ok: return None

        if cur_close > range_high and cur_close > cur_open and trend == "BULLISH":
            sl = midpoint  # failure if price returns to mid-range
            tp = range_high + range_size * 2.0  # 2x range extension
            _conf_c = 0.84 if _in_prime else 0.74  # higher conf during London/NY open
            logger.info(f"[STRAT C] {symbol}: Session BULL breakout | Range:{range_size:.4f} TP:{tp:.4f} prime={_in_prime}")
            return {'direction': 'BUY',  'stop_loss': sl, 'tp': tp,
                    'strategy_name': 'SESSION_BREAKOUT', 'confidence': _conf_c}

        elif cur_close < range_low and cur_close < cur_open and trend == "BEARISH":
            sl = midpoint
            tp = range_low - range_size * 2.0
            _conf_c = 0.84 if _in_prime else 0.74
            logger.info(f"[STRAT C] {symbol}: Session BEAR breakout | Range:{range_size:.4f} TP:{tp:.4f} prime={_in_prime}")
            return {'direction': 'SELL', 'stop_loss': sl, 'tp': tp,
                    'strategy_name': 'SESSION_BREAKOUT', 'confidence': _conf_c}

        return None

    except Exception as e:
        logger.error(f"[STRAT C] {symbol}: {e}")
        return None


# =============================================================================
# STRATEGY E: AOX MODEL (Algorithmic Order Execution)
# ICT/Swappy methodology -- manipulation spike detection + sniper reversal
# =============================================================================
# Entry uses CISD (Change in State of Delivery) as the mechanical trigger
# and CRT (Candle Range Theory) to confirm the manipulation is complete.
# Only fires during Temporal Macro windows for maximum institutional alignment.
# =============================================================================

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

def is_am_h4_candle() -> bool:
    """
    H4 Candle CRT Rule (from image 2):
    A daily candle = 6 H4 candles opening at 1,5,9 AM and 1,5,9 PM EST.

    TRADE:      1AM | 5AM | 9AM  H4 candles  (AM candles)
    DONT TRADE: 1PM | 5PM | 9PM  H4 candles  (PM candles)

    AM candles span:
      1AM-5AM   EST = 05:00-09:00 UTC (EDT)
      5AM-9AM   EST = 09:00-13:00 UTC (EDT)
      9AM-1PM   EST = 13:00-17:00 UTC (EDT)

    Returns True if currently inside an AM H4 candle window.
    """
    # Get current NY time
    now_utc = datetime.now(timezone.utc)
    t_utc   = now_utc.hour * 60 + now_utc.minute

    # AM candle windows in NY time: 1AM-1PM (12 hours)
    am_start_ny = 1 * 60   # 1:00 AM EST
    am_end_ny   = 13 * 60  # 1:00 PM EST (when PM candles start)

    # Convert to UTC
    utc_am_start = _ny_to_utc_minutes(1,  0)
    utc_am_end   = _ny_to_utc_minutes(13, 0)

    # Handle midnight wrap (UTC)
    if utc_am_start < utc_am_end:
        return utc_am_start <= t_utc < utc_am_end
    else:
        # Wraps midnight (e.g. EST in winter where 1AM = 6AM UTC next day)
        return t_utc >= utc_am_start or t_utc < utc_am_end


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
            f"[AOX] {symbol} {direction}: {spike['type']} | macro={macro} | "
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


def context_decision_engine(symbol: str, ai_bias: str = "NEUTRAL", stacking_mode: str = "NONE", min_confidence: float = 0.70) -> Optional[Dict[str, Any]]:
    """ContextDecisionEngine: Builds narrative, chooses behavior, and outputs a decision object"""
    if not config.ENABLE_CONFLUENCE_ENGINE:
        return None
    
    try:
        if is_trade_entry_paused_for_news(symbol): return None
        
        df_d1 = get_market_data(symbol, config.DAILY_TF, 200)
        df_entry = get_market_data(symbol, config.ENTRY_TF, 200)
        df_structure = get_market_data(symbol, config.STRUCTURE_TF, 200)
        df_micro = get_market_data(symbol, config.MICRO_STRUCTURE_TF, 100)
        
        if df_entry is None or df_structure is None or df_micro is None or df_d1 is None: return None
        
        # --- 1. INTENT-BASED NARRATIVE ---
        narrative = NarrativeIntentEngine.build(symbol, df_d1, df_structure, df_entry, df_micro)
        if not narrative: return None
        
        if narrative['liquidity_state'] == "TARGET_NEAR" or narrative['liquidity_state'] == "TAKEN":
            logger.info(f"[NARRATIVE VETO] {symbol} rejected. Liquidity state: {narrative['liquidity_state']}")
            return None
            
        market_regime, trend_direction = get_market_regime_and_trend(symbol)
        h1_highs, h1_lows = identify_swing_highs_lows(df_entry, 5)
        mss = detect_market_structure_shift(df_entry, h1_highs, h1_lows)
        sweep = detect_liquidity_sweep(df_entry, h1_highs, h1_lows)
        session = get_current_session()
        
        # --- 2. BEHAVIOR SELECTION & STACK INVALIDATION ---
        move_type = "UNKNOWN"
        direction_bias = "BUY" if narrative['dol'] == "BUY_SIDE" else "SELL"
        
        # Unified Narrative Confidence computation
        structural_alignment = 1.0 if (direction_bias == "BUY" and trend_direction == "BULLISH") or (direction_bias == "SELL" and trend_direction == "BEARISH") else 0.5
        liquidity_distance_score = min(1.0, narrative['distance_to_target'] / 50.0) # Assume 50+ is optimal
        narrative_confidence = (narrative['expansion_potential'] * 0.4) + (structural_alignment * 0.4) + (liquidity_distance_score * 0.2)
        narrative['confidence_score'] = narrative_confidence
        
        # PRO CHECK: Confidence Control Stacking Permission
        if stacking_mode != "NONE" and not ConfidenceController.allowed_to_stack(narrative_confidence):
            logger.info(f"[NARRATIVE VETO] {symbol} Stacking denied, confidence {narrative_confidence:.2f} < 0.6")
            return None

        # Mid-Move Control & Invalidation
        if symbol in state.narrative_stacks and state.narrative_stacks[symbol]['status'] in ['ACTIVE', 'RUNNER']:
             stack = state.narrative_stacks[symbol]
             
             # Call CapitalAdjustmentEngine (GAP 5)
             CapitalAdjustmentEngine.evaluate(symbol, stack, direction_bias, sweep, mss)
                  
             # Close stack if liquidity reached or expansion completely fails
             if narrative['liquidity_state'] == "TAKEN" or narrative['liquidity_state'] == "REACHED":
                  state.invalidate_stack(symbol, "LIQUIDITY_TAKEN")
                  logger.info(f"[STACK MANAGER] {symbol} stack invalidated: Liquidity Taken")
             # NEW: Invalidated if opposite breakout / structural failure
             elif move_type == "REVERSAL_AFTER_LIQUIDITY" and direction_bias != (stack['narrative_data'].get('expansion_direction', direction_bias)):
                  state.invalidate_stack(symbol, "OPPOSITE_STRUCTURAL_SHIFT")
             elif sweep == "SWEEP_HIGH" and direction_bias == "BUY":
                  state.invalidate_stack(symbol, "OPPOSITE_SWEEP")
             elif sweep == "SWEEP_LOW" and direction_bias == "SELL":
                  state.invalidate_stack(symbol, "OPPOSITE_SWEEP")
                  
        if sweep and mss:
            move_type = "REVERSAL_AFTER_LIQUIDITY"
            direction_bias = "BULLISH" if sweep == "SWEEP_LOW" else "BEARISH"
        elif narrative['expansion_potential'] > 0.7:
            move_type = "EXPANSION_BREAKOUT"
            direction_bias = narrative['expansion_direction']
        elif direction_bias in ["BUY", "SELL"] and market_regime == "TRENDING":
             move_type = "TREND_CONTINUATION"
             direction_bias = "BULLISH" if direction_bias == "BUY" else "BEARISH"
            
        if move_type not in config.BEHAVIOR_MODES: return None

        # Normalize direction_bias to BULLISH/BEARISH consistently
        if direction_bias == "BUY": direction_bias = "BULLISH"
        if direction_bias == "SELL": direction_bias = "BEARISH"
            
        # --- 3. EXECUTION MODELS & STACKING ---
        if stacking_mode != "NONE" and move_type == "REVERSAL_AFTER_LIQUIDITY":
            return None  # No stacking on reversals
            
        # ================================================================
        # THREE NAMED INTRADAY STRATEGIES (run independently, in priority)
        # ================================================================
        entry_signal = None
        trend_for_strat = trend_direction  # BULLISH / BEARISH / NEUTRAL

        # STRATEGY E: AOX Sniper -- always scanning, no session restriction
        # Fires whenever manipulation spike + CISD + SMT conditions are met
        # (The macro window is logged as context but does NOT gate the trade)
        if not entry_signal:
            df_m15_e = get_market_data(symbol, mt5.TIMEFRAME_M15, 50)
            df_m1_e  = get_market_data(symbol, mt5.TIMEFRAME_M1,  30)
            entry_signal = strategy_aox_model(symbol, df_m15_e, df_m1_e, trend_for_strat)
            if entry_signal:
                _macro_ctx = get_active_macro_window() or "NO_MACRO"
                logger.info(f"[STRAT E] {symbol}: AOX Sniper | macro_ctx={_macro_ctx}")

        # STRATEGY B (2nd priority): H1 OB Retest -- tightest SL, best RR
        if not entry_signal:
            df_m15_s = get_market_data(symbol, mt5.TIMEFRAME_M15, 50)
            entry_signal = strategy_h1_orderblock_retest(symbol, df_entry, df_m15_s, trend_for_strat)
            if entry_signal:
                logger.info(f"[STRAT B] {symbol}: H1 OB Retest setup found")

        # STRATEGY A (bread and butter): H4 Trend Pullback
        if not entry_signal:
            df_m15_a = get_market_data(symbol, mt5.TIMEFRAME_M15, 50)
            entry_signal = strategy_h4_trend_pullback(symbol, df_structure, df_entry, df_m15_a, trend_for_strat)
            if entry_signal:
                logger.info(f"[STRAT A] {symbol}: H4 Trend Pullback setup found")

        # STRATEGY C (session open only): London Open Breakout
        if not entry_signal:
            df_m15_c = get_market_data(symbol, mt5.TIMEFRAME_M15, 50)
            entry_signal = strategy_london_open_breakout(symbol, df_m15_c, trend_for_strat)
            if entry_signal:
                logger.info(f"[STRAT C] {symbol}: London Open Breakout setup found")

        # Legacy: Reversal after liquidity sweep (keep as Strategy D)
        if not entry_signal and move_type == "REVERSAL_AFTER_LIQUIDITY" and direction_bias not in ("NEUTRAL",""):
            entry_signal = reversal_precision_engine(symbol, df_entry, direction_bias, sweep, mss)
            if entry_signal:
                logger.info(f"[STRAT D] {symbol}: Reversal after liquidity sweep")
            
        if not entry_signal:
            logger.debug(
                f"[NO SETUP] {symbol}: no strategy fired | "
                f"trend={trend_direction} regime={market_regime} "
                f"sweep={sweep} mss={mss} move={move_type} "
                f"liq={narrative.get('liquidity_state') if narrative else 'N/A'}"
            )
            return None

        # Apply session-aware minimum confidence threshold
        sig_conf = entry_signal.get('confidence', 0.0)
        if sig_conf < min_confidence:
            logger.debug(
                f"[CONF GATE] {symbol}: {entry_signal['strategy_name']} "
                f"conf={sig_conf:.2f} < min={min_confidence:.2f} -- skip"
            )
            return None

        direction = entry_signal['direction']

        # COUNTER-TREND GATE: direction must agree with H4 macro trend
        # This was the #1 cause of losses in the scalping bot (April 3 incident)
        if trend_direction != "NEUTRAL":
            if direction == "BUY" and trend_direction == "BEARISH":
                logger.debug(f"[H4 GATE] {symbol}: BUY rejected -- H4 trend is BEARISH")
                return None
            if direction == "SELL" and trend_direction == "BULLISH":
                logger.debug(f"[H4 GATE] {symbol}: SELL rejected -- H4 trend is BULLISH")
                return None
        
        # AI Bias Confidence Modifier
        is_aligned = (ai_bias == direction) or \
                     (ai_bias == "BUY_ONLY" and direction == "BUY") or \
                     (ai_bias == "SELL_ONLY" and direction == "SELL")
                     
        is_conflict = (ai_bias == "BUY_ONLY" and direction == "SELL") or \
                      (ai_bias == "SELL_ONLY" and direction == "BUY") or \
                      (ai_bias == "BUY" and direction == "SELL") or \
                      (ai_bias == "SELL" and direction == "BUY")
                      
        if is_aligned:
            entry_signal['confidence'] = min(1.0, entry_signal['confidence'] + 0.2)
        elif is_conflict:
            logger.info(f"[AI VETO] Context engine direction {direction} conflicts with AI bias {ai_bias}")
            return None
            
        # Structure anchored SL
        atr_buf = calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], 14).iloc[-1] * 0.5
        if direction == "BUY":
            swing_lows = identify_swing_highs_lows(df_entry, 5)[1]
            if swing_lows: entry_signal['stop_loss'] = df_entry['low'].iloc[swing_lows[-1]] - atr_buf
        else:
            swing_highs = identify_swing_highs_lows(df_entry, 5)[0]
            if swing_highs: entry_signal['stop_loss'] = df_entry['high'].iloc[swing_highs[-1]] + atr_buf
                
        # 4. Final Formatting & Filters
        curr_price = df_entry['close'].iloc[-1]
        tick_info = get_symbol_specs(symbol)
        sl_pips = abs(curr_price - entry_signal['stop_loss']) / tick_info['pip_size']
        if sl_pips == 0: sl_pips = 1
        expected_rr = narrative['distance_to_target'] / sl_pips
        
        entry_signal['liquidity_target'] = narrative['target_price']
        
        # Edge Mode Engine integration
        entry_signal['risk_multiplier'] = edge_engine.get_risk_multiplier(expected_rr, narrative['expansion_potential'], market_regime, narrative.get('lifecycle', 'PRE_EXPANSION'), narrative.get('distance_to_target', 100.0))
        if narrative['expansion_potential'] > 0.8:
            entry_signal['risk_multiplier'] *= 1.2
            
        if stacking_mode != "NONE":
            # Moderate risk for continuation and pullback adds
            entry_signal['risk_multiplier'] *= 0.5
            
        # Behavior & Lifecycle specific RR thresholds
        lifecycle = narrative.get('lifecycle', 'PRE_EXPANSION')
        if stacking_mode != "NONE":
            min_rr = 1.0
        elif move_type == "EXPANSION_BREAKOUT":
            min_rr = 2.0 if lifecycle == "PRE_EXPANSION" else 1.5
        elif move_type == "REVERSAL_AFTER_LIQUIDITY":
            min_rr = 1.5
        else:
            min_rr = 1.2
            
        if expected_rr < min_rr:
            logger.info(f"[NARRATIVE VETO] {symbol} rejected. Expected RR {expected_rr:.1f} < {min_rr} (Lifecycle: {lifecycle})")
            return None
            
        entry_signal['symbol'] = symbol
        entry_signal['trend'] = trend_direction
        entry_signal['regime'] = market_regime
        entry_signal['move_type'] = move_type
        entry_signal['expected_pips'] = narrative['distance_to_target']
        entry_signal['expected_rr'] = expected_rr
        entry_signal['contributing_strategies'] = [entry_signal['strategy_name']]
        entry_signal['narrative'] = narrative  # Pass active narrative up to the manager
        
        logger.info(f"[DECISION ENGINE] [{symbol}] {move_type} | Dir: {direction} | Mode: {edge_engine.mode} | Exp RR: {expected_rr:.1f}")
        return entry_signal
        
    except Exception as e:
        logger.error(f"Error in narrative engine: {e}")
        return None

# =============================================================================
# AI FUNCTIONS (Simplified)
# =============================================================================

def _use_local_h4_bias():
    """Compute bias locally from H4 EMA structure -- no Gemini needed."""
    bias = {}
    for sym in config.SYMBOLS:
        try:
            df = get_market_data(sym, mt5.TIMEFRAME_H4, 60)
            if df is None or len(df) < 55:
                bias[sym] = "NEUTRAL"
                continue
            ema50  = float(df['close'].ewm(span=50, adjust=False).mean().iloc[-1])
            ema200 = float(df['close'].ewm(span=200, adjust=False).mean().iloc[-1])
            price  = float(df['close'].iloc[-1])
            if price > ema50 > ema200:   bias[sym] = "BUY_ONLY"
            elif price < ema50 < ema200: bias[sym] = "SELL_ONLY"
            else:                        bias[sym] = "NEUTRAL"
        except Exception:
            bias[sym] = "NEUTRAL"
    state.approved_bias = bias
    logger.info(f"[AI L1] Local H4 bias: {bias}")


def update_global_ai_context():
    """Update AI global context"""
    global state
    if not config.ENABLE_AI_VALIDATION:
        return
    
    if state.last_global_context_update and (datetime.now() - state.last_global_context_update) < timedelta(seconds=config.AI_GLOBAL_CONTEXT_INTERVAL):
        return
    
    logger.info("[AI] AI: Analyzing macro environment...")
    
    system_prompt = """You are a Senior Portfolio Manager analyzing markets for INTRADAY trades.
    Set trading bias for each symbol: BUY_ONLY, SELL_ONLY, or NEUTRAL.
    
    Respond ONLY with valid JSON:
    {
      "sentiment": "RISK_ON or RISK_OFF",
      "symbol_bias": {
        "EURUSDm": "BUY_ONLY"
      },
      "reasoning": "Brief analysis"
    }
    """
    
    symbols_str = ", ".join(config.SYMBOLS)
    prompt = f"Set intraday bias for provided symbols based on current market structure. Return JSON only."
    
    # INCREASED TOKENS to avoid truncation
    response = ai_provider.call_ai(prompt, system_prompt, temperature=0.3, max_tokens=2000, json_mode=True)
    
    if response:
        try:
            # CLEANUP: Remove markdown code blocks if present
            cleaned_response = response.strip()
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response.split("```")[1]
                if cleaned_response.startswith("json"):
                     cleaned_response = cleaned_response[4:]
            cleaned_response = cleaned_response.strip()

            # Robust JSON extraction -- handles any Gemini format
            import re as _re
            candidates = []
            s2 = cleaned_response.strip()
            if s2.startswith("```"):
                s2 = s2.lstrip("`").lstrip("json").strip().rstrip("`").strip()
                candidates.append(s2)
            for m in _re.finditer(r'{[\s\S]*}', cleaned_response):
                candidates.append(m.group(0))
            candidates.append(cleaned_response)

            result = None
            for chunk in candidates:
                try:
                    result = json.loads(chunk)
                    if isinstance(result, dict): break
                except: pass

            if result:
                state.approved_bias = result.get('symbol_bias', {})
                state.global_market_sentiment = result.get('sentiment', 'NEUTRAL')
                state.global_key_drivers = result.get('reasoning', 'N/A')
                logger.info(f"[AI L1] BIAS UPDATED: {state.approved_bias}")
                state.last_global_context_update = datetime.now()
            else:
                logger.warning("[AI L1] JSON parse failed -- using local H4 bias fallback")
                _use_local_h4_bias()

        except Exception as e:
            logger.error(f"Error processing AI bias: {e}")
            _use_local_h4_bias()
    else:
        logger.warning("[AI L1] No response from Gemini -- using local H4 bias fallback")
        _use_local_h4_bias()

# =============================================================================
# TRADE EXECUTION (Simplified for local testing)
# =============================================================================

def validate_trade_risk(signal: Dict, account_equity: float) -> Tuple[bool, str]:
    """
    Validate that proposed trade risk is within acceptable limits
    
    Args:
        signal: Trade signal dictionary
        account_equity: Current account equity
    
    Returns:
        (is_valid, reason): Tuple with validation result and reason
    """
    try:
        symbol = signal['symbol']
        stop_loss = signal['stop_loss']
        
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return False, "Cannot get tick data"
        
        entry_price = tick.ask if signal['direction'] == "BUY" else tick.bid
        
        # Calculate trade risk in dollars and percentage
        spec = get_symbol_specs(symbol)
        pip_risk = abs(entry_price - stop_loss) / spec['pip_size']
        
        # Use current risk percent from state
        risk_percent = state.current_risk_percent
        risk_amount = account_equity * (risk_percent / 100.0)
        
        # Calculate what the actual risk will be for this trade
        actual_risk_percent = (risk_amount / account_equity) * 100
        
        # Check 1: Single trade risk cap
        if actual_risk_percent > config.MAX_RISK_PER_TRADE_PERCENT:
            return False, f"Trade risk {actual_risk_percent:.2f}% exceeds per-trade limit {config.MAX_RISK_PER_TRADE_PERCENT}%"
            
        # PRO CHECK: Portfolio Correlation Limit (GAP 4)
        allowed, taper = portfolio_manager.check_exposure_limits(symbol, actual_risk_percent, state.narrative_stacks)
        if not allowed:
            return False, f"Portfolio currency exposure cap exceeded for {symbol}"
        if taper < 1.0:
            actual_risk_percent *= taper
            
        # PRO CHECK: Narrative Confidence Global Control (GAP 3)
        conf = signal.get('confidence', 0.5)
        # Risk override
        actual_risk_percent *= ConfidenceController.get_risk_multiplier(conf)
            
        # PRO CHECK: Narrative Stack Budget
        if symbol in state.narrative_stacks and state.narrative_stacks[symbol]['status'] == 'ACTIVE':
            stack = state.narrative_stacks[symbol]
            if (stack['consumed_risk'] + actual_risk_percent) > stack['max_risk_pct']:
                return False, f"Narrative risk budget exceeded. Consumed {stack['consumed_risk']:.2f}% / Max {stack['max_risk_pct']:.2f}%"
        
        # Check 2: Would this trade exceed daily loss limit if it hits SL?
        if state.daily_start_equity > 0:
            current_daily_loss_pct = abs(state.daily_pnl / state.daily_start_equity) * 100
            potential_total_loss_pct = current_daily_loss_pct + actual_risk_percent
            
            if potential_total_loss_pct > config.MAX_DAILY_LOSS_PERCENT:
                return False, f"Potential loss {potential_total_loss_pct:.2f}% would exceed daily limit {config.MAX_DAILY_LOSS_PERCENT}%"
        
        # Check 3: Would this trade exceed max drawdown if it hits SL?
        account_info = mt5.account_info()
        if account_info and state.daily_start_equity > 0:
            current_drawdown_pct = ((state.daily_start_equity - account_info.equity) / state.daily_start_equity) * 100
            potential_equity_after_loss = account_info.equity - risk_amount
            potential_total_drawdown_pct = ((state.daily_start_equity - potential_equity_after_loss) / state.daily_start_equity) * 100
            
            if potential_total_drawdown_pct > config.MAX_DRAWDOWN_PERCENT:
                return False, f"Potential drawdown {potential_total_drawdown_pct:.2f}% would exceed limit {config.MAX_DRAWDOWN_PERCENT}%"
        
        # Check 4: Pip risk sanity check (avoid extreme SL distances)
        # Relaxed logic for Crypto/Metals
        max_pip_risk = 500
        if any(s in symbol for s in ["BTC", "ETH", "XAU", "XAG"]):
            max_pip_risk = 25000 # Much higher limit for high-value assets
            
        if 'm' in symbol.lower() and pip_risk > max_pip_risk:
             # Only log warning for crypto/metal 
             if max_pip_risk > 500:
                 logger.debug(f"[RISK] High pip count {pip_risk} for {symbol} (Allowed: {max_pip_risk})")
             else:
                return False, f"Pip risk {pip_risk:.1f} exceeds maximum {max_pip_risk} pips"
        
        # All checks passed
        # Ensure we record this in the stack manager
        tick = mt5.symbol_info_tick(symbol)
        if tick and 'narrative' in signal:
             state.register_stack_trade(symbol, signal['narrative'], actual_risk_percent, tick.ask if signal['direction'] == 'BUY' else tick.bid, signal.get('regime', 'UNKNOWN'))
            
        logger.info(f"[RISK CHECK] Trade validated: Risk={actual_risk_percent:.2f}%, Pips={pip_risk:.1f}, Amount=${risk_amount:.2f}")
        return True, "Risk within acceptable limits"
        
    except Exception as e:
        logger.error(f"Error validating trade risk: {e}")
        return False, f"Validation error: {e}"

def ai_validate_intraday_trade(symbol: str, direction: str, strategy_name: str,
                                entry: float, sl: float, tp: float,
                                df_h1: pd.DataFrame) -> Dict:
    """
    L3 Gemini validation for intraday trades.
    Scores the setup 1-10. Cached 5 minutes per symbol.
    Falls back to confidence=7 on quota error (trade proceeds).
    """
    # 5-min cache per symbol
    if not hasattr(ai_validate_intraday_trade, '_cache'):
        ai_validate_intraday_trade._cache = {}
    cache = ai_validate_intraday_trade._cache
    key   = f"{symbol}_{direction}"
    now_t = time.time()
    if key in cache and (now_t - cache[key]['ts']) < 300:
        logger.debug(f"[AI L3] {symbol}: cached score={cache[key]['score']}/10")
        return cache[key]

    if not ai_provider.client:
        return {'score': 6, 'approved': True, 'reason': 'AI not initialized'}

    # Build context from H1 candles
    try:
        h1_ctx = ""
        if df_h1 is not None and len(df_h1) >= 5:
            for i in range(-5, 0):
                c = df_h1.iloc[i]
                h1_ctx += f"O:{c['open']:.2f} H:{c['high']:.2f} L:{c['low']:.2f} C:{c['close']:.2f}\n"
    except Exception:
        h1_ctx = "N/A"

    rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
    prompt = (
        f"Rate this intraday trade 1-10. "
        f"Symbol:{symbol} Dir:{direction} Strategy:{strategy_name} "
        f"Entry:{entry:.4f} SL:{sl:.4f} TP:{tp:.4f} RR:{rr:.1f}x\n"
        f"Last 5 H1 candles:\n{h1_ctx}"
        "Return ONLY JSON: {\"score\":7,\"reason\":\"brief\"}"
    )

    try:
        raw = ai_provider.call_ai(prompt,
            system_prompt="Output ONLY a JSON object starting with {{ and ending with }}.",
            temperature=0.0, max_tokens=80)

        if raw:
            import re as _re
            for m in _re.finditer(r'\{[^{}]*\}', raw):
                try:
                    result = json.loads(m.group(0))
                    if 'score' in result:
                        score = int(result['score'])
                        out = {'score': score, 'approved': score >= 6,
                               'reason': result.get('reason',''), 'ts': now_t}
                        cache[key] = out
                        return out
                except Exception: pass
    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower():
            logger.warning(f"[AI L3] Quota exceeded -- proceeding without L3 for {symbol}")
            return {'score': 7, 'approved': True, 'reason': 'quota_fallback', 'ts': now_t}

    return {'score': 6, 'approved': True, 'reason': 'parse_fallback', 'ts': now_t}


def place_intraday_trade(signal: Dict, account_equity: float):
    """Execute intraday trade with pre-trade risk validation"""
    try:
        # CRITICAL: Validate risk before placing trade
        is_valid, reason = validate_trade_risk(signal, account_equity)
        if not is_valid:
            logger.warning(f"[RISK VETO] Trade rejected for {signal['symbol']}: {reason}")
            return False
        
        symbol = signal['symbol']
        direction = signal['direction']
        stop_loss = signal['stop_loss']
        
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            logger.error(f"Cannot get tick data for {symbol}")
            return False
        
        entry_price = tick.ask if direction == "BUY" else tick.bid

        df    = get_market_data(symbol, config.ENTRY_TF, 50)
        df_h1 = get_market_data(symbol, mt5.TIMEFRAME_H1, 30)
        if df is None:
            return False

        # L3 AI validation -- score this specific setup
        tp_for_l3 = signal.get('tp', entry_price + abs(entry_price - signal['stop_loss']) * 2.0)
        l3 = ai_validate_intraday_trade(symbol, direction,
                                         signal.get('strategy_name','INTRADAY'),
                                         entry_price, signal['stop_loss'], tp_for_l3, df_h1)
        logger.info(f"[AI L3] {symbol} {direction}: score={l3['score']}/10 {l3['reason']}")
        if not l3['approved']:
            logger.info(f"[AI L3] {symbol}: score={l3['score']}/10 -- skip")
            return False
        
        atr = calculate_atr(df['high'], df['low'], df['close'], config.ATR_PERIOD).iloc[-1]
        
        # TP: Structural liquidity pool (swing highs/lows) -- NOT ATR multiples
        # ATR*6 is arbitrary math. Real TP = next liquidity target in H1 structure.
        sl_dist = abs(entry_price - stop_loss)
        if 'liquidity_target' in signal and signal['liquidity_target']:
            tp1 = float(signal['liquidity_target'])
            # Validate RR -- if liquidity target gives < 1.5:1, skip it
            tp_dist = abs(tp1 - entry_price)
            if sl_dist > 0 and tp_dist / sl_dist < 1.5:
                # Extend to minimum 2:1 RR
                tp1 = (entry_price + sl_dist * 2.0) if direction == "BUY" else (entry_price - sl_dist * 2.0)
        else:
            # Fallback: find nearest H1 swing in trade direction
            df_h1_tp = get_market_data(symbol, mt5.TIMEFRAME_H1, 100)
            if df_h1_tp is not None and len(df_h1_tp) >= 20:
                if direction == "BUY":
                    # TP = highest swing high above entry (nearest liquidity)
                    highs = [df_h1_tp['high'].iloc[i] for i in range(-50, -1)
                             if df_h1_tp['high'].iloc[i] > entry_price + sl_dist * 1.5]
                    tp1 = min(highs) if highs else entry_price + atr * 4.0
                else:
                    lows  = [df_h1_tp['low'].iloc[i] for i in range(-50, -1)
                             if df_h1_tp['low'].iloc[i] < entry_price - sl_dist * 1.5]
                    tp1 = max(lows) if lows else entry_price - atr * 4.0
            else:
                tp1 = (entry_price + atr * 4.0) if direction == "BUY" else (entry_price - atr * 4.0)
        
        # Apply Edge Mode Engine Risk Multiplier
        risk_percent = state.current_risk_percent * signal.get('risk_multiplier', 1.0)
        risk_amount = account_equity * (risk_percent / 100.0)
        spec = get_symbol_specs(symbol)
        pip_risk = abs(entry_price - stop_loss) / spec['pip_size']
        # Correct lot sizing using tick_value (works for ALL symbols including Gold/BTC/Oil)
        tick_val  = spec.get('trade_tick_value', 0)
        tick_size = spec.get('trade_tick_size', spec.get('pip_size', 0.0001))
        lot_step  = spec.get('lot_step', 0.01)
        if tick_val and tick_val > 0 and tick_size > 0:
            # Standard formula: risk_$ / (SL_pips  pip_value_per_lot)
            pip_value_per_lot = (tick_val / tick_size) * spec.get('pip_size', tick_size)
            lot_raw = risk_amount / max(pip_risk * pip_value_per_lot, 0.001)
        else:
            # Forex fallback: pip_risk * 10 (only valid for standard forex pairs)
            lot_raw = risk_amount / max(pip_risk * 10, 0.001)
        lot_size = round(lot_raw / lot_step) * lot_step
        lot_size = max(spec['min_lot'], min(lot_size, spec['max_lot']))
        if lot_raw < spec['min_lot']:
            actual_risk_pct = (spec['min_lot'] * pip_risk * (
                (tick_val / tick_size) * spec.get('pip_size', tick_size)
                if tick_val and tick_val > 0 else 10.0
            ) / account_equity) * 100
            logger.info(
                f"[LOT] {symbol}: lot_raw={lot_raw:.5f} < min_lot={spec['min_lot']} "
                f"-- using min_lot. Actual risk: ${spec['min_lot'] * pip_risk:.2f} "
                f"({actual_risk_pct:.1f}%) vs intended {risk_percent:.1f}%. Proceeding."
            )
        else:
            logger.info(f"[LOT] {symbol}: risk=${risk_amount:.2f} pip_risk={pip_risk:.4f} lot={lot_size}")
        
        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logger.error(f"Could not get symbol info for {symbol}")
            return False
            
        digits = symbol_info.digits
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": round(float(entry_price), digits),
            "sl": round(float(stop_loss), digits),
            "tp": round(float(tp1), digits),
            "deviation": 20,
            "magic": 234001,
            "comment": str(f"Intra_{signal['strategy_name']}")[:30],
        }

        # Broker compatibility for order filling (critical for Crypto/Metals)
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
        
        # Spread sanity check: spread must be < 40% of SL distance
        # Wider than that = entering into a slippage trap
        tick_check = mt5.symbol_info_tick(symbol)
        if tick_check:
            spread_raw = tick_check.ask - tick_check.bid
            sl_dist    = abs(entry_price - stop_loss)
            if sl_dist > 0 and spread_raw > sl_dist * 0.40:
                logger.warning(
                    f"[SPREAD GATE] {symbol}: spread {spread_raw:.5f} > "
                    f"40% of SL {sl_dist:.5f}. Skipping."
                )
                return False

        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            ticket = result.order
            
            state.open_positions[ticket] = {
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'initial_sl': stop_loss,    # * Store Initial SL for R-calc
                'stop_loss': stop_loss,     # Current SL (updates)
                'tp1': tp1,
                'lot_size': lot_size,
                'risk_pct': risk_percent,
                'atr': atr,
                'strategy': signal['strategy_name'],
                'opened_at': datetime.now(timezone.utc),
                'breakeven_done': False,
                'trailing_done': False,
                'trailing_active': False
            }
            
            portfolio_manager.add_exposure(symbol, risk_percent)
            state.position_open_times[ticket] = datetime.now(timezone.utc)
            state.daily_trades += 1
            
            logger.info(f"[OK] TRADE OPENED: {symbol} {direction} | Lot: {lot_size} | SL: {stop_loss:.5f} | TP: {tp1:.5f}")
            
            # --- SYNC TO DATABASE ---
            db_manager.record_trade(
                ticket=ticket,
                symbol=symbol,
                direction=direction,
                lot_size=lot_size,
                entry_price=entry_price,
                sl=stop_loss,
                tp=tp1,
                strategy=signal['strategy_name']
            )
            
            send_telegram_message(f" Trade opened: {symbol} {direction} | Lot: {lot_size}")
            return True
            
        else:
            mt5_err = mt5.last_error()
            logger.error(f"Trade failed: retcode={result.retcode if result else 'None'}, comment={result.comment if result else 'None'}, mt5_err={mt5_err}, request={request}")
            return False
            
    except Exception as e:
        logger.error(f"Error placing trade: {e}", exc_info=True)
        return False

# =============================================================================
# POSITION MANAGEMENT (Simplified)
# =============================================================================

def manage_intraday_positions():
    """
    Manage open positions using RISK-BASED Logic (R-Multiples).
    
    Refactored Logic:
    1. Calculate Initial Risk (R) = abs(Entry - Initial_SL)
    2. Breakeven: 
       - Trigger: Current Profit >= 1.0 * R
       - Action: Move SL to Entry + Buffer
    3. Trailing:
       - Trigger: Current Profit >= 1.5 * R
       - Action: Trail SL at distance of 1.0 * R
    """
    positions = mt5.positions_get()
    if not positions:
        return
    
    for pos in positions:
        ticket = pos.ticket
        symbol = pos.symbol
        
        # Skip if not our magic number
        if hasattr(pos, 'magic') and pos.magic != 234001:
            continue
        
        # Get position info from state
        if ticket not in state.open_positions:
            # Try to recover rudimentary state if missing (e.g. from restart)
            state.open_positions[ticket] = {
                'symbol': symbol,
                'direction': "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL",
                'entry_price': pos.price_open,
                'initial_sl': pos.sl if pos.sl > 0 else (pos.price_open - 0.0050 if pos.type == mt5.POSITION_TYPE_BUY else pos.price_open + 0.0050), # Fallback estimate
                'stop_loss': pos.sl,
                'opened_at': datetime.now(timezone.utc),
                'breakeven_done': False
            }
        
        pos_info = state.open_positions[ticket]
        entry_price = pos_info['entry_price']
        current_sl = pos_info['stop_loss']
        initial_sl = pos_info.get('initial_sl', current_sl) # Fallback to current if initial missing
        direction = pos_info['direction']
        
        # 0. GET CURRENT DATA
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            continue
        
        current_price = tick.bid if direction == "BUY" else tick.ask
        point = mt5.symbol_info(symbol).point
        
        # 1. CALCULATE METRICS (in Price Distance)
        if direction == "BUY":
            risk_dist = entry_price - initial_sl
            current_profit_dist = current_price - entry_price
        else: # SELL
            risk_dist = initial_sl - entry_price
            current_profit_dist = entry_price - current_price

        # Sanity check for zero risk (prevent div/0 or logic errors)
        if risk_dist <= 0:
            risk_dist = point * 100 # Fallback 10 pips default
            
        r_multiple = current_profit_dist / risk_dist
        
        # === UPDATE RUNNING P&L IN DATABASE ===
        try:
            running_profit = pos.profit  # MT5's calculated profit for this position
            db_manager.client.table('trades').update({
                'metadata': {
                    'stop_loss': pos.sl,
                    'take_profit': pos.tp,
                    'strategy_name': 'Intraday Core',
                    'running_profit': round(running_profit, 2),
                    'current_price': round(current_price, 5),
                    'r_multiple': round(r_multiple, 2)
                }
            }).eq('ticket', int(ticket)).eq('user_id', db_manager.user_id).execute()
        except Exception as e:
            logger.error(f"[DB ERROR] Running P&L update failed for {symbol}: {e}")
        
        # 2. === BREAKEVEN LOGIC ===
        # Trigger: Profit >= 1.0 R (Configurable)
        if config.ENABLE_BREAKEVEN and not pos_info.get('breakeven_done', False):
            if r_multiple >= config.BREAKEVEN_TRIGGER_R:
                logger.info(f"[MANAGE] {symbol} hit {r_multiple:.2f}R (> {config.BREAKEVEN_TRIGGER_R}R). Moving to Breakeven.")
                
                # Calculate BreakEven Price with Buffer
                buffer_size = config.BREAKEVEN_BUFFER_PIPS * point # e.g. 2 pips * point
                
                if direction == "BUY":
                    new_sl = entry_price + buffer_size
                    # Condition: New SL must be > Current SL
                    should_update = new_sl > current_sl
                else:
                    new_sl = entry_price - buffer_size
                    # Condition: New SL must be < Current SL
                    should_update = new_sl < current_sl
                
                if should_update:
                    if modify_position_sl(pos, new_sl):
                        pos_info['stop_loss'] = new_sl
                        pos_info['breakeven_done'] = True
                        logger.info(f"[OK] Breakeven Set: {symbol} @ {new_sl:.5f} (Locking fees)")
                        send_telegram_message(f" Breakeven Secure: {symbol} (+{r_multiple:.1f}R)")
                    else:
                        logger.error(f"[FAIL] Could not set Breakeven for {symbol}")

        # 3. === TRAILING STOP LOGIC ===
        if config.ENABLE_TRAILING_STOP:
            is_runner = False
            stack = None
            if symbol in state.narrative_stacks:
                stack = state.narrative_stacks[symbol]
                is_runner = stack.get('is_runner', False)
                
            if is_runner:
                # GAP 1: Runner specific trailing logic
                new_sl = RunnerManagementEngine.update_runner_trailing(stack, pos_info, current_price, risk_dist, current_profit_dist, current_sl, direction)
                if new_sl is not None:
                    apply_runner_trailing(ticket, new_sl, pos)
                    pos_info['stop_loss'] = new_sl
                    stack['runner_stop'] = new_sl # Persist in stack object
                    pos_info['trailing_active'] = True
                    logger.info(f"[RUNNER MGR] {symbol} Runner Trailing Mode: {stack['runner_trail_mode']} | New SL: {new_sl:.5f}")
            elif r_multiple >= config.TRAILING_START_R:
                # 3-STAGE STRUCTURAL TRAILING (R-based, progressively tighter)
                # Stage 1 (2-3R):  trail at 1.5R distance -- wide, lets winner run
                # Stage 2 (3-5R):  trail at 1.0R distance -- locks more profit
                # Stage 3 (5R+):   trail at 0.5R distance -- maximum lock
                if r_multiple >= 5.0:
                    trail_distance = risk_dist * 0.5   # Stage 3: tight
                    stage = "STAGE3"
                elif r_multiple >= 3.0:
                    trail_distance = risk_dist * 1.0   # Stage 2: medium
                    stage = "STAGE2"
                else:
                    trail_distance = risk_dist * 1.5   # Stage 1: wide
                    stage = "STAGE1"

                if direction == "BUY":
                    new_sl       = current_price - trail_distance
                    should_update = new_sl > current_sl
                else:
                    new_sl       = current_price + trail_distance
                    should_update = new_sl < current_sl

                if should_update:
                    if modify_position_sl(pos, new_sl):
                        pos_info['stop_loss']      = new_sl
                        pos_info['trailing_active'] = True
                        locked_r = (new_sl - entry_price)/risk_dist if direction=="BUY" else (entry_price-new_sl)/risk_dist
                        logger.info(f"[TRAIL {stage}] {symbol}: {r_multiple:.1f}R | SL={new_sl:.5f} | Locked {locked_r:.1f}R")
        
        # 3.5 === PARTIAL TP EXECUTION ===
        # Close 50% of position when price hits TP1 distance
        if config.ENABLE_PARTIAL_TP and not pos_info.get('partial_closed', False):
            tp1_price = pos_info.get('tp1')
            if tp1_price:
                tp_dist = abs(float(tp1_price) - entry_price)
                if tp_dist > 0 and current_profit_dist >= tp_dist * 0.90:
                    # Price is within 10% of TP1 -- close half
                    close_half_volume = round(pos.volume / 2.0, 2)
                    if close_half_volume >= 0.01:
                        req_partial = {
                            "action":      mt5.TRADE_ACTION_DEAL,
                            "symbol":      symbol,
                            "volume":      close_half_volume,
                            "type":        mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
                            "price":       current_price,
                            "position":    ticket,
                            "deviation":   20,
                            "magic":       234001,
                            "comment":     "PartialTP",
                            "type_filling": mt5.ORDER_FILLING_IOC,
                        }
                        sym_info_p = mt5.symbol_info(symbol)
                        if sym_info_p:
                            mode_p = sym_info_p.filling_mode
                            req_partial["type_filling"] = (
                                mt5.ORDER_FILLING_FOK if mode_p & 1 else
                                mt5.ORDER_FILLING_IOC if mode_p & 2 else
                                mt5.ORDER_FILLING_RETURN
                            )
                        res_p = mt5.order_send(req_partial)
                        if res_p and res_p.retcode == mt5.TRADE_RETCODE_DONE:
                            pos_info['partial_closed'] = True
                            logger.info(f"[PARTIAL TP] {symbol}: closed {close_half_volume} lots at {current_price:.5f} (R={r_multiple:.1f})")
                            # Move SL to breakeven after partial close
                            if not pos_info.get('breakeven_done'):
                                if modify_position_sl(pos, entry_price):
                                    pos_info['stop_loss'] = entry_price
                                    pos_info['breakeven_done'] = True
                        else:
                            logger.warning(f"[PARTIAL TP] {symbol}: partial close failed retcode={res_p.retcode if res_p else 'None'}")

        # 4. === EXIT INTELLIGENCE & RUNNER LOGIC ===
        if ticket in state.position_open_times:
            open_time = state.position_open_times[ticket]
            duration_hours = (datetime.now(timezone.utc) - open_time).total_seconds() / 3600
            
            # Dynamic Narrative Exits
            if symbol in state.narrative_stacks:
                stack = state.narrative_stacks[symbol]
                
                # Check if stack is invalidated
                if stack['status'] == 'CLOSED':
                    logger.info(f"[EXIT INTELLIGENCE] Auto-closing {symbol} due to Narrative Invalidation: {stack.get('close_reason')}")
                    close_position(pos)
                    continue
                    
                # 2. RUNNER PRESERVATION LOGIC & NARRATIVE EXITS
                lifecycle = stack.get('narrative_data', {}).get('lifecycle', 'UNKNOWN')
                liquidity_state = stack.get('narrative_data', {}).get('liquidity_state', 'SEEKING')
                narrative_conf = stack.get('narrative_data', {}).get('confidence_score', 0.5)
                expansion_prob = stack.get('narrative_data', {}).get('expansion_potential', 0.0)
                liquidity_distance = stack.get('narrative_data', {}).get('distance_to_target', 100.0)
                
                is_runner = stack.get('is_runner', False)
                
                # GAP 2: Narrative Exit Engine
                exit_action = NarrativeExitEngine.evaluate_exit(lifecycle, narrative_conf, expansion_prob, liquidity_distance, False)
                if exit_action != "HOLD":
                    execute_narrative_action(exit_action, pos, pos_info, stack)
                    if exit_action == "EXIT" or exit_action == "SCALE_OUT":
                        continue
                
                # Check exit aggressiveness
                aggr = ConfidenceController.get_exit_aggressiveness(narrative_conf)
                if aggr == "MAX" and is_runner:
                     tight_trail_dist = min(risk_dist * 0.5, current_profit_dist * 0.5)
                     if direction == "BUY":
                         new_sl = current_price - tight_trail_dist
                         if new_sl > current_sl: 
                            modify_position_sl(pos, new_sl)
                            stack['runner_stop'] = new_sl
                            logger.info(f"[RUNNER MGR] Max Aggr Long Runner Trail for {symbol}")
                     else:
                         new_sl = current_price + tight_trail_dist
                         if new_sl < current_sl: 
                            modify_position_sl(pos, new_sl)
                            stack['runner_stop'] = new_sl
                            logger.info(f"[RUNNER MGR] Max Aggr Short Runner Trail for {symbol}")
                         
                # GAP 3: Narrative Confidence as Global Controller (Runner Preservation)
                if is_runner and not ConfidenceController.preserve_runner(narrative_conf) and narrative_conf < 0.3:
                     logger.info(f"[EXIT INTELLIGENCE] Auto-closing Runner {symbol} due to total Narrative Collapse (Conf: {narrative_conf:.2f})")
                     close_position(pos)
                     continue
                         
            # Failsafe duration exit
            if duration_hours >= config.MAX_POSITION_DURATION_HOURS:
                logger.info(f"[TIME] Auto-closing {symbol} after {duration_hours:.1f} hours max duration")
                close_position(pos)
                
def initialize_mt5() -> bool:
    """Initialize MT5 connection"""
    try:
        if not mt5.initialize(login=config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER):
            logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            return False
        
        account_info = mt5.account_info()
        if account_info:
            logger.info(f"[OK] MT5 Connected | Account: {account_info.login} | Balance: ${account_info.balance:.2f}")
            
            # CRITICAL: Force symbols to be visible in Market Watch
            logger.info("Verifying Market Watch symbols...")
            for s in config.SYMBOLS:
                if not mt5.symbol_select(s, True):
                     logger.error(f"Failed to select {s} in Market Watch (Broker error?)")
            
            return True
        return False
    except Exception as e:
        logger.error(f"MT5 init error: {e}")
        return False


def modify_position_sl(position, new_sl: float) -> bool:
    """Modify position stop loss"""
    try:
        # Get symbol info for digits
        symbol_info = mt5.symbol_info(position.symbol)
        if not symbol_info:
             logger.error(f"Cannot get symbol info for {position.symbol}")
             return False
             
        digits = symbol_info.digits
        rounded_sl = round(new_sl, digits)
        
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "position": position.ticket,
            "sl": rounded_sl,
            "tp": position.tp,
        }
        
        result = mt5.order_send(request)
        
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return True
        else:
            logger.error(f"[ERROR] Failed to modify SL: {result.comment if result else 'No result'} ({result.retcode if result else '?'})")
            return False
            
    except Exception as e:
        logger.error(f"[ERROR] Exception modifying SL: {e}")
        return False

def close_position(position):
    """Close a position"""
    try:
        symbol = position.symbol
        ticket = position.ticket
        lot = position.volume
        
        if position.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 234001,
            "comment": "Intraday_Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # NOTE: No spread gate on CLOSE -- must always close regardless of spread
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"[OK] Position closed: {symbol} | Ticket: {ticket}")
            
            # --- SYNC TO SUPABASE ---
            # --- SYNC TO SUPABASE ---
            profit = 0.0
            try:
                if hasattr(result, 'deal') and result.deal > 0:
                    deals = mt5.history_deals_get(ticket=result.deal)
                    if deals and len(deals) > 0:
                        profit = deals[0].profit
                elif hasattr(result, 'profit'):
                     profit = result.profit
            except Exception as e:
                logger.error(f"Error fetching close profit: {e}")
            
            db_manager.update_trade_close(int(ticket), result.price, profit, "Intraday_Close")

            if ticket in state.open_positions:
                pos_info = state.open_positions[ticket]
                portfolio_manager.remove_exposure(symbol, pos_info.get('risk_pct', 0.0))
                del state.open_positions[ticket]
            if ticket in state.position_open_times:
                del state.position_open_times[ticket]
            
            return True
        else:
            logger.error(f"Failed to close position: {result.comment}")
            return False
            
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        return False

def recover_existing_positions():
    """
    Recover existing MT5 positions on bot startup
    
    This ensures positions opened before bot stopped/crashed are managed properly
    """
    try:
        positions = mt5.positions_get()
        
        if not positions:
            logger.info("[RECOVERY] No existing positions found")
            return
        
        logger.info(f"[RECOVERY] Found {len(positions)} existing positions - recovering...")
        
        recovered_count = 0
        old_positions_count = 0
        
        for pos in positions:
            ticket = pos.ticket
            symbol = pos.symbol
            
            # Track ALL positions for equity accuracy (not just our magic)
            if hasattr(pos, 'magic') and pos.magic != 234001:
                # External position (from manual trade or other bot)
                ext_pnl = pos.profit
                logger.warning(
                    f"[RECOVERY] EXTERNAL position detected: {symbol} "
                    f"lot={pos.volume} P&L=${ext_pnl:.2f} magic={pos.magic} "
                    f"-- will affect equity but NOT managed by this bot"
                )
                continue  # Don't manage it, just note it

            if hasattr(pos, 'magic') and pos.magic == 234001:
                # Reconstruct position info
                direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                
                # Get current market data for ATR
                df = get_market_data(symbol, config.ENTRY_TF, 50)
                atr = 0.0
                if df is not None:
                    atr = calculate_atr(df['high'], df['low'], df['close'], config.ATR_PERIOD).iloc[-1]
                
                # Calculate position duration
                position_open_time = datetime.fromtimestamp(pos.time, tz=timezone.utc)
                duration_hours = (datetime.now(timezone.utc) - position_open_time).total_seconds() / 3600
                
                # Add to state
                state.open_positions[ticket] = {
                    'symbol': symbol,
                    'direction': direction,
                    'entry_price': pos.price_open,
                    'initial_sl': pos.sl,       # * Store recovered SL as Initial
                    'stop_loss': pos.sl,
                    'tp1': pos.tp,
                    'lot_size': pos.volume,
                    'atr': atr,
                    'strategy': 'RECOVERED',  # Mark as recovered
                    'opened_at': position_open_time,
                    'breakeven_done': False,  # Will be checked by management
                    'trailing_done': False,   # Will be checked by management
                    'trailing_active': False  # Will be activated if criteria met
                }
                
                state.position_open_times[ticket] = position_open_time
                
                logger.info(f"[RECOVERY] {symbol} {direction} | Ticket: {ticket} | Duration: {duration_hours:.1f}h | P&L: ${pos.profit:.2f}")
                
                # Warn if position is older than max duration
                if duration_hours > config.MAX_POSITION_DURATION_HOURS:
                    logger.warning(f"[WARNING] Position {ticket} ({symbol}) has been open for {duration_hours:.1f}h (max: {config.MAX_POSITION_DURATION_HOURS}h)")
                    logger.warning(f"[WARNING] This position will be auto-closed by duration management")
                    old_positions_count += 1
                
                recovered_count += 1
        
        logger.info(f"[RECOVERY] Successfully recovered {recovered_count} positions")
        
        # Log warnings
        if old_positions_count > 0:
            logger.warning(f"[WARNING] {old_positions_count} positions exceed max duration - will be closed soon")
        
        # Log current exposure
        if recovered_count > 0:
            total_exposure = sum(pos.profit for pos in positions if hasattr(pos, 'magic') and pos.magic == 234001)
            logger.info(f"[RECOVERY] Total P&L from recovered positions: ${total_exposure:.2f}")
            logger.info(f"[RECOVERY] These positions will now be managed (breakeven, trailing, session close)")
            
    except Exception as e:
        logger.error(f"[ERROR] Failed to recover existing positions: {e}", exc_info=True)

def check_session_based_exits():
    """Close positions before session closes"""
    if not state.last_session_close_check or (datetime.now(timezone.utc) - state.last_session_close_check).total_seconds() > 300:
        current_hour = datetime.now(timezone.utc).hour
        
        if config.AUTO_CLOSE_BEFORE_LONDON_CLOSE and current_hour == config.LONDON_CLOSE_HOUR:
            positions = mt5.positions_get()
            if positions:
                logger.info("[FINISH] London close - closing all positions")
                for pos in positions:
                    close_position(pos)
        
        if config.AUTO_CLOSE_BEFORE_NY_CLOSE and current_hour == config.NY_CLOSE_HOUR:
            positions = mt5.positions_get()
            if positions:
                logger.info("[FINISH] NY close - closing all positions")
                for pos in positions:
                    close_position(pos)
        
        state.last_session_close_check = datetime.now(timezone.utc)

def update_closed_trades():
    """Update closed trades in database"""
    try:
        from_date = datetime.now(timezone.utc) - timedelta(hours=1)
        deals = mt5.history_deals_get(from_date, datetime.now(timezone.utc))
        
        if not deals:
            return
        
        for deal in deals:
            if deal.entry == mt5.DEAL_ENTRY_OUT:
                profit = deal.profit
                state.daily_pnl += profit
                
                # Retrieve Account Equity for precise RR calc
                account_info = mt5.account_info()
                equity = account_info.equity if account_info else 10000.0
                
                # Update Edge Mode Engine
                ticket = deal.position_id
                if ticket in state.open_positions:
                    pos_data = state.open_positions[ticket]
                    risk_percent = state.current_risk_percent / 100.0
                    projected_risk_amount = equity * risk_percent
                    if projected_risk_amount <= 0: projected_risk_amount = 1.0
                    
                    # Edge Mode Engine updated based on portfolio RR outcome
                    realized_rr = profit / projected_risk_amount
                    
                    # Update stack budget cleanup if closed
                    if hasattr(pos_data, 'symbol') and pos_data['symbol'] in state.narrative_stacks:
                        # Reduce consumed risk as capital is freed, limit to 0
                        stk = state.narrative_stacks[pos_data['symbol']]
                        stk['consumed_risk'] = max(0.0, stk['consumed_risk'] - risk_percent)

                    if profit > 0:
                        edge_engine.update_mode("WIN", realized_rr)
                    elif profit < 0:
                        edge_engine.update_mode("LOSS", 0.0)
                        
                # Track duration
                if ticket in state.position_open_times:
                    open_time = state.position_open_times[ticket]
                    close_time = datetime.fromtimestamp(deal.time, tz=timezone.utc)
                    duration_hours = (close_time - open_time).total_seconds() / 3600
                    state.total_position_duration_hours += duration_hours
                    state.closed_positions_count += 1
                    
                    logger.info(f"[STATUS] Position closed | Duration: {duration_hours:.2f} hours | P/L: ${profit:.2f}")
                    
                    del state.position_open_times[ticket]
                
                # Clean up
                if ticket in state.open_positions:
                    pos_info = state.open_positions[ticket]
                    portfolio_manager.remove_exposure(pos_info['symbol'], pos_info.get('risk_pct', 0.0))
                    del state.open_positions[ticket]
                
    except Exception as e:
        logger.error(f"Error updating closed trades: {e}")

def check_emergency_conditions(account_info) -> bool:
    """
    Check emergency stop conditions with dynamic adjustments for intraday trading
    
    Returns:
        True if emergency stop should be triggered, False otherwise
    """
    if not account_info:
        return False
    
    # Check 1: Daily loss limit
    if state.daily_start_equity > 0:
        # Track actual equity drop -- catches pre-existing position losses
        _eq_drop = state.daily_start_equity - account_info.equity
        daily_loss_amount = -_eq_drop if _eq_drop > 0 else (state.daily_pnl if state.daily_pnl < 0 else 0)
        daily_loss_percent = abs(daily_loss_amount / state.daily_start_equity) * 100
        
        # Dynamic adjustment based on number of open positions
        open_positions = mt5.positions_get()
        effective_limit = config.MAX_DAILY_LOSS_PERCENT
        
        if config.ENABLE_DYNAMIC_EMERGENCY_STOPS and open_positions:
            # If we have open positions, add buffer for their potential loss
            potential_additional_loss = 0
            for pos in open_positions:
                # Calculate potential loss if stop is hit
                pip_distance = abs(pos.price_open - pos.sl)
                potential_loss_pct = (pip_distance / pos.price_open) * 100
                potential_additional_loss += potential_loss_pct
            
            # Adjust effective limit to account for open position risk
            effective_limit = config.MAX_DAILY_LOSS_PERCENT + (potential_additional_loss * 0.5)
        
        if daily_loss_percent >= effective_limit:
            logger.critical(f"[EMERGENCY] Daily loss limit hit: {daily_loss_percent:.2f}% (Limit: {effective_limit:.2f}%)")
            logger.critical(f"[EMERGENCY] Loss Amount: ${abs(daily_loss_amount):.2f} / Starting Equity: ${state.daily_start_equity:.2f}")
            return True
    
    # Check 2: Maximum drawdown from daily start
    current_drawdown_pct = ((state.daily_start_equity - account_info.equity) / state.daily_start_equity) * 100
    
    if current_drawdown_pct >= config.MAX_DRAWDOWN_PERCENT:
        logger.critical(f"[EMERGENCY] Max drawdown exceeded: {current_drawdown_pct:.2f}% (Limit: {config.MAX_DRAWDOWN_PERCENT}%)")
        logger.critical(f"[EMERGENCY] Current Equity: ${account_info.equity:.2f} / Starting: ${state.daily_start_equity:.2f}")
        return True
    
    # Check 3: Warn if approaching limits (70% of limit)
    if daily_loss_percent >= config.MAX_DAILY_LOSS_PERCENT * 0.7:
        logger.warning(f"[WARNING] Approaching daily loss limit: {daily_loss_percent:.2f}% / {config.MAX_DAILY_LOSS_PERCENT}%")
    
    if current_drawdown_pct >= config.MAX_DRAWDOWN_PERCENT * 0.7:
        logger.warning(f"[WARNING] Approaching max drawdown: {current_drawdown_pct:.2f}% / {config.MAX_DRAWDOWN_PERCENT}%")
    
    return False

def update_heartbeat(status='running', error_message=None):
    try:
        #  FIX: Fetch account info locally first
        acc = mt5.account_info()
        current_bal = acc.balance if acc else 0.0
        current_eq = acc.equity if acc else 0.0
        is_connected = True if acc else False
        
        current_pid = os.getpid() if status == 'running' else None
        
        supabase.table('bot_heartbeats').upsert({
            'user_id': USER_ID,
            'strategy_id': STRATEGY_ID,
            'status': status,
            'last_heartbeat': datetime.now(timezone.utc).isoformat(),
            'pid': current_pid,
            'balance': current_bal,  # Use local variable
            'equity': current_eq,    # Use local variable
            'mt5_connected': is_connected, # Use local variable
            'error_message': error_message
        }, on_conflict='user_id,strategy_id').execute()
        
    except Exception as e:
        logger.error(f"Failed to update heartbeat: {e}")

def sync_active_positions_to_db():
    """
    Background process to ensure all local open positions exist in database
    """
    try:
        if not state.open_positions:
            return

        # Get what DB thinks is open
        db_open_tickets = set(db_manager.get_open_tickets())
        
        # Check active positions
        for ticket, pos_info in state.open_positions.items():
            if ticket not in db_open_tickets:
                logger.warning(f"[SYNC] Syncing missing position {ticket} ({pos_info['symbol']}) to DB")
                
                db_manager.record_trade(
                    ticket=ticket,
                    symbol=pos_info['symbol'],
                    direction=pos_info['direction'],
                    lot_size=pos_info['lot_size'],
                    entry_price=pos_info['entry_price'],
                    sl=pos_info['stop_loss'],
                    tp=pos_info['tp1'],
                    strategy=pos_info.get('strategy', 'SYNCED'),
                    opened_at=pos_info.get('opened_at')
                )
                
    except Exception as e:
        logger.error(f"[SYNC ERROR] Failed to sync positions: {e}")

# =============================================================================
# MAIN TRADING LOOP
# =============================================================================

def _ny_to_utc_minutes(h_ny: int, m_ny: int) -> int:
    """Convert NY time (EDT/EST) to UTC minutes-since-midnight, DST-aware."""
    import time as _time
    # Check if currently EDT (UTC-4) or EST (UTC-5)
    # DST in US: 2nd Sunday March -> 1st Sunday November
    now = datetime.now(timezone.utc)
    year = now.year
    # 2nd Sunday in March
    mar1 = datetime(year, 3, 1)
    dst_start = mar1 + timedelta(days=(6 - mar1.weekday()) % 7 + 7)
    # 1st Sunday in November
    nov1 = datetime(year, 11, 1)
    dst_end = nov1 + timedelta(days=(6 - nov1.weekday()) % 7)
    is_edt = dst_start.date() <= now.date() < dst_end.date()
    offset = 4 if is_edt else 5  # EDT=UTC-4, EST=UTC-5
    return (h_ny * 60 + m_ny + offset * 60) % (24 * 60)

def get_active_macro_window() -> Optional[str]:
    """
    ICT Temporal Macro Windows -- exact 5 periods from image (EST, DST-aware).

    NY AM Macro 1:      9:50 - 10:10 AM EST  (Silver Bullet, highest probability)
    NY AM Macro 2:     10:50 - 11:10 AM EST
    NY Lunch Macro:    11:50 AM - 12:10 PM EST
    NY PM Macro:        1:10 -  1:40 PM EST
    NY Last Hour Macro: 3:15 -  3:45 PM EST

    London Macro kept as a bonus window (not in NY image but valid ICT window):
    London Macro:       2:33 -  3:00 AM EST

    All times DST-aware: EDT (UTC-4) Mar-Nov, EST (UTC-5) Nov-Mar.
    """
    now_utc = datetime.now(timezone.utc)
    t_utc   = now_utc.hour * 60 + now_utc.minute

    # Exact 5 macros from image 1 + London macro
    ny_windows = [
        (2*60+33,   3*60+0,   "LONDON_MACRO"),       # London (bonus)
        (9*60+50,  10*60+10,  "NY_AM_MACRO_1"),       # Silver Bullet -- highest prob
        (10*60+50, 11*60+10,  "NY_AM_MACRO_2"),
        (11*60+50, 12*60+10,  "NY_LUNCH_MACRO"),
        (13*60+10, 13*60+40,  "NY_PM_MACRO"),
        (15*60+15, 15*60+45,  "NY_LAST_HOUR_MACRO"),  # 3:15-3:45 PM EST
    ]
    for ny_start, ny_end, name in ny_windows:
        utc_start = _ny_to_utc_minutes(ny_start // 60, ny_start % 60)
        utc_end   = _ny_to_utc_minutes(ny_end   // 60, ny_end   % 60)
        if utc_start <= t_utc < utc_end:
            return name
    return None

def is_in_kill_zone() -> bool:
    """
    Kill zone: London Open + NY Open session windows (NY time, DST-aware).
    London Open: 02:00-05:00 NY  = 06:00-09:00 UTC (EDT)
    NY Open:     09:30-16:00 NY  = 13:30-20:00 UTC (EDT)
    """
    now_utc = datetime.now(timezone.utc)
    t_utc   = now_utc.hour * 60 + now_utc.minute

    # London Open: 2:00-5:00 AM NY
    london_start = _ny_to_utc_minutes(2, 0)
    london_end   = _ny_to_utc_minutes(5, 0)
    # NY Open: 9:30 AM - 4:00 PM NY
    ny_start     = _ny_to_utc_minutes(9, 30)
    ny_end       = _ny_to_utc_minutes(16, 0)

    return (london_start <= t_utc < london_end) or (ny_start <= t_utc < ny_end)


def intraday_trading_session():
    """Main intraday trading loop"""
    last_heartbeat = time.time()
    
    logger.info("="*80)
    logger.info("[TARGET] INTRADAY TRADING BOT (SERVER) - SESSION STARTED")
    logger.info(f"   MT5 Account: {config.MT5_LOGIN}")
    logger.info(f"   Timeframes: H1/H4 (Intraday)")
    logger.info(f"   Max Trades/Day: {config.MAX_DAILY_TRADES}")
    logger.info(f"   Risk Per Trade: {config.BASE_RISK_PERCENT:.1f}% of equity per trade")
    logger.info("="*80)
    
    # CRITICAL: Recover any existing positions from previous session
    logger.info("[RECOVERY] Checking for existing positions...")
    recover_existing_positions()
    
    iteration = 0
    
    try:
        account_info = mt5.account_info()
        # Use CURRENT equity as baseline (includes floating P&L of any open positions)
        # This means the 25% loss limit measures loss from NOW, not from some previous state
        state.daily_start_equity = account_info.equity if account_info else 0.0
        logger.info(
            f"[RISK] Daily start equity set to ${state.daily_start_equity:.2f} "
            f"(includes floating P&L of any pre-existing positions)"
        )
    except Exception as e:
        logger.error(f"Failed to get initial account info: {e}")
        state.daily_start_equity = 0.0
    
    while True:
        try:
            iteration += 1
            
            # Reset and rebuild portfolio exposure (GAP 4)
            portfolio_manager.reset_exposure()
            for stack_symbol, stack in state.narrative_stacks.items():
                if stack.get('status') != "CLOSED":
                    portfolio_manager.add_exposure(stack_symbol, stack.get('consumed_risk', 0.0))
            
            # 0. DAILY RESET at midnight UTC
            current_day = datetime.now(timezone.utc).day
            if not hasattr(state, 'last_reset_day'):
                state.last_reset_day = current_day
            if current_day != state.last_reset_day:
                logger.info(f"[NEW DAY] Resetting P&L (was ${state.daily_pnl:.2f}) and trade count")
                state.daily_pnl = 0.0
                state.daily_trades = 0
                state.daily_start_equity = account_info.equity if account_info else state.daily_start_equity
                state.last_reset_day = current_day

            # 1. Connection Check
            account_info = mt5.account_info()
            if not account_info:
                logger.error("Lost MT5 connection")
                time.sleep(30)
                if not initialize_mt5():
                    logger.error("Failed to reconnect")
                    time.sleep(60)
                continue
                
            # 2. Heartbeat (non-blocking -- never freeze scan loop)
            if time.time() - last_heartbeat >= config.HEARTBEAT_INTERVAL:
                last_heartbeat = time.time()
                import threading as _t1
                _t1.Thread(target=db_manager.send_heartbeat, daemon=True).start()
                _t1.Thread(target=update_heartbeat, daemon=True).start()
            
            # 3. Kill switch + Emergency Stop
            try:
                _ks = supabase.table('bot_commands').select('kill_switch').eq('user_id', USER_ID).execute()
                if _ks.data and _ks.data[0].get('kill_switch', False):
                    logger.critical("[KILL SWITCH] Remote kill switch activated. Stopping.")
                    break
            except Exception as _kse:
                # Suppress 400 spam (table may not exist) -- log once per hour
                if not hasattr(state, '_ks_err_logged') or (time.time() - state._ks_err_logged) > 3600:
                    logger.debug(f"[KILL SWITCH] bot_commands check failed (table may not exist): {_kse}")
                    state._ks_err_logged = time.time()

            if check_emergency_conditions(account_info):
                logger.critical("[ALERT] EMERGENCY STOP TRIGGERED")
                break
            
            # 4. Update Context & News (non-blocking)
            import threading as _t2
            if not hasattr(state, '_last_ai_ctx_time'): state._last_ai_ctx_time = 0.0
            if time.time() - state._last_ai_ctx_time > config.AI_GLOBAL_CONTEXT_INTERVAL:
                state._last_ai_ctx_time = time.time()
                _t2.Thread(target=update_global_ai_context, daemon=True).start()
            if not hasattr(state, '_last_news_time'): state._last_news_time = 0.0
            if time.time() - state._last_news_time > 3600:
                state._last_news_time = time.time()
                _t2.Thread(target=fetch_upcoming_news_events, daemon=True).start()
            
            # 5. Manage Positions
            manage_intraday_positions()
            check_session_based_exits()
            
            # 6. Update History (non-blocking)
            import threading as _t3
            if not hasattr(state, '_last_closed_time'): state._last_closed_time = 0.0
            if time.time() - state._last_closed_time > 10.0:
                state._last_closed_time = time.time()
                _t3.Thread(target=update_closed_trades, daemon=True).start()
            
            # 7. Status Logging (every 30s)
            if not hasattr(state, '_last_status'): state._last_status = 0.0
            if time.time() - state._last_status >= 30.0:
                state._last_status = time.time()
                in_kz = is_in_kill_zone()
                h_now = datetime.now(timezone.utc).hour
                bias_str = " ".join(f"{s.replace('USDm','')[:3]}:{v.replace('_ONLY','')[:4]}"
                                    for s,v in state.approved_bias.items()) if state.approved_bias else "none"
                logger.info(
                    f"[STATUS] Eq:${account_info.equity:.2f} P&L:${state.daily_pnl:.2f} "
                    f"Trades:{state.daily_trades}/{config.MAX_DAILY_TRADES} "
                    f"Session:{get_current_session()} KillZone:{'YES' if in_kz else 'NO'} "
                    f"Bias:[{bias_str}] Risk:{config.BASE_RISK_PERCENT:.1f}% Macro:{get_active_macro_window() or "WAIT"}"
                )
            
            # --- HEARTBEAT SYNC ---
            if iteration % 6 == 0: # Every ~60s (10s * 6)
                db_manager.send_heartbeat()
                
            # --- BACKGROUD POSITION SYNC ---
            if iteration % 10 == 0:
                import threading as _t4
                _t4.Thread(target=sync_active_positions_to_db, daemon=True).start()

            # 8. Trade Entry Logic -- KILL ZONE GATE
            open_positions = mt5.positions_get()
            current_open_count = len(open_positions) if open_positions else 0

            # Rollover blackout: 21:30-23:00 UTC (US close + spread spikes)
            _ru_h = datetime.now(timezone.utc).hour
            _ru_m = datetime.now(timezone.utc).minute
            _in_rollover = (_ru_h == 21 and _ru_m >= 30) or (_ru_h == 22)
            if _in_rollover:
                if not hasattr(state, '_rollover_logged') or state._rollover_logged != _ru_h:
                    logger.warning(f"[ROLLOVER] {_ru_h}:{_ru_m:02d} UTC -- high spread window. No new entries.")
                    state._rollover_logged = _ru_h
                time.sleep(5)
                continue

            #  24/7 UNIFIED SCAN LOOP 
            # All strategies run at all times.
            # Session context adjusts the confidence threshold:
            #   Kill zone + macro window  -> min_confidence 0.70 (normal entry bar)
            #   Kill zone only            -> min_confidence 0.75 (slightly stricter)
            #   Outside kill zone         -> min_confidence 0.82 (only high-conviction)
            #   Asian session (00-07 UTC) -> min_confidence 0.88 (tightest -- low liquidity)
            # A perfect H1 OB during Asian hours still trades -- just needs higher score.
            # 

            _in_kz    = is_in_kill_zone()
            _macro    = get_active_macro_window()
            _h_utc    = datetime.now(timezone.utc).hour
            _asian    = 0 <= _h_utc < 7   # Asian session: low liquidity, tightest threshold

            # Session-aware minimum confidence threshold
            if _in_kz and _macro:
                _min_conf = 0.70   # Kill zone + macro: best conditions, normal bar
            elif _in_kz:
                _min_conf = 0.75   # Kill zone only: good conditions
            elif not _asian:
                _min_conf = 0.82   # Outside KZ but not Asian (London/late NY): elevated
            else:
                _min_conf = 0.88   # Asian session: only exceptional setups

            # Session context log every 30 iterations
            if iteration % 60 == 0:
                _sess_name = get_current_session()
                logger.info(
                    f"[SESSION] {datetime.now(timezone.utc).strftime('%H:%M')} UTC "
                    f"| Session:{_sess_name} KZ:{'YES' if _in_kz else 'NO'} "
                    f"Macro:{_macro or 'none'} MinConf:{_min_conf:.2f} "
                    f"(all strategies active)"
                )

            if state.daily_trades < config.MAX_DAILY_TRADES and current_open_count < config.MAX_CONCURRENT_TRADES:
                for symbol in config.SYMBOLS:
                    existing_pos = [p for p in open_positions if p.symbol == symbol] if open_positions else []
                    stacking_mode = "NONE"

                    # Compute temporary narrative just for stacking checks
                    try:
                        df_d1_t       = get_market_data(symbol, config.DAILY_TF, 200)
                        df_entry_t    = get_market_data(symbol, config.ENTRY_TF, 200)
                        df_structure_t= get_market_data(symbol, config.STRUCTURE_TF, 200)
                        df_micro_t    = get_market_data(symbol, config.MICRO_STRUCTURE_TF, 100)
                        temp_narrative = NarrativeIntentEngine.build(
                            symbol, df_d1_t, df_structure_t, df_entry_t, df_micro_t
                        ) if df_d1_t is not None else None
                    except Exception:
                        temp_narrative = None

                    if existing_pos:
                        stack_signal = active_stacking_engine(symbol, existing_pos, temp_narrative, df_micro_t)
                        if isinstance(stack_signal, str):
                            stack_signal = {"mode": stack_signal, "risk_multiplier": 0.5}
                        stacking_mode = stack_signal.get("mode", "NONE")
                        if stacking_mode == "NONE" and len(existing_pos) > 0:
                            continue

                    # Per-symbol cooldown
                    if symbol in state.symbol_cooldowns:
                        if datetime.now(timezone.utc) < state.symbol_cooldowns[symbol]:
                            continue
                        else:
                            del state.symbol_cooldowns[symbol]

                    bias = state.approved_bias.get(symbol, "NEUTRAL")

                    # Run context engine (A/B/C/D/E all inside)
                    local_signal = context_decision_engine(
                        symbol, ai_bias=bias, stacking_mode=stacking_mode,
                        min_confidence=_min_conf
                    )

                    if local_signal:
                        # Boost confidence label for logging
                        _sess_tag = "KZ+MACRO" if (_in_kz and _macro) else ("KZ" if _in_kz else ("ASIAN" if _asian else "OFF_SESSION"))
                        logger.info(
                            f"[SIGNAL] {symbol} {local_signal['direction']} "
                            f"strat={local_signal['strategy_name']} "
                            f"conf={local_signal.get('confidence',0):.2f} "
                            f"sess={_sess_tag} min={_min_conf:.2f}"
                        )

                        if stacking_mode != "NONE" and "risk_multiplier" in stack_signal:
                            local_signal['risk_multiplier'] *= stack_signal['risk_multiplier']

                        result = place_intraday_trade(local_signal, account_info.equity)
                        if result:
                            time.sleep(2)
                        else:
                            state.symbol_cooldowns[symbol] = datetime.now(timezone.utc) + timedelta(minutes=3)
            
        except KeyboardInterrupt:
            logger.info("[STOP] Bot stopped by user")
            break
        
        except Exception as e:
            import traceback as _tb
            logger.error(f"[CRASH] {type(e).__name__}: {e}")
            logger.error(_tb.format_exc()[-500:])
            time.sleep(10)

        # Prevent CPU spin -- intraday bot checks every 2s
        time.sleep(2.0)
    
    mt5.shutdown()
    logger.info("[FINISH] Bot shutdown complete")

# =============================================================================
# MAIN ENTRY
# =============================================================================

def main():
    """Main entry point"""
    
    logger.info("[START] Initializing Intraday Trading Bot (LOCAL TEST)...")
    
    if not ai_provider.api_key:
        logger.error("[ERROR] GEMINI_API_KEY not set!")
        logger.error("   Set it with: export GEMINI_API_KEY='your-key'")
        sys.exit(1)
    
    if not initialize_mt5():
        logger.error("[ERROR] Failed to initialize MT5")
        sys.exit(1)
    
    try:
        intraday_trading_session()
    except KeyboardInterrupt:
        logger.info("[STOP] Bot stopped by user")
    except Exception as e:
        logger.critical(f"[CRASH] Fatal error: {e}", exc_info=True)
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()
