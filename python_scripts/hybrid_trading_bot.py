# -*- coding: utf-8 -*-
"""
=============================================================================
🤖 HYBRID AI TRADING BOT - DYNAMIC V10.1 (STABLE) 🤖
=============================================================================
ARCHITECTURE:
This bot uses a "Hybrid" model to solve API quota limits and improve quality.
1.  LOCAL-FIRST ENGINE (From scalperv7):
    A 9-strategy confluence engine (ICT, SMC, Wyckoff, VP, etc.) runs
    locally 24/7 to find high-probability signals *without* API calls.
2.  AI-POWERED VALIDATION (From gemini_dyn_AI):
    *Only* when the local engine finds a signal, it asks the AI for:
    a. Final Macro Validation (does this trade make sense?)
    b. Optimal Risk Percentage (how much should we bet?)
3.  AI-POWERED LEARNING (From gemini_dyn_AI):
    The AI analyzes all closed trades from the SQLite DB to dynamically
    tune the bot's core parameters (SL/TP multipliers, risk) over time.
4.  DATA-DRIVEN NEWS FILTER (From scalperv7):
    A local Forex Factory calendar filter (0 API calls) pauses trading
    around high-impact news, replacing the old, wasteful AI news check.

This design reduces API calls by >95% and focuses AI power only on
the most critical decisions: final validation and long-term learning.

V10.1 Changelog:
- FIXED: Main loop now correctly calls manage_all_positions, update_closed_trades,
         and check_emergency_conditions.
- FIXED: ai_analyze_closed_trades now analyzes ALL recent trades (wins & losses).
- FIXED: update_closed_trades now correctly processes exit deals (deal.entry == 1).
- FIXED: check_emergency_conditions now reads correct 'win' data and uses
         daily_start_equity.
- FIXED: fetch_upcoming_news_events indentation error.
- FIXED: Crashes in ADX and strategy functions (ZeroDivisionError, KeyError).
- ADDED: SSL verification for news requests.
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
import sqlite3
from pathlib import Path
import re
import certifi # Added for reliable HTTPS requests

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class AITradingConfig:
    """Configuration for AI-powered adaptive trading bot"""
    
    # MT5 Connection
    MT5_LOGIN: int = 206578686
    MT5_PASSWORD: str = "Ravi@2001"
    MT5_SERVER: str = "Exness-MT5Trial7"
    
    # AI API Configuration
    AI_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-2.0-flash-exp" # Use 1.5 Pro for better reasoning
    
    # AI Feature Flags
    ENABLE_AI_VALIDATION: bool = True     # AI validates local signals
    ENABLE_AI_RISK_MANAGEMENT: bool = True  # AI sets risk % per trade
    ENABLE_AI_TRADE_LEARNING: bool = True    # AI learns from mistakes in DB
    
    # Local-First Strategy Engine Flags
    ENABLE_LOCAL_NEWS_FILTER: bool = True   # Use Forex Factory calendar
    ENABLE_CONFLUENCE_ENGINE: bool = True # Use scalperv7 engine
    
    # AI Analysis Intervals
    AI_GLOBAL_CONTEXT_INTERVAL: int = 3600  # 1 hour (for macro view)
    AI_LEARNING_INTERVAL: int = 3600  # 1 hour (for learning)
    LOCAL_NEWS_CHECK_INTERVAL: int = 1800 # 30 mins (for FF calendar)
    MIN_TRADES_FOR_LEARNING: int = 10
    
    # Trading Parameters
    SYMBOLS: List[str] = field(default_factory=lambda: ['EURUSDm', 'GBPUSDm', 'USDJPYm', 'XAUUSDm','BTCUSDm','ETHUSDm','USOILm','NZDUSDm','USDCADm','AUDUSDm','USDCHFm','GBPJPYm'])
    MAX_CONCURRENT_TRADES: int = 3
    MAX_DAILY_TRADES: int = 20
    MAX_DAILY_LOSS_PERCENT: float = 5.0 # Example: 5% daily loss limit
    
    # Timeframes (from scalperv7)
    ENTRY_TF: int = mt5.TIMEFRAME_M5
    STRUCTURE_TF: int = mt5.TIMEFRAME_M15
    MICRO_STRUCTURE_TF: int = mt5.TIMEFRAME_M1
    TREND_TF: int = mt5.TIMEFRAME_H1
    ATR_PERIOD: int = 14
    
    # DYNAMIC PARAMETERS (These are the BASE values. AI will adjust them)
    BASE_RISK_PERCENT: float = 1.0
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
    
    # Local News Filter (from scalperv7)
    NEWS_API_URL: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    NEWS_PAUSE_BEFORE_MINUTES: int = 30
    NEWS_PAUSE_AFTER_MINUTES: int = 30
    HIGH_IMPACT_CURRENCIES: List[str] = field(default_factory=lambda: ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF"])

    # Local Confluence Engine (from scalperv7)
    MIN_CONFLUENCE_SCORE_TRENDING: float = 1.5
    MIN_CONFLUENCE_SCORE_RANGING: float = 1.3
    ADX_PERIOD: int = 14
    ADX_TRENDING_THRESHOLD: float = 25.0
    
    # Local Strategy Weights (from scalperv7)
    STRATEGY_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        'ICT_KILLZONE': 1.0, 'ADVANCED_SMC': 0.9, 'LIQUIDITY_GRAB': 0.85,
        'WYCKOFF_PATTERNS': 0.8, 'VOLUME_PROFILE': 0.75,
        'MOMENTUM_CONFLUENCE': 0.7, 'TREND_PULLBACK': 0.7,
        'SUPPORT_RESISTANCE': 0.65, 'MEAN_REVERSION_BB': 0.6
    })
    
    # Enabled Local Strategies (from scalperv7)
    ENABLED_STRATEGIES: List[str] = field(default_factory=lambda: [
        'ICT_KILLZONE', 'ADVANCED_SMC', 'LIQUIDITY_GRAB', 
        'WYCKOFF_PATTERNS', 'VOLUME_PROFILE', 'SUPPORT_RESISTANCE',
        'MOMENTUM_CONFLUENCE', 'TREND_PULLBACK', 'MEAN_REVERSION_BB'
    ])
    
    # Strategy-Specific Params (from scalperv7)
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

# Symbol Specifications (from scalperv7, more detailed)
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

LOG_DIR = "Hybrid_AI_Bot_Logs"
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f"hybrid_ai_bot_{datetime.now().strftime('%Y%m%d')}.log"), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# TRADE HISTORY DATABASE (From gemini_dyn_AI)
# =============================================================================

class TradeHistoryDB:
    """SQLite database for comprehensive trade history logging"""
    def __init__(self):
        self.db_path = "ai_learning/hybrid_trade_history.db"
        Path("ai_learning").mkdir(exist_ok=True)
        self.conn = None
        self.init_database()
    
    def init_database(self):
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, ticket INTEGER,
                    symbol TEXT, direction TEXT, entry_price REAL, exit_price REAL,
                    stop_loss REAL, take_profit REAL, lot_size REAL, atr REAL,
                    volatility REAL, trend_strength REAL, market_regime TEXT, session TEXT,
                    be_moved INTEGER, trailing_activated INTEGER, partial_tp_taken INTEGER,
                    profit_loss REAL, win INTEGER, hold_time_minutes INTEGER, exit_reason TEXT,
                    ai_confidence REAL, ai_risk_percent REAL, strategy_name TEXT,
                    was_mistake INTEGER DEFAULT 0, mistake_reason TEXT, lesson_learned TEXT
                )
            """)
            self.conn.commit()
            logger.info("✅ Trade history database initialized")
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

