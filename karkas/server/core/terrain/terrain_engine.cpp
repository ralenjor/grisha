#include "terrain_engine.hpp"
#include <cmath>
#include <algorithm>
#include <queue>
#include <set>
#include <stdexcept>

// GDAL headers for GeoPackage support (optional)
#ifdef KARKAS_HAS_GDAL
#include <gdal.h>
#include <ogrsf_frmts.h>
#include <cpl_string.h>
#else
// Stub definitions when GDAL is not available
#define GDALAllRegister() ((void)0)
#endif

namespace karkas {

// Constants
constexpr double EARTH_RADIUS_KM = 6371.0;
constexpr double DEG_TO_RAD = M_PI / 180.0;
constexpr double RAD_TO_DEG = 180.0 / M_PI;

// Coordinate math implementation
double Coordinates::distance_to(const Coordinates& other) const {
    double lat1 = latitude * DEG_TO_RAD;
    double lat2 = other.latitude * DEG_TO_RAD;
    double dlat = (other.latitude - latitude) * DEG_TO_RAD;
    double dlon = (other.longitude - longitude) * DEG_TO_RAD;

    double a = std::sin(dlat / 2) * std::sin(dlat / 2) +
               std::cos(lat1) * std::cos(lat2) *
               std::sin(dlon / 2) * std::sin(dlon / 2);
    double c = 2 * std::atan2(std::sqrt(a), std::sqrt(1 - a));

    return EARTH_RADIUS_KM * c;
}

double Coordinates::bearing_to(const Coordinates& other) const {
    double lat1 = latitude * DEG_TO_RAD;
    double lat2 = other.latitude * DEG_TO_RAD;
    double dlon = (other.longitude - longitude) * DEG_TO_RAD;

    double x = std::sin(dlon) * std::cos(lat2);
    double y = std::cos(lat1) * std::sin(lat2) -
               std::sin(lat1) * std::cos(lat2) * std::cos(dlon);

    double bearing = std::atan2(x, y) * RAD_TO_DEG;
    return std::fmod(bearing + 360.0, 360.0);
}

Coordinates Coordinates::move_toward(double bearing_deg, double distance_km) const {
    double bearing = bearing_deg * DEG_TO_RAD;
    double lat1 = latitude * DEG_TO_RAD;
    double lon1 = longitude * DEG_TO_RAD;
    double d = distance_km / EARTH_RADIUS_KM;

    double lat2 = std::asin(std::sin(lat1) * std::cos(d) +
                           std::cos(lat1) * std::sin(d) * std::cos(bearing));
    double lon2 = lon1 + std::atan2(std::sin(bearing) * std::sin(d) * std::cos(lat1),
                                    std::cos(d) - std::sin(lat1) * std::sin(lat2));

    return {lat2 * RAD_TO_DEG, lon2 * RAD_TO_DEG};
}

bool BoundingBox::contains(const Coordinates& point) const {
    return point.latitude >= southwest.latitude &&
           point.latitude <= northeast.latitude &&
           point.longitude >= southwest.longitude &&
           point.longitude <= northeast.longitude;
}

double BoundingBox::width_km() const {
    Coordinates sw_east{southwest.latitude, northeast.longitude};
    return southwest.distance_to(sw_east);
}

double BoundingBox::height_km() const {
    Coordinates sw_north{northeast.latitude, southwest.longitude};
    return southwest.distance_to(sw_north);
}

// TerrainCell implementation
double TerrainCell::get_mobility_cost(MobilityClass mobility) const {
    if (is_impassable) return std::numeric_limits<double>::infinity();

    double base_cost = 1.0;

    // Terrain type effects
    switch (primary_type) {
        case TerrainType::Open:
            base_cost = 1.0;
            break;
        case TerrainType::Road:
            base_cost = 0.5;
            break;
        case TerrainType::Forest:
            base_cost = 2.0;
            break;
        case TerrainType::Urban:
            base_cost = 1.5 + urban_density;
            break;
        case TerrainType::Mountain:
            base_cost = 4.0;
            break;
        case TerrainType::Marsh:
            base_cost = 3.0;
            break;
        case TerrainType::Desert:
            base_cost = 1.2;
            break;
        case TerrainType::Water:
            base_cost = std::numeric_limits<double>::infinity();
            break;
        case TerrainType::Bridge:
            base_cost = 0.6;
            break;
    }

    // Mobility class modifiers
    switch (mobility) {
        case MobilityClass::Foot:
            if (primary_type == TerrainType::Mountain) base_cost *= 0.7;
            if (primary_type == TerrainType::Forest) base_cost *= 0.8;
            if (primary_type == TerrainType::Urban) base_cost *= 0.6;
            break;
        case MobilityClass::Wheeled:
            if (primary_type == TerrainType::Forest) base_cost *= 1.5;
            if (primary_type == TerrainType::Mountain) base_cost *= 2.0;
            if (primary_type == TerrainType::Marsh) base_cost = std::numeric_limits<double>::infinity();
            break;
        case MobilityClass::Tracked:
            if (primary_type == TerrainType::Marsh) base_cost *= 1.5;
            if (primary_type == TerrainType::Urban) base_cost *= 1.3;
            break;
        case MobilityClass::Rotary:
        case MobilityClass::FixedWing:
            base_cost = 1.0;  // Air units ignore terrain
            break;
    }

    return base_cost;
}

double TerrainCell::get_defense_modifier() const {
    double modifier = 1.0;

    switch (cover) {
        case CoverLevel::None: modifier = 1.0; break;
        case CoverLevel::Light: modifier = 1.2; break;
        case CoverLevel::Medium: modifier = 1.5; break;
        case CoverLevel::Heavy: modifier = 2.0; break;
        case CoverLevel::Fortified: modifier = 3.0; break;
    }

    if (primary_type == TerrainType::Urban) {
        modifier *= (1.0 + urban_density * 0.5);
    }

    return modifier;
}

double TerrainCell::get_attack_modifier() const {
    double modifier = 1.0;

    // Attacking from elevation advantage
    // (This would be computed relative to target)

    // Urban terrain reduces attack effectiveness
    if (primary_type == TerrainType::Urban) {
        modifier *= 0.8;
    }

    return modifier;
}

double TerrainCell::get_detection_modifier() const {
    return 1.0 - concealment;
}

// TerrainEngine private implementation
class TerrainEngine::Impl {
public:
    // Terrain data grid
    std::vector<std::vector<TerrainCell>> grid;
    int grid_width = 0;
    int grid_height = 0;
    BoundingBox bounds;
    double cell_size_km;
    double resolution_m = 100.0;
    bool gdal_initialized = false;

