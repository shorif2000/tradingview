# XAU Regime Scalper — 5m XAUUSD

A regime-switching scalping system for gold, built for **TradingView** and **MetaTrader 5**, plus
an independent Python backtester so you can check either platform against a second implementation.

## What's in the box

| File | What it is |
|---|---|
| `XAU_Regime_Scalper_INDICATOR.pine` | TradingView **indicator** — BUY/SELL markers, SL/TP, liquidity map, reason labels, alerts |
| `XAU_Regime_Scalper_STRATEGY.pine` | TradingView **strategy** — same logic, runs in the Strategy Tester |
| `XAU_Regime_Scalper.mq5` | **MT5 expert advisor** — trades it live or in the MT5 Strategy Tester, and draws the same liquidity map |
| `xau_engine.py` | The strategy re-implemented in Python, matched to Pine's `ta.*` maths |
| `data_io.py` | CSV loader — MT5, MT4, TradingView export, scraped chart tables |
| `run_backtest.py` / `final_report.py` | Run a backtest / build the combined HTML report |
| `analyze.py` | Week-by-week, statistical checks, parameter sensitivity, walk-forward |
| `m5.pkl` / `m1.pkl` / `m5_summer.pkl` | The three loaded datasets, ready to use |
| `validate.py` | 32-check suite proving the engine is correct |
| `gen_strategy.py` | Regenerates the Pine strategy from the indicator so they cannot drift apart |
| `backtest_report.html` | The results on your two data samples |

## How it decides

**1 — Classify the market.** ADX(14) plus Bollinger-width percentile decide TREND, RANGE, or
stand aside. Thresholds have hysteresis (enter trend above ADX 23, only leave below 18) so the
regime doesn't flicker bar to bar.

**2 — Three modules, highest priority first.**

- **Liquidity sweep.** Price runs the stops beyond a swing level and closes straight back —
  a failed breakout. Trade against the spike.
- **Trend pullback.** In a trending regime, buy dips into the EMA20 zone with the 1-hour trend agreeing.
- **Range fade.** In a compressed regime, fade failed Bollinger-band breakouts at range extremes.

**3 — Score the reasons.** Nothing fires on a single condition. Each candidate collects
independent reasons — swept level reclaimed, engulfing candle, pin bar, RSI reclaiming 50, higher
low, +DI expanding, divergence — and needs at least 2. Those reasons are printed on the chart and
in every alert, so each signal explains itself. A tie between long and short is **skipped**, not
resolved arbitrarily.

**4 — Stop and target.** Stop goes beyond structure — the 8-bar swing, the rejection wick, or the
wick that took the liquidity — padded by 0.35 × ATR, floored at 0.8 × ATR and capped at 2.0 × ATR.
If structure sits further away than the cap, the trade is skipped rather than taken with oversized
risk. Target is a fixed 2 × risk.

**Guardrails:** session 07:00–20:00 UK only, nothing after Friday 18:00, ATR must sit inside a
volatility band (skips the dead Asian session and news spikes), one position at a time, max 6
trades/day, £6 daily loss cap, 60-bar time stop.

## BSL and SSL — the liquidity map

**BSL (buy-side liquidity)** sits *above* swing highs: that's where shorts keep their stop-losses
and breakout traders keep buy-stops. **SSL (sell-side liquidity)** sits *below* swing lows for the
mirror reason. Price is drawn to these pools because that's where the resting orders are.

The tradable event isn't the pool, it's the **sweep**: price spikes through, fills those orders,
and immediately closes back. Both scripts draw every live pool as a horizontal line labelled with
its touch count (`BSL ×2`), turn it gold and mark it `swept` when it gets raided, and delete it
when price breaks through properly rather than reversing.

Touch count matters. A level tagged twice — "equal highs" — holds more resting orders than a
single swing, so `Sweep needs at least N touches` defaults to 2. One subtlety worth knowing: a
poke smaller than the equal-level tolerance that closes back counts as another **touch** rather
than consuming the pool. Without that rule a second high one tick above the first destroys the
pool before its pivot even confirms, and equal highs can never form.

