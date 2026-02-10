#include "redis_bus.h"

#include <hiredis/hiredis.h>
#include <spdlog/spdlog.h>
#include <stdexcept>

namespace ie {

struct RedisBus::Impl {
    RedisConfig config;
    redisContext* pub_ctx = nullptr;

    Impl(const RedisConfig& cfg) : config(cfg) {
        connect_pub();
    }

    ~Impl() {
        if (pub_ctx) redisFree(pub_ctx);
    }

    void connect_pub() {
        struct timeval timeout = {5, 0};
        pub_ctx = redisConnectWithTimeout(config.host.c_str(), config.port, timeout);
        if (!pub_ctx || pub_ctx->err) {
            std::string err = pub_ctx ? pub_ctx->errstr : "null context";
            if (pub_ctx) redisFree(pub_ctx);
            pub_ctx = nullptr;
            throw std::runtime_error("Redis connect failed: " + err);
        }
        spdlog::info("Connected to Redis at {}:{}", config.host, config.port);
    }
};


RedisBus::RedisBus(const RedisConfig& config) : impl_(std::make_unique<Impl>(config)) {}
RedisBus::~RedisBus() = default;


void RedisBus::publish(const std::string& channel, const std::string& message) {
    if (!impl_->pub_ctx) throw std::runtime_error("Redis not connected");

    redisReply* reply = static_cast<redisReply*>(
        redisCommand(impl_->pub_ctx, "PUBLISH %s %b", channel.c_str(), message.data(), message.size()));

    if (!reply) {
        spdlog::error("Redis PUBLISH failed: null reply");
        return;
    }
    freeReplyObject(reply);

    spdlog::debug("Published to {}: {} bytes", channel, message.size());
}


void RedisBus::subscribe(const std::string& channel, MessageHandler handler) {
    // Create a separate connection for subscribing (hiredis requirement)
    struct timeval timeout = {5, 0};
    redisContext* sub_ctx = redisConnectWithTimeout(
        impl_->config.host.c_str(), impl_->config.port, timeout);

    if (!sub_ctx || sub_ctx->err) {
        std::string err = sub_ctx ? sub_ctx->errstr : "null context";
        if (sub_ctx) redisFree(sub_ctx);
        throw std::runtime_error("Redis subscribe connect failed: " + err);
    }

    redisReply* reply = static_cast<redisReply*>(
        redisCommand(sub_ctx, "SUBSCRIBE %s", channel.c_str()));
    if (reply) freeReplyObject(reply);

    spdlog::info("Subscribed to Redis channel: {}", channel);

    while (true) {
        redisReply* msg = nullptr;
        if (redisGetReply(sub_ctx, reinterpret_cast<void**>(&msg)) != REDIS_OK) {
            spdlog::error("Redis subscribe read error");
            break;
        }

        if (msg && msg->type == REDIS_REPLY_ARRAY && msg->elements >= 3) {
            std::string type(msg->element[0]->str, msg->element[0]->len);
            if (type == "message") {
                std::string ch(msg->element[1]->str, msg->element[1]->len);
                std::string data(msg->element[2]->str, msg->element[2]->len);
                handler(ch, data);
            }
        }
        if (msg) freeReplyObject(msg);
    }

    redisFree(sub_ctx);
}


std::string RedisBus::channel_for(const std::string& event_type) const {
    return impl_->config.channel_prefix + ":" + event_type;
}


bool RedisBus::health_check() const {
    if (!impl_->pub_ctx) return false;
    redisReply* reply = static_cast<redisReply*>(redisCommand(impl_->pub_ctx, "PING"));
    if (!reply) return false;
    bool ok = (reply->type == REDIS_REPLY_STATUS && std::string(reply->str) == "PONG");
    freeReplyObject(reply);
    return ok;
}

} // namespace ie
