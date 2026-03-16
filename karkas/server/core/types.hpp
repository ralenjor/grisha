#pragma once

#include <cstdint>
#include <string>
#include <vector>
#include <optional>
#include <chrono>
#include <variant>
#include <memory>
#include <unordered_map>

namespace karkas {

// Forward declarations
struct Unit;
struct Contact;
struct Order;
struct TerrainCell;

// Basic types
using UnitId = std::string;
using PlayerId = std::string;
using OrderId = std::string;
using TurnNumber = uint32_t;

// Geographic coordinates
struct Coordinates {
    double latitude;
    double longitude;

    double distance_to(const Coordinates& other) const;
    double bearing_to(const Coordinates& other) const;
    Coordinates move_toward(double bearing_deg, double distance_km) const;

    bool operator==(const Coordinates& other) const {
        return latitude == other.latitude && longitude == other.longitude;
    }
};

// Bounding box for regions
struct BoundingBox {
    Coordinates southwest;
    Coordinates northeast;

    bool contains(const Coordinates& point) const;
    double width_km() const;
    double height_km() const;
};

// Enumerations
enum class Faction {
    Red,
    Blue,
    Neutral
};

enum class UnitType {
    Infantry,
    Armor,
    Mechanized,
    Artillery,
    AirDefense,
    Rotary,
    FixedWing,
    Support,
    Headquarters,
    Recon,
    Engineer,
    Logistics
};

enum class Echelon {
    Squad,      // ~10
    Platoon,    // ~30-50
    Company,    // ~100-200
    Battalion,  // ~500-800
    Regiment,   // ~2000-3000
    Brigade,    // ~3000-5000
    Division,   // ~10000-15000
    Corps,      // ~30000-50000
    Army        // ~100000+
};

enum class Posture {
    Attack,
    Defend,
    Move,
    Recon,
    Support,
    Reserve,
    Retreat,
    Disengaged
};

enum class MobilityClass {
    Foot,
    Wheeled,
    Tracked,
    Rotary,
    FixedWing
};

enum class TerrainType {
    Open,
    Forest,
    Urban,
    Water,
    Mountain,
    Marsh,
    Desert,
    Road,
    Bridge
};

enum class CoverLevel {
    None,
    Light,
    Medium,
    Heavy,
    Fortified
};

enum class SensorType {
    Visual,
    Thermal,
    Radar,
    SignalsIntel,  // Renamed from SIGINT to avoid conflict with signal.h macro
    Acoustic,
    Satellite,
    HumanIntel
};

enum class OrderType {
    Move,
    Attack,
    Defend,
    Support,
    Recon,
    Withdraw,
    Resupply,
    Hold
};

enum class RoutePreference {
    Fastest,
    Covered,
    Specified,
    Avoid_Enemy
};

enum class RulesOfEngagement {
    WeaponsFree,
    WeaponsHold,
    WeaponsTight
};

enum class ContactConfidence {
    Confirmed,    // Currently observed
    Probable,     // Recently observed, high confidence
    Suspected,    // Degraded data or inference
    Unknown       // Minimal information
};

// Sensor definition
struct Sensor {
    SensorType type;
    double range_km;
    double detection_probability;
    double identification_probability;
    double arc_degrees;  // 360 for all-around
    double heading;      // Center of arc
    bool active;         // Can be detected itself
};

// Electronic Warfare types
enum class JammingType {
    Noise,          // Broadband noise jamming
    Deceptive,      // False target generation
    Spot,           // Targeted frequency jamming
    Barrage         // Wide-spectrum saturation
};

// Jammer equipment on a unit
struct Jammer {
    JammingType type;
    double power_watts;         // Effective radiated power
    double range_km;            // Effective jamming radius
    double bandwidth_mhz;       // Frequency coverage
    bool active;                // Currently transmitting
    std::vector<SensorType> affects;  // Which sensor types it can jam
};

// Active jamming effect in an area
struct JammingEffect {
    std::string source_unit_id;
    Coordinates center;
    double radius_km;
    JammingType type;
    double intensity;           // 0.0 - 1.0, affects detection degradation
    std::vector<SensorType> affected_sensors;
};

// Electronic warfare state for the battlefield
struct EWEnvironment {
    std::vector<JammingEffect> active_jamming;

    // Get total jamming intensity affecting a sensor type at a position
    double get_jamming_intensity(const Coordinates& pos, SensorType sensor) const {
        double total = 0.0;
        for (const auto& jam : active_jamming) {
            // Check if this jamming affects this sensor type
            bool affects = false;
            for (auto affected : jam.affected_sensors) {
                if (affected == sensor) {
                    affects = true;
                    break;
                }
            }
            if (!affects) continue;

            // Calculate distance-based effect
            double dist = pos.distance_to(jam.center);
            if (dist < jam.radius_km) {
                // Intensity falls off with distance squared
                double falloff = 1.0 - (dist * dist) / (jam.radius_km * jam.radius_km);
                total += jam.intensity * falloff;
            }
        }
        return std::min(total, 1.0);
    }
};

// Combat statistics
struct CombatStats {
    double combat_power;     // Offensive capability
    double defense_value;    // Defensive capability
    double soft_attack;      // vs. infantry
    double hard_attack;      // vs. armor
    double air_attack;       // vs. aircraft
    double air_defense;      // defense vs. air
};

// Logistics state
struct LogisticsState {
    double fuel_level;        // 0.0 - 1.0
    double ammo_level;        // 0.0 - 1.0
    double supply_level;      // 0.0 - 1.0 (food, medical, etc.)
    double maintenance_state; // 0.0 - 1.0 (equipment readiness)

