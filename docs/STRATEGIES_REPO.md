# TA‑Lib Strategy Zoo (100 strategies)
*Designed as a diverse, indicator-driven set of rule-based strategies you can run on a single instrument or across a universe.*

## Conventions (apply to all strategies unless overridden)
**Data:** OHLCV bars (any timeframe).  
**Position sizing:** fixed % risk per trade (e.g., 0.5–1.0% of equity).  
**Orders:** enter on next bar open after signal (or close-to-close if you prefer).  
**Stops/targets:** use ATR-based rules for portability across tickers/timeframes.

### Default indicator parameters (edit globally)
- `EMA(20)`, `EMA(50)`, `EMA(200)`
- `SMA(20)`, `SMA(50)`, `SMA(200)`
- `RSI(14)` with levels 30/50/70
- `MACD(12,26,9)` → macd, signal, hist[STRATEGIES_REPO.md](STRATEGIES_REPO.md)
- `BBANDS(20, 2, 2)` → upper, middle, lower
- `ADX(14)` with trend threshold 20–25
- `ATR(14)`
- `STOCH(14,3,3)` → slowK, slowD
- `CCI(20)` with ±100
- `WILLR(14)` with −20/−80
- `MFI(14)`
- `OBV`, `ADOSC(3,10)`
- `SAR(0.02, 0.2)`
- `ROC(10)`, `MOM(10)`
- Candle patterns via `CDL*` functions

### Standard exits (building blocks)
- **Time stop:** exit after N bars (e.g., 20) if neither stop nor target hit.
- **ATR stop:** initial stop = `entry_price −/+ k*ATR` (k usually 1.5–2.5).
- **ATR target:** target = `entry_price +/− m*ATR` (m usually 2–4).
- **Trailing stop:** trail by `t*ATR` or by indicator (e.g., SAR, EMA).
- **Signal exit:** close when the opposite signal triggers.

### Tag schema (use these to group later)
Each strategy has tags across:
- **Theme:** `trend`, `mean_reversion`, `breakout`, `volatility`, `volume_flow`, `pattern`, `regime`, `multi_filter`
- **Direction:** `long_only`, `short_only`, `long_short`
- **EntryType:** `cross`, `threshold`, `pullback`, `breakout`, `pattern`, `divergence`
- **ExitType:** `signal`, `atr_stop`, `atr_target`, `trailing`, `time`
- **CoreIndicators:** list (e.g., `EMA`, `RSI`, `ADX`, `BBANDS`)
- **RegimeBias:** `trend_favor`, `range_favor`, `vol_expand`, `vol_contract`
- **Holding:** `scalp` (1–10 bars), `swing` (10–60), `position` (60+)
- **RiskProfile:** `tight`, `balanced`, `wide`

---

## A) Trend / Momentum (1–25)

### 1) EMA20/EMA50 Trend Cross
**Tags:** theme:trend; direction:long_short; entry:cross; exit:signal+atr_stop; indicators:EMA,ATR; regime:trend_favor; holding:swing  
**Entry Long:** EMA20 crosses above EMA50 AND close > EMA50.  
**Entry Short:** EMA20 crosses below EMA50 AND close < EMA50.  
**Exit:** opposite cross OR trailing stop = 2*ATR.  

### 2) EMA50/EMA200 Golden/Death Cross (slow)
**Tags:** trend; long_short; cross; signal+atr_stop; EMA,ATR; trend_favor; holding:position  
**Entry:** EMA50 crosses EMA200 (up=long, down=short).  
**Exit:** opposite cross OR stop=2.5*ATR, optional time stop 120 bars.

### 3) Price Above/Below KAMA Trend
**Tags:** trend; long_short; threshold; trailing; KAMA,ATR; trend_favor; swing  
**Entry Long:** close crosses above KAMA(30).  
**Entry Short:** close crosses below KAMA(30).  
**Exit:** close crosses back OR trail 2*ATR.

### 4) MACD Line/Signal Cross with Trend Filter
**Tags:** trend; long_short; cross; signal+atr_stop; MACD,ADX,ATR; trend_favor; swing  
**Entry Long:** MACD crosses above Signal AND ADX>20.  
**Entry Short:** MACD crosses below Signal AND ADX>20.  
**Exit:** opposite MACD cross OR stop 2*ATR.

### 5) MACD Histogram Zero-Line
**Tags:** trend; long_short; threshold; trailing; MACD,ATR; trend_favor; swing  
**Entry Long:** MACD hist crosses above 0.  
**Entry Short:** hist crosses below 0.  
**Exit:** hist crosses back OR trail 2*ATR.

### 6) ADX Rising Trend Continuation (DI+/-)
**Tags:** trend; long_short; threshold; signal+trailing; ADX,PLUS_DI,MINUS_DI,ATR; trend_favor; swing  
**Entry Long:** PLUS_DI > MINUS_DI AND ADX rising 3 bars AND ADX>20.  
**Entry Short:** MINUS_DI > PLUS_DI AND ADX rising 3 bars AND ADX>20.  
**Exit:** DI crossover OR SAR trail.

### 7) SAR Trend Ride
**Tags:** trend; long_short; threshold; trailing; SAR,ATR; trend_favor; swing  
**Entry Long:** close crosses above SAR.  
**Entry Short:** close crosses below SAR.  
**Exit:** SAR flip (close crosses opposite). Optional initial stop 2*ATR.

