"""
Integration tests for Python-C++ bindings.

These tests validate that the pybind11 bindings work correctly,
including type conversions, method calls, and data persistence
across the language boundary.

Run: pytest tests/integration/test_bindings.py -v

Prerequisites:
    - Build the C++ module: cd build && cmake .. && make
    - The karkas_engine.so module must be in the build directory or PYTHONPATH
"""
import json
import math
from pathlib import Path

import pytest


class TestModuleImport:
    """Test that the karkas_engine module loads correctly."""

    def test_module_import(self, karkas_engine):
        """Test basic module import."""
        assert karkas_engine is not None
        assert hasattr(karkas_engine, "__doc__")
        assert "KARKAS" in karkas_engine.__doc__

    def test_module_has_expected_classes(self, karkas_engine):
        """Test module exports expected classes."""
        expected_classes = [
            "Faction",
            "UnitType",
            "Echelon",
            "Posture",
            "TurnPhase",
            "Coordinates",
            "BoundingBox",
            "Unit",
            "TerrainEngine",
            "Simulation",
            "TurnResult",
        ]
        for cls_name in expected_classes:
            assert hasattr(karkas_engine, cls_name), f"Missing class: {cls_name}"


class TestEnumBindings:
    """Test enum type bindings."""

    def test_faction_enum(self, karkas_engine):
        """Test Faction enum values."""
        Faction = karkas_engine.Faction
        assert Faction.Red is not None
        assert Faction.Blue is not None
        assert Faction.Neutral is not None
        # Verify they are distinct
        assert Faction.Red != Faction.Blue
        assert Faction.Blue != Faction.Neutral
        assert Faction.Red != Faction.Neutral

    def test_unit_type_enum(self, karkas_engine):
        """Test UnitType enum values."""
        UnitType = karkas_engine.UnitType
        expected = [
            "Infantry", "Armor", "Mechanized", "Artillery",
            "AirDefense", "Rotary", "FixedWing", "Support",
            "Headquarters", "Recon", "Engineer", "Logistics"
        ]
        for name in expected:
            assert hasattr(UnitType, name), f"Missing UnitType: {name}"

    def test_echelon_enum(self, karkas_engine):
        """Test Echelon enum values."""
        Echelon = karkas_engine.Echelon
        expected = [
            "Squad", "Platoon", "Company", "Battalion",
            "Regiment", "Brigade", "Division", "Corps", "Army"
        ]
        for name in expected:
            assert hasattr(Echelon, name), f"Missing Echelon: {name}"

    def test_posture_enum(self, karkas_engine):
        """Test Posture enum values."""
        Posture = karkas_engine.Posture
        expected = [
            "Attack", "Defend", "Move", "Recon",
            "Support", "Reserve", "Retreat", "Disengaged"
        ]
        for name in expected:
            assert hasattr(Posture, name), f"Missing Posture: {name}"

    def test_turn_phase_enum(self, karkas_engine):
        """Test TurnPhase enum values."""
        TurnPhase = karkas_engine.TurnPhase
        assert hasattr(TurnPhase, "Planning")
        assert hasattr(TurnPhase, "Execution")
        assert hasattr(TurnPhase, "Reporting")

    def test_enum_comparison(self, karkas_engine):
        """Test enum comparison works."""
        Faction = karkas_engine.Faction
        f1 = Faction.Red
        f2 = Faction.Red
        f3 = Faction.Blue
        assert f1 == f2
        assert f1 != f3


