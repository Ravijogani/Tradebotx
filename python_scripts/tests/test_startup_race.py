import pathlib as _pl
_SCRIPTS = _pl.Path(__file__).resolve().parent.parent  # python_scripts/
import sys, time
sys.path.insert(0, str(_SCRIPTS))
import bot_control

passed = failed = 0
def check(name, fn):
    global passed, failed
    bot_control.reset_state()
    try:
        fn(); passed += 1; print(f"  PASS  {name}")
    except AssertionError as e:
        failed += 1; print(f"  FAIL  {name}: {e}")
    except Exception as e:
        failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")

U, S = 'user-1', 'strat-1'

class Q:
    """Minimal supabase double. Records update payloads; honours .eq filters."""
    def __init__(self, row, settings=None, raise_on=None):
        self.row = row; self.settings = settings or []
        self.raise_on = raise_on or set(); self.updates = []
    def table(self, name):
        self._t = name; self._filters = {}; self._payload = None; self._mode = 'select'; return self
    def select(self, *a): self._mode = 'select'; return self
    def update(self, payload): self._mode = 'update'; self._payload = payload; return self
    def in_(self, *a): return self
    def eq(self, k, v): self._filters[k] = v; return self
    def limit(self, n): return self
    def execute(self):
        if self._t in self.raise_on: raise RuntimeError("transport down")
        if self._t == 'platform_settings':
            return type('R', (), {'data': self.settings})
        if self._mode == 'update':
            # emulate WHERE: all eq filters must match current row
            match = all(self.row.get(k) == v for k, v in self._filters.items()
                        if k not in ('user_id', 'strategy_id'))
            if match:
                self.row.update(self._payload); self.updates.append(dict(self._payload))
                return type('R', (), {'data': [dict(self.row)]})
            self.updates.append({'REFUSED': dict(self._payload)})
            return type('R', (), {'data': []})
        return type('R', (), {'data': [dict(self.row)]})

# ---- 1. THE BUG: pre-launch false + status 'starting' must NOT stop the bot.
def t1():
    q = Q({'is_running': False, 'status': 'starting'})
    assert bot_control.check_remote_stop(q, U, S) is None, "killed itself at boot"
check("boot: is_running=false + status='starting' -> no stop (the live bug)", t1)

# ---- 2. The confirmation flips the row and sets the pid.
def t2():
    q = Q({'is_running': False, 'status': 'starting'})
    assert bot_control.confirm_bot_started(q, U, S, 4242) is True
    assert q.row['is_running'] is True and q.row['status'] == 'running'
    assert q.row['bot_pid'] == 4242, "bot_pid still not set"
    assert q.row['stopped_at'] is None
    assert bot_control.check_remote_stop(q, U, S) is None
check("confirm_bot_started sets is_running/status/bot_pid", t2)

# ---- 3. EMERGENCY STOP MUST BE INSTANT once running. No grace.
def t3():
    q = Q({'is_running': False, 'status': 'starting'})
    bot_control.confirm_bot_started(q, U, S, 1)
    q.row.update({'is_running': False, 'status': 'stopped'})   # admin stops it
    sig = bot_control.check_remote_stop(q, U, S)
    assert sig is not None, "EMERGENCY STOP IGNORED"
    assert sig.reason == 'remote_stop'
check("running -> false: stop is INSTANT (no grace)", t3)

# ---- 4. Latch: even if status is left stale/'running', a false still stops.
def t4():
    q = Q({'is_running': True, 'status': 'running'})
    assert bot_control.check_remote_stop(q, U, S) is None   # latches
    q.row['is_running'] = False                              # status left stale
    sig = bot_control.check_remote_stop(q, U, S)
    assert sig is not None and sig.reason == 'remote_stop', "latch failed"
check("latch: seen-true then false stops even with stale status", t4)

# ---- 5. Stop pressed DURING launch (never confirmed) -> stop immediately.
def t5():
    q = Q({'is_running': False, 'status': 'stopped'})
    sig = bot_control.check_remote_stop(q, U, S)
    assert sig is not None, "ignored a Stop pressed during launch"
    assert sig.reason == 'remote_stop'
check("stop during launch (status='stopped') -> stop, no grace", t5)

# ---- 6. The guard must not resurrect a bot stopped during launch.
def t6():
    q = Q({'is_running': False, 'status': 'stopped'})   # user hit Stop first
    assert bot_control.confirm_bot_started(q, U, S, 9) is False, "RESURRECTED a stopped bot"
    assert q.row['is_running'] is False and q.row['status'] == 'stopped'
    assert bot_control.check_remote_stop(q, U, S) is not None
check("confirm refuses to resurrect a bot stopped mid-launch", t6)

# ---- 7. Grace EXPIRES: unconfirmed forever is a real failure, named distinctly.
def t7():
    q = Q({'is_running': False, 'status': 'starting'})
    assert bot_control.check_remote_stop(q, U, S, startup_grace_seconds=0.05) is None
    time.sleep(0.08)
    sig = bot_control.check_remote_stop(q, U, S, startup_grace_seconds=0.05)
    assert sig is not None, "unconfirmed launch never surfaced"
    assert sig.reason == 'start_never_confirmed', f"misleading reason: {sig.reason}"
    assert 'never became true' in sig.detail
check("grace expiry -> 'start_never_confirmed', not a fake dashboard stop", t7)

# ---- 8. Fail-open on transport error, even mid-startup.
def t8():
    q = Q({'is_running': False, 'status': 'starting'}, raise_on={'user_strategies'})
    assert bot_control.check_remote_stop(q, U, S) is None
    assert bot_control.confirm_bot_started(q, U, S, 1) is False   # must not raise
check("transport error -> fail open, confirm returns False without raising", t8)

# ---- 9. Platform halt still outranks everything, including startup grace.
def t9():
    q = Q({'is_running': False, 'status': 'starting'},
          settings=[{'key': 'trading_halted', 'value': True}])
    sig = bot_control.check_remote_stop(q, U, S)
    assert sig is not None and sig.reason == 'platform_trading_halted'
check("platform halt beats startup grace", t9)

# ---- 10. Missing row still not a stop (original behaviour preserved).
def t10():
    class Empty(Q):
        def execute(self):
            if self._t == 'platform_settings': return type('R', (), {'data': []})
            return type('R', (), {'data': []})
    assert bot_control.check_remote_stop(Empty({}), U, S) is None
check("missing row -> still not a stop", t10)

# ---- 11. Per-(user,strategy) isolation: one bot's latch must not stop another.
def t11():
    q1 = Q({'is_running': True, 'status': 'running'})
    bot_control.check_remote_stop(q1, U, S)          # latch pair 1
    q2 = Q({'is_running': False, 'status': 'starting'})
    assert bot_control.check_remote_stop(q2, U, 'strat-2') is None, "latch leaked across strategies"
check("latch is per (user, strategy), no cross-talk", t11)

# ---- 12. Full live sequence end-to-end, mirroring the Lightsail log.
def t12():
    q = Q({'is_running': False, 'status': 'starting'})     # start-trading-bot
    assert bot_control.check_remote_stop(q, U, S) is None  # startup check (was fatal)
    assert bot_control.confirm_bot_started(q, U, S, 7788) is True
    for _ in range(200):                                   # 200 trading cycles
        assert bot_control.check_remote_stop(q, U, S) is None
    q.row.update({'is_running': False, 'status': 'stopped'})   # user presses Stop
    assert bot_control.check_remote_stop(q, U, S).reason == 'remote_stop'
check("end-to-end: boots, confirms, runs 200 cycles, obeys Stop", t12)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
