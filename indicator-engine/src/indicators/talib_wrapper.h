#pragma once

#include "indicators/base.h"
#include <vector>

namespace ie {

/// Compute TA-Lib indicators (~50+): RSI, MACD, Stochastic, ADX, CCI,
/// Bollinger Bands, SMA, EMA, Ichimoku, OBV, Parabolic SAR, etc.
///
/// Mirrors src/features/talib_indicators.py:TALibIndicatorCalculator
struct TALibCalculator {
    void compute(const std::vector<OHLCVBar>& bars,
                 std::vector<IndicatorResult>& results) const;

private:
    void compute_momentum(const std::vector<OHLCVBar>& bars,
                          std::vector<IndicatorResult>& results) const;
    void compute_trend(const std::vector<OHLCVBar>& bars,
                       std::vector<IndicatorResult>& results) const;
    void compute_volatility(const std::vector<OHLCVBar>& bars,
                            std::vector<IndicatorResult>& results) const;
    void compute_volume(const std::vector<OHLCVBar>& bars,
                        std::vector<IndicatorResult>& results) const;
    void compute_derived(const std::vector<OHLCVBar>& bars,
                         std::vector<IndicatorResult>& results) const;
};

} // namespace ie
