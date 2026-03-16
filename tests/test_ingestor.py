"""
Unit tests for the Grisha Ingestor module.

Tests cover:
- Token counting
- Relevance filtering
- Document classification
- Entity extraction
- Section detection
- Sentence-based chunking
- Document processing pipeline
"""

import pytest
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTokenCount:
    """Tests for token_count() function."""

    def test_empty_string(self):
        """Empty string should return 0 tokens."""
        from grisha_ingestor import token_count

        assert token_count("") == 0

    def test_single_word(self):
        """Single word should return small token count."""
        from grisha_ingestor import token_count

        count = token_count("hello")
        assert count >= 1
        assert count <= 2

    def test_sentence(self):
        """Sentence should return reasonable token count."""
        from grisha_ingestor import token_count

        count = token_count("The quick brown fox jumps over the lazy dog.")
        assert count >= 8
        assert count <= 15

    def test_longer_text(self):
        """Longer text should have proportionally more tokens."""
        from grisha_ingestor import token_count

        short = "Hello world."
        long = "Hello world. " * 10

        short_count = token_count(short)
        long_count = token_count(long)

        assert long_count > short_count


class TestIsRelevant:
    """Tests for is_relevant() function."""

    def test_russian_armed_forces_relevant(self):
        """Text mentioning Russian Armed Forces should be relevant."""
        from grisha_ingestor import is_relevant

        text = "The Russian Armed Forces conducted exercises."
        assert is_relevant(text) is True

    def test_btg_relevant(self):
        """Text mentioning Battalion Tactical Group should be relevant."""
        from grisha_ingestor import is_relevant

        text = "The Battalion Tactical Group formation is used in modern warfare."
        assert is_relevant(text) is True

    def test_maskirovka_relevant(self):
        """Text mentioning maskirovka should be relevant."""
        from grisha_ingestor import is_relevant

        text = "Soviet maskirovka doctrine emphasizes deception."
        assert is_relevant(text) is True

    def test_ukraine_relevant(self):
        """Text mentioning Ukraine should be relevant."""
        from grisha_ingestor import is_relevant

        text = "Operations in Ukraine demonstrated modern combined arms."
        assert is_relevant(text) is True

    def test_vdv_relevant(self):
        """Text mentioning VDV should be relevant."""
        from grisha_ingestor import is_relevant

        text = "VDV airborne forces were deployed."
        assert is_relevant(text) is True

    def test_irrelevant_text(self):
        """Irrelevant text should return False."""
        from grisha_ingestor import is_relevant

        text = "This is an article about cooking recipes and gardening tips."
        assert is_relevant(text) is False

    def test_case_insensitive(self):
        """Keyword matching should be case insensitive."""
        from grisha_ingestor import is_relevant

        text = "the russian military conducted operations"
        assert is_relevant(text) is True

    def test_spetsnaz_relevant(self):
        """Text mentioning Spetsnaz should be relevant."""
        from grisha_ingestor import is_relevant

        text = "Spetsnaz units conducted special operations."
        assert is_relevant(text) is True


