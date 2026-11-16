#pragma once

// FO4SFPipboyMenu Pip-Boy MAP controller (Slices 1-4; docs/ui/pipboy-map-s1-s4.md).
// Shipped off (Map=0 in FO4SFPipboyMenu.ini): every entry point returns immediately with no log lines and no game
// calls when Map=0. At Map=1 (Stage=2, Movie= and CodeObj=1):
//   Slice 1: MapKey opens FO4SF_PipboyMenu directly on MapPage (3 = MAP, tab 0 = WORLD) and hides any open vanilla
//            menu listed in MapMenus (e.g. GalaxyStarMapMenu) via UI::IsMenuOpen + UIMessageQueue::AddMessage(kHide).
//   Slice 2: Answers RegisterMap with onMapTexturesLoaded() and reads back WorldMapHolder_mc texture state for the
//            staged FO4SF_WorldMap.swf wrapper.
//   Slice 3: Mutates DataObj's getter-only WorldMapNW/NE/SWCorner Points and WorldMapMarkers Array in place (checking
//            ASMovieRootBase::CreateObject slot 0x2E inside Starfield.exe's image first), reading static markers from
//            MapStore (FO4SFPipboyMapMarkers.tsv), 24-bit discovery bitsets from FO4SF_MapDisc00..13 TESGlobals, and
//            live player coordinates + compass heading for PlayerLocMarker (type 86) and PlayerSetMarker (type 85).
//   Slice 4: Answers CheckHardcoreModeFastTravel (returning Boolean) and RefreshMapMarkers directly on BGSCodeObj,
//            handles PipboyMessageBox modal state, and routes FastTravel(idx) on the main thread by writing the target
//            into FO4SFPipboyTravel.esm's globals at +0x48 and dispatching FO4SF_PipboyTravel.Go (0 args, slot 0x2F).
namespace PipboyMap
{
	void Configure(const std::filesystem::path& a_ini, const std::filesystem::path& a_dir, int a_stage,
		std::uint32_t a_menuKey, std::uintptr_t a_base, std::size_t a_imageSize);

	void Start(const SFSE::TaskInterface* a_task);

	void OnMovieCreated(const RE::IMenu* a_menu);

	void Tick();

	void OnCodeObjCall(const std::string& a_name, const RE::Scaleform::GFx::FunctionHandler::Params& a_params);

	void OnShellUpdate(const void* a_menu, RE::Scaleform::GFx::ASMovieRootBase* a_root, RE::Scaleform::GFx::Value& a_top,
		const std::string& a_codeObjAt, std::atomic<std::int32_t>& a_answerPage, std::atomic<std::int32_t>& a_answerTab);

	void OnMenuDestroy();
}
