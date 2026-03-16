#pragma once

#include "tokenizer.hpp"
#include "posting_list.hpp"

#include <string>
#include <vector>
#include <unordered_map>
#include <memory>
#include <mutex>

namespace grisha {

/**
 * BM25 search result.
 */
struct BM25Result {
    std::string doc_id;   // External document ID (ChromaDB ID)
    double score;         // BM25 score
    uint32_t internal_id; // Internal document ID

    BM25Result() : score(0.0), internal_id(0) {}
    BM25Result(const std::string& id, double s, uint32_t iid)
        : doc_id(id), score(s), internal_id(iid) {}

    bool operator<(const BM25Result& other) const {
        return score > other.score;  // Higher score = better
    }
};

/**
 * BM25 Index for keyword-based document retrieval.
 *
 * Implements the Okapi BM25 ranking function:
 *   score(D, Q) = sum_{t in Q} IDF(t) * (f(t,D) * (k1 + 1)) / (f(t,D) + k1 * (1 - b + b * |D| / avgdl))
 *
 * where:
 *   - f(t,D) = term frequency of t in document D
 *   - |D| = document length (in tokens)
 *   - avgdl = average document length
 *   - k1, b = tuning parameters (default: k1=1.2, b=0.75)
 */
class BM25Index {
public:
    /**
     * Create an empty index with BM25 parameters.
     * @param k1 Term frequency saturation parameter (default: 1.2)
     * @param b Document length normalization (default: 0.75)
     */
    explicit BM25Index(double k1 = 1.2, double b = 0.75);

    ~BM25Index() = default;

    // Disable copy, allow move
    BM25Index(const BM25Index&) = delete;
    BM25Index& operator=(const BM25Index&) = delete;
    BM25Index(BM25Index&&) = default;
    BM25Index& operator=(BM25Index&&) = default;

    /**
     * Add a document to the index.
     * @param external_id External document ID (e.g., ChromaDB ID)
     * @param text Document text content
     */
    void add_document(const std::string& external_id, const std::string& text);

    /**
     * Finalize the index after adding all documents.
     * Must be called before searching.
     */
    void finalize();

    /**
     * Search the index with a query.
     * @param query Query text
     * @param top_k Number of results to return
     * @return Vector of BM25 results, sorted by score descending
     */
    std::vector<BM25Result> search(const std::string& query, size_t top_k) const;

    /**
     * Save the index to disk.
     * @param path Directory path to save index files
     */
    void save(const std::string& path) const;

    /**
     * Load an index from disk.
     * @param path Directory path containing index files
     */
    void load(const std::string& path);

    /**
     * Clear the index.
     */
    void clear();

    // Accessors
    size_t document_count() const { return doc_count_; }
    size_t vocabulary_size() const { return vocabulary_.size(); }
    double average_doc_length() const { return avg_doc_length_; }
    bool is_finalized() const { return finalized_; }

    // Get external ID from internal ID
    const std::string& get_external_id(uint32_t internal_id) const;

private:
    // BM25 parameters
    double k1_;
    double b_;

    // Index state
    bool finalized_ = false;
    size_t doc_count_ = 0;
    double avg_doc_length_ = 0.0;
    size_t total_tokens_ = 0;

    // Core data structures
    Tokenizer tokenizer_;
    std::unordered_map<std::string, PostingList> inverted_index_;
    std::unordered_map<std::string, uint32_t> vocabulary_;  // term -> term_id
    std::vector<uint32_t> doc_lengths_;                     // internal_id -> length
    std::vector<std::string> external_ids_;                 // internal_id -> external_id
    std::unordered_map<std::string, uint32_t> external_to_internal_;  // external_id -> internal_id

    // Thread safety for add_document
    mutable std::mutex mutex_;

    // Calculate IDF for a term
    double calculate_idf(size_t doc_freq) const;

    // Calculate BM25 score for a term in a document
    double calculate_term_score(uint32_t term_freq, uint32_t doc_length, size_t doc_freq) const;
};

}  // namespace grisha
