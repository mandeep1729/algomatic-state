#include "indicators/anchor.h"
#include <spdlog/spdlog.h>

namespace ie {

void AnchorCalculator::compute(
    const std::vector<OHLCVBar>& bars,
    std::vector<IndicatorResult>& results) const
{
    const int n = static_cast<int>(bars.size());

    // VWAP: rolling sum of (typical_price * volume) / sum(volume)
    RollingSum tp_vol_sum, vol_sum;
    tp_vol_sum.init(vwap_window);
    vol_sum.init(vwap_window);

    EmaState ema48;
    ema48.init(ema_period);

    RollingMax high_max;
    high_max.init(breakout_window);

    for (int i = 0; i < n; i++) {
        auto& r = results[i].features;
        double h = bars[i].high;
        double l = bars[i].low;
        double c = bars[i].close;
        double v = static_cast<double>(bars[i].volume);

        double typical = (h + l + c) / 3.0;

        // vwap_60
        tp_vol_sum.push(typical * v);
        vol_sum.push(v);
        double vwap = NaN;
        if (tp_vol_sum.full() && vol_sum.sum() > 0.0) {
            vwap = tp_vol_sum.sum() / vol_sum.sum();
        }
        r["vwap_60"] = vwap;

        // dist_vwap_60: (close - vwap) / close
        if (is_valid(vwap) && c > 0.0) {
            r["dist_vwap_60"] = safe_divide(c - vwap, c);
        } else {
            r["dist_vwap_60"] = NaN;
        }

        // dist_ema_48: (close - ema48) / close
        double e48 = ema48.update(c);
        if (i >= ema_period - 1 && c > 0.0) {
            r["dist_ema_48"] = safe_divide(c - e48, c);
        } else {
            r["dist_ema_48"] = NaN;
        }

        // breakout_20: (close - high_20) / close
        high_max.push(h);
        if (high_max.full() && c > 0.0) {
            double h20 = high_max.max_val();
            r["breakout_20"] = safe_divide(c - h20, c);
            // pullback_depth: (high_20 - close) / high_20
            r["pullback_depth"] = (h20 > 0.0) ? safe_divide(h20 - c, h20) : NaN;
        } else {
            r["breakout_20"] = NaN;
            r["pullback_depth"] = NaN;
        }
    }

    spdlog::debug("AnchorCalculator: computed {} bars", n);
}

} // namespace ie
