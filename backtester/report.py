"""
Self-contained HTML backtest report.

Palette: default validated instance, blue/red diverging pair
(light #2a78d6 / #e34948, dark #3987e5 / #e66767) — clears every gate in both
modes on the all-pairs list. Polarity is never colour-alone: every bar carries a
signed direct label, and a table view of each chart is present.
"""
from __future__ import annotations
import html
import json
import numpy as np
import pandas as pd

CSS = """
*{box-sizing:border-box}
.viz-root{
  color-scheme:light;
  --plane:#f9f9f7; --surface-1:#fcfcfb;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7;
  --pos:#2a78d6; --neg:#e34948; --neutral:#f0efec;
  --good:#0ca30c; --critical:#d03b3b; --warning:#fab219;
}
@media (prefers-color-scheme:dark){
  :root:where(:not([data-theme="light"])) .viz-root{
    color-scheme:dark;
    --plane:#0d0d0d; --surface-1:#1a1a19;
    --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835;
    --pos:#3987e5; --neg:#e66767; --neutral:#383835;
  }
}
:root[data-theme="dark"] .viz-root{
  color-scheme:dark;
  --plane:#0d0d0d; --surface-1:#1a1a19;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835;
  --pos:#3987e5; --neg:#e66767; --neutral:#383835;
}
body{margin:0;background:var(--plane);color:var(--text-primary);
 font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif}
.wrap{max-width:1120px;margin:0 auto;padding:32px 24px 72px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.02em}
h2{font-size:17px;margin:38px 0 12px;letter-spacing:-.01em}
.sub{color:var(--text-secondary);font-size:13.5px;margin:0 0 26px}
.card{background:var(--surface-1);border:1px solid var(--grid);border-radius:12px;padding:18px 20px;margin-bottom:18px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:12px;margin-bottom:22px}
.tile{background:var(--surface-1);border:1px solid var(--grid);border-radius:12px;padding:14px 16px}
.tile .k{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.tile .v{font-size:25px;font-weight:600;letter-spacing:-.02em;margin-top:3px;font-variant-numeric:tabular-nums}
.tile .n{font-size:11.5px;color:var(--text-secondary);margin-top:2px}
table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
th,td{padding:7px 10px;text-align:right;border-bottom:1px solid var(--grid)}
th{color:var(--muted);font-weight:500;font-size:11.5px;text-transform:uppercase;letter-spacing:.05em}
th:first-child,td:first-child{text-align:left}
tbody tr:hover{background:color-mix(in srgb,var(--grid) 40%,transparent)}
.legend{display:flex;gap:16px;font-size:12.5px;color:var(--text-secondary);margin:0 0 10px}
.legend i{width:11px;height:11px;border-radius:3px;display:inline-block;margin-right:5px;vertical-align:-1px}
.tt{position:fixed;pointer-events:none;opacity:0;transition:opacity .08s;background:var(--surface-1);
 border:1px solid var(--axis);border-radius:8px;padding:7px 10px;font-size:12.5px;
 box-shadow:0 6px 20px rgba(0,0,0,.14);z-index:9;white-space:nowrap;font-variant-numeric:tabular-nums}
details{margin-top:12px}summary{cursor:pointer;font-size:12.5px;color:var(--text-secondary)}
.note{background:color-mix(in srgb,var(--warning) 12%,var(--surface-1));border:1px solid color-mix(in srgb,var(--warning) 45%,var(--grid));
 border-radius:10px;padding:14px 16px;font-size:13.5px;margin-bottom:20px}
.bad{color:var(--critical);font-weight:600}.ok{color:var(--good);font-weight:600}
svg{display:block;width:100%;height:auto;overflow:visible}
.gl{stroke:var(--grid);stroke-width:1}.ax{stroke:var(--axis);stroke-width:1}
.al{fill:var(--muted);font-size:10.5px}
.dl{fill:var(--text-secondary);font-size:10.5px;font-variant-numeric:tabular-nums}
.toggle{position:fixed;top:14px;right:16px;background:var(--surface-1);border:1px solid var(--grid);
 border-radius:8px;padding:6px 11px;font-size:12px;cursor:pointer;color:var(--text-secondary);z-index:20}
"""


