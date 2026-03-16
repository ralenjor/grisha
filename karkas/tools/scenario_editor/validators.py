"""Validation logic for scenarios and ORBATs."""

import logging
from pathlib import Path
from typing import Optional
import yaml
from pydantic import ValidationError

from .models import Scenario, ORBAT, ORBATUnit, Objective, VictoryCondition

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of validation with errors and warnings."""

    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def merge(self, other: "ValidationResult") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    def __str__(self) -> str:
        lines = []
        if self.errors:
            lines.append(f"Errors ({len(self.errors)}):")
            for err in self.errors:
                lines.append(f"  - {err}")
        if self.warnings:
            lines.append(f"Warnings ({len(self.warnings)}):")
            for warn in self.warnings:
                lines.append(f"  - {warn}")
        if not lines:
            lines.append("Validation passed with no issues.")
        return "\n".join(lines)


def validate_scenario_file(path: Path) -> ValidationResult:
    """
    Validate a scenario YAML file.

    Args:
        path: Path to scenario YAML file

    Returns:
        ValidationResult with errors and warnings
    """
    result = ValidationResult()

    if not path.exists():
        result.add_error(f"File does not exist: {path}")
        return result

    if not path.suffix.lower() in ('.yaml', '.yml'):
        result.add_warning(f"File extension is not .yaml or .yml: {path.suffix}")

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        result.add_error(f"Invalid YAML syntax: {e}")
        return result

    if data is None:
        result.add_error("File is empty or contains only comments")
        return result

    # Validate against Pydantic model
    try:
        scenario = Scenario(**data)
    except ValidationError as e:
        for err in e.errors():
            loc = " -> ".join(str(x) for x in err['loc'])
            result.add_error(f"{loc}: {err['msg']}")
        return result

    # Additional semantic validations
    result.merge(_validate_scenario_semantics(scenario, path.parent))

    return result


def _validate_scenario_semantics(scenario: Scenario, base_dir: Path) -> ValidationResult:
    """Perform semantic validation beyond schema."""
    result = ValidationResult()

    # Check terrain file exists
    terrain_path = base_dir / scenario.region.terrain_source
    if not terrain_path.exists():
        terrain_in_data = base_dir.parent / "terrain" / scenario.region.terrain_source
        if not terrain_in_data.exists():
            result.add_warning(
                f"Terrain file not found: {scenario.region.terrain_source} "
                f"(checked {terrain_path} and {terrain_in_data})"
            )

    # Check ORBAT files exist
    for faction_key in ('red', 'blue'):
        faction = getattr(scenario.factions, faction_key)
        orbat_path = base_dir / faction.orbat_file
        if not orbat_path.exists():
            result.add_warning(
                f"{faction_key.capitalize()} ORBAT file not found: {faction.orbat_file}"
            )

    # Check objectives are within region bounds
    bounds = scenario.region.bounds
    for obj in scenario.objectives:
        lat, lon = obj.coordinates
        if not (bounds.southwest[0] <= lat <= bounds.northeast[0]):
            result.add_error(
                f"Objective '{obj.name}' latitude {lat} is outside region bounds "
                f"[{bounds.southwest[0]}, {bounds.northeast[0]}]"
            )
        if not (bounds.southwest[1] <= lon <= bounds.northeast[1]):
            result.add_error(
                f"Objective '{obj.name}' longitude {lon} is outside region bounds "
                f"[{bounds.southwest[1]}, {bounds.northeast[1]}]"
            )

    # Check victory conditions reference existing objectives
    obj_names = {obj.name for obj in scenario.objectives}
    for vc in scenario.victory_conditions:
        if vc.zones:
            for zone in vc.zones:
                if zone not in obj_names:
                    result.add_error(
                        f"Victory condition references unknown zone '{zone}'. "
                        f"Available: {obj_names}"
                    )

    # Warn if no victory conditions
    if not scenario.victory_conditions:
        result.add_warning("No victory conditions defined")

    # Warn if briefings are empty
    if not scenario.briefing.red.strip():
        result.add_warning("Red faction briefing is empty")
    if not scenario.briefing.blue.strip():
        result.add_warning("Blue faction briefing is empty")

    # Check for balanced victory conditions
    red_victories = sum(1 for vc in scenario.victory_conditions if vc.victor.value == "red")
    blue_victories = sum(1 for vc in scenario.victory_conditions if vc.victor.value == "blue")
    if red_victories == 0:
        result.add_warning("No victory conditions favor Red")
    if blue_victories == 0:
        result.add_warning("No victory conditions favor Blue")

    return result


def validate_orbat_file(path: Path, scenario_path: Optional[Path] = None) -> ValidationResult:
    """
    Validate an ORBAT YAML file.

    Args:
        path: Path to ORBAT YAML file
        scenario_path: Optional path to parent scenario for cross-validation

    Returns:
        ValidationResult with errors and warnings
    """
    result = ValidationResult()

    if not path.exists():
        result.add_error(f"File does not exist: {path}")
        return result

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        result.add_error(f"Invalid YAML syntax: {e}")
        return result

    if data is None:
        result.add_error("File is empty")
        return result

    # Validate against Pydantic model
    try:
        orbat = ORBAT(**data)
    except ValidationError as e:
        for err in e.errors():
            loc = " -> ".join(str(x) for x in err['loc'])
            result.add_error(f"{loc}: {err['msg']}")
        return result

    # Additional semantic validations
    result.merge(_validate_orbat_semantics(orbat, scenario_path))

    return result


def _validate_orbat_semantics(orbat: ORBAT, scenario_path: Optional[Path]) -> ValidationResult:
    """Perform semantic validation of ORBAT."""
    result = ValidationResult()

    if not orbat.units:
        result.add_warning("ORBAT has no units defined")
        return result

    # Check unit IDs are unique
    unit_ids = [u.id for u in orbat.units]
    seen = set()
    for uid in unit_ids:
        if uid in seen:
            result.add_error(f"Duplicate unit ID: {uid}")
        seen.add(uid)

    # Check hierarchy consistency
    for unit in orbat.units:
        if unit.parent_id:
            parent = next((u for u in orbat.units if u.id == unit.parent_id), None)
            if parent is None:
                result.add_error(
                    f"Unit '{unit.id}' references non-existent parent '{unit.parent_id}'"
                )
            elif unit.id not in parent.subordinate_ids:
                result.add_warning(
                    f"Unit '{unit.id}' lists parent '{unit.parent_id}' but is not in "
                    f"parent's subordinate_ids"
                )

        for sub_id in unit.subordinate_ids:
            sub = next((u for u in orbat.units if u.id == sub_id), None)
            if sub is None:
                result.add_error(
                    f"Unit '{unit.id}' references non-existent subordinate '{sub_id}'"
                )
            elif sub.parent_id != unit.id:
                result.add_warning(
                    f"Unit '{sub_id}' is in '{unit.id}' subordinate_ids but has "
                    f"different parent_id: '{sub.parent_id}'"
                )

    # Check personnel/equipment ratios
    for unit in orbat.units:
        if unit.personnel > unit.personnel_max:
            result.add_error(
                f"Unit '{unit.id}' has personnel ({unit.personnel}) > max ({unit.personnel_max})"
            )
        if unit.equipment > unit.equipment_max:
            result.add_error(
                f"Unit '{unit.id}' has equipment ({unit.equipment}) > max ({unit.equipment_max})"
            )

    # Check logistics levels
    for unit in orbat.units:
        logi = unit.logistics
        if logi.fuel_level < 0.3:
            result.add_warning(f"Unit '{unit.id}' starts with low fuel ({logi.fuel_level:.0%})")
        if logi.ammo_level < 0.3:
            result.add_warning(f"Unit '{unit.id}' starts with low ammo ({logi.ammo_level:.0%})")

    # Cross-validate with scenario if provided
    if scenario_path and scenario_path.exists():
        try:
            with open(scenario_path) as f:
                scenario_data = yaml.safe_load(f)
            scenario = Scenario(**scenario_data)
            result.merge(_cross_validate_orbat_scenario(orbat, scenario))
        except (yaml.YAMLError, ValidationError) as e:
            result.add_warning(f"Could not load scenario for cross-validation: {e}")

    return result


def _cross_validate_orbat_scenario(orbat: ORBAT, scenario: Scenario) -> ValidationResult:
    """Cross-validate ORBAT against scenario."""
    result = ValidationResult()

    bounds = scenario.region.bounds

    # Check units are within scenario bounds
    for unit in orbat.units:
        lat, lon = unit.position
        if not (bounds.southwest[0] <= lat <= bounds.northeast[0]):
            result.add_error(
                f"Unit '{unit.id}' latitude {lat} is outside scenario bounds "
                f"[{bounds.southwest[0]}, {bounds.northeast[0]}]"
            )
        if not (bounds.southwest[1] <= lon <= bounds.northeast[1]):
            result.add_error(
                f"Unit '{unit.id}' longitude {lon} is outside scenario bounds "
                f"[{bounds.southwest[1]}, {bounds.northeast[1]}]"
            )

    return result


def validate_coordinates(lat: float, lon: float) -> ValidationResult:
    """Validate coordinate values."""
    result = ValidationResult()

    if not -90 <= lat <= 90:
        result.add_error(f"Latitude {lat} must be between -90 and 90")
    if not -180 <= lon <= 180:
        result.add_error(f"Longitude {lon} must be between -180 and 180")

    return result


def validate_within_bounds(
    lat: float, lon: float,
    sw_lat: float, sw_lon: float,
    ne_lat: float, ne_lon: float
) -> ValidationResult:
    """Validate coordinates are within bounding box."""
    result = ValidationResult()

    result.merge(validate_coordinates(lat, lon))
    if result.is_valid:
        if not (sw_lat <= lat <= ne_lat):
            result.add_error(
                f"Latitude {lat} is outside bounds [{sw_lat}, {ne_lat}]"
            )
        if not (sw_lon <= lon <= ne_lon):
            result.add_error(
                f"Longitude {lon} is outside bounds [{sw_lon}, {ne_lon}]"
            )

    return result
