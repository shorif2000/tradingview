"""Baseline: how good are the range filter's longs and shorts, on 2M / 3M / 5M."""
from __future__ import annotations
import warnings
import pandas as pd

warnings.filterwarnings("ignore")
from rf_lib import rf_signals, simulate, summarise, direction_accuracy
from samples import samples

SAMPLES = samples()

print(f"{'sample':<12} {'bars':>7}  {'from':<17} {'to':<17}")
for k, (d, _) in SAMPLES.items():
    print(f"{k:<12} {len(d):>7,}  {str(d.index[0])[:16]:<17} {str(d.index[-1])[:16]:<17}")

print("\n" + "=" * 100)
print("BASELINE — the original's settings (fast 27/1.6, slow 55/2), all three combination modes")
print("=" * 100)
print(f"{'sample':<12} {'mode':<6} {'trades':>7} {'win%':>7} {'longW%':>7} {'shortW%':>8} "
      f"{'exp R':>8} {'net £':>8} {'DD%':>6}   direction-only 10/20/40 bars")

rows = []
for name, (d, m1) in SAMPLES.items():
    for mode in ("both", "fast", "slow"):
        sg = rf_signals(d, mode=mode)
        tr = simulate(sg, m1)
        s = summarise(tr, f"{name}|{mode}")
        da = direction_accuracy(sg)
        acc = "  ".join(f"{da[h][0]:5.1f}%" for h in (10, 20, 40))
        n_sig = int(sg.rf_long.sum() + sg.rf_short.sum())
        print(f"{name:<12} {mode:<6} {s['n']:>7} {s['win']:>6.1f}% "
              f"{s.get('long_win', float('nan')):>6.1f}% {s.get('short_win', float('nan')):>7.1f}% "
              f"{s['exp_r']:>+8.3f} {s['net']:>+8.1f} {s['dd']:>5.1f}%   {acc}  (n={n_sig})")
        s.update(sample=name, mode=mode, sigs=n_sig,
                 d10=da[10][0], d20=da[20][0], d40=da[40][0])
        rows.append(s)

pd.DataFrame(rows).to_csv("baseline.csv", index=False)
print("\nsaved baseline.csv")
