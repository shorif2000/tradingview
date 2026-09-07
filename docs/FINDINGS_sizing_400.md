# £400 at 0.01 lots

**Short answer: yes, £400 works — at 0.01 lots and no more.** It is the first
balance in this project that is genuinely survivable rather than merely
arithmetically possible. But the reason it works is not the one most people
expect, and the thing most likely to stop you is not risk.

Everything below resamples the 123 measured trades of the shipped configuration
(5M levels, 1H target, structural stop, anticipation entry) across two periods
of opposite market direction. `backtester/size400.py`.

---

## 1. Risk per trade — this is now fine

Median stop $5.22 = **£4.11** at 0.01 lots.

| Balance | 0.01 lot | 0.02 lot |
|---|---|---|
| £100 | 4.1% (p90 8.1%) | 8.2% (p90 16.3%) |
| £280 | 1.5% (p90 2.9%) | 2.9% (p90 5.8%) |
| **£400** | **1.0% (p90 2.0%)** | 2.1% (p90 4.1%) |
| £1000 | 0.4% (p90 0.8%) | 0.8% (p90 1.6%) |

At £400 a typical loss is 1.0% and a bad one is 2.0%. That is textbook. The
p90 column matters more than the median — stops are not all the same size, and
the wide ones arrive on the days you least want them.

---

## 2. Margin — this is the constraint nobody checks

A 0.01 lot of XAUUSD is **one ounce**, so the notional is the full gold price:
$4,425 ≈ £3,484. What that ties up depends entirely on which entity your account
sits under:

| Leverage | Margin per 0.01 lot | % of a £400 account |
|---|---|---|
| **20:1** (FCA / UK — gold is capped here) | **£174** | **44%** |
| 100:1 (common offshore default) | £35 | 9% |
| 500:1 (Vantage offshore maximum) | £7 | 2% |

**Check which entity you are on before anything else.** Under FCA rules a single
0.01 lot consumes 44% of £400, and two positions open at once leaves you one
wick from a margin call — regardless of how sensible the risk per trade looks.
The strategy averages 1.4 trades a day and holds ~30 minutes, so overlaps happen.

If you are on the FCA entity, £400 supports **one position at a time, full
stop.** On an offshore entity margin is a non-issue and risk is the only limit.

---

## 3. What it actually does

20,000 simulated paths. Critically, these propagate uncertainty in the *edge
itself* — each path draws its own plausible version of the true distribution and
then trades inside it. A simulation that treats +0.523R as a known constant only
ever goes up, and is fiction.

The measured edge was +0.523R with a 95% interval of **[+0.13, +0.93]**. So all
three of these are consistent with what has been observed:

### 0.01 lots

| Assumption | 1-year median | 10th pct | Median worst DD | P(down 30%) | P(account dead) |
|---|---|---|---|---|---|
| **As measured** (+0.523R) | £1,049 | £603 | 12% | 0% | 0% |
| **Conservative** (+0.13R) | £425 | £57 | 38% | 24% | 18% |
| **No edge** (0.00R) | £218 | £54 | 65% | 45% | 38% |

### 0.02 lots

| Assumption | 1-year median | 10th pct | Median worst DD | P(down 30%) | P(account dead) |
|---|---|---|---|---|---|
| As measured | £1,698 | £806 | 19% | 2% | 1% |
| Conservative | £428 | £49 | 66% | 44% | **39%** |
| No edge | £58 | £45 | 87% | 65% | **60%** |

**Read the conservative row, not the measured one.** At 0.01 lots the worst
realistic case is a year of going sideways with a 38% drawdown and roughly a
1-in-5 chance the account is finished. At 0.02 lots the same assumption gives a
**39% chance of being wiped out**. Doubling the size does not double the
outcome — it doubles the upside and roughly triples the chance of not being
there to collect it.

**So: 0.01 lots. Not 0.02.** Revisit size at £800, not before, and only if the
live results have tracked the backtest.

---

## 4. The losing streak you have to sit through

Win rate is **35.8%** — losing is the normal outcome of any single trade. Over
300 trades (about seven months), the longest run of consecutive losses:

- median **11 in a row**
- 90th percentile **15 in a row**
- worst simulated **36**

At 0.01 lots an 11-loss streak costs about **£45**, and a 15-loss streak about
**£62**. On £400 that is 11% to 16% of the account, arriving with no winners in
between, and it is *expected*, not a malfunction.

This is the part that ends most accounts. Not the maths — the eleven-in-a-row.

---

## What £400 does not fix

- **The edge is still uncertain.** P(no edge) was 0.3% and 93% of the parameter
  neighbourhood was positive, which is the strongest evidence in this project
  and still not proof. Both test periods are 2026.
- **Nothing here is compounded.** Lot size stays at 0.01 throughout, because
  0.01 is the minimum and cannot be reduced when the account falls. That
  asymmetry is why small accounts die: you can always size up, never down.
- **Spread is modelled at $0.20.** It widens exactly when these setups trigger.

The sensible move at £400 is to paper-trade or trade 0.01 lots for a month and
compare the live result against the backtest before believing any of the
one-year figures.
