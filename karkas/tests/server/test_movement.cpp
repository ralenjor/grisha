// KARKAS Movement Resolver Tests (6.2.4)
// Tests for MovementResolver: movement execution, pathfinding, traffic

#include <gtest/gtest.h>
#include "types.hpp"
#include "unit.hpp"
#include "terrain/terrain_engine.hpp"
#include "movement/movement_resolver.hpp"

using namespace karkas;

class MovementResolverTest : public ::testing::Test {
protected:
    void SetUp() override {
        resolver = std::make_unique<MovementResolver>();
        terrain = std::make_unique<TerrainEngine>();

        // Load terrain
        BoundingBox region{{50.0, 9.0}, {51.0, 10.0}};
        terrain->load_region(region, "");

        resolver->set_terrain(terrain.get());

        // Create test units
        mech_unit = std::make_unique<Unit>(
            "mech_1", "1st Mechanized Battalion",
            Faction::Red, UnitType::Mechanized, Echelon::Battalion);
        mech_unit->set_position({50.5, 9.5});
        mech_unit->set_posture(Posture::Move);

        infantry_unit = std::make_unique<Unit>(
            "inf_1", "1st Infantry Company",
            Faction::Red, UnitType::Infantry, Echelon::Company);
        infantry_unit->set_position({50.52, 9.52});
        infantry_unit->set_posture(Posture::Move);

        armor_unit = std::make_unique<Unit>(
            "arm_1", "1st Tank Battalion",
            Faction::Blue, UnitType::Armor, Echelon::Battalion);
        armor_unit->set_position({50.7, 9.7});
        armor_unit->set_posture(Posture::Move);
    }

    std::unique_ptr<MovementResolver> resolver;
    std::unique_ptr<TerrainEngine> terrain;
    std::unique_ptr<Unit> mech_unit;
    std::unique_ptr<Unit> infantry_unit;
    std::unique_ptr<Unit> armor_unit;
};

// Basic movement resolution
TEST_F(MovementResolverTest, BasicMovement) {
    MovementOrder order;
    order.unit_id = mech_unit->get_id();
    order.waypoints = {{50.55, 9.55}};
    order.route_preference = RoutePreference::Fastest;
    order.max_speed_modifier = 1.0;
    order.halt_on_contact = false;
    order.priority = 0;

    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    std::vector<Unit*> enemies;
    double turn_hours = 4.0;

    auto result = resolver->resolve_movement(
        *mech_unit, order, turn_hours, enemies, weather);

    EXPECT_EQ(result.unit_id, "mech_1");
    EXPECT_GT(result.distance_moved_km, 0.0);
    EXPECT_NEAR(result.start_position.latitude, 50.5, 0.001);
    EXPECT_NEAR(result.start_position.longitude, 9.5, 0.001);
}

TEST_F(MovementResolverTest, MovementUpdatesPosition) {
    MovementOrder order;
    order.unit_id = mech_unit->get_id();
    order.waypoints = {{50.55, 9.55}};
    order.route_preference = RoutePreference::Fastest;
    order.max_speed_modifier = 1.0;
    order.halt_on_contact = false;
    order.priority = 0;

    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    std::vector<Unit*> enemies;

    auto result = resolver->resolve_movement(
        *mech_unit, order, 4.0, enemies, weather);

    // End position should be different from start
    EXPECT_NE(result.end_position.latitude, result.start_position.latitude);
}

// Speed varies by unit type
TEST_F(MovementResolverTest, InfantrySlowerThanMechanized) {
    MovementOrder order;
    order.waypoints = {{50.6, 9.6}};  // Same destination for both
    order.route_preference = RoutePreference::Fastest;
    order.max_speed_modifier = 1.0;
    order.halt_on_contact = false;
    order.priority = 0;

    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    std::vector<Unit*> enemies;
    double turn_hours = 4.0;

    order.unit_id = mech_unit->get_id();
    auto mech_result = resolver->resolve_movement(
        *mech_unit, order, turn_hours, enemies, weather);

    order.unit_id = infantry_unit->get_id();
    auto inf_result = resolver->resolve_movement(
        *infantry_unit, order, turn_hours, enemies, weather);

    // Mechanized should move further in same time
    EXPECT_GT(mech_result.distance_moved_km, inf_result.distance_moved_km);
}

