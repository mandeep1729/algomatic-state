#include "db.h"
#include "json_builder.h"

#include <libpq-fe.h>
#include <spdlog/spdlog.h>
#include <cstring>
#include <sstream>
#include <stdexcept>

namespace ie {

struct Database::Impl {
    DatabaseConfig config;
    PGconn* conn = nullptr;
    mutable std::mutex mtx;

    Impl(const DatabaseConfig& cfg) : config(cfg) {
        connect();
    }

    ~Impl() {
        if (conn) PQfinish(conn);
    }

    void connect() {
        conn = PQconnectdb(config.connection_string().c_str());
        if (PQstatus(conn) != CONNECTION_OK) {
            std::string err = PQerrorMessage(conn);
            PQfinish(conn);
            conn = nullptr;
            throw std::runtime_error("DB connect failed: " + err);
        }
        spdlog::info("Connected to PostgreSQL at {}:{}/{}", config.host, config.port, config.dbname);
    }

    void ensure_connected() {
        if (!conn || PQstatus(conn) != CONNECTION_OK) {
            spdlog::warn("DB connection lost, reconnecting...");
            if (conn) PQfinish(conn);
            connect();
        }
    }

    PGresult* exec(const char* sql) {
        ensure_connected();
        PGresult* res = PQexec(conn, sql);
        if (!res) throw std::runtime_error("PQexec returned null");
        return res;
    }

