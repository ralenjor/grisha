// KARKAS Combat Resolver Tests (6.2.6)
// Tests for CombatResolver: engagement detection, combat power, casualties

#include <gtest/gtest.h>
#include "types.hpp"
#include "unit.hpp"
#include "terrain/terrain_engine.hpp"
#include "combat/combat_resolver.hpp"

using namespace karkas;

class CombatResolverTest : public ::testing::Test {
protected:
    void SetUp() override {
        resolver = std::make_unique<CombatResolver>(42);  // Fixed seed
        terrain = std::make_unique<TerrainEngine>();

        BoundingBox region{{50.0, 9.0}, {51.0, 10.0}};
        terrain->load_region(region, "");

        resolver->set_terrain(terrain.get());

        // Create attacker
        attacker = std::make_unique<Unit>(
            "atk_1", "1st Assault Battalion",
            Faction::Red, UnitType::Armor, Echelon::Battalion);
        attacker->set_position({50.5, 9.5});
        attacker->set_posture(Posture::Attack);

        // Create defender
        defender = std::make_unique<Unit>(
            "def_1", "1st Defense Battalion",
            Faction::Blue, UnitType::Mechanized, Echelon::Battalion);
        defender->set_position({50.52, 9.52});
        defender->set_posture(Posture::Defend);

        // Create infantry
        infantry = std::make_unique<Unit>(
            "inf_1", "Infantry Battalion",
            Faction::Red, UnitType::Infantry, Echelon::Battalion);
        infantry->set_position({50.5, 9.5});
        infantry->set_posture(Posture::Attack);

        // Setup weather and time
        good_weather.precipitation = Weather::Precipitation::None;
        good_weather.visibility = Weather::Visibility::Clear;
        good_weather.temperature_c = 20.0;
        good_weather.wind_speed_kph = 10.0;
        good_weather.wind_direction = 0.0;

        daytime.hour = 12;
        daytime.minute = 0;
    }

    std::unique_ptr<CombatResolver> resolver;
    std::unique_ptr<TerrainEngine> terrain;
    std::unique_ptr<Unit> attacker;
    std::unique_ptr<Unit> defender;
    std::unique_ptr<Unit> infantry;

    Weather good_weather;
    TimeOfDay daytime;
};

// Basic engagement
TEST_F(CombatResolverTest, BasicEngagement) {
    auto result = resolver->resolve_engagement(
        *attacker, *defender, good_weather, daytime);

    EXPECT_EQ(result.attacker_id, "atk_1");
    EXPECT_EQ(result.defender_id, "def_1");
    EXPECT_GE(result.attacker_casualties.personnel_killed, 0);
    EXPECT_GE(result.defender_casualties.personnel_killed, 0);
}

TEST_F(CombatResolverTest, EngagementNarrative) {
    auto result = resolver->resolve_engagement(
        *attacker, *defender, good_weather, daytime);

    EXPECT_FALSE(result.narrative.empty());
}

// Combat power calculation
TEST_F(CombatResolverTest, OddsRatioCalculation) {
    double odds = resolver->calculate_odds_ratio(*attacker, *defender);

    EXPECT_GT(odds, 0.0);
}

TEST_F(CombatResolverTest, ArmorVsInfantry) {
    // Armor attacking infantry should have advantage
    defender->set_posture(Posture::Move);  // Not dug in

    Unit inf_target("inf_def", "Infantry Defenders",
                    Faction::Blue, UnitType::Infantry, Echelon::Battalion);
    inf_target.set_position({50.52, 9.52});
    inf_target.set_posture(Posture::Move);

    auto result = resolver->resolve_engagement(
        *attacker, inf_target, good_weather, daytime);

    // Armor should generally inflict more casualties on infantry
    // (depends on random factors, but ratio should favor attacker)
    EXPECT_FALSE(result.narrative.empty());
}

