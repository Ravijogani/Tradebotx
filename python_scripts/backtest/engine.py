"""
Walk-forward backtest engine -- drives any StrategyAdapter from
strategies_registry.py through historical data identically.

Design principles (all a direct response to what the live script review
found missing):

  1. No lookahead. At each decision point a strategy only ever sees bars
     strictly before "now" (HistoricalDataset.window enforces this).
  2. Backtest/live parity by construction. Every adapter calls the real
     function/class from the live bot file (via bot_loader) -- not a
     reimplementation.
  3. Every trade's entry reasoning is a re-derivable, structured record,
     not a one-line summary -- this is what "know exactly what went
     wrong" requires.
  4. Spread is modeled explicitly, not ignored (see DEFAULT_SPREAD_MODEL).
  5. MARKET and LIMIT orders are simulated differently. A LIMIT setup
     (Shaakuni) is not guaranteed to fill just because it fired -- price
     has to actually return to the limit level, within a bounded wait, or
     the setup expires with no trade. Treating it as a market fill would
     overstate how often this strategy actually gets a position on.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from .data import HistoricalDataset, infer_point_size
from .strategies_registry import StrategyAdapter, StrategyResult

# REAL-SPREAD FIX: DEFAULT_SPREAD_MODEL is now only a fallback -- a single
# static number for the whole run was always a simplification (spread
# genuinely widens in low-liquidity sessions and news), and MT5 exports
# already carry real per-bar spread (export_mt5_history.py -> the
# `spread` column) that BacktestEngine now reads and converts to price
# units via infer_point_size() instead of ignoring. See BacktestEngine.
# _real_spread_at's docstring for the fallback chain (real per-bar spread
# -> this static model -> 0.0), unchanged for any dataset that doesn't
# carry real spread data (synthetic test data, or a CSV exported without
# the optional spread column).
DEFAULT_SPREAD_MODEL: Dict[str, float] = {
    "XAUUSDm": 0.30,
    "XAGUSDm": 0.03,
    "BTCUSDm": 25.0,
    "ETHUSDm": 1.5,
    "USOILm": 0.04,
    "EURUSDm": 0.00012,
    "GBPUSDm": 0.00015,
    "USDJPYm": 0.012,
}


def simulate_exit(direction: str, stop_loss: float, take_profit: float,
                   ltf_series: pd.DataFrame, start_idx: int, max_bars_in_trade: int):
    """
    Scans forward from `start_idx` (exclusive) for the first bar whose
    high/low touches stop_loss or take_profit; returns (exit_time,
    exit_price, exit_reason). Falls back to a TIMEOUT exit at the last
    scanned bar's close if neither is touched within max_bars_in_trade.

    Extracted out of BacktestEngine._simulate_trade unchanged (same
    ambiguous-same-bar tie-break: assume SL first) so AoxDriver can reuse
    the exact same exit simulation for AOX's layers instead of
    reimplementing it -- two copies of "how does a trade end" is exactly
    the kind of drift this harness exists to avoid.
    """
    for j in range(start_idx + 1, min(start_idx + 1 + max_bars_in_trade, len(ltf_series))):
        bar = ltf_series.iloc[j]
        if direction == "BUY":
            hit_sl = bar["low"] <= stop_loss
            hit_tp = bar["high"] >= take_profit
        else:
            hit_sl = bar["high"] >= stop_loss
            hit_tp = bar["low"] <= take_profit

        if hit_sl:
            # Both touched in the same bar is ambiguous from OHLC alone --
            # assume SL first (conservative, standard convention).
            return bar["time"], stop_loss, "SL"
        if hit_tp:
            return bar["time"], take_profit, "TP"

    last = ltf_series.iloc[min(start_idx + max_bars_in_trade, len(ltf_series) - 1)]
    return last["time"], last["close"], "TIMEOUT"


def attribute_exit(direction: str, entry_price: float, stop_loss: float,
                   take_profit: float, exit_reason: str,
                   ltf_series: pd.DataFrame, exit_idx: int,
                   lookahead_bars: int = 24) -> str:
    """
    WHY the trade ended that way -- not just the mechanical label.

    "SL" is not a reason. A stop that was swept and then saw price run to
    the original target is a STOP PLACEMENT problem. A stop hit by price
    that kept going against us is a THESIS problem. Those need opposite
    fixes -- tighten the entry vs re-examine the bias -- and the difference
    is only recoverable if it's attributed at the time.

    Looks forward `lookahead_bars` after the exit and classifies:
      swept_then_resumed  -- price came back and reached the original TP
      partial_recovery    -- price recovered past entry but not to TP
      thesis_invalidated  -- price continued against us
      clean_target        -- TP hit without ever threatening the stop
      target_hit          -- TP hit (stop was threatened earlier)
      timed_out_*         -- closed on max-bars, with which side it favoured

    Deliberately uses only bars AFTER the exit, so this is post-hoc
    attribution for R&D, never something a live decision could depend on
    (no lookahead is introduced into any trading decision).
    """
    n = len(ltf_series)
    if exit_idx is None or exit_idx >= n - 1:
        return f"{exit_reason.lower()}_no_followthrough_data"

    fwd = ltf_series.iloc[exit_idx + 1:min(exit_idx + 1 + lookahead_bars, n)]
    if len(fwd) == 0:
        return f"{exit_reason.lower()}_no_followthrough_data"

    if direction == "BUY":
        reached_tp = bool((fwd["high"] >= take_profit).any())
        recovered_entry = bool((fwd["high"] >= entry_price).any())
        went_further = bool((fwd["low"] <= stop_loss).any())
    else:
        reached_tp = bool((fwd["low"] <= take_profit).any())
        recovered_entry = bool((fwd["low"] <= entry_price).any())
        went_further = bool((fwd["high"] >= stop_loss).any())

    if exit_reason == "SL":
        if reached_tp:
            return "swept_then_resumed -- stop was hit but price then reached the original target (stop placement, not thesis)"
        if recovered_entry:
            return "partial_recovery -- price came back past entry but never reached target (marginal setup)"
        return "thesis_invalidated -- price continued against us after the stop (bias/structure was wrong)"

    if exit_reason == "TP":
        return "target_hit"

    # TIMEOUT
    if recovered_entry and not went_further:
        return "timed_out_favourable -- closed on time limit while still onside"
    return "timed_out_adverse -- closed on time limit while offside"


@dataclass
class SimulatedTrade:
    symbol: str
    strategy: str
    direction: str
    setup_reason: str
    entry_time: pd.Timestamp
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float = 0.0
    edge_score: Optional[float] = None
    edge_state: Optional[str] = None
    order_type: str = "MARKET"
    signal_time: Optional[pd.Timestamp] = None  # when the setup fired (may precede entry_time for LIMIT fills)
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # "SL" | "TP" | "TIMEOUT"
    r_multiple: Optional[float] = None
    # REAL-SPREAD FIX: the actual spread (price units) charged on entry --
    # surfaced per-trade specifically so this is verifiable rather than
    # trusted: real per-bar spread should visibly vary trade to trade,
    # unlike the old single static DEFAULT_SPREAD_MODEL number.
    spread_charged: Optional[float] = None
    # DECISION JOURNAL: the full case the strategy made for this trade, plus
    # exit attribution. Serialized as JSON in the ledger CSV so R&D can mine
    # "which confirmations predict a better trade" across a whole run --
    # see python_scripts/decision_journal.py and analyze_journal.py.
    journal: Optional[dict] = None
    exit_attribution: Optional[str] = None


@dataclass
class BacktestConfig:
    symbol: str
    rr_multiple: float = 2.0          # used only when a strategy doesn't supply its own take_profit
    max_bars_in_trade: int = 200
    max_limit_wait_bars: int = 30     # how long a LIMIT setup waits for a fill before expiring
    ltf_timeframe: str = "M5"
    spread: Optional[float] = None    # overrides DEFAULT_SPREAD_MODEL for this symbol
    warmup_bars: int = 110            # bars to skip at the start so H1/M15 rolling windows are populated


class BacktestEngine:
    def __init__(self, bot_module, dataset: HistoricalDataset, config: BacktestConfig, adapter: StrategyAdapter):
        self.bot = bot_module
        self.dataset = dataset
        self.config = config
        self.adapter = adapter
        # REAL-SPREAD FIX: computed once per run, not per trade -- the
        # point size doesn't change bar to bar, only the spread itself does.
        self._point_size = infer_point_size(dataset.frames.get(config.ltf_timeframe))

    def _real_spread_at(self, ltf_series: pd.DataFrame, idx: int) -> Optional[float]:
        """
        REAL-SPREAD FIX: real per-bar spread (MT5's raw points, converted
        to price units via this dataset's inferred point size) at the bar
        a trade actually fills on, instead of one static number charged to
        every trade in the entire run regardless of what the spread
        genuinely was at that moment (news spikes, thin Asian-session
        liquidity, etc. all widen real spread -- a flat number can't
        reflect that). Returns None whenever real data isn't usable (no
        `spread` column, this dataset's point size couldn't be inferred,
        or the bar's own spread value is missing/zero) -- the caller falls
        back to DEFAULT_SPREAD_MODEL in that case, exactly the behavior
        every backtest before this fix already had.
        """
        if self._point_size is None or "spread" not in ltf_series.columns:
            return None
        raw = ltf_series["spread"].iloc[idx]
        if not raw or raw <= 0:
            return None
        return float(raw) * self._point_size

    def run(self) -> List[SimulatedTrade]:
        cfg = self.config
        ltf_series = self.dataset.frames[cfg.ltf_timeframe]
        trades: List[SimulatedTrade] = []
        # Setups the strategy evaluated and declined. Collected via the
        # side-channel sink in decision_journal (never via return values --
        # see that module's note on why instrumentation must not be able to
        # place an order). Exposed as .rejections for run_backtest to persist.
        self.rejections: List[dict] = []

        i = cfg.warmup_bars
        n = len(ltf_series)
        while i < n:
            as_of = ltf_series["time"].iloc[i]

            result = self.adapter.call(self.bot, self.dataset, as_of, cfg.symbol)

            # Drain per bar so each rejection can be stamped with the bar it
            # happened on -- draining once at the end would lose that.
            for rj in self.bot.dj.drain_rejections():
                rj["at_bar"] = str(as_of)
                self.rejections.append(rj)

            if result is None:
                i += 1
                continue

            trade = self._simulate_trade(result, as_of, ltf_series, i)
            if trade is None:
                # LIMIT setup never filled within max_limit_wait_bars -- not
                # a trade, but also not nothing: still worth knowing how
                # often this strategy fires without ever getting a fill.
                i += 1
                continue

            trades.append(trade)

            if trade.exit_time is not None:
                exit_idx = ltf_series[ltf_series["time"] == trade.exit_time].index
                i = int(exit_idx[0]) + 1 if len(exit_idx) else i + 1
            else:
                i += 1

        return trades

    def _simulate_trade(self, result: StrategyResult, signal_time, ltf_series, signal_idx) -> Optional[SimulatedTrade]:
        cfg = self.config
        direction = result.direction

        if result.order_type == "LIMIT":
            fill = self._wait_for_limit_fill(result, ltf_series, signal_idx)
            if fill is None:
                return None
            filled_close_price, entry_idx = fill
            entry_time = ltf_series["time"].iloc[entry_idx]
            raw_entry = result.limit_entry
            start_idx = entry_idx
        else:
            raw_entry = result.entry_price if result.entry_price is not None else ltf_series["close"].iloc[signal_idx]
            entry_time = signal_time
            start_idx = signal_idx

        stop_loss = result.stop_loss
        sl_dist = abs(raw_entry - stop_loss)
        if sl_dist <= 0:
            return None  # degenerate SL -- can't size or measure R, skip rather than divide by zero

        take_profit = result.take_profit
        if take_profit is None:
            take_profit = (raw_entry + sl_dist * cfg.rr_multiple if direction == "BUY"
                            else raw_entry - sl_dist * cfg.rr_multiple)

        # REAL-SPREAD FIX: prefer real per-bar spread at the actual fill bar
        # over the static DEFAULT_SPREAD_MODEL number -- see _real_spread_at's
        # docstring. cfg.spread (an explicit --spread override) still wins
        # over both, unchanged from before this fix.
        spread = cfg.spread
        if spread is None:
            spread = self._real_spread_at(ltf_series, start_idx)
        if spread is None:
            spread = DEFAULT_SPREAD_MODEL.get(cfg.symbol, 0.0)

        # Charge the spread as a worse entry fill: BUY fills at ask
        # (raw_entry + spread), SELL fills at bid (raw_entry - spread).
        filled_entry = raw_entry + spread if direction == "BUY" else raw_entry - spread

        trade = SimulatedTrade(
            symbol=cfg.symbol, strategy=self.adapter.name, direction=direction,
            setup_reason=result.reason, entry_time=entry_time, entry_price=filled_entry,
            stop_loss=stop_loss, take_profit=take_profit, confidence=result.confidence,
            edge_score=result.edge_score, edge_state=result.edge_state,
            order_type=result.order_type, signal_time=signal_time,
            spread_charged=spread,
        )

        trade.exit_time, trade.exit_price, trade.exit_reason = simulate_exit(
            direction, stop_loss, take_profit, ltf_series, start_idx, cfg.max_bars_in_trade)

        realized = (trade.exit_price - trade.entry_price) if direction == "BUY" else (trade.entry_price - trade.exit_price)
        trade.r_multiple = realized / sl_dist

        # Locate the exit bar so the attribution can look at what happened
        # AFTER it (post-hoc only -- never feeds a trading decision).
        exit_idx = None
        if trade.exit_time is not None:
            matches = ltf_series.index[ltf_series["time"] == trade.exit_time]
            if len(matches):
                exit_idx = ltf_series.index.get_loc(matches[0])
        trade.exit_attribution = attribute_exit(
            direction, trade.entry_price, stop_loss, take_profit,
            trade.exit_reason or "", ltf_series, exit_idx)

        # Carry the strategy's own decision journal through, and close it out
        # with the real outcome so summarize_by_confirmation() can correlate
        # each confirmation against actual R.
        jrnl = getattr(result, "journal", None)
        if jrnl:
            jrnl = dict(jrnl)
            # float() on r_multiple is load-bearing, not cosmetic: it is
            # computed from numpy price columns, so it is an np.float64. That
            # serializes as `np.float64(-1.01)`, which is neither valid JSON
            # (the live path writes journals to a Supabase JSONB column) nor
            # parseable by analyze_journal.py -- which is exactly how
            # EMA_SCALP_CROSS journals were written successfully but silently
            # failed to load. decision_journal._plain() coerces everything
            # that goes through the journal's own methods; this dict is built
            # here directly, so it has to do the same.
            jrnl["exit"] = {
                "outcome": trade.exit_reason,
                "reason": trade.exit_attribution,
                "r_multiple": float(trade.r_multiple) if trade.r_multiple is not None else None,
                "at": str(trade.exit_time),
            }
            trade.journal = jrnl
        return trade

    def _wait_for_limit_fill(self, result: StrategyResult, ltf_series, signal_idx):
        """
        A LIMIT order only fills once price actually trades through
        limit_entry. Scans forward up to max_limit_wait_bars; returns
        (fill_price, bar_index) on the first bar that touches the limit
        level, or None if it never fills (the setup expires -- correctly
        recorded as no trade, not a loss).
        """
        cfg = self.config
        limit_price = result.limit_entry
        if limit_price is None:
            return None
        direction = result.direction
        for j in range(signal_idx + 1, min(signal_idx + 1 + cfg.max_limit_wait_bars, len(ltf_series))):
            bar = ltf_series.iloc[j]
            touched = (bar["low"] <= limit_price <= bar["high"])
            if touched:
                return limit_price, j
        return None
