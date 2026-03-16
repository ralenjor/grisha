"""
Unit tests for the Grisha Query module.

Tests cover:
- Citation extraction and verification (hallucination guard)
- Hybrid retrieval (with mocks)
- Main query function (with mocks)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCitationExtraction:
    """Tests for extract_citations()."""

    def test_extract_single_citation(self):
        """Should extract a single citation."""
        from grisha_query import extract_citations

        text = "The defensive width is 3-5km [RU-FM 100-2-1 Chapter 6]."
        citations = extract_citations(text)

        assert len(citations) == 1
        assert citations[0] == ("RU", "FM 100-2-1 Chapter 6")

    def test_extract_multiple_citations(self):
        """Should extract multiple citations."""
        from grisha_query import extract_citations

        text = """
        The defensive width is 3-5km [RU-FM 100-2-1 Chapter 6].
        US doctrine states similar parameters [US-FM 3-0 Operations].
        """
        citations = extract_citations(text)

        assert len(citations) == 2
        assert ("RU", "FM 100-2-1 Chapter 6") in citations
        assert ("US", "FM 3-0 Operations") in citations

    def test_extract_no_citations(self):
        """Should return empty list when no citations present."""
        from grisha_query import extract_citations

        text = "This text has no citations at all."
        citations = extract_citations(text)

        assert citations == []

    def test_extract_us_citation(self):
        """Should extract US nation citations."""
        from grisha_query import extract_citations

        text = "Javelin has minimum range of 65m [US-Javelin TM 3-22.37]."
        citations = extract_citations(text)

        assert len(citations) == 1
        assert citations[0][0] == "US"

    def test_extract_citation_with_section(self):
        """Should extract citation with section/chapter info."""
        from grisha_query import extract_citations

        text = "Battalion defense [RU-Russian Way of War Section 4.2] includes..."
        citations = extract_citations(text)

        assert len(citations) == 1
        assert "Section 4.2" in citations[0][1]

    def test_ignore_malformed_citations(self):
        """Should ignore citations without proper nation prefix."""
        from grisha_query import extract_citations

        text = "[No-Nation Here] and [X-Too Short] but [RU-Valid Citation] works."
        citations = extract_citations(text)

        # Only the valid one with 2-letter nation code
        assert len(citations) == 1
        assert citations[0][0] == "RU"

    def test_extract_adjacent_citations(self):
        """Should extract citations appearing adjacent to each other."""
        from grisha_query import extract_citations

        text = "See [RU-Manual A] [RU-Manual B] for details."
        citations = extract_citations(text)

        assert len(citations) == 2


class TestCitationVerification:
    """Tests for verify_citations()."""

    def test_valid_citation_passes(self, sample_context_blocks):
        """Valid citations matching context should pass."""
        from grisha_query import verify_citations

        response = "The width is 3-5km [RU-FM 100-2-1 Chapter 6]."

        is_valid, invalid, warning = verify_citations(response, sample_context_blocks)

        assert is_valid is True
        assert invalid == []
        assert warning is None

    def test_invalid_citation_detected(self, sample_context_blocks):
        """Citations not in context should be detected."""
        from grisha_query import verify_citations

        response = "The T-90 has 1000mm armor [RU-T-90 Technical Manual]."

        is_valid, invalid, warning = verify_citations(response, sample_context_blocks)

        assert is_valid is False
        assert len(invalid) == 1
        assert "[RU-T-90 Technical Manual]" in invalid
        assert warning is not None
        assert "could not be verified" in warning

    def test_no_citations_passes(self, sample_context_blocks):
        """Response without citations should pass."""
        from grisha_query import verify_citations

        response = "Archives incomplete for this parameter."

        is_valid, invalid, warning = verify_citations(response, sample_context_blocks)

        assert is_valid is True
        assert invalid == []

    def test_partial_title_match(self, sample_context_blocks):
        """Should match partial titles correctly."""
        from grisha_query import verify_citations

        # Context has "Russian Way of War Section 4.2"
        # Citation uses just the title
        response = "As documented [RU-Russian Way of War]."

        is_valid, invalid, warning = verify_citations(response, sample_context_blocks)

        assert is_valid is True

    def test_multiple_valid_citations(self, sample_context_blocks):
        """Multiple valid citations should all pass."""
        from grisha_query import verify_citations

        response = """
        The width is 3-5km [RU-FM 100-2-1 Chapter 6].
        The battalion defense [RU-Russian Way of War Section 4.2] includes trenches.
        """

        is_valid, invalid, warning = verify_citations(response, sample_context_blocks)

        assert is_valid is True
        assert invalid == []

    def test_mixed_valid_invalid(self, sample_context_blocks):
        """Mix of valid and invalid citations should report invalids."""
        from grisha_query import verify_citations

        response = """
        The width is 3-5km [RU-FM 100-2-1 Chapter 6].
        The T-90 has armor [RU-Fake Manual 9.9].
        """

        is_valid, invalid, warning = verify_citations(response, sample_context_blocks)

        assert is_valid is False
        assert len(invalid) == 1
        assert "[RU-Fake Manual 9.9]" in invalid

    def test_us_citation_in_context(self, sample_context_blocks):
        """US citations should be validated against US context."""
        from grisha_query import verify_citations

        response = "US doctrine states [US-FM 3-0 Operations Chapter 3]."

        is_valid, invalid, warning = verify_citations(response, sample_context_blocks)

        assert is_valid is True

    def test_wrong_nation_invalid(self, sample_context_blocks):
        """Citation with wrong nation prefix should be invalid."""
        from grisha_query import verify_citations

        # Context has RU-FM 100-2-1, not US-FM 100-2-1
        response = "The width is 3-5km [US-FM 100-2-1 Chapter 6]."

        is_valid, invalid, warning = verify_citations(response, sample_context_blocks)

        assert is_valid is False

    def test_warning_message_format(self, sample_context_blocks):
        """Warning message should be properly formatted."""
        from grisha_query import verify_citations

        response = "Fake data [RU-Nonexistent Manual]."

        is_valid, invalid, warning = verify_citations(response, sample_context_blocks)

        assert "WARNING" in warning
        assert "hallucinated" in warning.lower() or "Cross-reference" in warning


class TestHybridRetrieve:
    """Tests for hybrid_retrieve() function."""

    def test_semantic_only_when_bm25_unavailable(self, mock_chroma_collection):
        """Should fall back to semantic-only when BM25 unavailable."""
        from grisha_query import hybrid_retrieve

        with patch('grisha_query.bm25_index', None), \
             patch('grisha_query.HYBRID_ENABLED', False):

            results = hybrid_retrieve("test query", mock_chroma_collection)

            # Should return original ChromaDB results
            assert results["documents"][0] == mock_chroma_collection.query.return_value["documents"][0]
            mock_chroma_collection.query.assert_called_once()

    def test_empty_results_returned_as_is(self, mock_chroma_collection):
        """Empty results should be returned unchanged."""
        from grisha_query import hybrid_retrieve

        mock_chroma_collection.query.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
            "ids": [[]]
        }

        with patch('grisha_query.bm25_index', None):
            results = hybrid_retrieve("test query", mock_chroma_collection)

            assert results["documents"][0] == []

    def test_where_filter_passed_to_chromadb(self, mock_chroma_collection):
        """Where filter should be passed to ChromaDB query."""
        from grisha_query import hybrid_retrieve

        with patch('grisha_query.bm25_index', None):
            hybrid_retrieve(
                "test query",
                mock_chroma_collection,
                where_filter={"nation": "RU"},
                top_k=50
            )

            mock_chroma_collection.query.assert_called_once()
            call_kwargs = mock_chroma_collection.query.call_args[1]
            assert call_kwargs["where"] == {"nation": "RU"}
            assert call_kwargs["n_results"] == 50


class TestOPFORDetection:
    """Tests for OPFOR query detection."""

    def test_javelin_triggers_opfor(self):
        """Question mentioning Javelin should trigger OPFOR mode."""
        us_equipment = ['javelin', 'm240', 'm249', 'abrams', 'bradley', 'stryker', 'apache', 'blackhawk']
        question = "How should I position my Javelin teams?"

        is_opfor = any(weapon in question.lower() for weapon in us_equipment)

        assert is_opfor is True

    def test_abrams_triggers_opfor(self):
        """Question mentioning Abrams should trigger OPFOR mode."""
        us_equipment = ['javelin', 'm240', 'm249', 'abrams', 'bradley', 'stryker', 'apache', 'blackhawk']
        question = "What are Abrams vulnerabilities?"

        is_opfor = any(weapon in question.lower() for weapon in us_equipment)

        assert is_opfor is True

    def test_russian_equipment_no_opfor(self):
        """Question about Russian equipment should not trigger OPFOR."""
        us_equipment = ['javelin', 'm240', 'm249', 'abrams', 'bradley', 'stryker', 'apache', 'blackhawk']
        question = "What is the BMP-3 doctrine?"

        is_opfor = any(weapon in question.lower() for weapon in us_equipment)

        assert is_opfor is False

    def test_general_question_no_opfor(self):
        """General tactical question should not trigger OPFOR."""
        us_equipment = ['javelin', 'm240', 'm249', 'abrams', 'bradley', 'stryker', 'apache', 'blackhawk']
        question = "What is the defensive width of a battalion?"

        is_opfor = any(weapon in question.lower() for weapon in us_equipment)

        assert is_opfor is False


class TestAskGrishaBrain:
    """Tests for ask_grisha_brain() main function."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, reset_chat_history):
        """Reset state before each test."""
        pass

    def test_no_results_returns_message(self, mock_chroma_collection):
        """Empty retrieval should return appropriate message."""
        mock_chroma_collection.query.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
            "ids": [[]]
        }

        with patch('grisha_query.collection', mock_chroma_collection), \
             patch('grisha_query.bm25_index', None), \
             patch('grisha_query.hybrid_retrieve') as mock_hybrid:

            mock_hybrid.return_value = {
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]],
                "ids": [[]]
            }

            from grisha_query import ask_grisha_brain
            result = ask_grisha_brain("What is the meaning of life?")

            assert "No data found" in result or "No relevant" in result

    def test_high_distance_returns_no_data(self, mock_chroma_collection):
        """Results beyond relevance threshold should return no data message."""
        with patch('grisha_query.collection', mock_chroma_collection), \
             patch('grisha_query.bm25_index', None), \
             patch('grisha_query.hybrid_retrieve') as mock_hybrid:

            mock_hybrid.return_value = {
                "documents": [["Some irrelevant text"]],
                "metadatas": [[{"nation": "RU", "doc_type": "general_reference", "source_type": "wikipedia", "title": "Test"}]],
                "distances": [[10.0]],  # Very high distance
                "ids": [["id_1"]]
            }

            from grisha_query import ask_grisha_brain
            result = ask_grisha_brain("Completely unrelated query")

            assert "No data found" in result

    def test_successful_query_with_mocked_ollama(
        self, mock_chroma_collection, mock_ollama_response
    ):
        """Successful query should return LLM response."""
        with patch('grisha_query.collection', mock_chroma_collection), \
             patch('grisha_query.bm25_index', None), \
             patch('grisha_query.hybrid_retrieve') as mock_hybrid, \
             patch('grisha_query.requests.post') as mock_post, \
             patch('grisha_query.VERIFY_CITATIONS', False):

            mock_hybrid.return_value = {
                "documents": [["The BTG consists of a motorized rifle battalion."]],
                "metadatas": [[{
                    "nation": "RU",
                    "doc_type": "doctrine_primary",
                    "source_type": "field_manual",
                    "title": "FM 100-2-1",
                    "section": "Chapter 6"
                }]],
                "distances": [[0.3]],
                "ids": [["id_1"]]
            }

            mock_post.return_value = mock_ollama_response

            from grisha_query import ask_grisha_brain
            result = ask_grisha_brain("What is a BTG?")

            assert "defensive width" in result.lower() or "3-5km" in result

    def test_citation_warning_appended(
        self, mock_chroma_collection
    ):
        """Invalid citations should trigger warning when WARN_USER is true."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "message": {
                "content": "The T-90 has armor [RU-Fake Manual 9.9]."  # Invalid citation
            }
        }
        mock_response.raise_for_status = Mock()

        with patch('grisha_query.collection', mock_chroma_collection), \
             patch('grisha_query.bm25_index', None), \
             patch('grisha_query.hybrid_retrieve') as mock_hybrid, \
             patch('grisha_query.requests.post') as mock_post, \
             patch('grisha_query.VERIFY_CITATIONS', True), \
             patch('grisha_query.WARN_USER', True), \
             patch('grisha_query.FAIL_ON_INVALID', False):

            mock_hybrid.return_value = {
                "documents": [["The BTG consists of a motorized rifle battalion."]],
                "metadatas": [[{
                    "nation": "RU",
                    "doc_type": "doctrine_primary",
                    "source_type": "field_manual",
                    "title": "FM 100-2-1",
                    "section": "Chapter 6"
                }]],
                "distances": [[0.3]],
                "ids": [["id_1"]]
            }

            mock_post.return_value = mock_response

            from grisha_query import ask_grisha_brain
            result = ask_grisha_brain("What about the T-90?")

            assert "WARNING" in result or "could not be verified" in result

    def test_fail_on_invalid_rejects_response(
        self, mock_chroma_collection
    ):
        """FAIL_ON_INVALID should reject responses with invalid citations."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "message": {
                "content": "Fake data [RU-Nonexistent Manual]."
            }
        }
        mock_response.raise_for_status = Mock()

        with patch('grisha_query.collection', mock_chroma_collection), \
             patch('grisha_query.bm25_index', None), \
             patch('grisha_query.hybrid_retrieve') as mock_hybrid, \
             patch('grisha_query.requests.post') as mock_post, \
             patch('grisha_query.VERIFY_CITATIONS', True), \
             patch('grisha_query.FAIL_ON_INVALID', True):

            mock_hybrid.return_value = {
                "documents": [["Some text"]],
                "metadatas": [[{
                    "nation": "RU",
                    "doc_type": "doctrine_primary",
                    "source_type": "field_manual",
                    "title": "FM 100-2-1",
                    "section": "Chapter 6"
                }]],
                "distances": [[0.3]],
                "ids": [["id_1"]]
            }

            mock_post.return_value = mock_response

            from grisha_query import ask_grisha_brain
            result = ask_grisha_brain("Test query")

            assert "REJECTED" in result

    def test_ollama_error_returns_error_message(self, mock_chroma_collection):
        """Ollama connection error should return error message."""
        with patch('grisha_query.collection', mock_chroma_collection), \
             patch('grisha_query.bm25_index', None), \
             patch('grisha_query.hybrid_retrieve') as mock_hybrid, \
             patch('grisha_query.requests.post') as mock_post:

            mock_hybrid.return_value = {
                "documents": [["Some text"]],
                "metadatas": [[{
                    "nation": "RU",
                    "doc_type": "doctrine_primary",
                    "source_type": "field_manual",
                    "title": "Test",
                    "section": "General"
                }]],
                "distances": [[0.3]],
                "ids": [["id_1"]]
            }

            mock_post.side_effect = Exception("Connection refused")

            from grisha_query import ask_grisha_brain
            result = ask_grisha_brain("Test query")

            assert "Error" in result

    def test_chat_history_maintained(self, mock_chroma_collection, mock_ollama_response):
        """Chat history should be maintained across queries."""
        import grisha_query
        grisha_query.chat_history.clear()

        with patch('grisha_query.collection', mock_chroma_collection), \
             patch('grisha_query.bm25_index', None), \
             patch('grisha_query.hybrid_retrieve') as mock_hybrid, \
             patch('grisha_query.requests.post') as mock_post, \
             patch('grisha_query.VERIFY_CITATIONS', False):

            mock_hybrid.return_value = {
                "documents": [["Some text"]],
                "metadatas": [[{
                    "nation": "RU",
                    "doc_type": "doctrine_primary",
                    "source_type": "field_manual",
                    "title": "Test",
                    "section": "General"
                }]],
                "distances": [[0.3]],
                "ids": [["id_1"]]
            }

            mock_post.return_value = mock_ollama_response

            from grisha_query import ask_grisha_brain
            ask_grisha_brain("First question")

            assert len(grisha_query.chat_history) == 1
            assert grisha_query.chat_history[0][0] == "First question"


