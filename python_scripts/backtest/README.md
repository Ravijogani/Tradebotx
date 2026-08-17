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
Real-data result (XAUUSDm, ~90d), **before** the market_intelligence.py
integration described below: 11 trades, -0.003R expectancy, 36.4% win
rate, PF 1.00 — dead flat, not negative, not positive, on a sample too
small to call either way. Two real bugs were found and fixed getting to
that number — see "INTRADAY wiring" for what they were; both are live-code
fixes (context_decision_engine is the actual live function), not
backtest-only corrections. **After** wiring in the auction-theory regime
engine (see "MARKET INTELLIGENCE" below): 18 trades, +0.446R expectancy,
33.3% win rate, PF 1.71 — a real, verified improvement, five of those
trades coming directly from the new Balance Fade strategy (`--strategy
INTRADAY` now needs `--m15`/`--h4`/`--d1` in addition to `--h1`).

`BALANCE_FADE` (`market_intelligence.detect_balance_fade_signal`, driven
standalone via `balance_fade_driver.py`) is also now a real, independently
backtestable strategy in its own right — not tied to any one bot file, see
"MARKET INTELLIGENCE" below. Real-data result (XAUUSDm, ~90d, H1): 32
trades, +0.620R expectancy, 37.5% win rate, PF 1.96 — the best
risk-adjusted profile of anything tested in this harness so far, though
still a modest sample. Run it with `--strategy BALANCE_FADE` or `--all`;
needs only `--h1`.

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

## MARKET INTELLIGENCE (`market_intelligence.py`) — auction theory, liquidity, positioning

Every strategy across all three bots was originally built on retail-
indicator regime detection (ADX trend/range, EMA stacks) or no regime
detection at all — and, more importantly, **every one of them is a trend/
breakout/continuation archetype. Not one was designed to profit when the
market is rotating inside a range**, which is where price spends most of
its time. `market_intelligence.py` is a new, shared, pure module (zero
MT5/live-bot dependency — plain OHLCV DataFrames in, dict/float/None out)
that replaces the retail-indicator framework with the one an institutional
or professional prop desk actually uses, and adds the missing strategy
archetype. It's imported directly by all three live bots and by two new
backtest drivers (`balance_fade_driver.py` for the standalone strategy,
plus direct calls from `intraday_driver.py`/`swing_driver.py`'s underlying
live functions).

**Auction Market Theory replaces ADX.** `classify_auction_state()` builds
a Volume Profile (Point of Control, Value Area High/Low — the standard
"volume profile from OHLC" approximation used by any tool without L2 data:
each bar's `tick_volume` is distributed across every price bucket its
range overlaps) plus VWAP, and classifies the market as **BALANCE**
(rotating inside value — the fade regime) or **IMBALANCE_UP/DOWN** (a
genuine initiative move that left value on real follow-through, not a
single wick). This is a materially sharper regime read than "ADX > 25"
because it's built from where volume actually transacted. Honest caveat,
stated here and in the module's own docstring: MT5's `tick_volume` is tick
*count*, not real traded volume (forex/CFDs are OTC) — a workable, standard
proxy, not literal CME/COMEX contract volume.

**`build_liquidity_map()`** generalizes the equal-highs/lows liquidity-pool
concept Shaakuni SSM and AOX already used narrowly into a reusable
function: detects swing highs/lows, clusters nearby ones into pools, marks
each swept or untested.

**`detect_balance_fade_signal()`** is the actual missing strategy: fires
only when auction state reads BALANCE, fades the value area edge (VAH for
a SELL, VAL for a BUY) back toward POC/VWAP, confirmed by a rejection
candle, with a liquidity-map guard that refuses the fade if an untested
pool sits just beyond the edge (price is more likely to sweep it first
than reverse). Independently backtestable (`--strategy BALANCE_FADE`) and
wired into all three live bots as an additional strategy.

**`compute_intermarket_bias()`** generalizes AOX's SMT-divergence gate
(previously one narrow check on one strategy) into a reusable cross-market
confirmation any strategy could call — built and unit-tested, not yet
wired into a live call site in this round (no second real-data symbol
export was on hand to verify a live integration against; the function
itself is ready).

**`volatility_target_multiplier()`** — standard vol-targeting, scales size
by current realized volatility vs. its own trailing distribution. Wired
into all three bots' risk sizing (`CapitalController.calculate()` in
`hybrid_trading_bot_multiuser.py`, `validate_trade_risk()`/
`place_intraday_trade()` in `intraday.py`, `validate_trade_risk()`/
`place_swing_trade()` in `structural_swing_pro.py`).

**`fetch_cot_positioning()`/`cot_positioning_bias()`** — CFTC Commitment of
Traders positioning (public, weekly) for Gold/Silver/Oil, the one piece of
genuine institutional data this repo had zero of. **Not verified
end-to-end**: this sandbox's outbound network policy blocks `cftc.gov`
entirely (confirmed directly via a request, not assumed). The fetch is
written defensively (same "no data → neutral, never blocks trading"
contract every AI-optional fallback in this codebase follows) and the
interpretation logic (`cot_positioning_bias`) is independently unit-tested
against synthetic data, but the live network call itself needs verification
on a real deployment host before being trusted. Not yet wired into any
live bot's call sites this round — the fetch needing real-host
verification first, and the pure interpretation function being ready
whenever it is.

### Wiring into `structural_swing_pro.py`

`scan_for_signal()` now computes H4 auction state before trusting a
structural continuation signal: a confirmed pullback setup firing while
auction state shows IMBALANCE in the *opposite* direction is rejected (a
real red flag — price is still making a genuine move against the signal).
When no structural setup fires and auction state reads BALANCE,
`detect_balance_fade_signal()` gets a chance instead — its output dict
already matches what `place_swing_trade()` expects (`direction`/
`stop_loss`/`take_profit`), no adapter needed. Risk sizing now goes
through a new `effective_risk_percent()` helper (`config.BASE_RISK_PERCENT`
× `volatility_target_multiplier()`), called identically by
`validate_trade_risk()` and `place_swing_trade()` so the validated and
sized risk can never diverge — same discipline `_project_lot_and_risk()`
already established.

