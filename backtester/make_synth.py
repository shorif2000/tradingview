"""
Synthetic 5-minute XAUUSD generator — ENGINE VALIDATION ONLY.

This exists so the backtest code can be proven correct (fills, R-multiples,
equity maths, guardrails) before real data arrives. Performance numbers from
synthetic data are NOT a measure of edge and must never be reported as one.

It is built to be structurally realistic rather than statistically identical
to gold: alternating trending / mean-reverting / choppy regimes, an intraday
volatility profile (Asian dead zone, London and NY expansions), weekend gaps
and occasional news spikes.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def make_synth(start="2026-02-05", end="2026-08-05", start_price=3300.0, seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    idx = pd.date_range(start, end, freq="5min", tz="UTC")
    idx = idx[idx.dayofweek < 5]                                    # weekdays only
    # gold trades ~22h/day; drop the daily maintenance break 21:00-22:00 UTC
    idx = idx[~((idx.hour == 21))]
    n = len(idx)

    # ── intraday volatility profile (multiplier on base vol) ────────────────
    hour = idx.hour.to_numpy()
    prof = np.select(
        [hour < 6, hour < 7, hour < 12, hour < 13, hour < 17, hour < 20],
        [0.45,     0.75,     1.15,      1.35,      1.55,      1.10],
        default=0.65)

    # ── regime process: 0 = chop, 1 = trend, 2 = mean-revert ────────────────
    regime = np.zeros(n, dtype=int)
    persist = np.array([0.9985, 0.9990, 0.9988])
    cur = 0
    trend_sign = 1.0
    trend_strength = 0.0
    reg_list = np.zeros(n, dtype=int)
    for i in range(n):
        if rng.random() > persist[cur]:
            cur = rng.choice([0, 1, 2], p=[0.35, 0.35, 0.30])
            trend_sign = rng.choice([-1.0, 1.0])
            trend_strength = rng.uniform(0.15, 0.55)
        reg_list[i] = cur
    regime = reg_list

    # ── stochastic base volatility (log-OU) ────────────────────────────────
    base = 0.00030                       # ~3.0 bp per 5m bar
    logv = np.zeros(n)
    logv[0] = np.log(base)
    for i in range(1, n):
        logv[i] = logv[i - 1] + 0.004 * (np.log(base) - logv[i - 1]) + 0.05 * rng.standard_normal()
    vol = np.exp(logv) * prof

    # ── price path ─────────────────────────────────────────────────────────
    px = np.zeros(n)
    px[0] = start_price
    anchor = start_price
    drift_run = 0.0
    for i in range(1, n):
        r = reg_list[i]
        if r == 1:                                                  # trending
            if reg_list[i - 1] != 1:
                drift_run = rng.choice([-1.0, 1.0]) * rng.uniform(0.04, 0.18)
            mu = drift_run * vol[i]
        elif r == 2:                                                # mean reverting
            if reg_list[i - 1] != 2:
                anchor = px[i - 1]
            mu = -0.015 * (px[i - 1] - anchor) / px[i - 1]
        else:
            mu = 0.0
            drift_run = 0.0
        shock = 0.0
        if rng.random() < 0.00035:                                  # news spike
            shock = rng.choice([-1.0, 1.0]) * rng.uniform(3.0, 9.0) * vol[i]
        px[i] = px[i - 1] * (1.0 + mu + vol[i] * rng.standard_normal() + shock)

    # weekend gaps
    day = idx.dayofweek.to_numpy()
    newweek = np.where((day == 0) & (np.roll(day, 1) == 4))[0]
    for k in newweek:
        if k == 0:
            continue
        gap = rng.standard_normal() * 0.0025
        px[k:] *= (1.0 + gap)

    # ── build OHLC from the close path with plausible wicks ────────────────
    close = px
    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    span = np.abs(close - open_) + vol * close * rng.uniform(0.15, 0.65, n)
    up = rng.uniform(0.05, 0.75, n)
    high = np.maximum(open_, close) + span * up
    low = np.minimum(open_, close) - span * (1.0 - up)

    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                       "volume": rng.integers(200, 3000, n).astype(float)}, index=idx)
    df.index.name = "time"
    df["regime_true"] = reg_list
    return df


if __name__ == "__main__":
    d = make_synth()
    d.drop(columns=["regime_true"]).to_csv("/home/claude/synth_xauusd_5m.csv")
    tr = d.high - d.low
    print(f"bars={len(d):,}  {d.index[0]} -> {d.index[-1]}")
    print(f"price {d.close.min():.1f}-{d.close.max():.1f}   mean 5m range ${tr.mean():.2f}")
    print(f"regime mix: chop={100*(d.regime_true==0).mean():.0f}%  "
          f"trend={100*(d.regime_true==1).mean():.0f}%  mr={100*(d.regime_true==2).mean():.0f}%")
