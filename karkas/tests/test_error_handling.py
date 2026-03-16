"""
Tests for KARKAS error handling infrastructure.

Tests the custom exception hierarchy and error response formatting.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch
import sys
import os

# Add karkas to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from server.exceptions import (
    KarkasException,
    ValidationError,
    InvalidFactionError,
    InvalidOrderTypeError,
    MissingFieldError,
    InvalidCoordinatesError,
    NotFoundError,
    UnitNotFoundError,
    OrderNotFoundError,
    ScenarioNotFoundError,
    GameNotFoundError,
    ConflictError,
    DuplicateResourceError,
    InvalidStateError,
    OrdersAlreadySubmittedError,
    ActiveScenarioError,
    NoActiveScenarioError,
    ServiceError,
    GrishaServiceError,
    OllamaServiceError,
    ServiceTimeoutError,
    ServiceConnectionError,
    DatabaseError,
    DatabaseConnectionError,
    DatabaseIntegrityError,
    AuthenticationError,
    AuthorizationError,
    FactionAccessError,
    RateLimitError,
    SimulationError,
    TerrainError,
    PathfindingError,
)


# =============================================================================
# Test Exception Classes
# =============================================================================


class TestKarkasException:
    """Tests for base KarkasException"""

    def test_basic_exception(self):
        """Test basic exception creation"""
        exc = KarkasException("Something went wrong")
        assert exc.message == "Something went wrong"
        assert exc.error_code == "KARKAS"  # Derived from class name
        assert exc.http_status == 500
        assert exc.error_type == "server_error"
        assert exc.details == {}

    def test_exception_with_code(self):
        """Test exception with custom error code"""
        exc = KarkasException("Error", error_code="CUSTOM_ERROR")
        assert exc.error_code == "CUSTOM_ERROR"

    def test_exception_with_details(self):
        """Test exception with details"""
        exc = KarkasException("Error", details={"key": "value"})
        assert exc.details == {"key": "value"}

    def test_to_dict(self):
        """Test conversion to dictionary"""
        exc = KarkasException("Test error", error_code="TEST_ERROR")
        result = exc.to_dict(request_id="abc123")

        assert "error" in result
        assert result["error"]["code"] == "TEST_ERROR"
        assert result["error"]["message"] == "Test error"
        assert result["error"]["request_id"] == "abc123"
        assert "timestamp" in result["error"]

    def test_auto_error_code_generation(self):
        """Test automatic error code generation from class name"""
        exc = ValidationError("Test")
        assert exc.error_code == "VALIDATION"


class TestValidationErrors:
    """Tests for validation error classes"""

    def test_validation_error(self):
        """Test basic validation error"""
        exc = ValidationError("Invalid value", field="name", value="foo")
        assert exc.http_status == 422
        assert exc.error_type == "validation_error"
        assert exc.details["field"] == "name"
        assert exc.details["value"] == "foo"

    def test_invalid_faction_error(self):
        """Test invalid faction error"""
        exc = InvalidFactionError("green")
        assert "green" in exc.message
        assert exc.details["accepted_values"] == ["red", "blue"]
        assert exc.error_code == "INVALID_FACTION"

    def test_invalid_order_type_error(self):
        """Test invalid order type error"""
        exc = InvalidOrderTypeError("jump")
        assert "jump" in exc.message
        assert "accepted_values" in exc.details
        assert "move" in exc.details["accepted_values"]

    def test_missing_field_error(self):
        """Test missing field error"""
        exc = MissingFieldError("name", resource="Unit")
        assert "name" in exc.message
        assert "Unit" in exc.message
        assert exc.error_code == "MISSING_FIELD"

    def test_invalid_coordinates_error(self):
        """Test invalid coordinates error"""
        exc = InvalidCoordinatesError(lat=91.0, lon=180.0, reason="Latitude out of range")
        assert "Latitude out of range" in exc.message
        assert exc.details["latitude"] == 91.0


class TestNotFoundErrors:
    """Tests for not found error classes"""

    def test_not_found_error(self):
        """Test generic not found error"""
        exc = NotFoundError("Resource", "abc123")
        assert exc.http_status == 404
        assert exc.error_type == "not_found"
        assert "abc123" in exc.message
        assert exc.details["resource_id"] == "abc123"

    def test_unit_not_found_error(self):
        """Test unit not found error"""
        exc = UnitNotFoundError("unit_1")
        assert exc.error_code == "UNIT_NOT_FOUND"
        assert "unit_1" in exc.message

    def test_order_not_found_error(self):
        """Test order not found error"""
        exc = OrderNotFoundError("order_xyz")
        assert exc.error_code == "ORDER_NOT_FOUND"

    def test_scenario_not_found_error(self):
        """Test scenario not found error"""
        exc = ScenarioNotFoundError("fulda_gap")
        assert exc.error_code == "SCENARIO_NOT_FOUND"

    def test_game_not_found_error(self):
        """Test game not found error"""
        exc = GameNotFoundError("game_123")
        assert exc.error_code == "GAME_NOT_FOUND"


class TestConflictErrors:
    """Tests for conflict error classes"""

    def test_conflict_error(self):
        """Test basic conflict error"""
        exc = ConflictError("Resource conflict")
        assert exc.http_status == 409
        assert exc.error_type == "conflict"

    def test_duplicate_resource_error(self):
        """Test duplicate resource error"""
        exc = DuplicateResourceError("Scenario", "tutorial")
        assert "already exists" in exc.message
        assert exc.details["resource_id"] == "tutorial"

    def test_invalid_state_error(self):
        """Test invalid state error"""
        exc = InvalidStateError(
            "Cannot submit orders",
            current_state="execution",
            required_state="planning",
        )
        assert exc.details["current_state"] == "execution"
        assert exc.details["required_state"] == "planning"

    def test_orders_already_submitted_error(self):
        """Test orders already submitted error"""
        exc = OrdersAlreadySubmittedError("red")
        assert "red" in exc.message
        assert exc.details["faction"] == "red"

    def test_active_scenario_error(self):
        """Test active scenario error"""
        exc = ActiveScenarioError("fulda_gap", "delete")
        assert "delete" in exc.message
        assert exc.details["operation"] == "delete"

    def test_no_active_scenario_error(self):
        """Test no active scenario error"""
        exc = NoActiveScenarioError()
        assert "No scenario" in exc.message


class TestServiceErrors:
    """Tests for external service error classes"""

    def test_service_error(self):
        """Test base service error"""
        exc = ServiceError("test-service", "Service failed")
        assert exc.http_status == 503
        assert exc.error_type == "service_error"
        assert exc.details["service"] == "test-service"

    def test_grisha_service_error(self):
        """Test Grisha service error"""
        exc = GrishaServiceError("RAG query failed", operation="search")
        assert exc.details["service"] == "grisha"
        assert exc.details["operation"] == "search"

    def test_ollama_service_error(self):
        """Test Ollama service error"""
        exc = OllamaServiceError("Model not found", model="llama3")
        assert exc.details["model"] == "llama3"

    def test_service_timeout_error(self):
        """Test service timeout error"""
        exc = ServiceTimeoutError("ollama", 30.0)
        assert exc.http_status == 504
        assert "30.0s" in exc.message
        assert exc.details["timeout_seconds"] == 30.0

    def test_service_connection_error(self):
        """Test service connection error"""
        exc = ServiceConnectionError("grisha", host="localhost:8000")
        assert exc.details["host"] == "localhost:8000"


class TestDatabaseErrors:
    """Tests for database error classes"""

    def test_database_error(self):
        """Test database error"""
        exc = DatabaseError("Query failed", operation="insert")
        assert exc.http_status == 500
        assert exc.error_type == "database_error"
        assert exc.details["operation"] == "insert"

    def test_database_connection_error(self):
        """Test database connection error"""
        exc = DatabaseConnectionError()
        assert exc.http_status == 503
        assert "connection" in exc.message.lower()

    def test_database_integrity_error(self):
        """Test database integrity error"""
        exc = DatabaseIntegrityError("Duplicate key", constraint="unique_name")
        assert exc.details["constraint"] == "unique_name"


class TestAuthErrors:
    """Tests for authentication/authorization error classes"""

    def test_authentication_error(self):
        """Test authentication error"""
        exc = AuthenticationError()
        assert exc.http_status == 401
        assert exc.error_type == "authentication_error"

    def test_authorization_error(self):
        """Test authorization error"""
        exc = AuthorizationError("Cannot access this resource", resource="unit_1")
        assert exc.http_status == 403
        assert exc.error_type == "authorization_error"
        assert exc.details["resource"] == "unit_1"

    def test_faction_access_error(self):
        """Test faction access error"""
        exc = FactionAccessError("red", "blue")
        assert exc.details["requested_faction"] == "red"
        assert exc.details["allowed_faction"] == "blue"


class TestRateLimitError:
    """Tests for rate limit error class"""

    def test_rate_limit_error(self):
        """Test rate limit error"""
        exc = RateLimitError(retry_after=60)
        assert exc.http_status == 429
        assert exc.error_type == "rate_limit"
        assert exc.retry_after == 60
        assert exc.details["retry_after_seconds"] == 60


class TestSimulationErrors:
    """Tests for simulation error classes"""

    def test_terrain_error(self):
        """Test terrain error"""
        exc = TerrainError("Terrain not loaded", coordinates={"lat": 50.0, "lon": 9.0})
        assert exc.details["coordinates"] == {"lat": 50.0, "lon": 9.0}

    def test_pathfinding_error(self):
        """Test pathfinding error"""
        exc = PathfindingError(
            "No path found",
            start={"lat": 50.0, "lon": 9.0},
            end={"lat": 51.0, "lon": 10.0},
        )
        assert exc.details["start"] == {"lat": 50.0, "lon": 9.0}
        assert exc.details["end"] == {"lat": 51.0, "lon": 10.0}


# =============================================================================
# Test Error Response Creation
# =============================================================================
# NOTE: Full integration tests with FastAPI error handlers require all
# dependencies (SQLAlchemy, GeoAlchemy2, etc). These are tested when
# running the full test suite with `make test`.
#
# This file focuses on testing the exception classes themselves.
