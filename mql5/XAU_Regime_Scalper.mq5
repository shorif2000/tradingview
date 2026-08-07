//+------------------------------------------------------------------+
//|  XAU Regime Scalper - 5M                                         |
//|  Expert Advisor for MetaTrader 5                                 |
//|                                                                  |
//|  Same decision logic as the TradingView version:                 |
//|    1. LIQUIDITY SWEEP - stops taken above a swing high (BSL) or   |
//|       below a swing low (SSL), then price closes straight back.   |
//|    2. TREND pullback  - buy dips to the fast EMA in a trend.      |
//|    3. RANGE fade      - fade failed Bollinger breakouts.          |
//|  Every signal must collect >= N independent reasons, which are    |
//|  printed on the chart and in the journal so you can see why.      |
//|                                                                  |
//|  Attach to a 5-minute XAUUSD chart. Works in the Strategy Tester. |
//|  It also DRAWS the liquidity map, so it doubles as the indicator. |
//|                                                                  |
//|  File is deliberately ASCII-only so MetaEditor cannot mangle it.  |
//+------------------------------------------------------------------+
#property copyright "XAU Regime Scalper"
#property version   "2.10"

#include <Trade\Trade.mqh>

//====================================================================
//  INPUTS
//====================================================================
input group "=== Trading ==="
input double InpLots              = 0.01;   // Fixed lot size
input double InpRR                = 2.0;    // Take profit (x risk)
input long   InpMagic             = 20260805;
input int    InpSlippagePoints    = 30;     // Max deviation (points)
input bool   InpAllowLong         = true;
input bool   InpAllowShort        = true;

input group "=== Session (defined in UTC) ==="
input bool   InpUseSession        = true;
input int    InpServerGmtOffset   = 2;      // Broker server offset from UTC (Vantage: 2 winter, 3 summer)
input int    InpSessionStartUTC   = 7;      // 07:00 UTC = 07:00 London winter, 08:00 London summer
input int    InpSessionEndUTC     = 20;     // exclusive
input bool   InpBlockFridayLate   = true;   // no new trades after Fri 18:00 UTC

//-------------------------------------------------------------------
//  Every feature below is a switch. Turn a module off and it stops
//  trading; turn a confirmation off and it can no longer score a point
//  for any module. The reason text in the journal and on the chart
//  updates to match, so you can always see which rules are live.
//-------------------------------------------------------------------
input group "=== Modules - what is allowed to trade ==="
input bool   InpUseSweepModule    = true;   // Liquidity sweep entries
input bool   InpUseTrendModule    = false;  // Trend pullback entries (see README: ~zero expectancy in both tested samples)
input bool   InpUseRangeModule    = true;   // Range fade entries (carried both tested samples)

input group "=== Confirmations - what may score a point ==="
input bool   InpConfEmaReclaim    = true;   // EMA reclaim / rejection
input bool   InpConfEngulfing     = true;   // Engulfing candle
input bool   InpConfPinBar        = true;   // Pin bar / hammer / shooting star
input bool   InpConfRsi50Cross    = true;   // RSI(14) crossing 50
input bool   InpConfStructure     = true;   // Higher low / lower high
input bool   InpConfDiExpansion   = true;   // +DI / -DI expanding
input bool   InpConfRsiExtreme    = true;   // Fast RSI oversold / overbought
input bool   InpConfDivergence    = true;   // Price / RSI divergence
input bool   InpConfBbFailure     = true;   // Failed Bollinger breakout
input bool   InpConfRangeExtreme  = true;   // Range floor / ceiling tag
input bool   InpConfSweepReclaim  = true;   // Swept level reclaimed
input bool   InpConfEmaSide       = true;   // Back on the right side of the fast EMA
input bool   InpConfLiqInRange    = true;   // Credit a sweep inside the range module

input group "=== Volatility filter ==="
input bool   InpUseVolFilter      = true;   // Volatility band filter
input int    InpAtrLen            = 14;
input double InpMinAtrPct         = 0.020;  // % of price
input double InpMaxAtrPct         = 0.250;

input group "=== Regime ==="
input int    InpAdxLen            = 14;
input double InpAdxTrendOn        = 23.0;
input double InpAdxTrendOff       = 18.0;
input double InpAdxRangeOn        = 18.0;
input double InpAdxRangeOff       = 23.0;
input double InpBbwRankMax        = 45.0;   // percentile rank of BB width
input bool   InpUseHTF            = true;   // require H1 agreement for trend trades
input int    InpHtfFast           = 50;
input int    InpHtfSlow           = 200;

input group "=== Liquidity (BSL / SSL) ==="
input int    InpPivotLen          = 5;      // swing strength
input double InpLiqEqTolATR       = 0.30;   // equal-level tolerance (x ATR)
input int    InpLiqMaxAge         = 400;    // forget a pool after N bars
input int    InpSweepMinTouches   = 2;      // 2 = equal highs/lows only
input int    InpSweepLookback     = 3;      // entry allowed N bars after the grab
input int    InpSweepMinScore     = 2;

input group "=== Trend module ==="
input int    InpEmaFast           = 20;
input int    InpEmaMid            = 50;
input int    InpEmaSlow           = 200;
input double InpPbTolATR          = 0.35;
input int    InpPbLookback        = 6;
input int    InpTrendMinScore     = 2;

input group "=== Range module ==="
input int    InpBbLen             = 20;
input double InpBbMult            = 2.0;
input int    InpRsiFastLen        = 7;
input double InpRsiOS             = 22.0;
input double InpRsiOB             = 78.0;
input int    InpDonLen            = 50;
input double InpDonTolATR         = 0.15;   // range-extreme tag tolerance (x ATR)
input int    InpRangeMinScore     = 2;

input group "=== Risk and exits ==="
input double InpSlPadATR          = 0.35;
input int    InpSwingLen          = 8;
input double InpMinStopATR        = 0.80;
input double InpMaxStopATR        = 2.00;   // skip trades needing a wider stop
input bool   InpUseBreakEven      = false;  // move stop to entry at +1R
input bool   InpUseTimeStop       = true;
input int    InpTimeStopBars      = 60;
input bool   InpUseDailyLimits    = true;   // Daily trade / loss caps
input int    InpMaxTradesDay      = 6;      // 0 = unlimited
input double InpMaxLossDayCcy     = 6.0;    // 0 = off, in account currency

