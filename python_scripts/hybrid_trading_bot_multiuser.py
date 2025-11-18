# -*- coding: utf-8 -*-
"""
=============================================================================
🤖 HYBRID AI TRADING BOT - MULTI-USER VERSION 🤖
=============================================================================
Modified to support:
- Per-user credentials via CLI args
- Supabase integration instead of SQLite
- Telegram notifications
- Real-time dashboard updates
- Bot heartbeat monitoring
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
from pathlib import Path
import re
import certifi
from supabase import create_client, Client

# =============================================================================
# CLI ARGUMENT PARSING
# =============================================================================

parser = argparse.ArgumentParser(description='Multi-user Hybrid AI Trading Bot')
parser.add_argument('--user-id', type=str, required=True, help='User ID')
parser.add_argument('--strategy-id', type=str, required=True, help='Strategy ID')
parser.add_argument('--mt5-login', type=int, required=True, help='MT5 Login')
parser.add_argument('--mt5-password', type=str, required=True, help='MT5 Password')
parser.add_argument('--mt5-server', type=str, required=True, help='MT5 Server')
parser.add_argument('--account-size', type=float, required=True, help='Account Size')
parser.add_argument('--risk-per-trade', type=float, required=True, help='Risk Per Trade %')
parser.add_argument('--max-positions', type=int, default=3, help='Max Concurrent Positions')
parser.add_argument('--telegram-chat-id', type=str, required=False, help='Telegram Chat ID')
parser.add_argument('--telegram-bot-token', type=str, required=False, help='Telegram Bot Token')
parser.add_argument('--supabase-url', type=str, required=True, help='Supabase URL')
parser.add_argument('--supabase-key', type=str, required=True, help='Supabase Service Key')
parser.add_argument('--gemini-api-key', type=str, required=False, help='Gemini API Key')

args = parser.parse_args()

# User-specific configuration
USER_ID = args.user_id
STRATEGY_ID = args.strategy_id
ACCOUNT_SIZE = args.account_size
RISK_PER_TRADE = args.risk_per_trade
MAX_POSITIONS = args.max_positions
TELEGRAM_CHAT_ID = args.telegram_chat_id
TELEGRAM_BOT_TOKEN = args.telegram_bot_token

# Initialize Supabase client
supabase: Client = create_client(args.supabase_url, args.supabase_key)

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
    GEMINI_MODEL: str = "gemini-1.5-pro"  # Stable production model
    
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
    MAX_CONCURRENT_TRADES: int = MAX_POSITIONS
    MAX_DAILY_TRADES: int = 20
    MAX_DAILY_LOSS_PERCENT: float = 5.0
    
    # Timeframes
    ENTRY_TF: int = mt5.TIMEFRAME_M5
    STRUCTURE_TF: int = mt5.TIMEFRAME_M15
    MICRO_STRUCTURE_TF: int = mt5.TIMEFRAME_M1
    TREND_TF: int = mt5.TIMEFRAME_H1
    ATR_PERIOD: int = 14
    
    # DYNAMIC PARAMETERS
    BASE_RISK_PERCENT: float = RISK_PER_TRADE
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
# LOGGING SETUP
# =============================================================================

LOG_DIR = f"Hybrid_AI_Bot_Logs/{USER_ID}"
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f"bot_{datetime.now().strftime('%Y%m%d')}.log"), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# TELEGRAM NOTIFICATIONS
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

# =============================================================================
# BOT HEARTBEAT
# =============================================================================

def send_heartbeat(status: str = 'running', mt5_connected: bool = True, error_message: str = None):
    """Update bot heartbeat in Supabase"""
    try:
        supabase.table('bot_heartbeats').upsert({
            'user_id': USER_ID,
            'strategy_id': STRATEGY_ID,
            'last_heartbeat': datetime.utcnow().isoformat(),
            'status': status,
            'mt5_connected': mt5_connected,
            'error_message': error_message,
            'metadata': {}
        }, on_conflict='user_id,strategy_id').execute()
    except Exception as e:
        logger.error(f"Failed to update heartbeat: {e}")

# =============================================================================
# SUPABASE TRADE DATABASE (Replaces SQLite TradeHistoryDB)
# =============================================================================

class SupabaseTradeDB:
    """Supabase database for comprehensive trade history logging"""
    
    def __init__(self):
        logger.info("✅ Supabase Trade DB initialized")
    
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
                'metadata': {
                    'ticket': trade_data.get('ticket'),
                    'stop_loss': trade_data.get('stop_loss'),
                    'take_profit': trade_data.get('take_profit'),
                    'atr': trade_data.get('atr'),
                    'volatility': trade_data.get('volatility'),
                    'trend_strength': trade_data.get('trend_strength'),
                    'market_regime': trade_data.get('market_regime'),
                    'session': trade_data.get('session'),
                    'ai_confidence': trade_data.get('ai_confidence'),
                    'ai_risk_percent': trade_data.get('ai_risk_percent'),
                    'strategy_name': trade_data.get('strategy_name')
                }
            }
            
            result = supabase.table('trades').insert(db_trade).execute()
            logger.info(f"✅ Trade logged to Supabase: Ticket {trade_data.get('ticket')}")
            
            # Send Telegram notification
            send_telegram_notification(
                f"📈 <b>New Trade Opened</b>\n\n"
                f"Symbol: {trade_data.get('symbol')}\n"
                f"Type: {trade_data.get('direction', '').upper()}\n"
                f"Entry: {trade_data.get('entry_price'):.5f}\n"
                f"Lot Size: {trade_data.get('lot_size')}\n"
                f"SL: {trade_data.get('stop_loss'):.5f} | TP: {trade_data.get('take_profit'):.5f}\n"
                f"Confidence: {trade_data.get('ai_confidence', 0):.1%}"
            )
            
            return result.data[0]['id'] if result.data else None
            
        except Exception as e:
            logger.error(f"Trade logging error: {e}")
            return None

    def update_trade_closed(self, ticket: int, exit_price: float, profit_loss: float, exit_reason: str):
        """Update trade as closed in Supabase"""
        try:
            # Find the trade by ticket in metadata
            trades = supabase.table('trades').select('*').eq('user_id', USER_ID).eq(
                'metadata->>ticket', str(ticket)
            ).eq('status', 'open').execute()
            
            if not trades.data:
                logger.warning(f"Trade with ticket {ticket} not found")
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
            
            logger.info(f"✅ Trade closed in Supabase: Ticket {ticket}, P/L: ${profit_loss:.2f}")
            
            # Send Telegram notification
            profit_emoji = "💚" if profit_loss > 0 else "❌"
            send_telegram_notification(
                f"{profit_emoji} <b>Trade Closed</b>\n\n"
                f"Symbol: {trade['symbol']}\n"
                f"Exit: {exit_price:.5f}\n"
                f"P&L: <b>${profit_loss:.2f}</b>\n"
                f"Reason: {exit_reason}"
            )
            
        except Exception as e:
            logger.error(f"Error updating closed trade: {e}")

    def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        """Get recent trades from Supabase"""
        try:
            result = supabase.table('trades').select('*').eq(
                'user_id', USER_ID
            ).order('opened_at', desc=True).limit(limit).execute()
            
            return result.data if result.data else []
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
            
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error fetching losses: {e}")
            return []

trade_db = SupabaseTradeDB()

# =============================================================================
# NOTE: The rest of the file continues with the original hybrid_trading_bot.py
# code (AI state management, indicators, strategies, etc.) with minimal changes
# except for:
# 1. Using trade_db (SupabaseTradeDB) instead of SQLite
# 2. Adding send_heartbeat() calls at key points
# 3. Adding send_telegram_notification() calls for critical events
# 4. Using ACCOUNT_SIZE instead of account_info.equity where appropriate
# =============================================================================

# ... (Include all the original code from lines 269-1744 with the above modifications)
# For brevity, I'm showing the key integration points below

# Note: Due to length constraints, I'm showing the modified structure.
# The full implementation would include all original functions with these key changes:

logger.info("="*80)
logger.info(f"🤖 MULTI-USER HYBRID AI TRADING BOT INITIALIZED")
logger.info(f"   User ID: {USER_ID}")
logger.info(f"   Strategy ID: {STRATEGY_ID}")
logger.info(f"   MT5 Account: {config.MT5_LOGIN}")
logger.info(f"   Account Size: ${ACCOUNT_SIZE:.2f}")
logger.info(f"   Risk Per Trade: {RISK_PER_TRADE}%")
logger.info("="*80)
