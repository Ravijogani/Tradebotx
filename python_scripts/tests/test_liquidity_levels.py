import pathlib as _pl
_SCRIPTS = _pl.Path(__file__).resolve().parent.parent  # python_scripts/
import sys
sys.path.insert(0, str(_SCRIPTS))
import market_intelligence as mi
import pandas as pd
import numpy as np

def make_h1(n=200, start_price=100.0, seed=1):
    rng = np.random.RandomState(seed)
    t0 = pd.Timestamp("2026-01-05 00:00:00", tz="UTC")  # Monday 00:00 UTC
    rows = []
    price = start_price
    for i in range(n):
        o = price
        c = o + rng.uniform(-0.3, 0.3)
        hi = max(o, c) + rng.uniform(0, 0.15)
        lo = min(o, c) - rng.uniform(0, 0.15)
        rows.append({"time": t0 + pd.Timedelta(hours=i), "open": o, "high": hi, "low": lo, "close": c, "tick_volume": 100})
        price = c
    return pd.DataFrame(rows)

def make_d1(n=10, start_price=100.0, seed=2):
    rng = np.random.RandomState(seed)
    t0 = pd.Timestamp("2026-01-01", tz="UTC")
    rows = []
    price = start_price
    for i in range(n):
        o = price
        c = o + rng.uniform(-1, 1)
        hi = max(o, c) + rng.uniform(0, 0.5)
        lo = min(o, c) - rng.uniform(0, 0.5)
        rows.append({"time": t0 + pd.Timedelta(days=i), "open": o, "high": hi, "low": lo, "close": c, "tick_volume": 1000})
        price = c
    return pd.DataFrame(rows)

# TEST 1: PDH/PDL uses the SECOND-TO-LAST D1 bar (not the possibly-still-forming last one)
df_d1 = make_d1(10)
df_h1 = make_h1(200)
levels = mi.compute_liquidity_reference_levels(df_d1, df_h1)
labels = {l["label"]: l for l in levels}
assert "PDH" in labels and "PDL" in labels, labels
expected_pdh = float(df_d1["high"].iloc[-2])
expected_pdl = float(df_d1["low"].iloc[-2])
assert abs(labels["PDH"]["price"] - expected_pdh) < 1e-9, (labels["PDH"], expected_pdh)
assert abs(labels["PDL"]["price"] - expected_pdl) < 1e-9, (labels["PDL"], expected_pdl)
print("TEST 1 (PDH/PDL correct row) PASS:", labels["PDH"], labels["PDL"])

# TEST 2: H1_HIGH/H1_LOW use second-to-last H1 bar
assert "H1_HIGH" in labels and "H1_LOW" in labels
expected_h1h = float(df_h1["high"].iloc[-2])
assert abs(labels["H1_HIGH"]["price"] - expected_h1h) < 1e-9
print("TEST 2 (H1_HIGH/LOW correct row) PASS")

# TEST 3: side classification -- a level above current price must be BUY_SIDE
current_price = float(df_h1["close"].iloc[-1])
for lvl in levels:
    if lvl["price"] > current_price:
        assert lvl["side"] == "BUY_SIDE", lvl
    else:
        assert lvl["side"] == "SELL_SIDE", lvl
print("TEST 3 (side classification) PASS")

# TEST 4: session high/low -- build a dataset with a clean, isolated Asian
# session spike so we can verify the exact high/low gets picked up, and
# that it's NOT the still-in-progress current session.
rows = []
t0 = pd.Timestamp("2026-02-02 00:00:00", tz="UTC")  # Monday, starts in Asian session
for h in range(30):  # 30 hours -- covers Asian, London, partial NY
    rows.append({"time": t0 + pd.Timedelta(hours=h), "open": 100, "high": 100.1, "low": 99.9, "close": 100, "tick_volume": 50})
# Spike the Asian-session hours (0-7) on day 1 to a known high/low
for h in range(0, 7):
    rows[h]["high"] = 105.0
    rows[h]["low"] = 95.0
df_sess = pd.DataFrame(rows)
res = mi.compute_session_high_low(df_sess, mi._SESSION_HOURS_UTC["ASIAN"])
assert res is not None
hi, lo, end_time = res
assert abs(hi - 105.0) < 1e-9 and abs(lo - 95.0) < 1e-9, (hi, lo)
print("TEST 4 (session high/low) PASS:", hi, lo, end_time)

# TEST 5: swept vs untested -- a level whose price has already been
# touched by a later H1 high should be marked swept; one that hasn't
# should stay untested.
df_swept_test = make_h1(50)
h1_max_high = float(df_swept_test["high"].max())
h1_min_low = float(df_swept_test["low"].min())
df_d1_swept = make_d1(5)
# PDH set just below the H1 series' actual max high -> guaranteed swept
# (some later H1 bar's high reaches/exceeds it).
df_d1_swept.loc[df_d1_swept.index[-2], "high"] = h1_max_high - 0.01
# PDL set far below the H1 series' actual min low -> guaranteed untested
# (no H1 bar ever trades down that far).
df_d1_swept.loc[df_d1_swept.index[-2], "low"] = h1_min_low - 50.0
levels_swept = mi.compute_liquidity_reference_levels(df_d1_swept, df_swept_test)
pdh = next(l for l in levels_swept if l["label"] == "PDH")
pdl = next(l for l in levels_swept if l["label"] == "PDL")
assert pdh["swept"] is True, pdh
assert pdl["swept"] is False, pdl
print("TEST 5 (swept vs untested detection) PASS:", pdh, pdl)

