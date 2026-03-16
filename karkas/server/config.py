"""
Centralized Configuration for KARKAS Server (8.2.1 Configuration Management)

Provides a unified configuration system using Pydantic Settings with:
- Environment variable support with KARKAS_ prefix
- .env file loading
- Type validation and coercion
- Sensible defaults for all settings
- Nested configuration for subsystems (database, logging, AI)
- Secrets management via environment variables

Usage:
    from server.config import get_settings

    settings = get_settings()
    print(settings.server.port)
    print(settings.database.url)
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import quote_plus

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    """Server configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="KARKAS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server binding
    host: str = Field(default="0.0.0.0", description="Server bind address")
    port: int = Field(default=8080, ge=1, le=65535, description="Server port")

    # Development/debug mode
    debug: bool = Field(default=False, description="Enable debug mode")

    # CORS settings
    cors_origins: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins"
    )

    # Request handling
    request_timeout: int = Field(
        default=30,
        ge=1,
        description="Request timeout in seconds"
    )


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="KARKAS_DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Enable/disable database persistence
    enabled: bool = Field(default=False, description="Enable database persistence")

    # Connection parameters
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    name: str = Field(default="karkas", description="Database name")
    user: str = Field(default="karkas", description="Database username")
    password: str = Field(default="karkas", description="Database password")

    # Connection pool settings
    pool_size: int = Field(default=5, ge=1, le=100, description="Connection pool size")
    max_overflow: int = Field(default=10, ge=0, le=100, description="Max overflow connections")
    pool_timeout: int = Field(default=30, ge=1, description="Pool connection timeout")
    pool_recycle: int = Field(default=1800, ge=60, description="Connection recycle time")

    # Engine options
    echo: bool = Field(default=False, description="Log SQL queries")
    echo_pool: bool = Field(default=False, description="Log pool events")

    # Schema name
    schema_name: str = Field(default="karkas", alias="schema", description="Database schema")

    @property
    def url(self) -> str:
        """Build synchronous database connection URL."""
        password_encoded = quote_plus(self.password)
        return f"postgresql+psycopg2://{self.user}:{password_encoded}@{self.host}:{self.port}/{self.name}"

    @property
    def async_url(self) -> str:
        """Build async database connection URL."""
        password_encoded = quote_plus(self.password)
        return f"postgresql+asyncpg://{self.user}:{password_encoded}@{self.host}:{self.port}/{self.name}"


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="KARKAS_LOG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Log level
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Log level"
    )

    # Output format
    format: Literal["text", "json"] = Field(
        default="text",
        description="Log format: 'text' for colored console, 'json' for structured"
    )

    # File logging
    dir: Path = Field(default=Path("logs"), description="Log directory")
    to_file: bool = Field(default=True, description="Enable file logging")

    # Rotation settings
    max_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1024,
        description="Max log file size before rotation"
    )
    backup_count: int = Field(default=5, ge=1, le=100, description="Number of backup files")

    @field_validator("level", mode="before")
    @classmethod
    def uppercase_level(cls, v: str) -> str:
        """Ensure log level is uppercase."""
        return v.upper() if isinstance(v, str) else v


class GrishaSettings(BaseSettings):
    """Grisha AI integration settings."""

    model_config = SettingsConfigDict(
        env_prefix="GRISHA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Grisha RAG API
    api_url: str = Field(
        default="http://localhost:8000",
        description="Grisha RAG API URL"
    )
    api_timeout: int = Field(
        default=30,
        ge=1,
        description="API request timeout in seconds"
    )

    # Retrieval settings
    max_results: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum search results from RAG"
    )


class OllamaSettings(BaseSettings):
    """Ollama LLM settings."""

    model_config = SettingsConfigDict(
        env_prefix="OLLAMA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Ollama connection
    host: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL"
    )

    # Model selection
    model: str = Field(
        default="llama3.3:70b",
        description="Default LLM model for inference"
    )

    # Inference settings
    timeout: int = Field(
        default=120,
        ge=10,
        description="LLM inference timeout in seconds"
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM temperature setting"
    )
    max_tokens: int = Field(
        default=2048,
        ge=1,
        description="Maximum tokens in response"
    )


class PathSettings(BaseSettings):
    """Path configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="KARKAS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Data directories
    data_dir: Path = Field(default=Path("data"), description="Data directory")
    terrain_dir: Path = Field(default=Path("data/terrain"), description="Terrain data directory")
    scenarios_dir: Path = Field(default=Path("data/scenarios"), description="Scenarios directory")
    doctrine_dir: Path = Field(default=Path("data/doctrine"), description="Doctrine files directory")

    @model_validator(mode="after")
    def ensure_directories_exist(self) -> "PathSettings":
        """Ensure data directories exist."""
        for path in [self.data_dir, self.terrain_dir, self.scenarios_dir, self.doctrine_dir]:
            path.mkdir(parents=True, exist_ok=True)
        return self


class ClientSettings(BaseSettings):
    """Client configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="KARKAS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server connection
    server_url: str = Field(
        default="http://localhost:8080",
        description="KARKAS server URL"
    )

    # Connection settings
    connect_timeout: int = Field(
        default=10,
        ge=1,
        description="Connection timeout in seconds"
    )
    read_timeout: int = Field(
        default=30,
        ge=1,
        description="Read timeout in seconds"
    )


class Settings(BaseSettings):
    """
    Main settings class that aggregates all configuration subsystems.

    Environment variables are loaded automatically with appropriate prefixes:
    - KARKAS_* for server settings
    - KARKAS_DB_* for database settings
    - KARKAS_LOG_* for logging settings
    - GRISHA_* for Grisha RAG settings
    - OLLAMA_* for LLM settings

    A .env file in the current directory will be loaded automatically.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Subsystem settings (loaded independently)
    server: ServerSettings = Field(default_factory=ServerSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    grisha: GrishaSettings = Field(default_factory=GrishaSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    client: ClientSettings = Field(default_factory=ClientSettings)

    def __init__(self, **kwargs):
        """Initialize settings, loading each subsystem configuration."""
        super().__init__(**kwargs)
        # Re-load subsystems to pick up environment variables
        object.__setattr__(self, 'server', ServerSettings())
        object.__setattr__(self, 'database', DatabaseSettings())
        object.__setattr__(self, 'logging', LoggingSettings())
        object.__setattr__(self, 'grisha', GrishaSettings())
        object.__setattr__(self, 'ollama', OllamaSettings())
        object.__setattr__(self, 'paths', PathSettings())
        object.__setattr__(self, 'client', ClientSettings())


@lru_cache
def get_settings() -> Settings:
    """
    Get the cached settings instance.

    Settings are loaded once and cached. To reload settings,
    call `get_settings.cache_clear()` first.

    Returns:
        Settings instance with all configuration loaded
    """
    return Settings()


def get_database_url(async_driver: bool = False) -> str:
    """
    Get database URL from settings.

    Convenience function for backward compatibility with existing code.

    Args:
        async_driver: If True, return async driver URL

    Returns:
        Database connection URL
    """
    settings = get_settings()
    return settings.database.async_url if async_driver else settings.database.url


# Export commonly used items
__all__ = [
    "Settings",
    "ServerSettings",
    "DatabaseSettings",
    "LoggingSettings",
    "GrishaSettings",
    "OllamaSettings",
    "PathSettings",
    "ClientSettings",
    "get_settings",
    "get_database_url",
]
