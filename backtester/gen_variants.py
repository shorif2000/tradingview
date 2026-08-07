"""
Generate the focused single-purpose scripts from the master indicator.

Each variant is the SAME verified codebase with different defaults, rather than a
hand-cut copy. That matters: three separately-edited scripts drift apart, and a
bug fixed in one silently survives in the others. Re-run this after any change to
XAU_Regime_Scalper_INDICATOR.pine and every variant inherits the fix.

Measured on 2M Jan + 5M Jan + 5M Jun-Aug, 0.02 lots, half at 1R, swing trail:

  Range + Sweep together   151 tr   57.0% green   +0.368R   +£384   36% DD
  Range fade alone         141 tr   56.0% green   +0.321R   +£353   48% DD
  Liquidity sweep alone     63 tr   54.0% green   +0.314R    +£92   24% DD
  Trend pullback alone      63 tr   44.4% green   -0.093R    -£68   75% DD
  Breakout alone            49 tr   40.8% green   -0.076R    -£21   67% DD

Range and sweep are kept TOGETHER because together they beat either alone on
both expectancy and drawdown - they are complementary, not redundant. Trend and
breakout are split OUT because they lose money and drag the pair down from
+0.368R to +0.198R when bolted on.
"""
from __future__ import annotations
import re

from paths import PINE, VARIANTS as VARIANT_DIR

SRC = PINE / "XAU_Regime_Scalper_INDICATOR.pine"
master = open(SRC).read()


def set_default(text: str, var: str, new: str) -> str:
    """Rewrite the default of an input.* declaration, leaving everything else."""
    pat = re.compile(rf"^({re.escape(var)}\s*=\s*input\.\w+\()([^,]+)(,)", re.M)
    out, n = pat.subn(lambda m: m.group(1) + new + m.group(3), text, count=1)
    if n == 0:
        raise SystemExit(f"could not find input default for {var}")
    return out


def retitle(text: str, title: str, short: str, header: str) -> str:
    text = re.sub(r'indicator\("[^"]+", "[^"]+"', f'indicator("{title}", "{short}"', text, count=1)
    # replace the top-of-file banner with one describing this specific script
    end = text.index("indicator(")
    return header + "\n" + text[end:]


