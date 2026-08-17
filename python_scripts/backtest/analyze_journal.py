# -*- coding: utf-8 -*-
"""
=============================================================================
 ANALYZE JOURNAL -- mine the bot's own reasoning for what actually works
=============================================================================
Run this on a backtest ledger produced with journaling enabled:

    python3 -m backtest.analyze_journal --ledger out.csv

It answers the questions that make a trading system improve, which no
amount of staring at an equity curve can:

  1. Which of our confirmations actually predict a better trade?
     For each check the bot performs, the average R of trades where it was
     present vs absent. A confirmation with a NEGATIVE edge is one the bot
     currently believes in and shouldn't -- exactly the pattern that caught
     the regime router being anti-correlated with quality, now applied
     automatically to every confirmation instead of one at a time.

  2. HOW are we losing?
     Losses are grouped by attributed cause, not by the mechanical "SL"
     label. 'swept_then_resumed' (stop placement) and 'thesis_invalidated'
     (bias was wrong) demand opposite fixes, and the split tells you which
     problem you actually have.

  3. Which objections did we trade through, and did it cost us?
     Every trade the bot took DESPITE a check arguing against it, and how
     those turned out. This is where over-permissiveness shows up.

Deliberately reports sample sizes next to every number and refuses to draw
conclusions from tiny ones -- the same discipline as walk_forward.py. A
confirmation seen 4 times tells you nothing, and this says so rather than
ranking it first because its average happened to be high.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional

sys.path.insert(0, __file__.rsplit("/backtest/", 1)[0])
import decision_journal as dj  # noqa: E402


def _parse_journal(raw: str) -> Optional[Dict[str, Any]]:
    """
    Ledger CSV stores the journal as a Python-repr dict (csv.DictWriter on a
    dataclass) or JSON depending on how it was written. Accept either rather
    than being brittle about it.
    """
    if not raw or raw in ("", "None"):
        return None
    for loader in (json.loads, ast.literal_eval):
        try:
            v = loader(raw)
            return v if isinstance(v, dict) else None
        except (ValueError, SyntaxError):
            continue
    return None


def load_journals(ledger_path: str, strategy: Optional[str] = None) -> List[Dict[str, Any]]:
    out = []
    with open(ledger_path, newline="") as f:
        for row in csv.DictReader(f):
            if strategy and row.get("strategy") != strategy:
                continue
            j = _parse_journal(row.get("journal", ""))
            if not j:
                continue
            # Prefer the ledger's own outcome columns -- they're authoritative.
            if row.get("r_multiple"):
                try:
                    r = float(row["r_multiple"])
                    j.setdefault("exit", {})
                    j["exit"]["r_multiple"] = r
                    j["exit"].setdefault("outcome", row.get("exit_reason"))
                    j["exit"].setdefault("reason", row.get("exit_attribution"))
                except ValueError:
                    pass
            j["_strategy"] = row.get("strategy")
            out.append(j)
    return out


def report_confirmation_edges(journals: List[Dict[str, Any]], min_n: int = 10) -> None:
    print("=" * 92)
    print("1. WHICH CONFIRMATIONS ACTUALLY PREDICT A BETTER TRADE?")
    print("=" * 92)
    summary = dj.summarize_by_confirmation(journals)
    if not summary:
        print("No journalled checks found in this ledger.\n")
        return

    rows = []
    for key, v in summary.items():
        rows.append((key, v))
    # Sort by edge, but unknown/None edges last.
    rows.sort(key=lambda kv: (kv[1]["edge"] is None, -(kv[1]["edge"] or 0)))

    print(f"{'Confirmation':<30}{'Present':>9}{'Avg R':>9}{'Absent':>9}{'Avg R':>9}{'Edge':>9}   Verdict")
    print("-" * 92)
    for key, v in rows:
        pn, an = v["present_n"], v["absent_n"]
        pa = f"{v['present_avg_r']:+.3f}" if v["present_avg_r"] is not None else "-"
        aa = f"{v['absent_avg_r']:+.3f}" if v["absent_avg_r"] is not None else "-"
        ed = f"{v['edge']:+.3f}" if v["edge"] is not None else "-"

        if v["edge"] is None:
            verdict = "no contrast (always present or always absent)"
        elif min(pn, an) < min_n:
            verdict = f"too few samples to judge (min {min(pn, an)})"
        elif v["edge"] > 0.15:
            verdict = "EARNS ITS PLACE"
        elif v["edge"] < -0.15:
            verdict = "ANTI-CORRELATED -- investigate"
        else:
            verdict = "no measurable effect"
        print(f"{key:<30}{pn:>9}{pa:>9}{an:>9}{aa:>9}{ed:>9}   {verdict}")
    print()


def report_loss_causes(journals: List[Dict[str, Any]]) -> None:
    print("=" * 92)
    print("2. HOW ARE WE LOSING? (attributed cause, not the 'SL' label)")
    print("=" * 92)
    buckets: Dict[str, List[float]] = defaultdict(list)
    for j in journals:
        ex = j.get("exit") or {}
        r = ex.get("r_multiple")
        if r is None:
            continue
        reason = (ex.get("reason") or "unattributed").split(" -- ")[0]
        buckets[reason].append(r)

    if not buckets:
        print("No outcomes recorded.\n")
        return

    print(f"{'Attributed cause':<42}{'Trades':>8}{'Total R':>10}{'Avg R':>9}")
    print("-" * 92)
    for reason, rs in sorted(buckets.items(), key=lambda kv: sum(kv[1])):
        print(f"{reason:<42}{len(rs):>8}{sum(rs):>+10.2f}{sum(rs)/len(rs):>+9.3f}")

    swept = buckets.get("swept_then_resumed", [])
    thesis = buckets.get("thesis_invalidated", [])
    if swept or thesis:
        print()
        print(f"  Stop-placement losses (swept, then price reached our target): {len(swept)} trades, {sum(swept):+.2f}R")
        print(f"  Thesis losses (price kept going against us):                  {len(thesis)} trades, {sum(thesis):+.2f}R")
        if len(swept) > len(thesis):
            print("  -> Losses are dominated by STOPS BEING TOO TIGHT, not by bad direction calls.")
            print("     The fix is stop placement / entry timing, not the bias logic.")
        elif len(thesis) > len(swept):
            print("  -> Losses are dominated by THE DIRECTION BEING WRONG, not stop placement.")
            print("     The fix is the bias/structure logic, not wider stops.")
    print()


def report_traded_objections(journals: List[Dict[str, Any]], min_n: int = 5) -> None:
    print("=" * 92)
    print("3. TRADES WE TOOK DESPITE AN OBJECTION -- did it cost us?")
    print("=" * 92)
    with_obj, without_obj = [], []
    by_obj: Dict[str, List[float]] = defaultdict(list)
    for j in journals:
        ex = j.get("exit") or {}
        r = ex.get("r_multiple")
        if r is None:
            continue
        objs = j.get("objections") or []
        if objs:
            with_obj.append(r)
            for o in objs:
                by_obj[o].append(r)
        else:
            without_obj.append(r)

    if not with_obj and not without_obj:
        print("No outcomes recorded.\n")
        return

    def avg(xs):
        return sum(xs) / len(xs) if xs else None

    a_with, a_without = avg(with_obj), avg(without_obj)
    print(f"Clean setups (no objection):     {len(without_obj):>4} trades, avg "
          f"{a_without:+.3f}R" if without_obj else "Clean setups: none")
    print(f"Traded through an objection:     {len(with_obj):>4} trades, avg "
          f"{a_with:+.3f}R" if with_obj else "Traded through an objection: none")
    if a_with is not None and a_without is not None:
        diff = a_with - a_without
        print(f"Cost of trading through objections: {diff:+.3f}R per trade")
        if min(len(with_obj), len(without_obj)) < min_n:
            print("  (sample too small to act on)")
        elif diff < -0.15:
            print("  -> Objections are meaningful. Consider making the strongest ones hard vetoes.")
        elif diff > 0.15:
            print("  -> Counter-intuitive: these 'objections' came with BETTER trades.")
            print("     Do not tighten them -- verify before treating them as negatives at all.")
    if by_obj:
        print()
        print(f"{'Objection traded through':<30}{'Trades':>8}{'Avg R':>9}")
        print("-" * 92)
        for o, rs in sorted(by_obj.items(), key=lambda kv: avg(kv[1])):
            print(f"{o:<30}{len(rs):>8}{avg(rs):>+9.3f}")
    print()


def report_direction_split(journals: List[Dict[str, Any]]) -> None:
    """
    BUY vs SELL performance.

    Added after a real instrumentation bug: Swappy's journal used
    direction-specific key names ('higher_low' for BUY, 'lower_high' for
    SELL), so the confirmation table reported an "edge" for them that was
    actually just "SELLs outperformed BUYs in this window". The keys are
    shared now -- and the directional signal it was masking is genuinely
    worth seeing, so it gets its own section instead of leaking into another.
    """
    print("=" * 92)
    print("4. DIRECTIONAL SPLIT (a real asymmetry here is a finding, not noise)")
    print("=" * 92)
    buckets: Dict[str, List[float]] = defaultdict(list)
    for j in journals:
        r = (j.get("exit") or {}).get("r_multiple")
        if r is None:
            continue
        buckets[j.get("direction") or "?"].append(r)
    if not buckets:
        print("No outcomes recorded.\n")
        return
    print(f"{'Direction':<12}{'Trades':>8}{'Total R':>10}{'Avg R':>9}")
    print("-" * 92)
    for d, rs in sorted(buckets.items()):
        print(f"{d:<12}{len(rs):>8}{sum(rs):>+10.2f}{sum(rs)/len(rs):>+9.3f}")
    if len(buckets) == 2:
        vals = list(buckets.values())
        gap = abs(sum(vals[0])/len(vals[0]) - sum(vals[1])/len(vals[1]))
        if min(len(v) for v in vals) < 10:
            print(f"  Gap {gap:.3f}R per trade, but samples are small -- not actionable yet.")
        elif gap > 0.3:
            print(f"  Gap {gap:.3f}R per trade is large. Worth checking whether one side is")
            print("  structurally disadvantaged (spread, session, or a directional bug).")
    print()


def main():
    p = argparse.ArgumentParser(description="Mine decision journals from a backtest ledger")
    p.add_argument("--ledger", required=True, help="Path to a ledger CSV written with --out")
    p.add_argument("--strategy", default=None, help="Only analyze this strategy")
    p.add_argument("--min-n", type=int, default=10,
                   help="Minimum samples on each side before a confirmation edge is judged (default 10)")
    args = p.parse_args()

    journals = load_journals(args.ledger, args.strategy)
    if not journals:
        print("No decision journals found in that ledger.")
        print("Journals are written by strategies that populate them (SHAAKUNI_SSM today);")
        print("re-run the backtest with --out after this change to produce them.")
        return

    strategies = sorted({j.get("_strategy") or "?" for j in journals})
    outcomes = sum(1 for j in journals if (j.get("exit") or {}).get("r_multiple") is not None)
    print()
    print(f"Loaded {len(journals)} journalled trade(s) across {', '.join(strategies)}; "
          f"{outcomes} with recorded outcomes.")
    print()
    report_confirmation_edges(journals, args.min_n)
    report_loss_causes(journals)
    report_traded_objections(journals)
    report_direction_split(journals)


if __name__ == "__main__":
    main()
