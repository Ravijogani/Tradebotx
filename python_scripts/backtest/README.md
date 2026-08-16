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

**The live cascade trades exactly four setups, no more, no less**
(Shaakuni SSM, Swappy 3C, AOX, and the 9/25/50/200 EMA scalp). This was
first enforced via `config.ENABLE_STRATEGY_*` flags (flip one to
re-enable a fallback), then — once those flags had sat off through the
entire engagement and it was clear the fallbacks were never part of the
actual vision — the flagged-off code was removed outright. See "Fallback
and dormant strategies removed" below for what used to be here and why.

| Strategy | Reachable via a call site | Enabled by default today | Notes |
|---|---|---|---|
| `SHAAKUNI_SSM` | Yes | **Yes** | Places a LIMIT order, not a market order. Real-data result (XAUUSDm, 90d): 140 trades, +0.711R expectancy, PF 1.70 |
| `SWAPPY_3C` | Yes | **Yes** | Matches the fixed live entry mechanics — stop entry + 3:1 RR, not a market fill (see below). Real-data result: 18 trades, +0.219R expectancy — too small a sample to trust yet |
| `EMA_SCALP_CROSS` | Yes | **Yes** | Extracted from the main loop into `strategy_ema_scalp_cross()`, two behavior bugs found and fixed (see below). Real-data result: 75 trades, +0.051R expectancy — barely positive, weakest of the four |
| `AOX` (layered execution) | Yes | **Yes** | Backtestable via a dedicated stateful driver, not a `StrategyAdapter` — see "AOX wiring" below. **Not yet tested against real data** (needs M1) |
| `STRUCTURAL_SWING` | Yes | **Yes** | Lives in a **separate script** (`structural_swing_pro.py`), not this file — see "STRUCTURAL_SWING wiring" below for why. Real-data result (XAUUSDm, ~90d resampled D1): 3 trades, +1.65R expectancy, 66.7% win rate — a genuinely small sample (this strategy fires rarely by design), re-run once you have a longer native D1 export before trusting the numbers over the mechanics |

Separately, `intraday.py`'s own live cascade (`context_decision_engine`,
Strategies A/B/C/D/E) is now backtestable too — see "INTRADAY wiring"
below. It's a **different bot file entirely** (the Pro-tier "Intraday
Core" strategy), so it's not part of the table above, which is
specifically about `hybrid_trading_bot_multiuser.py`'s four setups.
Real-data result (XAUUSDm, ~90d): 11 trades, -0.003R expectancy, 36.4% win
rate, PF 1.00 — dead flat, not negative, not positive, on a sample too
small to call either way. Two real bugs were found and fixed getting to
that number — see "INTRADAY wiring" for what they were; both are live-code
fixes (context_decision_engine is the actual live function), not
backtest-only corrections.

### Fallback and dormant strategies removed (2026-08)

Two separate rounds of removal, both driven by the same principle: code
that isn't live shouldn't sit in the live file "just in case," because
that's exactly the shape of bug this whole engagement kept finding
(Swappy 3C's correct pending-order function sat dead for the same
reason — fully built, nobody calling it).

**Round 1 — 8 strategies with zero live call sites, ever:**
`EntryEngine`/`SMC_ENTRY_ENGINE`, `strategy_advanced_smc`,
`strategy_wyckoff_patterns`, `strategy_volume_profile`,
`strategy_support_resistance`, `strategy_volume_imbalance`,
`strategy_trend_pullback`, `strategy_mean_reversion_bb`. First
quarantined into a separate `strategies_research.py` module (kept
backtestable, out of the live file) so they could actually be evaluated
on real data before any keep/cut decision — then, once that data came
in, fully removed. Real-data results (XAUUSDm, 90 days) that drove the
removal:

