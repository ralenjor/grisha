"""Pydantic models for scenario validation and editing."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class Coordinates(BaseModel):
    """Geographic coordinates as [latitude, longitude] or object."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    @classmethod
    def from_list(cls, coords: list[float]) -> "Coordinates":
        """Create from [lat, lon] list."""
        if len(coords) != 2:
            raise ValueError("Coordinates must be [latitude, longitude]")
        return cls(latitude=coords[0], longitude=coords[1])


class BoundingBox(BaseModel):
    """Geographic bounding box."""
    southwest: list[float] = Field(..., min_length=2, max_length=2)
    northeast: list[float] = Field(..., min_length=2, max_length=2)

    @field_validator('southwest', 'northeast')
    @classmethod
    def validate_coords(cls, v: list[float]) -> list[float]:
        if len(v) != 2:
            raise ValueError("Coordinates must be [latitude, longitude]")
        lat, lon = v
        if not -90 <= lat <= 90:
            raise ValueError(f"Latitude {lat} must be between -90 and 90")
        if not -180 <= lon <= 180:
            raise ValueError(f"Longitude {lon} must be between -180 and 180")
        return v

    @model_validator(mode='after')
    def validate_bounds(self) -> "BoundingBox":
        if self.southwest[0] >= self.northeast[0]:
            raise ValueError("Southwest latitude must be less than northeast latitude")
        if self.southwest[1] >= self.northeast[1]:
            raise ValueError("Southwest longitude must be less than northeast longitude")
        return self


class Region(BaseModel):
    """Scenario region definition."""
    bounds: BoundingBox
    terrain_source: str = Field(..., min_length=1)


class Precipitation(str, Enum):
    """Weather precipitation types."""
    NONE = "none"
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"


class Visibility(str, Enum):
    """Visibility conditions."""
    CLEAR = "clear"
    HAZE = "haze"
    FOG = "fog"
    SMOKE = "smoke"


class Weather(BaseModel):
    """Weather conditions."""
    precipitation: Precipitation = Precipitation.NONE
    visibility: Visibility = Visibility.CLEAR
    temperature_c: float = Field(20.0, ge=-50, le=60)
    wind_speed_kph: float = Field(10.0, ge=0, le=200)
    wind_direction: float = Field(0.0, ge=0, lt=360)


class GrishaPersona(str, Enum):
    """Grisha AI persona types."""
    COMMANDER = "commander"
    ADVISOR = "advisor"


class Faction(BaseModel):
    """Faction configuration."""
    name: str = Field(..., min_length=1)
    doctrine: str = ""
    orbat_file: str = Field(..., min_length=1)
    ai_controlled: bool = False
    grisha_persona: Optional[GrishaPersona] = None

    @model_validator(mode='after')
    def validate_ai_persona(self) -> "Faction":
        if self.ai_controlled and self.grisha_persona is None:
            raise ValueError("AI-controlled factions must specify a grisha_persona")
        return self


