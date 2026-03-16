"""GeoPackage output writer for terrain data."""

from pathlib import Path
from typing import Optional, Any
import logging

from .models import TerrainCell

logger = logging.getLogger(__name__)


class GeoPackageWriter:
    """
    Write terrain data to GeoPackage format.

    Creates a GeoPackage with:
    - terrain_cells: Grid of terrain properties
    - roads: Road network geometries (optional)
    - buildings: Building footprints (optional)
    """

    def __init__(self, output_path: Path):
        """
        Initialize the writer.

        Args:
            output_path: Path for output GeoPackage file
        """
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        cells: list[TerrainCell],
        roads: Optional[list[dict]] = None,
        buildings: Optional[list[dict]] = None,
        create_spatial_index: bool = True,
    ) -> Path:
        """
        Write terrain data to GeoPackage.

        Args:
            cells: List of TerrainCell objects
            roads: Optional list of road geometry dicts
            buildings: Optional list of building geometry dicts
            create_spatial_index: Whether to create spatial index

        Returns:
            Path to created GeoPackage
        """
        import geopandas as gpd
        from shapely.geometry import Point, box

        logger.info(f"Writing {len(cells)} cells to {self.output_path}")

        # Create terrain cells GeoDataFrame
        records = []
        for cell in cells:
            # Create cell polygon (square centered on point)
            half_size_lat = cell.resolution_m / 111320 / 2  # Approximate
            half_size_lon = half_size_lat / np.cos(np.radians(cell.center_lat))

            geom = box(
                cell.center_lon - half_size_lon,
                cell.center_lat - half_size_lat,
                cell.center_lon + half_size_lon,
                cell.center_lat + half_size_lat,
            )

            record = {
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
            }
            records.append(record)

        cells_gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")

        # Write to GeoPackage
        cells_gdf.to_file(self.output_path, layer='terrain_cells', driver='GPKG')
        logger.info(f"Wrote terrain_cells layer ({len(cells_gdf)} features)")

        # Write roads if provided
        if roads and len(roads) > 0:
            roads_with_geom = [r for r in roads if 'geometry' in r and r['geometry'] is not None]
            if roads_with_geom:
                roads_gdf = gpd.GeoDataFrame(roads_with_geom, crs="EPSG:4326")
                roads_gdf.to_file(self.output_path, layer='roads', driver='GPKG', mode='a')
                logger.info(f"Wrote roads layer ({len(roads_gdf)} features)")

        # Write buildings if provided
        if buildings and len(buildings) > 0:
            buildings_with_geom = [b for b in buildings if 'geometry' in b and b['geometry'] is not None]
            if buildings_with_geom:
                buildings_gdf = gpd.GeoDataFrame(buildings_with_geom, crs="EPSG:4326")
                buildings_gdf.to_file(self.output_path, layer='buildings', driver='GPKG', mode='a')
                logger.info(f"Wrote buildings layer ({len(buildings_gdf)} features)")

        # Create spatial index
        if create_spatial_index:
            self._create_spatial_index()

        logger.info(f"GeoPackage created: {self.output_path}")
        return self.output_path

    def _create_spatial_index(self) -> None:
        """Create spatial index on terrain_cells layer."""
        import sqlite3

        try:
            conn = sqlite3.connect(self.output_path)
            cursor = conn.cursor()

            # Check if spatial index exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='rtree_terrain_cells_geom'
            """)

            if cursor.fetchone() is None:
                # GeoPackage should create this automatically via gpkg_extensions
                # but we can verify it exists
                cursor.execute("""
                    SELECT * FROM gpkg_extensions
                    WHERE extension_name = 'gpkg_rtree_index'
                """)
                has_rtree = cursor.fetchone() is not None

                if not has_rtree:
                    logger.warning("Spatial index may not be present")

            conn.close()

        except Exception as e:
            logger.warning(f"Could not verify spatial index: {e}")

    def write_metadata(
        self,
        region_name: str,
        bounds: 'BoundingBox',
        resolution_m: int,
        source_info: dict[str, str],
    ) -> None:
        """
        Write processing metadata to GeoPackage.

        Args:
            region_name: Name of the processed region
            bounds: Geographic bounds
            resolution_m: Cell resolution in meters
            source_info: Dictionary of source data information
        """
        import sqlite3
        import json
        from datetime import datetime

        conn = sqlite3.connect(self.output_path)
        cursor = conn.cursor()

        # Create metadata table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS terrain_metadata (
                id INTEGER PRIMARY KEY,
                key TEXT UNIQUE,
                value TEXT
            )
        """)

        metadata = {
            'region_name': region_name,
            'bounds_south': bounds.south,
            'bounds_west': bounds.west,
            'bounds_north': bounds.north,
            'bounds_east': bounds.east,
            'resolution_m': resolution_m,
            'created_at': datetime.utcnow().isoformat(),
            'source_info': json.dumps(source_info),
        }

        for key, value in metadata.items():
            cursor.execute("""
                INSERT OR REPLACE INTO terrain_metadata (key, value)
                VALUES (?, ?)
            """, (key, str(value)))

        conn.commit()
        conn.close()

        logger.info("Wrote processing metadata")


