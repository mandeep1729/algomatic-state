#include <gtest/gtest.h>
#include <cmath>

#include "pipeline.h"
#include "json_builder.h"

using namespace ie;

namespace {

std::vector<OHLCVBar> make_bars(int n) {
    std::vector<OHLCVBar> bars(n);
    for (int i = 0; i < n; i++) {
        bars[i].id = i + 1;
        bars[i].ticker_id = 1;
        double price = 100.0 + i * 0.1 + std::sin(i * 0.1) * 2.0;
        bars[i].open = price - 0.3;
        bars[i].high = price + 1.0;
        bars[i].low = price - 1.0;
        bars[i].close = price;
        bars[i].volume = 1000 + (i % 50) * 100;
        bars[i].timestamp = 1704067200 + i * 60;
    }
    return bars;
}

} // anonymous namespace


TEST(PipelineTest, EmptyBars) {
    Pipeline pipeline;
    auto results = pipeline.compute({});
    EXPECT_TRUE(results.empty());
}

TEST(PipelineTest, ComputeAllIndicators) {
    auto bars = make_bars(200);
    Pipeline pipeline;
    auto results = pipeline.compute(bars);

    ASSERT_EQ(results.size(), 200u);

    // Check bar_ids are preserved
    for (int i = 0; i < 200; i++) {
        EXPECT_EQ(results[i].bar_id, i + 1);
    }

    // At bar 100 (well past all lookback periods), all core features should be valid
    auto& f = results[100].features;

    // Returns
    EXPECT_TRUE(std::isfinite(f["r1"]));
    EXPECT_TRUE(std::isfinite(f["r5"]));
    EXPECT_TRUE(std::isfinite(f["r15"]));
    EXPECT_TRUE(std::isfinite(f["r60"]));
    EXPECT_TRUE(std::isfinite(f["cumret_60"]));
    EXPECT_TRUE(std::isfinite(f["ema_diff"]));
    EXPECT_TRUE(std::isfinite(f["slope_60"]));

    // Volatility
    EXPECT_TRUE(std::isfinite(f["rv_15"]));
    EXPECT_TRUE(std::isfinite(f["rv_60"]));
    EXPECT_TRUE(std::isfinite(f["range_1"]));
    EXPECT_TRUE(std::isfinite(f["atr_60"]));

    // Volume
    EXPECT_TRUE(std::isfinite(f["vol1"]));
    EXPECT_TRUE(std::isfinite(f["dvol1"]));
    EXPECT_TRUE(std::isfinite(f["relvol_60"]));

    // Intrabar
    EXPECT_TRUE(std::isfinite(f["clv"]));
    EXPECT_TRUE(std::isfinite(f["body_ratio"]));
    EXPECT_TRUE(std::isfinite(f["upper_wick"]));
    EXPECT_TRUE(std::isfinite(f["lower_wick"]));

    // Anchor
    EXPECT_TRUE(std::isfinite(f["vwap_60"]));
    EXPECT_TRUE(std::isfinite(f["dist_vwap_60"]));
    EXPECT_TRUE(std::isfinite(f["breakout_20"]));

    // Time-of-day
    EXPECT_TRUE(std::isfinite(f["tod_sin"]));
    EXPECT_TRUE(std::isfinite(f["tod_cos"]));
}

TEST(PipelineTest, FeatureCount) {
    auto bars = make_bars(200);
    Pipeline pipeline;
    auto results = pipeline.compute(bars);

    // Core custom indicators = 8 + 6 + 5 + 4 + 5 + 5 = 33
    // With TA-Lib disabled: at least 33 features
    // With TA-Lib enabled: 33 + ~50+ features
    int feature_count = static_cast<int>(results[100].features.size());
    EXPECT_GE(feature_count, 33);
}


// ========== JSON Builder Tests ==========

TEST(JsonBuilderTest, BasicBuild) {
    std::unordered_map<std::string, double> features;
    features["r1"] = 0.001;
    features["rv_60"] = 0.015;

    std::string json = build_features_json(features);
    EXPECT_NE(json.find("r1"), std::string::npos);
    EXPECT_NE(json.find("0.001"), std::string::npos);
}

TEST(JsonBuilderTest, SkipsNaN) {
    std::unordered_map<std::string, double> features;
    features["valid"] = 1.0;
    features["nan_val"] = std::numeric_limits<double>::quiet_NaN();
    features["inf_val"] = std::numeric_limits<double>::infinity();

    std::string json = build_features_json(features);
    EXPECT_NE(json.find("valid"), std::string::npos);
    EXPECT_EQ(json.find("nan_val"), std::string::npos);
    EXPECT_EQ(json.find("inf_val"), std::string::npos);
}

TEST(JsonBuilderTest, EmptyFeatures) {
    std::unordered_map<std::string, double> features;
    std::string json = build_features_json(features);
    EXPECT_EQ(json, "{}");
}
