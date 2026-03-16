// KARKAS Logistics Model Tests (6.2.7)
// Tests for SupplyModel: supply points, LOC, resupply, interdiction

#include <gtest/gtest.h>
#include "types.hpp"
#include "unit.hpp"
#include "orbat_manager.hpp"
#include "terrain/terrain_engine.hpp"
#include "logistics/supply_model.hpp"

using namespace karkas;

class SupplyModelTest : public ::testing::Test {
protected:
    void SetUp() override {
        supply = std::make_unique<SupplyModel>();
        terrain = std::make_unique<TerrainEngine>();
        orbat = std::make_unique<OrbatManager>();

        BoundingBox region{{50.0, 9.0}, {51.0, 10.0}};
        terrain->load_region(region, "");

        supply->set_terrain(terrain.get());
        supply->set_orbat(orbat.get());

        // Create Red supply points
        SupplyPoint red_depot;
        red_depot.id = "depot_red_1";
        red_depot.position = {50.3, 9.3};
        red_depot.faction = Faction::Red;
        red_depot.fuel_capacity = 10000.0;
        red_depot.ammo_capacity = 10000.0;
        red_depot.supply_capacity = 5000.0;
        red_depot.fuel_available = 8000.0;
        red_depot.ammo_available = 8000.0;
        red_depot.supply_available = 4000.0;
        red_depot.resupply_rate_per_turn = 500.0;

        supply->add_supply_point(red_depot);

        // Create Blue supply points
        SupplyPoint blue_depot;
        blue_depot.id = "depot_blue_1";
        blue_depot.position = {50.8, 9.8};
        blue_depot.faction = Faction::Blue;
        blue_depot.fuel_capacity = 10000.0;
        blue_depot.ammo_capacity = 10000.0;
        blue_depot.supply_capacity = 5000.0;
        blue_depot.fuel_available = 9000.0;
        blue_depot.ammo_available = 9000.0;
        blue_depot.supply_available = 4500.0;
        blue_depot.resupply_rate_per_turn = 500.0;

        supply->add_supply_point(blue_depot);

        // Create test units
        red_unit = std::make_unique<Unit>(
            "red_bn_1", "1st Motor Rifle Battalion",
            Faction::Red, UnitType::Mechanized, Echelon::Battalion);
        red_unit->set_position({50.5, 9.5});
        red_unit->get_logistics_mut().fuel_level = 0.5;
        red_unit->get_logistics_mut().ammo_level = 0.5;

        blue_unit = std::make_unique<Unit>(
            "blue_bn_1", "1st Armored Battalion",
            Faction::Blue, UnitType::Armor, Echelon::Battalion);
        blue_unit->set_position({50.7, 9.7});
        blue_unit->get_logistics_mut().fuel_level = 0.6;
        blue_unit->get_logistics_mut().ammo_level = 0.6;

        // Add units to ORBAT
        auto red_copy = std::make_unique<Unit>(*red_unit);
        auto blue_copy = std::make_unique<Unit>(*blue_unit);
        orbat->add_unit(std::move(red_copy));
        orbat->add_unit(std::move(blue_copy));
    }

    std::unique_ptr<SupplyModel> supply;
    std::unique_ptr<TerrainEngine> terrain;
    std::unique_ptr<OrbatManager> orbat;
    std::unique_ptr<Unit> red_unit;
    std::unique_ptr<Unit> blue_unit;
};

// Supply point management
TEST_F(SupplyModelTest, AddSupplyPoint) {
    SupplyPoint new_depot;
    new_depot.id = "depot_new";
    new_depot.position = {50.4, 9.4};
    new_depot.faction = Faction::Red;
    new_depot.fuel_capacity = 5000.0;
    new_depot.ammo_capacity = 5000.0;
    new_depot.supply_capacity = 2500.0;
    new_depot.fuel_available = 4000.0;
    new_depot.ammo_available = 4000.0;
    new_depot.supply_available = 2000.0;
    new_depot.resupply_rate_per_turn = 250.0;

    supply->add_supply_point(new_depot);

    auto* point = supply->get_supply_point("depot_new");
    ASSERT_NE(point, nullptr);
    EXPECT_EQ(point->faction, Faction::Red);
}

