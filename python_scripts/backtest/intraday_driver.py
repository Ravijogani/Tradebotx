"""
Backtest driver for INTRADAY (intraday.py's context_decision_engine cascade
-- Strategies A/B/C/D/E, checked in that priority order, see
context_decision_engine's own comments in intraday.py for exactly which is
which).

Not a StrategyAdapter like strategies_registry.py's adapters use: those
share one imported bot module (hybrid_trading_bot_multiuser.py) via
BacktestEngine.bot, but intraday.py is a genuinely separate script/process
in production (same reasoning swing_driver.py documents for structural_
swing_pro.py). Closer in shape to aox_driver.py than swing_driver.py,
though: context_decision_engine() is NOT a pure function -- it calls
get_market_data() and datetime.now() internally through several nested
live helpers, so this driver needs intraday_replay.py's patching (see that
file's own docstring for exactly why), unlike swing_driver.py which could
skip that machinery entirely because detect_structural_swing_signal() took
its OHLC windows as plain arguments.

What this driver does NOT attempt to replicate from the live loop:
  - Stacking/pyramiding. Live only computes a non-"NONE" stacking_mode when
    a position is already open on that symbol (active_stacking_engine);
    this driver always calls context_decision_engine with
    stacking_mode="NONE" and simply doesn't scan for a new entry while a
    simulated position is open on this symbol -- exactly matching live's
    own behavior in the (default, no-stack) case: `if stacking_mode ==
    "NONE" and len(existing_pos) > 0: continue`. The gap is only stacking
    ADDS to an already-winning position, a materially harder thing to
    replay correctly (needs the live narrative-stack state machine kept
    alive across calls) -- disclosed, not attempted, same category of gap
    SWAPPY_3C's own adapter already discloses for its 3rd-time re-entry rule.
  - state.approved_bias (AI L1 bias cache). Always passed as "NEUTRAL" --
    same disclosed gap _get_trend()'s docstring already documents for the
    other bot file's harness: there's no historical record of what a live
    AI bias call would have said on a given past bar.
  - MAX_CONCURRENT_TRADES. Not meaningful for a single-symbol backtest
    (this harness backtests one symbol at a time, same as every other
    driver here) -- a single symbol can have at most one open position by
    construction already.
  - Strategy E (AOX Sniper) needs M1 data (strategy_aox_model's df_m1
    argument); without --m1 it's a clean no-op (get_market_data returns
    None for the missing timeframe, same "no data -> skip" fallback every
    strategy function here already has), same as AOX's own --m1-optional
    precedent elsewhere in this harness.
"""

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from . import intraday_replay
from .data import HistoricalDataset, infer_point_size
from .engine import DEFAULT_SPREAD_MODEL, SimulatedTrade, simulate_exit, attribute_exit
from .journal_util import close_journal as _close_journal


@dataclass
class IntradayDriverConfig:
    symbol: str
    max_bars_in_trade: int = 100    # H1 bars (~4 days) -- generous vs MAX_POSITION_DURATION_HOURS live uses
    warmup_bars: int = 210          # H1 bars skipped so D1/H4/M15 windows behind them are populated
    spread: Optional[float] = None
    max_daily_trades: int = 10      # mirrors config.MAX_DAILY_TRADES


