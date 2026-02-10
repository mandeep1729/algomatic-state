#include "config.h"
#include "db.h"
#include "redis_bus.h"
#include "service.h"

#include <spdlog/spdlog.h>
#include <spdlog/sinks/stdout_color_sinks.h>

#include <csignal>
#include <cstring>
#include <string>
#include <thread>

static ie::Service* g_service = nullptr;

void signal_handler(int sig) {
    spdlog::info("Received signal {}, shutting down...", sig);
    if (g_service) g_service->stop();
}

void setup_logging(const std::string& level) {
    auto console = spdlog::stdout_color_mt("console");
    spdlog::set_default_logger(console);

    if (level == "debug") spdlog::set_level(spdlog::level::debug);
    else if (level == "warn") spdlog::set_level(spdlog::level::warn);
    else if (level == "error") spdlog::set_level(spdlog::level::err);
    else spdlog::set_level(spdlog::level::info);

    spdlog::set_pattern("[%Y-%m-%d %H:%M:%S.%e] [%^%l%$] [%t] %v");
}

int main(int argc, char* argv[]) {
    // Parse --config and --mode from CLI
    std::string config_path = "config.json";
    std::string mode_override;

    for (int i = 1; i < argc; i++) {
        if (std::strcmp(argv[i], "--config") == 0 && i + 1 < argc) {
            config_path = argv[++i];
        } else if (std::strncmp(argv[i], "--mode=", 7) == 0) {
            mode_override = argv[i] + 7;
        } else if (std::strcmp(argv[i], "--mode") == 0 && i + 1 < argc) {
            mode_override = argv[++i];
        }
    }

    // Load configuration
    ie::Config config = ie::Config::load(config_path);
    if (!mode_override.empty()) {
        config.service.mode = mode_override;
    }

    setup_logging(config.service.log_level);

    spdlog::info("indicator-engine v1.0.0 starting (mode={})", config.service.mode);

    // Set up signal handling
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    try {
        // Initialize database
        ie::Database db(config.database);
        if (!db.health_check()) {
            spdlog::error("Database health check failed");
            return 1;
        }
        spdlog::info("Database connected");

        // Initialize Redis
        ie::RedisBus redis(config.redis);
        if (!redis.health_check()) {
            spdlog::warn("Redis health check failed, continuing without Redis");
        } else {
            spdlog::info("Redis connected");
        }

        // Create service
        ie::Service service(config, db, redis);
        g_service = &service;

        if (config.service.mode == "service") {
            service.run_service_loop();
        } else if (config.service.mode == "listener") {
            service.run_listener();
        } else {
            // "both" — run service loop in background, listener in foreground
            std::thread service_thread([&service]() {
                service.run_service_loop();
            });

            service.run_listener();

            if (service_thread.joinable()) service_thread.join();
        }

        g_service = nullptr;
        spdlog::info("indicator-engine shut down cleanly");
        return 0;

    } catch (const std::exception& e) {
        spdlog::error("Fatal error: {}", e.what());
        return 1;
    }
}
