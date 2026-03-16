"""
KARKAS Database Module

Provides PostgreSQL/PostGIS persistence for game state, turn history, and replay functionality.
"""

from .config import DatabaseConfig, get_database_url
from .session import get_session, get_async_session, init_database, DatabaseSession
from .models import (
    Base,
    DBGame,
    DBUnit,
    DBOrder,
    DBContact,
    DBControlZone,
    DBTurnResult,
    DBCombatEvent,
    DBMovementEvent,
    DBDetectionEvent,
    DBSupplyEvent,
)
from .game_store import GameStore
from .turn_history import TurnHistoryStore
from .replay import ReplayController, ReplayState

__all__ = [
    # Configuration
    "DatabaseConfig",
    "get_database_url",
    # Session management
    "get_session",
    "get_async_session",
    "init_database",
    "DatabaseSession",
    # ORM Models
    "Base",
    "DBGame",
    "DBUnit",
    "DBOrder",
    "DBContact",
    "DBControlZone",
    "DBTurnResult",
    "DBCombatEvent",
    "DBMovementEvent",
    "DBDetectionEvent",
    "DBSupplyEvent",
    # Game persistence
    "GameStore",
    # Turn history
    "TurnHistoryStore",
    # Replay
    "ReplayController",
    "ReplayState",
]
