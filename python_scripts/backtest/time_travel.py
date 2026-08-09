"""
Makes datetime.now() inside the imported bot module return a fixed
"as-of" timestamp instead of the real wall clock, for the duration of one
replay step.

Why this is necessary: several signal functions read the actual current
time directly rather than deriving it from the bar being evaluated --
e.g. strategy_ict_killzone does `current_hour = datetime.now(timezone.utc).hour`
and get_current_session()/is_kill_zone() do the same. Live, that's correct
(the bar being evaluated basically IS "now"). In a backtest replaying
2019 data, "now" being the actual current wall-clock time would make every
kill-zone/session-gated strategy fire based on today's hour, not the
historical bar's hour -- silently wrong for exactly the strategies that
gate on time of day.

This patches the `datetime` name as it exists in the bot module's own
namespace (`from datetime import datetime, timezone, timedelta` at the top
of hybrid_trading_bot_multiuser.py), not the stdlib module globally -- so
it can never leak into other code, and needs zero changes to the bot file.
"""

from contextlib import contextmanager
from datetime import datetime as _real_datetime, timezone as _real_timezone


def _make_frozen_datetime(frozen_at: _real_datetime):
    class _FrozenDateTime(_real_datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return frozen_at.astimezone(tz)
            return frozen_at
        @classmethod
        def utcnow(cls):
            return frozen_at.astimezone(_real_timezone.utc).replace(tzinfo=None)
    return _FrozenDateTime


@contextmanager
def frozen_at(bot_module, as_of: _real_datetime):
    """
    Usage:
        with frozen_at(bot_module, bar_timestamp):
            signal = bot_module.strategy_ict_killzone(...)

    `as_of` must be timezone-aware (UTC) -- the bot's kill-zone/session
    logic reads datetime.now(timezone.utc).hour, so a naive datetime would
    raise or silently misbehave depending on comparison context.
    """
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=_real_timezone.utc)

    original = bot_module.datetime
    bot_module.datetime = _make_frozen_datetime(as_of)
    try:
        yield
    finally:
        bot_module.datetime = original
