"""
The bot killed itself at the same time every day. Here is the chain.

  21:30 UTC  the rollover guard fires and `continue`s past the rest of the
             loop -- including send_heartbeat().
  21:35 UTC  monitor-bot-health sees a heartbeat 5 minutes stale, decides the
             process crashed, writes is_running=false / status='crashed'.
  21:35 UTC  check_remote_stop -- which runs BEFORE the guard, so it never
             stopped running -- reads that false and exits the process.

So the bot spent 90 minutes a day asking "should I stop?" while starving the
only signal that proved it was alive, and then believed the answer.

Three separate defects, each pinned here:
  * the guard must block ENTRIES, not the loop;
  * a health-sweep reconciliation is a statement ABOUT the process, not an
    instruction TO it -- a live bot must re-assert itself, not die;
  * a stop must always reach the user, and a repeating fault must not send
    1440 Telegram messages a day.
"""
import pathlib as _pl
import sys
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))

import bot_control as bc

passed = failed = 0
def check(name, fn):
    global passed, failed
    try:
        fn(); passed += 1; print(f"  PASS  {name}")
    except AssertionError as e:
        failed += 1; print(f"  FAIL  {name}: {e}")
    except Exception as e:
        failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")

ROOT = _pl.Path(__file__).resolve().parent.parent
SRC = open(ROOT / 'hybrid_trading_bot_multiuser.py', encoding='utf-8').read()
LINES = SRC.split('\n')


class _Rows:
    """Minimal supabase double: returns one user_strategies row."""
    def __init__(self, row): self.row = row; self.data = [row] if row else []
    def table(self, n): return self
    def select(self, *a, **k): return self
    def update(self, p): self.updated = p; return self
    def eq(self, *a, **k): return self
    def limit(self, n): return self
    def order(self, *a, **k): return self
    def gte(self, *a, **k): return self
    def execute(self): return self


def _fresh(uid='u', sid='s'):
    bc.reset_state()
    return uid, sid


# ---------- 1. the rollover guard ----------
def t1():
    i = next(n for n, l in enumerate(LINES) if 'if _in_rollover:' in l)
    body = LINES[i:i + 14]
    assert not any(l.strip() == 'continue' for l in body), \
        "the rollover guard still skips the whole loop -- the heartbeat dies with it"
check("the rollover guard no longer skips the loop", t1)

def t2():
    # The heartbeat must be reachable during the blackout: it has to sit
    # OUTSIDE the guard, and the guard must no longer be able to jump past it.
    i = next(n for n, l in enumerate(LINES) if 'if _in_rollover:' in l)
    # The in-loop heartbeat, not the startup one -- the first that follows
    # the guard.
    hb = next(n for n, l in enumerate(LINES[i:], i)
              if "send_heartbeat(status='running'" in l)
    assert hb > i, "no heartbeat after the rollover guard at all"
    # Scope to the guard's OWN block by indentation rather than a fixed
    # window, so neighbouring code cannot make this pass or fail by accident.
    guard_indent = len(LINES[i]) - len(LINES[i].lstrip())
    body = []
    for l in LINES[i + 1:]:
        if l.strip() and (len(l) - len(l.lstrip())) <= guard_indent:
            break
        body.append(l)
    assert body, "the guard has no body"
    assert not any(l.strip() in ('continue', 'break') for l in body), \
        "the guard can still short-circuit before the heartbeat runs"
check("the heartbeat still fires during the rollover blackout", t2)

def t3():
    # Entries must still be blocked -- the guard has a real job.
    assert '_wk == \'NO_NEW\' or _in_rollover' in SRC, \
        "the rollover flag no longer blocks new entries anywhere"
check("new entries are still blocked during rollover", t3)

def t4():
    # Position management must survive the blackout. The spike guard lives in
    # manage_all_positions, and rollover is the highest-spread window of the
    # day -- exactly when it matters most.
    i = next(n for n, l in enumerate(LINES) if 'if _in_rollover:' in l)
    mg = next(n for n, l in enumerate(LINES) if 'target=manage_all_positions' in l)
    assert mg > i, "fixture assumption broken"
    body = LINES[i:i + 14]
    assert not any(l.strip() == 'continue' for l in body), \
        "position management is still skipped through the highest-spread window"
check("positions are still managed during the rollover blackout", t4)


