"""Order Parser - Translate natural language orders to structured JSON"""
import asyncio
import json
import re
from typing import Optional

import httpx


class OrderParser:
    """
    Parse natural language military orders into structured format.

    Uses Grisha/Ollama to interpret human-readable orders and convert
    them to JSON that can be processed by the simulation engine.
    """

    SYSTEM_PROMPT = """You are a military order parser. Your job is to convert
natural language military orders into structured JSON format.

Order types:
- move: Unit relocates to a position
- attack: Unit engages enemy at position or attacks specific unit
- defend: Unit holds position against enemy
- support: Unit provides fire support to another unit
- recon: Unit conducts reconnaissance
- withdraw: Unit retreats from current position
- resupply: Unit receives supplies
- hold: Unit maintains current position

Route preferences:
- fastest: Quickest route regardless of cover
- covered: Route providing maximum concealment
- avoid_enemy: Route avoiding known enemy positions

Rules of engagement:
- weapons_free: Engage any identified enemy
- weapons_hold: Only fire in self-defense
- weapons_tight: Fire only at designated targets

When parsing, extract:
1. Which units receive the order (target_units)
2. What action to take (order_type)
3. The objective (position, enemy unit, or zone)
4. Any constraints (route, ROE, timing)

Always respond with valid JSON in this format:
{
    "success": true/false,
    "order": {
        "issuer": "commander",
        "target_units": ["unit_id_1", "unit_id_2"],
        "order_type": "move|attack|defend|support|recon|withdraw|resupply|hold",
        "objective": {
            "type": "position|unit|zone",
            "coordinates": {"latitude": X, "longitude": Y},
            "target_unit_id": "enemy_unit_id",
            "zone_name": "zone name"
        },
        "constraints": {
            "route": "fastest|covered|avoid_enemy",
            "roe": "weapons_free|weapons_hold|weapons_tight",
            "timing_offset_hours": 0
        },
        "natural_language": "Original order text"
    },
    "confidence": 0.0-1.0,
    "ambiguities": ["List of unclear elements"],
    "assumptions": ["Assumptions made during parsing"]
}

If you cannot parse the order, set success=false and explain in ambiguities."""

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        model: str = "llama3.3:70b",
    ):
        self.ollama_host = ollama_host
        self.model = model
        self.http_client = httpx.AsyncClient(timeout=60.0)

        # Known unit patterns
        self.unit_patterns = [
            r"(\d+)(?:st|nd|rd|th)\s+(?:motor\s+rifle\s+)?(?:tank\s+)?battalion",
            r"(\d+)(?:st|nd|rd|th)\s+brigade",
            r"(\d+)(?:st|nd|rd|th)\s+division",
            r"recon(?:naissance)?\s+(?:squadron|company|platoon)",
            r"artillery\s+(?:regiment|battalion|battery)",
        ]

        # Order type patterns for quick classification
        self.order_patterns = {
            "attack": [r"attack", r"assault", r"seize", r"destroy", r"engage"],
            "defend": [r"defend", r"hold\s+(?:at|position)", r"block", r"deny"],
            "move": [r"move\s+to", r"advance\s+to", r"relocate", r"proceed\s+to"],
            "recon": [r"recon", r"scout", r"observe", r"surveillance"],
            "withdraw": [r"withdraw", r"retreat", r"fall\s+back", r"disengage"],
            "support": [r"support", r"fire\s+support", r"suppress", r"cover"],
        }

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()

    async def parse_order(
        self,
        text: str,
        available_units: Optional[list[dict]] = None,
        enemy_contacts: Optional[list[dict]] = None,
    ) -> dict:
        """
        Parse a natural language order into structured format.

        Args:
            text: Natural language order text
            available_units: List of available friendly units
            enemy_contacts: List of known enemy contacts

        Returns:
            Structured order dictionary
        """
        # Quick pre-processing to extract obvious elements
        preprocessed = self._preprocess(text)

        # Build context for LLM
        context = self._build_context(available_units, enemy_contacts)

        prompt = f"""Parse this military order into structured JSON format.

ORDER TEXT:
"{text}"

{context}

PRELIMINARY ANALYSIS:
{json.dumps(preprocessed, indent=2)}

Parse this order into the standard JSON format. If unit names in the order
match available units, use the exact unit IDs. If coordinates are mentioned,
extract them. If the order is ambiguous, list what needs clarification."""

        response = await self._call_ollama(prompt)

        try:
            result = json.loads(response)
            return self._validate_and_enhance(result, available_units, enemy_contacts)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            return self._extract_json(response, text)

    def _preprocess(self, text: str) -> dict:
        """Quick preprocessing to extract obvious elements"""
        text_lower = text.lower()

        # Detect order type
        detected_type = None
        for order_type, patterns in self.order_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    detected_type = order_type
                    break
            if detected_type:
                break

        # Extract coordinates if present
        coord_match = re.search(
            r'(\d+\.?\d*)\s*[,°]\s*(\d+\.?\d*)',
            text
        )
        coordinates = None
        if coord_match:
            try:
                coordinates = {
                    "latitude": float(coord_match.group(1)),
                    "longitude": float(coord_match.group(2)),
                }
            except ValueError:
                pass

        # Extract time references
        timing = None
        time_match = re.search(r'H\+(\d+)', text, re.IGNORECASE)
        if time_match:
            timing = int(time_match.group(1))

        # Detect ROE indicators
        roe = "weapons_free"  # default
        if re.search(r'weapons?\s+hold', text_lower):
            roe = "weapons_hold"
        elif re.search(r'weapons?\s+tight', text_lower):
            roe = "weapons_tight"

        # Detect route preference
        route = "fastest"  # default
        if re.search(r'cover|concealment|terrain', text_lower):
            route = "covered"
        elif re.search(r'avoid|bypass', text_lower):
            route = "avoid_enemy"

        return {
            "detected_type": detected_type,
            "coordinates": coordinates,
            "timing_offset": timing,
            "roe": roe,
            "route": route,
        }

    def _build_context(
        self,
        available_units: Optional[list[dict]],
        enemy_contacts: Optional[list[dict]],
    ) -> str:
        """Build context string for LLM"""
        lines = []

        if available_units:
            lines.append("AVAILABLE FRIENDLY UNITS:")
            for unit in available_units:
                pos = unit.get("position", {})
                lines.append(
                    f"  - {unit.get('id')}: {unit.get('name')} "
                    f"({unit.get('type')}) at "
                    f"({pos.get('latitude', 0):.4f}, {pos.get('longitude', 0):.4f})"
                )

        if enemy_contacts:
            lines.append("\nKNOWN ENEMY CONTACTS:")
            for contact in enemy_contacts:
                pos = contact.get("position", {})
                lines.append(
                    f"  - {contact.get('contact_id')}: "
                    f"{contact.get('estimated_type', 'unknown')} at "
                    f"({pos.get('latitude', 0):.4f}, {pos.get('longitude', 0):.4f})"
                )

        return "\n".join(lines) if lines else "No unit context available."

    def _validate_and_enhance(
        self,
        result: dict,
        available_units: Optional[list[dict]],
        enemy_contacts: Optional[list[dict]],
    ) -> dict:
        """Validate parsed result and enhance with available data"""
        if not result.get("success"):
            return result

        order = result.get("order", {})

        # Validate target units exist
        if available_units and order.get("target_units"):
            unit_ids = {u["id"] for u in available_units}
            valid_targets = [
                uid for uid in order["target_units"]
                if uid in unit_ids
            ]
            if not valid_targets:
                result["success"] = False
                result["ambiguities"] = result.get("ambiguities", []) + [
                    "Could not match any target units to available units"
                ]
            else:
                order["target_units"] = valid_targets

        # Validate enemy target exists
        obj = order.get("objective", {})
        if obj.get("type") == "unit" and enemy_contacts:
            contact_ids = {c["contact_id"] for c in enemy_contacts}
            if obj.get("target_unit_id") not in contact_ids:
                result["ambiguities"] = result.get("ambiguities", []) + [
                    f"Target unit '{obj.get('target_unit_id')}' not in known contacts"
                ]

        return result

    def _extract_json(self, response: str, original_text: str) -> dict:
        """Try to extract JSON from response text"""
        # Look for JSON block
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Return failure result
        return {
            "success": False,
            "order": {
                "natural_language": original_text,
            },
            "confidence": 0.0,
            "ambiguities": ["Failed to parse order - please rephrase"],
            "assumptions": [],
        }

    async def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API"""
        try:
            response = await self.http_client.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": self.SYSTEM_PROMPT,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # Lower temp for more deterministic parsing
                        "num_predict": 1000,
                    },
                },
            )
            response.raise_for_status()
            return response.json().get("response", "")

        except Exception as e:
            print(f"Error calling Ollama: {e}")
            return "{}"

    async def interactive_clarify(
        self,
        original_order: str,
        parsed_result: dict,
        clarification: str,
    ) -> dict:
        """
        Incorporate user clarification into order parsing.

        Args:
            original_order: Original order text
            parsed_result: Previous parsing result
            clarification: User's clarification

        Returns:
            Updated parsed order
        """
        prompt = f"""UPDATE ORDER PARSING WITH CLARIFICATION