# TEST 6: FVG detection -- construct an explicit bullish gap
rows_fvg = []
t0 = pd.Timestamp("2026-03-01", tz="UTC")
price = 100.0
for i in range(30):
    rows_fvg.append({"time": t0 + pd.Timedelta(hours=i), "open": price, "high": price + 0.2, "low": price - 0.2, "close": price, "tick_volume": 10})
# Bar 20: before (high=100.2) ; Bar 21: strong displacement up; Bar 22: after (low=101.5, gap above bar20's high)
rows_fvg[20]["high"] = 100.2
rows_fvg[21]["open"] = 100.2; rows_fvg[21]["close"] = 101.6; rows_fvg[21]["high"] = 101.7; rows_fvg[21]["low"] = 100.2
rows_fvg[22]["low"] = 101.5; rows_fvg[22]["open"] = 101.5; rows_fvg[22]["close"] = 101.8; rows_fvg[22]["high"] = 102.0
# keep everything after well above the gap so it stays unmitigated
for i in range(23, 30):
    rows_fvg[i]["low"] = 101.6
    rows_fvg[i]["open"] = 101.8; rows_fvg[i]["close"] = 101.9; rows_fvg[i]["high"] = 102.1
df_fvg = pd.DataFrame(rows_fvg)
zones = mi.detect_fvg_zones(df_fvg, "BUY", lookback=15)
assert len(zones) >= 1, zones
z = zones[0]
assert abs(z["low"] - 100.2) < 1e-9 and abs(z["high"] - 101.5) < 1e-9, z
print("TEST 6 (bullish FVG detection) PASS:", z)

# TEST 7: FVG mitigation -- if price later trades back into the gap, it
# should NOT be returned.
rows_fvg2 = [dict(r) for r in rows_fvg]
rows_fvg2[25]["low"] = 100.5  # trades back into the 100.2-101.5 gap
df_fvg2 = pd.DataFrame(rows_fvg2)
zones2 = mi.detect_fvg_zones(df_fvg2, "BUY", lookback=15)
assert all(not (z["low"] <= 100.2 and z["high"] >= 101.5) for z in zones2) or len(zones2) == 0, zones2
print("TEST 7 (FVG mitigation) PASS:", zones2)

# TEST 8: liquidity_confluence_check -- BUY at an untested SELL_SIDE level should be confluent
levels_test = [{"label": "PDL", "price": 99.5, "side": "SELL_SIDE", "swept": False}]
r = mi.liquidity_confluence_check(entry_price=99.52, direction="BUY", levels=levels_test, atr=1.0, tolerance_atr_mult=0.5)
assert r["confluent"] is True and r["matched_level"] == "PDL", r
print("TEST 8 (confluence match) PASS:", r)

# TEST 9: liquidity_confluence_check -- swept level must NOT count
levels_swept_test = [{"label": "PDL", "price": 99.5, "side": "SELL_SIDE", "swept": True}]
r2 = mi.liquidity_confluence_check(entry_price=99.52, direction="BUY", levels=levels_swept_test, atr=1.0)
assert r2["confluent"] is False, r2
print("TEST 9 (swept level excluded) PASS:", r2)

# TEST 10: liquidity_confluence_check -- far from any level, no FVG -> not confluent
r3 = mi.liquidity_confluence_check(entry_price=500.0, direction="BUY", levels=levels_test, atr=1.0)
assert r3["confluent"] is False, r3
print("TEST 10 (no confluence far away) PASS:", r3)

# TEST 11: nearest_liquidity_target -- picks nearest qualifying level, skips swept/wrong-side
levels_tp = [
    {"label": "H1_HIGH", "price": 102.0, "side": "BUY_SIDE", "swept": False},  # dist 2, sl_dist=1 -> RR 2.0 qualifies
    {"label": "PDH", "price": 105.0, "side": "BUY_SIDE", "swept": False},       # farther, also qualifies
    {"label": "ASIAN_HIGH", "price": 101.2, "side": "BUY_SIDE", "swept": True}, # closer but swept -- must be excluded
]
tp = mi.nearest_liquidity_target(entry_price=100.0, direction="BUY", levels=levels_tp, sl_distance=1.0, min_rr=1.5)
assert tp == 102.0, tp
print("TEST 11 (nearest target, swept excluded) PASS:", tp)

# TEST 12: nearest_liquidity_target -- returns None when nothing clears min_rr
tp2 = mi.nearest_liquidity_target(entry_price=100.0, direction="BUY", levels=[{"label": "X", "price": 100.5, "side": "BUY_SIDE", "swept": False}], sl_distance=1.0, min_rr=1.5)
assert tp2 is None, tp2
print("TEST 12 (no qualifying target -> None) PASS")

print("\nALL 12 LIQUIDITY-REFERENCE TESTS PASSED")
