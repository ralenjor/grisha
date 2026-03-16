"""Region and bounding box definitions."""

from typing import Optional
from pydantic import BaseModel, Field, model_validator


class BoundingBox(BaseModel):
    """
    Geographic bounding box.

    Attributes:
        south: Southern latitude boundary
        west: Western longitude boundary
        north: Northern latitude boundary
        east: Eastern longitude boundary
    """
    south: float = Field(..., ge=-90, le=90)
    west: float = Field(..., ge=-180, le=180)
    north: float = Field(..., ge=-90, le=90)
    east: float = Field(..., ge=-180, le=180)

    @model_validator(mode='after')
    def validate_bounds(self) -> 'BoundingBox':
        if self.south >= self.north:
            raise ValueError("south must be less than north")
        if self.west >= self.east:
            raise ValueError("west must be less than east")
        return self

    @property
    def width_deg(self) -> float:
        """Width in degrees longitude."""
        return self.east - self.west

    @property
    def height_deg(self) -> float:
        """Height in degrees latitude."""
        return self.north - self.south

    @property
    def center_lat(self) -> float:
        """Center latitude."""
        return (self.south + self.north) / 2

    @property
    def center_lon(self) -> float:
        """Center longitude."""
        return (self.west + self.east) / 2

    def contains(self, lat: float, lon: float) -> bool:
        """Check if a point is within this bounding box."""
        return (self.south <= lat <= self.north and
                self.west <= lon <= self.east)

    def to_tuple(self) -> tuple[float, float, float, float]:
        """Return as (west, south, east, north) tuple for GDAL/rasterio."""
        return (self.west, self.south, self.east, self.north)


class Region(BaseModel):
    """
    Named geographic region with metadata.

    Attributes:
        name: Region identifier
        bounds: Geographic bounding box
        description: Human-readable description
        osm_extract: Geofabrik extract name for OSM data
    """
    name: str
    bounds: BoundingBox
    description: Optional[str] = None
    osm_extract: Optional[str] = None


# Predefined regions for common use
PREDEFINED_REGIONS: dict[str, Region] = {
    "fulda_gap": Region(
        name="fulda_gap",
        bounds=BoundingBox(
            south=50.0,
            west=9.0,
            north=51.0,
            east=10.5,
        ),
        description="Fulda Gap region - historic Cold War invasion corridor",
        osm_extract="europe/germany/hessen",
    ),
    "suwalki_gap": Region(
        name="suwalki_gap",
        bounds=BoundingBox(
            south=53.8,
            west=22.5,
            north=54.6,
            east=24.0,
        ),
        description="Suwalki Gap - NATO strategic corridor between Poland and Lithuania",
        osm_extract="europe/poland",
    ),
    "baltic_states": Region(
        name="baltic_states",
        bounds=BoundingBox(
            south=53.5,
            west=20.5,
            north=59.7,
            east=28.5,
        ),
        description="Baltic states - Estonia, Latvia, Lithuania",
        osm_extract="europe/baltic-states",
    ),
    "central_europe": Region(
        name="central_europe",
        bounds=BoundingBox(
            south=47.0,
            west=5.0,
            north=55.0,
            east=15.0,
        ),
        description="Central Europe - Germany, Poland, Czech Republic, Austria",
        osm_extract="europe",
    ),
    "test_small": Region(
        name="test_small",
        bounds=BoundingBox(
            south=50.4,
            west=9.4,
            north=50.6,
            east=9.6,
        ),
        description="Small test region (~20x20 km) in Fulda area",
        osm_extract="europe/germany/hessen",
    ),
}


def get_region(name: str) -> Region:
    """
    Get a predefined region by name.

    Args:
        name: Region identifier

    Returns:
        Region object

    Raises:
        KeyError: If region not found
    """
    if name not in PREDEFINED_REGIONS:
        available = ", ".join(PREDEFINED_REGIONS.keys())
        raise KeyError(f"Unknown region '{name}'. Available: {available}")
    return PREDEFINED_REGIONS[name]
