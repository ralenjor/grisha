"""Interactive scenario editor mode."""

import sys
from pathlib import Path
from typing import Optional

from .editor import ScenarioEditor, ORBATEditor
from .templates import SCENARIO_TEMPLATES, ORBAT_TEMPLATES, PREDEFINED_REGIONS
from .models import ObjectiveType, VictoryType, UnitType, Echelon, Posture, MobilityClass


def print_menu(title: str, options: list[str]) -> None:
    """Print a numbered menu."""
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print('=' * 50)
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print("  0. Back / Exit")
    print()


def get_choice(prompt: str, max_val: int) -> int:
    """Get a valid menu choice."""
    while True:
        try:
            choice = input(f"{prompt} [0-{max_val}]: ").strip()
            if choice == '':
                return 0
            val = int(choice)
            if 0 <= val <= max_val:
                return val
            print(f"Please enter a number between 0 and {max_val}")
        except ValueError:
            print("Please enter a valid number")


def get_input(prompt: str, default: Optional[str] = None) -> str:
    """Get string input with optional default."""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"{prompt}: ").strip()


def get_float(prompt: str, default: Optional[float] = None) -> float:
    """Get float input."""
    while True:
        try:
            if default is not None:
                result = input(f"{prompt} [{default}]: ").strip()
                if not result:
                    return default
                return float(result)
            else:
                return float(input(f"{prompt}: ").strip())
        except ValueError:
            print("Please enter a valid number")


def get_int(prompt: str, default: Optional[int] = None) -> int:
    """Get integer input."""
    while True:
        try:
            if default is not None:
                result = input(f"{prompt} [{default}]: ").strip()
                if not result:
                    return default
                return int(result)
            else:
                return int(input(f"{prompt}: ").strip())
        except ValueError:
            print("Please enter a valid integer")


def choose_from_enum(prompt: str, enum_class) -> str:
    """Choose a value from an enum."""
    values = [e.value for e in enum_class]
    print(f"\n{prompt}:")
    for i, v in enumerate(values, 1):
        print(f"  {i}. {v}")
    choice = get_choice("Choice", len(values))
    if choice == 0:
        return values[0]
    return values[choice - 1]


