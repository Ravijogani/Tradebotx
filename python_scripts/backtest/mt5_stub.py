"""
Fake `MetaTrader5` module, installed into sys.modules before the live bot
file is imported for backtesting.

Why this exists: `hybrid_trading_bot_multiuser.py` does `import MetaTrader5
as mt5` at module scope. The real MetaTrader5 package is a Windows-only
wrapper around a running terminal64.exe process -- it can't be installed on
Linux/Mac, and even on Windows it would try to talk to a real, live
terminal. A backtest must never be able to touch a real account, so this
stub is used unconditionally (not just as an environment workaround) --
it's a deliberate safety boundary between "replaying history" and "placing
real orders."

Every function here returns None / a harmless default. The strategy and
analysis functions we actually call during a backtest (calculate_atr,
get_symbol_specs, the strategy_* functions, EdgeEngine, EntryEngine, ...)
either don't touch `mt5.*` at all, or already have a static fallback for
when `mt5.symbol_info()` returns None (see get_symbol_specs in the bot
file, which falls back to the hardcoded SYMBOL_SPECS dict). Order-execution
functions (place_*_trade, initialize_mt5, close_position, ...) are never
called by the backtest harness -- if something unexpectedly does reach
mt5.order_send or similar, it's better that it returns a clearly-fake
"placed" result here than crash, so we log loudly instead.
"""

import logging
from types import SimpleNamespace

_log = logging.getLogger("backtest.mt5_stub")

# --- Timeframe constants (values match the real package's; only used as
# dict keys / equality checks by the bot code, never passed to a real API
# here since copy_rates_from_pos is stubbed out below) ---
TIMEFRAME_M1 = 1
TIMEFRAME_M5 = 5
TIMEFRAME_M15 = 15
TIMEFRAME_M30 = 30
TIMEFRAME_H1 = 16385
TIMEFRAME_H4 = 16388
TIMEFRAME_D1 = 16408

# --- Order/trade constants ---
ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1
ORDER_TYPE_BUY_STOP = 4
ORDER_TYPE_SELL_STOP = 5
ORDER_TIME_GTC = 0
ORDER_TIME_SPECIFIED = 1
ORDER_FILLING_FOK = 0
ORDER_FILLING_IOC = 1
ORDER_FILLING_RETURN = 2
TRADE_ACTION_DEAL = 1
TRADE_ACTION_PENDING = 5
TRADE_ACTION_SLTP = 6
TRADE_RETCODE_DONE = 10009
TRADE_RETCODE_PLACED = 10008
DEAL_ENTRY_OUT = 1
SYMBOL_FILLING_FOK = 1
SYMBOL_FILLING_IOC = 2


def initialize(*args, **kwargs):
    _log.warning("mt5_stub.initialize() called -- backtest harness should never do this")
    return False


def shutdown(*args, **kwargs):
    return None


def last_error():
    return (0, "backtest stub -- no real MT5 connection")


def account_info():
    return None


def symbol_info(symbol):
    # None -> callers (e.g. get_symbol_specs in the bot file) fall back to
    # their static spec table. This is intentional, not a gap: it's the
    # same fallback path live code already has for "broker didn't return
    # info yet."
    return None


def symbol_info_tick(symbol):
    return None


def symbol_select(symbol, enable=True):
    return True


def symbols_get(*args, **kwargs):
    return []


def copy_rates_from_pos(symbol, timeframe, start_pos, count):
    _log.warning(
        "mt5_stub.copy_rates_from_pos() called -- the backtest harness feeds "
        "historical data directly, this should not be reached"
    )
    return None


def copy_rates_from(symbol, timeframe, date_from, count):
    # get_true_day_open() calls this directly (not through get_market_data,
    # so replay_data.py's patch doesn't intercept it). Returning None is
    # safe -- get_true_day_open already treats a failed fetch as "no TDO
    # filter available" and callers already handle that gracefully. See
    # replay_data.py for the backtest-safe TDO replacement that's patched
    # in during AOX replay instead of relying on this stub.
    return None


def copy_rates_range(symbol, timeframe, date_from, date_to):
    return None


def order_send(request):
    _log.error("mt5_stub.order_send() called -- backtest harness must not place real orders")
    return SimpleNamespace(retcode=-1, order=0, comment="blocked by backtest mt5_stub")


def order_calc_profit(order_type, symbol, volume, price_open, price_close):
    """
    P&L for `volume` lots moving from price_open to price_close.

    The live bot sizes positions from this rather than from tick_value /
    tick_size, because it is the broker's own answer and it is available when
    those fields are not. The stub mirrors the sign convention (a BUY that
    falls loses) so a test can tell a correctly-sized lot from a wrong one.

    Contract size 100 matches the metals/CFDs where the real mis-sizing
    happened; FX majors differ, but nothing here depends on the exact figure.
    """
    contract = 100.0
    delta = float(price_close) - float(price_open)
    if order_type == ORDER_TYPE_SELL:
        delta = -delta
    return delta * float(volume) * contract


def order_calc_margin(*args, **kwargs):
    return 0.0


def order_delete(*args, **kwargs):
    return SimpleNamespace(retcode=-1)


def orders_get(*args, **kwargs):
    return []


def positions_get(*args, **kwargs):
    return []


def history_deals_get(*args, **kwargs):
    return []
