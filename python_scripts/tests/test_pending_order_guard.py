"""
The 2026-08-18 incident: ~25 duplicate SELL_STOPs on USDCADm.

MT5 history showed 25+ orders sharing ONE open time (13:10:44), one price
(1.38675), one SL (1.38782) and one TP (1.38355), all closing together at
13:49:10 for -0.77 each. That is not 25 decisions -- it is 25 resting stop
orders filling at the same instant.

They accumulated because the per-symbol guard asked "do I have a POSITION on
this symbol?" and a pending order is not a position. Every cycle answered no.
"""
import pathlib as _pl
import sys
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
import bot_control as bc

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

# ---------- the guard that failed ----------
def t1():
    assert '_pending_orders = mt5.orders_get() or []' in SRC, "pending orders never read"
    assert '_committed_symbols' in SRC and '_committed_count' in SRC
check("the scan loop now reads pending orders", t1)

def t2():
    assert 'if symbol in _committed_symbols:' in SRC, "per-symbol guard still positions-only"
    old = "if any(pos.symbol == symbol and pos.magic == MAGIC_NUMBER for pos in my_bot_positions):"
    assert old not in SRC, "the positions-only guard is still present"
check("per-symbol guard covers positions AND pending orders", t2)

def t3():
    assert 'if _committed_count >= config.MAX_CONCURRENT_TRADES:' in SRC
    assert 'if len(my_bot_positions) >= config.MAX_CONCURRENT_TRADES:' not in SRC
check("MAX_CONCURRENT_TRADES counts committed risk, not just fills", t3)

def t4():
    assert '_total_risk_pct = _committed_count * config.BASE_RISK_PERCENT' in SRC
check("portfolio risk %% includes pending exposure", t4)

# ---------- the last line of defence ----------
def t5():
    i = SRC.find('def place_swappy_pending_order')
    body = SRC[i:i + 3000]
    assert 'mt5.orders_get(symbol=symbol)' in body, "placer does not check the book"
    assert 'refusing to stack another' in body
check("the order placer refuses to stack a second pending order", t5)

def t6():
    i = SRC.find('def place_swappy_pending_order')
    body = SRC[i:i + 3000]
    j = body.find('cannot read pending orders')
    assert j > 0, "no handling for an unreadable order book"
    assert 'return False' in body[j:j + 300], "must fail CLOSED, not place blind"
check("unreadable order book fails CLOSED (cannot verify -> do not place)", t6)

def t7():
    # Ordering, not mere presence. The duplicate check is worthless if a
    # `return False` upstream of it can be reached first -- and it must also
    # precede the expensive work (lesson lookup, CapitalController sizing) so
    # a duplicate costs nothing. Window is generous because the guard sits at
    # the top and the sizing block is ~150 lines further down; each landmark
    # is asserted FOUND, so a missing one fails loudly instead of silently
    # comparing against find()'s -1.
    i = SRC.find('def place_swappy_pending_order')
    assert i > 0, "place_swappy_pending_order not found"
    body = SRC[i:i + 8000]
    dup = body.find('mt5.orders_get(symbol=symbol)')
    assert dup > 0, "no duplicate check in the placer"
    for landmark, label in (("banned.upper()", "strategy ban"),
                            ("check_trade_against_lessons(", "lesson gating"),
                            ("CapitalController().calculate(", "risk sizing")):
        at = body.find(landmark)
        assert at > 0, f"{label} not found within the placer window"
        assert dup < at, f"duplicate check must run before {label}"
check("duplicate check runs first, before ban/lesson/sizing work", t7)

def t7b():
    # The scan loop's read must fail CLOSED too. A transport error there
    # leaves the bot blind to what is already committed, which is exactly the
    # state that produced the duplicates -- so it skips the cycle rather than
    # scanning on with an empty pending list.
    i = SRC.find('_pending_orders = mt5.orders_get()')
    assert i > 0, "scan loop does not read the order book"
    window = SRC[i - 200:i + 600]
    assert 'try:' in SRC[i - 200:i], "the scan-loop read is not guarded"
    j = window.find('cannot read pending orders')
    assert j > 0, "no handler for an unreadable book in the scan loop"
    assert 'continue' in window[j:j + 300], \
        "must skip the cycle, not fall through with an empty pending list"
check("scan-loop order-book read fails CLOSED (skips the cycle)", t7b)

# ---------- the dashboard lie ----------
def t8():
    assert 'def mark_bot_stopped' in open(
        _pl.Path(__file__).resolve().parent.parent / 'bot_control.py',
        encoding='utf-8').read()
check("bot_control.mark_bot_stopped exists", t8)

def t9():
    assert SRC.count('bot_control.mark_bot_stopped(') >= 2, \
        "needs both the emergency path and the catch-all"
    i = SRC.find('EMERGENCY CIRCUIT BREAKER TRIPPED')
    assert 'mark_bot_stopped' in SRC[i:i + 900], "emergency path does not mark stopped"
check("emergency breaker AND the final shutdown both mark the row stopped", t9)

def t10():
    for f in ('intraday.py', 'structural_swing_pro.py'):
        src = open(_pl.Path(__file__).resolve().parent.parent / f, encoding='utf-8').read()
        assert 'bot_control.mark_bot_stopped' in src, f"{f} can still exit silently"
check("all three bots mark themselves stopped on exit", t10)

def t11():
    src = open(_pl.Path(__file__).resolve().parent.parent / 'bot_control.py',
               encoding='utf-8').read()
    i = src.find('def mark_bot_stopped')
    body = src[i:i + 2200]
    assert ".eq('status'" not in body and ".in_('status'" not in body, \
        "mark_bot_stopped must be unconditional -- the process IS ending"
    assert '_confirmed_running.discard' in body, "latch not cleared on stop"
check("marking stopped is unconditional and clears the running latch", t11)

def t12():
    # a fake supabase whose update raises must not propagate out of a shutdown path
    class Boom:
        def table(self, n): return self
        def update(self, p): return self
        def eq(self, k, v): return self
        def execute(self): raise RuntimeError("network gone")
    assert bc.mark_bot_stopped(Boom(), 'u', 's') is False, "raised on a shutdown path"
check("a failed stop-write returns False instead of raising during shutdown", t12)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
