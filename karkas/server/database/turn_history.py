"""
Turn History Storage (8.1.4)

Provides storage and retrieval of turn results and events for game history
and replay functionality.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.orm import Session, selectinload
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from .models import (
    DBGame,
    DBTurnResult,
    DBCombatEvent,
    DBMovementEvent,
    DBDetectionEvent,
    DBSupplyEvent,
)
from .session import get_session
from .game_store import GameStore

from server.api.models.units import Unit, Faction, Coordinates
from server.api.models.orders import Order
from server.api.models.game import (
    TurnResult,
    CombatEvent,
    MovementEvent,
    DetectionEvent,
    Casualties,
    ContactConfidence,
    PerceptionState,
)


class TurnHistoryStore:
    """Turn history storage and retrieval"""

    def __init__(self, game_store: Optional[GameStore] = None):
        """Initialize with optional GameStore reference"""
        self._game_store = game_store or GameStore()

    # =========================================================================
    # TURN RESULT STORAGE
    # =========================================================================

    def save_turn_result(
        self,
        game_id: str,
        turn_result: TurnResult,
        state_snapshot: Optional[dict] = None,
        session: Optional[Session] = None,
    ) -> int:
        """Save a turn result with all events

        Args:
            game_id: The game ID
            turn_result: The turn result to save
            state_snapshot: Optional snapshot of game state for replay
            session: Optional session

        Returns:
            The turn result database ID
        """
        # Get game
        db_game = self._game_store.get_game(game_id, session)
        if db_game is None:
            raise ValueError(f"Game not found: {game_id}")

        # Check if turn result already exists
        existing = self.get_turn_result(game_id, turn_result.turn, session)
        if existing is not None:
            raise ValueError(f"Turn result already exists for turn {turn_result.turn}")

        # Create turn result
        db_result = DBTurnResult(
            game_id=db_game.id,
            turn=turn_result.turn,
            red_summary=turn_result.red_summary,
            blue_summary=turn_result.blue_summary,
            game_over=turn_result.game_over,
            winner=turn_result.winner.value if turn_result.winner else None,
            victory_reason=turn_result.victory_reason,
            state_snapshot=state_snapshot,
        )
        session.add(db_result)
        session.flush()  # Get the ID

        # Save combat events
        for event in turn_result.combats:
            db_event = DBCombatEvent(
                turn_result_id=db_result.id,
                turn=event.turn,
                attacker=event.attacker,
                defender=event.defender,
                location=from_shape(
                    Point(event.location.longitude, event.location.latitude),
                    srid=4326,
                ),
                attacker_casualties=event.attacker_casualties.model_dump(),
                defender_casualties=event.defender_casualties.model_dump(),
                attacker_retreated=event.attacker_retreated,
                defender_retreated=event.defender_retreated,
            )
            session.add(db_event)

        # Save movement events
        for event in turn_result.movements:
            db_event = DBMovementEvent(
                turn_result_id=db_result.id,
                turn=event.turn,
                unit=event.unit,
                from_position=from_shape(
                    Point(event.from_position.longitude, event.from_position.latitude),
                    srid=4326,
                ),
                to_position=from_shape(
                    Point(event.to_position.longitude, event.to_position.latitude),
                    srid=4326,
                ),
                distance_km=event.distance_km,
                completed=event.completed,
            )
            session.add(db_event)

        # Save detection events
        for event in turn_result.detections:
            db_event = DBDetectionEvent(
                turn_result_id=db_result.id,
                turn=event.turn,
                observer=event.observer,
                observed=event.observed,
                location=from_shape(
                    Point(event.location.longitude, event.location.latitude),
                    srid=4326,
                ),
                confidence=event.confidence.value,
            )
            session.add(db_event)

        return db_result.id

    def save_supply_event(
        self,
        game_id: str,
        turn: int,
        unit_id: str,
        depot_id: str,
        fuel_delivered: float = 0.0,
        ammo_delivered: float = 0.0,
        supply_delivered: float = 0.0,
        interdicted: bool = False,
        interdicting_units: Optional[list[str]] = None,
        session: Optional[Session] = None,
    ) -> None:
        """Save a supply event

        Args:
            game_id: The game ID
            turn: The turn number
            unit_id: The unit receiving supplies
            depot_id: The supply depot ID
            fuel_delivered: Amount of fuel delivered (0-1)
            ammo_delivered: Amount of ammo delivered (0-1)
            supply_delivered: Amount of supplies delivered (0-1)
            interdicted: Whether supply line was interdicted
            interdicting_units: List of unit IDs that interdicted
            session: Optional session
        """
        # Get turn result
        db_result = self._get_db_turn_result(game_id, turn, session)
        if db_result is None:
            raise ValueError(f"Turn result not found for turn {turn}")

        db_event = DBSupplyEvent(
            turn_result_id=db_result.id,
            turn=turn,
            unit=unit_id,
            depot_id=depot_id,
            fuel_delivered=fuel_delivered,
            ammo_delivered=ammo_delivered,
            supply_delivered=supply_delivered,
            supply_line_interdicted=interdicted,
            interdicting_units=interdicting_units or [],
        )
        session.add(db_event)

    # =========================================================================
    # TURN RESULT RETRIEVAL
    # =========================================================================

    def _get_db_turn_result(
        self,
        game_id: str,
        turn: int,
        session: Optional[Session] = None,
    ) -> Optional[DBTurnResult]:
        """Get the database turn result record"""
        db_game = self._game_store.get_game(game_id, session)
        if db_game is None:
            return None

        stmt = (
            select(DBTurnResult)
            .where(DBTurnResult.game_id == db_game.id, DBTurnResult.turn == turn)
            .options(
                selectinload(DBTurnResult.combat_events),
                selectinload(DBTurnResult.movement_events),
                selectinload(DBTurnResult.detection_events),
                selectinload(DBTurnResult.supply_events),
            )
        )
        result = session.execute(stmt)
        return result.scalar_one_or_none()

    def get_turn_result(
        self,
        game_id: str,
        turn: int,
        session: Optional[Session] = None,
    ) -> Optional[TurnResult]:
        """Get a turn result by turn number

        Args:
            game_id: The game ID
            turn: The turn number
            session: Optional session

        Returns:
            The turn result or None
        """
        db_result = self._get_db_turn_result(game_id, turn, session)
        if db_result is None:
            return None
        return db_result.to_pydantic()

    def get_all_turn_results(
        self,
        game_id: str,
        session: Optional[Session] = None,
    ) -> list[TurnResult]:
        """Get all turn results for a game

        Args:
            game_id: The game ID
            session: Optional session

        Returns:
            List of turn results ordered by turn number
        """
        db_game = self._game_store.get_game(game_id, session)
        if db_game is None:
            return []

        stmt = (
            select(DBTurnResult)
            .where(DBTurnResult.game_id == db_game.id)
            .order_by(DBTurnResult.turn)
            .options(
                selectinload(DBTurnResult.combat_events),
                selectinload(DBTurnResult.movement_events),
                selectinload(DBTurnResult.detection_events),
                selectinload(DBTurnResult.supply_events),
            )
        )
        result = session.execute(stmt)
        return [r.to_pydantic() for r in result.scalars()]

    def get_turn_count(
        self,
        game_id: str,
        session: Optional[Session] = None,
    ) -> int:
        """Get the number of completed turns

        Args:
            game_id: The game ID
            session: Optional session

        Returns:
            Number of turn results
        """
        db_game = self._game_store.get_game(game_id, session)
        if db_game is None:
            return 0

        return len(db_game.turn_results)

    def get_latest_turn(
        self,
        game_id: str,
        session: Optional[Session] = None,
    ) -> Optional[int]:
        """Get the latest turn number with a result

        Args:
            game_id: The game ID
            session: Optional session

        Returns:
            The latest turn number or None
        """
        db_game = self._game_store.get_game(game_id, session)
        if db_game is None:
            return None

        if not db_game.turn_results:
            return None

        return max(r.turn for r in db_game.turn_results)

    # =========================================================================
    # EVENT QUERIES
    # =========================================================================

    def get_combat_events(
        self,
        game_id: str,
        turn: Optional[int] = None,
        unit_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> list[CombatEvent]:
        """Get combat events with optional filters

        Args:
            game_id: The game ID
            turn: Optional turn filter
            unit_id: Optional unit filter (attacker or defender)
            session: Optional session

        Returns:
            List of combat events
        """
        db_game = self._game_store.get_game(game_id, session)
        if db_game is None:
            return []

        stmt = (
            select(DBCombatEvent)
            .join(DBTurnResult)
            .where(DBTurnResult.game_id == db_game.id)
        )

        if turn is not None:
            stmt = stmt.where(DBCombatEvent.turn == turn)

        if unit_id is not None:
            stmt = stmt.where(
                (DBCombatEvent.attacker == unit_id) | (DBCombatEvent.defender == unit_id)
            )

        result = session.execute(stmt)
        return [e.to_pydantic() for e in result.scalars()]

    def get_movement_events(
        self,
        game_id: str,
        turn: Optional[int] = None,
        unit_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> list[MovementEvent]:
        """Get movement events with optional filters

        Args:
            game_id: The game ID
            turn: Optional turn filter
            unit_id: Optional unit filter
            session: Optional session

        Returns:
            List of movement events
        """
        db_game = self._game_store.get_game(game_id, session)
        if db_game is None:
            return []

        stmt = (
            select(DBMovementEvent)
            .join(DBTurnResult)
            .where(DBTurnResult.game_id == db_game.id)
        )

        if turn is not None:
            stmt = stmt.where(DBMovementEvent.turn == turn)

        if unit_id is not None:
            stmt = stmt.where(DBMovementEvent.unit == unit_id)

        result = session.execute(stmt)
        return [e.to_pydantic() for e in result.scalars()]

    def get_detection_events(
        self,
        game_id: str,
        turn: Optional[int] = None,
        observer_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> list[DetectionEvent]:
        """Get detection events with optional filters

        Args:
            game_id: The game ID
            turn: Optional turn filter
            observer_id: Optional observer unit filter
            session: Optional session

        Returns:
            List of detection events
        """
        db_game = self._game_store.get_game(game_id, session)
        if db_game is None:
            return []

        stmt = (
            select(DBDetectionEvent)
            .join(DBTurnResult)
            .where(DBTurnResult.game_id == db_game.id)
        )

        if turn is not None:
            stmt = stmt.where(DBDetectionEvent.turn == turn)

        if observer_id is not None:
            stmt = stmt.where(DBDetectionEvent.observer == observer_id)

        result = session.execute(stmt)
        return [e.to_pydantic() for e in result.scalars()]

    # =========================================================================
    # STATE SNAPSHOTS
    # =========================================================================

    def get_state_snapshot(
        self,
        game_id: str,
        turn: int,
        session: Optional[Session] = None,
    ) -> Optional[dict]:
        """Get the game state snapshot for a turn

        Args:
            game_id: The game ID
            turn: The turn number
            session: Optional session

        Returns:
            The state snapshot or None
        """
        db_result = self._get_db_turn_result(game_id, turn, session)
        if db_result is None:
            return None
        return db_result.state_snapshot

    def save_state_snapshot(
        self,
        game_id: str,
        turn: int,
        snapshot: dict,
        session: Optional[Session] = None,
    ) -> None:
        """Save a state snapshot for a turn

        Args:
            game_id: The game ID
            turn: The turn number
            snapshot: The state snapshot
            session: Optional session
        """
        db_result = self._get_db_turn_result(game_id, turn, session)
        if db_result is None:
            raise ValueError(f"Turn result not found for turn {turn}")
        db_result.state_snapshot = snapshot

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_game_statistics(
        self,
        game_id: str,
        session: Optional[Session] = None,
    ) -> dict:
        """Get aggregate statistics for a game

        Args:
            game_id: The game ID
            session: Optional session

        Returns:
            Dictionary of statistics
        """
        db_game = self._game_store.get_game(game_id, session)
        if db_game is None:
            return {}

        total_combats = 0
        total_movements = 0
        total_detections = 0
        total_personnel_killed = 0
        total_equipment_destroyed = 0

        for result in db_game.turn_results:
            total_combats += len(result.combat_events)
            total_movements += len(result.movement_events)
            total_detections += len(result.detection_events)

            for combat in result.combat_events:
                total_personnel_killed += (
                    combat.attacker_casualties.get("personnel_killed", 0)
                    + combat.defender_casualties.get("personnel_killed", 0)
                )
                total_equipment_destroyed += (
                    combat.attacker_casualties.get("equipment_destroyed", 0)
                    + combat.defender_casualties.get("equipment_destroyed", 0)
                )

        return {
            "game_id": game_id,
            "total_turns": len(db_game.turn_results),
            "total_combats": total_combats,
            "total_movements": total_movements,
            "total_detections": total_detections,
            "total_personnel_killed": total_personnel_killed,
            "total_equipment_destroyed": total_equipment_destroyed,
            "game_over": db_game.game_over,
            "winner": db_game.winner,
        }

    def get_unit_history(
        self,
        game_id: str,
        unit_id: str,
        session: Optional[Session] = None,
    ) -> dict:
        """Get the history of a specific unit

        Args:
            game_id: The game ID
            unit_id: The unit ID
            session: Optional session

        Returns:
            Dictionary with unit's event history
        """
        return {
            "unit_id": unit_id,
            "movements": self.get_movement_events(game_id, unit_id=unit_id, session=session),
            "combats_as_attacker": [
                e for e in self.get_combat_events(game_id, session=session)
                if e.attacker == unit_id
            ],
            "combats_as_defender": [
                e for e in self.get_combat_events(game_id, session=session)
                if e.defender == unit_id
            ],
            "detections_made": self.get_detection_events(
                game_id, observer_id=unit_id, session=session
            ),
        }
