"""
The structural stop needs a floor, and that changes the answer.

predict5 showed R:R values of 1,424 and 6,085 to one. That is not a trade, it is
a division by nearly zero: when the nearest confirmed swing sits a few cents from
the fill, `risk` collapses and every dollar the trade earns is scored as hundreds
of R. Those degenerate rows are what produced the +0.972R headline, and they are
untradeable - no broker lets you rest a stop $0.04 from entry, and normal spread
alone would take you out.

So: impose a minimum stop distance, the way a real order would have to, and see
what is left. `floor` is in ATR units; the stop is pushed out to at least that,
which lowers R on the winners honestly rather than deleting the trades.
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import predict as Q
from predict import htf_target, struct_stop


def run_floor(P, *, k=0.25, floor=0.35, valid=48, piv=5, spread=0.20,
              max_hold=240, tgt="rr", rr=2.0, cap=None):
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
            target = htf_target(P, i, side)
            if target is None:
                continue
            limit = lvl - k * a if side == "long" else lvl + k * a
            fill = stop = None
            ei = None
            for j in range(i + 1, min(i + 1 + valid, n)):
                hit = L[j] <= limit if side == "long" else H[j] >= limit
                if hit:
                    fill = limit + spread / 2 if side == "long" else limit - spread / 2
                    sv = struct_stop(P, src, side, lvl)
                    if sv is None:
                        break
                    stop = sv - 0.10 * a if side == "long" else sv + 0.10 * a
                    # THE FIX: a stop closer than `floor` x ATR is not placeable
                    mn = floor * a
                    if abs(fill - stop) < mn:
                        stop = fill - mn if side == "long" else fill + mn
                    if abs(fill - stop) > 2.5 * a:
                        break
                    ei = j
                    break
                gone = C[j] < limit - 0.6 * a if side == "long" else C[j] > limit + 0.6 * a
                if gone:
                    break
            if ei is None:
                continue
            risk = abs(fill - stop)
            if risk <= 0:
                continue
            tp = target if tgt == "htf" else (fill + rr * risk if side == "long"
                                              else fill - rr * risk)
            if (side == "long" and tp <= fill) or (side == "short" and tp >= fill):
                continue
            rrq = abs(tp - fill) / risk
            if cap is not None and rrq > cap:
                continue
            why = px = None
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
            rows.append(dict(r=mv / risk, rr=rrq, risk=risk, bars=m - ei, why=why))
            busy = m
    return pd.DataFrame(rows)


def boot(r, n=8000, seed=13):
    rng = np.random.default_rng(seed)
    r = np.asarray(r, float)
    m = rng.choice(r, (n, len(r)), replace=True).mean(1)
    return np.percentile(m, 2.5), np.percentile(m, 97.5), (m <= 0).mean()


def report(lab, **kw):
    allr, ok, cells = [], {}, []
    for nm, P in Q.PREP.items():
        t = run_floor(P, **kw)
        if len(t) < 5:
            ok[nm] = np.nan
            cells.append(f"{'too few':>22}")
            continue
        ok[nm] = t.r.mean()
        allr.append(t.r.to_numpy())
        cells.append(f"{t.r.mean():+.3f} {(t.r>0).mean()*100:4.1f}% n{len(t):<4}")
    if not allr:
        print(f"{lab:<32}" + "".join(cells))
        return None
    r = np.concatenate(allr)
    lo, hi, p = boot(r)
    srt = np.sort(r)[::-1]
    both = all(np.isfinite(v) and v > 0 for v in ok.values())
    print(f"{lab:<32}" + "".join(f"{c:>22}" for c in cells) +
          f"  {r.mean():+.3f}R CI[{lo:+.2f},{hi:+.2f}] P{p*100:5.1f}%"
          f" -top3 {srt[3:].mean():+.3f}" + ("  BOTH+" if both else ""))
    return r


print("=" * 118)
print("Structural stop with a MINIMUM placeable distance. '-top3' = mean after")
print("removing the three biggest winners: if that collapses, the row is a lottery.")
print("=" * 118)
print(f"{'config':<32}" + "".join(f"{nm:>22}" for nm in Q.SAMPLES) + "  pooled")

for f in (0.25, 0.35, 0.50):
    report(f"HTF target, floor {f:.2f}xATR", floor=f, tgt="htf")
print()
for f in (0.25, 0.35, 0.50):
    report(f"HTF tgt cap 6R, floor {f:.2f}", floor=f, tgt="htf", cap=6.0)
print()
for f in (0.25, 0.35, 0.50):
    for rr in (1.5, 2.0, 3.0):
        report(f"{rr}R target, floor {f:.2f}xATR", floor=f, tgt="rr", rr=rr)
