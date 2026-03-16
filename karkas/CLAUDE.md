# CLAUDE.md - KARKAS Project Guide

This file provides guidance to Claude Code when working on the KARKAS military simulation platform.

## Project Overview

**KARKAS** is a WEGO-based theater-level military wargame featuring:
- Dual-faction (Red/Blue) gameplay with human or AI control
- C++ high-performance simulation engine with Python FastAPI wrapper
- Grisha RAG integration for AI decision-making using military doctrine
- Real-world GIS terrain with operational (100m) and tactical (10m) resolution
- Fog of war via sensor-based perception

## Current Development Priority

**CORE SIMULATION IS COMPLETE.** The remaining work is:
1. **Production Hardening** - Logging, configuration management, CI/CD
2. **Additional Content** - More scenarios, doctrine documents

## Documentation

- **User Guide**: `docs/USER_GUIDE.md` - Complete user documentation
- **Development Plan**: `DEVELOPMENT_PLAN.md` - Technical roadmap
- **API Docs**: http://localhost:8080/docs (when server running)

---

## Terrain Engine Architecture

### Design Decisions (Finalized)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Map library | **MapLibre GL JS** | Open source, self-hosted, WebGL performance |
| Base map data | **OpenStreetMap** | ODbL license, no usage restrictions |
| Elevation | **SRTM 30m / ALOS 12.5m** | Public domain, global coverage |
| Land cover | **ESA WorldCover 10m** | CC-BY 4.0, recent data (2021) |
| Soil/trafficability | **OpenLandMap** | ODbL, derived soil properties |
| Vector storage | **PostGIS** | Spatial queries, OSM import support |
| Raster storage | **GeoTIFF + custom binary** | GDAL compatible, fast grid access |
| Tile server | **Martin** or **TiTiler** | Vector + raster tile serving |
| Processing | **Python + GDAL/Rasterio** | Rapid development, rich ecosystem |
| Performance-critical | **C++** | LOS, pathfinding, viewshed analysis |

### Resolution Strategy

- **Operational level (100m cells)**: Pre-computed for entire region (Europe + Mediterranean)
- **Tactical level (10m cells)**: Generated on-demand when scenario bounds are defined
- Store both resolutions; operational is always available, tactical is scenario-specific

### Geographic Scope

- **Initial coverage**: Europe and Mediterranean basin
- **Storage estimate**: ~50-100 GB operational, ~25 GB per 100km×100km tactical scenario
- **Expansion planned**: Global coverage in future phases

### Data Bundling

- All terrain data is **bundled locally** (offline-first)
- No runtime network fetches for terrain data
- One-time import from open data sources

### Terrain Cell Data Model

```cpp
// From server/core/terrain/terrain_engine.hpp
struct TerrainCell {
    Coordinates center;
    double elevation_m;
    TerrainType primary_type;

    // Movement
    double get_mobility_cost(MobilityClass mobility) const;

    // Cover & Concealment
    CoverLevel cover;
    double concealment;      // 0-1

    // Urban
    double urban_density;    // 0-1
    uint32_t population;

    // Infrastructure
    bool is_road;
    bool is_bridge;
    bool is_impassable;
};
```

### Derived Military Properties

Raw geodata is transformed into tactical properties:

| Source Data | Derived Property | Usage |
|-------------|------------------|-------|
| Elevation (DEM) | Slope, aspect | LOS, movement cost, defensive value |
| Land cover | Concealment values | Detection probability |
| Buildings | Cover (hard), urban density | Combat modifiers |
| Vegetation | Cover (soft), movement penalty | Concealment, trafficability |
| Roads + soil + slope | Trafficability matrix | Movement planning |
| Hydrology | Water obstacles | Route planning |

### Terrain Processor Pipeline

```
tools/terrain_processor/
├── downloaders/           # Fetch raw open data
│   ├── osm.py            # OpenStreetMap extracts
│   ├── srtm.py           # Elevation tiles
│   ├── worldcover.py     # ESA land cover
│   └── openlandmap.py    # Soil data
├── processors/            # Transform to terrain properties
│   ├── elevation.py      # Slope, aspect computation
│   ├── trafficability.py # Movement cost matrix
│   ├── cover.py          # Concealment/protection values
│   └── urban.py          # Building density analysis
├── tiler.py              # Generate multi-resolution tiles
└── indexer.py            # Spatial index for queries
```

### Analysis Endpoints (Priority Order)

1. **Point query** - Get terrain properties at coordinate
2. **Line-of-sight** - Can observer at A see target at B?
3. **Viewshed** - What area can unit at A observe?
4. **Route planning** - Optimal path for unit mobility class
5. **Trafficability overlay** - Movement cost visualization