class InitialConditions(BaseModel):
    """Scenario initial conditions."""
    turn_length_hours: int = Field(4, ge=1, le=24)
    start_date: str = Field(...)
    weather: Weather = Field(default_factory=Weather)

    @field_validator('start_date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v)
        except ValueError as e:
            raise ValueError(f"Invalid ISO date format: {v}") from e
        return v


class ObjectiveType(str, Enum):
    """Types of objectives."""
    CITY = "city"
    CROSSROADS = "crossroads"
    BRIDGE = "bridge"
    AIRFIELD = "airfield"
    PORT = "port"
    SUPPLY_DEPOT = "supply_depot"
    HEADQUARTERS = "headquarters"
    TERRAIN = "terrain"


class FactionId(str, Enum):
    """Faction identifiers."""
    RED = "red"
    BLUE = "blue"
    NEUTRAL = "neutral"


class Objective(BaseModel):
    """Scenario objective."""
    name: str = Field(..., min_length=1)
    type: ObjectiveType
    coordinates: list[float] = Field(..., min_length=2, max_length=2)
    points: int = Field(..., ge=0)
    controller: FactionId

    @field_validator('coordinates')
    @classmethod
    def validate_coords(cls, v: list[float]) -> list[float]:
        if len(v) != 2:
            raise ValueError("Coordinates must be [latitude, longitude]")
        lat, lon = v
        if not -90 <= lat <= 90:
            raise ValueError(f"Latitude {lat} must be between -90 and 90")
        if not -180 <= lon <= 180:
            raise ValueError(f"Longitude {lon} must be between -180 and 180")
        return v


class VictoryType(str, Enum):
    """Types of victory conditions."""
    TERRITORIAL = "territorial"
    ATTRITION = "attrition"
    TIME = "time"
    OBJECTIVE = "objective"


class Victor(str, Enum):
    """Victory outcomes."""
    RED = "red"
    BLUE = "blue"
    DRAW = "draw"


class VictoryCondition(BaseModel):
    """Victory condition definition."""
    type: VictoryType
    description: str = Field(..., min_length=1)
    victor: Victor
    zones: Optional[list[str]] = None
    controller: Optional[FactionId] = None
    turns_held: Optional[int] = Field(None, ge=1)
    threshold: Optional[float] = Field(None, ge=0, le=1)
    faction: Optional[FactionId] = None
    max_turns: Optional[int] = Field(None, ge=1)

    @model_validator(mode='after')
    def validate_condition_type(self) -> "VictoryCondition":
        if self.type == VictoryType.TERRITORIAL:
            if not self.zones:
                raise ValueError("Territorial victory conditions require 'zones'")
            if self.controller is None:
                raise ValueError("Territorial victory conditions require 'controller'")
        elif self.type == VictoryType.ATTRITION:
            if self.threshold is None:
                raise ValueError("Attrition victory conditions require 'threshold'")
            if self.faction is None:
                raise ValueError("Attrition victory conditions require 'faction'")
        elif self.type == VictoryType.TIME:
            if self.max_turns is None:
                raise ValueError("Time victory conditions require 'max_turns'")
        return self


class TriggerType(str, Enum):
    """Trigger types for special rules."""
    TURN = "turn"
    ZONE_CAPTURED = "zone_captured"
    UNIT_DESTROYED = "unit_destroyed"
    THRESHOLD = "threshold"


class Trigger(BaseModel):
    """Trigger for special rules."""
    type: TriggerType
    turn: Optional[int] = None
    zone: Optional[str] = None
    unit: Optional[str] = None
    threshold: Optional[float] = None

    @model_validator(mode='after')
    def validate_trigger(self) -> "Trigger":
        if self.type == TriggerType.TURN and self.turn is None:
            raise ValueError("Turn triggers require 'turn' field")
        if self.type == TriggerType.ZONE_CAPTURED and self.zone is None:
            raise ValueError("Zone triggers require 'zone' field")
        if self.type == TriggerType.UNIT_DESTROYED and self.unit is None:
            raise ValueError("Unit triggers require 'unit' field")
        if self.type == TriggerType.THRESHOLD and self.threshold is None:
            raise ValueError("Threshold triggers require 'threshold' field")
        return self


class Effect(BaseModel):
    """Effect of special rule activation."""
    spawn_units: Optional[str] = None
    modify_weather: Optional[Weather] = None
    victory: Optional[Victor] = None
    message: Optional[str] = None


class SpecialRule(BaseModel):
    """Special rule definition."""
    name: str = Field(..., min_length=1)
    description: str = ""
    enabled: bool = True
    trigger: Optional[Trigger] = None
    effect: Optional[Effect] = None


class Briefing(BaseModel):
    """Scenario briefings for each faction."""
    red: str = ""
    blue: str = ""


class ScenarioMetadata(BaseModel):
    """Scenario metadata."""
    name: str = Field(..., min_length=1)
    description: str = ""


class Factions(BaseModel):
    """Container for both factions."""
    red: Faction
    blue: Faction


class Scenario(BaseModel):
    """Complete scenario definition."""
    scenario: ScenarioMetadata
    region: Region
    factions: Factions
    initial_conditions: InitialConditions
    objectives: list[Objective] = Field(default_factory=list)
    victory_conditions: list[VictoryCondition] = Field(default_factory=list)
    special_rules: list[SpecialRule] = Field(default_factory=list)
    briefing: Briefing = Field(default_factory=Briefing)

    @model_validator(mode='after')
    def validate_objective_references(self) -> "Scenario":
        """Ensure victory conditions reference valid objectives."""
        objective_names = {obj.name for obj in self.objectives}
        for vc in self.victory_conditions:
            if vc.zones:
                for zone in vc.zones:
                    if zone not in objective_names:
                        raise ValueError(
                            f"Victory condition references unknown zone '{zone}'. "
                            f"Available: {objective_names}"
                        )
        return self


# ============== Unit Template Models ==============

class UnitType(str, Enum):
    """Type of military unit."""
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
    """Unit echelon/size."""
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
    """Unit posture/stance."""
    ATTACK = "attack"
    DEFEND = "defend"
    MOVE = "move"
    RECON = "recon"
    SUPPORT = "support"
    RESERVE = "reserve"
    RETREAT = "retreat"
    DISENGAGED = "disengaged"


class MobilityClass(str, Enum):
    """Movement capability."""
    FOOT = "foot"
    WHEELED = "wheeled"
    TRACKED = "tracked"
    ROTARY = "rotary"
    FIXED_WING = "fixed_wing"


class CombatStats(BaseModel):
    """Combat capability values."""
    combat_power: float = Field(30.0, ge=0)
    defense_value: float = Field(30.0, ge=0)
    soft_attack: float = Field(30.0, ge=0)
    hard_attack: float = Field(10.0, ge=0)
    air_attack: float = Field(0.0, ge=0)
    air_defense: float = Field(5.0, ge=0)


class LogisticsState(BaseModel):
    """Logistics/supply state."""
    fuel_level: float = Field(1.0, ge=0, le=1)
    ammo_level: float = Field(1.0, ge=0, le=1)
    supply_level: float = Field(1.0, ge=0, le=1)


class ORBATUnit(BaseModel):
    """Unit definition for ORBAT files."""
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    type: UnitType
    echelon: Echelon
    mobility_class: MobilityClass = MobilityClass.FOOT
    position: list[float] = Field(..., min_length=2, max_length=2)
    heading: float = Field(0.0, ge=0, lt=360)
    posture: Posture = Posture.DEFEND
    parent_id: Optional[str] = None
    subordinate_ids: list[str] = Field(default_factory=list)
    personnel: int = Field(..., ge=1)
    personnel_max: int = Field(..., ge=1)
    equipment: int = Field(0, ge=0)
    equipment_max: int = Field(0, ge=0)
    combat_stats: CombatStats = Field(default_factory=CombatStats)
    logistics: LogisticsState = Field(default_factory=LogisticsState)

    @field_validator('position')
    @classmethod
    def validate_position(cls, v: list[float]) -> list[float]:
        lat, lon = v
        if not -90 <= lat <= 90:
            raise ValueError(f"Latitude {lat} must be between -90 and 90")
        if not -180 <= lon <= 180:
            raise ValueError(f"Longitude {lon} must be between -180 and 180")
        return v


class ORBAT(BaseModel):
    """Order of battle definition."""
    faction: FactionId
    name: str = Field(..., min_length=1)
    units: list[ORBATUnit] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_hierarchy(self) -> "ORBAT":
        """Validate unit hierarchy references."""
        unit_ids = {u.id for u in self.units}
        for unit in self.units:
            if unit.parent_id and unit.parent_id not in unit_ids:
                raise ValueError(
                    f"Unit '{unit.id}' references unknown parent '{unit.parent_id}'"
                )
            for sub_id in unit.subordinate_ids:
                if sub_id not in unit_ids:
                    raise ValueError(
                        f"Unit '{unit.id}' references unknown subordinate '{sub_id}'"
                    )
        return self