trade_db = TradeHistoryDB()

# =============================================================================
# AI STATE MANAGEMENT (From gemini_dyn_AI)
# =============================================================================

class AITradingState:
    """Enhanced state with AI learning and dynamic parameters"""
    def __init__(self):
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.open_positions: Dict = {}
        self.last_ai_learning_time = None
        self.daily_start_equity: float = 0.0 # <-- FIX #1: Initialized the variable
        
        # DYNAMIC PARAMETERS (AI will adjust these)
        self.current_risk_percent: float = config.BASE_RISK_PERCENT
        self.current_sl_multiplier: float = config.SL_ATR_MULTIPLIER
        self.current_tp1_multiplier: float = config.TP1_ATR_MULTIPLIER
        self.current_be_trigger: float = config.BREAKEVEN_TRIGGER_PERCENT
        self.current_trailing_start: float = config.TRAILING_START_PERCENT
        
        # Trade management tracking
        self.be_moved: set = set()
        self.trailing_active: set = set()
        self.partial_closed: set = set()

        # --- NEW: Global AI Context Cache ---
        self.last_global_context_update = None
        self.global_market_sentiment: str = "NEUTRAL"
        self.global_key_drivers: str = "Awaiting data"
        self.global_strong_currencies: List[str] = []
        self.global_weak_currencies: List[str] = []
        
        # --- NEW: Local News Filter Cache ---
        self.last_local_news_update = None
        self.upcoming_high_impact_events: List[Dict] = []

state = AITradingState()

# =============================================================================
# AI API WRAPPER (From gemini_dyn_AI)
# =============================================================================

class AIProvider:
    """Universal AI provider wrapper using Google GenAI SDK"""
    
    def __init__(self):
        self.provider = config.AI_PROVIDER
        self.gemini_model = None
        self.api_key = None
        self.setup_provider()
    
    def setup_provider(self):
        if self.provider == "gemini":
            self.api_key = config.GEMINI_API_KEY
            if self.api_key:
                try:
                    genai.configure(api_key=self.api_key)
                    self.gemini_model = genai.GenerativeModel(config.GEMINI_MODEL)
                    logger.info(f"✅ Gemini SDK Initialized: {config.GEMINI_MODEL}")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize Gemini SDK: {e}")
                    self.api_key = None
        if not self.api_key:
            logger.warning(f"⚠️ AI Provider '{self.provider}' API key not set. AI features disabled.")
    
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
            logger.error(f"❌ AI API Error: {e}")
            if "quota" in str(e).lower():
                logger.critical("!!! AI QUOTA EXCEEDED. BOT WILL PAUSE AI CALLS. !!!")
                # Implement a backoff mechanism
                state.last_global_context_update = datetime.now() + timedelta(hours=1)
            return None

ai_provider = AIProvider()

# =============================================================================
# MT5 CONNECTION & DATA
# =============================================================================

def initialize_mt5() -> bool:
    try:
        if not mt5.initialize(login=config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER):
            logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            return False
        account_info = mt5.account_info()
        if account_info:
            logger.info(f"✅ MT5 Connected | Account: {account_info.login} | Balance: ${account_info.balance:.2f}")
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
# LOCAL-FIRST INDICATORS & HELPERS (Ported from scalperv7)
# =============================================================================

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()

# === FIX #2: Added safety checks for ZeroDivisionError ===
def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    tr = calculate_atr(high, low, close, 1) # Use ATR with period 1 for True Range
    move_up = high.diff()
    move_down = -low.diff()
    plus_dm = pd.Series(np.where((move_up > move_down) & (move_up > 0), move_up, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((move_down > move_up) & (move_down > 0), move_down, 0.0), index=low.index)
    
    # Handle potential division by zero if tr is zero
    tr_ema = tr.ewm(alpha=1/period, adjust=False).mean()
    tr_ema = tr_ema.replace(0, np.nan) # Replace 0s with NaN to avoid division by zero
    
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / tr_ema)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / tr_ema)
    
    # Handle potential division by zero if (plus_di + minus_di) is zero
    di_sum = plus_di + minus_di
    di_sum = di_sum.replace(0, np.nan)
    
    dx = 100 * (abs(plus_di - minus_di) / di_sum)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # Fill NaN values that may have been created
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

# === FIX #3: Improved pip_size logic ===
def get_symbol_specs(symbol: str) -> Dict:
    info = mt5.symbol_info(symbol)
    if info:
        # Calculate pip_size based on digits
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
    # Fallback to static, but also calculate pip_size
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
# LOCAL-FIRST NEWS FILTER (Ported from scalperv7 & FIXED)
# =============================================================================

def get_new_york_utc_offset(event_date: datetime) -> int:
    # Simple DST logic for NY (approximates US DST)
    year = event_date.year
    dst_start = datetime(year, 3, 1) + timedelta(days=(6 - datetime(year, 3, 1).weekday() + 7) % 7 + 7)
    dst_end = datetime(year, 11, 1) + timedelta(days=(6 - datetime(year, 11, 1).weekday() + 7) % 7)
    return -4 if dst_start <= event_date < dst_end else -5