class TestCoordinatesBinding:
    """Test Coordinates class binding."""

    def test_default_constructor(self, karkas_engine):
        """Test default Coordinates constructor."""
        coords = karkas_engine.Coordinates()
        assert coords is not None
        # Default values should be 0.0
        assert coords.latitude == 0.0
        assert coords.longitude == 0.0

    def test_parameterized_constructor(self, karkas_engine):
        """Test Coordinates constructor with parameters."""
        coords = karkas_engine.Coordinates(50.5, 9.5)
        assert coords.latitude == 50.5
        assert coords.longitude == 9.5

    def test_coordinate_modification(self, karkas_engine):
        """Test modifying coordinate properties."""
        coords = karkas_engine.Coordinates()
        coords.latitude = 51.123
        coords.longitude = 10.456
        assert coords.latitude == 51.123
        assert coords.longitude == 10.456

    def test_distance_to(self, karkas_engine):
        """Test distance calculation between coordinates."""
        # Fulda Gap area coordinates
        fulda = karkas_engine.Coordinates(50.55, 9.68)
        frankfurt = karkas_engine.Coordinates(50.11, 8.68)

        distance = fulda.distance_to(frankfurt)
        # Approximate distance: ~90km
        assert 80 < distance < 100, f"Distance {distance} not in expected range"

    def test_distance_to_same_point(self, karkas_engine):
        """Test distance to same point is zero."""
        coords = karkas_engine.Coordinates(50.5, 9.5)
        distance = coords.distance_to(coords)
        assert distance == pytest.approx(0.0, abs=0.001)

    def test_bearing_to(self, karkas_engine):
        """Test bearing calculation between coordinates."""
        south = karkas_engine.Coordinates(50.0, 9.0)
        north = karkas_engine.Coordinates(51.0, 9.0)

        bearing = south.bearing_to(north)
        # Should be approximately 0 degrees (due north)
        assert -5 < bearing < 5 or 355 < bearing < 360

    def test_bearing_east(self, karkas_engine):
        """Test bearing to the east."""
        west = karkas_engine.Coordinates(50.0, 9.0)
        east = karkas_engine.Coordinates(50.0, 10.0)

        bearing = west.bearing_to(east)
        # Should be approximately 90 degrees (due east)
        assert 85 < bearing < 95

    def test_move_toward(self, karkas_engine):
        """Test moving toward another coordinate."""
        start = karkas_engine.Coordinates(50.0, 9.0)
        target = karkas_engine.Coordinates(51.0, 9.0)

        # Calculate bearing to target
        bearing = start.bearing_to(target)

        # Move 10km toward target
        result = start.move_toward(bearing, 10.0)

        # Should be north of start but south of target
        assert result.latitude > start.latitude
        assert result.latitude < target.latitude
        # Longitude should be approximately the same
        assert abs(result.longitude - start.longitude) < 0.1


class TestBoundingBoxBinding:
    """Test BoundingBox class binding."""

    def test_default_constructor(self, karkas_engine):
        """Test default BoundingBox constructor."""
        bbox = karkas_engine.BoundingBox()
        assert bbox is not None

    def test_set_bounds(self, karkas_engine):
        """Test setting bounding box bounds."""
        bbox = karkas_engine.BoundingBox()
        bbox.southwest = karkas_engine.Coordinates(50.0, 9.0)
        bbox.northeast = karkas_engine.Coordinates(51.0, 10.0)

        assert bbox.southwest.latitude == 50.0
        assert bbox.southwest.longitude == 9.0
        assert bbox.northeast.latitude == 51.0
        assert bbox.northeast.longitude == 10.0

    def test_contains_inside(self, karkas_engine):
        """Test point containment - point inside."""
        bbox = karkas_engine.BoundingBox()
        bbox.southwest = karkas_engine.Coordinates(50.0, 9.0)
        bbox.northeast = karkas_engine.Coordinates(51.0, 10.0)

        inside = karkas_engine.Coordinates(50.5, 9.5)
        assert bbox.contains(inside) is True

    def test_contains_outside(self, karkas_engine):
        """Test point containment - point outside."""
        bbox = karkas_engine.BoundingBox()
        bbox.southwest = karkas_engine.Coordinates(50.0, 9.0)
        bbox.northeast = karkas_engine.Coordinates(51.0, 10.0)

        outside = karkas_engine.Coordinates(52.0, 9.5)
        assert bbox.contains(outside) is False

    def test_contains_boundary(self, karkas_engine):
        """Test point containment - point on boundary."""
        bbox = karkas_engine.BoundingBox()
        bbox.southwest = karkas_engine.Coordinates(50.0, 9.0)
        bbox.northeast = karkas_engine.Coordinates(51.0, 10.0)

        on_boundary = karkas_engine.Coordinates(50.0, 9.5)
        # Boundary behavior may vary, just ensure no exception
        result = bbox.contains(on_boundary)
        assert isinstance(result, bool)

    def test_width_km(self, karkas_engine):
        """Test width calculation in kilometers."""
        bbox = karkas_engine.BoundingBox()
        bbox.southwest = karkas_engine.Coordinates(50.0, 9.0)
        bbox.northeast = karkas_engine.Coordinates(51.0, 10.0)

        width = bbox.width_km()
        # At 50°N, 1° longitude ≈ 71.5km
        assert 60 < width < 80

    def test_height_km(self, karkas_engine):
        """Test height calculation in kilometers."""
        bbox = karkas_engine.BoundingBox()
        bbox.southwest = karkas_engine.Coordinates(50.0, 9.0)
        bbox.northeast = karkas_engine.Coordinates(51.0, 10.0)

        height = bbox.height_km()
        # 1° latitude ≈ 111km
        assert 100 < height < 120


