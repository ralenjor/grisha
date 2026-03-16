cmake_minimum_required(VERSION 3.15)
project(grisha_bm25 VERSION 0.1.0 LANGUAGES CXX)

# C++17 required for std::filesystem
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Release by default
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Compiler flags
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG -march=native")
    set(CMAKE_CXX_FLAGS_DEBUG "-g -O0 -Wall -Wextra -Wpedantic")
endif()

if(MSVC)
    set(CMAKE_CXX_FLAGS_RELEASE "/O2 /DNDEBUG")
    set(CMAKE_CXX_FLAGS_DEBUG "/Zi /Od /Wall")
endif()

# Find pybind11
find_package(pybind11 CONFIG REQUIRED)

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)

# Source files
set(SOURCES
    src/tokenizer.cpp
    src/posting_list.cpp
    src/bm25_index.cpp
    src/mmap_storage.cpp
    src/hybrid_search.cpp
    src/bindings.cpp
)

# Create the Python module
pybind11_add_module(grisha_bm25 ${SOURCES})

# Link libraries
if(UNIX AND NOT APPLE)
    target_link_libraries(grisha_bm25 PRIVATE pthread)
endif()

# Install target
install(TARGETS grisha_bm25 DESTINATION .)
