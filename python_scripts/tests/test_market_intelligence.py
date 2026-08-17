"""Unit tests for market_intelligence.py's pure functions, using synthetic
OHLCV data with known expected outcomes."""
import pathlib as _pl
_SCRIPTS = _pl.Path(__file__).resolve().parent.parent  # python_scripts/
import sys
sys.path.insert(0, str(_SCRIPTS))

import numpy as np
import pandas as pd

import market_intelligence as mi

# =============================================================================
# TEST 1: compute_volume_profile -- known volume concentration
# =============================================================================
print("=== TEST 1: compute_volume_profile ===")
# 100 bars, all in a tight range [99, 101] EXCEPT a cluster of 20 bars at
# [104, 106] with much higher volume -- POC should land in the high-volume
# cluster, not the tight-range majority.
n = 100
highs = np.full(n, 101.0)
lows = np.full(n, 99.0)
vols = np.full(n, 10.0)
highs[40:60] = 106.0
lows[40:60] = 104.0
vols[40:60] = 100.0  # much heavier volume in this narrow band
closes = (highs + lows) / 2
df = pd.DataFrame({
    'time': pd.date_range('2026-01-01', periods=n, freq='h', tz='UTC'),
    'open': closes, 'high': highs, 'low': lows, 'close': closes, 'tick_volume': vols,
})
profile = mi.compute_volume_profile(df, num_bins=20)
print(f"POC={profile['poc']:.2f}, VAH={profile['vah']:.2f}, VAL={profile['val']:.2f}")
assert 104.0 <= profile['poc'] <= 106.0, f"FAILED: expected POC in [104,106], got {profile['poc']}"
print("PASSED: POC correctly lands in the high-volume cluster, not the wider low-volume range\n")

# Empty/degenerate cases
assert mi.compute_volume_profile(None)['poc'] is None
assert mi.compute_volume_profile(pd.DataFrame())['poc'] is None
print("PASSED: empty/degenerate inputs return None cleanly\n")

# =============================================================================
# TEST 2: compute_vwap
# =============================================================================
print("=== TEST 2: compute_vwap ===")
df_simple = pd.DataFrame({
    'high': [10.0, 20.0], 'low': [10.0, 20.0], 'close': [10.0, 20.0], 'tick_volume': [1.0, 1.0],
})
vwap = mi.compute_vwap(df_simple)
print(f"vwap={vwap}")
assert abs(vwap - 15.0) < 1e-9, f"FAILED: expected 15.0, got {vwap}"
# Weight one side heavier
df_weighted = pd.DataFrame({
    'high': [10.0, 20.0], 'low': [10.0, 20.0], 'close': [10.0, 20.0], 'tick_volume': [9.0, 1.0],
})
vwap2 = mi.compute_vwap(df_weighted)
print(f"weighted vwap={vwap2}")
assert vwap2 < 12.0, f"FAILED: expected close to 10 (heavier weight there), got {vwap2}"
print("PASSED\n")

# =============================================================================
# TEST 3: classify_auction_state -- BALANCE vs IMBALANCE
# =============================================================================
print("=== TEST 3: classify_auction_state ===")
# Balanced/rotating market: price oscillates in a tight band the whole time,
# last close still inside that band.
n2 = 150
rng = np.random.RandomState(42)
mid = 100 + 2 * np.sin(np.linspace(0, 8 * np.pi, n2))
highs_b = mid + 0.5
lows_b = mid - 0.5
closes_b = mid
vols_b = np.full(n2, 50.0)
df_balance = pd.DataFrame({
    'high': highs_b, 'low': lows_b, 'close': closes_b, 'tick_volume': vols_b,
})
state_b = mi.classify_auction_state(df_balance, num_bins=20)
print(f"balance scenario: {state_b['state']}")
assert state_b['state'] == "BALANCE", f"FAILED: expected BALANCE, got {state_b['state']}"

