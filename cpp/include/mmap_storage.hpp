#pragma once

#include <string>
#include <cstdint>
#include <cstddef>
#include <memory>

namespace grisha {

/**
 * Memory-mapped file for efficient index storage.
 * Provides cross-platform support for Unix mmap and Windows MapViewOfFile.
 */
class MMapFile {
public:
    MMapFile();
    ~MMapFile();

    // Disable copy
    MMapFile(const MMapFile&) = delete;
    MMapFile& operator=(const MMapFile&) = delete;

    // Allow move
    MMapFile(MMapFile&& other) noexcept;
    MMapFile& operator=(MMapFile&& other) noexcept;

    /**
     * Open a file for reading.
     * @param path File path
     * @return true if successful
     */
    bool open_read(const std::string& path);

    /**
     * Create a file for writing with specified size.
     * @param path File path
     * @param size File size in bytes
     * @return true if successful
     */
    bool open_write(const std::string& path, size_t size);

    /**
     * Close the file and unmap memory.
     */
    void close();

    /**
     * Check if file is open.
     */
    bool is_open() const { return data_ != nullptr; }

    /**
     * Get pointer to mapped data.
     */
    const uint8_t* data() const { return data_; }
    uint8_t* data() { return data_; }

    /**
     * Get file size.
     */
    size_t size() const { return size_; }

    /**
     * Sync changes to disk (for writable files).
     */
    void sync();

private:
    uint8_t* data_ = nullptr;
    size_t size_ = 0;

#ifdef _WIN32
    void* file_handle_ = nullptr;
    void* map_handle_ = nullptr;
#else
    int fd_ = -1;
#endif
};

/**
 * Index file format constants.
 */
namespace IndexFormat {
    // Magic number for index files
    constexpr uint32_t MAGIC = 0x47524953;  // "GRIS"
    constexpr uint32_t VERSION = 1;

    // File names
    constexpr const char* META_FILE = "index.meta";
    constexpr const char* VOCAB_FILE = "vocabulary.bin";
    constexpr const char* POSTINGS_FILE = "postings.bin";
    constexpr const char* DOCLENS_FILE = "doc_lengths.bin";
    constexpr const char* EXTIDS_FILE = "external_ids.bin";
}

/**
 * Index metadata header.
 */
struct IndexMeta {
    uint32_t magic = IndexFormat::MAGIC;
    uint32_t version = IndexFormat::VERSION;
    uint32_t doc_count = 0;
    uint32_t vocab_size = 0;
    uint64_t total_tokens = 0;
    double avg_doc_length = 0.0;
    double k1 = 1.2;
    double b = 0.75;

    // Reserved for future use
    uint8_t reserved[32] = {0};
};

}  // namespace grisha
