#pragma once

#include "indicators/base.h"
#include <vector>

namespace ie {

/// Compute return-based features: r1, r5, r15, r60, cumret_60, ema_diff,
/// slope_60, trend_strength.
///
/// Mirrors src/features/returns.py:ReturnFeatureCalculator
struct ReturnCalculator {
    int short_window = 5;
    int medium_window = 15;
    int long_window = 60;
    int ema_fast = 12;
    int ema_slow = 48;

    /// Compute return features for all bars.
    /// Populates result[i].features with r1, r5, etc.
    /// Also writes "r1" values into `r1_out` for downstream use.
    void compute(const std::vector<OHLCVBar>& bars,
                 std::vector<IndicatorResult>& results,
                 std::vector<double>& r1_out) const;
};

} // namespace ie
