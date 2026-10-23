// SHA-256 (FIPS 180-4) for the FOCCSidecar probe plugin: the sidecar file-name rule and the body checksum mirror
// src/fo4sf/combined/sidecar.py, which uses Python's hashlib.sha256. Portable C++ (no Windows API), so the same
// source is compiled on Linux in the repo's offline check and on the owner's PC with cl.exe.
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace focc {

// Lower-case hex digest (64 characters) of `len` bytes at `data`.
std::string sha256_hex(const void* data, std::size_t len);

inline std::string sha256_hex(const std::string& s) { return sha256_hex(s.data(), s.size()); }

}  // namespace focc