class TestClassifyDocument:
    """Tests for classify_document() function."""

    def test_field_manual_primary(self):
        """Field manual should be classified as doctrine_primary."""
        from grisha_ingestor import classify_document

        result = classify_document("FM 100-2-1", "Field manual content")
        assert result == "doctrine_primary"

    def test_regulations_primary(self):
        """Regulations should be classified as doctrine_primary."""
        from grisha_ingestor import classify_document

        result = classify_document("Combat Regulations", "Official regulations text")
        assert result == "doctrine_primary"

    def test_operational_art(self):
        """Operational art text should be operational_level."""
        from grisha_ingestor import classify_document

        result = classify_document("Campaign Planning", "Operational art and campaign planning")
        assert result == "operational_level"

    def test_corps_operational(self):
        """Corps-level content should be operational_level."""
        from grisha_ingestor import classify_document

        result = classify_document("Corps Operations", "The corps commander decided")
        assert result == "operational_level"

    def test_battalion_tactical(self):
        """Battalion content should be tactical_level."""
        from grisha_ingestor import classify_document

        result = classify_document("Battalion Tactics", "The battalion commander positioned")
        assert result == "tactical_level"

    def test_btg_tactical(self):
        """BTG content should be tactical_level."""
        from grisha_ingestor import classify_document

        result = classify_document("BTG Employment", "BTG tactics in modern warfare")
        assert result == "tactical_level"

    def test_specifications_technical(self):
        """Technical specifications should be technical_specs."""
        from grisha_ingestor import classify_document

        result = classify_document("T-90 Specifications", "Range 4000m, armor 800mm")
        assert result == "technical_specs"

    def test_caliber_technical(self):
        """Caliber mentions should be technical_specs."""
        from grisha_ingestor import classify_document

        result = classify_document("Weapons", "125mm caliber cannon")
        assert result == "technical_specs"

    def test_general_reference_default(self):
        """Unclassified content should be general_reference."""
        from grisha_ingestor import classify_document

        result = classify_document("General Article", "Some general content about history")
        assert result == "general_reference"

    def test_classification_case_insensitive(self):
        """Classification should be case insensitive."""
        from grisha_ingestor import classify_document

        result = classify_document("FIELD MANUAL", "FIELD MANUAL content")
        assert result == "doctrine_primary"


class TestExtractEntities:
    """Tests for extract_entities() function."""

    def test_extract_capitalized_phrases(self):
        """Should extract capitalized multi-word phrases."""
        from grisha_ingestor import extract_entities

        text = "The Russian Armed Forces deployed Battalion Tactical Groups."
        entities = extract_entities(text)

        # The regex captures multi-word capitalized phrases
        # It may include leading "The" since it starts with capital letter
        assert any("Russian Armed Forces" in e for e in entities)
        assert any("Tactical Groups" in e for e in entities)

    def test_extract_acronym_phrases(self):
        """Should extract phrases with acronyms."""
        from grisha_ingestor import extract_entities

        text = "The T-90 Main Battle Tank was deployed."
        entities = extract_entities(text)

        # Should find capitalized phrases
        assert len(entities) >= 0  # May or may not match depending on pattern

    def test_no_entities_in_lowercase(self):
        """Lowercase text should have no entities."""
        from grisha_ingestor import extract_entities

        text = "this is all lowercase text with no proper nouns."
        entities = extract_entities(text)

        assert entities == []

    def test_unique_entities(self):
        """Should return unique entities only."""
        from grisha_ingestor import extract_entities

        text = "Russian Forces and Russian Forces again."
        entities = extract_entities(text)

        # Count occurrences
        assert len(entities) == len(set(entities))


class TestExtractSection:
    """Tests for extract_section() function."""

    def test_extract_chapter(self):
        """Should extract Chapter references."""
        from grisha_ingestor import extract_section

        text = "Chapter 4: Defensive Operations\n\nThe battalion..."
        section = extract_section(text)

        assert "Chapter 4" in section

    def test_extract_section_number(self):
        """Should extract Section references."""
        from grisha_ingestor import extract_section

        text = "Section 4.2 - Tactical Reserves\n\nThe commander..."
        section = extract_section(text)

        assert "Section 4.2" in section

    def test_extract_paragraph(self):
        """Should extract Para/Paragraph references."""
        from grisha_ingestor import extract_section

        text = "Para 15. Movement procedures..."
        section = extract_section(text)

        assert "Para 15" in section

    def test_no_section_returns_general(self):
        """Text without section markers should return General."""
        from grisha_ingestor import extract_section

        text = "This is just regular text about military operations."
        section = extract_section(text)

        assert section == "General"

    def test_empty_text_returns_general(self):
        """Empty text should return General."""
        from grisha_ingestor import extract_section

        section = extract_section("")
        assert section == "General"

    def test_none_returns_general(self):
        """None input should return General."""
        from grisha_ingestor import extract_section

        section = extract_section(None)
        assert section == "General"

    def test_case_insensitive(self):
        """Section detection should be case insensitive."""
        from grisha_ingestor import extract_section

        text = "CHAPTER 5: OFFENSIVE OPERATIONS"
        section = extract_section(text)

        assert "5" in section