### 8) TRIX Signal Cross
**Tags:** trend; long_short; cross; signal+atr_stop; TRIX,ATR; trend_favor; swing  
**Entry:** TRIX(15) crosses above/below its SMA(9).  
**Exit:** opposite cross OR stop 2*ATR.

### 9) APO Momentum Cross (EMA fast-slow)
**Tags:** trend; long_short; cross; signal+atr_stop; APO,ATR; trend_favor; swing  
**Entry Long:** APO(12,26) crosses above 0 AND close>EMA50.  
**Entry Short:** APO crosses below 0 AND close<EMA50.  
**Exit:** APO crosses back OR stop 2*ATR.

### 10) ROC Break in Direction of SMA200
**Tags:** trend; long_short; threshold; atr_stop+time; ROC,SMA,ATR; trend_favor; swing  
**Entry Long:** close>SMA200 AND ROC(10) crosses above 0.  
**Entry Short:** close<SMA200 AND ROC crosses below 0.  
**Exit:** ROC back through 0 OR time stop 30 bars OR stop 2*ATR.

### 11) Momentum + Pullback to EMA20
**Tags:** trend; long_only; pullback; trailing; EMA,ADX,ATR; trend_favor; swing  
**Entry Long:** close>EMA50 AND ADX>20 AND low touches/breaches EMA20 then closes back above EMA20.  
**Exit:** close<EMA20 OR trail 2*ATR.

### 12) Momentum + Pullback to BB Middle
**Tags:** trend; long_short; pullback; trailing; BBANDS,ADX,ATR; trend_favor; swing  
**Entry Long:** ADX>20 AND close>BB middle AND intrabar pullback touches BB middle then closes above.  
**Entry Short:** ADX>20 AND close<BB middle AND pullback to BB middle then closes below.  
**Exit:** close crosses BB middle opposite OR trail 2*ATR.

### 13) Super Trend-like using ATR Channel (EMA baseline)
**Tags:** trend; long_short; threshold; trailing; EMA,ATR; trend_favor; swing  
**Compute:** baseline=EMA(20); upper=baseline+2*ATR; lower=baseline-2*ATR.  
**Entry Long:** close crosses above upper.  
**Entry Short:** close crosses below lower.  
**Exit:** cross back through baseline OR trailing 2*ATR.

### 14) Linear Regression Slope + Price Filter
**Tags:** trend; long_short; threshold; time+atr_stop; LINEARREG_SLOPE,SMA,ATR; trend_favor; swing  
**Entry Long:** LINEARREG_SLOPE(20) > 0 AND close>SMA50.  
**Entry Short:** slope<0 AND close<SMA50.  
**Exit:** slope sign flips OR time stop 40 OR stop 2*ATR.

### 15) Aroon Trend Start
**Tags:** trend; long_short; threshold; signal+atr_stop; AROON,ATR; trend_favor; swing  
**Entry Long:** AroonUp(25) crosses above 70 AND AroonDown<30.  
**Entry Short:** AroonDown crosses above 70 AND AroonUp<30.  
**Exit:** opposite condition OR stop 2*ATR.

### 16) Ichimoku-lite (using EMAs as proxy)
**Tags:** trend; long_only; threshold; trailing; EMA,ATR; trend_favor; swing  
**Entry Long:** EMA20>EMA50>EMA200 AND close>EMA20.  
**Exit:** EMA20<EMA50 OR close<EMA50 OR trail 2*ATR.

### 17) Trend + Volatility Expansion Confirmation
**Tags:** trend,volatility; long_short; breakout; atr_stop+target; BBANDS,ADX,ATR; vol_expand; swing  
**Entry Long:** ADX>20 AND close breaks above BB upper AND BB width increasing vs 5 bars ago.  
**Entry Short:** ADX>20 AND close breaks below BB lower AND BB width increasing.  
**Exit:** target=3*ATR, stop=2*ATR, or BB middle cross.

### 18) PPO Signal Cross with Long-Term Filter
**Tags:** trend; long_short; cross; signal+atr_stop; PPO,SMA,ATR; trend_favor; swing  
**Entry Long:** close>SMA200 AND PPO crosses above PPO signal.  
**Entry Short:** close<SMA200 AND PPO crosses below signal.  
**Exit:** opposite cross OR stop 2*ATR.

### 19) EMA Ribbon Compression → Break
**Tags:** trend,breakout; long_short; breakout; atr_stop; EMA,ATR; vol_contract→expand; swing  
**Setup:** |EMA20-EMA50| < 0.5*ATR for 10 bars.  
**Entry Long:** close breaks above max(EMA20,EMA50) + 0.5*ATR.  
**Entry Short:** close breaks below min(EMA20,EMA50) - 0.5*ATR.  
**Exit:** opposite break OR trail 2*ATR.

### 20) Trend Day Filter with VWAP Proxy (Typical Price SMA)
**Tags:** trend; long_only; threshold; time; SMA,ADX,ATR; trend_favor; scalp  
**Proxy:** vwap_proxy = SMA((H+L+C)/3, 20).  
**Entry Long:** close>vwap_proxy AND ADX>20 AND RSI>55.  
**Exit:** close<vwap_proxy OR time stop 10 bars OR stop 1.5*ATR.

### 21) DI Pullback Entry
**Tags:** trend; long_only; pullback; signal+trailing; PLUS_DI,MINUS_DI,ADX,ATR; trend_favor; swing  
**Entry Long:** PLUS_DI>MINUS_DI AND ADX>20 AND RSI dips below 45 then crosses back above 50.  
**Exit:** DI crossover OR trail 2*ATR.