    Impl() {
#ifdef KARKAS_HAS_GDAL
        // Initialize GDAL once
        if (!gdal_initialized) {
            GDALAllRegister();
            gdal_initialized = true;
        }
#endif
    }

    ~Impl() = default;

    // Convert TerrainType integer to enum
    static TerrainType int_to_terrain_type(int value) {
        switch (value) {
            case 0: return TerrainType::Open;
            case 1: return TerrainType::Forest;
            case 2: return TerrainType::Urban;
            case 3: return TerrainType::Water;
            case 4: return TerrainType::Mountain;
            case 5: return TerrainType::Marsh;
            case 6: return TerrainType::Desert;
            case 7: return TerrainType::Road;
            case 8: return TerrainType::Bridge;
            default: return TerrainType::Open;
        }
    }

    // Convert CoverLevel integer to enum
    static CoverLevel int_to_cover_level(int value) {
        switch (value) {
            case 0: return CoverLevel::None;
            case 1: return CoverLevel::Light;
            case 2: return CoverLevel::Medium;
            case 3: return CoverLevel::Heavy;
            case 4: return CoverLevel::Fortified;
            default: return CoverLevel::None;
        }
    }

    bool load_geopackage([[maybe_unused]] const std::string& gpkg_path) {
#ifdef KARKAS_HAS_GDAL
        // Open the GeoPackage as a vector dataset
        GDALDataset* dataset = static_cast<GDALDataset*>(
            GDALOpenEx(gpkg_path.c_str(), GDAL_OF_VECTOR | GDAL_OF_READONLY,
                       nullptr, nullptr, nullptr));

        if (dataset == nullptr) {
            return false;
        }

        // Get the terrain_cells layer
        OGRLayer* layer = dataset->GetLayerByName("terrain_cells");
        if (layer == nullptr) {
            GDALClose(dataset);
            return false;
        }

        // Get layer extent for bounds
        OGREnvelope extent;
        if (layer->GetExtent(&extent) != OGRERR_NONE) {
            GDALClose(dataset);
            return false;
        }

        bounds.southwest = {extent.MinY, extent.MinX};  // lat, lon
        bounds.northeast = {extent.MaxY, extent.MaxX};

        // Count features to pre-allocate
        int64_t feature_count = layer->GetFeatureCount();
        if (feature_count <= 0) {
            GDALClose(dataset);
            return false;
        }

        // Read all cells into a map by grid position
        std::unordered_map<int64_t, TerrainCell> cell_map;
        double min_lat = extent.MaxY, max_lat = extent.MinY;
        double min_lon = extent.MaxX, max_lon = extent.MinX;

        layer->ResetReading();
        OGRFeature* feature;
        while ((feature = layer->GetNextFeature()) != nullptr) {
            TerrainCell cell;

            // Read coordinates
            int lat_idx = feature->GetFieldIndex("center_lat");
            int lon_idx = feature->GetFieldIndex("center_lon");

            if (lat_idx >= 0 && lon_idx >= 0) {
                cell.center.latitude = feature->GetFieldAsDouble(lat_idx);
                cell.center.longitude = feature->GetFieldAsDouble(lon_idx);
            } else {
                // Try to get center from geometry
                OGRGeometry* geom = feature->GetGeometryRef();
                if (geom != nullptr) {
                    OGREnvelope cell_env;
                    geom->getEnvelope(&cell_env);
                    cell.center.latitude = (cell_env.MinY + cell_env.MaxY) / 2.0;
                    cell.center.longitude = (cell_env.MinX + cell_env.MaxX) / 2.0;
                }
            }

            // Read terrain properties
            int elev_idx = feature->GetFieldIndex("elevation_m");
            if (elev_idx >= 0) {
                cell.elevation_m = feature->GetFieldAsDouble(elev_idx);
            }

            int ptype_idx = feature->GetFieldIndex("primary_type");
            if (ptype_idx >= 0) {
                cell.primary_type = int_to_terrain_type(feature->GetFieldAsInteger(ptype_idx));
            }

            int stype_idx = feature->GetFieldIndex("secondary_type");
            if (stype_idx >= 0 && feature->IsFieldSetAndNotNull(stype_idx)) {
                cell.secondary_type = int_to_terrain_type(feature->GetFieldAsInteger(stype_idx));
            }

            int cover_idx = feature->GetFieldIndex("cover");
            if (cover_idx >= 0) {
                cell.cover = int_to_cover_level(feature->GetFieldAsInteger(cover_idx));
            }

            int conc_idx = feature->GetFieldIndex("concealment");
            if (conc_idx >= 0) {
                cell.concealment = feature->GetFieldAsDouble(conc_idx);
            }

            int urban_idx = feature->GetFieldIndex("urban_density");
            if (urban_idx >= 0) {
                cell.urban_density = feature->GetFieldAsDouble(urban_idx);
            }

            int pop_idx = feature->GetFieldIndex("population");
            if (pop_idx >= 0) {
                cell.population = static_cast<uint32_t>(feature->GetFieldAsInteger64(pop_idx));
            }

            int road_idx = feature->GetFieldIndex("is_road");
            if (road_idx >= 0) {
                cell.is_road = feature->GetFieldAsInteger(road_idx) != 0;
            }

            int bridge_idx = feature->GetFieldIndex("is_bridge");
            if (bridge_idx >= 0) {
                cell.is_bridge = feature->GetFieldAsInteger(bridge_idx) != 0;
            }

            int impass_idx = feature->GetFieldIndex("is_impassable");
            if (impass_idx >= 0) {
                cell.is_impassable = feature->GetFieldAsInteger(impass_idx) != 0;
            }

            int res_idx = feature->GetFieldIndex("resolution_m");
            if (res_idx >= 0) {
                resolution_m = feature->GetFieldAsDouble(res_idx);
            }

            // Track actual bounds
            min_lat = std::min(min_lat, cell.center.latitude);
            max_lat = std::max(max_lat, cell.center.latitude);
            min_lon = std::min(min_lon, cell.center.longitude);
            max_lon = std::max(max_lon, cell.center.longitude);

            // Store with hash key
            int64_t key = coord_to_hash(cell.center.latitude, cell.center.longitude);
            cell_map[key] = cell;

            OGRFeature::DestroyFeature(feature);
        }

        GDALClose(dataset);

        if (cell_map.empty()) {
            return false;
        }

        // Update bounds from actual data
        bounds.southwest = {min_lat, min_lon};
        bounds.northeast = {max_lat, max_lon};

        // Calculate grid dimensions
        cell_size_km = resolution_m / 1000.0;
        grid_width = static_cast<int>(bounds.width_km() / cell_size_km) + 1;
        grid_height = static_cast<int>(bounds.height_km() / cell_size_km) + 1;

        // Initialize grid
        grid.resize(grid_height);
        for (int y = 0; y < grid_height; ++y) {
            grid[y].resize(grid_width);
        }

        // Populate grid from cell map
        for (const auto& [key, cell] : cell_map) {
            auto [x, y] = coord_to_grid_internal(cell.center);
            if (x >= 0 && x < grid_width && y >= 0 && y < grid_height) {
                grid[y][x] = cell;
            }
        }

        // Fill any gaps with interpolated/default values
        fill_grid_gaps();

        return true;
#else
        // GDAL not available, return false to trigger fallback
        return false;
#endif
    }

