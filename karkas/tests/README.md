# KARKAS Test Suite

This document describes how to build and run the C++ unit tests for the KARKAS simulation engine.

## Prerequisites

### Required Dependencies

- **CMake 3.20+** - Build system
- **C++20 compiler** - GCC 11+, Clang 14+, or MSVC 2022
- **Google Test** - Unit testing framework (optional but recommended)
- **GDAL** - Geospatial library
- **PostgreSQL** - Database client libraries

### Installing Google Test

**Fedora/RHEL:**
```bash
sudo dnf install gtest-devel
```

**Ubuntu/Debian:**
```bash
sudo apt install libgtest-dev
```

**macOS (Homebrew):**
```bash
brew install googletest
```

**From source:**
```bash
git clone https://github.com/google/googletest.git
cd googletest
mkdir build && cd build
cmake ..
make
sudo make install
```

## Building the Tests

### Standard Build

From the `karkas/` directory:

```bash
# Create build directory
mkdir -p build && cd build

# Configure with tests enabled (default)
cmake ..

# Build everything including tests
make -j$(nproc)
```

### Build Options

```bash
# Explicitly enable tests
cmake -DKARKAS_BUILD_TESTS=ON ..

# Disable tests
cmake -DKARKAS_BUILD_TESTS=OFF ..

# Debug build (recommended for testing)
cmake -DCMAKE_BUILD_TYPE=Debug ..

# Release build with debug info
cmake -DCMAKE_BUILD_TYPE=RelWithDebInfo ..
```

## Running the Tests

### Using CTest (Recommended)

CTest is CMake's test runner and provides the best integration:

```bash
cd build

# Run all tests
ctest

# Run with verbose output
ctest -V

# Run with extra verbose output (shows each test)
ctest --output-on-failure

# Run tests matching a pattern
ctest -R terrain      # Only terrain tests
ctest -R combat       # Only combat tests
ctest -R "unit|orbat" # Unit and ORBAT tests

# Run tests in parallel
ctest -j$(nproc)

# List available tests without running
ctest -N
```

### Running the Test Executable Directly

For more control over test execution:

```bash
cd build

# Run all tests
./tests/karkas_tests

# Run with Google Test options
./tests/karkas_tests --gtest_list_tests           # List all tests
./tests/karkas_tests --gtest_filter="*Terrain*"   # Filter by pattern
./tests/karkas_tests --gtest_repeat=10            # Repeat tests
./tests/karkas_tests --gtest_shuffle              # Randomize order
./tests/karkas_tests --gtest_output=xml:results.xml  # XML output
```

### Simple Test Runner (Fallback)

If Google Test is not installed, a simple test runner is built instead:

```bash
cd build
./tests/karkas_simple_test
```

## Test Suites

### Available Test Files

| Test File | Component | Description |
|-----------|-----------|-------------|
| `test_unit.cpp` | Unit class | Identification, hierarchy, logistics, morale, combat stats, sensors |
| `test_orbat_manager.cpp` | ORBAT Manager | Unit management, spatial queries, command chains |
| `test_terrain.cpp` | Terrain Engine | Loading, LOS, pathfinding, mobility, area analysis |
| `test_movement.cpp` | Movement Resolver | Movement execution, routes, fuel consumption |
| `test_sensors.cpp` | Sensor Model | Detection, EW effects, contact tracking |
| `test_combat.cpp` | Combat Resolver | Engagement, casualties, morale effects |
| `test_logistics.cpp` | Supply Model | Supply points, LOC, resupply, interdiction |
| `test_simulation.cpp` | Simulation | Scenario loading, turn execution, victory conditions |

### Running Specific Test Suites

```bash
# Run only unit tests
./tests/karkas_tests --gtest_filter="UnitTest.*"

# Run only terrain tests
./tests/karkas_tests --gtest_filter="TerrainEngineTest.*"

# Run only combat tests
./tests/karkas_tests --gtest_filter="CombatResolverTest.*"

# Run multiple suites
./tests/karkas_tests --gtest_filter="UnitTest.*:OrbatManagerTest.*"

# Exclude specific tests
./tests/karkas_tests --gtest_filter="-*Serialization*"
```

## Test Output Examples

### Successful Run

