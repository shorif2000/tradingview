"""
Generate the Pine STRATEGY file from the INDICATOR file.

The two scripts must never disagree, so only one of them is hand-maintained.
Edit XAU_Regime_Scalper_INDICATOR.pine, then re-run this.
"""
src = open("XAU_Regime_Scalper_INDICATOR.pine").read()
s = src
n = 0


def rep(a, b):
    global s, n
    assert a in s, "NOT FOUND >>> " + a[:100]
    s = s.replace(a, b, 1)
    n += 1


rep("//  XAU REGIME SCALPER — 5M  |  INDICATOR (live signals + alerts)  v2",
    "//  XAU REGIME SCALPER — 5M  |  STRATEGY (backtest)  v2")

rep("""//  ALERTS: right-click → Add alert → Condition = this indicator →
//          "Any alert() function call" → Once per bar close.""",
    """//  BACKTESTING: set Commission and Slippage in the Properties tab to YOUR
//  broker's real numbers. The Vantage MT5 export used in development showed a
//  spread of 19-20 points ($0.19-0.20) on XAUUSD, i.e. about 20 ticks.
//
//  BAR LIMIT: TradingView loads roughly 5k bars of 5m history on free plans,
//  10k on Essential/Plus and 20k on Premium. Six months of 5m gold is ~37k bars,
//  so the Strategy Tester alone cannot cover it — use the Python backtester for
//  the long sample and this for chart-level verification.""")

rep("""indicator("XAU Regime Scalper 5M [Signals]", "XAU-RS Sig", overlay = true,
     max_labels_count = 500, max_lines_count = 500, max_boxes_count = 500)""",
    """strategy(
     title                   = "XAU Regime Scalper 5M [Strategy]",
     shorttitle              = "XAU-RS 5M",
     overlay                 = true,
     initial_capital         = 100,
     currency                = currency.GBP,
     default_qty_type        = strategy.fixed,
     default_qty_value       = 1,                 // 1 oz = 0.01 lot
     pyramiding              = 0,
     commission_type         = strategy.commission.cash_per_order,
     commission_value        = 0.0,
     slippage                = 20,                // ticks — models the ~$0.20 spread
     process_orders_on_close = true,
     calc_on_every_tick      = false,
     max_labels_count        = 500,
     max_lines_count         = 500,
     max_boxes_count         = 500)""")

rep("""gbpusd     = input.float(1.27, "GBPUSD rate",             group = gK, step = 0.01, minval = 0.01)""",
    """gbpusd     = input.float(1.27, "GBPUSD rate",             group = gK, step = 0.01, minval = 0.01)
useBE        = input.bool(false, "Move stop to break-even at +1R", group = gK)
useTimeStop  = input.bool(true,  "Time stop: close after N bars",  group = gK)
timeStopBars = input.int(60,     "N bars",                         group = gK, minval = 5)
maxTradesDay = input.int(6,      "Max trades per day (0 = off)",   group = gK, minval = 0)
maxLossDay   = input.float(6.0,  "Daily loss cap in £ (0 = off)",  group = gK, step = 0.5)""")

rep('showPanel    = input.bool(true, "Status panel",              group = gV)',
    'showPanel    = input.bool(true, "Status panel",              group = gV)\nshowTable    = input.bool(true, "Performance table",         group = gV)')

ORDERS = '''
// ═════════════════════════════════════════════════════════════════════════════
//  DAILY GUARDRAILS AND ORDERS
// ═════════════════════════════════════════════════════════════════════════════
newDay = ta.change(time("1D")) != 0
var int   tradesToday = 0
var float dayStartEq  = na
if newDay
    tradesToday := 0
    dayStartEq  := strategy.equity
if na(dayStartEq)
    dayStartEq := strategy.equity
dayPnL   = strategy.equity - dayStartEq
tradesOK = maxTradesDay == 0 or tradesToday < maxTradesDay
lossOK   = maxLossDay  == 0 or dayPnL > -maxLossDay
canGo    = strategy.position_size == 0 and tradesOK and lossOK

entLong  = newLong  and canGo
entShort = newShort and canGo

var float actSL = na
var float actTP = na
var int   barIn = na

if entLong
    strategy.entry("Long", strategy.long, comment = "BUY")
    strategy.exit("X-L", from_entry = "Long", stop = slPrice, limit = tpPrice, comment_loss = "SL", comment_profit = "TP")
    actSL := slPrice
    actTP := tpPrice
    barIn := bar_index
    tradesToday += 1

if entShort
    strategy.entry("Short", strategy.short, comment = "SELL")
    strategy.exit("X-S", from_entry = "Short", stop = slPrice, limit = tpPrice, comment_loss = "SL", comment_profit = "TP")
    actSL := slPrice
    actTP := tpPrice
    barIn := bar_index
    tradesToday += 1

// break-even management
if useBE and strategy.position_size > 0 and not na(actSL)
    r0 = strategy.position_avg_price - actSL
    if r0 > 0 and high >= strategy.position_avg_price + r0
        actSL := math.max(actSL, strategy.position_avg_price)
if useBE and strategy.position_size < 0 and not na(actSL)
    r0 = actSL - strategy.position_avg_price
    if r0 > 0 and low <= strategy.position_avg_price - r0
        actSL := math.min(actSL, strategy.position_avg_price)

// keep the live orders in sync every bar
if strategy.position_size > 0
    strategy.exit("X-L", from_entry = "Long", stop = actSL, limit = actTP, comment_loss = "SL", comment_profit = "TP")
if strategy.position_size < 0
    strategy.exit("X-S", from_entry = "Short", stop = actSL, limit = actTP, comment_loss = "SL", comment_profit = "TP")

// time stop
if useTimeStop and strategy.position_size != 0 and not na(barIn) and bar_index - barIn >= timeStopBars
    strategy.close_all(comment = "TimeStop")

// NOTE: position_size is still 0 on the bar the entry fires, so the reset must
// also confirm no entry happened this bar — otherwise it wipes the levels it
// just set and no stop or target is ever placed.
if strategy.position_size == 0 and not entLong and not entShort
    actSL := na
    actTP := na
    barIn := na

plot(not na(actSL) ? actSL : na, "Active SL", color.new(color.red, 0),   2, plot.style_linebr)
plot(not na(actTP) ? actTP : na, "Active TP", color.new(color.green, 0), 2, plot.style_linebr)

'''
rep("""// ═════════════════════════════════════════════════════════════════════════════
//  VISUALS
// ═════════════════════════════════════════════════════════════════════════════""",
    ORDERS + """// ═════════════════════════════════════════════════════════════════════════════
//  VISUALS
// ═════════════════════════════════════════════════════════════════════════════""")

