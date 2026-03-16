# Grisha + Karkas

**Theater-level military simulation with doctrine-aware AI**

Grisha is a RAG (Retrieval-Augmented Generation) system for military doctrine. Karkas is a WEGO wargame platform that uses Grisha for AI decision-making. Together they create an operational-level simulation where AI commanders make doctrine-informed decisions.

> **[User Guide](USER_GUIDE.md)** - Complete setup instructions, usage examples, and troubleshooting

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
│  │ qwen2.5:14b │    │  │Semantic │  │ Keyword │  │ Multi-signal│  │     │
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
- Ollama with `qwen2.5:14b-instruct-q4_K_M`
- PostgreSQL 16+ with PostGIS 3.4+ (for Karkas)
- CMake 3.20+, C++20 compiler, GDAL (for C++ components)
- tmux (for unified launcher)

### Installation

```bash
# Clone and set up environment
git clone https://github.com/your-username/grisha.git
cd grisha
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install Ollama and pull the model
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:14b-instruct-q4_K_M
```

### Building Your Knowledge Base

**The repository does not include document collections or pre-built vector databases.** You must build your own knowledge base.

Create the `brain/` directory and add your documents:

```bash
mkdir -p brain/manuals
```

**Option 1: Add your own documents**

Place PDF or JSONL files in `brain/` subdirectories, then ingest:

```bash
python3 grisha_ingestor.py brain/
```

**Option 2: Quick test with sample data**

Create a minimal JSONL file for testing:

```bash
cat > brain/manuals/sample.jsonl << 'EOF'
{"text": "The battalion is the basic tactical unit capable of independent operations. It consists of 3-5 companies plus support elements.", "source": "sample", "doc_type": "doctrine_primary", "nation": "RU"}
{"text": "Offensive operations aim to destroy enemy forces and seize terrain. The attacker should achieve 3:1 superiority at the point of main effort.", "source": "sample", "doc_type": "doctrine_primary", "nation": "RU"}
{"text": "Defense in depth employs multiple defensive lines to absorb and defeat enemy attacks. Forward positions trade space for time.", "source": "sample", "doc_type": "doctrine_primary", "nation": "RU"}
EOF

python3 grisha_ingestor.py brain/manuals/sample.jsonl
```

### Running Grisha

```bash
# Interactive query mode
./grisha.sh

# Or run directly
python3 grisha_query.py

# API server (port 8000)
python3 grisha_api.py
```

### Running the Full Stack (Grisha + Karkas)

The unified launcher starts both Grisha API and Karkas Server in a tmux session:

```bash
./karkas.sh      # Start all services
./karkas-stop.sh # Stop all services
```

The launcher:
- Checks prerequisites (venv, Ollama, PostgreSQL, tmux)
- Starts PostgreSQL and Ollama if not running
- Pre-loads the LLM model
- Launches services in a tmux session with split panes
- Waits for health checks before attaching

**tmux controls:**
- `Ctrl-B D` - Detach (services keep running)
- `Ctrl-B ↑/↓` - Switch panes
- `tmux attach -t karkas` - Reattach later

### Running Components Individually

```bash
# Grisha only (interactive)
./grisha.sh

# Karkas only (Docker)
cd karkas && make build && make run

# Karkas only (local)
cd karkas && ./run_server.sh
```

See the [User Guide](USER_GUIDE.md) for complete setup including PostgreSQL, C++ build, and terrain processing.

## Project Structure

```
grisha/
├── karkas.sh               # Unified launcher (Grisha + Karkas)
├── karkas-stop.sh          # Stop all services
├── grisha.sh               # Grisha-only interactive launcher
├── grisha_ingestor.py      # Document ingestion pipeline
├── grisha_query.py         # Interactive query interface
├── grisha_api.py           # FastAPI search endpoint
├── reranker.py             # Multi-signal reranking
├── config.yaml             # Grisha configuration
├── USER_GUIDE.md           # Complete usage documentation
│
├── brain/                  # Source documents (not included - build your own)
│   ├── manuals/           # Field manuals (highest priority)
│   ├── papers/            # Research papers
│   ├── strategy/          # Strategic documents
│   ├── us_doctrine/       # US doctrine (for OPFOR analysis)
│   └── wiki/              # General reference (lowest priority)
│
├── grisha_db/              # ChromaDB vector store (generated by ingestor)
├── bm25_index/             # BM25 keyword index (generated by ingestor)
│
├── cpp/                    # C++ BM25 hybrid search module
│   ├── src/
│   │   ├── bm25_index.cpp
│   │   ├── hybrid_search.cpp
│   │   └── porter_stemmer.cpp
│   └── CMakeLists.txt
│
└── karkas/                 # Military simulation platform
    ├── server/
    │   ├── api/            # FastAPI application
    │   ├── core/           # C++ simulation engine
    │   ├── grisha/         # AI commander/advisor integration
    │   └── database/       # PostgreSQL persistence
    ├── client/             # CLI client
    ├── data/
    │   ├── scenarios/      # YAML scenario definitions
    │   └── terrain/        # GeoPackage terrain data
    ├── tools/
    │   ├── terrain_processor/
    │   └── scenario_editor/
    ├── Dockerfile
    ├── docker-compose.yml
    └── Makefile
```

## Configuration

### Grisha (`config.yaml`)

```yaml
model_settings:
  max_tokens: 900
  overlap_tokens: 150
  model_name: "qwen2.5:14b-instruct-q4_K_M"
  embed_model: "bge-large-en-v1.5"

database_settings:
  path: "./grisha_db"
  collection_name: "grisha_knowledge"

hybrid_settings:
  enabled: true              # Enable after running ingestor
  semantic_weight: 0.5
  bm25_weight: 0.5
```

### Karkas (Environment Variables)

```bash
KARKAS_DB_HOST=localhost
KARKAS_DB_NAME=karkas
GRISHA_API_URL=http://localhost:8000
OLLAMA_MODEL=qwen2.5:14b-instruct-q4_K_M
```

## API Reference

### Grisha

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/search` | POST | Search doctrine, returns ranked contexts |

### Karkas

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/game/state` | GET | Current game state |
| `/api/game/ready` | POST | Mark faction ready |
| `/api/game/execute` | POST | Execute turn |
| `/api/units` | GET | List units |
| `/api/orders` | POST | Submit order |
| `/api/orders/parse-natural-language` | POST | Convert text to structured order |
| `/api/scenarios` | GET | List scenarios |
| `/api/scenarios/{name}/load` | POST | Load scenario |
| `/ws` | WebSocket | Real-time updates |

## Simulation Concepts

### Turn Phases

1. **Planning**: Both sides submit orders simultaneously
2. **Movement**: Units execute movement orders
3. **Detection**: Sensors generate/update contacts
4. **Combat**: Engagements resolved
5. **Logistics**: Supply consumption and resupply

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

```bash
# Run tests
pytest tests/

# Karkas tests
cd karkas && pytest tests/

# C++ tests
cd karkas/server/core/build && ctest --output-on-failure
```

## Documentation

- **[User Guide](USER_GUIDE.md)** - Setup, configuration, and usage
- **[config.yaml](config.yaml)** - Grisha configuration reference

## Acknowledgments

- Terrain data: OpenStreetMap, SRTM, ESA WorldCover
- Embeddings: ONNX MiniLM-L6-V2
- Vector store: ChromaDB
- LLM inference: Ollama (Qwen 2.5)

## License

MIT License - See [LICENSE](LICENSE) for details.