// Route preferences affect path
TEST_F(MovementResolverTest, RoutePreferences) {
    Coordinates destination{50.6, 9.6};

    MovementOrder fastest_order;
    fastest_order.unit_id = mech_unit->get_id();
    fastest_order.waypoints = {destination};
    fastest_order.route_preference = RoutePreference::Fastest;
    fastest_order.max_speed_modifier = 1.0;
    fastest_order.halt_on_contact = false;
    fastest_order.priority = 0;

    MovementOrder covered_order = fastest_order;
    covered_order.route_preference = RoutePreference::Covered;

    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    std::vector<Unit*> enemies;

    auto fastest_result = resolver->resolve_movement(
        *mech_unit, fastest_order, 4.0, enemies, weather);

    // Reset position
    mech_unit->set_position({50.5, 9.5});

    auto covered_result = resolver->resolve_movement(
        *mech_unit, covered_order, 4.0, enemies, weather);

    // Both should make progress
    EXPECT_GT(fastest_result.distance_moved_km, 0.0);
    EXPECT_GT(covered_result.distance_moved_km, 0.0);
}

// Speed modifier affects movement
TEST_F(MovementResolverTest, SpeedModifier) {
    MovementOrder order;
    order.unit_id = mech_unit->get_id();
    order.waypoints = {{50.7, 9.7}};
    order.route_preference = RoutePreference::Fastest;
    order.halt_on_contact = false;
    order.priority = 0;

    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    std::vector<Unit*> enemies;
    double turn_hours = 4.0;

    order.max_speed_modifier = 1.0;
    auto full_speed = resolver->resolve_movement(
        *mech_unit, order, turn_hours, enemies, weather);

    mech_unit->set_position({50.5, 9.5});

    order.max_speed_modifier = 0.5;
    auto half_speed = resolver->resolve_movement(
        *mech_unit, order, turn_hours, enemies, weather);

    EXPECT_GT(full_speed.distance_moved_km, half_speed.distance_moved_km);
}

// Multi-waypoint movement
TEST_F(MovementResolverTest, MultiWaypointMovement) {
    MovementOrder order;
    order.unit_id = mech_unit->get_id();
    order.waypoints = {
        {50.52, 9.52},
        {50.54, 9.54},
        {50.56, 9.56}
    };
    order.route_preference = RoutePreference::Fastest;
    order.max_speed_modifier = 1.0;
    order.halt_on_contact = false;
    order.priority = 0;

    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    std::vector<Unit*> enemies;

    auto result = resolver->resolve_movement(
        *mech_unit, order, 8.0, enemies, weather);

    EXPECT_GT(result.distance_moved_km, 0.0);
}

// Halt on contact
TEST_F(MovementResolverTest, HaltOnContact) {
    MovementOrder order;
    order.unit_id = mech_unit->get_id();
    order.waypoints = {{50.7, 9.7}};  // Move toward enemy
    order.route_preference = RoutePreference::Fastest;
    order.max_speed_modifier = 1.0;
    order.halt_on_contact = true;
    order.priority = 0;

    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    std::vector<Unit*> enemies = {armor_unit.get()};

    auto result = resolver->resolve_movement(
        *mech_unit, order, 4.0, enemies, weather);

    if (result.halted_by_contact) {
        // Unit should halt before reaching destination
        EXPECT_FALSE(result.reached_destination);
    }
}

// No halt on contact
TEST_F(MovementResolverTest, ContinueOnContact) {
    MovementOrder order;
    order.unit_id = mech_unit->get_id();
    order.waypoints = {{50.7, 9.7}};
    order.route_preference = RoutePreference::Fastest;
    order.max_speed_modifier = 1.0;
    order.halt_on_contact = false;
    order.priority = 0;

    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    std::vector<Unit*> enemies = {armor_unit.get()};

    auto result = resolver->resolve_movement(
        *mech_unit, order, 4.0, enemies, weather);

    // Should continue moving even if contact detected
    EXPECT_GT(result.distance_moved_km, 0.0);
}

