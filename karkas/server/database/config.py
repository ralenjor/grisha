"""
Database Configuration (8.1.1 PostgreSQL/PostGIS setup)

Provides database connection configuration with support for environment variables,
PostGIS spatial extensions, and connection pooling settings.

This module now delegates to the centralized settings system (server.config)
while maintaining backward compatibility with existing code.
"""

from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus

# Import from centralized settings
from server.config import get_settings, DatabaseSettings


@dataclass
class DatabaseConfig:
    """
    Database connection configuration.

    This class is maintained for backward compatibility. New code should use
    `server.config.get_settings().database` directly.
    """

    # Connection parameters
    host: str = "localhost"
    port: int = 5432
    database: str = "karkas"
    username: str = "karkas"
    password: str = "karkas"

    # Connection pool settings
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 1800  # Recycle connections after 30 minutes

    # Engine options
    echo: bool = False  # Log SQL queries
    echo_pool: bool = False  # Log pool events

    # Schema name for tables
    schema: str = "karkas"

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Load configuration from centralized settings."""
        settings = get_settings().database
        return cls(
            host=settings.host,
            port=settings.port,
            database=settings.name,
            username=settings.user,
            password=settings.password,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
            pool_timeout=settings.pool_timeout,
            pool_recycle=settings.pool_recycle,
            echo=settings.echo,
            echo_pool=settings.echo_pool,
            schema=settings.schema_name,
        )

    @classmethod
    def from_settings(cls, settings: DatabaseSettings) -> "DatabaseConfig":
        """Create config from DatabaseSettings instance."""
        return cls(
            host=settings.host,
            port=settings.port,
            database=settings.name,
            username=settings.user,
            password=settings.password,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
            pool_timeout=settings.pool_timeout,
            pool_recycle=settings.pool_recycle,
            echo=settings.echo,
            echo_pool=settings.echo_pool,
            schema=settings.schema_name,
        )

    def get_url(self, async_driver: bool = False) -> str:
        """Build database connection URL

        Args:
            async_driver: If True, use asyncpg for async connections
        """
        driver = "postgresql+asyncpg" if async_driver else "postgresql+psycopg2"
        password_encoded = quote_plus(self.password)
        return f"{driver}://{self.username}:{password_encoded}@{self.host}:{self.port}/{self.database}"


# Global configuration instance
_config: Optional[DatabaseConfig] = None


def get_database_config() -> DatabaseConfig:
    """Get the global database configuration."""
    global _config
    if _config is None:
        _config = DatabaseConfig.from_env()
    return _config


def set_database_config(config: DatabaseConfig) -> None:
    """Set the global database configuration."""
    global _config
    _config = config


def get_database_url(async_driver: bool = False) -> str:
    """Get the database connection URL."""
    return get_database_config().get_url(async_driver)


def is_database_enabled() -> bool:
    """Check if database persistence is enabled."""
    return get_settings().database.enabled


# SQL to create the schema and enable PostGIS
INIT_SQL = """
-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS karkas;

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Enable PostGIS topology (optional, for advanced spatial operations)
-- CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Set search path to include our schema
SET search_path TO karkas, public;
"""

# SQL to create custom enum types
ENUM_SQL = """
-- Drop existing types if they exist (for development)
DO $$ BEGIN
    DROP TYPE IF EXISTS karkas.faction CASCADE;
    DROP TYPE IF EXISTS karkas.unit_type CASCADE;
    DROP TYPE IF EXISTS karkas.echelon CASCADE;
    DROP TYPE IF EXISTS karkas.posture CASCADE;
    DROP TYPE IF EXISTS karkas.mobility_class CASCADE;
    DROP TYPE IF EXISTS karkas.sensor_type CASCADE;
    DROP TYPE IF EXISTS karkas.order_type CASCADE;
    DROP TYPE IF EXISTS karkas.route_preference CASCADE;
    DROP TYPE IF EXISTS karkas.roe CASCADE;
    DROP TYPE IF EXISTS karkas.objective_type CASCADE;
    DROP TYPE IF EXISTS karkas.turn_phase CASCADE;
    DROP TYPE IF EXISTS karkas.precipitation CASCADE;
    DROP TYPE IF EXISTS karkas.visibility CASCADE;
    DROP TYPE IF EXISTS karkas.contact_confidence CASCADE;
    DROP TYPE IF EXISTS karkas.victory_condition_type CASCADE;
EXCEPTION
    WHEN undefined_object THEN NULL;
END $$;

-- Faction enum
CREATE TYPE karkas.faction AS ENUM ('red', 'blue', 'neutral');

-- Unit type enum
CREATE TYPE karkas.unit_type AS ENUM (
    'infantry', 'armor', 'mechanized', 'artillery', 'air_defense',
    'rotary', 'fixed_wing', 'support', 'headquarters', 'recon',
    'engineer', 'logistics'
);

-- Echelon enum
CREATE TYPE karkas.echelon AS ENUM (
    'squad', 'platoon', 'company', 'battalion', 'regiment',
    'brigade', 'division', 'corps', 'army'
);

-- Posture enum
CREATE TYPE karkas.posture AS ENUM (
    'attack', 'defend', 'move', 'recon', 'support',
    'reserve', 'retreat', 'disengaged'
);

-- Mobility class enum
CREATE TYPE karkas.mobility_class AS ENUM (
    'foot', 'wheeled', 'tracked', 'rotary', 'fixed_wing'
);

-- Sensor type enum
CREATE TYPE karkas.sensor_type AS ENUM (
    'visual', 'thermal', 'radar', 'sigint', 'acoustic',
    'satellite', 'human_intel'
);

-- Order type enum
CREATE TYPE karkas.order_type AS ENUM (
    'move', 'attack', 'defend', 'support', 'recon',
    'withdraw', 'resupply', 'hold'
);

-- Route preference enum
CREATE TYPE karkas.route_preference AS ENUM (
    'fastest', 'covered', 'specified', 'avoid_enemy'
);

-- Rules of engagement enum
CREATE TYPE karkas.roe AS ENUM (
    'weapons_free', 'weapons_hold', 'weapons_tight'
);

-- Objective type enum
CREATE TYPE karkas.objective_type AS ENUM (
    'position', 'unit', 'zone'
);

-- Turn phase enum
CREATE TYPE karkas.turn_phase AS ENUM (
    'planning', 'execution', 'reporting'
);

-- Precipitation enum
CREATE TYPE karkas.precipitation AS ENUM (
    'none', 'light', 'moderate', 'heavy'
);

-- Visibility enum
CREATE TYPE karkas.visibility AS ENUM (
    'clear', 'haze', 'fog', 'smoke'
);

-- Contact confidence enum
CREATE TYPE karkas.contact_confidence AS ENUM (
    'confirmed', 'probable', 'suspected', 'unknown'
);

-- Victory condition type enum
CREATE TYPE karkas.victory_condition_type AS ENUM (
    'territorial', 'attrition', 'time', 'objective'
);
"""
