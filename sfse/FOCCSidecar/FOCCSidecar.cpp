// FOCCSidecar: the P1 probe plugin for SFSE (docs/spikes/combined-core-probes.md, engine-feasibility.md "PC probes").
//
// What it does, and nothing more:
//   - On kMessage_PreSaveGame it writes a sidecar file for the save name SFSE passes (codec.h mirrors
//     src/fo4sf/combined/sidecar.py: name rule, canonical JSON, checksum) with the stub world state
//     {"counter": k, "probe": "P1"}, k counting pre-save events in this process.
//   - On kMessage_PostLoadGame it reads the sidecar for the loaded save back and verifies it.
//   - Every event is appended as one JSON object per line to focc_sidecar.log, which group C's checker reads.
//   - It never deletes anything (SFSE sends no delete message; sidecar.orphans() lists orphans offline).
//   - Kill switch: without `bEnabled=1` under [FOCCSidecar] in FOCCSidecar.ini next to the dll it registers nothing
//     and writes nothing; SFSE's own log (sfse.log, "plugin FOCCSidecar.dll ...") is then the only trace it loaded.
//
// Interface: only SFSE's MIT-licensed sfse/PluginAPI.h (fetched by fetch_pluginapi.ps1 at a pinned commit, not
// committed). Facts taken from it (read 2026-10-21, commit 48535cc): SFSEPluginVersionData fields and the
// kAddressIndependence_/kStructureIndependence_ bits; SFSEInterface::QueryInterface and GetPluginHandle;
// SFSEMessagingInterface::RegisterListener(handle, "SFSE", cb) and Message {sender, type, dataLen, data};
// kMessage_PreSaveGame/PostSaveGame/PreLoadGame/PostLoadGame. The save-name payload is `(void*)a_name` with dataLen =
// strlen(a_name), a const char* (sfse/Hooks_Serialization.cpp lines 35-54, read, not copied). Whether that name is
// the save's display name or its file stem is UNVERIFIED: the log carries the raw bytes and their hex so the checker
// can compare with the .sfs names.
//
// Game addresses and structures are not touched at all, so the version data claims address and structure
// independence (kAddressIndependence_Signatures | kStructureIndependence_NoStructs); SFSE then loads the plugin on any
// runtime (PluginManager::checkPluginCompatibility, read upstream). compatibleVersions still names 1.16.244, the
// version SFSE 0.2.21 supports (sfse_whatsnew.txt), as documentation. No Address Library is needed.
//
// Files (all under <dll folder>\FOCCSidecar\): focc_sidecar.log, sidecars\<name>.focc. The dll folder is found with
// GetModuleFileNameW on this module, so nothing lands under Documents (Controlled Folder Access, make_bridge.py).
//
// Build: build.ps1 (cl.exe /std:c++20 /EHsc /LD FOCCSidecar.cpp sha256.cpp). This file cannot be compiled in the
// repo's Linux container (no Windows SDK); see README.md for what was and was not verified.

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>

#include "PluginAPI.h"
#include "codec.h"

namespace {

// MAKE_EXE_VERSION(1, 16, 244) as SFSE packs it: (major << 24) | (minor << 16) | (build << 4) | sub
// (sfse_common/sfse_version.h, read upstream; that file is not MIT, so the formula is restated, not copied).
constexpr std::uint32_t kRuntime_1_16_244 = (1u << 24) | (16u << 16) | (244u << 4);

constexpr std::uint32_t kPluginVersion = 1;
constexpr const wchar_t* kIniName = L"FOCCSidecar.ini";
constexpr const wchar_t* kSubdir = L"FOCCSidecar";
constexpr const wchar_t* kLogName = L"focc_sidecar.log";
constexpr const wchar_t* kSidecarDir = L"sidecars";

HMODULE g_module = nullptr;
PluginHandle g_handle = static_cast<PluginHandle>(kPluginHandle_Invalid);   // the enumerator is an int: C4245 without the cast
std::wstring g_dir;          // <dll folder>\FOCCSidecar
std::wstring g_sidecars;     // <dll folder>\FOCCSidecar\sidecars
std::mutex g_mutex;
long long g_counter = 0;     // pre-save events seen in this process (set from the sidecar on a valid load)
long long g_seq = 0;         // log line sequence

std::wstring widen_ascii(const std::string& s) {
    std::wstring w;
    w.reserve(s.size());
    for (unsigned char c : s) w.push_back(static_cast<wchar_t>(c));   // codec output is ASCII by construction
    return w;
}

std::string narrow_for_log(const std::wstring& w) {
    // UTF-8 for the log; the paths are ASCII in practice (our names) but the game folder may not be.
    int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), -1, nullptr, 0, nullptr, nullptr);
    std::string out;
    if (n > 1) {
        out.resize(static_cast<std::size_t>(n - 1));
        WideCharToMultiByte(CP_UTF8, 0, w.c_str(), -1, out.data(), n, nullptr, nullptr);
    }
    return out;
}

