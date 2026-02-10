#include <gtest/gtest.h>
#include <cmath>
#include <vector>

#include "indicators/base.h"
#include "indicators/returns.h"
#include "indicators/volatility.h"
#include "indicators/volume.h"
#include "indicators/intrabar.h"
#include "indicators/anchor.h"
#include "indicators/time_of_day.h"

using namespace ie;

namespace {

// Helper to create a sequence of bars with known prices
std::vector<OHLCVBar> make_bars(int n, double base_price = 100.0) {
    std::vector<OHLCVBar> bars(n);
    for (int i = 0; i < n; i++) {
        bars[i].id = i + 1;
        bars[i].ticker_id = 1;
        // Simple upward trend with some noise
        double price = base_price + i * 0.1;
        bars[i].open = price - 0.05;
        bars[i].high = price + 0.5;
        bars[i].low = price - 0.5;
        bars[i].close = price;
        bars[i].volume = 1000 + i * 10;
        bars[i].timestamp = 1704067200 + i * 60; // Start 2024-01-01 00:00 UTC, 1min bars
    }
    return bars;
}

std::vector<IndicatorResult> make_results(int n) {
    std::vector<IndicatorResult> results(n);
    for (int i = 0; i < n; i++) results[i].bar_id = i + 1;
    return results;
}

} // anonymous namespace


// ========== Base Math Tests ==========

TEST(BaseTest, SafeDivide) {
    EXPECT_NEAR(safe_divide(10.0, 2.0), 5.0, 1e-6);
    // Divide by zero returns value / EPS
    EXPECT_TRUE(std::isfinite(safe_divide(1.0, 0.0)));
}

TEST(BaseTest, LogReturn) {
    EXPECT_NEAR(log_return(110.0, 100.0), std::log(1.1), 1e-10);
    EXPECT_TRUE(std::isnan(log_return(100.0, 0.0)));
    EXPECT_TRUE(std::isnan(log_return(-1.0, 100.0)));
}

TEST(BaseTest, EmaState) {
    EmaState ema;
    ema.init(3);

    // First value = initialize
    double v1 = ema.update(100.0);
    EXPECT_DOUBLE_EQ(v1, 100.0);

    // Subsequent values weighted
    double v2 = ema.update(110.0);
    EXPECT_GT(v2, 100.0);
    EXPECT_LT(v2, 110.0);
}

TEST(BaseTest, RollingStats) {
    RollingStats rs;
    rs.init(3);

    rs.push(1.0);
    rs.push(2.0);
    EXPECT_FALSE(rs.full());

    rs.push(3.0);
    EXPECT_TRUE(rs.full());
    EXPECT_NEAR(rs.mean(), 2.0, 1e-10);
    EXPECT_GT(rs.std_dev(), 0.0);
}

TEST(BaseTest, RollingSlope) {
    RollingSlope rs;
    rs.init(3);

    // Linear data: 1, 2, 3 → slope = 1.0
    rs.push(1.0);
    rs.push(2.0);
    rs.push(3.0);
    EXPECT_NEAR(rs.slope(), 1.0, 1e-10);

    // Add 4: window is [2, 3, 4] → slope still 1.0
    rs.push(4.0);
    EXPECT_NEAR(rs.slope(), 1.0, 1e-10);
}


// ========== Return Calculator Tests ==========

TEST(ReturnsTest, BasicComputation) {
    auto bars = make_bars(100);
    auto results = make_results(100);
    std::vector<double> r1_out;

    ReturnCalculator calc;
    calc.compute(bars, results, r1_out);

    // r1 should be valid from index 1
    EXPECT_TRUE(std::isnan(results[0].features["r1"]));
    EXPECT_TRUE(std::isfinite(results[1].features["r1"]));

    // r5 valid from index 5
    EXPECT_TRUE(std::isnan(results[4].features["r5"]));
    EXPECT_TRUE(std::isfinite(results[5].features["r5"]));

    // r1_out should match
    EXPECT_EQ(r1_out.size(), 100u);
    EXPECT_DOUBLE_EQ(r1_out[1], results[1].features["r1"]);
}