### Wiring into `intraday.py`

`context_decision_engine()` computes auction state right after `df_entry`
is fetched. Two integrations, both live-code changes (this is the real
function, not a backtest-only path):

1. **TREND_CONTINUATION now requires auction confirmation, not just ADX.**
   The existing `market_regime == "TRENDING"` check is tightened, not
   replaced, with `auction["state"]` agreeing (IMBALANCE_UP for a BUY bias,
   IMBALANCE_DOWN for SELL) — an ADX-trending reading while price hasn't
   actually left its value area on real volume no longer qualifies.
2. **Strategy F (Balance Fade)** is tried when none of A-E fired and
   auction state reads BALANCE. Two real integration bugs were found and
   fixed getting this to actually fire reliably, not just log a signal
   that never converts to a trade:
   - The `move_type not in config.BEHAVIOR_MODES` gate (checked before any
     strategy runs) has no relationship to auction state at all — a
     BALANCE reading with no independently-classified `move_type` (no
     sweep+mss, no expansion_potential>0.7) returned `None` before
     Strategy F ever got a chance to run. Fixed with an explicit bypass
     when `auction["state"] == "BALANCE"`.
   - The generic "Final Formatting & Filters" RR check further down uses
     `narrative['distance_to_target']` — a completely different, unrelated
     number to Balance Fade's own POC/VWAP-based RR (already validated
     inside `detect_balance_fade_signal()` itself). Applying it a second
     time would judge Strategy F against a number that has nothing to do
     with its actual trade. Same for the structure-anchored SL override and
     the `liquidity_target` override two sections earlier — both were
     designed for Strategies A-E, which don't compute a target this precise
     themselves, and would have silently discarded Strategy F's real,
     already-correct SL/TP. All three are now skipped specifically for
     `strategy_name == 'BALANCE_FADE'`.

   `place_intraday_trade()` and `intraday_driver.py` (the backtest path)
   both bypass `resolve_intraday_tp()` for Balance Fade signals for the
   same reason — it would otherwise discard the signal's own `tp` in favor
   of a liquidity-target/swing-fallback computation Balance Fade never
   needed. Verified this actually mattered, not just defensive
   over-engineering: before these three fixes, `[STRAT F]` logged a signal
   exactly once across the whole ~90-day real-data run and it never became
   a trade; after, Balance Fade contributed 5 real trades to the 18-trade
   final result above.

   Risk sizing: a new `volatility_scaled_risk_multiplier()` helper,
   multiplied into `risk_percent` at both call sites in
   `validate_trade_risk()` and `place_intraday_trade()` the same way
   `risk_multiplier` already was.

### Wiring into `hybrid_trading_bot_multiuser.py`

Lighter-touch than the other two, a deliberate scope decision rather than
an oversight — explained here plainly: this file's downstream pipeline
(`CapitalController`, `portfolio_risk_gates_allow`, ban/unban, the 4-part
post-mortem system, `get_dynamic_trade_params()`'s own dynamic TP
computation) is the most complex and heavily-interdependent of the three
bots' risk/execution paths, built up over many rounds of this whole
engagement. Wiring Balance Fade in as a genuinely new live-firing strategy
here needs its own dedicated placement path (mirroring how Swappy 3C's
`place_swappy_pending_order()` bypasses the shared setup pipeline entirely
to protect its own structural TP) rather than a rushed bolt-on that risks
either breaking already-verified logic or silently losing Balance Fade's
own real target the same way `intraday.py`'s bug did before it was caught
above. Deferred, not dropped.

What **is** wired in, real and verified:

- **`_auction = mi.classify_auction_state(df_m5)`**, computed once per
  symbol per scan, gates Strategy A (EMA Scalp Cross) — the weakest of the
  four live setups by real-data evidence (+0.068R/trade, barely above
  zero pre-cost, exactly the signature of a momentum-cross strategy firing
  in both trending and ranging conditions with no regime filter). Now
  additionally requires the M5 auction state to confirm genuine imbalance
  in the trade direction before firing, the single highest-evidence gate
  among the four existing strategies.
