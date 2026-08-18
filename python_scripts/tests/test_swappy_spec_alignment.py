"""
Swappy 3C vs the published spec -- the three remaining divergences.

The spec (Swappy Trading's 3C setup) asks for things the code did not do:

  #2  candle 3 must be a SHALLOW pullback -- "a healthy pause before the next
      wave". The code accepted any opposite-colour candle that closed inside
      C1's extreme, including one that gave back the whole impulse.
  #3  the stop belongs "beyond the invalidation wick/level of the 3-candle
      structure". compute_swappy_sl() scanned the last FIFTEEN bars, whose
      extreme is by definition at or beyond the 3-candle one and usually well
      beyond it -- inflating risk distance AND, since find_swappy_structural_tp
      takes sl_dist as input, pushing the target out of reach too.
  #4  a REVERSAL variant (impulse -> indecision -> confirmation) that did not
      exist in any form.

(#1, the body filter, is covered in test_swappy_closed_candle.py.)
"""
import pathlib as _pl
import sys
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))

import pandas as pd

passed = failed = 0
def check(name, fn):
    global passed, failed
    try:
        fn(); passed += 1; print(f"  PASS  {name}")
    except AssertionError as e:
        failed += 1; print(f"  FAIL  {name}: {e}")
    except Exception as e:
        failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")

from backtest.bot_loader import import_bot_module
bot = import_bot_module()

ROOT = _pl.Path(__file__).resolve().parent.parent
SRC = open(ROOT / 'hybrid_trading_bot_multiuser.py', encoding='utf-8').read()


def _bars(rows):
    t0 = pd.Timestamp('2026-08-18 12:00:00')
    return pd.DataFrame({
        'time':  [t0 + pd.Timedelta(minutes=5 * i) for i in range(len(rows))],
        'open':  [r[0] for r in rows], 'high': [r[1] for r in rows],
        'low':   [r[2] for r in rows], 'close': [r[3] for r in rows],
        'tick_volume': [100] * len(rows),
    })

PAD = [(100.0, 100.2, 99.8, 100.0)] * 20
# Bear continuation: two red legs, then a green pullback.
C1 = (100.00, 100.02, 99.22, 99.30)
C2 = ( 99.30,  99.32, 98.52, 98.60)
C3_SHALLOW = (98.60, 98.90, 98.55, 98.85)   # body 0.25, retraces ~18% of impulse
# Deep pullback: still green, still closes below C1's high, but gives back
# most of the move. Passed the old filter; must not pass now.
C3_DEEP    = (98.60, 99.95, 98.55, 99.90)   # body 1.30 > both impulse legs


# ---------- #2 shallow C3 ----------
def t1():
    r = bot.detect_swappy_3c(_bars(PAD + [C1, C2, C3_SHALLOW]), 'SELL')
    assert r['confirmed'], f"shallow pullback rejected: {r.get('reason')}"
check("a shallow C3 still confirms", t1)


def t2():
    r = bot.detect_swappy_3c(_bars(PAD + [C1, C2, C3_DEEP]), 'SELL')
    assert not r['confirmed'], \
        "a pullback bigger than the impulse was accepted as a 'healthy pause'"
check("a pullback larger than the impulse is refused", t2)


def t3():
    # The rule is a proportion, not a constant: the SAME C3 must be judged
    # against the impulse it interrupts. Shrink the impulse legs and the once
    # shallow pullback is no longer shallow.
    small_c1 = (100.00, 100.01, 99.88, 99.90)   # body 0.10
    small_c2 = ( 99.90,  99.91, 99.78, 99.80)   # body 0.10
    c3       = ( 99.80,  99.98, 99.79, 99.95)   # body 0.15 -- now BIGGER than either leg
    r = bot.detect_swappy_3c(_bars(PAD + [small_c1, small_c2, c3]), 'SELL')
    assert not r['confirmed'], \
        "C3 was judged against a fixed size rather than against the impulse"
check("'shallow' is measured against the impulse, not a fixed size", t3)