| Strategy | Trades | Expectancy | Verdict |
|---|---|---|---|
| `VOLUME_PROFILE` | 290 | -0.120R | Losing, large sample |
| `SUPPORT_RESISTANCE` | 395 | -0.144R | Losing, large sample |
| `MEAN_REVERSION_BB` | 541 | -0.124R | Losing, large sample — also the philosophical outlier here (counter-trend fade vs. every other strategy being momentum/liquidity-based) |
| `TREND_PULLBACK` | 289 | -0.006R | Statistically flat, not worth pursuing |
| `VOLUME_IMBALANCE` | 0 | — | Essentially never fires |
| `WYCKOFF_PATTERNS` | untested | — | Needed M1 (not available at removal time); also isn't genuine Wyckoff method despite the name — no range/cause-and-effect schematic, no spring/upthrust/test/SOS/LPS, just a volume-climax reversal filter |
| `ADVANCED_SMC` | untested | — | Needed M1 (not available at removal time) |
| `SMC_ENTRY_ENGINE` (`EntryEngine`) | untested | — | Needed M1. Was the strongest candidate by code quality (real sweep + market-structure-shift + FVG confluence, not a single-indicator trigger) but was never actually validated against real data before this removal — removed to stop carrying 8 strategies' worth of unreachable code, not because real evidence said no |

**Round 2 — 3 strategies that WERE real, flag-gated live call sites**
(`strategy_ict_killzone`, `strategy_liquidity_grab`, and
`strategy_liquidity_fvg_engine` / "STRATEGY C" / `SMC_FVG_OB_RETEST`),
plus a genuinely dead `get_strategies_for_regime()` helper found while
removing them (zero call sites, and it already referenced two strategies
from Round 1 that no longer existed — a stale reference that had slipped
through Round 1's own cleanup). All three flag-gated strategies had sat
disabled (`config.ENABLE_STRATEGY_*_FALLBACK = False`) for the entire
engagement and were never part of the actual four-setup vision (Shaakuni
SSM / Swappy 3C / AOX / EMA scalp) — `SMC_FVG_OB_RETEST` also produced 0
trades in the real-data backtest while it was still wired here.
Removing these was more involved than Round 1: unlike the 8 dormant
strategies, these three had real downstream references scattered through
the live cascade's confluence/scoring logic (3C-confirmation exemptions,
L3 AI score thresholds, counter-trend structural-confluence checks) --
each reference was individually traced and either removed or narrowed to
the strategies that still exist, not just deleted wholesale.

If any of these needs to be revisited, they're recoverable from git
history — search this repo's log for `strategies_research.py`,
"Quarantine dormant strategies", "remove the 8 dormant strategies", or
"remove all 8 base strategies" to find the commits that added, then
removed, them. Recover and re-verify against real data; don't rewrite
from scratch.

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
  documented variant of 15) and a hard 200 EMA macro-trend gate.
