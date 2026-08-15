"""
Safely imports structural_swing_pro.py as a module for backtesting -- same
reasoning as bot_loader.py (which does this for hybrid_trading_bot_
multiuser.py), kept as a separate loader because structural_swing_pro.py is
a genuinely separate script/process in production, not a strategy living
inside the shared multiuser file. See structural_swing_pro.py's own module
docstring for why it's a dedicated file at all (tier-separation: the shared
bot files don't dispatch on strategy_id, so a new strategy folded into
either of them would silently run for every user of that file regardless
of which strategy they picked).

Unlike hybrid_trading_bot_multiuser.py, this module needs no genai stub --
structural_swing_pro.py has no AI dependency at all (deliberately: a
rule-based structural strategy doesn't need one), so there's one less thing
for this loader to work around.
"""

import os
import sys
import importlib.util
from pathlib import Path

_BOT_MODULE_NAME = "structural_swing_pro"
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


def import_swing_bot_module():
    """Returns the imported structural_swing_pro module, with mt5 stubbed
    and argv/env satisfied. Cached after the first call."""
    global _cached_module
    if _cached_module is not None:
        return _cached_module

    if not _BOT_PATH.exists():
        raise FileNotFoundError(f"Expected bot file at {_BOT_PATH}")

    _install_mt5_stub()
    _install_supabase_stub()

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