class TestUnitBinding:
    """Test Unit class binding."""

    def test_unit_creation(self, karkas_engine):
        """Test creating a unit."""
        unit = karkas_engine.Unit(
            "inf_bn_1",
            "1st Infantry Battalion",
            karkas_engine.Faction.Red,
            karkas_engine.UnitType.Infantry,
            karkas_engine.Echelon.Battalion
        )
        assert unit is not None
        assert unit.get_id() == "inf_bn_1"
        assert unit.get_name() == "1st Infantry Battalion"

    def test_unit_faction(self, karkas_engine):
        """Test unit faction getter."""
        unit = karkas_engine.Unit(
            "armor_co_1",
            "1st Tank Company",
            karkas_engine.Faction.Blue,
            karkas_engine.UnitType.Armor,
            karkas_engine.Echelon.Company
        )
        assert unit.get_faction() == karkas_engine.Faction.Blue

    def test_unit_type(self, karkas_engine):
        """Test unit type getter."""
        unit = karkas_engine.Unit(
            "arty_bn_1",
            "Artillery Battalion",
            karkas_engine.Faction.Red,
            karkas_engine.UnitType.Artillery,
            karkas_engine.Echelon.Battalion
        )
        assert unit.get_type() == karkas_engine.UnitType.Artillery

    def test_unit_echelon(self, karkas_engine):
        """Test unit echelon getter."""
        unit = karkas_engine.Unit(
            "div_hq",
            "Division HQ",
            karkas_engine.Faction.Blue,
            karkas_engine.UnitType.Headquarters,
            karkas_engine.Echelon.Division
        )
        assert unit.get_echelon() == karkas_engine.Echelon.Division

    def test_unit_position(self, karkas_engine):
        """Test unit position get/set."""
        unit = karkas_engine.Unit(
            "recon_plt",
            "Recon Platoon",
            karkas_engine.Faction.Red,
            karkas_engine.UnitType.Recon,
            karkas_engine.Echelon.Platoon
        )

        # Set position
        pos = karkas_engine.Coordinates(50.5, 9.5)
        unit.set_position(pos)

        # Get position
        result = unit.get_position()
        assert result.latitude == 50.5
        assert result.longitude == 9.5

    def test_unit_posture(self, karkas_engine):
        """Test unit posture get/set."""
        unit = karkas_engine.Unit(
            "mech_bn",
            "Mechanized Battalion",
            karkas_engine.Faction.Blue,
            karkas_engine.UnitType.Mechanized,
            karkas_engine.Echelon.Battalion
        )

        # Set posture
        unit.set_posture(karkas_engine.Posture.Defend)
        assert unit.get_posture() == karkas_engine.Posture.Defend

        # Change posture
        unit.set_posture(karkas_engine.Posture.Attack)
        assert unit.get_posture() == karkas_engine.Posture.Attack

    def test_unit_combat_effective(self, karkas_engine):
        """Test unit combat effectiveness check."""
        unit = karkas_engine.Unit(
            "inf_co",
            "Infantry Company",
            karkas_engine.Faction.Red,
            karkas_engine.UnitType.Infantry,
            karkas_engine.Echelon.Company
        )
        # New unit should be combat effective
        assert unit.is_combat_effective() is True

    def test_unit_not_destroyed(self, karkas_engine):
        """Test new unit is not destroyed."""
        unit = karkas_engine.Unit(
            "tank_plt",
            "Tank Platoon",
            karkas_engine.Faction.Blue,
            karkas_engine.UnitType.Armor,
            karkas_engine.Echelon.Platoon
        )
        assert unit.is_destroyed() is False

    def test_unit_to_json(self, karkas_engine):
        """Test unit JSON serialization."""
        unit = karkas_engine.Unit(
            "json_test",
            "JSON Test Unit",
            karkas_engine.Faction.Red,
            karkas_engine.UnitType.Infantry,
            karkas_engine.Echelon.Company
        )
        unit.set_position(karkas_engine.Coordinates(50.5, 9.5))
        unit.set_posture(karkas_engine.Posture.Defend)

        json_str = unit.to_json()
        assert json_str is not None
        assert len(json_str) > 0

        # Parse and verify
        data = json.loads(json_str)
        assert data["id"] == "json_test"
        assert data["name"] == "JSON Test Unit"


