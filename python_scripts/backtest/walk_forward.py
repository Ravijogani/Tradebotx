# -*- coding: utf-8 -*-
"""
=============================================================================
 WALK-FORWARD VALIDATION -- does the edge persist, or was it one good window?
=============================================================================
Why this exists:

Every backtest number this project has ever produced came from ONE run over
ONE instrument over ONE ~90-day window. Verified carefully, line by line --
but still a single draw from a noisy distribution. "Shaakuni SSM makes
+0.759R per trade" and "Shaakuni SSM made +0.759R per trade over 90 days of
gold in mid-2026" are very different claims, and only the second one was
ever actually supported.

WHAT WALK-FORWARD MEANS HERE (and what it deliberately does NOT mean)
---------------------------------------------------------------------
Classic walk-forward optimisation fits parameters on an in-sample window and
tests them out-of-sample, to detect curve-fitting. That framing does not
apply cleanly to this codebase, and pretending otherwise would be theatre:
these strategies have no fitted parameters. Their thresholds (EMA periods,
body-percentage bands, RR floors) are hand-specified from the source
methodology, not optimised against this data. There is nothing to overfit
in the usual sense.

What DOES matter, and what this module measures, is STABILITY: split the
history into sequential windows, run each one independently, and ask
whether the edge shows up repeatedly or came from one lucky stretch. A
strategy that makes +0.8R/trade in every window is a different proposition
from one that made +4R in a single window and roughly zero in the rest,
even when both average +0.8R overall.

The headline output is therefore not a single return number but:
  * per-window expectancy / profit factor / trade count
  * how many windows were profitable (consistency)
  * the spread between best and worst window
  * a pooled t-statistic on per-trade R, so "is this distinguishable from
    luck at this sample size" gets an actual number rather than a vibe

HONEST LIMITS OF THIS TOOL
--------------------------
* It cannot manufacture data. Run it on 90 days and it will tell you about
  90 days, in more detail and with less self-deception -- not more.
* Splitting a short history into more windows does not create information;
  it just makes each window noisier. `--min-trades` exists so windows too
  thin to interpret are reported as such rather than averaged in silently.
* Sequential windows share regime context (a single trending quarter split
  four ways is still one trending quarter). Genuine robustness evidence
  needs multiple instruments and multiple years -- this module is what you
  run on them once you have them, and what tells you honestly how little
  you can conclude until then.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from .data import HistoricalDataset
from .engine import BacktestEngine, BacktestConfig
from .report import summarize


@dataclass
class WindowResult:
    label: str
    start: pd.Timestamp
    end: pd.Timestamp
    trades: int
    win_rate: float
    expectancy: float
    profit_factor: float
    total_r: float
    interpretable: bool          # False when the window is too thin to read
    note: str = ""
    # Real per-trade R multiples from this window. Kept so the pooled
    # t-statistic is computed from actual trades rather than from a window
    # average repeated `trades` times -- that would collapse within-window
    # variance and inflate |t| dramatically.
    r_values: Optional[List[float]] = None


def split_windows(df: pd.DataFrame, n_windows: int) -> List[tuple]:
    """
    Split a bar series into `n_windows` contiguous, equal-length time spans.

    Split on TIME, not on row count: equal-row splits would make a quiet
    holiday stretch and a violent news week look like comparable windows,
    which is exactly the distortion this tool exists to avoid.
    """
    if df is None or len(df) == 0 or n_windows < 1:
        return []
    t0, t1 = df['time'].iloc[0], df['time'].iloc[-1]
    total = t1 - t0
    if total.total_seconds() <= 0:
        return []
    step = total / n_windows
    return [(t0 + step * i, t0 + step * (i + 1)) for i in range(n_windows)]


def _slice_dataset(dataset: HistoricalDataset, start, end,
                   warmup_bars: int = 250) -> HistoricalDataset:
    """
    A dataset restricted to [start, end), keeping `warmup_bars` of history
    BEFORE `start` on every timeframe.

    The warm-up is not optional. Strategies need real prior history to be
    themselves -- the 200 EMA, volume-profile value areas, swing-point
    detection and D1 structure all read backwards. Cutting a window dead at
    its first bar would measure a cold-start artefact and call it a regime.
    Trades are still only counted from `start` onward (the engine drives off
    the sliced M5 index), so the warm-up informs decisions without
    contributing trades to a window it doesn't belong to.
    """
    frames: Dict[str, pd.DataFrame] = {}
    for tf, df in dataset.frames.items():
        in_window = df[(df['time'] >= start) & (df['time'] < end)]
        before = df[df['time'] < start]
        if warmup_bars > 0 and len(before) > 0:
            frames[tf] = pd.concat([before.tail(warmup_bars), in_window], ignore_index=True)
        else:
            frames[tf] = in_window.reset_index(drop=True)
    return HistoricalDataset(dataset.symbol, frames)


def run_walk_forward(bot, dataset: HistoricalDataset, config: BacktestConfig,
                     adapter, n_windows: int = 4, min_trades: int = 10,
                     warmup_bars: int = 250) -> List[WindowResult]:
    """Run `adapter` independently over each sequential window."""
    results: List[WindowResult] = []
    base = dataset.frames.get("M5")
    if base is None:
        base = next(iter(dataset.frames.values()))

    for i, (start, end) in enumerate(split_windows(base, n_windows), 1):
        sub = _slice_dataset(dataset, start, end, warmup_bars)
        m5 = sub.frames.get("M5")
        if m5 is None or len(m5) < warmup_bars + 50:
            results.append(WindowResult(
                f"W{i}", start, end, 0, 0.0, 0.0, 0.0, 0.0,
                interpretable=False, note="not enough bars in window"))
            continue

        engine = BacktestEngine(bot, sub, config, adapter)
        # Only count trades that were actually entered inside the window --
        # the warm-up tail must inform decisions, never contribute trades.
        trades = [t for t in engine.run()
                  if getattr(t, 'entry_time', None) is not None and t.entry_time >= start]
        stats = summarize(trades)
        n = stats.get("total_trades", 0)
        results.append(WindowResult(
            label=f"W{i}",
            start=start, end=end,
            trades=n,
            win_rate=stats.get("win_rate", 0.0) or 0.0,
            expectancy=stats.get("expectancy_r", 0.0) or 0.0,
            profit_factor=stats.get("profit_factor", 0.0) or 0.0,
            total_r=sum(t.r_multiple for t in trades),
            interpretable=n >= min_trades,
            note="" if n >= min_trades else f"only {n} trades -- too thin to interpret",
            r_values=[t.r_multiple for t in trades],
        ))
    return results


def pooled_t_stat(all_r: List[float]) -> Optional[float]:
    """
    t = mean(R) / (stdev(R) / sqrt(n)) over every trade in every window.

    A rough "is this distinguishable from zero at this sample size" figure.
    Deliberately reported as a number with its caveats rather than converted
    into a p-value and a verdict: trade returns are not normally distributed
    and are not fully independent, so this is a sanity indicator, not a
    significance test to lean on. |t| < 2 at these sample sizes means the
    honest answer is "not yet distinguishable from luck".
    """
    if len(all_r) < 2:
        return None
    sd = statistics.stdev(all_r)
    if sd == 0:
        return None
    return statistics.mean(all_r) / (sd / (len(all_r) ** 0.5))


def print_walk_forward_report(name: str, results: List[WindowResult],
                              all_r: Optional[List[float]] = None) -> None:
    print("=" * 78)
    print(f"WALK-FORWARD: {name}")
    print("=" * 78)
    if not results:
        print("No windows produced -- not enough data.")
        return

    print(f"{'Window':<8}{'Period':<26}{'Trades':>7}{'Win%':>7}{'Expect':>9}{'PF':>7}{'Total R':>9}")
    print("-" * 78)
    for r in results:
        period = f"{r.start.date()} -> {r.end.date()}"
        if r.trades == 0:
            print(f"{r.label:<8}{period:<26}{0:>7}{'-':>7}{'-':>9}{'-':>7}{'-':>9}   {r.note}")
            continue
        flag = "" if r.interpretable else "  (thin)"
        print(f"{r.label:<8}{period:<26}{r.trades:>7}{r.win_rate*100:>6.1f}%"
              f"{r.expectancy:>+9.3f}{r.profit_factor:>7.2f}{r.total_r:>+9.2f}{flag}")

    traded = [r for r in results if r.trades > 0]
    readable = [r for r in results if r.interpretable]
    print("-" * 78)
    if traded:
        profitable = sum(1 for r in traded if r.total_r > 0)
        print(f"Windows with trades:   {len(traded)}/{len(results)}")
        print(f"Profitable windows:    {profitable}/{len(traded)}")
        exps = [r.expectancy for r in traded]
        print(f"Expectancy spread:     {min(exps):+.3f}R (worst) .. {max(exps):+.3f}R (best)")
        if len(traded) > 1:
            print(f"Expectancy stdev:      {statistics.stdev(exps):.3f}R")
    if len(readable) < len(traded):
        print(f"NOTE: {len(traded) - len(readable)} window(s) had too few trades to interpret.")

    if all_r:
        t = pooled_t_stat(all_r)
        if t is not None:
            verdict = ("distinguishable from luck at this sample size" if abs(t) >= 2
                       else "NOT yet distinguishable from luck at this sample size")
            print(f"Pooled t-stat (n={len(all_r)}): {t:+.2f} -- {verdict}")
            print("  (indicative only: trade returns are neither normal nor fully independent)")
    print()
