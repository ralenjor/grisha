"""
Unit tests for the Grisha Reranker module.

Tests cover:
- Individual score calculation functions
- Composite reranking algorithm
- Filtering and diversity controls
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from reranker import GrishaReranker


class TestSemanticScoring:
    """Tests for _calculate_semantic_score()."""

    def setup_method(self):
        self.reranker = GrishaReranker()

    def test_low_distance_high_score(self):
        """Lower distance should produce higher score."""
        score = self.reranker._calculate_semantic_score(0.1)
        # Formula: 1.0 / (0.1 + 0.1) = 5.0
        assert score == pytest.approx(5.0)

    def test_high_distance_low_score(self):
        """Higher distance should produce lower score."""
        score = self.reranker._calculate_semantic_score(0.9)
        # Formula: 1.0 / (0.9 + 0.1) = 1.0
        assert score == pytest.approx(1.0)

    def test_zero_distance(self):
        """Zero distance should produce maximum score."""
        score = self.reranker._calculate_semantic_score(0.0)
        # Formula: 1.0 / (0.0 + 0.1) = 10.0
        assert score == pytest.approx(10.0)

    def test_distance_ordering(self):
        """Scores should decrease as distance increases."""
        scores = [
            self.reranker._calculate_semantic_score(d)
            for d in [0.1, 0.3, 0.5, 0.7, 0.9]
        ]
        assert scores == sorted(scores, reverse=True)


class TestTypeScoring:
    """Tests for _calculate_type_score()."""

    def setup_method(self):
        self.reranker = GrishaReranker()

    def test_doctrine_primary_highest(self):
        """doctrine_primary should have highest priority (4)."""
        score = self.reranker._calculate_type_score("doctrine_primary")
        assert score == 4.0

    def test_operational_level(self):
        """operational_level should have priority 3."""
        score = self.reranker._calculate_type_score("operational_level")
        assert score == 3.0

    def test_tactical_level(self):
        """tactical_level should have priority 3."""
        score = self.reranker._calculate_type_score("tactical_level")
        assert score == 3.0

    def test_technical_specs(self):
        """technical_specs should have priority 2."""
        score = self.reranker._calculate_type_score("technical_specs")
        assert score == 2.0

    def test_general_reference_lowest(self):
        """general_reference should have lowest priority (1)."""
        score = self.reranker._calculate_type_score("general_reference")
        assert score == 1.0

    def test_unknown_type_zero(self):
        """Unknown document type should return 0."""
        score = self.reranker._calculate_type_score("unknown_type")
        assert score == 0.0


class TestSourceScoring:
    """Tests for _calculate_source_score()."""

    def setup_method(self):
        self.reranker = GrishaReranker()

    def test_field_manual_highest(self):
        """field_manual should have highest priority (3)."""
        score = self.reranker._calculate_source_score("field_manual")
        assert score == 3.0

    def test_academic_paper(self):
        """academic_paper should have priority 2."""
        score = self.reranker._calculate_source_score("academic_paper")
        assert score == 2.0

    def test_wikipedia_lowest(self):
        """wikipedia should have lowest priority (1)."""
        score = self.reranker._calculate_source_score("wikipedia")
        assert score == 1.0

    def test_unknown_source_zero(self):
        """Unknown source type should return 0."""
        score = self.reranker._calculate_source_score("unknown_source")
        assert score == 0.0


class TestNationScoring:
    """Tests for _calculate_nation_score()."""

    def setup_method(self):
        self.reranker = GrishaReranker()

    def test_ru_normal_query_highest(self):
        """RU nation in non-OPFOR query should score highest (3.0)."""
        score = self.reranker._calculate_nation_score("RU", is_opfor=False)
        assert score == 3.0

    def test_us_normal_query_zero(self):
        """US nation in non-OPFOR query should score zero."""
        score = self.reranker._calculate_nation_score("US", is_opfor=False)
        assert score == 0.0

    def test_us_opfor_query_highest(self):
        """US nation in OPFOR query should score highest (2.0)."""
        score = self.reranker._calculate_nation_score("US", is_opfor=True)
        assert score == 2.0

    def test_ru_opfor_query_secondary(self):
        """RU nation in OPFOR query should score slightly lower (1.5)."""
        score = self.reranker._calculate_nation_score("RU", is_opfor=True)
        assert score == 1.5

    def test_unknown_nation_normal(self):
        """Unknown nation in non-OPFOR query should score zero."""
        score = self.reranker._calculate_nation_score("Unknown", is_opfor=False)
        assert score == 0.0


class TestLengthScoring:
    """Tests for _calculate_length_score()."""

    def setup_method(self):
        self.reranker = GrishaReranker()

    def test_short_doc_low_score(self):
        """Short documents should have low score."""
        score = self.reranker._calculate_length_score("Short text")
        # 10 chars / 500 = 0.02
        assert score == pytest.approx(0.02)

    def test_medium_doc_medium_score(self):
        """Medium documents should have proportional score."""
        doc = "x" * 250  # 250 characters
        score = self.reranker._calculate_length_score(doc)
        # 250 / 500 = 0.5
        assert score == pytest.approx(0.5)

    def test_long_doc_capped_at_one(self):
        """Long documents should cap at 1.0."""
        doc = "x" * 1000  # 1000 characters
        score = self.reranker._calculate_length_score(doc)
        # min(1000/500, 1.0) = 1.0
        assert score == 1.0

    def test_exactly_500_chars(self):
        """500 characters should score exactly 1.0."""
        doc = "x" * 500
        score = self.reranker._calculate_length_score(doc)
        assert score == 1.0

    def test_empty_doc(self):
        """Empty document should score 0."""
        score = self.reranker._calculate_length_score("")
        assert score == 0.0


class TestRerank:
    """Tests for the composite rerank() function."""

    def setup_method(self):
        self.reranker = GrishaReranker()

    def test_basic_reranking(self, sample_documents):
        """Results should be ordered by composite score."""
        results = self.reranker.rerank(
            documents=sample_documents["documents"],
            metadatas=sample_documents["metadatas"],
            distances=sample_documents["distances"],
            is_opfor=False,
            return_top=5,
            max_per_source=5,
            relevance_threshold=2.0
        )

        # Should return tuples of (doc, meta, score)
        assert len(results) > 0
        assert all(len(r) == 3 for r in results)

        # Scores should be descending
        scores = [r[2] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_relevance_threshold_filtering(self, sample_documents):
        """Documents beyond relevance threshold should be filtered out."""
        # Set a very low threshold
        results = self.reranker.rerank(
            documents=sample_documents["documents"],
            metadatas=sample_documents["metadatas"],
            distances=sample_documents["distances"],
            is_opfor=False,
            return_top=10,
            max_per_source=10,
            relevance_threshold=0.25  # Only first doc qualifies
        )

        # Most docs should be filtered
        assert len(results) <= 2

    def test_us_filtered_in_normal_mode(self, sample_documents):
        """US documents should be filtered in non-OPFOR mode."""
        results = self.reranker.rerank(
            documents=sample_documents["documents"],
            metadatas=sample_documents["metadatas"],
            distances=sample_documents["distances"],
            is_opfor=False,
            return_top=10,
            max_per_source=10,
            relevance_threshold=2.0
        )

        # No US documents should appear
        nations = [r[1].get("nation") for r in results]
        assert "US" not in nations

    def test_us_included_in_opfor_mode(self, sample_documents):
        """US documents should be included in OPFOR mode."""
        results = self.reranker.rerank(
            documents=sample_documents["documents"],
            metadatas=sample_documents["metadatas"],
            distances=sample_documents["distances"],
            is_opfor=True,
            return_top=10,
            max_per_source=10,
            relevance_threshold=2.0
        )

        # US documents may appear if within threshold
        nations = [r[1].get("nation") for r in results]
        # At least one non-US should exist, and US may exist
        assert "RU" in nations or "US" in nations

    def test_max_per_source_diversity(self):
        """max_per_source should limit chunks from same source."""
        # Create documents all from same source
        documents = ["Doc 1", "Doc 2", "Doc 3", "Doc 4"]
        metadatas = [
            {"title": "Same Source", "nation": "RU", "doc_type": "doctrine_primary", "source_type": "field_manual"},
            {"title": "Same Source", "nation": "RU", "doc_type": "doctrine_primary", "source_type": "field_manual"},
            {"title": "Same Source", "nation": "RU", "doc_type": "doctrine_primary", "source_type": "field_manual"},
            {"title": "Same Source", "nation": "RU", "doc_type": "doctrine_primary", "source_type": "field_manual"},
        ]
        distances = [0.1, 0.2, 0.3, 0.4]

        results = self.reranker.rerank(
            documents=documents,
            metadatas=metadatas,
            distances=distances,
            is_opfor=False,
            return_top=10,
            max_per_source=2,  # Limit to 2 per source
            relevance_threshold=2.0
        )

        # Should only get 2 results from the same source
        assert len(results) == 2

    def test_return_top_limit(self, sample_documents):
        """return_top should limit number of results."""
        results = self.reranker.rerank(
            documents=sample_documents["documents"],
            metadatas=sample_documents["metadatas"],
            distances=sample_documents["distances"],
            is_opfor=False,
            return_top=2,
            max_per_source=10,
            relevance_threshold=2.0
        )

        assert len(results) <= 2

    def test_empty_input(self):
        """Empty input should return empty results."""
        results = self.reranker.rerank(
            documents=[],
            metadatas=[],
            distances=[],
            is_opfor=False
        )

        assert results == []

    def test_all_filtered_returns_empty(self):
        """If all documents filtered, return empty list."""
        documents = ["US only doc"]
        metadatas = [{"title": "US Manual", "nation": "US", "doc_type": "doctrine_primary", "source_type": "field_manual"}]
        distances = [0.1]

        results = self.reranker.rerank(
            documents=documents,
            metadatas=metadatas,
            distances=distances,
            is_opfor=False,  # US filtered out
            return_top=5,
            relevance_threshold=2.0
        )

        assert results == []

    def test_hybrid_score_used_when_available(self):
        """When hybrid_score is in metadata, it should be used."""
        documents = ["Doc with hybrid score", "Doc without hybrid score"]
        metadatas = [
            {"title": "Test1", "nation": "RU", "doc_type": "doctrine_primary",
             "source_type": "field_manual", "hybrid_score": 0.05},
            {"title": "Test2", "nation": "RU", "doc_type": "doctrine_primary",
             "source_type": "field_manual"}
        ]
        distances = [0.5, 0.1]  # Second would normally rank higher

        results = self.reranker.rerank(
            documents=documents,
            metadatas=metadatas,
            distances=distances,
            is_opfor=False,
            return_top=2,
            use_hybrid_scores=True
        )

        assert len(results) == 2
        # Hybrid score should influence ranking

    def test_hybrid_score_ignored_when_disabled(self):
        """When use_hybrid_scores=False, hybrid_score should be ignored."""
        documents = ["Doc 1", "Doc 2"]
        metadatas = [
            {"title": "Test1", "nation": "RU", "doc_type": "doctrine_primary",
             "source_type": "field_manual", "hybrid_score": 0.05},
            {"title": "Test2", "nation": "RU", "doc_type": "doctrine_primary",
             "source_type": "field_manual"}
        ]
        distances = [0.5, 0.1]

        results = self.reranker.rerank(
            documents=documents,
            metadatas=metadatas,
            distances=distances,
            is_opfor=False,
            return_top=2,
            use_hybrid_scores=False  # Disable hybrid
        )

        # Second doc (lower distance) should rank first when hybrid disabled
        assert results[0][1]["title"] == "Test2"

    def test_doctrine_primary_ranks_higher(self):
        """doctrine_primary should rank higher than general_reference with same distance."""
        documents = ["Doctrine doc" * 50, "Wiki doc" * 50]  # Same length
        metadatas = [
            {"title": "Source1", "nation": "RU", "doc_type": "general_reference", "source_type": "wikipedia"},
            {"title": "Source2", "nation": "RU", "doc_type": "doctrine_primary", "source_type": "field_manual"},
        ]
        distances = [0.3, 0.3]  # Same distance

        results = self.reranker.rerank(
            documents=documents,
            metadatas=metadatas,
            distances=distances,
            is_opfor=False,
            return_top=2
        )

        # doctrine_primary should rank first
        assert results[0][1]["doc_type"] == "doctrine_primary"


class TestRerankVerbose:
    """Tests for verbose output mode."""

    def setup_method(self):
        self.reranker = GrishaReranker()

    def test_verbose_includes_breakdown(self, sample_documents, capsys):
        """Verbose mode should print debug output."""
        self.reranker.rerank(
            documents=sample_documents["documents"],
            metadatas=sample_documents["metadatas"],
            distances=sample_documents["distances"],
            is_opfor=False,
            return_top=2,
            verbose=True
        )

        captured = capsys.readouterr()
        assert "RERANKER DEBUG OUTPUT" in captured.out
        assert "SCORE:" in captured.out
