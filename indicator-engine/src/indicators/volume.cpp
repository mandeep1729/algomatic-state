#include "indicators/volume.h"
#include <spdlog/spdlog.h>

namespace ie {

void VolumeCalculator::compute(
    const std::vector<OHLCVBar>& bars,
    std::vector<IndicatorResult>& results) const
{
    const int n = static_cast<int>(bars.size());

    RollingStats vol_stats, dvol_stats;
    vol_stats.init(window);
    dvol_stats.init(window);

    RollingSum vol_sum;
    vol_sum.init(window);

    for (int i = 0; i < n; i++) {
        auto& r = results[i].features;
        double v = static_cast<double>(bars[i].volume);
        double c = bars[i].close;
        double dv = c * v;  // dollar volume

        r["vol1"] = v;
        r["dvol1"] = dv;

        // relvol_60: volume / mean(volume, 60)
        vol_sum.push(v);
        if (vol_sum.full()) {
            r["relvol_60"] = safe_divide(v, vol_sum.mean());
        } else {
            r["relvol_60"] = NaN;
        }

        // vol_z_60: zscore of volume
        vol_stats.push(v);
        r["vol_z_60"] = vol_stats.full() ? vol_stats.zscore(v) : NaN;

        // dvol_z_60: zscore of dollar volume
        dvol_stats.push(dv);
        r["dvol_z_60"] = dvol_stats.full() ? dvol_stats.zscore(dv) : NaN;
    }

    spdlog::debug("VolumeCalculator: computed {} bars", n);
}

} // namespace ie