def run_intraday_backtest(bot_module, dataset: HistoricalDataset, config: IntradayDriverConfig) -> List[SimulatedTrade]:
    required = ["D1", "H4", "M15", "H1"]
    missing = [tf for tf in required if tf not in dataset.frames]
    if missing:
        raise ValueError(f"INTRADAY needs {', '.join(missing)} (context_decision_engine reads all of them)")

    h1_series = dataset.frames["H1"]
    point_size = infer_point_size(h1_series)

    trades: List[SimulatedTrade] = []
    daily_trade_count = 0
    last_reset_day = None

    i = config.warmup_bars
    n = len(h1_series)
    while i < n:
        as_of = h1_series["time"].iloc[i]

        current_day = as_of.day
        if last_reset_day is None:
            last_reset_day = current_day
        if current_day != last_reset_day:
            daily_trade_count = 0
            last_reset_day = current_day

        if daily_trade_count >= config.max_daily_trades:
            i += 1
            continue

        # Rollover blackout: 21:30-23:00 UTC -- matches the live loop's own
        # gate (high-spread window around US close, no new entries).
        h, m = as_of.hour, as_of.minute
        if (h == 21 and m >= 30) or h == 22:
            i += 1
            continue

        with intraday_replay.replay_context(bot_module, dataset, as_of):
            in_kz = bot_module.is_in_kill_zone()
            macro = bot_module.get_active_macro_window()
            asian = 0 <= h < 7

            # Session-aware minimum confidence threshold -- same cascade
            # as intraday_trading_session()'s own comment block.
            if in_kz and macro:
                min_conf = 0.70
            elif in_kz:
                min_conf = 0.75
            elif not asian:
                min_conf = 0.82
            else:
                min_conf = 0.88

            signal = bot_module.context_decision_engine(
                config.symbol, ai_bias="NEUTRAL", stacking_mode="NONE", min_confidence=min_conf)

            if signal is None:
                i += 1
                continue

            direction = signal["direction"]
            stop_loss = signal["stop_loss"]
            # MARKET fill at this bar's own close -- same convention every
            # other driver in this harness uses (engine.py, aox_driver.py):
            # the strategy's own view of "now" is anchored to bars strictly
            # before `as_of` (dataset.window's no-lookahead guarantee), but
            # once a decision is made, the fill happens at the bar that
            # just closed.
            raw_entry = float(h1_series["close"].iloc[i])

            # Same bypass place_intraday_trade() applies live: Strategy F
            # (Balance Fade) already computed its own precise target (POC/
            # VWAP) -- resolve_intraday_tp()'s liquidity_target/swing-
            # fallback logic was built for Strategies A-E and would
            # silently discard it.
            if signal.get("strategy_name") == "BALANCE_FADE":
                tp = signal.get("tp")
            else:
                tp, _atr = bot_module.resolve_intraday_tp(signal, config.symbol, direction, raw_entry, stop_loss)

        if tp is None:
            i += 1
            continue

        sl_dist = abs(raw_entry - stop_loss)
        if sl_dist <= 0:
            i += 1
            continue

        # Sanity guard: SL/TP must genuinely be on the correct side of the
        # actual fill price. Found necessary on real data -- these
        # strategies mix timeframes (an M15 rejection candle informing a
        # tight SL, nested inside this driver's H1 walk cadence), so by the
        # time of fill (this bar's own close, up to ~45-59 minutes after
        # the M15 confirmation candle) price can have already moved enough
        # to put a tight structural stop on the wrong side. Live doesn't
        # have this gap (the real fill happens seconds after the decision,
        # not up to an hour later), so this is a backtest-only staleness
        # artifact of walking a coarser bar than the finest timeframe a
        # signal actually used -- not a live bug. The honest, conservative
        # response is the same one a careful trader would apply manually:
        # if price already ran through where the setup's own invalidation
        # point would be by the time you're about to fill, don't take it.
        if direction == "BUY" and not (stop_loss < raw_entry < tp):
            i += 1
            continue
        if direction == "SELL" and not (tp < raw_entry < stop_loss):
            i += 1
            continue

        spread = config.spread
        if spread is None and point_size is not None and "spread" in h1_series.columns:
            raw_spread = h1_series["spread"].iloc[i]
            if raw_spread and raw_spread > 0:
                spread = float(raw_spread) * point_size
        if spread is None:
            spread = DEFAULT_SPREAD_MODEL.get(config.symbol, 0.0)

        filled_entry = raw_entry + spread if direction == "BUY" else raw_entry - spread

        exit_time, exit_price, exit_reason = simulate_exit(
            direction, stop_loss, tp, h1_series, i, config.max_bars_in_trade)
        realized = (exit_price - filled_entry) if direction == "BUY" else (filled_entry - exit_price)

        _exit_idx = None
        _m = h1_series.index[h1_series["time"] == exit_time] if exit_time is not None else []
        if len(_m):
            _exit_idx = h1_series.index.get_loc(_m[0])
        _attr = attribute_exit(direction, filled_entry, stop_loss, tp,
                               exit_reason or "", h1_series, _exit_idx)

        trades.append(SimulatedTrade(
            symbol=config.symbol, strategy=f"INTRADAY_{signal.get('strategy_name', '?')}", direction=direction,
            setup_reason=signal.get('strategy_name', 'INTRADAY'), entry_time=as_of, entry_price=filled_entry,
            stop_loss=stop_loss, take_profit=tp, confidence=signal.get('confidence', 0.0),
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
        daily_trade_count += 1

        # One position at a time for this symbol (see module docstring on
        # stacking) -- advance past the exit bar before scanning again.
        if exit_time is not None:
            exit_idx = h1_series[h1_series["time"] == exit_time].index
            i = int(exit_idx[0]) + 1 if len(exit_idx) else i + 1
        else:
            i += 1

    return trades
