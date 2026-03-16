# KARKAS Development Plan

**Project:** KARKAS - Theater-Level Military Simulation Platform
**Version:** 0.1.0
**Last Updated:** 2026-03-16

---

## Overview

KARKAS is a WEGO-based military wargame simulation integrating:
- C++ high-performance simulation engine
- Python FastAPI REST/WebSocket server
- Grisha RAG system integration for AI decision-making
- Terrain engine with GIS support
- Combat resolution system
- Sensor/detection modeling

---

## Development Status Summary

| Layer | Status | Completion |
|-------|--------|------------|
| Python API Server | COMPLETE | 100% |
| Data Models (Pydantic) | COMPLETE | 100% |
| Grisha Integration | COMPLETE | 100% |
| Client CLI | COMPLETE | 100% |
| C++ Type System | COMPLETE | 100% |
| C++ ORBAT Manager | COMPLETE | 100% |
| C++ Terrain Engine | COMPLETE | 100% |
| C++ Simulation Core | COMPLETE | 100% |
| C++ Combat Resolver | COMPLETE | 100% |
| C++ Sensor Model | COMPLETE | 100% |
| C++ Movement Resolver | COMPLETE | 100% |
| C++ Logistics Model | COMPLETE | 100% |
| JSON Serialization | COMPLETE | 100% |
| YAML Scenario Loading | COMPLETE | 100% |
| Python Tests | COMPLETE | 100% |
| C++ Tests | COMPLETE | 100% |
| Integration Tests | COMPLETE | 100% |
| Terrain Processor Tool | COMPLETE | 100% |
| Terrain Data (Fulda Gap) | COMPLETE | 100% |
| Scenario Editor Tool | COMPLETE | 100% |
| Additional Scenarios | NOT STARTED | 0% |
| Doctrine Data | NOT STARTED | 0% |
| Database Persistence | COMPLETE | 100% |
| Production Hardening | IN PROGRESS | 14% |

---

## Task List

### Legend
- [x] Completed
- [ ] Pending
- Deps: Dependencies (must be completed first)

---

## Phase 1: Foundation (Core Infrastructure)

### 1.1 Python API Server
- [x] **1.1.1** FastAPI application setup with CORS and lifespan
- [x] **1.1.2** WebSocket support for real-time updates
- [x] **1.1.3** SimulationManager in-memory state management
- [x] **1.1.4** Health check and root endpoints
- [x] **1.1.5** Unit CRUD routes (`/api/units`)
- [x] **1.1.6** Order routes (`/api/orders`)
- [x] **1.1.7** Game state routes (`/api/game`)
- [x] **1.1.8** Scenario routes (`/api/scenarios`)
- [x] **1.1.9** Perception routes (`/api/perception/{faction}`)
- [x] **1.1.10** Grisha AI control routes (`/api/grisha/*`)

### 1.2 Data Models
- [x] **1.2.1** Unit models (Coordinates, UnitType, Echelon, Faction, Posture, etc.)
- [x] **1.2.2** Order models (OrderType, RoutePreference, RulesOfEngagement, etc.)
- [x] **1.2.3** Game models (TurnPhase, GameState, TurnResult, PerceptionState, etc.)
- [x] **1.2.4** OrderBatch model for batch submissions

### 1.3 C++ Type System
- [x] **1.3.1** Core type definitions (`types.hpp`)
- [x] **1.3.2** Unit class with full attributes (`unit.hpp/cpp`)
- [x] **1.3.3** ORBAT Manager with spatial indexing (`orbat_manager.hpp/cpp`)
- [x] **1.3.4** Python bindings via pybind11 (`python_bindings.cpp`)

### 1.4 Configuration & Build
- [x] **1.4.1** CMakeLists.txt for C++ build
- [x] **1.4.2** pyproject.toml with dependencies
- [x] **1.4.3** run_server.sh launch script
- [x] **1.4.4** README.md documentation

---

## Phase 2: Grisha AI Integration

### 2.1 Commander (Red Force AI)
- [x] **2.1.1** GrishaCommander class structure
- [x] **2.1.2** Knowledge base queries to Grisha API
- [x] **2.1.3** Situation assessment generation
- [x] **2.1.4** Order generation based on doctrine
- [x] **2.1.5** Turn result evaluation
- [x] **2.1.6** Context history maintenance
- [x] **2.1.7** Colonel Viktor Petrov persona system prompt

### 2.2 Advisor (Blue Force Support)
- [x] **2.2.1** GrishaAdvisor class structure
- [x] **2.2.2** Enemy disposition analysis
- [x] **2.2.3** COA prediction
- [x] **2.2.4** Defensive position recommendations
- [x] **2.2.5** Situation assessments
- [x] **2.2.6** Order evaluation for doctrinal compliance
- [x] **2.2.7** Major Sarah Mitchell persona system prompt

### 2.3 Order Parser
- [x] **2.3.1** OrderParser class structure
- [x] **2.3.2** Regex preprocessing for order elements
- [x] **2.3.3** LLM-based structured JSON extraction
- [x] **2.3.4** Validation against available units/contacts
- [x] **2.3.5** Ambiguity detection
- [x] **2.3.6** Interactive clarification loops

---

## Phase 3: Client Interface

### 3.1 Command-Line Client
- [x] **3.1.1** KarkasClient class with async HTTP
- [x] **3.1.2** Server connection management
- [x] **3.1.3** Scenario listing and loading
- [x] **3.1.4** Game state viewing
- [x] **3.1.5** Unit listing
- [x] **3.1.6** Contact viewing
- [x] **3.1.7** Natural language order input
- [x] **3.1.8** Ready marking for turn execution
- [x] **3.1.9** Interactive menu system

### 3.2 Client Enhancements
- [x] **3.2.1** WebSocket integration for real-time updates
  - Deps: 1.1.2
  - Implemented: Async WebSocket listener with threaded input handling
  - Message types: phase_change, orders_submitted, turn_result, new_turn
- [x] **3.2.2** Order history display
  - Implemented: `orders` command shows session orders, `history` command shows turn history
- [x] **3.2.3** Turn result visualization
  - Implemented: TurnResultFormatter class with colored output for movements, combats, detections
