#pragma once

#include "indicators/base.h"
#include <vector>

namespace ie {

/// Compute intrabar features: clv, body_ratio, upper_wick, lower_wick.
///
/// Mirrors src/features/intrabar.py:IntrabarFeatureCalculator
struct IntrabarCalculator {
    void compute(const std::vector<OHLCVBar>& bars,
                 std::vector<IndicatorResult>& results) const;
};

} // namespace ie
