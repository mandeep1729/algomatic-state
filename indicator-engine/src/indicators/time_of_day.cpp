#include "indicators/time_of_day.h"
#include <cmath>
#include <spdlog/spdlog.h>

namespace ie {

void TimeOfDayCalculator::compute(
    const std::vector<OHLCVBar>& bars,
    std::vector<IndicatorResult>& results) const
{
    const int n = static_cast<int>(bars.size());
    constexpr double TWO_PI = 2.0 * M_PI;

    int open_offset = market_open_hour * 60 + market_open_minute;

    for (int i = 0; i < n; i++) {
        auto& r = results[i].features;

        // Convert UTC timestamp to local time (ET approximation via struct tm)
        struct tm t;
        time_t ts = bars[i].timestamp;
        gmtime_r(&ts, &t);

        int minutes_of_day = t.tm_hour * 60 + t.tm_min;
        int minutes_from_open = minutes_of_day - open_offset;

        // Clamp to trading range
        if (minutes_from_open < 0) minutes_from_open = 0;
        if (minutes_from_open > total_trading_minutes)
            minutes_from_open = total_trading_minutes;

        double frac = static_cast<double>(minutes_from_open) / total_trading_minutes;

        // tod_sin, tod_cos: cyclical encoding
        r["tod_sin"] = std::sin(TWO_PI * frac);
        r["tod_cos"] = std::cos(TWO_PI * frac);

        // is_open_window: first 30 minutes
        r["is_open_window"] = (minutes_from_open < open_window_minutes) ? 1.0 : 0.0;

        // is_close_window: last 60 minutes
        r["is_close_window"] = (minutes_from_open > total_trading_minutes - close_window_minutes) ? 1.0 : 0.0;

        // is_midday: 120-240 minutes from open
        r["is_midday"] = (minutes_from_open >= midday_start && minutes_from_open <= midday_end) ? 1.0 : 0.0;
    }

    spdlog::debug("TimeOfDayCalculator: computed {} bars", n);
}

} // namespace ie
