#include "sensor_model.hpp"
#include "../json_serialization.hpp"
#include <algorithm>
#include <cmath>
#include <sstream>
#include <iomanip>

namespace karkas {

SensorModel::SensorModel()
    : terrain_(nullptr), ew_environment_(nullptr), rng_(std::random_device{}()) {}

SensorModel::SensorModel(unsigned seed)
    : terrain_(nullptr), ew_environment_(nullptr), rng_(seed) {}

double SensorModel::get_terrain_concealment(const Coordinates& pos) const {
    if (!terrain_) return 0.0;

    auto cell = terrain_->get_cell(pos);
    return cell.concealment;
}

double SensorModel::get_posture_modifier(Posture posture) const {
    switch (posture) {
        case Posture::Defend:    return 0.5;   // Dug in, hard to see
        case Posture::Move:      return 1.5;   // Easy to see while moving
        case Posture::Attack:    return 1.3;   // Somewhat exposed
        case Posture::Recon:     return 0.7;   // Using concealment
        case Posture::Support:   return 1.0;
        case Posture::Reserve:   return 0.6;   // Hidden in reserve positions
        case Posture::Retreat:   return 1.4;   // Disorganized, visible
        case Posture::Disengaged: return 0.8;
        default: return 1.0;
    }
}

double SensorModel::get_movement_modifier(bool is_moving) const {
    return is_moving ? 1.4 : 1.0;
}

double SensorModel::get_unit_size_modifier(Echelon echelon) const {
    switch (echelon) {
        case Echelon::Squad:     return 0.3;
        case Echelon::Platoon:   return 0.5;
        case Echelon::Company:   return 0.8;
        case Echelon::Battalion: return 1.0;
        case Echelon::Regiment:  return 1.3;
        case Echelon::Brigade:   return 1.5;
        case Echelon::Division:  return 2.0;
        case Echelon::Corps:     return 2.5;
        case Echelon::Army:      return 3.0;
        default: return 1.0;
    }
}

double SensorModel::get_jamming_modifier(const Sensor& sensor, const Coordinates& observer_pos,
                                         const Coordinates& target_pos) const {
    if (!ew_environment_) return 1.0;

    // Jamming affects electronic sensors more than others
    double susceptibility = 1.0;
    switch (sensor.type) {
        case SensorType::Radar:
            susceptibility = 1.0;  // Highly susceptible
            break;
        case SensorType::SignalsIntel:
            susceptibility = 0.9;  // Very susceptible
            break;
        case SensorType::Thermal:
            susceptibility = 0.3;  // Some IR jamming possible
            break;
        case SensorType::Visual:
            susceptibility = 0.1;  // Smoke/obscurants only
            break;
        case SensorType::Acoustic:
            susceptibility = 0.2;  // Audio jamming possible
            break;
        case SensorType::Satellite:
            susceptibility = 0.5;  // GPS/comm jamming
            break;
        case SensorType::HumanIntel:
            susceptibility = 0.0;  // Not affected by EW
            break;
    }

    if (susceptibility <= 0.0) return 1.0;

    // Get jamming intensity at observer location (affects reception)
    double observer_jam = ew_environment_->get_jamming_intensity(observer_pos, sensor.type);

    // Get jamming intensity at target location (affects target signature masking)
    double target_jam = ew_environment_->get_jamming_intensity(target_pos, sensor.type);

    // Combined effect: both observer and target jamming reduce detection
    double total_jamming = std::max(observer_jam, target_jam);
    double jamming_effect = total_jamming * susceptibility;

    // Return modifier: 1.0 = no effect, 0.0 = completely jammed
    return std::clamp(1.0 - jamming_effect, 0.05, 1.0);
}

bool SensorModel::is_sensor_jammed(const Sensor& sensor, const Coordinates& pos) const {
    if (!ew_environment_) return false;

    double intensity = ew_environment_->get_jamming_intensity(pos, sensor.type);
    return intensity > 0.7;  // Consider jammed if >70% jamming intensity
}

JammingEffect SensorModel::create_jamming_effect(const Unit& jammer_unit, const Jammer& jammer) {
    JammingEffect effect;
    effect.source_unit_id = jammer_unit.get_id();
    effect.center = jammer_unit.get_position();
    effect.radius_km = jammer.range_km;
    effect.type = jammer.type;
    effect.affected_sensors = jammer.affects;

    // Calculate intensity based on jammer power and type
    switch (jammer.type) {
        case JammingType::Noise:
            // Broadband noise - moderate effect over wide area
            effect.intensity = 0.5;
            break;
        case JammingType::Deceptive:
            // Creates false targets - high intensity but may not fully block
            effect.intensity = 0.6;
            break;
        case JammingType::Spot:
            // Targeted jamming - very high intensity on specific frequencies
            effect.intensity = 0.9;
            break;
        case JammingType::Barrage:
            // Wide-spectrum saturation - high intensity
            effect.intensity = 0.8;
            break;
    }

    // Scale by power (assuming 1kW is baseline)
    double power_factor = std::log10(std::max(jammer.power_watts, 1.0) / 1000.0 + 1.0);
    effect.intensity = std::clamp(effect.intensity * (0.5 + power_factor), 0.0, 1.0);

    return effect;
}

double SensorModel::calculate_base_detection_prob(const Sensor& sensor,
                                                  double range_km,
                                                  double target_signature) const {
    if (range_km > sensor.range_km) return 0.0;

    // Base probability decreases with range
    double range_factor = 1.0 - (range_km / sensor.range_km);
    range_factor = std::pow(range_factor, 0.5);  // Sqrt for less harsh falloff

    // Combine with sensor's base detection probability
    double prob = sensor.detection_probability * range_factor * target_signature;

    return std::clamp(prob, 0.0, 0.99);
}

double SensorModel::calculate_identification_prob(const Sensor& sensor,
                                                  double range_km,
                                                  ContactConfidence current_confidence) const {
    if (range_km > sensor.range_km * 0.8) return 0.0;  // Need closer for ID

    double range_factor = 1.0 - (range_km / (sensor.range_km * 0.8));
    range_factor = std::pow(range_factor, 0.5);

    // Easier to improve confidence on already-identified contacts
    double confidence_bonus = 1.0;
    switch (current_confidence) {
        case ContactConfidence::Unknown:   confidence_bonus = 1.0; break;
        case ContactConfidence::Suspected: confidence_bonus = 1.2; break;
        case ContactConfidence::Probable:  confidence_bonus = 1.4; break;
        case ContactConfidence::Confirmed: confidence_bonus = 1.5; break;
    }

    double prob = sensor.identification_probability * range_factor * confidence_bonus;
    return std::clamp(prob, 0.0, 0.95);
}

double SensorModel::calculate_position_error(const Sensor& sensor,
                                            double range_km,
                                            const Weather& weather) const {
    // Base error scales with range
    double base_error_km = range_km * 0.02;  // 2% of range

    // Sensor type affects accuracy
    switch (sensor.type) {
        case SensorType::Visual:
            base_error_km *= 1.5;
            break;
        case SensorType::Thermal:
            base_error_km *= 0.8;
            break;
        case SensorType::Radar:
            base_error_km *= 0.3;  // Very accurate
            break;
        case SensorType::SignalsIntel:
            base_error_km *= 2.0;  // Less precise
            break;
        case SensorType::Acoustic:
            base_error_km *= 3.0;
            break;
        case SensorType::Satellite:
            base_error_km *= 0.1;  // Very accurate
            break;
        case SensorType::HumanIntel:
            base_error_km *= 5.0;  // Least precise
            break;
    }

    // Weather effects
    double weather_mod = weather.get_visibility_modifier();
    if (sensor.type == SensorType::Visual || sensor.type == SensorType::Thermal) {
        base_error_km /= weather_mod;
    }

    return std::max(base_error_km, 0.1);  // Minimum 100m error
}

DetectionResult SensorModel::check_detection(const Unit& observer, const Sensor& sensor,
                                            const Unit& target,
                                            const Weather& weather,
                                            const TimeOfDay& time) const {
    DetectionResult result;
    result.detected = false;
    result.confidence = ContactConfidence::Unknown;
    result.detection_source = observer.get_name();

    double range_km = observer.get_position().distance_to(target.get_position());

    // Check if in range
    if (range_km > sensor.range_km) {
        return result;
    }

    // Check sensor arc
    double bearing = observer.get_position().bearing_to(target.get_position());
    double arc_start = sensor.heading - sensor.arc_degrees / 2;
    double arc_end = sensor.heading + sensor.arc_degrees / 2;

    // Normalize bearing check
    if (sensor.arc_degrees < 360.0) {
        double relative_bearing = std::fmod(bearing - arc_start + 360.0, 360.0);
        if (relative_bearing > sensor.arc_degrees) {
            return result;
        }
    }

    // Check line of sight for visual/thermal sensors
    if (sensor.type == SensorType::Visual || sensor.type == SensorType::Thermal) {
        if (terrain_) {
            auto los = terrain_->calculate_sensor_los(
                observer.get_position(), target.get_position(), sensor.type);
            if (!los.has_los) {
                return result;
            }
        }
    }

    // Calculate target signature
    double signature = 1.0;
    signature *= (1.0 - get_terrain_concealment(target.get_position()));
    signature *= get_posture_modifier(target.get_posture());
    signature *= get_unit_size_modifier(target.get_echelon());
    signature *= weather.get_visibility_modifier();
    signature *= time.get_visibility_modifier();

    // Thermal sensors work better at night
    if (sensor.type == SensorType::Thermal && time.is_night()) {
        signature *= 1.5;
    }

    // Apply electronic warfare effects
    double ew_modifier = get_jamming_modifier(sensor, observer.get_position(), target.get_position());
    signature *= ew_modifier;

    // Track if we're operating under heavy jamming for later position error adjustment
    bool heavily_jammed = is_sensor_jammed(sensor, observer.get_position());

    // Calculate detection probability
    double detect_prob = calculate_base_detection_prob(sensor, range_km, signature);

    // Roll for detection
    std::uniform_real_distribution<double> dist(0.0, 1.0);
    if (dist(rng_) > detect_prob) {
        return result;
    }

    result.detected = true;
    result.observed_position = target.get_position();
    result.position_error_km = calculate_position_error(sensor, range_km, weather);

    // Apply jamming degradation to position accuracy
    if (heavily_jammed) {
        result.position_error_km *= 3.0;  // Much worse accuracy under jamming
    }

    // Add position error
    std::uniform_real_distribution<double> error_dist(-1.0, 1.0);
    result.observed_position.latitude += error_dist(rng_) * result.position_error_km / 111.0;
    result.observed_position.longitude += error_dist(rng_) * result.position_error_km / 111.0;

    // Determine confidence level
    double id_prob = calculate_identification_prob(sensor, range_km, ContactConfidence::Unknown);

    if (dist(rng_) < id_prob) {
        result.confidence = ContactConfidence::Confirmed;
        result.identified_type = target.get_type();
        result.identified_echelon = target.get_echelon();
    } else if (dist(rng_) < id_prob * 2) {
        result.confidence = ContactConfidence::Probable;
        result.identified_type = target.get_type();
    } else if (dist(rng_) < id_prob * 3) {
        result.confidence = ContactConfidence::Suspected;
    } else {
        result.confidence = ContactConfidence::Unknown;
    }

    return result;
}

std::vector<DetectionResult> SensorModel::scan_with_unit(
    const Unit& observer,
    const std::vector<Unit*>& potential_targets,
    const Weather& weather,
    const TimeOfDay& time) const {

    std::vector<DetectionResult> results;

    for (const auto& sensor : observer.get_sensors()) {
        for (const auto* target : potential_targets) {
            // Don't detect own faction
            if (target->get_faction() == observer.get_faction()) continue;

            auto result = check_detection(observer, sensor, *target, weather, time);
            if (result.detected) {
                results.push_back(result);
            }
        }
    }

    return results;
}

IntelReport SensorModel::generate_intel_report(const std::vector<Unit*>& friendly_units,
                                               const std::vector<Unit*>& enemy_units,
                                               TurnNumber turn,
                                               const Weather& weather,
                                               const TimeOfDay& time) const {
    IntelReport report;
    report.turn = turn;

    std::unordered_map<UnitId, Contact> detected_contacts;

    // Scan with each friendly unit
    for (const auto* friendly : friendly_units) {
        report.observer_id = friendly->get_id();

        auto detections = scan_with_unit(*friendly, const_cast<std::vector<Unit*>&>(enemy_units),
                                        weather, time);

        for (const auto& detection : detections) {
            // Find the actual unit this detection corresponds to
            for (const auto* enemy : enemy_units) {
                double dist = detection.observed_position.distance_to(enemy->get_position());
                if (dist < detection.position_error_km * 2) {
                    // This detection matches this enemy

                    Contact contact;
                    contact.contact_id = enemy->get_id() + "_contact";
                    contact.actual_unit_id = enemy->get_id();
                    contact.position = detection.observed_position;
                    contact.last_known_position = detection.observed_position;
                    contact.last_observed = std::chrono::system_clock::now();
                    contact.confidence = detection.confidence;
                    contact.estimated_type = detection.identified_type;
                    contact.estimated_echelon = detection.identified_echelon;
                    contact.faction = enemy->get_faction();
                    contact.source = detection.detection_source;

                    // Merge with existing detection (take best confidence)
                    auto it = detected_contacts.find(contact.contact_id);
                    if (it != detected_contacts.end()) {
                        if (detection.confidence > it->second.confidence) {
                            it->second = contact;
                        }
                    } else {
                        detected_contacts[contact.contact_id] = contact;
                    }
                    break;
                }
            }
        }
    }

    // Build contact list
    for (auto& [id, contact] : detected_contacts) {
        report.new_contacts.push_back(contact);
    }

    // Generate summary
    std::stringstream ss;
    ss << "Intel Report Turn " << turn << ": ";
    ss << report.new_contacts.size() << " enemy contacts detected. ";

    int confirmed = 0, probable = 0, suspected = 0;
    for (const auto& c : report.new_contacts) {
        switch (c.confidence) {
            case ContactConfidence::Confirmed: confirmed++; break;
            case ContactConfidence::Probable: probable++; break;
            case ContactConfidence::Suspected: suspected++; break;
            default: break;
        }
    }

    ss << confirmed << " confirmed, " << probable << " probable, "
       << suspected << " suspected.";

    report.summary = ss.str();

    return report;
}

void SensorModel::update_contact(Contact& contact, const DetectionResult& detection,
                                TurnNumber current_turn) const {
    contact.position = detection.observed_position;
    contact.last_known_position = detection.observed_position;
    contact.last_observed = std::chrono::system_clock::now();

    // Upgrade confidence if better detection
    if (detection.confidence > contact.confidence) {
        contact.confidence = detection.confidence;
    }

    // Update identification
    if (detection.identified_type.has_value()) {
        contact.estimated_type = detection.identified_type;
    }
    if (detection.identified_echelon.has_value()) {
        contact.estimated_echelon = detection.identified_echelon;
    }
}

std::vector<UnitId> SensorModel::age_contacts(std::vector<Contact>& contacts,
                              std::chrono::system_clock::time_point current_time,
                              std::chrono::hours max_age) const {
    std::vector<UnitId> lost;

    auto it = contacts.begin();
    while (it != contacts.end()) {
        auto age = current_time - it->last_observed;

        if (age > max_age) {
            // Remove very old contacts - track as lost
            lost.push_back(it->contact_id);
            it = contacts.erase(it);
        } else if (age > max_age * 3 / 4) {
            // >75% age: degrade to Suspected
            if (it->confidence == ContactConfidence::Confirmed) {
                it->confidence = ContactConfidence::Probable;
            } else if (it->confidence == ContactConfidence::Probable) {
                it->confidence = ContactConfidence::Suspected;
            }
            ++it;
        } else if (age > max_age / 2) {
            // >50% age: degrade Confirmed to Probable
            if (it->confidence == ContactConfidence::Confirmed) {
                it->confidence = ContactConfidence::Probable;
            }
            ++it;
        } else {
            ++it;
        }
    }

    return lost;
}

std::vector<Contact> SensorModel::merge_contacts(const std::vector<Contact>& contacts,
                                                  double merge_radius_km) const {
    if (contacts.empty()) return {};

    std::vector<Contact> merged;
    std::vector<bool> used(contacts.size(), false);

    for (size_t i = 0; i < contacts.size(); ++i) {
        if (used[i]) continue;

        Contact best = contacts[i];
        used[i] = true;

        // Find all contacts within merge radius
        std::vector<const Contact*> cluster;
        cluster.push_back(&contacts[i]);

        for (size_t j = i + 1; j < contacts.size(); ++j) {
            if (used[j]) continue;

            double dist = contacts[i].position.distance_to(contacts[j].position);
            if (dist <= merge_radius_km) {
                cluster.push_back(&contacts[j]);
                used[j] = true;
            }
        }

        // Merge cluster: take best confidence, most recent observation, best type/echelon
        for (const auto* c : cluster) {
            // Better confidence wins (lower enum value = higher confidence)
            if (c->confidence < best.confidence) {
                best.confidence = c->confidence;
            }

            // More recent observation wins
            if (c->last_observed > best.last_observed) {
                best.last_observed = c->last_observed;
                best.position = c->position;  // Use most recent position
            }

            // Identified type/echelon wins
            if (!best.estimated_type.has_value() && c->estimated_type.has_value()) {
                best.estimated_type = c->estimated_type;
            }
            if (!best.estimated_echelon.has_value() && c->estimated_echelon.has_value()) {
                best.estimated_echelon = c->estimated_echelon;
            }
        }

        // Update source to indicate merged report
        if (cluster.size() > 1) {
            best.source = "Multiple (" + std::to_string(cluster.size()) + " reports)";
        }

        merged.push_back(best);
    }

    return merged;
}

std::vector<Contact> SensorModel::apply_fog_of_war(const std::vector<Contact>& contacts) const {
    std::vector<Contact> filtered;
    std::uniform_real_distribution<double> dist(-1.0, 1.0);

    for (const auto& contact : contacts) {
        // Unknown confidence: hide the contact entirely (fog of war)
        if (contact.confidence == ContactConfidence::Unknown) {
            continue;
        }

        Contact fog_contact = contact;

        // Apply position jitter based on confidence
        double jitter_km = 0.0;
        switch (contact.confidence) {
            case ContactConfidence::Suspected:
                // Large uncertainty: up to 2km position error
                jitter_km = 2.0;
                // Also remove type/echelon identification
                fog_contact.estimated_type = std::nullopt;
                fog_contact.estimated_echelon = std::nullopt;
                break;

            case ContactConfidence::Probable:
                // Moderate uncertainty: up to 0.5km position error
                jitter_km = 0.5;
                // Keep type but remove echelon
                fog_contact.estimated_echelon = std::nullopt;
                break;

            case ContactConfidence::Confirmed:
                // Accurate position: minimal jitter
                jitter_km = 0.1;
                break;

            default:
                break;
        }

        // Apply random position jitter
        if (jitter_km > 0.0) {
            fog_contact.position.latitude += dist(rng_) * jitter_km / 111.0;
            fog_contact.position.longitude += dist(rng_) * jitter_km / 111.0;
        }

        filtered.push_back(fog_contact);
    }

    return filtered;
}

// PerceptionState implementation

PerceptionState::PerceptionState(Faction faction)
    : faction_(faction) {}

void PerceptionState::add_own_unit(const Unit& unit) {
    own_units_.push_back(unit);
}

void PerceptionState::update_own_unit(const Unit& unit) {
    for (auto& u : own_units_) {
        if (u.get_id() == unit.get_id()) {
            u = unit;
            return;
        }
    }
    own_units_.push_back(unit);
}

void PerceptionState::add_contact(Contact contact) {
    contacts_.push_back(std::move(contact));
}

void PerceptionState::update_contact(const Contact& contact) {
    for (auto& c : contacts_) {
        if (c.contact_id == contact.contact_id) {
            c = contact;
            return;
        }
    }
    contacts_.push_back(contact);
}

void PerceptionState::remove_contact(const std::string& contact_id) {
    contacts_.erase(
        std::remove_if(contacts_.begin(), contacts_.end(),
                      [&contact_id](const Contact& c) {
                          return c.contact_id == contact_id;
                      }),
        contacts_.end());
}

Contact* PerceptionState::get_contact(const std::string& contact_id) {
    for (auto& c : contacts_) {
        if (c.contact_id == contact_id) return &c;
    }
    return nullptr;
}

const Contact* PerceptionState::get_contact(const std::string& contact_id) const {
    for (const auto& c : contacts_) {
        if (c.contact_id == contact_id) return &c;
    }
    return nullptr;
}

void PerceptionState::add_control_zone(ControlZone zone) {
    control_zones_.push_back(std::move(zone));
}

void PerceptionState::update_control_zone(const ControlZone& zone) {
    for (auto& z : control_zones_) {
        if (z.zone_id == zone.zone_id) {
            z = zone;
            return;
        }
    }
    control_zones_.push_back(zone);
}

std::vector<Contact> PerceptionState::get_filtered_contacts() const {
    // Apply fog of war: position jitter based on confidence, hide Unknown contacts
    std::vector<Contact> filtered;
    std::uniform_real_distribution<double> dist(-1.0, 1.0);

    for (const auto& contact : contacts_) {
        // Unknown confidence: hide the contact entirely (fog of war)
        if (contact.confidence == ContactConfidence::Unknown) {
            continue;
        }

        Contact fog_contact = contact;

        // Apply position jitter based on confidence
        double jitter_km = 0.0;
        switch (contact.confidence) {
            case ContactConfidence::Suspected:
                // Large uncertainty: up to 2km position error
                jitter_km = 2.0;
                // Also remove type/echelon identification
                fog_contact.estimated_type = std::nullopt;
                fog_contact.estimated_echelon = std::nullopt;
                break;

            case ContactConfidence::Probable:
                // Moderate uncertainty: up to 0.5km position error
                jitter_km = 0.5;
                // Keep type but remove echelon
                fog_contact.estimated_echelon = std::nullopt;
                break;

            case ContactConfidence::Confirmed:
                // Accurate position: minimal jitter
                jitter_km = 0.1;
                break;

            default:
                break;
        }

        // Apply random position jitter
        if (jitter_km > 0.0) {
            fog_contact.position.latitude += dist(fog_rng_) * jitter_km / 111.0;
            fog_contact.position.longitude += dist(fog_rng_) * jitter_km / 111.0;
        }

        filtered.push_back(fog_contact);
    }

    return filtered;
}

std::vector<UnitId> PerceptionState::age_and_prune_contacts(
    std::chrono::system_clock::time_point current_time,
    std::chrono::hours max_age) {

    std::vector<UnitId> lost;

    auto it = contacts_.begin();
    while (it != contacts_.end()) {
        auto age = current_time - it->last_observed;

        if (age > max_age) {
            // Remove very old contacts - track as lost
            lost.push_back(it->contact_id);
            lost_contacts_.push_back(it->contact_id);
            it = contacts_.erase(it);
        } else if (age > max_age * 3 / 4) {
            // >75% age: degrade to Suspected
            if (it->confidence == ContactConfidence::Confirmed) {
                it->confidence = ContactConfidence::Probable;
            } else if (it->confidence == ContactConfidence::Probable) {
                it->confidence = ContactConfidence::Suspected;
            }
            ++it;
        } else if (age > max_age / 2) {
            // >50% age: degrade Confirmed to Probable
            if (it->confidence == ContactConfidence::Confirmed) {
                it->confidence = ContactConfidence::Probable;
            }
            ++it;
        } else {
            ++it;
        }
    }

    return lost;
}

std::string PerceptionState::generate_situation_summary() const {
    std::stringstream ss;

    ss << "SITUATION SUMMARY\n";
    ss << "=================\n\n";

    ss << "Own Forces: " << own_units_.size() << " units\n";
    ss << "Enemy Contacts: " << contacts_.size() << " reported\n\n";

    ss << generate_own_forces_report();
    ss << "\n";
    ss << generate_contact_report();

    return ss.str();
}

std::string PerceptionState::generate_own_forces_report() const {
    std::stringstream ss;

    ss << "OWN FORCES:\n";
    ss << "-----------\n";

    for (const auto& unit : own_units_) {
        ss << "- " << unit.get_name();
        ss << " (" << static_cast<int>(unit.get_echelon()) << "-level ";

        switch (unit.get_type()) {
            case UnitType::Infantry: ss << "Infantry"; break;
            case UnitType::Armor: ss << "Armor"; break;
            case UnitType::Mechanized: ss << "Mechanized"; break;
            case UnitType::Artillery: ss << "Artillery"; break;
            case UnitType::AirDefense: ss << "Air Defense"; break;
            case UnitType::Rotary: ss << "Rotary Wing"; break;
            case UnitType::FixedWing: ss << "Fixed Wing"; break;
            case UnitType::Support: ss << "Support"; break;
            case UnitType::Headquarters: ss << "HQ"; break;
            case UnitType::Recon: ss << "Recon"; break;
            case UnitType::Engineer: ss << "Engineer"; break;
            case UnitType::Logistics: ss << "Logistics"; break;
        }
        ss << ")";

        ss << " at (" << std::fixed << std::setprecision(4)
           << unit.get_position().latitude << ", "
           << unit.get_position().longitude << ")";

        ss << " [Strength: " << std::setprecision(0)
           << (unit.get_strength().get_strength_ratio() * 100) << "%";
        ss << ", Ammo: " << (unit.get_logistics().ammo_level * 100) << "%";
        ss << ", Fuel: " << (unit.get_logistics().fuel_level * 100) << "%]";
        ss << "\n";
    }

    return ss.str();
}

std::string PerceptionState::generate_contact_report() const {
    std::stringstream ss;

    ss << "ENEMY CONTACTS:\n";
    ss << "---------------\n";

    if (contacts_.empty()) {
        ss << "No enemy contacts reported.\n";
        return ss.str();
    }

    for (const auto& contact : contacts_) {
        ss << "- Contact " << contact.contact_id << ": ";

        switch (contact.confidence) {
            case ContactConfidence::Confirmed:
                ss << "[CONFIRMED] ";
                break;
            case ContactConfidence::Probable:
                ss << "[PROBABLE] ";
                break;
            case ContactConfidence::Suspected:
                ss << "[SUSPECTED] ";
                break;
            case ContactConfidence::Unknown:
                ss << "[UNKNOWN] ";
                break;
        }

        if (contact.estimated_type.has_value()) {
            switch (*contact.estimated_type) {
                case UnitType::Infantry: ss << "Infantry"; break;
                case UnitType::Armor: ss << "Armor"; break;
                case UnitType::Mechanized: ss << "Mechanized"; break;
                case UnitType::Artillery: ss << "Artillery"; break;
                default: ss << "Unknown type"; break;
            }
        } else {
            ss << "Unknown type";
        }

        ss << " at (" << std::fixed << std::setprecision(4)
           << contact.position.latitude << ", "
           << contact.position.longitude << ")";

        ss << " via " << contact.source;
        ss << "\n";
    }

    return ss.str();
}

std::string PerceptionState::to_json() const {
    json j;
    j["faction"] = faction_;

    // Serialize own units (simplified - just key info)
    json own_units_json = json::array();
    for (const auto& unit : own_units_) {
        json uj;
        uj["id"] = unit.get_id();
        uj["name"] = unit.get_name();
        uj["position"] = unit.get_position();
        uj["posture"] = unit.get_posture();
        uj["strength_ratio"] = unit.get_strength().get_strength_ratio();
        uj["logistics"] = unit.get_logistics();
        own_units_json.push_back(uj);
    }
    j["own_units"] = own_units_json;

    // Serialize contacts
    j["contacts"] = contacts_;

    // Serialize control zones
    j["control_zones"] = control_zones_;

    return j.dump(2);
}

PerceptionState PerceptionState::from_json(const std::string& json_str) {
    try {
        json j = json::parse(json_str);

        Faction faction = j.at("faction").get<Faction>();
        PerceptionState state(faction);

        // Load contacts
        for (const auto& contact : j.at("contacts")) {
            state.add_contact(contact.get<Contact>());
        }

        // Load control zones
        for (const auto& zone : j.at("control_zones")) {
            state.add_control_zone(zone.get<ControlZone>());
        }

        // Note: own_units are typically set from the authoritative game state,
        // not from serialized perception state
        return state;

    } catch (const json::exception& e) {
        return PerceptionState(Faction::Neutral);
    }
}

}  // namespace karkas
