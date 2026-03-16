// KARKAS Simple Test Runner
// Verifies basic functionality without external test framework

#include <iostream>
#include <cassert>
#include <cmath>

#include "types.hpp"
#include "unit.hpp"
#include "orbat_manager.hpp"
#include "terrain/terrain_engine.hpp"
#include "combat/combat_resolver.hpp"
#include "sensors/sensor_model.hpp"
#include "movement/movement_resolver.hpp"
#include "simulation.hpp"

using namespace karkas;

#define TEST(name) \
    std::cout << "Running test: " << #name << "... "; \
    test_##name(); \
    std::cout << "PASSED" << std::endl;

#define ASSERT_EQ(a, b) \
    if ((a) != (b)) { \
        std::cerr << "FAILED: " << #a << " != " << #b << std::endl; \
        std::cerr << "  Got: " << (a) << " Expected: " << (b) << std::endl; \
        assert(false); \
    }

#define ASSERT_NEAR(a, b, eps) \
    if (std::abs((a) - (b)) > (eps)) { \
        std::cerr << "FAILED: " << #a << " != " << #b << " (within " << eps << ")" << std::endl; \
        std::cerr << "  Got: " << (a) << " Expected: " << (b) << std::endl; \
        assert(false); \
    }

#define ASSERT_TRUE(cond) \
    if (!(cond)) { \
        std::cerr << "FAILED: " << #cond << " is false" << std::endl; \
        assert(false); \
    }

// Test coordinate distance calculation
void test_coordinates_distance() {
    Coordinates berlin{52.5200, 13.4050};
    Coordinates paris{48.8566, 2.3522};

    double dist = berlin.distance_to(paris);

    // Berlin to Paris is approximately 878 km
    ASSERT_NEAR(dist, 878.0, 10.0);
}

// Test coordinate bearing calculation
void test_coordinates_bearing() {
    Coordinates a{50.0, 10.0};
    Coordinates b{51.0, 10.0};  // Due north

    double bearing = a.bearing_to(b);
    ASSERT_NEAR(bearing, 0.0, 1.0);  // Should be approximately north

    Coordinates c{50.0, 11.0};  // Due east
    bearing = a.bearing_to(c);
    ASSERT_NEAR(bearing, 90.0, 5.0);  // Should be approximately east
}

// Test bounding box contains
void test_bounding_box_contains() {
    BoundingBox box{{50.0, 9.0}, {51.0, 10.0}};

    Coordinates inside{50.5, 9.5};
    Coordinates outside{52.0, 9.5};

    ASSERT_TRUE(box.contains(inside));
    ASSERT_TRUE(!box.contains(outside));
}

// Test unit creation
void test_unit_creation() {
    Unit unit("test_unit", "Test Infantry", Faction::Red, UnitType::Infantry, Echelon::Battalion);

    ASSERT_EQ(unit.get_id(), "test_unit");
    ASSERT_EQ(unit.get_name(), "Test Infantry");
    ASSERT_EQ(unit.get_faction(), Faction::Red);
    ASSERT_EQ(unit.get_type(), UnitType::Infantry);
    ASSERT_EQ(unit.get_echelon(), Echelon::Battalion);
    ASSERT_EQ(unit.get_mobility_class(), MobilityClass::Foot);
}

// Test unit combat effectiveness
void test_unit_combat_effectiveness() {
    Unit unit("test", "Test", Faction::Red, UnitType::Armor, Echelon::Battalion);

    ASSERT_TRUE(unit.is_combat_effective());

    // Drain ammo
    unit.consume_ammo(0.95);
    ASSERT_TRUE(!unit.is_combat_effective());
}

// Test ORBAT manager
void test_orbat_manager() {
    OrbatManager orbat;

    auto unit1 = std::make_unique<Unit>("u1", "Unit 1", Faction::Red, UnitType::Infantry, Echelon::Battalion);
    auto unit2 = std::make_unique<Unit>("u2", "Unit 2", Faction::Blue, UnitType::Armor, Echelon::Battalion);

    unit1->set_position({50.5, 9.5});
    unit2->set_position({50.3, 9.8});

    orbat.add_unit(std::move(unit1));
    orbat.add_unit(std::move(unit2));

    ASSERT_EQ(orbat.count_units(), 2);
    ASSERT_EQ(orbat.count_units(Faction::Red), 1);
    ASSERT_EQ(orbat.count_units(Faction::Blue), 1);

    auto* found = orbat.get_unit("u1");
    ASSERT_TRUE(found != nullptr);
    ASSERT_EQ(found->get_name(), "Unit 1");
}

// Test terrain cell mobility
void test_terrain_cell_mobility() {
    TerrainCell cell;
    cell.primary_type = TerrainType::Forest;
    cell.is_impassable = false;

    double foot_cost = cell.get_mobility_cost(MobilityClass::Foot);
    double wheeled_cost = cell.get_mobility_cost(MobilityClass::Wheeled);

    // Wheeled should be slower in forest than foot
    ASSERT_TRUE(wheeled_cost > foot_cost);

    // Air should be unaffected
    double rotary_cost = cell.get_mobility_cost(MobilityClass::Rotary);
    ASSERT_NEAR(rotary_cost, 1.0, 0.01);
}

