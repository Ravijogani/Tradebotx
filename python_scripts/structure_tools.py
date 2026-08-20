"""
structure_tools.py -- SHARED STRUCTURE / LIQUIDITY ENGINE
=========================================================

One implementation of "where does a professional trader actually put the
stop, the target, and the trail", imported by all three live bots
(hybrid_trading_bot_multiuser.py, intraday.py, structural_swing_pro.py)
so the three cannot drift apart the way the SL/TP logic already had.

WHY THIS EXISTS
---------------
Before this module the three bots managed open trades on FIXED R-multiples:

  * breakeven the instant r_multiple >= 1.0R, measured tick-by-tick,
  * then trail a straight PERCENTAGE of the open gain (50% / 70% / 85%)
    or a straight R-distance from the current price.

Both are pullback-blind. A normal, healthy retracement -- the 38-62%
pullback that follows practically every impulse leg, and the retest of a
broken level that a continuation setup is *built around* -- routinely
travels back through "entry + a couple of pips" and through "70% of the
open gain". The bot was therefore stopping itself out at BE (or at a
trail level sitting inside the noise band) on exactly the pullbacks its
own entry models are designed to hold through, and the trade would then
run to target without it.

WHAT A DISCRETIONARY TRADER DOES INSTEAD
----------------------------------------
The stop lives BEHIND STRUCTURE, never at a round R-number:

  1. Nothing is touched until the market has PROVED the move: a CLOSED
     bar beyond the level, not a wick, not an intra-bar tick.
  2. The stop goes behind the last CONFIRMED swing point (the higher low
     in an uptrend / lower high in a downtrend) plus a volatility buffer
     -- because that swing is the price that would actually invalidate
     the leg. If it hasn't formed yet, the stop does not move at all.
  3. The stop is never parked closer to price than the market's own
     noise amplitude (a function of ATR and the live spread). A stop
     inside the noise band is not protection, it is a guaranteed exit.
  4. The stop only ever advances, and only in the trade's direction.

Targets are LIQUIDITY, not arithmetic: resting stop clusters at equal
highs/lows and prior swing pivots, because that is where the fills are.

Everything here is a pure function of an OHLC DataFrame -- no MT5 calls,
no globals -- so the live bots and backtest/ harness get identical
behaviour, and every entry point is wrapped defensively by its caller.
"""

from typing import Dict, List, Optional, Tuple

try:
    import pandas as pd  # noqa: F401  (typing / duck-typed use only)
except Exception:  # pragma: no cover
    pd = None


# =============================================================================
# NOISE BAND -- the single most important number in this file
# =============================================================================

def noise_band(atr: float, spread: float, atr_mult: float = 0.75,
               spread_mult: float = 3.0) -> float:
    """
    The minimum distance a stop must keep from current price.

    A pullback is not a reversal. `atr_mult * ATR` is the ordinary
    breathing room of the instrument on the timeframe the ATR came from;
    `spread_mult * spread` covers broker widening at session opens and
    news. Whichever is larger wins -- on a tight-spread majors session
    ATR dominates, on gold/crypto or at rollover the spread term does.

    0.75 ATR is deliberate: below ~0.5 ATR a stop is inside the routine
    bar-to-bar range and gets tagged by noise; above ~1.5 ATR the trail
    stops protecting anything.
    """
    atr = abs(float(atr or 0.0))
    spread = abs(float(spread or 0.0))
    return max(atr * atr_mult, spread * spread_mult, 0.0)


def structure_buffer(atr: float, spread: float, atr_mult: float = 0.25,
                     spread_mult: float = 2.0) -> float:
    """
    How far BEYOND a swing point to place the stop.

    Stops resting exactly on the swing low are the liquidity that
    stop-hunts are aimed at. This pushes the stop past that pool by a
    volatility- and spread-aware margin.
    """
    atr = abs(float(atr or 0.0))
    spread = abs(float(spread or 0.0))
    return max(atr * atr_mult, spread * spread_mult, 0.0)


# =============================================================================
# SWING / PIVOT DETECTION
# =============================================================================