### 22) Trend Continuation After RSI Reset
**Tags:** trend; long_only; pullback; signal+atr_stop; RSI,EMA,ATR; trend_favor; swing  
**Entry Long:** close>EMA50 AND RSI(14) falls below 40 then crosses back above 50.  
**Exit:** RSI crosses below 45 OR close<EMA50 OR stop 2*ATR.

### 23) Moving Average Envelope Break
**Tags:** trend,breakout; long_short; breakout; atr_stop+target; SMA,ATR; vol_expand; swing  
**Bands:** SMA20 ± 1.5*ATR.  
**Entry:** close breaks above upper (long) or below lower (short).  
**Exit:** return to SMA20 OR target 3*ATR OR stop 2*ATR.

### 24) HT Trendline Cross (Hilbert)
**Tags:** trend; long_short; cross; signal+atr_stop; HT_TRENDLINE,ATR; trend_favor; swing  
**Entry:** close crosses above HT_TRENDLINE (long) / below (short).  
**Exit:** opposite cross OR stop 2*ATR.

### 25) “Three-Bar Trend” with EMA Filter
**Tags:** trend; long_short; threshold; time+atr_stop; EMA,ATR; trend_favor; scalp  
**Entry Long:** close>EMA50 AND last 3 closes increasing.  
**Entry Short:** close<EMA50 AND last 3 closes decreasing.  
**Exit:** opposite 2 closes OR time stop 8 bars OR stop 1.5*ATR.

---

## B) Mean Reversion / Range (26–50)

### 26) RSI Oversold Bounce (with trend filter)
**Tags:** mean_reversion; long_only; threshold; atr_stop+target; RSI,SMA,ATR; range_favor; swing  
**Entry Long:** close>SMA200 AND RSI crosses up through 30.  
**Exit:** target at RSI>55 OR 2.5*ATR target; stop 2*ATR; time stop 20.

### 27) RSI Overbought Fade (counter-trend)
**Tags:** mean_reversion; short_only; threshold; atr_stop+target; RSI,SMA,ATR; range_favor; swing  
**Entry Short:** close<SMA200 AND RSI crosses down through 70.  
**Exit:** RSI<45 OR target 2.5*ATR; stop 2*ATR.

### 28) Bollinger Band Reversion to Middle
**Tags:** mean_reversion; long_short; threshold; signal+time; BBANDS,ATR; range_favor; swing  
**Entry Long:** close < BB lower AND next close back above BB lower.  
**Entry Short:** close > BB upper AND next close back below BB upper.  
**Exit:** BB middle touch OR time stop 20 OR stop 2*ATR.

### 29) Bollinger “Double Tap” Fade
**Tags:** mean_reversion; long_short; threshold; atr_stop+target; BBANDS,ATR; range_favor; swing  
**Entry Long:** two closes within last 5 bars below BB lower AND RSI<35, then close back above BB lower.  
**Entry Short:** symmetric above BB upper with RSI>65.  
**Exit:** target BB middle or 3*ATR; stop 2*ATR.

### 30) Stoch Oversold/Overbought Cross
**Tags:** mean_reversion; long_short; cross; signal+time; STOCH,ATR; range_favor; scalp  
**Entry Long:** slowK crosses above slowD while both <20.  
**Entry Short:** slowK crosses below slowD while both >80.  
**Exit:** slowK reaches 50 OR time stop 10 OR stop 1.5*ATR.

### 31) Williams %R Snapback
**Tags:** mean_reversion; long_short; threshold; time; WILLR,ATR; range_favor; scalp  
**Entry Long:** WILLR crosses up through −80.  
**Entry Short:** crosses down through −20.  
**Exit:** WILLR reaches −50 OR time stop 8 OR stop 1.5*ATR.

### 32) CCI ±100 Reversion
**Tags:** mean_reversion; long_short; threshold; signal+time; CCI,ATR; range_favor; scalp  
**Entry Long:** CCI crosses up through −100.  
**Entry Short:** CCI crosses down through +100.  
**Exit:** CCI back to 0 OR time stop 12 OR stop 1.5*ATR.

### 33) MFI Extreme Fade (volume-weighted RSI)
**Tags:** mean_reversion,volume_flow; long_short; threshold; time; MFI,ATR; range_favor; swing  
**Entry Long:** MFI crosses up through 20.  
**Entry Short:** MFI crosses down through 80.  
**Exit:** MFI reaches 50 OR time stop 20 OR stop 2*ATR.

### 34) RSI(2) Quick Mean Reversion
**Tags:** mean_reversion; long_short; threshold; time; RSI,ATR; range_favor; scalp; risk:tight  
**Entry Long:** RSI(2) < 5 AND close above SMA50.  
**Entry Short:** RSI(2) > 95 AND close below SMA50.  
**Exit:** RSI(2) > 60 (long) / < 40 (short) OR time stop 5 OR stop 1*ATR.

### 35) Price vs EMA Deviation Reversion
**Tags:** mean_reversion; long_short; threshold; atr_stop+target; EMA,ATR; range_favor; swing  
**Entry Long:** (EMA20 - close) > 2*ATR.  
**Entry Short:** (close - EMA20) > 2*ATR.  
**Exit:** close returns to EMA20 OR target 2*ATR; stop 2*ATR.