# ---------- 2. a false crash is not a stop ----------
def t5():
    uid, sid = _fresh()
    db = _Rows({'is_running': True, 'status': 'running'})
    assert bc.check_remote_stop(db, uid, sid, check_platform=False) is None
    # now the health sweep reconciles it
    db = _Rows({'is_running': False, 'status': 'crashed'})
    sig = bc.check_remote_stop(db, uid, sid, check_platform=False)
    assert sig is not None and sig.reason == 'false_crash_report', \
        f"a stale-heartbeat reconciliation still reads as a user stop: {sig}"
check("a 'crashed' reconciliation is reported as a false crash, not a stop", t5)

def t6():
    # A REAL stop must still be instant. This is the emergency path.
    uid, sid = _fresh()
    bc.check_remote_stop(_Rows({'is_running': True, 'status': 'running'}), uid, sid,
                         check_platform=False)
    for status in ('stopped', 'stopping', '', 'running'):
        sig = bc.check_remote_stop(_Rows({'is_running': False, 'status': status}),
                                   uid, sid, check_platform=False)
        assert sig is not None and sig.reason == 'remote_stop', \
            f"status={status!r} did not stop the bot -- Stop must always work"
check("a real Stop still fires instantly, whatever the status says", t6)

def t7():
    # reassert_running must undo all three lies the sweep left behind.
    uid, sid = _fresh()
    db = _Rows({'is_running': False, 'status': 'crashed'})
    assert bc.reassert_running(db, uid, sid) is True
    upd = db.updated
    assert upd['is_running'] is True, "is_running not restored"
    assert upd['status'] == 'running', "status left as crashed"
    assert upd.get('bot_pid'), "bot_pid not restored -- the row still names nothing"
check("re-asserting restores is_running, status and pid", t7)

def t8():
    class Boom(_Rows):
        def execute(self): raise RuntimeError("network gone")
    assert bc.reassert_running(Boom({}), 'u', 's') is False, \
        "a failed re-assert raised instead of letting the bot keep trading"
check("a failed re-assert never interrupts trading", t8)

def t9():
    # All three bots must treat it the same way, or the two that don't keep
    # dying nightly.
    for f in ('hybrid_trading_bot_multiuser.py', 'intraday.py', 'structural_swing_pro.py'):
        src = open(ROOT / f, encoding='utf-8').read()
        assert "'false_crash_report'" in src, f"{f} still exits on a false crash report"
        assert 'reassert_running' in src, f"{f} never puts the row back"
check("all three bots recover from a false crash report", t9)

def t10():
    # Rate-limited: a persistent disagreement must not hammer the DB or log.
    i = SRC.find("_stop.reason == 'false_crash_report'")
    body = SRC[i:i + 900]
    assert '_last_reassert' in body and '> 60' in body, \
        "the re-assert is not rate-limited"
check("the re-assert is rate-limited, not once per cycle", t10)


# ---------- 3. the user must be told ----------
def t11():
    # Startup failures were completely silent: dashboard says "starting",
    # nothing trades, no notification anywhere.
    for marker in ('API key is not set', 'MetaTrader 5 would not initialise'):
        assert marker in SRC, f"startup failure still silent: {marker}"
check("a bot that cannot start says so on Telegram", t11)

def t12():
    # Every session-ending path must notify.
    for marker in ('EMERGENCY STOP', 'EQUITY PROTECT TRIGGERED', 'Bot Stopped'):
        assert marker in SRC, f"exit path with no Telegram: {marker}"
    # The IN-LOOP stop, not the startup one -- 'shutting down' names it.
    i = SRC.find('[REMOTE STOP] {_stop.reason}: {_stop.detail} -- shutting down.')
    assert i > 0, "the in-loop remote-stop exit vanished"
    assert 'send_telegram_notification' in SRC[i:i + 700], "remote stop does not notify"
check("every stop reaches Telegram", t12)

def t13():
    # The recovering error loop retries every 60s; unthrottled that is 1440
    # messages a day, which is how an alert channel gets muted.
    i = SRC.find('_err_alerts')
    assert i > 0, "the recurring-error Telegram is unthrottled"
    body = SRC[i:i + 1200]
    assert '3600' in body, "errors are not throttled to at most hourly"
    assert 'still running and retrying' in SRC, \
        "the message does not say the bot survived -- it reads like a stop"
check("a repeating fault alerts once an hour, not once a minute", t13)


print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
