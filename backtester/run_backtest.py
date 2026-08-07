#!/usr/bin/env python3
"""
Run the XAU Regime Scalper backtest.

    python3 run_backtest.py --csv XAUUSD_M5.csv --assume-tz Etc/GMT-3 --spread 0.25
    python3 run_backtest.py --synth                      # engine demo on synthetic bars

Outputs: stats to stdout, trades CSV, and a self-contained HTML report.
"""
from __future__ import annotations
import argparse
import sys
import pandas as pd

from xau_engine import Config, backtest, stats
from data_io import load_ohlc, describe
from report import build_report


def cost_sensitivity(df, base: Config, spreads=(0.10, 0.15, 0.25, 0.40, 0.60)):
    rows = []
    for sp in spreads:
        c = Config(**{**base.__dict__, "spread_usd": sp})
        t, e, _ = backtest(df, c)
        if len(t) == 0:
            rows.append([f"{sp:.2f}", 0, "—", "—", f"{c.start_balance_gbp:.2f}"])
            continue
        s = stats(t, e, c)
        flag = "  (wiped out)" if t.attrs.get("ruin") else ""
        rows.append([f"{sp:.2f}", s["trades"], f"{s['net_gbp']:+,.2f}",
                     f"{s['win_rate']:.1f}%", f"{s['final_balance']:.2f}{flag}"])
    return rows


def walk_forward(df, cfg: Config):
    """Split the sample in half. Both halves are still IN-sample for the parameters —
    this shows stability across time, it is not out-of-sample proof."""
    mid = df.index[len(df) // 2]
    rows = []
    for name, part in [("First half", df[df.index < mid]), ("Second half", df[df.index >= mid])]:
        t, e, _ = backtest(part, cfg)
        if len(t) == 0:
            rows.append([name, 0, "—", "—", "—"]); continue
        s = stats(t, e, cfg)
        rows.append([name, s["trades"], f"{s['win_rate']:.1f}%",
                     f"{s['net_gbp']:+,.2f}", f"{s['expectancy_r']:+.3f}"])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--synth", action="store_true")
    ap.add_argument("--assume-tz", default=None,
                    help="Timezone of the file's timestamps. MT4/MT5 = broker server time "
                         "(Vantage: Etc/GMT-2 in winter, Etc/GMT-3 in summer). TradingView = UTC.")
    ap.add_argument("--spread", type=float, default=0.25)
    ap.add_argument("--gbpusd", type=float, default=1.27)
    ap.add_argument("--rr", type=float, default=2.0)
    ap.add_argument("--balance", type=float, default=100.0)
    ap.add_argument("--lots", type=float, default=0.01)
    ap.add_argument("--out", default=None,
                    help="HTML report path (default: <repo>/reports/backtest_report.html)")
    ap.add_argument("--trades-out", default=None,
                    help="trades CSV path (default: <repo>/reports/trades.csv)")
    a = ap.parse_args()

    # Resolved here rather than as argparse defaults so the paths land inside the
    # repo the script actually lives in, not the directory it happens to be run
    # from — and so `reports/` is only created when a run is about to write there.
    from paths import report_dir
    if a.out is None:
        a.out = str(report_dir() / "backtest_report.html")
    if a.trades_out is None:
        a.trades_out = str(report_dir() / "trades.csv")

    if a.synth:
        from make_synth import make_synth
        df = make_synth().drop(columns=["regime_true"])
        caveat = ("<b>Synthetic data.</b> These bars were generated to prove the backtest engine is "
                  "correct — fills, R-multiples, cost handling and guardrails. The performance figures "
                  "below describe a simulated market with no real edge in it and must not be read as a "
                  "success rate for live trading.")
    elif a.csv:
        df = load_ohlc(a.csv, assume_tz=a.assume_tz)
        caveat = ""
    else:
        sys.exit("Give me --csv <file> or --synth")

    desc = describe(df)
    print(desc)
    if len(df) < 5000:
        print(f"WARNING: only {len(df)} bars — thin sample for 5m conclusions.")

    cfg = Config(start_balance_gbp=a.balance, lots=a.lots, spread_usd=a.spread,
                 gbpusd=a.gbpusd, rr=a.rr)
    tr, eq, feat = backtest(df, cfg)
    if len(tr) == 0:
        sys.exit("No trades generated — check the timezone of your timestamps and the session filter.")

    st = stats(tr, eq, cfg)
    print("\n" + "=" * 64)
    for k, v in st.items():
        print(f"  {k:<18} {v if isinstance(v,int) else f'{v:,.3f}'}")
    print("=" * 64)
    if tr.attrs.get("ruin"):
        print(f"  ACCOUNT WIPED OUT at {tr.attrs['ruin_time']}")

    tr.to_csv(a.trades_out, index=False)
    rows_cost = cost_sensitivity(df, cfg)
    rows_wf = walk_forward(df, cfg)
    html = build_report(tr, eq, st, cfg, {}, cost_rows=rows_cost, wf_rows=rows_wf,
                        data_desc=desc, caveat=caveat)
    with open(a.out, "w") as f:
        f.write(html)
    print(f"\nreport  -> {a.out}\ntrades  -> {a.trades_out}")


if __name__ == "__main__":
    main()
