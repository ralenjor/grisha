"""
SQLAlchemy ORM Models (8.1.2)

Defines all database models for game state persistence, including:
- Games (sessions)
- Units with full combat/logistics/morale state
- Orders with objectives and constraints
- Contacts and control zones
- Turn results with events (combat, movement, detection, supply)
"""

from datetime import datetime
from typing import Optional, Any
import json

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Index,
    UniqueConstraint,
    CheckConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape, from_shape
from shapely.geometry import Point, Polygon

from server.api.models.units import (
    Faction,
    UnitType,
    Echelon,
    Posture,
    MobilityClass,
    SensorType,
    Coordinates,
    LogisticsState,
    MoraleState,
    UnitStrength,
    CombatStats,
    Sensor,
    Unit,
)
from server.api.models.orders import (
    OrderType,
    RoutePreference,
    RulesOfEngagement,
    ObjectiveType,
    Order,
    Objective,
    OrderConstraints,
)
from server.api.models.game import (
    TurnPhase,
    Precipitation,
    Visibility,
    ContactConfidence,
    VictoryConditionType,
    Weather,
    TimeOfDay,
    TurnState,
    Contact,
    ControlZone,
    PerceptionState,
    Casualties,
    CombatEvent,
    MovementEvent,
    DetectionEvent,
    TurnResult,
    GameState,
    VictoryCondition,
    FactionConfig,
    BoundingBox,
    ScenarioConfig,
)


class Base(DeclarativeBase):
    """Base class for all ORM models"""

    pass


# =============================================================================
# GAME SESSION MODEL
# =============================================================================


class DBGame(Base):
    """Game session - top level entity for a game instance"""

    __tablename__ = "games"
    __table_args__ = {"schema": "karkas"}

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # Scenario info
    scenario_name: Mapped[str] = mapped_column(String(256), nullable=False)
    scenario_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scenario_config: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Full ScenarioConfig

    # Game region (PostGIS bounding box)
    region: Mapped[Any] = mapped_column(
        Geometry("POLYGON", srid=4326), nullable=False
    )

    # Current state
    turn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    phase: Mapped[str] = mapped_column(String(20), nullable=False, default="planning")
    turn_state: Mapped[dict] = mapped_column(JSONB, nullable=False)  # TurnState as JSON

    # Faction readiness
    red_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blue_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Game completion
    game_over: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    winner: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    victory_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    units: Mapped[list["DBUnit"]] = relationship("DBUnit", back_populates="game", cascade="all, delete-orphan")
    orders: Mapped[list["DBOrder"]] = relationship("DBOrder", back_populates="game", cascade="all, delete-orphan")
    contacts: Mapped[list["DBContact"]] = relationship("DBContact", back_populates="game", cascade="all, delete-orphan")
    control_zones: Mapped[list["DBControlZone"]] = relationship("DBControlZone", back_populates="game", cascade="all, delete-orphan")
    turn_results: Mapped[list["DBTurnResult"]] = relationship("DBTurnResult", back_populates="game", cascade="all, delete-orphan")

    def set_region(self, bbox: BoundingBox) -> None:
        """Set region from BoundingBox"""
        polygon = Polygon([
            (bbox.southwest.longitude, bbox.southwest.latitude),
            (bbox.northeast.longitude, bbox.southwest.latitude),
            (bbox.northeast.longitude, bbox.northeast.latitude),
            (bbox.southwest.longitude, bbox.northeast.latitude),
            (bbox.southwest.longitude, bbox.southwest.latitude),
        ])
        self.region = from_shape(polygon, srid=4326)

    def get_region(self) -> BoundingBox:
        """Get region as BoundingBox"""
        polygon = to_shape(self.region)
        bounds = polygon.bounds  # (minx, miny, maxx, maxy)
        return BoundingBox(
            southwest=Coordinates(latitude=bounds[1], longitude=bounds[0]),
            northeast=Coordinates(latitude=bounds[3], longitude=bounds[2]),
        )

    def to_game_state(self) -> GameState:
        """Convert to Pydantic GameState"""
        turn_state_dict = self.turn_state
        return GameState(
            turn=self.turn,
            phase=TurnPhase(self.phase),
            turn_state=TurnState(**turn_state_dict),
            red_ready=self.red_ready,
            blue_ready=self.blue_ready,
            game_over=self.game_over,
            winner=Faction(self.winner) if self.winner else None,
        )


# =============================================================================
# UNIT MODEL
# =============================================================================