    PGresult* exec_params(const char* sql, int nParams, const char* const* paramValues) {
        ensure_connected();
        PGresult* res = PQexecParams(conn, sql, nParams, nullptr, paramValues, nullptr, nullptr, 0);
        if (!res) throw std::runtime_error("PQexecParams returned null");
        return res;
    }
};


Database::Database(const DatabaseConfig& config) : impl_(std::make_unique<Impl>(config)) {}
Database::~Database() = default;


std::vector<OHLCVBar> Database::read_ohlcv_bars(
    int64_t ticker_id,
    const std::string& timeframe,
    time_t start,
    time_t end) const
{
    std::lock_guard<std::mutex> lock(impl_->mtx);

    std::ostringstream sql;
    sql << "SELECT id, ticker_id, "
        << "EXTRACT(EPOCH FROM timestamp)::bigint, "
        << "open, high, low, close, volume "
        << "FROM ohlcv_bars "
        << "WHERE ticker_id = " << ticker_id
        << " AND timeframe = '" << timeframe << "'";

    if (start > 0) sql << " AND timestamp >= to_timestamp(" << start << ")";
    if (end > 0) sql << " AND timestamp < to_timestamp(" << end << ")";
    sql << " ORDER BY timestamp ASC";

    PGresult* res = impl_->exec(sql.str().c_str());
    if (PQresultStatus(res) != PGRES_TUPLES_OK) {
        std::string err = PQresultErrorMessage(res);
        PQclear(res);
        throw std::runtime_error("read_ohlcv_bars failed: " + err);
    }

    int nrows = PQntuples(res);
    std::vector<OHLCVBar> bars;
    bars.reserve(nrows);

    for (int i = 0; i < nrows; i++) {
        OHLCVBar bar;
        bar.id = std::stoll(PQgetvalue(res, i, 0));
        bar.ticker_id = std::stoll(PQgetvalue(res, i, 1));
        bar.timestamp = std::stoll(PQgetvalue(res, i, 2));
        bar.open = std::stod(PQgetvalue(res, i, 3));
        bar.high = std::stod(PQgetvalue(res, i, 4));
        bar.low = std::stod(PQgetvalue(res, i, 5));
        bar.close = std::stod(PQgetvalue(res, i, 6));
        bar.volume = std::stoll(PQgetvalue(res, i, 7));
        bars.push_back(bar);
    }

    PQclear(res);
    spdlog::debug("Read {} OHLCV bars for ticker_id={} timeframe={}", nrows, ticker_id, timeframe);
    return bars;
}


std::set<int64_t> Database::get_existing_feature_bar_ids(
    int64_t ticker_id,
    const std::string& timeframe,
    time_t start,
    time_t end) const
{
    std::lock_guard<std::mutex> lock(impl_->mtx);

    std::ostringstream sql;
    sql << "SELECT bar_id FROM computed_features "
        << "WHERE ticker_id = " << ticker_id
        << " AND timeframe = '" << timeframe << "'";

    if (start > 0) sql << " AND timestamp >= to_timestamp(" << start << ")";
    if (end > 0) sql << " AND timestamp < to_timestamp(" << end << ")";

    PGresult* res = impl_->exec(sql.str().c_str());
    if (PQresultStatus(res) != PGRES_TUPLES_OK) {
        std::string err = PQresultErrorMessage(res);
        PQclear(res);
        throw std::runtime_error("get_existing_feature_bar_ids failed: " + err);
    }

    std::set<int64_t> ids;
    for (int i = 0; i < PQntuples(res); i++) {
        ids.insert(std::stoll(PQgetvalue(res, i, 0)));
    }
    PQclear(res);
    return ids;
}


std::vector<Ticker> Database::get_active_tickers() const {
    std::lock_guard<std::mutex> lock(impl_->mtx);

    PGresult* res = impl_->exec(
        "SELECT id, symbol FROM tickers WHERE is_active = true ORDER BY symbol");
    if (PQresultStatus(res) != PGRES_TUPLES_OK) {
        std::string err = PQresultErrorMessage(res);
        PQclear(res);
        throw std::runtime_error("get_active_tickers failed: " + err);
    }

    std::vector<Ticker> tickers;
    for (int i = 0; i < PQntuples(res); i++) {
        tickers.push_back({std::stoll(PQgetvalue(res, i, 0)), PQgetvalue(res, i, 1)});
    }
    PQclear(res);
    return tickers;
}


Ticker Database::get_ticker(const std::string& symbol) const {
    std::lock_guard<std::mutex> lock(impl_->mtx);

    const char* params[] = {symbol.c_str()};
    PGresult* res = impl_->exec_params(
        "SELECT id, symbol FROM tickers WHERE symbol = $1", 1, params);

    Ticker t{0, ""};
    if (PQresultStatus(res) == PGRES_TUPLES_OK && PQntuples(res) > 0) {
        t.id = std::stoll(PQgetvalue(res, 0, 0));
        t.symbol = PQgetvalue(res, 0, 1);
    }
    PQclear(res);
    return t;
}


int Database::batch_upsert_features(
    const std::vector<IndicatorResult>& results,
    int64_t ticker_id,
    const std::string& timeframe,
    const std::string& feature_version) const
{
    if (results.empty()) return 0;

    std::lock_guard<std::mutex> lock(impl_->mtx);
    impl_->ensure_connected();

    // Build multi-row INSERT ... ON CONFLICT
    std::ostringstream sql;
    sql << "INSERT INTO computed_features (bar_id, ticker_id, timeframe, timestamp, features, feature_version, created_at) "
        << "VALUES ";

    bool first = true;
    for (const auto& r : results) {
        std::string features_json = build_features_json(r.features);
        if (!first) sql << ", ";
        first = false;

        sql << "(" << r.bar_id
            << ", " << ticker_id
            << ", '" << timeframe << "'"
            << ", (SELECT timestamp FROM ohlcv_bars WHERE id = " << r.bar_id << ")"
            << ", '" << features_json << "'::jsonb"
            << ", '" << feature_version << "'"
            << ", NOW()"
            << ")";
    }

    sql << " ON CONFLICT (bar_id) DO UPDATE SET "
        << "features = EXCLUDED.features, "
        << "feature_version = EXCLUDED.feature_version";

    PGresult* res = impl_->exec(sql.str().c_str());
    ExecStatusType status = PQresultStatus(res);
    if (status != PGRES_COMMAND_OK) {
        std::string err = PQresultErrorMessage(res);
        PQclear(res);
        spdlog::error("batch_upsert_features failed: {}", err);
        return 0;
    }

    int affected = std::atoi(PQcmdTuples(res));
    PQclear(res);
    spdlog::debug("Upserted {} feature rows for ticker_id={} timeframe={}", affected, ticker_id, timeframe);
    return affected;
}


bool Database::health_check() const {
    std::lock_guard<std::mutex> lock(impl_->mtx);
    return impl_->conn && PQstatus(impl_->conn) == CONNECTION_OK;
}

} // namespace ie
