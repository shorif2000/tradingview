"""
A minimum reward, learned from someone else's signals losing money.

The SIGNAL MASTER ELITE Telegram channel posts gold zones with a fixed shape:
a $5-6 zone, a stop $5 beyond the far edge, and targets at $5 / $10 / $15 from
the near edge. Measured against 1M bars over 12 timestamped setups, a limit at
the near edge of the zone - the edge price reaches FIRST, so the one that
actually fills - gives:

    stop $10.10, TP1 $5  ->  R:R of 0.49 to 1
    6 wins, 5 losses, 1 open  ->  -0.166R

Half the trades hit TP1 and it still loses, because the reward is half the risk.
That is not a bad-luck sample; it is arithmetic. A 0.49:1 trade needs a 67% win
rate to break even and it won 50%.

Our engine has the mirror-image hole. `f_plan` refuses a trade whose target is
more than `planMaxR` away - the move is too big to count on - but there is NO
FLOOR. If the higher-timeframe target happens to sit just past the entry, the
trade is taken at whatever tiny reward is on offer, exactly the shape that is
losing money for that channel.

This measures what a floor does, on the two periods of opposite market
direction that every other claim in this repo is held to.
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import predict as Q
from predict import htf_target, struct_stop
from predict6 import boot

FLOOR, CAP, K = 0.50, 6.0, 0.25


def run(P, *, minr=0.0, k=K, floor=FLOOR, cap=CAP, valid=48, piv=5,
        spread=0.20, max_hold=240):
    A, H, L, C, n = P["A"], P["H"], P["L"], P["C"], P["n"]
    rows = []
    busy = -1
    for i in range(60, n - 2):
        if i <= busy:
            continue
        src = i - piv
        if src < 1:
            continue
        for side, isp, lvl in (("long", P["pl"][src], L[src]),
                               ("short", P["ph"][src], H[src])):
            if not isp or i <= busy:
                continue
            a = A[i]
            if not np.isfinite(a) or a <= 0:
                continue
            seg = slice(src + 1, i + 1)
            if side == "long" and L[seg].min() < lvl:
                continue
            if side == "short" and H[seg].max() > lvl:
                continue
            tp = htf_target(P, i, side)
            if tp is None:
                continue
            limit = lvl - k * a if side == "long" else lvl + k * a
            ei = None
            for j in range(i + 1, min(i + 1 + valid, n)):
                hit = L[j] <= limit if side == "long" else H[j] >= limit
                if hit:
                    ei = j
                    break
                gone = C[j] < limit - 0.6 * a if side == "long" else C[j] > limit + 0.6 * a
                if gone:
                    break
            if ei is None:
                continue
            fill = limit + spread / 2 if side == "long" else limit - spread / 2
            sv = struct_stop(P, src, side, lvl)
            mn = floor * a
            stop = (fill - mn if side == "long" else fill + mn) if sv is None else \
                   (sv - 0.10 * a if side == "long" else sv + 0.10 * a)
            if abs(fill - stop) < mn:
                stop = fill - mn if side == "long" else fill + mn
            if abs(fill - stop) > 2.5 * a:
                continue
            risk = abs(fill - stop)
            if risk <= 0:
                continue
            if (side == "long" and tp <= fill) or (side == "short" and tp >= fill):
                continue
            rr = abs(tp - fill) / risk
            if rr > cap:
                continue
            # THE NEW RULE. Below this, the trade is the Telegram shape: a real
            # stop against a reward too small to pay for it.
            if rr < minr:
                continue
            why = px = None
            m = ei + 1
            for m in range(ei + 1, min(ei + max_hold, n)):
                hs = L[m] <= stop if side == "long" else H[m] >= stop
                ht = H[m] >= tp if side == "long" else L[m] <= tp
                if hs:
                    why, px = "sl", stop
                    break
                if ht:
                    why, px = "tp", tp
                    break
            if why is None:
                m = min(ei + max_hold - 1, n - 1)
                why, px = "time", C[m]
            mv = px - fill if side == "long" else fill - px
            rows.append(dict(r=mv / risk, rr=rr, risk=risk, why=why))
            busy = m
    return pd.DataFrame(rows)


print("=" * 104)
print("Minimum reward floor. Every row must be positive in BOTH periods, as usual.")
print("=" * 104)
print(f"{'minimum R:R':<14}" + "".join(f"{nm:>24}" for nm in Q.SAMPLES) + "   pooled")

best = None
for minr in (0.0, 1.0, 1.5, 2.0, 2.5, 3.0):
    cells, per, allr = [], {}, []
    for nm, P in Q.PREP.items():
        t = run(P, minr=minr)
        if len(t) < 8:
            per[nm] = np.nan
            cells.append(f"{'too few':>24}")
            continue
        per[nm] = t.r.mean()
        allr.append(t.r.to_numpy())
        cells.append(f"{t.r.mean():+.3f} win{(t.r>0).mean()*100:4.1f}% n{len(t):<4}")
    if not allr:
        print(f"{('none' if minr==0 else str(minr)):<14}" + "".join(cells))
        continue
    r = np.concatenate(allr)
    lo, hi, p = boot(r)
    srt = np.sort(r)[::-1]
    both = all(np.isfinite(v) and v > 0 for v in per.values())
    lab = "none (today)" if minr == 0 else f"{minr:.1f}R"
    print(f"{lab:<14}" + "".join(f"{c:>24}" for c in cells) +
          f"   {r.mean():+.3f}R CI[{lo:+.2f},{hi:+.2f}] P{p*100:5.1f}% "
          f"-top3 {srt[3:].mean():+.3f}" + ("  BOTH+" if both else ""))

print("\nWhat share of today's trades are below each floor?")
allrr = []
for nm, P in Q.PREP.items():
    allrr.append(run(P, minr=0.0).rr.to_numpy())
rr = np.concatenate(allrr)
for f in (1.0, 1.5, 2.0, 2.5, 3.0):
    print(f"  below {f:.1f}R: {(rr < f).mean()*100:4.1f}% of trades")
print(f"  median reward asked: {np.median(rr):.2f}R")
