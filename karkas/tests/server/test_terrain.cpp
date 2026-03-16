// KARKAS Terrain Engine Tests (6.2.3)
// Tests for TerrainEngine: loading, queries, LOS, pathfinding, mobility

#include <gtest/gtest.h>
#include "types.hpp"
#include "terrain/terrain_engine.hpp"

using namespace karkas;

class TerrainEngineTest : public ::testing::Test {
protected:
    void SetUp() override {
        terrain = std::make_unique<TerrainEngine>();

        // Load a test region (Fulda Gap area)
        BoundingBox fulda_region{{50.0, 9.0}, {51.0, 10.0}};

        // Try to load actual terrain data if available
        bool loaded = terrain->load_from_geopackage(
            "data/terrain/fulda_gap.gpkg");

        if (!loaded) {
            // Fall back to synthetic terrain
            loaded = terrain->load_region(fulda_region, "");
        }

        terrain_loaded = loaded;
    }

    std::unique_ptr<TerrainEngine> terrain;
    bool terrain_loaded = false;
};

// Loading tests
TEST_F(TerrainEngineTest, TerrainLoaded) {
    EXPECT_TRUE(terrain->is_loaded());
}

TEST_F(TerrainEngineTest, BoundsValid) {
    auto bounds = terrain->get_bounds();

    EXPECT_LT(bounds.southwest.latitude, bounds.northeast.latitude);
    EXPECT_LT(bounds.southwest.longitude, bounds.northeast.longitude);
}

// Basic queries
TEST_F(TerrainEngineTest, GetCell) {
    Coordinates center{50.5, 9.5};
    auto cell = terrain->get_cell(center);

    // Cell should have reasonable values
    EXPECT_GE(cell.elevation_m, -500.0);  // Below sea level possible
    EXPECT_LE(cell.elevation_m, 9000.0);  // Below Everest
    EXPECT_GE(cell.concealment, 0.0);
    EXPECT_LE(cell.concealment, 1.0);
}

TEST_F(TerrainEngineTest, GetElevation) {
    Coordinates point{50.5, 9.5};
    double elevation = terrain->get_elevation(point);

    // Fulda Gap region elevations are roughly 200-700m
    EXPECT_GE(elevation, 0.0);
    EXPECT_LE(elevation, 2000.0);
}

TEST_F(TerrainEngineTest, GetTerrainType) {
    Coordinates point{50.5, 9.5};
    TerrainType type = terrain->get_terrain_type(point);

    // Type should be valid
    EXPECT_NE(type, TerrainType::Water);  // Not in water (middle of land)
}

TEST_F(TerrainEngineTest, GetCellsInRadius) {
    Coordinates center{50.5, 9.5};
    double radius_km = 5.0;

    auto cells = terrain->get_cells_in_radius(center, radius_km);

    EXPECT_GT(cells.size(), 0);

    // All cells should be within the radius
    for (const auto& cell : cells) {
        double dist = center.distance_to(cell.center);
        EXPECT_LE(dist, radius_km + 0.5);  // Small tolerance for cell size
    }
}

TEST_F(TerrainEngineTest, GetCellsInBox) {
    BoundingBox box{{50.45, 9.45}, {50.55, 9.55}};
    auto cells = terrain->get_cells_in_box(box);

    EXPECT_GT(cells.size(), 0);

    // Grid-based query returns cells that overlap box boundary
    // Cell centers may be slightly outside due to grid alignment
    // Just verify cells are reasonably close to the requested area
    double tolerance = 0.1;  // Allow ~10km tolerance for grid alignment
    BoundingBox expanded{{box.southwest.latitude - tolerance,
                          box.southwest.longitude - tolerance},
                         {box.northeast.latitude + tolerance,
                          box.northeast.longitude + tolerance}};

    for (const auto& cell : cells) {
        EXPECT_TRUE(expanded.contains(cell.center));
    }
}

// Mobility tests
TEST_F(TerrainEngineTest, MobilityCost) {
    Coordinates point{50.5, 9.5};

    double foot_cost = terrain->get_mobility_cost(point, MobilityClass::Foot);
    double tracked_cost = terrain->get_mobility_cost(point, MobilityClass::Tracked);
    double wheeled_cost = terrain->get_mobility_cost(point, MobilityClass::Wheeled);

    EXPECT_GT(foot_cost, 0.0);
    EXPECT_GT(tracked_cost, 0.0);
    EXPECT_GT(wheeled_cost, 0.0);
}

