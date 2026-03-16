"""Core scenario editing operations."""

import json
import logging
from pathlib import Path
from typing import Any, Optional
import yaml

from .models import (
    Scenario, ORBAT, ORBATUnit, Objective, VictoryCondition,
    ObjectiveType, VictoryType, FactionId, Victor,
    UnitType, Echelon, MobilityClass, Posture, CombatStats, LogisticsState
)
from .templates import (
    SCENARIO_TEMPLATES, ORBAT_TEMPLATES,
    PREDEFINED_REGIONS, get_blank_scenario_template
)
from .validators import validate_scenario_file, validate_orbat_file, ValidationResult

logger = logging.getLogger(__name__)


class ScenarioEditor:
    """Editor for creating and modifying scenarios."""

    def __init__(self, path: Optional[Path] = None):
        """
        Initialize editor.

        Args:
            path: Path to existing scenario file, or None for new scenario
        """
        self.path = path
        self.data: dict[str, Any] = {}
        self._modified = False

        if path and path.exists():
            self.load(path)

    @property
    def modified(self) -> bool:
        return self._modified

    def load(self, path: Path) -> None:
        """Load scenario from YAML file."""
        with open(path) as f:
            self.data = yaml.safe_load(f) or {}
        self.path = path
        self._modified = False
        logger.info(f"Loaded scenario from {path}")

    def save(self, path: Optional[Path] = None) -> None:
        """Save scenario to YAML file."""
        save_path = path or self.path
        if save_path is None:
            raise ValueError("No path specified for save")

        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, 'w') as f:
            yaml.dump(
                self.data,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=100
            )

        self.path = save_path
        self._modified = False
        logger.info(f"Saved scenario to {save_path}")

    def validate(self) -> ValidationResult:
        """Validate current scenario data."""
        if self.path is None:
            # Write to temp file for validation
            import tempfile
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.yaml', delete=False
            ) as f:
                yaml.dump(self.data, f)
                temp_path = Path(f.name)
            result = validate_scenario_file(temp_path)
            temp_path.unlink()
            return result
        else:
            # Save first, then validate
            self.save()
            return validate_scenario_file(self.path)

    def new_from_template(self, template_name: str = "blank") -> None:
        """Create new scenario from template."""
        if template_name not in SCENARIO_TEMPLATES:
            raise ValueError(
                f"Unknown template '{template_name}'. "
                f"Available: {list(SCENARIO_TEMPLATES.keys())}"
            )
        self.data = SCENARIO_TEMPLATES[template_name].copy()
        self._modified = True
        logger.info(f"Created new scenario from template: {template_name}")

    def set_name(self, name: str) -> None:
        """Set scenario name."""
        if 'scenario' not in self.data:
            self.data['scenario'] = {}
        self.data['scenario']['name'] = name
        self._modified = True

    def set_description(self, description: str) -> None:
        """Set scenario description."""
        if 'scenario' not in self.data:
            self.data['scenario'] = {}
        self.data['scenario']['description'] = description
        self._modified = True

    def set_region(
        self,
        sw_lat: float, sw_lon: float,
        ne_lat: float, ne_lon: float,
        terrain_source: str
    ) -> None:
        """Set scenario region bounds."""
        self.data['region'] = {
            'bounds': {
                'southwest': [sw_lat, sw_lon],
                'northeast': [ne_lat, ne_lon]
            },
            'terrain_source': terrain_source
        }
        self._modified = True

    def set_region_from_preset(self, preset_name: str) -> None:
        """Set region from a predefined region."""
        if preset_name not in PREDEFINED_REGIONS:
            raise ValueError(
                f"Unknown region '{preset_name}'. "
                f"Available: {list(PREDEFINED_REGIONS.keys())}"
            )
        region = PREDEFINED_REGIONS[preset_name]
        self.data['region'] = {
            'bounds': region['bounds'],
            'terrain_source': region['terrain_source']
        }
        self._modified = True
        logger.info(f"Set region from preset: {preset_name}")

    def set_faction(
        self,
        faction_id: str,  # 'red' or 'blue'
        name: str,
        orbat_file: str,
        doctrine: str = "",
        ai_controlled: bool = False,
        grisha_persona: Optional[str] = None
    ) -> None:
        """Configure a faction."""
        if faction_id not in ('red', 'blue'):
            raise ValueError("faction_id must be 'red' or 'blue'")

        if 'factions' not in self.data:
            self.data['factions'] = {}

        faction_data = {
            'name': name,
            'doctrine': doctrine,
            'orbat_file': orbat_file,
            'ai_controlled': ai_controlled
        }
        if grisha_persona:
            faction_data['grisha_persona'] = grisha_persona

        self.data['factions'][faction_id] = faction_data
        self._modified = True

    def set_initial_conditions(
        self,
        turn_length_hours: int = 4,
        start_date: str = "1985-08-15T04:00:00",
        precipitation: str = "none",
        visibility: str = "clear",
        temperature_c: float = 20.0,
        wind_speed_kph: float = 10.0,
        wind_direction: float = 270.0
    ) -> None:
        """Set initial conditions."""
        self.data['initial_conditions'] = {
            'turn_length_hours': turn_length_hours,
            'start_date': start_date,
            'weather': {
                'precipitation': precipitation,
                'visibility': visibility,
                'temperature_c': temperature_c,
                'wind_speed_kph': wind_speed_kph,
                'wind_direction': wind_direction
            }
        }
        self._modified = True

    def add_objective(
        self,
        name: str,
        obj_type: str,
        lat: float,
        lon: float,
        points: int,
        controller: str = "neutral"
    ) -> None:
        """Add an objective."""
        if 'objectives' not in self.data:
            self.data['objectives'] = []

        # Check for duplicate name
        for obj in self.data['objectives']:
            if obj['name'] == name:
                raise ValueError(f"Objective with name '{name}' already exists")

        objective = {
            'name': name,
            'type': obj_type,
            'coordinates': [lat, lon],
            'points': points,
            'controller': controller
        }
        self.data['objectives'].append(objective)
        self._modified = True
        logger.info(f"Added objective: {name}")

    def remove_objective(self, name: str) -> bool:
        """Remove an objective by name."""
        if 'objectives' not in self.data:
            return False

        original_len = len(self.data['objectives'])
        self.data['objectives'] = [
            obj for obj in self.data['objectives']
            if obj['name'] != name
        ]

        if len(self.data['objectives']) < original_len:
            self._modified = True
            logger.info(f"Removed objective: {name}")
            return True
        return False

    def add_victory_condition(
        self,
        vc_type: str,
        description: str,
        victor: str,
        zones: Optional[list[str]] = None,
        controller: Optional[str] = None,
        turns_held: Optional[int] = None,
        threshold: Optional[float] = None,
        faction: Optional[str] = None,
        max_turns: Optional[int] = None
    ) -> None:
        """Add a victory condition."""
        if 'victory_conditions' not in self.data:
            self.data['victory_conditions'] = []

        vc = {
            'type': vc_type,
            'description': description,
            'victor': victor
        }

        if zones:
            vc['zones'] = zones
        if controller:
            vc['controller'] = controller
        if turns_held is not None:
            vc['turns_held'] = turns_held
        if threshold is not None:
            vc['threshold'] = threshold
        if faction:
            vc['faction'] = faction
        if max_turns is not None:
            vc['max_turns'] = max_turns

        self.data['victory_conditions'].append(vc)
        self._modified = True
        logger.info(f"Added victory condition: {description}")

    def remove_victory_condition(self, index: int) -> bool:
        """Remove a victory condition by index."""
        if 'victory_conditions' not in self.data:
            return False
        if 0 <= index < len(self.data['victory_conditions']):
            removed = self.data['victory_conditions'].pop(index)
            self._modified = True
            logger.info(f"Removed victory condition: {removed.get('description', index)}")
            return True
        return False

    def add_special_rule(
        self,
        name: str,
        description: str = "",
        enabled: bool = True,
        trigger_type: Optional[str] = None,
        trigger_value: Optional[Any] = None,
        effect: Optional[dict] = None
    ) -> None:
        """Add a special rule."""
        if 'special_rules' not in self.data:
            self.data['special_rules'] = []

        rule: dict[str, Any] = {
            'name': name,
            'description': description,
            'enabled': enabled
        }

        if trigger_type:
            rule['trigger'] = {'type': trigger_type}
            if trigger_type == 'turn' and trigger_value is not None:
                rule['trigger']['turn'] = trigger_value
            elif trigger_type == 'zone_captured' and trigger_value is not None:
                rule['trigger']['zone'] = trigger_value

        if effect:
            rule['effect'] = effect

        self.data['special_rules'].append(rule)
        self._modified = True
        logger.info(f"Added special rule: {name}")

    def set_briefing(self, faction: str, briefing: str) -> None:
        """Set faction briefing text."""
        if faction not in ('red', 'blue'):
            raise ValueError("faction must be 'red' or 'blue'")

        if 'briefing' not in self.data:
            self.data['briefing'] = {}

        self.data['briefing'][faction] = briefing
        self._modified = True

    def export_json(self, path: Path) -> None:
        """Export scenario as JSON."""
        with open(path, 'w') as f:
            json.dump(self.data, f, indent=2)
        logger.info(f"Exported JSON to {path}")

    def get_summary(self) -> str:
        """Get a text summary of the scenario."""
        lines = []

        scenario = self.data.get('scenario', {})
        lines.append(f"Scenario: {scenario.get('name', 'Unnamed')}")
        lines.append(f"Description: {scenario.get('description', 'No description')}")
        lines.append("")

        region = self.data.get('region', {})
        bounds = region.get('bounds', {})
        sw = bounds.get('southwest', [0, 0])
        ne = bounds.get('northeast', [0, 0])
        lines.append(f"Region: {sw[0]:.4f},{sw[1]:.4f} to {ne[0]:.4f},{ne[1]:.4f}")
        lines.append(f"Terrain: {region.get('terrain_source', 'Not set')}")
        lines.append("")

        factions = self.data.get('factions', {})
        red = factions.get('red', {})
        blue = factions.get('blue', {})
        lines.append(f"Red: {red.get('name', 'Not set')} (ORBAT: {red.get('orbat_file', 'N/A')})")
        lines.append(f"Blue: {blue.get('name', 'Not set')} (ORBAT: {blue.get('orbat_file', 'N/A')})")
        lines.append("")

        objectives = self.data.get('objectives', [])
        lines.append(f"Objectives: {len(objectives)}")
        for obj in objectives:
            lines.append(f"  - {obj.get('name')}: {obj.get('type')} ({obj.get('points')} pts)")
        lines.append("")

        vcs = self.data.get('victory_conditions', [])
        lines.append(f"Victory Conditions: {len(vcs)}")
        for vc in vcs:
            lines.append(f"  - [{vc.get('victor')}] {vc.get('description')}")

        return "\n".join(lines)


