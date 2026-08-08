"""
Turns a list of SimulatedTrade into the numbers that actually answer "is
this strategy real": win rate, expectancy, profit factor, max drawdown,
and -- for the one path where it's meaningful (see strategies_registry.py's
docstring on why) -- whether EdgeEngine's score correlates with outcomes.
"""

import csv
from dataclasses import asdict
from typing import List

from .engine import SimulatedTrade


def summarize(trades: List[SimulatedTrade]) -> dict:
    if not trades:
        return {"total_trades": 0}

    r_values = [t.r_multiple for t in trades]
    wins = [r for r in r_values if r > 0]
    losses = [r for r in r_values if r <= 0]

    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in r_values:
        running += r
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)

    gross_win = sum(wins)
    gross_loss = abs(sum(losses))

    by_edge_state = {}
    scored = [t for t in trades if t.edge_state is not None]
    for state in ("STRONG", "NORMAL", "WEAK", "IGNORE"):
        state_trades = [t for t in scored if t.edge_state == state]
        if state_trades:
            state_r = [t.r_multiple for t in state_trades]
            by_edge_state[state] = {
                "count": len(state_trades),
                "win_rate": sum(1 for r in state_r if r > 0) / len(state_r),
                "avg_r": sum(state_r) / len(state_r),
            }

    return {
        "total_trades": len(trades),
        "win_rate": len(wins) / len(trades),
        "expectancy_r": sum(r_values) / len(r_values),
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else float("inf") if gross_win > 0 else 0.0,
        "max_drawdown_r": max_dd,
        "final_equity_r": running,
        "by_edge_state": by_edge_state,
        "exit_reason_counts": {
            reason: sum(1 for t in trades if t.exit_reason == reason)
            for reason in ("SL", "TP", "TIMEOUT")
        },
    }


def print_report(strategy_name: str, live: bool, trades: List[SimulatedTrade], stats: dict):
    live_tag = "LIVE" if live else "NOT LIVE -- not reachable by the real trading loop today"
    print("=" * 74)
    print(f"BACKTEST REPORT: {strategy_name}  [{live_tag}]")
    print("=" * 74)
    if stats.get("total_trades", 0) == 0:
        print("No trades were generated -- either the data window is too short, "
              "or the entry conditions never fired. That's a real finding: it "
              "tells you how rarely this setup actually occurs in the data you fed it.")
        print()
        return

    print(f"Total trades:     {stats['total_trades']}")
    print(f"Win rate:         {stats['win_rate']*100:.1f}%")
    print(f"Expectancy:       {stats['expectancy_r']:+.3f} R/trade")
    print(f"Profit factor:    {stats['profit_factor']:.2f}")
    print(f"Max drawdown:     {stats['max_drawdown_r']:.2f} R")
    print(f"Final equity:     {stats['final_equity_r']:+.2f} R")
    print(f"Exit reasons:     {stats['exit_reason_counts']}")
    if stats.get("by_edge_state"):
        print()
        print("By EdgeEngine score band:")
        for state, row in stats["by_edge_state"].items():
            print(f"  {state:8s} n={row['count']:4d}  win_rate={row['win_rate']*100:5.1f}%  avg_r={row['avg_r']:+.3f}")
    print()


def write_trade_csv(all_trades: List[SimulatedTrade], path: str):
    if not all_trades:
        return
    rows = [asdict(t) for t in all_trades]
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
