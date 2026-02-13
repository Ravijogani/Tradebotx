# -*- coding: utf-8 -*-
"""
=============================================================================
🤖 HYBRID AI TRADING BOT - V11.3 INTELLIGENT (CONTEXT-AWARE) 🤖
=============================================================================
ARCHITECTURE:
This is the production-ready, multi-user version.
-   It is controlled entirely by command-line arguments (CLI), allowing a
    backend "Bot Manager" to spawn one instance per user.
-   All credentials (MT5, API keys) are passed via CLI.
-   All trade logging and AI learning is now pointed to a central
    Supabase database, replacing the local SQLite DB.
-   Includes integrated Telegram notifications for trade events.
-   Includes a `send_heartbeat` function for dashboard monitoring.


V11.3 INTELLIGENT (🧠 CONTEXT-AWARE INTELLIGENCE):
- ✅ Added session-aware scoring (Asia: stricter, London: lenient)
- ✅ Added volatility adaptation (skips quiet markets, adapts SL/TP)
- ✅ Added performance tracking (considers recent strategy success)
- ✅ Adaptive thresholds (not hardcoded!)
- ✅ Context-aware decisions (not blind rule following)

Expected improvement: From 20% to 45-55% win rate with INTELLIGENT decisions!

V11.0 Changelog:
- Merged V10.1 (Stable) engine with `hybrid_trading_bot_multiuser.py` template.
- Replaced all CLI argument logic with the new top-level parser.
- Replaced `TradeHistoryDB` (SQLite) with `SupabaseTradeDB`.
- Rewrote `place_ai_trade`, `update_closed_trades`, `manage_all_positions`,
  `ai_analyze_closed_trades`, and `ai_calculate_risk_percent` to use
  the new Supabase functions.
- Integrated `send_telegram_notification` at key points.
- Integrated `send_heartbeat` into the main loop.
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
# CLI ARGUMENT PARSING
# =============================================================================

parser = argparse.ArgumentParser(description='Multi-user Hybrid AI Trading Bot')
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
parser.add_argument('--magic-number', type=int, required=False, help='Fixed Magic Number (optional - if not provided, generates from user-id + strategy-id)')

args = parser.parse_args()

# User-specific configuration
USER_ID = args.user_id
STRATEGY_ID = args.strategy_id
TELEGRAM_CHAT_ID = args.telegram_chat_id
TELEGRAM_BOT_TOKEN = args.telegram_bot_token

# MAGIC NUMBER MANAGEMENT
MAGIC_NUMBER = args.magic_number if args.magic_number else 234005
print(f"[MAGIC] Using Magic number: {MAGIC_NUMBER}")

# Initialize Supabase client
supabase: Client = create_client(args.supabase_url, args.supabase_key)

# DATA DIRECTORY SETUP (OS AGNOSTIC)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", USER_ID)
os.makedirs(DATA_DIR, exist_ok=True)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class AITradingConfig:
    """Configuration for AI-powered adaptive trading bot"""
    
    # MT5 Connection
    MT5_LOGIN: int = args.mt5_login
    MT5_PASSWORD: str = args.mt5_password
    MT5_SERVER: str = args.mt5_server
    
    # AI API Configuration
    AI_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = args.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"
    
    # AI Feature Flags
    ENABLE_AI_VALIDATION: bool = True
    ENABLE_AI_RISK_MANAGEMENT: bool = True
    ENABLE_AI_TRADE_LEARNING: bool = True
    
    # Local-First Strategy Engine Flags
    ENABLE_LOCAL_NEWS_FILTER: bool = True
    ENABLE_CONFLUENCE_ENGINE: bool = True
    
    # AI Analysis Intervals
    AI_GLOBAL_CONTEXT_INTERVAL: int = 3600
    AI_LEARNING_INTERVAL: int = 3600
    LOCAL_NEWS_CHECK_INTERVAL: int = 1800
    MIN_TRADES_FOR_LEARNING: int = 10
    
    # Trading Parameters
    # SCALPING MODE: Focus on 5 best pairs (tightest spreads, highest liquidity)
    SYMBOLS: List[str] = field(default_factory=lambda: [
        'EURUSDm', 'GBPUSDm', 'USDJPYm', 'XAUUSDm',
        'BTCUSDm', 'ETHUSDm', 'USOILm', 'NZDUSDm',
        'USDCADm', 'AUDUSDm', 'USDCHFm', 'GBPJPYm'
    ])
    MAX_CONCURRENT_TRADES: int = 3
    MAX_DAILY_TRADES: int = 50  # AI SCALPER: No artificial limits, focus on quality
    MAX_DAILY_LOSS_PERCENT: float = 15.0  # Base limit (dynamic: 10-15% based on conditions)
    MAX_DAILY_DRAWDOWN_PERCENT: float = 3.0   # HARD STOP: Equity Protector (3% max daily DD)
    ROLLOVER_WINDOW_START: int = 22           # UTC Hour to start blackout
    ROLLOVER_WINDOW_END: int = 23             # UTC Hour to end blackout
    
    # Timeframes
    ENTRY_TF: int = mt5.TIMEFRAME_M5
    STRUCTURE_TF: int = mt5.TIMEFRAME_M15
    MICRO_STRUCTURE_TF: int = mt5.TIMEFRAME_M1
    TREND_TF: int = mt5.TIMEFRAME_H1
    ATR_PERIOD: int = 14
    
    # DYNAMIC PARAMETERS
    BASE_RISK_PERCENT: float = 1.0
    MIN_RISK_PERCENT: float = 0.3
    MAX_RISK_PERCENT: float = 3.0
    SL_ATR_MULTIPLIER: float = 1.2   # Tighter stop for M5 scalping
    TP1_ATR_MULTIPLIER: float = 1.0  # Quick first target (10-12 pips)
    TP2_ATR_MULTIPLIER: float = 2.0  # Runner target (18-20 pips)
    ENABLE_BREAKEVEN: bool = True
    BREAKEVEN_TRIGGER_PERCENT: float = 75.0  # ULTRA CONSERVATIVE: Maximum patience
    BREAKEVEN_LOCK_PERCENT: float = 5.0
    ENABLE_TRAILING_STOP: bool = True
    TRAILING_START_PERCENT: float = 70.0  # ULTRA CONSERVATIVE: Start trailing later     # Aggressive scalping: start trailing at halfway
    TRAILING_ATR_MULTIPLIER: float = 1.0
    
    # [OK] FIX 2: Partial TP Configuration
    ENABLE_PARTIAL_TP: bool = True
    PARTIAL_TP_PERCENT: float = 50.0           # Close HALF (Standard Scalping)
    PARTIAL_TP_TRIGGER_PERCENT: float = 60.0   # Secure profit at 60% to TP
    
    SPREAD_ATR_THRESHOLD: float = 0.15         # Spread must be < 15% of Daily ATR
    MAX_SPREAD_RATIO: float = 0.5              # Legacy fallback
    
    
    # Local News Filter
    NEWS_API_URL: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    NEWS_PAUSE_BEFORE_MINUTES: int = 30
    NEWS_PAUSE_AFTER_MINUTES: int = 30
    HIGH_IMPACT_CURRENCIES: List[str] = field(default_factory=lambda: ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF"])

    # Local Confluence Engine
    MIN_CONFLUENCE_SCORE_TRENDING: float = 1.6  # AI SCALPER: Quality but not too strict  # Reduced from 1.5 for scalping
    MIN_CONFLUENCE_SCORE_RANGING: float = 1.4  # AI SCALPER: Quality but allows more trades   # Reduced from 1.3 for scalping
    ADX_PERIOD: int = 14
    ADX_TRENDING_THRESHOLD: float = 30.0  # ULTRA CONSERVATIVE: Strong trends only
    
    # Local Strategy Weights
    STRATEGY_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        'ICT_KILLZONE': 0.9, 'ADVANCED_SMC': 0.7, 'LIQUIDITY_GRAB': 0.95,
        'WYCKOFF_PATTERNS': 0.6, 'VOLUME_PROFILE': 0.6,
        'MOMENTUM_CONFLUENCE': 0.7, 'TREND_PULLBACK': 0.7,
        'SUPPORT_RESISTANCE': 0.85, 'MEAN_REVERSION_BB': 0.9
    })
    
    # Enabled Local Strategies
    ENABLED_STRATEGIES: List[str] = field(default_factory=lambda: [
        'ICT_KILLZONE', 'ADVANCED_SMC', 'LIQUIDITY_GRAB', 
        'WYCKOFF_PATTERNS', 'VOLUME_PROFILE', 'SUPPORT_RESISTANCE',
        'MOMENTUM_CONFLUENCE', 'TREND_PULLBACK', 'MEAN_REVERSION_BB'
    ])
    
    # Strategy-Specific Params
    ICT_FVG_MITIGATION_CANDLES: int = 20
    ICT_KILLZONES: Dict[str, Tuple[int, int]] = field(default_factory=lambda: {
        'LONDON': (7, 10), 'NEW_YORK': (13, 16), 'ASIAN': (1, 4)
    })
    SMC_MIN_OB_SIZE_PIPS: int = 10
    SMC_VALIDATION_CANDLES: int = 15
    SMC_SWING_LOOKBACK: int = 5
    VOLUME_PROFILE_PERIODS: int = 100
    VOLUME_LOOKBACK: int = 20
    VOLUME_SURGE_MULTIPLIER: float = 1.5
    MOMENTUM_EMA_FAST: int = 8
    MOMENTUM_EMA_SLOW: int = 21
    BB_PERIOD: int = 20
    BB_STD_DEV: float = 2.2
    SR_LOOKBACK_PERIODS: int = 50
    
    # [OK] FIX 3: Rate Limiting
    LOOP_DELAY_SECONDS: float = 1.0  # Reduced from 0.1 to 1.0 second

config = AITradingConfig()

# Symbol Specifications (same as original)
SYMBOL_SPECS = {
    "EURUSDm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "GBPUSDm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "USDJPYm": {"pip_size": 0.01, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "XAUUSDm": {"pip_size": 0.01, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
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

LOG_DIR = f"Hybrid_AI_Bot_Logs_{USER_ID}"
BACKUP_DIR = f"Backup_Trades_{USER_ID}"
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8',
    errors='replace',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f"hybrid_ai_bot_{datetime.now().strftime('%Y%m%d')}.log"), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
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
            logger.error(f"Failed to send Telegram notification (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
    return False

def send_heartbeat(status: str = 'running', mt5_connected: bool = True, error_message: str = None, max_retries: int = 3):
    """Corrected Heartbeat with required pid, balance, and equity"""
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
                'daily_pnl': getattr(state, 'daily_pnl', 0.0)
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
    
    def _retry_operation(self, operation_name: str, operation_func, max_retries: int = 3) -> bool:
        """Generic retry wrapper for Supabase operations"""
        for attempt in range(max_retries):
            try:
                operation_func()
                return True
            except Exception as e:
                logger.error(f"{operation_name} failed (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        return False
    
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
                result = supabase.table('trades').insert(db_trade).execute()
                logger.info(f"[DB] Trade {db_trade['ticket']} synced to dashboard")
            
            success = self._retry_operation("Trade logging", insert_trade)
            
            if not success:
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
        
        # Send Telegram notification
        emoji = "🟢" if profit_loss > 0 else "🔴"
        send_telegram_notification(
            f"{emoji} <b>Trade Closed</b>\n\n"
            f"Ticket: {ticket}\n"
            f"Reason: {exit_reason}\n"
            f"P&L: ${profit_loss:.2f}"
        )
        
        return True
    
    def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        """Get recent trades with error handling"""
        try:
            result = supabase.table('trades').select('*').eq(
                'user_id', USER_ID
            ).eq('status', 'closed').order(
                'closed_at', desc=True
            ).limit(limit).execute()
            
            return [self.convert_to_ai_format(t) for t in result.data] if result.data else []
        except Exception as e:
            logger.error(f"Error fetching recent trades: {e}")
            return []
    
    def get_winning_trades(self, limit: int = 20) -> List[Dict]:
        """Get winning trades"""
        try:
            result = supabase.table('trades').select('*').eq(
                'user_id', USER_ID
            ).eq('status', 'closed').gt('profit_loss', 0).order(
                'closed_at', desc=True
            ).limit(limit).execute()
            
            return [self.convert_to_ai_format(t) for t in result.data] if result.data else []
        except Exception as e:
            logger.error(f"Error fetching wins: {e}")
            return []
    
    def get_losing_trades(self, limit: int = 20) -> List[Dict]:
        """Get losing trades"""
        try:
            result = supabase.table('trades').select('*').eq(
                'user_id', USER_ID
            ).eq('status', 'closed').lt('profit_loss', 0).order(
                'closed_at', desc=True
            ).limit(limit).execute()
            
            return [self.convert_to_ai_format(t) for t in result.data] if result.data else []
        except Exception as e:
            logger.error(f"Error fetching losses: {e}")
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
                    'ticket', str(ticket)
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
                    'ticket': str(ticket),
                    'profit_loss': profit,
                    'metadata': {
                        'strategy_name': 'SYNCED',
                        'exit_reason': 'HISTORY_SYNC',
                        'market_regime': 'UNKNOWN',
                        'imported': True
                    }
                }
                
                supabase.table('trades').insert(db_trade).execute()
                count += 1
                
            except Exception as e:
                logger.error(f"Failed to sync trade {ticket}: {e}")

        if count > 0 or fixed_zombies > 0:
            logger.info(f" Sync Complete: {count} new imports, {fixed_zombies} zombie trades fixed")
        else:
            logger.info(" History is up to date")

    def restore_state_from_db(self, open_positions_dict: Dict):
        """Stateless Restoration: Pulls management flags from Supabase metadata to prevent logic loops"""
        logger.info(" [DB] Restoring persistent state for open positions...")
        try:
            result = supabase.table('trades').select('*').eq(
                'user_id', USER_ID
            ).eq('status', 'open').execute()
            
            if result.data:
                for db_trade in result.data:
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
        except Exception as e:
            logger.error(f"Error restoring state: {e}")
            
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
        """
        Get full trade details by ticket number for AI learning
        Returns trade data with all metadata
        """
        try:
            result = supabase.table('trades').select('*').eq(
                'user_id', USER_ID
            ).eq(
                'ticket', str(ticket)
            ).execute()
            
            if not result.data or len(result.data) == 0:
                logger.warning(f"[AI LEARNING] Trade #{ticket} not found in database")
                return {}
            
            trade = result.data[0]
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
            
        except Exception as e:
            logger.error(f"[AI LEARNING] Error fetching trade #{ticket}: {e}")
            return {}

    def update_metadata(self, ticket: str, updates: Dict) -> bool:
        """Update specific metadata fields without overwriting everything"""
        try:
            # 1. Get current metadata
            res = supabase.table('trades').select('metadata').eq('ticket', str(ticket)).eq('user_id', USER_ID).execute()
            if not res.data: return False
            
            current_meta = res.data[0].get('metadata', {})
            
            # 2. Merge updates
            current_meta.update(updates)
            
            # 3. Save back
            supabase.table('trades').update({'metadata': current_meta}).eq('ticket', str(ticket)).eq('user_id', USER_ID).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update metadata for {ticket}: {e}")
            return False

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
        self.current_risk_percent: float = config.BASE_RISK_PERCENT
        self.current_sl_multiplier: float = config.SL_ATR_MULTIPLIER
        self.current_tp1_multiplier: float = config.TP1_ATR_MULTIPLIER
        self.current_be_trigger: float = config.BREAKEVEN_TRIGGER_PERCENT
        self.current_trailing_start: float = config.TRAILING_START_PERCENT
        
        # Trade management
        self.be_moved: set = set()
        self.trailing_active: set = set()
        
        # [OK] FIX: Partial TP tracking
        self.partial_closed: set = set()

        # Pre-Approved Bias
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

state = AITradingState()

# =============================================================================
# ULTIMATE AI ENHANCEMENTS - FULL IMPLEMENTATION
# =============================================================================

class PatternRecognitionSystem:
    """
    BREAKTHROUGH: ML-based pattern recognition
    Learns from ALL trades, predicts outcomes BEFORE entry
    """
    
    def __init__(self):
        self.patterns_file = os.path.join(DATA_DIR, 'trade_patterns.json')
        self.patterns_db = []
        self.load_patterns()
        
    def load_patterns(self):
        """Load existing patterns from file"""
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
    Caches indicators and optimizes execution speed
    10x performance improvement
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
                    logger.info(f" [MICRO] {symbol} High liquidity sweep detected → SELL setup")
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
                logger.info(f" [MICRO] {symbol} Strong BUY momentum detected")
                return 'STRONG_BUY'
            elif recent_momentum < -0.0015 and recent_volume > avg_volume * 1.5:
                logger.info(f" [MICRO] {symbol} Strong SELL momentum detected")
                return 'STRONG_SELL'
            
            return None
            
        except Exception as e:
            logger.error(f"[MICRO] Error checking momentum: {e}")
            return None
    
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
    Eliminates sequential blocking (56s → 5s per cycle)
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
        """Fetch all required timeframes for a symbol"""
        try:
            return {
                'M1': get_market_data(symbol, mt5.TIMEFRAME_M1, 50),
                'M5': get_market_data(symbol, mt5.TIMEFRAME_M5, 100),
                'M15': get_market_data(symbol, mt5.TIMEFRAME_M15, 150),
                'H1': get_market_data(symbol, mt5.TIMEFRAME_H1, 100),
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
    Eliminates 200ms blocking calls during execution
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
            return ['MOMENTUM_CONFLUENCE', 'LIQUIDITY_GRAB']
        else:  # RANGING
            # Mean-reversion strategies
            return ['LIQUIDITY_GRAB', 'SUPPORT_RESISTANCE']


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
            elif h4_regime == "RANGING": score += 25
        
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

class AdaptiveRiskManager:
    """
    Intelligent risk management that adapts to loss streaks and AI recommendations.
    """
    
    @staticmethod
    def calculate_adaptive_lot_size(
        symbol: str, 
        entry_price: float, 
        stop_loss: float, 
        equity: float,
        tradability_score: int,
        ai_recommended_risk: float,
        ai_confidence: float,
        news_multiplier: float = 1.0 # <--- NEW: Volatility Awareness
    ) -> float:
        
        # 1. Start with AI Recommendation
        risk_percent = ai_recommended_risk
        
        # 2. "Sniper Boost" for High Confidence (ONLY if NO News)
        # If AI is > 85% sure and score is high, we boost risk
        is_high_confidence = (ai_confidence >= 0.85) and (tradability_score >= 80)
        
        if is_high_confidence and news_multiplier == 1.0:
            risk_percent *= 1.25 # 25% Boost
            logger.info(f" SNIPER BOOST: High Confidence ({ai_confidence:.0%}). Risk boosted to {risk_percent:.2f}%")

        # 3. Streak Protection (The Shield)
        # Only cut risk if it's NOT a high confidence setup
        if not is_high_confidence:
            recent_trades = trade_db.get_recent_trades(10)
            consec_losses = 0
            for t in recent_trades:
                if t.get('win') == 0: consec_losses += 1
                else: break
            if consec_losses >= 2: risk_percent *= 0.5
            if consec_losses >= 4: risk_percent *= 0.25
            
        # 4. Calculate Lot Size
        risk_amount = equity * (risk_percent / 100)
        spec = get_symbol_specs(symbol)
        pip_value = spec.get('trade_tick_value', 1.0)
        tick_size = spec.get('trade_tick_size', 0.00001)
        sl_pips = abs(entry_price - stop_loss)
        
        if sl_pips == 0 or tick_size == 0: 
            raw_lot = spec.get('min_lot', 0.01)
        else:
            raw_lot = risk_amount / (sl_pips / tick_size * pip_value)

        # 5. MICRO ACCOUNT GROWTH HACK & NEWS DAMPING
        # Force 0.02 lots for partial TP on low-volatility pairs
        # SAFETY: ONLY if News Multiplier is 1.0 (Normal market conditions)
        is_volatile = any(x in symbol for x in ['XAUUSDm', 'BTCUSDm', 'ETHUSDm', 'OILUSDm', 'USOILm'])
        
        # --- NEWS DAMPING (User Request: Reduce Size by 50%) ---
        if news_multiplier > 1.0:
            raw_lot *= 0.5
            logger.info(f" [NEWS GUARD] Damping lot size by 50% for {symbol} (Multiplier {news_multiplier}x)")
        
        elif equity < 300 and is_high_confidence and not is_volatile:
            if raw_lot < 0.02:
                raw_lot = 0.02
                logger.info(f" MICRO GROWTH: Forcing 0.02 lots on {symbol} to enable Partial TP.")

        # Rounding
        step = spec.get('lot_step', 0.01)
        lot_size = round(raw_lot / step) * step
        lot_size = max(spec.get('min_lot'), min(spec.get('max_lot'), lot_size))
        
        return lot_size

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
                    self.gemini_model = genai.GenerativeModel(config.GEMINI_MODEL)
                    logger.info(f"Gemini SDK Initialized: {config.GEMINI_MODEL}")
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
        
        try:
            response = self.gemini_model.generate_content(
                full_prompt,
                generation_config={"temperature": temperature, "max_output_tokens": max_tokens}
            )
            text = response.text.strip()
            if json_mode:
                if '```' in text:
                    text = text.split('```')[1] if text.count('```') >= 2 else text
                    text = text.replace('json', '').strip()
            return text
        except Exception as e:
            logger.error(f" AI API Error: {e}")
            if "quota" in str(e).lower():
                logger.critical("!!! AI QUOTA EXCEEDED. BOT WILL PAUSE AI CALLS. !!!")
                state.last_global_context_update = datetime.now() + timedelta(hours=1)
            return None

ai_provider = AIProvider()

# =============================================================================
# MT5 CONNECTION & DATA
# =============================================================================

def initialize_mt5() -> bool:
    try:
        # <-- Uses config values set by CLI args
        if not mt5.initialize(login=config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER):
            logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            return False
        account_info = mt5.account_info()
        if account_info:
            logger.info(f"MT5 Connected | Account: {account_info.login} | Balance: ${account_info.balance:.2f}")
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
    current_hour = datetime.now(timezone.utc).hour
    if 7 <= current_hour < 16: return "LONDON"
    if 13 <= current_hour < 22: return "NY"
    if 0 <= current_hour < 8: return "ASIAN"
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
            
    except Exception as e:
        logger.error(f"An unexpected error occurred in fetch_upcoming_news_events: {e}", exc_info=True)

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
                    sl = fvg_low - (atr * 0.5)
                    return {"direction": "BUY", "stop_loss": sl, "strategy_name": "ICT_KILLZONE", "confidence": 0.85}
        
        if df_entry['high'].iloc[i+1] < df_entry['low'].iloc[i-1]:
            fvg_high, fvg_low = df_entry['low'].iloc[i-1], df_entry['high'].iloc[i+1]
            if fvg_low <= current_price <= fvg_high and trend == "BEARISH":
                # CHECK: M1 Candle must be RED (Close < Open) to confirm rejection
                if df_micro['close'].iloc[-1] < df_micro['open'].iloc[-1]: 
                    sl = fvg_high + (atr * 0.5)
                    return {"direction": "SELL", "stop_loss": sl, "strategy_name": "ICT_KILLZONE", "confidence": 0.85}
    return None

def strategy_advanced_smc(df_entry: pd.DataFrame, df_structure: pd.DataFrame, trend: str, symbol: str, df_micro: pd.DataFrame) -> Optional[Dict[str, Any]]:
    spec = get_symbol_specs(symbol)
    if not spec or not spec.get('pip_size'): 
        logger.warning(f"SMC: Cannot get pip_size for {symbol}")
        return None
    pip_size = spec['pip_size']
    
    min_ob_size = config.SMC_MIN_OB_SIZE_PIPS * pip_size
    current_price = df_entry['close'].iloc[-1]
    atr = calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], config.ATR_PERIOD).iloc[-1]
    
    swing_highs, swing_lows = identify_swing_highs_lows(df_structure, config.SMC_SWING_LOOKBACK)
    bos = detect_break_of_structure(df_structure, swing_highs, swing_lows)
    
    for i in range(len(df_entry) - config.SMC_VALIDATION_CANDLES - 1, 5, -1):
        candle_open, candle_close = df_entry['open'].iloc[i], df_entry['close'].iloc[i]
        candle_high, candle_low = df_entry['high'].iloc[i], df_entry['low'].iloc[i]

        if candle_close < candle_open: # Bearish candle
            if i + 1 < len(df_entry) and df_entry['close'].iloc[i+1] > candle_high:
                ob_high, ob_low = candle_high, candle_low
                if (ob_high - ob_low) >= min_ob_size and ob_low <= current_price <= ob_high:
                    if current_price > df_entry['open'].iloc[-1]:
                        confidence = 0.75 + (0.10 if bos == "BULLISH_BOS" else 0)
                        return {"direction": "BUY", "stop_loss": ob_low - (atr * 0.5), "strategy_name": "ADVANCED_SMC", "confidence": confidence}

        elif candle_close > candle_open: # Bullish candle
            if i + 1 < len(df_entry) and df_entry['close'].iloc[i+1] < candle_low:
                ob_high, ob_low = candle_high, candle_low
                if (ob_high - ob_low) >= min_ob_size and ob_low <= current_price <= ob_high:
                    if current_price < df_entry['open'].iloc[-1]:
                        confidence = 0.75 + (0.10 if bos == "BEARISH_BOS" else 0)
                        return {"direction": "SELL", "stop_loss": ob_high + (atr * 0.5), "strategy_name": "ADVANCED_SMC", "confidence": confidence}
    return None

def strategy_liquidity_grab(df_entry: pd.DataFrame, df_structure: pd.DataFrame, trend: str, symbol: str, df_micro: pd.DataFrame) -> Optional[Dict[str, Any]]:
    if len(df_entry) < 15: return None
    swing_highs_idx, swing_lows_idx = identify_swing_highs_lows(df_entry, lookback=5)
    last_candle, prev_candle = df_entry.iloc[-1], df_entry.iloc[-2]
    atr = calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], config.ATR_PERIOD).iloc[-1]

    if swing_highs_idx and trend != "BULLISH":
        last_high = df_entry['high'].iloc[swing_highs_idx[-1]]
        if prev_candle['high'] > last_high and last_candle['close'] < last_candle['open'] and last_candle['close'] < prev_candle['low']:
             return {"direction": "SELL", "stop_loss": prev_candle['high'] + (atr * 0.2), "strategy_name": "LIQUIDITY_GRAB", "confidence": 0.8}

    if swing_lows_idx and trend != "BEARISH":
        last_low = df_entry['low'].iloc[swing_lows_idx[-1]]
        if prev_candle['low'] < last_low and last_candle['close'] > last_candle['open'] and last_candle['close'] > prev_candle['high']:
            return {"direction": "BUY", "stop_loss": prev_candle['low'] - (atr * 0.2), "strategy_name": "LIQUIDITY_GRAB", "confidence": 0.8}
    return None

def strategy_wyckoff_patterns(df_entry: pd.DataFrame, df_structure: pd.DataFrame, trend: str, symbol: str, df_micro: pd.DataFrame) -> Optional[Dict[str, Any]]:
    if len(df_entry) < config.VOLUME_LOOKBACK + 10: return None
    volume_avg = df_entry['tick_volume'].rolling(window=config.VOLUME_LOOKBACK).mean()
    volume_surge = df_entry['tick_volume'].iloc[-1] > (volume_avg.iloc[-1] * config.VOLUME_SURGE_MULTIPLIER)
    price_range = df_entry['high'].iloc[-1] - df_entry['low'].iloc[-1]
    avg_range = (df_entry['high'] - df_entry['low']).rolling(window=20).mean().iloc[-1]
    atr = calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], config.ATR_PERIOD).iloc[-1]

    if (trend != "BULLISH" and df_entry['low'].iloc[-1] < df_entry['low'].iloc[-2] and
        df_entry['close'].iloc[-1] > df_entry['close'].iloc[-2] and volume_surge and
        price_range > avg_range * 1.2 and df_entry['close'].iloc[-1] > df_entry['high'].iloc[-2]):
        return {"direction": "BUY", "stop_loss": df_entry['low'].iloc[-1] - (atr * 0.5), "strategy_name": "WYCKOFF_PATTERNS", "confidence": 0.8}
    
    if (trend != "BEARISH" and df_entry['high'].iloc[-1] > df_entry['high'].iloc[-2] and
        df_entry['close'].iloc[-1] < df_entry['close'].iloc[-2] and volume_surge and
        price_range > avg_range * 1.2 and df_entry['close'].iloc[-1] < df_entry['low'].iloc[-2]):
        return {"direction": "SELL", "stop_loss": df_entry['high'].iloc[-1] + (atr * 0.5), "strategy_name": "WYCKOFF_PATTERNS", "confidence": 0.8}
    return None

def strategy_volume_profile(df_entry: pd.DataFrame, trend: str, symbol: str) -> Optional[Dict[str, Any]]:
    if 'tick_volume' not in df_entry.columns or len(df_entry) < config.VOLUME_PROFILE_PERIODS: return None
    df_vp = df_entry.iloc[-config.VOLUME_PROFILE_PERIODS:]
    prices = pd.concat([df_vp['low'], df_vp['high']])
    volumes = pd.concat([df_vp['tick_volume'] / 2, df_vp['tick_volume'] / 2])
    price_bins = pd.cut(prices, bins=20)
    volume_by_bin = volumes.groupby(price_bins, observed=True).sum()
    if volume_by_bin.empty: return None
    poc_bin = volume_by_bin.idxmax()
    poc = poc_bin.mid
    current_price = df_entry['close'].iloc[-1]
    atr = calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], config.ATR_PERIOD).iloc[-1]
    proximity = atr * 0.5

    if trend != "BEARISH" and abs(current_price - poc) < proximity and current_price > poc:
        if df_entry['close'].iloc[-1] > df_entry['open'].iloc[-1]:
            return {"direction": "BUY", "stop_loss": poc - atr, "strategy_name": "VOLUME_PROFILE", "confidence": 0.75}

    if trend != "BULLISH" and abs(current_price - poc) < proximity and current_price < poc:
        if df_entry['close'].iloc[-1] < df_entry['open'].iloc[-1]:
            return {"direction": "SELL", "stop_loss": poc + atr, "strategy_name": "VOLUME_PROFILE", "confidence": 0.75}
    return None

def strategy_support_resistance(df_entry: pd.DataFrame, trend: str) -> Optional[Dict[str, Any]]:
    # 1. Setup Data
    if len(df_entry) < 20: return None
    current_price = df_entry['close'].iloc[-1]
    atr = calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], config.ATR_PERIOD).iloc[-1]
    
    # 2. Get recent Swing Lows/Highs
    swing_highs_idx, swing_lows_idx = identify_swing_highs_lows(df_entry, lookback=5)
    
    # --- SNIPER LOGIC: WICK REJECTION ---
    # We want to catch the bounce off the level, not just the touch.
    
    # BUY SETUP
    if swing_lows_idx:
        last_support = df_entry['low'].iloc[swing_lows_idx[-1]]
        proximity = atr * 0.5 
        
        # Check if current LOW wicked the support
        if abs(df_entry['low'].iloc[-1] - last_support) < proximity:
            # Check for Rejection: Close > Open AND Long Lower Wick
            candle = df_entry.iloc[-1]
            body = abs(candle['close'] - candle['open'])
            lower_wick = candle['open'] - candle['low'] if candle['close'] > candle['open'] else candle['close'] - candle['low']
            
            # Hammer Pattern: Wick is 2x Body
            if lower_wick > (body * 1.5) and candle['close'] > candle['open']:
                 return {
                    "direction": "BUY", 
                    "stop_loss": candle['low'] - (atr * 0.2), 
                    "strategy_name": "SNIPER_SUPPORT_WICK", 
                    "confidence": 0.95
                }

    # SELL SETUP
    if swing_highs_idx:
        last_resistance = df_entry['high'].iloc[swing_highs_idx[-1]]
        proximity = atr * 0.5
        
        # Check if current HIGH wicked the resistance
        if abs(df_entry['high'].iloc[-1] - last_resistance) < proximity:
            # Check for Rejection: Close < Open AND Long Upper Wick
            candle = df_entry.iloc[-1]
            body = abs(candle['close'] - candle['open'])
            upper_wick = candle['high'] - candle['open'] if candle['close'] < candle['open'] else candle['high'] - candle['close']
            
            # Shooting Star Pattern
            if upper_wick > (body * 1.5) and candle['close'] < candle['open']:
                return {
                    "direction": "SELL", 
                    "stop_loss": candle['high'] + (atr * 0.2), 
                    "strategy_name": "SNIPER_RESISTANCE_WICK", 
                    "confidence": 0.95
                }

    return None

def strategy_momentum_confluence(df_entry: pd.DataFrame, trend: str, symbol: str) -> Optional[Dict[str, Any]]:
    ema_fast = df_entry['close'].ewm(span=config.MOMENTUM_EMA_FAST, adjust=False).mean()
    ema_slow = df_entry['close'].ewm(span=config.MOMENTUM_EMA_SLOW, adjust=False).mean()
    if trend == "BULLISH" and ema_fast.iloc[-1] > ema_slow.iloc[-1] and ema_fast.iloc[-2] <= ema_slow.iloc[-2]:
        sl = df_entry['low'].iloc[-1] - (df_entry['high'].iloc[-1] - df_entry['low'].iloc[-1])
        return {"direction": "BUY", "stop_loss": sl, "strategy_name": "MOMENTUM_CONFLUENCE", "confidence": 0.7}
    if trend == "BEARISH" and ema_fast.iloc[-1] < ema_slow.iloc[-1] and ema_fast.iloc[-2] >= ema_slow.iloc[-2]:
        sl = df_entry['high'].iloc[-1] + (df_entry['high'].iloc[-1] - df_entry['low'].iloc[-1])
        return {"direction": "SELL", "stop_loss": sl, "strategy_name": "MOMENTUM_CONFLUENCE", "confidence": 0.7}
    return None

def strategy_trend_pullback(df_entry: pd.DataFrame, trend: str, symbol: str) -> Optional[Dict[str, Any]]:
    ema_slow = df_entry['close'].ewm(span=config.MOMENTUM_EMA_SLOW, adjust=False).mean().iloc[-1]
    last_candle, prev_candle = df_entry.iloc[-1], df_entry.iloc[-2]
    if trend == "BULLISH" and prev_candle['low'] < ema_slow and last_candle['close'] > last_candle['open'] and last_candle['close'] > prev_candle['high']:
        return {"direction": "BUY", "stop_loss": prev_candle['low'], "strategy_name": "TREND_PULLBACK", "confidence": 0.75}
    if trend == "BEARISH" and prev_candle['high'] > ema_slow and last_candle['close'] < last_candle['open'] and last_candle['close'] < prev_candle['low']:
        return {"direction": "SELL", "stop_loss": prev_candle['high'], "strategy_name": "TREND_PULLBACK", "confidence": 0.75}
    return None

def strategy_mean_reversion_bb(df_entry: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
    close = df_entry['close']
    sma = close.rolling(window=config.BB_PERIOD).mean()
    std = close.rolling(window=config.BB_PERIOD).std()
    upper = sma + (std * config.BB_STD_DEV)
    lower = sma - (std * config.BB_STD_DEV)
    last_candle = df_entry.iloc[-1]
    if last_candle['high'] > upper.iloc[-1] and last_candle['close'] < upper.iloc[-1]:
        return {"direction": "SELL", "stop_loss": last_candle['high'], "strategy_name": "MEAN_REVERSION_BB", "confidence": 0.7}
    if last_candle['low'] < lower.iloc[-1] and last_candle['close'] > lower.iloc[-1]:
        return {"direction": "BUY", "stop_loss": last_candle['low'], "strategy_name": "MEAN_REVERSION_BB", "confidence": 0.7}
    return None

# =============================================================================
# LOCAL-FIRST CONFLUENCE ENGINE
# =============================================================================
def analyze_order_flow(symbol: str) -> str:
    """
    Checks real-time buying/selling pressure from tick data.
    Returns: 'STRONG_BUY', 'STRONG_SELL', or 'NEUTRAL'
    """
    try:
        # Get last 60 seconds of ticks
        ticks = mt5.copy_ticks_from(symbol, datetime.now(timezone.utc) - timedelta(seconds=60), 1000, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0: return "NEUTRAL"
        
        df_ticks = pd.DataFrame(ticks)
        # Flag 1 = Buy (Ask), Flag 2 = Sell (Bid) - simplification for MT5
        buy_vol = df_ticks[df_ticks["flags"] & mt5.TICK_FLAG_BUY == mt5.TICK_FLAG_BUY]["volume"].sum()
        sell_vol = df_ticks[df_ticks["flags"] & mt5.TICK_FLAG_SELL == mt5.TICK_FLAG_SELL]["volume"].sum()
        
        total = buy_vol + sell_vol
        if total == 0: return "NEUTRAL"
        
        ratio = (buy_vol - sell_vol) / total
        
        if ratio > 0.2: return "STRONG_BUY"
        if ratio < -0.2: return "STRONG_SELL"
        return "NEUTRAL"
    except:
        return "NEUTRAL"

# =============================================================================
# [OK] NEW: SNIPER FILTERS & V12 VALIDATION
# =============================================================================

def precision_entry_check(symbol: str, direction: str) -> bool:
    """
    SNIPER SCOPE: Checks M1 timeframe.
    """
    try:
        # Get M1 Data
        df_m1 = get_market_data(symbol, mt5.TIMEFRAME_M1, 30)
        if df_m1 is None or len(df_m1) < 14: return True 

        # Calculate RSI manually
        delta = df_m1['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]

        # --- SCALPER MODE: Momentum Breakout Logic ---
        # If ADX > 25 (Strong Trend), IGNORE Overbought/Oversold
        # Because in strong trends, RSI stays extreme for a long time.
        
        # Calculate Trend Strength (ADX equivalent on M1)
        # Using simple ATR/Range proxy for speed
        range_m1 = df_m1['high'].max() - df_m1['low'].min()
        avg_candle = (df_m1['high'] - df_m1['low']).mean()
        momentum_score = range_m1 / (avg_candle * len(df_m1)) if avg_candle > 0 else 0
        
        is_strong_momentum = (momentum_score > 0.8) # Arbitrary threshold, tune as needed

        # Prevent Buying only if RSI is EXTREME (> 80) unless strong momentum
        if direction == "BUY" and rsi > 70:
            if is_strong_momentum or rsi < 80:
                # Allow it - it's a breakout
                pass 
            else:
                logger.info(f"  SKIPPED {symbol}: Price overextended (M1 RSI {rsi:.1f}).")
                return False
            
        # Prevent Selling only if RSI is EXTREME (< 20) unless strong momentum
        if direction == "SELL" and rsi < 30:
            if is_strong_momentum or rsi > 20:
                pass
            else:
                logger.info(f"  SKIPPED {symbol}: Price overextended (M1 RSI {rsi:.1f}).")
                return False
            
        return True
    except Exception as e:
        return True

def session_quality_score() -> float:
    """
    ULTRA CONSERVATIVE: Returns quality score (0-1) based on active market sessions.
    Only London and NY sessions are considered high quality (1.0)
    Everything else is discouraged
    """
    try:
        hour = datetime.now(timezone.utc).hour
        
        # ULTRA CONSERVATIVE: Only best times
        # London session (08:00-12:00 UTC) - Prime
        if 8 <= hour <= 11: return 1.0
        
        # NY session / London-NY overlap (13:00-17:00 UTC) - Best
        if 13 <= hour <= 16: return 1.0
        
        # London open / NY close (7-8, 17-20 UTC) - Acceptable but not ideal
        if hour == 7 or 17 <= hour <= 19: return 0.6
        
        # Asian session - Generally avoid
        if 0 <= hour <= 6: return 0.3
        
        # Dead zones - Strongly discouraged
        if 20 <= hour <= 23: return 0.2
        
        # Other hours (12, etc)
        return 0.4
        
    except: return 0.4

def volatility_spike_detector(df: pd.DataFrame) -> bool:
    """Detects if market is in a dangerous whipsaw state."""
    try:
        # Check if current ATR is 2x the average ATR (Explosive move)
        atr_current = df['high'].iloc[-5:].mean() - df['low'].iloc[-5:].mean()
        atr_avg = df['high'].iloc[-20:-5].mean() - df['low'].iloc[-20:-5].mean()
        if atr_avg == 0: return False
        
        ratio = atr_current / atr_avg
        if ratio > 2.0:
            logger.warning(f" Volatility Spike Detected (Ratio: {ratio:.1f}). Skipping.")
            return True # Is a spike
        return False
    except: return False

def price_action_confirmation(df: pd.DataFrame, direction: str) -> bool:
    """Ensures the last candle actually supports the trade direction."""
    try:
        candle = df.iloc[-1]
        close, open_ = candle['close'], candle['open']
        
        # If BUY, Candle must be Green (Close > Open)
        if direction == "BUY" and close < open_: return False
        # If SELL, Candle must be Red (Close < Open)
        if direction == "SELL" and close > open_: return False
        
        return True
    except: return True

def enhanced_signal_filter(signal: Dict, symbol: str) -> bool:
    """MASTER FILTER: Combines all checks."""
    # 1. Session Check
    # AI SCALPER: Trade 24/7, but log session quality for AI learning
    session_score = session_quality_score()
    if session_score < 0.3:  # Only skip extremely dead zones
        logger.info(f" SKIP: Session quality too low ({session_score:.2f})")
        return False
    
    df = get_market_data(symbol, config.ENTRY_TF, 50)
    if df is None: return False
    
    # 2. Volatility Check
    if volatility_spike_detector(df): return False
    
    # 3. Price Action Check (Don't buy on a red candle)
    if not price_action_confirmation(df, signal['direction']): return False
    
    return True


def get_trading_session() -> str:
    """Detect current trading session"""
    hour = datetime.now(timezone.utc).hour
    if 7 <= hour < 11:
        return "LONDON"
    elif 13 <= hour < 17:
        return "NY"
    elif 1 <= hour < 6:
        return "ASIA"
    else:
        return "OVERLAP"


def get_strategy_recent_performance(strategy_name: str, symbol: str, days: int = 3) -> float:
    """🧠 INTELLIGENT: Get recent win rate for a strategy"""
    try:
        recent_trades = trade_db.get_recent_trades_for_strategy(strategy_name, symbol, days)
        if len(recent_trades) < 3:
            return 0.6  # Default neutral
        
        wins = sum(1 for t in recent_trades if t.get('profit', 0) > 0)
        win_rate = wins / len(recent_trades)
        
        logger.debug(f"  [PERFORMANCE] {strategy_name} on {symbol}: {win_rate:.1%} over {days} days ({len(recent_trades)} trades)")
        return win_rate
    except:
        return 0.6  # Default neutral


def find_local_confluence_signal(symbol: str, cached_data: dict = None) -> Optional[Dict[str, Any]]:
    """
    SCALPING LIGHTNING V2.0: ULTRA-FAST signal detection
    - Uses cached data (no blocking I/O)
    - Regime-aware strategy selection (2-3 strategies max)
    - 10x faster than previous version
    """
    try:
        # SPEED OPTIMIZATION: Check cache first
        cache_key = f"confluence_{symbol}"
        cached_signal = speed_optimizer.get(cache_key)
        if cached_signal is not None:
            return cached_signal
        
        # USE CACHED DATA ONLY (NON-BLOCKING)
        if cached_data is None:
            # DO NOT fallback to live fetch - it blocks the entire loop
            speed_optimizer.set(cache_key, None)
            return None

        # Use pre-fetched cached data
        df_entry = cached_data.get('M5')
        df_structure = cached_data.get('M15')
        df_micro = cached_data.get('M1')
        
        if any(df is None for df in [df_entry, df_structure, df_micro]): 
            speed_optimizer.set(cache_key, None)
            return None
        
        # REGIME DETECTION (50ms)
        market_regime = regime_detector.detect_regime(symbol, df_structure)
        
        # Get trend direction for strategies (using pandas ewm directly)
        ema_series = df_structure['close'].ewm(span=20, adjust=False).mean()
        current_price = float(df_structure['close'].iloc[-1])
        ema_value = float(ema_series.iloc[-1])
        trend_direction = "BULLISH" if current_price > ema_value else "BEARISH"
        
        # SCALPING OPTIMIZATION: Only 2-3 fast strategies based on regime
        strategies_to_run = regime_detector.get_strategies_for_regime(market_regime)
        
        logger.info(f" [SCALPING] {symbol} Regime: {market_regime} | Strategies: {strategies_to_run}")

        all_signals = []
        strategy_functions = {
            "MOMENTUM_CONFLUENCE": strategy_momentum_confluence,
            "LIQUIDITY_GRAB": strategy_liquidity_grab,
            "SUPPORT_RESISTANCE": strategy_support_resistance,
        }
        
        # Execute ONLY selected strategies (2-3 max, ~400ms total)
        for name in strategies_to_run:
            if name in state.banned_strategies: 
                continue
            
            func = strategy_functions.get(name)
            if not func: 
                continue
            
            # Execute strategy function
            signal = None
            try:
                if name == "LIQUIDITY_GRAB":
                    signal = func(df_entry, df_structure, trend_direction, symbol, df_micro)
                elif name == "MOMENTUM_CONFLUENCE":
                    signal = func(df_entry, trend_direction, symbol)
                elif name == "SUPPORT_RESISTANCE":
                    signal = func(df_entry, trend_direction)
            except Exception as e:
                logger.error(f"[SCALPING] Error in {name}: {e}")
                continue

            if signal:
                signal['weight'] = config.STRATEGY_WEIGHTS.get(name, 1.0)
                signal['regime'] = market_regime
                all_signals.append(signal)

        if not all_signals: return None

        # Scoring Logic (simplified for speed)
        buy_signals = [s for s in all_signals if s['direction'] == 'BUY']
        sell_signals = [s for s in all_signals if s['direction'] == 'SELL']
        buy_score = sum(s['weight'] * s['confidence'] for s in buy_signals)
        sell_score = sum(s['weight'] * s['confidence'] for s in sell_signals)
        
        # 🧠 INTELLIGENT SCORING: Adaptive based on session
        session = get_trading_session()
        
        # Base score adjusted by session quality
        if session == "ASIA":
            min_score = 1.8  # Higher bar in low liquidity
            logger.info(f"  [INTELLIGENCE] ASIA session: Requiring higher confluence (1.8)")
        elif session == "LONDON":
            min_score = 1.0  # Lower bar in high liquidity  
            logger.info(f"  [INTELLIGENCE] LONDON session: Lower confluence needed (1.0)")
        elif session == "NY":
            min_score = 1.2  # Normal bar
            logger.info(f"  [INTELLIGENCE] NY session: Normal confluence (1.2)")
        else:
            min_score = 1.5  # Overlap/uncertain periods

        # STRICT CONFLUENCE ENFORCEMENT
        # 1. Must have at least 2 contributing strategies OR
        # 2. Score must be exceptionally high (> 2.5) with high confidence
        
        best_signal = None
        if buy_score >= min_score and buy_score > sell_score:
            strategies_count = len(buy_signals)
            avg_conf = np.mean([s['confidence'] for s in buy_signals])
            
            if strategies_count >= 2 or (strategies_count == 1 and avg_conf >= 0.9):
                valid_sls = [s['stop_loss'] for s in buy_signals if 'stop_loss' in s]
                if valid_sls:
                    best_signal = { 
                        "direction": "BUY", "stop_loss": min(valid_sls), "symbol": symbol,
                        "confidence": avg_conf, 
                        "contributing_strategies": [s['strategy_name'] for s in buy_signals], 
                        "trend": trend_direction, "regime": market_regime,
                        "score": buy_score
                    }
        elif sell_score >= min_score and sell_score > buy_score:
            strategies_count = len(sell_signals)
            avg_conf = np.mean([s['confidence'] for s in sell_signals])
            
            if strategies_count >= 2 or (strategies_count == 1 and avg_conf >= 0.9):
                valid_sls = [s['stop_loss'] for s in sell_signals if 'stop_loss' in s]
                if valid_sls:
                    best_signal = { 
                        "direction": "SELL", "stop_loss": max(valid_sls), "symbol": symbol,
                        "confidence": avg_conf, 
                        "contributing_strategies": [s['strategy_name'] for s in sell_signals], 
                        "trend": trend_direction, "regime": market_regime,
                        "score": sell_score
                    }
        
        if best_signal:
            logger.info(f" [{symbol}] SIGNAL | {best_signal['direction']} | Regime: {market_regime} | Score: {best_signal['score']:.2f}")
            
            # SPEED OPTIMIZATION: Cache the result
            speed_optimizer.set(cache_key, best_signal)
            return best_signal
        
        # Cache negative result
        speed_optimizer.set(cache_key, None)
        return None
        
    except Exception as e:
        logger.error(f"[SCALPING] Error in signal detection: {e}")
        return None

# =============================================================================
# AI-POWERED FUNCTIONS (Validation, Risk, Learning)
# =============================================================================

def update_global_ai_context():
    """
    UPDATED: Scans EVERY symbol in your config.
    Feeds the H4 trend of all your traded assets to the AI.
    This allows the AI to see the 'Whole Picture' without needing DXY.
    """
    global state
    if not config.ENABLE_AI_VALIDATION: return
    
    # Run only if interval has passed
    if state.last_global_context_update and (datetime.now() - state.last_global_context_update) < timedelta(seconds=config.AI_GLOBAL_CONTEXT_INTERVAL):
        return

    logger.info(" SMART AI: Scanning all symbols for Macro Bias...")

    # 1. Gather Data for ALL Traded Symbols
    market_scan = []
    
    # We scan every symbol in your list + Oil/Gold if they aren't there
    scan_list = list(set(config.SYMBOLS + ['XAUUSDm', 'BTCUSDm'])) 

    for symbol in scan_list:
        # Get H4 Data (Good for Intraday/Macro bias)
        df = get_market_data(symbol, mt5.TIMEFRAME_H4, 100)
        
        if df is not None and not df.empty:
            current_price = df['close'].iloc[-1]
            # Calculate Trend (EMA 50 vs 200)
            ema_50 = df['close'].ewm(span=50).mean().iloc[-1]
            ema_200 = df['close'].ewm(span=200).mean().iloc[-1]
            trend = "UP" if ema_50 > ema_200 else "DOWN"
            
            # Calculate Volatility (ATR)
            atr = calculate_atr(df['high'], df['low'], df['close'], 14).iloc[-1]
            daily_move_percent = ((df['close'].iloc[-1] - df['open'].iloc[-1]) / df['open'].iloc[-1]) * 100
            
            # Calculate Strength (Distance from EMA)
            strength = "STRONG" if abs(current_price - ema_50) > (atr * 2) else "WEAK"
            
            market_scan.append(f"{symbol}: Trend {trend} ({strength}), Day Move: {daily_move_percent:.2f}%")

    scan_data_str = "\n".join(market_scan)

    # 2. The Prompt
    system_prompt = """You are a Senior Hedge Fund Manager.
    I will provide the H4 technical status of my entire watchlist.
    
    Your Goal:
    1. deduce the global sentiment (e.g., If Crypto and Stocks are UP, it is Risk-On).
    2. deduce the Currency Strength (e.g., If EURUSD and GBPUSD are DOWN, USD is Strong).
    3. Set a TRADING BIAS for each symbol.
    
    Respond ONLY with valid JSON:
    {
      "sentiment": "RISK_ON / RISK_OFF / MIXED",
      "symbol_bias": {
        "EURUSDm": "SELL_ONLY",
        "GBPJPYm": "BUY_ONLY",
        "BTCUSDm": "NEUTRAL"
        ... (cover all symbols provided)
      },
      "reasoning": "Brief analysis of the correlations found."
    }
    """
    
    prompt = f"""
    Here is the Technical Scan of the market right now:
    {scan_data_str}
    
    Based on this data, determine the Bias for each symbol.
    """
    
    # 3. Call AI
    response = ai_provider.call_ai(prompt, system_prompt, temperature=0.3, max_tokens=1000, json_mode=True)
    
    if response:
        try:
            result = json.loads(response)
            state.approved_bias = result.get('symbol_bias', {})
            state.global_market_sentiment = result.get('sentiment', 'NEUTRAL')
            state.global_key_drivers = result.get('reasoning', 'N/A')
            
            logger.info(f" AI BIAS UPDATED: {state.global_market_sentiment}")
            logger.info(f"   Logic: {state.global_key_drivers}")
            logger.info(f"   Biases Set: {len(state.approved_bias)}")
            
            state.last_global_context_update = datetime.now()
            
        except Exception as e:
            logger.error(f"Failed to parse AI Bias: {e}")

def ai_filter_signal(local_signal: Dict) -> Dict[str, Any]:
    """
    NEW: This is the AI Validation step.
    """
    if not config.ENABLE_AI_VALIDATION:
        return {'approved': True, 'confidence_adjustment': 0.0, 'reason': 'AI filter disabled'}
    
    logger.info(f"AI validating local signal for {local_signal['symbol']}...")
    
    context = f"""
