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

from .data import HistoricalDataset
from .strategies_registry import StrategyAdapter, StrategyResult

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

    def run(self) -> List[SimulatedTrade]:
        cfg = self.config
        ltf_series = self.dataset.frames[cfg.ltf_timeframe]
        trades: List[SimulatedTrade] = []

        i = cfg.warmup_bars
        n = len(ltf_series)
        while i < n:
            as_of = ltf_series["time"].iloc[i]

            result = self.adapter.call(self.bot, self.dataset, as_of, cfg.symbol)
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
        spread = cfg.spread if cfg.spread is not None else DEFAULT_SPREAD_MODEL.get(cfg.symbol, 0.0)

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

        # Charge the spread as a worse entry fill: BUY fills at ask
        # (raw_entry + spread), SELL fills at bid (raw_entry - spread).
        filled_entry = raw_entry + spread if direction == "BUY" else raw_entry - spread

        trade = SimulatedTrade(
            symbol=cfg.symbol, strategy=self.adapter.name, direction=direction,
            setup_reason=result.reason, entry_time=entry_time, entry_price=filled_entry,
            stop_loss=stop_loss, take_profit=take_profit, confidence=result.confidence,
            edge_score=result.edge_score, edge_state=result.edge_state,
            order_type=result.order_type, signal_time=signal_time,
        )

        trade.exit_time, trade.exit_price, trade.exit_reason = simulate_exit(
            direction, stop_loss, take_profit, ltf_series, start_idx, cfg.max_bars_in_trade)

        realized = (trade.exit_price - trade.entry_price) if direction == "BUY" else (trade.entry_price - trade.exit_price)
        trade.r_multiple = realized / sl_dist
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
