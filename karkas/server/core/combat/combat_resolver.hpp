#pragma once

#include "../types.hpp"
#include "../unit.hpp"
#include "../terrain/terrain_engine.hpp"
#include <random>

namespace karkas {

// Combat result for a single engagement
struct CombatResult {
    UnitId attacker_id;
    UnitId defender_id;

    Casualties attacker_casualties;
    Casualties defender_casualties;

    bool attacker_retreated;
    bool defender_retreated;
    bool defender_destroyed;

    Coordinates final_attacker_position;
    Coordinates final_defender_position;

    double attacker_morale_delta;
    double defender_morale_delta;

    std::string narrative;  // Text description for reporting
};

// Parameters affecting combat resolution
struct CombatModifiers {
    double terrain_defense_mod;
    double terrain_attack_mod;
    double posture_mod;
    double supply_mod;
    double morale_mod;
    double weather_mod;
    double time_of_day_mod;
    double surprise_mod;
    double combined_arms_mod;

    double get_total_attack_modifier() const {
        return terrain_attack_mod * posture_mod * supply_mod *
               morale_mod * weather_mod * time_of_day_mod *
               surprise_mod * combined_arms_mod;
    }

    double get_total_defense_modifier() const {
        return terrain_defense_mod * posture_mod * supply_mod *
               morale_mod * weather_mod;
    }
};

class CombatResolver {
public:
    CombatResolver();
    explicit CombatResolver(unsigned seed);

    // Set terrain reference for terrain-based modifiers
    void set_terrain(const TerrainEngine* terrain) { terrain_ = terrain; }

    // Main combat resolution
    CombatResult resolve_engagement(Unit& attacker, Unit& defender,
                                   const Weather& weather,
                                   const TimeOfDay& time);

    // Fire support resolution (artillery, air strikes)
    CombatResult resolve_fire_support(Unit& fire_unit, Unit& target,
                                      const Weather& weather);

    // Calculate combat odds without resolving
    double calculate_odds_ratio(const Unit& attacker, const Unit& defender) const;

    // Estimate casualties without resolving
    std::pair<Casualties, Casualties> estimate_casualties(
        const Unit& attacker, const Unit& defender) const;

    // Check if unit should retreat
    bool should_retreat(const Unit& unit, const Casualties& taken) const;

    // Calculate combined arms bonus
    double calculate_combined_arms_bonus(
        const std::vector<Unit*>& attacking_units) const;

private:
    const TerrainEngine* terrain_;
    std::mt19937 rng_;

    // Internal resolution functions
    CombatModifiers calculate_modifiers(const Unit& attacker, const Unit& defender,
                                        const Weather& weather,
                                        const TimeOfDay& time) const;

    double calculate_base_casualties(double combat_power, double opposing_power,
                                    double randomness) const;

    Casualties distribute_casualties(const Unit& unit, double casualty_factor) const;

    std::string generate_combat_narrative(const Unit& attacker, const Unit& defender,
                                         const CombatResult& result) const;

    // Doctrine-based probability tables
    struct CasualtyTable {
        double odds_ratio;
        double attacker_casualty_rate;
        double defender_casualty_rate;
        double attacker_retreat_prob;
        double defender_retreat_prob;
    };

    static const std::vector<CasualtyTable> CASUALTY_TABLE;
    CasualtyTable lookup_casualty_rates(double odds_ratio) const;
};

// Multi-unit engagement resolver
class BattleResolver {
public:
    BattleResolver(CombatResolver& combat_resolver);

    struct BattleResult {
        std::vector<CombatResult> engagements;
        std::vector<UnitId> retreating_units;
        std::vector<UnitId> destroyed_units;
        Faction battle_winner;
        std::string battle_narrative;
    };

    // Resolve combat between multiple units in an area
    BattleResult resolve_battle(std::vector<Unit*>& attackers,
                               std::vector<Unit*>& defenders,
                               const Weather& weather,
                               const TimeOfDay& time);

    // Assign targets for combat
    std::vector<std::pair<Unit*, Unit*>> assign_targets(
        std::vector<Unit*>& attackers,
        std::vector<Unit*>& defenders) const;

private:
    CombatResolver& combat_resolver_;

    // Target priority scoring
    double calculate_target_priority(const Unit& attacker, const Unit& target) const;
};

}  // namespace karkas