### 36) Z-Score of Close vs SMA20 (approx)
**Tags:** mean_reversion; long_short; threshold; time; SMA,STDDEV,ATR; range_favor; swing  
**Compute:** z=(close-SMA20)/STDDEV(20).  
**Entry Long:** z < −2 AND RSI rising 2 bars.  
**Entry Short:** z > +2 AND RSI falling 2 bars.  
**Exit:** z returns to 0 OR time stop 20 OR stop 2*ATR.

### 37) BB Squeeze → Fade First Expansion (contrarian)
**Tags:** mean_reversion,volatility; long_short; threshold; atr_stop; BBANDS,ATR; vol_contract; scalp  
**Setup:** BB width lowest of last 50 bars.  
**Entry:** first close outside BB upper → short; outside BB lower → long (fade).  
**Exit:** BB middle OR time 10 OR stop 2*ATR.

### 38) Donchian Middle Reversion (range)
**Tags:** mean_reversion; long_short; pullback; time; MAX,MIN,ATR; range_favor; swing  
**Compute:** don_mid=(MAX(high,20)+MIN(low,20))/2.  
**Entry Long:** close < MIN(low,20) then close back above MIN(low,20).  
**Entry Short:** close > MAX(high,20) then close back below MAX(high,20).  
**Exit:** don_mid OR time 20 OR stop 2*ATR.

### 39) RSI Divergence (simple)
**Tags:** mean_reversion; long_short; divergence; signal+time; RSI; range_favor; swing  
**Entry Long:** price makes lower low vs 5 bars ago AND RSI makes higher low (RSI now > RSI 5 bars ago) AND RSI<40.  
**Entry Short:** price higher high AND RSI lower high AND RSI>60.  
**Exit:** RSI crosses 50 OR time 25 OR stop 2*ATR.

### 40) MACD Divergence (hist)
**Tags:** mean_reversion; long_short; divergence; signal+time; MACD; range_favor; swing  
**Entry Long:** price lower low but MACD hist higher low AND hist crosses above 0.  
**Entry Short:** price higher high but hist lower high AND crosses below 0.  
**Exit:** opposite hist cross OR time 30 OR stop 2.5*ATR.

### 41) Stoch “Hook” at Extremes
**Tags:** mean_reversion; long_short; pattern; time; STOCH; range_favor; scalp  
**Entry Long:** slowK < 20 AND slowK turns up 2 bars in a row.  
**Entry Short:** slowK > 80 AND turns down 2 bars.  
**Exit:** slowK reaches 50 OR time 10 OR stop 1.5*ATR.

### 42) Mean Reversion to VWAP Proxy
**Tags:** mean_reversion; long_short; threshold; time; SMA,ATR; range_favor; scalp  
**Proxy:** vwap_proxy = SMA((H+L+C)/3, 20).  
**Entry Long:** close < vwap_proxy − 1.5*ATR AND RSI<40.  
**Entry Short:** close > vwap_proxy + 1.5*ATR AND RSI>60.  
**Exit:** vwap_proxy touch OR time 12 OR stop 2*ATR.

### 43) Range Fade with ADX Low
**Tags:** mean_reversion,regime; long_short; threshold; time; ADX,RSI,ATR; range_favor; swing  
**Entry Long:** ADX<15 AND RSI crosses up through 30.  
**Entry Short:** ADX<15 AND RSI crosses down through 70.  
**Exit:** RSI to 50 OR time 20 OR stop 2*ATR.

### 44) BB PercentB Reversion
**Tags:** mean_reversion; long_short; threshold; time; BBANDS; range_favor; swing  
**Compute:** %B=(close-lower)/(upper-lower).  
**Entry Long:** %B < 0.05 then crosses above 0.1.  
**Entry Short:** %B > 0.95 then crosses below 0.9.  
**Exit:** %B returns to 0.5 OR time 20 OR stop 2*ATR.

### 45) CCI + ATR Exhaustion Fade
**Tags:** mean_reversion,volatility; long_short; threshold; atr_stop+target; CCI,ATR; range_favor; swing  
**Entry Long:** CCI < −200 AND (high-low) > 2*ATR, then next close higher.  
**Entry Short:** CCI > +200 AND range>2*ATR, then next close lower.  
**Exit:** CCI back above −100 / below +100 OR target 3*ATR; stop 2.5*ATR.

### 46) RSI Midline Range Strategy
**Tags:** mean_reversion; long_short; cross; signal+time; RSI,ADX; range_favor; swing  
**Entry Long:** ADX<20 AND RSI crosses above 50 from below.  
**Entry Short:** ADX<20 AND RSI crosses below 50 from above.  
**Exit:** RSI crosses back OR time 25 OR stop 2*ATR.

### 47) Price Touches Lower BB + Bullish Candle (pattern confirm)
**Tags:** mean_reversion,pattern; long_only; pattern; time; BBANDS,CDL*; range_favor; swing  
**Entry Long:** low < BB lower AND any bullish candle pattern (e.g., CDLENGULFING>0 or CDLHARAMI>0).  
**Exit:** BB middle OR time 20 OR stop 2*ATR.

### 48) Upper BB + Bearish Candle (pattern confirm)
**Tags:** mean_reversion,pattern; short_only; pattern; time; BBANDS,CDL*; range_favor; swing  
**Entry Short:** high > BB upper AND bearish pattern (e.g., CDLENGULFING<0 or CDLSHOOTINGSTAR<0).  
**Exit:** BB middle OR time 20 OR stop 2*ATR.

