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

LIVE strategies -- and why nothing else is here
--------------------------------------------------------------
The live cascade trades exactly four documented setups: Shaakuni SSM,
Swappy 3C, AOX (dedicated stateful driver, see aox_driver.py -- not a
StrategyAdapter, its phases persist and overlap across bar-closes), and
the 9/25/50/200 EMA scalp. Nothing else in the live file has a call site.

  LIVE right now (has a real call site in the file):
    - strategy_shaakuni_ssm()           ("SHAAKUNI SSM")
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
    - AOX -- see aox_driver.py, not a StrategyAdapter here on purpose.

  REMOVED 2026-08, all confirmed to have had zero live call sites at the
  time of removal (confirmed by grepping call sites, not just defs), or
  in the case of the three ICT-style fallbacks, flag-gated off for the
  entire time this bot traded anything real and never part of the actual
  four-setup vision. See python_scripts/backtest/README.md's "Dormant/
  fallback strategies removed" section for the full reasoning and any
  real-data numbers behind each removal. Recoverable from git history
  (search this repo's log for "strategies_research.py", "Quarantine
  dormant strategies", or "remove all 8 base strategies") -- don't
  rewrite any of these from scratch if revisited:
    - EntryEngine.evaluate_setup, strategy_advanced_smc,
      strategy_wyckoff_patterns, strategy_volume_profile,
      strategy_support_resistance, strategy_volume_imbalance,
      strategy_trend_pullback, strategy_mean_reversion_bb
      (the original 8 dormant strategies)
    - strategy_ict_killzone, strategy_liquidity_grab (flag-gated generic
      ICT fallbacks), strategy_liquidity_fvg_engine ("STRATEGY C" / SMC
      FVG retest, also flag-gated -- and 0 trades in the real-data
      backtest even while it was still wired here)

The live STRATEGY B additionally applies a location filter (near M5
support/resistance) and a stateful "3rd-time re-entry rule"
(can_take_swappy_entry) on top of detect_swappy_3c()'s pattern match --
only the pure pattern-detection part is wired in _adapt_swappy_3c below;
see that adapter's own docstring.
"""

from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from .data import HistoricalDataset
from .replay_data import replay_context

# EFFICIENCY: classify_m30_character() memoized per M30 bar boundary (see
# _get_m30_character() below) -- _get_trend() is called once per M5/M1
# replay step, up to ~6x more often than the M30 series actually advances.
_m30_char_cache: dict = {}


def _get_m30_character(bot, dataset: HistoricalDataset, as_of) -> dict:
    """
    Wraps bot.classify_m30_character() with memoization keyed by which M30
    bar it would be computed from, not by `as_of` itself. Without this,
    the first M30-gated real-data backtest run took several times longer
    than the equivalent ungated run for no behavioral reason: every M5 (or
    M1) replay step re-ran classify_m30_character()'s O(n) fractal
    swing-scan over a fresh 60-bar M30 window, even though up to 6
    consecutive M5 bars share the exact same "most recent M30 bar" and so
    get the identical result. Caching per M30 boundary computes it once
    per M30 bar instead of once per M5/M1 bar -- same results, not a
    behavior change, confirmed by re-running the exact backtest this was
    found in and comparing trade-for-trade before/after this fix.
    """
    empty = {'signal': 'NONE', 'break_direction': None, 'established_trend': 'NEUTRAL'}
    m30_time = dataset.frames["M30"]["time"]
    pos = m30_time.searchsorted(as_of, side="left") - 1
    if pos < 0:
        return empty
    boundary = m30_time.iloc[pos]
    key = (id(dataset), boundary)
    cached = _m30_char_cache.get(key)
    if cached is None:
        df_m30 = dataset.window("M30", as_of, 60)
        cached = bot.classify_m30_character(df_m30)
        _m30_char_cache[key] = cached
    return cached


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
                                          # bar's close.
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

    # M30 STRUCTURE-SHIFT GATE: mirrors the live scan loop's CHoCH veto
    # (see classify_m30_character()'s docstring in hybrid_trading_bot_
    # multiuser.py for the full "why"). Optional here -- if the dataset
    # wasn't given --m30, this gate is simply not exercised (same
    # graceful-degradation pattern as --h4/--d1/--m1 elsewhere in this
    # harness), not a hard requirement.
    if "M30" in dataset.frames:
        m30_char = _get_m30_character(bot, dataset, as_of)
        choch_veto_dir = "BEARISH" if effective_trend == "BULLISH" else "BULLISH"
        if m30_char["signal"] == "CHOCH" and m30_char["break_direction"] == choch_veto_dir:
            return None  # live does `continue` here -- see [CHOCH VETO] log line

    return effective_trend


def _adapt_shaakuni_ssm(bot, dataset: HistoricalDataset, as_of, symbol):
    # Live call site: strategy_shaakuni_ssm(symbol, df_h1, df_h4, df_m5,
    # effective_trend, df_d1) -- df_d1 optional (PDH/PDL liquidity
    # confluence/TP source), same graceful-degradation as the M30 gate
    # above: without --d1, strategy_shaakuni_ssm still runs, it just
    # never sees PDH/PDL as a candidate reference level.
    if "H4" not in dataset.frames:
        return None  # needs H4 -- see export_mt5_history.py / README
    with replay_context(bot, dataset, as_of):
        trend = _get_trend(bot, dataset, as_of, symbol)
        if trend is None:
            return None
        df_h1 = dataset.window("H1", as_of, 60)
        df_h4 = dataset.window("H4", as_of, 60)
        df_m5 = dataset.window("M5", as_of, 60)
        df_d1 = dataset.window("D1", as_of, 10) if "D1" in dataset.frames else None
        if len(df_m5) < 10:
            return None
        r = bot.strategy_shaakuni_ssm(symbol, df_h1, df_h4, df_m5, trend, df_d1)
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
    market fill at candle 3's close. SL and TP now call the exact same
    compute_swappy_sl() / find_swappy_structural_tp() functions live uses
    (extracted specifically so this adapter and the live call site can't
    drift apart the way the old duplicated inline SL calc already had) --
    trap-aware SL buffer, structural TP (nearest real swing level at
    >=1.5R) falling back to the original fixed 3:1 spec target only when
    nothing structural qualifies.

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
        df_m5 = dataset.window("M5", as_of, 80)  # find_swappy_structural_tp scans up to 80 bars back
        if len(df_m5) < 20:
            return None
        # MARKET INTELLIGENCE INTEGRATION: df_h1/df_d1 optional (liquidity
        # confluence strength bonus, see detect_swappy_3c's own docstring)
        # -- H1 always available (SWAPPY_3C is in STRATEGIES_LIVE, and
        # every real run provides --h1), D1 only if --d1 was given.
        df_h1_sw = dataset.window("H1", as_of, 60) if "H1" in dataset.frames else None
        df_d1_sw = dataset.window("D1", as_of, 10) if "D1" in dataset.frames else None
        sw = bot.detect_swappy_3c(df_m5, direction, df_h1_sw, df_d1_sw)
        if not sw.get("confirmed"):
            return None
        atr_m5 = float(bot.calculate_atr(df_m5['high'], df_m5['low'], df_m5['close'], 14).iloc[-1])
        sl = bot.compute_swappy_sl(df_m5, direction, atr_m5)
        stop_entry = sw['stop_entry']
        sl_dist = abs(stop_entry - sl)
        if sl_dist <= 0:
            return None
        tp = bot.find_swappy_structural_tp(df_m5, direction, stop_entry, sl_dist)
        if tp is None:
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
    the engine's generic --rr multiple is a disclosed approximation of
    live's real RR-gated TP, not a byte-exact replication -- but it's a
    real target on the correct side of entry, which is what matters most:
    the prior behavior wasn't an approximation of anything, it was
    unconditionally wrong.
    """
    with replay_context(bot, dataset, as_of):
        trend = _get_trend(bot, dataset, as_of, symbol)
        if trend not in ("BULLISH", "BEARISH"):
            return None
        direction = "BUY" if trend == "BULLISH" else "SELL"
        df_m5 = dataset.window("M5", as_of, 210)  # 200 EMA needs real history to be stable
        if len(df_m5) < 60:
            return None
        # MARKET INTELLIGENCE INTEGRATION: df_h1/df_d1 optional (liquidity
        # confluence feeding the existing liquidity_strength EdgeEngine
        # input, see strategy_ema_scalp_cross's own docstring).
        df_h1_ema = dataset.window("H1", as_of, 60) if "H1" in dataset.frames else None
        df_d1_ema = dataset.window("D1", as_of, 10) if "D1" in dataset.frames else None
        r = bot.strategy_ema_scalp_cross(df_m5, direction, symbol, df_h1_ema, df_d1_ema)
    if not r:
        return None
    return StrategyResult(direction=r["signal"], stop_loss=r["stop_loss"],
                           reason=r.get("reason", "EMA_SCALP_CROSS"))


STRATEGIES_LIVE = [
    StrategyAdapter("SHAAKUNI_SSM", True, _adapt_shaakuni_ssm),
    StrategyAdapter("SWAPPY_3C", True, _adapt_swappy_3c),
    StrategyAdapter("EMA_SCALP_CROSS", True, _adapt_ema_scalp_cross),
]

ALL_STRATEGIES = STRATEGIES_LIVE
STRATEGIES_BY_NAME = {s.name: s for s in ALL_STRATEGIES}
