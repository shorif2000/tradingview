"""
Week-by-week analysis, statistical reality check, parameter sensitivity and
walk-forward tuning on the real MT5 sample.

Design note: per-week numbers come from ONE full-sample backtest with the trades
sliced by week afterwards. Re-running the engine on a one-week slice would throw
away the 215-bar warm-up (EMA200 + BB-width percentile) and silently change the
signals, which would make the weeks incomparable.
"""
from __future__ import annotations
import itertools
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from xau_engine import Config, backtest, stats

M5 = pd.read_pickle("/home/claude/m5.pkl")
M1 = pd.read_pickle("/home/claude/m1.pkl")
LON = "Europe/London"


def week_key(ts):
    t = ts.tz_convert(LON)
    iso = t.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def summarise(tr: pd.DataFrame, label: str, start_bal=100.0) -> dict:
    if len(tr) == 0:
        return {"period": label, "trades": 0, "wr": np.nan, "net": 0.0, "exp_r": np.nan}
    return {"period": label, "trades": len(tr),
            "wr": (tr.pnl_gbp > 0).mean() * 100,
            "net": tr.pnl_gbp.sum(),
            "exp_r": tr.r_multiple.mean(),
            "worst": tr.pnl_gbp.min(), "best": tr.pnl_gbp.max()}


def run(cfg: Config):
    tr, eq, feat = backtest(M5, cfg, m1=M1)
    return tr, eq, feat


# ═══════════════════════════════════════════════════════════════════════════
print("=" * 78)
print("BASELINE — default parameters, real spread from the file, M1-resolved fills")
print("=" * 78)
base = Config(gbpusd=1.27)
tr, eq, feat = run(base)
st = stats(tr, eq, base)
print(f"{st['trades']} trades | win rate {st['win_rate']:.1f}% | PF {st['profit_factor']:.2f} "
      f"| net £{st['net_gbp']:+.2f} | expectancy {st['expectancy_r']:+.3f}R "
      f"| max DD {st['max_dd_pct']:.1f}%")

# ── statistical reality check ───────────────────────────────────────────────
print()
print("=" * 78)
print("IS THIS EDGE OR IS IT NOISE?")
print("=" * 78)
r = tr.r_multiple.to_numpy()
n = len(r)
mean_r, sd_r = r.mean(), r.std(ddof=1)
se = sd_r / np.sqrt(n)
t_stat = mean_r / se
print(f"expectancy      {mean_r:+.3f}R  (sd {sd_r:.3f}, n={n})")
print(f"standard error  {se:.3f}   ->  t = {t_stat:.2f}")

rng = np.random.default_rng(42)
boot = np.array([rng.choice(r, size=n, replace=True).mean() for _ in range(20000)])
lo, hi = np.percentile(boot, [2.5, 97.5])
p_neg = (boot <= 0).mean()
print(f"bootstrap 95% CI on expectancy: {lo:+.3f}R to {hi:+.3f}R")
print(f"probability the true edge is <= 0 given this sample: {p_neg*100:.1f}%")

# what the same trades would look like reshuffled into different orders
finals = []
for _ in range(20000):
    seq = rng.permutation(tr.pnl_gbp.to_numpy())
    finals.append(100.0 + seq.cumsum().min())      # worst equity point along the path
print(f"reshuffling the SAME trades: 5th-percentile worst equity dip = "
      f"£{np.percentile(finals,5):.2f}  (order mattered a lot here)")

# break-even win rate at this R
be_wr = 1.0 / (1.0 + base.rr) * 100
print(f"break-even win rate at {base.rr:g}R = {be_wr:.1f}% ; achieved {st['win_rate']:.1f}%")

# ── week by week ────────────────────────────────────────────────────────────
print()
print("=" * 78)
print("WEEK BY WEEK")
print("=" * 78)
tr["week"] = [week_key(t) for t in tr.entry_time]
rows = [summarise(g, w) for w, g in tr.groupby("week")]
wk = pd.DataFrame(rows)
print(wk.round(2).to_string(index=False))

print("\nby week and module:")
pv = tr.pivot_table(index="week", columns="module", values="pnl_gbp",
                    aggfunc=["size", "sum"]).fillna(0).round(2)
print(pv.to_string())

# ── day-of-week and hour ────────────────────────────────────────────────────
tr["dow"] = [t.tz_convert(LON).day_name()[:3] for t in tr.entry_time]
tr["hour"] = [t.tz_convert(LON).hour for t in tr.entry_time]
print("\nby London hour:")
h = tr.groupby("hour").agg(n=("pnl_gbp", "size"), wr=("pnl_gbp", lambda x: (x > 0).mean() * 100),
                           net=("pnl_gbp", "sum")).round(1)
