"""
STRATEGY F -- Shaakuni Midnight/Daylight opening, as a first-class strategy.

Five strategies now share one dispatch chain. What matters here is that this
one is DISTINCT (its own label, its own gate, no SD ladder) and that its
discipline rules survive being wired in.
"""
import pathlib as _pl
import sys
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
import session_opens as so

passed = failed = 0
def check(name, fn):
    global passed, failed
    try:
        fn(); passed += 1; print(f"  PASS  {name}")
    except AssertionError as e:
        failed += 1; print(f"  FAIL  {name}: {e}")
    except Exception as e:
        failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")

SRC = open(_pl.Path(__file__).resolve().parent.parent /
           'hybrid_trading_bot_multiuser.py', encoding='utf-8').read()

def t1():
    assert 'def strategy_shaakuni_opening' in SRC
    assert "setup = strategy_shaakuni_opening(df_m5, _trade_direction, symbol," in SRC
check("strategy exists and is called from the dispatch chain", t1)

def t2():
    assert "'reason':      'SHAAKUNI_OPENING'" in SRC
    assert "strategy='SHAAKUNI_OPENING'" in SRC
    assert "'strategy_type': 'SSM_OPEN'" in SRC
check("distinct labels -- not folded into SHAAKUNI_SSM", t2)

def t3():
    i = SRC.find('def strategy_shaakuni_opening')
    body = SRC[i:SRC.find('def strategy_ema_scalp_cross')]
    for banned in ('compute_sd_levels', 'sd_neg2', 'midnight_sd.sd_levels',
                   'macro_windows.classify_zone'):
        assert banned not in body, f"{banned} leaked into a strategy that uses no SD ladder"
check("uses NO standard-deviation ladder (that is a different strategy)", t3)

def t4():
    assert 'ENABLE_STRATEGY_SSM_OPENING: bool = True' in SRC
    assert "getattr(config, 'ENABLE_STRATEGY_SSM_OPENING', True)" in SRC
check("has its own kill switch, independent of the SD/AOX flags", t4)

def t5():
    i = SRC.find('def strategy_shaakuni_opening')
    body = SRC[i:SRC.find('def strategy_ema_scalp_cross')]
    assert 'session_opens.entry_allowed' in body, "premium/discount discipline not applied"
    assert 'session_opens.session_state' in body
    assert "dj.record_rejection" in body, "refusals must be journalled, not dropped"
    assert body.count('dj.record_rejection') >= 3, "not every refusal path journals"
check("applies the discipline rules and journals every refusal", t5)

def t6():
    i = SRC.find('def strategy_shaakuni_opening')
    body = SRC[i:SRC.find('def strategy_ema_scalp_cross')]
    # SL must be structural, never a fixed pip amount
    assert "_since['low'].min()" in body and "_since['high'].max()" in body
    assert 'wrong side of entry' in body, "no guard against an inverted stop"
check("stop is structural (sweep extreme), with an inverted-stop guard", t6)

def t7():
    # order in the chain: opening strategy is offered before SSM
    a = SRC.find('STRATEGY F: SHAAKUNI MIDNIGHT')
    b = SRC.find('# SHAAKUNI SSM: dedicated HTF sweep')
    assert 0 < a < b, "opening strategy must be offered before plain SSM"
check("sits before SSM in the chain (more specific read wins)", t7)

# --- the rules it depends on still behave ---
def t8():
    st = {'no_go': False, 'expected_direction': 'SELL', 'fake_side': 'above'}
    ok, why = so.entry_allowed('BUY', 100.0, 99.0, st)
    assert not ok, "joined the fake push"
    ok2, _ = so.entry_allowed('SELL', 100.0, 99.0, st)
    assert ok2, "a correct premium short was refused"
check("underlying discipline: fades the push, sells premium", t8)

def t9():
    st = so.session_state(99.0, [101.0], [97.0], 1.0)   # straddling first bar
    assert st['fake_side_undetermined']
    ok, why = so.entry_allowed('SELL', 100.0, 99.0, st)
    assert not ok and 'undetermined' in why
check("undetermined trap still blocks the trade end-to-end", t9)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
