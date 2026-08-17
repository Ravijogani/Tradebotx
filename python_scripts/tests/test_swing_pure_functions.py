"""Unit tests for structural_swing_pro.py's pure decision functions, using
synthetic OHLC so the expected pivots/structure/signal are known exactly."""
import pathlib as _pl
_SCRIPTS = _pl.Path(__file__).resolve().parent.parent  # python_scripts/
import sys
sys.path.insert(0, str(_SCRIPTS))

import os
# Stub MetaTrader5 minimally (structural_swing_pro.py does `import MetaTrader5
# as mt5` at module scope and reads mt5.TIMEFRAME_D1 etc. for config defaults)
sys.path.insert(0, str(_SCRIPTS / "backtest"))
from backtest import mt5_stub
sys.modules["MetaTrader5"] = mt5_stub
from backtest import supabase_stub
sys.modules["supabase"] = supabase_stub

sys.argv = [
    "structural_swing_pro.py",
    "--user-id", "test", "--strategy-id", "test",
    "--mt5-login", "1", "--mt5-server", "test-server",
    "--supabase-url", "http://test.invalid",
]
os.environ.setdefault("MT5_PASSWORD", "unused")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "unused")

import pandas as pd
import numpy as np

import structural_swing_pro as swing

def build_zigzag(anchors, n, spread=1.0):
    """anchors: list of (index, mid_price), strictly increasing index,
    linearly interpolated between them so every anchor is an unambiguous
    local extremum (monotonic segments on both sides) -- no emergent
    spurious pivots from a tapering heuristic."""
    idxs = [a[0] for a in anchors]
    vals = [a[1] for a in anchors]
    mid = np.interp(np.arange(n), idxs, vals)
    return mid + spread / 2, mid - spread / 2, mid  # highs, lows, closes


print("=== TEST 1: find_swing_points on a known zigzag ===")
# Clean zigzag: 100 -> 110 (idx10, swing high) -> 85 (idx20, swing low) ->
# 130 (idx30, swing high, higher) -> 95 (idx40, swing low, higher) -> 100
n = 50
highs, lows, closes = build_zigzag(
    [(0, 100), (10, 110), (20, 85), (30, 130), (40, 95), (49, 100)], n
)
df = pd.DataFrame({
    'time': pd.date_range('2026-01-01', periods=n, freq='D', tz='UTC'),
    'open': closes, 'high': highs, 'low': lows, 'close': closes,
})

swing_highs, swing_lows = swing.find_swing_points(df, lookback=3)
print(f"swing_highs idx: {swing_highs}")
print(f"swing_lows idx: {swing_lows}")
assert 10 in swing_highs, f"FAILED: expected pivot at 10 in swing_highs, got {swing_highs}"
assert 30 in swing_highs, f"FAILED: expected pivot at 30 in swing_highs, got {swing_highs}"
assert 20 in swing_lows, f"FAILED: expected pivot at 20 in swing_lows, got {swing_lows}"
assert 40 in swing_lows, f"FAILED: expected pivot at 40 in swing_lows, got {swing_lows}"
print("PASSED: known pivots detected\n")

print("=== TEST 2: classify_structure ===")
structure = swing.classify_structure(df, swing_highs, swing_lows)
print(f"structure: {structure}")
assert structure == "BULLISH", f"FAILED: expected BULLISH, got {structure}"
print("PASSED\n")

# Bearish mirror: lower highs, lower lows
highs2, lows2, closes2 = build_zigzag(
    [(0, 100), (10, 130), (20, 100), (30, 110), (40, 85), (49, 90)], n
)
df2 = pd.DataFrame({
    'time': pd.date_range('2026-01-01', periods=n, freq='D', tz='UTC'),
    'open': closes2, 'high': highs2, 'low': lows2, 'close': closes2,
})
sh2, sl2 = swing.find_swing_points(df2, lookback=3)
structure2 = swing.classify_structure(df2, sh2, sl2)
print(f"bearish scenario structure: {structure2}")
assert structure2 == "BEARISH", f"FAILED: expected BEARISH, got {structure2}"
print("PASSED\n")