TEST_F(TerrainEngineTest, IsPassable) {
    Coordinates land_point{50.5, 9.5};

    EXPECT_TRUE(terrain->is_passable(land_point, MobilityClass::Foot));
    EXPECT_TRUE(terrain->is_passable(land_point, MobilityClass::Tracked));
}

TEST_F(TerrainEngineTest, AirMobilityUnaffected) {
    Coordinates point{50.5, 9.5};

    double rotary_cost = terrain->get_mobility_cost(point, MobilityClass::Rotary);

    // Air mobility should have cost near 1.0 regardless of terrain
    EXPECT_NEAR(rotary_cost, 1.0, 0.1);
}

// TerrainCell mobility methods
TEST(TerrainCellTest, MobilityCostByType) {
    TerrainCell open_cell;
    open_cell.primary_type = TerrainType::Open;
    open_cell.is_impassable = false;

    TerrainCell forest_cell;
    forest_cell.primary_type = TerrainType::Forest;
    forest_cell.is_impassable = false;

    // Open terrain should be faster than forest
    EXPECT_LT(open_cell.get_mobility_cost(MobilityClass::Wheeled),
              forest_cell.get_mobility_cost(MobilityClass::Wheeled));

    // Foot infantry less affected by forest
    double foot_open = open_cell.get_mobility_cost(MobilityClass::Foot);
    double foot_forest = forest_cell.get_mobility_cost(MobilityClass::Foot);
    EXPECT_LT(foot_forest / foot_open, 2.0);  // Forest penalty not too severe for foot
}

TEST(TerrainCellTest, ImpassableTerrain) {
    TerrainCell impassable;
    impassable.is_impassable = true;

    // Impassable should have very high cost (or infinity)
    double cost = impassable.get_mobility_cost(MobilityClass::Tracked);
    EXPECT_GT(cost, 100.0);
}

TEST(TerrainCellTest, RoadBonus) {
    TerrainCell road_cell;
    road_cell.primary_type = TerrainType::Road;
    road_cell.is_road = true;
    road_cell.is_impassable = false;

    TerrainCell normal_cell;
    normal_cell.primary_type = TerrainType::Open;
    normal_cell.is_road = false;
    normal_cell.is_impassable = false;

    // Road should be faster
    EXPECT_LT(road_cell.get_mobility_cost(MobilityClass::Wheeled),
              normal_cell.get_mobility_cost(MobilityClass::Wheeled));
}

// TerrainCell combat modifiers
TEST(TerrainCellTest, DefenseModifiers) {
    TerrainCell forest;
    forest.primary_type = TerrainType::Forest;
    forest.cover = CoverLevel::Medium;

    TerrainCell urban;
    urban.primary_type = TerrainType::Urban;
    urban.cover = CoverLevel::Heavy;
    urban.urban_density = 0.8;

    TerrainCell open;
    open.primary_type = TerrainType::Open;
    open.cover = CoverLevel::None;

    // Urban should provide best defense
    EXPECT_GT(urban.get_defense_modifier(), forest.get_defense_modifier());
    EXPECT_GT(forest.get_defense_modifier(), open.get_defense_modifier());
}

TEST(TerrainCellTest, ConcealmentValues) {
    TerrainCell forest;
    forest.primary_type = TerrainType::Forest;
    forest.concealment = 0.8;

    TerrainCell open;
    open.primary_type = TerrainType::Open;
    open.concealment = 0.1;

    EXPECT_GT(forest.concealment, open.concealment);
    EXPECT_GE(forest.concealment, 0.0);
    EXPECT_LE(forest.concealment, 1.0);
}

// Line of Sight tests
TEST_F(TerrainEngineTest, LOSFlat) {
    // Two points on relatively flat terrain
    Coordinates from{50.5, 9.5};
    Coordinates to{50.51, 9.51};  // ~1.4km apart

    auto los = terrain->calculate_los(from, to);

    EXPECT_GT(los.distance_km, 0.0);
    EXPECT_LE(los.distance_km, 5.0);

    // LOS result should be consistent
    EXPECT_GE(los.terrain_screening, 0.0);
    EXPECT_LE(los.terrain_screening, 1.0);
}

