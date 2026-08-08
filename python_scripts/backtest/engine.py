"""
Walk-forward backtest engine.

Design principles (all a direct response to what the live script review
found missing):

  1. No lookahead. At each decision point the strategy only ever sees bars
     strictly before "now" (HistoricalDataset.window enforces this).
  2. Backtest/live parity by construction. We call the real EntryEngine /
     EdgeEngine classes imported from the live bot file (via bot_loader),
     not a reimplementation -- if the live file changes, the backtest
     automatically tests the new behavior next run.
  3. Every trade's entry reasoning is a re-derivable, structured record
     (setup dict + edge score components), not a one-line summary -- this
     is what "know exactly what went wrong" requires: you can look at any
     losing trade afterward and see precisely which score inputs, regime,
     and session it fired under.
  4. Spread is modeled explicitly, not ignored. It's a static
     per-symbol approximation (SPREAD_MODEL below) -- refine this with
     real recorded spreads from your broker once you have them; the point
     for v1 is that a real cost is being charged at all, since a strategy
     that only looks profitable with zero transaction costs isn't
     profitable.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import pandas as pd

from .data import HistoricalDataset
from .time_travel import frozen_at

# Static spread approximation in price units, per symbol. This is a v1
# placeholder -- real backtests should replace this with spread actually
# recorded from the broker (many brokers widen spread around news/session
# opens, which this can't capture). See export_mt5_history.py for how to
# pull real historical spread alongside OHLC if your broker's history
# provides it.
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


@dataclass
class SimulatedTrade:
    symbol: str
    direction: str
    setup_reason: str
    entry_time: pd.Timestamp
    entry_price: float
    stop_loss: float
    take_profit: float
    edge_score: float
    edge_state: str
    score_components: Dict[str, float]
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # "SL" | "TP" | "TIMEOUT"
    r_multiple: Optional[float] = None


@dataclass
class BacktestConfig:
    symbol: str
    rr_multiple: float = 2.0          # take_profit distance = SL distance * rr_multiple
    max_bars_in_trade: int = 200      # walk-forward cap before forced TIMEOUT exit
    ltf_bars: int = 60                # bars fed as "ltf_df" to EntryEngine
    micro_bars: int = 30              # bars fed as "micro_df"
    htf_bars: int = 100               # bars fed as "htf_df"
    ltf_timeframe: str = "M5"
    micro_timeframe: str = "M1"
    htf_timeframe: str = "H1"
    spread: Optional[float] = None    # overrides DEFAULT_SPREAD_MODEL for this symbol


class BacktestEngine:
    """
    v1 covers the EntryEngine -> EdgeEngine pipeline (the deterministic
    ICT/SMC "sole entry engine" per its own docstring in the live file).
    Wiring in the other strategy_* functions is mechanical from here: each
    just needs a small adapter that turns its (direction, stop_loss)-style
    return into the same SimulatedTrade flow -- see run_backtest.py for
    where to add one.
    """

    def __init__(self, bot_module, dataset: HistoricalDataset, config: BacktestConfig):
        self.bot = bot_module
        self.dataset = dataset
        self.config = config
        self.entry_engine = bot_module.EntryEngine()
        self.edge_engine = bot_module.EdgeEngine()

    def run(self) -> List[SimulatedTrade]:
        cfg = self.config
        ltf_series = self.dataset.frames[cfg.ltf_timeframe]
        trades: List[SimulatedTrade] = []

        i = max(cfg.ltf_bars, 20)  # warmup
        n = len(ltf_series)
        while i < n:
            as_of = ltf_series["time"].iloc[i]

            htf_df = self.dataset.window(cfg.htf_timeframe, as_of, cfg.htf_bars)
            ltf_df = self.dataset.window(cfg.ltf_timeframe, as_of, cfg.ltf_bars)
            micro_df = self.dataset.window(cfg.micro_timeframe, as_of, cfg.micro_bars)

            if len(htf_df) < 55 or len(ltf_df) < 20 or len(micro_df) < 12:
                i += 1
                continue

            with frozen_at(self.bot, as_of.to_pydatetime()):
                setup = self.entry_engine.evaluate_setup(htf_df, ltf_df, micro_df)

            if setup is None:
                i += 1
                continue

            ctx = self.bot.TradeContext(
                liquidity_distance=setup["liquidity_distance"],
                liquidity_strength=setup["liquidity_strength"],
                momentum_state=setup["momentum_state"],
                structure_alignment=setup["structure_alignment"],
                session_strength=0.7,   # v1: not session-aware yet, see README
                volatility_state=0.7,
            )
            edge = self.edge_engine.calculate(ctx)

            if not edge.allow_entry:
                i += 1
                continue

            trade = self._simulate_trade(setup, edge, ctx, as_of, ltf_series, i)
            trades.append(trade)

            # v1 simplification: don't evaluate new entries while this
            # trade is open (avoids overlapping-position P&L accounting).
            # Advance i past the trade's exit bar.
            if trade.exit_time is not None:
                exit_idx = ltf_series[ltf_series["time"] == trade.exit_time].index
                i = int(exit_idx[0]) + 1 if len(exit_idx) else i + 1
            else:
                i += 1

        return trades

    def _simulate_trade(self, setup, edge, ctx, as_of, ltf_series, start_idx) -> SimulatedTrade:
        cfg = self.config
        direction = setup["signal"]
        entry_price = setup["entry_price"]
        stop_loss = setup["stop_loss"]
        sl_dist = abs(entry_price - stop_loss)
        take_profit = (entry_price + sl_dist * cfg.rr_multiple if direction == "BUY"
                        else entry_price - sl_dist * cfg.rr_multiple)

        spread = cfg.spread if cfg.spread is not None else DEFAULT_SPREAD_MODEL.get(cfg.symbol, 0.0)
        # Charge the spread as a worse entry fill -- BUY fills at ask
        # (entry_price + spread), SELL fills at bid (entry_price - spread).
        filled_entry = entry_price + spread if direction == "BUY" else entry_price - spread

        trade = SimulatedTrade(
            symbol=cfg.symbol, direction=direction,
            setup_reason=setup["reason"], entry_time=as_of,
            entry_price=filled_entry, stop_loss=stop_loss, take_profit=take_profit,
            edge_score=edge.score, edge_state=edge.state,
            score_components={
                "liquidity_distance": ctx.liquidity_distance,
                "liquidity_strength": ctx.liquidity_strength,
                "momentum_state": ctx.momentum_state,
                "structure_alignment": ctx.structure_alignment,
            },
        )

        for j in range(start_idx + 1, min(start_idx + 1 + cfg.max_bars_in_trade, len(ltf_series))):
            bar = ltf_series.iloc[j]
            if direction == "BUY":
                hit_sl = bar["low"] <= stop_loss
                hit_tp = bar["high"] >= take_profit
            else:
                hit_sl = bar["high"] >= stop_loss
                hit_tp = bar["low"] <= take_profit

            if hit_sl and hit_tp:
                # Both touched in the same bar -- can't know which came
                # first from OHLC alone. Assume SL first (conservative,
                # standard backtesting convention -- never let ambiguity
                # inflate the result).
                trade.exit_time, trade.exit_price, trade.exit_reason = bar["time"], stop_loss, "SL"
                break
            if hit_sl:
                trade.exit_time, trade.exit_price, trade.exit_reason = bar["time"], stop_loss, "SL"
                break
            if hit_tp:
                trade.exit_time, trade.exit_price, trade.exit_reason = bar["time"], take_profit, "TP"
                break
        else:
            # Never resolved within max_bars_in_trade -- close at the last
            # seen price rather than leave it open forever.
            last = ltf_series.iloc[min(start_idx + cfg.max_bars_in_trade, len(ltf_series) - 1)]
            trade.exit_time, trade.exit_price, trade.exit_reason = last["time"], last["close"], "TIMEOUT"

        realized = (trade.exit_price - trade.entry_price) if direction == "BUY" else (trade.entry_price - trade.exit_price)
        trade.r_multiple = realized / sl_dist if sl_dist > 0 else 0.0
        return trade
