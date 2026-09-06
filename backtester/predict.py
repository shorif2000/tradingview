"""
Can the entry be placed BEFORE the move instead of after it?

The complaint is fair and structural: a confirmation-based signal cannot fire
before the confirmation, so by the time the sweep-and-reclaim candle closes, the
first part of the move is gone. The question is whether the level can be traded
in ANTICIPATION instead.

Every level here is knowable in advance - a swing low is confirmed 5 bars after
it forms, and it just sits there. So you can leave a resting buy limit at (or a
little below) it, with a tight stop under the anticipated overshoot, and target a
higher-timeframe objective. Nothing about that is a forecast; it is arithmetic on
a level that already exists.

Compared head to head with what the script does today:

  CONFIRM  wait for the candle that sweeps the level and closes back inside,
           enter on the next open, stop beyond that candle's extreme
  ANTICIPATE  resting limit at level - k*ATR, stop s*ATR below the fill,
           never waits for confirmation

Both target the same higher-timeframe level, so only the entry and stop differ.
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from paths import dataset
from xau_engine import atr as atr_fn


def rs(m1, rule):
    o = m1.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return o.dropna()


M1 = dataset("m1")
SAMPLES = {"5M Jan": rs(M1, "5min"), "5M Jun-Aug": dataset("m5_summer")}


def prep(d, htf_min=60, piv=5):
    A = atr_fn(d.high, d.low, d.close, 14).to_numpy(float)
    H, L, C, O = (d[x].to_numpy(float) for x in ("high", "low", "close", "open"))
    n = len(d)
    # swing levels, confirmed piv bars later
    pl = np.zeros(n, bool)
    ph = np.zeros(n, bool)
    for i in range(piv, n - piv):
        w = slice(i - piv, i + piv + 1)
        if L[i] == L[w].min() and (L[w] < L[i]).sum() == 0:
            pl[i] = True
        if H[i] == H[w].max() and (H[w] > H[i]).sum() == 0:
            ph[i] = True
    # higher-timeframe swing highs/lows, used only as TARGETS
    secs = (d.index.tz_convert("UTC").tz_localize(None)
              .astype("datetime64[s]").astype("int64").to_numpy())
    key = secs // (htf_min * 60)
    g = pd.Series(np.arange(n), index=key).groupby(level=0)
    htf = [(idx.iloc[-1], H[idx.iloc[0]:idx.iloc[-1] + 1].max(),
            L[idx.iloc[0]:idx.iloc[-1] + 1].min()) for _, idx in g]
    return dict(A=A, H=H, L=L, C=C, O=O, pl=pl, ph=ph, htf=htf, n=n, idx=d.index)


def htf_target(P, i, side, span=6):
    """Nearest higher-timeframe extreme beyond price, from CLOSED HTF bars only."""
    done = [b for b in P["htf"] if b[0] < i][-span:]
    if not done:
        return None
    return max(b[1] for b in done) if side == "long" else min(b[2] for b in done)


def struct_stop(P, src, side, lvl, back=200):
    """Next confirmed swing beyond the level - the market's own invalidation."""
    L, H, pl, ph = P["L"], P["H"], P["pl"], P["ph"]
    lo = max(0, src - back)
    if side == "long":
        cands = [L[x] for x in range(lo, src) if pl[x] and L[x] < lvl]
        return max(cands) if cands else None      # nearest one BELOW the level
    cands = [H[x] for x in range(lo, src) if ph[x] and H[x] > lvl]
    return min(cands) if cands else None