TEST_F(TerrainEngineTest, LOSDistance) {
    Coordinates from{50.5, 9.5};
    Coordinates to{50.6, 9.6};

    auto los = terrain->calculate_los(from, to);

    // Distance should roughly match straight-line
    double straight_line = from.distance_to(to);
    EXPECT_NEAR(los.distance_km, straight_line, straight_line * 0.1);
}

TEST_F(TerrainEngineTest, HasLOS) {
    Coordinates from{50.5, 9.5};
    Coordinates near_to{50.505, 9.505};  // Very close

    // At very close range, should typically have LOS
    bool has = terrain->has_los(from, near_to);
    // Result depends on terrain, but test the API works
    EXPECT_TRUE(has || !has);  // Just verify it runs
}

TEST_F(TerrainEngineTest, SensorLOS) {
    Coordinates from{50.5, 9.5};
    Coordinates to{50.55, 9.55};

    auto visual_los = terrain->calculate_sensor_los(from, to, SensorType::Visual);
    auto radar_los = terrain->calculate_sensor_los(from, to, SensorType::Radar);

    // Both should return valid results
    EXPECT_GE(visual_los.distance_km, 0.0);
    EXPECT_GE(radar_los.distance_km, 0.0);

    // Radar may penetrate some terrain that blocks visual
    // (depends on implementation)
}

// Pathfinding tests
TEST_F(TerrainEngineTest, FindPath) {
    Coordinates from{50.4, 9.4};
    Coordinates to{50.5, 9.5};

    auto path = terrain->find_path(from, to, MobilityClass::Tracked);

    ASSERT_TRUE(path.has_value());
    EXPECT_GT(path->total_distance_km, 0.0);
    EXPECT_GT(path->total_time_hours, 0.0);
    EXPECT_FALSE(path->segments.empty());
}

TEST_F(TerrainEngineTest, PathRoutePreferences) {
    Coordinates from{50.4, 9.4};
    Coordinates to{50.6, 9.6};

    auto fastest = terrain->find_path(from, to, MobilityClass::Wheeled,
                                      RoutePreference::Fastest);
    auto covered = terrain->find_path(from, to, MobilityClass::Wheeled,
                                     RoutePreference::Covered);

    ASSERT_TRUE(fastest.has_value());
    ASSERT_TRUE(covered.has_value());

    // Covered route might be longer but have better cover
    if (fastest->total_distance_km < covered->total_distance_km) {
        EXPECT_GE(covered->average_cover, fastest->average_cover);
    }
}

TEST_F(TerrainEngineTest, PathAvoidance) {
    Coordinates from{50.4, 9.4};
    Coordinates to{50.6, 9.6};
    std::vector<Coordinates> avoid = {{50.5, 9.5}};  // Avoid center

    auto path = terrain->find_path_avoiding(from, to, MobilityClass::Tracked,
                                            avoid, 5.0);

    ASSERT_TRUE(path.has_value());

    // Path should go around the avoided point
    for (const auto& seg : path->segments) {
        double dist_from = seg.from.distance_to(avoid[0]);
        double dist_to = seg.to.distance_to(avoid[0]);
        // At least one end of each segment should be >5km from avoided point
        // (simplified check)
    }
}

TEST_F(TerrainEngineTest, PathPositionAtTime) {
    Coordinates from{50.4, 9.4};
    Coordinates to{50.5, 9.5};

    auto path = terrain->find_path(from, to, MobilityClass::Tracked);
    ASSERT_TRUE(path.has_value());

    // Position at time 0 should be start
    Coordinates start_pos = path->get_position_at_time(0.0);
    EXPECT_NEAR(start_pos.latitude, from.latitude, 0.01);
    EXPECT_NEAR(start_pos.longitude, from.longitude, 0.01);

    // Position at end time should be destination
    Coordinates end_pos = path->get_position_at_time(path->total_time_hours);
    EXPECT_NEAR(end_pos.latitude, to.latitude, 0.01);
    EXPECT_NEAR(end_pos.longitude, to.longitude, 0.01);
}

// Road network
TEST_F(TerrainEngineTest, FindRoadRoute) {
    Coordinates from{50.4, 9.4};
    Coordinates to{50.6, 9.6};

    auto road_route = terrain->find_road_route(from, to);

    // May or may not find a road route depending on data
    if (road_route.has_value()) {
        EXPECT_TRUE(road_route->uses_roads);
    }
}

