"""
AOX's "institutional depth" SD filter must actually filter.

It gated entry (`if not reached_sd2 and not reached_sd4: return None`) AND
position size (`_l1_alloc = 0.35 if reached_sd4 else 0.25`), but compared a
PRICE against 85% OF A PRICE:

    reached_sd2 = spike_high >= (ref_high + ref_range*2.0) * 0.85

On XAUUSD near 4400 with a 5-point range that threshold is ~3744, so every
spike passed and every AOX entry took the 35% "major reversal" allocation.
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

def legacy_bear(spike_high, ref_high, ref_range):
    return spike_high >= (ref_high + ref_range * 2.0) * 0.85

def fixed(spike_dist, ref_range, mult):
    return spike_dist >= (ref_range * mult) * 0.85

# Realistic XAUUSD numbers from the live charts
REF_HIGH, REF_RANGE = 4395.0, 5.0

def t1():
    # A trivial 0.5-point poke above the range -- nowhere near -2 SD
    spike_high = REF_HIGH + 0.5
    assert legacy_bear(spike_high, REF_HIGH, REF_RANGE), "old code should wrongly pass"
    assert not fixed(0.5, REF_RANGE, 2.0), "fixed code must reject a 0.5pt poke"
check("0.5-point poke: old passed as '-2 SD institutional', fixed rejects", t1)

def t2():
    # 85% of 2 SD = 8.5 points beyond the range -- genuinely deep
    assert fixed(8.5, REF_RANGE, 2.0), "a real -2 SD sweep must pass"
    assert fixed(20.0, REF_RANGE, 4.0), "a real -4 SD sweep must pass"
check("genuine -2 SD and -4 SD sweeps still qualify", t2)

def t3():
    # The size lever: SD4 must be strictly harder than SD2
    assert fixed(9.0, REF_RANGE, 2.0) and not fixed(9.0, REF_RANGE, 4.0), \
        "SD4 must not trigger at SD2 depth"
check("SD4 (35% allocation) is strictly deeper than SD2 (25%)", t3)

def t4():
    # The old bug in one line: threshold far BELOW the range itself
    old_threshold = (REF_HIGH + REF_RANGE * 2.0) * 0.85
    assert old_threshold < REF_HIGH - 500, \
        f"old threshold {old_threshold:.0f} should be absurdly below ref_high"
check("old threshold sat ~650 points below the range (always true)", t4)

def t5():
    # Scale independence: the fix must behave identically on a 1.10 FX price
    assert not fixed(0.0001, 0.0010, 2.0), "tiny FX poke must reject"
    assert fixed(0.0017, 0.0010, 2.0), "real FX -2 SD sweep must pass"
    # the OLD form was scale-dependent and broken on every large-price symbol
    assert legacy_bear(1.1001, 1.1000, 0.0010), "old code passed on FX too"
check("fix is scale-independent (works on 1.10 FX and 4400 gold alike)", t5)

def t6():
    src = open(_pl.Path(__file__).resolve().parent.parent /
               'hybrid_trading_bot_multiuser.py', encoding='utf-8').read()
    # Executable code only -- the explanatory comments quote the old
    # expression on purpose, so a raw text search finds itself.
    import io, tokenize
    code = ' '.join(t.string for t in tokenize.generate_tokens(io.StringIO(src).readline)
                    if t.type not in (tokenize.COMMENT, tokenize.STRING))
    assert 'sd_neg2_level' not in code, "price-scaled SD compare remains in code"
    assert 'sd_neg4_level' not in code, "price-scaled SD compare remains in code"
    i = src.find('def detect_manipulation_spike')
    seg = src[i:i + 4500]
    assert seg.count('spike_dist >= (ref_range * 2.0) * 0.85') == 2, "both directions not fixed"
    assert seg.count('spike_dist >= (ref_range * 4.0) * 0.85') == 2
check("both directions use distance-based depth; no price-scaled compare left", t6)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
