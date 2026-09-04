"""
Like-for-like: the range filter against the engine that was already measured,
on the same bars, at 2M / 3M / 5M.

Also tests the one hybrid worth testing - using the range filter's STATE as
context for the mean-reversion entries. If the filter has no directional edge of
its own it may still be a useful regime label, and that is a different claim
worth a separate measurement rather than an assumption.
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from paths import dataset
from xau_engine import Config, backtest, stats
from rf_lib import rf_signals, rf_state

M1 = dataset("m1")
B5 = dataset("m5_summer")

def rs(m1, rule):
    o = m1.resample(rule, label="left", closed="left").agg(
        {"open":"first","high":"max","low":"min","close":"last","volume":"sum"})
    return o.dropna()

SAMPLES = {"2M Jan": (rs(M1,"2min"), M1, 2), "3M Jan": (rs(M1,"3min"), M1, 3),
           "5M Jan": (rs(M1,"5min"), M1, 5), "5M Jun-Aug": (B5, None, 5)}

def cfg_for(tf):
    return Config(start_balance_gbp=100.0, lots=0.02, spread_usd=0.20, tf_minutes=tf,
                  rr=2.0, exit_mode="partial", trail_mode="swing",
                  use_range_module=True, use_sweep_module=True,
                  use_trend_module=False, use_breakout_module=False)

def rf_context(d):
    """+1 while the range filter is long-side, -1 while short-side."""
    F = rf_state(d.close, 27, 1.6)
    S = rf_state(d.close, 55, 2.0)
    st = np.where((d.close > F.filt) & (d.close > S.filt), 1,
         np.where((d.close < F.filt) & (d.close < S.filt), -1, 0))
    return pd.Series(st, index=d.index)

JAN = ["2M Jan", "3M Jan", "5M Jan"]
print("=" * 104)
print("MEAN-REVERSION ENGINE (range fade + liquidity sweep), 0.02 lots, half at 1R, swing trail")
print("=" * 104)
print(f"{'sample':<12} {'trades':>7} {'win%':>7} {'exp R':>8} {'net £':>9} {'DD%':>7}   "
      f"{'RF-aligned':>26} {'RF-opposed':>26}")

rows = []
for nm, (d, m1, tf) in SAMPLES.items():
    cfg = cfg_for(tf)
    tr, eq, feat = backtest(d, cfg, m1)
    st = stats(tr, eq, cfg)
    base = (f"{len(tr):>7} {st.get('win_rate', float('nan')):>6.1f}% "
            f"{tr.r_multiple.mean():>+8.3f} {tr.pnl_gbp.sum():>+9.1f} "
            f"{st.get('max_dd_pct', float('nan')):>6.1f}%")

    # split the SAME trades by whether the range filter agreed with them
    ctx = rf_context(d).reindex(tr.entry_time if "entry_time" in tr else tr.index)
    if "entry_time" in tr.columns:
        ctx = rf_context(d).reindex(pd.DatetimeIndex(tr.entry_time)).to_numpy()
    else:
        ctx = np.zeros(len(tr))
    side = np.where(tr.side.to_numpy() == "long", 1, -1) if "side" in tr.columns else np.zeros(len(tr))
    aligned = ctx == side
    opposed = ctx == -side

    def blurb(mask):
        if mask.sum() == 0:
            return f"{'-':>26}"
        sub = tr[mask]
        return f"{sub.r_multiple.mean():>+7.3f}R {(sub.r_multiple>0).mean()*100:>5.1f}% n={len(sub):<5}"

    print(f"{nm:<12} {base}   {blurb(aligned):>26} {blurb(opposed):>26}")
    rows.append(dict(sample=nm, n=len(tr), exp_r=tr.r_multiple.mean(),
                     net=tr.pnl_gbp.sum(),
                     aligned_r=tr[aligned].r_multiple.mean() if aligned.sum() else np.nan,
                     aligned_n=int(aligned.sum()),
                     opposed_r=tr[opposed].r_multiple.mean() if opposed.sum() else np.nan,
                     opposed_n=int(opposed.sum())))

R = pd.DataFrame(rows)
R.to_csv("compare.csv", index=False)

print("\n" + "-" * 104)
jan_al = np.nansum(R[R['sample'].isin(JAN)].aligned_r * R[R['sample'].isin(JAN)].aligned_n) / \
         max(R[R['sample'].isin(JAN)].aligned_n.sum(), 1)
jan_op = np.nansum(R[R['sample'].isin(JAN)].opposed_r * R[R['sample'].isin(JAN)].opposed_n) / \
         max(R[R['sample'].isin(JAN)].opposed_n.sum(), 1)
jun = R[R['sample'] == "5M Jun-Aug"].iloc[0]
print(f"RF as a context filter, weighted:")
print(f"   January   aligned {jan_al:+.3f}R   opposed {jan_op:+.3f}R")
print(f"   June-Aug  aligned {jun.aligned_r:+.3f}R   opposed {jun.opposed_r:+.3f}R")
print("saved compare.csv")