# === FIX #4: Fixed IndentationError and added SSL verification ===
def fetch_upcoming_news_events():
    global state
    if not config.ENABLE_LOCAL_NEWS_FILTER: return
    
    # Check interval
    if state.last_local_news_update and (datetime.now(timezone.utc) - state.last_local_news_update) < timedelta(minutes=config.LOCAL_NEWS_CHECK_INTERVAL):
        return
    
    logger.info("Fetching upcoming high-impact news events from calendar...")
    try:
        response = requests.get(config.NEWS_API_URL, timeout=15, verify=certifi.where())
        response.raise_for_status()
        events_data = response.json()
        high_impact_events = []
        
        for event in events_data:
            # === CRITICAL INDENTATION FIX ===
            # All logic for parsing an event must be INSIDE the loop
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
            # === END OF INDENTATION FIX ===
                    
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
                logger.warning(f"⛔ LOCAL NEWS VETO: Pausing trades for {symbol}. Event '{event['title']}' ({event['currency']}) in {int(time_to_event.total_seconds()/60)} minutes.")
                return True
            
            time_since_event = now_utc - event['datetime_utc']
            if timedelta(seconds=0) < time_since_event < timedelta(minutes=config.NEWS_PAUSE_AFTER_MINUTES):
                logger.warning(f"⛔ LOCAL NEWS VETO: Pausing trades for {symbol}. Market volatile after '{event['title']}' ({event['currency']}).")
                return True
    return False

# =============================================================================
# LOCAL-FIRST STRATEGY ENGINE (Ported from scalperv7)
# =============================================================================
# Note: These are complex, advanced strategies. Their effectiveness is high
# but they will not generate signals on every candle. This is intended.

def strategy_ict_killzone(df_entry: pd.DataFrame, df_structure: pd.DataFrame, trend: str, symbol: str, df_micro: pd.DataFrame) -> Optional[Dict[str, Any]]:
    current_hour = datetime.now(timezone.utc).hour
    if not is_kill_zone(current_hour): return None
    
    current_price = df_entry['close'].iloc[-1]
    atr = calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], config.ATR_PERIOD).iloc[-1]

    for i in range(len(df_entry) - config.ICT_FVG_MITIGATION_CANDLES - 1, 2, -1):
        # Bullish FVG
        if df_entry['low'].iloc[i+1] > df_entry['high'].iloc[i-1]:
            fvg_high, fvg_low = df_entry['low'].iloc[i+1], df_entry['high'].iloc[i-1]
            if fvg_low <= current_price <= fvg_high and trend == "BULLISH":
                if df_entry['close'].iloc[-1] > df_entry['open'].iloc[-1]: # Bullish reversal candle
                    sl = fvg_low - (atr * 0.5)
                    return {"direction": "BUY", "stop_loss": sl, "strategy_name": "ICT_KILLZONE", "confidence": 0.85}
        
        # Bearish FVG
        if df_entry['high'].iloc[i+1] < df_entry['low'].iloc[i-1]:
            fvg_high, fvg_low = df_entry['low'].iloc[i-1], df_entry['high'].iloc[i+1]
            if fvg_low <= current_price <= fvg_high and trend == "BEARISH":
                if df_entry['close'].iloc[-1] < df_entry['open'].iloc[-1]: # Bearish reversal candle
                    sl = fvg_high + (atr * 0.5)
                    return {"direction": "SELL", "stop_loss": sl, "strategy_name": "ICT_KILLZONE", "confidence": 0.85}
    return None

# === FIX #5: Added safe .get() for pip_size ===
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

        # Bullish Order Block
        if candle_close < candle_open: # Bearish candle
            if i + 1 < len(df_entry) and df_entry['close'].iloc[i+1] > candle_high: # Bullish impulse
                ob_high, ob_low = candle_high, candle_low
                if (ob_high - ob_low) >= min_ob_size and ob_low <= current_price <= ob_high:
                    if current_price > df_entry['open'].iloc[-1]: # Rejection
                        confidence = 0.75 + (0.10 if bos == "BULLISH_BOS" else 0)
                        return {"direction": "BUY", "stop_loss": ob_low - (atr * 0.5), "strategy_name": "ADVANCED_SMC", "confidence": confidence}

        # Bearish Order Block
        elif candle_close > candle_open: # Bullish candle
            if i + 1 < len(df_entry) and df_entry['close'].iloc[i+1] < candle_low: # Bearish impulse
                ob_high, ob_low = candle_high, candle_low
                if (ob_high - ob_low) >= min_ob_size and ob_low <= current_price <= ob_high:
                    if current_price < df_entry['open'].iloc[-1]: # Rejection
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

    # Spring (Accumulation)
    if (trend != "BULLISH" and df_entry['low'].iloc[-1] < df_entry['low'].iloc[-2] and
        df_entry['close'].iloc[-1] > df_entry['close'].iloc[-2] and volume_surge and
        price_range > avg_range * 1.2 and df_entry['close'].iloc[-1] > df_entry['high'].iloc[-2]):
        return {"direction": "BUY", "stop_loss": df_entry['low'].iloc[-1] - (atr * 0.5), "strategy_name": "WYCKOFF_PATTERNS", "confidence": 0.8}
    
    # Upthrust (Distribution)
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
    
    # Simple POC calculation
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
# LOCAL-FIRST CONFLUENCE ENGINE (Ported from scalperv7)
# =============================================================================