print(h.to_string())

# ── parameter sensitivity: one factor at a time ──────────────────────────────
print()
print("=" * 78)
print("PARAMETER SENSITIVITY  (full sample; a stable edge should not swing wildly)")
print("=" * 78)
sens = {
    "rr":              [1.5, 2.0, 2.5, 3.0],
    "adx_trend_on":    [20, 23, 26, 29],
    "range_min_score": [2, 3, 4],
    "sweep_min_touches": [1, 2, 3],
    "max_stop_atr":    [2.0, 2.5, 3.0, 3.5],
    "min_atr_pct":     [0.0, 0.02, 0.04],
    "sess_start":      [0, 7, 8],
}
sens_rows = []
for k, vals in sens.items():
    for v in vals:
        c = Config(gbpusd=1.27, **{k: v})
        t2, e2, _ = run(c)
        if len(t2) == 0:
            sens_rows.append([k, v, 0, np.nan, 0.0, np.nan]); continue
        s2 = stats(t2, e2, c)
        sens_rows.append([k, v, s2["trades"], round(s2["win_rate"], 1),
                          round(s2["net_gbp"], 2), round(s2["expectancy_r"], 3)])
sdf = pd.DataFrame(sens_rows, columns=["param", "value", "trades", "win%", "net_£", "exp_R"])
print(sdf.to_string(index=False))
sdf.to_csv("/home/claude/sensitivity.csv", index=False)

# ── walk-forward: tune on everything BEFORE a week, test ON that week ───────
print()
print("=" * 78)
print("WALK-FORWARD  (parameters chosen only from earlier weeks, scored on the next)")
print("=" * 78)
grid = list(itertools.product([1.5, 2.0, 2.5],          # rr
                              [20, 23, 26],              # adx_trend_on
                              [2, 3],                    # range_min_score
                              [1, 2]))                   # sweep_min_touches
print(f"grid: {len(grid)} combinations")

cache = {}
for g in grid:
    c = Config(gbpusd=1.27, rr=g[0], adx_trend_on=g[1], range_min_score=g[2], sweep_min_touches=g[3])
    t2, e2, _ = run(c)
    if len(t2):
        t2["week"] = [week_key(x) for x in t2.entry_time]
    cache[g] = t2

weeks = sorted(tr.week.unique())
wf_rows = []
for i in range(1, len(weeks)):
    train_w, test_w = weeks[:i], weeks[i]
    best, best_score = None, -1e9
    for g, t2 in cache.items():
        if len(t2) == 0:
            continue
        tr_in = t2[t2.week.isin(train_w)]
        if len(tr_in) < 8:                     # refuse to "tune" on a handful of trades
            continue
        score = tr_in.r_multiple.mean()
        if score > best_score:
            best_score, best = score, g
    if best is None:
        wf_rows.append([test_w, "insufficient training trades", 0, np.nan, np.nan])
        continue
    t_out = cache[best][cache[best].week == test_w]
    wf_rows.append([test_w, f"rr={best[0]} adx={best[1]} rmin={best[2]} swp={best[3]}",
                    len(t_out),
                    round((t_out.pnl_gbp > 0).mean() * 100, 1) if len(t_out) else np.nan,
                    round(t_out.pnl_gbp.sum(), 2) if len(t_out) else np.nan])
wfdf = pd.DataFrame(wf_rows, columns=["test week", "params chosen on earlier weeks",
                                      "OOS trades", "OOS win%", "OOS net £"])
print(wfdf.to_string(index=False))

# how much does the best in-sample choice differ from the best out-of-sample choice?
print()
full_scores = {g: (t2.r_multiple.mean() if len(t2) else -9) for g, t2 in cache.items()}
best_full = max(full_scores, key=full_scores.get)
print(f"best parameters on the WHOLE sample: rr={best_full[0]} adx={best_full[1]} "
      f"rmin={best_full[2]} swp={best_full[3]}  -> {full_scores[best_full]:+.3f}R")
print(f"default parameters                 : rr=2.0 adx=23 rmin=2 swp=2  -> "
      f"{full_scores[(2.0,23,2,2)]:+.3f}R")
spread_of_grid = np.array([v for v in full_scores.values() if v > -9])
print(f"across the {len(spread_of_grid)} grid points, expectancy ranges "
      f"{spread_of_grid.min():+.3f}R to {spread_of_grid.max():+.3f}R "
      f"(sd {spread_of_grid.std():.3f})")

tr.to_csv("/home/claude/trades_real.csv", index=False)
print("\nsaved: trades_real.csv, sensitivity.csv")