    int64_t coord_to_hash(double lat, double lon) const {
        // Hash coordinates at resolution precision
        int lat_key = static_cast<int>(lat * 100000);  // ~1m precision
        int lon_key = static_cast<int>(lon * 100000);
        return (static_cast<int64_t>(lat_key) << 32) | (lon_key & 0xFFFFFFFF);
    }

    std::pair<int, int> coord_to_grid_internal(const Coordinates& coord) const {
        double norm_x = (coord.longitude - bounds.southwest.longitude) /
                       (bounds.northeast.longitude - bounds.southwest.longitude);
        double norm_y = (coord.latitude - bounds.southwest.latitude) /
                       (bounds.northeast.latitude - bounds.southwest.latitude);

        int x = static_cast<int>(norm_x * grid_width);
        int y = static_cast<int>(norm_y * grid_height);

        return {x, y};
    }

    void fill_grid_gaps() {
        // Fill empty cells with default terrain based on neighbors
        for (int y = 0; y < grid_height; ++y) {
            for (int x = 0; x < grid_width; ++x) {
                auto& cell = grid[y][x];

                // Check if cell is uninitialized (center coords are 0,0)
                if (cell.center.latitude == 0.0 && cell.center.longitude == 0.0) {
                    // Calculate expected center
                    double lat = bounds.southwest.latitude +
                                (bounds.northeast.latitude - bounds.southwest.latitude) * y / grid_height;
                    double lon = bounds.southwest.longitude +
                                (bounds.northeast.longitude - bounds.southwest.longitude) * x / grid_width;

                    cell.center = {lat, lon};

                    // Copy from nearest neighbor if available
                    bool found_neighbor = false;
                    for (int dy = -1; dy <= 1 && !found_neighbor; ++dy) {
                        for (int dx = -1; dx <= 1 && !found_neighbor; ++dx) {
                            if (dx == 0 && dy == 0) continue;
                            int nx = x + dx, ny = y + dy;
                            if (nx >= 0 && nx < grid_width && ny >= 0 && ny < grid_height) {
                                const auto& neighbor = grid[ny][nx];
                                if (neighbor.center.latitude != 0.0 || neighbor.center.longitude != 0.0) {
                                    cell.elevation_m = neighbor.elevation_m;
                                    cell.primary_type = neighbor.primary_type;
                                    cell.cover = neighbor.cover;
                                    cell.concealment = neighbor.concealment;
                                    found_neighbor = true;
                                }
                            }
                        }
                    }

                    // Default values if no neighbor
                    if (!found_neighbor) {
                        cell.primary_type = TerrainType::Open;
                        cell.cover = CoverLevel::None;
                        cell.concealment = 0.1;
                        cell.elevation_m = 200.0;
                    }
                }
            }
        }
    }

