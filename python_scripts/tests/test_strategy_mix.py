"""
"Every Telegram alert says SHAAKUNI_SSM -- is no other strategy trading?"

The bot could not answer that. [WHY-NO-TRADE] is per SYMBOL, and a symbol
that DID trade is omitted from it entirely -- so the one strategy that fires
is invisible in the telemetry, and the five that do not are indistinguishable
from strategies that are switched off.

Three separate things were true at once and none of them were observable:

  1. Swappy 3C and AOX self-execute and never touched place_ai_trade, which
     is where the "TRADE OPENED" Telegram is sent -- so they placed real
     orders and announced nothing (fixed in 9b2651d).
  2. ENABLE_SWAPPY_REVERSAL defaults False, so that strategy never trades.
  3. SSM is evaluated LAST of the six detectors and _candidates is consumed
     front-to-back, so SSM does not win on priority -- it wins the slot
     because nothing ahead of it survived.

These tests pin the telemetry that makes (3) readable, and the ordering fact
that makes it meaningful.
"""
import pathlib as _pl
import sys, tokenize, io, re
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
import decision_journal as dj

passed = failed = 0
def check(name, fn):
    global passed, failed
    try:
        fn(); passed += 1; print(f"  PASS  {name}")
    except AssertionError as e:
        failed += 1; print(f"  FAIL  {name}: {e}")
    except Exception as e:
        failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")

BOT = _pl.Path(__file__).resolve().parent.parent / 'hybrid_trading_bot_multiuser.py'
SRC = BOT.read_text(encoding='utf-8')

TRIPLES = ('"' * 3, "'" * 3)

def code_only(text):
    """Return the source with comments and docstrings blanked out.

    Every prose-matching test in this repo has been burned at least once by a
    search that matched the explanatory comment sitting directly above the
    code it was meant to check. Dropping ALL string tokens was the earlier
    attempt and it over-corrected -- half of these assertions are about
    string literals like 'SWAPPY_3C' that are real code. So: strip comments
    and triple-quoted blocks, keep ordinary literals.
    """
    drop = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                drop.append((tok.start, tok.end))
            elif tok.type == tokenize.STRING and \
                    tok.string.lstrip('rbfuRBFU')[:3] in TRIPLES:
                drop.append((tok.start, tok.end))
    except tokenize.TokenError:
        pass
    lines = text.splitlines(keepends=True)
    for (sr, sc), (er, ec) in reversed(drop):
        if sr == er:
            lines[sr - 1] = lines[sr - 1][:sc] + lines[sr - 1][ec:]
        else:
            lines[sr - 1] = lines[sr - 1][:sc] + "\n"
            for r in range(sr, er - 1):
                lines[r] = ""
            lines[er - 1] = lines[er - 1][ec:]
    return "".join(lines)

def flat(text):
    """Space-collapsed, so ('AOX', 'SSM') and ('AOX','SSM') both match."""
    return re.sub(r'\s+', '', text)

CODE = code_only(SRC)
FLAT = flat(CODE)

# ---------------------------------------------------------------- the tally
def t1():
    assert 'def _strat_tally' in SRC, "no per-strategy counter exists"
check("a per-strategy tally helper exists", t1)

def t2():
    i = SRC.find('def _strat_tally')
    body = SRC[i:i + 2000]
    assert "'candidate'" in body and "'entered'" in body, \
        "must separate 'detector produced a setup' from 'it became an order'"
check("the tally distinguishes candidates from entries", t2)

def t3():
    # Detection failure and filter failure look identical without this split.
    assert "_strat_tally(setup.get('strategy_type'" in FLAT, \
        "candidates are not tallied by their own strategy_type"
check("candidates are tallied under the strategy that produced them", t3)

def t4():
    # Every _candidates.append must be preceded by a tally, or a strategy
    # silently vanishes from the mix line.
    appends = FLAT.count('_candidates.append(setup)')
    assert appends >= 5, f"expected >=5 collect sites, found {appends}"
    tallies = FLAT.count("_strat_tally(setup.get('strategy_type'")
    assert tallies >= appends, \
        f"{appends} collect sites but only {tallies} tallies -- a strategy is invisible"
check("every candidate-collection site tallies", t4)

def t5():
    # The two self-executing strategies bypass _candidates entirely.
    assert "_strat_tally('SWAPPY_3C'" in FLAT, "Swappy 3C never tallies"
    assert "_strat_tally('AOX'" in FLAT, "AOX never tallies"
check("the self-executing strategies (Swappy 3C, AOX) tally themselves", t5)

def t6():
    i = SRC.find('trade_result = place_ai_trade(')
    assert i > 0
    body = SRC[i:i + 600]
    assert '_strat_tally' in body, "the shared pipeline's success path does not tally"
    assert "'entered'" in body
check("a filled trade tallies as 'entered' on its real strategy", t6)

# ---------------------------------------------------------- the output line
def t7():
    assert '[STRATEGY MIX]' in SRC, "no per-strategy summary line is ever logged"
check("a [STRATEGY MIX] line is emitted", t7)

def t8():
    i = SRC.find('[STRATEGY MIX]')
    window = SRC[max(0, i - 4000):i + 500]
    assert 'ENABLE_SWAPPY_REVERSAL' in window, \
        "the mix line cannot tell a disabled strategy from a silent one"
    assert 'OFF' in window
