#pragma once

#include "indicators/base.h"
#include <vector>

namespace ie {

/// Compute volume features: vol1, dvol1, relvol_60, vol_z_60, dvol_z_60.
///
/// Mirrors src/features/volume.py:VolumeFeatureCalculator
struct VolumeCalculator {
    int window = 60;

    void compute(const std::vector<OHLCVBar>& bars,
                 std::vector<IndicatorResult>& results) const;
};

} // namespace ie
