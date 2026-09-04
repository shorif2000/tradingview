"""
Range Filter — the mechanism behind the signals — plus a trade
simulator honest enough to say whether those signals are worth anything.

The filter is reimplemented from the public algorithm and matched to the
starting parameters: source close, fast 27/1.6,
slow 55/2.

Everything here is deliberately built the same way as the existing engine:
Pine-exact seeded EMAs, entry on the NEXT bar (you cannot fill on the close that
produced the signal), spread charged on both sides, and intrabar stop-vs-target
order resolved from M1 where it exists. A 2R system's result is decided almost
entirely by which of the two got touched first, so guessing that is the fastest
way to produce a number that means nothing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from xau_engine import ema, atr as atr_fn


# ── the filter ───────────────────────────────────────────────────────────────

def smooth_range(x: pd.Series, per: int, mult: float) -> pd.Series:
    """EMA of bar-to-bar movement, smoothed again over twice the window.

    The second smoothing is the point: it stops one wide bar from moving the
    filter, which is what keeps the signals sparse.
    """
    avrng = ema((x - x.shift(1)).abs(), per)
    return ema(avrng, per * 2 - 1) * mult


def range_filter(x: pd.Series, r: pd.Series) -> np.ndarray:
    """A step-follower that only ever moves toward price, never back.

    It sits still while price stays inside the range, so it does not whipsaw the
    way a moving average does.
    """
    xv, rv = x.to_numpy(float), r.to_numpy(float)
    out = np.empty(len(xv))
    prev = xv[0]
    for i in range(len(xv)):
        xi, ri = xv[i], rv[i]
        if np.isnan(ri):
            cur = prev
        elif xi > prev:
            cur = prev if xi - ri < prev else xi - ri
        else:
            cur = prev if xi + ri > prev else xi + ri
        out[i] = cur
        prev = cur
    return out


def rf_state(src: pd.Series, per: int, mult: float) -> pd.DataFrame:
    """Filter, band, and the consecutive-direction counters."""
    rng = smooth_range(src, per, mult)
    filt = range_filter(src, rng)
    f = pd.Series(filt, index=src.index)
    d = f.diff()

    up = np.zeros(len(f))
    dn = np.zeros(len(f))
    dv = d.to_numpy(float)
    for i in range(1, len(f)):
        up[i] = up[i - 1] + 1 if dv[i] > 0 else (0 if dv[i] < 0 else up[i - 1])
        dn[i] = dn[i - 1] + 1 if dv[i] < 0 else (0 if dv[i] > 0 else dn[i - 1])

    return pd.DataFrame({"filt": f, "rng": rng, "up": up, "dn": dn}, index=src.index)


def rf_signals(df: pd.DataFrame, fast=(27, 1.6), slow=(55, 2.0), mode="both",
               require_band=False, src_col="close") -> pd.DataFrame:
    """Long/short flags with the alternation the reference clearly enforces.

    `ini` remembers which side fired last and only releases a long when the
    previous state was short. That single variable is why eight consecutive
    signals on the reference data alternate perfectly.
    """
    src = df[src_col]
    F = rf_state(src, fast[0], fast[1])
    S = rf_state(src, slow[0], slow[1])

    if require_band:
        fL = (src > F.filt + F.rng) & (F.up > 0)
        fS = (src < F.filt - F.rng) & (F.dn > 0)
        sL = (src > S.filt + S.rng) & (S.up > 0)
        sS = (src < S.filt - S.rng) & (S.dn > 0)
    else:
        fL, fS = (src > F.filt) & (F.up > 0), (src < F.filt) & (F.dn > 0)
        sL, sS = (src > S.filt) & (S.up > 0), (src < S.filt) & (S.dn > 0)

    if mode == "fast":
        rawL, rawS = fL, fS
    elif mode == "slow":
        rawL, rawS = sL, sS
    else:                                   # both must agree
        rawL, rawS = fL & sL, fS & sS

    lv, sv = rawL.to_numpy(bool), rawS.to_numpy(bool)
    longSig = np.zeros(len(df), bool)
    shortSig = np.zeros(len(df), bool)
    ini = 0
    for i in range(len(df)):
        if lv[i] and ini == -1:
            longSig[i] = True
        if sv[i] and ini == 1:
            shortSig[i] = True
        if lv[i]:
            ini = 1
        elif sv[i]:
            ini = -1

    out = df.copy()
    out["rf_long"] = longSig
    out["rf_short"] = shortSig
    out["f_filt"], out["f_rng"] = F.filt, F.rng
    out["s_filt"], out["s_rng"] = S.filt, S.rng
    return out


# ── evaluation ───────────────────────────────────────────────────────────────

def _m1_slices(m1: pd.DataFrame | None):
    if m1 is None:
        return None, None
    return m1.index.to_numpy(), m1[["high", "low"]].to_numpy(float)


def _resolve(m1_idx, m1_hl, t0, t1, side, sl, tp):
    """Which of stop and target was touched first, from M1 bars.

    Returns 'sl', 'tp' or None. When both are inside the same M1 bar the stop
    wins — the pessimistic reading, because assuming otherwise is how a
    backtest quietly invents an edge it does not have.
    """
    if m1_idx is None:
        return None
    a = np.searchsorted(m1_idx, t0, "left")
    b = np.searchsorted(m1_idx, t1, "right")
    if b <= a:
        return None
    for h, l in m1_hl[a:b]:
        if side == "long":
            hit_sl, hit_tp = l <= sl, h >= tp
        else:
            hit_sl, hit_tp = h >= sl, l <= tp
        if hit_sl:
            return "sl"
        if hit_tp:
            return "tp"
    return None


def simulate(df: pd.DataFrame, m1: pd.DataFrame | None = None, *,
             spread=0.20, atr_len=14, sl_mult=1.2, rr=2.0,
             max_bars=60, invert=False, session=None,
             lots=0.02, gbpusd=1.27, start_bal=100.0) -> pd.DataFrame:
    """Fixed-risk trade sim: enter next bar's open, stop at sl_mult x ATR, target rr x risk.

    Entry on the NEXT bar is not a detail. The signal is only known at the close
    of its bar, and on a manually-traded mobile platform even that is optimistic.
    """
    d = df
    a = atr_fn(d.high, d.low, d.close, atr_len)
    m1_idx, m1_hl = _m1_slices(m1)

    idx = d.index.to_numpy()
    o, h, l, c = (d[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    L = d["rf_long"].to_numpy(bool)
    S = d["rf_short"].to_numpy(bool)
    av = a.to_numpy(float)

    if session is not None:
        lon = d.index.tz_convert("Europe/London").hour
        ok_sess = (lon >= session[0]) & (lon < session[1])
    else:
        ok_sess = np.ones(len(d), bool)

    rows = []
    i = 0
    n = len(d)
    while i < n - 2:
        sig_long, sig_short = L[i], S[i]
        if invert:
            sig_long, sig_short = sig_short, sig_long
        if (not sig_long and not sig_short) or not ok_sess[i] or np.isnan(av[i]):
            i += 1
            continue

        side = "long" if sig_long else "short"
        j = i + 1                                    # fill on the next bar's open
        risk = sl_mult * av[i]
        if risk <= 0:
            i += 1
            continue

        if side == "long":
            entry = o[j] + spread / 2.0
            sl, tp = entry - risk, entry + rr * risk
        else:
            entry = o[j] - spread / 2.0
            sl, tp = entry + risk, entry - rr * risk

        out_k, outcome, exit_px = None, None, None
        for k in range(j, min(j + max_bars, n)):
            r = _resolve(m1_idx, m1_hl, idx[k], idx[k], side, sl, tp)
            if r is None:                            # no M1: same pessimism, bar-level
                if side == "long":
                    hit_sl, hit_tp = l[k] <= sl, h[k] >= tp
                else:
                    hit_sl, hit_tp = h[k] >= sl, l[k] <= tp
                r = "sl" if hit_sl else ("tp" if hit_tp else None)
            if r is not None:
                out_k, outcome = k, r
                exit_px = sl if r == "sl" else tp
                break
        if out_k is None:                            # time stop
            out_k = min(j + max_bars - 1, n - 1)
            outcome = "time"
            exit_px = c[out_k]

        move = (exit_px - entry) if side == "long" else (entry - exit_px)
        r_mult = move / risk
        pnl_usd = move * lots * 100.0 - spread * lots * 100.0
        rows.append(dict(time=idx[i], side=side, entry=entry, sl=sl, tp=tp,
                         exit=exit_px, outcome=outcome, r=r_mult,
                         pnl_gbp=pnl_usd / gbpusd, bars=out_k - j,
                         risk=risk))
        i = out_k + 1                                # one position at a time
    tr = pd.DataFrame(rows)
    if len(tr):
        tr["equity"] = start_bal + tr.pnl_gbp.cumsum()
    return tr


def summarise(tr: pd.DataFrame, label: str) -> dict:
    if tr is None or len(tr) == 0:
        return dict(label=label, n=0, win=np.nan, exp_r=np.nan, net=np.nan, dd=np.nan)
    wins = (tr.r > 0).mean() * 100
    eq = tr.equity.to_numpy()
    peak = np.maximum.accumulate(np.concatenate([[100.0], eq]))
    dd = float(np.max((peak - np.concatenate([[100.0], eq])) / peak) * 100)
    return dict(label=label, n=len(tr), win=wins, exp_r=tr.r.mean(),
                net=tr.pnl_gbp.sum(), dd=dd,
                longs=int((tr.side == "long").sum()),
                long_win=float((tr[tr.side == "long"].r > 0).mean() * 100) if (tr.side == "long").any() else np.nan,
                short_win=float((tr[tr.side == "short"].r > 0).mean() * 100) if (tr.side == "short").any() else np.nan)


def direction_accuracy(df: pd.DataFrame, horizons=(10, 20, 40)) -> dict:
    """Did price simply go the right way, ignoring exits entirely?

    Separating this from the trade sim matters: a signal can be directionally
    right and still lose money to geometry, and the fix for each is different.
    """
    c = df.close.to_numpy(float)
    res = {}
    for hz in horizons:
        ok = tot = 0
        for arr, sign in ((df.rf_long.to_numpy(bool), 1), (df.rf_short.to_numpy(bool), -1)):
            for i in np.flatnonzero(arr):
                if i + hz < len(c):
                    tot += 1
                    if sign * (c[i + hz] - c[i]) > 0:
                        ok += 1
        res[hz] = (100.0 * ok / tot if tot else np.nan, tot)
    return res