class TestContextFormatting:
    """Tests for context block formatting."""

    def test_context_block_format(self):
        """Context blocks should have correct format."""
        # Simulate the formatting logic from ask_grisha_brain
        meta = {
            "nation": "RU",
            "title": "FM 100-2-1",
            "section": "Chapter 6"
        }
        doc = "The BTG consists of a motorized rifle battalion."

        source = f"[{meta['nation']}-{meta['title']} {meta['section']}]"
        context_block = f"{source}:\n{doc}"

        assert "[RU-FM 100-2-1 Chapter 6]:" in context_block
        assert doc in context_block

    def test_truncation_applied_to_long_chunks(self):
        """Long chunks should be truncated."""
        MAX_CHUNK_LENGTH = 600
        doc = "x" * 1000  # Long document

        truncated_doc = doc[:MAX_CHUNK_LENGTH] + "..." if len(doc) > MAX_CHUNK_LENGTH else doc

        assert len(truncated_doc) == MAX_CHUNK_LENGTH + 3  # +3 for "..."
        assert truncated_doc.endswith("...")

    def test_short_chunks_not_truncated(self):
        """Short chunks should not be truncated."""
        MAX_CHUNK_LENGTH = 600
        doc = "Short document content."

        truncated_doc = doc[:MAX_CHUNK_LENGTH] + "..." if len(doc) > MAX_CHUNK_LENGTH else doc

        assert truncated_doc == doc
        assert not truncated_doc.endswith("...")
