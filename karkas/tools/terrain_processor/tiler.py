"""Multi-resolution terrain tile generation."""

from pathlib import Path
from typing import Optional, Any
import logging

import numpy as np
from numpy.typing import NDArray

from .models import BoundingBox, TerrainCell, TerrainType, CoverLevel
from .models.terrain import apply_slope_modifiers
from .utils.geo import meters_to_lat_lon

logger = logging.getLogger(__name__)


class TerrainTiler:
    """
    Generate terrain cells at specified resolution.

    Combines elevation, land cover, roads, and urban data into
    unified TerrainCell objects ready for GeoPackage output.
    """

    def __init__(self, resolution_m: int = 100):
        """
        Initialize the tiler.

        Args:
            resolution_m: Cell size in meters
        """
        self.resolution_m = resolution_m

    def create_cells(
        self,
        bounds: BoundingBox,
        elevation: NDArray[np.float64],
        slope: NDArray[np.float64],
        landcover: dict[str, NDArray],
        roads: dict[str, Any],
        urban: dict[str, Any],
    ) -> list[TerrainCell]:
        """
        Create terrain cells from processed data layers.

        Args:
            bounds: Geographic bounding box
            elevation: Elevation array (meters)
            slope: Slope array (degrees)
            landcover: Dict with terrain_type, cover_level, concealment
            roads: Dict with is_road, is_bridge, road_type
            urban: Dict with urban_density, population

        Returns:
            List of TerrainCell objects
        """
        rows, cols = elevation.shape
        logger.info(f"Creating {rows * cols} terrain cells at {self.resolution_m}m resolution")

        # Calculate cell size in degrees
        deg_lon, deg_lat = meters_to_lat_lon(self.resolution_m, bounds.center_lat)

        cells = []

        for i in range(rows):
            for j in range(cols):
                # Calculate cell center coordinates
                # Note: row 0 is north, so we subtract from north
                lat = bounds.north - (i + 0.5) * deg_lat
                lon = bounds.west + (j + 0.5) * deg_lon

                # Skip cells outside bounds
                if not bounds.contains(lat, lon):
                    continue

                # Extract values from arrays
                elev = float(elevation[i, j])
                slp = float(slope[i, j])

                terrain_type = TerrainType(landcover['terrain_type'][i, j])
                cover_level = CoverLevel(landcover['cover_level'][i, j])
                concealment = float(landcover['concealment'][i, j])

                is_road = bool(roads['is_road'][i, j])
                is_bridge = bool(roads['is_bridge'][i, j])

                urban_density = float(urban['urban_density'][i, j])
                population = int(urban['population'][i, j])

                # Apply slope modifiers
                terrain_type, cover_level, is_impassable = apply_slope_modifiers(
                    terrain_type, cover_level, slp
                )

                # Urban areas get their terrain type from landcover,
                # but we enhance concealment based on density
                if urban_density > 0.3:
                    concealment = max(concealment, urban_density * 0.8)

                # Roads override terrain type for movement purposes
                secondary_type = None
                if is_road:
                    secondary_type = terrain_type
                    # Don't change primary type - road info is in is_road flag

                # Bridges are special
                if is_bridge:
                    secondary_type = terrain_type
                    # Bridge terrain handled by is_bridge flag

                cell = TerrainCell(
                    center_lat=lat,
                    center_lon=lon,
                    elevation_m=elev,
                    primary_type=terrain_type,
                    secondary_type=secondary_type,
                    cover=cover_level,
                    concealment=concealment,
                    urban_density=urban_density,
                    population=population,
                    is_road=is_road,
                    is_bridge=is_bridge,
                    is_impassable=is_impassable,
                    resolution_m=self.resolution_m,
                )
                cells.append(cell)

        logger.info(f"Created {len(cells)} terrain cells")
        return cells

    def load_and_tile(
        self,
        input_dir: Path,
        bounds: Optional[BoundingBox] = None,
    ) -> list[TerrainCell]:
        """
        Load pre-processed data and create terrain cells.

        Args:
            input_dir: Directory containing processed data files
            bounds: Optional bounds to clip to

        Returns:
            List of TerrainCell objects
        """
        import rasterio

        # Load elevation
        elev_file = input_dir / "elevation.tif"
        if elev_file.exists():
            with rasterio.open(elev_file) as src:
                elevation = src.read(1)
                if bounds is None:
                    b = src.bounds
                    bounds = BoundingBox(
                        south=b.bottom,
                        west=b.left,
                        north=b.top,
                        east=b.right,
                    )
        else:
            raise FileNotFoundError(f"Elevation file not found: {elev_file}")

        # Load slope
        slope_file = input_dir / "slope.tif"
        if slope_file.exists():
            with rasterio.open(slope_file) as src:
                slope = src.read(1)
        else:
            slope = np.zeros_like(elevation)

        # Load landcover
        landcover_file = input_dir / "landcover.tif"
        if landcover_file.exists():
            with rasterio.open(landcover_file) as src:
                terrain_type = src.read(1)
                cover_level = src.read(2) if src.count > 1 else np.zeros_like(terrain_type)
                concealment = src.read(3) if src.count > 2 else np.zeros_like(terrain_type, dtype=np.float32)
        else:
            terrain_type = np.full_like(elevation, TerrainType.Open, dtype=np.int8)
            cover_level = np.zeros_like(elevation, dtype=np.int8)
            concealment = np.zeros_like(elevation, dtype=np.float32)

        landcover = {
            'terrain_type': terrain_type,
            'cover_level': cover_level,
            'concealment': concealment,
        }

        # Load roads
        roads_file = input_dir / "roads.tif"
        if roads_file.exists():
            with rasterio.open(roads_file) as src:
                is_road = src.read(1).astype(bool)
                is_bridge = src.read(2).astype(bool) if src.count > 1 else np.zeros_like(is_road)
        else:
            is_road = np.zeros_like(elevation, dtype=bool)
            is_bridge = np.zeros_like(elevation, dtype=bool)

        roads = {
            'is_road': is_road,
            'is_bridge': is_bridge,
            'road_type': np.zeros_like(elevation, dtype=np.int8),
        }

        # Load urban
        urban_file = input_dir / "urban.tif"
        if urban_file.exists():
            with rasterio.open(urban_file) as src:
                urban_density = src.read(1).astype(np.float32)
                population = src.read(2).astype(np.int32) if src.count > 1 else np.zeros_like(urban_density, dtype=np.int32)
        else:
            urban_density = np.zeros_like(elevation, dtype=np.float32)
            population = np.zeros_like(elevation, dtype=np.int32)

        urban = {
            'urban_density': urban_density,
            'population': population,
        }

        return self.create_cells(bounds, elevation, slope, landcover, roads, urban)

    def resample_to_resolution(
        self,
        cells: list[TerrainCell],
        target_resolution_m: int,
        bounds: BoundingBox,
    ) -> list[TerrainCell]:
        """
        Resample terrain cells to a different resolution.

        Args:
            cells: Source terrain cells
            target_resolution_m: Target resolution in meters
            bounds: Geographic bounds

        Returns:
            List of resampled TerrainCell objects
        """
        if target_resolution_m == self.resolution_m:
            return cells

        # Convert cells to arrays
        from .utils.geo import lat_lon_to_meters

        m_per_deg_lon, m_per_deg_lat = lat_lon_to_meters(bounds.center_lat)

        src_rows = int(bounds.height_deg * m_per_deg_lat / self.resolution_m)
        src_cols = int(bounds.width_deg * m_per_deg_lon / self.resolution_m)

        dst_rows = int(bounds.height_deg * m_per_deg_lat / target_resolution_m)
        dst_cols = int(bounds.width_deg * m_per_deg_lon / target_resolution_m)

        # Create source arrays
        elevation = np.zeros((src_rows, src_cols))
        terrain_type = np.zeros((src_rows, src_cols), dtype=np.int8)

        deg_lat = self.resolution_m / m_per_deg_lat
        deg_lon = self.resolution_m / m_per_deg_lon

        for cell in cells:
            row = int((bounds.north - cell.center_lat) / deg_lat)
            col = int((cell.center_lon - bounds.west) / deg_lon)
            if 0 <= row < src_rows and 0 <= col < src_cols:
                elevation[row, col] = cell.elevation_m
                terrain_type[row, col] = cell.primary_type

        # Resample (simplified - just returns original for now)
        # Full implementation would use scipy.ndimage.zoom
        logger.warning(f"Resampling from {self.resolution_m}m to {target_resolution_m}m not fully implemented")
        return cells
