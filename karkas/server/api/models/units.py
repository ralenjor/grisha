"""Unit-related Pydantic models"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    """Geographic coordinates"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class Faction(str, Enum):
    """Military faction"""
    RED = "red"
    BLUE = "blue"
    NEUTRAL = "neutral"


class UnitType(str, Enum):
    """Type of military unit"""
    INFANTRY = "infantry"
    ARMOR = "armor"
    MECHANIZED = "mechanized"
    ARTILLERY = "artillery"
    AIR_DEFENSE = "air_defense"
    ROTARY = "rotary"
    FIXED_WING = "fixed_wing"
    SUPPORT = "support"
    HEADQUARTERS = "headquarters"
    RECON = "recon"
    ENGINEER = "engineer"
    LOGISTICS = "logistics"


class Echelon(str, Enum):
    """Unit echelon/size"""
    SQUAD = "squad"
    PLATOON = "platoon"
    COMPANY = "company"
    BATTALION = "battalion"
    REGIMENT = "regiment"
    BRIGADE = "brigade"
    DIVISION = "division"
    CORPS = "corps"
    ARMY = "army"


class Posture(str, Enum):
    """Unit posture/stance"""
    ATTACK = "attack"
    DEFEND = "defend"
    MOVE = "move"
    RECON = "recon"
    SUPPORT = "support"
    RESERVE = "reserve"
    RETREAT = "retreat"
    DISENGAGED = "disengaged"


class MobilityClass(str, Enum):
    """Movement capability"""
    FOOT = "foot"
    WHEELED = "wheeled"
    TRACKED = "tracked"
    ROTARY = "rotary"
    FIXED_WING = "fixed_wing"


class SensorType(str, Enum):
    """Type of sensor"""
    VISUAL = "visual"
    THERMAL = "thermal"
    RADAR = "radar"
    SIGINT = "sigint"
    ACOUSTIC = "acoustic"
    SATELLITE = "satellite"
    HUMAN_INTEL = "human_intel"


class LogisticsState(BaseModel):
    """Logistics/supply state"""
    fuel_level: float = Field(1.0, ge=0, le=1)
    ammo_level: float = Field(1.0, ge=0, le=1)
    supply_level: float = Field(1.0, ge=0, le=1)
    maintenance_state: float = Field(1.0, ge=0, le=1)


class MoraleState(BaseModel):
    """Morale and fatigue state"""
    morale: float = Field(0.8, ge=0, le=1)
    fatigue: float = Field(0.0, ge=0, le=1)
    cohesion: float = Field(1.0, ge=0, le=1)


class UnitStrength(BaseModel):
    """Personnel and equipment strength"""
    personnel_current: int = Field(..., ge=0)
    personnel_max: int = Field(..., ge=1)
    equipment_current: int = Field(..., ge=0)
    equipment_max: int = Field(..., ge=0)

    @property
    def strength_ratio(self) -> float:
        personnel_ratio = self.personnel_current / self.personnel_max
        equipment_ratio = (
            self.equipment_current / self.equipment_max
            if self.equipment_max > 0
            else 1.0
        )
        return (personnel_ratio + equipment_ratio) / 2.0


class CombatStats(BaseModel):
    """Combat capability values"""
    combat_power: float = Field(30.0, ge=0)
    defense_value: float = Field(30.0, ge=0)
    soft_attack: float = Field(30.0, ge=0)
    hard_attack: float = Field(10.0, ge=0)
    air_attack: float = Field(0.0, ge=0)
    air_defense: float = Field(5.0, ge=0)


class Sensor(BaseModel):
    """Detection sensor"""
    type: SensorType
    range_km: float = Field(..., gt=0)
    detection_probability: float = Field(..., ge=0, le=1)
    identification_probability: float = Field(..., ge=0, le=1)
    arc_degrees: float = Field(360.0, ge=0, le=360)
    heading: float = Field(0.0, ge=0, lt=360)
    active: bool = False


class Unit(BaseModel):
    """Complete unit representation"""
    id: str
    name: str
    faction: Faction
    type: UnitType
    echelon: Echelon
    mobility_class: MobilityClass

    position: Coordinates
    heading: float = Field(0.0, ge=0, lt=360)
    posture: Posture = Posture.DEFEND

    parent_id: Optional[str] = None
    subordinate_ids: list[str] = Field(default_factory=list)

    combat_stats: CombatStats = Field(default_factory=CombatStats)
    sensors: list[Sensor] = Field(default_factory=list)

    logistics: LogisticsState = Field(default_factory=LogisticsState)
    morale: MoraleState = Field(default_factory=MoraleState)
    strength: UnitStrength

    current_order_id: Optional[str] = None

    class Config:
        from_attributes = True


class UnitCreate(BaseModel):
    """Data for creating a new unit"""
    id: Optional[str] = None  # Auto-generated if not provided
    name: str
    faction: Faction
    type: UnitType
    echelon: Echelon
    position: Coordinates
    parent_id: Optional[str] = None


class UnitUpdate(BaseModel):
    """Data for updating a unit"""
    position: Optional[Coordinates] = None
    heading: Optional[float] = None
    posture: Optional[Posture] = None
    parent_id: Optional[str] = None

    # These can be partially updated
    logistics: Optional[LogisticsState] = None
    morale: Optional[MoraleState] = None
