#pragma once

#include "types.hpp"
#include <memory>
#include <vector>

namespace karkas {

class Unit {
public:
    Unit(UnitId id, std::string name, Faction faction, UnitType type, Echelon echelon);

    // Identification
    UnitId get_id() const { return id_; }
    std::string get_name() const { return name_; }
    Faction get_faction() const { return faction_; }
    UnitType get_type() const { return type_; }
    Echelon get_echelon() const { return echelon_; }
    MobilityClass get_mobility_class() const { return mobility_class_; }

    // Hierarchy
    std::optional<UnitId> get_parent_id() const { return parent_id_; }
    void set_parent(UnitId parent) { parent_id_ = parent; }
    const std::vector<UnitId>& get_subordinates() const { return subordinate_ids_; }
    void add_subordinate(UnitId sub) { subordinate_ids_.push_back(sub); }
    void remove_subordinate(UnitId sub);

    // Position and movement
    Coordinates get_position() const { return position_; }
    void set_position(Coordinates pos) { position_ = pos; }
    double get_heading() const { return heading_; }
    void set_heading(double h) { heading_ = h; }
    Posture get_posture() const { return posture_; }
    void set_posture(Posture p) { posture_ = p; }

    // Combat
    const CombatStats& get_combat_stats() const { return combat_stats_; }
    void set_combat_stats(CombatStats stats) { combat_stats_ = stats; }
    double get_effective_combat_power() const;
    double get_effective_defense() const;

    // Sensors
    const std::vector<Sensor>& get_sensors() const { return sensors_; }
    void add_sensor(Sensor sensor) { sensors_.push_back(sensor); }
    double get_max_sensor_range() const;

    // Electronic Warfare
    const std::vector<Jammer>& get_jammers() const { return jammers_; }
    void add_jammer(Jammer jammer) { jammers_.push_back(jammer); }
    bool has_active_jammer() const;
    void activate_jammers();
    void deactivate_jammers();

    // Logistics
    const LogisticsState& get_logistics() const { return logistics_; }
    LogisticsState& get_logistics_mut() { return logistics_; }
    void consume_fuel(double amount);
    void consume_ammo(double amount);
    void resupply(double fuel, double ammo, double supply);

    // Morale
    const MoraleState& get_morale() const { return morale_; }
    MoraleState& get_morale_mut() { return morale_; }
    void apply_fatigue(double amount);
    void rest(double recovery);
    void apply_morale_effect(double delta);

    // Strength and casualties
    const UnitStrength& get_strength() const { return strength_; }
    UnitStrength& get_strength_mut() { return strength_; }
    void apply_casualties(const Casualties& cas);
    bool is_combat_effective() const;
    bool is_destroyed() const;

    // Orders
    std::optional<Order> get_current_order() const { return current_order_; }
    void assign_order(Order order) { current_order_ = order; }
    void clear_order() { current_order_ = std::nullopt; }

    // Movement
    double get_max_speed_kph() const;
    double get_terrain_speed(TerrainType terrain) const;

    // Serialization
    std::string to_json() const;
    static Unit from_json(const std::string& json);

private:
    // Identity
    UnitId id_;
    std::string name_;
    Faction faction_;
    UnitType type_;
    Echelon echelon_;
    MobilityClass mobility_class_;

    // Hierarchy
    std::optional<UnitId> parent_id_;
    std::vector<UnitId> subordinate_ids_;

    // Position
    Coordinates position_;
    double heading_;  // degrees
    Posture posture_;

    // Combat
    CombatStats combat_stats_;
    std::vector<Sensor> sensors_;
    std::vector<Jammer> jammers_;

    // State
    LogisticsState logistics_;
    MoraleState morale_;
    UnitStrength strength_;

    // Current orders
    std::optional<Order> current_order_;
};

// Default unit templates
struct UnitTemplate {
    std::string template_name;
    UnitType type;
    Echelon echelon;
    MobilityClass mobility;
    CombatStats combat_stats;
    std::vector<Sensor> sensors;
    UnitStrength base_strength;
    double max_speed_kph;
};

// Factory for creating units from templates
class UnitFactory {
public:
    static UnitFactory& instance();

    void register_template(const std::string& name, UnitTemplate tmpl);
    Unit create_unit(const std::string& template_name, UnitId id,
                     const std::string& name, Faction faction);
    void load_templates_from_file(const std::string& filepath);

private:
    UnitFactory() = default;
    std::unordered_map<std::string, UnitTemplate> templates_;
};

}  // namespace karkas
