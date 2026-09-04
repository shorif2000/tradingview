# Trading the signals manually from £100 — 2M to 4H

Measured on the indicator's **real per-bar signals**, pulled from the chart's own
data (the columns right-click → Table view shows), not on a reconstruction.

## The short answer

**You cannot trade these signals from a £100 account on any timeframe.** On the
timeframes £100 can nearly fund, the signals lose money. On the timeframes where
they make money, one trade risks 18–29% of £100.

Every timeframe ruined the account:

| timeframe | ruined after | on |
|---|---|---|
| 3M | 100 trades | 2026-09-03 (6 days in) |
| 5M | 70 trades | 2026-08-28 (4 days in) |
| 15M | 23 trades | 2026-08-04 (7 days in) |
| 1H | **8 trades** | 2026-04-07 (12 days in) |
| 4H | 65 trades | 2025-11-02 |

## Why: 0.01 lots is the smallest MT5 will take

0.01 lots of gold is 1 ounce, so a $1 move is $1. A 1.2 × ATR stop costs:

| timeframe | median ATR | risk per trade | % of £100 | account needed for 2% risk |
|---|---|---|---|---|
| 3M | $3.61 | **£3.41** | 3.4% | £170 |
| 5M | $4.80 | **£4.53** | 4.5% | £227 |
| 15M | $8.16 | **£7.71** | 7.7% | £385 |
| 1H | $18.68 | **£17.65** | 17.7% | £883 |
| 4H | $24.49 | **£29.39** | 29.4% | £1,470 |

Six losses in a row is ordinary for a system winning 35–40%. At 17.7% a trade
that is the account, twice over.

## What the signals are actually worth

Fixed 0.01 lots, ruin ignored so the edge can be measured over the full sample.
Two exit styles: fixed 2R with an ATR stop, and **flip** — hold until the
opposite signal, which is how you would naturally trade an alternating marker.

| timeframe | span | signals | 2R exp R | flip exp R | flip win% | flip £/day | flip £/week |
|---|---|---|---|---|---|---|---|
| 3M | 7.7 days | 170 | −0.193 | −0.162 | 33.9% | −£13.80 | −£48.31 |
| 5M | 11.5 days | 169 | −0.172 | −0.087 | 37.5% | −£6.36 | −£34.97 |
| 15M | 38.6 days | 173 | +0.107 | +0.100 | 37.8% | +£0.34 | +£1.69 |
| 1H | 161.8 days | 149 | +0.082 | +0.223 | 40.1% | +£3.82 | +£15.95 |
| 4H | 623.6 days | 152 | +0.071 | **+0.423** | 40.7% | +£13.55 | +£25.33 |

The pattern is consistent and it makes sense for a trend-following device: the
higher the timeframe, the better it does, and **holding to the opposite signal
beats a fixed 2R target** — because a trend follower earns its living from the
few trades that run, and a 2R cap throws exactly those away.

Those £/day figures are not achievable as written. At fixed 0.01 lots the 1H
column carries a 427% drawdown — the equity went deep into negative territory on
the way. They measure the signal, not an account.

## What you could realistically make, properly sized

Risking 2% of a compounding balance, starting at £100:

| timeframe | plan | end balance | max drawdown | per week |
|---|---|---|---|---|
| 3M | flip, 2% | £38.74 | 67.9% | −£30.63 |
| 5M | flip, 2% | £53.59 | 51.1% | −£23.20 |
| 15M | flip, 2% | £108.25 | 48.5% | +£1.38 |
| 1H | flip, 2% | £156.48 | 32.3% | +£2.46 |
| **4H** | **flip, 2%** | **£281.21** | **29.7%** | **+£2.38** |

**The best measured outcome is 4H: £100 → £281 over 20 months, about £2.40 a
week, with a 30% drawdown along the way.** And to risk 2% per trade at 0.01 lots
on 4H you need roughly £1,470 — so from £100 you would be risking 29% a trade
and would not survive to collect it.

4H is also the only one that is comfortably tradeable by hand: 152 signals in 624
days is about **two trades a week**, not the all-day phone-watching that 3M
demands.

## How the test was built

- Signals are the indicator's own Long Signal / Short Signal columns.
- Entry on the **next bar's open**, plus half the spread ($0.20) and $0.10
  slippage — you see the marker at the bar close, unlock the phone, and tap.
- Stop wins intrabar ties.
- Ruin floor at £40, roughly the margin for 0.01 lots of gold at 1:100.
- Per-day and per-week figures count only days that actually had a closed trade.

**On the execution model:** using the next bar's open is right on 3M, where it is
a two-minute delay. On 4H it charges you up to four hours of drift for a tap that
really takes seconds, so the 4H numbers are probably pessimistic. That cuts in
your favour, but I have not quantified by how much.

## What limits this

**Three months was only reachable on 1H and 4H.** TradingView caps this account
at ~2,633 bars per timeframe, whatever you scroll:

| timeframe | history available |
|---|---|
| 3M | 7.7 days |
| 5M | 11.5 days |
| 15M | 38.6 days |
| 1H | 161.8 days ✓ |
| 4H | 623.6 days ✓ |

So the 3M and 5M columns are one week each — enough to see an account die, not
enough to characterise an edge. For those two, the earlier backtest on your MT5
M1 export is the better evidence, and it agreed: negative.

**2M could not be tested here at all.** `setResolution('2')` silently falls back
to 3M on this feed, and clicking the toolbar button did the same — so the first
2M numbers I produced in this session were 3M twice. The 2M figures worth using
are the ones from your M1 export (−0.066R), not anything from this chart.

**The 4H result rests on one 20-month sample and 150 trades.** It is the best
thing in this document and also the least replicated. It has not been tested on a
second, independent period, which is the bar the rest of this project uses before
believing anything.

## What follows

1. **£100 is not enough** for any timeframe here. 3M needs ~£170 to risk 2%,
   4H ~£1,470.
2. If the account grows, **4H is the timeframe worth testing**, held to the
   opposite signal, not a fixed target. About two trades a week.
3. **Do not trade 3M or 5M with these signals.** Both are negative on every
   measurement in this session and in the M1-export backtest.
4. Before committing money to the 4H finding, get a second period. Export 4H
   history from MT5 going back further and re-run — the code is in
   `backtester/`.
