# Grisha + Karkas User Guide

Complete guide for the Grisha RAG system and Karkas military simulation platform.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Building Your Knowledge Base](#building-your-knowledge-base)
3. [Using Grisha](#using-grisha)
4. [Using Karkas](#using-karkas)
5. [Game Concepts](#game-concepts)
6. [Using the Client CLI](#using-the-client-cli)
7. [Issuing Orders](#issuing-orders)
8. [Understanding Turn Results](#understanding-turn-results)
9. [Working with Scenarios](#working-with-scenarios)
10. [Grisha AI Integration](#grisha-ai-integration)
11. [Database and Persistence](#database-and-persistence)
12. [Advanced Tools](#advanced-tools)
13. [Configuration Reference](#configuration-reference)
14. [Troubleshooting](#troubleshooting)
15. [API Reference](#api-reference)
16. [Quick Reference](#quick-reference)

---

## Getting Started

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 16 GB | 32 GB |
| Storage | 10 GB | 50 GB (with terrain data) |
| GPU | Not required | NVIDIA GPU for faster inference |
| OS | Linux (tested on Fedora) | Linux |

**Required software:**

| Software | Purpose |
|----------|---------|
| Python 3.11+ | Core runtime |
| Ollama | Local LLM inference |
| tmux | Unified launcher |
| PostgreSQL + PostGIS | Karkas persistence (optional) |
| CMake 3.20+, C++20 compiler | Building C++ components |
| GDAL | Terrain processing |

### Installing Ollama

Grisha requires Ollama for local LLM inference.

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull the required model
ollama pull qwen2.5:14b-instruct-q4_K_M

# Verify it's working
ollama run qwen2.5:14b-instruct-q4_K_M "Hello, respond with OK"
```

### Installing Dependencies

```bash
# Clone the repository
git clone https://github.com/your-username/grisha.git
cd grisha

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Karkas package (includes all Karkas dependencies)
cd karkas
pip install -e .
cd ..

# Build the C++ BM25 module (optional, for hybrid search)
cd cpp
pip install pybind11 scikit-build-core
pip install -e .
cd ..

# Verify installation
python -c "import chromadb; print('ChromaDB OK')"
python -c "import grisha_bm25; print('BM25 OK')"  # Only if you built it
```

### Installing tmux

tmux is required for the unified launcher.

```bash
# Fedora
sudo dnf install tmux

# Ubuntu/Debian
sudo apt install tmux
```

---

## Building Your Knowledge Base

The repository does not include pre-built document collections or vector databases. You must build your own knowledge base by ingesting documents.

### Directory Structure

Create the `brain/` directory with your source documents:

```
brain/
├── manuals/        # Field manuals, regulations (highest priority)
├── papers/         # Research papers, analysis
├── strategy/       # Strategic documents
├── us_doctrine/    # US military doctrine (for OPFOR analysis)
└── wiki/           # General reference material (lowest priority)
```

### Supported Document Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| PDF | `.pdf` | Text extraction with OCR fallback |
| JSONL | `.jsonl` | Each line: `{"text": "...", "metadata": {...}}` |

### Ingesting Documents

```bash
# Ingest a single file
python3 grisha_ingestor.py brain/manuals/fm7-8.pdf

# Ingest an entire directory (recursive)
python3 grisha_ingestor.py brain/

# Ingest with verbose output
python3 grisha_ingestor.py brain/ --verbose
```

The ingestor will:
1. Extract text from documents
2. Chunk text into ~900 token segments with 150 token overlap
3. Classify documents by type (doctrine, operational, tactical, etc.)
4. Tag documents with nation metadata (RU/US)
5. Generate embeddings and store in ChromaDB
6. Build BM25 keyword index (if enabled)

### Quick Start with Minimal Data

If you want to test without gathering documents, create a simple JSONL file:

```bash
mkdir -p brain/manuals

cat > brain/manuals/sample.jsonl << 'EOF'
{"text": "The battalion is the basic tactical unit capable of independent operations. It consists of 3-5 companies plus support elements.", "source": "sample", "doc_type": "doctrine_primary", "nation": "RU"}
{"text": "Offensive operations aim to destroy enemy forces and seize terrain. The attacker should achieve 3:1 superiority at the point of main effort.", "source": "sample", "doc_type": "doctrine_primary", "nation": "RU"}
{"text": "Defense in depth employs multiple defensive lines to absorb and defeat enemy attacks. Forward positions trade space for time.", "source": "sample", "doc_type": "doctrine_primary", "nation": "RU"}
EOF

python3 grisha_ingestor.py brain/manuals/sample.jsonl
```

### Verifying Your Knowledge Base

```bash
# Check ChromaDB collection size
python3 -c "
import chromadb
client = chromadb.PersistentClient(path='./grisha_db')
col = client.get_collection('grisha_knowledge')
print(f'Documents in collection: {col.count()}')
"
```

---

## Using Grisha

### Interactive Query Mode

The simplest way to use Grisha is the interactive shell:

```bash
./grisha.sh
```

This script:
1. Activates the virtual environment
2. Starts Ollama if not running
3. Pre-loads the model into memory
4. Launches the query interface

Example session:

```
╔══════════════════════════════════════════════════════════════╗
║                    GRISHA QUERY SYSTEM                       ║
╚══════════════════════════════════════════════════════════════╝

Enter your question (or 'quit' to exit):
> What is the recommended force ratio for offensive operations?

[Searching knowledge base...]
[Found 5 relevant passages]
[Generating response...]

According to Soviet doctrine, offensive operations should achieve...

Sources:
- FM 100-2-1, Chapter 4, p.23
- Tactical Manual BTR Operations, Section 2.3

> quit
Goodbye.
```

### Direct Python Usage

```python
from grisha_query import GrishaQuery

# Initialize
grisha = GrishaQuery()

# Simple query
response = grisha.query("How should a motorized rifle battalion conduct a meeting engagement?")
print(response.answer)
print(response.sources)

# Query with options
response = grisha.query(
    question="What are Javelin missile specifications?",
    include_us_doctrine=True,  # Include US sources for OPFOR analysis
    top_k=10                   # Retrieve more context
)
```

### REST API

Start the API server:

```bash
python3 grisha_api.py
# Server runs on http://localhost:8000
```

Query via curl:

```bash
curl "http://localhost:8000/search?q=battalion+attack+formation"
```

Response:

```json
{
  "context": "[RU - FM 100-2-1 (Chapter 4)]: The battalion attacks in two echelons..."
}
```

---

## Using Karkas

### Prerequisites

Karkas requires additional setup beyond Grisha:

```bash
# Install tmux (for unified launcher)
sudo dnf install tmux  # Fedora
sudo apt install tmux  # Ubuntu

# Install PostgreSQL with PostGIS (optional, for persistence)
sudo dnf install postgresql-server postgis  # Fedora
sudo apt install postgresql postgis         # Ubuntu

# Initialize database
sudo postgresql-setup --initdb
sudo systemctl start postgresql

# Create database and user
sudo -u postgres psql << EOF
CREATE USER karkas WITH PASSWORD 'karkas';
CREATE DATABASE karkas OWNER karkas;
\c karkas
CREATE EXTENSION postgis;
EOF
```

### Building the C++ Core

```bash
cd karkas/server/core
mkdir build && cd build
cmake ..
make -j$(nproc)
cd ../../../..

# Verify
python -c "import karkas_engine; print('Karkas engine OK')"
```

### Unified Launcher (Recommended)

The easiest way to run both Grisha and Karkas together:

```bash
./karkas.sh
```

This script:
1. Checks all prerequisites (venv, Ollama, PostgreSQL, tmux)
2. Starts PostgreSQL if not running
3. Starts Ollama if not running
4. Pre-loads the LLM model into memory
5. Launches Grisha API (port 8000) and Karkas Server (port 8080) in tmux
6. Performs health checks and waits for services to be ready
7. Attaches you to the tmux session

**tmux layout:**
```
┌─────────────────────────────────────┐
│          Grisha API (8000)          │
├─────────────────────────────────────┤
│         Karkas Server (8080)        │
└─────────────────────────────────────┘
```

**tmux controls:**

| Keys | Action |
|------|--------|
| `Ctrl-B D` | Detach from session (services keep running) |
| `Ctrl-B ↑` or `Ctrl-B ↓` | Switch between panes |
| `Ctrl-B [` | Enter scroll mode (press `q` to exit) |
| `Ctrl-C` | Stop service in current pane |

**Reattaching later:**
```bash
tmux attach -t karkas
```

**Stopping all services:**
```bash
./karkas-stop.sh
```

The stop script shows the status of each service and cleanly terminates the tmux session. PostgreSQL and Ollama remain running (managed by systemd).

### Starting Components Individually

If you prefer to run services separately:

```bash
# Grisha interactive only
./grisha.sh

# Grisha API only
python3 grisha_api.py

# Karkas only (Docker)
cd karkas
make build && make run

# Karkas only (local)
cd karkas
./run_server.sh

# Or manually
cd karkas
python -m uvicorn server.api.main:app --host 0.0.0.0 --port 8080
```

---

## Game Concepts

### The WEGO Turn System

KARKAS uses a "We-Go" turn system where both sides act simultaneously:

```
┌─────────────────────────────────────────────────────────────┐
│                      TURN STRUCTURE                          │
├─────────────────────────────────────────────────────────────┤
│  1. PLANNING PHASE (Both sides simultaneously)              │
│     - Review intelligence                                    │
│     - Issue orders to units                                  │
│     - Orders are queued but not executed                    │
│     - Mark "ready" when done                                │
├─────────────────────────────────────────────────────────────┤
│  2. EXECUTION PHASE (Server processes)                       │
│     - Movement resolved (simultaneous)                       │
│     - Detection/sensor updates                               │
│     - Combat resolved at engagement ranges                   │
│     - Logistics consumption                                  │
│     - Morale updates                                        │
├─────────────────────────────────────────────────────────────┤
│  3. REPORTING PHASE                                          │
│     - Results sent to each side                             │
│     - Only see what your units observed                     │
│     - Enemy casualties are estimates                        │
│     - Next turn begins                                      │
└─────────────────────────────────────────────────────────────┘
```

### Fog of War

You only see what your units detect:

| Confidence | Meaning | Position Accuracy |
|------------|---------|-------------------|
| **Confirmed** | Visual identification, high confidence | ±100m |
| **Probable** | Good detection, some uncertainty | ±500m |
| **Suspected** | Weak signal, type uncertain | ±2km |
| **Unknown** | Just noise, filtered out | - |

Contacts degrade over time if not re-observed.

### Unit Types

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

### Terrain Effects

| Terrain | Movement | Cover | Concealment | Notes |
|---------|----------|-------|-------------|-------|
| Open | Normal | None | Low | Fast movement, exposed |
| Forest | Slow | Medium | High | Infantry advantage |
| Urban | Very Slow | High | Medium | Defensive bonus |
| Road | Fast | None | None | Quick movement, vulnerable |
| Water | Impassable | - | - | Must use bridges |
| Hill | Slow | Light | Medium | Observation bonus |

### Combat Basics

Combat occurs when units engage within weapon range:

1. **Detection**: Must see enemy to engage
2. **Range**: Different weapons have different ranges
3. **Odds Ratio**: Attacker power vs. defender power
4. **Modifiers**: Terrain, posture, supply affect combat power
5. **Resolution**: Casualties distributed based on doctrine tables
6. **Morale**: Heavy losses cause morale checks, possible retreat

---

## Using the Client CLI

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

### Example Session

```bash
python client/cli.py --faction blue --scenario tutorial_basics
```

```
Connecting to http://localhost:8080...
Connected to KARKAS v0.1.0
WebSocket connected - Turn 0, Phase: planning

KARKAS Interactive Session - Playing as BLUE
============================================================

[blue]> units

Own Forces (4 units):
  - Task Force Blue HQ (headquarters) at (50.4500, 9.5500) [support, 100%]
  - Tank Platoon (armor) at (50.4600, 9.5600) [reserve, 100%]
  - Mechanized Infantry Platoon (mechanized) at (50.4500, 9.5700) [reserve, 100%]
  - Recon Section (recon) at (50.4700, 9.5800) [recon, 100%]

[blue]> map

  9.50                                                      9.80
  +------------------------------------------------------------+
 50.60|                                                          |
      |                         ?                                |
      |       @                                                  |
      |      @@                                                  |
 50.40|                                                          |
  +------------------------------------------------------------+

Legend:
  @ = Friendly unit  ! = Confirmed enemy  ? = Probable enemy  ~ = Suspected
```

---

## Issuing Orders

### Order Types

| Type | Description | Example |
|------|-------------|---------|
| **MOVE** | Move to location | "Tank Platoon move to 50.52, 9.65" |
| **ATTACK** | Attack enemy or position | "Attack Hill 229 with Tank Platoon" |
| **DEFEND** | Hold position | "Mechanized Platoon defend the crossroads" |
| **RECON** | Scout and observe | "Recon Section observe the village" |
| **SUPPORT** | Fire support for other units | "Artillery support the attack" |
| **WITHDRAW** | Retreat from position | "Withdraw to the rear" |

### Natural Language Orders

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
Order recorded
```

### Route Preferences

| Route | Description |
|-------|-------------|
| **fastest** | Shortest time, may be exposed |
| **covered** | Use terrain for concealment |
| **avoid_enemy** | Stay away from known contacts |
| **specified** | Follow exact waypoints |

### Rules of Engagement

| ROE | Description |
|-----|-------------|
| **weapons_free** | Engage any enemy detected |
| **weapons_tight** | Only engage if directly threatened |
| **weapons_hold** | Do not engage unless ordered |

### Order Examples

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

## Understanding Turn Results

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
    Casualties: Tank Platoon lost 2, enemy lost 8 [defender withdrew]

INTELLIGENCE (3):
  Recon Section detected [confirmed] Tank Section at (50.54, 9.69)
  Tank Platoon detected [probable] infantry at (50.52, 9.65)
  Recon Section detected [suspected] movement at (50.55, 9.70)

SUMMARY:
  Attack on Hill 229 successful. Enemy withdrew to Village Bravo.
============================================================
```

### Reading Combat Results

| Term | Meaning |
|------|---------|
| **Casualties** | Personnel/equipment losses |
| **Withdrew** | Unit retreated from combat |
| **Suppressed** | Unit unable to act effectively |
| **Destroyed** | Unit no longer combat effective |

---

## Working with Scenarios

### Available Scenarios

List scenarios:
```bash
curl http://localhost:8080/api/scenarios
```

Built-in scenarios:

| Scenario | Description |
|----------|-------------|
| `tutorial_basics` | Tutorial for new players |
| `fulda_gap_1985` | Cold War offensive scenario |

### Loading a Scenario

```bash
curl -X POST http://localhost:8080/api/scenarios/tutorial_basics/load
```

Or in the client:
```bash
python client/cli.py --scenario tutorial_basics
```

### Creating Custom Scenarios

Use the scenario editor:

```bash
# Create new scenario from template
python -m tools.scenario_editor new \
    --template cold_war_offensive \
    --region fulda_gap \
    --output my_scenario.yaml

# Add objectives
python -m tools.scenario_editor add-objective my_scenario.yaml \
    --name hill_305 \
    --type terrain \
    --lat 50.52 \
    --lon 9.65 \
    --points 100

# Add victory conditions
python -m tools.scenario_editor add-victory-condition my_scenario.yaml \
    --type territorial \
    --description "Capture Hill 305" \
    --zones hill_305 \
    --controller blue \
    --victor red

# Validate
python -m tools.scenario_editor validate my_scenario.yaml
```

### Creating ORBATs

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

---

## Grisha AI Integration

### Overview

Grisha provides AI capabilities:

| Role | Description |
|------|-------------|
| **Commander** | Autonomous decision-making for Red force (Colonel Petrov) |
| **Advisor** | Analysis and recommendations for Blue force (Major Mitchell) |
| **Order Parser** | Natural language to structured orders |

### Requirements

1. **Grisha RAG System** running with military doctrine loaded
2. **Ollama** with a capable model (qwen2.5:14b recommended)

### Enabling AI Commander

Enable Red AI commander:
```bash
curl -X POST http://localhost:8080/api/grisha/enable/red
```

The AI will automatically:
1. Analyze the situation
2. Query doctrine for guidance
3. Generate orders
4. Submit when ready

### Getting AI Advice (Blue)

As Blue player, ask for advice:
```bash
curl -X POST http://localhost:8080/api/grisha/advise \
    -H "Content-Type: application/json" \
    -d '{"question": "What is the best approach to take Hill 229?"}'
```

### Checking AI Status

```bash
curl http://localhost:8080/api/grisha/status
```

---

## Database and Persistence

### Enabling Persistence

Set environment variable:
```bash
export KARKAS_DB_ENABLED=true
```

Or in `.env`:
```
KARKAS_DB_ENABLED=true
```

### Database Administration

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

### Saving and Loading Games

Games auto-save when turns execute.

Load a saved game:
```bash
curl -X POST http://localhost:8080/api/persistence/games/<game_id>/load
```

### Replay

View game replay:
```bash
curl http://localhost:8080/api/persistence/games/<game_id>/replay
```

Step through turns:
```bash
# Step forward
curl -X POST "http://localhost:8080/api/persistence/games/<game_id>/replay/step?direction=forward"

# Step backward
curl -X POST "http://localhost:8080/api/persistence/games/<game_id>/replay/step?direction=backward"

# Jump to turn
curl -X POST "http://localhost:8080/api/persistence/games/<game_id>/replay/jump?turn=5"
```

---

## Advanced Tools

### Scenario Editor

Full CLI for scenario management:

```bash
# Interactive mode
python -m tools.scenario_editor interactive my_scenario.yaml

# Export to JSON
python -m tools.scenario_editor export my_scenario.yaml --format json

# List available templates
python -m tools.scenario_editor list-templates

# List predefined regions
python -m tools.scenario_editor list-regions
```

### Terrain Processor

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

### Database Admin

```bash
# Full database reset
python tools/db_admin.py init --reset

# View statistics
python tools/db_admin.py stats

# Backup database (Docker)
make db-backup
```

---

## Configuration Reference

### Grisha (`config.yaml`)

```yaml
model_settings:
  max_tokens: 900              # Chunk size for ingestion
  overlap_tokens: 150          # Overlap between chunks
  model_name: "qwen2.5:14b-instruct-q4_K_M"
  embed_model: "bge-large-en-v1.5"

database_settings:
  path: "./grisha_db"
  collection_name: "grisha_knowledge"

bm25_settings:
  index_path: "./bm25_index"
  k1: 1.2                      # Term frequency saturation
  b: 0.75                      # Length normalization

hybrid_settings:
  enabled: true                # Enable after building BM25 index
  rrf_k: 60.0                  # RRF fusion constant
  semantic_weight: 0.5
  bm25_weight: 0.5

hallucination_guard:
  verify_citations: true
  fail_on_invalid: false
  warn_user: true

logging:
  level: "INFO"                # DEBUG, INFO, WARNING, ERROR
  format: "text"               # text or json
  file: null                   # Optional log file path
```

### Karkas (Environment Variables)

#### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `KARKAS_PORT` | `8080` | Server port |
| `KARKAS_HOST` | `0.0.0.0` | Server host |
| `KARKAS_DEBUG` | `false` | Enable debug mode |

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

#### Logging Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `KARKAS_LOG_LEVEL` | `INFO` | Log level |
| `KARKAS_LOG_FORMAT` | `text` | Log format (text or json) |
| `KARKAS_LOG_DIR` | `null` | Directory for log files |

#### Grisha Integration

| Variable | Default | Description |
|----------|---------|-------------|
| `GRISHA_API_URL` | `http://localhost:8000` | Grisha RAG API URL |
| `GRISHA_ENABLED` | `true` | Enable Grisha integration |

#### Ollama Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama LLM host |
| `OLLAMA_MODEL` | `qwen2.5:14b-instruct-q4_K_M` | Default model |

---

## Troubleshooting

### Ollama Issues

**Model not found:**
```bash
ollama pull qwen2.5:14b-instruct-q4_K_M
```

**Ollama not running:**
```bash
ollama serve &
# Or
systemctl start ollama
```

**Out of memory:**
Try a smaller model:
```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
# Update config.yaml model_name accordingly
```

### ChromaDB Issues

**Collection not found:**
```bash
# Re-run ingestion
python3 grisha_ingestor.py brain/
```

**Database corrupted:**
```bash
rm -rf grisha_db/
python3 grisha_ingestor.py brain/
```

### Karkas Issues

**Database connection refused:**
```bash
sudo systemctl start postgresql
# Check credentials in environment variables
```

**C++ module not found:**
```bash
cd karkas/server/core/build
cmake .. && make -j$(nproc)
# Ensure build artifacts are in Python path
```

**Terrain data missing:**
```bash
cd karkas/tools/terrain_processor
python main.py --region tutorial --resolution 100
```

**Missing Python dependencies (e.g., geoalchemy2):**
```bash
cd karkas
pip install -e .
```

### Unified Launcher Issues

**tmux not found:**
```bash
sudo dnf install tmux  # Fedora
sudo apt install tmux  # Ubuntu
```

**Session already exists:**
```bash
# Either attach to existing session
tmux attach -t karkas

# Or kill and restart
./karkas-stop.sh && ./karkas.sh
```

**Services not becoming healthy:**

If the health check times out, the services may still be starting. Check the tmux session for errors:
```bash
tmux attach -t karkas
# Look at each pane for error messages
```

Common causes:
- ChromaDB collection not found (run ingestor first)
- Port already in use (check with `lsof -i:8000` or `lsof -i:8080`)
- Missing Python dependencies

**Orphaned processes after crash:**

If services are running outside tmux (e.g., after a crash):
```bash
# Find and kill processes on the ports
lsof -ti:8000 | xargs kill  # Grisha API
lsof -ti:8080 | xargs kill  # Karkas Server
```

**PostgreSQL won't start:**
```bash
# Check status
sudo systemctl status postgresql

# View logs
sudo journalctl -u postgresql -n 50

# Common fix: initialize if first time
sudo postgresql-setup --initdb
sudo systemctl start postgresql
```

### Performance Tuning

**Slow queries:**
- Enable hybrid search in config.yaml
- Reduce `top_k` parameter
- Use a smaller/quantized model

**High memory usage:**
- Reduce ChromaDB cache size
- Use smaller embedding model
- Limit concurrent connections

---

## API Reference

### Base URLs

| Service | URL |
|---------|-----|
| Grisha API | http://localhost:8000 |
| Karkas Server | http://localhost:8080 |
| Karkas API Docs | http://localhost:8080/docs |

### Grisha Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/search?q=<query>` | Search doctrine, returns context |

### Karkas Endpoints

#### Server Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Server info |
| GET | `/health` | Health check with component status |

#### Game Control

| Method | Endpoint | Description |
|--------|----------|-------------|
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
| GET | `/api/perception/{faction}` | Get faction's view |

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

## Quick Reference

### Launcher Commands

| Command | Description |
|---------|-------------|
| `./karkas.sh` | Start Grisha API + Karkas Server |
| `./karkas-stop.sh` | Stop all services |
| `./grisha.sh` | Start Grisha interactive mode only |
| `tmux attach -t karkas` | Reattach to running session |

### Service Endpoints

| Service | URL | Health Check |
|---------|-----|--------------|
| Grisha API | http://localhost:8000 | `/search?q=test` |
| Karkas Server | http://localhost:8080 | `/health` |
| Karkas API Docs | http://localhost:8080/docs | - |

### tmux Quick Reference

| Keys | Action |
|------|--------|
| `Ctrl-B D` | Detach (services keep running) |
| `Ctrl-B ↑/↓` | Switch panes |
| `Ctrl-B [` | Scroll mode (`q` to exit) |
| `Ctrl-B %` | Split pane vertically |
| `Ctrl-B "` | Split pane horizontally |
| `Ctrl-B x` | Kill current pane |

### Client Commands

| Command | Description |
|---------|-------------|
| `status` | Server status |
| `state` | Game state |
| `units` | Your units |
| `contacts` | Enemy contacts |
| `map` | Battlefield map |
| `order` | Issue order |
| `ready` | Mark ready |

### Order Format

```
[Unit] [action] [target/location] [constraints]

Examples:
  Tank Platoon attack Hill 229
  Recon Section move to 50.52, 9.65 using covered routes
  Mech Platoon defend the crossroads, weapons tight
```