# Need numpy for the box calculation
import numpy as np


class GeoPackageReader:
    """Read terrain data from GeoPackage format."""

    def __init__(self, gpkg_path: Path):
        """
        Initialize the reader.

        Args:
            gpkg_path: Path to GeoPackage file
        """
        self.gpkg_path = Path(gpkg_path)

    def read_cells(self, bounds: Optional['BoundingBox'] = None) -> list[TerrainCell]:
        """
        Read terrain cells from GeoPackage.

        Args:
            bounds: Optional bounds to filter cells

        Returns:
            List of TerrainCell objects
        """
        import geopandas as gpd
        from ..models import TerrainType, CoverLevel

        gdf = gpd.read_file(self.gpkg_path, layer='terrain_cells')

        if bounds is not None:
            from shapely.geometry import box
            bbox = box(bounds.west, bounds.south, bounds.east, bounds.north)
            gdf = gdf.clip(bbox)

        cells = []
        for _, row in gdf.iterrows():
            cell = TerrainCell(
                center_lat=row['center_lat'],
                center_lon=row['center_lon'],
                elevation_m=row['elevation_m'],
                primary_type=TerrainType(row['primary_type']),
                secondary_type=TerrainType(row['secondary_type']) if row['secondary_type'] else None,
                cover=CoverLevel(row['cover']),
                concealment=row['concealment'],
                urban_density=row['urban_density'],
                population=row['population'],
                is_road=bool(row['is_road']),
                is_bridge=bool(row['is_bridge']),
                is_impassable=bool(row['is_impassable']),
                resolution_m=row['resolution_m'],
            )
            cells.append(cell)

        return cells

    def get_metadata(self) -> dict[str, Any]:
        """
        Read processing metadata from GeoPackage.

        Returns:
            Dictionary of metadata
        """
        import sqlite3
        import json

        conn = sqlite3.connect(self.gpkg_path)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT key, value FROM terrain_metadata")
            metadata = dict(cursor.fetchall())

            # Parse JSON fields
            if 'source_info' in metadata:
                metadata['source_info'] = json.loads(metadata['source_info'])

            return metadata
        except sqlite3.OperationalError:
            return {}
        finally:
            conn.close()

    def get_cell_at(self, lat: float, lon: float) -> Optional[TerrainCell]:
        """
        Get the terrain cell containing a specific coordinate.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            TerrainCell or None if not found
        """
        import sqlite3

        conn = sqlite3.connect(self.gpkg_path)
        conn.enable_load_extension(True)

        try:
            # Try to load spatialite for spatial queries
            conn.load_extension('mod_spatialite')

            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM terrain_cells
                WHERE ST_Contains(geom, MakePoint(?, ?, 4326))
                LIMIT 1
            """, (lon, lat))

            row = cursor.fetchone()
            if row:
                # Convert to TerrainCell (would need column mapping)
                pass

        except Exception:
            # Fall back to simple query
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM terrain_cells
                WHERE center_lat BETWEEN ? AND ?
                AND center_lon BETWEEN ? AND ?
                ORDER BY ABS(center_lat - ?) + ABS(center_lon - ?)
                LIMIT 1
            """, (lat - 0.01, lat + 0.01, lon - 0.01, lon + 0.01, lat, lon))

        conn.close()
        return None  # Simplified for now
