# KARKAS - Theater-Level Military Simulation Platform
cmake_minimum_required(VERSION 3.20)
project(karkas VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Options
option(KARKAS_BUILD_TESTS "Build tests" ON)
option(KARKAS_BUILD_PYTHON_BINDINGS "Build Python bindings" ON)

# Fetch nlohmann/json for JSON serialization
include(FetchContent)
FetchContent_Declare(
    json
    URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
)
FetchContent_MakeAvailable(json)

# Fetch yaml-cpp for YAML parsing
FetchContent_Declare(
    yaml-cpp
    GIT_REPOSITORY https://github.com/jbeder/yaml-cpp.git
    GIT_TAG 0.8.0
)
set(YAML_CPP_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(YAML_CPP_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(yaml-cpp)

# Find required packages
find_package(PkgConfig REQUIRED)
pkg_check_modules(GDAL REQUIRED gdal)
find_package(PostgreSQL REQUIRED)
find_package(Threads REQUIRED)

# Optional: pybind11 for Python bindings
if(KARKAS_BUILD_PYTHON_BINDINGS)
    find_package(pybind11 CONFIG)
endif()

# Include directories
include_directories(
    ${CMAKE_SOURCE_DIR}/server/core
    ${GDAL_INCLUDE_DIRS}
    ${PostgreSQL_INCLUDE_DIRS}
)

# Core library sources
set(CORE_SOURCES
    server/core/unit.cpp
    server/core/terrain/terrain_engine.cpp
    server/core/terrain/los_calculator.cpp
    server/core/terrain/mobility.cpp
    server/core/combat/combat_resolver.cpp
    server/core/combat/engagement.cpp
    server/core/movement/pathfinder.cpp
    server/core/movement/movement_resolver.cpp
    server/core/sensors/sensor_model.cpp
    server/core/sensors/detection.cpp
    server/core/logistics/supply_model.cpp
    server/core/simulation.cpp
    server/core/game_state.cpp
    server/core/turn_executor.cpp
    server/core/perception_generator.cpp
    server/core/orbat_manager.cpp
)

# Core library
add_library(karkas_core STATIC ${CORE_SOURCES})
set_property(TARGET karkas_core PROPERTY POSITION_INDEPENDENT_CODE ON)
target_link_libraries(karkas_core
    ${GDAL_LIBRARIES}
    ${PostgreSQL_LIBRARIES}
    Threads::Threads
    nlohmann_json::nlohmann_json
    yaml-cpp::yaml-cpp
)
target_include_directories(karkas_core PUBLIC
    ${GDAL_INCLUDE_DIRS}
    ${PostgreSQL_INCLUDE_DIRS}
)
target_compile_definitions(karkas_core PUBLIC KARKAS_HAS_GDAL)

# Python bindings
if(KARKAS_BUILD_PYTHON_BINDINGS AND pybind11_FOUND)
    pybind11_add_module(karkas_engine
        server/core/python_bindings.cpp
    )
    target_link_libraries(karkas_engine PRIVATE karkas_core)
    target_compile_definitions(karkas_engine PRIVATE KARKAS_BUILD_PYTHON_BINDINGS)
endif()

# Tests
if(KARKAS_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

# Install targets
install(TARGETS karkas_core
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)
