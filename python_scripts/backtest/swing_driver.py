"""
Backtest driver for STRUCTURAL_SWING (structural_swing_pro.py).

Not a StrategyAdapter like strategies_registry.py's adapters: those all
share one imported bot module (hybrid_trading_bot_multiuser.py) via
BacktestEngine.bot, but structural_swing_pro.py is a genuinely separate
script/process in production (see its own module docstring for why), so it
needs its own imported module (swing_loader.import_swing_bot_module()) --
the same "separate driver for a separate execution shape" reasoning
aox_driver.py already established for AOX, just because this is a
different *file* rather than a different *state machine*.

Simpler than aox_driver.py in one respect: detect_structural_swing_signal()
takes its OHLC windows as plain arguments rather than reaching into
get_market_data() internally, so this driver doesn't need replay_data.py's
monkeypatching machinery at all -- HistoricalDataset.window()'s results are
handed straight to the pure decision function, exactly like calling it
live would, just with historical data. That's a direct consequence of the
function's own design (see structural_swing_pro.py's module docstring,
"BACKTEST/LIVE PARITY"), not a shortcut specific to this driver.
"""

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from .data import HistoricalDataset, infer_point_size
from .engine import DEFAULT_SPREAD_MODEL, SimulatedTrade, simulate_exit, attribute_exit
from .journal_util import close_journal as _close_journal


@dataclass
class SwingDriverConfig:
    symbol: str
    d1_bars: int = 120
    h4_bars: int = 60
    max_bars_in_trade: int = 120   # H4 bars -- 120*4h = 20 days, matches MAX_POSITION_DURATION_DAYS
    warmup_bars: int = 70          # H4 bars skipped so the D1 window behind them is populated
    spread: Optional[float] = None


def run_swing_backtest(bot_module, dataset: HistoricalDataset, config: SwingDriverConfig) -> List[SimulatedTrade]:
    if "D1" not in dataset.frames:
        raise ValueError("STRUCTURAL_SWING needs D1 data (structure/bias detection reads it)")
    if "H4" not in dataset.frames:
        raise ValueError("STRUCTURAL_SWING needs H4 data (entry trigger reads it)")

    h4_series = dataset.frames["H4"]
    point_size = infer_point_size(h4_series)

    trades: List[SimulatedTrade] = []
    i = config.warmup_bars
    n = len(h4_series)
    while i < n:
        as_of = h4_series["time"].iloc[i]

        df_d1 = dataset.window("D1", as_of, config.d1_bars)
        df_h4 = dataset.window("H4", as_of, config.h4_bars)
        if len(df_d1) < 20 or len(df_h4) < 10:
            i += 1
            continue

        signal = bot_module.detect_structural_swing_signal(df_d1, df_h4, config.symbol)
        if signal is None:
            i += 1
            continue

        direction = signal["direction"]
        raw_entry = signal["entry_price"]
        stop_loss = signal["stop_loss"]
        take_profit = signal["take_profit"]
        sl_dist = abs(raw_entry - stop_loss)
        if sl_dist <= 0:
            i += 1
            continue

        spread = config.spread
        if spread is None and point_size is not None and "spread" in h4_series.columns:
            raw_spread = h4_series["spread"].iloc[i]
            if raw_spread and raw_spread > 0:
                spread = float(raw_spread) * point_size
        if spread is None:
            spread = DEFAULT_SPREAD_MODEL.get(config.symbol, 0.0)

        filled_entry = raw_entry + spread if direction == "BUY" else raw_entry - spread

        exit_time, exit_price, exit_reason = simulate_exit(
            direction, stop_loss, take_profit, h4_series, i, config.max_bars_in_trade)
        realized = (exit_price - filled_entry) if direction == "BUY" else (filled_entry - exit_price)

        _exit_idx = None
        _m = h4_series.index[h4_series["time"] == exit_time] if exit_time is not None else []
        if len(_m):
            _exit_idx = h4_series.index.get_loc(_m[0])
        _attr = attribute_exit(direction, filled_entry, stop_loss, take_profit,
                               exit_reason or "", h4_series, _exit_idx)

        trades.append(SimulatedTrade(
            symbol=config.symbol, strategy="STRUCTURAL_SWING", direction=direction,
            setup_reason=signal["reason"], entry_time=as_of, entry_price=filled_entry,
            stop_loss=stop_loss, take_profit=take_profit, confidence=0.0,
            order_type="MARKET", signal_time=as_of,
            exit_time=exit_time, exit_price=exit_price, exit_reason=exit_reason,
            r_multiple=realized / sl_dist, spread_charged=spread,
            # DECISION JOURNAL: carry the strategy's own entry reasoning and
            # close it out with the real outcome + attribution, so this driver's
            # trades are minable by backtest/analyze_journal.py exactly like the
            # scalping bot's are (one analysis path for all three bots).
            journal=_close_journal(signal.get('journal'), exit_reason,
                                   _attr, realized / sl_dist, exit_time),
            exit_attribution=_attr,
        ))

        # One position at a time for this symbol (matches the live script:
        # a fresh D1 structure read only fires again once the prior swing
        # trade has resolved) -- advance past the exit bar before scanning
        # for the next setup, same pattern engine.py's BacktestEngine.run()
        # and aox_driver.py's cooldown handling both already use.
        if exit_time is not None:
            exit_idx = h4_series[h4_series["time"] == exit_time].index
            i = int(exit_idx[0]) + 1 if len(exit_idx) else i + 1
        else:
            i += 1

    return trades
