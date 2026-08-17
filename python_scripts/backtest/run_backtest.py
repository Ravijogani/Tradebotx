#!/usr/bin/env python3
"""
CLI entry point for the backtest harness.

Run one strategy:
    python3 -m backtest.run_backtest --symbol XAUUSDm --data-dir ./history/XAUUSDm \\
        --m5 XAUUSDm_M5.csv --h1 XAUUSDm_H1.csv --strategy SWAPPY_3C --out trades.csv

Run every registered strategy and compare (--all also runs AOX):
    python3 -m backtest.run_backtest --symbol XAUUSDm --data-dir ./history/XAUUSDm \\
        --m1 XAUUSDm_M1.csv --m5 XAUUSDm_M5.csv --h1 XAUUSDm_H1.csv \\
        --h4 XAUUSDm_H4.csv --all --out trades.csv

Run just AOX, with its SMT-divergence correlated pair:
    python3 -m backtest.run_backtest --symbol XAUUSDm --data-dir ./history/XAUUSDm \\
        --m1 XAUUSDm_M1.csv --m5 XAUUSDm_M5.csv --h1 XAUUSDm_H1.csv \\
        --strategy AOX --corr-symbol XAGUSDm --corr-m15 XAGUSDm_M15.csv --out trades.csv

Run STRUCTURAL_SWING (structural_swing_pro.py -- a separate script/module,
not a StrategyAdapter, see swing_driver.py):
    python3 -m backtest.run_backtest --symbol XAUUSDm --data-dir ./history/XAUUSDm \\
        --m5 XAUUSDm_M5.csv --h1 XAUUSDm_H1.csv --h4 XAUUSDm_H4.csv --d1 XAUUSDm_D1.csv \\
        --strategy STRUCTURAL_SWING --out trades.csv

Run INTRADAY (intraday.py's context_decision_engine cascade -- Strategies
A/B/C/D/E -- also a separate script/module, see intraday_driver.py):
    python3 -m backtest.run_backtest --symbol XAUUSDm --data-dir ./history/XAUUSDm \\
        --m5 XAUUSDm_M5.csv --h1 XAUUSDm_H1.csv --h4 XAUUSDm_H4.csv \\
        --m15 XAUUSDm_M15.csv --d1 XAUUSDm_D1.csv --strategy INTRADAY --out trades.csv

See README.md for which strategies are LIVE, and which timeframes each
one needs. --m1 is optional -- only AOX and INTRADAY's Strategy E (AOX
Sniper) need it (both skip that one piece cleanly, not crashed, if
omitted); SHAAKUNI_SSM/SWAPPY_3C/EMA_SCALP_CROSS don't touch M1 at all.
--h4 is needed for SHAAKUNI_SSM, STRUCTURAL_SWING, and INTRADAY.
AOX's SMT-divergence gate additionally needs --corr-symbol/--corr-m15,
optional on top of --m1. --d1 is needed for STRUCTURAL_SWING and INTRADAY;
export_mt5_history.py doesn't export D1 by default -- resample H4 to D1
(pandas .resample('1D')) if you don't have a native D1 export yet. --m15 is
needed for INTRADAY (its M15 confirmation windows) in addition to AOX's
--corr-m15 use.
"""

import argparse
import sys

from .aox_driver import AoxDriverConfig, run_aox_backtest
from .balance_fade_driver import BalanceFadeDriverConfig, run_balance_fade_backtest
from .bot_loader import import_bot_module
from .data import HistoricalDataset
from .engine import BacktestEngine, BacktestConfig
from .intraday_driver import IntradayDriverConfig, run_intraday_backtest
from .intraday_loader import import_intraday_module
from .report import summarize, print_report, write_trade_csv
from .walk_forward import run_walk_forward, print_walk_forward_report
from .strategies_registry import ALL_STRATEGIES, STRATEGIES_BY_NAME
from .swing_driver import SwingDriverConfig, run_swing_backtest
from .swing_loader import import_swing_bot_module

