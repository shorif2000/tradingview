"""Round 2: a real higher-timeframe gate, and the ADX filter combined with exits."""
import warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from paths import dataset
from xau_engine import ema, atr as atr_fn, dmi
from rf_lib import rf_signals, smooth_range, range_filter
import improve as I   # reuse run()/PREP

def htf_state(d, rule):
    """Range-filter direction computed on genuinely higher-timeframe bars,
    then forward-filled onto the trading bars. No look-ahead: an HTF bar's
    state is only applied after that bar has closed."""
    ht = d.close.resample(rule, label="right", closed="right").last().dropna()
    r = smooth_range(ht, 38, 1.8)
    f = pd.Series(range_filter(ht, r), index=ht.index)
    up = (ht > f).astype(int).replace(0, -1)
    return up.reindex(d.index, method="ffill")

RULES = {"2M Jan":"1h","3M Jan":"1h","5M Jan":"1h","5M Jun-Aug":"1h"}
for nm,(sg,m1) in I.PREP.items():
    sg["htf"] = htf_state(sg, RULES[nm])

def gated(sg, mode):
    d = sg.copy()
    want_long  = d.htf > 0 if mode=="agree" else d.htf < 0
    want_short = d.htf < 0 if mode=="agree" else d.htf > 0
    d["rf_long"]  = d.rf_long  & want_long
    d["rf_short"] = d.rf_short & want_short
    return d

def ev(label, gate=None, **kw):
    jan, jun = [], None
    for nm,(sg,m1) in I.PREP.items():
        s = gated(sg, gate) if gate else sg
        tr = I.run(s, m1, **kw)
        if nm=="5M Jun-Aug": jun = tr
        else: jan.append(tr)
    jan = pd.concat(jan)
    if len(jan)==0 or jun is None or len(jun)==0: return None
    je,ue = jan.r.mean(), jun.r.mean()
    return dict(label=label, jn=len(jan), jr=je, jw=(jan.r>0).mean()*100,
                un=len(jun), ur=ue, uw=(jun.r>0).mean()*100, ok=(je>0 and ue>0))

CFG = [
 ("HTF agree",                 dict(gate="agree")),
 ("HTF oppose (fade)",         dict(gate="oppose")),
 ("HTF agree + adx>=20",       dict(gate="agree", min_adx=20)),
 ("HTF oppose + adx>=20",      dict(gate="oppose", min_adx=20)),
 ("adx>=15",                   dict(min_adx=15)),
 ("adx>=18",                   dict(min_adx=18)),
 ("adx>=20 (repeat)",          dict(min_adx=20)),
 ("adx>=22",                   dict(min_adx=22)),
 ("adx>=20 partial exit",      dict(min_adx=20, exit_mode="partial")),
 ("adx>=20 flip exit",         dict(min_adx=20, exit_mode="flip")),
 ("adx>=20 3R",                dict(min_adx=20, rr=3.0)),
 ("adx>=20 wide stop 1.8ATR",  dict(min_adx=20, sl_mult=1.8)),
]
print(f"{'config':<26} {'Jan n':>6} {'Jan R':>8} {'Jan win':>8} | {'Jun n':>6} {'Jun R':>8} {'Jun win':>8}  verdict")
rows=[]
for lab,kw in CFG:
    r = ev(lab, **kw)
    if not r: print(f"{lab:<26} (no trades)"); continue
    print(f"{r['label']:<26} {r['jn']:>6} {r['jr']:>+8.3f} {r['jw']:>7.1f}% | "
          f"{r['un']:>6} {r['ur']:>+8.3f} {r['uw']:>7.1f}%  {'BOTH POSITIVE' if r['ok'] else ''}")
    rows.append(r)
pd.DataFrame(rows).to_csv("improve2.csv", index=False)
