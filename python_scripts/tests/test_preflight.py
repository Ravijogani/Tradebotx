import pathlib as _pl
_SCRIPTS = _pl.Path(__file__).resolve().parent.parent  # python_scripts/
import sys, tempfile, pathlib
sys.path.insert(0, str(_SCRIPTS))
from bot_manager_core import (resolve_bot_script, verify_bot_dependencies,
                              MissingBotDependency, InvalidScriptPath,
                              REQUIRED_BOT_MODULES, ALLOWED_BOT_SCRIPTS)

passed = failed = 0
def check(name, fn):
    global passed, failed
    try:
        fn(); passed += 1; print(f"  PASS  {name}")
    except AssertionError as e:
        failed += 1; print(f"  FAIL  {name}: {e}")
    except Exception as e:
        failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")

def mkdir(modules, scripts):
    d = pathlib.Path(tempfile.mkdtemp())
    for m in modules: (d / m).write_text("# stub\n")
    for s in scripts: (d / s).write_text("# stub\n")
    return d

print(f"ALLOWED_BOT_SCRIPTS = {sorted(ALLOWED_BOT_SCRIPTS)}")
print(f"REQUIRED_BOT_MODULES = {list(REQUIRED_BOT_MODULES)}\n")

# 1. Reproduce the EXACT Lightsail state: bot present, shared modules absent.
def t1():
    d = mkdir([], ['hybrid_trading_bot_multiuser.py'])
    try:
        resolve_bot_script(d, 'hybrid_trading_bot_multiuser.py')
        raise AssertionError("should have raised")
    except MissingBotDependency as e:
        for m in REQUIRED_BOT_MODULES:
            assert m in str(e), f"{m} not named in error"
        assert 'Copy them' in str(e)
check("VPS state -> MissingBotDependency naming all 4 files", t1)

# 2. Partial: only risk_limits.py missing (the actual traceback in the photo).
def t2():
    mods = [m for m in REQUIRED_BOT_MODULES if m != 'risk_limits.py']
    d = mkdir(mods, ['hybrid_trading_bot_multiuser.py'])
    try:
        resolve_bot_script(d, 'hybrid_trading_bot_multiuser.py')
        raise AssertionError("should have raised")
    except MissingBotDependency as e:
        assert 'risk_limits.py' in str(e)
        assert 'bot_control.py' not in str(e), "named a file that IS present"
check("only risk_limits.py missing -> names just that one", t2)

# 3. Fully provisioned dir -> resolves normally.
def t3():
    d = mkdir(REQUIRED_BOT_MODULES, ['hybrid_trading_bot_multiuser.py'])
    p = resolve_bot_script(d, 'hybrid_trading_bot_multiuser.py')
    assert p.name == 'hybrid_trading_bot_multiuser.py'
check("complete dir -> resolves", t3)

# 4. All three modern bots are gated.
def t4():
    for s in ('hybrid_trading_bot_multiuser.py', 'intraday.py', 'structural_swing_pro.py'):
        if s not in ALLOWED_BOT_SCRIPTS:
            continue
        d = mkdir([], [s])
        try:
            resolve_bot_script(d, s)
            raise AssertionError(f"{s} not gated")
        except MissingBotDependency:
            pass
check("all modern bots gated", t4)

# 5. Legacy bot is EXEMPT (predates the modules, doesn't import them).
def t5():
    d = mkdir([], ['hybrid_trading_bot.py'])
    p = resolve_bot_script(d, 'hybrid_trading_bot.py')
    assert p.name == 'hybrid_trading_bot.py'
check("legacy hybrid_trading_bot.py exempt", t5)

# 6-8. Security checks must still fire, and must fire BEFORE the dep check
#      (a hostile path in an unprovisioned dir must be rejected as hostile).
def t6():
    d = mkdir([], [])
    for bad in ('../evil.py', '/etc/passwd', 'not_allowed.py', 'hybrid_trading_bot_multiuser.py.bak'):
        try:
            resolve_bot_script(d, bad)
            raise AssertionError(f"{bad!r} was accepted")
        except InvalidScriptPath:
            pass
        except MissingBotDependency:
            raise AssertionError(f"{bad!r} reported as missing-dep, not rejected as invalid")
check("hostile paths still rejected as InvalidScriptPath", t6)

# 9. A directory (not a file) named risk_limits.py must not satisfy the check.
def t9():
    d = mkdir([m for m in REQUIRED_BOT_MODULES if m != 'risk_limits.py'],
              ['hybrid_trading_bot_multiuser.py'])
    (d / 'risk_limits.py').mkdir()
    try:
        resolve_bot_script(d, 'hybrid_trading_bot_multiuser.py')
        raise AssertionError("a DIRECTORY satisfied the check")
    except MissingBotDependency:
        pass
check("directory named risk_limits.py does not satisfy check", t9)

# 10. verify_bot_dependencies is idempotent / no side effects on disk.
def t10():
    d = mkdir(REQUIRED_BOT_MODULES, ['intraday.py'])
    before = sorted(p.name for p in d.iterdir())
    verify_bot_dependencies(d, 'intraday.py')
    verify_bot_dependencies(d, 'intraday.py')
    assert sorted(p.name for p in d.iterdir()) == before
check("no disk side effects", t10)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