class DBUnit(Base):
    """Unit entity with full state"""

    __tablename__ = "units"
    __table_args__ = (
        Index("ix_units_game_faction", "game_id", "faction"),
        Index("ix_units_game_type", "game_id", "unit_type"),
        Index("ix_units_position", "position", postgresql_using="gist"),
        {"schema": "karkas"},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Foreign key to game
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("karkas.games.id"), nullable=False)
    game: Mapped["DBGame"] = relationship("DBGame", back_populates="units")

    # Unique constraint on unit_id within a game
    __table_args__ = (
        UniqueConstraint("game_id", "unit_id", name="uq_unit_game"),
        Index("ix_units_game_faction", "game_id", "faction"),
        Index("ix_units_game_type", "game_id", "unit_type"),
        {"schema": "karkas"},
    )

    # Core identity
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    faction: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(20), nullable=False)
    echelon: Mapped[str] = mapped_column(String(20), nullable=False)
    mobility_class: Mapped[str] = mapped_column(String(20), nullable=False)

    # Position (PostGIS Point)
    position: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    heading: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    posture: Mapped[str] = mapped_column(String(20), nullable=False, default="defend")

    # Hierarchy
    parent_unit_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    subordinate_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Combat stats (stored as JSON for simplicity)
    combat_stats: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Sensors (stored as JSON array)
    sensors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Logistics state
    fuel_level: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    ammo_level: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    supply_level: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    maintenance_state: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Morale state
    morale: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    fatigue: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cohesion: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Strength
    personnel_current: Mapped[int] = mapped_column(Integer, nullable=False)
    personnel_max: Mapped[int] = mapped_column(Integer, nullable=False)
    equipment_current: Mapped[int] = mapped_column(Integer, nullable=False)
    equipment_max: Mapped[int] = mapped_column(Integer, nullable=False)

    # Current order
    current_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    def set_position(self, coords: Coordinates) -> None:
        """Set position from Coordinates"""
        self.position = from_shape(Point(coords.longitude, coords.latitude), srid=4326)

    def get_position(self) -> Coordinates:
        """Get position as Coordinates"""
        point = to_shape(self.position)
        return Coordinates(latitude=point.y, longitude=point.x)

    @classmethod
    def from_pydantic(cls, game_id: int, unit: Unit) -> "DBUnit":
        """Create from Pydantic Unit model"""
        db_unit = cls(
            game_id=game_id,
            unit_id=unit.id,
            name=unit.name,
            faction=unit.faction.value,
            unit_type=unit.type.value,
            echelon=unit.echelon.value,
            mobility_class=unit.mobility_class.value,
            heading=unit.heading,
            posture=unit.posture.value,
            parent_unit_id=unit.parent_id,
            subordinate_ids=unit.subordinate_ids,
            combat_stats=unit.combat_stats.model_dump(),
            sensors=[s.model_dump() for s in unit.sensors],
            fuel_level=unit.logistics.fuel_level,
            ammo_level=unit.logistics.ammo_level,
            supply_level=unit.logistics.supply_level,
            maintenance_state=unit.logistics.maintenance_state,
            morale=unit.morale.morale,
            fatigue=unit.morale.fatigue,
            cohesion=unit.morale.cohesion,
            personnel_current=unit.strength.personnel_current,
            personnel_max=unit.strength.personnel_max,
            equipment_current=unit.strength.equipment_current,
            equipment_max=unit.strength.equipment_max,
            current_order_id=unit.current_order_id,
        )
        db_unit.set_position(unit.position)
        return db_unit

    def to_pydantic(self) -> Unit:
        """Convert to Pydantic Unit model"""
        return Unit(
            id=self.unit_id,
            name=self.name,
            faction=Faction(self.faction),
            type=UnitType(self.unit_type),
            echelon=Echelon(self.echelon),
            mobility_class=MobilityClass(self.mobility_class),
            position=self.get_position(),
            heading=self.heading,
            posture=Posture(self.posture),
            parent_id=self.parent_unit_id,
            subordinate_ids=self.subordinate_ids,
            combat_stats=CombatStats(**self.combat_stats),
            sensors=[Sensor(**s) for s in self.sensors],
            logistics=LogisticsState(
                fuel_level=self.fuel_level,
                ammo_level=self.ammo_level,
                supply_level=self.supply_level,
                maintenance_state=self.maintenance_state,
            ),
            morale=MoraleState(
                morale=self.morale,
                fatigue=self.fatigue,
                cohesion=self.cohesion,
            ),
            strength=UnitStrength(
                personnel_current=self.personnel_current,
                personnel_max=self.personnel_max,
                equipment_current=self.equipment_current,
                equipment_max=self.equipment_max,
            ),
            current_order_id=self.current_order_id,
        )


