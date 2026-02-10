#include "config.h"

#include <cstdlib>
#include <fstream>
#include <nlohmann/json.hpp>
#include <spdlog/spdlog.h>

using json = nlohmann::json;

namespace ie {

std::string DatabaseConfig::connection_string() const {
    return "host=" + host +
           " port=" + std::to_string(port) +
           " dbname=" + dbname +
           " user=" + user +
           " password=" + password;
}

namespace {

std::string env_or(const char* name, const std::string& fallback) {
    const char* val = std::getenv(name);
    return val ? std::string(val) : fallback;
}

int env_int_or(const char* name, int fallback) {
    const char* val = std::getenv(name);
    return val ? std::atoi(val) : fallback;
}

} // anonymous namespace

Config Config::load(const std::string& path) {
    Config cfg;

    // Load from JSON file if it exists
    std::ifstream f(path);
    if (f.is_open()) {
        try {
            json j = json::parse(f);

            if (j.count("database")) {
                auto& db = j["database"];
                if (db.count("host")) cfg.database.host = db["host"];
                if (db.count("port")) cfg.database.port = db["port"];
                if (db.count("dbname")) cfg.database.dbname = db["dbname"];
                if (db.count("user")) cfg.database.user = db["user"];
                if (db.count("password")) cfg.database.password = db["password"];
            }

            if (j.count("redis")) {
                auto& r = j["redis"];
                if (r.count("host")) cfg.redis.host = r["host"];
                if (r.count("port")) cfg.redis.port = r["port"];
                if (r.count("channel_prefix")) cfg.redis.channel_prefix = r["channel_prefix"];
            }

            if (j.count("service")) {
                auto& s = j["service"];
                if (s.count("interval_minutes")) cfg.service.interval_minutes = s["interval_minutes"];
                if (s.count("mode")) cfg.service.mode = s["mode"];
                if (s.count("log_level")) cfg.service.log_level = s["log_level"];
                if (s.count("feature_version")) cfg.service.feature_version = s["feature_version"];
            }

            if (j.count("indicators")) {
                auto& ind = j["indicators"];
                if (ind.count("timeframes")) {
                    cfg.indicators.timeframes.clear();
                    for (auto& tf : ind["timeframes"])
                        cfg.indicators.timeframes.push_back(tf);
                }
                if (ind.count("lookback_buffer")) cfg.indicators.lookback_buffer = ind["lookback_buffer"];
            }

            spdlog::info("Loaded config from {}", path);
        } catch (const std::exception& e) {
            spdlog::warn("Failed to parse config file {}: {}", path, e.what());
        }
    } else {
        spdlog::info("Config file {} not found, using defaults + env vars", path);
    }

    // Override with environment variables
    cfg.database.host = env_or("DB_HOST", cfg.database.host);
    cfg.database.port = env_int_or("DB_PORT", cfg.database.port);
    cfg.database.dbname = env_or("DB_NAME", cfg.database.dbname);
    cfg.database.user = env_or("DB_USER", cfg.database.user);
    cfg.database.password = env_or("DB_PASSWORD", cfg.database.password);

    cfg.redis.host = env_or("REDIS_HOST", cfg.redis.host);
    cfg.redis.port = env_int_or("REDIS_PORT", cfg.redis.port);
    cfg.redis.channel_prefix = env_or("REDIS_CHANNEL_PREFIX", cfg.redis.channel_prefix);

    cfg.service.mode = env_or("ENGINE_MODE", cfg.service.mode);
    cfg.service.log_level = env_or("ENGINE_LOG_LEVEL", cfg.service.log_level);
    cfg.service.feature_version = env_or("FEATURE_VERSION", cfg.service.feature_version);
    cfg.service.interval_minutes = env_int_or("ENGINE_INTERVAL_MINUTES", cfg.service.interval_minutes);

    return cfg;
}

} // namespace ie
