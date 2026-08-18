# -*- coding: utf-8 -*-
"""
=============================================================================
 MIDNIGHT / DAYLIGHT OPENING STRATEGY
=============================================================================
Time-based SMC. Two clock times act as algorithmic reset points, and the
OPENING PRICE of the candle at each becomes the session's equilibrium:

    MIDNIGHT   18:00 New York   start of the new trading day
    DAYLIGHT   00:00 New York   calendar midnight, the intraday reference

NO STANDARD DEVIATION HERE
--------------------------
Worth stating plainly, because this codebase now contains two frameworks
that both descend from Shaakuni material and are easy to confuse:

    macro_windows.py / midnight_sd.py -> PROJECTION. Anchors an SD ladder
        on a range and asks "where will price exhaust?" (-2.0, -2.5, -4.0).
        Used for the 08:30 / 09:30 / 10:00 macro windows.

    this module -> SEQUENCE. No ladder, no projection, no targets computed
        from a range. It asks "has the trap sprung yet?" and walks a fixed
        order of events:

            fake momentum away from the open
              -> liquidity sweep
                -> market structure shift
                  -> retrace into FVG / extreme order block
                    -> entry

The open is a LINE, not a range. Its job is to say which side of fair value
price is on, so an entry can be taken at a genuine discount (below the line,
for longs) or premium (above it, for shorts).

THE NO-GO RULE
--------------
If price leaves the open by a large distance without ever trading through
the line, the algorithm skipped the manipulation phase and there is no trap
to fade. That day is not a setup. Encoded here rather than left to
judgement, because the whole edge is the trap -- without it this is just
chasing a breakout, which is exactly who the trap is built to catch.

SCOPE
-----
Pure functions. Nothing here places an order; the sequence detectors return
state so the caller (which already owns sweep/MSS/FVG/OB detection) can
decide. Same reason as the sibling modules: the bot already has a Shaakuni
SSM strategy doing sweep + extreme OB, and what it lacks is the opening-line
reference, not another entry engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from midnight_sd import ny_window_utc

# New York clock times for each session open.
#
# 18:00 is the start of the new trading day (CME futures session open), which
# is why it carries the "midnight" name despite being 6pm. Some feeds print
# the first candle of that session a few minutes late -- 18:04 is commonly
# quoted -- so the resolver takes the FIRST bar at or after the open time
# rather than demanding an exact timestamp match.
SESSION_OPEN_NY: Dict[str, Tuple[int, int]] = {
    'MIDNIGHT': (18, 0),
    'DAYLIGHT': (0, 0),
}

# How far past the open a bar may be and still count as "the opening candle".
OPEN_BAR_TOLERANCE_MINUTES = 10

# No-go threshold: expansion this far from the open without ever crossing it
# means the manipulation phase was skipped. Expressed in ATR so it travels
# across instruments -- 50-100 pips on gold is not 50-100 pips on EURUSD.
NO_GO_ATR_MULTIPLE = 2.0


def session_open_price(session: str, bars, now_utc: Optional[datetime] = None
                       ) -> Optional[Tuple[float, datetime]]:
    """
    (opening price, bar timestamp) for a session's opening candle.

    Takes the OPEN of the first bar at or after the session time, within
    OPEN_BAR_TOLERANCE_MINUTES. Returns None when no such bar exists -- the
    line must never be guessed from a nearby candle, because everything
    downstream (premium/discount, no-go, entry side) hangs off it.
    """
    if session not in SESSION_OPEN_NY:
        raise KeyError(f"unknown session {session!r}; known: {sorted(SESSION_OPEN_NY)}")
    if bars is None or len(bars) == 0:
        return None

    now_utc = now_utc or datetime.now(timezone.utc)
    hm = SESSION_OPEN_NY[session]
    start, _ = ny_window_utc(now_utc, hm, hm)

    try:
        import pandas as pd
        cols = getattr(bars, 'columns', [])
        ts = pd.to_datetime(bars['time'] if 'time' in cols else bars.index, utc=True)
        cutoff = start + pd.Timedelta(minutes=OPEN_BAR_TOLERANCE_MINUTES)
        mask = (ts >= start) & (ts <= cutoff)
        window = bars[mask.values if hasattr(mask, 'values') else mask]
        if len(window) == 0:
            return None
        first = window.iloc[0]
        stamp = ts[mask.values if hasattr(mask, 'values') else mask].iloc[0]
        return float(first['open']), stamp.to_pydatetime()
    except Exception:
        return None


def pricing_side(price: float, open_price: float, tolerance: float = 0.0) -> str:
    """
    'PREMIUM' above the open, 'DISCOUNT' below, 'EQUILIBRIUM' within
    `tolerance`.

    Smart money buys discount and sells premium, so this decides whether an
    entry is on the right side of fair value or is chasing.
    """
    if price > open_price + tolerance:
        return 'PREMIUM'
    if price < open_price - tolerance:
        return 'DISCOUNT'
    return 'EQUILIBRIUM'


def session_state(open_price: float, highs, lows, atr: float,
                  no_go_atr: float = NO_GO_ATR_MULTIPLE) -> Dict[str, object]:
    """
    What has price done relative to the open since the session started?

    `highs` / `lows` are the bars since the open, in order.

    Returns:
        crossed_above / crossed_below : did price trade each side of the line
        crossed_both                  : the manipulation phase happened
        max_excursion                 : furthest distance from the line
        no_go                         : expanded far away and never crossed
        fake_side                     : which side the initial push went
        fake_side_undetermined        : first bar straddled the open
        expected_direction            : the trade the trap argues for

    `no_go` is the rule that keeps this from becoming breakout-chasing: a
    large one-way expansion with no cross means there was no trap to fade.
    """
    hs, ls = list(highs), list(lows)
    if not hs or not ls or atr <= 0:
        return {'crossed_above': False, 'crossed_below': False,
                'crossed_both': False, 'max_excursion': 0.0,
                'no_go': False, 'fake_side': None,
                'fake_side_undetermined': False, 'expected_direction': None}

    crossed_above = any(h > open_price for h in hs)
    crossed_below = any(l < open_price for l in ls)
    max_up = max(hs) - open_price
    max_dn = open_price - min(ls)
    max_excursion = max(max_up, max_dn, 0.0)

    # Which way did it push first? That is the fake move; the trade fades it.
    #
    # A bar whose HIGH is above the open and whose LOW is below it straddles
    # the line, and OHLC cannot say which side came first -- that needs ticks.
    # Guessing here would be actively harmful: pick wrong and the strategy
    # fades the real move and joins the fake one, which is the precise
    # opposite of its purpose. So an ambiguous first touch is reported as
    # undetermined and the caller refuses the trade.
    fake_side = None
    undetermined = False
    for h, l in zip(hs, ls):
        above, below = h > open_price, l < open_price
        if above and below:
            undetermined = True; break
        if above:
            fake_side = 'above'; break
        if below:
            fake_side = 'below'; break

    crossed_both = crossed_above and crossed_below
    no_go = (not crossed_both) and max_excursion >= atr * no_go_atr

    expected = None
    if fake_side == 'above':
        expected = 'SELL'      # pushed up into premium -> fade it down
    elif fake_side == 'below':
        expected = 'BUY'

    return {'crossed_above': crossed_above, 'crossed_below': crossed_below,
            'crossed_both': crossed_both, 'max_excursion': float(max_excursion),
            'no_go': bool(no_go), 'fake_side': fake_side,
            'fake_side_undetermined': bool(undetermined),
            'expected_direction': expected}


def entry_allowed(direction: str, entry_price: float, open_price: float,
                  state: Dict[str, object]) -> Tuple[bool, str]:
    """
    Does this entry satisfy the opening-strategy rules?

    Requires, in order:
      1. not a no-go session (a trap must have formed)
      2. the trade fades the fake push rather than joining it
      3. the entry sits on the correct side of the line -- longs at a
         discount, shorts at a premium

    (3) is the one worth being strict about. Entering a long ABOVE the open
    is buying premium, which is the retail side of exactly the trap this
    strategy exists to exploit.

    Returns (allowed, reason) so the caller can journal the refusal.
    """
    if state.get('fake_side_undetermined'):
        return False, ('which side the fake push went is undetermined -- the first '
                       'bar straddled the open, and OHLC cannot resolve the order '
                       'without ticks')

    if state.get('no_go'):
        return False, ('no-go session: price expanded away from the open without '
                       'ever crossing it -- manipulation phase skipped, no trap to fade')

    expected = state.get('expected_direction')
    if expected and direction != expected:
        return False, (f'trade joins the fake push instead of fading it '
                       f'(fake went {state.get("fake_side")}, so the setup is {expected})')

    side = pricing_side(entry_price, open_price)
    if direction == 'BUY' and side == 'PREMIUM':
        return False, 'long entry sits in premium (above the open) -- not a discount buy'
    if direction == 'SELL' and side == 'DISCOUNT':
        return False, 'short entry sits in discount (below the open) -- not a premium sell'

    return True, f'{direction} at {side.lower()} relative to the session open'
