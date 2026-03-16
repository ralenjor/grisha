#include "bm25_index.hpp"
#include "mmap_storage.hpp"

#include <cmath>
#include <algorithm>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <filesystem>

namespace grisha {

namespace fs = std::filesystem;

BM25Index::BM25Index(double k1, double b)
    : k1_(k1), b_(b) {}

void BM25Index::add_document(const std::string& external_id, const std::string& text) {
    std::lock_guard<std::mutex> lock(mutex_);

    if (finalized_) {
        throw std::runtime_error("Cannot add documents to finalized index");
    }

    // Check for duplicate
    if (external_to_internal_.count(external_id)) {
        return;  // Skip duplicates
    }

    uint32_t internal_id = static_cast<uint32_t>(doc_count_);

    // Get term frequencies
    auto term_freqs = tokenizer_.get_term_frequencies(text);

    // Calculate document length
    uint32_t doc_length = 0;
    for (const auto& [term, freq] : term_freqs) {
        doc_length += freq;
    }

    // Add to inverted index
    for (const auto& [term, freq] : term_freqs) {
        // Add term to vocabulary if new
        if (vocabulary_.find(term) == vocabulary_.end()) {
            vocabulary_[term] = static_cast<uint32_t>(vocabulary_.size());
        }

        // Add posting
        inverted_index_[term].add(internal_id, freq);
    }

    // Store document metadata
    doc_lengths_.push_back(doc_length);
    external_ids_.push_back(external_id);
    external_to_internal_[external_id] = internal_id;

    total_tokens_ += doc_length;
    doc_count_++;
}

void BM25Index::finalize() {
    std::lock_guard<std::mutex> lock(mutex_);

    if (doc_count_ == 0) {
        avg_doc_length_ = 0.0;
    } else {
        avg_doc_length_ = static_cast<double>(total_tokens_) / doc_count_;
    }

    finalized_ = true;
}

double BM25Index::calculate_idf(size_t doc_freq) const {
    // IDF = log((N - df + 0.5) / (df + 0.5) + 1)
    double N = static_cast<double>(doc_count_);
    double df = static_cast<double>(doc_freq);
    return std::log((N - df + 0.5) / (df + 0.5) + 1.0);
}

double BM25Index::calculate_term_score(uint32_t term_freq, uint32_t doc_length, size_t doc_freq) const {
    double tf = static_cast<double>(term_freq);
    double dl = static_cast<double>(doc_length);
    double avgdl = avg_doc_length_;

    double idf = calculate_idf(doc_freq);

    // BM25 term score
    double numerator = tf * (k1_ + 1.0);
    double denominator = tf + k1_ * (1.0 - b_ + b_ * (dl / avgdl));

    return idf * (numerator / denominator);
}

std::vector<BM25Result> BM25Index::search(const std::string& query, size_t top_k) const {
    if (!finalized_) {
        throw std::runtime_error("Index must be finalized before searching");
    }

    if (doc_count_ == 0) {
        return {};
    }

    // Tokenize query
    auto query_tokens = tokenizer_.tokenize(query);

    if (query_tokens.empty()) {
        return {};
    }

    // Score accumulator for each document
    std::vector<double> scores(doc_count_, 0.0);

    // Process each query term
    for (const auto& term : query_tokens) {
        auto it = inverted_index_.find(term);
        if (it == inverted_index_.end()) {
            continue;  // Term not in index
        }

        const auto& posting_list = it->second;
        size_t doc_freq = posting_list.document_frequency();

        // Score each document containing this term
        for (const auto& posting : posting_list.get_postings()) {
            uint32_t doc_id = posting.doc_id;
            uint32_t tf = posting.term_freq;
            uint32_t doc_length = doc_lengths_[doc_id];

            scores[doc_id] += calculate_term_score(tf, doc_length, doc_freq);
        }
    }

    // Find top-k documents
    std::vector<std::pair<double, uint32_t>> scored_docs;
    scored_docs.reserve(doc_count_);

    for (uint32_t i = 0; i < doc_count_; i++) {
        if (scores[i] > 0.0) {
            scored_docs.emplace_back(scores[i], i);
        }
    }

    // Partial sort for top-k
    size_t k = std::min(top_k, scored_docs.size());
    std::partial_sort(
        scored_docs.begin(),
        scored_docs.begin() + k,
        scored_docs.end(),
        [](const auto& a, const auto& b) { return a.first > b.first; }
    );

    // Build results
    std::vector<BM25Result> results;
    results.reserve(k);

    for (size_t i = 0; i < k; i++) {
        uint32_t internal_id = scored_docs[i].second;
        results.emplace_back(
            external_ids_[internal_id],
            scored_docs[i].first,
            internal_id
        );
    }

    return results;
}

const std::string& BM25Index::get_external_id(uint32_t internal_id) const {
    if (internal_id >= external_ids_.size()) {
        throw std::out_of_range("Invalid internal document ID");
    }
    return external_ids_[internal_id];
}

void BM25Index::save(const std::string& path) const {
    if (!finalized_) {
        throw std::runtime_error("Index must be finalized before saving");
    }

    // Create directory if it doesn't exist
    fs::create_directories(path);

    // 1. Write metadata
    {
        std::ofstream meta_file(fs::path(path) / IndexFormat::META_FILE, std::ios::binary);
        if (!meta_file) {
            throw std::runtime_error("Failed to create metadata file");
        }

        IndexMeta meta;
        meta.doc_count = static_cast<uint32_t>(doc_count_);
        meta.vocab_size = static_cast<uint32_t>(vocabulary_.size());
        meta.total_tokens = total_tokens_;
        meta.avg_doc_length = avg_doc_length_;
        meta.k1 = k1_;
        meta.b = b_;

        meta_file.write(reinterpret_cast<const char*>(&meta), sizeof(IndexMeta));
    }

    // 2. Write vocabulary (term -> posting offset mapping)
    {
        std::ofstream vocab_file(fs::path(path) / IndexFormat::VOCAB_FILE, std::ios::binary);
        if (!vocab_file) {
            throw std::runtime_error("Failed to create vocabulary file");
        }

        // Write number of terms
        uint32_t vocab_size = static_cast<uint32_t>(vocabulary_.size());
        vocab_file.write(reinterpret_cast<const char*>(&vocab_size), sizeof(uint32_t));

        // Write terms sorted by term_id for deterministic output
        std::vector<std::pair<std::string, uint32_t>> sorted_vocab(vocabulary_.begin(), vocabulary_.end());
        std::sort(sorted_vocab.begin(), sorted_vocab.end(),
                  [](const auto& a, const auto& b) { return a.second < b.second; });

        for (const auto& [term, term_id] : sorted_vocab) {
            uint32_t term_len = static_cast<uint32_t>(term.size());
            vocab_file.write(reinterpret_cast<const char*>(&term_len), sizeof(uint32_t));
            vocab_file.write(term.data(), term_len);
        }
    }

    // 3. Write postings
    {
        std::ofstream postings_file(fs::path(path) / IndexFormat::POSTINGS_FILE, std::ios::binary);
        if (!postings_file) {
            throw std::runtime_error("Failed to create postings file");
        }

        // Build offset table
        std::vector<uint64_t> offsets;
        offsets.reserve(vocabulary_.size());

        // First pass: collect all serialized posting lists
        std::vector<std::pair<std::string, std::vector<uint8_t>>> serialized_lists;
        serialized_lists.reserve(inverted_index_.size());

        for (const auto& [term, posting_list] : inverted_index_) {
            serialized_lists.emplace_back(term, posting_list.serialize());
        }

        // Sort by vocabulary order
        std::sort(serialized_lists.begin(), serialized_lists.end(),
                  [this](const auto& a, const auto& b) {
                      return vocabulary_.at(a.first) < vocabulary_.at(b.first);
                  });

        // Calculate total size for offset table
        uint64_t header_size = sizeof(uint32_t) + vocabulary_.size() * sizeof(uint64_t);
        uint64_t current_offset = header_size;

        for (const auto& [term, data] : serialized_lists) {
            offsets.push_back(current_offset);
            current_offset += data.size();
        }

        // Write number of posting lists
        uint32_t num_lists = static_cast<uint32_t>(serialized_lists.size());
        postings_file.write(reinterpret_cast<const char*>(&num_lists), sizeof(uint32_t));

        // Write offset table
        postings_file.write(reinterpret_cast<const char*>(offsets.data()),
                            offsets.size() * sizeof(uint64_t));

        // Write posting list data
        for (const auto& [term, data] : serialized_lists) {
            postings_file.write(reinterpret_cast<const char*>(data.data()), data.size());
        }
    }

    // 4. Write document lengths
    {
        std::ofstream doclens_file(fs::path(path) / IndexFormat::DOCLENS_FILE, std::ios::binary);
        if (!doclens_file) {
            throw std::runtime_error("Failed to create document lengths file");
        }

        doclens_file.write(reinterpret_cast<const char*>(doc_lengths_.data()),
                           doc_lengths_.size() * sizeof(uint32_t));
    }

    // 5. Write external IDs
    {
        std::ofstream extids_file(fs::path(path) / IndexFormat::EXTIDS_FILE, std::ios::binary);
        if (!extids_file) {
            throw std::runtime_error("Failed to create external IDs file");
        }

        for (const auto& id : external_ids_) {
            uint32_t id_len = static_cast<uint32_t>(id.size());
            extids_file.write(reinterpret_cast<const char*>(&id_len), sizeof(uint32_t));
            extids_file.write(id.data(), id_len);
        }
    }
}

void BM25Index::load(const std::string& path) {
    clear();

    // 1. Load metadata
    {
        std::ifstream meta_file(fs::path(path) / IndexFormat::META_FILE, std::ios::binary);
        if (!meta_file) {
            throw std::runtime_error("Failed to open metadata file");
        }

        IndexMeta meta;
        meta_file.read(reinterpret_cast<char*>(&meta), sizeof(IndexMeta));

        if (meta.magic != IndexFormat::MAGIC) {
            throw std::runtime_error("Invalid index file format");
        }
        if (meta.version != IndexFormat::VERSION) {
            throw std::runtime_error("Unsupported index version");
        }

        doc_count_ = meta.doc_count;
        total_tokens_ = meta.total_tokens;
        avg_doc_length_ = meta.avg_doc_length;
        k1_ = meta.k1;
        b_ = meta.b;
    }

    // 2. Load vocabulary
    {
        std::ifstream vocab_file(fs::path(path) / IndexFormat::VOCAB_FILE, std::ios::binary);
        if (!vocab_file) {
            throw std::runtime_error("Failed to open vocabulary file");
        }

        uint32_t vocab_size;
        vocab_file.read(reinterpret_cast<char*>(&vocab_size), sizeof(uint32_t));

        for (uint32_t i = 0; i < vocab_size; i++) {
            uint32_t term_len;
            vocab_file.read(reinterpret_cast<char*>(&term_len), sizeof(uint32_t));

            std::string term(term_len, '\0');
            vocab_file.read(&term[0], term_len);

            vocabulary_[term] = i;
        }
    }

    // 3. Load postings
    {
        std::ifstream postings_file(fs::path(path) / IndexFormat::POSTINGS_FILE, std::ios::binary);
        if (!postings_file) {
            throw std::runtime_error("Failed to open postings file");
        }

        uint32_t num_lists;
        postings_file.read(reinterpret_cast<char*>(&num_lists), sizeof(uint32_t));

        // Read offset table
        std::vector<uint64_t> offsets(num_lists);
        postings_file.read(reinterpret_cast<char*>(offsets.data()),
                           num_lists * sizeof(uint64_t));

        // Read entire postings data
        postings_file.seekg(0, std::ios::end);
        size_t file_size = postings_file.tellg();
        size_t header_size = sizeof(uint32_t) + num_lists * sizeof(uint64_t);
        size_t data_size = file_size - header_size;

        std::vector<uint8_t> postings_data(data_size);
        postings_file.seekg(header_size);
        postings_file.read(reinterpret_cast<char*>(postings_data.data()), data_size);

        // Build reverse vocabulary (term_id -> term)
        std::vector<std::string> id_to_term(vocabulary_.size());
        for (const auto& [term, id] : vocabulary_) {
            id_to_term[id] = term;
        }

        // Deserialize posting lists
        for (uint32_t i = 0; i < num_lists; i++) {
            size_t start = offsets[i] - header_size;
            size_t end = (i + 1 < num_lists) ? offsets[i + 1] - header_size : data_size;
            size_t list_size = end - start;

            const std::string& term = id_to_term[i];
            inverted_index_[term] = PostingList::deserialize(
                postings_data.data() + start, list_size);
        }
    }

    // 4. Load document lengths
    {
        std::ifstream doclens_file(fs::path(path) / IndexFormat::DOCLENS_FILE, std::ios::binary);
        if (!doclens_file) {
            throw std::runtime_error("Failed to open document lengths file");
        }

        doc_lengths_.resize(doc_count_);
        doclens_file.read(reinterpret_cast<char*>(doc_lengths_.data()),
                          doc_count_ * sizeof(uint32_t));
    }

    // 5. Load external IDs
    {
        std::ifstream extids_file(fs::path(path) / IndexFormat::EXTIDS_FILE, std::ios::binary);
        if (!extids_file) {
            throw std::runtime_error("Failed to open external IDs file");
        }

        external_ids_.reserve(doc_count_);
        for (size_t i = 0; i < doc_count_; i++) {
            uint32_t id_len;
            extids_file.read(reinterpret_cast<char*>(&id_len), sizeof(uint32_t));

            std::string id(id_len, '\0');
            extids_file.read(&id[0], id_len);

            external_ids_.push_back(id);
            external_to_internal_[id] = static_cast<uint32_t>(i);
        }
    }

    finalized_ = true;
}

void BM25Index::clear() {
    std::lock_guard<std::mutex> lock(mutex_);

    inverted_index_.clear();
    vocabulary_.clear();
    doc_lengths_.clear();
    external_ids_.clear();
    external_to_internal_.clear();

    doc_count_ = 0;
    total_tokens_ = 0;
    avg_doc_length_ = 0.0;
    finalized_ = false;
}

}  // namespace grisha
