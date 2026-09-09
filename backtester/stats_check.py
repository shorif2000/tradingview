"""Confidence intervals, so the comparison is an interval and not a point estimate."""
import warnings
import numpy as np

warnings.filterwarnings("ignore")
from xau_engine import Config, backtest
from rf_lib import rf_signals, simulate
from samples import TF_MINUTES, boot, samples

S = samples()

rf_all, mr_all = [], []
for nm, (d, m1) in S.items():
    tf = TF_MINUTES[nm]
    rf_all.append(simulate(rf_signals(d, mode="both"), m1).r.to_numpy())
    cfg = Config(start_balance_gbp=100.0, lots=0.02, spread_usd=0.20, tf_minutes=tf, rr=2.0,
                 exit_mode="partial", trail_mode="swing", use_range_module=True,
                 use_sweep_module=True, use_trend_module=False, use_breakout_module=False)
    tr,_,_ = backtest(d, cfg, m1)
    mr_all.append(tr.r_multiple.to_numpy())

for nm, arrs in (("RANGE FILTER", rf_all), ("MEAN REVERSION", mr_all)):
    pooled = np.concatenate(arrs)
    lo, hi, p = boot(pooled)
    print(f"{nm:<16} pooled n={len(pooled):<5} mean {pooled.mean():+.3f}R   "
          f"95% CI [{lo:+.3f}, {hi:+.3f}]   P(no edge) {p*100:.1f}%")
print()
for i,(nm,_) in enumerate(S.items()):
    lo,hi,p = boot(mr_all[i])
    print(f"  MR {nm:<12} n={len(mr_all[i]):<4} {mr_all[i].mean():+.3f}R  CI [{lo:+.3f}, {hi:+.3f}]  P(no edge) {p*100:4.1f}%")
