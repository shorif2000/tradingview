# How to trade it — the settings, and the evidence behind them

## Start here: the Display preset

The first input is **Display preset**. Leave it on **Beginner**.

| Preset | What appears |
|---|---|
| **Beginner** | BUY/SELL label with its reasons, stop, target, status panel, EMAs, regime tint. Nothing else. |
| **Standard** | + order blocks, strong support/resistance, liquidity lines |
| **Full** | + fair value gaps, BOS/CHoCH, HH/HL structure, candlestick labels |
| **Custom** | every individual switch is obeyed exactly as you set it |

Move up a level only once the current one makes sense. Every feature still exists on
Beginner — it is just not drawn, so nothing is hidden from the logic, only from the screen.

## Reading a zone

Zones now say what they are and why they matter:

```
BUY zone ×3   HIGH RISK
FVG SSL BOS
```

- **Blue = buy zone, red = sell zone**, newest most solid, older ones fading behind it.
- **×3** is the confluence count: how many independent things agree at that price.
  The five checked are a fair value gap, a liquidity pool, market structure, a moving
  average running through it, and the edge of the recent range — and the ones that
  actually fired are named on the second line.
- **Zones below `Hide zones with fewer confluences than` are not drawn at all.** A zone
  nothing else agrees with is just a candle.
- **HIGH RISK** appears when a zone only just clears the minimum. Its border goes dotted
  and thin so a marginal zone never *looks* like a strong one.
- **Used zones grey out** once price has traded back into them — their unfilled interest
  has been worked off.

Signals carry the same honesty: a BUY that only scraped past the minimum is labelled
`⚠ HIGH RISK - only 2 confluences` and turns orange instead of teal.

## Trailing instead of taking the target

Turn on **Mark strong support / resistance**. A level price has defended `strongTouch`
times (default 3) is drawn as a solid line labelled *STRONG SUPPORT ×3 (trail longs here)*.

Those are the levels worth trailing behind, because if one breaks, the reason you were in
the trade broke with it. That is a real exit signal; a fixed trailing distance is not.

**One thing the data is emphatic about: do not move your stop to break-even.** Measured on
your samples, a break-even stop dropped expectancy from +0.291R to +0.175R. Gold routinely
retraces through the entry before continuing, so a break-even stop scratches you out of
trades that would have paid. Leave the stop alone until at least +1R.

## How to size it — measured across 2M and 5M

Pooled across all three samples (2M January, 5M January, 5M June–August):

| Plan | Trades | Green | Expectancy | Worst drawdown |
|---|---|---|---|---|
| 0.01, fixed 2R | 207 | 41.5% | +0.216R | 41% |
| 0.01, 3R target + swing trail | 199 | 38.7% | +0.267R | 31% |
| 0.02, fixed 2R | 154 | 42.9% | +0.252R | 41% |
| 0.02, half at 1R then 3R | 152 | 36.2% | +0.241R | 44% |
| **0.02, half at 1R, rest trails** | **151** | **57.0%** | **+0.368R** | **14%** |
| 0.02, half at 1R + break-even | 163 | 52.8% | +0.157R | 41% |

**The recommendation is 0.02 lots, half off at 1R, trail the rest behind swing structure.**
It won on every axis at once — the highest share of green trades (57%), the best
expectancy (+0.368R), and the *lowest* drawdown (14% against 41%).

That last part is the counter-intuitive bit and it is the reason to prefer it: banking half
at 1R takes risk off the table early, so even though the position is twice the size, the
equity curve is far smoother than 0.01 held to a fixed target.

Per timeframe, same plan:

| | Green | Expectancy | Net £ | Drawdown |
|---|---|---|---|---|
| 2M January | 50.0% | +0.268R | +£53 | 36% |
| 5M January | 61.5% | +0.259R | +£61 | 29% |
| 5M June–August | 59.1% | +0.502R | +£270 | 14% |

**This also changes what I told you about 2M.** With a fixed 2R target 2M was +0.023R —
effectively nothing. With half off at 1R and a trail it reaches +0.268R at a 50% hit rate.
The problem was never only the entries; it was holding a fast-timeframe trade all the way
to a distant fixed target. Caveat: 2M has one sample (January, 46 trades) and no second
period to confirm it. 5M has two samples that agree.

### The catch on 0.02

0.02 lots on £100 is **£6–9 of risk per trade, 6–9% of the account**. The measured
drawdown was only 14% because half comes off at 1R so often — but five losses in a row is
normal for any system, and at this size that is a third of the account. The samples are
eleven weeks, not eleven months.

Honest guidance:

- **£100 account** → 0.01 with the 3R-target-plus-swing-trail plan (+0.267R). Lower
  expectancy, survivable risk.
- **£250+** → 0.02 with half at 1R and a trail becomes proportionate, and it is the better
  plan on every measure.

Sizing is the one thing in this whole system you cannot backtest your way out of.

## Settings summary

| Setting | Value | Why |
|---|---|---|
| Display preset | Beginner | Add layers as you learn them |
| Timeframe | 5M (2M is second-best) | Two agreeing samples on 5M, one on 2M |
| Lots | 0.02 at £250+, else 0.01 | Risk, not signal quality, is the constraint |
| Exit | half at 1R, trail the rest | Best hit rate, best expectancy, lowest drawdown |
| Break-even stop | **off** | Measured to cost 0.12R per trade |
| Session | 07:00–20:00 London | Going 24h costs 92% of the edge |
| Modules | sweep + range on, trend off | Trend was ~zero expectancy in both samples |
| Zone minimum confluence | 2 | Below that a zone is just a candle |
| Strong level touches | 3 | Where to trail, not where to guess |
