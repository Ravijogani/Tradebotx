# -*- coding: utf-8 -*-
"""
=============================================================================
 RISK LIMITS -- the capital-preservation ceilings, shared by all three bots
=============================================================================
Why this file exists:

The public site (src/components/landing/LivePerformance.tsx) tells every
prospective client, before they have signed up:

    "Maximum risk per trade: 1-2% of account.
     Daily loss limit: 5%. Weekly loss limit: 10%."

What the bots actually enforced before this module:

    hybrid_trading_bot_multiuser.py   daily 25%,  drawdown 30%
    intraday.py                       daily 25%,  drawdown 30%
    structural_swing_pro.py           daily  8%,  drawdown 15%
    weekly limit                      DID NOT EXIST ANYWHERE

So the platform advertised a ceiling five times tighter than the one it
enforced, and advertised a *weekly* limit that was not implemented as a
concept at all -- no weekly baseline, no weekly check, nothing. A client
could lose ~a third of their account in a single day while the marketing
page promised 5%.

This module is the single definition of those ceilings, so the promise and
the enforcement cannot drift apart again. Change a number here and every
bot changes with it.

DESIGN NOTES
------------
* `evaluate_risk_limits()` is pure -- equity numbers in, a verdict out. No
  MT5, no Supabase, no clock. Same discipline as market_intelligence.py,
  and the reason this is unit-testable at all.
* The weekly baseline gets the same restart-safe persistence the daily one
  already has (load_or_init_weekly_baseline): a bot restarted mid-week must
  not silently re-baseline and hand the account a fresh 10% to lose.
* A per-user override may only ever be STRICTER than the platform ceiling
  (see resolve_user_limits). A user cannot raise their own ceiling above
  what the platform advertises -- that would recreate the exact gap this
  module exists to close.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, NamedTuple, Optional, Tuple

# The advertised ceilings. These are the numbers on the public pricing/
# landing page; they are the contract with the client, so they live here as
# the default rather than being restated (differently) in three configs.
PLATFORM_MAX_DAILY_LOSS_PERCENT: float = 5.0
PLATFORM_MAX_WEEKLY_LOSS_PERCENT: float = 10.0

# The deeper equity-drawdown backstop. Distinct from the daily loss limit:
# daily loss is measured from today's opening equity, drawdown from the
# account's high-water mark, so a slow bleed across several days trips this
# even when no single day breaches the daily limit.
PLATFORM_MAX_DRAWDOWN_PERCENT: float = 10.0


class RiskVerdict(NamedTuple):
    breached: bool
    reason: str        # '' when not breached
    detail: str        # human-readable, safe to log / send to Telegram
    worst_usage: float # fraction of the tightest limit used, 0.0-1.0+


def resolve_user_limits(user_settings: Optional[Dict] = None) -> Dict[str, float]:
    """
    Effective limits for one user: the platform ceiling, optionally made
    STRICTER by that user's own settings, never looser.

    `user_settings` is whatever the bot loaded from user_setup (or None).
    A user asking for a 2% daily stop gets 2%. A user (or a stale row, or a
    bad migration) asking for 40% still gets the platform's 5% -- the
    ceiling is a ceiling, and the marketing page is a promise the platform
    makes, not a default a row can override.
    """
    limits = {
        'daily': PLATFORM_MAX_DAILY_LOSS_PERCENT,
        'weekly': PLATFORM_MAX_WEEKLY_LOSS_PERCENT,
        'drawdown': PLATFORM_MAX_DRAWDOWN_PERCENT,
    }
    if not user_settings:
        return limits
    for key, field in (('daily', 'max_daily_loss_percent'),
                       ('weekly', 'max_weekly_loss_percent'),
                       ('drawdown', 'max_drawdown_percent')):
        raw = user_settings.get(field)
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        if val > 0:
            limits[key] = min(limits[key], val)  # stricter only
    return limits


def evaluate_risk_limits(current_equity: float,
                         daily_start_equity: float,
                         weekly_start_equity: Optional[float],
                         peak_equity: Optional[float],
                         limits: Dict[str, float]) -> RiskVerdict:
    """
    Pure evaluation of every capital-preservation ceiling at once.

    Deliberately has no "dynamic buffer" that can raise a limit. intraday.py
    previously computed `effective_limit = MAX_DAILY_LOSS_PERCENT +
    (potential_additional_loss * 0.5)` -- i.e. the more open risk was on the
    book, the MORE it was willing to lose before halting, so realized losses
    could legitimately exceed the stated limit. Under a 25% limit that was
    merely alarming; under an advertised 5% limit it would make the promise
    untrue. A ceiling that widens under stress is not a ceiling.

    Returns a RiskVerdict. `worst_usage` is for the approaching-limit
    warnings the bots already emit at 70%.
    """
    if not daily_start_equity or daily_start_equity <= 0:
        # Self-healing rather than dividing by zero -- the same crash-loop
        # this codebase already fixed once in check_emergency_conditions.
        return RiskVerdict(False, '', 'no valid daily baseline yet', 0.0)

    usages = []

    daily_loss_pct = ((daily_start_equity - current_equity) / daily_start_equity) * 100
    usages.append(daily_loss_pct / limits['daily'] if limits['daily'] > 0 else 0.0)
    if daily_loss_pct >= limits['daily']:
        return RiskVerdict(
            True, 'daily_loss_limit',
            (f"daily loss {daily_loss_pct:.2f}% reached the {limits['daily']:.2f}% "
             f"limit (equity ${current_equity:,.2f} vs ${daily_start_equity:,.2f} at open)"),
            max(usages))

    if weekly_start_equity and weekly_start_equity > 0:
        weekly_loss_pct = ((weekly_start_equity - current_equity) / weekly_start_equity) * 100
        usages.append(weekly_loss_pct / limits['weekly'] if limits['weekly'] > 0 else 0.0)
        if weekly_loss_pct >= limits['weekly']:
            return RiskVerdict(
                True, 'weekly_loss_limit',
                (f"weekly loss {weekly_loss_pct:.2f}% reached the {limits['weekly']:.2f}% "
                 f"limit (equity ${current_equity:,.2f} vs ${weekly_start_equity:,.2f} at week open)"),
                max(usages))

    if peak_equity and peak_equity > 0:
        dd_pct = ((peak_equity - current_equity) / peak_equity) * 100
        usages.append(dd_pct / limits['drawdown'] if limits['drawdown'] > 0 else 0.0)
        if dd_pct >= limits['drawdown']:
            return RiskVerdict(
                True, 'max_drawdown',
                (f"drawdown {dd_pct:.2f}% from the ${peak_equity:,.2f} high-water mark "
                 f"reached the {limits['drawdown']:.2f}% limit"),
                max(usages))

    return RiskVerdict(False, '', 'within all limits', max(usages) if usages else 0.0)


# ---------------------------------------------------------------------------
# Restart-safe weekly baseline -- mirrors the existing daily-baseline pattern
# ---------------------------------------------------------------------------

def iso_week_key(now: Optional[datetime] = None) -> str:
    """'2026-W33' -- the ISO year+week this instant falls in (UTC)."""
    now = now or datetime.now(timezone.utc)
    iso = now.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _weekly_baseline_path(data_dir: str) -> str:
    return os.path.join(data_dir, 'weekly_equity_baseline.json')


def load_or_init_weekly_baseline(data_dir: str, current_equity: float,
                                 week_key: Optional[str] = None) -> Tuple[float, str]:
    """
    Restart-safe weekly-loss baseline, same contract as the daily one:
    reuse the stored baseline while we're still in the same ISO week, and
    only start a fresh one on a genuine new week. Without this a bot
    restarted mid-week would re-baseline from whatever equity survived and
    hand the account a fresh 10% to lose on top of what it already lost.

    Returns (baseline_equity, week_key).
    """
    week_key = week_key or iso_week_key()
    try:
        with open(_weekly_baseline_path(data_dir), 'r', encoding='utf-8') as f:
            saved = json.load(f)
        if (saved.get('week') == week_key
                and isinstance(saved.get('baseline'), (int, float))
                and saved['baseline'] > 0):
            return float(saved['baseline']), week_key
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, OSError):
        pass

    persist_weekly_baseline(data_dir, week_key, current_equity)
    return current_equity, week_key


def persist_weekly_baseline(data_dir: str, week_key: str, baseline: float) -> None:
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(_weekly_baseline_path(data_dir), 'w', encoding='utf-8') as f:
            json.dump({'week': week_key, 'baseline': baseline}, f)
    except OSError as e:
        print(f"[BASELINE] WARNING: could not persist weekly equity baseline: {e}")