ORIGINAL ORDER:
"{original_order}"

PREVIOUS PARSING:
{json.dumps(parsed_result, indent=2)}

USER CLARIFICATION:
"{clarification}"

Update the parsed order based on the clarification. Incorporate the new
information and resolve any ambiguities that the clarification addresses."""

        response = await self._call_ollama(prompt)

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return self._extract_json(response, original_order)


# Standalone test
async def test_parser():
    """Test the order parser"""
    parser = OrderParser()

    available_units = [
        {"id": "1bn", "name": "1st Battalion", "type": "mechanized",
         "position": {"latitude": 50.35, "longitude": 9.9}},
        {"id": "2bn", "name": "2nd Battalion", "type": "armor",
         "position": {"latitude": 50.38, "longitude": 9.85}},
    ]

    enemy_contacts = [
        {"contact_id": "enemy_1", "estimated_type": "armor",
         "position": {"latitude": 50.48, "longitude": 9.5}},
    ]

    test_orders = [
        "1st Battalion move to grid 50.4, 9.7 using covered routes",
        "All units attack enemy armor at 50.48, 9.5",
        "2nd Battalion defend current position, weapons hold",
        "Advance to contact along axis north",
    ]

    try:
        for order_text in test_orders:
            print(f"\nParsing: '{order_text}'")
            result = await parser.parse_order(
                order_text, available_units, enemy_contacts
            )
            print(json.dumps(result, indent=2))

    finally:
        await parser.close()


if __name__ == "__main__":
    asyncio.run(test_parser())
