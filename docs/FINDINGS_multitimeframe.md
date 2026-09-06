# HTF setup + LTF entry — does dropping to 3M/5M make the trade last?

You wanted the thesis and target from 1H/4H/Daily and the entry refined on
3M/5M, so trades run instead of scratching. I tested exactly that on two
separate periods of TradingView 5M data.

**The mechanism works. The stop placement everyone teaches is the trap. And the
setup I hung it on has no edge, so none of it makes money yet.**

## The one thing that replicated

Same setups, same targets, three stop placements:

**Period A — live chart, Aug 9 – Sep 6 (5,526 bars)**

| setup | variant | n | win% | median R:R | expectancy | median bars held |
|---|---|---|---|---|---|---|
| 1H | HTF entry (baseline) | 120 | 34.2% | 2.11 | −0.029 | 17 |
| 1H | LTF entry + **LTF stop** | 109 | **12.8%** | **7.04** | −0.070 | **3** |
| 1H | LTF entry + **HTF stop** | 109 | **33.0%** | **3.75** | −0.173 | 9 |

**Period B — your Jun 14 – Aug 5 export (7,791 bars)**

| setup | variant | n | win% | median R:R | expectancy | median bars held |
|---|---|---|---|---|---|---|
| 1H | HTF entry (baseline) | 184 | 38.6% | 1.90 | +0.078 | 13 |
| 1H | LTF entry + **LTF stop** | 158 | **12.7%** | **6.94** | −0.252 | **3** |
| 1H | LTF entry + **HTF stop** | 158 | **43.7%** | **3.72** | +0.060 | 5 |

Two independent periods, same shape:

- **LTF entry + LTF stop** — the version every multi-timeframe course teaches —
  gives you the R:R you were promised (**7.0x**, and 13.6x on 4H, 24x on Daily)
  and a **12.7% win rate**, with the median trade dead in **3 bars**.
- **LTF entry + HTF stop** roughly **doubles R:R (1.90 → 3.72) at the same or
  better win rate (38.6% → 43.7%)**.

## Why the tight stop destroys it

Gold's 5M ATR is about **$4.80**. A stop just beyond a 5M swing sits *inside a
single 5M bar's normal range*. So the trade is not stopped out because the idea
was wrong — it is stopped out by noise, before the 1H or 4H thesis has had a
chance to do anything. That is why the median hold collapses to 3 bars and the
win rate goes to 13%, 3%, then 0% as you climb to Daily setups.

**The R:R is real and the probability of reaching the target is not.** At 24:1
on a Daily setup I measured a 0% win rate across 9 trades. The trade never lasts
— it dies in one bar.

**So: use the lower timeframe for the entry PRICE, never for the stop DISTANCE.**
Your stop has to sit outside the noise of the timeframe your idea lives on. That
is the single actionable thing in this document, and it is the opposite of the
usual advice.

## What it does not fix

Every variant above is still roughly break-even or negative, because the HTF
setup I used is the **sweep-and-reclaim (CRT) pattern**, which `FINDINGS_crt.md`
already measured as negative at all six timeframes on 3.7 years of data.

Better entry mechanics on a setup with no edge gives you the same nothing, more
efficiently. The mechanics are worth keeping for when there *is* a setup.

## The data ceiling you should know about

TradingView caps 5M history at about **4 weeks** for this account, whatever you
scroll. That decides what is testable:

| HTF setup | setups available in 4 weeks of 5M |
|---|---|
| 1H | ~120 — usable |
| 4H | **~30** — too thin |
| Daily | **~11** — not testable |
| Monthly | **0** |

**A Daily or Monthly setup with 5M entries cannot be validated from TradingView
data.** Not "is hard to" — cannot. Eleven daily setups is not a sample. If that
is the system you want, you need years of M5 or M1 from MT5, which is the one
export that would unlock it.

## Where I would take this next

1. Keep the structure: HTF for direction and target, **5M for timing only, stop
   at HTF structure.** Worth ~2x on R:R for free.
2. Put it on a setup that has an edge. The only one measured positive in this
   project is the **mean-reversion engine at 5M** (+0.497R). It is not a
   long-hold strategy, but it is the honest starting point.
3. Export **1+ year of M5 from MT5** to make 4H and Daily setups testable at all.
