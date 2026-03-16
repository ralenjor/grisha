#include "mmap_storage.hpp"

#include <stdexcept>
#include <cstring>

#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#endif

namespace grisha {

MMapFile::MMapFile() = default;

MMapFile::~MMapFile() {
    close();
}

MMapFile::MMapFile(MMapFile&& other) noexcept
    : data_(other.data_), size_(other.size_)
#ifdef _WIN32
    , file_handle_(other.file_handle_), map_handle_(other.map_handle_)
#else
    , fd_(other.fd_)
#endif
{
    other.data_ = nullptr;
    other.size_ = 0;
#ifdef _WIN32
    other.file_handle_ = nullptr;
    other.map_handle_ = nullptr;
#else
    other.fd_ = -1;
#endif
}

MMapFile& MMapFile::operator=(MMapFile&& other) noexcept {
    if (this != &other) {
        close();

        data_ = other.data_;
        size_ = other.size_;
#ifdef _WIN32
        file_handle_ = other.file_handle_;
        map_handle_ = other.map_handle_;
        other.file_handle_ = nullptr;
        other.map_handle_ = nullptr;
#else
        fd_ = other.fd_;
        other.fd_ = -1;
#endif
        other.data_ = nullptr;
        other.size_ = 0;
    }
    return *this;
}

#ifdef _WIN32

bool MMapFile::open_read(const std::string& path) {
    close();

    file_handle_ = CreateFileA(
        path.c_str(),
        GENERIC_READ,
        FILE_SHARE_READ,
        nullptr,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        nullptr
    );

    if (file_handle_ == INVALID_HANDLE_VALUE) {
        file_handle_ = nullptr;
        return false;
    }

    LARGE_INTEGER file_size;
    if (!GetFileSizeEx(file_handle_, &file_size)) {
        CloseHandle(file_handle_);
        file_handle_ = nullptr;
        return false;
    }

    size_ = static_cast<size_t>(file_size.QuadPart);

    if (size_ == 0) {
        CloseHandle(file_handle_);
        file_handle_ = nullptr;
        return true;  // Empty file is valid
    }

    map_handle_ = CreateFileMappingA(
        file_handle_,
        nullptr,
        PAGE_READONLY,
        0, 0,
        nullptr
    );

    if (!map_handle_) {
        CloseHandle(file_handle_);
        file_handle_ = nullptr;
        return false;
    }

    data_ = static_cast<uint8_t*>(MapViewOfFile(
        map_handle_,
        FILE_MAP_READ,
        0, 0, 0
    ));

    if (!data_) {
        CloseHandle(map_handle_);
        CloseHandle(file_handle_);
        map_handle_ = nullptr;
        file_handle_ = nullptr;
        return false;
    }

    return true;
}

bool MMapFile::open_write(const std::string& path, size_t size) {
    close();

    if (size == 0) {
        return true;  // Nothing to write
    }

    file_handle_ = CreateFileA(
        path.c_str(),
        GENERIC_READ | GENERIC_WRITE,
        0,
        nullptr,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr
    );

    if (file_handle_ == INVALID_HANDLE_VALUE) {
        file_handle_ = nullptr;
        return false;
    }

    size_ = size;

    map_handle_ = CreateFileMappingA(
        file_handle_,
        nullptr,
        PAGE_READWRITE,
        static_cast<DWORD>(size >> 32),
        static_cast<DWORD>(size & 0xFFFFFFFF),
        nullptr
    );

    if (!map_handle_) {
        CloseHandle(file_handle_);
        file_handle_ = nullptr;
        return false;
    }

    data_ = static_cast<uint8_t*>(MapViewOfFile(
        map_handle_,
        FILE_MAP_ALL_ACCESS,
        0, 0, size
    ));

    if (!data_) {
        CloseHandle(map_handle_);
        CloseHandle(file_handle_);
        map_handle_ = nullptr;
        file_handle_ = nullptr;
        return false;
    }

    return true;
}

void MMapFile::close() {
    if (data_) {
        UnmapViewOfFile(data_);
        data_ = nullptr;
    }
    if (map_handle_) {
        CloseHandle(map_handle_);
        map_handle_ = nullptr;
    }
    if (file_handle_) {
        CloseHandle(file_handle_);
        file_handle_ = nullptr;
    }
    size_ = 0;
}

void MMapFile::sync() {
    if (data_) {
        FlushViewOfFile(data_, size_);
    }
}

#else  // Unix implementation

bool MMapFile::open_read(const std::string& path) {
    close();

    fd_ = ::open(path.c_str(), O_RDONLY);
    if (fd_ < 0) {
        return false;
    }

    struct stat st;
    if (fstat(fd_, &st) < 0) {
        ::close(fd_);
        fd_ = -1;
        return false;
    }

    size_ = static_cast<size_t>(st.st_size);

    if (size_ == 0) {
        return true;  // Empty file is valid
    }

    data_ = static_cast<uint8_t*>(mmap(
        nullptr, size_,
        PROT_READ,
        MAP_PRIVATE,
        fd_, 0
    ));

    if (data_ == MAP_FAILED) {
        data_ = nullptr;
        ::close(fd_);
        fd_ = -1;
        return false;
    }

    return true;
}

bool MMapFile::open_write(const std::string& path, size_t size) {
    close();

    if (size == 0) {
        return true;  // Nothing to write
    }

    fd_ = ::open(path.c_str(), O_RDWR | O_CREAT | O_TRUNC, 0644);
    if (fd_ < 0) {
        return false;
    }

    // Extend file to desired size
    if (ftruncate(fd_, static_cast<off_t>(size)) < 0) {
        ::close(fd_);
        fd_ = -1;
        return false;
    }

    size_ = size;

    data_ = static_cast<uint8_t*>(mmap(
        nullptr, size_,
        PROT_READ | PROT_WRITE,
        MAP_SHARED,
        fd_, 0
    ));

    if (data_ == MAP_FAILED) {
        data_ = nullptr;
        ::close(fd_);
        fd_ = -1;
        return false;
    }

    return true;
}

void MMapFile::close() {
    if (data_) {
        munmap(data_, size_);
        data_ = nullptr;
    }
    if (fd_ >= 0) {
        ::close(fd_);
        fd_ = -1;
    }
    size_ = 0;
}

void MMapFile::sync() {
    if (data_) {
        msync(data_, size_, MS_SYNC);
    }
}

#endif  // _WIN32

}  // namespace grisha
