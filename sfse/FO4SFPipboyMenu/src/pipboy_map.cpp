#include "pch.h"

#include "pipboy_map.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <mutex>
#include <numbers>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

REX_W32_IMPORT(std::int16_t, GetAsyncKeyState, std::int32_t);
REX_W32_IMPORT(void*, GetForegroundWindow);
REX_W32_IMPORT(std::uint32_t, GetWindowThreadProcessId, void*, std::uint32_t*);
REX_W32_IMPORT(std::uint32_t, GetCurrentProcessId);

namespace
{
	using namespace std::string_view_literals;

	constexpr auto          kOurMenu = "FO4SF_PipboyMenu"sv;
	constexpr REL::Version  kRuntime{ 1, 16, 244, 0 };
	constexpr std::size_t   kHeaderBytes = 96;
	constexpr std::size_t   kCreateObjectSlot = 0x2E;   // RE::Scaleform::GFx::ASMovieRootBase::CreateObject
	constexpr std::size_t   kGetVariableSlot = 0x32;
	constexpr std::size_t   kDispatchStaticCallSlot = 0x2F;
	constexpr std::size_t   kGameVmImplAt = 0xE0;
	constexpr std::uint32_t kDataHandlerRva = 0x5FD9B28;
	constexpr std::uint32_t kLookupByIdRva = 0x5DE3B0;

	// Player & form offsets verified on Starfield 1.16.244 in main.cpp (FAL-272, FAL-301, FAL-595)
	constexpr std::size_t   kAngleZAt = 0x88;           // HeadingAt=88: player yaw in radians clockwise from North
	constexpr std::size_t   kPositionAt = 0x80 + 0x0C;  // OBJ_REFR::location (float x, y, z in Starfield metres)
	constexpr std::size_t   kParentCellAt = 0xB0;
	constexpr std::size_t   kCellWorldAt = 0x110;
	constexpr std::size_t   kFullNameAt = 0x08;
	constexpr std::size_t   kFormIdAt = 0x28;
	constexpr std::size_t   kGlobalValueAt = 0x48;      // TESGlobal float32 value slot (vmovss xmm0, [r8+0x48])
	constexpr std::size_t   kFileCollectionAt = 0x1580; // TESDataHandler::compiledFileCollection
	constexpr std::size_t   kFileNameAt = 0x38;
	constexpr std::size_t   kFileNameSize = 260;
	constexpr std::size_t   kFileCompileIndexAt = 0x1B7;
	constexpr std::size_t   kFileIndexAt = 0x218;
	constexpr std::size_t   kMaxFiles = 4096;

	constexpr std::uint32_t kGameHourId = 0x38;
	constexpr std::uint32_t kGameDaysPassedId = 0x39;

	// FO4SFPipboyTravel.esm local FormIDs (written by scripts/ui/pipboy_map_store.py)
	constexpr std::uint32_t kGlobTravelTarget = 0x800;  // target marker local FormID (< 2^24, exact in float32)
	constexpr std::uint32_t kGlobTravelPlugin = 0x801;  // 0 = FO4SFMapMarkers.esm, 1 = FO4TerrainCore.esm
	constexpr std::uint32_t kGlobSurvivalMode = 0x802;  // 0 = fast travel enabled, 1 = survival blocked
	constexpr std::uint32_t kGlobTravelIndex = 0x803;   // marker store index
	constexpr std::uint32_t kGlobTravelX = 0x804;       // merged arrival X (Starfield m)
	constexpr std::uint32_t kGlobTravelY = 0x805;       // merged arrival Y (Starfield m)
	constexpr std::uint32_t kGlobTravelZ = 0x806;       // merged arrival Z (Starfield m)
	constexpr std::uint32_t kGlobTravelH = 0x807;       // arrival heading (degrees)
	constexpr std::uint32_t kGlobDiscFirst = 0x810;     // FO4SF_MapDisc00..13 (24 bits per TESGlobal)
	constexpr std::size_t   kDiscGlobals = 14;
	constexpr std::size_t   kBitsPerGlobal = 24;        // float32 mantissa preserves 24 integer bits losslessly

	// Canonical Fallout 4 Commonwealth world-map corners (MNAM cells -33..28, 25..-36 -> outer cell edges in FO4 units)
	constexpr double        kCommonwealthNWX = -135168.0;
	constexpr double        kCommonwealthNWY = 106496.0;
	constexpr double        kCommonwealthNEX = 118784.0;
	constexpr double        kCommonwealthNEY = 106496.0;
	constexpr double        kCommonwealthSWX = -135168.0;
	constexpr double        kCommonwealthSWY = -147456.0;
	constexpr double        kWorldMapTextureField = 0.0;
	constexpr auto          kDefaultWorldTexture = "Textures/Interface/Pip-Boy/WorldMap_d.dds";

	// Inverse coordinate transform from merged Starfield metres to canonical FO4 Commonwealth units
	constexpr double        kMergeOffsetX = -1200.0;
	constexpr double        kMergeOffsetY = -2700.0;
	constexpr double        kFo4UnitsPerMetre = 70.0;

	// Special Pipboy_MapPage MarkerTypesA indices
	constexpr std::uint32_t kPlayerSetMarkerType = 85;
	constexpr std::uint32_t kPlayerLocMarkerType = 86;
	constexpr std::uint32_t kMaxMarkerType = 87;

	constexpr std::size_t   kMaxStoreMarkers = 512;
	constexpr std::size_t   kMaxMapMenus = 8;
	constexpr std::size_t   kMaxName = 64;
	constexpr std::uint32_t kMaxLogLines = 64;
	constexpr std::uint32_t kF10 = 0x79;
	constexpr std::uint32_t kQuickSaveKey = 0x74;
	constexpr std::uint32_t kQuickLoadKey = 0x78;

	enum MapIdIndex : std::size_t
	{
		kPlayerSingleton,
		kPlayerRtti,
		kGameVmSingleton,
		kGameVmRtti,
		kVmRtti,
		kDataHandlerSingleton,
		kLookupById,
		kMapIdCount
	};

	struct MapIdSpec
	{
		const char*      name;
		std::uint32_t    id;
		std::string_view rttiTail;
		std::uint32_t    expectedRva;
	};

	constexpr std::array<MapIdSpec, kMapIdCount> kMapIds{ {
		{ "PlayerCharacter.Singleton", 922868, {}, 0 },
		{ "PlayerCharacter.RTTI", 860819, "PlayerCharacter@@"sv, 0 },
		{ "GameVM.Singleton", 937585, {}, 0 },
		{ "GameVM.RTTI", 865426, "GameVM@@"sv, 0 },
		{ "BSScript.Internal.VirtualMachine.RTTI", 870795, "VirtualMachine@Internal@BSScript@@"sv, 0 },
		{ "TESDataHandler.Singleton", 937572, {}, kDataHandlerRva },
		{ "TESForm.LookupByID", 47401, {}, kLookupByIdRva },
	} };

	struct StoreMarker
	{
		std::uint32_t index = 0;
		std::uint32_t pluginCode = 0;   // 0 = FO4SFMapMarkers.esm, 1 = FO4TerrainCore.esm
		std::uint32_t localId = 0;
		std::uint32_t type = 0;
		bool          initialDiscovered = false;
		double        xFo4 = 0.0;
		double        yFo4 = 0.0;
		float         arrivalXSf = 0.0f;
		float         arrivalYSf = 0.0f;
		float         arrivalZSf = 0.0f;
		float         arrivalHeadingDeg = 0.0f;
		std::string   label;
	};

	struct LiveSnapshot
	{
		bool                                      havePlayer = false;
		double                                    playerXFo4 = -89271.7;
		double                                    playerYFo4 = 91369.6;
		double                                    playerHeadingDeg = 0.0;
		float                                     gameHour = 9.0f;
		std::uint32_t                             dateMonth = 10;
		std::uint32_t                             dateDay = 23;
		std::uint32_t                             dateYear = 2287;
		std::string                               locationName = "COMMONWEALTH";
		bool                                      liveSurvival = false;
		std::array<std::uint32_t, kDiscGlobals>   discBits{};
	};