AOX_NAME = "AOX"  # not a StrategyAdapter (see aox_driver.py for why) -- handled as a separate CLI path below
STRUCTURAL_SWING_NAME = "STRUCTURAL_SWING"  # also not a StrategyAdapter -- separate script/module, see swing_driver.py
INTRADAY_NAME = "INTRADAY"  # also not a StrategyAdapter -- separate script/module, see intraday_driver.py
BALANCE_FADE_NAME = "BALANCE_FADE"  # also not a StrategyAdapter -- see balance_fade_driver.py / market_intelligence.py

# No StrategyAdapter here touches M1 anymore -- SHAAKUNI_SSM/SWAPPY_3C/
# EMA_SCALP_CROSS all confirmed M1-free by reading each adapter. Only AOX
# (handled separately below, not a StrategyAdapter) needs it.


def main():
    p = argparse.ArgumentParser(description="TradeBotX strategy backtest harness")
    p.add_argument("--symbol", required=True, help="Symbol name as used in the live bot's SYMBOL_SPECS, e.g. XAUUSDm")
    p.add_argument("--data-dir", required=True, help="Directory containing the historical CSVs")
    p.add_argument("--m1", default=None,
                    help="M1 CSV filename (relative to --data-dir). Only AOX actually needs M1 -- "
                         "SHAAKUNI_SSM/SWAPPY_3C/EMA_SCALP_CROSS don't touch it. "
                         "Omit it and AOX is skipped with a clear message; everything else still runs.")
    p.add_argument("--m5", required=True, help="M5 CSV filename (relative to --data-dir)")
    p.add_argument("--h1", required=True, help="H1 CSV filename (relative to --data-dir)")
    p.add_argument("--m15", default=None, help="M15 CSV filename. Not needed by any currently-live strategy "
                                                 "(kept for AOX's --corr-m15 correlated-pair use and any future "
                                                 "strategy that needs the primary symbol's own M15)")
    p.add_argument("--m30", default=None, help="M30 CSV filename. Optional -- exercises the SHAAKUNI_SSM/"
                                                 "SWAPPY_3C/EMA_SCALP_CROSS shared M30 Change-of-Character veto "
                                                 "(classify_m30_character, see _get_trend in strategies_registry.py). "
                                                 "Without it, that one gate is simply not exercised; no strategy "
                                                 "requires it to run. No native M30 export yet -- resample M15 to "
                                                 "M30 (pandas .resample('30min')) if you don't have one.")
    p.add_argument("--h4", default=None, help="H4 CSV filename (needed for SHAAKUNI_SSM and STRUCTURAL_SWING)")
    p.add_argument("--d1", default=None, help="D1 CSV filename (only needed for STRUCTURAL_SWING)")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--strategy", choices=list(STRATEGIES_BY_NAME.keys()) + [AOX_NAME, STRUCTURAL_SWING_NAME, INTRADAY_NAME, BALANCE_FADE_NAME], help="Run a single strategy")
    group.add_argument("--all", action="store_true", help="Run every registered strategy (incl. AOX, STRUCTURAL_SWING, INTRADAY, BALANCE_FADE) and print a report for each")
    p.add_argument("--rr", type=float, default=2.0, help="Take-profit distance as a multiple of SL distance, for strategies that don't compute their own TP (default 2.0)")
    p.add_argument("--spread", type=float, default=None, help="Override the default per-symbol spread model (price units)")
    p.add_argument("--out", default=None, help="Write the combined trade ledger to this CSV path")
    p.add_argument("--rejections-out", default=None, metavar="PATH",
                   help="Write the setups the strategies evaluated and DECLINED to this JSONL "
                        "path, so 'which gate actually does the rejecting' becomes a number. "
                        "Bounded (decision_journal._MAX_REJECTIONS) so a long run cannot exhaust "
                        "memory; truncation is reported rather than hidden.")
    p.add_argument("--walk-forward", type=int, default=None, metavar="N",
                   help="Instead of one pooled run, split the history into N sequential windows and "
                        "report each independently -- does the edge persist across time, or did it come "
                        "from one lucky stretch? See backtest/walk_forward.py for what this does and "
                        "does not prove. Applies to the M5 strategies (SHAAKUNI_SSM/SWAPPY_3C/"
                        "EMA_SCALP_CROSS); the separate AOX/SWING/INTRADAY/BALANCE_FADE drivers are "
                        "skipped in this mode.")
    p.add_argument("--min-trades", type=int, default=10,
                   help="Walk-forward only: windows with fewer trades than this are flagged as too thin "
                        "to interpret rather than being averaged in silently (default 10)")
    p.add_argument("--corr-symbol", default=None,
                    help="AOX only: correlated symbol for the SMT divergence check (e.g. XAGUSDm for XAUUSDm). "
                         "Without this, check_smt_divergence sees no correlated data and passes through with no veto -- "
                         "AOX still runs, just without that one confirmation gate exercised.")
    p.add_argument("--corr-m15", default=None, help="AOX only: M15 CSV filename for --corr-symbol (relative to --data-dir)")
    args = p.parse_args()

    print("Loading bot module (MT5/Supabase stubbed, no live connection)...")
    bot = import_bot_module()

    print(f"Loading historical data for {args.symbol}...")
    timeframes = {"M5": args.m5, "H1": args.h1}
    if args.m1:
        timeframes["M1"] = args.m1
    if args.m15:
        timeframes["M15"] = args.m15
    if args.m30:
        timeframes["M30"] = args.m30
    if args.h4:
        timeframes["H4"] = args.h4
    if args.d1:
        timeframes["D1"] = args.d1
    dataset = HistoricalDataset.from_csv_dir(args.symbol, args.data_dir, timeframes)
    for tf, df in dataset.frames.items():
        print(f"  {tf}: {len(df)} bars, {df['time'].iloc[0]} -> {df['time'].iloc[-1]}")

    config = BacktestConfig(symbol=args.symbol, rr_multiple=args.rr, spread=args.spread)

    extra_symbols = None
    if args.corr_symbol and args.corr_m15:
        print(f"Loading correlated-symbol data for {args.corr_symbol} (SMT divergence check)...")
        corr_dataset = HistoricalDataset.from_csv_dir(args.corr_symbol, args.data_dir, {"M15": args.corr_m15})
        extra_symbols = {args.corr_symbol: corr_dataset}
    elif args.corr_symbol or args.corr_m15:
        print("Both --corr-symbol and --corr-m15 are required to enable the SMT divergence check -- ignoring.")

    run_aox = args.strategy == AOX_NAME or args.all
    single_strategy_name = args.strategy not in (AOX_NAME, STRUCTURAL_SWING_NAME, INTRADAY_NAME, BALANCE_FADE_NAME)
    adapters = ([STRATEGIES_BY_NAME[args.strategy]] if args.strategy and single_strategy_name
                else (ALL_STRATEGIES if not args.strategy else []))

    # WALK-FORWARD MODE: stability across time instead of one pooled number.
    if args.walk_forward:
        if args.walk_forward < 2:
            p.error("--walk-forward needs at least 2 windows to compare anything")
        for adapter in adapters:
            if adapter.name == "SHAAKUNI_SSM" and "H4" not in dataset.frames:
                print(f"\nSkipping {adapter.name}: needs --h4 (not provided)")
                continue
            print(f"\nWalk-forward {adapter.name} over {args.walk_forward} windows...")
            results = run_walk_forward(bot, dataset, config, adapter,
                                       n_windows=args.walk_forward,
                                       min_trades=args.min_trades)
            # Pooled REAL per-trade R across every window, for the t-stat.
            pooled = []
            for wr in results:
                pooled.extend(wr.r_values or [])
            print_walk_forward_report(adapter.name, results, pooled)
        return

    all_trades = []
    all_rejections = []
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
        all_rejections.extend(getattr(engine, "rejections", []))

    if run_aox:
        if "M1" not in dataset.frames:
            print(f"\nSkipping {AOX_NAME}: needs --m1 (not provided)")
        else:
            print(f"\nRunning {AOX_NAME}...")
            aox_config = AoxDriverConfig(symbol=args.symbol, spread=args.spread)
            aox_trades = run_aox_backtest(bot, dataset, aox_config, extra_symbols=extra_symbols)
            stats = summarize(aox_trades)
            print_report(AOX_NAME, True, aox_trades, stats)
            all_trades.extend(aox_trades)

    run_swing = args.strategy == STRUCTURAL_SWING_NAME or args.all
    if run_swing:
        missing = [flag for flag, tf in (("--d1", "D1"), ("--h4", "H4")) if tf not in dataset.frames]
        if missing:
            print(f"\nSkipping {STRUCTURAL_SWING_NAME}: needs {', '.join(missing)} (not provided)")
        else:
            print(f"\nRunning {STRUCTURAL_SWING_NAME}...")
            swing_bot = import_swing_bot_module()
            swing_config = SwingDriverConfig(symbol=args.symbol, spread=args.spread)
            swing_trades = run_swing_backtest(swing_bot, dataset, swing_config)
            stats = summarize(swing_trades)
            print_report(STRUCTURAL_SWING_NAME, True, swing_trades, stats)
            all_trades.extend(swing_trades)

    run_intraday = args.strategy == INTRADAY_NAME or args.all
    if run_intraday:
        missing = [flag for flag, tf in (("--d1", "D1"), ("--h4", "H4"), ("--m15", "M15")) if tf not in dataset.frames]
        if missing:
            print(f"\nSkipping {INTRADAY_NAME}: needs {', '.join(missing)} (not provided)")
        else:
            print(f"\nRunning {INTRADAY_NAME}...")
            if "M1" not in dataset.frames:
                print("  (no --m1 -- Strategy E / AOX Sniper will be a clean no-op, everything else still runs)")
            intraday_bot = import_intraday_module()
            intraday_config = IntradayDriverConfig(symbol=args.symbol, spread=args.spread)
            intraday_trades = run_intraday_backtest(intraday_bot, dataset, intraday_config)
            stats = summarize(intraday_trades)
            print_report(INTRADAY_NAME, True, intraday_trades, stats)
            all_trades.extend(intraday_trades)

    run_balance_fade = args.strategy == BALANCE_FADE_NAME or args.all
    if run_balance_fade:
        if "H1" not in dataset.frames:
            print(f"\nSkipping {BALANCE_FADE_NAME}: needs --h1 (not provided)")
        else:
            print(f"\nRunning {BALANCE_FADE_NAME}...")
            bf_config = BalanceFadeDriverConfig(symbol=args.symbol, spread=args.spread)
            bf_trades = run_balance_fade_backtest(dataset, bf_config)
            stats = summarize(bf_trades)
            print_report(BALANCE_FADE_NAME, True, bf_trades, stats)
            all_trades.extend(bf_trades)

    if args.out and all_trades:
        write_trade_csv(all_trades, args.out)
        print(f"Combined trade ledger ({len(all_trades)} trades) written to {args.out}")

    if args.rejections_out and all_rejections:
        # JSONL rather than CSV: rejection journals are nested and numerous, so
        # one JSON object per line stays greppable and streamable.
        import json as _json
        with open(args.rejections_out, "w") as _f:
            for _r in all_rejections:
                _f.write(_json.dumps(_r, default=str) + "\n")
        print(f"\nRejected-setup journals ({len(all_rejections)}) written to {args.rejections_out}")
        funnel = bot.dj.rejection_funnel(all_rejections)
        for _strat, _counts in funnel.items():
            _tot = sum(_counts.values())
            print(f"\n  {_strat}: {_tot} setups declined -- decisive gate:")
            for _k, _v in sorted(_counts.items(), key=lambda kv: -kv[1])[:8]:
                print(f"    {_v:>7}  ({100*_v/_tot:>5.1f}%)  {_k}")


if __name__ == "__main__":
    sys.exit(main())
