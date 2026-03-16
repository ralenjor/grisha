#!/usr/bin/env python3
"""
Standalone script to generate Fulda Gap terrain data.

This generates synthetic terrain data for development/testing without
requiring external GIS data downloads.

Usage:
    python tools/generate_fulda_terrain.py
    python tools/generate_fulda_terrain.py --output data/terrain/custom.gpkg
    python tools/generate_fulda_terrain.py --resolution 50  # Higher detail
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

# Seed for reproducibility (scenario date: August 15, 1985)
SEED = 19850815


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


@dataclass
class CityLocation:
    """Known city location."""
    name: str
    lat: float
    lon: float
    radius_km: float
    population: int
    urban_density: float


# Major cities and towns in the Fulda Gap region
FULDA_GAP_CITIES = [
    CityLocation("Fulda", 50.5528, 9.6757, 4.0, 68000, 0.7),
    CityLocation("Bad Hersfeld", 50.8686, 9.7064, 2.5, 30000, 0.5),
    CityLocation("Schluchtern", 50.3486, 9.5253, 1.5, 10000, 0.4),
    CityLocation("Hunfeld", 50.6747, 9.7669, 1.2, 7000, 0.3),
    CityLocation("Lauterbach", 50.6375, 9.3961, 1.5, 14000, 0.4),
    CityLocation("Alsfeld", 50.7514, 9.2714, 1.5, 16000, 0.4),
    CityLocation("Bebra", 50.9722, 9.7900, 1.5, 14000, 0.4),
    CityLocation("Rotenburg", 50.9983, 9.7283, 1.5, 12000, 0.35),
    CityLocation("Gelnhausen", 50.2014, 9.1878, 2.0, 23000, 0.5),
    CityLocation("Hanau", 50.1264, 8.9231, 4.0, 97000, 0.7),
]

# Major road corridors (approximate polylines)
MAJOR_ROADS = [
    # A66 / E40 corridor (west-east through Fulda)
    [(50.12, 8.9), (50.25, 9.2), (50.40, 9.5), (50.55, 9.68)],
    # A7 corridor (north-south)
    [(50.0, 9.5), (50.3, 9.55), (50.55, 9.68), (50.87, 9.71), (51.0, 9.75)],
    # A4 corridor (northern route)
    [(50.9, 9.2), (50.95, 9.5), (51.0, 9.8)],
    # Secondary roads
    [(50.55, 9.68), (50.64, 9.40), (50.75, 9.27)],
    [(50.87, 9.71), (50.97, 9.79)],
]

# Fulda River approximate path
FULDA_RIVER = [
    (50.0, 9.62), (50.1, 9.60), (50.2, 9.58), (50.3, 9.55),
    (50.4, 9.60), (50.55, 9.68), (50.7, 9.70), (50.87, 9.71),
    (50.95, 9.72), (51.0, 9.73),
]


class SyntheticTerrainGenerator:
    """Generate synthetic terrain data for a region."""

    def __init__(self, seed: int = SEED):
        np.random.seed(seed)
        self._elevation_noise = np.random.rand(256, 256)
        self._forest_noise = np.random.rand(128, 128)
        self._detail_noise = np.random.rand(64, 64)

    def _sample_noise(self, table: np.ndarray, x: float, y: float) -> float:
        """Sample noise with bilinear interpolation."""
        size = len(table)
        x = max(0, min(1, x)) * (size - 1)
        y = max(0, min(1, y)) * (size - 1)

        x0, y0 = int(x), int(y)
        x1, y1 = min(x0 + 1, size - 1), min(y0 + 1, size - 1)
        fx, fy = x - x0, y - y0

        # Smoothstep
        fx = fx * fx * (3 - 2 * fx)
        fy = fy * fy * (3 - 2 * fy)

        return (table[y0, x0] * (1 - fx) * (1 - fy) +
                table[y0, x1] * fx * (1 - fy) +
                table[y1, x0] * (1 - fx) * fy +
                table[y1, x1] * fx * fy)

    def _multi_octave_noise(self, x: float, y: float, table: np.ndarray,
                            octaves: int = 4, persistence: float = 0.5) -> float:
        """Multi-octave noise for natural terrain."""
        total = 0.0
        amplitude = 1.0
        frequency = 1.0
        max_value = 0.0

        for _ in range(octaves):
            total += self._sample_noise(table, x * frequency, y * frequency) * amplitude
            max_value += amplitude
            amplitude *= persistence
            frequency *= 2

        return total / max_value

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

                dist = math.sqrt(
                    ((lat - closest_lat) * 111.0) ** 2 +
                    ((lon - closest_lon) * 111.0 * math.cos(math.radians(lat))) ** 2
                )
                min_dist = min(min_dist, dist)

        return min_dist

    def _get_elevation(self, lat: float, lon: float, bounds: BoundingBox) -> float:
        """Calculate elevation for a point."""
        norm_lat = (lat - bounds.south) / (bounds.north - bounds.south)
        norm_lon = (lon - bounds.west) / (bounds.east - bounds.west)

        base = self._multi_octave_noise(norm_lon, norm_lat, self._elevation_noise, 5, 0.5)

        # Vogelsberg (west)
        vogelsberg_dist = math.sqrt(
            ((lat - 50.5) * 111) ** 2 +
            ((lon - 9.2) * 111 * math.cos(math.radians(lat))) ** 2
        )
        vogelsberg = max(0, 1 - vogelsberg_dist / 40) * 250

        # Rhon mountains (east)
        rhon_dist = math.sqrt(
            ((lat - 50.4) * 111) ** 2 +
            ((lon - 10.0) * 111 * math.cos(math.radians(lat))) ** 2
        )
        rhon = max(0, 1 - rhon_dist / 35) * 350

        # River valley
        river_dist = self._distance_to_polyline(lat, lon, FULDA_RIVER)
        river_depression = max(0, 1 - river_dist / 5) * 80

        elevation = 200 + base * 200 + vogelsberg + rhon - river_depression

        detail = self._sample_noise(self._detail_noise, norm_lon * 4, norm_lat * 4)
        elevation += (detail - 0.5) * 30

        return max(150, min(750, elevation))

    def _get_terrain_type(self, lat: float, lon: float, elevation: float,
                          bounds: BoundingBox) -> tuple[TerrainType, CoverLevel, float]:
        """Determine terrain type."""
        norm_lat = (lat - bounds.south) / (bounds.north - bounds.south)
        norm_lon = (lon - bounds.west) / (bounds.east - bounds.west)

        # Water check
        river_dist = self._distance_to_polyline(lat, lon, FULDA_RIVER)
        if river_dist < 0.15:
            return TerrainType.Water, CoverLevel.Non, 0.0

        # Urban check
        for city in FULDA_GAP_CITIES:
            city_dist = math.sqrt(
                ((lat - city.lat) * 111) ** 2 +
                ((lon - city.lon) * 111 * math.cos(math.radians(lat))) ** 2
            )
            if city_dist < city.radius_km:
                density_factor = 1 - (city_dist / city.radius_km) ** 0.5
                return TerrainType.Urban, CoverLevel.Medium, 0.6 * density_factor

        # Forest probability
        forest_noise = self._multi_octave_noise(norm_lon * 2, norm_lat * 2, self._forest_noise, 3)
        elevation_bias = (elevation - 250) / 400
        forest_prob = forest_noise * 0.6 + max(0, elevation_bias) * 0.4

        detail = self._sample_noise(self._detail_noise, norm_lon * 8, norm_lat * 8)
        if detail > 0.7 and elevation > 350:
            forest_prob += 0.2

        if forest_prob > 0.55:
            return TerrainType.Forest, CoverLevel.Heavy, 0.8
        elif forest_prob > 0.40:
            return TerrainType.Forest, CoverLevel.Medium, 0.5

        if elevation > 550:
            return TerrainType.Open, CoverLevel.Light, 0.15
        elif river_dist < 2:
            return TerrainType.Open, CoverLevel.Non, 0.1
        else:
            return TerrainType.Open, CoverLevel.Light, 0.2

    def _check_road(self, lat: float, lon: float) -> tuple[bool, bool]:
        """Check if point is on a road or bridge."""
        for road in MAJOR_ROADS:
            if self._distance_to_polyline(lat, lon, road) < 0.15:
                river_dist = self._distance_to_polyline(lat, lon, FULDA_RIVER)
                return True, river_dist < 0.3
        return False, False

    def _get_urban_data(self, lat: float, lon: float) -> tuple[float, int]:
        """Get urban density and population."""
        for city in FULDA_GAP_CITIES:
            city_dist = math.sqrt(
                ((lat - city.lat) * 111) ** 2 +
                ((lon - city.lon) * 111 * math.cos(math.radians(lat))) ** 2
            )
            if city_dist < city.radius_km:
                factor = 1 - (city_dist / city.radius_km) ** 0.5
                density = city.urban_density * factor
                city_area = math.pi * city.radius_km ** 2
                pop = int(city.population / city_area * 0.01 * factor)
                return density, pop
        return 0.0, 0

    def generate(self, bounds: BoundingBox, resolution_m: int = 100) -> list[TerrainCell]:
        """Generate terrain cells for a region."""
        logger.info(f"Bounds: {bounds.south:.4f},{bounds.west:.4f} to {bounds.north:.4f},{bounds.east:.4f}")
        logger.info(f"Resolution: {resolution_m}m")

        lat_step = resolution_m / 111320
        lon_step = resolution_m / (111320 * math.cos(math.radians((bounds.north + bounds.south) / 2)))

        cells = []
        lat = bounds.south
        count = 0

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
                    is_impassable=elevation > 700,
                    resolution_m=resolution_m,
                )
                cells.append(cell)
                count += 1

                lon += lon_step
            lat += lat_step

            if count % 50000 == 0:
                logger.info(f"Generated {count} cells...")

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
        'region_name': 'fulda_gap',
        'bounds_south': bounds.south,
        'bounds_west': bounds.west,
        'bounds_north': bounds.north,
        'bounds_east': bounds.east,
        'resolution_m': resolution_m,
        'created_at': datetime.utcnow().isoformat(),
        'source_info': json.dumps({
            'type': 'synthetic',
            'generator': 'SyntheticTerrainGenerator',
            'seed': str(SEED),
            'version': '1.0',
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

    parser = argparse.ArgumentParser(description="Generate Fulda Gap terrain data")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("data/terrain/fulda_gap.gpkg"),
        help="Output GeoPackage path (default: data/terrain/fulda_gap.gpkg)",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=100,
        help="Cell resolution in meters (default: 100)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Generate smaller test region (20x20 km)",
    )

    args = parser.parse_args()

    if args.test:
        bounds = BoundingBox(south=50.4, west=9.4, north=50.6, east=9.6)
        logger.info("Generating test region (20x20 km)")
    else:
        bounds = BoundingBox(south=50.0, west=9.0, north=51.0, east=10.5)
        logger.info("Generating full Fulda Gap region (111x111 km)")

    generator = SyntheticTerrainGenerator(seed=SEED)
    cells = generator.generate(bounds, args.resolution)
    write_geopackage(cells, args.output, bounds, args.resolution)

    # Print statistics
    terrain_counts = {}
    for cell in cells:
        t = cell.primary_type.name
        terrain_counts[t] = terrain_counts.get(t, 0) + 1

    logger.info("Terrain distribution:")
    for terrain, count in sorted(terrain_counts.items(), key=lambda x: -x[1]):
        pct = count / len(cells) * 100
        logger.info(f"  {terrain}: {count} ({pct:.1f}%)")


if __name__ == "__main__":
    main()
