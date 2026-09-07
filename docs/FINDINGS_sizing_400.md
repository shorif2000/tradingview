# £400 at 500:1

**Short answer: still 0.01 lots, one or two positions at a time.** 500:1 removes
the margin ceiling completely — and that is the problem, not the solution. The
brake is gone; the discipline now has to come from you.

Everything below is measured on TradingView's own chart data
(`tools/tv_console_backtest.js`) except the resampled projections, which use the
123 trades of the shipped configuration across two periods.

---

## 1. Margin is now a non-issue

A 0.01 lot of XAUUSD is one ounce, so the notional is the whole gold price:
$4,425 ≈ £3,484. At 500:1 that needs **£7 of margin** — 2% of a £400 account.
Three positions open at once uses £21, about 5%.

| Leverage | Margin / 0.01 lot | % of £400 | Max lots £400 allows |
|---|---|---|---|
| 20:1 (FCA) | £174 | 44% | 0.02 |
| **500:1 (yours)** | **£7** | **2%** | **0.57** |

**That last cell is the danger.** 500:1 permits a 0.57 lot position on £400. At
the median $5.22 stop that is a **£234 loss on one trade — 58% of the account**,
and nothing in the platform will stop you. Under FCA leverage the margin
requirement quietly enforces sane sizing. At 500:1 nothing does.

So the sizing question is now answered purely by risk, and the answer is
unchanged: **0.01 lots = £4.11 = 1.0% per trade** (2.0% at the 90th percentile).

---

## 2. What 500:1 genuinely unlocks: multiple positions at once

This is the real change. Under FCA margin you could hold one position. Now the
pending-order table can show four resting orders and you can place all four.
Should you?

Measured, taking every qualifying setup in order and capping how many can be
open simultaneously. 0.01 lots each, £400 start:

### 5M levels → 1H target (19 trading days)

| Max open | Taken | Expectancy | Final | Max DD | Overlaps same direction |
|---|---|---|---|---|---|
| **1** | 69 | **+0.240R** | **£408** | **11.1%** | — |
| 2 | 86 | +0.127R | £383 | 15.8% | 76% |
| 3 | 87 | +0.114R | £379 | 16.7% | 68% |
| unlimited | 90 | +0.127R | £384 | 16.7% | 62% |

### 15M levels → 1H target (66.8 trading days)

| Max open | Taken | Expectancy | Final | Max DD | Overlaps same direction |
|---|---|---|---|---|---|
| 1 | 99 | +0.058R | £390 | 24.4% | — |
| 2 | 119 | +0.134R | £472 | 31.3% | 60% |
| **3** | 125 | **+0.174R** | **£496** | 32.9% | 56% |
| unlimited | 126 | +0.164R | £492 | 32.9% | 51% |

**The two timeframes disagree about whether concurrency helps.** On 5M it makes
things clearly worse; on 15M clearly better. When two samples of the same idea
point in opposite directions, the honest reading is that the return effect is
noise, not signal — exactly the trap this project has fallen into before.

**But they agree completely on the cost.** Drawdown rises in both: 11.1% → 16.7%
on 5M, 24.4% → 32.9% on 15M. That part is consistent, and consistent is what
gets believed.

### Why concurrent positions are not diversification

**56% to 76% of overlapping positions are the same direction.** They are not
independent bets. They are one directional view expressed two or three times,
which is why the drawdown grows roughly in proportion to the position count
while the return does not.

Three positions at "1% risk each" is not 3% spread over three independent
outcomes. It is closer to a single 2–3% bet on gold going one way, and it will
lose all three together.

**So: cap at 2 open positions, and treat your risk budget as total open risk
rather than per-trade risk.** If two are already live, the third order comes off
the table regardless of how good it looks.

---

## 3. What the account does over a year

20,000 paths, propagating uncertainty in the *edge itself* — each path draws its
own plausible version of the true distribution and trades inside it. A
simulation that treats +0.523R as a known constant only ever goes up, and is
fiction. The measured 95% interval was **[+0.13, +0.93]**, so all three of these
remain consistent with what has been observed.

### 0.01 lots

| Assumption | 1-yr median | 10th pct | Median worst DD | P(down 30%) | P(account dead) |
|---|---|---|---|---|---|
| As measured (+0.523R) | £1,049 | £603 | 12% | 0% | 0% |
| **Conservative (+0.13R)** | **£425** | £57 | 38% | 24% | **18%** |
| No edge (0.00R) | £218 | £54 | 65% | 45% | 38% |

### 0.02 lots

| Assumption | 1-yr median | 10th pct | Median worst DD | P(down 30%) | P(account dead) |
|---|---|---|---|---|---|
| As measured | £1,698 | £806 | 19% | 2% | 1% |
| Conservative | £428 | £49 | 66% | 44% | **39%** |
| No edge | £58 | £45 | 87% | 65% | **60%** |

Plan around the conservative row. At 0.01 lots the realistic bad case is a flat
year with a 38% drawdown and roughly a 1-in-5 chance of the account ending. At
0.02 the same assumption gives a **39% chance of being wiped out** — double the
upside, roughly triple the chance of not being there to collect it.

**0.02 is not justified by anything measured.** Revisit at £800.

---

## 4. The losing streak, which is what actually ends accounts

Win rate **35.8%** — losing is the normal outcome of any single trade. Over 300
trades (about seven months), the longest run of consecutive losses:

- median **11 in a row**
- 90th percentile **15 in a row**
- worst simulated **36**

At 0.01 lots that is roughly **£45–£62** with no winners in between: 11–16% of a
£400 account. It is expected, not a malfunction. If eleven straight losses would
make you double the size or abandon the rules, the projections above never get a
chance to happen.

---

## The rules £400 at 500:1 comes down to

1. **0.01 lots.** Not 0.02. The platform will offer you 0.57 — ignore it.
2. **Two open positions maximum**, because overlapping trades are mostly the
   same bet and their drawdowns add.
3. **Do not move the stop to break-even** — measured, that took expectancy from
   +0.291R to +0.175R.
4. **Expect eleven losses in a row** at some point and change nothing when it
   happens.
5. **Trade one month at 0.01 first** and compare live results with the backtest
   before believing any one-year figure.

Both test periods are 2026, and P(no edge) was 0.3% — the strongest evidence in
this project, and still not proof.