def t4():
    assert 'SWAPPY_REQUIRE_SHALLOW_C3' in SRC, "no flag to A/B the new filter"
    i = SRC.find('c3_shallow = ')
    assert i > 0 and 'not config.SWAPPY_REQUIRE_SHALLOW_C3' in SRC[i:i + 200], \
        "the flag does not actually disable the check"
check("the shallow-C3 requirement is behind a flag that really disables it", t4)


# ---------- #3 stop on the 3-candle structure ----------
def t5():
    # A far lower low 10 bars back must NOT drag the stop down with it.
    deep = list(PAD)
    deep[10] = (100.0, 100.2, 95.00, 100.0)     # an old spike, far outside the setup
    df = _bars(deep + [C1, C2, C3_SHALLOW])
    sl = bot.compute_swappy_sl(df, 'BUY', atr_m5=0.10)
    three_candle_low = min(C1[2], C2[2], C3_SHALLOW[2])
    assert sl > 96.0, \
        f"stop {sl:.4f} was dragged to an old spike -- still scanning >3 bars"
    assert sl < three_candle_low, \
        f"stop {sl:.4f} must sit BEYOND the 3-candle low {three_candle_low:.4f}"
check("the stop sits on the 3-candle structure, not a 15-bar window", t5)


def t6():
    df = _bars(PAD + [C1, C2, C3_SHALLOW])
    sl_buy  = bot.compute_swappy_sl(df, 'BUY',  atr_m5=0.10)
    sl_sell = bot.compute_swappy_sl(df, 'SELL', atr_m5=0.10)
    lo = min(C1[2], C2[2], C3_SHALLOW[2])
    hi = max(C1[1], C2[1], C3_SHALLOW[1])
    assert sl_buy < lo and sl_sell > hi, \
        "the stop must be beyond the structure, never inside it"
check("both directions place the stop outside the structure", t6)


def t7():
    # The ATR floor exists so three tight candles cannot produce a stop
    # distance near zero, which would ask for an enormous lot.
    tight = [(100.000, 100.002, 99.998, 100.001)] * 3
    df = _bars(PAD + tight)
    atr = 1.0
    sl = bot.compute_swappy_sl(df, 'BUY', atr_m5=atr)
    lo = 99.998
    assert (lo - sl) >= atr * bot.SWAPPY_MIN_SL_ATR - 1e-9, \
        f"stop distance {lo - sl:.5f} is below the {bot.SWAPPY_MIN_SL_ATR} ATR floor"
check("a degenerate 3-candle structure is widened to the ATR floor", t7)


def t8():
    # Live and backtest must measure the SAME three candles as the pattern.
    forming = (98.85, 98.95, 98.75, 98.80)
    closed_df  = _bars(PAD + [C1, C2, C3_SHALLOW])
    forming_df = _bars(PAD + [C1, C2, C3_SHALLOW, forming])
    a = bot.compute_swappy_sl(closed_df,  'BUY', 0.10)
    b = bot.compute_swappy_sl(forming_df, 'BUY', 0.10, last_bar_closed=False)
    assert abs(a - b) < 1e-9, \
        f"stop differs between live and backtest framing: {a} vs {b}"
    i = SRC.find('_sl_sw = compute_swappy_sl(')
    assert i > 0 and 'last_bar_closed=False' in SRC[i:i + 250], \
        "the live call site computes the stop from a forming bar"
check("the stop is computed from the same candles the pattern matched", t8)


# ---------- #4 the reversal variant ----------
# Bull reversal: strong red impulse, doji stall, strong green confirmation
# closing past C1's midpoint (99.62).
R1 = (100.00, 100.02, 99.22, 99.30)   # red impulse, body 0.70 of 0.80
R2 = ( 99.30,  99.40, 99.20, 99.28)   # doji, body 0.02 of 0.20
R3 = ( 99.28,  99.85, 99.26, 99.80)   # green, closes 99.80 > mid 99.62


