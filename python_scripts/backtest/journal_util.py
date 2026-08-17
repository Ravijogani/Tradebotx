# -*- coding: utf-8 -*-
"""
Shared journal close-out for the standalone drivers.

swing_driver.py and intraday_driver.py don't go through BacktestEngine (they
drive their own bots' pure signal functions), so they can't reuse the engine's
inline close-out. Rather than duplicate it twice and let the copies drift --
the exact failure this harness keeps finding -- it lives here once.
"""

from typing import Any, Dict, Optional


def close_journal(journal: Optional[Dict[str, Any]], exit_reason: Optional[str],
                  attribution: Optional[str], r_multiple: Optional[float],
                  exit_time: Any) -> Optional[Dict[str, Any]]:
    """
    Stamp the real outcome onto a strategy's entry journal.

    float() on r_multiple is load-bearing: it is derived from numpy price
    columns, so it is an np.float64, which serializes as `np.float64(-1.01)` --
    neither valid JSON nor parseable by analyze_journal.py. Same leak already
    found and fixed once in engine.py; fixed here by construction.
    """
    if not journal:
        return None
    out = dict(journal)
    out["exit"] = {
        "outcome": exit_reason,
        "reason": attribution,
        "r_multiple": float(r_multiple) if r_multiple is not None else None,
        "at": str(exit_time),
    }
    return out
