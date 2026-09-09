"""
Why are so many signals false? Diagnose before filtering.

Guessing at filters is how the last fourteen attempts failed. This asks the data
which conditions separate the winners from the losers, one feature at a time,
and only on features measurable AT SIGNAL TIME — anything computed from what
happened afterwards would be a look-ahead and would flatter every filter built
from it.

Uses the CALIBRATED rule (38 / 1.8, single filter), which reproduces 94-96% of
the indicator's real markers.
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from samples import samples
from xau_engine import ema, atr as atr_fn, rsi as rsi_fn, dmi
from rf_lib import rf_signals, simulate, smooth_range, range_filter

CAL = dict(fast=(38, 1.8), mode="fast")

SAMPLES = samples()


def features(sg: pd.DataFrame) -> pd.DataFrame:
    """Everything knowable at the close of the signal bar, and nothing more."""
    d = sg.copy()
    d["atr"] = atr_fn(d.high, d.low, d.close, 14)
    d["atr_pct"] = d.atr.rolling(300, min_periods=60).rank(pct=True)
    d["ema21"] = ema(d.close, 21)
    d["ema200"] = ema(d.close, 200)
    d["rsi"] = rsi_fn(d.close, 14)
    _, _, adx = dmi(d.high, d.low, d.close, 14, 14)
    d["adx"] = adx
    # how far price has run past the filter, in ATR — a proxy for "too late"
    d["ext"] = (d.close - d.f_filt).abs() / d.atr
    # how far price sits from the EMA21, in ATR — extension from the mean
    d["stretch"] = (d.close - d.ema21).abs() / d.atr
    # how long the filter has been travelling this way, and how far
    sig = np.where(d.rf_long, 1, np.where(d.rf_short, -1, 0))
    d["sig"] = sig
    last = -1
    bars_since = np.zeros(len(d))
    travel = np.zeros(len(d))
    fv = d.f_filt.to_numpy(float)
    for i in range(len(d)):
        bars_since[i] = i - last if last >= 0 else 9999
        travel[i] = abs(fv[i] - fv[last]) if last >= 0 else np.nan
        if sig[i] != 0:
            last = i
    d["bars_since_flip"] = bars_since
    d["travel_atr"] = travel / d.atr
    lon = d.index.tz_convert("Europe/London")
    d["hour"] = lon.hour
    # higher-timeframe agreement: the same filter on 4x the bars
    ht = d.close.rolling(4).mean()
    hr = smooth_range(ht, 38, 1.8)
    hf = range_filter(ht.bfill(), hr)
    d["htf_up"] = ht.to_numpy() > hf
    return d


def label_trades(sg, m1):
    tr = simulate(sg, m1)
    if len(tr) == 0:
        return None
    tr = tr.set_index(pd.DatetimeIndex(tr.time))
    return tr


rows = []
for nm, (d, m1) in SAMPLES.items():
    sg = features(rf_signals(d, **CAL))
    tr = label_trades(sg, m1)
    if tr is None:
        continue
    f = sg.loc[sg.index.isin(tr.index)]
    f = f.loc[~f.index.duplicated()]
    t = tr.loc[tr.index.isin(f.index)]
    t = t.loc[~t.index.duplicated()]
    j = f.join(t[["r", "side"]], how="inner")
    j["sample"] = nm
    rows.append(j)

ALL = pd.concat(rows)
JAN = ALL[ALL["sample"].str.contains("Jan")]
JUN = ALL[ALL["sample"].str.contains("Jun")]
print(f"trades: {len(ALL)}  (Jan {len(JAN)}, Jun-Aug {len(JUN)})")
print(f"baseline expectancy   Jan {JAN.r.mean():+.3f}R   Jun-Aug {JUN.r.mean():+.3f}R\n")

FEATS = ["ext", "stretch", "adx", "atr_pct", "rsi", "bars_since_flip", "travel_atr"]
print("Split each feature at its median. Does the top or bottom half do better,")
print("and does the SAME half win in both periods?\n")
print(f"{'feature':<18} {'Jan low':>9} {'Jan high':>9} {'Jun low':>9} {'Jun high':>9}   verdict")
for c in FEATS:
    med = ALL[c].median()
    jl, jh = JAN[JAN[c] <= med].r.mean(), JAN[JAN[c] > med].r.mean()
    ul, uh = JUN[JUN[c] <= med].r.mean(), JUN[JUN[c] > med].r.mean()
    jan_better_high = jh > jl
    jun_better_high = uh > ul
    same = jan_better_high == jun_better_high
    gap = min(abs(jh - jl), abs(uh - ul))
    verdict = ("AGREES: " + ("high" if jan_better_high else "low") + " half better") if same else "disagrees"
    if same and gap < 0.05:
        verdict += " (tiny)"
    print(f"{c:<18} {jl:>+9.3f} {jh:>+9.3f} {ul:>+9.3f} {uh:>+9.3f}   {verdict}")

print("\nBy hour of day (London), expectancy and count:")
for lo, hi, lab in [(0, 7, "00-07"), (7, 12, "07-12"), (12, 16, "12-16"), (16, 20, "16-20"), (20, 24, "20-24")]:
    j = JAN[(JAN.hour >= lo) & (JAN.hour < hi)]
    u = JUN[(JUN.hour >= lo) & (JUN.hour < hi)]
    print(f"  {lab}   Jan {j.r.mean():+.3f}R n={len(j):<4}   Jun-Aug {u.r.mean():+.3f}R n={len(u):<4}")

print("\nHTF agreement (same filter on 4x bars):")
for v, lab in [(True, "agrees"), (False, "opposes")]:
    j = JAN[(JAN.htf_up == (JAN.side == "long")) == v]
    u = JUN[(JUN.htf_up == (JUN.side == "long")) == v]
    print(f"  {lab:<8} Jan {j.r.mean():+.3f}R n={len(j):<4}   Jun-Aug {u.r.mean():+.3f}R n={len(u):<4}")

ALL.to_pickle("diag.pkl")
print("\nsaved diag.pkl")