VARIANTS = {
    # ── 4. the roadmap: destinations and spread, never a direction call ──────
    "XAU_4_Roadmap.pine": dict(
        title="XAU Roadmap", short="XAU-RM",
        header='''//@version=6
// ═══════════════════════════════════════════════════════════════════════════════
//  XAU ROADMAP  —  where price can go, and which side it reaches first
// ═══════════════════════════════════════════════════════════════════════════════
//  Read this first, because the honest version of "map the future direction" is
//  narrower than the phrase suggests.
//
//  I tested whether ANYTHING in the current state predicts which way price goes
//  next, asking at every bar: does the nearest liquidity above get taken before
//  the nearest below? Across both samples:
//
//    PROXIMITY        replicated almost exactly    86.9% / 86.4%   <- the edge
//    H1 trend up      FLIPPED SIGN                 54.8% / 43.1%
//    fresh SSL sweep  FLIPPED SIGN                 61.6% / 38.4%
//    regime = RANGE   FLIPPED SIGN                 58.9% / 46.2%
//
//  So the only thing that forecasts direction on this data is which level is
//  CLOSER. Trend, regime and sweep state are worthless for it - they looked
//  predictive in one sample and inverted in the other, which is what a spurious
//  pattern does. None of them feed this script.
//
//  WHAT IT DRAWS
//    - the nearest liquidity each side, each with a calibrated probability of
//      being reached first (logistic fit, 9,994 observations, Brier 0.197 vs
//      0.25 for guessing). Median time to resolve: 9 bars, ~45 min on 5m.
//    - a volatility cone: 68% and 95% bands, calibrated at 0.96 and 2.19 x ATR
//      x sqrt(bars), constants that held across both samples and every horizon
//      from 6 to 48 bars.
//
//  WHAT IT WILL NEVER DO
//    Tell you the market is going up. It maps DESTINATIONS and SPREAD. If you
//    want an entry, that is script 1.
// ═══════════════════════════════════════════════════════════════════════════════
''',
        defaults={
            "scriptMode": '"Roadmap"', "uiPreset": '"Full"',
        }),

    # ── 1. the earner: signals only, chart kept quiet ────────────────────────
    "XAU_1_MeanReversion_Scalper.pine": dict(
        title="XAU Mean-Reversion Scalper", short="XAU-MR",
        header='''//@version=6
// ═══════════════════════════════════════════════════════════════════════════════
//  XAU MEAN-REVERSION SCALPER  —  the earner
// ═══════════════════════════════════════════════════════════════════════════════
//  ONE job: fade stretched moves back toward the mean. Two complementary ways:
//
//    RANGE FADE      price pokes outside a Bollinger band at a range extreme and
//                    closes back inside - a failed breakout.
//    LIQUIDITY SWEEP price runs the stops beyond a swing level and closes
//                    straight back - a stop raid that failed.
//
//  They are kept together because measured on your data they beat either alone:
//
//    Range + Sweep    151 trades   57.0% green   +0.368R   +£384   36% DD
//    Range alone      141 trades   56.0% green   +0.321R   +£353   48% DD
//    Sweep alone       63 trades   54.0% green   +0.314R    +£92   24% DD
//
//  Trend and breakout entries are NOT here on purpose - both lost money in
//  testing and dragged this pair down from +0.368R to +0.198R. They live in
//  script 3 so they cannot contaminate this one.
//
//  This is a COUNTER-TREND system. A SELL while price is rising is the system
//  working, not a fault - those were the single best trades in the sample
//  (66% win rate). Chart drawings are off by default; run script 2 alongside
//  if you want the map.
// ═══════════════════════════════════════════════════════════════════════════════
''',
        defaults={
            "scriptMode": '"Scalper"', "uiPreset": '"Beginner"',
        }),

    # ── 2. the map: draws context, never fires a signal ─────────────────────
    "XAU_2_Liquidity_Map.pine": dict(
        title="XAU Liquidity Map", short="XAU-MAP",
        header='''//@version=6
// ═══════════════════════════════════════════════════════════════════════════════
//  XAU LIQUIDITY MAP  —  context only, zero signals
// ═══════════════════════════════════════════════════════════════════════════════
//  Draws WHERE the market is likely to react, and never tells you to trade.
//  Every entry module is switched off, so this cannot dilute or contradict the
//  scalper - run the two side by side and each does one job.
//
//    BSL / SSL       resting liquidity above swing highs and below swing lows,
//                    labelled with how many times the level was defended
//    ORDER BLOCKS    the last opposing candle before an impulsive move, scored
//                    by how many other things agree at that price
//    BREAKERS        a zone price closed THROUGH, which then flips polarity:
//                    a broken sell zone becomes support
//    IMBALANCE       the close-to-open body gap where almost no business was
//                    done (not an FVG - that is a wick-to-wick gap)
//    TARGETS         nearest untapped liquidity each side, with distance
//    STRUCTURE       HH / HL / LH / LL, BOS and CHoCH
//
//  Untouched zones project across the chart; once price visits one it freezes,
//  unless it is strong enough to keep mattering. Hover any zone for its exact
//  high, low and confluence list.
//
//  TIMING, so the chart cannot mislead you: zones are drawn AFTER price moves
//  away - an order block cannot be known until the impulse that defines it has
//  happened (~15 min on 5m), and a liquidity level needs its pivot to confirm
//  (~25 min). Scrolling back they look perfectly placed; live they arrive late.
//  Use them as destinations, not entry triggers.
// ═══════════════════════════════════════════════════════════════════════════════
''',
        defaults={
            "scriptMode": '"Liquidity map"', "uiPreset": '"Full"',
        }),

    # ── 3. the ideas that did not work, quarantined ─────────────────────────
    "XAU_3_Trend_Pullback.pine": dict(
        title="XAU Trend Pullback [UNPROFITABLE IN TESTING]", short="XAU-TP",
        header='''//@version=6
// ═══════════════════════════════════════════════════════════════════════════════
//  XAU TREND PULLBACK  —  kept separate because it LOST money
// ═══════════════════════════════════════════════════════════════════════════════
//  Read this before trading it. Measured across 2M Jan, 5M Jan and 5M Jun-Aug
//  at 0.02 lots with half off at 1R and a swing trail:
//
//    Trend pullback alone   63 trades   44.4% green   -0.093R   -£68   75% DD
//    Breakout alone         49 trades   40.8% green   -0.076R   -£21   67% DD
//
//  Both are negative, in two market regimes, on three timeframes. Bolting them
//  onto the mean-reversion pair took it from +0.368R down to +0.198R.
//
//  Only the TREND PULLBACK module is wired into Pine. The breakout module lives
//  in the Python backtester (use_breakout_module) - it was never added here
//  because it measured at -0.08R and wiring it would have meant restructuring a
//  working script for a feature the data says to leave alone.
//
//  Three separate attempts at trading WITH the trend all landed at zero or
//  worse: trend pullback (-0.09R), higher-timeframe trend gating (+0.485R fell
//  to +0.117R), and breakout continuation (-0.08R). That consistency is the
//  point - short-horizon gold mean-reverts, and at a 20-cent spread there is
//  not enough left in a continuation move to pay for the entry.
//
//  This script exists so you can test that claim yourself on new data, and so
//  these modules can never quietly dilute the scalper. If you find a period
//  where it works, that is a real finding - but it did not work here.
// ═══════════════════════════════════════════════════════════════════════════════
''',
        defaults={
            "scriptMode": '"Custom"', "uiPreset": '"Standard"',
            "useRangeModule": "false", "useSweepModule": "false",
            "useTrendModule": "true",
        }),
}

for fname, spec in VARIANTS.items():
    text = retitle(master, spec["title"], spec["short"], spec["header"])
    for var, val in spec["defaults"].items():
        text = set_default(text, var, val)
    VARIANT_DIR.mkdir(parents=True, exist_ok=True)
    open(VARIANT_DIR / fname, "w").write(text)
    print(f"{fname:<36} {len(text.splitlines()):>5} lines   "
          f"{len(spec['defaults'])} defaults changed")
print("\nAll three share one verified codebase — a fix in the master reaches all of them.")
