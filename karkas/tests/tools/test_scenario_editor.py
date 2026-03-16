"""Tests for the scenario editor tool."""

import pytest
import tempfile
from pathlib import Path
import yaml

from tools.scenario_editor.models import (
    Scenario, ORBAT, ORBATUnit, Objective, VictoryCondition,
    ObjectiveType, VictoryType, FactionId, Victor,
    BoundingBox, Region, Factions, Faction, GrishaPersona,
    InitialConditions, Briefing, ScenarioMetadata
)
from tools.scenario_editor.templates import (
    SCENARIO_TEMPLATES, ORBAT_TEMPLATES, PREDEFINED_REGIONS,
    get_blank_scenario_template, get_cold_war_offensive_template
)
from tools.scenario_editor.validators import (
    validate_scenario_file, validate_orbat_file,
    ValidationResult, validate_coordinates
)
from tools.scenario_editor.editor import ScenarioEditor, ORBATEditor


class TestModels:
    """Test Pydantic model validation."""

    def test_coordinates_validation(self):
        """Test coordinate validation."""
        result = validate_coordinates(50.5, 9.5)
        assert result.is_valid

        result = validate_coordinates(91, 0)  # Invalid latitude
        assert not result.is_valid

        result = validate_coordinates(0, 181)  # Invalid longitude
        assert not result.is_valid

    def test_bounding_box_validation(self):
        """Test bounding box validation."""
        # Valid box
        bbox = BoundingBox(southwest=[50.0, 9.0], northeast=[51.0, 10.0])
        assert bbox.southwest == [50.0, 9.0]

        # Invalid: SW > NE
        with pytest.raises(ValueError):
            BoundingBox(southwest=[51.0, 9.0], northeast=[50.0, 10.0])

    def test_objective_validation(self):
        """Test objective model validation."""
        obj = Objective(
            name="test_obj",
            type=ObjectiveType.CITY,
            coordinates=[50.5, 9.5],
            points=100,
            controller=FactionId.BLUE
        )
        assert obj.name == "test_obj"
        assert obj.points == 100

    def test_victory_condition_territorial(self):
        """Test territorial victory condition requires zones and controller."""
        # Valid
        vc = VictoryCondition(
            type=VictoryType.TERRITORIAL,
            description="Test",
            victor=Victor.RED,
            zones=["obj1"],
            controller=FactionId.RED
        )
        assert vc.zones == ["obj1"]

        # Missing zones
        with pytest.raises(ValueError):
            VictoryCondition(
                type=VictoryType.TERRITORIAL,
                description="Test",
                victor=Victor.RED,
                controller=FactionId.RED
            )

    def test_victory_condition_attrition(self):
        """Test attrition victory condition requires threshold and faction."""
        vc = VictoryCondition(
            type=VictoryType.ATTRITION,
            description="Test",
            victor=Victor.BLUE,
            threshold=0.6,
            faction=FactionId.RED
        )
        assert vc.threshold == 0.6

        # Missing threshold
        with pytest.raises(ValueError):
            VictoryCondition(
                type=VictoryType.ATTRITION,
                description="Test",
                victor=Victor.BLUE,
                faction=FactionId.RED
            )

    def test_victory_condition_time(self):
        """Test time victory condition requires max_turns."""
        vc = VictoryCondition(
            type=VictoryType.TIME,
            description="Test",
            victor=Victor.DRAW,
            max_turns=40
        )
        assert vc.max_turns == 40

        # Missing max_turns
        with pytest.raises(ValueError):
            VictoryCondition(
                type=VictoryType.TIME,
                description="Test",
                victor=Victor.DRAW
            )

    def test_faction_ai_requires_persona(self):
        """Test AI-controlled faction requires grisha_persona."""
        # Valid with persona
        faction = Faction(
            name="Test",
            orbat_file="test.yaml",
            ai_controlled=True,
            grisha_persona=GrishaPersona.COMMANDER
        )
        assert faction.grisha_persona == GrishaPersona.COMMANDER

        # Missing persona
        with pytest.raises(ValueError):
            Faction(
                name="Test",
                orbat_file="test.yaml",
                ai_controlled=True
            )

    def test_orbat_unit_validation(self):
        """Test ORBAT unit validation."""
        from tools.scenario_editor.models import UnitType, Echelon, MobilityClass, Posture

        unit = ORBATUnit(
            id="test_unit",
            name="Test Unit",
            type=UnitType.INFANTRY,
            echelon=Echelon.BATTALION,
            mobility_class=MobilityClass.FOOT,
            position=[50.5, 9.5],
            posture=Posture.DEFEND,
            personnel=500,
            personnel_max=600
        )
        assert unit.id == "test_unit"
        assert unit.personnel == 500