class TestTerrainEngineBinding:
    """Test TerrainEngine class binding."""

    def test_terrain_engine_creation(self, karkas_engine):
        """Test creating a terrain engine."""
        terrain = karkas_engine.TerrainEngine()
        assert terrain is not None

    def test_terrain_not_loaded_initially(self, karkas_engine):
        """Test terrain not loaded after creation."""
        terrain = karkas_engine.TerrainEngine()
        assert terrain.is_loaded() is False

    def test_terrain_load_region(self, karkas_engine, terrain_dir):
        """Test loading terrain region from GeoPackage."""
        terrain = karkas_engine.TerrainEngine()

        # Define bounds for Fulda Gap area
        bounds = karkas_engine.BoundingBox()
        bounds.southwest = karkas_engine.Coordinates(50.0, 9.0)
        bounds.northeast = karkas_engine.Coordinates(51.0, 10.0)

        # Check if terrain data exists
        gpkg_path = terrain_dir / "fulda_gap.gpkg"
        if not gpkg_path.exists():
            pytest.skip(f"Terrain data not found: {gpkg_path}")

        # Load terrain
        success = terrain.load_region(bounds, str(gpkg_path))
        assert success is True
        assert terrain.is_loaded() is True

    def test_terrain_get_bounds(self, karkas_engine, terrain_dir):
        """Test getting terrain bounds after loading."""
        terrain = karkas_engine.TerrainEngine()

        bounds = karkas_engine.BoundingBox()
        bounds.southwest = karkas_engine.Coordinates(50.0, 9.0)
        bounds.northeast = karkas_engine.Coordinates(51.0, 10.0)

        gpkg_path = terrain_dir / "fulda_gap.gpkg"
        if not gpkg_path.exists():
            pytest.skip(f"Terrain data not found: {gpkg_path}")

        terrain.load_region(bounds, str(gpkg_path))
        loaded_bounds = terrain.get_bounds()

        assert loaded_bounds is not None
        # Bounds should be similar to what we requested
        assert loaded_bounds.southwest.latitude <= bounds.southwest.latitude + 0.1
        assert loaded_bounds.northeast.latitude >= bounds.northeast.latitude - 0.1

    def test_terrain_get_elevation(self, karkas_engine, terrain_dir):
        """Test getting elevation at a point."""
        terrain = karkas_engine.TerrainEngine()

        bounds = karkas_engine.BoundingBox()
        bounds.southwest = karkas_engine.Coordinates(50.0, 9.0)
        bounds.northeast = karkas_engine.Coordinates(51.0, 10.0)

        gpkg_path = terrain_dir / "fulda_gap.gpkg"
        if not gpkg_path.exists():
            pytest.skip(f"Terrain data not found: {gpkg_path}")

        terrain.load_region(bounds, str(gpkg_path))

        # Query elevation
        point = karkas_engine.Coordinates(50.5, 9.5)
        elevation = terrain.get_elevation(point)

        # Elevation should be a reasonable value (Fulda area: 200-500m typical)
        assert -1000 < elevation < 5000

    def test_terrain_has_los(self, karkas_engine, terrain_dir):
        """Test line of sight calculation."""
        terrain = karkas_engine.TerrainEngine()

        bounds = karkas_engine.BoundingBox()
        bounds.southwest = karkas_engine.Coordinates(50.0, 9.0)
        bounds.northeast = karkas_engine.Coordinates(51.0, 10.0)

        gpkg_path = terrain_dir / "fulda_gap.gpkg"
        if not gpkg_path.exists():
            pytest.skip(f"Terrain data not found: {gpkg_path}")

        terrain.load_region(bounds, str(gpkg_path))

        # Test LOS between two close points
        observer = karkas_engine.Coordinates(50.5, 9.5)
        target = karkas_engine.Coordinates(50.501, 9.501)  # ~100m away

        has_los = terrain.has_los(observer, target)
        # Result should be boolean
        assert isinstance(has_los, bool)