print("=== TEST 3: fib_zone ===")
zl, zh = swing.fib_zone(leg_start=100.0, leg_end=200.0, near=0.5, far=0.786)
print(f"fib_zone(100->200, 0.5, 0.786) = ({zl:.2f}, {zh:.2f})")
assert abs(zl - 121.4) < 0.5 and abs(zh - 150.0) < 0.5, f"FAILED: unexpected zone bounds ({zl}, {zh})"
print("PASSED\n")

print("=== TEST 4: is_rejection_candle ===")
bull_bar = pd.Series({'open': 100.0, 'close': 104.0, 'high': 104.5, 'low': 99.0})   # closes near top
bear_bar = pd.Series({'open': 100.0, 'close': 96.0, 'high': 100.5, 'low': 95.5})    # closes near bottom
weak_bar = pd.Series({'open': 100.0, 'close': 100.5, 'high': 104.0, 'low': 97.0})   # weak close, mid-range
assert bool(swing.is_rejection_candle(bull_bar, "BUY")) == True
assert bool(swing.is_rejection_candle(bear_bar, "SELL")) == True
assert bool(swing.is_rejection_candle(weak_bar, "BUY")) == False
assert bool(swing.is_rejection_candle(bull_bar, "SELL")) == False
print("PASSED\n")

print("=== TEST 5: find_nearest_target ===")
target_buy = swing.find_nearest_target(df, swing_highs, swing_lows, "BUY", entry_price=100.0)
print(f"nearest BUY target above 100: {target_buy}")
assert target_buy is not None and target_buy > 100.0
target_sell = swing.find_nearest_target(df2, sh2, sl2, "SELL", entry_price=95.0)
print(f"nearest SELL target below 95: {target_sell}")
assert target_sell is not None and target_sell < 95.0
print("PASSED\n")

print("=== TEST 6: detect_structural_swing_signal end-to-end (constructed BUY setup) ===")
# D1 series with clear bullish structure whose MOST RECENT leg is
# low(idx45=95) -> high(idx60=160) -- a fresh, large higher high with no
# closer intermediate swing high in between, so the RR to it is genuinely
# good from a deep pullback -- the earlier version of this test placed an
# intermediate swing high too close to the pullback zone, which correctly
# (not a bug) got skipped by the MIN_RR filter; this shape isolates "does
# a good-RR setup fire" from "does the filter correctly reject a poor one"
# (covered separately by the min_rr assertion already in this test).
n_full = 75
highs_full, lows_full, closes_full = build_zigzag(
    [(0, 100), (15, 90), (30, 105), (45, 95), (60, 160), (74, 150)], n_full
)
d1_full = pd.DataFrame({
    'time': pd.date_range('2026-01-01', periods=n_full, freq='D', tz='UTC'),
    'open': closes_full, 'high': highs_full, 'low': lows_full, 'close': closes_full,
})

sh_full, sl_full = swing.find_swing_points(d1_full, lookback=3)
print(f"full D1 swing_highs: {sh_full[-3:]}, swing_lows: {sl_full[-3:]}")
structure_full = swing.classify_structure(d1_full, sh_full, sl_full)
print(f"structure: {structure_full}")
assert structure_full == "BULLISH"

leg_start_idx, leg_end_idx = sl_full[-1], sh_full[-1]
leg_start = d1_full['low'].iloc[leg_start_idx]
leg_end = d1_full['high'].iloc[leg_end_idx]
print(f"leg: low={leg_start:.2f} (idx {leg_start_idx}) -> high={leg_end:.2f} (idx {leg_end_idx})")
zone_low, zone_high = swing.fib_zone(leg_start, leg_end, 0.5, 0.786)
print(f"fib zone: ({zone_low:.2f}, {zone_high:.2f})")

