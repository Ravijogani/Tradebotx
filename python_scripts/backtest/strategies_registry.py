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
invoked from the live trading loop. This corrects something the v1
harness got wrong: EntryEngine.evaluate_setup() -- the class whose own
docstring calls it the "Deterministic SMC Entry Engine" -- is NEVER
instantiated anywhere in the file. `EdgeEngine` (which v1 correctly
identified as live, called at two real call sites) scores whichever setup
the ACTUAL live cascade below produced, not EntryEngine's output. v1's
backtest was validating a fully-built, carefully-documented, but
completely dead class. It's moved to STRATEGIES_DORMANT here.

  LIVE right now (has a real call site in the file):
    - strategy_liquidity_fvg_engine()   ("STRATEGY C" / SSM FVG retest)
    - strategy_shaakuni_ssm()           ("SHAAKUNI SSM")
    - strategy_liquidity_grab()         (fallback)
    - strategy_ict_killzone()           (fallback)
    - detect_swappy_3c()                ("STRATEGY B" -- see its adapter's
                                          docstring for what's still
                                          excluded vs the full live path)

  NOTE on "live" vs "enabled": per an explicit decision to run the live
  cascade on only three setups (Shaakuni SSM, Swappy 3C, AOX), STRATEGY A
  (EMA scalp), STRATEGY C (SMC FVG retest), and both generic fallbacks are
  now gated off by default via config.ENABLE_STRATEGY_* flags in
  AITradingConfig -- their call sites still exist (so `live=True` here is
  still accurate in the sense that flipping a flag re-enables them
  immediately), but they don't fire in the current default configuration.
  Test SMC_FVG_OB_RETEST/ICT_KILLZONE/LIQUIDITY_GRAB here if you're
  deciding whether to re-enable any of them; don't read their presence as
  "this is what the bot trades today."

  Defined, fully implemented, but NEVER CALLED anywhere in the file:
    - EntryEngine.evaluate_setup (see correction above)
    - strategy_advanced_smc
    - strategy_wyckoff_patterns
    - strategy_volume_profile
    - strategy_support_resistance
    - strategy_volume_imbalance
    - strategy_trend_pullback
    - strategy_mean_reversion_bb
  These are wired here too (STRATEGIES_DORMANT below) so they can be
  evaluated -- but their `live=False` flag means the report should label
  them clearly as "not currently reachable by the live bot," not blend
  their numbers in with strategies that actually trade real money today.

  NOT wired at all, on purpose:
    - "STRATEGY A" (EMA_SCALP_CROSS) is ~90 lines fully inline in the main
      trading loop (no standalone function exists to call) -- extracting
      it cleanly is a real refactor, not a quick adapter, and doing it
      blind (untestable end-to-end on this machine -- no MT5/Windows here)
      risks a subtle behavior change in a strategy that IS live. Left as a
      deliberate follow-up.
    - "STRATEGY D" (run_aox_layered_entry) manages its own multi-call phase
      state machine and appears to place real orders itself (returns bool,
      not a signal dict) -- it's an execution engine, not a pure signal
      generator, and needs either a refactor to separate signal-generation
      from order-placement, or a materially different backtest approach
      (capturing order *intent* instead of simulating fills the way this
      engine does). Also left as a follow-up, not faked here.
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
                                          # level (e.g. EntryEngine's FVG midpoint); otherwise
                                          # the engine fills at the current bar's close, matching
                                          # how the live fallback strategies enter at market.
    edge_score: Optional[float] = None   # set only for the EdgeEngine-scored path (EntryEngine)
    edge_state: Optional[str] = None


@dataclass
class StrategyAdapter:
    name: str
    live: bool  # reachable from the real trading loop today?
    call: Callable  # (bot, dataset, as_of, symbol) -> Optional[StrategyResult]


def _get_trend(bot, symbol: str) -> Optional[str]:
    """get_market_regime_and_trend must be called inside a replay_context
    block (it internally calls the now-patched get_market_data)."""
    try:
        _, trend = bot.get_market_regime_and_trend(symbol)
        return trend
    except Exception:
        return None


# ---------------------------------------------------------------------
# LIVE strategies
# ---------------------------------------------------------------------

