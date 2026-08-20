"""
Three questions from a live log, three different causes.

  "Modify failed ... No changes" repeating three times per cycle
  "why do I only see SSM in the logs?"
  "why does every Telegram alert say SSM?"

None of them was the thing it looked like.

  1. structural_trail tested "is this an improvement?" on the UNROUNDED
     candidate and then rounded the result. A stop better by less than half
     a tick passed the test and rounded straight back onto the current SL,
     so the bot asked MT5 to change a stop to its existing value. MT5 said
     No changes; modify_position treated that as failure and retried twice
     more, 0.5s apart.
  2. Shaakuni SSM logged every successful detection at INFO, and detection
     runs about twice a second. One unfilled setup wrote ~7,000 identical
     lines an hour. Every other strategy logs detections at DEBUG.
  3. Swappy and AOX place orders through their own mt5.order_send and never
     touched place_ai_trade's Telegram alert -- so every "TRADE OPENED"
     message ever sent came from the shared pipeline, where SSM dominates.
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

ROOT = _pl.Path(__file__).resolve().parent.parent
SRC = open(ROOT / 'hybrid_trading_bot_multiuser.py', encoding='utf-8').read()


def bars(closes, wick=0.15):
    return pd.DataFrame([(c - 0.05, c + wick, c - wick, c) for c in closes],
                        columns=['open', 'high', 'low', 'close'])

TREND = ([100, 100.6, 101.2, 101.9, 102.6, 103.3]
         + [102.9, 102.3, 101.8, 102.0]
         + [102.8, 103.6, 104.4, 105.1, 105.8]
         + [105.4, 104.9, 105.3]
         + [105.9, 106.6, 107.2, 107.8])
DF = bars(TREND)


# ---------- 1. the no-op modify ----------
def t1():
    # Reproduces the live line: SL 0.71231 -> 0.71231. Set the current stop to
    # exactly what the trail would round to; it must decline, not propose the
    # same number back.
    tr = st.structural_trail(DF, 'BUY', 100.0, 98.0, 107.8, 98.0,
                             atr=0.55, spread=0.02, pivot_n=2, digits=5)
    assert tr, "fixture produced no trail at all"
    same = st.structural_trail(DF, 'BUY', 100.0, 98.0, 107.8, tr['sl'],
                               atr=0.55, spread=0.02, pivot_n=2, digits=5)
    assert same is None, \
        f"proposed {same['sl']} when the stop is already there -- MT5 answers 'No changes'"
check("the trail declines to re-propose the stop it already set", t1)

def t2():
    # A sub-tick improvement must not survive rounding into a no-op.
    tr = st.structural_trail(DF, 'BUY', 100.0, 98.0, 107.8, 98.0,
                             atr=0.55, spread=0.02, pivot_n=2, digits=5)
    nudged = tr['sl'] - 0.000001          # better, but far below tick resolution
    again = st.structural_trail(DF, 'BUY', 100.0, 98.0, 107.8, nudged,
                                atr=0.55, spread=0.02, pivot_n=2, digits=5)
    if again is not None:
        assert round(again['sl'], 5) != round(nudged, 5), \
            "a sub-tick 'improvement' still rounds onto the current stop"
check("improvement is judged at tick resolution, not raw float", t2)

def t3():
    tr = st.breakeven_plan(DF, 'BUY', 102.0, 101.0, 107.8, 101.0,
                           atr=0.55, spread=0.02, pivot_n=2, digits=5)
    assert tr, "fixture produced no breakeven plan"
    same = st.breakeven_plan(DF, 'BUY', 102.0, 101.0, 107.8, tr['sl'],
                             atr=0.55, spread=0.02, pivot_n=2, digits=5)
    assert same is None, "breakeven re-proposes a stop already in place"
check("breakeven has the same tick-resolution guard", t3)

def t4():
    # Belt and braces at the MT5 boundary: "no changes" IS the desired end
    # state, so it must not burn three retries and 1.5s of sleep.
    i = SRC.find('def modify_position')
    body = SRC[i:i + 2200]
    assert 'TRADE_RETCODE_NO_CHANGES' in body, \
        "a no-op modify is still treated as a failure and retried"
    # The retcode is captured into a local once, so the COMPARISON is what to
    # look for -- not a second mention of the MT5 constant, which does not
    # appear again.
    j = body.find('== _NO_CHANGES')
    assert j > 0, "the no-changes retcode is defined but never compared against"
    assert 'return True' in body[j:j + 300], "no-changes does not return success"
    assert body.find('return True', j) < body.find('logger.warning', j), \
        "no-changes still falls through to the warn-and-retry path"
check("MT5's 'no changes' counts as success, not a retryable failure", t4)


# ---------- 2. the log flood ----------
def t5():
    i = SRC.find("[SSM] {symbol} {direction}: HTF sweep confirmed")
    assert i > 0, "the SSM detection log vanished"
    body = SRC[max(0, i - 1400):i]
    assert '_ssm_logged' in body, "SSM still logs every detection at INFO"
    assert 'logger.debug' in body, "there is no debug path for a repeated detection"
check("a re-detected SSM setup drops to DEBUG instead of repeating at INFO", t5)

def t6():
    # A NEW setup must still announce itself -- the throttle keys on the OB
    # level, so a different level is news.
    i = SRC.find('_ssm_key = (symbol, direction')
    assert i > 0, "the throttle is not keyed on the setup"
    line = SRC[i:SRC.find('\n', i)]
    assert "ob['entry']" in line, \
        "the key ignores the OB level, so a genuinely new setup would be silenced"
check("a new setup at a new level still logs immediately", t6)


# ---------- 3. the missing alerts ----------
def _fn_body(name):
    i = SRC.find(f'def {name}')
    assert i > 0, f'{name} not found'
    j = SRC.find('\ndef ', i + 10)
    return SRC[i:j if j > 0 else len(SRC)]

def t7():
    body = _fn_body('execute_aox_layer')
    assert body.count('mt5.order_send') >= 1, "fixture assumption broken"
    assert 'send_telegram_notification' in body, \
        "AOX still places orders with no alert -- a 25/25/50 scale-in in silence"
check("AOX announces each layer it fills", t7)

def t8():
    body = _fn_body('check_swappy_expirations')
    assert 'send_telegram_notification' in body, \
        "a Swappy pending order can still fill with no alert at all"
    i = body.find('send_telegram_notification')
    assert 'SWAPPY_3C' in body[i:i + 600], "the Swappy fill alert does not name the strategy"
check("a Swappy pending order that FILLS is announced", t8)

def t9():
    i = SRC.find('PENDING ORDER PLACED')
    assert i > 0, "a resting Swappy order is placed with no notification"
    assert 'SWAPPY_3C' in SRC[i:i + 500], "the placement alert does not name the strategy"
check("a resting Swappy order is announced when placed", t9)

def t10():
    # Every alert must name its own strategy rather than inheriting a default.
    i = SRC.find('Strategy: {local_signal.get(')
    assert i > 0, "the shared pipeline's alert lost its strategy field"
    line = SRC[i:SRC.find('\n', i)]
    assert "'setup_type'" in line, "the shared alert no longer reads the per-strategy reason"
    # and the self-executing paths hardcode theirs, since they never build a
    # local_signal at all
    for name in ('SWAPPY_3C', 'AOX'):
        assert f'Strategy: {name}' in SRC or f'Strategy: {name} (' in SRC, \
            f"{name} alerts do not name {name}"
check("every alert names the strategy that actually placed the trade", t10)


print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
