# Backtest harness (v1)

Walk-forward backtester that calls the **real, live** strategy code from
`hybrid_trading_bot_multiuser.py` against historical data — not a
reimplementation. That's the whole point: a backtest that tests different
code than what actually trades your money isn't testing anything real.

## What v1 covers

`EntryEngine.evaluate_setup()` → `EdgeEngine.calculate()` — the file's own
docstring calls `EntryEngine` the "Deterministic SMC Entry Engine," and
it's fully self-contained (three DataFrames in, a signal dict out), which
made it the right first strategy to wire up. Wiring in the other 10+
`strategy_*` functions is the same pattern — see "Adding more strategies"
below.

## How it works, and why it's structured this way

`hybrid_trading_bot_multiuser.py` is a script, not a library — it parses
CLI args and connects to real Supabase at import time, and would try to
talk to a real MT5 terminal the moment it runs. `bot_loader.py` imports it
safely by:

- Installing a fake `MetaTrader5` module (`mt5_stub.py`) — the backtest
  can **never** reach a real terminal, by construction, not by config.
- Installing a fake `supabase` module (`supabase_stub.py`) — same
  reasoning, the backtest never touches production data.
- Providing placeholder CLI args so the script's `argparse` call succeeds.

The result: the harness runs the exact same `EntryEngine`, `EdgeEngine`,
`CapitalController`, etc. classes the live bot runs, with zero chance of
placing a real order or writing to production, and zero duplicated logic
to drift out of sync.

`time_travel.py` patches `datetime.now()` inside the imported bot module
during each replay step, so time-of-day-gated logic (kill zones, sessions)
evaluates against the historical bar being replayed instead of the actual
wall clock. This needed zero changes to the live file.

## Getting historical data

Run `export_mt5_history.py` **on the machine with a live MT5 terminal**
(this is the one script here that talks to real MT5 — it's a data-export
tool, not part of the harness):

```
python export_mt5_history.py --symbol XAUUSDm --days 365 --out-dir ./history/XAUUSDm
```

Produces `XAUUSDm_M1.csv`, `XAUUSDm_M5.csv`, `XAUUSDm_H1.csv`.

## Running a backtest

From inside `python_scripts/`:

```
python3 -m backtest.run_backtest \
    --symbol XAUUSDm \
    --data-dir ./history/XAUUSDm \
    --m1 XAUUSDm_M1.csv --m5 XAUUSDm_M5.csv --h1 XAUUSDm_H1.csv \
    --out trades.csv
```

This prints a report (win rate, expectancy in R, profit factor, max
drawdown, and — the number nothing in this codebase measured before — a
breakdown by `EdgeEngine` score band, so you can see whether its
hand-picked weights actually predict anything) and writes every simulated
trade to `trades.csv` with its full entry reasoning and score components.
That per-trade record is what answers "what went wrong": you can look at
any losing trade and see exactly which score inputs, setup type, and
session it fired under, deterministically re-derivable from the same
historical data.

## Known v1 limitations — read before trusting a result

- **Spread is a static per-symbol approximation** (`engine.py`'s
  `DEFAULT_SPREAD_MODEL`), not real recorded spread. Real spread widens
  around news and session opens; this can't capture that yet. Override
  with `--spread` for a single run, or extend `export_mt5_history.py` to
  pull real historical spread if your broker's history provides it.
- **Take-profit is a fixed R-multiple off the SL distance** (`--rr`,
  default 2.0), not the live bot's actual TP-selection logic (which is
  entangled with live tick/broker-compat code deep in the order-placement
  path). This means the harness measures the entry logic's edge under a
  standard, explicit exit framework — it does not yet reproduce the live
  bot's exact exit behavior (runner management, breakeven trailing, mid-
  trade DecisionEngineV2 adjustments). That's the natural next extension.
- **One position at a time.** The engine doesn't evaluate new entries
  while a simulated trade is open, so it can't test correlated/stacked
  exposure across simultaneous trades. Fine for testing one strategy's
  raw edge; not yet a portfolio-level simulation.
- **session_strength / volatility_state are placeholder constants** (0.7)
  in the `TradeContext` built for `EdgeEngine.calculate()` — the live bot
  derives these from other pipeline stages not yet wired into the harness.
  Extend this once you're validating trades where session/volatility
  meaningfully affect the score.
- **Small sample sizes will look great or terrible by pure chance.**
  Don't trust a result from under a few hundred trades — that's normal
  statistics, not a harness bug.

## Adding more strategies

Every `strategy_*` function in the bot file (e.g.
`strategy_mean_reversion_bb`, `strategy_support_resistance`,
`strategy_liquidity_fvg_engine`) takes DataFrames + a symbol/trend string
and returns a signal dict (varies slightly per function — check the
function's return statements). To back-test one:

1. Call it the same way `BacktestEngine._simulate_trade`'s caller calls
   `EntryEngine.evaluate_setup` — inside a `frozen_at(bot, as_of)` block,
   fed windows from `HistoricalDataset.window(...)`.
2. Map its return dict's `direction`/`stop_loss` (field names vary per
   function — check each one) onto `SimulatedTrade`'s constructor, same as
   `_simulate_trade` does today.
3. If the strategy doesn't participate in `EdgeEngine` scoring, you can
   skip the `TradeContext`/`EdgeEngine.calculate()` step and simulate the
   trade directly off its own `confidence` field instead.

This is genuinely mechanical, not a redesign — the harness's data loading,
no-lookahead windowing, spread-aware trade simulation, and reporting are
all strategy-agnostic already.
