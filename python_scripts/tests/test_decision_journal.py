import pathlib as _pl
_SCRIPTS = _pl.Path(__file__).resolve().parent.parent  # python_scripts/
import sys
sys.path.insert(0, str(_SCRIPTS))
import decision_journal as dj

passed = failed = 0
def check(name, cond):
    global passed, failed
    if cond: passed += 1; print(f"PASS: {name}")
    else: failed += 1; print(f"FAIL: {name}")

j = dj.DecisionJournal("XAUUSDm", "BUY", "SHAAKUNI_SSM", at="2026-06-01T10:00:00Z")
j.note(dj.BIAS, "h4_bias", dj.CONFIRMED, "H4 macro bias BULLISH")
j.note(dj.LIQUIDITY, "htf_sweep", dj.CONFIRMED, "H1 swept prior low, closed back above")
j.note(dj.LOCATION, "premium_discount", dj.AGAINST, "price in PREMIUM for a BUY")
j.note(dj.REGIME, "auction_state", dj.WEAK, "IMBALANCE_UP but marginal")
j.note(dj.TIMING, "rollover", dj.NEUTRAL, "outside rollover window")
j.measure(rr=2.3, atr=4.1, spread=0.28)
j.decide(True, "mandatory checks passed, RR 2.3")

check("confirmations include CONFIRMED and WEAK", set(j.confirmations()) == {"h4_bias","htf_sweep","auction_state"})
check("objections include AGAINST", j.objections() == ["premium_discount"])
check("NEUTRAL is neither confirmation nor objection", "rollover" not in j.confirmations() + j.objections())
check("headline mentions the case", "H4 macro bias BULLISH" in j.headline())
check("headline surfaces objections via 'despite'", "despite" in j.headline())
check("numbers captured", j.to_dict()["numbers"]["rr"] == 2.3)
check("taken recorded", j.to_dict()["taken"] is True)
check("chaining returns self", isinstance(j.note(dj.RISK,"x",dj.NEUTRAL), dj.DecisionJournal))

# management + exit
j.action("moved_to_breakeven", "price reached 1:1 R", at="2026-06-01T11:00:00Z", trigger_r=1.0)
j.action("partial_close", "1.5R hit, closed 60%", at="2026-06-01T11:30:00Z", pct=60)
d = j.to_dict()
check("management actions recorded in order", [m["what"] for m in d["management"]] == ["moved_to_breakeven","partial_close"])
check("management extras preserved", d["management"][0]["trigger_r"] == 1.0)

j.closed("SL", "stop swept then price resumed our direction", r_multiple=-1.0, at="2026-06-01T12:00:00Z")
d = j.to_dict()
check("exit outcome + attributable reason", d["exit"]["outcome"] == "SL" and "resumed our direction" in d["exit"]["reason"])
check("exit r_multiple", d["exit"]["r_multiple"] == -1.0)

# a not-taken (vetoed) journal -- the rejected-setup case
jv = dj.DecisionJournal("EURUSDm", "SELL", "EMA_SCALP_CROSS")
jv.note(dj.REGIME, "regime_router", dj.VETO, "BALANCE -- stand aside")
jv.decide(False, "regime router vetoed")
check("veto counts as objection", jv.objections() == ["regime_router"])
check("not-taken recorded", jv.to_dict()["taken"] is False)

# --- the payoff: summarize_by_confirmation ---
def mk(key_verdicts, r):
    x = dj.DecisionJournal("XAUUSDm", "BUY", "SSM")
    for k, v in key_verdicts.items():
        x.note(dj.LIQUIDITY, k, v, "")
    x.closed("TP" if r > 0 else "SL", "test", r_multiple=r)
    return x.to_dict()

journals = [
    mk({"sweep": dj.CONFIRMED, "pd": dj.CONFIRMED}, 2.0),
    mk({"sweep": dj.CONFIRMED, "pd": dj.AGAINST},  1.5),
    mk({"sweep": dj.CONFIRMED, "pd": dj.CONFIRMED}, 2.5),
    mk({"sweep": dj.AGAINST,   "pd": dj.CONFIRMED}, -1.0),
    mk({"sweep": dj.AGAINST,   "pd": dj.AGAINST},  -1.0),
]
summary = dj.summarize_by_confirmation(journals)
check("sweep present_n correct", summary["sweep"]["present_n"] == 3)
check("sweep absent_n correct", summary["sweep"]["absent_n"] == 2)
check("sweep present avg R = 2.0", abs(summary["sweep"]["present_avg_r"] - 2.0) < 1e-9)
check("sweep absent avg R = -1.0", abs(summary["sweep"]["absent_avg_r"] - (-1.0)) < 1e-9)
check("sweep has strong positive edge", abs(summary["sweep"]["edge"] - 3.0) < 1e-9)
# pd is a weaker/misleading confirmation in this fixture
check("pd edge computed and smaller than sweep", summary["pd"]["edge"] < summary["sweep"]["edge"])