    bool load_geopackage_region([[maybe_unused]] const std::string& gpkg_path,
                                [[maybe_unused]] const BoundingBox& region) {
#ifdef KARKAS_HAS_GDAL
        // Open the GeoPackage as a vector dataset
        GDALDataset* dataset = static_cast<GDALDataset*>(
            GDALOpenEx(gpkg_path.c_str(), GDAL_OF_VECTOR | GDAL_OF_READONLY,
                       nullptr, nullptr, nullptr));

        if (dataset == nullptr) {
            return false;
        }

        // Get the terrain_cells layer
        OGRLayer* layer = dataset->GetLayerByName("terrain_cells");
        if (layer == nullptr) {
            GDALClose(dataset);
            return false;
        }

        // Set spatial filter to load only the requested region
        layer->SetSpatialFilterRect(
            region.southwest.longitude,  // minX
            region.southwest.latitude,   // minY
            region.northeast.longitude,  // maxX
            region.northeast.latitude    // maxY
        );

        bounds = region;

        // Count features in region
        int64_t feature_count = layer->GetFeatureCount();
        if (feature_count <= 0) {
            GDALClose(dataset);
            return false;
        }

        // Read cells into map
        std::unordered_map<int64_t, TerrainCell> cell_map;

        layer->ResetReading();
        OGRFeature* feature;
        while ((feature = layer->GetNextFeature()) != nullptr) {
            TerrainCell cell;

            // Read coordinates
            int lat_idx = feature->GetFieldIndex("center_lat");
            int lon_idx = feature->GetFieldIndex("center_lon");

            if (lat_idx >= 0 && lon_idx >= 0) {
                cell.center.latitude = feature->GetFieldAsDouble(lat_idx);
                cell.center.longitude = feature->GetFieldAsDouble(lon_idx);
            } else {
                OGRGeometry* geom = feature->GetGeometryRef();
                if (geom != nullptr) {
                    OGREnvelope cell_env;
                    geom->getEnvelope(&cell_env);
                    cell.center.latitude = (cell_env.MinY + cell_env.MaxY) / 2.0;
                    cell.center.longitude = (cell_env.MinX + cell_env.MaxX) / 2.0;
                }
            }

            // Read terrain properties
            int elev_idx = feature->GetFieldIndex("elevation_m");
            if (elev_idx >= 0) {
                cell.elevation_m = feature->GetFieldAsDouble(elev_idx);
            }

            int ptype_idx = feature->GetFieldIndex("primary_type");
            if (ptype_idx >= 0) {
                cell.primary_type = int_to_terrain_type(feature->GetFieldAsInteger(ptype_idx));
            }

            int stype_idx = feature->GetFieldIndex("secondary_type");
            if (stype_idx >= 0 && feature->IsFieldSetAndNotNull(stype_idx)) {
                cell.secondary_type = int_to_terrain_type(feature->GetFieldAsInteger(stype_idx));
            }

            int cover_idx = feature->GetFieldIndex("cover");
            if (cover_idx >= 0) {
                cell.cover = int_to_cover_level(feature->GetFieldAsInteger(cover_idx));
            }

            int conc_idx = feature->GetFieldIndex("concealment");
            if (conc_idx >= 0) {
                cell.concealment = feature->GetFieldAsDouble(conc_idx);
            }

            int urban_idx = feature->GetFieldIndex("urban_density");
            if (urban_idx >= 0) {
                cell.urban_density = feature->GetFieldAsDouble(urban_idx);
            }

            int pop_idx = feature->GetFieldIndex("population");
            if (pop_idx >= 0) {
                cell.population = static_cast<uint32_t>(feature->GetFieldAsInteger64(pop_idx));
            }

            int road_idx = feature->GetFieldIndex("is_road");
            if (road_idx >= 0) {
                cell.is_road = feature->GetFieldAsInteger(road_idx) != 0;
            }

            int bridge_idx = feature->GetFieldIndex("is_bridge");
            if (bridge_idx >= 0) {
                cell.is_bridge = feature->GetFieldAsInteger(bridge_idx) != 0;
            }

            int impass_idx = feature->GetFieldIndex("is_impassable");
            if (impass_idx >= 0) {
                cell.is_impassable = feature->GetFieldAsInteger(impass_idx) != 0;
            }

            int res_idx = feature->GetFieldIndex("resolution_m");
            if (res_idx >= 0) {
                resolution_m = feature->GetFieldAsDouble(res_idx);
            }

            int64_t key = coord_to_hash(cell.center.latitude, cell.center.longitude);
            cell_map[key] = cell;

            OGRFeature::DestroyFeature(feature);
        }

        GDALClose(dataset);

        if (cell_map.empty()) {
            return false;
        }

        // Calculate grid dimensions
        cell_size_km = resolution_m / 1000.0;
        grid_width = static_cast<int>(bounds.width_km() / cell_size_km) + 1;
        grid_height = static_cast<int>(bounds.height_km() / cell_size_km) + 1;

        // Initialize grid
        grid.resize(grid_height);
        for (int y = 0; y < grid_height; ++y) {
            grid[y].resize(grid_width);
        }

        // Populate grid from cell map
        for (const auto& [key, cell] : cell_map) {
            auto [x, y] = coord_to_grid_internal(cell.center);
            if (x >= 0 && x < grid_width && y >= 0 && y < grid_height) {
                grid[y][x] = cell;
            }
        }

        fill_grid_gaps();
        return true;
#else
        // GDAL not available
        return false;
#endif
    }

    void generate_synthetic_terrain(const BoundingBox& b, double resolution_km) {
        bounds = b;
        cell_size_km = resolution_km;

        grid_width = static_cast<int>(b.width_km() / resolution_km) + 1;
        grid_height = static_cast<int>(b.height_km() / resolution_km) + 1;

        grid.resize(grid_height);
        for (int y = 0; y < grid_height; ++y) {
            grid[y].resize(grid_width);
            for (int x = 0; x < grid_width; ++x) {
                auto& cell = grid[y][x];

                double lat = b.southwest.latitude +
                            (b.northeast.latitude - b.southwest.latitude) * y / grid_height;
                double lon = b.southwest.longitude +
                            (b.northeast.longitude - b.southwest.longitude) * x / grid_width;

                cell.center = {lat, lon};

                // Generate pseudo-random but deterministic terrain
                double noise = std::sin(lat * 100) * std::cos(lon * 100);
                cell.elevation_m = 200 + noise * 100;

                // Assign terrain types based on position
                double terrain_noise = std::sin(lat * 50 + lon * 30);
                if (terrain_noise > 0.7) {
                    cell.primary_type = TerrainType::Forest;
                    cell.cover = CoverLevel::Heavy;
                    cell.concealment = 0.8;
                } else if (terrain_noise > 0.3) {
                    cell.primary_type = TerrainType::Open;
                    cell.cover = CoverLevel::None;
                    cell.concealment = 0.1;
                } else if (terrain_noise > -0.3) {
                    cell.primary_type = TerrainType::Urban;
                    cell.urban_density = 0.5 + terrain_noise;
                    cell.cover = CoverLevel::Medium;
                    cell.concealment = 0.5;
                    cell.population = static_cast<uint32_t>(10000 * (0.5 + terrain_noise));
                } else {
                    cell.primary_type = TerrainType::Mountain;
                    cell.elevation_m += 500;
                    cell.cover = CoverLevel::Medium;
                    cell.concealment = 0.3;
                }

                // Add some roads
                if (x % 10 == 0 || y % 10 == 0) {
                    cell.is_road = true;
                    cell.secondary_type = cell.primary_type;
                    cell.primary_type = TerrainType::Road;
                }

                cell.is_impassable = false;
            }
        }
    }

