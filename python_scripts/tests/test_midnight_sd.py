"""
Midnight-opening-range SD projections, checked against a HAND-PLOTTED chart.

Fixtures are the real numbers read off a TradingView XAUUSD session
(Tue 18 Aug 2026, 00:00-00:30 NY), so these tests fail if the maths ever
drifts from what a trader sees when they plot the same range themselves.
"""
import pathlib as _pl
import sys
from datetime import datetime, timezone
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
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

# --- Fixture A: upward projection fib, 0 at range high -------------------
HI_A, LO_A = 4393.756, 4389.911
EXPECT_UP_A = {1.0: 4397.602, 1.5: 4399.524, 2.0: 4401.447, 2.25: 4402.408,
               2.5: 4403.370, 4.0: 4409.138, 4.25: 4410.099, 4.5: 4411.060}
# --- Fixture B: a second session, read off the other screenshot ----------
HI_B, LO_B = 4338.797, 4334.314
EXPECT_UP_B = {1.0: 4343.280, 2.0: 4347.764, 2.25: 4348.884, 2.5: 4350.005,
               4.0: 4356.730, 4.25: 4357.851, 4.5: 4358.972}

TOL = 0.02   # hand-placed anchors; third-decimal agreement is the bar

def t1():
    lv = msd.sd_levels(HI_A, LO_A)
    for m, want in EXPECT_UP_A.items():
        got = lv[f'up_{m:g}']
        assert abs(got - want) < TOL, f"up_{m}: got {got:.3f}, chart says {want:.3f}"
check("upward projections match the hand-plotted chart (fixture A)", t1)

def t2():
    lv = msd.sd_levels(HI_B, LO_B)
    for m, want in EXPECT_UP_B.items():
        got = lv[f'up_{m:g}']
        assert abs(got - want) < TOL, f"up_{m}: got {got:.3f}, chart says {want:.3f}"
check("upward projections match a second independent session (fixture B)", t2)

def t3():
    lv = msd.sd_levels(HI_A, LO_A)
    assert abs(lv['in_0'] - 4393.756) < 1e-6
    assert abs(lv['in_1'] - 4389.911) < 1e-6
    assert abs(lv['in_0.25'] - 4392.795) < TOL, lv['in_0.25']
check("inside levels: 0 at the high, 1 at the low, 0.25 matches chart", t3)

def t4():
    lv = msd.sd_levels(HI_A, LO_A)
    span = HI_A - LO_A
    for m in (1.0, 1.5, 2.0, 2.25, 2.5, 4.0, 4.25, 4.5):
        assert abs(lv[f'down_{m:g}'] - (LO_A - span * m)) < 1e-9
    assert lv['down_2'] < LO_A < HI_A < lv['up_2'], "projections on the wrong side"
check("downward projections mirror upward from the range low", t4)

def t5():
    lv = msd.sd_levels(HI_A, LO_A)
    for banned in ('up_1.272', 'up_2.272', 'up_3.414', 'up_3', 'up_4.618'):
        assert banned not in lv, f"{banned} should not be plotted (unchecked in the tool)"
    assert len(lv) == len(msd.INSIDE_MULTIPLES) + 2 * len(msd.PROJECTION_MULTIPLES)
check("only the ticked multiples exist -- no 1.272/2.272/3.414 noise", t5)

# --- the actual trade signal -------------------------------------------
def t6():
    # Price rallied into ~4402.4 and rejected -> that is the MINOR zone above.
    z = msd.reversal_zone(4402.4, HI_A, LO_A)
    assert z is not None, "the -2.25 tap was not recognised as a reversal zone"
    assert z['zone'] == 'minor' and z['side'] == 'above'
    assert z['expected_direction'] == 'SELL', z
check("the live 4402.4 rejection lands in the MINOR reversal zone -> SELL", t6)

def t7():
    z = msd.reversal_zone(4410.0, HI_A, LO_A)     # -4.25 area
    assert z and z['zone'] == 'major' and z['expected_direction'] == 'SELL'
    z2 = msd.reversal_zone(4373.6, HI_A, LO_A)    # -4.25 below
    assert z2 and z2['zone'] == 'major' and z2['expected_direction'] == 'BUY'
check("major zone recognised on both sides with the right direction", t7)

def t8():
    for p in (4395.0, 4392.0, 4399.0, 4405.5, 4389.0):   # inside / between bands
        assert msd.reversal_zone(p, HI_A, LO_A) is None, f"{p} wrongly flagged"
check("prices outside the bands are not flagged", t8)

def t9():
    assert msd.sd_levels(100.0, 100.0) == {}
    assert msd.reversal_zone(100.0, 100.0, 100.0) is None
check("degenerate zero-width range returns nothing rather than dividing by it", t9)

def t10():
    # inverted arguments must not silently flip the geometry
    a = msd.sd_levels(HI_A, LO_A); b = msd.sd_levels(LO_A, HI_A)
    assert a == b, "high/low order changed the levels"
check("high/low argument order does not matter", t10)

# --- session window, DST-aware -----------------------------------------
def t11():
    # 18 Aug 2026 is EDT (UTC-4): 00:00 NY == 04:00 UTC
    s, e = msd.midnight_range_window(datetime(2026, 8, 18, 8, 0, tzinfo=timezone.utc))
    assert (s.hour, s.minute) == (4, 0), s
    assert (e.hour, e.minute) == (4, 30), e
    assert s.date().isoformat() == '2026-08-18'
check("EDT session: 00:00-00:30 NY resolves to 04:00-04:30 UTC", t11)

def t12():
    # January is EST (UTC-5): 00:00 NY == 05:00 UTC
    s, e = msd.midnight_range_window(datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc))
    assert (s.hour, s.minute) == (5, 0), s
    assert (e.hour, e.minute) == (5, 30), e
check("EST session: 00:00-00:30 NY resolves to 05:00-05:30 UTC", t12)

def t13():
    # 02:00 UTC on the 18th is still 22:00 NY on the 17th -> the CURRENT
    # window is the one from the 17th, not one that has not happened yet.
    s, _ = msd.midnight_range_window(datetime(2026, 8, 18, 2, 0, tzinfo=timezone.utc))
    assert s.date().isoformat() == '2026-08-17', s
    assert s <= datetime(2026, 8, 18, 2, 0, tzinfo=timezone.utc), "window is in the future"
check("before midnight NY, uses the previous session (never a future window)", t13)

def t14():
    naive = datetime(2026, 8, 18, 8, 0)     # no tzinfo
    s, e = msd.midnight_range_window(naive)
    assert (s.hour, e.hour) == (4, 4)
check("naive datetimes are treated as UTC rather than crashing", t14)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
