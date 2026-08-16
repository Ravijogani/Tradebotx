# -*- coding: utf-8 -*-
"""
=============================================================================
 MARKET INTELLIGENCE -- shared auction-theory / liquidity / positioning
 engine used by all three live bots (hybrid_trading_bot_multiuser.py,
 intraday.py, structural_swing_pro.py) and the backtest harness.
=============================================================================
Why this file exists: every strategy across all three bots was built on
retail-indicator regime detection (ADX trend/range, EMA stacks) or no
regime detection at all. None of it is how an institutional or professional
prop desk actually reads a market. This module replaces that with the
framework a real desk uses -- and it's the ONE thing genuinely missing
across the whole codebase: **every existing strategy in this repo is a
trend/breakout/continuation archetype. Not one is designed to make money
when the market is rotating inside a range**, which is where price spends
most of its time. detect_balance_fade_signal() below is that missing piece.

FRAMEWORK
---------
1. Auction Market Theory, not ADX. classify_auction_state() computes a
   Volume Profile (Point of Control, Value Area High/Low) and VWAP, and
   classifies the market as BALANCE (rotating inside value -- fade the
   edges back toward POC) or IMBALANCE_UP/DOWN (an initiative move that
   left value on real follow-through, not just a wick -- follow it, don't
   fade it). This is a materially sharper regime read than "ADX > 25"
   because it's built from where volume actually transacted, not a
   smoothed momentum oscillator.

   Honest caveat: MT5's tick_volume is tick COUNT, not real traded volume
   -- forex/CFDs are OTC, there's no consolidated tape. It's a workable,
   standard proxy (more ticks does correlate with more activity, and this
   is the same simplification most retail platforms' own "volume" profile
   tools use without L2 data), not literal CME/COMEX contract volume. If a
   real futures volume feed for a symbol becomes available, feed it in as
   `volume_col` instead of the default 'tick_volume'.

2. Liquidity mapping as a shared engine, not a two-strategy afterthought.
   build_liquidity_map() finds equal highs/lows (where stops cluster) and
   marks each as swept or untested -- the same concept Shaakuni SSM and
   AOX already use narrowly, generalized so every strategy can ask "is
   there a real liquidity pool between here and my target, or am I
   targeting empty air?"

3. Intermarket confirmation. compute_intermarket_bias() generalizes the
   SMT-divergence concept AOX already has (one gate, one strategy) into a
   reusable correlation check any strategy can call: is a correlated
   market confirming or fighting this move?

4. Positioning. fetch_cot_positioning()/cot_positioning_bias() add the one
   piece of genuine institutional data this repo had zero of: CFTC
   Commitment of Traders positioning (public, weekly) for the futures
   contracts underlying XAUUSDm/XAGUSDm/USOILm. Extreme net positioning by
   large speculators is a real contrarian signal -- "who's left to buy."
   NETWORK CAVEAT, stated plainly rather than silently glossed over: this
   sandbox's outbound network policy blocks cftc.gov entirely (confirmed
   directly, not assumed -- a 403 policy denial from the proxy, not a
   transient failure), so fetch_cot_positioning() could not be tested
   end-to-end in this environment. It's written defensively (same "no
   data -> neutral, never blocks trading" pattern as every AI-optional
   fallback elsewhere in this codebase) and cot_positioning_bias() -- the
   actual interpretation logic -- IS independently unit-tested against
   synthetic positioning data. Verify the live fetch on a real deployment
   host before trusting it; if it fails there too, positioning bias stays
   neutral and every other piece of this module keeps working exactly as
   before.

5. Volatility-target sizing. volatility_target_multiplier() scales
   position size by how current realized volatility compares to its own
   trailing distribution -- standard vol-targeting, not a flat % risk
   regardless of how calm or violent the instrument currently is.

WHAT THIS FILE DELIBERATELY DOES NOT DO
----------------------------------------
No real order-book depth, no dark-pool prints, no true institutional order
flow -- none of that is reachable from a retail MT5 feed, and claiming
otherwise would be the kind of overclaim this whole engagement has
consistently avoided. Everything here is computable from OHLCV data (plus,
optionally, public COT data) and is the actual, honest ceiling of
"institutional-style" analysis available to a retail-executed bot. What
separates it from the indicator-stack it replaces is the framework
(auction theory, liquidity, positioning, cross-market confirmation), not
access to data no retail participant can get.

PURITY / BACKTEST-LIVE PARITY
-------------------------------
Every function here is pure (OHLCV DataFrames and plain values in,
dict/float/None out) -- no mt5.*, no get_market_data, no datetime.now().
Same principle as structural_swing_pro.py's detect_structural_swing_signal:
one implementation, called identically by every live bot and by the
backtest harness, so there is no second copy of this logic anywhere to
silently drift out of sync. fetch_cot_positioning() is the one exception
(it has to reach the network) -- kept separate from cot_positioning_bias()
(the pure interpretation function) for exactly that reason.
"""

