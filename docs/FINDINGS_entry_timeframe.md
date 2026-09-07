# Does a faster entry timeframe help? 1M / 3M levels, 5M / 15M levels, HTF targets

**Question:** use 1M or 3M for early entries, with 5M/15M levels, targeting
1H / 4H / Daily.

**Answer: no, and for two separate reasons — one of which makes the question
moot before any data is involved.**

All numbers below come from TradingView's own data on the live chart, collected
and backtested in the browser (`tools/tv_console_backtest.js`). No local CSVs.

---

## 1. For a resting order, the entry timeframe does not exist

This is the part worth internalising, because it is not a measurement — it is
arithmetic.

The order sits at `level ± 0.25 × ATR`. It fills when price trades there. **The
chart you happen to be watching has no effect on that.** A buy limit at 4,412.30
fills at 4,412.30 whether the chart is set to 1M, 5M or Daily. Switching to a
faster chart to "get in earlier" is watching the same event through a finer lens.

A faster chart only changes the entry for a **signal-triggered** system, where
the signal waits for a candle to close and a shorter candle closes sooner. That
is the system that was already measured at no edge — and speeding it up buys a
faster signal *and* proportionally more noise.

What a finer timeframe genuinely does buy is **backtest resolution**: a limit
fills part way through its bar, so the rest of that bar has to be discarded
(invariant I19). On 5M that discards up to 5 minutes; on 1M, one minute. Real,
but it changes what the test can *see*, not what the trade *earns*.

---

## 2. Cost does not shrink with the timeframe — the stop does

Median ATR(14) and a 0.50 × ATR stop, measured on the live chart, against a
$0.20 spread:

| Timeframe | Median ATR | 0.50 × ATR stop | **Spread as % of risk** |
|---|---|---|---|
| **1M** | $1.87 | $0.93 | **21.4%** |
| **3M** | $3.41 | $1.71 | **11.7%** |
| 5M | $4.37 | $2.19 | 9.1% |
| 15M | $8.10 | $4.05 | 4.9% |
| 1H | $14.35 | $7.17 | 2.8% |

Spread is fixed in dollars. The stop is not. Dropping from 5M to 1M more than
doubles what every trade pays before it has done anything, and the measured edge
is +0.523R — not a margin that survives handing over another 12% of risk per
trade. And $0.20 is the *quiet* spread; on gold it widens exactly when these
setups trigger.

---

## 3. Measured, all nine combinations

Identical rules throughout — the only differences are which timeframe the levels
come from and where the target sits.

| Levels | Target | n | Expectancy | Win | 95% CI | P(no edge) | −top 3 | Med stop |
|---|---|---|---|---|---|---|---|---|
| 3M | 1H | 65 | **−0.175R** | 18.5% | [−0.58, +0.28] | 79% | −0.435 | $5.39 |
| 3M | 4H | 38 | **−0.327R** | 18.4% | [−0.80, +0.23] | 90% | −0.743 | $5.81 |
| 3M | Daily | 23 | **−0.215R** | 30.4% | [−0.72, +0.32] | 79% | −0.665 | $4.69 |
| **5M** | **1H** | 58 | **+0.302R** | 29.3% | [−0.23, +0.84] | **14%** | +0.016 | $5.48 |
| 5M | 4H | 32 | +0.158R | 31.3% | [−0.50, +0.92] | 36% | −0.391 | $6.50 |
| 5M | Daily | 24 | −0.397R | 25.0% | [−0.79, +0.12] | 94% | −0.750 | $5.08 |
| 15M | 1H | 91 | +0.113R | 27.5% | [−0.21, +0.47] | 22% | −0.080 | $8.59 |
| 15M | 4H | 50 | +0.114R | 30.0% | [−0.38, +0.70] | 32% | −0.190 | $11.27 |
| 15M | Daily | 23 | +0.002R | 34.8% | [−0.58, +0.69] | 53% | −0.534 | $11.19 |

**What this says:**

- **3M levels are negative at every single target.** Not weak — negative, with
  the worst win rates in the table (18%), and worse still with the three best
  trades removed. Going finer than 5M for the levels actively destroys the edge.
- **5M levels → 1H target is the best row**, which is the configuration already
  in the indicator. It was arrived at from completely separate MT5 data across
  two periods, and TradingView's own data over a different, shorter window
  independently picks the same winner. That agreement is the most useful thing
  in this table.
- **15M works, but weaker** (+0.113 / +0.114), and it goes negative once the
  three best trades are removed. It also needs a $8.59–$11.27 stop, which is
  double 5M's — on a small account that is the binding problem, not expectancy.
- **Daily targets fail everywhere.** Too far to reach before the stop is hit.

---

## The caveat that applies to this whole table

A TradingView Basic account loads roughly **5,000 bars whatever the
timeframe**, so a faster timeframe buys *less* history, not more:

| Timeframe | Bars | Trading days available |
|---|---|---|
| 1M | 7,007 | **4.9** |
| 3M | 6,937 | 14.5 |
| 5M | 5,544 | 19.3 |
| 15M | 6,416 | 66.8 |

That is why **1M is absent from the results table entirely** — 4.9 days yields
roughly seven trades, which is not a sample, it is an anecdote. Even the rows
shown are small: every confidence interval crosses zero, so no single row here
is conclusive on its own. The 5M → 1H row is worth something only because it
agrees with a larger, two-period test on independent data.

Treat this table as a filter, not a proof: it is good enough to rule the 3M and
Daily combinations **out**, and not good enough to promote anything **in**.
