"""
KARKAS Custom Exceptions

This module defines a structured exception hierarchy for the KARKAS server.
All exceptions inherit from KarkasException and can be automatically converted
to standardized HTTP error responses.
"""
from datetime import datetime, timezone
from typing import Any, Optional


class KarkasException(Exception):
    """
    Base exception for all KARKAS-related errors.

    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code (e.g., "UNIT_NOT_FOUND")
        details: Additional context about the error
        http_status: HTTP status code to return (default 500)
    """

    http_status: int = 500
    error_type: str = "server_error"

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code or self._default_error_code()
        self.details = details or {}
        super().__init__(message)

    def _default_error_code(self) -> str:
        """Generate default error code from class name"""
        name = self.__class__.__name__
        # Convert CamelCase to SCREAMING_SNAKE_CASE
        result = []
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                result.append("_")
            result.append(char.upper())
        return "".join(result).replace("_ERROR", "").replace("_EXCEPTION", "")

    def to_dict(self, request_id: Optional[str] = None) -> dict[str, Any]:
        """Convert exception to API response format"""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "type": self.error_type,
                "details": self.details,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "request_id": request_id,
            }
        }


# =============================================================================
# Validation Errors (HTTP 400/422)
# =============================================================================


class ValidationError(KarkasException):
    """Raised when request data fails validation"""

    http_status = 422
    error_type = "validation_error"

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        constraint: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)[:100]  # Truncate long values
        if constraint:
            details["constraint"] = constraint
        super().__init__(message, details=details, **kwargs)


class InvalidFactionError(ValidationError):
    """Raised when an invalid faction is specified"""

    def __init__(self, faction: str):
        super().__init__(
            message=f"Invalid faction: '{faction}'. Must be 'red' or 'blue'",
            error_code="INVALID_FACTION",
            field="faction",
            value=faction,
            details={"accepted_values": ["red", "blue"]},
        )


class InvalidOrderTypeError(ValidationError):
    """Raised when an invalid order type is specified"""

    VALID_TYPES = ["move", "attack", "defend", "support", "recon", "withdraw", "resupply", "hold"]

    def __init__(self, order_type: str):
        super().__init__(
            message=f"Invalid order type: '{order_type}'",
            error_code="INVALID_ORDER_TYPE",
            field="order_type",
            value=order_type,
            details={"accepted_values": self.VALID_TYPES},
        )


class MissingFieldError(ValidationError):
    """Raised when a required field is missing"""

    def __init__(self, field: str, resource: Optional[str] = None):
        resource_msg = f" for {resource}" if resource else ""
        super().__init__(
            message=f"Missing required field: '{field}'{resource_msg}",
            error_code="MISSING_FIELD",
            field=field,
        )


class InvalidCoordinatesError(ValidationError):
    """Raised when coordinates are invalid"""

    def __init__(self, lat: Optional[float] = None, lon: Optional[float] = None, reason: Optional[str] = None):
        details = {}
        if lat is not None:
            details["latitude"] = lat
        if lon is not None:
            details["longitude"] = lon
        if reason:
            details["reason"] = reason

        super().__init__(
            message=reason or "Invalid coordinates",
            error_code="INVALID_COORDINATES",
            details=details,
        )


# =============================================================================
# Not Found Errors (HTTP 404)
# =============================================================================


class NotFoundError(KarkasException):
    """Base class for resource not found errors"""

    http_status = 404
    error_type = "not_found"

    def __init__(self, resource_type: str, resource_id: str, **kwargs):
        details = kwargs.pop("details", {})
        details["resource_type"] = resource_type
        details["resource_id"] = resource_id
        super().__init__(
            message=f"{resource_type} not found: {resource_id}",
            error_code=f"{resource_type.upper()}_NOT_FOUND",
            details=details,
            **kwargs,
        )


class UnitNotFoundError(NotFoundError):
    """Raised when a unit cannot be found"""

    def __init__(self, unit_id: str):
        super().__init__("Unit", unit_id)


class OrderNotFoundError(NotFoundError):
    """Raised when an order cannot be found"""

    def __init__(self, order_id: str):
        super().__init__("Order", order_id)


class ScenarioNotFoundError(NotFoundError):
    """Raised when a scenario cannot be found"""

    def __init__(self, scenario_id: str):
        super().__init__("Scenario", scenario_id)


class GameNotFoundError(NotFoundError):
    """Raised when a game cannot be found"""

    def __init__(self, game_id: str):
        super().__init__("Game", game_id)


class ContactNotFoundError(NotFoundError):
    """Raised when a contact cannot be found"""

    def __init__(self, contact_id: str):
        super().__init__("Contact", contact_id)


# =============================================================================
# Conflict Errors (HTTP 409)
# =============================================================================


class ConflictError(KarkasException):
    """Raised when an operation conflicts with current state"""

    http_status = 409
    error_type = "conflict"


class DuplicateResourceError(ConflictError):
    """Raised when trying to create a resource that already exists"""

    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            message=f"{resource_type} already exists: {resource_id}",
            error_code=f"{resource_type.upper()}_ALREADY_EXISTS",
            details={
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        )


class InvalidStateError(ConflictError):
    """Raised when an operation is invalid for the current state"""

    def __init__(self, message: str, current_state: Optional[str] = None, required_state: Optional[str] = None):
        details = {}
        if current_state:
            details["current_state"] = current_state
        if required_state:
            details["required_state"] = required_state
        super().__init__(
            message=message,
            error_code="INVALID_STATE",
            details=details,
        )


class OrdersAlreadySubmittedError(ConflictError):
    """Raised when orders have already been submitted for a faction"""

    def __init__(self, faction: str):
        super().__init__(
            message=f"Orders already submitted for {faction}",
            error_code="ORDERS_ALREADY_SUBMITTED",
            details={"faction": faction},
        )