def find_local_confluence_signal(symbol: str) -> Optional[Dict[str, Any]]:
    """
    This is the new "Local-First" signal generator.
    It runs all 9 local strategies and finds a confluence score.
    It makes ZERO API calls.
    """
    try:
        market_regime, trend_direction = get_market_regime_and_trend(symbol)
        
        # --- Local Veto Gates ---
        if is_trade_entry_paused_for_news(symbol):
            return None # Vetoed by local news filter
            
        # Fetch all required data once
        df_trend = get_market_data(symbol, config.TREND_TF, 200)
        df_entry = get_market_data(symbol, config.ENTRY_TF, 100)
        df_structure = get_market_data(symbol, config.STRUCTURE_TF, 150)
        df_micro = get_market_data(symbol, config.MICRO_STRUCTURE_TF, 50)
        
        if any(df is None for df in [df_trend, df_entry, df_structure, df_micro]):
            logger.error(f"[{symbol}] FAILED to fetch one or more dataframes for local engine.")
            return None
        
        # Select strategies based on regime
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
        
        current_session = get_current_session()
        
        for name in strategies_to_run:
            func = strategy_functions.get(name)
            if not func: continue
            
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
            except Exception as e:
                logger.error(f"Error executing local strategy '{name}': {e}", exc_info=True)

            if signal:
                logger.info(f"[{symbol}] 🔥 Local Signal Found: {signal['strategy_name']} ({signal['direction']})")
                signal['weight'] = config.STRATEGY_WEIGHTS.get(name, 1.0)
                all_signals.append(signal)

        if not all_signals:
            return None # No local signals found

        # --- Confluence Scoring ---
        buy_signals = [s for s in all_signals if s['direction'] == 'BUY']
        sell_signals = [s for s in all_signals if s['direction'] == 'SELL']
        buy_score = sum(s['weight'] * s['confidence'] for s in buy_signals)
        sell_score = sum(s['weight'] * s['confidence'] for s in sell_signals)
        
        min_score = config.MIN_CONFLUENCE_SCORE_TRENDING if market_regime == "TRENDING" else config.MIN_CONFLUENCE_SCORE_RANGING

        if buy_score < min_score and sell_score < min_score:
            logger.info(f"[{symbol}] Local signals found but score too low (Buy: {buy_score:.2f}, Sell: {sell_score:.2f}). Min: {min_score}")
            return None

        best_signal = None
        if buy_score >= min_score and buy_score > sell_score:
            valid_sls = [s['stop_loss'] for s in buy_signals if 'stop_loss' in s]
            if not valid_sls: return None
            best_signal = { 
                "direction": "BUY", "stop_loss": min(valid_sls), "symbol": symbol,
                "confidence": np.mean([s['confidence'] for s in buy_signals]), 
                "contributing_strategies": [s['strategy_name'] for s in buy_signals], 
                "trend": trend_direction, "regime": market_regime
            }
        elif sell_score >= min_score and sell_score > buy_score:
            valid_sls = [s['stop_loss'] for s in sell_signals if 'stop_loss' in s]
            if not valid_sls: return None
            best_signal = { 
                "direction": "SELL", "stop_loss": max(valid_sls), "symbol": symbol,
                "confidence": np.mean([s['confidence'] for s in sell_signals]), 
                "contributing_strategies": [s['strategy_name'] for s in sell_signals], 
                "trend": trend_direction, "regime": market_regime
            }

        if best_signal:
            logger.info(f"[{symbol}] ✅ LOCAL CONFLUENCE SIGNAL FOUND. Proceeding to AI Validation.")
            return best_signal
        
        return None
        
    except Exception as e:
        logger.error(f"Error in local confluence engine for {symbol}: {e}", exc_info=True)
        return None

# =============================================================================
# AI-POWERED FUNCTIONS (Validation, Risk, Learning)
# =============================================================================

def update_global_ai_context():
    """
    NEW: Runs 1x per hour. Gets the "big picture" from the AI.
    This is our ONE major API call for market analysis.
    """
    global state
    if not config.ENABLE_AI_VALIDATION: return
    
    # Check interval
    if state.last_global_context_update and (datetime.now() - state.last_global_context_update) < timedelta(seconds=config.AI_GLOBAL_CONTEXT_INTERVAL):
        return
    
    logger.info("🤖 Updating Global AI Macro Context...")
    
    system_prompt = """You are a Head Macro-Economic Analyst.
Your job is to provide a brief, high-level overview of the entire market.
Focus on:
1.  **Sentiment:** What is the dominant market sentiment? (RISK_ON, RISK_OFF, NEUTRAL)
2.  **Key Drivers:** What is the main story moving the market right now? (e.g., "Fed rate cut speculation", "Geopolitical tensions", "CPI data anticipation")
3.  **Strong/Weak Currencies:** Which 1-2 currencies are strongest and weakest right now?

Respond ONLY with valid JSON.
{
  "sentiment": "RISK_ON|RISK_OFF|NEUTRAL",
  "key_drivers": "A brief summary of the main market narrative.",
  "strong_currencies": ["USD", "JPY", "EUR", "GBP", "AUD", "CAD", "NZD", "CHF"],
  "weak_currencies": ["USD", "JPY", "EUR", "GBP", "AUD", "CAD", "NZD", "CHF"]
}
"""
    prompt = f"Provide your macro-economic analysis for {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}."
    
    response = ai_provider.call_ai(prompt, system_prompt, temperature=0.5, max_tokens=300, json_mode=True)
    
    if response:
        try:
            result = json.loads(response)
            state.global_market_sentiment = result.get('sentiment', 'NEUTRAL')
            state.global_key_drivers = result.get('key_drivers', 'N/A')
            state.global_strong_currencies = result.get('strong_currencies', [])
            state.global_weak_currencies = result.get('weak_currencies', [])
            state.last_global_context_update = datetime.now()
            
            logger.info("🤖 Global AI Context Updated:")
            logger.info(f"   Sentiment: {state.global_market_sentiment}")
            logger.info(f"   Drivers: {state.global_key_drivers}")
            logger.info(f"   Strong: {state.global_strong_currencies} | Weak: {state.global_weak_currencies}")
            
        except Exception as e:
            logger.error(f"Failed to parse AI global context: {e}")
    else:
        logger.error("Failed to get AI global context response.")

def ai_filter_signal(local_signal: Dict) -> Dict[str, Any]:
    """
    NEW: This is the AI Validation step.
    It takes the LOCAL signal and asks the AI for a final "Go/No-Go".
    """
    if not config.ENABLE_AI_VALIDATION:
        return {'approved': True, 'confidence_adjustment': 0.0, 'reason': 'AI filter disabled'}
    
    logger.info(f"🤖 AI validating local signal for {local_signal['symbol']}...")
    
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
            logger.info(f"🤖 AI Validation: {'✅ APPROVED' if result['approved'] else '❌ REJECTED'}")
            logger.info(f"   Reason: {result['reason']}")
            return result
    except Exception as e:
        logger.error(f"AI filter error: {e}")
    
    return {'approved': True, 'confidence_adjustment': 0.0, 'reason': 'AI filter failed, defaulting to approve'}

