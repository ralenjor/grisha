"""
Shared fixtures for Grisha unit tests.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_config():
    """Test configuration dict."""
    return {
        "model_settings": {
            "max_tokens": 100,
            "overlap_tokens": 20,
            "model_name": "test-model",
            "embed_model": "test-embed"
        },
        "database_settings": {
            "path": ":memory:",
            "collection_name": "test_collection"
        },
        "bm25_settings": {
            "k1": 1.5,
            "b": 0.75,
            "index_path": "/tmp/test_bm25"
        },
        "hybrid_settings": {
            "enabled": True,
            "rrf_k": 60.0,
            "semantic_weight": 0.7,
            "bm25_weight": 0.3
        },
        "hallucination_guard": {
            "verify_citations": True,
            "fail_on_invalid": False,
            "warn_user": True
        }
    }


@pytest.fixture
def mock_chroma_collection():
    """Mock ChromaDB collection with query results."""
    collection = Mock()
    collection.query.return_value = {
        "documents": [[
            "The BTG consists of a motorized rifle battalion reinforced with tanks.",
            "Defensive width is 3-5km per battalion sector.",
            "US Army doctrine recommends combined arms maneuver.",
        ]],
        "metadatas": [[
            {
                "title": "FM 100-2-1",
                "section": "Chapter 6",
                "nation": "RU",
                "doc_type": "doctrine_primary",
                "source_type": "field_manual"
            },
            {
                "title": "Russian Way of War",
                "section": "Section 4.2",
                "nation": "RU",
                "doc_type": "tactical_level",
                "source_type": "academic_paper"
            },
            {
                "title": "FM 3-0 Operations",
                "section": "Chapter 3",
                "nation": "US",
                "doc_type": "doctrine_primary",
                "source_type": "field_manual"
            }
        ]],
        "distances": [[0.25, 0.45, 0.65]],
        "ids": [["id_1", "id_2", "id_3"]]
    }
    return collection


@pytest.fixture
def sample_documents():
    """Sample document data for reranking tests."""
    return {
        "documents": [
            "The BTG consists of a motorized rifle battalion reinforced with tanks and artillery. " * 5,
            "Defensive width is 3-5km per battalion sector according to Russian doctrine.",
            "US Army doctrine recommends combined arms maneuver for offensive operations.",
            "Short doc.",
            "Wikipedia article about general military history without specific doctrine.",
        ],
        "metadatas": [
            {
                "title": "FM 100-2-1",
                "section": "Chapter 6",
                "nation": "RU",
                "doc_type": "doctrine_primary",
                "source_type": "field_manual"
            },
            {
                "title": "Russian Way of War",
                "section": "Section 4.2",
                "nation": "RU",
                "doc_type": "tactical_level",
                "source_type": "academic_paper"
            },
            {
                "title": "FM 3-0 Operations",
                "section": "Chapter 3",
                "nation": "US",
                "doc_type": "doctrine_primary",
                "source_type": "field_manual"
            },
            {
                "title": "FM 100-2-1",
                "section": "Chapter 7",
                "nation": "RU",
                "doc_type": "doctrine_primary",
                "source_type": "field_manual"
            },
            {
                "title": "Military History Wiki",
                "section": "General",
                "nation": "RU",
                "doc_type": "general_reference",
                "source_type": "wikipedia"
            }
        ],
        "distances": [0.2, 0.3, 0.5, 0.4, 0.8]
    }


@pytest.fixture
def sample_context_blocks():
    """Formatted context blocks for citation tests."""
    return [
        "[RU-FM 100-2-1 Chapter 6]:\nThe BTG consists of a motorized rifle battalion reinforced with tanks.",
        "[RU-Russian Way of War Section 4.2]:\nDefensive width is 3-5km per battalion sector.",
        "[US-FM 3-0 Operations Chapter 3]:\nCombined arms maneuver is essential for offensive operations."
    ]


@pytest.fixture
def reset_chat_history():
    """Reset global chat history between tests."""
    import grisha_query
    original_history = grisha_query.chat_history.copy()
    grisha_query.chat_history.clear()
    yield
    grisha_query.chat_history.clear()
    grisha_query.chat_history.extend(original_history)


@pytest.fixture
def mock_ollama_response():
    """Mock successful Ollama API response."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "message": {
            "content": "The defensive width is 3-5km [RU-FM 100-2-1 Chapter 6]. CURRENT READINESS ASSESSMENT: Parameters confirmed."
        }
    }
    mock_response.raise_for_status = Mock()
    return mock_response


@pytest.fixture
def sample_pdf_text():
    """Sample extracted PDF text for testing."""
    return """
    Chapter 4: Defensive Operations

    Section 4.1 - Battalion Defense

    The motorized rifle battalion defends a fortified area 3-5 kilometers wide
    and 2-2.5 kilometers in depth. The battalion position has three or four
    trenches, consisting of company strong points.

    Section 4.2 - Tactical Reserves

    The battalion commander maintains a tactical reserve consisting of one
    motorized rifle platoon and supporting armor assets.
    """


@pytest.fixture
def sample_jsonl_content():
    """Sample JSONL file content for streaming tests."""
    return [
        '{"title": "Battalion Tactical Group", "text": "The Battalion Tactical Group (BTG) is a Russian military formation used in modern conflicts. Russian Armed Forces have employed BTGs extensively."}',
        '{"title": "Maskirovka", "text": "Maskirovka is the Soviet and Russian military doctrine of deception."}',
        '{"title": "Irrelevant", "text": "This article about cooking has nothing to do with military topics."}'
    ]
