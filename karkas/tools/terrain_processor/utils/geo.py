"""Geographic coordinate utilities."""

import math
import numpy as np
from numpy.typing import NDArray

# Earth's radius in meters
EARTH_RADIUS_M = 6_371_000


def lat_lon_to_meters(lat: float) -> tuple[float, float]:
    """
    Calculate meters per degree at a given latitude.

    Args:
        lat: Latitude in degrees

    Returns:
        Tuple of (meters_per_degree_lon, meters_per_degree_lat)
    """
    lat_rad = math.radians(lat)

    # Meters per degree latitude (approximately constant)
    m_per_deg_lat = 111132.92 - 559.82 * math.cos(2 * lat_rad) + 1.175 * math.cos(4 * lat_rad)

    # Meters per degree longitude (varies with latitude)
    m_per_deg_lon = 111412.84 * math.cos(lat_rad) - 93.5 * math.cos(3 * lat_rad)

    return m_per_deg_lon, m_per_deg_lat


def meters_to_lat_lon(meters: float, lat: float) -> tuple[float, float]:
    """
    Convert meters to degrees at a given latitude.

    Args:
        meters: Distance in meters
        lat: Reference latitude

    Returns:
        Tuple of (degrees_lon, degrees_lat) equivalent to the given meters
    """
    m_per_deg_lon, m_per_deg_lat = lat_lon_to_meters(lat)
    return meters / m_per_deg_lon, meters / m_per_deg_lat


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points.

    Args:
        lat1, lon1: First point coordinates (degrees)
        lat2, lon2: Second point coordinates (degrees)

    Returns:
        Distance in meters
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_M * c


def calculate_slope(dem: NDArray[np.float64], cell_size_m: float) -> NDArray[np.float64]:
    """
    Calculate slope in degrees from a DEM array.

    Uses the Horn algorithm for slope calculation.

    Args:
        dem: 2D numpy array of elevation values
        cell_size_m: Cell size in meters

    Returns:
        2D numpy array of slope values in degrees
    """
    # Pad array to handle edges
    dem_padded = np.pad(dem, 1, mode='edge')

    # Calculate gradients using Horn's method
    # dz/dx = ((c + 2f + i) - (a + 2d + g)) / (8 * cell_size)
    # dz/dy = ((g + 2h + i) - (a + 2b + c)) / (8 * cell_size)

    a = dem_padded[:-2, :-2]
    b = dem_padded[:-2, 1:-1]
    c = dem_padded[:-2, 2:]
    d = dem_padded[1:-1, :-2]
    f = dem_padded[1:-1, 2:]
    g = dem_padded[2:, :-2]
    h = dem_padded[2:, 1:-1]
    i = dem_padded[2:, 2:]

    dz_dx = ((c + 2*f + i) - (a + 2*d + g)) / (8 * cell_size_m)
    dz_dy = ((g + 2*h + i) - (a + 2*b + c)) / (8 * cell_size_m)

    # Calculate slope in degrees
    slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
    slope_deg = np.degrees(slope_rad)

    return slope_deg


def calculate_aspect(dem: NDArray[np.float64], cell_size_m: float) -> NDArray[np.float64]:
    """
    Calculate aspect (direction of slope) from a DEM array.

    Args:
        dem: 2D numpy array of elevation values
        cell_size_m: Cell size in meters

    Returns:
        2D numpy array of aspect values in degrees (0-360, north = 0)
    """
    # Pad array to handle edges
    dem_padded = np.pad(dem, 1, mode='edge')

    a = dem_padded[:-2, :-2]
    b = dem_padded[:-2, 1:-1]
    c = dem_padded[:-2, 2:]
    d = dem_padded[1:-1, :-2]
    f = dem_padded[1:-1, 2:]
    g = dem_padded[2:, :-2]
    h = dem_padded[2:, 1:-1]
    i = dem_padded[2:, 2:]

    dz_dx = ((c + 2*f + i) - (a + 2*d + g)) / (8 * cell_size_m)
    dz_dy = ((g + 2*h + i) - (a + 2*b + c)) / (8 * cell_size_m)

    # Calculate aspect in degrees (0 = north, 90 = east, etc.)
    aspect_rad = np.arctan2(-dz_dx, dz_dy)
    aspect_deg = np.degrees(aspect_rad)

    # Convert to 0-360 range
    aspect_deg = np.where(aspect_deg < 0, aspect_deg + 360, aspect_deg)

    return aspect_deg


def generate_grid_coords(
    bounds: tuple[float, float, float, float],
    resolution_m: float
) -> tuple[NDArray[np.float64], NDArray[np.float64], int, int]:
    """
    Generate a grid of coordinates within bounds at given resolution.

    Args:
        bounds: (west, south, east, north) bounding box
        resolution_m: Cell size in meters

    Returns:
        Tuple of (lon_coords, lat_coords, n_cols, n_rows)
    """
    west, south, east, north = bounds
    center_lat = (south + north) / 2

    # Calculate degrees per cell
    deg_lon, deg_lat = meters_to_lat_lon(resolution_m, center_lat)

    # Generate coordinate arrays
    lon_coords = np.arange(west + deg_lon/2, east, deg_lon)
    lat_coords = np.arange(south + deg_lat/2, north, deg_lat)

    n_cols = len(lon_coords)
    n_rows = len(lat_coords)

    return lon_coords, lat_coords, n_cols, n_rows
