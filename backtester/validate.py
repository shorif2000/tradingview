"""
Engine validation suite.

Proves the backtest machinery is correct BEFORE any performance number is
reported. Every check is an invariant that must hold for any dataset:
fills land inside the bar that triggered them, R-multiples match the configured
risk/reward, the stop wins ties, guardrails bind, and no signal uses future data.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from xau_engine import Config, backtest, build_features, ema, rsi, atr, dmi, percentrank, bars_since
from make_synth import make_synth

FAILS: list[str] = []
PASSES = 0


def check(name: str, cond: bool, detail: str = ""):
    global PASSES
    if cond:
        PASSES += 1
        print(f"  PASS  {name}")
    else:
        FAILS.append(f"{name} :: {detail}")
        print(f"  FAIL  {name}  {detail}")


print("=" * 78)
print("1. INDICATOR MATHS")
print("=" * 78)
s = pd.Series([1.0, 2, 3, 4, 5, 6, 7, 8, 9, 10])
e3 = ema(s, 3)
# EMA(3) recursion by hand: seed = SMA(3) = 2, then a=0.5
manual = 2.0
for v in [4, 5, 6, 7, 8, 9, 10]:
    manual = manual + 0.5 * (v - manual)
check("EMA matches manual recursion", abs(e3.iloc[-1] - manual) < 1e-9,
      f"{e3.iloc[-1]:.10f} vs {manual:.10f}")

up_only = pd.Series(np.arange(1, 60, dtype=float))
check("RSI = 100 on a monotonic rise", abs(rsi(up_only, 14).iloc[-1] - 100.0) < 1e-6)
dn_only = pd.Series(np.arange(60, 1, -1, dtype=float))
check("RSI = 0 on a monotonic fall", abs(rsi(dn_only, 14).iloc[-1] - 0.0) < 1e-6)

pr = percentrank(pd.Series([1.0] * 200 + [5.0]), 200)
check("percentrank = 100 for a new high", abs(pr.iloc[-1] - 100.0) < 1e-9, f"{pr.iloc[-1]}")

bs = bars_since(pd.Series([False, True, False, False, True, False]))
check("bars_since counts correctly", list(bs) == [10**6, 0, 1, 2, 0, 1], str(list(bs)))

df = make_synth().drop(columns=["regime_true"])
cfg = Config()
feat = build_features(df, cfg)
a = feat["adx"].dropna()
check("ADX bounded 0-100", bool((a >= 0).all() and (a <= 100).all()),
      f"min {a.min():.2f} max {a.max():.2f}")
check("ATR strictly positive", bool((feat["atr"].dropna() > 0).all()))
check("regimes are mutually exclusive", not bool((feat["in_trend"] & feat["in_range"]).any()))

print()
print("=" * 78)
print("2. NO LOOKAHEAD IN THE HIGHER-TIMEFRAME FILTER")
print("=" * 78)
# The 1H filter must only ever reflect a CLOSED hourly bar. Recompute the 1H
# EMA state independently and confirm the 5m series equals the previous hour's value.
h1 = df["close"].resample("1h").last().dropna()
ref = (ema(h1, 50) > ema(h1, 200)).shift(1)
probe = feat["htf_bull"].resample("1h").last().dropna()
common = ref.dropna().index.intersection(probe.index)
agree = (ref.reindex(common).astype(bool) == probe.reindex(common).astype(bool)).mean()
check("1H filter uses only closed bars", agree > 0.995, f"agreement {agree:.4f}")

# A harsher test: shifting the input forward must change the signal set. If it
# does not, the engine is ignoring the filter (or peeking either way).
# the HTF filter only gates TREND trades, so that module must be on to test it
c1 = Config(); c1.use_trend_module = True
c2 = Config(); c2.use_trend_module = True; c2.use_htf = False
t_on, _, _ = backtest(df, c1)
t_off, _, _ = backtest(df, c2)
check("HTF filter actually binds", len(t_on) != len(t_off),
      f"on={len(t_on)} off={len(t_off)}")

print()
print("=" * 78)
print("3. FILL AND ACCOUNTING INVARIANTS  (run on 6 months of synthetic bars)")
print("=" * 78)
cfg = Config()
tr, eq, feat = backtest(df, cfg)
print(f"  ({len(tr)} trades generated for testing)")
check("trades were generated", len(tr) > 30, f"{len(tr)}")

bars = feat
lo = bars["low"]; hi = bars["high"]
oz = cfg.lots * cfg.oz_per_lot

# 3a. TP exits must pay exactly the configured R (no costs applied after entry)
tp_tr = tr[tr.reason == "TP"]
if len(tp_tr):
    err = (tp_tr.r_multiple - cfg.rr).abs().max()
    check(f"TP exits return exactly +{cfg.rr}R", err < 1e-6, f"max error {err:.2e}")

# 3b. SL exits must return -1R minus the modelled stop slippage
sl_tr = tr[tr.reason == "SL"]
if len(sl_tr):
    expected = -1.0 - cfg.slip_stop_usd * oz / (sl_tr.risk_usd)
    err = (sl_tr.r_multiple - expected).abs().max()
    check("SL exits return -1R minus slippage", err < 1e-6, f"max error {err:.2e}")

# 3c. every exit price must lie inside the exit bar's range (or be a close)
bad = 0
for t in tr.itertuples():
    b = bars.loc[t.exit_time]
    pad = cfg.slip_stop_usd + cfg.spread_usd + 1e-6
    if not (b.low - pad <= t.exit <= b.high + pad):
        bad += 1
check("exit prices lie within the exit bar", bad == 0, f"{bad} violations")

# 3d. the STOP must win when a single bar contains both levels
viol = 0
for t in tr.itertuples():
    b = bars.loc[t.exit_time]
    if t.side == "long":
        both = b.low <= t.sl and b.high >= t.tp
    else:
        both = b.high >= t.sl and b.low <= t.tp
    if both and t.reason != "SL":
        viol += 1
check("stop wins when one bar holds both levels", viol == 0, f"{viol} violations")

# 3e. an SL exit must not have had the target reachable on an earlier bar
viol = 0
pos = {ts: k for k, ts in enumerate(bars.index)}
for t in sl_tr.itertuples():
    i0, i1 = pos[t.entry_time] + 1, pos[t.exit_time]
    if i1 <= i0:
        continue
    seg = bars.iloc[i0:i1]
    reached = (seg.high >= t.tp).any() if t.side == "long" else (seg.low <= t.tp).any()
    if reached:
        viol += 1
check("no TP was skipped before an SL", viol == 0, f"{viol} violations")

# 3f. balance recursion
recon = cfg.start_balance_gbp + tr.pnl_gbp.cumsum()
check("balance recursion is consistent", bool(np.allclose(recon.to_numpy(), tr.balance_after.to_numpy(), atol=1e-9)))
check("final equity equals last trade balance",
      abs(eq.equity.iloc[-1] - tr.balance_after.iloc[-1]) < 1e-9)

# 3g. P/L direction sanity
sgn = np.where(tr.side == "long", 1.0, -1.0)
expect_usd = (tr.exit - tr.entry) * sgn * oz
check("P/L sign and magnitude correct", bool(np.allclose(expect_usd, tr.pnl_usd, atol=1e-9)))

print()
print("=" * 78)
print("4. RULES AND GUARDRAILS BIND")
print("=" * 78)
lh = bars["local_hour"]
entry_hours = pd.Series([lh.loc[t] for t in tr.entry_time])
check("no entry outside the 07:00-20:00 session",
      bool(((entry_hours >= cfg.sess_start) & (entry_hours < cfg.sess_end)).all()),
      f"hours seen {sorted(entry_hours.unique())}")

per_day = tr.groupby(pd.to_datetime(tr.entry_time).dt.date).size()
check(f"never exceeds {cfg.max_trades_day} trades/day", int(per_day.max()) <= cfg.max_trades_day,
      f"max {per_day.max()}")

# positions never overlap
ov = 0
prev_exit = None
for t in tr.sort_values("entry_time").itertuples():
    if prev_exit is not None and t.entry_time < prev_exit:
        ov += 1
    prev_exit = t.exit_time
check("no overlapping positions", ov == 0, f"{ov} overlaps")

# stop distance respects the min/max ATR band
dist = (tr.entry - tr.sl).abs()
atr_at = pd.Series([bars["atr"].loc[t] for t in tr.entry_time])
check("stop >= min_stop_atR", bool((dist >= cfg.min_stop_atr * atr_at - 1e-6).all()))
check("stop <= max_stop_atR", bool((dist <= cfg.max_stop_atr * atr_at + cfg.spread_usd + 1e-6).all()),
      f"worst ratio {(dist/atr_at).max():.3f}")

# risk/reward geometry
rrr = ((tr.tp - tr.entry).abs() / (tr.entry - tr.sl).abs())
check(f"every trade is set to {cfg.rr}R", bool(np.allclose(rrr, cfg.rr, atol=1e-9)))

# daily loss cap
daily = tr.groupby(pd.to_datetime(tr.entry_time).dt.date).pnl_gbp.sum()
worst_after_cap = daily.min()
check("daily loss cap limits damage (1 trade of overshoot allowed)",
      worst_after_cap > -(cfg.max_loss_day_gbp + abs(tr.pnl_gbp.min()) + 0.01),
      f"worst day {worst_after_cap:.2f}")

# every trade carries an explanation
check("every trade records why it fired", bool((tr.why.str.len() > 0).all()))
check("reasons meet the minimum score",
      bool((tr.why.str.count(r"\+") + 1 >= cfg.trend_min_score).all()))

print()
print("=" * 78)
print("5. COST SENSITIVITY IS MONOTONIC  (sanity of the cost model)")
print("=" * 78)
# Use a large balance here so account ruin cannot truncate the runs and hide
# the cost effect — this test isolates the cost model, not the account size.
nets = []
for sp in (0.10, 0.25, 0.50):
    c = Config(); c.spread_usd = sp; c.start_balance_gbp = 100_000.0; c.max_loss_day_gbp = 0.0
    t2, e2, _ = backtest(df, c)
    nets.append(float(t2.pnl_gbp.sum()))
    print(f"  spread ${sp:.2f} -> net £{nets[-1]:.2f} on {len(t2)} trades")
check("wider spread never helps", nets[0] > nets[1] > nets[2], str(nets))

print()
print("=" * 78)
print("6. ACCOUNT RUIN IS DETECTED AND HALTS TRADING")
print("=" * 78)
cr = Config(); cr.start_balance_gbp = 100.0
tr_r, eq_r, _ = backtest(df, cr)
margin_needed = float(df.close.mean()) * cr.lots * cr.oz_per_lot / cr.leverage / cr.gbpusd
check("ruin flag is set once the account can no longer fund 0.01 lot",
      tr_r.attrs["ruin"] is True and float(eq_r.equity.iloc[-1]) < margin_needed * 3,
      f"ruin={tr_r.attrs['ruin']} final=£{eq_r.equity.iloc[-1]:.2f} margin≈£{margin_needed:.2f}")
check("equity never goes negative", bool((eq_r.equity > -1e-9).all()),
      f"min equity £{eq_r.equity.min():.2f}")
check("no trades are recorded after ruin",
      tr_r.attrs["ruin_time"] is None or bool((pd.to_datetime(tr_r.entry_time) <= tr_r.attrs["ruin_time"]).all()))

print()
print("=" * 78)
print(f"RESULT: {PASSES} passed, {len(FAILS)} failed")
for f in FAILS:
    print("  ! " + f)
print("=" * 78)
