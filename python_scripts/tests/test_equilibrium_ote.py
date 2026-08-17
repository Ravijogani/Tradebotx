import pathlib as _pl
_SCRIPTS = _pl.Path(__file__).resolve().parent.parent  # python_scripts/
import sys
sys.path.insert(0, str(_SCRIPTS))
import pandas as pd
import numpy as np
import market_intelligence as mi

passed = 0
failed = 0

def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS: {name}")
    else:
        failed += 1
        print(f"FAIL: {name}")


def make_df(closes, highs=None, lows=None):
    n = len(closes)
    highs = highs if highs is not None else [c + 0.5 for c in closes]
    lows = lows if lows is not None else [c - 0.5 for c in closes]
    return pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=n, freq="5min"),
        "open": closes, "high": highs, "low": lows, "close": closes,
        "tick_volume": [100] * n,
    })


# Proper zigzag: down-leg (creates a swing LOW pivot) -> up-leg (creates a
# swing HIGH pivot) -> down-leg (pullback into discount at the end).
def build_up_then_pullback_df():
    down1 = list(np.linspace(110, 100, 8))
    up1 = list(np.linspace(100, 120, 15))
    down2 = list(np.linspace(120, 105, 10))
    return make_df(down1 + up1[1:] + down2[1:])

# Mirror: up-leg (swing HIGH) -> down-leg (swing LOW) -> up-leg (pullback
# into premium at the end) -- for SELL-side OTE / PREMIUM zone coverage.
def build_down_then_pullback_df():
    up1 = list(np.linspace(100, 110, 8))
    down1 = list(np.linspace(110, 90, 15))
    up2 = list(np.linspace(90, 105, 10))
    return make_df(up1 + down1[1:] + up2[1:])


df_swing = build_up_then_pullback_df()
df_down_swing = build_down_then_pullback_df()
df_short = make_df([100, 101, 102])
# Genuinely flat OHLC (high == low == close, no synthetic padding) -- a
# real zero-range series with no swings to find at all.
df_flat = make_df([100.0] * 30, highs=[100.0] * 30, lows=[100.0] * 30)


# --- compute_equilibrium_zone ---

eq = mi.compute_equilibrium_zone(df_swing, lookback=3)
check("equilibrium: found a zone", eq is not None)
if eq:
    check("equilibrium: low < high", eq["low"] < eq["high"])
    check("equilibrium: DISCOUNT after pullback below midpoint", eq["zone"] == "DISCOUNT")
    check("equilibrium: pct near expected (~0.26)", abs(eq["pct"] - 0.262) < 0.02)
    check("equilibrium: equilibrium == midpoint of high/low", abs(eq["equilibrium"] - (eq["high"] + eq["low"]) / 2) < 1e-9)

eq_prem = mi.compute_equilibrium_zone(df_down_swing, lookback=3)
check("equilibrium: PREMIUM after bounce above midpoint", eq_prem is not None and eq_prem["zone"] == "PREMIUM")

check("equilibrium: None on too-short df", mi.compute_equilibrium_zone(df_short) is None)
check("equilibrium: None on flat/no-swings data", mi.compute_equilibrium_zone(df_flat) is None)

# Exact-equilibrium edge case, constructed directly.
eq_exact = mi.premium_discount_confluence  # (unused here, just sanity on the dataclass-like dict below)


# --- premium_discount_confluence ---

pd_conf_buy_discount = mi.premium_discount_confluence("BUY", {"zone": "DISCOUNT", "pct": 0.2, "low": 100, "high": 120, "equilibrium": 110})
check("pd_confluence: BUY favorable in DISCOUNT", pd_conf_buy_discount["favorable"] is True)

pd_conf_buy_premium = mi.premium_discount_confluence("BUY", {"zone": "PREMIUM", "pct": 0.8, "low": 100, "high": 120, "equilibrium": 110})
check("pd_confluence: BUY NOT favorable in PREMIUM", pd_conf_buy_premium["favorable"] is False)

