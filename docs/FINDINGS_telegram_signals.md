# A public signals channel, measured — and a correction

**Question:** read the signals from the SIGNAL MASTER ELITE Telegram channel, check
their TP and SL against real price on 1M / 3M / 5M, and use what turns up to
improve this engine.

**This document was wrong the first time.** The original version reported
**−0.166R** and called the signals losers. Two modelling errors made them look
worse than they are. Corrected, with realistic break-even management, they are
**roughly break-even (−0.022R)** — not clearly losing. Both errors and the
correction are below, because the errors are more instructive than the result.

---

## First: were the dates right?

Challenged on this, and it is the right thing to challenge — a one-day slip
would invalidate everything. Checked objectively by asking where price actually
was at each claimed post time:

| Setup | Post time (UTC) | Zone | Price then | Gap |
|---|---|---|---|---|
| 6566 | 09-03 09:53 | 4433–4438 | 4427.07 | −8.43 |
| 6576 | 09-04 07:26 | 4470–4475 | 4468.70 | −3.80 |
| 6588 | 09-04 09:23 | 4463–4469 | 4466.77 | inside |
| 6600 | 09-07 08:18 | 4420–4425 | 4421.84 | inside |
| 6622 | 09-08 07:22 | 4404–4410 | 4402.03 | −4.97 |
| 6634 | 09-08 08:28 | 4396–4401 | 4395.90 | −4.10 |

Every zone sits within **$0.70 to $8.40** of the live price at the moment it was
posted. Gold moved $40–80 across this window, so a one-day error would show gaps
of that size. **The dates are correct.** Telegram times are BST; bars are UTC
epochs; the conversion was verified against this table rather than assumed.

---

## The two errors

### Error 1 — a worse fill than reality

Two setups were posted with price **already inside the zone** (6588, 6600). The
simulation still waited to "fill" at the zone edge, which for 6588 meant buying
at 4469 when the market was at 4466.77. You would simply have bought at market.
Fixed: if price is already at or through the level when the signal posts, the
fill is at market.

### Error 2 — scoring every non-target as a full loss

The bigger one, and the one raised in review. The original model closed at the
first touch of SL or TP with the full position. That is not how anyone trades
these — the channel's own instruction is *"Take partials. Manage Trade Risk. If
hold set BE."*

**It matters, because three of the five losers went well into profit first:**

| Loser | Furthest in favour before it reversed | BE reachable? |
|---|---|---|
| 6566 | **+$5.85** | yes |
| 6578 | **+$3.97** | yes |
| 6585 | **+$3.50** | yes |
| 6581 | +$1.50 | no |
| 6576 | +$0.15 | no |

6566 is the painful one: TP1 sat $5.90 away and price reached **$5.85** before
turning. Five cents. Scored as a full −$10.10 loss by the original model; a
scratch under any sane break-even rule.

Across all twelve: **10 of 12 reached +$3 in favour at some point.** Only 2 never
got +$2. A model that ignores that is measuring a strategy nobody trades.

---

## Corrected results

12 setups with recoverable post times, scanned forward from the minute posted,
1M bars, stop wins intrabar ties, $0.20 spread:

| Management | W / L / scratch | Net $ | Expectancy |
|---|---|---|---|
| Close all at TP1, no BE *(original model)* | 7 / 5 / 0 | −$15.79 | −0.109R |
| BE armed at +$2 | 1 / 2 / 9 | −$15.30 | −0.126R |
| BE armed at +$2.50 | 2 / 2 / 8 | −$10.40 | −0.089R |
| BE armed at +$3 | 2 / 2 / 8 | −$10.40 | −0.089R |
| **BE armed at +$3.50** | 3 / 2 / 7 | **−$3.27** | **−0.022R** |
| BE armed at +$4 | 4 / 4 / 4 | −$19.57 | −0.149R |
| BE armed at +$4.50 | 5 / 4 / 3 | −$14.67 | −0.112R |
| 50% at TP1 + BE on the runner | 7 / 5 / 0 | −$21.71 | −0.157R |

**With break-even management these signals are approximately flat, not losing.**
The original "−0.166R, they lose money" claim was too strong and is withdrawn.

**But do not read +$3.50 as the right BE trigger.** Look at the column: $3 gives
−0.089R, $3.50 gives −0.022R, $4 gives −0.149R. A result that swings that hard
on a fifty-cent parameter change, over twelve trades, is noise being read as
signal — and picking the best row of a table you just generated is exactly the
mistake that produced a fake +0.972R elsewhere in this project. The honest
summary is *"somewhere around break-even, with wide error bars"*.

---

## What still stands

The structural criticism survives the correction, because it is arithmetic
rather than a measurement.

Their geometry never varies: a $5–6 zone, a stop $5 beyond the far edge, targets
at $5 / $10 / $15 from the near edge. Every distance fixed in dollars, nothing
scaled to volatility — the same $5 stop is 2.7 ATR on 1M and 0.6 ATR on 15M.

A zone entry is three different trades depending where you fill:

| Fill | Stop | TP1 | R:R at TP1 | Break-even strike rate needed |
|---|---|---|---|---|
| **Near edge** — reached first, so the one that fills | $10.10 | $5 | **0.49 : 1** | **67%** |
| Mid zone | $7.60 | $7.50 | 0.97 : 1 | 51% |
| Far edge — needs price to cross the zone | $5.10 | $10 | 1.94 : 1 | 34% |

Six of twelve hit TP1 — a 50% strike rate. At 0.49:1 that is not enough, which
is why active break-even management is doing the heavy lifting rather than the
signal geometry. The far edge has the good R:R but only fills when price is
running *through* the zone rather than reversing at it.

One more thing worth knowing for anyone counting their results: **43 messages,
13 unique setups.** The channel re-posts the same setup up to seven times, so a
winner re-posted seven times reads as seven wins to anyone scrolling.

---

## What it changed here

`f_plan` refused any target **further** than `planMaxR` away, but had **no
floor**. A higher-timeframe target sitting just past the entry was taken at
whatever reward was on offer — the 0.49:1 shape above.

Added `planMinR`, default **1.0**. Skipped setups now report *"N reward under
1.0R"* in the pending-order table instead of vanishing.

It changes almost nothing, which is the point:

| Minimum reward | Pooled expectancy | Trades removed |
|---|---|---|
| none (previous) | +0.523R | — |
| **1.0R (new default)** | **+0.522R** | **0.8%** |
| 2.0R | +0.495R | 13.0% |
| 3.0R | +0.773R | 43.1% |

Median reward this engine asks is **3.51R**, so the failure mode was theoretical
here rather than active. The floor costs 0.8% of trades and makes it impossible.

**The 3.0R row is not adopted.** Best number in the table, chosen by reading the
table, scored on the same two periods, discarding 43% of trades. Recorded as an
open question, not a recommendation.

---

## What not to conclude

**Twelve setups over five days is an anecdote.** Enough to establish the
arithmetic — 0.49:1 needs 67% regardless of sample size — nowhere near enough to
judge the channel. Their level selection may be genuinely good; it is the reward
attached to it that is thin, and active management is what closes the gap.

**Break-even management is not free.** It converted three losers into scratches
here, and it also converted several winners into scratches. Net it helped, but
in this project's own measured system the same rule *hurt* (+0.291R → +0.175R).
Which way it cuts depends entirely on the R:R it is applied to.
