"""Shared fixtures for integration tests."""
import os
import sys
from pathlib import Path

import pytest


# Add build directory to path for finding karkas_engine module
BUILD_DIR = Path(__file__).parent.parent.parent / "build"
if BUILD_DIR.exists():
    sys.path.insert(0, str(BUILD_DIR))


@pytest.fixture(scope="session")
def karkas_engine():
    """Provide karkas_engine module, skip if not built."""
    return pytest.importorskip(
        "karkas_engine",
        reason="karkas_engine C++ module not built. Run: cd build && cmake .. && make"
    )


@pytest.fixture
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent.parent.parent / "data"


@pytest.fixture
def scenario_dir(test_data_dir):
    """Path to scenarios directory."""
    return test_data_dir / "scenarios"


@pytest.fixture
def terrain_dir(test_data_dir):
    """Path to terrain directory."""
    return test_data_dir / "terrain"