# a confirmation that is actively anti-correlated should show a NEGATIVE edge
anti = [
    mk({"bad": dj.CONFIRMED}, -1.0),
    mk({"bad": dj.CONFIRMED}, -0.5),
    mk({"bad": dj.AGAINST},   2.0),
]
s2 = dj.summarize_by_confirmation(anti)
check("anti-correlated confirmation shows negative edge", s2["bad"]["edge"] < 0)

# trades with no outcome yet must be excluded, not counted as zero
open_j = dj.DecisionJournal("XAUUSDm","BUY","SSM"); open_j.note(dj.LIQUIDITY,"sweep",dj.CONFIRMED,"")
s3 = dj.summarize_by_confirmation(journals + [open_j.to_dict()])
check("open trades excluded from stats", s3["sweep"]["present_n"] == 3)


# ---------------- attribute_live_exit ----------------
print("\n-- attribute_live_exit --")
A = dj.attribute_live_exit
def buy(exit_px, reason, **kw): return A('BUY',100.0,99.0,103.0,exit_px,reason,**kw)

check("TP -> target_hit", 'target_hit' in buy(103.0,'TP',mfe_r=3.0))
check("spread spike caught first (12s)", 'spread_spike_sl' in buy(99.0,'SL',held_seconds=12,mfe_r=0.0))
check("gave back a winner (2R then flat)", 'gave_back_a_winner' in buy(100.0,'SL',mfe_r=2.0,held_seconds=3600))
check("never went our way (MFE 0.1R)", 'never_went_our_way' in buy(99.0,'SL',mfe_r=0.1,held_seconds=3600))
check("partial recovery (MFE 0.6R)", 'partial_recovery' in buy(99.0,'SL',mfe_r=0.6,held_seconds=3600))
check("stopped at breakeven", 'stopped_at_breakeven' in buy(100.0,'SL',be_moved=True,mfe_r=0.8,held_seconds=3600))
check("partial then stopped", 'partial_then_stopped' in buy(99.0,'SL',partial_taken=True,mfe_r=1.5,held_seconds=3600))
check("no MFE data -> honest fallback", 'no favourable-excursion data' in buy(99.0,'SL',held_seconds=3600))
check("exit-engine close labelled", 'exit_engine' in buy(99.5,'EXIT_ENGINE',held_seconds=3600).lower())
check("SELL side mirrors correctly",
      'never_went_our_way' in A('SELL',100.0,101.0,97.0,101.0,'SL',mfe_r=0.05,held_seconds=3600))
check("spread spike outranks gave_back", 'spread_spike' in buy(99.0,'SL',mfe_r=2.0,held_seconds=5))
check("zero SL distance safe", isinstance(A('BUY',100.0,100.0,103.0,99.0,'SL',mfe_r=None), str))

# ---------------- rejection sink ----------------
print("\n-- rejection sink --")
dj.drain_rejections()
rj = dj.DecisionJournal("XAUUSDm","BUY","SSM"); rj.note(dj.LIQUIDITY,"htf_sweep",dj.VETO,"none"); rj.decide(False,"no sweep")
dj.record_rejection(rj)
drained = dj.drain_rejections()
check("rejection recorded", len(drained)==1 and drained[0]["taken"] is False)
check("drain clears the buffer", dj.drain_rejections()==[])
funnel = dj.rejection_funnel([rj.to_dict()])
check("funnel attributes the first veto", funnel.get("SSM",{}).get("htf_sweep")==1)
# bounded buffer + truncation reported
saved = dj._MAX_REJECTIONS
dj._MAX_REJECTIONS = 3
for _ in range(10): dj.record_rejection(rj)
d2 = dj.drain_rejections()
check("buffer is bounded", sum(1 for x in d2 if not x.get("_meta"))==3)
check("truncation is reported, not hidden", any(x.get("_meta")=="rejections_dropped" for x in d2))
dj._MAX_REJECTIONS = saved
dj.drain_rejections()

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
