# Unit tests

Run everything:

```bash
cd python_scripts && python tests/run_all.py
```

Each suite is a standalone script — run one directly to iterate:

```bash
cd python_scripts/tests && python test_bot_control.py
```

They need only `pandas` and `numpy`. MetaTrader5 and Supabase are stubbed
(see `backtest/bot_loader.py` and `backtest/mt5_stub.py`), so these run on
Linux CI where MT5 cannot be installed.

## What each suite protects

| Suite | Guards |
|---|---|
| `test_bot_control.py` | Emergency stop fires **instantly** on a running bot; fail-open on transport errors; a missing row is not a stop |
| `test_startup_race.py` | The startup grace that stops a booting bot reading its own pre-launch `is_running=false` as a Stop and killing itself |
| `test_zero_equity.py` | The bot refuses to trade on zero equity instead of crashing or sizing off nothing |
| `test_currency_exposure.py` | Netting, so 13 symbols can't become one leveraged bet; hedges still allowed; de-risking never blocked |
| `test_risk_limits.py` | Daily/weekly/drawdown ceilings; user limits can only tighten, never widen, the platform ones |
| `test_decision_journal.py` | Journal capture and JSON-safe serialisation (numpy types leak silently otherwise) |
| `test_preflight.py` | A bot won't launch with shared modules missing; path-traversal names still rejected |
| `test_market_intelligence.py`, `test_regime_router.py`, `test_choch.py`, `test_liquidity_levels.py`, `test_equilibrium_ote.py` | Pure strategy functions |
| `test_swing_pure_functions.py`, `test_intraday_fixes.py` | Per-bot decision logic |

## Why these live here

They were written alongside the fixes they cover but sat outside the repo,
so CI could not run them and nothing stopped a later edit from quietly
undoing a safety guarantee. That already happened once: changing
`check_remote_stop`'s contract left a stale expectation in
`test_bot_control.py` that no automated check caught.

A suite fails by exiting non-zero. If you add one, that is the only contract
`run_all.py` relies on.
