"""Is the improvement real, or a product of testing 31 configurations?"""
import warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
import improve as I
from improve2 import gated
from samples import boot

def pooled(**kw):
    out=[]
    for nm,(sg,m1) in I.PREP.items():
        s = gated(sg, kw.pop("gate")) if kw.get("gate") else sg
        out.append(I.run(s, m1, **{k:v for k,v in kw.items() if k!="gate"}))
    return pd.concat(out)

CAND = {
  "baseline (no filter)":        dict(),
  "adx>=20 + 3R":                dict(min_adx=20, rr=3.0),
  "adx>=20 + 2R":                dict(min_adx=20),
  "HTF oppose":                  dict(gate="oppose"),
}
print(f"{'config':<24} {'n':>6} {'expR':>8} {'win%':>7} {'95% CI':>22} {'P(no edge)':>11}")
res={}
for lab,kw in CAND.items():
    tr = pooled(**dict(kw))
    lo,hi,p = boot(tr.r, seed=1)
    res[lab]=tr
    print(f"{lab:<24} {len(tr):>6} {tr.r.mean():>+8.3f} {(tr.r>0).mean()*100:>6.1f}% "
          f"  [{lo:+.3f}, {hi:+.3f}] {p*100:>10.1f}%")

# What does the winning config earn in money at the only size a GBP100 account can use?
best = res["adx>=20 + 3R"]
days = (pd.DatetimeIndex(best.t).normalize().nunique())
print(f"\nadx>=20 + 3R, 0.01 lots: net GBP{best.pnl.sum():+.2f} over {days} trading days "
      f"= GBP{best.pnl.sum()/days:+.2f}/day, GBP{best.pnl.sum()/days*5:+.2f}/week")

# Multiple-testing reality check: how many of 31 coin-flip configs would come up
# positive in both periods by chance?
rng = np.random.default_rng(7)
hits=0; TRIALS=20000
for _ in range(TRIALS):
    if rng.normal(0,0.30/np.sqrt(500))>0 and rng.normal(0,0.30/np.sqrt(200))>0: hits+=1
p_both = hits/TRIALS
print(f"\nA zero-edge config has a {p_both*100:.0f}% chance of landing positive in both periods.")
print(f"Across 31 configurations tested, expect ~{31*p_both:.1f} false winners.")
print(f"I found 3.")
