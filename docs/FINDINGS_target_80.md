# The 80% / +0.20R target, on £500

Reproduce with `python3 backtester/target.py all`.

## What was asked

A target table was supplied: 78.5–80.6% TP1 hit rate and +0.18 to +0.21R
expectancy across 1m, 2m and 3m, with rules stated as

- signal = range-filter flip
- SL = 50% of the signal candle's range beyond its extreme
- TP1 = 0.5R
- a same-bar SL + TP1 counts as a stop
- a trade that hits neither is "flip first", closed when the signal reverses

Balance £500.

## The table's own arithmetic is correct

At 0.5:1 the break-even hit rate is 1/(1+0.5) = **66.7%**. Their 80.6% gives

```
0.806 x 0.5 - 0.194 x 1.0 = +0.209R
```

which matches the quoted +0.21R exactly. The sum is internally consistent.
Nothing is wrong with the maths. Two other things are.

## Problem one: we do not measure 80%

Same rules, our data, two periods of opposite market direction:

| sample | signals | TP1 | SL | flip | hit% (their basis) | E[R] their basis | E[R] all signals | median stop |
|---|---|---|---|---|---|---|---|---|
| 1M Jan | 1074 | 609 | 300 | 165 | 67.0% | +0.005R | **−0.090R** | $3.50 |
| 2M Jan | 540 | 312 | 150 | 77 | 67.5% | +0.013R | **−0.076R** | $4.81 |
| 3M Jan | 355 | 217 | 88 | 50 | 71.1% | +0.067R | **−0.020R** | $6.26 |
| 5M Jan | 207 | 129 | 48 | 30 | 72.9% | +0.093R | **−0.011R** | $8.61 |
| 5M Jun–Aug | 440 | 277 | 115 | 48 | 70.7% | +0.060R | **−0.007R** | $7.59 |

Our hit rate is **67–73%**, not 78.5–80.6%. That sits on or barely above the
66.7% break-even line, which is why "their basis" expectancy collapses from
+0.20R to between +0.005R and +0.093R. An 11-point hit-rate gap is not a
rounding difference; it is the entire edge.

## Problem two: the hit rate excludes a quarter of the trades

Their own counts show it. Signals = TP1 + SL + flip-first: 513 = 311 + 85 + 117.
But the hit rate is TP1/(TP1+SL). On 1m that leaves **117 of 513 signals — 23%
of them — out of the quoted number entirely.** Their profit and loss appears
nowhere in the +0.18R.

Those trades are not scratches. Measured here:

| sample | flips | share of signals | mean outcome | % positive |
|---|---|---|---|---|
| 1M Jan | 165 | 15.4% | **−0.628R** | 0.6% |
| 2M Jan | 77 | 14.3% | **−0.601R** | 1.3% |
| 3M Jan | 50 | 14.1% | **−0.548R** | 2.0% |
| 5M Jun–Aug | 48 | 10.9% | **−0.553R** | 2.1% |

A flip-first trade averages about two thirds of a full stop and is positive
roughly 1% of the time. Applying our measured flip outcome to **their** counts:

| | TP1 | SL | flip | their E[R] | E[R] with flips counted |
|---|---|---|---|---|---|
| 1m | 311 | 85 | 117 | +0.178R | **−0.002R** |
| 2m | 708 | 170 | 238 | +0.210R | **+0.035R** |
| 3m | 105 | 26 | 32 | +0.202R | **+0.054R** |

Even granting their hit rate in full, counting the excluded trades removes most
of the expectancy.

## Can it be fixed?

Three responses, only one of which is an actual rule change. Every variant
judged on all five samples; "ALL+" would mean positive in every one.

| variant | pooled | 95% CI | P(no edge) |
|---|---|---|---|
| TP 0.5R, exit on flip (as specified) | −0.057R | [−0.08, −0.03] | 100.0% |
| TP 0.75R, exit on flip | −0.060R | [−0.09, −0.03] | 100.0% |
| TP 1.0R, exit on flip | −0.060R | [−0.09, −0.03] | 100.0% |
| TP 0.5R, HOLD through flip | −0.057R | [−0.08, −0.03] | 100.0% |
| TP 0.75R, HOLD | −0.054R | [−0.09, −0.02] | 99.9% |
| TP 1.0R, HOLD | −0.057R | [−0.09, −0.02] | 99.9% |
| TP 1.5R, HOLD | −0.064R | [−0.11, −0.02] | 99.7% |
| TP 2.0R, HOLD | −0.055R | [−0.11, −0.00] | 97.7% |
| TP 0.5R, SL 1.0× candle, HOLD | −0.047R | [−0.08, −0.02] | 100.0% |
| TP 0.5R, SL 1.5× candle, HOLD | −0.037R | [−0.06, −0.01] | 99.7% |