import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# =============================================================================
# VOLUME PROFILE / AUCTION STATE
# =============================================================================

def compute_volume_profile(df: pd.DataFrame, num_bins: int = 24,
                            value_area_pct: float = 0.70,
                            volume_col: str = "tick_volume") -> Dict:
    """
    Volume Profile built from OHLC bars (not tick-by-tick prints, which no
    retail feed provides): the price range [low.min(), high.max()] across
    `df` is split into `num_bins` buckets; each bar's volume is distributed
    across every bucket its [low, high] range overlaps, proportional to
    the fraction of the bucket's width that bar's range covers. This is
    the standard "volume profile from OHLC" approximation used by most
    retail/prop tools that don't have L2 data -- not literal per-trade
    volume, but a much closer read of where activity concentrated than a
    single indicator value.

    Point of Control (POC) = the bucket with the most volume. Value Area
    (VAH/VAL) = expand outward from the POC bucket, always adding whichever
    neighboring bucket (above or below the current value-area range) has
    more volume, until `value_area_pct` of total volume is captured --
    the standard Market Profile construction.

    Returns {poc, vah, val, vwap, total_volume, bin_edges, bin_volumes}.
    Returns an all-None dict if `df` is empty or has zero total volume.
    """
    empty = {"poc": None, "vah": None, "val": None, "vwap": None,
             "total_volume": 0.0, "bin_edges": None, "bin_volumes": None}
    if df is None or len(df) == 0:
        return empty

    price_min = float(df["low"].min())
    price_max = float(df["high"].max())
    if not np.isfinite(price_min) or not np.isfinite(price_max) or price_max <= price_min:
        return empty

    bin_edges = np.linspace(price_min, price_max, num_bins + 1)
    bin_volumes = np.zeros(num_bins)

    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    vols = df[volume_col].to_numpy() if volume_col in df.columns else np.ones(len(df))

    for h, l, v in zip(highs, lows, vols):
        if v <= 0:
            continue
        bar_range = h - l
        if bar_range <= 0:
            # Zero-range bar (e.g. a flat tick) -- drop its whole volume in
            # the single bucket it falls in.
            idx = min(int((h - price_min) / (price_max - price_min) * num_bins), num_bins - 1)
            bin_volumes[idx] += v
            continue
        lo_idx = max(0, int((l - price_min) / (price_max - price_min) * num_bins))
        hi_idx = min(num_bins - 1, int((h - price_min) / (price_max - price_min) * num_bins))
        for i in range(lo_idx, hi_idx + 1):
            overlap = min(h, bin_edges[i + 1]) - max(l, bin_edges[i])
            if overlap > 0:
                bin_volumes[i] += v * (overlap / bar_range)

    total_volume = float(bin_volumes.sum())
    if total_volume <= 0:
        return empty

    poc_idx = int(np.argmax(bin_volumes))
    poc_price = float((bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2)

    va_lo_idx, va_hi_idx = poc_idx, poc_idx
    captured = bin_volumes[poc_idx]
    target = value_area_pct * total_volume
    while captured < target and (va_lo_idx > 0 or va_hi_idx < num_bins - 1):
        vol_above = bin_volumes[va_hi_idx + 1] if va_hi_idx < num_bins - 1 else -1.0
        vol_below = bin_volumes[va_lo_idx - 1] if va_lo_idx > 0 else -1.0
        if vol_above >= vol_below:
            va_hi_idx += 1
            captured += bin_volumes[va_hi_idx]
        else:
            va_lo_idx -= 1
            captured += bin_volumes[va_lo_idx]

    vah = float(bin_edges[va_hi_idx + 1])
    val = float(bin_edges[va_lo_idx])

    vwap = compute_vwap(df, volume_col=volume_col)

    return {
        "poc": poc_price, "vah": vah, "val": val, "vwap": vwap,
        "total_volume": total_volume, "bin_edges": bin_edges, "bin_volumes": bin_volumes,
    }


def compute_vwap(df: pd.DataFrame, volume_col: str = "tick_volume") -> Optional[float]:
    """
    Volume-weighted average price over the full window given -- callers
    pass whatever window they want VWAP anchored to (e.g. the same session
    used for compute_volume_profile, or a rolling N-bar window). Typical
    price = (high+low+close)/3, the standard VWAP definition.
    """
    if df is None or len(df) == 0:
        return None
    if volume_col not in df.columns:
        return None
    vol = df[volume_col]
    total_vol = float(vol.sum())
    if total_vol <= 0:
        return None
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    return float((typical * vol).sum() / total_vol)


def classify_auction_state(df: pd.DataFrame, num_bins: int = 24,
                            value_area_pct: float = 0.70,
                            imbalance_confirm_bars: int = 3,
                            volume_col: str = "tick_volume") -> Dict:
    """
    The real regime classifier this module exists to provide, replacing
    ADX-based trend/range detection everywhere it's used.

    BALANCE: last close is inside [VAL, VAH] -- the market is rotating
    inside its accepted value, the classic fade regime (see
    detect_balance_fade_signal).

    IMBALANCE_UP / IMBALANCE_DOWN: last close is outside the value area
    AND at least `imbalance_confirm_bars` of the most recent bars also
    closed beyond that edge -- genuine initiative follow-through, not a
    single wick poking outside value that closes back in (that's still
    BALANCE -- often the exact setup for a fade, not a breakout).

    Returns {state, poc, vah, val, vwap} -- state is one of "BALANCE",
    "IMBALANCE_UP", "IMBALANCE_DOWN", or None if the profile couldn't be
    computed (e.g. empty/degenerate data).
    """
    profile = compute_volume_profile(df, num_bins=num_bins, value_area_pct=value_area_pct,
                                      volume_col=volume_col)
    if profile["poc"] is None:
        return {"state": None, "poc": None, "vah": None, "val": None, "vwap": None}

    vah, val = profile["vah"], profile["val"]
    closes = df["close"].to_numpy()
    last_close = float(closes[-1])

    if last_close > vah:
        recent = closes[-imbalance_confirm_bars:] if len(closes) >= imbalance_confirm_bars else closes
        confirmed = bool(np.all(recent > vah))
        state = "IMBALANCE_UP" if confirmed else "BALANCE"
    elif last_close < val:
        recent = closes[-imbalance_confirm_bars:] if len(closes) >= imbalance_confirm_bars else closes
        confirmed = bool(np.all(recent < val))
        state = "IMBALANCE_DOWN" if confirmed else "BALANCE"
    else:
        state = "BALANCE"

    return {"state": state, "poc": profile["poc"], "vah": vah, "val": val, "vwap": profile["vwap"]}


# =============================================================================
# LIQUIDITY MAP
# =============================================================================

def find_swing_points(df: pd.DataFrame, lookback: int = 3) -> Tuple[List[int], List[int]]:
    """
    Fractal swing-point detection -- same technique structural_swing_pro.py
    uses, reimplemented locally here rather than imported so this module
    has zero dependency on any of the three live bot files (it's imported
    BY them, never the other way -- a shared module importing a specific
    bot script would be exactly backwards and would break the moment that
    script's own CLI-argument-parsing module-scope code ran on import).
    """
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
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


def build_liquidity_map(df: pd.DataFrame, lookback: int = 3,
                         equal_tolerance_atr_mult: float = 0.15,
                         atr_period: int = 14) -> List[Dict]:
    """
    Maps where stops actually cluster: groups nearby detected swing
    highs/lows (within `equal_tolerance_atr_mult` * ATR of each other --
    "equal highs/lows" in SMC/ICT terms) into liquidity pools, and marks
    each SWEPT (price has already traded through it since it formed) or
    UNTESTED (still sitting there, a real magnet for price).

    This is the generalized version of what Shaakuni SSM / AOX already do
    narrowly for their own entries -- exposed here so any strategy can
    check "is there a real liquidity pool between here and my target."

    Returns a list of {price, side: 'BUY_SIDE'|'SELL_SIDE', touches,
    swept}, nearest-to-current-price first. 'BUY_SIDE' pools sit above
    current price (sell-stops/breakout-buy-stops rest there in SMC terms
    -- price is drawn UP to take them); 'SELL_SIDE' pools sit below.
    """
    if df is None or len(df) < lookback * 2 + 5:
        return []

    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - df["close"].shift()).abs()
    tr3 = (df["low"] - df["close"].shift()).abs()
    atr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(atr_period).mean().iloc[-1]
    if pd.isna(atr) or atr <= 0:
        return []
    tolerance = atr * equal_tolerance_atr_mult

    swing_highs, swing_lows = find_swing_points(df, lookback)
    current_price = float(df["close"].iloc[-1])
    highs_arr = df["high"].to_numpy()
    lows_arr = df["low"].to_numpy()
    n = len(df)

    def _group(indices: List[int], values: np.ndarray, side: str) -> List[Dict]:
        if not indices:
            return []
        # Sort by price so nearby levels are adjacent, then cluster.
        sorted_idx = sorted(indices, key=lambda i: values[i])
        pools: List[Dict] = []
        cluster = [sorted_idx[0]]
        for idx in sorted_idx[1:]:
            if abs(values[idx] - values[cluster[-1]]) <= tolerance:
                cluster.append(idx)
            else:
                pools.append(cluster)
                cluster = [idx]
        pools.append(cluster)

        result = []
        for cluster in pools:
            price = float(np.mean([values[i] for i in cluster]))
            formed_at = max(cluster)  # most recent pivot in this cluster
            # Swept if any bar AFTER the pool formed traded through it.
            if side == "BUY_SIDE":
                swept = bool((highs_arr[formed_at + 1:] >= price).any()) if formed_at + 1 < n else False
            else:
                swept = bool((lows_arr[formed_at + 1:] <= price).any()) if formed_at + 1 < n else False
            result.append({
                "price": price, "side": side, "touches": len(cluster), "swept": swept,
            })
        return result

    buy_side = [p for p in _group(swing_highs, highs_arr, "BUY_SIDE") if p["price"] > current_price]
    sell_side = [p for p in _group(swing_lows, lows_arr, "SELL_SIDE") if p["price"] < current_price]

    pools = buy_side + sell_side
    pools.sort(key=lambda p: abs(p["price"] - current_price))
    return pools