class InteractiveScenarioEditor:
    """Interactive session for scenario editing."""

    def __init__(self, path: Optional[Path] = None):
        self.editor = ScenarioEditor(path)
        self.running = True

    def run(self) -> None:
        """Run the interactive session."""
        print("\n" + "=" * 60)
        print("  KARKAS Scenario Editor - Interactive Mode")
        print("=" * 60)

        if self.editor.path:
            print(f"\nLoaded: {self.editor.path}")
        else:
            print("\nNo scenario loaded. Create new or load existing.")

        while self.running:
            self._main_menu()

    def _main_menu(self) -> None:
        options = [
            "New Scenario",
            "Load Scenario",
            "Save Scenario",
            "Edit Basic Info",
            "Edit Region",
            "Edit Factions",
            "Manage Objectives",
            "Manage Victory Conditions",
            "Manage Special Rules",
            "Edit Briefings",
            "Validate",
            "Show Summary",
            "Export JSON",
        ]

        print_menu("Main Menu", options)

        if self.editor.modified:
            print("  [*] Unsaved changes")
        print()

        choice = get_choice("Select", len(options))

        if choice == 0:
            if self.editor.modified:
                if input("Unsaved changes. Exit anyway? [y/N]: ").lower() == 'y':
                    self.running = False
            else:
                self.running = False
        elif choice == 1:
            self._new_scenario()
        elif choice == 2:
            self._load_scenario()
        elif choice == 3:
            self._save_scenario()
        elif choice == 4:
            self._edit_basic_info()
        elif choice == 5:
            self._edit_region()
        elif choice == 6:
            self._edit_factions()
        elif choice == 7:
            self._manage_objectives()
        elif choice == 8:
            self._manage_victory_conditions()
        elif choice == 9:
            self._manage_special_rules()
        elif choice == 10:
            self._edit_briefings()
        elif choice == 11:
            self._validate()
        elif choice == 12:
            self._show_summary()
        elif choice == 13:
            self._export_json()

    def _new_scenario(self) -> None:
        templates = list(SCENARIO_TEMPLATES.keys())
        print_menu("Choose Template", templates)
        choice = get_choice("Template", len(templates))
        if choice == 0:
            return

        template = templates[choice - 1]
        self.editor.new_from_template(template)
        print(f"\nCreated new scenario from template: {template}")

    def _load_scenario(self) -> None:
        path = get_input("Path to scenario file")
        if not path:
            return
        try:
            self.editor.load(Path(path))
            print(f"Loaded: {path}")
        except Exception as e:
            print(f"Error loading: {e}")

    def _save_scenario(self) -> None:
        if self.editor.path:
            default = str(self.editor.path)
        else:
            default = "scenario.yaml"

        path = get_input("Save path", default)
        if not path:
            return

        try:
            self.editor.save(Path(path))
            print(f"Saved: {path}")
        except Exception as e:
            print(f"Error saving: {e}")

    def _edit_basic_info(self) -> None:
        scenario = self.editor.data.get('scenario', {})
        current_name = scenario.get('name', 'Unnamed')
        current_desc = scenario.get('description', '')

        name = get_input("Scenario name", current_name)
        if name:
            self.editor.set_name(name)

        print("Current description:")
        print(f"  {current_desc[:100]}...")
        if input("Change description? [y/N]: ").lower() == 'y':
            desc = get_input("New description")
            if desc:
                self.editor.set_description(desc)

    def _edit_region(self) -> None:
        options = [
            "Use predefined region",
            "Set custom bounds",
        ]
        print_menu("Region Options", options)
        choice = get_choice("Choice", len(options))

        if choice == 1:
            regions = list(PREDEFINED_REGIONS.keys())
            print("\nPredefined Regions:")
            for i, name in enumerate(regions, 1):
                region = PREDEFINED_REGIONS[name]
                print(f"  {i}. {name}: {region['description']}")
            r_choice = get_choice("Region", len(regions))
            if r_choice > 0:
                self.editor.set_region_from_preset(regions[r_choice - 1])
                print(f"Set region: {regions[r_choice - 1]}")

        elif choice == 2:
            print("\nEnter bounding box coordinates:")
            sw_lat = get_float("Southwest latitude", 50.0)
            sw_lon = get_float("Southwest longitude", 9.0)
            ne_lat = get_float("Northeast latitude", 51.0)
            ne_lon = get_float("Northeast longitude", 10.0)
            terrain = get_input("Terrain source file", "terrain.gpkg")
            self.editor.set_region(sw_lat, sw_lon, ne_lat, ne_lon, terrain)
            print("Region updated")

    def _edit_factions(self) -> None:
        for faction_id in ['red', 'blue']:
            print(f"\n--- {faction_id.upper()} Faction ---")
            factions = self.editor.data.get('factions', {})
            current = factions.get(faction_id, {})

            name = get_input("Name", current.get('name', f"{faction_id.title()} Force"))
            orbat = get_input("ORBAT file", current.get('orbat_file', f"{faction_id}_orbat.yaml"))
            doctrine = get_input("Doctrine", current.get('doctrine', ''))
            ai = input(f"AI controlled? [{'Y/n' if current.get('ai_controlled') else 'y/N'}]: ").strip().lower()
            ai_controlled = ai == 'y' if ai else current.get('ai_controlled', False)

            persona = None
            if ai_controlled:
                persona = choose_from_enum("Grisha persona", type('', (), {'COMMANDER': type('', (), {'value': 'commander'})(), 'ADVISOR': type('', (), {'value': 'advisor'})()}))

            self.editor.set_faction(
                faction_id=faction_id,
                name=name,
                orbat_file=orbat,
                doctrine=doctrine,
                ai_controlled=ai_controlled,
                grisha_persona=persona
            )
        print("\nFactions updated")

    def _manage_objectives(self) -> None:
        while True:
            objectives = self.editor.data.get('objectives', [])
            options = [
                "Add objective",
                "Remove objective",
            ]
            for obj in objectives:
                options.append(f"[{obj['controller']}] {obj['name']} ({obj['type']}, {obj['points']} pts)")

            print_menu("Objectives", options)
            choice = get_choice("Choice", len(options))

            if choice == 0:
                break
            elif choice == 1:
                self._add_objective()
            elif choice == 2:
                name = get_input("Objective name to remove")
                if self.editor.remove_objective(name):
                    print(f"Removed: {name}")
                else:
                    print("Not found")

    def _add_objective(self) -> None:
        name = get_input("Objective name (identifier)")
        if not name:
            return

        obj_type = choose_from_enum("Objective type", ObjectiveType)
        lat = get_float("Latitude")
        lon = get_float("Longitude")
        points = get_int("Victory points", 50)
        controller = get_input("Initial controller (red/blue/neutral)", "neutral")

        try:
            self.editor.add_objective(name, obj_type, lat, lon, points, controller)
            print(f"Added objective: {name}")
        except ValueError as e:
            print(f"Error: {e}")

    def _manage_victory_conditions(self) -> None:
        while True:
            vcs = self.editor.data.get('victory_conditions', [])
            options = [
                "Add victory condition",
                "Remove victory condition",
            ]
            for i, vc in enumerate(vcs):
                options.append(f"[{vc['victor']}] {vc['description'][:40]}")

            print_menu("Victory Conditions", options)
            choice = get_choice("Choice", len(options))

            if choice == 0:
                break
            elif choice == 1:
                self._add_victory_condition()
            elif choice == 2:
                idx = get_int("Index to remove (starting from 0)")
                if self.editor.remove_victory_condition(idx):
                    print("Removed")
                else:
                    print("Invalid index")

    def _add_victory_condition(self) -> None:
        vc_type = choose_from_enum("Victory condition type", VictoryType)
        description = get_input("Description")
        victor = get_input("Victor (red/blue/draw)")

        kwargs = {}

        if vc_type == "territorial":
            zones_str = get_input("Zone names (comma-separated)")
            kwargs['zones'] = [z.strip() for z in zones_str.split(',')]
            kwargs['controller'] = get_input("Required controller (red/blue)")
            turns = get_input("Turns held (optional)")
            if turns:
                kwargs['turns_held'] = int(turns)

        elif vc_type == "attrition":
            kwargs['threshold'] = get_float("Attrition threshold (0-1)", 0.5)
            kwargs['faction'] = get_input("Faction to check (red/blue)")

        elif vc_type == "time":
            kwargs['max_turns'] = get_int("Maximum turns")

        try:
            self.editor.add_victory_condition(
                vc_type=vc_type,
                description=description,
                victor=victor,
                **kwargs
            )
            print("Added victory condition")
        except ValueError as e:
            print(f"Error: {e}")

    def _manage_special_rules(self) -> None:
        while True:
            rules = self.editor.data.get('special_rules', [])
            options = [
                "Add special rule",
            ]
            for rule in rules:
                status = "ON" if rule.get('enabled', True) else "OFF"
                options.append(f"[{status}] {rule['name']}: {rule.get('description', '')[:30]}")

            print_menu("Special Rules", options)
            choice = get_choice("Choice", len(options))

            if choice == 0:
                break
            elif choice == 1:
                name = get_input("Rule name")
                desc = get_input("Description")
                enabled = input("Enabled? [Y/n]: ").lower() != 'n'

                trigger_type = None
                trigger_value = None
                if input("Add trigger? [y/N]: ").lower() == 'y':
                    trigger_type = get_input("Trigger type (turn/zone_captured/unit_destroyed)")
                    if trigger_type == "turn":
                        trigger_value = get_int("Turn number")
                    elif trigger_type == "zone_captured":
                        trigger_value = get_input("Zone name")

                effect = None
                if input("Add effect? [y/N]: ").lower() == 'y':
                    effect_type = get_input("Effect type (spawn_units/message)")
                    if effect_type == "spawn_units":
                        effect = {'spawn_units': get_input("Units file")}
                    elif effect_type == "message":
                        effect = {'message': get_input("Message text")}

                self.editor.add_special_rule(
                    name=name,
                    description=desc,
                    enabled=enabled,
                    trigger_type=trigger_type,
                    trigger_value=trigger_value,
                    effect=effect
                )
                print(f"Added rule: {name}")

    def _edit_briefings(self) -> None:
        for faction in ['red', 'blue']:
            print(f"\n--- {faction.upper()} Briefing ---")
            current = self.editor.data.get('briefing', {}).get(faction, '')
            print("Current:")
            print(current[:200] + "..." if len(current) > 200 else current)

            if input(f"\nEdit {faction} briefing? [y/N]: ").lower() == 'y':
                print("Enter briefing (end with empty line):")
                lines = []
                while True:
                    line = input()
                    if not line:
                        break
                    lines.append(line)
                if lines:
                    self.editor.set_briefing(faction, '\n'.join(lines))
                    print("Updated")

    def _validate(self) -> None:
        result = self.editor.validate()
        print("\nValidation Result:")
        print(str(result))

    def _show_summary(self) -> None:
        print("\n" + self.editor.get_summary())

    def _export_json(self) -> None:
        path = get_input("Export path", "scenario.json")
        if path:
            self.editor.export_json(Path(path))
            print(f"Exported: {path}")


