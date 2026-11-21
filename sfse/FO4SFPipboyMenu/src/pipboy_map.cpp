#include "pch.h"

#include "pipboy_map.h"
#include "blocking_menus.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <cctype>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <mutex>
#include <numbers>
#include <optional>
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
	constexpr std::uint32_t kGetExtraMapMarkerRva = 0x50A840;

	// Default 1.16.244 offsets (all configurable via FO4SFPipboyMenu.ini and verified by RTTI / ChooseGlobalSlot)
	constexpr std::size_t   kPositionAt = 0x80 + 0x0C;         // OBJ_REFR::location (float x, y, z in Starfield metres)
	constexpr std::size_t   kParentCellAt = 0xB0;
	constexpr std::size_t   kCellWorldAt = 0x110;
	constexpr std::size_t   kFormIdAt = 0x28;
	constexpr std::size_t   kDefaultHeadingAt = 0x88;          // [Kit] HeadingAt=88 (FAL-595 PC verified)
	constexpr std::size_t   kDefaultGlobalValueAt = 0x48;      // TESGlobal float32 value slot (ChooseGlobalSlot verified)
	constexpr std::size_t   kGlobalSearchFrom = 0x30;
	constexpr std::size_t   kGlobalObjectBytes = 0x60;
	constexpr float         kGlobalMinutes = 15.0f;
	constexpr float         kMaxDays = 1000000.0f;
	constexpr std::size_t   kDefaultFileListAt = 0x1570;       // TESDataHandler::files (BSSimpleList<TESFile*>)
	constexpr std::size_t   kDefaultFileCollectionAt = 0x1580; // TESDataHandler::compiledFileCollection
	constexpr std::size_t   kDefaultFileNameAt = 0x38;
	constexpr std::size_t   kFileNameSize = 260;
	constexpr std::size_t   kDefaultFileCompileIndexAt = 0x1B7;
	constexpr std::size_t   kFileRecordFlagsAt = 0x1B8;        // TESFile::recordFlags (0x200 ESL small, 0x400 ESH medium)
	constexpr std::size_t   kDefaultFileIndexAt = 0x218;
	constexpr std::size_t   kMaxFiles = 4096;
	constexpr std::size_t   kDefaultExtraListAt = 0xC8;        // TESObjectREFR::extraList (verified in SetMarkerDiscovered)
	constexpr std::size_t   kDefaultMarkerFlagsAt = 0x18;      // ExtraMapMarker flags dword (or [rax+0x18], 0x20)
	constexpr std::uint32_t kDefaultMarkerDiscMask = 0x20;     // kDiscovered bit set by SetMarkerDiscovered (rva 0x2080440)

	constexpr std::uint32_t kDefaultGameHourId = 0x38;
	constexpr std::uint32_t kDefaultGameDaysPassedId = 0x39;

	// FO4SFPipboyTravel.esm local FormIDs (written by scripts/ui/pipboy_map_store.py) and FO4SFCoreValues.esm hardcore gate (A2)
	constexpr std::uint32_t kGlobTravelTarget = 0x800;  // target marker local FormID (< 2^24, exact in float32)
	constexpr std::uint32_t kGlobTravelPlugin = 0x801;  // 0 = FO4SFMapMarkers.esm, 1 = FO4TerrainCore.esm, 2+ = other worlds
	constexpr std::uint32_t kCoreHardcoreFastTravelBlockedId = 0x841; // FO4SFCoreValues.esm GLOB FO4SF_HardcoreFastTravelBlocked
	constexpr std::uint32_t kGlobTravelIndex = 0x803;   // marker store index
	constexpr std::uint32_t kGlobTravelX = 0x804;       // merged arrival X (Starfield m)
	constexpr std::uint32_t kGlobTravelY = 0x805;       // merged arrival Y (Starfield m)
	constexpr std::uint32_t kGlobTravelZ = 0x806;       // merged arrival Z (Starfield m)
	constexpr std::uint32_t kGlobTravelH = 0x807;       // arrival heading (degrees)
	constexpr std::uint32_t kGlobDiscFirst = 0x810;     // FO4SF_MapDisc00..13 (24 bits per TESGlobal)
	constexpr std::size_t   kDiscGlobals = 14;
	constexpr std::size_t   kBitsPerGlobal = 24;        // float32 mantissa preserves 24 integer bits losslessly
	constexpr std::size_t   kPluginSlotCount = 5;       // 0..4 pluginCode table in FO4SF_PipboyTravel.psc

	constexpr std::array<std::string_view, kPluginSlotCount> kMarkerPluginFiles{ {
		"FO4SFMapMarkers.esm"sv,
		"FO4TerrainCore.esm"sv,
		"FO4CapitalWasteland.esm"sv,
		"FO4Mojave.esm"sv,
		"FO4Appalachia.esm"sv,
	} };

	constexpr std::array<std::string_view, 5> kMapUserEvents{ {
		"Map"sv,
		"SurfaceMap"sv,
		"PlanetMap"sv,
		"GalaxyMap"sv,
		"StarMap"sv,
	} };

	// Canonical Fallout 4 Commonwealth world-map corners (MNAM cells -33..28, 25..-36 -> outer cell edges in FO4 units)
	constexpr double        kCommonwealthNWX = -135168.0;
	constexpr double        kCommonwealthNWY = 106496.0;
	constexpr double        kCommonwealthNEX = 118784.0;
	constexpr double        kCommonwealthNEY = 106496.0;
	constexpr double        kCommonwealthSWX = -135168.0;
	constexpr double        kCommonwealthSWY = -147456.0;
	constexpr auto          kDefaultWorldTexture = "Textures/Interface/Pip-Boy/WorldMap_d.dds";

	// Inverse coordinate transform from merged Starfield metres to canonical FO4 Commonwealth units
	constexpr double        kMergeOffsetX = -1200.0;
	constexpr double        kMergeOffsetY = -2700.0;
	constexpr double        kFo4UnitsPerMetre = 70.0;

	// Special Pipboy_MapPage MarkerTypesA indices
	constexpr std::uint32_t kPlayerSetMarkerType = 85;
	constexpr std::uint32_t kPlayerLocMarkerType = 86;
	constexpr std::uint32_t kMaxLocationIconType = 84;  // 85 and 86 are reserved for PlayerSetMarker and PlayerLocMarker

	constexpr std::size_t   kMaxStoreMarkers = kDiscGlobals * kBitsPerGlobal;
	constexpr std::size_t   kMaxMapMenus = 16;
	constexpr std::size_t   kMaxName = 64;
	constexpr std::uint32_t kMaxLogLines = 64;
	constexpr std::int64_t  kMapKeyCooldownMs = 350;
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
		kGetExtraMapMarker,
		kExtraMapMarkerRtti,
		kTesFullNameRtti,
		kObjectRefrRtti,
		kTesFileRtti,
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
		{ "ExtraDataList.GetExtraMapMarker", 44761, {}, kGetExtraMapMarkerRva },
		{ "ExtraMapMarker.RTTI", 845517, "ExtraMapMarker@@"sv, 0 },
		{ "TESFullName.RTTI", 843072, "TESFullName@@"sv, 0 },
		{ "TESObjectREFR.RTTI", 840386, "TESObjectREFR@@"sv, 0 },
		{ "TESFile.RTTI", 845789, "TESFile@@"sv, 0 },
	} };

	struct StoreMarker
	{
		std::uint32_t index = 0;
		std::uint32_t pluginCode = 0;   // 0 = FO4SFMapMarkers.esm, 1 = FO4TerrainCore.esm, 2+ = other worlds
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
		std::uint32_t                             dateYear = 287;   // DateYear = year - 2000 (Pipboy_BottomBar prefixes ".2")
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
	using GetExtraMapMarker_t = void* (*)(std::uintptr_t);

	bool                                   g_on = false;
	std::uintptr_t                         g_base = 0;
	std::size_t                            g_imageSize = 0;
	std::array<std::uint32_t, kMapIdCount> g_rva{};
	const SFSE::TaskInterface*             g_task = nullptr;
	PipboyMap::OpenRequestFn               g_openFn = nullptr;
	PipboyMap::CloseRequestFn              g_closeFn = nullptr;
	PipboyMap::GfxEnterFn                  g_gfxEnterFn = nullptr;
	PipboyMap::GfxExitFn                   g_gfxExitFn = nullptr;
	PipboyMap::BlockedMenuFactoryFn        g_blockedFactoryFn = nullptr;

	std::uint32_t                          g_mapKey = 0x4D;
	std::uint32_t                          g_mapPage = 3;
	std::uint32_t                          g_mapDefaultTab = 0;
	bool                                   g_mapSurvival = false;
	bool                                   g_blockStarMap = false;
	std::size_t                            g_headingAt = kDefaultHeadingAt;
	bool                                   g_headingTurnsDown = false;
	std::size_t                            g_configuredGlobalValueAt = 0;   // 0 = auto-verify via ChooseMapGlobalSlot
	std::size_t                            g_verifiedGlobalValueAt = 0;
	bool                                   g_globalLogged = false;
	bool                                   g_headingLogged = false;
	std::uint32_t                          g_gameHourId = kDefaultGameHourId;
	std::uint32_t                          g_gameDaysPassedId = kDefaultGameDaysPassedId;
	std::size_t                            g_fileCollectionAt = kDefaultFileCollectionAt;
	std::size_t                            g_fileNameAt = kDefaultFileNameAt;
	std::size_t                            g_fileCompileIndexAt = kDefaultFileCompileIndexAt;
	std::size_t                            g_fileIndexAt = kDefaultFileIndexAt;
	std::size_t                            g_extraListAt = kDefaultExtraListAt;
	std::size_t                            g_markerFlagsAt = kDefaultMarkerFlagsAt;
	std::uint32_t                          g_markerDiscMask = kDefaultMarkerDiscMask;

	std::string                            g_travelPlugin = "FO4SFPipboyTravel.esm";
	std::string                            g_travelScript = "FO4SF_PipboyTravel";
	std::string                            g_travelFunction = "Go";
	std::vector<std::string>               g_mapMenus;
	std::vector<StoreMarker>               g_store;

	std::atomic<bool>                      g_menuOpen{ false };
	std::atomic<bool>                      g_closing{ false };
	std::atomic<bool>                      g_mapInputHeld{ false };
	std::atomic<bool>                      g_keyDown{ false };
	std::atomic<std::int64_t>              g_lastMapTransitionMs{ 0 };
	std::atomic<std::uint32_t>             g_keyPresses{ 0 };
	std::atomic<std::uint32_t>             g_suppressions{ 0 };
	std::atomic<std::uint32_t>             g_starMapBlocks{ 0 };
	std::atomic<std::uint32_t>             g_inputLogs{ 0 };
	std::atomic<std::uint32_t>             g_discSyncLogs{ 0 };
	std::atomic<std::uint32_t>             g_tickCount{ 0 };
	std::atomic<std::int32_t>              g_requestedPage{ -1 };
	std::atomic<std::int32_t>              g_requestedTab{ -1 };
	std::atomic<bool>                      g_markersDirty{ true };
	std::atomic<bool>                      g_needTexturesLoaded{ false };
	std::atomic<bool>                      g_needCenter{ false };
	std::atomic<std::int32_t>              g_requestedCenterMarkerId{ -1 };
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

	std::int64_t NowMs()
	{
		return std::chrono::duration_cast<std::chrono::milliseconds>(
			std::chrono::steady_clock::now().time_since_epoch())
		    .count();
	}

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

	std::string ReadSectionText(const std::filesystem::path& a_ini, const wchar_t* a_section, const wchar_t* a_key)
	{
		std::array<wchar_t, 512> buf{};
		REX::W32::GetPrivateProfileStringW(a_section, a_key, L"", buf.data(),
			static_cast<std::uint32_t>(buf.size()), a_ini.c_str());
		std::string out;
		for (const wchar_t* p = buf.data(); *p; ++p) {
			out += (*p >= 0x20 && *p < 0x7F) ? static_cast<char>(*p) : '?';
		}
		return out;
	}

	std::string ReadIniText(const std::filesystem::path& a_ini, const wchar_t* a_key)
	{
		return ReadSectionText(a_ini, L"FO4SFPipboyMenu", a_key);
	}

	std::uint32_t ReadIniNumber(const std::filesystem::path& a_ini, const wchar_t* a_key, std::uint32_t a_default)
	{
		const auto text = ReadIniText(a_ini, a_key);
		return text.empty() ? a_default : static_cast<std::uint32_t>(std::strtoul(text.c_str(), nullptr, 0));
	}

	bool ParseHeadingSpec(std::string_view a_spec, std::size_t& a_at, bool& a_turnsDown)
	{
		while (!a_spec.empty() && (a_spec.front() == ' ' || a_spec.front() == '\t')) {
			a_spec.remove_prefix(1);
		}
		while (!a_spec.empty() && (a_spec.back() == ' ' || a_spec.back() == '\t')) {
			a_spec.remove_suffix(1);
		}
		if (a_spec.empty()) {
			return false;
		}
		const bool down = a_spec.front() == '-';
		if (down) {
			a_spec.remove_prefix(1);
		}
		if (a_spec.starts_with("0x") || a_spec.starts_with("0X")) {
			a_spec.remove_prefix(2);
		}
		if (a_spec.empty() || a_spec.size() > 3 ||
			!std::ranges::all_of(a_spec, [](unsigned char c) { return std::isxdigit(c) != 0; })) {
			return false;
		}
		const auto parsed = static_cast<std::size_t>(std::strtoul(std::string(a_spec).c_str(), nullptr, 16));
		if (parsed < 0x40 || parsed > 0x200 || (parsed % 4) != 0) {
			return false;
		}
		a_at = parsed;
		a_turnsDown = down;
		return true;
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

	std::optional<std::uint32_t> BaseOffset(const ObjectType& a_type, std::string_view a_tail)
	{
		const auto hierarchy = a_type.hierarchy;
		if (!InImage(hierarchy, 0x10)) {
			return std::nullopt;
		}
		const auto count = *reinterpret_cast<const std::uint32_t*>(hierarchy + 0x08);
		const auto array = g_base + *reinterpret_cast<const std::uint32_t*>(hierarchy + 0x0C);
		if (count == 0 || count > 512 || !InImage(array, 4ull * count)) {
			return std::nullopt;
		}
		std::optional<std::uint32_t> found;
		std::size_t                  matches = 0;
		for (std::uint32_t i = 0; i < count; ++i) {
			const auto base = g_base + reinterpret_cast<const std::uint32_t*>(array)[i];
			if (!InImage(base, 0x1C)) {
				return std::nullopt;
			}
			if (!NameIs(TypeNameAt(g_base + *reinterpret_cast<const std::uint32_t*>(base)), a_tail)) {
				continue;
			}
			const auto mdisp = *reinterpret_cast<const std::int32_t*>(base + 0x08);
			const auto pdisp = *reinterpret_cast<const std::int32_t*>(base + 0x0C);
			if (pdisp != -1 || mdisp < 0) {
				return std::nullopt;
			}
			found = static_cast<std::uint32_t>(mdisp);
			++matches;
		}
		return matches == 1 ? found : std::nullopt;
	}

	// TESDataHandler's compiled file lists hold TESPackedFile (subclass of TESFile at +0, FAL-437; IsType(file, "TESFile@@") alone skips packed files)
	bool IsFileType(const ObjectType& a_type)
	{
		return a_type.offset == 0 && (NameIs(a_type.name, "TESFile@@") || BaseOffset(a_type, "TESFile@@") == 0u);
	}

	// REL::ID 44761 (RVA 0x50A840) dereferences [ExtraMapMarker + 0x18] and returns MAP_MARKER_DATA*, whose vtable at +0
	// is TESFullName@@ (checked via kTesFullNameRtti 843072); also accept ExtraMapMarker@@ if an INI override points at BSExtraData
	bool IsMapMarkerDataType(std::uintptr_t a_object)
	{
		ObjectType t;
		return TypeOf(a_object, t) && t.offset == 0 &&
		       (NameIs(t.name, "TESFullName@@") || BaseOffset(t, "TESFullName@@") == 0u ||
				   NameIs(t.name, "ExtraMapMarker@@") || BaseOffset(t, "ExtraMapMarker@@") == 0u);
	}

	bool IsRefrType(std::uintptr_t a_object)
	{
		ObjectType t;
		return TypeOf(a_object, t) && t.offset == 0 &&
		       (NameIs(t.name, "TESObjectREFR@@") || BaseOffset(t, "TESObjectREFR@@") == 0u);
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
			// Clamp location icon types below 85 so a store row can never collide with PlayerSetMarker (85) or PlayerLocMarker (86)
			m.type = std::min<std::uint32_t>(static_cast<std::uint32_t>(std::strtoul(cols[3].c_str(), nullptr, 10)), kMaxLocationIconType);
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

	// Verifies a candidate plugin prefix against a known form + RTTI (as main.cpp KitFileForm does) so an unverified
	// TESFile offset can never assign a wrong load-order prefix to a full or light plugin
	bool VerifyPluginCandidate(std::string_view a_fileName, std::uint32_t a_prefix, bool a_small)
	{
		const std::uint32_t mask = a_small ? 0xFFFu : 0xFFFFFFu;
		if (SameAscii(a_fileName, g_travelPlugin)) {
			const auto form = LookupForm(a_prefix | (kGlobTravelTarget & mask));
			return form && IsType(form, "TESGlobal@@");
		}
		for (const auto& m : g_store) {
			if (m.pluginCode < kPluginSlotCount && SameAscii(a_fileName, kMarkerPluginFiles[m.pluginCode])) {
				const auto refr = LookupForm(a_prefix | (m.localId & mask));
				return refr && IsRefrType(refr);
			}
		}
		return true;
	}

	bool ChooseVerifiedFilePrefix(std::string_view a_fileName, std::uintptr_t a_file, int a_listKind,
		std::uint32_t& a_prefix, bool& a_small)
	{
		std::uint8_t                compileIdx = 0xFF;
		std::uint32_t               recordFlags = 0;
		std::array<std::uint8_t, 4> indexBytes{};
		if (!Peek(a_file + g_fileCompileIndexAt, compileIdx) ||
			!PeekBytes(a_file + g_fileIndexAt, indexBytes.data(), indexBytes.size())) {
			return false;
		}
		Peek(a_file + kFileRecordFlagsAt, recordFlags);

		struct Candidate
		{
			std::uint32_t prefix;
			bool          small;
		};
		std::array<Candidate, 4> candidates{};
		std::size_t              candCount = 0;
		const auto addCandidate = [&](std::uint32_t p, bool s) {
			for (std::size_t i = 0; i < candCount; ++i) {
				if (candidates[i].prefix == p && candidates[i].small == s) {
					return;
				}
			}
			if (candCount < candidates.size()) {
				candidates[candCount++] = { p, s };
			}
		};

		if (a_listKind == 1 || compileIdx == 0xFE || indexBytes[0] == 0xFE || (recordFlags & 0x200u) != 0) {
			const std::uint32_t smallIdx = static_cast<std::uint32_t>(indexBytes[2]) |
			                               (static_cast<std::uint32_t>(indexBytes[3]) << 8);
			addCandidate(0xFE000000u | ((smallIdx & 0xFFFu) << 12), true);
		}
		if (a_listKind == 2 || compileIdx == 0xFD || indexBytes[0] == 0xFD || (recordFlags & 0x400u) != 0) {
			addCandidate(0xFD000000u | (static_cast<std::uint32_t>(indexBytes[1]) << 16), false);
		}
		if (compileIdx < 0xFD) {
			addCandidate(static_cast<std::uint32_t>(compileIdx) << 24, false);
		}
		if ((a_listKind <= 0) && indexBytes[0] < 0xFD) {
			addCandidate(static_cast<std::uint32_t>(indexBytes[0]) << 24, false);
		}

		for (std::size_t i = 0; i < candCount; ++i) {
			if (VerifyPluginCandidate(a_fileName, candidates[i].prefix, candidates[i].small)) {
				a_prefix = candidates[i].prefix;
				a_small = candidates[i].small;
				return true;
			}
		}
		return false;
	}

	// Finds the runtime FormID prefix (upper bits) of an active plugin by file name in TESDataHandler::compiledFileCollection,
	// checking TESFile@@ / TESPackedFile@@ RTTI and verifying the prefix against a known form's RTTI
	bool ResolvePluginPrefix(std::string_view a_fileName, std::uint32_t& a_prefix, bool& a_small)
	{
		std::uintptr_t handler = 0;
		if (!Peek(Address(kDataHandlerSingleton), handler) || !handler || !IsType(handler, "TESDataHandler@@")) {
			return false;
		}
		for (int listKind = 0; listKind < 3; ++listKind) {
			ArrayHead list{};
			if (!Peek(handler + g_fileCollectionAt + static_cast<std::size_t>(listKind) * sizeof(ArrayHead), list) ||
				list.size > list.capacity || list.size > kMaxFiles || (list.size && !list.data)) {
				continue;
			}
			const auto n = std::min<std::size_t>(list.size, kMaxFiles);
			for (std::size_t i = 0; i < n; ++i) {
				std::uintptr_t file = 0;
				if (!Peek(list.data + 8ull * i, file) || !file) {
					continue;
				}
				ObjectType fileType;
				if (!TypeOf(file, fileType) || !IsFileType(fileType)) {
					continue;
				}
				std::array<char, kFileNameSize> rawName{};
				if (!PeekBytes(file + g_fileNameAt, rawName.data(), rawName.size())) {
					continue;
				}
				rawName.back() = '\0';
				const std::string_view fileView(rawName.data(), strnlen(rawName.data(), rawName.size()));
				if (!SameAscii(fileView, a_fileName)) {
					continue;
				}
				if (ChooseVerifiedFilePrefix(a_fileName, file, listKind, a_prefix, a_small)) {
					return true;
				}
			}
		}

		// Fallback: walk TESDataHandler::files BSSimpleList<TESFile*> at +0x1570 (handles TESFile@@ and TESPackedFile@@)
		if (g_fileCollectionAt >= 0x10) {
			const std::size_t fileListAt = (g_fileCollectionAt == kDefaultFileCollectionAt) ? kDefaultFileListAt : (g_fileCollectionAt - 0x10);
			std::uintptr_t    nodeAddr = handler + fileListAt;
			for (std::size_t step = 0; step < kMaxFiles && nodeAddr; ++step) {
				std::uintptr_t file = 0;
				std::uintptr_t nextNode = 0;
				if (!Peek(nodeAddr, file) || !Peek(nodeAddr + sizeof(std::uintptr_t), nextNode)) {
					break;
				}
				nodeAddr = nextNode;
				if (!file) {
					continue;
				}
				ObjectType fileType;
				if (!TypeOf(file, fileType) || !IsFileType(fileType)) {
					continue;
				}
				std::array<char, kFileNameSize> rawName{};
				if (!PeekBytes(file + g_fileNameAt, rawName.data(), rawName.size())) {
					continue;
				}
				rawName.back() = '\0';
				const std::string_view fileView(rawName.data(), strnlen(rawName.data(), rawName.size()));
				if (!SameAscii(fileView, a_fileName)) {
					continue;
				}
				if (ChooseVerifiedFilePrefix(a_fileName, file, -1, a_prefix, a_small)) {
					return true;
				}
			}
		}
		return false;
	}

	bool ReadTimeAt(std::uintptr_t a_hourForm, std::uintptr_t a_daysForm, std::size_t a_at, float& a_hour, float& a_days)
	{
		if (!a_at || a_at == kFormIdAt || !a_hourForm || !a_daysForm ||
			!Peek(a_hourForm + a_at, a_hour) || !Peek(a_daysForm + a_at, a_days) ||
			!std::isfinite(a_hour) || !std::isfinite(a_days) ||
			a_hour < 0.0f || a_hour >= 24.0f || a_days <= 0.0f || a_days >= kMaxDays) {
			return false;
		}
		const float apart = std::fabs(std::fmod(a_days, 1.0f) * 24.0f - a_hour);
		return std::min(apart, 24.0f - apart) * 60.0f <= kGlobalMinutes;
	}

	// Self-verifies TESGlobal value offset (as main.cpp FindGlobalValue / ChooseGlobalSlot does), unless overridden in INI
	std::size_t EnsureGlobalValueOffset(std::uintptr_t a_hourForm, std::uintptr_t a_daysForm)
	{
		if (g_verifiedGlobalValueAt) {
			return g_verifiedGlobalValueAt;
		}
		if (g_configuredGlobalValueAt) {
			g_verifiedGlobalValueAt = g_configuredGlobalValueAt;
			if (!g_globalLogged) {
				g_globalLogged = true;
				REX::INFO("step=map_globals value_at={} source=ini", Hex(g_verifiedGlobalValueAt));
			}
			return g_verifiedGlobalValueAt;
		}
		if (!IsType(a_hourForm, "TESGlobal@@") || !IsType(a_daysForm, "TESGlobal@@")) {
			return 0;
		}
		float hour = 0.0f;
		float days = 0.0f;
		std::size_t chosen = 0;
		if (ReadTimeAt(a_hourForm, a_daysForm, kDefaultGlobalValueAt, hour, days)) {
			chosen = kDefaultGlobalValueAt;
		} else {
			for (std::size_t at = kGlobalSearchFrom; at + sizeof(float) <= kGlobalObjectBytes; at += 4) {
				if (at != kFormIdAt && at != kDefaultGlobalValueAt && ReadTimeAt(a_hourForm, a_daysForm, at, hour, days)) {
					chosen = at;
					break;
				}
			}
		}
		if (chosen) {
			ReadTimeAt(a_hourForm, a_daysForm, chosen, hour, days);
			g_verifiedGlobalValueAt = chosen;
			if (!g_globalLogged) {
				g_globalLogged = true;
				REX::INFO("step=map_globals value_at={} source=verified game_hour={:.4f} game_days_passed={:.4f}",
					Hex(chosen), hour, days);
			}
		}
		return g_verifiedGlobalValueAt;
	}

	std::uintptr_t LookupPluginGlobal(std::uint32_t a_prefix, bool a_small, std::uint32_t a_localId)
	{
		const std::uint32_t mask = a_small ? 0xFFFu : 0xFFFFFFu;
		const auto          form = LookupForm(a_prefix | (a_localId & mask));
		return (form && IsType(form, "TESGlobal@@")) ? form : 0;
	}

	bool ReadGlobalFloat(std::uintptr_t a_glob, float& a_out)
	{
		return a_glob && g_verifiedGlobalValueAt && Peek(a_glob + g_verifiedGlobalValueAt, a_out) && std::isfinite(a_out);
	}

	bool WriteGlobalFloat(std::uintptr_t a_glob, float a_val, float& a_readBack)
	{
		return a_glob && g_verifiedGlobalValueAt && PokeFloat(a_glob + g_verifiedGlobalValueAt, a_val) &&
		       ReadGlobalFloat(a_glob, a_readBack);
	}

	// Reads live engine map-marker discovery state (ExtraMapMarker flags & 0x20, set by ObjectReference.SetMarkerDiscovered)
	bool IsEngineMarkerDiscovered(std::uint32_t a_prefix, bool a_small, std::uint32_t a_localId)
	{
		if (!g_rva[kGetExtraMapMarker]) {
			return false;
		}
		const std::uint32_t mask = a_small ? 0xFFFu : 0xFFFFFFu;
		const auto          refr = LookupForm(a_prefix | (a_localId & mask));
		if (!refr || !IsRefrType(refr)) {
			return false;
		}
		std::uintptr_t extraList = 0;
		if (!Peek(refr + g_extraListAt, extraList) || !extraList) {
			return false;
		}
		const auto fn = reinterpret_cast<GetExtraMapMarker_t>(Address(kGetExtraMapMarker));
		const auto emm = reinterpret_cast<std::uintptr_t>(fn(extraList));
		if (!emm || !IsMapMarkerDataType(emm)) {
			return false;
		}
		std::uint32_t flags = 0;
		return Peek(emm + g_markerFlagsAt, flags) && ((flags & g_markerDiscMask) != 0);
	}

	void DaysToCalendar(float a_daysPassed, std::uint32_t& a_month, std::uint32_t& a_day, std::uint32_t& a_year)
	{
		static constexpr std::array<int, 12> kMonthDays{ 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 };
		int total = std::max(0, static_cast<int>(std::floor(a_daysPassed)));
		int y = 2287;
		int m = 9;   // 0-based October (Oct 23, 2287)
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
		a_year = static_cast<std::uint32_t>(y >= 2000 ? (y - 2000) : y);
	}

	// Main thread only: refreshes player position/heading, clock, survival mode, and syncs live engine discovery into FO4SF_MapDisc00..13
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
			if (g_headingAt && Peek(player + g_headingAt, yawRad) && std::isfinite(yawRad) && std::fabs(yawRad) <= 1000.0f) {
				const double signedRad = g_headingTurnsDown ? -static_cast<double>(yawRad) : static_cast<double>(yawRad);
				double       deg = std::fmod(signedRad * (180.0 / std::numbers::pi), 360.0);
				if (deg < 0.0) {
					deg += 360.0;
				}
				next.playerHeadingDeg = deg;
				if (!g_headingLogged) {
					g_headingLogged = true;
					REX::INFO("step=map_heading heading_at={}+{:03X} rad={:.4f} deg={:.1f}",
						g_headingTurnsDown ? "-" : "", g_headingAt, yawRad, deg);
				}
			}
			std::uintptr_t cell = 0;
			std::uintptr_t world = 0;
			if (Peek(player + kParentCellAt, cell) && cell && Peek(cell + kCellWorldAt, world)) {
				next.locationName = world ? "COMMONWEALTH" : "INTERIOR";
			}
		}

		const auto hourForm = LookupForm(g_gameHourId);
		const auto daysForm = LookupForm(g_gameDaysPassedId);
		EnsureGlobalValueOffset(hourForm, daysForm);
		float hour = 0.0f;
		float days = 0.0f;
		if (IsType(hourForm, "TESGlobal@@") && ReadGlobalFloat(hourForm, hour) && hour >= 0.0f && hour < 24.0f) {
			next.gameHour = hour;
		}
		if (IsType(daysForm, "TESGlobal@@") && ReadGlobalFloat(daysForm, days) && days >= 0.0f && days < kMaxDays) {
			DaysToCalendar(days, next.dateMonth, next.dateDay, next.dateYear);
		}

		static bool   loggedCoreSurvivalResolve = false;
		std::uint32_t corePrefix = 0;
		bool          coreSmall = false;
		if (g_verifiedGlobalValueAt != 0) {
			std::uintptr_t survGlob = 0;
			std::uint32_t  survFormId = 0;
			if (ResolvePluginPrefix("FO4SFCoreValues.esm", corePrefix, coreSmall)) {
				survGlob = LookupPluginGlobal(corePrefix, coreSmall, kCoreHardcoreFastTravelBlockedId);
				if (survGlob) {
					Peek(survGlob + kFormIdAt, survFormId);
				}
			}
			if (!loggedCoreSurvivalResolve) {
				loggedCoreSurvivalResolve = true;
				REX::INFO("step=core_value_resolve name=FO4SF_HardcoreFastTravelBlocked source=FO4SFCoreValues.esm:{:06X} found={} form={:08X}",
					kCoreHardcoreFastTravelBlockedId, survGlob ? 1 : 0, survFormId);
			}
			float surv = 0.0f;
			if (survGlob && ReadGlobalFloat(survGlob, surv)) {
				next.liveSurvival = surv >= 0.5f;
			}
		}

		std::uint32_t travelPrefix = 0;
		bool          travelSmall = false;
		const bool    haveTravelPlugin = g_verifiedGlobalValueAt != 0 &&
		                                 ResolvePluginPrefix(g_travelPlugin, travelPrefix, travelSmall);
		if (haveTravelPlugin) {
			for (std::size_t i = 0; i < kDiscGlobals; ++i) {
				float      bits = 0.0f;
				const auto glob = LookupPluginGlobal(travelPrefix, travelSmall, kGlobDiscFirst + static_cast<std::uint32_t>(i));
				if (ReadGlobalFloat(glob, bits) && bits >= 0.0f && bits < static_cast<float>(1u << kBitsPerGlobal)) {
					next.discBits[i] = static_cast<std::uint32_t>(bits) & ((1u << kBitsPerGlobal) - 1u);
				}
			}
		}

		// Sync live engine ExtraMapMarker kDiscovered (0x20, e.g. from Vault 111 exit lift reveal) + init_disc into discBits
		std::array<std::uint32_t, kPluginSlotCount> markerPrefixes{};
		std::array<bool, kPluginSlotCount>          markerSmall{};
		std::array<bool, kPluginSlotCount>          markerLoaded{};
		for (std::size_t p = 0; p < kPluginSlotCount; ++p) {
			markerLoaded[p] = ResolvePluginPrefix(kMarkerPluginFiles[p], markerPrefixes[p], markerSmall[p]);
		}

		std::array<bool, kDiscGlobals> dirtyGroups{};
		std::uint32_t                  newlySynced = 0;
		for (const auto& m : g_store) {
			const std::size_t grp = m.index / kBitsPerGlobal;
			const std::size_t bit = m.index % kBitsPerGlobal;
			if (grp >= kDiscGlobals) {
				continue;
			}
			const bool oldBit = ((next.discBits[grp] >> bit) & 1u) != 0;
			bool       engineDisc = false;
			if (m.pluginCode < kPluginSlotCount && markerLoaded[m.pluginCode]) {
				engineDisc = IsEngineMarkerDiscovered(markerPrefixes[m.pluginCode], markerSmall[m.pluginCode], m.localId);
			}
			if ((m.initialDiscovered || engineDisc) && !oldBit) {
				next.discBits[grp] |= (1u << bit);
				dirtyGroups[grp] = true;
				if (engineDisc) {
					++newlySynced;
				}
			}
		}

		if (haveTravelPlugin) {
			for (std::size_t grp = 0; grp < kDiscGlobals; ++grp) {
				if (!dirtyGroups[grp]) {
					continue;
				}
				const auto glob = LookupPluginGlobal(travelPrefix, travelSmall, kGlobDiscFirst + static_cast<std::uint32_t>(grp));
				float      rb = -1.0f;
				const float want = static_cast<float>(next.discBits[grp]);
				const bool  ok = WriteGlobalFloat(glob, want, rb) && rb == want;
				if (++g_discSyncLogs <= kMaxLogLines) {
					REX::INFO("step=map_disc_sync group={} bits={:#x} engine_new={} written={}", grp, next.discBits[grp],
						newlySynced, ok ? 1 : 0);
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

	// T2 (Round 6): default MapBlockStarMap=0 uses hide-only SuppressVanillaMapMenus() (proven outdoor M-key safe).
	// When MapBlockStarMap=1 is opted in, BlockedMapMenuCreateForSlot constructs a real non-null minimal self-hiding
	// IMenu via g_blockedFactoryFn so callers dereferencing [menu + 0xB0] immediately after initFunc never read nullptr.
	RE::Scaleform::Ptr<RE::IMenu>* BlockedMapMenuCreateForSlot(RE::Scaleform::Ptr<RE::IMenu>* a_out, std::size_t a_slot)
	{
		const char* menuName = (a_slot < g_mapMenus.size()) ? g_mapMenus[a_slot].c_str() : "GalaxyStarMapMenu";
		bool        nonNull = false;
		if (g_blockedFactoryFn && g_blockedFactoryFn(menuName, a_out)) {
			nonNull = true;
		} else {
			std::construct_at(a_out);
		}
		const auto n = ++g_starMapBlocks;
		if (n <= kMaxLogLines) {
			REX::INFO("step=starmap_blocked n={} blocked menu={} route=create non_null={}", n, menuName, nonNull ? 1 : 0);
		}
		return a_out;
	}

	RE::Scaleform::Ptr<RE::IMenu>* BlockedStarMapCreate(RE::Scaleform::Ptr<RE::IMenu>* a_out)
	{
		return BlockedMapMenuCreateForSlot(a_out, 0);
	}

	template <std::size_t Slot>
	RE::Scaleform::Ptr<RE::IMenu>* BlockedStarMapCreateSlot(RE::Scaleform::Ptr<RE::IMenu>* a_out)
	{
		return BlockedMapMenuCreateForSlot(a_out, Slot);
	}

	using MenuCreateFn = RE::Scaleform::Ptr<RE::IMenu>* (*)(RE::Scaleform::Ptr<RE::IMenu>*);

	constexpr std::array<MenuCreateFn, kMaxMapMenus> kBlockedMapMenuCreators{ {
		&BlockedStarMapCreate,
		&BlockedStarMapCreateSlot<1>,
		&BlockedStarMapCreateSlot<2>,
		&BlockedStarMapCreateSlot<3>,
		&BlockedStarMapCreateSlot<4>,
		&BlockedStarMapCreateSlot<5>,
		&BlockedStarMapCreateSlot<6>,
		&BlockedStarMapCreateSlot<7>,
		&BlockedStarMapCreateSlot<8>,
		&BlockedStarMapCreateSlot<9>,
		&BlockedStarMapCreateSlot<10>,
		&BlockedStarMapCreateSlot<11>,
		&BlockedStarMapCreateSlot<12>,
		&BlockedStarMapCreateSlot<13>,
		&BlockedStarMapCreateSlot<14>,
		&BlockedStarMapCreateSlot<15>,
	} };

	bool IsBlockedMapCreator(MenuCreateFn a_fn)
	{
		for (const auto fn : kBlockedMapMenuCreators) {
			if (fn == a_fn) {
				return true;
			}
		}
		return false;
	}

	std::array<bool, kMaxMapMenus> g_mapSlotInstalled{};
	std::uint32_t                  g_mapInstallRetryCount = 0;
	bool                           g_loggedPostHudMapRetry = false;

	bool HasPendingMapBlockSlots()
	{
		if (!g_blockStarMap) {
			return false;
		}
		for (std::size_t slot = 0; slot < g_mapMenus.size() && slot < kMaxMapMenus; ++slot) {
			if (!g_mapSlotInstalled[slot] && !SameAscii(g_mapMenus[slot].c_str(), "MapMenu")) {
				return true;
			}
		}
		return false;
	}

	void InstallStarMapBlock(bool a_isRetry = false)
	{
		if (!g_blockStarMap) {
			return;
		}
		auto* ui = RE::UI::GetSingleton();
		if (!ui) {
			return;
		}
		const std::uint32_t retryNum = a_isRetry ? ++g_mapInstallRetryCount : 0;
		std::uint32_t       newlyInstalled = 0;
		for (std::size_t slot = 0; slot < g_mapMenus.size() && slot < kMaxMapMenus; ++slot) {
			if (a_isRetry && g_mapSlotInstalled[slot]) {
				continue;
			}
			const auto& blocked = g_mapMenus[slot];
			bool        found = false;
			for (auto& entry : ui->menuMap) {
				const char* rawKey = entry.key.c_str();
				if (!rawKey || !SameAscii(rawKey, blocked)) {
					continue;
				}
				found = true;
				const auto origAddr = reinterpret_cast<std::uintptr_t>(entry.value.initFunc);
				if (IsBlockedMapCreator(entry.value.initFunc)) {
					g_mapSlotInstalled[slot] = true;
					if (!a_isRetry) {
						REX::INFO("step=starmap_block_install menu={} found=1 slot={} orig_rva=already_installed", blocked, slot);
					}
					break;
				}
				if (!InImage(origAddr, 1)) {
					RefuseStep("starmap_block", std::format("menu={} init_func={} reason=outside_image", blocked, Hex(origAddr)));
					break;
				}
				if (slot == 0) {
					entry.value.initFunc = &BlockedStarMapCreate;
				} else {
					entry.value.initFunc = kBlockedMapMenuCreators[slot];
				}
				g_mapSlotInstalled[slot] = true;
				++newlyInstalled;
				if (a_isRetry) {
					REX::INFO("step=starmap_block_install menu={} found=1 slot={} orig_rva={} retry={}",
						blocked, slot, Hex(origAddr - g_base), retryNum);
				} else {
					REX::INFO("step=starmap_block_install menu={} found=1 slot={} orig_rva={}",
						blocked, slot, Hex(origAddr - g_base));
				}
				break;
			}
			if (!found && !a_isRetry) {
				REX::INFO("step=starmap_block_install menu={} found=0", blocked);
			}
		}
		if (a_isRetry && (newlyInstalled > 0 || !g_loggedPostHudMapRetry)) {
			g_loggedPostHudMapRetry = true;
			std::string pending;
			for (std::size_t slot = 0; slot < g_mapMenus.size() && slot < kMaxMapMenus; ++slot) {
				if (!g_mapSlotInstalled[slot]) {
					if (!pending.empty()) {
						pending += ',';
					}
					pending += g_mapMenus[slot];
				}
			}
			REX::INFO("step=starmap_block_retry try={} newly_installed={} pending={}",
				retryNum, newlyInstalled, pending.empty() ? "none" : pending);
		}
	}

	// Main thread fallback: hides any open vanilla menu in MapMenus= and NEVER opens or reopens FO4SF_PipboyMenu
	// (preventing any close-then-reopen bounce loop)
	bool SuppressVanillaMapMenus()
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
		return suppressed;
	}

	const char* OpenBlockingMapMenu(RE::UI* a_ui, bool a_topModalOnly = false)
	{
		return fo4sf::FindOpenBlockingMenu(a_ui, a_topModalOnly, false);
	}

	// Main thread: opens FO4SF_PipboyMenu on MAP when pressed from gameplay (closed state)
	void HandleClosedMapKeyMainThread(std::uint32_t a_n)
	{
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue) {
			return;
		}
		SuppressVanillaMapMenus();
		if (ui->IsMenuOpen(OurMenuFixed())) {
			return;   // Open-menu MapKey is handled exclusively by OnButtonInput (IMenu input vtable)
		}
		if (const char* blocking = OpenBlockingMapMenu(ui)) {
			REX::INFO("step=map_key n={} vk={} ignored=menu_open menu={}", a_n, Hex(g_mapKey), blocking);
			return;
		}
		g_lastMapTransitionMs = NowMs();
		CollectMainThreadState();
		g_markersDirty = true;
		if (g_openFn) {
			g_openFn(g_mapPage, "map_key");
			REX::INFO("step=map_key n={} vk={} was_open=0 page={} sent=request_open", a_n, Hex(g_mapKey), g_mapPage);
			return;
		}
		g_requestedPage = static_cast<std::int32_t>(g_mapPage);
		g_requestedTab = 0;
		queue->AddMessage(OurMenuFixed(), RE::UI_MESSAGE_TYPE::kShow);
		REX::INFO("step=map_key n={} vk={} was_open=0 page={} sent=show", a_n, Hex(g_mapKey), g_mapPage);
	}

	// Main thread: handles MapKey swallowed by FO4SF_PipboyMenu's BSInputEventUser vtable while open
	void HandleOpenMenuMapKeyMainThread(std::uint32_t a_n)
	{
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue) {
			return;
		}
		SuppressVanillaMapMenus();
		if (!ui->IsMenuOpen(OurMenuFixed())) {
			return;
		}
		g_lastMapTransitionMs = NowMs();
		if (g_currentShellPage.load() == static_cast<std::int32_t>(g_mapPage) && !g_modalOpen.load()) {
			if (g_closeFn) {
				g_closeFn(a_n, "map_key");
			} else {
				queue->AddMessage(OurMenuFixed(), RE::UI_MESSAGE_TYPE::kHide);
			}
			REX::INFO("step=map_key n={} vk={} was_open=1 on_map=1 sent=hide", a_n, Hex(g_mapKey));
			return;
		}
		CollectMainThreadState();
		g_requestedPage = static_cast<std::int32_t>(g_mapPage);
		g_requestedTab = 0;
		g_markersDirty = true;
		queue->AddMessage(OurMenuFixed(), RE::UI_MESSAGE_TYPE::kUpdate);
		REX::INFO("step=map_key n={} vk={} was_open=1 page={} sent=update", a_n, Hex(g_mapKey), g_mapPage);
	}

	bool IsOurMapInputEvent(const void* a_event, bool& a_isPress, bool& a_isRelease, std::uint32_t& a_code, std::string_view& a_user)
	{
		a_isPress = false;
		a_isRelease = false;
		a_code = 0;
		a_user = {};
		if (!g_on || !a_event || !g_menuOpen.load()) {
			return false;
		}
		if (OpenBlockingMapMenu(RE::UI::GetSingleton(), true) != nullptr) {
			return false;   // Never swallow Console / MessageBoxMenu keys while open over PipboyMenu
		}
		const auto* base = static_cast<const RE::InputEvent*>(a_event);
		if (base->eventType != RE::InputEvent::EventType::kButton ||
			base->deviceType != RE::InputEvent::DeviceType::kKeyboard) {
			return false;
		}
		const auto* button = static_cast<const RE::ButtonEvent*>(a_event);
		a_code = static_cast<std::uint32_t>(button->idCode);
		a_user = button->strUserEvent.c_str() ? std::string_view(button->strUserEvent.c_str()) : std::string_view{};
		bool match = (a_code == g_mapKey);
		for (const auto evName : kMapUserEvents) {
			if (SameAscii(a_user, evName)) {
				match = true;
				break;
			}
		}
		if (!match) {
			return false;
		}
		a_isPress = button->value > 0.0f && button->heldDownSecs == 0.0f;
		a_isRelease = button->value == 0.0f;
		return true;
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

	// Main thread: closes Pip-Boy, writes travel globals at verified offset with read-back check, dispatches FO4SF_PipboyTravel.Go
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
				g_lastMapTransitionMs = NowMs();
				queue->AddMessage(OurMenuFixed(), RE::UI_MESSAGE_TYPE::kHide);
			}
		}

		std::uint32_t prefix = 0;
		bool          small = false;
		if (!g_verifiedGlobalValueAt || !ResolvePluginPrefix(g_travelPlugin, prefix, small)) {
			REX::INFO("step=map_fast_travel idx={} plugin={} result=plugin_or_globals_not_ready", a_storeIdx, g_travelPlugin);
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

	// Note: CheckCreateObjectSlot only checks that vtable slot 0x2E lies inside the Starfield.exe module image (InImage);
	// it does NOT prove that slot 0x2E is Scaleform::GFx::ASMovieRootBase::CreateObject (unverified until Slice 3 PC run).
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
		REX::INFO("step=map_root vtable={} slot_0x2e_in_image=1 slot_rva={}", Hex(vt), Hex(slot[kCreateObjectSlot] - g_base));
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
	struct MapGfxCallGuard
	{
		const char*   what = nullptr;
		std::uint64_t seq = 0;
		std::int64_t  startMs = 0;
		bool          uncapped = true;
		bool          ok = false;

		MapGfxCallGuard(const char* a_what, bool a_uncapped = true) :
			what(a_what), startMs(NowMs()), uncapped(a_uncapped)
		{
			if (g_gfxEnterFn) {
				seq = g_gfxEnterFn(a_what, a_uncapped);
			}
		}

		~MapGfxCallGuard()
		{
			if (g_gfxExitFn) {
				g_gfxExitFn(seq, what, ok, startMs, uncapped);
			}
		}
	};

	bool InvokeMapMovie(RE::Scaleform::GFx::Value& a_target, const char* a_method, RE::Scaleform::GFx::Value* a_ret,
		const RE::Scaleform::GFx::Value* a_args, std::size_t a_count, const char* a_label, bool a_uncapped = true)
	{
		MapGfxCallGuard guard(a_label, a_uncapped);
		guard.ok = a_target.Invoke(a_method, a_ret, a_args, a_count);
		return guard.ok;
	}

	void ResetMapMovieState()
	{
		g_menuOpen = false;
		g_closing = false;
		g_mapInputHeld = false;
		g_modalOpen = false;
		g_mapPageVal = RE::Scaleform::GFx::Value{};
		g_populatedMovie = nullptr;
		g_checkedCreateObjMovie = nullptr;
		g_needTexturesLoaded = false;
		g_needCenter = false;
		g_textureLogged = false;
		g_currentShellPage = -1;
		g_currentShellTab = 0;
		g_requestedPage = -1;
		g_requestedTab = -1;
		g_markersDirty = true;
		g_lastPlayerArrayIdx = -1;
		g_inputLogs = 0;
		g_discSyncLogs = 0;
		g_hardcoreLogs = 0;
		g_refreshLogs = 0;
		g_markerLogs = 0;
	}

	void CloseMenuOnFailedMovieCall(const char* a_where)
	{
		REX::ERROR("step=movie_call_failed where={} action=close_menu", a_where);
		ResetMapMovieState();
		if (g_task) {
			g_task->AddTask([]() {
				auto* ui = RE::UI::GetSingleton();
				auto* queue = RE::UIMessageQueue::GetSingleton();
				if (ui && queue && ui->IsMenuOpen(OurMenuFixed())) {
					g_lastMapTransitionMs = NowMs();
					queue->AddMessage(OurMenuFixed(), RE::UI_MESSAGE_TYPE::kHide);
				}
			});
		}
	}

	bool ExtractNonNegIndex(const RE::Scaleform::GFx::Value& a_val, std::int32_t& a_out)
	{
		if (a_val.IsUInt()) {
			a_out = static_cast<std::int32_t>(a_val.GetUInt());
			return a_out >= 0;
		}
		if (a_val.IsInt()) {
			a_out = a_val.GetInt();
			return a_out >= 0;
		}
		if (a_val.IsNumber() && std::isfinite(a_val.GetNumber()) && a_val.GetNumber() >= 0.0 && a_val.GetNumber() <= 64.0) {
			a_out = static_cast<std::int32_t>(a_val.GetNumber());
			return true;
		}
		return false;
	}
}

namespace PipboyMap
{
	bool Requested(const std::filesystem::path& a_ini)
	{
		return ReadIniNumber(a_ini, L"Map", 0) != 0;
	}

	bool Enabled()
	{
		return g_on;
	}

	std::uint32_t MapPageIndex()
	{
		return g_mapPage;
	}

	bool IsModalOpen()
	{
		return g_on && g_modalOpen.load();
	}

	void SetClosing(bool a_closing)
	{
		g_closing.store(a_closing);
	}

	void SetHostCallbacks(OpenRequestFn a_openFn, CloseRequestFn a_closeFn, GfxEnterFn a_gfxEnterFn, GfxExitFn a_gfxExitFn,
		BlockedMenuFactoryFn a_blockedFactoryFn)
	{
		g_openFn = a_openFn;
		g_closeFn = a_closeFn;
		g_gfxEnterFn = a_gfxEnterFn;
		g_gfxExitFn = a_gfxExitFn;
		g_blockedFactoryFn = a_blockedFactoryFn;
	}

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
		g_blockStarMap = ReadIniNumber(a_ini, L"MapBlockStarMap", 0) != 0;
		if (g_mapKey == 0 || g_mapKey > 0xFE || g_mapKey == a_menuKey || g_mapKey == kF10 ||
			g_mapKey == kQuickSaveKey || g_mapKey == kQuickLoadKey || g_mapPage > 4) {
			RefuseStep("ini", std::format("reason=map_key map_key={} key={} map_page={}", Hex(g_mapKey), Hex(a_menuKey), g_mapPage));
			return;
		}

		// Heading offset & sign: MapHeadingAt= overrides [Kit] HeadingAt= (default 88, FAL-595 verified)
		const auto mapHeadingSpec = ReadIniText(a_ini, L"MapHeadingAt");
		const auto kitHeadingSpec = ReadSectionText(a_ini, L"Kit", L"HeadingAt");
		const std::string headingSpec = !mapHeadingSpec.empty() ? mapHeadingSpec :
		                                !kitHeadingSpec.empty() ? kitHeadingSpec :
		                                                          std::string("88");
		if (!ParseHeadingSpec(headingSpec, g_headingAt, g_headingTurnsDown)) {
			RefuseStep("ini", std::format("reason=map_heading_at value={}", headingSpec));
			return;
		}

		g_configuredGlobalValueAt = ReadIniNumber(a_ini, L"MapGlobalValueAt", 0);
		if (g_configuredGlobalValueAt != 0 &&
			(g_configuredGlobalValueAt < kGlobalSearchFrom || g_configuredGlobalValueAt > kGlobalObjectBytes ||
				(g_configuredGlobalValueAt % 4) != 0 || g_configuredGlobalValueAt == kFormIdAt)) {
			RefuseStep("ini", std::format("reason=map_global_value_at value={}", Hex(g_configuredGlobalValueAt)));
			return;
		}
		g_gameHourId = ReadIniNumber(a_ini, L"MapGameHourId", kDefaultGameHourId);
		g_gameDaysPassedId = ReadIniNumber(a_ini, L"MapGameDaysPassedId", kDefaultGameDaysPassedId);
		g_fileCollectionAt = ReadIniNumber(a_ini, L"MapFileCollectionAt", static_cast<std::uint32_t>(kDefaultFileCollectionAt));
		g_fileNameAt = ReadIniNumber(a_ini, L"MapFileNameAt", static_cast<std::uint32_t>(kDefaultFileNameAt));
		g_fileCompileIndexAt = ReadIniNumber(a_ini, L"MapFileCompileIndexAt", static_cast<std::uint32_t>(kDefaultFileCompileIndexAt));
		g_fileIndexAt = ReadIniNumber(a_ini, L"MapFileIndexAt", static_cast<std::uint32_t>(kDefaultFileIndexAt));
		g_extraListAt = ReadIniNumber(a_ini, L"MapExtraListAt", static_cast<std::uint32_t>(kDefaultExtraListAt));
		g_markerFlagsAt = ReadIniNumber(a_ini, L"MapMarkerFlagsAt", static_cast<std::uint32_t>(kDefaultMarkerFlagsAt));
		g_markerDiscMask = ReadIniNumber(a_ini, L"MapMarkerDiscoveredMask", kDefaultMarkerDiscMask);
		if (!g_gameHourId || !g_gameDaysPassedId || !g_markerDiscMask) {
			RefuseStep("ini", "reason=map_offsets_zero");
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
		REX::INFO("step=map_config map_key={} map_page={} menus={} block_starmap={} store={} markers={} travel={}.{} survival={} heading_at={}+{:03X}",
			Hex(g_mapKey), g_mapPage, menusList, g_blockStarMap ? 1 : 0, storeFile, g_store.size(), g_travelScript,
			g_travelFunction, g_mapSurvival ? 1 : 0, g_headingTurnsDown ? "-" : "", g_headingAt);
	}

	void Start(const SFSE::TaskInterface* a_task)
	{
		if (!g_on) {
			return;
		}
		g_task = a_task;
		(void)OurMenuFixed();
		(void)MapMenusFixed();
		InstallStarMapBlock();
		SuppressVanillaMapMenus();
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
		const bool retryNeeded = HasPendingMapBlockSlots();
		bool       isBlockedMenu = false;
		for (const auto& blocked : g_mapMenus) {
			if (SameAscii(raw, blocked)) {
				isBlockedMenu = true;
				break;
			}
		}
		if (retryNeeded || isBlockedMenu) {
			g_task->AddTask([retryNeeded, isBlockedMenu]() {
				if (retryNeeded) {
					InstallStarMapBlock(true);
				}
				if (isBlockedMenu) {
					SuppressVanillaMapMenus();
				}
			});
		}
	}

	void OnMenuMessage(RE::UI_MESSAGE_TYPE a_type)
	{
		if (!g_on) {
			return;
		}
		if (a_type == RE::UI_MESSAGE_TYPE::kShow) {
			g_menuOpen = true;
			g_mapInputHeld = false;
			if (g_requestedPage.load() < 0) {
				g_currentShellPage = 0;
				g_currentShellTab = 0;
			}
			g_lastMapTransitionMs = NowMs();
		} else if (a_type == RE::UI_MESSAGE_TYPE::kHide) {
			ResetMapMovieState();
			g_lastMapTransitionMs = NowMs();
		}
	}

	bool ShouldHandleInput(const void* a_event)
	{
		bool             isPress = false;
		bool             isRelease = false;
		std::uint32_t    code = 0;
		std::string_view user;
		if (!IsOurMapInputEvent(a_event, isPress, isRelease, code, user)) {
			return false;
		}
		return static_cast<const RE::InputEvent*>(a_event)->status != RE::InputEvent::Status::kStop;
	}

	bool OnButtonInput(const void* a_event)
	{
		bool             isPress = false;
		bool             isRelease = false;
		std::uint32_t    code = 0;
		std::string_view user;
		if (!IsOurMapInputEvent(a_event, isPress, isRelease, code, user)) {
			return false;
		}
		const_cast<RE::InputEvent*>(static_cast<const RE::InputEvent*>(a_event))->status = RE::InputEvent::Status::kStop;
		if (++g_inputLogs <= kMaxLogLines && (isPress || isRelease)) {
			REX::INFO("step=map_input id={} user_event=\"{}\" press={} release={} swallowed=1", Hex(code), user,
				isPress ? 1 : 0, isRelease ? 1 : 0);
		}
		if (isPress && !g_mapInputHeld.exchange(true)) {
			g_lastMapTransitionMs = NowMs();
			const auto n = ++g_keyPresses;
			if (g_task) {
				g_task->AddTask([n]() { HandleOpenMenuMapKeyMainThread(n); });
			}
		} else if (isRelease) {
			g_mapInputHeld = false;
		}
		return true;
	}

	void Tick()
	{
		if (!g_on || !g_task) {
			return;
		}
		const bool now = (W32_IMPL_GetAsyncKeyState(static_cast<std::int32_t>(g_mapKey)) & 0x8000) != 0;
		const bool was = g_keyDown.exchange(now);
		// While FO4SF_PipboyMenu is open, OnButtonInput (IMenu vtable) owns MapKey; Tick only opens from closed gameplay
		// outside the transition cooldown so M can never close-then-reopen in a loop
		if (now && !was && !g_menuOpen.load() && GameInFront() &&
			(NowMs() - g_lastMapTransitionMs.load() >= kMapKeyCooldownMs)) {
			g_lastMapTransitionMs = NowMs();
			const auto n = ++g_keyPresses;
			g_task->AddTask([n]() { HandleClosedMapKeyMainThread(n); });
			return;
		}
		const auto t = ++g_tickCount;
		const bool recentTransition = (NowMs() - g_lastMapTransitionMs.load()) < 2500;
		if (recentTransition || (t % 3 == 0)) {
			g_task->AddTask([]() { SuppressVanillaMapMenus(); });
		}
		if (t % 17 == 0 && g_menuOpen.load() && g_currentShellPage.load() == static_cast<std::int32_t>(g_mapPage)) {
			g_task->AddTask([]() { SendMenuUpdateMainThread(); });
		}
	}

	void NotifyShellPageTab(std::int32_t a_page, std::int32_t a_tab)
	{
		if (a_page >= 0) {
			g_currentShellPage = a_page;
		}
		if (a_tab >= 0) {
			g_currentShellTab = a_tab;
		}
		if (g_on && a_page == static_cast<std::int32_t>(g_mapPage)) {
			g_markersDirty = true;
			if (g_task) {
				g_task->AddTask([]() { SendMenuUpdateMainThread(); });
			}
		}
	}

	void CollectStateForPage(std::int32_t a_targetPage)
	{
		if (!g_on || a_targetPage != static_cast<std::int32_t>(g_mapPage)) {
			return;
		}
		CollectMainThreadState();
		g_markersDirty = true;
	}

	void RequestCenterMarker(std::int32_t a_markerIdOrIndex)
	{
		if (!g_on) {
			return;
		}
		g_requestedCenterMarkerId.store(a_markerIdOrIndex);
		g_needCenter = true;
		g_markersDirty = true;
	}

	void ReleaseMovieRefs()
	{
		g_mapPageVal = RE::Scaleform::GFx::Value{};
		g_needTexturesLoaded = false;
		g_requestedCenterMarkerId = -1;
		g_modalOpen = false;
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
				REX::INFO("step=map_check_hardcore idx={} source=FO4SFCoreValues.esm:000841 allow={}", idx, allow ? 1 : 0);
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

	void PopulateMapDataObj(const void* a_menu, RE::Scaleform::GFx::ASMovieRootBase* a_root,
		RE::Scaleform::GFx::Value& a_dataObj, std::int32_t a_targetPage)
	{
		if (!g_on || g_closing.load() || !a_menu || !a_root || !a_dataObj.IsObject()) {
			return;
		}
		// G5 / Step 7: scope MAP markers and map time/texture fields strictly to MapPage (3)
		if (a_targetPage != static_cast<std::int32_t>(g_mapPage)) {
			return;
		}
		const void* const movie = static_cast<const RE::IMenu*>(a_menu)->uiMovie.get();
		if (!CheckCreateObjectSlot(movie, a_root)) {
			return;
		}

		LiveSnapshot snap;
		{
			std::scoped_lock lock(g_snapLock);
			snap = g_snap;
		}

		a_dataObj.SetMember("ReadOnlyMode", RE::Scaleform::GFx::Value(std::int32_t{ 0 }));
		a_dataObj.SetMember("TimeHour", RE::Scaleform::GFx::Value(static_cast<double>(snap.gameHour)));
		a_dataObj.SetMember("DateMonth", RE::Scaleform::GFx::Value(snap.dateMonth));
		a_dataObj.SetMember("DateDay", RE::Scaleform::GFx::Value(snap.dateDay));
		a_dataObj.SetMember("DateYear", RE::Scaleform::GFx::Value(snap.dateYear));
		a_dataObj.SetMember("CurrLocationName", RE::Scaleform::GFx::Value(snap.locationName.c_str()));
		a_dataObj.SetMember("WorldMapTextureName", RE::Scaleform::GFx::Value(kDefaultWorldTexture));

		const std::size_t cornersOk =
			(MutatePoint(a_dataObj, "WorldMapNWCorner", kCommonwealthNWX, kCommonwealthNWY) ? 1u : 0u) +
			(MutatePoint(a_dataObj, "WorldMapNECorner", kCommonwealthNEX, kCommonwealthNEY) ? 1u : 0u) +
			(MutatePoint(a_dataObj, "WorldMapSWCorner", kCommonwealthSWX, kCommonwealthSWY) ? 1u : 0u);
		MutatePoint(a_dataObj, "LocalMapNWCorner", -2048.0, 2048.0);
		MutatePoint(a_dataObj, "LocalMapNECorner", 2048.0, 2048.0);
		MutatePoint(a_dataObj, "LocalMapSWCorner", -2048.0, -2048.0);

		RE::Scaleform::GFx::Value markersArr;
		if (a_dataObj.GetMember("WorldMapMarkers", &markersArr) && markersArr.IsObject()) {
			a_dataObj.SetMember("RemoveAllMapMarkers", RE::Scaleform::GFx::Value(true));
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
			g_markersDirty = false;
			if (++g_markerLogs <= kMaxLogLines) {
				REX::INFO("step=map_markers n={} discovered={} undiscovered={} player_idx={} corners_set={}/3 read_back={}",
					arrIdx, discCount, undiscCount, g_lastPlayerArrayIdx, cornersOk,
					cornersOk == 3 ? "match" : "partial");
			}
		}
	}

	void OnShellUpdate(const void* a_menu, RE::Scaleform::GFx::ASMovieRootBase* a_root, RE::Scaleform::GFx::Value& a_top,
		const std::string& a_codeObjAt, std::atomic<std::int32_t>& a_answerPage, std::atomic<std::int32_t>& a_answerTab)
	{
		if (!g_on || g_closing.load() || !a_menu || !a_root || a_codeObjAt.empty()) {
			return;
		}
		const void* const movie = static_cast<const RE::IMenu*>(a_menu)->uiMovie.get();
		if (!CheckCreateObjectSlot(movie, a_root)) {
			CloseMenuOnFailedMovieCall("map_create_object_slot");
			return;
		}

		RE::Scaleform::GFx::Value menuMc;
		RE::Scaleform::GFx::Value dataObj;
		if (!ReadDotPath(a_top, a_codeObjAt, menuMc) || !menuMc.IsObject() ||
			!menuMc.GetMember("DataObj", &dataObj) || !dataObj.IsObject()) {
			return;
		}

		// External page/tab switch while open (e.g. pressing M while on STAT, or World/Local toggle):
		// wait until Menu_mc._IsLoadingPage == false and CurrentPage MovieClip is loaded, then route via TryToSetPage/TryToSetTab
		const auto pendingPage = g_requestedPage.load();
		const auto pendingTab = g_requestedTab.load();
		if (pendingPage >= 0 || pendingTab >= 0) {
			RE::Scaleform::GFx::Value loadingVal;
			RE::Scaleform::GFx::Value curPageClip;
			const bool loadingFlag = menuMc.GetMember("_IsLoadingPage", &loadingVal) && loadingVal.IsBoolean() && loadingVal.GetBoolean();
			const bool pageClipReady = menuMc.GetMember("CurrentPage", &curPageClip) && curPageClip.IsObject();
			if (loadingFlag || !pageClipReady) {
				// Page SWF is still loading; keep g_requestedPage / g_requestedTab queued for the next kUpdate
				if (g_task) {
					g_task->AddTask([]() { SendMenuUpdateMainThread(); });
				}
				return;
			}
			const auto reqPage = g_requestedPage.exchange(-1);
			const auto reqTab = g_requestedTab.exchange(-1);
			if (reqPage >= 0) {
				RE::Scaleform::GFx::Value pageArg(static_cast<std::uint32_t>(reqPage));
				RE::Scaleform::GFx::Value tryRes;
				if (!InvokeMapMovie(menuMc, "TryToSetPage", &tryRes, &pageArg, 1, "Menu_mc.TryToSetPage")) {
					a_answerPage.store(reqPage);
				}
			}
			if (reqTab >= 0) {
				RE::Scaleform::GFx::Value tabArg(static_cast<std::uint32_t>(reqTab));
				RE::Scaleform::GFx::Value tryRes;
				if (!InvokeMapMovie(menuMc, "TryToSetTab", &tryRes, &tabArg, 1, "Menu_mc.TryToSetTab")) {
					a_answerTab.store(reqTab);
				}
			}
		}

		RE::Scaleform::GFx::Value curPageVal, curTabVal;
		std::int32_t              parsedIdx = -1;
		if (a_answerPage.load() >= 0) {
			g_currentShellPage = a_answerPage.load();
		} else if (dataObj.GetMember("CurrentPage", &curPageVal) && ExtractNonNegIndex(curPageVal, parsedIdx)) {
			g_currentShellPage = parsedIdx;
		}
		if (a_answerTab.load() >= 0) {
			g_currentShellTab = a_answerTab.load();
		} else if (dataObj.GetMember("CurrentTab", &curTabVal) && ExtractNonNegIndex(curTabVal, parsedIdx)) {
			g_currentShellTab = parsedIdx;
		}

		// G5 / Step 7: scope MAP markers and map updates strictly to MapPage (3)
		if (g_currentShellPage.load() != static_cast<std::int32_t>(g_mapPage)) {
			return;
		}

		const bool newMovie = g_populatedMovie != movie;
		bool       rebuiltMarkers = false;
		if (newMovie || g_markersDirty.exchange(false)) {
			PopulateMapDataObj(a_menu, a_root, dataObj, static_cast<std::int32_t>(g_mapPage));
			rebuiltMarkers = (g_populatedMovie == movie);
		}

		// G1 fix: never invoke InvalidatePartialData(0x80) unless Pipboy_MapPage is registered and active on MapPage
		if (rebuiltMarkers && g_mapPageVal.IsObject() && a_answerPage.load() < 0 && a_answerTab.load() < 0 &&
			g_currentShellPage.load() == static_cast<std::int32_t>(g_mapPage)) {
			RE::Scaleform::GFx::Value maskArg(std::uint32_t{ 0x80u });
			RE::Scaleform::GFx::Value invRes;
			if (!InvokeMapMovie(menuMc, "InvalidatePartialData", &invRes, &maskArg, 1, "Menu_mc.InvalidatePartialData") &&
				!InvokeMapMovie(menuMc, "InvalidateData", &invRes, nullptr, 0, "Menu_mc.InvalidateData")) {
				REX::INFO("step=movie_call_miss where=map_invalidate_markers");
				return;
			}
			dataObj.SetMember("RemoveAllMapMarkers", RE::Scaleform::GFx::Value(false));
		}

		if (g_mapPageVal.IsObject()) {
			if (g_needTexturesLoaded.exchange(false)) {
				// Deliver WorldMapTextureName + corners to newly registered Pipboy_MapPage before onMapTexturesLoaded()
				RE::Scaleform::GFx::Value invRes;
				if (!InvokeMapMovie(menuMc, "InvalidateData", &invRes, nullptr, 0, "Menu_mc.InvalidateData")) {
					REX::INFO("step=movie_call_miss where=map_register_invalidate");
				}
				dataObj.SetMember("RemoveAllMapMarkers", RE::Scaleform::GFx::Value(false));
				RE::Scaleform::GFx::Value res;
				const bool called = InvokeMapMovie(g_mapPageVal, "onMapTexturesLoaded", &res, nullptr, 0, "MapPage.onMapTexturesLoaded");
				REX::INFO("step=map_textures_loaded called={}", called ? 1 : 0);
				if (!called) {
					REX::INFO("step=movie_call_miss where=onMapTexturesLoaded");
					return;
				}
			}
			if (!g_textureLogged.load()) {
				RE::Scaleform::GFx::Value holder, bLoaded, texHolder, children;
				if (ReadDotPath(g_mapPageVal, "WorldMapHolder_mc", holder) &&
					holder.GetMember("mapLoaded", &bLoaded) && bLoaded.IsBoolean() && bLoaded.GetBoolean()) {
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
				std::int32_t centerIdx = g_lastPlayerArrayIdx;
				const auto   wantId = g_requestedCenterMarkerId.exchange(-1);
				if (wantId >= 0) {
					for (std::size_t mi = 0; mi < g_store.size(); ++mi) {
						if (static_cast<std::int32_t>(g_store[mi].localId) == (wantId & 0xFFFFFF) ||
							static_cast<std::int32_t>(g_store[mi].index) == wantId) {
							centerIdx = static_cast<std::int32_t>(mi);
							break;
						}
					}
				}
				RE::Scaleform::GFx::Value idxArg(static_cast<std::uint32_t>(centerIdx));
				RE::Scaleform::GFx::Value res;
				const bool called = InvokeMapMovie(g_mapPageVal, "SetCenterMarker", &res, &idxArg, 1, "MapPage.SetCenterMarker");
				REX::INFO("step=map_center idx={} called={}", centerIdx, called ? 1 : 0);
				if (!called) {
					REX::INFO("step=movie_call_miss where=SetCenterMarker");
					return;
				}
			}
		}
	}

	void OnMenuDestroy()
	{
		ResetMapMovieState();
	}
}
