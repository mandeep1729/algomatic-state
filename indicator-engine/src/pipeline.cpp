#include "pipeline.h"
#include "indicators/returns.h"
#include "indicators/volatility.h"
#include "indicators/volume.h"
#include "indicators/intrabar.h"
#include "indicators/anchor.h"
#include "indicators/time_of_day.h"
#include "indicators/talib_wrapper.h"

#include <spdlog/spdlog.h>

namespace ie {

std::vector<IndicatorResult> Pipeline::compute(const std::vector<OHLCVBar>& bars) const {
    const int n = static_cast<int>(bars.size());
    if (n == 0) return {};

    // Initialize results with bar_ids
    std::vector<IndicatorResult> results(n);
    for (int i = 0; i < n; i++) {
        results[i].bar_id = bars[i].id;
    }

    spdlog::info("Pipeline: computing indicators for {} bars", n);

    // 1. Returns (produces r1 for downstream)
    std::vector<double> r1_values;
    ReturnCalculator returns_calc;
    returns_calc.compute(bars, results, r1_values);

    // 2. Volatility (consumes r1)
    VolatilityCalculator vol_calc;
    vol_calc.compute(bars, results, r1_values);

    // 3. Volume
    VolumeCalculator volume_calc;
    volume_calc.compute(bars, results);

    // 4. Intrabar
    IntrabarCalculator intrabar_calc;
    intrabar_calc.compute(bars, results);

    // 5. Anchor
    AnchorCalculator anchor_calc;
    anchor_calc.compute(bars, results);

    // 6. Time-of-day
    TimeOfDayCalculator tod_calc;
    tod_calc.compute(bars, results);

    // 7. TA-Lib
    TALibCalculator talib_calc;
    talib_calc.compute(bars, results);

    spdlog::info("Pipeline: computed {} features per bar", results[0].features.size());
    return results;
}

} // namespace ie
