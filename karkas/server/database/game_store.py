"""
Game Store (8.1.3 - Save/Load Functionality)

Provides high-level operations for saving and loading complete game states,
including all units, orders, contacts, and control zones.
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, delete
from sqlalchemy.orm import Session, selectinload
from geoalchemy2.shape import from_shape
from shapely.geometry import Polygon

from .models import (
    DBGame,
    DBUnit,
    DBOrder,
    DBContact,
    DBControlZone,
)
from .session import get_session

from server.api.models.units import Unit, Faction
from server.api.models.orders import Order
from server.api.models.game import (
    GameState,
    TurnState,
    Contact,
    ControlZone,
    PerceptionState,
    ScenarioConfig,
    BoundingBox,
    TurnPhase,
)


class GameStore:
    """High-level game persistence operations"""

    def __init__(self, session: Optional[Session] = None):
        """Initialize with optional session (for dependency injection)"""
        self._session = session
        self._owns_session = session is None

    def _get_session(self) -> Session:
        """Get the current session or create a new one"""
        if self._session is not None:
            return self._session
        raise RuntimeError("No session provided - use context manager or provide session")

    # =========================================================================
    # GAME LIFECYCLE
    # =========================================================================

    def create_game(
        self,
        scenario: ScenarioConfig,
        game_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> str:
        """Create a new game from scenario configuration

        Args:
            scenario: The scenario configuration
            game_id: Optional game ID (auto-generated if not provided)
            session: Optional session (uses internal if not provided)

        Returns:
            The game ID
        """
        sess = session or self._get_session()
        game_id = game_id or f"game_{uuid4().hex[:12]}"

        # Create initial turn state
        turn_state = TurnState(
            turn_number=0,
            simulation_time=scenario.start_time,
            turn_length_hours=scenario.turn_length_hours,
            time_of_day={"hour": scenario.start_time.hour, "minute": scenario.start_time.minute},
        )

        # Create game record
        db_game = DBGame(
            game_id=game_id,
            scenario_name=scenario.name,
            scenario_description=scenario.description,
            scenario_config=scenario.model_dump(mode="json"),
            turn=0,
            phase="planning",
            turn_state=turn_state.model_dump(mode="json"),
        )
        db_game.set_region(scenario.region)

        sess.add(db_game)
        sess.flush()  # Get the ID

        return game_id

    def get_game(
        self,
        game_id: str,
        session: Optional[Session] = None,
    ) -> Optional[DBGame]:
        """Get a game by ID

        Args:
            game_id: The game ID
            session: Optional session

        Returns:
            The game record or None
        """
        sess = session or self._get_session()
        stmt = select(DBGame).where(DBGame.game_id == game_id)
        result = sess.execute(stmt)
        return result.scalar_one_or_none()

    def delete_game(
        self,
        game_id: str,
        session: Optional[Session] = None,
    ) -> bool:
        """Delete a game and all related data

        Args:
            game_id: The game ID
            session: Optional session

        Returns:
            True if deleted, False if not found
        """
        sess = session or self._get_session()
        db_game = self.get_game(game_id, sess)
        if db_game is None:
            return False

        sess.delete(db_game)
        return True

    def list_games(
        self,
        include_completed: bool = True,
        session: Optional[Session] = None,
    ) -> list[dict]:
        """List all games

        Args:
            include_completed: Include completed games
            session: Optional session

        Returns:
            List of game summaries
        """
        sess = session or self._get_session()
        stmt = select(DBGame)
        if not include_completed:
            stmt = stmt.where(DBGame.game_over == False)
        stmt = stmt.order_by(DBGame.updated_at.desc())

        result = sess.execute(stmt)
        games = []
        for db_game in result.scalars():
            games.append({
                "game_id": db_game.game_id,
                "scenario_name": db_game.scenario_name,
                "turn": db_game.turn,
                "phase": db_game.phase,
                "game_over": db_game.game_over,
                "winner": db_game.winner,
                "created_at": db_game.created_at.isoformat(),
                "updated_at": db_game.updated_at.isoformat(),
            })
        return games

    # =========================================================================
    # GAME STATE OPERATIONS
    # =========================================================================

    def save_game_state(
        self,
        game_id: str,
        game_state: GameState,
        session: Optional[Session] = None,
    ) -> None:
        """Save the current game state

        Args:
            game_id: The game ID
            game_state: The game state to save
            session: Optional session
        """
        sess = session or self._get_session()
        db_game = self.get_game(game_id, sess)
        if db_game is None:
            raise ValueError(f"Game not found: {game_id}")

        db_game.turn = game_state.turn
        db_game.phase = game_state.phase.value
        db_game.turn_state = game_state.turn_state.model_dump(mode="json")
        db_game.red_ready = game_state.red_ready
        db_game.blue_ready = game_state.blue_ready
        db_game.game_over = game_state.game_over
        db_game.winner = game_state.winner.value if game_state.winner else None
        db_game.updated_at = datetime.utcnow()

    def load_game_state(
        self,
        game_id: str,
        session: Optional[Session] = None,
    ) -> Optional[GameState]:
        """Load the game state

        Args:
            game_id: The game ID
            session: Optional session

        Returns:
            The game state or None if not found
        """
        sess = session or self._get_session()
        db_game = self.get_game(game_id, sess)
        if db_game is None:
            return None
        return db_game.to_game_state()

    # =========================================================================
    # UNIT OPERATIONS
    # =========================================================================

    def save_units(
        self,
        game_id: str,
        units: list[Unit],
        session: Optional[Session] = None,
    ) -> None:
        """Save units to the database (upsert)

        Args:
            game_id: The game ID
            units: List of units to save
            session: Optional session
        """
        sess = session or self._get_session()
        db_game = self.get_game(game_id, sess)
        if db_game is None:
            raise ValueError(f"Game not found: {game_id}")

        # Get existing units
        existing = {u.unit_id: u for u in db_game.units}

        for unit in units:
            if unit.id in existing:
                # Update existing unit
                db_unit = existing[unit.id]
                db_unit.name = unit.name
                db_unit.faction = unit.faction.value
                db_unit.unit_type = unit.type.value
                db_unit.echelon = unit.echelon.value
                db_unit.mobility_class = unit.mobility_class.value
                db_unit.set_position(unit.position)
                db_unit.heading = unit.heading
                db_unit.posture = unit.posture.value
                db_unit.parent_unit_id = unit.parent_id
                db_unit.subordinate_ids = unit.subordinate_ids
                db_unit.combat_stats = unit.combat_stats.model_dump()
                db_unit.sensors = [s.model_dump() for s in unit.sensors]
                db_unit.fuel_level = unit.logistics.fuel_level
                db_unit.ammo_level = unit.logistics.ammo_level
                db_unit.supply_level = unit.logistics.supply_level
                db_unit.maintenance_state = unit.logistics.maintenance_state
                db_unit.morale = unit.morale.morale
                db_unit.fatigue = unit.morale.fatigue
                db_unit.cohesion = unit.morale.cohesion
                db_unit.personnel_current = unit.strength.personnel_current
                db_unit.personnel_max = unit.strength.personnel_max
                db_unit.equipment_current = unit.strength.equipment_current
                db_unit.equipment_max = unit.strength.equipment_max
                db_unit.current_order_id = unit.current_order_id
            else:
                # Create new unit
                db_unit = DBUnit.from_pydantic(db_game.id, unit)
                sess.add(db_unit)

    def load_units(
        self,
        game_id: str,
        faction: Optional[Faction] = None,
        session: Optional[Session] = None,
    ) -> list[Unit]:
        """Load units from the database

        Args:
            game_id: The game ID
            faction: Optional faction filter
            session: Optional session

        Returns:
            List of units
        """
        sess = session or self._get_session()
        db_game = self.get_game(game_id, sess)
        if db_game is None:
            return []

        stmt = select(DBUnit).where(DBUnit.game_id == db_game.id)
        if faction is not None:
            stmt = stmt.where(DBUnit.faction == faction.value)

        result = sess.execute(stmt)
        return [u.to_pydantic() for u in result.scalars()]

    def delete_unit(
        self,
        game_id: str,
        unit_id: str,
        session: Optional[Session] = None,
    ) -> bool:
        """Delete a unit

        Args:
            game_id: The game ID
            unit_id: The unit ID
            session: Optional session

        Returns:
            True if deleted, False if not found
        """
        sess = session or self._get_session()
        db_game = self.get_game(game_id, sess)
        if db_game is None:
            return False

        stmt = delete(DBUnit).where(
            DBUnit.game_id == db_game.id,
            DBUnit.unit_id == unit_id,
        )
        result = sess.execute(stmt)
        return result.rowcount > 0

    # =========================================================================
    # ORDER OPERATIONS
    # =========================================================================

    def save_orders(
        self,
        game_id: str,
        orders: list[Order],
        session: Optional[Session] = None,
    ) -> None:
        """Save orders to the database

        Args:
            game_id: The game ID
            orders: List of orders to save
            session: Optional session
        """
        sess = session or self._get_session()
        db_game = self.get_game(game_id, sess)
        if db_game is None:
            raise ValueError(f"Game not found: {game_id}")

        # Get existing orders
        existing = {o.order_id: o for o in db_game.orders}

        for order in orders:
            if order.order_id in existing:
                # Update existing order
                db_order = existing[order.order_id]
                db_order.issuer = order.issuer
                db_order.target_units = order.target_units
                db_order.order_type = order.order_type.value
                db_order.objective = order.objective.model_dump()
                db_order.constraints = order.constraints.model_dump()
                db_order.natural_language = order.natural_language
                db_order.issued_turn = order.issued_turn
                db_order.active = order.active
            else:
                # Create new order
                db_order = DBOrder.from_pydantic(db_game.id, order)
                sess.add(db_order)

    def load_orders(
        self,
        game_id: str,
        active_only: bool = False,
        session: Optional[Session] = None,
    ) -> list[Order]:
        """Load orders from the database

        Args:
            game_id: The game ID
            active_only: Only load active orders
            session: Optional session

        Returns:
            List of orders
        """
        sess = session or self._get_session()
        db_game = self.get_game(game_id, sess)
        if db_game is None:
            return []

        stmt = select(DBOrder).where(DBOrder.game_id == db_game.id)
        if active_only:
            stmt = stmt.where(DBOrder.active == True)

        result = sess.execute(stmt)
        return [o.to_pydantic() for o in result.scalars()]

    def deactivate_orders(
        self,
        game_id: str,
        session: Optional[Session] = None,
    ) -> int:
        """Deactivate all active orders (after turn execution)

        Args:
            game_id: The game ID
            session: Optional session

        Returns:
            Number of orders deactivated
        """
        sess = session or self._get_session()
        db_game = self.get_game(game_id, sess)
        if db_game is None:
            return 0

        count = 0
        for order in db_game.orders:
            if order.active:
                order.active = False
                count += 1
        return count

    # =========================================================================
    # CONTACT OPERATIONS
    # =========================================================================

    def save_contacts(
        self,
        game_id: str,
        faction: Faction,
        contacts: list[Contact],
        session: Optional[Session] = None,
    ) -> None:
        """Save contacts for a faction

        Args:
            game_id: The game ID
            faction: The observing faction
            contacts: List of contacts to save
            session: Optional session
        """
        sess = session or self._get_session()
        db_game = self.get_game(game_id, sess)
        if db_game is None:
            raise ValueError(f"Game not found: {game_id}")

        # Delete existing contacts for this faction
        stmt = delete(DBContact).where(
            DBContact.game_id == db_game.id,
            DBContact.observing_faction == faction.value,
        )
        sess.execute(stmt)

        # Insert new contacts
        for contact in contacts:
            db_contact = DBContact.from_pydantic(db_game.id, faction, contact)
            sess.add(db_contact)

    def load_contacts(
        self,
        game_id: str,
        faction: Faction,
        session: Optional[Session] = None,
    ) -> list[Contact]:
        """Load contacts for a faction

        Args:
            game_id: The game ID
            faction: The observing faction
            session: Optional session

        Returns:
            List of contacts
        """
        sess = session or self._get_session()
        db_game = self.get_game(game_id, sess)
        if db_game is None:
            return []

        stmt = select(DBContact).where(
            DBContact.game_id == db_game.id,
            DBContact.observing_faction == faction.value,
        )
        result = sess.execute(stmt)
        return [c.to_pydantic() for c in result.scalars()]

    # =========================================================================
    # CONTROL ZONE OPERATIONS
    # =========================================================================

    def save_control_zones(
        self,
        game_id: str,
        zones: list[ControlZone],
        session: Optional[Session] = None,
    ) -> None:
        """Save control zones

        Args:
            game_id: The game ID
            zones: List of control zones
            session: Optional session
        """
        sess = session or self._get_session()
        db_game = self.get_game(game_id, sess)
        if db_game is None:
            raise ValueError(f"Game not found: {game_id}")

        # Get existing zones
        existing = {z.zone_id: z for z in db_game.control_zones}

        for zone in zones:
            if zone.zone_id in existing:
                # Update existing zone
                db_zone = existing[zone.zone_id]
                db_zone.set_polygon(zone.polygon)
                db_zone.controller = zone.controller.value
                db_zone.control_strength = zone.control_strength
            else:
                # Create new zone
                db_zone = DBControlZone.from_pydantic(db_game.id, zone)
                sess.add(db_zone)

    def load_control_zones(
        self,
        game_id: str,
        session: Optional[Session] = None,
    ) -> list[ControlZone]:
        """Load control zones

        Args:
            game_id: The game ID
            session: Optional session

        Returns:
            List of control zones
        """
        sess = session or self._get_session()
        db_game = self.get_game(game_id, sess)
        if db_game is None:
            return []

        return [z.to_pydantic() for z in db_game.control_zones]

    # =========================================================================
    # PERCEPTION STATE OPERATIONS
    # =========================================================================

    def load_perception_state(
        self,
        game_id: str,
        faction: Faction,
        session: Optional[Session] = None,
    ) -> Optional[PerceptionState]:
        """Load the perception state for a faction

        Args:
            game_id: The game ID
            faction: The faction
            session: Optional session

        Returns:
            The perception state or None
        """
        sess = session or self._get_session()

        # Load units for this faction
        units = self.load_units(game_id, faction, sess)

        # Load contacts for this faction
        contacts = self.load_contacts(game_id, faction, sess)

        # Load control zones
        zones = self.load_control_zones(game_id, sess)

        return PerceptionState(
            faction=faction,
            own_units=units,
            contacts=contacts,
            control_zones=zones,
        )

    # =========================================================================
    # FULL SAVE/LOAD
    # =========================================================================

    def save_full_state(
        self,
        game_id: str,
        game_state: GameState,
        units: list[Unit],
        orders: list[Order],
        red_contacts: list[Contact],
        blue_contacts: list[Contact],
        control_zones: list[ControlZone],
        session: Optional[Session] = None,
    ) -> None:
        """Save the complete game state

        Args:
            game_id: The game ID
            game_state: The game state
            units: All units
            orders: All orders
            red_contacts: Red faction's contacts
            blue_contacts: Blue faction's contacts
            control_zones: All control zones
            session: Optional session
        """
        sess = session or self._get_session()

        self.save_game_state(game_id, game_state, sess)
        self.save_units(game_id, units, sess)
        self.save_orders(game_id, orders, sess)
        self.save_contacts(game_id, Faction.RED, red_contacts, sess)
        self.save_contacts(game_id, Faction.BLUE, blue_contacts, sess)
        self.save_control_zones(game_id, control_zones, sess)

    def load_full_state(
        self,
        game_id: str,
        session: Optional[Session] = None,
    ) -> Optional[dict]:
        """Load the complete game state

        Args:
            game_id: The game ID
            session: Optional session

        Returns:
            Dictionary with all game components or None
        """
        sess = session or self._get_session()

        game_state = self.load_game_state(game_id, sess)
        if game_state is None:
            return None

        return {
            "game_state": game_state,
            "units": self.load_units(game_id, session=sess),
            "orders": self.load_orders(game_id, session=sess),
            "red_perception": self.load_perception_state(game_id, Faction.RED, sess),
            "blue_perception": self.load_perception_state(game_id, Faction.BLUE, sess),
            "control_zones": self.load_control_zones(game_id, sess),
        }
