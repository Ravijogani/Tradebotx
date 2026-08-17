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

6. Liquidity REFERENCE levels + HTF fair value gaps, as a shared entry
   confluence check and TP source. compute_liquidity_reference_levels()
   computes the specific named levels professional/SMC traders actually
   watch -- previous day high/low, the last closed H1 candle's high/low,
   and the realized range of the last completed Asian/London/New York
   session -- each tagged swept/untested, same convention as
   build_liquidity_map()'s equal-highs/lows pools (this is the *named*
   reference-level layer; build_liquidity_map is the *generic* fractal-
   clustering layer -- complementary, not redundant). detect_fvg_zones()
   generalizes the existing M1-only AOX fair-value-gap detector to any
   timeframe (H1/H4 included -- the 3-candle imbalance definition never
   needed to be M1-specific). liquidity_confluence_check() answers "is
   this entry actually reacting to a real level, or sitting in open air"
   as an entry-quality gate; nearest_liquidity_target() answers "what's
   the next real liquidity level in my direction" as a TP source --
   generalizes intraday.py's detect_htf_liquidity_targets() (which did
   exactly this with D1 swing highs/prev-day H/L, but was never wired
   into a single live call site) to every reference level above, usable
   by any strategy in any of the three bots.

7. Market regime router. classify_market_regime() is the answer to "the
   bot should be smart enough to trade in all conditions" -- not by
   knowing more strategies (this exact repo already tried that: 11
   well-known concepts -- Wyckoff, volume profile, S/R, ICT killzones,
   liquidity grab, FVG retest, mean-reversion BB, trend pullback -- were
   built, wired, and removed after producing zero real edge; see
   strategies_registry.py's "REMOVED 2026-08" note), but by routing among
   the strategies already validated here: TREND_UP/DOWN (a genuine
   auction imbalance, what SSM/Swappy/EMA-Scalp are actually built for),
   BALANCE (rotating inside value -- none of hybrid_trading_bot_
   multiuser.py's live strategies fit; that's what detect_balance_
   fade_signal exists for, elsewhere), or CHOPPY (no reliable read, or
   conflicting M5-auction-vs-M30-structure evidence). BALANCE and CHOPPY
   both resolve to an explicit, first-class STAND-ASIDE state -- no
   strategy fires -- which nothing in this codebase modeled before this.

8. Premium/Discount (equilibrium) zones + Optimal Trade Entry (OTE).
   Researched directly off two more named traders (Raja Banks' "Smart Raja
   Concepts" and Guardeer's ICT/SMC mentorship material) -- both teach
   standard ICT vocabulary that substantially overlaps with what's already
   above (liquidity, order blocks, FVG, BOS/CHoCH, HTF structure), but two
   pieces were genuinely new here: compute_equilibrium_zone() classifies
   current price as PREMIUM (expensive half of the most recent dealing
   range -- favor selling the reaction) or DISCOUNT (cheap half -- favor
   buying it), the 50%-midpoint directional filter both traders teach as a
   primary bias check. compute_ote_zone() refines WHERE inside an
   already-valid setup to actually enter: the classic 61.8%-79% Fibonacci
   retracement of the most recent impulse leg in the trade's direction --
   layered ON TOP of an order-block/FVG entry, not a replacement for one.
   Deliberately built and wired as SOFT modifiers only (confidence/RR
   nudges, never a hard veto) -- a same-session frequency audit found two
   of the three hybrid_trading_bot_multiuser.py strategies already firing
   under 0.25 trades/day after the regime-router and liquidity-confluence
   work, so adding another hard gate on top would have directly repeated
   the over-filtering risk being audited for, not fixed it.

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

    # DECISION JOURNAL -- imported lazily so this module keeps its zero
    # import-time dependencies (decision_journal is pure too, so there is no
    # cycle; the local import just keeps market_intelligence importable on its
    # own exactly as before).
    import decision_journal as _dj
    _j = _dj.DecisionJournal(symbol, strategy='BALANCE_FADE')
    _j.note(_dj.REGIME, 'auction_balance',
            _dj.CONFIRMED if auction["state"] == "BALANCE" else _dj.VETO,
            (f'auction state BALANCE -- rotating inside value, which is the only '
             f'regime this fade is designed for' if auction["state"] == "BALANCE"
             else f'auction state {auction["state"]} -- not a rotation, no fade here'),
            value=auction["state"])
    if auction["state"] != "BALANCE":
        _j.decide(False, f'auction state {auction["state"]} is not BALANCE')
        _dj.record_rejection(_j)
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

    # Record which edge was touched and whether the liquidity guard fired --
    # the guard is this strategy's single most important discipline (see the
    # docstring), so whether it vetoed is exactly what R&D needs to see.
    _at_vah = high >= vah
    _at_val = low <= val
    _j.note(_dj.LOCATION, 'at_value_area_edge',
            _dj.CONFIRMED if (_at_vah or _at_val) else _dj.VETO,
            ('price reached the value-area high (VAH) -- fade candidate' if _at_vah
             else 'price reached the value-area low (VAL) -- fade candidate' if _at_val
             else 'price is mid-value, not at either edge'),
            value='VAH' if _at_vah else 'VAL' if _at_val else None)
    if (_at_vah or _at_val) and direction is None:
        _j.note(_dj.LIQUIDITY, 'liquidity_guard',
                _dj.VETO,
                'an untested liquidity pool sits just beyond the edge -- price is '
                'more likely to sweep those stops than respect the edge on first touch')
    elif direction is not None:
        _j.direction = direction
        _j.note(_dj.LIQUIDITY, 'liquidity_guard', _dj.CONFIRMED,
                'no untested liquidity pool just beyond the edge -- the fade is not '
                'standing in front of an obvious stop-hunt target')
        _j.note(_dj.TRIGGER, 'rejection_candle', _dj.CONFIRMED,
                f'bar closed as a {direction} rejection at the edge -- price actually '
                f'turned here rather than only touching')

    if direction is None:
        _j.decide(False, 'no valid fade at a value-area edge')
        _dj.record_rejection(_j)
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
    _rr = (reward_dist / sl_dist) if sl_dist > 0 else 0.0
    _j.note(_dj.LIQUIDITY, 'target_inside_value',
            _dj.CONFIRMED,
            (f'target {take_profit:.5f} is the POC/VWAP -- mean reversion to where '
             f'volume actually transacted, not an arbitrary multiple'),
            value=round(float(take_profit), 5))
    _j.measure(rr=round(_rr, 2), min_rr_required=min_rr, atr=round(float(atr), 5),
               vah=round(float(vah), 5), val=round(float(val), 5), poc=round(float(poc), 5))
    if reward_dist <= 0 or reward_dist / sl_dist < min_rr:
        _j.note(_dj.RISK, 'rr_floor', _dj.VETO,
                f'RR {_rr:.2f} below the {min_rr:.1f} required')
        _j.decide(False, f'RR {_rr:.2f} < {min_rr:.1f}')
        _dj.record_rejection(_j)
        return None
    _j.note(_dj.RISK, 'rr_floor', _dj.CONFIRMED, f'RR {_rr:.2f} clears the {min_rr:.1f} bar')
    _j.decide(True, f'BALANCE fade at the value-area edge, RR {_rr:.2f}')

    return {
        "direction": direction, "entry_price": entry_price, "stop_loss": stop_loss,
        "take_profit": take_profit,
        "reason": f"BALANCE_FADE_{direction}_RR{reward_dist / sl_dist:.1f}",
        "poc": poc, "vah": vah, "val": val, "vwap": vwap,
        "journal": _j.to_dict(),
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


# =============================================================================
# LIQUIDITY REFERENCE LEVELS (PDH/PDL, session H/L) + HTF FAIR VALUE GAPS
# =============================================================================

# Session hour boundaries in UTC. Mirrors hybrid_trading_bot_multiuser.py's
# get_current_session() (LONDON_NY overlap 13-16 folded into LONDON there
# for time-of-day classification) but defined independently here -- this
# module has zero dependency on any bot file's config, same discipline as
# find_swing_points() being reimplemented rather than imported.
_SESSION_HOURS_UTC: Dict[str, Tuple[int, int]] = {
    "ASIAN": (0, 8),
    "LONDON": (7, 16),
    "NEW_YORK": (16, 22),
}


def compute_session_high_low(df_h1: pd.DataFrame, session_hours: Tuple[int, int]) -> Optional[Tuple[float, float, "pd.Timestamp"]]:
    """
    Finds the most recently COMPLETED occurrence of a UTC hour window
    (e.g. Asian session 00:00-08:00) in df_h1 and returns its realized
    (high, low, end_time). "Completed" matters: if the current bar is
    still inside that session, the range isn't final yet and using it as
    a liquidity reference would be premature -- so a trailing run of
    in-session bars that touches the very last row in df_h1 is skipped in
    favor of the previous complete run.

    Returns None if there's no complete occurrence yet (not enough
    history, or the only run found is still in progress).
    """
    if df_h1 is None or len(df_h1) < 3:
        return None
    times = pd.to_datetime(df_h1["time"])
    hours = times.dt.hour
    start, end = session_hours
    in_session = (hours >= start) & (hours < end)
    if not in_session.any():
        return None

    idx = np.where(in_session.to_numpy())[0]
    runs: List[Tuple[int, int]] = []
    run_start = idx[0]
    prev = idx[0]
    for i in idx[1:]:
        if i != prev + 1:
            runs.append((run_start, prev))
            run_start = i
        prev = i
    runs.append((run_start, prev))

    last_row_idx = len(df_h1) - 1
    if runs[-1][1] == last_row_idx:
        if len(runs) < 2:
            return None  # only run found is still in progress -- nothing complete yet
        chosen = runs[-2]
    else:
        chosen = runs[-1]

    seg = df_h1.iloc[chosen[0]:chosen[1] + 1]
    return float(seg["high"].max()), float(seg["low"].min()), df_h1["time"].iloc[chosen[1]]


def compute_liquidity_reference_levels(df_d1: Optional[pd.DataFrame],
                                        df_h1: Optional[pd.DataFrame]) -> List[Dict]:
    """
    The specific NAMED liquidity levels professional/SMC traders actually
    watch -- distinct from build_liquidity_map()'s generic equal-highs/
    lows clustering:
      - PDH / PDL: previous COMPLETED daily candle's high/low (df_d1's
        second-to-last row -- the last row can still be today's
        in-progress day, same "don't use the still-forming bar"
        discipline as everywhere else in this module).
      - H1_HIGH / H1_LOW: the most recently CLOSED H1 candle's high/low
        (df_h1's second-to-last row, for the same reason).
      - {ASIAN,LONDON,NEW_YORK}_HIGH/LOW: the realized range of the last
        COMPLETED occurrence of each session (see compute_session_high_low).

    Each level is tagged BUY_SIDE (sits above current price -- price is
    drawn UP to take resting sell-stops/breakout orders there, same
    convention build_liquidity_map() uses) or SELL_SIDE (below), and
    swept (price has since traded through it, checked against the H1
    series regardless of which timeframe the level itself came from --
    H1 is granular enough to catch an intraday sweep of yesterday's PDH
    that hasn't yet produced a new D1 bar above it) or still untested.

    Returns a list of {label, price, side, swept}, nearest-to-current-
    price first. Pure function -- no MT5, callable identically live and
    in the backtest harness.
    """
    if df_h1 is None or len(df_h1) < 3:
        return []
    current_price = float(df_h1["close"].iloc[-1])
    levels: List[Dict] = []

    highs = df_h1["high"].to_numpy()
    lows = df_h1["low"].to_numpy()

    def _swept_since(price: float, side: str) -> bool:
        if side == "BUY_SIDE":
            return bool((highs >= price).any())
        return bool((lows <= price).any())

    def _add(label: str, price: Optional[float]):
        if price is None or pd.isna(price):
            return
        side = "BUY_SIDE" if price > current_price else "SELL_SIDE"
        levels.append({"label": label, "price": float(price), "side": side,
                        "swept": _swept_since(float(price), side)})

    if df_d1 is not None and len(df_d1) >= 2:
        _add("PDH", float(df_d1["high"].iloc[-2]))
        _add("PDL", float(df_d1["low"].iloc[-2]))

    if len(df_h1) >= 3:
        _add("H1_HIGH", float(df_h1["high"].iloc[-2]))
        _add("H1_LOW", float(df_h1["low"].iloc[-2]))

    for sess_label, hours in _SESSION_HOURS_UTC.items():
        res = compute_session_high_low(df_h1, hours)
        if res:
            hi, lo, _ = res
            _add(f"{sess_label}_HIGH", hi)
            _add(f"{sess_label}_LOW", lo)

    levels.sort(key=lambda lvl: abs(lvl["price"] - current_price))
    return levels


def detect_fvg_zones(df: pd.DataFrame, direction: str, lookback: int = 20,
                      max_zones: int = 3) -> List[Dict]:
    """
    Fair Value Gap detection, generalized to any timeframe. The existing
    detect_fpfvg() in hybrid_trading_bot_multiuser.py only ever runs on
    M1 (for AOX), but the 3-candle-imbalance definition itself is
    timeframe-agnostic -- the same textbook ICT gap, just reimplemented
    here (not imported, same zero-dependency-on-bot-files discipline as
    find_swing_points()) so H1/H4 FVGs are usable by any strategy in any
    of the three bots, not only AOX's M1 read.

    Bullish FVG: candle[i-1].high < candle[i+1].low (the displacement
    candle at i left a gap nothing has traded back into).
    Bearish FVG: candle[i-1].low > candle[i+1].high.

    Returns up to `max_zones` UNMITIGATED gaps (price hasn't traded back
    into the zone since), most recent first: {low, high, mid, direction}.
    """
    if df is None or len(df) < lookback + 3:
        return []
    zones: List[Dict] = []
    start = max(2, len(df) - lookback)
    for i in range(len(df) - 2, start - 1, -1):
        c_before = df.iloc[i - 1]
        c_after = df.iloc[i + 1]
        if direction == "BUY":
            if float(c_before["high"]) < float(c_after["low"]):
                gap_low, gap_high = float(c_before["high"]), float(c_after["low"])
                later_lows = df["low"].iloc[i + 2:]
                mitigated = bool((later_lows <= gap_high).any()) if len(later_lows) else False
                if not mitigated:
                    zones.append({"low": gap_low, "high": gap_high,
                                  "mid": (gap_low + gap_high) / 2, "direction": "BUY"})
        else:
            if float(c_before["low"]) > float(c_after["high"]):
                gap_high, gap_low = float(c_before["low"]), float(c_after["high"])
                later_highs = df["high"].iloc[i + 2:]
                mitigated = bool((later_highs >= gap_low).any()) if len(later_highs) else False
                if not mitigated:
                    zones.append({"low": gap_low, "high": gap_high,
                                  "mid": (gap_low + gap_high) / 2, "direction": "SELL"})
        if len(zones) >= max_zones:
            break
    return zones


def liquidity_confluence_check(entry_price: float, direction: str, levels: List[Dict],
                                fvg_zones: Optional[List[Dict]] = None,
                                atr: Optional[float] = None,
                                tolerance_atr_mult: float = 0.5) -> Dict:
    """
    Entry-quality gate: is this entry actually reacting to a real
    liquidity reference, or sitting in open air with no reason for orders
    to be resting there? A setup at a random price is a weaker entry than
    one at a level real participants are actually watching.

    For BUY: supporting confluence = an UNTESTED SELL_SIDE reference
    level (a prior low / session low / PDL -- demand is expected to
    defend there) at or just below entry_price, or entry sitting inside
    (or just above) a bullish unmitigated FVG. SELL mirrors this.

    tolerance_atr_mult (default 0.5x ATR, or ~0.15% of price if atr isn't
    supplied): how close entry needs to be to count as "at" the level --
    real liquidity has a zone, not a single tick.

    Returns {'confluent': bool, 'matched_level': Optional[str], 'reason': str}.
    Pure function -- no MT5, callable identically live and in the
    backtest harness.
    """
    tolerance = (atr * tolerance_atr_mult) if atr else abs(entry_price) * 0.0015
    supporting_side = "SELL_SIDE" if direction == "BUY" else "BUY_SIDE"

    for lvl in levels or []:
        if lvl["side"] != supporting_side or lvl["swept"]:
            continue
        if direction == "BUY" and lvl["price"] <= entry_price and entry_price - lvl["price"] <= tolerance:
            return {"confluent": True, "matched_level": lvl["label"],
                    "reason": f"at untested {lvl['label']} ({lvl['price']:.4f})"}
        if direction == "SELL" and lvl["price"] >= entry_price and lvl["price"] - entry_price <= tolerance:
            return {"confluent": True, "matched_level": lvl["label"],
                    "reason": f"at untested {lvl['label']} ({lvl['price']:.4f})"}

    for fvg in fvg_zones or []:
        if fvg["direction"] != direction:
            continue
        if fvg["low"] - tolerance <= entry_price <= fvg["high"] + tolerance:
            return {"confluent": True, "matched_level": "FVG",
                    "reason": f"inside {direction} FVG [{fvg['low']:.4f}-{fvg['high']:.4f}]"}

    return {"confluent": False, "matched_level": None,
            "reason": "no untested reference level or FVG near entry"}


def nearest_liquidity_target(entry_price: float, direction: str, levels: List[Dict],
                              sl_distance: float, min_rr: float = 1.5) -> Optional[float]:
    """
    Finds the nearest UNTESTED reference level beyond entry, in the trade
    direction, that clears min_rr against sl_distance. Generalizes
    intraday.py's dead detect_htf_liquidity_targets() (same "prev day
    high/low as TP target" idea, but only ever built for D1 swings and
    never wired into a single live call site) to every reference level
    compute_liquidity_reference_levels() returns, usable by any strategy
    in any of the three bots.

    Returns None if nothing qualifies -- the caller keeps its own
    existing TP unchanged, same "never overwrite a strategy's own
    already-correct target" discipline detect_balance_fade_signal's
    live-wiring already established.
    """
    if sl_distance <= 0:
        return None
    target_side = "BUY_SIDE" if direction == "BUY" else "SELL_SIDE"
    candidates: List[Tuple[float, float]] = []
    for lvl in levels or []:
        if lvl["side"] != target_side or lvl["swept"]:
            continue
        dist = abs(lvl["price"] - entry_price)
        if sl_distance > 0 and dist / sl_distance >= min_rr:
            candidates.append((dist, lvl["price"]))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0])
    return candidates[0][1]


# =============================================================================
# MARKET REGIME ROUTER -- decide WHICH strategy archetype fits right now,
# not add another one
# =============================================================================

def classify_market_regime(auction: Dict, m30_char: Optional[Dict] = None) -> Dict:
    """
    Synthesizes signals this module (and classify_m30_character() in
    hybrid_trading_bot_multiuser.py) already compute into ONE coherent
    per-scan regime read, with an explicit STAND-ASIDE state -- the piece
    that was missing. This is not a new strategy or a new indicator: it's
    routing among strategies already built and real-data validated
    elsewhere in this codebase, which is the actual, evidence-backed
    answer to "the bot should be smart enough to trade in all conditions."
    (This exact repo already tried the other interpretation -- give the
    bot more strategies/indicators/concepts -- and removed 11 of them
    after they produced zero real edge; see strategies_registry.py's
    "REMOVED 2026-08" note. More knowledge didn't make the bot smarter.
    Knowing which of a small number of validated setups fits the current
    market, and knowing when none of them do, is what "smart" means here.)

    Takes the ALREADY-COMPUTED auction (classify_auction_state()) and
    m30_char (classify_m30_character(), optional) dicts rather than raw
    DataFrames -- this function does no new computation of its own beyond
    combining two results the caller already has, so wiring it in is free.

    Regime logic:
      - auction IMBALANCE_UP/DOWN -> TREND_UP/TREND_DOWN: a genuine
        initiative move, the one condition SSM/Swappy/EMA-Scalp-style
        continuation strategies are actually built for.
      - auction BALANCE -> BALANCE: price rotating inside its value area.
        None of this codebase's currently-live hybrid_trading_bot_
        multiuser.py strategies are a fade/mean-reversion archetype (that
        gap is what detect_balance_fade_signal() exists to fill, wired
        into intraday.py/structural_swing_pro.py already) -- so BALANCE
        here means no strategy in THIS file's lineup should fire, not
        that the market is untradeable in general.
      - auction None/insufficient data -> CHOPPY: no reliable read at all.
      - CHoCH CONFLICT: if the auction state says TREND_UP/DOWN but
        m30_char reports a CHoCH break in the OPPOSITE direction (M30's
        own structure just flipped against what the M5 auction read is
        claiming), that's genuinely conflicting evidence, not confidently
        trending -- downgraded to CHOPPY rather than trusted at face
        value. BOS (confirming the trend) or no m30_char signal at all
        both pass through unaffected.

    Returns {'regime': 'TREND_UP'|'TREND_DOWN'|'BALANCE'|'CHOPPY',
    'allowed_directions': frozenset of 'BUY'/'SELL' (empty for BALANCE/
    CHOPPY -- the explicit stand-aside case), 'reason': str}.
    """
    state = auction.get("state") if auction else None

    if state == "IMBALANCE_UP":
        regime = "TREND_UP"
        reason = "auction IMBALANCE_UP -- genuine initiative move higher"
    elif state == "IMBALANCE_DOWN":
        regime = "TREND_DOWN"
        reason = "auction IMBALANCE_DOWN -- genuine initiative move lower"
    elif state == "BALANCE":
        regime = "BALANCE"
        reason = "auction BALANCE -- rotating inside value, no continuation edge here"
    else:
        regime = "CHOPPY"
        reason = "no reliable auction-state read"

    if m30_char and regime in ("TREND_UP", "TREND_DOWN"):
        opposing = "BEARISH" if regime == "TREND_UP" else "BULLISH"
        if m30_char.get("signal") == "CHOCH" and m30_char.get("break_direction") == opposing:
            regime = "CHOPPY"
            reason = (f"auction said {state} but M30 structure just flipped "
                      f"{m30_char['break_direction']} -- conflicting evidence, not confidently trending")

    allowed = {
        "TREND_UP": frozenset({"BUY"}),
        "TREND_DOWN": frozenset({"SELL"}),
        "BALANCE": frozenset(),
        "CHOPPY": frozenset(),
    }[regime]

    return {"regime": regime, "allowed_directions": allowed, "reason": reason}


# =============================================================================
# PREMIUM/DISCOUNT (EQUILIBRIUM) ZONES + OPTIMAL TRADE ENTRY (OTE)
# =============================================================================

def compute_equilibrium_zone(df: pd.DataFrame, lookback: int = 3) -> Optional[Dict]:
    """
    ICT/SMC "Premium & Discount": the current dealing range's most recent
    swing high and swing low (from find_swing_points() -- reused, not
    reimplemented, since it already lives in this module) bound a range.
    The 50% midpoint is "equilibrium." Price trading above it is PREMIUM
    (expensive relative to the range -- Raja Banks/Guardeer both teach
    favoring sells here), below it is DISCOUNT (cheap -- favor buys).

    Uses whichever of the most recent swing high / swing low is more
    recent as one bound, and the highest high / lowest low from a short
    trailing window around it as the other -- in practice, the simplest
    robust version of "the current dealing range" is just the most recent
    swing high and most recent swing low regardless of which came first;
    that's what's used here.

    Returns {zone: 'PREMIUM'|'DISCOUNT'|'EQUILIBRIUM', equilibrium, high,
    low, pct} where pct is current price's position in [0, 1] across
    [low, high] (0.5 = exactly at equilibrium). Returns None if there
    aren't at least one swing high and one swing low yet, or if they
    don't bound a real range.
    """
    if df is None or len(df) < lookback * 2 + 1:
        return None
    swing_highs, swing_lows = find_swing_points(df, lookback)
    if not swing_highs or not swing_lows:
        return None

    high_price = float(df["high"].iloc[swing_highs[-1]])
    low_price = float(df["low"].iloc[swing_lows[-1]])
    if high_price <= low_price:
        return None

    current_price = float(df["close"].iloc[-1])
    equilibrium = (high_price + low_price) / 2.0
    rng = high_price - low_price
    pct = (current_price - low_price) / rng

    if current_price > equilibrium:
        zone = "PREMIUM"
    elif current_price < equilibrium:
        zone = "DISCOUNT"
    else:
        zone = "EQUILIBRIUM"

    return {"zone": zone, "equilibrium": equilibrium, "high": high_price,
            "low": low_price, "pct": pct}


def premium_discount_confluence(direction: str, equilibrium_info: Optional[Dict]) -> Dict:
    """
    Directional read on an equilibrium zone: a BUY is "favorable" in
    DISCOUNT or right at EQUILIBRIUM, a SELL is "favorable" in PREMIUM or
    at EQUILIBRIUM. Deliberately returns a soft `favorable` flag, not a
    verdict a caller is forced to veto on -- see this module's docstring
    (section 8) for why: real-data trade-frequency evidence this session
    showed some of these strategies already fire under 0.25 trades/day,
    so this is meant to nudge a confidence/RR score, not gate entries
    outright, unless a specific strategy's own real-data check justifies
    a harder use (same pattern liquidity_confluence_check() established).

    Returns {favorable: bool, zone: str|None, reason: str}. No dealing
    range available (equilibrium_info is None) returns favorable=True --
    absence of information should never itself block a trade.
    """
    if not equilibrium_info:
        return {"favorable": True, "zone": None, "reason": "no dealing range available yet"}

    zone = equilibrium_info["zone"]
    if direction == "BUY":
        favorable = zone in ("DISCOUNT", "EQUILIBRIUM")
    elif direction == "SELL":
        favorable = zone in ("PREMIUM", "EQUILIBRIUM")
    else:
        favorable = True

    reason = (f"price in {zone} zone ({equilibrium_info['pct']:.0%} of the "
              f"{equilibrium_info['low']:.5f}-{equilibrium_info['high']:.5f} "
              f"dealing range) for a {direction}")
    return {"favorable": favorable, "zone": zone, "reason": reason}


def compute_ote_zone(df: pd.DataFrame, direction: str, lookback: int = 3,
                      fib_low: float = 0.618, fib_high: float = 0.79) -> Optional[Dict]:
    """
    ICT "Optimal Trade Entry" -- refines WHERE inside an already-valid
    setup to actually enter, layered on top of an order-block/FVG entry,
    not a replacement for one. For a BUY, finds the most recent up-leg
    (a swing low followed by a later swing high) and returns the
    `fib_low`-`fib_high` (61.8%-79% by default) retracement zone measured
    back down from the high -- the classic "let it come back and get you"
    pullback zone. Mirrors this for a SELL off the most recent down-leg
    (swing high followed by a later swing low).

    Returns {low, high, direction}, or None if no qualifying leg exists
    yet (e.g. the most recent swing high formed before the most recent
    swing low, for a BUY -- there's no completed up-leg to measure) or the
    leg has zero range.
    """
    if df is None or len(df) < lookback * 2 + 1 or direction not in ("BUY", "SELL"):
        return None
    swing_highs, swing_lows = find_swing_points(df, lookback)
    if not swing_highs or not swing_lows:
        return None

    highs_arr = df["high"].to_numpy()
    lows_arr = df["low"].to_numpy()

    if direction == "BUY":
        low_idx = swing_lows[-1]
        highs_after = [i for i in swing_highs if i > low_idx]
        if not highs_after:
            return None
        high_idx = highs_after[-1]
        low_p = float(lows_arr[low_idx])
        high_p = float(highs_arr[high_idx])
        if high_p <= low_p:
            return None
        leg = high_p - low_p
        zone_high = high_p - fib_low * leg
        zone_low = high_p - fib_high * leg
    else:
        high_idx = swing_highs[-1]
        lows_after = [i for i in swing_lows if i > high_idx]
        if not lows_after:
            return None
        low_idx = lows_after[-1]
        high_p = float(highs_arr[high_idx])
        low_p = float(lows_arr[low_idx])
        if high_p <= low_p:
            return None
        leg = high_p - low_p
        zone_low = low_p + fib_low * leg
        zone_high = low_p + fib_high * leg

    return {"low": zone_low, "high": zone_high, "direction": direction}


def in_ote_zone(price: float, ote: Optional[Dict]) -> bool:
    """True if `price` sits inside the OTE zone. None-safe (no zone yet ->
    False -- absence of a computable leg should never itself confirm an
    entry, only a real one should)."""
    if not ote:
        return False
    return ote["low"] <= price <= ote["high"]