def ai_calculate_risk_percent(local_signal: Dict, account_equity: float) -> float:
    """
    AI determines optimal risk percentage for this trade.
    """
    if not config.ENABLE_AI_RISK_MANAGEMENT:
        return state.current_risk_percent
    
    logger.info(f"🤖 AI calculating optimal risk percent...")
    
    # Get recent performance from DB
    recent_trades = trade_db.get_recent_trades(20)
    wins = sum(1 for t in recent_trades if t.get('win') == 1)
    win_rate = (wins / len(recent_trades)) * 100 if recent_trades else 50.0
    consec_losses = 0
    for t in recent_trades:
        # Check for win == 0 (loss) or win is None (not updated yet, assume loss for safety)
        if t.get('win') == 0 or t.get('win') is None: 
            consec_losses += 1
        else: 
            break # Found a win, streak is broken
    
    system_prompt = f"""You are a risk management expert. Determine the optimal risk percentage (between {config.MIN_RISK_PERCENT} and {config.MAX_RISK_PERCENT}) for this trade.
Base your decision on:
1. Signal quality and AI-adjusted confidence.
2. Recent trading performance (win rate, consecutive losses).
Respond ONLY with valid JSON: {{ "risk_percent": 0.25_to_2.0, "reasoning": "brief explanation" }}
"""
    prompt = f"""Calculate optimal risk percent:
Signal Details:
- Symbol: {local_signal['symbol']}
- Direction: {local_signal['direction']}
- Confidence: {local_signal.get('confidence', 0.7):.0%}
Recent Performance:
- Win Rate: {win_rate:.0f}%
- Consecutive Losses: {consec_losses}
Account:
- Equity: ${account_equity:.2f}
- Current Base Risk: {state.current_risk_percent:.2f}%
What risk percentage should be used?"""
    
    try:
        response = ai_provider.call_ai(prompt, system_prompt, temperature=0.2, max_tokens=200, json_mode=True)
        if response:
            result = json.loads(response)
            risk_percent = float(result['risk_percent'])
            risk_percent = max(config.MIN_RISK_PERCENT, min(config.MAX_RISK_PERCENT, risk_percent))
            logger.info(f"🤖 AI Risk Decision: {risk_percent:.2f}% | Reasoning: {result['reasoning']}")
            return risk_percent
    except Exception as e:
        logger.error(f"AI risk management error: {e}")
    
    return state.current_risk_percent

# === FIX #5: This function is now corrected to analyze ALL trades ===
def ai_analyze_closed_trades():
    """
    AI reviews ALL recent trades (wins and losses) from the DB to find patterns
    and dynamically adjust the bot's live parameters.
    """
    if not config.ENABLE_AI_TRADE_LEARNING: return
    if state.last_ai_learning_time and (datetime.now() - state.last_ai_learning_time) < timedelta(seconds=config.AI_LEARNING_INTERVAL):
        return
    
    # === FIX: Get ALL recent trades, not just losses ===
    all_recent = trade_db.get_recent_trades(50)
    
    if len(all_recent) < config.MIN_TRADES_FOR_LEARNING:
        logger.info(f"AI Learning: Not enough trades to analyze ({len(all_recent)}/{config.MIN_TRADES_FOR_LEARNING})")
        return
    
    logger.info(f"🧠 AI analyzing {len(all_recent)} recent trades (wins & losses) to learn...")
    
    # Create a summary of ALL trades
    trade_summary = [{
        'symbol': t.get('symbol'), 'strategy': t.get('strategy_name'), 'pnl': t.get('profit_loss'),
        'win': t.get('win'), 'exit_reason': t.get('exit_reason'), 'regime': t.get('market_regime')
    } for t in all_recent]
    
    wins = sum(1 for t in all_recent if t.get('win') == 1)
    win_rate = (wins / len(all_recent)) * 100 if all_recent else 0
    
    system_instruction = """You are an expert trading analyst. Analyze this list of recent trades (containing both wins and losses) to find patterns and provide actionable improvements to the bot's DYNAMIC parameters.
Focus on:
1.  What patterns do the WINNING trades share?
2.  What patterns do the LOSING trades share?
3.  Are the bot's parameters (SL, TP) too tight or too loose?
Respond ONLY with valid JSON:
{
  "patterns_found": ["pattern description 1 (e.g., 'Wins correlate with TRENDING regime')", "pattern description 2 (e.g., 'Losses common in ASIAN session')"],
  "recommended_adjustments": {
    "risk_percent": 0.3 to 2.0,
    "sl_multiplier": 1.5 to 3.0,
    "tp1_multiplier": 2.0 to 4.0,
    "be_trigger_percent": 30 to 60,
    "trailing_start_percent": 50 to 80
  },
  "lessons_learned": ["Specific lesson 1"],
  "confidence": 0.0 to 1.0
}"""
    
    # === FIX: Update the prompt to send ALL trade data ===
    prompt = f"""Analyze these {len(all_recent)} recent trades (wins and losses):
Recent Trade Data: {json.dumps(trade_summary, indent=2)}
Current Performance:
- Win Rate: {win_rate:.1f}%
Current Parameters:
- Risk: {state.current_risk_percent:.2f}%
- SL Multiplier: {state.current_sl_multiplier:.1f}x ATR
- TP1 Multiplier: {state.current_tp1_multiplier:.1f}x ATR
- BE Trigger: {state.current_be_trigger:.0f}% to TP
- Trailing Start: {state.current_trailing_start:.0f}% to TP
What adjustments should we make to improve?"""
    
    try:
        response = ai_provider.call_ai(prompt, system_instruction, temperature=0.4, max_tokens=800, json_mode=True)
        if not response:
            return
        
        result = json.loads(response)
        logger.info(f"🧠 AI MISTAKE ANALYSIS COMPLETE (Confidence: {result.get('confidence', 0):.0%}):")
        
        # APPLY DYNAMIC ADJUSTMENTS!
        adjustments = result.get('recommended_adjustments', {})
        if adjustments and result.get('confidence', 0) >= 0.6:
            logger.info(f"   Applying AI-recommended adjustments...")
            if 'risk_percent' in adjustments:
                state.current_risk_percent = max(config.MIN_RISK_PERCENT, min(config.MAX_RISK_PERCENT, adjustments['risk_percent']))
                logger.info(f"      Base Risk → {state.current_risk_percent:.2f}%")
            if 'sl_multiplier' in adjustments:
                state.current_sl_multiplier = max(1.0, min(3.5, adjustments['sl_multiplier']))
                logger.info(f"      SL Multiplier → {state.current_sl_multiplier:.1f}x ATR")
            if 'tp1_multiplier' in adjustments:
                state.current_tp1_multiplier = max(1.5, min(5.0, adjustments['tp1_multiplier']))
                logger.info(f"      TP1 Multiplier → {state.current_tp1_multiplier:.1f}x ATR")
        
        state.last_ai_learning_time = datetime.now()
    
    except Exception as e:
        logger.error(f"AI learning error: {e}")