	struct ArrayHead
	{
		std::uint32_t  size;
		std::uint32_t  capacity;
		std::uintptr_t data;
	};

	struct ObjectType
	{
		std::uintptr_t descriptor = 0;
		std::uintptr_t hierarchy = 0;
		std::uint32_t  offset = 0;
		std::string    name;
	};

	using LookupById_t = void* (*)(std::uint32_t);

	bool                                   g_on = false;
	std::uintptr_t                         g_base = 0;
	std::size_t                            g_imageSize = 0;
	std::array<std::uint32_t, kMapIdCount> g_rva{};
	const SFSE::TaskInterface*             g_task = nullptr;

	std::uint32_t                          g_mapKey = 0x4D;
	std::uint32_t                          g_mapPage = 3;
	bool                                   g_mapSurvival = false;
	std::string                            g_travelPlugin = "FO4SFPipboyTravel.esm";
	std::string                            g_travelScript = "FO4SF_PipboyTravel";
	std::string                            g_travelFunction = "Go";
	std::vector<std::string>               g_mapMenus;
	std::vector<StoreMarker>               g_store;

	std::atomic<bool>                      g_keyDown{ false };
	std::atomic<std::uint32_t>             g_keyPresses{ 0 };
	std::atomic<std::uint32_t>             g_suppressions{ 0 };
	std::atomic<std::uint32_t>             g_tickCount{ 0 };
	std::atomic<std::int32_t>              g_requestedPage{ -1 };
	std::atomic<std::int32_t>              g_requestedTab{ -1 };
	std::atomic<bool>                      g_markersDirty{ true };
	std::atomic<bool>                      g_needTexturesLoaded{ false };
	std::atomic<bool>                      g_needCenter{ false };
	std::atomic<bool>                      g_textureLogged{ false };
	std::atomic<bool>                      g_modalOpen{ false };
	std::atomic<bool>                      g_hasCustomMarker{ false };
	std::atomic<double>                    g_customX{ 0.0 };
	std::atomic<double>                    g_customY{ 0.0 };
	std::atomic<std::int32_t>              g_currentShellPage{ -1 };
	std::atomic<std::int32_t>              g_currentShellTab{ 0 };
	std::atomic<std::uint32_t>             g_hardcoreLogs{ 0 };
	std::atomic<std::uint32_t>             g_refreshLogs{ 0 };
	std::atomic<std::uint32_t>             g_markerLogs{ 0 };

	std::atomic<int>                       g_playerOk{ -1 };
	std::atomic<int>                       g_gameVmOk{ -1 };
	std::uintptr_t                         g_checkedVm = 0;
	bool                                   g_vmOff = false;
	bool                                   g_createObjOff = false;
	const void*                            g_checkedCreateObjMovie = nullptr;

	// Menu-thread only: stored Pipboy_MapPage reference from RegisterMap(this)
	RE::Scaleform::GFx::Value              g_mapPageVal;
	const void*                            g_populatedMovie = nullptr;
	std::int32_t                           g_lastPlayerArrayIdx = -1;

	std::mutex                             g_snapLock;
	LiveSnapshot                           g_snap;

	std::string Hex(std::uintptr_t a_v) { return std::format("{:#x}", a_v); }

	std::uintptr_t Address(MapIdIndex a_id) { return g_base + g_rva[a_id]; }

	bool InImage(std::uintptr_t a_addr, std::size_t a_len)
	{
		return a_addr >= g_base && a_len <= g_imageSize && a_addr - g_base <= g_imageSize - a_len;
	}

	bool PeekBytes(std::uintptr_t a_addr, void* a_out, std::size_t a_len)
	{
		__try {
			std::memcpy(a_out, reinterpret_cast<const void*>(a_addr), a_len);
			return true;
		} __except (1) {
			return false;
		}
	}

	template <class T>
	bool Peek(std::uintptr_t a_addr, T& a_out)
	{
		return PeekBytes(a_addr, &a_out, sizeof(T));
	}

	bool PokeFloat(std::uintptr_t a_addr, float a_val)
	{
		__try {
			std::memcpy(reinterpret_cast<void*>(a_addr), &a_val, sizeof(float));
			return true;
		} __except (1) {
			return false;
		}
	}

	bool RefuseStep(std::string_view a_step, const std::string& a_what)
	{
		REX::ERROR("refuse step={} {}", a_step, a_what);
		return false;
	}

	bool SameAscii(std::string_view a_l, std::string_view a_r)
	{
		return a_l.size() == a_r.size() &&
		       std::equal(a_l.begin(), a_l.end(), a_r.begin(), [](char c1, char c2) {
				   return std::toupper(static_cast<unsigned char>(c1)) == std::toupper(static_cast<unsigned char>(c2));
			   });
	}

	std::string ReadIniText(const std::filesystem::path& a_ini, const wchar_t* a_key)
	{
		std::array<wchar_t, 512> buf{};
		REX::W32::GetPrivateProfileStringW(L"FO4SFPipboyMenu", a_key, L"", buf.data(),
			static_cast<std::uint32_t>(buf.size()), a_ini.c_str());
		std::string out;
		for (const wchar_t* p = buf.data(); *p; ++p) {
			out += (*p >= 0x20 && *p < 0x7F) ? static_cast<char>(*p) : '?';
		}
		return out;
	}

	std::uint32_t ReadIniNumber(const std::filesystem::path& a_ini, const wchar_t* a_key, std::uint32_t a_default)
	{
		const auto text = ReadIniText(a_ini, a_key);
		return text.empty() ? a_default : static_cast<std::uint32_t>(std::strtoul(text.c_str(), nullptr, 0));
	}

	bool ValidIdentifier(std::string_view a_s, bool a_allowDot = false)
	{
		if (a_s.empty() || a_s.size() > kMaxName) {
			return false;
		}
		return std::ranges::all_of(a_s, [&](unsigned char c) {
			return std::isalnum(c) || c == '_' || (a_allowDot && (c == '.' || c == '-'));
		});
	}

	std::string TypeNameAt(std::uintptr_t a_descriptor)
	{
		std::string name;
		for (std::size_t i = 0; i < 96 && InImage(a_descriptor + 0x10 + i, 1); ++i) {
			const char c = *reinterpret_cast<const char*>(a_descriptor + 0x10 + i);
			if (!c) {
				return name;
			}
			name += (c >= 0x20 && c < 0x7F) ? c : '?';
		}
		return {};
	}

	bool NameIs(std::string_view a_name, std::string_view a_tail)
	{
		return a_name.size() == 4 + a_tail.size() && (a_name.starts_with(".?AV") || a_name.starts_with(".?AU")) &&
		       a_name.substr(4) == a_tail;
	}

	bool TypeOf(std::uintptr_t a_object, ObjectType& a_out)
	{
		std::uintptr_t vt = 0;
		if (!a_object || !Peek(a_object, vt) || !InImage(vt - 8, 8)) {
			return false;
		}
		const auto col = *reinterpret_cast<const std::uintptr_t*>(vt - 8);
		if (!InImage(col, 0x14) || *reinterpret_cast<const std::uint32_t*>(col) != 1) {
			return false;
		}
		a_out.offset = *reinterpret_cast<const std::uint32_t*>(col + 0x04);
		a_out.descriptor = g_base + *reinterpret_cast<const std::uint32_t*>(col + 0x0C);
		a_out.hierarchy = g_base + *reinterpret_cast<const std::uint32_t*>(col + 0x10);
		a_out.name = TypeNameAt(a_out.descriptor);
		return !a_out.name.empty();
	}

	bool IsType(std::uintptr_t a_object, std::string_view a_tail)
	{
		ObjectType t;
		return TypeOf(a_object, t) && t.offset == 0 && NameIs(t.name, a_tail);
	}

