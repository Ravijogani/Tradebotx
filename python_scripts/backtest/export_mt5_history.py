#!/usr/bin/env python3
"""
Run this ON the Windows machine that has a real MT5 terminal installed and
logged in (the same one hybrid_trading_bot_multiuser.py runs on) -- it
exports historical bars to the CSV format the backtest harness expects.
This script is NOT part of the harness itself and never gets its MT5 calls
stubbed; it needs the real terminal to pull real history.

Usage:
    python export_mt5_history.py --symbol XAUUSDm --days 365 --out-dir ./history/XAUUSDm

Produces XAUUSDm_M1.csv, XAUUSDm_M5.csv, XAUUSDm_H1.csv in --out-dir.
"""

import argparse
import os
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5
import pandas as pd

TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "H1": mt5.TIMEFRAME_H1,
}


def export_symbol(symbol: str, days: int, out_dir: str):
    if not mt5.initialize():
        raise RuntimeError(f"mt5.initialize() failed: {mt5.last_error()}. "
                            f"Make sure the MT5 terminal is running and logged in.")

    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Could not select {symbol} in Market Watch -- check the symbol name matches your broker exactly.")

    os.makedirs(out_dir, exist_ok=True)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    for tf_name, tf_const in TIMEFRAMES.items():
        rates = mt5.copy_rates_range(symbol, tf_const, start, end)
        if rates is None or len(rates) == 0:
            print(f"  WARNING: no {tf_name} data returned for {symbol} "
                  f"(broker may not retain {days} days of {tf_name} history)")
            continue
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        out_path = os.path.join(out_dir, f"{symbol}_{tf_name}.csv")
        df.to_csv(out_path, index=False)
        print(f"  {tf_name}: {len(df)} bars -> {out_path}  ({df['time'].iloc[0]} -> {df['time'].iloc[-1]})")

    mt5.shutdown()


def main():
    p = argparse.ArgumentParser(description="Export MT5 historical bars to CSV for the backtest harness")
    p.add_argument("--symbol", required=True, help="Symbol exactly as it appears in your broker's Market Watch, e.g. XAUUSDm")
    p.add_argument("--days", type=int, default=365, help="How many days of history to pull (default 365)")
    p.add_argument("--out-dir", required=True, help="Output directory for the CSVs")
    args = p.parse_args()

    print(f"Exporting {args.days} days of history for {args.symbol}...")
    export_symbol(args.symbol, args.days, args.out_dir)
    print("Done.")


if __name__ == "__main__":
    main()
