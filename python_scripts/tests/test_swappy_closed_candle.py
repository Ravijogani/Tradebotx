"""
Swappy 3C read a candle that had not finished yet.

detect_swappy_3c() took c3 = df.iloc[-1], and the live loop feeds
copy_rates_from_pos(symbol, tf, 0, N) -- bar 0 is the bar still forming. So
"C3 pulled back and failed to break C1" was being asserted about a candle
that could still become anything. Two consequences:

  1. the claim re-answered on every ~5s scan for five minutes, which is how
     one USDCADm setup became ~25 identical stop orders on 2026-08-18;
  2. the backtest's dataset.window() returns rows strictly BEFORE as_of, so
     it had always used a CLOSED c3 -- live and backtest were never grading
     the same pattern.

These check the drop happens, that it is a no-op for the backtest, and that
one setup candle can only produce one order.
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
    """rows: list of (open, high, low, close). Timestamps 5 min apart."""
    t0 = pd.Timestamp('2026-08-18 12:00:00')
    return pd.DataFrame({
        'time':  [t0 + pd.Timedelta(minutes=5 * i) for i in range(len(rows))],
        'open':  [r[0] for r in rows], 'high': [r[1] for r in rows],
        'low':   [r[2] for r in rows], 'close': [r[3] for r in rows],
        'tick_volume': [100] * len(rows),
    })


# A clean SWAPPY_BEAR: two red legs with ~75% bodies, then a green pullback
# that holds below C1's high. Padding bars keep the 20-bar body average and
# the >=5-row length requirement satisfied.
PAD = [(100.0, 100.2, 99.8, 100.0)] * 20
C1  = (100.0, 100.05, 99.20, 99.35)     # red, body 0.65 of 0.85 range = 76%
C2  = ( 99.35,  99.40, 98.55, 98.70)    # red, same shape, lower high
C3  = ( 98.70,  98.95, 98.65, 98.90)    # green pullback, closes below C1 high
FORMING = (98.90, 99.00, 98.80, 98.85)  # the unfinished bar


def t1():
    df = _bars(PAD + [C1, C2, C3])
    r = bot.detect_swappy_3c(df, 'SELL')
    assert r['confirmed'], f"fixture is not a valid setup: {r.get('reason')}"
check("fixture: closed-bar frame produces a confirmed SWAPPY_BEAR", t1)


def t2():
    # Same three candles, but now a forming bar sits after them. With
    # last_bar_closed=False the forming bar must be dropped and the result
    # must be IDENTICAL to the closed-only frame.
    closed  = bot.detect_swappy_3c(_bars(PAD + [C1, C2, C3]), 'SELL')
    forming = bot.detect_swappy_3c(_bars(PAD + [C1, C2, C3, FORMING]), 'SELL',
                                   last_bar_closed=False)
    assert forming['confirmed'], "dropping the forming bar lost the setup"
    for k in ('pattern', 'stop_entry', 'setup_high', 'setup_low'):
        assert forming[k] == closed[k], \
            f"{k} differs: forming={forming[k]} closed={closed[k]}"
check("last_bar_closed=False drops the forming bar and reproduces the setup", t2)


def t3():
    # The bug itself: WITHOUT the flag the forming bar is treated as C3, so
    # the pattern is read one candle late and the levels are wrong.
    wrong = bot.detect_swappy_3c(_bars(PAD + [C1, C2, C3, FORMING]), 'SELL')
    right = bot.detect_swappy_3c(_bars(PAD + [C1, C2, C3]), 'SELL')
    assert not wrong['confirmed'] or wrong['stop_entry'] != right['stop_entry'], \
        "including the forming bar produced the same answer -- fixture cannot " \
        "distinguish the bug, so this test proves nothing"
check("including a forming bar really does change the answer", t3)


def t4():
    # Default must stay True so the backtest adapter, which already feeds
    # closed bars only (dataset.window returns rows strictly before as_of),
    # is not shifted a second time.
    assert 'last_bar_closed: bool = True' in SRC, "default is not closed-bars"
    reg = open(ROOT / 'backtest' / 'strategies_registry.py', encoding='utf-8').read()
    i = reg.find('bot.detect_swappy_3c(')
    assert i > 0, "backtest adapter no longer calls detect_swappy_3c"
    assert 'last_bar_closed' not in reg[i:i + 200], \
        "backtest must rely on the default -- window() is already closed-only"
check("default is closed-bars, so the backtest is not double-shifted", t4)


def t5():
    i = SRC.find('_sw = detect_swappy_3c(')
    assert i > 0, "live call site not found"
    assert 'last_bar_closed=False' in SRC[i:i + 300], \
        "the LIVE call site still treats its forming bar as closed"
check("the live call site declares its last bar unfinished", t5)


def t6():
    for pat in ('setup_candle_time', 'state.swappy_last_setup'):
        assert pat in SRC, f"{pat} missing -- no per-candle latch"
    i = SRC.find('_sw_repeat = (')
    assert i > 0, "no repeat check"
    assert 'state.swappy_last_setup[symbol] = _sw_ct' in SRC, \
        "the latch is never armed after a successful placement"
check("one order per setup candle: the latch exists and is armed on placement", t6)


def t7():
    # The latch must not `continue` -- Swappy being done with this symbol is
    # no reason to deny AOX its turn for the rest of the candle.
    #
    # Searched over CODE, not raw text: the comment on that very branch
    # contains the word "continue", and a raw substring search would fail on
    # the prose explaining the fix rather than on the fix.
    import io, tokenize
    code_only = [(tok.start[0], tok.string)
                 for tok in tokenize.generate_tokens(io.StringIO(SRC).readline)
                 if tok.type not in (tokenize.COMMENT, tokenize.STRING)]

    lines = [ln for ln, txt in code_only if txt == '_sw_repeat']
    assert lines, "repeat check not found in code (only in comments?)"
    start = min(lines)
    branch = [txt for ln, txt in code_only if start <= ln <= start + 20]
    assert 'continue' not in branch, \
        "the latch short-circuits the whole symbol instead of just Swappy"
check("the latch skips Swappy only, not the strategies below it", t7)


def t8():
    # The latch is keyed on the setup candle, so a NEW candle is free to
    # produce its own order -- otherwise this would be a one-trade-ever guard.
    a = bot.detect_swappy_3c(_bars(PAD + [C1, C2, C3]), 'SELL')
    b = bot.detect_swappy_3c(_bars(PAD + [C1, C2, C3, FORMING]), 'SELL',
                             last_bar_closed=False)
    assert a['setup_candle_time'] == b['setup_candle_time'], \
        "same C3 must carry the same timestamp regardless of the forming bar"
    later = _bars(PAD + [C1, C2, C3])
    later['time'] = later['time'] + pd.Timedelta(minutes=5)
    c = bot.detect_swappy_3c(later, 'SELL')
    assert c['setup_candle_time'] != a['setup_candle_time'], \
        "a different candle must get a different latch key"
check("the latch key identifies the setup candle, not the symbol", t8)


print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
