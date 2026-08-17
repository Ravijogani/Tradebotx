"""
Standalone verification of the two intraday.py fixes (findings #2 and #3
from the whole-project audit), run outside the harness since intraday.py
is a script, not a library, and needs MT5/Supabase/genai stubbed the same
way backtest/bot_loader.py does for hybrid_trading_bot_multiuser.py.

Lives in python_scripts/tests/ and runs in CI.
"""
import importlib.util
import os
import sys
import types
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent  # python_scripts/
sys.path.insert(0, str(SCRIPTS_DIR))

# 1. Stub MetaTrader5 (reuse the backtest harness's stub)
from backtest import mt5_stub
sys.modules["MetaTrader5"] = mt5_stub

# 2. Stub supabase (reuse the backtest harness's stub)
from backtest import supabase_stub
sys.modules["supabase"] = supabase_stub

# 3. Stub google.generativeai (real one panics in this sandbox -- same
#    issue bot_loader.py's _ensure_genai_importable works around)
fake_genai = types.ModuleType("google.generativeai")
fake_genai.configure = lambda **kwargs: None
fake_genai.GenerativeModel = lambda *a, **k: None
sys.modules["google"] = types.ModuleType("google")
sys.modules["google"].generativeai = fake_genai
sys.modules["google.generativeai"] = fake_genai

# 4. argv/env intraday.py's module-level argparse + fail-fast checks need
sys.argv = [
    str(SCRIPTS_DIR / "intraday.py"),
    "--user-id", "test-user",
    "--strategy-id", "test-strategy",
    "--mt5-login", "12345",
    "--mt5-server", "test-server",
    "--supabase-url", "http://test.invalid",
]
os.environ.setdefault("MT5_PASSWORD", "test-unused")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-unused")

spec = importlib.util.spec_from_file_location("intraday", SCRIPTS_DIR / "intraday.py")
intraday = importlib.util.module_from_spec(spec)
sys.modules["intraday"] = intraday
spec.loader.exec_module(intraday)

print("=== Module imported OK ===\n")

# ---------------------------------------------------------------------
# TEST A: _project_lot_and_risk / validate_trade_risk (Fix #3)
# ---------------------------------------------------------------------
print("--- TEST A: _project_lot_and_risk ---")

# A1: normal case, well above min_lot -- actual_risk should equal intended
spec_normal = intraday.get_symbol_specs("EURUSDm")
proj = intraday._project_lot_and_risk(
    "EURUSDm", entry_price=1.10000, stop_loss=1.09900,  # 10 pip SL
    risk_percent=1.0, account_equity=100_000.0,
)
print(f"A1 normal EURUSDm: lot={proj['lot_size']}, intended%={proj['intended_risk_percent']:.3f}, "
      f"actual%={proj['actual_risk_percent']:.3f}")
assert abs(proj['actual_risk_percent'] - proj['intended_risk_percent']) < 0.05, \
    "A1 FAILED: normal-case actual risk should track intended risk closely"

# A2: tiny account + wide stop on a high-tick-value symbol -> forces the
# min-lot floor -- this is exactly the scenario the old code silently
# proceeded on. actual_risk_percent must now come out clearly LARGER than
# intended (proving it's derived from the real floored lot, not an
# identity restatement of the input).
spec_xau = intraday.get_symbol_specs("XAUUSDm")
proj2 = intraday._project_lot_and_risk(
    "XAUUSDm", entry_price=2400.0, stop_loss=2350.0,  # 50-dollar-wide SL
    risk_percent=0.1, account_equity=200.0,  # tiny account, tiny intended risk
)
print(f"A2 min-lot-floor XAUUSDm: lot_raw={proj2['lot_raw']:.5f}, lot_size={proj2['lot_size']}, "
      f"intended%={proj2['intended_risk_percent']:.3f}, actual%={proj2['actual_risk_percent']:.2f}")
assert proj2['lot_raw'] < spec_xau['min_lot'], "A2 setup invalid: expected lot_raw below min_lot"
assert proj2['actual_risk_percent'] > proj2['intended_risk_percent'] * 2, \
    "A2 FAILED: actual risk should blow well past intended once floored to min_lot"
print("A2 confirms: real floored risk is now visibly different from intended risk (old code could never see this)\n")

# ---------------------------------------------------------------------
# TEST B: validate_trade_risk end-to-end -- must REJECT when the real
# min-lot-floored risk exceeds MAX_RISK_PER_TRADE_PERCENT (the old code
# would have let this through, since actual_risk_percent == risk_percent
# algebraically and risk_percent itself is always <= the cap by
# construction elsewhere).
# ---------------------------------------------------------------------
print("--- TEST B: validate_trade_risk rejects real min-lot overshoot ---")

from types import SimpleNamespace

def fake_tick(symbol):
    return SimpleNamespace(ask=2400.0, bid=2399.5)

intraday.mt5.symbol_info_tick = fake_tick

intraday.state.current_risk_percent = 0.1  # tiny intended risk
intraday.state.daily_start_equity = 200.0
intraday.state.daily_pnl = 0.0
intraday.config.MAX_RISK_PER_TRADE_PERCENT = 2.0  # 2% cap

