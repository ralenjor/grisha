#include "hybrid_search.hpp"

#include <algorithm>
#include <unordered_map>

namespace grisha {

HybridSearch::HybridSearch(double rrf_k, double semantic_weight, double bm25_weight)
    : rrf_k_(rrf_k), semantic_weight_(semantic_weight), bm25_weight_(bm25_weight) {}

void HybridSearch::set_weights(double semantic_weight, double bm25_weight) {
    double total = semantic_weight + bm25_weight;
    if (total > 0) {
        semantic_weight_ = semantic_weight / total;
        bm25_weight_ = bm25_weight / total;
    }
}

double HybridSearch::rrf_score(int rank) const {
    if (rank <= 0) return 0.0;
    return 1.0 / (rrf_k_ + static_cast<double>(rank));
}

std::vector<HybridResult> HybridSearch::search(
    const BM25Index& index,
    const std::string& query,
    const std::vector<SemanticResult>& semantic_results,
    size_t top_k
) const {
    // Get BM25 results (retrieve more than needed for fusion)
    size_t bm25_k = std::max(top_k * 2, size_t(100));
    auto bm25_results = index.search(query, bm25_k);

    // Build result map keyed by doc_id
    std::unordered_map<std::string, HybridResult> result_map;

    // Process semantic results
    for (size_t i = 0; i < semantic_results.size(); i++) {
        const auto& sr = semantic_results[i];
        auto& hr = result_map[sr.doc_id];

        hr.doc_id = sr.doc_id;
        hr.semantic_rank = static_cast<int>(i + 1);
        hr.semantic_score = 1.0 / (1.0 + sr.distance);  // Convert distance to score
    }

    // Process BM25 results
    for (size_t i = 0; i < bm25_results.size(); i++) {
        const auto& br = bm25_results[i];
        auto& hr = result_map[br.doc_id];

        hr.doc_id = br.doc_id;
        hr.bm25_rank = static_cast<int>(i + 1);
        hr.bm25_score = br.score;
    }

    // Calculate RRF scores
    for (auto& [doc_id, hr] : result_map) {
        double semantic_rrf = semantic_weight_ * rrf_score(hr.semantic_rank);
        double bm25_rrf = bm25_weight_ * rrf_score(hr.bm25_rank);
        hr.rrf_score = semantic_rrf + bm25_rrf;
    }

    // Convert to vector and sort by RRF score
    std::vector<HybridResult> results;
    results.reserve(result_map.size());

    for (auto& [doc_id, hr] : result_map) {
        results.push_back(std::move(hr));
    }

    std::sort(results.begin(), results.end());

    // Return top-k
    if (results.size() > top_k) {
        results.resize(top_k);
    }

    return results;
}

}  // namespace grisha
