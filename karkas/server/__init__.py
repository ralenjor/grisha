"""
KARKAS Server Package

This package contains the core server components:
- api: FastAPI application and routes
- database: PostgreSQL/PostGIS persistence
- grisha: AI integration (Commander, Advisor, OrderParser)
- logging_config: Centralized logging configuration
"""

from .logging_config import (
    setup_logging,
    get_logger,
    RequestLoggingMiddleware,
    log_turn_execution,
    log_order_submission,
    log_grisha_api_call,
    log_ollama_call,
    log_database_operation,
    log_execution_time,
    LOGGER_ROOT,
    LOGGER_API,
    LOGGER_GRISHA,
    LOGGER_DATABASE,
    LOGGER_SIMULATION,
)

__all__ = [
    'setup_logging',
    'get_logger',
    'RequestLoggingMiddleware',
    'log_turn_execution',
    'log_order_submission',
    'log_grisha_api_call',
    'log_ollama_call',
    'log_database_operation',
    'log_execution_time',
    'LOGGER_ROOT',
    'LOGGER_API',
    'LOGGER_GRISHA',
    'LOGGER_DATABASE',
    'LOGGER_SIMULATION',
]