input group "=== Display ==="
input bool   InpShowLiquidity     = true;
input bool   InpShowSignals       = true;
input bool   InpShowLevels        = true;
input bool   InpShowPanel         = true;
input color  InpColBSL            = clrTomato;
input color  InpColSSL            = clrDodgerBlue;
input color  InpColSwept          = clrGoldenrod;

//====================================================================
//  GLOBALS
//====================================================================
CTrade trade;

int hAtr = INVALID_HANDLE, hAdx = INVALID_HANDLE, hBands = INVALID_HANDLE;
int hRsi = INVALID_HANDLE, hRsiF = INVALID_HANDLE;
int hEmaF = INVALID_HANDLE, hEmaM = INVALID_HANDLE, hEmaS = INVALID_HANDLE;
int hHtfFast = INVALID_HANDLE, hHtfSlow = INVALID_HANDLE;

datetime lastBarTime = 0;

bool regimeTrend = false;      // stateful, with hysteresis
bool regimeRange = false;

struct Pool
  {
   double   price;
   int      touch;
   datetime born;
   bool     swept;             // drawing kept, no longer tradable
   string   objLine;
   string   objLabel;
   bool     alive;
  };

Pool bslPools[];
Pool sslPools[];
int  poolSeq = 0;

// last liquidity grab, kept live for InpSweepLookback bars
double   grabBslLvl = 0.0,  grabSslLvl = 0.0;
double   grabBslWick = 0.0, grabSslWick = 0.0;   // the extreme the sweep printed
int      grabBslTouch = 0,  grabSslTouch = 0;
datetime grabBslTime = 0,   grabSslTime = 0;
datetime usedGrabBsl = 0,   usedGrabSsl = 0;     // never trade one pool twice

// swing memory for structure / divergence
double lastPH = 0, prevPH = 0, lastPL = 0, prevPL = 0;
double lastPHr = 0, prevPHr = 0, lastPLr = 0, prevPLr = 0;
bool   havePH = false, havePrevPH = false, havePL = false, havePrevPL = false;

// position bookkeeping
datetime entryBarTime = 0;
bool     beDone = false;

// daily guards
int    tradesToday = 0;
double dayStartEquity = 0.0;
int    currentUtcDay = -1;

string OBJ = "XRS_";

//====================================================================
//  INIT / DEINIT
//====================================================================
int OnInit()
  {
   if(Period() != PERIOD_M5)
      Print("WARNING: designed for M5; current chart is ", EnumToString((ENUM_TIMEFRAMES)Period()));

   // ---- input validation: bad values here fail silently and confusingly ----
   if(InpPivotLen < 2 || InpEmaFast < 2 || InpEmaMid < 2 || InpEmaSlow < 3 ||
      InpRR <= 0.0 || InpLots <= 0.0 || InpSweepMinScore < 1 ||
      InpTrendMinScore < 1 || InpRangeMinScore < 1 || InpAtrLen < 2 ||
      InpMinStopATR <= 0.0 || InpMaxStopATR < InpMinStopATR)
     {
      Print("Invalid inputs: check PivotLen>=2, EMA lengths, RR>0, Lots>0, "
            "min scores>=1 and MaxStopATR>=MinStopATR");
      return(INIT_PARAMETERS_INCORRECT);
     }

   hAtr   = iATR(_Symbol, PERIOD_CURRENT, InpAtrLen);
   hAdx   = iADX(_Symbol, PERIOD_CURRENT, InpAdxLen);
   hBands = iBands(_Symbol, PERIOD_CURRENT, InpBbLen, 0, InpBbMult, PRICE_CLOSE);
   hRsi   = iRSI(_Symbol, PERIOD_CURRENT, 14, PRICE_CLOSE);
   hRsiF  = iRSI(_Symbol, PERIOD_CURRENT, InpRsiFastLen, PRICE_CLOSE);
   hEmaF  = iMA(_Symbol, PERIOD_CURRENT, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
   hEmaM  = iMA(_Symbol, PERIOD_CURRENT, InpEmaMid,  0, MODE_EMA, PRICE_CLOSE);
   hEmaS  = iMA(_Symbol, PERIOD_CURRENT, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   hHtfFast = iMA(_Symbol, PERIOD_H1, InpHtfFast, 0, MODE_EMA, PRICE_CLOSE);
   hHtfSlow = iMA(_Symbol, PERIOD_H1, InpHtfSlow, 0, MODE_EMA, PRICE_CLOSE);

   if(hAtr==INVALID_HANDLE || hAdx==INVALID_HANDLE || hBands==INVALID_HANDLE ||
      hRsi==INVALID_HANDLE || hRsiF==INVALID_HANDLE || hEmaF==INVALID_HANDLE ||
      hEmaM==INVALID_HANDLE || hEmaS==INVALID_HANDLE ||
      hHtfFast==INVALID_HANDLE || hHtfSlow==INVALID_HANDLE)
     {
      Print("Failed to create one or more indicator handles");
      return(INIT_FAILED);
     }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   ArrayResize(bslPools, 0);
   ArrayResize(sslPools, 0);
   dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);

   // Adopt a position that already exists (recompile / restart / TF change),
   // otherwise entryBarTime stays 0 and the time stop never fires for it.
   long ty; double op, s2, tp2, v2;
   if(PosOpen(ty, op, s2, tp2, v2))
     {
      entryBarTime = (datetime)PositionGetInteger(POSITION_TIME);
      beDone = false;
      Print("Adopted an existing position opened at ", TimeToString(entryBarTime));
     }

   Print("XAU Regime Scalper ready. Spread now = ",
         (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD), " points (",
         DoubleToString((int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * _Point, 2), " per oz)");
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, OBJ);
   ChartRedraw(0);
   IndicatorRelease(hAtr);  IndicatorRelease(hAdx);  IndicatorRelease(hBands);
   IndicatorRelease(hRsi);  IndicatorRelease(hRsiF);
   IndicatorRelease(hEmaF); IndicatorRelease(hEmaM); IndicatorRelease(hEmaS);
   IndicatorRelease(hHtfFast); IndicatorRelease(hHtfSlow);
  }

//====================================================================
//  HELPERS
//====================================================================
double Buf(int handle, int buffer, int shift)
  {
   double v[];
   if(CopyBuffer(handle, buffer, shift, 1, v) != 1)
      return(EMPTY_VALUE);
   return(v[0]);
  }

bool Bad(double v)
  {
   return(v == EMPTY_VALUE || !MathIsValidNumber(v));
  }

bool PosOpen(long &type, double &openPrice, double &sl, double &tp, double &vol)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      type      = PositionGetInteger(POSITION_TYPE);
      openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      sl        = PositionGetDouble(POSITION_SL);
      tp        = PositionGetDouble(POSITION_TP);
      vol       = PositionGetDouble(POSITION_VOLUME);
      return(true);
     }
   return(false);
  }

