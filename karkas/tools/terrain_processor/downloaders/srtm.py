"""SRTM (Shuttle Radar Topography Mission) elevation data downloader."""

import math
from pathlib import Path
import logging
from typing import Optional

from .base import BaseDownloader
from ..models import BoundingBox
from ..config import TerrainProcessorConfig

logger = logging.getLogger(__name__)


class SRTMDownloader(BaseDownloader):
    """
    Download SRTM 30m elevation data.

    SRTM tiles are 1x1 degree and named by their southwest corner.
    Example: N50E009 covers 50-51°N, 9-10°E
    """

    # Alternative free mirror that doesn't require authentication
    SRTM_BASE_URL = "https://srtm.csi.cgiar.org/wp-content/uploads/files/srtm_5x5/TIFF/"

    # OpenTopography mirror (requires free registration)
    OPENTOPO_URL = "https://portal.opentopography.org/API/globaldem"

    def __init__(self, cache_dir: Path, config: TerrainProcessorConfig):
        super().__init__(cache_dir, config)
        self.use_cgiar = True  # Use CGIAR mirror by default (no auth required)

    @property
    def source_name(self) -> str:
        return "SRTM 30m Elevation"

    def download(self, bounds: BoundingBox, **kwargs) -> list[Path]:
        """
        Download SRTM tiles for the specified bounds.

        Args:
            bounds: Geographic bounding box

        Returns:
            List of paths to downloaded GeoTIFF files
        """
        tiles = self.get_tiles_for_bounds(bounds)
        logger.info(f"Downloading {len(tiles)} SRTM tiles")

        downloaded = []
        for tile_id in tiles:
            tile_path = self.get_tile_path(tile_id)

            if self.is_cached(tile_id):
                logger.debug(f"Using cached tile: {tile_id}")
                downloaded.append(tile_path)
                continue

            if self.use_cgiar:
                success = self._download_cgiar_tile(tile_id, tile_path)
            else:
                success = self._download_nasa_tile(tile_id, tile_path)

            if success:
                downloaded.append(tile_path)
            else:
                logger.warning(f"Failed to download tile {tile_id}")

        return downloaded

    def get_tiles_for_bounds(self, bounds: BoundingBox) -> list[str]:
        """
        Get list of SRTM tile identifiers for the bounding box.

        SRTM tiles are named by their southwest corner: N50E009
        """
        tiles = []

        # Iterate through all 1x1 degree tiles that intersect bounds
        for lat in range(math.floor(bounds.south), math.ceil(bounds.north)):
            for lon in range(math.floor(bounds.west), math.ceil(bounds.east)):
                tile_id = self._format_tile_id(lat, lon)
                tiles.append(tile_id)

        return tiles

    def get_tile_path(self, tile_id: str) -> Path:
        """Get path for an SRTM tile."""
        return self.cache_dir / f"{tile_id}.tif"

    def _format_tile_id(self, lat: int, lon: int) -> str:
        """Format latitude/longitude to SRTM tile ID."""
        lat_prefix = "N" if lat >= 0 else "S"
        lon_prefix = "E" if lon >= 0 else "W"
        return f"{lat_prefix}{abs(lat):02d}{lon_prefix}{abs(lon):03d}"

    def _get_cgiar_tile_name(self, lat: int, lon: int) -> Optional[str]:
        """
        Convert lat/lon to CGIAR SRTM 5x5 tile name.

        CGIAR uses a different naming scheme: srtm_XX_YY
        where XX and YY are tile indices.
        """
        # CGIAR tiles are 5x5 degrees, starting from (-180, 60)
        # Tile indices run from 01-72 (lon) and 01-24 (lat)
        if lat < -60 or lat >= 60:
            return None  # SRTM doesn't cover polar regions

        tile_x = int((lon + 180) / 5) + 1
        tile_y = int((60 - lat) / 5)

        if tile_y == 0:
            tile_y = 1

        return f"srtm_{tile_x:02d}_{tile_y:02d}"

    def _download_cgiar_tile(self, tile_id: str, dest: Path) -> bool:
        """
        Download from CGIAR mirror.

        Note: CGIAR tiles are 5x5 degree tiles, so we need to
        convert the 1x1 degree tile_id to the appropriate CGIAR tile.
        """
        # Parse tile_id to get lat/lon
        lat_prefix = tile_id[0]
        lat = int(tile_id[1:3])
        if lat_prefix == 'S':
            lat = -lat

        lon_prefix = tile_id[3]
        lon = int(tile_id[4:7])
        if lon_prefix == 'W':
            lon = -lon

        cgiar_name = self._get_cgiar_tile_name(lat, lon)
        if cgiar_name is None:
            logger.warning(f"Tile {tile_id} outside SRTM coverage")
            return False

        # CGIAR provides zipped TIFFs
        url = f"{self.SRTM_BASE_URL}{cgiar_name}.zip"
        zip_path = self.cache_dir / f"{cgiar_name}.zip"

        # Check if we already have this 5x5 tile
        cgiar_tif = self.cache_dir / f"{cgiar_name}.tif"
        if cgiar_tif.exists():
            # Create a symlink for the specific 1x1 tile
            if not dest.exists():
                dest.symlink_to(cgiar_tif)
            return True

        # Download and extract
        if not self._retry_download(url, zip_path):
            return False

        # Extract the TIF
        import zipfile
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                for name in zf.namelist():
                    if name.endswith('.tif'):
                        zf.extract(name, self.cache_dir)
                        extracted = self.cache_dir / name
                        if extracted != cgiar_tif:
                            extracted.rename(cgiar_tif)
                        break

            # Create symlink for the specific tile
            if not dest.exists():
                dest.symlink_to(cgiar_tif)

            # Clean up zip
            zip_path.unlink()
            return True

        except zipfile.BadZipFile:
            logger.error(f"Invalid zip file: {zip_path}")
            zip_path.unlink()
            return False

    def _download_nasa_tile(self, tile_id: str, dest: Path) -> bool:
        """
        Download from NASA Earthdata (requires .netrc auth).

        This is the official source but requires a free account.
        """
        # NASA SRTM GL1 format
        url = f"{self.config.download.srtm_url}{tile_id}.SRTMGL1.hgt.zip"

        zip_path = dest.with_suffix('.hgt.zip')
        if not self._retry_download(url, zip_path):
            return False

        # Extract HGT file and convert to GeoTIFF
        import zipfile
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                hgt_name = f"{tile_id}.hgt"
                zf.extract(hgt_name, self.cache_dir)

            # Convert HGT to GeoTIFF using rasterio
            self._hgt_to_geotiff(self.cache_dir / hgt_name, dest)

            # Clean up
            (self.cache_dir / hgt_name).unlink()
            zip_path.unlink()
            return True

        except (zipfile.BadZipFile, Exception) as e:
            logger.error(f"Error processing {tile_id}: {e}")
            return False

    def _hgt_to_geotiff(self, hgt_path: Path, tif_path: Path) -> None:
        """Convert SRTM HGT format to GeoTIFF."""
        import numpy as np
        import rasterio
        from rasterio.crs import CRS
        from rasterio.transform import from_bounds

        # Parse tile location from filename
        name = hgt_path.stem
        lat_prefix = name[0]
        lat = int(name[1:3])
        if lat_prefix == 'S':
            lat = -lat

        lon_prefix = name[3]
        lon = int(name[4:7])
        if lon_prefix == 'W':
            lon = -lon

        # SRTM 1 arc-second = 3601x3601 pixels for 1 degree
        size = 3601
        data = np.fromfile(hgt_path, dtype='>i2').reshape((size, size))

        # Create GeoTIFF
        transform = from_bounds(lon, lat, lon + 1, lat + 1, size, size)

        with rasterio.open(
            tif_path, 'w',
            driver='GTiff',
            height=size,
            width=size,
            count=1,
            dtype=data.dtype,
            crs=CRS.from_epsg(4326),
            transform=transform,
            compress='lzw',
        ) as dst:
            dst.write(data, 1)
