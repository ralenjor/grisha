#!/usr/bin/env python3
"""
Synthetic Terrain Generator for KARKAS.

Generates procedural terrain data for testing and development when real GIS
data is not available. Produces GeoPackage files compatible with the C++
terrain engine.

The Fulda Gap region characteristics:
- Elevation: Rolling hills between 150-600m, valleys along rivers
- Terrain: Mix of agricultural land (40%), forest on hills (35%), urban (10%), other (15%)
- Key cities: Fulda (50.55°N, 9.68°E), Bad Hersfeld (50.87°N, 9.71°E)
- Rivers: Fulda River running north-south
- Strategic corridor: Low terrain between Vogelsberg and Rhon mountains
"""

import logging
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from .models import TerrainType, CoverLevel, TerrainCell, BoundingBox

logger = logging.getLogger(__name__)

# Seed for reproducibility
SEED = 19850815  # Scenario date


@dataclass
class CityLocation:
    """Known city location for terrain generation."""
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

# Major road corridors (approximate lines)
MAJOR_ROADS = [
    # A66 / E40 corridor (west-east through Fulda)
    [(50.12, 8.9), (50.25, 9.2), (50.40, 9.5), (50.55, 9.68)],
    # A7 corridor (north-south)
    [(50.0, 9.5), (50.3, 9.55), (50.55, 9.68), (50.87, 9.71), (51.0, 9.75)],
    # A4 corridor (northern route)
    [(50.9, 9.2), (50.95, 9.5), (51.0, 9.8)],
    # Secondary roads
    [(50.55, 9.68), (50.64, 9.40), (50.75, 9.27)],  # Fulda to Alsfeld
    [(50.87, 9.71), (50.97, 9.79)],  # Bad Hersfeld to Bebra
]

# Fulda River approximate path
FULDA_RIVER = [
    (50.0, 9.62), (50.1, 9.60), (50.2, 9.58), (50.3, 9.55),
    (50.4, 9.60), (50.55, 9.68), (50.7, 9.70), (50.87, 9.71),
    (50.95, 9.72), (51.0, 9.73),
]


