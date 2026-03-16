#!/usr/bin/env python3
"""
Scenario Editor CLI - Create and manage KARKAS scenario files.

Usage:
    scenario-editor new --template cold_war_offensive --output scenarios/my_scenario.yaml
    scenario-editor validate scenarios/my_scenario.yaml
    scenario-editor add-objective scenarios/my_scenario.yaml --name berlin --type city --lat 52.52 --lon 13.40 --points 100
    scenario-editor add-unit orbats/red_orbat.yaml --id 1tr --name "1st Tank Regiment" --type armor --echelon regiment
    scenario-editor export scenarios/my_scenario.yaml --format json --output scenario.json
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from .editor import ScenarioEditor, ORBATEditor
from .templates import SCENARIO_TEMPLATES, ORBAT_TEMPLATES, PREDEFINED_REGIONS
from .validators import validate_scenario_file, validate_orbat_file
from .models import ObjectiveType, VictoryType, UnitType, Echelon, Posture, MobilityClass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="scenario-editor",
        description="Create and manage KARKAS scenario files",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # === new command ===
    new_parser = subparsers.add_parser(
        "new",
        help="Create a new scenario from template",
    )
    new_parser.add_argument(
        "--template", "-t",
        type=str,
        default="blank",
        choices=list(SCENARIO_TEMPLATES.keys()),
        help="Template to use (default: blank)",
    )
    new_parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output path for scenario file",
    )
    new_parser.add_argument(
        "--name",
        type=str,
        help="Scenario name (overrides template)",
    )
    new_parser.add_argument(
        "--region",
        type=str,
        choices=list(PREDEFINED_REGIONS.keys()),
        help="Use predefined region",
    )

    # === new-orbat command ===
    new_orbat_parser = subparsers.add_parser(
        "new-orbat",
        help="Create a new ORBAT from template",
    )
    new_orbat_parser.add_argument(
        "--template", "-t",
        type=str,
        default="blank_red",
        choices=list(ORBAT_TEMPLATES.keys()),
        help="Template to use (default: blank_red)",
    )
    new_orbat_parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output path for ORBAT file",
    )
    new_orbat_parser.add_argument(
        "--name",
        type=str,
        help="ORBAT name (overrides template)",
    )
    new_orbat_parser.add_argument(
        "--faction",
        type=str,
        choices=["red", "blue"],
        help="Faction (overrides template)",
    )

    # === validate command ===
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a scenario or ORBAT file",
    )
    validate_parser.add_argument(
        "file",
        type=Path,
        help="Path to scenario or ORBAT YAML file",
    )
    validate_parser.add_argument(
        "--type",
        type=str,
        choices=["scenario", "orbat", "auto"],
        default="auto",
        help="File type (auto-detected if not specified)",
    )
    validate_parser.add_argument(
        "--scenario",
        type=Path,
        help="Scenario file for ORBAT cross-validation",
    )

    # === add-objective command ===
    add_obj_parser = subparsers.add_parser(
        "add-objective",
        help="Add an objective to a scenario",
    )
    add_obj_parser.add_argument(
        "scenario",
        type=Path,
        help="Path to scenario file",
    )
    add_obj_parser.add_argument(
        "--name", "-n",
        type=str,
        required=True,
        help="Objective name (identifier)",
    )
    add_obj_parser.add_argument(
        "--type", "-t",
        type=str,
        required=True,
        choices=[e.value for e in ObjectiveType],
        help="Objective type",
    )
    add_obj_parser.add_argument(
        "--lat",
        type=float,
        required=True,
        help="Latitude",
    )
    add_obj_parser.add_argument(
        "--lon",
        type=float,
        required=True,
        help="Longitude",
    )
    add_obj_parser.add_argument(
        "--points", "-p",
        type=int,
        required=True,
        help="Victory points value",
    )
    add_obj_parser.add_argument(
        "--controller", "-c",
        type=str,
        default="neutral",
        choices=["red", "blue", "neutral"],
        help="Initial controller (default: neutral)",
    )

    # === remove-objective command ===
    rm_obj_parser = subparsers.add_parser(
        "remove-objective",
        help="Remove an objective from a scenario",
    )
    rm_obj_parser.add_argument(
        "scenario",
        type=Path,
        help="Path to scenario file",
    )
    rm_obj_parser.add_argument(
        "--name", "-n",
        type=str,
        required=True,
        help="Objective name to remove",
    )

    # === add-victory-condition command ===
    add_vc_parser = subparsers.add_parser(
        "add-victory-condition",
        help="Add a victory condition to a scenario",
    )
    add_vc_parser.add_argument(
        "scenario",
        type=Path,
        help="Path to scenario file",
    )
    add_vc_parser.add_argument(
        "--type", "-t",
        type=str,
        required=True,
        choices=[e.value for e in VictoryType],
        help="Victory condition type",
    )
    add_vc_parser.add_argument(
        "--description", "-d",
        type=str,
        required=True,
        help="Description of the condition",
    )
    add_vc_parser.add_argument(
        "--victor", "-v",
        type=str,
        required=True,
        choices=["red", "blue", "draw"],
        help="Who wins if condition is met",
    )
    add_vc_parser.add_argument(
        "--zones",
        type=str,
        nargs="+",
        help="Zone names for territorial conditions",
    )
    add_vc_parser.add_argument(
        "--controller",
        type=str,
        choices=["red", "blue"],
        help="Required controller for territorial",
    )
    add_vc_parser.add_argument(
        "--turns-held",
        type=int,
        help="Turns zone must be held",
    )
    add_vc_parser.add_argument(
        "--threshold",
        type=float,
        help="Attrition threshold (0-1)",
    )
    add_vc_parser.add_argument(
        "--faction",
        type=str,
        choices=["red", "blue"],
        help="Faction for attrition check",
    )
    add_vc_parser.add_argument(
        "--max-turns",
        type=int,
        help="Maximum turns for time condition",
    )

    # === add-unit command ===
    add_unit_parser = subparsers.add_parser(
        "add-unit",
        help="Add a unit to an ORBAT",
    )
    add_unit_parser.add_argument(
        "orbat",
        type=Path,
        help="Path to ORBAT file",
    )
    add_unit_parser.add_argument(
        "--id",
        type=str,
        required=True,
        help="Unit ID (unique identifier)",
    )
    add_unit_parser.add_argument(
        "--name", "-n",
        type=str,
        required=True,
        help="Unit name",
    )
    add_unit_parser.add_argument(
        "--type", "-t",
        type=str,
        required=True,
        choices=[e.value for e in UnitType],
        help="Unit type",
    )
    add_unit_parser.add_argument(
        "--echelon", "-e",
        type=str,
        required=True,
        choices=[e.value for e in Echelon],
        help="Unit echelon",
    )
    add_unit_parser.add_argument(
        "--lat",
        type=float,
        required=True,
        help="Initial latitude",
    )
    add_unit_parser.add_argument(
        "--lon",
        type=float,
        required=True,
        help="Initial longitude",
    )
    add_unit_parser.add_argument(
        "--personnel",
        type=int,
        required=True,
        help="Current personnel",
    )
    add_unit_parser.add_argument(
        "--personnel-max",
        type=int,
        required=True,
        help="Maximum personnel",
    )
    add_unit_parser.add_argument(
        "--mobility",
        type=str,
        default="foot",
        choices=[e.value for e in MobilityClass],
        help="Mobility class (default: foot)",
    )
    add_unit_parser.add_argument(
        "--posture",
        type=str,
        default="defend",
        choices=[e.value for e in Posture],
        help="Initial posture (default: defend)",
    )
    add_unit_parser.add_argument(
        "--parent",
        type=str,
        help="Parent unit ID",
    )
    add_unit_parser.add_argument(
        "--equipment",
        type=int,
        default=0,
        help="Current equipment count",
    )
    add_unit_parser.add_argument(
        "--equipment-max",
        type=int,
        default=0,
        help="Maximum equipment count",
    )

    # === remove-unit command ===
    rm_unit_parser = subparsers.add_parser(
        "remove-unit",
        help="Remove a unit from an ORBAT",
    )
    rm_unit_parser.add_argument(
        "orbat",
        type=Path,
        help="Path to ORBAT file",
    )
    rm_unit_parser.add_argument(
        "--id",
        type=str,
        required=True,
        help="Unit ID to remove",
    )

    # === move-unit command ===
    move_unit_parser = subparsers.add_parser(
        "move-unit",
        help="Move a unit to new coordinates",
    )
    move_unit_parser.add_argument(
        "orbat",
        type=Path,
        help="Path to ORBAT file",
    )
    move_unit_parser.add_argument(
        "--id",
        type=str,
        required=True,
        help="Unit ID to move",
    )
    move_unit_parser.add_argument(
        "--lat",
        type=float,
        required=True,
        help="New latitude",
    )
    move_unit_parser.add_argument(
        "--lon",
        type=float,
        required=True,
        help="New longitude",
    )

    # === info command ===
    info_parser = subparsers.add_parser(
        "info",
        help="Display scenario or ORBAT summary",
    )
    info_parser.add_argument(
        "file",
        type=Path,
        help="Path to scenario or ORBAT file",
    )
    info_parser.add_argument(
        "--type",
        type=str,
        choices=["scenario", "orbat", "auto"],
        default="auto",
        help="File type (auto-detected if not specified)",
    )

    # === export command ===
    export_parser = subparsers.add_parser(
        "export",
        help="Export scenario or ORBAT to JSON",
    )
    export_parser.add_argument(
        "file",
        type=Path,
        help="Path to scenario or ORBAT file",
    )
    export_parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output JSON path",
    )

    # === list-templates command ===
    subparsers.add_parser(
        "list-templates",
        help="List available templates",
    )

    # === list-regions command ===
    subparsers.add_parser(
        "list-regions",
        help="List predefined regions",
    )

    # === interactive command ===
    interactive_parser = subparsers.add_parser(
        "interactive",
        help="Launch interactive editor mode",
    )
    interactive_parser.add_argument(
        "--type", "-t",
        type=str,
        default="scenario",
        choices=["scenario", "orbat"],
        help="Editor type (default: scenario)",
    )
    interactive_parser.add_argument(
        "file",
        type=Path,
        nargs="?",
        help="Optional file to load",
    )

    # === set-briefing command ===
    briefing_parser = subparsers.add_parser(
        "set-briefing",
        help="Set faction briefing text",
    )
    briefing_parser.add_argument(
        "scenario",
        type=Path,
        help="Path to scenario file",
    )
    briefing_parser.add_argument(
        "--faction", "-f",
        type=str,
        required=True,
        choices=["red", "blue"],
        help="Faction to set briefing for",
    )
    briefing_parser.add_argument(
        "--text",
        type=str,
        help="Briefing text (or use --file)",
    )
    briefing_parser.add_argument(
        "--file",
        type=Path,
        help="Read briefing from file",
    )

    return parser


def detect_file_type(path: Path) -> str:
    """Detect if file is scenario or ORBAT based on content."""
    import yaml
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        if data is None:
            return "unknown"
        if 'scenario' in data or 'factions' in data or 'victory_conditions' in data:
            return "scenario"
        if 'units' in data or (data.get('faction') in ('red', 'blue')):
            return "orbat"
    except Exception:
        pass
    return "unknown"


def cmd_new(args: argparse.Namespace) -> int:
    """Create new scenario from template."""
    editor = ScenarioEditor()
    editor.new_from_template(args.template)

    if args.name:
        editor.set_name(args.name)

    if args.region:
        editor.set_region_from_preset(args.region)

    editor.save(args.output)
    print(f"Created scenario: {args.output}")

    # Show summary
    print("\n" + editor.get_summary())
    return 0


def cmd_new_orbat(args: argparse.Namespace) -> int:
    """Create new ORBAT from template."""
    editor = ORBATEditor()
    editor.new_from_template(args.template)

    if args.name:
        editor.set_name(args.name)

    if args.faction:
        editor.set_faction(args.faction)

    editor.save(args.output)
    print(f"Created ORBAT: {args.output}")
    print(f"Units: {editor.get_unit_count()}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate scenario or ORBAT file."""
    file_type = args.type
    if file_type == "auto":
        file_type = detect_file_type(args.file)
        if file_type == "unknown":
            print(f"Could not determine file type for: {args.file}")
            print("Use --type to specify explicitly")
            return 1

    print(f"Validating {file_type}: {args.file}")

    if file_type == "scenario":
        result = validate_scenario_file(args.file)
    else:
        result = validate_orbat_file(args.file, args.scenario)

    print()
    print(str(result))

    if result.is_valid:
        print("\nValidation PASSED")
        return 0
    else:
        print("\nValidation FAILED")
        return 1