	bool CheckSingleton(std::string_view a_what, MapIdIndex a_singleton, MapIdIndex a_rtti, std::atomic<int>& a_state)
	{
		const auto st = a_state.load();
		if (st >= 0) {
			return st == 1;
		}
		std::uintptr_t obj = 0;
		if (!Peek(Address(a_singleton), obj) || !obj) {
			return false;
		}
		ObjectType t;
		const bool known = TypeOf(obj, t);
		if (!known || t.descriptor != Address(a_rtti) || t.offset != 0) {
			a_state = 0;
			RefuseStep("object", std::format("name={} object={} type={} offset={}", a_what, Hex(obj),
				known ? t.name : "unreadable", Hex(t.offset)));
			return false;
		}
		a_state = 1;
		return true;
	}

	std::uintptr_t Singleton(MapIdIndex a_singleton)
	{
		std::uintptr_t obj = 0;
		Peek(Address(a_singleton), obj);
		return obj;
	}

	bool CheckMapAddressLibrary(const std::filesystem::path& a_file)
	{
		std::ifstream in(a_file, std::ios::binary);
		if (!in) {
			return RefuseStep("address_library", std::format("reason=missing file={}", a_file.filename().string()));
		}
		std::array<std::uint8_t, kHeaderBytes> head{};
		in.read(reinterpret_cast<char*>(head.data()), head.size());
		if (!in) {
			return RefuseStep("address_library", "reason=short_header");
		}
		const auto u32 = [&](std::size_t a_at) {
			std::uint32_t v = 0;
			std::memcpy(&v, head.data() + a_at, sizeof(v));
			return v;
		};
		const auto format = u32(0);
		const REL::Version version{ static_cast<std::uint16_t>(u32(4)), static_cast<std::uint16_t>(u32(8)),
			static_cast<std::uint16_t>(u32(12)), static_cast<std::uint16_t>(u32(16)) };
		const auto pointerSize = u32(84);
		const auto count = u32(92);
		if (format != 5 || version != kRuntime || pointerSize != 8) {
			return RefuseStep("address_library", "reason=header");
		}
		for (std::size_t i = 0; i < kMapIdCount; ++i) {
			const auto& spec = kMapIds[i];
			if (spec.id >= count) {
				return RefuseStep("id", std::format("name={} id={} reason=beyond_count", spec.name, spec.id));
			}
			std::uint32_t offset = 0;
			in.seekg(static_cast<std::streamoff>(kHeaderBytes + 4ull * spec.id));
			in.read(reinterpret_cast<char*>(&offset), sizeof(offset));
			if (!in || !offset || offset >= g_imageSize) {
				return RefuseStep("id", std::format("name={} id={} rva={} reason=invalid", spec.name, spec.id, Hex(offset)));
			}
			const auto viaLib = REL::ID(spec.id).offset();
			if (viaLib != offset) {
				return RefuseStep("id", std::format("name={} id={} reason=library_mismatch", spec.name, spec.id));
			}
			if (spec.expectedRva != 0 && offset != spec.expectedRva) {
				return RefuseStep("id", std::format("name={} id={} rva={} expected={}", spec.name, spec.id, Hex(offset),
					Hex(spec.expectedRva)));
			}
			g_rva[i] = offset;
			if (!spec.rttiTail.empty()) {
				const auto rttiName = TypeNameAt(g_base + offset);
				if (!NameIs(rttiName, spec.rttiTail)) {
					return RefuseStep("rtti", std::format("name={} type={}", spec.name, rttiName));
				}
			}
		}
		return true;
	}

	bool LoadMarkerStore(const std::filesystem::path& a_storePath)
	{
		g_store.clear();
		std::ifstream in(a_storePath);
		if (!in) {
			REX::INFO("step=map_store file={} status=absent markers=0", a_storePath.filename().string());
			return true;   // Slices 1-2 can run before the marker store is staged
		}
		std::string line;
		std::size_t lineNo = 0;
		while (std::getline(in, line)) {
			++lineNo;
			if (!line.empty() && line.back() == '\r') {
				line.pop_back();
			}
			if (line.empty() || line[0] == '#') {
				continue;
			}
			if (lineNo == 1 && line.starts_with("index\t")) {
				continue;
			}
			if (g_store.size() >= kMaxStoreMarkers) {
				break;
			}
			std::vector<std::string> cols;
			std::stringstream        ss(line);
			std::string              cell;
			while (std::getline(ss, cell, '\t')) {
				cols.push_back(cell);
			}
			if (cols.size() < 11) {
				return RefuseStep("ini", std::format("reason=map_store_columns line={} cols={}", lineNo, cols.size()));
			}
			StoreMarker m;
			m.index = static_cast<std::uint32_t>(std::strtoul(cols[0].c_str(), nullptr, 10));
			m.pluginCode = static_cast<std::uint32_t>(std::strtoul(cols[1].c_str(), nullptr, 10));
			m.localId = static_cast<std::uint32_t>(std::strtoul(cols[2].c_str(), nullptr, 16)) & 0x00FFFFFFu;
			m.type = std::min<std::uint32_t>(static_cast<std::uint32_t>(std::strtoul(cols[3].c_str(), nullptr, 10)), kMaxMarkerType);
			m.initialDiscovered = std::strtoul(cols[4].c_str(), nullptr, 10) != 0;
			m.xFo4 = std::strtod(cols[5].c_str(), nullptr);
			m.yFo4 = std::strtod(cols[6].c_str(), nullptr);
			m.arrivalXSf = std::strtof(cols[7].c_str(), nullptr);
			m.arrivalYSf = std::strtof(cols[8].c_str(), nullptr);
			m.arrivalZSf = std::strtof(cols[9].c_str(), nullptr);
			m.arrivalHeadingDeg = std::strtof(cols[10].c_str(), nullptr);
			m.label = cols.size() >= 12 ? cols[11].substr(0, 96) : std::format("LOC_{:03}", m.index);
			g_store.push_back(std::move(m));
		}
		REX::INFO("step=map_store file={} status=loaded markers={}", a_storePath.filename().string(), g_store.size());
		return true;
	}

	const RE::BSFixedString& OurMenuFixed()
	{
		static auto* const s = new RE::BSFixedString(kOurMenu.data());
		return *s;
	}

	const std::vector<RE::BSFixedString>& MapMenusFixed()
	{
		static const auto* const vec = [] {
			auto* out = new std::vector<RE::BSFixedString>();
			for (const auto& m : g_mapMenus) {
				out->emplace_back(m.c_str());
			}
			return out;
		}();
		return *vec;
	}

	bool GameInFront()
	{
		std::uint32_t pid = 0;
		W32_IMPL_GetWindowThreadProcessId(W32_IMPL_GetForegroundWindow(), &pid);
		return pid == W32_IMPL_GetCurrentProcessId();
	}

	std::uintptr_t LookupForm(std::uint32_t a_formId)
	{
		if (!a_formId || !g_rva[kLookupById]) {
			return 0;
		}
		const auto fn = reinterpret_cast<LookupById_t>(Address(kLookupById));
		return reinterpret_cast<std::uintptr_t>(fn(a_formId));
	}

	// Finds the runtime FormID prefix (upper bits) of an active plugin by file name in TESDataHandler::compiledFileCollection
	bool ResolvePluginPrefix(std::string_view a_fileName, std::uint32_t& a_prefix, bool& a_small)
	{
		std::uintptr_t handler = 0;
		if (!Peek(Address(kDataHandlerSingleton), handler) || !handler || !IsType(handler, "TESDataHandler@@")) {
			return false;
		}
		for (int listKind = 0; listKind < 3; ++listKind) {
			ArrayHead list{};
			if (!Peek(handler + kFileCollectionAt + static_cast<std::size_t>(listKind) * sizeof(ArrayHead), list)) {
				continue;
			}
			const auto n = std::min<std::size_t>(list.size, kMaxFiles);
			for (std::size_t i = 0; i < n; ++i) {
				std::uintptr_t file = 0;
				if (!Peek(list.data + 8ull * i, file) || !file) {
					continue;
				}
				std::array<char, kFileNameSize> rawName{};
				if (!PeekBytes(file + kFileNameAt, rawName.data(), rawName.size())) {
					continue;
				}
				rawName.back() = '\0';
				if (!SameAscii(rawName.data(), a_fileName)) {
					continue;
				}
				std::uint8_t  compileIdx = 0xFF;
				std::uint32_t fileIdx = 0;
				if (!Peek(file + kFileCompileIndexAt, compileIdx) || !Peek(file + kFileIndexAt, fileIdx)) {
					return false;
				}
				if (compileIdx == 0xFE) {
					a_small = true;
					a_prefix = 0xFE000000u | ((fileIdx & 0xFFFu) << 12);
					return true;
				}
				if (compileIdx == 0xFD) {
					a_small = false;
					a_prefix = 0xFD000000u | (((fileIdx >> 8) & 0xFFu) << 16);
					return true;
				}
				if (compileIdx < 0xFD) {
					a_small = false;
					a_prefix = static_cast<std::uint32_t>(compileIdx) << 24;
					return true;
				}
			}
		}
		return false;
	}