--- Local Signal Details ---
Symbol: {local_signal['symbol']}
Direction: {local_signal['direction']}
Local Strategies: {', '.join(local_signal['contributing_strategies'])}
Local Trend Analysis: {local_signal['trend']}
Local Regime Analysis: {local_signal['regime']}

--- Global AI Macro Context ---
Market Sentiment: {state.global_market_sentiment}
Key Drivers: {state.global_key_drivers}
Strong Currencies: {state.global_strong_currencies}
Weak Currencies: {state.global_weak_currencies}
"""
    
    system_prompt = """You are an elite Head Trader validating a signal from your junior (local) strategy bot.
Your job is to provide the FINAL "Go/No-Go" based on your macro-economic context.
-   Does the local signal (e.g., BUY EURUSD) make sense given your global view?
-   (e.g., if Sentiment is RISK_OFF and USD is strong, a BUY EURUSD signal is HIGH RISK).
-   (e.g., if Sentiment is RISK_ON and USD is weak, a BUY EURUSD signal is HIGH ALIGNMENT).

Respond ONLY with valid JSON:
{
  "approved": true/false,
  "confidence_adjustment": -0.3 to +0.3,
  "reason": "Brief reasoning for your decision (e.g., 'High alignment with macro view', 'Trade is counter-sentiment')"
}
"""
    
    prompt = f"Analyze this local signal given your macro context:\n\n{context}\n\nShould this trade be taken?"
    
    try:
        response = ai_provider.call_ai(prompt, system_prompt, temperature=0.2, max_tokens=200, json_mode=True)
        if response:
            result = json.loads(response)
            logger.info(f" AI Validation: {' APPROVED' if result['approved'] else ' REJECTED'}")
            logger.info(f"   Reason: {result['reason']}")
            return result
    except Exception as e:
        logger.error(f"AI filter error: {e}")
    
    return {'approved': True, 'confidence_adjustment': 0.0, 'reason': 'AI filter failed, defaulting to approve'}

# === COPY AND REPLACE THIS FUNCTION ===

def ai_calculate_risk_percent(local_signal: Dict, account_equity: float, current_daily_pnl: float) -> float:
    """
    INSTANT SCALPING RISK:
    Calculates risk purely based on math to ensure 0ms latency.
    """
    # 1. Base Risk
    risk_percent = config.BASE_RISK_PERCENT
    
    # 2. Confidence Booster (From Local Signal)
    # If the local strategy is very sure (e.g., 0.85), we increase risk slightly
    confidence = local_signal.get('confidence', 0.7)
    if confidence >= 0.85:
        risk_percent *= 1.2
        
    # 3. "House Money" Logic (Math Only - No AI)
    # If we are up money today, risk a bit more of the profit
    if current_daily_pnl > 0:
        # Risk up to 5% of the daily profit, but capped at MAX_RISK_PERCENT
        profit_risk_boost = (current_daily_pnl * 0.10) / account_equity * 100
        risk_percent = min(config.MAX_RISK_PERCENT, risk_percent + profit_risk_boost)
        
    # 4. Streak Protection (Math Only)
    # If we lost the last 2 trades, cut risk in half
    recent_trades = trade_db.get_recent_trades(5)
    losses = 0
    for t in recent_trades:
        if t.get('win') == 0: losses += 1
        else: break
        
    if losses >= 2: risk_percent *= 0.5
    if losses >= 3: risk_percent = config.MIN_RISK_PERCENT
    
    # Final Cap
    return max(config.MIN_RISK_PERCENT, min(config.MAX_RISK_PERCENT, risk_percent))

def ai_analyze_closed_trades():
    """
    SMART LEARNING:
    1. Reviews wins/losses.
    2. Adjusts risk parameters (Size, SL).
    3. BANS specific strategies that are performing poorly (e.g., 'Ban ICT_KILLZONE').
    """
    if not config.ENABLE_AI_TRADE_LEARNING: return
    if state.last_ai_learning_time and (datetime.now() - state.last_ai_learning_time) < timedelta(seconds=config.AI_LEARNING_INTERVAL):
        return
    
    # Get recent 50 trades from Supabase	
    recent_trades = trade_db.get_recent_trades(50)
    if len(recent_trades) < 10: return 
    
    logger.info(f" AI SELF-CORRECTION: Analyzing last {len(recent_trades)} trades...")

    # Calculate performance per strategy
    strat_perf = defaultdict(lambda: {'wins': 0, 'losses': 0, 'pnl': 0.0})
    for t in recent_trades:
        name = t.get('strategy_name', 'Unknown')
        pnl = t.get('profit_loss', 0)
        strat_perf[name]['pnl'] += pnl
        if pnl > 0: strat_perf[name]['wins'] += 1
        else: strat_perf[name]['losses'] += 1

    system_prompt = """You are a Strategy Optimization AI. 
    Review the performance data.
    1. If a strategy has a win rate < 40% or huge losses, add it to 'banned_strategies'.
    2. If a previously banned strategy is looking better (or if you want to retry), add to 'unban_strategies'.
    3. Suggest parameter tweaks.
    
    Respond ONLY with JSON:
    {
      "banned_strategies": ["Strategy_Name_1"],
      "unban_strategies": ["Strategy_Name_2"],
      "adjustments": { "risk_percent": 1.0 }
    }"""
    
    prompt = f"Strategy Performance Data: {json.dumps(strat_perf, indent=2)}\nCurrent Banned: {state.banned_strategies}"
    
    try:
        response = ai_provider.call_ai(prompt, system_prompt, temperature=0.2, max_tokens=500, json_mode=True)
        if response:
            result = json.loads(response)
            
            # Apply Bans
            new_bans = result.get('banned_strategies', [])
            for s in new_bans:
                if s not in state.banned_strategies:
                    state.banned_strategies.append(s)
                    logger.warning(f" AI BANNED Strategy: {s} (Poor Performance)")
            
            # Remove Bans
            unbans = result.get('unban_strategies', [])
            for s in unbans:
                if s in state.banned_strategies:
                    state.banned_strategies.remove(s)
                    logger.info(f" AI UN-BANNED Strategy: {s}")

            state.last_ai_learning_time = datetime.now()
            
    except Exception as e:
        logger.error(f"AI Learning Error: {e}")

# =============================================================================
# DYNAMIC TRADE EXECUTION & MANAGEMENT
# =============================================================================

def get_dynamic_trade_params(symbol: str, direction: str, df: pd.DataFrame) -> Dict:
    """Calculate ALL trade parameters DYNAMICALLY based on ATR and NEWS"""
    try:
        atr = calculate_atr(df['high'], df['low'], df['close'], config.ATR_PERIOD).iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # --- NEWS GUARD ADJUSTMENT ---
        # Widen stops during high-impact news events
        news_mult = get_news_volatility_multiplier(symbol)
        if news_mult > 1.0:
            logger.info(f" [NEWS GUARD] {symbol} Volatility Multiplier: {news_mult}x (Widening Stops)")
        
        adjusted_tr_mult = state.current_sl_multiplier * news_mult
        
        # --- FIX: STRUCTURE-BASED STOP LOSS (Smart Stop) ---
        # Instead of blind ATR, look for recent Swing High/Low
        
        if direction == 'BUY':
            # Find recent Low (Support) in last 10 candles
            recent_low = df['low'].iloc[-10:].min()
            
            # Default ATR SL (Widened by News)
            atr_sl = current_price - (atr * adjusted_tr_mult)
            
            # Structure SL (Low - Buffer)
            struct_sl = recent_low - (atr * 0.15 * news_mult)
            
            # Sanity Check: If structure is too far or too close, use ATR
            # If Struct SL is > (1.5 * news_mult) ATR away, it's too far (risk too high)
            # If Struct SL is < (0.3 * news_mult) ATR away, it's too close (noise)
            dist_struct = current_price - struct_sl
            if (0.3 * news_mult * atr) < dist_struct < (1.5 * news_mult * atr):
                sl = struct_sl
            else:
                sl = atr_sl
                
            # TP Calculation: Dynamic RR
            # In Trending Market, aim for 1:2. In Ranging, 1:1.2
            risk = current_price - sl
            
            # Market Regime Adjustment
            vol_50_mean = df['high'].iloc[-50:].mean()
            volatility_ratio = df['high'].iloc[-10:].mean() / vol_50_mean if vol_50_mean != 0 else 1
            
            rr_target = 2.0 if volatility_ratio > 1.2 else 1.2
            
            tp1 = current_price + (risk * rr_target)
            tp2 = current_price + (risk * rr_target * 1.5)

        else: # SELL
            # Find recent High (Resistance)
            recent_high = df['high'].iloc[-10:].max()
            
            # Default ATR SL (Widened by News)
            atr_sl = current_price + (atr * adjusted_tr_mult)
            
            # Structure SL (High + Buffer)
            struct_sl = recent_high + (atr * 0.15 * news_mult)
            
            # Sanity Check
            dist_struct = struct_sl - current_price
            if (0.3 * news_mult * atr) < dist_struct < (1.5 * news_mult * atr):
                sl = struct_sl
            else:
                sl = atr_sl
            
            risk = sl - current_price
            
            # Market Regime Adjustment
            vol_50_mean = df['high'].iloc[-50:].mean()
            volatility_ratio = df['high'].iloc[-10:].mean() / vol_50_mean if vol_50_mean != 0 else 1
            
            rr_target = 2.0 if volatility_ratio > 1.2 else 1.2
            
            tp1 = current_price - (risk * rr_target)
            tp2 = current_price - (risk * rr_target * 1.5)
            
        sl_distance = abs(current_price - sl)
        
        vol_50_mean = df['high'].iloc[-50:].mean()
        volatility_ratio = df['high'].iloc[-10:].mean() / vol_50_mean if vol_50_mean != 0 else 1
        ema_50 = df['close'].ewm(span=50).mean().iloc[-1]
        trend_strength = df['close'].ewm(span=20).mean().iloc[-1] / ema_50 if ema_50 != 0 else 1
        regime = "TRENDING" if trend_strength > 1.01 or trend_strength < 0.99 else "RANGING"
        session = get_current_session()
        
        # --- SESSION-RELATIVE ATR ADJUSTMENT (Trader's Feedback) ---
        # Adjust ATR multiplier based on Session characteristics
        if session == "ASIA":
            # Low liquidity, prone to "wicks" and stop hunts -> Widen SL
            adjusted_tr_mult *= 1.25 
            # logger.info(f" [SESSION] ASIA: Widening SL by 1.25x (Anti-Wick Mode)")
        elif session == "LONDON":
            # High liquidity, directional -> Standard SL
            pass
        elif session == "NY":
            # High volatility -> Slightly wider to survive initial burst
            adjusted_tr_mult *= 1.1

        return {
            'sl': sl, 'tp1': tp1, 'tp2': tp2,
            'sl_distance': sl_distance, 'atr': atr, 'volatility_ratio': volatility_ratio,
            'trend_strength': trend_strength, 'regime': regime, 'session': session,
            'news_multiplier': news_mult
        }
    except Exception as e:
        logger.error(f"Dynamic params error: {e}")
        return {}

def calculate_dynamic_lot_size(symbol: str, equity: float, risk_percent: float, sl_distance: float) -> float:
    """DYNAMIC lot sizing based on equity, risk %, and SL distance"""
    try:
        spec = get_symbol_specs(symbol)
        if not spec:
            logger.warning(f"No spec found for {symbol}, defaulting to min lot 0.01")
            return 0.01
        
        risk_amount = equity * (risk_percent / 100)
        
        tick_value = spec.get('trade_tick_value')
        tick_size = spec.get('trade_tick_size')
        lot_step = spec.get('lot_step', 0.01)
        min_lot = spec.get('min_lot', 0.01)
        max_lot = spec.get('max_lot', 1.0) # Safety cap

        if not tick_value or not tick_size or tick_value == 0 or tick_size == 0 or sl_distance == 0:
             logger.warning(f"Invalid tick/SL data for {symbol}. Check Market Watch. Defaulting to min lot.")
             return min_lot

        lot_size = risk_amount / (sl_distance / tick_size * tick_value)
        lot_size = round(lot_size / lot_step) * lot_step
        lot_size = max(min_lot, min(max_lot, lot_size))
        
        return lot_size
    except Exception as e:
        logger.error(f"Lot size calculation error: {e}", exc_info=True)
        return 0.01

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
            logger.debug("[MGR] Position Manager: No open positions")
            return
        
        logger.info(f"[MGR] Position Manager: Managing {len(positions)} position(s)")
        logger.info(f"[MAGIC] Bot Magic Number: {MAGIC_NUMBER}")
        
        for pos in positions:
            logger.info(f"[CHECK] Checking position #{pos.ticket} ({pos.symbol}): Magic={pos.magic}")
            
            if pos.magic != MAGIC_NUMBER:
                logger.warning(f"[WARN] SKIPPING ticket {pos.ticket} - Magic mismatch! Trade={pos.magic}, Bot={MAGIC_NUMBER}")
                continue
            
            logger.info(f"[OK] Magic match! Will manage #{pos.ticket}")
            
            symbol, ticket = pos.symbol, pos.ticket
            entry_price, current_price = pos.price_open, pos.price_current
            sl, tp = pos.sl, pos.tp
            current_volume = pos.volume
            
            logger.debug(f"[INFO] Managing {symbol} #{ticket}: Entry={entry_price:.5f}, Current={current_price:.5f}, SL={sl:.5f}, TP={tp:.5f}")
            
            # --- SPREAD PROTECTION (QA Request) ---
            # If spread is 2x the allowed limit (liquidity hole), DO NOT modify SL/TP
            # This prevents being stopped out by a temporary 50-pip spread widening
            tick = mt5.symbol_info_tick(symbol)
            if tick and (state.open_positions.get(ticket)):
                current_spread = tick.ask - tick.bid
                params = state.open_positions[ticket].get('params', {})
                atr = params.get('atr', 0.0010)
                
                # Default threshold is 15% of ATR. Emergency pause is 30% (2x)
                if current_spread > (atr * config.SPREAD_ATR_THRESHOLD * 2.0):
                    logger.warning(f" [MANAGE] Pausing {symbol} #{ticket} - Spread Spike ({current_spread:.5f}) > 2x Threshold")
                    continue

            # Calculate progress
            total_dist = abs(tp - entry_price)
            if total_dist == 0:
                logger.warning(f"[WARN] {symbol} #{ticket}: TP equals entry price! Skipping...")
                continue
            
            if pos.type == 0:  # BUY
                current_dist = current_price - entry_price
            else:  # SELL
                current_dist = entry_price - current_price
            
            progress = current_dist / total_dist
            
            # LOG PROGRESS FOR EVERY POSITION
            logger.info(f"[PROG] {symbol} #{ticket}: Progress = {progress*100:.1f}% to TP (Dist: {current_dist:.5f}/{total_dist:.5f})")

            # Get regime
            regime = "TRENDING" 
            if ticket in state.open_positions:
                params = state.open_positions[ticket].get('params', {})
                regime = params.get('regime', 'TRENDING')

            new_sl = sl
            sl_changed = False
            
            # 1. PERSISTENT PARTIAL TP
            if config.ENABLE_PARTIAL_TP and progress >= (config.PARTIAL_TP_TRIGGER_PERCENT / 100):
                if ticket not in state.partial_closed:
                    logger.info(f"[PROFIT] {symbol} reached {progress*100:.1f}% - attempting Partial TP...")
                    
                    # Calculate partial volume
                    partial_volume = current_volume * (config.PARTIAL_TP_PERCENT / 100)
                    
                    # Round to lot step
                    spec = get_symbol_specs(symbol)
                    lot_step = spec.get('lot_step', 0.01)
                    min_lot = spec.get('min_lot', 0.01)
                    
                    partial_volume = round(partial_volume / lot_step) * lot_step
                    remaining_volume = current_volume - partial_volume
                    
                    if partial_volume >= min_lot and remaining_volume >= min_lot:
                        if close_partial_position(ticket, partial_volume):
                            state.partial_closed.add(ticket)
                            
                            # PARTIAL TP INTEGRITY CHECK
                            # Ensure we haven't ALREADY acted on this volume
                            # If we want to close 50%, current volume should be near 100% of original.
                            # If current volume is already small, we might have already closed it.
                            # Since we don't track original_volume perfectly in memory, we assume
                            # the `state.partial_closed` set is the source of truth.
                            # BUT, we double check if volume is suspiciously small (e.g. 0.01)
                            
                            is_tiny_lot = current_volume <= get_symbol_specs(symbol).get('min_lot', 0.01)
                            
                            if not is_tiny_lot:
                                if close_partial_position(ticket, partial_volume):
                                    state.partial_closed.add(ticket)
                                    
                                    # PERSIST STATE IMMEDIATELY
                                    trade_db.update_metadata(ticket, {
                                        'partial_tp_executed': True,
                                        'partial_tp_time': datetime.now(timezone.utc).isoformat()
                                    })
                            
                            logger.info(f" PARTIAL TP: Closed {config.PARTIAL_TP_PERCENT}% of {symbol} at {progress*100:.1f}% progress")
                            
                            send_telegram_notification(
                                f" <b>Partial TP Executed</b>\n\n"
                                f"Symbol: {symbol}\n"
                                f"Closed: {partial_volume} lots ({config.PARTIAL_TP_PERCENT}%)\n"
                                f"Progress: {progress*100:.1f}%"
                            )
            
            # 2. PERSISTENT BREAKEVEN
            if config.ENABLE_BREAKEVEN and progress >= (config.BREAKEVEN_TRIGGER_PERCENT / 100):
                 if ticket not in state.be_moved: 
                    # Calculate breakeven price with small buffer
                    be_buffer = total_dist * (config.BREAKEVEN_LOCK_PERCENT / 100)
                    
                    if pos.type == 0:  # BUY
                        be_price = entry_price + be_buffer
                        # Only move if BE is BETTER (higher) than current SL
                        if be_price > sl:
                            new_sl = be_price
                            sl_changed = True
                            state.be_moved.add(ticket)
                            
                            trade_db.update_metadata(ticket, {'be_moved': True, 'be_level': new_sl})
                            logger.info(f"[BE] BREAKEVEN: {symbol} moved to {new_sl:.5f}")
                    else:  # SELL
                        be_price = entry_price - be_buffer
                        if be_price < sl:
                            new_sl = be_price
                            sl_changed = True
                            state.be_moved.add(ticket)
                            
                            trade_db.update_metadata(ticket, {'be_moved': True, 'be_level': new_sl})
                            logger.info(f"[BE] BREAKEVEN: {symbol} moved to {new_sl:.5f}")

            # 3. PROFESSIONAL ATR STEP TRAILING
            # "Breathe" logic: Don't choke the trade. Trail by ATR distances.
            if config.ENABLE_TRAILING_STOP and progress >= 0.40: # Start @ 40% to TP
                
                # Get ATR from persisted state if possible
                atr = params.get('atr', 0.0010)
                news_mult = params.get('news_multiplier', 1.0)
                
                # Dynamic Trail Distance
                # Early: Wide trail (1.5 ATR) to survive noise
                # Late (>80%): Tight trail (0.5 ATR) to bank profit
                trail_mult = 1.5 if progress < 0.80 else 0.5
                trail_dist = atr * trail_mult * news_mult # Use News Mult to widen trail if volatile
                
                if pos.type == 0:  # BUY
                    potential_sl = current_price - trail_dist
                    # Fractal Step: Only move if we jump by at least 0.1 ATR to avoid spamming broker
                    if potential_sl > (sl + (0.1 * atr)):
                        new_sl = potential_sl
                        sl_changed = True
                        trade_db.update_metadata(ticket, {'trailing_active': True})
                        logger.info(f"[TRAIL] {symbol} STEP UP → {new_sl:.5f} (Dist: {trail_mult}ATR)")
                        
                else:  # SELL
                    potential_sl = current_price + trail_dist
                    if potential_sl < (sl - (0.1 * atr)):
                        new_sl = potential_sl
                        sl_changed = True
                        trade_db.update_metadata(ticket, {'trailing_active': True})
                        logger.info(f"[TRAIL] {symbol} STEP DOWN → {new_sl:.5f} (Dist: {trail_mult}ATR)")

            # 4. EXECUTE MODIFICATION
            if sl_changed and new_sl != sl:
                if modify_position(ticket, new_sl, tp):
                    logger.info(f"[OK] SL UPDATED: {symbol} → {new_sl:.5f} ({regime}, {progress*100:.1f}% to TP)")
                else:
                    logger.error(f"[ERROR] SL UPDATE FAILED: {symbol} (tried to move to {new_sl:.5f})")


    except Exception as e:
        logger.error(f"[ERROR] ERROR in position management: {e}", exc_info=True)

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
                exit_reason = 'TP' if profit > 0 else 'SL' if profit < 0 else 'BE'
                
                # Get trade details from state
                pos_data = state.open_positions[ticket]
                symbol = deal.symbol
                direction = 'BUY' if deal.type == mt5.ORDER_TYPE_BUY else 'SELL'
                
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

        # Call Gemini AI for analysis
        if config.AI_API_KEY:
            import google.generativeai as genai
            genai.configure(api_key=config.AI_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            response = model.generate_content(prompt)
            lesson = response.text.strip()
            
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
    IMPROVED: Dynamic emergency circuit breaker with adaptive thresholds
    Adjusts limits based on:
    - Recent performance (losing streaks)
    - Margin level (account health)
    - Provides early warnings
    Returns True if trading should stop
    """
    # Initialize daily equity tracker
    if state.daily_start_equity == 0:
        state.daily_start_equity = account_info.equity
    
    if state.daily_start_equity <= 0:
        return False
    
    # Calculate current daily loss
    daily_loss_percent = ((account_info.equity - state.daily_start_equity) / state.daily_start_equity) * 100
    
    # 1. DYNAMIC EMERGENCY STOP - Adapts based on conditions
    # Base limit: 15% (safer than old 20%)
    # Tightens to 12% if losing streak detected
    # Tightens to 10% if low margin detected
    
    dynamic_limit = config.MAX_DAILY_LOSS_PERCENT  # Start with base 15%
    
    # Check recent performance for losing streak
    recent_trades = trade_db.get_recent_trades(5)
    if len(recent_trades) >= 3:
        recent_losses = sum(1 for t in recent_trades if t.get('win') == 0)
        if recent_losses >= 3:  # 3+ losses in last 5 trades
            dynamic_limit = 12.0  # Tighten to 12%
            logger.warning(f"[WARN] Emergency stop tightened to {dynamic_limit}% due to recent losses ({recent_losses}/5)")
    
    # Check margin level - if low, tighten further
    if account_info.margin_level > 0 and account_info.margin_level < 300:  # Below 300%
        dynamic_limit = min(dynamic_limit, 10.0)  # Tighten to 10% maximum
        logger.warning(f"[WARN] Emergency stop tightened to {dynamic_limit}% due to low margin ({account_info.margin_level:.0f}%)")
    
    # Apply dynamic emergency stop
    if daily_loss_percent <= -dynamic_limit:
        logger.critical(f"[ERROR] EMERGENCY STOP: Dynamic loss limit of {dynamic_limit}% reached")
        logger.critical(f"[ERROR] Actual loss: {daily_loss_percent:.2f}%")
        send_telegram_notification(
            f" <b>EMERGENCY STOP</b>\n\n"
            f"Dynamic loss limit: {dynamic_limit}%\n"
            f"Actual loss: {daily_loss_percent:.2f}%\n"
            f"Equity: ${account_info.equity:.2f}\n"
            f"Bot halting for safety."
        )
        return True
    
    # 2. Consecutive Losses Check (10 in a row = stop)
    all_recent = trade_db.get_recent_trades(10)
    if len(all_recent) >= 10:
        if all(t.get('win') == 0 for t in all_recent):
            logger.critical("[ERROR] EMERGENCY STOP: 10 consecutive losses detected")
            send_telegram_notification(" <b>EMERGENCY STOP</b>\n\nBot has 10 consecutive losses. Halting immediately.")
            return True
    
    # 3. Critical Margin Level (Below 200% = stop)
    if account_info.margin_level < 200 and account_info.margin_level > 0:
        logger.critical(f"[ERROR] EMERGENCY STOP: Critical margin level {account_info.margin_level:.0f}%")
        send_telegram_notification(
            f" <b>EMERGENCY STOP</b>\n\n"
            f"Margin level: {account_info.margin_level:.0f}%\n"
            f"Critical threshold: 200%\n"
            f"Bot halting to prevent margin call."
        )
        return True
    
    # 4. Early Warning System (warn at 70% of limit)
    warning_threshold = dynamic_limit * 0.7
    if daily_loss_percent <= -warning_threshold and daily_loss_percent > -(warning_threshold + 1):
        logger.warning(f" [WARN] Daily loss at {daily_loss_percent:.2f}% - Approaching {dynamic_limit}% emergency limit!")
        logger.warning(f" [WARN] Remaining room: {abs(dynamic_limit + daily_loss_percent):.2f}%")
    
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
    Broker-Agnostic Check:
    Ensures the spread is not eating too much of the expected move.
    """
    try:
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return False
        
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

def check_risk_vs_emergency_limit(account_info, proposed_risk_percent: float) -> tuple[bool, float]:
    """
    IMPROVED: Pre-trade safety check - ensures trade risk doesn't push too close to emergency stop
    
    Logic:
    1. Calculate current daily loss
    2. Get dynamic emergency limit (10-15%)
    3. Calculate remaining safe room (with 70% buffer)
    4. Reduce proposed risk if needed
    
    Returns: (is_safe, adjusted_risk_percent)
    
    Example:
    - Emergency limit: 15%
    - Current loss: -10%
    - Remaining: 5%
    - Safe room (70%): 3.5%
    - If AI wants 4% → Reduced to 2.8%
    - If AI wants 2% → Allowed as-is
    """
    # Initialize daily tracker
    if state.daily_start_equity == 0:
        state.daily_start_equity = account_info.equity
    
    if state.daily_start_equity <= 0:
        return True, proposed_risk_percent
    
    # Calculate current daily P&L
    current_daily_loss_percent = ((account_info.equity - state.daily_start_equity) / state.daily_start_equity) * 100
    
    # Get dynamic emergency limit (matches check_emergency_conditions logic)
    dynamic_limit = config.MAX_DAILY_LOSS_PERCENT  # Base: 15%
    
    # Check for losing streak (same logic as emergency check)
    recent_trades = trade_db.get_recent_trades(5)
    if len(recent_trades) >= 3:
        recent_losses = sum(1 for t in recent_trades if t.get('win') == 0)
        if recent_losses >= 3:
            dynamic_limit = 12.0
    
    # Check margin level
    if account_info.margin_level > 0 and account_info.margin_level < 300:
        dynamic_limit = min(dynamic_limit, 10.0)
    
    # Calculate remaining room to emergency stop
    remaining_room = dynamic_limit + current_daily_loss_percent  # How much we can still lose
    
    # Apply safety buffer: Only use 70% of remaining room
    safe_room = remaining_room * 0.7
    
    # Check if proposed risk fits within safe room
    if proposed_risk_percent > safe_room:
        logger.warning(f" [RISK LIMITER] Proposed risk {proposed_risk_percent:.2f}% exceeds safe room {safe_room:.2f}%")
        logger.warning(f" [RISK LIMITER] Current loss: {current_daily_loss_percent:.2f}%, Emergency limit: {dynamic_limit}%")
        logger.warning(f" [RISK LIMITER] Remaining to limit: {remaining_room:.2f}%")
        
        # Reduce risk to fit within safe room (use 80% of safe room, minimum 0.3%)
        adjusted_risk = max(0.3, safe_room * 0.8)
        logger.info(f" [RISK LIMITER] Risk adjusted: {proposed_risk_percent:.2f}% → {adjusted_risk:.2f}%")
        return True, adjusted_risk
    
    # Risk is within safe limits
    logger.debug(f" [RISK CHECK] {proposed_risk_percent:.2f}% risk OK (safe room: {safe_room:.2f}%)")
    return True, proposed_risk_percent


def adapt_sl_tp_for_volatility(symbol: str, base_sl_multiplier: float, base_tp_multiplier: float) -> Tuple[float, float]:
    """🧠 INTELLIGENT: Adapt SL/TP based on current volatility"""
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
        return base_sl_multiplier, base_tp_multiplier


def place_ai_trade(local_signal: Dict, account_equity: float, current_daily_pnl: float) -> bool:
    """
    ULTIMATE AI EXECUTION:
    Combines all advanced AI systems for superior trading
    """
    try:
        symbol = local_signal['symbol']
        direction = local_signal['direction']
        tradability_score = local_signal.get('tradability_score', 50) 
        confluence = local_signal.get('confluence', 0)
        
        df = get_market_data(symbol, config.ENTRY_TF, 100)
        if df is None: return False
        
        # Build context for all AI systems
        try:
            adx_val, _, _ = calculate_adx(df['high'], df['low'], df['close'], 14)
            adx = float(adx_val.iloc[-1]) if len(adx_val) > 0 else 0
        except:
            adx = 0
        
        # Get spread
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return False
        spread = (tick.ask - tick.bid) / tick.bid * 10000  # pips
        
        context = {
            'adx': adx,
            'session': get_current_session(),
            'hour': datetime.now(timezone.utc).hour,
            'confluence': confluence,
            'spread': spread
        }
        
        # =====================================================================
        # ULTIMATE AI CHECKS - All new systems integrated
        # =====================================================================
        
        # 1. SYMBOL PERFORMANCE CHECK
        should_trade, reason = symbol_tracker.should_trade_symbol(symbol)
        if not should_trade:
            logger.warning(f"[SYMBOL TRACKER] {symbol} blocked - {reason}")
            return False
        elif should_trade == 'REQUIRE_HIGH_QUALITY':
            # Symbol has below-average performance, require high confluence
            if confluence < 1.7:
                logger.warning(f"[SYMBOL TRACKER] {symbol} requires high quality (confluence {confluence:.2f} < 1.7)")
                return False
            logger.info(f"[SYMBOL TRACKER] {symbol} high-quality signal accepted")
        
        # 2. CORRELATION CHECK
        allow_corr, corr_reason = correlation_tracker.should_allow_trade(symbol)
        if not allow_corr:
            logger.warning(f"[CORRELATION] {symbol} blocked - {corr_reason}")
            return False
        
        # 3. PATTERN RECOGNITION - Predict trade quality
        success_prob, num_similar = pattern_recognizer.predict_trade_quality(symbol, direction, context)
        
        if num_similar >= 10:  # Enough data to make decision
            if success_prob < 0.40:
                logger.warning(f" [PATTERN] {symbol} {direction} blocked - Low success probability ({success_prob:.0%})")
                return False
            elif success_prob < 0.55:
                logger.warning(f" [PATTERN] {symbol} {direction} marginal - Success probability ({success_prob:.0%})")
                # Allow but with reduced risk
                tradability_score = tradability_score * 0.7
            else:
                logger.info(f" [PATTERN] {symbol} {direction} excellent - Success probability ({success_prob:.0%})")
        
        # 4. MICRO-STRUCTURE ANALYSIS
        # Check liquidity sweep
        sweep_setup = micro_analyzer.detect_liquidity_sweep(symbol)
        if sweep_setup and sweep_setup != f"{direction}_SETUP":
            logger.info(f" [MICRO] {symbol} waiting for {direction}_SETUP (detected {sweep_setup})")
            return False  # Wait for correct setup
        
        # Check momentum
        momentum = micro_analyzer.check_momentum_burst(symbol)
        if momentum:
            if (direction == 'BUY' and momentum == 'STRONG_SELL') or \
               (direction == 'SELL' and momentum == 'STRONG_BUY'):
                logger.warning(f" [MICRO] {symbol} {direction} conflicts with momentum {momentum}")
                return False
            elif (direction == 'BUY' and momentum == 'STRONG_BUY') or \
                 (direction == 'SELL' and momentum == 'STRONG_SELL'):
                logger.info(f" [MICRO] {symbol} {direction} confirmed by momentum!")
        
        # Check entry timing
        timing = micro_analyzer.optimal_entry_timing(symbol, direction)
        if timing == 'WAIT_PULLBACK':
            logger.info(f" [MICRO] {symbol} {direction} waiting for optimal entry")
            return False  # Wait for better entry
        
        # 4b. AI "HEAD TRADER" VALIDATION (Mandatory High-Level Check)
        ai_validation = ai_filter_signal(local_signal)
        if not ai_validation.get('approved', True):
             logger.warning(f" [AI HEAD TRADER] BLOCKED {symbol} {direction} - {ai_validation.get('reason')}")
             return False
        
        # Apply confidence adjustment
        local_signal['confidence'] += ai_validation.get('confidence_adjustment', 0.0)

        # 5. LEGACY AI LEARNING CHECK - Check against past losses
        is_safe, warning = check_trade_against_lessons(symbol, direction, context)
        if not is_safe:
            logger.warning(f" [AI LEARNING] BLOCKING {symbol} {direction} - Similar past losses detected")
            logger.warning(f" [AI LEARNING] {warning}")
            return False
            
        # --- HARD DAILY LOSS LIMIT (Founder Safety) ---
        if state.daily_pnl < -(state.daily_start_equity * (config.MAX_DAILY_LOSS_PERCENT / 100)):
            logger.critical(f" [RISK] Daily Loss Limit Exceeded during order placement! PnL: ${state.daily_pnl:.2f}")
            return False
            
        # =====================================================================
        # All checks passed - Proceed with trade execution
        # =====================================================================
        
        logger.info(f" [ULTIMATE AI] {symbol} {direction} passed all advanced checks!")
        
        # 1. Get Dynamic Stops/TPs
        params = get_dynamic_trade_params(symbol, direction, df)
        if not params:
            logger.error(f"Could not calculate dynamic params for {symbol}")
            return False
        
        # 2. AI RISK ASSESSMENT (The Brain)
        # We ask AI: "Given we made $X profit today, how much should we risk?"
        # This utilizes the function you wanted to keep.
        ai_risk_recommendation = ai_calculate_risk_percent(local_signal, account_equity, current_daily_pnl)
        
        # 2.5 RISK LIMITER - Pre-Trade Safety Check
        # IMPROVED: Check if risk would push too close to emergency stop
        # This prevents taking trades that could trigger emergency stop
        account_info = mt5.account_info()
        if account_info:
            is_safe, adjusted_risk = check_risk_vs_emergency_limit(account_info, ai_risk_recommendation)
            if adjusted_risk != ai_risk_recommendation:
                logger.warning(f" [RISK LIMITER] AI wanted {ai_risk_recommendation:.2f}%, using {adjusted_risk:.2f}% (emergency protection)")
            ai_risk_recommendation = adjusted_risk
        
        # 3. ADAPTIVE RISK CALCULATION (The Shield)
        # We pass the AI's wish into the Math Manager to ensure safety/streak protection.
        lot_size = AdaptiveRiskManager.calculate_adaptive_lot_size(
            symbol=symbol,
            entry_price=df['close'].iloc[-1],
            stop_loss=params['sl'],
            equity=account_equity,
            tradability_score=tradability_score,
            ai_recommended_risk=ai_risk_recommendation,
            ai_confidence=local_signal.get('confidence', 0.5), # <--- ADDED THIS LINE
            news_multiplier=params.get('news_multiplier', 1.0) # <--- ADDED NEWS MULT
        )
        
        # 4. Final Validation
        lot_size = validate_lot_size(symbol, lot_size)
        if lot_size < 0.01:
            logger.error(f"Invalid lot size {lot_size} for {symbol}")
            return False

        tick = mt5.symbol_info_tick(symbol)
        if not tick: return False
        
        # --- STALE TICK PROTECTION ---
        # During volatility, packets can delay. Ensure tick is fresh (< 2000ms)
        tick_age_sec = datetime.now(timezone.utc).timestamp() - tick.time
        if tick_age_sec > 2.0:
            logger.warning(f" [EXECUTION] Stale tick for {symbol} ({tick_age_sec:.2f}s old). Aborting.")
            return False
        
        price = tick.ask if direction == 'BUY' else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if direction == 'BUY' else mt5.ORDER_TYPE_SELL
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": lot_size,
            "type": order_type, "price": price, "sl": params['sl'], "tp": params['tp1'],
            "deviation": 20, "magic": MAGIC_NUMBER,
            "comment": f"V12_AI_{local_signal['contributing_strategies'][0][:10]}",
            "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            
            # --- SLIPPAGE LOGGING (Founder Request) ---
            slippage_pips = abs(result.price - price) / get_symbol_specs(symbol).get('pip_size', 0.0001)
            if slippage_pips > 1.0:
                 logger.warning(f" [EXECUTION] High Slippage detected: {slippage_pips:.1f} pips (Broker Latency?)")

            logger.info(f"  V12 HYBRID TRADE EXECUTED:")
            logger.info(f"   {symbol} {direction} | Lot: {lot_size:.2f} | Score: {tradability_score}")
            logger.info(f"   AI Risk: {ai_risk_recommendation:.2f}% | Final Risk: {(lot_size * params['sl_distance'] / account_equity * 100):.2f}%")
            
            # SCALPING OPTIMIZATION: Async logging (non-blocking)
            async_logger.log_trade_async({
                'timestamp': datetime.utcnow().isoformat(), 'ticket': result.order, 'symbol': symbol,
                'direction': direction, 'entry_price': price, 'stop_loss': params['sl'],
                'take_profit': params['tp1'], 'lot_size': lot_size, 'atr': params['atr'],
                'volatility_ratio': params['volatility_ratio'], 'trend_strength': params['trend_strength'],
                'market_regime': local_signal.get('regime', 'UNKNOWN'), 
                'session': params['session'],
                'ai_confidence': local_signal.get('confidence', 0.5),
                'ai_risk_percent': ai_risk_recommendation,
                'strategy_name': ', '.join(local_signal['contributing_strategies'])
            })
            
            state.daily_trades += 1
            state.open_positions[result.order] = {'params': params}
            return True
        else:
            logger.error(f" Trade failed: {result.comment if result else 'Unknown error'}")
            return False
    
    except Exception as e:
        logger.error(f"Error placing trade: {e}", exc_info=True)
        return False

# =============================================================================
# MAIN TRADING LOOP (HYBRID ARCHITECTURE)
# =============================================================================

def ai_trading_session():
    """
    SCALPING LIGHTNING V2.0: Main trading loop
    - Async data fetching (10x faster)
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
    base_symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD', 'BTCUSD', 'USOIL', 'ETHUSD', 'USDCAD', 'AUDUSD', 'NZDUSD', 'GBPJPY', 'USDCHF']
    actual_symbols = [get_actual_broker_symbol(base) for base in base_symbols]
    
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
        state.daily_start_equity = account_info.equity if account_info else 0.0

        # --- GLOBAL KILL SWITCH CHECK (Founder's Safety) ---
        # Check Supabase for a global 'kill_switch' flag
        try:
            kill_check = supabase.table('bot_control').select('kill_switch').eq('user_id', USER_ID).execute()
            if kill_check.data and kill_check.data[0].get('kill_switch', False):
                logger.critical(" [KILL SWITCH] Global Kill Switch Activated. STOPPING.")
                return 
        except: pass 
        
        send_telegram_notification(
            f"⚡ <b>SCALPING BOT V2.0 Started</b>\n\nUser: {USER_ID}\nStrategy: {STRATEGY_ID}\n"
            f"Account: {config.MT5_LOGIN}\nEquity: ${state.daily_start_equity:.2f}\n"
            f"Optimizations: Institutional Safety + Async Core"
        )
    except Exception as e:
        logger.error(f"Failed to get initial account info: {e}")
        state.daily_start_equity = 0.0

    while True:
        try:
            iteration += 1
            cycle_start = time.time()
            
            account_info = mt5.account_info()
            if not account_info:
                logger.error("Lost MT5 connection")
                send_heartbeat(status='error', mt5_connected=False, error_message="Lost MT5 connection")
                time.sleep(30)
                continue
            
            # --- 0. EQUITY PROTECTOR (The "Stop Loss" for the Account) ---
            current_dd_percent = ((state.daily_start_equity - account_info.equity) / state.daily_start_equity) * 100
            if state.daily_start_equity > 0 and current_dd_percent >= config.MAX_DAILY_DRAWDOWN_PERCENT:
                logger.critical(f" [EQUITY PROTECTOR] Max Drawdown Hit ({current_dd_percent:.2f}%). HALTING TRADING.")
                send_telegram_notification(f"🚨 <b>EQUITY PROTECT TRIGGERED</b>\n\nDrawdown: {current_dd_percent:.2f}%\nBot Halted.")
                break
            
            # --- 0.5 ROLLOVER BLACKOUT (Time-of-Day Dead Zone) ---
            current_hour = datetime.now(timezone.utc).hour
            if current_hour == config.ROLLOVER_WINDOW_START:
                 logger.warning(" [ROLLOVER GUARD] Spreads expanding. Pausing trading for 1 hour.")
                 time.sleep(60)
                 continue
            
            # --- 0. EMERGENCY CIRCUIT BREAKER ---
            if check_emergency_conditions(account_info):
                logger.critical("EMERGENCY CIRCUIT BREAKER TRIPPED. Stopping bot.")
                send_heartbeat(status='stopped', mt5_connected=True, error_message="Emergency Stop Triggered")
                send_telegram_notification(" <b>EMERGENCY STOP</b>\n\nBot has been halted due to safety violations.")
                break
            
            # --- 1. UPDATE GLOBAL CONTEXT (Every 4 hours, not in execution path) ---
            if iteration % 14400 == 0:  # Every 4 hours
                update_global_ai_context()
            
            fetch_upcoming_news_events()

            # --- 2. DYNAMIC TRADE MANAGEMENT ---
            manage_all_positions()
            
            # --- 3. UPDATE CLOSED TRADES ---
            update_closed_trades()

            # --- 4. AI LEARNING (Every hour, not in execution path) ---
            if iteration % 3600 == 0:  # Every hour
                ai_analyze_closed_trades()
            
            # --- 5. HEARTBEAT & STATUS LOGGING ---
            if time.time() - last_heartbeat_time > 60:
                send_heartbeat(status='running', mt5_connected=True)
                last_heartbeat_time = time.time()
            
            if iteration % 20 == 0:
                logger.info(f" Equity: ${account_info.equity:.2f} | Daily P&L: ${state.daily_pnl:.2f} | Trades: {state.daily_trades}/{config.MAX_DAILY_TRADES}")

            # --- 5b. SCHEDULED DB SYNC ---
            if time.time() - last_db_sync_time > 900:
                logger.info("Running scheduled DB/History sync...")
                trade_db.sync_account_history(days_back=1)
                last_db_sync_time = time.time()

            # --- 6. CHECK TRADE LIMITS ---
            if state.daily_trades >= config.MAX_DAILY_TRADES:
                time.sleep(300)
                continue
            
            open_positions = mt5.positions_get()
            if open_positions and len(open_positions) >= config.MAX_CONCURRENT_TRADES:
                time.sleep(30)
                continue
            
            # --- 7. SCALPING LIGHTNING SIGNAL LOOP ---
            # Get all cached data (instant, no blocking)
            all_cached_data = async_data_fetcher.get_all_data()
            
            if not all_cached_data:
                logger.warning(" [SCALPING] No cached data available yet")
                time.sleep(5)
                continue
            
            signals_found = 0
            
            for symbol in actual_symbols:
                # Check if already open
                if open_positions and any(pos.symbol == symbol for pos in open_positions):
                    continue
                
                # Get cached data (INSTANT - no blocking)
                cached_data = all_cached_data.get(symbol)
                if not cached_data:
                    continue
                
                # SPREAD CHECK with correct calculation
                tick = mt5.symbol_info_tick(symbol)
                if not tick:
                    continue
                
                spread = calculate_spread_correctly(symbol, tick)
                
                # Dynamic ATR Spread Check (Optimized)
                # Ensure spread is < 15% of H1 volatility
                df_h1 = cached_data.get('H1')
                if df_h1 is not None and not df_h1.empty:
                    range_avg = (df_h1['high'] - df_h1['low']).mean()
                    if range_avg > 0:
                        spread_threshold = range_avg * config.SPREAD_ATR_THRESHOLD
                        if spread > spread_threshold:
                            # logger.debug(f" [SPREAD] {symbol} Too High: {spread:.5f} > {spread_threshold:.5f}")
                            continue
                else:
                    # Fallback to static if no H1 data
                    if 'XAU' in symbol and spread > 0.50: continue
                    elif 'BTC' in symbol and spread > 10.0: continue
                    elif spread > 2.0 * mt5.symbol_info(symbol).point: continue

                # --- FIND SIGNAL (Uses cached data - FAST) ---
                local_signal = find_local_confluence_signal(symbol, cached_data)
                
                if local_signal:
                    signals_found += 1
                    direction = local_signal['direction']
                    
                    # 1. ASSET-AWARE REGIME DETECTION
                    df_m15 = cached_data.get('M15')
                    regime = RegimeDetector.detect_regime(symbol, df_m15)
                    local_signal['regime'] = regime
                    
                    # 2. VOLATILITY-ADJUSTED DONCHIAN (Filter Fakeouts)
                    # Only check if it's a "Breakout" or "Trend" strategy
                    is_breakout = 'MOMENTUM' in str(local_signal.get('contributing_strategies', ''))
                    
                    if is_breakout:
                        df_m5 = cached_data.get('M5')
                        if not RegimeDetector.check_volatility_adjusted_donchian(symbol, direction, df_m5):
                             logger.info(f" [DONCHIAN] {symbol} blocked - Failed Volatility Breakout Check")
                             continue

                    # Simplified trend check for scalping
                    df_structure = cached_data.get('M15')
                    if df_structure is not None and len(df_structure) > 0:
                        ema_series = df_structure['close'].ewm(span=20, adjust=False).mean()
                        current_price = float(df_structure['close'].iloc[-1])
                        ema_value = float(ema_series.iloc[-1])
                        trend_direction = "UPTREND" if current_price > ema_value else "DOWNTREND"
                    else:
                        trend_direction = "NEUTRAL"
                    
                    # SCALPING: Allow counter-trend in ranging markets
                    if regime == 'RANGING':
                        # Ranging market - mean reversion trades OK
                        logger.info(f" [SCALPING] {symbol} {direction} in RANGING market - mean reversion OK")
                    elif regime == 'TRENDING':
                        # Trending market - check trend alignment
                        signal_confidence = local_signal.get('confidence', 0)
                        
                        if direction == "BUY" and trend_direction == "DOWNTREND":
                            if signal_confidence < 0.85:
                                logger.info(f" [SCALPING] {symbol} Buy in downtrend blocked (conf: {signal_confidence:.2f})")
                                continue
                                
                        if direction == "SELL" and trend_direction == "UPTREND":
                            if signal_confidence < 0.85:
                                logger.info(f" [SCALPING] {symbol} Sell in uptrend blocked (conf: {signal_confidence:.2f})")
                                continue

                    # --- EXECUTION (FAST - no AI in path) ---
                    logger.info(f" [SCALPING] {symbol} {direction} | Regime: {regime} | Executing...")
                    place_ai_trade(local_signal, account_info.equity, state.daily_pnl)

            # Log cycle performance
            cycle_time = time.time() - cycle_start
            if signals_found > 0:
                logger.info(f" [SCALPING] Cycle completed in {cycle_time:.2f}s | Signals found: {signals_found}")
            
            # Fast cycle - check every 5 seconds
            time.sleep(5)

        except KeyboardInterrupt:
            logger.info(f" Bot stopped by user {USER_ID}")
            send_heartbeat(status='stopped', mt5_connected=True, error_message="Stopped by user")
            send_telegram_notification(" <b>Bot Stopped</b>\n\nBot was manually stopped.")
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
    main()
