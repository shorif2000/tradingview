# Comparing against a 2-minute scalping indicator

Screenshots of a live "MT TP SCALPER — Signals + TP/SL" running alongside the
reference indicator on a **2-minute** gold chart. What follows separates what
can actually be read off a screenshot from what cannot, because the second
category is larger than it looks.

---

## What is measurable from the images

**Target spacing, and it is the informative part.** Reading the TP labels:

| Screenshot | TP1 | TP2 | TP3 | Step |
|---|---|---|---|---|
| 19:30 | 4358.64 | 4359.69 | 4360.75 | **1.05 / 1.06** |
| 11:16 (a) | 4405.52 | 4407.84 | 4410.17 | **2.32 / 2.33** |
| 11:16 (b) | 4403.67 | 4406.38 | 4409.08 | **2.71 / 2.70** |
| 13:40 | 4393.44 | 4396.91 | — | **3.47** |

Two things follow immediately.

**The three targets are equally spaced.** Every pair of gaps within a setup
matches to the cent. This is TP1/TP2/TP3 = 1×, 2×, 3× of one step.

**The step is volatility-scaled, not fixed.** It ranges $1.05 to $3.47 — a 3.3×
spread. Measured over the same week, 2M ATR(14) on this instrument ran:

| | p10 | median | p90 |
|---|---|---|---|
| ATR(14) on 2M | $1.67 | **$2.71** | $4.91 |

A 2.9× spread, against their 3.3×. And one observed step is **$2.70–2.71**
against a median ATR of **$2.71**. The step is approximately **1 × ATR**.

That is a real difference from the Telegram channel measured in
[`FINDINGS_telegram_signals.md`](FINDINGS_telegram_signals.md), whose $5 steps
never moved regardless of conditions. This indicator is doing the right thing on
that axis.

## What is NOT measurable, and I am not going to guess it

**The stop rule.** SL labels are visible ($4355.08, $4359.23, $4395.55,
$4383.03…) but pairing each to its entry needs the entry price, and the entry
markers overlap the candles at a resolution where I cannot read them to the
cent. Without the pairing there is no risk figure, and without risk there is no
reward-to-risk — which is the number that actually decides whether a setup is
worth taking.

If you want that answered properly, the settings dialog will show the stop rule
directly, or a table export of a few setups would settle it in minutes.

---

## Where it differs from this engine, and which is right

**Targets at ATR steps vs targets at risk multiples.** Theirs sit at fixed ATR
distances. Ours sit at multiples of the risk on that specific trade.

This is not cosmetic. An ATR-spaced target is the *same distance* whether the
stop is tight or wide, so the reward-to-risk silently changes with stop
placement — a wider stop on the same setup quietly turns a 2:1 into a 1:1
without any label changing. Risk multiples hold R:R fixed, and R:R is the
quantity that decides whether a given win rate is enough.

That is the whole lesson from the Telegram analysis: 6 of 12 setups hit their
first target and the account still went nowhere, because the reward was half the
risk.

**A 2-minute chart doubles the cost drag.** Spread is fixed in dollars; the stop
is not:

| Timeframe | Median ATR | 0.5 × ATR stop | Spread as % of risk |
|---|---|---|---|
| 1M | $1.83 | $0.92 | 21.8% |
| **2M** | **$2.71** | **$1.36** | **14.8%** |
| 3M | $3.40 | $1.70 | 11.8% |
| 5M | $4.47 | $2.24 | 8.9% |

Trading their geometry on 2M hands over roughly **1.7× the cost** of the same
approach on 5M. Separately measured here, 3M levels were negative at every
target tested. Faster is not free.

---

## What was worth taking — the UI

The visual language is genuinely better than what this indicator had, and it has
been adopted:

**Shaded risk and reward zones.** A red block from entry to stop, a green block
from entry to the final target. Their relative heights *are* the reward-to-risk,
readable at a glance without parsing a single number. This is the single best
idea in those screenshots.

**Three targets rather than two.** Added as `sigTp3R`, default 3R — but spaced
by risk, not by ATR, for the reason above.

**Price tags at the right edge.** TP1 / TP2 / TP3 / SL as coloured pills at the
end of each line, matching how TradingView's own position tool labels things.

**And one thing they do not do: fading finished plans.** A plan stops being
information the moment it resolves. Once price reaches the stop or the final
target — or the plan runs out of bars — the shading drops back, the price tags
are removed entirely and the lines dim. Live setups now stand out against
finished ones instead of competing with them for attention.

The objects are faded rather than deleted, because the trade still happened and
seeing where it went is the point of leaving history on the chart. All of it is
switchable: *Shade the risk and reward zones*, *Price tags on the right edge*,
*Fade a plan once the move is over*.

Cost: each plan now draws 5 lines, 2 boxes and 5 labels, so the kept-plan cap
dropped from 8 to 6 to stay inside the shared 500-object budget.

**Verified:** compiled on TradingView with no errors, in a scratch buffer, with
the resulting probe removed from the chart afterwards.
