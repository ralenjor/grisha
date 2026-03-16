"""Data models for terrain processing."""

from .terrain import TerrainType, CoverLevel, TerrainCell, WORLDCOVER_MAPPING
from .region import BoundingBox, Region, PREDEFINED_REGIONS, get_region

__all__ = [
    "TerrainType",
    "CoverLevel",
    "TerrainCell",
    "WORLDCOVER_MAPPING",
    "BoundingBox",
    "Region",
    "PREDEFINED_REGIONS",
    "get_region",
]
