# How to enter, where the stop goes, where the target goes

Two real setups from the last two weeks, with exact prices you can pull up on
your own chart. Read the caveat at the bottom before you size anything.

---

## The rules

**Chart: 5-minute XAUUSD. Session: 07:00–20:00 London only.**
(Trading around the clock was measured to cost 92% of the edge.)

### Step 1 — find the level *before* anything happens

A **swing low** = a candle whose low is lower than the 5 candles either side of
it. A **swing high** is the mirror. You only know it 5 candles later — that lag
is unavoidable, not a fault.

**The level must still be untouched.** If price has already traded through it
since it formed, it is spent. This is the rule most people skip and it is the
one that matters most — see Example B.

### Step 2 — wait for the sweep and the reclaim

One single candle has to do both:

- its **low goes below** the swing low (the stop-run), **and**
- its **close comes back above** it (the reclaim)

That candle is your signal candle. Mirror it for shorts.

*Or* the range-fade version: the candle poke**s** below the lower Bollinger(20,2)
while sitting at the bottom of the last 75 candles, and closes back inside.

### Step 3 — you need two reasons, not one

At least **two** of these on the signal candle:

- bullish engulfing (its body swallows the previous candle's body)
- a lower wick longer than half the candle's total range
- RSI(14) crossing back above 50

One reason is a coincidence. The tie-break rule: if the candle argues both ways,
skip it.

### Entry

**At the open of the very next candle.** Not the close of the signal candle —
you cannot fill on a price that has already gone. On mobile MT5 that is a market
order the moment the new candle opens.

### Stop loss

**Below the signal candle's low, minus 0.35 × ATR(14).**

Then two guards:

- if that comes to **less than 0.8 × ATR**, widen it to 0.8 × ATR — a stop inside
  one candle's normal range is noise, not risk
- if it comes to **more than 2.0 × ATR**, **skip the trade entirely**. Do not take
  it with an oversized stop.

### Take profit

Risk = entry − stop. Then:

- **TP1 = entry + 1 × risk** → take half off here
- **TP2 = entry + 2 × risk** → and trail the rest behind swing lows

**Do not move your stop to break-even.** Measured on your data it dropped
expectancy from +0.291R to +0.175R. Gold routinely dips back through the entry
before it goes. Leave the stop where it is until at least +1R.

---

## Example A — a valid setup, and it lost

**Wednesday 2 September 2026, 08:35 UTC. Set the chart to 5m and scroll there.**

The level: a swing low formed at **07:50 at 4320.60**, and nothing had traded
below it since. Untouched. ✓

The signal candle, 08:35:

| | price |
|---|---|
| open | 4321.74 |
| high | 4326.80 |
| **low** | **4319.57** ← below 4320.60, the stop-run |
| **close** | **4324.96** ← back above it, the reclaim |

Two reasons present: **bullish engulfing** (its body covers the 08:30 candle,
which opened 4323.17 and closed 4321.75) and **RSI crossing back above 50**. ✓

The trade:

| | |
|---|---|
| **Entry** | **4325.11** — the 08:40 open (4324.96) plus spread and slippage |
| **Stop** | **4317.84** — the 4319.57 low minus 0.35 × ATR |
| Risk | **$7.27** |
| **TP1** | **4332.38** (+1R, half off) |
| **TP2** | **4339.65** (+2R) |

**What happened:** price ticked to 4320.41, then 4319.74, then the 08:50 candle
dropped to 4313.31. **Stopped out 15 minutes later for −1R.**

That is not a broken rule or a bad read. It is what roughly 6 out of 10 of these
do. The system makes money because the winners run to 2R, not because most trades
win.

---

## Example B — the one you must NOT take

**Tuesday 1 September 2026, 11:50 UTC.**

This one looks textbook. The 11:50 candle ran up to **4386.74**, above the
**4386.00** swing high from 10:40, and closed back down at **4379.13**. Perfect
sweep and reclaim. It then fell to 4352 within the hour — **it would have paid
2R in 40 minutes.**

**Skip it anyway.** That 4386.00 level had *already been broken* by candles
between 10:40 and 11:50. It was not fresh liquidity — the stops behind it were
already gone, so there was nothing there to grab.

I only caught this because I checked. One winner does not validate breaking the
rule; that is exactly how a rule quietly stops being a rule.

---

## Sizing it on your account

At 0.01 lots (the MT5 minimum), 1 ounce, a $1 move is $1.

Example A risked **$7.27 = £5.72**. On a £100 account that is **5.7% on one
trade.** Four losses in a row — normal at this win rate — is a quarter of the
account.

To risk a sane 2% per trade on 5-minute gold you need roughly **£280**. Below
that you are not trading the system, you are hoping to survive it.

---

## The caveat you need before trusting any of this

The rules above are my re-implementation of the engine that measured +0.497R on
5M. **My version is far stricter than that engine** — it produced 3 signals in
the last 15 days, where the measured engine fires about twice a day.

So **do not read "3 trades, 0 winners" as the system's expectancy.** It is a
small sample from a stricter filter over a bad fortnight. The +0.497R figure
comes from 41 trades in the January sample with the full engine, which also uses
order blocks and higher-timeframe bias that I did not reproduce here.

What the two examples above *are* good for: seeing exactly where the entry, stop
and target go on real candles you can look at yourself. That is what they were
built to show.
