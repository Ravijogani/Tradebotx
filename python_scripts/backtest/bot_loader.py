"""
Safely imports hybrid_trading_bot_multiuser.py as a module for backtesting.

This is the piece that makes backtest/live parity real rather than aspirational:
the harness calls the EXACT SAME function and class objects (EdgeEngine,
EntryEngine, CapitalController, every strategy_* function, ...) that the
live bot runs. We are not reimplementing the strategy logic a second time --
a second implementation would drift from live behavior silently and the
backtest would stop meaning anything.

hybrid_trading_bot_multiuser.py is a *script*, not a library: it parses
argv and calls sys.exit(1) at module scope if required CLI args or secrets
are missing, connects a real Supabase client at module scope, and creates
log/backup directories as a side effect of being imported. To import it
safely for backtesting we:

  1. Install a fake `MetaTrader5` module (mt5_stub.py) into sys.modules
     BEFORE import, so the bot can never reach a real terminal.
  2. Install a fake `supabase` module (supabase_stub.py) for the same
     reason -- a backtest has no business touching the production DB.
  3. Set sys.argv to dummy-but-valid values so its argparse call succeeds.
  4. Set MT5_PASSWORD / SUPABASE_SERVICE_KEY env vars so its "fail fast if
     no secret" checks pass -- these are never used for anything real
     because MT5 and Supabase are never actually reached in a backtest run.
  5. Import it once (Python caches modules -- a second call returns the
     cached instance, matching normal import semantics).

The log/backup directories it creates as a side effect
(Hybrid_AI_Bot_Logs_backtest_backtest, Backup_Trades_backtest_backtest) are
harmless and get created under wherever you run the harness from -- feel
free to delete them.
"""

import os
import sys
import importlib.util
from pathlib import Path

_BOT_MODULE_NAME = "hybrid_trading_bot_multiuser"
_BACKTEST_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _BACKTEST_DIR.parent
_BOT_PATH = _SCRIPTS_DIR / f"{_BOT_MODULE_NAME}.py"

_cached_module = None


def _install_mt5_stub():
    """Always installs the fake MetaTrader5 -- backtesting must never be
    able to reach a real terminal, regardless of what's actually installed
    in the current environment."""
    from . import mt5_stub
    sys.modules["MetaTrader5"] = mt5_stub


def _install_supabase_stub():
    """Always installs the fake supabase client -- same reasoning as MT5:
    a backtest has no business writing trade records or reading/writing
    anything in the production database, regardless of what credentials
    happen to be on hand in the environment it's run in."""
    from . import supabase_stub
    sys.modules["supabase"] = supabase_stub


def _ensure_genai_importable():
    """
    hybrid_trading_bot_multiuser.py does `import google.generativeai as
    genai` unconditionally at module scope, even though the backtest
    harness deliberately never calls it (GEMINI_API_KEY is left unset, so
    AIProvider.setup_provider() never reaches genai.configure/
    GenerativeModel -- see ai_validate_trade's honest bias fallback).

    On a real deployment machine the real package is already installed and
    working (it's a live dependency), so this only matters in constrained
    environments (e.g. a broken native cffi/cryptography install) where the
    real import can fail -- sometimes as a Rust panic surfaced through
    pyo3, which only `except BaseException` actually catches, not a plain
    `except Exception`. If that happens we substitute a harmless stub
    module rather than let an unused dependency block backtesting.
    """
    if "google.generativeai" in sys.modules:
        return
    try:
        import google.generativeai  # noqa: F401
        return
    except BaseException:
        pass

    import types
    fake_genai = types.ModuleType("google.generativeai")
    fake_genai.configure = lambda **kwargs: None
    fake_genai.GenerativeModel = lambda *args, **kwargs: (_ for _ in ()).throw(
        RuntimeError("genai stub active (real google-generativeai unavailable) -- "
                      "backtest should never reach this since GEMINI_API_KEY is unset")
    )
    if "google" not in sys.modules:
        sys.modules["google"] = types.ModuleType("google")
    sys.modules["google.generativeai"] = fake_genai
    sys.modules["google"].generativeai = fake_genai


def _ensure_argv_and_env():
    """
    Provide the minimum the bot file's module-level argparse/env checks
    need to get past import without touching anything real. Values are
    deliberately obvious placeholders (never used for a real connection).
    """
    sys.argv = [
        str(_BOT_PATH),
        "--user-id", "backtest",
        "--strategy-id", "backtest",
        "--mt5-login", "0",
        "--mt5-server", "backtest-server",
        "--supabase-url", "http://backtest.invalid",
    ]
    os.environ.setdefault("MT5_PASSWORD", "backtest-unused")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "backtest-unused")
    # Leave GEMINI_API_KEY unset unless the caller wants AI validation
    # exercised in the backtest (see ai_validate_trade's honest bias
    # fallback -- with no key, gemini_model stays None and every trade
    # goes through the L1-bias fallback path deterministically).


def import_bot_module():
    """
    Returns the imported hybrid_trading_bot_multiuser module, with mt5
    stubbed out and argv/env satisfied. Cached after the first call.
    """
    global _cached_module
    if _cached_module is not None:
        return _cached_module

    if not _BOT_PATH.exists():
        raise FileNotFoundError(f"Expected bot file at {_BOT_PATH}")

    _install_mt5_stub()
    _install_supabase_stub()
    _ensure_genai_importable()

    saved_argv = sys.argv
    try:
        _ensure_argv_and_env()
        spec = importlib.util.spec_from_file_location(_BOT_MODULE_NAME, _BOT_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[_BOT_MODULE_NAME] = module
        spec.loader.exec_module(module)
    finally:
        sys.argv = saved_argv

    _cached_module = module
    return module
