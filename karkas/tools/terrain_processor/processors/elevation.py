"""Elevation data processor - DEM to elevation, slope, aspect."""

from pathlib import Path
from typing import Any
import logging

import numpy as np
from numpy.typing import NDArray

from .base import BaseProcessor
from ..models import BoundingBox
from ..utils.geo import calculate_slope, calculate_aspect, lat_lon_to_meters

logger = logging.getLogger(__name__)


class ElevationProcessor(BaseProcessor):
    """
    Process SRTM/DEM data into elevation, slope, and aspect arrays.

    Takes raw elevation GeoTIFFs and produces:
    - elevation_m: Elevation in meters
    - slope_deg: Slope in degrees (0-90)
    - aspect_deg: Aspect in degrees (0-360, north=0)
    """

    @property
    def processor_name(self) -> str:
        return "Elevation Processor"

    def process(
        self,
        bounds: BoundingBox,
        resolution_m: int,
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """
        Process elevation data for the specified bounds.

        Args:
            bounds: Geographic bounding box
            resolution_m: Target resolution in meters

        Returns:
            Tuple of (elevation_array, slope_array)
        """
        import rasterio
        from rasterio.merge import merge
        from rasterio.mask import mask
        from rasterio.warp import reproject, Resampling
        from shapely.geometry import box

        # Find all SRTM tiles
        tif_files = self.find_data_files("*.tif")
        if not tif_files:
            logger.warning("No elevation files found, using default elevation")
            shape = self.get_grid_shape(bounds, resolution_m)
            return np.zeros(shape), np.zeros(shape)

        logger.info(f"Processing {len(tif_files)} elevation tiles")

        # Open all datasets
        datasets = []
        for f in tif_files:
            try:
                ds = rasterio.open(f)
                datasets.append(ds)
            except Exception as e:
                logger.warning(f"Could not open {f}: {e}")

        if not datasets:
            shape = self.get_grid_shape(bounds, resolution_m)
            return np.zeros(shape), np.zeros(shape)

        # Merge tiles
        if len(datasets) > 1:
            mosaic, mosaic_transform = merge(datasets)
            mosaic = mosaic[0]  # Get first band
            crs = datasets[0].crs
        else:
            mosaic = datasets[0].read(1)
            mosaic_transform = datasets[0].transform
            crs = datasets[0].crs

        for ds in datasets:
            ds.close()

        # Clip to bounds
        bbox = box(bounds.west, bounds.south, bounds.east, bounds.north)

        # Create a temporary dataset for clipping
        temp_profile = {
            'driver': 'GTiff',
            'height': mosaic.shape[0],
            'width': mosaic.shape[1],
            'count': 1,
            'dtype': mosaic.dtype,
            'crs': crs,
            'transform': mosaic_transform,
        }

        from rasterio.io import MemoryFile

        with MemoryFile() as memfile:
            with memfile.open(**temp_profile) as temp_ds:
                temp_ds.write(mosaic, 1)

            with memfile.open() as src:
                try:
                    clipped, clipped_transform = mask(src, [bbox], crop=True)
                    clipped = clipped[0]
                except ValueError:
                    # Bounds don't intersect data
                    logger.warning("Bounds don't intersect elevation data")
                    shape = self.get_grid_shape(bounds, resolution_m)
                    return np.zeros(shape), np.zeros(shape)

        # Handle nodata
        nodata_value = -32768
        clipped = np.where(clipped == nodata_value, np.nan, clipped).astype(np.float64)

        # Calculate slope at native resolution
        # Get cell size in meters at center latitude
        m_per_deg_lon, m_per_deg_lat = lat_lon_to_meters(bounds.center_lat)
        native_cell_size_m = m_per_deg_lat / clipped.shape[0] * bounds.height_deg

        slope_native = calculate_slope(clipped, native_cell_size_m)

        # Resample to target resolution
        target_shape = self.get_grid_shape(bounds, resolution_m)

        elevation = self.resample_to_grid(
            clipped,
            bounds.to_tuple(),
            bounds.to_tuple(),
            target_shape,
            method="bilinear",
        )

        slope = self.resample_to_grid(
            slope_native,
            bounds.to_tuple(),
            bounds.to_tuple(),
            target_shape,
            method="bilinear",
        )

        # Fill NaN with interpolation
        elevation = self._fill_nan(elevation)
        slope = self._fill_nan(slope)

        logger.info(f"Elevation range: {np.nanmin(elevation):.1f}m - {np.nanmax(elevation):.1f}m")
        logger.info(f"Slope range: {np.nanmin(slope):.1f}° - {np.nanmax(slope):.1f}°")

        return elevation, slope

    def _fill_nan(self, data: NDArray[np.float64]) -> NDArray[np.float64]:
        """Fill NaN values using nearest neighbor interpolation."""
        from scipy.ndimage import distance_transform_edt

        nan_mask = np.isnan(data)
        if not np.any(nan_mask):
            return data

        # Get indices of nearest non-NaN values
        indices = distance_transform_edt(
            nan_mask,
            return_distances=False,
            return_indices=True,
        )

        # Fill NaN values
        filled = data[tuple(indices)]
        return filled

    def compute_viewshed_factor(
        self,
        elevation: NDArray[np.float64],
        slope: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """
        Compute a viewshed/visibility factor based on elevation and slope.

        Higher values indicate positions with better observation capability.

        Args:
            elevation: Elevation array
            slope: Slope array

        Returns:
            Viewshed factor array (0-1)
        """
        # Normalize elevation to 0-1 within the local area
        elev_min, elev_max = np.nanmin(elevation), np.nanmax(elevation)
        if elev_max > elev_min:
            elev_norm = (elevation - elev_min) / (elev_max - elev_min)
        else:
            elev_norm = np.zeros_like(elevation)

        # Moderate slopes are better for observation posts
        # Very flat or very steep are less ideal
        slope_factor = np.clip(slope / 30, 0, 1)  # Normalize to 30 degrees
        slope_factor = 1 - np.abs(slope_factor - 0.5) * 2  # Peak at 15 degrees

        viewshed = 0.7 * elev_norm + 0.3 * slope_factor
        return np.clip(viewshed, 0, 1)
