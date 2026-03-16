"""
Grisha Logging Module
Centralized logging configuration for the Grisha RAG system.
"""

import logging
import os
import sys
import yaml
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for dev-friendly output."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def _load_config_logging() -> dict:
    """Load logging settings from config.yaml if available."""
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
            return config.get("logging", {})
    except (FileNotFoundError, yaml.YAMLError):
        return {}


def setup_logging(level: Optional[str] = None, format_type: Optional[str] = None) -> None:
    """
    Initialize logging for Grisha.

    Priority for settings:
    1. Function arguments
    2. Environment variables (GRISHA_LOG_LEVEL, GRISHA_LOG_FORMAT)
    3. config.yaml logging section
    4. Defaults (INFO, text)

    Args:
        level: DEBUG, INFO, WARNING, ERROR
        format_type: 'text' or 'json'
    """
    config_logging = _load_config_logging()

    # Determine log level
    log_level = (
        level or
        os.environ.get("GRISHA_LOG_LEVEL") or
        config_logging.get("level") or
        "INFO"
    ).upper()

    # Determine format type
    log_format = (
        format_type or
        os.environ.get("GRISHA_LOG_FORMAT") or
        config_logging.get("format") or
        "text"
    ).lower()

    # Determine log file (optional)
    log_file = config_logging.get("file")

    # Get numeric level
    numeric_level = getattr(logging, log_level, logging.INFO)

    # Configure root grisha logger
    root_logger = logging.getLogger("grisha")
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(numeric_level)

    if log_format == "json":
        # JSON format for structured logging
        formatter = logging.Formatter(
            '{"time": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "message": "%(message)s"}'
        )
    else:
        # Text format with colors
        formatter = ColoredFormatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S"
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Prevent propagation to root logger
    root_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Get a namespaced logger for Grisha components.

    Args:
        name: Component name (e.g., 'query', 'ingest', 'rerank', 'api')

    Returns:
        Logger instance with namespace 'grisha.<name>'
    """
    return logging.getLogger(f"grisha.{name}")
