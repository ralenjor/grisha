#pragma once

#include "types.hpp"
#include "unit.hpp"
#include "orbat_manager.hpp"
#include "terrain/terrain_engine.hpp"
#include "combat/combat_resolver.hpp"
#include "sensors/sensor_model.hpp"
#include "movement/movement_resolver.hpp"
#include "logistics/supply_model.hpp"
#include <memory>
#include <functional>
#include <chrono>

namespace karkas {

// Scenario configuration
struct ScenarioConfig {
    std::string name;
    std::string description;
    BoundingBox region;
    std::string terrain_data_path;

    struct FactionConfig {
        std::string name;
        Faction faction;
        std::string doctrine;
        std::string orbat_file;
        bool ai_controlled;
    };

    FactionConfig red_faction;
    FactionConfig blue_faction;

    std::chrono::hours turn_length;
    std::chrono::system_clock::time_point start_time;
    Weather initial_weather;

    struct VictoryCondition {
        enum class Type { Territorial, Attrition, Time, Objective };
        Type type;
        std::vector<std::string> zone_names;
        Faction required_controller;
        double attrition_threshold;
        int max_turns;
    };

    std::vector<VictoryCondition> victory_conditions;
};

// Complete game state at a point in time
class GameState {
public:
    GameState();

    // Turn management
    TurnNumber get_current_turn() const { return current_turn_; }
    void advance_turn() { current_turn_++; }
    const TurnState& get_turn_state() const { return turn_state_; }
    TurnState& get_turn_state_mut() { return turn_state_; }

    // ORBAT access
    OrbatManager& get_orbat() { return orbat_; }
    const OrbatManager& get_orbat() const { return orbat_; }

    // Pending orders
    void queue_order(Order order);
    std::vector<Order>& get_pending_orders(Faction faction);
    const std::vector<Order>& get_pending_orders(Faction faction) const;
    void clear_pending_orders();

    // Perception states
    PerceptionState& get_perception(Faction faction);
    const PerceptionState& get_perception(Faction faction) const;

    // Control zones
    std::vector<ControlZone>& get_control_zones() { return control_zones_; }
    const std::vector<ControlZone>& get_control_zones() const { return control_zones_; }
    void update_control_zones();

    // Event log
    void log_event(GameEvent event);
    const std::vector<GameEvent>& get_events() const { return events_; }
    std::vector<GameEvent> get_events_for_turn(TurnNumber turn) const;

    // Serialization
    std::string to_json() const;
    static GameState from_json(const std::string& json);
    void save_to_file(const std::string& filepath) const;
    static GameState load_from_file(const std::string& filepath);

private:
    TurnNumber current_turn_;
    TurnState turn_state_;
    OrbatManager orbat_;

    std::vector<Order> red_pending_orders_;
    std::vector<Order> blue_pending_orders_;

    PerceptionState red_perception_;
    PerceptionState blue_perception_;

    std::vector<ControlZone> control_zones_;
    std::vector<GameEvent> events_;
};

// Turn execution result
struct TurnResult {
    TurnNumber turn;
    std::vector<MovementEvent> movements;
    std::vector<CombatEvent> combats;
    std::vector<DetectionEvent> detections;
    std::vector<SupplyEvent> supplies;

    // Per-faction summaries
    std::string red_summary;
    std::string blue_summary;

    // Victory check
    bool game_over;
    std::optional<Faction> winner;
    std::string victory_reason;
};

// Phase of WEGO turn
enum class TurnPhase {
    Planning,
    Execution,
    Reporting
};

// Callback for turn events
using TurnEventCallback = std::function<void(const GameEvent&)>;

// Main simulation engine
class Simulation {
public:
    Simulation();
    ~Simulation();

    // Initialization
    bool load_scenario(const ScenarioConfig& config);
    bool load_scenario_from_file(const std::string& yaml_path);

    // State access
    GameState& get_state() { return state_; }
    const GameState& get_state() const { return state_; }
    const TerrainEngine& get_terrain() const { return terrain_; }
    SupplyModel& get_supply_model() { return supply_model_; }
    const SupplyModel& get_supply_model() const { return supply_model_; }
    TurnPhase get_phase() const { return current_phase_; }

    // Order submission
    bool submit_orders(Faction faction, const std::vector<Order>& orders);
    bool validate_order(const Order& order) const;
    std::string get_order_validation_error(const Order& order) const;

    // Turn execution
    bool ready_to_execute() const;
    TurnResult execute_turn();

    // Manual phase control (for debugging/testing)
    void start_planning_phase();
    void start_execution_phase();
    void start_reporting_phase();

    // Callbacks
    void set_event_callback(TurnEventCallback callback) { event_callback_ = callback; }

    // Victory checking
    bool check_victory() const;
    std::pair<bool, Faction> get_victory_status() const;

    // Random seed control
    void set_random_seed(unsigned seed);

    // Save/Load
    void save_game(const std::string& filepath) const;
    void load_game(const std::string& filepath);

private:
    ScenarioConfig scenario_;
    GameState state_;
    TerrainEngine terrain_;
    EWEnvironment ew_environment_;

    CombatResolver combat_resolver_;
    BattleResolver battle_resolver_;
    SensorModel sensor_model_;
    MovementResolver movement_resolver_;
    SupplyModel supply_model_;

    TurnPhase current_phase_;
    bool orders_submitted_red_;
    bool orders_submitted_blue_;

    TurnEventCallback event_callback_;

    // Turn execution steps
    void resolve_movement_phase();
    void resolve_detection_phase();
    void resolve_combat_phase();
    void resolve_logistics_phase();
    void update_perceptions();
    void generate_reports(TurnResult& result);
    void update_ew_environment();

    // Helper methods
    std::vector<std::pair<std::vector<Unit*>, std::vector<Unit*>>>
        find_combat_engagements() const;

    void emit_event(const GameEvent& event);
};

}  // namespace karkas
