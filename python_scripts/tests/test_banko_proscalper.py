"""
BANKO (SMC/ICT scalping engine) and proscalper.py -- review findings, pinned.

Both landed on main from Lovable without test coverage. The bugs worth
pinning are the silent ones -- code that runs, logs success, and quietly
throws away the thing it just computed.

  1. get_dynamic_trade_params accepted `ema50_tp_hint` and `range_scalp_mode`
     and never passed either on. BANKO does more work than anything else in
     the file to find its target -- next opposing liquidity pool, RR floor
     2.0 in a killzone / 2.5 outside one, structural-swing fallback -- hands
     it over through that channel, and it landed nowhere. EMA Scalp's 50-EMA
     target went the same way.
  2. BANKO's killzones were hardcoded UTC hours. The NY killzones are New
     York clock times, so their UTC hours shift with DST -- for the four
     months of EST the bot applied the lenient killzone RR bar to the wrong
     hour.
"""
import pathlib as _pl
import sys
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))

import inspect
from datetime import datetime, timezone

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


# ---------- the dropped hints ----------
def t1():
    # Accepting a parameter and never reading it is worse than not having it:
    # every caller believes the hint was honoured.
    i = SRC.find('_struct = get_structural_sl_tp(')
    assert i > 0, "the structural TP call vanished"
    call = SRC[i:i + 400]
    assert 'ema50_tp_hint=' in call, \
        "BANKO's and EMA Scalp's targets are still discarded before reaching the order"
    assert 'range_scalp_mode=' in call, "range-scalp capping is still dropped"
check("the target hint actually reaches get_structural_sl_tp", t1)

def t2():
    # The receiving end must still be able to use it.
    sig = inspect.signature(bot.get_structural_sl_tp)
    for p in ('ema50_tp_hint', 'range_scalp_mode'):
        assert p in sig.parameters, f"get_structural_sl_tp lost its {p} parameter"
    sig2 = inspect.signature(bot.get_dynamic_trade_params)
    for p in ('ema50_tp_hint', 'range_scalp_mode'):
        assert p in sig2.parameters, f"get_dynamic_trade_params lost its {p} parameter"
check("both ends of the hint channel still exist", t2)

def t3():
    # BANKO publishes its target through that channel -- if the key is
    # renamed without updating the consumer, the target silently vanishes
    # again with no error anywhere.
    i = SRC.find("'reason':        f'BANKO_SMC_{kz_name}'")
    assert i > 0, "BANKO's setup dict not found"
    body = SRC[max(0, i - 600):i + 900]
    assert "'ema50_tp'" in body, "BANKO no longer publishes its liquidity target"
    assert "'stop_loss'" in body, "BANKO no longer publishes its structural stop"
check("BANKO still publishes its target through the honoured channel", t3)


# ---------- killzones ----------
def t4():
    # A New York killzone must sit at the same NY clock hour year-round.
    # This is the check the hardcoded UTC hours failed for four months a year.
    def ny_hour_of(utc_hour):
        off = (datetime.now(timezone.utc) - bot.ny_now()).total_seconds() / 3600.0
        return int((utc_hour - round(off)) % 24)

    hits = []
    for utc_h in range(24):
        class _TS:
            hour = utc_h
        ok, name = bot._banko_in_killzone(_TS())
        if name == 'NY_AM':
            hits.append(ny_hour_of(utc_h))
    assert hits, "NY_AM killzone never fires at any hour"
    assert all(7 <= h < 10 for h in hits), \
        f"NY_AM fired at NY hours {sorted(set(hits))} -- expected 07:00-10:00 NY"
check("the NY killzone sits at NY clock hours, not fixed UTC hours", t4)

def t5():
    class _TS:
        hour = 20          # 20:00 UTC is outside every killzone in both DST states
    ok, name = bot._banko_in_killzone(_TS())
    assert not ok and name == 'OFF_KILLZONE', f"got {name}"
check("outside every window reports OFF_KILLZONE rather than failing open", t5)