check("a disabled strategy is reported as OFF, not as zero", t8)

def t9():
    # An unrecognised strategy_type must not be swallowed.
    i = SRC.find('[STRATEGY MIX]')
    window = SRC[max(0, i - 4000):i + 200]
    assert 'sorted(set(_sm)' in window, "unknown strategy names are dropped"
check("strategies not in the known list are still reported", t9)

def t10():
    j = SRC.find('logger.info(f"[STRATEGY MIX]')
    assert j > 0, "the mix line is never logged"
    # The helper also contains `state._strat = {}` as its lazy init, so look
    # for the reset AFTER the line that reports it, not anywhere in the file.
    assert SRC.find('state._strat = {}', j) > 0, \
        "the tally is never reset -- counts would accumulate forever"
    assert SRC.find('state._rej_sym = {}', j) > 0, \
        "the strategy reset must sit with the other per-window resets"
check("the tally resets each reporting window, after being logged", t10)

# ------------------------------------------------- the funnel, finally read
def t11():
    assert 'dj.drain_rejections()' in FLAT, \
        "decision_journal's rejection buffer is still never read back"
    assert 'dj.rejection_funnel(' in FLAT
check("the rejection funnel is actually consumed by the live bot", t11)

def t12():
    # Not just consumed -- printed. A drain with no output would be worse
    # than none: it would silently destroy the evidence.
    assert '[STRATEGY GATES]' in SRC
    i = SRC.find('dj.drain_rejections()')
    assert SRC.find('[STRATEGY GATES]', i) > 0, \
        "the drained funnel is not logged -- draining would just discard it"
check("the drained funnel is logged, not discarded", t12)

def t13():
    src = (_pl.Path(__file__).resolve().parent.parent /
           'decision_journal.py').read_text(encoding='utf-8')
    assert '_MAX_REJECTIONS' in src and '_rejections_dropped' in src
    assert 'rejections_dropped' in src
check("decision_journal reports truncation rather than hiding it", t13)

def t14():
    # Behavioural: the funnel names the FIRST vetoing check -- the gate that
    # was actually decisive, not merely the last one listed.
    dj.drain_rejections()
    j = dj.DecisionJournal('EURUSDm', direction='BUY', strategy='BANKO')
    j.note(dj.REGIME, 'killzone', dj.WEAK, 'outside killzone')
    j.note(dj.LIQUIDITY, 'liquidity_sweep', dj.VETO, 'no sweep')
    j.note(dj.STRUCTURE, 'mss', dj.VETO, 'no shift')
    j.decide(False, 'no sweep')
    dj.record_rejection(j)
    f = dj.rejection_funnel(dj.drain_rejections())
    assert f.get('BANKO', {}).get('liquidity_sweep') == 1, f
    assert 'mss' not in f.get('BANKO', {}), "counted a later veto as decisive"
check("the funnel attributes a rejection to its first decisive veto", t14)

def t15():
    # Draining must empty the buffer, or the same rejections are reported
    # every window and the counts become meaningless.
    dj.drain_rejections()
    j = dj.DecisionJournal('X', strategy='S')
    j.note(dj.STRUCTURE, 'k', dj.VETO, '')
    j.decide(False, '')
    dj.record_rejection(j)
    assert dj.drain_rejections(), "nothing recorded"
    assert dj.drain_rejections() == [], "drain did not clear the buffer"
check("draining clears the buffer so windows do not double-count", t15)

# ---------------------------------------------------- the ordering fact
def t16():
    # SSM dominating the alerts is NOT a priority artifact: it is evaluated
    # last and the candidate list is consumed front-to-back. If this ever
    # inverts, the diagnosis in this module's docstring stops being true.
    ema  = FLAT.find('setup=strategy_ema_scalp_cross(df_m5')
    bank = FLAT.find('setup=strategy_banko_smc(df_m15')
    opn  = FLAT.find('setup=strategy_shaakuni_opening(df_m5')
    ssm  = FLAT.find('_ssm_result=strategy_shaakuni_ssm(symbol')
    for label, at in (('EMA', ema), ('BANKO', bank), ('OPENING', opn), ('SSM', ssm)):
        assert at > 0, f"{label} call site not found"
    assert ema < bank < opn < ssm, \
        "SSM is no longer evaluated last -- re-check the SSM-dominance diagnosis"
check("SSM is evaluated LAST, so it does not win on priority", t16)

def t17():
    i = FLAT.find('forsetupin_candidates:')
    assert i > 0, "candidates are not iterated"
    body = FLAT[i:i + 200]
    assert '_entries_this_symbol>=_max_sym_entries' in body, \
        "no per-cycle entry cap -- ordering would not matter"
check("candidates are consumed front-to-back under a per-cycle cap", t17)

def t18():
    # The one genuine asymmetry that favours SSM: a lower AI bar.
    # Pinned so a future edit that widens the gap has to do it deliberately.
    assert "_strat_typein('AOX','SSM')" in FLAT, \
        "the per-strategy L3 threshold split is gone"
    assert '_l3_min_score=5' in FLAT, "SSM/AOX no longer have their own L3 threshold"
    assert '_l3_min_score=6' in FLAT, "the other strategies no longer have a higher bar"
check("SSM/AOX sit on a lower AI-L3 bar than the other strategies", t18)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