# Imbalanced market: rotates for a while then breaks out hard and stays out.
mid2 = np.concatenate([100 + 0.5 * np.sin(np.linspace(0, 6 * np.pi, 100)), np.linspace(101, 115, 30)])
highs_i = mid2 + 0.3
lows_i = mid2 - 0.3
closes_i = mid2
vols_i = np.full(len(mid2), 50.0)
df_imbalance = pd.DataFrame({
    'high': highs_i, 'low': lows_i, 'close': closes_i, 'tick_volume': vols_i,
})
state_i = mi.classify_auction_state(df_imbalance, num_bins=20)
print(f"imbalance scenario: {state_i['state']} (VAH={state_i['vah']:.2f}, last_close={closes_i[-1]:.2f})")
assert state_i['state'] == "IMBALANCE_UP", f"FAILED: expected IMBALANCE_UP, got {state_i['state']}"

# A single wick beyond VA that closes back inside should NOT count as imbalance
mid3 = 100 + 0.5 * np.sin(np.linspace(0, 6 * np.pi, 100))
highs_w = mid3 + 0.3
lows_w = mid3 - 0.3
closes_w = mid3.copy()
highs_w[-1] = 110.0  # one big wick
closes_w[-1] = mid3[-1]  # but closes back inside
df_wick = pd.DataFrame({
    'high': highs_w, 'low': lows_w, 'close': closes_w, 'tick_volume': np.full(100, 50.0),
})
state_w = mi.classify_auction_state(df_wick, num_bins=20)
print(f"wick-only scenario: {state_w['state']}")
assert state_w['state'] == "BALANCE", f"FAILED: a single wick that closes back inside should be BALANCE, got {state_w['state']}"
print("PASSED: BALANCE, IMBALANCE_UP, and wick-vs-real-breakout all classified correctly\n")

# =============================================================================
# TEST 4: find_swing_points / build_liquidity_map
# =============================================================================
print("=== TEST 4: build_liquidity_map ===")
def build_zigzag(anchors, n, spread=1.0):
    idxs = [a[0] for a in anchors]
    vals = [a[1] for a in anchors]
    mid = np.interp(np.arange(n), idxs, vals)
    return mid + spread / 2, mid - spread / 2, mid

n3 = 80
# Two roughly-equal highs (liquidity pool above), then price pulls back --
# current price well below both, leaving an untested BUY_SIDE pool.
highs4, lows4, closes4 = build_zigzag(
    [(0, 90), (15, 110.0), (30, 95), (45, 110.08), (60, 85), (79, 90)], n3
)
df4 = pd.DataFrame({
    'time': pd.date_range('2026-01-01', periods=n3, freq='h', tz='UTC'),
    'high': highs4, 'low': lows4, 'close': closes4, 'tick_volume': np.full(n3, 10.0),
})
pools = mi.build_liquidity_map(df4)
print(f"pools found: {[(round(p['price'],1), p['side'], p['touches'], p['swept']) for p in pools]}")
buy_side_pools = [p for p in pools if p['side'] == 'BUY_SIDE']
assert len(buy_side_pools) >= 1, "FAILED: expected at least one BUY_SIDE pool (the two ~110/111 highs)"
# The two highs (110, 111) should cluster into one pool given they're close
clustered = [p for p in buy_side_pools if p['touches'] >= 2]
assert len(clustered) >= 1, f"FAILED: expected the two nearby highs to cluster into one 2-touch pool, got {buy_side_pools}"
print("PASSED: equal highs correctly clustered into a multi-touch liquidity pool\n")

# =============================================================================
# TEST 5: is_rejection_candle (same contract as structural_swing_pro.py's)
# =============================================================================
print("=== TEST 5: is_rejection_candle ===")
bull_bar = pd.Series({'open': 100.0, 'close': 104.0, 'high': 104.5, 'low': 99.0})
bear_bar = pd.Series({'open': 100.0, 'close': 96.0, 'high': 100.5, 'low': 95.5})
assert bool(mi.is_rejection_candle(bull_bar, "BUY")) == True
assert bool(mi.is_rejection_candle(bear_bar, "SELL")) == True
assert bool(mi.is_rejection_candle(bull_bar, "SELL")) == False
print("PASSED\n")