class ORBATEditor:
    """Editor for creating and modifying ORBATs."""

    def __init__(self, path: Optional[Path] = None):
        """
        Initialize editor.

        Args:
            path: Path to existing ORBAT file, or None for new ORBAT
        """
        self.path = path
        self.data: dict[str, Any] = {}
        self._modified = False

        if path and path.exists():
            self.load(path)

    @property
    def modified(self) -> bool:
        return self._modified

    def load(self, path: Path) -> None:
        """Load ORBAT from YAML file."""
        with open(path) as f:
            self.data = yaml.safe_load(f) or {}
        self.path = path
        self._modified = False
        logger.info(f"Loaded ORBAT from {path}")

    def save(self, path: Optional[Path] = None) -> None:
        """Save ORBAT to YAML file."""
        save_path = path or self.path
        if save_path is None:
            raise ValueError("No path specified for save")

        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, 'w') as f:
            yaml.dump(
                self.data,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=100
            )

        self.path = save_path
        self._modified = False
        logger.info(f"Saved ORBAT to {save_path}")

    def validate(self, scenario_path: Optional[Path] = None) -> ValidationResult:
        """Validate current ORBAT data."""
        if self.path is None:
            import tempfile
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.yaml', delete=False
            ) as f:
                yaml.dump(self.data, f)
                temp_path = Path(f.name)
            result = validate_orbat_file(temp_path, scenario_path)
            temp_path.unlink()
            return result
        else:
            self.save()
            return validate_orbat_file(self.path, scenario_path)

    def new_from_template(self, template_name: str = "blank_red") -> None:
        """Create new ORBAT from template."""
        if template_name not in ORBAT_TEMPLATES:
            raise ValueError(
                f"Unknown template '{template_name}'. "
                f"Available: {list(ORBAT_TEMPLATES.keys())}"
            )
        self.data = ORBAT_TEMPLATES[template_name].copy()
        self._modified = True
        logger.info(f"Created new ORBAT from template: {template_name}")

    def set_faction(self, faction: str) -> None:
        """Set ORBAT faction."""
        if faction not in ('red', 'blue'):
            raise ValueError("faction must be 'red' or 'blue'")
        self.data['faction'] = faction
        self._modified = True

    def set_name(self, name: str) -> None:
        """Set ORBAT name."""
        self.data['name'] = name
        self._modified = True

    def add_unit(
        self,
        unit_id: str,
        name: str,
        unit_type: str,
        echelon: str,
        lat: float,
        lon: float,
        personnel: int,
        personnel_max: int,
        mobility_class: str = "foot",
        heading: float = 0.0,
        posture: str = "defend",
        parent_id: Optional[str] = None,
        equipment: int = 0,
        equipment_max: int = 0,
        combat_stats: Optional[dict] = None,
        logistics: Optional[dict] = None
    ) -> None:
        """Add a unit to the ORBAT."""
        if 'units' not in self.data:
            self.data['units'] = []

        # Check for duplicate ID
        for unit in self.data['units']:
            if unit['id'] == unit_id:
                raise ValueError(f"Unit with ID '{unit_id}' already exists")

        unit: dict[str, Any] = {
            'id': unit_id,
            'name': name,
            'type': unit_type,
            'echelon': echelon,
            'mobility_class': mobility_class,
            'position': [lat, lon],
            'heading': heading,
            'posture': posture,
            'personnel': personnel,
            'personnel_max': personnel_max,
            'equipment': equipment,
            'equipment_max': equipment_max
        }

        if parent_id:
            unit['parent_id'] = parent_id
            # Add to parent's subordinates
            for parent in self.data['units']:
                if parent['id'] == parent_id:
                    if 'subordinate_ids' not in parent:
                        parent['subordinate_ids'] = []
                    if unit_id not in parent['subordinate_ids']:
                        parent['subordinate_ids'].append(unit_id)
                    break

        if combat_stats:
            unit['combat_stats'] = combat_stats
        if logistics:
            unit['logistics'] = logistics

        self.data['units'].append(unit)
        self._modified = True
        logger.info(f"Added unit: {name} ({unit_id})")

    def remove_unit(self, unit_id: str) -> bool:
        """Remove a unit by ID."""
        if 'units' not in self.data:
            return False

        unit_to_remove = None
        for unit in self.data['units']:
            if unit['id'] == unit_id:
                unit_to_remove = unit
                break

        if unit_to_remove is None:
            return False

        # Remove from parent's subordinates
        if 'parent_id' in unit_to_remove:
            for parent in self.data['units']:
                if parent['id'] == unit_to_remove['parent_id']:
                    if 'subordinate_ids' in parent:
                        parent['subordinate_ids'] = [
                            sid for sid in parent['subordinate_ids']
                            if sid != unit_id
                        ]
                    break

        # Remove unit
        self.data['units'] = [u for u in self.data['units'] if u['id'] != unit_id]
        self._modified = True
        logger.info(f"Removed unit: {unit_id}")
        return True

    def update_unit(
        self,
        unit_id: str,
        **kwargs
    ) -> bool:
        """Update unit attributes."""
        for unit in self.data.get('units', []):
            if unit['id'] == unit_id:
                # Handle position specially
                if 'lat' in kwargs and 'lon' in kwargs:
                    unit['position'] = [kwargs.pop('lat'), kwargs.pop('lon')]

                # Update other attributes
                for key, value in kwargs.items():
                    if value is not None:
                        unit[key] = value

                self._modified = True
                logger.info(f"Updated unit: {unit_id}")
                return True
        return False

    def move_unit(self, unit_id: str, lat: float, lon: float) -> bool:
        """Move a unit to new coordinates."""
        for unit in self.data.get('units', []):
            if unit['id'] == unit_id:
                unit['position'] = [lat, lon]
                self._modified = True
                logger.info(f"Moved unit {unit_id} to ({lat}, {lon})")
                return True
        return False

    def set_unit_posture(self, unit_id: str, posture: str) -> bool:
        """Set unit posture."""
        for unit in self.data.get('units', []):
            if unit['id'] == unit_id:
                unit['posture'] = posture
                self._modified = True
                return True
        return False

    def set_parent(self, unit_id: str, parent_id: Optional[str]) -> bool:
        """Set or clear unit's parent."""
        unit = None
        for u in self.data.get('units', []):
            if u['id'] == unit_id:
                unit = u
                break

        if unit is None:
            return False

        # Remove from old parent's subordinates
        old_parent_id = unit.get('parent_id')
        if old_parent_id:
            for parent in self.data['units']:
                if parent['id'] == old_parent_id:
                    if 'subordinate_ids' in parent:
                        parent['subordinate_ids'] = [
                            sid for sid in parent['subordinate_ids']
                            if sid != unit_id
                        ]
                    break

        # Set new parent
        if parent_id:
            unit['parent_id'] = parent_id
            # Add to new parent's subordinates
            for parent in self.data['units']:
                if parent['id'] == parent_id:
                    if 'subordinate_ids' not in parent:
                        parent['subordinate_ids'] = []
                    if unit_id not in parent['subordinate_ids']:
                        parent['subordinate_ids'].append(unit_id)
                    break
        else:
            unit.pop('parent_id', None)

        self._modified = True
        return True

    def export_json(self, path: Path) -> None:
        """Export ORBAT as JSON."""
        with open(path, 'w') as f:
            json.dump(self.data, f, indent=2)
        logger.info(f"Exported JSON to {path}")

    def get_unit_count(self) -> int:
        """Get total number of units."""
        return len(self.data.get('units', []))

    def get_unit_by_id(self, unit_id: str) -> Optional[dict]:
        """Get unit by ID."""
        for unit in self.data.get('units', []):
            if unit['id'] == unit_id:
                return unit
        return None

    def list_units(self) -> list[dict]:
        """List all units."""
        return self.data.get('units', [])

    def get_hierarchy_tree(self) -> str:
        """Get a text representation of unit hierarchy."""
        units = self.data.get('units', [])
        if not units:
            return "No units"

        lines = []
        unit_by_id = {u['id']: u for u in units}

        # Find root units (no parent)
        roots = [u for u in units if 'parent_id' not in u or not u['parent_id']]

        def print_tree(unit: dict, indent: int = 0) -> None:
            prefix = "  " * indent
            echelon = unit.get('echelon', '?')
            utype = unit.get('type', '?')
            lines.append(f"{prefix}- {unit['name']} [{echelon} {utype}]")

            for sub_id in unit.get('subordinate_ids', []):
                if sub_id in unit_by_id:
                    print_tree(unit_by_id[sub_id], indent + 1)

        for root in roots:
            print_tree(root)

        return "\n".join(lines)
