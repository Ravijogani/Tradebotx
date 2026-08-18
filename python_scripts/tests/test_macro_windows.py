"""
NY macro windows: time anchors + the two risk rules.

The costly mistake this pins down is the CONTINUATION vs REVERSAL flip.
-1.0..-1.5 is re-accumulation (trade WITH the leg); -2.0..-2.5 is the
reversal band (trade AGAINST). Same tool, same chart, opposite trade.
"""
import pathlib as _pl
import sys
from datetime import datetime, timezone
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
import macro_windows as mw

passed = failed = 0
def check(name, fn):
    global passed, failed
    try:
        fn(); passed += 1; print(f"  PASS  {name}")
    except AssertionError as e:
        failed += 1; print(f"  FAIL  {name}: {e}")
    except Exception as e:
        failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")

AUG = datetime(2026, 8, 18, 14, 0, tzinfo=timezone.utc)   # EDT day, UTC-4
JAN = datetime(2026, 1, 15, 16, 0, tzinfo=timezone.utc)   # EST day, UTC-5

# ---------- windows resolve to the right UTC, DST-aware ----------
def t1():
    for name, (h, m) in (('MACRO_0830', (12, 30)), ('NY_OPEN', (13, 30)),
                         ('TEN_AM', (14, 0)), ('MIDNIGHT', (4, 0))):
        s, _ = mw.window_bounds(name, AUG, 'execute')
        assert (s.hour, s.minute) == (h, m), f"{name} EDT -> {s.hour}:{s.minute:02d}"
check("EDT: 08:30/09:30/10:00/00:00 NY map to 12:30/13:30/14:00/04:00 UTC", t1)

def t2():
    s, _ = mw.window_bounds('NY_OPEN', JAN, 'execute')
    assert (s.hour, s.minute) == (14, 30), f"EST NY_OPEN -> {s.hour}:{s.minute:02d}"
check("EST: 09:30 NY maps to 14:30 UTC (offset shifts with DST)", t2)

# ---------- anchor legs differ from execution windows ----------
def t3():
    s, e = mw.window_bounds('TEN_AM', AUG, 'anchor')
    assert (s.hour, s.minute) == (13, 30), s      # 09:30 NY
    assert (e.hour, e.minute) == (13, 59), e      # 09:59 NY
check("TEN_AM anchors on the 09:30-09:59 leg, not on 10:00", t3)

def t4():
    s, e = mw.window_bounds('NY_OPEN', AUG, 'anchor')
    assert (s.hour, s.minute) == (12, 30) and (e.hour, e.minute) == (13, 30)
check("NY_OPEN anchors on the 08:30 news swing (08:30-09:30)", t4)

def t5():
    s, e = mw.window_bounds('MACRO_0830', AUG, 'anchor')
    assert (s.hour, s.minute) == (12, 30) and (e.hour, e.minute) == (12, 35)
check("MACRO_0830 anchors on the 5-minute news reaction candle", t5)

# ---------- active_window ----------
def t6():
    inside = datetime(2026, 8, 18, 14, 2, tzinfo=timezone.utc)   # 10:02 NY
    assert mw.active_window(inside) == 'TEN_AM'
    outside = datetime(2026, 8, 18, 18, 0, tzinfo=timezone.utc)  # 14:00 NY
    assert mw.active_window(outside) is None, "a setup at 14:00 NY is not a macro setup"
check("active_window identifies the open window and None outside all of them", t6)

def t7():
    edge = datetime(2026, 8, 18, 14, 5, tzinfo=timezone.utc)     # exactly 10:05
    assert mw.active_window(edge) is None, "window end must be exclusive"
check("window end is exclusive (10:05 is already past TEN_AM)", t7)

# ---------- THE FLIP: continuation vs reversal ----------
HI, LO = 4393.756, 4389.911          # the hand-verified midnight range
SPAN = HI - LO

def t8():
    z = mw.classify_zone(HI + SPAN * 2.25, HI, LO)
    assert z['zone'] == 'minor' and z['kind'] == 'REVERSAL'
    assert z['direction'] == 'SELL', z
check("-2.25 above the range: REVERSAL -> SELL", t8)

def t9():
    z = mw.classify_zone(HI + SPAN * 1.25, HI, LO)
    assert z['zone'] == 'continuation' and z['kind'] == 'CONTINUATION'
    assert z['direction'] == 'BUY', "continuation band must trade WITH the leg, not against it"
