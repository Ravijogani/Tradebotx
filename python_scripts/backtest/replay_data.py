"""
Patches the imported bot module's `get_market_data` and `get_true_day_open`
to serve historical, no-lookahead data instead of live MT5 calls, for the
duration of one replay step.

Why this exists (beyond time_travel.py's datetime patch): several live
helper functions -- most importantly get_market_regime_and_trend(), which
every wired strategy depends on for its `trend` argument -- pull their own
data by calling get_market_data(symbol, timeframe, bars) internally rather
than receiving a DataFrame as a parameter. Reimplementing that logic
separately in the harness would risk exactly the kind of silent drift this
whole harness exists to prevent. Patching get_market_data instead means
get_market_regime_and_trend (and anything else that calls it) runs
unmodified and automatically stays in sync with the live file.
"""

from contextlib import contextmanager
from typing import Dict, Optional

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
def replay_context(bot_module, dataset: HistoricalDataset, as_of: pd.Timestamp,
                    extra_symbols: Optional[Dict[str, HistoricalDataset]] = None):
    """
    Usage:
        with replay_context(bot, dataset, as_of):
            regime, trend = bot.get_market_regime_and_trend(symbol)

    Combines the datetime freeze (see time_travel.py) with the
    get_market_data patch so any live helper called inside the block sees
    a fully consistent "as of `as_of`" view of the world.

    `extra_symbols`: optional {symbol: HistoricalDataset} for strategies
    that pull a SECOND symbol's data internally (e.g. check_smt_divergence,
    called by AOX, checks a correlated pair like XAUUSDm<->XAGUSDm). If a
    requested symbol isn't `dataset.symbol` and isn't in `extra_symbols`,
    the patch returns None -- NOT dataset's data mislabeled as the wrong
    symbol's. Every such caller in this codebase already treats a None
    return as "no data, pass through / skip" (see check_smt_divergence's
    own "if df_main is None or df_corr is None: return True"), so this is
    a safe, honest degradation, not a silent correctness bug.
    """
    from .time_travel import frozen_at

    extra_symbols = extra_symbols or {}
    original_get_market_data = bot_module.get_market_data
    original_get_true_day_open = bot_module.get_true_day_open

    def _dataset_for(symbol: str) -> Optional[HistoricalDataset]:
        if symbol == dataset.symbol:
            return dataset
        return extra_symbols.get(symbol)

    def _patched_get_market_data(symbol, timeframe, bars=200):
        ds = _dataset_for(symbol)
        if ds is None:
            return None
        tf_label = TIMEFRAME_LABELS.get(timeframe)
        if tf_label is None or tf_label not in ds.frames:
            return None
        window = ds.window(tf_label, as_of, bars)
        return window if len(window) > 0 else None

    def _patched_get_true_day_open(symbol):
        # Live version fetches the M5 candle at midnight EST via a direct
        # mt5.copy_rates_from call (not routed through get_market_data, so
        # the patch above doesn't cover it). Backtest-safe equivalent:
        # find the M5 bar closest to today's NY midnight in the loaded
        # dataset, same as the live function's own approach, minus the
        # live MT5 call.
        ds = _dataset_for(symbol)
        if ds is None or "M5" not in ds.frames:
            return None
        # NY midnight (EST/EDT) as a UTC timestamp for the day `as_of` falls in.
        # Matches the live function's own DST-naive-ish approach closely
        # enough for backtesting: EST is UTC-5, EDT is UTC-4; using -5
        # year-round would be off by up to an hour during EDT, which for a
        # discount/premium filter is a minor, documented approximation.
        ny_offset_hours = 5
        midnight_utc = pd.Timestamp(as_of.date(), tz="UTC") + pd.Timedelta(hours=ny_offset_hours)
        m5 = ds.frames["M5"]
        candidates = m5[(m5["time"] >= midnight_utc) & (m5["time"] < midnight_utc + pd.Timedelta(minutes=15))]
        if len(candidates) == 0:
            return None
        return float(candidates.iloc[0]["open"])

    bot_module.get_market_data = _patched_get_market_data
    bot_module.get_true_day_open = _patched_get_true_day_open
    try:
        with frozen_at(bot_module, as_of.to_pydatetime()):
            yield
    finally:
        bot_module.get_market_data = original_get_market_data
        bot_module.get_true_day_open = original_get_true_day_open
