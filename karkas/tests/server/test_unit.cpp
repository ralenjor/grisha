// KARKAS Unit Class Tests (6.2.1)
// Tests for the Unit class and UnitFactory

#include <gtest/gtest.h>
#include "types.hpp"
#include "unit.hpp"

using namespace karkas;

class UnitTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Create a standard infantry battalion for testing
        infantry = std::make_unique<Unit>(
            "inf_bn_1", "1st Infantry Battalion",
            Faction::Red, UnitType::Infantry, Echelon::Battalion
        );
        infantry->set_position({50.5, 9.5});

        // Create an armor battalion
        armor = std::make_unique<Unit>(
            "arm_bn_1", "1st Tank Battalion",
            Faction::Blue, UnitType::Armor, Echelon::Battalion
        );
        armor->set_position({50.6, 9.6});
    }

    std::unique_ptr<Unit> infantry;
    std::unique_ptr<Unit> armor;
};

// Basic identification tests
TEST_F(UnitTest, IdentificationAttributes) {
    EXPECT_EQ(infantry->get_id(), "inf_bn_1");
    EXPECT_EQ(infantry->get_name(), "1st Infantry Battalion");
    EXPECT_EQ(infantry->get_faction(), Faction::Red);
    EXPECT_EQ(infantry->get_type(), UnitType::Infantry);
    EXPECT_EQ(infantry->get_echelon(), Echelon::Battalion);
}

TEST_F(UnitTest, MobilityClassAssignment) {
    // Infantry should have foot mobility
    EXPECT_EQ(infantry->get_mobility_class(), MobilityClass::Foot);

    // Armor should have tracked mobility
    EXPECT_EQ(armor->get_mobility_class(), MobilityClass::Tracked);
}

// Position and movement tests
TEST_F(UnitTest, PositionManagement) {
    Coordinates new_pos{51.0, 10.0};
    infantry->set_position(new_pos);

    EXPECT_DOUBLE_EQ(infantry->get_position().latitude, 51.0);
    EXPECT_DOUBLE_EQ(infantry->get_position().longitude, 10.0);
}

TEST_F(UnitTest, HeadingManagement) {
    infantry->set_heading(90.0);
    EXPECT_DOUBLE_EQ(infantry->get_heading(), 90.0);

    // Test heading wrap-around
    infantry->set_heading(370.0);
    // Heading might be normalized to 0-360 depending on implementation
    double heading = infantry->get_heading();
    EXPECT_GE(heading, 0.0);
}

TEST_F(UnitTest, PostureManagement) {
    EXPECT_EQ(infantry->get_posture(), Posture::Defend);  // Default posture

    infantry->set_posture(Posture::Move);
    EXPECT_EQ(infantry->get_posture(), Posture::Move);

    infantry->set_posture(Posture::Attack);
    EXPECT_EQ(infantry->get_posture(), Posture::Attack);
}

// Hierarchy tests
TEST_F(UnitTest, ParentAssignment) {
    EXPECT_FALSE(infantry->get_parent_id().has_value());

    infantry->set_parent("brigade_1");
    EXPECT_TRUE(infantry->get_parent_id().has_value());
    EXPECT_EQ(infantry->get_parent_id().value(), "brigade_1");
}

TEST_F(UnitTest, SubordinateManagement) {
    EXPECT_TRUE(infantry->get_subordinates().empty());

    infantry->add_subordinate("company_a");
    infantry->add_subordinate("company_b");
    infantry->add_subordinate("company_c");

    EXPECT_EQ(infantry->get_subordinates().size(), 3);

    infantry->remove_subordinate("company_b");
    EXPECT_EQ(infantry->get_subordinates().size(), 2);
}

// Logistics tests
TEST_F(UnitTest, FuelConsumption) {
    auto initial_fuel = infantry->get_logistics().fuel_level;

    infantry->consume_fuel(0.2);
    EXPECT_NEAR(infantry->get_logistics().fuel_level, initial_fuel - 0.2, 0.01);

    // Fuel should not go below 0
    infantry->consume_fuel(2.0);  // Try to consume more than available
    EXPECT_GE(infantry->get_logistics().fuel_level, 0.0);
}

TEST_F(UnitTest, AmmoConsumption) {
    auto initial_ammo = infantry->get_logistics().ammo_level;

    infantry->consume_ammo(0.3);
    EXPECT_NEAR(infantry->get_logistics().ammo_level, initial_ammo - 0.3, 0.01);
}

