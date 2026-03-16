#!/usr/bin/env python3
"""
Generate synthetic terrain data for the KARKAS tutorial scenario.

This creates a small, well-designed terrain that teaches players about
terrain effects on combat: hills, forests, roads, and a small village.

Usage:
    python tools/generate_tutorial_terrain.py
    python tools/generate_tutorial_terrain.py --resolution 50
"""

import logging
import math
import sys
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Optional

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Seed for reproducibility (tutorial date: June 15, 2025)
SEED = 20250615


class TerrainType(IntEnum):
    """Terrain type enumeration matching C++ TerrainType."""
    Open = 0
    Forest = 1
    Urban = 2
    Water = 3
    Mountain = 4
    Marsh = 5
    Desert = 6
    Road = 7
    Bridge = 8


class CoverLevel(IntEnum):
    """Cover level enumeration matching C++ CoverLevel."""
    Non = 0
    Light = 1
    Medium = 2
    Heavy = 3
    Fortified = 4


@dataclass
class BoundingBox:
    """Geographic bounding box."""
    south: float
    west: float
    north: float
    east: float


@dataclass
class TerrainCell:
    """Terrain cell data."""
    center_lat: float
    center_lon: float
    elevation_m: float
    primary_type: TerrainType
    secondary_type: Optional[TerrainType]
    cover: CoverLevel
    concealment: float
    urban_density: float
    population: int
    is_road: bool
    is_bridge: bool
    is_impassable: bool
    resolution_m: int


# ═══════════════════════════════════════════════════════════════════════════
# Tutorial Area Design - A well-structured learning environment
# ═══════════════════════════════════════════════════════════════════════════
#
# Layout (approximate):
#
#     North
#       │
#   ┌───┴───────────────────────────────────┐
#   │                                       │
#   │      [Village Bravo]     ▲ Forest     │
#   │          (Urban)        ╱ ╲           │
#   │                        ╱   ╲          │
#   │    ═══════════════════╱═════╲════     │  <-- Main Road
#   │                      ╱       ╲        │
#   │    [Hill 229]       ╱ Stream  ╲       │
#   │      (High)        ╱           ╲      │
#   │                   ╱             ╲     │
#   │    [Crossroads]══╳═══════════════     │
#   │       Alpha                           │
#   │                                       │
#   │         ▼ Blue Start                  │
#   └───────────────────────────────────────┘
#     South
#

# Tutorial terrain features
HILL_229 = {"lat": 50.52, "lon": 9.65, "radius_km": 1.5, "peak_elevation": 380}
VILLAGE_BRAVO = {"lat": 55.55, "lon": 9.70, "radius_km": 0.8, "population": 500, "density": 0.6}
CROSSROADS_ALPHA = {"lat": 50.48, "lon": 9.62}

# Roads in the tutorial area
TUTORIAL_ROADS = [
    # Main east-west road
    [(50.50, 9.50), (50.52, 9.62), (50.54, 9.70), (50.55, 9.75)],
    # North-south road to village
    [(50.48, 9.62), (50.52, 9.65), (50.55, 9.70)],
    # Secondary approach road
    [(50.45, 9.55), (50.48, 9.62)],
]

# Small stream running through the area
STREAM = [
    (50.58, 9.55), (50.54, 9.60), (50.50, 9.65), (50.46, 9.68), (50.42, 9.72),
]

# Forest patches
FOREST_CENTERS = [
    {"lat": 50.56, "lon": 9.63, "radius_km": 1.2, "density": 0.8},
    {"lat": 50.50, "lon": 9.72, "radius_km": 0.8, "density": 0.6},
    {"lat": 50.46, "lon": 9.58, "radius_km": 0.6, "density": 0.7},
]


