"""
XAU Regime Scalper — backtest engine.

Faithful Python port of the Pine v6 strategy 'XAU Regime Scalper 5M'.
Indicator maths deliberately mirrors TradingView's `ta.*` functions so that
results are comparable with the Strategy Tester.

Model of reality
----------------
* Input data is assumed to be BID prices (what brokers ship).
* Longs enter at ask  = close + spread ; exit at bid.
* Shorts enter at bid = close - spread ; exit at ask.
* Signal is computed on the CLOSE of bar i, position opens at that close
  (matches process_orders_on_close=true in Pine).
* Stop/target are live from bar i+1 onwards.
* If a bar's range contains BOTH the stop and the target, the STOP is assumed
  to fill first (pessimistic; without tick data you cannot know the order).
* 0.01 lot on XAUUSD = 1 troy ounce -> $1 P/L per $1 of price move.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from dataclasses import dataclass, field


# ═════════════════════════════════════════════════════════════════════════════
#  TradingView-equivalent indicator maths
# ═════════════════════════════════════════════════════════════════════════════
def _seeded_ewm(s: pd.Series, n: int, alpha: float) -> pd.Series:
    """
    Pine-exact exponential smoothing.

    TradingView seeds ta.ema / ta.rma with the SMA of the first `n` values and
    only then applies the recursion. pandas' ewm(adjust=False) instead seeds with
    the first observation, which leaves a lasting offset on long lengths such as
    EMA200. This reproduces Pine so the Python results line up with the
    Strategy Tester.
    """
    v = s.to_numpy(dtype=float)
    out = np.full(v.shape, np.nan)
    valid = np.flatnonzero(~np.isnan(v))
    if valid.size == 0 or valid[0] + n > v.size:
        return pd.Series(out, index=s.index)
    start = valid[0]
    prev = float(np.nanmean(v[start:start + n]))
    out[start + n - 1] = prev
    for i in range(start + n, v.size):
        x = v[i]
        if np.isnan(x):
            x = prev
        prev = prev + alpha * (x - prev)
        out[i] = prev
    return pd.Series(out, index=s.index)


def ema(s: pd.Series, n: int) -> pd.Series:
    """ta.ema — alpha = 2/(n+1), SMA-seeded."""
    return _seeded_ewm(s, n, 2.0 / (n + 1.0))


def rma(s: pd.Series, n: int) -> pd.Series:
    """ta.rma / Wilder smoothing — alpha = 1/n, SMA-seeded."""
    return _seeded_ewm(s, n, 1.0 / n)


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def stdev(s: pd.Series, n: int) -> pd.Series:
    """ta.stdev — population (biased) standard deviation."""
    return s.rolling(n).std(ddof=0)


def true_range(h: pd.Series, l: pd.Series, c: pd.Series) -> pd.Series:
    pc = c.shift(1)
    return pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)


def atr(h, l, c, n: int) -> pd.Series:
    return rma(true_range(h, l, c), n)


def rsi(c: pd.Series, n: int) -> pd.Series:
    d = c.diff()
    up = rma(d.clip(lower=0.0), n)
    dn = rma((-d).clip(lower=0.0), n)
    rs = up / dn.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    out[dn == 0] = 100.0
    out[(up == 0) & (dn > 0)] = 0.0
    return out


def dmi(h, l, c, di_len: int, adx_smooth: int):
    """ta.dmi -> (+DI, -DI, ADX), Wilder."""
    up_move = h.diff()
    dn_move = -l.diff()
    plus_dm = np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0)
    tr_rma = rma(true_range(h, l, c), di_len)
    plus_di = 100.0 * rma(pd.Series(plus_dm, index=h.index), di_len) / tr_rma
    minus_di = 100.0 * rma(pd.Series(minus_dm, index=h.index), di_len) / tr_rma
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return plus_di, minus_di, rma(dx.fillna(0.0), adx_smooth)


def percentrank(s: pd.Series, n: int) -> pd.Series:
    """ta.percentrank — % of the previous n values that are <= the current value."""
    vals = s.to_numpy(dtype=float)
    out = np.full(vals.shape, np.nan)
    for i in range(n, len(vals)):
        win = vals[i - n:i]
        cur = vals[i]
        if np.isnan(cur) or np.isnan(win).any():
            continue
        out[i] = (win <= cur).sum() / n * 100.0
    return pd.Series(out, index=s.index)


def pivot_high(h: pd.Series, left: int, right: int) -> pd.Series:
    """ta.pivothigh — value confirmed `right` bars after the pivot bar."""
    v = h.to_numpy(dtype=float)
    out = np.full(v.shape, np.nan)
    for i in range(left + right, len(v)):
        p = i - right
        win = v[p - left:p + right + 1]
        if v[p] == win.max() and (win == v[p]).sum() == 1:
            out[i] = v[p]
    return pd.Series(out, index=h.index)


def pivot_low(l: pd.Series, left: int, right: int) -> pd.Series:
    v = l.to_numpy(dtype=float)
    out = np.full(v.shape, np.nan)
    for i in range(left + right, len(v)):
        p = i - right
        win = v[p - left:p + right + 1]
        if v[p] == win.min() and (win == v[p]).sum() == 1:
            out[i] = v[p]
    return pd.Series(out, index=l.index)


def bars_since(cond: pd.Series) -> pd.Series:
    """ta.barssince — bars elapsed since cond was last true (large int if never)."""
    c = cond.fillna(False).to_numpy(dtype=bool)
    out = np.full(c.shape, 10 ** 6, dtype=np.int64)
    last = -1
    for i in range(len(c)):
        if c[i]:
            last = i
        out[i] = (i - last) if last >= 0 else 10 ** 6
    return pd.Series(out, index=cond.index)


# ═════════════════════════════════════════════════════════════════════════════
#  Configuration
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class Config:
    # account / costs
    start_balance_gbp: float = 100.0
    lots: float = 0.01                  # 0.01 lot = 1 oz
    oz_per_lot: float = 100.0
    spread_usd: float = 0.25            # full spread in USD per oz
    slip_stop_usd: float = 0.05         # extra adverse slippage on stop fills
    commission_gbp_per_trade: float = 0.0
    gbpusd: float = 1.27                # USD -> GBP conversion
    swap_per_night_usd: float = 0.0     # swap-free account
    leverage: float = 500.0             # for the margin check
    ruin_level_gbp: float = 0.0         # trading halts at or below this balance

    # ── chart timeframe ──────────────────────────────────────────────────────
    #  Every setting below is calibrated on 5-minute bars. Point this at your
    #  actual chart timeframe and the engine rescales itself: bar-count settings
    #  stretch so they still span the same amount of TIME, and the ATR used for
    #  sizing is converted to its 5-minute equivalent (range grows with the
    #  square root of time). Without this, a 2-minute chart runs the same
    #  numbers over 2/5 of the history and produces far more, far worse signals.
    tf_minutes: float = 5.0

    # session / volatility
    use_session: bool = True
    sess_start: int = 7                 # inclusive, local hour
    sess_end: int = 20                  # exclusive
    tz: str = "Europe/London"
    block_fri_pm: bool = True
    atr_len: int = 14
    min_atr_pct: float = 0.020
    max_atr_pct: float = 0.250

    # regime
    adx_len: int = 14
    adx_smooth: int = 14
    adx_trend_on: float = 23.0
    adx_trend_off: float = 18.0
    adx_range_on: float = 18.0
    adx_range_off: float = 23.0
    bbw_rank_max: float = 45.0
    use_htf: bool = True
    htf_ema_fast: int = 50
    htf_ema_slow: int = 200

    # trend module
    ema_fast: int = 20
    ema_mid: int = 50
    ema_slow: int = 200
    pb_tol_atr: float = 0.35
    pb_lookback: int = 6
    trend_min_score: int = 2

    # range module
    bb_len: int = 20
    bb_mult: float = 2.0
    rsi_fast_len: int = 7
    rsi_os: float = 22.0
    rsi_ob: float = 78.0
    don_len: int = 50
    don_tol_atr: float = 0.15   # range-extreme tag tolerance
    range_min_score: int = 2
    use_div: bool = True

    # risk
    sl_pad_atr: float = 0.35
    swing_len: int = 8
    min_stop_atr: float = 0.80
    max_stop_atr: float = 2.50
    rr: float = 2.0
    use_be: bool = False

    # ── exit management ──────────────────────────────────────────────────────
    #  fixed   one target at rr, one stop. Original behaviour.
    #  staged  ONE position, so it works at 0.01 lot: the stop ratchets forward
    #          as price advances - to break-even at be_at_r, then to +lock_to_r
    #          at lock_at_r - and the final target sits at tp3_r. Raises the
    #          share of trades that do not lose without splitting the position.
    #  partial scale out at tp1/tp2/tp3. REQUIRES lots >= 0.03, because 0.01 is
    #          the broker minimum and cannot be divided.
    exit_mode: str = "fixed"
    tp1_r: float = 1.0
    tp2_r: float = 2.0
    tp3_r: float = 3.0
    lot_step_oz: float = 1.0    # 0.01 lot = 1 oz: partial closes come in whole
    #                             steps of this, never fractions of it
    tp1_frac: float = 0.34
    tp2_frac: float = 0.33
    be_at_r: float = 1.0        # move stop to entry once price is this far ahead
    be_offset_r: float = 0.0    # push it past entry to cover costs
    lock_at_r: float = 2.0      # then ratchet the stop to...
    lock_to_r: float = 1.0      # ...this much locked in
    trail_mode: str = "none"    # none | atr | swing
    trail_start_r: float = 1.0
    trail_atr_mult: float = 1.5

    use_time_stop: bool = True
    time_stop_bars: int = 60
    max_trades_day: int = 6
    max_loss_day_gbp: float = 6.0
    piv_len: int = 5

    # ── liquidity (BSL / SSL) ────────────────────────────────────────────────
    liq_eq_tol_atr: float = 0.30    # pivots within this many ATR are the "same" pool
    liq_max_age: int = 400          # bars a pool stays live before it is forgotten
    liq_max_pools: int = 24         # keep only the most recent pools per side
    sweep_min_touches: int = 2      # 2 = equal highs/lows; 1 = any single swing
    sweep_lookback: int = 3         # bars after the grab in which an entry may fire
    sweep_min_score: int = 2

    # ── SMC: order blocks and market-structure shifts ────────────────────────
    #  An order block is the last opposing candle before an impulsive move -
    #  where institutions were filling before price ran. Price returning to it
    #  is a high-quality entry area. BOS = break of structure (trend continues);
    #  CHoCH = change of character, the first break the other way.
    use_order_blocks: bool = True
    ob_impulse_bars: int = 3        # bars the impulse must cover
    ob_impulse_atr: float = 1.2     # and how far it must travel, in ATR
    ob_max_age: int = 300
    ob_max_blocks: int = 12
    conf_order_block: bool = False  # OFF: as a scoring vote this measurably
    #                                 diluted the signal (+0.24R vs +0.29R without).
    #                                 Order blocks earn their keep as DRAWN zones
    #                                 and as limit-order anchors, not as votes.
    conf_bos: bool = False          # OFF: worse still on its own (-0.03R).

    # ── breakout module ──────────────────────────────────────────────────────
    #  The mirror image of the sweep module. A SWEEP is price poking through a
    #  level and closing back - trade the reversal. A BREAKOUT is price closing
    #  decisively THROUGH it and holding - trade the continuation. Same event,
    #  opposite resolution, so the two can never fire on the same bar.
    #
    #  Direction comes from which side broke: buy-side liquidity taken and held
    #  = long, sell-side = short. This is the only module that trades WITH the
    #  move rather than against it.
    #  MEASURED: 26 trades, -0.014R, net -£3 across all three samples, and
    #  switching it on drags the whole system from +0.368R to +0.281R because it
    #  takes the slot a better setup would have used. Off by default; the toggle
    #  is here because a breakout module is the obvious thing to want, and this
    #  is what it actually did.
    use_breakout_module: bool = False
    breakout_min_touches: int = 2      # only levels defended more than once
    breakout_min_score: int = 2
    breakout_expansion_rank: float = 55.0   # BB-width percentile floor
    breakout_close_frac: float = 0.6   # close must land in this part of the range

    # ── higher-timeframe bias ────────────────────────────────────────────────
    #  Structure and order blocks read from a slower chart and applied as a
    #  GATE, not as another scoring vote. Only the last CLOSED higher-timeframe
    #  bar is ever consulted, so nothing here can see the future.
    # ── multi-timeframe trend, derived from the chart's own bars ─────────────
    #  H1 / H4 / Daily trend worked out by resampling the timestamps you are
    #  already on - no extra data feed needed. Each is EMA50 vs EMA200 on that
    #  timeframe, shifted one bar so only CLOSED candles are ever read.
    #  mtf_min_agree = how many of the three must agree with the trade direction
    #  (0 disables the filter and leaves it as on-screen context only).
    use_mtf_trend: bool = True        # compute it (cheap, and it is worth seeing)
    mtf_min_agree: int = 0            # 0 = context only, 1-3 = act as a filter
    #  MEASURED: requiring even ONE higher timeframe to agree dropped the system
    #  from +0.368R to +0.027R; requiring two took it negative (-0.128R). These
    #  are mean-reversion entries - demanding trend agreement removes the very
    #  trades that pay. Left at 0 so the trend is shown, not enforced.
    mtf_frames: tuple = (60, 240, 1440)
    mtf_fast: int = 20
    mtf_slow: int = 50
    #  20/50 rather than 50/200 on purpose: a 200-period EMA on the DAILY frame
    #  needs 200 days of bars, which almost no export contains. 20/50 is a
    #  standard trend read that H1 and H4 can actually support. Any frame that
    #  still lacks the history reports 0 (unknown) instead of guessing.
    #  A 200-period EMA on the DAILY frame needs 200 days of bars. Feed the
    #  engine three weeks and that frame simply cannot be known - it reports 0
    #  (unknown) rather than guessing, and mtf_score reflects only the frames
    #  that genuinely have the history behind them.

    use_htf_structure: bool = False   # only trade with higher-timeframe structure
    use_htf_ob: bool = False          # only trade from a higher-timeframe zone
    htf_bias_minutes: int = 60        # 60 = H1, 240 = H4

    # ── pending limit entries ────────────────────────────────────────────────
    #  Entering at market on the signal bar assumes an instant fill. Trading by
    #  hand from a phone that is fiction: a 60-second delay measured on this
    #  data removes most of the edge. A resting limit order removes the race -
    #  either price comes back to your level, or you simply do not trade.
    entry_mode: str = "market"      # market | limit
    limit_offset_atr: float = 0.25  # how far back from the signal close to rest
    limit_expiry_bars: int = 6      # cancel if unfilled after this many bars
    limit_to_ob: bool = True        # prefer the order-block edge where there is one

    # ── re-entry layering ────────────────────────────────────────────────────
    #  Extra positions deeper into the move. Each is a SEPARATE 0.01 lot, so N
    #  layers means N times the risk. That needs account size, not optimism,
    #  which is why it is off by default.
    use_layering: bool = False
    max_layers: int = 2             # extra entries beyond the first
    layer_spacing_atr: float = 0.6

    # ── which modules are allowed to trade ───────────────────────────────────
    use_sweep_module: bool = True
    use_trend_module: bool = False   # off by default: ~zero expectancy in both
    use_range_module: bool = True    #   tested samples. See README.

    # ── which filters are active ─────────────────────────────────────────────
    use_volatility_filter: bool = True
    use_daily_limits: bool = True

    # ── which confirmations may score a point ────────────────────────────────
    conf_ema_reclaim: bool = True      # close crossing back through the fast EMA
    conf_engulfing: bool = True        # bullish / bearish engulfing candle
    conf_pin_bar: bool = True          # hammer / shooting star / long-wick pin
    conf_rsi_50_cross: bool = True     # RSI(14) crossing the midline
    conf_structure: bool = True        # higher low / lower high
    conf_di_expansion: bool = True     # +DI or -DI pulling away and rising
    conf_rsi_extreme: bool = True      # fast RSI oversold / overbought
    conf_divergence: bool = True       # price/RSI divergence at a swing
    #  MEASURED: adding these three as scoring votes took the system from
    #  +0.368R to +0.228R and pushed drawdown from 36% to 55%. Not because the
    #  patterns are meaningless, but because every extra way to reach the score
    #  minimum lets a weaker setup through. Same effect the SMC votes had. They
    #  are detected and drawn; they just do not get a vote by default.
    conf_star: bool = False            # morning star / evening star
    conf_tweezer: bool = False         # tweezer top / bottom
    conf_harami: bool = False          # bullish / bearish harami

    # ── require a reversal, rather than merely counting one ─────────────────
    #  Adding reversal patterns as scoring VOTES made things worse: every extra
    #  way to reach the score minimum lets a weaker setup through. REQUIRING one
    #  is the opposite operation - it raises the bar instead of lowering it.
    #  Fewer signals, but every one has a candle that actually turned.
    require_reversal: bool = False
    conf_bb_failure: bool = True       # poked outside a band and closed back in
    conf_range_extreme: bool = True    # tagging the Donchian floor / ceiling
    conf_sweep_reclaim: bool = True    # closed back through the swept level
    conf_ema_side: bool = True         # back on the right side of the fast EMA
    conf_liq_in_range: bool = True     # credit a sweep inside the range module


@dataclass
class Trade:
    module: str
    side: str
    why: str
    entry_time: pd.Timestamp
    entry: float
    sl: float
    tp: float
    risk_usd: float
    exit_time: pd.Timestamp = None
    exit: float = None
    reason: str = ""
    pnl_usd: float = 0.0
    pnl_gbp: float = 0.0
    r_multiple: float = 0.0
    bars_held: int = 0
    partials: int = 0
    layers: int = 1
    entry_kind: str = "market"
    balance_after: float = 0.0
    ambiguous: bool = False
    adx: float = 0.0
    atr: float = 0.0


# ═════════════════════════════════════════════════════════════════════════════
#  Liquidity — BSL (buy-side) and SSL (sell-side)
# ═════════════════════════════════════════════════════════════════════════════
#  BSL sits ABOVE swing highs: that is where the stop-losses of shorts and the
#  buy-stops of breakout traders are parked. SSL sits BELOW swing lows for the
#  mirror reason. Price is drawn to these pools because that is where the orders
#  are — the tradable event is not the pool itself but the SWEEP: price spikes
#  through, fills those orders, and immediately closes back. That failed
#  breakout is a liquidity grab, and it is one of the higher-quality reversal
#  signals on gold.
#
#  A pool touched more than once ("equal highs" / "equal lows") holds more
#  resting orders than a single swing, so touch count is tracked as strength.
# ═════════════════════════════════════════════════════════════════════════════
def build_liquidity(d: pd.DataFrame, cfg: Config, pv_h: np.ndarray, pv_l: np.ndarray,
                    P: dict | None = None) -> pd.DataFrame:
    P = P or _scaled(cfg)
    n = len(d)
    high = d["high"].to_numpy(float)
    low = d["low"].to_numpy(float)
    close = d["close"].to_numpy(float)
    atr_a = d["atr"].to_numpy(float)

    bsl: list[dict] = []      # active buy-side pools (above price)
    ssl: list[dict] = []      # active sell-side pools (below price)

    out = {k: np.full(n, np.nan) for k in
           ("bsl_price", "ssl_price", "bsl_touch", "ssl_touch",
            "sweep_bsl_price", "sweep_ssl_price")}
    out["sweep_bsl_str"] = np.zeros(n)
    out["sweep_ssl_str"] = np.zeros(n)
    out["sweep_bsl_wick"] = np.full(n, np.nan)
    out["sweep_ssl_wick"] = np.full(n, np.nan)
    out["bsl_broken"] = np.zeros(n, dtype=bool)
    out["bsl_break_lvl"] = np.full(n, np.nan)
    out["ssl_break_lvl"] = np.full(n, np.nan)
    out["bsl_break_tch"] = np.zeros(n)
    out["ssl_break_tch"] = np.zeros(n)
    out["ssl_broken"] = np.zeros(n, dtype=bool)

    for i in range(n):
        a = atr_a[i]
        if np.isnan(a) or a <= 0:
            continue
        tol = cfg.liq_eq_tol_atr * a

        # ── 1. register newly confirmed pivots as pools ─────────────────────
        if not np.isnan(pv_h[i]):
            p = float(pv_h[i])
            for pool in bsl:
                if abs(pool["price"] - p) <= tol:
                    pool["price"] = max(pool["price"], p)   # sweep must clear them all
                    pool["touch"] += 1
                    pool["bar"] = i
                    break
            else:
                bsl.append({"price": p, "touch": 1, "bar": i})
        if not np.isnan(pv_l[i]):
            p = float(pv_l[i])
            for pool in ssl:
                if abs(pool["price"] - p) <= tol:
                    pool["price"] = min(pool["price"], p)
                    pool["touch"] += 1
                    pool["bar"] = i
                    break
            else:
                ssl.append({"price": p, "touch": 1, "bar": i})

        # ── 2. test this bar against every live pool ────────────────────────
        keep_b, sw_b_price, sw_b_str, broke_b = [], np.nan, 0.0, False
        brk_b_lvl, brk_b_tch = np.nan, 0.0
        for pool in bsl:
            if i - pool["bar"] > P["liq_max_age"]:
                continue
            if high[i] > pool["price"] + tol:
                if close[i] < pool["price"]:
                    # pierced well beyond and rejected -> liquidity grab
                    if pool["touch"] >= sw_b_str or np.isnan(sw_b_price):
                        sw_b_price, sw_b_str = pool["price"], max(sw_b_str, pool["touch"])
                else:
                    broke_b = True            # genuine break, pool is gone
                    brk_b_lvl, brk_b_tch = pool["price"], max(brk_b_tch, pool["touch"])
                continue                      # either way the pool is consumed
            if high[i] > pool["price"]:
                # marginal poke -> the level is being probed, liquidity builds
                pool["touch"] += 1
                pool["price"] = max(pool["price"], high[i])
                pool["bar"] = i
            keep_b.append(pool)
        bsl = keep_b[-cfg.liq_max_pools:]

        keep_s, sw_s_price, sw_s_str, broke_s = [], np.nan, 0.0, False
        brk_s_lvl, brk_s_tch = np.nan, 0.0
        for pool in ssl:
            if i - pool["bar"] > P["liq_max_age"]:
                continue
            if low[i] < pool["price"] - tol:
                if close[i] > pool["price"]:
                    if pool["touch"] >= sw_s_str or np.isnan(sw_s_price):
                        sw_s_price, sw_s_str = pool["price"], max(sw_s_str, pool["touch"])
                else:
                    broke_s = True
                    brk_s_lvl, brk_s_tch = pool["price"], max(brk_s_tch, pool["touch"])
                continue
            if low[i] < pool["price"]:
                pool["touch"] += 1
                pool["price"] = min(pool["price"], low[i])
                pool["bar"] = i
            keep_s.append(pool)
        ssl = keep_s[-cfg.liq_max_pools:]

        out["sweep_bsl_price"][i], out["sweep_bsl_str"][i] = sw_b_price, sw_b_str
        out["sweep_ssl_price"][i], out["sweep_ssl_str"][i] = sw_s_price, sw_s_str
        if sw_b_str > 0:
            out["sweep_bsl_wick"][i] = high[i]
        if sw_s_str > 0:
            out["sweep_ssl_wick"][i] = low[i]
        out["bsl_broken"][i], out["ssl_broken"][i] = broke_b, broke_s
        out["bsl_break_lvl"][i], out["bsl_break_tch"][i] = brk_b_lvl, brk_b_tch
        out["ssl_break_lvl"][i], out["ssl_break_tch"][i] = brk_s_lvl, brk_s_tch

        # ── 3. nearest live pool either side (context / optional targets) ───
        above = [p for p in bsl if p["price"] > close[i]]
        below = [p for p in ssl if p["price"] < close[i]]
        if above:
            nb = min(above, key=lambda p: p["price"] - close[i])
            out["bsl_price"][i], out["bsl_touch"][i] = nb["price"], nb["touch"]
        if below:
            nsl = min(below, key=lambda p: close[i] - p["price"])
            out["ssl_price"][i], out["ssl_touch"][i] = nsl["price"], nsl["touch"]

    for k, v in out.items():
        d[k] = v

    def carry(str_a, price_a, wick_a):
        cur_l = cur_w = np.nan
        cur_s, cur_b = 0.0, -1
        L = np.full(n, np.nan); W = np.full(n, np.nan)
        S = np.zeros(n);        B = np.full(n, -1, dtype=np.int64)
        for i in range(n):
            if str_a[i] > 0:
                expired = (cur_b < 0) or (i - cur_b > P["sweep_lookback"])
                if expired or str_a[i] >= cur_s:
                    cur_l, cur_w, cur_s, cur_b = price_a[i], wick_a[i], str_a[i], i
            live = (cur_b >= 0) and (i - cur_b <= P["sweep_lookback"])
            if live:
                L[i], W[i], S[i], B[i] = cur_l, cur_w, cur_s, cur_b
        return L, W, S, B

    bl, bw, bs, bb = carry(out["sweep_bsl_str"], out["sweep_bsl_price"], out["sweep_bsl_wick"])
    sl_, sw, ss, sb = carry(out["sweep_ssl_str"], out["sweep_ssl_price"], out["sweep_ssl_wick"])
    d["sweep_bsl_lvl"], d["grab_bsl_wick"], d["recent_bsl_str"], d["grab_bsl_bar"] = bl, bw, bs, bb
    d["sweep_ssl_lvl"], d["grab_ssl_wick"], d["recent_ssl_str"], d["grab_ssl_bar"] = sl_, sw, ss, sb
    return d


# ═════════════════════════════════════════════════════════════════════════════
#  SMART MONEY CONCEPTS — order blocks, BOS and CHoCH
# ═════════════════════════════════════════════════════════════════════════════
#  ORDER BLOCK: the last opposing candle before an impulsive move. The theory is
#  that size was being filled there before price ran, leaving unfilled interest
#  behind; price returning to that zone is where the remainder gets worked. It
#  is also, practically, a well-defined level to rest a limit order on.
#
#  BOS  (break of structure)  price takes out the last swing in the direction it
#                             was already going - the trend is continuing.
#  CHoCH (change of character) the FIRST break against the prevailing direction
#                             - the earliest structural warning of a reversal.
# ═════════════════════════════════════════════════════════════════════════════
def build_smc(d: pd.DataFrame, cfg: Config, ph: pd.Series, pl: pd.Series, P: dict) -> pd.DataFrame:
    n = len(d)
    o = d["open"].to_numpy(float); h = d["high"].to_numpy(float)
    l = d["low"].to_numpy(float);  c = d["close"].to_numpy(float)
    a5 = d["atr5"].to_numpy(float)
    imp = max(2, P["ob_impulse_bars"])

    bull_ob: list[dict] = []
    bear_ob: list[dict] = []
    cols = {k: np.full(n, np.nan) for k in
            ("ob_bull_top", "ob_bull_bot", "ob_bear_top", "ob_bear_bot")}
    in_bull = np.zeros(n, bool); in_bear = np.zeros(n, bool)
    bos_up = np.zeros(n, bool); bos_dn = np.zeros(n, bool)
    choch_up = np.zeros(n, bool); choch_dn = np.zeros(n, bool)
    sdir = np.zeros(n, np.int8)

    last_ph = last_pl = np.nan
    pv_h = ph.to_numpy(); pv_l = pl.to_numpy()
    direction = 0

    for i in range(n):
        if not np.isnan(pv_h[i]):
            last_ph = pv_h[i]
        if not np.isnan(pv_l[i]):
            last_pl = pv_l[i]

        # ── structure: BOS continues the direction, CHoCH reverses it ───────
        if not np.isnan(last_ph) and c[i] > last_ph:
            if direction >= 0:
                bos_up[i] = True
            else:
                choch_up[i] = True
            direction = 1
            last_ph = np.nan
        elif not np.isnan(last_pl) and c[i] < last_pl:
            if direction <= 0:
                bos_dn[i] = True
            else:
                choch_dn[i] = True
            direction = -1
            last_pl = np.nan
        sdir[i] = direction

        # ── order blocks: find the last opposing candle before an impulse ───
        if cfg.use_order_blocks and i >= imp + 1 and not np.isnan(a5[i]) and a5[i] > 0:
            move = c[i] - c[i - imp]
            if move >= cfg.ob_impulse_atr * a5[i]:
                for k in range(i - 1, i - imp - 1, -1):
                    if c[k] < o[k]:
                        bull_ob.append({"top": max(o[k], c[k]), "bot": l[k], "bar": i})
                        break
            elif -move >= cfg.ob_impulse_atr * a5[i]:
                for k in range(i - 1, i - imp - 1, -1):
                    if c[k] > o[k]:
                        bear_ob.append({"top": h[k], "bot": min(o[k], c[k]), "bar": i})
                        break
            bull_ob = [b for b in bull_ob if i - b["bar"] <= cfg.ob_max_age
                       and c[i] > b["bot"]][-cfg.ob_max_blocks:]
            bear_ob = [b for b in bear_ob if i - b["bar"] <= cfg.ob_max_age
                       and c[i] < b["top"]][-cfg.ob_max_blocks:]

        below = [b for b in bull_ob if b["top"] <= c[i]]
        above = [b for b in bear_ob if b["bot"] >= c[i]]
        if below:
            nb = max(below, key=lambda b: b["top"])
            cols["ob_bull_top"][i], cols["ob_bull_bot"][i] = nb["top"], nb["bot"]
        if above:
            nb = min(above, key=lambda b: b["bot"])
            cols["ob_bear_top"][i], cols["ob_bear_bot"][i] = nb["top"], nb["bot"]
        in_bull[i] = any(b["bot"] <= l[i] <= b["top"] or b["bot"] <= c[i] <= b["top"] for b in bull_ob)
        in_bear[i] = any(b["bot"] <= h[i] <= b["top"] or b["bot"] <= c[i] <= b["top"] for b in bear_ob)

    for k, v in cols.items():
        d[k] = v
    d["in_bull_ob"], d["in_bear_ob"] = in_bull, in_bear
    d["bos_up"], d["bos_dn"] = bos_up, bos_dn
    d["choch_up"], d["choch_dn"] = choch_up, choch_dn
    d["struct_dir"] = sdir
    return d


def attach_htf_bias(d: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """
    Read structure and order blocks from a slower chart and map them back.

    Every value is shifted by one higher-timeframe bar before use, so a 5-minute
    bar at 10:05 is judged against the H1 candle that CLOSED at 10:00 and never
    against the one still forming. Without that shift this would quietly leak
    the future into every signal and the backtest would look wonderful.
    """
    m = f"{cfg.htf_bias_minutes}min"
    htf = d.resample(m).agg({"open": "first", "high": "max", "low": "min",
                             "close": "last"}).dropna()
    if len(htf) < 30:
        d["htf_dir"] = 0
        d["htf_in_bull_ob"] = True
        d["htf_in_bear_ob"] = True
        return d

    hcfg = Config(**{**cfg.__dict__, "tf_minutes": float(cfg.htf_bias_minutes),
                     "use_htf_structure": False, "use_htf_ob": False})
    HP = _scaled(hcfg)
    htf["atr"] = atr(htf["high"], htf["low"], htf["close"], HP["atr_len"])
    htf["atr5"] = htf["atr"]
    hp = pivot_high(htf["high"], HP["piv_len"], HP["piv_len"])
    hl = pivot_low(htf["low"], HP["piv_len"], HP["piv_len"])
    htf = build_smc(htf, hcfg, hp, hl, HP)

    # one full higher-timeframe bar of lag = only closed candles are visible
    keep = htf[["struct_dir", "ob_bull_top", "ob_bull_bot",
                "ob_bear_top", "ob_bear_bot"]].shift(1)
    keep = keep.reindex(d.index, method="ffill")
    d["htf_dir"] = keep["struct_dir"].fillna(0).astype(int)
    lo, hi = d["low"], d["high"]
    d["htf_in_bull_ob"] = ((lo <= keep["ob_bull_top"]) & (hi >= keep["ob_bull_bot"])).fillna(False)
    d["htf_in_bear_ob"] = ((hi >= keep["ob_bear_bot"]) & (lo <= keep["ob_bear_top"])).fillna(False)
    return d


# ═════════════════════════════════════════════════════════════════════════════
#  Feature construction
# ═════════════════════════════════════════════════════════════════════════════
def _scaled(cfg: Config):
    """Bar-count settings restated for the active timeframe."""
    # CLAMPED AT 1.0. This factor exists to STRETCH the 5-minute calibration onto
    # a FASTER chart. Above 5m there is nothing to stretch - the bar counts are
    # already meaningful and the ATR is genuinely larger. Unclamped, a 1h chart
    # gave k = 0.083, which collapsed EMA200 to EMA17, the swing pivot to 2 bars,
    # and scaled the sizing ATR by 0.29, so it read 2-bar noise as structure.
    k = max(5.0 / max(cfg.tf_minutes, 0.1), 1.0)   # 2m -> 2.5, 3m -> 1.667, 5m+ -> 1.0
    r = lambda v, lo=2: max(lo, int(round(v * k)))
    return dict(k=k,
                atr_len=r(cfg.atr_len), adx_len=r(cfg.adx_len), adx_smooth=r(cfg.adx_smooth),
                ema_fast=r(cfg.ema_fast), ema_mid=r(cfg.ema_mid), ema_slow=r(cfg.ema_slow),
                bb_len=r(cfg.bb_len), rsi_fast_len=r(cfg.rsi_fast_len), rsi_len=r(14),
                don_len=r(cfg.don_len), swing_len=r(cfg.swing_len), piv_len=r(cfg.piv_len),
                pb_lookback=r(cfg.pb_lookback), liq_max_age=r(cfg.liq_max_age),
                time_stop_bars=r(cfg.time_stop_bars), sweep_lookback=r(cfg.sweep_lookback),
                rank_len=r(200), ob_impulse_bars=r(cfg.ob_impulse_bars),
                limit_expiry_bars=r(cfg.limit_expiry_bars))


def build_features(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    P = _scaled(cfg)
    d = df.copy()
    h, l, c, o = d["high"], d["low"], d["close"], d["open"]

    d["atr"] = atr(h, l, c, P["atr_len"])
    # Range grows with the square root of time, so a 2-minute ATR is smaller
    # than a 5-minute one. Convert to a 5-minute equivalent and every threshold
    # calibrated on 5m keeps its meaning on any timeframe.
    d["atr5"] = d["atr"] * np.sqrt(max(5.0 / max(cfg.tf_minutes, 0.1), 1.0))
    d["atr_pct"] = d["atr5"] / c * 100.0
    d["ef"] = ema(c, P["ema_fast"])
    d["em"] = ema(c, P["ema_mid"])
    d["es"] = ema(c, P["ema_slow"])

    dip, dim, adx = dmi(h, l, c, P["adx_len"], P["adx_smooth"])
    d["di_plus"], d["di_minus"], d["adx"] = dip, dim, adx

    basis = sma(c, P["bb_len"])
    dev = cfg.bb_mult * stdev(c, P["bb_len"])
    d["bb_basis"], d["bb_up"], d["bb_lo"] = basis, basis + dev, basis - dev
    d["bbw"] = (d["bb_up"] - d["bb_lo"]) / basis * 100.0
    d["bbw_rank"] = percentrank(d["bbw"], P["rank_len"])

    d["rsi"] = rsi(c, 14)
    d["rsi_f"] = rsi(c, P["rsi_fast_len"])
    d["don_hi"] = h.rolling(P["don_len"]).max()
    d["don_lo"] = l.rolling(P["don_len"]).min()
    d["swing_lo"] = l.rolling(P["swing_len"]).min()
    d["swing_hi"] = h.rolling(P["swing_len"]).max()

    # ── session gates ────────────────────────────────────────────────────────
    loc = d.index.tz_convert(cfg.tz) if d.index.tz is not None else d.index
    hr = pd.Series(loc.hour, index=d.index)
    dow = pd.Series(loc.dayofweek, index=d.index)          # Mon=0 .. Sun=6
    d["local_hour"] = hr
    d["in_sess"] = True if not cfg.use_session else ((hr >= cfg.sess_start) & (hr < cfg.sess_end))
    d["fri_late"] = (dow == 4) & (hr >= 18) if cfg.block_fri_pm else False
    d["vol_ok"] = (((d["atr_pct"] >= cfg.min_atr_pct) & (d["atr_pct"] <= cfg.max_atr_pct))
                   if cfg.use_volatility_filter else True)
    d["gate_ok"] = d["in_sess"] & (~d["fri_late"]) & d["vol_ok"]

    # ── regime with hysteresis (stateful) ───────────────────────────────────
    a = d["adx"].to_numpy(dtype=float)
    br = d["bbw_rank"].to_numpy(dtype=float)
    n = len(d)
    in_trend = np.zeros(n, dtype=bool)
    in_range = np.zeros(n, dtype=bool)
    t_state = r_state = False
    for i in range(n):
        if np.isnan(a[i]):
            in_trend[i] = in_range[i] = False
            continue
        t_state = (a[i] >= cfg.adx_trend_off) if t_state else (a[i] > cfg.adx_trend_on)
        rr_on = (a[i] < cfg.adx_range_on) and (not np.isnan(br[i])) and (br[i] < cfg.bbw_rank_max)
        r_state = (a[i] <= cfg.adx_range_off) if r_state else rr_on
        if t_state and r_state:
            r_state = False                                # trend wins ties
        in_trend[i], in_range[i] = t_state, r_state
    d["in_trend"], d["in_range"] = in_trend, in_range

    d["bull_bias"] = (d["em"] > d["es"]) & (d["ef"] > d["em"])
    d["bear_bias"] = (d["em"] < d["es"]) & (d["ef"] < d["em"])

    # ── H1 / H4 / Daily trend, from the same timestamps ─────────────────────
    if cfg.use_mtf_trend:
        agree_up = pd.Series(0, index=d.index)
        for mins in cfg.mtf_frames:
            c_htf = d["close"].resample(f"{mins}min").last().dropna()
            if len(c_htf) < 60:
                d[f"mtf_{mins}"] = 0
                continue
            fast, slow = ema(c_htf, cfg.mtf_fast), ema(c_htf, cfg.mtf_slow)
            # A NaN slow EMA means "not enough history", and `fast > NaN` is
            # False - which would silently report DOWNTREND for every bar before
            # the EMA exists. Unknown has to stay unknown, so it is masked to 0.
            known = slow.notna() & fast.notna()
            up = (fast > slow).where(known)
            # shift(1): judge against the candle that CLOSED, never the live one
            mapped = up.shift(1).reindex(d.index, method="ffill")
            col = mapped.map({True: 1, False: -1}).fillna(0).astype(int)
            d[f"mtf_{mins}"] = col
            agree_up += col
        d["mtf_score"] = agree_up          # +3 = all three up, -3 = all three down
    else:
        for mins in cfg.mtf_frames:
            d[f"mtf_{mins}"] = 0
        d["mtf_score"] = 0

    # ── higher-timeframe structure and order blocks ─────────────────────────
    if cfg.use_htf_structure or cfg.use_htf_ob:
        d = attach_htf_bias(d, cfg)
    else:
        d["htf_dir"] = 0
        d["htf_in_bull_ob"] = True
        d["htf_in_bear_ob"] = True

    # ── higher timeframe agreement (1H EMA50 vs EMA200, no lookahead) ────────
    #  The filter must ABSTAIN, not block, when the hourly EMAs don't exist yet.
    #  A 1H EMA200 needs 200 hourly bars; a short 5m sample has far fewer, so a
    #  naive `fillna(False)` silently vetoes every long trend trade and makes the
    #  backtest look bearish in a rising market. On a real TradingView/MT5 chart
    #  there is plenty of history, so blocking here would also make the backtest
    #  disagree with the live signals.
    h1 = d["close"].resample("1h").last().dropna()
    f_h, s_h = ema(h1, cfg.htf_ema_fast), ema(h1, cfg.htf_ema_slow)
    bull_1h = (f_h > s_h)
    valid_1h = f_h.notna() & s_h.notna()
    # shift(1): only use the LAST CLOSED hourly bar -> no lookahead bias
    d["htf_bull"] = bull_1h.shift(1).reindex(d.index, method="ffill").fillna(False)
    d["htf_valid"] = valid_1h.shift(1).reindex(d.index, method="ffill").fillna(False)

    # ── candlestick patterns ────────────────────────────────────────────────
    body = (c - o).abs()
    rng = (h - l).clip(lower=0.01)
    up_wick = h - pd.concat([o, c], axis=1).max(axis=1)
    dn_wick = pd.concat([o, c], axis=1).min(axis=1) - l
    d["bull_eng"] = (c > o) & (c.shift(1) < o.shift(1)) & (c >= o.shift(1)) & (o <= c.shift(1))
    d["bear_eng"] = (c < o) & (c.shift(1) > o.shift(1)) & (c <= o.shift(1)) & (o >= c.shift(1))
    d["hammer"] = (dn_wick > body * 1.5) & (up_wick < body) & (body / rng < 0.5)
    d["shooter"] = (up_wick > body * 1.5) & (dn_wick < body) & (body / rng < 0.5)
    d["bull_pin"] = (dn_wick / rng > 0.5) & (c > o)
    d["bear_pin"] = (up_wick / rng > 0.5) & (c < o)

    # ── classic three-bar and two-bar reversals ─────────────────────────────
    body1, body2 = body.shift(1), body.shift(2)
    mid2 = (o.shift(2) + c.shift(2)) / 2.0
    small = body1 <= body2 * 0.5
    # Morning star: heavy fall, a small indecisive candle, then a strong close
    # back above the midpoint of the fall. Evening star is the mirror.
    d["morning_star"] = ((c.shift(2) < o.shift(2)) & small & (c > o) & (c > mid2)
                         & (body > body1))
    d["evening_star"] = ((c.shift(2) > o.shift(2)) & small & (c < o) & (c < mid2)
                         & (body > body1))
    # Tweezers: two bars rejecting from the SAME price, the second closing away
    tw_tol = 0.10 * d["atr"]
    d["tweezer_bottom"] = ((l - l.shift(1)).abs() <= tw_tol) & (c > o) & (c.shift(1) < o.shift(1))
    d["tweezer_top"] = ((h - h.shift(1)).abs() <= tw_tol) & (c < o) & (c.shift(1) > o.shift(1))
    # Harami: a wide bar followed by a small one contained inside its body -
    # momentum stalling rather than reversing outright
    hi_body1 = pd.concat([o.shift(1), c.shift(1)], axis=1).max(axis=1)
    lo_body1 = pd.concat([o.shift(1), c.shift(1)], axis=1).min(axis=1)
    inside = (pd.concat([o, c], axis=1).max(axis=1) <= hi_body1) & \
             (pd.concat([o, c], axis=1).min(axis=1) >= lo_body1)
    d["bull_harami"] = inside & (c.shift(1) < o.shift(1)) & (c > o) & (body1 > body * 1.8)
    d["bear_harami"] = inside & (c.shift(1) > o.shift(1)) & (c < o) & (body1 > body * 1.8)

    # ── structure & divergence ──────────────────────────────────────────────
    ph = pivot_high(h, P["piv_len"], P["piv_len"])
    pl = pivot_low(l, P["piv_len"], P["piv_len"])
    rsi_at_piv = d["rsi"].shift(P["piv_len"])
    last_ph = prev_ph = last_pl = prev_pl = np.nan
    last_phr = prev_phr = last_plr = prev_plr = np.nan
    hh = np.zeros(n, bool); lh = np.zeros(n, bool)
    hl = np.zeros(n, bool); ll = np.zeros(n, bool)
    bdiv = np.zeros(n, bool); sdiv = np.zeros(n, bool)
    pv_h, pv_l = ph.to_numpy(), pl.to_numpy()
    rv = rsi_at_piv.to_numpy()
    for i in range(n):
        if not np.isnan(pv_h[i]):
            prev_ph, last_ph = last_ph, pv_h[i]
            prev_phr, last_phr = last_phr, rv[i]
        if not np.isnan(pv_l[i]):
            prev_pl, last_pl = last_pl, pv_l[i]
            prev_plr, last_plr = last_plr, rv[i]
        hh[i] = not np.isnan(prev_ph) and last_ph > prev_ph
        lh[i] = not np.isnan(prev_ph) and last_ph < prev_ph
        hl[i] = not np.isnan(prev_pl) and last_pl > prev_pl
        ll[i] = not np.isnan(prev_pl) and last_pl < prev_pl
        if cfg.use_div:
            bdiv[i] = (not np.isnan(prev_pl) and not np.isnan(last_plr) and not np.isnan(prev_plr)
                       and last_pl < prev_pl and last_plr > prev_plr)
            sdiv[i] = (not np.isnan(prev_ph) and not np.isnan(last_phr) and not np.isnan(prev_phr)
                       and last_ph > prev_ph and last_phr < prev_phr)
    d["hh"], d["lh"], d["hl"], d["ll"] = hh, lh, hl, ll
    d["bull_div"], d["bear_div"] = bdiv, sdiv

    # ── SMC: order blocks and structure shifts ──────────────────────────────
    d = build_smc(d, cfg, ph, pl, P)

    # ── liquidity pools: BSL above swing highs, SSL below swing lows ────────
    d = build_liquidity(d, cfg, pv_h, pv_l, P)

    # ── pullback proximity ──────────────────────────────────────────────────
    near_l = l <= d["ef"] + cfg.pb_tol_atr * d["atr"]
    near_s = h >= d["ef"] - cfg.pb_tol_atr * d["atr"]
    d["pulled_l"] = bars_since(near_l) <= P["pb_lookback"]
    d["pulled_s"] = bars_since(near_s) <= P["pb_lookback"]
    return d


# ═════════════════════════════════════════════════════════════════════════════
#  Signal scoring (mirrors the Pine reason lists exactly)
# ═════════════════════════════════════════════════════════════════════════════
def score_trend_long(r, rp, cfg):
    why = []
    if cfg.conf_ema_reclaim and r.close > r.ef and rp.close <= rp.ef:
        why.append(f"EMA{cfg.ema_fast} reclaim")
    if cfg.conf_engulfing and r.bull_eng:
        why.append("bullish engulfing")
    if cfg.conf_pin_bar and (r.hammer or r.bull_pin):
        why.append("bullish pin/hammer")
    if cfg.conf_rsi_50_cross and r.rsi > 50 and rp.rsi <= 50:
        why.append("RSI reclaims 50")
    if cfg.conf_structure and r.hl:
        why.append("higher low")
    if cfg.conf_di_expansion and r.di_plus > r.di_minus and r.di_plus > rp.di_plus:
        why.append("+DI expanding")
    return why


def score_trend_short(r, rp, cfg):
    why = []
    if cfg.conf_ema_reclaim and r.close < r.ef and rp.close >= rp.ef:
        why.append(f"EMA{cfg.ema_fast} rejection")
    if cfg.conf_engulfing and r.bear_eng:
        why.append("bearish engulfing")
    if cfg.conf_pin_bar and (r.shooter or r.bear_pin):
        why.append("bearish pin/shooting star")
    if cfg.conf_rsi_50_cross and r.rsi < 50 and rp.rsi >= 50:
        why.append("RSI loses 50")
    if cfg.conf_structure and r.lh:
        why.append("lower high")
    if cfg.conf_di_expansion and r.di_minus > r.di_plus and r.di_minus > rp.di_minus:
        why.append("-DI expanding")
    return why


def score_sweep_long(r, rp, cfg):
    """Sell-side liquidity was taken out and price closed back above it."""
    why = [f"SSL sweep ({int(r.recent_ssl_str)}x low @ {r.sweep_ssl_lvl:.2f})"]
    if cfg.conf_sweep_reclaim and r.close > r.sweep_ssl_lvl:
        why.append("reclaimed the swept level")
    if cfg.conf_pin_bar and (r.hammer or r.bull_pin or r.bull_eng):
        why.append("bullish rejection candle")
    if cfg.conf_rsi_extreme and (r.rsi_f < cfg.rsi_os or rp.rsi_f < cfg.rsi_os):
        why.append(f"fast RSI oversold {r.rsi_f:.0f}")
    if cfg.conf_divergence and r.bull_div:
        why.append("bullish RSI divergence")
    if cfg.conf_star and r.morning_star:
        why.append("morning star")
    if cfg.conf_tweezer and r.tweezer_bottom:
        why.append("tweezer bottom")
    if cfg.conf_ema_side and r.close > r.ef:
        why.append("back above EMA fast")
    if cfg.conf_order_block and r.in_bull_ob:
        why.append("inside a bullish order block")
    if cfg.conf_bos and (r.choch_up or r.struct_dir > 0):
        why.append("bullish CHoCH/BOS" if r.choch_up else "structure is bullish")
    return why


def score_sweep_short(r, rp, cfg):
    """Buy-side liquidity was taken out and price closed back below it."""
    why = [f"BSL sweep ({int(r.recent_bsl_str)}x high @ {r.sweep_bsl_lvl:.2f})"]
    if cfg.conf_sweep_reclaim and r.close < r.sweep_bsl_lvl:
        why.append("rejected back below the swept level")
    if cfg.conf_pin_bar and (r.shooter or r.bear_pin or r.bear_eng):
        why.append("bearish rejection candle")
    if cfg.conf_rsi_extreme and (r.rsi_f > cfg.rsi_ob or rp.rsi_f > cfg.rsi_ob):
        why.append(f"fast RSI overbought {r.rsi_f:.0f}")
    if cfg.conf_divergence and r.bear_div:
        why.append("bearish RSI divergence")
    if cfg.conf_star and r.evening_star:
        why.append("evening star")
    if cfg.conf_tweezer and r.tweezer_top:
        why.append("tweezer top")
    if cfg.conf_ema_side and r.close < r.ef:
        why.append("back below EMA fast")
    if cfg.conf_order_block and r.in_bear_ob:
        why.append("inside a bearish order block")
    if cfg.conf_bos and (r.choch_dn or r.struct_dir < 0):
        why.append("bearish CHoCH/BOS" if r.choch_dn else "structure is bearish")
    return why


def score_breakout_long(r, rp, cfg):
    """Buy-side liquidity was taken AND held — continuation, not reversal."""
    why = [f"BSL break ({int(r.bsl_break_tch)}x high @ {r.bsl_break_lvl:.2f})"]
    rng = max(r.high - r.low, 1e-9)
    if (r.close - r.low) / rng >= cfg.breakout_close_frac:
        why.append("closed strong into the break")
    if r.bbw_rank >= cfg.breakout_expansion_rank:
        why.append(f"volatility expanding ({r.bbw_rank:.0f}th pct)")
    if r.bos_up or r.choch_up:
        why.append("break of structure up")
    if r.di_plus > r.di_minus and r.adx > cfg.adx_trend_on:
        why.append("+DI leading, ADX trending")
    if r.close > r.ef and r.ef > r.em:
        why.append("stacked above the EMAs")
    return why


def score_breakout_short(r, rp, cfg):
    why = [f"SSL break ({int(r.ssl_break_tch)}x low @ {r.ssl_break_lvl:.2f})"]
    rng = max(r.high - r.low, 1e-9)
    if (r.high - r.close) / rng >= cfg.breakout_close_frac:
        why.append("closed weak into the break")
    if r.bbw_rank >= cfg.breakout_expansion_rank:
        why.append(f"volatility expanding ({r.bbw_rank:.0f}th pct)")
    if r.bos_dn or r.choch_dn:
        why.append("break of structure down")
    if r.di_minus > r.di_plus and r.adx > cfg.adx_trend_on:
        why.append("-DI leading, ADX trending")
    if r.close < r.ef and r.ef < r.em:
        why.append("stacked below the EMAs")
    return why


def has_bull_reversal(r) -> bool:
    """Did a candle actually turn up here, or do conditions merely look stretched?"""
    return bool(r.bull_eng or r.hammer or r.bull_pin or r.morning_star
                or r.tweezer_bottom or r.bull_harami or r.bull_div)


def has_bear_reversal(r) -> bool:
    return bool(r.bear_eng or r.shooter or r.bear_pin or r.evening_star
                or r.tweezer_top or r.bear_harami or r.bear_div)


def score_range_long(r, rp, cfg):
    why = []
    if cfg.conf_liq_in_range and r.recent_ssl_str > 0:
        why.append(f"SSL swept ({int(r.recent_ssl_str)}x)")
    if cfg.conf_bb_failure and rp.low < rp.bb_lo and r.close > r.bb_lo:
        why.append("failed BB-low breakdown")
    if cfg.conf_rsi_extreme and (r.rsi_f < cfg.rsi_os or rp.rsi_f < cfg.rsi_os):
        why.append(f"fast RSI oversold {r.rsi_f:.0f}")
    if cfg.conf_range_extreme and r.low <= rp.don_lo + cfg.don_tol_atr * r.atr:
        why.append("range floor tag")
    if cfg.conf_pin_bar and (r.hammer or r.bull_pin or r.bull_eng):
        why.append("bullish rejection candle")
    if cfg.conf_divergence and r.bull_div:
        why.append("bullish RSI divergence")
    if cfg.conf_star and r.morning_star:
        why.append("morning star")
    if cfg.conf_tweezer and r.tweezer_bottom:
        why.append("tweezer bottom")
    if cfg.conf_harami and r.bull_harami:
        why.append("bullish harami")
    if cfg.conf_order_block and r.in_bull_ob:
        why.append("inside a bullish order block")
    return why


def score_range_short(r, rp, cfg):
    why = []
    if cfg.conf_liq_in_range and r.recent_bsl_str > 0:
        why.append(f"BSL swept ({int(r.recent_bsl_str)}x)")
    if cfg.conf_bb_failure and rp.high > rp.bb_up and r.close < r.bb_up:
        why.append("failed BB-high breakout")
    if cfg.conf_rsi_extreme and (r.rsi_f > cfg.rsi_ob or rp.rsi_f > cfg.rsi_ob):
        why.append(f"fast RSI overbought {r.rsi_f:.0f}")
    if cfg.conf_range_extreme and r.high >= rp.don_hi - cfg.don_tol_atr * r.atr:
        why.append("range ceiling tag")
    if cfg.conf_pin_bar and (r.shooter or r.bear_pin or r.bear_eng):
        why.append("bearish rejection candle")
    if cfg.conf_divergence and r.bear_div:
        why.append("bearish RSI divergence")
    if cfg.conf_star and r.evening_star:
        why.append("evening star")
    if cfg.conf_tweezer and r.tweezer_top:
        why.append("tweezer top")
    if cfg.conf_harami and r.bear_harami:
        why.append("bearish harami")
    if cfg.conf_order_block and r.in_bear_ob:
        why.append("inside a bearish order block")
    return why


# ═════════════════════════════════════════════════════════════════════════════
#  Backtest loop
# ═════════════════════════════════════════════════════════════════════════════
def _m1_index(m1: pd.DataFrame | None):
    """Bucket 1-minute bars by the 5-minute bar that contains them."""
    if m1 is None or len(m1) == 0:
        return None
    g = m1.groupby(m1.index.floor("5min"))
    return {ts: (sub["high"].to_numpy(float), sub["low"].to_numpy(float))
            for ts, sub in g}


def _resolve_exit(m1b, side: str, sl: float, tp: float):
    """
    Walk the minute bars inside a 5-minute bar and return whichever level was
    actually reached first. Falls back to None if the minute data doesn't cover
    this bar, in which case the caller uses the pessimistic assumption.
    """
    if m1b is None:
        return None
    hi, lo = m1b
    for k in range(len(hi)):
        if side == "long":
            hit_sl = lo[k] <= sl
            hit_tp = hi[k] >= tp
        else:
            hit_sl = hi[k] >= sl
            hit_tp = lo[k] <= tp
        if hit_sl and hit_tp:
            return "SL"                      # same minute — still unknowable, stay pessimistic
        if hit_sl:
            return "SL"
        if hit_tp:
            return "TP"
    return None


def backtest(df: pd.DataFrame, cfg: Config, m1: pd.DataFrame | None = None):
    d = build_features(df, cfg)
    oz = cfg.lots * cfg.oz_per_lot
    usd_to_gbp = 1.0 / cfg.gbpusd
    m1map = _m1_index(m1)
    has_spread = "spread" in d.columns

    bal = cfg.start_balance_gbp
    equity_curve = []
    trades: list[Trade] = []

    pos = None            # dict describing the open position
    realised = []         # (price, qty) fills for the position being managed
    exit_reason = ""
    day = None
    trades_today = 0
    day_start_bal = bal
    ruin = False
    ruin_time = None
    pending = None        # resting limit order awaiting a fill
    unfilled = 0          # limit orders that expired without being touched
    skipped_margin = 0
    ambiguous_bars = 0
    used_grab_bsl = -1
    used_grab_ssl = -1

    rows = list(d.itertuples())
    P = _scaled(cfg)
    warmup = max(P["ema_slow"], P["rank_len"], P["don_len"]) + P["piv_len"] * 2 + 5

    for i in range(warmup, len(rows)):
        r = rows[i]
        rp = rows[i - 1]
        cur_day = r.Index.date()
        if cur_day != day:
            day = cur_day
            trades_today = 0
            day_start_bal = bal

        # ── 1. manage an open position on this bar ──────────────────────────
        #  The bar is walked as a sequence of sub-bars: the 1-minute bars where
        #  we have them, otherwise the 5-minute bar as one step. Inside a
        #  sub-bar the stop is always assumed to fill before any target.
        if pos is not None:
            sub = [(r.high, r.low)]
            if m1map is not None:
                mb = m1map.get(r.Index)
                if mb is not None:
                    mh, ml = mb
                    sub = list(zip(mh, ml))

            long = pos["side"] == "long"
            sgn = 1.0 if long else -1.0

            for sh, slo in sub:
                if pos["qty"] <= 1e-9:
                    break
                if (slo <= pos["sl"]) if long else (sh >= pos["sl"]):
                    px = pos["sl"] - cfg.slip_stop_usd if long else pos["sl"] + cfg.slip_stop_usd
                    realised.append((px, pos["qty"]))
                    pos["qty"] = 0.0
                    if pos["banked"]:
                        exit_reason = "StopAfterPartial"
                    elif pos["sl_moved"]:
                        exit_reason = "BreakEven" if abs(pos["sl"] - pos["entry"]) < 1e-6 else "TrailStop"
                    else:
                        exit_reason = "SL"
                    break

                for k, (lvl, frac) in enumerate(pos["targets"]):
                    if pos["done"][k] or frac <= 0:
                        continue
                    if not ((sh >= lvl) if long else (slo <= lvl)):
                        continue
                    pos["done"][k] = True
                    if k == len(pos["targets"]) - 1:
                        q = pos["qty"]
                    else:
                        # round DOWN to a whole 0.01 lot - a broker will not
                        # close 0.7 of the minimum lot, and rounding up would
                        # quietly close more than the plan says
                        step = max(cfg.lot_step_oz, 1e-9)
                        q = math.floor(min(pos["qty"], pos["qty0"] * frac) / step) * step
                        if pos["qty"] - q < step - 1e-9:
                            q = pos["qty"]          # would leave an untradable stub

                    if q > 1e-9:
                        realised.append((lvl, q))
                        pos["qty"] -= q
                        pos["banked"] += 1
                        exit_reason = "TP" if len(pos["targets"]) == 1 else f"TP{k+1}"
                if pos["qty"] <= 1e-9:
                    break

                if cfg.exit_mode in ("staged", "partial"):
                    reached = ((sh - pos["entry"]) if long else (pos["entry"] - slo)) / pos["risk"]
                    if cfg.lock_at_r > 0 and reached >= cfg.lock_at_r:
                        lock = pos["entry"] + sgn * cfg.lock_to_r * pos["risk"]
                        if (lock > pos["sl"]) if long else (lock < pos["sl"]):
                            pos["sl"] = lock; pos["sl_moved"] = True
                    elif cfg.be_at_r > 0 and reached >= cfg.be_at_r:
                        be = pos["entry"] + sgn * cfg.be_offset_r * pos["risk"]
                        if (be > pos["sl"]) if long else (be < pos["sl"]):
                            pos["sl"] = be; pos["sl_moved"] = True

            if pos is not None and pos["qty"] > 1e-9 and cfg.trail_mode != "none":
                reached = ((r.high - pos["entry"]) if long else (pos["entry"] - r.low)) / pos["risk"]
                if reached >= cfg.trail_start_r:
                    cand = ((r.close - cfg.trail_atr_mult * r.atr) if long else
                            (r.close + cfg.trail_atr_mult * r.atr)) if cfg.trail_mode == "atr" else \
                           (r.swing_lo if long else r.swing_hi)
                    if not np.isnan(cand) and ((cand > pos["sl"]) if long else (cand < pos["sl"])):
                        pos["sl"] = cand; pos["sl_moved"] = True

            if pos is not None and pos["qty"] > 1e-9 and cfg.use_time_stop \
                    and (i - pos["bar"]) >= P["time_stop_bars"]:
                px = r.close - cfg.spread_usd if long else r.close + cfg.spread_usd
                realised.append((px, pos["qty"]))
                pos["qty"] = 0.0
                exit_reason = "TimeStop"

            if pos is not None and pos["qty"] <= 1e-9:
                gross = sum((px - pos["entry"]) * sgn * q for px, q in realised)
                pnl_gbp = gross * usd_to_gbp - cfg.commission_gbp_per_trade
                bal += pnl_gbp
                t: Trade = pos["trade"]
                t.exit_time = r.Index
                t.exit = realised[-1][0]
                t.reason = exit_reason
                t.pnl_usd = gross
                t.pnl_gbp = pnl_gbp
                t.r_multiple = gross / (pos["risk"] * pos["qty0"]) if pos["risk"] > 0 else 0.0
                t.bars_held = i - pos["bar"]
                t.balance_after = bal
                t.partials = pos["banked"]
                trades.append(t)
                pos = None
                realised = []

        equity_curve.append((r.Index, bal))

        # ── 1b. account ruin — a real account cannot trade past zero ─────────
        if bal <= cfg.ruin_level_gbp and pos is None:
            ruin = True
            ruin_time = r.Index
            break

        # ── 1c. layer into an open position ─────────────────────────────────
        #  Each layer is another 0.01 lot on the SAME stop, so risk multiplies.
        #  This is why it ships off: two layers is double the loss when wrong.
        if pos is not None and cfg.use_layering and pos["layers"] <= cfg.max_layers \
                and not np.isnan(r.atr5):
            adverse = (pos["last_layer_px"] - r.low) if pos["side"] == "long" \
                      else (r.high - pos["last_layer_px"])
            if adverse >= cfg.layer_spacing_atr * r.atr5:
                add_px = pos["last_layer_px"] - cfg.layer_spacing_atr * r.atr5 \
                         if pos["side"] == "long" else \
                         pos["last_layer_px"] + cfg.layer_spacing_atr * r.atr5
                still_valid = (add_px > pos["sl"]) if pos["side"] == "long" else (add_px < pos["sl"])
                margin_ok = bal >= add_px * oz / cfg.leverage * usd_to_gbp
                if still_valid and margin_ok:
                    fill = add_px + cfg.spread_usd if pos["side"] == "long" else add_px - cfg.spread_usd
                    tot = pos["qty"] + oz
                    pos["entry"] = (pos["entry"] * pos["qty"] + fill * oz) / tot
                    pos["qty"] = tot
                    pos["qty0"] = pos["qty0"] + oz
                    pos["layers"] += 1
                    pos["last_layer_px"] = add_px
                    pos["trade"].layers = pos["layers"]

        # ── 2. resolve a resting limit order ────────────────────────────────
        if pending is not None:
            long_p = pending["side"] == "long"
            filled_px = None
            subs = [(r.high, r.low)]
            if m1map is not None:
                mb = m1map.get(r.Index)
                if mb is not None:
                    subs = list(zip(*mb))
            for sh, slo in subs:
                if (slo <= pending["limit"]) if long_p else (sh >= pending["limit"]):
                    filled_px = pending["limit"]
                    break
            if filled_px is not None:
                entry = filled_px + cfg.spread_usd if long_p else filled_px - cfg.spread_usd
                sgn0 = 1.0 if long_p else -1.0
                dist = abs(entry - pending["sl_abs"])
                dist = max(dist, cfg.min_stop_atr * pending["atr5"])
                if dist <= cfg.max_stop_atr * pending["atr5"] \
                        and bal >= entry * oz / cfg.leverage * usd_to_gbp:
                    sl = entry - sgn0 * dist
                    tp = entry + sgn0 * cfg.rr * dist
                    t = Trade(module=pending["module"], side=pending["side"],
                              why=pending["why"] + " | filled on a resting limit",
                              entry_time=r.Index, entry=entry, sl=sl, tp=tp,
                              risk_usd=dist * oz, adx=pending["adx"], atr=pending["atr"])
                    t.entry_kind = "limit"
                    targets = ([(tp, 1.0)] if cfg.exit_mode == "fixed"
                               else [(entry + sgn0 * cfg.tp3_r * dist, 1.0)] if cfg.exit_mode == "staged"
                               else [(entry + sgn0 * m * dist, f) for m, f in
                                     [(cfg.tp1_r, cfg.tp1_frac), (cfg.tp2_r, cfg.tp2_frac), (cfg.tp3_r, 1.0)]])
                    pos = {"side": pending["side"], "entry": entry, "sl": sl, "tp": tp,
                           "risk": dist, "bar": i, "trade": t, "qty": oz, "qty0": oz,
                           "banked": 0, "sl_moved": False, "targets": targets,
                           "done": [False] * len(targets), "layers": 1, "last_layer_px": entry}
                    realised = []
                    trades_today += 1
                pending = None
            elif i >= pending["expires"]:
                unfilled += 1
                pending = None

        # ── 3. look for a new entry (only when flat and nothing resting) ────
        if pos is not None or pending is not None or not r.gate_ok:
            continue
        if cfg.use_daily_limits:
            if cfg.max_trades_day and trades_today >= cfg.max_trades_day:
                continue
            if cfg.max_loss_day_gbp and (bal - day_start_bal) <= -cfg.max_loss_day_gbp:
                continue
        if np.isnan(r.atr) or np.isnan(r.es) or r.atr <= 0:
            continue

        # abstain when the hourly trend is not yet computable
        htf_known = bool(r.htf_valid)
        htf_l = (not cfg.use_htf) or (not htf_known) or bool(r.htf_bull)
        # H1 / H4 / Daily agreement. Frames without enough history report 0 and
        # simply do not vote, so a missing Daily never blocks a trade.
        mtf_up = sum(1 for m in cfg.mtf_frames if getattr(r, f"mtf_{m}", 0) == 1)
        mtf_dn = sum(1 for m in cfg.mtf_frames if getattr(r, f"mtf_{m}", 0) == -1)
        mtf_l = cfg.mtf_min_agree <= 0 or mtf_up >= cfg.mtf_min_agree
        mtf_s = cfg.mtf_min_agree <= 0 or mtf_dn >= cfg.mtf_min_agree
        bias_l = mtf_l and ((not cfg.use_htf_structure) or r.htf_dir >= 0) and \
                 ((not cfg.use_htf_ob) or bool(r.htf_in_bull_ob))
        bias_s = mtf_s and ((not cfg.use_htf_structure) or r.htf_dir <= 0) and \
                 ((not cfg.use_htf_ob) or bool(r.htf_in_bear_ob))
        htf_s = (not cfg.use_htf) or (not htf_known) or (not bool(r.htf_bull))

        why, side, module = [], None, None

        # ── liquidity sweep has priority: it is the most specific setup ──────
        if cfg.use_sweep_module:
            fresh_ssl = int(r.grab_ssl_bar) >= 0 and int(r.grab_ssl_bar) != used_grab_ssl
            fresh_bsl = int(r.grab_bsl_bar) >= 0 and int(r.grab_bsl_bar) != used_grab_bsl
            if (bias_l and fresh_ssl and r.recent_ssl_str >= cfg.sweep_min_touches
                    and not np.isnan(r.sweep_ssl_lvl) and r.recent_ssl_str > r.recent_bsl_str):
                w = score_sweep_long(r, rp, cfg)
                if len(w) >= cfg.sweep_min_score:
                    why, side, module = w, "long", "sweep"
            if (bias_s and side is None and fresh_bsl and r.recent_bsl_str >= cfg.sweep_min_touches
                    and not np.isnan(r.sweep_bsl_lvl) and r.recent_bsl_str > r.recent_ssl_str):
                w = score_sweep_short(r, rp, cfg)
                if len(w) >= cfg.sweep_min_score:
                    why, side, module = w, "short", "sweep"

        # ── breakout: the only module that trades WITH the move ─────────────
        if cfg.use_breakout_module and side is None and not r.in_range:
            if (bias_l and r.bsl_broken and r.bsl_break_tch >= cfg.breakout_min_touches
                    and not np.isnan(r.bsl_break_lvl)):
                w = score_breakout_long(r, rp, cfg)
                if len(w) >= cfg.breakout_min_score:
                    why, side, module = w, "long", "breakout"
            if (side is None and bias_s and r.ssl_broken
                    and r.ssl_break_tch >= cfg.breakout_min_touches
                    and not np.isnan(r.ssl_break_lvl)):
                w = score_breakout_short(r, rp, cfg)
                if len(w) >= cfg.breakout_min_score:
                    why, side, module = w, "short", "breakout"

        if (cfg.use_trend_module and bias_l and side is None and r.in_trend
                and r.bull_bias and htf_l and r.pulled_l):
            w = score_trend_long(r, rp, cfg)
            if len(w) >= cfg.trend_min_score:
                why, side, module = w, "long", "trend"
        if (cfg.use_trend_module and bias_s and side is None and r.in_trend
                and r.bear_bias and htf_s and r.pulled_s):
            w = score_trend_short(r, rp, cfg)
            if len(w) >= cfg.trend_min_score:
                why, side, module = w, "short", "trend"
        if cfg.use_range_module and side is None and r.in_range:
            wl = score_range_long(r, rp, cfg)
            ws = score_range_short(r, rp, cfg)
            if bias_l and len(wl) >= cfg.range_min_score and len(wl) > len(ws):
                why, side, module = wl, "long", "range"
            elif bias_s and len(ws) >= cfg.range_min_score and len(ws) > len(wl):
                why, side, module = ws, "short", "range"
        # A reversal must be PRESENT, not merely counted. This is a gate: it can
        # only remove signals, never let a weak one through.
        if side is not None and cfg.require_reversal:
            if side == "long" and not has_bull_reversal(r):
                side = None
            elif side == "short" and not has_bear_reversal(r):
                side = None

        if side is None:
            continue

        # ── 3. size the stop and target ─────────────────────────────────────
        spread = float(r.spread) if has_spread else cfg.spread_usd
        if side == "long":
            entry = r.close + spread                             # pay the ask
            if module == "breakout":
                # behind the level that broke: if price falls back through it,
                # the breakout has failed and the reason for the trade is gone
                raw_sl = min(r.bsl_break_lvl, r.low) - cfg.sl_pad_atr * r.atr
            elif module == "trend":
                raw_sl = min(r.swing_lo, r.low) - cfg.sl_pad_atr * r.atr
            elif module == "sweep":
                # below the wick that actually took the liquidity out
                lo_w = np.nanmin([r.low, rp.low, r.grab_ssl_wick, r.sweep_ssl_lvl])
                raw_sl = lo_w - cfg.sl_pad_atr * r.atr
            else:
                raw_sl = min(r.low, rp.low) - cfg.sl_pad_atr * r.atr
            dist = max(entry - raw_sl, cfg.min_stop_atr * r.atr)
            if dist > cfg.max_stop_atr * r.atr:
                continue
            sl, tp = entry - dist, entry + cfg.rr * dist
        else:
            entry = r.close - spread                            # sell at the bid
            if module == "breakout":
                raw_sl = max(r.ssl_break_lvl, r.high) + cfg.sl_pad_atr * r.atr
            elif module == "trend":
                raw_sl = max(r.swing_hi, r.high) + cfg.sl_pad_atr * r.atr
            elif module == "sweep":
                hi_w = np.nanmax([r.high, rp.high, r.grab_bsl_wick, r.sweep_bsl_lvl])
                raw_sl = hi_w + cfg.sl_pad_atr * r.atr
            else:
                raw_sl = max(r.high, rp.high) + cfg.sl_pad_atr * r.atr
            dist = max(raw_sl - entry, cfg.min_stop_atr * r.atr)
            if dist > cfg.max_stop_atr * r.atr:
                continue
            sl, tp = entry + dist, entry - cfg.rr * dist

        # margin must be available to open the position at all
        # Below this the account cannot fund even the minimum 0.01 lot — it is
        # dead in practice, not merely down, so the run stops here.
        # ── resting limit instead of chasing at market ──────────────────────
        if cfg.entry_mode == "limit":
            back = cfg.limit_offset_atr * r.atr5
            lim = (r.close - back) if side == "long" else (r.close + back)
            if cfg.limit_to_ob:
                edge = r.ob_bull_top if side == "long" else r.ob_bear_bot
                if not np.isnan(edge):
                    # only pull to the block if it sits between price and the stop
                    if (raw_sl < edge < r.close) if side == "long" else (r.close < edge < raw_sl):
                        lim = edge
            pending = {"side": side, "limit": lim, "sl_abs": raw_sl, "why": " + ".join(why),
                       "module": module, "expires": i + P["limit_expiry_bars"],
                       "atr5": r.atr5, "atr": float(r.atr), "adx": float(r.adx)}
            continue

        margin_gbp = entry * oz / cfg.leverage * usd_to_gbp
        if bal < margin_gbp:
            skipped_margin += 1
            ruin = True
            ruin_time = r.Index
            break

        t = Trade(module=module, side=side, why=" + ".join(why), entry_time=r.Index,
                  entry=entry, sl=sl, tp=tp, risk_usd=dist * oz,
                  adx=float(r.adx), atr=float(r.atr))
        sgn0 = 1.0 if side == "long" else -1.0
        if cfg.exit_mode == "fixed":
            targets = [(tp, 1.0)]
        elif cfg.exit_mode == "staged":
            # a single 0.01 lot is indivisible, so only the final target closes it
            targets = [(entry + sgn0 * cfg.tp3_r * dist, 1.0)]
        else:
            targets = [(entry + sgn0 * m * dist, f) for m, f in
                       [(cfg.tp1_r, cfg.tp1_frac), (cfg.tp2_r, cfg.tp2_frac), (cfg.tp3_r, 1.0)]]
        pos = {"side": side, "entry": entry, "sl": sl, "tp": tp, "risk": dist,
               "bar": i, "trade": t, "qty": oz, "qty0": oz, "banked": 0,
               "sl_moved": False, "targets": targets, "done": [False] * len(targets),
               "layers": 1, "last_layer_px": entry}
        realised = []
        trades_today += 1
        if module == "sweep":
            if side == "long":
                used_grab_ssl = int(r.grab_ssl_bar)
            else:
                used_grab_bsl = int(r.grab_bsl_bar)

    eq = pd.DataFrame(equity_curve, columns=["time", "equity"]).set_index("time")
    tr = pd.DataFrame([t.__dict__ for t in trades])
    tr.attrs["ruin"] = ruin
    tr.attrs["ruin_time"] = ruin_time
    tr.attrs["skipped_no_margin"] = skipped_margin
    tr.attrs["unfilled_limits"] = unfilled
    tr.attrs["bars_tested"] = len(rows) - warmup
    tr.attrs["m1_resolved"] = m1map is not None
    tr.attrs["ambiguous_exits"] = ambiguous_bars
    return tr, eq, d


# ═════════════════════════════════════════════════════════════════════════════
#  Statistics
# ═════════════════════════════════════════════════════════════════════════════
def stats(tr: pd.DataFrame, eq: pd.DataFrame, cfg: Config) -> dict:
    if tr is None or len(tr) == 0:
        return {"trades": 0}
    wins = tr[tr.pnl_gbp > 0]
    loss = tr[tr.pnl_gbp <= 0]
    gp = wins.pnl_gbp.sum()
    gl = -loss.pnl_gbp.sum()
    peak = eq.equity.cummax()
    dd = (eq.equity - peak)
    ddp = (dd / peak * 100.0)

    streak = cur = 0
    for p in tr.pnl_gbp:
        cur = cur + 1 if p <= 0 else 0
        streak = max(streak, cur)
    win_streak = cur = 0
    for p in tr.pnl_gbp:
        cur = cur + 1 if p > 0 else 0
        win_streak = max(win_streak, cur)

    final = float(eq.equity.iloc[-1])
    return {
        "trades": int(len(tr)),
        "wins": int(len(wins)),
        "losses": int(len(loss)),
        "win_rate": float(len(wins) / len(tr) * 100.0),
        "profit_factor": float(gp / gl) if gl > 0 else float("inf"),
        "net_gbp": float(tr.pnl_gbp.sum()),
        "return_pct": float((final - cfg.start_balance_gbp) / cfg.start_balance_gbp * 100.0),
        "final_balance": final,
        "avg_win_gbp": float(wins.pnl_gbp.mean()) if len(wins) else 0.0,
        "avg_loss_gbp": float(loss.pnl_gbp.mean()) if len(loss) else 0.0,
        "expectancy_gbp": float(tr.pnl_gbp.mean()),
        "expectancy_r": float(tr.r_multiple.mean()),
        "max_dd_gbp": float(-dd.min()),
        "max_dd_pct": float(-ddp.min()),
        "max_loss_streak": int(streak),
        "max_win_streak": int(win_streak),
        "avg_bars_held": float(tr.bars_held.mean()),
        "sl_exits": int((tr.reason == "SL").sum()),
        "tp_exits": int((tr.reason == "TP").sum()),
        "time_exits": int((tr.reason == "TimeStop").sum()),
        "trend_trades": int((tr.module == "trend").sum()),
        "range_trades": int((tr.module == "range").sum()),
        "sweep_trades": int((tr.module == "sweep").sum()),
        "sweep_wr": float((tr[tr.module == "sweep"].pnl_gbp > 0).mean() * 100) if (tr.module == "sweep").any() else 0.0,
        "trend_wr": float((tr[tr.module == "trend"].pnl_gbp > 0).mean() * 100) if (tr.module == "trend").any() else 0.0,
        "range_wr": float((tr[tr.module == "range"].pnl_gbp > 0).mean() * 100) if (tr.module == "range").any() else 0.0,
        "long_trades": int((tr.side == "long").sum()),
        "short_trades": int((tr.side == "short").sum()),
        "long_wr": float((tr[tr.side == "long"].pnl_gbp > 0).mean() * 100) if (tr.side == "long").any() else 0.0,
        "short_wr": float((tr[tr.side == "short"].pnl_gbp > 0).mean() * 100) if (tr.side == "short").any() else 0.0,
    }