def find_pivots(df, pivot_n: int = 2, lookback: int = 120,
                exclude_forming: bool = True) -> Tuple[List[float], List[float]]:
    """
    Return (swing_lows, swing_highs) as price lists, OLDEST -> NEWEST.

    A pivot needs `pivot_n` bars lower/higher on BOTH sides, which means
    the most recent `pivot_n` bars can never qualify -- that is the point:
    a swing is only real once the market has traded away from it and
    confirmed it. This is what stops the trail from chasing a wick that
    is still forming.

    pivot_n=2 (not 3) for management: a 3-bar pivot on M5 needs 6 bars
    (30 minutes) of confirmation, which is too slow to protect a scalp.
    Entry-side target detection uses the stricter 3.
    """
    lows: List[float] = []
    highs: List[float] = []
    if df is None or len(df) < (pivot_n * 2 + 3):
        return lows, highs
    try:
        data = df.iloc[-lookback:] if lookback else df
        if exclude_forming and len(data) > 1:
            data = data.iloc[:-1]        # last bar is still forming
        data = data.reset_index(drop=True)
        n = len(data)
        lo = data['low'].astype(float).values
        hi = data['high'].astype(float).values
        for i in range(pivot_n, n - pivot_n):
            if all(lo[i] <= lo[i - j] for j in range(1, pivot_n + 1)) and \
               all(lo[i] <= lo[i + j] for j in range(1, pivot_n + 1)):
                lows.append(float(lo[i]))
            if all(hi[i] >= hi[i - j] for j in range(1, pivot_n + 1)) and \
               all(hi[i] >= hi[i + j] for j in range(1, pivot_n + 1)):
                highs.append(float(hi[i]))
    except Exception:
        return [], []
    return lows, highs


def last_protective_swing(df, direction: str, reference_price: float,
                          pivot_n: int = 2, lookback: int = 120) -> Optional[float]:
    """
    The most recent CONFIRMED swing that sits on the protective side of
    `reference_price`: the newest higher-low below price for a BUY, the
    newest lower-high above price for a SELL.

    This is the level the trade is actually leaning on. Returns None when
    no such swing has formed yet -- and "no swing yet" must mean "do not
    move the stop", never "fall back to a percentage".
    """
    lows, highs = find_pivots(df, pivot_n=pivot_n, lookback=lookback)
    try:
        ref = float(reference_price)
        if direction.upper() == 'BUY':
            below = [p for p in lows if p < ref]
            return below[-1] if below else None
        above = [p for p in highs if p > ref]
        return above[-1] if above else None
    except Exception:
        return None


def swing_structure_intact(df, direction: str, pivot_n: int = 2,
                           lookback: int = 120) -> bool:
    """
    Is the leg still making higher lows (BUY) / lower highs (SELL)?

    Used as a HOLD condition: while structure is intact a deep retrace is
    a pullback, and the exit engines should not be closing the trade on a
    momentum reading alone. Two swings are the minimum needed to have a
    direction at all; with fewer, assume intact (nothing disproves it).
    """
    lows, highs = find_pivots(df, pivot_n=pivot_n, lookback=lookback)
    try:
        if direction.upper() == 'BUY':
            return len(lows) < 2 or lows[-1] >= lows[-2]
        return len(highs) < 2 or highs[-1] <= highs[-2]
    except Exception:
        return True


def is_normal_pullback(df, direction: str, entry_price: float, current_price: float,
                       atr: float, pivot_n: int = 2, lookback: int = 120,
                       max_retrace: float = 0.786) -> bool:
    """
    True when price pulling back against us is still a NORMAL retracement
    of the current leg rather than a structural failure.

    Measured as a Fibonacci retracement of the leg from the last
    protective swing to the leg's extreme: anything up to the 78.6% of
    that leg, WITH the last swing still unbroken, is ordinary. Beyond
    78.6% (or through the swing) the leg's premise is gone and the trade
    is no longer in a pullback -- it is in trouble.
    """
    try:
        if not swing_structure_intact(df, direction, pivot_n, lookback):
            return False
        swing = last_protective_swing(df, direction, current_price, pivot_n, lookback)
        if swing is None:
            # No protective swing has TWO very different causes and they need
            # opposite answers:
            #
            #   (a) no confirmed swings exist yet -- a fresh trade, or a frame
            #       too short. Nothing disproves the pullback, so assume normal.
            #   (b) swings exist but price has traded below EVERY one of them
            #       (above every one, for a short). That is not a pullback, it
            #       is a complete structural collapse.
            #
            # Both used to land on `return True`, so the exit veto was at its
            # strongest exactly when the trade had failed most completely: a
            # long entered at 100 sitting at 50 reported "structure intact --
            # holding through it", because there was no swing left below price
            # to lean on.
            lows, highs = find_pivots(df, pivot_n=pivot_n, lookback=lookback)
            if (lows if direction.upper() == 'BUY' else highs):
                return False
            return True
        data = df.iloc[-lookback:]
        if direction.upper() == 'BUY':
            leg_high = float(data['high'].max())
            leg = leg_high - swing
            if leg <= 0:
                return True
            if current_price <= swing:
                return False
            return (leg_high - current_price) / leg <= max_retrace
        leg_low = float(data['low'].min())
        leg = swing - leg_low
        if leg <= 0:
            return True
        if current_price >= swing:
            return False
        return (current_price - leg_low) / leg <= max_retrace
    except Exception:
        return True


