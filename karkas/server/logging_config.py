"""
Logging Configuration for KARKAS Server

Provides centralized logging configuration with:
- Console and rotating file handlers
- Structured JSON logging for production
- Request/response logging middleware for FastAPI
- Environment-based log level configuration
"""

import logging
import logging.config
import logging.handlers
import os
import sys
import json
from datetime import datetime, timezone
from typing import Optional, Any
from pathlib import Path
from contextvars import ContextVar
from functools import wraps
import time
import traceback

# Context variable for request ID tracking
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)

# Logger name constants
LOGGER_ROOT = "karkas"
LOGGER_API = "karkas.api"
LOGGER_GRISHA = "karkas.grisha"
LOGGER_DATABASE = "karkas.database"
LOGGER_CLIENT = "karkas.client"
LOGGER_SIMULATION = "karkas.simulation"


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    Outputs log records as JSON objects for easy parsing.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add request ID if available
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ('msg', 'args', 'name', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'lineno', 'funcName', 'created',
                          'msecs', 'relativeCreated', 'thread', 'threadName',
                          'processName', 'process', 'getMessage', 'exc_info',
                          'exc_text', 'stack_info', 'message'):
                if not key.startswith('_'):
                    log_data[key] = value

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """
    Colored console formatter for development use.
    """

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        # Add request ID to message if available
        request_id = request_id_var.get()
        if request_id:
            record.msg = f"[{request_id[:8]}] {record.msg}"

        color = self.COLORS.get(record.levelname, '')
        formatted = super().format(record)
        return f"{color}{formatted}{self.RESET}"


def get_log_level() -> str:
    """Get log level from environment, defaulting to INFO."""
    level = os.environ.get("KARKAS_LOG_LEVEL", "INFO").upper()
    valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    return level if level in valid_levels else "INFO"


def get_log_format() -> str:
    """Get log format from environment: 'json' or 'text'."""
    fmt = os.environ.get("KARKAS_LOG_FORMAT", "text").lower()
    return fmt if fmt in ("json", "text") else "text"


def get_log_dir() -> Path:
    """Get log directory, creating it if necessary."""
    log_dir = Path(os.environ.get("KARKAS_LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging(
    level: Optional[str] = None,
    log_format: Optional[str] = None,
    log_to_file: bool = True,
    log_dir: Optional[Path] = None,
) -> logging.Logger:
    """
    Configure logging for the KARKAS application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ('json' or 'text')
        log_to_file: Whether to log to rotating files
        log_dir: Directory for log files

    Returns:
        The root karkas logger
    """
    level = level or get_log_level()
    log_format = log_format or get_log_format()
    log_dir = log_dir or get_log_dir()

    # Create handlers
    handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ColoredFormatter(
            "[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
    handlers.append(console_handler)

    # File handlers
    if log_to_file:
        # Main application log (rotating, 10MB max, 5 backups)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "karkas.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(JSONFormatter())
        handlers.append(file_handler)

        # Error-only log
        error_handler = logging.handlers.RotatingFileHandler(
            log_dir / "karkas_errors.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        handlers.append(error_handler)

    # Configure root karkas logger
    root_logger = logging.getLogger(LOGGER_ROOT)
    root_logger.setLevel(level)
    root_logger.handlers = []  # Clear existing handlers
    for handler in handlers:
        root_logger.addHandler(handler)

    # Prevent propagation to root logger
    root_logger.propagate = False

    # Configure sub-loggers with appropriate levels
    _configure_sub_loggers(level)

    # Quiet down noisy third-party loggers
    _quiet_third_party_loggers()

    root_logger.info(
        "Logging initialized",
        extra={
            "log_level": level,
            "log_format": log_format,
            "log_to_file": log_to_file,
            "log_dir": str(log_dir)
        }
    )

    return root_logger


def _configure_sub_loggers(base_level: str) -> None:
    """Configure sub-loggers with appropriate levels."""
    level_num = getattr(logging, base_level.upper(), logging.INFO)

    # API logger - can be more verbose in debug mode
    api_logger = logging.getLogger(LOGGER_API)
    api_logger.setLevel(level_num)

    # Grisha AI logger - important for debugging AI decisions
    grisha_logger = logging.getLogger(LOGGER_GRISHA)
    grisha_logger.setLevel(level_num)

    # Database logger - usually INFO unless debugging
    db_logger = logging.getLogger(LOGGER_DATABASE)
    db_logger.setLevel(max(level_num, logging.INFO))

    # Simulation logger
    sim_logger = logging.getLogger(LOGGER_SIMULATION)
    sim_logger.setLevel(level_num)


def _quiet_third_party_loggers() -> None:
    """Reduce noise from third-party libraries."""
    noisy_loggers = [
        "uvicorn.access",
        "uvicorn.error",
        "httpcore",
        "httpx",
        "asyncio",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger by name.

    Args:
        name: Logger name (e.g., 'karkas.api.routes')

    Returns:
        Logger instance
    """
    # Ensure the name is under the karkas namespace
    if not name.startswith(LOGGER_ROOT):
        name = f"{LOGGER_ROOT}.{name}"
    return logging.getLogger(name)


def get_request_id() -> Optional[str]:
    """
    Get the current request ID from context.

    Returns:
        The request ID if set, otherwise None
    """
    return request_id_var.get()


def log_execution_time(logger: Optional[logging.Logger] = None, level: int = logging.DEBUG):
    """
    Decorator to log function execution time.

    Args:
        logger: Logger to use (defaults to module logger)
        level: Log level for timing messages
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)

            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start_time
                logger.log(level, f"{func.__name__} completed in {elapsed:.3f}s")
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start_time
                logger.error(
                    f"{func.__name__} failed after {elapsed:.3f}s: {e}",
                    exc_info=True
                )
                raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)

            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                elapsed = time.perf_counter() - start_time
                logger.log(level, f"{func.__name__} completed in {elapsed:.3f}s")
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start_time
                logger.error(
                    f"{func.__name__} failed after {elapsed:.3f}s: {e}",
                    exc_info=True
                )
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator


# FastAPI middleware for request logging
class RequestLoggingMiddleware:
    """
    Middleware for logging HTTP requests and responses.
    """

    def __init__(self, app):
        self.app = app
        self.logger = get_logger("api.middleware")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import uuid
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)

        start_time = time.perf_counter()
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        query_string = scope.get("query_string", b"").decode()

        self.logger.info(
            f"Request started: {method} {path}",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "query_string": query_string,
                "client": scope.get("client"),
            }
        )

        status_code = 500  # Default in case of error

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            self.logger.exception(
                f"Request failed: {method} {path}",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                }
            )
            raise
        finally:
            elapsed = time.perf_counter() - start_time
            log_level = logging.INFO if status_code < 400 else logging.WARNING
            if status_code >= 500:
                log_level = logging.ERROR

            self.logger.log(
                log_level,
                f"Request completed: {method} {path} - {status_code} in {elapsed:.3f}s",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": round(elapsed * 1000, 2),
                }
            )
            request_id_var.set(None)