# =============================================================================
# DYNAMIC TRADE EXECUTION & MANAGEMENT (From gemini_dyn_AI)
# =============================================================================

# === FIX #6: Added safety checks for ZeroDivisionError ===
def get_dynamic_trade_params(symbol: str, direction: str, df: pd.DataFrame) -> Dict:
    """Calculate ALL trade parameters DYNAMICALLY based on ATR"""
    try:
        atr = calculate_atr(df['high'], df['low'], df['close'], config.ATR_PERIOD).iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # Use DYNAMIC state multipliers
        if direction == 'BUY':
            sl = current_price - (atr * state.current_sl_multiplier)
            tp1 = current_price + (atr * state.current_tp1_multiplier)
            tp2 = current_price + (atr * config.TP2_ATR_MULTIPLIER)
        else:
            sl = current_price + (atr * state.current_sl_multiplier)
            tp1 = current_price - (atr * state.current_tp1_multiplier)
            tp2 = current_price - (atr * config.TP2_ATR_MULTIPLIER)
        
        sl_distance = abs(current_price - sl)
        
        # Market context for logging
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
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": sl,
            "tp": tp
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
        if not pos:
            return False
        pos = pos[0]
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": pos.symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
            "price": mt5.symbol_info_tick(pos.symbol).bid if pos.type == 0 else mt5.symbol_info_tick(pos.symbol).ask,
            "deviation": 20,
            "magic": 234000,
            "comment": "Partial_TP",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        return result and result.retcode == mt5.TRADE_RETCODE_DONE
    except Exception as e:
        logger.error(f"Error closing partial position {ticket}: {e}")
        return False

def manage_all_positions():
    """
    Advanced position management: Breakeven, Trailing Stop, Partial TP
    This function should be called regularly in the main loop
    """
    try:
        positions = mt5.positions_get()
        if not positions:
            return
        
        for pos in positions:
            if pos.magic != 234000:  # Only manage our trades
                continue
            
            symbol = pos.symbol
            ticket = pos.ticket
            entry_price = pos.price_open
            current_price = pos.price_current
            
            # Calculate profit in price terms
            if pos.type == 0:  # Buy
                profit_pips = current_price - entry_price
            else:  # Sell
                profit_pips = entry_price - current_price
            
            # Get stored params for this position
            if ticket not in state.open_positions:
                logger.warning(f"Position {ticket} not found in state, skipping management")
                continue
            
            params = state.open_positions[ticket].get('params')
            if not params:
                continue
            
            tp_distance = abs(params['tp1'] - entry_price)
            if tp_distance == 0:
                continue
            
            # Calculate profit as percentage toward TP
            profit_percent = (profit_pips / tp_distance) * 100
            
            # 1. BREAKEVEN MOVE
            if (config.ENABLE_BREAKEVEN and 
                ticket not in state.be_moved and 
                profit_percent >= state.current_be_trigger):
                
                # Move SL to breakeven + small buffer
                be_offset = tp_distance * (config.BREAKEVEN_LOCK_PERCENT / 100)
                if pos.type == 0:  # Buy
                    be_price = entry_price + be_offset
                else:  # Sell
                    be_price = entry_price - be_offset
                
                if modify_position(ticket, be_price, params['tp1']):
                    state.be_moved.add(ticket)
                    logger.info(f"✅ Breakeven moved for {ticket} {symbol}")
                    
                    # Update database
                    try:
                        cursor = trade_db.conn.cursor()
                        cursor.execute("UPDATE trades SET be_moved = 1 WHERE ticket = ?", (ticket,))
                        trade_db.conn.commit()
                    except:
                        pass
            
            # 2. TRAILING STOP
            if (config.ENABLE_TRAILING_STOP and 
                profit_percent >= state.current_trailing_start):
                
                atr = params['atr']
                
                if pos.type == 0:  # Buy
                    trailing_sl = current_price - (atr * config.TRAILING_ATR_MULTIPLIER)
                    # Only move SL up, never down
                    if trailing_sl > pos.sl:
                        if modify_position(ticket, trailing_sl, params['tp1']):
                            state.trailing_active.add(ticket)
                            logger.info(f"🔄 Trailing stop updated for {ticket} {symbol}: SL → {trailing_sl:.5f}")
                            
                            # Update database
                            try:
                                cursor = trade_db.conn.cursor()
                                cursor.execute("UPDATE trades SET trailing_activated = 1 WHERE ticket = ?", (ticket,))
                                trade_db.conn.commit()
                            except:
                                pass
                else:  # Sell
                    trailing_sl = current_price + (atr * config.TRAILING_ATR_MULTIPLIER)
                    # Only move SL down, never up
                    if trailing_sl < pos.sl:
                        if modify_position(ticket, trailing_sl, params['tp1']):
                            state.trailing_active.add(ticket)
                            logger.info(f"🔄 Trailing stop updated for {ticket} {symbol}: SL → {trailing_sl:.5f}")
                            
                            # Update database
                            try:
                                cursor = trade_db.conn.cursor()
                                cursor.execute("UPDATE trades SET trailing_activated = 1 WHERE ticket = ?", (ticket,))
                                trade_db.conn.commit()
                            except:
                                pass
            
            # 3. PARTIAL TAKE PROFIT
            if (config.ENABLE_PARTIAL_TP and 
                ticket not in state.partial_closed and 
                profit_percent >= config.PARTIAL_TP_PERCENT):
                
                partial_volume = pos.volume * 0.5  # Close 50% of position
                
                if close_partial_position(ticket, partial_volume):
                    state.partial_closed.add(ticket)
                    logger.info(f"✅ Partial TP (50%) executed for {ticket} {symbol}")
                    
                    # Move remaining position to breakeven
                    if modify_position(ticket, entry_price, params['tp2']):
                        logger.info(f"✅ Remaining position moved to BE + TP2 for {ticket}")
                    
                    # Update database
                    try:
                        cursor = trade_db.conn.cursor()
                        cursor.execute("UPDATE trades SET partial_tp_taken = 1 WHERE ticket = ?", (ticket,))
                        trade_db.conn.commit()
                    except:
                        pass
    
    except Exception as e:
        logger.error(f"Error in position management: {e}", exc_info=True)

