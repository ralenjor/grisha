#pragma once

#include "../types.hpp"
#include <memory>
#include <vector>
#include <optional>
#include <functional>

namespace karkas {

// Terrain cell with all relevant data
struct TerrainCell {
    Coordinates center;
    double elevation_m;
    TerrainType primary_type;
    std::optional<TerrainType> secondary_type;
    CoverLevel cover;
    double concealment;      // 0.0 - 1.0
    double urban_density;    // 0.0 - 1.0 (for urban cells)
    uint32_t population;     // Population count (for urban)
    bool is_road;
    bool is_bridge;
    bool is_impassable;

    // Mobility costs by class (1.0 = normal, higher = slower)
    double get_mobility_cost(MobilityClass mobility) const;

    // Combat modifiers
    double get_defense_modifier() const;
    double get_attack_modifier() const;
    double get_detection_modifier() const;
};

// Line of sight result
struct LOSResult {
    bool has_los;
    double distance_km;
    std::vector<Coordinates> blocking_points;
    double terrain_screening;  // Percentage of target screened
};

// Path segment
struct PathSegment {
    Coordinates from;
    Coordinates to;
    double distance_km;
    double travel_time_hours;
    TerrainType terrain;
    CoverLevel cover_along_route;
};

// Complete path
struct Path {
    std::vector<PathSegment> segments;
    double total_distance_km;
    double total_time_hours;
    double average_cover;
    bool uses_roads;

    Coordinates get_position_at_time(double hours) const;
};

class TerrainEngine {
public:
    TerrainEngine();
    ~TerrainEngine();

    // Initialization
    bool load_region(const BoundingBox& bounds, const std::string& data_path);
    bool load_from_geopackage(const std::string& gpkg_path);
    void set_resolution(double meters);  // Cell size

    // Basic queries
    TerrainCell get_cell(const Coordinates& coord) const;
    std::vector<TerrainCell> get_cells_in_radius(const Coordinates& center, double radius_km) const;
    std::vector<TerrainCell> get_cells_in_box(const BoundingBox& box) const;
    double get_elevation(const Coordinates& coord) const;
    TerrainType get_terrain_type(const Coordinates& coord) const;

    // Line of sight
    LOSResult calculate_los(const Coordinates& from, const Coordinates& to,
                           double observer_height_m = 2.0,
                           double target_height_m = 2.0) const;

    bool has_los(const Coordinates& from, const Coordinates& to) const {
        return calculate_los(from, to).has_los;
    }

    // Line of sight with sensor considerations
    LOSResult calculate_sensor_los(const Coordinates& from, const Coordinates& to,
                                   SensorType sensor_type) const;

    // Mobility
    double get_mobility_cost(const Coordinates& coord, MobilityClass mobility) const;
    bool is_passable(const Coordinates& coord, MobilityClass mobility) const;

    // Pathfinding
    std::optional<Path> find_path(const Coordinates& from, const Coordinates& to,
                                  MobilityClass mobility,
                                  RoutePreference preference = RoutePreference::Fastest) const;

    std::optional<Path> find_path_avoiding(const Coordinates& from, const Coordinates& to,
                                           MobilityClass mobility,
                                           const std::vector<Coordinates>& avoid_points,
                                           double avoid_radius_km) const;

    // Area analysis
    double calculate_area_cover(const std::vector<Coordinates>& polygon) const;
    std::vector<Coordinates> find_defensive_positions(const Coordinates& center,
                                                      double radius_km,
                                                      int max_positions = 5) const;
    std::vector<Coordinates> find_observation_points(const Coordinates& center,
                                                     double radius_km,
                                                     const Coordinates& target_area) const;

    // Urban operations
    std::vector<Coordinates> get_urban_centers(const BoundingBox& box) const;
    uint32_t get_population_in_area(const std::vector<Coordinates>& polygon) const;

    // Road network
    std::optional<Path> find_road_route(const Coordinates& from, const Coordinates& to) const;
    std::vector<Coordinates> get_road_intersections(const BoundingBox& box) const;
    std::vector<Coordinates> get_bridges(const BoundingBox& box) const;

    // Terrain analysis for AI
    struct TerrainAnalysis {
        double average_elevation;
        double elevation_variance;
        double percent_forest;
        double percent_urban;
        double percent_open;
        double road_density_km_per_sq_km;
        std::vector<Coordinates> key_terrain_features;
        std::vector<Coordinates> choke_points;
    };

    TerrainAnalysis analyze_area(const BoundingBox& box) const;

    // Weather effects on terrain
    void apply_weather_effects(const Weather& weather);

    // Bounds
    BoundingBox get_bounds() const { return bounds_; }
    bool is_loaded() const { return loaded_; }

private:
    class Impl;
    std::unique_ptr<Impl> impl_;

    BoundingBox bounds_;
    double resolution_m_;
    bool loaded_;

    // Caching
    mutable std::unordered_map<int64_t, TerrainCell> cell_cache_;
    int64_t coord_to_cache_key(const Coordinates& coord) const;
};

}  // namespace karkas
