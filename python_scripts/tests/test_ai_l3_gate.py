"""
An AI that says NOTHING must not look like an AI that says "marginal, skip".

Live symptom: dozens of SSM setups per minute, every one logged as
  [AI L3] ... score=5/10 approved=False | No reason given
and no trade ever placed. That line is not a verdict -- it is what the
.get() defaults produce when the response cannot be parsed (score default 5,
approved default score>=7 == False, reason default "No reason given").

These tests pin the distinction, on the pure parsing/defaulting logic.
"""
import pathlib as _pl
import sys
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))

passed = failed = 0
def check(name, fn):
    global passed, failed
    try:
        fn(); passed += 1; print(f"  PASS  {name}")
    except AssertionError as e:
        failed += 1; print(f"  FAIL  {name}: {e}")
    except Exception as e:
        failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")

def usable(result):
    """The guard now in ai_validate_trade."""
    return isinstance(result, dict) and 'score' in result and 'reason' in result

def legacy_verdict(result):
    """What the old code produced for any parse result."""
    score = int(result.get('score', 5))
    return {'score': score,
            'approved': bool(result.get('approved', score >= 7)),
            'reason': str(result.get('reason', 'No reason given'))}

# ---- 1. The exact live signature comes from an EMPTY parse.
def t1():
    v = legacy_verdict({})
    assert v == {'score': 5, 'approved': False, 'reason': 'No reason given'}, v
    assert not usable({}), "empty parse must not be treated as an answer"
check("empty parse reproduces 'score=5/10 approved=False | No reason given'", t1)

# ---- 2. Truncated / non-JSON replies are all 'no answer'.
def t2():
    for bad in ({}, {'score': 5}, {'approved': False}, {'risk_modifier': 1.0}):
        assert not usable(bad), f"{bad} wrongly treated as a verdict"
check("partial replies (no reason / no score) are not verdicts", t2)

# ---- 3. A REAL marginal rejection is still honoured.
def t3():
    real = {'score': 5, 'approved': False, 'reason': 'M5 shows no displacement after the sweep'}
    assert usable(real), "a genuine rejection was discarded"
    v = legacy_verdict(real)
    assert v['approved'] is False and v['score'] == 5
check("a real 'marginal, skip' verdict still rejects the trade", t3)

# ---- 4. A real approval still passes.
def t4():
    real = {'score': 8, 'approved': True, 'reason': 'clean sweep + FVG retest at HTF OB'}
    assert usable(real)
    v = legacy_verdict(real)
    assert v['approved'] is True and v['score'] == 8
check("a real approval still approves", t4)

# ---- 5. approved must never be inferred as True from a missing field.
def t5():
    v = legacy_verdict({'score': 9})           # no explicit 'approved'
    assert v['approved'] is True, "score>=7 should imply approval when stated"
    v2 = legacy_verdict({})                     # nothing at all
    assert v2['approved'] is False, "an absent response must never approve"
check("an absent response can never approve a trade", t5)

# ---- 6. The token budget must fit a reasoning model's overhead.
def t6():
    src = open(_pl.Path(__file__).resolve().parent.parent /
               'hybrid_trading_bot_multiuser.py', encoding='utf-8').read()
    i = src.find('You are a professional ICT scalping analyst')
    seg = src[i:i + 4000]
    assert 'max_tokens=800' in seg, "L3 validator token budget not raised"
    assert 'max_tokens=200' not in seg, "old 200-token cap still present"
check("L3 token budget raised above the reasoning-overhead cliff", t6)

# ---- 7. The guard is actually wired into the live function.
def t7():
    src = open(_pl.Path(__file__).resolve().parent.parent /
               'hybrid_trading_bot_multiuser.py', encoding='utf-8').read()
    assert "'score' not in result or 'reason' not in result" in src
    assert "_l3_bias_fallback(symbol, direction, 'AI returned no usable JSON')" in src
check("unusable responses degrade to the fail-closed L1 fallback", t7)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