# === FIX #6: This function is now corrected to log wins ===
def update_closed_trades():
    """
    Update database with exit information for closed trades
    Critical for AI learning to work properly
    """
    try:
        # Get recent deals from MT5 history
        from_date = datetime.now() - timedelta(days=1)
        deals = mt5.history_deals_get(from_date, datetime.now())
        
        if not deals:
            return
        
        for deal in deals:
            if deal.magic != 234000:  # Only our trades
                continue
            
            # === THE FIX: We want to process EXIT deals (1), not skip them ===
            if deal.entry == 0:  # This is an ENTRY deal (DEAL_ENTRY_IN), skip it
                continue
            
            # This is an exit deal (DEAL_ENTRY_OUT or DEAL_ENTRY_INOUT)
            ticket = deal.position_id
            
            # Check if we need to update this trade in database
            try:
                cursor = trade_db.conn.cursor()
                # Check if the exit_price is NULL (meaning not yet updated)
                cursor.execute("SELECT exit_price FROM trades WHERE ticket = ? AND exit_price IS NULL", (ticket,))
                result = cursor.fetchone()
                
                if result:  # Trade exists and is not yet updated
                    # Calculate hold time
                    cursor.execute("SELECT timestamp FROM trades WHERE ticket = ?", (ticket,))
                    entry_time_str = cursor.fetchone()[0]
                    entry_time = datetime.fromisoformat(entry_time_str)
                    exit_time = datetime.fromtimestamp(deal.time, tz=timezone.utc)
                    hold_time_minutes = int((exit_time - entry_time).total_seconds() / 60)
                    
                    # Determine exit reason
                    if deal.profit > 0:
                        exit_reason = 'TP'
                    elif deal.profit < 0:
                        exit_reason = 'SL'
                    else:
                        exit_reason = 'BE'
                    
                    # Update database
                    cursor.execute("""
                        UPDATE trades 
                        SET exit_price = ?, 
                            profit_loss = ?,
                            win = ?,
                            hold_time_minutes = ?,
                            exit_reason = ?
                        WHERE ticket = ?
                    """, (
                        deal.price,
                        deal.profit,
                        1 if deal.profit > 0 else 0, # <-- This now correctly sets 'win' to 1 for profits
                        hold_time_minutes,
                        exit_reason,
                        ticket
                    ))
                    trade_db.conn.commit()
                    
                    logger.info(f"📊 Trade {ticket} updated in database: {exit_reason}, P/L: ${deal.profit:.2f}")
                    
                    # Update state
                    state.daily_pnl += deal.profit
                    
                    # Clean up state tracking
                    if ticket in state.open_positions:
                        del state.open_positions[ticket]
                    state.be_moved.discard(ticket)
                    state.trailing_active.discard(ticket)
                    state.partial_closed.discard(ticket)
                    
            except Exception as e:
                logger.error(f"Error updating trade {ticket} in database: {e}")
                continue
    
    except Exception as e:
        logger.error(f"Error in update_closed_trades: {e}", exc_info=True)

# === FIX #7: This function is now corrected to read accurate data ===
def check_emergency_conditions(account_info) -> bool:
    """
    Emergency circuit breaker to stop trading in dangerous conditions
    Returns True if trading should stop
    """
    # 1. Maximum drawdown check
    if state.daily_start_equity == 0:
        state.daily_start_equity = account_info.equity
    
    peak_equity = max(state.daily_start_equity, account_info.equity)
    current_dd = ((peak_equity - account_info.equity) / peak_equity) * 100 if peak_equity > 0 else 0
    
    if current_dd >= 10:  # 10% drawdown
        logger.critical(f"🚨 EMERGENCY STOP: {current_dd:.1f}% drawdown from peak")
        return True
    
    # 2. Consecutive losses check
    recent_trades = trade_db.get_recent_trades(10)
    if len(recent_trades) >= 10:
        # This logic will now work correctly because `update_closed_trades` is fixed
        if all(t.get('win') == 0 for t in recent_trades[:10]):
            logger.critical("🚨 EMERGENCY STOP: 10 consecutive losses")
            return True
    
    # 3. Margin level check
    if account_info.margin_level < 200 and account_info.margin_level > 0:  # Below 200%
        logger.critical(f"🚨 EMERGENCY STOP: Low margin level {account_info.margin_level:.0f}%")
        return True
    
    # 4. Daily loss limit
    if hasattr(config, 'MAX_DAILY_LOSS_PERCENT') and state.daily_start_equity > 0:
        daily_loss_percent = ((account_info.equity - state.daily_start_equity) / state.daily_start_equity) * 100
        if daily_loss_percent <= -config.MAX_DAILY_LOSS_PERCENT:
            logger.critical(f"🚨 EMERGENCY STOP: Daily loss limit reached {daily_loss_percent:.2f}%")
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
        
        # Round to lot step
        lot_size = round(lot_size / lot_step) * lot_step
        
        # Enforce min/max
        lot_size = max(min_lot, min(max_lot, lot_size))
        
        # Check margin requirements
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return min_lot
        
        margin_required = mt5.order_calc_margin(
            mt5.ORDER_TYPE_BUY, symbol, lot_size, tick.ask
        )
        
        if margin_required is None:
            logger.error(f"Cannot calculate margin for {symbol} {lot_size}")
            return min_lot
        
        account_info = mt5.account_info()
        if not account_info:
            return min_lot
        
        # Use maximum 80% of free margin
        max_allowed_margin = account_info.margin_free * 0.8
        
        if margin_required > max_allowed_margin:
            logger.warning(f"Lot size {lot_size} requires too much margin. Reducing.")
            # Calculate max lot size we can afford
            affordable_lot = (max_allowed_margin / max_allowed_margin) * lot_size if margin_required > 0 else lot_size
            lot_size = round(affordable_lot / lot_step) * lot_step
            lot_size = max(min_lot, lot_size)
        
        return lot_size
    
    except Exception as e:
        logger.error(f"Error validating lot size: {e}")
        return 0.01