class InteractiveORBATEditor:
    """Interactive session for ORBAT editing."""

    def __init__(self, path: Optional[Path] = None):
        self.editor = ORBATEditor(path)
        self.running = True

    def run(self) -> None:
        """Run the interactive session."""
        print("\n" + "=" * 60)
        print("  KARKAS ORBAT Editor - Interactive Mode")
        print("=" * 60)

        if self.editor.path:
            print(f"\nLoaded: {self.editor.path}")
        else:
            print("\nNo ORBAT loaded. Create new or load existing.")

        while self.running:
            self._main_menu()

    def _main_menu(self) -> None:
        options = [
            "New ORBAT",
            "Load ORBAT",
            "Save ORBAT",
            "Edit Basic Info",
            "Add Unit",
            "Remove Unit",
            "Move Unit",
            "Set Unit Parent",
            "Show Hierarchy",
            "List All Units",
            "Validate",
            "Export JSON",
        ]

        print_menu("ORBAT Editor", options)

        if self.editor.modified:
            print("  [*] Unsaved changes")
        print()

        choice = get_choice("Select", len(options))

        if choice == 0:
            if self.editor.modified:
                if input("Unsaved changes. Exit anyway? [y/N]: ").lower() == 'y':
                    self.running = False
            else:
                self.running = False
        elif choice == 1:
            self._new_orbat()
        elif choice == 2:
            self._load_orbat()
        elif choice == 3:
            self._save_orbat()
        elif choice == 4:
            self._edit_basic_info()
        elif choice == 5:
            self._add_unit()
        elif choice == 6:
            self._remove_unit()
        elif choice == 7:
            self._move_unit()
        elif choice == 8:
            self._set_parent()
        elif choice == 9:
            self._show_hierarchy()
        elif choice == 10:
            self._list_units()
        elif choice == 11:
            self._validate()
        elif choice == 12:
            self._export_json()

    def _new_orbat(self) -> None:
        templates = list(ORBAT_TEMPLATES.keys())
        print_menu("Choose Template", templates)
        choice = get_choice("Template", len(templates))
        if choice == 0:
            return

        template = templates[choice - 1]
        self.editor.new_from_template(template)
        print(f"\nCreated new ORBAT from template: {template}")

    def _load_orbat(self) -> None:
        path = get_input("Path to ORBAT file")
        if not path:
            return
        try:
            self.editor.load(Path(path))
            print(f"Loaded: {path}")
        except Exception as e:
            print(f"Error loading: {e}")

    def _save_orbat(self) -> None:
        if self.editor.path:
            default = str(self.editor.path)
        else:
            default = "orbat.yaml"

        path = get_input("Save path", default)
        if not path:
            return

        try:
            self.editor.save(Path(path))
            print(f"Saved: {path}")
        except Exception as e:
            print(f"Error saving: {e}")

    def _edit_basic_info(self) -> None:
        current_name = self.editor.data.get('name', 'Unnamed')
        current_faction = self.editor.data.get('faction', 'red')

        name = get_input("ORBAT name", current_name)
        if name:
            self.editor.set_name(name)

        faction = get_input("Faction (red/blue)", current_faction)
        if faction in ('red', 'blue'):
            self.editor.set_faction(faction)

    def _add_unit(self) -> None:
        unit_id = get_input("Unit ID (unique)")
        if not unit_id:
            return

        name = get_input("Unit name")
        unit_type = choose_from_enum("Unit type", UnitType)
        echelon = choose_from_enum("Echelon", Echelon)
        mobility = choose_from_enum("Mobility class", MobilityClass)
        posture = choose_from_enum("Initial posture", Posture)

        lat = get_float("Latitude")
        lon = get_float("Longitude")
        personnel = get_int("Personnel")
        personnel_max = get_int("Personnel max", personnel)
        equipment = get_int("Equipment", 0)
        equipment_max = get_int("Equipment max", equipment)

        parent = get_input("Parent unit ID (optional)", None)

        try:
            self.editor.add_unit(
                unit_id=unit_id,
                name=name,
                unit_type=unit_type,
                echelon=echelon,
                lat=lat,
                lon=lon,
                personnel=personnel,
                personnel_max=personnel_max,
                mobility_class=mobility,
                posture=posture,
                parent_id=parent if parent else None,
                equipment=equipment,
                equipment_max=equipment_max
            )
            print(f"Added unit: {name}")
        except ValueError as e:
            print(f"Error: {e}")

    def _remove_unit(self) -> None:
        self._list_units()
        unit_id = get_input("Unit ID to remove")
        if self.editor.remove_unit(unit_id):
            print(f"Removed: {unit_id}")
        else:
            print("Not found")

    def _move_unit(self) -> None:
        self._list_units()
        unit_id = get_input("Unit ID to move")
        lat = get_float("New latitude")
        lon = get_float("New longitude")
        if self.editor.move_unit(unit_id, lat, lon):
            print("Moved")
        else:
            print("Unit not found")

    def _set_parent(self) -> None:
        self._list_units()
        unit_id = get_input("Unit ID")
        parent_id = get_input("New parent ID (empty to clear)")
        if self.editor.set_parent(unit_id, parent_id if parent_id else None):
            print("Updated")
        else:
            print("Unit not found")

    def _show_hierarchy(self) -> None:
        print("\nUnit Hierarchy:")
        print(self.editor.get_hierarchy_tree())

    def _list_units(self) -> None:
        units = self.editor.list_units()
        print(f"\nUnits ({len(units)} total):")
        for u in units:
            pos = u.get('position', [0, 0])
            print(f"  {u['id']}: {u['name']} [{u['echelon']} {u['type']}] at ({pos[0]:.4f}, {pos[1]:.4f})")

    def _validate(self) -> None:
        result = self.editor.validate()
        print("\nValidation Result:")
        print(str(result))

    def _export_json(self) -> None:
        path = get_input("Export path", "orbat.json")
        if path:
            self.editor.export_json(Path(path))
            print(f"Exported: {path}")


def run_interactive(file_type: str = "scenario", path: Optional[Path] = None) -> int:
    """Run interactive editor."""
    try:
        if file_type == "scenario":
            editor = InteractiveScenarioEditor(path)
        else:
            editor = InteractiveORBATEditor(path)
        editor.run()
        return 0
    except KeyboardInterrupt:
        print("\nExiting...")
        return 130
    except EOFError:
        print("\nExiting...")
        return 0