def is_rejection_candle(bar: pd.Series, direction: str) -> bool:
    """Same definition structural_swing_pro.py uses -- a bar that closes
    back in `direction` occupying at least the top (BUY) / bottom (SELL)
    60% of its own range. Reimplemented locally for the same
    no-cross-bot-import reason find_swing_points is."""
    rng = bar["high"] - bar["low"]
    if rng <= 0:
        return False
    if direction == "BUY":
        return bar["close"] > bar["open"] and (bar["close"] - bar["low"]) / rng >= 0.6
    return bar["close"] < bar["open"] and (bar["high"] - bar["close"]) / rng >= 0.6


# =============================================================================
# BALANCE FADE -- the actual missing strategy archetype
# =============================================================================

def detect_balance_fade_signal(df: pd.DataFrame, symbol: str, num_bins: int = 24,
                                value_area_pct: float = 0.70, min_rr: float = 1.5,
                                sl_buffer_atr_mult: float = 0.25,
                                liquidity_guard_atr_mult: float = 0.5,
                                atr_period: int = 14) -> Optional[Dict]:
    """
    Pure, no-lookahead decision function -- the mean-reversion strategy
    this whole codebase was missing. Every other strategy across all three
    bots is trend/breakout/continuation; this is the one designed to
    profit from the regime the market is actually in most of the time:
    rotating inside its own value area.

    Fires ONLY when classify_auction_state() reads BALANCE. Entry: price
    at the value area edge (VAH for a SELL fade, VAL for a BUY fade),
    confirmed by a rejection candle (price actually turned there, not just
    touched it). Stop: beyond the value area extreme, buffered by ATR.
    Target: POC, extended to VWAP if VWAP is further from entry but still
    inside the value area (a fuller mean-reversion target without chasing
    price beyond where it's actually been accepted). Skipped below min_rr.

    Institutional discipline before taking the fade: build_liquidity_map()
    is checked for an UNTESTED liquidity pool sitting just beyond the
    value area edge, in the direction price would need to move to
    invalidate the fade (a BUY_SIDE pool just above VAH for a SELL fade, a
    SELL_SIDE pool just below VAL for a BUY fade). If one exists within
    `liquidity_guard_atr_mult` * ATR of the edge, the fade is skipped --
    price is more likely to run that pool first (sweep the obvious stops)
    than respect the value area edge on the first touch. This is the same
    "don't fade until liquidity is actually taken" logic Shaakuni/AOX
    already use for their own reversal entries, applied here specifically
    to protect the fade from the single most common way a mean-reversion
    trade gets run over.

    df's LAST row must be the most recently CLOSED bar as of "now" --
    callers (live loop, backtest driver) are responsible for that, same
    contract as structural_swing_pro.py's detect_structural_swing_signal.
    """
    if df is None or len(df) < num_bins + atr_period + 5:
        return None

    auction = classify_auction_state(df, num_bins=num_bins, value_area_pct=value_area_pct)
    if auction["state"] != "BALANCE":
        return None

    vah, val, poc, vwap = auction["vah"], auction["val"], auction["poc"], auction["vwap"]
    bar = df.iloc[-1]
    high, low = float(bar["high"]), float(bar["low"])

    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - df["close"].shift()).abs()
    tr3 = (df["low"] - df["close"].shift()).abs()
    atr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(atr_period).mean().iloc[-1]
    if pd.isna(atr) or atr <= 0:
        return None

    liquidity = build_liquidity_map(df, atr_period=atr_period)

    direction = None
    if high >= vah and is_rejection_candle(bar, "SELL"):
        # Guard: an untested BUY_SIDE pool just above VAH means price is
        # more likely to sweep it first than reverse here.
        guard_hit = any(p["side"] == "BUY_SIDE" and not p["swept"]
                         and 0 <= p["price"] - vah <= atr * liquidity_guard_atr_mult
                         for p in liquidity)
        if not guard_hit:
            direction = "SELL"
    elif low <= val and is_rejection_candle(bar, "BUY"):
        guard_hit = any(p["side"] == "SELL_SIDE" and not p["swept"]
                         and 0 <= val - p["price"] <= atr * liquidity_guard_atr_mult
                         for p in liquidity)
        if not guard_hit:
            direction = "BUY"

    if direction is None:
        return None

    entry_price = float(bar["close"])
    buffer = atr * sl_buffer_atr_mult

    if direction == "SELL":
        stop_loss = vah + buffer
        # Target POC, extended to VWAP if VWAP is further but still <= VAH
        # (a fuller mean-reversion target without chasing beyond value).
        take_profit = poc
        if vwap is not None and vwap < poc and vwap >= val:
            take_profit = vwap
    else:
        stop_loss = val - buffer
        take_profit = poc
        if vwap is not None and vwap > poc and vwap <= vah:
            take_profit = vwap

    sl_dist = abs(entry_price - stop_loss)
    if sl_dist <= 0:
        return None
    reward_dist = abs(take_profit - entry_price)
    if reward_dist <= 0 or reward_dist / sl_dist < min_rr:
        return None

    return {
        "direction": direction, "entry_price": entry_price, "stop_loss": stop_loss,
        "take_profit": take_profit,
        "reason": f"BALANCE_FADE_{direction}_RR{reward_dist / sl_dist:.1f}",
        "poc": poc, "vah": vah, "val": val, "vwap": vwap,
    }