	std::uintptr_t LookupPluginGlobal(std::uint32_t a_prefix, bool a_small, std::uint32_t a_localId)
	{
		const std::uint32_t mask = a_small ? 0xFFFu : 0xFFFFFFu;
		const auto          form = LookupForm(a_prefix | (a_localId & mask));
		return (form && IsType(form, "TESGlobal@@")) ? form : 0;
	}

	bool ReadGlobalFloat(std::uintptr_t a_glob, float& a_out)
	{
		return a_glob && Peek(a_glob + kGlobalValueAt, a_out) && std::isfinite(a_out);
	}

	bool WriteGlobalFloat(std::uintptr_t a_glob, float a_val, float& a_readBack)
	{
		return a_glob && PokeFloat(a_glob + kGlobalValueAt, a_val) && ReadGlobalFloat(a_glob, a_readBack);
	}

	void DaysToCalendar(float a_daysPassed, std::uint32_t& a_month, std::uint32_t& a_day, std::uint32_t& a_year)
	{
		// Fallout 4 starts Oct 23, 2287 (day 0 = 2026/2287-10-23)
		static constexpr std::array<int, 12> kMonthDays{ 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 };
		int total = std::max(0, static_cast<int>(std::floor(a_daysPassed)));
		int y = 2287;
		int m = 9;   // 0-based October
		int d = 23 + total;
		while (d > kMonthDays[static_cast<std::size_t>(m)]) {
			d -= kMonthDays[static_cast<std::size_t>(m)];
			if (++m == 12) {
				m = 0;
				++y;
			}
		}
		a_month = static_cast<std::uint32_t>(m + 1);
		a_day = static_cast<std::uint32_t>(d);
		a_year = static_cast<std::uint32_t>(y);
	}

	// Main thread only: refreshes player position/heading, clock, survival mode and 24-bit discovery bitsets
	void CollectMainThreadState()
	{
		LiveSnapshot next;
		{
			std::scoped_lock lock(g_snapLock);
			next = g_snap;
		}
		if (CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk)) {
			const auto           player = Singleton(kPlayerSingleton);
			std::array<float, 3> xyz{};
			float                yawRad = 0.0f;
			if (Peek(player + kPositionAt, xyz) && std::isfinite(xyz[0]) && std::isfinite(xyz[1])) {
				next.havePlayer = true;
				next.playerXFo4 = (static_cast<double>(xyz[0]) - kMergeOffsetX) * kFo4UnitsPerMetre;
				next.playerYFo4 = (static_cast<double>(xyz[1]) - kMergeOffsetY) * kFo4UnitsPerMetre;
			}
			if (Peek(player + kAngleZAt, yawRad) && std::isfinite(yawRad)) {
				double deg = std::fmod(static_cast<double>(yawRad) * (180.0 / std::numbers::pi), 360.0);
				if (deg < 0.0) {
					deg += 360.0;
				}
				next.playerHeadingDeg = deg;
			}
			std::uintptr_t cell = 0;
			std::uintptr_t world = 0;
			if (Peek(player + kParentCellAt, cell) && cell && Peek(cell + kCellWorldAt, world)) {
				next.locationName = world ? "COMMONWEALTH" : "INTERIOR";
			}
		}

		const auto hourForm = LookupForm(kGameHourId);
		const auto daysForm = LookupForm(kGameDaysPassedId);
		float      hour = 0.0f;
		float      days = 0.0f;
		if (IsType(hourForm, "TESGlobal@@") && ReadGlobalFloat(hourForm, hour) && hour >= 0.0f && hour < 24.0f) {
			next.gameHour = hour;
		}
		if (IsType(daysForm, "TESGlobal@@") && ReadGlobalFloat(daysForm, days) && days >= 0.0f && days < 1000000.0f) {
			DaysToCalendar(days, next.dateMonth, next.dateDay, next.dateYear);
		}

		std::uint32_t prefix = 0;
		bool          small = false;
		if (ResolvePluginPrefix(g_travelPlugin, prefix, small)) {
			float surv = 0.0f;
			if (const auto survGlob = LookupPluginGlobal(prefix, small, kGlobSurvivalMode); ReadGlobalFloat(survGlob, surv)) {
				next.liveSurvival = surv >= 0.5f;
			}
			for (std::size_t i = 0; i < kDiscGlobals; ++i) {
				float bits = 0.0f;
				const auto glob = LookupPluginGlobal(prefix, small, kGlobDiscFirst + static_cast<std::uint32_t>(i));
				if (ReadGlobalFloat(glob, bits) && bits >= 0.0f && bits < static_cast<float>(1u << kBitsPerGlobal)) {
					next.discBits[i] = static_cast<std::uint32_t>(bits) & ((1u << kBitsPerGlobal) - 1u);
				}
			}
		}