def _adapt_entry_engine(bot, dataset: HistoricalDataset, as_of, symbol):
    """
    NOT LIVE -- see this module's docstring. EntryEngine is never
    instantiated anywhere in the bot file; kept here (in
    STRATEGIES_DORMANT) because it's cleanly self-contained and its score
    components are genuinely derived from the setup's measured
    liquidity/momentum/structure quality (unlike the fixed per-strategy-
    type constants the live cascade assigns for its fallback strategies),
    which makes it worth evaluating on its own methodological merits even
    though it doesn't trade a single live order today.
    """
    df_h1 = dataset.window("H1", as_of, 100)
    df_m5 = dataset.window("M5", as_of, 60)
    df_m1 = dataset.window("M1", as_of, 30)
    if len(df_h1) < 55 or len(df_m5) < 20 or len(df_m1) < 12:
        return None

    entry_engine = bot.EntryEngine()
    with replay_context(bot, dataset, as_of):
        setup = entry_engine.evaluate_setup(df_h1, df_m5, df_m1)
    if setup is None:
        return None

    ctx = bot.TradeContext(
        liquidity_distance=setup["liquidity_distance"],
        liquidity_strength=setup["liquidity_strength"],
        momentum_state=setup["momentum_state"],
        structure_alignment=setup["structure_alignment"],
        session_strength=0.7,   # see README "Known limitations" -- not yet session-aware
        volatility_state=0.7,
    )
    edge = bot.EdgeEngine().calculate(ctx)
    if not edge.allow_entry:
        return None

    return StrategyResult(
        direction=setup["signal"], stop_loss=setup["stop_loss"],
        reason=setup["reason"], entry_price=setup["entry_price"],
        edge_score=edge.score, edge_state=edge.state,
    )


def _adapt_ict_killzone(bot, dataset: HistoricalDataset, as_of, symbol):
    # Live call site: strategy_ict_killzone(df_m5, df_h1, h1_trend, symbol, df_m1)
    with replay_context(bot, dataset, as_of):
        trend = _get_trend(bot, symbol)
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
        trend = _get_trend(bot, symbol)
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
        trend = _get_trend(bot, symbol)
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
        trend = _get_trend(bot, symbol)
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
        trend = _get_trend(bot, symbol)
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


# ---------------------------------------------------------------------
# DORMANT strategies (fully implemented, not called anywhere live today)
# ---------------------------------------------------------------------

def _adapt_advanced_smc(bot, dataset, as_of, symbol):
    with replay_context(bot, dataset, as_of):
        trend = _get_trend(bot, symbol)
        if trend is None:
            return None
        df_m5 = dataset.window("M5", as_of, 60)
        df_h1 = dataset.window("H1", as_of, 100)
        df_m1 = dataset.window("M1", as_of, 30)
        if len(df_m5) < 15 or len(df_h1) < 20 or len(df_m1) < 5:
            return None
        r = bot.strategy_advanced_smc(df_m5, df_h1, trend, symbol, df_m1)
    if not r:
        return None
    return StrategyResult(direction=r["direction"], stop_loss=r["stop_loss"],
                           reason=r.get("strategy_name", "ADVANCED_SMC"),
                           confidence=r.get("confidence", 0.0))


def _adapt_wyckoff(bot, dataset, as_of, symbol):
    with replay_context(bot, dataset, as_of):
        trend = _get_trend(bot, symbol)
        if trend is None:
            return None
        df_m5 = dataset.window("M5", as_of, 60)
        df_h1 = dataset.window("H1", as_of, 100)
        df_m1 = dataset.window("M1", as_of, 30)
        if len(df_m5) < 40:
            return None
        r = bot.strategy_wyckoff_patterns(df_m5, df_h1, trend, symbol, df_m1)
    if not r:
        return None
    return StrategyResult(direction=r["direction"], stop_loss=r["stop_loss"],
                           reason=r.get("strategy_name", "WYCKOFF_PATTERNS"),
                           confidence=r.get("confidence", 0.0))


