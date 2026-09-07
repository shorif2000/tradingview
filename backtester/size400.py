"""
£400 at 0.01 lots: is it survivable, and what does it actually make?

Two things have to be answered separately and are constantly confused:

  RISK    what one loss costs as a share of the account
  MARGIN  what one open position TIES UP, which has nothing to do with risk and
          is what actually stops you opening the trade

At £100 the first one killed it. At £400 the first one is fine and the second
one becomes the question, because a 0.01 lot of gold is one ounce of a $4,400
instrument and the margin depends entirely on which entity the account sits
under. That is not a detail - under FCA leverage caps it consumes almost half
the account per position.

Everything is bootstrapped from the 123 measured trades of the shipped
configuration (5M levels, 1H target, structural stop, anticipation entry), which
spans two periods of opposite market direction. Resampling those trades assumes
the future looks like that sample, which is the strongest claim available and
still not a strong one - so the spread of outcomes matters far more than the
median, and the median is not the number to plan around.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

T = pd.read_csv("anticipate_trades.csv")
R = T.r.to_numpy(float)
RISK = T.risk.to_numpy(float)          # dollars per ounce, i.e. per 0.01 lot
GBP = 1.27
GOLD = 4425.0                          # spot, from the live chart

N_TRADES_PER_DAY = 1.4
DAYS_PER_MONTH = 21

print("=" * 76)
print("The trade distribution being resampled")
print("=" * 76)
print(f"  {len(R)} trades   expectancy {R.mean():+.3f}R   win {(R>0).mean()*100:.1f}%")
print(f"  median stop ${np.median(RISK):.2f}   mean ${RISK.mean():.2f}   "
      f"90th pct ${np.percentile(RISK,90):.2f}")
print(f"  worst single trade {R.min():+.2f}R   best {R.max():+.2f}R")

print("\n" + "=" * 76)
print("1. RISK PER TRADE  —  what one loss costs")
print("=" * 76)
print(f"{'balance':>9}  {'0.01 lot':>22}  {'0.02 lot':>22}")
for bal in (100, 280, 400, 600, 1000):
    row = f"{'£'+str(bal):>9}"
    for lots in (0.01, 0.02):
        oz = lots * 100
        med = np.median(RISK) * oz / GBP
        p90 = np.percentile(RISK, 90) * oz / GBP
        row += f"   £{med:5.2f} = {med/bal*100:4.1f}%  (p90 {p90/bal*100:4.1f}%)"
    print(row)
print("\n  The 2% rule is about the MEDIAN stop; the 90th percentile is what")
print("  actually turns up on a bad day, so both are shown.")

print("\n" + "=" * 76)
print("2. MARGIN  —  what one open position ties up")
print("=" * 76)
print("  A 0.01 lot of XAUUSD is 1 ounce. Notional = the gold price.")
print(f"  Gold at ${GOLD:,.0f}, so notional per 0.01 lot = ${GOLD:,.0f} "
      f"= £{GOLD/GBP:,.0f}\n")
print(f"  {'leverage':>10}  {'margin / 0.01 lot':>18}  {'% of £400':>10}  {'max lots on £400':>17}")
for lev, note in ((20, "FCA / UK entity — gold is capped at 20:1"),
                  (100, "common offshore default"),
                  (200, ""),
                  (500, "Vantage offshore maximum")):
    m = GOLD / lev / GBP
    maxlots = 400 / m * 0.01
    print(f"  {str(lev)+':1':>10}  {'£'+format(m, ',.0f'):>18}  {m/400*100:9.0f}%  "
          f"{maxlots:16.2f}   {note}")
print("\n  This is the constraint people miss. Under FCA rules a single 0.01 lot")
print("  position consumes over 40% of a £400 account in margin, and two open")
print("  at once is a margin call waiting for a wick — regardless of how")
print("  sensible the risk per trade looks.")


def simulate(balance, lots, n_trades, n_paths=20000, seed=7, ruin_at=0.30,
             shift=0.0, hier=True):
    """Resample whole trades, propagating uncertainty in the EDGE itself.

    A flat bootstrap of the 123 trades answers "what if the measured edge is
    exactly right and permanent?", which is not a question worth asking - it
    treats a sample estimate as a physical constant and produces projections
    that only ever go up. The measured expectancy was +0.523R with a 95%
    interval of [+0.13, +0.93]; a projection that ignores that width is
    fiction.

    So each path first draws its own WORLD - a bootstrap resample of the trade
    set, which is one plausible version of what the real distribution might be
    - and then trades inside it. Estimation error compounds through the path
    instead of averaging away across paths, which is what actually happens to
    someone trading one account once.

    `shift` moves expectancy in R to test a specific assumption, e.g. the
    lower confidence bound, or zero.
    """
    rng = np.random.default_rng(seed)
    oz = lots * 100
    if hier:
        world = rng.integers(0, len(R), (n_paths, len(R)))     # one world per path
        pick = rng.integers(0, len(R), (n_paths, n_trades))
        take = np.take_along_axis(world, pick % len(R), axis=1)
    else:
        take = rng.integers(0, len(R), (n_paths, n_trades))
    r = R[take] + shift
    pnl = r * RISK[take] * oz / GBP
    eq = balance + np.cumsum(pnl, axis=1)

    # Invariant I15: an account cannot go negative and cannot keep trading once
    # it is too small to place the minimum lot. Without this the simulation
    # happily reports a -£864 balance, which is not an outcome anyone can have
    # - the broker closes you first. Below `dead` the path freezes: no further
    # trades, and the balance stays where it stopped.
    dead = 60.0
    below = eq <= dead
    first = np.where(below.any(axis=1), below.argmax(axis=1), n_trades)
    cols = np.arange(n_trades)[None, :]
    frozen = cols >= first[:, None]
    stop_val = np.where(first < n_trades,
                        np.take_along_axis(eq, np.minimum(first, n_trades - 1)[:, None], 1).ravel(),
                        0.0)
    eq = np.where(frozen, np.maximum(stop_val, 0.0)[:, None], eq)

    full = np.concatenate([np.full((n_paths, 1), balance), eq], axis=1)
    peak = np.maximum.accumulate(full, axis=1)
    dd = (peak - full) / peak
    return dict(final=eq[:, -1], maxdd=dd.max(axis=1),
                ruined=(eq.min(axis=1) <= balance * ruin_at).mean(),
                dead=(first < n_trades).mean(),
                below_start=(eq[:, -1] < balance).mean())


print("\n" + "=" * 76)
print("3. WHAT £400 DOES  —  20,000 paths, uncertainty in the edge included")
print("=" * 76)
print("  Three assumptions, because which one is true is genuinely unknown:")
print("    AS MEASURED   +0.523R, the point estimate")
print("    CONSERVATIVE  +0.13R, the bottom of the 95% confidence interval")
print("    NO EDGE       0.00R, the honest null — costs still get paid")

for lots in (0.01, 0.02):
    print(f"\n  ══ {lots} lots ══════════════════════════════════════════════════")
    for lab_s, sh in (("as measured", 0.0), ("conservative", 0.13 - R.mean()),
                      ("no edge", -R.mean())):
        print(f"\n   {lab_s.upper()}")
        print(f"   {'horizon':>9} {'median':>9} {'10th pct':>9} {'90th pct':>9} "
              f"{'med DD':>8} {'P(lose)':>8} {'P(-30%)':>8} {'P(dead)':>8}")
        for months, lab in ((3, "3 months"), (6, "6 months"), (12, "1 year")):
            n = int(N_TRADES_PER_DAY * DAYS_PER_MONTH * months)
            s = simulate(400, lots, n, shift=sh)
            print(f"   {lab:>9} £{np.median(s['final']):8.0f} "
                  f"£{np.percentile(s['final'],10):8.0f} £{np.percentile(s['final'],90):8.0f} "
                  f"{np.median(s['maxdd'])*100:7.0f}% {s['below_start']*100:7.0f}% "
                  f"{s['ruined']*100:7.0f}% {s['dead']*100:7.0f}%")

print("\n  'med DD' is the MEDIAN worst drawdown across paths — the typical bad")
print("  patch, not the bad case. 'P(-30%)' is the chance of being 30% down at")
print("  some point, which is where most people quit regardless of the maths.")

print("\n" + "=" * 76)
print("4. THE LOSING STREAK YOU HAVE TO SIT THROUGH")
print("=" * 76)
w = (R > 0).mean()
print(f"  Win rate {w*100:.1f}%, so a loss is the normal outcome of any one trade.")
rng = np.random.default_rng(11)
seq = R[rng.integers(0, len(R), (20000, 300))] > 0
streak = np.zeros(len(seq), int)
for i in range(len(seq)):
    c = m = 0
    for v in seq[i]:
        c = 0 if v else c + 1
        m = max(m, c)
    streak[i] = m
print(f"  Over 300 trades (about 7 months), the longest run of losses:")
print(f"    median {np.median(streak):.0f}   90th pct {np.percentile(streak,90):.0f}   "
      f"worst seen {streak.max()}")
loss = np.median(RISK) / GBP
print(f"  At 0.01 lots that is a median streak costing £{np.median(streak)*loss:.0f}, "
      f"and a 90th-percentile streak costing £{np.percentile(streak,90)*loss:.0f}.")
