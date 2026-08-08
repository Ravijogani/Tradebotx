#!/usr/bin/env python3
"""
CLI entry point for the backtest harness.

Example:
    python3 run_backtest.py \\
        --symbol XAUUSDm \\
        --data-dir ./history/XAUUSDm \\
        --m1 XAUUSDm_M1.csv --m5 XAUUSDm_M5.csv --h1 XAUUSDm_H1.csv \\
        --out trades.csv

The CSVs are produced by export_mt5_history.py, run separately on a
machine with a live MT5 terminal (this harness itself never touches MT5 --
see mt5_stub.py).
"""

import argparse
import sys

from .bot_loader import import_bot_module
from .data import HistoricalDataset
from .engine import BacktestEngine, BacktestConfig
from .report import summarize, print_report, write_trade_csv


def main():
    p = argparse.ArgumentParser(description="TradeBotX strategy backtest harness")
    p.add_argument("--symbol", required=True, help="Symbol name as used in the live bot's SYMBOL_SPECS, e.g. XAUUSDm")
    p.add_argument("--data-dir", required=True, help="Directory containing the historical CSVs")
    p.add_argument("--m1", required=True, help="M1 CSV filename (relative to --data-dir)")
    p.add_argument("--m5", required=True, help="M5 CSV filename (relative to --data-dir)")
    p.add_argument("--h1", required=True, help="H1 CSV filename (relative to --data-dir)")
    p.add_argument("--rr", type=float, default=2.0, help="Take-profit distance as a multiple of SL distance (default 2.0)")
    p.add_argument("--spread", type=float, default=None, help="Override the default per-symbol spread model (price units)")
    p.add_argument("--out", default=None, help="Write the trade ledger to this CSV path")
    args = p.parse_args()

    print(f"Loading bot module (mt5 stubbed, no live connection)...")
    bot = import_bot_module()

    print(f"Loading historical data for {args.symbol}...")
    dataset = HistoricalDataset.from_csv_dir(
        args.symbol, args.data_dir,
        {"M1": args.m1, "M5": args.m5, "H1": args.h1},
    )
    for tf, df in dataset.frames.items():
        print(f"  {tf}: {len(df)} bars, {df['time'].iloc[0]} -> {df['time'].iloc[-1]}")

    config = BacktestConfig(symbol=args.symbol, rr_multiple=args.rr, spread=args.spread)
    engine = BacktestEngine(bot, dataset, config)

    print("Running walk-forward replay (this can take a while on large datasets)...")
    trades = engine.run()

    stats = summarize(trades)
    print_report(trades, stats)

    if args.out:
        write_trade_csv(trades, args.out)
        print(f"\nTrade ledger written to {args.out}")


if __name__ == "__main__":
    sys.exit(main())
