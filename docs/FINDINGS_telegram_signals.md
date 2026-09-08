# A public signals channel, measured

**Question:** read the signals from the SIGNAL MASTER ELITE Telegram channel, check
their TP and SL against real price on 1M / 3M / 5M, and use what turns up to
improve this engine.

**Answer: their geometry loses money by arithmetic, not by bad luck — and it
exposed one genuine hole in our own code.**

---

## What they post

43 signal messages, which reduce to **13 unique setups** — the channel re-posts
the same setup up to seven times. Everything visible spans Thu 3 Sep to Tue
8 Sep 2026; the channel does not serve older history to a recently joined
account, so this is five days, not a sample worth calling a sample.

The shape never varies:

```
GOLD SELL SETUP
Gold Sell Zone 4396 - 4401     <- a 5-6 wide zone
SL : 4406                      <- $5 beyond the FAR edge
TP1 : 4391   TP2 : 4386   TP3 : 4381    <- $5 / $10 / $15 from the NEAR edge
```

**Every distance is a fixed dollar amount.** Nothing scales with volatility.
Gold's median ATR(14) is $1.87 on 1M, $4.37 on 5M and $8.10 on 15M, so the same
$5 stop is 2.7 ATR on one timeframe and 0.6 ATR on another. It is the same $5
in a dead Asian session and during a CPI release.

---

## Why the zone decides everything

A zone entry is not one trade, it is three, depending where you are filled:

| Fill | Stop distance | TP1 distance | **R:R at TP1** |
|---|---|---|---|
| **Near edge** — the price reached *first*, so the one that actually fills | $10.10 | $5 | **0.49 : 1** |
| Mid zone | $7.60 | $7.50 | 0.97 : 1 |
| Far edge — needs price to cross the whole zone | $5.10 | $10 | 1.94 : 1 |

**A limit order at the near edge fills first and gets 0.49:1.** That needs a
**67% strike rate just to break even**.

---

## Measured against real price

12 setups with recoverable post times, each scanned forward from the minute it
was posted, resolved on TradingView's own bars, $0.20 spread charged:

| Fill | Filled | TP | SL | Net $ | Expectancy |
|---|---|---|---|---|---|
| **Near edge** | 12/12 | 6 | 5 | **−$19.86** | **−0.166R** |
| Mid zone | 11/12 | 4 | 5 | +$0.08 | −0.010R |
| Far edge | 9/12 | 1 | 7 | −$21.56 | −0.484R |

Consistent on 1M, 3M and 5M (1M shown; the others differ by under $5).

**Six of twelve hit TP1 at the near edge and it still lost money.** That is the
whole lesson. A 50% strike rate at 0.49:1 is a losing system, and no amount of
"take partials, move to BE" repairs it — those instructions reduce the winners
without touching the losers.

The far-edge column is the other trap: the R:R is genuinely good at 1.94:1, but
price has to cross the entire zone to fill you, so three setups never filled and
of the nine that did, **seven were stopped** — you get filled precisely when
price is running through the zone rather than reversing at it.

---

## What this exposed in our own engine

`f_plan` refused any setup whose target was **further** than `planMaxR` away —
the move is too big to count on. It had **no floor at all**. If a
higher-timeframe target happened to sit just beyond the entry, the trade was
taken at whatever reward was on offer: exactly the shape losing money above.

Added `planMinR`, default **1.0**. Skipped setups now show *"N reward under
1.0R"* in the pending-order table rather than vanishing.

**How much does it change? Almost nothing — and that is the point.**

| Minimum reward | Pooled expectancy | 95% CI | Trades removed |
|---|---|---|---|
| none (previous) | +0.523R | [+0.13, +0.93] | — |
| **1.0R (new default)** | **+0.522R** | [+0.13, +0.93] | **0.8%** |
| 1.5R | +0.479R | [+0.08, +0.90] | 5.7% |
| 2.0R | +0.495R | [+0.08, +0.93] | 13.0% |
| 2.5R | +0.547R | [+0.07, +1.02] | 27.6% |
| 3.0R | +0.773R | [+0.24, +1.34] | 43.1% |

Median reward this engine asks for is **3.51R**, so the failure mode was
theoretical here rather than active. The floor costs 0.8% of trades and makes it
impossible. That is what a guard rail should look like.

**On the 3.0R row: do not promote it.** +0.773R is the best number in the table
and it is exactly the shape of result this project has been burned by twice —
chosen by looking at the table, scored on the same two periods, discarding 43%
of trades. It needs a neighbourhood test and out-of-sample data before it is
anything more than an observation. It is recorded here as an open question, not
a recommendation.

---

## What not to conclude

**Twelve setups over five days is an anecdote.** It is enough to establish the
*arithmetic* — 0.49:1 needs 67% to break even, and that is true regardless of
sample size — but nowhere near enough to judge the channel's edge. Their level
selection may well be good; the R:R attached to it is what fails.

**Fixed-dollar levels are not automatically wrong**, they are wrong *for a
volatility-varying instrument*. The same $5 stop that is sensible at 5M ATR $4.37
is a coin flip at 1M and pointless at 15M.

**The re-posting matters for anyone counting results.** 43 messages, 13 setups.
A reader scrolling the channel sees far more apparent activity than there is,
and a winner re-posted seven times reads as seven wins.