# =============================================================================
# CLOSED-BAR CONFIRMATION
# =============================================================================

def closed_bar_beyond(df, direction: str, level: float) -> bool:
    """
    Has a CLOSED bar closed beyond `level` in the trade's direction?

    Every management action in this module is gated on this. Tick-based
    triggers fire on the spike that a pullback immediately retraces --
    which is precisely how a 1.0R breakeven turns a winner into a
    scratch. The last row of a live DataFrame is the forming bar, so it
    is excluded.
    """
    try:
        if df is None or len(df) < 2:
            return False
        closed = df.iloc[:-1]
        last_close = float(closed['close'].iloc[-1])
        return last_close > level if direction.upper() == 'BUY' else last_close < level
    except Exception:
        return False


# =============================================================================
# BREAKEVEN -- STRUCTURAL, NOT ARITHMETIC
# =============================================================================

def breakeven_plan(df, direction: str, entry_price: float, initial_sl: float,
                   current_price: float, current_sl: float, atr: float, spread: float,
                   trigger_r: float = 1.0, pivot_n: int = 2, lookback: int = 120,
                   confirm_extra_r: float = 0.3, digits: int = 5) -> Optional[Dict]:
    """
    Decide IF and WHERE to take a trade off risk.

    Returns {'sl', 'reason', 'r'} or None (meaning: leave the stop alone).

    THREE WAYS THIS FIRES, in order of quality:

      A. STRUCTURAL (preferred) -- price is >= trigger_r AND a confirmed
         higher low (BUY) / lower high (SELL) has formed on the
         profitable side of entry. The stop goes behind THAT swing, which
         is both risk-free and a real invalidation level. This is what a
         trader means by "move it up behind the structure".

      B. CONFIRMED IMPULSE -- no protective swing has formed yet, but a
         bar has CLOSED beyond trigger_r AND price has extended a further
         `confirm_extra_r` (default +0.3R). The extra cushion is what
         stops the classic failure: BE placed at exactly +1.0R, price
         retraces the impulse it just made, trade scratches, target hit
         without us. The stop goes to entry + a noise buffer.

      C. Nothing else. Below trigger, or on an unconfirmed tick spike,
         the ORIGINAL structural stop stays where the setup put it.

    The returned stop is additionally rejected if it would sit inside the
    noise band of current price -- a "protective" stop that price is
    already brushing is just a market order with extra steps.
    """
    try:
        risk = abs(float(entry_price) - float(initial_sl))
        if risk <= 0:
            return None
        is_buy = direction.upper() == 'BUY'
        gain = (current_price - entry_price) if is_buy else (entry_price - current_price)
        r_mult = gain / risk
        if r_mult < trigger_r:
            return None

        buf = structure_buffer(atr, spread)
        band = noise_band(atr, spread)
        trigger_level = entry_price + risk * trigger_r if is_buy else entry_price - risk * trigger_r

        candidate = None
        reason = ''

        # --- A: behind confirmed structure, only if that structure is
        #        already risk-free (at/beyond entry). A swing BELOW entry
        #        is a fine trail level later but it is not breakeven.
        swing = last_protective_swing(df, direction, current_price, pivot_n, lookback)
        if swing is not None:
            level = (swing - buf) if is_buy else (swing + buf)
            if (is_buy and level >= entry_price) or ((not is_buy) and level <= entry_price):
                candidate = level
                reason = (f'confirmed {"higher low" if is_buy else "lower high"} at '
                          f'{swing:.{digits}f} formed above entry -- stop moved behind '
                          f'structure, not to a round R-number')

        # --- B: confirmed impulse with a cushion, no structure yet
        if candidate is None:
            if closed_bar_beyond(df, direction, trigger_level) and \
               r_mult >= (trigger_r + confirm_extra_r):
                candidate = (entry_price + buf) if is_buy else (entry_price - buf)
                reason = (f'closed bar beyond {trigger_r:.1f}R and price extended to '
                          f'{r_mult:.2f}R with no swing formed yet -- risk removed at entry+buffer')
            else:
                # C: the move is unconfirmed. Holding the original stop is
                # the correct action, not a compromise.
                return None

        # Never park the stop inside the noise band...
        if is_buy and candidate > (current_price - band):
            candidate = current_price - band
        if (not is_buy) and candidate < (current_price + band):
            candidate = current_price + band
        # ...and if that pushed it back below entry, this is simply too
        # early to be risk-free. Wait.
        if (is_buy and candidate < entry_price) or ((not is_buy) and candidate > entry_price):
            return None
        # Only ever an improvement.
        if current_sl and ((is_buy and candidate <= current_sl) or
                           ((not is_buy) and candidate >= current_sl)):
            return None

        return {'sl': round(float(candidate), digits), 'reason': reason, 'r': round(r_mult, 2)}
    except Exception:
        return None