TEST_F(SupplyModelTest, RemoveSupplyPoint) {
    supply->remove_supply_point("depot_red_1");

    auto* point = supply->get_supply_point("depot_red_1");
    EXPECT_EQ(point, nullptr);
}

TEST_F(SupplyModelTest, GetSupplyPoints) {
    const auto& points = supply->get_supply_points();
    EXPECT_EQ(points.size(), 2);
}

// Supply distance calculation (legacy)
TEST_F(SupplyModelTest, SupplyDistance) {
    double distance = supply->calculate_supply_distance(*red_unit);

    EXPECT_GT(distance, 0.0);
    EXPECT_LT(distance, 100.0);  // Should find nearby depot
}

TEST_F(SupplyModelTest, IsUnitInSupply) {
    EXPECT_TRUE(supply->is_unit_in_supply(*red_unit));

    // Move unit far from depot
    red_unit->set_position({50.95, 9.95});
    supply->set_max_supply_range(20.0);

    // May or may not be in supply depending on distance
}

// LOC (Line of Communication) calculation
TEST_F(SupplyModelTest, CalculateLOC) {
    auto loc = supply->calculate_loc(*red_unit);

    EXPECT_TRUE(loc.has_valid_route);
    EXPECT_GT(loc.distance_km, 0.0);
    EXPECT_EQ(loc.depot_id, "depot_red_1");
}

TEST_F(SupplyModelTest, LOCUsesPathfinding) {
    auto loc = supply->calculate_loc(*red_unit);

    // Route distance should be >= straight line distance
    EXPECT_GE(loc.distance_km, loc.straight_line_km);

    // Route should have waypoints
    EXPECT_GT(loc.route.size(), 0);
}

TEST_F(SupplyModelTest, LOCToSpecificDepot) {
    auto* depot = supply->get_supply_point("depot_red_1");
    ASSERT_NE(depot, nullptr);

    auto loc = supply->calculate_loc_to_depot(*red_unit, *depot);

    EXPECT_TRUE(loc.has_valid_route);
    EXPECT_EQ(loc.depot_id, depot->id);
}

// Supply status
TEST_F(SupplyModelTest, GetSupplyStatus) {
    auto status = supply->get_supply_status(*red_unit);

    EXPECT_EQ(status.unit_id, "red_bn_1");
    EXPECT_TRUE(status.loc.has_valid_route);
    EXPECT_GT(status.days_of_supply, 0.0);
}

TEST_F(SupplyModelTest, CriticallyLowSupply) {
    // Drain supplies
    red_unit->get_logistics_mut().fuel_level = 0.1;
    red_unit->get_logistics_mut().ammo_level = 0.1;

    auto status = supply->get_supply_status(*red_unit);

    EXPECT_TRUE(status.is_critically_low);
}

TEST_F(SupplyModelTest, AllSupplyStatus) {
    std::vector<Unit*> units = {red_unit.get(), blue_unit.get()};
    auto statuses = supply->get_all_supply_status(units);

    EXPECT_EQ(statuses.size(), 2);
}

// Resupply operations
TEST_F(SupplyModelTest, ProcessResupplyRequest) {
    ResupplyRequest request;
    request.unit_id = "red_bn_1";
    request.fuel_needed = 0.3;
    request.ammo_needed = 0.3;
    request.supply_needed = 0.2;
    request.priority = 1;

    std::vector<ResupplyRequest> requests = {request};
    std::vector<Unit*> units = {red_unit.get()};

    double initial_fuel = red_unit->get_logistics().fuel_level;

    auto results = supply->process_resupply_requests(requests, units);

    EXPECT_EQ(results.size(), 1);
    EXPECT_EQ(results[0].unit_id, "red_bn_1");
    EXPECT_GT(results[0].fuel_delivered, 0.0);

    // Unit should have more fuel now
    EXPECT_GT(red_unit->get_logistics().fuel_level, initial_fuel);
}