datetime ToUtc(datetime serverTime)
  {
   return((datetime)((long)serverTime - (long)InpServerGmtOffset * 3600));
  }

int UtcHour(datetime serverTime)
  {
   MqlDateTime st; TimeToStruct(ToUtc(serverTime), st);
   return(st.hour);
  }

int UtcDayOfWeek(datetime serverTime)
  {
   MqlDateTime st; TimeToStruct(ToUtc(serverTime), st);
   return(st.day_of_week);      // 0 = Sunday
  }

int UtcDayOfMonth(datetime serverTime)
  {
   MqlDateTime st; TimeToStruct(ToUtc(serverTime), st);
   return(st.day);
  }

bool SessionOpen(datetime barTime)
  {
   if(!InpUseSession) return(true);
   int h = UtcHour(barTime);
   if(h < InpSessionStartUTC || h >= InpSessionEndUTC) return(false);
   if(InpBlockFridayLate && UtcDayOfWeek(barTime) == 5 && h >= 18) return(false);
   return(true);
  }

// Percentile rank of the current Bollinger width against the previous N values.
// These local arrays are NOT series-indexed, so element [need-1] is the most
// recent bar (shift 1) and [0] is the oldest.
double BbWidthRank(int lookback)
  {
   int need = lookback + 1;
   double up[], lo[], mid[];
   if(CopyBuffer(hBands, 1, 1, need, up)  != need) return(EMPTY_VALUE);
   if(CopyBuffer(hBands, 2, 1, need, lo)  != need) return(EMPTY_VALUE);
   if(CopyBuffer(hBands, 0, 1, need, mid) != need) return(EMPTY_VALUE);
   int last = need - 1;
   if(mid[last] == 0.0) return(EMPTY_VALUE);
   double cur = (up[last] - lo[last]) / mid[last] * 100.0;
   int cnt = 0;
   for(int i = 0; i < last; i++)
     {
      if(mid[i] == 0.0) continue;
      double w = (up[i] - lo[i]) / mid[i] * 100.0;
      if(w <= cur) cnt++;
     }
   return(100.0 * cnt / lookback);
  }

//====================================================================
//  LIQUIDITY POOL DRAWING
//====================================================================
void PoolDrawNew(Pool &p, bool isBsl)
  {
   p.objLine = ""; p.objLabel = "";
   if(!InpShowLiquidity) return;
   poolSeq++;
   p.objLine  = OBJ + "L" + IntegerToString(poolSeq);
   p.objLabel = OBJ + "T" + IntegerToString(poolSeq);
   color col  = isBsl ? InpColBSL : InpColSSL;
   ObjectCreate(0, p.objLine, OBJ_TREND, 0, p.born, p.price, TimeCurrent(), p.price);
   ObjectSetInteger(0, p.objLine, OBJPROP_COLOR, col);
   ObjectSetInteger(0, p.objLine, OBJPROP_STYLE, STYLE_DOT);
   ObjectSetInteger(0, p.objLine, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, p.objLine, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, p.objLine, OBJPROP_BACK, true);
   ObjectSetInteger(0, p.objLine, OBJPROP_SELECTABLE, false);
   ObjectCreate(0, p.objLabel, OBJ_TEXT, 0, TimeCurrent(), p.price);
   ObjectSetString(0, p.objLabel, OBJPROP_TEXT, (isBsl ? "BSL" : "SSL"));
   ObjectSetString(0, p.objLabel, OBJPROP_FONT, "Arial");
   ObjectSetInteger(0, p.objLabel, OBJPROP_FONTSIZE, 7);
   ObjectSetInteger(0, p.objLabel, OBJPROP_COLOR, col);
   ObjectSetInteger(0, p.objLabel, OBJPROP_SELECTABLE, false);
  }

void PoolRefresh(Pool &p, bool isBsl, datetime rightEdge)
  {
   if(p.objLine == "") return;
   ObjectMove(0, p.objLine, 0, p.born, p.price);
   ObjectMove(0, p.objLine, 1, rightEdge, p.price);
   ObjectSetInteger(0, p.objLine, OBJPROP_WIDTH, p.touch >= 2 ? 2 : 1);
   if(p.objLabel != "")
     {
      ObjectMove(0, p.objLabel, 0, rightEdge, p.price);
      ObjectSetString(0, p.objLabel, OBJPROP_TEXT,
                      (isBsl ? "BSL x" : "SSL x") + IntegerToString(p.touch));
     }
  }

void PoolMarkSwept(Pool &p, bool isBsl, datetime when)
  {
   if(p.objLine == "") return;
   ObjectSetInteger(0, p.objLine, OBJPROP_COLOR, InpColSwept);
   ObjectSetInteger(0, p.objLine, OBJPROP_STYLE, STYLE_SOLID);
   ObjectMove(0, p.objLine, 1, when, p.price);
   if(p.objLabel != "")
     {
      ObjectSetString(0, p.objLabel, OBJPROP_TEXT,
                      (isBsl ? "BSL swept x" : "SSL swept x") + IntegerToString(p.touch));
      ObjectSetInteger(0, p.objLabel, OBJPROP_COLOR, InpColSwept);
      ObjectMove(0, p.objLabel, 0, when, p.price);
     }
  }

void PoolKill(Pool &p)
  {
   if(p.objLine  != "") ObjectDelete(0, p.objLine);
   if(p.objLabel != "") ObjectDelete(0, p.objLabel);
   p.alive = false;
  }

void PoolCompact(Pool &arr[])
  {
   int w = 0;
   for(int i = 0; i < ArraySize(arr); i++)
      if(arr[i].alive)
        {
         if(w != i) arr[w] = arr[i];
         w++;
        }
   ArrayResize(arr, w);
  }