		bool changed = false;
		{
			std::scoped_lock lock(g_snapLock);
			changed = (g_snap.discBits != next.discBits) ||
			          (std::fabs(g_snap.playerXFo4 - next.playerXFo4) > 35.0) ||
			          (std::fabs(g_snap.playerYFo4 - next.playerYFo4) > 35.0) ||
			          (std::fabs(g_snap.playerHeadingDeg - next.playerHeadingDeg) > 1.0);
			g_snap = std::move(next);
		}
		if (changed) {
			g_markersDirty = true;
		}
	}

	bool IsMarkerDiscovered(const StoreMarker& a_m, const std::array<std::uint32_t, kDiscGlobals>& a_discBits)
	{
		if (a_m.initialDiscovered) {
			return true;
		}
		const std::size_t group = a_m.index / kBitsPerGlobal;
		const std::size_t bit = a_m.index % kBitsPerGlobal;
		if (group < kDiscGlobals && ((a_discBits[group] >> bit) & 1u) != 0) {
			return true;
		}
		return false;
	}

	void SendMenuUpdateMainThread()
	{
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue || !ui->IsMenuOpen(OurMenuFixed())) {
			return;
		}
		CollectMainThreadState();
		queue->AddMessage(OurMenuFixed(), RE::UI_MESSAGE_TYPE::kUpdate);
	}

	// Main thread: suppresses any open vanilla map menu in MapMenus= and opens FO4SF_PipboyMenu on MAP (page 3, tab 0)
	bool SuppressVanillaMapMenus(bool a_openOursOnSuppress)
	{
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue) {
			return false;
		}
		const auto& names = MapMenusFixed();
		bool        suppressed = false;
		for (std::size_t i = 0; i < names.size(); ++i) {
			if (!ui->IsMenuRegistered(names[i]) || !ui->IsMenuOpen(names[i])) {
				continue;
			}
			queue->AddMessage(names[i], RE::UI_MESSAGE_TYPE::kHide);
			suppressed = true;
			const auto n = ++g_suppressions;
			if (n <= kMaxLogLines) {
				REX::INFO("step=map_suppress n={} name={} sent=hide", n, g_mapMenus[i]);
			}
		}
		if (suppressed && a_openOursOnSuppress) {
			CollectMainThreadState();
			g_requestedPage = static_cast<std::int32_t>(g_mapPage);
			g_requestedTab = 0;
			g_markersDirty = true;
			if (!ui->IsMenuOpen(OurMenuFixed())) {
				queue->AddMessage(OurMenuFixed(), RE::UI_MESSAGE_TYPE::kShow);
			} else {
				queue->AddMessage(OurMenuFixed(), RE::UI_MESSAGE_TYPE::kUpdate);
			}
		}
		return suppressed;
	}

	void HandleMapKeyMainThread(std::uint32_t a_n)
	{
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue) {
			return;
		}
		SuppressVanillaMapMenus(false);
		const bool open = ui->IsMenuOpen(OurMenuFixed());
		if (open && g_currentShellPage.load() == static_cast<std::int32_t>(g_mapPage) && !g_modalOpen.load()) {
			queue->AddMessage(OurMenuFixed(), RE::UI_MESSAGE_TYPE::kHide);
			REX::INFO("step=map_key n={} vk={} was_open=1 on_map=1 sent=hide", a_n, Hex(g_mapKey));
			return;
		}
		CollectMainThreadState();
		g_requestedPage = static_cast<std::int32_t>(g_mapPage);
		g_requestedTab = 0;
		g_markersDirty = true;
		queue->AddMessage(OurMenuFixed(), open ? RE::UI_MESSAGE_TYPE::kUpdate : RE::UI_MESSAGE_TYPE::kShow);
		REX::INFO("step=map_key n={} vk={} was_open={} page={} sent={}", a_n, Hex(g_mapKey), open ? 1 : 0, g_mapPage,
			open ? "update" : "show");
	}

	RE::BSScript::IVirtualMachine* CheckedScriptVm()
	{
		if (g_vmOff || !CheckSingleton("GameVM", kGameVmSingleton, kGameVmRtti, g_gameVmOk)) {
			return nullptr;
		}
		std::uintptr_t vm = 0;
		if (!Peek(Singleton(kGameVmSingleton) + kGameVmImplAt, vm) || !vm) {
			return nullptr;
		}
		if (vm != g_checkedVm) {
			ObjectType     type;
			std::uintptr_t vt = 0;
			const bool     known = TypeOf(vm, type) && Peek(vm, vt);
			if (!known || type.descriptor != Address(kVmRtti) || type.offset != 0 ||
				!InImage(vt, (kDispatchStaticCallSlot + 1) * 8)) {
				g_vmOff = true;
				RefuseStep("object", std::format("name=VirtualMachine object={} vtable={}", Hex(vm), Hex(vt)));
				return nullptr;
			}
			const auto* slot = reinterpret_cast<const std::uintptr_t*>(vt);
			for (std::size_t i = 0; i <= kDispatchStaticCallSlot; ++i) {
				if (!InImage(slot[i], 1)) {
					g_vmOff = true;
					RefuseStep("object", std::format("name=VirtualMachine slot={} reason=outside_image", Hex(i)));
					return nullptr;
				}
			}
			g_checkedVm = vm;
		}
		return reinterpret_cast<RE::BSScript::IVirtualMachine*>(vm);
	}

	// Main thread: closes Pip-Boy, writes travel globals at +0x48 with read-back check, dispatches FO4SF_PipboyTravel.Go
	void ExecuteFastTravelMainThread(std::uint32_t a_storeIdx)
	{
		if (a_storeIdx >= g_store.size()) {
			REX::INFO("step=map_fast_travel idx={} result=out_of_range count={}", a_storeIdx, g_store.size());
			return;
		}
		CollectMainThreadState();
		LiveSnapshot snap;
		{
			std::scoped_lock lock(g_snapLock);
			snap = g_snap;
		}
		const auto& m = g_store[a_storeIdx];
		if (g_mapSurvival || snap.liveSurvival) {
			REX::INFO("step=map_fast_travel idx={} result=survival_blocked", a_storeIdx);
			return;
		}
		if (!IsMarkerDiscovered(m, snap.discBits)) {
			REX::INFO("step=map_fast_travel idx={} result=undiscovered", a_storeIdx);
			return;
		}
		if (auto* ui = RE::UI::GetSingleton(); ui && ui->IsMenuOpen(OurMenuFixed())) {
			if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
				queue->AddMessage(OurMenuFixed(), RE::UI_MESSAGE_TYPE::kHide);
			}
		}

		std::uint32_t prefix = 0;
		bool          small = false;
		if (!ResolvePluginPrefix(g_travelPlugin, prefix, small)) {
			REX::INFO("step=map_fast_travel idx={} plugin={} result=plugin_not_loaded", a_storeIdx, g_travelPlugin);
			return;
		}

		const auto gTarget = LookupPluginGlobal(prefix, small, kGlobTravelTarget);
		const auto gPlugin = LookupPluginGlobal(prefix, small, kGlobTravelPlugin);
		const auto gIndex = LookupPluginGlobal(prefix, small, kGlobTravelIndex);
		const auto gX = LookupPluginGlobal(prefix, small, kGlobTravelX);
		const auto gY = LookupPluginGlobal(prefix, small, kGlobTravelY);
		const auto gZ = LookupPluginGlobal(prefix, small, kGlobTravelZ);
		const auto gH = LookupPluginGlobal(prefix, small, kGlobTravelH);

		float rbTarget = -1.0f, rbPlugin = -1.0f, rbIndex = -1.0f;
		float rbX = 0.0f, rbY = 0.0f, rbZ = 0.0f, rbH = 0.0f;
		const float wantTarget = static_cast<float>(m.localId);
		const float wantPlugin = static_cast<float>(m.pluginCode);
		const float wantIndex = static_cast<float>(m.index);

		const bool wrote = WriteGlobalFloat(gTarget, wantTarget, rbTarget) &&
		                   WriteGlobalFloat(gPlugin, wantPlugin, rbPlugin) &&
		                   WriteGlobalFloat(gIndex, wantIndex, rbIndex) &&
		                   WriteGlobalFloat(gX, m.arrivalXSf, rbX) &&
		                   WriteGlobalFloat(gY, m.arrivalYSf, rbY) &&
		                   WriteGlobalFloat(gZ, m.arrivalZSf, rbZ) &&
		                   WriteGlobalFloat(gH, m.arrivalHeadingDeg, rbH);
		const bool match = wrote && rbTarget == wantTarget && rbPlugin == wantPlugin && rbIndex == wantIndex;

		auto* const vm = CheckedScriptVm();
		bool        queued = false;
		if (match && vm) {
			const RE::BSFixedString                                        script(g_travelScript.c_str());
			const RE::BSFixedString                                        fn(g_travelFunction.c_str());
			const RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> noCallback{};
			const auto noArguments = [](RE::BSScrapArray<RE::BSScript::Variable>&) { return true; };
			queued = vm->DispatchStaticCall(script, fn, noArguments, noCallback, 0);
		}
		REX::INFO("step=map_fast_travel idx={} local_id={:#x} plugin_code={} global_set={} read_back={} call={}.{} queued={}",
			a_storeIdx, m.localId, m.pluginCode, wrote ? 1 : 0, match ? "match" : "mismatch", g_travelScript,
			g_travelFunction, queued ? 1 : 0);
	}

	bool CheckCreateObjectSlot(const void* a_movie, RE::Scaleform::GFx::ASMovieRootBase* a_root)
	{
		if (g_createObjOff || !a_movie || !a_root) {
			return false;
		}
		if (g_checkedCreateObjMovie == a_movie) {
			return true;
		}
		std::uintptr_t vt = 0;
		const auto     rootAddr = reinterpret_cast<std::uintptr_t>(a_root);
		if (!Peek(rootAddr, vt)) {
			g_createObjOff = true;
			return RefuseStep("channel", "what=map_root_vtable");
		}
		const auto* slot = reinterpret_cast<const std::uintptr_t*>(vt);
		if (!InImage(vt, (kGetVariableSlot + 1) * 8) || !InImage(slot[kCreateObjectSlot], 1)) {
			g_createObjOff = true;
			return RefuseStep("channel", std::format("what=create_object_slot vtable={}", Hex(vt)));
		}
		g_checkedCreateObjMovie = a_movie;
		REX::INFO("step=map_root vtable={} create_object={}", Hex(vt), Hex(slot[kCreateObjectSlot] - g_base));
		return true;
	}

	bool ReadDotPath(const RE::Scaleform::GFx::Value& a_from, std::string_view a_path, RE::Scaleform::GFx::Value& a_out)
	{
		RE::Scaleform::GFx::Value cur = a_from;
		for (std::size_t start = 0; start <= a_path.size();) {
			const auto                end = std::min(a_path.find('.', start), a_path.size());
			const std::string         part(a_path.substr(start, end - start));
			RE::Scaleform::GFx::Value next;
			if (!(cur.IsObject() || cur.GetType() == RE::Scaleform::GFx::Value::ValueType::kClosure) ||
				!cur.GetMember(part.c_str(), &next)) {
				return false;
			}
			cur = next;
			start = end + 1;
		}
		a_out = cur;
		return true;
	}

	bool MutatePoint(RE::Scaleform::GFx::Value& a_dataObj, const char* a_member, double a_x, double a_y)
	{
		RE::Scaleform::GFx::Value pt;
		if (!a_dataObj.GetMember(a_member, &pt) || !pt.IsObject()) {
			return false;
		}
		const bool setX = pt.SetMember("x", RE::Scaleform::GFx::Value(a_x));
		const bool setY = pt.SetMember("y", RE::Scaleform::GFx::Value(a_y));
		RE::Scaleform::GFx::Value rx, ry;
		const bool okX = setX && pt.GetMember("x", &rx) && rx.IsNumber() && std::fabs(rx.GetNumber() - a_x) < 0.5;
		const bool okY = setY && pt.GetMember("y", &ry) && ry.IsNumber() && std::fabs(ry.GetNumber() - a_y) < 0.5;
		return okX && okY;
	}

	bool PushMarkerObject(RE::Scaleform::GFx::Value& a_arr, const RE::Scaleform::GFx::Value& a_obj)
	{
		RE::Scaleform::GFx::Value res;
		return a_arr.Invoke("push", &res, &a_obj, 1);
	}

	bool ParseArgUInt(const RE::Scaleform::GFx::FunctionHandler::Params& a_params, std::uint32_t a_idx, std::uint32_t& a_out)
	{
		if (a_idx >= a_params.argCount) {
			return false;
		}
		const auto& v = a_params.args[a_idx];
		if (v.IsUInt()) {
			a_out = v.GetUInt();
			return true;
		}
		if (v.IsInt() && v.GetInt() >= 0) {
			a_out = static_cast<std::uint32_t>(v.GetInt());
			return true;
		}
		if (v.IsNumber() && v.GetNumber() >= 0.0 && v.GetNumber() <= 4294967295.0) {
			a_out = static_cast<std::uint32_t>(v.GetNumber());
			return true;
		}
		return false;
	}

	bool ParseArgNumber(const RE::Scaleform::GFx::FunctionHandler::Params& a_params, std::uint32_t a_idx, double& a_out)
	{
		if (a_idx >= a_params.argCount) {
			return false;
		}
		const auto& v = a_params.args[a_idx];
		if (v.IsNumber()) {
			a_out = v.GetNumber();
			return std::isfinite(a_out);
		}
		if (v.IsInt()) {
			a_out = static_cast<double>(v.GetInt());
			return true;
		}
		if (v.IsUInt()) {
			a_out = static_cast<double>(v.GetUInt());
			return true;
		}
		return false;
	}
}