def _adapt_volume_profile(bot, dataset, as_of, symbol):
    with replay_context(bot, dataset, as_of):
        trend = _get_trend(bot, symbol)
        if trend is None:
            return None
        df_m5 = dataset.window("M5", as_of, 60)
        if len(df_m5) < 30:
            return None
        r = bot.strategy_volume_profile(df_m5, trend, symbol)
    if not r:
        return None
    return StrategyResult(direction=r["direction"], stop_loss=r["stop_loss"],
                           reason=r.get("strategy_name", "VOLUME_PROFILE"),
                           confidence=r.get("confidence", 0.0))


def _adapt_support_resistance(bot, dataset, as_of, symbol):
    with replay_context(bot, dataset, as_of):
        df_m5 = dataset.window("M5", as_of, 40)
        if len(df_m5) < 20:
            return None
        r = bot.strategy_support_resistance(df_m5, "NEUTRAL")
    if not r:
        return None
    return StrategyResult(direction=r["direction"], stop_loss=r["stop_loss"],
                           reason=r.get("strategy_name", "SUPPORT_RESISTANCE"),
                           confidence=r.get("confidence", 0.0))


def _adapt_volume_imbalance(bot, dataset, as_of, symbol):
    with replay_context(bot, dataset, as_of):
        trend = _get_trend(bot, symbol)
        if trend is None:
            return None
        df_m5 = dataset.window("M5", as_of, 20)
        if len(df_m5) < 5:
            return None
        r = bot.strategy_volume_imbalance(df_m5, trend, symbol)
    if not r:
        return None
    return StrategyResult(direction=r["direction"], stop_loss=r["stop_loss"],
                           reason=r.get("strategy_name", "VOLUME_IMBALANCE"),
                           confidence=r.get("confidence", 0.0))


def _adapt_trend_pullback(bot, dataset, as_of, symbol):
    with replay_context(bot, dataset, as_of):
        trend = _get_trend(bot, symbol)
        if trend not in ("BULLISH", "BEARISH"):
            return None
        df_m5 = dataset.window("M5", as_of, 40)
        if len(df_m5) < 20:
            return None
        r = bot.strategy_trend_pullback(df_m5, trend, symbol)
    if not r:
        return None
    return StrategyResult(direction=r["direction"], stop_loss=r["stop_loss"],
                           reason=r.get("strategy_name", "TREND_PULLBACK"),
                           confidence=r.get("confidence", 0.0))


def _adapt_mean_reversion_bb(bot, dataset, as_of, symbol):
    with replay_context(bot, dataset, as_of):
        df_m5 = dataset.window("M5", as_of, 40)
        if len(df_m5) < 20:
            return None
        r = bot.strategy_mean_reversion_bb(df_m5, symbol)
    if not r:
        return None
    return StrategyResult(direction=r["direction"], stop_loss=r["stop_loss"],
                           reason=r.get("strategy_name", "MEAN_REVERSION_BB"),
                           confidence=r.get("confidence", 0.0))


STRATEGIES_LIVE = [
    StrategyAdapter("ICT_KILLZONE", True, _adapt_ict_killzone),
    StrategyAdapter("LIQUIDITY_GRAB", True, _adapt_liquidity_grab),
    StrategyAdapter("SMC_FVG_OB_RETEST", True, _adapt_liquidity_fvg_engine),
    StrategyAdapter("SHAAKUNI_SSM", True, _adapt_shaakuni_ssm),
    StrategyAdapter("SWAPPY_3C", True, _adapt_swappy_3c),
]

STRATEGIES_DORMANT = [
    StrategyAdapter("SMC_ENTRY_ENGINE", False, _adapt_entry_engine),
    StrategyAdapter("ADVANCED_SMC", False, _adapt_advanced_smc),
    StrategyAdapter("WYCKOFF_PATTERNS", False, _adapt_wyckoff),
    StrategyAdapter("VOLUME_PROFILE", False, _adapt_volume_profile),
    StrategyAdapter("SUPPORT_RESISTANCE", False, _adapt_support_resistance),
    StrategyAdapter("VOLUME_IMBALANCE", False, _adapt_volume_imbalance),
    StrategyAdapter("TREND_PULLBACK", False, _adapt_trend_pullback),
    StrategyAdapter("MEAN_REVERSION_BB", False, _adapt_mean_reversion_bb),
]

ALL_STRATEGIES = STRATEGIES_LIVE + STRATEGIES_DORMANT
STRATEGIES_BY_NAME = {s.name: s for s in ALL_STRATEGIES}
