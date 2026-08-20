"""
The 0.15-lot gold trade: 28.6% of the account on one position.

Live on 2026-08-20, on a $161.48 account:

    xauusdm  sell  0.15  entry 4467.388  SL 4470.469   ->  -46.22

A 3.081-point stop on 0.15 lots is $46.22 at risk -- 28.6% of the account,
where CapitalController had intended 1.5%. Nineteen times the intended risk
and fifteen times the minimum lot. Every non-gold position that day was
0.01-0.02, because those symbols had usable tick data.

TWO defects, and the second is why the first was never caught:

  1. When trade_tick_value / trade_tick_size were unavailable, sizing fell
     back to
         lot_raw = risk_money / (margin_per_lot * sl_dist_price)
     whose units are dollars / (dollars x points) -- meaningless. On a
     high-leverage broker the margin for one lot is small, the denominator
     collapses, and the lot explodes. Exness offers unlimited leverage under
     $1k, so this is not a corner case for this account.

  2. The risk check in that same branch read
         actual_risk_dollars = risk_money * (lot_size / lot_raw)
     which scales the INTENDED risk by the lot rounding and therefore returns
     roughly the intended figure however wrong lot_raw was. It reported 1.5%
     for a position risking 28.6%, and the hard cap passed it. A safety check
     computed from the same assumption as the thing it checks cannot fail --
     it can only confirm.

Both now go through mt5.order_calc_profit: the broker's own answer for what
one lot loses at this stop, available when the tick fields are not.
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

import io
import tokenize

ROOT = _pl.Path(__file__).resolve().parent.parent
SRC = open(ROOT / 'hybrid_trading_bot_multiuser.py', encoding='utf-8').read()


def code_only(text: str) -> str:
    """
    Source with comments and string literals stripped.

    Necessary because the comments in this file QUOTE the formulas that were
    removed -- explaining a deleted bug is how you stop it coming back, and a
    raw substring search would then fail on the explanation rather than on
    the code.
    """
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type not in (tokenize.COMMENT, tokenize.STRING):
                out.append(tok.string)
    except tokenize.TokenError:
        return text
    return " ".join(out)


CODE = code_only(SRC)

EQUITY, ENTRY, STOP = 161.48, 4467.388, 4470.469
SL_DIST = abs(STOP - ENTRY)


def t1():
    # The arithmetic of the live trade, so the numbers in this file are not
    # taken on trust.
    risk = 0.15 * SL_DIST * 100          # 100 oz per lot
    assert abs(risk - 46.22) < 0.5, f"reconstructed risk {risk:.2f}, screenshot said 46.22"
    assert risk / EQUITY * 100 > 25, "reconstruction does not reproduce the >25% exposure"
check("the live 0.15-lot trade really did risk 28.6% of the account", t1)

def t2():
    # What it should have been.
    for pct in (0.25, 1.0, 1.5):
        lot = (EQUITY * pct / 100) / (SL_DIST * 100)
        assert lot < 0.01, f"at {pct}% the correct lot is {lot:.4f}, above min lot"
check("correct sizing floors at min lot 0.01, not 0.15", t2)

def t3():
    # The dangerous fallback must be gone.
    assert 'margin_per_lot' not in CODE, \
        "sizing still divides by margin x distance -- dimensionally meaningless"
    assert 'order_calc_profit' in CODE, "sizing does not ask the broker what a lot risks"
check("position size no longer derives from margin", t3)

def t4():
    # And it must fail closed rather than guess.
    i = SRC.find('cannot determine risk per lot')
    assert i > 0, "there is still a blind-sizing path"
    body = SRC[i:i + 900]
    assert 'return False' in body, "an unsizeable trade is still placed"
    assert 'send_telegram_notification' in body, "a skipped trade is silent"
check("a trade that cannot be sized is refused, not guessed", t4)

def t5():
    # THE ONE THAT MATTERS: the check must not be computed from the thing it
    # is checking.
    i = SRC.find('actual_risk_dollars')
    body = SRC[max(0, i - 1500):i + 900]
    assert '_risk_per_lot' in body, \
        "actual risk is still derived from the intended risk rather than measured"
    j = SRC.find('actual_risk_dollars = lot_size * _risk_per_lot')
    assert j > 0, "actual risk is not computed from the broker's per-lot figure"
check("the risk check is measured independently of the lot calculation", t5)

def t6():
    # AOX sized itself the same way and had its own bad fallback: sl_dist * 10
    # assumes a $10/point instrument, true of nothing this bot trades.
    i = SRC.find('def execute_aox_layer')
    j = SRC.find('\ndef ', i + 10)
    body_code = code_only(SRC[i:j])
    assert 'sl_dist * 10' not in body_code, "AOX still assumes $10 per point"
    assert 'order_calc_profit' in body_code, "AOX does not ask the broker either"
    assert 'refusing to size this layer blind' in SRC[i:j], "AOX still guesses"
check("AOX sizes from the broker too, and fails closed", t6)

def t7():
    # The broker call must be sign-agnostic -- it returns a NEGATIVE number
    # for a losing move, and a lot derived from a negative risk would be
    # negative or rejected.
    for fn_name in ('order_calc_profit',):
        for guard in ('abs(float(_p))', 'abs(float(_ap))'):
            assert guard in SRC, f"{guard} missing -- sign not handled"
check("the broker's P&L sign is handled, not passed through", t7)

def t8():
    # Sanity against the stub, which mirrors the real sign convention.
    from backtest.bot_loader import import_bot_module
    bot = import_bot_module()
    import MetaTrader5 as mt5
    loss = mt5.order_calc_profit(mt5.ORDER_TYPE_SELL, "XAUUSDm", 1.0, ENTRY, STOP)
    assert loss < 0, "a SELL stopped out above entry should lose"
    risk_per_lot = abs(loss)
    lot = (EQUITY * 1.5 / 100) / risk_per_lot
    assert lot < 0.01, f"broker-derived sizing gives {lot:.4f}, still above min lot"
check("broker-derived sizing reproduces the correct sub-min-lot answer", t8)


print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
