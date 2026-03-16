"""Game state Pydantic models"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from .units import Coordinates, Faction, UnitType, Echelon, Unit


class TurnPhase(str, Enum):
    """Phase of WEGO turn"""
    PLANNING = "planning"
    EXECUTION = "execution"
    REPORTING = "reporting"


class Precipitation(str, Enum):
    """Weather precipitation"""
    NONE = "none"
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"


class Visibility(str, Enum):
    """Weather visibility"""
    CLEAR = "clear"
    HAZE = "haze"
    FOG = "fog"
    SMOKE = "smoke"


class Weather(BaseModel):
    """Weather conditions"""
    precipitation: Precipitation = Precipitation.NONE
    visibility: Visibility = Visibility.CLEAR
    temperature_c: float = 20.0
    wind_speed_kph: float = 10.0
    wind_direction: float = Field(0.0, ge=0, lt=360)


class TimeOfDay(BaseModel):
    """Time of day"""
    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(0, ge=0, le=59)

    @property
    def is_night(self) -> bool:
        return self.hour < 6 or self.hour >= 20

    @property
    def is_twilight(self) -> bool:
        return (5 <= self.hour < 7) or (19 <= self.hour < 21)


class TurnState(BaseModel):
    """State of current turn"""
    turn_number: int = Field(..., ge=0)
    simulation_time: datetime
    turn_length_hours: int = 4
    weather: Weather = Field(default_factory=Weather)
    time_of_day: TimeOfDay


class ContactConfidence(str, Enum):
    """Confidence level for enemy contact"""
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    SUSPECTED = "suspected"
    UNKNOWN = "unknown"


class Contact(BaseModel):
    """Enemy contact report"""
    contact_id: str
    position: Coordinates
    last_known_position: Coordinates
    last_observed: datetime

    confidence: ContactConfidence
    estimated_type: Optional[UnitType] = None
    estimated_echelon: Optional[Echelon] = None
    estimated_strength: Optional[float] = None

    faction: Faction
    source: str  # How it was detected


class ControlZone(BaseModel):
    """Zone of control"""
    zone_id: str
    polygon: list[Coordinates]
    controller: Faction
    control_strength: float = Field(..., ge=0, le=1)


class PerceptionState(BaseModel):
    """Faction's perception of the battlefield"""
    faction: Faction
    own_units: list[Unit] = Field(default_factory=list)
    contacts: list[Contact] = Field(default_factory=list)
    control_zones: list[ControlZone] = Field(default_factory=list)

    def get_situation_summary(self) -> str:
        """Generate text summary for AI consumption"""
        lines = [
            f"SITUATION SUMMARY - {self.faction.value.upper()} FORCE",
            "=" * 50,
            "",
            f"Own Forces: {len(self.own_units)} units",
            f"Enemy Contacts: {len(self.contacts)} reported",
            "",
        ]

        lines.append("OWN FORCES:")
        for unit in self.own_units:
            strength_pct = unit.strength.strength_ratio * 100
            lines.append(
                f"  - {unit.name} ({unit.echelon.value} {unit.type.value}) "
                f"at ({unit.position.latitude:.4f}, {unit.position.longitude:.4f}) "
                f"[{strength_pct:.0f}% strength, {unit.posture.value}]"
            )

        lines.append("")
        lines.append("ENEMY CONTACTS:")
        if not self.contacts:
            lines.append("  No contacts reported")
        else:
            for contact in self.contacts:
                type_str = contact.estimated_type.value if contact.estimated_type else "unknown"
                lines.append(
                    f"  - [{contact.confidence.value}] {type_str} "
                    f"at ({contact.position.latitude:.4f}, {contact.position.longitude:.4f})"
                )

        return "\n".join(lines)


class Casualties(BaseModel):
    """Casualty report"""
    personnel_killed: int = 0
    personnel_wounded: int = 0
    equipment_destroyed: int = 0
    equipment_damaged: int = 0


class CombatEvent(BaseModel):
    """Combat engagement event"""
    turn: int
    attacker: str
    defender: str
    location: Coordinates
    attacker_casualties: Casualties
    defender_casualties: Casualties
    attacker_retreated: bool
    defender_retreated: bool


class MovementEvent(BaseModel):
    """Movement event"""
    turn: int
    unit: str
    from_position: Coordinates
    to_position: Coordinates
    distance_km: float
    completed: bool


class DetectionEvent(BaseModel):
    """Detection event"""
    turn: int
    observer: str
    observed: str
    location: Coordinates
    confidence: ContactConfidence


class TurnResult(BaseModel):
    """Result of turn execution"""
    turn: int
    movements: list[MovementEvent] = Field(default_factory=list)
    combats: list[CombatEvent] = Field(default_factory=list)
    detections: list[DetectionEvent] = Field(default_factory=list)

    red_summary: str = ""
    blue_summary: str = ""

    game_over: bool = False
    winner: Optional[Faction] = None
    victory_reason: Optional[str] = None


class GameState(BaseModel):
    """Complete game state"""
    turn: int
    phase: TurnPhase
    turn_state: TurnState

    red_ready: bool = False
    blue_ready: bool = False

    game_over: bool = False
    winner: Optional[Faction] = None


class VictoryConditionType(str, Enum):
    """Type of victory condition"""
    TERRITORIAL = "territorial"
    ATTRITION = "attrition"
    TIME = "time"
    OBJECTIVE = "objective"


class VictoryCondition(BaseModel):
    """Victory condition definition"""
    type: VictoryConditionType
    zone_names: list[str] = Field(default_factory=list)
    required_controller: Optional[Faction] = None
    attrition_threshold: Optional[float] = None
    max_turns: Optional[int] = None


class FactionConfig(BaseModel):
    """Configuration for a faction"""
    name: str
    faction: Faction
    doctrine: str = ""
    orbat_file: Optional[str] = None
    ai_controlled: bool = False


class BoundingBox(BaseModel):
    """Geographic bounding box"""
    southwest: Coordinates
    northeast: Coordinates


class ScenarioConfig(BaseModel):
    """Scenario configuration"""
    name: str
    description: str = ""
    region: BoundingBox
    terrain_data_path: Optional[str] = None

    red_faction: FactionConfig
    blue_faction: FactionConfig

    turn_length_hours: int = 4
    start_time: datetime

    victory_conditions: list[VictoryCondition] = Field(default_factory=list)


class ScenarioSummary(BaseModel):
    """Summary of a scenario for listing"""
    name: str
    description: str
    region_name: str
    red_faction_name: str
    blue_faction_name: str
