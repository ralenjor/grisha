# Grisha + Karkas

**Theater-level military simulation with doctrine-aware AI**

Grisha is a RAG (Retrieval-Augmented Generation) system for military doctrine. Karkas is a WEGO wargame platform that uses Grisha for AI decision-making. Together they create an operational-level simulation where AI commanders make doctrine-informed decisions.

## Features

### Grisha - Doctrine RAG System
- **Hybrid search**: Semantic embeddings + BM25 keyword matching with Reciprocal Rank Fusion
- **Document classification**: Automatic tiering (doctrine, operational, tactical, technical, reference)
- **Nation segregation**: Filters by RU/US doctrine with OPFOR detection
- **Multi-signal reranking**: Semantic distance, document type, source authority
- **Hallucination guard**: Citation verification against source material
- **Local inference**: ONNXMiniLM embeddings + Ollama LLM (no external APIs)

### Karkas - Simulation Platform
- **WEGO turn system**: Simultaneous planning, sequential execution
- **C++ simulation core**: ~6000 LOC covering terrain, movement, sensors, combat, logistics
- **GIS terrain**: Real-world data from OSM, SRTM elevation, ESA land cover
- **Fog of war**: Sensor-based perception with contact confidence degradation
- **AI commanders**: Doctrine-driven decision making via Grisha queries
- **Natural language orders**: Parse free-text commands into structured orders
- **Persistence**: PostgreSQL/PostGIS with full replay capability

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              KARKAS                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────┐  │
│  │   Client    │◄──►│  FastAPI    │◄──►│     C++ Simulation Core     │  │
│  │    CLI      │ WS │   Server    │    │  ┌─────────┬─────────────┐  │  │
│  │  + ASCII    │    │             │    │  │ Terrain │  Movement   │  │  │
│  │    Map      │    │  /api/...   │    │  │ Engine  │  Resolver   │  │  │
│  └─────────────┘    │             │    │  ├─────────┼─────────────┤  │  │
│                     │  Orders     │    │  │ Sensor  │   Combat    │  │  │
│                     │  Units      │    │  │  Model  │  Resolver   │  │  │
│                     │  Game       │    │  ├─────────┴─────────────┤  │  │
│                     │  Scenarios  │    │  │  Logistics / Supply   │  │  │
│                     └──────┬──────┘    │  └───────────────────────┘  │  │
│                            │           └─────────────────────────────┘  │
│                            ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      Grisha Integration                          │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐    │   │
│  │  │   Commander   │  │    Advisor    │  │   Order Parser    │    │   │
│  │  │  (Red Force)  │  │  (Blue Force) │  │  (NL → Struct)    │    │   │
│  │  │  Col. Petrov  │  │  Maj. Mitchell│  │                   │    │   │
│  │  └───────┬───────┘  └───────┬───────┘  └─────────┬─────────┘    │   │
│  └──────────┼──────────────────┼────────────────────┼──────────────┘   │
│             └──────────────────┼────────────────────┘                   │
│                                ▼                                        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│                              GRISHA                                      │
│  ┌─────────────┐    ┌─────────────────────────────────────────────┐     │
│  │   Ollama    │◄───│              Query Engine                    │     │
│  │  LLM Local  │    │  ┌─────────┐  ┌─────────┐  ┌─────────────┐  │     │
│  │             │    │  │ChromaDB │  │  BM25   │  │  Reranker   │  │     │
│  │ llama3.3:70b│    │  │Semantic │  │ Keyword │  │ Multi-signal│  │     │
│  └─────────────┘    │  │ Search  │  │ Search  │  │  Scoring    │  │     │
│                     │  └────┬────┘  └────┬────┘  └──────┬──────┘  │     │
│                     │       └──────┬─────┘              │         │     │
│                     │              ▼                    │         │     │
│                     │     Reciprocal Rank Fusion ───────┘         │     │
│                     └─────────────────────────────────────────────┘     │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                         Ingestor                                 │    │
│  │   PDF/JSONL → Chunking → Classification → Embeddings → Index    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Ollama with `llama3.3:70b` (or configure alternative)
- PostgreSQL 16+ with PostGIS 3.4+ (for Karkas)
- CMake 3.20+, C++20 compiler, GDAL (for building C++ components)

### Installation

