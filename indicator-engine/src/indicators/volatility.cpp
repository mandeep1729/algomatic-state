#include "indicators/volatility.h"
#include <spdlog/spdlog.h>

namespace ie {

void VolatilityCalculator::compute(
    const std::vector<OHLCVBar>& bars,
    std::vector<IndicatorResult>& results,
    const std::vector<double>& r1_values) const
{
    const int n = static_cast<int>(bars.size());

    RollingStats rv_short, rv_long;
    rv_short.init(short_window);
    rv_long.init(long_window);

    RollingStats range_z;
    range_z.init(long_window);

    RollingSum atr_sum;
    atr_sum.init(long_window);

    // vol_of_vol: std of rv_15 over 60 bars
    RollingStats vov_stats;
    vov_stats.init(long_window);

    for (int i = 0; i < n; i++) {
        auto& r = results[i].features;
        double h = bars[i].high;
        double l = bars[i].low;
        double c = bars[i].close;

        // Get r1 from precomputed values
        double r1 = (i < static_cast<int>(r1_values.size())) ? r1_values[i] : NaN;

        // rv_15, rv_60: rolling std of r1
        if (is_valid(r1)) {
            rv_short.push(r1);
            rv_long.push(r1);
        }
        r["rv_15"] = rv_short.full() ? rv_short.std_dev() : NaN;
        r["rv_60"] = rv_long.full() ? rv_long.std_dev() : NaN;

        // range_1: (high - low) / close
        double rng = (c > 0.0) ? (h - l) / c : NaN;
        r["range_1"] = rng;

        // atr_60: rolling mean of range_1
        if (is_valid(rng)) atr_sum.push(rng);
        r["atr_60"] = atr_sum.full() ? atr_sum.mean() : NaN;

        // range_z_60: zscore of range_1
        if (is_valid(rng)) range_z.push(rng);
        r["range_z_60"] = range_z.full() ? range_z.zscore(rng) : NaN;

        // vol_of_vol: std of rv_15 over 60 bars
        double rv15 = r["rv_15"];
        if (is_valid(rv15)) vov_stats.push(rv15);
        r["vol_of_vol"] = vov_stats.full() ? vov_stats.std_dev() : NaN;
    }

    spdlog::debug("VolatilityCalculator: computed {} bars", n);
}

} // namespace ie
