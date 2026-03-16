"""Land cover processor - WorldCover to terrain types."""

from pathlib import Path
from typing import Any
import logging

import numpy as np
from numpy.typing import NDArray

from .base import BaseProcessor
from ..models import BoundingBox, TerrainType, CoverLevel, WORLDCOVER_MAPPING

logger = logging.getLogger(__name__)


class LandcoverProcessor(BaseProcessor):
    """
    Process ESA WorldCover data into terrain types and cover levels.

    Takes WorldCover 10m classification and produces:
    - terrain_type: Primary terrain classification
    - cover_level: Vegetation/structure cover
    - concealment: Concealment value (0-1)
    """

    @property
    def processor_name(self) -> str:
        return "Land Cover Processor"

    def process(
        self,
        bounds: BoundingBox,
        resolution_m: int,
    ) -> dict[str, NDArray]:
        """
        Process land cover data for the specified bounds.

        Args:
            bounds: Geographic bounding box
            resolution_m: Target resolution in meters

        Returns:
            Dictionary with terrain_type, cover_level, concealment arrays
        """
        import rasterio
        from rasterio.merge import merge
        from rasterio.mask import mask
        from shapely.geometry import box
        from scipy.stats import mode

        # Find WorldCover tiles
        tif_files = self.find_data_files("*.tif")
        if not tif_files:
            logger.warning("No land cover files found, using default (Open)")
            shape = self.get_grid_shape(bounds, resolution_m)
            return {
                'terrain_type': np.full(shape, TerrainType.Open, dtype=np.int8),
                'cover_level': np.full(shape, CoverLevel.Non, dtype=np.int8),
                'concealment': np.zeros(shape, dtype=np.float32),
            }

        logger.info(f"Processing {len(tif_files)} land cover tiles")

        # Open and merge tiles
        datasets = []
        for f in tif_files:
            try:
                ds = rasterio.open(f)
                datasets.append(ds)
            except Exception as e:
                logger.warning(f"Could not open {f}: {e}")

        if not datasets:
            shape = self.get_grid_shape(bounds, resolution_m)
            return {
                'terrain_type': np.full(shape, TerrainType.Open, dtype=np.int8),
                'cover_level': np.full(shape, CoverLevel.Non, dtype=np.int8),
                'concealment': np.zeros(shape, dtype=np.float32),
            }

        if len(datasets) > 1:
            mosaic, mosaic_transform = merge(datasets)
            mosaic = mosaic[0]
            crs = datasets[0].crs
        else:
            mosaic = datasets[0].read(1)
            mosaic_transform = datasets[0].transform
            crs = datasets[0].crs

        for ds in datasets:
            ds.close()

        # Clip to bounds
        bbox = box(bounds.west, bounds.south, bounds.east, bounds.north)

        from rasterio.io import MemoryFile

        temp_profile = {
            'driver': 'GTiff',
            'height': mosaic.shape[0],
            'width': mosaic.shape[1],
            'count': 1,
            'dtype': mosaic.dtype,
            'crs': crs,
            'transform': mosaic_transform,
        }

        with MemoryFile() as memfile:
            with memfile.open(**temp_profile) as temp_ds:
                temp_ds.write(mosaic, 1)

            with memfile.open() as src:
                try:
                    clipped, clipped_transform = mask(src, [bbox], crop=True)
                    clipped = clipped[0]
                except ValueError:
                    logger.warning("Bounds don't intersect land cover data")
                    shape = self.get_grid_shape(bounds, resolution_m)
                    return {
                        'terrain_type': np.full(shape, TerrainType.Open, dtype=np.int8),
                        'cover_level': np.full(shape, CoverLevel.Non, dtype=np.int8),
                        'concealment': np.zeros(shape, dtype=np.float32),
                    }

        # Resample to target resolution using majority filter
        target_shape = self.get_grid_shape(bounds, resolution_m)
        landcover = self._resample_categorical(clipped, target_shape)

        # Convert WorldCover codes to terrain properties
        terrain_type = np.zeros(target_shape, dtype=np.int8)
        cover_level = np.zeros(target_shape, dtype=np.int8)
        concealment = np.zeros(target_shape, dtype=np.float32)

        for wc_code, (tt, cl, conc) in WORLDCOVER_MAPPING.items():
            mask_arr = landcover == wc_code
            terrain_type[mask_arr] = tt
            cover_level[mask_arr] = cl
            concealment[mask_arr] = conc

        # Log statistics
        unique, counts = np.unique(terrain_type, return_counts=True)
        total = terrain_type.size
        for tt, count in zip(unique, counts):
            pct = count / total * 100
            name = TerrainType(tt).name if tt in [e.value for e in TerrainType] else "Unknown"
            logger.info(f"  {name}: {pct:.1f}%")

        return {
            'terrain_type': terrain_type,
            'cover_level': cover_level,
            'concealment': concealment,
        }

    def _resample_categorical(
        self,
        data: NDArray[np.uint8],
        target_shape: tuple[int, int],
    ) -> NDArray[np.uint8]:
        """
        Resample categorical data using majority filter.

        Args:
            data: Source categorical array
            target_shape: Target shape (rows, cols)

        Returns:
            Resampled categorical array
        """
        src_rows, src_cols = data.shape
        dst_rows, dst_cols = target_shape

        result = np.zeros(target_shape, dtype=data.dtype)

        # Calculate block sizes
        row_ratio = src_rows / dst_rows
        col_ratio = src_cols / dst_cols

        for i in range(dst_rows):
            for j in range(dst_cols):
                # Source block bounds
                r0 = int(i * row_ratio)
                r1 = min(int((i + 1) * row_ratio), src_rows)
                c0 = int(j * col_ratio)
                c1 = min(int((j + 1) * col_ratio), src_cols)

                # Get block and find most common value
                block = data[r0:r1, c0:c1].flatten()
                if len(block) > 0:
                    values, counts = np.unique(block, return_counts=True)
                    result[i, j] = values[np.argmax(counts)]

        return result

    def compute_forest_density(
        self,
        terrain_type: NDArray[np.int8],
        window_size: int = 5,
    ) -> NDArray[np.float32]:
        """
        Compute local forest density using a moving window.

        Args:
            terrain_type: Terrain type array
            window_size: Size of the analysis window

        Returns:
            Forest density array (0-1)
        """
        from scipy.ndimage import uniform_filter

        forest_mask = (terrain_type == TerrainType.Forest).astype(np.float32)
        density = uniform_filter(forest_mask, size=window_size, mode='nearest')
        return density
