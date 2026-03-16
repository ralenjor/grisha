"""Tests for the logging configuration module"""

import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


class TestLoggingConfig:
    """Tests for logging configuration functions"""

    def test_get_log_level_default(self):
        """Test default log level is INFO"""
        from server.logging_config import get_log_level
        with patch.dict(os.environ, {}, clear=True):
            assert get_log_level() == "INFO"

    def test_get_log_level_from_env(self):
        """Test log level from environment variable"""
        from server.logging_config import get_log_level
        with patch.dict(os.environ, {"KARKAS_LOG_LEVEL": "DEBUG"}):
            assert get_log_level() == "DEBUG"

    def test_get_log_level_invalid_fallback(self):
        """Test invalid log level falls back to INFO"""
        from server.logging_config import get_log_level
        with patch.dict(os.environ, {"KARKAS_LOG_LEVEL": "INVALID"}):
            assert get_log_level() == "INFO"

    def test_get_log_format_default(self):
        """Test default log format is text"""
        from server.logging_config import get_log_format
        with patch.dict(os.environ, {}, clear=True):
            assert get_log_format() == "text"

    def test_get_log_format_json(self):
        """Test JSON log format from environment"""
        from server.logging_config import get_log_format
        with patch.dict(os.environ, {"KARKAS_LOG_FORMAT": "json"}):
            assert get_log_format() == "json"

    def test_get_log_dir_default(self):
        """Test default log directory"""
        from server.logging_config import get_log_dir
        with patch.dict(os.environ, {}, clear=True):
            log_dir = get_log_dir()
            assert log_dir == Path("logs")

    def test_get_log_dir_custom(self):
        """Test custom log directory from environment"""
        from server.logging_config import get_log_dir
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"KARKAS_LOG_DIR": tmpdir}):
                log_dir = get_log_dir()
                assert log_dir == Path(tmpdir)


class TestLoggerSetup:
    """Tests for logger setup and initialization"""

    def test_setup_logging_returns_logger(self):
        """Test that setup_logging returns a logger"""
        from server.logging_config import setup_logging
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = setup_logging(log_to_file=False)
            assert isinstance(logger, logging.Logger)
            assert logger.name == "karkas"

    def test_get_logger_namespaced(self):
        """Test get_logger returns properly namespaced logger"""
        from server.logging_config import get_logger
        logger = get_logger("test.module")
        assert logger.name == "karkas.test.module"

    def test_get_logger_already_namespaced(self):
        """Test get_logger with already namespaced name"""
        from server.logging_config import get_logger
        logger = get_logger("karkas.api")
        assert logger.name == "karkas.api"


class TestJSONFormatter:
    """Tests for JSON log formatter"""

    def test_json_formatter_basic(self):
        """Test JSON formatter produces valid JSON"""
        import json
        from server.logging_config import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["message"] == "Test message"
        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["line"] == 42

    def test_json_formatter_with_exception(self):
        """Test JSON formatter includes exception info"""
        import json
        from server.logging_config import JSONFormatter

        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="/test/path.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert "Test error" in data["exception"]["message"]


class TestColoredFormatter:
    """Tests for colored console formatter"""

    def test_colored_formatter_basic(self):
        """Test colored formatter produces output"""
        from server.logging_config import ColoredFormatter

        formatter = ColoredFormatter("[%(levelname)s] %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        assert "Test message" in output
        assert "INFO" in output


class TestRequestIdContext:
    """Tests for request ID context tracking"""

    def test_request_id_context(self):
        """Test request ID is accessible in context"""
        from server.logging_config import request_id_var

        assert request_id_var.get() is None

        request_id_var.set("test-123")
        assert request_id_var.get() == "test-123"

        request_id_var.set(None)
        assert request_id_var.get() is None


class TestLoggingHelpers:
    """Tests for logging helper functions"""

    def test_log_grisha_api_call(self):
        """Test log_grisha_api_call function"""
        from server.logging_config import log_grisha_api_call, setup_logging
        setup_logging(log_to_file=False)

        # Should not raise
        log_grisha_api_call("/search", 150.5, success=True)
        log_grisha_api_call("/search", 500.0, success=False, error="Timeout")

    def test_log_ollama_call(self):
        """Test log_ollama_call function"""
        from server.logging_config import log_ollama_call, setup_logging
        setup_logging(log_to_file=False)

        # Should not raise
        log_ollama_call("llama3.3:70b", 5000.0, tokens=250, success=True)
        log_ollama_call("llama3.3:70b", 100.0, success=False, error="Connection refused")

    def test_log_turn_execution(self):
        """Test log_turn_execution function"""
        from server.logging_config import log_turn_execution, setup_logging
        setup_logging(log_to_file=False)

        # Should not raise
        log_turn_execution(
            turn_number=5,
            phase="execution",
            duration_ms=1500.0,
            events={"movements": 3, "combats": 1, "detections": 5}
        )

    def test_log_order_submission(self):
        """Test log_order_submission function"""
        from server.logging_config import log_order_submission, setup_logging
        setup_logging(log_to_file=False)

        # Should not raise
        log_order_submission("red", 3, ["unit_1", "unit_2", "unit_3"])

    def test_log_database_operation(self):
        """Test log_database_operation function"""
        from server.logging_config import log_database_operation, setup_logging
        setup_logging(log_to_file=False)

        # Should not raise
        log_database_operation("INSERT", "units", 15.5, rows_affected=1)


class TestExecutionTimeDecorator:
    """Tests for log_execution_time decorator"""

    def test_sync_function_timing(self):
        """Test timing of synchronous function"""
        from server.logging_config import log_execution_time, setup_logging
        import time

        setup_logging(log_to_file=False)

        @log_execution_time()
        def slow_function():
            time.sleep(0.01)
            return "done"

        result = slow_function()
        assert result == "done"

    @pytest.mark.asyncio
    async def test_async_function_timing(self):
        """Test timing of async function"""
        from server.logging_config import log_execution_time, setup_logging
        import asyncio

        setup_logging(log_to_file=False)

        @log_execution_time()
        async def slow_async_function():
            await asyncio.sleep(0.01)
            return "async done"

        result = await slow_async_function()
        assert result == "async done"

    def test_function_exception_logged(self):
        """Test that exceptions are logged with timing"""
        from server.logging_config import log_execution_time, setup_logging

        setup_logging(log_to_file=False)

        @log_execution_time()
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()


class TestLoggerConstants:
    """Tests for logger name constants"""

    def test_logger_constants_defined(self):
        """Test that logger constants are defined"""
        from server.logging_config import (
            LOGGER_ROOT,
            LOGGER_API,
            LOGGER_GRISHA,
            LOGGER_DATABASE,
            LOGGER_SIMULATION,
        )

        assert LOGGER_ROOT == "karkas"
        assert LOGGER_API == "karkas.api"
        assert LOGGER_GRISHA == "karkas.grisha"
        assert LOGGER_DATABASE == "karkas.database"
        assert LOGGER_SIMULATION == "karkas.simulation"