# =============================================================================
# INTERMARKET CONFIRMATION
# =============================================================================

def compute_intermarket_bias(primary_df: pd.DataFrame, correlated_df: pd.DataFrame,
                              expected_correlation_sign: int, lookback: int = 20) -> Dict:
    """
    Generalizes AOX's SMT-divergence concept (previously one narrow gate
    on one strategy) into a reusable cross-market confirmation check any
    strategy can call. `expected_correlation_sign`: +1 if the two symbols
    normally move together (e.g. two risk-on equity indices), -1 if they
    normally move opposite (e.g. XAUUSDm vs a USD-strength proxy -- gold
    and the dollar are typically inversely correlated).

    Compares each symbol's % move over `lookback` bars. CONFIRMING: both
    moved in the direction the expected correlation predicts. DIVERGING:
    the correlated market moved against what the primary market's own move
    would predict -- a real warning sign, not noise (e.g. gold breaking to
    a new high while the dollar is ALSO strengthening, not weakening, is
    exactly the kind of divergence that precedes a failed breakout).

    Returns {bias: 'CONFIRMING'|'DIVERGING'|'NEUTRAL', primary_pct_move,
    correlated_pct_move}. NEUTRAL if either series is too short or flat.
    """
    empty = {"bias": "NEUTRAL", "primary_pct_move": None, "correlated_pct_move": None}
    if primary_df is None or correlated_df is None:
        return empty
    if len(primary_df) < lookback + 1 or len(correlated_df) < lookback + 1:
        return empty

    p_now, p_then = float(primary_df["close"].iloc[-1]), float(primary_df["close"].iloc[-lookback - 1])
    c_now, c_then = float(correlated_df["close"].iloc[-1]), float(correlated_df["close"].iloc[-lookback - 1])
    if p_then == 0 or c_then == 0:
        return empty

    p_move = (p_now - p_then) / p_then
    c_move = (c_now - c_then) / c_then

    # Flat correlated market (no real move either way) carries no signal.
    if abs(c_move) < 1e-6:
        return {"bias": "NEUTRAL", "primary_pct_move": p_move, "correlated_pct_move": c_move}

    same_sign = (p_move > 0) == (c_move > 0)
    confirming = same_sign if expected_correlation_sign > 0 else not same_sign
    bias = "CONFIRMING" if confirming else "DIVERGING"
    return {"bias": bias, "primary_pct_move": p_move, "correlated_pct_move": c_move}


