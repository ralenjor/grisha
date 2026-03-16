#include "orbat_manager.hpp"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>

namespace karkas {

void OrbatManager::add_unit(std::unique_ptr<Unit> unit) {
    UnitId id = unit->get_id();
    update_spatial_index(*unit);
    units_[id] = std::move(unit);
}

void OrbatManager::remove_unit(UnitId id) {
    units_.erase(id);
    rebuild_spatial_index();
}

Unit* OrbatManager::get_unit(UnitId id) {
    auto it = units_.find(id);
    return it != units_.end() ? it->second.get() : nullptr;
}

const Unit* OrbatManager::get_unit(UnitId id) const {
    auto it = units_.find(id);
    return it != units_.end() ? it->second.get() : nullptr;
}

bool OrbatManager::has_unit(UnitId id) const {
    return units_.find(id) != units_.end();
}

std::vector<Unit*> OrbatManager::get_units_by_faction(Faction faction) {
    std::vector<Unit*> result;
    for (auto& [id, unit] : units_) {
        if (unit->get_faction() == faction) {
            result.push_back(unit.get());
        }
    }
    return result;
}

std::vector<const Unit*> OrbatManager::get_units_by_faction(Faction faction) const {
    std::vector<const Unit*> result;
    for (const auto& [id, unit] : units_) {
        if (unit->get_faction() == faction) {
            result.push_back(unit.get());
        }
    }
    return result;
}

std::vector<Unit*> OrbatManager::get_units_by_type(UnitType type) {
    std::vector<Unit*> result;
    for (auto& [id, unit] : units_) {
        if (unit->get_type() == type) {
            result.push_back(unit.get());
        }
    }
    return result;
}

std::vector<Unit*> OrbatManager::get_units_by_type(Faction faction, UnitType type) {
    std::vector<Unit*> result;
    for (auto& [id, unit] : units_) {
        if (unit->get_faction() == faction && unit->get_type() == type) {
            result.push_back(unit.get());
        }
    }
    return result;
}

int64_t OrbatManager::coord_to_grid_key(const Coordinates& coord) const {
    int lat_cell = static_cast<int>(coord.latitude * 111.0 / GRID_SIZE_KM);
    int lon_cell = static_cast<int>(coord.longitude * 111.0 * std::cos(coord.latitude * M_PI / 180.0) / GRID_SIZE_KM);
    return (static_cast<int64_t>(lat_cell) << 32) | static_cast<uint32_t>(lon_cell);
}

void OrbatManager::update_spatial_index(const Unit& unit) {
    int64_t key = coord_to_grid_key(unit.get_position());
    spatial_grid_[key].unit_ids.push_back(unit.get_id());
}

void OrbatManager::rebuild_spatial_index() {
    spatial_grid_.clear();
    for (const auto& [id, unit] : units_) {
        update_spatial_index(*unit);
    }
}

std::vector<Unit*> OrbatManager::get_units_in_radius(Coordinates center, double radius_km) {
    std::vector<Unit*> result;

    // Check grid cells that could contain units in radius
    int cell_radius = static_cast<int>(radius_km / GRID_SIZE_KM) + 1;
    int64_t center_key = coord_to_grid_key(center);
    int center_lat = static_cast<int>(center_key >> 32);
    int center_lon = static_cast<int>(center_key & 0xFFFFFFFF);

    for (int dlat = -cell_radius; dlat <= cell_radius; ++dlat) {
        for (int dlon = -cell_radius; dlon <= cell_radius; ++dlon) {
            int64_t key = (static_cast<int64_t>(center_lat + dlat) << 32) |
                         static_cast<uint32_t>(center_lon + dlon);

            auto it = spatial_grid_.find(key);
            if (it != spatial_grid_.end()) {
                for (const auto& unit_id : it->second.unit_ids) {
                    auto* unit = get_unit(unit_id);
                    if (unit && center.distance_to(unit->get_position()) <= radius_km) {
                        result.push_back(unit);
                    }
                }
            }
        }
    }

    return result;
}

std::vector<Unit*> OrbatManager::get_units_in_radius(Coordinates center, double radius_km, Faction faction) {
    auto all = get_units_in_radius(center, radius_km);
    std::vector<Unit*> result;

    for (auto* unit : all) {
        if (unit->get_faction() == faction) {
            result.push_back(unit);
        }
    }

    return result;
}

std::vector<Unit*> OrbatManager::get_units_in_box(const BoundingBox& box) {
    std::vector<Unit*> result;

    for (auto& [id, unit] : units_) {
        if (box.contains(unit->get_position())) {
            result.push_back(unit.get());
        }
    }

    return result;
}

Unit* OrbatManager::get_parent(const Unit& unit) {
    auto parent_id = unit.get_parent_id();
    if (!parent_id.has_value()) return nullptr;
    return get_unit(*parent_id);
}

std::vector<Unit*> OrbatManager::get_subordinates(const Unit& unit) {
    std::vector<Unit*> result;
    for (const auto& sub_id : unit.get_subordinates()) {
        auto* sub = get_unit(sub_id);
        if (sub) {
            result.push_back(sub);
        }
    }
    return result;
}

std::vector<Unit*> OrbatManager::get_all_subordinates_recursive(const Unit& unit) {
    std::vector<Unit*> result;

    std::function<void(const Unit&)> collect = [&](const Unit& u) {
        for (const auto& sub_id : u.get_subordinates()) {
            auto* sub = get_unit(sub_id);
            if (sub) {
                result.push_back(sub);
                collect(*sub);
            }
        }
    };

    collect(unit);
    return result;
}

Unit* OrbatManager::get_higher_hq(const Unit& unit, Echelon min_echelon) {
    auto* current = get_parent(unit);
    while (current) {
        if (current->get_echelon() >= min_echelon &&
            current->get_type() == UnitType::Headquarters) {
            return current;
        }
        current = get_parent(*current);
    }
    return nullptr;
}

bool OrbatManager::is_in_command_chain(const Unit& superior, const Unit& subordinate) const {
    const Unit* current = &subordinate;

    while (current) {
        if (current->get_id() == superior.get_id()) {
            return true;
        }

        auto parent_id = current->get_parent_id();
        if (!parent_id.has_value()) break;

        current = get_unit(*parent_id);
    }

    return false;
}

std::vector<Unit*> OrbatManager::get_command_chain(const Unit& unit) {
    std::vector<Unit*> chain;
    Unit* current = get_parent(unit);

    while (current) {
        chain.push_back(current);
        current = get_parent(*current);
    }

    return chain;
}

void OrbatManager::for_each_unit(std::function<void(Unit&)> fn) {
    for (auto& [id, unit] : units_) {
        fn(*unit);
    }
}

void OrbatManager::for_each_unit(std::function<void(const Unit&)> fn) const {
    for (const auto& [id, unit] : units_) {
        fn(*unit);
    }
}

void OrbatManager::for_each_unit_of_faction(Faction faction, std::function<void(Unit&)> fn) {
    for (auto& [id, unit] : units_) {
        if (unit->get_faction() == faction) {
            fn(*unit);
        }
    }
}

size_t OrbatManager::count_units(Faction faction) const {
    size_t count = 0;
    for (const auto& [id, unit] : units_) {
        if (unit->get_faction() == faction) {
            count++;
        }
    }
    return count;
}

size_t OrbatManager::count_combat_effective(Faction faction) const {
    size_t count = 0;
    for (const auto& [id, unit] : units_) {
        if (unit->get_faction() == faction && unit->is_combat_effective()) {
            count++;
        }
    }
    return count;
}

std::string OrbatManager::to_json() const {
    std::stringstream ss;
    ss << "{\n  \"units\": [\n";

    bool first = true;
    for (const auto& [id, unit] : units_) {
        if (!first) ss << ",\n";
        first = false;
        ss << "    " << unit->to_json();
    }

    ss << "\n  ]\n}";
    return ss.str();
}

void OrbatManager::load_from_yaml(const std::string& filepath) {
    // TODO: Implement YAML parsing
    // For now, create some sample units

    // Example Red force
    auto red_hq = std::make_unique<Unit>(
        "red_1mrd_hq", "1st Motor Rifle Division HQ",
        Faction::Red, UnitType::Headquarters, Echelon::Division);
    red_hq->set_position({50.5, 9.5});

    auto red_1bn = std::make_unique<Unit>(
        "red_1mrd_1bn", "1st Motor Rifle Battalion",
        Faction::Red, UnitType::Mechanized, Echelon::Battalion);
    red_1bn->set_position({50.45, 9.45});
    red_1bn->set_parent("red_1mrd_hq");

    auto red_2bn = std::make_unique<Unit>(
        "red_1mrd_2bn", "2nd Motor Rifle Battalion",
        Faction::Red, UnitType::Mechanized, Echelon::Battalion);
    red_2bn->set_position({50.48, 9.52});
    red_2bn->set_parent("red_1mrd_hq");

    auto red_tank = std::make_unique<Unit>(
        "red_1mrd_tank", "1st Tank Battalion",
        Faction::Red, UnitType::Armor, Echelon::Battalion);
    red_tank->set_position({50.52, 9.48});
    red_tank->set_parent("red_1mrd_hq");

    auto red_arty = std::make_unique<Unit>(
        "red_1mrd_arty", "1st Artillery Regiment",
        Faction::Red, UnitType::Artillery, Echelon::Regiment);
    red_arty->set_position({50.55, 9.4});
    red_arty->set_parent("red_1mrd_hq");

    // Example Blue force
    auto blue_hq = std::make_unique<Unit>(
        "blue_1ad_hq", "1st Armored Division HQ",
        Faction::Blue, UnitType::Headquarters, Echelon::Division);
    blue_hq->set_position({50.3, 10.0});

    auto blue_1bde = std::make_unique<Unit>(
        "blue_1bde", "1st Brigade Combat Team",
        Faction::Blue, UnitType::Mechanized, Echelon::Brigade);
    blue_1bde->set_position({50.35, 9.95});
    blue_1bde->set_parent("blue_1ad_hq");
    blue_1bde->set_posture(Posture::Defend);

    auto blue_2bde = std::make_unique<Unit>(
        "blue_2bde", "2nd Brigade Combat Team",
        Faction::Blue, UnitType::Armor, Echelon::Brigade);
    blue_2bde->set_position({50.28, 10.05});
    blue_2bde->set_parent("blue_1ad_hq");
    blue_2bde->set_posture(Posture::Defend);

    auto blue_recon = std::make_unique<Unit>(
        "blue_recon", "Division Cavalry Squadron",
        Faction::Blue, UnitType::Recon, Echelon::Battalion);
    blue_recon->set_position({50.4, 9.8});
    blue_recon->set_parent("blue_1ad_hq");
    blue_recon->set_posture(Posture::Recon);

    // Add to manager
    add_unit(std::move(red_hq));
    add_unit(std::move(red_1bn));
    add_unit(std::move(red_2bn));
    add_unit(std::move(red_tank));
    add_unit(std::move(red_arty));

    add_unit(std::move(blue_hq));
    add_unit(std::move(blue_1bde));
    add_unit(std::move(blue_2bde));
    add_unit(std::move(blue_recon));

    // Update subordinate lists
    if (auto* hq = get_unit("red_1mrd_hq")) {
        hq->add_subordinate("red_1mrd_1bn");
        hq->add_subordinate("red_1mrd_2bn");
        hq->add_subordinate("red_1mrd_tank");
        hq->add_subordinate("red_1mrd_arty");
    }

    if (auto* hq = get_unit("blue_1ad_hq")) {
        hq->add_subordinate("blue_1bde");
        hq->add_subordinate("blue_2bde");
        hq->add_subordinate("blue_recon");
    }
}

void OrbatManager::save_to_yaml(const std::string& filepath) const {
    std::ofstream file(filepath);
    file << "# KARKAS ORBAT Export\n\n";
    file << "units:\n";

    for (const auto& [id, unit] : units_) {
        file << "  - id: " << unit->get_id() << "\n";
        file << "    name: " << unit->get_name() << "\n";
        file << "    faction: " << (unit->get_faction() == Faction::Red ? "red" : "blue") << "\n";
        file << "    type: " << static_cast<int>(unit->get_type()) << "\n";
        file << "    echelon: " << static_cast<int>(unit->get_echelon()) << "\n";
        file << "    position: [" << unit->get_position().latitude << ", "
             << unit->get_position().longitude << "]\n";

        if (unit->get_parent_id().has_value()) {
            file << "    parent: " << *unit->get_parent_id() << "\n";
        }
        file << "\n";
    }
}

OrbatManager OrbatManager::from_json(const std::string& json) {
    // TODO: Implement JSON parsing
    return OrbatManager();
}

}  // namespace karkas
