# -*- coding: utf-8 -*-
"""
=============================================================================
 NY MACRO WINDOWS -- time anchors for the standard-deviation framework
=============================================================================
midnight_sd.py answers "given a range, where are the levels?". This module
answers the other half: "which range, and when?".

The method is one piece of maths applied to four different anchors. What
changes between windows is only the leg the tool is stretched across:

    window        execute (NY)     SD anchored on
    ------------  ---------------  --------------------------------------
    MIDNIGHT      00:00-00:30      the 00:00-00:30 opening range itself
    MACRO_0830    08:30-08:45      the 08:30 news reaction candle (5m)
    NY_OPEN       09:30-09:45      the 08:30 news swing (08:30-09:30)
    TEN_AM        10:00-10:05      the 09:30-09:59 opening leg

THE BAND THAT REVERSES THE TRADE
--------------------------------
Getting this backwards is the expensive mistake, so it is encoded rather
than left to the caller:

    -1.0 .. -1.5   CONTINUATION  re-accumulation/distribution. Trade WITH
                                 the prevailing leg. This is not a reversal.
    -2.0 .. -2.5   REVERSAL      the common reaction band. Trade AGAINST.
    -4.0 .. -4.5   REVERSAL      deeper, rarer, higher conviction.

Same tool, same chart, opposite trade depending on which band price is in.

A NOTE ON -3.5
--------------
The written framework calls the extreme band "-3.5 to -4.0". The fib tool
it is drawn with has no 3.5 -- the ticked multiples are 4, 4.25, 4.5 (see
midnight_sd.PROJECTION_MULTIPLES, taken from the tool's own settings).
The band here follows the tool, because that is what is actually plotted
and what the levels were verified against. Worth resolving before this
drives anything.

SCOPE
-----
Pure functions: no MT5, no orders, no I/O. Same reason as midnight_sd --
four windows times four setup archetypes is a large amount of new, entirely
unmeasured surface area, and it should be backtested before it is traded.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from midnight_sd import (MAJOR_REVERSAL_ZONE, MINOR_REVERSAL_ZONE,
                         ny_window_utc, sd_levels)

# Re-accumulation band: NOT a reversal. Trade with the leg, not against it.
CONTINUATION_ZONE = (1.0, 1.5)

# execute = when a setup may be taken; anchor = the leg the SD tool spans.
WINDOWS: Dict[str, Dict[str, Tuple[Tuple[int, int], Tuple[int, int]]]] = {
    'MIDNIGHT':   {'execute': ((0, 0), (0, 30)),   'anchor': ((0, 0), (0, 30))},
    'MACRO_0830': {'execute': ((8, 30), (8, 45)),  'anchor': ((8, 30), (8, 35))},
    'NY_OPEN':    {'execute': ((9, 30), (9, 45)),  'anchor': ((8, 30), (9, 30))},
    'TEN_AM':     {'execute': ((10, 0), (10, 5)),  'anchor': ((9, 30), (9, 59))},
}

# "Algorithmic macro expansions are designed to move rapidly; stagnation
# means the algorithm is hunting a deeper structural level."
TIME_CUT_MINUTES = 20

# A close beyond the level with a body this thick is continuation, not
# rejection -- the framework's "you must see a wick rejection" rule.
THICK_BODY_FRACTION = 0.65
MIN_REJECTION_WICK_FRACTION = 0.25


def window_bounds(name: str, now_utc: datetime,
                  which: str = 'execute') -> Tuple[datetime, datetime]:
    """UTC bounds of a named window's execute or anchor span."""
    if name not in WINDOWS:
        raise KeyError(f"unknown macro window {name!r}; known: {sorted(WINDOWS)}")
    if which not in ('execute', 'anchor'):
        raise ValueError("which must be 'execute' or 'anchor'")
    start_hm, end_hm = WINDOWS[name][which]
    return ny_window_utc(now_utc, start_hm, end_hm)