```bash
# Clone repository
git clone https://github.com/your-username/grisha.git
cd grisha

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Build C++ BM25 module (Grisha hybrid search)
cd cpp
pip install pybind11 scikit-build-core
pip install -e .
cd ..

# Build Karkas C++ core
cd karkas/server/core
mkdir build && cd build
cmake .. && make -j$(nproc)
cd ../../../..

# Verify installation
python -c "import grisha_bm25; print('BM25 OK')"
python -c "import karkas_engine; print('Karkas OK')"
```

### Using Docker

```bash
cd karkas

# Build and start all services
make build
make run

# View logs
make logs

# Stop services
make stop
```

## Usage

### Grisha Standalone

```bash
# Ingest documents
python3 grisha_ingestor.py brain/

# Interactive query mode
./grisha.sh

# API server (port 8000)
python3 grisha_api.py
```

### Karkas Simulation

```bash
cd karkas

# Start server (connects to PostgreSQL)
make dev

# Or run locally
make run-local

# In another terminal, start client
python client/cli.py
```

### Client Commands

```
┌─────────────────────────────────────────┐
│           KARKAS CLIENT                 │
├─────────────────────────────────────────┤
│  1. View game state                     │
│  2. View my units                       │
│  3. Issue order                         │
│  4. Issue order (natural language)      │
│  5. Mark ready                          │
│  6. View map                            │
│  7. Request Grisha advice               │
│  8. View turn history                   │
│  q. Quit                                │
└─────────────────────────────────────────┘
```

## Configuration

### Grisha (`config.yaml`)

```yaml
model_settings:
  max_tokens: 900          # Chunk size
  overlap_tokens: 150      # Chunk overlap
  model: "llama3.3:70b"    # Ollama model

database_settings:
  path: "./grisha_db"      # ChromaDB location

bm25_settings:
  index_path: "./bm25_index"
  k1: 1.2
  b: 0.75

hybrid_settings:
  enabled: true
  rrf_k: 60.0
  semantic_weight: 0.6
  bm25_weight: 0.4
```

### Karkas (Environment Variables)

```bash
# Server
KARKAS_HOST=0.0.0.0
KARKAS_PORT=8080
KARKAS_DEBUG=false

# Database
KARKAS_DB_HOST=localhost
KARKAS_DB_PORT=5432
KARKAS_DB_NAME=karkas
KARKAS_DB_USER=karkas
KARKAS_DB_PASSWORD=karkas

# Grisha integration
GRISHA_API_URL=http://localhost:8000
GRISHA_ENABLED=true

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.3:70b
```

## API Reference

### Grisha API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/search` | POST | Search doctrine with query, returns ranked contexts |

### Karkas API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/game/state` | GET | Current game state |
| `/api/game/turn` | GET | Current turn info |
| `/api/game/ready` | POST | Mark faction ready |
| `/api/game/execute` | POST | Execute turn (when all ready) |
| `/api/units` | GET | List units (filtered by faction perception) |
| `/api/units/{id}` | GET | Unit details |
| `/api/orders` | POST | Submit order |
| `/api/orders/validate` | POST | Validate order without submitting |
| `/api/orders/parse-natural-language` | POST | Convert text to structured order |
| `/api/scenarios` | GET | List available scenarios |
| `/api/scenarios/{name}/load` | POST | Load scenario |
| `/api/perception/{faction}` | GET | Faction's perceived battlefield |
| `/api/grisha/status` | GET | AI integration status |
| `/ws` | WebSocket | Real-time updates |

## Project Structure

