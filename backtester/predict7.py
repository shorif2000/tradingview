"""
Neighbourhood robustness for the one row that survived.

predict6 killed the +0.972R headline: with a placeable stop floor it falls to
+0.02R and goes negative once the three biggest winners are removed. It was
division by nearly zero.

But one configuration survived every test applied to it:

  HTF target, capped at 6R, stop floor 0.50 x ATR
  +0.523R pooled, CI [+0.13,+0.93], P(no edge) 0.3%, 35% win rate,
  and STILL +0.392R after deleting the three largest winners.

That is the strongest result in this project. Which is precisely why it should
be distrusted: I chose that cap and that floor after looking at the table, and
fifteen rows were on the table. Established earlier in this work, on synthetic
zero-edge data, roughly 25% of configurations pass "positive in both periods" by
luck alone. One row out of fifteen passing loudly is not yet evidence.

The test that has repeatedly separated real effects from noise here is whether
the NEIGHBOURS also work. A genuine edge is a plateau - move the cap, the floor,
the anticipation distance, the pivot definition, and it degrades gracefully. An
artifact is a spike: its neighbours are ordinary.

Pass mark: comfortably more than 25% of the neighbourhood positive in both
periods, and the centre should not be the only strong cell.
"""
from __future__ import annotations
import warnings
import itertools
import numpy as np

warnings.filterwarnings("ignore")
import predict as Q
from predict import prep
from predict6 import run_floor, boot


def cell(k, floor, cap, PREP):
    out = {}
    allr = []
    for nm, P in PREP.items():
        t = run_floor(P, k=k, floor=floor, tgt="htf", cap=cap)
        if len(t) < 8:
            return None
        out[nm] = t.r.mean()
        allr.append(t.r.to_numpy())
    r = np.concatenate(allr)
    return dict(both=all(v > 0 for v in out.values()), pooled=r.mean(),
                n=len(r), r=r, per=out)


KS = [0.15, 0.25, 0.35]
FLOORS = [0.40, 0.50, 0.60]
CAPS = [4.0, 6.0, 8.0]

print("=" * 76)
print("Neighbourhood of (k 0.25, floor 0.50, cap 6R). Centre marked *.")
print("Each cell: pooled R, and + if positive in BOTH periods.")
print("=" * 76)
res = {}
for k, f, c in itertools.product(KS, FLOORS, CAPS):
    res[(k, f, c)] = cell(k, f, c, Q.PREP)

for c in CAPS:
    print(f"\ncap {c:.0f}R" + "".join(f"{'floor '+format(f,'.2f'):>16}" for f in FLOORS))
    for k in KS:
        line = f"  k {k:.2f}"
        for f in FLOORS:
            v = res[(k, f, c)]
            if v is None:
                line += f"{'-':>16}"
                continue
            star = "*" if (k, f, c) == (0.25, 0.50, 6.0) else " "
            line += f"{v['pooled']:+.3f}{'+' if v['both'] else ' '}{star:>2} n{v['n']:<3}".rjust(16)
        print(line)

ok = [v for v in res.values() if v is not None]
passed = sum(v["both"] for v in ok)
print(f"\npositive in both periods: {passed}/{len(ok)} = {passed/len(ok)*100:.0f}%"
      f"   (noise baseline for this test is ~25%)")
print(f"median pooled across the grid: {np.median([v['pooled'] for v in ok]):+.3f}R")
print(f"cells above +0.30R: {sum(v['pooled'] > 0.30 for v in ok)}/{len(ok)}")

# structural sensitivity: does it survive redefining the swing pivot itself?
print("\n" + "=" * 76)
print("Redefining the level: pivot width and higher-timeframe choice")
print("=" * 76)
import predict as _Q
for piv in (3, 5, 7):
    for htf in (60, 240):
        P2 = {nm: prep(d, htf_min=htf, piv=piv) for nm, d in _Q.SAMPLES.items()}
        allr, per = [], {}
        for nm, P in P2.items():
            t = run_floor(P, k=0.25, floor=0.50, tgt="htf", cap=6.0, piv=piv)
            if len(t) < 8:
                per[nm] = np.nan
                continue
            per[nm] = t.r.mean()
            allr.append(t.r.to_numpy())
        if not allr:
            print(f"  piv {piv}  htf {htf}min   too few")
            continue
        r = np.concatenate(allr)
        lo, hi, p = boot(r)
        srt = np.sort(r)[::-1]
        both = all(np.isfinite(v) and v > 0 for v in per.values())
        tag = "  <- as tested" if (piv, htf) == (5, 60) else ""
        print(f"  piv {piv}  htf {htf:>3}min   {r.mean():+.3f}R  CI[{lo:+.2f},{hi:+.2f}]  "
              f"P{p*100:5.1f}%  n{len(r):<4} -top3 {srt[3:].mean():+.3f}"
              + ("  BOTH+" if both else "") + tag)
