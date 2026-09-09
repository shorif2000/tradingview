"""
Anticipation entries: rest a limit at a level instead of confirming it.

Replaces predict.py and predict5/6/7/8/10, which were seven files that each
re-implemented the same trade loop with one parameter changed. Everything they
measured is reproducible from the single `run()` below plus the study functions
at the bottom:

    python3 backtester/anticipation.py compare     confirm vs anticipate
    python3 backtester/anticipation.py outliers    is it a few big winners?
    python3 backtester/anticipation.py grid        neighbourhood robustness
    python3 backtester/anticipation.py minr        minimum reward floor
    python3 backtester/anticipation.py all         every study

THE FINDING. On identical levels, stops and targets, resting a limit BEYOND an
untouched swing beats waiting for the confirmation candle: +0.523R against
+0.222R, a $5.22 median stop against $6.25, and under half the drawdown. 93% of
a 27-cell parameter neighbourhood is positive in both test periods against the
~25% baseline that noise produces at these sample sizes. It is the only plateau
found anywhere in this project.

TWO INVARIANTS LIVE IN HERE, both learned the hard way.

  I19  A limit order fills part way through its bar, so the rest of that bar's
       range is unknowable at bar resolution. Resolution starts on the NEXT bar.
       Awarding the fill bar let a wide bar hand the test whichever of stop and
       target suited; the tell was "median time in trade: 0 minutes". Fixing it
       halved the apparent edge.
  I20  A structural stop can land cents from the fill, and risk then divides to
       near zero. Without a floor this reported +0.972R on trades whose MEDIAN
       outcome was -1.00R. Floor the stop before computing R. A three-figure
       R:R in any output means this was broken.
"""
from __future__ import annotations

import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from paths import dataset
from xau_engine import atr as atr_fn

# The shipped configuration, arrived at by neighbourhood test rather than by
# picking the best cell of a table.
K, FLOOR, CAP, PIV, SPREAD = 0.25, 0.50, 6.0, 5, 0.20


# ── data ────────────────────────────────────────────────────────────────────

def _resample(m1, rule):
    o = m1.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"})
    return o.dropna()


def load():
    """The two periods every claim here is held to - opposite market direction."""
    m1 = dataset("m1")
    return {"5M Jan": _resample(m1, "5min"), "5M Jun-Aug": dataset("m5_summer")}