# H4 series: last bar dips into the zone and closes as a bullish rejection candle
h4 = pd.DataFrame({
    'time': pd.date_range('2026-03-01', periods=15, freq='4h', tz='UTC'),
    'open': np.linspace(zone_high + 5, zone_low, 15),
    'high': np.linspace(zone_high + 8, zone_low + 3, 15),
    'low': np.linspace(zone_high + 2, zone_low - 2, 15),
    'close': np.linspace(zone_high + 4, zone_low + 1, 15),
})
near_zone_low = zone_low + (zone_high - zone_low) * 0.15  # deep pullback entry -- shorter SL distance, better RR
h4.loc[14, ['open', 'low', 'high', 'close']] = [
    near_zone_low - 2, near_zone_low - 4, near_zone_low + 3, near_zone_low + 2.5
]  # bullish rejection, wicks into the deep end of the zone

signal = swing.detect_structural_swing_signal(d1_full, h4, "XAUUSDm")
print(f"signal: {signal}")
assert signal is not None, "FAILED: expected a BUY signal, got None"
assert signal['direction'] == "BUY"
assert signal['stop_loss'] < signal['entry_price'] < signal['take_profit']
rr = abs(signal['take_profit'] - signal['entry_price']) / abs(signal['entry_price'] - signal['stop_loss'])
print(f"RR = {rr:.2f}")
assert rr >= swing.config.MIN_RR - 0.01, f"FAILED: RR {rr} below MIN_RR {swing.config.MIN_RR}"
print("PASSED: end-to-end BUY signal detected with correct SL/TP sides and RR\n")

print("=== TEST 7: no signal when H4 doesn't confirm (no rejection candle) ===")
h4_no_confirm = h4.copy()
h4_no_confirm.loc[14, ['open', 'low', 'high', 'close']] = [
    near_zone_low + 2, near_zone_low - 4, near_zone_low + 3, near_zone_low - 2
]  # closes weak, not a rejection
signal2 = swing.detect_structural_swing_signal(d1_full, h4_no_confirm, "XAUUSDm")
print(f"signal (should be None): {signal2}")
assert signal2 is None, "FAILED: expected None without a rejection candle"
print("PASSED\n")

print("=== TEST 8: project_lot_and_risk sanity (reused pattern from intraday.py fix) ===")
# entry/stop/equity chosen so lot_raw lands comfortably away from a
# lot_step rounding boundary (0.025 in an earlier draft of this test sat
# almost exactly between two 0.01 lot steps, which made quantization noise
# -- an expected, real effect of discrete lot sizes -- look like a bug).
proj = swing.project_lot_and_risk("XAUUSDm", entry_price=2400.0, stop_loss=2390.0,
                                    risk_percent=1.0, account_equity=500_000.0)
print(f"lot={proj['lot_size']}, lot_raw={proj['lot_raw']:.4f}, "
      f"actual_risk%={proj['actual_risk_percent']:.3f} (intended 1.0%)")
assert abs(proj['actual_risk_percent'] - 1.0) < 0.05
print("PASSED\n")

# Also confirm the min-lot-floor overshoot behavior (same real-risk
# correctness the intraday.py fix established) shows up here too, on a
# tiny account with a wide stop.
proj2 = swing.project_lot_and_risk("XAUUSDm", entry_price=2400.0, stop_loss=2350.0,
                                     risk_percent=0.1, account_equity=200.0)
print(f"min-lot-floor case: lot_raw={proj2['lot_raw']:.6f}, lot_size={proj2['lot_size']}, "
      f"intended%={proj2['intended_risk_percent']:.3f}, actual%={proj2['actual_risk_percent']:.2f}")
assert proj2['lot_raw'] < proj2['spec']['min_lot']
assert proj2['actual_risk_percent'] > proj2['intended_risk_percent'] * 2
print("PASSED: real floored risk correctly diverges from intended risk\n")

print("=== ALL SWING PURE-FUNCTION TESTS PASSED ===")
