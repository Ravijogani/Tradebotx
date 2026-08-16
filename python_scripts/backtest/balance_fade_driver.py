"""
Backtest driver for BALANCE_FADE (market_intelligence.detect_balance_fade_
signal) -- the mean-reversion strategy this repo was missing before this
round of work. Every other strategy across all three bots is trend/
breakout/continuation; this is the one designed to profit from a market
rotating inside its own value area, which is where price spends most of
its time.

Unlike the other three driver files, this one needs no loader of its own:
market_intelligence.py has zero MT5/live-bot dependency (pure functions,
plain DataFrames in, dict/float/None out), so it's just imported directly
-- the same way engine.py itself is imported, not stubbed into a fake
sys.modules entry.
"""

from dataclasses import dataclass
from typing import List, Optional

import market_intelligence as mi
from .data import HistoricalDataset, infer_point_size
from .engine import DEFAULT_SPREAD_MODEL, SimulatedTrade, simulate_exit


@dataclass
class BalanceFadeDriverConfig:
    symbol: str
    timeframe: str = "H1"              # which loaded timeframe to trade the fade on
    profile_lookback_bars: int = 150   # ~6 days of H1 -- a genuinely RECENT value area,
                                        # not one computed over the whole dataset (real
                                        # Market Profile is always a rolling read, not static)
    num_bins: int = 24
    min_rr: float = 1.5
    max_bars_in_trade: int = 60        # ~2.5 days of H1 -- a fade unresolved by then has
                                        # likely stopped being the setup that triggered it
    warmup_bars: int = 160
    spread: Optional[float] = None


def run_balance_fade_backtest(dataset: HistoricalDataset, config: BalanceFadeDriverConfig) -> List[SimulatedTrade]:
    if config.timeframe not in dataset.frames:
        raise ValueError(f"BALANCE_FADE needs {config.timeframe} data (not provided)")

    series = dataset.frames[config.timeframe]
    point_size = infer_point_size(series)

    trades: List[SimulatedTrade] = []
    i = config.warmup_bars
    n = len(series)
    while i < n:
        as_of = series["time"].iloc[i]

        # No-lookahead window: bars strictly before `as_of` (through bar
        # i-1), same convention dataset.window() enforces for every other
        # driver in this harness -- the decision uses only what's already
        # closed, the fill happens at bar i's own close (see below).
        window = dataset.window(config.timeframe, as_of, config.profile_lookback_bars)
        if len(window) < config.profile_lookback_bars // 2:
            i += 1
            continue

        signal = mi.detect_balance_fade_signal(
            window, config.symbol, num_bins=config.num_bins, min_rr=config.min_rr)

        if signal is None:
            i += 1
            continue

        direction = signal["direction"]
        stop_loss = signal["stop_loss"]
        take_profit = signal["take_profit"]
        # MARKET fill at this bar's own close -- same convention engine.py/
        # aox_driver.py/intraday_driver.py all use.
        raw_entry = float(series["close"].iloc[i])

        sl_dist = abs(raw_entry - stop_loss)
        if sl_dist <= 0:
            i += 1
            continue

        # Same staleness guard intraday_driver.py needed: the signal was
        # computed off the window through bar i-1, filled at bar i's own
        # close -- if price already moved enough in that one-bar gap to put
        # the fade's own SL/TP on the wrong side, skip it rather than take
        # a broken trade.
        if direction == "BUY" and not (stop_loss < raw_entry < take_profit):
            i += 1
            continue
        if direction == "SELL" and not (take_profit < raw_entry < stop_loss):
            i += 1
            continue

        spread = config.spread
        if spread is None and point_size is not None and "spread" in series.columns:
            raw_spread = series["spread"].iloc[i]
            if raw_spread and raw_spread > 0:
                spread = float(raw_spread) * point_size
        if spread is None:
            spread = DEFAULT_SPREAD_MODEL.get(config.symbol, 0.0)

        filled_entry = raw_entry + spread if direction == "BUY" else raw_entry - spread

        exit_time, exit_price, exit_reason = simulate_exit(
            direction, stop_loss, take_profit, series, i, config.max_bars_in_trade)
        realized = (exit_price - filled_entry) if direction == "BUY" else (filled_entry - exit_price)

        trades.append(SimulatedTrade(
            symbol=config.symbol, strategy="BALANCE_FADE", direction=direction,
            setup_reason=signal["reason"], entry_time=as_of, entry_price=filled_entry,
            stop_loss=stop_loss, take_profit=take_profit, confidence=0.0,
            order_type="MARKET", signal_time=as_of,
            exit_time=exit_time, exit_price=exit_price, exit_reason=exit_reason,
            r_multiple=realized / sl_dist, spread_charged=spread,
        ))

        # One position at a time -- advance past the exit bar.
        if exit_time is not None:
            exit_idx = series[series["time"] == exit_time].index
            i = int(exit_idx[0]) + 1 if len(exit_idx) else i + 1
        else:
            i += 1

    return trades