**Nothing clears zero.** Not one variant is positive pooled, and not one is
positive in all five samples. Holding through the flip does not rescue it — it
relabels the loss rather than removing it. Widening the stop helps a little and
is still negative.

Cost is part of why. A 0.5R target on a $3.50 stop means the target is $1.75
and the spread is $0.20 — over 11% of the reward:

| sample | spread $0.00 | $0.10 | $0.20 | $0.30 |
|---|---|---|---|---|
| 1M Jan | 69.0% −0.059R | 67.7% −0.077R | 67.0% −0.090R | 66.4% −0.099R |
| 3M Jan | 72.5% +0.001R | 72.1% −0.007R | 71.1% −0.020R | 71.1% −0.021R |
| 5M Jan | 74.2% +0.009R | 73.6% +0.001R | 72.9% −0.011R | 72.7% −0.016R |

The best cells are barely above zero **at zero cost** and go negative the moment
a real spread is charged. That is the signature of no edge, not a small one.

## What £500 does

Sizing is not the constraint. At 0.01 lots (1 ounce, so a $1 move is $1):

| sample | median stop | in £ | % of £500 |
|---|---|---|---|
| 1M Jan | $3.50 | £2.75 | 0.55% |
| 2M Jan | $4.81 | £3.79 | 0.76% |
| 3M Jan | $6.26 | £4.93 | 0.99% |
| 5M Jan | $8.61 | £6.78 | 1.36% |
| 5M Jun–Aug | $7.59 | £5.98 | 1.20% |

Every one is under 2% — comfortable. **The constraint is the expectancy, not the
account size.**

20,000 bootstrapped paths over one month, at the trade frequency the signal
actually produced:

| | trades/mo | median | 10th pct | 90th pct | median DD | P(dead) |
|---|---|---|---|---|---|---|
| 1m, all signals | 1074 | **£244** | £142 | £345 | 54% | 1% |
| 1m, flips excluded | 909 | £711 | £623 | £796 | 6% | 0% |
| 2m, all signals | 540 | **£361** | £262 | £459 | 33% | 0% |
| 2m, flips excluded | 463 | £663 | £577 | £749 | 7% | 0% |
| 3m, all signals | 355 | **£468** | £373 | £562 | 18% | 0% |
| 3m, flips excluded | 305 | £714 | £634 | £794 | 5% | 0% |
| 5m, all signals | 207 | **£550** | £454 | £644 | 11% | 0% |
| 5m, flips excluded | 177 | £739 | £661 | £817 | 4% | 0% |

The two rows for each timeframe are the whole argument. Excluded-flips is what
the target table measures, and it turns £500 into £663–739 in a month. All
signals is what a real account experiences, and it turns £500 into £244–550 —
**a loss on every timeframe except 5m, which roughly breaks even.**

The gap between those two rows is not slippage or modelling; it is 165 trades on
1m that the headline number never counted.

## Verdict

The 80% / +0.20R target is not reachable from this signal.

- our hit rate is 67–73%, against 66.7% break-even at 0.5:1
- the quoted hit rate excludes 11–15% of signals here (23% in their own 1m
  counts) whose measured outcome is about −0.6R each
- applying our flip outcome to their own counts drops +0.178R to −0.002R
- every attempted fix is negative pooled, P(no edge) 97.7–100%
- £500 sizes the trade comfortably and cannot rescue a negative expectancy

This is not an argument that the table was fabricated. It is an argument that
**TP1/(TP1+SL) is the wrong denominator**, and that the difference between it
and TP1/all-signals is exactly the difference between +0.21R and losing money.
If the flips settle near break-even in live trading rather than at −0.6R, the
picture changes — that is the one measurement worth taking, and it is a
forward-test question, not a backtest one.

For contrast, the anticipation entry in `backtester/anticipation.py` measures
+0.523R with 93% of its parameter neighbourhood positive in both test periods.
That remains the only plateau found in this project.
