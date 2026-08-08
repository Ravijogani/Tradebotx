# Backtest harness

Walk-forward backtester that calls the **real, live** strategy code from
`hybrid_trading_bot_multiuser.py` against historical data — not a
reimplementation. That's the whole point: a backtest that tests different
code than what actually trades your money isn't testing anything real.

## Read this first: what's actually live

Grepping the whole bot file for call sites (not just `def`s) found that
most of the strategy-shaped code in this file is never actually reached by
the live trading loop. This corrects something the first version of this
harness got wrong — it was built around `EntryEngine.evaluate_setup()`
believing it to be "the deterministic SMC entry engine" (that's its own
docstring's description); `EntryEngine` is in fact never instantiated
anywhere in the file.

| Strategy | Live today? | Notes |
|---|---|---|
| `ICT_KILLZONE` | **Yes** | Fallback strategy in the live cascade |
| `LIQUIDITY_GRAB` | **Yes** | Fallback strategy in the live cascade |
| `SMC_FVG_OB_RETEST` | **Yes** | "STRATEGY C" — the SSM/FVG-retest engine |
| `SHAAKUNI_SSM` | **Yes** | Places a LIMIT order, not a market order |
| `SWAPPY_3C_PATTERN_ONLY` | **Partially** | Only the pattern-detection half of live "STRATEGY B" — see its adapter's docstring for what's excluded (a location filter + a stateful "3rd-time re-entry rule") |
| `SMC_ENTRY_ENGINE` | **No** | Never instantiated anywhere — fully built, unused |
| `ADVANCED_SMC` | **No** | Defined, never called |
| `WYCKOFF_PATTERNS` | **No** | Defined, never called |
| `VOLUME_PROFILE` | **No** | Defined, never called |
| `SUPPORT_RESISTANCE` | **No** | Defined, never called |
| `VOLUME_IMBALANCE` | **No** | Defined, never called |
| `TREND_PULLBACK` | **No** | Defined, never called |
| `MEAN_REVERSION_BB` | **No** | Defined, never called |

Two more live strategies exist but are **not wired here on purpose**:

- **"STRATEGY A" (EMA_SCALP_CROSS)** is ~90 lines fully inline in the main
  trading loop — no standalone function exists to call. Extracting it
  cleanly is a real refactor of live-critical code, not a quick adapter,
  and this sandbox can't run the live bot end-to-end to verify a refactor
  didn't change its behavior (no Windows, no MT5 terminal). Left as a
  deliberate follow-up to do carefully, with real testing access.
- **"STRATEGY D" (`run_aox_layered_entry`)** manages its own multi-call
  phase state machine and returns `bool`, not a signal dict — it looks
  like it places real orders itself rather than just proposing a trade.
  It needs either a refactor to separate signal-generation from
  order-placement, or a different backtest approach entirely (capturing
  order *intent* instead of this engine's simulate-fills-against-
  subsequent-bars model). Not faked here.

Every report the harness prints is labeled `[LIVE]` or `[NOT LIVE — not
reachable by the real trading loop today]` so this distinction is never
lost in the numbers. The dormant strategies are still wired up and
runnable — they're fully-built code worth evaluating on their own merits
before deciding whether any belong in the live cascade — but don't read
their backtest results as "how the bot is performing," because none of
them currently place a single real order.

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

`replay_data.py` additionally patches `get_market_data` (the function
every live helper — most importantly `get_market_regime_and_trend`, which
every wired strategy depends on for its `trend` input — uses to pull its
own data) to serve historical, no-lookahead windows instead of live MT5
calls. This means `get_market_regime_and_trend` runs completely unmodified
during a backtest and can never drift from what it computes live.
`time_travel.py` does the same for `datetime.now()`, so kill-zone/session
gates evaluate against the bar being replayed instead of the real clock.

The result: every adapter in `strategies_registry.py` calls the exact same
function/class objects the live bot runs, with zero chance of placing a
real order or touching production data, and zero duplicated logic to
drift out of sync.

## Getting historical data

Run `export_mt5_history.py` **on the machine with a live MT5 terminal**
(this is the one script here that talks to real MT5 — it's a data-export
tool, not part of the harness):

```
python export_mt5_history.py --symbol XAUUSDm --days 365 --out-dir ./history/XAUUSDm
```

Produces `XAUUSDm_M1.csv`, `_M5.csv`, `_M15.csv`, `_H1.csv`, `_H4.csv`.
M15 is only needed by `SMC_FVG_OB_RETEST`'s HTF confluence check; H4 is
only needed by `SHAAKUNI_SSM`. Everything else only needs M1/M5/H1.

## Running a backtest

From inside `python_scripts/`:

```
# One strategy:
python3 -m backtest.run_backtest \
    --symbol XAUUSDm --data-dir ./history/XAUUSDm \
    --m1 XAUUSDm_M1.csv --m5 XAUUSDm_M5.csv --h1 XAUUSDm_H1.csv \
    --strategy ICT_KILLZONE --out trades.csv

# Every registered strategy, one report each, one combined trade CSV:
python3 -m backtest.run_backtest \
    --symbol XAUUSDm --data-dir ./history/XAUUSDm \
    --m1 XAUUSDm_M1.csv --m5 XAUUSDm_M5.csv --h1 XAUUSDm_H1.csv \
    --m15 XAUUSDm_M15.csv --h4 XAUUSDm_H4.csv \
    --all --out trades.csv
```

Each report prints win rate, expectancy in R, profit factor, and max
drawdown; `SMC_ENTRY_ENGINE` additionally gets an EdgeEngine score-band
breakdown (it's the only adapter whose score components are genuinely
derived per-setup rather than fixed constants — see
`strategies_registry.py`'s docstring). The combined CSV records every
trade's full entry reasoning, so any losing trade is re-derivable from the
same historical data, not just summarized.

## Known limitations — read before trusting a result

- **Spread is a static per-symbol approximation**
  (`engine.py`'s `DEFAULT_SPREAD_MODEL`), not real recorded spread.
  `SMC_FVG_OB_RETEST` calls `mt5.symbol_info_tick()` for live spread and
  already has its own ATR-based fallback for when that's unavailable
  (which it always is here) — the harness doesn't override that,
  it just inherits the live file's own fallback behavior.
- **Take-profit defaults to a fixed R-multiple off the SL distance**
  (`--rr`, default 2.0) for every strategy except `SHAAKUNI_SSM` (which
  computes its own TP) — not the live bot's full exit logic (runner
  management, breakeven trailing, mid-trade `DecisionEngineV2`
  adjustments). This measures each strategy's entry logic under a
  standard, explicit exit framework; it doesn't yet reproduce the live
  bot's exact exit behavior.
- **One position at a time per strategy.** The engine doesn't evaluate
  new entries while a simulated trade from the same run is open, so it
  can't test correlated/stacked exposure across strategies running
  simultaneously (which the live bot does).
- **`SMC_ENTRY_ENGINE`'s `session_strength`/`volatility_state` are
  placeholder constants** (0.7) — the live cascade derives these
  elsewhere in the pipeline, not from `EntryEngine`'s own output (unsurprising,
  since `EntryEngine` isn't live).
- **Small sample sizes will look great or terrible by pure chance.**
  Several strategies produced 0 trades against 20 days of synthetic data
  in smoke testing — that's expected for strict multi-condition setups on
  a short window, not a harness bug. Don't trust a result from under a
  few hundred trades.

## Extending this

To wire in EMA_SCALP_CROSS or the AOX layered engine, the honest path is:
extract them into standalone, testable functions in the live bot file
first (separating AOX's signal-detection from its order-placement), with
real testing on the actual MT5/Windows environment to confirm the
extraction didn't change live behavior — then add an adapter here the same
way every other strategy in `strategies_registry.py` is wired. Don't
shortcut this by reimplementing their logic directly in the harness; that
reintroduces exactly the live/backtest drift risk this whole harness
exists to eliminate.
