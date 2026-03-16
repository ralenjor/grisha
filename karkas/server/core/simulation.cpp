#include "simulation.hpp"
#include "json_serialization.hpp"
#include <yaml-cpp/yaml.h>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <ctime>
#include <iomanip>

namespace karkas {

// GameState implementation

GameState::GameState()
    : current_turn_(0),
      red_perception_(Faction::Red),
      blue_perception_(Faction::Blue) {}

void GameState::queue_order(Order order) {
    // Determine faction from issuing unit
    auto* unit = orbat_.get_unit(order.issuer);
    if (!unit) return;

    if (unit->get_faction() == Faction::Red) {
        red_pending_orders_.push_back(std::move(order));
    } else if (unit->get_faction() == Faction::Blue) {
        blue_pending_orders_.push_back(std::move(order));
    }
}

std::vector<Order>& GameState::get_pending_orders(Faction faction) {
    return (faction == Faction::Red) ? red_pending_orders_ : blue_pending_orders_;
}

const std::vector<Order>& GameState::get_pending_orders(Faction faction) const {
    return (faction == Faction::Red) ? red_pending_orders_ : blue_pending_orders_;
}

void GameState::clear_pending_orders() {
    red_pending_orders_.clear();
    blue_pending_orders_.clear();
}

PerceptionState& GameState::get_perception(Faction faction) {
    return (faction == Faction::Red) ? red_perception_ : blue_perception_;
}

const PerceptionState& GameState::get_perception(Faction faction) const {
    return (faction == Faction::Red) ? red_perception_ : blue_perception_;
}

void GameState::update_control_zones() {
    // Simple control zone calculation based on unit positions
    // More sophisticated version would use influence mapping

    std::unordered_map<std::string, std::pair<double, double>> zone_influence;

    orbat_.for_each_unit([&](const Unit& unit) {
        // Each unit contributes to nearby zones
        double influence_radius = 5.0;  // km

        for (auto& zone : control_zones_) {
            // Check if unit is in or near zone
            bool in_zone = false;
            for (const auto& coord : zone.polygon) {
                if (unit.get_position().distance_to(coord) < influence_radius) {
                    in_zone = true;
                    break;
                }
            }

            if (in_zone) {
                double combat_power = unit.get_effective_combat_power();
                if (unit.get_faction() == Faction::Red) {
                    zone_influence[zone.zone_id].first += combat_power;
                } else {
                    zone_influence[zone.zone_id].second += combat_power;
                }
            }
        }
    });

    // Update zone control based on influence
    for (auto& zone : control_zones_) {
        auto it = zone_influence.find(zone.zone_id);
        if (it != zone_influence.end()) {
            double red_inf = it->second.first;
            double blue_inf = it->second.second;
            double total = red_inf + blue_inf;

            if (total > 0) {
                if (red_inf > blue_inf * 1.5) {
                    zone.controller = Faction::Red;
                    zone.control_strength = red_inf / total;
                } else if (blue_inf > red_inf * 1.5) {
                    zone.controller = Faction::Blue;
                    zone.control_strength = blue_inf / total;
                } else {
                    zone.controller = Faction::Neutral;
                    zone.control_strength = 0.5;
                }
            }
        }
    }
}

void GameState::log_event(GameEvent event) {
    events_.push_back(std::move(event));
}

std::vector<GameEvent> GameState::get_events_for_turn(TurnNumber turn) const {
    std::vector<GameEvent> turn_events;

    for (const auto& event : events_) {
        TurnNumber event_turn = std::visit([](const auto& e) { return e.turn; }, event);
        if (event_turn == turn) {
            turn_events.push_back(event);
        }
    }

    return turn_events;
}

std::string GameState::to_json() const {
    json j;
    j["turn"] = current_turn_;
    j["turn_state"] = turn_state_;

    // Serialize units
    json units_json = json::array();
    orbat_.for_each_unit([&](const Unit& unit) {
        json uj;
        uj["id"] = unit.get_id();
        uj["name"] = unit.get_name();
        uj["faction"] = unit.get_faction();
        uj["type"] = unit.get_type();
        uj["echelon"] = unit.get_echelon();
        uj["position"] = unit.get_position();
        uj["posture"] = unit.get_posture();
        uj["logistics"] = unit.get_logistics();
        uj["morale"] = unit.get_morale();
        uj["strength"] = unit.get_strength();
        units_json.push_back(uj);
    });
    j["units"] = units_json;

    // Serialize contacts for each perception state
    j["red_contacts"] = red_perception_.get_contacts();
    j["blue_contacts"] = blue_perception_.get_contacts();

    // Serialize control zones
    j["control_zones"] = control_zones_;

    // Serialize events
    json events_json = json::array();
    for (const auto& event : events_) {
        json ej;
        std::visit([&ej](const auto& e) {
            ej = e;  // Uses ADL to find the correct to_json
        }, event);
        events_json.push_back(ej);
    }
    j["events"] = events_json;

    return j.dump(2);
}

void GameState::save_to_file(const std::string& filepath) const {
    std::ofstream file(filepath);
    file << to_json();
}

// Simulation implementation

Simulation::Simulation()
    : combat_resolver_(),
      battle_resolver_(combat_resolver_),
      current_phase_(TurnPhase::Planning),
      orders_submitted_red_(false),
      orders_submitted_blue_(false) {

    // Connect components to terrain and EW environment
    combat_resolver_.set_terrain(&terrain_);
    sensor_model_.set_terrain(&terrain_);
    sensor_model_.set_ew_environment(&ew_environment_);
    movement_resolver_.set_terrain(&terrain_);
    supply_model_.set_terrain(&terrain_);
}

Simulation::~Simulation() = default;

bool Simulation::load_scenario(const ScenarioConfig& config) {
    scenario_ = config;

    // Load terrain
    if (!terrain_.load_region(config.region, config.terrain_data_path)) {
        return false;
    }

    // Initialize turn state
    state_.get_turn_state_mut().turn_number = 0;
    state_.get_turn_state_mut().simulation_time = config.start_time;
    state_.get_turn_state_mut().turn_length = config.turn_length;
    state_.get_turn_state_mut().weather = config.initial_weather;

    // Calculate initial time of day
    auto time_t = std::chrono::system_clock::to_time_t(config.start_time);
    auto tm = *std::localtime(&time_t);
    state_.get_turn_state_mut().time_of_day.hour = tm.tm_hour;
    state_.get_turn_state_mut().time_of_day.minute = tm.tm_min;

    // Connect supply model to orbat (for interdiction checking)
    supply_model_.set_orbat(&state_.get_orbat());

    // TODO: Load ORBATs from files
    // For now, create empty ORBAT

    current_phase_ = TurnPhase::Planning;
    return true;
}

bool Simulation::load_scenario_from_file(const std::string& yaml_path) {
    try {
        YAML::Node root = YAML::LoadFile(yaml_path);
        YAML::Node scenario = root["scenario"];

        ScenarioConfig config;

        // Basic info
        config.name = scenario["name"].as<std::string>();
        config.description = scenario["description"].as<std::string>("");

        // Region bounds
        auto bounds = scenario["region"]["bounds"];
        auto sw = bounds["southwest"].as<std::vector<double>>();
        auto ne = bounds["northeast"].as<std::vector<double>>();
        config.region.southwest = {sw[0], sw[1]};
        config.region.northeast = {ne[0], ne[1]};

        if (scenario["region"]["terrain_source"]) {
            config.terrain_data_path = scenario["region"]["terrain_source"].as<std::string>();
        }

        // Faction configs
        auto factions = scenario["factions"];

        config.red_faction.name = factions["red"]["name"].as<std::string>();
        config.red_faction.faction = Faction::Red;
        config.red_faction.doctrine = factions["red"]["doctrine"].as<std::string>("");
        config.red_faction.orbat_file = factions["red"]["orbat_file"].as<std::string>("");
        config.red_faction.ai_controlled = factions["red"]["ai_controlled"].as<bool>(true);

        config.blue_faction.name = factions["blue"]["name"].as<std::string>();
        config.blue_faction.faction = Faction::Blue;
        config.blue_faction.doctrine = factions["blue"]["doctrine"].as<std::string>("");
        config.blue_faction.orbat_file = factions["blue"]["orbat_file"].as<std::string>("");
        config.blue_faction.ai_controlled = factions["blue"]["ai_controlled"].as<bool>(false);

        // Initial conditions
        auto init = scenario["initial_conditions"];
        config.turn_length = std::chrono::hours(init["turn_length_hours"].as<int>(4));

        // Parse start date
        if (init["start_date"]) {
            std::string date_str = init["start_date"].as<std::string>();
            std::tm tm = {};
            std::istringstream ss(date_str);
            ss >> std::get_time(&tm, "%Y-%m-%dT%H:%M:%S");
            config.start_time = std::chrono::system_clock::from_time_t(std::mktime(&tm));
        } else {
            config.start_time = std::chrono::system_clock::now();
        }

        // Weather
        if (init["weather"]) {
            auto weather = init["weather"];
            std::string precip = weather["precipitation"].as<std::string>("none");
            std::string vis = weather["visibility"].as<std::string>("clear");

            if (precip == "none") config.initial_weather.precipitation = Weather::Precipitation::None;
            else if (precip == "light") config.initial_weather.precipitation = Weather::Precipitation::Light;
            else if (precip == "moderate") config.initial_weather.precipitation = Weather::Precipitation::Moderate;
            else if (precip == "heavy") config.initial_weather.precipitation = Weather::Precipitation::Heavy;

            if (vis == "clear") config.initial_weather.visibility = Weather::Visibility::Clear;
            else if (vis == "haze") config.initial_weather.visibility = Weather::Visibility::Haze;
            else if (vis == "fog") config.initial_weather.visibility = Weather::Visibility::Fog;
            else if (vis == "smoke") config.initial_weather.visibility = Weather::Visibility::Smoke;

            config.initial_weather.temperature_c = weather["temperature_c"].as<double>(15.0);
            config.initial_weather.wind_speed_kph = weather["wind_speed_kph"].as<double>(10.0);
            config.initial_weather.wind_direction = weather["wind_direction"].as<double>(0.0);
        }

        // Victory conditions
        if (scenario["victory_conditions"]) {
            for (const auto& vc : scenario["victory_conditions"]) {
                ScenarioConfig::VictoryCondition condition;

                std::string type_str = vc["type"].as<std::string>();
                if (type_str == "territorial") {
                    condition.type = ScenarioConfig::VictoryCondition::Type::Territorial;
                    if (vc["zones"]) {
                        condition.zone_names = vc["zones"].as<std::vector<std::string>>();
                    }
                    std::string controller = vc["controller"].as<std::string>("neutral");
                    if (controller == "red") condition.required_controller = Faction::Red;
                    else if (controller == "blue") condition.required_controller = Faction::Blue;
                    else condition.required_controller = Faction::Neutral;
                } else if (type_str == "attrition") {
                    condition.type = ScenarioConfig::VictoryCondition::Type::Attrition;
                    condition.attrition_threshold = vc["threshold"].as<double>(0.5);
                } else if (type_str == "time") {
                    condition.type = ScenarioConfig::VictoryCondition::Type::Time;
                    condition.max_turns = vc["max_turns"].as<int>(40);
                } else if (type_str == "objective") {
                    condition.type = ScenarioConfig::VictoryCondition::Type::Objective;
                }

                config.victory_conditions.push_back(condition);
            }
        }

        // Load objectives as control zones
        if (scenario["objectives"]) {
            for (const auto& obj : scenario["objectives"]) {
                ControlZone zone;
                zone.zone_id = obj["name"].as<std::string>();

                auto coords = obj["coordinates"].as<std::vector<double>>();
                Coordinates center{coords[0], coords[1]};

                // Create a small polygon around the point (1km radius approximate)
                double offset = 0.01;  // ~1km in lat/lon
                zone.polygon = {
                    {center.latitude - offset, center.longitude - offset},
                    {center.latitude - offset, center.longitude + offset},
                    {center.latitude + offset, center.longitude + offset},
                    {center.latitude + offset, center.longitude - offset}
                };

                std::string controller = obj["controller"].as<std::string>("neutral");
                if (controller == "red") zone.controller = Faction::Red;
                else if (controller == "blue") zone.controller = Faction::Blue;
                else zone.controller = Faction::Neutral;

                zone.control_strength = 1.0;
                state_.get_control_zones().push_back(zone);
            }
        }

        return load_scenario(config);

    } catch (const YAML::Exception& e) {
        // YAML parsing failed
        return false;
    } catch (const std::exception& e) {
        return false;
    }
}

bool Simulation::validate_order(const Order& order) const {
    // Check issuer exists and belongs to correct faction
    auto* issuer = state_.get_orbat().get_unit(order.issuer);
    if (!issuer) return false;

    // Check target units exist and are subordinate to issuer
    for (const auto& target_id : order.target_units) {
        auto* target = state_.get_orbat().get_unit(target_id);
        if (!target) return false;
        if (target->get_faction() != issuer->get_faction()) return false;
    }

    // Validate objective
    if (order.objective.type == Objective::Type::Position) {
        if (!order.objective.coordinates.has_value()) return false;
        if (!terrain_.get_bounds().contains(*order.objective.coordinates)) return false;
    }

    return true;
}

std::string Simulation::get_order_validation_error(const Order& order) const {
    auto* issuer = state_.get_orbat().get_unit(order.issuer);
    if (!issuer) return "Issuing unit not found";

    for (const auto& target_id : order.target_units) {
        auto* target = state_.get_orbat().get_unit(target_id);
        if (!target) return "Target unit " + target_id + " not found";
        if (target->get_faction() != issuer->get_faction()) {
            return "Target unit " + target_id + " belongs to different faction";
        }
    }

    if (order.objective.type == Objective::Type::Position) {
        if (!order.objective.coordinates.has_value()) {
            return "Position objective requires coordinates";
        }
        if (!terrain_.get_bounds().contains(*order.objective.coordinates)) {
            return "Objective coordinates outside map bounds";
        }
    }

    return "";
}

bool Simulation::submit_orders(Faction faction, const std::vector<Order>& orders) {
    if (current_phase_ != TurnPhase::Planning) {
        return false;
    }

    // Validate all orders
    for (const auto& order : orders) {
        if (!validate_order(order)) {
            return false;
        }
    }

    // Queue orders
    for (const auto& order : orders) {
        state_.queue_order(order);
    }

    if (faction == Faction::Red) {
        orders_submitted_red_ = true;
    } else {
        orders_submitted_blue_ = true;
    }

    return true;
}

bool Simulation::ready_to_execute() const {
    // Both sides need to submit orders (or AI handles it)
    bool red_ready = orders_submitted_red_ || scenario_.red_faction.ai_controlled;
    bool blue_ready = orders_submitted_blue_ || scenario_.blue_faction.ai_controlled;
    return red_ready && blue_ready;
}

void Simulation::start_planning_phase() {
    current_phase_ = TurnPhase::Planning;
    orders_submitted_red_ = false;
    orders_submitted_blue_ = false;
}

void Simulation::start_execution_phase() {
    current_phase_ = TurnPhase::Execution;
}

void Simulation::start_reporting_phase() {
    current_phase_ = TurnPhase::Reporting;
}

TurnResult Simulation::execute_turn() {
    TurnResult result;
    result.turn = state_.get_current_turn();
    result.game_over = false;

    // Move to execution phase
    start_execution_phase();

    // 1. Movement resolution
    resolve_movement_phase();

    // 2. Detection phase
    resolve_detection_phase();

    // 3. Combat resolution
    resolve_combat_phase();

    // 4. Logistics
    resolve_logistics_phase();

    // 5. Update perceptions
    update_perceptions();

    // 6. Check victory conditions
    auto [game_over, winner] = get_victory_status();
    result.game_over = game_over;
    result.winner = winner;

    // 7. Generate reports
    generate_reports(result);

    // Advance turn
    state_.advance_turn();
    auto& ts = state_.get_turn_state_mut();
    ts.turn_number = state_.get_current_turn();
    ts.simulation_time += ts.turn_length;

    // Update time of day
    auto hours = ts.turn_length.count();
    ts.time_of_day.hour = (ts.time_of_day.hour + hours) % 24;

    // Clear orders and reset for next turn
    state_.clear_pending_orders();
    start_planning_phase();

    return result;
}

void Simulation::resolve_movement_phase() {
    const auto& turn_state = state_.get_turn_state();
    double turn_hours = turn_state.turn_length.count();

    // Collect all units and their movement orders
    std::vector<Unit*> all_units;
    std::vector<MovementOrder> all_orders;

    state_.get_orbat().for_each_unit([&](Unit& unit) {
        all_units.push_back(&unit);

        auto order_opt = unit.get_current_order();
        if (order_opt.has_value() &&
            (order_opt->order_type == OrderType::Move ||
             order_opt->order_type == OrderType::Attack ||
             order_opt->order_type == OrderType::Recon)) {

            MovementOrder move_order;
            move_order.unit_id = unit.get_id();

            if (order_opt->objective.coordinates.has_value()) {
                move_order.waypoints.push_back(*order_opt->objective.coordinates);
            }

            move_order.route_preference = order_opt->constraints.route;
            move_order.max_speed_modifier = 1.0;
            move_order.halt_on_contact = (order_opt->order_type != OrderType::Attack);

            all_orders.push_back(move_order);
        }
    });

    // Process pending orders for this turn
    for (auto* faction_orders : {&state_.get_pending_orders(Faction::Red),
                                  &state_.get_pending_orders(Faction::Blue)}) {
        for (const auto& order : *faction_orders) {
            // Assign orders to units
            for (const auto& target_id : order.target_units) {
                auto* unit = state_.get_orbat().get_unit(target_id);
                if (unit) {
                    unit->assign_order(order);

                    // Add movement order if applicable
                    if (order.order_type == OrderType::Move ||
                        order.order_type == OrderType::Attack) {

                        MovementOrder move_order;
                        move_order.unit_id = target_id;

                        if (order.objective.coordinates.has_value()) {
                            move_order.waypoints.push_back(*order.objective.coordinates);
                        }

                        move_order.route_preference = order.constraints.route;
                        move_order.max_speed_modifier = 1.0;
                        move_order.halt_on_contact = (order.order_type != OrderType::Attack);

                        all_orders.push_back(move_order);
                    }
                }
            }
        }
    }

    // Resolve all movements
    auto results = movement_resolver_.resolve_all_movements(
        all_units, all_orders, turn_hours, turn_state.weather);

    // Log movement events
    for (const auto& result : results) {
        if (result.distance_moved_km > 0.1) {
            MovementEvent event;
            event.turn = state_.get_current_turn();
            event.unit = result.unit_id;
            event.from = result.start_position;
            event.to = result.end_position;
            event.distance_km = result.distance_moved_km;
            event.completed = result.reached_destination;

            state_.log_event(event);
            emit_event(event);
        }
    }
}

void Simulation::resolve_detection_phase() {
    // Update EW environment based on active jammers
    update_ew_environment();

    const auto& turn_state = state_.get_turn_state();

    // Generate intel reports for each faction
    std::vector<Unit*> red_units, blue_units;

    state_.get_orbat().for_each_unit([&](Unit& unit) {
        if (unit.get_faction() == Faction::Red) {
            red_units.push_back(&unit);
        } else if (unit.get_faction() == Faction::Blue) {
            blue_units.push_back(&unit);
        }
    });

    // Red detects Blue
    auto red_intel = sensor_model_.generate_intel_report(
        red_units, blue_units, state_.get_current_turn(),
        turn_state.weather, turn_state.time_of_day);

    // Blue detects Red
    auto blue_intel = sensor_model_.generate_intel_report(
        blue_units, red_units, state_.get_current_turn(),
        turn_state.weather, turn_state.time_of_day);

    // Apply contact merging for spatial deduplication (4.7.3)
    auto red_merged = sensor_model_.merge_contacts(red_intel.new_contacts, 0.5);
    auto blue_merged = sensor_model_.merge_contacts(blue_intel.new_contacts, 0.5);

    // Update perception states with merged contacts
    for (const auto& contact : red_merged) {
        state_.get_perception(Faction::Red).update_contact(contact);

        DetectionEvent event;
        event.turn = state_.get_current_turn();
        event.observer = red_intel.observer_id;
        event.observed = contact.actual_unit_id.value_or(contact.contact_id);
        event.location = contact.position;
        event.confidence = contact.confidence;

        state_.log_event(event);
        emit_event(event);
    }

    for (const auto& contact : blue_merged) {
        state_.get_perception(Faction::Blue).update_contact(contact);

        DetectionEvent event;
        event.turn = state_.get_current_turn();
        event.observer = blue_intel.observer_id;
        event.observed = contact.actual_unit_id.value_or(contact.contact_id);
        event.location = contact.position;
        event.confidence = contact.confidence;

        state_.log_event(event);
        emit_event(event);
    }
}

std::vector<std::pair<std::vector<Unit*>, std::vector<Unit*>>>
Simulation::find_combat_engagements() const {

    std::vector<std::pair<std::vector<Unit*>, std::vector<Unit*>>> engagements;

    // Find units in contact (within engagement range)
    const double engagement_range = 5.0;  // km

    std::vector<Unit*> red_units, blue_units;
    state_.get_orbat().for_each_unit([&](const Unit& unit) {
        if (unit.get_faction() == Faction::Red && unit.is_combat_effective()) {
            red_units.push_back(const_cast<Unit*>(&unit));
        } else if (unit.get_faction() == Faction::Blue && unit.is_combat_effective()) {
            blue_units.push_back(const_cast<Unit*>(&unit));
        }
    });

    // Simple clustering: find groups of units in contact
    std::vector<bool> red_assigned(red_units.size(), false);
    std::vector<bool> blue_assigned(blue_units.size(), false);

    for (size_t r = 0; r < red_units.size(); ++r) {
        if (red_assigned[r]) continue;

        std::vector<Unit*> red_group, blue_group;

        // Check if this red unit is attacking or in range of blue
        bool in_contact = false;
        auto red_order = red_units[r]->get_current_order();
        bool is_attacking = red_order.has_value() &&
                           red_order->order_type == OrderType::Attack;

        for (size_t b = 0; b < blue_units.size(); ++b) {
            double dist = red_units[r]->get_position().distance_to(
                blue_units[b]->get_position());

            if (dist < engagement_range) {
                in_contact = true;
                if (!blue_assigned[b]) {
                    blue_group.push_back(blue_units[b]);
                    blue_assigned[b] = true;
                }
            }
        }

        if (in_contact || is_attacking) {
            red_group.push_back(red_units[r]);
            red_assigned[r] = true;

            // Add nearby red units to the same engagement
            for (size_t r2 = r + 1; r2 < red_units.size(); ++r2) {
                if (red_assigned[r2]) continue;

                double dist = red_units[r]->get_position().distance_to(
                    red_units[r2]->get_position());

                if (dist < engagement_range / 2) {
                    red_group.push_back(red_units[r2]);
                    red_assigned[r2] = true;
                }
            }

            if (!blue_group.empty()) {
                engagements.push_back({red_group, blue_group});
            }
        }
    }

    return engagements;
}

void Simulation::resolve_combat_phase() {
    const auto& turn_state = state_.get_turn_state();

    // Find units in contact
    auto engagements = find_combat_engagements();

    for (auto& [attackers, defenders] : engagements) {
        // Determine attacker/defender based on posture and orders
        // For now, Red is always attacker in engagement

        auto battle_result = battle_resolver_.resolve_battle(
            attackers, defenders, turn_state.weather, turn_state.time_of_day);

        // Log combat events
        for (const auto& engagement : battle_result.engagements) {
            CombatEvent event;
            event.turn = state_.get_current_turn();
            event.attacker = engagement.attacker_id;
            event.defender = engagement.defender_id;
            event.location = engagement.final_defender_position;
            event.attacker_casualties = engagement.attacker_casualties;
            event.defender_casualties = engagement.defender_casualties;
            event.attacker_retreated = engagement.attacker_retreated;
            event.defender_retreated = engagement.defender_retreated;

            state_.log_event(event);
            emit_event(event);
        }
    }

    // Handle artillery/fire support
    state_.get_orbat().for_each_unit([&](Unit& unit) {
        if (unit.get_type() != UnitType::Artillery) return;

        auto order = unit.get_current_order();
        if (!order.has_value() || order->order_type != OrderType::Support) return;

        // Find target
        if (order->objective.type == Objective::Type::Unit) {
            auto* target = state_.get_orbat().get_unit(*order->objective.target_unit_id);
            if (target && target->get_faction() != unit.get_faction()) {
                auto result = combat_resolver_.resolve_fire_support(
                    unit, *target, turn_state.weather);

                CombatEvent event;
                event.turn = state_.get_current_turn();
                event.attacker = result.attacker_id;
                event.defender = result.defender_id;
                event.location = target->get_position();
                event.attacker_casualties = result.attacker_casualties;
                event.defender_casualties = result.defender_casualties;

                state_.log_event(event);
                emit_event(event);
            }
        }
    });
}

void Simulation::resolve_logistics_phase() {
    const auto& turn_state = state_.get_turn_state();
    double turn_hours = turn_state.turn_length.count();

    // Collect all units
    std::vector<Unit*> all_units;
    state_.get_orbat().for_each_unit([&](Unit& unit) {
        all_units.push_back(&unit);
    });

    // Apply supply consumption using the supply model
    supply_model_.apply_turn_consumption(all_units, turn_hours);

    // Generate automatic resupply requests for units below threshold
    std::vector<ResupplyRequest> resupply_requests;
    for (auto* unit : all_units) {
        const auto& logistics = unit->get_logistics();

        // Request resupply if below 50% on any resource
        double fuel_needed = 0.0, ammo_needed = 0.0, supply_needed = 0.0;
        bool needs_resupply = false;

        if (logistics.fuel_level < 0.5) {
            fuel_needed = 0.8 - logistics.fuel_level;  // Resupply to 80%
            needs_resupply = true;
        }
        if (logistics.ammo_level < 0.5) {
            ammo_needed = 0.8 - logistics.ammo_level;
            needs_resupply = true;
        }
        if (logistics.supply_level < 0.5) {
            supply_needed = 0.8 - logistics.supply_level;
            needs_resupply = true;
        }

        if (needs_resupply) {
            ResupplyRequest request;
            request.unit_id = unit->get_id();
            request.fuel_needed = fuel_needed;
            request.ammo_needed = ammo_needed;
            request.supply_needed = supply_needed;

            // Priority based on supply criticality and unit type
            int priority = 5;  // Default middle priority
            if (logistics.fuel_level < 0.2 || logistics.ammo_level < 0.2) {
                priority = 1;  // Critical
            } else if (logistics.supply_level < 0.3) {
                priority = 2;
            }

            // Combat units get higher priority
            if (unit->get_type() == UnitType::Armor ||
                unit->get_type() == UnitType::Mechanized ||
                unit->get_type() == UnitType::Artillery) {
                priority = std::max(1, priority - 1);
            }

            request.priority = priority;
            resupply_requests.push_back(request);
        }
    }

    // Process resupply requests
    if (!resupply_requests.empty()) {
        auto results = supply_model_.process_resupply_requests(resupply_requests, all_units);

        // Log resupply events
        for (const auto& result : results) {
            if (result.fuel_delivered > 0 || result.ammo_delivered > 0 ||
                result.supply_delivered > 0) {
                // Find the unit to get its supply status
                Unit* unit = nullptr;
                for (auto* u : all_units) {
                    if (u->get_id() == result.unit_id) {
                        unit = u;
                        break;
                    }
                }

                if (unit) {
                    auto status = supply_model_.get_supply_status(*unit);

                    SupplyEvent event;
                    event.turn = state_.get_current_turn();
                    event.unit = result.unit_id;
                    event.depot_id = status.loc.depot_id;
                    event.fuel_delivered = result.fuel_delivered;
                    event.ammo_delivered = result.ammo_delivered;
                    event.supply_delivered = result.supply_delivered;
                    event.supply_line_interdicted = false;
                    // No interdicting units since resupply succeeded

                    state_.log_event(event);
                    emit_event(event);
                }
            }
        }
    }

    // Log supply status warnings for units with interdicted supply lines
    for (auto* unit : all_units) {
        auto status = supply_model_.get_supply_status(*unit);

        if (status.loc.is_interdicted) {
            // Log the interdiction event
            SupplyEvent event;
            event.turn = state_.get_current_turn();
            event.unit = unit->get_id();
            event.depot_id = status.loc.depot_id;
            event.fuel_delivered = 0.0;
            event.ammo_delivered = 0.0;
            event.supply_delivered = 0.0;
            event.supply_line_interdicted = true;
            event.interdicting_units = status.loc.interdicting_units;

            state_.log_event(event);
            emit_event(event);
        }
    }

    // Apply rest/fatigue recovery for units not in combat
    state_.get_orbat().for_each_unit([&](Unit& unit) {
        if (unit.get_posture() == Posture::Reserve ||
            unit.get_posture() == Posture::Disengaged) {
            unit.rest(0.1);  // Recover 10% fatigue
        } else if (unit.get_posture() == Posture::Defend) {
            unit.rest(0.05);  // Recover 5%
        }
    });
}

void Simulation::update_perceptions() {
    // Update own-unit views in perception states
    state_.get_orbat().for_each_unit([&](const Unit& unit) {
        if (unit.get_faction() == Faction::Red) {
            state_.get_perception(Faction::Red).update_own_unit(unit);
        } else if (unit.get_faction() == Faction::Blue) {
            state_.get_perception(Faction::Blue).update_own_unit(unit);
        }
    });

    // Age contacts and track lost ones (4.7.4 - Historical contact decay)
    // Use 24 hours as max contact age before removal
    auto current_time = std::chrono::system_clock::now();
    auto max_age = std::chrono::hours(24);

    // Clear previous lost contacts before aging
    state_.get_perception(Faction::Red).clear_lost_contacts();
    state_.get_perception(Faction::Blue).clear_lost_contacts();

    // Age contacts and prune old ones
    state_.get_perception(Faction::Red).age_and_prune_contacts(current_time, max_age);
    state_.get_perception(Faction::Blue).age_and_prune_contacts(current_time, max_age);

    // Update control zones
    state_.update_control_zones();

    for (const auto& zone : state_.get_control_zones()) {
        state_.get_perception(Faction::Red).update_control_zone(zone);
        state_.get_perception(Faction::Blue).update_control_zone(zone);
    }
}

void Simulation::generate_reports(TurnResult& result) {
    // Generate faction-specific summaries
    std::stringstream red_ss, blue_ss;

    red_ss << "TURN " << result.turn << " RED SITREP\n";
    red_ss << "============================\n\n";
    red_ss << state_.get_perception(Faction::Red).generate_situation_summary();

    blue_ss << "TURN " << result.turn << " BLUE SITREP\n";
    blue_ss << "=============================\n\n";
    blue_ss << state_.get_perception(Faction::Blue).generate_situation_summary();

    result.red_summary = red_ss.str();
    result.blue_summary = blue_ss.str();

    // Extract events for this turn
    auto turn_events = state_.get_events_for_turn(result.turn);
    for (const auto& event : turn_events) {
        std::visit([&result](const auto& e) {
            using T = std::decay_t<decltype(e)>;
            if constexpr (std::is_same_v<T, MovementEvent>) {
                result.movements.push_back(e);
            } else if constexpr (std::is_same_v<T, CombatEvent>) {
                result.combats.push_back(e);
            } else if constexpr (std::is_same_v<T, DetectionEvent>) {
                result.detections.push_back(e);
            } else if constexpr (std::is_same_v<T, SupplyEvent>) {
                result.supplies.push_back(e);
            }
        }, event);
    }
}

bool Simulation::check_victory() const {
    return get_victory_status().first;
}

std::pair<bool, Faction> Simulation::get_victory_status() const {
    for (const auto& condition : scenario_.victory_conditions) {
        switch (condition.type) {
            case ScenarioConfig::VictoryCondition::Type::Territorial: {
                // Check if required faction controls all specified zones
                bool all_controlled = true;
                for (const auto& zone_name : condition.zone_names) {
                    bool found = false;
                    for (const auto& zone : state_.get_control_zones()) {
                        if (zone.zone_id == zone_name) {
                            found = true;
                            if (zone.controller != condition.required_controller) {
                                all_controlled = false;
                            }
                            break;
                        }
                    }
                    if (!found) all_controlled = false;
                }
                if (all_controlled) {
                    return {true, condition.required_controller};
                }
                break;
            }

            case ScenarioConfig::VictoryCondition::Type::Attrition: {
                // Check if enemy has lost threshold percentage
                double red_strength = 0, blue_strength = 0;
                double red_max = 0, blue_max = 0;

                state_.get_orbat().for_each_unit([&](const Unit& unit) {
                    if (unit.get_faction() == Faction::Red) {
                        red_strength += unit.get_strength().personnel_current;
                        red_max += unit.get_strength().personnel_max;
                    } else {
                        blue_strength += unit.get_strength().personnel_current;
                        blue_max += unit.get_strength().personnel_max;
                    }
                });

                if (red_max > 0 && (1.0 - red_strength / red_max) > condition.attrition_threshold) {
                    return {true, Faction::Blue};
                }
                if (blue_max > 0 && (1.0 - blue_strength / blue_max) > condition.attrition_threshold) {
                    return {true, Faction::Red};
                }
                break;
            }

            case ScenarioConfig::VictoryCondition::Type::Time: {
                if (state_.get_current_turn() >= static_cast<TurnNumber>(condition.max_turns)) {
                    // Time victory - check who's ahead
                    // Simplified: whoever controls more zones
                    int red_zones = 0, blue_zones = 0;
                    for (const auto& zone : state_.get_control_zones()) {
                        if (zone.controller == Faction::Red) red_zones++;
                        else if (zone.controller == Faction::Blue) blue_zones++;
                    }

                    if (red_zones > blue_zones) return {true, Faction::Red};
                    if (blue_zones > red_zones) return {true, Faction::Blue};
                    return {true, Faction::Neutral};  // Draw
                }
                break;
            }

            default:
                break;
        }
    }

    return {false, Faction::Neutral};
}

void Simulation::set_random_seed(unsigned seed) {
    // Recreate combat resolver with new seed
    // Note: battle_resolver_ holds a reference to combat_resolver_, so it will
    // automatically use the updated combat_resolver_ after reassignment
    combat_resolver_ = CombatResolver(seed);
    sensor_model_ = SensorModel(seed);

    // Re-apply terrain and EW environment after recreation
    combat_resolver_.set_terrain(&terrain_);
    sensor_model_.set_terrain(&terrain_);
    sensor_model_.set_ew_environment(&ew_environment_);
}

void Simulation::emit_event(const GameEvent& event) {
    if (event_callback_) {
        event_callback_(event);
    }
}

void Simulation::update_ew_environment() {
    // Clear previous jamming effects
    ew_environment_.active_jamming.clear();

    // Collect active jamming from all units
    state_.get_orbat().for_each_unit([this](const Unit& unit) {
        for (const auto& jammer : unit.get_jammers()) {
            if (jammer.active) {
                auto effect = SensorModel::create_jamming_effect(unit, jammer);
                ew_environment_.active_jamming.push_back(effect);
            }
        }
    });
}

void Simulation::save_game(const std::string& filepath) const {
    state_.save_to_file(filepath);
}

void Simulation::load_game(const std::string& filepath) {
    state_ = GameState::load_from_file(filepath);
}

GameState GameState::from_json(const std::string& json_str) {
    GameState state;

    try {
        json j = json::parse(json_str);

        state.current_turn_ = j.at("turn").get<TurnNumber>();
        state.turn_state_ = j.at("turn_state").get<TurnState>();

        // Load units
        for (const auto& uj : j.at("units")) {
            auto unit = std::make_unique<Unit>(
                uj.at("id").get<std::string>(),
                uj.at("name").get<std::string>(),
                uj.at("faction").get<Faction>(),
                uj.at("type").get<UnitType>(),
                uj.at("echelon").get<Echelon>()
            );
            unit->set_position(uj.at("position").get<Coordinates>());
            unit->set_posture(uj.at("posture").get<Posture>());

            auto& logistics = unit->get_logistics_mut();
            logistics = uj.at("logistics").get<LogisticsState>();

            auto& morale = unit->get_morale_mut();
            morale = uj.at("morale").get<MoraleState>();

            auto& strength = unit->get_strength_mut();
            strength = uj.at("strength").get<UnitStrength>();

            state.orbat_.add_unit(std::move(unit));
        }

        // Load contacts
        for (const auto& contact : j.at("red_contacts")) {
            state.red_perception_.add_contact(contact.get<Contact>());
        }
        for (const auto& contact : j.at("blue_contacts")) {
            state.blue_perception_.add_contact(contact.get<Contact>());
        }

        // Load control zones
        state.control_zones_ = j.at("control_zones").get<std::vector<ControlZone>>();

    } catch (const json::exception& e) {
        // Return empty state on parse error
        return GameState();
    }

    return state;
}

GameState GameState::load_from_file(const std::string& filepath) {
    std::ifstream file(filepath);
    std::stringstream buffer;
    buffer << file.rdbuf();
    return from_json(buffer.str());
}

}  // namespace karkas