    TerrainCell& get_cell_at(int x, int y) {
        x = std::clamp(x, 0, grid_width - 1);
        y = std::clamp(y, 0, grid_height - 1);
        return grid[y][x];
    }

    const TerrainCell& get_cell_at(int x, int y) const {
        int cx = std::clamp(x, 0, grid_width - 1);
        int cy = std::clamp(y, 0, grid_height - 1);
        return grid[cy][cx];
    }

    std::pair<int, int> coord_to_grid(const Coordinates& coord) const {
        double norm_x = (coord.longitude - bounds.southwest.longitude) /
                       (bounds.northeast.longitude - bounds.southwest.longitude);
        double norm_y = (coord.latitude - bounds.southwest.latitude) /
                       (bounds.northeast.latitude - bounds.southwest.latitude);

        int x = static_cast<int>(norm_x * grid_width);
        int y = static_cast<int>(norm_y * grid_height);

        return {x, y};
    }
};

TerrainEngine::TerrainEngine()
    : impl_(std::make_unique<Impl>()),
      resolution_m_(30.0),
      loaded_(false) {}

TerrainEngine::~TerrainEngine() = default;

bool TerrainEngine::load_region(const BoundingBox& bounds, const std::string& data_path) {
    bounds_ = bounds;

    // Try to load from GeoPackage if path ends with .gpkg
    if (data_path.size() >= 5 &&
        data_path.substr(data_path.size() - 5) == ".gpkg") {
        if (impl_->load_geopackage_region(data_path, bounds)) {
            bounds_ = impl_->bounds;
            resolution_m_ = impl_->resolution_m;
            loaded_ = true;
            return true;
        }
    }

    // Fall back to synthetic terrain
    impl_->generate_synthetic_terrain(bounds, resolution_m_ / 1000.0);
    loaded_ = true;
    return true;
}

bool TerrainEngine::load_from_geopackage(const std::string& gpkg_path) {
    // Try GDAL-based loading
    if (impl_->load_geopackage(gpkg_path)) {
        bounds_ = impl_->bounds;
        resolution_m_ = impl_->resolution_m;
        loaded_ = true;
        return true;
    }

    // Fall back to synthetic terrain for development/testing
    BoundingBox default_bounds{
        {50.0, 9.0},   // SW corner (roughly Fulda Gap area)
        {51.0, 10.5}   // NE corner
    };
    return load_region(default_bounds, gpkg_path);
}

void TerrainEngine::set_resolution(double meters) {
    resolution_m_ = meters;
}

TerrainCell TerrainEngine::get_cell(const Coordinates& coord) const {
    if (!loaded_) {
        return TerrainCell{};
    }

    auto [x, y] = impl_->coord_to_grid(coord);
    return impl_->get_cell_at(x, y);
}

std::vector<TerrainCell> TerrainEngine::get_cells_in_radius(
    const Coordinates& center, double radius_km) const {

    std::vector<TerrainCell> result;
    if (!loaded_) return result;

    double cell_size_km = resolution_m_ / 1000.0;
    int cells_radius = static_cast<int>(radius_km / cell_size_km) + 1;

    auto [cx, cy] = impl_->coord_to_grid(center);

    for (int dy = -cells_radius; dy <= cells_radius; ++dy) {
        for (int dx = -cells_radius; dx <= cells_radius; ++dx) {
            int x = cx + dx;
            int y = cy + dy;

            if (x >= 0 && x < impl_->grid_width &&
                y >= 0 && y < impl_->grid_height) {

                const auto& cell = impl_->get_cell_at(x, y);
                if (center.distance_to(cell.center) <= radius_km) {
                    result.push_back(cell);
                }
            }
        }
    }

    return result;
}

std::vector<TerrainCell> TerrainEngine::get_cells_in_box(const BoundingBox& box) const {
    std::vector<TerrainCell> result;
    if (!loaded_) return result;

    auto [x1, y1] = impl_->coord_to_grid(box.southwest);
    auto [x2, y2] = impl_->coord_to_grid(box.northeast);

    for (int y = y1; y <= y2; ++y) {
        for (int x = x1; x <= x2; ++x) {
            if (x >= 0 && x < impl_->grid_width &&
                y >= 0 && y < impl_->grid_height) {
                result.push_back(impl_->get_cell_at(x, y));
            }
        }
    }

    return result;
}

double TerrainEngine::get_elevation(const Coordinates& coord) const {
    return get_cell(coord).elevation_m;
}

TerrainType TerrainEngine::get_terrain_type(const Coordinates& coord) const {
    return get_cell(coord).primary_type;
}

LOSResult TerrainEngine::calculate_los(const Coordinates& from, const Coordinates& to,
                                       double observer_height_m,
                                       double target_height_m) const {
    LOSResult result;
    result.distance_km = from.distance_to(to);
    result.has_los = true;
    result.terrain_screening = 0.0;

    if (!loaded_) {
        return result;
    }

    // Sample points along the line
    int num_samples = static_cast<int>(result.distance_km / (resolution_m_ / 1000.0)) + 1;
    num_samples = std::max(num_samples, 10);

    double observer_elev = get_elevation(from) + observer_height_m;
    double target_elev = get_elevation(to) + target_height_m;

    // Calculate LOS line slope
    double elev_diff = target_elev - observer_elev;
    double slope = elev_diff / result.distance_km;

    for (int i = 1; i < num_samples - 1; ++i) {
        double t = static_cast<double>(i) / num_samples;

        // Interpolate position
        Coordinates sample_pos{
            from.latitude + t * (to.latitude - from.latitude),
            from.longitude + t * (to.longitude - from.longitude)
        };

        double sample_dist = from.distance_to(sample_pos);
        double los_height_at_point = observer_elev + slope * sample_dist;
        double terrain_height = get_elevation(sample_pos);

        // Check vegetation/urban screening
        auto cell = get_cell(sample_pos);
        if (cell.primary_type == TerrainType::Forest) {
            terrain_height += 15.0;  // Tree canopy
        } else if (cell.primary_type == TerrainType::Urban) {
            terrain_height += 10.0 + cell.urban_density * 20.0;  // Buildings
        }

        if (terrain_height > los_height_at_point) {
            result.has_los = false;
            result.blocking_points.push_back(sample_pos);
            result.terrain_screening += 1.0 / num_samples;
        }
    }

    return result;
}

LOSResult TerrainEngine::calculate_sensor_los(const Coordinates& from, const Coordinates& to,
                                              SensorType sensor_type) const {
    auto result = calculate_los(from, to);

    // Modify based on sensor type
    switch (sensor_type) {
        case SensorType::Thermal:
            // Thermal can see through light vegetation
            if (result.terrain_screening < 0.3) {
                result.has_los = true;
            }
            break;
        case SensorType::Radar:
            // Radar blocked by terrain but sees through vegetation
            result.terrain_screening *= 0.5;
            break;
        case SensorType::SignalsIntel:
        case SensorType::Acoustic:
            // These don't require LOS
            result.has_los = true;
            result.terrain_screening = 0;
            break;
        case SensorType::Satellite:
            // Overhead view, only blocked by heavy cover
            result.has_los = true;
            result.terrain_screening *= 0.3;
            break;
        default:
            break;
    }

    return result;
}

double TerrainEngine::get_mobility_cost(const Coordinates& coord, MobilityClass mobility) const {
    return get_cell(coord).get_mobility_cost(mobility);
}

bool TerrainEngine::is_passable(const Coordinates& coord, MobilityClass mobility) const {
    double cost = get_mobility_cost(coord, mobility);
    return std::isfinite(cost);
}

std::optional<Path> TerrainEngine::find_path(const Coordinates& from, const Coordinates& to,
                                             MobilityClass mobility,
                                             RoutePreference preference) const {
    if (!loaded_) return std::nullopt;

    // A* pathfinding implementation
    struct Node {
        int x, y;
        double g_cost;  // Cost from start
        double h_cost;  // Heuristic to goal
        double f_cost() const { return g_cost + h_cost; }
        int parent_x, parent_y;

        bool operator>(const Node& other) const {
            return f_cost() > other.f_cost();
        }
    };

    auto [start_x, start_y] = impl_->coord_to_grid(from);
    auto [end_x, end_y] = impl_->coord_to_grid(to);

    std::priority_queue<Node, std::vector<Node>, std::greater<Node>> open_set;
    std::set<std::pair<int, int>> closed_set;
    std::vector<std::vector<std::pair<int, int>>> came_from(
        impl_->grid_height, std::vector<std::pair<int, int>>(impl_->grid_width, {-1, -1}));
    std::vector<std::vector<double>> g_score(
        impl_->grid_height, std::vector<double>(impl_->grid_width,
            std::numeric_limits<double>::infinity()));

    g_score[start_y][start_x] = 0;

    Coordinates goal_coord = impl_->get_cell_at(end_x, end_y).center;
    double initial_h = from.distance_to(goal_coord);

    open_set.push({start_x, start_y, 0, initial_h, -1, -1});

    const int dx[] = {-1, 0, 1, -1, 1, -1, 0, 1};
    const int dy[] = {-1, -1, -1, 0, 0, 1, 1, 1};
    const double dist_mult[] = {1.414, 1.0, 1.414, 1.0, 1.0, 1.414, 1.0, 1.414};

    while (!open_set.empty()) {
        Node current = open_set.top();
        open_set.pop();

        if (current.x == end_x && current.y == end_y) {
            // Reconstruct path
            Path path;
            path.total_distance_km = 0;
            path.total_time_hours = 0;
            path.uses_roads = false;

            int cx = end_x, cy = end_y;
            std::vector<std::pair<int, int>> coords;

            while (cx != -1 && cy != -1) {
                coords.push_back({cx, cy});
                auto [px, py] = came_from[cy][cx];
                cx = px;
                cy = py;
            }

            std::reverse(coords.begin(), coords.end());

            for (size_t i = 1; i < coords.size(); ++i) {
                const auto& cell_from = impl_->get_cell_at(coords[i-1].first, coords[i-1].second);
                const auto& cell_to = impl_->get_cell_at(coords[i].first, coords[i].second);

                PathSegment seg;
                seg.from = cell_from.center;
                seg.to = cell_to.center;
                seg.distance_km = seg.from.distance_to(seg.to);
                seg.terrain = cell_to.primary_type;
                seg.cover_along_route = cell_to.cover;

                // Calculate travel time based on mobility
                double speed_kph = 30.0;  // Base speed
                switch (mobility) {
                    case MobilityClass::Foot: speed_kph = 5.0; break;
                    case MobilityClass::Wheeled: speed_kph = 60.0; break;
                    case MobilityClass::Tracked: speed_kph = 40.0; break;
                    case MobilityClass::Rotary: speed_kph = 200.0; break;
                    case MobilityClass::FixedWing: speed_kph = 500.0; break;
                }

                double cost = cell_to.get_mobility_cost(mobility);
                seg.travel_time_hours = seg.distance_km / (speed_kph / cost);

                path.segments.push_back(seg);
                path.total_distance_km += seg.distance_km;
                path.total_time_hours += seg.travel_time_hours;

                if (cell_to.is_road) path.uses_roads = true;
            }

            // Calculate average cover
            double total_cover = 0;
            for (const auto& seg : path.segments) {
                total_cover += static_cast<int>(seg.cover_along_route);
            }
            path.average_cover = total_cover / path.segments.size();

            return path;
        }

        if (closed_set.count({current.x, current.y})) continue;
        closed_set.insert({current.x, current.y});

        for (int i = 0; i < 8; ++i) {
            int nx = current.x + dx[i];
            int ny = current.y + dy[i];

            if (nx < 0 || nx >= impl_->grid_width ||
                ny < 0 || ny >= impl_->grid_height) continue;

            if (closed_set.count({nx, ny})) continue;

            const auto& neighbor_cell = impl_->get_cell_at(nx, ny);
            double move_cost = neighbor_cell.get_mobility_cost(mobility);

            if (!std::isfinite(move_cost)) continue;

            double cell_dist = impl_->cell_size_km * dist_mult[i];
            double tentative_g = current.g_cost + cell_dist * move_cost;

            // Route preference modifiers
            if (preference == RoutePreference::Covered) {
                double cover_bonus = static_cast<int>(neighbor_cell.cover) * 0.1;
                tentative_g *= (1.0 - cover_bonus);
            } else if (preference == RoutePreference::Fastest && neighbor_cell.is_road) {
                tentative_g *= 0.5;
            }

            if (tentative_g < g_score[ny][nx]) {
                came_from[ny][nx] = {current.x, current.y};
                g_score[ny][nx] = tentative_g;

                double h = neighbor_cell.center.distance_to(goal_coord);
                open_set.push({nx, ny, tentative_g, h, current.x, current.y});
            }
        }
    }

    return std::nullopt;  // No path found
}

std::optional<Path> TerrainEngine::find_path_avoiding(
    const Coordinates& from, const Coordinates& to,
    MobilityClass mobility,
    const std::vector<Coordinates>& avoid_points,
    double avoid_radius_km) const {

    // TODO: Implement avoidance-aware pathfinding
    // For now, use standard pathfinding
    return find_path(from, to, mobility, RoutePreference::Covered);
}

double TerrainEngine::calculate_area_cover(const std::vector<Coordinates>& polygon) const {
    // Simplified: get bounding box and sample cells
    if (polygon.empty()) return 0;

    double min_lat = polygon[0].latitude, max_lat = polygon[0].latitude;
    double min_lon = polygon[0].longitude, max_lon = polygon[0].longitude;

    for (const auto& p : polygon) {
        min_lat = std::min(min_lat, p.latitude);
        max_lat = std::max(max_lat, p.latitude);
        min_lon = std::min(min_lon, p.longitude);
        max_lon = std::max(max_lon, p.longitude);
    }

    BoundingBox box{{min_lat, min_lon}, {max_lat, max_lon}};
    auto cells = get_cells_in_box(box);

    double total_cover = 0;
    for (const auto& cell : cells) {
        total_cover += static_cast<int>(cell.cover);
    }

    return cells.empty() ? 0 : total_cover / cells.size();
}

std::vector<Coordinates> TerrainEngine::find_defensive_positions(
    const Coordinates& center, double radius_km, int max_positions) const {

    std::vector<std::pair<Coordinates, double>> candidates;

    auto cells = get_cells_in_radius(center, radius_km);
    for (const auto& cell : cells) {
        double score = cell.get_defense_modifier();
        score += cell.elevation_m / 100.0;  // Elevation bonus
        candidates.push_back({cell.center, score});
    }

    std::sort(candidates.begin(), candidates.end(),
              [](const auto& a, const auto& b) { return a.second > b.second; });

    std::vector<Coordinates> result;
    for (int i = 0; i < max_positions && i < static_cast<int>(candidates.size()); ++i) {
        result.push_back(candidates[i].first);
    }

    return result;
}

std::vector<Coordinates> TerrainEngine::find_observation_points(
    const Coordinates& center, double radius_km,
    const Coordinates& target_area) const {

    std::vector<std::pair<Coordinates, double>> candidates;

    auto cells = get_cells_in_radius(center, radius_km);
    for (const auto& cell : cells) {
        auto los = calculate_los(cell.center, target_area);
        if (los.has_los) {
            double score = cell.elevation_m / 100.0;
            score += cell.concealment;  // Good concealment for observer
            candidates.push_back({cell.center, score});
        }
    }

    std::sort(candidates.begin(), candidates.end(),
              [](const auto& a, const auto& b) { return a.second > b.second; });

    std::vector<Coordinates> result;
    for (int i = 0; i < 5 && i < static_cast<int>(candidates.size()); ++i) {
        result.push_back(candidates[i].first);
    }

    return result;
}

std::vector<Coordinates> TerrainEngine::get_urban_centers(const BoundingBox& box) const {
    std::vector<Coordinates> centers;

    auto cells = get_cells_in_box(box);
    for (const auto& cell : cells) {
        if (cell.primary_type == TerrainType::Urban && cell.population > 50000) {
            centers.push_back(cell.center);
        }
    }

    return centers;
}

uint32_t TerrainEngine::get_population_in_area(const std::vector<Coordinates>& polygon) const {
    // Simplified implementation
    if (polygon.empty()) return 0;

    double min_lat = polygon[0].latitude, max_lat = polygon[0].latitude;
    double min_lon = polygon[0].longitude, max_lon = polygon[0].longitude;

    for (const auto& p : polygon) {
        min_lat = std::min(min_lat, p.latitude);
        max_lat = std::max(max_lat, p.latitude);
        min_lon = std::min(min_lon, p.longitude);
        max_lon = std::max(max_lon, p.longitude);
    }

    BoundingBox box{{min_lat, min_lon}, {max_lat, max_lon}};
    auto cells = get_cells_in_box(box);

    uint32_t total = 0;
    for (const auto& cell : cells) {
        total += cell.population;
    }

    return total;
}

std::optional<Path> TerrainEngine::find_road_route(const Coordinates& from,
                                                   const Coordinates& to) const {
    // Find path preferring roads
    return find_path(from, to, MobilityClass::Wheeled, RoutePreference::Fastest);
}

std::vector<Coordinates> TerrainEngine::get_road_intersections(const BoundingBox& box) const {
    std::vector<Coordinates> intersections;

    auto cells = get_cells_in_box(box);
    for (size_t i = 0; i < cells.size(); ++i) {
        if (!cells[i].is_road) continue;

        // Count adjacent road cells
        auto [x, y] = impl_->coord_to_grid(cells[i].center);
        int road_neighbors = 0;

        for (int dx = -1; dx <= 1; ++dx) {
            for (int dy = -1; dy <= 1; ++dy) {
                if (dx == 0 && dy == 0) continue;
                int nx = x + dx, ny = y + dy;
                if (nx >= 0 && nx < impl_->grid_width &&
                    ny >= 0 && ny < impl_->grid_height) {
                    if (impl_->get_cell_at(nx, ny).is_road) {
                        road_neighbors++;
                    }
                }
            }
        }

        if (road_neighbors >= 3) {
            intersections.push_back(cells[i].center);
        }
    }

    return intersections;
}

std::vector<Coordinates> TerrainEngine::get_bridges(const BoundingBox& box) const {
    std::vector<Coordinates> bridges;

    auto cells = get_cells_in_box(box);
    for (const auto& cell : cells) {
        if (cell.is_bridge) {
            bridges.push_back(cell.center);
        }
    }

    return bridges;
}

TerrainEngine::TerrainAnalysis TerrainEngine::analyze_area(const BoundingBox& box) const {
    TerrainAnalysis analysis{};

    auto cells = get_cells_in_box(box);
    if (cells.empty()) return analysis;

    double sum_elev = 0;
    int forest_count = 0, urban_count = 0, open_count = 0, road_count = 0;

    for (const auto& cell : cells) {
        sum_elev += cell.elevation_m;

        switch (cell.primary_type) {
            case TerrainType::Forest: forest_count++; break;
            case TerrainType::Urban: urban_count++; break;
            case TerrainType::Open: open_count++; break;
            case TerrainType::Road: road_count++; break;
            default: break;
        }
    }

    double n = static_cast<double>(cells.size());
    analysis.average_elevation = sum_elev / n;
    analysis.percent_forest = 100.0 * forest_count / n;
    analysis.percent_urban = 100.0 * urban_count / n;
    analysis.percent_open = 100.0 * open_count / n;

    // Calculate elevation variance
    double sum_sq_diff = 0;
    for (const auto& cell : cells) {
        double diff = cell.elevation_m - analysis.average_elevation;
        sum_sq_diff += diff * diff;
    }
    analysis.elevation_variance = sum_sq_diff / n;

    // Road density
    double area_sq_km = box.width_km() * box.height_km();
    double road_km = road_count * (resolution_m_ / 1000.0);
    analysis.road_density_km_per_sq_km = road_km / area_sq_km;

    // Find key terrain (highest points, major intersections)
    std::vector<std::pair<Coordinates, double>> elevations;
    for (const auto& cell : cells) {
        elevations.push_back({cell.center, cell.elevation_m});
    }
    std::sort(elevations.begin(), elevations.end(),
              [](const auto& a, const auto& b) { return a.second > b.second; });

    for (int i = 0; i < 3 && i < static_cast<int>(elevations.size()); ++i) {
        analysis.key_terrain_features.push_back(elevations[i].first);
    }

    // Find choke points (narrow passages, bridges)
    analysis.choke_points = get_bridges(box);

    return analysis;
}

void TerrainEngine::apply_weather_effects(const Weather& weather) {
    // Modify terrain based on weather
    for (auto& row : impl_->grid) {
        for (auto& cell : row) {
            // Heavy rain makes ground softer
            if (weather.precipitation == Weather::Precipitation::Heavy) {
                if (cell.primary_type == TerrainType::Open) {
                    cell.primary_type = TerrainType::Marsh;
                }
            }
        }
    }
}

Coordinates Path::get_position_at_time(double hours) const {
    if (segments.empty()) return {};

    double accumulated_time = 0;
    for (const auto& seg : segments) {
        if (accumulated_time + seg.travel_time_hours >= hours) {
            double fraction = (hours - accumulated_time) / seg.travel_time_hours;
            return {
                seg.from.latitude + fraction * (seg.to.latitude - seg.from.latitude),
                seg.from.longitude + fraction * (seg.to.longitude - seg.from.longitude)
            };
        }
        accumulated_time += seg.travel_time_hours;
    }

    return segments.back().to;
}

// Weather modifiers
double Weather::get_visibility_modifier() const {
    double modifier = 1.0;

    switch (visibility) {
        case Visibility::Clear: modifier = 1.0; break;
        case Visibility::Haze: modifier = 0.8; break;
        case Visibility::Fog: modifier = 0.4; break;
        case Visibility::Smoke: modifier = 0.3; break;
    }

    switch (precipitation) {
        case Precipitation::None: break;
        case Precipitation::Light: modifier *= 0.9; break;
        case Precipitation::Moderate: modifier *= 0.7; break;
        case Precipitation::Heavy: modifier *= 0.5; break;
    }

    return modifier;
}

double Weather::get_mobility_modifier() const {
    switch (precipitation) {
        case Precipitation::None: return 1.0;
        case Precipitation::Light: return 0.95;
        case Precipitation::Moderate: return 0.8;
        case Precipitation::Heavy: return 0.6;
    }
    return 1.0;
}

double TimeOfDay::get_visibility_modifier() const {
    if (is_night()) return 0.2;
    if (is_twilight()) return 0.6;
    return 1.0;
}

int64_t TerrainEngine::coord_to_cache_key(const Coordinates& coord) const {
    int lat_key = static_cast<int>(coord.latitude * 1000);
    int lon_key = static_cast<int>(coord.longitude * 1000);
    return (static_cast<int64_t>(lat_key) << 32) | lon_key;
}

}  // namespace karkas