### 49) Slow MA Mean Reversion (to SMA50)
**Tags:** mean_reversion; long_short; threshold; time; SMA,ATR; range_favor; swing  
**Entry Long:** close < SMA50 − 2*ATR AND RSI<40.  
**Entry Short:** close > SMA50 + 2*ATR AND RSI>60.  
**Exit:** SMA50 touch OR time 30 OR stop 2.5*ATR.

### 50) “Pinch” Reversion (ATR contraction then snap)
**Tags:** mean_reversion,volatility; long_short; threshold; time; ATR,RSI; vol_contract; swing  
**Setup:** ATR(14) below its SMA(50) by 20% AND ADX<20.  
**Entry Long:** RSI crosses above 50 after being <40.  
**Entry Short:** RSI crosses below 50 after being >60.  
**Exit:** time 25 OR stop 2*ATR OR RSI crosses back.

---

## C) Breakout / Volatility Expansion (51–70)

### 51) Donchian 20 High/Low Breakout
**Tags:** breakout; long_short; breakout; atr_stop+target; MAX,MIN,ATR; vol_expand; swing  
**Entry Long:** close > MAX(high,20).  
**Entry Short:** close < MIN(low,20).  
**Exit:** trailing stop 2*ATR OR opposite breakout; optional target 4*ATR.

### 52) Donchian + ATR Filter
**Tags:** breakout,volatility; long_short; breakout; atr_stop; MAX,MIN,ATR; vol_expand; swing  
**Entry:** as #51 AND (high-low) > 1.2*ATR today.  
**Exit:** trail 2*ATR.

### 53) BB Upper/Lower Breakout
**Tags:** breakout; long_short; breakout; atr_stop+target; BBANDS,ATR; vol_expand; swing  
**Entry Long:** close > BB upper AND BB width rising.  
**Entry Short:** close < BB lower AND BB width rising.  
**Exit:** stop 2*ATR; target 3*ATR; or BB middle cross.

### 54) BB Squeeze Breakout (classic)
**Tags:** breakout,volatility; long_short; breakout; atr_stop; BBANDS,ATR; vol_contract→expand; swing  
**Setup:** BB width lowest of last 60 bars.  
**Entry:** first close outside upper (long) / below lower (short).  
**Exit:** trail 2*ATR or opposite close back inside bands for 2 bars.

### 55) ATR Channel Breakout
**Tags:** breakout; long_short; breakout; atr_stop+target; ATR,SMA; vol_expand; swing  
**Bands:** SMA20 ± 2*ATR.  
**Entry:** close breaks beyond band in either direction.  
**Exit:** return to SMA20 OR target 4*ATR OR stop 2.5*ATR.

### 56) Range Expansion Day Breakout (RED)
**Tags:** breakout,volatility; long_short; breakout; time+atr_stop; ATR; vol_expand; scalp  
**Entry Long:** today’s range > 1.8*ATR AND close in top 20% of range.  
**Entry Short:** range > 1.8*ATR AND close in bottom 20%.  
**Exit:** time stop 5–10 bars OR trail 1.5*ATR.

### 57) Opening Range Breakout Proxy (first N bars)
**Tags:** breakout; long_short; breakout; time; MAX,MIN,ATR; vol_expand; scalp  
**Compute:** OR_high = MAX(high, N); OR_low = MIN(low, N) for first N bars of session.  
**Entry:** break above OR_high (long) / below OR_low (short).  
**Exit:** time stop 10–20 bars or trail 1.5*ATR.

### 58) Volatility “Step-Up” + Break
**Tags:** volatility,breakout; long_short; breakout; atr_stop; ATR,BBANDS; vol_expand; swing  
**Setup:** ATR(14) rising 5 bars AND BB width rising.  
**Entry:** close breaks 10-bar high (long) / 10-bar low (short).  
**Exit:** trail 2*ATR.

### 59) Keltner-style Breakout (ATR around EMA)
**Tags:** breakout; long_short; breakout; atr_stop+target; EMA,ATR; vol_expand; swing  
**Bands:** EMA20 ± 1.5*ATR.  
**Entry:** close breaks band.  
**Exit:** return to EMA20 OR target 3*ATR OR stop 2*ATR.

### 60) ADX Breakout (trend ignition)
**Tags:** breakout,regime; long_short; threshold; atr_stop; ADX,MAX,MIN,ATR; trend_favor; swing  
**Setup:** ADX<15 for 10 bars then ADX crosses above 20.  
**Entry Long:** break 20-bar high.  
**Entry Short:** break 20-bar low.  
**Exit:** trail 2*ATR.

### 61) RSI Breakout (momentum ignition)
**Tags:** breakout; long_short; threshold; time+atr_stop; RSI,MAX,MIN,ATR; vol_expand; swing  
**Entry Long:** RSI crosses above 60 AND close breaks 10-bar high.  
**Entry Short:** RSI crosses below 40 AND close breaks 10-bar low.  
**Exit:** RSI returns to 50 OR time 25 OR stop 2*ATR.

### 62) MACD Breakout Confirmation
**Tags:** breakout; long_short; breakout; atr_stop; MACD,MAX,MIN,ATR; vol_expand; swing  
**Entry Long:** close breaks 20-bar high AND MACD>0.  
**Entry Short:** close breaks 20-bar low AND MACD<0.  
**Exit:** MACD crosses 0 opposite OR trail 2*ATR.