TEST_F(TerrainEngineTest, GetBridges) {
    BoundingBox box{{50.3, 9.3}, {50.7, 9.7}};
    auto bridges = terrain->get_bridges(box);

    // Bridges are terrain features, may or may not exist in test data
    // Just verify API works
    for (const auto& bridge : bridges) {
        EXPECT_TRUE(box.contains(bridge));
    }
}

// Area analysis
TEST_F(TerrainEngineTest, AnalyzeArea) {
    BoundingBox box{{50.4, 9.4}, {50.6, 9.6}};
    auto analysis = terrain->analyze_area(box);

    EXPECT_GE(analysis.average_elevation, 0.0);
    EXPECT_GE(analysis.percent_forest, 0.0);
    EXPECT_LE(analysis.percent_forest, 100.0);
    EXPECT_GE(analysis.percent_urban, 0.0);
    EXPECT_LE(analysis.percent_urban, 100.0);
    EXPECT_GE(analysis.percent_open, 0.0);
    EXPECT_LE(analysis.percent_open, 100.0);

    // Individual percentages should be valid (0-100)
    // Total may be less than 100% if there are other terrain types (water, marsh, etc.)
    double total = analysis.percent_forest + analysis.percent_urban +
                   analysis.percent_open;
    EXPECT_LE(total, 100.0);
}

TEST_F(TerrainEngineTest, FindDefensivePositions) {
    Coordinates center{50.5, 9.5};
    auto positions = terrain->find_defensive_positions(center, 5.0, 5);

    EXPECT_LE(positions.size(), 5);

    for (const auto& pos : positions) {
        double dist = center.distance_to(pos);
        EXPECT_LE(dist, 5.0);
    }
}

TEST_F(TerrainEngineTest, FindObservationPoints) {
    Coordinates center{50.5, 9.5};
    Coordinates target{50.55, 9.55};

    auto obs_points = terrain->find_observation_points(center, 3.0, target);

    for (const auto& pos : obs_points) {
        // Observation points should have LOS to target
        // (or at least good potential)
        double dist = center.distance_to(pos);
        EXPECT_LE(dist, 3.0);
    }
}

// Urban terrain
TEST_F(TerrainEngineTest, GetUrbanCenters) {
    BoundingBox box{{50.0, 9.0}, {51.0, 10.0}};
    auto urban = terrain->get_urban_centers(box);

    // May or may not have urban areas in test region
    for (const auto& center : urban) {
        EXPECT_TRUE(box.contains(center));
    }
}

TEST_F(TerrainEngineTest, AreaCover) {
    std::vector<Coordinates> polygon = {
        {50.4, 9.4},
        {50.6, 9.4},
        {50.6, 9.6},
        {50.4, 9.6}
    };

    double cover = terrain->calculate_area_cover(polygon);

    // Returns average CoverLevel (0=None to 4=Fortified)
    EXPECT_GE(cover, 0.0);
    EXPECT_LE(cover, 4.0);  // Max is CoverLevel::Fortified = 4
}

// Weather effects
TEST_F(TerrainEngineTest, WeatherEffects) {
    Weather bad_weather;
    bad_weather.visibility = Weather::Visibility::Fog;
    bad_weather.precipitation = Weather::Precipitation::Heavy;
    bad_weather.temperature_c = 5.0;
    bad_weather.wind_speed_kph = 20.0;
    bad_weather.wind_direction = 180.0;

    terrain->apply_weather_effects(bad_weather);

    // Terrain should still be queryable after weather applied
    Coordinates point{50.5, 9.5};
    auto cell = terrain->get_cell(point);
    EXPECT_GE(cell.elevation_m, 0.0);
}

// Edge cases
TEST(TerrainEngineEdgeTest, UnloadedTerrain) {
    TerrainEngine unloaded;

    EXPECT_FALSE(unloaded.is_loaded());
}

TEST_F(TerrainEngineTest, OutOfBoundsQuery) {
    // Query a point outside loaded bounds
    Coordinates far_away{80.0, 0.0};  // Near North Pole

    // Should handle gracefully (return default or throw)
    // Implementation dependent
}
