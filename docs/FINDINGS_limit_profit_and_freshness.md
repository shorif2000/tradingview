# Profit rate on the limit orders, and when a level has gone stale

Two questions, both measured on TradingView's own chart data across five
timeframes (`tools/tv_console_backtest.js`). One has a clean answer. The other
has an honest answer, which is not the same thing.

---

## 1. Profit rate by chart timeframe

Same rules throughout — the only thing changing is the chart the levels come
from. Target is a timeframe 12× the chart (the 5M → 1H ratio, held constant).

| Chart | n | Expectancy | Win | Median stop | £/trade @ 0.01 | **Stop as % of £400** |
|---|---|---|---|---|---|---|
| **5M** | 58 | **+0.302R** | 29% | $5.48 | **£1.30** | **1.1%** ✅ |
| **15M** | 64 | +0.084R | 27% | $10.77 | £0.71 | 2.1% ⚠️ |
| 45M | 55 | **−0.063R** | 24% | $22.20 | **−£1.10** | 4.4% ❌ |
| 1H | 100 | +0.120R | 28% | $20.10 | £1.89 | 4.0% ❌ |
| 4H | 64 | +0.112R | 27% | $16.24 | £1.44 | 3.2% ❌ |

**The right-hand column is the one that decides this, not the expectancy.**

You noticed orders appearing on 15M, 45M, 1H and 4H. They are real setups, but
at £400 and 0.01 lots the higher timeframes are **not tradeable** — a single
stop is 3% to 4.4% of your account, and 0.01 is the minimum lot so you cannot
size down to fix it. One 1H trade risks what four 5M trades risk.

**45M is worse than untradeable — it is the only negative row in the table.**

So: **trade the 5M orders. 15M occasionally. Ignore 45M, 1H and 4H** until the
account is large enough that a $20 stop is 1% of it — around £1,600.

Every CI here crosses zero (n = 55–100 over 19 to 946 days), so read this as a
ranking, not as five separate verdicts.

---

## 2. "Has this area already been used?"

Your example: **a sell limit at 4425, but price reacted from 4423 and has
already gone down.** The move the order was waiting for happened without you.
What fills it now is the retrace.

That is a real and distinct failure mode, and it is not what the existing
freshness rule catches. The script already refuses any level price has *traded
through*. It said nothing about a level price came close to and turned away
from — which leaves the order live and the reason for it already spent.

### Measured

Defined as: price came within **0.5 × ATR** of the entry without filling it, and
then travelled **1.0 × ATR** in the direction the trade wanted to go.

| Chart | Fresh | Already reacted | Fresh better? |
|---|---|---|---|
| 5M | +0.374R | +0.254R | ✅ |
| 15M | +0.129R | +0.055R | ✅ |
| 45M | +0.065R | **−0.228R** | ✅ |
| 1H | +0.084R | +0.154R | ❌ |
| 4H | +0.185R | +0.052R | ✅ |

**Four of five timeframes agree with you.** On 45M it is the whole difference
between a losing setup and a marginal one.

**But pooled, the gap does not clear the bar:**

```
FRESH            n=157   +0.148R   CI [−0.17, +0.46]
ALREADY REACTED  n=184   +0.083R   CI [−0.18, +0.39]

gap              +0.065R  CI [−0.35, +0.48]
P(gap is zero or negative) = 37.9%
```

Between a third and a half of these setups get flagged, so this is not a rare
edge case — but a 38% chance the effect is zero or backwards is not evidence to
delete trades on. Four-of-five is suggestive; by a sign test that is p ≈ 0.19.

### So the indicator marks them, it does not hide them

Live levels that meet the near-miss test now show **⚠ STALE** on the chart label
and a **⚠** in the pending-order table, greyed out. They stay in the list.
There is a *Hide near-miss levels entirely* switch, **off by default**, because
the evidence says these are probably worse, not certainly worse.

Acting on a hunch is how this project produced a fake +0.972R. Showing you the
hunch, labelled as one, is not.

---

## The three checks before you place any of these

1. **Untouched?** The script enforces this — a level price has traded through is
   deleted, not greyed.
2. **Not already reacted from?** Look for **⚠ STALE**. If the move you wanted
   already happened without you, the order is a retrace entry, not the setup.
3. **Stop small enough?** Set your account size in the settings and read the
   **% ACCT** column. It turns red past 2%. On £400 that means 5M orders pass
   and almost nothing above 15M does.

Check 3 rejects more orders than checks 1 and 2 combined, and it is the one with
no uncertainty attached to it.
