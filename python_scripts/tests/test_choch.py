import pathlib as _pl
_SCRIPTS = _pl.Path(__file__).resolve().parent.parent  # python_scripts/
import sys, os
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_SCRIPTS / "backtest"))
from backtest.bot_loader import import_bot_module
bot = import_bot_module()

import pandas as pd, numpy as np

def make_zigzag(prices, bars_per_leg=8):
    rows = []
    t0 = pd.Timestamp("2026-01-01", tz="UTC")
    idx = 0
    for i in range(len(prices) - 1):
        p0, p1 = prices[i], prices[i+1]
        for b in range(bars_per_leg):
            frac0 = b / bars_per_leg
            frac1 = (b + 1) / bars_per_leg
            o = p0 + (p1 - p0) * frac0
            c = p0 + (p1 - p0) * frac1
            hi = max(o, c) + abs(p1 - p0) * 0.02
            lo = min(o, c) - abs(p1 - p0) * 0.02
            rows.append({"time": t0 + pd.Timedelta(minutes=30 * idx), "open": o, "high": hi,
                         "low": lo, "close": c, "tick_volume": 100})
            idx += 1
    return pd.DataFrame(rows)

# TEST 1: clean bullish structure (HH+HL), then a genuine CHoCH -- price
# breaks below the last swing low.
df1 = make_zigzag([100, 90, 110, 95, 120, 100, 130, 60])  # last leg: sharp break well below prior low (95)
r1 = bot.classify_m30_character(df1)
print("TEST 1 (bullish structure -> CHoCH break down):", r1)
assert r1['established_trend'] == 'BULLISH', r1
assert r1['signal'] == 'CHOCH', r1
assert r1['break_direction'] == 'BEARISH', r1

# TEST 2: clean bullish structure (HH+HL), continuation break above last high (130)
df2 = make_zigzag([100, 90, 110, 95, 120, 100, 130, 110, 150])
r2 = bot.classify_m30_character(df2)
print("TEST 2 (bullish structure -> BOS break up):", r2)
assert r2['established_trend'] == 'BULLISH', r2
assert r2['signal'] == 'BOS', r2
assert r2['break_direction'] == 'BULLISH', r2

# TEST 3: clean bearish structure (LH+LL), then a genuine CHoCH -- price
# breaks above the last swing high.
df3 = make_zigzag([100, 110, 90, 105, 80, 100, 70, 140])
r3 = bot.classify_m30_character(df3)
print("TEST 3 (bearish structure -> CHoCH break up):", r3)
assert r3['established_trend'] == 'BEARISH', r3
assert r3['signal'] == 'CHOCH', r3
assert r3['break_direction'] == 'BULLISH', r3

# TEST 4: too little data / no swings -> NONE, no crash
df4 = make_zigzag([100, 101], bars_per_leg=3)
r4 = bot.classify_m30_character(df4)
print("TEST 4 (insufficient data):", r4)
assert r4['signal'] == 'NONE', r4

# TEST 5: None input -> empty, no crash
r5 = bot.classify_m30_character(None)
print("TEST 5 (None input):", r5)
assert r5['signal'] == 'NONE', r5

print("\nALL CHOCH TESTS PASSED")