# =============================================================================
# TRAILING -- BEHIND SWINGS, WITH A FLOOR
# =============================================================================

def structural_trail(df, direction: str, entry_price: float, initial_sl: float,
                     current_price: float, current_sl: float, atr: float, spread: float,
                     pivot_n: int = 2, lookback: int = 120,
                     min_lock_r: float = 0.0, digits: int = 5) -> Optional[Dict]:
    """
    Trail the stop behind the newest CONFIRMED swing, never at a fixed
    percentage of the open gain.

    Returns {'sl', 'reason', 'swing'} or None (leave the stop alone).

    Why swing-based beats percentage-based: locking "70% of the current
    gain" puts the stop at a price the market has no reason to respect,
    typically right in the middle of the last impulse leg -- the first
    ordinary retrace takes it. The swing low that price just left behind
    is a level other participants are also defending; price going through
    it is genuine information that the leg is over.

    `min_lock_r` is a one-way ratchet for late-stage trades (e.g. hold at
    least +1R once 3R has been seen) -- it can only ever TIGHTEN the
    swing level, never loosen it, and it too respects the noise band.
    """
    try:
        risk = abs(float(entry_price) - float(initial_sl))
        if risk <= 0:
            return None
        is_buy = direction.upper() == 'BUY'
        buf = structure_buffer(atr, spread)
        band = noise_band(atr, spread)

        swing = last_protective_swing(df, direction, current_price, pivot_n, lookback)
        candidate = None
        reason = ''
        if swing is not None:
            level = (swing - buf) if is_buy else (swing + buf)
            # A swing that is already inside the noise band of price is a
            # stop waiting to be tagged -- skip this cycle, the next
            # confirmed swing will be further away.
            if (is_buy and level <= current_price - band) or \
               ((not is_buy) and level >= current_price + band):
                candidate = level
                reason = (f'trailing behind confirmed '
                          f'{"higher low" if is_buy else "lower high"} at {swing:.{digits}f}')

        if min_lock_r and min_lock_r > 0:
            floor = (entry_price + risk * min_lock_r) if is_buy else (entry_price - risk * min_lock_r)
            in_band = (floor > current_price - band) if is_buy else (floor < current_price + band)
            if not in_band:
                if candidate is None or (is_buy and floor > candidate) or \
                   ((not is_buy) and floor < candidate):
                    candidate = floor
                    reason = f'ratchet: holding a minimum of {min_lock_r:.1f}R locked'

        if candidate is None:
            return None
        if current_sl and ((is_buy and candidate <= current_sl) or
                           ((not is_buy) and candidate >= current_sl)):
            return None
        if (is_buy and candidate >= current_price) or ((not is_buy) and candidate <= current_price):
            return None

        return {'sl': round(float(candidate), digits), 'reason': reason,
                'swing': round(float(swing), digits) if swing is not None else None}
    except Exception:
        return None


# =============================================================================
# LIQUIDITY TARGETS
# =============================================================================

