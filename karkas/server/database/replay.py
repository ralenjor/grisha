"""
Replay Functionality (8.1.5)

Provides replay capabilities for reviewing past games turn by turn,
including:
- Step forward/backward through turns
- Jump to specific turns
- Get events for current turn
- Reconstruct game state from snapshots
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session

from .game_store import GameStore
from .turn_history import TurnHistoryStore

from server.api.models.units import Unit, Faction
from server.api.models.orders import Order
from server.api.models.game import (
    GameState,
    TurnResult,
    TurnState,
    TurnPhase,
    PerceptionState,
    Contact,
    ControlZone,
    CombatEvent,
    MovementEvent,
    DetectionEvent,
)


class ReplayDirection(str, Enum):
    """Direction of replay navigation"""
    FORWARD = "forward"
    BACKWARD = "backward"


@dataclass
class ReplayState:
    """Current state of a replay session"""
    game_id: str
    current_turn: int
    max_turn: int
    is_at_start: bool
    is_at_end: bool
    turn_result: Optional[TurnResult] = None
    game_state: Optional[GameState] = None
    units: list[Unit] = field(default_factory=list)
    red_contacts: list[Contact] = field(default_factory=list)
    blue_contacts: list[Contact] = field(default_factory=list)
    control_zones: list[ControlZone] = field(default_factory=list)


class ReplayController:
    """Controller for game replay functionality"""

    def __init__(
        self,
        game_store: Optional[GameStore] = None,
        turn_history: Optional[TurnHistoryStore] = None,
    ):
        """Initialize with optional dependencies"""
        self._game_store = game_store or GameStore()
        self._turn_history = turn_history or TurnHistoryStore(self._game_store)
        self._current_game_id: Optional[str] = None
        self._current_turn: int = 0
        self._max_turn: int = 0

    # =========================================================================
    # REPLAY SESSION MANAGEMENT
    # =========================================================================

    def start_replay(
        self,
        game_id: str,
        start_turn: int = 0,
        session: Optional[Session] = None,
    ) -> ReplayState:
        """Start a replay session for a game

        Args:
            game_id: The game ID to replay
            start_turn: Starting turn number (default: 0)
            session: Optional database session

        Returns:
            Initial replay state
        """
        # Verify game exists
        db_game = self._game_store.get_game(game_id, session)
        if db_game is None:
            raise ValueError(f"Game not found: {game_id}")

        # Get max turn
        max_turn = self._turn_history.get_latest_turn(game_id, session)
        if max_turn is None:
            max_turn = 0

        # Validate start turn
        if start_turn < 0 or start_turn > max_turn:
            raise ValueError(f"Invalid start turn: {start_turn} (max: {max_turn})")

        self._current_game_id = game_id
        self._current_turn = start_turn
        self._max_turn = max_turn

        return self._get_current_state(session)

    def end_replay(self) -> None:
        """End the current replay session"""
        self._current_game_id = None
        self._current_turn = 0
        self._max_turn = 0

    def is_active(self) -> bool:
        """Check if a replay session is active"""
        return self._current_game_id is not None

    # =========================================================================
    # NAVIGATION
    # =========================================================================

    def step_forward(self, session: Optional[Session] = None) -> ReplayState:
        """Move to the next turn

        Args:
            session: Optional database session

        Returns:
            Updated replay state
        """
        if not self.is_active():
            raise RuntimeError("No active replay session")

        if self._current_turn < self._max_turn:
            self._current_turn += 1

        return self._get_current_state(session)

    def step_backward(self, session: Optional[Session] = None) -> ReplayState:
        """Move to the previous turn

        Args:
            session: Optional database session

        Returns:
            Updated replay state
        """
        if not self.is_active():
            raise RuntimeError("No active replay session")

        if self._current_turn > 0:
            self._current_turn -= 1

        return self._get_current_state(session)

    def jump_to_turn(self, turn: int, session: Optional[Session] = None) -> ReplayState:
        """Jump to a specific turn

        Args:
            turn: Target turn number
            session: Optional database session

        Returns:
            Updated replay state
        """
        if not self.is_active():
            raise RuntimeError("No active replay session")

        if turn < 0 or turn > self._max_turn:
            raise ValueError(f"Invalid turn: {turn} (range: 0-{self._max_turn})")

        self._current_turn = turn
        return self._get_current_state(session)

    def jump_to_start(self, session: Optional[Session] = None) -> ReplayState:
        """Jump to the start of the game

        Args:
            session: Optional database session

        Returns:
            Updated replay state
        """
        return self.jump_to_turn(0, session)

    def jump_to_end(self, session: Optional[Session] = None) -> ReplayState:
        """Jump to the end of the game

        Args:
            session: Optional database session

        Returns:
            Updated replay state
        """
        return self.jump_to_turn(self._max_turn, session)

    # =========================================================================
    # STATE RETRIEVAL
    # =========================================================================

    def _get_current_state(self, session: Optional[Session] = None) -> ReplayState:
        """Get the current replay state

        Args:
            session: Optional database session

        Returns:
            Current replay state
        """
        if not self.is_active():
            raise RuntimeError("No active replay session")

        # Get turn result
        turn_result = self._turn_history.get_turn_result(
            self._current_game_id, self._current_turn, session
        )

        # Try to get state from snapshot
        snapshot = self._turn_history.get_state_snapshot(
            self._current_game_id, self._current_turn, session
        )

        # Reconstruct state
        units = []
        red_contacts = []
        blue_contacts = []
        control_zones = []
        game_state = None

        if snapshot:
            # Reconstruct from snapshot
            game_state = self._reconstruct_game_state(snapshot)
            units = self._reconstruct_units(snapshot)
            red_contacts = self._reconstruct_contacts(snapshot, Faction.RED)
            blue_contacts = self._reconstruct_contacts(snapshot, Faction.BLUE)
            control_zones = self._reconstruct_control_zones(snapshot)
        else:
            # Load current state from database (for turn 0 or if no snapshot)
            full_state = self._game_store.load_full_state(self._current_game_id, session)
            if full_state:
                game_state = full_state["game_state"]
                units = full_state["units"]
                if full_state["red_perception"]:
                    red_contacts = full_state["red_perception"].contacts
                if full_state["blue_perception"]:
                    blue_contacts = full_state["blue_perception"].contacts
                control_zones = full_state["control_zones"]

        return ReplayState(
            game_id=self._current_game_id,
            current_turn=self._current_turn,
            max_turn=self._max_turn,
            is_at_start=self._current_turn == 0,
            is_at_end=self._current_turn == self._max_turn,
            turn_result=turn_result,
            game_state=game_state,
            units=units,
            red_contacts=red_contacts,
            blue_contacts=blue_contacts,
            control_zones=control_zones,
        )

    def get_current_turn_result(self, session: Optional[Session] = None) -> Optional[TurnResult]:
        """Get the turn result for the current turn

        Args:
            session: Optional database session

        Returns:
            Turn result or None
        """
        if not self.is_active():
            return None
        return self._turn_history.get_turn_result(
            self._current_game_id, self._current_turn, session
        )

    def get_current_events(
        self,
        session: Optional[Session] = None,
    ) -> dict:
        """Get all events for the current turn

        Args:
            session: Optional database session

        Returns:
            Dictionary of event lists
        """
        if not self.is_active():
            return {}

        return {
            "combats": self._turn_history.get_combat_events(
                self._current_game_id, self._current_turn, session
            ),
            "movements": self._turn_history.get_movement_events(
                self._current_game_id, self._current_turn, session
            ),
            "detections": self._turn_history.get_detection_events(
                self._current_game_id, self._current_turn, session
            ),
        }

    # =========================================================================
    # STATE RECONSTRUCTION
    # =========================================================================

    def _reconstruct_game_state(self, snapshot: dict) -> Optional[GameState]:
        """Reconstruct GameState from snapshot"""
        if "game_state" not in snapshot:
            return None

        gs_data = snapshot["game_state"]
        return GameState(
            turn=gs_data.get("turn", 0),
            phase=TurnPhase(gs_data.get("phase", "planning")),
            turn_state=TurnState(**gs_data.get("turn_state", {})),
            red_ready=gs_data.get("red_ready", False),
            blue_ready=gs_data.get("blue_ready", False),
            game_over=gs_data.get("game_over", False),
            winner=Faction(gs_data["winner"]) if gs_data.get("winner") else None,
        )

    def _reconstruct_units(self, snapshot: dict) -> list[Unit]:
        """Reconstruct units from snapshot"""
        units_data = snapshot.get("units", [])
        return [Unit(**u) for u in units_data]

    def _reconstruct_contacts(self, snapshot: dict, faction: Faction) -> list[Contact]:
        """Reconstruct contacts for a faction from snapshot"""
        key = f"{faction.value}_contacts"
        contacts_data = snapshot.get(key, [])
        return [Contact(**c) for c in contacts_data]

    def _reconstruct_control_zones(self, snapshot: dict) -> list[ControlZone]:
        """Reconstruct control zones from snapshot"""
        zones_data = snapshot.get("control_zones", [])
        return [ControlZone(**z) for z in zones_data]

    # =========================================================================
    # REPLAY ANALYSIS
    # =========================================================================

    def get_turn_summary(
        self,
        turn: int,
        session: Optional[Session] = None,
    ) -> dict:
        """Get a summary of what happened in a specific turn

        Args:
            turn: Turn number
            session: Optional database session

        Returns:
            Turn summary dictionary
        """
        if not self.is_active():
            raise RuntimeError("No active replay session")

        result = self._turn_history.get_turn_result(
            self._current_game_id, turn, session
        )
        if result is None:
            return {"error": f"No result for turn {turn}"}

        return {
            "turn": turn,
            "movement_count": len(result.movements),
            "combat_count": len(result.combats),
            "detection_count": len(result.detections),
            "red_summary": result.red_summary,
            "blue_summary": result.blue_summary,
            "game_over": result.game_over,
            "winner": result.winner.value if result.winner else None,
        }

    def get_all_turn_summaries(
        self,
        session: Optional[Session] = None,
    ) -> list[dict]:
        """Get summaries for all turns

        Args:
            session: Optional database session

        Returns:
            List of turn summaries
        """
        if not self.is_active():
            raise RuntimeError("No active replay session")

        summaries = []
        for turn in range(self._max_turn + 1):
            summaries.append(self.get_turn_summary(turn, session))
        return summaries

    def find_events_involving_unit(
        self,
        unit_id: str,
        session: Optional[Session] = None,
    ) -> dict:
        """Find all events involving a specific unit across all turns

        Args:
            unit_id: The unit ID to search for
            session: Optional database session

        Returns:
            Dictionary with lists of events by type
        """
        if not self.is_active():
            raise RuntimeError("No active replay session")

        return self._turn_history.get_unit_history(
            self._current_game_id, unit_id, session
        )

    def get_victory_analysis(
        self,
        session: Optional[Session] = None,
    ) -> dict:
        """Analyze the game outcome

        Args:
            session: Optional database session

        Returns:
            Victory analysis dictionary
        """
        if not self.is_active():
            raise RuntimeError("No active replay session")

        stats = self._turn_history.get_game_statistics(
            self._current_game_id, session
        )

        # Get final turn result
        final_result = self._turn_history.get_turn_result(
            self._current_game_id, self._max_turn, session
        )

        return {
            **stats,
            "final_turn": self._max_turn,
            "victory_reason": final_result.victory_reason if final_result else None,
        }

    # =========================================================================
    # EXPORT
    # =========================================================================

    def export_replay(
        self,
        session: Optional[Session] = None,
    ) -> dict:
        """Export the complete replay data

        Args:
            session: Optional database session

        Returns:
            Complete replay data dictionary
        """
        if not self.is_active():
            raise RuntimeError("No active replay session")

        db_game = self._game_store.get_game(self._current_game_id, session)
        all_results = self._turn_history.get_all_turn_results(
            self._current_game_id, session
        )
        stats = self._turn_history.get_game_statistics(
            self._current_game_id, session
        )

        return {
            "game_id": self._current_game_id,
            "scenario_name": db_game.scenario_name,
            "scenario_config": db_game.scenario_config,
            "total_turns": self._max_turn,
            "turn_results": [r.model_dump(mode="json") for r in all_results],
            "statistics": stats,
            "exported_at": datetime.utcnow().isoformat(),
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def create_replay_controller() -> ReplayController:
    """Factory function to create a ReplayController with dependencies"""
    game_store = GameStore()
    turn_history = TurnHistoryStore(game_store)
    return ReplayController(game_store, turn_history)


def replay_game(
    game_id: str,
    session: Optional[Session] = None,
) -> ReplayController:
    """Start a replay session for a game

    Args:
        game_id: The game ID
        session: Optional database session

    Returns:
        Active ReplayController
    """
    controller = create_replay_controller()
    controller.start_replay(game_id, session=session)
    return controller
