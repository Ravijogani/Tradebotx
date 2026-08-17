# -*- coding: utf-8 -*-
"""
=============================================================================
 DECISION JOURNAL -- why the bot did what it did, on every trade, end to end
=============================================================================
WHY THIS EXISTS

A professional discretionary trader doesn't just record "bought gold, lost
$40". They record the case: H4 is bullish, price swept yesterday's low and
closed back above it, we're in discount, the M5 pulled back into the order
block, so I'm long -- and afterwards, why it worked or didn't.

This bot had none of that. Before this module it recorded the ticket, the
prices, the P&L, a strategy name, and (as of the previous change) a handful
of entry fields. What it could never answer is the question that actually
improves a system:

    "Of the confirmations we look for, which ones were present on the trades
     that won, and which were present on the trades that lost?"

Without that, every post-mortem is guesswork and every 'improvement' is a
coin flip that has to be validated from scratch against real data. With it,
the 132 SSM trades already sitting in the ledger become an actual dataset
about our own decision process.

WHAT IT RECORDS

Three phases, one record per trade:

  1. ENTRY -- every check that ran, with its verdict. Crucially this
     includes checks that PASSED WEAKLY or were NEUTRAL, not just the ones
     that fired. "SSM won 3x more often when premium/discount agreed" is
     only discoverable if disagreement was also written down.
  2. MANAGEMENT -- what the bot did to the position while it was open and
     why: moved to break-even, took partial profit, trailed the stop,
     tightened on an adverse signal. Each with the trigger that caused it.
  3. EXIT -- how it ended and the attributable reason. "SL" is not a
     reason; "price swept our stop and then continued in our direction" and
     "structure genuinely broke against us" are different failures with
     different fixes, and the difference is only recoverable if recorded at
     the time.

DESIGN NOTES

* Pure and dependency-free: no MT5, no Supabase, no clock of its own
  (timestamps are passed in). Same discipline as market_intelligence.py --
  which is what lets the BACKTEST produce journals too, not just live
  trading. That matters enormously: it means R&D can mine the reasoning of
  132 historical trades today instead of waiting months for live ones.
* Additive and non-blocking. A journal failure must never stop a trade or
  break a strategy. Every public method is exception-safe by construction
  (plain dict/list appends), and callers treat the journal as write-only.
* Compact when serialized. This ends up in trades.metadata (JSONB) and in a
  local JSONL for offline analysis, so entries are short keys plus a
  human-readable detail string, not nested prose.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Verdicts. Deliberately more than pass/fail: the whole analytical value is
# in being able to separate "this confirmation was strongly present" from
# "it was absent" from "we never checked", which a boolean collapses.
CONFIRMED = "CONFIRMED"    # the check passed and supports the trade
WEAK = "WEAK"              # passed, but marginally
NEUTRAL = "NEUTRAL"        # no signal either way / not applicable here
AGAINST = "AGAINST"        # actively argues against the trade (but didn't veto)
VETO = "VETO"              # blocked the trade outright

# Categories, so analysis can group by the KIND of evidence.
BIAS = "BIAS"              # HTF directional bias (H4/H1/D1)
STRUCTURE = "STRUCTURE"    # market structure: BOS, CHoCH, swing sequence
LIQUIDITY = "LIQUIDITY"    # sweeps, PDH/PDL, session levels, FVG, OB
REGIME = "REGIME"          # auction state / trend-vs-balance routing
LOCATION = "LOCATION"      # premium/discount, OTE, distance from mean
TRIGGER = "TRIGGER"        # the entry pattern itself
RISK = "RISK"              # RR, spread, exposure, correlation, sizing
TIMING = "TIMING"          # session, rollover window, news proximity


def _plain(v: Any) -> Any:
    """
    Coerce a value to something JSON/repr-safe.

    Found by running the analyzer on real output: numpy scalars serialize as
    `np.float64(23.08)`, which is neither valid JSON nor parseable by
    ast.literal_eval -- so EMA_SCALP_CROSS journals silently failed to load
    in analyze_journal.py even though they were written. Worse, the LIVE path
    writes journals into a Supabase JSONB column, and np.float64 is not JSON
    serializable at all: that would have raised on the first real EMA trade.
    Fixed at the source so every journal is safe by construction rather than
    relying on each caller to remember to cast.
    """
    # EXACT type check, not isinstance: np.float64 SUBCLASSES Python float, so
    # an isinstance shortcut passes it through untouched and the leak survives
    # (found exactly that way -- np.int64 was coerced while np.float64 wasn't).
    if v is None or type(v) in (bool, int, float, str):
        return v
    # numpy / pandas scalars expose .item()
    item = getattr(v, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:
            pass
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return str(v)


class DecisionJournal:
    """
    Accumulates the case for (or against) one trade, then its life and death.

    Usage in a strategy or scan loop:

        j = DecisionJournal(symbol="XAUUSDm", direction="BUY", strategy="SHAAKUNI_SSM")
        j.note(BIAS, "h4_bias", CONFIRMED, "H4 macro bias BULLISH")
        j.note(LIQUIDITY, "htf_sweep", CONFIRMED, "H1 swept prior low, closed back above")
        j.note(LOCATION, "premium_discount", AGAINST, "price in PREMIUM for a BUY")
        ...
        j.decide(True, "all mandatory checks passed, RR 2.3")
    """

    def __init__(self, symbol: str, direction: Optional[str] = None,
                 strategy: Optional[str] = None, at: Optional[str] = None):
        self.symbol = symbol
        self.direction = direction
        self.strategy = strategy
        self.created_at = at
        self.entry_checks: List[Dict[str, Any]] = []
        self.management: List[Dict[str, Any]] = []
        self.exit: Optional[Dict[str, Any]] = None
        self.taken: Optional[bool] = None
        self.decision_detail: str = ""
        self.numbers: Dict[str, Any] = {}

    # ---------------- entry phase ----------------

    def note(self, category: str, key: str, verdict: str, detail: str = "",
             value: Any = None) -> "DecisionJournal":
        """
        Record one check. Returns self so calls can chain.

        `key` is a stable machine name (analysis groups on it), `detail` is
        the human sentence, `value` is the raw number/label if there is one.
        """
        self.entry_checks.append({
            "cat": category, "key": key, "verdict": verdict,
            "detail": str(detail), "value": _plain(value),
        })
        return self

    def measure(self, **kwargs) -> "DecisionJournal":
        """Record the raw numbers behind the decision (rr, atr, spread, ...)."""
        self.numbers.update({k: _plain(v) for k, v in kwargs.items()})
        return self

    def decide(self, taken: bool, detail: str = "") -> "DecisionJournal":
        self.taken = taken
        self.decision_detail = detail
        return self

    # ---------------- management phase ----------------

    def action(self, what: str, why: str, at: Optional[str] = None,
               **extra) -> "DecisionJournal":
        """
        Something was done to a live position and this is why.

        `what` is a stable label -- 'moved_to_breakeven', 'partial_close',
        'trail_stop', 'tighten_stop', 'manual_close'. `why` is the trigger.
        """
        entry = {"what": what, "why": why, "at": at}
        entry.update({k: _plain(v) for k, v in extra.items()})
        self.management.append(entry)
        return self

    # ---------------- exit phase ----------------

    def closed(self, outcome: str, reason: str, r_multiple: Optional[float] = None,
               at: Optional[str] = None, **extra) -> "DecisionJournal":
        """
        How it ended, and WHY -- attribution, not just the mechanical label.

        `outcome`: 'TP' | 'SL' | 'BREAKEVEN' | 'TIMEOUT' | 'MANUAL' | 'PARTIAL'
        `reason`: the attributable cause, e.g. 'stop swept then price
        resumed our direction' vs 'M30 structure broke against us'. These
        demand different fixes; 'SL' alone tells you nothing.
        """
        self.exit = {"outcome": outcome, "reason": reason,
                     "r_multiple": _plain(r_multiple), "at": at}
        self.exit.update({k: _plain(v) for k, v in extra.items()})
        return self

    # ---------------- serialization / summary ----------------

    def confirmations(self) -> List[str]:
        """Keys that actively supported the trade -- the quick 'why long?' list."""
        return [c["key"] for c in self.entry_checks
                if c["verdict"] in (CONFIRMED, WEAK)]

    def objections(self) -> List[str]:
        """Keys that argued against it. Present even on trades we took."""
        return [c["key"] for c in self.entry_checks
                if c["verdict"] in (AGAINST, VETO)]

    def headline(self) -> str:
        """One human line: the case, as a trader would say it out loud."""
        supports = [c["detail"] for c in self.entry_checks if c["verdict"] == CONFIRMED]
        against = [c["detail"] for c in self.entry_checks if c["verdict"] in (AGAINST, VETO)]
        parts = []
        if supports:
            parts.append("; ".join(supports))
        if against:
            parts.append("despite: " + "; ".join(against))
        base = f"{self.direction or '?'} {self.symbol}"
        return f"{base} -- {' | '.join(parts)}" if parts else base

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "strategy": self.strategy,
            "created_at": self.created_at,
            "taken": self.taken,
            "decision": self.decision_detail,
            "checks": self.entry_checks,
            "confirmations": self.confirmations(),
            "objections": self.objections(),
            "numbers": self.numbers,
            "management": self.management,
            "exit": self.exit,
            "headline": self.headline(),
        }


def summarize_by_confirmation(journals: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    THE PAYOFF FUNCTION. Given many journals with outcomes, report, per
    confirmation key: how often it was present, and the average R of the
    trades where it was present vs absent.

    This is the same removed-vs-kept methodology that caught the regime
    router being anti-correlated with quality, generalized to every
    confirmation the bot looks for -- so "which of our confirmations
    actually predict a better trade" becomes a table instead of an opinion.

    Returns {key: {present_n, present_avg_r, absent_n, absent_avg_r, edge}}
    where `edge` is present_avg_r - absent_avg_r. A confirmation with a
    negative edge is one the bot believes in and shouldn't.
    """
    keys = set()
    for j in journals:
        for c in (j.get("checks") or []):
            keys.add(c["key"])

    def r_of(j):
        ex = j.get("exit") or {}
        return ex.get("r_multiple")

    out: Dict[str, Dict[str, Any]] = {}
    for key in sorted(keys):
        present, absent = [], []
        for j in journals:
            r = r_of(j)
            if r is None:
                continue
            verdicts = [c["verdict"] for c in (j.get("checks") or []) if c["key"] == key]
            supported = any(v in (CONFIRMED, WEAK) for v in verdicts)
            (present if supported else absent).append(r)
        if not present and not absent:
            continue
        p_avg = sum(present) / len(present) if present else None
        a_avg = sum(absent) / len(absent) if absent else None
        out[key] = {
            "present_n": len(present),
            "present_avg_r": p_avg,
            "absent_n": len(absent),
            "absent_avg_r": a_avg,
            "edge": (p_avg - a_avg) if (p_avg is not None and a_avg is not None) else None,
        }
    return out
