#pragma once

#include "indicators/base.h"
#include <vector>

namespace ie {

/// Orchestrate indicator computation in dependency order.
///
/// Pipeline order (mirrors src/features/pipeline.py):
/// 1. Returns -> produces r1 intermediate
/// 2. Volatility -> consumes r1
/// 3. Volume
/// 4. Intrabar
/// 5. Anchor
/// 6. Time-of-day
/// 7. TA-Lib (all ~50+ indicators)
class Pipeline {
public:
    /// Compute all indicators for the given bars.
    /// Returns one IndicatorResult per bar with all features merged.
    std::vector<IndicatorResult> compute(const std::vector<OHLCVBar>& bars) const;
};

} // namespace ie
