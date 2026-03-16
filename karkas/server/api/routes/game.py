"""Game management routes"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter

from server.exceptions import (
    InvalidFactionError,
    InvalidStateError,
)

router = APIRouter()

# Game state (simplified)
_game_state = {
    "turn": 0,
    "phase": "planning",
    "scenario": None,
    "red_ready": False,
    "blue_ready": False,
    "game_over": False,
    "winner": None,
    "turn_state": {
        "turn_number": 0,
        "simulation_time": datetime.now().isoformat(),
        "turn_length_hours": 4,
        "weather": {
            "precipitation": "none",
            "visibility": "clear",
            "temperature_c": 20.0,
            "wind_speed_kph": 10.0,
            "wind_direction": 0.0,
        },
        "time_of_day": {
            "hour": 6,
            "minute": 0,
        },
    },
}

# Turn history
_turn_history: list[dict] = []


@router.get("/state")
async def get_game_state():
    """Get current game state"""
    return _game_state


@router.get("/turn")
async def get_current_turn():
    """Get current turn number and phase"""
    return {
        "turn": _game_state["turn"],
        "phase": _game_state["phase"],
        "time_of_day": _game_state["turn_state"]["time_of_day"],
        "weather": _game_state["turn_state"]["weather"],
    }


@router.get("/history")
async def get_turn_history(start_turn: int = 0, end_turn: Optional[int] = None):
    """Get turn history"""
    if end_turn is None:
        end_turn = _game_state["turn"]

    history = [
        h for h in _turn_history
        if start_turn <= h["turn"] <= end_turn
    ]

    return {"history": history}


@router.post("/ready/{faction}")
async def mark_ready(faction: str):
    """Mark a faction as ready for turn execution"""
    if faction not in ["red", "blue"]:
        raise InvalidFactionError(faction)

    if _game_state["phase"] != "planning":
        raise InvalidStateError(
            "Cannot mark ready outside planning phase",
            current_state=_game_state["phase"],
            required_state="planning",
        )

    if faction == "red":
        _game_state["red_ready"] = True
    else:
        _game_state["blue_ready"] = True

    # Check if both ready
    both_ready = _game_state["red_ready"] and _game_state["blue_ready"]

    return {
        "message": f"{faction} marked ready",
        "both_ready": both_ready,
    }


@router.post("/execute")
async def execute_turn_manual():
    """Manually trigger turn execution (for testing)"""
    if _game_state["phase"] != "planning":
        raise InvalidStateError(
            "Cannot execute turn outside planning phase",
            current_state=_game_state["phase"],
            required_state="planning",
        )

    # Execute turn
    result = execute_turn()
    return result


@router.post("/reset")
async def reset_game():
    """Reset the game"""
    _game_state["turn"] = 0
    _game_state["phase"] = "planning"
    _game_state["red_ready"] = False
    _game_state["blue_ready"] = False
    _game_state["game_over"] = False
    _game_state["winner"] = None
    _turn_history.clear()

    return {"message": "Game reset"}


@router.post("/weather")
async def set_weather(weather: dict):
    """Set weather conditions"""
    _game_state["turn_state"]["weather"].update(weather)
    return _game_state["turn_state"]["weather"]


@router.get("/victory-check")
async def check_victory():
    """Check current victory status"""
    # Simplified victory check
    return {
        "game_over": _game_state["game_over"],
        "winner": _game_state["winner"],
        "reason": None,
    }


def execute_turn() -> dict:
    """Execute a game turn (simplified)"""
    _game_state["phase"] = "execution"

    # Record turn start
    turn_record = {
        "turn": _game_state["turn"],
        "start_time": datetime.now().isoformat(),
        "movements": [],
        "combats": [],
        "detections": [],
    }

    # Simulate execution (would call C++ core)

    # Update time of day
    time = _game_state["turn_state"]["time_of_day"]
    hours = _game_state["turn_state"]["turn_length_hours"]
    time["hour"] = (time["hour"] + hours) % 24

    # Update simulation time
    _game_state["turn_state"]["turn_number"] = _game_state["turn"] + 1

    # Record turn end
    turn_record["end_time"] = datetime.now().isoformat()
    _turn_history.append(turn_record)

    # Advance to next turn
    _game_state["turn"] += 1
    _game_state["phase"] = "planning"
    _game_state["red_ready"] = False
    _game_state["blue_ready"] = False

    return {
        "turn": _game_state["turn"] - 1,
        "result": turn_record,
        "next_turn": _game_state["turn"],
    }


@router.get("/timeline")
async def get_timeline():
    """Get simulation timeline"""
    return {
        "current_turn": _game_state["turn"],
        "current_time": _game_state["turn_state"]["simulation_time"],
        "turn_length_hours": _game_state["turn_state"]["turn_length_hours"],
        "total_elapsed_hours": _game_state["turn"] * _game_state["turn_state"]["turn_length_hours"],
    }
