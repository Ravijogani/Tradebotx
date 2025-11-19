# -*- coding: utf-8 -*-
"""
=============================================================================
🤖 HYBRID AI TRADING BOT - V11.0 (MULTI-USER & SUPABASE) 🤖
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
import argparse # <-- ADDED
import sqlite3
from pathlib import Path
import re
import certifi
from supabase import create_client, Client # <-- ADDED

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
parser.add_argument('--supabase-anon-key', type=str, required=True, help='Supabase Anon Key')
parser.add_argument('--supabase-user-token', type=str, required=True, help='Supabase User Token')
parser.add_argument('--gemini-api-key', type=str, required=False, help='Gemini API Key')

args = parser.parse_args()

# User-specific configuration
USER_ID = args.user_id
STRATEGY_ID = args.strategy_id
TELEGRAM_CHAT_ID = args.telegram_chat_id
TELEGRAM_BOT_TOKEN = args.telegram_bot_token

# Initialize Supabase client with anon key and authenticate with user token
supabase: Client = create_client(args.supabase_url, args.supabase_anon_key)
# Authenticate with user token for RLS
supabase.postgrest.auth(args.supabase_user_token)

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class AITradingConfig:
    """Configuration for AI-powered adaptive trading bot"""
    
    # MT5 Connection (will be set from CLI args)
    MT5_LOGIN: int = args.mt5_login
    MT5_PASSWORD: str = args.mt5_password
    MT5_SERVER: str = args.mt5_server
    
    # AI API Configuration
    AI_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = args.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-2.0-flash-exp" # Use 1.5 Pro for better reasoning
    
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
    SYMBOLS: List[str] = field(default_factory=lambda: ['EURUSDm', 'GBPUSDm', 'USDJPYm', 'XAUUSDm','BTCUSDm','ETHUSDm','USOILm','NZDUSDm','USDCADm','AUDUSDm','USDCHFm','GBPJPYm'])
    MAX_CONCURRENT_TRADES: int = 3
    MAX_DAILY_TRADES: int = 20
    MAX_DAILY_LOSS_PERCENT: float = 5.0
    
    # Timeframes
    ENTRY_TF: int = mt5.TIMEFRAME_M5
    STRUCTURE_TF: int = mt5.TIMEFRAME_M15
    MICRO_STRUCTURE_TF: int = mt5.TIMEFRAME_M1
    TREND_TF: int = mt5.TIMEFRAME_H1
    ATR_PERIOD: int = 14
    
    # DYNAMIC PARAMETERS
    BASE_RISK_PERCENT: float = 1.0 # This will be the starting point
    MIN_RISK_PERCENT: float = 0.3
    MAX_RISK_PERCENT: float = 2.0
    SL_ATR_MULTIPLIER: float = 2.0
    TP1_ATR_MULTIPLIER: float = 3.0
    TP2_ATR_MULTIPLIER: float = 5.0
    ENABLE_BREAKEVEN: bool = True
    BREAKEVEN_TRIGGER_PERCENT: float = 40.0
    BREAKEVEN_LOCK_PERCENT: float = 10.0
    ENABLE_TRAILING_STOP: bool = True
    TRAILING_START_PERCENT: float = 60.0
    TRAILING_ATR_MULTIPLIER: float = 1.5
    ENABLE_PARTIAL_TP: bool = True
    PARTIAL_TP_PERCENT: float = 50.0
    
    # Local News Filter
    NEWS_API_URL: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    NEWS_PAUSE_BEFORE_MINUTES: int = 30
    NEWS_PAUSE_AFTER_MINUTES: int = 30
    HIGH_IMPACT_CURRENCIES: List[str] = field(default_factory=lambda: ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF"])

    # Local Confluence Engine
    MIN_CONFLUENCE_SCORE_TRENDING: float = 1.5
    MIN_CONFLUENCE_SCORE_RANGING: float = 1.3
    ADX_PERIOD: int = 14
    ADX_TRENDING_THRESHOLD: float = 25.0
    
    # Local Strategy Weights
    STRATEGY_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        'ICT_KILLZONE': 1.0, 'ADVANCED_SMC': 0.9, 'LIQUIDITY_GRAB': 0.85,
        'WYCKOFF_PATTERNS': 0.8, 'VOLUME_PROFILE': 0.75,
        'MOMENTUM_CONFLUENCE': 0.7, 'TREND_PULLBACK': 0.7,
        'SUPPORT_RESISTANCE': 0.65, 'MEAN_REVERSION_BB': 0.6
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

config = AITradingConfig()

# Symbol Specifications
SYMBOL_SPECS = {
    "EURUSDm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "GBPUSDm": {"pip_size": 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "USDJPYm": {"pip_size": 0.01,   "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "XAUUSDm": {"pip_size": 0.01,   "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    "BTCUSDm": {"pip_size": 1.0,    "min_lot": 0.01, "lot_step": 0.01, "max_lot": 10.0},
    'ETHUSDm': {'pip_size': 0.01,   "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    'USOILm':  {'pip_size': 0.01,   "min_lot": 0.01, "lot_step": 0.01, "max_lot": 1000.0},
    'NZDUSDm': {'pip_size': 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    'USDCADm': {'pip_size': 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    'AUDUSDm': {'pip_size': 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    'USDCHFm': {'pip_size': 0.0001, "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
    'GBPJPYm': {'pip_size': 0.01,   "min_lot": 0.01, "lot_step": 0.01, "max_lot": 100.0},
}

# =============================================================================
# LOGGING SETUP (Now User-Specific)
# =============================================================================

LOG_DIR = f"Hybrid_AI_Bot_Logs_{USER_ID}" # <-- CHANGED
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8',  # <-- ADD THIS
    errors='replace',  # <-- ADD THIS
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f"hybrid_ai_bot_{datetime.now().strftime('%Y%m%d')}.log"), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# TELEGRAM & HEARTBEAT FUNCTIONS (New)
# =============================================================================

def send_telegram_notification(message: str, parse_mode: str = "HTML"):
    """Send Telegram notification to user"""
    if not TELEGRAM_CHAT_ID or not TELEGRAM_BOT_TOKEN:
        return
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": parse_mode
        }
        response = requests.post(url, json=data, timeout=5)
        if response.status_code != 200:
            logger.warning(f"Telegram notification failed: {response.text}")
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")

def send_heartbeat(status: str = 'running', mt5_connected: bool = True, error_message: str = None):
    """Update bot heartbeat with PID management."""
    try:
        acc = mt5.account_info()
        current_bal = acc.balance if acc else 0.0
        current_eq = acc.equity if acc else 0.0
        
        # LOGIC: Store PID if running, remove (None) if stopped/crashed
        current_pid = os.getpid() if status == 'running' else None

        supabase.table('bot_heartbeats').upsert({
            'user_id': USER_ID,
            'strategy_id': STRATEGY_ID,
            'last_heartbeat': datetime.now(timezone.utc).isoformat(),
            'status': status,
            'mt5_connected': mt5_connected,
            'error_message': error_message,
            'balance': current_bal,
            'equity': current_eq,
            'pid': current_pid  # <--- CRITICAL: Stores or Removes PID
        }, on_conflict='user_id,strategy_id').execute()
    except Exception as e:
        logger.error(f"Failed to update heartbeat: {e}")

# =============================================================================
# SUPABASE TRADE DATABASE (Replaces SQLite)
# =============================================================================

class SupabaseTradeDB:
    """Supabase database for comprehensive trade history logging"""
    
    def __init__(self):
        logger.info("Supabase Trade DB initialized")
    
    def log_trade(self, trade_data: Dict):
        """Log trade to Supabase"""
        try:
            # Prepare data for Supabase trades table
            db_trade = {
                'user_id': USER_ID,
                'strategy_id': STRATEGY_ID,
                'symbol': trade_data.get('symbol'),
                'trade_type': trade_data.get('direction', '').upper(),
                'entry_price': float(trade_data.get('entry_price', 0)),
                'quantity': float(trade_data.get('lot_size', 0)),
                'status': 'open',
                'opened_at': trade_data.get('timestamp', datetime.utcnow().isoformat()),
                'ticket': trade_data.get('ticket'),
                'metadata': {
                    'stop_loss': trade_data.get('stop_loss'),
                    'take_profit': trade_data.get('take_profit'),
                    'atr': trade_data.get('atr'),
                    'volatility': trade_data.get('volatility_ratio'),
                    'trend_strength': trade_data.get('trend_strength'),
                    'market_regime': trade_data.get('market_regime'),
                    'session': trade_data.get('session'),
                    'ai_confidence': trade_data.get('ai_confidence'),
                    'ai_risk_percent': trade_data.get('ai_risk_percent'),
                    'strategy_name': trade_data.get('strategy_name')
                }
            }
            
            result = supabase.table('trades').insert(db_trade).execute()
            logger.info(f"Trade logged to Supabase: Ticket {trade_data.get('ticket')}")
            
            # Send Telegram notification
            send_telegram_notification(
                f" <b>New Trade Opened</b>\n\n"
                f"Symbol: {trade_data.get('symbol')}\n"
                f"Type: {trade_data.get('direction', '').upper()}\n"
                f"Entry: {trade_data.get('entry_price'):.5f}\n"
                f"Lot Size: {trade_data.get('lot_size')}\n"
                f"SL: {trade_data.get('stop_loss'):.5f} | TP: {trade_data.get('take_profit'):.5f}\n"
                f"Confidence: {trade_data.get('ai_confidence', 0):.1%}"
            )
            
        except Exception as e:
            logger.error(f"Supabase trade logging error: {e}")

    def update_trade_closed(self, ticket: int, exit_price: float, profit_loss: float, exit_reason: str):
        """Update trade as closed in Supabase"""
        try:
            # Find the trade by ticket
            trades = supabase.table('trades').select('*').eq(
                'user_id', USER_ID
            ).eq(
                'ticket', str(ticket)
            ).eq('status', 'open').execute()
            
            if not trades.data:
                logger.warning(f"Trade with ticket {ticket} not found or already closed in Supabase.")
                return
            
            trade = trades.data[0]
            
            # Update trade to closed
            supabase.table('trades').update({
                'status': 'closed',
                'exit_price': float(exit_price),
                'profit_loss': float(profit_loss),
                'closed_at': datetime.utcnow().isoformat(),
                'metadata': {
                    **trade['metadata'],
                    'exit_reason': exit_reason
                }
            }).eq('id', trade['id']).execute()
            
            logger.info(f" Trade closed in Supabase: Ticket {ticket}, P/L: ${profit_loss:.2f}")
            
            # Send Telegram notification
            profit_emoji = "" if profit_loss > 0 else "❌"
            send_telegram_notification(
                f"{profit_emoji} <b>Trade Closed</b>\n\n"
                f"Symbol: {trade['symbol']}\n"
                f"Exit: {exit_price:.5f}\n"
                f"P&L: <b>${profit_loss:.2f}</b>\n"
                f"Reason: {exit_reason}"
            )
            
        except Exception as e:
            logger.error(f"Error updating closed trade in Supabase: {e}")
            
    def update_trade_management(self, ticket: int, update_data: Dict):
        """Updates metadata for an open trade (e.g., BE move, TSL)"""
        try:
            trades = supabase.table('trades').select('id, metadata').eq(
                'user_id', USER_ID
            ).eq(
                'ticket', str(ticket)
            ).eq('status', 'open').execute()
            
            if not trades.data:
                return
                
            trade = trades.data[0]
            new_metadata = {**trade['metadata'], **update_data}
            
            supabase.table('trades').update({
                'metadata': new_metadata
            }).eq('id', trade['id']).execute()
            
        except Exception as e:
            logger.error(f"Error updating trade management in Supabase: {e}")

    def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        """Get recent trades from Supabase"""
        try:
            result = supabase.table('trades').select('*').eq(
                'user_id', USER_ID
            ).order('opened_at', desc=True).limit(limit).execute()
            
            # Convert Supabase data to the format our AI expects
            return [self.convert_to_ai_format(t) for t in result.data] if result.data else []
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
            return []
    
    def get_losing_trades(self, limit: int = 20) -> List[Dict]:
        """Get losing trades from Supabase"""
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
        """
        Scans MT5 history for the last 'days_back' and uploads missing trades 
        to Supabase. This captures manual trades and past bot history.
        """
        logger.info(f" Syncing trade history (last {days_back} days)...")
        
        from_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        to_date = datetime.now(timezone.utc)
        
        # Get history deals (Closed trades)
        deals = mt5.history_deals_get(from_date, to_date)
        
        if deals is None or len(deals) == 0:
            logger.info("No history found in MT5 for this period.")
            return

        count = 0
        for deal in deals:
            # Only look at 'Entry Out' (Exits) and ignore balance operations (entry=0)
            if deal.entry != mt5.DEAL_ENTRY_OUT:
                continue
            
            ticket = deal.position_id
            
            # 1. Check if this trade already exists in DB
            try:
                exists = supabase.table('trades').select('ticket').eq('ticket', str(ticket)).execute()
                if exists.data:
                    continue # Skip if already recorded
            except Exception as e:
                logger.error(f"Error checking DB for ticket {ticket}: {e}")
                continue

            # 2. If missing, fetch details and insert
            try:
                symbol = deal.symbol
                profit = deal.profit
                direction = "BUY" if deal.type == 1 else "SELL" # 1=Sell (Exit Buy), 0=Buy (Exit Sell)
                
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
                    'ticket': ticket,
                    'profit_loss': profit,
                    'metadata': {
                        'strategy_name': 'MANUAL_OR_HISTORY',
                        'exit_reason': 'SYNCED',
                        'market_regime': 'UNKNOWN',
                        'imported': True
                    }
                }
                
                supabase.table('trades').insert(db_trade).execute()
                count += 1
                
            except Exception as e:
                logger.error(f"Failed to sync trade {ticket}: {e}")

        if count > 0:
            logger.info(f" Successfully synced {count} past/manual trades to database.")
        else:
            logger.info("History is up to date.")
            
    def convert_to_ai_format(self, trade: Dict) -> Dict:
        """Converts a Supabase trade row to the dict format our AI functions expect"""
        metadata = trade.get('metadata', {})
        
        # --- FIX: Safely handle None for profit_loss ---
        pl = trade.get('profit_loss')
        if pl is None:
            pl = 0.0
        # -----------------------------------------------

        return {
            'symbol': trade.get('symbol'),
            'strategy_name': metadata.get('strategy_name'),
            'profit_loss': pl,
            'win': 1 if pl > 0 else 0,  # This line was causing the crash
            'exit_reason': metadata.get('exit_reason'),
            'market_regime': metadata.get('market_regime'),
            'session': metadata.get('session')
        }

trade_db = SupabaseTradeDB() # <-- This now points to Supabase

# =============================================================================
# AI STATE MANAGEMENT
# =============================================================================

class AITradingState:
    """Enhanced state with Strategy Banning and Hourly AI Bias"""
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
        self.partial_closed: set = set()

        # === NEW SMART FEATURES ===
        # 1. Pre-Approved Bias (Latency Fix)
        self.approved_bias: Dict[str, str] = {} 
        self.last_global_context_update = None
        
        # 2. Strategy Banning (Deep Learning)
        self.banned_strategies: List[str] = []
        
        # 3. News Filter
        self.last_local_news_update = None
        self.upcoming_high_impact_events: List[Dict] = []
        
        # === LEGACY FIELDS (Added to prevent crashes) ===
        self.global_strong_currencies: List[str] = []
        self.global_weak_currencies: List[str] = []
        self.global_market_sentiment: str = "NEUTRAL"
        self.global_key_drivers: str = "N/A"

state = AITradingState()

# =============================================================================
# AI API WRAPPER
# =============================================================================
# =============================================================================
# ✅ V12 UPGRADE: MARKET CONDITION & ADAPTIVE RISK MODULES
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
        if adx > 25:
            if volatility_ratio > 3.0:
                return "VOLATILE" # Too dangerous
            return "TRENDING"
        elif adx < 20:
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
        ai_recommended_risk: float  # <--- NEW PARAMETER
    ) -> float:
        
        # 1. Start with the AI's recommendation (or Config Base if AI fails)
        risk_percent = ai_recommended_risk
        
        # 2. Adjust for Tradability (Smart Market Awareness)
        # Even if AI is confident, if the market is choppy, we reduce size.
        if tradability_score >= 80:
            risk_percent *= 1.1 # Slight boost for perfect technicals
        elif tradability_score < 60:
            risk_percent *= 0.7 # Decrease size in weak setups
            
        # 3. Adjust for Losing Streaks (The "Shield")
        # This overrides everything. Safety first.
        recent_trades = trade_db.get_recent_trades(10)
        consec_losses = 0
        for t in recent_trades:
            if t.get('win') == 0: consec_losses += 1
            else: break
            
        if consec_losses >= 2:
            risk_percent *= 0.5  # Cut risk in half after 2 losses
            logger.warning(f" Risk reduced by 50% (Streak: {consec_losses} losses). Base: {ai_recommended_risk:.2f}% -> Final: {risk_percent:.2f}%")
        if consec_losses >= 4:
            risk_percent *= 0.25 # Cut risk to 25% after 4 losses
            
        # 4. Calculate Lot Size
        risk_amount = equity * (risk_percent / 100)
        
        spec = get_symbol_specs(symbol)
        pip_value = spec.get('trade_tick_value', 1.0)
        tick_size = spec.get('trade_tick_size', 0.00001)
        
        sl_pips = abs(entry_price - stop_loss)
        
        if sl_pips == 0: return spec.get('min_lot', 0.01)
        
        if tick_size == 0: lot_size = spec.get('min_lot')
        else: lot_size = risk_amount / (sl_pips / tick_size * pip_value)
        
        # Rounding and Safety Caps
        step = spec.get('lot_step', 0.01)
        lot_size = round(lot_size / step) * step
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
                if df_entry['close'].iloc[-1] > df_entry['open'].iloc[-1]:
                    sl = fvg_low - (atr * 0.5)
                    return {"direction": "BUY", "stop_loss": sl, "strategy_name": "ICT_KILLZONE", "confidence": 0.85}
        
        if df_entry['high'].iloc[i+1] < df_entry['low'].iloc[i-1]:
            fvg_high, fvg_low = df_entry['low'].iloc[i-1], df_entry['high'].iloc[i+1]
            if fvg_low <= current_price <= fvg_high and trend == "BEARISH":
                if df_entry['close'].iloc[-1] < df_entry['open'].iloc[-1]:
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
    volume_by_bin = volumes.groupby(price_bins).sum()
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
    if len(df_entry) < 20: return None
    swing_highs_idx, swing_lows_idx = identify_swing_highs_lows(df_entry, lookback=5)
    current_price = df_entry['close'].iloc[-1]
    atr = calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], config.ATR_PERIOD).iloc[-1]
    proximity = atr * 0.5

    if swing_highs_idx and trend != "BULLISH":
        last_resistance = df_entry['high'].iloc[swing_highs_idx[-1]]
        if abs(current_price - last_resistance) < proximity and df_entry['close'].iloc[-1] < df_entry['open'].iloc[-1]:
            return {"direction": "SELL", "stop_loss": last_resistance + (atr * 0.5), "strategy_name": "SUPPORT_RESISTANCE", "confidence": 0.7}

    if swing_lows_idx and trend != "BEARISH":
        last_support = df_entry['low'].iloc[swing_lows_idx[-1]]
        if abs(current_price - last_support) < proximity and df_entry['close'].iloc[-1] > df_entry['open'].iloc[-1]:
            return {"direction": "BUY", "stop_loss": last_support - (atr * 0.5), "strategy_name": "SUPPORT_RESISTANCE", "confidence": 0.7}
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

def find_local_confluence_signal(symbol: str) -> Optional[Dict[str, Any]]:
    """
    V12 UPGRADE: Checks Market Regime (H4/H1) BEFORE running strategies.
    """
    try:
        # 1. INTELLIGENT CHECK: Get Multi-Timeframe Context
        multi_tf_data = MarketConditionAnalyzer.get_multi_timeframe_data(symbol)
        score, analysis = MarketConditionAnalyzer.get_tradability_score(multi_tf_data)
        
        # 2. FILTER: If market is bad (Choppy/Trappy), STOP immediately.
        if score < 50:
            # logger.info(f"[{symbol}] Skipped. Low Tradability Score: {score}/100 (Regime: {analysis.get('h4_regime')})")
            return None
            
        # 3. Determine Regime for Strategy Selection based on H4
        market_regime = analysis.get('h4_regime', 'RANGING') 
        trend_direction = "BULLISH" if market_regime == "TRENDING" else "NEUTRAL" 
        
        # 4. Standard Data Fetching (for local strategies)
        if is_trade_entry_paused_for_news(symbol): return None
        df_entry = get_market_data(symbol, config.ENTRY_TF, 100)
        df_structure = get_market_data(symbol, config.STRUCTURE_TF, 150)
        df_micro = get_market_data(symbol, config.MICRO_STRUCTURE_TF, 50)
        
        if any(df is None for df in [df_entry, df_structure, df_micro]): return None

        # 5. Select Strategies based on Intelligent Regime
        trending_strategies = ["ADVANCED_SMC", "MOMENTUM_CONFLUENCE", "ICT_KILLZONE", "TREND_PULLBACK"]
        ranging_strategies = ["SUPPORT_RESISTANCE", "VOLUME_PROFILE", "LIQUIDITY_GRAB", "WYCKOFF_PATTERNS", "MEAN_REVERSION_BB"]
        
        strategies_to_run = trending_strategies if market_regime == "TRENDING" else ranging_strategies
        strategies_to_run = [s for s in strategies_to_run if s in config.ENABLED_STRATEGIES]

        all_signals = []
        strategy_functions = {
            "ICT_KILLZONE": strategy_ict_killzone, "ADVANCED_SMC": strategy_advanced_smc,
            "SUPPORT_RESISTANCE": strategy_support_resistance, "MOMENTUM_CONFLUENCE": strategy_momentum_confluence,
            "LIQUIDITY_GRAB": strategy_liquidity_grab, "WYCKOFF_PATTERNS": strategy_wyckoff_patterns,
            "VOLUME_PROFILE": strategy_volume_profile, "TREND_PULLBACK": strategy_trend_pullback,
            "MEAN_REVERSION_BB": strategy_mean_reversion_bb
        }
        
        for name in strategies_to_run:
             # CHECK AI BLACKLIST (V11 Feature preserved)
            if name in state.banned_strategies: continue
            
            func = strategy_functions.get(name)
            if not func: continue
            
            # Execute strategy function
            signal = None
            try:
                if name in ["ICT_KILLZONE", "ADVANCED_SMC", "LIQUIDITY_GRAB", "WYCKOFF_PATTERNS"]:
                    signal = func(df_entry, df_structure, trend_direction, symbol, df_micro)
                elif name in ["VOLUME_PROFILE", "MOMENTUM_CONFLUENCE", "TREND_PULLBACK"]:
                    signal = func(df_entry, trend_direction, symbol)
                elif name == "SUPPORT_RESISTANCE":
                    signal = func(df_entry, trend_direction)
                elif name == "MEAN_REVERSION_BB":
                    signal = func(df_entry, symbol)
            except Exception: continue

            if signal:
                signal['weight'] = config.STRATEGY_WEIGHTS.get(name, 1.0)
                all_signals.append(signal)

        if not all_signals: return None

        # Scoring Logic
        buy_signals = [s for s in all_signals if s['direction'] == 'BUY']
        sell_signals = [s for s in all_signals if s['direction'] == 'SELL']
        buy_score = sum(s['weight'] * s['confidence'] for s in buy_signals)
        sell_score = sum(s['weight'] * s['confidence'] for s in sell_signals)
        
        min_score = config.MIN_CONFLUENCE_SCORE_TRENDING if market_regime == "TRENDING" else config.MIN_CONFLUENCE_SCORE_RANGING

        best_signal = None
        if buy_score >= min_score and buy_score > sell_score:
            valid_sls = [s['stop_loss'] for s in buy_signals if 'stop_loss' in s]
            if valid_sls:
                best_signal = { 
                    "direction": "BUY", "stop_loss": min(valid_sls), "symbol": symbol,
                    "confidence": np.mean([s['confidence'] for s in buy_signals]), 
                    "contributing_strategies": [s['strategy_name'] for s in buy_signals], 
                    "trend": trend_direction, "regime": market_regime
                }
        elif sell_score >= min_score and sell_score > buy_score:
            valid_sls = [s['stop_loss'] for s in sell_signals if 'stop_loss' in s]
            if valid_sls:
                best_signal = { 
                    "direction": "SELL", "stop_loss": max(valid_sls), "symbol": symbol,
                    "confidence": np.mean([s['confidence'] for s in sell_signals]), 
                    "contributing_strategies": [s['strategy_name'] for s in sell_signals], 
                    "trend": trend_direction, "regime": market_regime
                }
        
        if best_signal:
            # Pass the Tradability Score to the execution engine
            best_signal['tradability_score'] = score
            best_signal['market_analysis'] = analysis
            logger.info(f"[{symbol}]  SIGNAL FOUND. Score: {score} | Regime: {market_regime}")
            return best_signal
            
        return None
        
    except Exception as e:
        logger.error(f"Error in local confluence engine: {e}")
        return None

# =============================================================================
# AI-POWERED FUNCTIONS (Validation, Risk, Learning)
# =============================================================================

def update_global_ai_context():
    """
    SMART UPDATE: Runs 1x per hour.
    Sets a hard 'BIAS' (Buy/Sell/Neutral) for every symbol based on Macroeconomics.
    This removes the need to call AI during the fast scalping loop.
    """
    global state
    if not config.ENABLE_AI_VALIDATION: return
    
    # Run only if interval has passed (e.g., 1 hour)
    if state.last_global_context_update and (datetime.now() - state.last_global_context_update) < timedelta(seconds=config.AI_GLOBAL_CONTEXT_INTERVAL):
        return
    
    logger.info(" SMART AI: Analyzing Macro-Economics & Setting Hourly Bias...")
    
    system_prompt = """You are a Senior Hedge Fund Manager.
    Analyze the current global macro environment (USD Strength, Geopolitics, Market Sentiment).
    For each symbol provided, define a STRICT BIAS:
    - 'BUY_ONLY': Macro supports longs (e.g., Weak USD for EURUSD).
    - 'SELL_ONLY': Macro supports shorts.
    - 'NEUTRAL': Market is choppy or risky, stay out.
    
    Respond ONLY with valid JSON:
    {
      "sentiment": "RISK_ON or RISK_OFF",
      "symbol_bias": {
        "EURUSDm": "SELL_ONLY",
        "GBPUSDm": "NEUTRAL",
        "XAUUSDm": "BUY_ONLY"
      },
      "reasoning": "Brief reason"
    }
    """
    
    # Create a string of all symbols we are trading
    symbols_str = ", ".join(config.SYMBOLS)
    prompt = f"Set the hourly trading bias for these symbols based on current market conditions: {symbols_str}."
    
    response = ai_provider.call_ai(prompt, system_prompt, temperature=0.3, max_tokens=500, json_mode=True)
    
    if response:
        try:
            result = json.loads(response)
            state.approved_bias = result.get('symbol_bias', {})
            
            # --- ADD THESE 2 LINES ---
            state.global_market_sentiment = result.get('sentiment', 'NEUTRAL')
            state.global_key_drivers = result.get('reasoning', 'N/A')
            # -------------------------
            
            logger.info(f" BIAS UPDATED: {state.approved_bias}")
            logger.info(f"   Reason: {result.get('reasoning')}")
            
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
    AI determines optimal risk percentage for this trade.
    V11.1 - Now includes 'house money' logic based on current_daily_pnl.
    """
    if not config.ENABLE_AI_RISK_MANAGEMENT:
        return state.current_risk_percent
    
    logger.info(f" AI calculating optimal risk percent...")
    
    # Get recent performance from DB
    recent_trades = trade_db.get_recent_trades(20)
    wins = sum(1 for t in recent_trades if t.get('win') == 1)
    win_rate = (wins / len(recent_trades)) * 100 if recent_trades else 50.0
    consec_losses = 0
    for t in recent_trades:
        if t.get('win') == 0 or t.get('win') is None: 
            consec_losses += 1
        else: 
            break
    
    # === NEW: House Money Logic ===
    house_money_prompt = "You are trading on base risk."
    if current_daily_pnl > 0:
        house_money_prompt = f"""
You are currently IN PROFIT by ${current_daily_pnl:.2f} for the day.
You have 'house money' to use.
If this is a high-confidence signal, you are authorized to risk up to 50% of the *gained profit*
(e.g., up to ${current_daily_pnl * 0.5:.2f}) on this single trade to target a larger gain.
Calculate a risk percentage that is aggressive but prudent.
"""
    
    system_prompt = f"""You are a risk management expert for a scalping bot. Determine the
optimal risk percentage (between {config.MIN_RISK_PERCENT} and {config.MAX_RISK_PERCENT}) for this trade.

Your Base Risk is {state.current_risk_percent:.2f}%.
{house_money_prompt}

Base your final decision on:
1. Signal quality and confidence.
2. Recent trading performance (win rate, consecutive losses).
3. The 'house money' rule (if applicable).

Respond ONLY with valid JSON: {{ "risk_percent": 0.3_to_5.0, "reasoning": "brief explanation" }}
"""
    # Note: I increased max risk in the JSON prompt to 5.0 to allow for the house money rule.
    # The config.MAX_RISK_PERCENT will still be the *default* cap.
    
    prompt = f"""Calculate optimal risk percent:
Signal Details:
- Symbol: {local_signal['symbol']}
- Direction: {local_signal['direction']}
- Confidence: {local_signal.get('confidence', 0.7):.0%}
Intraday Performance:
- Current Daily P&L: ${current_daily_pnl:.2f}
Recent Performance:
- Win Rate (Last 20): {win_rate:.0f}%
- Consecutive Losses: {consec_losses}
Account:
- Equity: ${account_equity:.2f}
What risk percentage should be used?"""
    
    try:
        response = ai_provider.call_ai(prompt, system_prompt, temperature=0.4, max_tokens=200, json_mode=True)
        if response:
            result = json.loads(response)
            risk_percent = float(result['risk_percent'])
            
            # Apply safety caps
            if current_daily_pnl <= 0:
                # If not in profit, cap at normal max risk
                risk_percent = max(config.MIN_RISK_PERCENT, min(config.MAX_RISK_PERCENT, risk_percent))
            else:
                # If in profit, allow a higher cap (e.g., 5% or 50% of profit)
                profit_risk_cap = (current_daily_pnl * 0.5) / account_equity * 100
                final_cap = max(config.MAX_RISK_PERCENT, profit_risk_cap)
                risk_percent = max(config.MIN_RISK_PERCENT, min(final_cap, risk_percent))
            
            logger.info(f" AI Risk Decision: {risk_percent:.2f}% | Reasoning: {result['reasoning']}")
            return risk_percent
    except Exception as e:
        logger.error(f"AI risk management error: {e}")
    
    return state.current_risk_percent

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
    """Calculate ALL trade parameters DYNAMICALLY based on ATR"""
    try:
        atr = calculate_atr(df['high'], df['low'], df['close'], config.ATR_PERIOD).iloc[-1]
        current_price = df['close'].iloc[-1]
        
        if direction == 'BUY':
            sl = current_price - (atr * state.current_sl_multiplier)
            tp1 = current_price + (atr * state.current_tp1_multiplier)
            tp2 = current_price + (atr * config.TP2_ATR_MULTIPLIER)
        else:
            sl = current_price + (atr * state.current_sl_multiplier)
            tp1 = current_price - (atr * state.current_tp1_multiplier)
            tp2 = current_price - (atr * config.TP2_ATR_MULTIPLIER)
        sl_distance = abs(current_price - sl)
        
        vol_50_mean = df['high'].iloc[-50:].mean()
        volatility_ratio = df['high'].iloc[-10:].mean() / vol_50_mean if vol_50_mean != 0 else 1
        ema_50 = df['close'].ewm(span=50).mean().iloc[-1]
        trend_strength = df['close'].ewm(span=20).mean().iloc[-1] / ema_50 if ema_50 != 0 else 1
        regime = "TRENDING" if trend_strength > 1.01 or trend_strength < 0.99 else "RANGING"
        session = get_current_session()
        
        return {
            'sl': sl, 'tp1': tp1, 'tp2': tp2,
            'sl_distance': sl_distance, 'atr': atr, 'volatility_ratio': volatility_ratio,
            'trend_strength': trend_strength, 'regime': regime, 'session': session
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

def modify_position(ticket: int, sl: float, tp: float) -> bool:
    """Modify SL/TP of an existing position"""
    try:
        request = {
            "action": mt5.TRADE_ACTION_SLTP, "position": ticket,
            "sl": sl, "tp": tp
        }
        result = mt5.order_send(request)
        return result and result.retcode == mt5.TRADE_RETCODE_DONE
    except Exception as e:
        logger.error(f"Error modifying position {ticket}: {e}")
        return False

def close_partial_position(ticket: int, volume: float) -> bool:
    """Close partial volume of a position"""
    try:
        pos = mt5.positions_get(ticket=ticket)
        if not pos: return False
        pos = pos[0]
        request = {
            "action": mt5.TRADE_ACTION_DEAL, "position": ticket, "symbol": pos.symbol,
            "volume": volume, "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
            "price": mt5.symbol_info_tick(pos.symbol).bid if pos.type == 0 else mt5.symbol_info_tick(pos.symbol).ask,
            "deviation": 20, "magic": 234000, "comment": "Partial_TP",
            "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        return result and result.retcode == mt5.TRADE_RETCODE_DONE
    except Exception as e:
        logger.error(f"Error closing partial position {ticket}: {e}")
        return False

def manage_all_positions():
    """
    Advanced position management: Breakeven, Trailing Stop, Partial TP
    """
    try:
        positions = mt5.positions_get()
        if not positions: return
        
        for pos in positions:
            if pos.magic != 234000: continue
            
            symbol, ticket, entry_price, current_price = pos.symbol, pos.ticket, pos.price_open, pos.price_current
            profit_pips = (current_price - entry_price) if pos.type == 0 else (entry_price - current_price)

            try:
                trade_db.update_trade_management(ticket, {
                    'current_price': pos.price_current,
                    'running_profit': pos.profit
                })
            except Exception as e:
                logger.warning(f"Failed to sync real-time P&L for ticket {ticket}: {e}")
		
            if ticket not in state.open_positions:
                logger.warning(f"Position {ticket} not found in state, skipping management")
                continue
            
            params = state.open_positions[ticket].get('params')
            if not params: continue
            
            tp_distance = abs(params['tp1'] - entry_price)
            if tp_distance == 0: continue
            
            profit_percent = (profit_pips / tp_distance) * 100
            
            # 1. BREAKEVEN MOVE
            if (config.ENABLE_BREAKEVEN and ticket not in state.be_moved and 
                profit_percent >= state.current_be_trigger):
                
                be_offset = tp_distance * (config.BREAKEVEN_LOCK_PERCENT / 100)
                be_price = entry_price + be_offset if pos.type == 0 else entry_price - be_offset
                
                if modify_position(ticket, be_price, params['tp1']):
                    state.be_moved.add(ticket)
                    logger.info(f" Breakeven moved for {ticket} {symbol}")
                    trade_db.update_trade_management(ticket, {'be_moved': True}) # <-- Update Supabase
            
            # 2. TRAILING STOP
            if (config.ENABLE_TRAILING_STOP and profit_percent >= state.current_trailing_start):
                atr = params['atr']
                trailing_sl = (current_price - (atr * config.TRAILING_ATR_MULTIPLIER)) if pos.type == 0 else (current_price + (atr * config.TRAILING_ATR_MULTIPLIER))
                
                if (pos.type == 0 and trailing_sl > pos.sl) or (pos.type == 1 and trailing_sl < pos.sl):
                    if modify_position(ticket, trailing_sl, params['tp1']):
                        if ticket not in state.trailing_active:
                             logger.info(f" Trailing stop updated for {ticket} {symbol}: SL → {trailing_sl:.5f}")
                             state.trailing_active.add(ticket)
                             trade_db.update_trade_management(ticket, {'trailing_activated': True}) # <-- Update Supabase

            # 3. PARTIAL TAKE PROFIT
            if (config.ENABLE_PARTIAL_TP and ticket not in state.partial_closed and 
                profit_percent >= config.PARTIAL_TP_PERCENT):
                
                partial_volume = round(pos.volume * (config.PARTIAL_TP_PERCENT / 100), 2)
                spec = get_symbol_specs(symbol)
                if partial_volume < spec.get('min_lot', 0.01):
                    partial_volume = spec.get('min_lot', 0.01)
                
                if partial_volume < pos.volume and close_partial_position(ticket, partial_volume):
                    state.partial_closed.add(ticket)
                    logger.info(f"Partial TP (50%) executed for {ticket} {symbol}")
                    trade_db.update_trade_management(ticket, {'partial_tp_taken': True}) # <-- Update Supabase
                    
                    if modify_position(ticket, entry_price, params['tp2']):
                        logger.info(f"Remaining position moved to BE + TP2 for {ticket}")
                        
    except Exception as e:
        logger.error(f"Error in position management: {e}", exc_info=True)

def update_closed_trades():
    """
    Update Supabase with exit information for closed trades
    """
    try:
        from_date = datetime.now() - timedelta(days=7)
        deals = mt5.history_deals_get(from_date, datetime.now())
        if not deals: return
        
        for deal in deals:
            if deal.magic != 234000 or deal.entry == 0: # Skip non-bot trades and entry deals
                continue
            
            ticket = deal.position_id
            
            # Check if we need to update this trade (This check is now handled by SupabaseDB)
            if ticket in state.open_positions:
                profit = deal.profit
                exit_reason = 'TP' if profit > 0 else 'SL' if profit < 0 else 'BE'
                
                # === MODIFIED: Call Supabase function ===
                trade_db.update_trade_closed(ticket, deal.price, profit, exit_reason)
                
                state.daily_pnl += profit
                
                # Clean up local state
                if ticket in state.open_positions:
                    del state.open_positions[ticket]
                state.be_moved.discard(ticket)
                state.trailing_active.discard(ticket)
                state.partial_closed.discard(ticket)
                    
    except Exception as e:
        logger.error(f"Error in update_closed_trades: {e}", exc_info=True)


# === COPY AND REPLACE THIS FUNCTION ===

def check_emergency_conditions(account_info) -> bool:
    """
    Emergency circuit breaker to stop trading in dangerous conditions
    Returns True if trading should stop
    """
    # 1. Daily Loss Limit (Fixed)
    if state.daily_start_equity == 0:
        state.daily_start_equity = account_info.equity
    
    if state.daily_start_equity > 0:
        daily_loss_percent = ((account_info.equity - state.daily_start_equity) / state.daily_start_equity) * 100
        if daily_loss_percent <= -config.MAX_DAILY_LOSS_PERCENT:
            logger.critical(f" EMERGENCY STOP: Daily loss limit of {config.MAX_DAILY_LOSS_PERCENT}% reached. (Loss: {daily_loss_percent:.2f}%)")
            send_telegram_notification(f" <b>EMERGENCY STOP</b> \n\nDaily loss limit of {config.MAX_DAILY_LOSS_PERCENT}% has been hit. Bot is halting for the day.")
            return True
    
    # 2. Consecutive Losses (Performance-Based)
    # This check now works because our 'win' data is accurate
    recent_trades = trade_db.get_recent_trades(10)
    if len(recent_trades) >= 10:
        if all(t.get('win') == 0 for t in recent_trades):
            logger.critical(" EMERGENCY STOP: 10 consecutive losses")
            send_telegram_notification(" <b>EMERGENCY STOP</b> \n\nBot has 10 consecutive losses. Halting to prevent further issues.")
            return True
    
    # 3. Margin Level Check (Broker-Based)
    if account_info.margin_level < 200 and account_info.margin_level > 0:  # Below 200%
        logger.critical(f" EMERGENCY STOP: Low margin level {account_info.margin_level:.0f}%")
        send_telegram_notification(f" <b>EMERGENCY STOP</b> \n\nAccount margin level is critically low ({account_info.margin_level:.0f}%). Bot is halting.")
        return True
    
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

def place_ai_trade(local_signal: Dict, account_equity: float, current_daily_pnl: float) -> bool:
    """
    V12 HYBRID EXECUTION: 
    Combines AI 'House Money' Logic + Mathematical 'Safety Shield'.
    """
    try:
        symbol = local_signal['symbol']
        direction = local_signal['direction']
        tradability_score = local_signal.get('tradability_score', 50) 
        
        df = get_market_data(symbol, config.ENTRY_TF, 100)
        if df is None: return False
        
        # 1. Get Dynamic Stops/TPs
        params = get_dynamic_trade_params(symbol, direction, df)
        if not params:
            logger.error(f"Could not calculate dynamic params for {symbol}")
            return False
        
        # 2. AI RISK ASSESSMENT (The Brain)
        # We ask AI: "Given we made $X profit today, how much should we risk?"
        # This utilizes the function you wanted to keep.
        ai_risk_recommendation = ai_calculate_risk_percent(local_signal, account_equity, current_daily_pnl)
        
        # 3. ADAPTIVE RISK CALCULATION (The Shield)
        # We pass the AI's wish into the Math Manager to ensure safety/streak protection.
        lot_size = AdaptiveRiskManager.calculate_adaptive_lot_size(
            symbol=symbol,
            entry_price=df['close'].iloc[-1],
            stop_loss=params['sl'],
            equity=account_equity,
            tradability_score=tradability_score,
            ai_recommended_risk=ai_risk_recommendation # <-- Passing AI result here
        )
        
        # 4. Final Validation
        lot_size = validate_lot_size(symbol, lot_size)
        if lot_size < 0.01:
            logger.error(f"Invalid lot size {lot_size} for {symbol}")
            return False

        tick = mt5.symbol_info_tick(symbol)
        if not tick: return False
        
        price = tick.ask if direction == 'BUY' else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if direction == 'BUY' else mt5.ORDER_TYPE_SELL
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": lot_size,
            "type": order_type, "price": price, "sl": params['sl'], "tp": params['tp1'],
            "deviation": 20, "magic": 234000,
            "comment": f"V12_AI_{local_signal['contributing_strategies'][0][:10]}",
            "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f" 🚀 V12 HYBRID TRADE EXECUTED:")
            logger.info(f"   {symbol} {direction} | Lot: {lot_size:.2f} | Score: {tradability_score}")
            logger.info(f"   AI Risk: {ai_risk_recommendation:.2f}% | Final Risk: {(lot_size * params['sl_distance'] / account_equity * 100):.2f}%")
            
            # Log to Supabase
            trade_db.log_trade({
                'timestamp': datetime.utcnow().isoformat(), 'ticket': result.order, 'symbol': symbol,
                'direction': direction, 'entry_price': price, 'stop_loss': params['sl'],
                'take_profit': params['tp1'], 'lot_size': lot_size, 'atr': params['atr'],
                'volatility_ratio': params['volatility_ratio'], 'trend_strength': params['trend_strength'],
                'market_regime': local_signal.get('regime', 'UNKNOWN'), 
                'session': params['session'],
                'ai_confidence': local_signal.get('confidence', 0.5),
                'ai_risk_percent': ai_risk_recommendation, # Log what AI wanted
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
    """Main trading loop with new Hybrid (Local-First) architecture"""

    last_heartbeat_time = time.time()
    
    logger.info("="*80)
    logger.info(f" HYBRID AI TRADING BOT (V11 MULTI-USER) - SESSION STARTED FOR {USER_ID}")
    logger.info(f"   MT5 ACCOUNT: {config.MT5_LOGIN}")
    logger.info("="*80)
    
    iteration = 0
    if time.time() - last_heartbeat_time > 15: 
        send_heartbeat(status='running', mt5_connected=True)
        last_heartbeat_time = time.time()
    
    try:
        account_info = mt5.account_info()
        state.daily_start_equity = account_info.equity if account_info else 0.0
        send_telegram_notification(
            f" <b>Bot Started</b>\n\nUser: {USER_ID}\nStrategy: {STRATEGY_ID}\n"
            f"Account: {config.MT5_LOGIN}\nEquity: ${state.daily_start_equity:.2f}"
        )
    except Exception as e:
        logger.error(f"Failed to get initial account info: {e}")
        state.daily_start_equity = 0.0
    
    while True:
        try:
            iteration += 1
            
            account_info = mt5.account_info()
            if not account_info:
                logger.error("Lost MT5 connection")
                send_heartbeat(status='error', mt5_connected=False, error_message="Lost MT5 connection")
                time.sleep(30)
                continue
            
            # --- 0. EMERGENCY CIRCUIT BREAKER ---
            if check_emergency_conditions(account_info):
                logger.critical("EMERGENCY CIRCUIT BREAKER TRIPPED. Stopping bot.")
                send_heartbeat(status='stopped', mt5_connected=True, error_message="Emergency Stop Triggered")
                send_telegram_notification(" <b>EMERGENCY STOP</b> \n\nBot has been halted due to safety violations (drawdown or loss streak).")
                break
            
            # --- 1. UPDATE GLOBAL CONTEXT (Runs on interval) ---
            update_global_ai_context()
            fetch_upcoming_news_events()

            # --- 2. DYNAMIC TRADE MANAGEMENT ---
            manage_all_positions()
            
            # --- 3. UPDATE CLOSED TRADES (ESSENTIAL FOR LEARNING) ---
            update_closed_trades()

            # --- 4. AI LEARNING (Runs on interval) ---
            ai_analyze_closed_trades()
            
            # --- 5. HEARTBEAT & STATUS LOGGING ---
            if time.time() - last_heartbeat_time > 60:
                send_heartbeat(status='running', mt5_connected=True)
                last_heartbeat_time = time.time()
            
            if iteration % 20 == 0:
                logger.info(f" Equity: ${account_info.equity:.2f} | Daily P&L: ${state.daily_pnl:.2f} | Trades: {state.daily_trades}/{config.MAX_DAILY_TRADES}")
                logger.info(f" AI Risk: {state.current_risk_percent:.2f}% | SL: {state.current_sl_multiplier:.1f}x | TP: {state.current_tp1_multiplier:.1f}x")
                logger.info(f" AI Sentiment: {state.global_market_sentiment} ({state.global_key_drivers})")

            # --- 6. CHECK TRADE LIMITS ---
            if state.daily_trades >= config.MAX_DAILY_TRADES:
                time.sleep(300)
                continue
            
            open_positions = mt5.positions_get()
            if open_positions and len(open_positions) >= config.MAX_CONCURRENT_TRADES:
                time.sleep(30)
                continue
            
            # --- 7. NEW HYBRID SIGNAL LOOP ---
            for symbol in config.SYMBOLS:
                if open_positions and any(pos.symbol == symbol for pos in open_positions):
                    continue
                
                # A. Check Hourly AI Bias (Fast Filter)
                bias = state.approved_bias.get(symbol, "NEUTRAL")
                if bias == "NEUTRAL":
                    continue # Skip if AI says market is unsure
                
                # B. Find Local Pattern
                local_signal = find_local_confluence_signal(symbol)
                
                if local_signal:
                    strat_name = local_signal['contributing_strategies'][0]
                    
                    # C. Check if Strategy is Banned (Self-Correction)
                    if strat_name in state.banned_strategies:
                        logger.info(f" Skipping {symbol}: Strategy '{strat_name}' is currently BANNED.")
                        continue

                    # D. Check Bias Alignment
                    if bias == "BUY_ONLY" and local_signal['direction'] != "BUY":
                        continue
                    if bias == "SELL_ONLY" and local_signal['direction'] != "SELL":
                        continue
                    
                    # E. Check Order Flow (The "Eyes")
                    flow = analyze_order_flow(symbol)
                    if local_signal['direction'] == "BUY" and flow == "STRONG_SELL":
                        logger.info(f"⚠️ Skipping BUY: Order Flow is Selling.")
                        continue
                    if local_signal['direction'] == "SELL" and flow == "STRONG_BUY":
                        logger.info(f"⚠️ Skipping SELL: Order Flow is Buying.")
                        continue

                    # --- NEW: AI SNIPER CHECK (Optional Latency Added) ---
                    # Validates the specific setup with the AI Brain
                    ai_validation = ai_filter_signal(local_signal)
                    
                    if not ai_validation['approved']:
                        logger.info(f"🚫 AI VETO: {symbol} trade rejected. Reason: {ai_validation['reason']}")
                        continue # Skip this trade
                    
                    # If approved, adjust confidence based on AI's feedback
                    local_signal['confidence'] += ai_validation.get('confidence_adjustment', 0.0)
                    # -----------------------------------------------------

                    # F. EXECUTE
                    place_ai_trade(local_signal, account_info.equity, state.daily_pnl)
                    
                    time.sleep(1) # Short pause after trade
            
        except KeyboardInterrupt:
            logger.info(f" Bot stopped by user {USER_ID}")
            send_heartbeat(status='stopped', mt5_connected=True, error_message="Stopped by user")
            send_telegram_notification(" <b>Bot Stopped</b>\n\nBot was manually stopped.")
            break
        except Exception as e:
            logger.error(f" Critical error: {e}", exc_info=True)
            send_heartbeat(status='error', mt5_connected=True, error_message=str(e))
            send_telegram_notification(f" <b>Critical Error</b>\n\nBot has encountered an error: {e}")
            time.sleep(60)
    
    mt5.shutdown()
    logger.info(" Bot shutdown complete")

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
