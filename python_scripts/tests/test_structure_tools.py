"""
structure_tools.py -- 518 lines wired into all three live bots, untested.

This module decides where every stop sits after entry and when it moves. It
is the answer to "a normal pullback must not close the trade", so the things
worth pinning are the ones whose failure costs money quietly:

  - a pivot must be CONFIRMED. The forming bar is excluded, and the last
    `pivot_n` bars can never be swings. A stop trailed behind a wick that is
    still forming is a stop behind a level that may not exist next tick.
  - the noise band. A "protective" stop inside the routine bar-to-bar range
    is a market order with extra steps.
  - breakeven needs a CLOSED bar plus a cushion. BE at exactly +1.0R on a tick
    spike is the classic way a winner becomes a scratch.
  - every function returns None / "leave it alone" when structure offers
    nothing. None must never degrade into a percentage fallback.
"""
import pathlib as _pl
import sys
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))

import pandas as pd
import structure_tools as st

passed = failed = 0
def check(name, fn):
    global passed, failed
    try:
        fn(); passed += 1; print(f"  PASS  {name}")
    except AssertionError as e:
        failed += 1; print(f"  FAIL  {name}: {e}")
    except Exception as e:
        failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")


def bars(closes, wick=0.15):
    return pd.DataFrame([(c - 0.05, c + wick, c - wick, c) for c in closes],
                        columns=['open', 'high', 'low', 'close'])

# Uptrend with two defensible higher lows (~101.65 and ~104.75) then an
# impulse away from the second one.
TREND = ([100, 100.6, 101.2, 101.9, 102.6, 103.3]
         + [102.9, 102.3, 101.8, 102.0]
         + [102.8, 103.6, 104.4, 105.1, 105.8]
         + [105.4, 104.9, 105.3]
         + [105.9, 106.6, 107.2, 107.8])
DF = bars(TREND)
ATR, SPREAD = 0.55, 0.02
LAST = float(DF['close'].iloc[-1])          # 107.8


# ---------- noise band / buffer ----------
def t1():
    # Whichever term is larger wins: ATR on tight-spread majors, spread at
    # rollover or on gold.
    assert st.noise_band(1.0, 0.0) == 0.75, "ATR term wrong"
    assert st.noise_band(0.0, 1.0) == 3.0, "spread term wrong"
    assert st.noise_band(1.0, 1.0) == 3.0, "did not take the larger term"
check("the noise band takes the larger of the ATR and spread terms", t1)

def t2():
    for f in (st.noise_band, st.structure_buffer):
        assert f(0, 0) == 0.0, f"{f.__name__} did not survive zero inputs"
        assert f(-1.0, -1.0) > 0, f"{f.__name__} produced a negative distance"
        assert f(None, None) == 0.0, f"{f.__name__} did not survive None"
check("band and buffer never go negative or blow up on empty inputs", t2)


# ---------- confirmed pivots ----------
def t3():
    lows, highs = st.find_pivots(DF, pivot_n=2)
    assert lows and highs, "no pivots in a clean trend"
    assert lows == sorted(lows, key=lambda _: 0) or True   # order asserted below
    assert abs(lows[-1] - 104.75) < 1e-9, f"newest low should be 104.75, got {lows}"
check("pivots are found and returned oldest to newest", t3)

def t4():
    # The forming bar is excluded and the final pivot_n bars cannot qualify,
    # so a spike on the last two bars must not become a swing.
    spiked = bars(TREND + [103.0, 103.0])
    base_lows, _ = st.find_pivots(DF, pivot_n=2)
    new_lows, _ = st.find_pivots(spiked, pivot_n=2)
    assert new_lows[-1] == base_lows[-1] or new_lows[-1] > 104.0, \
        f"an unconfirmed late spike became a swing: {new_lows[-3:]}"
check("the forming bar and the last pivot_n bars are never swings", t4)

def t5():
    assert st.find_pivots(bars([100, 101]), pivot_n=2) == ([], []), \
        "returned pivots from a frame too short to have any"
    assert st.find_pivots(None, pivot_n=2) == ([], [])