std::wstring module_dir() {
    wchar_t buf[MAX_PATH * 4];
    DWORD n = GetModuleFileNameW(g_module, buf, static_cast<DWORD>(sizeof(buf) / sizeof(buf[0])));
    if (n == 0 || n >= sizeof(buf) / sizeof(buf[0])) return L"";
    std::wstring path(buf, n);
    std::size_t slash = path.find_last_of(L"\\/");
    return slash == std::wstring::npos ? L"" : path.substr(0, slash);
}

std::string utc_now() {
    SYSTEMTIME st;
    GetSystemTime(&st);
    char buf[40];
    std::snprintf(buf, sizeof(buf), "%04u-%02u-%02uT%02u:%02u:%02u.%03uZ", st.wYear, st.wMonth, st.wDay, st.wHour,
                  st.wMinute, st.wSecond, st.wMilliseconds);
    return buf;
}

std::string hex32(std::uint32_t v) {
    char buf[16];
    std::snprintf(buf, sizeof(buf), "0x%08X", v);
    return buf;
}

// Append one line to the log (open, write at end, close: the game may be killed at any time and a partial line is
// the worst case). Failures are silent: there is no other place to report them.
void log_line(const std::string& jsonFields) {
    std::lock_guard<std::mutex> lock(g_mutex);
    ++g_seq;
    std::string line = "{\"seq\": " + std::to_string(g_seq) + ", \"time\": " + focc::json_string(utc_now()) + ", " +
                       jsonFields + "}\r\n";
    HANDLE h = CreateFileW((g_dir + L"\\" + kLogName).c_str(), FILE_APPEND_DATA, FILE_SHARE_READ, nullptr,
                           OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    WriteFile(h, line.data(), static_cast<DWORD>(line.size()), &written, nullptr);
    CloseHandle(h);
}

// Atomic write like sidecar.write: temp file in the same folder, flush, MoveFileExW with replace.
bool write_file_atomic(const std::wstring& path, const std::string& body, std::string& error) {
    std::wstring tmp = path + L".tmp";
    HANDLE h = CreateFileW(tmp.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) { error = "CreateFileW failed " + std::to_string(GetLastError()); return false; }
    DWORD written = 0;
    BOOL ok = WriteFile(h, body.data(), static_cast<DWORD>(body.size()), &written, nullptr);
    if (ok) ok = FlushFileBuffers(h);
    CloseHandle(h);
    if (!ok || written != body.size()) {
        error = "WriteFile failed " + std::to_string(GetLastError());
        DeleteFileW(tmp.c_str());   // our own temp file of this write, nothing else is ever removed
        return false;
    }
    if (!MoveFileExW(tmp.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        error = "MoveFileExW failed " + std::to_string(GetLastError());
        return false;
    }
    return true;
}

bool read_file(const std::wstring& path, std::string& out, std::string& error) {
    HANDLE h = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) {
        DWORD e = GetLastError();
        error = (e == ERROR_FILE_NOT_FOUND || e == ERROR_PATH_NOT_FOUND) ? "not found" : "CreateFileW failed " + std::to_string(e);
        return false;
    }
    LARGE_INTEGER size{};
    if (!GetFileSizeEx(h, &size) || size.QuadPart > (16 << 20)) {
        CloseHandle(h);
        error = "unreadable size";
        return false;
    }
    out.resize(static_cast<std::size_t>(size.QuadPart));
    DWORD got = 0;
    BOOL ok = out.empty() ? TRUE : ReadFile(h, out.data(), static_cast<DWORD>(out.size()), &got, nullptr);
    CloseHandle(h);
    if (!ok || got != out.size()) { error = "ReadFile failed " + std::to_string(GetLastError()); return false; }
    return true;
}

std::string save_name_of(const SFSEMessagingInterface::Message* msg) {
    if (!msg || !msg->data) return "";
    const char* p = static_cast<const char*>(msg->data);
    // dataLen is strlen(a_name) upstream; trust the shorter of dataLen and the terminator, never read past dataLen.
    std::size_t n = 0;
    while (n < msg->dataLen && p[n] != '\0') ++n;
    return std::string(p, n);
}

std::string name_fields(const std::string& save) {
    return "\"save\": " + focc::json_string(save) + ", \"save_hex\": " + focc::json_string(focc::hex_bytes(save));
}

void on_pre_save(const std::string& save) {
    if (save.empty()) { log_line("\"event\": \"pre_save\", \"error\": \"empty save name\""); return; }
    long long k;
    { std::lock_guard<std::mutex> lock(g_mutex); k = ++g_counter; }
    const std::string file = focc::sidecar_name(save);
    std::string error;
    bool ok = write_file_atomic(g_sidecars + L"\\" + widen_ascii(file), focc::encode_sidecar(save, k), error);
    log_line("\"event\": \"pre_save\", " + name_fields(save) + ", \"counter\": " + std::to_string(k) +
             ", \"file\": " + focc::json_string(file) + ", \"written\": " + (ok ? "true" : "false") +
             (ok ? "" : ", \"error\": " + focc::json_string(error)));
}

void on_post_load(const std::string& save) {
    if (save.empty()) { log_line("\"event\": \"post_load\", \"error\": \"empty save name\""); return; }
    const std::string file = focc::sidecar_name(save);
    std::string text, error;
    bool found = read_file(g_sidecars + L"\\" + widen_ascii(file), text, error);
    focc::Decoded d;
    if (found) d = focc::decode_sidecar(text, save);
    if (d.valid) { std::lock_guard<std::mutex> lock(g_mutex); g_counter = d.counter; }
    log_line("\"event\": \"post_load\", " + name_fields(save) + ", \"file\": " + focc::json_string(file) +
             ", \"found\": " + (found ? "true" : "false") + ", \"valid\": " + (d.valid ? "true" : "false") +
             ", \"counter\": " + std::to_string(d.valid ? d.counter : -1) +
             (found && !d.valid ? ", \"error\": " + focc::json_string(d.error) : "") +
             (!found ? ", \"error\": " + focc::json_string(error) : ""));
}

void OnSFSEMessage(SFSEMessagingInterface::Message* msg) {
    if (!msg) return;
    switch (msg->type) {
        case SFSEMessagingInterface::kMessage_PostLoad:
            log_line("\"event\": \"sfse_post_load\"");
            break;
        case SFSEMessagingInterface::kMessage_PreSaveGame:
            on_pre_save(save_name_of(msg));
            break;
        case SFSEMessagingInterface::kMessage_PostSaveGame:
            log_line("\"event\": \"post_save\", " + name_fields(save_name_of(msg)));
            break;
        case SFSEMessagingInterface::kMessage_PreLoadGame:
            log_line("\"event\": \"pre_load\", " + name_fields(save_name_of(msg)));
            break;
        case SFSEMessagingInterface::kMessage_PostLoadGame:
            on_post_load(save_name_of(msg));
            break;
        default:
            break;   // data-load messages carry pointers we do not look at
    }
}

bool enabled_by_ini() {
    // Kill switch: [FOCCSidecar] bEnabled=1 in <dll folder>\FOCCSidecar.ini. Missing file or key = disabled.
    std::wstring ini = module_dir() + L"\\" + kIniName;
    return GetPrivateProfileIntW(L"FOCCSidecar", L"bEnabled", 0, ini.c_str()) == 1;
}

}  // namespace

