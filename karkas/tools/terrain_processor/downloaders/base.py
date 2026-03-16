"""Abstract base class for data downloaders."""

from abc import ABC, abstractmethod
from pathlib import Path
import logging

from ..models import BoundingBox
from ..config import TerrainProcessorConfig

logger = logging.getLogger(__name__)


class BaseDownloader(ABC):
    """
    Abstract base class for terrain data downloaders.

    Subclasses implement specific download logic for different data sources
    (SRTM, WorldCover, OSM, etc.).
    """

    def __init__(self, cache_dir: Path, config: TerrainProcessorConfig):
        """
        Initialize the downloader.

        Args:
            cache_dir: Directory to cache downloaded files
            config: Terrain processor configuration
        """
        self.cache_dir = cache_dir
        self.config = config
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name of the data source."""
        pass

    @abstractmethod
    def download(self, bounds: BoundingBox, **kwargs) -> list[Path]:
        """
        Download data for the specified bounding box.

        Args:
            bounds: Geographic bounding box to download
            **kwargs: Additional source-specific options

        Returns:
            List of paths to downloaded files
        """
        pass

    @abstractmethod
    def get_tiles_for_bounds(self, bounds: BoundingBox) -> list[str]:
        """
        Get list of tile identifiers needed to cover the bounding box.

        Args:
            bounds: Geographic bounding box

        Returns:
            List of tile identifiers (format varies by source)
        """
        pass

    def is_cached(self, tile_id: str) -> bool:
        """
        Check if a tile is already cached.

        Args:
            tile_id: Tile identifier

        Returns:
            True if tile is already downloaded
        """
        return self.get_tile_path(tile_id).exists()

    @abstractmethod
    def get_tile_path(self, tile_id: str) -> Path:
        """
        Get the local file path for a tile.

        Args:
            tile_id: Tile identifier

        Returns:
            Path where the tile is/will be stored
        """
        pass

    def _download_file(self, url: str, dest: Path, chunk_size: int = 8192) -> None:
        """
        Download a file with progress reporting.

        Args:
            url: URL to download
            dest: Destination file path
            chunk_size: Download chunk size in bytes
        """
        import requests
        from tqdm import tqdm

        dest.parent.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Downloading {url} to {dest}")

        response = requests.get(
            url,
            stream=True,
            timeout=self.config.download.timeout_seconds,
        )
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))

        with open(dest, 'wb') as f:
            with tqdm(
                total=total_size,
                unit='B',
                unit_scale=True,
                desc=dest.name,
                disable=total_size == 0,
            ) as pbar:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

    def _retry_download(self, url: str, dest: Path) -> bool:
        """
        Download with retries.

        Args:
            url: URL to download
            dest: Destination file path

        Returns:
            True if download succeeded
        """
        import time
        from requests.exceptions import RequestException

        for attempt in range(self.config.download.max_retries):
            try:
                self._download_file(url, dest)
                return True
            except RequestException as e:
                logger.warning(f"Download attempt {attempt + 1} failed: {e}")
                if attempt < self.config.download.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

        logger.error(f"Failed to download {url} after {self.config.download.max_retries} attempts")
        return False