pd_conf_sell_premium = mi.premium_discount_confluence("SELL", {"zone": "PREMIUM", "pct": 0.8, "low": 100, "high": 120, "equilibrium": 110})
check("pd_confluence: SELL favorable in PREMIUM", pd_conf_sell_premium["favorable"] is True)

pd_conf_sell_discount = mi.premium_discount_confluence("SELL", {"zone": "DISCOUNT", "pct": 0.2, "low": 100, "high": 120, "equilibrium": 110})
check("pd_confluence: SELL NOT favorable in DISCOUNT", pd_conf_sell_discount["favorable"] is False)

pd_conf_none = mi.premium_discount_confluence("BUY", None)
check("pd_confluence: None info -> favorable=True (never blocks on absence)", pd_conf_none["favorable"] is True)

pd_conf_eq = mi.premium_discount_confluence("BUY", {"zone": "EQUILIBRIUM", "pct": 0.5, "low": 100, "high": 120, "equilibrium": 110})
check("pd_confluence: EQUILIBRIUM favorable for BUY", pd_conf_eq["favorable"] is True)
pd_conf_eq_sell = mi.premium_discount_confluence("SELL", {"zone": "EQUILIBRIUM", "pct": 0.5, "low": 100, "high": 120, "equilibrium": 110})
check("pd_confluence: EQUILIBRIUM favorable for SELL", pd_conf_eq_sell["favorable"] is True)


# --- compute_ote_zone ---

ote_buy = mi.compute_ote_zone(df_swing, "BUY", lookback=3)
check("ote: BUY zone found off completed up-leg", ote_buy is not None)
if ote_buy:
    check("ote: BUY zone low < high", ote_buy["low"] < ote_buy["high"])
    check("ote: BUY zone direction tagged", ote_buy["direction"] == "BUY")
    check("ote: BUY zone sits below the swing high (a real pullback zone)", ote_buy["high"] < 120.5)

ote_sell = mi.compute_ote_zone(df_down_swing, "SELL", lookback=3)
check("ote: SELL zone found off completed down-leg", ote_sell is not None)
if ote_sell:
    check("ote: SELL zone low < high", ote_sell["low"] < ote_sell["high"])
    check("ote: SELL zone direction tagged", ote_sell["direction"] == "SELL")

# Asking for the opposite direction's OTE when no completed leg of that
# kind exists yet (df_swing ends with a down-leg, so there's no completed
# UP-leg after the swing high for a SELL... wait -- SELL needs a down-leg
# after a swing high, and df_swing's last leg IS a down-leg after its
# swing high, so a SELL zone legitimately exists there too. Use the
# genuinely-absent case instead: asking df_down_swing (ends mid up-leg,
# swing-high -> swing-low -> rising, no swing high after the swing low)
# for a BUY needs a swing high after its last swing low, which doesn't
# exist yet since the final leg hasn't pivoted back down.
ote_wrong = mi.compute_ote_zone(df_down_swing, "BUY", lookback=3)
check("ote: None when no completed up-leg exists yet", ote_wrong is None)

check("ote: None on invalid direction", mi.compute_ote_zone(df_swing, "SIDEWAYS", lookback=3) is None)
check("ote: None on too-short df", mi.compute_ote_zone(df_short, "BUY") is None)

# --- in_ote_zone ---
check("in_ote_zone: None-safe (no zone -> False)", mi.in_ote_zone(105.0, None) is False)
zone = {"low": 100.0, "high": 105.0, "direction": "BUY"}
check("in_ote_zone: price inside -> True", mi.in_ote_zone(102.5, zone) is True)
check("in_ote_zone: price below -> False", mi.in_ote_zone(99.0, zone) is False)
check("in_ote_zone: price above -> False", mi.in_ote_zone(106.0, zone) is False)
check("in_ote_zone: price exactly on boundary -> True (inclusive)",
      mi.in_ote_zone(100.0, zone) is True and mi.in_ote_zone(105.0, zone) is True)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