```
grisha/
├── grisha_ingestor.py      # Document ingestion pipeline
├── grisha_query.py         # Interactive query interface
├── grisha_api.py           # FastAPI search endpoint
├── reranker.py             # Multi-signal reranking
├── config.yaml             # Grisha configuration
├── brain/                  # Source documents
│   ├── manuals/           # Field manuals
│   ├── papers/            # Research papers
│   ├── strategy/          # Strategic documents
│   ├── us_doctrine/       # US military doctrine
│   └── wiki/              # Reference material
├── grisha_db/              # ChromaDB vector store
├── bm25_index/             # BM25 keyword index
├── cpp/                    # C++ BM25 module
│   ├── src/
│   │   ├── bm25_index.cpp
│   │   ├── hybrid_search.cpp
│   │   └── porter_stemmer.cpp
│   └── CMakeLists.txt
│
└── karkas/
    ├── server/
    │   ├── api/
    │   │   ├── main.py           # FastAPI application
    │   │   ├── routes/           # API endpoints
    │   │   └── models/           # Pydantic schemas
    │   ├── core/                 # C++ simulation engine
    │   │   ├── simulation.cpp    # Game orchestration
    │   │   ├── unit.cpp          # Unit mechanics
    │   │   ├── orbat_manager.cpp # Force organization
    │   │   ├── terrain/          # GIS terrain engine
    │   │   ├── movement/         # Pathfinding & movement
    │   │   ├── sensors/          # Detection & EW
    │   │   ├── combat/           # Engagement resolution
    │   │   └── logistics/        # Supply & resupply
    │   ├── grisha/               # AI integration
    │   │   ├── commander.py      # Red force AI
    │   │   ├── advisor.py        # Blue force advisor
    │   │   └── order_parser.py   # NL order parsing
    │   └── database/             # PostgreSQL persistence
    ├── client/
    │   └── cli.py               # Command-line client
    ├── data/
    │   ├── scenarios/           # YAML scenario definitions
    │   ├── terrain/             # GeoPackage terrain data
    │   └── doctrine/            # Doctrine documents
    ├── tools/
    │   ├── terrain_processor/   # GIS data pipeline
    │   └── scenario_editor/     # Scenario creation tool
    ├── tests/                   # Test suite
    ├── Dockerfile
    ├── docker-compose.yml
    └── Makefile
```

## Simulation Concepts

### Turn Phases

1. **Planning**: Both sides submit orders simultaneously
2. **Movement**: Units execute movement orders
3. **Detection**: Sensors generate/update contacts
4. **Combat**: Engagements resolved
5. **Logistics**: Supply consumption and resupply
6. **End Turn**: State updates, history recorded

### Order Types

| Order | Description |
|-------|-------------|
| `MOVE` | Move to destination via computed path |
| `ATTACK` | Move to and engage target |
| `DEFEND` | Hold position, engage approaching enemies |
| `SUPPORT` | Provide fire support to another unit |
| `RESUPPLY` | Request/provide logistics support |
| `RECON` | Move with emphasis on detection avoidance |

### Document Classification

| Tier | Priority | Examples |
|------|----------|----------|
| `doctrine_primary` | Highest | Field manuals, regulations |
| `operational_level` | High | Campaign planning docs |
| `tactical_level` | Medium | Battalion/company tactics |
| `technical_specs` | Low | Equipment specifications |
| `general_reference` | Lowest | Wikipedia, general refs |

## Development

### Running Tests

```bash
# Grisha tests
pytest tests/

# Karkas Python tests
cd karkas
pytest tests/

# Karkas C++ tests
cd server/core/build
ctest --output-on-failure

# All tests with coverage
pytest --cov=. --cov-report=html
```

### Code Quality

```bash
cd karkas
make lint    # Run linters
make format  # Auto-format code
```

### Creating Scenarios

```bash
cd karkas/tools/scenario_editor

# Interactive mode
python editor.py

# Create from template
python editor.py create --template cold_war_offensive --name my_scenario

# Validate scenario
python editor.py validate ../../data/scenarios/my_scenario.yaml
```

### Processing Terrain

```bash
cd karkas/tools/terrain_processor

# Download and process terrain for a region
python main.py --region fulda_gap --resolution 100

# Output: data/terrain/fulda_gap.gpkg
```

## Scenarios

### Fulda Gap 1985

Cold War confrontation in the historical Fulda Gap region. Soviet forces attempt breakthrough against NATO defenses.

- **Terrain**: 80x40 km, 100m resolution, 320 MB
- **Forces**: Mechanized divisions with air support
- **Duration**: Multi-day operation

### Tutorial Basics

Learning scenario for new players.

- **Terrain**: 20x30 km simplified terrain
- **Forces**: Reduced company-level units
- **Duration**: Single engagement

## Acknowledgments

- Terrain data: OpenStreetMap, SRTM, ESA WorldCover
- Embeddings: ONNX MiniLM-L6-V2
- Vector store: ChromaDB
- LLM inference: Ollama

## License

MIT License - See [LICENSE](LICENSE) for details.