namespace PipboyMap
{
	void Configure(const std::filesystem::path& a_ini, const std::filesystem::path& a_dir, int a_stage,
		std::uint32_t a_menuKey, std::uintptr_t a_base, std::size_t a_imageSize)
	{
		if (ReadIniNumber(a_ini, L"Map", 0) == 0) {
			return;
		}
		g_base = a_base;
		g_imageSize = a_imageSize;
		const auto movie = ReadIniText(a_ini, L"Movie");
		const auto codeObj = ReadIniNumber(a_ini, L"CodeObj", 0);
		if (a_stage != 2 || movie.empty() || codeObj == 0) {
			RefuseStep("ini", std::format("reason=map_stage stage={} movie={} code_obj={} (Map=1 requires Stage=2, Movie= and CodeObj=1)",
				a_stage, movie.empty() ? "none" : movie, codeObj));
			return;
		}
		g_mapKey = ReadIniNumber(a_ini, L"MapKey", 0x4D);
		g_mapPage = ReadIniNumber(a_ini, L"MapPage", 3);
		g_mapSurvival = ReadIniNumber(a_ini, L"MapSurvival", 0) != 0;
		if (g_mapKey == 0 || g_mapKey > 0xFE || g_mapKey == a_menuKey || g_mapKey == kF10 ||
			g_mapKey == kQuickSaveKey || g_mapKey == kQuickLoadKey || g_mapPage > 4) {
			RefuseStep("ini", std::format("reason=map_key map_key={} key={} map_page={}", Hex(g_mapKey), Hex(a_menuKey), g_mapPage));
			return;
		}

		const auto menusRaw = ReadIniText(a_ini, L"MapMenus");
		const std::string menusList = menusRaw.empty() ? std::string("GalaxyStarMapMenu") : menusRaw;
		g_mapMenus.clear();
		for (std::size_t s = 0; s <= menusList.size();) {
			const auto e = std::min(menusList.find(',', s), menusList.size());
			const auto item = menusList.substr(s, e - s);
			if (!item.empty()) {
				if (!ValidIdentifier(item) || SameAscii(item, kOurMenu) || g_mapMenus.size() >= kMaxMapMenus) {
					RefuseStep("ini", std::format("reason=map_menus map_menus={}", menusList));
					return;
				}
				g_mapMenus.push_back(item);
			}
			s = e + 1;
		}

		const auto storeName = ReadIniText(a_ini, L"MapStore");
		const std::string storeFile = storeName.empty() ? std::string("FO4SFPipboyMapMarkers.tsv") : storeName;
		if (!ValidIdentifier(storeFile, true) || storeFile.find("..") != std::string::npos) {
			RefuseStep("ini", std::format("reason=map_store map_store={}", storeFile));
			return;
		}

		const auto travelPlugin = ReadIniText(a_ini, L"MapTravelPlugin");
		if (!travelPlugin.empty()) {
			if (!ValidIdentifier(travelPlugin, true)) {
				RefuseStep("ini", std::format("reason=map_travel_plugin plugin={}", travelPlugin));
				return;
			}
			g_travelPlugin = travelPlugin;
		}

		const auto travelCall = ReadIniText(a_ini, L"MapTravelScript");
		const std::string callSpec = travelCall.empty() ? std::string("FO4SF_PipboyTravel.Go") : travelCall;
		const auto dot = callSpec.find('.');
		if (dot == std::string::npos || !ValidIdentifier(callSpec.substr(0, dot)) || !ValidIdentifier(callSpec.substr(dot + 1))) {
			RefuseStep("ini", std::format("reason=map_travel_script call={}", callSpec));
			return;
		}
		g_travelScript = callSpec.substr(0, dot);
		g_travelFunction = callSpec.substr(dot + 1);

		if (!CheckMapAddressLibrary(a_dir / "versionlib-1-16-244-0.bin") || !LoadMarkerStore(a_dir / storeFile)) {
			return;
		}

		g_on = true;
		REX::INFO("step=map_config map_key={} map_page={} menus={} store={} markers={} travel={}.{} survival={}",
			Hex(g_mapKey), g_mapPage, menusList, storeFile, g_store.size(), g_travelScript, g_travelFunction,
			g_mapSurvival ? 1 : 0);
	}

	void Start(const SFSE::TaskInterface* a_task)
	{
		if (!g_on) {
			return;
		}
		g_task = a_task;
		(void)OurMenuFixed();
		(void)MapMenusFixed();
	}

	void OnMovieCreated(const RE::IMenu* a_menu)
	{
		if (!g_on || !g_task || !a_menu) {
			return;
		}
		const char* raw = a_menu->menuName.c_str();
		if (!raw) {
			return;
		}
		for (const auto& blocked : g_mapMenus) {
			if (SameAscii(raw, blocked)) {
				g_task->AddTask([]() { SuppressVanillaMapMenus(true); });
				return;
			}
		}
	}

