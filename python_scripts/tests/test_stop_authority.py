"""
The permanent fix for "the bot stops itself seconds after starting".

user_strategies.is_running was doing two incompatible jobs: carrying a human
COMMAND (Stop pressed) and carrying TELEMETRY (something guessed the bot was
dead). The dashboard writes the second within seconds of a launch, and the
bot obeyed it as if it were the first. Observed live: started 19:00:35,
stopped 19:00:37 -- two seconds, before Python had finished importing.

These tests pin the rule that separates them, in both directions: a real stop
must still stop the bot, and a guess must never be able to.
"""
import pathlib as _pl
import sys, time
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
import bot_control as bc

passed = failed = 0
def check(name, fn):
    global passed, failed
    bc.reset_state()
    try:
        fn(); passed += 1; print(f"  PASS  {name}")
    except AssertionError as e:
        failed += 1; print(f"  FAIL  {name}: {e}")
    except Exception as e:
        failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")

U, S = 'u1', 's1'

class FakeDB:
    """Rows keyed by table. `audit` = human stop rows. raise_on = tables that error."""
    def __init__(self, strategy_row, audit=None, raise_on=(), settings=None):
        self.row = strategy_row; self.audit = audit or []
        self.raise_on = set(raise_on); self.settings = settings or []
        self.updates = []
    def table(self, n):
        self._t = n; self._mode='select'; self._payload=None; self._f={}; return self
    def select(self, *a): self._mode='select'; return self
    def update(self, p): self._mode='update'; self._payload=p; return self
    def eq(self, k, v): self._f[k]=v; return self
    def in_(self, k, v): self._f[k]=('in', v); return self
    def gte(self, k, v): return self
    def limit(self, n): return self
    def execute(self):
        if self._t in self.raise_on: raise RuntimeError("db unreachable")
        if self._t == 'platform_settings': return type('R',(),{'data': self.settings})
        if self._t == 'bot_audit_logs':    return type('R',(),{'data': list(self.audit)})
        if self._mode == 'update':
            st = self._f.get('status')
            ok = (self.row.get('status') in st[1]) if isinstance(st, tuple) else True
            if ok:
                self.row.update(self._payload); self.updates.append(dict(self._payload))
                return type('R',(),{'data':[dict(self.row)]})
            return type('R',(),{'data':[]})
        return type('R',(),{'data':[dict(self.row)]})

# ---------- THE BUG: dashboard inference during launch ----------
def t1():
    db = FakeDB({'is_running': False, 'status': 'stopped'}, audit=[])
    assert bc.check_remote_stop(db, U, S) is None, "bot killed itself on an inferred stop"
check("launching + 'stopped' with NO audit row -> keeps running (the live bug)", t1)

def t2():
    db = FakeDB({'is_running': False, 'status': 'stopped'}, audit=[])
    assert bc.check_remote_stop(db, U, S) is None
    assert bc.confirm_bot_started(db, U, S, 4242) is True, "could not claim its own row"
    assert db.row['is_running'] is True and db.row['status'] == 'running'
    assert db.row['bot_pid'] == 4242
check("...and can then CLAIM the row it was wrongly stopped in", t2)

# ---------- A REAL STOP MUST STILL WIN ----------
def t3():
    db = FakeDB({'is_running': False, 'status': 'stopped'}, audit=[{'id': 1}])
    sig = bc.check_remote_stop(db, U, S)
    assert sig is not None, "IGNORED a genuine user Stop during launch"
    assert sig.reason == 'remote_stop' and 'explicit' in sig.detail
check("launching + 'stopped' WITH an audit row -> stops (real Stop honoured)", t3)

def t4():
    db = FakeDB({'is_running': False, 'status': 'stopped'}, audit=[{'id': 1}])
    assert bc.confirm_bot_started(db, U, S, 1) is True  # claim itself is unguarded...
    # ...but the caller stops first, so a real stop is never resurrected:
    bc.reset_state()
    db2 = FakeDB({'is_running': False, 'status': 'stopped'}, audit=[{'id': 1}])
    assert bc.check_remote_stop(db2, U, S) is not None
check("a real stop is caught by check_remote_stop before any claim", t4)

# ---------- EMERGENCY STOP ON A RUNNING BOT: UNCHANGED ----------
def t5():
    db = FakeDB({'is_running': True, 'status': 'running'})
    assert bc.check_remote_stop(db, U, S) is None          # latches
    db.row.update({'is_running': False, 'status': 'stopped'})
    sig = bc.check_remote_stop(db, U, S)
    assert sig is not None, "EMERGENCY STOP IGNORED on a running bot"
    assert sig.reason == 'remote_stop'
check("confirmed-running -> is_running=false stops INSTANTLY (no audit needed)", t5)

def t6():
    # and it must not even consult the audit table on that path
    db = FakeDB({'is_running': True, 'status': 'running'}, raise_on={'bot_audit_logs'})
    bc.check_remote_stop(db, U, S)
    db.row.update({'is_running': False, 'status': 'stopped'})
    assert bc.check_remote_stop(db, U, S) is not None, "running-bot stop depended on the audit read"
check("running-bot stop works even if bot_audit_logs is unreadable", t6)

# ---------- DEGRADED / HOSTILE CONDITIONS ----------
def t7():
    db = FakeDB({'is_running': False, 'status': 'stopped'}, raise_on={'bot_audit_logs'})
    assert bc.check_remote_stop(db, U, S) is None, "refused to start when audit table unreadable"
check("audit table unreadable during launch -> starts anyway (documented choice)", t7)

def t8():
    db = FakeDB({'is_running': False, 'status': 'starting'}, audit=[])
    assert bc.check_remote_stop(db, U, S) is None
check("normal launch ('starting') unaffected", t8)

def t9():
    db = FakeDB({'is_running': False, 'status': 'stopped'}, audit=[],
                settings=[{'key': 'trading_halted', 'value': True}])
    sig = bc.check_remote_stop(db, U, S)
    assert sig is not None and sig.reason == 'platform_trading_halted'
check("platform halt still outranks everything", t9)

def t10():
    db = FakeDB({'is_running': False, 'status': 'starting'}, audit=[])
    assert bc.check_remote_stop(db, U, S, startup_grace_seconds=0.05) is None
    time.sleep(0.08)
    sig = bc.check_remote_stop(db, U, S, startup_grace_seconds=0.05)
    assert sig is not None and sig.reason == 'start_never_confirmed'
check("a launch that never confirms is still surfaced, not hidden forever", t10)

# ---------- FULL LIFECYCLE ----------
def t11():
    db = FakeDB({'is_running': False, 'status': 'starting'}, audit=[])
    assert bc.check_remote_stop(db, U, S) is None
    db.row.update({'is_running': False, 'status': 'stopped'})   # dashboard guesses, 2s in
    assert bc.check_remote_stop(db, U, S) is None                # survives
    assert bc.confirm_bot_started(db, U, S, 777) is True         # claims
    for _ in range(300):
        assert bc.check_remote_stop(db, U, S) is None            # trades
    db.row.update({'is_running': False, 'status': 'stopped'})    # user presses Stop
    assert bc.check_remote_stop(db, U, S).reason == 'remote_stop'
check("end-to-end: survives the guess, claims, runs 300 cycles, obeys the real Stop", t11)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
