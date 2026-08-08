"""
Strategy logic that is NOT called anywhere in hybrid_trading_bot_multiuser.py's
live trading loop today -- fully implemented, backtestable via
backtest/strategies_registry.py's STRATEGIES_DORMANT, but not one of the
setups actually placing real orders.

Why this file exists (moved out of the live bot file, 2026-08):
grepping the live file for call sites (not just `def`s) found these 7
functions and EntryEngine sitting among ~9,700 lines of code that IS live,
with zero call sites of their own. That's exactly the shape of bug this
whole engagement kept finding elsewhere in this codebase (Swappy 3C's
correct pending-order function was dead for the same reason -- a fully-
built, correct implementation nobody was calling). Keeping unreachable
code physically mixed into the live file makes that kind of bug easy to
reintroduce (someone half-wires one of these back in later without the
same scrutiny a real change gets) and makes the live file harder to audit
(every line has to be individually confirmed dead or live). Moving them
here makes the split structural: if it's in this file, it does not trade
real money, full stop -- promoting one back to live means moving it back
into hybrid_trading_bot_multiuser.py and wiring a real call site, not
flipping a flag.

Dependency note: several of these functions use shared helpers that live
in hybrid_trading_bot_multiuser.py (config, calculate_atr,
identify_swing_highs_lows, detect_break_of_structure, get_symbol_specs).
This file deliberately does NOT `import hybrid_trading_bot_multiuser` at
module scope -- that file is a *script*, not a library (see
backtest/bot_loader.py's docstring: it parses argv, connects a real
Supabase client, and creates directories as import-time side effects), so
importing it directly here would either re-trigger those side effects or
crash outside the harness's controlled bot_loader.import_bot_module()
path. Instead, `_bot()` below does a lazy, read-only lookup into
sys.modules -- it only works once something else (bot_loader for
backtesting, or the live file itself if one of these is ever promoted and
imports this module) has already loaded hybrid_trading_bot_multiuser, and
raises a clear error otherwise rather than silently doing the wrong thing.
EntryEngine needs none of this -- it's fully self-contained (pandas only).
"""

import sys
from typing import Any, Dict, Optional

import pandas as pd


def _bot():
    """
    Returns the already-imported hybrid_trading_bot_multiuser module.
    Never imports it itself -- see module docstring for why. Callers of
    the functions below are expected to be the backtest harness (which
    guarantees hybrid_trading_bot_multiuser is loaded first via
    backtest.bot_loader.import_bot_module()) or, if one of these is ever
    promoted to live, the bot file itself after it has fully executed its
    own module scope.
    """
    mod = sys.modules.get("hybrid_trading_bot_multiuser")
    if mod is None:
        raise RuntimeError(
            "strategies_research functions need hybrid_trading_bot_multiuser "
            "already imported (e.g. via backtest.bot_loader.import_bot_module()) "
            "-- they read shared config/helpers from it lazily rather than "
            "importing it directly (see this module's docstring)."
        )
    return mod


# =============================================================================
# EntryEngine -- "ICT Algorithmic Liquidity Model / Deterministic SMC Entry
# Engine" (its own docstring's description). Never instantiated anywhere in
# the live file. Of everything in this file, this is the one worth the
# most serious consideration for promotion: real touch-and-reject sweep
# detection (not a fixed-price window), real market-structure-shift
# detection off actual swing highs/lows (not a naive lookback), a real FVG
# check on the micro timeframe, and it requires all three (sweep + MSS +
# FVG) to align before firing -- a genuine confluence entry, not a
# single-indicator trigger. Its EdgeEngine score inputs (liquidity_distance,
# liquidity_strength, momentum_state, structure_alignment) are measured
# from the specific setup, not fixed per-strategy constants the way every
# live fallback strategy's `confidence` is. Needs real-data backtesting
# (see backtest/README.md) before any promotion decision, not a
# synthetic-data smoke test alone.
# =============================================================================

