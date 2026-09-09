"""
Re-run with the rule CALIBRATED against the original's own signals.

The settings dialog says Fast Period 27 / Fast Range 1.6, and feeding those
straight into the public range-filter algorithm reproduces only ~60% of the
indicator's actual markers. Fitting the two parameters against 2,600 bars of the
real thing lands on 38 / 1.8, which reproduces 94-96% of them on BOTH 3m and 5m.
Same parameters on two timeframes, so it is a chart-timeframe rule and not a
higher-timeframe request in disguise. Whatever transformation sits between the
displayed inputs and the filter, THIS is the rule that matches the markers.
"""
import warnings
import numpy as np

warnings.filterwarnings("ignore")
from rf_lib import rf_signals, simulate, summarise, direction_accuracy
from samples import boot, samples

S = samples()

CAL = dict(fast=(38, 1.8), mode="fast")
print(f"{'sample':<12} {'sigs':>5} {'trades':>7} {'win%':>7} {'longW%':>7} {'shortW%':>8} "
      f"{'exp R':>8} {'DD%':>7}   direction 10/20/40")
allr = []
for nm,(d,m1) in S.items():
    sg = rf_signals(d, **CAL)
    tr = simulate(sg, m1)
    s = summarise(tr, nm); da = direction_accuracy(sg)
    allr.append(tr.r.to_numpy())
    print(f"{nm:<12} {int(sg.rf_long.sum()+sg.rf_short.sum()):>5} {s['n']:>7} {s['win']:>6.1f}% "
          f"{s['long_win']:>6.1f}% {s['short_win']:>7.1f}% {s['exp_r']:>+8.3f} {s['dd']:>6.1f}%   "
          + "  ".join(f"{da[h][0]:5.1f}%" for h in (10,20,40)))

pooled = np.concatenate(allr)
lo, hi, p = boot(pooled)
print(f"\nCALIBRATED (38/1.8, fast) pooled n={len(pooled)}  {pooled.mean():+.3f}R  "
      f"95% CI [{lo:+.3f}, {hi:+.3f}]  P(no edge) {p*100:.1f}%")