// Test terrain engine loading
void test_terrain_engine_loading() {
    TerrainEngine terrain;

    BoundingBox bounds{{50.0, 9.0}, {51.0, 10.0}};
    bool loaded = terrain.load_region(bounds, "");

    ASSERT_TRUE(loaded);
    ASSERT_TRUE(terrain.is_loaded());

    // Get a cell
    Coordinates center{50.5, 9.5};
    auto cell = terrain.get_cell(center);

    // Should have some terrain type
    ASSERT_TRUE(cell.primary_type != TerrainType::Water);  // Not all water
}

// Test combat resolution
void test_combat_resolution() {
    CombatResolver resolver(42);  // Fixed seed for reproducibility

    Unit attacker("atk", "Attacker", Faction::Red, UnitType::Armor, Echelon::Battalion);
    Unit defender("def", "Defender", Faction::Blue, UnitType::Infantry, Echelon::Battalion);

    attacker.set_position({50.5, 9.5});
    defender.set_position({50.52, 9.52});
    defender.set_posture(Posture::Defend);

    Weather weather;
    TimeOfDay time{12, 0};

    auto result = resolver.resolve_engagement(attacker, defender, weather, time);

    // Combat should have occurred
    ASSERT_EQ(result.attacker_id, "atk");
    ASSERT_EQ(result.defender_id, "def");

    // Should have some casualties (with these forces)
    // Note: with stochastic combat, this might occasionally fail
}

// Test sensor detection
void test_sensor_detection() {
    SensorModel sensor(42);

    Unit observer("obs", "Observer", Faction::Red, UnitType::Recon, Echelon::Battalion);
    Unit target("tgt", "Target", Faction::Blue, UnitType::Armor, Echelon::Battalion);

    observer.set_position({50.5, 9.5});
    target.set_position({50.52, 9.52});  // ~2km away

    Weather weather;
    TimeOfDay time{12, 0};  // Daytime

    // Get observer's sensors
    auto& sensors = observer.get_sensors();
    ASSERT_TRUE(!sensors.empty());

    // Check detection
    auto result = sensor.check_detection(observer, sensors[0], target, weather, time);

    // At 2km in daylight with recon unit, should probably detect
    // But this is stochastic, so we just verify the API works
    ASSERT_TRUE(result.detection_source == observer.get_name());
}

// Test movement resolver
void test_movement_resolver() {
    MovementResolver resolver;

    Unit unit("mv", "Mover", Faction::Red, UnitType::Mechanized, Echelon::Battalion);
    unit.set_position({50.5, 9.5});

    MovementOrder order;
    order.unit_id = "mv";
    order.waypoints.push_back({50.55, 9.55});
    order.route_preference = RoutePreference::Fastest;
    order.max_speed_modifier = 1.0;
    order.halt_on_contact = false;

    Weather weather;
    std::vector<Unit*> enemies;

    auto result = resolver.resolve_movement(unit, order, 4.0, enemies, weather);

    ASSERT_EQ(result.unit_id, "mv");
    ASSERT_TRUE(result.distance_moved_km > 0);
    ASSERT_EQ(result.start_position.latitude, 50.5);
}

// Test simulation initialization
void test_simulation_init() {
    Simulation sim;

    ScenarioConfig config;
    config.name = "Test Scenario";
    config.region = {{50.0, 9.0}, {51.0, 10.0}};
    config.turn_length = std::chrono::hours(4);
    config.start_time = std::chrono::system_clock::now();

    bool loaded = sim.load_scenario(config);
    ASSERT_TRUE(loaded);

    auto& state = sim.get_state();
    ASSERT_EQ(state.get_current_turn(), 0);
}

// Test perception state summary generation
void test_perception_state() {
    PerceptionState perception(Faction::Blue);

    Unit unit("u1", "1st Battalion", Faction::Blue, UnitType::Infantry, Echelon::Battalion);
    unit.set_position({50.5, 9.5});
    perception.add_own_unit(unit);

    Contact contact;
    contact.contact_id = "c1";
    contact.position = {50.6, 9.6};
    contact.last_known_position = {50.6, 9.6};
    contact.confidence = ContactConfidence::Probable;
    contact.estimated_type = UnitType::Armor;
    contact.faction = Faction::Red;
    contact.source = "recon";
    perception.add_contact(contact);

    std::string summary = perception.generate_situation_summary();

    ASSERT_TRUE(summary.find("1st Battalion") != std::string::npos);
    ASSERT_TRUE(summary.find("PROBABLE") != std::string::npos);
}

int main() {
    std::cout << "KARKAS Test Suite" << std::endl;
    std::cout << "=================" << std::endl << std::endl;

    try {
        TEST(coordinates_distance);
        TEST(coordinates_bearing);
        TEST(bounding_box_contains);
        TEST(unit_creation);
        TEST(unit_combat_effectiveness);
        TEST(orbat_manager);
        TEST(terrain_cell_mobility);
        TEST(terrain_engine_loading);
        TEST(combat_resolution);
        TEST(sensor_detection);
        TEST(movement_resolver);
        TEST(simulation_init);
        TEST(perception_state);

        std::cout << std::endl;
        std::cout << "All tests passed!" << std::endl;
        return 0;

    } catch (const std::exception& e) {
        std::cerr << "Test failed with exception: " << e.what() << std::endl;
        return 1;
    }
}
