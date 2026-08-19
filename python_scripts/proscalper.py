# -*- coding: utf-8 -*-
"""
proscalper.py -- HIGH-FREQUENCY CANDLE SCALPER (STANDALONE / EXPERIMENTAL)
=========================================================================

A deliberately AGGRESSIVE scalper: it evaluates EVERY closed candle on the
execution timeframe and takes a position whenever that candle expresses a
clear directional bias. It flips or flattens the moment the market turns
against it, books partials into strength, and hard-stops the whole session
if account equity falls 20% below the session's starting equity.

THIS IS NOT ONE OF THE THREE PRODUCTION BOTS.
---------------------------------------------
It is intentionally NOT wired into the dashboard, bot_manager, Supabase,
Telegram or the shared risk_limits.py ceilings (5% daily / 10% weekly).
It runs from the command line against a local MT5 terminal so it can be
tested in isolation on a DEMO account first. Nothing in this file imports
from, or is imported by, the live stack.

RISK WARNING (read before running on anything with real money in it)
--------------------------------------------------------------------
Trading every candle means paying the spread every candle. At M1 on a
typical retail feed the spread alone is a meaningful fraction of the move
this strategy is trying to capture, so the edge is thin by construction
and the strategy is expected to be spread- and execution-sensitive. The
20% equity stop is a backstop against catastrophe, not a substitute for
an edge. Test on DEMO, and size with --risk-percent well under 1.

HOW IT DECIDES
--------------
On each newly CLOSED candle (never mid-bar -- an unclosed bar can change
its mind entirely before it prints):

  1. BODY DOMINANCE  the candle's body must be >= BODY_RATIO of its total
     range, so we act on conviction candles and ignore indecision/doji.
  2. RANGE FLOOR     the candle's range must be >= MIN_RANGE_ATR * ATR,
     which filters the dead micro-bars that only pay the spread.
  3. TREND ALIGNMENT the candle must close on the correct side of a fast
     EMA, and the fast EMA on the correct side of the slow EMA. Scalping
     against the immediate trend is how this style of bot bleeds out.
  4. SPREAD GATE     the live spread must be <= MAX_SPREAD_ATR * ATR.
     Widening spread is the single best predictor of a bad scalp fill.

MANAGEMENT
----------
  * STOP     beyond the signal candle's extreme + a spread-aware buffer.
  * TARGET   TP_R multiples of that stop distance.
  * PARTIAL  half the position is closed at PARTIAL_R; the remainder
             runs with the stop moved to breakeven + spread.
  * REVERSE  a closed candle satisfying the full entry test in the
             OPPOSITE direction closes the position immediately (and,
             with --allow-flip, opens the opposite one on the same bar).
  * TRAIL    after the partial, the stop trails the previous candle's
             extreme, so a trend leg is allowed to run.

EQUITY KILL SWITCH
------------------
Session start equity is captured once and persisted to disk, so a restart
mid-session does NOT hand the account a fresh 20% to lose (the same
restart-safety the production bots' daily baseline has). On breach: every
position this bot opened is closed, and the process exits non-zero.

USAGE
-----
    python proscalper.py --login 123456 --password xxx --server Exness-MT5Trial \
        --symbols XAUUSDm,EURUSDm --timeframe M1 --risk-percent 0.25 --dry-run

    --dry-run  logs every decision and places NO orders. Start here.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover
    print("MetaTrader5 package not installed. pip install MetaTrader5")
    raise

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    print("pandas not installed. pip install pandas")
    raise


# =============================================================================
# TUNABLES -- every number this strategy's behaviour depends on, in one place
# =============================================================================

MAGIC_NUMBER = 990001          # keeps this bot's positions separate from every
                               # other bot on the same terminal. Never reuse.

BODY_RATIO = 0.60              # body must be >=60% of range: conviction only
MIN_RANGE_ATR = 0.35           # candle range floor as a fraction of ATR
MAX_SPREAD_ATR = 0.25          # refuse to trade when spread eats the move
EMA_FAST, EMA_SLOW = 8, 21     # immediate-trend filter
ATR_PERIOD = 14

SL_BUFFER_ATR = 0.15           # extra room beyond the signal candle extreme
TP_R = 1.6                     # full target, in R
PARTIAL_R = 0.8                # bank half here, then breakeven the rest
TRAIL_AFTER_PARTIAL = True

MAX_OPEN_POSITIONS = 3         # across all symbols
MAX_TRADES_PER_SYMBOL_PER_HOUR = 12   # churn brake
DEFAULT_RISK_PERCENT = 0.25    # per trade, % of equity

EQUITY_STOP_PERCENT = 20.0     # hard session kill switch
BASELINE_FILE = "proscalper_equity_baseline.json"

TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1, "M2": mt5.TIMEFRAME_M2, "M3": mt5.TIMEFRAME_M3,
    "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
}

log = logging.getLogger("proscalper")


# =============================================================================
# INDICATORS -- plain pandas, no TA library dependency
# =============================================================================

def ema(series, period: int):
    return series.ewm(span=period, adjust=False).mean()


def atr(df, period: int = ATR_PERIOD) -> float:
    high, low, close = df["high"], df["low"], df["close"]
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    val = tr.rolling(period).mean().iloc[-1]
    return float(val) if val == val else 0.0   # NaN-safe


# =============================================================================
# SIGNAL -- pure function of the candle frame, so it is testable without MT5
# =============================================================================

def candle_signal(df, spread_price: float) -> Optional[Dict]:
    """
    Evaluate the LAST CLOSED candle. Returns a signal dict or None.

    df must already exclude the still-forming bar (see fetch_closed_candles).
    """
    if df is None or len(df) < max(EMA_SLOW, ATR_PERIOD) + 2:
        return None

    a = atr(df)
    if a <= 0:
        return None

    c = df.iloc[-1]
    rng = float(c["high"] - c["low"])
    if rng <= 0:
        return None

    body = abs(float(c["close"] - c["open"]))
    if body / rng < BODY_RATIO:
        return None                        # doji / indecision
    if rng < MIN_RANGE_ATR * a:
        return None                        # dead micro-bar, spread-only trade
    if spread_price > MAX_SPREAD_ATR * a:
        return None                        # spread gate

    fast = ema(df["close"], EMA_FAST).iloc[-1]
    slow = ema(df["close"], EMA_SLOW).iloc[-1]
    close = float(c["close"])

    if close > fast and fast > slow and c["close"] > c["open"]:
        direction = "BUY"
        stop = float(c["low"]) - (SL_BUFFER_ATR * a) - spread_price
    elif close < fast and fast < slow and c["close"] < c["open"]:
        direction = "SELL"
        stop = float(c["high"]) + (SL_BUFFER_ATR * a) + spread_price
    else:
        return None

    risk = abs(close - stop)
    if risk <= 0:
        return None

    return {
        "direction": direction,
        "ref_close": close,
        "stop": stop,
        "risk_distance": risk,
        "atr": a,
        "bar_time": df.index[-1],
    }


# =============================================================================
# EQUITY BASELINE -- restart-safe, mirrors the production daily-baseline rule
# =============================================================================

def load_or_init_baseline(data_dir: str, equity: float) -> float:
    path = os.path.join(data_dir, BASELINE_FILE)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if saved.get("day") == day and float(saved.get("baseline", 0)) > 0:
            return float(saved["baseline"])
    except (OSError, ValueError, TypeError, KeyError):
        pass
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"day": day, "baseline": equity}, f)
    except OSError as e:
        log.warning("could not persist equity baseline: %s", e)
    return equity


# =============================================================================
# MT5 PLUMBING
# =============================================================================

def connect(login: Optional[int], password: Optional[str], server: Optional[str],
            mt5_path: Optional[str]) -> bool:
    ok = mt5.initialize(path=mt5_path) if mt5_path else mt5.initialize()
    if not ok:
        log.error("MT5 initialize failed: %s", mt5.last_error())
        return False
    if login:
        if not mt5.login(login=int(login), password=password, server=server):
            log.error("MT5 login failed: %s", mt5.last_error())
            return False
    acct = mt5.account_info()
    if not acct:
        log.error("no account info after login")
        return False
    log.info("connected | login=%s balance=%.2f equity=%.2f", acct.login, acct.balance, acct.equity)
    return True


def fetch_closed_candles(symbol: str, tf: int, count: int = 200):
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) < 3:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time")
    return df.iloc[:-1]      # drop the still-forming bar -- decisions on closes only


def live_spread(symbol: str) -> float:
    t = mt5.symbol_info_tick(symbol)
    return float(t.ask - t.bid) if t else 0.0


def calc_lot(symbol: str, equity: float, risk_percent: float, risk_distance: float) -> float:
    info = mt5.symbol_info(symbol)
    if not info or risk_distance <= 0:
        return 0.0
    risk_cash = equity * (risk_percent / 100.0)
    tick_value = info.trade_tick_value or 0.0
    tick_size = info.trade_tick_size or info.point or 0.0
    if tick_value <= 0 or tick_size <= 0:
        return 0.0
    loss_per_lot = (risk_distance / tick_size) * tick_value
    if loss_per_lot <= 0:
        return 0.0
    lot = risk_cash / loss_per_lot
    step = info.volume_step or 0.01
    lot = max(info.volume_min, min(info.volume_max, round(lot / step) * step))
    return round(lot, 2)


def open_position(symbol: str, sig: Dict, lot: float, dry_run: bool) -> Optional[int]:
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return None
    is_buy = sig["direction"] == "BUY"
    price = tick.ask if is_buy else tick.bid
    r = sig["risk_distance"]
    tp = price + TP_R * r if is_buy else price - TP_R * r

    if dry_run:
        log.info("[DRY] %s %s lot=%.2f entry=%.5f sl=%.5f tp=%.5f",
                 sig["direction"], symbol, lot, price, sig["stop"], tp)
        return None

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sig["stop"],
        "tp": tp,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": "proscalper",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        log.error("order failed %s: %s", symbol, getattr(res, "comment", mt5.last_error()))
        return None
    log.info("OPEN %s %s lot=%.2f @%.5f sl=%.5f tp=%.5f ticket=%s",
             sig["direction"], symbol, lot, price, sig["stop"], tp, res.order)
    return res.order


def close_position(pos, volume: Optional[float] = None, reason: str = "") -> bool:
    tick = mt5.symbol_info_tick(pos.symbol)
    if not tick:
        return False
    is_buy = pos.type == mt5.POSITION_TYPE_BUY
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": pos.symbol,
        "volume": volume or pos.volume,
        "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
        "position": pos.ticket,
        "price": tick.bid if is_buy else tick.ask,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": f"proscalper:{reason}"[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    ok = res is not None and res.retcode == mt5.TRADE_RETCODE_DONE
    log.info("CLOSE %s %s vol=%.2f reason=%s -> %s",
             pos.symbol, pos.ticket, volume or pos.volume, reason, "OK" if ok else "FAIL")
    return ok


def modify_stop(pos, new_sl: float) -> bool:
    res = mt5.order_send({
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": pos.symbol,
        "position": pos.ticket,
        "sl": new_sl,
        "tp": pos.tp,
    })
    return res is not None and res.retcode == mt5.TRADE_RETCODE_DONE


def my_positions(symbol: Optional[str] = None) -> List:
    pos = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    return [p for p in (pos or []) if p.magic == MAGIC_NUMBER]


# =============================================================================
# POSITION MANAGEMENT -- partial, breakeven, trail, reversal exit
# =============================================================================

def manage_position(pos, df, sig: Optional[Dict], state: Dict, dry_run: bool) -> None:
    """
    `sig` is the current candle's signal (may be None). A signal in the
    OPPOSITE direction is treated as invalidation and closes the trade --
    that is the "auto exit if reverse" behaviour, and it is deliberately
    evaluated on CLOSED bars so an intra-bar spike cannot trigger it.
    """
    is_buy = pos.type == mt5.POSITION_TYPE_BUY
    tick = mt5.symbol_info_tick(pos.symbol)
    if not tick:
        return
    price = tick.bid if is_buy else tick.ask

    st = state.setdefault(pos.ticket, {"partial_done": False, "entry": pos.price_open})
    risk = abs(pos.price_open - pos.sl) if pos.sl else 0.0
    if risk <= 0:
        return
    r_mult = ((price - pos.price_open) if is_buy else (pos.price_open - price)) / risk

    # --- 1. reversal exit -------------------------------------------------
    if sig and ((is_buy and sig["direction"] == "SELL") or (not is_buy and sig["direction"] == "BUY")):
        if not dry_run:
            close_position(pos, reason="reverse")
        else:
            log.info("[DRY] would close %s on reversal", pos.ticket)
        state.pop(pos.ticket, None)
        return

    # --- 2. partial + breakeven ------------------------------------------
    if not st["partial_done"] and r_mult >= PARTIAL_R:
        half = round(pos.volume / 2, 2)
        info = mt5.symbol_info(pos.symbol)
        if info and half >= info.volume_min:
            if dry_run:
                log.info("[DRY] would bank half of %s at %.2fR", pos.ticket, r_mult)
            elif close_position(pos, volume=half, reason="partial"):
                st["partial_done"] = True
                spread = live_spread(pos.symbol)
                be = pos.price_open + spread if is_buy else pos.price_open - spread
                remaining = [p for p in my_positions(pos.symbol) if p.ticket == pos.ticket]
                if remaining:
                    modify_stop(remaining[0], be)
                    log.info("breakeven set on %s @%.5f", pos.ticket, be)

    # --- 3. trail behind the previous closed candle -----------------------
    if TRAIL_AFTER_PARTIAL and st["partial_done"] and df is not None and len(df) >= 2:
        prev = df.iloc[-1]
        new_sl = float(prev["low"]) if is_buy else float(prev["high"])
        better = (is_buy and new_sl > pos.sl) or (not is_buy and (pos.sl == 0 or new_sl < pos.sl))
        safe = (is_buy and new_sl < price) or (not is_buy and new_sl > price)
        if better and safe and not dry_run:
            if modify_stop(pos, new_sl):
                log.info("trail %s -> %.5f", pos.ticket, new_sl)


# =============================================================================
# MAIN LOOP
# =============================================================================

def run(args) -> int:
    tf = TIMEFRAMES[args.timeframe]
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    for s in symbols:
        mt5.symbol_select(s, True)

    acct = mt5.account_info()
    baseline = load_or_init_baseline(args.data_dir, acct.equity)
    floor = baseline * (1 - EQUITY_STOP_PERCENT / 100.0)
    log.info("session baseline equity=%.2f | 20%% kill switch at %.2f", baseline, floor)

    state: Dict = {}
    last_bar: Dict[str, object] = {}
    trade_times: Dict[str, List[float]] = {}

    while True:
        acct = mt5.account_info()
        if not acct:
            log.error("lost account info; retrying")
            time.sleep(5)
            continue

        # ---- kill switch, checked before anything else -------------------
        if acct.equity <= floor:
            log.critical("EQUITY STOP: equity %.2f <= floor %.2f (-%.1f%%). Flattening and exiting.",
                         acct.equity, floor, EQUITY_STOP_PERCENT)
            for p in my_positions():
                close_position(p, reason="equity_stop")
            return 2

        for symbol in symbols:
            try:
                df = fetch_closed_candles(symbol, tf)
                if df is None or df.empty:
                    continue
                bar_time = df.index[-1]
                spread = live_spread(symbol)
                sig = candle_signal(df, spread)

                # manage first: an existing position's reversal exit outranks
                # any new entry on the same bar.
                for p in my_positions(symbol):
                    manage_position(p, df, sig, state, args.dry_run)

                if last_bar.get(symbol) == bar_time:
                    continue                       # one decision per candle
                last_bar[symbol] = bar_time

                if not sig:
                    continue

                open_now = my_positions()
                same_symbol = [p for p in open_now if p.symbol == symbol]
                if same_symbol and not args.allow_flip:
                    continue
                if len(open_now) >= MAX_OPEN_POSITIONS:
                    log.debug("%s skipped: %d positions already open", symbol, len(open_now))
                    continue

                now = time.time()
                hist = [t for t in trade_times.get(symbol, []) if now - t < 3600]
                trade_times[symbol] = hist
                if len(hist) >= MAX_TRADES_PER_SYMBOL_PER_HOUR:
                    log.info("%s churn brake: %d trades in the last hour", symbol, len(hist))
                    continue

                lot = calc_lot(symbol, acct.equity, args.risk_percent, sig["risk_distance"])
                if lot <= 0:
                    log.warning("%s lot sizing returned 0 -- skipping", symbol)
                    continue

                if open_position(symbol, sig, lot, args.dry_run):
                    trade_times[symbol].append(now)

            except Exception as e:                 # one bad symbol must not kill the loop
                log.exception("error on %s: %s", symbol, e)

        time.sleep(args.poll_seconds)


def main() -> int:
    p = argparse.ArgumentParser(description="proscalper -- aggressive per-candle scalper (standalone)")
    p.add_argument("--login", type=int)
    p.add_argument("--password")
    p.add_argument("--server")
    p.add_argument("--mt5-path", dest="mt5_path", help="path to terminal64.exe for a portable instance")
    p.add_argument("--symbols", default="XAUUSDm,EURUSDm")
    p.add_argument("--timeframe", default="M1", choices=list(TIMEFRAMES.keys()))
    p.add_argument("--risk-percent", type=float, default=DEFAULT_RISK_PERCENT)
    p.add_argument("--poll-seconds", type=float, default=2.0)
    p.add_argument("--allow-flip", action="store_true",
                   help="allow opening the opposite side on the same bar a position was reversed out of")
    p.add_argument("--dry-run", action="store_true", help="log decisions, place no orders")
    p.add_argument("--data-dir", default=".")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(os.path.join(args.data_dir, "proscalper.log"), encoding="utf-8")],
    )

    if not connect(args.login, args.password, args.server, args.mt5_path):
        return 1
    try:
        return run(args)
    except KeyboardInterrupt:
        log.info("stopped by user")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