```
[==========] Running 215 tests from 12 test suites.
[----------] Global test environment set-up.
[----------] 30 tests from UnitTest
[ RUN      ] UnitTest.IdentificationAttributes
[       OK ] UnitTest.IdentificationAttributes (0 ms)
[ RUN      ] UnitTest.MobilityClassAssignment
[       OK ] UnitTest.MobilityClassAssignment (0 ms)
...
[----------] 30 tests from UnitTest (45 ms total)
[----------] Global test environment tear-down
[==========] 215 tests from 12 test suites ran. (1523 ms total)
[  PASSED  ] 215 tests.
```

### Failed Test

```
[ RUN      ] UnitTest.FuelConsumption
/home/user/karkas/tests/server/test_unit.cpp:95: Failure
Expected: (infantry->get_logistics().fuel_level) < (initial_fuel - 0.2)
  Actual: 0.8 vs 0.8
[  FAILED  ] UnitTest.FuelConsumption (1 ms)
```

## Debugging Failed Tests

### Run Single Failing Test

```bash
./tests/karkas_tests --gtest_filter="UnitTest.FuelConsumption" --gtest_break_on_failure
```

### With GDB

```bash
gdb ./tests/karkas_tests
(gdb) run --gtest_filter="UnitTest.FuelConsumption"
```

### With Valgrind (Memory Checks)

```bash
valgrind --leak-check=full ./tests/karkas_tests --gtest_filter="UnitTest.*"
```

### With AddressSanitizer

```bash
# Rebuild with sanitizers
cmake -DCMAKE_CXX_FLAGS="-fsanitize=address -g" ..
make -j$(nproc)
./tests/karkas_tests
```

## Continuous Integration

### GitHub Actions Example

```yaml
- name: Build and Test
  run: |
    mkdir build && cd build
    cmake -DCMAKE_BUILD_TYPE=Debug ..
    make -j$(nproc)
    ctest --output-on-failure
```

### Generate Test Reports

```bash
# JUnit XML format (for CI systems)
./tests/karkas_tests --gtest_output=xml:test_results.xml

# JSON format
./tests/karkas_tests --gtest_output=json:test_results.json
```

## Test Data Requirements

Some tests require terrain data to be present:

```bash
# Ensure Fulda Gap terrain is available
ls data/terrain/fulda_gap.gpkg

# If missing, tests will use synthetic terrain (slower but works)
```

## Writing New Tests

### Test File Template

```cpp
#include <gtest/gtest.h>
#include "types.hpp"
#include "your_component.hpp"

using namespace karkas;

class YourComponentTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Initialize test fixtures
    }

    void TearDown() override {
        // Cleanup (optional)
    }

    // Test fixtures
    std::unique_ptr<YourComponent> component;
};

TEST_F(YourComponentTest, BasicFunctionality) {
    EXPECT_TRUE(component->do_something());
    EXPECT_EQ(component->get_value(), 42);
}

TEST_F(YourComponentTest, EdgeCase) {
    ASSERT_NE(component, nullptr);
    EXPECT_THROW(component->invalid_operation(), std::runtime_error);
}
```

### Adding to Build

Edit `tests/CMakeLists.txt`:

```cmake
add_executable(karkas_tests
    server/test_unit.cpp
    server/test_your_component.cpp  # Add new file
    # ...
)
```

## Troubleshooting

### "Google Test not found"

The build will fall back to `karkas_simple_test`. Install Google Test or use:

```bash
# Force use of simple tests
cmake -DKARKAS_BUILD_TESTS=ON ..
```

### Tests fail to load terrain

```bash
# Check terrain file exists
ls -la data/terrain/fulda_gap.gpkg

# Tests will use synthetic terrain if file is missing
# This is slower but functional
```

### Linker errors

Ensure all dependencies are installed:

```bash
# Fedora
sudo dnf install gdal-devel postgresql-devel

# Ubuntu
sudo apt install libgdal-dev libpq-dev
```

### Slow tests

Some terrain tests can be slow. Run fast tests only:

```bash
./tests/karkas_tests --gtest_filter="-*Terrain*:-*Pathfinding*"
```

## Quick Reference

```bash
# Full test cycle
cd karkas
mkdir -p build && cd build
cmake -DCMAKE_BUILD_TYPE=Debug ..
make -j$(nproc)
ctest --output-on-failure

# Quick retest after code changes
make -j$(nproc) && ctest -j$(nproc)

# Test specific component
ctest -R combat -V

# Debug a failing test
./tests/karkas_tests --gtest_filter="FailingTest" --gtest_break_on_failure
```
