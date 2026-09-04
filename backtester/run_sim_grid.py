"""
Trade-level improvement grid.

Direction accuracy sits at 50-54%, so no exit tweak can manufacture an edge -
it can only move the win rate around at roughly constant expectancy, minus
costs. This grid asks the question that follows from that: is there ANY
combination of entry filter and exit geometry that clears zero in both periods?

Expectancy is reported in R, not pounds. Pounds at 0.02 lots on a GBP100 account
are dominated by sizing, and the sim does not close the account at zero, so the
pound column below is a ranking device and nothing more.
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from paths import dataset
from xau_engine import atr as atr_fn, ema
from rf_lib import rf_signals, simulate

M1 = dataset("m1")
B5 = dataset("m5_summer")

def rs(m1, rule):
    o = m1.resample(rule, label="left", closed="left").agg(
        {"open":"first","high":"max","low":"min","close":"last","volume":"sum"})
    return o.dropna()

SAMPLES = {"2M Jan": (rs(M1,"2min"), M1), "3M Jan": (rs(M1,"3min"), M1),
           "5M Jan": (rs(M1,"5min"), M1), "5M Jun-Aug": (B5, None)}
SIG = {(nm, md): rf_signals(d, mode=md) for nm, (d, _) in SAMPLES.items()
       for md in ("both", "fast")}


def gate(sg, *, session=False, ema_align=False, band=0.0):
    """Drop signals that fail the filter, keeping the frame shape intact."""
    d = sg.copy()
    keep_l = pd.Series(True, index=d.index)
    keep_s = pd.Series(True, index=d.index)
    if session:
        lon = d.index.tz_convert("Europe/London").hour
        ok = (lon >= 7) & (lon < 20)
        keep_l &= ok; keep_s &= ok
    if ema_align:
        e = ema(d.close, 200)
        keep_l &= d.close > e
        keep_s &= d.close < e
    if band > 0:
        keep_l &= d.close > d.f_filt + band * d.f_rng
        keep_s &= d.close < d.f_filt - band * d.f_rng
    d["rf_long"] = d.rf_long & keep_l
    d["rf_short"] = d.rf_short & keep_s
    return d


CONFIGS = [
    ("baseline both 2R",       dict(mode="both"), {},                              dict(rr=2.0, sl_mult=1.2)),
    ("baseline fast 2R",       dict(mode="fast"), {},                              dict(rr=2.0, sl_mult=1.2)),
    ("both 1R",                dict(mode="both"), {},                              dict(rr=1.0, sl_mult=1.2)),
    ("both 1.5R",              dict(mode="both"), {},                              dict(rr=1.5, sl_mult=1.2)),
    ("both 3R",                dict(mode="both"), {},                              dict(rr=3.0, sl_mult=1.2)),
    ("both 2R wide stop",      dict(mode="both"), {},                              dict(rr=2.0, sl_mult=2.0)),
    ("both 2R tight stop",     dict(mode="both"), {},                              dict(rr=2.0, sl_mult=0.8)),
    ("both + session",         dict(mode="both"), dict(session=True),              dict(rr=2.0, sl_mult=1.2)),
    ("both + EMA200",          dict(mode="both"), dict(ema_align=True),            dict(rr=2.0, sl_mult=1.2)),
    ("both + EMA200 + sess",   dict(mode="both"), dict(ema_align=True, session=True), dict(rr=2.0, sl_mult=1.2)),
    ("both + half-band",       dict(mode="both"), dict(band=0.5),                  dict(rr=2.0, sl_mult=1.2)),
    ("both + EMA200 1R",       dict(mode="both"), dict(ema_align=True),            dict(rr=1.0, sl_mult=1.2)),
    ("INVERTED both 2R",       dict(mode="both"), {},                              dict(rr=2.0, sl_mult=1.2, invert=True)),
    ("INVERTED both + sess",   dict(mode="both"), dict(session=True),              dict(rr=2.0, sl_mult=1.2, invert=True)),
]

JAN = ["2M Jan", "3M Jan", "5M Jan"]
print("=" * 112)
print("EXPECTANCY IN R.  A configuration has to clear zero in the January samples AND in June-August.")
print("=" * 112)
hdr = f"{'config':<24}" + "".join(f"{s:>17}" for s in SAMPLES) + "   verdict"
print(hdr)

rows = []
for label, sigkw, gkw, simkw in CONFIGS:
    cells, exps = [], {}
    for nm, (d, m1) in SAMPLES.items():
        sg = gate(SIG[(nm, sigkw["mode"])], **gkw)
        tr = simulate(sg, m1, **simkw)
        if len(tr) == 0:
            exps[nm] = np.nan; cells.append("       -        "); continue
        e = tr.r.mean(); w = (tr.r > 0).mean() * 100
        exps[nm] = e
        cells.append(f"{e:+.3f} {w:4.1f}% n{len(tr):<4}")
    jan = np.nanmean([exps[s] for s in JAN]); jun = exps["5M Jun-Aug"]
    verdict = "POSITIVE BOTH" if (jan > 0 and jun > 0) else \
              ("flips sign" if jan * jun < 0 else "negative both")
    print(f"{label:<24}" + "".join(f"{c:>17}" for c in cells) + f"   {verdict}")
    rows.append(dict(config=label, jan=jan, jun=jun, verdict=verdict))

pd.DataFrame(rows).to_csv("grid_sim.csv", index=False)
print("\nsaved grid_sim.csv")