def run(P, *, mode="confirm", k=0.25, s=0.75, valid=48, piv=5, stop_mode="atr",
        spread=0.20, slip=0.10, max_hold=240, tgt="htf", rr=2.0):
    A, H, L, C, O, n = P["A"], P["H"], P["L"], P["C"], P["O"], P["n"]
    rows = []
    busy = -1
    for i in range(60, n - 2):
        if i <= busy:
            continue
        # a level is confirmed piv bars after it forms
        src = i - piv
        if src < 1:
            continue
        for side, isp, lvl in (("long", P["pl"][src], L[src]), ("short", P["ph"][src], H[src])):
            if not isp or i <= busy:
                continue
            a = A[i]
            if not np.isfinite(a) or a <= 0:
                continue
            # level must still be untouched at the moment we would act on it
            seg = slice(src + 1, i + 1)
            if side == "long" and L[seg].min() < lvl:
                continue
            if side == "short" and H[seg].max() > lvl:
                continue
            target = htf_target(P, i, side)
            if target is None:
                continue

            fill = stop = None
            ei = None
            if mode == "anticipate":
                limit = lvl - k * a if side == "long" else lvl + k * a
                for j in range(i + 1, min(i + 1 + valid, n)):
                    hit = L[j] <= limit if side == "long" else H[j] >= limit
                    if hit:
                        fill = limit + spread / 2 if side == "long" else limit - spread / 2
                        if stop_mode == "structure":
                            sv = struct_stop(P, src, side, lvl)
                            if sv is None:
                                break
                            stop = sv - 0.10 * a if side == "long" else sv + 0.10 * a
                            # a structural stop miles away is not a tight stop
                            if abs(fill - stop) > 2.5 * a:
                                break
                        else:
                            stop = fill - s * a if side == "long" else fill + s * a
                        ei = j
                        break
                    # level properly broken -> idea is dead, cancel the order
                    gone = C[j] < limit - s * a if side == "long" else C[j] > limit + s * a
                    if gone:
                        break
            else:                                   # confirm: today's behaviour
                for j in range(i + 1, min(i + 1 + valid, n)):
                    sweep = (L[j] < lvl and C[j] > lvl) if side == "long" \
                        else (H[j] > lvl and C[j] < lvl)
                    if sweep and j + 1 < n:
                        fill = O[j + 1] + spread / 2 + slip if side == "long" \
                            else O[j + 1] - spread / 2 - slip
                        stop = L[j] - 0.35 * a if side == "long" else H[j] + 0.35 * a
                        ei = j + 1
                        break
                    gone = C[j] < lvl - 1.0 * a if side == "long" else C[j] > lvl + 1.0 * a
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
            why = px = None
            # A limit fills PART WAY THROUGH its bar, so the rest of that bar's
            # range is not knowable without M1 - and using all of it would let a
            # 5M bar wide enough to reach both the stop and the target award
            # whichever suits. Resolution starts on the NEXT bar. For the
            # confirmation entry the fill is at a bar's OPEN, so its own bar is
            # legitimately available and scanning from ei is correct there.
            scan_from = ei + 1 if mode == "anticipate" else ei
            for m in range(scan_from, min(ei + max_hold, n)):
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
            rows.append(dict(r=mv / risk, rr=abs(tp - fill) / risk, risk=risk,
                             bars=m - ei, why=why))
            busy = m
    return pd.DataFrame(rows)


PREP = {nm: prep(d) for nm, d in SAMPLES.items()}

CONFIGS = [
    ("CONFIRM (today), HTF tgt",   dict(mode="confirm", tgt="htf")),
    ("CONFIRM (today), 2R tgt",    dict(mode="confirm", tgt="rr")),
    ("ANTICIPATE k0.00 s0.75",     dict(mode="anticipate", k=0.00, s=0.75)),
    ("ANTICIPATE k0.25 s0.75",     dict(mode="anticipate", k=0.25, s=0.75)),
    ("ANTICIPATE k0.50 s0.75",     dict(mode="anticipate", k=0.50, s=0.75)),
    ("ANTICIPATE k0.25 s0.50",     dict(mode="anticipate", k=0.25, s=0.50)),
    ("ANTICIPATE k0.25 s1.00",     dict(mode="anticipate", k=0.25, s=1.00)),
    ("ANTICIPATE k0.50 s1.00",     dict(mode="anticipate", k=0.50, s=1.00)),
    ("ANTICIPATE k0.25 s0.75 2R",  dict(mode="anticipate", k=0.25, s=0.75, tgt="rr")),
]

print(f"{'config':<28}" + "".join(f"{nm:>26}" for nm in SAMPLES) + "   verdict")
for lab, kw in CONFIGS:
    cells, exps = [], {}
    for nm, P in PREP.items():
        t = run(P, **kw)
        if len(t) < 5:
            exps[nm] = np.nan
            cells.append(f"{'too few':>26}")
            continue
        exps[nm] = t.r.mean()
        cells.append(f"{t.r.mean():+.3f}R {(t.r>0).mean()*100:4.1f}% "
                     f"rr{t.rr.median():4.1f} n{len(t):<4}")
    ok = all(np.isfinite(v) and v > 0 for v in exps.values())
    print(f"{lab:<28}" + "".join(f"{c:>26}" for c in cells) + ("   BOTH POSITIVE" if ok else ""))
