"""
The stop must never sit frozen while price runs.

Every strategy had the same shape: structural breakeven, then a GAP, then a
trail. The gap was different in each and justified in none.

    generic   breakeven at 1.0R, trail from 1.5R   -> 0.5R frozen
    Swappy    breakeven at 1.0R, trail from 3.0R   -> 2.0R frozen
    AOX       breakeven at 1.0R, then nothing      -> frozen forever

Those thresholds were leftovers from the arithmetic ladder this replaced,
where "stage 2" meant lock 50% of open gains and genuinely needed a trigger.
A structural trail needs no trigger: the rule is "keep the stop behind the
newest confirmed swing", and there is no market reason to stop doing that
for half an R and then start again.

It cost a real trade. ETHUSD on 2026-08-20: breakeven at ~1.0R put the stop
behind a swing at 2281.04 (+0.30R), price ran to 1.14R and never reached
1.5R, so the trail never engaged. Higher lows formed above 2281 with nothing
following them, and the retrace took the frozen stop -- +$0.95 out of a
+$3.65 peak.

What is NOT changed here, deliberately: no threshold was retuned and no new
number invented. Thresholds with a market justification (the noise band, the
ratchet floors) are untouched; only the arbitrary activation gates are gone.
"""
import pathlib as _pl
import sys
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))

import io
import re
import tokenize

passed = failed = 0
def check(name, fn):
    global passed, failed
    try:
        fn(); passed += 1; print(f"  PASS  {name}")
    except AssertionError as e:
        failed += 1; print(f"  FAIL  {name}: {e}")
    except Exception as e:
        failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")

ROOT = _pl.Path(__file__).resolve().parent.parent
SRC = open(ROOT / 'hybrid_trading_bot_multiuser.py', encoding='utf-8').read()

_i = SRC.find('def manage_all_positions')
_j = SRC.find('\ndef update_closed_trades')
MGMT = SRC[_i:_j]

# Code with comments and docstrings removed, so a search cannot be satisfied
# by prose describing the very thing that was deleted. Spaces around "." are
# collapsed because the token join would otherwise turn `state.be_moved` into
# `state . be_moved` and quietly fail every attribute-access assertion.
CODE = re.sub(
    r"\s*\.\s*", ".",
    " ".join(t.string for t in tokenize.generate_tokens(io.StringIO(MGMT).readline)
             if t.type not in (tokenize.COMMENT, tokenize.STRING)))


def t1():
    # No trail branch may carry an R-threshold gate any more.
    for gate in ('r_multiple >= 1.5 and ticket in state.be_moved',
                 'r_multiple >= 3.0 and ticket in state.be_moved'):
        assert gate not in CODE, f"the trail is still gated behind `{gate}`"
check("no trail branch waits for an R threshold before engaging", t1)

def t2():
    assert CODE.count('elif ticket in state.be_moved') >= 3, (
        "not every strategy path trails once risk is off -- expected the "
        "generic, Swappy and AOX branches")
check("generic, Swappy and AOX all trail from the moment risk is off", t2)

def t3():
    # AOX had no trail at all.
    i = MGMT.find("if _strategy_type == 'AOX':")
    body = MGMT[i:i + 1600]
    assert '_try_structural_trail' in body, "AOX still has no trail"
    assert 'elif ticket in state.be_moved' in body, "AOX's trail is conditional again"
check("AOX trails instead of sitting at its breakeven stop", t3)

def t4():
    # ...but AOX's TARGET is its plan and must stay untouched. A trail that
    # pulled the SD level in would be changing the strategy, not protecting it.
    i = MGMT.find("if _strategy_type == 'AOX':")
    body = MGMT[i:i + 1600]
    j = body.find("_try_structural_trail('AOX'")
    assert j > 0, "AOX trail call not found"
    call = body[j:body.find(')', j) + 1]
    assert '_tp_override' not in call, \
        "the AOX trail overrides its take-profit -- the SD levels are the plan"
check("the AOX trail never touches its SD target", t4)

def t5():
    i = MGMT.find("if _strategy_type == 'SWAPPY':")
    body = MGMT[i:i + 1800]
    assert '_min_lock_r=2.0' not in body, \
        "Swappy still asks for a flat 2R lock -- below 2R that is a stop above price"
    assert '_lock_floor_for(r_multiple)' in body, "Swappy does not use the shared ratchet"
check("Swappy uses the shared ratchet, not a flat 2R floor", t5)

def t6():
    # The ratchet itself must be unchanged -- this was a structural fix, not
    # a retune, and silently moving these would be exactly the kind of
    # invented tuning that has no evidence behind it.
    i = MGMT.find('def _lock_floor_for')
    body = MGMT[i:i + 1600]
    for r, floor in (('4.0', '2.0'), ('3.0', '1.0'), ('2.0', '0.5')):
        assert f'>= {r}' in body and f'return {floor}' in body, \
            f"the {r}R ratchet floor of {floor}R changed"
    assert 'return 0.0' in body, "the below-2R case no longer returns a zero floor"