def t6():
    # Off-killzone must be a HIGHER bar, never a block -- BANKO's mandate is
    # all-day. A stricter RR is the intended cost of trading outside them.
    assert bot.config.BANKO_OFF_KILLZONE_MIN_RR > bot.config.BANKO_MIN_RR, \
        "the off-killzone RR bar is not stricter than the killzone one"
    # Window sized to the whole helper -- its docstring and DST comment run
    # long, and a short window would only see prose.
    i = SRC.find('def _banko_in_killzone')
    j = SRC.find('def _banko_find_sweep')
    assert 0 < i < j, "killzone helper not found"
    body = SRC[i:j]
    assert "return False, 'OFF_KILLZONE'" in body, \
        "the helper no longer labels the off-killzone case"
    assert 'raise' not in body, "the killzone helper blocks instead of labelling"
check("off-killzone raises the RR bar, it does not block the trade", t6)

def t7():
    # A sweep is a raid that CLOSES back inside. A bar that closes beyond the
    # level is a break, and trading it is buying into a real move down.
    i = SRC.find('def _banko_find_sweep')
    body = SRC[i:i + 2600]
    assert 'rejected' in body and 'took_liquidity' in body, \
        "the sweep test no longer distinguishes a raid from a break"
    assert 'df.iloc[:-1]' in body, "the sweep search includes the forming bar"
check("BANKO's sweep requires a close back inside, on closed bars only", t7)

def t8():
    # Displacement is what separates a real shift from drift.
    i = SRC.find('def _banko_market_structure_shift')
    body = SRC[i:i + 2200]
    assert 'displacement_mult' in body, "the MSS no longer requires displacement"
    assert 'closed = df.iloc[:-1]' in body, "the MSS reads the forming bar"
check("BANKO's structure shift requires displacement, on closed bars", t8)


# ---------- proscalper ----------
def t9():
    # It documents itself as experimental and outside the live stack; the
    # allow-list must agree, or bot_manager could launch it for a real user.
    core = open(ROOT / 'bot_manager_core.py', encoding='utf-8').read()
    i = core.find('ALLOWED_BOT_SCRIPTS')
    block = core[i:i + 400]
    assert 'proscalper' not in block, \
        "proscalper is allow-listed despite documenting itself as not a production bot"
check("proscalper is not launchable through the bot manager", t9)

def t10():
    ps = open(ROOT / 'proscalper.py', encoding='utf-8').read()
    assert 'df.iloc[:-1]' in ps, "proscalper does not drop the forming bar"
    i = ps.find('def candle_signal')
    body = ps[i:i + 2000]
    assert 'MAX_SPREAD_ATR' in body, "the spread gate is missing from the signal test"
check("proscalper decides on closed bars and gates on spread", t10)

def t11():
    ps = open(ROOT / 'proscalper.py', encoding='utf-8').read()
    # Its own magic number, so it can never manage or close a position
    # belonging to one of the three production bots.
    assert 'MAGIC_NUMBER = 990001' in ps, "proscalper's magic number changed"
    for other in ('hybrid_trading_bot_multiuser.py', 'intraday.py'):
        src = open(ROOT / other, encoding='utf-8').read()
        assert '990001' not in src, f"{other} shares proscalper's magic number"
check("proscalper cannot touch the production bots' positions", t11)

def t12():
    ps = open(ROOT / 'proscalper.py', encoding='utf-8').read()
    for const in ('MAX_OPEN_POSITIONS', 'MAX_TRADES_PER_SYMBOL_PER_HOUR',
                  'EQUITY_STOP_PERCENT', 'TP_R'):
        # Declared AND read somewhere other than its own definition line --
        # this file has a history of config that gates nothing.
        uses = [ln for ln in ps.split('\n')
                if const in ln and not ln.strip().startswith(f'{const} =')
                and not ln.strip().startswith('#') and not ln.strip().startswith('*')]
        assert uses, f"{const} is declared but never enforced"
check("proscalper's risk constants are all actually enforced", t12)


print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
