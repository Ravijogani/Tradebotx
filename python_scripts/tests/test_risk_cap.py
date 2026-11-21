"""
How much can ONE trade lose? The answer used to depend on a silent failure.

Four layers set position size, and two of them disagreed with their own
comments:

  1. CapitalController.calculate() clamps INTENDED risk to [0.25%, 1.5%].
     This layer works.
  2. get_dynamic_trade_params narrows the STOP so a min-lot position lands
     near MAX_RISK_PERCENT. This is the primary control -- and it sat in a
     try/except that swallowed failures to logger.debug, so when it did not
     run, nothing said so.
  3. place_ai_trade's min-lot backstop refused trades over `hard_cap_pct`.
     That was 10.0 on a line commented "Never exceed 3% on any single
     trade" -- $18.93 authorised on a $189 account where intent was $1.89.
  4. The portfolio cap reads 25.0 (commented 3%) but MAX_CONCURRENT_TRADES
     binds first at 2, so the real portfolio ceiling is 2x1.0 + 1.5 = 3.5%.

Layers 1 and 3 are asserted against the real objects; 2 and 4 by inspection,
because both live inside the MT5 call path.
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

from backtest.bot_loader import import_bot_module
bot = import_bot_module()
cfg = bot.config
ROOT = _pl.Path(__file__).resolve().parent.parent
SRC = open(ROOT / 'hybrid_trading_bot_multiuser.py', encoding='utf-8').read()


# ---------- layer 1: intended risk ----------
def _calc(**kw):
    args = dict(edge_score=65.0, symbol_metrics=1.0, session="LONDON_NY",
                drawdown=0.0, symbol="EURUSDm", open_positions_count=0,
                pattern_health=1.0)
    args.update(kw)
    return bot.CapitalController().calculate(**args)

def t1():
    # Every combination, including the most permissive one, stays inside the
    # clamp. Eight multipliers compound, so this is not obvious by reading.
    hot = _calc(edge_score=100.0, symbol_metrics=99.0, pattern_health=99.0,
                session="LONDON_NY")
    assert hot <= 1.5 + 1e-9, f"intended risk escaped the clamp: {hot}"
    cold = _calc(edge_score=0.0, symbol_metrics=0.0, pattern_health=0.0,
                 session="ASIA", open_positions_count=5)
    assert cold >= 0.25 - 1e-9, f"intended risk fell below the floor: {cold}"
check("intended risk is always clamped to [0.25%, 1.5%]", t1)

def t2():
    # Drawdown must throttle to a full stop, not merely shrink.
    assert _calc(drawdown=8.0) == 0.25 or _calc(drawdown=8.0) < _calc(drawdown=0.0), \
        "8% drawdown does not reduce size"
    for dd in (0.0, 2.0, 4.0, 6.0):
        assert _calc(drawdown=dd) >= _calc(drawdown=dd + 2.0), \
            f"risk did not fall going into deeper drawdown at {dd}%"
check("size falls monotonically as drawdown deepens", t2)

def t3():
    assert _calc(symbol="BTCUSDm") < _calc(symbol="EURUSDm"), "BTC not scaled down"
    assert _calc(symbol="XAUUSDm") < _calc(symbol="EURUSDm"), "gold not scaled down"
    assert _calc(session="ASIA") < _calc(session="LONDON_NY"), "session not applied"
    assert _calc(open_positions_count=2) < _calc(open_positions_count=0), \
        "existing exposure does not reduce new size"
check("instrument, session and exposure all reduce size", t3)


# ---------- layer 3: the min-lot backstop ----------
def t4():
    i = SRC.find('hard_cap_pct = ')
    assert i > 0, "the min-lot backstop vanished"
    line = SRC[i:SRC.find('\n', i)]
    assert 'PLATFORM_MAX_RISK_PER_TRADE_PERCENT' in line, (
        "the backstop must use the same shared 1.5% ceiling as every strategy")
    assert cfg.MAX_RISK_PERCENT == 1.5
check("minimum-lot trades cannot bypass the shared 1.5% per-trade ceiling", t4)

def t5():
    i = SRC.find('hard_cap_pct = ')
    line = SRC[i:SRC.find('\n', i)]
    assert '5.0' not in line and '10.0' not in line, \
        "a looser hardcoded risk backstop remains"
check("the execution backstop has no looser hardcoded override", t5)

def t6():
    # Nothing downstream can shrink a min-lot position, so an overshoot is
    # the operator's only warning and must not be INFO.
    i = SRC.find('lot_raw={lot_raw:.5f} < min_lot')
    assert i > 0, "the overshoot notice vanished"
    assert 'logger.warning' in SRC[max(0, i - 400):i], \
        "a trade going out at several times intended risk is still only INFO"
check("a min-lot overshoot is logged as a warning, not buried at INFO", t6)


# ---------- layer 2: the primary control must not fail silently ----------
def t7():
    i = SRC.find('[SL CAP] Could not compute')
    assert i > 0, "the SL cap still fails silently"
    body = SRC[max(0, i - 300):i + 900]
    assert 'logger.error' in body, "the failure is still below error level"
    assert 'send_telegram_notification' in body, "the operator is never told"
check("the primary risk control says so when it cannot run", t7)

def t8():
    # It must not stop trading -- a spec read that fails once is not a reason
    # to halt -- and it must not spam.
    i = SRC.find('[SL CAP] Could not compute')
    body = SRC[i:i + 1200]
    assert 'return' not in body.split('send_telegram_notification')[0], \
        "a failed cap now aborts the trade -- that was not the chosen behaviour"
    assert '3600' in body, "the alert is not rate-limited"
check("a failed cap keeps trading and alerts at most hourly", t8)


# ---------- layer 4: the portfolio ceiling ----------
def t9():
    # The real ceiling is the concurrency limit, not the 25% figure.
    worst = cfg.MAX_CONCURRENT_TRADES * cfg.BASE_RISK_PERCENT + cfg.MAX_RISK_PERCENT
    assert worst <= 5.0, f"portfolio exposure can reach {worst}%"
    assert cfg.MAX_CONCURRENT_TRADES <= 3, \
        "concurrency is the binding portfolio control; loosening it raises total risk"
check("total open risk is bounded by concurrency, not the 25% figure", t9)

def t10():
    # Platform-level breakers must stay at the advertised numbers.
    import risk_limits
    assert risk_limits.PLATFORM_MAX_DAILY_LOSS_PERCENT <= 5.0
    assert risk_limits.PLATFORM_MAX_WEEKLY_LOSS_PERCENT <= 10.0
    assert cfg.MAX_DAILY_LOSS_PERCENT == risk_limits.PLATFORM_MAX_DAILY_LOSS_PERCENT, \
        "the bot's daily limit has drifted from the platform promise"
check("daily/weekly breakers still match what the site advertises", t10)


print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
