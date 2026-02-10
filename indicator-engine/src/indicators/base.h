#pragma once

#include <cmath>
#include <cstdint>
#include <ctime>
#include <string>
#include <unordered_map>
#include <vector>

namespace ie {

constexpr double EPS = 1e-9;
constexpr double NaN = std::numeric_limits<double>::quiet_NaN();

struct OHLCVBar {
    int64_t id;         // bar PK from DB
    int64_t ticker_id;
    double open, high, low, close;
    int64_t volume;
    time_t timestamp;   // UTC epoch
};

struct IndicatorResult {
    int64_t bar_id;
    std::unordered_map<std::string, double> features;
};

// ---------------------------------------------------------------------------
// Math utilities (mirrors src/features/base.py)
// ---------------------------------------------------------------------------

inline double safe_divide(double num, double den) {
    return num / (den + EPS);
}

inline bool is_valid(double v) {
    return std::isfinite(v);
}

/// Log return: ln(close[i] / close[i-periods])
inline double log_return(double current, double lagged) {
    if (lagged <= 0.0 || current <= 0.0) return NaN;
    return std::log(current / lagged);
}

/// Exponential moving average (recursive form)
/// alpha = 2.0 / (span + 1)
struct EmaState {
    double value = NaN;
    double alpha = 0.0;
    bool initialized = false;

    void init(int span) {
        alpha = 2.0 / (span + 1.0);
        initialized = false;
        value = NaN;
    }

    double update(double x) {
        if (!is_valid(x)) return value;
        if (!initialized) {
            value = x;
            initialized = true;
        } else {
            value = alpha * x + (1.0 - alpha) * value;
        }
        return value;
    }
};

/// Rolling statistics helper
struct RollingStats {
    std::vector<double> buf;
    int window = 0;
    int pos = 0;
    int count = 0;
    double sum = 0.0;
    double sq_sum = 0.0;

    void init(int w) {
        window = w;
        buf.assign(w, 0.0);
        pos = 0;
        count = 0;
        sum = 0.0;
        sq_sum = 0.0;
    }

    void push(double x) {
        if (count >= window) {
            double old = buf[pos];
            sum -= old;
            sq_sum -= old * old;
        } else {
            count++;
        }
        buf[pos] = x;
        sum += x;
        sq_sum += x * x;
        pos = (pos + 1) % window;
    }

    bool full() const { return count >= window; }

    double mean() const {
        if (count == 0) return NaN;
        return sum / count;
    }

    double variance() const {
        if (count < 2) return NaN;
        double m = mean();
        return (sq_sum / count) - m * m;
    }

    double std_dev() const {
        double v = variance();
        return (v >= 0.0) ? std::sqrt(v) : NaN;
    }

    double zscore(double x) const {
        if (!full()) return NaN;
        double sd = std_dev();
        double m = mean();
        return safe_divide(x - m, sd);
    }
};

/// Rolling sum helper
struct RollingSum {
    std::vector<double> buf;
    int window = 0;
    int pos = 0;
    int count = 0;
    double total = 0.0;

    void init(int w) {
        window = w;
        buf.assign(w, 0.0);
        pos = 0;
        count = 0;
        total = 0.0;
    }

    void push(double x) {
        if (count >= window) {
            total -= buf[pos];
        } else {
            count++;
        }
        buf[pos] = x;
        total += x;
        pos = (pos + 1) % window;
    }

    bool full() const { return count >= window; }
    double sum() const { return total; }
    double mean() const { return count > 0 ? total / count : NaN; }
};

/// Rolling max helper
struct RollingMax {
    std::vector<double> buf;
    int window = 0;
    int pos = 0;
    int count = 0;

    void init(int w) {
        window = w;
        buf.assign(w, -std::numeric_limits<double>::infinity());
        pos = 0;
        count = 0;
    }

    void push(double x) {
        if (count < window) count++;
        buf[pos] = x;
        pos = (pos + 1) % window;
    }

    bool full() const { return count >= window; }

    double max_val() const {
        double mx = -std::numeric_limits<double>::infinity();
        int n = std::min(count, window);
        for (int i = 0; i < n; i++) {
            if (buf[i] > mx) mx = buf[i];
        }
        return mx;
    }
};

/// Rolling min helper
struct RollingMin {
    std::vector<double> buf;
    int window = 0;
    int pos = 0;
    int count = 0;

    void init(int w) {
        window = w;
        buf.assign(w, std::numeric_limits<double>::infinity());
        pos = 0;
        count = 0;
    }

    void push(double x) {
        if (count < window) count++;
        buf[pos] = x;
        pos = (pos + 1) % window;
    }

    bool full() const { return count >= window; }

    double min_val() const {
        double mn = std::numeric_limits<double>::infinity();
        int n = std::min(count, window);
        for (int i = 0; i < n; i++) {
            if (buf[i] < mn) mn = buf[i];
        }
        return mn;
    }
};

/// Linear regression slope over a rolling window
struct RollingSlope {
    std::vector<double> buf;
    int window = 0;
    int pos = 0;
    int count = 0;

    void init(int w) {
        window = w;
        buf.assign(w, 0.0);
        pos = 0;
        count = 0;
    }

    void push(double x) {
        if (count < window) count++;
        buf[pos] = x;
        pos = (pos + 1) % window;
    }

    bool full() const { return count >= window; }

    double slope() const {
        if (!full()) return NaN;
        int n = window;
        double x_mean = (n - 1.0) / 2.0;
        double y_mean = 0.0;
        for (int i = 0; i < n; i++) {
            int idx = (pos + i) % window;
            y_mean += buf[idx];
        }
        y_mean /= n;

        double num = 0.0, den = 0.0;
        for (int i = 0; i < n; i++) {
            int idx = (pos + i) % window;
            double dx = i - x_mean;
            num += dx * (buf[idx] - y_mean);
            den += dx * dx;
        }
        return (den > EPS) ? num / den : 0.0;
    }
};

} // namespace ie
