#pragma once

#include "config.h"
#include "data_service_client.h"
#include "pipeline.h"
#include "redis_bus.h"

#include <atomic>

namespace ie {

/// Service that manages periodic and on-demand indicator computation.
class Service {
public:
    Service(const Config& config, DataServiceClient& db, RedisBus& redis);

    /// Run the periodic batch computation loop.
    void run_service_loop();

    /// Run the Redis listener for on-demand requests.
    void run_listener();

    /// Stop all loops.
    void stop();

private:
    const Config& config_;
    DataServiceClient& db_;
    RedisBus& redis_;
    Pipeline pipeline_;
    std::atomic<bool> running_{true};

    /// Process one ticker/timeframe: compute missing features.
    struct ComputeStats {
        int bars_computed = 0;
        int bars_skipped = 0;
    };

    ComputeStats compute_for_ticker(int64_t ticker_id, const std::string& timeframe);

    /// Handle an incoming INDICATOR_COMPUTE_REQUEST from Redis.
    void handle_compute_request(const std::string& message);
};

} // namespace ie