- [x] **3.2.4** Map display (ASCII or curses-based)
  - Implemented: ASCIIMapRenderer class with `map` command
  - Features: Auto-scaling bounds, color-coded units/contacts, legend

---

## Phase 4: C++ Simulation Engine

### 4.1 Terrain Engine
- [x] **4.1.1** TerrainCell data structure
- [x] **4.1.2** TerrainEngine class header
- [x] **4.1.3** GeoPackage/GIS file loading
  - Deps: 4.1.1, 4.1.2
  - Implemented: GDAL-based loading from GeoPackage terrain_cells layer
- [x] **4.1.4** Terrain grid initialization
  - Deps: 4.1.3
  - Implemented: Grid initialization and gap filling in load_geopackage()
- [x] **4.1.5** LOS (Line of Sight) calculation implementation
  - Deps: 4.1.4
  - Implemented: calculate_los() with terrain/vegetation screening
- [x] **4.1.6** Pathfinding (A* algorithm)
  - Deps: 4.1.4
  - Implemented: find_path() with A* and route preferences
- [x] **4.1.7** Mobility cost calculations
  - Deps: 4.1.4
  - Implemented: TerrainCell::get_mobility_cost() with terrain/vehicle modifiers
- [x] **4.1.8** Urban terrain analysis
  - Deps: 4.1.4
  - Implemented: get_urban_centers(), urban_density effects on combat/LOS
- [x] **4.1.9** Terrain query API
  - Deps: 4.1.5, 4.1.6, 4.1.7
  - Implemented: get_cell(), get_cells_in_radius(), analyze_area(), etc.

### 4.2 Movement Resolver
- [x] **4.2.1** MovementResolver class header
- [x] **4.2.2** Movement phase execution
  - Deps: 4.1.6, 4.1.7
  - Implemented: resolve_movement(), follow_path() with segment-based terrain traversal
- [x] **4.2.3** Route calculation and following
  - Deps: 4.1.6
  - Implemented: Path segment following with terrain-based speed calculations
- [x] **4.2.4** Traffic/congestion handling
  - Deps: 4.2.2
  - Implemented: Priority ordering, collision detection, road capacity, cell occupation
- [x] **4.2.5** Fuel consumption during movement
  - Deps: 4.2.2, 4.5.2
  - Implemented: Per-segment fuel calculation with terrain/speed modifiers
- [x] **4.2.6** Movement event generation
  - Deps: 4.2.2
  - Implemented: Detailed narrative generation with direction, outcome, fuel warnings

### 4.3 Sensor Model
- [x] **4.3.1** SensorModel class header
- [x] **4.3.2** Detection probability calculation
  - Deps: 4.1.5, 4.3.1
  - Implemented: calculate_base_detection_prob(), terrain/posture/size modifiers
- [x] **4.3.3** Sensor range modeling by type
  - Deps: 4.3.1
  - Implemented: Per-sensor type range and arc handling
- [x] **4.3.4** Environmental effects (weather, time of day)
  - Deps: 4.3.2
  - Implemented: Weather/time visibility modifiers, thermal night bonus
- [x] **4.3.5** Contact generation and tracking
  - Deps: 4.3.2
  - Implemented: generate_intel_report(), Contact struct, PerceptionState
- [x] **4.3.6** Contact confidence degradation over time
  - Deps: 4.3.5
  - Implemented: age_contacts() with configurable max age
- [x] **4.3.7** Electronic warfare effects
  - Deps: 4.3.2
  - Implemented: EWEnvironment, Jammer, JammingEffect, get_jamming_modifier()

### 4.4 Combat Resolver
- [x] **4.4.1** CombatResolver class header
- [x] **4.4.2** Engagement detection (units in range)
  - Deps: 4.1.5, 4.3.2
  - Implemented: find_combat_engagements() in Simulation
- [x] **4.4.3** Combat power calculation
  - Deps: 4.4.1
  - Implemented: calculate_odds_ratio(), lookup_casualty_rates()
- [x] **4.4.4** Terrain modifier application
  - Deps: 4.1.4, 4.4.3
  - Implemented: calculate_modifiers() with terrain defense/attack modifiers
- [x] **4.4.5** Casualty calculation
  - Deps: 4.4.3, 4.4.4
  - Implemented: distribute_casualties(), doctrine-based casualty tables
- [x] **4.4.6** Unit strength reduction
  - Deps: 4.4.5
  - Implemented: Unit::apply_casualties()
- [x] **4.4.7** Morale effects from combat
  - Deps: 4.4.5
  - Implemented: apply_morale_effect() with victory/defeat bonuses
- [x] **4.4.8** Ammunition consumption
  - Deps: 4.4.2, 4.5.2
  - Implemented: consume_ammo() in resolve_engagement()
- [x] **4.4.9** Combat event generation
  - Deps: 4.4.5
  - Implemented: generate_combat_narrative(), CombatEvent logging

### 4.5 Logistics Model
- [x] **4.5.1** SupplyModel class header
- [x] **4.5.2** Supply state tracking (fuel, ammo, supplies)
  - Deps: 4.5.1
  - Implemented: LogisticsState in Unit, SupplyPoint depots
- [x] **4.5.3** Consumption rates by activity
  - Deps: 4.5.2
  - Implemented: apply_turn_consumption() with posture-based rates
- [x] **4.5.4** Resupply mechanics
  - Deps: 4.5.2
  - Implemented: process_resupply_requests(), priority-based allocation
- [x] **4.5.5** Supply line/LOC calculation
  - Deps: 4.1.6, 4.5.2
  - Implemented: Full pathfinding-based LOC calculation via terrain engine
  - Features: Road route preference, terrain-aware path distance, enemy interdiction checking
- [x] **4.5.6** Supply shortage effects
  - Deps: 4.5.2
  - Implemented: get_effectiveness_modifier() reduces combat power
- [x] **4.5.7** Maintenance and repair
  - Deps: 4.5.2
  - Implemented: maintenance_state degradation over time

### 4.6 Simulation Core
- [x] **4.6.1** Simulation class header
- [x] **4.6.2** Scenario loading from YAML
  - Implemented: load_scenario_from_file() with yaml-cpp
- [x] **4.6.3** State management structure
  - Implemented: GameState class with ORBAT, orders, perception, events
