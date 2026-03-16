"""Abstract base class for data processors."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import logging

import numpy as np
from numpy.typing import NDArray

from ..models import BoundingBox

logger = logging.getLogger(__name__)


class BaseProcessor(ABC):
    """
    Abstract base class for terrain data processors.

    Processors transform raw downloaded data (GeoTIFF, GeoJSON, etc.)
    into terrain properties usable by the terrain engine.
    """

    def __init__(self, data_dir: Path):
        """
        Initialize the processor.

        Args:
            data_dir: Directory containing downloaded data files
        """
        self.data_dir = data_dir

    @property
    @abstractmethod
    def processor_name(self) -> str:
        """Human-readable name of this processor."""
        pass

    @abstractmethod
    def process(
        self,
        bounds: BoundingBox,
        resolution_m: int,
    ) -> dict[str, Any]:
        """
        Process data for the specified bounds and resolution.

        Args:
            bounds: Geographic bounding box
            resolution_m: Target resolution in meters

        Returns:
            Dictionary of processed data arrays and metadata
        """
        pass

    def find_data_files(self, pattern: str) -> list[Path]:
        """
        Find data files matching a pattern.

        Args:
            pattern: Glob pattern to match

        Returns:
            List of matching file paths
        """
        return list(self.data_dir.glob(pattern))

    def resample_to_grid(
        self,
        data: NDArray[np.float64],
        src_bounds: tuple[float, float, float, float],
        dst_bounds: tuple[float, float, float, float],
        dst_shape: tuple[int, int],
        method: str = "nearest",
    ) -> NDArray[np.float64]:
        """
        Resample a data array to a target grid.

        Args:
            data: Source data array
            src_bounds: Source bounds (west, south, east, north)
            dst_bounds: Destination bounds
            dst_shape: Destination shape (rows, cols)
            method: Resampling method ('nearest', 'bilinear', 'cubic')

        Returns:
            Resampled data array
        """
        from scipy.ndimage import zoom, map_coordinates

        src_height, src_width = data.shape
        dst_height, dst_width = dst_shape

        # Calculate scale factors
        y_scale = dst_height / src_height
        x_scale = dst_width / src_width

        if method == "nearest":
            order = 0
        elif method == "bilinear":
            order = 1
        elif method == "cubic":
            order = 3
        else:
            order = 0

        resampled = zoom(data, (y_scale, x_scale), order=order)

        # Ensure exact shape
        if resampled.shape != dst_shape:
            resampled = resampled[:dst_height, :dst_width]

        return resampled

    def get_grid_shape(
        self,
        bounds: BoundingBox,
        resolution_m: int,
    ) -> tuple[int, int]:
        """
        Calculate grid dimensions for given bounds and resolution.

        Args:
            bounds: Geographic bounding box
            resolution_m: Cell size in meters

        Returns:
            Tuple of (n_rows, n_cols)
        """
        from ..utils.geo import lat_lon_to_meters

        center_lat = bounds.center_lat
        m_per_deg_lon, m_per_deg_lat = lat_lon_to_meters(center_lat)

        width_m = bounds.width_deg * m_per_deg_lon
        height_m = bounds.height_deg * m_per_deg_lat

        n_cols = int(width_m / resolution_m)
        n_rows = int(height_m / resolution_m)

        return n_rows, n_cols
