#pragma once

#include "unit.hpp"
#include <unordered_map>
#include <functional>

namespace karkas {

class OrbatManager {
public:
    OrbatManager() = default;

    // Unit management
    void add_unit(std::unique_ptr<Unit> unit);
    void remove_unit(UnitId id);
    Unit* get_unit(UnitId id);
    const Unit* get_unit(UnitId id) const;
    bool has_unit(UnitId id) const;

    // Faction queries
    std::vector<Unit*> get_units_by_faction(Faction faction);
    std::vector<const Unit*> get_units_by_faction(Faction faction) const;

    // Type queries
    std::vector<Unit*> get_units_by_type(UnitType type);
    std::vector<Unit*> get_units_by_type(Faction faction, UnitType type);

    // Spatial queries
    std::vector<Unit*> get_units_in_radius(Coordinates center, double radius_km);
    std::vector<Unit*> get_units_in_radius(Coordinates center, double radius_km, Faction faction);
    std::vector<Unit*> get_units_in_box(const BoundingBox& box);

    // Hierarchy queries
    Unit* get_parent(const Unit& unit);
    std::vector<Unit*> get_subordinates(const Unit& unit);
    std::vector<Unit*> get_all_subordinates_recursive(const Unit& unit);
    Unit* get_higher_hq(const Unit& unit, Echelon min_echelon);

    // Command chain
    bool is_in_command_chain(const Unit& superior, const Unit& subordinate) const;
    std::vector<Unit*> get_command_chain(const Unit& unit);

    // Iteration
    void for_each_unit(std::function<void(Unit&)> fn);
    void for_each_unit(std::function<void(const Unit&)> fn) const;
    void for_each_unit_of_faction(Faction faction, std::function<void(Unit&)> fn);

    // Statistics
    size_t count_units() const { return units_.size(); }
    size_t count_units(Faction faction) const;
    size_t count_combat_effective(Faction faction) const;

    // Serialization
    std::string to_json() const;
    static OrbatManager from_json(const std::string& json);
    void load_from_yaml(const std::string& filepath);
    void save_to_yaml(const std::string& filepath) const;

private:
    std::unordered_map<UnitId, std::unique_ptr<Unit>> units_;

    // Spatial index for efficient queries (simple grid-based)
    void update_spatial_index(const Unit& unit);
    void rebuild_spatial_index();

    struct GridCell {
        std::vector<UnitId> unit_ids;
    };
    std::unordered_map<int64_t, GridCell> spatial_grid_;
    static constexpr double GRID_SIZE_KM = 10.0;

    int64_t coord_to_grid_key(const Coordinates& coord) const;
};

}  // namespace karkas