class TestTemplates:
    """Test scenario templates."""

    def test_blank_template_exists(self):
        """Test blank template is available."""
        assert "blank" in SCENARIO_TEMPLATES
        template = SCENARIO_TEMPLATES["blank"]
        assert "scenario" in template
        assert "factions" in template

    def test_cold_war_template(self):
        """Test cold war offensive template."""
        assert "cold_war_offensive" in SCENARIO_TEMPLATES
        template = SCENARIO_TEMPLATES["cold_war_offensive"]
        assert template["scenario"]["name"] == "Cold War Offensive"
        assert len(template["objectives"]) > 0
        assert len(template["victory_conditions"]) > 0

    def test_predefined_regions(self):
        """Test predefined regions exist."""
        assert "fulda_gap" in PREDEFINED_REGIONS
        assert "suwalki_gap" in PREDEFINED_REGIONS

        fulda = PREDEFINED_REGIONS["fulda_gap"]
        assert "bounds" in fulda
        assert "terrain_source" in fulda

    def test_orbat_templates(self):
        """Test ORBAT templates."""
        assert "blank_red" in ORBAT_TEMPLATES
        assert "sample_red" in ORBAT_TEMPLATES
        assert "sample_blue" in ORBAT_TEMPLATES

        sample = ORBAT_TEMPLATES["sample_red"]
        assert sample["faction"] == "red"
        assert len(sample["units"]) > 0


