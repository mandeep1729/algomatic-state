#include "indicators/intrabar.h"
#include <algorithm>
#include <spdlog/spdlog.h>

namespace ie {

void IntrabarCalculator::compute(
    const std::vector<OHLCVBar>& bars,
    std::vector<IndicatorResult>& results) const
{
    const int n = static_cast<int>(bars.size());

    for (int i = 0; i < n; i++) {
        auto& r = results[i].features;
        double o = bars[i].open;
        double h = bars[i].high;
        double l = bars[i].low;
        double c = bars[i].close;
        double range = h - l + EPS;

        // clv: Close Location Value — (close - low) / (high - low)
        r["clv"] = (c - l) / range;

        // body_ratio: |close - open| / (high - low)
        r["body_ratio"] = std::abs(c - o) / range;

        // upper_wick: (high - max(open, close)) / (high - low)
        r["upper_wick"] = (h - std::max(o, c)) / range;

        // lower_wick: (min(open, close) - low) / (high - low)
        r["lower_wick"] = (std::min(o, c) - l) / range;
    }

    spdlog::debug("IntrabarCalculator: computed {} bars", n);
}

} // namespace ie