def equal_level_clusters(df, direction: str, reference_price: float, atr: float,
                         lookback: int = 200, tol_atr: float = 0.12,
                         min_touches: int = 2) -> List[float]:
    """
    Equal highs / equal lows ahead of price -- the resting stop pools
    that price is genuinely drawn toward. Two or more highs within
    ~0.12 ATR of each other is the standard "equal highs" read.

    Returned NEAREST FIRST: the first pool in front of price is the one
    that realistically gets tagged; the far one is a bonus, not a plan.
    """
    out: List[float] = []
    try:
        if df is None or len(df) < 10:
            return out
        data = df.iloc[-lookback:]
        tol = max(abs(float(atr or 0.0)) * tol_atr, 1e-9)
        is_buy = direction.upper() == 'BUY'
        src = data['high'].astype(float).values if is_buy else data['low'].astype(float).values
        ahead = [p for p in src if (p > reference_price if is_buy else p < reference_price)]
        clusters: List[List[float]] = []
        for p in sorted(ahead):
            if clusters and abs(p - clusters[-1][-1]) <= tol:
                clusters[-1].append(p)
            else:
                clusters.append([p])
        levels = [sum(c) / len(c) for c in clusters if len(c) >= min_touches]
        out = sorted(levels) if is_buy else sorted(levels, reverse=True)
    except Exception:
        return []
    return out


def liquidity_targets(df, direction: str, entry_price: float, sl_dist: float,
                      atr: float, min_rr: float = 1.5, pivot_n: int = 3,
                      lookback: int = 200, digits: int = 5) -> Dict:
    """
    TP1 / TP2 from real levels: equal-high/low stop pools first, prior
    swing pivots second.

    TP1 = the NEAREST level ahead of entry that still clears `min_rr`.
    Aiming past a pool that price has to fight through is how a +2R trade
    becomes a scratch -- take the first honest one.

    TP2 = the next level beyond TP1, used as the runner target once the
    trail has taken over the job of protecting the position.

    Returns {'tp1', 'tp2', 'rr1', 'source'}; zeros when the structure
    offers nothing that qualifies, which the caller should treat as "this
    setup has no real target" rather than inventing one.
    """
    res = {'tp1': 0.0, 'tp2': 0.0, 'rr1': 0.0, 'source': 'NONE'}
    try:
        if sl_dist <= 0:
            return res
        is_buy = direction.upper() == 'BUY'
        pools = equal_level_clusters(df, direction, entry_price, atr, lookback=lookback)
        lows, highs = find_pivots(df, pivot_n=pivot_n, lookback=lookback)
        pivots = [p for p in (highs if is_buy else lows)
                  if (p > entry_price if is_buy else p < entry_price)]
        pivots = sorted(pivots) if is_buy else sorted(pivots, reverse=True)

        for label, levels in (('LIQUIDITY_POOL', pools), ('SWING_PIVOT', pivots)):
            qualified = [p for p in levels
                         if (abs(p - entry_price) / sl_dist) >= min_rr]
            if not qualified:
                continue
            tp1 = qualified[0]
            tp2 = qualified[1] if len(qualified) > 1 else 0.0
            res.update({'tp1': round(float(tp1), digits),
                        'tp2': round(float(tp2), digits) if tp2 else 0.0,
                        'rr1': round(abs(tp1 - entry_price) / sl_dist, 2),
                        'source': label})
            return res
    except Exception:
        return res
    return res


# =============================================================================
# EXIT VETO
# =============================================================================

def should_hold_through_pullback(df, direction: str, entry_price: float,
                                 current_price: float, atr: float,
                                 pivot_n: int = 2, lookback: int = 120) -> Tuple[bool, str]:
    """
    Veto used by the bots' momentum/edge exit engines.

    Those engines read momentum, and momentum is NEGATIVE by definition
    during a pullback -- which is exactly when a continuation trade
    should be held, not closed. If structure is still intact and the
    retrace is within the normal band, the answer is hold; the trade's
    own structural stop is the thing entitled to end it.

    Returns (hold, reason).
    """
    try:
        if not swing_structure_intact(df, direction, pivot_n, lookback):
            return False, 'market structure broke (swing sequence failed) -- not a pullback'
        if is_normal_pullback(df, direction, entry_price, current_price, atr,
                              pivot_n, lookback):
            return True, 'normal retracement with structure intact -- holding through it'
        return False, 'retrace exceeded the normal band for this leg'
    except Exception:
        return False, 'structure check unavailable'
