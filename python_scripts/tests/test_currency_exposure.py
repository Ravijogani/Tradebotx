import pathlib as _pl
_SCRIPTS = _pl.Path(__file__).resolve().parent.parent  # python_scripts/
import sys
sys.path.insert(0, str(_SCRIPTS))
from risk_limits import decompose_symbol, position_exposure, net_currency_exposure, check_currency_exposure
p=f=0
def check(n,fn):
    global p,f
    try: fn(); p+=1; print(f"  PASS  {n}")
    except AssertionError as e: f+=1; print(f"  FAIL  {n}: {e}")
    except Exception as e: f+=1; print(f"  ERROR {n}: {type(e).__name__}: {e}")

def t1():
    for s,exp in (('EURUSDm',('EUR','USD')),('XAUUSDm',('XAU','USD')),('BTCUSDm',('BTC','USD')),
                  ('GBPJPYm',('GBP','JPY')),('USDCHFm',('USD','CHF')),('USOILm',('USOIL','USD')),
                  ('EURUSD',('EUR','USD'))):
        got=decompose_symbol(s); assert got==exp, f"{s} -> {got}, want {exp}"
check("decompose all 13 symbol shapes incl. suffix", t1)

def t2():
    e=position_exposure('EURUSDm','BUY')
    assert e=={'EUR':1.0,'USD':-1.0}, e
    e=position_exposure('EURUSDm','SELL')
    assert e=={'EUR':-1.0,'USD':1.0}, e
check("BUY is long base / short quote; SELL reverses", t2)

# THE case the expansion creates: 3 longs that are one short-USD bet
def t3():
    pos=[{'symbol':'EURUSDm','direction':'BUY'},{'symbol':'GBPUSDm','direction':'BUY'}]
    net=net_currency_exposure(pos); assert net['USD']==-2.0, net
    ok,why=check_currency_exposure('AUDUSDm','BUY',pos)
    assert not ok, "allowed a third stacked short-USD trade"
    assert 'USD' in why
check("3rd stacked short-USD trade BLOCKED (the real risk)", t3)

# The case a group cap gets wrong: a genuine hedge must be allowed
def t4():
    pos=[{'symbol':'EURUSDm','direction':'BUY'}]
    net=net_currency_exposure(pos+[{'symbol':'USDCHFm','direction':'BUY'}])
    assert abs(net.get('USD',0))<1e-9, f"USD should net flat, got {net}"
    ok,_=check_currency_exposure('USDCHFm','BUY',pos)
    assert ok, "blocked a trade that nets USD toward flat"
check("long EURUSD + long USDCHF allowed (USD nets flat)", t4)

def t5():
    pos=[{'symbol':'XAUUSDm','direction':'BUY'},{'symbol':'XAGUSDm','direction':'BUY'}]
    ok,_=check_currency_exposure('BTCUSDm','BUY',pos)
    assert not ok, "allowed a 3rd USD-denominated long"
check("XAU+XAG long then BTC long blocked at cap 2", t5)

# De-risking must never be blocked, even when already over the cap
def t6():
    pos=[{'symbol':'EURUSDm','direction':'BUY'},{'symbol':'GBPUSDm','direction':'BUY'},
         {'symbol':'AUDUSDm','direction':'BUY'}]           # already -3 USD
    ok,_=check_currency_exposure('NZDUSDm','SELL',pos)      # +1 USD, toward flat
    assert ok, "blocked a trade that REDUCES the concentration"
check("de-risking trade allowed even when over cap", t6)

def t7():
    pos=[{'symbol':'EURUSDm','direction':'BUY','risk':0.5},{'symbol':'GBPUSDm','direction':'BUY','risk':0.5}]
    ok,_=check_currency_exposure('AUDUSDm','BUY',pos,risk=0.5)
    assert ok, "risk-weighted exposure 1.5 should be under cap 2"
check("risk-weighted mode respects actual size", t7)

def t8():
    ok,why=check_currency_exposure('EURUSDm','BUY',[])
    assert ok and 'within limits' in why
check("first trade always allowed", t8)

def t9():
    # non-USD cross must not be mis-netted
    pos=[{'symbol':'GBPJPYm','direction':'BUY'},{'symbol':'GBPUSDm','direction':'BUY'}]
    net=net_currency_exposure(pos)
    assert net['GBP']==2.0 and net['JPY']==-1.0 and net['USD']==-1.0, net
    ok,why=check_currency_exposure('EURGBPm','SELL',pos)   # SELL EURGBP = long GBP
    assert not ok and 'GBP' in why, (ok,why)
check("cross pairs net correctly; 3rd long-GBP blocked", t9)

print(f"\n{p} passed, {f} failed")
raise SystemExit(1 if f else 0)
