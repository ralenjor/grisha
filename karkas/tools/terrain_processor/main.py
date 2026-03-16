#!/usr/bin/env python3
"""
Terrain Processor CLI - Download and process GIS data for KARKAS terrain engine.

Usage:
    terrain-processor process --region fulda_gap --output data/terrain/
    terrain-processor download --region fulda_gap --source srtm,worldcover,osm
    terrain-processor tile --input data/terrain/raw --resolution 100 --output data/terrain/operational
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from .config import load_config, TerrainProcessorConfig
from .models import BoundingBox, get_region, PREDEFINED_REGIONS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="terrain-processor",
        description="Download and process GIS data for KARKAS terrain engine",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Process command (full pipeline)
    process_parser = subparsers.add_parser(
        "process",
        help="Run full pipeline: download, process, and tile terrain data",
    )
    _add_region_args(process_parser)
    process_parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("data/terrain"),
        help="Output directory for processed terrain",
    )
    process_parser.add_argument(
        "--resolution",
        type=int,
        default=100,
        help="Output resolution in meters (default: 100)",
    )
    process_parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download step (use cached data)",
    )

    # Download command
    download_parser = subparsers.add_parser(
        "download",
        help="Download raw terrain data for a region",
    )
    _add_region_args(download_parser)
    download_parser.add_argument(
        "--source",
        type=str,
        default="srtm,worldcover,osm",
        help="Comma-separated data sources to download (default: srtm,worldcover,osm)",
    )
    download_parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Directory to cache downloaded data",
    )

    # Tile command
    tile_parser = subparsers.add_parser(
        "tile",
        help="Generate terrain tiles from processed data",
    )
    tile_parser.add_argument(
        "--input", "-i",
        type=Path,
        required=True,
        help="Input directory with processed terrain data",
    )
    tile_parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output directory for terrain tiles",
    )
    tile_parser.add_argument(
        "--resolution",
        type=int,
        default=100,
        help="Output resolution in meters (default: 100)",
    )
    _add_region_args(tile_parser)

    # List regions command
    subparsers.add_parser(
        "list-regions",
        help="List available predefined regions",
    )

    return parser


def _add_region_args(parser: argparse.ArgumentParser) -> None:
    """Add region specification arguments to a parser."""
    region_group = parser.add_mutually_exclusive_group(required=False)
    region_group.add_argument(
        "--region",
        type=str,
        help="Predefined region name (e.g., fulda_gap, suwalki_gap)",
    )
    region_group.add_argument(
        "--bounds",
        type=str,
        help="Custom bounds as 'south,west,north,east'",
    )


def parse_bounds(bounds_str: str) -> BoundingBox:
    """Parse bounds string to BoundingBox."""
    try:
        parts = [float(x.strip()) for x in bounds_str.split(",")]
        if len(parts) != 4:
            raise ValueError("Bounds must have exactly 4 values")
        return BoundingBox(
            south=parts[0],
            west=parts[1],
            north=parts[2],
            east=parts[3],
        )
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid bounds format: {bounds_str}. Expected 'south,west,north,east'") from e


def get_bounds_from_args(args: argparse.Namespace) -> Optional[BoundingBox]:
    """Extract bounding box from command line arguments."""
    if hasattr(args, 'region') and args.region:
        region = get_region(args.region)
        return region.bounds
    elif hasattr(args, 'bounds') and args.bounds:
        return parse_bounds(args.bounds)
    return None


def cmd_process(args: argparse.Namespace, config: TerrainProcessorConfig) -> int:
    """Run the full processing pipeline."""
    bounds = get_bounds_from_args(args)
    if bounds is None:
        logger.error("Either --region or --bounds must be specified")
        return 1

    region_name = args.region if hasattr(args, 'region') and args.region else "custom"
    logger.info(f"Processing region: {region_name}")
    logger.info(f"Bounds: {bounds.south:.4f},{bounds.west:.4f},{bounds.north:.4f},{bounds.east:.4f}")
    logger.info(f"Output resolution: {args.resolution}m")

    # Import processors here to avoid import errors if deps not installed
    try:
        from .downloaders import SRTMDownloader, WorldCoverDownloader, OSMDownloader
        from .processors import ElevationProcessor, LandcoverProcessor, RoadsProcessor, UrbanProcessor
        from .tiler import TerrainTiler
        from .gpkg_writer import GeoPackageWriter
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Install with: pip install rasterio fiona geopandas")
        return 1

    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = config.download.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Download data
    if not args.skip_download:
        logger.info("Step 1/4: Downloading raw data...")

        srtm = SRTMDownloader(cache_dir / "srtm", config)
        srtm.download(bounds)

        worldcover = WorldCoverDownloader(cache_dir / "worldcover", config)
        worldcover.download(bounds)

        osm = OSMDownloader(cache_dir / "osm", config)
        osm_extract = None
        if hasattr(args, 'region') and args.region:
            osm_extract = get_region(args.region).osm_extract
        osm.download(bounds, extract_name=osm_extract)
    else:
        logger.info("Step 1/4: Skipping download (using cached data)")

    # Step 2: Process elevation
    logger.info("Step 2/4: Processing elevation data...")
    elevation_proc = ElevationProcessor(cache_dir / "srtm")
    elevation_data, slope_data = elevation_proc.process(bounds, args.resolution)

    # Step 3: Process land cover and roads
    logger.info("Step 3/4: Processing land cover and infrastructure...")
    landcover_proc = LandcoverProcessor(cache_dir / "worldcover")
    landcover_data = landcover_proc.process(bounds, args.resolution)

    roads_proc = RoadsProcessor(cache_dir / "osm")
    road_data = roads_proc.process(bounds, args.resolution)

    urban_proc = UrbanProcessor(cache_dir / "osm")
    urban_data = urban_proc.process(bounds, args.resolution)

    # Step 4: Generate tiles and write GeoPackage
    logger.info("Step 4/4: Generating terrain tiles...")
    tiler = TerrainTiler(args.resolution)
    terrain_cells = tiler.create_cells(
        bounds=bounds,
        elevation=elevation_data,
        slope=slope_data,
        landcover=landcover_data,
        roads=road_data,
        urban=urban_data,
    )

    output_file = output_dir / f"{region_name}.gpkg"
    writer = GeoPackageWriter(output_file)
    writer.write(terrain_cells, roads=road_data.get('geometries'))

    logger.info(f"Terrain data written to: {output_file}")
    logger.info(f"Total cells: {len(terrain_cells)}")

    return 0


def cmd_download(args: argparse.Namespace, config: TerrainProcessorConfig) -> int:
    """Download raw terrain data."""
    bounds = get_bounds_from_args(args)
    if bounds is None:
        logger.error("Either --region or --bounds must be specified")
        return 1

    sources = [s.strip().lower() for s in args.source.split(",")]
    cache_dir = args.cache_dir or config.download.cache_dir

    logger.info(f"Downloading sources: {', '.join(sources)}")
    logger.info(f"Cache directory: {cache_dir}")

    try:
        from .downloaders import SRTMDownloader, WorldCoverDownloader, OSMDownloader
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        return 1

    if "srtm" in sources:
        logger.info("Downloading SRTM elevation data...")
        srtm = SRTMDownloader(cache_dir / "srtm", config)
        srtm.download(bounds)

    if "worldcover" in sources:
        logger.info("Downloading ESA WorldCover data...")
        worldcover = WorldCoverDownloader(cache_dir / "worldcover", config)
        worldcover.download(bounds)

    if "osm" in sources:
        logger.info("Downloading OpenStreetMap data...")
        osm = OSMDownloader(cache_dir / "osm", config)
        osm_extract = None
        if hasattr(args, 'region') and args.region:
            osm_extract = get_region(args.region).osm_extract
        osm.download(bounds, extract_name=osm_extract)

    logger.info("Download complete")
    return 0


def cmd_tile(args: argparse.Namespace, config: TerrainProcessorConfig) -> int:
    """Generate terrain tiles from processed data."""
    bounds = get_bounds_from_args(args)

    if not args.input.exists():
        logger.error(f"Input directory does not exist: {args.input}")
        return 1

    logger.info(f"Generating tiles at {args.resolution}m resolution")
    logger.info(f"Input: {args.input}")
    logger.info(f"Output: {args.output}")

    try:
        from .tiler import TerrainTiler
        from .gpkg_writer import GeoPackageWriter
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        return 1

    args.output.mkdir(parents=True, exist_ok=True)

    tiler = TerrainTiler(args.resolution)
    terrain_cells = tiler.load_and_tile(args.input, bounds)

    output_file = args.output / "terrain.gpkg"
    writer = GeoPackageWriter(output_file)
    writer.write(terrain_cells)

    logger.info(f"Tiles written to: {output_file}")
    return 0


def cmd_list_regions(args: argparse.Namespace, config: TerrainProcessorConfig) -> int:
    """List available predefined regions."""
    print("\nAvailable predefined regions:\n")
    for name, region in PREDEFINED_REGIONS.items():
        bounds = region.bounds
        print(f"  {name}:")
        print(f"    Description: {region.description}")
        print(f"    Bounds: {bounds.south:.2f},{bounds.west:.2f},{bounds.north:.2f},{bounds.east:.2f}")
        if region.osm_extract:
            print(f"    OSM Extract: {region.osm_extract}")
        print()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    config = load_config(args.config)

    commands = {
        "process": cmd_process,
        "download": cmd_download,
        "tile": cmd_tile,
        "list-regions": cmd_list_regions,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args, config)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