---

## Commands

### Building the C++ Core

```bash
cd karkas
mkdir build && cd build
cmake ..
make -j$(nproc)
```

### Running the Server

```bash
cd karkas
./run_server.sh
# Server starts on http://localhost:8080
```

### Running Tests

```bash
# Python tests
cd karkas
pytest tests/

# C++ tests (after build)
cd karkas/build
ctest
```

### Terrain Processing (when implemented)

```bash
# Download raw data for a region
python tools/terrain_processor/downloaders/osm.py --region europe

# Process terrain to operational grid
python tools/terrain_processor/tiler.py --resolution 100 --output data/terrain/operational/

# Generate tactical tiles for scenario
python tools/terrain_processor/tiler.py --resolution 10 --bounds "50.0,8.0,51.0,10.0" --output data/terrain/tactical/
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        KARKAS SERVER                             │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │  Terrain  │  │   ORBAT   │  │   Sim     │  │  Grisha   │    │
│  │  Engine   │  │  Manager  │  │   Core    │  │ Instances │    │
│  │  (C++)    │  │   (C++)   │  │   (C++)   │  │ (Python)  │    │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘    │
│        └──────────────┴──────────────┴──────────────┘          │
│                              │                                   │
│                    ┌─────────┴─────────┐                        │
│                    │ Python Bindings   │                        │
│                    │   (pybind11)      │                        │
│                    └─────────┬─────────┘                        │
│                              │                                   │
│                    ┌─────────┴─────────┐                        │
│                    │   FastAPI Server  │                        │
│                    │  REST + WebSocket │                        │
│                    └─────────┬─────────┘                        │
└──────────────────────────────┼──────────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               │                               │
        ┌──────┴──────┐                 ┌──────┴──────┐
        │ BLUE CLIENT │                 │ RED CLIENT  │
        │  (Human/AI) │                 │  (Human/AI) │
        └─────────────┘                 └─────────────┘
```

---

## Directory Structure

```
karkas/
├── server/
│   ├── core/                    # C++ simulation engine
│   │   ├── terrain/             # Terrain engine (CURRENT FOCUS)
│   │   │   ├── terrain_engine.hpp/cpp
│   │   │   ├── los_calculator.cpp
│   │   │   └── mobility.cpp
│   │   ├── combat/              # Combat resolution
│   │   ├── movement/            # Movement/pathfinding
│   │   ├── sensors/             # Detection model
│   │   ├── logistics/           # Supply model
│   │   ├── types.hpp            # Core type definitions
│   │   ├── unit.hpp/cpp         # Unit class
│   │   ├── orbat_manager.hpp/cpp
│   │   ├── simulation.hpp/cpp
│   │   └── python_bindings.cpp  # pybind11 bindings
│   ├── api/                     # Python FastAPI
│   │   ├── main.py              # Application entry
│   │   ├── routes/              # API endpoints
│   │   └── models/              # Pydantic models
│   └── grisha/                  # AI integration
│       ├── commander.py         # Red force AI
│       ├── advisor.py           # Blue force advisor
│       └── order_parser.py      # NL order parsing
├── client/
│   └── cli.py                   # Command-line client
├── data/
│   ├── terrain/                 # GIS data (to be populated)
│   │   ├── raw/                 # Downloaded source data
│   │   ├── operational/         # 100m pre-computed grids
│   │   └── tactical/            # 10m scenario-specific
│   ├── scenarios/               # Scenario definitions
│   │   └── fulda_gap_1985.yaml
│   └── doctrine/                # Doctrine documents
├── tools/
│   ├── terrain_processor/       # GIS processing (to be built)
│   └── scenario_editor/         # Scenario editing (future)
├── tests/
│   ├── test_api.py
│   └── server/
├── CMakeLists.txt
├── pyproject.toml
├── run_server.sh
├── README.md
└── DEVELOPMENT_PLAN.md          # Full task breakdown
```

---

## Development Status

See `DEVELOPMENT_PLAN.md` for the complete task breakdown. Summary:

| Component | Status |
|-----------|--------|
| Python API Server | ✅ Complete |
| Grisha Integration | ✅ Complete |
| Client CLI | ✅ Complete |
| C++ Type System | ✅ Complete |
| C++ ORBAT Manager | ✅ Complete |
| C++ Terrain Engine | ✅ Complete |
| C++ Movement Resolver | ✅ Complete |
| C++ Sensor Model | ✅ Complete |
| C++ Combat Resolver | ✅ Complete |
| C++ Logistics Model | ✅ Complete |
| Terrain Processor Tool | ✅ Complete |
| Scenario Editor Tool | ✅ Complete |
| C++ & Integration Tests | ✅ Complete |
| Database Persistence | ⏳ Not Started |
| Production Hardening | ⏳ Not Started |

