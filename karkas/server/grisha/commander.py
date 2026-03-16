"""Grisha AI Commander - Autonomous decision-making for Red force"""
import asyncio
import json
import os
import sys
import time
from typing import Optional

import httpx

# Add parent path for Grisha imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from server.config import get_settings
from server.logging_config import get_logger, log_grisha_api_call, log_ollama_call, LOGGER_GRISHA

logger = get_logger(f"{LOGGER_GRISHA}.commander")


class GrishaCommander:
    """
    AI Commander using Grisha RAG system for military decision-making.

    The commander operates as an autonomous Red force leader, generating
    orders based on Soviet/Russian military doctrine retrieved from the
    knowledge base.
    """

    SYSTEM_PROMPT = """You are Colonel Viktor Petrov, a Soviet/Russian military commander
in a theater-level wargame simulation. You command Red forces and must make tactical
and operational decisions based on Russian military doctrine.

Your role:
1. Analyze the current situation (enemy positions, own forces, terrain)
2. Develop courses of action based on Russian military principles
3. Issue clear, doctrinally-sound orders to your subordinate units
4. Prioritize mass, tempo, and combined arms operations

When issuing orders, structure them as follows:
- Specify which units receive the order
- Define the objective (position, enemy unit, or zone)
- Set constraints (route preference, rules of engagement)
- Provide commander's intent

Respond in the following JSON format when issuing orders:
{
    "assessment": "Brief situation assessment",
    "intent": "Commander's intent statement",
    "orders": [
        {
            "target_units": ["unit_id_1", "unit_id_2"],
            "order_type": "move|attack|defend|support|recon",
            "objective": {
                "type": "position|unit|zone",
                "coordinates": {"latitude": X, "longitude": Y},
                "target_unit_id": "enemy_unit_id (if attacking unit)",
                "zone_name": "zone name (if zone objective)"
            },
            "constraints": {
                "route": "fastest|covered|avoid_enemy",
                "roe": "weapons_free|weapons_hold|weapons_tight"
            },
            "natural_language": "Plain language description of the order"
        }
    ],
    "priority_targets": ["enemy_unit_ids in priority order"],
    "main_effort": "Description of main effort"
}
"""

    def __init__(
        self,
        grisha_api_url: Optional[str] = None,
        ollama_host: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize the Grisha Commander.

        Args:
            grisha_api_url: Override Grisha API URL (default from settings/env)
            ollama_host: Override Ollama host URL (default from settings/env)
            model: Override LLM model name (default from settings/env)
        """
        settings = get_settings()
        self.grisha_api_url = grisha_api_url or settings.grisha.api_url
        self.ollama_host = ollama_host or settings.ollama.host
        self.model = model or settings.ollama.model
        self.http_client = httpx.AsyncClient(timeout=float(settings.ollama.timeout))
        self.context_history: list[dict] = []

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()

    async def query_doctrine(self, query: str) -> str:
        """Query Grisha knowledge base for doctrine"""
        start_time = time.perf_counter()
        try:
            logger.debug(f"Querying doctrine: {query[:100]}...")
            response = await self.http_client.get(
                f"{self.grisha_api_url}/search",
                params={"query": query, "n_results": 5},
            )
            response.raise_for_status()
            results = response.json()

            # Format context from search results
            context_parts = []
            for doc in results.get("documents", []):
                context_parts.append(doc.get("content", ""))

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            log_grisha_api_call("/search", elapsed_ms, success=True)
            logger.debug(f"Doctrine query returned {len(context_parts)} results in {elapsed_ms:.1f}ms")

            return "\n\n".join(context_parts)

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            log_grisha_api_call("/search", elapsed_ms, success=False, error=str(e))
            logger.error(f"Error querying Grisha: {e}", exc_info=True)
            return ""

    async def generate_orders(
        self,
        situation_report: str,
        own_forces: list[dict],
        enemy_contacts: list[dict],
        turn_number: int,
    ) -> dict:
        """
        Generate orders for the current turn.

        Args:
            situation_report: Text summary of current situation
            own_forces: List of own unit data
            enemy_contacts: List of detected enemy contacts
            turn_number: Current turn number

        Returns:
            Dictionary containing assessment and orders
        """
        logger.info(f"Generating orders for turn {turn_number} with {len(own_forces)} units, {len(enemy_contacts)} contacts")
        start_time = time.perf_counter()

        # Build situation context
        situation = self._build_situation_prompt(
            situation_report, own_forces, enemy_contacts, turn_number
        )

        # Query doctrine for relevant guidance
        doctrine_context = await self._get_relevant_doctrine(
            own_forces, enemy_contacts
        )

        # Build full prompt
        prompt = f"""CURRENT SITUATION (Turn {turn_number}):
{situation}

RELEVANT DOCTRINE:
{doctrine_context}

Based on the situation and doctrine, provide your assessment and orders.
Remember to follow Russian military principles: mass at decisive point,
maintain tempo, use combined arms, and exploit success.

Respond in JSON format as specified."""

        # Generate response using Ollama
        response = await self._call_ollama(prompt)

        # Parse response
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        try:
            orders = json.loads(response)
            self.context_history.append({
                "turn": turn_number,
                "orders": orders,
            })
            order_count = len(orders.get("orders", []))
            logger.info(f"Generated {order_count} orders for turn {turn_number} in {elapsed_ms:.1f}ms")
            return orders
        except json.JSONDecodeError:
            # Try to extract JSON from response
            logger.warning(f"Failed to parse JSON response, attempting extraction")
            return self._extract_json_from_response(response)

    async def _get_relevant_doctrine(
        self,
        own_forces: list[dict],
        enemy_contacts: list[dict],
    ) -> str:
        """Get relevant doctrine based on current situation"""
        # Determine situation type
        queries = []

        # Check force composition
        has_armor = any(u.get("type") == "armor" for u in own_forces)
        has_artillery = any(u.get("type") == "artillery" for u in own_forces)
        has_infantry = any(
            u.get("type") in ["infantry", "mechanized"] for u in own_forces
        )

        if has_armor and has_infantry:
            queries.append("combined arms offensive operations")
        elif has_armor:
            queries.append("tank battalion attack tactics")
        elif has_infantry:
            queries.append("motor rifle regiment offensive")

        if has_artillery:
            queries.append("artillery fire support coordination")

        # Check enemy situation
        enemy_defending = any(
            c.get("estimated_posture") == "defend" for c in enemy_contacts
        )
        if enemy_defending:
            queries.append("breakthrough operations against prepared defense")

        # Query doctrine
        doctrine_parts = []
        for query in queries[:3]:  # Limit queries
            context = await self.query_doctrine(query)
            if context:
                doctrine_parts.append(f"[{query}]\n{context}")

        return "\n\n".join(doctrine_parts) if doctrine_parts else "No specific doctrine retrieved."

    def _build_situation_prompt(
        self,
        situation_report: str,
        own_forces: list[dict],
        enemy_contacts: list[dict],
        turn_number: int,
    ) -> str:
        """Build situation description prompt"""
        lines = [situation_report, "", "OWN FORCES:"]

        for unit in own_forces:
            pos = unit.get("position", {})
            strength = unit.get("strength", {})
            strength_pct = (
                strength.get("personnel_current", 0) /
                max(strength.get("personnel_max", 1), 1) * 100
            )
            lines.append(
                f"  - {unit.get('name')} ({unit.get('echelon')} {unit.get('type')}) "
                f"at ({pos.get('latitude', 0):.4f}, {pos.get('longitude', 0):.4f}) "
                f"[{strength_pct:.0f}% strength, {unit.get('posture', 'unknown')}]"
            )

        lines.append("")
        lines.append("ENEMY CONTACTS:")

        if not enemy_contacts:
            lines.append("  No contacts reported")
        else:
            for contact in enemy_contacts:
                pos = contact.get("position", {})
                lines.append(
                    f"  - [{contact.get('confidence', 'unknown')}] "
                    f"{contact.get('estimated_type', 'unknown')} "
                    f"at ({pos.get('latitude', 0):.4f}, {pos.get('longitude', 0):.4f})"
                )

        return "\n".join(lines)

    async def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API for generation"""
        start_time = time.perf_counter()
        try:
            logger.debug(f"Calling Ollama model {self.model}")
            response = await self.http_client.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": self.SYSTEM_PROMPT,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 2000,
                    },
                },
            )
            response.raise_for_status()
            result = response.json()
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Log Ollama call metrics
            eval_count = result.get("eval_count", 0)
            log_ollama_call(self.model, elapsed_ms, tokens=eval_count, success=True)
            logger.debug(f"Ollama generated {eval_count} tokens in {elapsed_ms:.1f}ms")

            return result.get("response", "")

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            log_ollama_call(self.model, elapsed_ms, success=False, error=str(e))
            logger.error(f"Error calling Ollama: {e}", exc_info=True)
            return "{}"

    def _extract_json_from_response(self, response: str) -> dict:
        """Try to extract JSON from a response that may contain other text"""
        import re

        # Look for JSON block
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Return default structure
        return {
            "assessment": "Unable to parse response",
            "intent": "",
            "orders": [],
            "error": "Failed to parse AI response",
        }

    async def evaluate_turn_result(
        self,
        turn_result: dict,
        previous_orders: dict,
    ) -> str:
        """Evaluate turn results and provide assessment"""
        prompt = f"""TURN RESULT ANALYSIS

Previous Orders:
{json.dumps(previous_orders, indent=2)}

Turn Results:
{json.dumps(turn_result, indent=2)}

Analyze the results of your orders. Consider:
1. Were objectives achieved?
2. What were the casualties?
3. How did the enemy react?
4. What adjustments are needed for next turn?

Provide a brief after-action assessment."""

        response = await self._call_ollama(prompt)
        return response