## Install — TradingView

1. Open a **5-minute XAUUSD** chart (`VANTAGE:XAUUSD`).
2. Pine Editor → paste the INDICATOR file → Save → Add to chart.
3. For backtesting, second Pine Editor tab → paste the STRATEGY file → add that too.
4. **Set your real costs** in the strategy's Properties tab. Your MT5 export showed a spread of
   19–20 points, so 20 ticks of slippage is about right.
5. Alerts: right-click → Add alert → Condition = *XAU Regime Scalper 5M [Signals]* →
   *Any alert() function call* → **Once per bar close**.

TradingView caps 5-minute history at roughly 5,000 bars on free plans, 10,000 on Essential/Plus
and 20,000 on Premium. Six months of 5m gold is about 37,000 bars, so the Strategy Tester can't
cover a long sample on its own — that's what the Python backtester is for.

## Install — MetaTrader 5

1. MT5 → File → **Open Data Folder** → `MQL5/Experts/` → drop `XAU_Regime_Scalper.mq5` in.
2. MetaEditor → open it → **Compile** (F7). It should compile with no errors.
3. Drag it onto a **5-minute XAUUSD** chart. Enable **Algo Trading**.
4. **Set `InpServerGmtOffset` to your server's offset from UTC.** Vantage runs UTC+2 in winter and
   UTC+3 in summer. This one input decides whether the session filter lands on the right hours —
   see the warning below.
5. To backtest: Strategy Tester → select the EA → M5 → **Every tick based on real ticks** if you
   have it, since the strategy depends on which of the stop and target is hit first.

The EA draws the liquidity map, signal arrows with their reasons, SL/TP lines and a status panel,
so you don't need a separate indicator on the MT5 side.

## Run the Python backtest

```bash
pip install pandas numpy
python3 run_backtest.py --csv XAUUSD_M5.csv --assume-tz Etc/GMT-2
python3 validate.py          # 32 correctness checks
python3 analyze.py           # week-by-week, sensitivity, walk-forward
```

### The timezone trap — read this one

MT5 exports timestamps in **broker server time**, not UTC, and getting it wrong silently shifts
every session filter by an hour. You can verify it from the data itself rather than guessing:
gold has a one-hour daily break at **22:00–23:00 UTC in winter** (17:00–18:00 New York). Load the
file, find the missing hour, and pick the offset that puts the gap on 22.

For your January file that offset was **UTC+2** (`Etc/GMT-2`), not the +3 I first assumed.
Note the sign inversion in that notation is correct: `Etc/GMT-2` means UTC+2.

## Everything is a switch

Both Pine files and the MQL5 EA expose the same three tiers of control, and the Python `Config`
uses identical names so a setting means the same thing everywhere.

**Modules — what is allowed to trade.** Liquidity sweep, trend pullback, range fade. Turn one off
and it stops producing signals entirely.

**Confirmations — what may score a point.** EMA reclaim, engulfing candle, pin bar, RSI 50 cross,
higher low / lower high, DI expansion, fast-RSI extreme, divergence, failed Bollinger breakout,
range floor/ceiling tag, swept-level reclaim, right side of the fast EMA, and whether a sweep
counts inside the range module. Switch one off and it can no longer contribute to any module's
score — and because the on-chart reason label is built from the same list, the label always tells
you which rules are actually live.

**Filters and guardrails.** Session window, volatility band, higher-timeframe agreement, daily
trade and loss caps, time stop, break-even. All individually switchable.

Every switch was verified by running the backtest with it off and confirming its reason text
disappears from all signals — a toggle can leave the trade *count* unchanged while still removing
a reason, so counting trades alone would not have proved it.

## What the backtest actually found

