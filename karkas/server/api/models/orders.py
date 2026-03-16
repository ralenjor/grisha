"""Order-related Pydantic models"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from .units import Coordinates


class OrderType(str, Enum):
    """Type of military order"""
    MOVE = "move"
    ATTACK = "attack"
    DEFEND = "defend"
    SUPPORT = "support"
    RECON = "recon"
    WITHDRAW = "withdraw"
    RESUPPLY = "resupply"
    HOLD = "hold"


class RoutePreference(str, Enum):
    """Preferred route for movement"""
    FASTEST = "fastest"
    COVERED = "covered"
    SPECIFIED = "specified"
    AVOID_ENEMY = "avoid_enemy"


class RulesOfEngagement(str, Enum):
    """Rules of engagement"""
    WEAPONS_FREE = "weapons_free"
    WEAPONS_HOLD = "weapons_hold"
    WEAPONS_TIGHT = "weapons_tight"


class ObjectiveType(str, Enum):
    """Type of objective"""
    POSITION = "position"
    UNIT = "unit"
    ZONE = "zone"


class Objective(BaseModel):
    """Order objective"""
    type: ObjectiveType
    coordinates: Optional[Coordinates] = None
    target_unit_id: Optional[str] = None
    zone_name: Optional[str] = None
    zone_polygon: Optional[list[Coordinates]] = None


class OrderConstraints(BaseModel):
    """Constraints on order execution"""
    route: RoutePreference = RoutePreference.FASTEST
    timing_offset_hours: Optional[int] = None  # H+N hours
    roe: RulesOfEngagement = RulesOfEngagement.WEAPONS_FREE
    max_casualties_percent: Optional[float] = Field(None, ge=0, le=100)
    specified_route: Optional[list[Coordinates]] = None


class Order(BaseModel):
    """Complete order representation"""
    order_id: str
    issuer: str
    target_units: list[str]
    order_type: OrderType
    objective: Objective
    constraints: OrderConstraints = Field(default_factory=OrderConstraints)

    natural_language: str = ""  # Original text for human review
    issued_turn: int = 0
    active: bool = True

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    """Data for creating a new order"""
    issuer: str
    target_units: list[str]
    order_type: OrderType
    objective: Objective
    constraints: Optional[OrderConstraints] = None
    natural_language: Optional[str] = None


class OrderValidationResult(BaseModel):
    """Result of order validation"""
    valid: bool
    error: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class OrderBatch(BaseModel):
    """Batch of orders for submission"""
    faction: str
    orders: list[OrderCreate]