- [x] **4.6.4** Order validation implementation
  - Deps: 4.2.1, 4.4.1
  - Implemented: validate_order(), get_order_validation_error()
- [x] **4.6.5** Turn execution orchestration
  - Deps: 4.2.2, 4.3.2, 4.4.2, 4.5.2
  - Implemented: execute_turn() with full phase resolution
- [x] **4.6.6** Phase transitions (Planning → Execution → Reporting)
  - Deps: 4.6.5
  - Implemented: TurnPhase enum, start_*_phase() methods
- [x] **4.6.7** Event aggregation and logging
  - Deps: 4.6.5
  - Implemented: log_event(), GameEvent variant, emit_event() callback
- [x] **4.6.8** Victory condition checking
  - Deps: 4.6.5
  - Implemented: check_victory(), get_victory_status() with multiple condition types
- [x] **4.6.9** Game state serialization/deserialization
  - Deps: 4.6.3
  - Implemented: to_json()/from_json() with nlohmann/json

### 4.7 Perception Generator
- [x] **4.7.1** Faction-specific view generation
  - Deps: 4.3.5
  - Implemented: `get_filtered_contacts()` in PerceptionState with fog of war filtering
- [x] **4.7.2** Fog of war application
  - Deps: 4.7.1
  - Implemented: `apply_fog_of_war()` hides Unknown contacts, applies position jitter by confidence
  - Suspected: 2km jitter + strips type/echelon, Probable: 0.5km jitter + strips echelon, Confirmed: 0.1km minimal jitter
- [x] **4.7.3** Contact merging and deduplication
  - Deps: 4.3.5, 4.7.1
  - Implemented: `merge_contacts()` with spatial clustering (0.5km radius)
  - Takes best confidence, most recent observation, identified type/echelon
- [x] **4.7.4** Historical contact decay
  - Deps: 4.3.6
  - Implemented: `age_and_prune_contacts()` integrated into `update_perceptions()`
  - Confidence degrades: 50% age: Confirmed→Probable, 75% age: →Suspected, 100% age: removed
  - Lost contacts tracked in `lost_contacts_` vector

---

## Phase 5: Data & Scenarios

### 5.1 Scenario Data
- [x] **5.1.1** Fulda Gap 1985 scenario YAML
- [x] **5.1.2** Tutorial scenario
  - Implemented: `data/scenarios/tutorial_basics.yaml` - "Basic Training" tutorial
  - Features: Comprehensive briefings with gameplay instructions, lesson progression
  - ORBAT: `tutorial_blue_orbat.yaml` (Task Force: Tank Plt, Mech Plt, Recon Sec)
  - ORBAT: `tutorial_red_orbat.yaml` (OPFOR: Mech Plt, Tank Sec, Recon Tm)
  - Terrain: `data/terrain/tutorial_area.gpkg` (47K cells, 20x30 km area)
  - Features: Hill 229 objective, Village Bravo, Crossroads Alpha
  - Teaches: WEGO turns, order types, combined arms, terrain effects
- [ ] **5.1.3** Additional historical scenarios
- [ ] **5.1.4** ORBAT data for scenarios (unit definitions)
  - Deps: 5.1.1

### 5.2 Terrain Data
- [x] **5.2.1** Terrain data format specification
  - Implemented: GeoPackage with terrain_cells layer, metadata table
  - Fields: center_lat/lon, elevation_m, primary_type, cover, concealment, urban_density, population, is_road/bridge/impassable
- [x] **5.2.2** Fulda Gap terrain GeoPackage
  - Deps: 5.2.1
  - Implemented: Synthetic terrain generator (`tools/generate_fulda_terrain.py`)
  - Output: `data/terrain/fulda_gap.gpkg` (320 MB, 1.18M cells at 100m resolution)
  - Distribution: 49.5% Forest, 48.7% Open, 0.9% Urban, 0.5% Road, 0.2% Water
- [x] **5.2.3** Terrain loading in C++ engine
  - Deps: 4.1.3, 5.2.2
  - Implemented: GDAL-based GeoPackage loading in terrain_engine.cpp

### 5.3 Doctrine Data
- [ ] **5.3.1** Soviet/Russian doctrine reference files
- [ ] **5.3.2** NATO doctrine reference files
- [ ] **5.3.3** Doctrine integration with Grisha queries

---

## Phase 6: Testing

### 6.1 Python Tests
- [x] **6.1.1** API endpoint tests (test_api.py)
- [x] **6.1.2** Grisha integration tests
  - Deps: 2.1.1, 2.2.1, 2.3.1
  - Implemented: `tests/test_grisha.py` (45 tests)
  - Coverage: GrishaCommander (order generation, doctrine queries, turn evaluation), GrishaAdvisor (enemy analysis, defense recommendations, situation assessment), OrderParser (preprocessing, parsing, validation, clarification)
  - Features: Mock-based testing for external services (Grisha API, Ollama), system prompt validation, error handling tests
- [x] **6.1.3** WebSocket tests
  - Deps: 1.1.2
  - Implemented: `tests/test_api.py::TestWebSocketEndpoint` (7 tests)
  - Coverage: Connection establishment, ping/pong heartbeat, faction subscription, multiple pings, unknown message handling, initial state validation
- [x] **6.1.4** Order parsing tests
  - Deps: 2.3.1
  - Implemented: `tests/test_order_parser.py` (64 tests)
  - Coverage: Preprocessing (order types, ROE, routes, coordinates, timing), context building, validation (units, targets), JSON extraction, LLM parsing, interactive clarification, error handling, edge cases
  - Test classes: TestPreprocessingOrderTypes, TestPreprocessingROE, TestPreprocessingRoute, TestPreprocessingCoordinates, TestPreprocessingTiming, TestContextBuilding, TestValidation, TestJSONExtraction, TestParseOrder, TestInteractiveClarify, TestErrorHandling, TestOrderPatterns, TestSystemPrompt, TestEdgeCases, TestMultiUnitOrders, TestOllamaIntegration

### 6.2 C++ Tests
- [x] **6.2.1** Unit class tests
  - Deps: 1.3.2
  - Implemented: `tests/server/test_unit.cpp` - identification, hierarchy, logistics, morale, combat effectiveness, sensors, orders, serialization