Two samples, about 10 weeks in total, deliberately different: **2–20 Jan on M5** from your MT5
export (real per-bar spread, stop-vs-target order resolved from the M1 file) during a +9.2% rally,
and **14 Jun – 5 Aug on M5** from your TradingView export during a −1.6% choppy drift.

With the shipped defaults: **149 trades, 44.3% win rate, +0.291R expectancy**, 95% CI
+0.055R to +0.531R, which excludes zero.

**That last number is flattering and you should discount it.** The module selection — running with
the trend module off — was chosen by looking at these same samples. Before that choice, with all
three modules on, the same data gives **+0.215R over 166 trades with a CI of −0.004 to +0.440R**,
which still touches zero. Picking the best of five variants and then quoting its confidence
interval is precisely the bias that makes weekly tuning useless. Treat the pre-selection number as
the trustworthy one and the post-selection number as a hypothesis for the next batch of data.

**Why the trend module is off by default.** It produced roughly zero expectancy in *both* samples
(−0.06R and −0.04R) while range-fade carried both (+0.34R and +0.42R) and liquidity-sweep was
mildly positive in both (+0.19R and +0.12R). Two independent periods with opposite market
direction agreeing on sign is a much stronger signal than a parameter that scores well once.
Turning it off also cut Sample A's drawdown from 22% to 15%. It's a one-click toggle, so if your
own testing disagrees, put it back.

**Tuning still doesn't earn its keep.** Refitting weekly on earlier data gave +0.506R
out-of-sample against +0.579R for leaving the defaults alone. Both positive, so this is a weaker
finding than before — but tuning didn't beat doing nothing, and it leaves you holding a fitted
parameter set that may not survive the next regime.

**The number that should worry you is drawdown: 41% of peak equity in Sample B.** On £100 at 0.01
lots that isn't a statistic, it's most of the account. Sizing, not signal quality, is the binding
constraint. A £500–1,000 account makes 0.01 lots sane; £100 does not.

### Timezone — verify it, don't assume it

Getting this wrong silently shifts every session filter by hours, and the two export types differ:

| Source | Timestamps in | Pass to the loader |
|---|---|---|
| Your MT5 export | broker server time, **UTC+2** in January | `--assume-tz Etc/GMT-2` |
| Your TradingView export | **UTC** | `--assume-tz UTC` |

You can verify it from the data instead of trusting either: gold has a one-hour daily break at
**22:00–23:00 UTC in winter** and **21:00–22:00 UTC in summer** (17:00–18:00 New York). Load the
file, find the missing hour, and pick the offset that puts the gap where it belongs. Note that in
`Etc/GMT-2` the sign is inverted by design — it means UTC+2.

In MT5, set `InpServerGmtOffset` to the same offset. Vantage runs UTC+2 in winter, UTC+3 in summer.

### To settle the question

Export **6+ months of M5 or M1** from MT5 (View → Symbols → XAUUSD → Bars tab → set the date range
→ Export Bars). At this effect size roughly 180–200 trades decides it, and six months gives
300–400. Everything is already wired: drop the file in and run `run_backtest.py`.

## Read this before trading it

**0.01 lot on a £100 account is aggressive.** A typical 5m gold stop here is $3–6, which is
£2.40–£4.70 — **2–4% of a £100 account per trade** — and 0.01 is the smallest lot most brokers
allow, so you cannot risk less. Drawdown reached **41% of peak equity** in the June–August sample.
Five or six losses in a row is entirely normal for a 2R system winning ~44% of the time, and at
this sizing that is a third of the account gone.

**Costs are not small at this size.** A $0.20 spread against a $3 stop is about 7% of your risk on
every single trade, before slippage.

Any backtest is the optimistic case. Live trading adds requotes, wider spreads at news, and
slippage through stops on gaps. Trade it on demo until you've seen enough signals to judge it
yourself — and given what the statistics above say, that is the honest recommendation rather than
a disclaimer.
