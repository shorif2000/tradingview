"""
Candle Range Theory on gold, and its inverse.

CRT as taught: a range candle, then a candle that sweeps ONE side of it and
closes back inside (the liquidity grab), then distribution toward the OPPOSITE
end. You fade the sweep.

The inverse — treat the sweep as real and trade WITH it — is tested alongside,
because on this instrument the browser pass said the taught version loses at
every timeframe from 15M to Monthly while the inverse wins on 1H, 4H and Weekly.
This script checks that on a different data source: your TradingView H1/H4
exports rather than the live chart feed.
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from paths import dataset
from xau_engine import atr as atr_fn

H4 = dataset("h4")
H1 = dataset("h1")


def crt(d, *, fade=True, rr=2.0, max_bars=20, spread=0.20, slip=0.10,
        sl_buf=0.1, target="fixed"):
    A = atr_fn(d.high, d.low, d.close, 14).to_numpy(float)
    T = d.index.to_numpy()
    O, H, L, C = (d[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    n = len(d)
    rows = []
    for i in range(1, n - 2):
        rh, rl = H[i - 1], L[i - 1]
        if not np.isfinite(A[i]) or A[i] <= 0:
            continue
        sl_, sh_ = L[i] < rl, H[i] > rh
        side = None
        if sl_ and not sh_ and C[i] > rl:
            side = "long" if fade else "short"
        if sh_ and not sl_ and C[i] < rh:
            side = "short" if fade else "long"
        if side is None:
            continue
        j = i + 1
        buf = sl_buf * A[i]
        entry = O[j] + spread / 2 + slip if side == "long" else O[j] - spread / 2 - slip
        if fade and target == "opposite":
            stop = (L[i] - buf) if side == "long" else (H[i] + buf)
            tp = rh if side == "long" else rl
        else:
            risk0 = 1.2 * A[i]
            stop = entry - risk0 if side == "long" else entry + risk0
            tp = entry + rr * risk0 if side == "long" else entry - rr * risk0
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        if (side == "long" and tp <= entry) or (side == "short" and tp >= entry):
            continue
        why, px = None, None
        for k in range(j, min(j + max_bars, n)):
            hs = L[k] <= stop if side == "long" else H[k] >= stop
            ht = H[k] >= tp if side == "long" else L[k] <= tp
            if hs:                       # stop wins ties
                why, px = "sl", stop
                break
            if ht:
                why, px = "tp", tp
                break
        if why is None:
            k = min(j + max_bars - 1, n - 1)
            why, px = "time", C[k]
        mv = (px - entry) if side == "long" else (entry - px)
        rows.append(dict(t=T[i], side=side, r=mv / risk, why=why))
    return pd.DataFrame(rows)


def boot(r, n=10000, seed=3):
    rng = np.random.default_rng(seed)
    r = np.asarray(r, float)
    m = rng.choice(r, (n, len(r)), replace=True).mean(1)
    return np.percentile(m, 2.5), np.percentile(m, 97.5), (m <= 0).mean()


def quarters(tr, k=4):
    m = len(tr) // k
    return [round(tr.r.iloc[i * m:(i + 1) * m].mean(), 3) for i in range(k)]


print(f"H4 export: {len(H4)} bars  {H4.index[0].date()} -> {H4.index[-1].date()}")
print(f"H1 export: {len(H1)} bars  {H1.index[0].date()} -> {H1.index[-1].date()}\n")
print(f"{'data':<8} {'variant':<24} {'n':>5} {'win%':>7} {'expR':>8} {'95% CI':>20} {'P(no edge)':>11}  quarters")
for lab, d in (("H4", H4), ("H1", H1)):
    for vlab, kw in (("CRT as taught (fade)", dict(fade=True, target="opposite")),
                     ("CRT fade, fixed 2R", dict(fade=True, target="fixed")),
                     ("INVERSE (continuation)", dict(fade=False))):
        tr = crt(d, **kw)
        if len(tr) < 10:
            print(f"{lab:<8} {vlab:<24} too few")
            continue
        lo, hi, p = boot(tr.r)
        print(f"{lab:<8} {vlab:<24} {len(tr):>5} {(tr.r>0).mean()*100:>6.1f}% "
              f"{tr.r.mean():>+8.3f}  [{lo:+.3f},{hi:+.3f}] {p*100:>10.1f}%  {quarters(tr)}")
