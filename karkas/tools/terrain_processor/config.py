"""Configuration handling for terrain processor."""

from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel, Field


class DownloadConfig(BaseModel):
    """Download configuration settings."""
    cache_dir: Path = Field(default=Path("data/terrain/raw"))
    srtm_url: str = "https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11/"
    worldcover_url: str = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
    osm_mirror: str = "https://download.geofabrik.de/"
    timeout_seconds: int = 300
    max_retries: int = 3


class ProcessingConfig(BaseModel):
    """Processing configuration settings."""
    default_resolution_m: int = 100
    tactical_resolution_m: int = 10
    nodata_value: float = -9999.0
    use_parallel: bool = True
    max_workers: int = 4


class OutputConfig(BaseModel):
    """Output configuration settings."""
    output_dir: Path = Field(default=Path("data/terrain"))
    operational_subdir: str = "operational"
    tactical_subdir: str = "tactical"
    create_spatial_index: bool = True
    compress_output: bool = True


class TerrainProcessorConfig(BaseModel):
    """Main configuration for terrain processor."""
    download: DownloadConfig = Field(default_factory=DownloadConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "TerrainProcessorConfig":
        """Load configuration from YAML file."""
        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f)

        if data is None:
            return cls()

        return cls(**data)

    def to_yaml(self, path: Path) -> None:
        """Save configuration to YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump(self.model_dump(mode='json'), f, default_flow_style=False)


# Default config file location
DEFAULT_CONFIG_PATH = Path("config/terrain_processor.yaml")


def load_config(config_path: Optional[Path] = None) -> TerrainProcessorConfig:
    """
    Load terrain processor configuration.

    Args:
        config_path: Optional path to config file. Uses default if not specified.

    Returns:
        Configuration object
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    return TerrainProcessorConfig.from_yaml(config_path)


def get_cache_dir(config: TerrainProcessorConfig, source: str) -> Path:
    """
    Get cache directory for a specific data source.

    Args:
        config: Configuration object
        source: Data source name (srtm, worldcover, osm)

    Returns:
        Path to cache directory
    """
    cache_dir = config.download.cache_dir / source
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_output_dir(config: TerrainProcessorConfig, resolution_m: int) -> Path:
    """
    Get output directory for a specific resolution.

    Args:
        config: Configuration object
        resolution_m: Target resolution in meters

    Returns:
        Path to output directory
    """
    if resolution_m <= config.processing.tactical_resolution_m:
        subdir = config.output.tactical_subdir
    else:
        subdir = config.output.operational_subdir

    output_dir = config.output.output_dir / subdir
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
