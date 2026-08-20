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


print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