### 63) Bollinger “Walk the Band” (trend breakout)
**Tags:** breakout,trend; long_short; threshold; trailing; BBANDS,ATR; trend_favor; swing  
**Entry Long:** 3 consecutive closes above BB upper.  
**Entry Short:** 3 consecutive closes below BB lower.  
**Exit:** first close back inside bands OR trail 2*ATR.

### 64) Pivot Breakout (classic floor pivots proxy)
**Tags:** breakout; long_short; breakout; time; SMA,ATR; vol_expand; scalp  
**Proxy pivot:** pivot = SMA((H+L+C)/3, 1 previous day) (implement in your pipeline).  
**Entry:** close breaks pivot + 1*ATR (long) / pivot − 1*ATR (short).  
**Exit:** time 10–20 OR stop 1.5*ATR.

### 65) Volatility Contraction Pattern (VCP) proxy
**Tags:** breakout,volatility; long_only; breakout; atr_stop; ATR,MAX; vol_contract→expand; swing  
**Setup:** ATR decreasing 10 bars AND higher lows.  
**Entry Long:** break above 20-bar high.  
**Exit:** trail 2*ATR.

### 66) Gap + Go (simple)
**Tags:** breakout; long_short; breakout; time; ATR; vol_expand; scalp  
**Entry Long:** open gaps up > 1*ATR above prior close AND close>open.  
**Entry Short:** gap down >1*ATR AND close<open.  
**Exit:** time 5–15 OR trail 1.5*ATR.

### 67) Inside Bar Breakout (NR7-ish proxy)
**Tags:** breakout,pattern; long_short; pattern+breakout; time; ATR; vol_contract→expand; scalp  
**Setup:** bar range is smallest of last 7 bars.  
**Entry:** break above that bar high (long) / below low (short).  
**Exit:** time 10 OR stop 1.5*ATR OR target 2.5*ATR.

### 68) “1-2-3” Breakout
**Tags:** breakout; long_only; breakout; atr_stop; MAX,MIN,ATR; vol_expand; swing  
**Entry Long:** (1) swing low formed, (2) pullback high, (3) break above pullback high (use 10-bar fractals proxy).  
**Exit:** stop under swing low (or 2*ATR), target 3*ATR.

### 69) ATR Trailing Breakout
**Tags:** breakout; long_short; breakout; trailing; ATR; vol_expand; swing  
**Entry Long:** close > prior close + 1*ATR.  
**Entry Short:** close < prior close − 1*ATR.  
**Exit:** trail 2*ATR or time 20.

### 70) Chande Momentum Oscillator (CMO) breakout
**Tags:** breakout; long_short; threshold; time; CMO,MAX,MIN,ATR; vol_expand; swing  
**Entry Long:** CMO(14) > +40 AND close breaks 10-bar high.  
**Entry Short:** CMO < −40 AND close breaks 10-bar low.  
**Exit:** CMO back within ±10 OR stop 2*ATR.

---

## D) Volume / Flow Confirmed (71–80)

### 71) OBV Breakout Confirmation
**Tags:** volume_flow,breakout; long_short; breakout; atr_stop; OBV,MAX,MIN,ATR; vol_expand; swing  
**Entry Long:** close breaks 20-bar high AND OBV breaks 20-bar high.  
**Entry Short:** close breaks 20-bar low AND OBV breaks 20-bar low.  
**Exit:** trail 2*ATR.

### 72) OBV Trend + Pullback
**Tags:** volume_flow,trend; long_only; pullback; trailing; OBV,EMA,ATR; trend_favor; swing  
**Entry Long:** OBV above its SMA20 AND close>EMA50 AND pullback touches EMA20 then closes above.  
**Exit:** close<EMA20 OR trail 2*ATR.

### 73) ADOSC Momentum
**Tags:** volume_flow; long_short; threshold; time; ADOSC,ATR; trend_favor; swing  
**Entry Long:** ADOSC crosses above 0 AND close>EMA50.  
**Entry Short:** crosses below 0 AND close<EMA50.  
**Exit:** ADOSC crosses back OR stop 2*ATR.

### 74) MFI + BB Breakout
**Tags:** volume_flow,breakout; long_short; breakout; atr_stop+target; MFI,BBANDS,ATR; vol_expand; swing  
**Entry Long:** close>BB upper AND MFI>60.  
**Entry Short:** close<BB lower AND MFI<40.  
**Exit:** target 3*ATR; stop 2*ATR; or BB middle cross.

### 75) Volume Spike Trend Continuation
**Tags:** volume_flow,trend; long_only; threshold; time; SMA,ATR; trend_favor; swing  
**Proxy volume spike:** volume > 2 * SMA(volume,20).  
**Entry Long:** close>SMA50 AND volume spike AND close in top 25% of range.  
**Exit:** time 20 OR trail 2*ATR.

### 76) OBV Divergence Reversal
**Tags:** volume_flow,mean_reversion; long_short; divergence; time; OBV,ATR; range_favor; swing  
**Entry Long:** price lower low vs 10 bars ago, OBV higher low; bullish candle.  
**Entry Short:** price higher high, OBV lower high; bearish candle.  
**Exit:** time 25 OR target 3*ATR OR stop 2.5*ATR.