def t9():
    r = bot.detect_swappy_reversal(_bars(PAD + [R1, R2, R3]), 'BUY')
    assert r['confirmed'], f"textbook reversal rejected: {r.get('reason')}"
    assert r['order_type'] == 'MARKET', \
        "C3 IS the confirmation -- there is nothing left to rest an order for"
check("the reversal variant exists and confirms on the spec's shape", t9)


def t10():
    # C2 must be indecision. Replace the doji with a full-bodied candle and
    # the pattern is a continuation, not a stall.
    r2_strong = (99.30, 99.32, 98.52, 98.60)
    r = bot.detect_swappy_reversal(_bars(PAD + [R1, r2_strong, R3]), 'BUY')
    assert not r['confirmed'], "a full-bodied C2 passed as 'indecision'"
check("C2 must actually be an indecision candle", t10)


def t11():
    # C3 must close PAST C1's midpoint. One tick short is not confirmation.
    mid = (R1[2] + R1[1]) / 2
    r3_short = (99.28, 99.60, 99.26, mid - 0.01)
    r = bot.detect_swappy_reversal(_bars(PAD + [R1, R2, r3_short]), 'BUY')
    assert not r['confirmed'], \
        "C3 closing short of C1's midpoint was accepted as 'control changed'"
check("C3 must close past C1's midpoint", t11)


def t12():
    # Direction is the TRADE's, so C1 is checked for the OPPOSITE. Asking for
    # a SELL on a setup whose impulse is already down must find nothing --
    # otherwise the function detects continuations and calls them reversals.
    r = bot.detect_swappy_reversal(_bars(PAD + [R1, R2, R3]), 'SELL')
    assert not r['confirmed'], \
        "a bullish reversal was also reported as a SELL -- direction is inverted"
check("the reversal trades against C1, not with it", t12)


def t13():
    # Off by default: a brand-new entry path must not start trading on its own.
    assert 'ENABLE_SWAPPY_REVERSAL: bool = False' in SRC, \
        "the untested reversal variant is enabled by default"
    i = SRC.find("getattr(config, 'ENABLE_SWAPPY_REVERSAL'")
    assert i > 0, "the live call site does not consult the flag"
    assert "ENABLE_SWAPPY_REVERSAL', False)" in SRC[i:i + 80], \
        "the getattr default is not False -- an older config would enable it"
check("the reversal is OFF by default, including for an older config object", t13)


def t14():
    # It must go through the shared pipeline. Every Swappy bug so far came
    # from self-executing past the ban / lesson / same-candle guards.
    i = SRC.find('STRATEGY B2: SWAPPY 3C REVERSAL')
    assert i > 0, "the reversal is not wired into the live loop"
    block = SRC[i:i + 3200]
    assert "setup = {" in block, "the reversal does not build a shared setup dict"
    assert 'place_' not in block and 'order_send' not in block, \
        "the reversal places its own order instead of using the shared pipeline"
check("the reversal routes through the shared pipeline, never self-executes", t14)


def t15():
    reg = open(ROOT / 'backtest' / 'strategies_registry.py', encoding='utf-8').read()
    assert '_adapt_swappy_reversal' in reg, "not backtestable"
    assert 'StrategyAdapter("SWAPPY_REVERSAL", False,' in reg, \
        "registered as live=True while the live flag defaults False"
    # CODE, not raw text: the adapter's own comment explains why it omits
    # last_bar_closed, and a substring search would trip over the explanation.
    import io, tokenize
    code = [(t.start[0], t.string)
            for t in tokenize.generate_tokens(io.StringIO(reg).readline)
            if t.type not in (tokenize.COMMENT, tokenize.STRING)]
    starts = [ln for ln, txt in code if txt == '_adapt_swappy_reversal']
    assert starts, "adapter not found in code"
    start = min(starts)
    body = [txt for ln, txt in code if start <= ln <= start + 60]
    assert 'last_bar_closed' not in body, \
        "the backtest must use the default -- window() is already closed-only"
check("the reversal is registered for backtesting, marked not-live", t15)


print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