# =============================================================================
# VOLATILITY-TARGET SIZING
# =============================================================================

def volatility_target_multiplier(df: pd.DataFrame, atr_period: int = 14,
                                  lookback: int = 100, floor: float = 0.5,
                                  ceiling: float = 1.5) -> float:
    """
    Standard vol-targeting: scales position size by where CURRENT realized
    volatility (ATR) sits relative to its own trailing distribution over
    `lookback` bars, instead of every trade risking the same flat % of
    equity regardless of how calm or violent the instrument currently is.

    Returns a multiplier (clamped to [floor, ceiling], default [0.5, 1.5])
    to apply on top of a strategy's base risk_percent -- current ATR at
    the median of its trailing distribution returns ~1.0 (no adjustment);
    elevated current vol (near the top of its own recent range) scales
    size DOWN toward `floor`; compressed current vol scales size UP toward
    `ceiling`, capped so a genuinely dead-quiet reading doesn't blow past a
    sane sizing bound. Returns 1.0 (no adjustment) if there's not enough
    history to compute a meaningful distribution.
    """
    if df is None or len(df) < atr_period + lookback:
        return 1.0

    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - df["close"].shift()).abs()
    tr3 = (df["low"] - df["close"].shift()).abs()
    atr_series = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(atr_period).mean()
    recent = atr_series.tail(lookback).dropna()
    if len(recent) < lookback // 2:
        return 1.0

    current_atr = float(atr_series.iloc[-1])
    median_atr = float(recent.median())
    if pd.isna(current_atr) or median_atr <= 0:
        return 1.0

    ratio = current_atr / median_atr
    # Inverse relationship: higher current vol -> lower size multiplier.
    multiplier = 1.0 / ratio
    return float(max(floor, min(ceiling, multiplier)))


