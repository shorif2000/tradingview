# Answers to your findings — measured on your 149-trade sample

Everything below is measured on your own data: MT5 January M5 (real spread, M1-resolved fills)
plus TradingView 14 Jun – 5 Aug M5. Two periods, opposite market direction.

---

## 1. The green triangle is not a buy signal

The small teal triangle under a candle is the **engulfing-pattern marker** (Visuals → "Pattern
marks"). It marks a candle shape and nothing else. A real entry is a **labelled `BUY` tag plus a
reason box**. Two different things that look alike — my design error, being fixed.

## 2. Why 5m looked dead

Two causes, both mine:

- On your Jun–Aug data the engine fires **2.3 signals/day (~12/week)**. Watching for an afternoon
  can legitimately show nothing.
- Worse: **TREND regime covers 64.9% of your bars**, and I shipped the trend module *off* last
  round. That left the range module only **18.5%** of bars. I optimised expectancy and starved
  your signal rate.

## 3. The 90% win rate — measured, not argued

| Target | Win rate | Expectancy | Net £ |
|---|---|---|---|
| 0.15R | **79.9%** | −0.084R | **−£43** |
| 0.25R | 76.7% | −0.044R | −£9 |
| 1R | 52.4% | +0.043R | +£45 |
| **2R** | 44.3% | **+0.291R** | **+£190** |
| 3R | 36.1% | +0.300R | +£141 |

Win rate is a **dial you trade against payoff**, not a quality measure. Pushing it up by shrinking
the target is what turns this from +£190 into −£43. 90% is reachable only by risking 1 to make
~0.1, which loses money by construction.

## 4. Break-even stops actively cost you money

You asked when to trail the stop in profit. The data has an uncomfortable answer.

| Exit management | Win% | Expectancy | Net £ |
|---|---|---|---|
| **Fixed 2R (current)** | **44.3%** | **+0.291R** | **+£190** |
| Stop → break-even at 1R, target 3R | 32.5% | +0.175R | +£132 |
| Stop → break-even at 0.5R, target 2R | 23.8% | +0.160R | +£118 |
| Stop → break-even at 1R, target 2R | 33.8% | +0.226R | +£163 |
| Swing trail from 1R | 39.2% | **+0.318R** | **+£201** |
| ATR trail from 1R | 38.9% | +0.298R | +£187 |

**Moving your stop to break-even makes things worse**, and it is the single most commonly given
piece of trading advice. It costs ~0.12R per trade here, because gold routinely retraces through
the entry before continuing — you get scratched out of trades that would have paid 2R.

The only exit tweak that helped was a **swing-structure trail starting at +1R**: +0.318R vs
+0.291R. Marginal, but it is the one I'd keep. **Recommendation: don't move the stop until +1R,
then trail behind swing structure. Never to break-even before that.**

## 5. Partial exits — the honest route to a higher hit rate

| Exit style | Win% | Expectancy | Net £ | Lot needed |
|---|---|---|---|---|
| Fixed 2R | 44.3% | +0.291R | +£190 | 0.01 |
| Partials 1R/2R/3R | **56.6%** | +0.202R | +£307 | **0.03** |
| Partials 1R/2R/4R + trail | **58.3%** | +0.258R | +£349 | **0.03** |

This is the real version of what you're asking for: **hit rate up from 44% to 58%**, with a
modest cost in expectancy per unit of risk.

**The catch is the lot size.** 0.01 is your broker's minimum and cannot be split — scaling out in
three requires **0.03 lots**, three times the risk. On a £100 account that is **7–14% risk per
trade**. Two bad trades and you're down a quarter of the account. Partial exits need roughly
**£500–1,000** to be sane. On £100 they are not an option, and the higher net £ in that table is
just the 3× position, not a better strategy.

## 6. Trading all sessions makes it worse

| Configuration | Signals/week | Win% | Expectancy | Net £ |
|---|---|---|---|---|
| **London/NY only (current)** | 12.0 | **44.3%** | **+0.291R** | **+£190** |
| Trend module back on | 13.4 | 41.0% | +0.215R | +£169 |
| All sessions, 24h | 14.2 | 34.7% | +0.023R | +£20 |
| All sessions + trend on | 14.5 | 34.4% | +0.021R | +£36 |
| All sessions, no daily cap | 17.3 | 35.8% | +0.059R | +£45 |
| Everything open, min 1 reason | 24.2 | 31.3% | **−0.077R** | **−£39** |

Going 24-hour buys you **2 extra signals a week and costs 92% of the edge**. The Asian session is
where gold chops without follow-through, which is exactly what a mean-reversion entry needs to
avoid.

That last row is also the mechanism behind your 2-minute complaint: **relax the confirmation
requirement and signal count doubles while expectancy goes negative.** More signals is not more
opportunity — on this data it is strictly worse.

## 7. Your delay point was the most important one on the list

Measured against your M1 file:

| Entry timing | Avg worse entry | Expectancy |
|---|---|---|
| Instant (what the backtest assumes) | — | +0.485R |
| ~60 seconds later | $1.68 | **+0.071R** |
| Worst price in the first minute | $1.71 | **+0.000R** |

**A one-minute delay eats ~85% of the edge.** You said you'll trade manually from mobile MT5 —
that workflow, as-is, has no edge left in it. This is fixable, but it has to be designed for:
place a **pending limit order** at the signal price instead of chasing at market, so a slow fill
costs you the trade rather than the edge.

---

## What I'd change, given all of the above

**Keep:** 2R base target, London/NY session, the confirmation scoring, the ≥2-reason rule.

**Change:** trend module back **on** (you need the signal rate, and the cost is 0.08R not the edge);
swing trail from +1R instead of a fixed stop; pattern marks made visually distinct from signals.

**Reject, with data:** break-even stops, all-session trading, relaxed confirmation counts,
sub-1R targets. Each one measurably loses money on your own sample.

**Gate behind account size:** partial exits at 0.03 lots. Revisit at £500+.

**Build next:** limit-order entry levels so manual mobile execution stops bleeding the edge —
this matters more than any indicator I could add.
