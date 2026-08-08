#!/usr/bin/env python3
"""
CLI entry point for the backtest harness.

Run one strategy:
    python3 -m backtest.run_backtest --symbol XAUUSDm --data-dir ./history/XAUUSDm \\
        --m1 XAUUSDm_M1.csv --m5 XAUUSDm_M5.csv --h1 XAUUSDm_H1.csv \\
        --strategy ICT_KILLZONE --out trades.csv

Run every registered strategy and compare:
    python3 -m backtest.run_backtest --symbol XAUUSDm --data-dir ./history/XAUUSDm \\
        --m1 XAUUSDm_M1.csv --m5 XAUUSDm_M5.csv --h1 XAUUSDm_H1.csv --m15 XAUUSDm_M15.csv \\
        --h4 XAUUSDm_H4.csv --all --out trades.csv

See README.md for which strategies are LIVE vs NOT LIVE, and which
timeframes each one needs (SHAAKUNI_SSM needs --h4; nothing else does).
"""

import argparse
import sys

from .bot_loader import import_bot_module
from .data import HistoricalDataset
from .engine import BacktestEngine, BacktestConfig
from .report import summarize, print_report, write_trade_csv
from .strategies_registry import ALL_STRATEGIES, STRATEGIES_BY_NAME


def main():
    p = argparse.ArgumentParser(description="TradeBotX strategy backtest harness")
    p.add_argument("--symbol", required=True, help="Symbol name as used in the live bot's SYMBOL_SPECS, e.g. XAUUSDm")
    p.add_argument("--data-dir", required=True, help="Directory containing the historical CSVs")
    p.add_argument("--m1", required=True, help="M1 CSV filename (relative to --data-dir)")
    p.add_argument("--m5", required=True, help="M5 CSV filename (relative to --data-dir)")
    p.add_argument("--h1", required=True, help="H1 CSV filename (relative to --data-dir)")
    p.add_argument("--m15", default=None, help="M15 CSV filename (only needed for SMC_FVG_OB_RETEST's HTF confluence check)")
    p.add_argument("--h4", default=None, help="H4 CSV filename (only needed for SHAAKUNI_SSM)")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--strategy", choices=list(STRATEGIES_BY_NAME.keys()), help="Run a single strategy")
    group.add_argument("--all", action="store_true", help="Run every registered strategy and print a report for each")
    p.add_argument("--rr", type=float, default=2.0, help="Take-profit distance as a multiple of SL distance, for strategies that don't compute their own TP (default 2.0)")
    p.add_argument("--spread", type=float, default=None, help="Override the default per-symbol spread model (price units)")
    p.add_argument("--out", default=None, help="Write the combined trade ledger to this CSV path")
    args = p.parse_args()

    print("Loading bot module (MT5/Supabase stubbed, no live connection)...")
    bot = import_bot_module()

    print(f"Loading historical data for {args.symbol}...")
    timeframes = {"M1": args.m1, "M5": args.m5, "H1": args.h1}
    if args.m15:
        timeframes["M15"] = args.m15
    if args.h4:
        timeframes["H4"] = args.h4
    dataset = HistoricalDataset.from_csv_dir(args.symbol, args.data_dir, timeframes)
    for tf, df in dataset.frames.items():
        print(f"  {tf}: {len(df)} bars, {df['time'].iloc[0]} -> {df['time'].iloc[-1]}")

    config = BacktestConfig(symbol=args.symbol, rr_multiple=args.rr, spread=args.spread)

    adapters = [STRATEGIES_BY_NAME[args.strategy]] if args.strategy else ALL_STRATEGIES

    all_trades = []
    for adapter in adapters:
        if adapter.name == "SHAAKUNI_SSM" and "H4" not in dataset.frames:
            print(f"\nSkipping {adapter.name}: needs --h4 (not provided)")
            continue
        print(f"\nRunning {adapter.name}...")
        engine = BacktestEngine(bot, dataset, config, adapter)
        trades = engine.run()
        stats = summarize(trades)
        print_report(adapter.name, adapter.live, trades, stats)
        all_trades.extend(trades)

    if args.out and all_trades:
        write_trade_csv(all_trades, args.out)
        print(f"Combined trade ledger ({len(all_trades)} trades) written to {args.out}")


if __name__ == "__main__":
    sys.exit(main())