- [x] **6.2.2** ORBAT Manager tests
  - Deps: 1.3.3
  - Implemented: `tests/server/test_orbat_manager.cpp` - unit management, faction/type queries, spatial queries, hierarchy, command chain, serialization
- [x] **6.2.3** Terrain engine tests
  - Deps: 4.1.9
  - Implemented: `tests/server/test_terrain.cpp` - loading, queries, mobility, LOS, pathfinding, area analysis, urban terrain
- [x] **6.2.4** Movement resolver tests
  - Deps: 4.2.6
  - Implemented: `tests/server/test_movement.cpp` - basic movement, route preferences, speed modifiers, fuel consumption, weather, traffic
- [x] **6.2.5** Sensor model tests
  - Deps: 4.3.7
  - Implemented: `tests/server/test_sensors.cpp` - detection, range/arc, target attributes, weather/night, EW jamming, contact aging
- [x] **6.2.6** Combat resolver tests
  - Deps: 4.4.9
  - Implemented: `tests/server/test_combat.cpp` - engagement, odds ratio, terrain modifiers, casualties, morale, ammo consumption
- [x] **6.2.7** Logistics model tests
  - Deps: 4.5.7
  - Implemented: `tests/server/test_logistics.cpp` - supply points, LOC calculation, resupply, interdiction, consumption
- [x] **6.2.8** Full simulation integration tests
  - Deps: 4.6.9
  - Implemented: `tests/server/test_simulation.cpp` - scenario loading, orders, turn execution, perception, victory conditions

### 6.3 Integration Tests
- [x] **6.3.1** Python-C++ binding tests
  - Deps: 1.3.4, 4.6.9
  - Implemented: `tests/integration/test_bindings.py` (53 tests)
  - Coverage: Module import, enums, Coordinates, BoundingBox, Unit, TerrainEngine, Simulation, TurnResult
  - Tests: Type safety, data integrity, memory management, error handling
- [x] **6.3.2** End-to-end game flow tests
  - Deps: 6.3.1
  - Implemented: `tests/integration/test_game_flow.py` (8 tests)
  - Coverage: Scenario loading, turn execution, save/load, victory conditions, terrain integration
- [x] **6.3.3** Multi-turn scenario tests
  - Deps: 6.3.2
  - Implemented: `tests/integration/test_multi_turn.py` (10 tests)
  - Coverage: State progression, result accumulation, persistence, stress testing

---

## Phase 7: Tools

### 7.1 Scenario Editor
- [x] **7.1.1** YAML schema validation
  - Implemented: Pydantic models in `tools/scenario_editor/models.py`
  - Features: Full scenario/ORBAT validation with semantic checks, coordinate bounds, hierarchy validation
- [x] **7.1.2** Unit placement interface
  - Implemented: `tools/scenario_editor/editor.py` ORBATEditor class
  - Features: add_unit(), move_unit(), set_parent(), hierarchy tree display
  - CLI: `scenario-editor add-unit`, `move-unit`, `remove-unit` commands
- [x] **7.1.3** Objective definition
  - Implemented: `tools/scenario_editor/editor.py` ScenarioEditor class
  - Features: add_objective(), remove_objective(), coordinate validation
  - CLI: `scenario-editor add-objective`, `remove-objective` commands
- [x] **7.1.4** Victory condition configuration
  - Implemented: Full victory condition support (territorial, attrition, time, objective)
  - Features: Validation for required fields per condition type
  - CLI: `scenario-editor add-victory-condition` command
- [x] **7.1.5** Scenario export
  - Implemented: JSON export, YAML save/load
  - CLI: `scenario-editor export` command
- [x] **7.1.6** CLI interface
  - Implemented: `tools/scenario_editor/main.py`
  - Commands: new, new-orbat, validate, add-*, remove-*, move-unit, info, export, list-templates, list-regions, set-briefing, interactive
- [x] **7.1.7** Interactive mode
  - Implemented: `tools/scenario_editor/interactive.py`
  - Features: Menu-driven scenario/ORBAT editing with prompts
- [x] **7.1.8** Scenario templates
  - Implemented: `tools/scenario_editor/templates.py`
  - Templates: blank, cold_war_offensive, meeting_engagement, defensive
  - ORBAT templates: blank_red, blank_blue, sample_red, sample_blue
  - Predefined regions: fulda_gap, suwalki_gap, north_german_plain, korean_dmz, baltics

### 7.2 Terrain Processor
- [x] **7.2.1** GIS data import (GeoTIFF, Shapefiles)
- [x] **7.2.2** Terrain classification (ESA WorldCover → TerrainType)
- [x] **7.2.3** Elevation processing (SRTM → elevation + slope)
- [x] **7.2.4** Road/river network extraction (OSM → roads/bridges)
- [x] **7.2.5** GeoPackage export for engine
- [x] **7.2.6** CLI interface (process/download/tile commands)
- [x] **7.2.7** Urban density processor (buildings → urban_density)
- [x] **7.2.8** Predefined regions (fulda_gap, suwalki_gap, baltic_states)

---

## Phase 8: Persistence & Production

### 8.1 Database Integration
- [x] **8.1.1** PostgreSQL/PostGIS setup
  - Implemented: `server/database/config.py` - DatabaseConfig, connection URL generation, schema/enum SQL
  - Implemented: `server/database/session.py` - Session management, async support, init_database()
  - Features: Environment variable configuration, connection pooling, PostGIS extension setup
- [x] **8.1.2** SQLAlchemy models for game state
  - Implemented: `server/database/models.py` - Full ORM model suite
  - Models: DBGame, DBUnit, DBOrder, DBContact, DBControlZone, DBTurnResult
  - Events: DBCombatEvent, DBMovementEvent, DBDetectionEvent, DBSupplyEvent
  - Features: PostGIS geometry columns, JSONB for nested data, pydantic conversion methods
- [x] **8.1.3** Game save/load functionality
  - Deps: 8.1.1, 8.1.2
  - Implemented: `server/database/game_store.py` - GameStore class
  - Features: Create/delete games, save/load units/orders/contacts/zones, full state save/load
- [x] **8.1.4** Turn history storage
  - Deps: 8.1.2
  - Implemented: `server/database/turn_history.py` - TurnHistoryStore class
  - Features: Save/retrieve turn results, event queries, state snapshots, game statistics