check("-1.25 above the range: CONTINUATION -> BUY (the flip)", t9)

def t10():
    below_rev = mw.classify_zone(LO - SPAN * 2.25, HI, LO)
    assert below_rev['direction'] == 'BUY' and below_rev['kind'] == 'REVERSAL'
    below_cont = mw.classify_zone(LO - SPAN * 1.25, HI, LO)
    assert below_cont['direction'] == 'SELL' and below_cont['kind'] == 'CONTINUATION'
check("the flip holds on the downside too", t10)

def t11():
    z = mw.classify_zone(HI + SPAN * 4.25, HI, LO)
    assert z['zone'] == 'major' and z['direction'] == 'SELL'
    for p in (HI + SPAN * 1.75, HI + SPAN * 3.0, HI + SPAN * 5.0, HI + SPAN * 0.5):
        assert mw.classify_zone(p, HI, LO) is None, f"{p} is between bands, must not flag"
check("major band recognised; gaps between bands are not flagged", t11)

# ---------- the 5-minute rule ----------
LEVEL = HI + SPAN * 2.5

def t12():
    # thick-bodied candle closing beyond -2.5 => continuation, refuse entry
    o, h, l, c = LEVEL - 1.0, LEVEL + 3.0, LEVEL - 1.2, LEVEL + 2.8
    ok, why = mw.five_minute_rule(o, h, l, c, LEVEL, 'above')
    assert not ok, f"thick body beyond the level was allowed: {why}"
    assert 'continuation' in why
check("thick body closing beyond -2.5 blocks entry (framework's 5-min rule)", t12)

def t13():
    # long upper wick, closes back inside => valid rejection
    o, h, l, c = LEVEL - 0.5, LEVEL + 3.0, LEVEL - 1.0, LEVEL - 0.8
    ok, why = mw.five_minute_rule(o, h, l, c, LEVEL, 'above')
    assert ok, f"a clean wick rejection was blocked: {why}"
check("wick rejection closing back inside is allowed", t13)

def t14():
    # closes just beyond but with a big rejection wick
    o, h, l, c = LEVEL - 2.0, LEVEL + 4.0, LEVEL - 2.2, LEVEL + 0.2
    ok, why = mw.five_minute_rule(o, h, l, c, LEVEL, 'above')
    assert ok and 'wick' in why, why
check("close just beyond with a large rejection wick is allowed", t14)

def t15():
    ok, why = mw.five_minute_rule(100.0, 100.0, 100.0, 100.0, LEVEL, 'above')
    assert not ok, "a zero-range candle must not read as permission"
check("degenerate candle fails CLOSED (no information != permission)", t15)

def t16():
    # Thick body driving DOWN through the level: open above it, close well
    # below it, almost no lower wick -> continuation, refuse entry.
    o, h, l, c = LEVEL + 1.0, LEVEL + 1.2, LEVEL - 3.0, LEVEL - 2.8
    ok, why = mw.five_minute_rule(o, h, l, c, LEVEL, 'below')
    assert not ok, f"downside thick body beyond the level was allowed: {why}"
    assert 'continuation' in why, why
    # And the mirror: a long lower wick that closes back above is a rejection.
    o2, h2, l2, c2 = LEVEL + 0.5, LEVEL + 1.0, LEVEL - 3.0, LEVEL + 0.8
    ok2, _ = mw.five_minute_rule(o2, h2, l2, c2, LEVEL, 'below')
    assert ok2, "downside wick rejection was blocked"
check("the rule works symmetrically on the 'below' side", t16)

# ---------- time cut ----------
def t17():
    assert not mw.time_cut_expired(1000.0, 1000.0 + 19 * 60)
    assert mw.time_cut_expired(1000.0, 1000.0 + 20 * 60)
    assert not mw.time_cut_expired(None, 123.0), "missing timestamp must not force a cut"
check("20-minute time cut fires at 20 minutes, not before", t17)

def t18():
    try:
        mw.window_bounds('LONDON_OPEN', AUG)
        raise AssertionError("unknown window silently accepted")
    except KeyError as e:
        assert 'LONDON_OPEN' in str(e)
check("an unknown window name raises rather than guessing", t18)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
