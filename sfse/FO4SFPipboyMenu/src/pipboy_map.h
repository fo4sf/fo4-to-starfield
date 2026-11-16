#pragma once

// FO4SFPipboyMenu Pip-Boy MAP controller (Slices 1-4; docs/ui/pipboy-map-s1-s4.md).
// Shipped off (Map=0 in FO4SFPipboyMenu.ini): every entry point returns immediately with no log lines and no game
// calls when Map=0. At Map=1 (Stage=2, Movie= and CodeObj=1):
//   Slice 1: Blocks Starfield's star map completely (replaces MapMenus initFunc in UI::menuMap with BlockedStarMapCreate
//            when MapBlockStarMap=1, swallows MapKey + map user events via IMenu's BSInputEventUser vtable while open
//            so M never loops close-then-reopen, and sends kHide on any fallback suppression without reopening ours),
//            and opens FO4SF_PipboyMenu directly on MapPage (3 = MAP, tab 0 = WORLD).
//   Slice 2: Answers RegisterMap with onMapTexturesLoaded() and reads back WorldMapHolder_mc texture state for the
//            staged FO4SF_WorldMap.swf wrapper.
//   Slice 3: Mutates DataObj's getter-only WorldMapNW/NE/SWCorner Points and WorldMapMarkers Array in place (checking
//            ASMovieRootBase::CreateObject slot 0x2E inside Starfield.exe's image first), reading static markers from
//            MapStore (FO4SFPipboyMapMarkers.tsv), live engine ExtraMapMarker kDiscovered (0x20) state synced into
//            FO4SF_MapDisc00..13 TESGlobals (verified via ChooseGlobalSlot), and live player coordinates + configurable
//            compass heading (MapHeadingAt / [Kit] HeadingAt) for PlayerLocMarker (type 86) and PlayerSetMarker (85).
//   Slice 4: Answers CheckHardcoreModeFastTravel (returning Boolean) and RefreshMapMarkers directly on BGSCodeObj,
//            handles PipboyMessageBox modal state, and routes FastTravel(idx) (and cross-world travel) on the main
//            thread by writing the target into FO4SFPipboyTravel.esm's globals and dispatching FO4SF_PipboyTravel.Go.
namespace PipboyMap
{
	bool Requested(const std::filesystem::path& a_ini);

	bool Enabled();

	void Configure(const std::filesystem::path& a_ini, const std::filesystem::path& a_dir, int a_stage,
		std::uint32_t a_menuKey, std::uintptr_t a_base, std::size_t a_imageSize);

	void Start(const SFSE::TaskInterface* a_task);

	void OnMovieCreated(const RE::IMenu* a_menu);

	void OnMenuMessage(RE::UI_MESSAGE_TYPE a_type);

	bool ShouldHandleInput(const void* a_event);

	bool OnButtonInput(const void* a_event);

	void Tick();

	void OnCodeObjCall(const std::string& a_name, const RE::Scaleform::GFx::FunctionHandler::Params& a_params);

	void OnShellUpdate(const void* a_menu, RE::Scaleform::GFx::ASMovieRootBase* a_root, RE::Scaleform::GFx::Value& a_top,
		const std::string& a_codeObjAt, std::atomic<std::int32_t>& a_answerPage, std::atomic<std::int32_t>& a_answerTab);

	void OnMenuDestroy();
}
