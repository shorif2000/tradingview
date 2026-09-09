# AGENTS.md — machine-readable project context

Single handoff document for any agent or person picking this repo up cold.
Everything here is a **measured fact or a decision with its reason**, not a plan.
Changing anything under [§3 Invariants](#3-invariants) changes a _result_, not a
style choice.

`CLAUDE.md` is a pointer to this file. Keep one context document, not two — two
drift apart, and the second one to drift is the one that misleads.

**Read order:** this file → `README.md` → `docs/HOW_TO_TRADE_IT.md` →
`backtester/validate.py`.

---

## 1. What this is

A regime-switching **scalping system for XAUUSD (gold)** on 2m/3m/5m, implemented
**four times** so each implementation can be cross-checked against the others.

| Surface               | File                                     | Role                                                                                                                         |
| --------------------- | ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| TradingView indicator | `pine/XAU_Regime_Scalper_INDICATOR.pine` | **Hand-maintained source of truth.** Live signals, alerts, all drawing. ~1393 lines                                          |
| TradingView strategy  | `pine/XAU_Regime_Scalper_STRATEGY.pine`  | **Generated** — never hand-edit. 1507 lines                                                                                  |
| TradingView variants  | `pine/variants/*.pine`                   | **Generated** single-purpose cuts (different default toggles/UI, same engine). Never hand-edit                               |
| MT5 expert advisor    | `mql5/XAU_Regime_Scalper.mq5`            | Hand-maintained port. Live trading / MT5 Strategy Tester. 981 lines, ASCII-only, 89 inputs                                   |
| Python backtester     | `backtester/xau_engine.py`               | Hand-maintained, maths matched to Pine `ta.*`. The only place results are measured — long history, walk-forward, sensitivity |

| TradingView indicator | `pine/XAU_5_Liquidity_Engine.pine` | **Hand-maintained, standalone.** Standalone liquidity-level and resting-order tool. Not generated, not part of the measured system |

**The rule that matters most:** `XAU_Regime_Scalper_INDICATOR.pine` is the only
hand-edited Pine file **in the measured system**. Edit a generated file and the edit is silently lost on the
next generator run, and that file drifts from the indicator it is supposed to
match. When you change indicator logic, check whether `mql5/XAU_Regime_Scalper.mq5`
and `backtester/xau_engine.py` need the equivalent change — **the four are meant to
agree, and disagreement is treated as a bug until proven otherwise.** That is what
`validate.py` and the two real-data samples exist for.

### The indicator is a deliberate exception to the no-drift rule

`XAU_5_Liquidity_Engine.pine` carries its own copy of the range-fade and
liquidity-sweep triggers so its "Mean reversion" engine can run without the
master. That is duplication, and duplication drifts — the two will disagree the
first time the master's entry logic changes and nobody remembers to mirror it.

It is accepted here because this indicator's job is to be a standalone
liquidity tool, not a fifth view of the measured system, and folding it into the
master would have meant bending the master's UI around a design that is not ours.
The cost is real though: **if you change entry logic in the master, check the
standalone by hand.** If the indicator ever becomes something you actually trade,
promote it into the master as a `scriptMode` and delete the standalone.

Nothing in the indicator has been backtested. Its default engine is trend-following,
which §7 records as the thing that consistently did not work on this instrument.

### Operator context (this shapes design decisions)

- Trades **XAUUSD via Vantage**, swap-free account.
- Reads signals on **TradingView**, places orders **manually on mobile MT5**.
  Multi-second human delay between signal and fill, measured to cost **~85% of
  the edge** ([§6](#6-hard-findings)).
- Sizing context: **£100 start**, 0.01 or 0.02 lots.
- Stated goals were "90% win rate" and "90%+ PnL". **Neither is achievable on this
  data.** Do not tune toward them — see [§7](#7-things-that-do-not-work).
- Get data from Trading view. browse to site select the required timeframe. right click and switch to table view. then extract the data by scrolling down. same for all other timeframes. !m/3M/5M etc.

---

## 2. Layout and commands

```
pine/
  XAU_Regime_Scalper_INDICATOR.pine     master — edit THIS
  XAU_Regime_Scalper_STRATEGY.pine      generated
  XAU_5_Liquidity_Engine.pine       HAND-MAINTAINED, standalone — see §1
  variants/
    XAU_1_MeanReversion_Scalper.pine    generated — the earner
    XAU_2_Liquidity_Map.pine            generated — context only, zero signals
    XAU_3_Trend_Pullback.pine           generated — UNPROFITABLE, quarantined
    XAU_4_Roadmap.pine                  generated — destinations, never direction
mql5/XAU_Regime_Scalper.mq5
backtester/                             see the table below
data/                                   the samples every number was measured on
docs/
  HOW_TO_TRADE_IT.md                    settings + the evidence for each
  FINDINGS_exit_and_sessions.md         exit-mode and session-filter results
reports/                                build artefacts, gitignored
.cache/                                 parsed-data cache, gitignored
```

### Commands

All scripts resolve paths relative to the repo root via `backtester/paths.py`, so
**they work from any working directory**:

```bash
pip install pandas numpy

# engine self-check — run after ANY change to xau_engine.py. 32 checks, all must pass
python3 backtester/validate.py

# backtest a shipped sample (timezone matters — see below)
python3 backtester/run_backtest.py --csv data/XAUUSD_M5_jan2026_mt5.csv --assume-tz Etc/GMT-2

# engine correctness on synthetic bars, no real data needed
python3 backtester/run_backtest.py --synth

# the headline multi-sample report
python3 backtester/final_report.py

# week-by-week, sensitivity, walk-forward
python3 backtester/analyze.py

# direction quality vs exit-geometry quality
python3 backtester/signal_accuracy.py
```

Outputs land in `reports/`. Override with `XAU_REPORT_DIR`; override the parsed-data
cache with `XAU_CACHE_DIR`.

### Regenerating Pine

```bash
python3 backtester/gen_strategy.py     # -> pine/XAU_Regime_Scalper_STRATEGY.pine
python3 backtester/gen_variants.py     # -> pine/variants/*.pine
python3 backtester/validate.py         # must pass before committing
```

Run both after any edit to the master indicator. `gen_strategy.py` **asserts each
text block it expects to find is still present**, so renaming or restructuring
something a transform depends on fails loudly rather than drifting silently.

Generation exists so the strategy and the four variants **cannot** drift from the
indicator. Three separately-edited copies means a bug fixed in one survives in the
other two.

### `backtester/` file map

| File                            | What it does                                                                                                                                                                                                                                                                     |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `xau_engine.py`                 | Strategy logic, ~1600 lines. Pine-exact. See [§4](#4-architecture) for internal order                                                                                                                                                                                            |
| `paths.py`                      | Repo-relative paths + `dataset()` loader. Everything else imports from here                                                                                                                                                                                                      |
| `samples.py`                    | The two measured periods (`samples()`), the resample helper, and the bootstrap (`boot()`). Eleven scripts each carried their own copy of this preamble with the CSV filenames and timezones hardcoded, which only worked from the repo root and skipped `dataset()`'s bar-resolution check|
| `data_io.py`                    | Tolerant OHLC loader — TradingView/MT5/MT4 quirks: tabs inside a comma-separated header, thousands separators in quoted numbers, headerless MT4 files, reverse chronological order, null glyphs. Resamples to 5m unless told not to. Entry points `load_ohlc()` and `describe()` |
| `run_backtest.py`               | Single run against a CSV or synthetic bars                                                                                                                                                                                                                                       |
| `validate.py`                   | 32 invariant checks against synthetic bars: fills land in the triggering bar, R-multiples match configured RR, **stop wins ties**, guardrails bind, no lookahead, ruin handling                                                                                                  |
| `make_synth.py`                 | Structurally-realistic (**not** statistically-real) synthetic 5m bars, for engine validation only. **Never quote its performance numbers as edge**                                                                                                                               |
| `analyze.py`                    | Week-by-week, parameter sensitivity, walk-forward                                                                                                                                                                                                                                |
| `signal_accuracy.py`            | Separates _direction_ quality (did price move the right way at all) from _exit-geometry_ quality (did the R-multiple capture it), using M1 to resolve which of +1R/−1R came first                                                                                                |
| `report.py` / `final_report.py` | Self-contained HTML reports (equity curve, cost sensitivity, walk-forward). `final_report.py` is specific to the two named real samples                                                                                                                                          |
| `gen_strategy.py`               | Indicator → strategy, 13 transforms                                                                                                                                                                                                                                              |
| `gen_variants.py`               | Indicator → 4 variants, defaults only                                                                                                                                                                                                                                            |
| `anticipation.py`               | The anticipation-entry study. One parameterised `run()` plus four CLI studies (`compare`, `outliers`, `grid`, `minr`, `all`). **Replaced `predict.py` and `predict5/6/7/8/10.py`** — seven files that each re-implemented the same trade loop with one parameter changed         |
| `target.py`                     | The supplied 80% / +0.20R target, tested at £500. Studies `rules`, `flips`, `cost`, `fix`, `money`, `all`. **Replaced `target80.py`, `target500.py`, `target_fix.py`**                                                                                                           |

`analyze.py` slices per-week numbers from **one full-sample backtest**, never by
re-running the engine per week. Re-running per slice would throw away the ~215-bar
warm-up (EMA200 + BB-width percentile) and silently change signals near every
boundary, making the weeks incomparable.

### Multi-timeframe entries — the one mechanic that replicated

Use the lower timeframe for the entry PRICE, never for the stop DISTANCE. Keeping
the stop at HTF structure while refining the entry on 5M roughly **doubles median
R:R (1.90 → 3.72) at an equal or better win rate (38.6% → 43.7%)**, in both test
periods. Moving the stop down to LTF structure destroys it (see invariant list
item 12). This is mechanics, not edge — it does not rescue a setup that has none.

### Datasets

`paths.dataset(name)` loads from `data/` and caches the parsed frame under
`.cache/`. Pickles are a **cache, never a source of truth** — delete them freely.

| Name        | File                                    | TZ          | Resampled to 5m  |
| ----------- | --------------------------------------- | ----------- | ---------------- |
| `m5`        | `XAUUSD_M5_jan2026_mt5.csv`             | `Etc/GMT-2` | yes              |
| `m1`        | `XAUUSD_M1_jan2026_mt5.csv`             | `Etc/GMT-2` | **no** — see I16 |
| `m5_summer` | `XAUUSD_M5_jun-aug2026_tradingview.csv` | `UTC`       | yes              |
| `h1`        | `XAUUSD_H1_tradingview.csv`             | `UTC`       | no               |
| `h4`        | `XAUUSD_H4_tradingview.csv`             | `UTC`       | no               |

Sample naming used throughout `docs/`: **Sample A** = January MT5 export (+9.2%
rally, real per-bar spread, M1 available). **Sample B** = June–August TradingView
export (−1.6% choppy drift).

### Timezone — always verify, never assume

MT5 exports are in **broker server time** (Vantage: UTC+2 winter / UTC+3 summer).
TradingView exports are **UTC**. Getting `--assume-tz` wrong shifts every session
filter by hours **without erroring**.

Verify from the data itself: gold has a one-hour daily break at **22:00–23:00 UTC
in winter**, 21:00–22:00 in summer (17:00–18:00 New York). Load the file, find the
missing hour, pick the offset that puts the gap there. `Etc/GMT-2` means UTC+2 —
the sign inversion is POSIX convention, not a typo. An early run in this project
was 2h-shifted because UTC+3 was assumed.

---

## 3. Invariants

Do not change these without re-measuring and updating the numbers in `README.md`,
`docs/HOW_TO_TRADE_IT.md` and this file.

| #   | Invariant                                                                                       | The failure it prevents                                                                                                                                                                                                                                |
| --- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| I1  | `tfK = max(5.0 / tfMin, 1.0)` — **clamped at 1.0**                                              | Unclamped, a 1h chart got EMA 2/4/17, pivot 2, ATR ×0.29 and an impulse threshold of $5.75 instead of $19.86 → 286 spurious order blocks (119 after the fix)                                                                                           |
| I2  | Strategy SL/TP reset guarded by `if strategy.position_size == 0 and not goLong and not goShort` | `strategy.position_size` is 0 on the entry bar, so the naive guard wiped SL/TP the same bar it set them                                                                                                                                                |
| I3  | Python EMA uses `_seeded_ewm` with an SMA seed                                                  | `pandas.ewm` differs from Pine `ta.ema` for the first `len` bars; unseeded, the port diverges                                                                                                                                                          |
| I4  | Percentages computed as `100.0 * wins / tot`                                                    | Integer division silently returned 0                                                                                                                                                                                                                   |
| I5  | SMC block declared **above** the limit-entry block                                              | `obBuyTop` / `obSellBot` used before declaration                                                                                                                                                                                                       |
| I6  | Zone/box cosmetics run under `barstate.islast`; state updates run every bar                     | Redrawing zones on every historical bar froze the browser tab                                                                                                                                                                                          |
| I7  | Reason labels capped at `maxReasonLbl` (default 2), oldest shifted off                          | Labels overlapped into unreadable congestion                                                                                                                                                                                                           |
| I8  | MTF bias uses EMA **20/50** and masks NaN to 0 (unknown)                                        | `EMA50 > EMA200` with NaN evaluates False, so "no history" was reported as "downtrend"                                                                                                                                                                 |
| I9  | Volume-imbalance boxes skip their creation bar via `box.get_left(...) < bar_index - 1`          | Otherwise the box fills on the bar that created it                                                                                                                                                                                                     |
| I10 | Pine ternaries wrapped at **18 spaces max**                                                     | A 36-space continuation indent is a hard Pine compile error                                                                                                                                                                                            |
| I11 | Input group constants unique (`gRM` for Roadmap, not `gR`)                                      | Duplicate `gR` between Regime and Roadmap = compile error. When renaming, catch **both** `group=gR` and `group = gR,` forms                                                                                                                            |
| I12 | One indicator handles all four jobs via the `scriptMode` dropdown                               | A 4-script split hits TradingView's "maximum number of studies per chart"                                                                                                                                                                              |
| I13 | Intrabar order resolved from **M1**, **stop wins ties**                                         | A 2R system's result is decided entirely by which of SL/TP is touched first                                                                                                                                                                            |
| I14 | Spread from the MT5 `<SPREAD>` column, bid-price assumption                                     | $0.20 spread against a $3 stop is ~7% of risk per trade                                                                                                                                                                                                |
| I15 | Ruin and margin modelled explicitly                                                             | An early run drove the account to **−£121**, not a possible outcome                                                                                                                                                                                    |
| I16 | `dataset("m1")` loads with `resample_5m=False`, and `_check_step` asserts the modal bar spacing | The M1 file resampled to 5m is just a second copy of the M5 file, which **silently disables I13** while still producing plausible-looking results                                                                                                      |
| I17 | Derived files (`*.clean.csv`, pickles, reports) go to `.cache/` and `reports/`                  | `_preclean` used to write beside the source, leaving junk inside `data/`                                                                                                                                                                               |
| I18 | `Config.tf_minutes` set when running a non-5m chart                                             | Bar-count settings rescale to preserve wall-clock span and ATR sizing converts via `sqrt(time)`; without it, other-timeframe backtests run distorted lookback windows                                                                                  |
| I19 | A limit-order fill resolves from the **next** bar, never its own                                | The order fills part way through the candle, so the rest of that candle's range is unknowable at bar resolution — awarding it lets a wide bar hand the test whichever of SL/TP suits. Market-on-open entries are exempt: the fill _is_ that bar's open |
| I20 | Every stop has a **minimum placeable distance** (0.50 × ATR) before R is computed               | A structural stop can land cents from the fill; risk divides to near zero and R multiples explode. This alone turned +0.02R into a fake +0.972R. Check `t.rr.max()` — a three-figure R:R means this was broken                                         |

---

## 4. Architecture

### The four-stage decision pipeline (implemented four times, kept in sync)

**1 — Classify the regime.** ADX(14) + Bollinger-width percentile → TREND, RANGE or
stand aside, with **hysteresis**: enter TREND above ADX 23, leave only below 18, so
it cannot flicker bar to bar.

**2 — Modules, in priority order:** liquidity sweep > trend pullback > range fade.
Each is independently switchable and produces its own reason strings.

| Module                    | Trigger                                                                                          | Status                                                               |
| ------------------------- | ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| **Range fade**            | Price pokes outside a Bollinger band at a range extreme and closes back inside (failed breakout) | **ON** — carries the system                                          |
| **Liquidity sweep**       | Price runs stops beyond a swing level and closes straight back (failed stop raid)                | **ON** — complementary to range fade                                 |
| **Trend pullback**        | Dip into the EMA20 zone with H1 trend agreeing                                                   | **OFF** — loses money                                                |
| **Breakout continuation** | Continuation after a range break                                                                 | **OFF** — Python only (`use_breakout_module`), never wired into Pine |

Range and sweep are kept **together** because together they beat either alone on
both expectancy _and_ drawdown. Trend and breakout are **quarantined in variant 3**
because bolting them on drags the pair from +0.368R to +0.198R.

**3 — Score confirmations.** Each candidate needs ≥2 independent reasons (swept-level
reclaim, engulfing candle, pin bar, RSI reclaiming 50, higher low, +DI expansion,
divergence, …). Nothing fires on a single condition, and **a long/short tie is
skipped, not resolved arbitrarily**. The on-chart and alert reason text is generated
from the _same list_ used to score, so it cannot drift from what actually fired.

> **Counter-intuitive but measured:** adding confirmations _reduces_ expectancy,
> because more routes to the score minimum let weaker setups through.
> SMC votes: +0.29R → +0.06R. Reversal votes: +0.37R → +0.23R.
> **Do not "improve" this by adding confirmations.**

**4 — Stop and target.** Stop beyond the structure that caused the signal (8-bar
swing / rejection wick / liquidity wick), padded 0.35 × ATR, floored 0.8 × ATR,
capped 2.0 × ATR. **If structure sits further than the cap, the trade is skipped**
rather than taken oversized. Target is a multiple of risk (`rr`, default 2R);
`exit_mode` (`fixed` / `staged` / `partial`) controls what happens to the stop and
position size as price moves in favour — exact mechanics in `Config`.

### The liquidity map (BSL/SSL) — shared across all four implementations

**BSL** (buy-side liquidity, above swing highs) and **SSL** (below swing lows) are
pools of resting stop orders. The tradable event is the **sweep**: price spikes
through, fills them, closes straight back — trade _against_ the spike.

All implementations draw every live pool, tag its touch count (`BSL ×2`), turn it
gold and mark it `swept` on a raid, and delete it on a clean break-through.

One subtlety that matters: **a poke smaller than the equal-level tolerance that
closes back counts as another touch on the same pool, not a consumption of it.**
Without that rule a second high one tick above the first destroys the pool before
its pivot even confirms, and equal highs can never form.

### SMC layer

Order blocks (translucent **blue** = buy, **red** = sell), breaker blocks (yellow),
volume imbalance (light blue, close-to-open **body** gap — distinct from a
wick-to-wick FVG). FVG/IFVG were **removed on request**; the operator has other
scripts for those.

Zone rules: a minimum confluence count to be drawn at all; `HIGH RISK` plus a
dotted thin border when a zone only just clears the minimum; untouched zones extend
across the chart; visited zones freeze and grey out unless strong; hover shows exact
high/low and the confluence list.

### Control surface — three tiers, named identically everywhere

Pine, MQL5 and the Python `Config` dataclass use **matching names** for the same
setting, so a setting means the same thing on every surface.

- **Modules** — what may trade at all. Off = zero signals from that module.
- **Confirmations** — what may contribute a scoring point. Off = cannot score, and
  disappears from the reason label (same source list).
- **Filters / guardrails** — session window, volatility band, HTF agreement, daily
  trade and loss caps, time stop, break-even. All individually switchable.

When adding a confirmation or filter, wire it into **all four** implementations under
the same name, and add it to the reason-label source list — not as a side effect
alongside it.

### UI gating

Two orthogonal mechanisms:

```pine
scriptMode = "Scalper" | "Liquidity map" | "Roadmap" | "Everything" | "Custom"
f_mode(userFlag, onInThisMode) => modeCust ? userFlag : onInThisMode
// 18 effective display flags, e.g.
eShowOB = f_mode(showOB, modeMap or modeAll)

uiPreset = "Beginner" | "Standard" | "Full" | "Custom"
f_show(userFlag, needRank)
```

16 input groups, numbered ⓪–⑯, no duplicate group constants.

### `xau_engine.py` internal order

Pine-equivalent primitives (`ema`, `rma`, `atr`, `rsi`, `dmi`, `percentrank`,
`pivot_high/low`, `bars_since`) → `Config` (every tunable, heavily commented, the
single source of truth for defaults) → `Trade` → `build_liquidity` (BSL/SSL pool
tracking) → `build_smc` (order blocks, BOS/CHoCH) → `attach_htf_bias` →
`build_features` → `score_*` per module and direction → `backtest()` (bar-by-bar
loop, fills, guardrails, exit modes) → `stats()`.

### Roadmap module

Calibrated logistic on which liquidity level is reached first:

```
p = 1 / (1 + exp(-(2.2929 - 4.6045 * ratio)))
```

9,994 observations, **Brier 0.197** vs 0.25 for guessing. Median resolution 9 bars
(~45 min on 5m). Volatility cone at **0.96** and **2.19** × ATR × √bars for the
68%/95% bands — constants that held across both samples and every horizon from 6 to
48 bars.

**The roadmap never calls direction.** It maps destinations and spread only.

---

## 5. Backtest realism model

- Bid-price assumption; spread from the MT5 `<SPREAD>` column
- M1-resolved intrabar fill ordering, **pessimistic SL-first tie-break**
- Lot-step rounding at 0.01 granularity (partial scale-out needs ≥ 0.03 lots)
- Margin and ruin modelling
- Statistics: bootstrap CIs, Wilson intervals, Brier score, permutation tests,
  walk-forward, MFE/MAE, R-multiples

**Regression check.** `python3 backtester/final_report.py` must reproduce:

```
pooled 149 trades | 44.3% WR | +0.291R | CI +0.055 to +0.530 | P(no edge) 0.80%
  sample A:  47 trades, 51.1% WR, £+70.76, +0.485R, DD 15.1%
  sample B: 102 trades, 41.2% WR, £+118.99, +0.202R, DD 41.3%
```

If a refactor changes those numbers, it changed behaviour. Investigate before
committing.

---

## 6. Hard findings

Measured on 2M Jan + 5M Jan + 5M Jun–Aug, **0.02 lots, half off at 1R, swing trail**:

| Configuration              | Trades  | Green     | Expectancy  | Net       | Max DD  |
| -------------------------- | ------- | --------- | ----------- | --------- | ------- |
| **Range + Sweep together** | **151** | **57.0%** | **+0.368R** | **+£384** | **14%** |
| Range fade alone           | 141     | 56.0%     | +0.321R     | +£353     | 48%     |
| Liquidity sweep alone      | 63      | 54.0%     | +0.314R     | +£92      | 24%     |
| Trend pullback alone       | 63      | 44.4%     | −0.093R     | −£68      | 75%     |
| Breakout alone             | 49      | 40.8%     | −0.076R     | −£21      | 67%     |

Exit plans, pooled across all three samples:

| Plan                              | Trades  | Green     | Expectancy  | Max DD  |
| --------------------------------- | ------- | --------- | ----------- | ------- |
| 0.01, fixed 2R                    | 207     | 41.5%     | +0.216R     | 41%     |
| 0.01, 3R + swing trail            | 199     | 38.7%     | +0.267R     | 31%     |
| 0.02, fixed 2R                    | 154     | 42.9%     | +0.252R     | 41%     |
| 0.02, half at 1R then 3R          | 152     | 36.2%     | +0.241R     | 44%     |
| **0.02, half at 1R, rest trails** | **151** | **57.0%** | **+0.368R** | **14%** |
| 0.02, half at 1R + break-even     | 163     | 52.8%     | +0.157R     | 41%     |

Per timeframe on the winning plan:

| Sample         | Green | Expectancy | Net   | DD  |
| -------------- | ----- | ---------- | ----- | --- |
| 2M January     | 50.0% | +0.268R    | +£53  | 36% |
| 5M January     | 61.5% | +0.259R    | +£61  | 29% |
| 5M June–August | 59.1% | +0.502R    | +£270 | 14% |

### Directional predictors — replication test

At every bar: is the nearest liquidity **above** taken before the nearest **below**?

| Predictor                             | Sample A  | Sample B  | Verdict                             |
| ------------------------------------- | --------- | --------- | ----------------------------------- |
| **Proximity** (which level is closer) | **86.9%** | **86.4%** | **replicates — the only real edge** |
| H1 trend up                           | 54.8%     | 43.1%     | flipped sign — spurious             |
| Fresh SSL sweep                       | 61.6%     | 38.4%     | flipped sign — spurious             |
| Regime = RANGE                        | 58.9%     | 46.2%     | flipped sign — spurious             |

**Only proximity forecasts direction.** Trend, regime and sweep state are worthless
for it — they looked predictive in one sample and inverted in the other, which is
exactly what a spurious pattern does. None of them feed the roadmap script.

### Other measured facts

- **Break-even stops cost money**: +0.291R → +0.175R (~0.12R/trade). Gold routinely
  retraces through entry before continuing. Leave the stop alone until at least +1R.
  Do not add a break-even feature without re-measuring on **both** samples.
- **The session filter is load-bearing**: 07:00–20:00 London. Going 24h costs **92%**
  of the edge — the Asian session chops without follow-through.
- **Weekly re-tuning does not pay**: refit weekly gave +0.506R out-of-sample vs
  **+0.579R for leaving the defaults alone**.
- **Manual mobile execution costs ~85% of the edge** against instant fills.
- **Selection bias is real.** With all three modules on (pre-selection), Samples A+B
  give **+0.215R over 166 trades, CI −0.004 to +0.440R** — touching zero. The
  +0.291R headline is _post_-selection. Treat the pre-selection number as the
  trustworthy one and the post-selection one as a hypothesis for new data.
- **The bar for trusting any change** is "opposite market direction, same sign of
  result". Justify a change against **both** samples in `data/`, never one.

### Anticipating a level beats confirming it — the one plateau found

The strongest result in the project, and the only one whose _neighbourhood_ also
works. Rest a limit **0.25 × ATR beyond** an untouched swing, stop at the last
swing beyond it (floored at **0.50 × ATR**, skip beyond 2.5 × ATR), target the
extreme of the last 6 closed 1H bars, skip if that target is more than **6R**
away. Against the confirmation entry on identical levels, stops and targets:

|                             | CONFIRM               | ANTICIPATE               |
| --------------------------- | --------------------- | ------------------------ |
| Expectancy                  | +0.222R               | **+0.523R**              |
| 95% CI / P(no edge)         | [−0.11,+0.58] / 10.2% | **[+0.13,+0.93] / 0.3%** |
| minus 3 best trades         | +0.082R               | **+0.392R**              |
| Median stop / time in trade | $6.25 / 60 min        | **$5.22 / 30 min**       |
| Max DD at 0.01 lots         | −£85.63               | **−£39.54**              |

27-cell neighbourhood grid: **25/27 positive in both periods (93%)** against the
~25% noise baseline, median +0.253R. Breaks at `swingLen` 7 (+0.114R) and goes
negative at swingLen 7 with a 4H target. Long/short balanced (+0.473 / +0.576).
`docs/FINDINGS_anticipation.md`, `backtester/anticipation.py` (run
`python3 backtester/anticipation.py all`).

**Two artifacts were removed to get here, both of which looked better:**

- _Intrabar look-ahead_ — a limit fills mid-candle, so resolution must start on
  the NEXT bar. The tell was "median time in trade 0 min". Fixing it dropped a
  robustness grid from 72% to 16%, i.e. below noise.
- _Division by near-zero_ — a structural stop landing cents from the fill scored
  small wins at 1,424R and 6,085R, producing a fake **+0.972R** (median outcome
  −1.00R; 70% of gross profit from the best 5%; −0.240R trimmed). The stop floor
  is what makes it honest: it took +0.972R to +0.02R, and the +0.523R above is
  the capped-target version measured _with_ the floor in place.

---

## 7. Things that do not work

Do not re-attempt without new evidence. Each was tested and failed.

1. **Trading with the trend on short-horizon gold.** Three independent attempts:
   trend pullback (−0.09R), H1 trend gating (+0.485R fell to +0.117R), breakout
   continuation (−0.08R). Consistent across regimes and timeframes. At a 20-cent
   spread there is not enough left in a continuation move to pay for the entry.
   **Short-horizon gold mean-reverts.**
2. **Adding confirmations to raise win rate.** It lowers expectancy — see §4.
3. **Break-even stops.** −0.12R per trade.
4. **Weekly parameter tuning.** Loses to doing nothing, and leaves you holding a
   fitted parameter set that may not survive the next regime.
5. **A 90% win rate.** Not reachable on this data. The best measured configuration
   is 57% green at +0.368R — a system can be excellent at 57%.
6. **Splitting into four separate TradingView scripts.** Hits the studies-per-chart
   cap. Use `scriptMode` instead (I12).
7. **The range filter** (the signal mechanism). +0.002R over 1,131
   trades across 2M/3M/5M, measured with a rule verified against the indicator's
   own signals. Fading it also loses. Fourth independent trend-following
   approach to fail on this instrument.
8. **Filtering the range filter into profitability.** 31 configurations tried
   across two rounds — ADX, stretch-from-EMA21, pullback limit entries, HTF
   gating both ways, five exit styles. Best is ADX>=20 + 3R at +0.053R, CI
   [−0.075, +0.184]. A zero-edge config has a **25% chance** of landing positive
   in both periods at these sample sizes, so 31 configs predict ~7.7 false
   winners; three were found. Fewer than noise produces.
   `docs/FINDINGS_signal_improvement.md`.
9. **A lower-timeframe stop on a higher-timeframe idea.** The standard
   multi-timeframe recipe — 1H/4H/Daily for direction, 5M for a tight entry and
   a tight stop — gives exactly the R:R it promises (7x on 1H, 13.6x on 4H, 24x
   on Daily) and a 12.7% win rate, with the median trade dead in 3 bars. Gold's
   5M ATR is ~$4.80, so a stop beyond a 5M swing sits inside one bar's normal
   range: the trade is killed by noise before the HTF thesis can act. Replicated
   on two periods. `docs/FINDINGS_multitimeframe.md`.

10. **Candle Range Theory as taught** (fade the sweep back to the opposite end
    of the range). Negative at all six timeframes tested — 15M, 1H, 4H, Daily,
    Weekly, Monthly. On 4H over 3.7 years and 1,524 setups it is −0.099R and
    negative in every individual year. Win rates of 44–49% look fine; the median
    reward is ~1.0R, and one 69%-win variant still lost money at 0.4R median.
    `docs/FINDINGS_crt.md`.
11. **CRT inverse (continuation) as a durable edge.** Looked excellent on six
    months of 4H (+0.262R, all quarters positive, replicated on the H4 export).
    Over 3.7 years it is +0.052R, CI [−0.021, +0.121], and 2023 is negative. The
    short sample sat entirely inside 2026, the one strongly positive year. A
    regime artifact, and a reminder that N setups from one market condition is
    not N independent observations.

12. **Pullback (limit) entries on a trend-follower.** −0.245R / −0.047R, far worse
    than chasing. A resting order only fills when price comes back, so you are
    selected into precisely the signals that immediately reversed.

13. **An 80% hit rate at 0.5:1 on the range-filter flip.** The supplied target
    table quotes 78.5–80.6% and +0.18 to +0.21R. Its arithmetic is correct, but
    the hit rate is `TP1/(TP1+SL)` — it excludes the "flip first" trades, 23% of
    signals in its own 1m counts. Those average **−0.6R** here and are positive
    ~1% of the time. Applying our measured flip outcome to their own counts takes
    1m from +0.178R to **−0.002R**. Our own hit rate on the same rules is
    **67–73%**, against a 66.7% break-even. Every fix tried — holding through the
    flip, TP 0.5R through 2.0R, stops at 1.0× and 1.5× the candle — is negative
    pooled at P(no edge) 97.7–100%. `docs/FINDINGS_target_80.md`,
    `backtester/target.py`.

---

## 8. Environment constraints

| Constraint                             | Detail                                                                                                                                                                                                                                                                                                                        |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TradingView 5M ceiling                 | ~4 weeks (5,526 bars) whatever you scroll. That yields ~120 1H setups, ~30 4H, ~11 Daily, 0 Monthly — so a Daily or Monthly setup with 5M entries CANNOT be validated from TradingView data. Needs a multi-year M5/M1 export from MT5.                                                                                        |
| TradingView history                    | Shrinking bar spacing does NOT fetch older bars — it only re-renders what is loaded. `model.timeScale().scrollToFirstBar()` requests history: 782 → 5,679 bars on 4H. That call is the difference between a six-month sample and 3.7 years, and in the CRT test it was the difference between a false positive and the truth. |
| Market-data hosts                      | Blocked from the build sandbox (403/502). Data must be supplied as CSV exports                                                                                                                                                                                                                                                |
| `api.github.com`                       | 502 from the sandbox                                                                                                                                                                                                                                                                                                          |
| `GITHUB_TOKEN` / `GH_TOKEN` in sandbox | Literal placeholder `proxy-injected` — not a credential. **Never solicit or accept a real token**                                                                                                                                                                                                                             |
| Device bridge (`device_bash`)          | **No network.** `git push` must be run by the operator                                                                                                                                                                                                                                                                        |
| Device bridge deletes                  | `rm` blocked ("Operation not permitted"). `mv` into `_to_delete/` instead. Git leaves `.lock` files it cannot clean up — clear `HEAD.lock`, `index.lock`, `refs/heads/*.lock` **immediately before** any git write, or bypass the index with `commit-tree` + `update-ref`                                                     |
| TradingView history caps               | ~5,000 5m bars free, 10,000 Essential/Plus, 20,000 Premium. Six months of 5m gold is ~37,000 bars — the Strategy Tester cannot cover a long sample. That is what the Python backtester is for                                                                                                                                 |
| Credentials                            | Operator login details and OAuth sign-in are **declined on principle**, regardless of offered permission                                                                                                                                                                                                                      |

---

## 9. Open items

- **Settle the statistics.** Export **6+ months of M5 or M1** from MT5 (View →
  Symbols → XAUUSD → Bars tab → date range → Export Bars). At this effect size
  ~180–200 trades decides it; six months gives 300–400. Everything is wired — drop
  the file in `data/`, add it to `paths.DATASETS`, run `run_backtest.py`.
- **2M has one sample only** (January, 46 trades). 5M has two that agree. Do not
  present 2M results with equal confidence.
- **Sizing is the binding constraint, not signal quality.** 0.02 lots on £100 is
  £6–9 risk per trade (6–9% of the account). Recommendation: 0.01 below £250, 0.02
  at £250+. This cannot be backtested away.
- **The breakout module is Python-only.** Never wired into Pine because it measured
  −0.08R; wiring it would mean restructuring a working script for a feature the data
  says to leave alone.
- **Manual trading from £100 is not viable on any timeframe** — 0.01 lots is the
  MT5 minimum, and a 1.2×ATR stop is 3.4% of £100 on 3M rising to 29.4% on 4H.
  Every timeframe ruined the account, 1H in eight trades.
  `docs/FINDINGS_manual_trading_100.md`.
- **Timeframe ranking flips for the range filter once exits hold winners.** On
  the indicator's real signals, held to the opposite signal rather than a fixed
  2R: 3M −0.162R, 5M −0.087R, 15M +0.100R, 1H +0.223R, 4H +0.423R. 4H properly
  sized at 2% turns £100 into £281 over 20 months (~£2.40/week, 30% DD) — one
  sample, 150 trades, unreplicated, and it needs ~£1,470 to size correctly.
- **The indicator has now been measured, and its signals have no edge.** The dual
  range filter scores +0.002R over 1,131 trades, CI [−0.079, +0.084], P(no edge)
  49%, using a rule CALIBRATED against the indicator's own per-bar signal values
  (38/1.8 single filter reproduces 94–96% of its markers; the dialog's 27/1.6
  reproduces only ~60%). Direction accuracy is 48–54% at every horizon. Fourteen variants —
  including inverting every signal — produced nothing positive in both periods.
  Use the script for its map, not its markers. `docs/FINDINGS_range_filter.md`.
- **Automation** would recover most of the ~85% of edge lost to manual execution.
  The MQL5 EA exists for this and **has not been run live.**

---

## 10. Conventions

- Pine v6. Indentation matters — see I10.
- MQL5 file is **ASCII-only**; no Unicode in string literals.
- Python `Config` field names match Pine input names exactly.
- Every toggle was verified by running the backtest with it off and confirming its
  reason text disappears from all signals. **Counting trades alone does not prove a
  toggle works** — a toggle can leave the trade count unchanged while still removing
  a reason.
- Commit trailers used here:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: <session url>
  ```

---

## 11. Repo state

|             |                                                                                                                           |
| ----------- | ------------------------------------------------------------------------------------------------------------------------- |
| Remote      | `https://github.com/shorif2000/tradingview`                                                                               |
| Local clone | `/Users/Mohammed/tradingview` (macOS)                                                                                     |
| Branch      | `main`                                                                                                                    |
| Ignored     | `*.pkl`, `__pycache__/`, `*.pyc`, `backtest_report.html`, `trades*.csv`, `.claude/`, `_to_delete/`, `reports/`, `.cache/` |
