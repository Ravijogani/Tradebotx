"""
One adapter per strategy the backtest harness can drive, each calling the
real function from the imported bot module with the exact arguments the
live pipeline uses (window sizes, timeframe roles) -- see each adapter's
comment for the live call site it mirrors.

Deliberately one explicit adapter function per strategy rather than a
single "generic" dispatcher: these functions have genuinely different
signatures (some take df_structure/df_micro, some don't; some take
`symbol`, some don't; Shaakuni is a limit order with its own TP, everything
else is a market order sized off SL distance). A clever generic dispatcher
risks silently passing the wrong argument to the wrong function; explicit
adapters make each one's contract checkable at a glance.

LIVE vs NOT LIVE, and why some strategies aren't here at all
--------------------------------------------------------------
Grepping the whole bot file for call sites (not just `def`s) found that
only some of the strategy-shaped code in this file is ever actually
invoked from the live trading loop.

  LIVE right now (has a real call site in the file):
    - strategy_liquidity_fvg_engine()   ("STRATEGY C" / SSM FVG retest)
    - strategy_shaakuni_ssm()           ("SHAAKUNI SSM")
    - strategy_liquidity_grab()         (fallback)
    - strategy_ict_killzone()           (fallback)
    - strategy_ema_scalp_cross()        ("STRATEGY A" -- extracted from a
                                          ~90-line inline block in the main
                                          loop specifically so it could be
                                          wired in here; see its own
                                          docstring for the real bugs found
                                          during that extraction and the
                                          first real-data backtest)
    - detect_swappy_3c()                ("STRATEGY B" -- see its adapter's
                                          docstring for what's still
                                          excluded vs the full live path)

  NOTE on "live" vs "enabled": per an explicit decision to run the live
  cascade on only four setups (Shaakuni SSM, Swappy 3C, AOX, EMA scalp),
  STRATEGY C (SMC FVG retest) and both generic fallbacks are gated off by
  default via config.ENABLE_STRATEGY_* flags in AITradingConfig -- their
  call sites still exist (so `live=True` here is still accurate in the
  sense that flipping a flag re-enables them immediately), but they don't
  fire in the current default configuration. Test SMC_FVG_OB_RETEST/
  ICT_KILLZONE/LIQUIDITY_GRAB here if you're deciding whether to
  re-enable any of them; don't read their presence as "this is what the
  bot trades today."

  REMOVED 2026-08 (were never live, and were fully removed rather than
  kept dormant, after real-data backtest evidence -- see
  python_scripts/backtest/README.md's "Dormant strategies removed"
  section for the full numbers and reasoning): EntryEngine.evaluate_setup,
  strategy_advanced_smc, strategy_wyckoff_patterns, strategy_volume_profile,
  strategy_support_resistance, strategy_volume_imbalance,
  strategy_trend_pullback, strategy_mean_reversion_bb. If any of these
  needs to be revisited, recover it from git history (search this repo's
  log for "strategies_research.py" or "Quarantine dormant strategies") --
  don't rewrite from scratch.

  NOT a StrategyAdapter here, on purpose (but IS wired -- see aox_driver.py):
    - "STRATEGY D" / AOX. run_aox_layered_entry() was split into
      detect_aox_phase_signal() (pure decision logic, no order placement)
      + a thin execution wrapper, specifically so it could be backtested.
      It's still not one of the adapters in this file, because AOX's phase
      state persists across many bar-closes and its layers can overlap in
      time (Layer 2 can fire while Layer 1's trade is still open) --
      StrategyAdapter's single-bar, single-trade-at-a-time contract (built
      for every other strategy here) can't express that. See aox_driver.py
      for the dedicated stateful driver and run_backtest.py's --strategy
      AOX / --all for how to run it.
    - The live STRATEGY B additionally applies a location filter (near
      M5 support/resistance) and a stateful "3rd-time re-entry rule"
      (can_take_swappy_entry) on top of detect_swappy_3c()'s pattern
      match. Only the pure pattern-detection part is wired here -- see
      that adapter's docstring.
"""

from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from .data import HistoricalDataset
from .replay_data import replay_context


@dataclass
class StrategyResult:
    direction: str                    # "BUY" | "SELL"
    stop_loss: float
    reason: str
    confidence: float = 0.0
    order_type: str = "MARKET"        # "MARKET" | "LIMIT"
    limit_entry: Optional[float] = None
    take_profit: Optional[float] = None  # set only if the strategy computes its own (e.g. Shaakuni)
    entry_price: Optional[float] = None  # set only if the strategy computes a specific entry
                                          # level; otherwise the engine fills at the current
                                          # bar's close, matching how the live fallback
                                          # strategies enter at market.
    edge_score: Optional[float] = None
    edge_state: Optional[str] = None


