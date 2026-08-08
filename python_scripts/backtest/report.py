"""
Turns a list of SimulatedTrade into the numbers that actually answer "is
this strategy real": win rate, expectancy, profit factor, max drawdown,
and -- the important one nothing in this codebase measured before --
whether the EdgeEngine's score actually correlates with outcomes at all.
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

    equity_curve = []
    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in r_values:
        running += r
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)
        equity_curve.append(running)

    gross_win = sum(wins)
    gross_loss = abs(sum(losses))

    by_edge_state = {}
    for state in ("STRONG", "NORMAL", "WEAK", "IGNORE"):
        state_trades = [t for t in trades if t.edge_state == state]
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
        "avg_r": sum(r_values) / len(r_values),
        "expectancy_r": sum(r_values) / len(r_values),  # same thing, named per convention
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else float("inf") if gross_win > 0 else 0.0,
        "max_drawdown_r": max_dd,
        "final_equity_r": running,
        "by_edge_state": by_edge_state,
        "exit_reason_counts": {
            reason: sum(1 for t in trades if t.exit_reason == reason)
            for reason in ("SL", "TP", "TIMEOUT")
        },
    }


def print_report(trades: List[SimulatedTrade], stats: dict):
    print("=" * 70)
    print("BACKTEST REPORT")
    print("=" * 70)
    if stats.get("total_trades", 0) == 0:
        print("No trades were generated -- either the data window is too short, "
              "or the entry conditions never fired. This is itself a real finding: "
              "it tells you how rarely this setup actually occurs in the data you fed it.")
        return

    print(f"Total trades:     {stats['total_trades']}")
    print(f"Win rate:         {stats['win_rate']*100:.1f}%")
    print(f"Expectancy:       {stats['expectancy_r']:+.3f} R/trade")
    print(f"Profit factor:    {stats['profit_factor']:.2f}")
    print(f"Max drawdown:     {stats['max_drawdown_r']:.2f} R")
    print(f"Final equity:     {stats['final_equity_r']:+.2f} R")
    print(f"Exit reasons:     {stats['exit_reason_counts']}")
    print()
    print("By edge score band -- this is the number that actually tells you")
    print("whether EdgeEngine's hand-picked weights predict anything real:")
    for state, row in stats.get("by_edge_state", {}).items():
        print(f"  {state:8s} n={row['count']:4d}  win_rate={row['win_rate']*100:5.1f}%  avg_r={row['avg_r']:+.3f}")
    print("=" * 70)


def write_trade_csv(trades: List[SimulatedTrade], path: str):
    if not trades:
        return
    rows = []
    for t in trades:
        row = asdict(t)
        # Flatten score_components for a readable CSV
        comps = row.pop("score_components")
        for k, v in comps.items():
            row[f"score_{k}"] = v
        rows.append(row)

    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