- [x] **8.1.5** Replay functionality
  - Deps: 8.1.4
  - Implemented: `server/database/replay.py` - ReplayController, ReplayState
  - Features: Step forward/backward, jump to turn, state reconstruction, export replay
  - API: `server/api/routes/persistence.py` - REST endpoints for persistence operations
  - CLI: `tools/db_admin.py` - Database administration tool

### 8.2 Production Hardening
- [ ] **8.2.1** Configuration management (env vars, secrets)
- [x] **8.2.2** Logging infrastructure
  - Implemented: `server/logging_config.py` - Centralized logging configuration
  - Features: JSON and colored text formatters, request ID tracking
  - Handlers: Console output + rotating file handlers (10MB, 5 backups)
  - Environment configuration: KARKAS_LOG_LEVEL, KARKAS_LOG_FORMAT, KARKAS_LOG_DIR
  - Helper functions: log_grisha_api_call, log_ollama_call, log_turn_execution, log_order_submission
  - Middleware: RequestLoggingMiddleware for FastAPI request/response logging
  - Decorator: log_execution_time for function timing
  - Replaced all print() statements with structured logging
  - Tests: `tests/test_logging.py`
- [ ] **8.2.3** Error handling improvements
- [ ] **8.2.4** Rate limiting
- [ ] **8.2.5** Authentication (optional)
- [x] **8.2.6** Docker containerization
  - Implemented: `Dockerfile` - Multi-stage build for C++ core + Python API
  - Implemented: `docker-compose.yml` - Server + PostgreSQL/PostGIS orchestration
  - Implemented: `docker-compose.dev.yml` - Development overrides with hot reload
  - Implemented: `docker-entrypoint.sh` - Database initialization and startup
  - Implemented: `docker/db-init/01-init.sql` - PostGIS setup and enum types
  - Implemented: `Makefile` - Convenient Docker commands
  - Implemented: `.dockerignore` - Build optimization
  - Implemented: `.env.example` - Environment variable documentation
  - Features: Health checks, non-root user, volume mounts, connection pooling
- [ ] **8.2.7** CI/CD pipeline

---

## Dependency Graph (Critical Path)

```
Phase 1 (Foundation) ─────────────────────────────────────┐
    │                                                      │
    ├── 1.3 C++ Types ──► 4.1 Terrain ──► 4.2 Movement ───┤
    │                         │              │             │
    │                         │              ▼             │
    │                         └────────► 4.3 Sensors ──────┤
    │                                        │             │
    │                                        ▼             │
    │                                   4.4 Combat ────────┤
    │                                        │             │
    │                                        ▼             │
    │                                   4.5 Logistics ─────┤
    │                                        │             │
    │                                        ▼             │
    │                                   4.6 Simulation ────┤
    │                                        │             │
    ▼                                        ▼             │
Phase 2 (Grisha) ◄────────────────────── Phase 4 Core ────┤
    │                                        │             │
    ▼                                        ▼             │
Phase 3 (Client) ◄────────────────────── Phase 5 Data ────┤
    │                                        │             │
    ▼                                        ▼             │
Phase 6 (Testing) ◄──────────────────────────┘             │
    │                                                      │
    ▼                                                      │
Phase 7 (Tools) ◄──────────────────────────────────────────┤
    │                                                      │
    ▼                                                      │
Phase 8 (Production) ◄─────────────────────────────────────┘
```

---

## Priority Recommendations

### Core Simulation Engine ✅ COMPLETE
All core simulation components are fully implemented and tested:
- ~~Terrain Engine~~ ✅
- ~~Movement Resolver~~ ✅
- ~~Sensor Model~~ ✅
- ~~Combat Resolver~~ ✅
- ~~Logistics Model~~ ✅
- ~~Simulation Core~~ ✅
- ~~Perception Generator~~ ✅

### Tools & Testing ✅ COMPLETE
- ~~Terrain Processor~~ ✅
- ~~Scenario Editor~~ ✅
- ~~C++ Unit Tests~~ ✅
- ~~Integration Tests~~ ✅
- ~~Client Enhancements~~ ✅

### Database Integration ✅ COMPLETE
- ~~PostgreSQL/PostGIS setup~~ ✅
- ~~SQLAlchemy models~~ ✅
- ~~Game save/load~~ ✅
- ~~Turn history storage~~ ✅
- ~~Replay functionality~~ ✅

### Docker Containerization ✅ COMPLETE
- ~~Dockerfile~~ ✅
- ~~docker-compose.yml~~ ✅
- ~~Development overrides~~ ✅
- ~~Database init scripts~~ ✅
- ~~Makefile commands~~ ✅

### Tutorial Scenario ✅ COMPLETE
- ~~Tutorial scenario~~ ✅
- ~~Tutorial ORBAT files~~ ✅
- ~~Tutorial terrain data~~ ✅

### Logging Infrastructure ✅ COMPLETE
- ~~Centralized logging config~~ ✅
- ~~JSON and colored formatters~~ ✅
- ~~Rotating file handlers~~ ✅
- ~~Request ID tracking~~ ✅
- ~~Helper functions for metrics~~ ✅
- ~~FastAPI middleware~~ ✅

### Remaining Work - Priority Order

**High Priority (Production Hardening)**
1. **8.2.1** - Configuration management (env vars, secrets)
2. **8.2.3** - Error handling improvements

**Medium Priority (Production Hardening)**
3. **8.2.4** - Rate limiting
4. **8.2.5** - Authentication (optional)
5. **8.2.7** - CI/CD pipeline

**Content (Can Be Done Anytime)**
6. **5.1.3-5.1.4** - Additional scenarios + ORBAT data
7. **5.3.1-5.3.3** - Doctrine reference files + Grisha integration

---

## File Locations Reference