### 77) Chaikin A/D Line Trend (proxy via ADOSC cumulative)
**Tags:** volume_flow,trend; long_short; threshold; trailing; ADOSC,EMA,ATR; trend_favor; swing  
**Entry Long:** ADOSC above 0 for 5 bars AND close>EMA50.  
**Entry Short:** ADOSC below 0 for 5 AND close<EMA50.  
**Exit:** ADOSC flips sign OR trail 2*ATR.

### 78) MFI Reversion with ADX Low
**Tags:** volume_flow,mean_reversion,regime; long_short; threshold; time; MFI,ADX,ATR; range_favor; swing  
**Entry Long:** ADX<15 AND MFI crosses up through 20.  
**Entry Short:** ADX<15 AND MFI crosses down through 80.  
**Exit:** MFI 50 OR time 20 OR stop 2*ATR.

### 79) OBV “Break then Retest”
**Tags:** volume_flow,breakout; long_only; pullback; atr_stop; OBV,MAX,ATR; vol_expand; swing  
**Entry Long:** OBV breaks 20-bar high, then price pulls back within 1*ATR of breakout level and closes back above.  
**Exit:** trail 2*ATR or time 40.

### 80) Price Breakout + Positive Accumulation (ADOSC rising)
**Tags:** volume_flow,breakout; long_only; breakout; atr_stop; ADOSC,MAX,ATR; vol_expand; swing  
**Entry Long:** close breaks 20-bar high AND ADOSC rising 3 bars.  
**Exit:** trail 2*ATR.

---

## E) Candlestick / Pattern Confirmed (81–90)
*(TA‑Lib provides many `CDL*` pattern functions returning +/− values. Use any one or a small basket.)*

### 81) Bullish Engulfing + Trend Filter
**Tags:** pattern,trend; long_only; pattern; atr_stop+target; CDLENGULFING,EMA,ATR; trend_favor; swing  
**Entry Long:** CDLENGULFING > 0 AND close>EMA50.  
**Exit:** target 3*ATR OR close<EMA20 OR stop 2*ATR.

### 82) Bearish Engulfing + Trend Filter
**Tags:** pattern,trend; short_only; pattern; atr_stop+target; CDLENGULFING,EMA,ATR; trend_favor; swing  
**Entry Short:** CDLENGULFING < 0 AND close<EMA50.  
**Exit:** target 3*ATR OR close>EMA20 OR stop 2*ATR.

### 83) Hammer at Lower BB
**Tags:** pattern,mean_reversion; long_only; pattern; time; CDLHAMMER,BBANDS,ATR; range_favor; swing  
**Entry Long:** CDLHAMMER > 0 AND low < BB lower.  
**Exit:** BB middle OR time 20 OR stop 2*ATR.

### 84) Shooting Star at Upper BB
**Tags:** pattern,mean_reversion; short_only; pattern; time; CDLSHOOTINGSTAR,BBANDS,ATR; range_favor; swing  
**Entry Short:** CDLSHOOTINGSTAR < 0 AND high > BB upper.  
**Exit:** BB middle OR time 20 OR stop 2*ATR.

### 85) Morning Star (reversal)
**Tags:** pattern,mean_reversion; long_only; pattern; atr_stop; CDLMORNINGSTAR,ATR; range_favor; swing  
**Entry Long:** CDLMORNINGSTAR > 0.  
**Exit:** time 30 OR target 3*ATR OR stop 2.5*ATR.

### 86) Evening Star (reversal)
**Tags:** pattern,mean_reversion; short_only; pattern; atr_stop; CDLEVENINGSTAR,ATR; range_favor; swing  
**Entry Short:** CDLEVENINGSTAR < 0.  
**Exit:** time 30 OR target 3*ATR OR stop 2.5*ATR.

### 87) Doji + Trend Exhaustion (ATR spike)
**Tags:** pattern,mean_reversion,volatility; long_short; pattern; time; CDLDOJI,ATR,RSI; range_favor; swing  
**Entry Long:** CDLDOJI != 0 AND range > 1.8*ATR AND RSI<45 then next close higher.  
**Entry Short:** CDLDOJI !=0 AND range>1.8*ATR AND RSI>55 then next close lower.  
**Exit:** time 20 OR target 2.5*ATR OR stop 2*ATR.

### 88) Three White Soldiers / Three Black Crows (continuation)
**Tags:** pattern,trend; long_short; pattern; trailing; CDL3WHITESOLDIERS,CDL3BLACKCROWS,ATR; trend_favor; swing  
**Entry Long:** CDL3WHITESOLDIERS > 0.  
**Entry Short:** CDL3BLACKCROWS < 0.  
**Exit:** trail 2*ATR or opposite pattern.

### 89) Harami + RSI Confirm
**Tags:** pattern,mean_reversion; long_short; pattern; time; CDLHARAMI,RSI,ATR; range_favor; swing  
**Entry Long:** CDLHARAMI > 0 AND RSI<45 then RSI rising 2 bars.  
**Entry Short:** CDLHARAMI < 0 AND RSI>55 then RSI falling 2 bars.  
**Exit:** RSI 50 or time 25 or stop 2*ATR.

### 90) Marubozu Breakout Continuation
**Tags:** pattern,breakout; long_short; pattern+breakout; time; CDLMARUBOZU,ATR; vol_expand; swing  
**Entry Long:** bullish marubozu (CDLMARUBOZU > 0) AND close breaks 10-bar high.  
**Entry Short:** bearish marubozu (<0) AND close breaks 10-bar low.  
**Exit:** time 20 OR trail 2*ATR.