	void Tick()
	{
		if (!g_on || !g_task) {
			return;
		}
		const bool now = (W32_IMPL_GetAsyncKeyState(static_cast<std::int32_t>(g_mapKey)) & 0x8000) != 0;
		const bool was = g_keyDown.exchange(now);
		if (now && !was && GameInFront()) {
			const auto n = ++g_keyPresses;
			g_task->AddTask([n]() { HandleMapKeyMainThread(n); });
			// Stage=2 sends no periodic kUpdate on show; follow up after 750 ms so late calls & MAP DataObj run
			REX::W32::Sleep(750);
			g_task->AddTask([]() { SendMenuUpdateMainThread(); });
			return;
		}
		const auto t = ++g_tickCount;
		if (t % 3 == 0) {
			g_task->AddTask([]() { SuppressVanillaMapMenus(true); });
		}
		if (t % 17 == 0 && g_currentShellPage.load() == static_cast<std::int32_t>(g_mapPage)) {
			g_task->AddTask([]() { SendMenuUpdateMainThread(); });
		}
	}

	void OnCodeObjCall(const std::string& a_name, const RE::Scaleform::GFx::FunctionHandler::Params& a_params)
	{
		if (!g_on) {
			return;
		}
		if (a_name == "CheckHardcoreModeFastTravel") {
			bool liveSurv = false;
			{
				std::scoped_lock lock(g_snapLock);
				liveSurv = g_snap.liveSurvival;
			}
			const bool allow = !(g_mapSurvival || liveSurv);
			if (a_params.ret) {
				*a_params.ret = RE::Scaleform::GFx::Value(allow);
			}
			if (++g_hardcoreLogs <= kMaxLogLines) {
				std::uint32_t idx = 0;
				ParseArgUInt(a_params, 0, idx);
				REX::INFO("step=map_check_hardcore idx={} allow={}", idx, allow ? 1 : 0);
			}
			return;
		}
		if (a_name == "RefreshMapMarkers") {
			if (++g_refreshLogs <= 16) {
				std::uint32_t idx = 0;
				ParseArgUInt(a_params, 0, idx);
				REX::INFO("step=map_refresh_hover idx={}", idx);
			}
			return;
		}
		if (a_name == "RegisterMap") {
			if (a_params.argCount > 0 && a_params.args[0].IsObject()) {
				g_mapPageVal = a_params.args[0];
				g_needTexturesLoaded = true;
				g_needCenter = true;
				g_markersDirty = true;
				g_textureLogged = false;
				REX::INFO("step=map_register ok=1");
				if (g_task) {
					g_task->AddTask([]() { SendMenuUpdateMainThread(); });
				}
			}
			return;
		}
		if (a_name == "UnregisterMap") {
			g_mapPageVal = RE::Scaleform::GFx::Value{};
			g_needTexturesLoaded = false;
			REX::INFO("step=map_unregister ok=1");
			return;
		}
		if (a_name == "CenterMarkerRequest") {
			g_needCenter = true;
			if (g_task) {
				g_task->AddTask([]() { SendMenuUpdateMainThread(); });
			}
			return;
		}
		if (a_name == "onSwitchBetweenWorldLocalMap") {
			const std::int32_t nextTab = g_currentShellTab.load() == 0 ? 1 : 0;
			g_requestedTab = nextTab;
			if (g_task) {
				g_task->AddTask([]() { SendMenuUpdateMainThread(); });
			}
			return;
		}
		if (a_name == "SetPlayerMarker") {
			double wx = 0.0, wy = 0.0;
			if (ParseArgNumber(a_params, 0, wx) && ParseArgNumber(a_params, 1, wy)) {
				g_customX = wx;
				g_customY = wy;
				g_hasCustomMarker = true;
				g_markersDirty = true;
				REX::INFO("step=map_waypoint set=1 x={:.1f} y={:.1f}", wx, wy);
				if (g_task) {
					g_task->AddTask([]() { SendMenuUpdateMainThread(); });
				}
			}
			return;
		}
		if (a_name == "ClearPlayerMarker") {
			g_hasCustomMarker = false;
			g_markersDirty = true;
			REX::INFO("step=map_waypoint set=0");
			if (g_task) {
				g_task->AddTask([]() { SendMenuUpdateMainThread(); });
			}
			return;
		}
		if (a_name == "onModalOpen") {
			const bool open = a_params.argCount > 0 && a_params.args[0].IsBoolean() && a_params.args[0].GetBoolean();
			g_modalOpen = open;
			REX::INFO("step=map_modal open={}", open ? 1 : 0);
			return;
		}
		if (a_name == "FastTravel") {
			std::uint32_t idx = 0;
			if (ParseArgUInt(a_params, 0, idx) && g_task) {
				REX::INFO("step=map_fast_travel_req idx={}", idx);
				g_task->AddTask([idx]() { ExecuteFastTravelMainThread(idx); });
			}
			return;
		}
	}