# =============================================================================
# COT (COMMITMENT OF TRADERS) POSITIONING
# =============================================================================

# Maps this bot's symbols to the CFTC's "legacy" report contract market
# codes (the CFTC Commodity Index Number, from the public
# https://www.cftc.gov/dea/newcot/deafut.txt legacy futures-only report).
# Only symbols with a clean, liquid, single-contract COT mapping are
# included -- FX majors trade as currency futures with genuine COT data
# too, but mapping a CFD pair to the right contract code is more ambiguous
# and left out here rather than guessed.
COT_CONTRACT_CODES = {
    "XAUUSDm": "088691",   # GOLD - COMMODITY EXCHANGE INC.
    "XAGUSDm": "084691",   # SILVER - COMMODITY EXCHANGE INC.
    "USOILm": "067651",    # CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE
}

_cot_cache: Dict[str, Dict] = {}
_COT_CACHE_TTL_SECONDS = 6 * 24 * 3600  # ~weekly -- COT is only published Fridays


def fetch_cot_positioning(symbol: str, timeout: int = 15) -> Optional[Dict]:
    """
    Best-effort fetch of the latest CFTC legacy futures-only COT report row
    for `symbol`'s underlying contract, cached for ~6 days (COT updates
    weekly). Returns None on ANY failure -- unmapped symbol, network
    unreachable, unexpected report format -- same "no data -> neutral,
    never blocks trading" contract every AI-optional fallback in this
    codebase already follows. NOT independently verified end-to-end in
    this sandbox: cftc.gov is blocked by this environment's outbound
    network policy (confirmed via a direct request, not assumed). Verify
    this on a real deployment host with normal internet access before
    trusting it; if it fails there too, callers degrade to a neutral bias
    exactly as if this function were never called.

    Returns {noncomm_long, noncomm_short, noncomm_net, report_date} on
    success -- "noncommercial" is the CFTC's own label for large
    speculators (funds, institutional positioning), the figure a
    contrarian positioning read is actually based on.
    """
    contract_code = COT_CONTRACT_CODES.get(symbol)
    if not contract_code:
        return None

    cached = _cot_cache.get(symbol)
    if cached and (time.time() - cached["_fetched_at"]) < _COT_CACHE_TTL_SECONDS:
        return cached

    try:
        import requests
        resp = requests.get("https://www.cftc.gov/dea/newcot/deafut.txt", timeout=timeout)
        resp.raise_for_status()
        for line in resp.text.splitlines():
            fields = [f.strip() for f in line.split(",")]
            if len(fields) < 12 or fields[1] != contract_code:
                continue
            # Legacy report column layout (0-indexed):
            # 0 name, 1 code, 2 date, ... 8 noncommercial-long,
            # 9 noncommercial-short, ... (see CFTC's own column key at
            # https://www.cftc.gov/MarketReports/CommitmentsofTraders/ExplanatoryNotes)
            report_date = fields[2]
            noncomm_long = float(fields[8])
            noncomm_short = float(fields[9])
            result = {
                "noncomm_long": noncomm_long, "noncomm_short": noncomm_short,
                "noncomm_net": noncomm_long - noncomm_short, "report_date": report_date,
                "_fetched_at": time.time(),
            }
            _cot_cache[symbol] = result
            return result
        return None
    except Exception:
        return None