def log_database_operation(operation: str, table: str, duration_ms: float, rows_affected: int = 0):
    """Log a database operation with metrics."""
    logger = get_logger("database")
    logger.debug(
        f"Database {operation} on {table}",
        extra={
            "operation": operation,
            "table": table,
            "duration_ms": duration_ms,
            "rows_affected": rows_affected,
        }
    )


def log_grisha_api_call(endpoint: str, duration_ms: float, success: bool, error: Optional[str] = None):
    """Log a Grisha API call with metrics."""
    logger = get_logger("grisha.api")
    level = logging.INFO if success else logging.ERROR
    logger.log(
        level,
        f"Grisha API call to {endpoint}: {'success' if success else 'failed'}",
        extra={
            "endpoint": endpoint,
            "duration_ms": duration_ms,
            "success": success,
            "error": error,
        }
    )


def log_ollama_call(model: str, duration_ms: float, tokens: int = 0, success: bool = True, error: Optional[str] = None):
    """Log an Ollama LLM call with metrics."""
    logger = get_logger("grisha.ollama")
    level = logging.INFO if success else logging.ERROR
    logger.log(
        level,
        f"Ollama {model} inference: {'success' if success else 'failed'}",
        extra={
            "model": model,
            "duration_ms": duration_ms,
            "tokens": tokens,
            "success": success,
            "error": error,
        }
    )


def log_turn_execution(turn_number: int, phase: str, duration_ms: float, events: dict):
    """Log turn execution with summary metrics."""
    logger = get_logger("simulation.turn")
    logger.info(
        f"Turn {turn_number} {phase} completed",
        extra={
            "turn_number": turn_number,
            "phase": phase,
            "duration_ms": duration_ms,
            "events": events,
        }
    )


def log_order_submission(faction: str, order_count: int, unit_ids: list):
    """Log order submission."""
    logger = get_logger("api.orders")
    logger.info(
        f"Orders submitted by {faction}: {order_count} orders",
        extra={
            "faction": faction,
            "order_count": order_count,
            "unit_ids": unit_ids,
        }
    )