@dataclass
class StrategyAdapter:
    name: str
    live: bool  # reachable from the real trading loop today?
    call: Callable  # (bot, dataset, as_of, symbol) -> Optional[StrategyResult]


def _get_trend(bot, dataset: HistoricalDataset, as_of, symbol: str) -> Optional[str]:
    """
    Replicates the live main loop's actual `effective_trend` computation:
    H4 macro bias (get_h4_macro_bias) leads, H1 trend (strict EMA50/EMA200
    stacking, not a simple cross) confirms, a real H4-vs-H1 conflict skips
    entirely, and only if both are NEUTRAL does live fall back to an
    AI/L1 bias cache this harness has no equivalent for (see below).

    BUG FIX (2026-08, found while running the first real-data backtest):
    this function used to call bot.get_market_regime_and_trend(symbol) --
    which turns out to have ZERO call sites anywhere in the live file
    (confirmed by grepping, not guessed) and is separately broken on any
    real dataset anyway (`config.ADX_PERIOD` / `config.ADX_TRENDING_
    THRESHOLD` don't exist on AITradingConfig -- an AttributeError on
    every call once enough TREND_TF history exists, silently swallowed by
    this function's own try/except into `trend = None`). Every adapter
    that gates on `trend is None` was therefore getting rejected almost
    always on real data, regardless of what the real strategies would
    have done. The first real backtest run (XAUUSDm, 90 days) showed all
    four live strategies at exactly 0 trades; this was the actual reason,
    not the strategies genuinely never firing. Corrected to replicate
    effective_trend's real computation (see hybrid_trading_bot_multiuser.py,
    "STEP 1: TOP-DOWN HIERARCHY", right before STRATEGY A) instead.

    Known, disclosed gap (not fixed, can't be from historical data alone):
    live's NEUTRAL/NEUTRAL fallback reads state.approved_bias, an AI(L1)-
    computed bias cache that only exists as live in-memory state -- there
    is no historical record of what it would have said on a given past
    bar. This function returns None in that case (same as "no trend
    available"), which under-counts trades relative to live specifically
    in the cases where that fallback would have supplied a direction H4/H1
    alone don't agree on. That's a real, disclosed limitation of backtesting
    this cascade from OHLC history alone, not a bug to silently paper over.
    """
    df_h4 = dataset.window("H4", as_of, 60) if "H4" in dataset.frames else None
    h4_bias = bot.get_h4_macro_bias(df_h4) if df_h4 is not None and len(df_h4) >= 55 else "NEUTRAL"

    df_h1 = dataset.window("H1", as_of, 100)
    try:
        ema50_h1 = df_h1['close'].ewm(span=50, adjust=False).mean().iloc[-1]
        ema200_h1 = df_h1['close'].ewm(span=200, adjust=False).mean().iloc[-1]
        close_h1 = df_h1['close'].iloc[-1]
        if close_h1 > ema50_h1 > ema200_h1:
            h1_trend = "BULLISH"
        elif close_h1 < ema50_h1 < ema200_h1:
            h1_trend = "BEARISH"
        else:
            h1_trend = "NEUTRAL"
    except Exception:
        h1_trend = "NEUTRAL"

    if h4_bias != "NEUTRAL" and h1_trend != "NEUTRAL" and h4_bias != h1_trend:
        return None  # live does `continue` here -- confirmed conflict, no trend this bar

    effective_trend = h4_bias if h4_bias != "NEUTRAL" else h1_trend
    if effective_trend == "NEUTRAL":
        return None  # live falls back to state.approved_bias -- see docstring above
    return effective_trend


def _adapt_ict_killzone(bot, dataset: HistoricalDataset, as_of, symbol):
    # Live call site: strategy_ict_killzone(df_m5, df_h1, h1_trend, symbol, df_m1)
    with replay_context(bot, dataset, as_of):
        trend = _get_trend(bot, dataset, as_of, symbol)
        if trend is None:
            return None
        df_m5 = dataset.window("M5", as_of, 60)
        df_h1 = dataset.window("H1", as_of, 100)
        df_m1 = dataset.window("M1", as_of, 30)
        if len(df_m5) < 20 or len(df_h1) < 55 or len(df_m1) < 12:
            return None
        r = bot.strategy_ict_killzone(df_m5, df_h1, trend, symbol, df_m1)
    if not r:
        return None
    return StrategyResult(direction=r["direction"], stop_loss=r["stop_loss"],
                           reason=r.get("strategy_name", "ICT_KILLZONE"),
                           confidence=r.get("confidence", 0.0))


