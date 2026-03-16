"""Order management routes"""
import uuid
from typing import Optional
from fastapi import APIRouter

from server.exceptions import (
    OrderNotFoundError,
    ValidationError,
    MissingFieldError,
    InvalidOrderTypeError,
)

router = APIRouter()

# In-memory order storage
_orders: dict[str, dict] = {}


@router.get("")
async def list_orders(
    faction: Optional[str] = None,
    active: Optional[bool] = None,
    turn: Optional[int] = None,
):
    """List all orders, optionally filtered"""
    orders = list(_orders.values())

    if faction:
        orders = [o for o in orders if o.get("faction") == faction]
    if active is not None:
        orders = [o for o in orders if o.get("active") == active]
    if turn is not None:
        orders = [o for o in orders if o.get("issued_turn") == turn]

    return {"orders": orders, "count": len(orders)}


@router.get("/{order_id}")
async def get_order(order_id: str):
    """Get a specific order by ID"""
    order = _orders.get(order_id)
    if not order:
        raise OrderNotFoundError(order_id)
    return order


@router.post("")
async def create_order(order_data: dict):
    """Create a new order"""
    order_id = str(uuid.uuid4())
    order_data["order_id"] = order_id
    order_data.setdefault("active", True)
    order_data.setdefault("issued_turn", 0)

    # Validate order
    validation = validate_order(order_data)
    if not validation["valid"]:
        # Return all errors in details, first error as message
        raise ValidationError(
            message=validation["error"],
            details={
                "errors": validation.get("all_errors", [validation["error"]]),
                "warnings": validation.get("warnings", []),
            },
        )

    _orders[order_id] = order_data
    return order_data


@router.post("/validate")
async def validate_order_endpoint(order_data: dict):
    """Validate an order without creating it"""
    return validate_order(order_data)


@router.delete("/{order_id}")
async def cancel_order(order_id: str):
    """Cancel an order"""
    order = _orders.get(order_id)
    if not order:
        raise OrderNotFoundError(order_id)

    order["active"] = False
    return {"message": "Order cancelled"}


@router.post("/batch")
async def create_orders_batch(orders: list[dict]):
    """Create multiple orders at once"""
    created = []
    errors = []

    for i, order_data in enumerate(orders):
        validation = validate_order(order_data)
        if not validation["valid"]:
            errors.append({"index": i, "error": validation["error"]})
            continue

        order_id = str(uuid.uuid4())
        order_data["order_id"] = order_id
        order_data.setdefault("active", True)
        _orders[order_id] = order_data
        created.append(order_data)

    return {
        "created": created,
        "errors": errors,
        "success_count": len(created),
        "error_count": len(errors),
    }


def validate_order(order_data: dict) -> dict:
    """Validate order data"""
    errors = []
    warnings = []

    # Required fields
    required = ["issuer", "target_units", "order_type", "objective"]
    for field in required:
        if field not in order_data:
            errors.append(f"Missing required field: {field}")

    if errors:
        return {
            "valid": False,
            "error": errors[0],
            "all_errors": errors,
            "warnings": warnings,
        }

    # Validate order type
    valid_types = ["move", "attack", "defend", "support", "recon", "withdraw", "resupply", "hold"]
    if order_data["order_type"] not in valid_types:
        errors.append(f"Invalid order type: {order_data['order_type']}. Valid types: {', '.join(valid_types)}")

    # Validate objective
    objective = order_data.get("objective", {})
    obj_type = objective.get("type")

    if obj_type == "position":
        if "coordinates" not in objective:
            errors.append("Position objective requires coordinates")
    elif obj_type == "unit":
        if "target_unit_id" not in objective:
            errors.append("Unit objective requires target_unit_id")
    elif obj_type == "zone":
        if "zone_name" not in objective and "zone_polygon" not in objective:
            errors.append("Zone objective requires zone_name or zone_polygon")

    # Validate target units
    if not order_data.get("target_units"):
        errors.append("Order must have at least one target unit")

    # Warnings for potentially problematic orders
    constraints = order_data.get("constraints", {})
    if constraints.get("max_casualties_percent", 100) < 10:
        warnings.append("Low casualty threshold may cause premature withdrawal")

    if order_data["order_type"] == "attack" and constraints.get("roe") == "weapons_hold":
        warnings.append("Attack order with weapons hold ROE may be ineffective")

    if errors:
        return {
            "valid": False,
            "error": errors[0],
            "all_errors": errors,
            "warnings": warnings,
        }

    return {"valid": True, "error": None, "all_errors": [], "warnings": warnings}


@router.post("/parse-natural-language")
async def parse_natural_language(data: dict):
    """Parse natural language order into structured format"""
    text = data.get("text", "")
    faction = data.get("faction", "red")

    # This would normally call Grisha to parse
    # For now, return a simple template
    return {
        "parsed": {
            "issuer": "commander",
            "target_units": [],
            "order_type": "move",
            "objective": {
                "type": "position",
                "coordinates": None,
            },
            "constraints": {
                "route": "fastest",
                "roe": "weapons_free",
            },
            "natural_language": text,
        },
        "confidence": 0.0,
        "needs_clarification": True,
        "questions": [
            "Which units should execute this order?",
            "What is the destination?",
        ],
    }
