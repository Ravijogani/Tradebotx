# -*- coding: utf-8 -*-
"""
=============================================================================
 MIDNIGHT OPENING RANGE -- STANDARD DEVIATION PROJECTIONS
=============================================================================
The Swappy / ICT standard-deviation method, anchored where it is actually
meant to be anchored: the midnight opening range, 00:00-00:30 New York time.

WHY THIS EXISTS
---------------
hybrid_trading_bot_multiuser.py already computes the right LEVEL SET --
0, 0.25, 0.5, 0.7, 1, -1, -1.5, -2, -2.25, -2.5, -4, -4.25, -4.5 -- but
projects it from `df.iloc[-13:-3]`, a rolling window of 10 M15 bars ending
three bars ago. That anchor moves with every candle, so its "-2 SD" is a
different price every bar and bears no relation to the levels a trader
plotting the midnight range is watching.

The method depends on the anchor being FIXED for the session. Manipulation
is measured against where the day opened, not against a sliding window.

TERMINOLOGY (matches the levels a trader plots by hand)
------------------------------------------------------
    minor reversal zone : -2.0 .. -2.5 SD    the common reaction band
    major reversal zone : -4.0 .. -4.5 SD    deeper, rarer, higher conviction

Both project in BOTH directions from the same range -- upward from the range
high, downward from the range low -- because manipulation can run either
way before the real move. On a chart that is two fib tools sharing one range,
which is exactly how it is drawn by hand.

SCOPE / HONESTY
---------------
This module computes levels and answers "is price in a reversal zone". It
deliberately does NOT place trades. Whether the midnight anchor beats the
existing rolling anchor is an empirical question that needs measuring over
many sessions, not one good afternoon -- so this is built pure and
importable precisely so the backtest can answer that before anything is
wired to an order.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

# The multiples a trader actually ticks on the fib tool. Anything not in this
# list is deliberately absent -- 1.272, 2.272, 3.414 and friends are left
# unchecked in the tool and must not appear here either.
INSIDE_MULTIPLES = (0.0, 0.25, 0.5, 0.7, 1.0)
PROJECTION_MULTIPLES = (1.0, 1.5, 2.0, 2.25, 2.5, 4.0, 4.25, 4.5)

MINOR_REVERSAL_ZONE = (2.0, 2.5)
MAJOR_REVERSAL_ZONE = (4.0, 4.5)

OPENING_RANGE_START_NY = (0, 0)    # 00:00 New York
OPENING_RANGE_END_NY = (0, 30)     # 00:30 New York


def ny_utc_offset_hours(when: datetime) -> int:
    """
    Hours to ADD to New York time to get UTC: 4 during EDT, 5 during EST.

    US DST: starts 2nd Sunday of March, ends 1st Sunday of November. Computed
    rather than imported so this module has no tz-database dependency, which
    matters because it runs on a Windows VPS and inside the backtest harness.
    """
    year = when.year
    mar1 = datetime(year, 3, 1, tzinfo=timezone.utc)
    dst_start = mar1 + timedelta(days=(6 - mar1.weekday()) % 7 + 7)
    nov1 = datetime(year, 11, 1, tzinfo=timezone.utc)
    dst_end = nov1 + timedelta(days=(6 - nov1.weekday()) % 7)
    return 4 if dst_start.date() <= when.date() < dst_end.date() else 5


def ny_window_utc(now_utc: datetime,
                  start_hm: Tuple[int, int],
                  end_hm: Tuple[int, int]) -> Tuple[datetime, datetime]:
    """
    The UTC bounds of an arbitrary New York time-of-day window, for the
    session containing `now_utc`.

    Generalised from midnight_range_window so every macro window (08:30,
    09:30, 10:00 ...) resolves through one DST-aware implementation rather
    than each growing its own copy.

    Always returns a window at or before `now_utc`: if today's has not
    happened yet, the previous day's is returned. A window in the future
    would be projected from bars that do not exist.
    """
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    offset = ny_utc_offset_hours(now_utc)
    ny_now = now_utc - timedelta(hours=offset)

    start_ny = ny_now.replace(hour=start_hm[0], minute=start_hm[1],
                              second=0, microsecond=0)
    if ny_now < start_ny:
        start_ny -= timedelta(days=1)
    end_ny = start_ny.replace(hour=end_hm[0], minute=end_hm[1])
    if end_ny <= start_ny:                     # window crosses NY midnight
        end_ny += timedelta(days=1)
    return start_ny + timedelta(hours=offset), end_ny + timedelta(hours=offset)


def midnight_range_window(now_utc: datetime) -> Tuple[datetime, datetime]:
    """
    The UTC start/end of the 00:00-00:30 NY window for the session containing
    `now_utc`.

    "The session containing now" matters: at 03:00 NY the relevant window is
    earlier the same NY day, but at 22:00 NY it is the window that has not
    happened yet, so the correct answer is the PREVIOUS one -- the levels a
    trader is still watching. Returning a future window would silently
    produce levels from bars that do not exist.
    """
    return ny_window_utc(now_utc, OPENING_RANGE_START_NY, OPENING_RANGE_END_NY)


def opening_range_from_bars(bars, now_utc: Optional[datetime] = None
                            ) -> Optional[Tuple[float, float]]:
    """
    (high, low) of the midnight opening range from a DataFrame of bars.

    `bars` needs a UTC 'time' column (or DatetimeIndex) plus 'high'/'low'.
    Returns None when the window isn't covered by the data -- an incomplete
    range must never be silently projected, because every level downstream
    would be wrong by however much of the window was missing.
    """
    if bars is None or len(bars) == 0:
        return None
    now_utc = now_utc or datetime.now(timezone.utc)
    start, end = midnight_range_window(now_utc)

    try:
        import pandas as pd  # local: keeps this module importable without pandas
        if 'time' in getattr(bars, 'columns', []):
            ts = pd.to_datetime(bars['time'], utc=True)
        else:
            ts = pd.to_datetime(bars.index, utc=True)
        mask = (ts >= start) & (ts < end)
        window = bars[mask.values if hasattr(mask, 'values') else mask]
        if len(window) == 0:
            return None
        return float(window['high'].max()), float(window['low'].min())
    except Exception:
        return None


def sd_levels(range_high: float, range_low: float) -> Dict[str, float]:
    """
    Every level, keyed as it is read off the chart.

      'in_0' .. 'in_1'   inside the range (0 at the high, 1 at the low)
      'up_2'   etc.      projected ABOVE the range high
      'down_2' etc.      projected BELOW the range low

    Verified against a hand-plotted XAUUSD session: range 4393.756/4389.911
    gives up_2 = 4401.447 and up_2.5 = 4403.370, matching the chart to the
    third decimal.
    """
    span = abs(range_high - range_low)
    if span <= 0:
        return {}
    hi, lo = max(range_high, range_low), min(range_high, range_low)

    levels: Dict[str, float] = {}
    for m in INSIDE_MULTIPLES:
        levels[f'in_{m:g}'] = hi - span * m
    for m in PROJECTION_MULTIPLES:
        levels[f'up_{m:g}'] = hi + span * m
        levels[f'down_{m:g}'] = lo - span * m
    return levels


def reversal_zone(price: float, range_high: float, range_low: float
                  ) -> Optional[Dict[str, object]]:
    """
    Is `price` sitting in a reversal zone, and which one?

    Returns None when it isn't. Otherwise:
        {'zone': 'minor'|'major', 'side': 'above'|'below',
         'expected_direction': 'SELL'|'BUY', 'low': x, 'high': y}

    `expected_direction` is the trade the zone argues for -- price extended
    ABOVE the range into a reversal band argues for a SELL, and vice versa.
    Major is checked first: the bands never overlap, but if the range is ever
    degenerate enough that they did, the deeper read should win.
    """
    span = abs(range_high - range_low)
    if span <= 0:
        return None
    hi, lo = max(range_high, range_low), min(range_high, range_low)

    for name, (a, b) in (('major', MAJOR_REVERSAL_ZONE), ('minor', MINOR_REVERSAL_ZONE)):
        up_lo, up_hi = hi + span * a, hi + span * b
        if up_lo <= price <= up_hi:
            return {'zone': name, 'side': 'above', 'expected_direction': 'SELL',
                    'low': up_lo, 'high': up_hi}
        dn_hi, dn_lo = lo - span * a, lo - span * b
        if dn_lo <= price <= dn_hi:
            return {'zone': name, 'side': 'below', 'expected_direction': 'BUY',
                    'low': dn_lo, 'high': dn_hi}
    return None
