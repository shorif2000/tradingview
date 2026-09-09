"""
An 80% hit-rate / +0.20R target, tested on our data at a GBP 500 balance.

Replaces target80.py, target500.py and target_fix.py, which shared one trade
loop between them and differed only in what they printed.

    python3 backtester/target.py rules     their rules on our data
    python3 backtester/target.py flips     the trades their table leaves out
    python3 backtester/target.py cost      how much of a 0.5R target is spread
    python3 backtester/target.py fix       can holding through flips save it?
    python3 backtester/target.py money     what GBP 500 actually does
    python3 backtester/target.py all       every study

THE RULES AS STATED. Signal = range-filter flip. SL = 50% of the signal
candle's range beyond its extreme. TP1 = 0.5R. A same-bar SL+TP1 counts as a
stop. A trade that hits neither is "flip first", closed when the signal
reverses.

THE ARITHMETIC IS SOUND. At 0.5:1 the break-even hit rate is 1/(1+0.5) = 66.7%,
and 80.6% gives 0.806 x 0.5 - 0.194 x 1.0 = +0.209R, matching the quoted +0.21R
exactly. Nothing wrong with the sum. This is a high-hit-rate, small-reward
system, so everything rests on the hit rate staying above 66.7%.

THE GAP IN THE TABLE. Signals = TP1 + SL + flip-first (513 = 311 + 85 + 117),
but the hit rate is TP1/(TP1+SL) - it EXCLUDES the flips. On 1m that is 117 of
513 signals, 23% of them, whose profit and loss appears nowhere in the quoted
E[R]. If those flips average even -0.3R the true expectancy falls to

    (311 x 0.5 - 85 x 1.0 - 117 x 0.3) / 513 = +0.069R

The table does not say how flips settle, so this script measures them.
"""
from __future__ import annotations

import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from paths import dataset
from rf_lib import rf_signals

CAL = dict(fast=(38, 1.8), mode="fast")
GBP = 1.27          # 0.01 lots of XAUUSD = 1 ounce, so a $1 move = $1
DAYS = 21           # trading days in a month - the horizon every path is run to

# Trading days each sample actually covers, so trade counts scale to one month
# rather than assuming every sample is a month long. Jun-Aug is not.
SPAN_DAYS = {"1M Jan": 21, "2M Jan": 21, "3M Jan": 21, "5M Jan": 21,
             "5M Jun-Aug": 63}

# what the target table claims, and its own trade counts
THEIRS = {"1m": (78.5, 0.18, 311, 85, 117, 513),
          "2m": (80.6, 0.21, 708, 170, 238, 1117),
          "3m": (80.2, 0.20, 105, 26, 32, 163)}


def _resample(m1, rule):
    o = m1.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return o.dropna()


def load():
    """Five samples, including two periods of opposite market direction."""
    m1 = dataset("m1")
    return {"1M Jan": m1, "2M Jan": _resample(m1, "2min"),
            "3M Jan": _resample(m1, "3min"), "5M Jan": _resample(m1, "5min"),
            "5M Jun-Aug": dataset("m5_summer")}


# ── one trade loop ──────────────────────────────────────────────────────────