class EntryEngine:
    """
    ICT Algorithmic Liquidity Model -- Deterministic SMC Entry Engine.

    QA FIX v11.5 -- "Touch and Reject" logic replaces "Fixed Price Window":
    - Old: price must be within tolerance% of a level (missed 95% of sweeps)
    - New: detect the CANDLE that swept/touched the level then CLOSED back
           through it -- this is the actual ICT confirmation signal.
    tolerance_pct widened from 0.001 to 0.0025 (0.25% = ~$6 on XAU@2500).
    """

    def __init__(self, tolerance: float = 0.0025):
        self.tolerance_pct = tolerance

    def _abs_tolerance(self, price: float) -> float:
        return max(price * self.tolerance_pct, 0.001)

    def get_htf_bias(self, df) -> str:
        """H1/H4 bias: price must be 5% of range away from midpoint to avoid neutrals."""
        if len(df) < 55:
            return "NEUTRAL"
        high = df["high"].rolling(50).max().iloc[-1]
        low  = df["low"].rolling(50).min().iloc[-1]
        eq   = (high + low) / 2
        price = df["close"].iloc[-1]
        margin = (high - low) * 0.05
        if price > eq + margin:
            return "BULLISH"
        if price < eq - margin:
            return "BEARISH"
        return "NEUTRAL"

    def detect_equal_highs_lows(self, df) -> dict:
        if len(df) < 5:
            return {"equal_highs": False, "equal_lows": False}
        ref_price = df["close"].iloc[-1]
        tol = self._abs_tolerance(ref_price)
        highs = df["high"].tail(5)
        lows  = df["low"].tail(5)
        return {
            "equal_highs": (max(highs) - min(highs)) < tol,
            "equal_lows":  (max(lows)  - min(lows))  < tol,
        }

    def detect_sweep(self, df):
        """
        UPGRADED: Checks last 3 candles for Touch-and-Reject sweep.
        Reference level = high/low of last 5 confirmed candles.
        Valid sweep = wick through level + close BACK INSIDE the level.
        """
        if len(df) < 8:
            return None
        lookback = df.iloc[-6:-1]
        ref_high = lookback["high"].max()
        ref_low  = lookback["low"].min()
        for offset in [-1, -2, -3]:
            c = df.iloc[offset]
            if c["high"] > ref_high and c["close"] < ref_high:
                return "SELL_SWEEP"
            if c["low"] < ref_low and c["close"] > ref_low:
                return "BUY_SWEEP"
        return None

    def _swing_high(self, df, i: int) -> bool:
        if i < 2 or i >= len(df) - 2: return False
        return (df["high"].iloc[i] > df["high"].iloc[i-1] and
                df["high"].iloc[i] > df["high"].iloc[i-2] and
                df["high"].iloc[i] > df["high"].iloc[i+1] and
                df["high"].iloc[i] > df["high"].iloc[i+2])

    def _swing_low(self, df, i: int) -> bool:
        if i < 2 or i >= len(df) - 2: return False
        return (df["low"].iloc[i] < df["low"].iloc[i-1] and
                df["low"].iloc[i] < df["low"].iloc[i-2] and
                df["low"].iloc[i] < df["low"].iloc[i+1] and
                df["low"].iloc[i] < df["low"].iloc[i+2])

    def detect_mss(self, df):
        """MSS: searches last 20 candles for swing, not just 5."""
        if len(df) < 10:
            return None
        curr_low  = df["low"].iloc[-1]
        curr_high = df["high"].iloc[-1]
        lookback = min(len(df) - 3, 20)
        for i in range(len(df) - 2, len(df) - lookback, -1):
            if self._swing_low(df, i):
                if curr_low < df["low"].iloc[i]:
                    return "BEARISH"
                break
        for i in range(len(df) - 2, len(df) - lookback, -1):
            if self._swing_high(df, i):
                if curr_high > df["high"].iloc[i]:
                    return "BULLISH"
                break
        return None

    def detect_fvg(self, df):
        """
        Searches last 10 candle triplets for price NOW inside a FVG.
        Relaxed displacement threshold from 1.5x to 1.2x avg body.
        """
        if len(df) < 12:
            return None
        avg_body = abs(df["close"] - df["open"]).rolling(10).mean().iloc[-1]
        price_now = df["close"].iloc[-1]
        for offset in range(3, min(12, len(df))):
            c1 = df.iloc[-offset - 2]
            c2 = df.iloc[-offset - 1]
            c3 = df.iloc[-offset]
            body = abs(c2["close"] - c2["open"])
            if body <= avg_body * 1.2:
                continue
            if c3["low"] > c1["high"] and c1["high"] <= price_now <= c3["low"]:
                return {"direction": "BULLISH", "top": c3["low"], "bottom": c1["high"],
                        "midpoint": (c1["high"] + c3["low"]) / 2}
            if c3["high"] < c1["low"] and c3["high"] <= price_now <= c1["low"]:
                return {"direction": "BEARISH", "top": c1["low"], "bottom": c3["high"],
                        "midpoint": (c3["high"] + c1["low"]) / 2}
        return None

    def evaluate_setup(self, htf_df, ltf_df, micro_df):
        """
        Full ICT pipeline. HTF bias is advisory not blocking:
        sweep+MSS+FVG alignment can fire even in NEUTRAL bias
        with reduced structure_alignment score.
        """
        bias = self.get_htf_bias(htf_df)
        liquidity = self.detect_equal_highs_lows(ltf_df)
        sweep = self.detect_sweep(ltf_df)
        if not sweep:
            return None
        mss = self.detect_mss(ltf_df)
        if not mss:
            return None
        fvg = self.detect_fvg(micro_df)
        if not fvg:
            return None

        recent_high = ltf_df["high"].rolling(10).max().iloc[-1]
        recent_low  = ltf_df["low"].rolling(10).min().iloc[-1]
        body_avg    = abs(ltf_df["close"] - ltf_df["open"]).rolling(10).mean().iloc[-1]
        last_body   = abs(ltf_df["close"].iloc[-1] - ltf_df["open"].iloc[-1])
        momentum_score = min(last_body / body_avg, 2.0) / 2.0 if body_avg > 0 else 0.5
        atr_ltf = float(ltf_df["high"].rolling(14).max().iloc[-1] - ltf_df["low"].rolling(14).min().iloc[-1]) / 14.0

        str_align_bear = 1.0 if bias == "BEARISH" else (0.7 if bias == "NEUTRAL" else 0.5)
        str_align_bull = 1.0 if bias == "BULLISH" else (0.7 if bias == "NEUTRAL" else 0.5)

        if sweep == "SELL_SWEEP" and mss == "BEARISH" and fvg["direction"] == "BEARISH":
            dist = abs(fvg["midpoint"] - recent_high)
            liq_dist = max(0.0, 1.0 - (dist / max(recent_high * 0.005, 1e-9)))
            return {
                "signal": "SELL", "entry_price": fvg["midpoint"],
                "stop_loss": fvg["top"] + atr_ltf * 1.5,
                "reason": "BEARISH_ICT_SETUP",
                "fvg": fvg, "liquidity_targets": liquidity,
                "liquidity_distance": liq_dist,
                "liquidity_strength": 1.0 if liquidity["equal_highs"] else 0.5,
                "momentum_state": momentum_score,
                "structure_alignment": str_align_bear,
            }

        if sweep == "BUY_SWEEP" and mss == "BULLISH" and fvg["direction"] == "BULLISH":
            dist = abs(fvg["midpoint"] - recent_low)
            liq_dist = max(0.0, 1.0 - (dist / max(recent_low * 0.005, 1e-9)))
            return {
                "signal": "BUY", "entry_price": fvg["midpoint"],
                "stop_loss": fvg["bottom"] - atr_ltf * 1.5,
                "reason": "BULLISH_ICT_SETUP",
                "fvg": fvg, "liquidity_targets": liquidity,
                "liquidity_distance": liq_dist,
                "liquidity_strength": 1.0 if liquidity["equal_lows"] else 0.5,
                "momentum_state": momentum_score,
                "structure_alignment": str_align_bull,
            }
        return None