//====================================================================
//  MAIN
//====================================================================
void OnTick()
  {
   datetime t0 = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t0 == 0 || t0 == lastBarTime) return;      // act once per completed bar

   int bars = Bars(_Symbol, PERIOD_CURRENT);
   int warmup = (int)MathMax(InpEmaSlow, 200) + InpPivotLen * 2 + 260;
   if(bars < warmup) return;

   MqlRates rt[];
   ArraySetAsSeries(rt, true);
   int need = (int)MathMax(InpDonLen, MathMax(InpSwingLen, InpPivotLen * 2 + 3)) + 6;
   if(CopyRates(_Symbol, PERIOD_CURRENT, 1, need, rt) < need) return;
   lastBarTime = t0;                              // only consume the bar once data is good
   // rt[0] = last CLOSED bar

   double o = rt[0].open, h = rt[0].high, l = rt[0].low, c = rt[0].close;
   double o1 = rt[1].open, h1 = rt[1].high, l1 = rt[1].low, c1 = rt[1].close;
   datetime barTime = rt[0].time;

   // ---------- rolling day bookkeeping, aligned to the UTC session ----------
   int utcDay = UtcDayOfMonth(barTime);
   if(utcDay != currentUtcDay)
     {
      currentUtcDay  = utcDay;
      tradesToday    = 0;
      dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
     }

   // ---------- indicators, all read at the last closed bar ----------
   double atr   = Buf(hAtr, 0, 1);
   double adx   = Buf(hAdx, 0, 1);
   double diP   = Buf(hAdx, 1, 1);
   double diM   = Buf(hAdx, 2, 1);
   double diP1  = Buf(hAdx, 1, 2);
   double diM1  = Buf(hAdx, 2, 2);
   double bbUp  = Buf(hBands, 1, 1);
   double bbLo  = Buf(hBands, 2, 1);
   double bbUp1 = Buf(hBands, 1, 2);
   double bbLo1 = Buf(hBands, 2, 2);
   double rsi   = Buf(hRsi, 0, 1);
   double rsi1  = Buf(hRsi, 0, 2);
   double rsiF  = Buf(hRsiF, 0, 1);
   double rsiF1 = Buf(hRsiF, 0, 2);
   double emaF  = Buf(hEmaF, 0, 1);
   double emaF1 = Buf(hEmaF, 0, 2);
   double emaM  = Buf(hEmaM, 0, 1);
   double emaS  = Buf(hEmaS, 0, 1);

   if(Bad(atr) || atr <= 0 || Bad(adx) || Bad(emaS) || Bad(emaM) ||
      Bad(emaF) || Bad(emaF1) || Bad(rsi) || Bad(rsiF) || Bad(bbUp) || Bad(bbLo))
      return;

   double atrPct  = atr / c * 100.0;
   double bbwRank = BbWidthRank(200);

   // ---------- regime, with hysteresis ----------
   regimeTrend = regimeTrend ? (adx >= InpAdxTrendOff) : (adx > InpAdxTrendOn);
   bool rangeOn = (adx < InpAdxRangeOn) && (!Bad(bbwRank)) && (bbwRank < InpBbwRankMax);
   regimeRange = regimeRange ? (adx <= InpAdxRangeOff) : rangeOn;
   if(regimeTrend && regimeRange) regimeRange = false;

   bool bullBias = (emaM > emaS) && (emaF > emaM);
   bool bearBias = (emaM < emaS) && (emaF < emaM);

   // H1 agreement. If the H1 EMAs have no history the filter ABSTAINS instead of
   // vetoing every trade on one side.
   double hf = Buf(hHtfFast, 0, 1), hs = Buf(hHtfSlow, 0, 1);
   bool htfKnown = (!Bad(hf) && !Bad(hs) && hf > 0 && hs > 0);
   bool htfBull  = htfKnown && (hf > hs);
   bool htfOKL   = (!InpUseHTF) || (!htfKnown) || htfBull;
   bool htfOKS   = (!InpUseHTF) || (!htfKnown) || (!htfBull);

   bool volOK  = (!InpUseVolFilter) || (atrPct >= InpMinAtrPct && atrPct <= InpMaxAtrPct);
   bool gateOK = SessionOpen(barTime) && volOK;

   // ---------- candlestick patterns ----------
   double body   = MathAbs(c - o);
   double rng    = MathMax(h - l, _Point);
   double upWick = h - MathMax(o, c);
   double dnWick = MathMin(o, c) - l;
   bool bullEng = (c > o) && (c1 < o1) && (c >= o1) && (o <= c1);
   bool bearEng = (c < o) && (c1 > o1) && (c <= o1) && (o >= c1);
   // use <= on the opposite wick so a doji-bodied pin bar still qualifies
   bool hammer  = (dnWick > body * 1.5) && (upWick <= body) && (body / rng < 0.5);
   bool shooter = (upWick > body * 1.5) && (dnWick <= body) && (body / rng < 0.5);
   bool bullPin = (dnWick / rng > 0.5) && (c >= o);
   bool bearPin = (upWick / rng > 0.5) && (c <= o);

   // ---------- swing detection: pivot confirmed InpPivotLen bars back ----------
   int P = InpPivotLen;
   bool isPH = true, isPL = true;
   double pvH = rt[P].high, pvL = rt[P].low;
   for(int k = 0; k <= 2 * P; k++)
     {
      if(k == P) continue;
      // strict on the newer side so the FIRST of two identical highs still counts
      if(k < P) { if(rt[k].high >  pvH) isPH = false; if(rt[k].low <  pvL) isPL = false; }
      else      { if(rt[k].high >= pvH) isPH = false; if(rt[k].low <= pvL) isPL = false; }
     }
   double rsiAtPivot = Buf(hRsi, 0, 1 + P);

   if(isPH)
     {
      prevPH = lastPH;  havePrevPH = havePH;
      lastPH = pvH;     havePH = true;
      prevPHr = lastPHr; lastPHr = rsiAtPivot;
     }
   if(isPL)
     {
      prevPL = lastPL;  havePrevPL = havePL;
      lastPL = pvL;     havePL = true;
      prevPLr = lastPLr; lastPLr = rsiAtPivot;
     }
   bool higherLow  = havePL && havePrevPL && (lastPL > prevPL);
   bool higherHigh = havePH && havePrevPH && (lastPH > prevPH);
   bool lowerHigh  = havePH && havePrevPH && (lastPH < prevPH);
   bool bullDiv    = havePL && havePrevPL && (lastPL < prevPL) && (lastPLr > prevPLr);
   bool bearDiv    = havePH && havePrevPH && (lastPH > prevPH) && (lastPHr < prevPHr);

   // ---------- register new pools, merging equal levels ----------
   double tol = InpLiqEqTolATR * atr;
   if(isPH)
     {
      bool merged = false;
      for(int i = 0; i < ArraySize(bslPools); i++)
        {
         if(!bslPools[i].alive || bslPools[i].swept) continue;
         if(MathAbs(bslPools[i].price - pvH) <= tol)
           {
            bslPools[i].price = MathMax(bslPools[i].price, pvH);
            bslPools[i].touch++;
            bslPools[i].born  = rt[P].time;
            merged = true;
            break;
           }
        }
      if(!merged)
        {
         Pool np; np.price = pvH; np.touch = 1; np.born = rt[P].time;
         np.alive = true; np.swept = false;
         PoolDrawNew(np, true);
         int nb = ArraySize(bslPools); ArrayResize(bslPools, nb + 1); bslPools[nb] = np;
        }
     }
   if(isPL)
     {
      bool merged = false;
      for(int i = 0; i < ArraySize(sslPools); i++)
        {
         if(!sslPools[i].alive || sslPools[i].swept) continue;
         if(MathAbs(sslPools[i].price - pvL) <= tol)
           {
            sslPools[i].price = MathMin(sslPools[i].price, pvL);
            sslPools[i].touch++;
            sslPools[i].born  = rt[P].time;
            merged = true;
            break;
           }
        }
      if(!merged)
        {
         Pool np; np.price = pvL; np.touch = 1; np.born = rt[P].time;
         np.alive = true; np.swept = false;
         PoolDrawNew(np, false);
         int ns = ArraySize(sslPools); ArrayResize(sslPools, ns + 1); sslPools[ns] = np;
        }
     }

   // ---------- test this bar against live pools ----------
   //  A poke smaller than `tol` that closes back is the level being PROBED, so
   //  count it as a touch and keep the pool alive. Consuming it on any pierce
   //  would stop equal highs/lows ever reaching touch >= 2.
   int    ageSecs = InpLiqMaxAge * PeriodSeconds(PERIOD_CURRENT);
   double sweptB = 0.0, sweptBw = 0.0; int sweptBt = 0;
   for(int i = 0; i < ArraySize(bslPools); i++)
     {
      if(!bslPools[i].alive) continue;
      if(barTime - bslPools[i].born > ageSecs) { PoolKill(bslPools[i]); continue; }
      if(bslPools[i].swept) continue;                 // drawing only, ages out above
      if(h > bslPools[i].price + tol)
        {
         if(c < bslPools[i].price)                    // pierced well beyond, rejected
           {
            if(bslPools[i].touch >= sweptBt)
              { sweptB = bslPools[i].price; sweptBt = bslPools[i].touch; sweptBw = h; }
            PoolMarkSwept(bslPools[i], true, barTime);
            bslPools[i].swept = true;                 // keep drawing, stop trading it
           }
         else
            PoolKill(bslPools[i]);                    // genuine break
        }
      else if(h > bslPools[i].price)
        {
         bslPools[i].price = MathMax(bslPools[i].price, h);
         bslPools[i].touch++;
         bslPools[i].born  = barTime;
         PoolRefresh(bslPools[i], true, barTime + PeriodSeconds(PERIOD_CURRENT) * 3);
        }
      else
         PoolRefresh(bslPools[i], true, barTime + PeriodSeconds(PERIOD_CURRENT) * 3);
     }
   double sweptS = 0.0, sweptSw = 0.0; int sweptSt = 0;
   for(int i = 0; i < ArraySize(sslPools); i++)
     {
      if(!sslPools[i].alive) continue;
      if(barTime - sslPools[i].born > ageSecs) { PoolKill(sslPools[i]); continue; }
      if(sslPools[i].swept) continue;
      if(l < sslPools[i].price - tol)
        {
         if(c > sslPools[i].price)
           {
            if(sslPools[i].touch >= sweptSt)
              { sweptS = sslPools[i].price; sweptSt = sslPools[i].touch; sweptSw = l; }
            PoolMarkSwept(sslPools[i], false, barTime);
            sslPools[i].swept = true;
           }
         else
            PoolKill(sslPools[i]);
        }
      else if(l < sslPools[i].price)
        {
         sslPools[i].price = MathMin(sslPools[i].price, l);
         sslPools[i].touch++;
         sslPools[i].born  = barTime;
         PoolRefresh(sslPools[i], false, barTime + PeriodSeconds(PERIOD_CURRENT) * 3);
        }
      else
         PoolRefresh(sslPools[i], false, barTime + PeriodSeconds(PERIOD_CURRENT) * 3);
     }
   PoolCompact(bslPools);
   PoolCompact(sslPools);

   // A later WEAKER grab must not overwrite a live stronger one.
   int lookSecs = InpSweepLookback * PeriodSeconds(PERIOD_CURRENT);
   if(sweptB > 0.0 && (grabBslTime == 0 || sweptBt >= grabBslTouch ||
                       (barTime - grabBslTime) > lookSecs))
     { grabBslLvl = sweptB; grabBslWick = sweptBw; grabBslTouch = sweptBt; grabBslTime = barTime; }
   if(sweptS > 0.0 && (grabSslTime == 0 || sweptSt >= grabSslTouch ||
                       (barTime - grabSslTime) > lookSecs))
     { grabSslLvl = sweptS; grabSslWick = sweptSw; grabSslTouch = sweptSt; grabSslTime = barTime; }

   bool bslGrabLive = InpUseSweepModule && grabBslTime > 0 && grabBslLvl > 0.0 &&
                      (barTime - grabBslTime) <= lookSecs &&
                      grabBslTouch >= InpSweepMinTouches && usedGrabBsl != grabBslTime;
   bool sslGrabLive = InpUseSweepModule && grabSslTime > 0 && grabSslLvl > 0.0 &&
                      (barTime - grabSslTime) <= lookSecs &&
                      grabSslTouch >= InpSweepMinTouches && usedGrabSsl != grabSslTime;

   // ---------- manage an open position ----------
   long pType; double pOpen, pSl, pTp, pVol;
   if(PosOpen(pType, pOpen, pSl, pTp, pVol))
     {
      if(InpUseBreakEven && !beDone && pSl > 0.0)
        {
         double r0 = (pType == POSITION_TYPE_BUY) ? (pOpen - pSl) : (pSl - pOpen);
         if(r0 > 0)
           {
            // only latch beDone if the modify was ACCEPTED, else it never retries
            if(pType == POSITION_TYPE_BUY && h >= pOpen + r0)
              { if(trade.PositionModify(_Symbol, NormalizeDouble(pOpen, _Digits), pTp)) beDone = true; }
            if(pType == POSITION_TYPE_SELL && l <= pOpen - r0)
              { if(trade.PositionModify(_Symbol, NormalizeDouble(pOpen, _Digits), pTp)) beDone = true; }
           }
        }
      if(InpUseTimeStop && entryBarTime > 0 &&
         (barTime - entryBarTime) >= (datetime)(InpTimeStopBars * PeriodSeconds(PERIOD_CURRENT)))
        {
         if(trade.PositionClose(_Symbol))
            Print("Time stop: closed after ", InpTimeStopBars, " bars");
        }
      DrawPanel(bullBias, bearBias, adx, atr, atrPct, htfKnown, htfBull, gateOK,
                ArraySize(bslPools), ArraySize(sslPools));
      ChartRedraw(0);
      return;                                    // one position at a time
     }
   beDone = false;
   entryBarTime = 0;

   DrawPanel(bullBias, bearBias, adx, atr, atrPct, htfKnown, htfBull, gateOK,
             ArraySize(bslPools), ArraySize(sslPools));
   ChartRedraw(0);

   // ---------- guards ----------
   if(!gateOK) return;
   if(InpUseDailyLimits)
     {
      if(InpMaxTradesDay > 0 && tradesToday >= InpMaxTradesDay) return;
      if(InpMaxLossDayCcy > 0 &&
         (AccountInfoDouble(ACCOUNT_EQUITY) - dayStartEquity) <= -InpMaxLossDayCcy) return;
     }

   // ---------- pullback proximity ----------
   bool pulledL = false, pulledS = false;
   double efArr[];
   if(CopyBuffer(hEmaF, 0, 1, InpPbLookback + 1, efArr) == InpPbLookback + 1)
      for(int k = 0; k <= InpPbLookback; k++)
        {
         double ef_k = efArr[InpPbLookback - k];    // not series-indexed
         if(Bad(ef_k)) continue;
         if(rt[k].low  <= ef_k + InpPbTolATR * atr) pulledL = true;
         if(rt[k].high >= ef_k - InpPbTolATR * atr) pulledS = true;
        }

   // ================= SCORING =================
   int    swl = 0, sws = 0, tl = 0, ts = 0, rl = 0, rs = 0;
   string swlR = "", swsR = "", tlR = "", tsR = "", rlR = "", rsR = "";

   if(sslGrabLive)
     {
      swl++; swlR = "SSL sweep (x" + IntegerToString(grabSslTouch) + " @ " + DoubleToString(grabSslLvl, _Digits) + ")";
      if(InpConfSweepReclaim && c > grabSslLvl) { swl++; swlR += " + reclaimed the swept level"; }
      if(InpConfPinBar && (hammer || bullPin || bullEng)) { swl++; swlR += " + bullish rejection candle"; }
      if(InpConfRsiExtreme && (rsiF < InpRsiOS || rsiF1 < InpRsiOS)) { swl++; swlR += " + fast RSI oversold " + DoubleToString(rsiF, 0); }
      if(InpConfDivergence && bullDiv)          { swl++; swlR += " + bullish RSI divergence"; }
      if(InpConfEmaSide && c > emaF)            { swl++; swlR += " + back above EMA fast"; }
     }
   if(bslGrabLive)
     {
      sws++; swsR = "BSL sweep (x" + IntegerToString(grabBslTouch) + " @ " + DoubleToString(grabBslLvl, _Digits) + ")";
      if(InpConfSweepReclaim && c < grabBslLvl) { sws++; swsR += " + rejected back below the swept level"; }
      if(InpConfPinBar && (shooter || bearPin || bearEng)) { sws++; swsR += " + bearish rejection candle"; }
      if(InpConfRsiExtreme && (rsiF > InpRsiOB || rsiF1 > InpRsiOB)) { sws++; swsR += " + fast RSI overbought " + DoubleToString(rsiF, 0); }
      if(InpConfDivergence && bearDiv)          { sws++; swsR += " + bearish RSI divergence"; }
      if(InpConfEmaSide && c < emaF)            { sws++; swsR += " + back below EMA fast"; }
     }
   if(InpUseTrendModule && regimeTrend && bullBias && htfOKL && pulledL)
     {
      if(InpConfEmaReclaim && c > emaF && c1 <= emaF1) { tl++; if(tlR!="") tlR += " + "; tlR += "EMA" + IntegerToString(InpEmaFast) + " reclaim"; }
      if(InpConfEngulfing && bullEng)      { tl++; if(tlR!="") tlR += " + "; tlR += "bullish engulfing"; }
      if(InpConfPinBar && (hammer || bullPin)) { tl++; if(tlR!="") tlR += " + "; tlR += "bullish pin/hammer"; }
      if(InpConfRsi50Cross && rsi > 50 && rsi1 <= 50) { tl++; if(tlR!="") tlR += " + "; tlR += "RSI reclaims 50"; }
      if(InpConfStructure && higherLow)    { tl++; if(tlR!="") tlR += " + "; tlR += "higher low"; }
      if(InpConfStructure && higherHigh)   { tl++; if(tlR!="") tlR += " + "; tlR += "higher high"; }
      if(InpConfDiExpansion && diP > diM && diP > diP1) { tl++; if(tlR!="") tlR += " + "; tlR += "+DI expanding"; }
     }
   if(InpUseTrendModule && regimeTrend && bearBias && htfOKS && pulledS)
     {
      if(InpConfEmaReclaim && c < emaF && c1 >= emaF1) { ts++; if(tsR!="") tsR += " + "; tsR += "EMA" + IntegerToString(InpEmaFast) + " rejection"; }
      if(InpConfEngulfing && bearEng)      { ts++; if(tsR!="") tsR += " + "; tsR += "bearish engulfing"; }
      if(InpConfPinBar && (shooter || bearPin)) { ts++; if(tsR!="") tsR += " + "; tsR += "bearish pin/shooting star"; }
      if(InpConfRsi50Cross && rsi < 50 && rsi1 >= 50) { ts++; if(tsR!="") tsR += " + "; tsR += "RSI loses 50"; }
      if(InpConfStructure && lowerHigh)    { ts++; if(tsR!="") tsR += " + "; tsR += "lower high"; }
      if(InpConfDiExpansion && diM > diP && diM > diM1) { ts++; if(tsR!="") tsR += " + "; tsR += "-DI expanding"; }
     }
   if(InpUseRangeModule && regimeRange)
     {
      double donHi = rt[1].high, donLo = rt[1].low;
      for(int k = 1; k <= InpDonLen && k < need; k++)
        {
         donHi = MathMax(donHi, rt[k].high);
         donLo = MathMin(donLo, rt[k].low);
        }
      double dtol = InpDonTolATR * atr;          // ATR-relative, not a % of price
      if(InpConfLiqInRange && sslGrabLive)      { rl++; if(rlR!="") rlR += " + "; rlR += "SSL swept x" + IntegerToString(grabSslTouch); }
      if(InpConfBbFailure && l1 < bbLo1 && c > bbLo) { rl++; if(rlR!="") rlR += " + "; rlR += "failed BB-low breakdown"; }
      if(InpConfRsiExtreme && (rsiF < InpRsiOS || rsiF1 < InpRsiOS)) { rl++; if(rlR!="") rlR += " + "; rlR += "fast RSI oversold " + DoubleToString(rsiF, 0); }
      if(InpConfRangeExtreme && l <= donLo + dtol) { rl++; if(rlR!="") rlR += " + "; rlR += "range floor tag"; }
      if(InpConfPinBar && (hammer || bullPin || bullEng)) { rl++; if(rlR!="") rlR += " + "; rlR += "bullish rejection candle"; }
      if(InpConfDivergence && bullDiv)          { rl++; if(rlR!="") rlR += " + "; rlR += "bullish RSI divergence"; }

      if(InpConfLiqInRange && bslGrabLive)      { rs++; if(rsR!="") rsR += " + "; rsR += "BSL swept x" + IntegerToString(grabBslTouch); }
      if(InpConfBbFailure && h1 > bbUp1 && c < bbUp) { rs++; if(rsR!="") rsR += " + "; rsR += "failed BB-high breakout"; }
      if(InpConfRsiExtreme && (rsiF > InpRsiOB || rsiF1 > InpRsiOB)) { rs++; if(rsR!="") rsR += " + "; rsR += "fast RSI overbought " + DoubleToString(rsiF, 0); }
      if(InpConfRangeExtreme && h >= donHi - dtol) { rs++; if(rsR!="") rsR += " + "; rsR += "range ceiling tag"; }
      if(InpConfPinBar && (shooter || bearPin || bearEng)) { rs++; if(rsR!="") rsR += " + "; rsR += "bearish rejection candle"; }
      if(InpConfDivergence && bearDiv)          { rs++; if(rsR!="") rsR += " + "; rsR += "bearish RSI divergence"; }
     }

   // ---------- pick the module: sweep > trend > range ----------
   //  Ties are SKIPPED, not resolved arbitrarily: both sides being raided within
   //  the same window is the choppiest possible condition to be trading.
   int    dir = 0, score = 0;
   string reasons = "", modName = "";
   if(swl >= InpSweepMinScore && swl > sws)          { dir =  1; score = swl; reasons = swlR; modName = "LIQUIDITY sweep"; }
   else if(sws >= InpSweepMinScore && sws > swl)     { dir = -1; score = sws; reasons = swsR; modName = "LIQUIDITY sweep"; }
   else if(tl >= InpTrendMinScore && tl > ts)        { dir =  1; score = tl;  reasons = tlR;  modName = "TREND pullback"; }
   else if(ts >= InpTrendMinScore && ts > tl)        { dir = -1; score = ts;  reasons = tsR;  modName = "TREND pullback"; }
   else if(rl >= InpRangeMinScore && rl > rs)        { dir =  1; score = rl;  reasons = rlR;  modName = "RANGE fade"; }
   else if(rs >= InpRangeMinScore && rs > rl)        { dir = -1; score = rs;  reasons = rsR;  modName = "RANGE fade"; }

   if(dir == 0) return;
   if(dir > 0 && !InpAllowLong)  return;
   if(dir < 0 && !InpAllowShort) return;

   // ================= SIZE THE TRADE =================
   double swingLo = rt[0].low, swingHi = rt[0].high;
   for(int k = 0; k < InpSwingLen && k < need; k++)
     {
      swingLo = MathMin(swingLo, rt[k].low);
      swingHi = MathMax(swingHi, rt[k].high);
     }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask <= 0.0 || bid <= 0.0) return;
   double entry = (dir > 0) ? ask : bid;

   double rawSl;
   if(modName == "LIQUIDITY sweep")
      // beyond the wick the sweep actually printed, not just the pool level -
      // otherwise a simple retest of that wick takes the trade out
      rawSl = (dir > 0) ? MathMin(MathMin(l, l1), MathMin(grabSslWick, grabSslLvl)) - InpSlPadATR * atr
                        : MathMax(MathMax(h, h1), MathMax(grabBslWick, grabBslLvl)) + InpSlPadATR * atr;
   else if(modName == "TREND pullback")
      rawSl = (dir > 0) ? swingLo - InpSlPadATR * atr
                        : swingHi + InpSlPadATR * atr;
   else
      rawSl = (dir > 0) ? MathMin(l, l1) - InpSlPadATR * atr
                        : MathMax(h, h1) + InpSlPadATR * atr;

   double dist = (dir > 0) ? MathMax(entry - rawSl, InpMinStopATR * atr)
                           : MathMax(rawSl - entry, InpMinStopATR * atr);
   if(dist > InpMaxStopATR * atr)
     {
      Print("Skipped - structure stop ", DoubleToString(dist, 2), " exceeds the ",
            DoubleToString(InpMaxStopATR, 2), "x ATR cap (", DoubleToString(InpMaxStopATR * atr, 2),
            "). ", modName, ": ", reasons);
      return;
     }

   // The server validates a BUY's stop against BID while we size from ASK, so the
   // spread has to be inside the minimum-distance allowance.
   double minStopDist = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point + (ask - bid);
   if(dist < minStopDist) dist = minStopDist * 1.1;

   double sl = NormalizeDouble((dir > 0) ? entry - dist : entry + dist, _Digits);
   double tp = NormalizeDouble((dir > 0) ? entry + InpRR * dist : entry - InpRR * dist, _Digits);

   // ---- volume ----
   double vmin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vol   = MathMax(InpLots, vmin);
   if(vstep > 0) vol = MathFloor(vol / vstep + 0.5) * vstep;
   if(vmax > 0)  vol = MathMin(vol, vmax);
   int vdig = (vstep > 0) ? (int)MathMax(0, MathRound(-MathLog10(vstep))) : 2;
   vol = NormalizeDouble(vol, vdig);

   double marginNeeded = 0.0;
   if(!OrderCalcMargin(dir > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, _Symbol, vol, entry, marginNeeded))
      marginNeeded = 0.0;
   if(marginNeeded > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
     {
      Print("Not enough free margin for ", DoubleToString(vol, 2), " lots - skipped");
      return;
     }

   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double riskCcy  = (tickSize > 0) ? dist / tickSize * tickVal * vol : 0.0;

   string note = StringFormat("%s | %s | score %d | stop %.2f (%.2f %s risk) | why: %s",
                              (dir > 0 ? "BUY" : "SELL"), modName, score, dist, riskCcy,
                              AccountInfoString(ACCOUNT_CURRENCY), reasons);

   bool sent = (dir > 0) ? trade.Buy(vol, _Symbol, ask, sl, tp, "XRS " + modName)
                         : trade.Sell(vol, _Symbol, bid, sl, tp, "XRS " + modName);
   if(!sent)
     {
      Print("Order failed: ", trade.ResultRetcode(), " ",
            trade.ResultRetcodeDescription(), " | ", note);
      return;
     }

   tradesToday++;
   entryBarTime = barTime;
   beDone = false;
   if(modName == "LIQUIDITY sweep")
     {
      if(dir > 0) usedGrabSsl = grabSslTime;    // never trade this pool again
      else        usedGrabBsl = grabBslTime;
     }
   Print(note);

   if(InpShowSignals) DrawSignal(barTime, dir, entry, sl, tp, modName, reasons, atr);
   if(InpShowLevels)  DrawLevels(barTime, entry, sl, tp);
   ChartRedraw(0);
  }

