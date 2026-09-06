# CRT on gold — tested on real history, including the part that killed my own result

You asked about Candle Range Theory on 4H / Daily / Monthly, and then to check
against real historic data on TradingView. That second instruction is the
important one: **it overturned a result I had already written up.**

## What I found first, and why it was wrong

On six months of 4H I found that the *inverse* of CRT — trading **with** the
sweep instead of fading it — returned **+0.262R**, positive in all four quarters,
and replicated on your H4 export at +0.173R. I was ready to call it the best
thing in this project.

Then I forced TradingView to load its full history (`scrollToFirstBar` on the
time scale, rather than just shrinking bar spacing, which never requests older
data). **5,679 4H bars back to January 2023** instead of 782.

| 4H continuation | by year |
|---|---|
| 2023 | **−0.110R** |
| 2024 | +0.074R |
| 2025 | +0.058R |
| 2026 | **+0.251R** |

Over 3.7 years and 1,528 setups: **+0.052R, 95% CI [−0.021, +0.121], P(no edge)
7.8%.** The interval contains zero.

My six-month sample happened to sit inside 2026, which is the one strongly
positive year. **The finding was a regime artifact.** Six months of 4H looked
like 208 independent setups and behaved like one market condition.

## Classic CRT loses — and this part is solid

CRT as taught: a range candle, then a candle that sweeps **one** side and closes
back inside, then distribution toward the **opposite** end. Fade the sweep.

4H, 3.7 years, 1,524 setups: **−0.099R**, and negative in every single year:

| 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|
| −0.091R | −0.098R | −0.095R | −0.117R |

Across every timeframe tested:

| timeframe | span | setups | win% | expectancy |
|---|---|---|---|---|
| 15M | 12 days | 254 | 47.2% | −0.054R |
| 1H | 7 weeks | 236 | 45.3% | −0.041R |
| **4H** | **3.7 years** | **1,524** | **44.2%** | **−0.099R** |
| Daily | 8.5 years | 704 | 45.7% | −0.030R |
| Weekly | 8.5 years | 136 | 49.3% | −0.055R |
| Monthly | 8.5 years | 27 | 40.7% | −0.150R |

Six timeframes, six negatives, and the deepest sample is the most negative and
the most consistent. Confirmed independently on your H4 export (−0.059R) and H1
export (−0.091R).

**Why it fails despite decent win rates.** 44–49% feels fine. The payoff does
not: targeting the opposite end of the range after a deep sweep gives a median
reward around **1.0R**. One variant hit a **69% win rate and still lost money**
at 0.4R median. A high win rate with a small target is exactly how a pattern
feels right and loses anyway.

## Daily, over 8.5 years, is a regime coin-flip

| year | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|
| continuation | +0.18 | −0.21 | −0.14 | −0.19 | +0.13 | −0.05 | −0.04 | +0.19 | +0.27 |

Pooled: **−0.001R over 706 setups.** Four positive years, five negative. This is
not an edge switching on and off — it is what no edge looks like when you slice
it finely enough to find encouraging years.

Note 2025 and 2026 are the two strongest, matching the 4H result. Gold has been
trending recently. Momentum strategies look excellent in that window. That is a
statement about 2025–26, not about gold.

**Monthly is not testable.** 8.5 years yields 27 setups. Nothing you conclude
from 27 trades is a conclusion, in either direction.

## What this costs the earlier 4H claims

Earlier in this project I reported the range filter held to the opposite signal
at **+0.423R on 4H** over 20 months, and called it the most promising unverified
result. It sat in the same 2024–2026 window that the CRT continuation test now
shows is regime-dependent, and it was never checked year by year. **Treat it as
unproven for the same reason** until it is run over 2023 and earlier.

## What actually survives deep testing

| system | timeframe | evidence |
|---|---|---|
| **mean-reversion engine** (range fade + liquidity sweep) | **5M** | +0.497R, P(no edge) 1.5% |
| mean-reversion engine | 3M | +0.375R, P(no edge) 4.0% |
| Range filter | any | +0.002R, no edge |
| CRT as taught | any | negative at all six timeframes |
| CRT inverse | 4H | +0.052R, CI spans zero, one bad year in four |

## How to load real history on TradingView

For anyone repeating this: shrinking bar spacing does **not** fetch older data —
it only re-renders what is loaded. The chart requests history when you scroll
past the loaded left edge:

```js
model.timeScale().scrollToFirstBar()   // 782 bars -> 5,679 bars on 4H
```

That single call is the difference between a six-month sample and 3.7 years, and
in this case between a false positive and the truth.

## What would settle the momentum question properly

Export **5+ years of H4 from MT5** (View → Symbols → XAUUSD → Bars → set range →
Export Bars). TradingView gave 3.7 years; MT5 will go further, and the years
2018–2022 are exactly the ones missing from the 4H test. Run `backtester/crt.py`.
