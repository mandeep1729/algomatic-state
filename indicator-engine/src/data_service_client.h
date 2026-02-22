#pragma once

#include "indicators/base.h"

#include <memory>
#include <set>
#include <string>
#include <vector>

namespace ie {

struct Ticker {
    int64_t id;
    std::string symbol;
};

/// gRPC client for the data-service, drop-in replacement for Database.
class DataServiceClient {
public:
    explicit DataServiceClient(const std::string& target);
    ~DataServiceClient();

    DataServiceClient(const DataServiceClient&) = delete;
    DataServiceClient& operator=(const DataServiceClient&) = delete;

    /// Read OHLCV bars for a ticker/timeframe in a time range (uses StreamBars).
    std::vector<OHLCVBar> read_ohlcv_bars(
        int64_t ticker_id,
        const std::string& timeframe,
        time_t start = 0,
        time_t end = 0) const;

    /// Get bar_ids that already have computed features (non-aggregate timeframes only).
    std::set<int64_t> get_existing_feature_bar_ids(
        int64_t ticker_id,
        const std::string& timeframe,
        time_t start = 0,
        time_t end = 0) const;

    /// Get timestamps that already have computed features (works for all timeframes).
    std::set<time_t> get_existing_feature_timestamps(
        int64_t ticker_id,
        const std::string& timeframe,
        time_t start = 0,
        time_t end = 0) const;

    /// Get all active tickers.
    std::vector<Ticker> get_active_tickers() const;

    /// Look up a ticker by symbol. Returns id=0 if not found.
    Ticker get_ticker(const std::string& symbol) const;

    /// Batch upsert computed features (chunks into 5000 per RPC).
    int batch_upsert_features(
        const std::vector<IndicatorResult>& results,
        int64_t ticker_id,
        const std::string& timeframe,
        const std::string& feature_version) const;

    /// Check gRPC connectivity.
    bool health_check() const;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace ie
