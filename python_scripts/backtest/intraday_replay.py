"""
Patches the imported intraday.py module's `get_market_data` and freezes its
`datetime.now()`, for the duration of one replay step -- same reasoning and
mechanics as replay_data.py (which does this for hybrid_trading_bot_
multiuser.py), kept as its own file because intraday.py is a separate
module with a differently-shaped set of live helpers.

Why this exists: context_decision_engine() -- the real, live entry point
this driver calls -- doesn't take OHLC windows as arguments the way
structural_swing_pro.py's detect_structural_swing_signal() does. It calls
get_market_data(symbol, timeframe, bars) itself, repeatedly, both directly
and through nested live helpers (NarrativeIntentEngine.build,
get_market_regime_and_trend, and all five strategy_* functions --
strategy_aox_model, strategy_h1_orderblock_retest,
strategy_h4_trend_pullback, strategy_london_open_breakout,
reversal_precision_engine). Patching get_market_data once here means every
one of those keeps running completely unmodified and automatically stays
in sync with the live file -- reimplementing that call graph in the
harness would risk exactly the kind of silent drift this whole harness
exists to prevent (same principle replay_data.py's own docstring states).

Freezing datetime.now() matters for a different reason here than usual:
is_in_kill_zone(), get_active_macro_window(), get_current_session(), and
strategy_london_open_breakout()'s own prime-session check all read the
real wall clock directly rather than deriving "now" from the bar being
evaluated. Without the freeze, a backtest run would evaluate every
session/kill-zone/macro-window gate against whatever moment the script
happens to be running, not the historical bar's time -- silently wrong in
exactly the strategies that gate on time of day (Strategy C especially).
"""

from contextlib import contextmanager
from typing import Dict, Optional

import pandas as pd

from .data import HistoricalDataset
from .time_travel import frozen_at

# mt5 timeframe constant -> HistoricalDataset frame key. Matches
# mt5_stub.py's constants (same values the real MetaTrader5 package uses).
# Extends replay_data.py's mapping with D1, which intraday.py's
# context_decision_engine reads via config.DAILY_TF for narrative bias.
TIMEFRAME_LABELS = {
    1: "M1",
    5: "M5",
    15: "M15",
    30: "M30",
    16385: "H1",
    16388: "H4",
    16408: "D1",
}


@contextmanager
def replay_context(bot_module, dataset: HistoricalDataset, as_of: pd.Timestamp):
    """
    Usage:
        with replay_context(bot, dataset, as_of):
            signal = bot.context_decision_engine(symbol, ...)

    Single-symbol only (intraday_driver.py backtests one symbol at a time,
    same as every other driver in this harness) -- unlike replay_data.py's
    version, there's no extra_symbols parameter because none of
    intraday.py's live strategies read a second symbol's data.
    """
    original_get_market_data = bot_module.get_market_data

    def _patched_get_market_data(symbol, timeframe, bars=500):
        if symbol != dataset.symbol:
            return None
        tf_label = TIMEFRAME_LABELS.get(timeframe)
        if tf_label is None or tf_label not in dataset.frames:
            return None
        window = dataset.window(tf_label, as_of, bars)
        return window if len(window) > 0 else None

    bot_module.get_market_data = _patched_get_market_data
    try:
        with frozen_at(bot_module, as_of.to_pydatetime()):
            yield
    finally:
        bot_module.get_market_data = original_get_market_data
