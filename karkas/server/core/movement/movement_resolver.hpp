#pragma once

#include "../types.hpp"
#include "../unit.hpp"
#include "../terrain/terrain_engine.hpp"
#include <vector>
#include <map>
#include <set>

namespace karkas {

struct MovementOrder {
    UnitId unit_id;
    std::vector<Coordinates> waypoints;
    RoutePreference route_preference;
    double max_speed_modifier;  // 1.0 = normal, 0.5 = cautious, 1.5 = rapid
    bool halt_on_contact;
    std::optional<Coordinates> final_destination;
    int priority;  // Higher priority moves first (default 0)
};

struct MovementResult {
    UnitId unit_id;
    Coordinates start_position;
    Coordinates end_position;
    double distance_moved_km;
    double time_elapsed_hours;
    bool reached_destination;
    bool halted_by_contact;
    bool halted_by_terrain;
    bool halted_by_congestion;
    double fuel_consumed;
    std::vector<Coordinates> path_taken;
    std::vector<PathSegment> segments_traversed;
    std::string narrative;
};

// Traffic congestion tracking
struct RoadSegment {
    Coordinates from;
    Coordinates to;
    double capacity_units_per_hour;  // Max throughput
    double current_usage;
    std::vector<UnitId> queued_units;
};

// Movement priority for ordering
struct MovementPriority {
    UnitId unit_id;
    int priority;           // Order priority (higher first)
    Echelon echelon;        // Larger units move first at same priority
    double distance_to_obj; // Closer units move first at same echelon

    bool operator<(const MovementPriority& other) const {
        if (priority != other.priority) return priority > other.priority;
        if (echelon != other.echelon) return echelon > other.echelon;
        return distance_to_obj < other.distance_to_obj;
    }
};

class MovementResolver {
public:
    MovementResolver();

    void set_terrain(const TerrainEngine* terrain) { terrain_ = terrain; }

    // Resolve movement for a single unit for one turn
    MovementResult resolve_movement(Unit& unit, const MovementOrder& order,
                                   double turn_hours,
                                   const std::vector<Unit*>& enemy_units,
                                   const Weather& weather);

    // Resolve movement for multiple units (handles collision avoidance)
    std::vector<MovementResult> resolve_all_movements(
        std::vector<Unit*>& units,
        const std::vector<MovementOrder>& orders,
        double turn_hours,
        const Weather& weather);

    // Calculate expected movement range
    double estimate_movement_range(const Unit& unit, double hours,
                                  const Weather& weather) const;

    // Check for interdiction (enemy units blocking path)
    bool check_interdiction(const Path& path,
                           const std::vector<Unit*>& enemy_units,
                           double interdiction_radius_km) const;

    // Find the closest enemy that would interdict
    std::optional<Coordinates> find_interdiction_point(
        const Path& path,
        const std::vector<Unit*>& enemy_units,
        double interdiction_radius_km) const;

    // Formation movement
    struct FormationSpec {
        std::string formation_type;  // "column", "line", "wedge", "echelon_left", "echelon_right"
        double spacing_km;
        double depth_km;  // For column formations
    };

    std::vector<Coordinates> calculate_formation_positions(
        const Coordinates& center,
        double heading,
        const FormationSpec& formation,
        int num_units) const;

    // Road network capacity
    void set_road_capacity(double units_per_hour) { road_capacity_ = units_per_hour; }
    double get_road_capacity() const { return road_capacity_; }

private:
    const TerrainEngine* terrain_;
    double road_capacity_;  // Units per hour per road segment

    // Congestion tracking for current resolution
    std::map<int64_t, RoadSegment> road_segments_;
    std::set<int64_t> occupied_cells_;  // Cells occupied by stopped/slow units

    // Internal movement calculation
    double calculate_effective_speed(const Unit& unit,
                                    const TerrainCell& terrain,
                                    const Weather& weather) const;

    double calculate_fuel_consumption(const Unit& unit,
                                     double distance_km,
                                     const TerrainCell& terrain,
                                     double speed_kph) const;

    // Segment-based fuel consumption
    double calculate_segment_fuel(const Unit& unit,
                                 const PathSegment& segment,
                                 double actual_speed_kph) const;

    // Path following with terrain
    MovementResult follow_path(Unit& unit, const Path& path,
                              const MovementOrder& order,
                              double turn_hours,
                              const std::vector<Unit*>& enemy_units,
                              const Weather& weather);

    // Collision detection between moving units
    std::vector<std::pair<UnitId, UnitId>> detect_collisions(
        const std::vector<Unit*>& units,
        const std::vector<MovementResult>& planned_movements) const;

    // Priority ordering
    std::vector<MovementPriority> calculate_movement_order(
        const std::vector<Unit*>& units,
        const std::vector<MovementOrder>& orders) const;

    // Congestion handling
    bool check_road_congestion(const Coordinates& from, const Coordinates& to) const;
    void update_road_usage(const Coordinates& from, const Coordinates& to,
                          const UnitId& unit_id);
    void clear_congestion_state();

    // Cell occupation for collision avoidance
    int64_t coord_to_cell_key(const Coordinates& coord) const;
    bool is_cell_occupied(const Coordinates& coord) const;
    void occupy_cell(const Coordinates& coord);
    void release_cell(const Coordinates& coord);

    // Find alternate route around congestion
    std::optional<Path> find_bypass_route(
        const Coordinates& from,
        const Coordinates& to,
        const Unit& unit,
        const std::set<Coordinates>& blocked_points) const;

    // Generate narrative for movement result
    std::string generate_narrative(const Unit& unit, const MovementResult& result,
                                  const MovementOrder& order) const;
};

}  // namespace karkas
