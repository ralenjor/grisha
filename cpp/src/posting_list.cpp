#include "posting_list.hpp"

#include <stdexcept>

namespace grisha {

// ============================================================================
// VByte Codec Implementation
// ============================================================================

void VByteCodec::encode_single(uint32_t value, std::vector<uint8_t>& output) {
    while (value >= 128) {
        output.push_back(static_cast<uint8_t>(value & 0x7F));
        value >>= 7;
    }
    output.push_back(static_cast<uint8_t>(value | 0x80));  // Set continuation bit
}

uint32_t VByteCodec::decode_single(const uint8_t* data, size_t& pos) {
    uint32_t value = 0;
    int shift = 0;

    while (true) {
        uint8_t byte = data[pos++];
        value |= static_cast<uint32_t>(byte & 0x7F) << shift;

        if (byte & 0x80) {
            // This is the last byte
            return value;
        }
        shift += 7;

        if (shift >= 35) {
            throw std::runtime_error("VByte decode overflow");
        }
    }
}

std::vector<uint8_t> VByteCodec::encode(const std::vector<uint32_t>& values) {
    std::vector<uint8_t> output;
    output.reserve(values.size() * 2);  // Estimate 2 bytes per value

    for (uint32_t value : values) {
        encode_single(value, output);
    }

    return output;
}

std::vector<uint32_t> VByteCodec::decode(const std::vector<uint8_t>& data) {
    std::vector<uint32_t> values;
    size_t pos = 0;

    while (pos < data.size()) {
        values.push_back(decode_single(data.data(), pos));
    }

    return values;
}

// ============================================================================
// Posting List Implementation
// ============================================================================

void PostingList::add(uint32_t doc_id, uint32_t term_freq) {
    // Maintain sorted order by doc_id
    // (assuming documents are added in order, which they typically are)
    postings_.emplace_back(doc_id, term_freq);
}

std::vector<uint8_t> PostingList::serialize() const {
    std::vector<uint8_t> output;

    // First, encode the number of postings
    VByteCodec::encode_single(static_cast<uint32_t>(postings_.size()), output);

    if (postings_.empty()) {
        return output;
    }

    // Delta-encode doc IDs and encode term frequencies
    uint32_t prev_doc_id = 0;

    for (const auto& posting : postings_) {
        // Delta-encode doc_id
        uint32_t delta = posting.doc_id - prev_doc_id;
        VByteCodec::encode_single(delta, output);
        prev_doc_id = posting.doc_id;

        // Encode term frequency
        VByteCodec::encode_single(posting.term_freq, output);
    }

    return output;
}

PostingList PostingList::deserialize(const std::vector<uint8_t>& data) {
    return deserialize(data.data(), data.size());
}

PostingList PostingList::deserialize(const uint8_t* data, size_t size) {
    PostingList list;

    if (size == 0) {
        return list;
    }

    size_t pos = 0;

    // Decode number of postings
    uint32_t count = VByteCodec::decode_single(data, pos);

    list.postings_.reserve(count);

    // Decode delta-encoded doc IDs and term frequencies
    uint32_t prev_doc_id = 0;

    for (uint32_t i = 0; i < count && pos < size; i++) {
        uint32_t delta = VByteCodec::decode_single(data, pos);
        uint32_t doc_id = prev_doc_id + delta;
        prev_doc_id = doc_id;

        uint32_t term_freq = VByteCodec::decode_single(data, pos);

        list.postings_.emplace_back(doc_id, term_freq);
    }

    return list;
}

}  // namespace grisha
