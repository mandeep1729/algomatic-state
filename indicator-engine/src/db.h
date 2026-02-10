#pragma once

#include "config.h"
#include "indicators/base.h"

#include <memory>
#include <mutex>
#include <set>
#include <string>
#include <vector>

namespace ie {

struct Ticker {
    int64_t id;
    std::string symbol;
};

/// PostgreSQL database access layer via libpq.
class Database {
public:
    explicit Database(const DatabaseConfig& config);
    ~Database();

    Database(const Database&) = delete;
    Database& operator=(const Database&) = delete;

    /// Read OHLCV bars for a ticker/timeframe in a time range.
    std::vector<OHLCVBar> read_ohlcv_bars(
        int64_t ticker_id,
        const std::string& timeframe,
        time_t start = 0,
        time_t end = 0) const;

    /// Get bar_ids that already have computed features.
    std::set<int64_t> get_existing_feature_bar_ids(
        int64_t ticker_id,
        const std::string& timeframe,
        time_t start = 0,
        time_t end = 0) const;

    /// Get all active tickers.
    std::vector<Ticker> get_active_tickers() const;

    /// Look up a ticker by symbol. Returns id=0 if not found.
    Ticker get_ticker(const std::string& symbol) const;

    /// Batch upsert computed features.
    int batch_upsert_features(
        const std::vector<IndicatorResult>& results,
        int64_t ticker_id,
        const std::string& timeframe,
        const std::string& feature_version) const;

    /// Check database connectivity.
    bool health_check() const;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace ie
