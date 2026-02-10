#pragma once

#include "indicators/base.h"
#include <vector>

namespace ie {

/// Compute anchor features: vwap_60, dist_vwap_60, dist_ema_48,
/// breakout_20, pullback_depth.
///
/// Mirrors src/features/anchor.py:AnchorFeatureCalculator
struct AnchorCalculator {
    int vwap_window = 60;
    int ema_period = 48;
    int breakout_window = 20;

    void compute(const std::vector<OHLCVBar>& bars,
                 std::vector<IndicatorResult>& results) const;
};

} // namespace ie