def run(d, *, sl_frac=0.5, tp_r=0.5, spread=0.20, exit_on_flip=True, max_bars=400):
    """Their rules, with the flip outcome measured rather than dropped."""
    sg = rf_signals(d, **CAL)
    o, h, l, c = (sg[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    L, S = sg.rf_long.to_numpy(bool), sg.rf_short.to_numpy(bool)
    n = len(sg)
    rows = []

    for i in range(1, n - 2):
        side = "long" if L[i] else ("short" if S[i] else None)
        if side is None:
            continue
        rng = h[i] - l[i]
        if rng <= 0:
            continue

        j = i + 1                                   # enter at the next open
        fill = o[j] + spread / 2 if side == "long" else o[j] - spread / 2
        stop = (l[i] - sl_frac * rng) if side == "long" else (h[i] + sl_frac * rng)
        risk = abs(fill - stop)
        if risk <= 0:
            continue
        tp = fill + tp_r * risk if side == "long" else fill - tp_r * risk

        why = None
        r = 0.0
        for m in range(j, min(j + max_bars, n)):
            # a same-bar SL+TP1 counts as a stop, as specified
            if (l[m] <= stop) if side == "long" else (h[m] >= stop):
                why, r = "SL", -1.0
                break
            if (h[m] >= tp) if side == "long" else (l[m] <= tp):
                why, r = "TP1", tp_r
                break
            flipped = (side == "long" and S[m]) or (side == "short" and L[m])
            if exit_on_flip and flipped and m > j:
                mv = c[m] - fill if side == "long" else fill - c[m]
                why, r = "flip", mv / risk
                break
        if why is None:
            m = min(j + max_bars - 1, n - 1)
            mv = c[m] - fill if side == "long" else fill - c[m]
            why, r = "time", mv / risk

        rows.append(dict(side=side, why=why, r=r, risk=risk))

    return pd.DataFrame(rows)


def boot(r, n=6000, seed=11):
    """Percentile bootstrap. Returns (lo, hi, P(mean <= 0))."""
    r = np.asarray(r, float)
    if len(r) < 5:
        return np.nan, np.nan, np.nan
    m = np.random.default_rng(seed).choice(r, (n, len(r))).mean(1)
    return np.percentile(m, 2.5), np.percentile(m, 97.5), (m <= 0).mean()


def hit_and_e(t):
    """Hit rate and E[R] on THEIR basis - flips excluded - plus E[R] on all."""
    tp = int((t.why == "TP1").sum())
    sl = int((t.why == "SL").sum())
    if tp + sl == 0:
        return np.nan, np.nan, t.r.mean(), tp, sl
    return tp / (tp + sl) * 100, (tp * 0.5 - sl) / (tp + sl), t.r.mean(), tp, sl


# ── studies ─────────────────────────────────────────────────────────────────

def study_rules(S, store):
    print("\nTheir rules on our data. 'their basis' excludes flips exactly as the")
    print("target table does; 'all signals' counts every trade that was taken.\n")
    print(f"{'sample':<12} {'signals':>8} {'TP1':>6} {'SL':>5} {'flip':>5} {'time':>5} "
          f"{'hit% their basis':>18} {'E[R] their basis':>17} {'E[R] all':>12} {'stop $':>8}")
    for nm, t in store.items():
        hit, e_their, e_all, tp, sl = hit_and_e(t)
        fl = int((t.why == "flip").sum())
        tm = int((t.why == "time").sum())
        print(f"{nm:<12} {len(t):>8} {tp:>6} {sl:>5} {fl:>5} {tm:>5} "
              f"{hit:>17.1f}% {e_their:>+16.3f}R {e_all:>+11.3f}R {t.risk.median():>7.2f}")

    print("\nAgainst the target, side by side:")
    print(f"{'':14}{'their target':>26}{'measured here':>26}")
    for lab, key in (("1m", "1M Jan"), ("2m", "2M Jan"), ("3m", "3M Jan")):
        thit, tE = THEIRS[lab][:2]
        hit, e_their, _, _, _ = hit_and_e(store[key])
        print(f"  {lab:<10} hit {thit:>5.1f}%  E {tE:+.2f}R   ->   hit {hit:>5.1f}%  E {e_their:+.3f}R")
    print("\nBreak-even at 0.5:1 is 66.7%. Below that the system loses however good")
    print("it looks.")


def study_flips(S, store):
    print("\nThe trades the target table leaves out. These carry real money and")
    print("appear nowhere in the quoted E[R].\n")
    print(f"{'':14}{'flips':>8}{'share of signals':>19}{'mean outcome':>15}{'% positive':>12}")
    for nm, t in store.items():
        f = t[t.why == "flip"]
        if not len(f):
            continue
        print(f"  {nm:<12} {len(f):>6} {len(f)/len(t)*100:>18.1f}% "
              f"{f.r.mean():>+14.3f}R {(f.r>0).mean()*100:>11.1f}%")

    print("\nApplying our measured flip outcome to THEIR counts:")
    print(f"{'':10}{'TP1':>7}{'SL':>6}{'flip':>6}{'their E[R]':>13}{'E[R] with flips counted':>26}")
    for lab, key in (("1m", "1M Jan"), ("2m", "2M Jan"), ("3m", "3M Jan")):
        _, _, tp, sl, fl, tot = THEIRS[lab]
        f = store[key]
        flip_r = f[f.why == "flip"].r.mean()
        e_their = (tp * 0.5 - sl) / (tp + sl)
        e_full = (tp * 0.5 - sl * 1.0 + fl * flip_r) / tot
        print(f"  {lab:<8} {tp:>7} {sl:>6} {fl:>6} {e_their:>+12.3f}R {e_full:>+25.3f}R")


def study_cost(S, store):
    print("\nA 0.5R target on a small stop is mostly spread. If the edge only")
    print("survives at zero cost, it is not an edge.\n")
    spreads = (0.0, 0.10, 0.20, 0.30)
    print(f"{'sample':<12} " + "".join(f"{'spread $'+format(s,'.2f'):>16}" for s in spreads))
    for nm, d in S.items():
        cells = []
        for sp in spreads:
            t = run(d, spread=sp)
            hit, _, _, _, _ = hit_and_e(t)
            cells.append(f"{hit:6.1f}% {t.r.mean():+.3f}R")
        print(f"{nm:<12} " + "".join(f"{c:>16}" for c in cells))


def _fix_line(S, lab, **kw):
    """One variant across every sample, pooled with a bootstrap on the end."""
    means, cells, pool = [], [], []
    for d in S.values():
        t = run(d, **kw)
        means.append(t.r.mean())
        pool.append(t.r.to_numpy())
        cells.append(f"{t.r.mean():+.3f} {(t.r>0).mean()*100:4.1f}% n{len(t):<4}")
    r = np.concatenate(pool)
    lo, hi, p = boot(r)
    print(f"  {lab:<34}" + "".join(f"{c:>22}" for c in cells) +
          f"  {r.mean():+.3f}R CI[{lo:+.2f},{hi:+.2f}] P{p*100:5.1f}%" +
          ("  ALL+" if all(m > 0 for m in means) else ""))


def study_fix(S, store):
    print("\nThe flip exit is what breaks it. Is it fixable? A 'flip first' trade")
    print("averages about -0.6R here and is positive ~1% of the time - that is two")
    print("thirds of a full stop, on roughly 15% of signals.\n")
    print("'ALL+' means positive in all five samples, including the two periods of")
    print("opposite market direction.\n")
    print(f"  {'variant':<34}" + "".join(f"{nm:>22}" for nm in S) + "  pooled")

    print("\n-- as specified: exit on flip --")
    for tp in (0.5, 0.75, 1.0):
        _fix_line(S, f"TP {tp}R, exit on flip", tp_r=tp, exit_on_flip=True)

    print("\n-- the fix: ignore the flip, let it resolve --")
    for tp in (0.5, 0.75, 1.0, 1.5, 2.0):
        _fix_line(S, f"TP {tp}R, HOLD through flip", tp_r=tp, exit_on_flip=False)

    print("\n-- wider stop, held through flips --")
    for slf in (1.0, 1.5):
        _fix_line(S, f"TP 0.5R, SL {slf} x candle, HOLD", tp_r=0.5, sl_frac=slf,
                  exit_on_flip=False)

    print("\nBreak-even hit rates: 0.5R needs 66.7%, 0.75R needs 57.1%, 1R needs 50%,")
    print("1.5R needs 40%, 2R needs 33.3%.")


def sim(r_pool, risk_pool, n_trades, start=500.0, paths=20000, seed=5, dead=60.0):
    """Bootstrap whole trades. A path freezes once it can no longer trade."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(r_pool), (paths, n_trades))
    eq = start + np.cumsum(r_pool[idx] * risk_pool[idx] / GBP, axis=1)
    below = eq <= dead
    first = np.where(below.any(1), below.argmax(1), n_trades)
    frozen = np.arange(n_trades)[None, :] >= first[:, None]
    stopval = np.where(
        first < n_trades,
        np.take_along_axis(eq, np.minimum(first, n_trades - 1)[:, None], 1).ravel(), 0.0)
    eq = np.where(frozen, np.maximum(stopval, 0)[:, None], eq)
    full = np.concatenate([np.full((paths, 1), start), eq], 1)
    peak = np.maximum.accumulate(full, 1)
    return eq[:, -1], ((peak - full) / peak).max(1), (first < n_trades).mean()


def study_money(S, store):
    print("\nGBP 500 at 0.01 lots.\n")
    for nm, t in store.items():
        med = t.risk.median()
        print(f"  {nm:<12} median stop ${med:5.2f} = GBP {med/GBP:5.2f} = "
              f"{med/GBP/500*100:4.2f}% of GBP 500 per trade")
    print("\n  Sizing is not the constraint at GBP 500 - every one of these is well")
    print("  under 2%. The constraint is whether the expectancy is real.")

    print("\n20,000 bootstrapped paths over one month. Trade counts are what the")
    print("signal actually produced, not an assumption.\n")
    print(f"{'':26}{'trades/mo':>11}{'median':>10}{'10th pct':>10}{'90th pct':>10}"
          f"{'med DD':>9}{'P(dead)':>9}")
    for nm, t in store.items():
        span = SPAN_DAYS.get(nm, DAYS)
        for lab, sub in ((f"{nm} ALL signals", t),
                         (f"{nm} flips excluded", t[t.why != "flip"])):
            n = max(1, round(len(sub) / span * DAYS))
            fin, dd, dead = sim(sub.r.to_numpy(), sub.risk.to_numpy(), n)
            print(f"  {lab:<26}{n:>11}{np.median(fin):>9.0f}"
                  f"{np.percentile(fin,10):>10.0f}{np.percentile(fin,90):>10.0f}"
                  f"{np.median(dd)*100:>8.0f}%{dead*100:>8.0f}%")


STUDIES = {"rules": study_rules, "flips": study_flips, "cost": study_cost,
           "fix": study_fix, "money": study_money}

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "rules"
    names = list(STUDIES) if which == "all" else [which]
    if any(nm not in STUDIES for nm in names):
        print(f"unknown study. choose from: {', '.join(STUDIES)}, all")
        raise SystemExit(1)

    S = load()
    store = {nm: run(d) for nm, d in S.items()}
    for nm in names:
        print("=" * 118)
        print(nm.upper())
        print("=" * 118)
        STUDIES[nm](S, store)