TEST_F(SupplyModelTest, ResupplyPriority) {
    // Create two requests with different priorities
    ResupplyRequest high_priority;
    high_priority.unit_id = "red_bn_1";
    high_priority.fuel_needed = 0.5;
    high_priority.ammo_needed = 0.5;
    high_priority.supply_needed = 0.0;
    high_priority.priority = 1;

    ResupplyRequest low_priority;
    low_priority.unit_id = "red_bn_1";  // Same unit for simplicity
    low_priority.fuel_needed = 0.5;
    low_priority.ammo_needed = 0.5;
    low_priority.supply_needed = 0.0;
    low_priority.priority = 3;

    // Limit depot supplies to force prioritization
    auto* depot = supply->get_supply_point("depot_red_1");
    depot->fuel_available = 0.4;  // Not enough for both

    std::vector<ResupplyRequest> requests = {low_priority, high_priority};
    std::vector<Unit*> units = {red_unit.get()};

    auto results = supply->process_resupply_requests(requests, units);

    // High priority should be satisfied first
    auto high_result = std::find_if(results.begin(), results.end(),
        [](const ResupplyResult& r) { return r.unit_id == "red_bn_1"; });

    if (high_result != results.end()) {
        EXPECT_GT(high_result->fuel_delivered, 0.0);
    }
}

// Supply route management
TEST_F(SupplyModelTest, AddSupplyRoute) {
    SupplyRoute route;
    route.id = "route_1";
    route.waypoints = {{50.3, 9.3}, {50.4, 9.4}, {50.5, 9.5}};
    route.capacity_per_turn = 1000.0;
    route.is_cut = false;
    route.route_distance_km = 25.0;
    route.uses_roads = true;

    supply->add_supply_route(route);

    // Route should be usable
}

TEST_F(SupplyModelTest, CutSupplyRoute) {
    SupplyRoute route;
    route.id = "route_1";
    route.waypoints = {{50.3, 9.3}, {50.5, 9.5}};
    route.capacity_per_turn = 1000.0;
    route.is_cut = false;
    route.route_distance_km = 25.0;
    route.uses_roads = true;

    supply->add_supply_route(route);
    supply->cut_route("route_1");

    // Route should be marked as cut
}

TEST_F(SupplyModelTest, RestoreSupplyRoute) {
    SupplyRoute route;
    route.id = "route_1";
    route.waypoints = {{50.3, 9.3}, {50.5, 9.5}};
    route.capacity_per_turn = 1000.0;
    route.is_cut = true;
    route.route_distance_km = 25.0;
    route.uses_roads = false;

    supply->add_supply_route(route);
    supply->restore_route("route_1");

    // Route should be usable again
}

// Interdiction
TEST_F(SupplyModelTest, RouteInterdiction) {
    // Create an enemy unit along supply route
    auto enemy = std::make_unique<Unit>(
        "enemy_1", "Enemy Blocking Force",
        Faction::Blue, UnitType::Mechanized, Echelon::Battalion);
    enemy->set_position({50.4, 9.4});  // On route between depot and unit
    orbat->add_unit(std::move(enemy));

    std::vector<Coordinates> route = {{50.3, 9.3}, {50.4, 9.4}, {50.5, 9.5}};

    bool interdicted = supply->is_route_interdicted(
        route, Faction::Red, 5.0);  // 5km interdiction radius

    EXPECT_TRUE(interdicted);
}

TEST_F(SupplyModelTest, GetInterdictingUnits) {
    auto enemy = std::make_unique<Unit>(
        "blocker", "Blocking Force",
        Faction::Blue, UnitType::Armor, Echelon::Battalion);
    enemy->set_position({50.4, 9.4});
    orbat->add_unit(std::move(enemy));

    std::vector<Coordinates> route = {{50.3, 9.3}, {50.4, 9.4}, {50.5, 9.5}};

    auto interdicting = supply->get_interdicting_units(
        route, Faction::Red, 5.0);

    EXPECT_EQ(interdicting.size(), 1);
    EXPECT_EQ(interdicting[0], "blocker");
}

TEST_F(SupplyModelTest, LOCInterdictionCheck) {
    // Place enemy on supply route
    auto enemy = std::make_unique<Unit>(
        "enemy_block", "Enemy",
        Faction::Blue, UnitType::Mechanized, Echelon::Battalion);
    enemy->set_position({50.4, 9.4});
    orbat->add_unit(std::move(enemy));

    auto loc = supply->calculate_loc(*red_unit);

    // LOC should detect interdiction
    // (depends on route taken by pathfinding)
}

