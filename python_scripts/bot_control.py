# -*- coding: utf-8 -*-
"""
=============================================================================
 BOT CONTROL -- the remote-stop authority shared by all three live bots
 (hybrid_trading_bot_multiuser.py, intraday.py, structural_swing_pro.py).
=============================================================================
Why this file exists (read before changing anything here):

Every one of the three live bots used to poll `bot_commands.kill_switch`
once per loop as its "remote kill switch". That column HAS NEVER EXISTED --
`bot_commands` is created in supabase/migrations/20251110060738_*.sql with
(id, user_id, strategy_id, action, config, status, error_message,
created_at, processed_at, completed_at) and nothing has ever added
`kill_switch` to it. Every one of those polls raised, every bot swallowed
the error, and two of the three logged it at DEBUG once an hour. So the
"Founder's Safety" global kill switch was decorative: it could not stop
anything, ever.

Meanwhile the admin panel's "Emergency Stop All" button
(src/components/admin/BotMonitoringDashboard.tsx :: handleEmergencyStopAll)
does exactly one thing: UPDATE user_strategies SET is_running = false
WHERE is_running = true. It never called the bot manager and never wrote
any field a bot read. So the admin's one "stop everything now" control
turned the dashboard green while every subprocess kept trading live client
capital. Same for the user's own per-bot Stop in RunningBotsPanel when the
bot-manager HTTP call fails: the DB says stopped, the process disagrees.

This module makes `user_strategies.is_running` the single source of truth
that the bots actually obey -- the same field the UI has been writing all
along -- and adds the platform-wide halt that PlatformSettings.tsx has
been offering admins with nothing behind it.

DESIGN NOTES
------------
* Dependency-injected, not import-time-configured: every function takes the
  caller's own supabase client / ids. Same reason market_intelligence.py
  takes DataFrames instead of calling MT5 -- it keeps this unit-testable
  and stops a shared module from reaching into any specific bot's globals.
* FAIL-OPEN on transport errors, FAIL-CLOSED on an explicit stop. A network
  blip must never mass-halt every user's bot mid-position; but an explicit
  is_running=false / kill switch must always win. `check_remote_stop`
  returns None ("no answer, carry on") rather than raising, and only
  returns a StopSignal when the database actually said stop.
* Cheap enough to poll every loop: two indexed point-reads, and the
  platform-settings read is cached for `settings_ttl_seconds`.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, NamedTuple, Optional


class StopSignal(NamedTuple):
    """An explicit, authoritative instruction to stop trading."""
    reason: str      # short machine-ish token, e.g. 'admin_emergency_stop'
    detail: str      # human-readable line for the log / Telegram


# Cache for the platform-wide settings read: {key: (value, fetched_at)}
_settings_cache: Dict[str, Any] = {}
_settings_cache_at: float = 0.0

# Per-(user, strategy) launch state, for the startup race described in
# check_remote_stop. `_confirmed_running` is a LATCH: once we have seen
# is_running=true for a pair, any later false is an authoritative stop with no
# grace whatsoever -- an emergency stop on a live position must never wait.
_confirmed_running: set = set()
_first_check_at: Dict[tuple, float] = {}

# How long after this process's FIRST check a not-yet-confirmed launch may sit
# at is_running=false before we conclude the start genuinely failed. Generous
# on purpose: trigger-bot's fetch to the bot manager alone has an 8s timeout.
DEFAULT_STARTUP_GRACE_SECONDS = 120.0


def reset_state() -> None:
    """Clear module caches/latches. For tests and for a bot that re-launches
    in-process; a fresh subprocess starts clean anyway."""
    global _settings_cache, _settings_cache_at
    _settings_cache = {}
    _settings_cache_at = 0.0
    _confirmed_running.clear()
    _first_check_at.clear()


def explicit_stop_exists(supabase, user_id: str, strategy_id: str,
                         since_epoch: float) -> Optional[bool]:
    """
    Did a HUMAN stop this bot since `since_epoch`, or did something merely
    guess it was dead?

    This distinction is the whole ballgame, and its absence is why bots kept
    dying seconds after launch. `user_strategies.is_running` is used for two
    incompatible jobs at once:

      as a COMMAND   -- the user pressed Stop, the admin hit Emergency Stop
      as TELEMETRY   -- something inferred "this bot looks dead" and wrote it

    BotStatusSync (the dashboard, running in the user's browser) does the
    second: it sees a stale bot_heartbeats row and writes is_running=false /
    status='stopped'. During startup that inference is ALWAYS wrong, because
    a bot that has not booted yet cannot have sent a heartbeat. Observed
    live: started_at 19:00:35, stopped_at 19:00:37 -- the row was killed two
    seconds in, before the Python process had finished importing.

    Fixing each writer as it misbehaves is endless. Instead, tell the two
    apart at the source. A real stop leaves an audit trail:

      stop-trading-bot  -> INSERTs bot_audit_logs (action='stop')
      BotStatusSync     -> writes no audit row at all (verified: zero
                           references to bot_audit_logs in that component)

    Returns True (a human stopped it), False (no evidence -- inference), or
    None when the question could not be answered. None is NOT "no": callers
    must decide deliberately, because guessing either way has a cost.
    """
    try:
        since_iso = datetime.fromtimestamp(since_epoch, tz=timezone.utc).isoformat()
        res = (supabase.table('bot_audit_logs')
               .select('id')
               .eq('user_id', user_id)
               .eq('strategy_id', strategy_id)
               .eq('action', 'stop')
               .gte('created_at', since_iso)
               .limit(1)
               .execute())
        return bool(res.data)
    except Exception:
        return None


def confirm_bot_started(supabase, user_id: str, strategy_id: str,
                        pid: Optional[int] = None) -> bool:
    """
    Announce "this process is really up and trading" -- the write that
    start-trading-bot's own comment has always promised and that nothing ever
    performed:

        is_running: false, // Don't set to true until bot confirms it started
        bot_pid: null,     // Will be set by bot when it starts

    No code ever confirmed, so is_running stayed false and bot_pid stayed
    null for the platform's entire history. That was invisible while nothing
    read the column; once the bots began obeying is_running it became a
    deadlock -- the bot booted, read its own pre-launch false, and shut
    itself down a few seconds later. It also means the admin's "Emergency
    Stop All" (which targets `.eq('is_running', true)`) matched zero rows,
    and the dashboard showed "No bots running" beside a live process.

    Returns True when this call flipped the row to running.

    Claims the row from 'starting' or from a 'stopped' that no human asked
    for. It used to claim only from 'starting', which sounded safe and was
    not: the dashboard writes status='stopped' by inference within seconds of
    a launch, so the claim matched nothing and the bot then obeyed a stop
    nobody issued.

    Resurrecting a genuine stop is prevented by the CALLER, not by this
    status guard -- check_remote_stop asks explicit_stop_exists() whether a
    human actually stopped the bot and shuts down before ever calling this.
    That is the right place for the decision, because only there is the
    evidence (an audit row) available.
    """
    # Claim the row from 'starting' OR from a 'stopped' that no human asked
    # for. The guard used to be status='starting' alone, which meant the
    # dashboard's bogus 'stopped' write (see explicit_stop_exists) made this
    # match nothing -- the bot could not claim its own row and then obeyed
    # the very stop that should never have been written. Claiming from
    # 'stopped' is safe only because a human stop is detected separately and
    # checked by the caller before we get here.
    claimable = ('starting', 'stopped')
    try:
        res = (supabase.table('user_strategies')
               .update({'is_running': True,
                        'status': 'running',
                        'bot_pid': pid,
                        'stopped_at': None})
               .eq('user_id', user_id)
               .eq('strategy_id', strategy_id)
               .in_('status', list(claimable))
               .execute())
    except Exception:
        # Fail OPEN, consistent with the rest of this module: if we cannot
        # write the confirmation we must NOT refuse to trade. The startup
        # grace in check_remote_stop covers the window, and a bot that never
        # manages to confirm stops itself once the grace expires.
        return False

    if res.data:
        _confirmed_running.add((user_id, strategy_id))
        return True
    return False


def _platform_halt(supabase, ttl_seconds: float = 30.0) -> Optional[StopSignal]:
    """
    Platform-wide halt, set by an admin in PlatformSettings.tsx.

    Reads the `platform_settings` key/value table -- which the admin UI has
    been writing to since it shipped and which NOTHING in this repo has
    ever read back (confirmed by grepping supabase/functions and
    python_scripts for 'platform_settings' / 'maintenance_mode': zero
    reads). Two keys stop trading:

      trading_halted  -- explicit "stop every bot on the platform NOW"
      maintenance_mode -- the toggle already present in the admin UI

    Cached for `ttl_seconds` so polling this every loop iteration costs
    roughly nothing.
    """
    global _settings_cache, _settings_cache_at

    now = time.time()
    if now - _settings_cache_at > ttl_seconds:
        try:
            res = supabase.table('platform_settings').select('key,value').in_(
                'key', ['trading_halted', 'maintenance_mode']
            ).execute()
            _settings_cache = {r['key']: r.get('value') for r in (res.data or [])}
            _settings_cache_at = now
        except Exception:
            # Fail OPEN: a transport error here must not halt every bot on
            # the platform. Keep whatever was last known good and move on.
            return None

    for key, label in (('trading_halted', 'platform trading halt'),
                       ('maintenance_mode', 'platform maintenance mode')):
        val = _settings_cache.get(key)
        # value is JSONB: accept true, "true", {"enabled": true}
        enabled = False
        if isinstance(val, bool):
            enabled = val
        elif isinstance(val, str):
            enabled = val.strip().lower() == 'true'
        elif isinstance(val, dict):
            enabled = bool(val.get('enabled') or val.get('value'))
        if enabled:
            return StopSignal(
                reason=f'platform_{key}',
                detail=f'{label} is active -- an admin halted trading platform-wide',
            )
    return None


def check_remote_stop(supabase, user_id: str, strategy_id: str,
                      check_platform: bool = True,
                      startup_grace_seconds: float = DEFAULT_STARTUP_GRACE_SECONDS
                      ) -> Optional[StopSignal]:
    """
    "Should this bot stop right now?" -- the one call every live bot makes
    each loop iteration.

    Returns a StopSignal when the platform has explicitly said stop, or
    None when it hasn't (including when we simply couldn't reach the
    database -- see the fail-open note in this module's docstring).

    Checks, in order of authority:

      1. platform-wide halt / maintenance mode (admin, all users)
      2. user_strategies.is_running == false for THIS (user, strategy)

    (2) is what actually repairs the broken control surface: it is the
    exact field written by the admin's "Emergency Stop All", by the admin's
    per-bot Stop, by the user's own Stop button, and by the
    stop-trading-bot edge function. Obeying it means every one of those
    controls now really stops the process instead of only relabelling it in
    the UI.

    A missing row is deliberately NOT treated as a stop: a bot launched
    before its row is written (or with an id mismatch) should keep running
    and be stopped explicitly, not silently killed by a race.

    THE STARTUP RACE (this cost a live bot 10 seconds of life; see
    confirm_bot_started). is_running=false does not only mean "stop" -- it is
    also the value start-trading-bot writes BEFORE the process is launched,
    meaning "not confirmed started yet". A booting bot reads that pre-launch
    false and, taken literally, kills itself. So false is resolved by
    context, never blindly:

      * Latched running (we have seen true at least once) -> STOP, instantly.
        No grace. This is the emergency-stop path and it must not be delayed.
      * status says 'stopped'/'stopping' -> STOP, instantly, even if we never
        saw true: somebody really did press Stop during the launch window.
      * Otherwise (status 'starting', or absent) -> unconfirmed launch. Return
        None while within startup_grace_seconds of this process's first check,
        then STOP with reason 'start_never_confirmed' -- which is a real
        failure worth surfacing, not a stop instruction, and is named
        distinctly so the log says what actually happened.
    """
    if check_platform:
        halt = _platform_halt(supabase)
        if halt is not None:
            return halt

    key = (user_id, strategy_id)
    now = time.time()
    first_seen = _first_check_at.setdefault(key, now)

    try:
        res = (supabase.table('user_strategies')
               .select('is_running,status')
               .eq('user_id', user_id)
               .eq('strategy_id', strategy_id)
               .limit(1)
               .execute())
    except Exception:
        return None  # fail open -- transport problem, not an instruction

    rows = res.data or []
    if not rows:
        return None  # no row yet: see docstring, don't infer a stop

    if rows[0].get('is_running') is True:
        _confirmed_running.add(key)   # latch: later falses are authoritative
        return None

    if rows[0].get('is_running') is not False:
        return None  # null/absent -- not an instruction either way

    status = (rows[0].get('status') or '').strip().lower()

    # ALREADY RUNNING: stop instantly, no questions, no grace. An emergency
    # stop on an open position must never wait, and once we have been running
    # a false here can only mean somebody turned us off.
    if key in _confirmed_running:
        return StopSignal(
            reason='remote_stop',
            detail=('user_strategies.is_running is false -- stopped from the '
                    'dashboard (user Stop, admin per-bot Stop, admin '
                    'Emergency Stop All, or the stop-trading-bot function)'),
        )

    # STILL LAUNCHING: a 'stopped' row here is far more often the dashboard
    # guessing than a person deciding, so require evidence before dying.
    # Asked only in this narrow window, so the running-bot path above stays
    # a plain two-column read.
    if status in ('stopped', 'stopping'):
        human = explicit_stop_exists(supabase, user_id, strategy_id, first_seen)
        if human:
            return StopSignal(
                reason='remote_stop',
                detail=('stopped during launch by an explicit user/admin action '
                        '(bot_audit_logs recorded a stop)'),
            )
        if human is False:
            # No audit row: inference, not a command. Say so loudly -- this is
            # the failure that repeatedly killed bots seconds after start, and
            # a silent recovery would hide that it is still happening.
            return None
        # human is None -- the audit table could not be read. Do not guess.
        # Carrying on is the safer error here: the admin's Emergency Stop All
        # only ever targets `.eq('is_running', true)`, so it cannot be aimed at
        # a bot that has not confirmed yet, and a real Stop also kills the
        # process out-of-band via the bot manager. Refusing to start, by
        # contrast, is the exact breakage being fixed.
        return None

    if now - first_seen < startup_grace_seconds:
        return None  # launch not confirmed yet -- not a stop instruction

    return StopSignal(
        reason='start_never_confirmed',
        detail=(f'is_running never became true within '
                f'{startup_grace_seconds:.0f}s of startup (status={status!r}). '
                'The bot launched but its start was never confirmed -- check '
                'that confirm_bot_started() ran and that trigger-bot reached '
                'the bot manager.'),
    )