class ActiveScenarioError(ConflictError):
    """Raised when an operation cannot be performed on an active scenario"""

    def __init__(self, scenario_id: str, operation: str):
        super().__init__(
            message=f"Cannot {operation} active scenario: {scenario_id}",
            error_code="ACTIVE_SCENARIO",
            details={
                "scenario_id": scenario_id,
                "operation": operation,
            },
        )


class NoActiveScenarioError(ConflictError):
    """Raised when an operation requires an active scenario but none is loaded"""

    def __init__(self):
        super().__init__(
            message="No scenario is currently active",
            error_code="NO_ACTIVE_SCENARIO",
        )


# =============================================================================
# External Service Errors (HTTP 502/503/504)
# =============================================================================


class ServiceError(KarkasException):
    """Base class for external service errors"""

    http_status = 503
    error_type = "service_error"

    def __init__(self, service: str, message: str, **kwargs):
        details = kwargs.pop("details", {})
        details["service"] = service
        super().__init__(message, details=details, **kwargs)


class GrishaServiceError(ServiceError):
    """Raised when the Grisha RAG service fails"""

    def __init__(self, message: str = "Grisha service unavailable", operation: Optional[str] = None):
        details = {}
        if operation:
            details["operation"] = operation
        super().__init__(
            service="grisha",
            message=message,
            error_code="GRISHA_SERVICE_ERROR",
            details=details,
        )


class OllamaServiceError(ServiceError):
    """Raised when the Ollama LLM service fails"""

    def __init__(self, message: str = "Ollama service unavailable", model: Optional[str] = None):
        details = {}
        if model:
            details["model"] = model
        super().__init__(
            service="ollama",
            message=message,
            error_code="OLLAMA_SERVICE_ERROR",
            details=details,
        )


class ServiceTimeoutError(ServiceError):
    """Raised when an external service request times out"""

    http_status = 504

    def __init__(self, service: str, timeout_seconds: float):
        super().__init__(
            service=service,
            message=f"{service} request timed out after {timeout_seconds}s",
            error_code="SERVICE_TIMEOUT",
            details={"timeout_seconds": timeout_seconds},
        )


class ServiceConnectionError(ServiceError):
    """Raised when connection to an external service fails"""

    def __init__(self, service: str, host: Optional[str] = None):
        details = {}
        if host:
            details["host"] = host
        super().__init__(
            service=service,
            message=f"Cannot connect to {service}",
            error_code="SERVICE_CONNECTION_ERROR",
            details=details,
        )


# =============================================================================
# Database Errors (HTTP 500/503)
# =============================================================================


class DatabaseError(KarkasException):
    """Raised when a database operation fails"""

    http_status = 500
    error_type = "database_error"

    def __init__(self, message: str, operation: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if operation:
            details["operation"] = operation
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            details=details,
            **kwargs,
        )


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails"""

    http_status = 503

    def __init__(self, message: str = "Database connection failed"):
        super().__init__(message, operation=None)
        self.error_code = "DATABASE_CONNECTION_ERROR"


class DatabaseIntegrityError(DatabaseError):
    """Raised when a database integrity constraint is violated"""

    def __init__(self, message: str, constraint: Optional[str] = None):
        super().__init__(message, operation=None)
        self.error_code = "DATABASE_INTEGRITY_ERROR"
        if constraint:
            self.details["constraint"] = constraint


# =============================================================================
# Authorization Errors (HTTP 401/403)
# =============================================================================


class AuthenticationError(KarkasException):
    """Raised when authentication fails"""

    http_status = 401
    error_type = "authentication_error"

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, error_code="AUTHENTICATION_REQUIRED")


class AuthorizationError(KarkasException):
    """Raised when authorization fails"""

    http_status = 403
    error_type = "authorization_error"

    def __init__(self, message: str = "Permission denied", resource: Optional[str] = None):
        details = {}
        if resource:
            details["resource"] = resource
        super().__init__(message, error_code="PERMISSION_DENIED", details=details)


class FactionAccessError(AuthorizationError):
    """Raised when accessing resources of another faction"""

    def __init__(self, requested_faction: str, allowed_faction: str):
        super().__init__(
            message=f"Cannot access {requested_faction} resources as {allowed_faction}",
            resource=f"faction:{requested_faction}",
        )
        self.details["requested_faction"] = requested_faction
        self.details["allowed_faction"] = allowed_faction


# =============================================================================
# Rate Limiting (HTTP 429)
# =============================================================================


class RateLimitError(KarkasException):
    """Raised when rate limit is exceeded"""

    http_status = 429
    error_type = "rate_limit"

    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        details = {}
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(message, error_code="RATE_LIMIT_EXCEEDED", details=details)
        self.retry_after = retry_after


# =============================================================================
# Simulation Errors (HTTP 400/500)
# =============================================================================


class SimulationError(KarkasException):
    """Base class for simulation-related errors"""

    http_status = 500
    error_type = "simulation_error"


class TerrainError(SimulationError):
    """Raised when terrain operations fail"""

    def __init__(self, message: str, coordinates: Optional[dict] = None):
        details = {}
        if coordinates:
            details["coordinates"] = coordinates
        super().__init__(message, error_code="TERRAIN_ERROR", details=details)


class PathfindingError(SimulationError):
    """Raised when pathfinding fails"""

    def __init__(self, message: str, start: Optional[dict] = None, end: Optional[dict] = None):
        details = {}
        if start:
            details["start"] = start
        if end:
            details["end"] = end
        super().__init__(message, error_code="PATHFINDING_ERROR", details=details)