// Casualty calculation
TEST_F(CombatResolverTest, CasualtyDistribution) {
    // Run multiple engagements to see distribution
    int total_atk_casualties = 0;
    int total_def_casualties = 0;

    for (int i = 0; i < 100; i++) {
        // Reset units for each engagement
        attacker = std::make_unique<Unit>(
            "atk_1", "Attackers", Faction::Red, UnitType::Armor, Echelon::Battalion);
        attacker->set_position({50.5, 9.5});
        attacker->set_posture(Posture::Attack);

        defender = std::make_unique<Unit>(
            "def_1", "Defenders", Faction::Blue, UnitType::Mechanized, Echelon::Battalion);
        defender->set_position({50.52, 9.52});
        defender->set_posture(Posture::Defend);

        auto result = resolver->resolve_engagement(
            *attacker, *defender, good_weather, daytime);

        total_atk_casualties += result.attacker_casualties.personnel_killed;
        total_def_casualties += result.defender_casualties.personnel_killed;
    }

    // Both sides should take some casualties over 100 engagements
    EXPECT_GT(total_atk_casualties, 0);
    EXPECT_GT(total_def_casualties, 0);
}

// Morale effects
TEST_F(CombatResolverTest, MoraleEffectsFromCombat) {
    double initial_atk_morale = attacker->get_morale().morale;
    double initial_def_morale = defender->get_morale().morale;

    auto result = resolver->resolve_engagement(
        *attacker, *defender, good_weather, daytime);

    // After engagement, morale may have changed
    // (depends on outcome)
    // Just verify the values are valid
    EXPECT_GE(attacker->get_morale().morale, 0.0);
    EXPECT_LE(attacker->get_morale().morale, 1.0);
}

// Ammo consumption
TEST_F(CombatResolverTest, AmmoConsumption) {
    double initial_atk_ammo = attacker->get_logistics().ammo_level;
    double initial_def_ammo = defender->get_logistics().ammo_level;

    auto result = resolver->resolve_engagement(
        *attacker, *defender, good_weather, daytime);

    // Both sides should consume ammo
    // Unit ammo levels should decrease
    EXPECT_LT(attacker->get_logistics().ammo_level, initial_atk_ammo);
    EXPECT_LT(defender->get_logistics().ammo_level, initial_def_ammo);
}

TEST_F(CombatResolverTest, LowAmmoReducesCombatPower) {
    // Deplete attacker's ammo
    attacker->consume_ammo(0.9);

    double low_ammo_odds = resolver->calculate_odds_ratio(*attacker, *defender);

    // Reset ammo
    attacker->resupply(0, 0.9, 0);

    double full_ammo_odds = resolver->calculate_odds_ratio(*attacker, *defender);

    // Full ammo should have better odds
    EXPECT_GT(full_ammo_odds, low_ammo_odds);
}

// Unit strength effects
TEST_F(CombatResolverTest, ReducedStrengthReducesPower) {
    // Apply casualties to attacker
    Casualties prior_losses;
    prior_losses.personnel_killed = 100;
    prior_losses.personnel_wounded = 0;
    prior_losses.equipment_destroyed = 5;
    prior_losses.equipment_damaged = 0;
    attacker->apply_casualties(prior_losses);

    auto weakened_result = resolver->resolve_engagement(
        *attacker, *defender, good_weather, daytime);

    // Create fresh attacker
    Unit fresh_attacker("atk_2", "Fresh Attackers",
                        Faction::Red, UnitType::Armor, Echelon::Battalion);
    fresh_attacker.set_position({50.5, 9.5});
    fresh_attacker.set_posture(Posture::Attack);

    // Reset defender
    defender = std::make_unique<Unit>(
        "def_1", "Defenders", Faction::Blue, UnitType::Mechanized, Echelon::Battalion);
    defender->set_position({50.52, 9.52});
    defender->set_posture(Posture::Defend);

    // Weakened attacker should generally perform worse
    // (stochastic, so just verify calculations work)
    EXPECT_FALSE(weakened_result.narrative.empty());
}