def _adapt_liquidity_grab(bot, dataset: HistoricalDataset, as_of, symbol):
    # Live call site: strategy_liquidity_grab(df_m5, df_h1, h1_trend, symbol, df_m1)
    with replay_context(bot, dataset, as_of):
        trend = _get_trend(bot, dataset, as_of, symbol)
        if trend is None:
            return None
        df_m5 = dataset.window("M5", as_of, 60)
        df_h1 = dataset.window("H1", as_of, 100)
        df_m1 = dataset.window("M1", as_of, 30)
        if len(df_m5) < 15 or len(df_h1) < 20 or len(df_m1) < 5:
            return None
        r = bot.strategy_liquidity_grab(df_m5, df_h1, trend, symbol, df_m1)
    if not r:
        return None
    return StrategyResult(direction=r["direction"], stop_loss=r["stop_loss"],
                           reason=r.get("strategy_name", "LIQUIDITY_GRAB"),
                           confidence=r.get("confidence", 0.0))


def _adapt_liquidity_fvg_engine(bot, dataset: HistoricalDataset, as_of, symbol):
    # Live call site: strategy_liquidity_fvg_engine(symbol, df_m5, df_h1,
    #   effective_trend, edge_mode="NORMAL", df_m15=df_m15, df_h1=df_h1)
    with replay_context(bot, dataset, as_of):
        trend = _get_trend(bot, dataset, as_of, symbol)
        if trend is None:
            return None
        df_m5 = dataset.window("M5", as_of, 60)
        df_h1 = dataset.window("H1", as_of, 100)
        df_m15 = dataset.frames.get("M15")
        df_m15_w = dataset.window("M15", as_of, 150) if df_m15 is not None else None
        if len(df_m5) < 25:
            return None
        r = bot.strategy_liquidity_fvg_engine(symbol, df_m5, df_h1, trend,
                                               edge_mode="NORMAL", df_m15=df_m15_w, df_h1=df_h1)
    if not r:
        return None
    return StrategyResult(direction=r["direction"], stop_loss=r["stop_loss"],
                           reason=r.get("strategy_name", "SMC_FVG_OB_RETEST"),
                           confidence=r.get("confidence", 0.0))


def _adapt_shaakuni_ssm(bot, dataset: HistoricalDataset, as_of, symbol):
    # Live call site: strategy_shaakuni_ssm(symbol, df_h1, df_h4, df_m5, effective_trend)
    if "H4" not in dataset.frames:
        return None  # needs H4 -- see export_mt5_history.py / README
    with replay_context(bot, dataset, as_of):
        trend = _get_trend(bot, dataset, as_of, symbol)
        if trend is None:
            return None
        df_h1 = dataset.window("H1", as_of, 60)
        df_h4 = dataset.window("H4", as_of, 60)
        df_m5 = dataset.window("M5", as_of, 60)
        if len(df_m5) < 10:
            return None
        r = bot.strategy_shaakuni_ssm(symbol, df_h1, df_h4, df_m5, trend)
    if not r:
        return None
    return StrategyResult(direction=r["signal"], stop_loss=r["stop_loss"],
                           reason=r.get("reason", "SHAAKUNI_SSM"),
                           order_type="LIMIT", limit_entry=r.get("limit_entry"),
                           take_profit=r.get("tp"))


def _adapt_swappy_3c(bot, dataset: HistoricalDataset, as_of, symbol):
    """
    Matches the live entry mechanics after the fix (see hybrid_trading_bot_
    multiuser.py's STRATEGY B and place_swappy_pending_order): a stop
    entry at _sw['stop_entry'] (above/below the 3-candle high/low), not a
    market fill at candle 3's close, and 3:1 reward:risk TP -- both taken
    directly from place_swappy_pending_order's own logic, the function
    this adapter is meant to mirror.

    Still excludes two things the live cascade additionally applies on
    top of detect_swappy_3c: the near-support/resistance location filter,
    and the stateful "3rd-time re-entry rule" (can_take_swappy_entry) --
    both depend on cross-call state that would need careful, deliberate
    handling to replay correctly (symbol-scoped level history across the
    whole backtest run), not a quick addition. So this measures "how does
    the pattern + real entry/exit mechanics perform," not the complete
    live filter stack.

    order_type="LIMIT" here reuses the engine's existing "wait for price
    to touch this level" fill simulation -- that mechanic is identical for
    a limit order and a stop order (only which side price approaches
    from differs, and the engine's touch check is direction-agnostic).
    """
    with replay_context(bot, dataset, as_of):
        trend = _get_trend(bot, dataset, as_of, symbol)
        if trend not in ("BULLISH", "BEARISH"):
            return None
        direction = "BUY" if trend == "BULLISH" else "SELL"
        df_m5 = dataset.window("M5", as_of, 30)
        if len(df_m5) < 20:
            return None
        sw = bot.detect_swappy_3c(df_m5, direction)
        if not sw.get("confirmed"):
            return None
        atr_m5 = float(bot.calculate_atr(df_m5['high'], df_m5['low'], df_m5['close'], 14).iloc[-1])
        scan = df_m5.iloc[-15:]
        sl = float(scan['low'].min()) - atr_m5 * 0.3 if direction == "BUY" else float(scan['high'].max()) + atr_m5 * 0.3
        stop_entry = sw['stop_entry']
        sl_dist = abs(stop_entry - sl)
        if sl_dist <= 0:
            return None
        tp = stop_entry + sl_dist * 3.0 if direction == "BUY" else stop_entry - sl_dist * 3.0
    return StrategyResult(direction=direction, stop_loss=sl,
                           reason=f"SWAPPY_3C_{sw['pattern']}",
                           confidence=sw.get("strength", 0.0),
                           order_type="LIMIT", limit_entry=stop_entry, take_profit=tp)


