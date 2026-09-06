"""
Final head-to-head, and what it means in pounds.

The user's complaint: "the signal appears once the move is done". The fix on
offer is to stop waiting for confirmation and instead rest a limit order at a
level that already exists, with the stop at the market's own invalidation point.

predict7 showed that idea sits on a genuine plateau - 93% of a 27-cell
neighbourhood positive in both periods against a 25% noise baseline, median
+0.253R. This settles the remaining question: is the ANTICIPATION doing the
work, or would confirming with the same target, cap and stop floor do just as
well? Both arms get identical rules from here on, so only the entry differs.

Then the same numbers in pounds at 0.01 lots, because R is not money.
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


def run(P, *, mode, k=K, floor=FLOOR, cap=CAP, valid=48, piv=5,
        spread=0.20, slip=0.10, max_hold=240):
    A, H, L, C, O, n = P["A"], P["H"], P["L"], P["C"], P["O"], P["n"]
    idx = P["idx"]
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

            fill = stop = None
            ei = None
            if mode == "anticipate":
                limit = lvl - k * a if side == "long" else lvl + k * a
                for j in range(i + 1, min(i + 1 + valid, n)):
                    hit = L[j] <= limit if side == "long" else H[j] >= limit
                    if hit:
                        fill = limit + spread / 2 if side == "long" else limit - spread / 2
                        sv = struct_stop(P, src, side, lvl)
                        if sv is None:
                            break
                        stop = sv - 0.10 * a if side == "long" else sv + 0.10 * a
                        ei = j
                        break
                    gone = C[j] < limit - 0.6 * a if side == "long" else C[j] > limit + 0.6 * a
                    if gone:
                        break
            else:
                for j in range(i + 1, min(i + 1 + valid, n)):
                    sweep = (L[j] < lvl and C[j] > lvl) if side == "long" \
                        else (H[j] > lvl and C[j] < lvl)
                    if sweep and j + 1 < n:
                        fill = O[j + 1] + spread / 2 + slip if side == "long" \
                            else O[j + 1] - spread / 2 - slip
                        sv = struct_stop(P, src, side, lvl)
                        base = L[j] if side == "long" else H[j]
                        sv = base if sv is None else (min(sv, base) if side == "long"
                                                      else max(sv, base))
                        stop = sv - 0.10 * a if side == "long" else sv + 0.10 * a
                        ei = j + 1
                        break
                    gone = C[j] < lvl - 0.6 * a if side == "long" else C[j] > lvl + 0.6 * a
                    if gone:
                        break
            if ei is None:
                continue
            mn = floor * a
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
            why = px = None
            scan = ei + 1 if mode == "anticipate" else ei
            for m in range(scan, min(ei + max_hold, n)):
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
            rows.append(dict(t=idx[ei], side=side, r=mv / risk, rr=rr, risk=risk,
                             mins=(m - ei) * 5, why=why))
            busy = m
    return pd.DataFrame(rows)


print("=" * 92)
print("Identical levels, identical stops, identical targets. Only the ENTRY differs.")
print("=" * 92)
store = {}
for mode, lab in (("confirm", "CONFIRM  (wait for the reclaim candle)"),
                  ("anticipate", "ANTICIPATE (resting limit at the level)")):
    allr, per = [], {}
    parts = []
    for nm, P in Q.PREP.items():
        t = run(P, mode=mode)
        per[nm] = t
        allr.append(t.r.to_numpy())
        parts.append(t)
    r = np.concatenate(allr)
    lo, hi, p = boot(r)
    srt = np.sort(r)[::-1]
    A = pd.concat(parts)
    store[mode] = A
    print(f"\n{lab}")
    for nm, t in per.items():
        print(f"   {nm:<12} {t.r.mean():+.3f}R  win {(t.r>0).mean()*100:4.1f}%  n={len(t)}")
    print(f"   POOLED       {r.mean():+.3f}R  CI[{lo:+.2f},{hi:+.2f}]  P(no edge) {p*100:.1f}%")
    print(f"   after removing the 3 best trades: {srt[3:].mean():+.3f}R")
    print(f"   stop size    median ${A.risk.median():.2f}   90th pct ${A.risk.quantile(.9):.2f}")
    print(f"   reward asked median {A.rr.median():.1f}R    time in trade median {A.mins.median():.0f} min")
    print(f"   exits: " + ", ".join(f"{k} {v/len(A)*100:.0f}%" for k, v in A.why.value_counts().items()))

print("\n" + "=" * 92)
print("In pounds, 0.01 lots (1 oz, so $1 move = $1), GBP 1.27, spread already charged")
print("=" * 92)
DAYS = {"5M Jan": 21, "5M Jun-Aug": 64}
for mode in ("confirm", "anticipate"):
    A = store[mode]
    tot_days = sum(DAYS.values())
    pnl = (A.r * A.risk).sum() / 1.27
    n = len(A)
    print(f"\n{mode.upper():<11} {n} trades over ~{tot_days} trading days "
          f"= {n/tot_days:.1f} trades/day")
    print(f"   total  GBP {pnl:+.2f}    per trade GBP {pnl/n:+.2f}    "
          f"per week GBP {pnl/tot_days*5:+.2f}")
    print(f"   average risk per trade  ${A.risk.mean():.2f} = GBP {A.risk.mean()/1.27:.2f}")
    print(f"   on a GBP 100 account that is {A.risk.mean()/1.27:.1f}% per trade at 0.01 lots")
    worst = (A.r * A.risk / 1.27).cumsum()
    dd = (worst - worst.cummax()).min()
    print(f"   worst peak-to-trough drawdown  GBP {dd:.2f}")

print("\n" + "=" * 92)
print("Long vs short, and by hour (London) - anticipate arm")
A = store["anticipate"]
for s in ("long", "short"):
    x = A[A.side == s]
    print(f"   {s:<6} {x.r.mean():+.3f}R  win {(x.r>0).mean()*100:4.1f}%  n={len(x)}")
lon = pd.DatetimeIndex(A.t).tz_convert("Europe/London").hour
for lo_, hi_, lab in [(0, 7, "00-07"), (7, 12, "07-12"), (12, 16, "12-16"),
                      (16, 20, "16-20"), (20, 24, "20-24")]:
    x = A[(lon >= lo_) & (lon < hi_)]
    if len(x) == 0:
        continue
    print(f"   {lab}  {x.r.mean():+.3f}R  win {(x.r>0).mean()*100:4.1f}%  n={len(x)}")
A.to_csv("anticipate_trades.csv", index=False)
print("\nsaved anticipate_trades.csv")