# =============================================================================
# Dormant strategy_* functions. Logic unchanged from the live file --
# moved verbatim, only the shared-helper lookups changed from bare names
# (module-scope in the live file) to `_bot().name` (see _bot() above).
# =============================================================================

def strategy_advanced_smc(df_entry: pd.DataFrame, df_structure: pd.DataFrame, trend: str, symbol: str, df_micro: pd.DataFrame) -> Optional[Dict[str, Any]]:
    bot = _bot()
    spec = bot.get_symbol_specs(symbol)
    if not spec or not spec.get('pip_size'):
        bot.logger.warning(f"SMC: Cannot get pip_size for {symbol}")
        return None
    pip_size = spec['pip_size']

    # FIX: pip_size for Gold = 0.01, so 5 pips = $0.05 -- way too small for an OB.
    # Use 0.3x ATR as minimum OB size -- scales correctly for all assets.
    atr_now = bot.calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], bot.config.ATR_PERIOD).iloc[-1]
    min_ob_size = atr_now * 0.3  # OB must be at least 30% of current ATR
    current_price = df_entry['close'].iloc[-1]
    atr = bot.calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], bot.config.ATR_PERIOD).iloc[-1]

    swing_highs, swing_lows = bot.identify_swing_highs_lows(df_structure, bot.config.SMC_SWING_LOOKBACK)
    bos = bot.detect_break_of_structure(df_structure, swing_highs, swing_lows)

    for i in range(len(df_entry) - bot.config.SMC_VALIDATION_CANDLES - 1, 5, -1):
        candle_open, candle_close = df_entry['open'].iloc[i], df_entry['close'].iloc[i]
        candle_high, candle_low = df_entry['high'].iloc[i], df_entry['low'].iloc[i]

        if candle_close < candle_open: # Bearish candle
            if i + 1 < len(df_entry) and df_entry['close'].iloc[i+1] > candle_high:
                ob_high, ob_low = candle_high, candle_low
                if (ob_high - ob_low) >= min_ob_size and ob_low <= current_price <= ob_high:
                    if current_price > df_entry['open'].iloc[-1]:
                        confidence = 0.75 + (0.10 if bos == "BULLISH_BOS" else 0)
                        return {"direction": "BUY", "stop_loss": ob_low - (atr * 1.5), "strategy_name": "ADVANCED_SMC", "confidence": confidence}

        elif candle_close > candle_open: # Bullish candle
            if i + 1 < len(df_entry) and df_entry['close'].iloc[i+1] < candle_low:
                ob_high, ob_low = candle_high, candle_low
                if (ob_high - ob_low) >= min_ob_size and ob_low <= current_price <= ob_high:
                    if current_price < df_entry['open'].iloc[-1]:
                        confidence = 0.75 + (0.10 if bos == "BEARISH_BOS" else 0)
                        return {"direction": "SELL", "stop_loss": ob_high + (atr * 1.5), "strategy_name": "ADVANCED_SMC", "confidence": confidence}
    return None