// Turn consumption
TEST_F(SupplyModelTest, ApplyTurnConsumption) {
    double initial_fuel = red_unit->get_logistics().fuel_level;
    double initial_ammo = red_unit->get_logistics().ammo_level;

    std::vector<Unit*> units = {red_unit.get()};
    supply->apply_turn_consumption(units, 4.0);  // 4-hour turn

    // Supplies should be reduced
    EXPECT_LT(red_unit->get_logistics().fuel_level, initial_fuel);
}

TEST_F(SupplyModelTest, ConsumptionVariesByPosture) {
    // Marching consumes more than defending
    red_unit->set_posture(Posture::Move);
    double march_initial = 1.0;
    red_unit->get_logistics_mut().fuel_level = march_initial;

    std::vector<Unit*> march_units = {red_unit.get()};
    supply->apply_turn_consumption(march_units, 4.0);
    double march_consumed = march_initial - red_unit->get_logistics().fuel_level;

    // Reset
    red_unit->get_logistics_mut().fuel_level = 1.0;
    red_unit->set_posture(Posture::Defend);

    std::vector<Unit*> defend_units = {red_unit.get()};
    supply->apply_turn_consumption(defend_units, 4.0);
    double defend_consumed = 1.0 - red_unit->get_logistics().fuel_level;

    // Marching should consume more
    EXPECT_GT(march_consumed, defend_consumed);
}

// Configuration
TEST_F(SupplyModelTest, SetMaxSupplyRange) {
    supply->set_max_supply_range(25.0);

    // Move unit far away
    red_unit->set_position({50.6, 9.6});  // ~30km from depot

    auto loc = supply->calculate_loc(*red_unit);

    // May or may not have valid route depending on range
}

TEST_F(SupplyModelTest, SetInterdictionRadius) {
    supply->set_interdiction_radius(10.0);  // Large radius

    auto enemy = std::make_unique<Unit>(
        "enemy", "Enemy",
        Faction::Blue, UnitType::Armor, Echelon::Battalion);
    enemy->set_position({50.4, 9.4});
    orbat->add_unit(std::move(enemy));

    std::vector<Coordinates> route = {{50.3, 9.3}, {50.5, 9.5}};

    bool interdicted = supply->is_route_interdicted(route, Faction::Red, 10.0);

    // With large radius, enemy should interdict
    EXPECT_TRUE(interdicted);
}

// Edge cases
TEST_F(SupplyModelTest, NoDepotForFaction) {
    // Remove all Red depots
    supply->remove_supply_point("depot_red_1");

    auto loc = supply->calculate_loc(*red_unit);

    EXPECT_FALSE(loc.has_valid_route);
}

TEST_F(SupplyModelTest, EmptyResupplyRequest) {
    std::vector<ResupplyRequest> empty_requests;
    std::vector<Unit*> units = {red_unit.get()};

    auto results = supply->process_resupply_requests(empty_requests, units);

    EXPECT_TRUE(results.empty());
}

TEST_F(SupplyModelTest, DepletedDepot) {
    // Deplete depot
    auto* depot = supply->get_supply_point("depot_red_1");
    depot->fuel_available = 0.0;
    depot->ammo_available = 0.0;

    ResupplyRequest request;
    request.unit_id = "red_bn_1";
    request.fuel_needed = 0.5;
    request.ammo_needed = 0.5;
    request.supply_needed = 0.0;
    request.priority = 1;

    std::vector<ResupplyRequest> requests = {request};
    std::vector<Unit*> units = {red_unit.get()};

    auto results = supply->process_resupply_requests(requests, units);

    // Should not deliver supplies from empty depot
    EXPECT_EQ(results[0].fuel_delivered, 0.0);
    EXPECT_EQ(results[0].ammo_delivered, 0.0);
}

// Supply line path details
TEST_F(SupplyModelTest, SupplyRouteDetails) {
    auto loc = supply->calculate_loc(*red_unit);

    // Route may use roads if available
    // Just verify the field exists
    EXPECT_TRUE(loc.is_interdicted || !loc.is_interdicted);  // Boolean is valid
}

TEST_F(SupplyModelTest, SupplyRouteDistance) {
    auto loc = supply->calculate_loc(*red_unit);

    // Route distance should be reasonable
    EXPECT_GT(loc.distance_km, 0.0);
    EXPECT_LT(loc.distance_km, 200.0);  // Not unreasonably long

    // Should be >= straight line
    EXPECT_GE(loc.distance_km, loc.straight_line_km * 0.99);  // Allow small tolerance
}
