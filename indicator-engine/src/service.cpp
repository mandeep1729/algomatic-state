#include "service.h"
#include "json_builder.h"

#include <chrono>
#include <nlohmann/json.hpp>
#include <spdlog/spdlog.h>
#include <thread>

using json = nlohmann::json;

namespace ie {

// Batch size for writing features to database.
// Smaller batches reduce PostgreSQL memory pressure and allow incremental commits.
constexpr size_t WRITE_BATCH_SIZE = 5000;

Service::Service(const Config& config, DataServiceClient& db, RedisBus& redis)
    : config_(config), db_(db), redis_(redis) {}


void Service::run_service_loop() {
    spdlog::info("Service loop started (interval={}min)", config_.service.interval_minutes);
    auto interval = std::chrono::minutes(config_.service.interval_minutes);

    while (running_) {
        auto start = std::chrono::steady_clock::now();

        try {
            auto tickers = db_.get_active_tickers();
            spdlog::info("Processing {} active tickers", tickers.size());

            int total_computed = 0, total_skipped = 0;

            for (const auto& ticker : tickers) {
                for (const auto& tf : config_.indicators.timeframes) {
                    auto stats = compute_for_ticker(ticker.id, tf);
                    total_computed += stats.bars_computed;
                    total_skipped += stats.bars_skipped;
                }
            }

            auto elapsed = std::chrono::steady_clock::now() - start;
            auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(elapsed).count();
            spdlog::info("Service loop complete: {} computed, {} skipped, {}ms",
                         total_computed, total_skipped, ms);

        } catch (const std::exception& e) {
            spdlog::error("Service loop error: {}", e.what());
        }

        // Sleep for the remaining interval
        auto elapsed = std::chrono::steady_clock::now() - start;
        auto remaining = interval - elapsed;
        if (remaining.count() > 0 && running_) {
            std::this_thread::sleep_for(remaining);
        }
    }

    spdlog::info("Service loop stopped");
}


void Service::run_listener() {
    std::string channel = redis_.channel_for("indicator_compute_request");
    spdlog::info("Listener started on channel: {}", channel);

    redis_.subscribe(channel, [this](const std::string& ch, const std::string& msg) {
        if (!running_) return;
        try {
            handle_compute_request(msg);
        } catch (const std::exception& e) {
            spdlog::error("Error handling compute request: {}", e.what());
        }
    });
}


void Service::stop() {
    running_ = false;
}


Service::ComputeStats Service::compute_for_ticker(int64_t ticker_id, const std::string& timeframe) {
    ComputeStats stats;

    // Read all OHLCV bars
    auto bars = db_.read_ohlcv_bars(ticker_id, timeframe);
    if (bars.empty()) return stats;

    // Get existing feature bar_ids
    auto existing = db_.get_existing_feature_bar_ids(ticker_id, timeframe);

    // Identify missing bar_ids
    std::set<int64_t> all_ids;
    for (const auto& bar : bars) all_ids.insert(bar.id);

    std::set<int64_t> missing;
    for (auto id : all_ids) {
        if (existing.find(id) == existing.end()) missing.insert(id);
    }

    stats.bars_skipped = static_cast<int>(existing.size());

    if (missing.empty()) {
        spdlog::debug("ticker_id={} {}: all {} bars have features", ticker_id, timeframe, bars.size());
        return stats;
    }

    spdlog::info("ticker_id={} {}: computing for {} missing bars (out of {} total)",
                 ticker_id, timeframe, missing.size(), bars.size());

    // Compute all indicators (need full range for lookback)
    auto results = pipeline_.compute(bars);

    // Filter to only missing bar_ids
    std::vector<IndicatorResult> to_write;
    to_write.reserve(missing.size());
    for (auto& r : results) {
        if (missing.count(r.bar_id)) {
            to_write.push_back(std::move(r));
        }
    }

    // Write in batches to reduce PostgreSQL memory pressure
    int total_written = 0;
    for (size_t i = 0; i < to_write.size(); i += WRITE_BATCH_SIZE) {
        size_t end = std::min(i + WRITE_BATCH_SIZE, to_write.size());
        std::vector<IndicatorResult> batch(
            std::make_move_iterator(to_write.begin() + i),
            std::make_move_iterator(to_write.begin() + end)
        );

        int written = db_.batch_upsert_features(batch, ticker_id, timeframe, config_.service.feature_version);
        total_written += written;

        spdlog::debug("ticker_id={} {}: wrote batch {}-{} ({} rows)",
                      ticker_id, timeframe, i, end, written);
    }
    stats.bars_computed = total_written;

    return stats;
}


void Service::handle_compute_request(const std::string& message) {
    json req = json::parse(message);

    std::string symbol = req.value("/payload/symbol"_json_pointer, "");
    std::string timeframe = req.value("/payload/timeframe"_json_pointer, "5Min");
    std::string correlation_id = req.value("correlation_id", "");

    spdlog::info("Handling compute request: symbol={}, timeframe={}, correlation_id={}",
                 symbol, timeframe, correlation_id);

    // Look up ticker
    auto ticker = db_.get_ticker(symbol);
    if (ticker.id == 0) {
        spdlog::error("Ticker not found: {}", symbol);
        // Publish failure
        json resp;
        resp["event_type"] = "indicator_compute_failed";
        resp["payload"]["symbol"] = symbol;
        resp["payload"]["error"] = "Ticker not found";
        resp["source"] = "indicator-engine";
        resp["correlation_id"] = correlation_id;
        redis_.publish(redis_.channel_for("indicator_compute_failed"), resp.dump());
        return;
    }

    // Compute
    auto stats = compute_for_ticker(ticker.id, timeframe);

    // Publish completion
    json resp;
    resp["event_type"] = "indicator_compute_complete";
    resp["payload"]["symbol"] = symbol;
    resp["payload"]["timeframe"] = timeframe;
    resp["payload"]["bars_computed"] = stats.bars_computed;
    resp["payload"]["bars_skipped"] = stats.bars_skipped;
    resp["source"] = "indicator-engine";
    resp["correlation_id"] = correlation_id;

    redis_.publish(redis_.channel_for("indicator_compute_complete"), resp.dump());

    spdlog::info("Compute complete: symbol={}, computed={}, skipped={}",
                 symbol, stats.bars_computed, stats.bars_skipped);
}

} // namespace ie