class SyntheticTerrainGenerator:
    """
    Generate synthetic terrain data for a region.

    Uses Perlin-like noise combined with geographic features to create
    realistic terrain for wargame simulations.
    """

    def __init__(self, seed: int = SEED):
        """
        Initialize the generator.

        Args:
            seed: Random seed for reproducibility
        """
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

        # Pre-generate noise tables for terrain features
        self._elevation_noise = self._generate_noise_table(256)
        self._forest_noise = self._generate_noise_table(128)
        self._detail_noise = self._generate_noise_table(64)

    def _generate_noise_table(self, size: int) -> np.ndarray:
        """Generate a gradient noise table."""
        return np.random.rand(size, size)

    def _sample_noise(self, table: np.ndarray, x: float, y: float) -> float:
        """
        Sample noise from table with bilinear interpolation.

        Args:
            table: Noise table
            x, y: Normalized coordinates (0-1)

        Returns:
            Interpolated noise value (0-1)
        """
        size = len(table)
        x = x * (size - 1)
        y = y * (size - 1)

        x0 = int(x)
        y0 = int(y)
        x1 = min(x0 + 1, size - 1)
        y1 = min(y0 + 1, size - 1)

        fx = x - x0
        fy = y - y0

        # Smoothstep interpolation
        fx = fx * fx * (3 - 2 * fx)
        fy = fy * fy * (3 - 2 * fy)

        v00 = table[y0, x0]
        v10 = table[y0, x1]
        v01 = table[y1, x0]
        v11 = table[y1, x1]

        return (v00 * (1 - fx) * (1 - fy) +
                v10 * fx * (1 - fy) +
                v01 * (1 - fx) * fy +
                v11 * fx * fy)

    def _multi_octave_noise(
        self,
        x: float,
        y: float,
        table: np.ndarray,
        octaves: int = 4,
        persistence: float = 0.5,
    ) -> float:
        """
        Generate multi-octave noise for more natural terrain.

        Args:
            x, y: Normalized coordinates
            table: Base noise table
            octaves: Number of noise octaves
            persistence: Amplitude decay per octave

        Returns:
            Noise value (0-1)
        """
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

    def _distance_to_line_segment(
        self,
        lat: float,
        lon: float,
        line: list[tuple[float, float]],
    ) -> float:
        """
        Calculate minimum distance from point to polyline in km.

        Args:
            lat, lon: Point coordinates
            line: List of (lat, lon) points forming the line

        Returns:
            Distance in kilometers
        """
        min_dist = float('inf')

        for i in range(len(line) - 1):
            lat1, lon1 = line[i]
            lat2, lon2 = line[i + 1]

            # Vector from p1 to p2
            dx = lon2 - lon1
            dy = lat2 - lat1

            # Vector from p1 to point
            px = lon - lon1
            py = lat - lat1

            # Project point onto line segment
            seg_len_sq = dx * dx + dy * dy
            if seg_len_sq > 0:
                t = max(0, min(1, (px * dx + py * dy) / seg_len_sq))

                # Closest point on segment
                closest_lon = lon1 + t * dx
                closest_lat = lat1 + t * dy

                # Distance in approximate km
                dist = math.sqrt(
                    ((lat - closest_lat) * 111.0) ** 2 +
                    ((lon - closest_lon) * 111.0 * math.cos(math.radians(lat))) ** 2
                )
                min_dist = min(min_dist, dist)

        return min_dist

    def _get_elevation(self, lat: float, lon: float, bounds: BoundingBox) -> float:
        """
        Calculate elevation for a point.

        Fulda Gap terrain features:
        - Vogelsberg volcanic plateau to the west (high elevation)
        - Rhon mountains to the east (high elevation)
        - Low corridor through the middle (the "gap")
        - River valleys lower than surroundings

        Args:
            lat, lon: Point coordinates
            bounds: Region bounds for normalization

        Returns:
            Elevation in meters
        """
        # Normalize coordinates
        norm_lat = (lat - bounds.south) / (bounds.north - bounds.south)
        norm_lon = (lon - bounds.west) / (bounds.east - bounds.west)

        # Base elevation from noise
        base_elevation = self._multi_octave_noise(
            norm_lon, norm_lat, self._elevation_noise, octaves=5, persistence=0.5
        )

        # Regional elevation features
        # Vogelsberg (west side, centered around 50.5°N, 9.2°E)
        vogelsberg_dist = math.sqrt(
            ((lat - 50.5) * 111) ** 2 +
            ((lon - 9.2) * 111 * math.cos(math.radians(lat))) ** 2
        )
        vogelsberg_influence = max(0, 1 - vogelsberg_dist / 40) * 250

        # Rhon mountains (east side, around 50.4°N, 10.0°E)
        rhon_dist = math.sqrt(
            ((lat - 50.4) * 111) ** 2 +
            ((lon - 10.0) * 111 * math.cos(math.radians(lat))) ** 2
        )
        rhon_influence = max(0, 1 - rhon_dist / 35) * 350

        # River valley depression
        river_dist = self._distance_to_line_segment(lat, lon, FULDA_RIVER)
        river_depression = max(0, 1 - river_dist / 5) * 80

        # Combine: base terrain + hills - river valleys
        elevation = (
            200 +  # Base elevation
            base_elevation * 200 +  # Noise variation (0-200m)
            vogelsberg_influence +
            rhon_influence -
            river_depression
        )

        # Add fine detail
        detail = self._sample_noise(self._detail_noise, norm_lon * 4, norm_lat * 4)
        elevation += (detail - 0.5) * 30

        return max(150, min(750, elevation))

    def _get_terrain_type(
        self,
        lat: float,
        lon: float,
        elevation: float,
        bounds: BoundingBox,
    ) -> tuple[TerrainType, CoverLevel, float]:
        """
        Determine terrain type based on location and elevation.

        Args:
            lat, lon: Point coordinates
            elevation: Elevation in meters
            bounds: Region bounds

        Returns:
            Tuple of (terrain_type, cover_level, concealment)
        """
        # Normalize coordinates
        norm_lat = (lat - bounds.south) / (bounds.north - bounds.south)
        norm_lon = (lon - bounds.west) / (bounds.east - bounds.west)

        # Check for water (river proximity)
        river_dist = self._distance_to_line_segment(lat, lon, FULDA_RIVER)
        if river_dist < 0.15:  # Within 150m of river
            return TerrainType.Water, CoverLevel.Non, 0.0

        # Check for urban (city proximity)
        for city in FULDA_GAP_CITIES:
            city_dist = math.sqrt(
                ((lat - city.lat) * 111) ** 2 +
                ((lon - city.lon) * 111 * math.cos(math.radians(lat))) ** 2
            )
            if city_dist < city.radius_km:
                # Urban density falls off from center
                density_factor = 1 - (city_dist / city.radius_km) ** 0.5
                return TerrainType.Urban, CoverLevel.Medium, 0.6 * density_factor

        # Forest noise
        forest_noise = self._multi_octave_noise(
            norm_lon * 2, norm_lat * 2, self._forest_noise, octaves=3
        )

        # Higher elevations more likely to be forested
        elevation_forest_bias = (elevation - 250) / 400  # 0 at 250m, 1 at 650m
        forest_probability = forest_noise * 0.6 + max(0, elevation_forest_bias) * 0.4

        # Steeper slopes more likely forested (approximated by elevation variation)
        detail = self._sample_noise(self._detail_noise, norm_lon * 8, norm_lat * 8)
        if detail > 0.7 and elevation > 350:
            forest_probability += 0.2

        if forest_probability > 0.55:
            return TerrainType.Forest, CoverLevel.Heavy, 0.8
        elif forest_probability > 0.40:
            return TerrainType.Forest, CoverLevel.Medium, 0.5

        # Remaining terrain is mostly agricultural/open
        if elevation > 550:
            # High elevation = mountain meadows
            return TerrainType.Open, CoverLevel.Light, 0.15
        elif river_dist < 2:
            # Near river = floodplain meadows
            return TerrainType.Open, CoverLevel.Non, 0.1
        else:
            # Cropland
            return TerrainType.Open, CoverLevel.Light, 0.2

    def _check_road(self, lat: float, lon: float) -> tuple[bool, bool]:
        """
        Check if point is near a road or bridge.

        Args:
            lat, lon: Point coordinates

        Returns:
            Tuple of (is_road, is_bridge)
        """
        for road in MAJOR_ROADS:
            road_dist = self._distance_to_line_segment(lat, lon, road)
            if road_dist < 0.15:  # Within 150m of road
                # Check if also near river (= bridge)
                river_dist = self._distance_to_line_segment(lat, lon, FULDA_RIVER)
                is_bridge = river_dist < 0.3
                return True, is_bridge

        return False, False

    def _get_urban_data(
        self,
        lat: float,
        lon: float,
    ) -> tuple[float, int]:
        """
        Get urban density and population for a cell.

        Args:
            lat, lon: Point coordinates

        Returns:
            Tuple of (urban_density, population)
        """
        for city in FULDA_GAP_CITIES:
            city_dist = math.sqrt(
                ((lat - city.lat) * 111) ** 2 +
                ((lon - city.lon) * 111 * math.cos(math.radians(lat))) ** 2
            )
            if city_dist < city.radius_km:
                # Density falls off from center
                distance_factor = 1 - (city_dist / city.radius_km) ** 0.5
                density = city.urban_density * distance_factor

                # Population per cell based on city population and area
                city_area_km2 = math.pi * city.radius_km ** 2
                pop_per_km2 = city.population / city_area_km2
                cell_area_km2 = 0.01  # 100m cell = 0.01 km²
                pop = int(pop_per_km2 * cell_area_km2 * distance_factor)

                return density, pop

        return 0.0, 0

    def generate(
        self,
        bounds: BoundingBox,
        resolution_m: int = 100,
    ) -> list[TerrainCell]:
        """
        Generate terrain cells for a region.

        Args:
            bounds: Geographic bounds to generate
            resolution_m: Cell resolution in meters

        Returns:
            List of TerrainCell objects
        """
        logger.info(f"Generating terrain for bounds: {bounds.south:.4f},{bounds.west:.4f} to {bounds.north:.4f},{bounds.east:.4f}")
        logger.info(f"Resolution: {resolution_m}m")

        # Calculate grid dimensions
        lat_range = bounds.north - bounds.south
        lon_range = bounds.east - bounds.west

        # Approximate cell size in degrees
        lat_step = resolution_m / 111320  # ~111km per degree latitude
        lon_step = resolution_m / (111320 * math.cos(math.radians((bounds.north + bounds.south) / 2)))

        cells = []
        total_cells = int((lat_range / lat_step) * (lon_range / lon_step))
        logger.info(f"Generating approximately {total_cells} cells...")

        lat = bounds.south
        cell_count = 0
        while lat < bounds.north:
            lon = bounds.west
            while lon < bounds.east:
                # Calculate cell properties
                elevation = self._get_elevation(lat, lon, bounds)
                terrain_type, cover, concealment = self._get_terrain_type(
                    lat, lon, elevation, bounds
                )
                is_road, is_bridge = self._check_road(lat, lon)
                urban_density, population = self._get_urban_data(lat, lon)

                # Override terrain type for roads
                if is_bridge:
                    terrain_type = TerrainType.Bridge
                    cover = CoverLevel.Non
                elif is_road:
                    terrain_type = TerrainType.Road
                    cover = CoverLevel.Non
                    concealment = 0.0

                # Check for impassable terrain (steep slopes approximated by elevation gradient)
                is_impassable = False
                if elevation > 700:
                    is_impassable = True

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
                    is_impassable=is_impassable,
                    resolution_m=resolution_m,
                )
                cells.append(cell)
                cell_count += 1

                lon += lon_step
            lat += lat_step

            # Progress logging
            if cell_count % 50000 == 0:
                logger.info(f"Generated {cell_count} cells...")

        logger.info(f"Generated {len(cells)} terrain cells")
        return cells


