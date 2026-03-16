#include "unit.hpp"
#include "json_serialization.hpp"
#include "terrain/terrain_engine.hpp"
#include <algorithm>
#include <sstream>

namespace karkas {

Unit::Unit(UnitId id, std::string name, Faction faction, UnitType type, Echelon echelon)
    : id_(std::move(id)),
      name_(std::move(name)),
      faction_(faction),
      type_(type),
      echelon_(echelon),
      position_{0.0, 0.0},
      heading_(0.0),
      posture_(Posture::Defend) {

    // Set mobility class based on unit type
    switch (type) {
        case UnitType::Infantry:
            mobility_class_ = MobilityClass::Foot;
            break;
        case UnitType::Armor:
        case UnitType::Mechanized:
        case UnitType::AirDefense:
        case UnitType::Artillery:
            mobility_class_ = MobilityClass::Tracked;
            break;
        case UnitType::Support:
        case UnitType::Headquarters:
        case UnitType::Logistics:
            mobility_class_ = MobilityClass::Wheeled;
            break;
        case UnitType::Recon:
            mobility_class_ = MobilityClass::Wheeled;
            break;
        case UnitType::Engineer:
            mobility_class_ = MobilityClass::Tracked;
            break;
        case UnitType::Rotary:
            mobility_class_ = MobilityClass::Rotary;
            break;
        case UnitType::FixedWing:
            mobility_class_ = MobilityClass::FixedWing;
            break;
    }

    // Initialize logistics at full
    logistics_.fuel_level = 1.0;
    logistics_.ammo_level = 1.0;
    logistics_.supply_level = 1.0;
    logistics_.maintenance_state = 1.0;

    // Initialize morale at good
    morale_.morale = 0.8;
    morale_.fatigue = 0.0;
    morale_.cohesion = 1.0;

    // Set default strength based on echelon
    switch (echelon) {
        case Echelon::Squad:
            strength_.personnel_max = 10;
            strength_.equipment_max = 2;
            break;
        case Echelon::Platoon:
            strength_.personnel_max = 40;
            strength_.equipment_max = 4;
            break;
        case Echelon::Company:
            strength_.personnel_max = 150;
            strength_.equipment_max = 15;
            break;
        case Echelon::Battalion:
            strength_.personnel_max = 600;
            strength_.equipment_max = 50;
            break;
        case Echelon::Regiment:
            strength_.personnel_max = 2500;
            strength_.equipment_max = 150;
            break;
        case Echelon::Brigade:
            strength_.personnel_max = 4000;
            strength_.equipment_max = 250;
            break;
        case Echelon::Division:
            strength_.personnel_max = 12000;
            strength_.equipment_max = 500;
            break;
        case Echelon::Corps:
            strength_.personnel_max = 40000;
            strength_.equipment_max = 1500;
            break;
        case Echelon::Army:
            strength_.personnel_max = 100000;
            strength_.equipment_max = 4000;
            break;
    }

    strength_.personnel_current = strength_.personnel_max;
    strength_.equipment_current = strength_.equipment_max;

    // Set default combat stats based on type
    switch (type) {
        case UnitType::Infantry:
            combat_stats_.combat_power = 30.0;
            combat_stats_.defense_value = 40.0;
            combat_stats_.soft_attack = 35.0;
            combat_stats_.hard_attack = 10.0;
            combat_stats_.air_attack = 5.0;
            combat_stats_.air_defense = 10.0;
            break;
        case UnitType::Armor:
            combat_stats_.combat_power = 60.0;
            combat_stats_.defense_value = 50.0;
            combat_stats_.soft_attack = 40.0;
            combat_stats_.hard_attack = 60.0;
            combat_stats_.air_attack = 0.0;
            combat_stats_.air_defense = 5.0;
            break;
        case UnitType::Mechanized:
            combat_stats_.combat_power = 45.0;
            combat_stats_.defense_value = 45.0;
            combat_stats_.soft_attack = 40.0;
            combat_stats_.hard_attack = 35.0;
            combat_stats_.air_attack = 5.0;
            combat_stats_.air_defense = 15.0;
            break;
        case UnitType::Artillery:
            combat_stats_.combat_power = 50.0;
            combat_stats_.defense_value = 15.0;
            combat_stats_.soft_attack = 60.0;
            combat_stats_.hard_attack = 30.0;
            combat_stats_.air_attack = 0.0;
            combat_stats_.air_defense = 5.0;
            break;
        case UnitType::AirDefense:
            combat_stats_.combat_power = 10.0;
            combat_stats_.defense_value = 20.0;
            combat_stats_.soft_attack = 10.0;
            combat_stats_.hard_attack = 5.0;
            combat_stats_.air_attack = 70.0;
            combat_stats_.air_defense = 60.0;
            break;
        case UnitType::Recon:
            combat_stats_.combat_power = 15.0;
            combat_stats_.defense_value = 20.0;
            combat_stats_.soft_attack = 20.0;
            combat_stats_.hard_attack = 10.0;
            combat_stats_.air_attack = 0.0;
            combat_stats_.air_defense = 5.0;
            break;
        default:
            combat_stats_.combat_power = 5.0;
            combat_stats_.defense_value = 10.0;
            combat_stats_.soft_attack = 5.0;
            combat_stats_.hard_attack = 0.0;
            combat_stats_.air_attack = 0.0;
            combat_stats_.air_defense = 0.0;
            break;
    }

    // Scale combat stats by echelon
    double echelon_mult = static_cast<double>(static_cast<int>(echelon) + 1);
    combat_stats_.combat_power *= echelon_mult;
    combat_stats_.defense_value *= echelon_mult;

    // Add default sensor
    Sensor visual;
    visual.type = SensorType::Visual;
    visual.range_km = 5.0;
    visual.detection_probability = 0.6;
    visual.identification_probability = 0.4;
    visual.arc_degrees = 360.0;
    visual.heading = 0.0;
    visual.active = false;
    sensors_.push_back(visual);

    // Recon units get better sensors
    if (type == UnitType::Recon) {
        visual.range_km = 10.0;
        visual.detection_probability = 0.8;
        visual.identification_probability = 0.6;
        sensors_[0] = visual;

        Sensor thermal;
        thermal.type = SensorType::Thermal;
        thermal.range_km = 8.0;
        thermal.detection_probability = 0.7;
        thermal.identification_probability = 0.5;
        thermal.arc_degrees = 120.0;
        thermal.heading = 0.0;
        thermal.active = false;
        sensors_.push_back(thermal);
    }
}

void Unit::remove_subordinate(UnitId sub) {
    subordinate_ids_.erase(
        std::remove(subordinate_ids_.begin(), subordinate_ids_.end(), sub),
        subordinate_ids_.end());
}

double Unit::get_effective_combat_power() const {
    double base = combat_stats_.combat_power;

    // Modify by strength
    base *= strength_.get_strength_ratio();

    // Modify by logistics
    base *= logistics_.get_effectiveness_modifier();

    // Modify by morale
    base *= morale_.get_effectiveness_modifier();

    return base;
}

double Unit::get_effective_defense() const {
    double base = combat_stats_.defense_value;

    // Modify by strength
    base *= strength_.get_strength_ratio();

    // Modify by logistics
    base *= logistics_.get_effectiveness_modifier();

    // Modify by morale
    base *= morale_.get_effectiveness_modifier();

    // Posture bonus
    if (posture_ == Posture::Defend) {
        base *= 1.5;
    }

    return base;
}

double Unit::get_max_sensor_range() const {
    double max_range = 0;
    for (const auto& sensor : sensors_) {
        max_range = std::max(max_range, sensor.range_km);
    }
    return max_range;
}

bool Unit::has_active_jammer() const {
    for (const auto& jammer : jammers_) {
        if (jammer.active) return true;
    }
    return false;
}

void Unit::activate_jammers() {
    for (auto& jammer : jammers_) {
        jammer.active = true;
    }
}

void Unit::deactivate_jammers() {
    for (auto& jammer : jammers_) {
        jammer.active = false;
    }
}

void Unit::consume_fuel(double amount) {
    logistics_.fuel_level = std::max(0.0, logistics_.fuel_level - amount);
}

void Unit::consume_ammo(double amount) {
    logistics_.ammo_level = std::max(0.0, logistics_.ammo_level - amount);
}

void Unit::resupply(double fuel, double ammo, double supply) {
    logistics_.fuel_level = std::min(1.0, logistics_.fuel_level + fuel);
    logistics_.ammo_level = std::min(1.0, logistics_.ammo_level + ammo);
    logistics_.supply_level = std::min(1.0, logistics_.supply_level + supply);
}

void Unit::apply_fatigue(double amount) {
    morale_.fatigue = std::min(1.0, morale_.fatigue + amount);

    // Excessive fatigue affects morale
    if (morale_.fatigue > 0.7) {
        morale_.morale = std::max(0.0, morale_.morale - 0.02);
    }
}

void Unit::rest(double recovery) {
    morale_.fatigue = std::max(0.0, morale_.fatigue - recovery);

    // Rest improves morale slightly
    if (morale_.fatigue < 0.3) {
        morale_.morale = std::min(1.0, morale_.morale + 0.01);
    }
}

void Unit::apply_morale_effect(double delta) {
    morale_.morale = std::clamp(morale_.morale + delta, 0.0, 1.0);

    // Low morale affects cohesion
    if (morale_.morale < 0.3) {
        morale_.cohesion = std::max(0.0, morale_.cohesion - 0.05);
    }
}

void Unit::apply_casualties(const Casualties& cas) {
    strength_.personnel_current = std::max(0u,
        strength_.personnel_current - cas.personnel_killed - cas.personnel_wounded);
    strength_.equipment_current = std::max(0u,
        strength_.equipment_current - cas.equipment_destroyed);

    // Equipment damage reduces effectiveness but doesn't remove
    // (Could be repaired)

    // Casualties affect morale
    double casualty_rate = static_cast<double>(cas.personnel_killed + cas.personnel_wounded) /
                          std::max(strength_.personnel_max, 1u);
    morale_.morale = std::max(0.0, morale_.morale - casualty_rate * 2.0);
    morale_.cohesion = std::max(0.0, morale_.cohesion - casualty_rate);
}

bool Unit::is_combat_effective() const {
    // Unit is combat effective if it has reasonable strength, supply, and morale
    if (strength_.get_strength_ratio() < 0.3) return false;
    if (logistics_.ammo_level < 0.1) return false;
    if (morale_.morale < 0.2) return false;
    if (morale_.cohesion < 0.2) return false;

    return true;
}

bool Unit::is_destroyed() const {
    return strength_.personnel_current == 0 ||
           (strength_.get_strength_ratio() < 0.1 && morale_.cohesion < 0.1);
}

double Unit::get_max_speed_kph() const {
    switch (mobility_class_) {
        case MobilityClass::Foot:
            return 5.0;
        case MobilityClass::Wheeled:
            return 80.0;
        case MobilityClass::Tracked:
            return 50.0;
        case MobilityClass::Rotary:
            return 250.0;
        case MobilityClass::FixedWing:
            return 800.0;
    }
    return 10.0;
}

double Unit::get_terrain_speed(TerrainType terrain) const {
    double base_speed = get_max_speed_kph();

    // Create a temporary terrain cell to get mobility cost
    TerrainCell cell;
    cell.primary_type = terrain;

    double cost = cell.get_mobility_cost(mobility_class_);
    if (!std::isfinite(cost)) return 0.0;

    return base_speed / cost;
}

std::string Unit::to_json() const {
    json j;
    j["id"] = id_;
    j["name"] = name_;
    j["faction"] = faction_;
    j["type"] = type_;
    j["echelon"] = echelon_;
    j["mobility_class"] = mobility_class_;
    j["position"] = position_;
    j["heading"] = heading_;
    j["posture"] = posture_;
    j["combat_stats"] = combat_stats_;
    j["sensors"] = sensors_;
    j["jammers"] = jammers_;
    j["logistics"] = logistics_;
    j["morale"] = morale_;
    j["strength"] = strength_;

    if (parent_id_) j["parent_id"] = *parent_id_;
    if (!subordinate_ids_.empty()) j["subordinates"] = subordinate_ids_;
    if (current_order_.has_value()) {
        // Serialize order type only for now
        j["current_order_type"] = current_order_->order_type;
    }

    return j.dump(2);
}

Unit Unit::from_json(const std::string& json_str) {
    try {
        json j = json::parse(json_str);

        Unit unit(
            j.at("id").get<std::string>(),
            j.at("name").get<std::string>(),
            j.at("faction").get<Faction>(),
            j.at("type").get<UnitType>(),
            j.at("echelon").get<Echelon>()
        );

        unit.position_ = j.at("position").get<Coordinates>();
        unit.heading_ = j.at("heading").get<double>();
        unit.posture_ = j.at("posture").get<Posture>();

        if (j.contains("mobility_class")) {
            unit.mobility_class_ = j.at("mobility_class").get<MobilityClass>();
        }

        if (j.contains("combat_stats")) {
            unit.combat_stats_ = j.at("combat_stats").get<CombatStats>();
        }

        if (j.contains("sensors")) {
            unit.sensors_ = j.at("sensors").get<std::vector<Sensor>>();
        }

        if (j.contains("jammers")) {
            unit.jammers_ = j.at("jammers").get<std::vector<Jammer>>();
        }

        unit.logistics_ = j.at("logistics").get<LogisticsState>();
        unit.morale_ = j.at("morale").get<MoraleState>();
        unit.strength_ = j.at("strength").get<UnitStrength>();

        if (j.contains("parent_id")) {
            unit.parent_id_ = j.at("parent_id").get<std::string>();
        }

        if (j.contains("subordinates")) {
            unit.subordinate_ids_ = j.at("subordinates").get<std::vector<UnitId>>();
        }

        return unit;

    } catch (const json::exception& e) {
        // Return a default invalid unit on parse error
        return Unit("invalid", "Parse Error", Faction::Neutral, UnitType::Infantry, Echelon::Squad);
    }
}

// UnitFactory implementation

UnitFactory& UnitFactory::instance() {
    static UnitFactory instance;
    return instance;
}

void UnitFactory::register_template(const std::string& name, UnitTemplate tmpl) {
    templates_[name] = std::move(tmpl);
}

Unit UnitFactory::create_unit(const std::string& template_name, UnitId id,
                             const std::string& name, Faction faction) {
    auto it = templates_.find(template_name);
    if (it == templates_.end()) {
        // Return default unit
        return Unit(id, name, faction, UnitType::Infantry, Echelon::Battalion);
    }

    const auto& tmpl = it->second;
    Unit unit(id, name, faction, tmpl.type, tmpl.echelon);

    unit.set_combat_stats(tmpl.combat_stats);
    for (const auto& sensor : tmpl.sensors) {
        unit.add_sensor(sensor);
    }

    auto& strength = unit.get_strength_mut();
    strength = tmpl.base_strength;
    strength.personnel_current = strength.personnel_max;
    strength.equipment_current = strength.equipment_max;

    return unit;
}

void UnitFactory::load_templates_from_file(const std::string& filepath) {
    // TODO: Implement YAML/JSON template loading
}

}  // namespace karkas