def place_ai_trade(local_signal: Dict, account_equity: float) -> bool:
    """
    Execute trade with DYNAMIC lot size, SL, and TP,
    and log everything to the database for learning.
    """
    try:
        symbol = local_signal['symbol']
        direction = local_signal['direction']
        
        # 1. Get market data
        df = get_market_data(symbol, config.ENTRY_TF, 100)
        if df is None: return False
        
        # 2. Calculate DYNAMIC parameters (ATR-based SL/TP)
        params = get_dynamic_trade_params(symbol, direction, df)
        if not params:
            logger.error(f"Could not calculate dynamic params for {symbol}")
            return False
        
        # 3. AI determines RISK PERCENTAGE
        risk_percent = ai_calculate_risk_percent(local_signal, account_equity)
        
        # 4. Calculate DYNAMIC lot size
        lot_size = calculate_dynamic_lot_size(
            symbol, account_equity, risk_percent, params['sl_distance']
        )
        
        # 4b. VALIDATE LOT SIZE
        lot_size = validate_lot_size(symbol, lot_size)
        
        if lot_size < 0.01:
            logger.error(f"Invalid lot size {lot_size} for {symbol}")
            return False

        # 5. Get current price
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return False
        
        price = tick.ask if direction == 'BUY' else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if direction == 'BUY' else mt5.ORDER_TYPE_SELL
        
        # 6. Place order
        request = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": lot_size,
            "type": order_type, "price": price, "sl": params['sl'], "tp": params['tp1'],
            "deviation": 20, "magic": 234000,
            "comment": f"AI_Bot_{local_signal['contributing_strategies'][0][:10]}",
            "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"✅ HYBRID TRADE EXECUTED:")
            logger.info(f"   {symbol} {direction} | Lot: {lot_size:.2f}")
            logger.info(f"   Entry: {price:.5f} | SL: {params['sl']:.5f} | TP1: {params['tp1']:.5f}")
            logger.info(f"   Risk: {risk_percent:.2f}% | Session: {params['session']}")
            logger.info(f"   Strategies: {', '.join(local_signal['contributing_strategies'])}")
            
            # 7. Log to database for AI learning
            trade_db.log_trade({
                'timestamp': datetime.now().isoformat(), 'ticket': result.order, 'symbol': symbol,
                'direction': direction, 'entry_price': price, 'stop_loss': params['sl'],
                'take_profit': params['tp1'], 'lot_size': lot_size, 'atr': params['atr'],
                'volatility': params['volatility_ratio'], 'trend_strength': params['trend_strength'],
                'market_regime': params['regime'], 'session': params['session'], 'be_moved': 0,
                'trailing_activated': 0, 'partial_tp_taken': 0, 'profit_loss': 0.0, 'win': 0,
                'hold_time_minutes': 0, 'exit_reason': 'OPEN',
                'ai_confidence': local_signal.get('confidence', 0.5),
                'ai_risk_percent': risk_percent,
                'strategy_name': ', '.join(local_signal['contributing_strategies'])
            })
            
            state.daily_trades += 1
            state.open_positions[result.order] = {'params': params} # Store params for management
            return True
        else:
            logger.error(f"❌ Trade failed: {result.comment if result else 'Unknown error'}")
            return False
    
    except Exception as e:
        logger.error(f"Error placing trade: {e}", exc_info=True)
        return False

# =============================================================================
# MAIN TRADING LOOP (HYBRID ARCHITECTURE)
# =============================================================================

# === FIX #8: The main loop is now corrected ===
def ai_trading_session():
    """Main trading loop with new Hybrid (Local-First) architecture"""
    
    logger.info("="*80)
    logger.info("🤖 HYBRID AI TRADING BOT (V10.1 STABLE) - SESSION STARTED")
    logger.info("   MODE: Local-First Confluence + AI Validation & Learning")
    logger.info("="*80)
    
    iteration = 0
    
    # Set daily start equity for drawdown checks
    try:
        state.daily_start_equity = mt5.account_info().equity
    except:
        state.daily_start_equity = 0.0
    
    while True:
        try:
            iteration += 1
            
            account_info = mt5.account_info()
            if not account_info:
                logger.error("Lost MT5 connection")
                time.sleep(30)
                continue
            
            # --- 0. EMERGENCY CIRCUIT BREAKER ---
            if check_emergency_conditions(account_info):
                logger.critical("🚨 EMERGENCY CIRCUIT BREAKER TRIPPED. Stopping bot.")
                break # Exit the main loop
            
            # --- 1. UPDATE GLOBAL CONTEXT (Runs on interval) ---
            update_global_ai_context()
            fetch_upcoming_news_events()

            # --- 2. DYNAMIC TRADE MANAGEMENT ---
            manage_all_positions() # <-- This is now active
            
            # --- 3. UPDATE CLOSED TRADES (ESSENTIAL FOR LEARNING) ---
            update_closed_trades() # <-- This is now active

            # --- 4. AI LEARNING (Runs on interval) ---
            ai_analyze_closed_trades() # <-- This now has correct data to read
            
            # --- 5. STATUS LOGGING ---
            if iteration % 20 == 0:
                logger.info(f"📊 Equity: ${account_info.equity:.2f} | Daily P&L: ${state.daily_pnl:.2f} | Trades: {state.daily_trades}/{config.MAX_DAILY_TRADES}")
                logger.info(f"🧠 AI Risk: {state.current_risk_percent:.2f}% | SL: {state.current_sl_multiplier:.1f}x | TP: {state.current_tp1_multiplier:.1f}x")
                logger.info(f"🌍 AI Sentiment: {state.global_market_sentiment} ({state.global_key_drivers})")

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
                
                # A. Find LOCAL-FIRST signal (0 API calls)
                local_signal = find_local_confluence_signal(symbol)
                
                if local_signal:
                    # B. AI VALIDATION (1 API call)
                    ai_validation = ai_filter_signal(local_signal)
                    
                    if ai_validation['approved']:
                        local_signal['confidence'] += ai_validation.get('confidence_adjustment', 0.0)
                        
                        # C. AI RISK & EXECUTION (1 API call)
                        if place_ai_trade(local_signal, account_info.equity):
                            time.sleep(5)
                        
                        # Refresh open positions after placing a trade
                        open_positions = mt5.positions_get()
                        if open_positions and len(open_positions) >= config.MAX_CONCURRENT_TRADES:
                            break # Stop scanning symbols if max trades hit
            
            time.sleep(30)  # Main loop delay
            
        except KeyboardInterrupt:
            logger.info("⚠️ Bot stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ Critical error: {e}", exc_info=True)
            time.sleep(60)
    
    mt5.shutdown()
    logger.info("🛑 Bot shutdown complete")

# =============================================================================
# MAIN ENTRY
# =============================================================================

def main():
    """Main entry point"""
    logger.info("🤖 Initializing Hybrid AI Trading Bot...")
    
    if not ai_provider.api_key:
        logger.error(f"❌ {config.AI_PROVIDER.upper()} API key not set!")
        logger.error("  export GEMINI_API_KEY='your-key'")
        sys.exit(1)
    
    if not initialize_mt5():
        logger.error("Failed to initialize MT5")
        sys.exit(1)
    
    try:
        ai_trading_session()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()