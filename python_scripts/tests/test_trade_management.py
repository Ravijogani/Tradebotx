"""
SL/TP and position management -- the audit findings, pinned.

Four things were wrong, and three of them were invisible because the code
LOOKED like it did them:

  1. ScalpingExitEngine returned SCALE_OUT at r >= PARTIAL_TP_RR (2.0), and
     manage_all_positions `continue`s on any non-HOLD decision. Runner
     promotion needs r >= 2.0. The Stage 3 (70% lock) trail needs r >= 2.0.
     Both sit below that intercept, so neither had ever executed.
  2. Breakeven fired at 1.5R generic / 2.0R Swappy. Swappy's structural TP
     has a 1.5R floor -- so a Swappy trade targeting 1.5-2.0R had its BE
     trigger BEYOND its own take-profit and carried full risk to the exit.
  3. The open-position spike guard force-closed at 3x normal spread, which is
     reached at the NY open, on news and at rollover.
  4. Nothing handled the weekend. The bot would open a scalp at 16:55 NY on a
     Friday and carry it through the Sunday gap, where the stop that sized the
     position cannot fill.
"""
import pathlib as _pl
import sys
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta, timezone

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
cfg = bot.config


# ---------- 1. the 2R intercept ----------
def _exit_ctx(r, progress=0.0, edge=60.0, dur=20.0):
    return bot.ExitContext(
        trade_ctx=bot.TradeContext(), edge_score=edge,
        lifecycle="EXPANSION", momentum="INCREASING",
        liquidity_state="HIT" if progress >= 0.9 else "NORMAL",
        regime="TRENDING", r_multiple=r, duration_mins=dur,
    )

def t1():
    e = bot.ScalpingExitEngine()
    # At 2R -- the exact point runner promotion and the Stage 3 trail trigger --
    # the engine must now stand aside so they can run.
    assert e.decide(_exit_ctx(2.0)) == "HOLD", \
        "still intercepting at 2R -- Stage 3 and the RunnerEngine stay unreachable"
    assert e.decide(_exit_ctx(3.5)) == "HOLD", "still intercepting above 2R"
check("the exit engine no longer claims the trade at 2R", t1)

def t2():
    e = bot.ScalpingExitEngine()
    # 90%-of-target was the second route to the same interception.
    assert e.decide(_exit_ctx(1.8, progress=0.95)) == "HOLD", \
        "progress>=90% still scales out, which also skips the trail"
check("nearing the target no longer scales out either", t2)

def t3():
    # Flag flipped back = old behaviour. The point of gating rather than
    # deleting is that this stays one flag away, not one commit away.
    e = bot.ScalpingExitEngine()
    old = cfg.ENABLE_PARTIAL_TP
    try:
        cfg.ENABLE_PARTIAL_TP = True
        assert e.decide(_exit_ctx(2.0)) == "SCALE_OUT", "flag no longer restores scale-out"
    finally:
        cfg.ENABLE_PARTIAL_TP = old
check("ENABLE_PARTIAL_TP=True restores the old scale-out behaviour", t3)

def t4():
    # The genuine exits must survive. A trade well past its stop with a dead
    # edge still has to be closed.
    e = bot.ScalpingExitEngine()
    assert e.decide(_exit_ctx(-0.5, edge=20.0, dur=10.0)) == "EXIT", \
        "structural-failure exit was disabled along with the scale-out"
    assert e.decide(_exit_ctx(0.05, edge=20.0, dur=60.0)) == "EXIT", \
        "stale-trade exit was disabled"
check("real exits (structural failure, stale trade) still fire", t4)

def t5():
    assert cfg.ENABLE_PARTIAL_TP is False, "trailing mode is not the default"
check("trailing mode is the default", t5)


# ---------- 2. breakeven at 1.0R ----------
SRC = open(_pl.Path(__file__).resolve().parent.parent /
           'hybrid_trading_bot_multiuser.py', encoding='utf-8').read()

def t6():
    assert cfg.BREAKEVEN_TRIGGER_RR == 1.0, \
        f"BE trigger is {cfg.BREAKEVEN_TRIGGER_RR}R, not 1.0R"
check("breakeven triggers at 1.0R", t6)

def t7():
    # The Swappy branch had a hardcoded 2.0 -- beyond its own minimum target.
    i = SRC.find("if _strategy_type == 'SWAPPY':")
    assert i > 0, "Swappy management branch not found"
    body = SRC[i:i + 700]
    assert 'r_multiple >= 2.0' not in body, \
        "Swappy still moves to BE at a hardcoded 2.0R"
    assert 'config.BREAKEVEN_TRIGGER_RR' in body, \
        "Swappy does not use the shared BE trigger"
check("Swappy uses the shared BE trigger, not a hardcoded 2.0R", t7)

def t8():
    # The gap this closes, stated as arithmetic: Swappy's structural TP floor
    # is 1.5R, so any BE trigger above it is unreachable for those trades.
    import inspect
    sig = inspect.signature(bot.find_swappy_structural_tp)
    tp_floor = sig.parameters['min_rr'].default
    assert cfg.BREAKEVEN_TRIGGER_RR <= tp_floor, (
        f"BE at {cfg.BREAKEVEN_TRIGGER_RR}R is beyond Swappy's {tp_floor}R minimum "
        f"target -- those trades can never reach breakeven")
