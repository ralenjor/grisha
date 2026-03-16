"""Roads processor - OSM roads to road network grid."""

from pathlib import Path
from typing import Any
import logging
import json

import numpy as np
from numpy.typing import NDArray

from .base import BaseProcessor
from ..models import BoundingBox

logger = logging.getLogger(__name__)


class RoadsProcessor(BaseProcessor):
    """
    Process OpenStreetMap road data into road grid.

    Takes GeoJSON roads and produces:
    - is_road: Boolean grid of road presence
    - is_bridge: Boolean grid of bridge presence
    - road_type: Road classification (for movement cost)
    - geometries: Road geometries for GeoPackage output
    """

    # Road type priorities (higher = better road)
    ROAD_PRIORITIES = {
        'motorway': 10,
        'motorway_link': 9,
        'trunk': 8,
        'trunk_link': 7,
        'primary': 6,
        'primary_link': 5,
        'secondary': 4,
        'secondary_link': 3,
        'tertiary': 2,
        'tertiary_link': 1,
        'residential': 1,
        'unclassified': 1,
        'service': 0,
        'track': 0,
        'path': -1,
    }

    @property
    def processor_name(self) -> str:
        return "Roads Processor"

    def process(
        self,
        bounds: BoundingBox,
        resolution_m: int,
    ) -> dict[str, Any]:
        """
        Process road data for the specified bounds.

        Args:
            bounds: Geographic bounding box
            resolution_m: Target resolution in meters

        Returns:
            Dictionary with is_road, is_bridge, road_type arrays and geometries
        """
        target_shape = self.get_grid_shape(bounds, resolution_m)

        # Find roads GeoJSON
        roads_files = self.find_data_files("roads.geojson")
        if not roads_files:
            logger.warning("No road data found")
            return {
                'is_road': np.zeros(target_shape, dtype=bool),
                'is_bridge': np.zeros(target_shape, dtype=bool),
                'road_type': np.zeros(target_shape, dtype=np.int8),
                'geometries': [],
            }

        roads_file = roads_files[0]
        logger.info(f"Processing roads from {roads_file}")

        try:
            import geopandas as gpd
            from shapely.geometry import box as shapely_box

            # Load roads
            roads_gdf = gpd.read_file(roads_file)

            # Clip to bounds
            bbox = shapely_box(bounds.west, bounds.south, bounds.east, bounds.north)
            roads_gdf = roads_gdf.clip(bbox)

            if len(roads_gdf) == 0:
                logger.warning("No roads within bounds")
                return {
                    'is_road': np.zeros(target_shape, dtype=bool),
                    'is_bridge': np.zeros(target_shape, dtype=bool),
                    'road_type': np.zeros(target_shape, dtype=np.int8),
                    'geometries': [],
                }

            # Rasterize roads
            is_road = self._rasterize_roads(roads_gdf, bounds, target_shape)
            is_bridge = self._rasterize_bridges(roads_gdf, bounds, target_shape)
            road_type = self._rasterize_road_types(roads_gdf, bounds, target_shape)

            # Extract geometries for GeoPackage
            geometries = self._extract_geometries(roads_gdf)

            logger.info(f"Road coverage: {np.sum(is_road) / is_road.size * 100:.2f}%")
            logger.info(f"Bridge count: {np.sum(is_bridge)}")

            return {
                'is_road': is_road,
                'is_bridge': is_bridge,
                'road_type': road_type,
                'geometries': geometries,
            }

        except ImportError:
            logger.warning("geopandas not available, using fallback")
            return self._process_without_geopandas(roads_file, bounds, target_shape)

    def _rasterize_roads(
        self,
        roads_gdf,
        bounds: BoundingBox,
        shape: tuple[int, int],
    ) -> NDArray[np.bool_]:
        """Rasterize road geometries to a boolean grid."""
        from rasterio.features import rasterize
        from rasterio.transform import from_bounds

        transform = from_bounds(
            bounds.west, bounds.south, bounds.east, bounds.north,
            shape[1], shape[0],
        )

        geometries = [(geom, 1) for geom in roads_gdf.geometry if geom is not None]

        if not geometries:
            return np.zeros(shape, dtype=bool)

        raster = rasterize(
            geometries,
            out_shape=shape,
            transform=transform,
            dtype=np.uint8,
            fill=0,
            all_touched=True,
        )

        return raster.astype(bool)

    def _rasterize_bridges(
        self,
        roads_gdf,
        bounds: BoundingBox,
        shape: tuple[int, int],
    ) -> NDArray[np.bool_]:
        """Rasterize bridge locations."""
        from rasterio.features import rasterize
        from rasterio.transform import from_bounds

        # Filter for bridges
        bridge_col = None
        for col in ['bridge', 'man_made']:
            if col in roads_gdf.columns:
                bridge_col = col
                break

        if bridge_col is None:
            return np.zeros(shape, dtype=bool)

        bridges = roads_gdf[roads_gdf[bridge_col].notna() & (roads_gdf[bridge_col] != 'no')]

        if len(bridges) == 0:
            return np.zeros(shape, dtype=bool)

        transform = from_bounds(
            bounds.west, bounds.south, bounds.east, bounds.north,
            shape[1], shape[0],
        )

        geometries = [(geom, 1) for geom in bridges.geometry if geom is not None]

        raster = rasterize(
            geometries,
            out_shape=shape,
            transform=transform,
            dtype=np.uint8,
            fill=0,
            all_touched=True,
        )

        return raster.astype(bool)

    def _rasterize_road_types(
        self,
        roads_gdf,
        bounds: BoundingBox,
        shape: tuple[int, int],
    ) -> NDArray[np.int8]:
        """Rasterize road type priorities."""
        from rasterio.features import rasterize
        from rasterio.transform import from_bounds

        transform = from_bounds(
            bounds.west, bounds.south, bounds.east, bounds.north,
            shape[1], shape[0],
        )

        # Find highway column
        highway_col = None
        for col in ['highway', 'fclass']:
            if col in roads_gdf.columns:
                highway_col = col
                break

        if highway_col is None:
            # Just mark as generic road
            return self._rasterize_roads(roads_gdf, bounds, shape).astype(np.int8)

        # Create geometries with priorities
        geometries = []
        for _, row in roads_gdf.iterrows():
            if row.geometry is None:
                continue
            highway_type = row.get(highway_col, '')
            priority = self.ROAD_PRIORITIES.get(highway_type, 0) + 1  # +1 so 0 = no road
            geometries.append((row.geometry, priority))

        if not geometries:
            return np.zeros(shape, dtype=np.int8)

        raster = rasterize(
            geometries,
            out_shape=shape,
            transform=transform,
            dtype=np.int8,
            fill=0,
            merge_alg='MAX',  # Higher priority roads win
        )

        return raster

    def _extract_geometries(self, roads_gdf) -> list[dict]:
        """Extract road geometries for GeoPackage output."""
        geometries = []

        highway_col = None
        for col in ['highway', 'fclass']:
            if col in roads_gdf.columns:
                highway_col = col
                break

        name_col = None
        for col in ['name', 'ref']:
            if col in roads_gdf.columns:
                name_col = col
                break

        for _, row in roads_gdf.iterrows():
            if row.geometry is None:
                continue

            geom_dict = {
                'geometry': row.geometry,
                'road_type': row.get(highway_col, 'unknown') if highway_col else 'unknown',
                'name': row.get(name_col, '') if name_col else '',
            }
            geometries.append(geom_dict)

        return geometries

    def _process_without_geopandas(
        self,
        roads_file: Path,
        bounds: BoundingBox,
        shape: tuple[int, int],
    ) -> dict[str, Any]:
        """Fallback processing without geopandas."""
        with open(roads_file) as f:
            data = json.load(f)

        is_road = np.zeros(shape, dtype=bool)
        is_bridge = np.zeros(shape, dtype=bool)
        geometries = []

        rows, cols = shape
        lat_step = bounds.height_deg / rows
        lon_step = bounds.width_deg / cols

        for feature in data.get('features', []):
            geom = feature.get('geometry', {})
            props = feature.get('properties', {})

            if geom.get('type') != 'LineString':
                continue

            coords = geom.get('coordinates', [])

            for lon, lat in coords:
                if bounds.contains(lat, lon):
                    row = int((bounds.north - lat) / lat_step)
                    col = int((lon - bounds.west) / lon_step)

                    if 0 <= row < rows and 0 <= col < cols:
                        is_road[row, col] = True

                        if props.get('bridge') and props['bridge'] != 'no':
                            is_bridge[row, col] = True

            geometries.append({
                'road_type': props.get('highway', 'unknown'),
                'name': props.get('name', ''),
            })

        return {
            'is_road': is_road,
            'is_bridge': is_bridge,
            'road_type': is_road.astype(np.int8),
            'geometries': geometries,
        }
