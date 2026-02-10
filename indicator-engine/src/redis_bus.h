#pragma once

#include "config.h"

#include <functional>
#include <memory>
#include <string>

namespace ie {

/// Redis pub/sub client using hiredis.
class RedisBus {
public:
    explicit RedisBus(const RedisConfig& config);
    ~RedisBus();

    RedisBus(const RedisBus&) = delete;
    RedisBus& operator=(const RedisBus&) = delete;

    using MessageHandler = std::function<void(const std::string& channel, const std::string& message)>;

    /// Publish a message to a channel.
    void publish(const std::string& channel, const std::string& message);

    /// Subscribe and block, calling handler for each message.
    /// Returns when handler signals stop or on error.
    void subscribe(const std::string& channel, MessageHandler handler);

    /// Build the full channel name for an event type.
    std::string channel_for(const std::string& event_type) const;

    bool health_check() const;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace ie
