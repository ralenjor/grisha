# KARKAS Tests
enable_testing()

# Find Google Test
find_package(GTest QUIET)

if(GTest_FOUND)
    message(STATUS "Google Test found, building comprehensive test suite")

    # Unit tests with GTest
    add_executable(karkas_tests
        server/test_unit.cpp
        server/test_orbat_manager.cpp
        server/test_terrain.cpp
        server/test_movement.cpp
        server/test_sensors.cpp
        server/test_combat.cpp
        server/test_logistics.cpp
        server/test_simulation.cpp
    )

    target_link_libraries(karkas_tests
        karkas_core
        GTest::gtest
        GTest::gtest_main
    )

    # Use Google Test's test discovery
    include(GoogleTest)
    gtest_discover_tests(karkas_tests)
else()
    message(STATUS "Google Test not found, using simple test runner")

    # Simple test executable without GTest
    add_executable(karkas_simple_test
        server/simple_test.cpp
    )

    target_link_libraries(karkas_simple_test karkas_core)

    add_test(NAME karkas_simple_test COMMAND karkas_simple_test)
endif()
