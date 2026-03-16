#pragma once

#include "../types.hpp"
#include "../unit.hpp"
#include "../terrain/terrain_engine.hpp"
#include <random>
#include <vector>

namespace karkas {

// Detection result
struct DetectionResult {
    bool detected;
    ContactConfidence confidence;
    std::optional<UnitType> identified_type;
    std::optional<Echelon> identified_echelon;
    Coordinates observed_position;
    double position_error_km;  // How accurate is position estimate
    std::string detection_source;
};

// Intelligence report combining multiple detections
struct IntelReport {
    std::string report_id;
    TurnNumber turn;
    UnitId observer_id;

    std::vector<Contact> new_contacts;
    std::vector<Contact> updated_contacts;
    std::vector<UnitId> lost_contacts;

    std::string summary;
};

class SensorModel {
public:
    SensorModel();
    explicit SensorModel(unsigned seed);

    void set_terrain(const TerrainEngine* terrain) { terrain_ = terrain; }
    void set_ew_environment(const EWEnvironment* ew) { ew_environment_ = ew; }

    // Single sensor check
    DetectionResult check_detection(const Unit& observer, const Sensor& sensor,
                                   const Unit& target,
                                   const Weather& weather,
                                   const TimeOfDay& time) const;

    // Check all sensors on a unit
    std::vector<DetectionResult> scan_with_unit(const Unit& observer,
                                                const std::vector<Unit*>& potential_targets,
                                                const Weather& weather,
                                                const TimeOfDay& time) const;

    // Generate intelligence report for a faction
    IntelReport generate_intel_report(const std::vector<Unit*>& friendly_units,
                                      const std::vector<Unit*>& enemy_units,
                                      TurnNumber turn,
                                      const Weather& weather,
                                      const TimeOfDay& time) const;

    // Update contact based on new detection
    void update_contact(Contact& contact, const DetectionResult& detection,
                       TurnNumber current_turn) const;

    // Age out old contacts and return lost contact IDs
    std::vector<UnitId> age_contacts(std::vector<Contact>& contacts,
                                      std::chrono::system_clock::time_point current_time,
                                      std::chrono::hours max_age) const;

    // Merge nearby contacts based on spatial proximity
    // Returns merged contact list (combines multiple detections of same area)
    std::vector<Contact> merge_contacts(const std::vector<Contact>& contacts,
                                        double merge_radius_km = 0.5) const;

    // Apply fog of war to contacts - obscures position based on confidence
    // Unknown contacts are hidden, Suspected get large position error,
    // Probable get moderate error, Confirmed get accurate positions
    std::vector<Contact> apply_fog_of_war(const std::vector<Contact>& contacts) const;

    // Calculate detection probability modifiers
    double get_terrain_concealment(const Coordinates& pos) const;
    double get_posture_modifier(Posture posture) const;
    double get_movement_modifier(bool is_moving) const;
    double get_unit_size_modifier(Echelon echelon) const;

    // Electronic warfare effects
    double get_jamming_modifier(const Sensor& sensor, const Coordinates& observer_pos,
                                const Coordinates& target_pos) const;
    bool is_sensor_jammed(const Sensor& sensor, const Coordinates& pos) const;

    // Activate jamming from a unit's jammers
    static JammingEffect create_jamming_effect(const Unit& jammer_unit, const Jammer& jammer);

private:
    const TerrainEngine* terrain_;
    const EWEnvironment* ew_environment_;
    mutable std::mt19937 rng_;

    // Detection probability calculation
    double calculate_base_detection_prob(const Sensor& sensor,
                                        double range_km,
                                        double target_signature) const;

    // Identification probability
    double calculate_identification_prob(const Sensor& sensor,
                                        double range_km,
                                        ContactConfidence current_confidence) const;

    // Position error based on sensor and conditions
    double calculate_position_error(const Sensor& sensor,
                                   double range_km,
                                   const Weather& weather) const;
};

// Perception state for a faction
class PerceptionState {
public:
    PerceptionState(Faction faction);

    Faction get_faction() const { return faction_; }

    // Own units (full information)
    void add_own_unit(const Unit& unit);
    void update_own_unit(const Unit& unit);
    const std::vector<Unit>& get_own_units() const { return own_units_; }

    // Enemy contacts
    void add_contact(Contact contact);
    void update_contact(const Contact& contact);
    void remove_contact(const std::string& contact_id);
    const std::vector<Contact>& get_contacts() const { return contacts_; }
    Contact* get_contact(const std::string& contact_id);
    const Contact* get_contact(const std::string& contact_id) const;

    // Fog of war: get filtered contacts with position obscuring
    // This is the primary method for getting faction-specific view
    std::vector<Contact> get_filtered_contacts() const;

    // Age contacts and track lost ones
    // Returns list of contact IDs that were removed
    std::vector<UnitId> age_and_prune_contacts(
        std::chrono::system_clock::time_point current_time,
        std::chrono::hours max_age = std::chrono::hours(24));

    // Get lost contacts since last check
    const std::vector<UnitId>& get_lost_contacts() const { return lost_contacts_; }
    void clear_lost_contacts() { lost_contacts_.clear(); }

    // Control zones
    void add_control_zone(ControlZone zone);
    void update_control_zone(const ControlZone& zone);
    const std::vector<ControlZone>& get_control_zones() const { return control_zones_; }

    // Generate text summary for AI consumption
    std::string generate_situation_summary() const;
    std::string generate_contact_report() const;
    std::string generate_own_forces_report() const;

    // Serialization
    std::string to_json() const;
    static PerceptionState from_json(const std::string& json);

private:
    Faction faction_;
    std::vector<Unit> own_units_;
    std::vector<Contact> contacts_;
    std::vector<ControlZone> control_zones_;
    std::vector<UnitId> lost_contacts_;  // Contacts removed due to age
    mutable std::mt19937 fog_rng_{std::random_device{}()};  // RNG for fog of war position jitter
};

}  // namespace karkas
