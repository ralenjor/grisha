#pragma once

#include "../types.hpp"
#include "../unit.hpp"
#include "../terrain/terrain_engine.hpp"
#include <vector>
#include <optional>

namespace karkas {

// Forward declaration
class OrbatManager;

// Supply point / depot
struct SupplyPoint {
    std::string id;
    Coordinates position;
    Faction faction;

    double fuel_capacity;
    double ammo_capacity;
    double supply_capacity;

    double fuel_available;
    double ammo_available;
    double supply_available;

    double resupply_rate_per_turn;  // How much is replenished per turn
};

// Supply route
struct SupplyRoute {
    std::string id;
    std::vector<Coordinates> waypoints;
    double capacity_per_turn;
    bool is_cut;
    double route_distance_km;       // Actual route distance (pathfinding)
    bool uses_roads;                // Whether route primarily uses roads
};

// Line of Communication result
struct LOCResult {
    bool has_valid_route;           // Route exists to a depot
    double distance_km;             // Actual route distance (not straight-line)
    double straight_line_km;        // Straight-line distance for comparison
    std::string depot_id;           // ID of nearest reachable depot
    std::vector<Coordinates> route; // Waypoints along supply route
    bool is_interdicted;            // Enemy units along route
    std::vector<UnitId> interdicting_units;  // Which enemies cut the route
    double interdiction_strength;   // Combined strength of interdicting units
};

// Supply status for a unit
struct SupplyStatus {
    UnitId unit_id;
    LOCResult loc;
    double days_of_supply;          // Estimated days at current consumption
    bool is_critically_low;         // Below 20% on any supply type
    bool can_receive_resupply;      // Has valid, uninterdicted route
};

// Resupply request
struct ResupplyRequest {
    UnitId unit_id;
    double fuel_needed;
    double ammo_needed;
    double supply_needed;
    int priority;  // 1 = highest
};

// Resupply result
struct ResupplyResult {
    UnitId unit_id;
    double fuel_delivered;
    double ammo_delivered;
    double supply_delivered;
    bool fully_satisfied;
};

class SupplyModel {
public:
    SupplyModel() = default;

    // Component connections
    void set_terrain(const TerrainEngine* terrain) { terrain_ = terrain; }
    void set_orbat(const OrbatManager* orbat) { orbat_ = orbat; }

    // Supply point management
    void add_supply_point(SupplyPoint point);
    void remove_supply_point(const std::string& id);
    SupplyPoint* get_supply_point(const std::string& id);
    const std::vector<SupplyPoint>& get_supply_points() const { return supply_points_; }

    // Route management
    void add_supply_route(SupplyRoute route);
    void cut_route(const std::string& id);
    void restore_route(const std::string& id);

    // Supply operations
    std::vector<ResupplyResult> process_resupply_requests(
        const std::vector<ResupplyRequest>& requests,
        std::vector<Unit*>& units);

    // LOC (Line of Communication) calculation - pathfinding-based
    LOCResult calculate_loc(const Unit& unit) const;
    LOCResult calculate_loc_to_depot(const Unit& unit, const SupplyPoint& depot) const;

    // Supply status
    SupplyStatus get_supply_status(const Unit& unit) const;
    std::vector<SupplyStatus> get_all_supply_status(const std::vector<Unit*>& units) const;

    // Legacy simple distance (for backwards compatibility)
    double calculate_supply_distance(const Unit& unit) const;
    bool is_unit_in_supply(const Unit& unit, double max_distance_km = 50.0) const;

    // Interdiction checking
    bool is_route_interdicted(const std::vector<Coordinates>& route,
                              Faction friendly_faction,
                              double check_radius_km = 2.0) const;
    std::vector<UnitId> get_interdicting_units(const std::vector<Coordinates>& route,
                                               Faction friendly_faction,
                                               double check_radius_km = 2.0) const;

    // Automatic consumption
    void apply_turn_consumption(std::vector<Unit*>& units, double turn_hours);

    // Logistics unit operations
    void dispatch_resupply_convoy(
        const std::string& depot_id,
        const std::vector<UnitId>& target_units);

    // Configuration
    void set_max_supply_range(double km) { max_supply_range_km_ = km; }
    void set_interdiction_radius(double km) { interdiction_radius_km_ = km; }

private:
    std::vector<SupplyPoint> supply_points_;
    std::vector<SupplyRoute> supply_routes_;

    const TerrainEngine* terrain_ = nullptr;
    const OrbatManager* orbat_ = nullptr;

    double max_supply_range_km_ = 100.0;      // Max LOC distance
    double interdiction_radius_km_ = 2.0;     // How close enemy must be to cut route

    SupplyPoint* find_nearest_depot(const Coordinates& pos, Faction faction);
    const SupplyPoint* find_nearest_depot(const Coordinates& pos, Faction faction) const;

    // Internal helpers
    std::optional<Path> calculate_supply_route(const Coordinates& from,
                                               const Coordinates& to) const;
    double calculate_route_distance(const std::vector<Coordinates>& waypoints) const;
};

}  // namespace karkas
