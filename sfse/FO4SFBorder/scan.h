// scan.h: the platform-free half of FO4SFBorder (docs/terrain/border.md, "Per-world switch"). Header-only so the same
// code compiles into the dll (mingw-w64 or MSVC) and into tests/sfse_border_scan_test.cpp on Linux.
//
// 1. find_setting_candidates: where the game keeps the INI setting "bBorderRegionsEnabled:General". A Bethesda
//    Setting is assumed to hold a pointer to its own name string; the image is searched for the NUL-terminated name,
//    then the writable sections for 8-byte values equal to that string's address. Each hit is a candidate; the value
//    byte sits a few bytes before the name pointer. Which offset is the value is NOT assumed: the probe mode watches
//    the bytes before every candidate and logs each change, so typing SetINI in the console shows it.
// 2. parse_signal: the newest "border=off" / "border=on" token in new text from FO4SF_MapMarkers' user log.
// 3. parse_value_offset: the signed byte offset from the ini. Windows GetPrivateProfileInt returns 0 for every
//    negative number, so "ValueOffset=-16" cannot be read with it.
#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace fo4sfborder {

constexpr const char* kSettingName = "bBorderRegionsEnabled:General";

struct Region {
    std::uintptr_t base;     // address the bytes are mapped at
    const std::uint8_t* data;
    std::size_t size;
    bool writable;
};

struct Candidate {
    std::uintptr_t string_addr;    // the name string
    std::uintptr_t pointer_addr;   // the 8 bytes that hold string_addr (inside a writable region)
};

// Every start of `needle` (including its NUL) in the regions.
inline std::vector<std::uintptr_t> find_strings(const std::vector<Region>& regions, const char* needle) {
    std::vector<std::uintptr_t> out;
    const std::size_t n = std::strlen(needle) + 1;
    for (const Region& r : regions) {
        if (r.size < n) continue;
        for (std::size_t i = 0; i + n <= r.size; ++i) {
            if (r.data[i] == static_cast<std::uint8_t>(needle[0]) && std::memcmp(r.data + i, needle, n) == 0) {
                out.push_back(r.base + i);
            }
        }
    }
    return out;
}

// Every 8-aligned 8-byte value in a writable region that equals one of `targets`.
inline std::vector<Candidate> find_pointers(const std::vector<Region>& regions, const std::vector<std::uintptr_t>& targets) {
    std::vector<Candidate> out;
    if (targets.empty()) return out;
    for (const Region& r : regions) {
        if (!r.writable) continue;
        std::size_t start = (8 - (r.base % 8)) % 8;
        for (std::size_t i = start; i + 8 <= r.size; i += 8) {
            std::uint64_t v;
            std::memcpy(&v, r.data + i, 8);
            for (std::uintptr_t t : targets) {
                if (v == static_cast<std::uint64_t>(t)) out.push_back({t, r.base + i});
            }
        }
    }
    return out;
}

inline std::vector<Candidate> find_setting_candidates(const std::vector<Region>& regions) {
    return find_pointers(regions, find_strings(regions, kSettingName));
}

// The newest border token in `text`: 0 = "border=off" (switch the border off), 1 = "border=on", -1 = none.
inline int parse_signal(const std::string& text) {
    const std::size_t off = text.rfind("border=off");
    const std::size_t on = text.rfind("border=on");
    if (off == std::string::npos && on == std::string::npos) return -1;
    if (off == std::string::npos) return 1;
    if (on == std::string::npos) return 0;
    return off > on ? 0 : 1;
}

// The complete lines of `carry` + `chunk` (up to and including the last newline); what follows the last newline is
// kept in `carry` for the next read, so a token split across two reads is still seen whole.
inline std::string complete_lines(std::string& carry, const std::string& chunk) {
    std::string all = carry + chunk;
    const std::size_t nl = all.rfind('\n');
    if (nl == std::string::npos) {
        carry = all;
        return std::string();
    }
    carry = all.substr(nl + 1);
    return all.substr(0, nl + 1);
}

// Signed offset of the setting's value byte, in [-watch_bytes, -1]. Anything else (blank, not an integer,
// zero, positive, or further back than the probe watches) is `fallback`.
//
// Do not feed this through GetPrivateProfileInt: its return is unsigned, and a negative ini value comes back as 0
// (Win32 docs), so ValueOffset=-16 would be thrown away and only the fallback would remain.
inline int parse_value_offset(const std::string& text, int fallback, int watch_bytes) {
    if (watch_bytes < 1) return fallback;
    std::size_t a = 0, b = text.size();
    while (a < b && (text[a] == ' ' || text[a] == '\t' || text[a] == '\r' || text[a] == '\n')) ++a;
    while (b > a && (text[b - 1] == ' ' || text[b - 1] == '\t' || text[b - 1] == '\r' || text[b - 1] == '\n')) --b;
    if (a >= b) return fallback;
    int sign = 1;
    if (text[a] == '+' || text[a] == '-') {
        if (text[a] == '-') sign = -1;
        ++a;
        if (a >= b) return fallback;
    }
    long v = 0;
    for (std::size_t i = a; i < b; ++i) {
        if (text[i] < '0' || text[i] > '9') return fallback;
        v = v * 10 + (text[i] - '0');
        if (v > 1000000L) return fallback;
    }
    v *= sign;
    if (v < -watch_bytes || v > -1) return fallback;
    return static_cast<int>(v);
}

}  // namespace fo4sfborder