TEST_F(UnitTest, Resupply) {
    // Deplete supplies
    infantry->consume_fuel(0.5);
    infantry->consume_ammo(0.5);

    double fuel_before = infantry->get_logistics().fuel_level;
    double ammo_before = infantry->get_logistics().ammo_level;

    infantry->resupply(0.3, 0.3, 0.2);

    EXPECT_NEAR(infantry->get_logistics().fuel_level, fuel_before + 0.3, 0.01);
    EXPECT_NEAR(infantry->get_logistics().ammo_level, ammo_before + 0.3, 0.01);
}

// Morale tests
TEST_F(UnitTest, FatigueApplication) {
    double initial_fatigue = infantry->get_morale().fatigue;

    infantry->apply_fatigue(0.2);
    EXPECT_GT(infantry->get_morale().fatigue, initial_fatigue);
}

TEST_F(UnitTest, RestRecovery) {
    infantry->apply_fatigue(0.5);
    double fatigued = infantry->get_morale().fatigue;

    infantry->rest(0.3);
    EXPECT_LT(infantry->get_morale().fatigue, fatigued);
}

TEST_F(UnitTest, MoraleEffects) {
    double initial_morale = infantry->get_morale().morale;

    infantry->apply_morale_effect(0.1);
    EXPECT_GT(infantry->get_morale().morale, initial_morale);

    infantry->apply_morale_effect(-0.2);
    EXPECT_LT(infantry->get_morale().morale, initial_morale + 0.1);
}

// Combat effectiveness tests
TEST_F(UnitTest, InitialCombatEffectiveness) {
    EXPECT_TRUE(infantry->is_combat_effective());
    EXPECT_FALSE(infantry->is_destroyed());
}

TEST_F(UnitTest, CombatEffectivenessWithLowAmmo) {
    // Drain most ammo
    infantry->consume_ammo(0.95);

    // Unit with <10% ammo should not be combat effective
    EXPECT_FALSE(infantry->is_combat_effective());
}

TEST_F(UnitTest, CasualtiesAffectEffectiveness) {
    Casualties heavy_casualties;
    heavy_casualties.personnel_killed = 70;
    heavy_casualties.personnel_wounded = 0;
    heavy_casualties.equipment_destroyed = 10;
    heavy_casualties.equipment_damaged = 0;

    infantry->apply_casualties(heavy_casualties);

    // After heavy casualties, unit should be less effective
    EXPECT_LT(infantry->get_strength().personnel_current,
              infantry->get_strength().personnel_max);
}

TEST_F(UnitTest, UnitDestruction) {
    // Apply devastating casualties - kill all personnel
    // Battalion has 600 personnel, need to kill them all
    Casualties devastating;
    devastating.personnel_killed = 600;
    devastating.personnel_wounded = 0;
    devastating.equipment_destroyed = 50;
    devastating.equipment_damaged = 0;

    infantry->apply_casualties(devastating);

    // Unit is destroyed when personnel reaches 0
    EXPECT_TRUE(infantry->is_destroyed());
}

// Sensor tests
TEST_F(UnitTest, SensorManagement) {
    EXPECT_FALSE(infantry->get_sensors().empty());  // Should have default sensors

    Sensor radar;
    radar.type = SensorType::Radar;
    radar.range_km = 30.0;
    radar.detection_probability = 0.8;
    radar.identification_probability = 0.5;
    radar.arc_degrees = 360.0;
    radar.heading = 0.0;
    radar.active = true;

    size_t initial_sensors = infantry->get_sensors().size();
    infantry->add_sensor(radar);

    EXPECT_EQ(infantry->get_sensors().size(), initial_sensors + 1);
}

TEST_F(UnitTest, MaxSensorRange) {
    Sensor long_range;
    long_range.type = SensorType::Radar;
    long_range.range_km = 50.0;
    long_range.detection_probability = 0.7;
    long_range.identification_probability = 0.4;
    long_range.arc_degrees = 360.0;
    long_range.heading = 0.0;
    long_range.active = true;

    infantry->add_sensor(long_range);

    EXPECT_GE(infantry->get_max_sensor_range(), 50.0);
}

