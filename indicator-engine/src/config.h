#pragma once

#include <string>
#include <vector>

namespace ie {

struct DatabaseConfig {
    std::string host = "localhost";
    int port = 5432;
    std::string dbname = "algomatic";
    std::string user = "algomatic";
    std::string password = "algomatic_dev";

    std::string connection_string() const;
};

struct RedisConfig {
    std::string host = "localhost";
    int port = 6379;
    std::string channel_prefix = "algomatic";
};

struct ServiceConfig {
    int interval_minutes = 15;
    std::string mode = "both";  // "service", "listener", "both"
    std::string log_level = "info";
    std::string feature_version = "v2.0";
};

struct IndicatorConfig {
    std::vector<std::string> timeframes = {"1Min", "5Min", "15Min", "1Hour", "1Day"};
    int lookback_buffer = 250;
};

struct Config {
    DatabaseConfig database;
    RedisConfig redis;
    ServiceConfig service;
    IndicatorConfig indicators;

    /// Load from JSON file, then override with environment variables.
    static Config load(const std::string& path);
};

} // namespace ie
