cmake_minimum_required(VERSION 3.16)
project(indicator-engine VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# ---- Dependencies via FetchContent ----
include(FetchContent)

FetchContent_Declare(
    nlohmann_json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG        v3.11.3
    GIT_SHALLOW    TRUE
)

FetchContent_Declare(
    spdlog
    GIT_REPOSITORY https://github.com/gabime/spdlog.git
    GIT_TAG        v1.13.0
    GIT_SHALLOW    TRUE
)

FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG        v1.14.0
    GIT_SHALLOW    TRUE
)

FetchContent_MakeAvailable(nlohmann_json spdlog googletest)

# ---- gRPC and Protobuf ----
find_package(Protobuf REQUIRED)
find_package(gRPC REQUIRED)

# Generated proto sources (copied into build context by Dockerfile)
set(PROTO_GEN_DIR ${CMAKE_CURRENT_SOURCE_DIR}/proto_gen)

file(GLOB PROTO_SRCS ${PROTO_GEN_DIR}/*.pb.cc)
file(GLOB GRPC_SRCS ${PROTO_GEN_DIR}/*.grpc.pb.cc)

add_library(market_proto STATIC ${PROTO_SRCS} ${GRPC_SRCS})
target_include_directories(market_proto PUBLIC ${PROTO_GEN_DIR})
target_link_libraries(market_proto PUBLIC
    protobuf::libprotobuf
    gRPC::grpc++
)

# ---- System libraries ----
find_library(LIBHIREDIS hiredis REQUIRED)
find_library(LIBTALIB ta_lib NAMES ta_lib ta-lib)

find_path(HIREDIS_INCLUDE_DIR hiredis/hiredis.h)
find_path(TALIB_INCLUDE_DIR ta-lib/ta_libc.h ta_libc.h)

# ---- Main binary ----
add_executable(indicator-engine
    src/main.cpp
    src/config.cpp
    src/data_service_client.cpp
    src/redis_bus.cpp
    src/pipeline.cpp
    src/json_builder.cpp
    src/service.cpp
    src/indicators/talib_wrapper.cpp
    src/indicators/returns.cpp
    src/indicators/volatility.cpp
    src/indicators/volume.cpp
    src/indicators/intrabar.cpp
    src/indicators/anchor.cpp
    src/indicators/time_of_day.cpp
)

target_include_directories(indicator-engine PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${HIREDIS_INCLUDE_DIR}
    ${TALIB_INCLUDE_DIR}
)

target_link_libraries(indicator-engine PRIVATE
    nlohmann_json::nlohmann_json
    spdlog::spdlog
    market_proto
    ${LIBHIREDIS}
)

if(LIBTALIB)
    target_link_libraries(indicator-engine PRIVATE ${LIBTALIB})
    target_compile_definitions(indicator-engine PRIVATE HAS_TALIB=1)
endif()

# ---- Tests ----
enable_testing()

add_executable(indicator-engine-tests
    tests/test_indicators.cpp
    tests/test_pipeline.cpp
    src/indicators/returns.cpp
    src/indicators/volatility.cpp
    src/indicators/volume.cpp
    src/indicators/intrabar.cpp
    src/indicators/anchor.cpp
    src/indicators/time_of_day.cpp
    src/indicators/talib_wrapper.cpp
    src/pipeline.cpp
    src/json_builder.cpp
)

target_include_directories(indicator-engine-tests PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${TALIB_INCLUDE_DIR}
)

target_link_libraries(indicator-engine-tests PRIVATE
    GTest::gtest_main
    nlohmann_json::nlohmann_json
    spdlog::spdlog
)

if(LIBTALIB)
    target_link_libraries(indicator-engine-tests PRIVATE ${LIBTALIB})
    target_compile_definitions(indicator-engine-tests PRIVATE HAS_TALIB=1)
endif()

include(GoogleTest)
gtest_discover_tests(indicator-engine-tests)
