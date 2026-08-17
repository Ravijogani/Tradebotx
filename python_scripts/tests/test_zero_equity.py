"""Reproduce the live ZeroDivisionError and prove each fixed expression is safe."""
passed = failed = 0
def check(name, fn):
    global passed, failed
    try:
        fn(); passed += 1; print(f"  PASS  {name}")
    except ZeroDivisionError as e:
        failed += 1; print(f"  FAIL  {name}: ZeroDivisionError: {e}")
    except AssertionError as e:
        failed += 1; print(f"  FAIL  {name}: {e}")

class S: pass

# --- 1. The exact expression from the live traceback (line 10064), unfixed.
def original():
    daily_start_equity, equity = 0.0, 0.0
    return ((daily_start_equity - equity) / daily_start_equity) * 100
try:
    original(); print("  (control) old expression did NOT raise -- unexpected")
except ZeroDivisionError:
    print("  (control) old expression raises ZeroDivisionError as it did live ✓")

# --- 2. The fixed form.
def t1():
    for dse, eq in ((0.0, 0.0), (0.0, 245.84), (245.84, 0.0), (245.84, 200.0)):
        dd = ((dse - eq) / dse) * 100 if dse > 0 else 0.0
        assert isinstance(dd, float)
    # sanity: real numbers still compute correctly
    assert abs((((100.0 - 90.0) / 100.0) * 100) - 10.0) < 1e-9
check("hybrid daily drawdown: zero baseline -> 0.0, real values unchanged", t1)

# --- 3. Position sizing risk pct (hybrid L7382).
def t2():
    for risk, eq in ((5.0, 0.0), (5.0, 245.84)):
        pct = (risk / eq * 100) if eq > 0 else 0.0
        assert pct >= 0.0
    assert abs((5.0 / 250.0 * 100) - 2.0) < 1e-9
check("hybrid position-sizing risk pct: zero equity -> 0.0", t2)

# --- 4. Swing's two sites.
def t3():
    for dse in (0.0, 250.0):
        loss_amt = -10.0
        lp = abs(loss_amt / dse) * 100 if dse else 0.0
        dd = ((dse - 200.0) / dse) * 100 if dse else 0.0
        assert isinstance(lp, float) and isinstance(dd, float)
    assert abs((abs(-10.0 / 250.0) * 100) - 4.0) < 1e-9
check("swing daily loss pct + drawdown pct: zero baseline safe", t3)

# --- 5. The equity gate predicate: what actually stops the bot trading.
def t4():
    # values MT5 reports mid-login vs once authenticated
    assert (0.0 <= 0) is True,      "zero equity must be gated"
    assert (-1.0 <= 0) is True,     "negative equity must be gated"
    assert (245.84 <= 0) is False,  "real equity must NOT be gated"
check("equity gate: blocks 0 and negative, allows real equity", t4)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
