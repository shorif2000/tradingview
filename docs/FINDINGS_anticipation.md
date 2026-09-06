# Anticipating the level instead of confirming it

**Question:** the buy and sell signals only appear once the move has already
happened. Can the entry be placed *before* the move, with a tight stop?

**Answer: yes, and it measures better than confirming on every axis.** This is
the first result in this project that has survived every test applied to it. It
is also the result where I got the answer badly wrong twice before getting it
right, so the failures are documented alongside it — they are the reason to
believe the final number.

---

## Why the signal is always late

It is not a bug and it is not fixable by tuning. A sweep-and-reclaim signal
cannot fire until the reclaim candle **closes**. On a 5-minute chart that is up
to five minutes and one full candle's range after the low is in. The range
filter has the same problem for the same reason.

But the *level* is not late. A swing low is confirmed 5 bars after it forms and
then just sits there. So you can leave a resting order at it, with a stop at the
market's own invalidation point, and be filled **during** the sweep rather than
after it. Nothing about that is a forecast — it is arithmetic on a level that
already exists.

---

## The comparison

Identical levels, identical stops, identical targets. Only the entry differs.
5M XAUUSD, January (n=71) and June–August (n=124), 195 trades total.

| | CONFIRM (today) | ANTICIPATE |
|---|---|---|
| Expectancy | +0.222R | **+0.523R** |
| 95% CI | [−0.11, +0.58] | **[+0.13, +0.93]** |
| P(no edge) | 10.2% | **0.3%** |
| After deleting the 3 best trades | +0.082R | **+0.392R** |
| Win rate | 32–35% | 35–36% |
| **Median stop** | $6.25 | **$5.22** |
| Median time in trade | 60 min | **30 min** |
| Worst drawdown (0.01 lots) | −£85.63 | **−£39.54** |
| Trades per day | 1.4 | 1.4 |

Long +0.473R, short +0.576R — balanced, which matters because almost everything
else tested in this project worked in one direction and not the other.

---

## Why this one is believable when fourteen earlier attempts were not

The standing bar in this project is "positive in January **and** June–August",
which have opposite market direction. That bar killed fourteen previous ideas.
But it was also measured, on synthetic zero-edge data, that **roughly 25% of
configurations clear it by luck alone**. Passing it once is not evidence.

So the real test is whether the *neighbours* work. A genuine effect is a
plateau; an artifact is a spike.

A 27-cell grid around the chosen settings — anticipation distance × stop floor ×
reward cap:

```
positive in both periods: 25/27 = 93%     (noise baseline ~25%)
median across the whole grid:      +0.253R
cells above +0.30R:                12/27
```

That is a plateau. It is the only one found in this project.

**Where it breaks.** Widening the swing definition to 7 bars either side drops
it to +0.114R, and 7 bars combined with a 4-hour target goes negative
(−0.214R). The effect is real but it is specific to *short-term* structure. Use
5 (3 also works, +0.297R).

---

## Two mistakes, both of which produced a better-looking answer

Recorded because the corrected number is only meaningful next to them.

**1. Intrabar look-ahead.** The tell was "median time in trade: 0 minutes". A
limit order fills part way through its candle, so the rest of that candle's
range is not knowable without minute data — and a 5M candle wide enough to reach
both the stop and the target was being awarded whichever suited. Resolution now
starts on the **next** candle. This halved the apparent edge and dropped an
earlier robustness grid from 72% to 16%, which is *below* the noise baseline —
that version was worthless and was discarded.

**2. Dividing by nearly zero.** A version of this document briefly claimed
**+0.972R** for the structural stop with a higher-timeframe target. It was
false. When the nearest swing sits a few cents from the fill, risk collapses and
a small win is scored as hundreds of R. The distribution gave it away:

```
median outcome                          −1.00R
R:R "achieved" on the best trades        1,424 : 1   and   6,085 : 1
share of gross profit from the best 5%      70%
mean after removing the top 5 trades    −0.065R
5% trimmed mean                         −0.240R
```

A stop $0.04 from entry is not a trade — spread alone removes it. Imposing a
minimum placeable stop distance took +0.972R down to **+0.02R**. The number in
the table above is what is left after that floor is applied, and it survives
deleting its three biggest winners.

---

## The rules

**5M XAUUSD. London hours are better** (12:00–16:00 +0.709R, 16:00–20:00
+0.732R, versus 00:00–07:00 +0.094R) but the overnight session is not negative,
so this is a preference rather than a filter.

1. **Find the level.** A swing high or low with 5 candles either side. It must
   still be **untouched** — if price has traded through it, it is spent.
2. **Rest the order 0.25 × ATR *beyond* it.** Sell limit above a swing high, buy
   limit below a swing low. Resting *at* the level measured **negative**: you
   want to be filled by the stop-run, not by the level.
3. **Stop at the last swing beyond the level**, plus 0.10 × ATR. Not an ATR
   multiple — the market's own invalidation point.
4. **Floor the stop at 0.50 × ATR** from the fill. Closer is not placeable.
   Skip the trade if the structural stop is more than 2.5 × ATR away.
5. **Target the higher timeframe** — the extreme of the last 6 closed 1-hour
   bars. This is the "lower-timeframe entry, higher-timeframe objective" shape:
   the entry is 5M, the objective is 1H.
6. **Skip if the target is more than 6R away.** That move is too big to count
   on. Tightening to 4R made results worse; 8R held up.
7. **Cancel the order** if price closes 0.6 × ATR beyond the level — the level
   broke, the idea is dead.

The indicator draws all of this. Levels that fail rules 4–6 draw no plan at all,
which is the intended behaviour: most levels are not tradeable.

---

## What this does not mean

**The stop is tighter, not tight.** $5.22 median against $6.25. The "$2.64" that
an earlier version of the indicator tooltip advertised was the artifact above.

**35% of these win.** Six losers in a row is an ordinary week. The money is made
because the winners run to the higher-timeframe level, not because most trades
work.

**£100 still cannot trade this.** Average risk is $5.74 = £4.52, which is 4.5%
of a £100 account at the 0.01 lot minimum — better than the 5.5% the
confirmation entry needs, and still far too much. £230 gets you to 2%.

**Both test periods are 2026.** Everything here is in-sample in the sense that
no truly untouched period was held back. The neighbourhood test is a defence
against curve-fitting, not against a regime that has not happened yet. The
sensible next step is to paper-trade it forward for a month before it is sized
up.
