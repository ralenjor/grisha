"""Terrain data models matching C++ TerrainCell structure."""

from enum import IntEnum
from typing import Optional
from pydantic import BaseModel, Field


class TerrainType(IntEnum):
    """Terrain type enumeration matching C++ TerrainType."""
    Open = 0
    Forest = 1
    Urban = 2
    Water = 3
    Mountain = 4
    Marsh = 5
    Desert = 6
    Road = 7
    Bridge = 8


class CoverLevel(IntEnum):
    """Cover level enumeration matching C++ CoverLevel."""
    Non = 0  # 'None' is reserved in Python
    Light = 1
    Medium = 2
    Heavy = 3
    Fortified = 4


class TerrainCell(BaseModel):
    """
    Terrain cell data matching C++ TerrainCell structure.

    Attributes:
        center_lat: Latitude of cell center
        center_lon: Longitude of cell center
        elevation_m: Elevation in meters
        primary_type: Primary terrain type
        secondary_type: Optional secondary terrain type
        cover: Cover level for protection
        concealment: Concealment value (0.0 - 1.0)
        urban_density: Urban density (0.0 - 1.0)
        population: Population count for urban cells
        is_road: Whether cell contains a road
        is_bridge: Whether cell contains a bridge
        is_impassable: Whether cell is impassable
        resolution_m: Cell resolution in meters
    """
    center_lat: float = Field(..., ge=-90, le=90)
    center_lon: float = Field(..., ge=-180, le=180)
    elevation_m: float = 0.0
    primary_type: TerrainType = TerrainType.Open
    secondary_type: Optional[TerrainType] = None
    cover: CoverLevel = CoverLevel.Non
    concealment: float = Field(default=0.0, ge=0.0, le=1.0)
    urban_density: float = Field(default=0.0, ge=0.0, le=1.0)
    population: int = Field(default=0, ge=0)
    is_road: bool = False
    is_bridge: bool = False
    is_impassable: bool = False
    resolution_m: int = 100

    class Config:
        use_enum_values = True


# ESA WorldCover code to terrain mapping
WORLDCOVER_MAPPING: dict[int, tuple[TerrainType, CoverLevel, float]] = {
    # Code: (TerrainType, CoverLevel, Concealment)
    10: (TerrainType.Forest, CoverLevel.Heavy, 0.8),      # Tree cover
    20: (TerrainType.Forest, CoverLevel.Medium, 0.5),     # Shrubland
    30: (TerrainType.Open, CoverLevel.Non, 0.1),          # Grassland
    40: (TerrainType.Open, CoverLevel.Light, 0.2),        # Cropland
    50: (TerrainType.Urban, CoverLevel.Medium, 0.6),      # Built-up
    60: (TerrainType.Desert, CoverLevel.Non, 0.05),       # Bare/sparse
    70: (TerrainType.Open, CoverLevel.Non, 0.0),          # Snow/ice
    80: (TerrainType.Water, CoverLevel.Non, 0.0),         # Water
    90: (TerrainType.Marsh, CoverLevel.Light, 0.3),       # Wetland
    95: (TerrainType.Marsh, CoverLevel.Non, 0.1),         # Mangroves
    100: (TerrainType.Desert, CoverLevel.Non, 0.0),       # Moss/lichen
}


def terrain_from_worldcover(code: int) -> tuple[TerrainType, CoverLevel, float]:
    """
    Convert ESA WorldCover code to terrain properties.

    Args:
        code: ESA WorldCover classification code

    Returns:
        Tuple of (TerrainType, CoverLevel, concealment)
    """
    return WORLDCOVER_MAPPING.get(code, (TerrainType.Open, CoverLevel.Non, 0.1))


def apply_slope_modifiers(
    terrain_type: TerrainType,
    cover: CoverLevel,
    slope_degrees: float
) -> tuple[TerrainType, CoverLevel, bool]:
    """
    Apply slope-based terrain modifiers.

    Args:
        terrain_type: Current terrain type
        cover: Current cover level
        slope_degrees: Slope in degrees

    Returns:
        Tuple of (modified TerrainType, modified CoverLevel, is_impassable)
    """
    is_impassable = False

    if slope_degrees > 45:
        is_impassable = True
        terrain_type = TerrainType.Mountain
        cover = CoverLevel.Heavy
    elif slope_degrees > 30:
        terrain_type = TerrainType.Mountain
        cover = CoverLevel.Heavy
    elif slope_degrees > 15:
        if terrain_type == TerrainType.Open:
            terrain_type = TerrainType.Mountain

    return terrain_type, cover, is_impassable