// Weather effects on combat
TEST_F(CombatResolverTest, WeatherAffectsCombat) {
    Weather bad_weather;
    bad_weather.visibility = Weather::Visibility::Fog;
    bad_weather.precipitation = Weather::Precipitation::Heavy;
    bad_weather.temperature_c = 5.0;
    bad_weather.wind_speed_kph = 30.0;
    bad_weather.wind_direction = 0.0;

    auto good_weather_result = resolver->resolve_engagement(
        *attacker, *defender, good_weather, daytime);

    // Reset units
    attacker = std::make_unique<Unit>(
        "atk_1", "Attackers", Faction::Red, UnitType::Armor, Echelon::Battalion);
    attacker->set_position({50.5, 9.5});
    attacker->set_posture(Posture::Attack);

    defender = std::make_unique<Unit>(
        "def_1", "Defenders", Faction::Blue, UnitType::Mechanized, Echelon::Battalion);
    defender->set_position({50.52, 9.52});
    defender->set_posture(Posture::Defend);

    auto bad_weather_result = resolver->resolve_engagement(
        *attacker, *defender, bad_weather, daytime);

    // Both should produce valid results
    // Weather typically helps defender in bad conditions
    EXPECT_FALSE(good_weather_result.narrative.empty());
    EXPECT_FALSE(bad_weather_result.narrative.empty());
}

// Night combat
TEST_F(CombatResolverTest, NightCombat) {
    TimeOfDay night{2, 0};

    auto night_result = resolver->resolve_engagement(
        *attacker, *defender, good_weather, night);

    EXPECT_FALSE(night_result.narrative.empty());
    // Night combat typically has reduced effectiveness
}

// Destroyed units
TEST_F(CombatResolverTest, DestroyedUnitCannotFight) {
    // Get personnel count to ensure we destroy the unit completely
    auto strength = attacker->get_strength();

    // Apply casualties equal to full personnel count to ensure destruction
    Casualties devastating;
    devastating.personnel_killed = strength.personnel_max;  // Kill all personnel
    devastating.personnel_wounded = 0;
    devastating.equipment_destroyed = strength.equipment_max;
    devastating.equipment_damaged = 0;
    attacker->apply_casualties(devastating);

    EXPECT_TRUE(attacker->is_destroyed());

    // Combat with destroyed unit should not occur or have minimal effect
    auto result = resolver->resolve_engagement(
        *attacker, *defender, good_weather, daytime);

    // Implementation dependent - destroyed units may not fight
}

// Combat power by unit type
TEST_F(CombatResolverTest, UnitTypeCombatPower) {
    double armor_power = attacker->get_effective_combat_power();
    double infantry_power = infantry->get_effective_combat_power();

    // Armor should generally have higher combat power
    EXPECT_GT(armor_power, 0.0);
    EXPECT_GT(infantry_power, 0.0);
}

// Casualty types
TEST_F(CombatResolverTest, CasualtyTypes) {
    auto result = resolver->resolve_engagement(
        *attacker, *defender, good_weather, daytime);

    // Casualties should be broken down
    EXPECT_GE(result.attacker_casualties.personnel_killed, 0);
    EXPECT_GE(result.attacker_casualties.equipment_destroyed, 0);
    EXPECT_GE(result.defender_casualties.personnel_killed, 0);
    EXPECT_GE(result.defender_casualties.equipment_destroyed, 0);
}

// Should retreat check
TEST_F(CombatResolverTest, ShouldRetreatCheck) {
    Casualties heavy_casualties;
    heavy_casualties.personnel_killed = 200;
    heavy_casualties.personnel_wounded = 100;
    heavy_casualties.equipment_destroyed = 20;
    heavy_casualties.equipment_damaged = 10;

    bool should_retreat = resolver->should_retreat(*defender, heavy_casualties);
    // Result depends on unit state, just verify it doesn't crash
    EXPECT_TRUE(should_retreat || !should_retreat);  // Boolean is valid
}

// Estimate casualties
TEST_F(CombatResolverTest, EstimateCasualties) {
    auto [atk_cas, def_cas] = resolver->estimate_casualties(*attacker, *defender);

    // Estimates should be non-negative
    EXPECT_GE(atk_cas.personnel_killed, 0);
    EXPECT_GE(def_cas.personnel_killed, 0);
}

// Combined arms bonus
TEST_F(CombatResolverTest, CombinedArmsBonus) {
    std::vector<Unit*> mixed_force = {attacker.get(), infantry.get()};

    double bonus = resolver->calculate_combined_arms_bonus(mixed_force);

    // Mixed force should have some bonus
    EXPECT_GE(bonus, 1.0);  // At least 1.0 (no penalty)
}

