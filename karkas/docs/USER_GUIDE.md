# KARKAS User Guide

**Version 0.1.0** | Theater-Level Military Simulation Platform

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Requirements](#2-system-requirements)
3. [Installation](#3-installation)
4. [Configuration](#4-configuration)
5. [Quick Start Tutorial](#5-quick-start-tutorial)
6. [Game Concepts](#6-game-concepts)
7. [Using the Client CLI](#7-using-the-client-cli)
8. [Issuing Orders](#8-issuing-orders)
9. [Understanding Turn Results](#9-understanding-turn-results)
10. [Working with Scenarios](#10-working-with-scenarios)
11. [Grisha AI Integration](#11-grisha-ai-integration)
12. [Database & Persistence](#12-database--persistence)
13. [Advanced Tools](#13-advanced-tools)
14. [Troubleshooting](#14-troubleshooting)
15. [API Reference](#15-api-reference)

---

## 1. Introduction

KARKAS is a WEGO (We-Go) turn-based military simulation platform for theater-level operations. It features:

- **Dual-faction gameplay**: Command Red (OPFOR) or Blue (NATO) forces
- **Simultaneous planning**: Both sides issue orders at the same time
- **Fog of war**: See only what your sensors detect
- **AI integration**: Grisha RAG system provides AI commanders and advisors
- **Realistic combat**: Doctrinally-based resolution with terrain effects
- **Natural language orders**: Issue commands in plain English

### How KARKAS Works

```
┌─────────────────────────────────────────────────────────────┐
│                    KARKAS ARCHITECTURE                       │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │   Server    │◄───│  Database   │    │   Grisha    │      │
│  │  (FastAPI)  │    │ (PostgreSQL)│    │ (RAG + LLM) │      │
│  └──────┬──────┘    └─────────────┘    └──────┬──────┘      │
│         │                                      │             │
│         │ REST/WebSocket                       │ Doctrine    │
│         │                                      │ Queries     │
│  ┌──────┴──────┐                        ┌──────┴──────┐      │
│  │    Blue     │                        │    Red      │      │
│  │   Client    │                        │   Client    │      │
│  │  (Human)    │                        │   (AI)      │      │
│  └─────────────┘                        └─────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. System Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| OS | Linux, macOS, or Windows with WSL2 |
| CPU | 4 cores |
| RAM | 8 GB |
| Disk | 10 GB free space |
| Python | 3.11+ |

### For Full Features (AI + Database)

| Component | Requirement |
|-----------|-------------|
| RAM | 16 GB+ (for LLM inference) |
| Disk | 50 GB+ (for terrain data) |
| Docker | 24.0+ |
| Ollama | With llama3.3:70b or similar |

### For Building from Source

| Component | Requirement |
|-----------|-------------|
| C++ Compiler | C++20 support (GCC 11+, Clang 14+) |
| CMake | 3.20+ |
| GDAL | 3.6+ |
| PostgreSQL | 16+ with PostGIS 3.4+ |

---

## 3. Installation

### Option A: Docker (Recommended)

The easiest way to get started:

```bash
# Clone the repository
git clone <repository_url>
cd karkas

# Copy environment configuration
cp .env.example .env

# Build and start all services
make build
make run
```

This starts:
- **KARKAS Server** at http://localhost:8080
- **PostgreSQL/PostGIS** at localhost:5433
- **API Documentation** at http://localhost:8080/docs

#### Docker Commands Reference

| Command | Description |
|---------|-------------|
| `make build` | Build Docker images |
| `make run` | Start all services |
| `make stop` | Stop all services |
| `make logs` | View server logs |
| `make shell` | Open shell in server container |
| `make db-shell` | Open PostgreSQL shell |
| `make clean` | Remove all containers and data |

### Option B: Local Development

#### Step 1: Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y \
    build-essential cmake ninja-build \
    libgdal-dev libpq-dev libpython3-dev \
    python3-pip python3-venv
```

**macOS:**
```bash
brew install cmake ninja gdal postgresql pybind11
```

**Fedora:**
```bash
sudo dnf install -y \
    cmake ninja-build gdal-devel postgresql-devel \
    python3-devel pybind11-devel
```

#### Step 2: Create Python Virtual Environment

```bash
cd karkas
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

#### Step 3: Build C++ Core (Optional - for full simulation)

```bash
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

#### Step 4: Set Up Database (Optional - for persistence)

```bash
# Install PostgreSQL with PostGIS
sudo apt install postgresql postgis

# Create database
sudo -u postgres createuser karkas
sudo -u postgres createdb karkas -O karkas
sudo -u postgres psql -d karkas -c "CREATE EXTENSION postgis;"

# Initialize schema
export KARKAS_DB_ENABLED=true
python -c "from server.database import init_database; init_database(create_tables=True)"
```

#### Step 5: Start the Server

```bash
./run_server.sh
```

Or manually:
```bash
python -m uvicorn server.api.main:app --host 0.0.0.0 --port 8080
```

---

## 4. Configuration

### Environment Variables

Create a `.env` file or export these variables:

#### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `KARKAS_PORT` | `8080` | Server port |
| `KARKAS_DEBUG` | `false` | Enable debug mode |
| `KARKAS_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |

#### Database Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `KARKAS_DB_ENABLED` | `false` | Enable database persistence |
| `KARKAS_DB_HOST` | `localhost` | Database host |
| `KARKAS_DB_PORT` | `5432` | Database port |
| `KARKAS_DB_NAME` | `karkas` | Database name |
| `KARKAS_DB_USER` | `karkas` | Database username |
| `KARKAS_DB_PASSWORD` | `karkas` | Database password |
| `KARKAS_DB_ECHO` | `false` | Log SQL queries |

#### Grisha AI Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GRISHA_API_URL` | `http://localhost:8000` | Grisha RAG API URL |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama LLM host |

### Example .env File

```bash
# Server
KARKAS_PORT=8080
KARKAS_DEBUG=false

# Database
KARKAS_DB_ENABLED=true
KARKAS_DB_HOST=localhost
KARKAS_DB_PORT=5432
KARKAS_DB_NAME=karkas
KARKAS_DB_USER=karkas
KARKAS_DB_PASSWORD=your_secure_password

# AI Integration
GRISHA_API_URL=http://localhost:8000
OLLAMA_HOST=http://localhost:11434
```

---

## 5. Quick Start Tutorial

This walkthrough uses the built-in tutorial scenario.

### Step 1: Start the Server

```bash
# Using Docker
make run

# Or locally
./run_server.sh
```

### Step 2: Open the API Documentation

Visit http://localhost:8080/docs in your browser to see all available endpoints.

### Step 3: Load the Tutorial Scenario

Using curl:
```bash
curl -X POST http://localhost:8080/api/scenarios/tutorial_basics/load
```

Or use the client:
```bash
python client/cli.py --faction blue --scenario tutorial_basics
```

### Step 4: Start the Client CLI

```bash
python client/cli.py --faction blue
```

You'll see:
```
Connecting to http://localhost:8080...
Connected to KARKAS v0.1.0
WebSocket connected - Turn 0, Phase: planning
Subscribed to blue faction updates

KARKAS Interactive Session - Playing as BLUE
============================================================
Commands:
  status    - Show server status
  state     - Show game state
  units     - Show your units
  contacts  - Show enemy contacts
  map       - Display ASCII battlefield map
  order     - Issue an order (natural language)
  orders    - Show submitted orders
  history   - Show turn history
  ready     - Mark ready for turn execution
  help      - Show this help
  quit      - Exit
============================================================

[blue]>
```

### Step 5: View Your Units

```
[blue]> units

Own Forces (4 units):
  - Task Force Blue HQ (headquarters) at (50.4500, 9.5500) [support, 100%]
  - Tank Platoon (armor) at (50.4600, 9.5600) [reserve, 100%]
  - Mechanized Infantry Platoon (mechanized) at (50.4500, 9.5700) [reserve, 100%]
  - Recon Section (recon) at (50.4700, 9.5800) [recon, 100%]
```

### Step 6: View the Map

```
[blue]> map

  9.50                                                      9.80
  +------------------------------------------------------------+
 50.60|                                                          |
      |                         ?                                |
      |                                                          |
      |                                                          |
      |                                                          |
      |                                                          |
      |                                                          |
      |                                                          |
      |       @                                                  |
      |      @@                                                  |
 50.40|                                                          |
  +------------------------------------------------------------+

Legend:
  @ = Friendly unit  ! = Confirmed enemy  ? = Probable enemy  ~ = Suspected
```

### Step 7: Issue an Order

```
[blue]> order
Enter order (natural language): Move Recon Section north to observe Hill 229

Parsed Order:
{
  "target_units": ["blue_recon_sec"],
  "order_type": "move",
  "objective": {
    "type": "position",
    "coordinates": {"latitude": 50.52, "longitude": 9.65}
  },
  "constraints": {
    "route": "covered",
    "roe": "weapons_hold"
  }
}
Order recorded
```

### Step 8: Mark Ready

```
[blue]> ready
Marked ready for turn execution
```

When both sides are ready (Red AI will submit automatically if enabled), the turn executes and you'll see results.

---

## 6. Game Concepts

### 6.1 The WEGO Turn System

KARKAS uses a "We-Go" turn system where both sides act simultaneously:

```
┌─────────────────────────────────────────────────────────────┐
│                      TURN STRUCTURE                          │
├─────────────────────────────────────────────────────────────┤
│  1. PLANNING PHASE (Both sides simultaneously)              │
│     • Review intelligence                                    │
│     • Issue orders to units                                  │
│     • Orders are queued but not executed                    │
│     • Mark "ready" when done                                │
├─────────────────────────────────────────────────────────────┤
│  2. EXECUTION PHASE (Server processes)                       │
│     • Movement resolved (simultaneous)                       │
│     • Detection/sensor updates                               │
│     • Combat resolved at engagement ranges                   │
│     • Logistics consumption                                  │
│     • Morale updates                                        │
├─────────────────────────────────────────────────────────────┤
│  3. REPORTING PHASE                                          │
│     • Results sent to each side                             │
│     • Only see what your units observed                     │
│     • Enemy casualties are estimates                        │
│     • Next turn begins                                      │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Fog of War

You only see what your units detect:

| Confidence | Meaning |
|------------|---------|
| **Confirmed** | Visual identification, high confidence in type/size |
| **Probable** | Good detection, some uncertainty in details |
| **Suspected** | Weak signal, position and type uncertain |
| **Unknown** | Just noise, filtered out |

Contacts degrade over time if not re-observed.

### 6.3 Unit Types

| Type | Role | Mobility |
|------|------|----------|
| **Armor** | Main battle force, anti-armor | Tracked |
| **Mechanized** | Combined arms, versatile | Tracked |
| **Infantry** | Hold terrain, urban combat | Foot |
| **Recon** | Find enemy, early warning | Wheeled |
| **Artillery** | Indirect fire support | Wheeled/Tracked |
| **Air Defense** | Counter air threats | Wheeled |
| **Headquarters** | Command and control | Wheeled |
| **Logistics** | Supply and maintenance | Wheeled |

### 6.4 Terrain Effects

| Terrain | Movement | Cover | Concealment | Notes |
|---------|----------|-------|-------------|-------|
| Open | Normal | None | Low | Fast movement, exposed |
| Forest | Slow | Medium | High | Infantry advantage |
| Urban | Very Slow | High | Medium | Defensive bonus |
| Road | Fast | None | None | Quick movement, vulnerable |
| Water | Impassable | - | - | Must use bridges |
| Hill | Slow | Light | Medium | Observation bonus |

### 6.5 Combat Basics

Combat occurs when units engage within weapon range:

1. **Detection**: Must see enemy to engage
2. **Range**: Different weapons have different ranges
3. **Odds Ratio**: Attacker power vs. defender power
4. **Modifiers**: Terrain, posture, supply affect combat power
5. **Resolution**: Casualties distributed based on doctrine tables
6. **Morale**: Heavy losses cause morale checks, possible retreat

---

## 7. Using the Client CLI

### Starting the Client

```bash
python client/cli.py [options]
```

| Option | Description |
|--------|-------------|
| `--server URL` | Server URL (default: http://localhost:8080) |
| `--faction FACTION` | Play as "red" or "blue" (default: blue) |
| `--scenario NAME` | Load scenario on startup |
| `--no-websocket` | Disable real-time updates |

### Commands Reference

| Command | Description |
|---------|-------------|
| `status` | Show server and connection status |
| `state` | Show current turn, phase, ready status |
| `units` | List your units with positions and strength |
| `contacts` | Show detected enemy contacts |
| `map` | Display ASCII battlefield map |
| `order` | Issue a natural language order |
| `orders` | Show orders submitted this session |
| `history` | Show turn history with events |
| `ready` | Mark ready for turn execution |
| `help` | Show command help |
| `quit` | Exit the client |

### Reading the Map

```
  9.50                                            9.80
  +--------------------------------------------------+
 50.60|          !        ~                            |
      |                                                |
      |     @                   ?                      |
      |    @@                                          |
      |                                                |
 50.40|                                                |
  +--------------------------------------------------+

Legend:
  @ = Friendly unit (Blue)
  ! = Confirmed enemy contact
  ? = Probable enemy contact
  ~ = Suspected enemy contact
```

---

## 8. Issuing Orders

### 8.1 Order Types

| Type | Description | Example |
|------|-------------|---------|
| **MOVE** | Move to location | "Tank Platoon move to 50.52, 9.65" |
| **ATTACK** | Attack enemy or position | "Attack Hill 229 with Tank Platoon" |
| **DEFEND** | Hold position | "Mechanized Platoon defend the crossroads" |
| **RECON** | Scout and observe | "Recon Section observe the village" |
| **SUPPORT** | Fire support for other units | "Artillery support the attack" |
| **WITHDRAW** | Retreat from position | "Withdraw to the rear" |

### 8.2 Natural Language Orders

The system parses plain English orders:

```
[blue]> order
Enter order: Tank Platoon attack Hill 229, use covered routes

Parsed Order:
{
  "target_units": ["blue_tank_plt"],
  "order_type": "attack",
  "objective": {
    "type": "position",
    "name": "hill_229",
    "coordinates": {"latitude": 50.52, "longitude": 9.65}
  },
  "constraints": {
    "route": "covered",
    "roe": "weapons_free"
  }
}
```

### 8.3 Route Preferences

| Route | Description |
|-------|-------------|
| **fastest** | Shortest time, may be exposed |
| **covered** | Use terrain for concealment |
| **avoid_enemy** | Stay away from known contacts |
| **specified** | Follow exact waypoints |

### 8.4 Rules of Engagement

| ROE | Description |
|-----|-------------|
| **weapons_free** | Engage any enemy detected |
| **weapons_tight** | Only engage if directly threatened |
| **weapons_hold** | Do not engage unless ordered |

### 8.5 Order Examples

**Movement:**
```
Move Recon Section to position 50.52, 9.65
Tank Platoon advance north along the road
Mech Platoon move to the crossroads using covered routes
```

**Attack:**
```
Tank Platoon attack the enemy on Hill 229
Attack the village with all available forces
Conduct hasty attack on suspected enemy position
```

**Defense:**
```
Mechanized Platoon defend current position
Establish defensive position at the crossroads
Hold the village until relieved
```

**Reconnaissance:**
```
Recon Section observe Hill 229
Scout the northern approaches
Find the enemy main body
```

---

## 9. Understanding Turn Results

After each turn, you receive a report:

```
============================================================
TURN 3 RESULTS
============================================================

MOVEMENTS (2):
  Tank Platoon: (50.46, 9.56) -> (50.48, 9.60) [2.3 km, complete]
  Recon Section: (50.48, 9.58) -> (50.50, 9.62) [1.8 km, complete]

ENGAGEMENTS (1):
  Tank Platoon vs 1st Mechanized Platoon at (50.51, 9.64)
    Casualties: Tank Platoon lost 2, 1st Mechanized Platoon lost 8 [defender withdrew]

INTELLIGENCE (3):
  Recon Section detected [confirmed] Tank Section at (50.54, 9.69)
  Tank Platoon detected [probable] infantry at (50.52, 9.65)
  Recon Section detected [suspected] movement at (50.55, 9.70)

SUMMARY:
  Attack on Hill 229 successful. Enemy withdrew to Village Bravo.
  Recommend consolidation before next phase.
============================================================
```

### Reading Combat Results

| Term | Meaning |
|------|---------|
| **Casualties** | Personnel/equipment losses |
| **Withdrew** | Unit retreated from combat |
| **Suppressed** | Unit unable to act effectively |
| **Destroyed** | Unit no longer combat effective |

### Contact Confidence

| Level | Accuracy |
|-------|----------|
| **Confirmed** | Position ±100m, type accurate |
| **Probable** | Position ±500m, type likely |
| **Suspected** | Position ±2km, type unknown |

---

## 10. Working with Scenarios

### 10.1 Available Scenarios

List scenarios:
```bash
curl http://localhost:8080/api/scenarios
```

Built-in scenarios:

| Scenario | Description |
|----------|-------------|
| `tutorial_basics` | Tutorial for new players |
| `fulda_gap_1985` | Cold War offensive scenario |

### 10.2 Loading a Scenario

```bash
curl -X POST http://localhost:8080/api/scenarios/fulda_gap_1985/load
```

Or in the client:
```bash
python client/cli.py --scenario fulda_gap_1985
```

### 10.3 Creating Custom Scenarios

Use the scenario editor:

```bash
# Create new scenario from template
python -m tools.scenario_editor new \
    --template cold_war_offensive \
    --region fulda_gap \
    --output my_scenario.yaml

# Add objectives
python -m tools.scenario_editor add-objective my_scenario.yaml \
    --name berlin \
    --type city \
    --lat 52.52 \
    --lon 13.40 \
    --points 100

# Add victory conditions
python -m tools.scenario_editor add-victory-condition my_scenario.yaml \
    --type territorial \
    --description "Capture Berlin" \
    --zones berlin \
    --controller blue \
    --victor red

# Validate
python -m tools.scenario_editor validate my_scenario.yaml
```

### 10.4 Creating ORBATs

```bash
# Create new ORBAT
python -m tools.scenario_editor new-orbat \
    --template sample_red \
    --output my_orbat.yaml

# Add units
python -m tools.scenario_editor add-unit my_orbat.yaml \
    --id tank_bn_1 \
    --name "1st Tank Battalion" \
    --type armor \
    --echelon battalion \
    --lat 50.5 \
    --lon 9.6 \
    --personnel 500 \
    --equipment 31
```

### 10.5 Generating Terrain

```bash
# Generate terrain for a region
python tools/generate_tutorial_terrain.py --output data/terrain/my_region.gpkg
```

---

## 11. Grisha AI Integration

### 11.1 Overview

Grisha provides AI capabilities:

| Role | Description |
|------|-------------|
| **Commander** | Autonomous decision-making for Red force |
| **Advisor** | Analysis and recommendations for Blue force |
| **Order Parser** | Natural language to structured orders |

### 11.2 Requirements

1. **Grisha RAG System** running with military doctrine loaded
2. **Ollama** with a capable model (llama3.3:70b recommended)

### 11.3 Starting Grisha

```bash
# Start Grisha API (from main grisha directory)
python grisha_api.py

# Ensure Ollama is running with model loaded
ollama run llama3.3:70b
```

### 11.4 Enabling AI Commander

Enable Red AI commander:
```bash
curl -X POST http://localhost:8080/api/grisha/enable/red
```

The AI will automatically:
1. Analyze the situation
2. Query doctrine for guidance
3. Generate orders
4. Submit when ready

### 11.5 Getting AI Advice (Blue)

As Blue player, ask for advice:
```bash
curl -X POST http://localhost:8080/api/grisha/advise \
    -H "Content-Type: application/json" \
    -d '{"question": "What is the best approach to take Hill 229?"}'
```

---

## 12. Database & Persistence

### 12.1 Enabling Persistence

Set environment variable:
```bash
export KARKAS_DB_ENABLED=true
```

Or in `.env`:
```
KARKAS_DB_ENABLED=true
```

### 12.2 Database Administration

Use the admin tool:

```bash
# Initialize database
python tools/db_admin.py init --reset

# List games
python tools/db_admin.py list

# View game history
python tools/db_admin.py history <game_id>

# Export game
python tools/db_admin.py export <game_id> --output game_export.json

# Delete game
python tools/db_admin.py delete <game_id>
```

### 12.3 Saving and Loading Games

Games auto-save when turns execute.

Load a saved game:
```bash
curl -X POST http://localhost:8080/api/persistence/games/<game_id>/load
```

### 12.4 Replay

View game replay:
```bash
curl http://localhost:8080/api/persistence/games/<game_id>/replay
```

Step through turns:
```bash
# Step forward
curl -X POST http://localhost:8080/api/persistence/games/<game_id>/replay/step?direction=forward

# Step backward
curl -X POST http://localhost:8080/api/persistence/games/<game_id>/replay/step?direction=backward

# Jump to turn
curl -X POST http://localhost:8080/api/persistence/games/<game_id>/replay/jump?turn=5
```

---

## 13. Advanced Tools

### 13.1 Scenario Editor

Full CLI for scenario management:

```bash
# Interactive mode
python -m tools.scenario_editor interactive my_scenario.yaml

# Export to JSON
python -m tools.scenario_editor export my_scenario.yaml --format json

# Validate scenario
python -m tools.scenario_editor validate my_scenario.yaml

# List available templates
python -m tools.scenario_editor list-templates
```

### 13.2 Terrain Processor

Process real-world GIS data:

```bash
# Download elevation data
python -m tools.terrain_processor download srtm --region europe

# Process terrain
python -m tools.terrain_processor process \
    --elevation data/raw/srtm/ \
    --landcover data/raw/worldcover/ \
    --output data/terrain/europe.gpkg
```

### 13.3 Database Admin

```bash
# Full database reset
python tools/db_admin.py init --reset

# View statistics
python tools/db_admin.py stats

# Backup database
make db-backup
```

---

## 14. Troubleshooting

### Connection Issues

**"Cannot connect to server"**
```bash
# Check if server is running
curl http://localhost:8080/health

# Check logs
make logs  # Docker
# or
tail -f server.log  # Local
```

**"WebSocket connection failed"**
- Check firewall settings
- Try `--no-websocket` flag for HTTP-only mode

### Database Issues

**"Database connection failed"**
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Check connection
psql -h localhost -U karkas -d karkas

# Reinitialize
python tools/db_admin.py init --reset
```

### Scenario Issues

**"Scenario not found"**
```bash
# List available scenarios
curl http://localhost:8080/api/scenarios

# Check scenario directory
ls data/scenarios/
```

**"Invalid scenario format"**
```bash
# Validate scenario
python -m tools.scenario_editor validate my_scenario.yaml
```

### AI/Grisha Issues

**"Grisha API not available"**
```bash
# Check Grisha is running
curl http://localhost:8000/health

# Start Grisha
cd /path/to/grisha && ./grisha.sh
```

**"Ollama not responding"**
```bash
# Check Ollama
curl http://localhost:11434/api/tags

# Ensure model is loaded
ollama list
ollama pull llama3.3:70b
```

### Performance Issues

**Slow terrain loading**
- Use lower resolution (200m instead of 100m)
- Reduce scenario area bounds

**High memory usage**
- Reduce WebSocket connections
- Use smaller LLM model for AI

---

## 15. API Reference

### Base URL

```
http://localhost:8080
```

### Endpoints

#### Game Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Server info |
| GET | `/health` | Health check |
| GET | `/api/game/state` | Current game state |
| POST | `/api/game/ready/{faction}` | Mark faction ready |
| POST | `/api/game/submit-orders/{faction}` | Submit orders |

#### Units

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/units` | List all units |
| GET | `/api/units/{id}` | Get unit details |
| POST | `/api/units` | Create unit |
| PUT | `/api/units/{id}` | Update unit |

#### Orders

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/orders` | List orders |
| POST | `/api/orders` | Create order |
| POST | `/api/orders/validate` | Validate order |
| POST | `/api/orders/parse-natural-language` | Parse NL order |

#### Scenarios

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/scenarios` | List scenarios |
| GET | `/api/scenarios/{id}` | Scenario details |
| POST | `/api/scenarios/{id}/load` | Load scenario |

#### Perception

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/perception/{faction}` | Get faction's perception state |

#### Grisha AI

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/grisha/status` | AI status |
| POST | `/api/grisha/enable/{faction}` | Enable AI |
| POST | `/api/grisha/disable/{faction}` | Disable AI |

#### WebSocket

| Endpoint | Description |
|----------|-------------|
| `ws://localhost:8080/ws` | Real-time updates |

**WebSocket Messages:**

```json
// Subscribe to faction
{"type": "subscribe", "faction": "blue"}

// Heartbeat
{"type": "ping"}

// Received messages
{"type": "phase_change", "phase": "execution", "turn": 3}
{"type": "orders_submitted", "faction": "red"}
{"type": "turn_result", "turn": 3, "result": {...}}
{"type": "new_turn", "turn": 4, "phase": "planning"}
```

---

## Quick Reference Card

### Essential Commands

```bash
# Start server (Docker)
make run

# Start client
python client/cli.py --faction blue

# Load scenario
curl -X POST http://localhost:8080/api/scenarios/tutorial_basics/load

# View game state
curl http://localhost:8080/api/game/state

# Submit orders
curl -X POST http://localhost:8080/api/game/submit-orders/blue \
    -H "Content-Type: application/json" \
    -d '{"orders": [...]}'
```

### Client Commands

```
status   - Server status
state    - Game state
units    - Your units
contacts - Enemy contacts
map      - Battlefield map
order    - Issue order
ready    - Mark ready
```

### Order Format

```
[Unit] [action] [target/location] [constraints]

Examples:
  Tank Platoon attack Hill 229
  Recon Section move to 50.52, 9.65 using covered routes
  Mech Platoon defend the crossroads, weapons tight
```

---

*For more information, visit the API documentation at http://localhost:8080/docs*