extern "C" {

__declspec(dllexport) SFSEPluginVersionData SFSEPlugin_Version = {
    SFSEPluginVersionData::kVersion,

    kPluginVersion,
    "FOCCSidecar",
    "fo4-to-starfield combined core probe",

    SFSEPluginVersionData::kAddressIndependence_Signatures,     // no game addresses used at all
    SFSEPluginVersionData::kStructureIndependence_NoStructs,    // no game structures used at all
    { kRuntime_1_16_244, 0 },                                    // documentation; ignored when version independent

    0,      // any SFSE version
    0, 0,   // reserved
};

__declspec(dllexport) bool SFSEPlugin_Load(const SFSEInterface* sfse) {
    if (!sfse) return false;
    if (!enabled_by_ini()) return true;   // loaded, idle, silent: the documented kill switch

    g_handle = sfse->GetPluginHandle();
    std::wstring base = module_dir();
    if (base.empty()) return true;
    g_dir = base + L"\\" + kSubdir;
    g_sidecars = g_dir + L"\\" + kSidecarDir;
    CreateDirectoryW(g_dir.c_str(), nullptr);        // existing folders are fine (ERROR_ALREADY_EXISTS)
    CreateDirectoryW(g_sidecars.c_str(), nullptr);

    auto* messaging = static_cast<SFSEMessagingInterface*>(sfse->QueryInterface(kInterface_Messaging));
    bool registered = false;
    if (messaging && messaging->interfaceVersion >= SFSEMessagingInterface::kInterfaceVersion) {
        registered = messaging->RegisterListener(g_handle, "SFSE", OnSFSEMessage);
    }
    log_line("\"event\": \"load\", \"plugin\": \"FOCCSidecar\", \"plugin_version\": " + std::to_string(kPluginVersion) +
             ", \"sfse_version\": " + focc::json_string(hex32(sfse->sfseVersion)) +
             ", \"runtime_version\": " + focc::json_string(hex32(sfse->runtimeVersion)) +
             ", \"interface_version\": " + std::to_string(sfse->interfaceVersion) +
             ", \"messaging\": " + (messaging ? "true" : "false") + ", \"registered\": " + (registered ? "true" : "false") +
             ", \"dir\": " + focc::json_string(narrow_for_log(g_dir)));
    return true;   // never refuse to load: a refusal would be reported by SFSE as an incompatibility we do not mean
}

}  // extern "C"

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_module = instance;
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