def cmd_add_objective(args: argparse.Namespace) -> int:
    """Add objective to scenario."""
    editor = ScenarioEditor(args.scenario)

    try:
        editor.add_objective(
            name=args.name,
            obj_type=args.type,
            lat=args.lat,
            lon=args.lon,
            points=args.points,
            controller=args.controller
        )
        editor.save()
        print(f"Added objective: {args.name}")
        return 0
    except ValueError as e:
        print(f"Error: {e}")
        return 1


def cmd_remove_objective(args: argparse.Namespace) -> int:
    """Remove objective from scenario."""
    editor = ScenarioEditor(args.scenario)

    if editor.remove_objective(args.name):
        editor.save()
        print(f"Removed objective: {args.name}")
        return 0
    else:
        print(f"Objective not found: {args.name}")
        return 1


def cmd_add_victory_condition(args: argparse.Namespace) -> int:
    """Add victory condition to scenario."""
    editor = ScenarioEditor(args.scenario)

    try:
        editor.add_victory_condition(
            vc_type=args.type,
            description=args.description,
            victor=args.victor,
            zones=args.zones,
            controller=args.controller,
            turns_held=args.turns_held,
            threshold=args.threshold,
            faction=args.faction,
            max_turns=args.max_turns
        )
        editor.save()
        print(f"Added victory condition: {args.description}")
        return 0
    except ValueError as e:
        print(f"Error: {e}")
        return 1


