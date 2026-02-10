#pragma once

#include "indicators/base.h"
#include <vector>

namespace ie {

/// Compute volatility features: rv_15, rv_60, range_1, atr_60, range_z_60,
/// vol_of_vol.
///
/// Mirrors src/features/volatility.py:VolatilityFeatureCalculator
struct VolatilityCalculator {
    int short_window = 15;
    int long_window = 60;

    /// Compute volatility features. Uses r1_values if provided (from returns).
    void compute(const std::vector<OHLCVBar>& bars,
                 std::vector<IndicatorResult>& results,
                 const std::vector<double>& r1_values) const;
};

} // namespace ie
