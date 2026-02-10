#include "indicators/returns.h"
#include <cmath>
#include <spdlog/spdlog.h>

namespace ie {

void ReturnCalculator::compute(
    const std::vector<OHLCVBar>& bars,
    std::vector<IndicatorResult>& results,
    std::vector<double>& r1_out) const
{
    const int n = static_cast<int>(bars.size());
    r1_out.resize(n, NaN);

    EmaState ema_f, ema_s;
    ema_f.init(ema_fast);
    ema_s.init(ema_slow);

    RollingSum cumret_sum;
    cumret_sum.init(long_window);

    RollingSlope slope;
    slope.init(long_window);

    RollingStats rv_rolling;
    rv_rolling.init(long_window);

    for (int i = 0; i < n; i++) {
        auto& r = results[i].features;
        double c = bars[i].close;

        // r1: 1-bar log return
        double r1 = (i >= 1) ? log_return(c, bars[i - 1].close) : NaN;
        r["r1"] = r1;
        r1_out[i] = r1;

        // r5, r15, r60: multi-period log returns
        r["r5"]  = (i >= short_window)  ? log_return(c, bars[i - short_window].close)  : NaN;
        r["r15"] = (i >= medium_window) ? log_return(c, bars[i - medium_window].close) : NaN;
        r["r60"] = (i >= long_window)   ? log_return(c, bars[i - long_window].close)   : NaN;

        // cumret_60: rolling sum of r1 over 60 bars
        if (is_valid(r1)) cumret_sum.push(r1);
        r["cumret_60"] = cumret_sum.full() ? cumret_sum.sum() : NaN;

        // ema_diff: (EMA_fast - EMA_slow) / close
        double ef = ema_f.update(c);
        double es = ema_s.update(c);
        if (i >= ema_slow - 1 && c > 0.0) {
            r["ema_diff"] = safe_divide(ef - es, c);
        } else {
            r["ema_diff"] = NaN;
        }

        // slope_60: linear regression slope of log(close)
        double lc = (c > 0.0) ? std::log(c) : NaN;
        if (is_valid(lc)) slope.push(lc);
        r["slope_60"] = slope.full() ? slope.slope() : NaN;

        // trend_strength: |slope_60| / rv_60
        if (is_valid(r1)) rv_rolling.push(r1);
        double rv60 = rv_rolling.full() ? rv_rolling.std_dev() : NaN;
        if (is_valid(r["slope_60"]) && is_valid(rv60)) {
            r["trend_strength"] = safe_divide(std::abs(r["slope_60"]), rv60);
        } else {
            r["trend_strength"] = NaN;
        }
    }

    spdlog::debug("ReturnCalculator: computed {} bars", n);
}

} // namespace ie