check("the BE trigger sits inside Swappy's minimum target distance", t8)


# ---------- 3. spike guard ----------
def t9():
    assert cfg.SPREAD_SPIKE_CLOSE_MULT >= 6.0, \
        f"open-position spike guard still at {cfg.SPREAD_SPIKE_CLOSE_MULT}x"
    i = SRC.find('SPIKE GUARD')
    assert '_normal_max * config.SPREAD_SPIKE_CLOSE_MULT' in SRC, \
        "the guard still uses a hardcoded multiple"
check("the spike guard uses the configured multiple, >= 6x", t9)


# ---------- 4. weekend ----------
def _ny(dow_iso, h, m=0):
    """A datetime whose weekday() is dow_iso (0=Mon) at h:m."""
    base = datetime(2026, 8, 17)          # a Monday
    return base + timedelta(days=dow_iso, hours=h, minutes=m)

def t10():
    assert bot.weekend_state(_ny(2, 10)) == 'OPEN', "Wednesday morning is not open"
    assert bot.weekend_state(_ny(4, 9)) == 'OPEN', "Friday morning is not open"
check("mid-week and Friday morning trade normally", t10)

def t11():
    ws = bot.weekend_state
    assert ws(_ny(4, 15, 0)) == 'NO_NEW', "Friday 15:00 NY does not stop new entries"
    assert ws(_ny(4, 16, 29)) == 'NO_NEW', "still not blocking at 16:29"
    assert ws(_ny(4, 16, 30)) == 'FLATTEN', "Friday 16:30 NY does not flatten"
    assert ws(_ny(4, 16, 59)) == 'FLATTEN', "not flattening before the 17:00 close"
check("Friday: no new trades at 15:00, flat by 16:30", t11)

def t12():
    ws = bot.weekend_state
    # A bot started on a Saturday must not arm itself, and Sunday only
    # reopens at the 17:00 NY session open.
    assert ws(_ny(5, 12)) == 'FLATTEN', "Saturday is treated as open"
    assert ws(_ny(6, 12)) == 'FLATTEN', "Sunday midday is treated as open"
    assert ws(_ny(6, 17, 0)) == 'OPEN', "Sunday 17:00 NY reopen not honoured"
check("the weekend itself stays closed until the Sunday 17:00 reopen", t12)

def t13():
    old = cfg.ENABLE_WEEKEND_FLAT
    try:
        cfg.ENABLE_WEEKEND_FLAT = False
        assert bot.weekend_state(_ny(5, 12)) == 'OPEN', "flag does not disable the guard"
    finally:
        cfg.ENABLE_WEEKEND_FLAT = old
check("ENABLE_WEEKEND_FLAT=False disables the guard entirely", t13)

def t14():
    # Resting orders must be cancelled too: a stop order left on the book can
    # be triggered by the Sunday gap itself, at a price nobody chose.
    i = SRC.find('def flatten_for_weekend')
    assert i > 0, "no flatten function"
    body = SRC[i:i + 3000]
    assert 'orders_get' in body and 'order_delete' in body, \
        "flatten closes positions but leaves pending orders on the book"
check("the weekend flatten cancels resting orders as well as positions", t14)

def t15():
    # It must be wired in AHEAD of anything that can open a position, and the
    # flatten must be latched so it fires once, not every cycle for 48 hours.
    i = SRC.find("_wk = weekend_state()")
    assert i > 0, "weekend_state is never called from the loop"
    j = SRC.find("for symbol in actual_symbols:")
    assert i < j, "the weekend check runs after the entry scan"
    assert '_weekend_flat_done' in SRC, "the flatten is not latched -- it would re-fire every cycle"
check("the weekend check runs before the entry scan and latches its flatten", t15)


# ---------- the runner target ----------
def t16():
    # Trailing while the TP sits at 2R is a contradiction: the TP closes the
    # trade whatever the stop does. Stage 3 must extend the target it was
    # given to the runner TP that was previously computed and discarded.
    i = SRC.find('TRAIL STAGE3')
    assert i > 0, "Stage 3 trail not found"
    body = SRC[max(0, i - 1800):i + 900]
    assert "params.get('tp2'" in body, "Stage 3 never reaches for the runner target"
    assert "'tp2':           params.get('tp2', 0.0)," in SRC, \
        "tp2 is still discarded at entry, so there is nothing to extend to"
check("the trail extends the target instead of trailing into a fixed TP", t16)

def t17():
    # Only ever further away, never nearer -- pulling a TP closer mid-trade
    # would cut a winner short.
    i = SRC.find("_tp2 = params.get('tp2', 0.0)")
    assert i > 0, "runner-target lookup not found"
    body = SRC[i:i + 400]
    assert '_tp2 > tp' in body and '_tp2 < tp' in body, \
        "the target is not direction-checked -- it could be moved nearer"
check("the target is only ever extended, never pulled closer", t17)


print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