- **`CapitalController.calculate()`** gained an optional
  `df_for_vol_target` parameter — when passed (wired in at the main scan
  loop's call site with `df_m5`), multiplies in
  `volatility_target_multiplier()` alongside the existing `vol_scale`
  factor. Not the same thing: `vol_scale` is a fixed per-symbol constant
  (BTC=0.40, XAU=0.75, etc., normalizing dollar-per-point across
  instrument types); this is dynamic — the *same* symbol sizes down when
  it's currently more volatile than its own recent normal. Defaults to no
  adjustment when no data is passed, so every other call site is
  unaffected.

### Liquidity reference levels (PDH/PDL, session H/L) + HTF FVG — refining entries and TP targets

Requested directly: which SMC liquidity concepts (previous day high/low,
last H1 candle, the last completed Asian/London/New York session range,
higher-timeframe order blocks, H1/HTF fair value gaps) should refine entry
quality and TP targeting across Shaakuni SSM, Swappy 3C, and EMA Scalp
Cross. HTF order blocks were already live (that's literally what SSM's
extreme-OB entry is). The rest either sat as **dead code** or didn't exist:

- `compute_liquidity_reference_levels(df_d1, df_h1)` — PDH/PDL (previous
  *completed* D1 bar, not the still-forming current one), H1_HIGH/H1_LOW
  (last closed H1 candle), and `{ASIAN,LONDON,NEW_YORK}_HIGH/LOW` (the
  realized range of the last *completed* occurrence of each UTC session
  window — a trailing run of in-session bars still touching the latest bar
  is skipped in favor of the previous complete one). Each level tagged
  BUY_SIDE/SELL_SIDE (same convention as `build_liquidity_map`) and
  swept/untested against the H1 series. This generalizes
  `intraday.py`'s `detect_htf_liquidity_targets()` — which did the same
  "prev day high/low as TP target" idea, correctly, but had **zero call
  sites anywhere** — to every reference level above, usable by any
  strategy in any of the three bots.
- `detect_fvg_zones(df, direction)` — the same 3-candle-imbalance FVG
  definition `detect_fpfvg()` already used, but that one only ever ran on
  M1 for AOX. Reimplemented here (not imported — same zero-dependency-on-
  bot-files discipline as `find_swing_points`) so H1/H4 FVGs are usable
  anywhere, returning unmitigated zones (not just a midpoint).
- `liquidity_confluence_check(entry_price, direction, levels, fvg_zones, atr)`
  — is this entry actually reacting to a real level, or sitting in open
  air? `nearest_liquidity_target(entry_price, direction, levels, sl_distance, min_rr)`
  — the nearest untested level beyond entry that clears a minimum RR, as
  a TP source (returns `None`, never overwriting a strategy's own target,
  if nothing qualifies).

**Wired in, three different ways, deliberately — not one generic filter
bolted onto all three:**

- **Shaakuni SSM**: confluence is a *soft* filter, not a veto — a
  confluent entry keeps the existing 1.5:1 minimum RR; a non-confluent one
  needs a stricter 2.0:1. TP is upgraded to the nearest qualifying
  liquidity level only when it's genuinely farther out (better RR) than
  the sweep's own target — never a downgrade. Real-data result: 135 → 133
  trades, +0.703R → +0.713R expectancy — a wash, not a meaningful move
  either direction (confluence rarely matched at the exact OB entry price
  in this window).
- **Swappy 3C**: a +0.10 strength bonus (matching the function's own
  existing bonus-stacking pattern) when the stop-entry trigger sits at an
  untested level or a fresh FVG. **Disclosed limitation**: `strength`
  only ever feeds `EdgeEngine.calculate()`, which is LIVE-ONLY and never
  invoked by the backtest harness at all — this change is correct by
  construction and unit-tested, but its effect on trade selection is not
  backtest-verifiable, the same class of limitation as the volatility-
  target sizing integration.
- **EMA Scalp Cross**: a genuine hard veto, not a soft nudge — deliberately
  different from SSM's approach because this strategy's `liquidity_strength`
  field has the exact same EdgeEngine-only, backtest-invisible problem
  Swappy's `strength` does, so a scoring-only nudge here would have been
  completely unverifiable either way. A real, backtest-observable gate was
  the only way to actually check this mattered — justified further by
  this being the weakest-edge strategy already gated once this session
  (auction-imbalance filter). Real-data result: 74 → 15 trades (an ~80%
  reduction), but expectancy nearly tripled: +0.068R → +0.182R, PF 1.12 →
  1.30. Final accumulated equity over this ~90-day window actually
  dropped (+5.05R → +2.72R) purely because so much fewer volume more than
  offset the quality improvement — an honest trade-off between setup
  quality and trade frequency, not a clean win, disclosed as such.

**AOX was explicitly not touched.** Its entry logic is a 3-phase stateful
state machine (SD-tap → SMT+FVG Turtle Soup → Hippo/mitigation) that
persists across bar-closes, and this sandbox has no real M1 export to
backtest it with at all (`--m1` has never been available here — every AOX
run this whole engagement shows "Skipping AOX: needs --m1"). Wiring an
unverifiable change into the most complex, stateful entry logic in the
repo would have violated this project's core discipline of never shipping
a live-behavior change without running it against real data first.

**Efficiency finding, found and fixed while verifying this exact change**:
`identify_swing_highs_lows()` (in `hybrid_trading_bot_multiuser.py`, the
function `classify_m30_character()`'s CHoCH gate depends on) used a
Python-level nested loop calling `df['high'].iloc[i]` repeatedly instead of
slicing numpy arrays — a real bottleneck once called frequently enough
(profiling a real-data run pinned it as the majority of a multi-minute
slowdown). Rewritten to numpy-array slicing, confirmed **byte-identical**
output against the original via 60 randomized equivalence tests (including
forced tied values — the one case a careless rewrite of a *strict*
dominance check could silently get wrong) and 47x faster on a 3000-bar
benchmark. Separately, `compute_liquidity_reference_levels()` itself is now
memoized (`cached_liquidity_reference_levels()` in
`hybrid_trading_bot_multiuser.py`) keyed on `(df_d1's last bar time,
df_h1's last bar time)` — PDH/PDL only move once a day, H1_HIGH/session
levels only move once an hour, but Swappy/EMA call this once per M5 bar in
a backtest replay, up to 6-12x more often than the underlying data
actually changes.

### Market regime router — the "smart in all conditions" piece, and a self-caught mistake

Requested directly, after being asked to make the bot know "every single
depth detailed thing of trading" so it's "smart enough to trade in all the
conditions." Reading that literally as "add more strategies/concepts" would
have repeated a mistake this repo already made once: see "Fallback and
dormant strategies removed (2026-08)" above — 11 well-known
strategies/concepts (Wyckoff, volume profile, support/resistance, volume
imbalance, trend pullback, mean-reversion BB, ICT killzone, liquidity grab,
FVG retest engine among them) were built and then removed from this exact
codebase after producing zero real edge. More strategies did not make the
bot smarter; it made it noisier. The correct reading of "smart in all
conditions" is a bot that recognizes *when a condition doesn't suit any of
its strategies and stands aside* — the piece that was actually missing.

`classify_market_regime(auction, m30_char)` in `market_intelligence.py`
synthesizes the auction-state classifier and the M30-character classifier
(both already live, previously never combined into one verdict) into a
single regime label:

- `TREND_UP` / `TREND_DOWN` — M5 auction state shows a genuine initiative
  move (`IMBALANCE_UP`/`IMBALANCE_DOWN`), *and* it isn't contradicted by a
  just-happened M30 CHoCH in the opposite direction (a same-direction CHoCH,
  or no M30 read at all, does not downgrade the regime).
- `BALANCE` — auction state is rotating inside value; `allowed_directions`
  is the **empty set**. This is the actual "stand-aside" state: not a
  fourth strategy, a deliberate absence of one.
- `CHOPPY` — no reliable auction-state read, or a trend regime that got
  contradicted by a fresh opposing M30 CHoCH; also stands aside.

Each regime carries `allowed_directions` (`{"BUY"}`, `{"SELL"}`, or `set()`)
and a human-readable `reason` string logged at the point of use. Unit
tested with 10 cases covering both trend directions, the BALANCE
stand-aside, CHOPPY on missing/empty auction data, a same-direction CHoCH
not vetoing, an opposing CHoCH downgrading a trend to CHOPPY, and BALANCE
ignoring `m30_char` entirely (there's no trend to un-confirm).

**First attempt, and why it was wrong.** The obvious wiring is a blanket
gate: compute `_regime` once per symbol per bar, and require the
strategy's trade direction to be in `allowed_directions` before letting
*any* of Shaakuni SSM, Swappy 3C, or EMA Scalp Cross fire. Two things had
to be caught before this could ship:

1. Placement: `_regime` is computed before "STRATEGY D: AOX MODEL" in the
   scan loop's strategy order (Swappy → AOX → SSM). A single blanket
   `continue` placed right after computing `_regime` would have silently
   skipped AOX's own entry logic whenever the regime didn't favor the
   current trade direction — disabling a strategy that (a) is a
   structurally different manipulation/mean-reversion archetype (SD-tap →
   Turtle Soup → Hippo/mitigation), not a continuation strategy the regime
   router is even meant to describe, and (b) has never been verifiable in
   this sandbox at all (`--m1` has never been available here). Caught
   before running anything, by tracing the call order — fixed by gating
   each of the three continuation strategies individually at their own
   call sites, leaving AOX's condition completely untouched.
2. The gate itself, once applied only to the three intended strategies and
   run against real data, turned out to **help one and hurt two**:

   | Strategy | Trades (before → after) | Expectancy (before → after) | PF | Equity |
   |---|---|---|---|---|
   | SHAAKUNI_SSM | 133 → 30 | +0.713R → +0.305R | 1.71 → 1.30 | +94.78R → +9.14R |
   | SWAPPY_3C | 18 → 4 | +0.223R → -0.012R | 1.33 → 0.98 | +4.01R → -0.05R |
   | EMA_SCALP_CROSS | 15 → 5 | +0.182R → +0.790R | 1.30 → 2.95 | +2.72R → +3.95R |

   A mixed table like that is not self-explanatory — fewer trades and lower
   *total* equity is exactly what a good filter looks like too, if it's
   cutting a long tail of small losers. So before accepting or rejecting
   anything, every trade the gate removed was split out from every trade it
   kept, and each side's average R-multiple was computed:

   | Strategy | Removed trades (n, avg R) | Kept trades (n, avg R) |
   |---|---|---|
   | SHAAKUNI_SSM | 103 trades, **+0.831R** avg | 30 trades, +0.305R avg |
   | SWAPPY_3C | 14 trades, **+0.290R** avg | 4 trades, -0.013R avg |
   | EMA_SCALP_CROSS | 10 trades, -0.123R avg | 5 trades, **+0.790R** avg |

   For SSM and Swappy, the trades the regime gate *removed* outperformed
   the trades it *kept* — the filter was anti-correlated with quality, not
   an improvement, and the change in the summary numbers was an illusion of
   fewer-trades-means-tighter-filter. Only for EMA Scalp Cross did the gate
   correctly cut the worse half.

   The mechanistic reason: SSM's OB-retest entry and Swappy's 3rd-candle
   pullback entry both involve a deliberate pause/consolidation *within* an
   already-valid setup — exactly the kind of pattern the M5 auction-state
   classifier can legitimately score as `BALANCE` even when the trade is a
   textbook-correct continuation. EMA Scalp Cross enters directly on the
   EMA cross with no deliberate pause, so a genuine `BALANCE` read there
   really does mean "no momentum yet" — the same regime gate measures
   different things depending on how the strategy's entry itself already
   uses (or doesn't use) a pause.

**Final wiring, corrected before shipping**: the regime gate is opt-in, not
automatic. `_get_trend()` in `strategies_registry.py` takes a new
`apply_regime_gate: bool = False` parameter — only `_adapt_ema_scalp_cross`
passes `True`; SSM's and Swappy's adapters call it with the default (off).
The live scan loop in `hybrid_trading_bot_multiuser.py` mirrors this: SSM's
and Swappy's call sites were reverted to their original, ungated
conditions (with the full evidence table above left in-code as a comment,
not just in the commit message, so the next person who's tempted to
"just gate everything" sees why not to); only EMA Scalp Cross's call site
checks `_regime_ok`. AOX remains completely untouched, as it was from the
first design.

Confirmed with a full re-run after the correction: SHAAKUNI_SSM and
SWAPPY_3C returned to their exact pre-regime-router baseline (133
trades/+0.713R/PF 1.71/+94.78R and 18 trades/+0.223R/PF 1.33/+4.01R,
respectively — byte-identical to the numbers before any regime-router code
existed), while EMA_SCALP_CROSS kept its improvement (5 trades/+0.790R/PF
2.95/+3.95R). STRUCTURAL_SWING and BALANCE_FADE, untouched controls, were
unchanged. Zero tracebacks; trade sidedness (SL/TP correctly signed per
BUY/SELL) spot-checked on the EMA Scalp Cross ledger rows.

This is the same discipline this whole engagement has followed throughout:
a change that moves the summary numbers is not automatically a working
filter, and "the numbers changed in the direction I expected" still needs
checking against "did it change them for the right reason" before it
ships.

### Two more named traders (Raja Banks, Guardeer) + a frequency audit + a real bug found while verifying it

Requested directly: research two more traders (Raja Banks, and "Guardeer"
once disambiguated from a voice-transcribed name that didn't initially
match anything searchable) the same way TOPG/Shakuni Trap/Swappy were
researched earlier, and — the user's own explicit second half of the same
ask — audit whether this engagement's own additions have made trades
*harder* to find, not just smarter to take, since hybrid_trading_bot_
multiuser.py exists specifically to scalp and intraday.py to hold
multi-day swings.

**Research finding, stated plainly rather than silently padding the
codebase**: both traders teach standard ICT/SMC vocabulary (liquidity,
order blocks, FVG, BOS/CHoCH, HTF structure) that substantially overlaps
with what earlier phases of this exact session already built. Only two
pieces were genuinely new:

- **Premium/Discount (equilibrium zones)** — Raja Banks' primary
  directional filter: is price in the cheap half of its current dealing
  range (DISCOUNT — favor buys) or the expensive half (PREMIUM — favor
  sells)? `compute_equilibrium_zone()` / `premium_discount_confluence()`
  in `market_intelligence.py`, built off the swing-point range bounded by
  `find_swing_points()` (reused, not reimplemented).
- **Optimal Trade Entry (OTE)** — Guardeer/ICT's Fibonacci refinement of
  *where* inside an already-valid setup to enter: the classic 61.8%-79%
  retracement of the most recent impulse leg in the trade's direction.
  `compute_ote_zone()` / `in_ote_zone()`, layered on top of an existing
  order-block/FVG entry, never a replacement for one. 30 unit tests cover
  both (dealing-range/leg construction, PREMIUM/DISCOUNT/EQUILIBRIUM
  classification, BUY/SELL OTE zones off up-legs and down-legs, the
  None-safe "no leg yet" cases, and boundary-inclusive `in_ote_zone`).

**Frequency audit, done before wiring anything new in** — real numbers
from the last full real-data backtest of hybrid_trading_bot_multiuser.py's
three backtestable strategies:

| Strategy | Trades | Span | Trades/day |
|---|---|---|---|
| SHAAKUNI_SSM | 133 | 87d | 1.53 |
| SWAPPY_3C | 18 | 78d | 0.23 |
| EMA_SCALP_CROSS | 5 | 65d | 0.08 |

EMA Scalp Cross and Swappy 3C are thin. Tracing why, rather than assuming
either needed loosening or needed nothing:

- **EMA Scalp Cross** has 6 internal gates (200 EMA trend, EMA-bunching
  distance rule, W/M/H&S pattern pre-filter, cross validity, unswept-trap
  avoidance, this-session's liquidity-confluence veto) plus 2 call-site
  gates (enable flag, this-session's regime gate) plus 4 shared upstream
  gates before it's even tried (H4/H1 conflict, M30 CHoCH veto,
  EMA-momentum-flat, overextension). Both of THIS session's own additions
  were already independently verified with real removed-vs-kept R-multiple
  evidence to cut worse trades, not better ones (liquidity confluence:
  74→15 trades, expectancy +0.068R→+0.182R; regime gate: removed -0.123R
  avg, kept +0.790R avg — see the regime-router section above). The
  thinness reflects genuine selectivity working as intended on an
  already-narrow, low-edge legacy strategy, not reckless stacking.
- **Swappy 3C**'s thinness is intrinsic to its own pattern definition (two
  candles at 70-80% body with a higher-low/lower-high plus a failed
  pullback, all in the same 3-bar window) — a rare shape by construction,
  predating this session. Its liquidity-confluence and (new, this pass)
  premium/discount/OTE additions are pure strength bonuses that never gate
  `confirmed` — the regime gate was tried here too and reverted specifically
  because it hurt Swappy (see the regime-router section). No evidence this
  session's work made Swappy any thinner than its base pattern already was.
- **Real caveat found in this audit, worth stating plainly**: the backtest
  harness doesn't replicate every live-only gate for either strategy — the
  overextension filter, the EMA-momentum-flat check, and (per
  `_adapt_swappy_3c`'s own docstring) Swappy's near-support/resistance
  location filter and stateful 3rd-time re-entry rule all exist live but
  aren't exercised in the backtest adapters at all. So live frequency for
  these two is likely *lower* than the backtest numbers above, not higher
  — the backtest is, if anything, an optimistic frequency estimate for
  them, not a pessimistic one.
- **Bot-level total**: SSM + Swappy + EMA alone sum to ~1.84 trades/day,
  dominated by SSM (PF 1.71-1.77 across runs) — a healthy scalping cadence
  at the bot level even though EMA Scalp Cross specifically has become a
  rare, high-conviction add-on rather than a primary generator.
- **intraday.py** (the swing bot) was checked the same way: its aggregate
  `INTRADAY` backtest (H4 Trend Pullback + H1 OB Retest + Balance Fade
  sub-strategies) produced 18 trades over 76 days, 1.66/week, PF 1.71,
  expectancy +0.446R — a reasonable cadence for a strategy meant to hold
  positions 2-5 days (daily new entries while still holding a multi-day
  position isn't actually the goal). Not touched further this pass.

**Conclusion drawn from the audit, before writing any wiring code**: no
evidence this session's own gates have over-filtered anything to the point
of harm — every one of them was verified with real removed-vs-kept
evidence. So Premium/Discount and OTE were wired as **soft, loosening-only
modifiers, never new hard vetoes** — directly informed by this audit, not
a generic design preference:

- **Shaakuni SSM**: `strategy_shaakuni_ssm`'s existing RR-floor logic
  (`min_rr = 1.5 if confluence['confluent'] else 2.0`) was extended to
  `min_rr = 1.5 if (confluence['confluent'] or (equilibrium is not None and
  pd_conf['favorable']) or in_ote) else 2.0` — three independent reasons,
  ORed together, any one of which is enough to earn the looser bar. Purely
  additive: nothing that passed before can now fail. Real-data result:
  133→134 trades, +0.713R→+0.717R, PF 1.71→1.72, equity +94.78R→+96.09R —
  a small, genuine improvement in the expected direction of a
  loosening-only change.
- **Swappy 3C**: a further +0.05 strength bonus (premium/discount) and
  +0.05 (OTE match), stacking on top of the existing +0.10 liquidity bonus
  — same non-blocking pattern, disclosed the same way (`strength` only
  feeds the live-only `EdgeEngine`, not backtest-visible on trade count).
  Confirmed 18→18 trades, no change, as expected for a bonus-only addition.
- **structural_swing_pro.py** (the swing bot, checked next): it already
  had its own OTE equivalent (`fib_zone`, a native D1/H4 Fibonacci
  retracement-zone entry) but no premium/discount directional read, so
  `compute_equilibrium_zone`/`premium_discount_confluence` were wired in
  there — same loosen-only pattern as SSM: a favorable read relaxes
  `MIN_RR` by 0.3 (floored at 1.0), deliberately modest given this
  strategy's own real-data trade count (3 on the 90-day sample) is too
  small for the removed-vs-kept rigor used elsewhere. Real-data result:
  3→3 trades, identical numbers — a genuine null result on this sample
  (no candidate that failed the RR floor happened to fall inside the 0.3
  loosening window), not a bug; zero tracebacks, sidedness confirmed clean
  on all 3 trades.
- **intraday.py checked and deliberately left alone**: it already
  implements both concepts natively and independently — its own
  premium/discount entry filter (`intraday.py` around the H1 pullback
  check) and its own equilibrium/Fibonacci sniper-zone logic
  (`compute_aox_fibonacci`, which literally computes `'equilibrium':
  start + span * 0.5`) — so wiring the generic `market_intelligence.py`
  versions in here would have been redundant with existing, already-
  working logic, not a genuine addition.
- **EMA Scalp Cross was deliberately left untouched** — the audit gave no
  reason to add anything to a strategy already found to be correctly,
  verifiably selective.

**Real bug found and fixed while verifying the above** (present before
this session's changes too — confirmed identical on two separate
real-data runs, so not something the premium/discount/OTE work itself
introduced): `ShaakuniSSM.find_extreme_ob()`'s OB search range
(`leg_low`/`leg_high`) is an ATR-based approximation of the swept leg, not
clamped to the sweep's own `tp_target` (the swept HTF candle's actual
high/low). On 2 of 133 real XAUUSDm trades, this let it pick an "extreme
OB" entry that was already on the wrong side of `tp_target` — a SELL
where `tp` ended up *above* entry, the same side as `sl`. The RR check
downstream (`abs(entry - tp) / sl_dist`) can't catch this because `abs()`
erases the sign, so both malformed trades passed every existing gate and
were logged as normal SL/TP exits — with a *negative* `r_multiple`
regardless of which label the backtest engine assigned, quietly corrupting
win-rate/expectancy stats for those two trades. Fixed with a direct
geometric check at the one place the real entry/sl/tp values are in hand
(`if not (sl < entry < tp): return empty` for BUY, mirrored for SELL) —
rejecting the setup outright rather than letting a backwards TP reach a
live order. Confirmed with a before/after real-data re-run: 134→132
trades (exactly the 2 flagged rows removed, nothing else touched), and
expectancy *improved* despite fewer trades (+0.717R→+0.759R, PF
1.72→1.77, equity +96.09R→+100.17R) — the direct, expected signature of
removing two genuinely bad trades. A full sidedness sweep across all 5
strategies' final ledgers (190 trades total) confirmed zero violations
remaining.

### Walk-forward validation — the finding that matters most

`--walk-forward N` (see `walk_forward.py`) splits the history into N
sequential windows and runs each independently. It exists because every
number this project had ever produced came from ONE pooled run over ONE
instrument over ONE ~90-day window, and "SSM makes +0.759R/trade" is a
materially different claim from "SSM made +0.759R/trade over 90 days of
gold in mid-2026." Only the second was ever supported.

Note what this deliberately does NOT claim to be: classic walk-forward
*optimisation* tests fitted parameters out-of-sample to detect
curve-fitting. That framing doesn't apply here and pretending otherwise
would be theatre — these strategies have no fitted parameters, their
thresholds come from the source methodology, so there is nothing to overfit
in the usual sense. What this measures is **stability**: does the edge recur
across windows, or did it come from one lucky stretch?

**The result on the real XAUUSDm data, 4 windows:**

| Window | Period | Trades | Win% | Expectancy | PF | Total R |
|---|---|---|---|---|---|---|
| W1 | 05-17 → 06-09 | 31 | 9.7% | **-0.014** | 0.99 | -0.43 |
| W2 | 06-09 → 07-01 | 34 | 23.5% | +1.189 | 2.30 | +40.43 |
| W3 | 07-01 → 07-23 | 26 | 15.4% | +0.386 | 1.39 | +10.04 |
| W4 | 07-23 → 08-14 | 41 | 19.5% | +1.223 | 2.29 | +50.13 |

And at 6 windows, which exposes more:

| Window | Trades | Expectancy | Total R |
|---|---|---|---|
| W1 | 21 | -0.257 | -5.39 |
| W2 | 24 | +0.359 | +8.61 |
| W3 | 20 | +1.839 | +36.77 |
| W4 | 16 | **-0.911** | **-14.57** |
| W5 | 19 | +1.368 | +26.00 |
| W6 | 32 | +1.523 | +48.75 |

**What this establishes, stated plainly:**

1. **The pooled +100.17R was concentrated, not steady.** At 4 windows,
   ~90R of it came from two windows and W1 was flat. At 6 windows there is a
   **-14.57R window** that the single pooled number hid completely. Per-window
   expectancy ranges from -0.911R to +1.839R (stdev 1.099R) — that is not the
   profile of a stable edge, it's the profile of a strategy whose result
   depends heavily on which stretch of market you happened to measure.
2. **It is not yet statistically distinguishable from luck.** Pooled
   t-statistic on per-trade R is **+1.70 at n=132** — below the |t| ≥ 2 rule
   of thumb, and identical at both window counts (as it should be; it's a
   trade-level statistic). Indicative only, since trade returns are neither
   normal nor fully independent, but the direction of the answer is clear.
3. **Swappy 3C (t=+0.51, n=18) and EMA Scalp Cross (t=+1.07, n=5) are
   nowhere near interpretable.** Swappy was profitable in 2 of 4 windows with
   expectancy swinging -1.017R to +1.383R. EMA Scalp Cross produced 5 trades
   in 90 days total, including a window with none at all. `--min-trades`
   flags these as "(thin)" rather than averaging them in silently.

**The honest conclusion**: the strategies are not broken — expectancy is
positive overall and the mechanics are verified — but this data does not yet
support a claim of consistent profitability, and nobody should present it as
if it does. What's needed is more data (multiple instruments, multiple years,
a bear/crisis regime), not more strategies or more filters. This tool is what
to run on that data when it exists, and in the meantime it states honestly
how little can be concluded.

`--min-trades N` (default 10) flags windows too thin to interpret. Windows
carry 250 bars of warm-up history before their first counted trade, so the
200 EMA / volume-profile / swing-structure reads are real rather than
cold-start artefacts, while trades are only counted from inside the window.

### Decision journals — and what they found on the first run

Requested directly: the bot should record every reason it identified when
taking a trade, the way a discretionary trader writes up their case, plus
why each trade ended the way it did — so that R&D can find out where the bot
is actually going wrong instead of guessing.

`python_scripts/decision_journal.py` (22 unit tests) records three phases per
trade: **entry** (every check that ran, with a verdict — `CONFIRMED`, `WEAK`,
`NEUTRAL`, `AGAINST`, `VETO` — so disagreements are recorded, not just the
checks that fired), **management** (break-even moves, partials, trailing,
each with its trigger), and **exit** with an *attributed cause*.

`backtest/engine.py`'s new `attribute_exit()` is the piece that makes losses
diagnosable. "SL" is not a reason. It looks forward past the exit (post-hoc
only — never feeds a trading decision) and separates:

- `swept_then_resumed` — the stop was hit, then price reached the original
  target anyway. **A stop-placement problem.**
- `partial_recovery` — price came back past entry but never reached target.
- `thesis_invalidated` — price kept going against us. **A direction problem.**

`backtest/analyze_journal.py` then mines a ledger. Journals are produced by
the backtest as well as live, which matters enormously: it means the 132
existing SSM trades became an analyzable dataset immediately instead of
waiting months for live ones.

**What the first real run found (XAUUSDm, 132 SSM trades):**

| Confirmation | Present | Avg R | Absent | Avg R | Edge |
|---|---|---|---|---|---|
| liquidity_confluence | 10 | +1.523 | 122 | +0.696 | **+0.827** |
| premium_discount | 51 | +0.145 | 81 | +1.146 | **-1.001** |
| ote_zone | 12 | -0.202 | 120 | +0.855 | **-1.057** |

Premium/discount and OTE — both added earlier in this same session — read as
strongly **anti-correlated** with trade quality for SSM. Before treating that
as a verdict, two candidate explanations were tested against the data:

1. *Selection effect from the RR floor?* Partly present but insufficient: the
   objection trades did face a stricter floor on average (min_rr 1.89 vs 1.50),
   but the favorable-PD trades had **higher** average RR (15.89 vs 12.56) and
   still performed far worse. The confound does not explain it away.
2. *The real mechanism.* SSM's take-profit is a fixed far-away level (the
   swept candle's extreme), so RR is largely a proxy for **how far the target
   is** — and win rate collapses with distance:

| RR band | Trades | Win rate | Avg R |
|---|---|---|---|
| 0–5x | 18 | 22.2% | **-0.376** |
| 5–10x | 35 | 25.7% | +0.956 |
| 10–20x | 54 | 16.7% | +1.260 |
| 20x+ | 25 | **4.0%** | +0.217 |

A deeper discount sits further from the swept extreme, so "favorable
premium/discount" for SSM is measuring target distance, not entry quality.
That is why it reads backwards.

**And the coherent headline finding**, from the loss attribution:

| Attributed cause | Trades | Total R |
|---|---|---|
| partial_recovery | 66 | -77.86 |
| swept_then_resumed | 26 | -31.40 |
| thesis_invalidated | 17 | -20.18 |
| target_hit | 23 | +229.61 |

**92 of 109 losses were trades where price moved back in our favour but never
reached the target. Only 17 were genuinely wrong about direction.** SSM's
problem is not its bias logic or its entries — it is that its take-profit is
too far away.

**Deliberately NOT acted on yet, and this is the disciplined part.** The
obvious move is to cap RR or pull targets nearer. But walk-forward already
established that 132 trades on one instrument over one window cannot
distinguish this strategy's edge from luck; slicing that same sample into RR
bands makes each band weaker still (n=25 for the 20x+ band). Shipping a
target change fitted to these bands would be textbook curve-fitting to one
quarter of gold — the exact mistake this harness exists to prevent. The
finding is recorded as a hypothesis with a clear test: re-run this analysis
on more instruments and more history, and if the pattern holds there, then
change the targets.

### Journaling extended to Swappy 3C, EMA Scalp Cross and AOX

Same instrumentation as SSM, now across every live strategy in the scalping
bot. Coverage verified on real data: 132/132 SSM, 18/18 Swappy, 5/5 EMA
Scalp journalled, with results byte-identical to before (no behavioural
change). AOX is journalled per layer (`AOX_L1_SD_TAP`, `AOX_L2_TURTLE`,
`AOX_L3_HIPPO`) — deliberately valuable there because AOX is the one live
strategy that has **never been backtested**, so when M1 history finally
arrives every AOX decision will already explain itself.

**Two real bugs the analyzer caught by being pointed at its own output:**

1. **numpy scalars broke serialization.** `np.float64` values serialize as
   `np.float64(23.08)` — neither valid JSON nor parseable by
   `ast.literal_eval`. EMA Scalp journals were being *written* but silently
   failed to *load*. Worse, the live path writes journals into a Supabase
   **JSONB** column and `np.float64` is not JSON-serializable at all, so this
   would have raised on the first real EMA trade in production. Fixed at the
   source with a `_plain()` coercion in `decision_journal.py` — and note the
   subtlety that made the first fix insufficient: **`np.float64` subclasses
   Python `float`**, so an `isinstance(v, float)` shortcut passes it straight
   through. It needs an exact-type check. One more leak lived in
   `engine.py`, which builds the exit dict directly and so bypassed the
   journal's own coercion.

2. **Direction-specific key names faked an edge.** Swappy's journal used
   `higher_low` for BUY and `lower_high` for SELL, and `c3_above_mid` /
   `c3_below_mid` likewise. Those are the *same concept* per direction, so
   they became BUY/SELL proxies — and the analyzer duly reported a
   confident-looking ±0.333R "edge" for them that was really just "SELLs
   outperformed BUYs in this window." Fixed to one shared key per concept,
   with direction recorded separately; the spurious edges correctly collapsed
   to "no contrast" afterwards. A new **directional split** section was added
   to the analyzer so the asymmetry it was masking is visible on purpose
   rather than by accident.

**Two structural findings about the strategies themselves:**

- **EMA Scalp Cross cannot learn from its taken trades.** All eight of its
  confirmations report "no contrast" — because every one of them is a *hard
  veto*, so every surviving trade has all of them by construction.
  Confirmation-edge analysis is uninformative for an all-mandatory-gate
  strategy. The only way to learn about it is to journal the **rejected**
  setups (which gate rejected how many, and what those rejected setups would
  have done). That is the clear next step for this strategy specifically,
  and is noted rather than half-built.

- **EMA Scalp Cross never actually traded a cross.** All 5 trades in the
  window fired via the `ema9_bounce` variant — not one hard 9/25 cross, not
  one near-cross. The strategy is named for, and documented as, a crossover
  system, and in practice it is trading 9-EMA bounces. Worth knowing before
  anyone tunes "the cross".

- **Swappy's premium/discount reads anti-correlated too** (-0.285R edge,
  n=6 vs 12), the same direction as SSM's much larger sample. Consistent
  story across two strategies now, though still one instrument and one
  window — the same caveat as everything else here.

### Rejection journaling — where setups actually die

Journaling the trades we take only tells half the story. `--rejections-out
PATH` now also records every setup a strategy **evaluated and declined**, so
"which of our filters actually does the rejecting" is a number instead of an
assumption.

**Design constraint worth stating**, because it drove the implementation:
every strategy signals "no trade" by returning a falsy value, and every
caller branches on exactly that. Returning the rejection journal would make
those returns *truthy* and a declined setup would be executed as a trade.
So rejections go through a side-channel sink (`decision_journal.record_
rejection` / `drain_rejections`) and return values are byte-for-byte
unchanged. **Instrumentation must never be able to place an order.** The sink
is also bounded (`_MAX_REJECTIONS`) because the scan loop evaluates every
symbol on every bar — unbounded it would be a slow memory leak in a
long-running live bot — and truncation is reported rather than hidden.

**First run: 19,662 declined setups, and the decisive gate for each.**

| Strategy | Declined | Decisive gate |
|---|---|---|
| SHAAKUNI_SSM | 7,023 | `extreme_ob` 64.0% · `htf_sweep` 35.0% · `premium_discount` 0.8% · `rr_floor` 0.2% |
| SWAPPY_3C | 10,383 | `c1_trend_candle` **94.8%** · `c2_continuation` 5.2% |
| EMA_SCALP_CROSS | 2,256 | `wm_hs_pattern` 56.2% · `cross_valid` 19.4% · `ema_separation` 15.0% · `ema200_trend_gate` 4.9% · `liquidity_confluence` 4.6% |

Three things fall straight out of that table:

1. **SSM's RR floor and premium/discount checks are nearly inert as gates** —
   together they decide only 1% of rejections. All the earlier analysis of
   whether premium/discount "earns its place" was measuring a check that
   barely rejects anything; its real effect is on the RR *bar*, not on
   admission.
2. **Swappy dies almost entirely on its very first condition** — 94.8% of
   10,383 rejections never get past C1. That single check explains the
   strategy's ~0.23 trades/day, not the later filters.
3. **EMA Scalp's own liquidity-confluence veto** (added earlier this session)
   decides only 4.6% of its rejections; the W/M/H&S pattern pre-filter does
   most of the work.

**The Swappy C1 finding, investigated rather than assumed.** C1 requires
`0.70 <= body_pct <= 0.80` — an upper *and* lower bound. Instrumenting the
rejection with the actual body percentage showed:

| C1 rejection cause | Count | Share |
|---|---|---|
| body < 70% (too weak — correct rejection) | 8,474 | 90.7% |
| body > 80% (**too strong** — discarded) | 867 | 9.3% |

A candle with a >80% body has almost no wick: it is a *stronger* trend candle
than one at 75%, and the strategy currently throws it away. That looks like a
design oddity rather than an intention.

Measured, as an experiment (upper bound relaxed to 1.00, then **reverted**):

| | Trades | Win rate | Expectancy | PF | Equity |
|---|---|---|---|---|---|
| Baseline (0.70–0.80) | 18 | 33.3% | +0.223R | 1.33 | +4.01R |
| Relaxed (0.70–1.00) | 40 | 35.0% | +0.184R | 1.29 | **+7.37R** |

Removed-vs-kept on the newly admitted setups: **22 trades, +3.35R total,
+0.152R average** — genuinely profitable, but weaker than the +0.223R the
strategy already takes. So relaxing the band roughly doubles total profit
while diluting per-trade quality. That is a judgment call about whether this
bot wants frequency or selectivity, not an obvious bug fix, and it rests on
22 new trades from one instrument in one window. **Left reverted**, recorded
here with the numbers, for a deliberate decision rather than a silent one.

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
