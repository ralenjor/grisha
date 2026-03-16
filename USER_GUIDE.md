# Grisha + Karkas User Guide

This guide covers how to set up, configure, and use the Grisha RAG system and Karkas military simulation platform.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Building Your Knowledge Base](#building-your-knowledge-base)
3. [Using Grisha](#using-grisha)
4. [Using Karkas](#using-karkas)
5. [Configuration Reference](#configuration-reference)
6. [Troubleshooting](#troubleshooting)

---

## Getting Started

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 16 GB | 32 GB |
| Storage | 10 GB | 50 GB (with terrain data) |
| GPU | Not required | NVIDIA GPU for faster inference |
| OS | Linux (tested on Fedora) | Linux |

**Required tools:**
- Python 3.11+
- Ollama
- tmux (for unified launcher)
- PostgreSQL with PostGIS (for Karkas persistence)

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

# Build the C++ BM25 module (optional, for hybrid search)
cd cpp
pip install pybind11 scikit-build-core
pip install -e .
cd ..

# Verify installation
python -c "import chromadb; print('ChromaDB OK')"
python -c "import grisha_bm25; print('BM25 OK')"  # Only if you built it
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
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "battalion attack formation", "top_k": 5}'
```

Response:

```json
{
  "results": [
    {
      "text": "The battalion attacks in two echelons...",
      "source": "FM 100-2-1",
      "score": 0.89,
      "doc_type": "doctrine_primary"
    }
  ]
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

# Install PostgreSQL with PostGIS
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
# Karkas only (Docker)
cd karkas
make build
make run

# Karkas only (local)
cd karkas
./run_server.sh

# Or manually
export KARKAS_DB_HOST=localhost
export KARKAS_DB_PASSWORD=karkas
python -m uvicorn server.api.main:app --reload
```

### Using the Client

```bash
cd karkas
python client/cli.py
```

Client interface:

```
╔══════════════════════════════════════════════════════════════╗
║                      KARKAS CLIENT                           ║
╠══════════════════════════════════════════════════════════════╣
║  1. View game state                                          ║
║  2. View my units                                            ║
║  3. Issue order                                              ║
║  4. Issue order (natural language)                           ║
║  5. Mark ready for next turn                                 ║
║  6. View map                                                 ║
║  7. Request Grisha advice                                    ║
║  8. View turn history                                        ║
║  q. Quit                                                     ║
╚══════════════════════════════════════════════════════════════╝
```

### Loading a Scenario

```bash
# Via client menu, or via API:
curl -X POST http://localhost:8080/api/scenarios/tutorial_basics/load
```

### Issuing Orders

**Structured order:**

```bash
curl -X POST http://localhost:8080/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "unit_id": "1btn-1mrr",
    "order_type": "MOVE",
    "destination": {"x": 5000, "y": 3000},
    "route_preference": "COVERED"
  }'
```

**Natural language order:**

```bash
curl -X POST http://localhost:8080/api/orders/parse-natural-language \
  -H "Content-Type: application/json" \
  -d '{
    "text": "First battalion move to hill 305 using covered routes, avoid enemy contact"
  }'
```

### Turn Execution

1. Both sides submit orders
2. Both sides mark ready: `POST /api/game/ready`
3. Execute turn: `POST /api/game/execute`
4. View results in turn history

### AI Commanders

Enable Grisha AI for Red force:

```bash
curl -X POST http://localhost:8080/api/grisha/enable
```

The AI commander (Colonel Petrov) will automatically generate orders for Red units based on doctrine queries to Grisha.

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

# Grisha Integration
GRISHA_API_URL=http://localhost:8000
GRISHA_ENABLED=true

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b-instruct-q4_K_M
```

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

---

## Next Steps

- Add more documents to `brain/` for richer responses
- Create custom scenarios with the scenario editor
- Process terrain for new regions
- Integrate with external systems via the REST APIs
