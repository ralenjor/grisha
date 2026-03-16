#pragma once

#include "types.hpp"
#include "unit.hpp"
#include <nlohmann/json.hpp>

namespace karkas {

using json = nlohmann::json;

// Coordinates
inline void to_json(json& j, const Coordinates& c) {
    j = json{{"lat", c.latitude}, {"lon", c.longitude}};
}

inline void from_json(const json& j, Coordinates& c) {
    j.at("lat").get_to(c.latitude);
    j.at("lon").get_to(c.longitude);
}

// BoundingBox
inline void to_json(json& j, const BoundingBox& b) {
    j = json{{"sw", b.southwest}, {"ne", b.northeast}};
}

inline void from_json(const json& j, BoundingBox& b) {
    j.at("sw").get_to(b.southwest);
    j.at("ne").get_to(b.northeast);
}

// Enums - use NLOHMANN_JSON_SERIALIZE_ENUM for automatic conversion
NLOHMANN_JSON_SERIALIZE_ENUM(Faction, {
    {Faction::Red, "red"},
    {Faction::Blue, "blue"},
    {Faction::Neutral, "neutral"}
})

NLOHMANN_JSON_SERIALIZE_ENUM(UnitType, {
    {UnitType::Infantry, "infantry"},
    {UnitType::Armor, "armor"},
    {UnitType::Mechanized, "mechanized"},
    {UnitType::Artillery, "artillery"},
    {UnitType::AirDefense, "air_defense"},
    {UnitType::Rotary, "rotary"},
    {UnitType::FixedWing, "fixed_wing"},
    {UnitType::Support, "support"},
    {UnitType::Headquarters, "headquarters"},
    {UnitType::Recon, "recon"},
    {UnitType::Engineer, "engineer"},
    {UnitType::Logistics, "logistics"}
})

NLOHMANN_JSON_SERIALIZE_ENUM(Echelon, {
    {Echelon::Squad, "squad"},
    {Echelon::Platoon, "platoon"},
    {Echelon::Company, "company"},
    {Echelon::Battalion, "battalion"},
    {Echelon::Regiment, "regiment"},
    {Echelon::Brigade, "brigade"},
    {Echelon::Division, "division"},
    {Echelon::Corps, "corps"},
    {Echelon::Army, "army"}
})

NLOHMANN_JSON_SERIALIZE_ENUM(Posture, {
    {Posture::Attack, "attack"},
    {Posture::Defend, "defend"},
    {Posture::Move, "move"},
    {Posture::Recon, "recon"},
    {Posture::Support, "support"},
    {Posture::Reserve, "reserve"},
    {Posture::Retreat, "retreat"},
    {Posture::Disengaged, "disengaged"}
})

NLOHMANN_JSON_SERIALIZE_ENUM(MobilityClass, {
    {MobilityClass::Foot, "foot"},
    {MobilityClass::Wheeled, "wheeled"},
    {MobilityClass::Tracked, "tracked"},
    {MobilityClass::Rotary, "rotary"},
    {MobilityClass::FixedWing, "fixed_wing"}
})

NLOHMANN_JSON_SERIALIZE_ENUM(TerrainType, {
    {TerrainType::Open, "open"},
    {TerrainType::Forest, "forest"},
    {TerrainType::Urban, "urban"},
    {TerrainType::Water, "water"},
    {TerrainType::Mountain, "mountain"},
    {TerrainType::Marsh, "marsh"},
    {TerrainType::Desert, "desert"},
    {TerrainType::Road, "road"},
    {TerrainType::Bridge, "bridge"}
})

NLOHMANN_JSON_SERIALIZE_ENUM(CoverLevel, {
    {CoverLevel::None, "none"},
    {CoverLevel::Light, "light"},
    {CoverLevel::Medium, "medium"},
    {CoverLevel::Heavy, "heavy"},
    {CoverLevel::Fortified, "fortified"}
})

NLOHMANN_JSON_SERIALIZE_ENUM(SensorType, {
    {SensorType::Visual, "visual"},
    {SensorType::Thermal, "thermal"},
    {SensorType::Radar, "radar"},
    {SensorType::SignalsIntel, "sigint"},
    {SensorType::Acoustic, "acoustic"},
    {SensorType::Satellite, "satellite"},
    {SensorType::HumanIntel, "humint"}
})

NLOHMANN_JSON_SERIALIZE_ENUM(OrderType, {
    {OrderType::Move, "move"},
    {OrderType::Attack, "attack"},
    {OrderType::Defend, "defend"},
    {OrderType::Support, "support"},
    {OrderType::Recon, "recon"},
    {OrderType::Withdraw, "withdraw"},
    {OrderType::Resupply, "resupply"},
    {OrderType::Hold, "hold"}
})

NLOHMANN_JSON_SERIALIZE_ENUM(RoutePreference, {
    {RoutePreference::Fastest, "fastest"},
    {RoutePreference::Covered, "covered"},
    {RoutePreference::Specified, "specified"},
    {RoutePreference::Avoid_Enemy, "avoid_enemy"}
})

NLOHMANN_JSON_SERIALIZE_ENUM(RulesOfEngagement, {
    {RulesOfEngagement::WeaponsFree, "weapons_free"},
    {RulesOfEngagement::WeaponsHold, "weapons_hold"},
    {RulesOfEngagement::WeaponsTight, "weapons_tight"}
})

NLOHMANN_JSON_SERIALIZE_ENUM(ContactConfidence, {
    {ContactConfidence::Confirmed, "confirmed"},
    {ContactConfidence::Probable, "probable"},
    {ContactConfidence::Suspected, "suspected"},
    {ContactConfidence::Unknown, "unknown"}
})

NLOHMANN_JSON_SERIALIZE_ENUM(JammingType, {
    {JammingType::Noise, "noise"},
    {JammingType::Deceptive, "deceptive"},
    {JammingType::Spot, "spot"},
    {JammingType::Barrage, "barrage"}
})

// Sensor
inline void to_json(json& j, const Sensor& s) {
    j = json{
        {"type", s.type},
        {"range_km", s.range_km},
        {"detection_prob", s.detection_probability},
        {"id_prob", s.identification_probability},
        {"arc_deg", s.arc_degrees},
        {"heading", s.heading},
        {"active", s.active}
    };
}

inline void from_json(const json& j, Sensor& s) {
    j.at("type").get_to(s.type);
    j.at("range_km").get_to(s.range_km);
    j.at("detection_prob").get_to(s.detection_probability);
    j.at("id_prob").get_to(s.identification_probability);
    j.at("arc_deg").get_to(s.arc_degrees);
    j.at("heading").get_to(s.heading);
    j.at("active").get_to(s.active);
}

// Jammer
inline void to_json(json& j, const Jammer& jm) {
    j = json{
        {"type", jm.type},
        {"power_watts", jm.power_watts},
        {"range_km", jm.range_km},
        {"bandwidth_mhz", jm.bandwidth_mhz},
        {"active", jm.active},
        {"affects", jm.affects}
    };
}

inline void from_json(const json& j, Jammer& jm) {
    j.at("type").get_to(jm.type);
    j.at("power_watts").get_to(jm.power_watts);
    j.at("range_km").get_to(jm.range_km);
    j.at("bandwidth_mhz").get_to(jm.bandwidth_mhz);
    j.at("active").get_to(jm.active);
    j.at("affects").get_to(jm.affects);
}

// CombatStats
inline void to_json(json& j, const CombatStats& cs) {
    j = json{
        {"combat_power", cs.combat_power},
        {"defense_value", cs.defense_value},
        {"soft_attack", cs.soft_attack},
        {"hard_attack", cs.hard_attack},
        {"air_attack", cs.air_attack},
        {"air_defense", cs.air_defense}
    };
}

inline void from_json(const json& j, CombatStats& cs) {
    j.at("combat_power").get_to(cs.combat_power);
    j.at("defense_value").get_to(cs.defense_value);
    j.at("soft_attack").get_to(cs.soft_attack);
    j.at("hard_attack").get_to(cs.hard_attack);
    j.at("air_attack").get_to(cs.air_attack);
    j.at("air_defense").get_to(cs.air_defense);
}

// LogisticsState
inline void to_json(json& j, const LogisticsState& ls) {
    j = json{
        {"fuel", ls.fuel_level},
        {"ammo", ls.ammo_level},
        {"supply", ls.supply_level},
        {"maintenance", ls.maintenance_state}
    };
}

inline void from_json(const json& j, LogisticsState& ls) {
    j.at("fuel").get_to(ls.fuel_level);
    j.at("ammo").get_to(ls.ammo_level);
    j.at("supply").get_to(ls.supply_level);
    j.at("maintenance").get_to(ls.maintenance_state);
}

// MoraleState
inline void to_json(json& j, const MoraleState& ms) {
    j = json{
        {"morale", ms.morale},
        {"fatigue", ms.fatigue},
        {"cohesion", ms.cohesion}
    };
}

inline void from_json(const json& j, MoraleState& ms) {
    j.at("morale").get_to(ms.morale);
    j.at("fatigue").get_to(ms.fatigue);
    j.at("cohesion").get_to(ms.cohesion);
}

// UnitStrength
inline void to_json(json& j, const UnitStrength& us) {
    j = json{
        {"personnel_current", us.personnel_current},
        {"personnel_max", us.personnel_max},
        {"equipment_current", us.equipment_current},
        {"equipment_max", us.equipment_max}
    };
}

inline void from_json(const json& j, UnitStrength& us) {
    j.at("personnel_current").get_to(us.personnel_current);
    j.at("personnel_max").get_to(us.personnel_max);
    j.at("equipment_current").get_to(us.equipment_current);
    j.at("equipment_max").get_to(us.equipment_max);
}

// Casualties
inline void to_json(json& j, const Casualties& c) {
    j = json{
        {"kia", c.personnel_killed},
        {"wia", c.personnel_wounded},
        {"equip_destroyed", c.equipment_destroyed},
        {"equip_damaged", c.equipment_damaged}
    };
}

inline void from_json(const json& j, Casualties& c) {
    j.at("kia").get_to(c.personnel_killed);
    j.at("wia").get_to(c.personnel_wounded);
    j.at("equip_destroyed").get_to(c.equipment_destroyed);
    j.at("equip_damaged").get_to(c.equipment_damaged);
}

// Contact
inline void to_json(json& j, const Contact& c) {
    j = json{
        {"contact_id", c.contact_id},
        {"position", c.position},
        {"last_known_position", c.last_known_position},
        {"confidence", c.confidence},
        {"faction", c.faction},
        {"source", c.source}
    };
    if (c.actual_unit_id) j["actual_unit_id"] = *c.actual_unit_id;
    if (c.estimated_type) j["estimated_type"] = *c.estimated_type;
    if (c.estimated_echelon) j["estimated_echelon"] = *c.estimated_echelon;
    if (c.estimated_strength) j["estimated_strength"] = *c.estimated_strength;
}

inline void from_json(const json& j, Contact& c) {
    j.at("contact_id").get_to(c.contact_id);
    j.at("position").get_to(c.position);
    j.at("last_known_position").get_to(c.last_known_position);
    j.at("confidence").get_to(c.confidence);
    j.at("faction").get_to(c.faction);
    j.at("source").get_to(c.source);
    if (j.contains("actual_unit_id")) c.actual_unit_id = j["actual_unit_id"].get<std::string>();
    if (j.contains("estimated_type")) c.estimated_type = j["estimated_type"].get<UnitType>();
    if (j.contains("estimated_echelon")) c.estimated_echelon = j["estimated_echelon"].get<Echelon>();
    if (j.contains("estimated_strength")) c.estimated_strength = j["estimated_strength"].get<double>();
}

// ControlZone
inline void to_json(json& j, const ControlZone& cz) {
    j = json{
        {"zone_id", cz.zone_id},
        {"polygon", cz.polygon},
        {"controller", cz.controller},
        {"control_strength", cz.control_strength}
    };
}

inline void from_json(const json& j, ControlZone& cz) {
    j.at("zone_id").get_to(cz.zone_id);
    j.at("polygon").get_to(cz.polygon);
    j.at("controller").get_to(cz.controller);
    j.at("control_strength").get_to(cz.control_strength);
}

// Weather
NLOHMANN_JSON_SERIALIZE_ENUM(Weather::Precipitation, {
    {Weather::Precipitation::None, "none"},
    {Weather::Precipitation::Light, "light"},
    {Weather::Precipitation::Moderate, "moderate"},
    {Weather::Precipitation::Heavy, "heavy"}
})

NLOHMANN_JSON_SERIALIZE_ENUM(Weather::Visibility, {
    {Weather::Visibility::Clear, "clear"},
    {Weather::Visibility::Haze, "haze"},
    {Weather::Visibility::Fog, "fog"},
    {Weather::Visibility::Smoke, "smoke"}
})

inline void to_json(json& j, const Weather& w) {
    j = json{
        {"precipitation", w.precipitation},
        {"visibility", w.visibility},
        {"temperature_c", w.temperature_c},
        {"wind_speed_kph", w.wind_speed_kph},
        {"wind_direction", w.wind_direction}
    };
}

inline void from_json(const json& j, Weather& w) {
    j.at("precipitation").get_to(w.precipitation);
    j.at("visibility").get_to(w.visibility);
    j.at("temperature_c").get_to(w.temperature_c);
    j.at("wind_speed_kph").get_to(w.wind_speed_kph);
    j.at("wind_direction").get_to(w.wind_direction);
}

// TimeOfDay
inline void to_json(json& j, const TimeOfDay& t) {
    j = json{{"hour", t.hour}, {"minute", t.minute}};
}

inline void from_json(const json& j, TimeOfDay& t) {
    j.at("hour").get_to(t.hour);
    j.at("minute").get_to(t.minute);
}

// TurnState
inline void to_json(json& j, const TurnState& ts) {
    j = json{
        {"turn_number", ts.turn_number},
        {"turn_length_hours", ts.turn_length.count()},
        {"weather", ts.weather},
        {"time_of_day", ts.time_of_day}
    };
}

inline void from_json(const json& j, TurnState& ts) {
    j.at("turn_number").get_to(ts.turn_number);
    ts.turn_length = std::chrono::hours(j.at("turn_length_hours").get<int>());
    j.at("weather").get_to(ts.weather);
    j.at("time_of_day").get_to(ts.time_of_day);
}

// Events
inline void to_json(json& j, const CombatEvent& e) {
    j = json{
        {"type", "combat"},
        {"turn", e.turn},
        {"attacker", e.attacker},
        {"defender", e.defender},
        {"location", e.location},
        {"attacker_casualties", e.attacker_casualties},
        {"defender_casualties", e.defender_casualties},
        {"attacker_retreated", e.attacker_retreated},
        {"defender_retreated", e.defender_retreated}
    };
}

inline void to_json(json& j, const DetectionEvent& e) {
    j = json{
        {"type", "detection"},
        {"turn", e.turn},
        {"observer", e.observer},
        {"observed", e.observed},
        {"location", e.location},
        {"sensor_used", e.sensor_used},
        {"confidence", e.confidence}
    };
}

inline void to_json(json& j, const MovementEvent& e) {
    j = json{
        {"type", "movement"},
        {"turn", e.turn},
        {"unit", e.unit},
        {"from", e.from},
        {"to", e.to},
        {"distance_km", e.distance_km},
        {"completed", e.completed}
    };
}

inline void to_json(json& j, const SupplyEvent& e) {
    j = json{
        {"type", "supply"},
        {"turn", e.turn},
        {"unit", e.unit},
        {"depot_id", e.depot_id},
        {"fuel_delivered", e.fuel_delivered},
        {"ammo_delivered", e.ammo_delivered},
        {"supply_delivered", e.supply_delivered},
        {"supply_line_interdicted", e.supply_line_interdicted},
        {"interdicting_units", e.interdicting_units}
    };
}

inline void to_json(json& j, const GameEvent& e) {
    std::visit([&j](const auto& event) { to_json(j, event); }, e);
}

}  // namespace karkas
