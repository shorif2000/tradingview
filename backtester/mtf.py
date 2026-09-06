"""
HTF setup + LTF entry: does refining the entry on 5M actually help?

The claim being tested is the one every multi-timeframe course makes: take your
direction and target from 1H/4H/Daily, then drop to 3M/5M to find a tighter
entry, and the R-multiple expands because your stop is smaller.

Three stop placements, same setups, same targets:
  LTF stop  - beyond the 5M swing that triggered the entry (what the courses say)
  HTF stop  - beyond the HTF sweep wick (where the thesis actually lives)
  HALF      - midway between them
"""
from __future__ import annotations
import warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from paths import dataset
from xau_engine import atr as atr_fn

D = dataset("m5_summer")          # TradingView M5 export, Jun 14 - Aug 5

def run(d, htf_min, *, lookback=3, wait=60, conf_lb=12, spread=0.20, slip=0.10,
        sl_buf=0.15, max_hold=900, stop_mode="htf", entry="ltf"):
    A = atr_fn(d.high, d.low, d.close, 14).to_numpy(float)
    T = d.index.to_numpy(); O,H,L,C = (d[x].to_numpy(float) for x in ("open","high","low","close"))
    n = len(d)
    # bucket LTF bars into HTF candles by wall clock; an HTF bar is only usable
    # once its final LTF bar has closed
    # pandas 3 stores this index at MICROSECOND resolution, so the old
    # nanosecond assumption collapsed 649 hourly buckets into 3.
    secs = (d.index.tz_convert("UTC").tz_localize(None)
              .astype("datetime64[s]").astype("int64").to_numpy())
    key = secs // (htf_min * 60)
    G = []
    for k, idx in pd.Series(np.arange(n), index=key).groupby(level=0):
        a, b = idx.iloc[0], idx.iloc[-1]
        G.append(dict(h=H[a:b+1].max(), l=L[a:b+1].min(), c=C[b], end=b))
    rows=[]
    for g in range(lookback, len(G)-1):
        pl = min(G[k]["l"] for k in range(g-lookback, g))
        ph = max(G[k]["h"] for k in range(g-lookback, g))
        s_lo = G[g]["l"] < pl and G[g]["c"] > pl
        s_hi = G[g]["h"] > ph and G[g]["c"] < ph
        if s_lo == s_hi: continue
        side = "long" if s_lo else "short"
        target = ph if side=="long" else pl
        i0 = G[g]["end"]
        if not np.isfinite(A[i0]) or A[i0] <= 0: continue
        htf_stop = G[g]["l"]-sl_buf*A[i0] if side=="long" else G[g]["h"]+sl_buf*A[i0]
        if entry == "htf":
            ei, ltf_stop = i0+1, htf_stop
        else:
            ei = ltf_stop = None
            for k in range(i0+1, min(i0+1+wait, n)):
                lo = L[max(0,k-conf_lb):k].min(); hi = H[max(0,k-conf_lb):k].max()
                if side=="long" and L[k]<lo and C[k]>lo:
                    ei, ltf_stop = k+1, L[k]-sl_buf*A[k]; break
                if side=="short" and H[k]>hi and C[k]<hi:
                    ei, ltf_stop = k+1, H[k]+sl_buf*A[k]; break
            if ei is None or ei>=n: continue
        stop = htf_stop if stop_mode=="htf" else (ltf_stop if stop_mode=="ltf"
               else (ltf_stop+htf_stop)/2)
        fill = O[ei]+spread/2+slip if side=="long" else O[ei]-spread/2-slip
        risk = abs(fill-stop)
        if risk<=0: continue
        if (side=="long" and target<=fill) or (side=="short" and target>=fill): continue
        why=px=None
        for k in range(ei, min(ei+max_hold, n)):
            hs = L[k]<=stop if side=="long" else H[k]>=stop
            ht = H[k]>=target if side=="long" else L[k]<=target
            if hs: why,px="sl",stop; break
            if ht: why,px="tp",target; break
        if why is None:
            k=min(ei+max_hold-1,n-1); why,px="time",C[k]
        mv = px-fill if side=="long" else fill-px
        rows.append(dict(r=mv/risk, rr=abs(target-fill)/risk, bars=k-ei))
    return pd.DataFrame(rows)

print(f"data: {len(D)} 5M bars  {D.index[0].date()} -> {D.index[-1].date()}\n")
print(f"{'setup':<6} {'variant':<22} {'n':>4} {'win%':>7} {'medRR':>7} {'expR':>8} {'med bars':>9}")
for mins,lab in ((60,"1H"),(240,"4H")):
    for vlab,kw in (("HTF entry (baseline)", dict(entry="htf")),
                    ("LTF entry + LTF stop", dict(stop_mode="ltf")),
                    ("LTF entry + HTF stop", dict(stop_mode="htf"))):
        t = run(D, mins, **kw)
        if len(t)==0: print(f"{lab:<6} {vlab:<22} none"); continue
        print(f"{lab:<6} {vlab:<22} {len(t):>4} {(t.r>0).mean()*100:>6.1f}% "
              f"{t.rr.median():>7.2f} {t.r.mean():>+8.3f} {int(t.bars.median()):>9}")
