# Can the buy/sell signal be made profitable?

**No — not by filtering it.** Thirty-one configurations later, the honest answer
is that the "improvements" that survive testing are fewer than pure chance would
produce. There is one change worth making anyway, but for a different reason
than profit: it removes 41% of the signals without making the survivors worse.

## Diagnosis first, not guesswork

The last round of this failed by guessing at filters. This time I asked the data
which conditions separate winners from losers, using only features knowable **at
the signal bar** — anything measured afterwards would be look-ahead and would
flatter every filter built on it.

Two features pointed the same way in both periods:

| feature | better half | why it makes sense |
|---|---|---|
| `stretch` = \|close − EMA21\| / ATR | **low** | the filter is a lagging step-follower, so it fires *after* a move has travelled — the false signals are the ones where price has already run |
| `ADX(14)` | **high** | no trend to follow means nothing for a trend-follower to catch |

Both say the same thing: **you are being asked to buy the top of a spike.**

## Acting on it

Two ways to use that. Filter the extended entries out, or don't chase — leave a
limit order back at the EMA21 and only trade if price comes to you.

| change | Jan | Jun–Aug | verdict |
|---|---|---|---|
| baseline, market entry, 2R | −0.067 | +0.053 | |
| stretch ≤ 0.75 | −0.069 | +0.166 | flips |
| stretch ≤ 0.50 | −0.075 | +0.199 | flips |
| **ADX ≥ 20** | **+0.006** | **+0.060** | both positive |
| **ADX ≥ 20, 3R target** | **+0.052** | **+0.054** | both positive |
| **fade the 1H filter direction** | **+0.048** | **+0.041** | both positive |
| pullback to EMA21 | −0.245 | −0.047 | worse than chasing |
| pullback + ADX ≥ 20 | −0.287 | −0.182 | much worse |
| HTF agree (trend gate) | −0.129 | +0.034 | flips |

**The pullback idea backfired badly**, and the reason is worth keeping: a resting
limit order only fills when price comes back to it, so on a trend-follower you
are selected into exactly the signals that immediately reversed. Waiting for a
better price gets you a worse trade.

Note also that the stretch filter, which the diagnosis liked, does not survive as
an actual rule. The median-split diagnosis and the trade-level test disagree —
so the diagnosis was suggestive, not decisive, and the trade-level test wins.

## Why none of this counts as an improvement

| config | trades | expectancy | 95% CI | P(no edge) |
|---|---|---|---|---|
| baseline (no filter) | 1,144 | −0.031R | [−0.113, +0.051] | 77.8% |
| **ADX ≥ 20 + 3R** | 670 | **+0.053R** | [−0.075, +0.184] | **22.2%** |
| ADX ≥ 20 + 2R | 725 | +0.023R | [−0.079, +0.127] | 33.5% |
| fade 1H filter | 1,000 | +0.018R | [−0.068, +0.107] | 34.6% |

Every interval contains zero.

And the number that matters most: **a genuinely zero-edge configuration has a 25%
chance of landing positive in both periods**, just from sampling noise at these
sample sizes. Across the 31 configurations tested here, chance alone predicts
about **7.7 false winners.**

**I found 3.**

That is fewer than noise would produce. There is nothing here to build on.

## The one change still worth making

**ADX ≥ 20.** Not because it is proven profitable — it is not — but because it
cuts the signal count from 1,144 to 670 trades, **41% fewer signals**, while
nudging expectancy from −0.031R to +0.053R. You pay a spread on every trade, so
removing 41% of them at no measured cost is worth having even if the expectancy
gain is noise.

That also speaks directly to "a lot of the time the signal is false": the ones it
removes are the low-trend-strength ones, which is where a trend-follower has no
business firing.

Implemented in the indicator as **Minimum ADX** in the Range filter group, default
20. Set it to 0 for the reference unfiltered behaviour.

At 0.01 lots the filtered version earned **+£0.18/day, +£0.89/week** across 58
trading days. That is not a living, and it is not statistically distinguishable
from zero.

## What actually works, for perspective

| system | trades | expectancy | P(no edge) |
|---|---|---|---|
| range filter, best variant found | 670 | +0.053R | 22.2% |
| **mean-reversion engine** | **213** | **+0.263R** | **0.3%** |

Five times the expectancy, a fifth of the trades, and a P-value three orders of
magnitude better. `Signal engine = Mean reversion` in the indicator.

## Caveats

- The 31 configurations were selected using both periods, so even the
  best-looking numbers are post-selection and optimistic. There is no held-out
  third period.
- Two periods, eleven weeks in total. A longer MT5 export would settle far more
  than another round of filters would.
- ADX ≥ 20 was chosen partly because it was the least-bad of several thresholds
  tested (15, 18, 20, 22). That is itself a fitted choice.