def strategy_wyckoff_patterns(df_entry: pd.DataFrame, df_structure: pd.DataFrame, trend: str, symbol: str, df_micro: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    NOTE (added when this moved out of the live file): despite the name,
    this is a volume-climax reversal filter, not genuine Wyckoff method --
    there's no range/cause-and-effect schematic, no spring/upthrust/test/
    SOS/LPS detection. Real Wyckoff analysis would need to be built from
    scratch. Kept under its existing name/label since that's how any
    existing backtest history would reference it; don't read a good
    backtest result here as validating Wyckoff method specifically.
    """
    bot = _bot()
    config = bot.config
    if len(df_entry) < config.VOLUME_LOOKBACK + 10: return None
    volume_avg = df_entry['tick_volume'].rolling(window=config.VOLUME_LOOKBACK).mean()
    volume_surge = df_entry['tick_volume'].iloc[-1] > (volume_avg.iloc[-1] * config.VOLUME_SURGE_MULTIPLIER)
    price_range = df_entry['high'].iloc[-1] - df_entry['low'].iloc[-1]
    avg_range = (df_entry['high'] - df_entry['low']).rolling(window=20).mean().iloc[-1]
    atr = bot.calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], config.ATR_PERIOD).iloc[-1]

    if (trend != "BULLISH" and df_entry['low'].iloc[-1] < df_entry['low'].iloc[-2] and
        df_entry['close'].iloc[-1] > df_entry['close'].iloc[-2] and volume_surge and
        price_range > avg_range * 1.2 and df_entry['close'].iloc[-1] > df_entry['high'].iloc[-2]):
        return {"direction": "BUY", "stop_loss": df_entry['low'].iloc[-1] - (atr * 1.5), "strategy_name": "WYCKOFF_PATTERNS", "confidence": 0.8}

    if (trend != "BEARISH" and df_entry['high'].iloc[-1] > df_entry['high'].iloc[-2] and
        df_entry['close'].iloc[-1] < df_entry['close'].iloc[-2] and volume_surge and
        price_range > avg_range * 1.2 and df_entry['close'].iloc[-1] < df_entry['low'].iloc[-2]):
        return {"direction": "SELL", "stop_loss": df_entry['high'].iloc[-1] + (atr * 1.5), "strategy_name": "WYCKOFF_PATTERNS", "confidence": 0.8}
    return None


def strategy_volume_profile(df_entry: pd.DataFrame, trend: str, symbol: str) -> Optional[Dict[str, Any]]:
    bot = _bot()
    config = bot.config
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
    atr = bot.calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], config.ATR_PERIOD).iloc[-1]
    proximity = atr * 0.5

    if trend != "BEARISH" and abs(current_price - poc) < proximity and current_price > poc:
        if df_entry['close'].iloc[-1] > df_entry['open'].iloc[-1]:
            return {"direction": "BUY", "stop_loss": poc - atr, "strategy_name": "VOLUME_PROFILE", "confidence": 0.75}

    if trend != "BULLISH" and abs(current_price - poc) < proximity and current_price < poc:
        if df_entry['close'].iloc[-1] < df_entry['open'].iloc[-1]:
            return {"direction": "SELL", "stop_loss": poc + atr, "strategy_name": "VOLUME_PROFILE", "confidence": 0.75}
    return None


def strategy_support_resistance(df_entry: pd.DataFrame, trend: str) -> Optional[Dict[str, Any]]:
    bot = _bot()
    # 1. Setup Data
    if len(df_entry) < 20: return None
    current_price = df_entry['close'].iloc[-1]
    atr = bot.calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], bot.config.ATR_PERIOD).iloc[-1]

    # 2. Get recent Swing Lows/Highs
    # FIX: lookback=5 misses wide swings on Gold/Crypto. Use 3 for scalping sensitivity.
    swing_highs_idx, swing_lows_idx = bot.identify_swing_highs_lows(df_entry, lookback=3)

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
                    "stop_loss": candle['low'] - (atr * 1.2),
                    "strategy_name": "SUPPORT_RESISTANCE",
                    "confidence": 0.85
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
                    "stop_loss": candle['high'] + (atr * 1.2),
                    "strategy_name": "SUPPORT_RESISTANCE",
                    "confidence": 0.85
                }

    return None


def strategy_volume_imbalance(df_entry: pd.DataFrame, trend: str, symbol: str) -> Optional[Dict[str, Any]]:
    """
    ICT Concept: Fair Value Gap (FVG) / Imbalance
    Replaces lagging EMA crosses with Price Action gaps.
    """
    bot = _bot()
    if len(df_entry) < 3: return None

    current_price = df_entry['close'].iloc[-1]
    atr = bot.calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], bot.config.ATR_PERIOD).iloc[-1]

    # 1. Bearish FVG (Sell)
    # Candle 1 Low > Candle 3 High
    c1_low = df_entry['low'].iloc[-3]
    c3_high = df_entry['high'].iloc[-1]

    if trend != "BULLISH" and c1_low > c3_high:
        gap_size = c1_low - c3_high
        if gap_size > (atr * 0.2): # Significant Gap
            # If price retraces into the gap, SELL
            if c3_high < current_price < c1_low:
                 return {"direction": "SELL", "stop_loss": c1_low + (atr * 1.0), "strategy_name": "VOLUME_IMBALANCE", "confidence": 0.8}

    # 2. Bullish FVG (Buy)
    # Candle 1 High < Candle 3 Low
    c1_high = df_entry['high'].iloc[-3]
    c3_low = df_entry['low'].iloc[-1]

    if trend != "BEARISH" and c1_high < c3_low:
        gap_size = c3_low - c1_high
        if gap_size > (atr * 0.2):
             # If price retraces into the gap, BUY
             if c1_high < current_price < c3_low:
                 return {"direction": "BUY", "stop_loss": c1_high - (atr * 1.0), "strategy_name": "VOLUME_IMBALANCE", "confidence": 0.8}

    return None


def strategy_trend_pullback(df_entry: pd.DataFrame, trend: str, symbol: str) -> Optional[Dict[str, Any]]:
    bot = _bot()
    ema_slow = df_entry['close'].ewm(span=bot.config.MOMENTUM_EMA_SLOW, adjust=False).mean().iloc[-1]
    last_candle, prev_candle = df_entry.iloc[-1], df_entry.iloc[-2]
    atr = bot.calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], 14).iloc[-1]
    if trend == "BULLISH" and prev_candle['low'] < ema_slow and last_candle['close'] > last_candle['open'] and last_candle['close'] > prev_candle['high']:
        return {"direction": "BUY", "stop_loss": prev_candle['low'] - (atr * 0.8), "strategy_name": "TREND_PULLBACK", "confidence": 0.75}  # FIX: added ATR buffer
    if trend == "BEARISH" and prev_candle['high'] > ema_slow and last_candle['close'] < last_candle['open'] and last_candle['close'] < prev_candle['low']:
        return {"direction": "SELL", "stop_loss": prev_candle['high'] + (atr * 0.8), "strategy_name": "TREND_PULLBACK", "confidence": 0.75}  # FIX: added ATR buffer
    return None


def strategy_mean_reversion_bb(df_entry: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
    """
    NOTE (added when this moved out of the live file): this is a
    counter-trend fade (buy the lower band touch, sell the upper band
    touch) -- philosophically the odd one out here. Every other live and
    dormant strategy in this bot (Shaakuni, Swappy, AOX, EMA scalp,
    EntryEngine, the SMC/ICT-style dormant ones) trades WITH institutional
    liquidity flow/momentum after a sweep or break of structure; this one
    explicitly fades price extremes instead. Not wrong on its own terms --
    mean reversion is a real, legitimate style -- but mixing it into the
    same cascade as the momentum/liquidity strategies needs a deliberate
    decision (e.g. gate it to ranging-regime-only), not a shared `not
    setup` cascade slot with the rest.
    """
    bot = _bot()
    config = bot.config
    close = df_entry['close']
    sma = close.rolling(window=config.BB_PERIOD).mean()
    std = close.rolling(window=config.BB_PERIOD).std()
    upper = sma + (std * config.BB_STD_DEV)
    lower = sma - (std * config.BB_STD_DEV)
    last_candle = df_entry.iloc[-1]
    atr = bot.calculate_atr(df_entry['high'], df_entry['low'], df_entry['close'], 14).iloc[-1]
    if last_candle['high'] > upper.iloc[-1] and last_candle['close'] < upper.iloc[-1]:
        return {"direction": "SELL", "stop_loss": last_candle['high'] + (atr * 1.0), "strategy_name": "MEAN_REVERSION_BB", "confidence": 0.7}  # FIX: added ATR buffer
    if last_candle['low'] < lower.iloc[-1] and last_candle['close'] > lower.iloc[-1]:
        return {"direction": "BUY", "stop_loss": last_candle['low'] - (atr * 1.0), "strategy_name": "MEAN_REVERSION_BB", "confidence": 0.7}  # FIX: added ATR buffer
    return None
