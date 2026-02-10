#include "json_builder.h"

#include <cmath>
#include <nlohmann/json.hpp>

namespace ie {

std::string build_features_json(const std::unordered_map<std::string, double>& features) {
    nlohmann::json j = nlohmann::json::object();

    for (const auto& [key, val] : features) {
        if (std::isfinite(val)) {
            j[key] = val;
        }
        // Skip NaN and Inf (matches Python behaviour of dropping non-finite values)
    }

    return j.dump();
}

} // namespace ie
