"""ESA WorldCover land cover data downloader."""

import math
from pathlib import Path
import logging

from .base import BaseDownloader
from ..models import BoundingBox
from ..config import TerrainProcessorConfig

logger = logging.getLogger(__name__)


class WorldCoverDownloader(BaseDownloader):
    """
    Download ESA WorldCover 10m land cover data.

    WorldCover tiles are 3x3 degrees and named by their center.
    Example: ESA_WorldCover_10m_2021_v200_N51E009_Map.tif
    """

    # ESA WorldCover S3 bucket (public, no auth required)
    BASE_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"

    def __init__(self, cache_dir: Path, config: TerrainProcessorConfig):
        super().__init__(cache_dir, config)

    @property
    def source_name(self) -> str:
        return "ESA WorldCover 10m"

    def download(self, bounds: BoundingBox, **kwargs) -> list[Path]:
        """
        Download WorldCover tiles for the specified bounds.

        Args:
            bounds: Geographic bounding box

        Returns:
            List of paths to downloaded GeoTIFF files
        """
        tiles = self.get_tiles_for_bounds(bounds)
        logger.info(f"Downloading {len(tiles)} WorldCover tiles")

        downloaded = []
        for tile_id in tiles:
            tile_path = self.get_tile_path(tile_id)

            if self.is_cached(tile_id):
                logger.debug(f"Using cached tile: {tile_id}")
                downloaded.append(tile_path)
                continue

            url = self._get_tile_url(tile_id)
            if self._retry_download(url, tile_path):
                downloaded.append(tile_path)
            else:
                logger.warning(f"Failed to download tile {tile_id}")

        return downloaded

    def get_tiles_for_bounds(self, bounds: BoundingBox) -> list[str]:
        """
        Get list of WorldCover tile identifiers for the bounding box.

        WorldCover tiles are 3x3 degrees, named by their lower-left corner.
        Tiles are at intervals of 3 degrees: ..., -3, 0, 3, 6, 9, ...
        """
        tiles = []

        # Find the 3-degree grid cells that cover our bounds
        lat_start = (math.floor(bounds.south / 3)) * 3
        lat_end = (math.ceil(bounds.north / 3)) * 3
        lon_start = (math.floor(bounds.west / 3)) * 3
        lon_end = (math.ceil(bounds.east / 3)) * 3

        for lat in range(lat_start, lat_end, 3):
            for lon in range(lon_start, lon_end, 3):
                tile_id = self._format_tile_id(lat, lon)
                tiles.append(tile_id)

        return tiles

    def get_tile_path(self, tile_id: str) -> Path:
        """Get path for a WorldCover tile."""
        return self.cache_dir / f"{tile_id}.tif"

    def _format_tile_id(self, lat: int, lon: int) -> str:
        """Format latitude/longitude to WorldCover tile ID."""
        lat_prefix = "N" if lat >= 0 else "S"
        lon_prefix = "E" if lon >= 0 else "W"
        return f"{lat_prefix}{abs(lat):02d}{lon_prefix}{abs(lon):03d}"

    def _get_tile_url(self, tile_id: str) -> str:
        """Get download URL for a WorldCover tile."""
        # ESA WorldCover filename format
        filename = f"ESA_WorldCover_10m_2021_v200_{tile_id}_Map.tif"
        return f"{self.BASE_URL}{filename}"


class WorldCoverProcessor:
    """Process WorldCover GeoTIFFs into terrain properties."""

    # WorldCover class codes
    CLASSES = {
        10: "Tree cover",
        20: "Shrubland",
        30: "Grassland",
        40: "Cropland",
        50: "Built-up",
        60: "Bare / sparse vegetation",
        70: "Snow and ice",
        80: "Permanent water bodies",
        90: "Herbaceous wetland",
        95: "Mangroves",
        100: "Moss and lichen",
    }

    @staticmethod
    def merge_tiles(tiles: list[Path], bounds: BoundingBox, output: Path) -> Path:
        """
        Merge multiple WorldCover tiles and clip to bounds.

        Args:
            tiles: List of tile paths
            bounds: Bounding box to clip to
            output: Output file path

        Returns:
            Path to merged/clipped GeoTIFF
        """
        import rasterio
        from rasterio.merge import merge
        from rasterio.mask import mask
        from shapely.geometry import box

        if len(tiles) == 1:
            # Just clip the single tile
            src_path = tiles[0]
        else:
            # Merge tiles first
            datasets = [rasterio.open(p) for p in tiles]
            mosaic, out_transform = merge(datasets)

            for ds in datasets:
                ds.close()

            # Write temporary merged file
            merged_path = output.with_suffix('.merged.tif')
            with rasterio.open(
                merged_path, 'w',
                driver='GTiff',
                height=mosaic.shape[1],
                width=mosaic.shape[2],
                count=1,
                dtype=mosaic.dtype,
                crs='EPSG:4326',
                transform=out_transform,
                compress='lzw',
            ) as dst:
                dst.write(mosaic)

            src_path = merged_path

        # Clip to bounds
        bbox = box(bounds.west, bounds.south, bounds.east, bounds.north)

        with rasterio.open(src_path) as src:
            clipped, clipped_transform = mask(src, [bbox], crop=True)

            with rasterio.open(
                output, 'w',
                driver='GTiff',
                height=clipped.shape[1],
                width=clipped.shape[2],
                count=1,
                dtype=clipped.dtype,
                crs=src.crs,
                transform=clipped_transform,
                compress='lzw',
            ) as dst:
                dst.write(clipped)

        # Clean up merged file if we created one
        if len(tiles) > 1 and merged_path.exists():
            merged_path.unlink()

        return output
