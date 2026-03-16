# KARKAS - Theater-Level Military Simulation Platform

KARKAS is a WEGO-based military simulation platform for theater-level operations featuring dual-player (Red/Blue) gameplay with human or AI (Grisha) control.

## Features

- **WEGO Turn System**: Simultaneous planning, sequential execution
- **Dual Factions**: Red (Warsaw Pact/Russia) and Blue (NATO) forces
- **AI Integration**: Grisha RAG system for autonomous Red commander and Blue advisor
- **Fog of War**: Sensor-based intelligence with contact degradation
- **Doctrinally Accurate**: Combat resolution based on military doctrine
- **Natural Language Orders**: Issue orders in plain language, parsed to structured commands
- **High-Resolution Terrain**: GIS-based terrain with elevation, land cover, and urban data

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        KARKAS SERVER                             │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │  Terrain  │  │   ORBAT   │  │   Sim     │  │  Grisha   │    │
│  │  Engine   │  │  Manager  │  │   Core    │  │ Instances │    │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘    │
│        └──────────────┴──────────────┴──────────────┘          │
│                              │                                   │
│                    ┌─────────┴─────────┐                        │
│                    │   Game State      │                        │
│                    │   Manager         │                        │
│                    └─────────┬─────────┘                        │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         │                    │                    │             │
│  ┌──────┴──────┐    ┌────────┴────────┐   ┌──────┴──────┐      │
│  │Ground Truth │    │   Perception    │   │   Order     │      │
│  │   State     │    │   Generator     │   │  Processor  │      │
│  └─────────────┘    └─────────────────┘   └─────────────┘      │
└─────────────────────────────┬───────────────────────────────────┘
                              │ WebSocket/REST
              ┌───────────────┴───────────────┐
              │                               │
       ┌──────┴──────┐                 ┌──────┴──────┐
       │ BLUE CLIENT │                 │ RED CLIENT  │
       │  (Human or  │                 │  (Human or  │
       │   Grisha)   │                 │   Grisha)   │
       └─────────────┘                 └─────────────┘
```

## Quick Start

### Option 1: Docker (Recommended)

The easiest way to run KARKAS is with Docker:

```bash
# Clone and navigate to the project
cd karkas

# Copy environment file and customize if needed
cp .env.example .env

# Build and start all services
make build
make run

# View logs
make logs
```

This starts:
- KARKAS server on `http://localhost:8080`
- PostgreSQL/PostGIS database on `localhost:5433`

API documentation is available at `http://localhost:8080/docs`.

#### Docker Commands

```bash
make build      # Build Docker images
make run        # Start all services
make stop       # Stop all services
make logs       # View server logs
make shell      # Open shell in server container
make db-shell   # Open psql shell in database
make clean      # Stop and remove all data
```

#### Development with Docker

```bash
# Start with hot reload (mounts source code)
make dev
```

### Option 2: Local Development

#### Prerequisites

- C++ compiler with C++20 support
- CMake 3.20+
- GDAL library
- PostgreSQL with PostGIS (optional)
- Python 3.11+
- Ollama (for AI features)

#### Building the C++ Core

```bash
cd karkas
mkdir build && cd build
cmake ..
make -j$(nproc)
```

#### Running the Python API Server

```bash
cd karkas
pip install -e .
karkas-server
```

The server will start on `http://localhost:8080`.

### Running a Scenario

1. Start the server
2. Load a scenario via the API or client
3. Submit orders for each faction
4. Execute turns

## API Endpoints

### Game Control

- `GET /` - Server info
- `GET /health` - Health check
- `GET /api/game/state` - Current game state
- `POST /api/game/ready/{faction}` - Mark faction ready
- `POST /api/game/execute` - Execute turn

### Units

- `GET /api/units` - List all units
- `GET /api/units/{id}` - Get specific unit
- `POST /api/units` - Create unit
- `PUT /api/units/{id}` - Update unit

### Orders

- `GET /api/orders` - List orders
- `POST /api/orders` - Create order
- `POST /api/orders/validate` - Validate order
- `POST /api/orders/parse-natural-language` - Parse NL order

### Scenarios

- `GET /api/scenarios` - List scenarios
- `GET /api/scenarios/{id}` - Get scenario details
- `POST /api/scenarios/{id}/load` - Load scenario

### Grisha AI

- `GET /api/grisha/status` - AI status
- `POST /api/grisha/enable/{faction}` - Enable AI
- `POST /api/grisha/disable/{faction}` - Disable AI

### WebSocket

- `ws://localhost:8080/ws` - Real-time updates

## Turn Structure (WEGO)

1. **Planning Phase** (simultaneous)
   - Both sides issue orders
   - Orders validated and queued

2. **Execution Phase** (server-side)
   - Movement resolution
   - Detection/sensor updates
   - Combat resolution
   - Logistics consumption
   - Morale/fatigue updates

3. **Reporting Phase**
   - Generate perception state for each side
   - Push updates to clients

## Configuration

Scenarios are defined in YAML format. See `data/scenarios/fulda_gap_1985.yaml` for an example.

## Grisha Integration

KARKAS integrates with the Grisha RAG system for AI decision-making:

- **Red Commander**: Autonomous decision-making using Soviet/Russian doctrine
- **Blue Advisor**: Advisory support for human players using NATO doctrine
- **Order Parser**: Natural language to structured order conversion

## Directory Structure

```
karkas/
├── server/
│   ├── core/           # C++ simulation engine
│   │   ├── terrain/    # Terrain engine
│   │   ├── combat/     # Combat resolution
│   │   ├── movement/   # Movement resolution
│   │   └── sensors/    # Sensor/detection model
│   ├── api/            # Python FastAPI
│   │   ├── routes/     # API endpoints
│   │   └── models/     # Pydantic models
│   └── grisha/         # Grisha integration
├── client/             # Client application (future)
├── data/
│   ├── terrain/        # GIS data
│   ├── scenarios/      # Scenario definitions
│   └── doctrine/       # Doctrine documents
├── tools/              # Development tools
└── tests/              # Test suite
```

## Documentation

- **[User Guide](docs/USER_GUIDE.md)** - Complete guide for installation, configuration, and gameplay
- **[Development Plan](DEVELOPMENT_PLAN.md)** - Technical roadmap and task tracking
- **[API Documentation](http://localhost:8080/docs)** - Interactive API reference (when server is running)

## License

MIT License

## Contributing

Contributions welcome. Please open an issue to discuss major changes.
