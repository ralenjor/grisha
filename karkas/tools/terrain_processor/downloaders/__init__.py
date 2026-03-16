"""Data downloaders for terrain processing."""

from .base import BaseDownloader
from .srtm import SRTMDownloader
from .worldcover import WorldCoverDownloader
from .osm import OSMDownloader

__all__ = [
    "BaseDownloader",
    "SRTMDownloader",
    "WorldCoverDownloader",
    "OSMDownloader",
]