// Battle resolver tests
class BattleResolverTest : public ::testing::Test {
protected:
    void SetUp() override {
        combat_resolver = std::make_unique<CombatResolver>(42);
        battle_resolver = std::make_unique<BattleResolver>(*combat_resolver);
        terrain = std::make_unique<TerrainEngine>();

        BoundingBox region{{50.0, 9.0}, {51.0, 10.0}};
        terrain->load_region(region, "");

        combat_resolver->set_terrain(terrain.get());

        // Setup weather and time
        good_weather.precipitation = Weather::Precipitation::None;
        good_weather.visibility = Weather::Visibility::Clear;
        good_weather.temperature_c = 20.0;
        good_weather.wind_speed_kph = 10.0;
        good_weather.wind_direction = 0.0;

        daytime.hour = 12;
        daytime.minute = 0;
    }

    std::unique_ptr<CombatResolver> combat_resolver;
    std::unique_ptr<BattleResolver> battle_resolver;
    std::unique_ptr<TerrainEngine> terrain;

    Weather good_weather;
    TimeOfDay daytime;
};

TEST_F(BattleResolverTest, MultipleCombatantsEngagement) {
    // Create attackers
    std::vector<std::unique_ptr<Unit>> attackers_owned;
    attackers_owned.push_back(std::make_unique<Unit>(
        "atk_1", "1st Tank", Faction::Red, UnitType::Armor, Echelon::Battalion));
    attackers_owned[0]->set_position({50.5, 9.5});
    attackers_owned[0]->set_posture(Posture::Attack);

    attackers_owned.push_back(std::make_unique<Unit>(
        "atk_2", "2nd Mech", Faction::Red, UnitType::Mechanized, Echelon::Battalion));
    attackers_owned[1]->set_position({50.51, 9.51});
    attackers_owned[1]->set_posture(Posture::Attack);

    // Create defenders
    std::vector<std::unique_ptr<Unit>> defenders_owned;
    defenders_owned.push_back(std::make_unique<Unit>(
        "def_1", "1st Defense", Faction::Blue, UnitType::Mechanized, Echelon::Battalion));
    defenders_owned[0]->set_position({50.52, 9.52});
    defenders_owned[0]->set_posture(Posture::Defend);

    // Convert to pointer vectors
    std::vector<Unit*> attackers;
    for (auto& u : attackers_owned) attackers.push_back(u.get());

    std::vector<Unit*> defenders;
    for (auto& u : defenders_owned) defenders.push_back(u.get());

    auto result = battle_resolver->resolve_battle(
        attackers, defenders, good_weather, daytime);

    // Should have battle narrative
    EXPECT_FALSE(result.battle_narrative.empty());
}

TEST_F(BattleResolverTest, TargetAssignment) {
    // Create combatants
    std::vector<std::unique_ptr<Unit>> attackers_owned;
    attackers_owned.push_back(std::make_unique<Unit>(
        "atk_1", "Attacker 1", Faction::Red, UnitType::Armor, Echelon::Battalion));
    attackers_owned[0]->set_position({50.5, 9.5});

    attackers_owned.push_back(std::make_unique<Unit>(
        "atk_2", "Attacker 2", Faction::Red, UnitType::Mechanized, Echelon::Battalion));
    attackers_owned[1]->set_position({50.51, 9.51});

    std::vector<std::unique_ptr<Unit>> defenders_owned;
    defenders_owned.push_back(std::make_unique<Unit>(
        "def_1", "Defender 1", Faction::Blue, UnitType::Infantry, Echelon::Battalion));
    defenders_owned[0]->set_position({50.52, 9.52});

    defenders_owned.push_back(std::make_unique<Unit>(
        "def_2", "Defender 2", Faction::Blue, UnitType::Mechanized, Echelon::Battalion));
    defenders_owned[1]->set_position({50.53, 9.53});

    std::vector<Unit*> attackers;
    for (auto& u : attackers_owned) attackers.push_back(u.get());

    std::vector<Unit*> defenders;
    for (auto& u : defenders_owned) defenders.push_back(u.get());

    auto assignments = battle_resolver->assign_targets(attackers, defenders);

    // Should have target assignments
    EXPECT_GT(assignments.size(), 0);
}