def cmd_add_unit(args: argparse.Namespace) -> int:
    """Add unit to ORBAT."""
    editor = ORBATEditor(args.orbat)

    try:
        editor.add_unit(
            unit_id=args.id,
            name=args.name,
            unit_type=args.type,
            echelon=args.echelon,
            lat=args.lat,
            lon=args.lon,
            personnel=args.personnel,
            personnel_max=args.personnel_max,
            mobility_class=args.mobility,
            posture=args.posture,
            parent_id=args.parent,
            equipment=args.equipment,
            equipment_max=args.equipment_max
        )
        editor.save()
        print(f"Added unit: {args.name} ({args.id})")
        return 0
    except ValueError as e:
        print(f"Error: {e}")
        return 1


def cmd_remove_unit(args: argparse.Namespace) -> int:
    """Remove unit from ORBAT."""
    editor = ORBATEditor(args.orbat)

    if editor.remove_unit(args.id):
        editor.save()
        print(f"Removed unit: {args.id}")
        return 0
    else:
        print(f"Unit not found: {args.id}")
        return 1


def cmd_move_unit(args: argparse.Namespace) -> int:
    """Move unit to new coordinates."""
    editor = ORBATEditor(args.orbat)

    if editor.move_unit(args.id, args.lat, args.lon):
        editor.save()
        print(f"Moved unit {args.id} to ({args.lat}, {args.lon})")
        return 0
    else:
        print(f"Unit not found: {args.id}")
        return 1