### Completed Components
| Component | Location |
|-----------|----------|
| API Server | `server/api/main.py` |
| API Routes | `server/api/routes/*.py` |
| API Models | `server/api/models/*.py` |
| Grisha Commander | `server/grisha/commander.py` |
| Grisha Advisor | `server/grisha/advisor.py` |
| Order Parser | `server/grisha/order_parser.py` |
| Client CLI | `client/cli.py` |
| Client WebSocket | `client/cli.py` (KarkasClient.websocket_listener) |
| Turn Result Formatter | `client/cli.py` (TurnResultFormatter class) |
| ASCII Map Renderer | `client/cli.py` (ASCIIMapRenderer class) |
| C++ Types | `server/core/types.hpp` |
| C++ Unit | `server/core/unit.hpp`, `server/core/unit.cpp` |
| C++ ORBAT | `server/core/orbat_manager.hpp`, `server/core/orbat_manager.cpp` |
| Python API Tests | `tests/test_api.py` |
| Grisha Integration Tests | `tests/test_grisha.py` |
| Order Parser Tests | `tests/test_order_parser.py` |
| Scenario | `data/scenarios/fulda_gap_1985.yaml` |

### Completed Components (C++ Terrain)
| Component | Location |
|-----------|----------|
| Terrain Engine | `server/core/terrain/terrain_engine.cpp` |
| LOS Calculator | `server/core/terrain/terrain_engine.cpp` (inline) |
| Mobility | `server/core/terrain/terrain_engine.cpp` (inline) |

### Completed Components (C++ Movement)
| Component | Location |
|-----------|----------|
| Movement Resolver | `server/core/movement/movement_resolver.cpp` |

### Now Complete Components
| Component | Location | Notes |
|-----------|----------|-------|
| Sensor Model | `server/core/sensors/sensor_model.cpp` | Full detection, EW effects |
| Detection | `server/core/sensors/detection.cpp` | EW integration docs |
| Combat Resolver | `server/core/combat/combat_resolver.cpp` | Full combat resolution |
| Supply Model | `server/core/logistics/supply_model.cpp` | Resupply, consumption, pathfinding-based LOC, interdiction |
| Simulation | `server/core/simulation.cpp` | Full turn execution with integrated SupplyModel |
| JSON Serialization | `server/core/json_serialization.hpp` | nlohmann/json based, includes SupplyEvent |

### Partially Implemented / Integrated Components
| Component | Location | Notes |
|-----------|----------|-------|
| Pathfinder | `server/core/terrain/terrain_engine.cpp` | A* pathfinding integrated into terrain engine |
| Game State | `server/core/simulation.cpp` | GameState class in simulation.hpp/cpp |
| Turn Executor | `server/core/simulation.cpp` | execute_turn() with full phase resolution |
| Perception Gen | `server/core/sensors/sensor_model.cpp` | Full: generate_intel_report(), apply_fog_of_war(), merge_contacts(), get_filtered_contacts(), age_and_prune_contacts() |

### Completed Tool Components
| Component | Location |
|-----------|----------|
| Terrain Processor CLI | `tools/terrain_processor/main.py` |
| Terrain Models | `tools/terrain_processor/models/` |
| Data Downloaders | `tools/terrain_processor/downloaders/` |
| Data Processors | `tools/terrain_processor/processors/` |
| GeoPackage Writer | `tools/terrain_processor/gpkg_writer.py` |
| Terrain Tiler | `tools/terrain_processor/tiler.py` |

### Completed Data Files
| File | Description |
|------|-------------|
| `data/terrain/fulda_gap.gpkg` | Fulda Gap terrain (320 MB, 1.18M cells at 100m resolution) |
| `data/scenarios/fulda_gap_1985.yaml` | Fulda Gap 1985 scenario definition |
| `data/terrain/tutorial_area.gpkg` | Tutorial terrain (47K cells, 20x30 km) |
| `data/scenarios/tutorial_basics.yaml` | Tutorial scenario with learning instructions |
| `data/scenarios/tutorial_blue_orbat.yaml` | Blue force ORBAT (Tank Plt, Mech Plt, Recon Sec) |
| `data/scenarios/tutorial_red_orbat.yaml` | Red force ORBAT (Mech Plt, Tank Sec, Recon Tm) |
| `tools/generate_tutorial_terrain.py` | Tutorial terrain generator |

### Completed Tool Components
| Component | Location |
|-----------|----------|
| Terrain Processor CLI | `tools/terrain_processor/main.py` |
| Terrain Models | `tools/terrain_processor/models/` |
| Data Downloaders | `tools/terrain_processor/downloaders/` |
| Data Processors | `tools/terrain_processor/processors/` |
| GeoPackage Writer | `tools/terrain_processor/gpkg_writer.py` |
| Terrain Tiler | `tools/terrain_processor/tiler.py` |
| Synthetic Generator | `tools/generate_fulda_terrain.py` |

### Completed Components (C++ Tests)
| Component | Location |
|-----------|----------|
| Unit Tests | `tests/server/test_unit.cpp` |
| ORBAT Manager Tests | `tests/server/test_orbat_manager.cpp` |
| Terrain Engine Tests | `tests/server/test_terrain.cpp` |
| Movement Resolver Tests | `tests/server/test_movement.cpp` |
| Sensor Model Tests | `tests/server/test_sensors.cpp` |
| Combat Resolver Tests | `tests/server/test_combat.cpp` |
| Logistics Model Tests | `tests/server/test_logistics.cpp` |
| Simulation Tests | `tests/server/test_simulation.cpp` |
| Simple Test Runner | `tests/server/simple_test.cpp` |

### Completed Components (Integration Tests)
| Component | Location |
|-----------|----------|
| Test Fixtures | `tests/integration/conftest.py` |
| Python-C++ Binding Tests | `tests/integration/test_bindings.py` |
| Game Flow Tests | `tests/integration/test_game_flow.py` |
| Multi-Turn Tests | `tests/integration/test_multi_turn.py` |

### Completed Tool Components (Scenario Editor)
| Component | Location |
|-----------|----------|
| Scenario Editor CLI | `tools/scenario_editor/main.py` |
| Pydantic Models | `tools/scenario_editor/models.py` |
| Scenario Templates | `tools/scenario_editor/templates.py` |
| Validators | `tools/scenario_editor/validators.py` |
| Editor Core | `tools/scenario_editor/editor.py` |
| Interactive Mode | `tools/scenario_editor/interactive.py` |
| Tests | `tests/tools/test_scenario_editor.py` |