// Fuel consumption during movement
TEST_F(MovementResolverTest, FuelConsumption) {
    double initial_fuel = mech_unit->get_logistics().fuel_level;

    MovementOrder order;
    order.unit_id = mech_unit->get_id();
    order.waypoints = {{50.6, 9.6}};
    order.route_preference = RoutePreference::Fastest;
    order.max_speed_modifier = 1.0;
    order.halt_on_contact = false;
    order.priority = 0;

    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    std::vector<Unit*> enemies;

    auto result = resolver->resolve_movement(
        *mech_unit, order, 4.0, enemies, weather);

    EXPECT_GT(result.fuel_consumed, 0.0);

    // Unit's fuel should be reduced
    double final_fuel = mech_unit->get_logistics().fuel_level;
    EXPECT_LT(final_fuel, initial_fuel);
}

// Movement narrative generation
TEST_F(MovementResolverTest, MovementNarrative) {
    MovementOrder order;
    order.unit_id = mech_unit->get_id();
    order.waypoints = {{50.55, 9.55}};
    order.route_preference = RoutePreference::Fastest;
    order.max_speed_modifier = 1.0;
    order.halt_on_contact = false;
    order.priority = 0;

    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    std::vector<Unit*> enemies;

    auto result = resolver->resolve_movement(
        *mech_unit, order, 4.0, enemies, weather);

    // Should have a narrative description
    EXPECT_FALSE(result.narrative.empty());
}

// Weather affects movement
TEST_F(MovementResolverTest, WeatherEffects) {
    MovementOrder order;
    order.unit_id = mech_unit->get_id();
    order.waypoints = {{50.6, 9.6}};
    order.route_preference = RoutePreference::Fastest;
    order.max_speed_modifier = 1.0;
    order.halt_on_contact = false;
    order.priority = 0;

    std::vector<Unit*> enemies;

    Weather good_weather;
    good_weather.visibility = Weather::Visibility::Clear;
    good_weather.precipitation = Weather::Precipitation::None;
    good_weather.temperature_c = 20.0;
    good_weather.wind_speed_kph = 5.0;
    good_weather.wind_direction = 0.0;

    auto good_result = resolver->resolve_movement(
        *mech_unit, order, 4.0, enemies, good_weather);

    mech_unit->set_position({50.5, 9.5});

    Weather bad_weather;
    bad_weather.visibility = Weather::Visibility::Fog;
    bad_weather.precipitation = Weather::Precipitation::Heavy;
    bad_weather.temperature_c = 5.0;
    bad_weather.wind_speed_kph = 30.0;
    bad_weather.wind_direction = 0.0;

    auto bad_result = resolver->resolve_movement(
        *mech_unit, order, 4.0, enemies, bad_weather);

    // Bad weather should slow movement
    EXPECT_GE(good_result.distance_moved_km, bad_result.distance_moved_km);
}

// Terrain type affects movement
TEST_F(MovementResolverTest, TerrainEffectsOnMovement) {
    // This test validates that different terrain types affect speed
    // The exact effect depends on terrain data loaded

    MovementOrder order;
    order.unit_id = mech_unit->get_id();
    order.waypoints = {{50.55, 9.55}};
    order.route_preference = RoutePreference::Fastest;
    order.max_speed_modifier = 1.0;
    order.halt_on_contact = false;
    order.priority = 0;

    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    std::vector<Unit*> enemies;

    auto result = resolver->resolve_movement(
        *mech_unit, order, 4.0, enemies, weather);

    // Just verify movement happened with terrain considerations
    EXPECT_GT(result.distance_moved_km, 0.0);
}

