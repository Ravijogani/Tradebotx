import pathlib as _pl
_SCRIPTS = _pl.Path(__file__).resolve().parent.parent  # python_scripts/
import sys
sys.path.insert(0, str(_SCRIPTS))
import market_intelligence as mi

# TEST 1: IMBALANCE_UP with no m30_char -> TREND_UP, BUY allowed
r = mi.classify_market_regime({"state": "IMBALANCE_UP"}, None)
assert r["regime"] == "TREND_UP", r
assert r["allowed_directions"] == frozenset({"BUY"}), r
print("TEST 1 (TREND_UP, no m30) PASS:", r)

# TEST 2: IMBALANCE_DOWN -> TREND_DOWN, SELL allowed
r = mi.classify_market_regime({"state": "IMBALANCE_DOWN"}, None)
assert r["regime"] == "TREND_DOWN"
assert r["allowed_directions"] == frozenset({"SELL"})
print("TEST 2 (TREND_DOWN) PASS:", r)

# TEST 3: BALANCE -> BALANCE, nothing allowed
r = mi.classify_market_regime({"state": "BALANCE"}, None)
assert r["regime"] == "BALANCE"
assert r["allowed_directions"] == frozenset()
print("TEST 3 (BALANCE stand-aside) PASS:", r)

# TEST 4: None/missing state -> CHOPPY, nothing allowed
r = mi.classify_market_regime({"state": None}, None)
assert r["regime"] == "CHOPPY"
assert r["allowed_directions"] == frozenset()
print("TEST 4 (CHOPPY on no data) PASS:", r)

r2 = mi.classify_market_regime({}, None)
assert r2["regime"] == "CHOPPY"
print("TEST 4b (CHOPPY on empty dict) PASS:", r2)

# TEST 5: TREND_UP + M30 BOS in same direction -> still TREND_UP (confirmed, not vetoed)
r = mi.classify_market_regime({"state": "IMBALANCE_UP"}, {"signal": "BOS", "break_direction": "BULLISH"})
assert r["regime"] == "TREND_UP", r
print("TEST 5 (BOS confirms, no downgrade) PASS:", r)

# TEST 6: TREND_UP + M30 CHOCH BEARISH (conflicting) -> downgraded to CHOPPY
r = mi.classify_market_regime({"state": "IMBALANCE_UP"}, {"signal": "CHOCH", "break_direction": "BEARISH"})
assert r["regime"] == "CHOPPY", r
assert r["allowed_directions"] == frozenset()
assert "conflicting" in r["reason"]
print("TEST 6 (TREND_UP + opposing CHoCH -> CHOPPY) PASS:", r)

# TEST 7: TREND_DOWN + M30 CHOCH BULLISH (conflicting) -> downgraded to CHOPPY
r = mi.classify_market_regime({"state": "IMBALANCE_DOWN"}, {"signal": "CHOCH", "break_direction": "BULLISH"})
assert r["regime"] == "CHOPPY", r
print("TEST 7 (TREND_DOWN + opposing CHoCH -> CHOPPY) PASS:", r)

# TEST 8: TREND_UP + M30 CHOCH BULLISH (same direction -- shouldn't happen per
# classify_m30_character's own semantics, but confirm it does NOT veto if it did)
r = mi.classify_market_regime({"state": "IMBALANCE_UP"}, {"signal": "CHOCH", "break_direction": "BULLISH"})
assert r["regime"] == "TREND_UP", r
print("TEST 8 (CHoCH same-direction does not veto) PASS:", r)

# TEST 9: BALANCE regime ignores m30_char entirely (only applies to TREND_UP/DOWN)
r = mi.classify_market_regime({"state": "BALANCE"}, {"signal": "CHOCH", "break_direction": "BEARISH"})
assert r["regime"] == "BALANCE", r
print("TEST 9 (BALANCE unaffected by m30_char) PASS:", r)

print("\nALL 10 REGIME ROUTER TESTS PASSED")
