"""
Session-anchored SD, wired into the live spike detector.

Going straight to live trading, so the properties that matter here are the
SAFE ONES: the anchor only changes inside a macro window, an incomplete
anchor leg falls back rather than projecting a too-small range, and the
whole thing can be switched off without a redeploy.
"""
import pathlib as _pl
import sys
from datetime import datetime, timezone
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
import macro_windows as mw
import midnight_sd as msd

passed = failed = 0
def check(name, fn):
    global passed, failed
    try:
        fn(); passed += 1; print(f"  PASS  {name}")
    except AssertionError as e:
        failed += 1; print(f"  FAIL  {name}: {e}")
    except Exception as e:
        failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")

SRC = open(_pl.Path(__file__).resolve().parent.parent /
           'hybrid_trading_bot_multiuser.py', encoding='utf-8').read()

# ---------- the wiring itself ----------
def t1():
    assert 'def resolve_sd_anchor' in SRC
    # count CALLS only -- the def line matches the same substring
    calls = SRC.count('= resolve_sd_anchor(symbol')
    assert calls == 2, f"expected 2 call sites, found {calls}"
    assert 'detect_manipulation_spike(df_m5, atr, _sd_ref, _sd_anchor)' in SRC
    assert 'detect_manipulation_spike(df_m15, atr_m15, _sd_ref, _sd_anchor)' in SRC
check("both spike call sites pass the resolved anchor", t1)

def t2():
    assert 'ENABLE_MACRO_SD_ANCHOR: bool = True' in SRC
    assert 'ENABLE_MACRO_5MIN_RULE: bool = True' in SRC
    assert "getattr(config, 'ENABLE_MACRO_SD_ANCHOR', False)" in SRC, \
        "flag must default OFF when absent, so a stale config cannot silently enable it"
check("kill switches exist; missing flag defaults to the old behaviour", t2)

def t3():
    i = SRC.find('def resolve_sd_anchor')
    body = SRC[i:i + 2000]
    assert "return None, 'rolling'" in body
    assert body.count("return None, 'rolling'") >= 4, \
        "every uncertain path must fall back to the rolling window"
check("resolver falls back to rolling on off/no-window/bad-leg/error", t3)

def t4():
    i = SRC.find('def detect_manipulation_spike')
    body = SRC[i:i + 1800]
    assert 'if ref_override is not None:' in body
    assert "ref      = df.iloc[-13:-3]" in body, "rolling fallback removed"
check("spike detector keeps the rolling window as its fallback", t4)

# ---------- the 5-minute rule gate ----------
def t5():
    i = SRC.find('THE 5-MINUTE RULE')
    body = SRC[i:i + 1600]
    assert '_sd_ref is not None' in body, "rule must apply only to session-anchored setups"
    assert 'df_m5.iloc[-2]' in body, "must use the last CLOSED candle, not the forming one"
    assert 'dj.VETO' in body and 'record_rejection' in body, "blocked entries must be journalled"
check("5-min rule: session-anchored only, closed candle, journalled", t5)

def t6():
    i = SRC.find('THE 5-MINUTE RULE')
    body = SRC[i:i + 1600]
    d = body.find("_side5 = 'above' if direction == 'SELL' else 'below'")
    assert d > 0, "side not derived from direction"
    assert SRC.find("direction = 'SELL' if spike['type']") < SRC.find('THE 5-MINUTE RULE'), \
        "rule uses `direction` before it is assigned"
check("rule maps SELL->above / BUY->below and runs after direction is set", t6)

# ---------- behaviour, not just presence ----------
def t7():
    # inside TEN_AM, an anchor exists; outside every window, it must not
    inside = datetime(2026, 8, 18, 14, 2, tzinfo=timezone.utc)   # 10:02 NY
    outside = datetime(2026, 8, 18, 18, 0, tzinfo=timezone.utc)  # 14:00 NY
    assert mw.active_window(inside) == 'TEN_AM'
    assert mw.active_window(outside) is None
check("anchor only engages inside a macro window", t7)

def t8():
    # A too-small anchor leg puts the -2 zone far too close to price. Confirm
    # the geometry so the fallback's purpose is explicit and tested.
    hi, lo = 4393.756, 4389.911
    wide = msd.sd_levels(hi, lo)['up_2']
    narrow = msd.sd_levels(hi, hi - 0.2)['up_2']       # leg only 5% as wide
    assert (narrow - hi) < (wide - hi) / 10, \
        "a truncated leg brings the -2 zone far closer -- hence the fallback"
check("truncated anchor leg would put -2 SD far too close (why we fall back)", t8)

def t9():
    hi, lo = 4393.756, 4389.911
    z = mw.classify_zone(hi + (hi - lo) * 2.25, hi, lo)
    assert z['direction'] == 'SELL' and z['kind'] == 'REVERSAL'
    lvl = msd.sd_levels(hi, lo)['up_2.5']
    ok, why = mw.five_minute_rule(lvl - 1.0, lvl + 3.0, lvl - 1.2, lvl + 2.8, lvl, 'above')
    assert not ok, "thick body through -2.5 must block the short"
check("end-to-end: -2.25 tap says SELL, thick body through -2.5 blocks it", t9)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
