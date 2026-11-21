"""Regression coverage for shared sizing and daily-equity safety helpers."""
import pathlib
import sys
import tempfile
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import risk_limits as rl

MAIN_SOURCE = (ROOT / "hybrid_trading_bot_multiuser.py").read_text(encoding="utf-8")


passed = failed = 0


def check(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"PASS: {name}")
    except Exception as exc:
        failed += 1
        print(f"FAIL: {name}: {type(exc).__name__}: {exc}")


def test_volume_floor_never_rounds_up():
    assert rl.floor_volume_to_step(0.019, 0.01, 0.01, 100.0) == 0.01
    assert rl.floor_volume_to_step(0.029, 0.01, 0.01, 100.0) == 0.02
    assert rl.floor_volume_to_step(0.02, 0.01, 0.01, 100.0) == 0.02


def test_volume_rejects_below_minimum():
    assert rl.floor_volume_to_step(0.009, 0.01, 0.01, 100.0) == 0.0
    assert rl.floor_volume_to_step(0.0, 0.01, 0.01, 100.0) == 0.0


def test_volume_rejects_invalid_specs():
    assert rl.floor_volume_to_step(1.0, 0.0, 0.01, 100.0) == 0.0
    assert rl.floor_volume_to_step(float("nan"), 0.01, 0.01, 100.0) == 0.0
    assert rl.floor_volume_to_step(1.0, 0.01, 0.02, 0.01) == 0.0


def test_volume_caps_at_broker_max():
    assert rl.floor_volume_to_step(200.0, 0.1, 0.1, 5.0) == 5.0


def test_daily_baseline_survives_restart():
    with tempfile.TemporaryDirectory() as directory:
        first = rl.load_or_init_daily_baseline(directory, 10000.0, "2026-11-21")
        restarted = rl.load_or_init_daily_baseline(directory, 9300.0, "2026-11-21")
        assert first == 10000.0
        assert restarted == 10000.0


def test_daily_baseline_rolls_on_full_utc_date():
    with tempfile.TemporaryDirectory() as directory:
        rl.load_or_init_daily_baseline(directory, 10000.0, "2026-11-21")
        next_month = rl.load_or_init_daily_baseline(directory, 9700.0, "2026-12-21")
        assert next_month == 9700.0


def test_daily_baseline_uses_atomic_legacy_compatible_schema():
    with tempfile.TemporaryDirectory() as directory:
        rl.load_or_init_daily_baseline(directory, 10000.0, "2026-11-21")
        import json
        path = pathlib.Path(directory) / "daily_equity_baseline.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload == {"date": "2026-11-21", "baseline": 10000.0}
        assert not pathlib.Path(str(path) + ".tmp").exists()





def test_corrupt_daily_baseline_is_not_reset_from_current_equity():
    with tempfile.TemporaryDirectory() as directory:
        path = pathlib.Path(directory) / "daily_equity_baseline.json"
        path.write_text("{corrupt", encoding="utf-8")
        assert rl.load_or_init_daily_baseline(directory, 9300.0, "2026-11-21") == 0.0


def test_daily_baseline_fails_closed_when_storage_unavailable():
    with tempfile.TemporaryDirectory() as directory:
        blocker = pathlib.Path(directory) / "not_a_directory"
        blocker.write_text("file", encoding="utf-8")
        baseline = rl.load_or_init_daily_baseline(str(blocker), 10000.0, "2026-11-21")
        assert baseline == 0.0


def test_all_bot_tiers_use_persistent_full_date_baseline():
    for name in ("intraday.py", "structural_swing_pro.py"):
        source = (ROOT / name).read_text(encoding="utf-8")
        assert "risk_limits.utc_day_key()" in source
        assert "risk_limits.load_or_init_daily_baseline(" in source
        assert "datetime.now(timezone.utc).day" not in source
    assert "risk_limits.load_or_init_daily_baseline(data_dir, current_equity, today)" in MAIN_SOURCE


def test_main_execution_volume_guard_fails_closed():
    start = MAIN_SOURCE.index("def validate_lot_size(")
    end = MAIN_SOURCE.index("\ndef is_spread_safe(", start)
    helper = MAIN_SOURCE[start:end]
    assert "floor_volume_to_step" in helper
    assert "return min_lot" not in helper
    assert "return 0.0" in helper
    callsite = MAIN_SOURCE.index("lot_size = validate_lot_size(symbol, lot_raw)")
    assert "if lot_size <= 0:" in MAIN_SOURCE[callsite:callsite + 500]



def test_main_execution_rejects_invalid_equity_and_risk_override():
    start = MAIN_SOURCE.index("def place_ai_trade(")
    end = MAIN_SOURCE.index("\ndef ", start + 5)
    body = MAIN_SOURCE[start:end]
    assert "not math.isfinite(account_equity)" in body
    assert "account_equity <= 0" in body
    assert "final_risk_percent > risk_limits.PLATFORM_MAX_RISK_PER_TRADE_PERCENT" in body


def test_main_final_hard_cap_uses_shared_constant():
    assert "hard_cap_pct = risk_limits.PLATFORM_MAX_RISK_PER_TRADE_PERCENT" in MAIN_SOURCE


def test_per_trade_limit_is_shared_and_stricter_only():
    assert rl.resolve_user_limits(None)["per_trade"] == 1.5
    assert rl.resolve_user_limits({"max_risk_per_trade_percent": 0.5})["per_trade"] == 0.5
    assert rl.resolve_user_limits({"max_risk_per_trade_percent": 9.0})["per_trade"] == 1.5


check("volume is floored to broker step, never rounded up", test_volume_floor_never_rounds_up)
check("below-minimum volume is rejected rather than forced up", test_volume_rejects_below_minimum)
check("invalid broker volume specifications fail closed", test_volume_rejects_invalid_specs)
check("volume respects broker maximum", test_volume_caps_at_broker_max)
check("daily baseline survives same-day process restart", test_daily_baseline_survives_restart)
check("daily baseline uses full date and rolls across month boundary", test_daily_baseline_rolls_on_full_utc_date)
check("daily baseline writes atomically with compatible schema", test_daily_baseline_uses_atomic_legacy_compatible_schema)
check("corrupt daily baseline is not reset from current equity", test_corrupt_daily_baseline_is_not_reset_from_current_equity)
check("daily baseline failure blocks rather than silently allowing trading", test_daily_baseline_fails_closed_when_storage_unavailable)
check("all bot tiers use persistent full-date daily baselines", test_all_bot_tiers_use_persistent_full_date_baseline)
check("primary bot volume validation fails closed below minimum or on margin errors", test_main_execution_volume_guard_fails_closed)
check("primary bot rejects invalid equity and risk overrides before sizing", test_main_execution_rejects_invalid_equity_and_risk_override)
check("primary bot final execution cap uses the shared per-trade constant", test_main_final_hard_cap_uses_shared_constant)
check("per-trade ceiling is shared and user overrides can only tighten", test_per_trade_limit_is_shared_and_stricter_only)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
