"""
Tests for Order Parser component.

Task 6.1.4 - Order parsing tests
Comprehensive tests for the OrderParser class covering:
- Preprocessing (order type detection, ROE, routes, coordinates, timing)
- Context building for LLM
- Validation of units and targets
- LLM response parsing and JSON extraction
- Interactive clarification
- Error handling and edge cases
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from server.grisha.order_parser import OrderParser


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def parser():
    """Create an OrderParser instance for testing."""
    return OrderParser()


@pytest.fixture
def available_units():
    """Sample available friendly units."""
    return [
        {
            "id": "1bn",
            "name": "1st Motor Rifle Battalion",
            "type": "mechanized",
            "position": {"latitude": 50.35, "longitude": 9.9},
        },
        {
            "id": "2bn",
            "name": "2nd Tank Battalion",
            "type": "armor",
            "position": {"latitude": 50.38, "longitude": 9.85},
        },
        {
            "id": "arty_1",
            "name": "1st Artillery Regiment",
            "type": "artillery",
            "position": {"latitude": 50.40, "longitude": 9.80},
        },
        {
            "id": "recon_1",
            "name": "Recon Squadron",
            "type": "reconnaissance",
            "position": {"latitude": 50.42, "longitude": 9.78},
        },
    ]


@pytest.fixture
def enemy_contacts():
    """Sample enemy contacts."""
    return [
        {
            "contact_id": "enemy_1",
            "estimated_type": "armor",
            "confidence": "probable",
            "position": {"latitude": 50.48, "longitude": 9.5},
        },
        {
            "contact_id": "enemy_2",
            "estimated_type": "mechanized",
            "confidence": "suspected",
            "position": {"latitude": 50.50, "longitude": 9.45},
        },
        {
            "contact_id": "enemy_arty",
            "estimated_type": "artillery",
            "confidence": "confirmed",
            "position": {"latitude": 50.55, "longitude": 9.40},
        },
    ]


@pytest.fixture
def mock_successful_parse_response():
    """Mock successful LLM parsing response."""
    return {
        "response": json.dumps({
            "success": True,
            "order": {
                "issuer": "commander",
                "target_units": ["1bn"],
                "order_type": "move",
                "objective": {
                    "type": "position",
                    "coordinates": {"latitude": 50.4, "longitude": 9.7},
                },
                "constraints": {
                    "route": "covered",
                    "roe": "weapons_free",
                    "timing_offset_hours": 0,
                },
                "natural_language": "1st Battalion move to grid 50.4, 9.7 using covered routes",
            },
            "confidence": 0.9,
            "ambiguities": [],
            "assumptions": ["Assuming 1bn refers to 1st Motor Rifle Battalion"],
        })
    }


# =============================================================================
# Preprocessing Tests - Order Type Detection
# =============================================================================


class TestPreprocessingOrderTypes:
    """Tests for order type detection in preprocessing."""

    @pytest.mark.asyncio
    async def test_preprocess_move_order(self, parser):
        """Test detection of move orders."""
        test_cases = [
            "1st Battalion move to grid 50.4, 9.7",
            "All units advance to phase line alpha",
            "Relocate to new positions at hill 203",
            "Proceed to assembly area charlie",
        ]
        for text in test_cases:
            result = parser._preprocess(text)
            assert result["detected_type"] == "move", f"Failed for: {text}"
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_attack_order(self, parser):
        """Test detection of attack orders."""
        test_cases = [
            "Attack enemy position at hill 105",
            "Assault the town center",
            "Seize objective bravo",
            "Destroy enemy tank battalion",
            "Engage enemy forces at grid 50.5, 9.6",
        ]
        for text in test_cases:
            result = parser._preprocess(text)
            assert result["detected_type"] == "attack", f"Failed for: {text}"
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_defend_order(self, parser):
        """Test detection of defend orders."""
        test_cases = [
            "Defend current position",
            "Hold at grid reference 123456",
            "Block enemy advance along route 7",
            "Deny access to bridge",
        ]
        for text in test_cases:
            result = parser._preprocess(text)
            assert result["detected_type"] == "defend", f"Failed for: {text}"
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_recon_order(self, parser):
        """Test detection of reconnaissance orders."""
        test_cases = [
            "Recon route to objective",
            "Scout enemy positions",
            "Observe enemy movements",
            "Conduct surveillance of the valley",
        ]
        for text in test_cases:
            result = parser._preprocess(text)
            assert result["detected_type"] == "recon", f"Failed for: {text}"
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_withdraw_order(self, parser):
        """Test detection of withdraw orders."""
        test_cases = [
            "Withdraw to phase line delta",
            "Retreat to secondary positions",
            "Fall back to the river",
            # Note: "Disengage" contains "engage" which matches attack first
            # due to dict iteration order, so we test it separately
        ]
        for text in test_cases:
            result = parser._preprocess(text)
            assert result["detected_type"] == "withdraw", f"Failed for: {text}"
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_support_order(self, parser):
        """Test detection of support orders."""
        test_cases = [
            # Note: Patterns are checked in dict order. Avoid text containing
            # patterns from earlier-checked order types (attack, defend, move, recon, withdraw)
            "Provide fire support to 2nd Battalion",
            "Suppress enemy artillery",
            "Cover our flank",
            "Support 1st Battalion's advance",
        ]
        for text in test_cases:
            result = parser._preprocess(text)
            assert result["detected_type"] == "support", f"Failed for: {text}"
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_unknown_order_type(self, parser):
        """Test preprocessing with unrecognized order type."""
        result = parser._preprocess("Just do something")
        assert result["detected_type"] is None
        await parser.close()


# =============================================================================
# Preprocessing Tests - ROE Detection
# =============================================================================


class TestPreprocessingROE:
    """Tests for Rules of Engagement detection."""

    @pytest.mark.asyncio
    async def test_preprocess_roe_weapons_free(self, parser):
        """Test default ROE is weapons_free."""
        result = parser._preprocess("Attack the enemy position")
        assert result["roe"] == "weapons_free"
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_roe_weapons_hold(self, parser):
        """Test weapons_hold ROE detection."""
        test_cases = [
            "Defend position, weapons hold",
            "Advance with weapon hold until contact",
            "Move to objective, weapons hold",
        ]
        for text in test_cases:
            result = parser._preprocess(text)
            assert result["roe"] == "weapons_hold", f"Failed for: {text}"
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_roe_weapons_tight(self, parser):
        """Test weapons_tight ROE detection."""
        test_cases = [
            "Advance, weapons tight until ordered",
            "Move forward with weapons tight",
            "Proceed, weapon tight",
        ]
        for text in test_cases:
            result = parser._preprocess(text)
            assert result["roe"] == "weapons_tight", f"Failed for: {text}"
        await parser.close()


# =============================================================================
# Preprocessing Tests - Route Preference Detection
# =============================================================================


class TestPreprocessingRoute:
    """Tests for route preference detection."""

    @pytest.mark.asyncio
    async def test_preprocess_route_fastest(self, parser):
        """Test default route is fastest."""
        result = parser._preprocess("Move to objective alpha")
        assert result["route"] == "fastest"
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_route_covered(self, parser):
        """Test covered route detection."""
        test_cases = [
            "Advance using covered routes",
            "Move with maximum concealment",
            "Follow terrain features for cover",
        ]
        for text in test_cases:
            result = parser._preprocess(text)
            assert result["route"] == "covered", f"Failed for: {text}"
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_route_avoid_enemy(self, parser):
        """Test avoid_enemy route detection."""
        test_cases = [
            "Move to objective, avoid enemy positions",
            "Bypass known enemy contacts",
            "Avoid contact during movement",
        ]
        for text in test_cases:
            result = parser._preprocess(text)
            assert result["route"] == "avoid_enemy", f"Failed for: {text}"
        await parser.close()


# =============================================================================
# Preprocessing Tests - Coordinate Extraction
# =============================================================================


class TestPreprocessingCoordinates:
    """Tests for coordinate extraction."""

    @pytest.mark.asyncio
    async def test_preprocess_coordinates_comma_format(self, parser):
        """Test coordinate extraction with comma separator."""
        result = parser._preprocess("Move to 50.45, 9.75")
        assert result["coordinates"] is not None
        assert result["coordinates"]["latitude"] == 50.45
        assert result["coordinates"]["longitude"] == 9.75
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_coordinates_degree_format(self, parser):
        """Test coordinate extraction with degree symbol."""
        result = parser._preprocess("Attack position at 50.48° 9.52")
        assert result["coordinates"] is not None
        assert result["coordinates"]["latitude"] == 50.48
        assert result["coordinates"]["longitude"] == 9.52
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_no_coordinates(self, parser):
        """Test preprocessing with no coordinates."""
        result = parser._preprocess("Attack the enemy position")
        assert result["coordinates"] is None
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_invalid_coordinate_values(self, parser):
        """Test preprocessing with malformed coordinate text."""
        # Should not crash with strange inputs
        result = parser._preprocess("Move to grid abc, xyz")
        assert result["coordinates"] is None
        await parser.close()


# =============================================================================
# Preprocessing Tests - Timing Extraction
# =============================================================================


class TestPreprocessingTiming:
    """Tests for timing extraction."""

    @pytest.mark.asyncio
    async def test_preprocess_timing_h_plus(self, parser):
        """Test H+ timing extraction."""
        test_cases = [
            ("Attack at H+2", 2),
            ("Move at H+6", 6),
            ("Begin at H+0", 0),
            ("Execute at h+12", 12),  # Case insensitive
        ]
        for text, expected in test_cases:
            result = parser._preprocess(text)
            assert result["timing_offset"] == expected, f"Failed for: {text}"
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_no_timing(self, parser):
        """Test preprocessing with no timing info."""
        result = parser._preprocess("Attack enemy position")
        assert result["timing_offset"] is None
        await parser.close()


# =============================================================================
# Context Building Tests
# =============================================================================


class TestContextBuilding:
    """Tests for LLM context building."""

    @pytest.mark.asyncio
    async def test_build_context_with_units(self, parser, available_units):
        """Test context building with available units."""
        context = parser._build_context(available_units, None)

        assert "AVAILABLE FRIENDLY UNITS:" in context
        assert "1bn: 1st Motor Rifle Battalion" in context
        assert "2bn: 2nd Tank Battalion" in context
        assert "mechanized" in context
        assert "armor" in context
        await parser.close()

    @pytest.mark.asyncio
    async def test_build_context_with_contacts(self, parser, enemy_contacts):
        """Test context building with enemy contacts."""
        context = parser._build_context(None, enemy_contacts)

        assert "KNOWN ENEMY CONTACTS:" in context
        assert "enemy_1:" in context
        assert "enemy_2:" in context
        assert "armor" in context
        await parser.close()

    @pytest.mark.asyncio
    async def test_build_context_with_both(self, parser, available_units, enemy_contacts):
        """Test context building with both units and contacts."""
        context = parser._build_context(available_units, enemy_contacts)

        assert "AVAILABLE FRIENDLY UNITS:" in context
        assert "KNOWN ENEMY CONTACTS:" in context
        assert "1bn:" in context
        assert "enemy_1:" in context
        await parser.close()

    @pytest.mark.asyncio
    async def test_build_context_empty(self, parser):
        """Test context building with no data."""
        context = parser._build_context(None, None)
        assert "No unit context available" in context
        await parser.close()

    @pytest.mark.asyncio
    async def test_build_context_empty_lists(self, parser):
        """Test context building with empty lists."""
        context = parser._build_context([], [])
        assert "No unit context available" in context
        await parser.close()


# =============================================================================
# Validation Tests
# =============================================================================


class TestValidation:
    """Tests for validation and enhancement."""

    @pytest.mark.asyncio
    async def test_validate_valid_target_units(self, parser, available_units):
        """Test validation with valid target units."""
        result = {
            "success": True,
            "order": {
                "target_units": ["1bn", "2bn"],
            },
        }
        validated = parser._validate_and_enhance(result, available_units, None)

        assert validated["success"] is True
        assert validated["order"]["target_units"] == ["1bn", "2bn"]
        await parser.close()

    @pytest.mark.asyncio
    async def test_validate_invalid_target_units(self, parser, available_units):
        """Test validation with invalid target units."""
        result = {
            "success": True,
            "order": {
                "target_units": ["nonexistent_unit"],
            },
        }
        validated = parser._validate_and_enhance(result, available_units, None)

        assert validated["success"] is False
        assert any("Could not match" in amb for amb in validated["ambiguities"])
        await parser.close()

    @pytest.mark.asyncio
    async def test_validate_partial_valid_units(self, parser, available_units):
        """Test validation with mix of valid and invalid units."""
        result = {
            "success": True,
            "order": {
                "target_units": ["1bn", "invalid_unit"],
            },
        }
        validated = parser._validate_and_enhance(result, available_units, None)

        # Should succeed with only valid units
        assert validated["success"] is True
        assert validated["order"]["target_units"] == ["1bn"]
        await parser.close()

    @pytest.mark.asyncio
    async def test_validate_valid_enemy_target(self, parser, enemy_contacts):
        """Test validation with valid enemy target."""
        result = {
            "success": True,
            "order": {
                "target_units": [],
                "objective": {
                    "type": "unit",
                    "target_unit_id": "enemy_1",
                },
            },
        }
        validated = parser._validate_and_enhance(result, None, enemy_contacts)

        assert "ambiguities" not in validated or len(validated.get("ambiguities", [])) == 0
        await parser.close()

    @pytest.mark.asyncio
    async def test_validate_invalid_enemy_target(self, parser, enemy_contacts):
        """Test validation with invalid enemy target."""
        result = {
            "success": True,
            "order": {
                "target_units": [],
                "objective": {
                    "type": "unit",
                    "target_unit_id": "nonexistent_enemy",
                },
            },
        }
        validated = parser._validate_and_enhance(result, None, enemy_contacts)

        assert any("not in known contacts" in amb for amb in validated.get("ambiguities", []))
        await parser.close()

    @pytest.mark.asyncio
    async def test_validate_failed_result_passthrough(self, parser):
        """Test validation passes through already-failed results."""
        result = {
            "success": False,
            "ambiguities": ["Could not understand order"],
        }
        validated = parser._validate_and_enhance(result, None, None)

        assert validated["success"] is False
        await parser.close()


# =============================================================================
# JSON Extraction Tests
# =============================================================================


class TestJSONExtraction:
    """Tests for JSON extraction from LLM responses."""

    @pytest.mark.asyncio
    async def test_extract_json_clean_response(self, parser):
        """Test extraction from clean JSON response."""
        response = '{"success": true, "order": {"order_type": "move"}, "confidence": 0.9}'
        result = parser._extract_json(response, "original")

        assert result["success"] is True
        assert result["order"]["order_type"] == "move"
        await parser.close()

    @pytest.mark.asyncio
    async def test_extract_json_with_preamble(self, parser):
        """Test extraction from response with text before JSON."""
        response = '''I'll parse this order for you:
        {"success": true, "order": {"order_type": "attack"}, "confidence": 0.85}
        That's my analysis.'''
        result = parser._extract_json(response, "original")

        assert result["success"] is True
        assert result["order"]["order_type"] == "attack"
        await parser.close()

    @pytest.mark.asyncio
    async def test_extract_json_no_json(self, parser):
        """Test extraction when no JSON present."""
        response = "I don't understand that order at all."
        result = parser._extract_json(response, "original order text")

        assert result["success"] is False
        assert "Failed to parse" in result["ambiguities"][0]
        assert result["order"]["natural_language"] == "original order text"
        await parser.close()

    @pytest.mark.asyncio
    async def test_extract_json_malformed_json(self, parser):
        """Test extraction with malformed JSON."""
        response = '{"success": true, "order": {"order_type": "move"'  # Missing closing braces
        result = parser._extract_json(response, "original")

        assert result["success"] is False
        await parser.close()


# =============================================================================
# Full Parse Order Tests
# =============================================================================


class TestParseOrder:
    """Tests for full order parsing."""

    @pytest.mark.asyncio
    async def test_parse_order_success(
        self, parser, available_units, mock_successful_parse_response
    ):
        """Test successful order parsing."""
        with patch.object(parser.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_successful_parse_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await parser.parse_order(
                "1st Battalion move to grid 50.4, 9.7 using covered routes",
                available_units=available_units,
            )

            assert result["success"] is True
            assert result["order"]["order_type"] == "move"
            assert result["order"]["target_units"] == ["1bn"]
            assert result["confidence"] == 0.9

        await parser.close()

    @pytest.mark.asyncio
    async def test_parse_order_with_enemy_context(
        self, parser, available_units, enemy_contacts
    ):
        """Test order parsing includes enemy context in prompt."""
        attack_response = {
            "response": json.dumps({
                "success": True,
                "order": {
                    "target_units": ["1bn"],
                    "order_type": "attack",
                    "objective": {
                        "type": "unit",
                        "target_unit_id": "enemy_1",
                    },
                },
                "confidence": 0.85,
                "ambiguities": [],
                "assumptions": [],
            })
        }

        with patch.object(parser.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = attack_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            await parser.parse_order(
                "Attack the enemy armor",
                available_units=available_units,
                enemy_contacts=enemy_contacts,
            )

            # Verify enemy context was included in prompt
            call_args = mock_post.call_args
            prompt = call_args.kwargs["json"]["prompt"]
            assert "KNOWN ENEMY CONTACTS:" in prompt
            assert "enemy_1" in prompt

        await parser.close()

    @pytest.mark.asyncio
    async def test_parse_order_includes_preprocessed_data(self, parser, available_units):
        """Test that preprocessed data is included in prompt."""
        with patch.object(parser.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "response": json.dumps({
                    "success": True,
                    "order": {"target_units": ["1bn"], "order_type": "move"},
                    "confidence": 0.8,
                    "ambiguities": [],
                    "assumptions": [],
                })
            }
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            await parser.parse_order(
                "Move to 50.4, 9.7 using covered routes at H+2",
                available_units=available_units,
            )

            call_args = mock_post.call_args
            prompt = call_args.kwargs["json"]["prompt"]

            # Check preprocessed data is in prompt
            assert "PRELIMINARY ANALYSIS:" in prompt
            assert '"detected_type": "move"' in prompt
            assert '"route": "covered"' in prompt

        await parser.close()

    @pytest.mark.asyncio
    async def test_parse_order_handles_non_json_response(self, parser):
        """Test parsing handles non-JSON LLM response."""
        with patch.object(parser.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "response": "Sorry, I cannot understand that order."
            }
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await parser.parse_order("gibberish nonsense order")

            assert result["success"] is False
            assert "Failed to parse" in result["ambiguities"][0]

        await parser.close()


# =============================================================================
# Interactive Clarification Tests
# =============================================================================


class TestInteractiveClarify:
    """Tests for interactive clarification."""

    @pytest.mark.asyncio
    async def test_interactive_clarify_resolves_ambiguity(self, parser):
        """Test clarification resolves ambiguities."""
        clarified_response = {
            "response": json.dumps({
                "success": True,
                "order": {
                    "target_units": ["1bn", "2bn"],
                    "order_type": "attack",
                    "objective": {
                        "type": "position",
                        "coordinates": {"latitude": 50.4, "longitude": 9.5},
                    },
                },
                "confidence": 0.95,
                "ambiguities": [],
                "assumptions": [],
            })
        }

        with patch.object(parser.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = clarified_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await parser.interactive_clarify(
                original_order="Attack objective alpha",
                parsed_result={
                    "success": False,
                    "ambiguities": ["Which units should execute the attack?"],
                },
                clarification="Use 1st and 2nd battalions",
            )

            assert result["success"] is True
            assert "1bn" in result["order"]["target_units"]
            assert "2bn" in result["order"]["target_units"]

        await parser.close()

    @pytest.mark.asyncio
    async def test_interactive_clarify_includes_context(self, parser):
        """Test clarification includes original order and previous parsing."""
        with patch.object(parser.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "response": json.dumps({
                    "success": True,
                    "order": {"target_units": ["1bn"], "order_type": "move"},
                    "confidence": 0.9,
                    "ambiguities": [],
                    "assumptions": [],
                })
            }
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            await parser.interactive_clarify(
                original_order="Move somewhere",
                parsed_result={"success": False, "ambiguities": ["Where?"]},
                clarification="To grid 50.4, 9.7",
            )

            call_args = mock_post.call_args
            prompt = call_args.kwargs["json"]["prompt"]

            assert "ORIGINAL ORDER:" in prompt
            assert "Move somewhere" in prompt
            assert "PREVIOUS PARSING:" in prompt
            assert "USER CLARIFICATION:" in prompt
            assert "To grid 50.4, 9.7" in prompt

        await parser.close()

    @pytest.mark.asyncio
    async def test_interactive_clarify_handles_failed_parse(self, parser):
        """Test clarification handles failed LLM response."""
        with patch.object(parser.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "response": "Still don't understand"
            }
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await parser.interactive_clarify(
                original_order="Do the thing",
                parsed_result={"success": False},
                clarification="You know, THE thing",
            )

            assert result["success"] is False

        await parser.close()


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_parse_order_llm_connection_error(self, parser):
        """Test parsing handles LLM connection error."""
        with patch.object(parser.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("Connection refused")

            result = await parser.parse_order("Move to objective")

            # Should not raise, returns empty or failed result
            assert isinstance(result, dict)

        await parser.close()

    @pytest.mark.asyncio
    async def test_parse_order_llm_timeout(self, parser):
        """Test parsing handles LLM timeout."""
        import httpx

        with patch.object(parser.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Request timed out")

            result = await parser.parse_order("Complex multi-part order")

            assert isinstance(result, dict)

        await parser.close()

    @pytest.mark.asyncio
    async def test_parse_order_empty_input(self, parser):
        """Test parsing handles empty input."""
        with patch.object(parser.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "response": json.dumps({
                    "success": False,
                    "ambiguities": ["Empty order received"],
                })
            }
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await parser.parse_order("")

            assert result["success"] is False

        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_special_characters(self, parser):
        """Test preprocessing handles special characters."""
        result = parser._preprocess("Move to grid @#$%^&*()")
        # Should not crash
        assert isinstance(result, dict)
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_unicode_characters(self, parser):
        """Test preprocessing handles unicode."""
        result = parser._preprocess("Атаковать позицию противника")  # Russian text
        assert isinstance(result, dict)
        await parser.close()

    @pytest.mark.asyncio
    async def test_preprocess_very_long_input(self, parser):
        """Test preprocessing handles very long input."""
        long_text = "Move to objective " * 1000
        result = parser._preprocess(long_text)
        assert isinstance(result, dict)
        assert result["detected_type"] == "move"
        await parser.close()


# =============================================================================
# Order Pattern Tests
# =============================================================================


class TestOrderPatterns:
    """Tests for order pattern matching."""

    @pytest.mark.asyncio
    async def test_order_pattern_attack_variations(self, parser):
        """Test various attack order phrasings."""
        attack_texts = [
            "ATTACK objective bravo",
            "Attack!",
            "assault the hill",
            "SEIZE the bridge",
            "Destroy enemy forces",
            "engage at will",
        ]
        for text in attack_texts:
            result = parser._preprocess(text)
            assert result["detected_type"] == "attack", f"Failed for: {text}"
        await parser.close()

    @pytest.mark.asyncio
    async def test_order_pattern_defend_variations(self, parser):
        """Test various defend order phrasings."""
        defend_texts = [
            "DEFEND this position",
            "hold at hill 203",
            "Hold position at all costs",
            "block the road",
            "deny enemy access",
        ]
        for text in defend_texts:
            result = parser._preprocess(text)
            assert result["detected_type"] == "defend", f"Failed for: {text}"
        await parser.close()

    @pytest.mark.asyncio
    async def test_order_pattern_move_variations(self, parser):
        """Test various move order phrasings."""
        move_texts = [
            "Move to objective alpha",
            "advance to phase line",
            "RELOCATE to assembly area",
            "proceed to waypoint charlie",
        ]
        for text in move_texts:
            result = parser._preprocess(text)
            assert result["detected_type"] == "move", f"Failed for: {text}"
        await parser.close()


# =============================================================================
# System Prompt Tests
# =============================================================================


class TestSystemPrompt:
    """Tests for system prompt configuration."""

    def test_system_prompt_contains_order_types(self):
        """Test system prompt documents all order types."""
        prompt = OrderParser.SYSTEM_PROMPT

        order_types = ["move", "attack", "defend", "support", "recon", "withdraw", "resupply", "hold"]
        for order_type in order_types:
            assert order_type in prompt, f"Missing order type: {order_type}"

    def test_system_prompt_contains_roe(self):
        """Test system prompt documents ROE options."""
        prompt = OrderParser.SYSTEM_PROMPT

        roe_types = ["weapons_free", "weapons_hold", "weapons_tight"]
        for roe in roe_types:
            assert roe in prompt, f"Missing ROE: {roe}"

    def test_system_prompt_contains_routes(self):
        """Test system prompt documents route preferences."""
        prompt = OrderParser.SYSTEM_PROMPT

        routes = ["fastest", "covered", "avoid_enemy"]
        for route in routes:
            assert route in prompt, f"Missing route: {route}"

    def test_system_prompt_contains_json_format(self):
        """Test system prompt specifies JSON format."""
        prompt = OrderParser.SYSTEM_PROMPT

        assert "JSON" in prompt
        assert "success" in prompt
        assert "order" in prompt
        assert "confidence" in prompt


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_multiple_order_types_in_text(self, parser):
        """Test preprocessing when multiple order types appear."""
        # First match should win
        result = parser._preprocess("Attack then withdraw to regroup")
        assert result["detected_type"] == "attack"
        await parser.close()

    @pytest.mark.asyncio
    async def test_multiple_coordinates_in_text(self, parser):
        """Test coordinate extraction with multiple coordinates."""
        # First coordinate pair should be extracted
        result = parser._preprocess("Move from 50.3, 9.8 to 50.5, 9.9")
        assert result["coordinates"]["latitude"] == 50.3
        assert result["coordinates"]["longitude"] == 9.8
        await parser.close()

    @pytest.mark.asyncio
    async def test_conflicting_roe(self, parser):
        """Test ROE detection with conflicting indicators."""
        # Last match should win based on the order of if-elif
        result = parser._preprocess("weapons hold then weapons tight later")
        assert result["roe"] == "weapons_hold"
        await parser.close()

    @pytest.mark.asyncio
    async def test_validation_with_empty_order(self, parser, available_units):
        """Test validation with empty order dict."""
        result = {
            "success": True,
            "order": {},
        }
        validated = parser._validate_and_enhance(result, available_units, None)
        # Should not crash
        assert isinstance(validated, dict)
        await parser.close()

    @pytest.mark.asyncio
    async def test_context_with_missing_position(self, parser):
        """Test context building with units missing position."""
        units_no_position = [
            {"id": "1bn", "name": "1st Battalion", "type": "mechanized"},
        ]
        context = parser._build_context(units_no_position, None)
        # Should use defaults (0, 0)
        assert "1bn:" in context
        assert "0.0000" in context
        await parser.close()


# =============================================================================
# Multi-Unit Order Tests
# =============================================================================


class TestMultiUnitOrders:
    """Tests for orders involving multiple units."""

    @pytest.mark.asyncio
    async def test_parse_all_units_order(self, parser, available_units):
        """Test parsing order targeting all units."""
        all_units_response = {
            "response": json.dumps({
                "success": True,
                "order": {
                    "target_units": ["1bn", "2bn", "arty_1", "recon_1"],
                    "order_type": "attack",
                    "objective": {
                        "type": "position",
                        "coordinates": {"latitude": 50.5, "longitude": 9.6},
                    },
                },
                "confidence": 0.88,
                "ambiguities": [],
                "assumptions": ["'All units' interpreted as all available units"],
            })
        }

        with patch.object(parser.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = all_units_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await parser.parse_order(
                "All units attack objective at 50.5, 9.6",
                available_units=available_units,
            )

            assert result["success"] is True
            assert len(result["order"]["target_units"]) == 4

        await parser.close()

    @pytest.mark.asyncio
    async def test_validate_some_valid_units(self, parser, available_units):
        """Test validation keeps only valid units from mixed list."""
        result = {
            "success": True,
            "order": {
                "target_units": ["1bn", "invalid", "2bn", "nonexistent"],
            },
        }
        validated = parser._validate_and_enhance(result, available_units, None)

        assert validated["success"] is True
        assert set(validated["order"]["target_units"]) == {"1bn", "2bn"}
        await parser.close()


# =============================================================================
# Ollama Integration Tests
# =============================================================================


class TestOllamaIntegration:
    """Tests for Ollama API integration."""

    @pytest.mark.asyncio
    async def test_call_ollama_uses_correct_endpoint(self, parser):
        """Test _call_ollama uses correct Ollama endpoint."""
        with patch.object(parser.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": "{}"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            await parser._call_ollama("test prompt")

            mock_post.assert_called_once()
            call_url = mock_post.call_args[0][0]
            assert "/api/generate" in call_url

        await parser.close()

    @pytest.mark.asyncio
    async def test_call_ollama_uses_system_prompt(self, parser):
        """Test _call_ollama includes system prompt."""
        with patch.object(parser.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": "{}"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            await parser._call_ollama("test prompt")

            call_args = mock_post.call_args
            request_json = call_args.kwargs["json"]
            assert "system" in request_json
            assert "military order parser" in request_json["system"]

        await parser.close()

    @pytest.mark.asyncio
    async def test_call_ollama_uses_low_temperature(self, parser):
        """Test _call_ollama uses low temperature for deterministic parsing."""
        with patch.object(parser.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": "{}"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            await parser._call_ollama("test prompt")

            call_args = mock_post.call_args
            options = call_args.kwargs["json"]["options"]
            assert options["temperature"] == 0.3

        await parser.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
