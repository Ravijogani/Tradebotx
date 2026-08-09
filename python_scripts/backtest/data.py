"""
Historical bar data loading for the backtest harness.

Loads a CSV per (symbol, timeframe) into a pandas DataFrame shaped exactly
like what the live bot's get_market_data() produces from
mt5.copy_rates_from_pos() -- same column names, same dtypes -- so the
strategy functions can't tell the difference between a live snapshot and a
replayed historical window.

Expected CSV columns (header row required):
    time,open,high,low,close,tick_volume[,spread][,real_volume]

`time` must be parseable by pandas.to_datetime (ISO 8601 recommended,
e.g. 2024-01-02 09:30:00). spread/real_volume are optional and default to
0 if missing -- they're rarely read by the strategy logic, but included
for shape-compatibility with anything that touches them.

Use export_mt5_history.py (run on the Windows machine with a live MT5
terminal) to produce these CSVs directly from your broker's history.
"""

from pathlib import Path
from typing import Dict

import pandas as pd

REQUIRED_COLUMNS = ["time", "open", "high", "low", "close"]
OPTIONAL_COLUMNS = {"tick_volume": 0, "spread": 0, "real_volume": 0}


def load_bars_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing required column(s) {missing}. "
                          f"Expected at least {REQUIRED_COLUMNS}.")

    df["time"] = pd.to_datetime(df["time"], utc=True)
    for col, default in OPTIONAL_COLUMNS.items():
        if col not in df.columns:
            df[col] = default

    df = df.sort_values("time").reset_index(drop=True)
    # Basic sanity check -- OHLC integrity. A malformed export (e.g. a
    # timezone-mangled or duplicated bar) can silently produce nonsense
    # signals, so fail loudly rather than backtest against broken data.
    bad = df[(df["high"] < df["low"]) |
             (df["high"] < df["open"]) | (df["high"] < df["close"]) |
             (df["low"] > df["open"]) | (df["low"] > df["close"])]
    if len(bad) > 0:
        raise ValueError(
            f"{path}: {len(bad)} bar(s) fail basic OHLC integrity checks "
            f"(high/low inconsistent with open/close). First bad row:\n{bad.iloc[0]}"
        )
    return df


class HistoricalDataset:
    """
    Holds loaded bar data for one symbol across the timeframes a backtest
    run needs (e.g. M1/M5/M15/H1), and gives the harness a no-lookahead
    window: `window(timeframe, as_of, bars)` never returns a bar whose
    `time` is >= as_of.
    """

    def __init__(self, symbol: str, frames: Dict[str, pd.DataFrame]):
        self.symbol = symbol
        self.frames = frames  # e.g. {"M1": df, "M5": df, "M15": df, "H1": df}

    @classmethod
    def from_csv_dir(cls, symbol: str, csv_dir: str, timeframes: Dict[str, str]):
        """
        timeframes: {"M1": "EURUSD_M1.csv", "M5": "EURUSD_M5.csv", ...}
        (filenames relative to csv_dir)
        """
        base = Path(csv_dir)
        frames = {}
        for tf, filename in timeframes.items():
            frames[tf] = load_bars_csv(str(base / filename))
        return cls(symbol, frames)

    def window(self, timeframe: str, as_of: pd.Timestamp, bars: int) -> pd.DataFrame:
        """
        Returns up to `bars` rows of `timeframe` data strictly before
        `as_of`, matching the shape get_market_data(symbol, tf, bars)
        returns live (most-recent-last). Raises KeyError if `timeframe`
        wasn't loaded.
        """
        df = self.frames[timeframe]
        visible = df[df["time"] < as_of]
        return visible.tail(bars).reset_index(drop=True)

    def replay_timestamps(self, timeframe: str):
        """All bar-close timestamps for the given timeframe, in order --
        the harness iterates these as the sequence of decision points."""
        return list(self.frames[timeframe]["time"])