class TutorialTerrainGenerator:
    """Generate synthetic terrain for the tutorial scenario."""

    def __init__(self, seed: int = SEED):
        np.random.seed(seed)
        self._noise = np.random.rand(64, 64)

    def _sample_noise(self, x: float, y: float) -> float:
        """Sample noise with bilinear interpolation."""
        size = len(self._noise)
        x = max(0, min(1, x)) * (size - 1)
        y = max(0, min(1, y)) * (size - 1)

        x0, y0 = int(x), int(y)
        x1, y1 = min(x0 + 1, size - 1), min(y0 + 1, size - 1)
        fx, fy = x - x0, y - y0

        return (self._noise[y0, x0] * (1 - fx) * (1 - fy) +
                self._noise[y0, x1] * fx * (1 - fy) +
                self._noise[y1, x0] * (1 - fx) * fy +
                self._noise[y1, x1] * fx * fy)

    def _distance_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in kilometers."""
        return math.sqrt(
            ((lat1 - lat2) * 111.0) ** 2 +
            ((lon1 - lon2) * 111.0 * math.cos(math.radians(lat1))) ** 2
        )

    def _distance_to_polyline(self, lat: float, lon: float,
                              line: list[tuple[float, float]]) -> float:
        """Calculate minimum distance from point to polyline in km."""
        min_dist = float('inf')

        for i in range(len(line) - 1):
            lat1, lon1 = line[i]
            lat2, lon2 = line[i + 1]

            dx, dy = lon2 - lon1, lat2 - lat1
            px, py = lon - lon1, lat - lat1

            seg_len_sq = dx * dx + dy * dy
            if seg_len_sq > 0:
                t = max(0, min(1, (px * dx + py * dy) / seg_len_sq))
                closest_lon = lon1 + t * dx
                closest_lat = lat1 + t * dy

                dist = self._distance_km(lat, lon, closest_lat, closest_lon)
                min_dist = min(min_dist, dist)

        return min_dist

    def _get_elevation(self, lat: float, lon: float, bounds: BoundingBox) -> float:
        """Calculate elevation for a point."""
        norm_lat = (lat - bounds.south) / (bounds.north - bounds.south)
        norm_lon = (lon - bounds.west) / (bounds.east - bounds.west)

        # Base elevation with gentle variation
        base = 220 + self._sample_noise(norm_lon, norm_lat) * 40

        # Hill 229 - the main tactical feature
        hill_dist = self._distance_km(lat, lon, HILL_229["lat"], HILL_229["lon"])
        if hill_dist < HILL_229["radius_km"]:
            hill_factor = 1 - (hill_dist / HILL_229["radius_km"]) ** 2
            base += (HILL_229["peak_elevation"] - 220) * hill_factor

        # Gentle slope toward the north
        base += (norm_lat - 0.5) * 30

        # Stream valley depression
        stream_dist = self._distance_to_polyline(lat, lon, STREAM)
        if stream_dist < 0.5:
            base -= (0.5 - stream_dist) * 30

        # Small noise for natural variation
        detail = self._sample_noise(norm_lon * 4, norm_lat * 4)
        base += (detail - 0.5) * 15

        return max(180, min(400, base))

    def _get_terrain_type(self, lat: float, lon: float, elevation: float,
                          bounds: BoundingBox) -> tuple[TerrainType, CoverLevel, float]:
        """Determine terrain type."""
        # Stream water check
        stream_dist = self._distance_to_polyline(lat, lon, STREAM)
        if stream_dist < 0.08:
            return TerrainType.Water, CoverLevel.Non, 0.0

        # Village Bravo urban area
        village_dist = self._distance_km(lat, lon, 50.55, 9.70)  # Corrected coordinates
        if village_dist < 0.8:
            density_factor = 1 - (village_dist / 0.8) ** 0.5
            return TerrainType.Urban, CoverLevel.Medium, 0.6 * density_factor

        # Forest patches
        for forest in FOREST_CENTERS:
            forest_dist = self._distance_km(lat, lon, forest["lat"], forest["lon"])
            if forest_dist < forest["radius_km"]:
                factor = 1 - (forest_dist / forest["radius_km"]) ** 0.5
                if factor > 0.3:
                    return TerrainType.Forest, CoverLevel.Heavy, 0.8 * factor
                elif factor > 0.1:
                    return TerrainType.Forest, CoverLevel.Medium, 0.5 * factor

        # Hill 229 - open terrain with some grass
        hill_dist = self._distance_km(lat, lon, HILL_229["lat"], HILL_229["lon"])
        if hill_dist < HILL_229["radius_km"]:
            return TerrainType.Open, CoverLevel.Light, 0.2

        # Default open terrain
        return TerrainType.Open, CoverLevel.Light, 0.15

    def _check_road(self, lat: float, lon: float) -> tuple[bool, bool]:
        """Check if point is on a road or bridge."""
        for road in TUTORIAL_ROADS:
            road_dist = self._distance_to_polyline(lat, lon, road)
            if road_dist < 0.1:
                # Bridge check - where road crosses stream
                stream_dist = self._distance_to_polyline(lat, lon, STREAM)
                return True, stream_dist < 0.15
        return False, False

    def _get_urban_data(self, lat: float, lon: float) -> tuple[float, int]:
        """Get urban density and population."""
        village_dist = self._distance_km(lat, lon, 50.55, 9.70)
        if village_dist < 0.8:
            factor = 1 - (village_dist / 0.8) ** 0.5
            density = 0.6 * factor
            # Estimate population per cell based on village size
            pop = int(500 / (math.pi * 0.8 ** 2) * 0.01 * factor)
            return density, pop
        return 0.0, 0

    def generate(self, bounds: BoundingBox, resolution_m: int = 100) -> list[TerrainCell]:
        """Generate terrain cells for the tutorial area."""
        logger.info(f"Generating tutorial terrain")
        logger.info(f"Bounds: {bounds.south:.4f},{bounds.west:.4f} to {bounds.north:.4f},{bounds.east:.4f}")
        logger.info(f"Resolution: {resolution_m}m")

        lat_step = resolution_m / 111320
        lon_step = resolution_m / (111320 * math.cos(math.radians((bounds.north + bounds.south) / 2)))

        cells = []
        lat = bounds.south

        while lat < bounds.north:
            lon = bounds.west
            while lon < bounds.east:
                elevation = self._get_elevation(lat, lon, bounds)
                terrain_type, cover, concealment = self._get_terrain_type(lat, lon, elevation, bounds)
                is_road, is_bridge = self._check_road(lat, lon)
                urban_density, population = self._get_urban_data(lat, lon)

                if is_bridge:
                    terrain_type = TerrainType.Bridge
                    cover = CoverLevel.Non
                elif is_road:
                    terrain_type = TerrainType.Road
                    cover = CoverLevel.Non
                    concealment = 0.0

                cell = TerrainCell(
                    center_lat=lat,
                    center_lon=lon,
                    elevation_m=elevation,
                    primary_type=terrain_type,
                    secondary_type=None,
                    cover=cover,
                    concealment=concealment,
                    urban_density=urban_density,
                    population=population,
                    is_road=is_road,
                    is_bridge=is_bridge,
                    is_impassable=False,
                    resolution_m=resolution_m,
                )
                cells.append(cell)

                lon += lon_step
            lat += lat_step

        logger.info(f"Total: {len(cells)} cells")
        return cells


def write_geopackage(cells: list[TerrainCell], output_path: Path,
                     bounds: BoundingBox, resolution_m: int) -> None:
    """Write terrain cells to GeoPackage format."""
    try:
        import geopandas as gpd
        from shapely.geometry import box
    except ImportError:
        logger.error("geopandas and shapely required: pip install geopandas shapely")
        sys.exit(1)

    logger.info(f"Writing {len(cells)} cells to {output_path}")

    records = []
    for cell in cells:
        half_lat = cell.resolution_m / 111320 / 2
        half_lon = half_lat / math.cos(math.radians(cell.center_lat))

        geom = box(
            cell.center_lon - half_lon,
            cell.center_lat - half_lat,
            cell.center_lon + half_lon,
            cell.center_lat + half_lat,
        )

        records.append({
            'geometry': geom,
            'center_lat': cell.center_lat,
            'center_lon': cell.center_lon,
            'elevation_m': cell.elevation_m,
            'primary_type': int(cell.primary_type),
            'secondary_type': int(cell.secondary_type) if cell.secondary_type else None,
            'cover': int(cell.cover),
            'concealment': cell.concealment,
            'urban_density': cell.urban_density,
            'population': cell.population,
            'is_road': int(cell.is_road),
            'is_bridge': int(cell.is_bridge),
            'is_impassable': int(cell.is_impassable),
            'resolution_m': cell.resolution_m,
        })

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_path, layer='terrain_cells', driver='GPKG')

    # Write metadata
    import sqlite3
    import json
    from datetime import datetime

    conn = sqlite3.connect(output_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS terrain_metadata (
            id INTEGER PRIMARY KEY,
            key TEXT UNIQUE,
            value TEXT
        )
    """)

    metadata = {
        'region_name': 'tutorial_area',
        'bounds_south': bounds.south,
        'bounds_west': bounds.west,
        'bounds_north': bounds.north,
        'bounds_east': bounds.east,
        'resolution_m': resolution_m,
        'created_at': datetime.utcnow().isoformat(),
        'source_info': json.dumps({
            'type': 'synthetic',
            'generator': 'TutorialTerrainGenerator',
            'seed': str(SEED),
            'version': '1.0',
            'description': 'Tutorial scenario terrain with Hill 229, Village Bravo, and training features',
        }),
    }

    for key, value in metadata.items():
        cursor.execute(
            "INSERT OR REPLACE INTO terrain_metadata (key, value) VALUES (?, ?)",
            (key, str(value))
        )

    conn.commit()
    conn.close()

    logger.info(f"GeoPackage created: {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate tutorial terrain data")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("data/terrain/tutorial_area.gpkg"),
        help="Output GeoPackage path (default: data/terrain/tutorial_area.gpkg)",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=100,
        help="Cell resolution in meters (default: 100)",
    )

    args = parser.parse_args()

    # Tutorial area bounds (matches scenario definition)
    bounds = BoundingBox(south=50.4, west=9.5, north=50.6, east=9.8)

    generator = TutorialTerrainGenerator(seed=SEED)
    cells = generator.generate(bounds, args.resolution)
    write_geopackage(cells, args.output, bounds, args.resolution)

    # Print statistics
    terrain_counts = {}
    for cell in cells:
        t = cell.primary_type.name
        terrain_counts[t] = terrain_counts.get(t, 0) + 1

    logger.info("")
    logger.info("═══════════════════════════════════════════════════")
    logger.info("           Tutorial Terrain Statistics              ")
    logger.info("═══════════════════════════════════════════════════")
    for terrain, count in sorted(terrain_counts.items(), key=lambda x: -x[1]):
        pct = count / len(cells) * 100
        logger.info(f"  {terrain:12s}: {count:5d} cells ({pct:5.1f}%)")
    logger.info("═══════════════════════════════════════════════════")

    # Print key features
    logger.info("")
    logger.info("Key terrain features:")
    logger.info(f"  Hill 229:         {HILL_229['lat']:.2f}°N, {HILL_229['lon']:.2f}°E (elevation ~{HILL_229['peak_elevation']}m)")
    logger.info(f"  Village Bravo:    50.55°N, 9.70°E")
    logger.info(f"  Crossroads Alpha: 50.48°N, 9.62°E")


if __name__ == "__main__":
    main()
