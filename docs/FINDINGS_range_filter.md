# Does the signal have an edge? — 2M / 3M / 5M

Short answer: **no.** Measured over 997 trades, the range filter's longs and
shorts are a coin flip, and the confidence interval comfortably contains zero.
The mean-reversion engine already in this repo, run on the same bars, is
positive on all four samples.

## How the test was built

The signals come from a **dual range filter** (fast 27 / 1.6, slow 55 / 2, source
close) — established by reading the reference public input surface, not guessed.
`backtester/rf_lib.py` reimplements it from the public algorithm, including the
`CondIni` state variable that makes signals strictly alternate.

Rules kept identical to the rest of this project so the numbers are comparable:

- entry on the **next bar's open**, never the close that produced the signal
- spread charged on both sides at $0.20
- stop 1.2 × ATR(14), target 2R unless stated
- **stop wins intrabar ties**, resolved from M1 where M1 exists
- one position at a time

2M and 3M were resampled from the January M1 export. June–August is a M5
TradingView export, so it cannot produce 2M or 3M bars — **the second period only
exists at 5M**, and that limits how much any 2M or 3M result can be trusted.

## How correct are the longs and shorts?

Direction only — did price simply move the right way, exits ignored:

| horizon | 2M Jan | 3M Jan | 5M Jan | 5M Jun–Aug |
|---|---|---|---|---|
| 10 bars | 46.7% | 47.9% | 55.6% | 49.0% |
| 20 bars | 51.7% | 50.3% | 53.6% | 53.8% |
| 40 bars | 50.3% | 49.8% | 49.4% | 50.5% |

Nothing here is distinguishable from a coin. Longs and shorts are equally
mediocre — there is no side that works and no side that is broken.

As trades, with all three combination modes:

| sample | mode | trades | win% | long win% | short win% | exp R |
|---|---|---|---|---|---|---|
| 2M Jan | both | 334 | 29.9% | 29.3% | 30.6% | −0.105 |
| 2M Jan | fast | 428 | 34.3% | 35.9% | 32.9% | +0.028 |
| 3M Jan | both | 224 | 32.6% | 31.9% | 33.3% | −0.030 |
| 3M Jan | fast | 273 | 33.0% | 32.9% | 33.1% | −0.008 |
| 5M Jan | both | 126 | 28.6% | 29.2% | 27.9% | −0.162 |
| 5M Jan | fast | 168 | 28.6% | 29.1% | 28.0% | −0.146 |
| 5M Jun–Aug | both | 313 | 35.5% | 34.0% | 36.8% | +0.056 |
| 5M Jun–Aug | fast | 356 | 39.0% | 35.5% | 42.8% | +0.163 |

A 2R system needs 33.3% just to break even before costs. Most of these are below
it. Two incidental findings worth keeping:

- **"Both must agree" is nearly identical to "slow only."** The slow filter is
  the binding constraint; the fast one almost never vetoes it. So the question I
  could not settle from the settings dialog turns out not to matter much.
- **The band filter can never bite.** When the filter moves it moves to exactly
  `price − range`, so `close > filt + range` is an equality, never a strict
  inequality. Any "require price beyond the band" rule is a no-op by construction.

## Fourteen attempts to improve it

Every configuration measured on both periods, because a change that works in one
and inverts in the other is what a spurious pattern looks like:

| config | Jan (mean of 2M/3M/5M) | Jun–Aug | verdict |
|---|---|---|---|
| baseline both 2R | −0.099 | +0.056 | flips sign |
| baseline fast 2R | −0.042 | +0.163 | flips sign |
| 1R target | −0.077 | +0.069 | flips sign |
| 1.5R target | −0.100 | +0.026 | flips sign |
| 3R target | −0.130 | +0.005 | flips sign |
| wide stop (2.0 ATR) | +0.045 | −0.076 | flips sign |
| tight stop (0.8 ATR) | −0.074 | −0.041 | negative both |
| + session 07:00–20:00 | −0.137 | +0.041 | flips sign |
| + EMA200 alignment | −0.079 | +0.005 | flips sign |
| + EMA200 + session | −0.231 | +0.035 | flips sign |
| + half-band | −0.099 | +0.056 | flips sign (no-op) |
| + EMA200, 1R | −0.068 | +0.087 | flips sign |
| **inverted** (fade every signal) | −0.052 | −0.105 | negative both |
| inverted + session | −0.003 | −0.232 | negative both |

**Not one is positive in both periods.** Inverting deserves its own mention: if
the signals were reliably wrong that would be an edge, and they are not — fading
them loses money too. That is what genuinely no information looks like.

## Pooled, with intervals

| system | trades | expectancy | 95% CI | P(no edge) |
|---|---|---|---|---|
| Range filter | 997 | −0.045R | [−0.130, +0.043] | **84.6%** |
| Mean reversion | 213 | +0.263R | [+0.071, +0.460] | **0.3%** |

997 trades is a well-powered null. This is not "we could not detect an edge for
lack of data" — it is a reasonably tight interval centred just below zero.

## The mean-reversion engine on the same bars

0.02 lots, half off at 1R, swing trail:

| sample | trades | win% | exp R | net £ | max DD | P(no edge) |
|---|---|---|---|---|---|---|
| 2M Jan | 47 | 29.8% | +0.135 | +£2 | 34.8% | 25.1% |
| 3M Jan | 47 | 44.7% | +0.375 | +£82 | 19.4% | 4.0% |
| **5M Jan** | 41 | 46.3% | **+0.497** | +£138 | 21.1% | **1.5%** |
| 5M Jun–Aug | 78 | 37.2% | +0.150 | +£126 | 57.3% | 16.7% |

Positive on all four, and it fires about a fifth as often — 213 trades against
997 — which matters when every trade pays a spread.

**Timeframe ranking is consistent: 5M > 3M > 2M.** 2M's interval spans zero
comfortably and it earned £2 across three weeks. It is not established.

## Does the range filter work as context rather than as a signal?

The one hybrid worth testing: split the mean-reversion trades by whether the
range filter agreed with them.

| period | RF aligned | RF opposed |
|---|---|---|
| January | −0.109R (n=26) | +0.451R (n=99) |
| June–August | +0.347R (n=8) | +0.044R (n=67) |

**Sign flips between periods**, on tiny aligned samples. No, it does not work as
context either. This is the same failure mode as H1 trend, sweep state and
regime in the earlier replication test — looked useful once, inverted the next
time.

## What to actually do

1. **Do not trade the range filter's markers.** Keep the script for its map — the
   liquidity levels, the FVGs and CE, EMA 21 and VWAP are useful furniture.
2. **Use the mean-reversion engine for entries**, `Signal engine = Mean reversion`.
3. **Trade 5M. 3M second.** 2M is not established on one sample of 47 trades.
4. Nothing above changes the sizing problem: 0.02 lots on £100 is 6–9% of the
   account per trade, and the June–August drawdown was 57%.

## Caveats

- June–August exists only at 5M, so the both-periods discipline that killed
  fourteen range-filter variants could only be applied at 5M. The 2M and 3M
  columns each rest on one three-week sample.
- The mean-reversion numbers are the same measurements as the rest of the repo
  and carry the same selection-bias caveat recorded in `AGENTS.md` §6: the module
  choice was made by looking at these samples.
- Reproduce with `python3 backtester/run_rf.py`, `run_grid.py`, `run_sim_grid.py`,
  `run_compare.py`.
