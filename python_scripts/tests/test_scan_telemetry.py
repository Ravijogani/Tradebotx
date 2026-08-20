"""
Why the bot could not tell you why a symbol never trades.

Asked "why has XAUUSD not placed a trade in two days?", the bot had no
answer available anywhere in its output. Three compounding defects:

  1. The [STATUS] line carrying every skip reason was the `elif` of a
     "sleep if the cycle finished early" branch. Cycles normally finish
     early -- that is why the sleep exists -- so the branch was never taken
     and the entire diagnostic output was unreachable in normal operation.
  2. Of ~14 rejection reasons counted in 25 places, the summary named 6.
     A symbol dying on m5_ranging or correlation printed "Skips:[none]".
  3. The counters were global. "no-setup:412" says 412 rejections happened
     somewhere across thirteen symbols, and nothing about which.
"""
import pathlib as _pl
import sys
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))

import io
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
LINES = SRC.split('\n')

CODE = [(t.start[0], t.string)
        for t in tokenize.generate_tokens(io.StringIO(SRC).readline)
        if t.type not in (tokenize.COMMENT, tokenize.STRING)]


def t1():
    # THE BUG: the status log must not hang off the cycle-timing branch.
    i = next(n for n, l in enumerate(LINES) if 'if elapsed < 0.5:' in l)
    window = LINES[i:i + 6]
    assert not any(l.strip().startswith('elif') for l in window), \
        "the status log is still the elif of the sleep -- unreachable on a fast cycle"
check("the status summary no longer hides behind the cycle-timing branch", t1)

def t2():
    # It must be reachable on the normal path: the `if iteration % 20` has to
    # sit at the same indent as the sleep branch, not inside it.
    i = next(n for n, l in enumerate(LINES) if 'if elapsed < 0.5:' in l)
    j = next(n for n, l in enumerate(LINES[i:i + 30], i) if 'iteration % 20' in l)
    assert (len(LINES[j]) - len(LINES[j].lstrip())) == (len(LINES[i]) - len(LINES[i].lstrip())), \
        "the status log is nested under the sleep instead of running alongside it"
check("the status summary runs on the normal fast-cycle path", t2)

def t3():
    # Every counted reason must be displayable. A reason counted but never
    # labelled prints as "Skips:[none]" while blocking every trade.
    import re
    counted = set()
    for m in re.finditer(r"_reject\(symbol,\s*'([a-z0-9_]+)'\)", SRC):
        counted.add(m.group(1))
    assert counted, "no rejection sites found"
    i = SRC.find('_REJ_LABEL = {')
    labels = SRC[i:SRC.find('}', i)]
    missing = sorted(r for r in counted if f"'{r}'" not in labels)
    assert not missing, f"counted but never displayed: {missing}"
check("every rejection reason the bot counts is also displayed", t3)

def t4():
    # Per-symbol attribution: the question is "why THIS symbol", not "how
    # many rejections happened overall".
    assert 'def _reject(' in SRC, "no per-symbol rejection helper"
    assert '_rej_sym' in SRC, "rejections are still only counted globally"
    import re
    old = re.findall(r"state\._rej\['[a-z0-9_]+'\]\s*(?:\+=|=)", SRC)
    assert not old, f"{len(old)} rejection sites still bypass the per-symbol helper"
check("every rejection is attributed to the symbol it blocked", t4)

def t5():
    i = SRC.find('[WHY-NO-TRADE]')
    assert i > 0, "no per-symbol summary line"
    body = SRC[max(0, i - 1400):i + 600]
    assert 'actual_symbols' in body, \
        "the summary iterates the rejection dict, so a symbol that is never " \
        "scanned at all would be invisible -- exactly the case being diagnosed"
    assert 'NOT-SCANNED' in body, "a symbol producing no rejections at all is not distinguished"
check("a symbol that is never even scanned is named, not silently omitted", t5)

def t6():
    # The global tally still feeds the existing [STATUS] line.
    i = SRC.find('def _reject(')
    body = SRC[i:i + 1400]
    assert 'state._rej[' in body and 'state._rej_sym' in body, \
        "the helper does not keep both the global and per-symbol tallies"
check("the existing global status line keeps working", t6)

def t7():
    # Both tallies must reset together, or the per-symbol view accumulates
    # forever and the "biggest blocker" stops reflecting the last window.
    i = SRC.find('state._rej = {k: 0 for k in state._rej}')
    assert i > 0, "global counters no longer reset"
    assert 'state._rej_sym = {}' in SRC[i:i + 200], \
        "the per-symbol counters are never reset -- the summary would go stale"
check("both tallies reset together after each summary", t7)

def t8():
    # SYMBOL_MIN_EQUITY still gates nothing. Left deliberately, but pinned so
    # the situation is visible rather than assumed handled: XAUUSDm is listed
    # as needing $300 and the bot happily scans it at any equity.
    import re
    uses = re.findall(r"SYMBOL_MIN_EQUITY", SRC)
    assert len(uses) == 1, (
        f"SYMBOL_MIN_EQUITY now has {len(uses)} references -- if it was wired "
        f"up, this test should assert the gate instead of its absence")
check("SYMBOL_MIN_EQUITY is still dead config (known, documented)", t8)


print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