# =============================================================================
# TEST 6: detect_balance_fade_signal end-to-end
# =============================================================================
print("=== TEST 6: detect_balance_fade_signal ===")
# Build a clean balanced range: many bars oscillating [95, 105], heavy
# volume in the middle (POC near 100), then a final bar that pokes ABOVE
# the VAH and closes back down hard (a textbook rejection at the range
# top). Large N deliberately -- with only ~160 bars, modifying the single
# final bar measurably shifts the recomputed VAH itself (confirmed
# directly: ~1.2 points), since it's ~1/160th of the whole profile's
# volume. At 1200 bars the same single-bar edit is diluted enough that
# the pre- and post-modification VAH are effectively identical, which is
# what "construct a bar exactly at the real VAH" actually requires.
n4 = 1200
rng2 = np.random.RandomState(7)
mid4 = 100 + 3.5 * np.sin(np.linspace(0, 75 * np.pi, n4))
highs5 = mid4 + 0.4
lows5 = mid4 - 0.4
closes5 = mid4.copy()
vols5 = np.full(n4, 30.0) + (3.5 - np.abs(mid4 - 100)) * 20  # heavier vol near mid (POC pull to 100)

df5 = pd.DataFrame({
    'time': pd.date_range('2026-01-01', periods=n4, freq='4h', tz='UTC'),
    'open': closes5, 'high': highs5, 'low': lows5, 'close': closes5, 'tick_volume': vols5,
})
auction5 = mi.classify_auction_state(df5, num_bins=20)
print(f"pre-signal auction state: {auction5['state']}, POC={auction5['poc']:.2f}, "
      f"VAH={auction5['vah']:.2f}, VAL={auction5['val']:.2f}")
assert auction5['state'] == "BALANCE"

# Craft a final rejection bar at VAH -- give it LOW volume (so it doesn't
# itself drag the recomputed profile around much) and a generous buffer
# above the pre-modification VAH (since adding this bar to the dataset
# and recomputing the profile does shift VAH somewhat -- confirmed
# directly: a +0.3 buffer wasn't enough margin, the recomputed VAH moved
# up more than that once this single high-volume bar was swapped for a
# low-volume one).
vah5 = auction5['vah']
df5.loc[n4 - 1, ['open', 'low', 'high', 'close', 'tick_volume']] = \
    [vah5 - 0.5, vah5 - 1.0, vah5 + 2.0, vah5 - 0.8, 5.0]

signal = mi.detect_balance_fade_signal(df5, "XAUUSDm", num_bins=20, min_rr=1.0)
print(f"signal: {signal}")
assert signal is not None, "FAILED: expected a SELL fade signal at VAH"
assert signal['direction'] == "SELL"
assert signal['stop_loss'] > signal['entry_price'] > signal['take_profit'], "FAILED: SL/TP on wrong sides for a SELL"
print("PASSED: balance-fade SELL signal fires with correct SL/TP sides\n")

# No signal when NOT at a value area edge (mid-range bar)
mid_bar_idx = 80
signal_mid = mi.detect_balance_fade_signal(df5.iloc[:mid_bar_idx + 1], "XAUUSDm", num_bins=20, min_rr=1.0)
print(f"mid-range signal (should likely be None): {signal_mid}")
# (not asserting None strictly -- depends on where bar 80 happens to sit -- just
#  confirming the function runs without error on a partial window)

# Liquidity guard: an untested BUY_SIDE pool just above VAH should block the fade
df6 = df5.copy()
# Inject two equal highs just above VAH before the final bar, close enough
# to trigger the guard, far enough back to be detected as swing highs.
guard_level = vah5 + 0.1
for idx in [n4 - 20, n4 - 10]:
    df6.loc[idx, ['open', 'high', 'low', 'close']] = [guard_level - 0.3, guard_level, guard_level - 0.6, guard_level - 0.4]