def generate_fulda_gap(
    output_path: Path,
    resolution_m: int = 100,
) -> Path:
    """
    Generate Fulda Gap terrain data.

    Args:
        output_path: Path for output GeoPackage
        resolution_m: Cell resolution in meters

    Returns:
        Path to created GeoPackage
    """
    from .gpkg_writer import GeoPackageWriter
    from .models import BoundingBox

    bounds = BoundingBox(
        south=50.0,
        west=9.0,
        north=51.0,
        east=10.5,
    )

    generator = SyntheticTerrainGenerator(seed=SEED)
    cells = generator.generate(bounds, resolution_m)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = GeoPackageWriter(output_path)
    writer.write(cells)
    writer.write_metadata(
        region_name="fulda_gap",
        bounds=bounds,
        resolution_m=resolution_m,
        source_info={
            "type": "synthetic",
            "generator": "SyntheticTerrainGenerator",
            "seed": str(SEED),
            "version": "1.0",
        },
    )

    return output_path


def main():
    """CLI entry point for generating synthetic terrain."""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Generate synthetic terrain data for KARKAS"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("data/terrain/fulda_gap.gpkg"),
        help="Output GeoPackage path",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=100,
        help="Cell resolution in meters (default: 100)",
    )
    parser.add_argument(
        "--region",
        choices=["fulda_gap", "test_small"],
        default="fulda_gap",
        help="Region to generate",
    )

    args = parser.parse_args()

    if args.region == "fulda_gap":
        generate_fulda_gap(args.output, args.resolution)
    elif args.region == "test_small":
        from .models import BoundingBox
        bounds = BoundingBox(south=50.4, west=9.4, north=50.6, east=9.6)
        generator = SyntheticTerrainGenerator()
        cells = generator.generate(bounds, args.resolution)

        from .gpkg_writer import GeoPackageWriter
        writer = GeoPackageWriter(args.output)
        writer.write(cells)

    logger.info(f"Terrain data written to {args.output}")


if __name__ == "__main__":
    main()
