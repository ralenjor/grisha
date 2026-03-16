"""Grisha AI Advisor - Advisory support for Blue force human player"""
import asyncio
import json
import os
import sys
import time
from typing import Optional

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from server.logging_config import get_logger, log_grisha_api_call, log_ollama_call, LOGGER_GRISHA

logger = get_logger(f"{LOGGER_GRISHA}.advisor")


class GrishaAdvisor:
    """
    AI Advisor using Grisha RAG system for tactical/operational advice.

    The advisor assists the human Blue force commander by:
    - Analyzing enemy dispositions and likely courses of action
    - Suggesting defensive positions and force deployments
    - Providing doctrinal guidance on NATO operations
    - Warning of potential threats and opportunities
    """

    SYSTEM_PROMPT = """You are Major Sarah Mitchell, a NATO military advisor in a
theater-level wargame simulation. You advise the Blue force commander (human player)
on tactical and operational decisions.

Your role:
1. Analyze enemy (Red) dispositions and predict their intentions
2. Recommend courses of action based on NATO doctrine
3. Identify threats and opportunities
4. Provide clear, actionable advice

When providing advice:
- Be concise and professional
- Reference relevant doctrine when applicable
- Highlight critical information and time-sensitive issues
- Present options with pros/cons rather than single solutions

Focus on:
- Defensive operations and economy of force
- Combined arms integration
- Intelligence and reconnaissance
- Logistics and sustainment

Remember: You are an ADVISOR. Present analysis and recommendations,
but the human commander makes final decisions."""

    def __init__(
        self,
        grisha_api_url: str = "http://localhost:8000",
        ollama_host: str = "http://localhost:11434",
        model: str = "llama3.3:70b",
    ):
        self.grisha_api_url = grisha_api_url
        self.ollama_host = ollama_host
        self.model = model
        self.http_client = httpx.AsyncClient(timeout=120.0)

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

    async def analyze_enemy(
        self,
        enemy_contacts: list[dict],
        own_forces: list[dict],
        terrain_info: Optional[str] = None,
    ) -> dict:
        """
        Analyze enemy dispositions and predict intentions.

        Returns:
            Dictionary with enemy analysis and predicted COAs
        """
        logger.info(f"Analyzing {len(enemy_contacts)} enemy contacts")
        start_time = time.perf_counter()

        # Query relevant doctrine about enemy tactics
        doctrine_context = await self.query_doctrine(
            "Soviet Russian offensive tactics motor rifle division"
        )

        prompt = f"""ENEMY ANALYSIS REQUEST

DETECTED ENEMY CONTACTS:
{json.dumps(enemy_contacts, indent=2)}

OWN FORCE POSITIONS:
{json.dumps(own_forces, indent=2)}

RELEVANT ENEMY DOCTRINE:
{doctrine_context}

{f"TERRAIN: {terrain_info}" if terrain_info else ""}

Analyze the enemy situation and provide:
1. Assessment of enemy strength and composition
2. Most likely course of action (MLCOA)
3. Most dangerous course of action (MDCOA)
4. Key indicators to watch for
5. Recommended priority intelligence requirements (PIR)

Format your response as JSON:
{{
    "strength_assessment": "Assessment of enemy strength",
    "composition": "Assessment of enemy force composition",
    "mlcoa": {{
        "description": "Most likely course of action",
        "indicators": ["indicator 1", "indicator 2"],
        "timeline": "Expected timeline"
    }},
    "mdcoa": {{
        "description": "Most dangerous course of action",
        "indicators": ["indicator 1", "indicator 2"],
        "timeline": "Expected timeline"
    }},
    "pir": ["Priority intelligence requirement 1", "PIR 2"],
    "watch_areas": ["Geographic areas to monitor"]
}}"""

        response = await self._call_ollama(prompt)

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"raw_analysis": response}

    async def recommend_defense(
        self,
        own_forces: list[dict],
        enemy_contacts: list[dict],
        terrain_info: Optional[str] = None,
        objectives: Optional[list[str]] = None,
    ) -> dict:
        """
        Recommend defensive positions and dispositions.

        Returns:
            Dictionary with defensive recommendations
        """
        doctrine_context = await self.query_doctrine(
            "NATO defensive operations prepared positions"
        )

        prompt = f"""DEFENSIVE PLANNING REQUEST

OWN FORCES:
{json.dumps(own_forces, indent=2)}

ENEMY THREAT:
{json.dumps(enemy_contacts, indent=2)}

{f"TERRAIN: {terrain_info}" if terrain_info else ""}
{f"OBJECTIVES TO DEFEND: {objectives}" if objectives else ""}

RELEVANT DOCTRINE:
{doctrine_context}

Recommend a defensive plan including:
1. Main defensive line positions
2. Reserve positioning
3. Engagement areas
4. Obstacles and barriers
5. Fire support plan
6. Counterattack options

Format as JSON:
{{
    "concept": "Overall defensive concept",
    "main_line": [
        {{
            "unit": "unit_id",
            "position": {{"latitude": X, "longitude": Y}},
            "sector": "Description of sector",
            "task": "Defend/Delay/Block"
        }}
    ],
    "reserve": {{
        "units": ["unit_ids"],
        "position": {{"latitude": X, "longitude": Y}},
        "counterattack_triggers": ["Trigger conditions"]
    }},
    "engagement_areas": [
        {{
            "name": "EA name",
            "polygon": "Description of area",
            "target_priority": "Priority targets"
        }}
    ],
    "risks": ["Identified risks"],
    "critical_events": ["Events requiring commander decision"]
}}"""

        response = await self._call_ollama(prompt)

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"raw_recommendation": response}

    async def assess_situation(
        self,
        situation_report: str,
        own_forces: list[dict],
        enemy_contacts: list[dict],
        turn_number: int,
    ) -> str:
        """
        Provide a staff-style situation assessment.

        Returns:
            Narrative assessment text
        """
        prompt = f"""SITUATION ASSESSMENT - TURN {turn_number}

CURRENT SITUATION:
{situation_report}

OWN FORCES:
{self._format_forces(own_forces)}

ENEMY CONTACTS:
{self._format_contacts(enemy_contacts)}

Provide a professional military staff assessment covering:
1. Current situation summary
2. Enemy activity and assessment
3. Own force status and readiness
4. Key decision points
5. Recommended actions

Be concise and actionable. Highlight critical information."""

        return await self._call_ollama(prompt)

    async def answer_question(self, question: str, context: Optional[dict] = None) -> str:
        """
        Answer a commander's question using doctrine knowledge.

        Args:
            question: The commander's question
            context: Optional current game context

        Returns:
            Advisory response
        """
        # Query doctrine for relevant information
        doctrine_context = await self.query_doctrine(question)

        prompt = f"""COMMANDER'S QUESTION:
{question}

{f"CURRENT CONTEXT: {json.dumps(context)}" if context else ""}

RELEVANT DOCTRINE:
{doctrine_context}

Provide a clear, professional answer to the commander's question.
Reference doctrine when relevant. Be concise and actionable."""

        return await self._call_ollama(prompt)

    async def evaluate_order(self, proposed_order: dict, situation: dict) -> dict:
        """
        Evaluate a proposed order and provide feedback.

        Returns:
            Dictionary with evaluation and suggestions
        """
        prompt = f"""ORDER EVALUATION REQUEST

PROPOSED ORDER:
{json.dumps(proposed_order, indent=2)}

CURRENT SITUATION:
{json.dumps(situation, indent=2)}

Evaluate this order considering:
1. Doctrinal soundness
2. Feasibility given current forces
3. Risk assessment
4. Potential enemy reactions
5. Logistics implications

Format response as JSON:
{{
    "assessment": "overall|minor_concerns|major_concerns",
    "doctrinal_compliance": "Assessment of doctrinal soundness",
    "feasibility": "Assessment of execution feasibility",
    "risks": ["Identified risks"],
    "enemy_reaction": "Predicted enemy response",
    "suggestions": ["Suggested modifications"],
    "recommendation": "approve|modify|reconsider"
}}"""

        response = await self._call_ollama(prompt)

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"raw_evaluation": response}

    def _format_forces(self, forces: list[dict]) -> str:
        """Format force list for prompt"""
        lines = []
        for unit in forces:
            pos = unit.get("position", {})
            strength = unit.get("strength", {})
            pct = (
                strength.get("personnel_current", 0) /
                max(strength.get("personnel_max", 1), 1) * 100
            )
            lines.append(
                f"  - {unit.get('name')} ({unit.get('type')}) "
                f"at ({pos.get('latitude', 0):.4f}, {pos.get('longitude', 0):.4f}) "
                f"[{pct:.0f}% strength]"
            )
        return "\n".join(lines) if lines else "  No forces reported"

    def _format_contacts(self, contacts: list[dict]) -> str:
        """Format contact list for prompt"""
        lines = []
        for contact in contacts:
            pos = contact.get("position", {})
            lines.append(
                f"  - [{contact.get('confidence', 'unknown')}] "
                f"{contact.get('estimated_type', 'unknown')} "
                f"at ({pos.get('latitude', 0):.4f}, {pos.get('longitude', 0):.4f})"
            )
        return "\n".join(lines) if lines else "  No contacts reported"

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
            return "Error: Unable to generate response"