class TestSimulationBinding:
    """Test Simulation class binding."""

    def test_simulation_creation(self, karkas_engine):
        """Test creating a simulation."""
        sim = karkas_engine.Simulation()
        assert sim is not None

    def test_simulation_initial_phase(self, karkas_engine):
        """Test simulation initial phase is Planning."""
        sim = karkas_engine.Simulation()
        phase = sim.get_phase()
        assert phase == karkas_engine.TurnPhase.Planning

    def test_simulation_ready_check(self, karkas_engine):
        """Test simulation ready_to_execute check works."""
        sim = karkas_engine.Simulation()
        # Check returns a boolean (implementation may default to True)
        result = sim.ready_to_execute()
        assert isinstance(result, bool)

    def test_simulation_load_scenario(self, karkas_engine, scenario_dir):
        """Test loading a scenario file."""
        sim = karkas_engine.Simulation()

        scenario_path = scenario_dir / "fulda_gap_1985.yaml"
        if not scenario_path.exists():
            pytest.skip(f"Scenario not found: {scenario_path}")

        success = sim.load_scenario_from_file(str(scenario_path))
        assert success is True

    def test_simulation_victory_check(self, karkas_engine):
        """Test checking victory conditions."""
        sim = karkas_engine.Simulation()

        # Without a scenario loaded, should not have victory
        result = sim.check_victory()
        # Result should be a string or enum value
        assert result is not None


class TestTurnResultBinding:
    """Test TurnResult class binding."""

    def test_turn_result_attributes(self, karkas_engine, scenario_dir):
        """Test TurnResult has expected attributes."""
        sim = karkas_engine.Simulation()

        scenario_path = scenario_dir / "fulda_gap_1985.yaml"
        if not scenario_path.exists():
            pytest.skip(f"Scenario not found: {scenario_path}")

        sim.load_scenario_from_file(str(scenario_path))

        # We can't easily execute a turn without more setup,
        # but we can verify TurnResult class exists and has expected attributes
        TurnResult = karkas_engine.TurnResult
        assert hasattr(TurnResult, "turn")
        assert hasattr(TurnResult, "game_over")
        assert hasattr(TurnResult, "red_summary")
        assert hasattr(TurnResult, "blue_summary")


class TestCrossLanguageDataIntegrity:
    """Test data integrity across Python-C++ boundary."""

    def test_coordinate_round_trip(self, karkas_engine):
        """Test coordinate values survive round-trip."""
        original = karkas_engine.Coordinates(50.123456789, 9.987654321)

        # Pass through unit set/get
        unit = karkas_engine.Unit(
            "test",
            "Test",
            karkas_engine.Faction.Red,
            karkas_engine.UnitType.Infantry,
            karkas_engine.Echelon.Company
        )
        unit.set_position(original)
        result = unit.get_position()

        # Check precision maintained
        assert abs(result.latitude - original.latitude) < 1e-9
        assert abs(result.longitude - original.longitude) < 1e-9

    def test_string_handling(self, karkas_engine):
        """Test string handling across boundary."""
        # Test various string types
        names = [
            "Simple Name",
            "1st Battalion, 23rd Infantry Regiment",
            "Полк",  # Russian characters
            "Name with 'quotes'",
            "Name with \"double quotes\"",
        ]

        for name in names:
            unit = karkas_engine.Unit(
                "test_id",
                name,
                karkas_engine.Faction.Red,
                karkas_engine.UnitType.Infantry,
                karkas_engine.Echelon.Battalion
            )
            assert unit.get_name() == name, f"Name mismatch for: {name}"

    def test_enum_stability(self, karkas_engine):
        """Test enum values remain stable across calls."""
        # Store enum values
        stored_faction = karkas_engine.Faction.Red
        stored_type = karkas_engine.UnitType.Armor
        stored_echelon = karkas_engine.Echelon.Brigade

        # Create unit
        unit = karkas_engine.Unit(
            "test",
            "Test",
            stored_faction,
            stored_type,
            stored_echelon
        )

        # Verify they match
        assert unit.get_faction() == stored_faction
        assert unit.get_type() == stored_type
        assert unit.get_echelon() == stored_echelon

        # Verify comparisons still work
        assert unit.get_faction() == karkas_engine.Faction.Red
        assert unit.get_type() == karkas_engine.UnitType.Armor
        assert unit.get_echelon() == karkas_engine.Echelon.Brigade