TEST(ReturnsTest, Ema) {
    auto bars = make_bars(100);
    auto results = make_results(100);
    std::vector<double> r1_out;

    ReturnCalculator calc;
    calc.compute(bars, results, r1_out);

    // ema_diff should be valid after ema_slow bars
    EXPECT_TRUE(std::isnan(results[10].features["ema_diff"]));
    EXPECT_TRUE(std::isfinite(results[60].features["ema_diff"]));
}


// ========== Volatility Calculator Tests ==========

TEST(VolatilityTest, BasicComputation) {
    auto bars = make_bars(100);
    auto results = make_results(100);

    // First compute returns to get r1
    std::vector<double> r1_out;
    ReturnCalculator ret_calc;
    ret_calc.compute(bars, results, r1_out);

    VolatilityCalculator vol_calc;
    vol_calc.compute(bars, results, r1_out);

    // rv_15 valid after 15 bars
    EXPECT_TRUE(std::isnan(results[10].features["rv_15"]));
    EXPECT_TRUE(std::isfinite(results[20].features["rv_15"]));
    EXPECT_GT(results[20].features["rv_15"], 0.0);

    // range_1 should always be valid (non-NaN for valid bars)
    EXPECT_TRUE(std::isfinite(results[0].features["range_1"]));
    EXPECT_GT(results[0].features["range_1"], 0.0);
}


// ========== Volume Calculator Tests ==========

TEST(VolumeTest, BasicComputation) {
    auto bars = make_bars(100);
    auto results = make_results(100);

    VolumeCalculator calc;
    calc.compute(bars, results);

    // vol1 and dvol1 always valid
    EXPECT_DOUBLE_EQ(results[0].features["vol1"], 1000.0);
    EXPECT_GT(results[0].features["dvol1"], 0.0);

    // relvol_60 valid after 60 bars
    EXPECT_TRUE(std::isnan(results[10].features["relvol_60"]));
    EXPECT_TRUE(std::isfinite(results[70].features["relvol_60"]));
}


// ========== Intrabar Calculator Tests ==========

TEST(IntrabarTest, BasicComputation) {
    auto bars = make_bars(10);
    auto results = make_results(10);

    IntrabarCalculator calc;
    calc.compute(bars, results);

    for (int i = 0; i < 10; i++) {
        // clv should be in [0, 1]
        EXPECT_GE(results[i].features["clv"], 0.0);
        EXPECT_LE(results[i].features["clv"], 1.0);

        // body_ratio in [0, 1]
        EXPECT_GE(results[i].features["body_ratio"], 0.0);
        EXPECT_LE(results[i].features["body_ratio"], 1.0);

        // upper_wick + body_ratio + lower_wick ≈ 1
        double sum = results[i].features["upper_wick"]
                   + results[i].features["body_ratio"]
                   + results[i].features["lower_wick"];
        EXPECT_NEAR(sum, 1.0, 0.01);
    }
}


// ========== Anchor Calculator Tests ==========

TEST(AnchorTest, BasicComputation) {
    auto bars = make_bars(100);
    auto results = make_results(100);

    AnchorCalculator calc;
    calc.compute(bars, results);

    // vwap_60 valid after 60 bars
    EXPECT_TRUE(std::isnan(results[10].features["vwap_60"]));
    EXPECT_TRUE(std::isfinite(results[70].features["vwap_60"]));

    // breakout_20 valid after 20 bars
    EXPECT_TRUE(std::isnan(results[10].features["breakout_20"]));
    EXPECT_TRUE(std::isfinite(results[25].features["breakout_20"]));
}


// ========== Time-of-Day Calculator Tests ==========

TEST(TimeOfDayTest, BasicComputation) {
    auto bars = make_bars(10);
    auto results = make_results(10);

    TimeOfDayCalculator calc;
    calc.compute(bars, results);

    for (int i = 0; i < 10; i++) {
        // tod_sin/cos should be in [-1, 1]
        EXPECT_GE(results[i].features["tod_sin"], -1.0);
        EXPECT_LE(results[i].features["tod_sin"], 1.0);
        EXPECT_GE(results[i].features["tod_cos"], -1.0);
        EXPECT_LE(results[i].features["tod_cos"], 1.0);

        // Binary flags should be 0 or 1
        double ow = results[i].features["is_open_window"];
        EXPECT_TRUE(ow == 0.0 || ow == 1.0);
    }
}