- **CORRECTION (2026-08, found from the first real-data backtest run):**
  the claim right above used to also say the 50 EMA TP wiring
  (`ema50_tp` -> `get_dynamic_trade_params`'s `ema50_tp_hint`) was
  "verified already correctly wired." That was wrong -- verified only
  that the value *reaches* the parameter, not that it ever actually
  takes effect. `ema50_tp` is always on the wrong side of entry by
  construction (the cross-validity gate in `strategy_ema_scalp_cross()`
  requires price already be above the 50 EMA for a BUY signal, below for
  a SELL), and `get_dynamic_trade_params`'s own guard only applies it as
  TP when it's on the *correct* side with >=1.2:1 RR -- a condition this
  value can structurally never meet. Live silently, permanently falls
  back to its structural swing-based TP1 instead. The "50 EMA is the
  primary TP target" feature this spec describes has never actually
  fired in live. See `strategies_registry.py`'s `_adapt_ema_scalp_cross`
  docstring for the full trace and the harness-side fix (the adapter
  used to pass this broken value straight through, producing a
  catastrophic-looking 0.4% win rate on real data that was actually a
  harness bug, not the strategy's real performance).
- **Added: the "Distance Rule"** — the spec's no-trade-zone filter for when
  the 9/25 cluster and 50 EMA are bunched/braided (ranging market, cross
  is noise not momentum). Implemented as an ATR-relative gap requirement
  (`config.EMA_DISTANCE_RULE_ATR_MULT`, starting value 0.5x M5 ATR) rather
  than the spec's fixed "~15 pips", since a fixed pip count doesn't
  translate across Gold/BTC/forex (the same reasoning the now-removed
  `strategy_advanced_smc`'s `min_ob_size` used). Not empirically
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

Every report the harness prints is labeled `[LIVE]` since all four
registered strategies genuinely trade real money today — no flagged-off
or dormant strategies remain in the registry (see "Fallback and dormant
strategies removed" above for what used to be here and why).

### AOX wiring

AOX (`run_aox_layered_entry`) manages a 3-phase state machine per symbol
(Layer 1 SD-zone tap 25% → Layer 2 SMT+CISD+FPFVG "Turtle Soup" 25% →
Layer 3 mitigation-block "Hippo" 50%) that persists across many bar-closes
and appeared to place real orders itself — unlike every other strategy
here, which makes one stateless decision per bar. Wiring it in took two
steps:

1. **Split detection from execution.** `run_aox_layered_entry` was
   refactored into `detect_aox_phase_signal(aox_state, df_m5, df_m1,
   effective_trend, symbol)` — the pure phase-gating logic, every check
   and threshold unchanged — plus a thin wrapper that calls
   `execute_aox_layer()` with whatever the pure function decided. Same
   split every other extraction in this harness follows: the live file
   keeps one function that's independently testable, not two divergent
   copies of the decision logic.
2. **A dedicated stateful driver, not a `StrategyAdapter`.** `aox_driver.py`
   walks the M5 series bar by bar itself, keeps one `aox_state` dict alive
   across the whole run (same shape `get_aox_state()` uses live), and
   calls `detect_aox_phase_signal()` at every bar — so a layer that fires
   is recorded as its own `SimulatedTrade` while the state machine keeps
   evolving underneath it (Layer 2 can fire while Layer 1's trade is still
   open, exactly like live). Run it with `--strategy AOX` or `--all` in
   `run_backtest.py`. `check_smt_divergence`'s correlated-pair gate (e.g.
   XAUUSDm↔XAGUSDm) needs a second symbol's M15 data — pass
   `--corr-symbol`/`--corr-m15`, or it passes through with no veto (same
   "no data → no veto" behavior the live function already has for a
   missing feed).

**A real bug found and fixed along the way (not something the extraction
introduced — it was already there):** `reset_aox_state(symbol)` existed,
fully implemented, with **zero call sites anywhere in the file**. Combined
with `run_aox_layered_entry`'s call site running *before* the main loop's
shared `state.symbol_cooldowns` check, AOX never actually honored its own
"reset after 2 hours" comment — once a symbol completed one full 3-layer
cycle, its phase stuck at 3 forever (no phase-3 branch existed in the
detection logic, so every subsequent call just returned `None`). AOX went
permanently inert per-symbol for the life of the running process, with no
error or log to indicate it. Fixed by having `run_aox_layered_entry` check
the shared cooldown dict directly and call `reset_aox_state()` once it
clears; `aox_driver.py` mirrors the identical rule with its own local
`cooldown_until` (the harness runs one strategy at a time, so there's no
other cooldown source to share the dict with).

**Deliberately preserved, not fixed:** `detect_manipulation_spike`'s own
docstring says it detects the spike "on M15," and the AOX reference spec
calls the 15-minute chart the primary trend-refinement timeframe — but the
call site (both before and after this extraction) passes `df_m5`, not a
separate M15 series. Left exactly as found and flagged in
`detect_aox_phase_signal`'s docstring: changing the timeframe here is a
real design decision (needs an M15 feed threaded through this whole call
chain), not something to bundle into a behavior-preserving extraction.

**Verified mechanically, not just by compiling:** stepped
`detect_aox_phase_signal` through Phase 1 → Phase 2 → Phase 3 directly
(forcing `check_smt_divergence`/`detect_cisd_trigger`/`detect_fpfvg` to
pass, since the codebase's synthetic random-walk test data has no genuine
Turtle Soup setups) and confirmed each phase produces the correct
`layer_name`/`risk_fraction`/`sl`/`tp` from a fabricated fib dict, with the
correct `next_phase`. Phase 0 itself (spike + SD-zone + sniper-zone tap)
never fired naturally against the synthetic data in ~5,760 M5 bars — the
sniper zone is a genuinely narrow band (fractions of a point on Gold), and
a random walk doesn't produce the structured retracements real manipulated
moves do. That's a data-realism limit of synthetic history, not a driver
bug — confirmed separately that the SD-zone/reached_sd4 check itself fires
often (163 times in one run) and only the subsequent sniper-zone touch
never lands. Re-run against real exported history before trusting any AOX
trade count from this harness.

### STRUCTURAL_SWING wiring (separate script)

Unlike every other strategy here, `STRUCTURAL_SWING` doesn't live inside
`hybrid_trading_bot_multiuser.py` at all — it's `structural_swing_pro.py`,
a standalone script. That's deliberate: `hybrid_trading_bot_multiuser.py`
and `intraday.py` don't dispatch on `strategy_id` — every strategy defined
in a given bot file runs for every user who launches that file, regardless
of which strategy they picked in the UI. Folding a new strategy into either
shared file would have silently bundled it into a tier that didn't select
it. A dedicated script per tier (matching how `intraday.py` already relates
to `hybrid_trading_bot_multiuser.py`) keeps that separation real. Full
reasoning in `structural_swing_pro.py`'s own module docstring.

Because it's a separate module, it needed its own loader
(`swing_loader.py`, mirrors `bot_loader.py`) and its own driver
(`swing_driver.py`, mirrors `aox_driver.py`'s "not a `StrategyAdapter`"
pattern — `BacktestEngine` is built around one shared bot module per run,
which doesn't fit a genuinely different file). One thing that made this
simpler than AOX: `detect_structural_swing_signal(df_d1, df_h4, symbol)` is
a pure function that takes its OHLC windows as plain arguments instead of
calling `get_market_data()` internally, so `swing_driver.py` doesn't need
`replay_data.py`'s monkeypatching machinery at all — `HistoricalDataset.
window()`'s results are handed straight to the decision function, exactly
like calling it live would.

**A real design issue found via the real-data backtest, not a coding
bug:** the first version placed the stop-loss beyond the *entire D1 leg's
origin* (the point that invalidates the higher-high/higher-low bias read).
On real XAUUSDm data every single candidate that cleared the zone-touch +
rejection-candle bar (9 of them, over the ~90-day window) still failed the
MIN_RR filter — often by a wide margin — because a leg's full range routinely
swamped the reward to the next real opposing level. Fixed by moving the
stop to the *local pullback's own extreme* (the H4 high/low since the D1
leg's own end, which is often the trigger candle's own wick) — the point
that actually invalidates this specific pullback continuing, not the much
larger move that invalidates the whole D1 bias read. Re-ran after the fix:
5 raw signals fired (down to 3 non-overlapping trades once one is "open"),
all with correct SL/TP sides and sane R-multiples matching their computed
RR. Run it with `--strategy STRUCTURAL_SWING` or `--all`; needs `--d1` in
addition to `--h4` (see "Getting historical data" below).

### INTRADAY wiring (separate script, real bugs found and fixed)

`intraday.py` is a third, separate script — the Pro-tier "Intraday Core"
strategy, previously never backtested at all despite being live and
charging more than the free tier. Its real live entry point is
`context_decision_engine()`, which checks five named strategies in
priority order every time it's called (Strategy E = AOX Sniper, B = H1 OB
Retest, A = H4 Trend Pullback, C = London Open Breakout, D = reversal
after liquidity sweep — see that function's own comments in intraday.py).
Confirmed real call sites for all five (not dead/flag-gated code) by
reading the function directly, same discipline as everywhere else in this
harness.

Needed its own loader (`intraday_loader.py`, mirrors `bot_loader.py` —
including the genai stub, since intraday.py does import
`google.generativeai` even though the backtest never reaches it with no
GEMINI_API_KEY set) and its own replay patch (`intraday_replay.py`,
mirrors `replay_data.py`). Closer in shape to `aox_driver.py` than
`swing_driver.py`: `context_decision_engine()` is **not** a pure function
— it calls `get_market_data()` and `datetime.now()` internally through
several nested live helpers (`NarrativeIntentEngine.build`,
`get_market_regime_and_trend`, all five `strategy_*` functions,
`is_in_kill_zone`/`get_active_macro_window`/`get_current_session`, and
`strategy_london_open_breakout`'s own session-prime check) — so this
driver needs the full patch-and-freeze machinery, unlike
`structural_swing_pro.py`'s pure `detect_structural_swing_signal()`.

One extraction was needed for backtest/live parity: `place_intraday_trade`
mixed its real TP-selection logic (liquidity-target-with-RR-floor, falling
back to the nearest real H1 swing level, falling back to an ATR
projection) in with real MT5 order construction. Pulled the TP logic out
into `resolve_intraday_tp()` — same "strategy_ema_scalp_cross extraction"
precedent as the other bot file — so `intraday_driver.py` calls the exact
same function `place_intraday_trade` does instead of reimplementing it.

**Two real, live bugs found via the first real-data run — not backtest
artifacts, both fixed directly in `context_decision_engine()` itself:**

1. **Structure-anchored stop-loss could land on the wrong side of entry.**
   The SL override took `identify_swing_highs_lows()`'s *chronologically
   most recent* pivot unconditionally (`swing_highs[-1]` /
   `swing_lows[-1]`) with no check that it was still actually ahead of
   price. In a live trend, price regularly moves back through an old local
   high/low that's still the "last" one detected in a 200-bar window — so
   a SELL's "stop" could end up *below* current price (in the trade's own
   profit direction), which no broker accepts as a real stop. On real
   XAUUSDm data this affected the majority of Strategy A signals in a
   single ~90-day window. Fixed by walking back through detected pivots
   for the nearest one still genuinely on the correct side of price;
   falls through to the firing strategy's own stop-loss if none qualify.
2. **The narrative-derived TP target had no direction check.**
   `entry_signal['liquidity_target'] = narrative['target_price']` was
   attached to every trade unconditionally. `narrative['target_price']` is
   derived from `narrative['dol']` ("where's the next liquidity pool"),
   which has **no guaranteed relationship** to `direction` — the real
   trade direction the firing strategy actually chose a few lines earlier.
   When they disagreed, the resulting TP landed on the wrong side of
   entry — and `resolve_intraday_tp`'s minimum-RR check didn't catch it,
   because it only measures absolute distance, not which side of entry the
   target is on. On real data this produced "TP" exits with R-multiples of
   -7.3R, -2.7R, and -2.9R in a single run — a target that looked like a
   win by exit-reason label but was actually a severe loss. Fixed by only
   attaching `liquidity_target` when it's genuinely on the correct side of
   current price for the real direction; `resolve_intraday_tp`'s own
   direction-aware swing-level fallback handles it otherwise.

**One backtest-only limitation, disclosed rather than silently absorbed:**
these strategies mix timeframes (an M15 rejection candle informing a tight
SL, nested inside this driver's H1 walk cadence), so by the time of fill —
this bar's own close, up to ~45-59 minutes after the M15 confirmation
candle — price can occasionally have moved enough to put an otherwise-valid
tight stop on the wrong side, purely as an artifact of walking a coarser
bar than the finest timeframe a signal used. Live doesn't have this gap
(the real fill happens seconds after the decision, not up to an hour
later). `intraday_driver.py` guards against it directly: any signal whose
SL/TP aren't genuinely on the correct side of the actual fill price is
skipped, the same discipline a careful trader would apply manually rather
than chasing a setup whose invalidation point already ran through.

Run it with `--strategy INTRADAY` or `--all`; needs `--h4`, `--m15`, and
`--d1` in addition to `--h1` (Strategy E / AOX Sniper additionally wants
`--m1`, but is a clean no-op without it — everything else still runs).

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
live helpers like `get_h4_macro_bias` and `strategy_shaakuni_ssm` use to
pull their own data) to serve historical, no-lookahead windows instead of
live MT5 calls. `time_travel.py` does the same for `datetime.now()`, so
kill-zone/session gates evaluate against the bar being replayed instead
of the real clock.

Trend specifically is computed by `strategies_registry.py`'s own
`_get_trend()`, which directly replicates the live main loop's
`effective_trend` cascade (H4 macro bias, strict H1 EMA-stack confirm,
conflict-skip) rather than patching a live function to reuse -- see that
function's own docstring for why: the live file's own
`get_market_regime_and_trend()` has zero call sites anywhere in the
actual trading loop and is separately broken on real data (references two
`AITradingConfig` attributes that don't exist). It was a real bug that
`_get_trend()` used to call that dead function, found from the first
real-data backtest run.

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

Produces `XAUUSDm_M1.csv`, `_M5.csv`, `_M15.csv`, `_H1.csv`, `_H4.csv`,
`_D1.csv`. M1 is needed by `AOX` and (optionally, Strategy E) `INTRADAY`;
H4 is needed by `SHAAKUNI_SSM`, `STRUCTURAL_SWING`, and `INTRADAY`; D1 is
needed by `STRUCTURAL_SWING` and `INTRADAY`; M15 is needed by `INTRADAY`
(in addition to AOX's `--corr-m15` use). `SWAPPY_3C`/`EMA_SCALP_CROSS`
only need M5/H1.

No native D1 export yet? `pandas.read_csv(...).resample('1D', on='time')`
over an H4 export (aggregate `open`→first, `high`→max, `low`→min,
`close`→last) is a reasonable stand-in for backtesting — what the real
`STRUCTURAL_SWING` verification run above used, since M1-era exports
predate D1 being added here. It's not byte-identical to MT5's own D1 bars
(server-day boundaries can differ slightly from a UTC calendar-day
resample), so re-run against a native D1 export once you have one before
fully trusting a result over the mechanics.

## Running a backtest

From inside `python_scripts/`:

```
# One strategy:
python3 -m backtest.run_backtest \
    --symbol XAUUSDm --data-dir ./history/XAUUSDm \
    --m5 XAUUSDm_M5.csv --h1 XAUUSDm_H1.csv \
    --strategy SWAPPY_3C --out trades.csv

# Every registered strategy, one report each, one combined trade CSV:
python3 -m backtest.run_backtest \
    --symbol XAUUSDm --data-dir ./history/XAUUSDm \
    --m1 XAUUSDm_M1.csv --m5 XAUUSDm_M5.csv --h1 XAUUSDm_H1.csv \
    --h4 XAUUSDm_H4.csv \
    --all --out trades.csv
```

Each report prints win rate, expectancy in R, profit factor, and max
drawdown. The combined CSV records every trade's full entry reasoning, so
any losing trade is re-derivable from the same historical data, not just
summarized.

## Known limitations — read before trusting a result

- **Spread is a static per-symbol approximation**
  (`engine.py`'s `DEFAULT_SPREAD_MODEL`), not real recorded spread.
- **Take-profit defaults to a fixed R-multiple off the SL distance**
  (`--rr`, default 2.0) only for `EMA_SCALP_CROSS` (see its adapter's
  docstring for why -- the live strategy's own "50 EMA TP" feature is
  provably inert, so there's no honest strategy-specific target to use
  instead). `SHAAKUNI_SSM` and `SWAPPY_3C` both compute their own real
  TP (Shaakuni: opposing liquidity target; Swappy: fixed 3:1 RR off the
  stop-entry level per the live spec). None of this reproduces the live
  bot's full exit logic (runner management, breakeven trailing, mid-trade
  `DecisionEngineV2` adjustments) -- this measures each strategy's entry
  logic under a standard, explicit exit framework, not the live bot's
  exact exit behavior.
- **One position at a time per strategy.** The engine doesn't evaluate
  new entries while a simulated trade from the same run is open, so it
  can't test correlated/stacked exposure across strategies running
  simultaneously (which the live bot does). AOX's own driver is the one
  deliberate exception — its layers are allowed to overlap in time by
  design (see "AOX wiring" above), matching that live behavior instead of
  this general rule.
- **Small sample sizes will look great or terrible by pure chance.**
  Several strategies produced 0 trades against 20 days of synthetic data
  in smoke testing — that's expected for strict multi-condition setups on
  a short window, not a harness bug. Don't trust a result from under a
  few hundred trades.

## Other live-file fixes verified via this harness (not strategy-shaped)

Not every real bug this engagement found lives in strategy logic a
`StrategyAdapter` can drive — some live in the main scan loop's risk
gating (`EdgeEngine`, `CapitalController`, `SymbolCorrelationTracker`),
which the per-strategy adapters bypass entirely (they call
`bot.strategy_X()` directly, not the full cascade). Those still got
verified through this harness's `bot_loader.import_bot_module()` — calling
the real classes directly with constructed inputs, same "call the actual
live object, not a reimplementation" principle, just without a
`StrategyAdapter` wrapper since there's no bar-by-bar decision to replay:

- **`CapitalController.calculate()` ignored two of its own inputs.**
  `symbol_metrics` was a parameter with a real value already computed at
  the live call site, but the method body never read it. Separately,
  `PatternRecognitionSystem.get_edge_health_score()` (a real 0.0-1.5
  confidence multiplier) was only ever called in the mid-trade management
  loop, and even there its result was discarded. Both now actually move
  position size. Verified with direct assertions: strong/weak pattern
  history and good/bad symbol performance move size in the correct
  direction; omitting the new parameter reproduces the exact old
  behavior; the 1.5% hard cap still holds with everything maxed.
- **`SymbolCorrelationTracker.should_allow_trade()` had zero call
  sites**, and separately its `correlation_groups` dict used bare symbol
  names (`'XAUUSD'`) while every real traded symbol carries a broker
  suffix (`'XAUUSDm'`), so `get_correlation_group()` would have returned
  `'UNCORRELATED'` for everything even if it had been called. Both fixed
  (prefix match handles the suffix; the gate is now wired into the main
  loop's entry cascade). Verified directly: simulating 2 open
  same-correlation-group positions blocks a 3rd, a different group is
  unaffected, and being under the limit still allows a trade.
- **`RegimeDetector.detect_regime()`'s output never reached a decision.**
  Its own docstring says it "selects appropriate strategies for each
  regime," and the live call site already passes a real computed value
  into `TradeContext.regime` -- but `EdgeEngine.calculate()`'s `WEIGHTS`
  never included it. Fixed as a multiplicative adjustment on the existing
  weighted score (TRENDING/unrecognized = neutral 1.0x, RANGING = 0.80x)
  rather than re-tuning `WEIGHTS` itself. Since `EdgeEngine` is the single
  scoring authority both the entry gate and the mid-trade exit re-score
  call into, this one fix closes the gap on both sides without needing a
  second, separate change to `ScalpingExitEngine`. Verified directly:
  RANGING scores exactly 80% of the identical TRENDING input; an
  unrecognized regime string reproduces the exact old (neutral) behavior.

## Extending this

No dormant strategies remain — every `StrategyAdapter` in
`strategies_registry.py` calls something with a real live call site. For
any future strategy, the same honest path applies: extract it into a
standalone, testable function in the live bot file first, with real
testing on the actual MT5/Windows environment to confirm the extraction
didn't change live behavior — then add either a `StrategyAdapter` in
`strategies_registry.py` (for a single-bar, single-trade decision) or a
dedicated driver like `aox_driver.py` (for anything with cross-bar
state). Don't shortcut this by reimplementing the logic directly in the
harness; that reintroduces exactly the live/backtest drift risk this
whole harness exists to eliminate.

And per the "Dormant strategies removed" section above: don't add a new
strategy to the live cascade before the 4 existing ones (Shaakuni SSM,
Swappy 3C, EMA Scalp Cross, AOX) have real-data evidence behind them
across more than one symbol and more than one time window. One ~90-day
single-symbol backtest is encouraging, not proof.