//====================================================================
//  DRAWING
//====================================================================
void DrawSignal(datetime when, int dir, double entry, double sl, double tp,
                string modName, string reasons, double atr)
  {
   string a = OBJ + "sig" + IntegerToString((int)when);
   ObjectCreate(0, a, OBJ_ARROW, 0, when, dir > 0 ? entry - atr * 0.6 : entry + atr * 0.6);
   ObjectSetInteger(0, a, OBJPROP_ARROWCODE, dir > 0 ? 233 : 234);
   ObjectSetInteger(0, a, OBJPROP_COLOR, dir > 0 ? clrTeal : clrCrimson);
   ObjectSetInteger(0, a, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, a, OBJPROP_SELECTABLE, false);

   string txt = OBJ + "sigtxt" + IntegerToString((int)when);
   ObjectCreate(0, txt, OBJ_TEXT, 0, when, dir > 0 ? entry - atr * 1.4 : entry + atr * 1.4);
   ObjectSetString(0, txt, OBJPROP_TEXT,
                   StringFormat("%s %s | SL %.2f TP %.2f | %s",
                                (dir > 0 ? "BUY" : "SELL"), modName, sl, tp, reasons));
   ObjectSetInteger(0, txt, OBJPROP_FONTSIZE, 7);
   ObjectSetInteger(0, txt, OBJPROP_COLOR, dir > 0 ? clrTeal : clrCrimson);
   ObjectSetInteger(0, txt, OBJPROP_SELECTABLE, false);
  }