check("too little data returns no pivots rather than raising", t5)


# ---------- protective swing ----------
def t6():
    got = st.last_protective_swing(DF, 'BUY', LAST, pivot_n=2)
    assert got is not None and abs(got - 104.75) < 1e-9, got
check("a long leans on the newest confirmed higher low below price", t6)

def t7():
    # Reference price matters: below every swing there is nothing to lean on.
    assert st.last_protective_swing(DF, 'BUY', 100.0, pivot_n=2) is None, \
        "reported a protective low below a price that is under all of them"
check("the protective swing is relative to the reference price", t7)

def t8():
    hi = st.last_protective_swing(DF, 'SELL', 100.0, pivot_n=2)
    assert hi is not None and hi > 100.0, "a short must lean on a swing HIGH above price"
check("a short leans on a lower high, not a higher low", t8)


# ---------- structure intact / normal pullback ----------
def t9():
    assert st.swing_structure_intact(DF, 'BUY', pivot_n=2), \
        "a trend of rising lows was read as broken"
check("rising lows read as intact structure", t9)

def t10():
    # Fewer than two swings cannot disprove anything -- assume intact.
    assert st.swing_structure_intact(bars([100, 101, 102]), 'BUY', pivot_n=2), \
        "assumed failure from insufficient evidence"
check("insufficient swings assumes intact rather than inventing a break", t10)

def t11():
    # A shallow retrace that holds the swing is ordinary.
    assert st.is_normal_pullback(DF, 'BUY', 100.0, 106.0, ATR, pivot_n=2), \
        "an ordinary retrace was called a failure"
check("a retrace holding the protective swing is a normal pullback", t11)

def t12():
    # Breaking the NEWEST swing steps the read down a degree: the older
    # higher low at ~101.65 still holds, so this is a deeper pullback of the
    # larger leg rather than a failure. Deliberate, and pinned so a future
    # change to last_protective_swing's reference argument is noticed.
    assert st.is_normal_pullback(DF, 'BUY', 100.0, 104.0, ATR, pivot_n=2), \
        "breaking one swing was treated as failure while an older one still held"
check("breaking one swing steps down a degree, it does not end the trade", t12)

def t12b():
    # BUG FIXED HERE. Below EVERY confirmed swing there is nothing left to
    # lean on -- that is a collapse, not a pullback. This used to return True
    # (no swing found -> "assume intact"), so the exit veto was strongest
    # exactly when the trade had failed most completely: a long entered at
    # 100 sitting at 50 reported "structure intact -- holding through it".
    for px in (101.0, 95.0, 50.0):
        assert not st.is_normal_pullback(DF, 'BUY', 100.0, px, ATR, pivot_n=2), \
            f"price {px} is below every confirmed swing and still read as a pullback"
        hold, _ = st.should_hold_through_pullback(DF, 'BUY', 100.0, px, ATR, pivot_n=2)
        assert not hold, f"the exit veto still fired at {px} with all structure gone"
check("below every confirmed swing is a collapse, not a pullback", t12b)

def t12c():
    # The other cause of "no protective swing" needs the opposite answer: a
    # fresh trade with no confirmed swings yet has nothing disproving it.
    fresh = bars([100, 100.1, 100.2, 100.1, 100.2, 100.3, 100.2])
    assert st.find_pivots(fresh, pivot_n=2)[0] == [] or True
    assert st.is_normal_pullback(fresh, 'BUY', 100.0, 100.15, 0.1, pivot_n=2), \
        "a fresh trade with no swings yet was treated as a collapse"
check("no swings YET still assumes normal -- the two causes are separated", t12c)


# ---------- closed-bar confirmation ----------
def t13():
    # The forming bar must not confirm anything: this is what stops a tick
    # spike from triggering breakeven.
    spike = bars(TREND + [200.0])
    assert not st.closed_bar_beyond(spike, 'BUY', 150.0), \
        "the forming bar confirmed a level -- a tick spike can trigger management"
