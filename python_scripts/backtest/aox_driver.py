"""
Stateful multi-bar driver for the AOX 25/25/50 layered-entry model.

Why this isn't just another StrategyAdapter in strategies_registry.py:
every adapter there makes a single, stateless decision per bar -- given
the current window of history, either there's a setup right now or there
isn't, and BacktestEngine.run() advances past whatever that one trade's
lifetime is before asking again. AOX is structurally different. Its 3
layers unfold across many separate bar-closes (Layer 1's SD-zone tap, then
possibly hours later Layer 2's SMT+FPFVG confirmation, then possibly hours
after that Layer 3's mitigation-block entry), and *which phase it's in* is
state that must persist across calls -- exactly the shape of
state.aox_states[symbol] in the live file. Layer 2 can also fire while
Layer 1's trade is still open (that's the point of layering into a
developing move), so BacktestEngine's "simulate this trade to its exit,
then resume scanning" loop would be actively wrong here: it would freeze
the state machine while layer 1's trade plays out, silently skipping any
Layer 2/3 signal that should have fired during that window.

So this is a dedicated driver instead. It walks the M5 series bar by bar
itself, keeps one aox_state dict per run (same shape get_aox_state()/
reset_aox_state() use live), and calls the bot's own
detect_aox_phase_signal() -- the pure decision function extracted from
run_aox_layered_entry() -- at every bar. The decision logic under test is
100% the live function, unmodified, same guarantee every other adapter
gives.

Each layer that fires becomes its own independent SimulatedTrade (sized
off the signal's own entry/sl/tp, exited via engine.py's shared
simulate_exit -- the same SL/TP-touch scan every other strategy uses) --
layers aren't merged into one trade, since live they're genuinely separate
MT5 tickets with separate lifecycles.

What this driver does NOT attempt to replicate from the live loop:
  - The main loop's shared `state.symbol_cooldowns` dict -- this backtest
    has no other strategy contending for that symbol's cooldown slot (the
    harness runs one strategy at a time), so a local `cooldown_until`
    variable is the honest equivalent, applying the exact same rule the
    live bug fix added to run_aox_layered_entry(): pause while a cooldown
    is active, reset the state machine back to phase 0 once it clears.
  - MAX_DAILY_TRADES -- run_backtest.py doesn't apply this to any other
    strategy's results either; not singled out here.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from .data import HistoricalDataset
from .engine import DEFAULT_SPREAD_MODEL, SimulatedTrade, simulate_exit
from .replay_data import replay_context
from .strategies_registry import _get_trend


def _fresh_aox_state() -> dict:
    # Must match get_aox_state()'s default dict shape in the live file
    # exactly, since detect_aox_phase_signal() reads/writes these keys.
    return {
        'phase': 0, 'spike': None, 'fib': None, 'direction': None,
        'layer1_ticket': None, 'layer2_ticket': None, 'layer3_ticket': None,
        'fpfvg': None,
    }


@dataclass
class AoxDriverConfig:
    symbol: str
    max_bars_in_trade: int = 200
    warmup_bars: int = 210   # matches EMA scalp's warmup -- AOX's phase-0 detection also reads a 200+ bar M5 window
    spread: Optional[float] = None
    m5_window_bars: int = 210
    m1_window_bars: int = 60


def run_aox_backtest(bot_module, dataset: HistoricalDataset, config: AoxDriverConfig,
                      extra_symbols: Optional[Dict[str, HistoricalDataset]] = None) -> List[SimulatedTrade]:
    if "M1" not in dataset.frames:
        raise ValueError("AOX needs M1 data (Layer 2's FPFVG/CISD detection reads df_m1)")

    ltf_series = dataset.frames["M5"]
    spread = config.spread if config.spread is not None else DEFAULT_SPREAD_MODEL.get(config.symbol, 0.0)

    aox_state = _fresh_aox_state()
    cooldown_until: Optional[pd.Timestamp] = None

    trades: List[SimulatedTrade] = []
    i = config.warmup_bars
    n = len(ltf_series)
    while i < n:
        as_of = ltf_series["time"].iloc[i]

        if cooldown_until is not None:
            if as_of < cooldown_until:
                i += 1
                continue
            # Cooldown elapsed -- mirrors run_aox_layered_entry's bug fix:
            # reset the state machine so a new spike can be detected.
            aox_state = _fresh_aox_state()
            cooldown_until = None

        with replay_context(bot_module, dataset, as_of, extra_symbols=extra_symbols):
            trend = _get_trend(bot_module, config.symbol)
            if trend is None:
                i += 1
                continue
            df_m5 = dataset.window("M5", as_of, config.m5_window_bars)
            df_m1 = dataset.window("M1", as_of, config.m1_window_bars)
            if len(df_m5) < 60 or len(df_m1) < 20:
                i += 1
                continue
            signal = bot_module.detect_aox_phase_signal(aox_state, df_m5, df_m1, trend, config.symbol)

        if signal is None:
            i += 1
            continue

        direction = signal["direction"]
        entry_price = signal["entry_price"]
        stop_loss = signal["sl"]
        take_profit = signal["tp"]
        sl_dist = abs(entry_price - stop_loss)
        if sl_dist <= 0:
            # Degenerate SL -- can't size/measure R. Live execute_aox_layer
            # would also be unable to place a sane order here; skip this
            # bar but still let the state machine keep evolving normally
            # (no state_updates applied, matching "no trade happened").
            i += 1
            continue

        filled_entry = entry_price + spread if direction == "BUY" else entry_price - spread
        exit_time, exit_price, exit_reason = simulate_exit(
            direction, stop_loss, take_profit, ltf_series, i, config.max_bars_in_trade)
        realized = (exit_price - filled_entry) if direction == "BUY" else (filled_entry - exit_price)

        trades.append(SimulatedTrade(
            symbol=config.symbol, strategy=f"AOX_{signal['layer_name']}", direction=direction,
            setup_reason=f"AOX phase->{signal['next_phase']}", entry_time=as_of, entry_price=filled_entry,
            stop_loss=stop_loss, take_profit=take_profit, confidence=signal.get("risk_fraction", 0.0),
            order_type="MARKET", signal_time=as_of,
            exit_time=exit_time, exit_price=exit_price, exit_reason=exit_reason,
            r_multiple=realized / sl_dist,
        ))

        # Apply the same state transition run_aox_layered_entry applies
        # live after execute_aox_layer() succeeds -- everything except the
        # actual mt5.order_send call, which this driver never touches.
        aox_state.update(signal["state_updates"])
        aox_state["phase"] = signal["next_phase"]
        aox_state[f"layer{signal['next_phase']}_ticket"] = f"BT-{len(trades)}"  # placeholder, never a real ticket
        if signal["next_phase"] == 3:
            cooldown_until = as_of + pd.Timedelta(hours=2)

        i += 1

    return trades
