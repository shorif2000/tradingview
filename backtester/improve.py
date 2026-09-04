"""
Improving the signal, guided by the diagnosis rather than by guesswork.

Two things separated winners from losers in BOTH periods:

  stretch  = |close - EMA21| / ATR at the signal bar.  LOW half is better.
  adx(14)  at the signal bar.                          HIGH half is better.

Both say the same thing about a range filter: it is a lagging step-follower, so
it fires AFTER a move has travelled. The false signals are disproportionately the
ones where price has already run — you are buying the top of the spike. Two ways
to act on that:

  FILTER  — refuse the trade when price is too extended, or when ADX says there
            is no trend to follow.
  PULLBACK — do not chase. Leave a limit order back at the EMA21 (or at the
            filter line) and only trade if price comes to you.

Everything is judged on the same rule as the rest of this project: it has to be
positive in the January samples AND in June-August, which have opposite market
direction. That bar has already killed fourteen earlier attempts.
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from paths import dataset
from xau_engine import ema, atr as atr_fn, dmi
from rf_lib import rf_signals

CAL = dict(fast=(38, 1.8), mode="fast")


def rs(m1, rule):
    o = m1.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return o.dropna()


M1 = dataset("m1")
B5 = dataset("m5_summer")
SAMPLES = {"2M Jan": (rs(M1, "2min"), M1), "3M Jan": (rs(M1, "3min"), M1),
           "5M Jan": (rs(M1, "5min"), M1), "5M Jun-Aug": (B5, None)}
JAN = ["2M Jan", "3M Jan", "5M Jan"]


def prep(d):
    sg = rf_signals(d, **CAL)
    sg["atr"] = atr_fn(sg.high, sg.low, sg.close, 14)
    sg["ema21"] = ema(sg.close, 21)
    _, _, adx = dmi(sg.high, sg.low, sg.close, 14, 14)
    sg["adx"] = adx
    sg["stretch"] = (sg.close - sg.ema21).abs() / sg.atr
    return sg


PREP = {nm: (prep(d), m1) for nm, (d, m1) in SAMPLES.items()}


def _m1_arrays(m1):
    if m1 is None:
        return None, None
    return m1.index.to_numpy(), m1[["high", "low"]].to_numpy(float)


def _first_touch(m1_idx, m1_hl, t, side, sl, tp):
    if m1_idx is None:
        return None
    a = np.searchsorted(m1_idx, t, "left")
    b = np.searchsorted(m1_idx, t, "right")
    b = max(b, a + 1)
    for h, l in m1_hl[a:b]:
        if side == "long":
            if l <= sl:
                return "sl"
            if h >= tp:
                return "tp"
        else:
            if h >= sl:
                return "sl"
            if l <= tp:
                return "tp"
    return None


def run(sg, m1, *, entry="market", limit_ref="ema21", limit_bars=8,
        max_stretch=None, min_adx=None, exit_mode="2R", rr=2.0, sl_mult=1.2,
        spread=0.20, slip=0.10, max_bars=60, gbp=1.27, lots=0.01):
    idx = sg.index.to_numpy()
    o, h, l, c = (sg[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    L, S = sg.rf_long.to_numpy(bool), sg.rf_short.to_numpy(bool)
    av, e21, adx, st = (sg[x].to_numpy(float) for x in ("atr", "ema21", "adx", "stretch"))
    filt = sg.f_filt.to_numpy(float)
    m1_idx, m1_hl = _m1_arrays(m1)
    n = len(sg)
    rows = []
    i = 1
    while i < n - 2:
        side = "long" if L[i] else ("short" if S[i] else None)
        if side is None or not np.isfinite(av[i]) or av[i] <= 0:
            i += 1
            continue
        if max_stretch is not None and not (st[i] <= max_stretch):
            i += 1
            continue
        if min_adx is not None and not (adx[i] >= min_adx):
            i += 1
            continue

        risk = sl_mult * av[i]
        j = i + 1
        if entry == "market":
            fill = o[j] + spread / 2 + slip if side == "long" else o[j] - spread / 2 - slip
            k0 = j
        else:
            ref = e21[i] if limit_ref == "ema21" else filt[i]
            k0 = None
            for k in range(j, min(j + limit_bars, n)):
                if side == "long" and l[k] <= ref:
                    k0 = k
                    break
                if side == "short" and h[k] >= ref:
                    k0 = k
                    break
                # an opposite signal cancels a resting order
                if (side == "long" and S[k]) or (side == "short" and L[k]):
                    break
            if k0 is None:
                i += 1
                continue
            fill = ref + spread / 2 if side == "long" else ref - spread / 2

        sl = fill - risk if side == "long" else fill + risk
        tp = fill + rr * risk if side == "long" else fill - rr * risk
        out_k, why, px = None, None, None
        half_done = False
        realised = 0.0
        trail = None
        for k in range(k0, min(k0 + max_bars, n)):
            if exit_mode == "flip":
                if (side == "long" and S[k]) or (side == "short" and L[k]):
                    out_k, why = k, "flip"
                    px = c[k]
                    break
            r = _first_touch(m1_idx, m1_hl, idx[k], side, sl, tp)
            if r is None:
                if side == "long":
                    hs, ht = l[k] <= sl, h[k] >= tp
                else:
                    hs, ht = h[k] >= sl, l[k] <= tp
                r = "sl" if hs else ("tp" if ht else None)
            if exit_mode == "partial":
                one_r = fill + risk if side == "long" else fill - risk
                if not half_done:
                    reached = h[k] >= one_r if side == "long" else l[k] <= one_r
                    if reached and r != "sl":
                        half_done = True
                        realised += 0.5 * 1.0
                if half_done:
                    sw = (l[max(k - 8, 0):k + 1].min() if side == "long"
                          else h[max(k - 8, 0):k + 1].max())
                    trail = sw if trail is None else (max(trail, sw) if side == "long" else min(trail, sw))
                    hit_tr = (l[k] <= trail) if side == "long" else (h[k] >= trail)
                    if hit_tr:
                        out_k, why, px = k, "trail", trail
                        break
            if r is not None:
                out_k, why = k, r
                px = sl if r == "sl" else tp
                break
        if out_k is None:
            out_k, why, px = min(k0 + max_bars - 1, n - 1), "time", c[min(k0 + max_bars - 1, n - 1)]

        mv = (px - fill) if side == "long" else (fill - px)
        r_mult = mv / risk
        if exit_mode == "partial" and half_done:
            r_mult = realised + 0.5 * r_mult
        pnl = (r_mult * risk * lots * 100.0 - spread * lots * 100.0) / gbp
        rows.append(dict(t=idx[i], side=side, r=r_mult, pnl=pnl, why=why))
        i = out_k + 1
    return pd.DataFrame(rows)


def evaluate(label, **kw):
    per = {}
    for nm, (sg, m1) in PREP.items():
        tr = run(sg, m1, **kw)
        per[nm] = tr
    jan = pd.concat([per[s] for s in JAN])
    jun = per["5M Jun-Aug"]
    if len(jan) == 0 or len(jun) == 0:
        return None
    je, ue = jan.r.mean(), jun.r.mean()
    ok = je > 0 and ue > 0
    return dict(label=label, jan_n=len(jan), jan_r=je, jan_win=(jan.r > 0).mean() * 100,
                jun_n=len(jun), jun_r=ue, jun_win=(jun.r > 0).mean() * 100,
                both_positive=ok)


CONFIGS = [
    ("baseline market 2R",            dict()),
    ("baseline market flip",          dict(exit_mode="flip")),
    ("baseline market partial",       dict(exit_mode="partial")),
    ("stretch<=0.75",                 dict(max_stretch=0.75)),
    ("stretch<=0.50",                 dict(max_stretch=0.50)),
    ("adx>=20",                       dict(min_adx=20)),
    ("adx>=25",                       dict(min_adx=25)),
    ("stretch<=0.75 + adx>=20",       dict(max_stretch=0.75, min_adx=20)),
    ("stretch<=0.50 + adx>=25",       dict(max_stretch=0.50, min_adx=25)),
    ("PULLBACK to EMA21",             dict(entry="limit", limit_ref="ema21")),
    ("PULLBACK to filter",            dict(entry="limit", limit_ref="filt")),
    ("PULLBACK + adx>=20",            dict(entry="limit", limit_ref="ema21", min_adx=20)),
    ("PULLBACK partial exit",         dict(entry="limit", limit_ref="ema21", exit_mode="partial")),
    ("PULLBACK flip exit",            dict(entry="limit", limit_ref="ema21", exit_mode="flip")),
    ("PULLBACK 3R",                   dict(entry="limit", limit_ref="ema21", rr=3.0)),
    ("PULLBACK 1.5R",                 dict(entry="limit", limit_ref="ema21", rr=1.5)),
    ("PULLBACK+adx20 partial",        dict(entry="limit", limit_ref="ema21", min_adx=20, exit_mode="partial")),
]

print("=" * 104)
print("Each row must be positive in BOTH January and June-August. Baseline first.")
print("=" * 104)
print(f"{'config':<26} {'Jan n':>6} {'Jan R':>8} {'Jan win':>8} | {'Jun n':>6} {'Jun R':>8} {'Jun win':>8}   verdict")
out = []
for label, kw in CONFIGS:
    r = evaluate(label, **kw)
    if r is None:
        print(f"{label:<26} (no trades)")
        continue
    v = "BOTH POSITIVE" if r["both_positive"] else ""
    print(f"{r['label']:<26} {r['jan_n']:>6} {r['jan_r']:>+8.3f} {r['jan_win']:>7.1f}% | "
          f"{r['jun_n']:>6} {r['jun_r']:>+8.3f} {r['jun_win']:>7.1f}%   {v}")
    out.append(r)
pd.DataFrame(out).to_csv("improve.csv", index=False)
print("\nsaved improve.csv")