# Standalone test
async def test_advisor():
    """Test the advisor with sample data"""
    from server.logging_config import setup_logging
    setup_logging(level="DEBUG")

    advisor = GrishaAdvisor()
    logger.info("Starting advisor test")

    own_forces = [
        {
            "id": "blue_1bde",
            "name": "1st Brigade Combat Team",
            "type": "mechanized",
            "position": {"latitude": 50.35, "longitude": 9.95},
            "posture": "defend",
            "strength": {"personnel_current": 3500, "personnel_max": 4000},
        },
    ]

    enemy_contacts = [
        {
            "contact_id": "contact_1",
            "confidence": "probable",
            "estimated_type": "armor",
            "position": {"latitude": 50.48, "longitude": 9.48},
        },
        {
            "contact_id": "contact_2",
            "confidence": "suspected",
            "estimated_type": "mechanized",
            "position": {"latitude": 50.45, "longitude": 9.45},
        },
    ]

    try:
        # Test enemy analysis
        logger.info("Analyzing enemy...")
        analysis = await advisor.analyze_enemy(enemy_contacts, own_forces)
        logger.info(f"Enemy Analysis:\n{json.dumps(analysis, indent=2)}")

        # Test question answering
        logger.info("Asking question...")
        answer = await advisor.answer_question(
            "What is the best way to defend against a Soviet tank attack?"
        )
        logger.info(f"Answer:\n{answer}")

    finally:
        await advisor.close()


if __name__ == "__main__":
    asyncio.run(test_advisor())