# =============================================================================
# ORDER MODEL
# =============================================================================


class DBOrder(Base):
    """Military order"""

    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_game_active", "game_id", "active"),
        Index("ix_orders_game_issuer", "game_id", "issuer"),
        {"schema": "karkas"},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Foreign key to game
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("karkas.games.id"), nullable=False)
    game: Mapped["DBGame"] = relationship("DBGame", back_populates="orders")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("game_id", "order_id", name="uq_order_game"),
        Index("ix_orders_game_active", "game_id", "active"),
        Index("ix_orders_game_issuer", "game_id", "issuer"),
        {"schema": "karkas"},
    )

    # Order details
    issuer: Mapped[str] = mapped_column(String(64), nullable=False)
    target_units: Mapped[list] = mapped_column(JSONB, nullable=False)  # List of unit IDs
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Objective (stored as JSON)
    objective: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Constraints (stored as JSON)
    constraints: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Metadata
    natural_language: Mapped[str] = mapped_column(Text, nullable=False, default="")
    issued_turn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    @classmethod
    def from_pydantic(cls, game_id: int, order: Order) -> "DBOrder":
        """Create from Pydantic Order model"""
        return cls(
            game_id=game_id,
            order_id=order.order_id,
            issuer=order.issuer,
            target_units=order.target_units,
            order_type=order.order_type.value,
            objective=order.objective.model_dump(),
            constraints=order.constraints.model_dump(),
            natural_language=order.natural_language,
            issued_turn=order.issued_turn,
            active=order.active,
        )

    def to_pydantic(self) -> Order:
        """Convert to Pydantic Order model"""
        return Order(
            order_id=self.order_id,
            issuer=self.issuer,
            target_units=self.target_units,
            order_type=OrderType(self.order_type),
            objective=Objective(**self.objective),
            constraints=OrderConstraints(**self.constraints),
            natural_language=self.natural_language,
            issued_turn=self.issued_turn,
            active=self.active,
        )


# =============================================================================
# CONTACT MODEL
# =============================================================================


class DBContact(Base):
    """Enemy contact report"""

    __tablename__ = "contacts"
    __table_args__ = (
        Index("ix_contacts_game_faction", "game_id", "observing_faction"),
        Index("ix_contacts_position", "position", postgresql_using="gist"),
        {"schema": "karkas"},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contact_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Foreign key to game
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("karkas.games.id"), nullable=False)
    game: Mapped["DBGame"] = relationship("DBGame", back_populates="contacts")

    # Which faction reported this contact
    observing_faction: Mapped[str] = mapped_column(String(20), nullable=False)

    # Position (PostGIS Point)
    position: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    last_known_position: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    last_observed: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Assessment
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    estimated_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    estimated_echelon: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    estimated_strength: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Target faction
    faction: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)

    def set_position(self, coords: Coordinates) -> None:
        """Set position from Coordinates"""
        self.position = from_shape(Point(coords.longitude, coords.latitude), srid=4326)

    def get_position(self) -> Coordinates:
        """Get position as Coordinates"""
        point = to_shape(self.position)
        return Coordinates(latitude=point.y, longitude=point.x)

    def set_last_known_position(self, coords: Coordinates) -> None:
        """Set last known position from Coordinates"""
        self.last_known_position = from_shape(Point(coords.longitude, coords.latitude), srid=4326)

    def get_last_known_position(self) -> Coordinates:
        """Get last known position as Coordinates"""
        point = to_shape(self.last_known_position)
        return Coordinates(latitude=point.y, longitude=point.x)

    @classmethod
    def from_pydantic(cls, game_id: int, observing_faction: Faction, contact: Contact) -> "DBContact":
        """Create from Pydantic Contact model"""
        db_contact = cls(
            game_id=game_id,
            contact_id=contact.contact_id,
            observing_faction=observing_faction.value,
            last_observed=contact.last_observed,
            confidence=contact.confidence.value,
            estimated_type=contact.estimated_type.value if contact.estimated_type else None,
            estimated_echelon=contact.estimated_echelon.value if contact.estimated_echelon else None,
            estimated_strength=contact.estimated_strength,
            faction=contact.faction.value,
            source=contact.source,
        )
        db_contact.set_position(contact.position)
        db_contact.set_last_known_position(contact.last_known_position)
        return db_contact

    def to_pydantic(self) -> Contact:
        """Convert to Pydantic Contact model"""
        return Contact(
            contact_id=self.contact_id,
            position=self.get_position(),
            last_known_position=self.get_last_known_position(),
            last_observed=self.last_observed,
            confidence=ContactConfidence(self.confidence),
            estimated_type=UnitType(self.estimated_type) if self.estimated_type else None,
            estimated_echelon=Echelon(self.estimated_echelon) if self.estimated_echelon else None,
            estimated_strength=self.estimated_strength,
            faction=Faction(self.faction),
            source=self.source,
        )


