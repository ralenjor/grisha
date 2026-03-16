"""Urban processor - OSM buildings to urban density grid."""

from pathlib import Path
from typing import Any
import logging
import json

import numpy as np
from numpy.typing import NDArray

from .base import BaseProcessor
from ..models import BoundingBox

logger = logging.getLogger(__name__)


class UrbanProcessor(BaseProcessor):
    """
    Process OpenStreetMap building data into urban density grid.

    Takes GeoJSON buildings and produces:
    - urban_density: Building coverage ratio (0-1)
    - population: Estimated population (based on building area)
    - building_geometries: Building footprints for GeoPackage
    """

    # Estimated population density per 100m² of building footprint
    # Varies by building type
    POPULATION_DENSITY = {
        'residential': 0.5,
        'apartments': 1.5,
        'house': 0.3,
        'commercial': 0.1,
        'industrial': 0.05,
        'retail': 0.2,
        'office': 0.3,
        'default': 0.2,
    }

    @property
    def processor_name(self) -> str:
        return "Urban Processor"

    def process(
        self,
        bounds: BoundingBox,
        resolution_m: int,
    ) -> dict[str, Any]:
        """
        Process building data for the specified bounds.

        Args:
            bounds: Geographic bounding box
            resolution_m: Target resolution in meters

        Returns:
            Dictionary with urban_density, population arrays and geometries
        """
        target_shape = self.get_grid_shape(bounds, resolution_m)

        # Find buildings GeoJSON
        buildings_files = self.find_data_files("buildings.geojson")
        if not buildings_files:
            logger.warning("No building data found")
            return {
                'urban_density': np.zeros(target_shape, dtype=np.float32),
                'population': np.zeros(target_shape, dtype=np.int32),
                'geometries': [],
            }

        buildings_file = buildings_files[0]
        logger.info(f"Processing buildings from {buildings_file}")

        try:
            import geopandas as gpd
            from shapely.geometry import box as shapely_box

            # Load buildings
            buildings_gdf = gpd.read_file(buildings_file)

            # Clip to bounds
            bbox = shapely_box(bounds.west, bounds.south, bounds.east, bounds.north)
            buildings_gdf = buildings_gdf.clip(bbox)

            if len(buildings_gdf) == 0:
                logger.warning("No buildings within bounds")
                return {
                    'urban_density': np.zeros(target_shape, dtype=np.float32),
                    'population': np.zeros(target_shape, dtype=np.int32),
                    'geometries': [],
                }

            # Calculate urban density
            urban_density = self._calculate_density(
                buildings_gdf, bounds, target_shape, resolution_m
            )

            # Estimate population
            population = self._estimate_population(
                buildings_gdf, bounds, target_shape, resolution_m
            )

            # Extract geometries
            geometries = self._extract_geometries(buildings_gdf)

            total_buildings = len(buildings_gdf)
            urban_coverage = np.mean(urban_density) * 100
            total_pop = np.sum(population)

            logger.info(f"Buildings: {total_buildings}")
            logger.info(f"Urban coverage: {urban_coverage:.2f}%")
            logger.info(f"Estimated population: {total_pop}")

            return {
                'urban_density': urban_density,
                'population': population,
                'geometries': geometries,
            }

        except ImportError:
            logger.warning("geopandas not available, using fallback")
            return self._process_without_geopandas(buildings_file, bounds, target_shape, resolution_m)

    def _calculate_density(
        self,
        buildings_gdf,
        bounds: BoundingBox,
        shape: tuple[int, int],
        resolution_m: int,
    ) -> NDArray[np.float32]:
        """Calculate building density per cell."""
        from rasterio.features import rasterize
        from rasterio.transform import from_bounds

        transform = from_bounds(
            bounds.west, bounds.south, bounds.east, bounds.north,
            shape[1], shape[0],
        )

        # Rasterize with coverage fraction
        geometries = [(geom, 1) for geom in buildings_gdf.geometry if geom is not None]

        if not geometries:
            return np.zeros(shape, dtype=np.float32)

        # Simple binary rasterization first
        raster = rasterize(
            geometries,
            out_shape=shape,
            transform=transform,
            dtype=np.uint8,
            fill=0,
            all_touched=True,
        )

        # Calculate local density using a 3x3 window
        from scipy.ndimage import uniform_filter
        density = uniform_filter(raster.astype(np.float32), size=3, mode='nearest')

        return np.clip(density, 0, 1)

    def _estimate_population(
        self,
        buildings_gdf,
        bounds: BoundingBox,
        shape: tuple[int, int],
        resolution_m: int,
    ) -> NDArray[np.int32]:
        """Estimate population per cell based on building area and type."""
        from rasterio.transform import from_bounds
        from ..utils.geo import lat_lon_to_meters

        population = np.zeros(shape, dtype=np.float32)

        rows, cols = shape
        lat_step = bounds.height_deg / rows
        lon_step = bounds.width_deg / cols

        # Get meters per degree for area calculation
        m_per_deg_lon, m_per_deg_lat = lat_lon_to_meters(bounds.center_lat)

        # Find building type column
        building_col = None
        for col in ['building', 'type', 'fclass']:
            if col in buildings_gdf.columns:
                building_col = col
                break

        for _, row in buildings_gdf.iterrows():
            geom = row.geometry
            if geom is None:
                continue

            # Get building type
            building_type = 'default'
            if building_col:
                bt = row.get(building_col, '')
                if bt in self.POPULATION_DENSITY:
                    building_type = bt
                elif bt == 'yes':
                    building_type = 'residential'

            # Calculate area in m²
            centroid = geom.centroid
            if hasattr(geom, 'area'):
                # Convert from degrees² to m²
                area_m2 = geom.area * m_per_deg_lon * m_per_deg_lat
            else:
                area_m2 = 100  # Default

            # Estimate population
            pop_density = self.POPULATION_DENSITY[building_type]
            estimated_pop = area_m2 / 100 * pop_density

            # Assign to grid cell
            lat, lon = centroid.y, centroid.x
            if bounds.contains(lat, lon):
                row_idx = int((bounds.north - lat) / lat_step)
                col_idx = int((lon - bounds.west) / lon_step)

                if 0 <= row_idx < rows and 0 <= col_idx < cols:
                    population[row_idx, col_idx] += estimated_pop

        return population.astype(np.int32)

    def _extract_geometries(self, buildings_gdf) -> list[dict]:
        """Extract building geometries for GeoPackage output."""
        geometries = []

        building_col = None
        for col in ['building', 'type', 'fclass']:
            if col in buildings_gdf.columns:
                building_col = col
                break

        for _, row in buildings_gdf.iterrows():
            if row.geometry is None:
                continue

            geom_dict = {
                'geometry': row.geometry,
                'building_type': row.get(building_col, 'yes') if building_col else 'yes',
            }
            geometries.append(geom_dict)

        return geometries

    def _process_without_geopandas(
        self,
        buildings_file: Path,
        bounds: BoundingBox,
        shape: tuple[int, int],
        resolution_m: int,
    ) -> dict[str, Any]:
        """Fallback processing without geopandas."""
        with open(buildings_file) as f:
            data = json.load(f)

        urban_density = np.zeros(shape, dtype=np.float32)
        population = np.zeros(shape, dtype=np.int32)
        geometries = []

        rows, cols = shape
        lat_step = bounds.height_deg / rows
        lon_step = bounds.width_deg / cols

        building_count = np.zeros(shape, dtype=np.int32)

        for feature in data.get('features', []):
            geom = feature.get('geometry', {})
            props = feature.get('properties', {})

            geom_type = geom.get('type', '')
            if geom_type not in ['Polygon', 'MultiPolygon']:
                continue

            # Get centroid (simplified)
            coords = geom.get('coordinates', [])
            if geom_type == 'Polygon' and coords:
                ring = coords[0]
                lons = [c[0] for c in ring]
                lats = [c[1] for c in ring]
                center_lon = sum(lons) / len(lons)
                center_lat = sum(lats) / len(lats)
            elif geom_type == 'MultiPolygon' and coords:
                ring = coords[0][0]
                lons = [c[0] for c in ring]
                lats = [c[1] for c in ring]
                center_lon = sum(lons) / len(lons)
                center_lat = sum(lats) / len(lats)
            else:
                continue

            if bounds.contains(center_lat, center_lon):
                row_idx = int((bounds.north - center_lat) / lat_step)
                col_idx = int((center_lon - bounds.west) / lon_step)

                if 0 <= row_idx < rows and 0 <= col_idx < cols:
                    building_count[row_idx, col_idx] += 1

                    # Simple population estimate
                    building_type = props.get('building', 'default')
                    pop_density = self.POPULATION_DENSITY.get(building_type, 0.2)
                    population[row_idx, col_idx] += int(pop_density * 10)

            geometries.append({
                'building_type': props.get('building', 'yes'),
            })

        # Convert building count to density
        max_buildings = max(np.max(building_count), 1)
        urban_density = building_count.astype(np.float32) / max_buildings

        return {
            'urban_density': urban_density,
            'population': population,
            'geometries': geometries,
        }