def _fmt(v, nd=2, unit=""):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return "—"
    return f"{v:,.{nd}f}{unit}"


def equity_chart(eq: pd.DataFrame, start: float) -> str:
    """Line chart, one series -> no legend box; crosshair tooltip."""
    s = eq.equity
    if len(s) > 1400:
        s = s.iloc[:: max(1, len(s) // 1400)]
    W, H, PL, PR, PT, PB = 1040, 300, 52, 14, 14, 30
    iw, ih = W - PL - PR, H - PT - PB
    ymin, ymax = float(min(s.min(), start)), float(max(s.max(), start))
    pad = max((ymax - ymin) * 0.08, 0.5)
    ymax = ymax + pad
    ymin = max(0.0, ymin - pad) if ymin >= 0 else ymin - pad   # equity can't go negative
    xs = np.linspace(PL, PL + iw, len(s))
    ys = PT + ih - (s.to_numpy() - ymin) / (ymax - ymin) * ih

    ticks = np.linspace(ymin, ymax, 5)
    grid = "".join(
        f'<line class="gl" x1="{PL}" x2="{PL+iw}" y1="{PT+ih-(t-ymin)/(ymax-ymin)*ih:.1f}" '
        f'y2="{PT+ih-(t-ymin)/(ymax-ymin)*ih:.1f}"/>'
        f'<text class="al" x="{PL-8}" y="{PT+ih-(t-ymin)/(ymax-ymin)*ih+3.5:.1f}" text-anchor="end">£{t:,.0f}</text>'
        for t in ticks)
    base_y = PT + ih - (start - ymin) / (ymax - ymin) * ih
    path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    n = len(s)
    xlab = "".join(
        f'<text class="al" x="{xs[i]:.0f}" y="{H-8}" text-anchor="middle">'
        f'{s.index[i].strftime("%d %b")}</text>'
        for i in np.linspace(0, n - 1, min(7, n)).astype(int))
    pts = json.dumps([[float(x), float(y), s.index[i].strftime("%d %b %Y %H:%M"), float(s.iloc[i])]
                      for i, (x, y) in enumerate(zip(xs, ys))])
    return f"""
<svg viewBox="0 0 {W} {H}" id="eqsvg" role="img" aria-label="Account equity over time">
 {grid}
 <line class="ax" x1="{PL}" x2="{PL+iw}" y1="{base_y:.1f}" y2="{base_y:.1f}" stroke-dasharray="4 4"/>
 <text class="dl" x="{PL+iw}" y="{base_y-6:.1f}" text-anchor="end">start £{start:,.0f}</text>
 <path d="{path}" fill="none" stroke="var(--pos)" stroke-width="2" stroke-linejoin="round"/>
 <line id="eqcross" class="ax" y1="{PT}" y2="{PT+ih}" x1="-9" x2="-9" opacity="0"/>
 <circle id="eqdot" r="4.5" fill="var(--pos)" stroke="var(--surface-1)" stroke-width="2" opacity="0"/>
 <rect x="{PL}" y="{PT}" width="{iw}" height="{ih}" fill="transparent" id="eqhit"/>
 {xlab}
</svg>
<script>window.__eq={pts};</script>"""


def bar_chart(labels, values, cid, unit="£", fmt="{:+,.2f}",
              signs=None, baseline="center", legend=("positive", "negative")) -> str:
    """
    Bars with meaningful colour only.

    baseline="center" -> diverging around zero, colour = sign of the value.
    baseline="bottom" -> magnitudes on a floor (counts); colour comes from `signs`,
                         which must say what each bucket MEANS, not how tall it is.
    """
    W, H, PL, PR, PT, PB = 1040, 250, 52, 14, 22, 34
    iw, ih = W - PL - PR, H - PT - PB
    v = np.array(values, dtype=float)
    if len(v) == 0:
        return "<p class='sub'>No data.</p>"
    sg = np.array(signs, dtype=float) if signs is not None else np.sign(v)
    centred = baseline == "center"
    vmax = max(abs(v).max(), 1e-9) * 1.22
    zero = PT + ih / 2 if centred else PT + ih
    half = (ih / 2) if centred else ih
    bw = min(iw / len(v) * 0.62, 74)
    step = iw / len(v)
    out = [f'<line class="ax" x1="{PL}" x2="{PL+iw}" y1="{zero}" y2="{zero}"/>']
    for i, (lb, val) in enumerate(zip(labels, v)):
        cx = PL + step * (i + 0.5)
        h = abs(val) / vmax * half
        y = zero - h if (val >= 0 or not centred) else zero
        col = "var(--pos)" if sg[i] >= 0 else "var(--neg)"
        # 2px surface gap between adjacent fills, 4px rounded data-end at the baseline
        out.append(f'<rect x="{cx-bw/2+1:.1f}" y="{y:.1f}" width="{bw-2:.1f}" height="{max(h,1):.1f}" '
                   f'fill="{col}" rx="4" data-l="{html.escape(str(lb))}" data-v="{val:.4f}" class="bar"/>')
        ly = (y - 6) if (val >= 0 or not centred) else (y + h + 13)
        out.append(f'<text class="dl" x="{cx:.1f}" y="{ly:.1f}" text-anchor="middle">{fmt.format(val)}</text>')
        out.append(f'<text class="al" x="{cx:.1f}" y="{H-10}" text-anchor="middle">{html.escape(str(lb))}</text>')
    return (f'<div class="legend"><span><i style="background:var(--pos)"></i>{html.escape(legend[0])}</span>'
            f'<span><i style="background:var(--neg)"></i>{html.escape(legend[1])}</span></div>'
            f'<svg viewBox="0 0 {W} {H}" id="{cid}" role="img">{"".join(out)}</svg>')


def table_view(headers, rows) -> str:
    th = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    tb = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>"


def build_report(tr: pd.DataFrame, eq: pd.DataFrame, st: dict, cfg, meta: dict,
                 cost_rows=None, wf_rows=None, data_desc="", caveat="") -> str:
    ruin = bool(tr.attrs.get("ruin", False))
    net = st.get("net_gbp", 0.0)
    tiles = [
        ("Net P/L", f"£{net:,.2f}", f"{st.get('return_pct',0):+.1f}% on £{cfg.start_balance_gbp:,.0f}"),
        ("Win rate", f"{st.get('win_rate',0):.1f}%", f"{st.get('wins',0)}W / {st.get('losses',0)}L"),
        ("Profit factor", _fmt(st.get("profit_factor"), 2), "gross win ÷ gross loss"),
        ("Expectancy", f"{st.get('expectancy_r',0):+.3f}R", f"£{st.get('expectancy_gbp',0):+.3f} per trade"),
        ("Max drawdown", f"£{st.get('max_dd_gbp',0):,.2f}", f"{st.get('max_dd_pct',0):.1f}% peak-to-trough"),
        ("Trades", f"{st.get('trades',0):,}", f"{st.get('avg_bars_held',0):.0f} bars held avg"),
    ]
    tile_html = "".join(
        f'<div class="tile"><div class="k">{html.escape(k)}</div>'
        f'<div class="v">{html.escape(v)}</div><div class="n">{html.escape(n)}</div></div>'
        for k, v, n in tiles)

    # monthly
    t2 = tr.copy()
    t2["m"] = pd.to_datetime(t2.entry_time).dt.strftime("%b %Y")
    mo = t2.groupby("m", sort=False).agg(net=("pnl_gbp", "sum"), n=("pnl_gbp", "size"),
                                         wr=("pnl_gbp", lambda s: (s > 0).mean() * 100))
    mo_chart = bar_chart(list(mo.index), list(mo.net), "mosvg")
    mo_table = table_view(["Month", "Trades", "Win rate", "Net £"],
                          [[m, int(r.n), f"{r.wr:.1f}%", f"{r.net:+,.2f}"] for m, r in mo.iterrows()])

    # R distribution
    bins = [(-99, -1.0, "≤ −1R"), (-1.0, -0.5, "−1 to −0.5R"), (-0.5, 0.0, "−0.5 to 0R"),
            (0.0, 0.5, "0 to 0.5R"), (0.5, 1.0, "0.5 to 1R"), (1.0, 1.99, "1 to 2R"), (1.99, 99, "≥ 2R")]
    rl, rv, rs = [], [], []
    for lo, hi, lb in bins:
        c = int(((tr.r_multiple > lo) & (tr.r_multiple <= hi)).sum())
        rl.append(lb); rv.append(c); rs.append(1.0 if lo >= 0.0 else -1.0)
    r_chart = bar_chart(rl, [float(x) for x in rv], "rsvg", fmt="{:,.0f}",
                        signs=rs, baseline="bottom",
                        legend=("winning buckets", "losing buckets"))
    r_table = table_view(["R bucket", "Trades", "% of all"],
                         [[l, v, f"{v/max(len(tr),1)*100:.1f}%"] for l, v in zip(rl, rv)])

    brk = table_view(
        ["Segment", "Trades", "Win rate", "Net £", "Expectancy R"],
        [[seg, int(g.shape[0]), f"{(g.pnl_gbp>0).mean()*100:.1f}%",
          f"{g.pnl_gbp.sum():+,.2f}", f"{g.r_multiple.mean():+.3f}"]
         for seg, g in [("Trend module", tr[tr.module == "trend"]),
                        ("Range module", tr[tr.module == "range"]),
                        ("Longs", tr[tr.side == "long"]),
                        ("Shorts", tr[tr.side == "short"])] if len(g)])

    ex = table_view(["Exit", "Count", "% of trades"],
                    [[k, int(v), f"{v/max(len(tr),1)*100:.1f}%"]
                     for k, v in tr.reason.value_counts().items()])

    why = (tr.why.str.split(" + ").explode().value_counts().head(12))
    why_t = table_view(["Trigger reason", "Appearances", "Win rate when present"],
                       [[k, int(v),
                         f"{(tr[tr.why.str.contains(k, regex=False)].pnl_gbp>0).mean()*100:.1f}%"]
                        for k, v in why.items()])

    cost_t = table_view(["Spread (USD)", "Trades", "Net £", "Win rate", "Final balance"], cost_rows or [])
    wf_t = table_view(["Period", "Trades", "Win rate", "Net £", "Expectancy R"], wf_rows or [])

    tl = tr.tail(60).iloc[::-1]
    trades_t = table_view(
        ["Entry time", "Side", "Module", "Entry", "SL", "TP", "Exit", "Why", "R", "P/L £", "Balance"],
        [[str(t.entry_time)[:16], t.side, t.module, f"{t.entry:.2f}", f"{t.sl:.2f}", f"{t.tp:.2f}",
          f"{t.reason} @ {t.exit:.2f}", html.escape(t.why[:70]),
          f"{t.r_multiple:+.2f}", f"{t.pnl_gbp:+.2f}", f"{t.balance_after:.2f}"] for t in tl.itertuples()])

    ruin_note = ""
    if ruin:
        ruin_note = (f'<div class="note"><b>The account was wiped out.</b> Equity fell below the margin '
                     f'needed to open even one 0.01 lot on {str(tr.attrs.get("ruin_time"))[:16]}, so the '
                     f'test stops there. Trades after that point are not simulated.</div>')

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>XAU Regime Scalper — 5m backtest</title><style>{CSS}</style></head>
<body class="viz-root"><button class="toggle" id="tg">◐ theme</button><div class="wrap">
<h1>XAU Regime Scalper — 5-minute backtest</h1>
<p class="sub">{html.escape(data_desc)}<br>
£{cfg.start_balance_gbp:,.0f} start · {cfg.lots} lot fixed ({cfg.lots*cfg.oz_per_lot:.0f} oz, $1 per $1 move) ·
spread ${cfg.spread_usd:.2f} · stop slippage ${cfg.slip_stop_usd:.2f} · target {cfg.rr:g}R ·
session {cfg.sess_start:02d}:00–{cfg.sess_end:02d}:00 {cfg.tz} · max {cfg.max_trades_day} trades/day</p>
{f'<div class="note">{caveat}</div>' if caveat else ''}
{ruin_note}
<div class="tiles">{tile_html}</div>

<h2>Equity curve</h2>
<div class="card">{equity_chart(eq, cfg.start_balance_gbp)}</div>

<h2>Net result by month</h2>
<div class="card">{mo_chart}
<details><summary>Table view</summary>{mo_table}</details></div>

<h2>Where the trades finished (R multiples)</h2>
<div class="card">{r_chart}
<details><summary>Table view</summary>{r_table}</details></div>

<h2>Breakdown by module and direction</h2>
<div class="card">{brk}</div>

<h2>How trades ended</h2>
<div class="card">{ex}</div>

<h2>Which triggers actually fired — and how they did</h2>
<div class="card">{why_t}</div>

<h2>Sensitivity to dealing costs</h2>
<div class="card">{cost_t}</div>

<h2>Walk-forward: first half vs second half</h2>
<div class="card">{wf_t}</div>

<h2>Last 60 trades</h2>
<div class="card" style="overflow-x:auto">{trades_t}</div>
</div><div class="tt" id="tt"></div>
<script>
const tt=document.getElementById('tt');
function show(e,h){{tt.innerHTML=h;tt.style.opacity=1;
 tt.style.left=Math.min(e.clientX+14,innerWidth-tt.offsetWidth-10)+'px';
 tt.style.top=(e.clientY-tt.offsetHeight-12)+'px';}}
function hide(){{tt.style.opacity=0;}}
document.querySelectorAll('.bar').forEach(b=>{{
 b.addEventListener('mousemove',e=>show(e,'<b>'+b.dataset.l+'</b><br>'+(+b.dataset.v).toLocaleString(undefined,{{maximumFractionDigits:2}})));
 b.addEventListener('mouseleave',hide);}});
const hit=document.getElementById('eqhit'),cross=document.getElementById('eqcross'),dot=document.getElementById('eqdot');
if(hit&&window.__eq){{
 const svg=document.getElementById('eqsvg');
 hit.addEventListener('mousemove',e=>{{
  const r=svg.getBoundingClientRect(),vb=svg.viewBox.baseVal;
  const x=(e.clientX-r.left)/r.width*vb.width;
  let best=0,bd=1e9;
  for(let i=0;i<window.__eq.length;i++){{const d=Math.abs(window.__eq[i][0]-x);if(d<bd){{bd=d;best=i;}}}}
  const p=window.__eq[best];
  cross.setAttribute('x1',p[0]);cross.setAttribute('x2',p[0]);cross.setAttribute('opacity',.6);
  dot.setAttribute('cx',p[0]);dot.setAttribute('cy',p[1]);dot.setAttribute('opacity',1);
  show(e,'<b>'+p[2]+'</b><br>£'+p[3].toFixed(2));}});
 hit.addEventListener('mouseleave',()=>{{hide();cross.setAttribute('opacity',0);dot.setAttribute('opacity',0);}});}}
document.getElementById('tg').onclick=()=>{{
 const r=document.documentElement;
 const cur=r.dataset.theme||(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');
 r.dataset.theme=cur==='dark'?'light':'dark';}};
</script></body></html>"""