# =============================================================================
# CONTROL ZONE MODEL
# =============================================================================


class DBControlZone(Base):
    """Zone of control"""

    __tablename__ = "control_zones"
    __table_args__ = (
        Index("ix_control_zones_game", "game_id"),
        Index("ix_control_zones_polygon", "polygon", postgresql_using="gist"),
        {"schema": "karkas"},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Foreign key to game
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("karkas.games.id"), nullable=False)
    game: Mapped["DBGame"] = relationship("DBGame", back_populates="control_zones")

    # Zone geometry (PostGIS Polygon)
    polygon: Mapped[Any] = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)

    # Control status
    controller: Mapped[str] = mapped_column(String(20), nullable=False)
    control_strength: Mapped[float] = mapped_column(Float, nullable=False)

    def set_polygon(self, coords: list[Coordinates]) -> None:
        """Set polygon from list of Coordinates"""
        points = [(c.longitude, c.latitude) for c in coords]
        # Ensure closed polygon
        if points[0] != points[-1]:
            points.append(points[0])
        self.polygon = from_shape(Polygon(points), srid=4326)

    def get_polygon(self) -> list[Coordinates]:
        """Get polygon as list of Coordinates"""
        polygon = to_shape(self.polygon)
        return [Coordinates(latitude=y, longitude=x) for x, y in polygon.exterior.coords]

    @classmethod
    def from_pydantic(cls, game_id: int, zone: ControlZone) -> "DBControlZone":
        """Create from Pydantic ControlZone model"""
        db_zone = cls(
            game_id=game_id,
            zone_id=zone.zone_id,
            controller=zone.controller.value,
            control_strength=zone.control_strength,
        )
        db_zone.set_polygon(zone.polygon)
        return db_zone

    def to_pydantic(self) -> ControlZone:
        """Convert to Pydantic ControlZone model"""
        return ControlZone(
            zone_id=self.zone_id,
            polygon=self.get_polygon(),
            controller=Faction(self.controller),
            control_strength=self.control_strength,
        )


# =============================================================================
# TURN RESULT MODEL (Turn History)
# =============================================================================


class DBTurnResult(Base):
    """Turn result with aggregated events"""

    __tablename__ = "turn_results"
    __table_args__ = (
        Index("ix_turn_results_game_turn", "game_id", "turn"),
        UniqueConstraint("game_id", "turn", name="uq_turn_result_game_turn"),
        {"schema": "karkas"},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to game
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("karkas.games.id"), nullable=False)
    game: Mapped["DBGame"] = relationship("DBGame", back_populates="turn_results")

    # Turn number
    turn: Mapped[int] = mapped_column(Integer, nullable=False)

    # Summaries
    red_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    blue_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Game end status
    game_over: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    winner: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    victory_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Snapshot of game state at end of turn (for replay)
    state_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships to events
    combat_events: Mapped[list["DBCombatEvent"]] = relationship(
        "DBCombatEvent", back_populates="turn_result", cascade="all, delete-orphan"
    )
    movement_events: Mapped[list["DBMovementEvent"]] = relationship(
        "DBMovementEvent", back_populates="turn_result", cascade="all, delete-orphan"
    )
    detection_events: Mapped[list["DBDetectionEvent"]] = relationship(
        "DBDetectionEvent", back_populates="turn_result", cascade="all, delete-orphan"
    )
    supply_events: Mapped[list["DBSupplyEvent"]] = relationship(
        "DBSupplyEvent", back_populates="turn_result", cascade="all, delete-orphan"
    )

    def to_pydantic(self) -> TurnResult:
        """Convert to Pydantic TurnResult model"""
        return TurnResult(
            turn=self.turn,
            movements=[e.to_pydantic() for e in self.movement_events],
            combats=[e.to_pydantic() for e in self.combat_events],
            detections=[e.to_pydantic() for e in self.detection_events],
            red_summary=self.red_summary,
            blue_summary=self.blue_summary,
            game_over=self.game_over,
            winner=Faction(self.winner) if self.winner else None,
            victory_reason=self.victory_reason,
        )


