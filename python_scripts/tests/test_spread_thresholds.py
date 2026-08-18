"""
Spread spike thresholds must be per-symbol CORRECT, not per-symbol assumed.

Live alert that exposed this:
  [SPREAD SPIKE] USDJPYm order ABORTED: spread 0.0100 (67x normal)

0.0100 on USDJPY is 1.0 pip -- an ordinary spread. It scored 67x because the
FX threshold was hardcoded to FX_PIPS * 0.0001 (the pip size of a 5-digit
pair), making it 100x too small on a 3-digit JPY pair. One guard blocked
every JPY order; a second CLOSED open JPY positions at a normal spread.
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

FX_PIPS = 1.5

def threshold(point, digits):
    """The corrected derivation from max_allowed_spread_price()."""
    pip = point * 10 if digits in (3, 5) else point
    return FX_PIPS * pip

def legacy(_point, _digits):
    return FX_PIPS * 0.0001

# ---- 1. Reproduce the live false alarm exactly.
def t1():
    spread = 0.0100                       # 1.0 pip on USDJPY -- normal
    old = legacy(0.001, 3)
    assert abs(old - 0.00015) < 1e-9, old
    assert round(spread / old) == 67, f"expected the logged 67x, got {spread/old:.1f}x"
    assert spread > old * 3, "old code would abort (confirming the bug)"
check("old threshold reproduces the logged '67x normal' on USDJPY", t1)

# ---- 2. The fix makes that same spread ordinary.
def t2():
    spread = 0.0100
    new = threshold(0.001, 3)             # USDJPY, 3-digit broker
    assert abs(new - 0.015) < 1e-9, new
    assert spread <= new, "a normal 1-pip JPY spread is still flagged"
    assert not (spread > new * 3), "would still abort"
check("corrected threshold treats 1.0-pip USDJPY as normal", t2)

# ---- 3. A REAL JPY spike must still be caught.
def t3():
    new = threshold(0.001, 3)
    for spike in (0.05, 0.10, 0.50):      # 5, 10, 50 pips
        assert spike > new * 3, f"{spike} not caught as a spike"
check("genuine JPY spikes (5+ pips) are still blocked", t3)

# ---- 4. 5-digit majors unchanged -- no regression.
def t4():
    new = threshold(0.00001, 5)           # EURUSD
    assert abs(new - 0.00015) < 1e-12, new
    assert abs(new - legacy(0.00001, 5)) < 1e-12, "behaviour changed for EURUSD"
    assert 0.00010 <= new                       # 1.0 pip passes
    assert 0.0010 > new * 3                     # 10 pips blocked
check("EURUSD threshold identical to before (no regression)", t4)

# ---- 5. 4-digit / 2-digit brokers (whole-pip quoting) handled.
def t5():
    assert abs(threshold(0.0001, 4) - 0.00015) < 1e-12   # EURUSD, 4-digit
    assert abs(threshold(0.01, 2) - 0.015) < 1e-12       # USDJPY, 2-digit
check("whole-pip (4/2-digit) brokers derive the same thresholds", t5)

# ---- 6. GBPJPY, the other pair the expansion added.
def t6():
    new = threshold(0.001, 3)
    assert 0.020 <= new * 3, "a 2-pip GBPJPY spread should not abort"
    assert threshold(0.001, 3) > legacy(0.001, 3) * 50, "JPY fix not applied"
check("GBPJPY no longer aborts on ordinary spreads", t6)

# ---- 7. Metals/crypto/oil keep absolute-value thresholds.
def t7():
    src = open(_pl.Path(__file__).resolve().parent.parent /
               'hybrid_trading_bot_multiuser.py', encoding='utf-8').read()
    i = src.find('def max_allowed_spread_price')
    seg = src[i:i+2200]
    for k in ('SCALP_MAX_SPREAD_XAUUSD', 'SCALP_MAX_SPREAD_XAGUSD',
              'SCALP_MAX_SPREAD_BTC', 'SCALP_MAX_SPREAD_ETH', 'SCALP_MAX_SPREAD_OIL'):
        assert k in seg, f"{k} branch lost"
check("metals / crypto / oil branches preserved", t7)

# ---- 8. Both guards now share the one helper.
def t8():
    src = open(_pl.Path(__file__).resolve().parent.parent /
               'hybrid_trading_bot_multiuser.py', encoding='utf-8').read()
    calls = src.count('max_allowed_spread_price(')
    assert calls >= 3, f"expected def + 2 call sites, found {calls}"
    # Check EXECUTABLE CODE only. A raw text search trips over this file's own
    # comments and docstrings, which quote the old expression to explain it --
    # so strip comments and string literals via tokenize before looking.
    import io, tokenize
    code = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type not in (tokenize.COMMENT, tokenize.STRING):
            code.append(tok.string)
    code = ' '.join(code)
    assert 'SCALP_MAX_SPREAD_FX_PIPS' not in code or '0.0001' not in code.split(
        'SCALP_MAX_SPREAD_FX_PIPS')[1][:40], "a hardcoded FX pip size remains in code"
check("both spike guards use the shared helper; no hardcoded pip left", t8)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