# markers reflect real orders, not raw signals
rep('plotshape(newLong,  "BUY signal",  shape.labelup,   location.belowbar, color.new(color.teal, 0),   text = "BUY",  textcolor = color.white, size = size.normal)\nplotshape(newShort, "SELL signal", shape.labeldown, location.abovebar, color.new(color.maroon, 0), text = "SELL", textcolor = color.white, size = size.normal)',
    'plotshape(entLong,  "BUY entry",  shape.labelup,   location.belowbar, color.new(color.teal, 0),   text = "BUY",  textcolor = color.white, size = size.normal)\nplotshape(entShort, "SELL entry", shape.labeldown, location.abovebar, color.new(color.maroon, 0), text = "SELL", textcolor = color.white, size = size.normal)')
rep('if eShowReasons and (newLong or newShort)', 'if eShowReasons and (entLong or entShort)')
rep('    txt = (newLong ? "▲ BUY" : "▼ SELL")', '    txt = (entLong ? "▲ BUY" : "▼ SELL")')
rep('    rl = label.new(bar_index, newLong ? low - atr * 1.2 : high + atr * 1.2, txt,\n              style = newLong ? label.style_label_up : label.style_label_down,\n              color = thin ? color.new(color.orange, 20) :\n                      (newLong ? color.new(color.teal, 20) : color.new(color.maroon, 20)),',
    '    rl = label.new(bar_index, entLong ? low - atr * 1.2 : high + atr * 1.2, txt,\n              style = entLong ? label.style_label_up : label.style_label_down,\n              color = thin ? color.new(color.orange, 20) :\n                      (entLong ? color.new(color.teal, 20) : color.new(color.maroon, 20)),')
rep('if eShowLevels and (newLong or newShort)', 'if eShowLevels and (entLong or entShort)')

rep('''// ═════════════════════════════════════════════════════════════════════════════
//  ALERTS
// ═════════════════════════════════════════════════════════════════════════════
alertcondition(newLong  and barstate.isconfirmed, "XAU-RS BUY",  "XAUUSD BUY signal")
alertcondition(newShort and barstate.isconfirmed, "XAU-RS SELL", "XAUUSD SELL signal")
alertcondition(not na(sweptBslLvl), "BSL swept", "Buy-side liquidity swept")
alertcondition(not na(sweptSslLvl), "SSL swept", "Sell-side liquidity swept")

if newLong and barstate.isconfirmed''',
'''// ═════════════════════════════════════════════════════════════════════════════
//  PERFORMANCE TABLE
// ═════════════════════════════════════════════════════════════════════════════
var table pt = table.new(position.bottom_right, 2, 7, border_width = 1)

f_prow(r, k, v) =>
    table.cell(pt, 0, r, k, text_color = color.gray,  text_size = size.small, text_halign = text.align_left)
    table.cell(pt, 1, r, v, text_color = color.white, text_size = size.small, text_halign = text.align_right)

if showTable and barstate.islast
    tot = strategy.closedtrades
    wr  = tot > 0 ? 100.0 * strategy.wintrades / tot : 0.0      // 100.0 first: int/int truncates
    pf  = strategy.grossloss > 0 ? strategy.grossprofit / strategy.grossloss : na
    f_prow(0, "Trades",     str.tostring(tot))
    f_prow(1, "Win rate",   str.tostring(wr, "#.#") + " %")
    f_prow(2, "Profit fac", na(pf) ? "—" : str.tostring(pf, "#.##"))
    f_prow(3, "Net P/L",    str.tostring(strategy.netprofit, "#.##"))
    f_prow(4, "Equity",     str.tostring(strategy.equity, "#.##"))
    f_prow(5, "Max DD",     str.tostring(strategy.max_drawdown, "#.##"))
    f_prow(6, "Today",      str.tostring(tradesToday) + " trades  " + str.tostring(dayPnL, "#.##"))

// ═════════════════════════════════════════════════════════════════════════════
//  ALERTS
// ═════════════════════════════════════════════════════════════════════════════
if entLong and barstate.isconfirmed''')
rep('if newShort and barstate.isconfirmed\n    alert("XAUUSD SELL "', 'if entShort and barstate.isconfirmed\n    alert("XAUUSD SELL "')

open("XAU_Regime_Scalper_STRATEGY.pine", "w").write(s)
print(f"strategy generated from indicator: {n} transforms, {len(s.splitlines())} lines")
