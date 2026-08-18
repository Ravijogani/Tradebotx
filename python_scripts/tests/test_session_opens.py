"""
Midnight (18:00 NY) / Daylight (00:00 NY) opening strategy.

Sequence-based, not projection-based: fake momentum -> sweep -> MSS ->
FVG/extreme OB. The properties worth pinning are the ones that stop it
degenerating into breakout-chasing, which is the retail side of the very
trap it exists to fade.
"""
import pathlib as _pl
import sys
from datetime import datetime, timezone
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
import session_opens as so

passed = failed = 0
def check(name, fn):
    global passed, failed
    try:
        fn(); passed += 1; print(f"  PASS  {name}")
    except AssertionError as e:
        failed += 1; print(f"  FAIL  {name}: {e}")
    except Exception as e:
        failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")

OPEN = 4390.0
ATR = 2.0

# ---------- session times ----------
def t1():
    assert so.SESSION_OPEN_NY['MIDNIGHT'] == (18, 0), "midnight open is 18:00 NY"
    assert so.SESSION_OPEN_NY['DAYLIGHT'] == (0, 0), "daylight open is 00:00 NY"
check("MIDNIGHT=18:00 NY, DAYLIGHT=00:00 NY (per the trader's definition)", t1)

def t2():
    from midnight_sd import ny_window_utc
    aug = datetime(2026, 8, 18, 23, 0, tzinfo=timezone.utc)     # EDT
    s, _ = ny_window_utc(aug, (18, 0), (18, 0))
    assert s.hour == 22, f"18:00 NY in EDT should be 22:00 UTC, got {s.hour}"
    jan = datetime(2026, 1, 15, 23, 0, tzinfo=timezone.utc)     # EST
    s2, _ = ny_window_utc(jan, (18, 0), (18, 0))
    assert s2.hour == 23, f"18:00 NY in EST should be 23:00 UTC, got {s2.hour}"
check("18:00 NY resolves DST-aware (22:00 UTC EDT / 23:00 UTC EST)", t2)

def t3():
    try:
        so.session_open_price('LONDON', None)
        raise AssertionError("unknown session accepted")
    except KeyError:
        pass
check("unknown session name raises rather than guessing", t3)

# ---------- premium / discount ----------
def t4():
    assert so.pricing_side(OPEN + 1, OPEN) == 'PREMIUM'
    assert so.pricing_side(OPEN - 1, OPEN) == 'DISCOUNT'
    assert so.pricing_side(OPEN, OPEN) == 'EQUILIBRIUM'
check("premium above the open, discount below", t4)

# ---------- the trap sequence ----------
def t5():
    # pushed UP through the open first, then came back below -> trap formed
    st = so.session_state(OPEN, [OPEN + 3, OPEN + 4, OPEN + 1],
                          [OPEN + 1, OPEN - 1, OPEN - 2], ATR)
    assert st['crossed_both'] and not st['no_go']
    assert st['fake_side'] == 'above'
    assert st['expected_direction'] == 'SELL', st
check("push above the open then back below: fake=above -> SELL setup", t5)

def t6():
    # First bar entirely BELOW the open, so the order is unambiguous.
    st = so.session_state(OPEN, [OPEN - 1, OPEN + 2],
                          [OPEN - 3, OPEN - 4], ATR)
    assert st['fake_side'] == 'below' and st['expected_direction'] == 'BUY', st
check("the mirror: push below first -> BUY setup", t6)

def t6b():
    # First bar STRADDLES the open: OHLC cannot say which side came first.
    # Guessing would fade the real move and join the fake one.
    st = so.session_state(OPEN, [OPEN + 2], [OPEN - 2], ATR)
    assert st['fake_side_undetermined'], "straddle silently resolved to a side"
    ok, why = so.entry_allowed('SELL', OPEN + 1, OPEN, st)
    assert not ok and 'undetermined' in why, why
check("a straddling first bar is undetermined and blocks the trade", t6b)

# ---------- THE NO-GO RULE ----------
def t7():
    # ran 5 ATR straight up, never traded below the line: no manipulation
    highs = [OPEN + i for i in range(1, 12)]
    lows = [OPEN + i - 0.5 for i in range(1, 12)]
    st = so.session_state(OPEN, highs, lows, ATR)
    assert not st['crossed_both']
    assert st['no_go'], "one-way expansion with no cross must be a no-go"
check("one-way expansion without crossing the line = NO-GO", t7)

def t8():
    # small one-way drift is NOT a no-go -- the day may still trap later
    st = so.session_state(OPEN, [OPEN + 0.5, OPEN + 1.0], [OPEN + 0.1, OPEN + 0.2], ATR)
    assert not st['no_go'], "a small drift must not disqualify the session"
check("small one-way drift is not yet a no-go", t8)

def t9():
    ok, why = so.entry_allowed('SELL', OPEN + 2,
                               OPEN, {'no_go': True, 'expected_direction': 'SELL'})
    assert not ok and 'no-go' in why
check("no-go session blocks the entry", t9)

# ---------- the discipline rules ----------
def t10():
    st = {'no_go': False, 'expected_direction': 'SELL', 'fake_side': 'above'}
    ok, why = so.entry_allowed('BUY', OPEN - 1, OPEN, st)
    assert not ok and 'joins the fake push' in why, why
check("a trade that joins the fake push instead of fading it is refused", t10)

def t11():
    st = {'no_go': False, 'expected_direction': 'BUY', 'fake_side': 'below'}
    ok, why = so.entry_allowed('BUY', OPEN + 3, OPEN, st)
    assert not ok and 'premium' in why, why
check("BUYING above the open (premium) is refused -- that is the retail side", t11)

def t12():
    st = {'no_go': False, 'expected_direction': 'SELL', 'fake_side': 'above'}
    ok, why = so.entry_allowed('SELL', OPEN - 3, OPEN, st)
    assert not ok and 'discount' in why, why
check("SELLING below the open (discount) is refused", t12)

def t13():
    st = {'no_go': False, 'expected_direction': 'BUY', 'fake_side': 'below'}
    ok, why = so.entry_allowed('BUY', OPEN - 2, OPEN, st)
    assert ok, why
    assert 'discount' in why
    st2 = {'no_go': False, 'expected_direction': 'SELL', 'fake_side': 'above'}
    ok2, why2 = so.entry_allowed('SELL', OPEN + 2, OPEN, st2)
    assert ok2 and 'premium' in why2
check("a correct fade at the right side of the line is allowed", t13)

# ---------- degenerate input ----------
def t14():
    st = so.session_state(OPEN, [], [], ATR)
    assert st['fake_side'] is None and not st['no_go']
    # dict shape must be stable across every return path
    full = so.session_state(OPEN, [OPEN + 1], [OPEN + 0.5], ATR)
    assert set(st) == set(full), f"key sets differ: {set(full) ^ set(st)}"
    st2 = so.session_state(OPEN, [OPEN + 1], [OPEN - 1], 0.0)
    assert not st2['no_go'], "zero ATR must not manufacture a no-go verdict"
check("empty bars / zero ATR degrade quietly instead of inventing a verdict", t14)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