### Completed Components (Database Integration)
| Component | Location |
|-----------|----------|
| Database Config | `server/database/config.py` |
| Session Management | `server/database/session.py` |
| ORM Models | `server/database/models.py` |
| Game Store | `server/database/game_store.py` |
| Turn History Store | `server/database/turn_history.py` |
| Replay Controller | `server/database/replay.py` |
| Persistence API Routes | `server/api/routes/persistence.py` |
| Database Admin CLI | `tools/db_admin.py` |
| Database Tests | `tests/test_database.py` |

### Completed Components (Docker)
| Component | Location |
|-----------|----------|
| Dockerfile | `Dockerfile` |
| Docker Compose | `docker-compose.yml` |
| Dev Compose | `docker-compose.dev.yml` |
| Entrypoint | `docker-entrypoint.sh` |
| DB Init Script | `docker/db-init/01-init.sql` |
| Makefile | `Makefile` |
| Docker Ignore | `.dockerignore` |
| Env Example | `.env.example` |

### Completed Components (Logging)
| Component | Location |
|-----------|----------|
| Logging Config | `server/logging_config.py` |
| Server Package Init | `server/__init__.py` |
| Logging Tests | `tests/test_logging.py` |

### Directories Needing Content
| Directory | Purpose | Related Task |
|-----------|---------|--------------|
| `data/doctrine/` | Doctrine reference documents | 5.3.1-5.3.2 |
| `data/scenarios/` | Additional scenario files | 5.1.2-5.1.4 |
| `tests/client/` | Client tests | (optional) |

---

## Statistics

- **Total Tasks:** 159
- **Completed:** 149 (94%)
- **Pending:** 10 (6%)
- **Critical Path Length:** 8 phases
- **Last Updated:** 2026-03-16

### Pending Tasks Summary

**Phase 5 - Data & Scenarios (5 tasks)**
- 5.1.3 Additional historical scenarios
- 5.1.4 ORBAT data for scenarios
- 5.3.1 Soviet/Russian doctrine reference files
- 5.3.2 NATO doctrine reference files
- 5.3.3 Doctrine integration with Grisha queries

**Phase 8 - Production Hardening (5 tasks)**
- 8.2.1 Configuration management (env vars, secrets)
- 8.2.3 Error handling improvements
- 8.2.4 Rate limiting
- 8.2.5 Authentication (optional)
- 8.2.7 CI/CD pipeline

### Recent Completions (This Session)
- Logging Infrastructure (8.2.2)
  - **server/logging_config.py**: Centralized logging configuration
    - JSON formatter for structured production logging
    - Colored text formatter for development console
    - Rotating file handlers (10MB, 5 backups, JSON format)
    - Request ID context tracking via contextvars
    - Environment variable configuration (KARKAS_LOG_LEVEL, KARKAS_LOG_FORMAT, KARKAS_LOG_DIR)
  - **Helper functions**:
    - log_grisha_api_call: Track Grisha RAG API calls with timing
    - log_ollama_call: Track LLM inference calls with token counts
    - log_turn_execution: Track turn execution with event metrics
    - log_order_submission: Track order submission by faction
    - log_database_operation: Track database operation timing
  - **Middleware**: RequestLoggingMiddleware for FastAPI
    - Automatic request ID generation and tracking
    - Request start/end logging with duration
    - HTTP status code logging with appropriate log levels
  - **Decorator**: log_execution_time for function timing
  - **Code updates**:
    - Replaced 26 print() statements with structured logging
    - Updated server/api/main.py with logging
    - Updated server/grisha/commander.py and advisor.py
    - Updated server/database/session.py
  - **Tests**: `tests/test_logging.py` (18 tests)
  - **server/__init__.py**: Package initialization with logging exports

- Tutorial Scenario (5.1.2)
  - **tutorial_basics.yaml**: Complete tutorial scenario with guided learning
    - Comprehensive briefings explaining WEGO turns, order types, combined arms
    - Clear terrain layout: Hill 229, Village Bravo, Crossroads Alpha
    - 15-turn exercise with appropriate victory conditions
  - **tutorial_blue_orbat.yaml**: Blue Task Force
    - Task Force HQ
    - Tank Platoon (4 MBTs)
    - Mechanized Infantry Platoon (3 IFVs + dismounts)
    - Recon Section (2 scout vehicles)
  - **tutorial_red_orbat.yaml**: OPFOR Training Detachment
    - OPFOR HQ
    - Mechanized Platoon (defending Hill 229)
    - Tank Section (2 tanks, reserve)
    - Recon Team (forward observation)
  - **tools/generate_tutorial_terrain.py**: Terrain generator
    - 20x30 km synthetic terrain area
    - 47K cells at 100m resolution
    - Hill 229 with tactical elevation (~380m)
    - Road network with bridges
    - Village, forest patches, stream
  - **data/terrain/tutorial_area.gpkg**: Generated terrain data

- Docker Containerization (8.2.6)
  - **Dockerfile**: Multi-stage build (builder + runtime)
    - Builder: C++ compilation with CMake, GDAL, pybind11
    - Runtime: Python 3.11-slim with minimal dependencies
    - Non-root user, health checks, proper signal handling
  - **docker-compose.yml**: Service orchestration
    - KARKAS server with environment configuration
    - PostgreSQL 16 with PostGIS 3.4
    - Volume mounts for terrain/scenario data
    - Health checks and dependency ordering
  - **docker-compose.dev.yml**: Development overrides
    - Source code mounting for hot reload
    - SQL query logging enabled
  - **docker-entrypoint.sh**: Startup script
    - Database connection waiting with retry logic
    - Schema initialization
    - Configuration display
  - **docker/db-init/01-init.sql**: Database bootstrap
    - PostGIS extension setup
    - Custom enum types
    - Schema creation
  - **Makefile**: Convenience commands
    - build, run, stop, logs, clean, shell, db-shell
    - dev, test, lint, format
    - db-init, db-reset, db-backup
  - **.env.example**: Environment documentation
  - **.dockerignore**: Build optimization

