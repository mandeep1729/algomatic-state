#pragma once

#include <string>
#include <unordered_map>

namespace ie {

/// Build a PostgreSQL JSONB-compatible string from a features map.
/// Skips NaN and Inf values (matches Python behaviour).
std::string build_features_json(const std::unordered_map<std::string, double>& features);

} // namespace ie
