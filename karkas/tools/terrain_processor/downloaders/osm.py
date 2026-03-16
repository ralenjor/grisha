"""OpenStreetMap data downloader via Geofabrik."""

from pathlib import Path
import logging
from typing import Optional
import subprocess

from .base import BaseDownloader
from ..models import BoundingBox
from ..config import TerrainProcessorConfig

logger = logging.getLogger(__name__)


class OSMDownloader(BaseDownloader):
    """
    Download OpenStreetMap data from Geofabrik.

    Downloads regional extracts in PBF format, then extracts to GeoJSON
    for the specific bounding box.
    """

    # Geofabrik download server
    BASE_URL = "https://download.geofabrik.de/"

    # Common European extracts
    EXTRACTS = {
        "europe": "europe-latest.osm.pbf",
        "europe/germany": "europe/germany-latest.osm.pbf",
        "europe/germany/hessen": "europe/germany/hessen-latest.osm.pbf",
        "europe/poland": "europe/poland-latest.osm.pbf",
        "europe/baltic-states": "europe/baltic-states-latest.osm.pbf",
    }

    def __init__(self, cache_dir: Path, config: TerrainProcessorConfig):
        super().__init__(cache_dir, config)

    @property
    def source_name(self) -> str:
        return "OpenStreetMap"

    def download(
        self,
        bounds: BoundingBox,
        extract_name: Optional[str] = None,
        **kwargs
    ) -> list[Path]:
        """
        Download OSM data for the specified bounds.

        Args:
            bounds: Geographic bounding box
            extract_name: Optional Geofabrik extract name (e.g., "europe/germany/hessen")

        Returns:
            List of paths to downloaded/extracted files
        """
        # Determine which extract to use
        if extract_name is None:
            extract_name = self._find_smallest_extract(bounds)

        if extract_name not in self.EXTRACTS:
            logger.warning(f"Unknown extract: {extract_name}, using full Europe")
            extract_name = "europe"

        pbf_filename = self.EXTRACTS[extract_name]
        pbf_path = self.cache_dir / pbf_filename.replace("/", "_")

        # Download PBF if not cached
        if not pbf_path.exists():
            url = f"{self.BASE_URL}{pbf_filename}"
            logger.info(f"Downloading OSM extract: {extract_name}")
            if not self._retry_download(url, pbf_path):
                return []

        # Extract relevant features to GeoJSON
        extracted_files = self._extract_features(pbf_path, bounds)

        return extracted_files

    def get_tiles_for_bounds(self, bounds: BoundingBox) -> list[str]:
        """OSM uses regional extracts, not tiles."""
        return [self._find_smallest_extract(bounds)]

    def get_tile_path(self, tile_id: str) -> Path:
        """Get path for an OSM extract."""
        return self.cache_dir / f"{tile_id.replace('/', '_')}.osm.pbf"

    def _find_smallest_extract(self, bounds: BoundingBox) -> str:
        """Find the smallest Geofabrik extract that covers the bounds."""
        # For simplicity, use a heuristic based on center point
        center_lat = bounds.center_lat
        center_lon = bounds.center_lon

        # Germany
        if 47 < center_lat < 55 and 5 < center_lon < 15:
            # Hessen (Fulda area)
            if 49 < center_lat < 52 and 7 < center_lon < 11:
                return "europe/germany/hessen"
            return "europe/germany"

        # Poland
        if 49 < center_lat < 55 and 14 < center_lon < 24:
            return "europe/poland"

        # Baltic states
        if 53 < center_lat < 60 and 20 < center_lon < 29:
            return "europe/baltic-states"

        return "europe"

    def _extract_features(self, pbf_path: Path, bounds: BoundingBox) -> list[Path]:
        """
        Extract relevant features from PBF using osmium or ogr2ogr.

        Extracts roads, buildings, and other infrastructure.
        """
        output_files = []

        # Check for osmium-tool
        try:
            subprocess.run(["osmium", "--version"], capture_output=True, check=True)
            has_osmium = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            has_osmium = False
            logger.warning("osmium-tool not found, using ogr2ogr (slower)")

        bounds_str = f"{bounds.west},{bounds.south},{bounds.east},{bounds.north}"

        if has_osmium:
            output_files = self._extract_with_osmium(pbf_path, bounds_str)
        else:
            output_files = self._extract_with_ogr(pbf_path, bounds_str)

        return output_files

    def _extract_with_osmium(self, pbf_path: Path, bounds_str: str) -> list[Path]:
        """Extract features using osmium-tool."""
        # First, extract the bounding box
        clipped_pbf = self.cache_dir / "clipped.osm.pbf"

        try:
            subprocess.run([
                "osmium", "extract",
                "--bbox", bounds_str,
                "--output", str(clipped_pbf),
                "--overwrite",
                str(pbf_path),
            ], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"osmium extract failed: {e.stderr.decode()}")
            return []

        # Export to GeoJSON using osmium export
        roads_path = self.cache_dir / "roads.geojson"
        buildings_path = self.cache_dir / "buildings.geojson"

        # Export roads (highways)
        try:
            subprocess.run([
                "osmium", "tags-filter",
                str(clipped_pbf),
                "w/highway",
                "-o", str(self.cache_dir / "roads.osm.pbf"),
                "--overwrite",
            ], check=True, capture_output=True)

            subprocess.run([
                "osmium", "export",
                str(self.cache_dir / "roads.osm.pbf"),
                "-o", str(roads_path),
                "--overwrite",
            ], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"osmium roads export failed: {e.stderr.decode()}")

        # Export buildings
        try:
            subprocess.run([
                "osmium", "tags-filter",
                str(clipped_pbf),
                "aw/building",
                "-o", str(self.cache_dir / "buildings.osm.pbf"),
                "--overwrite",
            ], check=True, capture_output=True)

            subprocess.run([
                "osmium", "export",
                str(self.cache_dir / "buildings.osm.pbf"),
                "-o", str(buildings_path),
                "--overwrite",
            ], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"osmium buildings export failed: {e.stderr.decode()}")

        # Clean up intermediate files
        for f in ["clipped.osm.pbf", "roads.osm.pbf", "buildings.osm.pbf"]:
            (self.cache_dir / f).unlink(missing_ok=True)

        output = []
        if roads_path.exists():
            output.append(roads_path)
        if buildings_path.exists():
            output.append(buildings_path)

        return output

    def _extract_with_ogr(self, pbf_path: Path, bounds_str: str) -> list[Path]:
        """Extract features using ogr2ogr (GDAL)."""
        roads_path = self.cache_dir / "roads.geojson"
        buildings_path = self.cache_dir / "buildings.geojson"

        west, south, east, north = bounds_str.split(",")

        # Extract roads
        try:
            subprocess.run([
                "ogr2ogr",
                "-f", "GeoJSON",
                str(roads_path),
                str(pbf_path),
                "lines",  # OSM lines layer contains roads
                "-where", "highway IS NOT NULL",
                "-spat", west, south, east, north,
                "-overwrite",
            ], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"ogr2ogr roads extraction failed: {e.stderr.decode()}")

        # Extract buildings
        try:
            subprocess.run([
                "ogr2ogr",
                "-f", "GeoJSON",
                str(buildings_path),
                str(pbf_path),
                "multipolygons",  # Buildings are in multipolygons layer
                "-where", "building IS NOT NULL",
                "-spat", west, south, east, north,
                "-overwrite",
            ], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"ogr2ogr buildings extraction failed: {e.stderr.decode()}")

        output = []
        if roads_path.exists():
            output.append(roads_path)
        if buildings_path.exists():
            output.append(buildings_path)

        return output