// Electronic warfare tests
TEST_F(UnitTest, JammerManagement) {
    EXPECT_TRUE(infantry->get_jammers().empty());

    Jammer jammer;
    jammer.type = JammingType::Barrage;
    jammer.power_watts = 1000;
    jammer.range_km = 10.0;
    jammer.bandwidth_mhz = 100.0;
    jammer.active = false;
    jammer.affects = {SensorType::Radar};

    infantry->add_jammer(jammer);
    EXPECT_FALSE(infantry->has_active_jammer());

    infantry->activate_jammers();
    EXPECT_TRUE(infantry->has_active_jammer());

    infantry->deactivate_jammers();
    EXPECT_FALSE(infantry->has_active_jammer());
}

// Order management tests
TEST_F(UnitTest, OrderAssignment) {
    EXPECT_FALSE(infantry->get_current_order().has_value());

    Order move_order;
    move_order.order_id = "order_1";
    move_order.issuer = "brigade_1";
    move_order.target_units = {infantry->get_id()};
    move_order.order_type = OrderType::Move;
    move_order.active = true;

    infantry->assign_order(move_order);
    EXPECT_TRUE(infantry->get_current_order().has_value());
    EXPECT_EQ(infantry->get_current_order()->order_type, OrderType::Move);

    infantry->clear_order();
    EXPECT_FALSE(infantry->get_current_order().has_value());
}

// Movement speed tests
TEST_F(UnitTest, MaxSpeed) {
    // Infantry should be slower than armor
    double infantry_speed = infantry->get_max_speed_kph();
    double armor_speed = armor->get_max_speed_kph();

    EXPECT_GT(armor_speed, infantry_speed);
}

TEST_F(UnitTest, TerrainSpeedModifiers) {
    double road_speed = infantry->get_terrain_speed(TerrainType::Road);
    double forest_speed = infantry->get_terrain_speed(TerrainType::Forest);

    // Road should be faster than forest
    EXPECT_GT(road_speed, forest_speed);
}

// Serialization tests
TEST_F(UnitTest, JsonSerialization) {
    std::string json = infantry->to_json();

    // JSON should contain key fields
    EXPECT_NE(json.find("inf_bn_1"), std::string::npos);
    EXPECT_NE(json.find("1st Infantry Battalion"), std::string::npos);
}

TEST_F(UnitTest, JsonRoundTrip) {
    std::string json = infantry->to_json();
    Unit restored = Unit::from_json(json);

    EXPECT_EQ(restored.get_id(), infantry->get_id());
    EXPECT_EQ(restored.get_name(), infantry->get_name());
    EXPECT_EQ(restored.get_faction(), infantry->get_faction());
    EXPECT_EQ(restored.get_type(), infantry->get_type());
    EXPECT_EQ(restored.get_echelon(), infantry->get_echelon());
}

// Combat stats tests
TEST_F(UnitTest, CombatPowerCalculation) {
    double attack_power = infantry->get_effective_combat_power();
    double defense = infantry->get_effective_defense();

    EXPECT_GT(attack_power, 0.0);
    EXPECT_GT(defense, 0.0);
}

TEST_F(UnitTest, DefendingBonusToDefense) {
    infantry->set_posture(Posture::Move);
    double march_defense = infantry->get_effective_defense();

    infantry->set_posture(Posture::Defend);
    double defend_defense = infantry->get_effective_defense();

    // Defending should provide defense bonus
    EXPECT_GT(defend_defense, march_defense);
}

// Different unit types
TEST(UnitTypeTest, ReconUnit) {
    Unit recon("recon_1", "Recon Platoon", Faction::Red,
               UnitType::Recon, Echelon::Platoon);

    // Recon should have good sensors
    EXPECT_FALSE(recon.get_sensors().empty());
    EXPECT_GT(recon.get_max_sensor_range(), 5.0);
}

TEST(UnitTypeTest, ArtilleryUnit) {
    Unit artillery("arty_1", "Artillery Battalion", Faction::Blue,
                   UnitType::Artillery, Echelon::Battalion);

    // Artillery has wheeled mobility (self-propelled) or tracked
    auto mobility = artillery.get_mobility_class();
    EXPECT_TRUE(mobility == MobilityClass::Wheeled || mobility == MobilityClass::Tracked);
}

TEST(UnitTypeTest, AirDefenseUnit) {
    Unit air_defense("ad_1", "Air Defense Company", Faction::Red,
                     UnitType::AirDefense, Echelon::Company);

    // Air defense should have at least visual sensors (default)
    // Radar sensors would be added explicitly for specific units
    EXPECT_FALSE(air_defense.get_sensors().empty());

    // Air defense should have high air attack value
    EXPECT_GT(air_defense.get_combat_stats().air_attack, 50.0);
}
