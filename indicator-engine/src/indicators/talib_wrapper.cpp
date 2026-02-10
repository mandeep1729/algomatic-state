#include "indicators/talib_wrapper.h"
#include <algorithm>
#include <cmath>
#include <spdlog/spdlog.h>

#ifdef HAS_TALIB
#include <ta-lib/ta_libc.h>
#endif

namespace ie {

namespace {

// Helper to extract OHLCV arrays from bars
struct PriceArrays {
    std::vector<double> open, high, low, close;
    std::vector<double> volume;
    int n;

    explicit PriceArrays(const std::vector<OHLCVBar>& bars) : n(static_cast<int>(bars.size())) {
        open.resize(n);
        high.resize(n);
        low.resize(n);
        close.resize(n);
        volume.resize(n);
        for (int i = 0; i < n; i++) {
            open[i] = bars[i].open;
            high[i] = bars[i].high;
            low[i] = bars[i].low;
            close[i] = bars[i].close;
            volume[i] = static_cast<double>(bars[i].volume);
        }
    }
};

#ifdef HAS_TALIB

// Write TA-Lib output into results, offset by outBegIdx
void write_output(std::vector<IndicatorResult>& results,
                  const std::string& name,
                  const double* out,
                  int outBegIdx,
                  int outNbElement,
                  int total)
{
    for (int i = 0; i < outBegIdx; i++)
        results[i].features[name] = NaN;
    for (int i = 0; i < outNbElement; i++)
        results[outBegIdx + i].features[name] = out[i];
    for (int i = outBegIdx + outNbElement; i < total; i++)
        results[i].features[name] = NaN;
}

#endif // HAS_TALIB

} // anonymous namespace


void TALibCalculator::compute(
    const std::vector<OHLCVBar>& bars,
    std::vector<IndicatorResult>& results) const
{
#ifdef HAS_TALIB
    TA_Initialize();
    compute_momentum(bars, results);
    compute_trend(bars, results);
    compute_volatility(bars, results);
    compute_volume(bars, results);
    compute_derived(bars, results);
    TA_Shutdown();
    spdlog::debug("TALibCalculator: computed {} bars", bars.size());
#else
    spdlog::warn("TALibCalculator: TA-Lib not available, skipping");
    // Fill all TA-Lib indicator names with NaN
    for (auto& r : results) {
        for (const auto& name : {"rsi_14", "macd", "macd_signal", "macd_hist",
                                  "stoch_k", "stoch_d", "adx_14", "cci_20",
                                  "willr_14", "mfi_14", "sma_20", "sma_50",
                                  "sma_200", "ema_20", "ema_50", "ema_200",
                                  "bb_upper", "bb_middle", "bb_lower", "bb_width",
                                  "bb_pct", "atr_14", "obv", "psar"}) {
            r.features[name] = NaN;
        }
    }
#endif
}


void TALibCalculator::compute_momentum(
    const std::vector<OHLCVBar>& bars,
    std::vector<IndicatorResult>& results) const
{
#ifdef HAS_TALIB
    PriceArrays p(bars);
    int n = p.n;
    std::vector<double> out1(n), out2(n), out3(n);
    int outBeg, outNb;

    // RSI-14
    if (TA_RSI(0, n - 1, p.close.data(), 14, &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "rsi_14", out1.data(), outBeg, outNb, n);

    // RSI-2
    if (TA_RSI(0, n - 1, p.close.data(), 2, &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "rsi_2", out1.data(), outBeg, outNb, n);

    // MACD (12, 26, 9)
    if (TA_MACD(0, n - 1, p.close.data(), 12, 26, 9,
                &outBeg, &outNb, out1.data(), out2.data(), out3.data()) == TA_SUCCESS) {
        write_output(results, "macd", out1.data(), outBeg, outNb, n);
        write_output(results, "macd_signal", out2.data(), outBeg, outNb, n);
        write_output(results, "macd_hist", out3.data(), outBeg, outNb, n);
    }

    // Stochastic (14, 3, 3)
    if (TA_STOCH(0, n - 1, p.high.data(), p.low.data(), p.close.data(),
                 14, 3, TA_MAType_SMA, 3, TA_MAType_SMA,
                 &outBeg, &outNb, out1.data(), out2.data()) == TA_SUCCESS) {
        write_output(results, "stoch_k", out1.data(), outBeg, outNb, n);
        write_output(results, "stoch_d", out2.data(), outBeg, outNb, n);
    }

    // ADX-14
    if (TA_ADX(0, n - 1, p.high.data(), p.low.data(), p.close.data(), 14,
               &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "adx_14", out1.data(), outBeg, outNb, n);

    // CCI-20
    if (TA_CCI(0, n - 1, p.high.data(), p.low.data(), p.close.data(), 20,
               &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "cci_20", out1.data(), outBeg, outNb, n);

    // Williams %R
    if (TA_WILLR(0, n - 1, p.high.data(), p.low.data(), p.close.data(), 14,
                 &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "willr_14", out1.data(), outBeg, outNb, n);

    // MFI-14
    if (TA_MFI(0, n - 1, p.high.data(), p.low.data(), p.close.data(),
               p.volume.data(), 14, &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "mfi_14", out1.data(), outBeg, outNb, n);

    // CMO-14
    if (TA_CMO(0, n - 1, p.close.data(), 14, &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "cmo_14", out1.data(), outBeg, outNb, n);

    // ROC-10
    if (TA_ROC(0, n - 1, p.close.data(), 10, &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "roc_10", out1.data(), outBeg, outNb, n);

    // MOM-10
    if (TA_MOM(0, n - 1, p.close.data(), 10, &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "mom_10", out1.data(), outBeg, outNb, n);

    // APO
    if (TA_APO(0, n - 1, p.close.data(), 12, 26, TA_MAType_EMA,
               &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "apo", out1.data(), outBeg, outNb, n);

    // PPO
    if (TA_PPO(0, n - 1, p.close.data(), 12, 26, TA_MAType_EMA,
               &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "ppo", out1.data(), outBeg, outNb, n);

    // TRIX-15
    if (TA_TRIX(0, n - 1, p.close.data(), 15, &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "trix_15", out1.data(), outBeg, outNb, n);

    // Plus DI / Minus DI
    if (TA_PLUS_DI(0, n - 1, p.high.data(), p.low.data(), p.close.data(), 14,
                   &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "plus_di_14", out1.data(), outBeg, outNb, n);

    if (TA_MINUS_DI(0, n - 1, p.high.data(), p.low.data(), p.close.data(), 14,
                    &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "minus_di_14", out1.data(), outBeg, outNb, n);

    // Aroon
    if (TA_AROON(0, n - 1, p.high.data(), p.low.data(), 25,
                 &outBeg, &outNb, out1.data(), out2.data()) == TA_SUCCESS) {
        write_output(results, "aroon_down_25", out1.data(), outBeg, outNb, n);
        write_output(results, "aroon_up_25", out2.data(), outBeg, outNb, n);
    }
#endif
}


void TALibCalculator::compute_trend(
    const std::vector<OHLCVBar>& bars,
    std::vector<IndicatorResult>& results) const
{
#ifdef HAS_TALIB
    PriceArrays p(bars);
    int n = p.n;
    std::vector<double> out1(n);
    int outBeg, outNb;

    // SMA 20/50/200
    for (auto [period, name] : {std::pair{20, "sma_20"}, {50, "sma_50"}, {200, "sma_200"}}) {
        if (TA_SMA(0, n - 1, p.close.data(), period, &outBeg, &outNb, out1.data()) == TA_SUCCESS)
            write_output(results, name, out1.data(), outBeg, outNb, n);
    }

    // EMA 20/50/200
    for (auto [period, name] : {std::pair{20, "ema_20"}, {50, "ema_50"}, {200, "ema_200"}}) {
        if (TA_EMA(0, n - 1, p.close.data(), period, &outBeg, &outNb, out1.data()) == TA_SUCCESS)
            write_output(results, name, out1.data(), outBeg, outNb, n);
    }

    // Parabolic SAR
    if (TA_SAR(0, n - 1, p.high.data(), p.low.data(), 0.02, 0.2,
               &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "psar", out1.data(), outBeg, outNb, n);

    // KAMA-30
    if (TA_KAMA(0, n - 1, p.close.data(), 30, &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "kama_30", out1.data(), outBeg, outNb, n);

    // Hilbert Transform Trendline
    if (TA_HT_TRENDLINE(0, n - 1, p.close.data(), &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "ht_trendline", out1.data(), outBeg, outNb, n);

    // Linear regression slope (20)
    if (TA_LINEARREG_SLOPE(0, n - 1, p.close.data(), 20, &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "linearreg_slope_20", out1.data(), outBeg, outNb, n);

    // Ichimoku (manual — TA-Lib doesn't have native Ichimoku)
    for (int i = 0; i < n; i++) {
        auto& r = results[i].features;

        // Tenkan-sen (9-period)
        if (i >= 8) {
            double hh = -1e18, ll = 1e18;
            for (int j = i - 8; j <= i; j++) { hh = std::max(hh, p.high[j]); ll = std::min(ll, p.low[j]); }
            r["ichi_tenkan"] = (hh + ll) / 2.0;
        } else {
            r["ichi_tenkan"] = NaN;
        }

        // Kijun-sen (26-period)
        if (i >= 25) {
            double hh = -1e18, ll = 1e18;
            for (int j = i - 25; j <= i; j++) { hh = std::max(hh, p.high[j]); ll = std::min(ll, p.low[j]); }
            r["ichi_kijun"] = (hh + ll) / 2.0;
        } else {
            r["ichi_kijun"] = NaN;
        }

        // Senkou Span A
        if (is_valid(r["ichi_tenkan"]) && is_valid(r["ichi_kijun"]))
            r["ichi_senkou_a"] = (r["ichi_tenkan"] + r["ichi_kijun"]) / 2.0;
        else
            r["ichi_senkou_a"] = NaN;

        // Senkou Span B (52-period)
        if (i >= 51) {
            double hh = -1e18, ll = 1e18;
            for (int j = i - 51; j <= i; j++) { hh = std::max(hh, p.high[j]); ll = std::min(ll, p.low[j]); }
            r["ichi_senkou_b"] = (hh + ll) / 2.0;
        } else {
            r["ichi_senkou_b"] = NaN;
        }

        r["ichi_chikou"] = p.close[i];
    }
#endif
}


void TALibCalculator::compute_volatility(
    const std::vector<OHLCVBar>& bars,
    std::vector<IndicatorResult>& results) const
{
#ifdef HAS_TALIB
    PriceArrays p(bars);
    int n = p.n;
    std::vector<double> out1(n), out2(n), out3(n);
    int outBeg, outNb;

    // Bollinger Bands (20, 2)
    if (TA_BBANDS(0, n - 1, p.close.data(), 20, 2.0, 2.0, TA_MAType_SMA,
                  &outBeg, &outNb, out1.data(), out2.data(), out3.data()) == TA_SUCCESS) {
        write_output(results, "bb_upper", out1.data(), outBeg, outNb, n);
        write_output(results, "bb_middle", out2.data(), outBeg, outNb, n);
        write_output(results, "bb_lower", out3.data(), outBeg, outNb, n);

        // Derived: bb_width, bb_pct
        for (int i = outBeg; i < outBeg + outNb; i++) {
            double upper = results[i].features["bb_upper"];
            double middle = results[i].features["bb_middle"];
            double lower = results[i].features["bb_lower"];
            results[i].features["bb_width"] = (middle > EPS) ? (upper - lower) / middle : NaN;
            double brange = upper - lower;
            results[i].features["bb_pct"] = (brange > EPS) ? (p.close[i] - lower) / brange : NaN;
        }
    }

    // ATR-14
    if (TA_ATR(0, n - 1, p.high.data(), p.low.data(), p.close.data(), 14,
               &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "atr_14", out1.data(), outBeg, outNb, n);

    // STDDEV-20
    if (TA_STDDEV(0, n - 1, p.close.data(), 20, 1.0, &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "stddev_20", out1.data(), outBeg, outNb, n);
#endif
}


void TALibCalculator::compute_volume(
    const std::vector<OHLCVBar>& bars,
    std::vector<IndicatorResult>& results) const
{
#ifdef HAS_TALIB
    PriceArrays p(bars);
    int n = p.n;
    std::vector<double> out1(n);
    int outBeg, outNb;

    // OBV
    if (TA_OBV(0, n - 1, p.close.data(), p.volume.data(), &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "obv", out1.data(), outBeg, outNb, n);

    // AD Oscillator (3, 10)
    if (TA_ADOSC(0, n - 1, p.high.data(), p.low.data(), p.close.data(),
                 p.volume.data(), 3, 10, &outBeg, &outNb, out1.data()) == TA_SUCCESS)
        write_output(results, "adosc", out1.data(), outBeg, outNb, n);

    // VWAP (cumulative)
    double cum_tp_vol = 0.0, cum_vol = 0.0;
    for (int i = 0; i < n; i++) {
        double tp = (p.high[i] + p.low[i] + p.close[i]) / 3.0;
        cum_tp_vol += tp * p.volume[i];
        cum_vol += p.volume[i];
        results[i].features["vwap"] = (cum_vol > 0.0) ? cum_tp_vol / cum_vol : NaN;
    }

    // Pivot points
    for (int i = 0; i < n; i++) {
        double pp = (p.high[i] + p.low[i] + p.close[i]) / 3.0;
        results[i].features["pivot_pp"] = pp;
        results[i].features["pivot_r1"] = 2.0 * pp - p.low[i];
        results[i].features["pivot_r2"] = pp + (p.high[i] - p.low[i]);
        results[i].features["pivot_s1"] = 2.0 * pp - p.high[i];
        results[i].features["pivot_s2"] = pp - (p.high[i] - p.low[i]);
    }
#endif
}


void TALibCalculator::compute_derived(
    const std::vector<OHLCVBar>& bars,
    std::vector<IndicatorResult>& results) const
{
#ifdef HAS_TALIB
    int n = static_cast<int>(bars.size());
    PriceArrays p(bars);

    // Donchian Channels
    for (int i = 0; i < n; i++) {
        auto& r = results[i].features;

        // 20-period
        if (i >= 19) {
            double hh = -1e18, ll = 1e18;
            for (int j = i - 19; j <= i; j++) { hh = std::max(hh, p.high[j]); ll = std::min(ll, p.low[j]); }
            r["donchian_high_20"] = hh;
            r["donchian_low_20"] = ll;
            r["donchian_mid_20"] = (hh + ll) / 2.0;
        }

        // 10-period
        if (i >= 9) {
            double hh = -1e18, ll = 1e18;
            for (int j = i - 9; j <= i; j++) { hh = std::max(hh, p.high[j]); ll = std::min(ll, p.low[j]); }
            r["donchian_high_10"] = hh;
            r["donchian_low_10"] = ll;
        }

        // Bar range
        r["bar_range"] = p.high[i] - p.low[i];

        // Typical price SMA-20
        double tp = (p.high[i] + p.low[i] + p.close[i]) / 3.0;
        r["typical_price"] = tp;  // Temporary, used for SMA below
    }

    // Derived SMAs of computed indicators (atr_sma_50, obv_sma_20, etc.)
    // These require rolling windows over previously computed indicator values

    // atr_sma_50: SMA of atr_14 over 50 bars
    {
        RollingSum rs;
        rs.init(50);
        for (int i = 0; i < n; i++) {
            double v = results[i].features.count("atr_14") ? results[i].features["atr_14"] : NaN;
            if (is_valid(v)) rs.push(v);
            results[i].features["atr_sma_50"] = rs.full() ? rs.mean() : NaN;
        }
    }

    // obv_sma_20, obv_high_20, obv_low_20
    {
        RollingSum rs;
        rs.init(20);
        RollingMax rmax;
        rmax.init(20);
        RollingMin rmin;
        rmin.init(20);

        for (int i = 0; i < n; i++) {
            double v = results[i].features.count("obv") ? results[i].features["obv"] : NaN;
            if (is_valid(v)) { rs.push(v); rmax.push(v); rmin.push(v); }
            results[i].features["obv_sma_20"] = rs.full() ? rs.mean() : NaN;
            results[i].features["obv_high_20"] = rmax.full() ? rmax.max_val() : NaN;
            results[i].features["obv_low_20"] = rmin.full() ? rmin.min_val() : NaN;
        }
    }

    // typical_price_sma_20
    {
        RollingSum rs;
        rs.init(20);
        for (int i = 0; i < n; i++) {
            double tp = (p.high[i] + p.low[i] + p.close[i]) / 3.0;
            rs.push(tp);
            results[i].features["typical_price_sma_20"] = rs.full() ? rs.mean() : NaN;
        }
        // Remove temporary typical_price
        for (int i = 0; i < n; i++)
            results[i].features.erase("typical_price");
    }

    // volume_sma_20
    {
        RollingSum rs;
        rs.init(20);
        for (int i = 0; i < n; i++) {
            rs.push(p.volume[i]);
            results[i].features["volume_sma_20"] = rs.full() ? rs.mean() : NaN;
        }
    }
#endif
}

} // namespace ie
