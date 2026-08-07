"""
Week-by-week signal accuracy, split by direction.

Win rate at a fixed 2R target conflates two different things: whether the signal
picked the right DIRECTION, and whether the exit geometry captured it. So this
measures direction quality separately:

  reached +1R before -1R   how often the signal was right before the target
                           distance mattered. This is the cleanest read on
                           whether BUY means up and SELL means down.
  MFE / MAE in R           how far the trade ran in favour / against before
                           resolving. Tells you whether losers went straight
                           against you or wobbled first.

Where 1-minute data exists (Sample A) the +1R-vs--1R race is resolved minute by
minute. Elsewhere, when a single 5-minute bar contains both levels, the ADVERSE
one is assumed first, so these numbers are the pessimistic reading.
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from xau_engine import Config, backtest, stats, _m1_index

LON = "Europe/London"
A5 = pd.read_pickle("/home/claude/m5.pkl")
A1 = pd.read_pickle("/home/claude/m1.pkl")
B5 = pd.read_pickle("/home/claude/m5_summer.pkl")
BREAKEVEN_WR = 1.0 / 3.0 * 100.0          # 33.3% at 2R


def cfg_for(sample: str, **over) -> Config:
    base = dict(gbpusd=1.27, max_stop_atr=2.0)
    if sample == "B":
        base["spread_usd"] = 0.20
    return Config(**{**base, **over})


def excursions(tr: pd.DataFrame, bars: pd.DataFrame, m1: pd.DataFrame | None):
    """Per trade: MFE, MAE (in R) and which of +1R / -1R was reached first."""
    idx = {ts: i for i, ts in enumerate(bars.index)}
    m1map = _m1_index(m1)
    hi = bars["high"].to_numpy(float)
    lo = bars["low"].to_numpy(float)
    out = []
    for t in tr.itertuples():
        i0, i1 = idx[t.entry_time], idx[t.exit_time]
        risk = abs(t.entry - t.sl)
        if risk <= 0:
            out.append((np.nan, np.nan, None)); continue
        sgn = 1.0 if t.side == "long" else -1.0
        one_up = t.entry + sgn * risk          # +1R level
        one_dn = t.entry - sgn * risk          # -1R level (= the stop)
        mfe = mae = 0.0
        first = None
        for i in range(i0 + 1, i1 + 1):
            fav = (hi[i] - t.entry) * sgn      # best move in our favour this bar
            adv = (t.entry - lo[i]) * sgn if t.side == "long" else (hi[i] - t.entry) * -sgn
            if t.side == "long":
                fav = (hi[i] - t.entry)
                adv = (t.entry - lo[i])
                up_hit = hi[i] >= one_up
                dn_hit = lo[i] <= one_dn
            else:
                fav = (t.entry - lo[i])
                adv = (hi[i] - t.entry)
                up_hit = lo[i] <= one_up
                dn_hit = hi[i] >= one_dn
            mfe = max(mfe, fav / risk)
            mae = max(mae, adv / risk)
            if first is None and (up_hit or dn_hit):
                if up_hit and dn_hit:
                    # both inside one 5m bar: ask the minute data, else assume adverse
                    res = None
                    if m1map is not None:
                        m1b = m1map.get(bars.index[i])
                        if m1b is not None:
                            mh, ml = m1b
                            for k in range(len(mh)):
                                if t.side == "long":
                                    u, d = mh[k] >= one_up, ml[k] <= one_dn
                                else:
                                    u, d = ml[k] <= one_up, mh[k] >= one_dn
                                if u and d:
                                    res = "adverse"; break
                                if u:
                                    res = "favourable"; break
                                if d:
                                    res = "adverse"; break
                    first = res if res else "adverse"
                else:
                    first = "favourable" if up_hit else "adverse"
        out.append((mfe, mae, first))
    return pd.DataFrame(out, columns=["mfe_r", "mae_r", "first_1r"], index=tr.index)


def wilson(k: int, n: int, z: float = 1.96):
    """Confidence interval for a hit rate — honest on small weekly samples."""
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, (c - h)) * 100, min(1.0, (c + h)) * 100)


def main():
    SAMPLES = [("A", A5, A1), ("B", B5, None)]
    frames = {}

    print("=" * 96)
    print("WEEK BY WEEK, SPLIT BY DIRECTION   (shipped defaults: sweep + range on, trend off)")
    print("=" * 96)
    for key, df, m1 in SAMPLES:
        cfg = cfg_for(key)
        tr, eq, feat = backtest(df, cfg, m1=m1)
        ex = excursions(tr, feat, m1)
        tr = pd.concat([tr, ex], axis=1)
        tr["wk"] = [t.tz_convert(LON).isocalendar()[1] for t in tr.entry_time]
        frames[key] = (tr, feat, cfg)

        print(f"\nSample {key} — {tr.entry_time.min():%d %b} to {tr.entry_time.max():%d %b}")
        print(f"{'week':>5} {'BUY n':>6} {'BUY win%':>9} {'BUY R':>7} {'SELL n':>7} {'SELL win%':>10} "
              f"{'SELL R':>7} {'net £':>8} {'dir.acc':>8}")
        for wk, g in tr.groupby("wk"):
            L, S = g[g.side == "long"], g[g.side == "short"]
            acc = g.first_1r.eq("favourable").mean() * 100 if len(g) else np.nan
            print(f"{wk:>5} {len(L):>6} {((L.pnl_gbp>0).mean()*100 if len(L) else np.nan):>8.1f}% "
                  f"{(L.r_multiple.mean() if len(L) else np.nan):>+7.2f} {len(S):>7} "
                  f"{((S.pnl_gbp>0).mean()*100 if len(S) else np.nan):>9.1f}% "
                  f"{(S.r_multiple.mean() if len(S) else np.nan):>+7.2f} "
                  f"{g.pnl_gbp.sum():>+8.2f} {acc:>7.1f}%")
        wkn = tr.groupby("wk").pnl_gbp.sum()
        print(f"  weeks profitable: {int((wkn>0).sum())} of {len(wkn)}")

    print()
    print("=" * 96)
    print("DIRECTIONAL ACCURACY — did BUY mean up and SELL mean down?")
    print("=" * 96)
    print("'reached +1R before -1R' ignores the 2R target, so it isolates direction from exit geometry.")
    print(f"{'sample':>7} {'side':>6} {'n':>5} {'+1R first':>10} {'95% CI':>18} {'win% @2R':>9} "
          f"{'mean MFE':>9} {'mean MAE':>9}")
    for key, (tr, feat, cfg) in frames.items():
        for side in ["long", "short", "all"]:
            g = tr if side == "all" else tr[tr.side == side]
            if len(g) == 0:
                continue
            k = int(g.first_1r.eq("favourable").sum())
            lo, hi = wilson(k, len(g))
            print(f"{key:>7} {side:>6} {len(g):>5} {k/len(g)*100:>9.1f}% "
                  f"{f'{lo:.1f} - {hi:.1f}%':>18} {(g.pnl_gbp>0).mean()*100:>8.1f}% "
                  f"{g.mfe_r.mean():>+9.2f} {g.mae_r.mean():>+9.2f}")

    allt = pd.concat([frames[k][0] for k in frames])
    k = int(allt.first_1r.eq("favourable").sum())
    lo, hi = wilson(k, len(allt))
    print(f"\nPOOLED: {k}/{len(allt)} = {k/len(allt)*100:.1f}% reached +1R first "
          f"(95% CI {lo:.1f}-{hi:.1f}%). A coin flip is 50%.")
    print(f"        win rate at the 2R target: {(allt.pnl_gbp>0).mean()*100:.1f}% "
          f"(break-even needs {BREAKEVEN_WR:.1f}%)")
    for side in ["long", "short"]:
        g = allt[allt.side == side]
        print(f"        {side:<5}: {len(g):>3} trades, {(g.pnl_gbp>0).mean()*100:.1f}% win rate, "
              f"{g.r_multiple.mean():+.3f}R")

    # ── rolling walk-forward across every week of both samples ──────────────────
    print()
    print("=" * 96)
    print("ROLLING WALK-FORWARD — every week tested on rules fitted only to earlier weeks")
    print("=" * 96)
    import itertools
    GRID = list(itertools.product([1.5, 2.0, 2.5], [2.0, 2.5], [2, 3], [1, 2]))
    for key, df, m1 in SAMPLES:
        cache = {}
        for g in GRID:
            c = cfg_for(key)
            c.rr, c.max_stop_atr, c.range_min_score, c.sweep_min_touches = g
            t, _, _ = backtest(df, c, m1=m1)
            if len(t):
                t["wk"] = [x.tz_convert(LON).isocalendar()[1] for x in t.entry_time]
            cache[g] = t
        weeks = sorted(frames[key][0].wk.unique())
        print(f"\nSample {key}: {len(weeks)} weeks, grid of {len(GRID)} parameter sets")
        print(f"{'test wk':>8} {'chosen on earlier weeks':>26} {'n':>4} {'win%':>7} {'net £':>8} "
              f"{'R':>7}   {'untuned same wk':>16}")
        oos, unt = [], []
        base = frames[key][0]
        for wk in weeks:
            prior = [w for w in weeks if w < wk]
            train = pd.concat([cache[g][cache[g].wk.isin(prior)] for g in [GRID[0]]]) if prior else None
            if not prior or train is None or len(train) < 8:
                print(f"{wk:>8} {'(not enough history)':>26}")
                continue
            best, bs = None, -9
            for g, t in cache.items():
                if not len(t):
                    continue
                tin = t[t.wk.isin(prior)]
                if len(tin) < 8:
                    continue
                if tin.r_multiple.mean() > bs:
                    bs, best = tin.r_multiple.mean(), g
            o = cache[best][cache[best].wk == wk]
            u = base[base.wk == wk]
            oos.append(o); unt.append(u)
            tag = f"rr{best[0]} cap{best[1]} rm{best[2]} sw{best[3]}"
            print(f"{wk:>8} {tag:>26} {len(o):>4} "
                  f"{((o.pnl_gbp>0).mean()*100 if len(o) else np.nan):>6.1f}% {o.pnl_gbp.sum():>+8.2f} "
                  f"{(o.r_multiple.mean() if len(o) else np.nan):>+7.2f}   "
                  f"{u.pnl_gbp.sum():>+8.2f} ({u.r_multiple.mean():+.2f}R)")
        if oos:
            O, U = pd.concat(oos), pd.concat(unt)
            print(f"{'TOTAL':>8} {'tuned':>26} {len(O):>4} {(O.pnl_gbp>0).mean()*100:>6.1f}% "
                  f"{O.pnl_gbp.sum():>+8.2f} {O.r_multiple.mean():>+7.2f}   "
                  f"{U.pnl_gbp.sum():>+8.2f} ({U.r_multiple.mean():+.2f}R) untuned")

    allt.to_csv("/home/claude/trades_with_accuracy.csv", index=False)
    print("\nsaved trades_with_accuracy.csv (adds mfe_r, mae_r, first_1r per trade)")


if __name__ == '__main__':
    main()