def active_window(now_utc: Optional[datetime] = None) -> Optional[str]:
    """
    Which macro window is open right now, if any.

    Windows do not overlap, so the first match is the answer. Returns None
    outside all of them -- the framework is explicitly time-bound, and a
    setup found at 14:00 is not one of these setups.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    for name in WINDOWS:
        start, end = window_bounds(name, now_utc, 'execute')
        if start <= now_utc < end:
            return name
    return None


def anchor_range(name: str, bars, now_utc: Optional[datetime] = None
                 ) -> Optional[Tuple[float, float]]:
    """
    (high, low) of a window's anchor leg, from bars carrying a UTC 'time'
    column or DatetimeIndex.

    Returns None when the anchor span is not fully covered by the data. A
    partially-formed leg must never be projected: every level downstream
    would be wrong by however much of the leg was missing, and silently so.
    """
    if bars is None or len(bars) == 0:
        return None
    now_utc = now_utc or datetime.now(timezone.utc)
    start, end = window_bounds(name, now_utc, 'anchor')
    try:
        import pandas as pd
        cols = getattr(bars, 'columns', [])
        ts = pd.to_datetime(bars['time'] if 'time' in cols else bars.index, utc=True)
        mask = (ts >= start) & (ts < end)
        window = bars[mask.values if hasattr(mask, 'values') else mask]
        if len(window) == 0:
            return None
        return float(window['high'].max()), float(window['low'].min())
    except Exception:
        return None


def classify_zone(price: float, range_high: float, range_low: float
                  ) -> Optional[Dict[str, object]]:
    """
    Which band is price in, and what does that band argue for?

    Returns None outside every band, otherwise:
        {'zone': 'continuation'|'minor'|'major',
         'kind': 'CONTINUATION'|'REVERSAL',
         'side': 'above'|'below',
         'direction': 'BUY'|'SELL',
         'low': x, 'high': y}

    `direction` already accounts for the continuation/reversal flip: price
    extended ABOVE the range in the reversal band argues SELL, but in the
    continuation band argues BUY, because that band is where an uptrend
    re-accumulates rather than turns.

    Deepest band first: they do not overlap, but if a degenerate range ever
    made them, the deeper read should win.
    """
    span = abs(range_high - range_low)
    if span <= 0:
        return None
    hi, lo = max(range_high, range_low), min(range_high, range_low)

    bands = (('major', MAJOR_REVERSAL_ZONE, 'REVERSAL'),
             ('minor', MINOR_REVERSAL_ZONE, 'REVERSAL'),
             ('continuation', CONTINUATION_ZONE, 'CONTINUATION'))

    for zone, (a, b), kind in bands:
        up_lo, up_hi = hi + span * a, hi + span * b
        if up_lo <= price <= up_hi:
            return {'zone': zone, 'kind': kind, 'side': 'above',
                    'direction': 'SELL' if kind == 'REVERSAL' else 'BUY',
                    'low': up_lo, 'high': up_hi}
        dn_hi, dn_lo = lo - span * a, lo - span * b
        if dn_lo <= price <= dn_hi:
            return {'zone': zone, 'kind': kind, 'side': 'below',
                    'direction': 'BUY' if kind == 'REVERSAL' else 'SELL',
                    'low': dn_lo, 'high': dn_hi}
    return None


def five_minute_rule(o: float, h: float, l: float, c: float,
                     level: float, side: str) -> Tuple[bool, str]:
    """
    The 5-minute rule: at 08:35 / 09:35 / 10:05, a full thick-bodied candle
    closing beyond the -2.5 level is continuation, not exhaustion. Entry is
    only allowed on a wick rejection.

    `side` is where the extension ran: 'above' for an upward run (short
    setup), 'below' for a downward one.

    Returns (allowed, reason). Fails CLOSED on a degenerate candle -- a
    zero-range bar tells us nothing, and "no information" must not read as
    "permission".
    """
    rng = h - l
    if rng <= 0:
        return False, 'degenerate candle (zero range) -- no rejection evidence'

    body_fraction = abs(c - o) / rng
    if side == 'above':
        closed_beyond = c > level
        wick = h - max(o, c)
    elif side == 'below':
        closed_beyond = c < level
        wick = min(o, c) - l
    else:
        raise ValueError("side must be 'above' or 'below'")
    wick_fraction = wick / rng

    if not closed_beyond:
        return True, f'closed back inside the level (body {body_fraction:.0%} of range)'
    if body_fraction >= THICK_BODY_FRACTION:
        return False, (f'thick body ({body_fraction:.0%} of range) closed beyond the '
                       f'level -- continuation, not rejection')
    if wick_fraction >= MIN_REJECTION_WICK_FRACTION:
        return True, f'rejection wick {wick_fraction:.0%} of range beyond the level'
    return False, (f'closed beyond the level with only a {wick_fraction:.0%} wick '
                   f'-- no rejection')


def time_cut_expired(entry_epoch: float, now_epoch: float,
                     minutes: int = TIME_CUT_MINUTES) -> bool:
    """
    Has a macro entry overstayed its welcome?

    These expansions are meant to be fast. Past `minutes` without reaching
    target the edge is considered gone and the position should be cut or
    moved to break-even.
    """
    if entry_epoch is None or now_epoch is None:
        return False
    return (now_epoch - entry_epoch) >= minutes * 60