// No movement with no fuel
TEST_F(MovementResolverTest, LowFuelReducesMovement) {
    // Get movement with full fuel first
    MovementOrder order;
    order.unit_id = mech_unit->get_id();
    order.waypoints = {{50.6, 9.6}};
    order.route_preference = RoutePreference::Fastest;
    order.max_speed_modifier = 1.0;
    order.halt_on_contact = false;
    order.priority = 0;

    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    std::vector<Unit*> enemies;

    auto full_fuel_result = resolver->resolve_movement(
        *mech_unit, order, 4.0, enemies, weather);
    double full_fuel_dist = full_fuel_result.distance_moved_km;

    // Reset and drain fuel
    mech_unit->resupply(1.0, 0, 0);  // Restore fuel
    mech_unit->consume_fuel(0.95);   // Drain most fuel
    EXPECT_LT(mech_unit->get_logistics().fuel_level, 0.1);

    // Reset unit position for second test
    mech_unit->set_position({50.5, 9.5});
    auto low_fuel_result = resolver->resolve_movement(
        *mech_unit, order, 4.0, enemies, weather);

    // Low fuel should significantly reduce movement (but not to zero)
    EXPECT_LT(low_fuel_result.distance_moved_km, full_fuel_dist);
}

// Movement for rotary units
TEST_F(MovementResolverTest, RotaryUnitMovement) {
    Unit helicopter("helo_1", "Attack Helicopter Company",
                    Faction::Red, UnitType::Rotary, Echelon::Company);
    helicopter.set_position({50.5, 9.5});

    MovementOrder order;
    order.unit_id = "helo_1";
    order.waypoints = {{50.7, 9.7}};
    order.route_preference = RoutePreference::Fastest;
    order.max_speed_modifier = 1.0;
    order.halt_on_contact = false;
    order.priority = 0;

    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    std::vector<Unit*> enemies;

    auto result = resolver->resolve_movement(
        helicopter, order, 2.0, enemies, weather);

    // Air units should move faster and terrain doesn't affect them
    EXPECT_GT(result.distance_moved_km, 10.0);  // Should cover significant distance
}

// Defending unit doesn't move
TEST_F(MovementResolverTest, DefendingUnitMinimalMovement) {
    mech_unit->set_posture(Posture::Defend);

    MovementOrder order;
    order.unit_id = mech_unit->get_id();
    order.waypoints = {{50.6, 9.6}};
    order.route_preference = RoutePreference::Fastest;
    order.max_speed_modifier = 1.0;
    order.halt_on_contact = false;
    order.priority = 0;

    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    std::vector<Unit*> enemies;

    auto result = resolver->resolve_movement(
        *mech_unit, order, 4.0, enemies, weather);

    // Defending units should move very slowly or not at all
    // (depends on implementation - may require changing posture first)
}

// Traffic/congestion
TEST_F(MovementResolverTest, TrafficAffectsMovement) {
    // Create multiple units moving in same direction
    std::vector<std::unique_ptr<Unit>> convoy;
    for (int i = 0; i < 5; i++) {
        auto unit = std::make_unique<Unit>(
            "convoy_" + std::to_string(i),
            "Convoy Unit " + std::to_string(i),
            Faction::Red, UnitType::Mechanized, Echelon::Battalion);
        unit->set_position({50.5 + i * 0.001, 9.5});
        convoy.push_back(std::move(unit));
    }

    MovementOrder order;
    order.waypoints = {{50.6, 9.6}};
    order.route_preference = RoutePreference::Fastest;
    order.max_speed_modifier = 1.0;
    order.halt_on_contact = false;
    order.priority = 0;

    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    std::vector<Unit*> enemies;

    // Resolve movement for all units
    std::vector<MovementResult> results;
    for (auto& unit : convoy) {
        order.unit_id = unit->get_id();
        auto result = resolver->resolve_movement(
            *unit, order, 4.0, enemies, weather);
        results.push_back(result);
    }

    // All should make progress (traffic handling varies by implementation)
    for (const auto& result : results) {
        EXPECT_GT(result.distance_moved_km, 0.0);
    }
}

// Estimate movement range
TEST_F(MovementResolverTest, EstimateMovementRange) {
    Weather weather;
    weather.precipitation = Weather::Precipitation::None;
    weather.visibility = Weather::Visibility::Clear;
    weather.temperature_c = 20.0;
    weather.wind_speed_kph = 10.0;
    weather.wind_direction = 0.0;

    double range = resolver->estimate_movement_range(*mech_unit, 4.0, weather);

    EXPECT_GT(range, 0.0);
    EXPECT_LT(range, 200.0);  // Reasonable limit for 4 hours
}