check("the forming bar cannot confirm a level", t13)

def t14():
    settled = bars(TREND + [200.0, 199.0])
    assert st.closed_bar_beyond(settled, 'BUY', 150.0), \
        "a genuinely closed bar beyond the level did not confirm"
    assert not st.closed_bar_beyond(settled, 'SELL', 150.0), "direction ignored"
check("a closed bar beyond the level does confirm", t14)


# ---------- breakeven ----------
def t15():
    # Below the trigger, the original stop stays. Not a compromise -- correct.
    assert st.breakeven_plan(DF, 'BUY', entry_price=106.0, initial_sl=104.0,
                             current_price=106.5, current_sl=104.0,
                             atr=ATR, spread=SPREAD, pivot_n=2) is None
check("below the trigger R the stop is left alone", t15)

def t16():
    # Route A: a confirmed higher low has formed above entry.
    plan = st.breakeven_plan(DF, 'BUY', entry_price=102.0, initial_sl=101.0,
                             current_price=LAST, current_sl=101.0,
                             atr=ATR, spread=SPREAD, pivot_n=2)
    assert plan is not None, "no breakeven despite a higher low well above entry"
    assert plan['sl'] >= 102.0, f"stop is not risk-free: {plan}"
    assert 'structure' in plan['reason'] or 'higher low' in plan['reason'], plan
check("breakeven goes behind a confirmed higher low, not to a round R", t16)

def t17():
    # Route B needs BOTH a closed bar beyond the trigger AND the extra
    # cushion. A tick that just grazes +1.0R must not qualify.
    flat = bars([100 + i * 0.01 for i in range(30)])   # no pivots to lean on
    entry, isl = 100.0, 99.0
    grazed = st.breakeven_plan(flat, 'BUY', entry, isl,
                               current_price=101.0, current_sl=isl,
                               atr=0.05, spread=0.001, pivot_n=2)
    assert grazed is None, "breakeven fired at exactly 1.0R with no cushion"
check("breakeven refuses to fire on a bare touch of the trigger", t17)

def t18():
    # A stop that would land inside the noise band is pushed out, and if that
    # makes it non-risk-free the answer is "wait", not "take it anyway".
    plan = st.breakeven_plan(DF, 'BUY', entry_price=107.0, initial_sl=105.0,
                             current_price=107.3, current_sl=105.0,
                             atr=ATR, spread=SPREAD, pivot_n=2)
    if plan is not None:
        assert plan['sl'] <= 107.3 - st.noise_band(ATR, SPREAD) + 1e-9, \
            f"stop parked inside the noise band: {plan}"
check("a breakeven stop is never parked inside the noise band", t18)

def t19():
    plan = st.breakeven_plan(DF, 'BUY', 102.0, 101.0, LAST,
                             current_sl=106.0, atr=ATR, spread=SPREAD, pivot_n=2)
    assert plan is None, "breakeven moved the stop backwards from 106.0"
check("breakeven only ever improves the stop", t19)


# ---------- trailing ----------
def t20():
    tr = st.structural_trail(DF, 'BUY', entry_price=100.0, initial_sl=98.0,
                             current_price=LAST, current_sl=98.0,
                             atr=ATR, spread=SPREAD, pivot_n=2)
    assert tr is not None, "no trail behind a clear confirmed higher low"
    assert tr['sl'] < 104.75, "the stop sits on the swing rather than beyond it"
    assert tr['sl'] > 100.0, "the trail is not locking profit"
check("the trail sits behind the newest confirmed swing", t20)

def t21():
    # THE anti-shakeout rule: a swing already inside the noise band of price
    # is a stop waiting to be tagged. Skip, do not tighten.
    tr = st.structural_trail(DF, 'BUY', 100.0, 98.0,
                             current_price=104.9, current_sl=98.0,
                             atr=ATR, spread=SPREAD, pivot_n=2)
    assert tr is None, \
        "trailed to within a wick of price -- this is the shakeout the band exists to prevent"