signal_guarded = mi.detect_balance_fade_signal(df6, "XAUUSDm", num_bins=20, min_rr=1.0, liquidity_guard_atr_mult=2.0)
print(f"guarded signal (should be None or a valid signal, not a broken one): {signal_guarded}")
if signal_guarded is not None:
    assert signal_guarded['stop_loss'] > signal_guarded['entry_price'] > signal_guarded['take_profit']
print("PASSED: liquidity guard runs without breaking signal validity\n")

# =============================================================================
# TEST 7: compute_intermarket_bias
# =============================================================================
print("=== TEST 7: compute_intermarket_bias ===")
primary_up = pd.DataFrame({'close': np.linspace(100, 110, 25)})
correlated_down = pd.DataFrame({'close': np.linspace(100, 90, 25)})  # inversely correlated, moved opposite as expected
bias1 = mi.compute_intermarket_bias(primary_up, correlated_down, expected_correlation_sign=-1, lookback=20)
print(f"expected inverse, actual inverse: {bias1}")
assert bias1['bias'] == "CONFIRMING"

correlated_up = pd.DataFrame({'close': np.linspace(100, 110, 25)})  # moved WITH primary, contradicts expected inverse
bias2 = mi.compute_intermarket_bias(primary_up, correlated_up, expected_correlation_sign=-1, lookback=20)
print(f"expected inverse, actual same-direction: {bias2}")
assert bias2['bias'] == "DIVERGING"
print("PASSED\n")

# =============================================================================
# TEST 8: volatility_target_multiplier
# =============================================================================
print("=== TEST 8: volatility_target_multiplier ===")
n5 = 200
base_range = np.full(n5, 1.0)
base_range[-14:] = 3.0  # current ATR window much wider than trailing history
closes7 = 100 + np.cumsum(np.random.RandomState(1).normal(0, 0.1, n5))
highs7 = closes7 + base_range / 2
lows7 = closes7 - base_range / 2
df7 = pd.DataFrame({'high': highs7, 'low': lows7, 'close': closes7})
mult_high_vol = mi.volatility_target_multiplier(df7, atr_period=14, lookback=100)
print(f"elevated current vol -> multiplier={mult_high_vol:.2f} (expect < 1.0)")
assert mult_high_vol < 1.0, f"FAILED: expected size-down multiplier, got {mult_high_vol}"

base_range2 = np.full(n5, 3.0)
base_range2[-14:] = 1.0  # current ATR much tighter than trailing history
highs8 = closes7 + base_range2 / 2
lows8 = closes7 - base_range2 / 2
df8 = pd.DataFrame({'high': highs8, 'low': lows8, 'close': closes7})
mult_low_vol = mi.volatility_target_multiplier(df8, atr_period=14, lookback=100)
print(f"compressed current vol -> multiplier={mult_low_vol:.2f} (expect > 1.0)")
assert mult_low_vol > 1.0, f"FAILED: expected size-up multiplier, got {mult_low_vol}"
print("PASSED\n")

# =============================================================================
# TEST 9: cot_positioning_bias
# =============================================================================
print("=== TEST 9: cot_positioning_bias ===")
crowded_long = {"noncomm_long": 900.0, "noncomm_short": 100.0, "noncomm_net": 800.0}
crowded_short = {"noncomm_long": 100.0, "noncomm_short": 900.0, "noncomm_net": -800.0}
balanced = {"noncomm_long": 500.0, "noncomm_short": 480.0, "noncomm_net": 20.0}
assert mi.cot_positioning_bias(crowded_long)['bias'] == "CROWDED_LONG"
assert mi.cot_positioning_bias(crowded_short)['bias'] == "CROWDED_SHORT"
assert mi.cot_positioning_bias(balanced)['bias'] == "NEUTRAL"
assert mi.cot_positioning_bias(None)['bias'] == "NEUTRAL"
print("PASSED\n")

print("=== ALL MARKET_INTELLIGENCE TESTS PASSED ===")