- Database Integration (8.1.1-8.1.5)
  - **8.1.1 PostgreSQL/PostGIS setup**: `server/database/config.py`, `session.py`
    - DatabaseConfig class with environment variable support
    - Connection pooling configuration
    - Schema and PostGIS extension initialization SQL
    - Synchronous and asynchronous session factories
  - **8.1.2 SQLAlchemy models**: `server/database/models.py`
    - DBGame: Game session with scenario config, state, region (PostGIS)
    - DBUnit: Full unit with position (PostGIS Point), combat/logistics/morale state
    - DBOrder: Orders with objectives and constraints (JSONB)
    - DBContact: Enemy contacts with confidence and position (PostGIS)
    - DBControlZone: Territory control with polygon (PostGIS)
    - DBTurnResult: Turn results with event relationships
    - Event models: DBCombatEvent, DBMovementEvent, DBDetectionEvent, DBSupplyEvent
  - **8.1.3 Game save/load**: `server/database/game_store.py`
    - GameStore class with CRUD operations for games, units, orders, contacts, zones
    - Full state save/load with perception state reconstruction
    - Upsert support for incremental updates
  - **8.1.4 Turn history storage**: `server/database/turn_history.py`
    - TurnHistoryStore for saving/retrieving turn results and events
    - Event queries with filtering (by turn, unit, etc.)
    - State snapshots for replay
    - Game statistics aggregation
  - **8.1.5 Replay functionality**: `server/database/replay.py`
    - ReplayController for navigating game history
    - Step forward/backward, jump to turn
    - State reconstruction from snapshots
    - Victory analysis and export
  - **API Routes**: `server/api/routes/persistence.py`
    - REST endpoints for all persistence operations
    - Replay control endpoints
  - **CLI Tool**: `tools/db_admin.py`
    - Initialize/reset database
    - List/delete games
    - View statistics and history
    - Export game data
  - **Tests**: `tests/test_database.py`
    - Model tests for all ORM classes
    - GameStore, TurnHistoryStore, ReplayController tests

- Order Parsing Tests (6.1.4)
  - Created comprehensive test suite: `tests/test_order_parser.py` (64 tests)
  - Test coverage includes:
    - Preprocessing: Order type detection (move, attack, defend, recon, withdraw, support)
    - ROE detection (weapons_free, weapons_hold, weapons_tight)
    - Route preference detection (fastest, covered, avoid_enemy)
    - Coordinate and timing extraction
    - Context building for LLM
    - Validation of target units and enemy targets
    - JSON extraction from LLM responses
    - Full order parsing flow
    - Interactive clarification
    - Error handling (connection errors, timeouts, malformed responses)
    - Edge cases (unicode, special chars, long input)
    - Multi-unit orders
    - Ollama integration

- Grisha Integration Tests (6.1.2)
  - Created comprehensive Python test suite: `tests/test_grisha.py` (45 tests)
  - GrishaCommander tests: order generation, doctrine queries, context history, turn evaluation
  - GrishaAdvisor tests: enemy analysis, defense recommendations, situation assessment, order evaluation
  - OrderParser tests: preprocessing (order type, ROE, routes, coordinates), LLM parsing, validation, clarification
  - Integration tests: commander-to-parser flow, advisor workflow
  - Error handling tests: LLM failures, empty inputs, malformed responses
  - System prompt validation tests
  - All tests use mocks for external services (Grisha API, Ollama)

- Perception Generator (4.7.1-4.7.4)
  - Faction-specific view generation via `get_filtered_contacts()`
  - Fog of war: hides Unknown contacts, applies position jitter by confidence level
  - Spatial contact merging with 0.5km clustering radius
  - Historical contact decay integrated into `update_perceptions()`
  - 8 new unit tests for perception features (all passing)
  - Total: 35 sensor model tests passing

- Client Enhancements (3.2.1-3.2.4)
  - WebSocket real-time message handling with async listener + threaded input
  - Message types: phase_change, orders_submitted, turn_result, new_turn
  - Order history display via `orders` and `history` commands
  - TurnResultFormatter for colored movement/combat/detection output
  - ASCIIMapRenderer for `map` command with auto-scaling bounds
  - Enhanced unit/contact display with color-coded strength/confidence
  - New CLI commands: map, orders, history

- Scenario Editor Tool (7.1.1-7.1.8)
  - Created comprehensive CLI tool for scenario/ORBAT management
  - Pydantic models for full YAML schema validation
  - Scenario templates: blank, cold_war_offensive, meeting_engagement, defensive
  - ORBAT templates with sample Red/Blue forces
  - Predefined regions: fulda_gap, suwalki_gap, north_german_plain, korean_dmz, baltics
  - Interactive mode with menu-driven editing
  - 36 unit tests passing
  - CLI commands: new, new-orbat, validate, add-objective, add-victory-condition, add-unit, move-unit, info, export, set-briefing, interactive

- Integration Tests (6.3.1-6.3.3)
  - Created Python-C++ binding integration test suite (71 tests total)
  - test_bindings.py: Module import, enums, Coordinates, BoundingBox, Unit, TerrainEngine, Simulation bindings (53 tests)
  - test_game_flow.py: Scenario loading, turn execution, save/load, victory conditions (8 tests)
  - test_multi_turn.py: Multi-turn simulation, state persistence, stress tests (10 tests)
  - Fixed CMakeLists.txt: Added POSITION_INDEPENDENT_CODE for karkas_core, added KARKAS_BUILD_PYTHON_BINDINGS define
  - All 71 integration tests passing

- C++ Unit Tests (6.2.1-6.2.8)
  - Created comprehensive Google Test-based test suite
  - test_unit.cpp: Unit class tests (identification, hierarchy, logistics, morale, combat, sensors)
  - test_orbat_manager.cpp: ORBAT Manager tests (unit management, spatial queries, hierarchy)
  - test_terrain.cpp: Terrain Engine tests (loading, LOS, pathfinding, mobility, area analysis)
  - test_movement.cpp: Movement Resolver tests (basic movement, routes, fuel, weather, traffic)
  - test_sensors.cpp: Sensor Model tests (detection, EW, weather/night effects, contact aging)
  - test_combat.cpp: Combat Resolver tests (engagement, casualties, morale, ammo consumption)
  - test_logistics.cpp: Supply Model tests (supply points, LOC, resupply, interdiction)
  - test_simulation.cpp: Full simulation integration tests (scenario, orders, turns, victory)
  - Updated tests/CMakeLists.txt with all test files and gtest_discover_tests()