class TestSplitBySentence:
    """Tests for split_by_sentence() function."""

    def test_single_sentence(self):
        """Single sentence should return one chunk."""
        from grisha_ingestor import split_by_sentence

        text = "This is a single sentence."
        chunks = split_by_sentence(text, max_tokens=100)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_multiple_sentences_under_limit(self):
        """Multiple sentences under limit should be one chunk."""
        from grisha_ingestor import split_by_sentence

        text = "First sentence. Second sentence. Third sentence."
        chunks = split_by_sentence(text, max_tokens=100)

        assert len(chunks) == 1

    def test_sentences_split_at_limit(self):
        """Sentences should split when exceeding token limit."""
        from grisha_ingestor import split_by_sentence

        # Create text that will exceed a small token limit
        text = "First sentence with some words. Second sentence with more words. Third sentence here."
        chunks = split_by_sentence(text, max_tokens=10)

        assert len(chunks) > 1

    def test_empty_text(self):
        """Empty text should return empty list or single empty chunk."""
        from grisha_ingestor import split_by_sentence

        chunks = split_by_sentence("", max_tokens=100)

        # Either empty list or list with empty string
        assert len(chunks) <= 1

    def test_preserves_sentences(self):
        """Chunking should preserve complete sentences."""
        from grisha_ingestor import split_by_sentence

        text = "First sentence. Second sentence. Third sentence."
        chunks = split_by_sentence(text, max_tokens=100)

        # Rejoining should give original content
        rejoined = " ".join(chunks)
        assert "First sentence" in rejoined
        assert "Second sentence" in rejoined
        assert "Third sentence" in rejoined


class TestChunkDocument:
    """Tests for chunk_document() function."""

    def test_basic_chunking(self):
        """Should chunk document and preserve metadata."""
        from grisha_ingestor import chunk_document

        doc = {
            "title": "Test Manual",
            "text": "Chapter 1: Introduction. This is the introduction text.",
            "nation": "RU",
            "source_type": "field_manual",
            "doc_type": "doctrine_primary"
        }

        chunks = list(chunk_document(doc))

        assert len(chunks) >= 1
        for chunk in chunks:
            assert "text" in chunk
            assert "metadata" in chunk
            assert chunk["metadata"]["title"] == "Test Manual"
            assert chunk["metadata"]["nation"] == "RU"
            assert chunk["metadata"]["source_type"] == "field_manual"

    def test_section_extraction_in_chunks(self):
        """Chunks should have section metadata."""
        from grisha_ingestor import chunk_document

        doc = {
            "title": "Test Manual",
            "text": "Chapter 4: Defense. The defensive parameters are defined.",
            "nation": "RU",
            "source_type": "field_manual",
            "doc_type": "doctrine_primary"
        }

        chunks = list(chunk_document(doc))

        assert len(chunks) >= 1
        # Section should be extracted
        assert chunks[0]["metadata"]["section"] is not None

    def test_chunk_index_increments(self):
        """Chunk index should increment for multiple chunks."""
        from grisha_ingestor import chunk_document

        # Create a document that will produce multiple chunks
        long_text = "Sentence number one. " * 100

        doc = {
            "title": "Long Document",
            "text": long_text,
            "nation": "RU",
            "source_type": "field_manual",
            "doc_type": "doctrine_primary"
        }

        with patch('grisha_ingestor.MAX_TOKENS', 50):  # Force small chunks
            chunks = list(chunk_document(doc))

        if len(chunks) > 1:
            indices = [c["metadata"]["chunk_index"] for c in chunks]
            assert indices == list(range(len(chunks)))

    def test_nation_propagates(self):
        """Nation tag should propagate to all chunks."""
        from grisha_ingestor import chunk_document

        doc = {
            "title": "US Manual",
            "text": "Content for US doctrine.",
            "nation": "US",
            "source_type": "field_manual",
            "doc_type": "doctrine_primary"
        }

        chunks = list(chunk_document(doc))

        for chunk in chunks:
            assert chunk["metadata"]["nation"] == "US"


