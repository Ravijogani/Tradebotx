import pathlib as _pl
_SCRIPTS = _pl.Path(__file__).resolve().parent.parent  # python_scripts/
import sys, time
sys.path.insert(0, str(_SCRIPTS))
import bot_control as bc

passed = failed = 0
def check(name, cond):
    global passed, failed
    if cond: passed += 1; print(f"PASS: {name}")
    else: failed += 1; print(f"FAIL: {name}")

class FakeRes:
    def __init__(self, data): self.data = data

class FakeQuery:
    def __init__(self, table, store): self.table, self.store = table, store
    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def in_(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def gte(self, *a, **k): return self
    def execute(self):
        if isinstance(self.store, Exception): raise self.store
        return FakeRes(self.store)

class FakeSupabase:
    def __init__(self, tables): self.tables = tables
    def table(self, name): return FakeQuery(name, self.tables.get(name, []))

def reset_cache():
    bc.reset_state()
    bc._settings_cache = {}; bc._settings_cache_at = 0.0

# --- user_strategies.is_running gate (the actual bug fix) ---
reset_cache()
# CONTRACT NOTE: a bare is_running=False is no longer read as a stop on its
# own. It is also the value start-trading-bot writes BEFORE launching, meaning
# "not confirmed started yet", and taking it literally made booting bots kill
# themselves seconds after start (see test_startup_race.py). It is a stop when
# the row says so, or once the bot has confirmed running.
# A stop DURING LAUNCH now requires evidence a human asked for it -- an audit
# row. Without one it is the dashboard's inference, which killed live bots two
# seconds after start. See test_stop_authority.py for the full contract.
sb = FakeSupabase({'platform_settings': [],
                   'user_strategies': [{'is_running': False, 'status': 'stopped'}],
                   'bot_audit_logs': [{'id': 1}]})
sig = bc.check_remote_stop(sb, 'u1', 's1')
check("is_running=False + status stopped + audit row -> StopSignal", sig is not None and sig.reason == 'remote_stop')

reset_cache()
sb = FakeSupabase({'platform_settings': [],
                   'user_strategies': [{'is_running': False, 'status': 'stopped'}],
                   'bot_audit_logs': []})
check("is_running=False + status stopped, NO audit row -> keeps running",
      bc.check_remote_stop(sb, 'u1', 's1') is None)

# The emergency-stop guarantee: once running, a bare False stops INSTANTLY.
reset_cache()
bc._confirmed_running.add(('u1', 's1'))
sb = FakeSupabase({'platform_settings': [], 'user_strategies': [{'is_running': False}]})
sig = bc.check_remote_stop(sb, 'u1', 's1')
check("confirmed-running then is_running=False -> instant StopSignal",
      sig is not None and sig.reason == 'remote_stop')

# An unconfirmed launch is NOT a stop -- this is the bug that killed live bots.
reset_cache()
sb = FakeSupabase({'platform_settings': [], 'user_strategies': [{'is_running': False, 'status': 'starting'}]})
check("unconfirmed launch -> no stop (startup grace)", bc.check_remote_stop(sb, 'u1', 's1') is None)

reset_cache()
sb = FakeSupabase({'platform_settings': [], 'user_strategies': [{'is_running': True}]})
check("is_running=True -> no stop", bc.check_remote_stop(sb, 'u1', 's1') is None)

reset_cache()
sb = FakeSupabase({'platform_settings': [], 'user_strategies': []})
check("missing row -> no stop (no silent kill on race)", bc.check_remote_stop(sb, 'u1', 's1') is None)

# --- fail-open on transport error ---
reset_cache()
sb = FakeSupabase({'platform_settings': [], 'user_strategies': RuntimeError("network down")})
check("user_strategies transport error -> fail OPEN (None)", bc.check_remote_stop(sb, 'u1', 's1') is None)

reset_cache()
sb = FakeSupabase({'platform_settings': RuntimeError("boom"), 'user_strategies': [{'is_running': True}]})
check("platform_settings transport error -> fail OPEN, still checks user row",
      bc.check_remote_stop(sb, 'u1', 's1') is None)

# --- platform-wide halt, all JSONB shapes ---
for val, label in [(True, "bool true"), ("true", "string 'true'"), ({"enabled": True}, "dict enabled")]:
    reset_cache()
    sb = FakeSupabase({'platform_settings': [{'key': 'trading_halted', 'value': val}],
                       'user_strategies': [{'is_running': True}]})
    sig = bc.check_remote_stop(sb, 'u1', 's1')
    check(f"trading_halted={label} -> StopSignal", sig is not None and sig.reason == 'platform_trading_halted')

reset_cache()
sb = FakeSupabase({'platform_settings': [{'key': 'maintenance_mode', 'value': True}],
                   'user_strategies': [{'is_running': True}]})
sig = bc.check_remote_stop(sb, 'u1', 's1')
check("maintenance_mode=True -> StopSignal", sig is not None and sig.reason == 'platform_maintenance_mode')

reset_cache()
sb = FakeSupabase({'platform_settings': [{'key': 'trading_halted', 'value': False}],
                   'user_strategies': [{'is_running': True}]})
check("trading_halted=False -> no stop", bc.check_remote_stop(sb, 'u1', 's1') is None)

# platform halt outranks a running user row
reset_cache()
sb = FakeSupabase({'platform_settings': [{'key': 'trading_halted', 'value': True}],
                   'user_strategies': [{'is_running': True}]})
check("platform halt outranks is_running=True", bc.check_remote_stop(sb, 'u1', 's1') is not None)

# check_platform=False skips it
reset_cache()
sb = FakeSupabase({'platform_settings': [{'key': 'trading_halted', 'value': True}],
                   'user_strategies': [{'is_running': True}]})
check("check_platform=False skips platform halt",
      bc.check_remote_stop(sb, 'u1', 's1', check_platform=False) is None)

# --- caching behaviour ---
reset_cache()
class CountingSupabase(FakeSupabase):
    def __init__(self, tables): super().__init__(tables); self.calls = 0
    def table(self, name):
        if name == 'platform_settings': self.calls += 1
        return FakeQuery(name, self.tables.get(name, []))
sb = CountingSupabase({'platform_settings': [], 'user_strategies': [{'is_running': True}]})
for _ in range(5): bc.check_remote_stop(sb, 'u1', 's1')
check("platform_settings read is cached across loops (1 fetch, not 5)", sb.calls == 1)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