	void OnShellUpdate(const void* a_menu, RE::Scaleform::GFx::ASMovieRootBase* a_root, RE::Scaleform::GFx::Value& a_top,
		const std::string& a_codeObjAt, std::atomic<std::int32_t>& a_answerPage, std::atomic<std::int32_t>& a_answerTab)
	{
		if (!g_on || !a_menu || !a_root || a_codeObjAt.empty()) {
			return;
		}
		const void* const movie = static_cast<const RE::IMenu*>(a_menu)->uiMovie.get();
		if (!CheckCreateObjectSlot(movie, a_root)) {
			return;
		}

		// Hand any MapKey / world-local toggle request into ShellUpdate's own CurrentPage/CurrentTab answer slot
		const auto reqPage = g_requestedPage.exchange(-1);
		const auto reqTab = g_requestedTab.exchange(-1);
		if (reqPage >= 0) {
			a_answerPage.store(reqPage);
		}
		if (reqTab >= 0) {
			a_answerTab.store(reqTab);
		}

		RE::Scaleform::GFx::Value menuMc;
		RE::Scaleform::GFx::Value dataObj;
		if (!ReadDotPath(a_top, a_codeObjAt, menuMc) || !menuMc.IsObject() ||
			!menuMc.GetMember("DataObj", &dataObj) || !dataObj.IsObject()) {
			return;
		}

		LiveSnapshot snap;
		{
			std::scoped_lock lock(g_snapLock);
			snap = g_snap;
		}

		// Update header/footer scalar properties on DataObj (public setters)
		dataObj.SetMember("ReadOnlyMode", RE::Scaleform::GFx::Value(std::int32_t{ 0 }));
		dataObj.SetMember("TimeHour", RE::Scaleform::GFx::Value(static_cast<double>(snap.gameHour)));
		dataObj.SetMember("DateMonth", RE::Scaleform::GFx::Value(snap.dateMonth));
		dataObj.SetMember("DateDay", RE::Scaleform::GFx::Value(snap.dateDay));
		dataObj.SetMember("DateYear", RE::Scaleform::GFx::Value(snap.dateYear));
		dataObj.SetMember("CurrLocationName", RE::Scaleform::GFx::Value(snap.locationName.c_str()));
		dataObj.SetMember("WorldMapTextureName", RE::Scaleform::GFx::Value(kDefaultWorldTexture));
		(void)kWorldMapTextureField;

		const bool newMovie = g_populatedMovie != movie;
		bool       rebuiltMarkers = false;
		if (newMovie || g_markersDirty.exchange(false)) {
			const std::size_t cornersOk =
				(MutatePoint(dataObj, "WorldMapNWCorner", kCommonwealthNWX, kCommonwealthNWY) ? 1u : 0u) +
				(MutatePoint(dataObj, "WorldMapNECorner", kCommonwealthNEX, kCommonwealthNEY) ? 1u : 0u) +
				(MutatePoint(dataObj, "WorldMapSWCorner", kCommonwealthSWX, kCommonwealthSWY) ? 1u : 0u);
			// Non-zero local map axes so LocalMapHolder never computes 1/0 = Infinity
			MutatePoint(dataObj, "LocalMapNWCorner", -2048.0, 2048.0);
			MutatePoint(dataObj, "LocalMapNECorner", 2048.0, 2048.0);
			MutatePoint(dataObj, "LocalMapSWCorner", -2048.0, -2048.0);

			RE::Scaleform::GFx::Value markersArr;
			if (dataObj.GetMember("WorldMapMarkers", &markersArr) && markersArr.IsObject()) {
				dataObj.SetMember("RemoveAllMapMarkers", RE::Scaleform::GFx::Value(true));
				markersArr.SetMember("length", RE::Scaleform::GFx::Value(std::uint32_t{ 0 }));

				std::uint32_t arrIdx = 0;
				std::uint32_t discCount = 0;
				std::uint32_t undiscCount = 0;
				for (const auto& m : g_store) {
					RE::Scaleform::GFx::Value entry;
					a_root->CreateObject(&entry, "Object");
					if (!entry.IsObject()) {
						continue;
					}
					const bool disc = IsMarkerDiscovered(m, snap.discBits);
					disc ? ++discCount : ++undiscCount;
					entry.SetMember("arrayIndex", RE::Scaleform::GFx::Value(arrIdx));
					entry.SetMember("markerId", RE::Scaleform::GFx::Value(m.localId));
					entry.SetMember("x", RE::Scaleform::GFx::Value(m.xFo4));
					entry.SetMember("y", RE::Scaleform::GFx::Value(m.yFo4));
					entry.SetMember("type", RE::Scaleform::GFx::Value(m.type));
					entry.SetMember("name", RE::Scaleform::GFx::Value(m.label.c_str()));
					entry.SetMember("undiscovered", RE::Scaleform::GFx::Value(!disc));
					if (PushMarkerObject(markersArr, entry)) {
						++arrIdx;
					}
				}

				if (g_hasCustomMarker.load()) {
					RE::Scaleform::GFx::Value wp;
					a_root->CreateObject(&wp, "Object");
					if (wp.IsObject()) {
						wp.SetMember("arrayIndex", RE::Scaleform::GFx::Value(arrIdx));
						wp.SetMember("markerId", RE::Scaleform::GFx::Value(std::uint32_t{ 0xFFFFFEu }));
						wp.SetMember("x", RE::Scaleform::GFx::Value(g_customX.load()));
						wp.SetMember("y", RE::Scaleform::GFx::Value(g_customY.load()));
						wp.SetMember("type", RE::Scaleform::GFx::Value(kPlayerSetMarkerType));
						wp.SetMember("name", RE::Scaleform::GFx::Value(""));
						if (PushMarkerObject(markersArr, wp)) {
							++arrIdx;
						}
					}
				}

				RE::Scaleform::GFx::Value playerEntry;
				a_root->CreateObject(&playerEntry, "Object");
				if (playerEntry.IsObject()) {
					playerEntry.SetMember("arrayIndex", RE::Scaleform::GFx::Value(arrIdx));
					playerEntry.SetMember("markerId", RE::Scaleform::GFx::Value(std::uint32_t{ 0xFFFFFFu }));
					playerEntry.SetMember("x", RE::Scaleform::GFx::Value(snap.playerXFo4));
					playerEntry.SetMember("y", RE::Scaleform::GFx::Value(snap.playerYFo4));
					playerEntry.SetMember("type", RE::Scaleform::GFx::Value(kPlayerLocMarkerType));
					playerEntry.SetMember("name", RE::Scaleform::GFx::Value(""));
					playerEntry.SetMember("rotation", RE::Scaleform::GFx::Value(snap.playerHeadingDeg));
					if (PushMarkerObject(markersArr, playerEntry)) {
						g_lastPlayerArrayIdx = static_cast<std::int32_t>(arrIdx);
						++arrIdx;
					}
				}

				g_populatedMovie = movie;
				rebuiltMarkers = true;
				if (++g_markerLogs <= kMaxLogLines) {
					REX::INFO("step=map_markers n={} discovered={} undiscovered={} player_idx={} corners_set={}/3 read_back={}",
						arrIdx, discCount, undiscCount, g_lastPlayerArrayIdx, cornersOk,
						cornersOk == 3 ? "match" : "partial");
				}
			}
		}

		// Track which page/tab the shell is currently showing (including pending answer)
		RE::Scaleform::GFx::Value curPageVal, curTabVal;
		if (a_answerPage.load() >= 0) {
			g_currentShellPage = a_answerPage.load();
		} else if (dataObj.GetMember("CurrentPage", &curPageVal) && curPageVal.IsUInt()) {
			g_currentShellPage = static_cast<std::int32_t>(curPageVal.GetUInt());
		}
		if (a_answerTab.load() >= 0) {
			g_currentShellTab = a_answerTab.load();
		} else if (dataObj.GetMember("CurrentTab", &curTabVal) && curTabVal.IsUInt()) {
			g_currentShellTab = static_cast<std::int32_t>(curTabVal.GetUInt());
		}

		// If markers were rebuilt while already on MAP (no pending page/tab change for ShellUpdate to invalidate),
		// trigger InvalidatePartialData(0x80) or InvalidateData() directly and clear RemoveAllMapMarkers afterward.
		if (rebuiltMarkers && a_answerPage.load() < 0 && a_answerTab.load() < 0 &&
			g_currentShellPage.load() == static_cast<std::int32_t>(g_mapPage)) {
			RE::Scaleform::GFx::Value maskArg(std::uint32_t{ 0x80u });
			RE::Scaleform::GFx::Value invRes;
			if (!menuMc.Invoke("InvalidatePartialData", &invRes, &maskArg, 1)) {
				menuMc.Invoke("InvalidateData", &invRes, nullptr, 0);
			}
			dataObj.SetMember("RemoveAllMapMarkers", RE::Scaleform::GFx::Value(false));
		}

		// Slice 2 & 3 page handshakes after RegisterMap(this) arrived
		if (g_mapPageVal.IsObject()) {
			if (g_needTexturesLoaded.exchange(false)) {
				RE::Scaleform::GFx::Value res;
				const bool called = g_mapPageVal.Invoke("onMapTexturesLoaded", &res, nullptr, 0);
				REX::INFO("step=map_textures_loaded called={}", called ? 1 : 0);
			}
			if (!g_textureLogged.load()) {
				RE::Scaleform::GFx::Value holder, bLoaded, texHolder, children;
				if (ReadDotPath(g_mapPageVal, "WorldMapHolder_mc", holder) &&
					holder.GetMember("bMapLoaded", &bLoaded) && bLoaded.IsBoolean() && bLoaded.GetBoolean()) {
					int numChildren = -1;
					if (holder.GetMember("TextureHolder_mc", &texHolder) && texHolder.IsObject() &&
						texHolder.GetMember("numChildren", &children)) {
						if (children.IsInt()) {
							numChildren = children.GetInt();
						} else if (children.IsUInt()) {
							numChildren = static_cast<int>(children.GetUInt());
						} else if (children.IsNumber()) {
							numChildren = static_cast<int>(children.GetNumber());
						}
					}
					g_textureLogged = true;
					REX::INFO("step=map_texture loaded=1 children={}", numChildren);
				}
			}
			if (g_needCenter.exchange(false) && g_lastPlayerArrayIdx >= 0) {
				RE::Scaleform::GFx::Value idxArg(static_cast<std::uint32_t>(g_lastPlayerArrayIdx));
				RE::Scaleform::GFx::Value res;
				const bool called = g_mapPageVal.Invoke("SetCenterMarker", &res, &idxArg, 1);
				REX::INFO("step=map_center idx={} called={}", g_lastPlayerArrayIdx, called ? 1 : 0);
			}
		}
	}

	void OnMenuDestroy()
	{
		g_mapPageVal = RE::Scaleform::GFx::Value{};
		g_populatedMovie = nullptr;
		g_checkedCreateObjMovie = nullptr;
		g_needTexturesLoaded = false;
		g_needCenter = false;
		g_textureLogged = false;
	}
}