check("the ratchet floors are unchanged at 0.5R / 1.0R / 2.0R", t6)

def t7():
    # One definition, three callers -- three copies would drift.
    assert MGMT.count('def _lock_floor_for') == 1, "the ratchet is defined more than once"
    assert MGMT.count('_lock_floor_for(r_multiple)') >= 3, \
        "not every path uses the shared ratchet"
check("one ratchet definition, used by every path", t7)

def t8():
    # Breakeven must still gate the trail: trailing a stop that is still
    # below entry would tighten a losing trade toward its own stop.
    for marker in ('elif ticket in state.be_moved',):
        assert marker in CODE, "the trail no longer requires risk to be off first"
    assert 'r_multiple >= config.BREAKEVEN_TRIGGER_RR' in CODE or \
           'BREAKEVEN_TRIGGER_RR' in CODE, "the breakeven trigger vanished"
check("the trail still requires breakeven first -- it cannot tighten a loser", t8)

def t9():
    # The noise band is the anti-shakeout rule and lives in structure_tools;
    # making the trail continuous only matters if that still holds.
    import structure_tools as st
    assert st.noise_band(1.0, 0.0) > 0, "the noise band collapsed"
    band = st.noise_band(1.0, 0.02)
    assert band >= 0.75, "the ATR term of the noise band changed"
check("the noise band still protects a continuously-trailing stop", t9)


def t10():
    # A declining trail must say WHY. structural_trail returns None for three
    # different correct reasons and used to report none of them, so "my stop
    # is not trailing" was unanswerable from the log.
    import structure_tools as st
    import pandas as pd

    def bars(cl, w=0.15):
        return pd.DataFrame([(c - .05, c + w, c - w, c) for c in cl],
                            columns=['open', 'high', 'low', 'close'])

    trend = ([100, 100.6, 101.2, 101.9, 102.6, 103.3]
             + [102.9, 102.3, 101.8, 102.0]
             + [102.8, 103.6, 104.4, 105.1, 105.8]
             + [105.4, 104.9, 105.3]
             + [105.9, 106.6, 107.2, 107.8])
    df = bars(trend)

    # (a) swing too close to price -> the noise-band answer, the one that
    #     looks like a bug and is not
    why = st.trail_status(df, 'BUY', 100.0, 98.0, 104.9, 98.0,
                          atr=0.55, spread=0.02, pivot_n=2)
    assert 'noise band' in why, f"noise-band case not explained: {why}"

    # (b) stop already better than the swing would give
    why2 = st.trail_status(df, 'BUY', 100.0, 98.0, 107.8, 106.0,
                           atr=0.55, spread=0.02, pivot_n=2)
    assert 'no better' in why2, f"no-improvement case not explained: {why2}"

    # (c) nothing confirmed yet
    flat = bars([100 + i * 0.5 for i in range(25)])
    why3 = st.trail_status(flat, 'BUY', 100.0, 98.0, 112.0, 98.0,
                           atr=0.55, spread=0.02, pivot_n=2)
    assert 'no confirmed swing' in why3, f"no-swing case not explained: {why3}"

    # (d) and when it WOULD move, it says where
    why4 = st.trail_status(df, 'BUY', 100.0, 98.0, 107.8, 98.0,
                           atr=0.55, spread=0.02, pivot_n=2)
    assert 'would trail to' in why4, f"the positive case is not explained: {why4}"
check("a trail that declines explains which of the three reasons applies", t10)

def t11():
    # Diagnostic only -- it must never be able to change what the bot does.
    # Scope precisely to the declining branch: from `if not _tr:` to the
    # `return False` that ends it. A fixed character window would either miss
    # the return or spill into the success path below it.
    i = MGMT.find('if not _tr:')
    assert i > 0, "the declining branch vanished"
    end = MGMT.find('return False', i)
    assert end > i, "the declining branch no longer returns False"
    branch = MGMT[i:end]
    assert 'st.trail_status' in branch, "the explanation is not in the declining branch"
    assert 'modify_position' not in branch, "the diagnostic path can move a stop"
    assert 'order_send' not in branch, "the diagnostic path can place an order"
check("the explanation is logging only, never a decision", t11)

def t12():
    # Throttled: this runs every management cycle and the answer only changes
    # when structure does.
    i = MGMT.find('_trail_why_')
    assert i > 0, "the explanation is not throttled per position"
    assert '> 120' in MGMT[i:i + 300], "no throttle interval"
check("the explanation is throttled per position, not once per cycle", t12)


print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