Before stopping code generation and awaiting instructions from the user, you are required to update DEVELOPMENT_PLAN.md to reflect any changes made.

---

## Key Files for Terrain Work

| Purpose | File |
|---------|------|
| Terrain data structures | `server/core/terrain/terrain_engine.hpp` |
| Terrain implementation | `server/core/terrain/terrain_engine.cpp` |
| LOS calculation | `server/core/terrain/los_calculator.cpp` |
| Mobility costs | `server/core/terrain/mobility.cpp` |
| Core types (TerrainType, etc.) | `server/core/types.hpp` |
| Movement integration | `server/core/movement/pathfinder.cpp` |

---

## Data Sources Reference

### OpenStreetMap
- **URL**: https://download.geofabrik.de/
- **Format**: PBF (Protocol Buffer Format)
- **Coverage**: Full Europe extract ~25GB compressed
- **License**: ODbL

### SRTM Elevation
- **URL**: https://dwtkns.com/srtm30m/ or NASA Earthdata
- **Format**: GeoTIFF, 30m resolution
- **Coverage**: 60°N to 60°S (covers all of Europe)
- **License**: Public domain

### ALOS World 3D (higher resolution)
- **URL**: https://www.eorc.jaxa.jp/ALOS/en/aw3d30/
- **Format**: GeoTIFF, 12.5m resolution
- **License**: Free for non-commercial

### ESA WorldCover
- **URL**: https://worldcover2021.esa.int/
- **Format**: GeoTIFF, 10m resolution
- **Classes**: Trees, shrubs, grassland, cropland, built-up, water, etc.
- **License**: CC-BY 4.0

### OpenLandMap (Soil)
- **URL**: https://openlandmap.org/
- **Format**: GeoTIFF
- **Properties**: Soil texture, drainage, organic content
- **License**: ODbL

---

## Coding Conventions

### C++ (server/core/)
- C++20 standard
- Use `#pragma once` for headers
- Namespace: `karkas`
- PIMPL idiom for implementation hiding where appropriate
- GDAL for GIS operations

### Python (server/api/, server/grisha/, tools/)
- Python 3.11+
- Type hints required
- Pydantic for data models
- FastAPI for HTTP endpoints
- asyncio for async operations

### File Naming
- C++: `snake_case.hpp`, `snake_case.cpp`
- Python: `snake_case.py`
- Data: `region_type_resolution.ext` (e.g., `europe_elevation_100m.tif`)

---

## Testing Approach

### Unit Tests
- C++: Google Test (in `tests/server/`)
- Python: pytest (in `tests/`)

### Integration Tests
- End-to-end game flow tests
- Python-C++ binding tests

### Terrain-Specific Tests
- Known point elevation verification
- LOS validation against manual calculations
- Pathfinding correctness tests
- Performance benchmarks for large areas

---

## Common Tasks

### Adding a new terrain query
1. Add method signature to `terrain_engine.hpp`
2. Implement in `terrain_engine.cpp`
3. Add Python binding in `python_bindings.cpp`
4. Add API endpoint in `server/api/routes/` if needed

### Processing terrain for a new region
1. Run downloaders for the region
2. Run processors to compute derived properties
3. Run tiler to generate multi-resolution grids
4. Update config with new region bounds

### Adding a new scenario
1. Create YAML in `data/scenarios/`
2. Define bounds, factions, units, objectives
3. Generate tactical terrain if needed
4. Test scenario loading via API

---

## Dependencies

### C++ Build
- CMake 3.20+
- GDAL library (for GIS operations)
- pybind11 (for Python bindings)
- nlohmann/json (for JSON parsing)
- Google Test (for testing)

### Python Runtime
- FastAPI
- uvicorn
- pydantic
- httpx (for Grisha API calls)
- rasterio (for terrain processing)
- shapely (for geometry operations)

### Terrain Processing
- GDAL/OGR
- Rasterio
- Fiona
- PostGIS (optional, for large vector queries)

---

## Notes for Claude

1. **Always check DEVELOPMENT_PLAN.md** for task dependencies before implementing features
2. **Terrain is the critical path** - most simulation features depend on it
3. **Keep C++ core fast** - avoid unnecessary allocations, use spatial indexing
4. **Test with real data** - use the Fulda Gap scenario as primary test case
5. **Coordinate with Grisha** - terrain analysis feeds into AI decision-making
6. **Prefer existing patterns** - follow conventions in completed components
