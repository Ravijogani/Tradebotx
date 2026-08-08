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

**As of the decision to run the live cascade on only four setups**
(Shaakuni SSM, Swappy 3C, AOX, and the 9/25/50/200 EMA scalp), everything
below except those four is gated off by default via
`config.ENABLE_STRATEGY_*` flags in `AITradingConfig` — the code paths
still exist (flip a flag to re-enable), but they don't fire in the
current configuration.

| Strategy | Reachable via a call site | Enabled by default today | Notes |
|---|---|---|---|
| `SHAAKUNI_SSM` | Yes | **Yes** | Places a LIMIT order, not a market order |
| `SWAPPY_3C` | Yes | **Yes** | Now matches the fixed live entry mechanics — stop entry + 3:1 RR, not a market fill (see below) |
| `EMA_SCALP_CROSS` | Yes | **Yes** | Now backtestable — extracted from the main loop into `strategy_ema_scalp_cross()`, with two behavior fixes made in the process (see below) |
| AOX (layered execution) | Yes | **Yes** | Not backtestable here — see "not wired" below |
| `ICT_KILLZONE` | Yes | No (`ENABLE_STRATEGY_ICT_KILLZONE_FALLBACK`) | Fallback strategy |
| `LIQUIDITY_GRAB` | Yes | No (`ENABLE_STRATEGY_LIQUIDITY_GRAB_FALLBACK`) | Fallback strategy |
| `SMC_FVG_OB_RETEST` | Yes | No (`ENABLE_STRATEGY_SMC_FVG_RETEST`) | "STRATEGY C" |
| `SMC_ENTRY_ENGINE` | **No** | No | Never instantiated anywhere — fully built, unused |
| `ADVANCED_SMC` | **No** | No | Defined, never called |
| `WYCKOFF_PATTERNS` | **No** | No | Defined, never called |
| `VOLUME_PROFILE` | **No** | No | Defined, never called |
| `SUPPORT_RESISTANCE` | **No** | No | Defined, never called |
| `VOLUME_IMBALANCE` | **No** | No | Defined, never called |
| `TREND_PULLBACK` | **No** | No | Defined, never called |
| `MEAN_REVERSION_BB` | **No** | No | Defined, never called |

### The Swappy 3C entry bug (fixed)

`detect_swappy_3c` always recommended a stop entry above/below the
3-candle high/low (`order_type: BUY_STOP`/`SELL_STOP`, trigger at
`stop_entry`) — a breakout-confirmation entry. The live caller (STRATEGY
B) ignored that and built a generic setup dict using candle 3's close as
a market-style entry instead. There was already a fully-built, correctly
implemented `place_swappy_pending_order()` (proper stop order, 3:1 RR per
the Swappy spec, 25-minute expiry) and `check_swappy_expirations()`
(cancels stale pending orders, tracks the 3rd-time re-entry rule) — both
100% dead code, never called anywhere. Fixed by wiring STRATEGY B to call
`place_swappy_pending_order()` directly (mirroring how AOX self-manages
its own execution) and calling `check_swappy_expirations()` once per
cycle. The `SWAPPY_3C` adapter here was updated to match: it now models a
stop entry with 3:1 RR instead of a market fill.

### EMA_SCALP_CROSS extraction (two behavior fixes found and made)

Previously ~90 lines fully inline in the main loop with no standalone
function to call. Extracted into `strategy_ema_scalp_cross()` so it could
be wired in here. This was meant to be a faithful "move, don't rewrite"
extraction, but tracing every external variable dependency surfaced two
real bugs, both fixed as part of the extraction (not silently — see the
function's own docstring):

1. **The pattern pre-filter never actually gated anything.** The inline
   code computed `detect_ema_pattern_prefilter()`, logged whether a
   qualifying double-top/bottom or H&S pattern was found, and — on
   "not found" — logged, bumped a counter, and then **fell straight
   through to the cross-detection logic anyway**, with no `continue` or
   gate. The comment even says "Don't continue -- let other strategies
   still check," which is true but irrelevant: nothing stopped *this*
   strategy from proceeding past its own failed filter. So the filter
   that exists specifically to stop "random crossovers in ranging
   markets" (its own comment) never once blocked a trade. Fixed: a failed
   pre-filter now returns `None`.
2. **`state._rej` double-counting.** The inline version incremented the
   rejection counter at up to 3 internal points *and* the cascade's
   single catch-all after everything fails — double-counting whenever
   every strategy failed the same cycle. Moved the bookkeeping to the
   caller, matching how every other cascade strategy already works.

One more live strategy exists but is **not wired here on purpose**:

- **"STRATEGY D" (`run_aox_layered_entry`)** manages its own multi-call
  phase state machine and returns `bool`, not a signal dict — it looks
  like it places real orders itself rather than just proposing a trade.
  It needs either a refactor to separate signal-generation from
  order-placement, or a different backtest approach entirely (capturing
  order *intent* instead of this engine's simulate-fills-against-
  subsequent-bars model). Not faked here.

### EMA scalp (9/25/50/200) -- what changed

Per the 9/15/50/200 EMA framework spec:

- **Enabled by default** (`ENABLE_STRATEGY_EMA_SCALP = True`). The existing
  implementation already matched the spec reasonably well before touching
  anything: a 9/25 EMA cross (the spec explicitly allows 25 as a
  documented variant of 15), a hard 200 EMA macro-trend gate, and the 50
  EMA used as the primary TP target (via `ema50_tp` -> `get_dynamic_trade_
  params`'s `ema50_tp_hint`, verified already correctly wired, not new).
- **Added: the "Distance Rule"** — the spec's no-trade-zone filter for when
  the 9/25 cluster and 50 EMA are bunched/braided (ranging market, cross
  is noise not momentum). Implemented as an ATR-relative gap requirement
  (`config.EMA_DISTANCE_RULE_ATR_MULT`, starting value 0.5x M5 ATR) rather
  than the spec's fixed "~15 pips", since a fixed pip count doesn't
  translate across Gold/BTC/forex — same reasoning already used elsewhere
  in this file (`strategy_advanced_smc`'s `min_ob_size`). Not empirically
  validated; tune via this harness now that EMA scalp is backtestable.
- **Extracted into `strategy_ema_scalp_cross()`** (see the section above)
  so it's now wired into this harness as `EMA_SCALP_CROSS` — found and
  fixed two real behavior bugs in the process, also covered above.

**Still deliberately NOT implemented:** the spec's core execution protocol
is a limit entry at the 50% retracement of the trigger candle, not a
market fill. The current code enters at the live market price via the
shared `place_ai_trade` pipeline — verified that `entry_price` in the
setup dict is informational only (the actual fill price comes from a
fresh bid/ask tick at execution time), so simply changing that value
would not have made this a real limit order. Implementing the retracement
entry correctly needs an actual order-type branch (`TRADE_ACTION_DEAL` vs
`TRADE_ACTION_PENDING`) inside the shared execution function used by every
other strategy's market orders too — a change to core, heavily-shared
execution code that this sandbox cannot verify end-to-end (no Windows, no
MT5 terminal, no way to confirm a real order got placed correctly).
Flagged as a follow-up rather than shipped blind. The spec's remaining
pieces — the "reverse close" invalidation rule, top-down Daily-candle
bias (needs a D1 data feed the live pipeline doesn't currently fetch),
and triple-layered position scaling (1:1.5R / 50 EMA / 25-EMA-trailed) —
are bigger, separate subsystems, not included here either.

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
