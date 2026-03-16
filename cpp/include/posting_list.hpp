#pragma once

#include <vector>
#include <cstdint>
#include <cstddef>

namespace grisha {

/**
 * A posting represents a single document occurrence.
 */
struct Posting {
    uint32_t doc_id;      // Internal document ID
    uint32_t term_freq;   // Term frequency in this document

    Posting() : doc_id(0), term_freq(0) {}
    Posting(uint32_t id, uint32_t tf) : doc_id(id), term_freq(tf) {}
};

/**
 * VByte encoder/decoder for compact integer storage.
 */
class VByteCodec {
public:
    /**
     * Encode a vector of integers using VByte encoding.
     * @param values Input integers
     * @return Encoded bytes
     */
    static std::vector<uint8_t> encode(const std::vector<uint32_t>& values);

    /**
     * Decode VByte encoded data.
     * @param data Encoded bytes
     * @return Decoded integers
     */
    static std::vector<uint32_t> decode(const std::vector<uint8_t>& data);

    /**
     * Encode a single integer.
     */
    static void encode_single(uint32_t value, std::vector<uint8_t>& output);

    /**
     * Decode a single integer from a byte stream.
     * @param data Byte stream
     * @param pos Current position (will be updated)
     * @return Decoded integer
     */
    static uint32_t decode_single(const uint8_t* data, size_t& pos);
};

/**
 * A posting list stores all occurrences of a term.
 * Uses delta encoding for doc IDs and VByte compression.
 */
class PostingList {
public:
    PostingList() = default;

    /**
     * Add a posting to the list.
     * @param doc_id Document ID
     * @param term_freq Term frequency
     */
    void add(uint32_t doc_id, uint32_t term_freq);

    /**
     * Get all postings (decompressed).
     */
    const std::vector<Posting>& get_postings() const { return postings_; }

    /**
     * Get the number of documents containing this term (DF).
     */
    size_t document_frequency() const { return postings_.size(); }

    /**
     * Serialize the posting list to bytes.
     */
    std::vector<uint8_t> serialize() const;

    /**
     * Deserialize a posting list from bytes.
     */
    static PostingList deserialize(const std::vector<uint8_t>& data);

    /**
     * Deserialize from raw pointer (for memory-mapped access).
     */
    static PostingList deserialize(const uint8_t* data, size_t size);

private:
    std::vector<Posting> postings_;
};

}  // namespace grisha
