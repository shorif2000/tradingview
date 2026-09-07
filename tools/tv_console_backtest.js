/*
 * Backtest the resting-order idea on TradingView's OWN data, in the browser.
 *
 * WHY THIS EXISTS. The rest of backtester/ reads CSVs from data/. Those are
 * fine, but they are a second source of truth: an MT5 export in broker time, a
 * TradingView export in UTC, both frozen at the moment they were downloaded. If
 * you want to know what the chart in front of you actually did, ask the chart.
 *
 * HOW TO RUN. Open the chart, open DevTools (F12) -> Console, paste this whole
 * file, then:
 *
 *     await tvbt.collect(["3","5","15"])     // pulls max history per timeframe
 *     tvbt.grid()                            // prints the results table
 *
 * WHAT IT REPLICATES. Identical rules to backtester/predict8.py:
 *   - swing levels with `piv` bars either side, still untouched when acted on
 *   - resting limit at level +/- k * ATR (BEYOND the level, never at it)
 *   - stop at the nearest swing beyond the level, floored at floor * ATR,
 *     skipped past 2.5 * ATR
 *   - target = extreme of the last `span` CLOSED calendar buckets of tgtMin
 *   - skipped if the target is further than `cap` x risk
 *   - resolution starts on the bar AFTER the fill (invariant I19)
 *
 * KNOWN LIMITS, so nobody reads more into the output than is there:
 *   - A TradingView Basic account loads roughly 5,000-7,000 bars whatever the
 *     timeframe, so finer timeframes buy you LESS history, not more. Measured:
 *     1m = 4.9 trading days, 3m = 14.5, 5m = 19.3, 15m = 66.8. Every intraday
 *     result here is one short, recent period. It cannot clear this project's
 *     usual bar of "positive in two periods of opposite direction".
 *   - Swings here require a STRICT extreme; the Python allows ties. Marginally
 *     fewer levels, same conclusions.
 *   - Spread is a flat constant. Real spread widens exactly when these setups
 *     trigger, so treat every number as an optimistic bound.
 */