def _adapt_ema_scalp_cross(bot, dataset: HistoricalDataset, as_of, symbol):
    """
    STRATEGY A, now backtestable since strategy_ema_scalp_cross() was
    extracted from the main loop into a standalone function. Mirrors the
    live call site exactly: df_m5 + the H4-aligned bias direction.

    BUG FIX (2026-08, found from the first real-data run -- XAUUSDm,
    90 days, 223 EMA_SCALP_CROSS trades, 0.4% win rate, every "TP" exit
    was actually a loss): this used to pass the setup dict's 'ema50_tp'
    straight through as StrategyResult.take_profit. That field is always
    on the WRONG side of entry by construction -- the cross-validity gate
    in strategy_ema_scalp_cross() requires _cur_price > _e50 for a BUY
    signal (and < for SELL), so a TP set to _e50 is always below entry
    for BUY / above entry for SELL, i.e. a guaranteed-loss target, not a
    take-profit. This is real in the live bot's own strategy function too
    -- but it does NOT actually reach a real order live: get_dynamic_
    trade_params()'s ema50_tp_hint handling (search that name) only
    applies the 50 EMA as TP if `ema50_tp_hint > entry_price` for BUY /
    `< entry_price` for SELL AND it clears a 1.2:1 RR minimum -- a
    condition this value can never satisfy, so live silently and
    permanently falls back to its own structural swing-based TP1
    (computed earlier in that same large, tick/account-dependent
    function) instead. The "50 EMA is the primary TP" feature this
    strategy's docstring/doc-spec describes is therefore 100% inert in
    live, not just in this harness -- worth knowing on its own, separate
    from the harness bug. (Corrects an earlier, wrong claim in this
    repo's README that this wiring was "verified already correctly
    wired" -- it reaches the parameter, but the geometry means it can
    never actually activate; that's a materially different, weaker claim
    than "wired and working.")

    Fix here: don't pass the broken value through at all. get_dynamic_
    trade_params()'s real fallback (structural swing TP1, hard-minimum
    1.2:1 RR, auto-adjusted to 1.5x SL if below that) needs a live tick
    and account_info() to compute entry price and risk caps -- there's no
    honest historical equivalent to replay it exactly. Falling back to
    the engine's generic --rr multiple (same as every other fallback-style
    adapter here that doesn't set its own take_profit, e.g. ICT_KILLZONE/
    LIQUIDITY_GRAB) is a disclosed approximation of live's real RR-gated
    TP, not a byte-exact replication -- but it's a real target on the
    correct side of entry, which is what matters most: the prior behavior
    wasn't an approximation of anything, it was unconditionally wrong.
    """
    with replay_context(bot, dataset, as_of):
        trend = _get_trend(bot, dataset, as_of, symbol)
        if trend not in ("BULLISH", "BEARISH"):
            return None
        direction = "BUY" if trend == "BULLISH" else "SELL"
        df_m5 = dataset.window("M5", as_of, 210)  # 200 EMA needs real history to be stable
        if len(df_m5) < 60:
            return None
        r = bot.strategy_ema_scalp_cross(df_m5, direction, symbol)
    if not r:
        return None
    return StrategyResult(direction=r["signal"], stop_loss=r["stop_loss"],
                           reason=r.get("reason", "EMA_SCALP_CROSS"))


STRATEGIES_LIVE = [
    StrategyAdapter("ICT_KILLZONE", True, _adapt_ict_killzone),
    StrategyAdapter("LIQUIDITY_GRAB", True, _adapt_liquidity_grab),
    StrategyAdapter("SMC_FVG_OB_RETEST", True, _adapt_liquidity_fvg_engine),
    StrategyAdapter("SHAAKUNI_SSM", True, _adapt_shaakuni_ssm),
    StrategyAdapter("SWAPPY_3C", True, _adapt_swappy_3c),
    StrategyAdapter("EMA_SCALP_CROSS", True, _adapt_ema_scalp_cross),
]

ALL_STRATEGIES = STRATEGIES_LIVE
STRATEGIES_BY_NAME = {s.name: s for s in ALL_STRATEGIES}
