"""
Can anything lift the range filter's direction accuracy above chance?

The discipline here is the one AGENTS.md sets: a change has to work in BOTH
periods, which have opposite market direction. Something that scores well in one
and inverts in the other is what a spurious pattern looks like, and this project
has already killed three ideas that way.
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from paths import dataset
from xau_engine import atr as atr_fn, ema, rsi as rsi_fn
from rf_lib import rf_signals, simulate, summarise

M1 = dataset("m1")
B5 = dataset("m5_summer")

def rs(m1, rule):
    o = m1.resample(rule, label="left", closed="left").agg(
        {"open":"first","high":"max","low":"min","close":"last","volume":"sum"})
    return o.dropna()

SAMPLES = {"2M Jan": (rs(M1,"2min"), M1), "3M Jan": (rs(M1,"3min"), M1),
           "5M Jan": (rs(M1,"5min"), M1), "5M Jun-Aug": (B5, None)}

# pre-compute signals once per (sample, mode)
BASE = {}
for nm, (d, m1) in SAMPLES.items():
    for mode in ("both", "fast"):
        BASE[(nm, mode)] = rf_signals(d, mode=mode)


def add_ctx(sg):
    d = sg.copy()
    d["atr"] = atr_fn(d.high, d.low, d.close, 14)
    d["atr_pct"] = d.atr.rolling(500, min_periods=50).rank(pct=True)
    d["ema200"] = ema(d.close, 200)
    d["rsi"] = rsi_fn(d.close, 14)
    d["lon"] = d.index.tz_convert("Europe/London").hour
    d["body"] = (d.close - d.open)
    return d


FILTERS = {
    "none":            lambda d, s: pd.Series(True, index=d.index),
    "session 7-20":    lambda d, s: (d.lon >= 7) & (d.lon < 20),
    "beyond band":     lambda d, s: np.where(s > 0, d.close > d.f_filt + d.f_rng,
                                                    d.close < d.f_filt - d.f_rng),
    "slow agrees":     lambda d, s: np.where(s > 0, d.close > d.s_filt, d.close < d.s_filt),
    "with EMA200":     lambda d, s: np.where(s > 0, d.close > d.ema200, d.close < d.ema200),
    "vs EMA200":       lambda d, s: np.where(s > 0, d.close < d.ema200, d.close > d.ema200),
    "ATR mid 20-80":   lambda d, s: (d.atr_pct > 0.2) & (d.atr_pct < 0.8),
    "signal candle":   lambda d, s: np.where(s > 0, d.body > 0, d.body < 0),
    "RSI not extreme": lambda d, s: (d.rsi > 30) & (d.rsi < 70),
}


def dir_acc(d, mask_fn, hz, invert=False):
    c = d.close.to_numpy(float)
    L = d.rf_long.to_numpy(bool)
    S = d.rf_short.to_numpy(bool)
    if invert:
        L, S = S, L
    ok = tot = 0
    for arr, sign in ((L, 1), (S, -1)):
        m = np.asarray(mask_fn(d, sign), dtype=bool)
        for i in np.flatnonzero(arr & m):
            if i + hz < len(c):
                tot += 1
                ok += 1 if sign * (c[i + hz] - c[i]) > 0 else 0
    return (100.0 * ok / tot if tot else np.nan), tot


CTX = {k: add_ctx(v) for k, v in BASE.items()}
JAN = ["2M Jan", "3M Jan", "5M Jan"]

print("=" * 108)
print("DIRECTION ACCURACY at 20 bars, mode = both-agree.  A filter has to beat 50% in BOTH periods.")
print("=" * 108)
print(f"{'filter':<18} {'2M Jan':>14} {'3M Jan':>14} {'5M Jan':>14} {'5M Jun-Aug':>14}   verdict")

res = []
for fname, fn in FILTERS.items():
    cells, accs = [], {}
    for nm in SAMPLES:
        a, n = dir_acc(CTX[(nm, "both")], fn, 20)
        accs[nm] = a
        cells.append(f"{a:5.1f}% n={n:<4}" if n else "     -      ")
    jan = np.nanmean([accs[s] for s in JAN])
    jun = accs["5M Jun-Aug"]
    both_up = (jan > 50) and (jun > 50)
    verdict = "REPLICATES" if both_up else ("flips sign" if (jan - 50) * (jun - 50) < 0 else "both below 50")
    print(f"{fname:<18} " + " ".join(f"{c:>14}" for c in cells) + f"   {verdict}")
    res.append(dict(filter=fname, jan=jan, jun=jun, verdict=verdict))

print("\n" + "=" * 108)
print("INVERTED (fade every signal) — the same table, signals flipped")
print("=" * 108)
for fname in ("none", "session 7-20", "beyond band"):
    cells, accs = [], {}
    for nm in SAMPLES:
        a, n = dir_acc(CTX[(nm, "both")], FILTERS[fname], 20, invert=True)
        accs[nm] = a
        cells.append(f"{a:5.1f}% n={n:<4}" if n else "     -      ")
    jan = np.nanmean([accs[s] for s in JAN]); jun = accs["5M Jun-Aug"]
    v = "REPLICATES" if (jan > 50 and jun > 50) else ("flips sign" if (jan-50)*(jun-50) < 0 else "both below 50")
    print(f"{'inv ' + fname:<18} " + " ".join(f"{c:>14}" for c in cells) + f"   {v}")

pd.DataFrame(res).to_csv("grid_direction.csv", index=False)
print("\nsaved grid_direction.csv")
