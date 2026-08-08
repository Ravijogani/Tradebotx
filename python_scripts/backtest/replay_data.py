"""
Patches the imported bot module's `get_market_data` to serve historical,
no-lookahead windows instead of live MT5 data, for the duration of one
replay step.

Why this exists (beyond time_travel.py's datetime patch): several live
helper functions -- most importantly get_market_regime_and_trend(), which
every wired strategy depends on for its `trend` argument -- pull their own
data by calling get_market_data(symbol, timeframe, bars) internally rather
than receiving a DataFrame as a parameter. Reimplementing that trend logic
separately in the harness would risk exactly the kind of silent drift this
whole harness exists to prevent. Patching get_market_data instead means
get_market_regime_and_trend (and anything else that calls it) runs
unmodified and automatically stays in sync with the live file.
"""

from contextlib import contextmanager

import pandas as pd

from .data import HistoricalDataset

# mt5 timeframe constant -> HistoricalDataset frame key. Values match
# mt5_stub.py (and the real MetaTrader5 package, which uses the same
# constants) -- not every constant needs an entry, only the ones any
# wired strategy's dependencies actually request.
TIMEFRAME_LABELS = {
    1: "M1",
    5: "M5",
    15: "M15",
    30: "M30",
    16385: "H1",
    16388: "H4",
}


@contextmanager
def replay_context(bot_module, dataset: HistoricalDataset, as_of: pd.Timestamp):
    """
    Usage:
        with replay_context(bot, dataset, as_of):
            regime, trend = bot.get_market_regime_and_trend(symbol)

    Combines the datetime freeze (see time_travel.py) with the
    get_market_data patch so any live helper called inside the block sees
    a fully consistent "as of `as_of`" view of the world.
    """
    from .time_travel import frozen_at

    original_get_market_data = bot_module.get_market_data

    def _patched(symbol, timeframe, bars=200):
        tf_label = TIMEFRAME_LABELS.get(timeframe)
        if tf_label is None or tf_label not in dataset.frames:
            return None
        window = dataset.window(tf_label, as_of, bars)
        return window if len(window) > 0 else None

    bot_module.get_market_data = _patched
    try:
        with frozen_at(bot_module, as_of.to_pydatetime()):
            yield
    finally:
        bot_module.get_market_data = original_get_market_data
