#pragma once

#include "indicators/base.h"
#include <vector>

namespace ie {

/// Compute time-of-day features: tod_sin, tod_cos, is_open_window,
/// is_close_window, is_midday.
///
/// Mirrors src/features/time_of_day.py:TimeOfDayFeatureCalculator
struct TimeOfDayCalculator {
    int market_open_hour = 9;
    int market_open_minute = 30;
    int total_trading_minutes = 390;
    int open_window_minutes = 30;
    int close_window_minutes = 60;
    int midday_start = 120;
    int midday_end = 240;

    void compute(const std::vector<OHLCVBar>& bars,
                 std::vector<IndicatorResult>& results) const;
};

} // namespace ie