# =============================================================================
# EVENT MODELS
# =============================================================================


class DBCombatEvent(Base):
    """Combat engagement event"""

    __tablename__ = "combat_events"
    __table_args__ = (
        Index("ix_combat_events_turn_result", "turn_result_id"),
        {"schema": "karkas"},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to turn result
    turn_result_id: Mapped[int] = mapped_column(Integer, ForeignKey("karkas.turn_results.id"), nullable=False)
    turn_result: Mapped["DBTurnResult"] = relationship("DBTurnResult", back_populates="combat_events")

    # Event data
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    attacker: Mapped[str] = mapped_column(String(64), nullable=False)
    defender: Mapped[str] = mapped_column(String(64), nullable=False)
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=False)

    # Casualties (stored as JSON)
    attacker_casualties: Mapped[dict] = mapped_column(JSONB, nullable=False)
    defender_casualties: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Outcomes
    attacker_retreated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    defender_retreated: Mapped[bool] = mapped_column(Boolean, nullable=False)

    def to_pydantic(self) -> CombatEvent:
        """Convert to Pydantic CombatEvent model"""
        point = to_shape(self.location)
        return CombatEvent(
            turn=self.turn,
            attacker=self.attacker,
            defender=self.defender,
            location=Coordinates(latitude=point.y, longitude=point.x),
            attacker_casualties=Casualties(**self.attacker_casualties),
            defender_casualties=Casualties(**self.defender_casualties),
            attacker_retreated=self.attacker_retreated,
            defender_retreated=self.defender_retreated,
        )


class DBMovementEvent(Base):
    """Movement event"""

    __tablename__ = "movement_events"
    __table_args__ = (
        Index("ix_movement_events_turn_result", "turn_result_id"),
        {"schema": "karkas"},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to turn result
    turn_result_id: Mapped[int] = mapped_column(Integer, ForeignKey("karkas.turn_results.id"), nullable=False)
    turn_result: Mapped["DBTurnResult"] = relationship("DBTurnResult", back_populates="movement_events")

    # Event data
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    from_position: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    to_position: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False)

    def to_pydantic(self) -> MovementEvent:
        """Convert to Pydantic MovementEvent model"""
        from_point = to_shape(self.from_position)
        to_point = to_shape(self.to_position)
        return MovementEvent(
            turn=self.turn,
            unit=self.unit,
            from_position=Coordinates(latitude=from_point.y, longitude=from_point.x),
            to_position=Coordinates(latitude=to_point.y, longitude=to_point.x),
            distance_km=self.distance_km,
            completed=self.completed,
        )


class DBDetectionEvent(Base):
    """Detection event"""

    __tablename__ = "detection_events"
    __table_args__ = (
        Index("ix_detection_events_turn_result", "turn_result_id"),
        {"schema": "karkas"},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to turn result
    turn_result_id: Mapped[int] = mapped_column(Integer, ForeignKey("karkas.turn_results.id"), nullable=False)
    turn_result: Mapped["DBTurnResult"] = relationship("DBTurnResult", back_populates="detection_events")

    # Event data
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    observer: Mapped[str] = mapped_column(String(64), nullable=False)
    observed: Mapped[str] = mapped_column(String(64), nullable=False)
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)

    def to_pydantic(self) -> DetectionEvent:
        """Convert to Pydantic DetectionEvent model"""
        point = to_shape(self.location)
        return DetectionEvent(
            turn=self.turn,
            observer=self.observer,
            observed=self.observed,
            location=Coordinates(latitude=point.y, longitude=point.x),
            confidence=ContactConfidence(self.confidence),
        )


class DBSupplyEvent(Base):
    """Supply/logistics event"""

    __tablename__ = "supply_events"
    __table_args__ = (
        Index("ix_supply_events_turn_result", "turn_result_id"),
        {"schema": "karkas"},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to turn result
    turn_result_id: Mapped[int] = mapped_column(Integer, ForeignKey("karkas.turn_results.id"), nullable=False)
    turn_result: Mapped["DBTurnResult"] = relationship("DBTurnResult", back_populates="supply_events")

    # Event data
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    depot_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Supply delivered
    fuel_delivered: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ammo_delivered: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    supply_delivered: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Interdiction status
    supply_line_interdicted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interdicting_units: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