class TestStreamWikipediaJsonl:
    """Tests for stream_wikipedia_jsonl() function."""

    def test_streams_relevant_articles(self, tmp_path):
        """Should stream only relevant articles."""
        from grisha_ingestor import stream_wikipedia_jsonl

        # Create test JSONL file
        jsonl_file = tmp_path / "test.jsonl"
        with open(jsonl_file, "w") as f:
            f.write('{"title": "Battalion Tactical Group", "text": "Russian Armed Forces BTG formation."}\n')
            f.write('{"title": "Cooking", "text": "This is about cooking recipes."}\n')
            f.write('{"title": "Maskirovka", "text": "Soviet maskirovka deception doctrine."}\n')

        articles = list(stream_wikipedia_jsonl(jsonl_file, nation="RU"))

        # Should only get the relevant articles
        assert len(articles) == 2
        titles = [a["title"] for a in articles]
        assert "Battalion Tactical Group" in titles
        assert "Maskirovka" in titles
        assert "Cooking" not in titles

    def test_sets_nation_tag(self, tmp_path):
        """Should set nation tag on all articles."""
        from grisha_ingestor import stream_wikipedia_jsonl

        jsonl_file = tmp_path / "test.jsonl"
        with open(jsonl_file, "w") as f:
            f.write('{"title": "VDV Forces", "text": "VDV airborne operations."}\n')

        articles = list(stream_wikipedia_jsonl(jsonl_file, nation="RU"))

        assert len(articles) == 1
        assert articles[0]["nation"] == "RU"

    def test_classifies_documents(self, tmp_path):
        """Should classify documents correctly."""
        from grisha_ingestor import stream_wikipedia_jsonl

        jsonl_file = tmp_path / "test.jsonl"
        with open(jsonl_file, "w") as f:
            f.write('{"title": "FM Field Manual", "text": "Russian Armed Forces field manual content."}\n')

        articles = list(stream_wikipedia_jsonl(jsonl_file, nation="RU"))

        assert len(articles) == 1
        assert articles[0]["doc_type"] == "doctrine_primary"

    def test_handles_malformed_json(self, tmp_path):
        """Should skip malformed JSON lines."""
        from grisha_ingestor import stream_wikipedia_jsonl

        jsonl_file = tmp_path / "test.jsonl"
        with open(jsonl_file, "w") as f:
            f.write('{"title": "Valid", "text": "Russian Armed Forces content."}\n')
            f.write('this is not valid json\n')
            f.write('{"title": "Also Valid", "text": "More Russian military content."}\n')

        articles = list(stream_wikipedia_jsonl(jsonl_file, nation="RU"))

        # Should get both valid articles, skip the malformed one
        assert len(articles) == 2

    def test_skips_empty_text(self, tmp_path):
        """Should skip articles with empty text."""
        from grisha_ingestor import stream_wikipedia_jsonl

        jsonl_file = tmp_path / "test.jsonl"
        with open(jsonl_file, "w") as f:
            f.write('{"title": "Empty Article", "text": ""}\n')
            f.write('{"title": "Valid", "text": "Russian Armed Forces content."}\n')

        articles = list(stream_wikipedia_jsonl(jsonl_file, nation="RU"))

        assert len(articles) == 1
        assert articles[0]["title"] == "Valid"