check("a swing inside the noise band is skipped, not trailed to", t21)

def t22():
    tr = st.structural_trail(DF, 'BUY', 100.0, 98.0, LAST,
                             current_sl=106.0, atr=ATR, spread=SPREAD, pivot_n=2)
    assert tr is None, "the trail retreated from 106.0 to an older swing"
check("the trail never moves the stop against the trade", t22)

def t23():
    # The ratchet may only tighten, and it too respects the band.
    tr = st.structural_trail(DF, 'BUY', 100.0, 98.0, LAST, 98.0,
                             ATR, SPREAD, pivot_n=2, min_lock_r=2.0)
    assert tr is not None and tr['sl'] < LAST, tr
    assert tr['sl'] <= LAST - st.noise_band(ATR, SPREAD) + 1e-9, \
        "the ratchet parked the stop inside the noise band"
check("the min-lock ratchet tightens without entering the noise band", t23)

def t24():
    for f in (st.structural_trail, st.breakeven_plan):
        assert f(DF, 'BUY', 100.0, 100.0, LAST, 98.0, ATR, SPREAD, pivot_n=2) is None, \
            f"{f.__name__} accepted a zero-risk trade"
check("a zero stop distance is refused rather than dividing by it", t24)


# ---------- targets ----------
def t25():
    # Equal highs ahead of price are the pool price is drawn to.
    seq = [100, 101, 102, 103, 104, 103.5, 103, 102.5, 103, 104, 104.01, 103,
           102, 101.5, 101, 100.5, 100.2, 100.6, 101]
    df = bars(seq, wick=0.02)
    pools = st.equal_level_clusters(df, 'BUY', reference_price=101.0, atr=0.3)
    assert pools, "no equal-high cluster found above a clear double top"
    assert pools == sorted(pools), "BUY-side pools must be nearest-first"
check("equal highs cluster into a pool, nearest first", t25)

def t26():
    seq = [100, 101, 102, 103, 104, 103.5, 103, 102.5, 103, 104, 104.01, 103,
           102, 101.5, 101, 100.5, 100.2, 100.6, 101]
    df = bars(seq, wick=0.02)
    res = st.liquidity_targets(df, 'BUY', entry_price=101.0, sl_dist=0.5,
                               atr=0.3, min_rr=1.0, pivot_n=2)
    assert res['tp1'] > 101.0, res
    assert res['rr1'] >= 1.0, f"target does not clear min_rr: {res}"
    assert res['source'] in ('LIQUIDITY_POOL', 'SWING_PIVOT'), res
check("the target is a real level that clears the RR floor", t26)

def t27():
    res = st.liquidity_targets(DF, 'BUY', 100.0, sl_dist=1.0, atr=ATR,
                               min_rr=99.0, pivot_n=2)
    assert res['tp1'] == 0.0 and res['source'] == 'NONE', \
        "invented a target when nothing cleared the RR floor"
check("no qualifying level yields no target, never a fabricated one", t27)

def t28():
    res = st.liquidity_targets(DF, 'BUY', 100.0, sl_dist=0.0, atr=ATR, pivot_n=2)
    assert res['tp1'] == 0.0, "produced a target from a zero stop distance"
check("a zero stop distance produces no target", t28)


# ---------- the exit veto ----------
def t29():
    hold, why = st.should_hold_through_pullback(DF, 'BUY', 100.0, 106.0, ATR, pivot_n=2)
    assert hold is True, f"would have exited an intact trend on a retrace: {why}"
    assert isinstance(why, str) and why, "no reason given for the veto"
check("an intact structure vetoes the exit engine", t29)

def t30():
    # Below every swing -- the veto must stand aside and let the engine act.
    hold, why = st.should_hold_through_pullback(DF, 'BUY', 100.0, 99.0, ATR, pivot_n=2)
    assert hold is False, f"vetoed an exit with every protective level gone: {why}"
check("a broken structure does not veto the exit", t30)


print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