# Standalone test
async def test_commander():
    """Test the commander with sample data"""
    from server.logging_config import setup_logging
    setup_logging(level="DEBUG")

    commander = GrishaCommander()
    logger.info("Starting commander test")

    situation = "Red forces advancing toward Frankfurt. Blue forces defending in depth."

    own_forces = [
        {
            "id": "red_1bn",
            "name": "1st Motor Rifle Battalion",
            "type": "mechanized",
            "echelon": "battalion",
            "position": {"latitude": 50.45, "longitude": 9.45},
            "posture": "attack",
            "strength": {"personnel_current": 500, "personnel_max": 600},
        },
        {
            "id": "red_tank",
            "name": "1st Tank Battalion",
            "type": "armor",
            "echelon": "battalion",
            "position": {"latitude": 50.48, "longitude": 9.48},
            "posture": "attack",
            "strength": {"personnel_current": 300, "personnel_max": 350},
        },
    ]

    enemy_contacts = [
        {
            "contact_id": "contact_1",
            "confidence": "probable",
            "estimated_type": "mechanized",
            "position": {"latitude": 50.35, "longitude": 9.8},
        },
    ]

    try:
        orders = await commander.generate_orders(
            situation, own_forces, enemy_contacts, turn_number=1
        )
        logger.info(f"Generated Orders:\n{json.dumps(orders, indent=2)}")
    finally:
        await commander.close()


if __name__ == "__main__":
    asyncio.run(test_commander())