def cot_positioning_bias(cot_data: Optional[Dict], extreme_percentile_hint: float = 0.80) -> Dict:
    """
    Pure interpretation of an already-fetched COT snapshot -- separated
    from fetch_cot_positioning() specifically so this logic is unit-testable
    without any network dependency. `extreme_percentile_hint` isn't computed
    from a real historical percentile here (that needs a stored time series
    this single-snapshot function doesn't have) -- it's a placeholder
    signal ratio threshold; a real deployment should track fetched
    snapshots over time and replace this with a genuine trailing
    percentile once enough history has accumulated. Documented as a
    disclosed simplification, not silently presented as more rigorous than
    it is.

    Returns {bias: 'CROWDED_LONG'|'CROWDED_SHORT'|'NEUTRAL', net_ratio}
    where net_ratio = noncomm_net / (noncomm_long + noncomm_short) -- +1.0
    would mean 100% of large-speculator positioning is long, -1.0 100%
    short. CROWDED_LONG (a contrarian bearish tilt) when net_ratio is
    strongly positive; CROWDED_SHORT (contrarian bullish tilt) when
    strongly negative.
    """
    if not cot_data:
        return {"bias": "NEUTRAL", "net_ratio": None}
    total = cot_data["noncomm_long"] + cot_data["noncomm_short"]
    if total <= 0:
        return {"bias": "NEUTRAL", "net_ratio": None}
    net_ratio = cot_data["noncomm_net"] / total
    if net_ratio >= extreme_percentile_hint:
        return {"bias": "CROWDED_LONG", "net_ratio": net_ratio}
    if net_ratio <= -extreme_percentile_hint:
        return {"bias": "CROWDED_SHORT", "net_ratio": net_ratio}
    return {"bias": "NEUTRAL", "net_ratio": net_ratio}