class TestValidators:
    """Test validation logic."""

    def test_validate_valid_scenario(self):
        """Test validation of valid scenario."""
        template = get_cold_war_offensive_template()

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        ) as f:
            yaml.dump(template, f)
            path = Path(f.name)

        try:
            result = validate_scenario_file(path)
            # Should have no errors (may have warnings about missing files)
            assert len(result.errors) == 0
        finally:
            path.unlink()

    def test_validate_invalid_yaml(self):
        """Test validation catches invalid YAML."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        ) as f:
            f.write("invalid: yaml: content: [")
            path = Path(f.name)

        try:
            result = validate_scenario_file(path)
            assert not result.is_valid
            assert any("YAML" in err or "yaml" in err for err in result.errors)
        finally:
            path.unlink()

    def test_validate_missing_fields(self):
        """Test validation catches missing required fields."""
        incomplete = {"scenario": {"name": "Test"}}

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        ) as f:
            yaml.dump(incomplete, f)
            path = Path(f.name)

        try:
            result = validate_scenario_file(path)
            assert not result.is_valid
        finally:
            path.unlink()

    def test_validation_result_str(self):
        """Test ValidationResult string output."""
        result = ValidationResult()
        assert "no issues" in str(result).lower()

        result.add_error("Test error")
        assert "Test error" in str(result)

        result.add_warning("Test warning")
        assert "Test warning" in str(result)


class TestScenarioEditor:
    """Test ScenarioEditor class."""

    def test_new_from_template(self):
        """Test creating new scenario from template."""
        editor = ScenarioEditor()
        editor.new_from_template("blank")

        assert "scenario" in editor.data
        assert editor.modified

    def test_set_name_description(self):
        """Test setting name and description."""
        editor = ScenarioEditor()
        editor.new_from_template("blank")

        editor.set_name("Test Scenario")
        editor.set_description("A test description")

        assert editor.data["scenario"]["name"] == "Test Scenario"
        assert editor.data["scenario"]["description"] == "A test description"

    def test_set_region(self):
        """Test setting region bounds."""
        editor = ScenarioEditor()
        editor.new_from_template("blank")

        editor.set_region(50.0, 9.0, 51.0, 10.0, "test.gpkg")

        assert editor.data["region"]["bounds"]["southwest"] == [50.0, 9.0]
        assert editor.data["region"]["bounds"]["northeast"] == [51.0, 10.0]

    def test_set_region_from_preset(self):
        """Test setting region from preset."""
        editor = ScenarioEditor()
        editor.new_from_template("blank")

        editor.set_region_from_preset("fulda_gap")

        assert editor.data["region"]["terrain_source"] == "fulda_gap.gpkg"

    def test_add_remove_objective(self):
        """Test adding and removing objectives."""
        editor = ScenarioEditor()
        editor.new_from_template("blank")

        editor.add_objective("test_obj", "city", 50.5, 9.5, 100, "blue")
        assert len(editor.data["objectives"]) == 1
        assert editor.data["objectives"][0]["name"] == "test_obj"

        # Duplicate should raise
        with pytest.raises(ValueError):
            editor.add_objective("test_obj", "city", 50.5, 9.5, 50, "red")

        editor.remove_objective("test_obj")
        assert len(editor.data["objectives"]) == 0

    def test_add_victory_condition(self):
        """Test adding victory conditions."""
        editor = ScenarioEditor()
        editor.new_from_template("blank")

        editor.add_victory_condition(
            vc_type="time",
            description="Test timeout",
            victor="draw",
            max_turns=40
        )

        assert len(editor.data["victory_conditions"]) == 1
        assert editor.data["victory_conditions"][0]["max_turns"] == 40

    def test_save_load(self):
        """Test save and load operations."""
        editor = ScenarioEditor()
        editor.new_from_template("cold_war_offensive")
        editor.set_name("Saved Test")

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        ) as f:
            path = Path(f.name)

        try:
            editor.save(path)
            assert not editor.modified

            editor2 = ScenarioEditor(path)
            assert editor2.data["scenario"]["name"] == "Saved Test"
        finally:
            path.unlink()

    def test_get_summary(self):
        """Test getting scenario summary."""
        editor = ScenarioEditor()
        editor.new_from_template("cold_war_offensive")
        editor.set_name("Summary Test Scenario")

        summary = editor.get_summary()
        assert "Summary Test Scenario" in summary
        assert "Objectives:" in summary


class TestORBATEditor:
    """Test ORBATEditor class."""

    def test_new_from_template(self):
        """Test creating new ORBAT from template."""
        editor = ORBATEditor()
        editor.new_from_template("sample_red")

        assert editor.data["faction"] == "red"
        assert len(editor.data["units"]) > 0

    def test_add_unit(self):
        """Test adding units."""
        editor = ORBATEditor()
        editor.new_from_template("blank_red")

        editor.add_unit(
            unit_id="test_bn",
            name="Test Battalion",
            unit_type="infantry",
            echelon="battalion",
            lat=50.5,
            lon=9.5,
            personnel=500,
            personnel_max=600
        )

        assert editor.get_unit_count() == 1
        unit = editor.get_unit_by_id("test_bn")
        assert unit is not None
        assert unit["name"] == "Test Battalion"

    def test_add_unit_with_parent(self):
        """Test adding unit with parent reference."""
        editor = ORBATEditor()
        editor.new_from_template("blank_red")

        # Add parent
        editor.add_unit(
            unit_id="hq",
            name="HQ",
            unit_type="headquarters",
            echelon="division",
            lat=50.5,
            lon=9.5,
            personnel=100,
            personnel_max=150
        )

        # Add child
        editor.add_unit(
            unit_id="bn1",
            name="1st Battalion",
            unit_type="infantry",
            echelon="battalion",
            lat=50.6,
            lon=9.6,
            personnel=500,
            personnel_max=600,
            parent_id="hq"
        )

        hq = editor.get_unit_by_id("hq")
        assert "bn1" in hq["subordinate_ids"]

        bn = editor.get_unit_by_id("bn1")
        assert bn["parent_id"] == "hq"

    def test_remove_unit(self):
        """Test removing units."""
        editor = ORBATEditor()
        editor.new_from_template("sample_red")

        initial_count = editor.get_unit_count()
        first_unit = editor.list_units()[0]

        result = editor.remove_unit(first_unit["id"])
        assert result
        assert editor.get_unit_count() == initial_count - 1

    def test_move_unit(self):
        """Test moving units."""
        editor = ORBATEditor()
        editor.new_from_template("sample_red")

        first_unit = editor.list_units()[0]
        result = editor.move_unit(first_unit["id"], 51.0, 10.0)

        assert result
        unit = editor.get_unit_by_id(first_unit["id"])
        assert unit["position"] == [51.0, 10.0]

    def test_set_parent(self):
        """Test setting unit parent."""
        editor = ORBATEditor()
        editor.new_from_template("blank_red")

        editor.add_unit("a", "Unit A", "headquarters", "division", 50.0, 9.0, 100, 100)
        editor.add_unit("b", "Unit B", "infantry", "battalion", 50.1, 9.1, 500, 500)

        editor.set_parent("b", "a")

        a = editor.get_unit_by_id("a")
        b = editor.get_unit_by_id("b")

        assert "b" in a["subordinate_ids"]
        assert b["parent_id"] == "a"

    def test_get_hierarchy_tree(self):
        """Test hierarchy tree output."""
        editor = ORBATEditor()
        editor.new_from_template("sample_red")

        tree = editor.get_hierarchy_tree()
        assert "8th Guards Tank Army" in tree or "division" in tree.lower()


class TestCLI:
    """Test CLI commands."""

    def test_main_help(self):
        """Test main help output."""
        from tools.scenario_editor.main import main

        # argparse calls sys.exit(0) for --help
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_list_templates(self):
        """Test list-templates command."""
        from tools.scenario_editor.main import cmd_list_templates
        import argparse

        args = argparse.Namespace()
        result = cmd_list_templates(args)
        assert result == 0

    def test_list_regions(self):
        """Test list-regions command."""
        from tools.scenario_editor.main import cmd_list_regions
        import argparse

        args = argparse.Namespace()
        result = cmd_list_regions(args)
        assert result == 0

    def test_new_command(self):
        """Test new scenario creation."""
        from tools.scenario_editor.main import cmd_new
        import argparse

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        ) as f:
            path = Path(f.name)

        try:
            args = argparse.Namespace(
                template="blank",
                output=path,
                name="CLI Test",
                region=None
            )
            result = cmd_new(args)
            assert result == 0
            assert path.exists()

            # Verify content
            with open(path) as f:
                data = yaml.safe_load(f)
            assert data["scenario"]["name"] == "CLI Test"
        finally:
            path.unlink()

    def test_validate_command(self):
        """Test validate command."""
        from tools.scenario_editor.main import cmd_validate
        import argparse

        template = get_cold_war_offensive_template()

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        ) as f:
            yaml.dump(template, f)
            path = Path(f.name)

        try:
            args = argparse.Namespace(
                file=path,
                type="scenario",
                scenario=None
            )
            result = cmd_validate(args)
            assert result == 0
        finally:
            path.unlink()