signal = {'symbol': 'XAUUSDm', 'direction': 'BUY', 'stop_loss': 2350.0, 'confidence': 0.8}
is_valid, reason = intraday.validate_trade_risk(signal, account_equity=200.0)
print(f"B1 (min-lot overshoot, over cap): is_valid={is_valid}, reason={reason!r}")
assert is_valid is False, "B1 FAILED: should have been rejected -- real risk (~250%) far exceeds the 2% cap"
assert "exceeds per-trade limit" in reason, f"B1 FAILED: unexpected rejection reason: {reason}"
print("B1 confirms: the old tautological check could NEVER have rejected this -- now it does.\n")

# B2: normal, well-sized trade (same shape as A1) run through the FULL
# validate_trade_risk end-to-end -- proves the fix doesn't just reject
# everything, a real risk safely within every cap still passes.
intraday.config.MAX_RISK_PER_TRADE_PERCENT = 2.0
intraday.state.current_risk_percent = 1.0
intraday.mt5.symbol_info_tick = lambda s: SimpleNamespace(ask=1.10000, bid=1.09995)
signal_normal = {'symbol': 'EURUSDm', 'direction': 'BUY', 'stop_loss': 1.09900, 'confidence': 0.8}
is_valid2, reason2 = intraday.validate_trade_risk(signal_normal, account_equity=100_000.0)
print(f"B2 (normal well-sized trade): is_valid={is_valid2}, reason={reason2!r}")
assert is_valid2 is True, f"B2 FAILED: expected acceptance for a normal trade well within caps, got: {reason2}"
print("B2 confirms: fix doesn't just reject everything -- a real risk within the cap still passes.\n")

# B3: risk_multiplier parity -- validate_trade_risk must use the same
# risk_percent place_intraday_trade will actually size with.
intraday.config.MAX_RISK_PER_TRADE_PERCENT = 2.0
intraday.state.current_risk_percent = 1.0
signal_boosted = {'symbol': 'EURUSDm', 'direction': 'BUY', 'stop_loss': 1.09000,
                   'confidence': 0.8, 'risk_multiplier': 5.0}  # 1.0% * 5 = 5% > 2% cap
intraday.mt5.symbol_info_tick = lambda s: SimpleNamespace(ask=1.10000, bid=1.09995)
is_valid3, reason3 = intraday.validate_trade_risk(signal_boosted, account_equity=100_000.0)
print(f"B3 (risk_multiplier=5x pushes over cap): is_valid={is_valid3}, reason={reason3!r}")
assert is_valid3 is False, "B3 FAILED: risk_multiplier should be honored and this should breach the cap"
print("B3 confirms: risk_multiplier is now applied consistently (old code ignored it here entirely).\n")

# ---------------------------------------------------------------------
# TEST C: check_emergency_conditions (Fix #2)
# ---------------------------------------------------------------------
print("--- TEST C: check_emergency_conditions self-heals instead of crashing ---")

fake_account = SimpleNamespace(equity=9500.0, balance=9500.0)

# C1: daily_start_equity == 0.0 (the exact startup-hiccup scenario) --
# must NOT raise ZeroDivisionError, must self-heal, must return False.
intraday.state.daily_start_equity = 0.0
intraday.state.daily_pnl = 0.0
try:
    result = intraday.check_emergency_conditions(fake_account)
except ZeroDivisionError as e:
    raise AssertionError(f"C1 FAILED: ZeroDivisionError still raised: {e}")
except UnboundLocalError as e:
    raise AssertionError(f"C1 FAILED: UnboundLocalError still raised: {e}")
print(f"C1 (daily_start_equity=0.0): returned {result}, self-healed to {intraday.state.daily_start_equity}")
assert result is False, "C1 FAILED: should return False on the self-heal call, not trigger emergency stop"
assert intraday.state.daily_start_equity == 9500.0, "C1 FAILED: baseline should have self-healed to current equity"

# C2: next call, now with a real baseline -- normal operation, no loss,
# should return False cleanly (no exception, no false trigger).
intraday.config.MAX_DAILY_LOSS_PERCENT = 8.0
intraday.config.MAX_DRAWDOWN_PERCENT = 15.0
intraday.config.ENABLE_DYNAMIC_EMERGENCY_STOPS = False
result2 = intraday.check_emergency_conditions(fake_account)
print(f"C2 (normal, no loss): returned {result2}")
assert result2 is False, "C2 FAILED: no loss yet, should not trigger"

# C3: a real, large loss from the (now-healed) baseline should still
# correctly trigger the emergency stop -- proves the fix didn't neuter the
# actual safety check.
big_loss_account = SimpleNamespace(equity=9500.0 * 0.80, balance=9500.0 * 0.80)  # -20%
result3 = intraday.check_emergency_conditions(big_loss_account)
print(f"C3 (20% equity drop, limit 8%): returned {result3}")
assert result3 is True, "C3 FAILED: a real >MAX_DAILY_LOSS_PERCENT drop must still trigger the emergency stop"
print("C3 confirms: the fix self-heals the zero-baseline case WITHOUT disabling real emergency detection.\n")

# C4: negative daily_start_equity (defensive -- shouldn't happen, but the
# guard is `<= 0` specifically to cover it) -- must also self-heal cleanly.
intraday.state.daily_start_equity = -50.0
result4 = intraday.check_emergency_conditions(fake_account)
print(f"C4 (daily_start_equity=-50.0): returned {result4}, self-healed to {intraday.state.daily_start_equity}")
assert result4 is False
assert intraday.state.daily_start_equity == fake_account.equity

print("\n=== ALL TESTS PASSED ===")