    double get_effectiveness_modifier() const {
        return std::min({fuel_level, ammo_level, supply_level, maintenance_state});
    }
};

// Morale and fatigue
struct MoraleState {
    double morale;    // 0.0 - 1.0
    double fatigue;   // 0.0 - 1.0 (1.0 = exhausted)
    double cohesion;  // 0.0 - 1.0 (unit integrity)

    double get_effectiveness_modifier() const {
        return morale * cohesion * (1.0 - fatigue * 0.5);
    }
};

// Casualty tracking
struct Casualties {
    uint32_t personnel_killed;
    uint32_t personnel_wounded;
    uint32_t equipment_destroyed;
    uint32_t equipment_damaged;
};

// Unit strength
struct UnitStrength {
    uint32_t personnel_current;
    uint32_t personnel_max;
    uint32_t equipment_current;
    uint32_t equipment_max;

    double get_strength_ratio() const {
        double personnel_ratio = static_cast<double>(personnel_current) / personnel_max;
        double equipment_ratio = static_cast<double>(equipment_current) / equipment_max;
        return (personnel_ratio + equipment_ratio) / 2.0;
    }
};

// Contact report (enemy unit observation)
struct Contact {
    UnitId contact_id;
    std::optional<UnitId> actual_unit_id;  // Ground truth link (server only)

    Coordinates position;
    Coordinates last_known_position;
    std::chrono::system_clock::time_point last_observed;

    ContactConfidence confidence;
    std::optional<UnitType> estimated_type;
    std::optional<Echelon> estimated_echelon;
    std::optional<double> estimated_strength;

    Faction faction;
    std::string source;  // How it was detected
};

// Order objective
struct Objective {
    enum class Type { Position, Unit, Zone };

    Type type;
    std::optional<Coordinates> coordinates;
    std::optional<UnitId> target_unit_id;
    std::optional<std::string> zone_name;
    std::optional<std::vector<Coordinates>> zone_polygon;
};

// Order constraints
struct OrderConstraints {
    RoutePreference route;
    std::optional<std::chrono::hours> timing_offset;  // H+N hours
    RulesOfEngagement roe;
    std::optional<double> max_casualties_percent;
    std::optional<std::vector<Coordinates>> specified_route;
};

// Full order structure
struct Order {
    OrderId order_id;
    UnitId issuer;
    std::vector<UnitId> target_units;
    OrderType order_type;
    Objective objective;
    OrderConstraints constraints;

    std::string natural_language;  // Original text for review
    TurnNumber issued_turn;
    bool active;
};

// Zone of control
struct ControlZone {
    std::string zone_id;
    std::vector<Coordinates> polygon;
    Faction controller;
    double control_strength;  // 0.0 - 1.0
};

// Weather conditions
struct Weather {
    enum class Precipitation { None, Light, Moderate, Heavy };
    enum class Visibility { Clear, Haze, Fog, Smoke };

    Precipitation precipitation;
    Visibility visibility;
    double temperature_c;
    double wind_speed_kph;
    double wind_direction;

    double get_visibility_modifier() const;
    double get_mobility_modifier() const;
};

// Time of day
struct TimeOfDay {
    uint8_t hour;    // 0-23
    uint8_t minute;  // 0-59

    bool is_night() const { return hour < 6 || hour >= 20; }
    bool is_twilight() const { return (hour >= 5 && hour < 7) || (hour >= 19 && hour < 21); }
    double get_visibility_modifier() const;
};

// Turn state
struct TurnState {
    TurnNumber turn_number;
    std::chrono::system_clock::time_point simulation_time;
    std::chrono::hours turn_length;
    Weather weather;
    TimeOfDay time_of_day;
};

// Event types for logging
struct CombatEvent {
    TurnNumber turn;
    UnitId attacker;
    UnitId defender;
    Coordinates location;
    Casualties attacker_casualties;
    Casualties defender_casualties;
    bool attacker_retreated;
    bool defender_retreated;
};

struct DetectionEvent {
    TurnNumber turn;
    UnitId observer;
    UnitId observed;
    Coordinates location;
    SensorType sensor_used;
    ContactConfidence confidence;
};

struct MovementEvent {
    TurnNumber turn;
    UnitId unit;
    Coordinates from;
    Coordinates to;
    double distance_km;
    bool completed;
};

struct SupplyEvent {
    TurnNumber turn;
    UnitId unit;
    std::string depot_id;
    double fuel_delivered;
    double ammo_delivered;
    double supply_delivered;
    bool supply_line_interdicted;
    std::vector<UnitId> interdicting_units;
};

using GameEvent = std::variant<CombatEvent, DetectionEvent, MovementEvent, SupplyEvent>;

}  // namespace karkas
