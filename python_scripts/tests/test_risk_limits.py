import pathlib as _pl
_SCRIPTS = _pl.Path(__file__).resolve().parent.parent  # python_scripts/
import sys, tempfile, os
sys.path.insert(0, str(_SCRIPTS))
import risk_limits as rl

passed = failed = 0
def check(name, cond):
    global passed, failed
    if cond: passed += 1; print(f"PASS: {name}")
    else: failed += 1; print(f"FAIL: {name}")

L = rl.resolve_user_limits(None)
check("default limits match the advertised promise (5/10/10)",
      L['daily'] == 5.0 and L['weekly'] == 10.0 and L['drawdown'] == 10.0)

# --- user overrides: stricter only ---
check("user may tighten daily to 2%", rl.resolve_user_limits({'max_daily_loss_percent': 2})['daily'] == 2.0)
check("user may NOT loosen daily to 40%", rl.resolve_user_limits({'max_daily_loss_percent': 40})['daily'] == 5.0)
check("garbage override ignored", rl.resolve_user_limits({'max_daily_loss_percent': 'abc'})['daily'] == 5.0)
check("zero/negative override ignored", rl.resolve_user_limits({'max_daily_loss_percent': 0})['daily'] == 5.0)

# --- daily limit ---
v = rl.evaluate_risk_limits(9500, 10000, None, None, L)   # -5.0%
check("daily loss exactly at 5% breaches", v.breached and v.reason == 'daily_loss_limit')
v = rl.evaluate_risk_limits(9600, 10000, None, None, L)   # -4.0%
check("daily loss 4% does not breach", not v.breached)
check("worst_usage reported for warnings (~0.8)", abs(v.worst_usage - 0.8) < 0.01)

# --- weekly limit (did not exist before this module) ---
v = rl.evaluate_risk_limits(9000, 9200, 10000, None, L)   # daily -2.2%, weekly -10%
check("weekly loss 10% breaches even when daily is fine", v.breached and v.reason == 'weekly_loss_limit')
v = rl.evaluate_risk_limits(9500, 9600, 10000, None, L)   # weekly -5%
check("weekly loss 5% does not breach", not v.breached)
v = rl.evaluate_risk_limits(9000, 9200, None, None, L)
check("no weekly baseline -> weekly check skipped, not crashed", not v.breached)

# --- drawdown from high-water mark ---
v = rl.evaluate_risk_limits(9000, 9100, 9100, 10000, L)   # dd -10% from peak
check("drawdown 10% from peak breaches", v.breached and v.reason == 'max_drawdown')
v = rl.evaluate_risk_limits(9500, 9600, 9600, 10000, L)   # dd -5%
check("drawdown 5% from peak does not breach", not v.breached)

# --- precedence: daily is evaluated first ---
v = rl.evaluate_risk_limits(8000, 10000, 10000, 10000, L)  # all three breached
check("daily reported first when several breach", v.breached and v.reason == 'daily_loss_limit')

# --- no dynamic widening under stress ---
v = rl.evaluate_risk_limits(9490, 10000, None, None, L)
check("limit is a hard ceiling (no open-risk buffer widens it)", v.breached)

# --- degenerate inputs self-heal instead of ZeroDivisionError ---
for bad in (0, None, -1):
    v = rl.evaluate_risk_limits(9000, bad, None, None, L)
    check(f"daily_start_equity={bad!r} self-heals, no crash", not v.breached)

# --- profit is never a breach ---
v = rl.evaluate_risk_limits(12000, 10000, 10000, 10000, L)
check("account in profit never breaches", not v.breached)

# --- weekly baseline persistence is restart-safe ---
with tempfile.TemporaryDirectory() as d:
    b1, wk = rl.load_or_init_weekly_baseline(d, 10000.0)
    check("first call baselines at current equity", b1 == 10000.0)
    b2, _ = rl.load_or_init_weekly_baseline(d, 8000.0)   # simulate mid-week restart after losses
    check("restart mid-week REUSES baseline (no free 10% reset)", b2 == 10000.0)
    b3, _ = rl.load_or_init_weekly_baseline(d, 8000.0, week_key="2099-W01")
    check("genuine new week starts a fresh baseline", b3 == 8000.0)

check("iso_week_key shape", rl.iso_week_key().count("-W") == 1)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
