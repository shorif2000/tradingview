"""
Is the HTF-target result real, or is it three lottery tickets?

predict4 produced a striking number: ANTICIPATE + structural stop + higher-
timeframe target = +0.972R pooled, CI [+0.04, +2.24], P(no edge) 1.9%. That
would be an extraordinary edge. But the win rate is 24-28% and the confidence
interval is nine times wider than any other row in the table, which is exactly
the shape you get when a handful of enormous winners carry an otherwise losing
distribution.

This checks that directly, because if it IS a few outliers then the mean is not
something you can trade - you would need to catch those specific trades, and the
median outcome is what you would actually live through.

  - what does the mean become if the best trade is removed? the best three?
  - trimmed mean, median, and the share of total profit from the top 5%
  - how big is the R:R actually being asked for, and how often is it absurd
  - does the edge survive capping the target at a sane distance
"""
from __future__ import annotations
import warnings
import numpy as np

warnings.filterwarnings("ignore")
import predict as Q

CFG = dict(mode="anticipate", k=0.25, stop_mode="structure", tgt="htf")
FIX = dict(mode="anticipate", k=0.25, stop_mode="structure", tgt="rr", rr=2.0)


def boot(r, n=8000, seed=13):
    rng = np.random.default_rng(seed)
    r = np.asarray(r, float)
    m = rng.choice(r, (n, len(r)), replace=True).mean(1)
    return np.percentile(m, 2.5), np.percentile(m, 97.5), (m <= 0).mean()


print("=" * 78)
print("ANTICIPATE + structural stop + HTF target: where does the profit come from?")
print("=" * 78)

pool = []
for nm, P in Q.PREP.items():
    t = Q.run(P, **CFG)
    t["sample"] = nm
    pool.append(t)
    r = t.r.to_numpy()
    srt = np.sort(r)[::-1]
    print(f"\n{nm}  n={len(t)}  mean {r.mean():+.3f}R  median {np.median(r):+.3f}R")
    print(f"  best five R: {', '.join(f'{x:+.1f}' for x in srt[:5])}")
    print(f"  drop best 1 -> {srt[1:].mean():+.3f}R    drop best 3 -> {srt[3:].mean():+.3f}R")
    win = r[r > 0]
    print(f"  {len(win)} winners of {len(r)}; top 3 winners are "
          f"{win.sum() and srt[:3].sum() / win.sum() * 100:.0f}% of all gross profit")
    print(f"  R:R demanded  median {t.rr.median():.1f}  p90 {t.rr.quantile(0.9):.1f}  max {t.rr.max():.1f}")
    print(f"  time in trade median {t.bars.median():.0f} bars   exits: "
          + ", ".join(f"{k} {v}" for k, v in t.why.value_counts().items()))

import pandas as pd
A = pd.concat(pool)
r = A.r.to_numpy()
srt = np.sort(r)[::-1]
print("\n" + "-" * 78)
print(f"POOLED n={len(r)}   mean {r.mean():+.3f}R   median {np.median(r):+.3f}R")
lo, hi, p = boot(r)
print(f"  full sample      {r.mean():+.3f}R  CI[{lo:+.2f},{hi:+.2f}]  P(no edge) {p*100:.1f}%")
for d in (1, 3, 5):
    x = srt[d:]
    lo, hi, p = boot(x)
    print(f"  minus top {d:<2}      {x.mean():+.3f}R  CI[{lo:+.2f},{hi:+.2f}]  P(no edge) {p*100:.1f}%")
tr = srt[int(len(srt) * 0.05):]
print(f"  5% trimmed       {tr.mean():+.3f}R")
print(f"  share of gross profit from best 5% of trades: "
      f"{srt[:max(1, int(len(srt)*0.05))].sum() / r[r > 0].sum() * 100:.0f}%")

print("\n" + "-" * 78)
print("Same idea with a CAPPED target, so no single trade can dominate:")
for cap in (2.0, 3.0, 4.0, 6.0):
    allr = []
    ok = {}
    for nm, P in Q.PREP.items():
        t = Q.run(P, **CFG)
        # cap the reward: anything asking for more than `cap` R is refused
        t = t[t.rr <= cap]
        if len(t) < 5:
            ok[nm] = np.nan
            continue
        ok[nm] = t.r.mean()
        allr.append(t.r.to_numpy())
    if not allr:
        continue
    x = np.concatenate(allr)
    lo, hi, p = boot(x)
    both = all(np.isfinite(v) and v > 0 for v in ok.values())
    print(f"  rr<={cap:<4} n={len(x):<4} {x.mean():+.3f}R  CI[{lo:+.2f},{hi:+.2f}]  "
          f"P {p*100:4.1f}%" + ("  BOTH+" if both else ""))

print("\n" + "-" * 78)
print("Fixed 2R target on the same entries and stops (the tradeable version):")
allr = []
ok = {}
for nm, P in Q.PREP.items():
    t = Q.run(P, **FIX)
    ok[nm] = t.r.mean()
    allr.append(t.r.to_numpy())
    print(f"  {nm:<12} {t.r.mean():+.3f}R  win {(t.r>0).mean()*100:.1f}%  n={len(t)}  "
          f"median {t.r.median():+.2f}R")
x = np.concatenate(allr)
lo, hi, p = boot(x)
print(f"  POOLED       {x.mean():+.3f}R  CI[{lo:+.2f},{hi:+.2f}]  P(no edge) {p*100:.1f}%"
      + ("  BOTH+" if all(v > 0 for v in ok.values()) else ""))