def prep(d, htf_min=60, piv=PIV):
    """Swing levels, and higher-timeframe buckets used only as targets."""
    A = atr_fn(d.high, d.low, d.close, 14).to_numpy(float)
    H, L, C, O = (d[x].to_numpy(float) for x in ("high", "low", "close", "open"))
    n = len(d)

    ph = np.zeros(n, bool)
    pl = np.zeros(n, bool)
    for i in range(piv, n - piv):
        w = slice(i - piv, i + piv + 1)
        if H[i] == H[w].max() and (H[w] > H[i]).sum() == 0:
            ph[i] = True
        if L[i] == L[w].min() and (L[w] < L[i]).sum() == 0:
            pl[i] = True

    # Calendar-aligned buckets. pandas 3 defaults to microsecond resolution,
    # which collapsed 649 groups into 3 until this cast was added.
    secs = (d.index.tz_convert("UTC").tz_localize(None)
              .astype("datetime64[s]").astype("int64").to_numpy())
    g = pd.Series(np.arange(n), index=secs // (htf_min * 60)).groupby(level=0)
    htf = [(idx.iloc[-1], H[idx.iloc[0]:idx.iloc[-1] + 1].max(),
            L[idx.iloc[0]:idx.iloc[-1] + 1].min()) for _, idx in g]

    return dict(A=A, H=H, L=L, C=C, O=O, ph=ph, pl=pl, htf=htf, n=n, idx=d.index)


# ── the two things a level needs ────────────────────────────────────────────

def htf_target(P, i, side, span=6):
    """Extreme of the last `span` CLOSED higher-timeframe bars."""
    done = [b for b in P["htf"] if b[0] < i][-span:]
    if not done:
        return None
    return max(b[1] for b in done) if side == "long" else min(b[2] for b in done)


def struct_stop(P, src, side, lvl, back=200):
    """Nearest confirmed swing beyond the level - the market's own invalidation."""
    L, H, pl, ph = P["L"], P["H"], P["pl"], P["ph"]
    lo = max(0, src - back)
    if side == "long":
        c = [L[x] for x in range(lo, src) if pl[x] and L[x] < lvl]
        return max(c) if c else None
    c = [H[x] for x in range(lo, src) if ph[x] and H[x] > lvl]
    return min(c) if c else None


# ── one trade loop, every variant ───────────────────────────────────────────

def run(P, *, mode="anticipate", k=K, floor=FLOOR, cap=CAP, minr=0.0,
        piv=PIV, spread=SPREAD, slip=0.10, valid=48, max_hold=240, span=6):
    """
    mode="anticipate"  rest a limit at level +/- k*ATR, stop at the structural
                       swing floored at floor*ATR, target the HTF extreme
    mode="confirm"     wait for the sweep-and-reclaim candle, enter next open

    Both use the same levels, the same stop rule and the same target, so only
    the entry differs and the comparison is fair.
    """
    A, H, L, C, O, n, idx = (P["A"], P["H"], P["L"], P["C"], P["O"], P["n"], P["idx"])
    rows, busy = [], -1

    for i in range(60, n - 2):
        if i <= busy:
            continue
        src = i - piv
        if src < 1:
            continue

        for side, is_piv, lvl in (("long", P["pl"][src], L[src]),
                                  ("short", P["ph"][src], H[src])):
            if not is_piv or i <= busy:
                continue
            a = A[i]
            if not np.isfinite(a) or a <= 0:
                continue

            # the level must still be untouched at the moment we act on it
            seg = slice(src + 1, i + 1)
            if side == "long" and L[seg].min() < lvl:
                continue
            if side == "short" and H[seg].max() > lvl:
                continue

            tp = htf_target(P, i, side, span)
            if tp is None:
                continue

            fill = ei = None
            if mode == "anticipate":
                limit = lvl - k * a if side == "long" else lvl + k * a
                for j in range(i + 1, min(i + 1 + valid, n)):
                    if (L[j] <= limit) if side == "long" else (H[j] >= limit):
                        fill = limit + spread / 2 if side == "long" else limit - spread / 2
                        ei = j
                        break
                    gone = (C[j] < limit - 0.6 * a) if side == "long" else (C[j] > limit + 0.6 * a)
                    if gone:
                        break
            else:
                for j in range(i + 1, min(i + 1 + valid, n)):
                    swept = (L[j] < lvl and C[j] > lvl) if side == "long" \
                        else (H[j] > lvl and C[j] < lvl)
                    if swept and j + 1 < n:
                        fill = O[j + 1] + spread / 2 + slip if side == "long" \
                            else O[j + 1] - spread / 2 - slip
                        ei = j + 1
                        break
                    gone = (C[j] < lvl - 0.6 * a) if side == "long" else (C[j] > lvl + 0.6 * a)
                    if gone:
                        break
            if ei is None:
                continue

            sv = struct_stop(P, src, side, lvl)
            mn = floor * a
            stop = (fill - mn if side == "long" else fill + mn) if sv is None else \
                   (sv - 0.10 * a if side == "long" else sv + 0.10 * a)
            if mode == "confirm":                       # never inside the signal candle
                base = L[ei - 1] if side == "long" else H[ei - 1]
                stop = min(stop, base - 0.10 * a) if side == "long" else max(stop, base + 0.10 * a)
            if abs(fill - stop) < mn:                   # I20
                stop = fill - mn if side == "long" else fill + mn
            if abs(fill - stop) > 2.5 * a:
                continue

            risk = abs(fill - stop)
            if risk <= 0 or ((tp <= fill) if side == "long" else (tp >= fill)):
                continue
            rr = abs(tp - fill) / risk
            if rr > cap or rr < minr:
                continue

            # I19: an anticipated fill happens mid-bar, so resolution starts on
            # the next one. A confirmed fill is at a bar's open, so its own bar
            # is legitimately available.
            why = px = None
            m = ei + 1 if mode == "anticipate" else ei
            start = m
            for m in range(start, min(ei + max_hold, n)):
                if (L[m] <= stop) if side == "long" else (H[m] >= stop):
                    why, px = "sl", stop
                    break
                if (H[m] >= tp) if side == "long" else (L[m] <= tp):
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


# ── statistics ──────────────────────────────────────────────────────────────

def boot(r, n=8000, seed=13):
    """Percentile bootstrap. Returns (lo, hi, P(mean <= 0))."""
    r = np.asarray(r, float)
    if len(r) < 5:
        return np.nan, np.nan, np.nan
    m = np.random.default_rng(seed).choice(r, (n, len(r))).mean(1)
    return np.percentile(m, 2.5), np.percentile(m, 97.5), (m <= 0).mean()


def summarise(prepped, **kw):
    """Run every sample, pool, and report. Returns (pooled array, per-sample)."""
    per, pool = {}, []
    for nm, P in prepped.items():
        t = run(P, **kw)
        per[nm] = t
        if len(t):
            pool.append(t.r.to_numpy())
    return (np.concatenate(pool) if pool else np.array([])), per


def line(label, pooled, per, width=22):
    if len(pooled) < 5:
        print(f"  {label:<34}{'too few trades':>{width}}")
        return
    lo, hi, p = boot(pooled)
    srt = np.sort(pooled)[::-1]
    cells = "".join(f"{t.r.mean():+.3f} {(t.r>0).mean()*100:4.1f}% n{len(t):<4}".rjust(width)
                    for t in per.values())
    ok = all(len(t) and t.r.mean() > 0 for t in per.values())
    print(f"  {label:<34}{cells}  {pooled.mean():+.3f}R CI[{lo:+.2f},{hi:+.2f}] "
          f"P{p*100:5.1f}% -top3 {srt[3:].mean():+.3f}" + ("  BOTH+" if ok else ""))


# ── studies ─────────────────────────────────────────────────────────────────

def study_compare(pp):
    print("\nIdentical levels, stops and targets. Only the ENTRY differs.")
    print(f"  {'':34}" + "".join(f"{nm:>22}" for nm in pp) + "  pooled")
    for mode, lab in (("confirm", "CONFIRM (wait for the reclaim)"),
                      ("anticipate", "ANTICIPATE (resting limit)")):
        pooled, per = summarise(pp, mode=mode)
        line(lab, pooled, per)
        a = pd.concat(per.values())
        print(f"    stop ${a.risk.median():.2f} median, {a.mins.median():.0f} min in trade, "
              f"exits: " + ", ".join(f"{k} {v/len(a)*100:.0f}%" for k, v in a.why.value_counts().items()))


def study_outliers(pp):
    print("\nIs the edge a handful of winners? If removing three trades flips the")
    print("sign, the result was three trades.")
    pooled, per = summarise(pp, mode="anticipate")
    srt = np.sort(pooled)[::-1]
    print(f"  n={len(pooled)}  mean {pooled.mean():+.3f}R  median {np.median(pooled):+.3f}R")
    for d in (0, 1, 3, 5):
        x = srt[d:]
        lo, hi, p = boot(x)
        print(f"    minus top {d:<2} {x.mean():+.3f}R  CI[{lo:+.2f},{hi:+.2f}]  P {p*100:.1f}%")
    win = pooled[pooled > 0]
    print(f"    best 5% of trades are {srt[:max(1,len(srt)//20)].sum()/win.sum()*100:.0f}% "
          f"of gross profit")


def study_grid(pp):
    print("\nNeighbourhood. A real effect is a plateau; an artifact is a spike.")
    print("Noise clears 'positive in both periods' about 25% of the time here.")
    ok = tot = 0
    vals = []
    for cap in (4.0, 6.0, 8.0):
        print(f"\n  cap {cap:.0f}R" + "".join(f"{'floor '+format(f,'.2f'):>16}" for f in (0.40, 0.50, 0.60)))
        for k in (0.15, 0.25, 0.35):
            row = f"    k {k:.2f}"
            for fl in (0.40, 0.50, 0.60):
                pooled, per = summarise(pp, mode="anticipate", k=k, floor=fl, cap=cap)
                if len(pooled) < 8:
                    row += f"{'-':>16}"
                    continue
                good = all(len(t) and t.r.mean() > 0 for t in per.values())
                ok += good
                tot += 1
                vals.append(pooled.mean())
                row += f"{pooled.mean():+.3f}{'+' if good else ' '} n{len(pooled):<3}".rjust(16)
            print(row)
    print(f"\n  positive in both periods: {ok}/{tot} = {ok/tot*100:.0f}%   "
          f"median across grid {np.median(vals):+.3f}R")


def study_minr(pp):
    print("\nA minimum reward floor. Guards against the one failure that is pure")
    print("arithmetic: a real stop against a reward too small to pay for it.")
    print(f"  {'':34}" + "".join(f"{nm:>22}" for nm in pp) + "  pooled")
    base, _ = summarise(pp, mode="anticipate")
    for minr in (0.0, 1.0, 2.0, 3.0):
        pooled, per = summarise(pp, mode="anticipate", minr=minr)
        dropped = (1 - len(pooled) / len(base)) * 100 if len(base) else 0
        line(f"{'none' if minr == 0 else f'{minr:.1f}R'}  (drops {dropped:4.1f}%)", pooled, per)
    print("\n  3.0R measures best and is NOT the default: it was chosen by reading")
    print("  this table, scored on the same two periods, and discards 43% of trades.")


STUDIES = {"compare": study_compare, "outliers": study_outliers,
           "grid": study_grid, "minr": study_minr}

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "compare"
    pp = {nm: prep(d) for nm, d in load().items()}
    for name in (STUDIES if which == "all" else [which]):
        if name not in STUDIES:
            print(f"unknown study '{name}'. choose from: {', '.join(STUDIES)}, all")
            raise SystemExit(1)
        print("=" * 118)
        print(name.upper())
        print("=" * 118)
        STUDIES[name](pp)
