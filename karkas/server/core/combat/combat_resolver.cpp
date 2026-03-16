#include "combat_resolver.hpp"
#include <algorithm>
#include <cmath>
#include <sstream>

namespace karkas {

// Doctrine-based casualty table (based on historical military analysis)
// Odds ratio: attacker strength / defender strength
const std::vector<CombatResolver::CasualtyTable> CombatResolver::CASUALTY_TABLE = {
    // odds,  atk_cas, def_cas, atk_ret, def_ret
    {0.25,    0.30,    0.05,    0.80,    0.05},  // Defender has 4:1 advantage
    {0.50,    0.20,    0.08,    0.50,    0.10},  // Defender has 2:1 advantage
    {0.75,    0.15,    0.12,    0.30,    0.15},  // Defender has slight advantage
    {1.00,    0.12,    0.15,    0.20,    0.25},  // Even odds
    {1.50,    0.10,    0.18,    0.10,    0.35},  // Attacker has slight advantage
    {2.00,    0.08,    0.22,    0.05,    0.50},  // Attacker has 2:1 advantage
    {3.00,    0.05,    0.28,    0.02,    0.70},  // Attacker has 3:1 advantage
    {4.00,    0.03,    0.35,    0.01,    0.85},  // Attacker has 4:1 advantage
    {5.00,    0.02,    0.45,    0.01,    0.95},  // Attacker has 5:1 advantage
};

CombatResolver::CombatResolver()
    : terrain_(nullptr), rng_(std::random_device{}()) {}

CombatResolver::CombatResolver(unsigned seed)
    : terrain_(nullptr), rng_(seed) {}

CombatResolver::CasualtyTable CombatResolver::lookup_casualty_rates(double odds_ratio) const {
    // Clamp odds ratio
    odds_ratio = std::clamp(odds_ratio, 0.1, 10.0);

    // Find bracketing entries
    for (size_t i = 1; i < CASUALTY_TABLE.size(); ++i) {
        if (odds_ratio <= CASUALTY_TABLE[i].odds_ratio) {
            // Interpolate between entries
            const auto& low = CASUALTY_TABLE[i - 1];
            const auto& high = CASUALTY_TABLE[i];

            double t = (odds_ratio - low.odds_ratio) / (high.odds_ratio - low.odds_ratio);

            return {
                odds_ratio,
                low.attacker_casualty_rate + t * (high.attacker_casualty_rate - low.attacker_casualty_rate),
                low.defender_casualty_rate + t * (high.defender_casualty_rate - low.defender_casualty_rate),
                low.attacker_retreat_prob + t * (high.attacker_retreat_prob - low.attacker_retreat_prob),
                low.defender_retreat_prob + t * (high.defender_retreat_prob - low.defender_retreat_prob)
            };
        }
    }

    return CASUALTY_TABLE.back();
}

CombatModifiers CombatResolver::calculate_modifiers(const Unit& attacker, const Unit& defender,
                                                    const Weather& weather,
                                                    const TimeOfDay& time) const {
    CombatModifiers mods;

    // Terrain modifiers
    mods.terrain_attack_mod = 1.0;
    mods.terrain_defense_mod = 1.0;

    if (terrain_) {
        auto def_cell = terrain_->get_cell(defender.get_position());
        mods.terrain_defense_mod = def_cell.get_defense_modifier();
        mods.terrain_attack_mod = def_cell.get_attack_modifier();
    }

    // Posture modifiers
    mods.posture_mod = 1.0;
    switch (defender.get_posture()) {
        case Posture::Defend:
            mods.terrain_defense_mod *= 1.5;
            break;
        case Posture::Attack:
            mods.terrain_defense_mod *= 0.8;  // Less effective at defense
            break;
        case Posture::Move:
            mods.terrain_defense_mod *= 0.6;  // Caught moving
            break;
        default:
            break;
    }

    switch (attacker.get_posture()) {
        case Posture::Attack:
            mods.posture_mod = 1.2;
            break;
        case Posture::Recon:
            mods.posture_mod = 0.8;
            break;
        default:
            mods.posture_mod = 1.0;
    }

    // Supply modifiers
    double atk_supply = attacker.get_logistics().get_effectiveness_modifier();
    double def_supply = defender.get_logistics().get_effectiveness_modifier();
    mods.supply_mod = atk_supply / std::max(def_supply, 0.1);

    // Morale modifiers
    double atk_morale = attacker.get_morale().get_effectiveness_modifier();
    double def_morale = defender.get_morale().get_effectiveness_modifier();
    mods.morale_mod = atk_morale / std::max(def_morale, 0.1);

    // Weather modifier
    mods.weather_mod = weather.get_visibility_modifier();

    // Time of day modifier
    mods.time_of_day_mod = time.get_visibility_modifier();

    // Surprise modifier (simplified - would need detection history)
    mods.surprise_mod = 1.0;

    // Combined arms bonus (simplified - would check supporting units)
    mods.combined_arms_mod = 1.0;

    return mods;
}

double CombatResolver::calculate_odds_ratio(const Unit& attacker, const Unit& defender) const {
    double atk_power = attacker.get_effective_combat_power();
    double def_power = defender.get_effective_defense();

    return atk_power / std::max(def_power, 0.1);
}

Casualties CombatResolver::distribute_casualties(const Unit& unit, double casualty_factor) const {
    Casualties cas{};

    const auto& strength = unit.get_strength();

    // Calculate total casualties
    uint32_t personnel_cas = static_cast<uint32_t>(
        strength.personnel_current * casualty_factor);
    uint32_t equipment_cas = static_cast<uint32_t>(
        strength.equipment_current * casualty_factor * 0.5);  // Equipment harder to destroy

    // Split between killed/wounded (roughly 1:3 ratio historically)
    cas.personnel_killed = personnel_cas / 4;
    cas.personnel_wounded = personnel_cas - cas.personnel_killed;

    // Split between destroyed/damaged
    cas.equipment_destroyed = equipment_cas / 3;
    cas.equipment_damaged = equipment_cas - cas.equipment_destroyed;

    return cas;
}

CombatResult CombatResolver::resolve_engagement(Unit& attacker, Unit& defender,
                                                const Weather& weather,
                                                const TimeOfDay& time) {
    CombatResult result;
    result.attacker_id = attacker.get_id();
    result.defender_id = defender.get_id();
    result.attacker_retreated = false;
    result.defender_retreated = false;
    result.defender_destroyed = false;

    // Calculate modifiers
    auto mods = calculate_modifiers(attacker, defender, weather, time);

    // Calculate modified odds ratio
    double base_odds = calculate_odds_ratio(attacker, defender);
    double modified_odds = base_odds * mods.get_total_attack_modifier() /
                          mods.get_total_defense_modifier();

    // Look up casualty rates
    auto rates = lookup_casualty_rates(modified_odds);

    // Add randomness
    std::uniform_real_distribution<double> dist(0.5, 1.5);
    double atk_random = dist(rng_);
    double def_random = dist(rng_);

    // Calculate casualties
    double atk_casualty_rate = rates.attacker_casualty_rate * atk_random;
    double def_casualty_rate = rates.defender_casualty_rate * def_random;

    result.attacker_casualties = distribute_casualties(attacker, atk_casualty_rate);
    result.defender_casualties = distribute_casualties(defender, def_casualty_rate);

    // Apply casualties
    attacker.apply_casualties(result.attacker_casualties);
    defender.apply_casualties(result.defender_casualties);

    // Consume ammunition
    attacker.consume_ammo(0.1 + 0.1 * dist(rng_));
    defender.consume_ammo(0.08 + 0.08 * dist(rng_));

    // Morale effects
    result.attacker_morale_delta = -atk_casualty_rate * 0.5;
    result.defender_morale_delta = -def_casualty_rate * 0.5;

    // Victory bonus to morale
    if (modified_odds > 1.5) {
        result.attacker_morale_delta += 0.1;
        result.defender_morale_delta -= 0.1;
    } else if (modified_odds < 0.7) {
        result.attacker_morale_delta -= 0.1;
        result.defender_morale_delta += 0.1;
    }

    attacker.apply_morale_effect(result.attacker_morale_delta);
    defender.apply_morale_effect(result.defender_morale_delta);

    // Check for retreat
    std::uniform_real_distribution<double> retreat_dist(0.0, 1.0);

    if (retreat_dist(rng_) < rates.attacker_retreat_prob ||
        should_retreat(attacker, result.attacker_casualties)) {
        result.attacker_retreated = true;
    }

    if (retreat_dist(rng_) < rates.defender_retreat_prob ||
        should_retreat(defender, result.defender_casualties)) {
        result.defender_retreated = true;
    }

    // Check for destruction
    if (defender.is_destroyed()) {
        result.defender_destroyed = true;
        result.defender_retreated = false;
    }

    // Calculate final positions
    result.final_attacker_position = attacker.get_position();
    result.final_defender_position = defender.get_position();

    if (result.attacker_retreated) {
        // Retreat 2-5 km away from defender
        double retreat_dist_km = 2.0 + dist(rng_) * 3.0;
        double bearing = defender.get_position().bearing_to(attacker.get_position());
        result.final_attacker_position = attacker.get_position().move_toward(bearing, retreat_dist_km);
        attacker.set_position(result.final_attacker_position);
        attacker.set_posture(Posture::Retreat);
    }

    if (result.defender_retreated && !result.defender_destroyed) {
        double retreat_dist_km = 2.0 + dist(rng_) * 3.0;
        double bearing = attacker.get_position().bearing_to(defender.get_position());
        result.final_defender_position = defender.get_position().move_toward(bearing, retreat_dist_km);
        defender.set_position(result.final_defender_position);
        defender.set_posture(Posture::Retreat);
    }

    // Generate narrative
    result.narrative = generate_combat_narrative(attacker, defender, result);

    return result;
}

CombatResult CombatResolver::resolve_fire_support(Unit& fire_unit, Unit& target,
                                                  const Weather& weather) {
    CombatResult result;
    result.attacker_id = fire_unit.get_id();
    result.defender_id = target.get_id();
    result.attacker_retreated = false;
    result.defender_retreated = false;
    result.defender_destroyed = false;
    result.attacker_casualties = {};

    // Fire support doesn't risk the firing unit
    // Calculate effectiveness
    double base_effectiveness = 0.15;  // Base casualty rate from artillery

    // Range modifier
    double range_km = fire_unit.get_position().distance_to(target.get_position());
    double max_range = 30.0;  // Artillery typical range
    double range_mod = 1.0 - (range_km / max_range) * 0.3;
    range_mod = std::max(range_mod, 0.5);

    // Weather modifier
    double weather_mod = weather.get_visibility_modifier();

    // Target posture modifier
    double posture_mod = 1.0;
    switch (target.get_posture()) {
        case Posture::Defend: posture_mod = 0.6; break;  // Dug in
        case Posture::Move: posture_mod = 1.5; break;    // Exposed
        default: break;
    }

    // Terrain modifier
    double terrain_mod = 1.0;
    if (terrain_) {
        auto cell = terrain_->get_cell(target.get_position());
        terrain_mod = 1.0 / cell.get_defense_modifier();
    }

    // Calculate final casualty rate
    std::uniform_real_distribution<double> dist(0.5, 1.5);
    double casualty_rate = base_effectiveness * range_mod * weather_mod *
                          posture_mod * terrain_mod * dist(rng_);

    result.defender_casualties = distribute_casualties(target, casualty_rate);
    target.apply_casualties(result.defender_casualties);

    // Consume ammo for fire unit
    fire_unit.consume_ammo(0.15);

    // Morale effect from bombardment
    result.defender_morale_delta = -0.1 * casualty_rate * 10;
    target.apply_morale_effect(result.defender_morale_delta);

    // Check for destruction
    if (target.is_destroyed()) {
        result.defender_destroyed = true;
    }

    result.final_attacker_position = fire_unit.get_position();
    result.final_defender_position = target.get_position();

    std::stringstream ss;
    ss << fire_unit.get_name() << " conducts fire mission against "
       << target.get_name() << ". Target suffers "
       << result.defender_casualties.personnel_killed << " KIA, "
       << result.defender_casualties.personnel_wounded << " WIA.";
    result.narrative = ss.str();

    return result;
}

std::pair<Casualties, Casualties> CombatResolver::estimate_casualties(
    const Unit& attacker, const Unit& defender) const {

    double odds = calculate_odds_ratio(attacker, defender);
    auto rates = lookup_casualty_rates(odds);

    Casualties atk_cas = distribute_casualties(attacker, rates.attacker_casualty_rate);
    Casualties def_cas = distribute_casualties(defender, rates.defender_casualty_rate);

    return {atk_cas, def_cas};
}

bool CombatResolver::should_retreat(const Unit& unit, const Casualties& taken) const {
    // Check multiple factors for retreat

    // Heavy casualties trigger retreat
    double casualty_ratio = static_cast<double>(taken.personnel_killed + taken.personnel_wounded) /
                           std::max(unit.get_strength().personnel_max, 1u);
    if (casualty_ratio > 0.25) return true;

    // Low morale triggers retreat
    if (unit.get_morale().morale < 0.3) return true;

    // Low cohesion triggers retreat
    if (unit.get_morale().cohesion < 0.3) return true;

    // Out of ammo triggers retreat
    if (unit.get_logistics().ammo_level < 0.1) return true;

    // Near destruction triggers retreat
    if (unit.get_strength().get_strength_ratio() < 0.3) return true;

    return false;
}

double CombatResolver::calculate_combined_arms_bonus(
    const std::vector<Unit*>& attacking_units) const {

    bool has_infantry = false;
    bool has_armor = false;
    bool has_artillery = false;
    bool has_air = false;

    for (const auto* unit : attacking_units) {
        switch (unit->get_type()) {
            case UnitType::Infantry:
            case UnitType::Mechanized:
                has_infantry = true;
                break;
            case UnitType::Armor:
                has_armor = true;
                break;
            case UnitType::Artillery:
                has_artillery = true;
                break;
            case UnitType::Rotary:
            case UnitType::FixedWing:
                has_air = true;
                break;
            default:
                break;
        }
    }

    double bonus = 1.0;

    // Combined arms bonuses
    if (has_infantry && has_armor) bonus += 0.2;
    if ((has_infantry || has_armor) && has_artillery) bonus += 0.15;
    if ((has_infantry || has_armor) && has_air) bonus += 0.2;
    if (has_infantry && has_armor && has_artillery) bonus += 0.1;  // Additional synergy

    return bonus;
}

std::string CombatResolver::generate_combat_narrative(const Unit& attacker, const Unit& defender,
                                                     const CombatResult& result) const {
    std::stringstream ss;

    ss << attacker.get_name() << " engages " << defender.get_name() << ". ";

    // Attacker results
    if (result.attacker_casualties.personnel_killed +
        result.attacker_casualties.personnel_wounded > 0) {
        ss << attacker.get_name() << " suffers "
           << result.attacker_casualties.personnel_killed << " KIA, "
           << result.attacker_casualties.personnel_wounded << " WIA. ";
    }

    // Defender results
    if (result.defender_destroyed) {
        ss << defender.get_name() << " is destroyed. ";
    } else {
        ss << defender.get_name() << " suffers "
           << result.defender_casualties.personnel_killed << " KIA, "
           << result.defender_casualties.personnel_wounded << " WIA. ";
    }

    // Movement results
    if (result.attacker_retreated) {
        ss << attacker.get_name() << " withdraws. ";
    }
    if (result.defender_retreated && !result.defender_destroyed) {
        ss << defender.get_name() << " withdraws. ";
    }

    return ss.str();
}

// BattleResolver implementation

BattleResolver::BattleResolver(CombatResolver& combat_resolver)
    : combat_resolver_(combat_resolver) {}

double BattleResolver::calculate_target_priority(const Unit& attacker, const Unit& target) const {
    double priority = 0.0;

    // Distance - closer is higher priority
    double dist = attacker.get_position().distance_to(target.get_position());
    priority += 10.0 / (1.0 + dist);

    // Unit type matching
    // Armor vs armor, infantry vs infantry for close combat
    if (attacker.get_type() == target.get_type()) {
        priority += 2.0;
    }

    // Anti-armor targets armor
    if (attacker.get_type() == UnitType::Infantry &&
        target.get_type() == UnitType::Armor) {
        priority += 1.5;  // AT weapons
    }

    // Artillery prefers static targets
    if (attacker.get_type() == UnitType::Artillery &&
        target.get_posture() == Posture::Defend) {
        priority += 2.0;
    }

    // HQ targets are high priority
    if (target.get_type() == UnitType::Headquarters) {
        priority += 5.0;
    }

    // Weak targets are attractive
    priority += (1.0 - target.get_strength().get_strength_ratio()) * 3.0;

    return priority;
}

std::vector<std::pair<Unit*, Unit*>> BattleResolver::assign_targets(
    std::vector<Unit*>& attackers,
    std::vector<Unit*>& defenders) const {

    std::vector<std::pair<Unit*, Unit*>> assignments;

    // Simple greedy assignment based on priority
    std::vector<bool> defender_assigned(defenders.size(), false);

    for (auto* attacker : attackers) {
        double best_priority = -1;
        int best_target = -1;

        for (size_t i = 0; i < defenders.size(); ++i) {
            if (defender_assigned[i]) continue;

            double priority = calculate_target_priority(*attacker, *defenders[i]);
            if (priority > best_priority) {
                best_priority = priority;
                best_target = static_cast<int>(i);
            }
        }

        if (best_target >= 0) {
            assignments.push_back({attacker, defenders[best_target]});
            defender_assigned[best_target] = true;
        }
    }

    return assignments;
}

BattleResolver::BattleResult BattleResolver::resolve_battle(
    std::vector<Unit*>& attackers,
    std::vector<Unit*>& defenders,
    const Weather& weather,
    const TimeOfDay& time) {

    BattleResult result;

    // Calculate combined arms bonuses
    double attacker_ca_bonus = combat_resolver_.calculate_combined_arms_bonus(attackers);

    // Assign targets
    auto assignments = assign_targets(attackers, defenders);

    // Resolve each engagement
    for (auto& [attacker, defender] : assignments) {
        // Apply combined arms bonus temporarily
        // (In a more sophisticated system, this would modify the unit's stats)

        auto combat_result = combat_resolver_.resolve_engagement(*attacker, *defender,
                                                                 weather, time);
        result.engagements.push_back(combat_result);

        if (combat_result.attacker_retreated) {
            result.retreating_units.push_back(combat_result.attacker_id);
        }
        if (combat_result.defender_retreated) {
            result.retreating_units.push_back(combat_result.defender_id);
        }
        if (combat_result.defender_destroyed) {
            result.destroyed_units.push_back(combat_result.defender_id);
        }
    }

    // Determine battle winner
    int attacker_losses = 0, defender_losses = 0;
    for (const auto& eng : result.engagements) {
        attacker_losses += eng.attacker_casualties.personnel_killed +
                          eng.attacker_casualties.personnel_wounded;
        defender_losses += eng.defender_casualties.personnel_killed +
                          eng.defender_casualties.personnel_wounded;
    }

    // Winner has fewer relative losses and less retreating
    double attacker_retreat_rate = static_cast<double>(result.retreating_units.size()) /
                                  std::max(attackers.size(), size_t{1});
    double defender_retreat_rate = static_cast<double>(result.retreating_units.size()) /
                                  std::max(defenders.size(), size_t{1});

    if (defender_losses > attacker_losses * 1.5 || defender_retreat_rate > 0.5) {
        result.battle_winner = attackers.empty() ? Faction::Neutral : attackers[0]->get_faction();
    } else if (attacker_losses > defender_losses * 1.5 || attacker_retreat_rate > 0.5) {
        result.battle_winner = defenders.empty() ? Faction::Neutral : defenders[0]->get_faction();
    } else {
        result.battle_winner = Faction::Neutral;  // Inconclusive
    }

    // Generate battle narrative
    std::stringstream ss;
    ss << "Battle engaged with " << attackers.size() << " attacking units vs "
       << defenders.size() << " defending units. "
       << result.engagements.size() << " engagements resolved. ";

    for (const auto& eng : result.engagements) {
        ss << eng.narrative << " ";
    }

    result.battle_narrative = ss.str();

    return result;
}

}  // namespace karkas