def cmd_info(args: argparse.Namespace) -> int:
    """Display file summary."""
    file_type = args.type
    if file_type == "auto":
        file_type = detect_file_type(args.file)

    if file_type == "scenario":
        editor = ScenarioEditor(args.file)
        print(editor.get_summary())
    elif file_type == "orbat":
        editor = ORBATEditor(args.file)
        print(f"ORBAT: {editor.data.get('name', 'Unnamed')}")
        print(f"Faction: {editor.data.get('faction', 'Not set')}")
        print(f"Units: {editor.get_unit_count()}")
        print("\nHierarchy:")
        print(editor.get_hierarchy_tree())
    else:
        print(f"Unknown file type: {args.file}")
        return 1

    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export to JSON."""
    file_type = detect_file_type(args.file)

    if file_type == "scenario":
        editor = ScenarioEditor(args.file)
    elif file_type == "orbat":
        editor = ORBATEditor(args.file)
    else:
        print(f"Unknown file type: {args.file}")
        return 1

    editor.export_json(args.output)
    print(f"Exported to: {args.output}")
    return 0


def cmd_list_templates(args: argparse.Namespace) -> int:
    """List available templates."""
    print("\nScenario Templates:")
    print("=" * 40)
    for name, template in SCENARIO_TEMPLATES.items():
        scenario = template.get('scenario', {})
        print(f"  {name}:")
        print(f"    {scenario.get('description', 'No description')[:60]}")
    print()

    print("ORBAT Templates:")
    print("=" * 40)
    for name, template in ORBAT_TEMPLATES.items():
        units = template.get('units', [])
        print(f"  {name}:")
        print(f"    {template.get('name', 'Unnamed')} ({len(units)} units)")
    print()

    return 0


def cmd_list_regions(args: argparse.Namespace) -> int:
    """List predefined regions."""
    print("\nPredefined Regions:")
    print("=" * 50)
    for name, region in PREDEFINED_REGIONS.items():
        bounds = region['bounds']
        sw = bounds['southwest']
        ne = bounds['northeast']
        print(f"  {name}:")
        print(f"    {region['description']}")
        print(f"    Bounds: {sw[0]:.2f},{sw[1]:.2f} to {ne[0]:.2f},{ne[1]:.2f}")
        print(f"    Terrain: {region['terrain_source']}")
        print()
    return 0


def cmd_set_briefing(args: argparse.Namespace) -> int:
    """Set faction briefing."""
    editor = ScenarioEditor(args.scenario)

    if args.file:
        with open(args.file) as f:
            text = f.read()
    elif args.text:
        text = args.text
    else:
        print("Error: must specify --text or --file")
        return 1

    editor.set_briefing(args.faction, text)
    editor.save()
    print(f"Set {args.faction} briefing ({len(text)} chars)")
    return 0


def cmd_interactive(args: argparse.Namespace) -> int:
    """Launch interactive editor."""
    from .interactive import run_interactive
    return run_interactive(args.type, args.file)


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    commands = {
        "new": cmd_new,
        "new-orbat": cmd_new_orbat,
        "validate": cmd_validate,
        "add-objective": cmd_add_objective,
        "remove-objective": cmd_remove_objective,
        "add-victory-condition": cmd_add_victory_condition,
        "add-unit": cmd_add_unit,
        "remove-unit": cmd_remove_unit,
        "move-unit": cmd_move_unit,
        "info": cmd_info,
        "export": cmd_export,
        "list-templates": cmd_list_templates,
        "list-regions": cmd_list_regions,
        "set-briefing": cmd_set_briefing,
        "interactive": cmd_interactive,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except FileNotFoundError as e:
        logger.error(f"File not found: {e.filename}")
        return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
