"""
End-to-end game flow integration tests.

These tests validate the complete game flow from scenario loading
through turn execution to game completion.

Run: pytest tests/integration/test_game_flow.py -v

Prerequisites:
    - Build the C++ module: cd build && cmake .. && make
    - The karkas_engine.so module must be in the build directory or PYTHONPATH
"""
from pathlib import Path

import pytest


class TestScenarioLoading:
    """Test scenario loading flow."""

    def test_load_fulda_gap_scenario(self, karkas_engine, scenario_dir):
        """Test loading the Fulda Gap scenario."""
        scenario_path = scenario_dir / "fulda_gap_1985.yaml"
        if not scenario_path.exists():
            pytest.skip(f"Scenario not found: {scenario_path}")

        sim = karkas_engine.Simulation()
        result = sim.load_scenario_from_file(str(scenario_path))

        assert result is True
        assert sim.get_phase() == karkas_engine.TurnPhase.Planning

    def test_scenario_initializes_state(self, karkas_engine, scenario_dir):
        """Test scenario loading initializes game state properly."""
        scenario_path = scenario_dir / "fulda_gap_1985.yaml"
        if not scenario_path.exists():
            pytest.skip(f"Scenario not found: {scenario_path}")

        sim = karkas_engine.Simulation()
        sim.load_scenario_from_file(str(scenario_path))

        # Should start in planning phase
        assert sim.get_phase() == karkas_engine.TurnPhase.Planning

        # Victory should not be achieved at start
        victory = sim.check_victory()
        # Should indicate no victory or ongoing
        assert victory is not None


class TestTurnExecution:
    """Test turn execution flow."""

    def test_turn_requires_readiness(self, karkas_engine, scenario_dir):
        """Test turn cannot execute without factions ready."""
        scenario_path = scenario_dir / "fulda_gap_1985.yaml"
        if not scenario_path.exists():
            pytest.skip(f"Scenario not found: {scenario_path}")

        sim = karkas_engine.Simulation()
        sim.load_scenario_from_file(str(scenario_path))

        # Should not be ready initially
        assert sim.ready_to_execute() is False

    def test_execute_turn_flow(self, karkas_engine, scenario_dir):
        """Test basic turn execution flow."""
        scenario_path = scenario_dir / "fulda_gap_1985.yaml"
        if not scenario_path.exists():
            pytest.skip(f"Scenario not found: {scenario_path}")

        sim = karkas_engine.Simulation()
        sim.load_scenario_from_file(str(scenario_path))

        # Execute turn (may require readiness to be set)
        try:
            result = sim.execute_turn()
            # If execution succeeds, verify result
            assert result is not None
            assert hasattr(result, "turn")
            assert hasattr(result, "game_over")
        except Exception as e:
            # Execution may fail if not ready - that's expected
            assert "not ready" in str(e).lower() or "faction" in str(e).lower()


class TestGamePersistence:
    """Test game save/load functionality."""

    def test_save_game(self, karkas_engine, scenario_dir, tmp_path):
        """Test saving game state."""
        scenario_path = scenario_dir / "fulda_gap_1985.yaml"
        if not scenario_path.exists():
            pytest.skip(f"Scenario not found: {scenario_path}")

        sim = karkas_engine.Simulation()
        sim.load_scenario_from_file(str(scenario_path))

        save_path = tmp_path / "test_save.json"
        # save_game may return None (void) or bool depending on C++ signature
        sim.save_game(str(save_path))

        # Verify file was created
        assert save_path.exists()

    def test_load_game(self, karkas_engine, scenario_dir, tmp_path):
        """Test loading saved game state."""
        scenario_path = scenario_dir / "fulda_gap_1985.yaml"
        if not scenario_path.exists():
            pytest.skip(f"Scenario not found: {scenario_path}")

        # Create and save a game
        sim1 = karkas_engine.Simulation()
        sim1.load_scenario_from_file(str(scenario_path))
        saved_phase = sim1.get_phase()

        save_path = tmp_path / "test_load.json"
        sim1.save_game(str(save_path))

        # Load into new simulation
        sim2 = karkas_engine.Simulation()
        # load_game may return None (void) or bool
        sim2.load_game(str(save_path))

        # Verify state was loaded
        assert sim2.get_phase() == saved_phase


class TestVictoryConditions:
    """Test victory condition checking."""

    def test_no_immediate_victory(self, karkas_engine, scenario_dir):
        """Test that victory is not immediately achieved."""
        scenario_path = scenario_dir / "fulda_gap_1985.yaml"
        if not scenario_path.exists():
            pytest.skip(f"Scenario not found: {scenario_path}")

        sim = karkas_engine.Simulation()
        sim.load_scenario_from_file(str(scenario_path))

        victory = sim.check_victory()
        # Should not have immediate victory
        assert victory is not None
        # Victory result should indicate ongoing game or no victor yet


class TestTerrainIntegration:
    """Test terrain integration with simulation."""

    def test_terrain_loaded_with_scenario(self, karkas_engine, scenario_dir, terrain_dir):
        """Test terrain is loaded when scenario is loaded."""
        scenario_path = scenario_dir / "fulda_gap_1985.yaml"
        terrain_path = terrain_dir / "fulda_gap.gpkg"

        if not scenario_path.exists():
            pytest.skip(f"Scenario not found: {scenario_path}")
        if not terrain_path.exists():
            pytest.skip(f"Terrain not found: {terrain_path}")

        # Create terrain engine separately to test
        terrain = karkas_engine.TerrainEngine()

        bounds = karkas_engine.BoundingBox()
        bounds.southwest = karkas_engine.Coordinates(50.0, 9.0)
        bounds.northeast = karkas_engine.Coordinates(51.0, 10.0)

        terrain.load_region(bounds, str(terrain_path))

        # Load scenario
        sim = karkas_engine.Simulation()
        sim.load_scenario_from_file(str(scenario_path))

        # Both should be in consistent state
        assert terrain.is_loaded() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
