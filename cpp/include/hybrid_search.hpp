#pragma once

#include "bm25_index.hpp"
#include <vector>
#include <string>
#include <utility>

namespace grisha {

/**
 * Result from semantic search (ChromaDB).
 */
struct SemanticResult {
    std::string doc_id;
    double distance;  // Lower is better for ChromaDB L2 distance

    SemanticResult() : distance(0.0) {}
    SemanticResult(const std::string& id, double dist) : doc_id(id), distance(dist) {}
};

/**
 * Combined hybrid search result.
 */
struct HybridResult {
    std::string doc_id;
    double rrf_score;        // Reciprocal Rank Fusion score
    double semantic_score;   // Normalized semantic score (1 / (1 + distance))
    double bm25_score;       // Raw BM25 score
    int semantic_rank;       // Rank in semantic results (0 if not present)
    int bm25_rank;          // Rank in BM25 results (0 if not present)

    HybridResult()
        : rrf_score(0.0), semantic_score(0.0), bm25_score(0.0),
          semantic_rank(0), bm25_rank(0) {}

    bool operator<(const HybridResult& other) const {
        return rrf_score > other.rrf_score;  // Higher score = better
    }
};

/**
 * Hybrid search combining semantic (ChromaDB) and keyword (BM25) retrieval
 * using Reciprocal Rank Fusion (RRF).
 *
 * RRF score: score(d) = sum_{r in ranks} 1 / (k + r)
 *
 * where k is a constant (default 60) that controls how much to
 * favor top-ranked documents vs. lower-ranked ones.
 */
class HybridSearch {
public:
    /**
     * Create hybrid search with RRF parameter.
     * @param rrf_k RRF constant (default: 60.0)
     * @param semantic_weight Weight for semantic results (default: 0.5)
     * @param bm25_weight Weight for BM25 results (default: 0.5)
     */
    explicit HybridSearch(double rrf_k = 60.0,
                          double semantic_weight = 0.5,
                          double bm25_weight = 0.5);

    /**
     * Perform hybrid search combining semantic and BM25 results.
     *
     * @param index BM25 index
     * @param query Query text
     * @param semantic_results Results from ChromaDB semantic search
     * @param top_k Number of results to return
     * @return Vector of hybrid results, sorted by RRF score descending
     */
    std::vector<HybridResult> search(
        const BM25Index& index,
        const std::string& query,
        const std::vector<SemanticResult>& semantic_results,
        size_t top_k
    ) const;

    /**
     * Set RRF parameter.
     */
    void set_rrf_k(double k) { rrf_k_ = k; }
    double get_rrf_k() const { return rrf_k_; }

    /**
     * Set weights for combining semantic and BM25 scores.
     */
    void set_weights(double semantic_weight, double bm25_weight);
    double get_semantic_weight() const { return semantic_weight_; }
    double get_bm25_weight() const { return bm25_weight_; }

private:
    double rrf_k_;
    double semantic_weight_;
    double bm25_weight_;

    // Calculate RRF score for a rank
    double rrf_score(int rank) const;
};

}  // namespace grisha