window.tvbt = (() => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const data = {};

  const chart = () => {
    const api = window.TradingViewApi;
    if (!api) throw new Error("TradingViewApi missing - is this a chart page?");
    const ch = api.activeChart();
    return { ch, m: ch._chartWidget.model() };
  };
  const grab = () => {
    const { m } = chart(); const o = [];
    m.mainSeries().data().each((i, b) => { o.push([b[0], b[1], b[2], b[3], b[4]]); return false; });
    return o;
  };
  const count = () => { const { m } = chart(); let n = 0; m.mainSeries().data().each(() => { n++; return false; }); return n; };
  const modalStep = b => {
    const c = {};
    for (let i = 1; i < Math.min(b.length, 400); i++) { const d = b[i][0] - b[i - 1][0]; c[d] = (c[d] || 0) + 1; }
    return +Object.entries(c).sort((x, y) => y[1] - x[1])[0][0];
  };

  /* Collect max history for each resolution.
   *
   * The spacing check is not paranoia. setResolution() is asynchronous, and
   * grabbing too early returns the PREVIOUS timeframe's bars - which look
   * perfectly valid and are silently wrong. The first run of this produced a
   * "1 minute" series spanning three years, byte-identical to the 4-hour one.
   * Never trust a resolution switch you have not verified by bar spacing. */
  async function collect(list) {
    const want = { "1": 60, "3": 180, "5": 300, "15": 900, "60": 3600, "240": 14400, "1D": 86400 };
    const { ch, m } = chart(), ts = m.timeScale(), log = [];
    for (const res of list) {
      ch.setResolution(res);
      let ok = false;
      for (let k = 0; k < 20; k++) {
        await sleep(1500);
        const b = grab();
        if (b.length > 50 && modalStep(b) === want[res]) { ok = true; break; }
      }
      if (!ok) { log.push(res + ": resolution never settled - skipped"); continue; }
      let prev = 0, stalls = 0, rounds = 0;
      while (rounds < 40 && stalls < 4) {
        ts.scrollToFirstBar(); await sleep(1200);
        const n = count(); if (n <= prev) stalls++; else stalls = 0; prev = n; rounds++;
      }
      const b = grab(); data[res] = b;
      log.push(res + ": " + b.length + " bars, " +
        ((b.length * want[res]) / 86400).toFixed(1) + " trading days, from " +
        new Date(b[0][0] * 1000).toISOString().slice(0, 10));
    }
    console.table(log.map(l => ({ loaded: l })));
    return log;
  }

  const atrArr = (b, n = 14) => {
    const out = new Array(b.length).fill(NaN), tr = new Array(b.length).fill(NaN);
    for (let i = 1; i < b.length; i++) {
      const pc = b[i - 1][4];
      tr[i] = Math.max(b[i][2] - b[i][3], Math.abs(b[i][2] - pc), Math.abs(b[i][3] - pc));
    }
    let s = 0;
    for (let i = 1; i < b.length; i++) { s += tr[i]; if (i > n) s -= tr[i - n]; if (i >= n) out[i] = s / n; }
    return out;
  };
  const swings = (b, piv) => {
    const n = b.length, ph = new Array(n).fill(false), pl = new Array(n).fill(false);
    for (let i = piv; i < n - piv; i++) {
      let isH = true, isL = true;
      for (let j = i - piv; j <= i + piv; j++) {
        if (j === i) continue;
        if (b[j][2] >= b[i][2]) isH = false;
        if (b[j][3] <= b[i][3]) isL = false;
      }
      ph[i] = isH; pl[i] = isL;
    }
    return { ph, pl };
  };
  /* Calendar-aligned buckets, and a bucket is only emitted once the next one
   * starts - so the bucket price is inside cannot contribute to its own target.
   * That is the structural version of lookahead_off, and it is why this needs
   * no request.security equivalent. */
  const buckets = (b, minutes) => {
    const sec = minutes * 60, out = []; let start = 0, key = Math.floor(b[0][0] / sec);
    for (let i = 1; i <= b.length; i++) {
      const k = i < b.length ? Math.floor(b[i][0] / sec) : null;
      if (i === b.length || k !== key) {
        let hi = -Infinity, lo = Infinity;
        for (let j = start; j < i; j++) { if (b[j][2] > hi) hi = b[j][2]; if (b[j][3] < lo) lo = b[j][3]; }
        out.push([i - 1, hi, lo]); start = i; key = k;
      }
    }
    return out;
  };

  function run(res, tgtMin, opt) {
    opt = Object.assign({ k: 0.25, floor: 0.50, cap: 6.0, piv: 5, spread: 0.20,
                          validMin: 240, holdMin: 1200, span: 6 }, opt || {});
    const b = data[res];
    if (!b) throw new Error("no data for " + res + " - run collect() first");
    const step = modalStep(b);
    const A = atrArr(b), { ph, pl } = swings(b, opt.piv), bk = buckets(b, tgtMin);
    const validBars = Math.round(opt.validMin * 60 / step);
    const holdBars = Math.round(opt.holdMin * 60 / step);
    const n = b.length, rows = [];
    let busy = -1;
    const H = i => b[i][2], L = i => b[i][3], C = i => b[i][4];

    const target = (i, side) => {
      const done = [];
      for (let q = bk.length - 1; q >= 0 && done.length < opt.span; q--) if (bk[q][0] < i) done.push(bk[q]);
      if (!done.length) return null;
      let v = side === "long" ? -Infinity : Infinity;
      for (const d of done) v = side === "long" ? Math.max(v, d[1]) : Math.min(v, d[2]);
      return v;
    };
    const structStop = (src, side, lvl) => {
      const lo = Math.max(0, src - 200); let best = null;
      for (let x = lo; x < src; x++) {
        if (side === "long" && pl[x] && L(x) < lvl) best = best === null ? L(x) : Math.max(best, L(x));
        if (side === "short" && ph[x] && H(x) > lvl) best = best === null ? H(x) : Math.min(best, H(x));
      }
      return best;
    };

    for (let i = 60; i < n - 2; i++) {
      const src = i - opt.piv; if (src < 1) continue;
      for (const [side, isp, lvl] of [["long", pl[src], L(src)], ["short", ph[src], H(src)]]) {
        if (!isp || i <= busy) continue;
        const a = A[i]; if (!isFinite(a) || a <= 0) continue;
        let touched = false;
        for (let x = src + 1; x <= i; x++) { if (side === "long" ? L(x) < lvl : H(x) > lvl) { touched = true; break; } }
        if (touched) continue;
        const tp = target(i, side); if (tp === null) continue;
        const limit = side === "long" ? lvl - opt.k * a : lvl + opt.k * a;
        let ei = null;
        for (let j = i + 1; j < Math.min(i + 1 + validBars, n); j++) {
          if (side === "long" ? L(j) <= limit : H(j) >= limit) { ei = j; break; }
          if (side === "long" ? C(j) < limit - 0.6 * a : C(j) > limit + 0.6 * a) break;
        }
        if (ei === null) continue;
        const fill = side === "long" ? limit + opt.spread / 2 : limit - opt.spread / 2;
        const sv = structStop(src, side, lvl), mn = opt.floor * a;
        let stop = sv === null ? (side === "long" ? fill - mn : fill + mn)
                               : (side === "long" ? sv - 0.10 * a : sv + 0.10 * a);
        if (Math.abs(fill - stop) < mn) stop = side === "long" ? fill - mn : fill + mn;
        if (Math.abs(fill - stop) > 2.5 * a) continue;
        const risk = Math.abs(fill - stop); if (risk <= 0) continue;
        if (side === "long" ? tp <= fill : tp >= fill) continue;
        const rr = Math.abs(tp - fill) / risk; if (rr > opt.cap) continue;
        let why = null, px = null, m = ei + 1;
        for (m = ei + 1; m < Math.min(ei + holdBars, n); m++) {
          const hs = side === "long" ? L(m) <= stop : H(m) >= stop;
          const ht = side === "long" ? H(m) >= tp : L(m) <= tp;
          if (hs) { why = "sl"; px = stop; break; }
          if (ht) { why = "tp"; px = tp; break; }
        }
        if (!why) { m = Math.min(ei + holdBars - 1, n - 1); why = "time"; px = C(m); }
        const mv = side === "long" ? px - fill : fill - px;
        rows.push({ r: mv / risk, rr, risk, why, mins: (m - ei) * step / 60, side });
        busy = m;
      }
    }
    return rows;
  }

  // Deterministic bootstrap, so two runs of the same data agree.
  const boot = (r, n = 4000) => {
    if (r.length < 5) return [NaN, NaN, NaN];
    let seed = 13; const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
    const ms = [];
    for (let i = 0; i < n; i++) { let s = 0; for (let j = 0; j < r.length; j++) s += r[Math.floor(rnd() * r.length)]; ms.push(s / r.length); }
    ms.sort((a, b) => a - b);
    return [ms[Math.floor(n * 0.025)], ms[Math.floor(n * 0.975)], ms.filter(x => x <= 0).length / n];
  };

  function grid(levels, targets) {
    levels = levels || Object.keys(data);
    targets = targets || [[60, "1H"], [240, "4H"], [1440, "Daily"]];
    const out = [];
    for (const res of levels) for (const [tgt, tn] of targets) {
      const tr = run(res, tgt), r = tr.map(x => x.r);
      if (r.length < 5) { out.push({ levels: res + "m", target: tn, n: r.length, note: "too few" }); continue; }
      const mean = r.reduce((a, b) => a + b, 0) / r.length;
      const [lo, hi, p] = boot(r);
      const srt = [...r].sort((a, b) => b - a), t3 = srt.slice(3);
      const risks = tr.map(x => x.risk).sort((a, b) => a - b);
      out.push({ levels: res + "m", target: tn, n: r.length, R: +mean.toFixed(3),
        win: +(r.filter(x => x > 0).length / r.length * 100).toFixed(1),
        CI: "[" + lo.toFixed(2) + "," + hi.toFixed(2) + "]", P_no_edge: +(p * 100).toFixed(1),
        // If removing three trades flips the sign, the row was three trades.
        minusTop3: +(t3.reduce((a, b) => a + b, 0) / t3.length).toFixed(3),
        medStop: +risks[Math.floor(risks.length / 2)].toFixed(2) });
    }
    console.table(out);
    return out;
  }

  // Spread as a share of the stop. This is the number that kills fine
  // timeframes: cost is fixed in dollars while the stop shrinks with ATR.
  function costs(spread = 0.20) {
    const out = [];
    for (const res of Object.keys(data)) {
      const b = data[res], a = atrArr(b).filter(isFinite).sort((x, y) => x - y);
      const med = a[Math.floor(a.length / 2)];
      out.push({ res, medATR: +med.toFixed(2), stop_050ATR: +(0.5 * med).toFixed(2),
        spread_pct_of_stop: +(spread / (0.5 * med) * 100).toFixed(1) });
    }
    console.table(out);
    return out;
  }

  return { collect, run, grid, costs, data, sleep };
})();
console.log('tvbt ready. Try:  await tvbt.collect(["3","5","15"])  then  tvbt.grid()');