void DrawLevels(datetime when, double entry, double sl, double tp)
  {
   datetime right = when + PeriodSeconds(PERIOD_CURRENT) * 30;
   string names[3]; double px[3]; color cols[3];
   names[0] = OBJ + "sl" + IntegerToString((int)when); px[0] = sl;    cols[0] = clrRed;
   names[1] = OBJ + "tp" + IntegerToString((int)when); px[1] = tp;    cols[1] = clrLimeGreen;
   names[2] = OBJ + "en" + IntegerToString((int)when); px[2] = entry; cols[2] = clrSilver;
   for(int i = 0; i < 3; i++)
     {
      ObjectCreate(0, names[i], OBJ_TREND, 0, when, px[i], right, px[i]);
      ObjectSetInteger(0, names[i], OBJPROP_COLOR, cols[i]);
      ObjectSetInteger(0, names[i], OBJPROP_STYLE, i == 2 ? STYLE_DOT : STYLE_DASH);
      ObjectSetInteger(0, names[i], OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, names[i], OBJPROP_SELECTABLE, false);
     }
  }

void DrawPanel(bool bullBias, bool bearBias, double adx, double atr, double atrPct,
               bool htfKnown, bool htfBull, bool gateOK, int nBsl, int nSsl)
  {
   if(!InpShowPanel) return;
   string regime = regimeTrend ? (bullBias ? "TREND up" : bearBias ? "TREND down" : "TREND mixed")
                               : regimeRange ? "RANGE" : "NO-TRADE";
   string lines[8];
   lines[0] = "XAU Regime Scalper";
   lines[1] = "Regime:  " + regime;
   lines[2] = StringFormat("ADX:     %.1f", adx);
   lines[3] = StringFormat("ATR:     %.2f  (%.3f%%)", atr, atrPct);
   lines[4] = "Session: " + (gateOK ? "tradable" : "blocked");
   lines[5] = "H1 bias: " + (htfKnown ? (htfBull ? "bullish" : "bearish") : "no data - abstaining");
   lines[6] = StringFormat("BSL/SSL pools: %d / %d", nBsl, nSsl);
   lines[7] = StringFormat("Today:   %d trades", tradesToday);

   for(int i = 0; i < 8; i++)
     {
      string nm = OBJ + "panel" + IntegerToString(i);
      if(ObjectFind(0, nm) < 0)
        {
         ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
         ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_RIGHT_UPPER);
         ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, 10);
         ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, 16 + i * 14);
         ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_RIGHT_UPPER);
         ObjectSetString(0, nm, OBJPROP_FONT, "Consolas");
         ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 8);
         ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
        }
      ObjectSetString(0, nm, OBJPROP_TEXT, lines[i]);
      ObjectSetInteger(0, nm, OBJPROP_COLOR,
                       i == 0 ? clrWhite :
                       (i == 1 ? (regimeTrend ? clrTeal : regimeRange ? clrDodgerBlue : clrGray)
                               : clrSilver));
     }
  }
//+------------------------------------------------------------------+
