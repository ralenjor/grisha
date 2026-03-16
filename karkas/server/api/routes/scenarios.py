"""Scenario management routes"""
import os
from typing import Optional
from fastapi import APIRouter

from server.exceptions import (
    ScenarioNotFoundError,
    DuplicateResourceError,
    MissingFieldError,
    ActiveScenarioError,
    NoActiveScenarioError,
)

router = APIRouter()

# In-memory scenario storage
_scenarios: dict[str, dict] = {
    "fulda_gap_1985": {
        "id": "fulda_gap_1985",
        "name": "Fulda Gap 1985",
        "description": "Soviet offensive through the Fulda Gap against NATO forces",
        "region": {
            "southwest": {"latitude": 50.0, "longitude": 9.0},
            "northeast": {"latitude": 51.0, "longitude": 10.5},
        },
        "terrain_data_path": "data/terrain/fulda.gpkg",
        "red_faction": {
            "name": "Warsaw Pact",
            "faction": "red",
            "doctrine": "soviet_offensive",
            "ai_controlled": True,
        },
        "blue_faction": {
            "name": "NATO",
            "faction": "blue",
            "doctrine": "nato_defense",
            "ai_controlled": False,
        },
        "turn_length_hours": 4,
        "start_time": "1985-08-15T06:00:00",
        "victory_conditions": [
            {
                "type": "territorial",
                "zone_names": ["frankfurt", "kassel"],
                "required_controller": "red",
            },
            {
                "type": "time",
                "max_turns": 30,
            },
        ],
    },
    "tutorial": {
        "id": "tutorial",
        "name": "Tutorial Scenario",
        "description": "Small-scale training scenario",
        "region": {
            "southwest": {"latitude": 50.3, "longitude": 9.5},
            "northeast": {"latitude": 50.6, "longitude": 10.0},
        },
        "terrain_data_path": None,
        "red_faction": {
            "name": "Red Force",
            "faction": "red",
            "doctrine": "offensive",
            "ai_controlled": True,
        },
        "blue_faction": {
            "name": "Blue Force",
            "faction": "blue",
            "doctrine": "defensive",
            "ai_controlled": False,
        },
        "turn_length_hours": 4,
        "start_time": "2025-01-01T06:00:00",
        "victory_conditions": [
            {
                "type": "attrition",
                "attrition_threshold": 0.5,
            },
        ],
    },
}

_active_scenario: Optional[str] = None


@router.get("")
async def list_scenarios():
    """List all available scenarios"""
    scenarios = [
        {
            "id": s["id"],
            "name": s["name"],
            "description": s["description"],
            "red_faction_name": s["red_faction"]["name"],
            "blue_faction_name": s["blue_faction"]["name"],
        }
        for s in _scenarios.values()
    ]
    return {"scenarios": scenarios}


@router.get("/active")
async def get_active_scenario():
    """Get the currently active scenario"""
    if not _active_scenario:
        return {"active": False, "scenario": None}

    return {
        "active": True,
        "scenario": _scenarios.get(_active_scenario),
    }


@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Get a specific scenario by ID"""
    scenario = _scenarios.get(scenario_id)
    if not scenario:
        raise ScenarioNotFoundError(scenario_id)
    return scenario


@router.post("/{scenario_id}/load")
async def load_scenario(scenario_id: str):
    """Load and activate a scenario"""
    global _active_scenario

    scenario = _scenarios.get(scenario_id)
    if not scenario:
        raise ScenarioNotFoundError(scenario_id)

    # In production, this would:
    # 1. Load terrain data
    # 2. Initialize ORBAT
    # 3. Set up victory conditions
    # 4. Initialize Grisha instances if AI-controlled

    _active_scenario = scenario_id

    return {
        "message": f"Scenario '{scenario['name']}' loaded",
        "scenario": scenario,
    }


@router.post("")
async def create_scenario(scenario_data: dict):
    """Create a new scenario"""
    scenario_id = scenario_data.get("id")
    if not scenario_id:
        import uuid
        scenario_id = str(uuid.uuid4())
        scenario_data["id"] = scenario_id

    if scenario_id in _scenarios:
        raise DuplicateResourceError("Scenario", scenario_id)

    # Validate required fields
    required = ["name", "region", "red_faction", "blue_faction"]
    for field in required:
        if field not in scenario_data:
            raise MissingFieldError(field, resource="Scenario")

    _scenarios[scenario_id] = scenario_data
    return scenario_data


@router.put("/{scenario_id}")
async def update_scenario(scenario_id: str, updates: dict):
    """Update an existing scenario"""
    if scenario_id not in _scenarios:
        raise ScenarioNotFoundError(scenario_id)

    if scenario_id == _active_scenario:
        raise ActiveScenarioError(scenario_id, "update")

    _scenarios[scenario_id].update(updates)
    return _scenarios[scenario_id]


@router.delete("/{scenario_id}")
async def delete_scenario(scenario_id: str):
    """Delete a scenario"""
    if scenario_id not in _scenarios:
        raise ScenarioNotFoundError(scenario_id)

    if scenario_id == _active_scenario:
        raise ActiveScenarioError(scenario_id, "delete")

    del _scenarios[scenario_id]
    return {"message": "Scenario deleted"}


@router.post("/active/unload")
async def unload_scenario():
    """Unload the active scenario"""
    global _active_scenario

    if not _active_scenario:
        raise NoActiveScenarioError()

    scenario_name = _scenarios[_active_scenario]["name"]
    _active_scenario = None

    return {"message": f"Scenario '{scenario_name}' unloaded"}


@router.get("/{scenario_id}/orbat")
async def get_scenario_orbat(scenario_id: str, faction: Optional[str] = None):
    """Get ORBAT for a scenario"""
    scenario = _scenarios.get(scenario_id)
    if not scenario:
        raise ScenarioNotFoundError(scenario_id)

    # In production, load ORBAT from file
    # For now, return sample data
    orbat = {
        "red": [
            {
                "id": "red_1mrd_hq",
                "name": "1st Motor Rifle Division HQ",
                "type": "headquarters",
                "echelon": "division",
            },
            {
                "id": "red_1mrd_1bn",
                "name": "1st Motor Rifle Battalion",
                "type": "mechanized",
                "echelon": "battalion",
                "parent_id": "red_1mrd_hq",
            },
        ],
        "blue": [
            {
                "id": "blue_1ad_hq",
                "name": "1st Armored Division HQ",
                "type": "headquarters",
                "echelon": "division",
            },
            {
                "id": "blue_1bde",
                "name": "1st Brigade Combat Team",
                "type": "mechanized",
                "echelon": "brigade",
                "parent_id": "blue_1ad_hq",
            },
        ],
    }

    if faction:
        return {"faction": faction, "units": orbat.get(faction, [])}

    return orbat
