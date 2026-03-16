#include "movement_resolver.hpp"
#include <algorithm>
#include <cmath>
#include <sstream>
#include <iomanip>
#include <queue>

namespace karkas {

MovementResolver::MovementResolver()
    : terrain_(nullptr),
      road_capacity_(20.0) {}  // Default: 20 units per hour per road segment

// ===========================================================================
// Speed and Fuel Calculations
// ===========================================================================

double MovementResolver::calculate_effective_speed(const Unit& unit,
                                                   const TerrainCell& terrain,
                                                   const Weather& weather) const {
    double base_speed = unit.get_max_speed_kph();

    // Terrain mobility cost (1.0 = normal, higher = slower)
    double terrain_cost = terrain.get_mobility_cost(unit.get_mobility_class());
    double terrain_modifier = 1.0 / std::max(terrain_cost, 0.1);

    // Road bonus - units on roads move faster
    if (terrain.is_road && unit.get_mobility_class() != MobilityClass::Foot) {
        terrain_modifier = std::min(terrain_modifier * 1.5, 1.2);  // Up to 20% bonus
    }

    // Weather effects
    double weather_modifier = weather.get_mobility_modifier();

    // Supply state affects speed (low fuel = slower)
    double fuel_level = unit.get_logistics().fuel_level;
    double supply_modifier = (fuel_level > 0.3) ? 1.0 : (0.5 + fuel_level * 1.67);

    // Fatigue affects speed (max 30% reduction at full fatigue)
    double fatigue = unit.get_morale().fatigue;
    double fatigue_modifier = 1.0 - (fatigue * 0.3);

    // Morale affects movement efficiency
    double morale = unit.get_morale().morale;
    double morale_modifier = 0.7 + (morale * 0.3);  // 70-100% based on morale

    // Equipment state affects speed
    double maintenance = unit.get_logistics().maintenance_state;
    double maintenance_modifier = 0.6 + (maintenance * 0.4);  // 60-100%

    return base_speed * terrain_modifier * weather_modifier *
           supply_modifier * fatigue_modifier * morale_modifier * maintenance_modifier;
}

double MovementResolver::calculate_fuel_consumption(const Unit& unit,
                                                   double distance_km,
                                                   const TerrainCell& terrain,
                                                   double speed_kph) const {
    // Base consumption per km by mobility class
    double base_consumption = 0.0;

    switch (unit.get_mobility_class()) {
        case MobilityClass::Foot:
            base_consumption = 0.001;  // Minimal fuel for infantry (food/water)
            break;
        case MobilityClass::Wheeled:
            base_consumption = 0.005;
            break;
        case MobilityClass::Tracked:
            base_consumption = 0.015;  // Tanks burn more fuel
            break;
        case MobilityClass::Rotary:
            base_consumption = 0.03;   // Helicopters expensive
            break;
        case MobilityClass::FixedWing:
            base_consumption = 0.05;   // Aircraft very expensive
            break;
    }

    // Terrain difficulty increases consumption
    double terrain_multiplier = terrain.get_mobility_cost(unit.get_mobility_class());

    // Speed affects consumption (faster = more fuel)
    // Optimal speed is around 60% of max
    double max_speed = unit.get_max_speed_kph();
    double speed_ratio = (max_speed > 0) ? speed_kph / max_speed : 0.5;
    double speed_multiplier = 0.8 + (speed_ratio * 0.4);  // 80-120% based on speed

    // Road travel is more fuel efficient
    if (terrain.is_road) {
        terrain_multiplier *= 0.7;
    }

    return distance_km * base_consumption * terrain_multiplier * speed_multiplier;
}

double MovementResolver::calculate_segment_fuel(const Unit& unit,
                                                const PathSegment& segment,
                                                double actual_speed_kph) const {
    // Get terrain at midpoint of segment
    Coordinates midpoint{
        (segment.from.latitude + segment.to.latitude) / 2,
        (segment.from.longitude + segment.to.longitude) / 2
    };

    TerrainCell cell;
    if (terrain_) {
        cell = terrain_->get_cell(midpoint);
    } else {
        cell.primary_type = TerrainType::Open;
        cell.is_road = false;
    }

    return calculate_fuel_consumption(unit, segment.distance_km, cell, actual_speed_kph);
}

double MovementResolver::estimate_movement_range(const Unit& unit, double hours,
                                                const Weather& weather) const {
    double base_speed = unit.get_max_speed_kph();
    double weather_mod = weather.get_mobility_modifier();
    double supply_mod = std::max(unit.get_logistics().fuel_level, 0.1);

    // Assume average terrain (slightly difficult)
    double terrain_mod = 0.7;

    // Fatigue reduces range
    double fatigue_mod = 1.0 - (unit.get_morale().fatigue * 0.2);

    return base_speed * hours * weather_mod * supply_mod * terrain_mod * fatigue_mod;
}

// ===========================================================================
// Interdiction Detection
// ===========================================================================

bool MovementResolver::check_interdiction(const Path& path,
                                         const std::vector<Unit*>& enemy_units,
                                         double interdiction_radius_km) const {
    return find_interdiction_point(path, enemy_units, interdiction_radius_km).has_value();
}

std::optional<Coordinates> MovementResolver::find_interdiction_point(
    const Path& path,
    const std::vector<Unit*>& enemy_units,
    double interdiction_radius_km) const {

    for (const auto& segment : path.segments) {
        // Check multiple points along segment (from, midpoint, to)
        std::vector<Coordinates> check_points = {
            segment.from,
            {(segment.from.latitude + segment.to.latitude) / 2,
             (segment.from.longitude + segment.to.longitude) / 2},
            segment.to
        };

        for (const auto& point : check_points) {
            for (const auto* enemy : enemy_units) {
                if (!enemy || !enemy->is_combat_effective()) continue;

                double dist = point.distance_to(enemy->get_position());
                if (dist < interdiction_radius_km) {
                    // Check if enemy can actually interdict
                    // (has combat power and is in offensive/defensive posture)
                    if (enemy->get_effective_combat_power() > 0 &&
                        enemy->get_posture() != Posture::Retreat &&
                        enemy->get_posture() != Posture::Disengaged) {

                        // Check line of sight if terrain available
                        if (terrain_) {
                            auto los = terrain_->calculate_los(enemy->get_position(), point);
                            if (los.has_los) {
                                return point;
                            }
                        } else {
                            return point;
                        }
                    }
                }
            }
        }
    }

    return std::nullopt;
}

// ===========================================================================
// Path Following
// ===========================================================================

MovementResult MovementResolver::follow_path(Unit& unit, const Path& path,
                                             const MovementOrder& order,
                                             double turn_hours,
                                             const std::vector<Unit*>& enemy_units,
                                             const Weather& weather) {
    MovementResult result;
    result.unit_id = unit.get_id();
    result.start_position = unit.get_position();
    result.distance_moved_km = 0;
    result.time_elapsed_hours = 0;
    result.reached_destination = false;
    result.halted_by_contact = false;
    result.halted_by_terrain = false;
    result.halted_by_congestion = false;
    result.fuel_consumed = 0;
    result.path_taken.push_back(unit.get_position());

    if (path.segments.empty()) {
        result.end_position = unit.get_position();
        result.narrative = generate_narrative(unit, result, order);
        return result;
    }

    double remaining_time = turn_hours;
    Coordinates current_pos = unit.get_position();
    size_t segment_idx = 0;

    // Find starting segment (closest to current position)
    double min_dist = std::numeric_limits<double>::max();
    for (size_t i = 0; i < path.segments.size(); ++i) {
        double d = current_pos.distance_to(path.segments[i].from);
        if (d < min_dist) {
            min_dist = d;
            segment_idx = i;
        }
    }

    // Traverse path segments
    while (remaining_time > 0.01 && segment_idx < path.segments.size()) {
        const PathSegment& segment = path.segments[segment_idx];

        // Get terrain for this segment
        TerrainCell cell;
        if (terrain_) {
            Coordinates midpoint{
                (segment.from.latitude + segment.to.latitude) / 2,
                (segment.from.longitude + segment.to.longitude) / 2
            };
            cell = terrain_->get_cell(midpoint);
        } else {
            cell.primary_type = segment.terrain;
            cell.cover = segment.cover_along_route;
            cell.is_road = (segment.terrain == TerrainType::Road);
        }

        // Calculate effective speed for this segment
        double effective_speed = calculate_effective_speed(unit, cell, weather);
        effective_speed *= order.max_speed_modifier;

        // Check road congestion
        if (cell.is_road && check_road_congestion(segment.from, segment.to)) {
            effective_speed *= 0.3;  // Severe slowdown in congestion
            result.halted_by_congestion = true;
        }

        // Check for enemy contact along this segment
        if (order.halt_on_contact) {
            // Create mini-path for just this segment
            Path segment_path;
            segment_path.segments.push_back(segment);

            if (auto interdict_point = find_interdiction_point(segment_path, enemy_units, 3.0)) {
                // Move toward the interdiction point but stop short
                double dist_to_contact = current_pos.distance_to(*interdict_point);
                double safe_dist = std::max(0.0, dist_to_contact - 2.0);  // Stop 2km short

                if (safe_dist > 0.1 && effective_speed > 0) {
                    double time_to_safe = safe_dist / effective_speed;
                    double actual_time = std::min(time_to_safe, remaining_time);
                    double actual_dist = actual_time * effective_speed;

                    double bearing = current_pos.bearing_to(*interdict_point);
                    current_pos = current_pos.move_toward(bearing, actual_dist);

                    double fuel = calculate_segment_fuel(unit, segment, effective_speed);
                    fuel *= (actual_dist / segment.distance_km);
                    unit.consume_fuel(fuel);
                    result.fuel_consumed += fuel;

                    result.distance_moved_km += actual_dist;
                    result.time_elapsed_hours += actual_time;
                    result.path_taken.push_back(current_pos);
                }

                result.halted_by_contact = true;
                break;
            }
        }

        // Calculate remaining distance in segment
        double dist_in_segment = current_pos.distance_to(segment.to);

        // Check if terrain is passable
        if (terrain_ && !terrain_->is_passable(segment.to, unit.get_mobility_class())) {
            result.halted_by_terrain = true;
            break;
        }

        // Calculate how far we can go in remaining time
        double max_dist_this_turn = effective_speed * remaining_time;

        if (dist_in_segment <= max_dist_this_turn) {
            // Complete this segment
            double time_for_segment = dist_in_segment / effective_speed;
            remaining_time -= time_for_segment;

            double fuel = calculate_segment_fuel(unit, segment, effective_speed);
            fuel *= (dist_in_segment / std::max(segment.distance_km, 0.01));
            unit.consume_fuel(fuel);
            result.fuel_consumed += fuel;

            result.distance_moved_km += dist_in_segment;
            result.time_elapsed_hours += time_for_segment;

            current_pos = segment.to;
            result.path_taken.push_back(current_pos);
            result.segments_traversed.push_back(segment);

            // Update road usage for congestion tracking
            if (cell.is_road) {
                update_road_usage(segment.from, segment.to, unit.get_id());
            }

            segment_idx++;
        } else {
            // Partial movement within segment
            double partial_dist = max_dist_this_turn;
            double bearing = current_pos.bearing_to(segment.to);
            current_pos = current_pos.move_toward(bearing, partial_dist);

            double fuel = calculate_segment_fuel(unit, segment, effective_speed);
            fuel *= (partial_dist / std::max(segment.distance_km, 0.01));
            unit.consume_fuel(fuel);
            result.fuel_consumed += fuel;

            result.distance_moved_km += partial_dist;
            result.time_elapsed_hours += remaining_time;
            result.path_taken.push_back(current_pos);

            remaining_time = 0;
        }

        // Check fuel - stop if running low
        if (unit.get_logistics().fuel_level < 0.05) {
            result.narrative = unit.get_name() + " halts due to fuel shortage.";
            break;
        }
    }

    // Check if we reached destination
    if (segment_idx >= path.segments.size() ||
        (order.final_destination.has_value() &&
         current_pos.distance_to(*order.final_destination) < 0.5)) {
        result.reached_destination = true;
    }

    result.end_position = current_pos;

    // Update unit state
    unit.set_position(current_pos);

    if (result.distance_moved_km > 0.1) {
        double heading = result.start_position.bearing_to(result.end_position);
        unit.set_heading(heading);
    }

    // Apply fatigue based on distance and time
    double max_range = estimate_movement_range(unit, 8.0, weather);
    double fatigue_increase = (result.distance_moved_km / max_range) * 0.15;
    fatigue_increase += result.time_elapsed_hours * 0.02;  // Base fatigue from time
    unit.apply_fatigue(fatigue_increase);

    // Occupy the destination cell
    occupy_cell(current_pos);

    // Generate narrative
    result.narrative = generate_narrative(unit, result, order);

    return result;
}

// ===========================================================================
// Single Unit Movement
// ===========================================================================

MovementResult MovementResolver::resolve_movement(Unit& unit, const MovementOrder& order,
                                                 double turn_hours,
                                                 const std::vector<Unit*>& enemy_units,
                                                 const Weather& weather) {
    MovementResult result;
    result.unit_id = unit.get_id();
    result.start_position = unit.get_position();
    result.distance_moved_km = 0;
    result.time_elapsed_hours = 0;
    result.reached_destination = false;
    result.halted_by_contact = false;
    result.halted_by_terrain = false;
    result.halted_by_congestion = false;
    result.fuel_consumed = 0;

    result.path_taken.push_back(unit.get_position());

    if (order.waypoints.empty()) {
        result.end_position = unit.get_position();
        result.narrative = unit.get_name() + " holds position.";
        return result;
    }

    Coordinates current_pos = unit.get_position();
    double remaining_time = turn_hours;
    size_t waypoint_idx = 0;

    while (remaining_time > 0.01 && waypoint_idx < order.waypoints.size()) {
        Coordinates target = order.waypoints[waypoint_idx];

        // Get path to waypoint using terrain pathfinding
        std::optional<Path> path;
        if (terrain_) {
            path = terrain_->find_path(current_pos, target,
                                      unit.get_mobility_class(),
                                      order.route_preference);
        }

        if (path.has_value() && !path->segments.empty()) {
            // Use path-following for accurate terrain traversal
            MovementOrder segment_order = order;
            segment_order.waypoints = {target};
            segment_order.final_destination = target;

            auto segment_result = follow_path(unit, *path, segment_order,
                                             remaining_time, enemy_units, weather);

            // Aggregate results
            result.distance_moved_km += segment_result.distance_moved_km;
            result.time_elapsed_hours += segment_result.time_elapsed_hours;
            result.fuel_consumed += segment_result.fuel_consumed;

            for (size_t i = 1; i < segment_result.path_taken.size(); ++i) {
                result.path_taken.push_back(segment_result.path_taken[i]);
            }

            for (const auto& seg : segment_result.segments_traversed) {
                result.segments_traversed.push_back(seg);
            }

            current_pos = segment_result.end_position;
            remaining_time = turn_hours - result.time_elapsed_hours;

            if (segment_result.halted_by_contact) {
                result.halted_by_contact = true;
                break;
            }
            if (segment_result.halted_by_terrain) {
                result.halted_by_terrain = true;
                break;
            }
            if (segment_result.halted_by_congestion) {
                result.halted_by_congestion = true;
            }

            if (segment_result.reached_destination) {
                waypoint_idx++;
            }
        } else {
            // No path found or no terrain - direct movement
            TerrainCell cell;
            if (terrain_) {
                cell = terrain_->get_cell(current_pos);
            } else {
                cell.primary_type = TerrainType::Open;
                cell.cover = CoverLevel::None;
                cell.is_road = false;
            }

            double effective_speed = calculate_effective_speed(unit, cell, weather);
            effective_speed *= order.max_speed_modifier;

            double dist_to_target = current_pos.distance_to(target);
            double max_dist = effective_speed * remaining_time;

            // Check for interdiction
            if (order.halt_on_contact) {
                for (const auto* enemy : enemy_units) {
                    if (!enemy || !enemy->is_combat_effective()) continue;

                    double enemy_dist = current_pos.distance_to(enemy->get_position());
                    if (enemy_dist < 5.0 && enemy->get_posture() != Posture::Retreat) {
                        double safe_dist = std::max(0.0, enemy_dist - 2.0);
                        if (safe_dist < max_dist) {
                            max_dist = safe_dist;
                            result.halted_by_contact = true;
                        }
                    }
                }
            }

            if (dist_to_target <= max_dist) {
                // Reach waypoint
                double time_used = dist_to_target / effective_speed;
                remaining_time -= time_used;

                double fuel = calculate_fuel_consumption(unit, dist_to_target, cell, effective_speed);
                unit.consume_fuel(fuel);
                result.fuel_consumed += fuel;

                result.distance_moved_km += dist_to_target;
                result.time_elapsed_hours += time_used;

                current_pos = target;
                result.path_taken.push_back(current_pos);
                waypoint_idx++;
            } else {
                // Partial movement
                double bearing = current_pos.bearing_to(target);
                current_pos = current_pos.move_toward(bearing, max_dist);

                double fuel = calculate_fuel_consumption(unit, max_dist, cell, effective_speed);
                unit.consume_fuel(fuel);
                result.fuel_consumed += fuel;

                result.distance_moved_km += max_dist;
                result.time_elapsed_hours += remaining_time;
                result.path_taken.push_back(current_pos);

                remaining_time = 0;
            }

            if (result.halted_by_contact) break;
        }

        // Check terrain passability
        if (terrain_ && !terrain_->is_passable(current_pos, unit.get_mobility_class())) {
            result.halted_by_terrain = true;
            break;
        }
    }

    result.end_position = current_pos;
    result.reached_destination = (waypoint_idx >= order.waypoints.size());

    // Update unit position
    unit.set_position(current_pos);

    // Update heading
    if (result.distance_moved_km > 0.1) {
        double heading = result.start_position.bearing_to(result.end_position);
        unit.set_heading(heading);
    }

    // Apply fatigue
    double max_range = estimate_movement_range(unit, 8.0, weather);
    double fatigue_increase = (result.distance_moved_km / max_range) * 0.2;
    unit.apply_fatigue(fatigue_increase);

    // Generate narrative
    result.narrative = generate_narrative(unit, result, order);

    return result;
}

// ===========================================================================
// Multi-Unit Movement Resolution
// ===========================================================================

std::vector<MovementPriority> MovementResolver::calculate_movement_order(
    const std::vector<Unit*>& units,
    const std::vector<MovementOrder>& orders) const {

    std::vector<MovementPriority> priorities;

    std::unordered_map<UnitId, const MovementOrder*> order_map;
    for (const auto& order : orders) {
        order_map[order.unit_id] = &order;
    }

    for (const auto* unit : units) {
        if (!unit) continue;

        MovementPriority mp;
        mp.unit_id = unit->get_id();
        mp.echelon = unit->get_echelon();

        auto it = order_map.find(unit->get_id());
        if (it != order_map.end() && it->second) {
            mp.priority = it->second->priority;

            // Calculate distance to objective
            if (!it->second->waypoints.empty()) {
                mp.distance_to_obj = unit->get_position().distance_to(
                    it->second->waypoints.back());
            } else {
                mp.distance_to_obj = std::numeric_limits<double>::max();
            }
        } else {
            mp.priority = 0;
            mp.distance_to_obj = std::numeric_limits<double>::max();
        }

        priorities.push_back(mp);
    }

    // Sort by priority (descending), echelon (descending), distance (ascending)
    std::sort(priorities.begin(), priorities.end());

    return priorities;
}

std::vector<MovementResult> MovementResolver::resolve_all_movements(
    std::vector<Unit*>& units,
    const std::vector<MovementOrder>& orders,
    double turn_hours,
    const Weather& weather) {

    std::vector<MovementResult> results;
    results.reserve(units.size());

    // Clear congestion state from previous resolution
    clear_congestion_state();

    // Create order lookup
    std::unordered_map<UnitId, const MovementOrder*> order_map;
    for (const auto& order : orders) {
        order_map[order.unit_id] = &order;
    }

    // Separate units by faction for interdiction checks
    std::unordered_map<Faction, std::vector<Unit*>> units_by_faction;
    for (auto* unit : units) {
        if (unit) {
            units_by_faction[unit->get_faction()].push_back(unit);
        }
    }

    // Calculate movement priority order
    auto movement_order = calculate_movement_order(units, orders);

    // Process units in priority order
    for (const auto& mp : movement_order) {
        Unit* unit = nullptr;
        for (auto* u : units) {
            if (u && u->get_id() == mp.unit_id) {
                unit = u;
                break;
            }
        }

        if (!unit) continue;

        auto order_it = order_map.find(unit->get_id());
        if (order_it == order_map.end() || !order_it->second) {
            // No movement order - unit holds position
            MovementResult result;
            result.unit_id = unit->get_id();
            result.start_position = unit->get_position();
            result.end_position = unit->get_position();
            result.distance_moved_km = 0;
            result.time_elapsed_hours = 0;
            result.reached_destination = true;
            result.halted_by_contact = false;
            result.halted_by_terrain = false;
            result.halted_by_congestion = false;
            result.fuel_consumed = 0;
            result.narrative = unit->get_name() + " holds position.";

            // Mark cell as occupied
            occupy_cell(unit->get_position());

            results.push_back(result);
            continue;
        }

        // Get enemy units for interdiction check
        std::vector<Unit*> enemy_units;
        for (auto& [faction, faction_units] : units_by_faction) {
            if (faction != unit->get_faction()) {
                enemy_units.insert(enemy_units.end(),
                                  faction_units.begin(), faction_units.end());
            }
        }

        // Release starting cell before movement
        release_cell(unit->get_position());

        // Resolve movement
        auto result = resolve_movement(*unit, *order_it->second, turn_hours,
                                      enemy_units, weather);

        results.push_back(result);
    }

    // Post-processing: collision detection and resolution
    auto collisions = detect_collisions(units, results);

    // Handle collisions - later units adjust
    for (const auto& [id1, id2] : collisions) {
        // Find results
        MovementResult* result1 = nullptr;
        MovementResult* result2 = nullptr;
        Unit* unit2 = nullptr;

        for (auto& result : results) {
            if (result.unit_id == id1) result1 = &result;
            if (result.unit_id == id2) result2 = &result;
        }

        for (auto* u : units) {
            if (u && u->get_id() == id2) {
                unit2 = u;
                break;
            }
        }

        if (!result2 || !unit2) continue;

        // Adjust unit 2 (lower priority) - stop short
        if (result2->path_taken.size() > 1) {
            // Move back one step in path
            size_t stop_idx = result2->path_taken.size() - 2;
            Coordinates adjusted_pos = result2->path_taken[stop_idx];

            // Recalculate distance
            double original_dist = result2->distance_moved_km;
            result2->end_position = adjusted_pos;
            result2->distance_moved_km = 0;

            for (size_t i = 1; i <= stop_idx; ++i) {
                result2->distance_moved_km +=
                    result2->path_taken[i-1].distance_to(result2->path_taken[i]);
            }

            // Trim path
            result2->path_taken.resize(stop_idx + 1);
            result2->reached_destination = false;
            result2->halted_by_congestion = true;
            result2->narrative += " (adjusted for traffic)";

            // Update unit position
            unit2->set_position(adjusted_pos);
        }
    }

    return results;
}

// ===========================================================================
// Collision Detection
// ===========================================================================

std::vector<std::pair<UnitId, UnitId>> MovementResolver::detect_collisions(
    const std::vector<Unit*>& units,
    const std::vector<MovementResult>& planned_movements) const {

    std::vector<std::pair<UnitId, UnitId>> collisions;
    const double collision_radius = 0.5;  // 500m

    for (size_t i = 0; i < planned_movements.size(); ++i) {
        for (size_t j = i + 1; j < planned_movements.size(); ++j) {
            // Get units
            const Unit* unit_i = nullptr;
            const Unit* unit_j = nullptr;

            for (const auto* unit : units) {
                if (!unit) continue;
                if (unit->get_id() == planned_movements[i].unit_id) unit_i = unit;
                if (unit->get_id() == planned_movements[j].unit_id) unit_j = unit;
            }

            if (!unit_i || !unit_j) continue;

            // Only check same-faction collisions
            if (unit_i->get_faction() != unit_j->get_faction()) continue;

            // Check end positions
            double end_dist = planned_movements[i].end_position.distance_to(
                planned_movements[j].end_position);

            if (end_dist < collision_radius) {
                collisions.push_back({planned_movements[i].unit_id,
                                     planned_movements[j].unit_id});
                continue;
            }

            // Check path crossings (simplified - check path endpoints)
            for (size_t pi = 1; pi < planned_movements[i].path_taken.size(); ++pi) {
                for (size_t pj = 1; pj < planned_movements[j].path_taken.size(); ++pj) {
                    double d = planned_movements[i].path_taken[pi].distance_to(
                        planned_movements[j].path_taken[pj]);

                    if (d < collision_radius * 0.5) {
                        collisions.push_back({planned_movements[i].unit_id,
                                             planned_movements[j].unit_id});
                        goto next_pair;
                    }
                }
            }
            next_pair:;
        }
    }

    return collisions;
}

// ===========================================================================
// Congestion Handling
// ===========================================================================

int64_t MovementResolver::coord_to_cell_key(const Coordinates& coord) const {
    // Grid cells of approximately 1km
    int lat_cell = static_cast<int>(coord.latitude * 100);
    int lon_cell = static_cast<int>(coord.longitude * 100);
    return (static_cast<int64_t>(lat_cell) << 32) | static_cast<int64_t>(lon_cell);
}

bool MovementResolver::is_cell_occupied(const Coordinates& coord) const {
    return occupied_cells_.count(coord_to_cell_key(coord)) > 0;
}

void MovementResolver::occupy_cell(const Coordinates& coord) {
    occupied_cells_.insert(coord_to_cell_key(coord));
}

void MovementResolver::release_cell(const Coordinates& coord) {
    occupied_cells_.erase(coord_to_cell_key(coord));
}

bool MovementResolver::check_road_congestion(const Coordinates& from,
                                            const Coordinates& to) const {
    // Generate segment key
    int64_t from_key = coord_to_cell_key(from);
    int64_t to_key = coord_to_cell_key(to);
    int64_t segment_key = from_key ^ to_key;

    auto it = road_segments_.find(segment_key);
    if (it != road_segments_.end()) {
        return it->second.current_usage >= it->second.capacity_units_per_hour;
    }

    return false;
}

void MovementResolver::update_road_usage(const Coordinates& from,
                                        const Coordinates& to,
                                        const UnitId& unit_id) {
    int64_t from_key = coord_to_cell_key(from);
    int64_t to_key = coord_to_cell_key(to);
    int64_t segment_key = from_key ^ to_key;

    auto& segment = road_segments_[segment_key];
    segment.from = from;
    segment.to = to;
    segment.capacity_units_per_hour = road_capacity_;
    segment.current_usage += 1.0;
    segment.queued_units.push_back(unit_id);
}

void MovementResolver::clear_congestion_state() {
    road_segments_.clear();
    occupied_cells_.clear();
}

std::optional<Path> MovementResolver::find_bypass_route(
    const Coordinates& from,
    const Coordinates& to,
    const Unit& unit,
    const std::set<Coordinates>& blocked_points) const {

    if (!terrain_) return std::nullopt;

    // Try to find path avoiding blocked points
    std::vector<Coordinates> avoid_points(blocked_points.begin(), blocked_points.end());
    return terrain_->find_path_avoiding(from, to, unit.get_mobility_class(),
                                       avoid_points, 1.0);
}

// ===========================================================================
// Formation Positions
// ===========================================================================

std::vector<Coordinates> MovementResolver::calculate_formation_positions(
    const Coordinates& center,
    double heading,
    const FormationSpec& formation,
    int num_units) const {

    std::vector<Coordinates> positions;
    if (num_units <= 0) return positions;

    positions.reserve(num_units);

    if (formation.formation_type == "column") {
        // Units in a line behind the center (march column)
        double depth = formation.depth_km > 0 ? formation.depth_km : formation.spacing_km;
        double rear_bearing = std::fmod(heading + 180.0 + 360.0, 360.0);

        for (int i = 0; i < num_units; ++i) {
            double offset = i * depth;
            positions.push_back(center.move_toward(rear_bearing, offset));
        }
    } else if (formation.formation_type == "line") {
        // Units spread perpendicular to heading (assault line)
        double left_bearing = std::fmod(heading - 90.0 + 360.0, 360.0);

        double total_width = (num_units - 1) * formation.spacing_km;
        Coordinates start = center.move_toward(left_bearing, total_width / 2);

        double right_bearing = std::fmod(heading + 90.0, 360.0);
        for (int i = 0; i < num_units; ++i) {
            double offset = i * formation.spacing_km;
            positions.push_back(start.move_toward(right_bearing, offset));
        }
    } else if (formation.formation_type == "wedge") {
        // V-shaped formation with lead element at center
        positions.push_back(center);  // Lead element

        double rear_bearing = std::fmod(heading + 180.0 + 360.0, 360.0);
        double left_bearing = std::fmod(heading - 135.0 + 360.0, 360.0);
        double right_bearing = std::fmod(heading + 135.0 + 360.0, 360.0);

        for (int i = 1; i < num_units; ++i) {
            int row = (i + 1) / 2;
            bool is_left = (i % 2 == 1);

            double distance = row * formation.spacing_km * 1.4;  // Diagonal spacing
            double bearing = is_left ? left_bearing : right_bearing;

            positions.push_back(center.move_toward(bearing, distance));
        }
    } else if (formation.formation_type == "echelon_left") {
        // Staggered diagonal formation to the left
        double rear_left_bearing = std::fmod(heading + 225.0, 360.0);

        for (int i = 0; i < num_units; ++i) {
            double offset = i * formation.spacing_km;
            positions.push_back(center.move_toward(rear_left_bearing, offset));
        }
    } else if (formation.formation_type == "echelon_right") {
        // Staggered diagonal formation to the right
        double rear_right_bearing = std::fmod(heading + 135.0, 360.0);

        for (int i = 0; i < num_units; ++i) {
            double offset = i * formation.spacing_km;
            positions.push_back(center.move_toward(rear_right_bearing, offset));
        }
    } else if (formation.formation_type == "box") {
        // Square/rectangular formation
        int side = static_cast<int>(std::ceil(std::sqrt(num_units)));
        double half_width = (side - 1) * formation.spacing_km / 2;

        double left_bearing = std::fmod(heading - 90.0 + 360.0, 360.0);
        double rear_bearing = std::fmod(heading + 180.0 + 360.0, 360.0);

        Coordinates top_left = center.move_toward(left_bearing, half_width);

        int idx = 0;
        for (int row = 0; row < side && idx < num_units; ++row) {
            for (int col = 0; col < side && idx < num_units; ++col) {
                Coordinates pos = top_left;
                pos = pos.move_toward(std::fmod(heading + 90.0, 360.0),
                                     col * formation.spacing_km);
                pos = pos.move_toward(rear_bearing, row * formation.spacing_km);
                positions.push_back(pos);
                idx++;
            }
        }
    } else {
        // Default: circular arrangement
        for (int i = 0; i < num_units; ++i) {
            double angle = (360.0 / num_units) * i;
            double bearing = std::fmod(heading + angle, 360.0);
            positions.push_back(center.move_toward(bearing, formation.spacing_km));
        }
    }

    return positions;
}

// ===========================================================================
// Narrative Generation
// ===========================================================================

std::string MovementResolver::generate_narrative(const Unit& unit,
                                                const MovementResult& result,
                                                const MovementOrder& order) const {
    std::stringstream ss;

    ss << unit.get_name();

    if (result.distance_moved_km < 0.1) {
        ss << " holds position";

        if (result.halted_by_contact) {
            ss << " (enemy contact)";
        } else if (result.halted_by_terrain) {
            ss << " (impassable terrain)";
        } else if (result.halted_by_congestion) {
            ss << " (road congestion)";
        }

        ss << ".";
        return ss.str();
    }

    ss << " advances " << std::fixed << std::setprecision(1)
       << result.distance_moved_km << " km";

    // Direction
    if (result.path_taken.size() >= 2) {
        double bearing = result.start_position.bearing_to(result.end_position);

        if (bearing >= 337.5 || bearing < 22.5) ss << " north";
        else if (bearing >= 22.5 && bearing < 67.5) ss << " northeast";
        else if (bearing >= 67.5 && bearing < 112.5) ss << " east";
        else if (bearing >= 112.5 && bearing < 157.5) ss << " southeast";
        else if (bearing >= 157.5 && bearing < 202.5) ss << " south";
        else if (bearing >= 202.5 && bearing < 247.5) ss << " southwest";
        else if (bearing >= 247.5 && bearing < 292.5) ss << " west";
        else ss << " northwest";
    }

    // Outcome
    if (result.reached_destination) {
        ss << " and reaches objective";
    } else if (result.halted_by_contact) {
        ss << " before halting at enemy contact";
    } else if (result.halted_by_terrain) {
        ss << " before halting at impassable terrain";
    } else if (result.halted_by_congestion) {
        ss << " (slowed by traffic)";
    }

    // Fuel warning
    if (result.fuel_consumed > 0.1) {
        double remaining_fuel = unit.get_logistics().fuel_level;
        if (remaining_fuel < 0.2) {
            ss << " [LOW FUEL]";
        }
    }

    ss << ".";

    return ss.str();
}

}  // namespace karkas