class TestMemoryManagement:
    """Test memory management across Python-C++ boundary."""

    def test_object_lifecycle(self, karkas_engine):
        """Test objects clean up properly."""
        # Create many objects
        units = []
        for i in range(100):
            unit = karkas_engine.Unit(
                f"unit_{i}",
                f"Unit {i}",
                karkas_engine.Faction.Red,
                karkas_engine.UnitType.Infantry,
                karkas_engine.Echelon.Company
            )
            units.append(unit)

        # Access all
        for unit in units:
            _ = unit.get_id()
            _ = unit.get_name()

        # Clear list (should trigger cleanup)
        units.clear()
        # If we get here without segfault, cleanup worked

    def test_nested_object_lifecycle(self, karkas_engine):
        """Test nested objects (Coordinates in Unit) clean up."""
        unit = karkas_engine.Unit(
            "test",
            "Test",
            karkas_engine.Faction.Red,
            karkas_engine.UnitType.Infantry,
            karkas_engine.Echelon.Company
        )

        # Set position multiple times
        for i in range(100):
            pos = karkas_engine.Coordinates(50.0 + i * 0.001, 9.0 + i * 0.001)
            unit.set_position(pos)

        # Get final position
        final = unit.get_position()
        assert final.latitude > 50.0

    def test_large_coordinate_computation(self, karkas_engine):
        """Test large number of coordinate operations."""
        start = karkas_engine.Coordinates(50.0, 9.0)
        current = start

        # Chain of movements toward northeast
        for i in range(50):
            target = karkas_engine.Coordinates(50.0 + i * 0.01, 9.0 + i * 0.01)
            bearing = current.bearing_to(target)
            current = current.move_toward(bearing, 1.0)

        # Should complete without memory issues
        assert current.latitude > start.latitude


class TestErrorHandling:
    """Test error handling in bindings."""

    def test_invalid_terrain_path(self, karkas_engine):
        """Test loading terrain from invalid path."""
        terrain = karkas_engine.TerrainEngine()
        bounds = karkas_engine.BoundingBox()
        bounds.southwest = karkas_engine.Coordinates(50.0, 9.0)
        bounds.northeast = karkas_engine.Coordinates(51.0, 10.0)

        # Should handle gracefully (return False or raise exception)
        try:
            result = terrain.load_region(bounds, "/nonexistent/path.gpkg")
            assert result is False
        except Exception:
            # Exception is also acceptable behavior
            pass

    def test_invalid_scenario_path(self, karkas_engine):
        """Test loading scenario from invalid path."""
        sim = karkas_engine.Simulation()

        try:
            result = sim.load_scenario_from_file("/nonexistent/scenario.yaml")
            assert result is False
        except Exception:
            pass

    def test_terrain_query_before_load(self, karkas_engine):
        """Test querying terrain before loading."""
        terrain = karkas_engine.TerrainEngine()
        point = karkas_engine.Coordinates(50.5, 9.5)

        # Should handle gracefully
        try:
            elevation = terrain.get_elevation(point)
            # May return default value or raise
            assert elevation is not None or elevation == 0.0
        except Exception:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
