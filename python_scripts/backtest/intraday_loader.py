"""
Safely imports intraday.py as a module for backtesting -- same reasoning
and mechanics as bot_loader.py (which does this for hybrid_trading_bot_
multiuser.py). A separate loader because intraday.py is a genuinely
separate script/process in production, not a strategy living inside the
shared multiuser file (see structural_swing_pro.py's module docstring for
the full "why a dedicated script per tier" reasoning -- intraday.py is the
original instance of that pattern, this repo just hadn't backtested it
until now).

Unlike swing_loader.py, this DOES need the genai stub -- intraday.py does
`import google.generativeai as genai` unconditionally at module scope
(GeminiAIProvider), even though the backtest never reaches it (no
GEMINI_API_KEY is set, so ai_provider.client stays None and every AI-gated
call -- ai_validate_intraday_trade's L3 score -- takes its own documented
"AI not initialized" pass-through path, same as live with no key
configured).
"""

import os
import sys
import importlib.util
from pathlib import Path

_BOT_MODULE_NAME = "intraday"
_BACKTEST_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _BACKTEST_DIR.parent
_BOT_PATH = _SCRIPTS_DIR / f"{_BOT_MODULE_NAME}.py"

_cached_module = None


def _install_mt5_stub():
    from . import mt5_stub
    sys.modules["MetaTrader5"] = mt5_stub


def _install_supabase_stub():
    from . import supabase_stub
    sys.modules["supabase"] = supabase_stub


def _ensure_genai_importable():
    """Same reasoning/mechanics as bot_loader.py's identical helper: on a
    real deployment machine the real google-generativeai package is
    already installed and working; this only matters in constrained
    sandboxes where the real import can fail (sometimes as a Rust panic
    surfaced through pyo3, which only `except BaseException` catches)."""
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
    # Leave GEMINI_API_KEY unset -- ai_validate_intraday_trade's honest
    # "AI not initialized" pass-through is exactly the deterministic path
    # this harness wants exercised (see EMA_SCALP_CROSS's / SWAPPY_3C's
    # equivalent AI-optional handling in the other bot file's harness).


def import_intraday_module():
    """Returns the imported intraday module, with mt5/supabase/genai
    stubbed and argv/env satisfied. Cached after the first call."""
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