---

## F) Regime-Switch / Multi-Filter Hybrids (91–100)

### 91) Regime: ADX Trend vs Range Switch (meta-strategy)
**Tags:** regime,multi_filter; long_short; threshold; mixed; ADX,EMA,RSI,BBANDS,ATR; holding:swing  
**Regime A (Trend):** if ADX>25 → use Strategy #1 (EMA cross) signals.  
**Regime B (Range):** if ADX<18 → use Strategy #28 (BB reversion) signals.  
**Exit:** follow selected sub-strategy exit.

### 92) Volatility Regime Switch (ATR vs ATR-SMA)
**Tags:** regime,volatility; long_short; threshold; mixed; ATR,BBANDS,MAX,MIN; holding:swing  
**Regime Expand:** ATR(14) > SMA(ATR,50) → run breakouts (#51/#54).  
**Regime Contract:** ATR(14) < 0.85*SMA(ATR,50) → run mean reversion (#42/#36).  

### 93) Trend Quality Filter (ADX + BB width)
**Tags:** regime,trend; long_only; pullback; trailing; ADX,BBANDS,EMA,ATR; trend_favor; swing  
**Entry Long:** ADX>20 AND BB width rising AND pullback to EMA20 then bullish close.  
**Exit:** close<EMA20 OR trail 2*ATR.

### 94) “No-Trade” Filter Strategy
**Tags:** regime; long_short; threshold; time; ATR,ADX; risk:tight; holding:scalp  
**Rule:** trade only when (ADX between 18 and 35) AND (ATR not in bottom 20% of last 200 bars).  
**Then:** run simple momentum (#10) with time stop 15.

### 95) Dual-Timeframe Filter (implement by resampling)
**Tags:** multi_filter,trend; long_only; pullback; trailing; EMA,RSI,ATR; trend_favor; swing  
**HTF filter:** higher timeframe close > HTF EMA50.  
**LTF entry:** RSI crosses above 50 after dip <40 AND close>EMA20.  
**Exit:** LTF close<EMA20 OR trail 2*ATR.

### 96) Mean Reversion Only When Trend Flat (SMA200 slope ~ 0)
**Tags:** multi_filter,mean_reversion,regime; long_short; threshold; time; SMA,LINEARREG_SLOPE,RSI,ATR; range_favor; swing  
**Filter:** abs(LINEARREG_SLOPE(SMA200,50)) < small epsilon (define per instrument).  
**Entry:** RSI(14) crosses up 30 (long) or down 70 (short).  
**Exit:** RSI 50 OR time 25 OR stop 2*ATR.

### 97) Breakout Only When Volume/Flow Confirms
**Tags:** multi_filter,breakout,volume_flow; long_short; breakout; atr_stop; MAX,MIN,OBV,ADOSC,ATR; vol_expand; swing  
**Entry Long:** close breaks 20-bar high AND OBV breaks 20-bar high AND ADOSC>0.  
**Entry Short:** symmetric for lows and ADOSC<0.  
**Exit:** trail 2*ATR.

### 98) Trend + Mean Reversion “Add-on” (pyramiding logic)
**Tags:** trend,mean_reversion,multi_filter; long_only; pullback; trailing; EMA,RSI,ATR; trend_favor; holding:position  
**Base Entry:** EMA20 crosses above EMA50 (like #1 long).  
**Add-on:** while in position, add 1 unit when RSI crosses above 50 after dipping below 40 and price holds above EMA50.  
**Exit:** close<EMA50 OR trail 2*ATR.  

### 99) Volatility Breakout with “Failure Exit”
**Tags:** breakout,volatility; long_short; breakout; signal+atr_stop; BBANDS,ATR; vol_expand; swing  
**Entry:** BB squeeze breakout (#54).  
**Failure Exit:** if within 3 bars price closes back inside bands AND RSI crosses back through 50 against direction → exit immediately.  
**Otherwise Exit:** trail 2*ATR.

### 100) Ensemble Vote (3-strategy majority)
**Tags:** regime,ensemble,multi_filter; long_short; mixed; EMA,RSI,MACD,ATR; holding:swing  
**Signals:**  
- S1: EMA20>EMA50 (bull) / < (bear)  
- S2: RSI>55 (bull) / <45 (bear)  
- S3: MACD hist >0 (bull) / <0 (bear)  
**Entry:** go long if ≥2 bull and none strongly bear (RSI<40 + MACD<0). Short if ≥2 bear similarly.  
**Exit:** when vote flips (≥2 opposite) OR stop 2*ATR OR target 3*ATR.

---

## Implementation notes (practical)
1. **Normalize signals:** record for each strategy on each bar: `{signal ∈ {-1,0,+1}, strength ∈ [0,1], entry_price, stop, target}`.  
2. **Backtest hygiene:** always account for slippage/fees and avoid lookahead (compute indicators on close, trade next open).  
3. **Tagging:** store tags as arrays so you can aggregate by theme/regime and compute “theme heatmaps” over time.  
4. **Diversity check:** ensure your 100 strategies span multiple themes and are not all variants of RSI.  

If you want, I can also generate:
- a **JSON/YAML registry** for all 100 strategies (name, params, tags, logic block),
- and a **Python skeleton** that evaluates each strategy’s signal from TA‑Lib arrays.