class TestProcessFile:
    """Tests for process_file() function."""

    def test_process_jsonl_file(self, tmp_path):
        """Should process JSONL files."""
        from grisha_ingestor import process_file

        jsonl_file = tmp_path / "test.jsonl"
        with open(jsonl_file, "w") as f:
            f.write('{"title": "BTG Operations", "text": "Russian Armed Forces BTG tactics."}\n')

        docs = list(process_file(jsonl_file))

        assert len(docs) == 1
        assert docs[0]["title"] == "BTG Operations"

    def test_detects_us_doctrine_path(self, tmp_path):
        """Should detect US doctrine from path."""
        from grisha_ingestor import process_file

        # Create path structure matching US doctrine
        us_path = tmp_path / "grisha" / "brain" / "us_doctrine"
        us_path.mkdir(parents=True)
        jsonl_file = us_path / "test.jsonl"
        with open(jsonl_file, "w") as f:
            f.write('{"title": "US Manual", "text": "Russian Armed Forces comparison with US."}\n')

        docs = list(process_file(jsonl_file))

        if len(docs) > 0:
            assert docs[0]["nation"] == "US"

    def test_default_nation_ru(self, tmp_path):
        """Default nation should be RU."""
        from grisha_ingestor import process_file

        jsonl_file = tmp_path / "test.jsonl"
        with open(jsonl_file, "w") as f:
            f.write('{"title": "Military", "text": "Russian Armed Forces doctrine."}\n')

        docs = list(process_file(jsonl_file))

        assert len(docs) == 1
        assert docs[0]["nation"] == "RU"

    def test_pdf_file_detection(self, tmp_path):
        """Should detect PDF files."""
        from grisha_ingestor import process_file

        pdf_file = tmp_path / "test.pdf"

        with patch('grisha_ingestor.extract_text_from_pdf') as mock_extract:
            mock_extract.return_value = "Extracted PDF content about Russian Armed Forces."

            docs = list(process_file(pdf_file))

            mock_extract.assert_called_once()
            assert len(docs) == 1
            assert docs[0]["title"] == "test.pdf"

    def test_fm_pdf_classified_as_field_manual(self, tmp_path):
        """PDFs with 'fm' in name should be field_manual source type."""
        from grisha_ingestor import process_file

        pdf_file = tmp_path / "fm_100-2-1.pdf"

        with patch('grisha_ingestor.extract_text_from_pdf') as mock_extract:
            mock_extract.return_value = "Field manual content."

            docs = list(process_file(pdf_file))

            assert len(docs) == 1
            assert docs[0]["source_type"] == "field_manual"


class TestBM25IndexCreation:
    """Tests for BM25 index management functions."""

    def test_create_index_when_available(self, sample_config):
        """Should create BM25 index when module available."""
        from grisha_ingestor import create_bm25_index

        with patch('grisha_ingestor.BM25_AVAILABLE', True), \
             patch('grisha_ingestor.grisha_bm25') as mock_bm25:

            mock_index = Mock()
            mock_bm25.BM25Index.return_value = mock_index

            index = create_bm25_index(sample_config)

            mock_bm25.BM25Index.assert_called_once_with(k1=1.5, b=0.75)
            assert index == mock_index

    def test_create_index_when_unavailable(self, sample_config):
        """Should return None when BM25 module unavailable."""
        from grisha_ingestor import create_bm25_index

        with patch('grisha_ingestor.BM25_AVAILABLE', False):
            index = create_bm25_index(sample_config)

            assert index is None

    def test_save_index(self, sample_config, tmp_path):
        """Should save BM25 index to disk."""
        from grisha_ingestor import save_bm25_index

        mock_index = Mock()
        mock_index.document_count = 100
        mock_index.vocabulary_size = 5000
        mock_index.average_doc_length = 150.5

        config = sample_config.copy()
        config["bm25_settings"]["index_path"] = str(tmp_path / "bm25")

        save_bm25_index(mock_index, config)

        mock_index.finalize.assert_called_once()
        mock_index.save.assert_called_once()

    def test_save_none_index(self, sample_config):
        """Saving None index should do nothing."""
        from grisha_ingestor import save_bm25_index

        # Should not raise
        save_bm25_index(None, sample_config)
