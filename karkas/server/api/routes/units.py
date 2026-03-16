"""Unit management routes"""
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException

router = APIRouter()

# In-memory unit storage (would be replaced by C++ simulation state)
_units: dict[str, dict] = {}


@router.get("")
async def list_units(
    faction: Optional[str] = None,
    type: Optional[str] = None,
    echelon: Optional[str] = None,
):
    """List all units, optionally filtered"""
    units = list(_units.values())

    if faction:
        units = [u for u in units if u.get("faction") == faction]
    if type:
        units = [u for u in units if u.get("type") == type]
    if echelon:
        units = [u for u in units if u.get("echelon") == echelon]

    return {"units": units, "count": len(units)}


@router.get("/{unit_id}")
async def get_unit(unit_id: str):
    """Get a specific unit by ID"""
    unit = _units.get(unit_id)
    if not unit:
        raise HTTPException(404, "Unit not found")
    return unit


@router.post("")
async def create_unit(unit_data: dict):
    """Create a new unit"""
    unit_id = unit_data.get("id") or str(uuid.uuid4())
    unit_data["id"] = unit_id

    # Set defaults
    unit_data.setdefault("posture", "defend")
    unit_data.setdefault("heading", 0)
    unit_data.setdefault("logistics", {
        "fuel_level": 1.0,
        "ammo_level": 1.0,
        "supply_level": 1.0,
        "maintenance_state": 1.0,
    })
    unit_data.setdefault("morale", {
        "morale": 0.8,
        "fatigue": 0.0,
        "cohesion": 1.0,
    })

    # Set default strength based on echelon
    echelon_strength = {
        "squad": {"personnel_max": 10, "equipment_max": 2},
        "platoon": {"personnel_max": 40, "equipment_max": 4},
        "company": {"personnel_max": 150, "equipment_max": 15},
        "battalion": {"personnel_max": 600, "equipment_max": 50},
        "regiment": {"personnel_max": 2500, "equipment_max": 150},
        "brigade": {"personnel_max": 4000, "equipment_max": 250},
        "division": {"personnel_max": 12000, "equipment_max": 500},
    }

    echelon = unit_data.get("echelon", "battalion")
    defaults = echelon_strength.get(echelon, echelon_strength["battalion"])
    unit_data.setdefault("strength", {
        "personnel_current": defaults["personnel_max"],
        "personnel_max": defaults["personnel_max"],
        "equipment_current": defaults["equipment_max"],
        "equipment_max": defaults["equipment_max"],
    })

    _units[unit_id] = unit_data
    return unit_data


@router.put("/{unit_id}")
async def update_unit(unit_id: str, updates: dict):
    """Update a unit"""
    unit = _units.get(unit_id)
    if not unit:
        raise HTTPException(404, "Unit not found")

    # Update allowed fields
    allowed_fields = ["position", "heading", "posture", "logistics", "morale"]
    for field in allowed_fields:
        if field in updates:
            if isinstance(updates[field], dict) and isinstance(unit.get(field), dict):
                unit[field].update(updates[field])
            else:
                unit[field] = updates[field]

    return unit


@router.delete("/{unit_id}")
async def delete_unit(unit_id: str):
    """Delete a unit"""
    if unit_id not in _units:
        raise HTTPException(404, "Unit not found")

    del _units[unit_id]
    return {"message": "Unit deleted"}


@router.get("/{unit_id}/subordinates")
async def get_subordinates(unit_id: str):
    """Get subordinate units"""
    unit = _units.get(unit_id)
    if not unit:
        raise HTTPException(404, "Unit not found")

    subordinates = [
        u for u in _units.values()
        if u.get("parent_id") == unit_id
    ]

    return {"subordinates": subordinates}


@router.post("/{unit_id}/assign-parent/{parent_id}")
async def assign_parent(unit_id: str, parent_id: str):
    """Assign a parent unit"""
    unit = _units.get(unit_id)
    parent = _units.get(parent_id)

    if not unit:
        raise HTTPException(404, "Unit not found")
    if not parent:
        raise HTTPException(404, "Parent unit not found")
    if unit.get("faction") != parent.get("faction"):
        raise HTTPException(400, "Units must be same faction")

    unit["parent_id"] = parent_id
    return unit


@router.get("/by-location")
async def get_units_by_location(
    lat: float,
    lon: float,
    radius_km: float = 10.0,
    faction: Optional[str] = None,
):
    """Get units within radius of a location"""
    import math

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon/2)**2)
        return R * 2 * math.asin(math.sqrt(a))

    results = []
    for unit in _units.values():
        pos = unit.get("position", {})
        ulat = pos.get("latitude", 0)
        ulon = pos.get("longitude", 0)

        dist = haversine(lat, lon, ulat, ulon)
        if dist <= radius_km:
            if faction is None or unit.get("faction") == faction:
                results.append({**unit, "distance_km": dist})

    results.sort(key=lambda u: u["distance_km"])
    return {"units": results}
