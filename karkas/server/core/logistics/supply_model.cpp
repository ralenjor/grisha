#include "supply_model.hpp"
#include "../orbat_manager.hpp"
#include <algorithm>
#include <limits>
#include <cmath>

namespace karkas {

void SupplyModel::add_supply_point(SupplyPoint point) {
    supply_points_.push_back(std::move(point));
}

void SupplyModel::remove_supply_point(const std::string& id) {
    supply_points_.erase(
        std::remove_if(supply_points_.begin(), supply_points_.end(),
                      [&id](const SupplyPoint& sp) { return sp.id == id; }),
        supply_points_.end());
}

SupplyPoint* SupplyModel::get_supply_point(const std::string& id) {
    for (auto& sp : supply_points_) {
        if (sp.id == id) return &sp;
    }
    return nullptr;
}

void SupplyModel::add_supply_route(SupplyRoute route) {
    supply_routes_.push_back(std::move(route));
}

void SupplyModel::cut_route(const std::string& id) {
    for (auto& route : supply_routes_) {
        if (route.id == id) {
            route.is_cut = true;
            return;
        }
    }
}

void SupplyModel::restore_route(const std::string& id) {
    for (auto& route : supply_routes_) {
        if (route.id == id) {
            route.is_cut = false;
            return;
        }
    }
}

SupplyPoint* SupplyModel::find_nearest_depot(const Coordinates& pos, Faction faction) {
    SupplyPoint* nearest = nullptr;
    double min_dist = std::numeric_limits<double>::max();

    for (auto& sp : supply_points_) {
        if (sp.faction != faction) continue;

        double dist = pos.distance_to(sp.position);
        if (dist < min_dist) {
            min_dist = dist;
            nearest = &sp;
        }
    }

    return nearest;
}

const SupplyPoint* SupplyModel::find_nearest_depot(const Coordinates& pos, Faction faction) const {
    const SupplyPoint* nearest = nullptr;
    double min_dist = std::numeric_limits<double>::max();

    for (const auto& sp : supply_points_) {
        if (sp.faction != faction) continue;

        double dist = pos.distance_to(sp.position);
        if (dist < min_dist) {
            min_dist = dist;
            nearest = &sp;
        }
    }

    return nearest;
}

double SupplyModel::calculate_supply_distance(const Unit& unit) const {
    double min_dist = std::numeric_limits<double>::max();

    for (const auto& sp : supply_points_) {
        if (sp.faction != unit.get_faction()) continue;

        double dist = unit.get_position().distance_to(sp.position);
        min_dist = std::min(min_dist, dist);
    }

    return min_dist;
}

bool SupplyModel::is_unit_in_supply(const Unit& unit, double max_distance_km) const {
    // Use pathfinding-based LOC if terrain available
    if (terrain_) {
        LOCResult loc = calculate_loc(unit);
        return loc.has_valid_route && !loc.is_interdicted && loc.distance_km <= max_distance_km;
    }
    // Fallback to straight-line
    return calculate_supply_distance(unit) <= max_distance_km;
}

// ============================================================================
// LOC (Line of Communication) Calculation - Pathfinding-based
// ============================================================================

std::optional<Path> SupplyModel::calculate_supply_route(const Coordinates& from,
                                                         const Coordinates& to) const {
    if (!terrain_) return std::nullopt;

    // Try road route first (supply convoys prefer roads)
    auto road_path = terrain_->find_road_route(from, to);
    if (road_path.has_value()) {
        return road_path;
    }

    // Fall back to general path with wheeled mobility (supply trucks)
    return terrain_->find_path(from, to, MobilityClass::Wheeled, RoutePreference::Fastest);
}

double SupplyModel::calculate_route_distance(const std::vector<Coordinates>& waypoints) const {
    if (waypoints.size() < 2) return 0.0;

    double total = 0.0;
    for (size_t i = 1; i < waypoints.size(); ++i) {
        total += waypoints[i-1].distance_to(waypoints[i]);
    }
    return total;
}

LOCResult SupplyModel::calculate_loc_to_depot(const Unit& unit, const SupplyPoint& depot) const {
    LOCResult result;
    result.depot_id = depot.id;
    result.straight_line_km = unit.get_position().distance_to(depot.position);
    result.has_valid_route = false;
    result.is_interdicted = false;
    result.interdiction_strength = 0.0;

    // Check if straight-line is beyond maximum range
    if (result.straight_line_km > max_supply_range_km_) {
        result.distance_km = result.straight_line_km;
        return result;
    }

    // Calculate actual route via terrain
    if (terrain_) {
        auto path = calculate_supply_route(depot.position, unit.get_position());

        if (path.has_value()) {
            result.has_valid_route = true;
            result.distance_km = path->total_distance_km;

            // Extract waypoints from path segments
            result.route.push_back(depot.position);
            for (const auto& segment : path->segments) {
                result.route.push_back(segment.to);
            }

            // Check if route exceeds max range
            if (result.distance_km > max_supply_range_km_) {
                result.has_valid_route = false;
            }
        } else {
            // No path found
            result.distance_km = result.straight_line_km;
        }
    } else {
        // No terrain engine, use straight-line
        result.has_valid_route = true;
        result.distance_km = result.straight_line_km;
        result.route = {depot.position, unit.get_position()};
    }

    // Check for interdiction by enemy units
    if (result.has_valid_route && orbat_ && !result.route.empty()) {
        auto interdictors = get_interdicting_units(result.route, unit.get_faction(),
                                                    interdiction_radius_km_);
        result.interdicting_units = interdictors;
        result.is_interdicted = !interdictors.empty();

        if (result.is_interdicted) {
            // Calculate total interdiction strength
            for (const auto& unit_id : interdictors) {
                auto* enemy = orbat_->get_unit(unit_id);
                if (enemy) {
                    result.interdiction_strength += enemy->get_effective_combat_power();
                }
            }
        }
    }

    return result;
}

LOCResult SupplyModel::calculate_loc(const Unit& unit) const {
    LOCResult best_result;
    best_result.has_valid_route = false;
    best_result.distance_km = std::numeric_limits<double>::max();

    // Find best depot (shortest uninterdicted route, or shortest interdicted if all cut)
    LOCResult best_uninterdicted;
    best_uninterdicted.has_valid_route = false;
    best_uninterdicted.distance_km = std::numeric_limits<double>::max();

    for (const auto& depot : supply_points_) {
        if (depot.faction != unit.get_faction()) continue;

        LOCResult loc = calculate_loc_to_depot(unit, depot);

        if (loc.has_valid_route) {
            // Prefer uninterdicted routes
            if (!loc.is_interdicted && loc.distance_km < best_uninterdicted.distance_km) {
                best_uninterdicted = loc;
            }
            // Track best overall (even if interdicted)
            if (loc.distance_km < best_result.distance_km) {
                best_result = loc;
            }
        }
    }

    // Return best uninterdicted if available, otherwise best interdicted
    if (best_uninterdicted.has_valid_route) {
        return best_uninterdicted;
    }
    return best_result;
}

bool SupplyModel::is_route_interdicted(const std::vector<Coordinates>& route,
                                        Faction friendly_faction,
                                        double check_radius_km) const {
    return !get_interdicting_units(route, friendly_faction, check_radius_km).empty();
}

std::vector<UnitId> SupplyModel::get_interdicting_units(const std::vector<Coordinates>& route,
                                                         Faction friendly_faction,
                                                         double check_radius_km) const {
    std::vector<UnitId> interdictors;

    if (!orbat_ || route.empty()) return interdictors;

    // Check each segment of the route for nearby enemy units
    orbat_->for_each_unit([&](const Unit& unit) {
        // Skip friendly units
        if (unit.get_faction() == friendly_faction) return;

        // Skip units that can't interdict (not combat-effective)
        if (!unit.is_combat_effective()) return;

        // Check distance to each point on route
        for (const auto& waypoint : route) {
            double dist = unit.get_position().distance_to(waypoint);
            if (dist <= check_radius_km) {
                interdictors.push_back(unit.get_id());
                return;  // Don't add same unit twice
            }
        }

        // Also check segments between waypoints
        for (size_t i = 1; i < route.size(); ++i) {
            // Point-to-line-segment distance calculation
            const auto& p1 = route[i-1];
            const auto& p2 = route[i];
            const auto& p = unit.get_position();

            // Vector from p1 to p2
            double dx = p2.longitude - p1.longitude;
            double dy = p2.latitude - p1.latitude;
            double segment_length_sq = dx * dx + dy * dy;

            if (segment_length_sq > 0.0001) {  // Avoid division by zero
                // Project p onto line, clamp to segment
                double t = std::max(0.0, std::min(1.0,
                    ((p.longitude - p1.longitude) * dx + (p.latitude - p1.latitude) * dy) / segment_length_sq));

                // Closest point on segment
                Coordinates closest{p1.latitude + t * dy, p1.longitude + t * dx};
                double dist = p.distance_to(closest);

                if (dist <= check_radius_km) {
                    interdictors.push_back(unit.get_id());
                    return;
                }
            }
        }
    });

    return interdictors;
}

SupplyStatus SupplyModel::get_supply_status(const Unit& unit) const {
    SupplyStatus status;
    status.unit_id = unit.get_id();
    status.loc = calculate_loc(unit);

    const auto& logistics = unit.get_logistics();

    // Estimate days of supply based on current consumption rates
    // Assume average consumption of 5% per day (posture-dependent)
    double avg_consumption_per_day = 0.05;
    status.days_of_supply = logistics.supply_level / avg_consumption_per_day;

    // Check if critically low (any resource below 20%)
    status.is_critically_low = logistics.fuel_level < 0.2 ||
                               logistics.ammo_level < 0.2 ||
                               logistics.supply_level < 0.2;

    // Can receive resupply if route exists and is not interdicted
    status.can_receive_resupply = status.loc.has_valid_route && !status.loc.is_interdicted;

    return status;
}

std::vector<SupplyStatus> SupplyModel::get_all_supply_status(const std::vector<Unit*>& units) const {
    std::vector<SupplyStatus> statuses;
    statuses.reserve(units.size());

    for (const auto* unit : units) {
        if (unit) {
            statuses.push_back(get_supply_status(*unit));
        }
    }

    return statuses;
}

std::vector<ResupplyResult> SupplyModel::process_resupply_requests(
    const std::vector<ResupplyRequest>& requests,
    std::vector<Unit*>& units) {

    std::vector<ResupplyResult> results;

    // Sort requests by priority
    auto sorted_requests = requests;
    std::sort(sorted_requests.begin(), sorted_requests.end(),
              [](const ResupplyRequest& a, const ResupplyRequest& b) {
                  return a.priority < b.priority;
              });

    for (const auto& request : sorted_requests) {
        // Find the unit
        Unit* unit = nullptr;
        for (auto* u : units) {
            if (u->get_id() == request.unit_id) {
                unit = u;
                break;
            }
        }

        if (!unit) continue;

        // Calculate LOC to determine supply feasibility
        LOCResult loc = calculate_loc(*unit);

        // Skip if no valid route or route is interdicted
        if (!loc.has_valid_route) continue;
        if (loc.is_interdicted) continue;
        if (loc.distance_km > max_supply_range_km_) continue;

        // Find the depot we're getting supplies from
        SupplyPoint* depot = nullptr;
        for (auto& sp : supply_points_) {
            if (sp.id == loc.depot_id) {
                depot = &sp;
                break;
            }
        }
        if (!depot) continue;

        ResupplyResult result;
        result.unit_id = request.unit_id;
        result.fully_satisfied = true;

        // Calculate delivery efficiency based on distance
        // Longer routes = less efficient delivery (some supplies consumed in transit)
        double delivery_efficiency = 1.0;
        if (loc.distance_km > 30.0) {
            // Efficiency drops linearly from 100% at 30km to 70% at max range
            double excess_distance = loc.distance_km - 30.0;
            double max_excess = max_supply_range_km_ - 30.0;
            if (max_excess > 0) {
                delivery_efficiency = 1.0 - 0.3 * (excess_distance / max_excess);
            }
        }

        // Fuel
        double fuel_requested = request.fuel_needed / delivery_efficiency;
        double fuel_to_deliver = std::min(fuel_requested, depot->fuel_available);
        depot->fuel_available -= fuel_to_deliver;
        result.fuel_delivered = fuel_to_deliver * delivery_efficiency;
        if (result.fuel_delivered < request.fuel_needed * 0.99) result.fully_satisfied = false;

        // Ammo
        double ammo_requested = request.ammo_needed / delivery_efficiency;
        double ammo_to_deliver = std::min(ammo_requested, depot->ammo_available);
        depot->ammo_available -= ammo_to_deliver;
        result.ammo_delivered = ammo_to_deliver * delivery_efficiency;
        if (result.ammo_delivered < request.ammo_needed * 0.99) result.fully_satisfied = false;

        // Supply
        double supply_requested = request.supply_needed / delivery_efficiency;
        double supply_to_deliver = std::min(supply_requested, depot->supply_available);
        depot->supply_available -= supply_to_deliver;
        result.supply_delivered = supply_to_deliver * delivery_efficiency;
        if (result.supply_delivered < request.supply_needed * 0.99) result.fully_satisfied = false;

        // Apply to unit
        unit->resupply(result.fuel_delivered, result.ammo_delivered, result.supply_delivered);

        results.push_back(result);
    }

    return results;
}

void SupplyModel::apply_turn_consumption(std::vector<Unit*>& units, double turn_hours) {
    for (auto* unit : units) {
        auto& logistics = unit->get_logistics_mut();

        // Base consumption rates (per hour)
        double fuel_per_hour = 0.01;
        double supply_per_hour = 0.005;

        // Adjust by posture
        switch (unit->get_posture()) {
            case Posture::Attack:
                fuel_per_hour *= 1.5;
                supply_per_hour *= 2.0;
                break;
            case Posture::Move:
                fuel_per_hour *= 2.0;
                break;
            case Posture::Defend:
                fuel_per_hour *= 0.5;
                supply_per_hour *= 0.8;
                break;
            case Posture::Reserve:
                fuel_per_hour *= 0.3;
                supply_per_hour *= 0.5;
                break;
            default:
                break;
        }

        // Apply consumption
        logistics.fuel_level = std::max(0.0, logistics.fuel_level - fuel_per_hour * turn_hours);
        logistics.supply_level = std::max(0.0, logistics.supply_level - supply_per_hour * turn_hours);

        // Maintenance degrades slightly each turn
        logistics.maintenance_state = std::max(0.0, logistics.maintenance_state - 0.005);
    }

    // Replenish depots
    for (auto& depot : supply_points_) {
        depot.fuel_available = std::min(depot.fuel_capacity,
            depot.fuel_available + depot.resupply_rate_per_turn);
        depot.ammo_available = std::min(depot.ammo_capacity,
            depot.ammo_available + depot.resupply_rate_per_turn);
        depot.supply_available = std::min(depot.supply_capacity,
            depot.supply_available + depot.resupply_rate_per_turn);
    }
}

void SupplyModel::dispatch_resupply_convoy(
    const std::string& depot_id,
    const std::vector<UnitId>& target_units) {
    // Future: Model supply convoys as actual units that can be interdicted
}

}  // namespace karkas
