// FO4SFPipboyMenu: Pip-Boy step 1 (FAL-187; README.md in this folder). Can a plugin of ours register a menu of its
// own and show a movie of its own on Starfield 1.16.244? One named menu, FO4SF_PipboyMenu, opened and closed on one
// key, every step in its own log. Stage=1 (a): the menu with no movie; Stage=2 (b): the same menu showing
// Interface/FO4SF_PipboyMenu.swf (scripts/ui/make_probe_swf.py), loaded from "FO4SFPipboyProbe - Main.ba2".
//
// Built on libxse/commonlibsf 9d090c4 for SFSE, the Address Library, the logger, UI::RegisterMenu, UI::IsMenuOpen,
// UIMessageQueue::AddMessage and BSFixedString, but NOT on its IMenu class: every IMenu virtual there is
// REL::ID{ 0 } (include/RE/IDs.h), and a lookup of id 0 stops the game with a message box. The menu object is the
// engine's own: the engine's IMenu constructor, then a copy of the engine's IMenu primary vtable with only our
// slots replaced, and the engine's RTTI locator in the slot before the copy (the two other vtables are the engine's,
// as the constructor set them).
//
// Nothing is called before it is checked (README, "Where every id comes from"):
//   - the runtime is 1.16.244.0 (SFSE's), else nothing but the refusal line;
//   - the Address Library file next to this dll is read here first (format 5, game version 1.16.244.0, every id we
//     use below its count, non-zero and inside Starfield.exe's image), so libxse's own lookup can never hit a
//     missing id; then each id is looked up again through libxse and must give the same offset;
//   - the three IMenu vtables carry IMenu's RTTI (complete object locator: x64, subobject offsets 0, 0x10, 0x50, type
//     ".?AVIMenu@@", the type descriptor libxse's RTTI id names);
//   - the primary vtable's slots are the functions their ids name: 0x00 the scalar deleting destructor, 0x06
//     LoadMovie (also SFSE 0.2.21's own hook address, 0x2551AB0), 0x08 ProcessMessage, 0x0A IsMovieLoaded; 0x03 and
//     0x04 (GetName, GetRootPath) are the same pure-virtual stub;
//   - the constructor's first 0x200 bytes load the primary vtable's address (lea r64, [rip+disp32]).
// Any mismatch is one "refuse step=<step>" line and the plugin stays idle: no registration, no call into the game.
//
// Slots replaced in the copy: 0x00 (our destructor wrapper: the engine's destructor without its delete, then our
// free, since the object is ours), 0x03 GetName, 0x04 GetRootPath (""), 0x05 GetViewScaleMode (ShowAll), 0x06 LoadMovie
// (stage a: true without a movie; stage b: the engine's, logged, with addEventDispatcher forced off: our movie has no
// engine event backend), 0x08 ProcessMessage (logged; stage a answers kShow itself, as the engine's refuses a menu
// without a movie), and in stage a 0x0A IsMovieLoaded (true). The key is polled on a worker thread; every UI call runs
// on the main thread through SFSE's task interface.
//
// Stage=3 (c), FAL-216: stage (b) plus the data channel, with the movie make_probe_swf.py --channel writes. Inside our
// ProcessMessage, on the engine's own thread for this menu: at kShow the plugin finds the movie's two named children
// (getChildByName) and adds a click listener on the button whose handler is ours; at kShow and at every kUpdate (sent
// every 500 ms while the menu is open) it writes the player's position into the text field and reads it back. Pause
// state and the input holders (the UI menu stack and ControlMap's active input contexts) are logged at show, while
// open, at hide, on the main thread after each toggle, and on a second key. FlagSets cycles the menu flags per open.
// Checked first, at stage c only: 13 more ids (singletons of Main, the player and ControlMap; five RTTI type
// descriptors, by name; five Scaleform Value functions, each equal to SFSE 0.2.21's own address for 1.16.244), then,
// before first use, the type of every object: Main, the player, ControlMap, the movie (GFx::MovieImpl) and its root
// (GFx::AS3::MovieRoot), whose two slots we call (0x30 CreateFunction, 0x32 GetVariable; libxse and SFSE agree on
// both) must be inside the image. Reads of engine objects whose layout only libxse states (input contexts, the pause
// byte, the position) are guarded: a fault logs "fault" instead of stopping the game. A snapshot's menus= lists the
// open menus among a few known names, through the engine's IsMenuRegistered and IsMenuOpen, on the main thread only
// (libxse's menu stack at UI+0x3F0 read empty in every FAL-216 snapshot, the pause menu's too); off it, "-".
//
// Stage c with ClickCall set (FAL-246, native to script): each click also reaches a quest. On the main thread (SFSE's
// task interface) the plugin asks the script VM to run one global Papyrus function with no arguments
// (ClickCall=FOCC_B0.Click: the combined probe's B0 script, which resolves its probe quest and logs "b0 click" there)
// through IVirtualMachine::DispatchStaticCall, libxse's slot 0x2F. Checked first, at stage c: 3 more ids (FOCCPing's
// GameVM singleton and two RTTI ids, the RTTI ids by name); before the first call, the GameVM singleton is a GameVM by
// RTTI, the VM it holds (libxse GameVM::impl, +0xE0) a BSScript::Internal::VirtualMachine by RTTI at offset 0, and its
// vtable's slots 0x00 to 0x2F are inside the image. No arguments: a BSScrapArray that grows calls
// ScrapHeap::Allocate, which libxse 9d090c4 states as REL::ID{ 0 }, so the argument function never touches the array.
// No callback: a null functor, as the public precedents pass.
//
// Stage=4 (d), FAL-272: the STAT page, the first page the owner uses by hand. Stage (c)'s checks, with the movie
// make_probe_swf.py --page writes: a tab line and seven lines the plugin writes at kShow and every kUpdate, and two
// buttons, NEXT TAB (the other set of lines) and CLOSE (the menu closes, as on F10). The values are collected on the
// main thread (SFSE's task, before each kShow and kUpdate) and only written on the menu's thread. Every value is read,
// not called for, except two calls: the player's own GetActorValue, and the engine's lookup of a form by its form id
// (TESForm::LookupByID, equal to SFSE 0.2.21's GetFormByNumericID). The health, carry weight and experience are the
// actor values Starfield.esm's ActorValueInfo forms 0x2D4, 0x2DC and 0x2C9 name, and the game time its GameHour (0x38)
// and GameDaysPassed (0x39) globals: each accepted by its form id and RTTI type (at 3eb30d71 four of them did not pass
// an editor-ID check). FO4SF_Rads is found by editor ID at local id 0x800 of any plugin; the level is the player's base
// TESNPC's TESActorBaseData; the place is the parent cell's and its worldspace's names. (The data handler's per-type
// form lists, read at 5a4e6016, were empty: their raw entries are logged once, step=page_form_arrays, to settle the
// layout.)
// Checked before use: each form's type by its RTTI name; each base class's offset (ActorValueOwner, TESActorBaseData,
// TESFullName) from the RTTI class hierarchy, and that subobject's vtable naming the same complete type there; the
// string reader on our own menu name first; and which ActorValueOwner slot is GetActorValue (libxse declares a virtual
// destructor before it, SFSE 0.2.21 does not): slot 0 must be the adjustor thunk to the player's destructor. A value
// that fails its check prints "?" and its reason is logged once. PageFlagSets (default 0x9, the flag set at which the
// FAL-216 clicks reached our menu) cycles per open like FlagSets.
//
// Stage=5 (e), FAL-301: the page kit. One movie for every page (make_pipboy_kit.py, staged with --kit: a title bar,
// main tabs with a bracket, sub-tabs, a list of 16 rows with a selection bar and scrolling, 16 two-column value rows, a
// footer and key hints) and the pages as data: the [Kit] and [Page <TAB>/<SUB>] sections of this plugin's ini, read
// once at load with the grammar and checks of make_pipboy_kit.py's parse_kit (a wrong line: refuse step=pages, the kit
// stays off). A page is rows (Row=<label>|<value>), a list from a list provider or a notice. The values come from
// named value providers, stage d's reads (health, level, xp, carry_max, rads, cell, world, time, days, position) and
// av:<form id>, any actor value accepted by its RTTI type. The screen is built on the main thread and written on the
// menu's through `text` and `visible` only, each change read back. Keys (polled while the page is open and the game in
// front) and clicks (one listener on the movie's root, which reads the click's target name) move the selection, the
// sub-tab and the main tab; CLOSE keeps stage d's handler. Stage (d)'s checks and ids; nothing new is called.
//
// Stage=2 with Movie= and Arm=1, FAL-852 (S1-arm; README "The arm"; off by default): Key, which may not be F10 (the
// owner's faction device), plays the raise first and opens Fallout 4's screen ArmRaiseMs later, and every close of it is
// followed by the lower. The raise and the lower are idles named by editor id, found with the engine's own lookup
// (TESForm::LookupByEditorID, libxse id 47403, checked in the Address Library file like the others), and their
// animation events are sent to the player (IAnimationGraphManagerHolder at +0x60, slot 0x01 NotifyAnimationGraphImpl,
// checked by RTTI): #776's route (FAL-714, FAL-725), taken over for this screen. Pause=1 adds the pause bit to Flags.

#include "pch.h"

#include <algorithm>
#include <atomic>
#include <cctype>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <limits>
#include <memory>
#include <mutex>
#include <numbers>
#include <optional>
#include <set>
#include <string>
#include <unordered_map>
#include <vector>

#include "setup_places.h"
#include "lift_menu.h"
#include "pipboy_screen_source.h"
#include "hud_quest_label.h"

// Win32 calls that libxse's REX::W32 does not wrap, imported the way REX/W32.cpp imports its own (REX/W32/BASE.h):
// libxse refuses a <windows.h> included before it
REX_W32_IMPORT(std::int16_t, GetAsyncKeyState, std::int32_t);
REX_W32_IMPORT(void*, GetForegroundWindow);
REX_W32_IMPORT(std::uint32_t, GetWindowThreadProcessId, void*, std::uint32_t*);
REX_W32_IMPORT(std::uint32_t, GetCurrentProcessId);
// FAL-614 proof 1d (CodeObjSound=1): Windows audio's waveOut calls (winmm, xmake.lua add_syslinks)
REX_W32_IMPORT(std::uint32_t, waveOutOpen, void**, std::uint32_t, const void*, std::uintptr_t, std::uintptr_t, std::uint32_t);
REX_W32_IMPORT(std::uint32_t, waveOutPrepareHeader, void*, void*, std::uint32_t);
REX_W32_IMPORT(std::uint32_t, waveOutWrite, void*, void*, std::uint32_t);
REX_W32_IMPORT(std::uint32_t, waveOutReset, void*);
REX_W32_IMPORT(std::uint32_t, waveOutUnprepareHeader, void*, void*, std::uint32_t);
REX_W32_IMPORT(std::uint32_t, waveOutClose, void*);

#include "blocking_menus.h"
#include "pipboy_map.h"
#include "world.h"   // FAL-250: the world-surface census and candidate (World=1; README.md, "World surface")

namespace
{
	using namespace std::string_view_literals;

	constexpr auto          kMenuName = "FO4SF_PipboyMenu";
	constexpr REL::Version  kRuntime{ 1, 16, 244, 0 };
	constexpr std::uint32_t kLoadMovieRva = 0x2551AB0;       // SFSE 0.2.21 sfse/Hooks_Scaleform.cpp: IMenu_LoadMovie
	constexpr std::uint32_t kPrecedentCtorRva = 0x25516B0;   // a public precedent's base IMenu constructor (logged only)
	constexpr std::size_t   kMenuBytes = 0x400;              // IMenu is 0x138; the engine's own menus are larger
	constexpr std::size_t   kSlots = 0x20;                   // primary vtable entries copied (IMenu declares 0x00-0x1A)
	constexpr std::size_t   kCtorScan = 0x200;
	constexpr std::size_t   kHeaderBytes = 96;               // Address Library format 5 header (libxse REL/IDDB.cpp)
	constexpr char          kTypeName[] = ".?AVIMenu@@";
	constexpr auto          kFieldName = "fo4sfPosition";    // make_probe_swf.py FIELD_NAME
	constexpr auto          kButtonName = "fo4sfButton";     // make_probe_swf.py BUTTON_NAME
	constexpr std::size_t   kMovieRootAt = 0x18;             // GFx::Movie: RefCountBase 0x00, StateBag 0x10, root 0x18
	constexpr std::size_t   kCreateObjectSlot = 0x2E;        // GFx::ASMovieRootBase::CreateObject (checked InImage in RootOf)
	constexpr std::size_t   kCreateFunctionSlot = 0x30;      // GFx::ASMovieRootBase (libxse and SFSE 0.2.21 agree)
	constexpr std::size_t   kGetVariableSlot = 0x32;
	constexpr std::size_t   kMainPausedAt = 0x448;           // libxse RE::Main::isGameMenuPaused
	constexpr std::size_t   kContextsAt = 0x2A8;             // libxse RE::ControlMap::activeInputContexts (16-byte items)
	constexpr std::size_t   kPositionAt = 0x80 + 0x0C;       // libxse RE::TESObjectREFR::data (0x80), OBJ_REFR::location
	constexpr std::size_t   kMaxListed = 16;                 // contexts listed per snapshot
	constexpr std::size_t   kMaxFlagSets = 16;   // FAL-414: a flag sweep (one set per open) needs more than four
	constexpr std::size_t   kGameVmImplAt = 0xE0;            // libxse RE::GameVM::impl (BSTSmartPointer<IVirtualMachine>)
	constexpr std::size_t   kDispatchStaticCallSlot = 0x2F;  // libxse IVirtualMachine::DispatchStaticCall
	constexpr std::size_t   kMaxName = 64;                   // ClickCall: each of the script's and function's names
	constexpr std::uint32_t kMaxCodeCalls = 256;             // FAL-614 proof 1b: stand-in BGSCodeObj calls logged (S1-c: 256, paging)
	constexpr std::size_t   kMaxCodeArg = 64;                // and the first characters of a string argument
	constexpr std::uint32_t kMaxCodeArgs = 4;                // FAL-614 S1-c: the arguments logged per call
	constexpr std::size_t   kMaxCodeNames = 64;              // CodeObjNames: up to 64 (holds all 46 FO4 BGSCodeObj functions + HideMenu)
	constexpr std::size_t   kMaxShellKeys = 8;               // FAL-614 S1-c: ShellKeys=, keys that call a shell path
	constexpr std::uint32_t kMaxAnswers = 512;               // FAL-614 S1-c: page and tab answers per movie
	constexpr std::int64_t  kMaxAnswerIndex = 63;            // the highest page or tab index answered
	constexpr std::uint32_t kMaxSpecialLines = 16;           // FAL-1025: step=code_obj_special lines logged
	constexpr std::uint32_t kMaxGfxFreqLines = 128;          // step=gfx_enter/gfx_exit cap for frequent read/probe movie calls
	constexpr std::int64_t  kWatchdogBusyMs = 2000;          // step=watchdog_busy threshold for stuck movie calls
	constexpr std::array<const char*, 7> kSpecialNames{ "STRENGTH", "PERCEPTION", "ENDURANCE", "CHARISMA", "INTELLIGENCE",
		"AGILITY", "LUCK" };                                     // FAL-1025: CodeObjSpecial=fill's entries, in DataObj's order
	constexpr std::array<const char*, 7> kSpecialEditorIds{
		"FO4SF_Special_Strength",
		"FO4SF_Special_Perception",
		"FO4SF_Special_Endurance",
		"FO4SF_Special_Charisma",
		"FO4SF_Special_Intelligence",
		"FO4SF_Special_Agility",
		"FO4SF_Special_Luck",
	};
	constexpr std::uint32_t kMaxCodeObjTries = 40;           // tries per movie (load, show, then one per kUpdate)
	constexpr std::uint32_t kLoggedCodeObjTries = 5;
	constexpr std::size_t   kMaxSoundBytes = 32u << 20;      // FAL-614 proof 1d: one converted sound file, at most
	constexpr std::uint32_t kMaxSoundsPlaying = 4;           // sounds at once (the boot sequence overlaps two)
	constexpr std::uint32_t kMaxSoundLines = 64;             // step=sound lines logged
	constexpr auto          kSoundFolder = "FO4SFPipboyMenuSounds";   // beside the dll: the player's converted files         // the first tries logged; the one that sets it always

	// FAL-852, the arm (Arm=1 at Stage=2 with Movie= only; README, "The arm"). #776's ids and offsets (FAL-714, FAL-719),
	// read there on the PC at 1.16.244. The idles are named by editor id, never by form id: step 3a's playidle by form id
	// showed nothing
	constexpr std::uint32_t kLookupByEditorId = 47403;       // libxse 9d090c4 ID::TESForm::LookupByEditorID (not in kIds)
	constexpr std::uint32_t kActorPlayIdleId = 102136;       // Papyrus Actor.PlayIdle internal helper (RVA 0x19BFFD0)
	constexpr std::uint32_t kPlayIdleContextId = 35720;      // PlayIdle thread context getter (RVA 0x2B7DD0)
	constexpr std::uint32_t kRegisterSinkId = 123821;        // libxse ID::BSTEventSource::RegisterSink
	constexpr std::uint32_t kUnregisterSinkId = 123822;      // libxse ID::BSTEventSource::UnregisterSink
	constexpr std::uint32_t kIdleExamineWatchFormId = 0x000C154F; // Starfield.esm IDLE IdleExamineWatch
	constexpr std::size_t   kActorCurrentProcessAt = 0x228;  // Actor::currentProcess (verified in Papyrus Actor.PlayIdle)
	constexpr std::uint32_t kEquipManagerSingletonId = 938503; // ID::ActorEquipManager::Singleton
	constexpr std::uint32_t kEquipManagerRttiId = 860014;    // RTTI::ActorEquipManager
	constexpr std::uint32_t kEquipObjectId = 101949;         // ID::ActorEquipManager::EquipObject
	constexpr std::uint32_t kUnequipObjectId = 101951;       // ID::ActorEquipManager::UnequipObject
	constexpr std::uint32_t kObjectInstanceCtorId = 59786;   // ID::BGSObjectInstance::ctor
	constexpr std::uint32_t kAlchemyItemRttiId = 845251;     // RTTI::AlchemyItem
	constexpr std::uint32_t kOxygenAvifId = 0x2E2;           // Starfield.esm AVIF Oxygen (AP dial)
	constexpr std::uint32_t kDamageResistAvifId = 0x2E3;     // Starfield.esm AVIF DamageResist
	constexpr std::uint32_t kEnergyResistAvifId = 0x2EB;     // Starfield.esm AVIF EnergyResist
	constexpr std::uint32_t kCreditsFormId = 0x0000000F;     // Starfield.esm MISC Credits (Caps)
	constexpr std::uint32_t kCoreSpecialFirstLocalId = 0x810; // FO4SFCoreValues.esm AVIF FO4SF_Special_Strength..Luck (0x810..0x816)
	constexpr std::uint32_t kCoreRadResistLocalId = 0x804;   // FO4SFCoreValues.esm AVIF FO4SF_RadResist
	constexpr std::uint32_t kCoreHardcoreFastTravelBlockedId = 0x841; // FO4SFCoreValues.esm GLOB FO4SF_HardcoreFastTravelBlocked (A2)
	constexpr std::uint32_t kCoreStimpakLocalId = 0x851;     // FO4SFCoreValues.esm ALCH FO4SF_Stimpak
	constexpr std::uint32_t kCorePipboyAcquiredId = 0x865;   // FO4SFCoreValues.esm GLOB FO4SF_PipboyAcquired (X2)
	constexpr std::uint32_t kNewGamePipboyWristId = 0x80D;   // FO4SFNewGame.esm ARMO FO4SF_PipboyWrist (owned + worn gate)
	constexpr std::uint32_t kCoreStartCardOpenId = 0x866;    // FO4SFCoreValues.esm GLOB FO4SF_StartCardOpen (N2, R13)
	constexpr std::uint32_t kCoreGameModeId = 0x870;         // FO4SFCoreValues.esm GLOB FO4SF_GameMode (S1, R13)
	constexpr std::uint32_t kCoreSurvivalStartId = 0x871;    // FO4SFCoreValues.esm GLOB FO4SF_SurvivalStart (S1, R13)
	constexpr std::uint32_t kCoreSurvivalLockedId = 0x872;   // FO4SFCoreValues.esm GLOB FO4SF_SurvivalLocked (S1, R13)
	constexpr std::uint32_t kCoreStartDifficultyId = 0x873;  // FO4SFCoreValues.esm GLOB FO4SF_StartDifficulty (S1, R13)
	constexpr std::uint32_t kCoreWarfareFactionId = 0x874;   // FO4SFCoreValues.esm GLOB FO4SF_WarfareFaction (S1, R13)
	constexpr std::uint32_t kCoreWarfareStartIndexId = 0x875;// FO4SFCoreValues.esm GLOB FO4SF_WarfareStartIndex (S1, R13)
	constexpr std::uint32_t kCoreStartChoiceDoneId = 0x876;  // FO4SFCoreValues.esm GLOB FO4SF_StartChoiceDone (S1, R13)
	constexpr std::uint32_t kCoreStoryLineId = 0x878;        // FO4SFCoreValues.esm GLOB FO4SF_StoryLine (S1, R13)
	constexpr std::uint32_t kCoreStartPlaceRowId = 0x879;    // FO4SFCoreValues.esm GLOB FO4SF_StartPlaceRow (S1, R13)
	constexpr std::uint32_t kCoreSpecialMenuPendingFirstId = 0x880; // FO4SFCoreValues.esm GLOB FO4SF_SpecialMenuPendingS..L (0x880..0x886)
	constexpr std::uint32_t kCoreSpecialMenuCommitReqId = 0x887;    // FO4SFCoreValues.esm GLOB FO4SF_SpecialMenuCommitRequested
	constexpr std::uint32_t kRadsRadawayLocalId = 0x820;     // FO4SFRads.esm ALCH FO4SF_RadAway
	constexpr std::array<const char*, 7> kSpecialPendingEditorIds{
		"FO4SF_SpecialMenuPendingS",
		"FO4SF_SpecialMenuPendingP",
		"FO4SF_SpecialMenuPendingE",
		"FO4SF_SpecialMenuPendingC",
		"FO4SF_SpecialMenuPendingI",
		"FO4SF_SpecialMenuPendingA",
		"FO4SF_SpecialMenuPendingL",
	};
	constexpr std::array<std::uint32_t, 6> kLimbConditionAvifIds{ 0x36C, 0x36D, 0x36E, 0x370 - 1, 0x370, 0x371 };
	constexpr std::array<const char*, 7> kSpecialTitleNames{
		"Strength", "Perception", "Endurance", "Charisma", "Intelligence", "Agility", "Luck"
	};
	constexpr std::size_t   kRefrRemoveItemSlot = 0x8B;      // libxse RE::TESObjectREFR::RemoveItem (docs/ui/pipboy-inv-drop-note.md)
	constexpr std::size_t   kFormTypeAt = 0x2E;              // libxse RE::TESForm::formType (a u8)
	constexpr std::uint8_t  kIdleType = 0x5C;                // libxse FormType kIDLE (TESIdleForm)
	constexpr std::size_t   kIdleGraphAt = 0x68;             // FAL-719, the 3b session at 1.16.244 (the Sep 2025 libxse header:
	constexpr std::size_t   kIdleEventAt = 0x70;             //   0x60 and 0x68)
	constexpr std::size_t   kIdleSlotFirst = 0x58;           // FAL-719: step=arm_idle_slots reads s58 to s80, 8 bytes apart
	constexpr std::size_t   kIdleSlotLast = 0x80;
	constexpr std::uint32_t kAnimHolderAt = 0x60;            // libxse RE::TESObjectREFR: IAnimationGraphManagerHolder base
	constexpr std::size_t   kNotifyGraphSlot = 0x01;         // libxse IAnimationGraphManagerHolder::NotifyAnimationGraphImpl
	constexpr std::size_t   kGetGraphMgrSlot = 0x03;         // libxse IAnimationGraphManagerHolder::GetAnimationGraphManagerImpl
	constexpr std::size_t   kMaxIdleName = 96;               // an idle's editor id or an event's name: letters, digits, '_'
	constexpr std::uint32_t kMaxArmMs = 6000;                // ArmRaiseMs, ArmLowerMs and ArmRetryMs, at most
	constexpr std::int64_t  kArmRetryEveryMs = 100;          // FAL-725: a refused raise or lower is resent this often
	constexpr std::uint32_t kF10 = 0x79;                     // the owner's faction device (14 Nov): never Key at Arm=1
	constexpr std::uint32_t kQuickSaveKey = 0x74;            // FAL-719: F5 Quick Save and F9 Quick Load; the key thread only
	constexpr std::uint32_t kQuickLoadKey = 0x78;            //   polls, so a press with the screen closed reaches the game too

	// stage d (the STAT page)
	constexpr std::uint32_t kDataHandlerRva = 0x5FD9B28;     // SFSE 0.2.21 sfse/GameData.h: TESDataHandler::GetSingleton
	constexpr std::uint32_t kLookupByIdRva = 0x5DE3B0;       // SFSE 0.2.21 sfse/GameForms.cpp: TESForm::GetFormByNumericID
	constexpr std::uint32_t kCoreFormIds = 0x1000;           // Starfield.esm form ids searched for the actor values
	constexpr std::uint32_t kRadsLocalId = 0x800;            // FO4SF_Rads in FO4SFRadsProbe.esm (dotnet/RadsProbe AvifId)
	constexpr std::uint32_t kGameHourId = 0x38;              // Starfield.esm GLOB GameHour (docs/ai/test-queue.md)
	constexpr std::uint32_t kGameDaysPassedId = 0x39;        // Starfield.esm GLOB GameDaysPassed
	constexpr std::uint32_t kHealthId = 0x2D4;               // Starfield.esm AVIF Health (the PC's read, 11 Nov)
	constexpr std::uint32_t kCarryWeightId = 0x2DC;          // Starfield.esm AVIF CarryWeight
	constexpr std::uint32_t kExperienceId = 0x2C9;           // Starfield.esm AVIF Experience
	constexpr std::size_t   kFormArrayEntries = 0xE0;        // form-list entries logged (SFSE: 0xDA before unk14E0)
	constexpr std::size_t   kFormArraysAt = 0x70;            // TESDataHandler::formArrays, libxse and SFSE agree: 0x18
	constexpr std::size_t   kFormArrayBytes = 0x18;          //   each, a lock, then a BSTArray of TESForm*
	constexpr std::size_t   kGlobType = 0x0A;                // FormType kGLOB, libxse and SFSE agree
	constexpr std::size_t   kAvifType = 0x6D;                // FormType kAVIF, libxse and SFSE agree
	constexpr std::size_t   kFormIdAt = 0x28;                // TESForm::formID, libxse and SFSE agree
	constexpr std::size_t   kGlobalEditorIdAt = 0x30;        // libxse RE::TESGlobal::formEditorID (a BSFixedString first)
	constexpr std::size_t   kGlobalBytesAt = 0x28;           // the TESGlobal bytes logged: from the form id to the end of
	constexpr std::size_t   kGlobalObjectBytes = 0x50;      //   the object (the game's own size for a GLOB, form type 0x0A at +0x2E)
	constexpr std::size_t   kGlobalBytes = kGlobalObjectBytes - kGlobalBytesAt;
	constexpr std::size_t   kGlobalValueAt = 0x48;           // the float the game's GetValue reads (vmovss xmm0, [r8+0x48]); libxse's
	constexpr std::size_t   kGlobalSearchFrom = 0x30;        //   +0x40 read -3.5924 at a156037c, and the slot at +0x28 is the form id
	constexpr float         kGlobalMinutes = 3.0f;           // GameHour and GameDaysPassed's fraction agree this close
	constexpr float         kMaxDays = 1000000.0f;           // GameDaysPassed below this
	constexpr std::size_t   kAvifEditorIdAt = 0x40;          // libxse RE::ActorValueInfo::editorID
	constexpr std::size_t   kBaseObjectAt = 0x80 + 0x18;     // libxse RE::TESObjectREFR::data, OBJ_REFR::objectReference
	constexpr std::size_t   kParentCellAt = 0xB0;            // libxse RE::TESObjectREFR::parentCell
	constexpr std::size_t   kLoadedDataAt = 0xB8;            // libxse RE::TESObjectREFR::loadedData (BSGuarded<LOADED_REF_DATA*, ...>)
	constexpr std::size_t   kLoadedData3DAt = 0x08;          // libxse RE::LOADED_REF_DATA::data3D (NiPointer<NiAVObject>)
	constexpr std::size_t   kCellWorldAt = 0x110;            // FAL-595, PC at 4d1e7641: kit_map_world at=+110 "Mars" outdoors in two
	                                                         // cells, found=0 indoors (libxse names +0x118, which read 0)
	constexpr std::size_t   kCellScanEnd = 0x200;            // FAL-595: F11 looks for the worldspace in the cell's +0x38 to here
	constexpr std::size_t   kAngleAt = 0x80;                 // FAL-595: libxse OBJ_REFR::angle, three floats (radians)
	constexpr std::size_t   kMapDumpBytes = 0x40;            // F11: the player's +0x80 to +0xC0 (angle, location, ... parentCell)
	constexpr std::size_t   kCellFlagsAt = 0x40;             // libxse RE::TESObjectCELL::cellFlags (kInterior = 1)
	constexpr std::size_t   kCellDataAt = 0x58;              // libxse RE::TESObjectCELL::cellData: EXTERIOR_DATA*, cellX, cellY
	constexpr std::uint32_t kGridUnitsMin = 1;               // [Kit] GridUnits=: a cell's width in game units, 1 ...
	constexpr std::uint32_t kGridUnitsMax = 65536;           // ... to 65536 (the PC, 12 Nov: cell_x is x over 100)
	constexpr std::size_t   kLevelAt = 0x08 + 0x06;          // libxse RE::TESActorBaseData::actorData, ACTOR_BASE_DATA::level
	constexpr std::size_t   kFullNameAt = 0x08;              // libxse RE::TESFullName::fullName (a BSFixedStringCS)
	constexpr std::size_t   kPageLines = 7;                  // make_probe_swf.py PAGE_LINES
	constexpr std::size_t   kPageColumns = 54;               // make_probe_swf.py page_columns(): the characters of a line
	constexpr std::string_view kPageChars = " !#%&'()+,-./0123456789:=?ABCDEFGHIJKLMNOPQRSTUVWXYZ_";   // PAGE_FONT
	constexpr auto          kTabFieldName = "fo4sfTab";      // make_probe_swf.py TAB_FIELD
	constexpr auto          kLineFieldName = "fo4sfLine";    // make_probe_swf.py LINE_FIELD, then 0 to 6
	constexpr auto          kTabButtonName = "fo4sfTabButton";       // make_probe_swf.py TAB_BUTTON
	constexpr auto          kCloseButtonName = "fo4sfCloseButton";   // make_probe_swf.py CLOSE_BUTTON

	// stage e (the kit): make_pipboy_kit.py's sizes, columns, font and names
	constexpr std::size_t   kKitTabs = 5;                    // TABS: main tabs
	constexpr std::size_t   kKitSubs = 5;                    // SUBS: sub-tab slots
	constexpr std::size_t   kKitRows = 16;                   // ROWS: list rows on screen, and value rows
	constexpr std::size_t   kKitFooter = 3;                  // FOOTER: footer cells
	constexpr std::size_t   kKitMaxPageRows = 64;            // MAX_PAGE_ROWS: Row= lines per page
	constexpr std::size_t   kKitTitleColumns = 42;           // TITLE_COLUMNS (the header's too)
	constexpr std::size_t   kKitTabColumns = 9;              // TAB_COLUMNS
	constexpr std::size_t   kKitSubColumns = 13;             // SUB_COLUMNS
	constexpr std::size_t   kKitNameColumns = 33;            // NAME_COLUMNS
	constexpr std::size_t   kKitValueColumns = 8;            // VALUE_COLUMNS
	constexpr std::size_t   kKitInfoLabelColumns = 16;       // INFO_LABEL_COLUMNS
	constexpr std::size_t   kKitInfoValueColumns = 12;       // INFO_VALUE_COLUMNS
	constexpr std::size_t   kKitFooterColumns = 23;          // FOOTER_COLUMNS
	constexpr std::size_t   kKitFooterLabelColumns = 10;     // FOOTER_LABEL_COLUMNS
	constexpr std::size_t   kKitHintColumns = 72;            // HINT_COLUMNS
	constexpr std::uint32_t kKitVersion = 1;                 // KIT_VERSION
	constexpr std::size_t   kKitTestRows = 30;               // the kit_test list
	constexpr std::size_t   kInventoryListAt = 0xA0;         // libxse RE::TESObjectREFR::inventoryList (BSGuarded: the pointer first)
	constexpr std::size_t   kInventoryDataAt = 0x28;         // libxse RE::BGSInventoryList::data, BSTArray<BGSInventoryItem>
	constexpr std::size_t   kInventoryItemSize = 0x28;       // libxse sizeof(RE::BGSInventoryItem)
	constexpr std::size_t   kItemStacksAt = 0x10;            // libxse RE::BGSInventoryItem::stacks, BSTArray<Stack>
	constexpr std::size_t   kItemFlagsAt = 0x20;             // libxse RE::BGSInventoryItem::flags (bits 0-2: the equip slot)
	constexpr std::size_t   kStackSize = 0x10;               // libxse sizeof(RE::BGSInventoryItem::Stack)
	constexpr std::size_t   kStackCountAt = 0x08;            // a u32: the PC's step=kit_inventory read 01000000 here (11 Nov)
	constexpr std::size_t   kKitMaxItems = 512;              // the inventory list's rows, at most
	constexpr std::size_t   kFileCollectionAt = 0x1580;      // libxse RE::TESDataHandler::compiledFileCollection
	constexpr std::size_t   kFileNameAt = 0x38;              // libxse RE::TESFile::fileName, char[260]
	constexpr std::size_t   kFileNameSize = 260;
	constexpr std::size_t   kFileCompileIndexAt = 0x1B7;     // libxse RE::TESFile::compileIndex
	constexpr std::size_t   kFileIndexAt = 0x218;            // libxse RE::TESFile::fileIndex: full u8, medium u8, small u16
	constexpr std::size_t   kKitMaxFiles = 4096;             // a file list's entries, at most
	constexpr std::size_t   kQuestFlagsAt = 0x10C;           // libxse RE::TESQuest QUEST_DATA flags, u16 (bits: the PC's log)
	constexpr std::size_t   kQuestBytesAt = 0x100;           // the quest's bytes logged once (flags and stage among them)
	constexpr std::uint32_t kPauseFlag = 0x2;                // Pause=1 at stages d and e (FAL-446): the PC's sweep at 14176a5e
	constexpr std::size_t   kQuestDumpAt = 0x38;            // F11 at stage e (FAL-446): libxse RE::TESQuest's pad038 ...
	constexpr std::size_t   kQuestDumpEnd = 0x338;           // ... to the end of its startEventData (+0x330), 64 to a line
	constexpr std::size_t   kQuestStageLast = kQuestDumpEnd - 2;   // [Kit] MissionStageAt=: a u16 inside the F11 dump
	constexpr std::size_t   kQuestPointerLast = kQuestDumpEnd - 8;   // FAL-571: the dump's last 8-byte word
	constexpr std::size_t   kObjectiveBlock = 0x40;          // FAL-571: the bytes read behind each pointer followed
	constexpr std::size_t   kKitObjectives = 8;              // [Kit] MissionObjective= lines, at most
	constexpr std::size_t   kQuestObjectivesAt = 0x148;      // FAL-571, PC at 73271aa3: objectives' BSTArray, data at +0x150
	constexpr std::size_t   kObjectiveOwnerAt = 0x18;        // ... in each objective: its quest's address,
	constexpr std::size_t   kObjectiveNumberAt = 0x24;       // its number (u16, 10, 85, 86 as the console takes it)
	constexpr std::size_t   kObjectiveStateAt = 0x28;        // and its state (a byte: 0 not shown, 1 shown, 3 shown and completed)
	constexpr std::uint32_t kQuestObjectivesMax = 64;        // a larger size is not read (reason=head)
	constexpr std::size_t   kKitObjectiveRows = 12;          // value rows for objectives: 16 less FORM, FILE, FLAGS, STAGE
	constexpr std::string_view kKitChars = " !#%&'()*+,-./0123456789:;<=>?ABCDEFGHIJKLMNOPQRSTUVWXYZ[]_";   // KIT_FONT
	constexpr auto          kKitTitle = "fo4sfTitle";        // NAMES
	constexpr auto          kKitHeader = "fo4sfHeaderInfo";
	constexpr auto          kKitTab = "fo4sfTab";            // then 0 to 4, as each name below with a number
	constexpr auto          kKitTabMark = "fo4sfTabMark";
	constexpr auto          kKitTabHit = "fo4sfTabHit";
	constexpr auto          kKitSub = "fo4sfSub";
	constexpr auto          kKitSubDim = "fo4sfSubDim";
	constexpr auto          kKitSubHit = "fo4sfSubHit";
	constexpr auto          kKitRowName = "fo4sfRowName";
	constexpr auto          kKitRowValue = "fo4sfRowValue";
	constexpr auto          kKitRowNameSel = "fo4sfRowNameSel";
	constexpr auto          kKitRowValueSel = "fo4sfRowValueSel";
	constexpr auto          kKitBar = "fo4sfBar";
	constexpr auto          kKitRowHit = "fo4sfRowHit";
	constexpr auto          kKitMoreUp = "fo4sfMoreUp";
	constexpr auto          kKitMoreDown = "fo4sfMoreDown";
	constexpr auto          kKitInfoLabel = "fo4sfInfoLabel";
	constexpr auto          kKitInfoValue = "fo4sfInfoValue";
	constexpr auto          kKitFoot = "fo4sfFoot";
	constexpr auto          kKitHints = "fo4sfHints";
	constexpr auto          kKitClose = "fo4sfClose";
	constexpr auto          kKitId = "fo4sfKitId";
	// VALUE_PROVIDERS and LIST_PROVIDERS; av:<hex> is the actor value of that form id
	constexpr std::array<std::string_view, 12> kKitValues{ "health", "level", "xp", "carry_max", "rads", "cell", "world",
		"time", "days", "position", "heading", "grid" };
	constexpr std::array<std::string_view, 3> kKitLists{ "kit_test", "inventory", "quests" };
	constexpr std::string_view kKitActorValue = "av:";
	// the menus a main-thread snapshot asks the engine about (IsMenuRegistered, IsMenuOpen); only Console is named by
	// libxse, the rest are guesses, and the first snapshot logs which of them are registered
	constexpr std::array<const char*, 14> kKnownMenus{ "FO4SF_PipboyMenu", "HUDMenu", "CursorMenu", "PauseMenu",
		"Console", "LoadingMenu", "FaderMenu", "DataMenu", "InventoryMenu", "MainMenu", "DialogueMenu", "ContainerMenu",
		"BarterMenu", "SleepWaitMenu" };

	struct Id
	{
		const char*   name;
		std::uint32_t id;
		const char*   source;
	};

	enum : std::size_t
	{
		kUISingleton,
		kRegisterMenu,
		kIsMenuOpen,
		kQueueSingleton,
		kAddMessage,
		kStringGetEntry,
		kStringRelease,
		kVtblPrimary,
		kVtblInput,
		kVtblSink,
		kRtti,
		kCtor,
		kDtor,
		kLoadMovie,
		kProcessMessage,
		kIsMovieLoaded,
		kIdCountB,                       // stages a and b check the ids above; stage c all of them
		kMainSingleton = kIdCountB,
		kPlayerSingleton,
		kControlMapSingleton,
		kMainRtti,
		kPlayerRtti,
		kControlMapRtti,
		kMovieImplRtti,
		kMovieRootRtti,
		kValueAddRef,
		kValueRelease,
		kValueGetMember,
		kValueSetMember,
		kValueInvoke,
		kGameVmSingleton,                // FAL-246: the click reaches a quest
		kGameVmRtti,
		kVmRtti,
		kIdCountC,                       // stage c checks the ids above; stage d all of them
		kDataHandlerSingleton = kIdCountC,
		kLookupById,
		kIdCount
	};

	// README, "Where every id comes from": libxse = libxse/commonlibsf 9d090c4 include/RE/IDs*.h; precedent = a
	// public precedent's CommonLibSF fork, annotated for 1.16.244 (its offsets are logged here, never assumed)
	constexpr std::array<Id, kIdCount> kIds{ {
		{ "UI.Singleton", 937580, "libxse" },
		{ "UI.RegisterMenu", 130463, "libxse" },
		{ "UI.IsMenuOpen", 130475, "libxse" },
		{ "UIMessageQueue.Singleton", 937897, "libxse" },
		{ "UIMessageQueue.AddMessage", 130659, "libxse" },
		{ "BSStringPool.GetEntry", 1186742, "libxse" },
		{ "BSStringPool.Entry.Release", 139340, "libxse" },
		{ "IMenu.vtable.primary", 475515, "libxse VTABLE_IMenu, checked by RTTI" },
		{ "IMenu.vtable.BSInputEventUser", 475517, "libxse VTABLE_IMenu[1], checked by RTTI" },  // +0x10, 10 slots
		{ "IMenu.vtable.BSTEventSink", 475519, "libxse VTABLE_IMenu[0], checked by RTTI" },     // +0x50, 2 slots
		{ "IMenu.RTTI", 844868, "libxse RTTI_IMenu" },
		{ "IMenu.ctor", 130615, "precedent" },
		{ "IMenu.scalar_deleting_dtor", 130616, "precedent" },
		{ "IMenu.LoadMovie", 130618, "precedent" },
		{ "IMenu.ProcessMessage", 130624, "precedent" },
		{ "IMenu.IsMovieLoaded", 130619, "precedent" },
		{ "Main.Singleton", 883591, "libxse" },
		{ "PlayerCharacter.Singleton", 922868, "libxse" },
		{ "ControlMap.Singleton", 938003, "libxse" },
		{ "Main.RTTI", 859948, "libxse RTTI_Main, checked by name" },
		{ "PlayerCharacter.RTTI", 860819, "libxse RTTI_PlayerCharacter, checked by name" },
		{ "ControlMap.RTTI", 867481, "libxse RTTI_ControlMap, checked by name" },
		{ "GFx.MovieImpl.RTTI", 841612, "libxse RTTI_Scaleform__GFx__MovieImpl, checked by name" },
		{ "GFx.AS3.MovieRoot.RTTI", 842209, "libxse RTTI_Scaleform__GFx__AS3__MovieRoot, checked by name" },
		{ "GFx.Value.ObjectAddRef", 169745, "libxse, equal to SFSE's" },
		{ "GFx.Value.ObjectRelease", 169746, "libxse, equal to SFSE's" },
		{ "GFx.Value.GetMember", 169748, "libxse, equal to SFSE's" },
		{ "GFx.Value.SetMember", 169749, "libxse, equal to SFSE's" },
		{ "GFx.Value.Invoke", 169750, "libxse, equal to SFSE's" },
		{ "GameVM.Singleton", 937585, "libxse, as FOCCPing" },
		{ "GameVM.RTTI", 865426, "libxse RTTI_GameVM, checked by name" },
		{ "BSScript.Internal.VirtualMachine.RTTI", 870795, "libxse RTTI_BSScript__Internal__VirtualMachine, checked by name" },
		{ "TESDataHandler.Singleton", 937572, "libxse, equal to SFSE's" },
		{ "TESForm.LookupByID", 47401, "libxse, equal to SFSE's" },
	} };

	// stage c: each RTTI id's type name after its ".?AV" (class) or ".?AU" (struct) prefix, and SFSE 0.2.21's own
	// 1.16.244 address of each Value function (sfse/ScaleformValue.h at 48535cc, ObjectInterface); the Address Library
	// offset must equal it
	constexpr std::array<std::pair<std::size_t, std::string_view>, 7> kRttiNames{ {
		{ kMainRtti, "Main@@"sv },
		{ kPlayerRtti, "PlayerCharacter@@"sv },
		{ kControlMapRtti, "ControlMap@@"sv },
		{ kMovieImplRtti, "MovieImpl@GFx@Scaleform@@"sv },
		{ kMovieRootRtti, "MovieRoot@AS3@GFx@Scaleform@@"sv },
		{ kGameVmRtti, "GameVM@@"sv },
		{ kVmRtti, "VirtualMachine@Internal@BSScript@@"sv },
	} };
	constexpr std::array<std::pair<std::size_t, std::uint32_t>, 5> kSfseRvas{ {
		{ kValueAddRef, 0x3352400 },
		{ kValueRelease, 0x33524A0 },
		{ kValueGetMember, 0x33528A0 },
		{ kValueSetMember, 0x3352C90 },
		{ kValueInvoke, 0x33530B0 },
	} };

	using Ctor_t = void* (*)(void*);
	using Dtor_t = void* (*)(void*, std::uint32_t);
	using LoadMovie_t = bool (*)(void*, bool, bool);
	using ProcessMessage_t = RE::UI_MESSAGE_RESULT (*)(void*, RE::UIMessageData&);

	// the primary vtable copy, with the engine's RTTI complete object locator in the slot before it, where MSVC's
	// dynamic_cast reads it. The engine casts a shown menu from IMenu to GameMenuBase (FAL-187 hang dump at b3f352b7);
	// without the locator the cast read the global that happened to lie before the copy, and the game hung
	struct PrimaryVtable
	{
		std::uintptr_t                     locator;
		std::array<std::uintptr_t, kSlots> slots;
	};
	static_assert(sizeof(PrimaryVtable) == (1 + kSlots) * sizeof(std::uintptr_t));   // no padding: locator is slots[-1]

	// FAL-414: the BSInputEventUser vtable copy (subobject 0x10, ten slots; the locator again one slot before it)
	constexpr std::size_t kInputSlots = 10;
	struct InputVtable
	{
		std::uintptr_t                          locator;
		std::array<std::uintptr_t, kInputSlots> slots;
	};
	static_assert(sizeof(InputVtable) == (1 + kInputSlots) * sizeof(std::uintptr_t));

	// INI (FO4SFPipboyMenu.ini next to the dll)
	int           g_stage = 0;      // 0 off, 1 = (a), 2 = (b), 3 = (c), 4 = (d), 5 = (e)
	std::uint32_t g_key = 0x79;     // F10
	std::uint32_t g_flags = 0;      // OR'ed into the flags the constructor set
	bool          g_keepAlive = true;
	std::string   g_movie;          // FAL-614, Stage=2 only: Movie=, the movie Interface/<Movie>.swf instead of ours; "" = ours

	std::uintptr_t                           g_base = 0;
	std::size_t                              g_imageSize = 0;
	std::array<std::uint32_t, kIdCount>      g_rva{};
	PrimaryVtable                            g_vtbl{};
	InputVtable                              g_inputVtbl{};
	bool (*g_engineShouldHandle)(void*, const void*) = nullptr;   // input vtable [01], called with this = menu + 0x10
	void (*g_engineOnButton)(void*, const void*) = nullptr;       // input vtable [08]
	std::array<std::uint32_t, 4>             g_cancelCodes{ 0x1B, 0x09, 0, 0 };   // INI CancelCodes: Esc, Tab (Windows virtual-key codes: the PC's game run, #738)
	std::size_t                              g_cancelCount = 2;
	std::atomic<bool>                        g_cancelHeld{ false };    // a Tab or Esc press already closed the menu, not yet released
	std::atomic<bool>                        g_cancelNow{ false };     // Tab or Esc heard while open: the key thread closes the menu
	std::atomic<std::uint32_t>               g_cancelLogged{ 0 };
	Ctor_t                                   g_ctor = nullptr;
	Dtor_t                                   g_engineDtor = nullptr;
	LoadMovie_t                              g_engineLoadMovie = nullptr;
	std::atomic<bool>                        g_loadingMovie{ false };   // FAL-614: inside our call of the engine's LoadMovie
	std::atomic<std::uint32_t>               g_movieNameAsks{ 0 };      // GetName calls answered with Movie= in that call
	bool                                     g_codeObj = false;         // FAL-614 proof 1b: CodeObj=1, the stand-in BGSCodeObj
	bool                                     g_codeObjHide = false;     // FAL-614 proof 1c: CodeObjHide=1, HideMenu closes our menu
	bool                                     g_codeObjSound = false;    // FAL-614 proof 1d: CodeObjSound=1, PlaySound plays a file
	std::string                              g_codeObjInit;             // FAL-614 proof 2a: CodeObjInit=<root function>, handed the stand-in
	std::array<std::string, kMaxCodeNames>   g_probeNames;              // FAL-614 proof 2b-i: CodeObjProbe=, read once after the hand-over
	std::size_t                              g_probeCount = 0;
	std::array<std::string, kMaxCodeNames>   g_rootCallNames;           // FAL-614 proof 2b-ii: CodeObjCalls=, called once after the hand-over
	std::size_t                              g_rootCallCount = 0;
	std::string                              g_codeObjAt;               // FAL-614 S1-c: CodeObjAt=<path>, the stand-in also as <path>.BGSCodeObj
	bool                                     g_codeObjPages = false;    // FAL-614 S1-c: CodeObjPages=1, onNewPage and onNewTab answered
	bool                                     g_populateInCall = false;  // Task 1 step 1b: default 0 for 1a crash proof; 1 fills vitals in PopulatePipboyInfoObj
	bool                                     g_lateInvalidate = false;  // Task 1 step 1b: optional late InvalidateData on kShow, default 0
	bool                                     g_statActions = false;     // Task 1 step 1j: UseStimpak/UseRadaway, default 0 until THIS ROUND passes
	bool                                     g_invDataAnswers = false;  // Task 1 step 1k: INV/DATA same-call answers, default 0 until THIS ROUND passes
	bool                                     g_shellBackdrop = true;    // Round 10 C4-1: opaque CRT backdrop on FO4SF_Fo4Shell (default 1, rollback 0)
	bool                                     g_shellVitalsFill = false; // Round 10 C4-2: FillPipboyDataObj on kShow/page/partial when PopulateInCall=0 (C++ default 0, staged 1, rollback 0 = exact 2f path)
	bool                                     g_suppressDataMenu = false; // Round 10 C4-4: opt-in hide-only DataMenu suppression (default 0)
	bool                                     g_tabOpensPipboy = false;   // Round 10 C4-4: opt-in closed-Pip-Boy Tab open with blocking-menu cooldown (default 0)
	bool                                     g_hideStarfieldWatch = false; // Round 11 D7(b): hide Starfield HUDMenu BottomLeftGroup_mc wrist watch (C++ fallback 0, staged 1, rollback 0)
	bool                                     g_requirePickup = false;   // Task 4 step X2: RequirePickup=0 default off; 1 checks FO4SF_PipboyAcquired >= 0.5
	fo4sf::pipboy::ScreenSourceMode          g_screenSourceIni = fo4sf::pipboy::ScreenSourceMode::k2DIMenu;
	fo4sf::hud::QuestLabelConfig             g_questLabelCfg{};
	fo4sf::hud::TranslateFileStatus          g_translateStatus{};
	std::atomic<bool>                        g_questLabelRuntimeIdsOk{ false };
	std::uint32_t                            g_scaleformSingletonRva = 0;
	std::uint32_t                            g_scaleformTranslateRva = 0;
	std::uint32_t                            g_scaleformRttiRva = 0;
	std::string                              g_bootMovie;               // Task 1 step 1f: BootMovie=pipboybootsequence
	bool                                     g_bootOnFirstOpen = false; // Task 1 step 1f: play BootMovie once after FO4SF_PipboyAcquired >= 0.5
	std::filesystem::path                    g_gameDir;                 // Game root (<Starfield>/) for Data\Interface\<BootMovie>.swf check
	std::atomic<bool>                        g_loggedBootSkipMissing{ false };
	// Task 1 step 1k (UI-3): opt-in FO4SF_SpecialMenu host for SPECIALMenu.swf
	bool                                     g_specialMenu = false;
	std::string                              g_specialMovie;
	std::uint32_t                            g_specialMaxPoints = 40;
	std::uint32_t                            g_specialKey = 0;
	PrimaryVtable                            g_specialVtbl{};
	InputVtable                              g_specialInputVtbl{};
	std::atomic<bool>                        g_specialOpen{ false };
	std::atomic<bool>                        g_specialClosing{ false };
	std::atomic<bool>                        g_loadingSpecialMovie{ false };
	std::atomic<const void*>                 g_specialCodeObjMovie{ nullptr };
	std::atomic<std::uint32_t>               g_specialCreated{ 0 };
	// N2 Variant (b): non-modal depth=0 start title card (FO4SF_StartCardMenu -> Interface/FO4SF_StartCard.swf)
	PrimaryVtable                            g_startCardVtbl{};
	InputVtable                              g_startCardInputVtbl{};
	std::atomic<bool>                        g_startCardOpen{ false };
	std::atomic<bool>                        g_loadingStartCardMovie{ false };
	std::atomic<bool>                        g_startCardMissing{ false };
	std::atomic<std::uint32_t>               g_startCardCreated{ 0 };
	// S1 / S3 Variant (b): interactive single-page New-Game Setup Screen (FO4SF_SetupMenu -> Interface/FO4SF_SetupScreen.swf)
	std::filesystem::path                    g_pluginDir;
	bool                                     g_setupShowUnavailable = false;
	PrimaryVtable                            g_setupVtbl{};
	InputVtable                              g_setupInputVtbl{};
	// T2 (Round 6): non-null minimal self-hiding IMenu for optional MapBlockStarMap=1 create-time block
	PrimaryVtable                            g_blockedMapVtbl{};
	InputVtable                              g_blockedMapInputVtbl{};
	std::atomic<std::uint32_t>               g_blockedMapCreated{ 0 };
	std::atomic<bool>                        g_setupOpen{ false };
	std::atomic<bool>                        g_loadingSetupMovie{ false };
	std::atomic<bool>                        g_setupMissing{ false };
	std::atomic<const void*>                 g_setupListenedMovie{ nullptr };
	std::atomic<std::uint32_t>               g_setupCreated{ 0 };
	std::mutex                               g_setupLock;
	fo4sf::setup::SetupScreenModel           g_setupModel;
	bool                                     g_setupModelLoaded = false;
	// Paused Vault 111 Exit Lift + 40-pt S.P.E.C.I.A.L. Screen (FO4SF_LiftMenu -> Interface/FO4SF_LiftScreen.swf)
	PrimaryVtable                            g_liftVtbl{};
	InputVtable                              g_liftInputVtbl{};
	std::atomic<bool>                        g_liftOpen{ false };
	std::atomic<bool>                        g_loadingLiftMovie{ false };
	std::atomic<bool>                        g_liftMissing{ false };
	std::atomic<const void*>                 g_liftListenedMovie{ nullptr };
	std::atomic<std::uint32_t>               g_liftCreated{ 0 };
	std::mutex                               g_liftLock;
	fo4sf::lift::LiftMenuModel               g_liftModel;
	// Persistent across opens (Step 1): Key opens s_savedPage; MapKey sets s_savedPage = 3 and opens 3
	std::atomic<std::uint32_t>               s_savedPage{ 0 };
	std::array<std::atomic<std::uint32_t>, 5> s_savedTabs{ { 0, 0, 0, 0, 0 } };
	std::atomic<bool>                        s_bootPlayed{ false };
	// Per-movie FO4 shell session state (cleared in ClearMovieSessionState / before engine kHide)
	RE::Scaleform::GFx::Value                g_dataObj;                 // menu thread only: Menu_mc.DataObj handed to PopulatePipboyInfoObj
	std::atomic<bool>                        g_closing{ false };        // Task 1 step 1c: set first on kHide so nothing writes to movie/DataObj
	std::atomic<bool>                        g_playingBootMovie{ false };
	std::atomic<std::int32_t>                g_bootReopenPage{ -1 };    // N1/H0c: >= 0 while boot_done kHide transitions directly to FO4SF_Fo4Shell
	std::atomic<bool>                        g_armDispatching{ false }; // N1: main-thread gate check in flight from ArmKey
	std::atomic<bool>                        g_inDestructionCall{ false };
	std::mutex                               g_deferredLogLock;
	std::vector<std::string>                 g_deferredDestructionLogs;
	std::atomic<const void*>                 g_destroyedCodeObjMovie{ nullptr };
	std::atomic<const void*>                 g_shownInvalidatedMovie{ nullptr };
	std::atomic<const void*>                 g_populatedLogMovie{ nullptr };
	std::atomic<const void*>                 g_vitalsLogMovie{ nullptr };
	std::atomic<const void*>                 g_backdropMovie{ nullptr };
	std::atomic<const void*>                 g_dateFixLogMovie{ nullptr };
	std::atomic<const void*>                 g_dateFixDoneMovie{ nullptr };   // Round 11 A2.6: once-per-movie/page date-fix guard
	std::atomic<std::int32_t>                g_dateFixDonePage{ -1 };
	std::atomic<const void*>                 g_hintBarDoneMovie{ nullptr };   // Round 11 D5-1: ButtonHintBar_mc repositioned below BottomBar_mc
	std::atomic<const void*>                 g_platformDoneMovie{ nullptr };  // Round 11 D5-2: SetPlatform(0, false) + trigger hide applied
	std::atomic<const void*>                 g_staticListsInitMovie{ nullptr }; // Round 11 A2.6: static structural DataObj lists built for this movie
	std::atomic<const void*>                 g_hudWatchHiddenMovie{ nullptr };  // Round 11 D7(b): HUDMenu movie whose BottomLeftGroup_mc watch was hidden
	std::atomic<std::uint32_t>               g_hudWatchTryCount{ 0 };           // Round 11 Review #5: attempts for current HUDMenu movie
	std::atomic<bool>                        g_hudWatchRetryPending{ false };   // Round 11 Review #5: retry across MenuOpenCloseEvent / UI poll until hidden or unloaded
	constexpr std::uint32_t                  kMaxHudWatchTries = 40;
	std::atomic<const void*>                 g_createdCodeObjMovie{ nullptr };
	std::atomic<const void*>                 g_activeShellMenu{ nullptr };
	std::atomic<std::int64_t>                g_lastShellTransitionMs{ 0 };
	std::atomic<bool>                        g_nonDataBlockingOpen{ false };
	std::atomic<std::int64_t>                g_lastNonDataBlockingMs{ 0 };
	std::atomic<std::uint32_t>               g_dataMenuSuppressions{ 0 };
	std::atomic<std::uint32_t>               g_tabKeyPresses{ 0 };
	constexpr std::int64_t                   kShellTabCooldownMs = 350;
	constexpr std::int64_t                   kBlockingMenuCooldownMs = 500;
	std::atomic<std::int32_t>                g_currentShellPage{ -1 };
	std::atomic<std::int32_t>                g_currentShellTab{ 0 };
	std::atomic<std::int32_t>                g_externalTargetPage{ -1 };
	std::atomic<std::uint32_t>               g_pendingPartialMask{ 0 };
	std::atomic<bool>                        g_keyInputHeld{ false };
	std::atomic<bool>                        g_pendingCancelRelease{ false };
	std::atomic<std::uint32_t>               g_invSortMode{ 0 };
	// Watchdog & movie call entry/exit diagnostics (Step 5, stack-aware & synchronized)
	struct GfxWatchdogFrame
	{
		std::uint64_t seq = 0;
		std::int64_t  startMs = 0;
		const char*   what = nullptr;
	};
	std::atomic<std::uint64_t>               g_gfxCallSeq{ 0 };
	std::mutex                               g_gfxWatchdogLock;
	GfxWatchdogFrame                         g_gfxActiveFrame{};
	thread_local std::vector<GfxWatchdogFrame> t_gfxWatchdogStack;
	std::atomic<std::uint64_t>               g_gfxWatchdogLoggedSeq{ 0 };
	std::atomic<std::uint32_t>               g_gfxFreqLines{ 0 };
	// Extra checked RVAs for FO4 shell stats/aid & native PlayIdle (not in kIds so Stage 1..3 step=id counts stay exact)
	std::uint32_t                            g_shellLookupEditorIdRva = 0;
	std::uint32_t                            g_equipMgrSingletonRva = 0;
	std::uint32_t                            g_equipMgrRttiRva = 0;
	std::uint32_t                            g_equipObjectRva = 0;
	std::uint32_t                            g_unequipObjectRva = 0;
	std::uint32_t                            g_objInstanceCtorRva = 0;
	std::uint32_t                            g_alchemyRttiRva = 0;
	bool                                     g_shellExtraIdsReady = false;
	std::mutex                               g_perkSoundLock;
	void*                                    g_activePerkWaveOut = nullptr;
	enum : int
	{
		kSpecialOff,
		kSpecialFill,
		kSpecialClear
	};
	int                                      g_codeObjSpecial = kSpecialOff;   // FAL-1025: CodeObjSpecial=fill or clear
	std::atomic<std::uint32_t>               g_specialLines{ 0 };
	std::atomic<std::uint32_t>               g_invFillLogs{ 0 };
	std::atomic<std::uint32_t>               g_questFillLogs{ 0 };
	std::atomic<std::uint32_t>               g_invSelectLogs{ 0 };
	struct ShellKey   // FAL-614 S1-c: ShellKeys=<key>:<path>,...
	{
		std::uint32_t vk = 0;
		std::string   path;
	};
	std::array<ShellKey, kMaxShellKeys>      g_shellKeys;
	std::size_t                              g_shellKeyCount = 0;
	std::atomic<std::uint32_t>               g_shellKeyPending{ 0 };    // key thread: one bit per ShellKeys entry pressed
	std::atomic<std::uint32_t>               g_shellKeyLines{ 0 };
	std::atomic<std::int32_t>                g_answerPage{ -1 };        // menu's thread: the page the shell asked for, -1 = none
	std::atomic<std::int32_t>                g_answerTab{ -1 };         // and the tab
	std::atomic<bool>                        g_answerNow{ false };      // key thread: send a kUpdate to answer
	std::atomic<std::uint32_t>               g_answers{ 0 };            // answers on g_codeObjMovie
	std::filesystem::path                    g_soundDir;                // <dll folder>/FO4SFPipboyMenuSounds
	std::atomic<std::uint32_t>               g_soundsPlaying{ 0 };
	std::atomic<std::uint32_t>               g_soundLines{ 0 };
	std::atomic<std::uint32_t>               g_codeCalls{ 0 };          // calls of the stand-in's functions, logged up to kMaxCodeCalls
	std::atomic<const void*>                 g_codeObjMovie{ nullptr }; // the movie the stand-in is set on (done for it)
	std::atomic<const void*>                 g_codeObjTriedMovie{ nullptr };
	std::atomic<std::uint32_t>               g_codeObjTries{ 0 };       // tries on g_codeObjTriedMovie

	// FAL-852, the arm (INI Arm ... ArmRetryMs; read at Stage=2 with Movie= only, used only at Arm=1)
	bool                                     g_arm = false;
	std::string                              g_armRaiseIdle;            // an editor id
	std::string                              g_armLowerIdle;            // an editor id, or empty
	std::string                              g_armLowerEvent;           // an event's name (ActionInterrupt), or empty
	std::uint32_t                            g_armRaiseMs = 2000;
	std::uint32_t                            g_armLowerMs = 3500;
	std::uint32_t                            g_armRetryMs = 2000;
	std::uint32_t                            g_armLookupRva = 0;        // TESForm::LookupByEditorID, CheckArmId
	std::uint32_t                            g_armPlayIdleRva = 0;      // Actor.PlayIdle helper (REL::ID 102136), CheckArmId
	std::uint32_t                            g_armPlayIdleCtxRva = 0;   // PlayIdle context getter (REL::ID 35720), CheckArmId
	std::uint32_t                            g_armRegSinkRva = 0;       // BSTEventSource::RegisterSink (REL::ID 123821), CheckArmId
	std::uint32_t                            g_armUnregSinkRva = 0;     // BSTEventSource::UnregisterSink (REL::ID 123822), CheckArmId
	std::atomic<std::int64_t>                g_armPressAt{ 0 };         // the last Key press that started a raise, steady ms
	std::atomic<std::uint32_t>               g_armN{ 0 };               // that press's n
	std::atomic<std::uint32_t>               g_armPendingOpenN{ 0 };    // active open cycle token consumed once by ArmShow/watchdog/Close
	std::atomic<std::int64_t>                g_armLowerUntil{ 0 };      // Key ignored until then (ArmLowerMs)
	std::atomic<bool>                        g_armRaiseAccepted{ false };
	std::atomic<bool>                        g_armWaitingRaiseGraph{ false };

	// FAL-725: one pending send (the raise or the lower). The main thread sends and writes the outcome; the key thread's
	// 30 ms tick queues the next try at nextAt. kIdle: nothing pending; kInFlight: a try is queued on the main thread;
	// kWaiting: the last try gave 0 and the next is due at nextAt
	enum : int
	{
		kRetryIdle,
		kRetryInFlight,
		kRetryWaiting
	};
	struct ArmRetry
	{
		std::atomic<int>           state{ kRetryIdle };
		std::atomic<std::uint32_t> n{ 0 };
		std::atomic<std::int64_t>  firstAt{ 0 };    // the first try, steady ms
		std::atomic<std::int64_t>  nextAt{ 0 };
		std::atomic<std::int64_t>  deadline{ 0 };   // firstAt + ArmRetryMs
		std::atomic<std::uint32_t> tries{ 0 };
	};
	ArmRetry                                 g_raiseRetry;
	ArmRetry                                 g_lowerRetry;
	std::atomic<std::int64_t>                g_armShowAt{ 0 };          // the screen's show due (0 = none), set by the raise's outcome
	std::string                              g_armRaiseOutcome;         // main thread only: "1", "gave_up", or a stop word
	std::atomic<bool>                        g_armShown{ false };       // our ProcessMessage saw kShow and no kHide since
	int                                      g_armState = -1;           // main thread only: -1 unresolved, 0 refused, 1 ready
	std::uintptr_t                           g_raiseIdle = 0;           // main thread only: the TESIdleForms
	std::uintptr_t                           g_lowerIdle = 0;
	RE::BSFixedString*                       g_lowerEvent = nullptr;    // main thread only: ArmLowerEvent's string, never freed
	std::uintptr_t                           g_armHolderVtable = 0;     // the player's IAnimationGraphManagerHolder vtable
	std::uintptr_t                           g_armNotify = 0;           // its checked slot 0x01
	std::uintptr_t                           g_armGetGraphMgr = 0;      // its checked slot 0x03 (GetAnimationGraphManagerImpl)
	std::uintptr_t                           g_armWatchedGraph = 0;     // BSAnimationGraph* with ArmAnimGraphSink registered
	std::uintptr_t                           g_armWatchedMgrAddr = 0;   // BSAnimationGraphManager* identity for g_armWatchedGraph
	std::uintptr_t                           g_armWatchedPlayer3D = 0;  // Player data3D identity when g_armWatchedGraph registered
	std::uint64_t                            g_armWatchedGen = 0;       // Load generation counter when g_armWatchedGraph registered
	std::atomic<std::uint64_t>               g_armGraphLoadGen{ 1 };    // Incremented on LoadingMenu / cell transition (A4)
	bool                                     g_armSawLoadingMenu = false;
	std::atomic<bool>                        g_shellHardcoreFastTravelBlocked{ false };
	ProcessMessage_t                         g_engineProcessMessage = nullptr;
	const SFSE::TaskInterface*               g_task = nullptr;
	std::atomic<bool>                        g_registered{ false };
	std::atomic<std::uint32_t>               g_created{ 0 };
	std::atomic<std::uint32_t>               g_otherMessages{ 0 };
	std::atomic<int>                         g_expectOpen{ -1 };

	// stage c (INI FlagSets, SnapshotKey)
	std::array<std::uint32_t, kMaxFlagSets>  g_flagSets{};
	std::size_t                              g_flagSetCount = 0;
	std::uint32_t                            g_snapshotKey = 0x7A;   // F11; 0 = none
	std::atomic<std::uint32_t>               g_ctorFlags{ 0 };
	std::atomic<std::uint32_t>               g_shows{ 0 };
	std::atomic<std::uint32_t>               g_updates{ 0 };
	std::atomic<std::uint32_t>               g_clicks{ 0 };
	std::atomic<std::uint32_t>               g_snapshots{ 0 };
	std::atomic<bool>                        g_open{ false };          // the main thread's last IsMenuOpen
	std::atomic<bool>                        g_channelOff{ false };    // a channel check refused: no more channel calls
	std::atomic<const void*>                 g_listenedMovie{ nullptr };   // the movie our click listener is on
	std::atomic<const void*>                 g_checkedMovie{ nullptr };    // the movie whose root RootOf checked
	std::atomic<int>                         g_mainOk{ -1 };           // -1 unchecked, 0 refused, 1 checked
	std::atomic<int>                         g_playerOk{ -1 };
	std::atomic<int>                         g_controlMapOk{ -1 };

	// stage c, FAL-246 (INI ClickCall=<script>.<function>; empty = off)
	std::string                              g_clickScript;
	std::string                              g_clickFunction;
	std::atomic<int>                         g_gameVmOk{ -1 };
	std::uintptr_t                           g_checkedVm = 0;          // main thread only: the VM whose type was checked
	bool                                     g_vmOff = false;          // main thread only: a VM check refused

	// stage d (INI PageFlagSets): the page. The text is collected on the main thread and written on the menu's
	std::atomic<std::uint32_t>               g_tab{ 0 };               // the shown tab: 0 STATUS, 1 DATA
	std::atomic<std::uint32_t>               g_tabClicks{ 0 };
	std::atomic<std::uint32_t>               g_closeClicks{ 0 };
	std::atomic<std::uint32_t>               g_pageWrites{ 0 };
	std::atomic<bool>                        g_refreshNow{ false };    // NEXT TAB: the key thread sends an update now
	std::atomic<bool>                        g_closeNow{ false };      // CLOSE: the key thread closes the menu
	std::mutex                               g_pageLock;
	std::array<std::array<std::string, kPageLines + 1>, 2> g_pageText;   // [tab][0] the tab line, [1..7] the lines

	std::uintptr_t Address(std::size_t a_id) { return g_base + g_rva[a_id]; }

	// FAL-614 proof 1b: stage b with CodeObj=1 reaches the movie's root as stage c does (RootOf's RTTI, the Value
	// functions), so it reads and checks stage c's ids too; without them RootOf compared against an unread RTTI address
	bool ChannelIdsNeeded() { return g_stage >= 3 || (g_stage == 2 && (g_codeObj || g_arm)); }   // FAL-852: the arm too

	std::size_t IdCount() { return g_stage >= 4 ? kIdCount : ChannelIdsNeeded() ? kIdCountC : kIdCountB; }   // (e): (d)'s ids

	bool InImage(std::uintptr_t a_addr, std::size_t a_len)
	{
		return a_addr >= g_base && a_len <= g_imageSize && a_addr - g_base <= g_imageSize - a_len;
	}

	std::string Hex(std::uintptr_t a_value) { return std::format("{:#x}", a_value); }

	const RE::BSFixedString& MenuName()
	{
		// process lifetime: a BSFixedString destructor calls the engine (the main thread makes it first)
		static auto* const name = new RE::BSFixedString(kMenuName);
		return *name;
	}

	bool IsOurs(const void* a_menu)
	{
		return a_menu && *static_cast<const std::uintptr_t*>(a_menu) == reinterpret_cast<std::uintptr_t>(g_vtbl.slots.data());
	}

	const void* MovieOf(const void* a_menu)
	{
		return static_cast<const RE::IMenu*>(a_menu)->uiMovie.get();
	}

	bool Refuse(std::string_view a_step, const std::string& a_what);

	// ------------------------------------------------------------------------------------------- stage c: reading
	// A read behind a pointer the engine handed us, or of a layout only libxse states: an access fault returns false
	// instead of stopping the game (a structured exception handler; no C++ object lives in this frame)
	bool Peek(std::uintptr_t a_addr, void* a_out, std::size_t a_len)
	{
		__try {
			std::memcpy(a_out, reinterpret_cast<const void*>(a_addr), a_len);
			return true;
		} __except (1 /* EXCEPTION_EXECUTE_HANDLER */) {
			return false;
		}
	}

	template <class T>
	bool Peek(std::uintptr_t a_addr, T& a_out)
	{
		return Peek(a_addr, &a_out, sizeof(T));
	}

	// FAL-571: a word of the quest's dump worth following: 8-byte aligned, in user space and outside the game's image (a
	// heap object), its 0x40 bytes committed, readable and not a guard page (VirtualQuery; a read of a guard page would
	// fault once and take its guard away)
	bool Followable(std::uintptr_t a_addr)
	{
		if (a_addr < 0x10000 || a_addr > 0x7FFF'FFFF'0000 || a_addr % 8 != 0 || InImage(a_addr, 1)) {
			return false;
		}
		REX::W32::MEMORY_BASIC_INFORMATION info{};
		if (!REX::W32::VirtualQuery(reinterpret_cast<const void*>(a_addr), &info, sizeof(info)) ||
			info.state != REX::W32::MEM_COMMIT) {
			return false;
		}
		constexpr std::uint32_t readable = REX::W32::PAGE_READONLY | REX::W32::PAGE_READWRITE | REX::W32::PAGE_WRITECOPY |
		                                   REX::W32::PAGE_EXECUTE_READ | REX::W32::PAGE_EXECUTE_READWRITE;
		constexpr std::uint32_t guard = 0x100;   // PAGE_GUARD, which REX::W32 does not name
		const auto              end = reinterpret_cast<std::uintptr_t>(info.baseAddress) + info.regionSize;
		return (info.protect & readable) != 0 && (info.protect & guard) == 0 && a_addr + kObjectiveBlock <= end;
	}

	// the mangled name in an RTTI type descriptor (inside the image), or "" if it leaves the image unterminated
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

	bool NameIs(std::string_view a_name, std::string_view a_tail)   // ".?AV" + tail (a class) or ".?AU" + tail (a struct)
	{
		return a_name.size() == 4 + a_tail.size() && (a_name.starts_with(".?AV") || a_name.starts_with(".?AU")) &&
		       a_name.substr(4) == a_tail;
	}

	struct ObjectType
	{
		std::uintptr_t descriptor = 0;
		std::uintptr_t hierarchy = 0;   // the complete type's class hierarchy descriptor
		std::uint32_t  offset = 0;
		std::string    name;
	};

	// an object's type through its vtable's complete object locator; false if a read faults or leaves the image
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

	std::string ShortName(std::string_view a_name)   // ".?AVHUDMenu@@" -> "HUDMenu@@" -> "HUDMenu"
	{
		if (a_name.size() > 4) {
			a_name.remove_prefix(4);
		}
		if (a_name.ends_with("@@")) {
			a_name.remove_suffix(2);
		}
		return std::string(a_name);
	}

	// a singleton is the type its RTTI id names (the same descriptor, at subobject offset 0), checked once; a null
	// singleton is not cached (it may not exist yet)
	bool CheckSingleton(std::string_view a_what, std::size_t a_singleton, std::size_t a_rtti, std::atomic<int>& a_state)
	{
		const auto state = a_state.load();
		if (state >= 0) {
			return state == 1;
		}
		std::uintptr_t object = 0;
		if (!Peek(Address(a_singleton), object) || !object) {
			REX::INFO("step=object name={} result=null", a_what);
			return false;
		}
		ObjectType type;
		const bool known = TypeOf(object, type);
		if (!known || type.descriptor != Address(a_rtti) || type.offset != 0) {
			a_state = 0;
			Refuse("object", std::format("name={} object={} type={} offset={} (its reads stay off)", a_what, Hex(object),
				known ? type.name : "unreadable", Hex(type.offset)));
			return false;
		}
		a_state = 1;
		REX::INFO("step=object name={} object={} type={}", a_what, Hex(object), type.name);
		return true;
	}

	std::uintptr_t Singleton(std::size_t a_singleton)
	{
		std::uintptr_t object = 0;
		Peek(Address(a_singleton), object);
		return object;
	}

	struct ArrayHead   // BSTArray (libxse): size, capacity, data
	{
		std::uint32_t  size;
		std::uint32_t  capacity;
		std::uintptr_t data;
	};

	std::string ReadPaused()
	{
		if (!CheckSingleton("Main", kMainSingleton, kMainRtti, g_mainOk)) {
			return "?";
		}
		std::uint8_t paused = 0;
		return Peek(Singleton(kMainSingleton) + kMainPausedAt, paused) ? std::to_string(paused) : "fault";
	}

	// which of kKnownMenus are open, through the engine's own IsMenuRegistered and IsMenuOpen (the calls Register and
	// Toggle make): main thread only. The first call logs which names are registered, so a wrong guess shows
	std::string ReadMenus()
	{
		auto* ui = RE::UI::GetSingleton();
		if (!ui) {
			return "no_ui";
		}
		// process lifetime, as MenuName(): made once, on the main thread
		static const auto* const names = [] {
			auto* list = new std::vector<RE::BSFixedString>();
			for (const auto* name : kKnownMenus) {
				list->emplace_back(name);
			}
			return list;
		}();
		static bool logged = false;
		std::string open;
		std::string registered;
		std::string unknown;
		std::size_t count = 0;
		for (std::size_t i = 0; i < names->size(); ++i) {
			const auto& name = (*names)[i];
			if (!ui->IsMenuRegistered(name)) {
				unknown += std::format("{}{}", unknown.empty() ? "" : ",", kKnownMenus[i]);
				continue;
			}
			registered += std::format("{}{}", registered.empty() ? "" : ",", kKnownMenus[i]);
			if (ui->IsMenuOpen(name)) {
				open += std::format("{}{}", count++ ? "," : "", kKnownMenus[i]);
			}
		}
		if (!logged) {
			logged = true;
			REX::INFO("step=menu_names registered={} not_registered={}", registered.empty() ? "none" : registered,
				unknown.empty() ? "none" : unknown);
		}
		return std::format("{}[{}]", count, open);
	}

	// ControlMap's active input contexts in stored order (their ids)
	std::string ReadContexts()
	{
		if (!CheckSingleton("ControlMap", kControlMapSingleton, kControlMapRtti, g_controlMapOk)) {
			return "?";
		}
		ArrayHead list{};
		if (!Peek(Singleton(kControlMapSingleton) + kContextsAt, list)) {
			return "fault";
		}
		std::string out = std::format("{}[", list.size);
		for (std::uint32_t i = 0; i < list.size && i < kMaxListed; ++i) {
			std::uint8_t id = 0;
			out += std::format("{}{}", i ? "," : "", Peek(list.data + 16ull * i, id) ? std::to_string(id) : "fault");
		}
		return out + "]";
	}

	// FAL-414 diagnostic, main thread, on the snapshot key: each known menu the UI has open, with its flags and the four
	// unnamed IMenu words at +0xC4..+0xD0 (read with Peek), so a run with our menu, the data menu and the pause menu open
	// shows what a real menu asks the control map for
	void LogOpenMenuDetails()
	{
		auto* ui = RE::UI::GetSingleton();
		if (!ui) {
			return;
		}
		static const auto* const names = [] {
			auto* list = new std::vector<RE::BSFixedString>();
			for (const auto* name : kKnownMenus) {
				list->emplace_back(name);
			}
			return list;
		}();
		for (std::size_t i = 0; i < names->size(); ++i) {
			const auto& name = (*names)[i];
			if (!ui->IsMenuRegistered(name) || !ui->IsMenuOpen(name)) {
				continue;
			}
			const auto menu = ui->GetMenu(name);
			const auto at = reinterpret_cast<std::uintptr_t>(menu.get());
			std::uint32_t flags = 0;
			std::array<std::uint32_t, 4> words{};
			const bool ok = at && Peek(at + 0xC0, flags) && Peek(at + 0xC4, words);
			REX::INFO("step=menu_detail name={} menu={} {}", kKnownMenus[i], Hex(at),
				ok ? std::format("flags={} c4={} c8={} cc={} d0={}", Hex(flags), Hex(words[0]), Hex(words[1]), Hex(words[2]), Hex(words[3])) :
				     std::string("unreadable"));
		}
	}

	// pause state and who holds input, on whichever thread calls it (a_main: the main thread, where menus= is read)
	void Snapshot(std::string_view a_tag, bool a_main = false)
	{
		const auto n = ++g_snapshots;
		const auto paused = ReadPaused();
		const auto menus = a_main ? ReadMenus() : "-";
		const auto contexts = ReadContexts();
		REX::INFO("step=snapshot n={} tag={} paused={} menus={} contexts={} expected_open={}", n, a_tag, paused, menus,
			contexts, g_expectOpen.load());
		if (a_main && a_tag == "key") {
			LogOpenMenuDetails();
		}
	}

	bool ReadPosition(std::array<float, 3>& a_xyz)
	{
		return CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk) &&
		       Peek(Singleton(kPlayerSingleton) + kPositionAt, a_xyz);
	}

	// ------------------------------------------------------------------------------------------- stage c: the channel
	// our movie's ActionScript 3 root, checked once per movie: the pointer at +0x18 of the movie is a
	// GFx::AS3::MovieRoot by RTTI, and its slots 0x30 and 0x32 are inside the image. The movie's own type is logged.
	RE::Scaleform::GFx::ASMovieRootBase* RootOf(const void* a_menu)
	{
		const auto movie = reinterpret_cast<std::uintptr_t>(MovieOf(a_menu));
		if (!movie || g_channelOff) {
			return nullptr;
		}
		std::uintptr_t root = 0;
		if (g_checkedMovie != MovieOf(a_menu)) {
			ObjectType movieType;
			ObjectType rootType;
			std::uintptr_t vt = 0;
			const bool movieKnown = TypeOf(movie, movieType);
			if (!Peek(movie + kMovieRootAt, root) || !TypeOf(root, rootType) || rootType.descriptor != Address(kMovieRootRtti)) {
				g_channelOff = true;
				Refuse("channel", std::format("what=movie_root movie={} movie_type={} root={} root_type={}", Hex(movie),
					movieKnown ? movieType.name : "unreadable", Hex(root), rootType.name.empty() ? "unreadable" : rootType.name));
				return nullptr;
			}
			Peek(root, vt);
			const auto* slot = reinterpret_cast<const std::uintptr_t*>(vt);
			if (!InImage(vt, (kGetVariableSlot + 1) * 8) || !InImage(slot[kCreateObjectSlot], 1) || !InImage(slot[kCreateFunctionSlot], 1) || !InImage(slot[kGetVariableSlot], 1)) {
				g_channelOff = true;
				Refuse("channel", std::format("what=root_slots root={} vtable={}", Hex(root), Hex(vt)));
				return nullptr;
			}
			REX::INFO("step=movie_root movie={} movie_type={} root={} root_type={} root_offset={} create_object={} create_function={} get_variable={}",
				Hex(movie), movieKnown ? movieType.name : "unreadable", Hex(root), rootType.name, Hex(rootType.offset),
				Hex(slot[kCreateObjectSlot] - g_base), Hex(slot[kCreateFunctionSlot] - g_base), Hex(slot[kGetVariableSlot] - g_base));
			g_checkedMovie = MovieOf(a_menu);
		} else {
			Peek(movie + kMovieRootAt, root);
		}
		return reinterpret_cast<RE::Scaleform::GFx::ASMovieRootBase*>(root);
	}

	int TypeCode(const RE::Scaleform::GFx::Value& a_value) { return static_cast<int>(a_value.GetType()); }

	// the root's child of that instance name (getChildByName, an ActionScript 3 DisplayObjectContainer method)
	bool ChildOf(RE::Scaleform::GFx::Value& a_root, const char* a_name, RE::Scaleform::GFx::Value& a_out)
	{
		const RE::Scaleform::GFx::Value name(a_name);
		return a_root.Invoke("getChildByName", &a_out, &name, 1) && a_out.IsObject();
	}

	// ------------------------------------------------------------------------------------------- stage c: click to quest
	// FAL-246, main thread only. The script VM: the GameVM singleton is a GameVM (RTTI, offset 0, once), the VM it holds a
	// BSScript::Internal::VirtualMachine (RTTI at offset 0: IVirtualMachine is its first base), and its vtable's slots up
	// to DispatchStaticCall's are inside the image. nullptr while there is none (logged) or after a refusal
	RE::BSScript::IVirtualMachine* ScriptVm()
	{
		if (g_vmOff || !CheckSingleton("GameVM", kGameVmSingleton, kGameVmRtti, g_gameVmOk)) {
			return nullptr;
		}
		std::uintptr_t vm = 0;
		if (!Peek(Singleton(kGameVmSingleton) + kGameVmImplAt, vm) || !vm) {
			REX::INFO("step=object name=VirtualMachine result=null");
			return nullptr;
		}
		if (vm != g_checkedVm) {
			ObjectType     type;
			std::uintptr_t vt = 0;
			const bool     known = TypeOf(vm, type) && Peek(vm, vt);
			if (!known || type.descriptor != Address(kVmRtti) || type.offset != 0 ||
				!InImage(vt, (kDispatchStaticCallSlot + 1) * 8)) {
				g_vmOff = true;
				Refuse("object", std::format("name=VirtualMachine object={} type={} offset={} vtable={} (no click reaches a script)",
					Hex(vm), known ? type.name : "unreadable", Hex(type.offset), Hex(vt)));
				return nullptr;
			}
			const auto* slot = reinterpret_cast<const std::uintptr_t*>(vt);
			for (std::size_t i = 0; i <= kDispatchStaticCallSlot; ++i) {
				if (!InImage(slot[i], 1)) {
					g_vmOff = true;
					Refuse("object", std::format("name=VirtualMachine vtable={} slot={} reason=outside_image", Hex(vt), Hex(i)));
					return nullptr;
				}
			}
			g_checkedVm = vm;
			REX::INFO("step=object name=VirtualMachine object={} type={} dispatch_static_call={}", Hex(vm), type.name,
				Hex(slot[kDispatchStaticCallSlot] - g_base));
		}
		return reinterpret_cast<RE::BSScript::IVirtualMachine*>(vm);
	}

	// after click n: the VM queues one call of the ClickCall function and runs it on its own schedule; that function's
	// own log line says when it ran
	void DispatchClick(std::uint32_t a_n)
	{
		auto* const vm = ScriptVm();
		if (!vm) {
			REX::INFO("step=dispatch n={} call={}.{} result=no_vm", a_n, g_clickScript, g_clickFunction);
			return;
		}
		const RE::BSFixedString                                        script(g_clickScript.c_str());
		const RE::BSFixedString                                        function(g_clickFunction.c_str());
		const RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> noCallback{};
		// no arguments: growing the array would call ScrapHeap::Allocate, REL::ID{ 0 } in libxse 9d090c4
		const auto noArguments = [](RE::BSScrapArray<RE::BSScript::Variable>&) { return true; };
		const bool queued = vm->DispatchStaticCall(script, function, noArguments, noCallback, 0);
		REX::INFO("step=dispatch n={} call={}.{} queued={}", a_n, g_clickScript, g_clickFunction, queued ? 1 : 0);
	}

	// the button's click handler: Scaleform calls it from the movie. Static and never released by us: the movie holds
	// its own references (Scaleform's count at +0x08) on top of ours, so the count never reaches zero
	class ClickHandler final : public RE::Scaleform::GFx::FunctionHandler
	{
	public:
		void Call(const Params& a_params) override
		{
			const auto n = ++g_clicks;
			REX::INFO("step=click n={} args={} movie={}", n, a_params.argCount, Hex(reinterpret_cast<std::uintptr_t>(a_params.movie)));
			if (!g_clickScript.empty()) {   // FAL-246: on to the script VM, from the main thread
				g_task->AddTask([n]() { DispatchClick(n); });
			}
		}
	};
	ClickHandler g_clickHandler;

	// once per movie, at kShow: our function as the button's "click" listener
	void ChannelListen(const void* a_menu)
	{
		auto* const root = RootOf(a_menu);
		const auto  movie = MovieOf(a_menu);
		if (!root || g_listenedMovie == movie) {
			return;
		}
		g_listenedMovie = movie;
		RE::Scaleform::GFx::Value top;
		RE::Scaleform::GFx::Value button;
		RE::Scaleform::GFx::Value function;
		const bool gotRoot = root->GetVariable(&top, "root") && top.IsObject();
		const bool gotButton = gotRoot && ChildOf(top, kButtonName, button);
		bool       added = false;
		if (gotButton) {
			root->CreateFunction(&function, &g_clickHandler);
			if (!function.IsUndefined()) {
				std::array<RE::Scaleform::GFx::Value, 2> args;
				args[0] = "click";
				args[1] = function;
				added = button.Invoke("addEventListener", nullptr, args.data(), args.size());
			}
		}
		REX::INFO("step=listen root={} button={} function_type={} added={} event=click", gotRoot ? 1 : 0, gotButton ? 1 : 0,
			TypeCode(function), added ? 1 : 0);
	}

	// at kShow and every kUpdate: the player's position into the field, then read back
	void ChannelWrite(const void* a_menu, std::uint32_t a_n)
	{
		auto* const root = RootOf(a_menu);
		if (!root) {
			return;
		}
		std::array<float, 3> xyz{};
		const bool  havePosition = ReadPosition(xyz) && std::isfinite(xyz[0]) && std::isfinite(xyz[1]) && std::isfinite(xyz[2]);
		const auto  clicks = g_clicks.load();
		const auto  text = havePosition ? std::format("X {:.1f} Y {:.1f} Z {:.1f} CLICKS {}", xyz[0], xyz[1], xyz[2], clicks) :
		                                  std::format("NO POSITION CLICKS {}", clicks);
		RE::Scaleform::GFx::Value top;
		RE::Scaleform::GFx::Value field;
		RE::Scaleform::GFx::Value back;
		const bool gotRoot = root->GetVariable(&top, "root") && top.IsObject();
		const bool gotField = gotRoot && ChildOf(top, kFieldName, field);
		const bool set = gotField && field.SetMember("text", RE::Scaleform::GFx::Value(text.c_str()));
		const bool got = gotField && field.GetMember("text", &back) && back.IsString();
		const std::string read = got ? back.GetString() : "";
		if (a_n <= 20 || a_n % 20 == 0 || read != text) {
			REX::INFO("step=field n={} root={} field={} set={} read_back={} match={} text=\"{}\" read=\"{}\"", a_n,
				gotRoot ? 1 : 0, gotField ? 1 : 0, set ? 1 : 0, got ? 1 : 0, read == text ? "yes" : "no", text, read);
		}
	}

	std::uint32_t FlagSetIndex(std::uint32_t a_n) { return g_flagSetCount ? (a_n - 1) % static_cast<std::uint32_t>(g_flagSetCount) : 0; }
	std::uint32_t FlagSet(std::uint32_t a_n) { return g_flagSetCount ? g_flagSets[FlagSetIndex(a_n)] : 0; }

	// at kShow, before the engine handles it: the constructor's flags | Flags | this open's FlagSets entry
	void ApplyFlagSet(void* a_self, std::uint32_t a_show)
	{
		auto*      imenu = static_cast<RE::IMenu*>(a_self);
		const auto had = imenu->flags;
		const auto want = g_ctorFlags.load() | g_flags | FlagSet(a_show);
		if (had != want) {
			imenu->flags = want;
			imenu->flagsUpdated = true;
		}
		REX::INFO("step=flags show={} set={} had={} now={}", a_show, FlagSetIndex(a_show), Hex(had), Hex(imenu->flags));
	}

	// ------------------------------------------------------------------------------------------- stage d: the page
	// Up to PageCollect, everything runs on the main thread (SFSE's task, before each kShow and kUpdate): the reads,
	// the two calls into the game (LookupByID, GetActorValue) and the text. PageWrite and the click handlers run on the
	// menu's.

	bool SameText(std::string_view a_left, std::string_view a_right)   // ASCII, either case
	{
		return a_left.size() == a_right.size() &&
		       std::equal(a_left.begin(), a_left.end(), a_right.begin(), [](char a_l, char a_r) {
				   return std::toupper(static_cast<unsigned char>(a_l)) == std::toupper(static_cast<unsigned char>(a_r));
			   });
	}

	// a line as the page's font draws it: upper case, a character the font lacks as "?", at most kPageColumns
	std::string PageText(std::string_view a_text)
	{
		std::string out;
		for (const char c : a_text.substr(0, kPageColumns)) {
			const auto up = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
			out += kPageChars.find(up) != std::string_view::npos ? up : '?';
		}
		return out;
	}

	// a page value that could not be read: "?", and its reason logged once per kind
	std::string Unknown(std::string_view a_what, const std::string& a_why)
	{
		static std::set<std::string, std::less<>> noted;
		if (noted.emplace(a_what).second) {
			REX::INFO("step=page_unknown what={} {}", a_what, a_why);
		}
		return "?";
	}

	// the characters of a BSStringPool entry (libxse BSStringPool::Entry: 0x18 bytes, then the characters; an external
	// entry, flag 0x02 at +0x14, points on at +0x08; the last one's length is at +0x08). An entry of 0 is "". False if
	// a read faults or the chain is longer than four
	bool ReadPoolString(std::uintptr_t a_entry, std::string& a_out)
	{
		a_out.clear();
		for (int hop = 0; a_entry; ++hop) {
			std::uint8_t flags = 0;
			if (hop == 4 || !Peek(a_entry + 0x14, flags)) {
				return false;
			}
			if (!(flags & 0x02)) {
				break;
			}
			if (!Peek(a_entry + 0x08, a_entry)) {
				return false;
			}
		}
		if (!a_entry) {
			return true;
		}
		std::uint32_t          length = 0;
		std::array<char, 128>  text{};
		if (!Peek(a_entry + 0x08, length)) {
			return false;
		}
		const auto n = std::min<std::size_t>(length, text.size());
		if (n && !Peek(a_entry + 0x18, text.data(), n)) {
			return false;
		}
		a_out.assign(text.data(), std::find(text.data(), text.data() + n, '\0'));
		return true;
	}

	static_assert(sizeof(RE::BSFixedString) == sizeof(std::uintptr_t));   // the pool entry pointer alone

	// the string reader on a string of ours before any of the game's: our menu name, as the engine's pool holds it
	bool CheckStrings()
	{
		std::string read;
		const auto  entry = *reinterpret_cast<const std::uintptr_t*>(&MenuName());
		if (!ReadPoolString(entry, read) || !SameText(read, kMenuName)) {
			return Refuse("page", std::format("what=strings entry={} read=\"{}\" (no names, no form lists)", Hex(entry),
				PageText(read)));
		}
		REX::INFO("step=page_strings self_test=ok read=\"{}\"", read);
		return true;
	}

	// the object is a complete a_tail (".?AV" or ".?AU" + tail) by its RTTI
	bool IsType(std::uintptr_t a_object, std::string_view a_tail, ObjectType& a_type)
	{
		return a_object && TypeOf(a_object, a_type) && NameIs(a_type.name, a_tail) && a_type.offset == 0;
	}

	// the offset of the base class a_tail inside the complete type, from its RTTI class hierarchy descriptor (+0x08
	// the count, +0x0C the base class array; each base class descriptor: +0x00 its type descriptor, +0x08 mdisp, +0x0C
	// pdisp). None if the base is absent, virtual (pdisp not -1) or listed more than once
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

	// a plugin file's complete type: TESFile, or a type with TESFile as its base at +0. The data handler's file lists
	// hold TESPackedFile objects (FAL-437: the PC read every loaded file's vtable at RVA 0x4b29b80, RTTI
	// TESPackedFile, its bases itself and TESFile, both at +0), which a plain IsType(file, "TESFile@@") refuses
	bool IsFileType(const ObjectType& a_type)
	{
		return a_type.offset == 0 && (NameIs(a_type.name, "TESFile@@") || BaseOffset(a_type, "TESFile@@") == 0u);
	}

	// the subobject at a_offset is a base of the object's complete type: its vtable's locator names that same
	// complete type at that offset
	bool CheckSubobject(std::uintptr_t a_object, const ObjectType& a_type, std::uint32_t a_offset)
	{
		ObjectType sub;
		return TypeOf(a_object + a_offset, sub) && sub.descriptor == a_type.descriptor && sub.offset == a_offset;
	}

	// the target of an adjustor thunk, rcx moved down by a_adjust (sub rcx, imm; add rcx, -imm; or lea rcx,
	// [rcx-imm]) then jmp rel32: what MSVC puts in a secondary base's vtable for a virtual the complete class
	// overrides. 0 if the code is not one
	std::uintptr_t ThunkTarget(std::uintptr_t a_code, std::uint32_t a_adjust)
	{
		if (!InImage(a_code, 12)) {
			return 0;
		}
		const auto* code = reinterpret_cast<const std::uint8_t*>(a_code);
		const auto  imm8 = static_cast<std::int8_t>(code[3]);
		std::int32_t imm32;
		std::memcpy(&imm32, code + 3, sizeof imm32);
		const auto  adjust = static_cast<std::int64_t>(a_adjust);
		std::size_t at = 0;
		if (code[0] != 0x48) {
			return 0;
		} else if ((code[1] == 0x83 && code[2] == 0xE9 && imm8 == adjust) || (code[1] == 0x83 && code[2] == 0xC1 && imm8 == -adjust) ||
				   (code[1] == 0x8D && code[2] == 0x49 && imm8 == -adjust)) {
			at = 4;
		} else if ((code[1] == 0x81 && code[2] == 0xE9 && imm32 == adjust) || (code[1] == 0x81 && code[2] == 0xC1 && imm32 == -adjust) ||
				   (code[1] == 0x8D && code[2] == 0x89 && imm32 == -adjust)) {
			at = 7;
		} else {
			return 0;
		}
		if (code[at] != 0xE9) {
			return 0;
		}
		std::int32_t rel;
		std::memcpy(&rel, code + at + 1, sizeof rel);
		return a_code + at + 5 + static_cast<std::intptr_t>(rel);
	}

	struct PageForms
	{
		bool           scanned = false;
		bool           strings = false;    // ReadPoolString read our menu name back
		bool           avifs = false;      // the actor values were looked up: a name not found is not installed
		bool           globals = false;    // the globals were looked up
		std::uintptr_t health = 0;         // ActorValueInfo forms
		std::uintptr_t carryWeight = 0;
		std::uintptr_t experience = 0;
		std::uintptr_t rads = 0;
		std::uintptr_t gameHour = 0;       // TESGlobal forms
		std::uintptr_t gameDaysPassed = 0;
		std::size_t    globalValueAt = 0;  // the TESGlobal value's offset, once FindGlobalValue found it (0: not yet)
		bool           globalBytes = false;  // the globals' bytes were logged
		std::uint32_t  ownerOffset = 0;    // ActorValueOwner inside PlayerCharacter
		std::uintptr_t ownerVtable = 0;
		std::uintptr_t getActorValue = 0;  // its checked GetActorValue slot
	};
	PageForms g_forms;   // main thread only

	struct Want
	{
		std::string_view editorId;
		std::uintptr_t*  form;
	};

	// the data handler (its id is SFSE's own address, CheckPageIds), a TESDataHandler by its RTTI; only its form-list
	// memory is logged
	std::uintptr_t DataHandler()
	{
		const auto handler = Singleton(kDataHandlerSingleton);
		ObjectType type;
		if (!IsType(handler, "TESDataHandler@@", type)) {
			Refuse("object", std::format("name=TESDataHandler object={} type={} offset={} (the page's form lists stay unread)",
				Hex(handler), type.name.empty() ? "unreadable" : type.name, Hex(type.offset)));
			return 0;
		}
		REX::INFO("step=object name=TESDataHandler object={} type={}", Hex(handler), type.name);
		return handler;
	}

	// the data handler's form lists as raw memory, once: at 5a4e6016 the size read at +0x70 + type x 0x18 + 0x08 was 0
	// for AVIF and GLOB, so the next run logs the three qwords of every entry that is not all zero (the first 48) and
	// of those two types, to settle the layout. Reads only, guarded
	void LogFormArrays(std::uintptr_t a_handler)
	{
		std::array<std::uint64_t, 3> avif{};
		std::array<std::uint64_t, 3> glob{};
		std::string                  nonzero;
		std::size_t                  count = 0;
		for (std::size_t i = 0; i < kFormArrayEntries; ++i) {
			std::array<std::uint64_t, 3> q{};
			if (!Peek(a_handler + kFormArraysAt + i * kFormArrayBytes, q)) {
				nonzero += std::format(" {:#x}:fault", i);
				break;
			}
			if (i == kAvifType) {
				avif = q;
			}
			if (i == kGlobType) {
				glob = q;
			}
			if ((q[0] || q[1] || q[2]) && count++ < 48) {
				nonzero += std::format(" {:#x}:{:x}/{:x}/{:x}", i, q[0], q[1], q[2]);
			}
		}
		REX::INFO("step=page_form_arrays avif={:x}/{:x}/{:x} glob={:x}/{:x}/{:x} nonzero_count={}{}", avif[0], avif[1],
			avif[2], glob[0], glob[1], glob[2], count, nonzero);
	}

	using LookupById_t = void* (*)(std::uint32_t);

	// a form by its form id, through the engine's own lookup (libxse TESForm::LookupByID and SFSE 0.2.21
	// GetFormByNumericID: the same address, CheckPageIds, and the same TESForm* (u32) declaration); main thread only
	std::uintptr_t FormById(std::uint32_t a_formId)
	{
		return reinterpret_cast<std::uintptr_t>(reinterpret_cast<LookupById_t>(Address(kLookupById))(a_formId));
	}

	// the editor ID of a form of type a_type by its RTTI (a BSFixedString at a_editorIdAt), or "" if the form is not
	// that type or its name does not read
	std::string EditorIdOf(std::uintptr_t a_form, std::string_view a_type, std::size_t a_editorIdAt)
	{
		ObjectType     type;
		std::uintptr_t entry = 0;
		std::string    id;
		if (!IsType(a_form, a_type, type) || !Peek(a_form + a_editorIdAt, entry) || !ReadPoolString(entry, id)) {
			return {};
		}
		return id;
	}

	// a Want gets the form if its editor ID is the Want's name and it has none yet
	template <std::size_t N>
	void Match(std::array<Want, N>& a_want, std::uintptr_t a_form, std::string_view a_editorId)
	{
		for (auto& want : a_want) {
			if (!*want.form && SameText(a_editorId, want.editorId)) {
				*want.form = a_form;
			}
		}
	}

	// a form by its fixed form id, accepted by its RTTI type alone (at 3eb30d71 the editor-ID check passed Health 0x2D4
	// and not 0x2C9, 0x2DC, 0x38 or 0x39): what the lookup gave is logged in full, its type name, the four bytes at
	// +0x2C (the form type byte among them) and the editor ID as read
	std::string AcceptById(std::uint32_t a_id, std::string_view a_name, std::string_view a_type, std::size_t a_editorIdAt,
		std::uintptr_t& a_out)
	{
		const auto     form = FormById(a_id);
		ObjectType     type;
		std::uintptr_t entry = 0;
		std::string    name;
		std::uint32_t  bytes = 0;
		if (IsType(form, a_type, type)) {
			a_out = form;
			if (Peek(form + a_editorIdAt, entry)) {
				ReadPoolString(entry, name);
			}
		}
		if (form) {
			Peek(form + 0x2C, bytes);
		}
		return std::format("{}:{:x}:form={}:type={}:bytes2c={:08x}:name={}:{}", a_name, a_id, form ? 1 : 0,
			type.name.empty() ? "unreadable" : type.name, bytes, name.empty() ? "-" : name, a_out ? "used" : "refused");
	}

	// the page's forms by form id: the globals and actor values by their fixed ids and RTTI type (AcceptById); every
	// ActorValueInfo among Starfield.esm's ids 0x001 to 0xFFF listed with its editor ID as read, once; FO4SF_Rads by its
	// FO4SF_Rads is owned by FO4SFCoreValues.esm at local id 0x800; scan 0x800 of each full (01..FD) and light (FE000..FEFFF) plugin and log the resolved id
	void FindForms()
	{
		std::string known = AcceptById(kGameHourId, "GameHour", "TESGlobal@@", kGlobalEditorIdAt, g_forms.gameHour);
		known += " " + AcceptById(kGameDaysPassedId, "GameDaysPassed", "TESGlobal@@", kGlobalEditorIdAt, g_forms.gameDaysPassed);
		known += " " + AcceptById(kHealthId, "Health", "ActorValueInfo@@", kAvifEditorIdAt, g_forms.health);
		known += " " + AcceptById(kCarryWeightId, "CarryWeight", "ActorValueInfo@@", kAvifEditorIdAt, g_forms.carryWeight);
		known += " " + AcceptById(kExperienceId, "Experience", "ActorValueInfo@@", kAvifEditorIdAt, g_forms.experience);
		g_forms.globals = true;
		std::uint32_t typed = 0;
		std::string   avifs;
		for (std::uint32_t id = 1; id < kCoreFormIds; ++id) {
			const auto form = FormById(id);
			ObjectType type;
			if (!form || !IsType(form, "ActorValueInfo@@", type)) {
				continue;
			}
			++typed;
			const auto name = EditorIdOf(form, "ActorValueInfo@@", kAvifEditorIdAt);
			if (avifs.size() < 2000) {
				avifs += std::format("{}{:x}={}", avifs.empty() ? "" : ",", id, name.empty() ? "-" : name);
			}
		}
		std::array<Want, 1> rads{ { { "FO4SF_Rads", &g_forms.rads } } };
		std::uint32_t       radsId = 0;
		for (std::uint32_t i = 0; i < 0xFD + 0x1000 && !g_forms.rads; ++i) {
			const auto id = i < 0xFD ? ((i + 1) << 24) | kRadsLocalId : 0xFE000000u | ((i - 0xFD) << 12) | kRadsLocalId;
			const auto form = FormById(id);
			if (form) {
				Match(rads, form, EditorIdOf(form, "ActorValueInfo@@", kAvifEditorIdAt));
				radsId = g_forms.rads ? id : 0;
			}
		}
		g_forms.avifs = typed > 0;
		REX::INFO("step=page_forms lookup=by_form_id known={} avif_typed={} rads={} avif_ids={}", known, typed,
			g_forms.rads ? std::format("{:08X}", radsId) : "not_installed", avifs.empty() ? "none" : avifs);
	}

	// the player's ActorValueOwner and its GetActorValue slot: the base's offset from PlayerCharacter's RTTI
	// hierarchy, its vtable's locator naming PlayerCharacter at that offset, and slot 0x00 the adjustor thunk to the
	// player's own slot 0x00, its destructor. Then GetActorValue is slot 0x01, libxse's declaration (SFSE 0.2.21
	// declares no destructor and would put it at 0x00). Anything else: no actor values on the page
	bool CheckActorValues()
	{
		ObjectType type;
		const auto player = Singleton(kPlayerSingleton);
		if (!CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk) || !TypeOf(player, type)) {
			return false;
		}
		const auto     at = BaseOffset(type, "ActorValueOwner@@");
		std::uintptr_t primary = 0;
		std::uintptr_t owner = 0;
		if (!at || !CheckSubobject(player, type, *at) || !Peek(player, primary) || !Peek(player + *at, owner) ||
			!InImage(primary, 8) || !InImage(owner, 2 * 8)) {
			return Refuse("page", std::format("what=actor_value_owner offset={} (no actor values)", at ? Hex(*at) : "none"));
		}
		const auto* slots = reinterpret_cast<const std::uintptr_t*>(owner);
		const auto  destructor = *reinterpret_cast<const std::uintptr_t*>(primary);
		const auto  target0 = ThunkTarget(slots[0], *at);
		const auto  target1 = ThunkTarget(slots[1], *at);
		const auto  rva = [](std::uintptr_t a_addr) { return InImage(a_addr, 1) ? Hex(a_addr - g_base) : Hex(a_addr); };
		if (target0 != destructor || !InImage(slots[1], 1)) {
			return Refuse("page", std::format("what=get_actor_value offset={} slot0={} target0={} slot1={} target1={} "
				"destructor={} (no actor values)", Hex(*at), rva(slots[0]), rva(target0), rva(slots[1]), rva(target1),
				rva(destructor)));
		}
		g_forms.ownerOffset = *at;
		g_forms.ownerVtable = owner;
		g_forms.getActorValue = slots[1];
		REX::INFO("step=page_actor_values owner_offset={} destructor_slot=0x00 get_actor_value_slot=0x01 slot={} target={}",
			Hex(*at), rva(slots[1]), rva(target1));
		return true;
	}

	// once a player exists: the string reader, the actor-value slot, the form-list layout and the forms, each logged once
	void PageScan()
	{
		if (g_forms.scanned || !Singleton(kPlayerSingleton)) {
			return;
		}
		g_forms.scanned = true;
		g_forms.strings = CheckStrings();
		CheckActorValues();
		if (const auto handler = DataHandler()) {
			LogFormArrays(handler);
		}
		if (g_forms.strings) {
			FindForms();
		}
	}

	using GetActorValue_t = float (*)(void*, const void*);

	// the player's value of an actor value, as a whole number: the engine's GetActorValue (the slot CheckActorValues
	// checked, called only while the player's ActorValueOwner vtable is still the checked one), or "?"
	std::string ActorValueText(std::string_view a_what, std::uintptr_t a_info)
	{
		if (!a_info) {
			return Unknown(a_what, std::format("reason={}", g_forms.avifs ? "no_such_actor_value" : "actor_values_unread"));
		}
		const auto     player = Singleton(kPlayerSingleton);
		std::uintptr_t vtable = 0;
		if (!g_forms.getActorValue || !player || !Peek(player + g_forms.ownerOffset, vtable) || vtable != g_forms.ownerVtable) {
			return Unknown(a_what, "reason=no_get_actor_value");
		}
		const auto value = reinterpret_cast<GetActorValue_t>(g_forms.getActorValue)(
			reinterpret_cast<void*>(player + g_forms.ownerOffset), reinterpret_cast<const void*>(a_info));
		return std::isfinite(value) ? std::format("{:.0f}", value) : Unknown(a_what, "reason=not_finite");
	}

	// the player's level: the base TESNPC's TESActorBaseData (its offset from the RTTI hierarchy), ACTOR_BASE_DATA::level
	std::string LevelText()
	{
		const auto     player = Singleton(kPlayerSingleton);
		std::uintptr_t base = 0;
		ObjectType     type;
		std::uint16_t  level = 0;
		if (g_playerOk != 1 || !Peek(player + kBaseObjectAt, base) || !IsType(base, "TESNPC@@", type)) {
			return Unknown("level", std::format("reason=base base={} type={}", Hex(base), type.name.empty() ? "unreadable" : type.name));
		}
		const auto at = BaseOffset(type, "TESActorBaseData@@");
		if (!at || !CheckSubobject(base, type, *at) || !Peek(base + *at + kLevelAt, level)) {
			return Unknown("level", std::format("reason=actor_base_data offset={}", at ? Hex(*at) : "none"));
		}
		return std::to_string(level);
	}

	// a form's name, read through its TESFullName base (offset from the RTTI hierarchy, checked like the player's), and
	// its form id: "NAME (0001ABCD)", "NO NAME (...)" when it has none
	std::string NameText(std::string_view a_what, std::uintptr_t a_form, const ObjectType& a_type)
	{
		const auto     at = BaseOffset(a_type, "TESFullName@@");
		std::uintptr_t entry = 0;
		std::uint32_t  formId = 0;
		std::string    name;
		Peek(a_form + kFormIdAt, formId);
		if (!at || !CheckSubobject(a_form, a_type, *at) || !Peek(a_form + *at + kFullNameAt, entry) || !ReadPoolString(entry, name)) {
			return std::format("{} ({:08X})", Unknown(a_what, std::format("reason=full_name offset={}", at ? Hex(*at) : "none")), formId);
		}
		return std::format("{} ({:08X})", name.empty() ? "NO NAME" : name, formId);
	}

	// the player's parent cell and its worldspace ("NONE (INTERIOR)" when it has none)
	std::pair<std::string, std::string> PlaceText()
	{
		const auto     player = Singleton(kPlayerSingleton);
		std::uintptr_t cell = 0;
		std::uintptr_t world = 0;
		ObjectType     cellType;
		ObjectType     worldType;
		if (g_playerOk != 1 || !Peek(player + kParentCellAt, cell) || !IsType(cell, "TESObjectCELL@@", cellType)) {
			return { Unknown("cell", std::format("reason=cell cell={} type={}", Hex(cell),
						 cellType.name.empty() ? "unreadable" : cellType.name)),
				"?" };
		}
		auto cellText = NameText("cell_name", cell, cellType);
		if (!Peek(cell + kCellWorldAt, world)) {
			return { cellText, Unknown("world", "reason=fault") };
		}
		if (!world) {   // FAL-595: 0 at +0x110 indoors, a TESWorldSpace outdoors (the PC, 12 Nov)
			return { cellText, "NONE (INTERIOR)" };
		}
		if (!IsType(world, "TESWorldSpace@@", worldType)) {
			return { cellText, Unknown("world", std::format("reason=type world={} type={}", Hex(world),
								   worldType.name.empty() ? "unreadable" : worldType.name)) };
		}
		return { cellText, NameText("world_name", world, worldType) };
	}

	// GameHour and GameDaysPassed read as floats at one offset: both in range (an hour in [0, 24), a day count above 0
	// and below kMaxDays) and the hour within kGlobalMinutes of the day count's fraction, else false
	bool ReadTime(std::size_t a_at, float& a_hour, float& a_days)
	{
		if (!a_at || !g_forms.gameHour || !g_forms.gameDaysPassed || !Peek(g_forms.gameHour + a_at, a_hour) ||
			!Peek(g_forms.gameDaysPassed + a_at, a_days) || !std::isfinite(a_hour) || !std::isfinite(a_days) ||
			a_hour < 0.0f || a_hour >= 24.0f || a_days <= 0.0f || a_days >= kMaxDays) {
			return false;
		}
		const auto apart = std::fabs(std::fmod(a_days, 1.0f) * 24.0f - a_hour);
		return std::min(apart, 24.0f - apart) * 60.0f <= kGlobalMinutes;
	}

	// the kGlobalBytes (40) bytes of a TESGlobal from kGlobalBytesAt, as hex and as ten floats
	std::string GlobalBytes(std::uintptr_t a_form)
	{
		std::array<std::uint8_t, kGlobalBytes> bytes{};
		if (!a_form || !Peek(a_form + kGlobalBytesAt, bytes.data(), bytes.size())) {
			return "unreadable";
		}
		std::string hex;
		std::string floats;
		for (std::size_t i = 0; i < bytes.size(); i += 4) {
			float value = 0.0f;
			std::memcpy(&value, bytes.data() + i, sizeof(value));
			hex += std::format("{}{:02x}{:02x}{:02x}{:02x}", i ? "," : "", bytes[i], bytes[i + 1], bytes[i + 2],
				bytes[i + 3]);
			floats += std::format("{}{:.4f}", i ? "," : "", value);
		}
		return std::format("hex={} floats={}", hex, floats);
	}

	// which slot of a TESGlobal holds the value, given a_accepts(offset) (ReadTime at that offset): kGlobalValueAt when it
	// passes, else the first other slot from kGlobalSearchFrom to the end of the object that does; never kFormIdAt (the
	// form ids 0x38 and 0x39 read as floats of about zero, and passed). 0 when none does
	template <class Accepts>
	std::size_t ChooseGlobalSlot(Accepts a_accepts)
	{
		if (kGlobalValueAt != kFormIdAt && a_accepts(kGlobalValueAt)) {
			return kGlobalValueAt;
		}
		for (std::size_t at = kGlobalSearchFrom; at + sizeof(float) <= kGlobalObjectBytes; at += 4) {
			if (at != kFormIdAt && at != kGlobalValueAt && a_accepts(at)) {
				return at;
			}
		}
		return 0;
	}

	// the TESGlobal value's offset, chosen by ChooseGlobalSlot over ReadTime on both globals. Tried at each collect until
	// found; both globals' bytes are logged at the first try
	void FindGlobalValue()
	{
		if (g_forms.globalValueAt || !g_forms.gameHour || !g_forms.gameDaysPassed) {
			return;
		}
		if (!g_forms.globalBytes) {
			g_forms.globalBytes = true;
			REX::INFO("step=page_globals from={} game_hour {} game_days_passed {}", Hex(kGlobalBytesAt),
				GlobalBytes(g_forms.gameHour), GlobalBytes(g_forms.gameDaysPassed));
		}
		float hour = 0.0f;
		float days = 0.0f;
		const auto at = ChooseGlobalSlot([&](std::size_t a_at) { return ReadTime(a_at, hour, days); });
		if (at) {
			ReadTime(at, hour, days);   // the chosen slot's values, for the log (the search leaves the last try's)
			g_forms.globalValueAt = at;
			REX::INFO("step=page_globals value_at={} game_hour={:.4f} game_days_passed={:.4f}", Hex(at), hour, days);
		}
	}

	// the game time from the GameHour and GameDaysPassed globals, at the offset FindGlobalValue found: "08:23   DAY 1"
	std::string TimeText()
	{
		float hour = 0.0f;
		float days = 0.0f;
		if (!ReadTime(g_forms.globalValueAt, hour, days)) {
			const auto reason = !g_forms.globals        ? "globals_unread" :
			                    !g_forms.globalValueAt ? "no_value_offset" :
			                                             "out_of_range";
			return Unknown("time", std::format("reason={}", reason));
		}
		const auto minutes = static_cast<int>(hour * 60.0f);
		return std::format("{:02}:{:02}   DAY {}", minutes / 60 % 24, minutes % 60, static_cast<long long>(days) + 1);
	}

	// both tabs' text, on the main thread before each kShow and kUpdate; the menu's thread copies one tab of it
	void PageCollect()
	{
		PageScan();
		FindGlobalValue();
		const auto [cell, world] = PlaceText();
		const auto rads = g_forms.rads ? ActorValueText("rads", g_forms.rads) :
		                  g_forms.avifs ? std::string("NOT INSTALLED") :
		                                  Unknown("rads", "reason=actor_values_unread");
		std::array<float, 3> xyz{};
		float                hour = 0.0f;
		float                days = 0.0f;
		const bool           position = ReadPosition(xyz) && std::isfinite(xyz[0]) && std::isfinite(xyz[1]) && std::isfinite(xyz[2]);
		const bool           haveDays = ReadTime(g_forms.globalValueAt, hour, days);
		const auto           shows = g_shows.load();
		std::array<std::array<std::string, kPageLines + 1>, 2> text{ {
			{ "TAB 1 OF 2: STATUS",
				std::format("HEALTH {}", ActorValueText("health", g_forms.health)),
				std::format("LEVEL {}   XP {}", LevelText(), ActorValueText("experience", g_forms.experience)),
				std::format("CARRY WEIGHT MAX {}", ActorValueText("carry_weight", g_forms.carryWeight)),
				std::format("RADS {}", rads),
				std::format("CELL {}", cell),
				std::format("WORLD {}", world),
				std::format("TIME {}", TimeText()) },
			{ "TAB 2 OF 2: DATA",
				position ? std::format("POSITION X {:.1f} Y {:.1f} Z {:.1f}", xyz[0], xyz[1], xyz[2]) : "POSITION ?",
				std::format("UPDATES {}   (TWO A SECOND)", g_updates.load()),
				std::format("NEXT TAB CLICKS {}   CLOSE CLICKS {}", g_tabClicks.load(), g_closeClicks.load()),
				std::format("OPENS {}   FLAGS {}", shows, Hex(FlagSet(shows ? shows : 1))),
				std::format("GAME PAUSED {}", ReadPaused()),
				std::format("MENUS {}", ReadMenus()),
				haveDays ? std::format("DAYS PASSED {:.4f}", days) : "DAYS PASSED ?" },
		} };
		for (auto& tab : text) {
			for (auto& line : tab) {
				line = PageText(line);
			}
		}
		std::scoped_lock lock(g_pageLock);
		g_pageText = std::move(text);
	}

	// the two buttons' click handlers, called by Scaleform on the menu's thread (static, never released, as the
	// channel's): they only count and raise a flag; the key thread acts on it through the main thread
	class TabHandler final : public RE::Scaleform::GFx::FunctionHandler
	{
	public:
		void Call(const Params& a_params) override
		{
			const auto n = ++g_tabClicks;
			const auto tab = (g_tab.fetch_add(1) + 1) % 2;
			g_refreshNow = true;
			REX::INFO("step=click button=tab n={} args={} tab={}", n, a_params.argCount, tab);
		}
	};
	TabHandler g_tabHandler;

	class CloseHandler final : public RE::Scaleform::GFx::FunctionHandler
	{
	public:
		void Call(const Params& a_params) override
		{
			const auto n = ++g_closeClicks;
			g_closeNow = true;
			REX::INFO("step=click button=close n={} args={}", n, a_params.argCount);
		}
	};
	CloseHandler g_closeHandler;

	// once per movie, at kShow: our two functions as the buttons' "click" listeners
	void PageListen(const void* a_menu)
	{
		auto* const root = RootOf(a_menu);
		const auto  movie = MovieOf(a_menu);
		if (!root || g_listenedMovie == movie) {
			return;
		}
		g_listenedMovie = movie;
		RE::Scaleform::GFx::Value top;
		const bool                gotRoot = root->GetVariable(&top, "root") && top.IsObject();
		const std::array<std::pair<const char*, RE::Scaleform::GFx::FunctionHandler*>, 2> buttons{ {
			{ kTabButtonName, &g_tabHandler }, { kCloseButtonName, &g_closeHandler } } };
		for (const auto& [name, handler] : buttons) {
			RE::Scaleform::GFx::Value button;
			RE::Scaleform::GFx::Value function;
			const bool                gotButton = gotRoot && ChildOf(top, name, button);
			bool                      added = false;
			if (gotButton) {
				root->CreateFunction(&function, handler);
				if (!function.IsUndefined()) {
					std::array<RE::Scaleform::GFx::Value, 2> args;
					args[0] = "click";
					args[1] = function;
					added = button.Invoke("addEventListener", nullptr, args.data(), args.size());
				}
			}
			REX::INFO("step=listen name={} root={} button={} function_type={} added={} event=click", name, gotRoot ? 1 : 0,
				gotButton ? 1 : 0, TypeCode(function), added ? 1 : 0);
		}
	}

	// at kShow and every kUpdate, on the menu's thread: the shown tab's text into the tab line and the seven lines,
	// each read back. Logged for n = 1 to 20, then every 20th, and on the first 20 that do not read back
	void PageWrite(const void* a_menu, std::uint32_t a_update)
	{
		auto* const root = RootOf(a_menu);
		if (!root) {
			return;
		}
		static std::atomic<std::uint32_t>        mismatches{ 0 };
		const auto                               tab = g_tab.load() % 2;
		std::array<std::string, kPageLines + 1> text;
		{
			std::scoped_lock lock(g_pageLock);
			text = g_pageText[tab];
		}
		RE::Scaleform::GFx::Value top;
		const bool                gotRoot = root->GetVariable(&top, "root") && top.IsObject();
		std::size_t               found = 0;
		std::size_t               set = 0;
		std::size_t               match = 0;
		for (std::size_t i = 0; gotRoot && i < text.size(); ++i) {
			const auto                name = i == 0 ? std::string(kTabFieldName) : std::format("{}{}", kLineFieldName, i - 1);
			RE::Scaleform::GFx::Value field;
			RE::Scaleform::GFx::Value back;
			if (!ChildOf(top, name.c_str(), field)) {
				continue;
			}
			++found;
			set += field.SetMember("text", RE::Scaleform::GFx::Value(text[i].c_str())) ? 1 : 0;
			match += field.GetMember("text", &back) && back.IsString() && text[i] == back.GetString() ? 1 : 0;
		}
		const auto n = ++g_pageWrites;
		if (n <= 20 || n % 20 == 0 || (match != text.size() && mismatches++ < 20)) {
			std::string all;
			for (const auto& line : text) {
				all += std::format("{}{}", all.empty() ? "" : " | ", line);
			}
			REX::INFO("step=page n={} update={} tab={} root={} fields={}/{} set={} match={} text=\"{}\"", n, a_update, tab,
				gotRoot ? 1 : 0, found, text.size(), set, match, all);
		}
	}

	// ------------------------------------------------------------------------------------------- stage e: the kit
	// FAL-301. The pages are read once at load (ReadKit) and never change after. KitCollect builds the shown page's
	// screen on the main thread (stage d's reads and its two calls, nothing else); KitWrite writes it on the menu's
	// thread. The state (main tab, each tab's sub-tab, each page's selection and first row on screen) moves on keys (the
	// key thread) and clicks (the menu's thread), always under g_pageLock, and each move asks for an update at once.

	struct KitCell   // a Row= or Footer= line
	{
		std::string label;
		std::string value;   // a value provider: one of kKitValues, or av:<hex>
	};

	struct KitPage
	{
		std::string              tab;
		std::string              sub;
		std::vector<KitCell>     rows;
		std::string              list;     // a list provider, or ""
		std::vector<std::string> notice;
		std::vector<KitCell>     footer;
		std::string              hint;
		std::size_t              line = 0;
	};

	struct KitObjective   // [Kit] MissionObjective=<index>|<path> (FAL-571)
	{
		std::uint16_t            index = 0;   // the objective's number, as the console takes it (10, 85, 86)
		std::vector<std::size_t> path;        // from the quest: a pointer read at each offset but the last, then its state's byte
	};

	struct KitConfig
	{
		std::string                                    title = "FO4SF PIP-BOY";
		std::string                                    header;   // a value provider, or ""
		std::string                                    hints;
		std::string                                    missionFile;   // Mission=: our mission's plugin file, or ""
		std::uint32_t                                  missionId = 0;   // and its form's local id in that file
		std::size_t                                    missionStageAt = 0;   // MissionStageAt=: its stage's u16, or 0 (STAGE ?)
		std::vector<KitObjective>                      objectives;   // MissionObjective=: each objective's state, or none
		std::size_t                                    headingAt = 0;   // HeadingAt=: the player's heading float, or 0 (HEADING ?)
		bool                                           headingTurnsDown = false;   // HeadingAt=-<hex>: it falls turning right
		std::uint32_t                                  gridUnits = 0;   // GridUnits=: a cell's width in game units, or 0 (GRID ?)
		std::vector<KitPage>                           pages;
		std::vector<std::string>                       tabs;     // in the order of their first page
		std::array<std::vector<std::size_t>, kKitTabs> subs;     // each tab's pages, in order
	};
	KitConfig g_kit;   // ReadKit, at load; read only after

	struct KitState
	{
		std::size_t                       tab = 0;
		std::array<std::size_t, kKitTabs> sub{};      // the sub-tab each main tab shows, kept while another tab is shown
		std::vector<std::size_t>          selected;   // per page: the selected row
		std::vector<std::size_t>          top;        // per page: the first row on screen
		std::vector<std::size_t>          count;      // per page: its selectable rows, as last collected
		std::uint32_t                     keys = 0;   // moves by key and by click (the kit_test list shows them)
		std::uint32_t                     clicks = 0;
	};

	struct KitScreen
	{
		std::size_t                          page = 0;
		std::string                          title;
		std::string                          header;
		std::string                          hints;
		std::array<std::string, kKitTabs>    tabs;
		std::size_t                          tab = 0;
		std::array<std::string, kKitSubs>    subs;
		std::size_t                          sub = 0;
		std::array<std::string, kKitRows>    names;
		std::array<std::string, kKitRows>    values;
		std::optional<std::size_t>           bar;      // the selected row's place on screen, none on a notice
		std::array<std::string, kKitRows>    infoLabels;
		std::array<std::string, kKitRows>    infoValues;
		std::array<std::string, kKitFooter>  footer;
		bool                                 moreUp = false;
		bool                                 moreDown = false;
	};

	struct KitRow
	{
		std::string                                      name;
		std::string                                      value;
		std::vector<std::pair<std::string, std::string>> info;   // the value rows beside the list while it is selected
	};

	enum class KitMove : std::size_t { kUp, kDown, kPrevSub, kNextSub, kPrevTab, kNextTab, kTab, kSub, kRow };
	constexpr std::array<std::string_view, 9> kKitMoveNames{ "up", "down", "prev_sub", "next_sub", "prev_tab", "next_tab",
		"tab", "sub", "row" };

	struct KitKey   // INI KitUp ... KitNextTab
	{
		KitMove                      move;
		const wchar_t*               ini;
		const wchar_t*               keys;   // the default
		std::array<std::uint32_t, 3> vk{};
		std::size_t                  count = 0;
	};
	std::array<KitKey, 6> g_kitKeys{ { { KitMove::kUp, L"KitUp", L"0x26,0x57" }, { KitMove::kDown, L"KitDown", L"0x28,0x53" },
		{ KitMove::kPrevSub, L"KitPrevSub", L"0x25,0x41" }, { KitMove::kNextSub, L"KitNextSub", L"0x27,0x44" },
		{ KitMove::kPrevTab, L"KitPrevTab", L"0x51" }, { KitMove::kNextTab, L"KitNextTab", L"0x45" } } };

	KitState                                     g_kitState;        // under g_pageLock
	KitScreen                                    g_kitScreen;       // under g_pageLock: built on the main thread
	bool                                         g_kitCollected = false;   // under g_pageLock
	std::vector<bool>                            g_kitPageLogged;   // main thread only
	std::unordered_map<std::uint32_t, std::uintptr_t> g_kitActorValues;   // main thread only: av:<id>'s form, once
	std::uintptr_t                               g_kitQuest = 0;    // main thread only: the mission KitQuestRows last accepted
	std::unordered_map<std::string, std::string> g_kitTexts;        // menu's thread only: each field as last set and read
	std::unordered_map<std::string, bool>        g_kitShown;        // menu's thread only: each object's visible, likewise
	std::atomic<std::uint32_t>                   g_kitWrites{ 0 };
	std::atomic<std::uint32_t>                   g_kitClicks{ 0 };

	std::string_view KitTrim(std::string_view a_text)
	{
		const auto first = a_text.find_first_not_of(" \t\r");
		if (first == std::string_view::npos) {
			return {};
		}
		return a_text.substr(first, a_text.find_last_not_of(" \t\r") - first + 1);
	}

	// ReadKit's label check, parse_kit's _fits: 1 to a_columns characters, each in the kit's font (upper case)
	bool KitLabel(std::string_view a_text, std::size_t a_columns)
	{
		return !a_text.empty() && a_text.size() <= a_columns &&
		       std::ranges::all_of(a_text, [](char a_c) { return kKitChars.find(a_c) != std::string_view::npos; });
	}

	// parse_kit's check_value: a name of kKitValues, or av:<1 to 8 hex digits, not zero>
	bool KitValueName(std::string_view a_spec)
	{
		if (std::ranges::find(kKitValues, a_spec) != kKitValues.end()) {
			return true;
		}
		if (!a_spec.starts_with(kKitActorValue)) {
			return false;
		}
		const auto hex = a_spec.substr(kKitActorValue.size());
		return !hex.empty() && hex.size() <= 8 &&
		       std::ranges::all_of(hex, [](char a_c) { return std::isxdigit(static_cast<unsigned char>(a_c)) != 0; }) &&
		       std::strtoul(std::string(hex).c_str(), nullptr, 16) != 0;
	}

	// <label>|<value>, parse_kit's _cell: exactly one '|', the label in a_columns, the value a value provider
	bool KitCellOf(std::string_view a_text, std::size_t a_columns, KitCell& a_out)
	{
		const auto bar = a_text.find('|');
		if (bar == std::string_view::npos || a_text.find('|', bar + 1) != std::string_view::npos) {
			return false;
		}
		const auto label = KitTrim(a_text.substr(0, bar));
		const auto value = KitTrim(a_text.substr(bar + 1));
		if (!KitLabel(label, a_columns) || !KitValueName(value)) {
			return false;
		}
		a_out = { std::string(label), std::string(value) };
		return true;
	}

	// parse_kit's check_mission: <plugin file>|<local id, 1 to 6 hex digits, not zero>; the file 1 to 64 characters
	// (letters, digits, space _ - .) ending .esm, .esp or .esl
	bool KitMission(std::string_view a_text)
	{
		const auto bar = a_text.find('|');
		if (bar == std::string_view::npos || a_text.find('|', bar + 1) != std::string_view::npos) {
			return false;
		}
		const auto file = KitTrim(a_text.substr(0, bar));
		const auto hex = KitTrim(a_text.substr(bar + 1));
		const auto lower = [](std::string_view a_s) {
			std::string out(a_s);
			std::ranges::transform(out, out.begin(), [](unsigned char a_c) { return static_cast<char>(std::tolower(a_c)); });
			return out;
		};
		const auto fileChar = [](char a_c) {
			return std::isalnum(static_cast<unsigned char>(a_c)) != 0 || std::string_view(" _-.").find(a_c) != std::string_view::npos;
		};
		const auto ext = file.size() > 4 ? lower(file.substr(file.size() - 4)) : std::string{};
		if (file.size() > 64 || (ext != ".esm" && ext != ".esp" && ext != ".esl") || !std::ranges::all_of(file, fileChar) ||
			hex.empty() || hex.size() > 6 ||
			!std::ranges::all_of(hex, [](char a_c) { return std::isxdigit(static_cast<unsigned char>(a_c)) != 0; })) {
			return false;
		}
		const auto id = static_cast<std::uint32_t>(std::strtoul(std::string(hex).c_str(), nullptr, 16));
		if (!id) {
			return false;
		}
		g_kit.missionFile = file;
		g_kit.missionId = id;
		return true;
	}

	// parse_kit's check_stage_at (FAL-527): <1 to 3 hex digits>, the offset of the mission's current stage (a u16) as
	// scripts/ui/pipboy_quest_bytes.py names it from two F11 dumps; even, inside the dump (+0x38 to +0x336)
	bool KitStageAt(std::string_view a_text)
	{
		if (a_text.empty() || a_text.size() > 3 ||
			!std::ranges::all_of(a_text, [](char a_c) { return std::isxdigit(static_cast<unsigned char>(a_c)) != 0; })) {
			return false;
		}
		const auto at = static_cast<std::size_t>(std::strtoul(std::string(a_text).c_str(), nullptr, 16));
		if (at < kQuestDumpAt || at > kQuestStageLast || at % 2 != 0) {
			return false;
		}
		g_kit.missionStageAt = at;
		return true;
	}

	// parse_kit's check_heading_at (FAL-595): [-]<80, 84 or 88>, the player's angle float that is the heading, as
	// scripts/ui/pipboy_map_bytes.py names it from two F11 dumps around a turn to the right; '-' when it falls
	bool KitHeadingAt(std::string_view a_text)
	{
		const bool down = a_text.starts_with('-');
		if (down) {
			a_text.remove_prefix(1);
		}
		if (a_text != "80" && a_text != "84" && a_text != "88") {
			return false;
		}
		g_kit.headingAt = static_cast<std::size_t>(std::strtoul(std::string(a_text).c_str(), nullptr, 16));
		g_kit.headingTurnsDown = down;
		return true;
	}

	// parse_kit's check_grid_units (FAL-595): <decimal>, a cell's width in game units (1 to 65536), as
	// scripts/ui/pipboy_map_bytes.py names it from F11 dumps in two cells
	bool KitGridUnits(std::string_view a_text)
	{
		if (a_text.empty() || a_text.size() > 5 ||
			!std::ranges::all_of(a_text, [](char a_c) { return a_c >= '0' && a_c <= '9'; })) {
			return false;
		}
		const auto units = static_cast<std::uint32_t>(std::strtoul(std::string(a_text).c_str(), nullptr, 10));
		if (units < kGridUnitsMin || units > kGridUnitsMax) {
			return false;
		}
		g_kit.gridUnits = units;
		return true;
	}

	// parse_kit's check_objective (FAL-571): <index>|<path>, the objective's number (1 to 5 decimal digits, at most 65535,
	// once) and where its state is, as scripts/ui/pipboy_quest_bytes.py --objective prints it from the F11 dumps: 2 or 3
	// offsets of 1 to 3 hex digits joined by '/', the first a pointer in the quest's dump (a multiple of 8, 38 to 330),
	// a middle one a pointer in the 0x40 bytes behind it (a multiple of 8, 0 to 38), the last the state's byte (0 to 3F);
	// at most 8 lines
	bool KitObjectiveLine(std::string_view a_text)
	{
		const auto all = [](std::string_view a_s, auto a_is) {
			return !a_s.empty() && std::ranges::all_of(a_s, [&](char a_c) { return a_is(static_cast<unsigned char>(a_c)) != 0; });
		};
		const auto bar = a_text.find('|');
		if (bar == std::string_view::npos || g_kit.objectives.size() == kKitObjectives) {
			return false;
		}
		const auto number = a_text.substr(0, bar);
		if (number.size() > 5 || !all(number, [](int a_c) { return std::isdigit(a_c); })) {
			return false;
		}
		const auto value = std::strtoul(std::string(number).c_str(), nullptr, 10);
		if (value > 0xFFFF) {
			return false;
		}
		const auto index = static_cast<std::uint16_t>(value);
		if (std::ranges::any_of(g_kit.objectives, [&](const KitObjective& a_o) { return a_o.index == index; })) {
			return false;
		}
		KitObjective objective;
		objective.index = index;
		auto rest = a_text.substr(bar + 1);
		while (true) {
			const auto slash = rest.find('/');
			const auto part = rest.substr(0, slash);
			if (part.size() > 3 || !all(part, [](int a_c) { return std::isxdigit(a_c); }) || objective.path.size() == 3) {
				return false;
			}
			objective.path.push_back(static_cast<std::size_t>(std::strtoul(std::string(part).c_str(), nullptr, 16)));
			if (slash == std::string_view::npos) {
				break;
			}
			rest.remove_prefix(slash + 1);
		}
		const auto& path = objective.path;
		if (path.size() < 2 || path.front() < kQuestDumpAt || path.front() > kQuestPointerLast || path.front() % 8 != 0 ||
			(path.size() == 3 && (path[1] > kObjectiveBlock - 8 || path[1] % 8 != 0)) || path.back() >= kObjectiveBlock) {
			return false;
		}
		g_kit.objectives.push_back(std::move(objective));
		return true;
	}

	std::string KitSignature()   // make_pipboy_kit.py signature(): the movie's fo4sfKitId
	{
		std::string tabs;
		for (const auto& tab : g_kit.tabs) {
			tabs += std::format("{}{}", tabs.empty() ? "" : ",", tab);
		}
		return std::format("FO4SF KIT {} {} {}", kKitVersion, kKitRows, tabs);
	}

	bool KitRefuse(std::size_t a_line, std::string_view a_why)
	{
		return Refuse("pages", std::format("line={} reason={} (the kit stays off)", a_line, a_why));
	}

	// the [Kit] and [Page <TAB>/<SUB>] sections of the ini, with parse_kit's grammar and checks; other sections are
	// skipped. Any wrong line refuses the whole kit, at load
	bool ReadKit(const std::filesystem::path& a_ini)
	{
		std::ifstream in(a_ini, std::ios::binary);
		if (!in) {
			return KitRefuse(0, "no_ini");
		}
		enum class Section { kOther, kKit, kPage };
		auto        section = Section::kOther;
		std::string raw;
		std::size_t n = 0;
		while (std::getline(in, raw)) {
			++n;
			const auto line = KitTrim(raw);
			if (line.empty() || line[0] == ';' || line[0] == '#') {
				continue;
			}
			if (line[0] == '[') {
				if (line.back() != ']') {
					return KitRefuse(n, "section");
				}
				const auto name = KitTrim(line.substr(1, line.size() - 2));
				section = Section::kOther;
				if (name == "Kit") {
					section = Section::kKit;
				} else if (name.starts_with("Page ")) {
					const auto path = KitTrim(name.substr(5));
					const auto slash = path.find('/');
					if (slash == std::string_view::npos || path.find('/', slash + 1) != std::string_view::npos) {
						return KitRefuse(n, "page_name");
					}
					KitPage page;
					page.tab = KitTrim(path.substr(0, slash));
					page.sub = KitTrim(path.substr(slash + 1));
					page.line = n;
					if (!KitLabel(page.tab, kKitTabColumns) || !KitLabel(page.sub, kKitSubColumns)) {
						return KitRefuse(n, "tab_or_sub_label");
					}
					for (const auto& other : g_kit.pages) {
						if (other.tab == page.tab && other.sub == page.sub) {
							return KitRefuse(n, "page_twice");
						}
					}
					g_kit.pages.push_back(std::move(page));
					section = Section::kPage;
				}
				continue;
			}
			if (section == Section::kOther) {
				continue;
			}
			const auto eq = line.find('=');
			if (eq == std::string_view::npos) {
				return KitRefuse(n, "no_equals");
			}
			const auto key = KitTrim(line.substr(0, eq));
			const auto value = KitTrim(line.substr(eq + 1));
			if (section == Section::kKit) {
				if (key == "Title" && KitLabel(value, kKitTitleColumns)) {
					g_kit.title = value;
				} else if (key == "Header" && KitValueName(value)) {
					g_kit.header = value;
				} else if (key == "Hints" && KitLabel(value, kKitHintColumns)) {
					g_kit.hints = value;
				} else if (key == "Mission" && g_kit.missionFile.empty() && KitMission(value)) {
					// KitMission kept it
				} else if (key == "MissionStageAt" && !g_kit.missionStageAt && KitStageAt(value)) {
					// KitStageAt kept it
				} else if (key == "MissionObjective" && KitObjectiveLine(value)) {
					// KitObjectiveLine kept it
				} else if (key == "HeadingAt" && !g_kit.headingAt && KitHeadingAt(value)) {
					// KitHeadingAt kept it
				} else if (key == "GridUnits" && !g_kit.gridUnits && KitGridUnits(value)) {
					// KitGridUnits kept it
				} else {
					return KitRefuse(n, std::format("kit_key key={}", key));
				}
				continue;
			}
			auto&   page = g_kit.pages.back();
			KitCell cell;
			if (key == "Row" && page.rows.size() < kKitMaxPageRows && KitCellOf(value, kKitNameColumns, cell)) {
				page.rows.push_back(std::move(cell));
			} else if (key == "List" && page.list.empty() && std::ranges::find(kKitLists, value) != kKitLists.end()) {
				page.list = value;
			} else if (key == "Notice" && page.notice.size() < kKitRows && KitLabel(value, kKitNameColumns)) {
				page.notice.emplace_back(value);
			} else if (key == "Footer" && page.footer.size() < kKitFooter && KitCellOf(value, kKitFooterLabelColumns, cell)) {
				page.footer.push_back(std::move(cell));
			} else if (key == "Hint" && KitLabel(value, kKitHintColumns)) {
				page.hint = value;
			} else {
				return KitRefuse(n, std::format("page_key key={}", key));
			}
		}
		if (g_kit.pages.empty()) {
			return KitRefuse(n, "no_pages");
		}
		for (std::size_t i = 0; i < g_kit.pages.size(); ++i) {
			const auto& page = g_kit.pages[i];
			const auto  kinds = (page.rows.empty() ? 0 : 1) + (page.list.empty() ? 0 : 1) + (page.notice.empty() ? 0 : 1);
			if (kinds != 1) {
				return KitRefuse(page.line, "page_kind (exactly one of Row, List and Notice)");
			}
			auto tab = std::ranges::find(g_kit.tabs, page.tab);
			if (tab == g_kit.tabs.end()) {
				if (g_kit.tabs.size() == kKitTabs) {
					return KitRefuse(page.line, "tabs");
				}
				g_kit.tabs.push_back(page.tab);
				tab = std::prev(g_kit.tabs.end());
			}
			auto& subs = g_kit.subs[static_cast<std::size_t>(std::distance(g_kit.tabs.begin(), tab))];
			if (subs.size() == kKitSubs) {
				return KitRefuse(page.line, "subs");
			}
			subs.push_back(i);
			REX::INFO("step=page_def n={} page={}/{} kind={} rows={} footer={}", i, page.tab, page.sub,
				!page.rows.empty() ? "rows" : !page.list.empty() ? page.list : "notice",
				page.rows.empty() ? page.notice.size() : page.rows.size(), page.footer.size());
		}
		g_kitState.selected.assign(g_kit.pages.size(), 0);
		g_kitState.top.assign(g_kit.pages.size(), 0);
		g_kitState.count.assign(g_kit.pages.size(), 0);
		g_kitPageLogged.assign(g_kit.pages.size(), false);
		REX::INFO("step=pages pages={} tabs={} signature=\"{}\"", g_kit.pages.size(), g_kit.tabs.size(), KitSignature());
		return true;
	}

	// the kit's keys (INI KitUp ... KitNextTab): up to three virtual-key codes each, none 0, above 0xFE, Key or
	// SnapshotKey
	bool ReadKitKeys(const std::filesystem::path& a_ini)
	{
		for (auto& binding : g_kitKeys) {
			std::array<wchar_t, 64> text{};
			REX::W32::GetPrivateProfileStringW(L"FO4SFPipboyMenu", binding.ini, binding.keys, text.data(),
				static_cast<std::uint32_t>(text.size()), a_ini.c_str());
			const wchar_t* at = text.data();
			binding.count = 0;
			while (*at && binding.count < binding.vk.size()) {
				wchar_t*   end = nullptr;
				const auto vk = static_cast<std::uint32_t>(std::wcstoul(at, &end, 0));
				if (end == at || vk == 0 || vk > 0xFE || vk == g_key || vk == g_snapshotKey) {
					return Refuse("ini", std::format("kit_key={} (1 to 0xFE, not Key or SnapshotKey)",
						kKitMoveNames[static_cast<std::size_t>(binding.move)]));
				}
				binding.vk[binding.count++] = vk;
				at = end;
				while (*at == L',' || *at == L' ') {
					++at;
				}
			}
			std::string keys;
			for (std::size_t i = 0; i < binding.count; ++i) {
				keys += std::format("{}{}", i ? "," : "", Hex(binding.vk[i]));
			}
			REX::INFO("step=kit_keys action={} keys={}", kKitMoveNames[static_cast<std::size_t>(binding.move)],
				keys.empty() ? "none" : keys);
		}
		return true;
	}

	// a kit field's text, as the kit's font draws it: upper case, a character the font lacks as "?", at most a_columns
	std::string KitText(std::string_view a_text, std::size_t a_columns)
	{
		std::string out;
		for (const char c : a_text.substr(0, a_columns)) {
			const auto up = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
			out += kKitChars.find(up) != std::string_view::npos ? up : '?';
		}
		return out;
	}

	std::string KitRight(std::string_view a_text, std::size_t a_columns)   // right-aligned: the font is monospaced
	{
		const auto text = KitText(a_text, a_columns);
		return std::string(a_columns - text.size(), ' ') + text;
	}

	std::string KitCentre(std::string_view a_text, std::size_t a_columns)
	{
		const auto text = KitText(a_text, a_columns);
		return std::string((a_columns - text.size()) / 2, ' ') + text;
	}

	std::size_t KitPageIndex(const KitState& a_state) { return g_kit.subs[a_state.tab][a_state.sub[a_state.tab]]; }

	// the first row on screen that keeps the selected row on screen
	std::size_t KitTop(std::size_t a_top, std::size_t a_selected, std::size_t a_count)
	{
		if (a_count <= kKitRows) {
			return 0;
		}
		if (a_selected < a_top) {
			a_top = a_selected;
		}
		if (a_selected >= a_top + kKitRows) {
			a_top = a_selected + 1 - kKitRows;
		}
		return std::min(a_top, a_count - kKitRows);
	}

	// av:<id>'s ActorValueInfo form, looked up once by form id and accepted by its RTTI type (stage d's AcceptById,
	// logged whole as step=kit_av); main thread only
	std::uintptr_t KitActorValue(std::uint32_t a_id)
	{
		if (const auto known = g_kitActorValues.find(a_id); known != g_kitActorValues.end()) {
			return known->second;
		}
		std::uintptr_t form = 0;
		REX::INFO("step=kit_av {}", AcceptById(a_id, "av", "ActorValueInfo@@", kAvifEditorIdAt, form));
		g_kitActorValues.emplace(a_id, form);
		return form;
	}

	// FAL-595: the player's heading in compass degrees (0 to 359), the float at [Kit] HeadingAt= (Peek only; ? without
	// the setting), negated for HeadingAt=-<hex>; logged once: step=kit_heading heading_at= rad= deg=
	std::string HeadingText()
	{
		if (!g_kit.headingAt) {
			return Unknown("heading", "reason=no_heading_at (HeadingAt= in [Kit])");
		}
		float rad = 0.0f;
		if (!CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk) ||
			!Peek(Singleton(kPlayerSingleton) + g_kit.headingAt, rad) || !std::isfinite(rad) || std::abs(rad) > 1000.0f) {
			return Unknown("heading", std::format("reason=unreadable heading_at=+{:03X}", g_kit.headingAt));
		}
		const auto turned = g_kit.headingTurnsDown ? -rad : rad;
		auto       deg = static_cast<int>(std::lround(std::fmod(turned * 180.0 / std::numbers::pi, 360.0)));
		deg = (deg % 360 + 360) % 360;
		static bool logged = false;
		if (!logged) {
			logged = true;
			REX::INFO("step=kit_heading heading_at={}+{:03X} rad={:.4f} deg={}", g_kit.headingTurnsDown ? "-" : "",
				g_kit.headingAt, rad, deg);
		}
		return std::to_string(deg);
	}

	// FAL-595: the player's cell on the grid, POSITION's x and y over [Kit] GridUnits=, rounded down (? without the
	// setting; NONE (INTERIOR) where WORLD says so: the PC's indoor press had libxse's kInterior clear); logged at the
	// first read and at each change:
	// step=kit_grid units= x= y=
	std::string GridText()
	{
		if (!g_kit.gridUnits) {
			return Unknown("grid", "reason=no_grid_units (GridUnits= in [Kit])");
		}
		if (!CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk)) {
			return Unknown("grid", "reason=no_player");
		}
		const auto world = PlaceText().second;
		if (world == "NONE (INTERIOR)") {
			return world;
		}
		if (world == "?") {
			return Unknown("grid", "reason=world");
		}
		std::array<float, 3> xyz{};
		if (!ReadPosition(xyz) || !std::isfinite(xyz[0]) || !std::isfinite(xyz[1])) {
			return Unknown("grid", "reason=no_player");
		}
		const auto  x = static_cast<std::int64_t>(std::floor(xyz[0] / static_cast<double>(g_kit.gridUnits)));
		const auto  y = static_cast<std::int64_t>(std::floor(xyz[1] / static_cast<double>(g_kit.gridUnits)));
		constexpr auto none = std::numeric_limits<std::int64_t>::min();
		static auto    logged = std::pair<std::int64_t, std::int64_t>{ none, none };
		if (logged != std::pair{ x, y }) {
			logged = { x, y };
			REX::INFO("step=kit_grid units={} x={} y={}", g_kit.gridUnits, x, y);
		}
		return std::format("{} {}", x, y);
	}

	// one value provider's text (README, "Stage (e)": what each reads, and its step=page_unknown line when it cannot);
	// main thread only
	std::string KitValueRead(std::string_view a_spec)
	{
		if (a_spec == "health") {
			return ActorValueText("health", g_forms.health);
		}
		if (a_spec == "xp") {
			return ActorValueText("experience", g_forms.experience);
		}
		if (a_spec == "carry_max") {
			return ActorValueText("carry_weight", g_forms.carryWeight);
		}
		if (a_spec == "rads") {
			return g_forms.rads ? ActorValueText("rads", g_forms.rads) :
			       g_forms.avifs ? std::string("NOT INSTALLED") :
			                       Unknown("rads", "reason=actor_values_unread");
		}
		if (a_spec == "level") {
			return LevelText();
		}
		if (a_spec == "cell") {
			return PlaceText().first;
		}
		if (a_spec == "world") {
			return PlaceText().second;
		}
		if (a_spec == "time") {
			return TimeText();
		}
		if (a_spec == "days") {   // checked as the time is: both globals in range at the offset FindGlobalValue found
			float hour = 0.0f;
			float days = 0.0f;
			if (!ReadTime(g_forms.globalValueAt, hour, days)) {
				const auto reason = !g_forms.globals        ? "globals_unread" :
				                    !g_forms.globalValueAt ? "no_value_offset" :
				                                             "out_of_range";
				return Unknown("days", std::format("reason={}", reason));
			}
			return std::format("{:.2f}", days);
		}
		if (a_spec == "position") {
			std::array<float, 3> xyz{};
			return ReadPosition(xyz) && std::isfinite(xyz[0]) && std::isfinite(xyz[1]) && std::isfinite(xyz[2]) ?
			           std::format("{:.0f} {:.0f} {:.0f}", xyz[0], xyz[1], xyz[2]) :
			           Unknown("position", "reason=no_player");
		}
		if (a_spec == "heading") {
			return HeadingText();
		}
		if (a_spec == "grid") {
			return GridText();
		}
		if (a_spec.starts_with(kKitActorValue)) {   // ReadKit checked the hex
			const auto id = static_cast<std::uint32_t>(std::strtoul(std::string(a_spec.substr(kKitActorValue.size())).c_str(), nullptr, 16));
			return ActorValueText(a_spec, KitActorValue(id));
		}
		return Unknown(a_spec, "reason=no_such_value");
	}

	// each value once per screen (a footer cell that repeats a row's value reads it once)
	std::string KitValue(std::string_view a_spec, std::unordered_map<std::string, std::string>& a_memo)
	{
		std::string key(a_spec);
		if (const auto known = a_memo.find(key); known != a_memo.end()) {
			return known->second;
		}
		auto value = KitValueRead(a_spec);
		a_memo.emplace(std::move(key), value);
		return value;
	}

	// the kit_test list: thirty rows to scroll, select and click, with the kit's move counts beside the selected one
	std::vector<KitRow> KitTestRows(const KitState& a_state)
	{
		std::vector<KitRow> rows;
		for (std::size_t i = 1; i <= kKitTestRows; ++i) {
			rows.push_back({ std::format("TEST ROW {:02}", i), std::to_string(i * 7),
				{ { "ROW", std::format("{} OF {}", i, kKitTestRows) }, { "KEY MOVES", std::to_string(a_state.keys) },
					{ "CLICK MOVES", std::to_string(a_state.clicks) }, { "UPDATES", std::to_string(g_updates.load()) } } });
		}
		return rows;
	}

	// a_len bytes as hex, a comma every 8, for the log; "unreadable" if the read faults
	std::string KitBytes(std::uintptr_t a_at, std::size_t a_len)
	{
		std::array<std::uint8_t, 0x40> bytes{};
		if (!a_at || a_len > bytes.size() || !Peek(a_at, bytes.data(), a_len)) {
			return "unreadable";
		}
		std::string hex;
		for (std::size_t i = 0; i < a_len; ++i) {
			hex += std::format("{}{:02x}", i && i % 8 == 0 ? "," : "", bytes[i]);
		}
		return hex;
	}

	// the inventory list (FAL-426; README, "Stage (e)", lists): the player's BGSInventoryList by its RTTI, each item's
	// name and count (the sum of its stacks), sorted by name. Reads only, guarded, no lock taken: a torn read shows ?
	// and never faults. The first read logs the list and its first item's and stack's bytes once (step=kit_inventory),
	// which settles kStackCountAt on the PC; a list not read is one row and one step=page_unknown what=inventory line
	std::vector<KitRow> KitInventoryRows()
	{
		static bool logged = false;
		const auto  unread = [](std::string_view a_why, const std::string& a_detail) {
			Unknown("inventory", std::format("reason={} {}", a_why, a_detail));
			return std::vector<KitRow>{ { "INVENTORY NOT READ", "", { { "REASON", std::string(a_why) } } } };
		};
		if (!CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk)) {
			return unread("no_player", "");
		}
		const auto     player = Singleton(kPlayerSingleton);
		std::uintptr_t list = 0;
		ObjectType     listType;
		if (!Peek(player + kInventoryListAt, list) || !IsType(list, "BGSInventoryList@@", listType)) {
			return unread("list_type", std::format("list={} type={}", Hex(list), listType.name.empty() ? "unreadable" : listType.name));
		}
		ArrayHead items{};
		if (!Peek(list + kInventoryDataAt, items) || items.size > items.capacity || items.size > kKitMaxItems ||
			(items.size && !items.data)) {
			return unread("items", std::format("size={} capacity={} data={}", items.size, items.capacity, Hex(items.data)));
		}
		if (!logged) {
			logged = true;
			ArrayHead first{};
			const bool stacked = items.size && Peek(items.data + kItemStacksAt, first) && first.size;
			REX::INFO("step=kit_inventory list={} type={} size={} capacity={} first_item={} first_stack={}", Hex(list),
				listType.name, items.size, items.capacity, items.size ? KitBytes(items.data, kInventoryItemSize) : "none",
				stacked ? KitBytes(first.data, kStackSize) : "none");
		}
		std::vector<KitRow> rows;
		for (std::uint32_t i = 0; i < items.size; ++i) {
			const auto     item = items.data + i * kInventoryItemSize;
			std::uintptr_t object = 0;
			ObjectType     type;
			if (!Peek(item, object) || !TypeOf(object, type) || !BaseOffset(type, "TESBoundObject@@")) {
				rows.push_back({ "?", "?", { { "ITEM", std::to_string(i + 1) }, { "OBJECT", Hex(object) } } });
				continue;
			}
			std::uint32_t  formId = 0;
			std::uintptr_t entry = 0;
			std::string    name;
			Peek(object + kFormIdAt, formId);
			const auto at = BaseOffset(type, "TESFullName@@");
			if (!at || !CheckSubobject(object, type, *at) || !Peek(object + *at + kFullNameAt, entry) ||
				!ReadPoolString(entry, name) || name.empty()) {
				name = std::format("{:08X}", formId);   // no name read: its form id
			}
			ArrayHead     stacks{};
			std::uint64_t count = 0;
			bool          counted = Peek(item + kItemStacksAt, stacks) && stacks.size <= stacks.capacity &&
			                        stacks.size <= kKitMaxItems && (!stacks.size || stacks.data);
			for (std::uint32_t s = 0; counted && s < stacks.size; ++s) {
				std::uint32_t n = 0;
				counted = Peek(stacks.data + s * kStackSize + kStackCountAt, n);
				count += n;
			}
			std::uint32_t flags = 0;
			const bool    equipped = Peek(item + kItemFlagsAt, flags) && (flags & 0x7);
			rows.push_back({ name, counted ? std::to_string(count) : "?",
				{ { "FORM", std::format("{:08X}", formId) }, { "TYPE", ShortName(type.name) },
					{ "STACKS", counted ? std::to_string(stacks.size) : "?" }, { "EQUIPPED", equipped ? "YES" : "NO" } } });
		}
		std::ranges::stable_sort(rows, {}, &KitRow::name);
		if (rows.empty()) {
			rows.push_back({ "NO ITEMS", "", {} });
		}
		return rows;
	}

	// a plugin file's form: its TESFile by name in the data handler's compiled file collection (libxse 9d090c4: files,
	// smallFiles, mediumFiles at +0x00, +0x10, +0x20, each a BSTArray<TESFile*>; a file accepted by its RTTI as
	// IsFileType), then the form id that file gives a_localId (full: the compile index, then fileIndex's full byte;
	// small FE + 12 bits; medium FD + 16 bits), accepted only if the engine's lookup gives a form of RTTI type a_type.
	// a_detail logs the file and every id tried; files skipped for their type are counted, and logged once
	// (step=kit_file), so a miss is never silent
	std::uint32_t KitFileForm(std::string_view a_file, std::uint32_t a_localId, std::string_view a_type, std::string& a_detail)
	{
		static bool skipLogged = false;
		std::size_t skipped = 0;
		std::string skippedType;
		const auto  logSkipped = [&] {
			if (skipped && !skipLogged) {
				skipLogged = true;
				REX::INFO("step=kit_file file={} skipped={} type={} (not a TESFile at +0)", a_file, skipped, skippedType);
			}
		};
		const auto handler = Singleton(kDataHandlerSingleton);
		ObjectType type;
		if (!IsType(handler, "TESDataHandler@@", type)) {
			a_detail = "reason=data_handler";
			return 0;
		}
		for (std::size_t kind = 0; kind < 3; ++kind) {   // full, small, medium
			ArrayHead files{};
			if (!Peek(handler + kFileCollectionAt + kind * 0x10, files) || files.size > files.capacity ||
				files.size > kKitMaxFiles || (files.size && !files.data)) {
				a_detail = std::format("reason=files kind={} size={} capacity={}", kind, files.size, files.capacity);
				logSkipped();
				return 0;
			}
			for (std::uint32_t i = 0; i < files.size; ++i) {
				std::uintptr_t                  file = 0;
				ObjectType                      fileType;
				std::array<char, kFileNameSize> name{};
				if (!Peek(files.data + i * sizeof(std::uintptr_t), file) || !file) {
					continue;
				}
				if (!TypeOf(file, fileType) || !IsFileType(fileType)) {
					if (!skipped++) {
						skippedType = fileType.name.empty() ? "unread" : ShortName(fileType.name);
					}
					continue;
				}
				if (!Peek(file + kFileNameAt, name.data(), name.size()) ||
					!SameText(std::string_view(name.data(), strnlen(name.data(), name.size())), a_file)) {
					continue;
				}
				std::uint8_t                compile = 0;
				std::array<std::uint8_t, 4> index{};
				Peek(file + kFileCompileIndexAt, compile);
				Peek(file + kFileIndexAt, index.data(), index.size());
				const std::uint32_t smallIndex = index[2] | (index[3] << 8);
				std::vector<std::uint32_t> ids;
				if (kind == 0) {
					ids = { (std::uint32_t{ compile } << 24) | (a_localId & 0xFFFFFF), (std::uint32_t{ index[0] } << 24) | (a_localId & 0xFFFFFF) };
				} else if (kind == 1) {
					ids = { 0xFE000000u | ((smallIndex & 0xFFF) << 12) | (a_localId & 0xFFF) };
				} else {
					ids = { 0xFD000000u | (std::uint32_t{ index[1] } << 16) | (a_localId & 0xFFFF) };
				}
				a_detail = std::format("file_kind={} file={} file_type={} compile_index={:02x} file_index={}", kind, Hex(file),
					ShortName(fileType.name), compile, KitBytes(file + kFileIndexAt, 4));
				logSkipped();
				for (const auto id : ids) {
					ObjectType formType;
					const auto form = FormById(id);
					a_detail += std::format(" tried={:08X}:{}", id, form && TypeOf(form, formType) ? ShortName(formType.name) : "none");
					if (IsType(form, a_type, formType)) {
						return id;
					}
				}
				return 0;
			}
		}
		a_detail = std::format("reason=file_not_loaded skipped={}", skipped);
		logSkipped();
		return 0;
	}

	// the quest list (FAL-431; README, "Stage (e)", lists): our mission first, the quest [Kit] Mission= names, by its
	// file and local id (KitFileForm), accepted by its RTTI (TESQuest); its name (TESFullName, at +0x40 in Starfield's
	// RTTI) and its QUEST_DATA flags as read (u16 at +0x10C, the running and completed bits not named until the PC's
	// log does). The first read logs the quest's bytes from +0x100 once (step=kit_quest), where the flags and the
	// current stage are; the stage shows ? until [Kit] MissionStageAt= names its offset (FAL-527). Starfield's own
	// quests are not listed yet
	void KitObjectiveRows(std::uintptr_t a_quest, std::uint32_t a_formId, std::vector<std::pair<std::string, std::string>>& a_info);

	std::vector<KitRow> KitQuestRows()
	{
		static std::uint32_t formId = 0;
		static bool          logged = false;
		const auto           unread = [](std::string_view a_why, const std::string& a_detail) {
			Unknown("quests", std::format("reason={} {}", a_why, a_detail));
			return std::vector<KitRow>{ { "QUESTS NOT READ", "", { { "REASON", std::string(a_why) } } } };
		};
		if (g_kit.missionFile.empty()) {
			return unread("no_mission", "");
		}
		std::string detail;
		if (!formId) {
			formId = KitFileForm(g_kit.missionFile, g_kit.missionId, "TESQuest@@", detail);
		}
		const auto quest = formId ? FormById(formId) : 0;
		ObjectType type;
		if (!IsType(quest, "TESQuest@@", type)) {
			if (!logged) {
				logged = true;
				REX::INFO("step=kit_quest mission={}|{:X} found=no {}", g_kit.missionFile, g_kit.missionId, detail);
			}
			formId = 0;
			g_kitQuest = 0;
			return unread("mission_not_found", std::format("mission={}|{:X}", g_kit.missionFile, g_kit.missionId));
		}
		g_kitQuest = quest;
		std::string    name;   // its TESFullName as the inventory reads one, else its form id
		std::uintptr_t entry = 0;
		const auto     at = BaseOffset(type, "TESFullName@@");
		if (!at || !CheckSubobject(quest, type, *at) || !Peek(quest + *at + kFullNameAt, entry) || !ReadPoolString(entry, name) ||
			name.empty()) {
			name = std::format("{:08X}", formId);
		}
		std::uint16_t flags = 0;
		const bool    flagged = Peek(quest + kQuestFlagsAt, flags);
		if (!logged) {
			logged = true;
			REX::INFO("step=kit_quest mission={}|{:X} found=yes form={:08X} quest={} type={} full_name_at={} name=\"{}\" flags={} "
				"bytes100={} {}", g_kit.missionFile, g_kit.missionId, formId, Hex(quest), type.name, at ? Hex(*at) : "none", name,
				flagged ? std::format("{:04x}", flags) : "unreadable", KitBytes(quest + kQuestBytesAt, 0x40), detail);
		}
		// FAL-527: the stage, a u16 at [Kit] MissionStageAt= (read with Peek only; ? without the setting), logged at
		// the first read and at each change: step=kit_quest_stage form= stage_at=+<offset> stage=<n>
		static int    loggedStage = -1;
		std::uint16_t stage = 0;
		std::string   stageText = "?";
		if (!g_kit.missionStageAt) {
			Unknown("quest_stage", "reason=no_stage_at (MissionStageAt= in [Kit])");
		} else if (!Peek(quest + g_kit.missionStageAt, stage)) {
			Unknown("quest_stage", std::format("reason=unreadable stage_at=+{:03X}", g_kit.missionStageAt));
		} else {
			stageText = std::to_string(stage);
			if (loggedStage != stage) {
				loggedStage = stage;
				REX::INFO("step=kit_quest_stage form={:08X} stage_at=+{:03X} stage={}", formId, g_kit.missionStageAt, stage);
			}
		}
		std::string file = g_kit.missionFile;
		std::ranges::transform(file, file.begin(), [](unsigned char a_c) { return static_cast<char>(std::toupper(a_c)); });
		std::vector<std::pair<std::string, std::string>> info{ { "FORM", std::format("{:08X}", formId) }, { "FILE", file },
			{ "FLAGS", flagged ? std::format("{:04X}", flags) : "?" }, { "STAGE", stageText } };
		KitObjectiveRows(quest, formId, info);
		return { { name, "", std::move(info) } };
	}

	// FAL-571: an objective's state as the PC's run at 73271aa3 read it (0, 1, 3); any other value raw
	std::string ObjectiveState(std::uint8_t a_state)
	{
		switch (a_state) {
		case 0:
			return "NOT SHOWN";
		case 1:
			return "SHOWN";
		case 3:
			return "DONE";
		default:
			return std::format("STATE {}", static_cast<unsigned>(a_state));
		}
	}

	// FAL-571: the quest's objectives as value rows OBJECTIVE <n>, each its state named (ObjectiveState). Peek only.
	// [Kit] MissionObjective= lines, when there are any, are used as they are (an override, each read along its path).
	// Else the objectives' BSTArray at +0x148 is walked: its size at most 64 and at most its capacity, and every entry an
	// objective whose +0x18 is this quest, else one row OBJECTIVES ? and what=quest_objectives reason=head or
	// reason=objective index=<i> (nothing shown from a half-read array). Logged when it changes:
	// step=kit_quest_objectives form= at=+148 size= capacity= objectives=<n>,... (or the reason), and each state at the
	// first read and at each change: step=kit_quest_objective form= objective=<n> from=<array or path=...> state=<n>.
	// At most 12 rows: past 11, the 12th is MORE OBJECTIVES <count>
	void KitObjectiveRows(std::uintptr_t a_quest, std::uint32_t a_formId, std::vector<std::pair<std::string, std::string>>& a_info)
	{
		static std::unordered_map<std::uint32_t, int> loggedStates;
		const auto shown = [&](std::uint16_t a_number, std::uint8_t a_state, const std::string& a_from) {
			a_info.emplace_back(std::format("OBJECTIVE {}", a_number), ObjectiveState(a_state));
			auto& logged = loggedStates.try_emplace(a_number, -1).first->second;
			if (logged != a_state) {
				logged = a_state;
				REX::INFO("step=kit_quest_objective form={:08X} objective={} from={} state={}", a_formId, a_number, a_from,
					static_cast<unsigned>(a_state));
			}
		};
		if (g_kit.objectives.empty()) {
			static std::string loggedWalk;
			ArrayHead          head{};
			std::string        why;
			std::vector<std::pair<std::uint16_t, std::uint8_t>> found;
			if (!Peek(a_quest + kQuestObjectivesAt, head) || head.size > head.capacity || head.size > kQuestObjectivesMax ||
				(head.size && !head.data)) {
				why = std::format("reason=head size={} capacity={} data={}", head.size, head.capacity, Hex(head.data));
			}
			for (std::uint32_t i = 0; why.empty() && i < head.size; ++i) {
				std::uintptr_t objective = 0;
				std::uintptr_t owner = 0;
				std::uint16_t  number = 0;
				std::uint8_t   state = 0;
				if (!Peek(head.data + 8ull * i, objective) || !objective || !Peek(objective + kObjectiveOwnerAt, owner) ||
					owner != a_quest || !Peek(objective + kObjectiveNumberAt, number) || !Peek(objective + kObjectiveStateAt, state)) {
					why = std::format("reason=objective index={} objective={} owner={}", i, Hex(objective), Hex(owner));
				} else {
					found.emplace_back(number, state);
				}
			}
			std::string numbers;
			for (const auto& entry : found) {
				numbers += std::format("{}{}", numbers.empty() ? "" : ",", entry.first);
			}
			if (numbers.empty()) {
				numbers = "none";
			}
			const auto walk = why.empty() ? std::format("size={} capacity={} objectives={}", head.size, head.capacity, numbers) : why;
			if (walk != loggedWalk) {
				loggedWalk = walk;
				REX::INFO("step=kit_quest_objectives form={:08X} at=+{:03X} {}", a_formId, kQuestObjectivesAt, walk);
			}
			if (!why.empty()) {
				a_info.emplace_back("OBJECTIVES", Unknown("quest_objectives", why));
				return;
			}
			if (found.empty()) {
				a_info.emplace_back("OBJECTIVES", "NONE");
				return;
			}
			const auto rows = found.size() > kKitObjectiveRows ? kKitObjectiveRows - 1 : found.size();
			for (std::size_t i = 0; i < rows; ++i) {
				shown(found[i].first, found[i].second, "array");
			}
			if (rows < found.size()) {
				a_info.emplace_back("MORE OBJECTIVES", std::to_string(found.size() - rows));
			}
			return;
		}
		for (std::size_t i = 0; i < g_kit.objectives.size(); ++i) {
			const auto&    objective = g_kit.objectives[i];
			std::string    path;
			std::uintptr_t at = a_quest;
			bool           read = true;
			for (std::size_t p = 0; p < objective.path.size(); ++p) {
				path += std::format("{}+{:02X}", p ? "/" : "", objective.path[p]);
				if (read && p + 1 < objective.path.size()) {
					read = Peek(at + objective.path[p], at) && at;
				}
			}
			std::uint8_t state = 0;
			if (!read || !Peek(at + objective.path.back(), state)) {
				a_info.emplace_back(std::format("OBJECTIVE {}", objective.index), Unknown(std::format("objective:{}", objective.index),
					std::format("reason=unreadable objective={} path={}", objective.index, path)));
				continue;
			}
			shown(objective.index, state, "path=" + path);
		}
	}

	// FAL-571, after the quest's bytes on F11 at stage (e): where the objectives' states are. They are not among the
	// quest's own bytes as far as the sources say (FO4's and Skyrim's BGSQuestObjective is an object of its own that
	// points back to its quest, reached through a list or an array), so each 8-byte word of the dump that is Followable
	// is followed one hop (its 0x40 bytes), and each such word in those bytes one hop further. A block that holds the
	// quest's own address (its owner) is logged once, by the first path that reached it,
	// step=kit_quest_obj n=<snapshot> form= path=+<offset>[/+<offset>] at=<address> bytes=<64 bytes>, then
	// step=kit_quest_objs n= form= followed=<blocks read> owned=<blocks logged>. Peek and VirtualQuery only, no call into
	// the game; a third hop (a list's third entry) is not followed
	void LogKitQuestObjectives(std::uint32_t a_n, std::uint32_t a_formId)
	{
		struct Block
		{
			std::uintptr_t at;
			std::string    path;
		};
		const auto               quest = g_kitQuest;
		std::set<std::uintptr_t> seen{ quest };
		std::vector<Block>       hop1;
		std::size_t              followed = 0;
		std::size_t              owned = 0;
		const auto visit = [&](std::uintptr_t a_from, std::size_t a_offset, std::string a_path, std::vector<Block>* a_keep) {
			std::uintptr_t                                  to = 0;
			std::array<std::uintptr_t, kObjectiveBlock / 8> words{};
			if (!Peek(a_from + a_offset, to) || !Followable(to) || !seen.insert(to).second ||
				!Peek(to, words.data(), kObjectiveBlock)) {
				return;
			}
			++followed;
			if (std::ranges::find(words, quest) != words.end()) {
				++owned;
				REX::INFO("step=kit_quest_obj n={} form={:08X} path={} at={} bytes={}", a_n, a_formId, a_path, Hex(to),
					KitBytes(to, kObjectiveBlock));
			}
			if (a_keep) {
				a_keep->push_back({ to, std::move(a_path) });
			}
		};
		for (auto at = kQuestDumpAt; at <= kQuestPointerLast; at += 8) {
			visit(quest, at, std::format("+{:02X}", at), &hop1);
		}
		for (const auto& block : hop1) {
			for (std::size_t at = 0; at < kObjectiveBlock; at += 8) {
				visit(block.at, at, std::format("{}/+{:02X}", block.path, at), nullptr);
			}
		}
		REX::INFO("step=kit_quest_objs n={} form={:08X} followed={} owned={}", a_n, a_formId, followed, owned);
	}

	// FAL-446, main thread, on the snapshot key at stage (e): the mission's bytes from +0x38 to +0x338, 64 to a line
	// (step=kit_quest_bytes n=<snapshot> form= at=+<offset> bytes=), so two presses with the mission at two stages (the
	// console's setstage between them) show where the current stage is. The quest is the one the quests page last
	// accepted, checked again by its RTTI; no call into the game. STAGE shows ? until [Kit] MissionStageAt= names it.
	// FAL-571: then the blocks behind its pointers that point back to it (LogKitQuestObjectives)
	void LogKitQuestBytes()
	{
		const auto n = g_snapshots.load();
		ObjectType type;
		if (!IsType(g_kitQuest, "TESQuest@@", type)) {
			REX::INFO("step=kit_quest_bytes n={} reason={}", n, g_kitQuest ? "not_a_quest" : "quests_page_not_read");
			return;
		}
		std::uint32_t formId = 0;
		Peek(g_kitQuest + kFormIdAt, formId);
		for (auto at = kQuestDumpAt; at < kQuestDumpEnd; at += 0x40) {
			REX::INFO("step=kit_quest_bytes n={} form={:08X} at=+{:03X} bytes={}", n, formId, at, KitBytes(g_kitQuest + at, 0x40));
		}
		LogKitQuestObjectives(n, formId);
	}

	// FAL-595, main thread, on the snapshot key at stage (e): the player's bytes from +0x80 to +0xC0 (OBJ_REFR's angle
	// and location, ... parentCell at +0xB0) and the six floats at +0x80 (step=kit_map_bytes n= at=+080 bytes= floats=),
	// then the player's cell and its own grid (libxse TESObjectCELL::cellData at +0x58, EXTERIOR_DATA's cellX and cellY:
	// step=kit_map_cell n= cell= world= flags= data= cell_x= cell_y=), so F11 before and after a turn shows which float
	// is the heading and F11 in two cells which GridUnits= POSITION needs (scripts/ui/pipboy_map_bytes.py). Peek only.
	void LogKitMapBytes()
	{
		const auto n = g_snapshots.load();
		if (!CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk)) {
			REX::INFO("step=kit_map_bytes n={} reason=no_player", n);
			return;
		}
		const auto           player = Singleton(kPlayerSingleton);
		std::array<float, 6> floats{};
		std::string          floatText = "unreadable";
		if (Peek(player + kAngleAt, floats)) {
			floatText.clear();
			for (std::size_t i = 0; i < floats.size(); ++i) {
				floatText += std::format("{}{:.4f}", i ? "," : "", floats[i]);
			}
		}
		REX::INFO("step=kit_map_bytes n={} at=+{:03X} bytes={} floats={}", n, kAngleAt, KitBytes(player + kAngleAt, kMapDumpBytes),
			floatText);
		std::uintptr_t cell = 0;
		ObjectType     cellType;
		if (!Peek(player + kParentCellAt, cell) || !IsType(cell, "TESObjectCELL@@", cellType)) {
			REX::INFO("step=kit_map_cell n={} reason=cell cell={}", n, Hex(cell));
			return;
		}
		std::uintptr_t               world = 0;
		std::uint32_t                flags = 0;
		std::uintptr_t               data = 0;
		std::array<std::int32_t, 2>  xy{};
		const bool                   gotWorld = Peek(cell + kCellWorldAt, world);
		const bool                   gotFlags = Peek(cell + kCellFlagsAt, flags);
		const bool                   gotXy = Peek(cell + kCellDataAt, data) && data && Peek(data, xy);
		REX::INFO("step=kit_map_cell n={} cell={} world={} flags={} data={} {}", n, Hex(cell), gotWorld ? Hex(world) : "unreadable",
			gotFlags ? Hex(flags) : "unreadable", Hex(data), gotXy ? std::format("cell_x={} cell_y={}", xy[0], xy[1]) : "cell_xy=unreadable");
		// FAL-595: where the cell keeps its worldspace (+0x118 read 0 outdoors): each 8-byte word from +0x38 to +0x200 that
		// is a heap object whose RTTI is TESWorldSpace, step=kit_map_world n= at=+<offset> world=<addr> name="<name>";
		// then step=kit_map_worlds n= found=<k>. Peek and VirtualQuery only
		std::size_t found = 0;
		for (auto at = std::size_t{ 0x38 }; at < kCellScanEnd; at += 8) {
			std::uintptr_t word = 0;
			ObjectType     worldType;
			if (!Peek(cell + at, word) || !Followable(word) || !IsType(word, "TESWorldSpace@@", worldType)) {
				continue;
			}
			++found;
			REX::INFO("step=kit_map_world n={} at=+{:03X} world={} name=\"{}\"", n, at, Hex(word), NameText("world_name", word, worldType));
		}
		REX::INFO("step=kit_map_worlds n={} cell={} found={}", n, Hex(cell), found);
	}

	// a_text in lines of at most a_columns, each broken after its last space, '_', '-', '/' or '|' when the rest does
	// not fit, else cut at a_columns (FAL-437: MISSION_NOT_FOUND read MISSION_NOT_FOUN / D)
	std::vector<std::string> KitWrap(std::string_view a_text, std::size_t a_columns)
	{
		std::vector<std::string> lines;
		while (!a_text.empty()) {
			auto cut = std::min(a_text.size(), a_columns);
			if (cut < a_text.size()) {
				const auto at = a_text.substr(0, cut).find_last_of(" _-/|");
				if (at != std::string_view::npos && at > 0) {
					cut = at + 1;
				}
			}
			const auto line = a_text.substr(0, cut);
			lines.emplace_back(line.substr(0, line.find_last_not_of(' ') + 1));
			a_text.remove_prefix(cut);
			a_text.remove_prefix(std::min(a_text.find_first_not_of(' '), a_text.size()));
		}
		return lines;
	}

	// the selected row's value rows: a label and its value right-aligned, or, for a value longer than its column,
	// the label alone and the value on the lines below, left-aligned in the label column (KitWrap)
	void KitInfoLines(const std::vector<std::pair<std::string, std::string>>& a_info, KitScreen& a_screen)
	{
		constexpr auto width = kKitInfoLabelColumns + kKitInfoValueColumns;
		std::size_t    line = 0;
		for (const auto& [label, value] : a_info) {
			if (line == kKitRows) {
				break;
			}
			const auto text = KitText(value, width * 3);
			a_screen.infoLabels[line] = KitText(label, kKitInfoLabelColumns);
			if (text.size() <= kKitInfoValueColumns) {
				a_screen.infoValues[line++] = KitRight(text, kKitInfoValueColumns);
				continue;
			}
			++line;
			for (const auto& part : KitWrap(text, kKitInfoLabelColumns)) {
				if (line == kKitRows) {
					break;
				}
				a_screen.infoLabels[line] = part;
				a_screen.infoValues[line++] = "";
			}
		}
	}

	// the shown page's screen, on the main thread before each kShow and kUpdate (Toggle, SendUpdate)
	void KitCollect()
	{
		PageScan();
		FindGlobalValue();
		KitState state;
		{
			std::scoped_lock lock(g_pageLock);
			state = g_kitState;
		}
		const auto                                   index = KitPageIndex(state);
		const auto&                                  page = g_kit.pages[index];
		std::unordered_map<std::string, std::string> memo;
		std::vector<KitRow>                          rows;
		if (!page.rows.empty()) {
			for (const auto& cell : page.rows) {
				auto value = KitValue(cell.value, memo);
				rows.push_back({ cell.label, value, { { "VALUE", value }, { "FROM", cell.value } } });
			}
		} else if (page.list == "kit_test") {
			rows = KitTestRows(state);
		} else if (page.list == "inventory") {
			rows = KitInventoryRows();
		} else if (page.list == "quests") {
			rows = KitQuestRows();
		} else {
			for (const auto& line : page.notice) {
				rows.push_back({ line, "", {} });
			}
		}
		const auto count = page.notice.empty() ? rows.size() : std::size_t{ 0 };   // a notice has no selection
		const auto selected = count ? std::min(state.selected[index], count - 1) : std::size_t{ 0 };
		const auto top = KitTop(state.top[index], selected, count);
		KitScreen  screen;
		screen.page = index;
		screen.title = KitText(g_kit.title, kKitTitleColumns);
		screen.header = g_kit.header.empty() ? "" : KitRight(KitValue(g_kit.header, memo), kKitTitleColumns);
		screen.hints = KitText(page.hint.empty() ? g_kit.hints : page.hint, kKitHintColumns);
		for (std::size_t i = 0; i < g_kit.tabs.size(); ++i) {
			screen.tabs[i] = KitText(g_kit.tabs[i], kKitTabColumns);
		}
		screen.tab = state.tab;
		const auto& subs = g_kit.subs[state.tab];
		for (std::size_t i = 0; i < subs.size(); ++i) {
			screen.subs[i] = KitText(g_kit.pages[subs[i]].sub, kKitSubColumns);
		}
		screen.sub = state.sub[state.tab];
		for (std::size_t i = 0; i < kKitRows && top + i < rows.size(); ++i) {
			const auto& row = rows[top + i];
			if (row.value.size() <= kKitValueColumns) {
				screen.names[i] = KitText(row.name, kKitNameColumns);
				screen.values[i] = row.value.empty() ? "" : KitRight(row.value, kKitValueColumns);
			} else {   // a long value follows its label in the name's column
				screen.names[i] = KitText(std::format("{} {}", row.name, row.value), kKitNameColumns);
			}
		}
		if (count) {
			screen.bar = selected - top;
			KitInfoLines(rows[selected].info, screen);
		}
		screen.moreUp = top > 0;
		screen.moreDown = top + kKitRows < rows.size();
		for (std::size_t i = 0; i < page.footer.size(); ++i) {
			screen.footer[i] = KitCentre(std::format("{} {}", page.footer[i].label, KitValue(page.footer[i].value, memo)),
				kKitFooterColumns);
		}
		if (!g_kitPageLogged[index]) {
			g_kitPageLogged[index] = true;
			REX::INFO("step=kit_page page={}/{} rows={} selectable={} first=\"{}\"", page.tab, page.sub, rows.size(), count,
				rows.empty() ? "" : KitText(std::format("{} {}", rows[0].name, rows[0].value), kKitNameColumns));
		}
		std::scoped_lock lock(g_pageLock);
		if (KitPageIndex(g_kitState) == index) {   // keep a move made since the copy; only bound it
			auto& s = g_kitState;
			s.count[index] = count;
			s.selected[index] = count ? std::min(s.selected[index], count - 1) : std::size_t{ 0 };
			s.top[index] = KitTop(s.top[index], s.selected[index], count);
		}
		g_kitScreen = std::move(screen);
		g_kitCollected = true;
	}

	// one move of the state, from a key (the key thread) or a click (the menu's thread), then an update at once.
	// Returns what it did, for the log line of its caller
	std::string KitAct(KitMove a_move, std::size_t a_index, bool a_key)
	{
		std::scoped_lock lock(g_pageLock);
		auto&      s = g_kitState;
		const auto page = KitPageIndex(s);
		const auto tabs = g_kit.tabs.size();
		const auto subs = g_kit.subs[s.tab].size();
		const auto count = s.count[page];
		auto&      selected = s.selected[page];
		auto&      sub = s.sub[s.tab];
		bool       moved = false;
		switch (a_move) {   // a move past either end changes nothing (no wrap)
		case KitMove::kUp:
			moved = selected > 0;
			if (moved) {
				--selected;
			}
			break;
		case KitMove::kDown:
			moved = selected + 1 < count;
			if (moved) {
				++selected;
			}
			break;
		case KitMove::kPrevSub:
			moved = sub > 0;
			if (moved) {
				--sub;
			}
			break;
		case KitMove::kNextSub:
			moved = sub + 1 < subs;
			if (moved) {
				++sub;
			}
			break;
		case KitMove::kPrevTab:
			moved = s.tab > 0;
			if (moved) {
				--s.tab;
			}
			break;
		case KitMove::kNextTab:
			moved = s.tab + 1 < tabs;
			if (moved) {
				++s.tab;
			}
			break;
		case KitMove::kTab:
			moved = a_index < tabs && a_index != s.tab;
			if (moved) {
				s.tab = a_index;
			}
			break;
		case KitMove::kSub:
			moved = a_index < subs && a_index != sub;
			if (moved) {
				sub = a_index;
			}
			break;
		case KitMove::kRow:
			moved = s.top[page] + a_index < count && s.top[page] + a_index != selected;
			if (moved) {
				selected = s.top[page] + a_index;
			}
			break;
		}
		s.top[page] = KitTop(s.top[page], s.selected[page], count);
		if (moved) {
			++(a_key ? s.keys : s.clicks);
			g_refreshNow = true;   // the key thread sends an update at once
		}
		const auto& shown = g_kit.pages[KitPageIndex(s)];
		return std::format("action={} index={} moved={} page={}/{} selected={}", kKitMoveNames[static_cast<std::size_t>(a_move)],
			a_index, moved ? 1 : 0, shown.tab, shown.sub, s.selected[KitPageIndex(s)]);
	}

	// a click's target, by its instance name: a main tab, a sub-tab or a row (its hit area, its bar or its text).
	// CLOSE has its own listener; any other name (the screen, a value row) changes nothing
	std::string KitClick(std::string_view a_name)
	{
		const auto indexAfter = [&](std::string_view a_prefix) -> std::optional<std::size_t> {
			if (!a_name.starts_with(a_prefix)) {
				return std::nullopt;
			}
			const auto digits = a_name.substr(a_prefix.size());
			if (digits.empty() || digits.size() > 2 ||
				!std::ranges::all_of(digits, [](char a_c) { return a_c >= '0' && a_c <= '9'; })) {
				return std::nullopt;
			}
			return static_cast<std::size_t>(std::strtoul(std::string(digits).c_str(), nullptr, 10));
		};
		for (const auto* prefix : { kKitTab, kKitTabMark, kKitTabHit }) {
			if (const auto i = indexAfter(prefix)) {
				return KitAct(KitMove::kTab, *i, false);
			}
		}
		for (const auto* prefix : { kKitSub, kKitSubDim, kKitSubHit }) {
			if (const auto i = indexAfter(prefix)) {
				return KitAct(KitMove::kSub, *i, false);
			}
		}
		for (const auto* prefix : { kKitRowName, kKitRowValue, kKitRowNameSel, kKitRowValueSel, kKitBar, kKitRowHit }) {
			if (const auto i = indexAfter(prefix)) {
				return KitAct(KitMove::kRow, *i, false);
			}
		}
		return a_name == kKitClose ? "action=close (its own listener)" : "action=none";
	}

	// every click in the kit's movie reaches this listener on the root (Scaleform calls it on the menu's thread, the
	// event as the only argument): the event's target, then its instance name
	class KitClickHandler final : public RE::Scaleform::GFx::FunctionHandler
	{
	public:
		void Call(const Params& a_params) override
		{
			const auto                n = ++g_kitClicks;
			RE::Scaleform::GFx::Value target;
			RE::Scaleform::GFx::Value name;
			const bool                gotTarget = a_params.argCount >= 1 && a_params.args && a_params.args[0].IsObject() &&
			                                      a_params.args[0].GetMember("target", &target) && target.IsObject();
			const bool                gotName = gotTarget && target.GetMember("name", &name) && name.IsString();
			const std::string         what = gotName ? name.GetString() : "";
			const auto                action = gotName ? KitClick(what) : std::string("action=none");
			REX::INFO("step=kit_click n={} args={} target={} name={} {}", n, a_params.argCount, gotTarget ? 1 : 0,
				what.empty() ? "-" : what, action);
		}
	};
	KitClickHandler g_kitClickHandler;

	// our function as a_target's "click" listener (CreateFunction, addEventListener), as stage d adds its buttons'
	bool KitAddListener(RE::Scaleform::GFx::ASMovieRootBase* a_root, RE::Scaleform::GFx::Value& a_target,
		RE::Scaleform::GFx::FunctionHandler* a_handler, RE::Scaleform::GFx::Value& a_function)
	{
		a_root->CreateFunction(&a_function, a_handler);
		if (a_function.IsUndefined()) {
			return false;
		}
		std::array<RE::Scaleform::GFx::Value, 2> args;
		args[0] = "click";
		args[1] = a_function;
		return a_target.Invoke("addEventListener", nullptr, args.data(), args.size());
	}

	// once per movie, at kShow: the movie's signature against ours, our listener on the root, and stage d's CLOSE
	// handler on the CLOSE button
	void KitListen(const void* a_menu)
	{
		auto* const root = RootOf(a_menu);
		const auto  movie = MovieOf(a_menu);
		if (!root || g_listenedMovie == movie) {
			return;
		}
		g_listenedMovie = movie;
		RE::Scaleform::GFx::Value top;
		const bool                gotRoot = root->GetVariable(&top, "root") && top.IsObject();
		RE::Scaleform::GFx::Value idField;
		RE::Scaleform::GFx::Value id;
		const bool        gotId = gotRoot && ChildOf(top, kKitId, idField) && idField.GetMember("text", &id) && id.IsString();
		const std::string read = gotId ? id.GetString() : "";
		REX::INFO("step=kit_movie id=\"{}\" expected=\"{}\" match={}", read, KitSignature(), read == KitSignature() ? "yes" : "no");
		RE::Scaleform::GFx::Value rootFunction;
		const bool                rootAdded = gotRoot && KitAddListener(root, top, &g_kitClickHandler, rootFunction);
		REX::INFO("step=listen name=root root={} function_type={} added={} event=click", gotRoot ? 1 : 0,
			TypeCode(rootFunction), rootAdded ? 1 : 0);
		RE::Scaleform::GFx::Value close;
		RE::Scaleform::GFx::Value closeFunction;
		const bool                gotClose = gotRoot && ChildOf(top, kKitClose, close);
		const bool                closeAdded = gotClose && KitAddListener(root, close, &g_closeHandler, closeFunction);
		REX::INFO("step=listen name={} root={} button={} function_type={} added={} event=click", kKitClose, gotRoot ? 1 : 0,
			gotClose ? 1 : 0, TypeCode(closeFunction), closeAdded ? 1 : 0);
	}

	struct KitCount
	{
		std::size_t found = 0;     // children found for a change
		std::size_t set = 0;       // SetMember returned true
		std::size_t match = 0;     // and the value read back
		std::size_t missing = 0;   // no child of that name
	};

	// a field's text, set only if it changed since the last read-back on this movie
	void KitSetText(RE::Scaleform::GFx::Value& a_root, const std::string& a_name, const std::string& a_text, KitCount& a_count)
	{
		if (const auto known = g_kitTexts.find(a_name); known != g_kitTexts.end() && known->second == a_text) {
			return;
		}
		RE::Scaleform::GFx::Value field;
		RE::Scaleform::GFx::Value back;
		if (!ChildOf(a_root, a_name.c_str(), field)) {
			++a_count.missing;
			return;
		}
		++a_count.found;
		a_count.set += field.SetMember("text", RE::Scaleform::GFx::Value(a_text.c_str())) ? 1 : 0;
		if (field.GetMember("text", &back) && back.IsString() && a_text == back.GetString()) {
			++a_count.match;
			g_kitTexts[a_name] = a_text;   // one that did not read back is set again on the next write
		}
	}

	// an object's `visible`, likewise
	void KitSetShown(RE::Scaleform::GFx::Value& a_root, const std::string& a_name, bool a_shown, KitCount& a_count)
	{
		if (const auto known = g_kitShown.find(a_name); known != g_kitShown.end() && known->second == a_shown) {
			return;
		}
		RE::Scaleform::GFx::Value object;
		RE::Scaleform::GFx::Value back;
		if (!ChildOf(a_root, a_name.c_str(), object)) {
			++a_count.missing;
			return;
		}
		++a_count.found;
		a_count.set += object.SetMember("visible", RE::Scaleform::GFx::Value(a_shown)) ? 1 : 0;
		if (object.GetMember("visible", &back) && back.IsBoolean() && back.GetBoolean() == a_shown) {
			++a_count.match;
			g_kitShown[a_name] = a_shown;
		}
	}

	// at kShow (everything, a_show) and every kUpdate (what changed), on the menu's thread: the screen KitCollect built.
	// Logged for n = 1 to 20, then every 20th, and on the first 20 with a child missing or a value not read back
	void KitWrite(const void* a_menu, std::uint32_t a_update, bool a_show)
	{
		auto* const root = RootOf(a_menu);
		if (!root) {
			return;
		}
		static std::atomic<std::uint32_t> problems{ 0 };
		KitScreen                         screen;
		bool                              collected = false;
		{
			std::scoped_lock lock(g_pageLock);
			screen = g_kitScreen;
			collected = g_kitCollected;
		}
		if (a_show) {   // a new movie, or the same one shown again: set everything once
			g_kitTexts.clear();
			g_kitShown.clear();
		}
		RE::Scaleform::GFx::Value top;
		const bool                gotRoot = root->GetVariable(&top, "root") && top.IsObject();
		KitCount                  count;
		if (gotRoot && collected) {
			const auto named = [](const char* a_name, std::size_t a_i) { return std::format("{}{}", a_name, a_i); };
			KitSetText(top, kKitTitle, screen.title, count);
			KitSetText(top, kKitHeader, screen.header, count);
			KitSetText(top, kKitHints, screen.hints, count);
			for (std::size_t i = 0; i < g_kit.tabs.size(); ++i) {
				KitSetText(top, named(kKitTab, i), screen.tabs[i], count);
				KitSetShown(top, named(kKitTabMark, i), i == screen.tab, count);
			}
			for (std::size_t i = 0; i < kKitSubs; ++i) {
				KitSetText(top, named(kKitSub, i), screen.subs[i], count);
				KitSetText(top, named(kKitSubDim, i), screen.subs[i], count);
				KitSetShown(top, named(kKitSub, i), i == screen.sub, count);
				KitSetShown(top, named(kKitSubDim, i), i != screen.sub, count);
			}
			for (std::size_t i = 0; i < kKitRows; ++i) {
				const bool selected = screen.bar && *screen.bar == i;
				KitSetText(top, named(kKitRowName, i), screen.names[i], count);
				KitSetText(top, named(kKitRowValue, i), screen.values[i], count);
				KitSetText(top, named(kKitRowNameSel, i), screen.names[i], count);
				KitSetText(top, named(kKitRowValueSel, i), screen.values[i], count);
				KitSetShown(top, named(kKitRowName, i), !selected, count);
				KitSetShown(top, named(kKitRowValue, i), !selected, count);
				KitSetShown(top, named(kKitRowNameSel, i), selected, count);
				KitSetShown(top, named(kKitRowValueSel, i), selected, count);
				KitSetShown(top, named(kKitBar, i), selected, count);
				KitSetText(top, named(kKitInfoLabel, i), screen.infoLabels[i], count);
				KitSetText(top, named(kKitInfoValue, i), screen.infoValues[i], count);
			}
			KitSetShown(top, kKitMoreUp, screen.moreUp, count);
			KitSetShown(top, kKitMoreDown, screen.moreDown, count);
			for (std::size_t i = 0; i < kKitFooter; ++i) {
				KitSetText(top, named(kKitFoot, i), screen.footer[i], count);
			}
		}
		const auto n = ++g_kitWrites;
		const bool problem = count.missing || count.match != count.found;
		if (n <= 20 || n % 20 == 0 || (problem && problems++ < 20)) {
			std::string rows;
			for (std::size_t i = 0; i < kKitRows && rows.size() < 900; ++i) {
				if (!screen.names[i].empty()) {
					rows += std::format("{}{}{}{}", rows.empty() ? "" : " | ", screen.bar && *screen.bar == i ? ">" : "",
						screen.names[i], screen.values[i]);
				}
			}
			const auto& page = g_kit.pages[screen.page];
			REX::INFO("step=kit n={} update={} show={} page={}/{} root={} collected={} changed={} set={} match={} missing={} "
					  "bar={} footer=\"{}|{}|{}\" rows=\"{}\"",
				n, a_update, a_show ? 1 : 0, page.tab, page.sub, gotRoot ? 1 : 0, collected ? 1 : 0, count.found, count.set,
				count.match, count.missing, screen.bar ? std::to_string(*screen.bar) : "-", screen.footer[0], screen.footer[1],
				screen.footer[2], rows);
		}
	}

	// the kit's keys, every 30 ms on the key thread while the page is open and the game in front: a press moves once; a
	// held Up or Down repeats after 420 ms, every 90 ms. Each press is logged with what it did
	void KitKeys(std::array<std::uint32_t, 6>& a_held)
	{
		for (std::size_t i = 0; i < g_kitKeys.size(); ++i) {
			const auto&   binding = g_kitKeys[i];
			std::uint32_t vk = 0;
			for (std::size_t k = 0; k < binding.count && !vk; ++k) {
				if (W32_IMPL_GetAsyncKeyState(static_cast<std::int32_t>(binding.vk[k])) & 0x8000) {
					vk = binding.vk[k];
				}
			}
			if (!vk) {
				a_held[i] = 0;
				continue;
			}
			const auto ticks = ++a_held[i];
			const bool repeats = binding.move == KitMove::kUp || binding.move == KitMove::kDown;
			if (ticks == 1) {
				REX::INFO("step=kit_key vk={} {}", Hex(vk), KitAct(binding.move, 0, true));
			} else if (repeats && ticks > 14 && (ticks - 14) % 3 == 0) {
				KitAct(binding.move, 0, true);
			}
		}
	}

	// ------------------------------------------------------------------------------------------- the menu's slots
	void Close(std::uint32_t a_n, const char* a_by);

	std::int64_t NowMs()
	{
		return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
	}

	std::uint64_t GfxWatchdogEnter(const char* a_what, bool a_uncapped)
	{
		const GfxWatchdogFrame frame{ ++g_gfxCallSeq, NowMs(), a_what };
		t_gfxWatchdogStack.push_back(frame);
		{
			std::scoped_lock lock(g_gfxWatchdogLock);
			g_gfxActiveFrame = frame;
		}
		if (a_uncapped || ++g_gfxFreqLines <= kMaxGfxFreqLines) {
			REX::INFO("step=gfx_enter seq={} call={}", frame.seq, a_what ? a_what : "unknown");
		}
		return frame.seq;
	}

	void GfxWatchdogExit(std::uint64_t a_seq, const char* a_what, bool a_ok, std::int64_t a_startMs, bool a_uncapped)
	{
		if (!t_gfxWatchdogStack.empty()) {
			if (t_gfxWatchdogStack.back().seq == a_seq) {
				t_gfxWatchdogStack.pop_back();
			} else {
				for (auto it = t_gfxWatchdogStack.rbegin(); it != t_gfxWatchdogStack.rend(); ++it) {
					if (it->seq == a_seq) {
						t_gfxWatchdogStack.erase(std::next(it).base());
						break;
					}
				}
			}
		}
		{
			std::scoped_lock lock(g_gfxWatchdogLock);
			g_gfxActiveFrame = t_gfxWatchdogStack.empty() ? GfxWatchdogFrame{} : t_gfxWatchdogStack.back();
		}
		const auto tookMs = NowMs() - a_startMs;
		if (a_uncapped || !a_ok || g_gfxFreqLines.load() <= kMaxGfxFreqLines) {
			REX::INFO("step=gfx_exit seq={} call={} ok={} took_ms={}", a_seq, a_what ? a_what : "unknown", a_ok ? 1 : 0, tookMs);
		}
	}

	struct MovieCallGuard
	{
		const char*   what = nullptr;
		std::uint64_t seq = 0;
		std::int64_t  startMs = 0;
		bool          uncapped = true;
		bool          ok = false;

		MovieCallGuard(const char* a_what, bool a_uncapped = true) :
			what(a_what), seq(GfxWatchdogEnter(a_what, a_uncapped)), startMs(NowMs()), uncapped(a_uncapped)
		{}

		~MovieCallGuard()
		{
			GfxWatchdogExit(seq, what, ok, startMs, uncapped);
		}
	};

	bool InvokeMovieTracked(RE::Scaleform::GFx::Value& a_target, const char* a_method, RE::Scaleform::GFx::Value* a_ret,
		const RE::Scaleform::GFx::Value* a_args, std::size_t a_count, const char* a_label, bool a_uncapped = true)
	{
		MovieCallGuard guard(a_label, a_uncapped);
		guard.ok = a_target.Invoke(a_method, a_ret, a_args, a_count);
		return guard.ok;
	}

	bool IsFo4ShellActive()
	{
		return g_stage == 2 && g_codeObj && g_codeObjAt == "Menu_mc" && !g_playingBootMovie.load();
	}

	bool ExtractShellUInt32(const RE::Scaleform::GFx::Value& a_val, std::uint32_t& a_out)
	{
		if (a_val.IsUInt()) {
			a_out = a_val.GetUInt();
			return true;
		}
		if (a_val.IsInt() && a_val.GetInt() >= 0) {
			a_out = static_cast<std::uint32_t>(a_val.GetInt());
			return true;
		}
		if (a_val.IsNumber() && std::isfinite(a_val.GetNumber())) {
			const double d = a_val.GetNumber();
			if (d >= 0.0 && d <= 4294967295.0 && std::floor(d) == d) {
				a_out = static_cast<std::uint32_t>(d);
				return true;
			}
		}
		return false;
	}

	bool ExtractShellIndex(const RE::Scaleform::GFx::Value& a_val, std::int32_t& a_out, std::int32_t a_max = 63)
	{
		if (a_val.IsUInt()) {
			const auto u = a_val.GetUInt();
			if (u <= static_cast<std::uint32_t>(a_max)) {
				a_out = static_cast<std::int32_t>(u);
				return true;
			}
			return false;
		}
		if (a_val.IsInt()) {
			const auto i = a_val.GetInt();
			if (i >= 0 && i <= a_max) {
				a_out = i;
				return true;
			}
			return false;
		}
		if (a_val.IsNumber() && std::isfinite(a_val.GetNumber())) {
			const double d = a_val.GetNumber();
			if (d >= 0.0 && d <= static_cast<double>(a_max) && std::floor(d) == d) {
				a_out = static_cast<std::int32_t>(d);
				return true;
			}
		}
		return false;
	}

	struct PendingUserEvent
	{
		std::string name;
		bool        isDown = false;
	};
	std::mutex                      g_shellEventLock;
	std::vector<PendingUserEvent>   g_pendingUserEvents;

	void QueueShellUserEvent(std::string_view a_name, bool a_isDown)
	{
		{
			std::scoped_lock lock(g_shellEventLock);
			if (g_pendingUserEvents.size() < 32) {
				g_pendingUserEvents.push_back({ std::string(a_name), a_isDown });
			}
		}
		if (g_task) {
			g_task->AddTask([]() {
				if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
					queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
				}
			});
		}
	}

	void ClearMovieSessionState(bool a_keepInstallTries = false)
	{
		g_open = false;
		g_closing = false;
		g_playingBootMovie = false;
		g_inDestructionCall = false;
		g_cancelHeld = false;
		g_keyInputHeld = false;
		g_pendingCancelRelease = false;
		{
			std::scoped_lock lock(g_shellEventLock);
			g_pendingUserEvents.clear();
		}
		{
			std::scoped_lock lock(g_deferredLogLock);
			g_deferredDestructionLogs.clear();
		}
		g_dataObj = RE::Scaleform::GFx::Value{};
		g_activeShellMenu = nullptr;
		g_listenedMovie = nullptr;
		g_checkedMovie = nullptr;
		g_codeObjMovie = nullptr;
		g_destroyedCodeObjMovie = nullptr;
		g_shownInvalidatedMovie = nullptr;
		g_populatedLogMovie = nullptr;
		g_vitalsLogMovie = nullptr;
		g_backdropMovie = nullptr;
		g_dateFixLogMovie = nullptr;
		g_dateFixDoneMovie = nullptr;
		g_dateFixDonePage = -1;
		g_hintBarDoneMovie = nullptr;
		g_platformDoneMovie = nullptr;
		g_staticListsInitMovie = nullptr;
		g_createdCodeObjMovie = nullptr;
		if (!a_keepInstallTries) {
			g_codeObjTriedMovie = nullptr;
			g_codeObjTries = 0;
		}
		g_shellKeyPending = 0;
		g_answerPage = -1;
		g_answerTab = -1;
		g_externalTargetPage = -1;
		g_pendingPartialMask = 0;
		g_otherMessages = 0;
		g_codeCalls = 0;
		g_answers = 0;
		g_specialLines = 0;
		g_invFillLogs = 0;
		g_questFillLogs = 0;
		g_invSelectLogs = 0;
		g_shellKeyLines = 0;
		g_soundLines = 0;
		g_cancelLogged = 0;
		g_gfxFreqLines = 0;
		g_currentShellPage = -1;
		g_currentShellTab = 0;
		PipboyMap::OnMenuDestroy();
	}

	const char* OpenBlockingOverlayMenu(RE::UI* a_ui, bool a_topModalOnly = false)
	{
		return fo4sf::FindOpenBlockingMenu(a_ui, a_topModalOnly, false);
	}

	void FailMovieCall(const char* a_where, const std::string& a_detail = "")
	{
		REX::ERROR("step=movie_call_failed where={}{}{} action=close_menu", a_where, a_detail.empty() ? "" : " ", a_detail);
		g_playingBootMovie = false;
		g_bootReopenPage = -1;
		ClearMovieSessionState(true);
		if (g_task) {
			g_task->AddTask([]() { Close(0, "movie_call_failed"); });
		}
	}

	void* MenuDestroy(void* a_self, std::uint32_t a_flags)
	{
		REX::INFO("step=destroy menu={} flags={}", Hex(reinterpret_cast<std::uintptr_t>(a_self)), a_flags);
		// G1 fix: engine kHide clears uiMovie before MenuDestroy, so always clear session movie state unconditionally
		g_codeObjMovie = nullptr;
		ClearMovieSessionState();
		g_engineDtor(a_self, a_flags & ~1u);   // the engine's IMenu destructor, without its delete: the memory is ours
		if (a_flags & 1) {
			std::free(a_self);
		}
		REX::INFO("step=destroyed menu={}", Hex(reinterpret_cast<std::uintptr_t>(a_self)));
		return a_self;
	}

	// the menu's name; while our LoadMovie runs the engine's, Movie= when set (FAL-614: the engine names the movie
	// file Interface/<name>.swf after it, as it loads Interface/FO4SF_PipboyMenu.swf for ours). Each answer with Movie=
	// is counted and logged with the load (step=load_movie ... name_asks=)
	const char* MenuGetName(const void*)
	{
		if (g_loadingMovie.load()) {
			if (g_playingBootMovie.load() && !g_bootMovie.empty()) {
				g_movieNameAsks.fetch_add(1);
				return g_bootMovie.c_str();
			}
			if (!g_movie.empty()) {
				g_movieNameAsks.fetch_add(1);
				return g_movie.c_str();
			}
		}
		return kMenuName;
	}

	// "" binds no menu object in the movie: our movie has no code (a file path here is read as a clip path)
	const char* MenuGetRootPath(const void*) { return ""; }

	std::int32_t MenuGetViewScaleMode(void*) { return 1; }   // Scaleform ShowAll: the whole stage, aspect kept

	// FAL-614 proof 1b (CodeObj=1, Stage=2 with Movie=): a Fallout 4 movie calls its engine through the object at
	// root.BGSCodeObj (D2's names: BGSCodeObj, BGSExternalInterface, PlaySound, HideMenu). The stand-in answers each
	// function named in CodeObjNames with a log line and does nothing else: no sound plays and the menu stays open (F10
	// closes it). A name not listed is not there, as for a movie with no engine object.
	void Close(std::uint32_t a_n, const char* a_by);

	// FAL-614 proof 1d (CodeObjSound=1, with CodeObj=1): route S2. The stand-in's PlaySound plays the player's own
	// converted file <dll folder>/FO4SFPipboyMenuSounds/<name>.wav through Windows audio. Read D4: the boot sequence's
	// three sounds are SNDR records whose files sit in Fallout4 - Sounds.ba2 as XWMA, mono, 44100 Hz; the PC converts
	// them to PCM 16 bit WAVE, named by the editor id the movie passes, and they never enter Git. Each call plays on a
	// waveOut stream and a thread of its own, so the sounds overlap and Windows mixes them (each runs about a second
	// into the next), and closing the menu does not cut one (C ends about 2 s after HideMenu). It does not follow the
	// game's volume sliders.
#pragma pack(push, 1)
	struct WaveFormat   // WAVEFORMATEX
	{
		std::uint16_t tag;
		std::uint16_t channels;
		std::uint32_t rate;
		std::uint32_t bytesPerSecond;
		std::uint16_t blockAlign;
		std::uint16_t bits;
		std::uint16_t extra;
	};
#pragma pack(pop)
	static_assert(sizeof(WaveFormat) == 18);

	struct WaveHeader   // WAVEHDR
	{
		char*          data;
		std::uint32_t  length;
		std::uint32_t  recorded;
		std::uintptr_t user;
		std::uint32_t  flags;
		std::uint32_t  loops;
		WaveHeader*    next;
		std::uintptr_t reserved;
	};
	static_assert(sizeof(WaveHeader) == 48);
	constexpr std::uint32_t kWaveMapper = 0xFFFFFFFF;   // WAVE_MAPPER: the default output
	constexpr std::uint32_t kWaveHeaderDone = 0x1;      // WHDR_DONE

	// why the file is not PCM 16 bit RIFF/WAVE with 1 or 2 channels (empty: it is), with its format and the data's place;
	// the chunks are walked by their sizes, "fmt " before "data", the data cut to whole frames and to the file
	std::string WaveProblem(const std::vector<char>& a_file, WaveFormat& a_wave, std::size_t& a_at, std::size_t& a_bytes)
	{
		const auto u32 = [&](std::size_t a_p) {
			std::uint32_t v;
			std::memcpy(&v, a_file.data() + a_p, sizeof v);
			return v;
		};
		if (a_file.size() < 12 || std::memcmp(a_file.data(), "RIFF", 4) != 0 || std::memcmp(a_file.data() + 8, "WAVE", 4) != 0) {
			return "not_riff_wave";
		}
		bool fmt = false;
		a_bytes = 0;
		for (std::size_t p = 12; p + 8 <= a_file.size();) {
			const std::size_t size = u32(p + 4);
			const auto        body = p + 8;
			const auto        room = a_file.size() - body;
			if (std::memcmp(a_file.data() + p, "fmt ", 4) == 0 && size >= 16 && size <= room) {
				std::memcpy(&a_wave, a_file.data() + body, 16);
				a_wave.extra = 0;
				fmt = true;
			} else if (std::memcmp(a_file.data() + p, "data", 4) == 0 && fmt) {
				a_at = body;
				a_bytes = std::min(size, room);
				break;
			}
			if (size > room) {
				break;
			}
			p = body + size + (size & 1);
		}
		if (!fmt) {
			return "no_fmt";
		}
		if (a_wave.tag != 1 || a_wave.bits != 16) {   // read D4's XWMA is 0x0161: converted on the PC first
			return std::format("not_pcm16 tag={} bits={}", Hex(a_wave.tag), a_wave.bits);
		}
		if (a_wave.channels < 1 || a_wave.channels > 2 || a_wave.rate < 8000 || a_wave.rate > 192000 ||
			a_wave.blockAlign != a_wave.channels * 2) {
			return std::format("bad_format channels={} rate={} block_align={}", a_wave.channels, a_wave.rate, a_wave.blockAlign);
		}
		a_bytes -= a_bytes % a_wave.blockAlign;
		if (a_bytes == 0 || a_bytes > 0xFFFFFFFFu) {
			return "no_data";
		}
		a_wave.bytesPerSecond = a_wave.rate * a_wave.blockAlign;
		return {};
	}

	struct Sound
	{
		std::uint32_t n;
		std::string   name;
		bool          isPerkSound = false;
	};

	// one sound, start to end, on its own thread: read, check, play, wait for the end, close
	std::uint32_t SoundThread(void* a_sound)
	{
		const std::unique_ptr<Sound> sound(static_cast<Sound*>(a_sound));
		const auto                   start = std::chrono::steady_clock::now();
		const auto                   ms = [&]() {
			return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();
		};
		const auto line = [&](std::string_view a_result, const std::string& a_more) {
			if (++g_soundLines <= kMaxSoundLines) {
				REX::INFO("step=sound n={} name={} result={}{}", sound->n, sound->name, a_result, a_more);
			}
		};
		const auto end = [&](std::string_view a_result, const std::string& a_more) {
			line(a_result, a_more);
			--g_soundsPlaying;
			return 0u;
		};
		std::ifstream in(g_soundDir / (sound->name + ".wav"), std::ios::binary | std::ios::ate);
		if (!in) {
			return end("missing", std::format(" file={}/{}.wav", kSoundFolder, sound->name));
		}
		const auto size = static_cast<std::streamoff>(in.tellg());
		if (size <= 0 || static_cast<std::size_t>(size) > kMaxSoundBytes) {
			return end("bad_size", std::format(" bytes={}", static_cast<long long>(size)));
		}
		std::vector<char> file(static_cast<std::size_t>(size));
		in.seekg(0);
		if (!in.read(file.data(), size)) {
			return end("unreadable", "");
		}
		WaveFormat  wave{};
		std::size_t at = 0;
		std::size_t bytes = 0;
		if (const auto why = WaveProblem(file, wave, at, bytes); !why.empty()) {
			return end(why, "");
		}
		const auto length = bytes * 1000 / wave.bytesPerSecond;
		void*      out = nullptr;
		if (const auto r = W32_IMPL_waveOutOpen(&out, kWaveMapper, &wave, std::uintptr_t{ 0 }, std::uintptr_t{ 0 }, 0u); r != 0) {
			return end("open_failed", std::format(" mmresult={}", r));
		}
		if (sound->isPerkSound) {
			std::scoped_lock lock(g_perkSoundLock);
			if (g_activePerkWaveOut) {
				W32_IMPL_waveOutReset(g_activePerkWaveOut);
			}
			g_activePerkWaveOut = out;
		}
		WaveHeader header{};
		header.data = file.data() + at;
		header.length = static_cast<std::uint32_t>(bytes);
		auto r = W32_IMPL_waveOutPrepareHeader(out, &header, static_cast<std::uint32_t>(sizeof header));
		if (r == 0) {
			r = W32_IMPL_waveOutWrite(out, &header, static_cast<std::uint32_t>(sizeof header));
		}
		if (r == 0) {
			line("start", std::format(" rate={} channels={} ms={} playing={}", wave.rate, wave.channels, length, g_soundsPlaying.load()));
			const std::atomic_ref<std::uint32_t> flags(header.flags);   // Windows sets WHDR_DONE from its own thread
			while (!(flags.load() & kWaveHeaderDone) && ms() < static_cast<long long>(length) + 2000) {
				REX::W32::Sleep(20);
			}
		}
		if (sound->isPerkSound) {
			std::scoped_lock lock(g_perkSoundLock);
			if (g_activePerkWaveOut == out) {
				g_activePerkWaveOut = nullptr;
			}
		}
		W32_IMPL_waveOutReset(out);
		W32_IMPL_waveOutUnprepareHeader(out, &header, static_cast<std::uint32_t>(sizeof header));
		W32_IMPL_waveOutClose(out);
		return r == 0 ? end("end", std::format(" took_ms={}", ms())) : end("write_failed", std::format(" mmresult={}", r));
	}

	bool StopActivePerkSound()
	{
		std::scoped_lock lock(g_perkSoundLock);
		if (!g_activePerkWaveOut) {
			return false;
		}
		W32_IMPL_waveOutReset(g_activePerkWaveOut);
		g_activePerkWaveOut = nullptr;
		return true;
	}

	// the stand-in's PlaySound with CodeObjSound=1: its first argument names the file (1 to 64 letters, digits and _)
	void StartSound(std::uint32_t a_n, const RE::Scaleform::GFx::Value* a_arg, bool a_isPerkSound = false)
	{
		std::string name = a_arg && a_arg->IsString() ? std::string(a_arg->GetString()) : std::string();
		const bool  ok = !name.empty() && name.size() <= kMaxName && std::ranges::all_of(name, [](char a_c) {
			return (a_c >= 'A' && a_c <= 'Z') || (a_c >= 'a' && a_c <= 'z') || (a_c >= '0' && a_c <= '9') || a_c == '_';
		});
		if (!ok) {
			if (++g_soundLines <= kMaxSoundLines) {
				REX::INFO("step=sound n={} result=bad_name", a_n);
			}
			return;
		}
		if (++g_soundsPlaying > kMaxSoundsPlaying) {
			--g_soundsPlaying;
			if (++g_soundLines <= kMaxSoundLines) {
				REX::INFO("step=sound n={} name={} result=busy playing={}", a_n, name, kMaxSoundsPlaying);
			}
			return;
		}
		auto       sound = std::make_unique<Sound>(Sound{ a_n, std::move(name), a_isPerkSound });
		const auto thread = REX::W32::CreateThread(nullptr, 0, &SoundThread, sound.get(), 0, nullptr);
		if (!thread) {
			--g_soundsPlaying;
			REX::INFO("step=sound n={} name={} result=no_thread", a_n, sound->name);
			return;
		}
		sound.release();   // the thread owns it now
		REX::W32::CloseHandle(thread);
	}

	// FAL-614 S1-c: one argument of a stand-in call as logged: a string's first 64 characters, a boolean or a number after
	// '#' (#true, #2), else its type (type<n>: an object such as the shell's DataObj, null, undefined)
	std::string ArgText(const RE::Scaleform::GFx::Value& a_arg)
	{
		if (a_arg.IsString()) {
			return std::string(a_arg.GetString()).substr(0, kMaxCodeArg);
		}
		if (a_arg.IsBoolean()) {
			return a_arg.GetBoolean() ? "#true" : "#false";
		}
		if (a_arg.IsInt()) {
			return std::format("#{}", a_arg.GetInt());
		}
		if (a_arg.IsUInt()) {
			return std::format("#{}", a_arg.GetUInt());
		}
		if (a_arg.IsNumber()) {
			return std::format("#{}", a_arg.GetNumber());
		}
		return std::format("type{}", static_cast<int>(a_arg.GetType()));
	}

	// FAL-614 S1-c (CodeObjPages=1): the shell asks its engine for another page or tab (R1: TryToSetPage calls onNewPage,
	// TryToSetTab onNewTab, through BGSExternalInterface; the index is taken to be the one argument, a **hypothesis** the
	// code_call line shows). Noted here, on the menu's thread inside the shell's call, and answered at the menu's next
	// kUpdate (ShellUpdate), after the shell's own call has returned
	struct ShellVitalsSnapshot
	{
		bool                       ready = false;
		double                     currHp = 100.0;
		double                     maxHp = 100.0;
		double                     currAp = 100.0;
		double                     maxAp = 100.0;
		std::uint32_t              xpLevel = 1;
		double                     xpProgressPct = 0.0;
		double                     currWeight = 0.0;
		double                     maxWeight = 150.0;
		std::uint32_t              caps = 0;
		std::string                playerName = "Sole Survivor";
		std::uint32_t              dateMonth = 10;
		std::uint32_t              dateDay = 23;
		std::uint32_t              dateYear = 287;   // DateYear = year - 2000 (fixes 10.23.22287 -> 10.23.2287)
		double                     timeHour = 9.0;
		std::string                locationName = "Commonwealth";
		std::uint32_t              stimpakCount = 0;
		std::uint32_t              radawayCount = 0;
		std::array<double, 6>      limbCondition{ 100.0, 100.0, 100.0, 100.0, 100.0, 100.0 };
		std::uint32_t              headFlags = 0;
		std::uint32_t              bodyFlags = 0;
		double                     rads = 0.0;
		double                     damageResist = 0.0;
		double                     energyResist = 0.0;
		double                     radResist = 0.0;
		std::array<std::int32_t, 7> special{ 5, 5, 5, 5, 5, 5, 5 };
		std::string                specialSource = "fallback";
		std::string                hpSource = "formula";
		std::string                apSource = "formula";
		std::uint32_t              stimpakFormId = 0;
		std::uint32_t              radawayFormId = 0;
	};
	std::mutex                  g_shellSnapLock;
	ShellVitalsSnapshot         g_shellSnap;
	// g_activeShellMenu declared above ClearMovieSessionState as std::atomic<const void*>

	using ShellAvCall_t = float (*)(void*, const void*);
	using ShellLookupEdid_t = void* (*)(const RE::BSFixedString&);

	bool ReadShellActorValue(std::uintptr_t a_avif, float& a_out)
	{
		if (!a_avif || !g_forms.getActorValue) {
			return false;
		}
		const auto     player = Singleton(kPlayerSingleton);
		std::uintptr_t vtable = 0;
		if (!player || !Peek(player + g_forms.ownerOffset, vtable) || vtable != g_forms.ownerVtable) {
			return false;
		}
		const float v = reinterpret_cast<ShellAvCall_t>(g_forms.getActorValue)(
			reinterpret_cast<void*>(player + g_forms.ownerOffset), reinterpret_cast<const void*>(a_avif));
		if (!std::isfinite(v)) {
			return false;
		}
		a_out = v;
		return true;
	}

	std::uintptr_t LookupFormByEditorIdChecked(const char* a_editorId, std::string_view a_rttiTail)
	{
		const std::uint32_t rva = g_shellLookupEditorIdRva ? g_shellLookupEditorIdRva : g_armLookupRva;
		if (!rva || !a_editorId || !*a_editorId) {
			return 0;
		}
		static std::unordered_map<std::string, RE::BSFixedString*> interned;
		auto it = interned.find(a_editorId);
		if (it == interned.end()) {
			it = interned.emplace(a_editorId, new RE::BSFixedString(a_editorId)).first;
		}
		const auto form = reinterpret_cast<std::uintptr_t>(
			reinterpret_cast<ShellLookupEdid_t>(g_base + rva)(*it->second));
		ObjectType t;
		return (form && IsType(form, a_rttiTail, t)) ? form : 0;
	}

	void ShellCalendarFromDays(float a_daysPassed, std::uint32_t& a_month, std::uint32_t& a_day, std::uint32_t& a_yearShort)
	{
		static constexpr std::array<int, 12> kMonthDays{ 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 };
		int total = std::max(0, static_cast<int>(std::floor(a_daysPassed)));
		int y = 2287;
		int m = 9;   // October 23, 2287
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
		a_yearShort = static_cast<std::uint32_t>(y >= 2000 ? (y - 2000) : y);
	}

	std::string CleanDisplayName(const std::string& a_formatted)
	{
		if (a_formatted.empty() || a_formatted == "?" || a_formatted.starts_with("NO NAME")) {
			return {};
		}
		const auto paren = a_formatted.rfind(" (");
		if (paren != std::string::npos && a_formatted.back() == ')' && paren + 11 == a_formatted.size()) {
			return a_formatted.substr(0, paren);
		}
		return a_formatted;
	}

	struct ShellInvEntry
	{
		std::uint32_t nodeId = 0;
		std::uint32_t invIndex = 0;
		std::uint32_t formId = 0;
		std::uint8_t  formType = 0;
		std::string   name;
		std::uint32_t count = 1;
		std::uint32_t equipState = 0;
		std::uint32_t filterFlag = 0x08u;
		double        weight = 0.0;
		std::int32_t  value = 0;
		std::int32_t  favorite = -1;
		bool          canFavorite = false;
	};

	struct ShellObjectiveEntry
	{
		std::uint16_t number = 0;
		std::uint8_t  state = 1;   // 1 = shown/active, 3 = completed
		std::string   text;
	};

	struct ShellQuestEntry
	{
		std::uint32_t                    formId = 0;
		std::string                      name;
		std::string                      description;
		bool                             completed = false;
		bool                             active = true;
		std::int32_t                     sortVal = 0;
		std::vector<ShellObjectiveEntry> objectives;
	};

	struct ShellWorkshopEntry
	{
		std::string   name;
		std::int32_t  mapMarkerId = -1;
		std::array<std::int32_t, 7> values{ 5, 80, 6, 6, 5, 8, 6 };
	};

	struct ShellStatCategory
	{
		std::string                                      name;
		std::vector<std::pair<std::string, std::string>> rows;
	};

	struct ShellInvDataSnapshot
	{
		std::vector<ShellInvEntry>      items;
		std::uint64_t                   totalItemCount = 0;
		std::vector<ShellQuestEntry>    quests;
		std::vector<ShellWorkshopEntry> workshops;
		std::vector<ShellStatCategory>  statCategories;
	};
	std::mutex                         g_invDataLock;
	ShellInvDataSnapshot               g_invDataSnap;
	std::array<std::int32_t, 7>        g_invSelectedPerTab{ 0, 0, 0, 0, 0, 0, 0 };
	std::array<std::uint32_t, 12>      g_quickkeyFormIds{};
	std::set<std::uint32_t>            g_inactiveQuestFormIds;
	std::set<std::uint32_t>            g_taggedComponentFormIds;

	void SortShellInvEntries(std::vector<ShellInvEntry>& a_items, std::uint32_t a_sortMode)
	{
		std::ranges::stable_sort(a_items, [a_sortMode](const ShellInvEntry& a, const ShellInvEntry& b) {
			if (a_sortMode == 1u) {   // Type / Equip state
				if (a.equipState != b.equipState) {
					return a.equipState > b.equipState;
				}
				if (a.filterFlag != b.filterFlag) {
					return a.filterFlag < b.filterFlag;
				}
			} else if (a_sortMode == 2u) {   // Weight descending
				if (std::abs(a.weight - b.weight) > 1e-4) {
					return a.weight > b.weight;
				}
			} else if (a_sortMode == 3u) {   // Value descending
				if (a.value != b.value) {
					return a.value > b.value;
				}
			}
			return a.name < b.name;
		});
		for (std::uint32_t idx = 0; idx < a_items.size(); ++idx) {
			a_items[idx].nodeId = idx;
		}
	}

	std::uint32_t InvFilterFlagForForm(std::uintptr_t a_obj, const ObjectType& a_type, std::uint8_t a_formType)
	{
		switch (a_formType) {
		case 0x30: return 1u << 0;   // kWEAP -> Weapons (tab 0)
		case 0x22: return 1u << 1;   // kARMO -> Apparel (tab 1)
		case 0x36:                   // kALCH -> Aid (tab 2)
		case 0x26: return 1u << 2;   // kINGR -> Aid (tab 2)
		case 0x98: return 1u << 5;   // kOMOD -> Mods (tab 5)
		case 0x31: return 1u << 6;   // kAMMO -> Ammo (tab 6)
		case 0x9F: return 1u << 4;   // kIRES (BGSResource) -> Junk (tab 4)
		case 0x28:                   // kMISC
		case 0x23:                   // kBOOK
		case 0x35:                   // kKEYM
		case 0x39:                   // kNOTE
		case 0x3D:                   // kSLGM
		{
			if (a_formType == 0x28) {
				std::uintptr_t edEntry = 0;
				std::string    edid;
				if (Peek(a_obj + 0x30, edEntry) && ReadPoolString(edEntry, edid)) {
					if (edid.find("Junk") != std::string::npos || edid.find("junk") != std::string::npos ||
						edid.find("Scrap") != std::string::npos || edid.find("scrap") != std::string::npos) {
						return 1u << 4;   // Junk (tab 4)
					}
				}
			}
			(void)a_type;
			return 1u << 3;   // Misc (tab 3)
		}
		default:
			return 0u;
		}
	}

	std::string ReadObjectiveDisplayText(std::uintptr_t a_objective, std::uint16_t a_number)
	{
		for (const std::size_t off : { std::size_t{ 0x00 }, std::size_t{ 0x08 }, std::size_t{ 0x10 } }) {
			std::uintptr_t entry = 0;
			std::string    txt;
			if (!Peek(a_objective + off, entry) || !entry || !ReadPoolString(entry, txt) || txt.size() < 2 || txt.size() > 120) {
				continue;
			}
			const bool printable = std::ranges::all_of(txt, [](unsigned char c) { return c >= 0x20 && c < 0x7F; });
			if (printable) {
				return txt;
			}
		}
		return std::format("Objective {}", a_number);
	}

	std::uintptr_t ShellFormLookup(std::uint32_t a_formId)
	{
		if (!a_formId || !g_rva[kLookupById]) {
			return 0;
		}
		return reinterpret_cast<std::uintptr_t>(reinterpret_cast<LookupById_t>(Address(kLookupById))(a_formId));
	}

	struct CachedQuestForm
	{
		std::string    pluginName;
		std::uint32_t  localId = 0;
		std::uint32_t  formId = 0;
		std::uintptr_t form = 0;
	};
	std::vector<CachedQuestForm> g_cachedQuestForms;
	std::uintptr_t               g_questCacheHandler = 0;
	bool                         g_questCacheBuilt = false;
	bool                         g_questCacheWorkshopLoaded = false;

	void CollectQuestAndStatsMainThread(const ShellVitalsSnapshot& a_vitals, float a_daysPassed, ShellInvDataSnapshot& a_out)
	{
		std::set<std::uint32_t> inactiveCopy;
		{
			std::scoped_lock lock(g_invDataLock);
			inactiveCopy = g_inactiveQuestFormIds;
		}

		const auto handler = Singleton(kDataHandlerSingleton);
		ObjectType hType;
		const bool wantFullData = g_invDataAnswers;
		std::vector<PipboyMap::QuestObjectiveMarker> activeQuestMarkers;
		std::size_t totalObjectives = 0;

		// R6: Discover FO4SF*/FO4Core* TESQuest* forms once after PostDataLoad (0x800..0xBFF per plugin) and cache them,
		// instead of calling LookupById 1,024 times per plugin on every 500 ms vitals tick.
		if (!g_questCacheBuilt || g_questCacheHandler != handler) {
			g_cachedQuestForms.clear();
			g_questCacheWorkshopLoaded = false;
			g_questCacheHandler = handler;
			std::set<std::uint32_t> seenCached;
			std::size_t             pluginsScanned = 0;
			std::size_t             idsScanned = 0;
			if (IsType(handler, "TESDataHandler@@", hType)) {
				for (std::size_t kind = 0; kind < 3; ++kind) {
					ArrayHead files{};
					if (!Peek(handler + kFileCollectionAt + kind * 0x10, files) || files.size > files.capacity ||
						files.size > kKitMaxFiles || (files.size && !files.data)) {
						continue;
					}
					for (std::uint32_t fi = 0; fi < files.size; ++fi) {
						std::uintptr_t                  file = 0;
						ObjectType                      fileType;
						std::array<char, kFileNameSize> fname{};
						if (!Peek(files.data + fi * sizeof(std::uintptr_t), file) || !file ||
							!TypeOf(file, fileType) || !IsFileType(fileType) ||
							!Peek(file + kFileNameAt, fname.data(), fname.size())) {
							continue;
						}
						const std::string_view sv(fname.data(), strnlen(fname.data(), fname.size()));
						if (sv.size() < 6 || !(SameText(sv.substr(0, 5), "FO4SF") || SameText(sv.substr(0, 7), "FO4Core"))) {
							continue;
						}
						++pluginsScanned;
						if (SameText(sv, "FO4SFWorkshop.esm")) {
							g_questCacheWorkshopLoaded = true;
						}
						std::uint8_t                compile = 0;
						std::array<std::uint8_t, 4> fidx{};
						Peek(file + kFileCompileIndexAt, compile);
						Peek(file + kFileIndexAt, fidx.data(), fidx.size());
						const std::uint32_t smallIdx = fidx[2] | (fidx[3] << 8);
						for (std::uint32_t localId = 0x800; localId <= 0xBFF; ++localId) {
							++idsScanned;
							std::uint32_t fid = 0;
							if (kind == 0) {
								const std::uint8_t topByte = compile != 0xFF && compile != 0 ? compile : fidx[0];
								if (topByte == 0 || topByte >= 0xFE) {
									continue;
								}
								fid = (std::uint32_t{ topByte } << 24) | localId;
							} else if (kind == 1) {
								fid = 0xFE000000u | ((smallIdx & 0xFFF) << 12) | (localId & 0xFFF);
							} else {
								fid = 0xFD000000u | (std::uint32_t{ fidx[1] } << 16) | (localId & 0xFFFF);
							}
							if (!fid || seenCached.contains(fid)) {
								continue;
							}
							const auto form = ShellFormLookup(fid);
							ObjectType qType;
							if (!form || !IsType(form, "TESQuest@@", qType)) {
								continue;
							}
							seenCached.insert(fid);
							g_cachedQuestForms.push_back({ std::string(sv), localId, fid, form });
						}
					}
				}
				g_questCacheBuilt = true;
				REX::INFO("step=quest_cache_build plugins={} quests={} workshop={} scanned={}",
					pluginsScanned, g_cachedQuestForms.size(), g_questCacheWorkshopLoaded ? 1 : 0, idsScanned);
			}
		}

		const auto processCachedQuest = [&](const CachedQuestForm& a_cached) {
			const std::string_view a_pluginName = a_cached.pluginName;
			const std::uint32_t    a_localId = a_cached.localId;
			const std::uint32_t    a_fid = a_cached.formId;
			const auto             form = a_cached.form;
			ObjectType             qType;
			if (!form || !IsType(form, "TESQuest@@", qType)) {
				return;
			}
			std::uint16_t qFlags = 0;
			if (!Peek(form + kQuestFlagsAt, qFlags)) {
				return;
			}
			ArrayHead head{};
			std::vector<ShellObjectiveEntry> objs;
			if (Peek(form + kQuestObjectivesAt, head) && head.size <= head.capacity && head.size <= kQuestObjectivesMax &&
				(!head.size || head.data)) {
				for (std::uint32_t oi = 0; oi < head.size; ++oi) {
					std::uintptr_t objPtr = 0;
					std::uintptr_t owner = 0;
					std::uint16_t  num = 0;
					std::uint8_t   st = 0;
					if (Peek(head.data + 8ull * oi, objPtr) && objPtr &&
						Peek(objPtr + kObjectiveOwnerAt, owner) && owner == form &&
						Peek(objPtr + kObjectiveNumberAt, num) && Peek(objPtr + kObjectiveStateAt, st) &&
						(st == 1 || st == 3)) {
						std::string objText = ReadObjectiveDisplayText(objPtr, num);
						if (objText == std::format("Objective {}", num)) {
							PipboyMap::QuestObjectiveCatalogEntry cat{};
							if (PipboyMap::LookupQuestObjectiveCatalog(a_pluginName, a_localId, num, cat) &&
								!cat.fallbackText.empty()) {
								objText = cat.fallbackText;
							}
						}
						objs.push_back({ num, st, std::move(objText) });
					}
				}
			}
			const bool running = (qFlags & 0x0001u) != 0;
			const bool completed = (qFlags & 0x0002u) != 0;
			if (!running && !completed && objs.empty()) {
				return;
			}
			std::string qName;
			if (const auto fnAt = BaseOffset(qType, "TESFullName@@"); fnAt && CheckSubobject(form, qType, *fnAt)) {
				std::uintptr_t fnEntry = 0;
				if (Peek(form + *fnAt + kFullNameAt, fnEntry)) {
					ReadPoolString(fnEntry, qName);
				}
			}
			const bool hasDisplayName = !qName.empty();
			if (!hasDisplayName) {
				qName = EditorIdOf(form, "TESQuest@@", 0x30);
			}
			if (objs.empty() && (!hasDisplayName || qName.find("_Probe") != std::string::npos ||
				qName.find("_Bootstrap") != std::string::npos || qName.find("Keeper") != std::string::npos ||
				qName.find("COMPreston") != std::string::npos || qName.find("_Travel") != std::string::npos ||
				qName.find("_CoreCandidate") != std::string::npos)) {
				return;   // Skip silent internal controller/utility quests with no player display name or objectives
			}
			if (qName.empty()) {
				qName = std::format("Quest {:08X}", a_fid);
			}
			const bool isCompleted = completed && !running;
			const bool isActive = !isCompleted && !inactiveCopy.contains(a_fid);
			totalObjectives += objs.size();

			// Prefer the first active (uncompleted, state == 1) objective for the quest card summary & map marker
			std::string firstDesc;
			for (const auto& ob : objs) {
				if (ob.state == 1) {
					firstDesc = ob.text;
					if (isActive && !isCompleted) {
						PipboyMap::QuestObjectiveCatalogEntry cat{};
						if (PipboyMap::LookupQuestObjectiveCatalog(a_pluginName, a_localId, ob.number, cat)) {
							activeQuestMarkers.push_back({
								a_fid,
								ob.number,
								cat.xFo4,
								cat.yFo4,
								qName,
								ob.text,
								cat.locationLabel,
							});
						}
					}
					break;
				}
			}
			if (!wantFullData) {
				return;   // R6: skip DATA quest/workshop/stat list work when InvDataAnswers=0
			}
			ShellQuestEntry qe;
			qe.formId = a_fid;
			qe.name = std::move(qName);
			qe.completed = isCompleted;
			qe.active = isActive;
			qe.sortVal = qe.completed ? 1 : 0;
			qe.description = !firstDesc.empty() ? std::move(firstDesc) : (!objs.empty() ? objs.front().text : std::string{});
			qe.objectives = std::move(objs);
			a_out.quests.push_back(std::move(qe));
		};

		for (const auto& cached : g_cachedQuestForms) {
			processCachedQuest(cached);
		}

		const std::size_t qmCount = activeQuestMarkers.size();
		PipboyMap::SetActiveQuestObjectives(std::move(activeQuestMarkers));

		if (!wantFullData) {
			return;
		}

		std::ranges::stable_sort(a_out.quests, [](const ShellQuestEntry& a, const ShellQuestEntry& b) {
			if (a.completed != b.completed) {
				return !a.completed;
			}
			return a.name < b.name;
		});

		// PLACEHOLDER (A13): WorkshopsList is a fixed static placeholder row when FO4SFWorkshop.esm is loaded; not live settlement data
		if (g_questCacheWorkshopLoaded) {
			ShellWorkshopEntry ws;
			ws.name = "Sanctuary Hills (Placeholder)";
			ws.mapMarkerId = 0;
			ws.values = { 5, 80, 6, 6, 5, 8, 6 };
			a_out.workshops.push_back(std::move(ws));
		}

		std::size_t activeQuests = 0;
		std::size_t completedQuests = 0;
		for (const auto& q : a_out.quests) {
			q.completed ? ++completedQuests : ++activeQuests;
		}
		static std::uint32_t s_questCollectLogs = 0;
		static std::size_t   s_lastLoggedQ = static_cast<std::size_t>(-1);
		static std::size_t   s_lastLoggedObj = static_cast<std::size_t>(-1);
		static std::size_t   s_lastLoggedQm = static_cast<std::size_t>(-1);
		if ((a_out.quests.size() != s_lastLoggedQ || totalObjectives != s_lastLoggedObj || qmCount != s_lastLoggedQm) &&
			++s_questCollectLogs <= 64) {
			s_lastLoggedQ = a_out.quests.size();
			s_lastLoggedObj = totalObjectives;
			s_lastLoggedQm = qmCount;
			REX::INFO("step=quests_collect n={} active={} completed={} objectives={} quest_markers={}",
				a_out.quests.size(), activeQuests, completedQuests, totalObjectives, qmCount);
		}
		a_out.statCategories = {
			{ "General", {
				{ "Days Passed", std::format("{}", std::max(0, static_cast<int>(std::floor(a_daysPassed)))) },
				{ "Caps Carried", std::format("{}", a_vitals.caps) },
				{ "Items Carried", std::format("{}", a_out.totalItemCount) },
				{ "Stimpaks Carried", std::format("{}", a_vitals.stimpakCount) },
			} },
			{ "Quest", {
				{ "Active Quests", std::format("{}", activeQuests) },
				{ "Quests Completed", std::format("{}", completedQuests) },
			} },
			{ "Combat", {
				{ "Player Level", std::format("{}", a_vitals.xpLevel) },
				{ "Radiation (RADS)", std::format("{:.0f}", a_vitals.rads) },
			} },
		};
	}

	void LogCoreValueResolve(std::string_view a_name, std::uint32_t a_localId, std::uint32_t a_resolvedFormId)
	{
		REX::INFO("step=core_value_resolve name={} source=FO4SFCoreValues.esm:{:06X} found={} form={:08X}",
			a_name, a_localId, a_resolvedFormId ? 1 : 0, a_resolvedFormId);
	}

	// Main thread only: collects player vitals, S.P.E.C.I.A.L. (FO4SFCoreValues.esm 0x810..0x816), Rads (0x800),
	// Stimpak/RadAway/Caps counts, limb conditions, and (only when a_targetPage == 3) MAP state before kShow / throttled update
	void CollectShellVitalsMainThread(std::uint32_t a_targetPage)
	{
		if ((!g_codeObj && !g_specialMenu) || !g_shellExtraIdsReady) {
			PipboyMap::CollectStateForPage(static_cast<std::int32_t>(a_targetPage));
			return;
		}
		PageScan();
		FindGlobalValue();

		static bool                         extraResolved = false;
		static bool                         radsFormLogged = false;
		static bool                         specialLogged = false;
		static std::uintptr_t               oxygenAvif = 0;
		static std::uintptr_t               drAvif = 0;
		static std::uintptr_t               erAvif = 0;
		static std::uintptr_t               rrAvif = 0;
		static std::uintptr_t               hardcoreBlockedGlob = 0;
		static std::array<std::uintptr_t, 6> limbAvifs{};
		static std::array<std::uintptr_t, 7> specialAvifs{};
		static std::string                  resolvedSpecialSource = "fallback";
		static std::uint32_t                stimpakId = 0;
		static std::uint32_t                radawayId = 0;
		static double                       highWaterHp = 100.0;
		static double                       highWaterAp = 100.0;

		if (!extraResolved) {
			extraResolved = true;
			AcceptById(kOxygenAvifId, "Oxygen", "ActorValueInfo@@", kAvifEditorIdAt, oxygenAvif);
			AcceptById(kDamageResistAvifId, "DamageResist", "ActorValueInfo@@", kAvifEditorIdAt, drAvif);
			AcceptById(kEnergyResistAvifId, "EnergyResist", "ActorValueInfo@@", kAvifEditorIdAt, erAvif);
			for (std::size_t i = 0; i < kLimbConditionAvifIds.size(); ++i) {
				AcceptById(kLimbConditionAvifIds[i], "LimbCondition", "ActorValueInfo@@", kAvifEditorIdAt, limbAvifs[i]);
			}
			std::string radsDetail;
			const auto  radsStoreId = KitFileForm("FO4SFCoreValues.esm", kRadsLocalId, "ActorValueInfo@@", radsDetail);
			if (radsStoreId) {
				AcceptById(radsStoreId, "FO4SF_Rads", "ActorValueInfo@@", kAvifEditorIdAt, g_forms.rads);
			}
			LogCoreValueResolve("FO4SF_Rads", kRadsLocalId, g_forms.rads ? radsStoreId : 0u);

			std::string detail;
			const auto  rrId = KitFileForm("FO4SFCoreValues.esm", kCoreRadResistLocalId, "ActorValueInfo@@", detail);
			if (rrId) {
				AcceptById(rrId, "FO4SF_RadResist", "ActorValueInfo@@", kAvifEditorIdAt, rrAvif);
			} else {
				rrAvif = LookupFormByEditorIdChecked("FO4SF_RadResist", "ActorValueInfo@@");
			}
			LogCoreValueResolve("FO4SF_RadResist", kCoreRadResistLocalId, rrAvif ? rrId : 0u);

			std::size_t fromCoreStore = 0;
			std::size_t fromEditorId = 0;
			std::size_t fromVanilla = 0;
			for (std::size_t i = 0; i < kSpecialEditorIds.size(); ++i) {
				std::string        spDetail;
				const std::uint32_t spLocalId = kCoreSpecialFirstLocalId + static_cast<std::uint32_t>(i);
				const auto         spId = KitFileForm("FO4SFCoreValues.esm", spLocalId, "ActorValueInfo@@", spDetail);
				if (spId) {
					AcceptById(spId, kSpecialEditorIds[i], "ActorValueInfo@@", kAvifEditorIdAt, specialAvifs[i]);
					if (specialAvifs[i]) {
						++fromCoreStore;
					}
				}
				LogCoreValueResolve(kSpecialEditorIds[i], spLocalId, specialAvifs[i] ? spId : 0u);
				if (!specialAvifs[i]) {
					specialAvifs[i] = LookupFormByEditorIdChecked(kSpecialEditorIds[i], "ActorValueInfo@@");
					if (specialAvifs[i]) {
						++fromEditorId;
					}
				}
				if (!specialAvifs[i]) {
					// Fallback to Starfield AVIF 0x2C2..0x2C8 if FO4SFCoreValues.esm is absent in a standalone probe
					AcceptById(0x2C2u + static_cast<std::uint32_t>(i), kSpecialNames[i], "ActorValueInfo@@", kAvifEditorIdAt, specialAvifs[i]);
					if (specialAvifs[i]) {
						++fromVanilla;
					}
				}
			}
			if (fromCoreStore == 7) {
				resolvedSpecialSource = "FO4SFCoreValues.esm";
			} else if (fromCoreStore + fromEditorId == 7) {
				resolvedSpecialSource = "LookupByEditorID";
			} else if (fromVanilla > 0) {
				resolvedSpecialSource = "Starfield.esm";
			}
			std::string stimDetail;
			stimpakId = KitFileForm("FO4SFCoreValues.esm", kCoreStimpakLocalId, "AlchemyItem@@", stimDetail);
			LogCoreValueResolve("FO4SF_Stimpak", kCoreStimpakLocalId, stimpakId);
			if (!stimpakId) {
				if (const auto f = LookupFormByEditorIdChecked("FO4SF_Stimpak", "AlchemyItem@@")) {
					Peek(f + kFormIdAt, stimpakId);
				}
			}
			std::string radDetail;
			radawayId = KitFileForm("FO4SFRads.esm", kRadsRadawayLocalId, "AlchemyItem@@", radDetail);
			if (!radawayId) {
				if (const auto f = LookupFormByEditorIdChecked("FO4SF_RadAway", "AlchemyItem@@")) {
					Peek(f + kFormIdAt, radawayId);
				}
			}
			std::string hcDetail;
			const auto  hcId = KitFileForm("FO4SFCoreValues.esm", kCoreHardcoreFastTravelBlockedId, "TESGlobal@@", hcDetail);
			if (hcId) {
				AcceptById(hcId, "FO4SF_HardcoreFastTravelBlocked", "TESGlobal@@", kGlobalEditorIdAt, hardcoreBlockedGlob);
			}
			LogCoreValueResolve("FO4SF_HardcoreFastTravelBlocked", kCoreHardcoreFastTravelBlockedId, hardcoreBlockedGlob ? hcId : 0u);
		}

		bool hcBlocked = false;
		if (hardcoreBlockedGlob) {
			const std::size_t valAt = g_forms.globalValueAt ? g_forms.globalValueAt : kGlobalValueAt;
			float             hcVal = 0.0f;
			if (Peek(hardcoreBlockedGlob + valAt, hcVal) && std::isfinite(hcVal)) {
				hcBlocked = hcVal >= 0.5f;
			}
		}
		g_shellHardcoreFastTravelBlocked.store(hcBlocked);

		if (!g_forms.rads) {
			g_forms.rads = LookupFormByEditorIdChecked("FO4SF_Rads", "ActorValueInfo@@");
		}
		if (g_forms.rads && !radsFormLogged) {
			std::uint32_t radsFid = 0;
			if (Peek(g_forms.rads + kFormIdAt, radsFid) && radsFid != 0) {
				radsFormLogged = true;
				REX::INFO("step=shell_rads_form editor_id=FO4SF_Rads form={:08X}", radsFid);
			}
		}

		ShellVitalsSnapshot next;
		next.ready = true;
		next.specialSource = resolvedSpecialSource;
		next.stimpakFormId = stimpakId;
		next.radawayFormId = radawayId;

		ShellInvDataSnapshot invDataNext;
		std::array<std::uint32_t, 12> quickkeysCopy{};
		{
			std::scoped_lock lock(g_invDataLock);
			quickkeysCopy = g_quickkeyFormIds;
		}

		// 1. S.P.E.C.I.A.L. (7 values, safe fallback 5)
		std::string spSummary;
		for (std::size_t i = 0; i < 7; ++i) {
			float sv = 5.0f;
			int   iv = 5;
			if (ReadShellActorValue(specialAvifs[i], sv) && sv >= 1.0f && sv <= 99.0f) {
				iv = static_cast<int>(std::lround(sv));
			}
			next.special[i] = iv;
			if (!specialLogged) {
				std::uint32_t sfid = 0;
				if (specialAvifs[i]) {
					Peek(specialAvifs[i] + kFormIdAt, sfid);
				}
				spSummary += std::format("{}{}:{}:{:08X}", i ? "," : "", kSpecialNames[i], iv, sfid);
			}
		}
		if (!specialLogged) {
			specialLogged = true;
			REX::INFO("step=shell_special values={}", spSummary);
		}

		// 2. Player Level, Name, XPProgressPct (0..1), Inventory & Aid counts
		double carriedWeight = 0.0;
		if (CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk)) {
			const auto     player = Singleton(kPlayerSingleton);
			std::uintptr_t base = 0;
			ObjectType     npcType;
			if (Peek(player + kBaseObjectAt, base) && IsType(base, "TESNPC@@", npcType)) {
				if (const auto at = BaseOffset(npcType, "TESActorBaseData@@"); at && CheckSubobject(base, npcType, *at)) {
					std::uint16_t lvl = 1;
					if (Peek(base + *at + kLevelAt, lvl) && lvl >= 1) {
						next.xpLevel = lvl;
					}
				}
				const auto nm = CleanDisplayName(NameText("player_name", base, npcType));
				if (!nm.empty()) {
					next.playerName = nm;
				}
			}

			// Inventory scan: Caps (0xF), FO4SF_Stimpak, FO4SF_RadAway, and UI-2 InvItems (Fallout items only)
			std::uint32_t  fo4StimpakCount = 0;
			std::uintptr_t invList = 0;
			ObjectType     listType;
			ArrayHead      items{};
			if (Peek(player + kInventoryListAt, invList) && IsType(invList, "BGSInventoryList@@", listType) &&
				Peek(invList + kInventoryDataAt, items) && items.size <= items.capacity && items.size <= kKitMaxItems &&
				(!items.size || items.data)) {
				for (std::uint32_t i = 0; i < items.size; ++i) {
					const auto     item = items.data + i * kInventoryItemSize;
					std::uintptr_t obj = 0;
					ObjectType     objType;
					if (!Peek(item, obj) || !obj || !TypeOf(obj, objType)) {
						continue;
					}
					std::uint32_t fid = 0;
					if (!Peek(obj + kFormIdAt, fid) || !fid) {
						continue;
					}
					const bool isAidOrCaps = (fid == kCreditsFormId || (stimpakId && fid == stimpakId) ||
					                          (radawayId && fid == radawayId));
					if (!isAidOrCaps && !g_invDataAnswers) {
						continue;
					}
					ArrayHead     stacks{};
					std::uint64_t total = 0;
					bool          okStacks = Peek(item + kItemStacksAt, stacks) && stacks.size <= stacks.capacity &&
					                         stacks.size <= kKitMaxItems && (!stacks.size || stacks.data);
					for (std::uint32_t s = 0; okStacks && s < stacks.size; ++s) {
						std::uint32_t cnt = 0;
						okStacks = Peek(stacks.data + s * kStackSize + kStackCountAt, cnt);
						total += cnt;
					}
					if (!okStacks || total == 0) {
						continue;
					}
					const auto clamped = static_cast<std::uint32_t>(std::min<std::uint64_t>(total, 999999999ull));
					if (fid == kCreditsFormId) {
						next.caps += clamped;
						continue;
					}
					if (stimpakId && fid == stimpakId) {
						fo4StimpakCount += clamped;
					} else if (radawayId && fid == radawayId) {
						next.radawayCount += clamped;
					}

					if (g_invDataAnswers && BaseOffset(objType, "TESBoundObject@@")) {
						std::uint8_t ftype = 0;
						Peek(obj + kFormTypeAt, ftype);
						const auto filterFlag = InvFilterFlagForForm(obj, objType, ftype);
						if (filterFlag != 0) {
							std::string itemName;
							if (const auto fnAt = BaseOffset(objType, "TESFullName@@"); fnAt && CheckSubobject(obj, objType, *fnAt)) {
								std::uintptr_t fnEntry = 0;
								if (Peek(obj + *fnAt + kFullNameAt, fnEntry)) {
									ReadPoolString(fnEntry, itemName);
								}
							}
							if (itemName.empty()) {
								continue;   // Skip nameless internal token forms
							}
							float itemWt = 0.0f;
							if (const auto wtAt = BaseOffset(objType, "TESWeightForm@@"); wtAt && CheckSubobject(obj, objType, *wtAt)) {
								float rawWt = 0.0f;
								if (Peek(obj + *wtAt + 0x08, rawWt) && std::isfinite(rawWt) && rawWt >= 0.0f) {
									itemWt = rawWt;
								}
							}
							std::int32_t itemVal = 0;
							if (const auto valAt = BaseOffset(objType, "TESValueForm@@"); valAt && CheckSubobject(obj, objType, *valAt)) {
								std::int32_t rawVal = 0;
								if (Peek(obj + *valAt + 0x08, rawVal) && rawVal >= 0) {
									itemVal = rawVal;
								}
							}
							std::uint32_t itemFlags = 0;
							const bool equipped = Peek(item + kItemFlagsAt, itemFlags) && (itemFlags & 0x7u) != 0;
							std::int32_t favSlot = -1;
							for (std::size_t qs = 0; qs < quickkeysCopy.size(); ++qs) {
								if (quickkeysCopy[qs] == fid) {
									favSlot = static_cast<std::int32_t>(qs);
									break;
								}
							}
							const bool favAllowed = (ftype == 0x30 || ftype == 0x22 || ftype == 0x36 || ftype == 0x26);
							carriedWeight += static_cast<double>(itemWt) * static_cast<double>(clamped);
							invDataNext.totalItemCount += clamped;
							invDataNext.items.push_back({
								0u,
								i,
								fid,
								ftype,
								std::move(itemName),
								clamped,
								equipped ? 1u : 0u,
								filterFlag,
								static_cast<double>(itemWt),
								itemVal,
								favSlot,
								favAllowed,
							});
						}
					}
				}
			}
			if (fo4StimpakCount > 0 && stimpakId != 0) {
				next.stimpakCount = fo4StimpakCount;
				next.stimpakFormId = stimpakId;
			}
		}

		// 3. Health, AP, Rads, CarryWeight, XP, Limb conditions, Resists
		float radsVal = 0.0f;
		if (ReadShellActorValue(g_forms.rads, radsVal) && radsVal > 0.0f) {
			next.rads = std::clamp(static_cast<double>(radsVal), 0.0, 1000.0);
		}
		static bool   everPositiveHp = false;
		static bool   everPositiveAp = false;
		float         hpVal = 0.0f;
		const bool    hpReadOk = ReadShellActorValue(g_forms.health, hpVal);
		const double  formulaMaxHp = std::max(80.0 + static_cast<double>(next.special[2]) * 5.0 +
		                                          static_cast<double>(next.xpLevel - 1) * (static_cast<double>(next.special[2]) * 0.5 + 2.5),
			1.0);
		if (hpReadOk && (hpVal > 0.0f || everPositiveHp)) {
			if (hpVal > 0.0f) {
				everPositiveHp = true;
			}
			next.currHp = std::max(0.0, static_cast<double>(hpVal));
			highWaterHp = std::max({ highWaterHp, next.currHp, formulaMaxHp });
			next.maxHp = std::max(1.0, highWaterHp);
			next.hpSource = "av";
		} else {
			next.maxHp = std::max(1.0, formulaMaxHp);
			next.currHp = next.maxHp;
			next.hpSource = hpReadOk ? "formula_zero_av" : "formula";
		}

		float         apVal = 0.0f;
		const bool    apReadOk = ReadShellActorValue(oxygenAvif, apVal);
		const double  formulaMaxAp = std::max(60.0 + static_cast<double>(next.special[5]) * 10.0, 1.0);
		if (apReadOk && (apVal > 0.0f || everPositiveAp)) {
			if (apVal > 0.0f) {
				everPositiveAp = true;
			}
			next.currAp = std::max(0.0, static_cast<double>(apVal));
			highWaterAp = std::max({ highWaterAp, next.currAp, formulaMaxAp });
			next.maxAp = std::max(1.0, highWaterAp);
			next.apSource = "av";
		} else {
			next.maxAp = formulaMaxAp;
			next.currAp = formulaMaxAp;
			next.apSource = apReadOk ? "formula_zero_av" : "formula";
		}

		float cwVal = 0.0f;
		if (ReadShellActorValue(g_forms.carryWeight, cwVal) && cwVal > 0.0f) {
			next.maxWeight = static_cast<double>(cwVal);
		} else {
			next.maxWeight = std::max(1.0, 150.0 + static_cast<double>(next.special[0]) * 10.0);
		}
		next.currWeight = std::clamp(carriedWeight, 0.0, 99999.0);

		float xpVal = 0.0f;
		if (ReadShellActorValue(g_forms.experience, xpVal) && xpVal >= 0.0f) {
			const double l = static_cast<double>(next.xpLevel);
			const double xpStart = 37.5 * (l - 1.0) * l + 125.0 * (l - 1.0);
			const double xpSpan = std::max(1.0, 75.0 * l + 125.0);
			if (static_cast<double>(xpVal) >= xpStart) {
				next.xpProgressPct = std::clamp((static_cast<double>(xpVal) - xpStart) / xpSpan, 0.0, 1.0);
			} else {
				next.xpProgressPct = std::clamp(static_cast<double>(xpVal) / xpSpan, 0.0, 1.0);
			}
		}

		bool anyLimbCrippled = false;
		for (std::size_t i = 0; i < 6; ++i) {
			float lv = 100.0f;
			if (ReadShellActorValue(limbAvifs[i], lv)) {
				if (lv == 0.0f && next.currHp >= next.maxHp * 0.99) {
					lv = 100.0f;
				}
				next.limbCondition[i] = std::clamp(static_cast<double>(lv), 0.0, 100.0);
			} else {
				next.limbCondition[i] = 100.0;
			}
			if (next.limbCondition[i] <= 0.5) {
				anyLimbCrippled = true;
			}
		}
		next.headFlags = (next.limbCondition[0] <= 0.5) ? 1u : 0u;
		next.bodyFlags = anyLimbCrippled ? 1u : 0u;

		float rv = 0.0f;
		if (ReadShellActorValue(drAvif, rv) && rv > 0.0f) {
			next.damageResist = static_cast<double>(rv);
		}
		if (ReadShellActorValue(erAvif, rv) && rv > 0.0f) {
			next.energyResist = static_cast<double>(rv);
		}
		if (ReadShellActorValue(rrAvif, rv) && rv > 0.0f) {
			next.radResist = static_cast<double>(rv);
		}

		// 4. Date (DateYear = year - 2000), TimeHour, CurrLocationName
		float hour = 9.0f;
		float days = 0.0f;
		if (ReadTime(g_forms.globalValueAt, hour, days)) {
			next.timeHour = std::clamp(static_cast<double>(hour), 0.0, 23.999);
			ShellCalendarFromDays(days, next.dateMonth, next.dateDay, next.dateYear);
		}
		const auto [cellRaw, worldRaw] = PlaceText();
		const auto cellClean = CleanDisplayName(cellRaw);
		const auto worldClean = (worldRaw == "NONE (INTERIOR)") ? std::string{} : CleanDisplayName(worldRaw);
		if (!cellClean.empty()) {
			next.locationName = cellClean;
		} else if (!worldClean.empty()) {
			next.locationName = worldClean;
		}

		if (g_invDataAnswers) {
			CollectQuestAndStatsMainThread(next, days, invDataNext);
			std::scoped_lock invLock(g_invDataLock);
			SortShellInvEntries(invDataNext.items, g_invSortMode.load(std::memory_order_relaxed));
			g_invDataSnap = std::move(invDataNext);
		} else if (PipboyMap::Enabled()) {
			// A5: keep MAP active objective markers synced even when InvDataAnswers=0
			CollectQuestAndStatsMainThread(next, days, invDataNext);
		}

		bool changed = false;
		{
			std::scoped_lock lock(g_shellSnapLock);
			changed = !g_shellSnap.ready ||
			          std::abs(g_shellSnap.currHp - next.currHp) >= 0.5 ||
			          std::abs(g_shellSnap.maxHp - next.maxHp) >= 0.5 ||
			          std::abs(g_shellSnap.currAp - next.currAp) >= 0.5 ||
			          std::abs(g_shellSnap.maxAp - next.maxAp) >= 0.5 ||
			          std::abs(g_shellSnap.rads - next.rads) >= 0.5 ||
			          std::abs(g_shellSnap.currWeight - next.currWeight) >= 0.1 ||
			          std::abs(g_shellSnap.timeHour - next.timeHour) >= (1.0 / 60.0) ||
			          g_shellSnap.xpLevel != next.xpLevel ||
			          g_shellSnap.caps != next.caps ||
			          g_shellSnap.stimpakCount != next.stimpakCount ||
			          g_shellSnap.radawayCount != next.radawayCount ||
			          g_shellSnap.dateDay != next.dateDay ||
			          g_shellSnap.locationName != next.locationName ||
			          g_shellSnap.special != next.special;
			g_shellSnap = std::move(next);
		}
		if (changed && g_open.load()) {
			g_pendingPartialMask.fetch_or(0x2u);
		}
		PipboyMap::CollectStateForPage(static_cast<std::int32_t>(a_targetPage));
	}

	struct RawObjectInstance
	{
		void*          object = nullptr;
		std::uintptr_t instanceData = 0;
	};
	static_assert(sizeof(RawObjectInstance) == 0x10);

	struct RawRemoveItemRequest
	{
		void*          object = nullptr;          // 00
		std::uintptr_t instanceData = 0;          // 08
		void*          extra = nullptr;           // 10
		std::int32_t   inventoryIndex = -1;       // 18
		std::int32_t   count = 1;                 // 1C
		std::uint32_t  reason = 3;                // 20 (ITEM_TRANSFER_REASON::kDropping)
		std::uint32_t  pad24 = 0;                 // 24
		void*          moveTo = nullptr;          // 28
		void*          dropLocation = nullptr;    // 30
		void*          dropRotation = nullptr;    // 38
	};
	static_assert(sizeof(RawRemoveItemRequest) == 0x40);

	using ObjInstanceCtor_t = RawObjectInstance* (*)(RawObjectInstance*, void*, void*);
	using EquipObjectCall_t = bool (*)(void*, void*, const RawObjectInstance&, const void*, bool, bool, bool, bool, bool);
	using UnequipObjectCall_t = bool (*)(void*, void*, const RawObjectInstance&, const void*, bool, bool, bool, bool, const void*);
	using RefrRemoveItemCall_t = void (*)(void*, std::uint32_t&, const RawRemoveItemRequest&);

	void ConsumePipboyAidMainThread(bool a_stimpak)
	{
		const char* const label = a_stimpak ? "stimpak" : "radaway";
		if (!g_shellExtraIdsReady || !g_equipMgrSingletonRva || !g_equipObjectRva || !g_objInstanceCtorRva) {
			REX::INFO("step=shell_aid kind={} result=ids_not_ready", label);
			return;
		}
		CollectShellVitalsMainThread(s_savedPage.load());
		ShellVitalsSnapshot snap;
		{
			std::scoped_lock lock(g_shellSnapLock);
			snap = g_shellSnap;
		}
		const std::uint32_t count = a_stimpak ? snap.stimpakCount : snap.radawayCount;
		const std::uint32_t fid = a_stimpak ? snap.stimpakFormId : snap.radawayFormId;
		if (count == 0 || fid == 0) {
			if (a_stimpak) {
				REX::INFO("step=stat_use item={:08X} hp_before={:.0f} hp_after={:.0f} used=0 reason=none_in_inventory",
					fid, snap.currHp, snap.currHp);
			} else {
				REX::INFO("step=stat_use item={:08X} rads_before={:.0f} rads_after={:.0f} used=0 reason=none_in_inventory",
					fid, snap.rads, snap.rads);
			}
			return;
		}
		if (a_stimpak && snap.currHp >= snap.maxHp - 0.05) {
			REX::INFO("step=stat_use item={:08X} hp_before={:.0f} hp_after={:.0f} used=0 reason=full_hp",
				fid, snap.currHp, snap.currHp);
			return;
		}
		const auto player = Singleton(kPlayerSingleton);
		if (!player || !CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk)) {
			REX::INFO("step=shell_aid kind={} result=no_player", label);
			return;
		}
		std::uintptr_t equipMgr = 0;
		ObjectType     mgrType;
		if (!Peek(g_base + g_equipMgrSingletonRva, equipMgr) || !equipMgr || !IsType(equipMgr, "ActorEquipManager@@", mgrType)) {
			REX::INFO("step=shell_aid kind={} result=no_equip_manager", label);
			return;
		}
		std::uintptr_t alchForm = 0;
		AcceptById(fid, label, "AlchemyItem@@", 0x30, alchForm);
		if (!alchForm) {
			REX::INFO("step=shell_aid kind={} result=form_not_alchemy form={:08X}", label, fid);
			return;
		}
		RawObjectInstance inst{};
		reinterpret_cast<ObjInstanceCtor_t>(g_base + g_objInstanceCtorRva)(&inst, reinterpret_cast<void*>(alchForm), nullptr);
		const bool equipped = reinterpret_cast<EquipObjectCall_t>(g_base + g_equipObjectRva)(
			reinterpret_cast<void*>(equipMgr), reinterpret_cast<void*>(player), inst, nullptr, false, false, true, true, false);

		CollectShellVitalsMainThread(s_savedPage.load());
		ShellVitalsSnapshot after;
		{
			std::scoped_lock lock(g_shellSnapLock);
			after = g_shellSnap;
		}
		if (a_stimpak) {
			REX::INFO("step=stat_use item={:08X} hp_before={:.0f} hp_after={:.0f} used={}",
				fid, snap.currHp, after.currHp, equipped ? 1 : 0);
		} else {
			REX::INFO("step=stat_use item={:08X} rads_before={:.0f} rads_after={:.0f} used={}",
				fid, snap.rads, after.rads, equipped ? 1 : 0);
		}
		g_pendingPartialMask.fetch_or(0x2u);   // PipboyUpdateMask.Stats (0x2) + BottomBar
		if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
			queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
		}
	}

	void ToggleEquipInvItemMainThread(std::uint32_t a_nodeId)
	{
		if (!g_shellExtraIdsReady || !g_equipMgrSingletonRva || !g_equipObjectRva || !g_objInstanceCtorRva) {
			return;
		}
		ShellInvEntry target;
		bool          found = false;
		{
			std::scoped_lock lock(g_invDataLock);
			if (a_nodeId < g_invDataSnap.items.size()) {
				target = g_invDataSnap.items[a_nodeId];
				found = true;
			}
		}
		if (!found || !target.formId) {
			return;
		}
		const auto player = Singleton(kPlayerSingleton);
		std::uintptr_t equipMgr = 0;
		ObjectType     mgrType;
		const auto     objForm = ShellFormLookup(target.formId);
		ObjectType     objType;
		if (!player || !CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk) ||
			!Peek(g_base + g_equipMgrSingletonRva, equipMgr) || !equipMgr || !IsType(equipMgr, "ActorEquipManager@@", mgrType) ||
			!objForm || !TypeOf(objForm, objType) || !BaseOffset(objType, "TESBoundObject@@")) {
			return;
		}
		RawObjectInstance inst{};
		reinterpret_cast<ObjInstanceCtor_t>(g_base + g_objInstanceCtorRva)(&inst, reinterpret_cast<void*>(objForm), nullptr);
		bool ok = false;
		const char* action = "equip";
		if (target.equipState != 0 && (target.formType == 0x30 || target.formType == 0x22)) {
			if (!g_unequipObjectRva) {
				REX::INFO("step=inv_equip node={} form={:08X} action=unequip ok=0 reason=no_unequip_rva", a_nodeId, target.formId);
				return;
			}
			action = "unequip";
			ok = reinterpret_cast<UnequipObjectCall_t>(g_base + g_unequipObjectRva)(
				reinterpret_cast<void*>(equipMgr), reinterpret_cast<void*>(player), inst, nullptr, false, false, true, true, nullptr);
		} else {
			ok = reinterpret_cast<EquipObjectCall_t>(g_base + g_equipObjectRva)(
				reinterpret_cast<void*>(equipMgr), reinterpret_cast<void*>(player), inst, nullptr, false, false, true, true, false);
		}
		REX::INFO("step=inv_equip node={} form={:08X} action={} ok={}", a_nodeId, target.formId, action, ok ? 1 : 0);
		CollectShellVitalsMainThread(s_savedPage.load());
		g_pendingPartialMask.fetch_or(0x6u);   // Stats | Inv
		if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
			queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
		}
	}

	constexpr bool IsDroppableItemFormType(std::uint8_t a_formType) noexcept
	{
		switch (a_formType) {
		case 0x22:   // kARMO (TESObjectARMO)
		case 0x23:   // kBOOK (TESObjectBOOK)
		case 0x26:   // kINGR (IngredientItem)
		case 0x28:   // kMISC (TESObjectMISC)
		case 0x30:   // kWEAP (TESObjectWEAP)
		case 0x31:   // kAMMO (TESAmmo)
		case 0x35:   // kKEYM (TESKey)
		case 0x36:   // kALCH (AlchemyItem)
		case 0x39:   // kNOTE (BGSNote)
		case 0x3D:   // kSLGM (TESSoulGem)
		case 0x98:   // kOMOD (BGSMod::Attachment::Mod)
		case 0x9F:   // kIRES (BGSResource)
			return true;
		default:
			return false;
		}
	}

	// Virtual slot 0x8B (RE::TESObjectREFR::RemoveItem) and 0x40-byte RE::RemoveItemRequest layout documented in
	// docs/ui/pipboy-inv-drop-note.md (CommonLibSF include/RE/T/TESObjectREFR.h:102-115, 201).
	void DropInvItemMainThread(std::uint32_t a_nodeId, std::uint32_t a_count)
	{
		ShellInvEntry target;
		bool          found = false;
		{
			std::scoped_lock lock(g_invDataLock);
			if (a_nodeId < g_invDataSnap.items.size()) {
				target = g_invDataSnap.items[a_nodeId];
				found = true;
			}
		}
		if (!found || !target.formId || a_count == 0) {
			return;
		}
		const auto     player = Singleton(kPlayerSingleton);
		std::uintptr_t primaryVt = 0;
		const auto     objForm = ShellFormLookup(target.formId);
		ObjectType     objType;
		std::uint8_t   formType = 0;
		if (!player || !CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk) ||
			!Peek(player, primaryVt) || !InImage(primaryVt, (kRefrRemoveItemSlot + 1) * 8) ||
			!objForm || !TypeOf(objForm, objType) || !BaseOffset(objType, "TESBoundObject@@") ||
			!Peek(objForm + kFormTypeAt, formType) || !IsDroppableItemFormType(formType)) {
			return;
		}
		std::array<float, 3> worldPos{};
		std::array<float, 3> worldRot{};
		if (!Peek(player + kPositionAt, worldPos.data(), sizeof(worldPos)) ||
			!std::isfinite(worldPos[0]) || !std::isfinite(worldPos[1]) || !std::isfinite(worldPos[2])) {
			return;
		}
		const bool haveRot = Peek(player + kAngleAt, worldRot.data(), sizeof(worldRot)) &&
		                     std::isfinite(worldRot[0]) && std::isfinite(worldRot[1]) && std::isfinite(worldRot[2]);
		const auto removeFn = reinterpret_cast<const std::uintptr_t*>(primaryVt)[kRefrRemoveItemSlot];
		if (!InImage(removeFn, 1)) {
			return;
		}
		RawRemoveItemRequest req{};
		req.object = reinterpret_cast<void*>(objForm);
		req.inventoryIndex = static_cast<std::int32_t>(target.invIndex);
		req.count = static_cast<std::int32_t>(std::min(a_count, target.count));
		req.reason = 3u;   // ITEM_TRANSFER_REASON::kDropping
		req.dropLocation = worldPos.data();
		req.dropRotation = haveRot ? worldRot.data() : nullptr;
		std::uint32_t outHandle = 0;
		reinterpret_cast<RefrRemoveItemCall_t>(removeFn)(reinterpret_cast<void*>(player), outHandle, req);
		REX::INFO("step=inv_drop node={} form={:08X} form_type={:#x} count={} handle={:#x}",
			a_nodeId, target.formId, formType, req.count, outHandle);
		CollectShellVitalsMainThread(s_savedPage.load());
		g_pendingPartialMask.fetch_or(0x6u);   // Stats | Inv
		if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
			queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
		}
	}

	bool ClearAs3ArrayInPlace(RE::Scaleform::GFx::Value& a_arr)
	{
		if (!a_arr.IsArray() && !a_arr.IsObject()) {
			return false;
		}
		RE::Scaleform::GFx::Value res;
		const RE::Scaleform::GFx::Value zero(std::uint32_t{ 0 });
		return a_arr.Invoke("splice", &res, &zero, 1) || a_arr.SetMember("length", zero);
	}

	// Round 11 A2.6: Atomically replace an AS3 Array from pre-staged GFx::Value entries only after every
	// CreateObject call succeeded, so a failed CreateObject leaves the existing AS3 list intact.
	std::uint32_t ReplaceAs3ArrayFromStaged(RE::Scaleform::GFx::Value& a_arr,
		std::vector<RE::Scaleform::GFx::Value>& a_staged)
	{
		if (!ClearAs3ArrayInPlace(a_arr)) {
			return 0;
		}
		RE::Scaleform::GFx::Value pushRes;
		std::uint32_t             pushed = 0;
		for (auto& entry : a_staged) {
			if (a_arr.Invoke("push", &pushRes, &entry, 1)) {
				++pushed;
			}
		}
		return pushed;
	}

	void FillInvAndDataIntoDataObj(RE::Scaleform::GFx::ASMovieRootBase* a_root, RE::Scaleform::GFx::Value& a_dataObj,
		std::uint32_t a_page, std::uint32_t a_tab, const char* a_when)
	{
		if (!g_invDataAnswers || !a_root || !a_dataObj.IsObject()) {
			return;
		}
		const std::uint32_t invTab = std::min<std::uint32_t>(a_tab, 6u);
		const std::int32_t  invFilter = (a_page == 1u) ? static_cast<std::int32_t>(1u << invTab) : 1;
		a_dataObj.SetMember("InvFilter", RE::Scaleform::GFx::Value(invFilter));
		a_dataObj.SetMember("SortMode", RE::Scaleform::GFx::Value(g_invSortMode.load(std::memory_order_relaxed)));

		RE::Scaleform::GFx::Value selArr, pushRes;
		if (a_dataObj.GetMember("InvSelectedItems", &selArr) && ClearAs3ArrayInPlace(selArr)) {
			for (std::size_t ti = 0; ti < g_invSelectedPerTab.size(); ++ti) {
				RE::Scaleform::GFx::Value sv(g_invSelectedPerTab[ti]);
				selArr.Invoke("push", &pushRes, &sv, 1);
			}
		}

		if (a_page == 1u) {
			ShellInvDataSnapshot          snap;
			std::array<std::uint32_t, 12> quickkeysCopy{};
			{
				std::scoped_lock lock(g_invDataLock);
				snap = g_invDataSnap;
				quickkeysCopy = g_quickkeyFormIds;
			}
			RE::Scaleform::GFx::Value invArr;
			std::uint32_t             pushed = 0;
			if (a_dataObj.GetMember("InvItems", &invArr) && (invArr.IsArray() || invArr.IsObject())) {
				std::vector<RE::Scaleform::GFx::Value> staged;
				staged.reserve(snap.items.size());
				bool stageOk = true;
				for (const auto& it : snap.items) {
					RE::Scaleform::GFx::Value entry;
					a_root->CreateObject(&entry);
					if (!entry.IsObject()) {
						stageOk = false;
						break;
					}
					entry.SetMember("text", RE::Scaleform::GFx::Value(it.name.c_str()));
					entry.SetMember("count", RE::Scaleform::GFx::Value(it.count));
					entry.SetMember("equipState", RE::Scaleform::GFx::Value(it.equipState));
					entry.SetMember("filterFlag", RE::Scaleform::GFx::Value(it.filterFlag));
					entry.SetMember("favorite", RE::Scaleform::GFx::Value(it.favorite));
					entry.SetMember("canFavorite", RE::Scaleform::GFx::Value(it.canFavorite));
					entry.SetMember("isLegendary", RE::Scaleform::GFx::Value(false));
					entry.SetMember("taggedForSearch", RE::Scaleform::GFx::Value(false));
					entry.SetMember("nodeID", RE::Scaleform::GFx::Value(it.nodeId));
					entry.SetMember("formID", RE::Scaleform::GFx::Value(it.formId));
					entry.SetMember("weight", RE::Scaleform::GFx::Value(it.weight));
					entry.SetMember("value", RE::Scaleform::GFx::Value(it.value));
					staged.push_back(std::move(entry));
				}
				if (stageOk) {
					pushed = ReplaceAs3ArrayFromStaged(invArr, staged);
				} else {
					REX::WARN("step=data_obj_stage_abort list=InvItems built={} want={}", staged.size(), snap.items.size());
				}
			}
			RE::Scaleform::GFx::Value compArr;
			if (a_dataObj.GetMember("InvComponents", &compArr)) {
				ClearAs3ArrayInPlace(compArr);
			}
			RE::Scaleform::GFx::Value favArr;
			if (a_dataObj.GetMember("FavoritesList", &favArr) && (favArr.IsArray() || favArr.IsObject())) {
				std::vector<RE::Scaleform::GFx::Value> staged;
				staged.reserve(quickkeysCopy.size());
				bool stageOk = true;
				for (std::size_t slot = 0; slot < quickkeysCopy.size(); ++slot) {
					RE::Scaleform::GFx::Value favVal(nullptr);
					if (quickkeysCopy[slot] != 0) {
						for (const auto& it : snap.items) {
							if (it.formId == quickkeysCopy[slot]) {
								a_root->CreateObject(&favVal);
								if (!favVal.IsObject()) {
									stageOk = false;
									break;
								}
								favVal.SetMember("text", RE::Scaleform::GFx::Value(it.name.c_str()));
								favVal.SetMember("nodeID", RE::Scaleform::GFx::Value(it.nodeId));
								favVal.SetMember("formID", RE::Scaleform::GFx::Value(it.formId));
								break;
							}
						}
					}
					if (!stageOk) {
						break;
					}
					staged.push_back(std::move(favVal));
				}
				if (stageOk) {
					(void)ReplaceAs3ArrayFromStaged(favArr, staged);
				} else {
					REX::WARN("step=data_obj_stage_abort list=FavoritesList built={} want={}", staged.size(), quickkeysCopy.size());
				}
			}
			if (++g_invFillLogs <= 64) {
				REX::INFO("step=inv_fill when={} tab={} filter={:#x} n={} total_count={}",
					a_when, invTab, invFilter, pushed, snap.totalItemCount);
			}
		} else if (a_page == 2u) {
			ShellInvDataSnapshot snap;
			{
				std::scoped_lock lock(g_invDataLock);
				snap = g_invDataSnap;
			}
			RE::Scaleform::GFx::Value questsArr;
			std::uint32_t             qPushed = 0;
			std::uint32_t             qActive = 0;
			std::uint32_t             qCompleted = 0;
			if (a_dataObj.GetMember("QuestsList", &questsArr) && (questsArr.IsArray() || questsArr.IsObject())) {
				std::vector<RE::Scaleform::GFx::Value> staged;
				staged.reserve(snap.quests.size());
				bool stageOk = true;
				for (const auto& q : snap.quests) {
					RE::Scaleform::GFx::Value entry;
					a_root->CreateObject(&entry);
					if (!entry.IsObject()) {
						stageOk = false;
						break;
					}
					entry.SetMember("text", RE::Scaleform::GFx::Value(q.name.c_str()));
					entry.SetMember("formID", RE::Scaleform::GFx::Value(q.formId));
					entry.SetMember("enabled", RE::Scaleform::GFx::Value(!q.completed));
					entry.SetMember("completed", RE::Scaleform::GFx::Value(q.completed));
					entry.SetMember("active", RE::Scaleform::GFx::Value(q.active));
					entry.SetMember("sortval", RE::Scaleform::GFx::Value(q.sortVal));
					entry.SetMember("swfFile", RE::Scaleform::GFx::Value(""));
					entry.SetMember("description", RE::Scaleform::GFx::Value(q.description.c_str()));
					staged.push_back(std::move(entry));
				}
				if (stageOk) {
					qPushed = ReplaceAs3ArrayFromStaged(questsArr, staged);
					for (const auto& q : snap.quests) {
						if (q.completed) {
							++qCompleted;
						} else if (q.active) {
							++qActive;
						}
					}
				} else {
					REX::WARN("step=data_obj_stage_abort list=QuestsList built={} want={}", staged.size(), snap.quests.size());
				}
			}
			RE::Scaleform::GFx::Value wsArr;
			if (a_dataObj.GetMember("WorkshopsList", &wsArr) && (wsArr.IsArray() || wsArr.IsObject())) {
				std::vector<RE::Scaleform::GFx::Value> staged;
				staged.reserve(snap.workshops.size());
				bool stageOk = true;
				for (const auto& ws : snap.workshops) {
					RE::Scaleform::GFx::Value entry, dataArr;
					a_root->CreateObject(&entry);
					a_root->CreateObject(&dataArr, "Array");
					if (!entry.IsObject() || !(dataArr.IsArray() || dataArr.IsObject())) {
						stageOk = false;
						break;
					}
					for (std::size_t wi = 0; wi < ws.values.size(); ++wi) {
						RE::Scaleform::GFx::Value cell;
						a_root->CreateObject(&cell);
						if (!cell.IsObject()) {
							stageOk = false;
							break;
						}
						cell.SetMember("value", RE::Scaleform::GFx::Value(ws.values[wi]));
						cell.SetMember("rating", RE::Scaleform::GFx::Value(std::int32_t{ 0 }));
						dataArr.Invoke("push", &pushRes, &cell, 1);
					}
					if (!stageOk) {
						break;
					}
					entry.SetMember("text", RE::Scaleform::GFx::Value(ws.name.c_str()));
					entry.SetMember("mapMarkerID", RE::Scaleform::GFx::Value(ws.mapMarkerId));
					entry.SetMember("workshopData", dataArr);
					staged.push_back(std::move(entry));
				}
				if (stageOk) {
					(void)ReplaceAs3ArrayFromStaged(wsArr, staged);
				} else {
					REX::WARN("step=data_obj_stage_abort list=WorkshopsList built={} want={}", staged.size(), snap.workshops.size());
				}
			}
			RE::Scaleform::GFx::Value statsArr;
			if (a_dataObj.GetMember("GeneralStatsList", &statsArr) && (statsArr.IsArray() || statsArr.IsObject())) {
				std::vector<RE::Scaleform::GFx::Value> staged;
				staged.reserve(snap.statCategories.size());
				bool stageOk = true;
				for (const auto& cat : snap.statCategories) {
					RE::Scaleform::GFx::Value catObj, rowArr;
					a_root->CreateObject(&catObj);
					a_root->CreateObject(&rowArr, "Array");
					if (!catObj.IsObject() || !(rowArr.IsArray() || rowArr.IsObject())) {
						stageOk = false;
						break;
					}
					for (const auto& [rLabel, rVal] : cat.rows) {
						RE::Scaleform::GFx::Value rObj;
						a_root->CreateObject(&rObj);
						if (!rObj.IsObject()) {
							stageOk = false;
							break;
						}
						rObj.SetMember("text", RE::Scaleform::GFx::Value(rLabel.c_str()));
						rObj.SetMember("value", RE::Scaleform::GFx::Value(rVal.c_str()));
						rowArr.Invoke("push", &pushRes, &rObj, 1);
					}
					if (!stageOk) {
						break;
					}
					catObj.SetMember("text", RE::Scaleform::GFx::Value(cat.name.c_str()));
					catObj.SetMember("statArray", rowArr);
					staged.push_back(std::move(catObj));
				}
				if (stageOk) {
					(void)ReplaceAs3ArrayFromStaged(statsArr, staged);
				} else {
					REX::WARN("step=data_obj_stage_abort list=GeneralStatsList built={} want={}", staged.size(), snap.statCategories.size());
				}
			}
			if (++g_questFillLogs <= 64) {
				REX::INFO("step=quests_fill when={} tab={} n={} active={} completed={}",
					a_when, a_tab, qPushed, qActive, qCompleted);
			}
		}
	}

	void FillPipboyDataObj(const void* a_menu, RE::Scaleform::GFx::ASMovieRootBase* a_root,
		RE::Scaleform::GFx::Value& a_dataObj, std::uint32_t a_targetPage, std::uint32_t a_targetTab, const char* a_when)
	{
		if (!a_root || !a_dataObj.IsObject()) {
			return;
		}
		const std::uint32_t page = std::min<std::uint32_t>(a_targetPage, 4u);
		const std::uint32_t tab = std::min<std::uint32_t>(a_targetTab, 16u);
		const void* const   movie = a_menu ? MovieOf(a_menu) : nullptr;
		const bool          isPartial = (a_when != nullptr && std::string_view(a_when) == "partial");
		const bool          needStructuralLists = !isPartial || !movie || g_staticListsInitMovie.load() != movie;

		ShellVitalsSnapshot snap;
		{
			std::scoped_lock lock(g_shellSnapLock);
			snap = g_shellSnap;
		}

		// Step 1 critical order: CurrentPage MUST be set BEFORE CurrentTab (_StoredTabs[_CurrentPage])
		a_dataObj.SetMember("CurrentPage", RE::Scaleform::GFx::Value(page));
		a_dataObj.SetMember("CurrentTab", RE::Scaleform::GFx::Value(tab));

		a_dataObj.SetMember("ReadOnlyMode", RE::Scaleform::GFx::Value(std::int32_t{ 0 }));
		a_dataObj.SetMember("bPipboyEffectInitialized", RE::Scaleform::GFx::Value(true));
		a_dataObj.SetMember("PlayerName", RE::Scaleform::GFx::Value(snap.playerName.c_str()));
		a_dataObj.SetMember("CurrHP", RE::Scaleform::GFx::Value(snap.currHp));
		a_dataObj.SetMember("MaxHP", RE::Scaleform::GFx::Value(std::max(1.0, snap.maxHp)));
		a_dataObj.SetMember("CurrAP", RE::Scaleform::GFx::Value(snap.currAp));
		a_dataObj.SetMember("MaxAP", RE::Scaleform::GFx::Value(std::max(1.0, snap.maxAp)));
		a_dataObj.SetMember("XPLevel", RE::Scaleform::GFx::Value(snap.xpLevel));
		a_dataObj.SetMember("XPProgressPct", RE::Scaleform::GFx::Value(std::clamp(snap.xpProgressPct, 0.0, 1.0)));
		a_dataObj.SetMember("CurrWeight", RE::Scaleform::GFx::Value(snap.currWeight));
		a_dataObj.SetMember("MaxWeight", RE::Scaleform::GFx::Value(std::max(1.0, snap.maxWeight)));
		a_dataObj.SetMember("Caps", RE::Scaleform::GFx::Value(snap.caps));
		a_dataObj.SetMember("PerkPoints", RE::Scaleform::GFx::Value(std::uint32_t{ 0 }));
		a_dataObj.SetMember("StimpakCount", RE::Scaleform::GFx::Value(snap.stimpakCount));
		a_dataObj.SetMember("RadawayCount", RE::Scaleform::GFx::Value(snap.radawayCount));
		a_dataObj.SetMember("DateMonth", RE::Scaleform::GFx::Value(snap.dateMonth));
		a_dataObj.SetMember("DateDay", RE::Scaleform::GFx::Value(snap.dateDay));
		a_dataObj.SetMember("DateYear", RE::Scaleform::GFx::Value(snap.dateYear));
		a_dataObj.SetMember("TimeHour", RE::Scaleform::GFx::Value(snap.timeHour));
		a_dataObj.SetMember("CurrLocationName", RE::Scaleform::GFx::Value(snap.locationName.c_str()));
		a_dataObj.SetMember("HeadCondition", RE::Scaleform::GFx::Value(snap.limbCondition[0]));
		a_dataObj.SetMember("TorsoCondition", RE::Scaleform::GFx::Value(snap.limbCondition[1]));
		a_dataObj.SetMember("LArmCondition", RE::Scaleform::GFx::Value(snap.limbCondition[2]));
		a_dataObj.SetMember("RArmCondition", RE::Scaleform::GFx::Value(snap.limbCondition[3]));
		a_dataObj.SetMember("LLegCondition", RE::Scaleform::GFx::Value(snap.limbCondition[4]));
		a_dataObj.SetMember("RLegCondition", RE::Scaleform::GFx::Value(snap.limbCondition[5]));
		a_dataObj.SetMember("HeadFlags", RE::Scaleform::GFx::Value(snap.headFlags));
		a_dataObj.SetMember("BodyFlags", RE::Scaleform::GFx::Value(snap.bodyFlags));
		a_dataObj.SetMember("UnderwearType", RE::Scaleform::GFx::Value(std::uint32_t{ 0 }));
		a_dataObj.SetMember("SortMode", RE::Scaleform::GFx::Value(g_invSortMode));

		// A2.6: Stage every AS3 list build before clearing the target array so a failed CreateObject leaves
		// prior lists intact; skip static structural lists on partial vitals refreshes once initialized for this movie.
		if (needStructuralLists) {
			// SPECIALList (7 entries {text, value, modifier, description})
			RE::Scaleform::GFx::Value specialArr;
			if (a_dataObj.GetMember("SPECIALList", &specialArr) && (specialArr.IsArray() || specialArr.IsObject())) {
				if (g_codeObjSpecial == kSpecialClear) {
					ClearAs3ArrayInPlace(specialArr);
				} else {
					std::vector<RE::Scaleform::GFx::Value> staged;
					staged.reserve(kSpecialNames.size());
					bool stageOk = true;
					for (std::size_t i = 0; i < kSpecialNames.size(); ++i) {
						RE::Scaleform::GFx::Value entry;
						a_root->CreateObject(&entry);
						if (!entry.IsObject()) {
							stageOk = false;
							break;
						}
						entry.SetMember("text", RE::Scaleform::GFx::Value(kSpecialNames[i]));
						entry.SetMember("value", RE::Scaleform::GFx::Value(static_cast<std::int32_t>(snap.special[i])));
						entry.SetMember("modifier", RE::Scaleform::GFx::Value(std::int32_t{ 0 }));
						entry.SetMember("description", RE::Scaleform::GFx::Value(""));
						staged.push_back(std::move(entry));
					}
					if (stageOk) {
						(void)ReplaceAs3ArrayFromStaged(specialArr, staged);
					} else {
						REX::WARN("step=data_obj_stage_abort list=SPECIALList built={} want={}", staged.size(), kSpecialNames.size());
					}
				}
			}

			// SlotResists (9 empty sub-arrays 0..8 for PaperDoll)
			RE::Scaleform::GFx::Value slotResists;
			if (a_dataObj.GetMember("SlotResists", &slotResists) && (slotResists.IsArray() || slotResists.IsObject())) {
				std::vector<RE::Scaleform::GFx::Value> staged;
				staged.reserve(9);
				bool stageOk = true;
				for (std::size_t s = 0; s < 9; ++s) {
					RE::Scaleform::GFx::Value subArr;
					a_root->CreateObject(&subArr, "Array");
					if (!(subArr.IsObject() || subArr.IsArray())) {
						stageOk = false;
						break;
					}
					staged.push_back(std::move(subArr));
				}
				if (stageOk) {
					(void)ReplaceAs3ArrayFromStaged(slotResists, staged);
				} else {
					REX::WARN("step=data_obj_stage_abort list=SlotResists built={} want=9", staged.size());
				}
			}

			// Ensure PerksList, StatsCategories, and RadioList are clean Arrays so PERKS / DATA / RADIO
			// never encounter malformed elements when ShellVitalsFill=1.
			for (const char* arrName : { "PerksList", "StatsCategories", "RadioList" }) {
				RE::Scaleform::GFx::Value arr;
				if (a_dataObj.GetMember(arrName, &arr)) {
					ClearAs3ArrayInPlace(arr);
				}
			}
			// When InvDataAnswers=0, ensure INV & DATA list containers remain valid Arrays without clobbering
			// InvDataAnswers=1 data (FillInvAndDataIntoDataObj owns them when g_invDataAnswers=1).
			if (!g_invDataAnswers) {
				for (const char* arrName : { "InvItems", "InvComponents", "InvSelectedItems", "FavoritesList", "QuestsList", "WorkshopsList", "GeneralStatsList" }) {
					RE::Scaleform::GFx::Value arr;
					if (a_dataObj.GetMember(arrName, &arr)) {
						ClearAs3ArrayInPlace(arr);
					}
				}
			}
			if (movie) {
				g_staticListsInitMovie.store(movie);
			}
		}

		// TotalResists (Ballistic=1, Energy=4, Radiation=6) — atomically staged
		RE::Scaleform::GFx::Value totalResists;
		if (a_dataObj.GetMember("TotalResists", &totalResists) && (totalResists.IsArray() || totalResists.IsObject())) {
			const std::array<std::pair<std::uint32_t, double>, 3> resists{ {
				{ 1u, snap.damageResist },
				{ 4u, snap.energyResist },
				{ 6u, snap.radResist },
			} };
			std::vector<RE::Scaleform::GFx::Value> staged;
			staged.reserve(resists.size());
			bool stageOk = true;
			for (const auto& [rtype, rval] : resists) {
				RE::Scaleform::GFx::Value entry;
				a_root->CreateObject(&entry);
				if (!entry.IsObject()) {
					stageOk = false;
					break;
				}
				entry.SetMember("type", RE::Scaleform::GFx::Value(rtype));
				entry.SetMember("value", RE::Scaleform::GFx::Value(rval));
				staged.push_back(std::move(entry));
			}
			if (stageOk) {
				(void)ReplaceAs3ArrayFromStaged(totalResists, staged);
			} else {
				REX::WARN("step=data_obj_stage_abort list=TotalResists built={} want={}", staged.size(), resists.size());
			}
		}

		// ActiveEffects (RADS when >= 1.0) — atomically staged
		RE::Scaleform::GFx::Value activeEffects;
		if (a_dataObj.GetMember("ActiveEffects", &activeEffects) && (activeEffects.IsArray() || activeEffects.IsObject())) {
			std::vector<RE::Scaleform::GFx::Value> staged;
			bool                                   stageOk = true;
			if (snap.rads >= 1.0) {
				RE::Scaleform::GFx::Value eff;
				a_root->CreateObject(&eff);
				if (!eff.IsObject()) {
					stageOk = false;
				} else {
					eff.SetMember("EffectName", RE::Scaleform::GFx::Value("RADS"));
					eff.SetMember("Magnitude", RE::Scaleform::GFx::Value(std::round(snap.rads)));
					eff.SetMember("Duration", RE::Scaleform::GFx::Value(0.0));
					eff.SetMember("elapsed", RE::Scaleform::GFx::Value(0.0));
					eff.SetMember("isTimed", RE::Scaleform::GFx::Value(false));
					eff.SetMember("inactive", RE::Scaleform::GFx::Value(false));
					staged.push_back(std::move(eff));
				}
			}
			if (stageOk) {
				(void)ReplaceAs3ArrayFromStaged(activeEffects, staged);
			} else {
				REX::WARN("step=data_obj_stage_abort list=ActiveEffects built=0 want=1");
			}
		}

		// Step 1k (UI-2): populate InvItems / QuestsList / WorkshopsList / GeneralStatsList in place when InvDataAnswers=1
		if (g_invDataAnswers) {
			FillInvAndDataIntoDataObj(a_root, a_dataObj, page, tab, a_when);
		}

		// Build WorldMapMarkers ONLY when targetPage == 3 (MAP) and NOT during a non-0x80 partial update
		// (PipboyMap::OnShellUpdate owns 0x80 marker rebuilds and RemoveAllMapMarkers reset).
		if (a_menu && page == PipboyMap::MapPageIndex() && std::string_view(a_when) != "partial") {
			PipboyMap::PopulateMapDataObj(a_menu, a_root, a_dataObj, static_cast<std::int32_t>(page));
		}

		g_currentShellPage.store(static_cast<std::int32_t>(page));
		g_currentShellTab.store(static_cast<std::int32_t>(tab));

		if (g_populateInCall && std::string_view(a_when) == "PopulatePipboyInfoObj") {
			if (!movie || g_populatedLogMovie.exchange(movie) != movie) {
				const int paused = (g_flags & kPauseFlag) != 0 ? 1 : 0;
				REX::INFO("step=populate page={} tab={} hp={:.0f}/{:.0f} ap={:.0f}/{:.0f} level={} special={},{},{},{},{},{},{} source={} paused={}",
					page, tab, snap.currHp, std::max(1.0, snap.maxHp), snap.currAp, std::max(1.0, snap.maxAp), snap.xpLevel,
					snap.special[0], snap.special[1], snap.special[2], snap.special[3], snap.special[4], snap.special[5], snap.special[6],
					snap.specialSource, paused);
			}
		}

		const void* const vitalsMovie = a_menu ? MovieOf(a_menu) : nullptr;
		if (!vitalsMovie || g_vitalsLogMovie.exchange(vitalsMovie) != vitalsMovie) {
			REX::INFO("step=shell_vitals when={} page={} tab={} hp={:.0f}/{:.0f} ap={:.0f}/{:.0f} lvl={} hp_src={} ap_src={}",
				a_when, page, tab, snap.currHp, std::max(1.0, snap.maxHp), snap.currAp, std::max(1.0, snap.maxAp),
				snap.xpLevel, snap.hpSource, snap.apSource);
		}

		REX::INFO("step=data_obj_fill when={} page={} tab={} hp={:.0f}/{:.0f} ap={:.0f}/{:.0f} lvl={} stim={} radaway={} rads={:.0f} date={}.{}.2{:03}",
			a_when, page, tab, snap.currHp, snap.maxHp, snap.currAp, snap.maxAp, snap.xpLevel, snap.stimpakCount,
			snap.radawayCount, snap.rads, snap.dateMonth, snap.dateDay, snap.dateYear);
	}

	bool ReadPath(const RE::Scaleform::GFx::Value& a_from, const std::string& a_path, RE::Scaleform::GFx::Value& a_out);
	void SpecialReady(RE::Scaleform::GFx::ASMovieRootBase* a_root, const RE::Scaleform::GFx::Value& a_top, const char* a_when);
	void ApplyBottomBarDateFix(const void* a_menu, const RE::Scaleform::GFx::Value& a_menuMc, const char* a_when);
	void ApplyShellHintBarLayout(const void* a_menu, const RE::Scaleform::GFx::Value& a_menuMc, const char* a_when);
	void ApplyShellPlatform(const void* a_menu, RE::Scaleform::GFx::Value& a_menuMc, const char* a_when, bool a_forcePageRefresh = false);

	// Step 1: synchronous in-call answer for onNewPage(pageIdx) and onNewTab(tabIdx) on the menu thread
	void AnswerPageOrTabSynchronously(bool a_isPage, std::int32_t a_idx)
	{
		if (g_closing.load()) {
			return;
		}
		const void* const menu = g_activeShellMenu.load();
		if (!menu || !MovieOf(menu)) {
			return;
		}
		auto* const               root = RootOf(menu);
		RE::Scaleform::GFx::Value top;
		RE::Scaleform::GFx::Value menuMc;
		if (!root || !root->GetVariable(&top, "root") || !top.IsObject() ||
			!ReadPath(top, g_codeObjAt, menuMc) || !menuMc.IsObject()) {
			return;
		}
		if (!g_dataObj.IsObject()) {
			menuMc.GetMember("DataObj", &g_dataObj);
		}
		if (!g_dataObj.IsObject()) {
			return;
		}
		std::uint32_t targetPage = s_savedPage.load();
		std::uint32_t targetTab = s_savedTabs[std::min<std::uint32_t>(targetPage, 4u)].load();
		if (a_isPage) {
			targetPage = static_cast<std::uint32_t>(std::clamp(a_idx, 0, 4));
			s_savedPage.store(targetPage);
			targetTab = s_savedTabs[targetPage].load();
		} else {
			targetPage = std::min<std::uint32_t>(targetPage, 4u);
			targetTab = static_cast<std::uint32_t>(std::clamp(a_idx, 0, 16));
			s_savedTabs[targetPage].store(targetTab);
		}

		// Always set CurrentPage BEFORE CurrentTab, populate target page fields, then InvalidateData() ONCE.
		// C4-2: ShellVitalsFill=1 (or PopulateInCall=1) populates full player HP/AP/SPECIAL/Date; 0 restores exact 2f path.
		if (g_populateInCall || g_shellVitalsFill) {
			FillPipboyDataObj(menu, root, g_dataObj, targetPage, targetTab, a_isPage ? "onNewPage" : "onNewTab");
			if (g_codeObjSpecial == kSpecialClear) {
				SpecialReady(root, top, "answer");
			}
		} else {
			g_dataObj.SetMember("CurrentPage", RE::Scaleform::GFx::Value(targetPage));
			g_dataObj.SetMember("CurrentTab", RE::Scaleform::GFx::Value(targetTab));
			SpecialReady(root, top, "answer");
			if (g_invDataAnswers) {
				FillInvAndDataIntoDataObj(root, g_dataObj, targetPage, targetTab, a_isPage ? "onNewPage" : "onNewTab");
			}
			if (targetPage == PipboyMap::MapPageIndex()) {
				PipboyMap::PopulateMapDataObj(menu, root, g_dataObj, static_cast<std::int32_t>(targetPage));
			}
			g_currentShellPage.store(static_cast<std::int32_t>(targetPage));
			g_currentShellTab.store(static_cast<std::int32_t>(targetTab));
		}
		PipboyMap::NotifyShellPageTab(static_cast<std::int32_t>(targetPage), static_cast<std::int32_t>(targetTab));
		if (a_isPage && targetPage == PipboyMap::MapPageIndex() && g_task) {
			g_task->AddTask([]() {
				PipboyMap::CollectStateForPage(static_cast<std::int32_t>(PipboyMap::MapPageIndex()));
				if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
					queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
				}
			});
		}

		RE::Scaleform::GFx::Value invRes;
		const bool invalidated = InvokeMovieTracked(menuMc, "InvalidateData", &invRes, nullptr, 0, "Menu_mc.InvalidateData");
		if (invalidated) {
			ApplyShellHintBarLayout(menu, menuMc, a_isPage ? "onNewPage" : "onNewTab");
			ApplyShellPlatform(menu, menuMc, a_isPage ? "onNewPage" : "onNewTab", a_isPage);
			ApplyBottomBarDateFix(menu, menuMc, a_isPage ? "onNewPage" : "onNewTab");
		}
		const auto n = ++g_answers;
		if (n <= kMaxAnswers) {
			REX::INFO("step=code_answer n={} kind={} page={} tab={} invalidated={}", n, a_isPage ? "page" : "tab",
				targetPage, targetTab, invalidated ? 1 : 0);
		}
		if (!invalidated) {
			REX::INFO("step=movie_call_miss where=code_answer_invalidate page={} tab={}", targetPage, targetTab);
		}
	}

	void NoteAnswer(const std::string& a_name, const RE::Scaleform::GFx::FunctionHandler::Params& a_params)
	{
		const bool page = a_name == "onNewPage";
		if ((!g_codeObjPages && !IsFo4ShellActive()) || (!page && a_name != "onNewTab")) {
			return;
		}
		std::int32_t index = -1;
		if (a_params.argCount > 0) {
			ExtractShellIndex(a_params.args[0], index, static_cast<std::int32_t>(kMaxAnswerIndex));
		}
		if (index < 0 || index > kMaxAnswerIndex) {
			if (g_answers.load() < kMaxAnswers) {
				REX::INFO("step=code_answer name={} result=bad_index args={}", a_name, a_params.argCount);
			}
			return;
		}
		if (IsFo4ShellActive()) {
			AnswerPageOrTabSynchronously(page, index);
			return;
		}
		(page ? g_answerPage : g_answerTab).store(index);
		g_answerNow = true;
	}

	void RequestPipboyOpen(std::uint32_t a_targetPage, const char* a_by);

	class CodeObjFunction final : public RE::Scaleform::GFx::FunctionHandler
	{
	public:
		void Name(const std::string& a_name) { _name = a_name; }

		void Call(const Params& a_params) override
		{
			const auto n = ++g_codeCalls;
			std::string callLogLine;
			if (n <= kMaxCodeCalls) {
				std::string args = a_params.argCount ? "" : " arg0=none";
				for (std::uint32_t i = 0; i < a_params.argCount && i < kMaxCodeArgs; ++i) {
					args += std::format(" arg{}={}", i, ArgText(a_params.args[i]));
				}
				callLogLine = std::format("step=code_call n={} name={} args={}{}", n, _name, a_params.argCount, args);
				if (!(g_inDestructionCall.load() && _name == "UnregisterMap")) {
					REX::INFO("{}", callLogLine);
				}
			}

			if (g_inDestructionCall.load() && _name == "UnregisterMap") {
				PipboyMap::ReleaseMovieRefs();
				std::scoped_lock lock(g_deferredLogLock);
				if (!callLogLine.empty()) {
					g_deferredDestructionLogs.push_back(std::move(callLogLine));
				}
				if (PipboyMap::Enabled()) {
					g_deferredDestructionLogs.emplace_back("step=map_unregister ok=1");
				}
				return;
			}

			if (g_closing.load()) {
				return;
			}

			// Step 1b (PopulateInCall=1) & Step 1k (InvDataAnswers=1): PopulatePipboyInfoObj(dataObj) fills in place and calls InvalidateData once
			if (_name == "PopulatePipboyInfoObj") {
				if (a_params.argCount > 0 && a_params.args[0].IsObject()) {
					g_dataObj = a_params.args[0];
					if (g_populateInCall || g_invDataAnswers) {
						const void* const menu = g_activeShellMenu.load();
						const void* const movie = menu ? MovieOf(menu) : nullptr;
						auto* const       root = menu ? RootOf(menu) : nullptr;
						const auto        page = std::min<std::uint32_t>(s_savedPage.load(), 4u);
						const auto        tab = s_savedTabs[page].load();
						if (root) {
							if (g_populateInCall) {
								FillPipboyDataObj(menu, root, g_dataObj, page, tab, "PopulatePipboyInfoObj");
							} else {
								g_dataObj.SetMember("CurrentPage", RE::Scaleform::GFx::Value(page));
								g_dataObj.SetMember("CurrentTab", RE::Scaleform::GFx::Value(tab));
								FillInvAndDataIntoDataObj(root, g_dataObj, page, tab, "PopulatePipboyInfoObj");
								if (page == PipboyMap::MapPageIndex()) {
									PipboyMap::PopulateMapDataObj(menu, root, g_dataObj, static_cast<std::int32_t>(page));
								}
							}
							PipboyMap::NotifyShellPageTab(static_cast<std::int32_t>(page), static_cast<std::int32_t>(tab));
							RE::Scaleform::GFx::Value top;
							RE::Scaleform::GFx::Value menuMc;
							if (std::string_view(g_loadingMovie.load() ? "load" : "show") != "load" &&
								root->GetVariable(&top, "root") && top.IsObject() &&
								ReadPath(top, g_codeObjAt, menuMc) && menuMc.IsObject()) {
								if (!g_populateInCall) {
									SpecialReady(root, top, "populate");
								}
								RE::Scaleform::GFx::Value invRes;
								const bool invalidated = InvokeMovieTracked(menuMc, "InvalidateData", &invRes, nullptr, 0,
									"Menu_mc.InvalidateData");
								if (invalidated && movie) {
									g_shownInvalidatedMovie = movie;
								}
								REX::INFO("step=populate_invalidate page={} tab={} invalidated={}", page, tab, invalidated ? 1 : 0);
							}
						}
					}
				}
				return;
			}

			// Step 1: onNewPage / onNewTab answered synchronously inside CodeObjFunction::Call
			if (_name == "onNewPage" || _name == "onNewTab") {
				NoteAnswer(_name, a_params);
				return;
			}

			// Step 1j (StatActions=1): UseStimpak, UseRadaway, PlayPerkSound, StopPerkSound, PlaySmallTransition, ShowPerksMenu
			if (g_statActions) {
				if (_name == "UseStimpak" && g_task) {
					g_task->AddTask([]() { ConsumePipboyAidMainThread(true); });
					return;
				}
				if (_name == "UseRadaway" && g_task) {
					g_task->AddTask([]() { ConsumePipboyAidMainThread(false); });
					return;
				}
				if (_name == "PlayPerkSound") {
					const std::string snd = (a_params.argCount > 0 && a_params.args[0].IsString()) ?
					                            std::string(a_params.args[0].GetString()).substr(0, kMaxCodeArg) :
					                            std::string("none");
					REX::INFO("step=stat_sound action=play_perk_sound name={}", snd);
					if (g_codeObjSound) {
						StartSound(n, a_params.argCount > 0 ? &a_params.args[0] : nullptr, true);
					}
					return;
				}
				if (_name == "StopPerkSound") {
					const bool stopped = StopActivePerkSound();
					REX::INFO("step=stat_sound action=stop_perk_sound stopped={}", stopped ? 1 : 0);
					return;
				}
				if (_name == "PlaySmallTransition") {
					const std::string arg0 = a_params.argCount > 0 ? ArgText(a_params.args[0]) : std::string("none");
					REX::INFO("step=stat_sound action=play_small_transition arg={}", arg0);
					if (g_codeObjSound && a_params.argCount > 0 && a_params.args[0].IsString()) {
						StartSound(n, &a_params.args[0], false);
					}
					return;
				}
				if (_name == "ShowPerksMenu") {
					REX::INFO("step=stat_stub name=ShowPerksMenu");
					return;
				}
			}

			// Step 1k (UI-2, InvDataAnswers=1): INV and DATA same-call & main-thread handlers
			if (g_invDataAnswers) {
				if (_name == "onInvItemSelection") {
					if (a_params.argCount >= 4) {
						std::int32_t selNode = -1;
						ExtractShellIndex(a_params.args[0], selNode, 4096);
						const auto curTab = std::min<std::size_t>(s_savedTabs[1].load(), 6u);
						if (selNode >= 0) {
							g_invSelectedPerTab[curTab] = selNode;
						}
						RE::Scaleform::GFx::Value cardArr = a_params.args[1];
						RE::Scaleform::GFx::Value dollArr = a_params.args[2];
						RE::Scaleform::GFx::Value invPage = a_params.args[3];
						ClearAs3ArrayInPlace(cardArr);
						ClearAs3ArrayInPlace(dollArr);

						const void* const shellMenu = g_activeShellMenu.load();
						auto* const root = shellMenu ? RootOf(shellMenu) : nullptr;
						ShellInvEntry chosen;
						bool          haveItem = false;
						{
							std::scoped_lock lock(g_invDataLock);
							if (selNode >= 0 && static_cast<std::size_t>(selNode) < g_invDataSnap.items.size()) {
								chosen = g_invDataSnap.items[static_cast<std::size_t>(selNode)];
								haveItem = true;
							}
						}
						if (root && haveItem && (cardArr.IsArray() || cardArr.IsObject())) {
							RE::Scaleform::GFx::Value pushRes;
							const auto pushCard = [&](const char* a_text, double a_val, std::uint32_t a_prec) {
								RE::Scaleform::GFx::Value c;
								root->CreateObject(&c);
								if (c.IsObject()) {
									c.SetMember("text", RE::Scaleform::GFx::Value(a_text));
									c.SetMember("value", RE::Scaleform::GFx::Value(a_val));
									c.SetMember("difference", RE::Scaleform::GFx::Value(0.0));
									c.SetMember("precision", RE::Scaleform::GFx::Value(a_prec));
									c.SetMember("DamageType", RE::Scaleform::GFx::Value(std::uint32_t{ 0 }));
									cardArr.Invoke("push", &pushRes, &c, 1);
								}
							};
							pushCard("$WT", chosen.weight, 1u);
							pushCard("$VAL", static_cast<double>(chosen.value), 0u);
							if (dollArr.IsArray() || dollArr.IsObject()) {
								for (std::size_t si = 0; si < 9; ++si) {
									RE::Scaleform::GFx::Value b(chosen.formType == 0x22 && si == 0);
									dollArr.Invoke("push", &pushRes, &b, 1);
								}
							}
							if (++g_invSelectLogs <= 64) {
								REX::INFO("step=inv_select node={} form={:08X} wt={:.1f} val={}",
									chosen.nodeId, chosen.formId, chosen.weight, chosen.value);
							}
						}
						if (invPage.IsObject()) {
							RE::Scaleform::GFx::Value res;
							InvokeMovieTracked(invPage, "onListSelectionChangeCallback", &res, nullptr, 0,
								"InvPage.onListSelectionChangeCallback", false);
						}
					}
					return;
				}
				if (_name == "SelectItem") {
					std::int32_t nodeId = -1;
					if (a_params.argCount >= 1 && ExtractShellIndex(a_params.args[0], nodeId, 4096) && nodeId >= 0 && g_task) {
						const auto uNode = static_cast<std::uint32_t>(nodeId);
						g_task->AddTask([uNode]() { ToggleEquipInvItemMainThread(uNode); });
					}
					return;
				}
				if (_name == "ItemDrop") {
					std::int32_t nodeId = -1;
					std::int32_t dropCount = 1;
					if (a_params.argCount >= 1 && ExtractShellIndex(a_params.args[0], nodeId, 4096) && nodeId >= 0 && g_task) {
						if (a_params.argCount >= 2) {
							ExtractShellIndex(a_params.args[1], dropCount, 999999);
						}
						const auto uNode = static_cast<std::uint32_t>(nodeId);
						const auto uCnt = static_cast<std::uint32_t>(std::max(1, dropCount));
						g_task->AddTask([uNode, uCnt]() { DropInvItemMainThread(uNode, uCnt); });
					}
					return;
				}
				if (_name == "SortItemList") {
					std::uint32_t nextSort = 0;
					{
						std::scoped_lock lock(g_invDataLock);
						nextSort = (g_invSortMode.load(std::memory_order_relaxed) + 1u) % 4u;
						g_invSortMode.store(nextSort, std::memory_order_relaxed);
						SortShellInvEntries(g_invDataSnap.items, nextSort);
					}
					const void* const shellMenu = g_activeShellMenu.load();
					auto* const root = shellMenu ? RootOf(shellMenu) : nullptr;
					if (root && g_dataObj.IsObject()) {
						FillInvAndDataIntoDataObj(root, g_dataObj, 1u, s_savedTabs[1].load(), "SortItemList");
					}
					REX::INFO("step=inv_sort mode={}", nextSort);
					if (a_params.argCount >= 1 && a_params.args[0].IsObject()) {
						RE::Scaleform::GFx::Value invPage = a_params.args[0];
						RE::Scaleform::GFx::Value zeroArg(std::uint32_t{ 0 });
						RE::Scaleform::GFx::Value res;
						InvokeMovieTracked(invPage, "onSortComplete", &res, &zeroArg, 1, "InvPage.onSortComplete");
					}
					g_pendingPartialMask.fetch_or(0x4u);
					if (g_task) {
						g_task->AddTask([]() {
							if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
								queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
							}
						});
					}
					return;
				}
				if (_name == "SetQuickkey") {
					std::int32_t nodeId = -1;
					std::int32_t slotIdx = -1;
					if (a_params.argCount >= 2 && ExtractShellIndex(a_params.args[0], nodeId, 4096) &&
						ExtractShellIndex(a_params.args[1], slotIdx, 11) && nodeId >= 0 && slotIdx >= 0) {
						std::uint32_t assignedFid = 0;
						{
							std::scoped_lock lock(g_invDataLock);
							if (static_cast<std::size_t>(nodeId) < g_invDataSnap.items.size()) {
								assignedFid = g_invDataSnap.items[static_cast<std::size_t>(nodeId)].formId;
								for (auto& existing : g_quickkeyFormIds) {
									if (existing == assignedFid) {
										existing = 0;
									}
								}
								g_quickkeyFormIds[static_cast<std::size_t>(slotIdx)] = assignedFid;
								for (auto& it : g_invDataSnap.items) {
									if (it.formId == assignedFid) {
										it.favorite = slotIdx;
									} else if (it.favorite == slotIdx) {
										it.favorite = -1;
									}
								}
							}
						}
						REX::INFO("step=inv_quickkey node={} slot={} form={:08X}", nodeId, slotIdx, assignedFid);
						g_pendingPartialMask.fetch_or(0x4u);
						if (g_task) {
							g_task->AddTask([]() {
								if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
									queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
								}
							});
						}
					}
					return;
				}
				if (_name == "ToggleComponentFavorite") {
					std::int32_t compFid = -1;
					if (a_params.argCount >= 1 && ExtractShellIndex(a_params.args[0], compFid, 0x7FFFFFFF) && compFid > 0) {
						const auto uFid = static_cast<std::uint32_t>(compFid);
						bool tagged = false;
						{
							std::scoped_lock lock(g_invDataLock);
							if (g_taggedComponentFormIds.contains(uFid)) {
								g_taggedComponentFormIds.erase(uFid);
							} else {
								g_taggedComponentFormIds.insert(uFid);
								tagged = true;
							}
						}
						REX::INFO("step=inv_component_tag form={:08X} tagged={}", uFid, tagged ? 1 : 0);
					}
					return;
				}
				if (_name == "ExamineItem" || _name == "updateItem3D" || _name == "onShowHotKeys" ||
					_name == "onComponentViewToggle" || _name == "toggleMovementToDirectional") {
					if (_name != "updateItem3D" && _name != "toggleMovementToDirectional") {
						REX::INFO("step=inv_action name={} arg0={}", _name, a_params.argCount > 0 ? ArgText(a_params.args[0]) : "none");
					}
					return;
				}
				if (_name == "onQuestSelection") {
					if (a_params.argCount >= 3) {
						RE::Scaleform::GFx::Value objList = a_params.args[0];
						RE::Scaleform::GFx::Value qEntry = a_params.args[1];
						RE::Scaleform::GFx::Value questsTab = a_params.args[2];
						ClearAs3ArrayInPlace(objList);

						std::uint32_t qFid = 0;
						RE::Scaleform::GFx::Value fidVal;
						if (qEntry.IsObject() && qEntry.GetMember("formID", &fidVal)) {
							if (fidVal.IsUInt()) {
								qFid = fidVal.GetUInt();
							} else if (fidVal.IsInt() && fidVal.GetInt() >= 0) {
								qFid = static_cast<std::uint32_t>(fidVal.GetInt());
							} else if (fidVal.IsNumber() && fidVal.GetNumber() >= 0.0) {
								qFid = static_cast<std::uint32_t>(fidVal.GetNumber());
							}
						}
						const void* const shellMenu = g_activeShellMenu.load();
						auto* const root = shellMenu ? RootOf(shellMenu) : nullptr;
						std::uint32_t objCount = 0;
						if (root && qFid != 0 && (objList.IsArray() || objList.IsObject())) {
							std::vector<ShellObjectiveEntry> objsCopy;
							bool qActive = true;
							{
								std::scoped_lock lock(g_invDataLock);
								for (const auto& q : g_invDataSnap.quests) {
									if (q.formId == qFid) {
										objsCopy = q.objectives;
										qActive = q.active;
										break;
									}
								}
							}
							RE::Scaleform::GFx::Value pushRes;
							for (const auto& ob : objsCopy) {
								RE::Scaleform::GFx::Value obVal;
								root->CreateObject(&obVal);
								if (obVal.IsObject()) {
									const bool done = (ob.state == 3);
									obVal.SetMember("text", RE::Scaleform::GFx::Value(ob.text.c_str()));
									obVal.SetMember("enabled", RE::Scaleform::GFx::Value(!done));
									obVal.SetMember("completed", RE::Scaleform::GFx::Value(done));
									obVal.SetMember("active", RE::Scaleform::GFx::Value(!done && qActive));
									obVal.SetMember("formID", RE::Scaleform::GFx::Value(static_cast<std::uint32_t>(ob.number)));
									if (objList.Invoke("push", &pushRes, &obVal, 1)) {
										++objCount;
									}
								}
							}
						}
						REX::INFO("step=quest_select form={:08X} objectives={}", qFid, objCount);
						if (questsTab.IsObject()) {
							RE::Scaleform::GFx::Value res;
							InvokeMovieTracked(questsTab, "onObjectivesReady", &res, nullptr, 0, "QuestsTab.onObjectivesReady", false);
						}
					}
					return;
				}
				if (_name == "SetQuestActive") {
					if (a_params.argCount >= 1 && a_params.args[0].IsObject()) {
						RE::Scaleform::GFx::Value qEntry = a_params.args[0];
						RE::Scaleform::GFx::Value fidVal;
						std::uint32_t qFid = 0;
						if (qEntry.GetMember("formID", &fidVal)) {
							if (fidVal.IsUInt()) {
								qFid = fidVal.GetUInt();
							} else if (fidVal.IsInt() && fidVal.GetInt() >= 0) {
								qFid = static_cast<std::uint32_t>(fidVal.GetInt());
							} else if (fidVal.IsNumber() && fidVal.GetNumber() >= 0.0) {
								qFid = static_cast<std::uint32_t>(fidVal.GetNumber());
							}
						}
						if (qFid != 0) {
							bool nowActive = true;
							{
								std::scoped_lock lock(g_invDataLock);
								if (g_inactiveQuestFormIds.contains(qFid)) {
									g_inactiveQuestFormIds.erase(qFid);
									nowActive = true;
								} else {
									g_inactiveQuestFormIds.insert(qFid);
									nowActive = false;
								}
								for (auto& q : g_invDataSnap.quests) {
									if (q.formId == qFid && !q.completed) {
										q.active = nowActive;
									}
								}
							}
							qEntry.SetMember("active", RE::Scaleform::GFx::Value(nowActive));
							REX::INFO("step=quest_active form={:08X} active={}", qFid, nowActive ? 1 : 0);
							g_pendingPartialMask.fetch_or(0x10u);
							if (g_task) {
								g_task->AddTask([]() {
									CollectShellVitalsMainThread(s_savedPage.load());
									if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
										queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
									}
								});
							}
						}
					}
					return;
				}
				if (_name == "ShowQuestOnMap" || _name == "ShowWorkshopOnMap") {
					const bool    isQuest = (_name == "ShowQuestOnMap");
					std::uint32_t targetU32 = 0;
					std::int32_t  targetIdx = -1;
					if (a_params.argCount >= 1) {
						if (isQuest) {
							ExtractShellUInt32(a_params.args[0], targetU32);
						} else {
							ExtractShellIndex(a_params.args[0], targetIdx, 0x7FFFFFFF);
						}
					}
					REX::INFO("step=data_show_on_map kind={} id={:#x}", isQuest ? "quest" : "workshop",
						isQuest ? targetU32 : static_cast<std::uint32_t>(targetIdx >= 0 ? targetIdx : 0));
					if (!isQuest) {
						PipboyMap::RequestCenterMarker(targetIdx);
					}
					s_savedPage.store(3u);
					s_savedTabs[3].store(0u);
					g_externalTargetPage.store(3);
					if (g_task) {
						g_task->AddTask([isQuest, targetU32]() {
							CollectShellVitalsMainThread(3u);
							if (isQuest) {
								if (targetU32 == 0 || !PipboyMap::RequestCenterQuest(targetU32)) {
									PipboyMap::RequestCenterMarker(-1);
								}
							}
							if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
								queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
							}
						});
					}
					return;
				}
				if (_name == "ToggleRadioStationActiveStatus") {
					REX::INFO("step=radio_toggle args={}", a_params.argCount);
					return;
				}
			}

			PipboyMap::OnCodeObjCall(_name, a_params);
			if (_name == "CheckHardcoreModeFastTravel" && !PipboyMap::Enabled()) {
				const bool allow = !g_shellHardcoreFastTravelBlocked.load();
				if (a_params.ret) {
					*a_params.ret = RE::Scaleform::GFx::Value(allow);
				}
				std::int32_t idx = 0;
				if (a_params.argCount >= 1) {
					ExtractShellIndex(a_params.args[0], idx, 0x7FFFFFFF);
				}
				REX::INFO("step=map_check_hardcore idx={} source=FO4SFCoreValues.esm:000841 allow={}",
					idx >= 0 ? idx : 0, allow ? 1 : 0);
			}

			if (g_codeObjHide && _name == "HideMenu" && g_task) {
				if (g_playingBootMovie.exchange(false)) {
					const auto reopenPage = s_savedPage.load();
					REX::INFO("step=boot_sequence finished=1 reopen_page={}", reopenPage);
					g_bootReopenPage.store(static_cast<std::int32_t>(reopenPage));
					g_task->AddTask([n]() { Close(n, "boot_done"); });
				} else {
					g_task->AddTask([n]() { Close(n, "hide_menu"); });
				}
			}
			if (g_codeObjSound && (_name == "PlaySound" || _name == "PlaySmallTransition" || _name == "PlayPerkSound" || _name == "PlayFocusSound")) {
				StartSound(n, a_params.argCount > 0 ? &a_params.args[0] : nullptr);
			}
		}

	private:
		std::string _name = "BGSCodeObj";
	};
	std::array<CodeObjFunction, kMaxCodeNames>       g_codeObjFunctions;
	std::array<std::string, kMaxCodeNames>           g_codeObjNames;
	std::size_t                                      g_codeObjCount = 0;

	// a function object as the holder (an ActionScript 3 Function is dynamic, so it takes members) with one function per
	// name on it, set as root.BGSCodeObj, then read back. Proof 1b found no root right after the engine's LoadMovie
	// returned (root=0 in the same millisecond), so it is tried there ("load"), after the engine's own kShow ("show") and
	// after each kUpdate ("update", sent while it is not set), on the menu's thread, up to kMaxCodeObjTries per movie;
	// the first tries and the one that sets it are logged with what was found
	// FAL-614 proof 2b: a path (members joined by '.') read from a_from with GetMember, one member at a time; false
	// when a member is missing or the value on the way is not an object or a function
	bool ReadPath(const RE::Scaleform::GFx::Value& a_from, const std::string& a_path, RE::Scaleform::GFx::Value& a_out)
	{
		RE::Scaleform::GFx::Value at = a_from;
		for (std::size_t start = 0; start <= a_path.size();) {
			const auto end = std::min(a_path.find('.', start), a_path.size());
			RE::Scaleform::GFx::Value next;
			if (!(at.IsObject() || at.GetType() == RE::Scaleform::GFx::Value::ValueType::kClosure) ||
				!at.GetMember(a_path.substr(start, end - start), &next)) {
				return false;
			}
			at = next;
			start = end + 1;
		}
		a_out = at;
		return true;
	}

	// FAL-614 S1-c: the function at a path from a_from (as CodeObjCalls= reads it) called on its owner with a_args;
	// a_found when the path ends in a function
	bool CallPath(const RE::Scaleform::GFx::Value& a_from, const std::string& a_path, const RE::Scaleform::GFx::Value* a_args,
		std::size_t a_count, bool& a_found)
	{
		RE::Scaleform::GFx::Value owner = a_from;
		RE::Scaleform::GFx::Value function;
		RE::Scaleform::GFx::Value result;
		const auto                last = a_path.rfind('.');
		const auto                name = last == std::string::npos ? a_path : a_path.substr(last + 1);
		const bool                read = (last == std::string::npos || ReadPath(a_from, a_path.substr(0, last), owner)) &&
		                  ReadPath(owner, name, function);
		a_found = read && function.GetType() == RE::Scaleform::GFx::Value::ValueType::kClosure;
		return a_found && InvokeMovieTracked(owner, name.c_str(), &result, a_args, a_count, a_path.c_str());
	}

	// FAL-1025: a path whose last member is InvalidateData, the call that loads a page and dispatches the change event
	bool IsInvalidate(const std::string& a_path)
	{
		const auto last = a_path.rfind('.');
		return (last == std::string::npos ? a_path : a_path.substr(last + 1)) == "InvalidateData";
	}

	// FAL-1025 (CodeObjSpecial=fill or clear, with CodeObjAt=): Gemini's PC read of Fallout 4's movies (REPORT 4 to 6),
	// checked in the decompiled AS3: PipboyMenu's DataObj starts SPECIALList as 7 empty objects, the STAT page's hidden
	// SPECIAL tab takes that list on each change event InvalidateData dispatches, and SPECIALListEntry.SetEntryText calls
	// value.toString() on each entry: an AS3 TypeError (#1010) inside the dispatch, which has no try/catch. Fallout 4's
	// engine fills the list first (PopulatePipboyInfoObj); our stand-in only logs. So right before each InvalidateData the
	// plugin calls, <CodeObjAt>.DataObj.SPECIALList is emptied (splice(0), else length = 0) and, with fill, given 7
	// entries {text, value, modifier, description}: the attribute's name, 1, 0 and "" (placeholders, not the player's).
	// Only the root's CreateObject (a virtual) and Value's GetMember, SetMember and Invoke: no new Address Library id
	void SpecialReady(RE::Scaleform::GFx::ASMovieRootBase* a_root, const RE::Scaleform::GFx::Value& a_top, const char* a_when)
	{
		if (g_codeObjSpecial == kSpecialOff || !a_root) {
			return;
		}
		RE::Scaleform::GFx::Value list;
		RE::Scaleform::GFx::Value result;
		const bool                found = ReadPath(a_top, g_codeObjAt + ".DataObj.SPECIALList", list);
		const RE::Scaleform::GFx::Value start(std::uint32_t{ 0 });
		const auto clearList = [&]() -> std::string_view {
			if (list.Invoke("splice", &result, &start, 1)) {
				return "splice";
			}
			if (list.SetMember("length", start)) {
				return "length";
			}
			return "none";
		};
		std::string_view by = found && list.IsArray() ? clearList() : "none";
		std::size_t      pushed = 0;
		for (std::size_t i = 0; by != "none" && g_codeObjSpecial == kSpecialFill && i < kSpecialNames.size(); ++i) {
			RE::Scaleform::GFx::Value entry;
			a_root->CreateObject(&entry);
			const bool made = entry.IsObject() && entry.SetMember("text", RE::Scaleform::GFx::Value(kSpecialNames[i])) &&
			                  entry.SetMember("value", RE::Scaleform::GFx::Value(std::uint32_t{ 1 })) &&
			                  entry.SetMember("modifier", RE::Scaleform::GFx::Value(std::int32_t{ 0 })) &&
			                  entry.SetMember("description", RE::Scaleform::GFx::Value(""));
			if (!made || !list.Invoke("push", &result, &entry, 1)) {
				break;
			}
			++pushed;
		}
		if (by != "none" && g_codeObjSpecial == kSpecialFill && pushed > 0 && pushed < kSpecialNames.size()) {
			by = clearList();   // partial fill rolled back so incomplete entries never reach InvalidateData
		}
		RE::Scaleform::GFx::Value length;
		const auto now = found && list.IsArray() && list.GetMember("length", &length) ? ArgText(length) : std::string("none");
		if (const auto n = ++g_specialLines; n <= kMaxSpecialLines) {
			REX::INFO("step=code_obj_special n={} when={} mode={} found={} type={} cleared_by={} pushed={} length={}", n, a_when, g_codeObjSpecial == kSpecialFill ? "fill" : "clear", found ? 1 : 0,
				found ? TypeCode(list) : -1, by, pushed, now);
		}
	}

	bool CodeObjInstall(const void* a_menu, const char* a_when)
	{
		if (g_closing.load()) {
			return false;
		}
		const void* const movie = MovieOf(a_menu);
		if (!movie || g_codeObjMovie.load() == movie) {
			return true;
		}
		g_activeShellMenu = a_menu;
		if (g_codeObjTriedMovie.exchange(movie) != movie) {
			g_codeObjTries.store(0);
		}
		const auto attempt = ++g_codeObjTries;
		if (attempt > kMaxCodeObjTries) {
			return false;
		}
		auto* const root = RootOf(a_menu);
		RE::Scaleform::GFx::Value top;
		RE::Scaleform::GFx::Value holder;
		RE::Scaleform::GFx::Value back;
		const bool  gotVariable = root && root->GetVariable(&top, "root");
		const bool  gotRoot = gotVariable && top.IsObject();
		const bool  bootMode = g_playingBootMovie.load();
		std::size_t members = 0;
		bool        topSet = false;
		const char* holderSource = "none";
		if (gotRoot) {
			// Task 1 step 1a (proven crash fix): NEVER use CreateFunction as the BGSCodeObj holder!
			// Read Menu_mc's own plain Object (PipboyMenu.as:53 `this.BGSCodeObj = new Object()`) once Menu_mc exists,
			// or construct a plain Object via root->CreateObject(&holder, "Object") when CodeObjAt= is empty / missing.
			RE::Scaleform::GFx::Value atCandidate;
			const bool needAtFirst = !bootMode && !g_codeObjAt.empty();
			const bool haveAtFirst = !needAtFirst || (ReadPath(top, g_codeObjAt, atCandidate) && atCandidate.IsObject());
			if (haveAtFirst) {
				if (needAtFirst) {
					RE::Scaleform::GFx::Value existing;
					if (atCandidate.GetMember("BGSCodeObj", &existing) && existing.IsObject() &&
						existing.GetType() != RE::Scaleform::GFx::Value::ValueType::kClosure) {
						holder = existing;
						holderSource = "menu_mc";
					}
				}
				if (holder.IsUndefined() || !holder.IsObject() ||
					holder.GetType() == RE::Scaleform::GFx::Value::ValueType::kClosure) {
					root->CreateObject(&holder, "Object");
					holderSource = "create_object";
				}
				for (std::size_t i = 0; i < g_codeObjCount && !holder.IsUndefined() && holder.IsObject(); ++i) {
					RE::Scaleform::GFx::Value function;
					root->CreateFunction(&function, &g_codeObjFunctions[i]);
					members += !function.IsUndefined() && holder.SetMember(g_codeObjNames[i].c_str(), function) ? 1 : 0;
				}
				topSet = !holder.IsUndefined() && holder.IsObject() && top.SetMember("BGSCodeObj", holder);
			}
		}
		const std::size_t set = members + (topSet ? 1 : 0);
		const bool        readBack = gotRoot && top.GetMember("BGSCodeObj", &back) && back.IsObject() &&
		                      back.GetType() != RE::Scaleform::GFx::Value::ValueType::kClosure;
		const bool        holderReady = gotRoot && !holder.IsUndefined() && members == g_codeObjCount;
		bool atSet = false;
		bool atReadBack = false;
		if (holderReady && !g_codeObjAt.empty()) {
			if (bootMode) {
				atSet = true;
				atReadBack = true;
			} else {
				RE::Scaleform::GFx::Value at;
				RE::Scaleform::GFx::Value atBack;
				atSet = ReadPath(top, g_codeObjAt, at) && at.SetMember("BGSCodeObj", holder);
				atReadBack = atSet && at.GetMember("BGSCodeObj", &atBack) &&
				             atBack.IsObject() && atBack.GetType() != RE::Scaleform::GFx::Value::ValueType::kClosure;
			}
		}
		const bool atDone = g_codeObjAt.empty() || atReadBack;
		bool called = false;
		if (holderReady && !bootMode && !g_codeObjInit.empty()) {
			RE::Scaleform::GFx::Value init;
			RE::Scaleform::GFx::Value result;
			RE::Scaleform::GFx::Value codeObj;
			const bool got = top.GetMember(g_codeObjInit.c_str(), &init);
			const bool found = got && (init.GetType() == RE::Scaleform::GFx::Value::ValueType::kClosure || init.IsObject());
			{
				MovieCallGuard initGuard(g_codeObjInit.c_str());
				called = found && top.Invoke(g_codeObjInit.c_str(), &result, &holder, 1);
				initGuard.ok = called;
			}
			const bool gotCodeObj = called && top.GetMember("codeObj", &codeObj);
			if (called || attempt <= kLoggedCodeObjTries || attempt == kMaxCodeObjTries) {
				REX::INFO("step=code_obj_init when={} try={} name={} got={} found={} type={} called={} result_type={} "
						  "code_obj={} code_obj_type={}",
					a_when, attempt, g_codeObjInit, got ? 1 : 0, found ? 1 : 0, TypeCode(init), called ? 1 : 0, TypeCode(result),
					gotCodeObj ? 1 : 0, TypeCode(codeObj));
			}
		}
		const bool done = holderReady && ((readBack && topSet) || called) && atDone;
		if (done) {
			g_codeObjMovie = movie;
			g_answers = 0;   // S1-c: this movie's answers
			REX::INFO("step=code_obj_holder type=object raw_type={} is_closure={} source={} members={} of={}",
				TypeCode(holder),
				holder.GetType() == RE::Scaleform::GFx::Value::ValueType::kClosure ? 1 : 0,
				holderSource, members, g_codeObjCount);
		}
		// FAL-614 proof 2b-ii (CodeObjCalls=<path>,...): once per movie on the try that finished the hand-over and before
		// the probe, each path is called with no arguments (Step 1: never call InvalidateData on the LoadMovie worker thread)
		for (std::size_t i = 0; done && !bootMode && i < g_rootCallCount; ++i) {
			if (std::string_view(a_when) == "load" && IsInvalidate(g_rootCallNames[i])) {
				REX::INFO("step=code_obj_root_call n={} name={} skipped_on_load=1", i + 1, g_rootCallNames[i]);
				continue;
			}
			RE::Scaleform::GFx::Value owner;
			RE::Scaleform::GFx::Value function;
			RE::Scaleform::GFx::Value result;
			const auto                last = g_rootCallNames[i].rfind('.');
			const auto                name = last == std::string::npos ? g_rootCallNames[i] : g_rootCallNames[i].substr(last + 1);
			bool                      read = false;
			if (last == std::string::npos) {
				read = ReadPath(top, name, function);
				owner = top;
			} else {
				read = ReadPath(top, g_rootCallNames[i].substr(0, last), owner) && ReadPath(owner, name, function);
			}
			if (IsInvalidate(g_rootCallNames[i])) {
				SpecialReady(root, top, "calls");   // FAL-1025
			}
			const bool found = read && function.GetType() == RE::Scaleform::GFx::Value::ValueType::kClosure;
			bool       rootCalled = false;
			{
				MovieCallGuard rootGuard(g_rootCallNames[i].c_str());
				rootCalled = found && owner.Invoke(name.c_str(), &result, nullptr, 0);
				rootGuard.ok = rootCalled;
			}
			if (rootCalled && g_rootCallNames[i] == "Menu_mc.onCodeObjCreate") {
				g_createdCodeObjMovie = movie;
			}
			if (rootCalled && g_rootCallNames[i] == "Menu_mc.InvalidateData") {
				g_shownInvalidatedMovie = movie;
			}
			REX::INFO("step=code_obj_root_call n={} name={} found={} type={} called={} result_type={}", i + 1, g_rootCallNames[i],
				found ? 1 : 0, read ? TypeCode(function) : -1, rootCalled ? 1 : 0, TypeCode(result));
			if (!rootCalled) {
				REX::INFO("step=movie_call_miss where=code_obj_root_call name={} found={}", g_rootCallNames[i], found ? 1 : 0);
			}
		}
		// FAL-614 proof 2b-i (CodeObjProbe=<path>,...): read-only. Once per movie, on the try that finished the
		// hand-over, each path (a root member, or members joined by '.') is read with GetMember and its type logged,
		// with the value only for a boolean or a number; nothing is set or called. type=-1: not found, nothing read
		for (std::size_t i = 0; done && !bootMode && i < g_probeCount; ++i) {
			RE::Scaleform::GFx::Value at;
			const bool                found = ReadPath(top, g_probeNames[i], at);
			std::string value;
			if (found && at.IsBoolean()) {
				value = std::format(" value={}", at.GetBoolean() ? 1 : 0);
			} else if (found && at.IsInt()) {
				value = std::format(" value={}", at.GetInt());
			} else if (found && at.IsUInt()) {
				value = std::format(" value={}", at.GetUInt());
			} else if (found && at.IsNumber()) {
				value = std::format(" value={}", at.GetNumber());
			}
			REX::INFO("step=code_obj_probe n={} name={} found={} type={}{}", i + 1, g_probeNames[i], found ? 1 : 0,
				found ? TypeCode(at) : -1, value);
		}
		if (done || attempt <= kLoggedCodeObjTries || attempt == kMaxCodeObjTries) {
			std::string names;
			for (std::size_t i = 0; i < g_codeObjCount; ++i) {
				names += std::format("{}{}", i ? "," : "", g_codeObjNames[i]);
			}
			REX::INFO("step=code_obj when={} try={} root_of={} get_variable={} root={} root_type={} holder_type={} set={} of={} "
					  "read_back={} names={} at={} at_set={} at_read_back={}",
				a_when, attempt, root ? 1 : 0, gotVariable ? 1 : 0, gotRoot ? 1 : 0, TypeCode(top), TypeCode(holder), set,
				g_codeObjCount + 1, readBack ? 1 : 0, names, g_codeObjAt.empty() ? "none" : g_codeObjAt, atSet ? 1 : 0,
				atReadBack ? 1 : 0);
		}
		if (!done && attempt >= kMaxCodeObjTries) {
			FailMovieCall("code_obj_install", std::format("tries={}", attempt));
			return false;
		}
		return done;
	}

	// stage b with CodeObj=1: true while the menu's movie has no stand-in yet and tries are left (the key thread then
	// sends kUpdate, which stage b does not otherwise get)
	bool CodeObjPending()
	{
		return g_codeObj && g_codeObjMovie.load() == nullptr && g_codeObjTries.load() < kMaxCodeObjTries;
	}

	// C4-1: Draw an opaque dark Pip-Boy CRT backing behind Menu_mc on root.graphics (fallback Menu_mc.graphics)
	// so 3D world geometry never bleeds through STAT/INV/DATA/RADIO or the letterbox margins of MAP.
	bool ApplyShellBackdrop(const void* a_menu, RE::Scaleform::GFx::Value& a_top, RE::Scaleform::GFx::Value& a_menuMc)
	{
		if (!g_shellBackdrop) {
			return true;
		}
		const void* const movie = a_menu ? MovieOf(a_menu) : nullptr;
		if (!movie || g_backdropMovie.load() == movie) {
			return true;
		}
		RE::Scaleform::GFx::Value gfx;
		const char*               target = "none";
		if (a_top.IsObject() && a_top.GetMember("graphics", &gfx) && gfx.IsObject()) {
			target = "root_graphics";
		} else if (a_menuMc.IsObject() && a_menuMc.GetMember("graphics", &gfx) && gfx.IsObject()) {
			target = "menu_mc_graphics";
		} else {
			REX::INFO("step=shell_backdrop movie={} ok=0 target=none color=0x041409 alpha=0.97",
				Hex(reinterpret_cast<std::uintptr_t>(movie)));
			return false;
		}
		RE::Scaleform::GFx::Value res;
		bool                      ok = gfx.Invoke("clear", &res, nullptr, 0);
		// 1. Full-viewport outer dim matte covering 16:9 and ultrawide margins around the 876x700 Pip-Boy stage
		{
			const RE::Scaleform::GFx::Value fillArgs[2]{
				RE::Scaleform::GFx::Value(std::uint32_t{ 0x020804u }),
				RE::Scaleform::GFx::Value(0.92),
			};
			const RE::Scaleform::GFx::Value rectArgs[4]{
				RE::Scaleform::GFx::Value(-2000.0),
				RE::Scaleform::GFx::Value(-1000.0),
				RE::Scaleform::GFx::Value(4876.0),
				RE::Scaleform::GFx::Value(2700.0),
			};
			ok = ok && gfx.Invoke("beginFill", &res, fillArgs, 2) &&
			     gfx.Invoke("drawRect", &res, rectArgs, 4) &&
			     gfx.Invoke("endFill", &res, nullptr, 0);
		}
		// 2. Opaque dark green-black Pip-Boy CRT backing directly behind the 876x700 stage
		{
			const RE::Scaleform::GFx::Value fillArgs[2]{
				RE::Scaleform::GFx::Value(std::uint32_t{ 0x041409u }),
				RE::Scaleform::GFx::Value(0.97),
			};
			const RE::Scaleform::GFx::Value rectArgs[4]{
				RE::Scaleform::GFx::Value(-8.0),
				RE::Scaleform::GFx::Value(-8.0),
				RE::Scaleform::GFx::Value(892.0),
				RE::Scaleform::GFx::Value(716.0),
			};
			ok = ok && gfx.Invoke("beginFill", &res, fillArgs, 2) &&
			     gfx.Invoke("drawRect", &res, rectArgs, 4) &&
			     gfx.Invoke("endFill", &res, nullptr, 0);
		}
		// 3. Subtle CRT bezel border framing the 876x700 Pip-Boy display
		{
			const RE::Scaleform::GFx::Value lineArgs[3]{
				RE::Scaleform::GFx::Value(2.0),
				RE::Scaleform::GFx::Value(std::uint32_t{ 0x185228u }),
				RE::Scaleform::GFx::Value(0.80),
			};
			const RE::Scaleform::GFx::Value rectArgs[4]{
				RE::Scaleform::GFx::Value(-8.0),
				RE::Scaleform::GFx::Value(-8.0),
				RE::Scaleform::GFx::Value(892.0),
				RE::Scaleform::GFx::Value(716.0),
			};
			(void)gfx.Invoke("lineStyle", &res, lineArgs, 3);
			(void)gfx.Invoke("drawRect", &res, rectArgs, 4);
			(void)gfx.Invoke("lineStyle", &res, nullptr, 0);
		}
		if (ok) {
			g_backdropMovie.store(movie);
		}
		REX::INFO("step=shell_backdrop movie={} ok={} target={} color=0x041409 alpha=0.97",
			Hex(reinterpret_cast<std::uintptr_t>(movie)), ok ? 1 : 0, target);
		return ok;
	}

	// C4-3 + Round 11 A2.6: On DATA/MAP (BottomBar_Info_3 Frame 6), Date_tf starts at x=8.0 width=150.0 while Time_tf
	// starts at x=207.0 (49 px unused gap). Starfield's wider fallback UI font clips "10.23.2287" to "10.23.228".
	// Widen Date_tf to 194.0 with wordWrap=false and autoSize="left" (clear of Time_tf at 207.0) and widen Time_tf to
	// 156.0. Guarded once per (movie, page) once succeeded so ShellUpdate never re-runs ReadPath/GetMember every tick.
	void ApplyBottomBarDateFix(const void* a_menu, const RE::Scaleform::GFx::Value& a_menuMc, const char* a_when)
	{
		if (!a_menu || !a_menuMc.IsObject()) {
			return;
		}
		const void* const movie = MovieOf(a_menu);
		const auto        curPage = g_currentShellPage.load();
		// Frame 6 (Date_tf / Time_tf) only exists on DATA (2) and MAP (3); skip on STAT/INV/RADIO.
		if (curPage >= 0 && curPage != 2 && curPage != 3) {
			return;
		}
		if (movie && g_dateFixDoneMovie.load() == movie && g_dateFixDonePage.load() == curPage) {
			return;
		}
		RE::Scaleform::GFx::Value dateTf;
		if (!ReadPath(a_menuMc, "BottomBar_mc.Info_mc.Date_tf", dateTf) || !dateTf.IsObject()) {
			return;
		}
		double                    oldW = 0.0;
		RE::Scaleform::GFx::Value wVal;
		if (dateTf.GetMember("width", &wVal)) {
			if (wVal.IsNumber()) {
				oldW = wVal.GetNumber();
			} else if (wVal.IsInt()) {
				oldW = static_cast<double>(wVal.GetInt());
			} else if (wVal.IsUInt()) {
				oldW = static_cast<double>(wVal.GetUInt());
			}
		}
		RE::Scaleform::GFx::Value autoVal;
		const bool alreadyLeft = dateTf.GetMember("autoSize", &autoVal) && autoVal.IsString() &&
		                         SameText(autoVal.GetString(), "left");
		if (alreadyLeft && oldW >= 160.0) {
			if (movie) {
				g_dateFixDonePage.store(curPage);
				g_dateFixDoneMovie.store(movie);
			}
			return;
		}
		const bool setWrap = dateTf.SetMember("wordWrap", RE::Scaleform::GFx::Value(false));
		const bool setW = dateTf.SetMember("width", RE::Scaleform::GFx::Value(194.0));
		const bool setAuto = dateTf.SetMember("autoSize", RE::Scaleform::GFx::Value("left"));
		RE::Scaleform::GFx::Value timeTf;
		if (ReadPath(a_menuMc, "BottomBar_mc.Info_mc.Time_tf", timeTf) && timeTf.IsObject()) {
			RE::Scaleform::GFx::Value twVal;
			double                    tw = 0.0;
			if (timeTf.GetMember("width", &twVal) && twVal.IsNumber()) {
				tw = twVal.GetNumber();
			}
			if (tw < 155.0) {
				timeTf.SetMember("wordWrap", RE::Scaleform::GFx::Value(false));
				timeTf.SetMember("width", RE::Scaleform::GFx::Value(156.0));
			}
		}
		double                    newW = 0.0;
		RE::Scaleform::GFx::Value nwVal;
		if (dateTf.GetMember("width", &nwVal) && nwVal.IsNumber()) {
			newW = nwVal.GetNumber();
		}
		if (movie && setW && setAuto) {
			g_dateFixDonePage.store(curPage);
			g_dateFixDoneMovie.store(movie);
		}
		if (movie && g_dateFixLogMovie.exchange(movie) != movie) {
			REX::INFO("step=shell_date_fix when={} old_w={:.1f} new_w={:.1f} auto_size={} word_wrap={} width_set={}",
				a_when ? a_when : "update", oldW, newW, setAuto ? 1 : 0, setWrap ? 1 : 0, setW ? 1 : 0);
		}
	}

	// Round 11 D5 Part 1: In PipboyMenu.swf (Sprite 79), ButtonHintBar_mc sits at y=575.0 while StatusTab_mc.Name_tf
	// ("PLAYER") sits at y=580.0 (5 px overlap directly over "RADAWAY (0)" on cand2g still 12). BottomBar_mc occupies
	// y=629.8..668.0 inside the 708.0 CRT bezel. Move ButtonHintBar_mc.y to 672.0 once per movie so Name_tf sits
	// cleanly between DMG/DR (y=553) and BottomBar_mc (y=629.8) with zero collision.
	void ApplyShellHintBarLayout(const void* a_menu, const RE::Scaleform::GFx::Value& a_menuMc, const char* a_when)
	{
		if (!a_menu || !a_menuMc.IsObject()) {
			return;
		}
		const void* const movie = MovieOf(a_menu);
		if (!movie || g_hintBarDoneMovie.load() == movie) {
			return;
		}
		RE::Scaleform::GFx::Value hintBar;
		if (!ReadPath(a_menuMc, "ButtonHintBar_mc", hintBar) || !hintBar.IsObject()) {
			return;
		}
		double                    oldY = 0.0;
		RE::Scaleform::GFx::Value yVal;
		if (hintBar.GetMember("y", &yVal)) {
			if (yVal.IsNumber()) {
				oldY = yVal.GetNumber();
			} else if (yVal.IsInt()) {
				oldY = static_cast<double>(yVal.GetInt());
			} else if (yVal.IsUInt()) {
				oldY = static_cast<double>(yVal.GetUInt());
			}
		}
		constexpr double kTargetHintBarY = 672.0;
		const bool       setY = hintBar.SetMember("y", RE::Scaleform::GFx::Value(kTargetHintBarY));
		if (setY) {
			g_hintBarDoneMovie.store(movie);
		}
		REX::INFO("step=shell_hintbar_layout when={} old_y={:.1f} new_y={:.1f} ok={}",
			a_when ? a_when : "update", oldY, kTargetHintBarY, setY ? 1 : 0);
	}

	// Round 11 D5 Part 2: PipboyMenu.swf starts with _uiPlatform=PLATFORM_INVALID (0xFFFFFFFF) because Starfield never
	// calls SetPlatform, causing BSButtonHint and Pipboy_Header to render Xbox controller glyphs (A, X, Y, LT, RT) on
	// keyboard + mouse. Call Menu_mc.SetPlatform(0u, false) (PLATFORM_PC_KB_MOUSE = 0) and hide Header_mc's
	// LeftTriggerButton_mc / RightTriggerButton_mc on KB+M. Guarded once per movie (plus page-switch refresh).
	void ApplyShellPlatform(const void* a_menu, RE::Scaleform::GFx::Value& a_menuMc, const char* a_when, bool a_forcePageRefresh)
	{
		if (!a_menu || !a_menuMc.IsObject()) {
			return;
		}
		const void* const movie = MovieOf(a_menu);
		if (!movie) {
			return;
		}
		const bool alreadyDone = (g_platformDoneMovie.load() == movie);
		if (alreadyDone && !a_forcePageRefresh) {
			return;
		}
		constexpr std::uint32_t   kPlatformPcKbMouse = 0u;
		RE::Scaleform::GFx::Value args[2]{
			RE::Scaleform::GFx::Value(kPlatformPcKbMouse),
			RE::Scaleform::GFx::Value(false),
		};
		RE::Scaleform::GFx::Value res;
		const bool calledMenu = InvokeMovieTracked(a_menuMc, "SetPlatform", &res, args, 2, "Menu_mc.SetPlatform", false);

		RE::Scaleform::GFx::Value hintBar;
		if (ReadPath(a_menuMc, "ButtonHintBar_mc", hintBar) && hintBar.IsObject()) {
			(void)hintBar.Invoke("SetPlatform", &res, args, 2);
		}
		std::uint32_t             triggersHidden = 0;
		RE::Scaleform::GFx::Value headerMc;
		if (ReadPath(a_menuMc, "Header_mc", headerMc) && headerMc.IsObject()) {
			(void)headerMc.Invoke("SetPlatform", &res, args, 2);
			for (const char* trigName : { "LeftTriggerButton_mc", "RightTriggerButton_mc" }) {
				RE::Scaleform::GFx::Value trig;
				if (headerMc.GetMember(trigName, &trig) && trig.IsObject()) {
					const bool visOk = trig.SetMember("visible", RE::Scaleform::GFx::Value(false));
					(void)trig.SetMember("alpha", RE::Scaleform::GFx::Value(0.0));
					if (visOk) {
						++triggersHidden;
					}
				}
			}
		}
		if (calledMenu || triggersHidden > 0) {
			const bool firstLog = (g_platformDoneMovie.exchange(movie) != movie);
			if (firstLog) {
				REX::INFO("step=shell_platform when={} platform=0 called={} triggers_hidden={}",
					a_when ? a_when : "update", calledMenu ? 1 : 0, triggersHidden);
			}
		}
	}

	// Step 1: on kShow (menu thread, after g_engineProcessMessage and CodeObjInstall), ensure Menu_mc.onCodeObjCreate()
	// ran, draw the opaque Pip-Boy backdrop (C4-1), populate DataObj (CurrentPage before CurrentTab; C4-2 real vitals
	// even when PopulateInCall=0), call Menu_mc.InvalidateData() ONCE, and widen BottomBar Date_tf (C4-3)
	void ShellShowInit(const void* a_menu)
	{
		if (g_closing.load() || !IsFo4ShellActive()) {
			return;
		}
		const void* const movie = MovieOf(a_menu);
		if (!movie || g_codeObjMovie.load() != movie) {
			return;
		}
		g_activeShellMenu = a_menu;
		auto* const               root = RootOf(a_menu);
		RE::Scaleform::GFx::Value top;
		RE::Scaleform::GFx::Value menuMc;
		if (!root || !root->GetVariable(&top, "root") || !top.IsObject() ||
			!ReadPath(top, g_codeObjAt, menuMc) || !menuMc.IsObject()) {
			REX::INFO("step=movie_call_miss where=shell_show_root");
			return;
		}
		ApplyShellBackdrop(a_menu, top, menuMc);
		ApplyShellHintBarLayout(a_menu, menuMc, "kShow");
		if (g_createdCodeObjMovie.exchange(movie) != movie) {
			RE::Scaleform::GFx::Value createRes;
			if (!InvokeMovieTracked(menuMc, "onCodeObjCreate", &createRes, nullptr, 0, "Menu_mc.onCodeObjCreate")) {
				REX::INFO("step=movie_call_miss where=onCodeObjCreate");
				return;
			}
		}
		ApplyShellPlatform(a_menu, menuMc, "kShow");
		const bool alreadyInvalidated = (g_shownInvalidatedMovie.exchange(movie) == movie);
		if (alreadyInvalidated && !g_lateInvalidate) {
			ApplyBottomBarDateFix(a_menu, menuMc, "kShow_existing");
			return;
		}
		if (!g_dataObj.IsObject()) {
			menuMc.GetMember("DataObj", &g_dataObj);
		}
		if (!g_dataObj.IsObject()) {
			REX::INFO("step=movie_call_miss where=shell_show_data_obj");
			return;
		}
		const auto page = std::min<std::uint32_t>(s_savedPage.load(), 4u);
		const auto tab = s_savedTabs[page].load();
		// C4-2: ShellVitalsFill=1 (or PopulateInCall=1) populates real HP/AP/SPECIAL/Date on kShow; 0 restores exact 2f path
		if (g_populateInCall || g_shellVitalsFill) {
			FillPipboyDataObj(a_menu, root, g_dataObj, page, tab, "kShow");
			if (g_codeObjSpecial == kSpecialClear) {
				SpecialReady(root, top, "show");
			}
		} else {
			g_dataObj.SetMember("CurrentPage", RE::Scaleform::GFx::Value(page));
			g_dataObj.SetMember("CurrentTab", RE::Scaleform::GFx::Value(tab));
			SpecialReady(root, top, "show");
			if (g_invDataAnswers) {
				FillInvAndDataIntoDataObj(root, g_dataObj, page, tab, "kShow");
			}
			if (page == PipboyMap::MapPageIndex()) {
				PipboyMap::PopulateMapDataObj(a_menu, root, g_dataObj, static_cast<std::int32_t>(page));
			}
			g_currentShellPage.store(static_cast<std::int32_t>(page));
			g_currentShellTab.store(static_cast<std::int32_t>(tab));
		}
		PipboyMap::NotifyShellPageTab(static_cast<std::int32_t>(page), static_cast<std::int32_t>(tab));

		RE::Scaleform::GFx::Value invRes;
		const bool invalidated = InvokeMovieTracked(menuMc, "InvalidateData", &invRes, nullptr, 0, "Menu_mc.InvalidateData");
		if (invalidated) {
			ApplyShellHintBarLayout(a_menu, menuMc, "kShow");
			ApplyShellPlatform(a_menu, menuMc, "kShow");
			ApplyBottomBarDateFix(a_menu, menuMc, "kShow");
		}
		REX::INFO("step=shell_show_invalidate page={} tab={} invalidated={}", page, tab, invalidated ? 1 : 0);
		if (!invalidated) {
			REX::INFO("step=movie_call_miss where=shell_show_invalidate page={} tab={}", page, tab);
		}
	}

	// Step 1c: on kHide BEFORE g_engineProcessMessage (while MovieOf(a_menu) is still non-null, guarded once per movie),
	// set g_closing first so nothing writes to DataObj or the movie, call Menu_mc.onCodeObjDestruction(), log
	// code_obj_destruction called=1, then UnregisterMap (if MAP was loaded), then touch the movie no more before step=destroy
	void ShellHideTeardown(const void* a_menu)
	{
		g_closing.store(true);
		PipboyMap::SetClosing(true);
		const void* const movie = MovieOf(a_menu);
		if (!movie || !IsFo4ShellActive() || g_codeObjMovie.load() != movie) {
			PipboyMap::ReleaseMovieRefs();
			g_dataObj = RE::Scaleform::GFx::Value{};
			g_activeShellMenu = nullptr;
			return;
		}
		if (g_destroyedCodeObjMovie.exchange(movie) == movie) {
			return;
		}
		PipboyMap::ReleaseMovieRefs();
		g_dataObj = RE::Scaleform::GFx::Value{};
		{
			std::scoped_lock lock(g_deferredLogLock);
			g_deferredDestructionLogs.clear();
		}

		bool        called = false;
		auto* const root = RootOf(a_menu);
		RE::Scaleform::GFx::Value top;
		RE::Scaleform::GFx::Value menuMc;
		if (root && root->GetVariable(&top, "root") && top.IsObject() &&
			ReadPath(top, g_codeObjAt, menuMc) && menuMc.IsObject()) {
			RE::Scaleform::GFx::Value res;
			g_inDestructionCall.store(true);
			called = InvokeMovieTracked(menuMc, "onCodeObjDestruction", &res, nullptr, 0, "Menu_mc.onCodeObjDestruction");
			g_inDestructionCall.store(false);
		}
		PipboyMap::ReleaseMovieRefs();
		g_dataObj = RE::Scaleform::GFx::Value{};
		g_activeShellMenu = nullptr;
		REX::INFO("step=code_obj_destruction movie={} called={}", Hex(reinterpret_cast<std::uintptr_t>(movie)), called ? 1 : 0);

		std::vector<std::string> deferred;
		{
			std::scoped_lock lock(g_deferredLogLock);
			deferred.swap(g_deferredDestructionLogs);
		}
		for (const auto& line : deferred) {
			REX::INFO("{}", line);
		}
	}

	// Steps 1, 3, 4: drain ProcessUserEvent queue (with Cancel release -> !consumed && CurrentPage.CanLowerPipboy()),
	// external page switch guard (_IsLoadingPage == false && CurrentPage loaded), and throttled partial vitals refresh
	bool ProcessPendingShellEvents(const void* a_menu, RE::Scaleform::GFx::ASMovieRootBase* a_root, RE::Scaleform::GFx::Value& a_top)
	{
		if (g_closing.load()) {
			return false;
		}
		g_activeShellMenu = a_menu;
		RE::Scaleform::GFx::Value menuMc;
		if (!ReadPath(a_top, g_codeObjAt, menuMc) || !menuMc.IsObject()) {
			REX::INFO("step=movie_call_miss where=shell_events_menu_mc");
			return false;
		}

		std::vector<PendingUserEvent> batch;
		{
			std::scoped_lock lock(g_shellEventLock);
			batch.swap(g_pendingUserEvents);
		}
		for (const auto& ev : batch) {
			if (g_closing.load()) {
				break;
			}
			RE::Scaleform::GFx::Value args[2]{
				RE::Scaleform::GFx::Value(ev.name.c_str()),
				RE::Scaleform::GFx::Value(ev.isDown),
			};
			RE::Scaleform::GFx::Value res;
			if (!InvokeMovieTracked(menuMc, "ProcessUserEvent", &res, args, 2, "Menu_mc.ProcessUserEvent")) {
				REX::INFO("step=movie_call_miss where=ProcessUserEvent event={}", ev.name);
				continue;
			}
			const bool consumed = res.IsBoolean() && res.GetBoolean();
			REX::INFO("step=process_user_event name={} handled={} down={}", ev.name, consumed ? 1 : 0, ev.isDown ? 1 : 0);

			if (ev.name == "Cancel" && !ev.isDown) {
				bool                      canLower = true;
				RE::Scaleform::GFx::Value curPageClip;
				if (menuMc.GetMember("CurrentPage", &curPageClip) && curPageClip.IsObject()) {
					RE::Scaleform::GFx::Value canRes;
					if (!InvokeMovieTracked(curPageClip, "CanLowerPipboy", &canRes, nullptr, 0, "CurrentPage.CanLowerPipboy")) {
						REX::INFO("step=movie_call_miss where=CanLowerPipboy");
					} else if (canRes.IsBoolean()) {
						canLower = canRes.GetBoolean();
					}
				}
				const bool modalOpen = PipboyMap::IsModalOpen();
				const bool allowClose = !consumed && canLower && !modalOpen;
				REX::INFO("step=shell_cancel_check consumed={} can_lower={} map_modal={} close={}",
					consumed ? 1 : 0, canLower ? 1 : 0, modalOpen ? 1 : 0, allowClose ? 1 : 0);
				if (allowClose) {
					g_cancelNow = true;
				}
			}
		}

		if (const auto extPage = g_externalTargetPage.load(); extPage >= 0) {
			RE::Scaleform::GFx::Value loadingVal;
			RE::Scaleform::GFx::Value curPageClip;
			const bool loadingFlag = menuMc.GetMember("_IsLoadingPage", &loadingVal) && loadingVal.IsBoolean() && loadingVal.GetBoolean();
			const bool pageClipReady = menuMc.GetMember("CurrentPage", &curPageClip) && curPageClip.IsObject();
			if (loadingFlag || !pageClipReady) {
				if (g_task) {
					g_task->AddTask([]() {
						if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
							queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
						}
					});
				}
			} else {
				auto expected = extPage;
				if (g_externalTargetPage.compare_exchange_strong(expected, -1)) {
					RE::Scaleform::GFx::Value pageArg(static_cast<std::uint32_t>(extPage));
					RE::Scaleform::GFx::Value tryRes;
					if (!InvokeMovieTracked(menuMc, "TryToSetPage", &tryRes, &pageArg, 1, "Menu_mc.TryToSetPage")) {
						REX::INFO("step=movie_call_miss where=TryToSetPage page={}", extPage);
					}
				}
			}
		}

		if (const auto mask = g_pendingPartialMask.exchange(0); mask != 0 && (g_populateInCall || g_shellVitalsFill || g_statActions || g_invDataAnswers)) {
			if (!g_dataObj.IsObject()) {
				menuMc.GetMember("DataObj", &g_dataObj);
			}
			if (g_dataObj.IsObject()) {
				const auto page = std::min<std::uint32_t>(s_savedPage.load(), 4u);
				const auto tab = s_savedTabs[page].load();
				if (g_populateInCall || g_shellVitalsFill || g_statActions) {
					FillPipboyDataObj(a_menu, a_root, g_dataObj, page, tab, "partial");
				} else if (g_invDataAnswers) {
					FillInvAndDataIntoDataObj(a_root, g_dataObj, page, tab, "partial");
				}
				RE::Scaleform::GFx::Value maskArg(mask);
				RE::Scaleform::GFx::Value partRes;
				if (!InvokeMovieTracked(menuMc, "InvalidatePartialData", &partRes, &maskArg, 1, "Menu_mc.InvalidatePartialData", false)) {
					REX::INFO("step=movie_call_miss where=InvalidatePartialData mask={:#x}", mask);
				} else {
					ApplyBottomBarDateFix(a_menu, menuMc, "partial");
				}
			}
		}
		return true;
	}

	void ShellUpdate(const void* a_menu)
	{
		if (g_closing.load()) {
			return;
		}
		const void* const movie = MovieOf(a_menu);
		if (!movie || g_codeObjMovie.load() != movie) {
			return;
		}
		g_activeShellMenu = a_menu;
		auto* const               root = RootOf(a_menu);
		RE::Scaleform::GFx::Value top;
		if (!root || !root->GetVariable(&top, "root") || !top.IsObject()) {
			REX::INFO("step=movie_call_miss where=shell_update_root");
			return;
		}
		if (IsFo4ShellActive() && !ProcessPendingShellEvents(a_menu, root, top)) {
			return;
		}
		const auto keys = g_shellKeyPending.exchange(0);
		for (std::size_t i = 0; i < g_shellKeyCount; ++i) {
			if (!(keys & (1u << i))) {
				continue;
			}
			if (IsInvalidate(g_shellKeys[i].path)) {
				SpecialReady(root, top, "keys");   // FAL-1025
			}
			bool       found = false;
			const bool called = CallPath(top, g_shellKeys[i].path, nullptr, 0, found);
			if (const auto line = ++g_shellKeyLines; line <= kMaxCodeCalls) {
				REX::INFO("step=shell_key n={} vk={} path={} found={} called={}", line, Hex(g_shellKeys[i].vk),
					g_shellKeys[i].path, found ? 1 : 0, called ? 1 : 0);
			}
			if (!called) {
				REX::INFO("step=movie_call_miss where=shell_key path={}", g_shellKeys[i].path);
				return;
			}
		}
		PipboyMap::OnShellUpdate(a_menu, root, top, g_codeObjAt, g_answerPage, g_answerTab);
		// A2.6: Once backdrop, hint-bar layout, KB+M platform, and current-page date fix have succeeded for this movie,
		// skip the ReadPath/GetMember lookup entirely on subsequent 500 ms ShellUpdate ticks.
		if (IsFo4ShellActive()) {
			const auto curPage = g_currentShellPage.load();
			const bool needBackdrop = g_shellBackdrop && g_backdropMovie.load() != movie;
			const bool needHintBar = g_hintBarDoneMovie.load() != movie;
			const bool needPlatform = g_platformDoneMovie.load() != movie;
			const bool needDateFix = (curPage == 2 || curPage == 3 || curPage < 0) &&
			                         !(g_dateFixDoneMovie.load() == movie && g_dateFixDonePage.load() == curPage);
			if (needBackdrop || needHintBar || needPlatform || needDateFix) {
				RE::Scaleform::GFx::Value menuMc;
				if (ReadPath(top, g_codeObjAt, menuMc) && menuMc.IsObject()) {
					if (needBackdrop) {
						ApplyShellBackdrop(a_menu, top, menuMc);
					}
					if (needHintBar) {
						ApplyShellHintBarLayout(a_menu, menuMc, "update");
					}
					if (needPlatform) {
						ApplyShellPlatform(a_menu, menuMc, "update");
					}
					if (needDateFix) {
						ApplyBottomBarDateFix(a_menu, menuMc, "update");
					}
				}
			}
		}
		const auto page = g_answerPage.exchange(-1);
		const auto tab = g_answerTab.exchange(-1);
		if ((page < 0 && tab < 0) || g_codeObjAt.empty()) {
			return;
		}
		const auto n = ++g_answers;
		if (n > kMaxAnswers) {
			return;   // the cap, against a shell that asks again at every InvalidateData
		}
		RE::Scaleform::GFx::Value data;
		RE::Scaleform::GFx::Value now;
		const bool                gotData = ReadPath(top, g_codeObjAt + ".DataObj", data) && data.IsObject();
		const bool pageSet = page >= 0 && gotData && data.SetMember("CurrentPage", RE::Scaleform::GFx::Value(static_cast<std::uint32_t>(page)));
		const bool tabSet = tab >= 0 && gotData && data.SetMember("CurrentTab", RE::Scaleform::GFx::Value(static_cast<std::uint32_t>(tab)));
		const auto read = [&](const char* a_member) {
			return gotData && data.GetMember(a_member, &now) ? ArgText(now) : std::string("none");
		};
		const auto pageNow = read("CurrentPage");
		const auto tabNow = read("CurrentTab");
		if (gotData) {
			SpecialReady(root, top, "answer");   // FAL-1025
		}
		bool       found = false;
		const bool invalidated = gotData && CallPath(top, g_codeObjAt + ".InvalidateData", nullptr, 0, found);
		REX::INFO("step=code_answer n={} page={} tab={} data={} page_set={} tab_set={} page_now={} tab_now={} "
				  "invalidate_found={} invalidated={}",
			n, page, tab, gotData ? 1 : 0, pageSet ? 1 : 0, tabSet ? 1 : 0, pageNow, tabNow, found ? 1 : 0, invalidated ? 1 : 0);
		if (!invalidated) {
			REX::INFO("step=movie_call_miss where=code_answer_invalidate page={} tab={}", page, tab);
		}
	}

	// The bundle ships Data\Interface\<BootMovie>.swf as a loose file under Data\Interface\ (and verify_bundle enforces
	// its presence). Check that loose file on disk before attempting a boot movie load so a missing file never locks
	// g_playingBootMovie or prevents the main Pip-Boy movie from opening.
	bool BootMovieLooseFileExists()
	{
		if (g_bootMovie.empty()) {
			return false;
		}
		const std::string relName = g_bootMovie + ".swf";
		std::error_code   ec;
		if (!g_gameDir.empty()) {
			if (std::filesystem::is_regular_file(g_gameDir / "Data" / "Interface" / relName, ec)) {
				return true;
			}
		}
		return std::filesystem::is_regular_file(std::filesystem::path("Data") / "Interface" / relName, ec);
	}

	bool MenuLoadMovie(void* a_self, bool a_dispatcher, bool a_arg2)
	{
		const auto menu = Hex(reinterpret_cast<std::uintptr_t>(a_self));
		if (g_stage == 1) {
			REX::INFO("step=load_movie menu={} dispatcher={} arg2={} stage=a result=skipped", menu, a_dispatcher, a_arg2);
			return true;
		}
		if (MovieOf(a_self)) {
			REX::INFO("step=load_movie menu={} dispatcher={} arg2={} stage=b result=already_loaded", menu, a_dispatcher, a_arg2);
			return true;
		}
		const bool attemptingBoot = g_playingBootMovie.load() && !g_bootMovie.empty();
		const char* targetMovie = attemptingBoot
		                              ? g_bootMovie.c_str()
		                              : (g_movie.empty() ? kMenuName : g_movie.c_str());
		REX::INFO("step=load_movie menu={} dispatcher={} arg2={} stage=b calling movie_name={}", menu, a_dispatcher, a_arg2,
			targetMovie);
		g_movieNameAsks.store(0);
		g_loadingMovie.store(true);
		bool loaded = g_engineLoadMovie(a_self, false, a_arg2);
		g_loadingMovie.store(false);
		REX::INFO("step=load_movie menu={} stage=b result={} movie={} movie_name={} name_asks={}", menu, loaded ? 1 : 0,
			Hex(reinterpret_cast<std::uintptr_t>(MovieOf(a_self))), targetMovie,
			g_movieNameAsks.load());
		// H0c / R10: g_engineLoadMovie resolves both loose Data\Interface\<BootMovie>.swf and BA2-packed Interface\<BootMovie>.swf;
		// if absent from both, log step=boot_skip reason=missing once and immediately load the main Pip-Boy movie.
		if (attemptingBoot && (!loaded || !MovieOf(a_self))) {
			g_playingBootMovie.store(false);
			if (!g_loggedBootSkipMissing.exchange(true)) {
				REX::INFO("step=boot_skip reason=missing movie={} file=Interface\\{}.swf", g_bootMovie, g_bootMovie);
			}
			const char* fallbackMovie = g_movie.empty() ? kMenuName : g_movie.c_str();
			REX::INFO("step=load_movie menu={} dispatcher={} arg2={} stage=b calling movie_name={}", menu, a_dispatcher,
				a_arg2, fallbackMovie);
			g_movieNameAsks.store(0);
			g_loadingMovie.store(true);
			loaded = g_engineLoadMovie(a_self, false, a_arg2);
			g_loadingMovie.store(false);
			REX::INFO("step=load_movie menu={} stage=b result={} movie={} movie_name={} name_asks={}", menu, loaded ? 1 : 0,
				Hex(reinterpret_cast<std::uintptr_t>(MovieOf(a_self))), fallbackMovie,
				g_movieNameAsks.load());
		}
		if (!loaded || !MovieOf(a_self)) {
			if (a_dispatcher) {
				// Async LoadMovie worker thread: defer non-atomic GFx teardown to MenuDestroy/kHide on the menu thread.
				REX::ERROR("step=movie_call_failed where=load_movie dispatcher=1 action=close_menu");
				g_playingBootMovie = false;
				g_bootReopenPage = -1;
				g_open = false;
				if (g_task) {
					g_task->AddTask([]() { Close(0, "load_movie"); });
				}
			} else {
				FailMovieCall("load_movie");
			}
			return false;
		}
		if (g_codeObj) {
			CodeObjInstall(a_self, "load");
		}
		return loaded;
	}

	// ------------------------------------------------------------------------------------------- FAL-852: the arm
	// Arm=1 at Stage=2 with Movie= (README, "The arm"). Key while the screen is closed sends the raise idle's animation
	// event to the player and opens the screen ArmRaiseMs after the graph took it; every close of a screen opened that
	// way (Key, or the movie's HideMenu with CodeObjHide=1) is followed by the lower: the lower idle's event, ArmLowerEvent
	// by name, or nothing, and then the raise's own clip, held by the pause while the screen was up, carries on and lowers
	// the arm by itself (PB-HOLD-1: the clip resumes from its frozen frame). Every arm line carries t_ms, the milliseconds
	// since the press that started the raise (steady clock). #776's code (FAL-714, FAL-719, FAL-725), written there for
	// its kit, taken over for Fallout 4's screen. At Arm=0 none of it runs and none of its lines is logged.
	std::int64_t SincePress() { return NowMs() - g_armPressAt.load(); }

	using LookupByEditorId_t = void* (*)(const RE::BSFixedString&);
	using NotifyGraph_t = bool (*)(void*, const RE::BSFixedString&);
	using GetGraphMgr_t = bool (*)(void*, RE::BSTSmartPointer<RE::BSAnimationGraphManager>&);
	using RegisterAnimSink_t = void (*)(void*, RE::BSTEventSink<RE::BSAnimationGraphEvent>*);
	using PlayIdleCtx_t = void* (*)();
	using ActorPlayIdle_t = bool (*)(void*, void*, std::uint32_t, void*, bool, void*, void*);

	class ArmAnimGraphSink final : public RE::BSTEventSink<RE::BSAnimationGraphEvent>
	{
	public:
		RE::BSEventNotifyControl ProcessEvent(const RE::BSAnimationGraphEvent& a_event,
			RE::BSTEventSource<RE::BSAnimationGraphEvent>*) override
		{
			const bool waitingRaise = g_armWaitingRaiseGraph.load();
			const auto lowerUntil = g_armLowerUntil.load();
			const auto now = NowMs();
			if (!waitingRaise && now >= lowerUntil) {
				return RE::BSEventNotifyControl::kContinue;
			}
			const auto evAddr = reinterpret_cast<std::uintptr_t>(&a_event);
			std::string tag;
			for (const std::size_t off : { std::size_t{ 0x00 }, std::size_t{ 0x08 }, std::size_t{ 0x10 } }) {
				std::uintptr_t entry = 0;
				std::string    cand;
				if (Peek(evAddr + off, entry) && entry && ReadPoolString(entry, cand) &&
					!cand.empty() && cand.size() <= 96 &&
					std::ranges::all_of(cand, [](unsigned char c) { return c >= 0x20 && c < 0x7F; })) {
					tag = std::move(cand);
					break;
				}
			}
			if (tag.empty()) {
				return RE::BSEventNotifyControl::kContinue;
			}
			if (waitingRaise) {
				const bool raiseReady = SameText(tag, "pipboyOpened") || SameText(tag, "WatchUp") ||
				                        SameText(tag, "AnimObjDraw") || SameText(tag, "IdleStop") ||
				                        (tag.find("Watch") != std::string::npos && SincePress() >= 350);
				if (raiseReady && g_armPendingOpenN.load() != 0 && g_armWaitingRaiseGraph.exchange(false)) {
					g_armShowAt.store(now);
					REX::INFO("step=arm_graph_event phase=raise event={} action=show_now t_ms={}", tag, SincePress());
				}
			} else if (now < lowerUntil) {
				const bool lowerDone = SameText(tag, "IdleStop") || SameText(tag, "pipboyClosed") ||
				                       SameText(tag, "AnimComplete") || SameText(tag, "WatchDown");
				if (lowerDone) {
					g_armLowerUntil.store(0);
					REX::INFO("step=arm_graph_event phase=lower event={} action=unlock t_ms={}", tag, SincePress());
				}
			}
			return RE::BSEventNotifyControl::kContinue;
		}
	};
	ArmAnimGraphSink g_armGraphSink;

	std::uintptr_t ReadPlayer3DRoot(std::uintptr_t a_player)
	{
		std::uintptr_t loadedData = 0;
		std::uintptr_t data3D = 0;
		if (a_player && Peek(a_player + kLoadedDataAt, loadedData) && loadedData) {
			Peek(loadedData + kLoadedData3DAt, data3D);
		}
		return data3D;
	}

	// A4: Clear g_armWatchedGraph WITHOUT unregistering through a potentially freed pointer whenever LoadingMenu /
	// LoadingMenuNewLocation opens, and bump g_armGraphLoadGen so a newly allocated graph reusing the same address re-registers.
	void ArmPollLoadingTransitionMainThread()
	{
		auto* const ui = RE::UI::GetSingleton();
		if (!ui) {
			return;
		}
		static auto* const kLoadingMenuFixed = new RE::BSFixedString("LoadingMenu");
		static auto* const kLoadingNewLocFixed = new RE::BSFixedString("LoadingMenuNewLocation");
		const bool loadingNow = (ui->IsMenuRegistered(*kLoadingMenuFixed) && ui->IsMenuOpen(*kLoadingMenuFixed)) ||
		                        (ui->IsMenuRegistered(*kLoadingNewLocFixed) && ui->IsMenuOpen(*kLoadingNewLocFixed));
		if (loadingNow && !g_armSawLoadingMenu) {
			g_armSawLoadingMenu = true;
			g_raiseRetry.state = kRetryIdle;
			g_armShowAt = 0;
			g_armWaitingRaiseGraph = false;
			g_armDispatching = false;
			g_armPendingOpenN = 0;
			g_armPressAt = 0;
			g_bootReopenPage = -1;
			const auto gen = ++g_armGraphLoadGen;
			if (g_armWatchedGraph != 0) {
				g_armWatchedGraph = 0;
				g_armWatchedMgrAddr = 0;
				g_armWatchedPlayer3D = 0;
				REX::INFO("step=arm_graph_sink_reset reason=loading_menu gen={}", gen);
			}
		} else if (!loadingNow && g_armSawLoadingMenu) {
			g_armSawLoadingMenu = false;
		}
	}

	void ArmSyncGraphSink()
	{
		ArmPollLoadingTransitionMainThread();
		if (!g_armGetGraphMgr || !g_armRegSinkRva) {
			return;
		}
		const auto     player = Singleton(kPlayerSingleton);
		std::uintptr_t holder = 0;
		if (!player || !Peek(player + kAnimHolderAt, holder) || holder != g_armHolderVtable) {
			if (g_armWatchedGraph != 0) {
				g_armWatchedGraph = 0;
				g_armWatchedMgrAddr = 0;
				g_armWatchedPlayer3D = 0;
				++g_armGraphLoadGen;
			}
			return;
		}
		const std::uintptr_t player3D = ReadPlayer3DRoot(player);
		RE::BSTSmartPointer<RE::BSAnimationGraphManager> mgr;
		if (!reinterpret_cast<GetGraphMgr_t>(g_armGetGraphMgr)(reinterpret_cast<void*>(player + kAnimHolderAt), mgr) || !mgr) {
			if (g_armWatchedGraph != 0) {
				g_armWatchedGraph = 0;
				g_armWatchedMgrAddr = 0;
				g_armWatchedPlayer3D = 0;
				++g_armGraphLoadGen;
			}
			return;
		}
		const auto mgrAddr = reinterpret_cast<std::uintptr_t>(mgr.get());
		const auto curGen = g_armGraphLoadGen.load();
		// A4: Inspect the live graph pointer first so 1st/3rd-person player3D swaps keeping the same live
		// BSAnimationGraph* within the same load generation do not duplicate RegisterSink; otherwise drop
		// g_armWatchedGraph WITHOUT calling UnregisterSink when load generation, manager, or 3D changed.
		std::uint32_t gSize = 0;
		std::uint32_t activeIdx = 0;
		std::uint32_t capBits = 0;
		if (!Peek(mgrAddr + 0x30, gSize) || gSize == 0 || gSize > 16 ||
			!Peek(mgrAddr + 0x38, capBits) || !Peek(mgrAddr + 0x78, activeIdx)) {
			return;
		}
		const bool          isLocal = (capBits & 0x80000000u) != 0;
		std::uintptr_t      dataPtr = 0;
		if (isLocal) {
			dataPtr = mgrAddr + 0x40;
		} else if (!Peek(mgrAddr + 0x40, dataPtr) || !dataPtr) {
			return;
		}
		const std::uint32_t idx = activeIdx < gSize ? activeIdx : 0u;
		std::uintptr_t      graphPtr = 0;
		if (!Peek(dataPtr + idx * sizeof(std::uintptr_t), graphPtr) || !graphPtr) {
			return;
		}
		if (graphPtr == g_armWatchedGraph && curGen == g_armWatchedGen) {
			g_armWatchedMgrAddr = mgrAddr;
			g_armWatchedPlayer3D = player3D;
			return;
		}
		if (g_armWatchedGraph != 0 &&
			(curGen != g_armWatchedGen || mgrAddr != g_armWatchedMgrAddr || player3D != g_armWatchedPlayer3D)) {
			g_armWatchedGraph = 0;
			g_armWatchedMgrAddr = 0;
			g_armWatchedPlayer3D = 0;
			REX::INFO("step=arm_graph_sink_reset reason=player3d_or_mgr_changed gen={}", curGen);
		}
		ObjectType gType;
		if (!TypeOf(graphPtr, gType)) {
			return;
		}
		if (g_armWatchedGraph && g_armUnregSinkRva && curGen == g_armWatchedGen && mgrAddr == g_armWatchedMgrAddr) {
			bool oldStillPresent = false;
			for (std::uint32_t gi = 0; gi < gSize; ++gi) {
				std::uintptr_t candidate = 0;
				if (Peek(dataPtr + gi * sizeof(std::uintptr_t), candidate) && candidate == g_armWatchedGraph) {
					oldStillPresent = true;
					break;
				}
			}
			ObjectType oldType;
			if (oldStillPresent && TypeOf(g_armWatchedGraph, oldType)) {
				reinterpret_cast<RegisterAnimSink_t>(g_base + g_armUnregSinkRva)(reinterpret_cast<void*>(g_armWatchedGraph), &g_armGraphSink);
			}
		}
		reinterpret_cast<RegisterAnimSink_t>(g_base + g_armRegSinkRva)(reinterpret_cast<void*>(graphPtr), &g_armGraphSink);
		g_armWatchedGraph = graphPtr;
		g_armWatchedMgrAddr = mgrAddr;
		g_armWatchedPlayer3D = player3D;
		g_armWatchedGen = curGen;
		REX::INFO("step=arm_graph_sink graph={} type={} active_idx={} count={} gen={}",
			Hex(graphPtr), gType.name, idx, gSize, curGen);
	}

	// FAL-719: an event name that looks like a file path: a '\' or '/', or ending .agx, .hkx or .hkt (any case)
	bool EventIsPath(std::string_view a_event)
	{
		if (a_event.find_first_of("\\/") != std::string_view::npos) {
			return true;
		}
		for (const std::string_view ext : { ".agx"sv, ".hkx"sv, ".hkt"sv }) {
			if (a_event.size() >= ext.size() && SameText(a_event.substr(a_event.size() - ext.size()), ext)) {
				return true;
			}
		}
		return false;
	}

	// one idle by its editor id, through the engine's lookup (libxse TESForm::LookupByEditorID, CheckArmId), on the main
	// thread: a TESIdleForm by its RTTI, form type IDLE (+0x2E), with an animation event. Its form id, graph and event are
	// logged, and every pool string from +0x58 to +0x80 once, read only (FAL-719: the layout is shown, not assumed)
	std::uintptr_t ArmIdleForm(std::string_view a_which, const std::string& a_editorId)
	{
		static std::vector<RE::BSFixedString*> names;   // process lifetime: a BSFixedString destructor calls the engine
		names.push_back(new RE::BSFixedString(a_editorId.c_str()));
		auto form = reinterpret_cast<std::uintptr_t>(
			reinterpret_cast<LookupByEditorId_t>(g_base + g_armLookupRva)(*names.back()));
		if (!form && SameText(a_editorId, "idleexaminewatch") && g_rva[kLookupById] != 0) {
			form = ShellFormLookup(kIdleExamineWatchFormId);
		}
		if (!form) {
			Refuse("arm_idle", std::format("which={} editor_id={} reason=not_found t_ms={}", a_which, a_editorId, SincePress()));
			return 0;
		}
		ObjectType    type;
		std::uint32_t formId = 0;
		std::uint8_t  formType = 0;
		const bool    typed = IsType(form, "TESIdleForm@@", type);
		Peek(form + kFormIdAt, formId);
		Peek(form + kFormTypeAt, formType);
		if (!typed || formType != kIdleType) {
			Refuse("arm_idle", std::format("which={} editor_id={} reason=not_idle form={:08X} type={:#x} rtti={} t_ms={}",
				a_which, a_editorId, formId, formType, type.name.empty() ? "unreadable" : type.name, SincePress()));
			return 0;
		}
		std::string slots;
		for (std::size_t at = kIdleSlotFirst; at <= kIdleSlotLast; at += 8) {
			std::uintptr_t entry = 0;
			std::string    text;
			const bool     read = Peek(form + at, entry) && ReadPoolString(entry, text);
			slots += std::format(" s{:x}={}", at, read && !text.empty() ? text : "-");
		}
		REX::INFO("step=arm_idle_slots which={} form={:08X}{} t_ms={}", a_which, formId, slots, SincePress());
		std::uintptr_t graphEntry = 0;
		std::uintptr_t eventEntry = 0;
		std::string    graph;
		std::string    event;
		const bool     gotGraph = Peek(form + kIdleGraphAt, graphEntry) && ReadPoolString(graphEntry, graph);
		const bool     gotEvent = Peek(form + kIdleEventAt, eventEntry) && ReadPoolString(eventEntry, event);
		if (!gotEvent || event.empty()) {
			Refuse("arm_idle", std::format("which={} editor_id={} reason=no_event form={:08X} type={:#x} graph={} t_ms={}",
				a_which, a_editorId, formId, formType, gotGraph && !graph.empty() ? graph : "-", SincePress()));
			return 0;
		}
		if (EventIsPath(event)) {   // FAL-719: a file path is not an animation event
			Refuse("arm_idle", std::format("which={} editor_id={} reason=event_is_path slot={:#x} value={} form={:08X} t_ms={}",
				a_which, a_editorId, kIdleEventAt, event, formId, SincePress()));
			return 0;
		}
		REX::INFO("step=arm_idle which={} editor_id={} form={:08X} type={:#x} graph={} event={} t_ms={}", a_which, a_editorId,
			formId, formType, gotGraph && !graph.empty() ? graph : "-", event, SincePress());
		return form;
	}

	// the player's IAnimationGraphManagerHolder, as CheckActorValues checks ActorValueOwner: the base's offset from
	// PlayerCharacter's RTTI hierarchy (libxse: 0x60), its vtable's locator naming PlayerCharacter there, slot 0x00 the
	// adjustor thunk to the player's own destructor, and slots 0x01 / 0x03 inside the image
	int ArmHolder()
	{
		ObjectType type;
		const auto player = Singleton(kPlayerSingleton);
		if (!player) {
			return -1;
		}
		if (!CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk) || !TypeOf(player, type)) {
			Refuse("arm_holder", std::format("reason=player_type t_ms={}", SincePress()));
			return 0;
		}
		const auto     at = BaseOffset(type, "IAnimationGraphManagerHolder@@");
		std::uintptr_t primary = 0;
		std::uintptr_t holder = 0;
		if (!at || *at != kAnimHolderAt || !CheckSubobject(player, type, *at) || !Peek(player, primary) ||
			!Peek(player + *at, holder) || !InImage(primary, 8) || !InImage(holder, (kGetGraphMgrSlot + 1) * 8)) {
			Refuse("arm_holder", std::format("reason=holder offset={} expected={} t_ms={}", at ? Hex(*at) : "none",
				Hex(kAnimHolderAt), SincePress()));
			return 0;
		}
		const auto* slots = reinterpret_cast<const std::uintptr_t*>(holder);
		const auto  destructor = *reinterpret_cast<const std::uintptr_t*>(primary);
		const auto  target0 = ThunkTarget(slots[0], *at);
		const auto  rva = [](std::uintptr_t a_addr) { return InImage(a_addr, 1) ? Hex(a_addr - g_base) : Hex(a_addr); };
		if (target0 != destructor || !InImage(slots[kNotifyGraphSlot], 1)) {
			Refuse("arm_holder", std::format("reason=slots offset={} slot0={} target0={} destructor={} slot1={} t_ms={}",
				Hex(*at), rva(slots[0]), rva(target0), rva(destructor), rva(slots[kNotifyGraphSlot]), SincePress()));
			return 0;
		}
		g_armHolderVtable = holder;
		g_armNotify = slots[kNotifyGraphSlot];
		g_armGetGraphMgr = InImage(slots[kGetGraphMgrSlot], 1) ? slots[kGetGraphMgrSlot] : 0;
		REX::INFO("step=arm_holder offset={} vtable={} destructor_slot=0x00 notify_slot=0x01 slot={} get_mgr_slot={} t_ms={}",
			Hex(*at), rva(holder), rva(g_armNotify), g_armGetGraphMgr ? rva(g_armGetGraphMgr) : "none", SincePress());
		return 1;
	}

	// main thread, once (on the first raise with a player): the player's holder, the raise idle, and the lower (an idle,
	// an event by name, or none)
	bool ArmResolve()
	{
		if (g_armState >= 0) {
			return g_armState == 1;
		}
		const int holder = ArmHolder();
		if (holder < 0) {
			return false;   // no player yet: tried again on the next press
		}
		g_raiseIdle = ArmIdleForm("raise", g_armRaiseIdle);
		bool lower = true;
		if (!g_armLowerIdle.empty()) {
			g_lowerIdle = ArmIdleForm("lower", g_armLowerIdle);
			lower = g_lowerIdle != 0;
		} else if (!g_armLowerEvent.empty()) {
			g_lowerEvent = new RE::BSFixedString(g_armLowerEvent.c_str());   // process lifetime, as ArmIdleForm's
			REX::INFO("step=arm_idle which=lower event={} (by name, no idle) t_ms={}", g_armLowerEvent, SincePress());
		}
		g_armState = holder == 1 && g_raiseIdle && lower ? 1 : 0;
		return g_armState == 1;
	}

	// an animation event to the player (NotifyAnimationGraphImpl, called with this = player + 0x60), main thread only.
	// Used ONLY for explicit ArmLowerEvent= override; raise/lower TESIdleForms use Actor.PlayIdle exclusively (Step 1i).
	std::string ArmNotify(const RE::BSFixedString& a_event)
	{
		const auto     player = Singleton(kPlayerSingleton);
		std::uintptr_t holder = 0;
		if (!player) {
			return "no_player";
		}
		if (!Peek(player + kAnimHolderAt, holder) || holder != g_armHolderVtable) {
			return "holder_changed";
		}
		const bool sent = reinterpret_cast<NotifyGraph_t>(g_armNotify)(reinterpret_cast<void*>(player + kAnimHolderAt), a_event);
		return sent ? "1" : "0";
	}

	// Task 1 step 1i: Starfield's own TESIdleForm / AIProcess::PlayIdle call (REL::ID 102136 + context REL::ID 35720)
	// on Actor::currentProcess (+0x228) with action 0x36 (ActionIdle). Never falls back to refused DynamicIdle graph events.
	std::string ArmPlayIdle(std::uintptr_t a_idle)
	{
		const auto player = Singleton(kPlayerSingleton);
		if (!player) {
			return "no_player";
		}
		ArmSyncGraphSink();
		std::uint32_t formId = 0;
		Peek(a_idle + kFormIdAt, formId);
		void* process = nullptr;
		if (!g_armPlayIdleRva || !g_armPlayIdleCtxRva || !Peek(player + kActorCurrentProcessAt, process) || !process) {
			REX::INFO("step=arm_play_idle form={:08X} process=0 played=0 accepted=0 t_ms={}", formId, SincePress());
			return "0";
		}
		void* const ctx = reinterpret_cast<PlayIdleCtx_t>(g_base + g_armPlayIdleCtxRva)();
		const bool  played = reinterpret_cast<ActorPlayIdle_t>(g_base + g_armPlayIdleRva)(
			process, reinterpret_cast<void*>(player), 0x36u, reinterpret_cast<void*>(a_idle), true, nullptr, ctx);
		REX::INFO("step=arm_play_idle form={:08X} process={} played={} accepted={} t_ms={}", formId,
			Hex(reinterpret_cast<std::uintptr_t>(process)), played ? 1 : 0, played ? 1 : 0, SincePress());
		return played ? "1" : "0";
	}

	bool ArmLowerSet() { return !g_armLowerIdle.empty() || !g_armLowerEvent.empty(); }

	void ArmRetryStart(ArmRetry& a_retry, std::uint32_t a_n)
	{
		const auto now = NowMs();
		a_retry.n = a_n;
		a_retry.firstAt = now;
		a_retry.nextAt = now;
		a_retry.deadline = now + g_armRetryMs;
		a_retry.tries = 0;
		a_retry.state = kRetryInFlight;
	}

	std::string ArmRetryOutcome(ArmRetry& a_retry, const std::string& a_result)
	{
		const auto now = NowMs();
		if (a_result == "0" && now + kArmRetryEveryMs <= a_retry.deadline.load()) {
			a_retry.nextAt = now + kArmRetryEveryMs;
			a_retry.state = kRetryWaiting;
			return {};
		}
		a_retry.state = kRetryIdle;
		return a_result == "0" ? std::string("gave_up") : a_result;
	}

	// main thread: Key or MapKey while closed. Plays the watch raise idle; if accepted=1, waits for the raise graph event
	// (with ArmRaiseMs timeout fallback); if accepted=0 (third person or weapon drawn), opens immediately without hanging.
	void ArmRaise(std::uint32_t a_n)
	{
		if (g_armPendingOpenN.load() != a_n || g_armShown.load()) {
			g_raiseRetry.state = kRetryIdle;
			g_armWaitingRaiseGraph = false;
			return;
		}
		if (const char* blocking = OpenBlockingOverlayMenu(RE::UI::GetSingleton())) {
			g_raiseRetry.state = kRetryIdle;
			g_armWaitingRaiseGraph = false;
			g_armShowAt = 0;
			g_armPendingOpenN = 0;
			g_armPressAt = 0;
			REX::INFO("step=arm_raise n={} ignored=menu_open menu={} accepted=0 t_ms={}", a_n, blocking, SincePress());
			return;
		}
		const auto  tries = ++g_raiseRetry.tries;
		std::string result;
		if (!ArmResolve()) {
			result = g_armState == 0 ? "refused" : "no_player";
		} else {
			result = ArmPlayIdle(g_raiseIdle);
		}
		const int accepted = (result == "1") ? 1 : 0;
		if (tries == 1) {
			REX::INFO("step=arm_raise n={} result={} try=1 accepted={} t_ms={}", a_n, result, accepted, SincePress());
		}
		// A13: Retry refused raise (result == "0") every 100 ms up to ArmRetryMs (FO4SFPipboyMenu.ini); if it gives up,
		// open the screen cleanly without stalling indefinitely.
		if (g_armRetryMs == 0) {
			g_raiseRetry.state = kRetryIdle;
		}
		const auto outcome = g_armRetryMs == 0 ? result : ArmRetryOutcome(g_raiseRetry, result);
		if (outcome.empty()) {
			return;
		}
		if (g_armPendingOpenN.load() != a_n || g_armShown.load()) {
			g_armWaitingRaiseGraph = false;
			return;
		}
		g_armRaiseOutcome = outcome;
		g_armRaiseAccepted = (outcome == "1");
		const auto showLeadMs = (outcome == "1") ? g_armRaiseMs : 0u;
		REX::INFO("step=arm_raise_done n={} result={} accepted={} tries={} waited_ms={} show_in_ms={} t_ms={}", a_n, outcome,
			outcome == "1" ? 1 : 0, tries, NowMs() - g_raiseRetry.firstAt.load(), showLeadMs, SincePress());
		// Store g_armShowAt BEFORE arming g_armWaitingRaiseGraph so an immediate ArmAnimGraphSink event cannot be overwritten.
		if (outcome == "1") {
			g_armShowAt = NowMs() + g_armRaiseMs;
			g_armWaitingRaiseGraph.store(true, std::memory_order_release);
		} else {
			g_armWaitingRaiseGraph.store(false, std::memory_order_release);
			g_armShowAt = NowMs();
		}
	}

	// main thread: the screen opened by the arm was hidden (any route), and a lower is set
	void ArmLower(std::uint32_t a_n)
	{
		const auto tries = ++g_lowerRetry.tries;
		std::string result = "refused";
		if (g_armState == 1) {
			result = g_lowerIdle ? ArmPlayIdle(g_lowerIdle) : g_lowerEvent ? ArmNotify(*g_lowerEvent) : std::string("refused");
		}
		const int accepted = (result == "1") ? 1 : 0;
		if (tries == 1) {
			REX::INFO("step=arm_lower n={} send={} result={} try=1 accepted={} t_ms={}", a_n, g_lowerIdle ? "idle" : "event",
				result, accepted, SincePress());
		}
		if (g_armRetryMs == 0) {
			g_lowerRetry.state = kRetryIdle;
		}
		const auto outcome = g_armRetryMs == 0 ? result : ArmRetryOutcome(g_lowerRetry, result);
		if (outcome.empty()) {
			return;
		}
		if (outcome == "1") {
			g_armLowerUntil = NowMs() + g_armLowerMs;
		} else {
			g_armLowerUntil = 0;
		}
		REX::INFO("step=arm_lower_done n={} result={} accepted={} tries={} waited_ms={} lock_ms={} t_ms={}", a_n, outcome,
			outcome == "1" ? 1 : 0, tries, NowMs() - g_lowerRetry.firstAt.load(), outcome == "1" ? g_armLowerMs : 0, SincePress());
	}

	// on the menu's thread, after the engine's own handling of kShow or kHide: logs step=arm_lower ... accepted=<0|1> on every close
	void ArmMessage(bool a_show)
	{
		if (a_show) {
			g_armWaitingRaiseGraph = false;
			g_armPendingOpenN = 0;
			g_armShown = true;
			REX::INFO("step=arm_shown n={} accepted={} t_ms={}", g_armN.load(), g_armRaiseAccepted.load() ? 1 : 0, SincePress());
			return;
		}
		if (!g_armShown.exchange(false)) {
			return;
		}
		g_armWaitingRaiseGraph = false;
		g_armPendingOpenN = 0;
		const auto elapsed = SincePress();
		g_armPressAt = 0;
		const auto n = g_armN.load();
		if (!ArmLowerSet()) {
			const int  accepted = g_armRaiseAccepted.load() ? 1 : 0;
			const auto lockMs = accepted ? g_armLowerMs : 0u;
			g_armLowerUntil = accepted ? (NowMs() + g_armLowerMs) : 0;
			REX::INFO("step=arm_lower n={} send=none (the raise's clip carries on) accepted={} lock_ms={} t_ms={}",
				n, accepted, lockMs, elapsed);
			return;
		}
		ArmRetryStart(g_lowerRetry, n);
		g_task->AddTask([n]() { ArmLower(n); });
	}

	RE::UI_MESSAGE_RESULT MenuProcessMessage(void* a_self, RE::UIMessageData& a_message)
	{
		const auto type = a_message.type;
		if (type == RE::UI_MESSAGE_TYPE::kShow) {
			g_closing.store(false);
			PipboyMap::SetClosing(false);
		} else if (type == RE::UI_MESSAGE_TYPE::kHide) {
			g_closing.store(true);
			PipboyMap::SetClosing(true);
		}
		if (g_stage == 2 && g_codeObj && type == RE::UI_MESSAGE_TYPE::kHide) {
			// Step 2: invoke Menu_mc.onCodeObjDestruction() BEFORE g_engineProcessMessage destroys uiMovie
			ShellHideTeardown(a_self);
		}
		if (g_stage >= 3 && type == RE::UI_MESSAGE_TYPE::kShow) {
			ApplyFlagSet(a_self, ++g_shows);
		}
		if (g_stage >= 2 && type == RE::UI_MESSAGE_TYPE::kShow && !MovieOf(a_self)) {
			REX::INFO("step=load_movie menu={} caller=plugin before=show", Hex(reinterpret_cast<std::uintptr_t>(a_self)));
			MenuLoadMovie(a_self, false, false);
		}
		const auto result = g_stage == 1 && type == RE::UI_MESSAGE_TYPE::kShow ?
		                        RE::UI_MESSAGE_RESULT::kHandled :
		                        g_engineProcessMessage(a_self, a_message);
		const bool showOrHide = type == RE::UI_MESSAGE_TYPE::kShow || type == RE::UI_MESSAGE_TYPE::kHide;
		if (showOrHide || g_otherMessages.fetch_add(1) < 20) {
			const auto name = type == RE::UI_MESSAGE_TYPE::kShow ? "show"sv :
			                  type == RE::UI_MESSAGE_TYPE::kHide ? "hide"sv :
			                  type == RE::UI_MESSAGE_TYPE::kUpdate ? "update"sv :
			                                                         "other"sv;
			REX::INFO("step=message menu={} type={} raw={} result={}", Hex(reinterpret_cast<std::uintptr_t>(a_self)), name,
				static_cast<std::uint32_t>(type), static_cast<std::int64_t>(result));
		}
		if (g_stage == 2 && g_codeObj &&
			(type == RE::UI_MESSAGE_TYPE::kShow || type == RE::UI_MESSAGE_TYPE::kUpdate)) {   // FAL-614 proof 1b
			CodeObjInstall(a_self, type == RE::UI_MESSAGE_TYPE::kShow ? "show" : "update");
		}
		const std::int32_t bootReopen = (type == RE::UI_MESSAGE_TYPE::kHide) ? g_bootReopenPage.exchange(-1) : -1;
		if (g_arm && showOrHide && bootReopen < 0) {   // FAL-852 / N1: skip arm lower across boot_done -> FO4SF_Fo4Shell transition
			if (!(type == RE::UI_MESSAGE_TYPE::kShow && g_armShown.load())) {
				ArmMessage(type == RE::UI_MESSAGE_TYPE::kShow);
			}
		}
		if (showOrHide) {
			g_open = (type == RE::UI_MESSAGE_TYPE::kShow);
			g_lastShellTransitionMs.store(NowMs());
			g_cancelHeld = false;
			PipboyMap::OnMenuMessage(type);
			if (g_stage == 2 && g_codeObj && type == RE::UI_MESSAGE_TYPE::kShow) {
				ShellShowInit(a_self);
			}
			if (type == RE::UI_MESSAGE_TYPE::kHide) {
				ClearMovieSessionState();
				if (bootReopen >= 0 && g_task) {
					const auto targetPage = static_cast<std::uint32_t>(std::min<std::int32_t>(bootReopen, 4));
					g_task->AddTask([targetPage]() {
						s_savedPage.store(targetPage);
						auto* ui = RE::UI::GetSingleton();
						auto* queue = RE::UIMessageQueue::GetSingleton();
						if (!ui || !queue || ui->IsMenuOpen(MenuName()) || OpenBlockingOverlayMenu(ui)) {
							if (g_arm && g_armShown.load()) {
								ArmMessage(false);
							}
							return;
						}
						if (g_stage == 2 && g_codeObj) {
							CollectShellVitalsMainThread(targetPage);
						}
						g_expectOpen = 1;
						queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kShow);
						REX::INFO("step=boot_reopen page={} sent=show", targetPage);
					});
				}
			}
		}
		if (g_stage == 2 && g_codeObj && type == RE::UI_MESSAGE_TYPE::kUpdate) {   // FAL-614 S1-c: keys, then answers
			ShellUpdate(a_self);
		}
		if (g_stage >= 3) {   // stages c, d and e: after the engine's own handling, on its thread for this menu
			if (type == RE::UI_MESSAGE_TYPE::kShow) {
				if (g_stage == 5) {   // the kit opens on the page it showed last
					KitListen(a_self);
					KitWrite(a_self, 0, true);
				} else if (g_stage == 4) {   // the page opens on its first tab
					g_tab = 0;
					PageListen(a_self);
					PageWrite(a_self, 0);
				} else {
					ChannelListen(a_self);
					ChannelWrite(a_self, 0);
				}
				Snapshot("show");
			} else if (type == RE::UI_MESSAGE_TYPE::kUpdate) {
				const auto n = ++g_updates;
				if (g_stage == 5) {
					KitWrite(a_self, n, false);
				} else if (g_stage == 4) {
					PageWrite(a_self, n);
				} else {
					ChannelWrite(a_self, n);
				}
				if (n % 10 == 1) {
					Snapshot("open");
				}
			} else if (type == RE::UI_MESSAGE_TYPE::kHide) {
				Snapshot("hide");
			}
		}
		return result;
	}

	bool MenuIsMovieLoaded(void*) { return true; }   // stage a: the admission check the engine's answers with uiMovie

	// the creator UI calls on kShow. The engine passes uninitialised storage for a Scaleform::Ptr<IMenu> (MSVC's hidden
	// return slot); the menu pointer is written there owning the constructor's reference, as the engine's own creators do
	// FAL-414: the menu's own cancel handling. Both input slots are called with this = menu + 0x10 (BSInputEventUser).
	// A keyboard button whose id is in CancelCodes (or whose user event is "Cancel"), while the menu is open, is ours:
	// [01] says we handle it, [08] marks it kStop (the pause menu's ShouldHandleEvent refuses a stopped event) and, on the
	// press (value > 0, heldDownSecs == 0), asks the key thread to close the menu. Everything else goes to the engine's.
	struct CancelLook
	{
		bool          mine = false;
		bool          press = false;
		std::uint32_t code = 0;
	};

	CancelLook LookAtEvent(const void* a_event, bool a_log)
	{
		CancelLook look;
		if (!a_event || !g_open) {
			return look;
		}
		if (OpenBlockingOverlayMenu(RE::UI::GetSingleton(), true) != nullptr) {
			return look;   // Let Console / MessageBoxMenu / PauseMenu own Esc & Tab when stacked above PipboyMenu
		}
		const auto* base = static_cast<const RE::InputEvent*>(a_event);
		if (base->eventType != RE::InputEvent::EventType::kButton || base->deviceType != RE::InputEvent::DeviceType::kKeyboard) {
			return look;
		}
		const auto* button = static_cast<const RE::ButtonEvent*>(a_event);
		look.code = static_cast<std::uint32_t>(button->idCode);
		const std::string_view user = button->strUserEvent.c_str() ? std::string_view(button->strUserEvent.c_str()) : std::string_view{};
		bool cancel = user == "Cancel";
		for (std::size_t i = 0; i < g_cancelCount; ++i) {
			cancel = cancel || look.code == g_cancelCodes[i];
		}
		look.mine = cancel;
		look.press = button->value > 0.0f && button->heldDownSecs == 0.0f;
		if (a_log && g_cancelLogged.load() < 40 && (cancel || look.press)) {   // the first presses: which id and user event the game sends
			++g_cancelLogged;
			REX::INFO("step=input id={} user_event=\"{}\" value={} held={} status={} cancel={}", Hex(look.code), user, button->value,
				button->heldDownSecs, static_cast<std::uint32_t>(base->status), cancel ? 1 : 0);
		}
		return look;
	}

	bool a_eventValueIsRelease(const void* a_event)
	{
		return static_cast<const RE::ButtonEvent*>(a_event)->value == 0.0f;
	}

	struct ShellInputDecision
	{
		bool             intercept = false;
		bool             passToScaleformToo = false;
		bool             isToggleKey = false;
		bool             isCancel = false;
		bool             press = false;
		bool             release = false;
		std::uint32_t    code = 0;
		std::string_view shellEvent;
	};

	ShellInputDecision InspectShellOpenButton(const void* a_event, bool a_log)
	{
		ShellInputDecision out;
		if (!a_event || !g_open || !IsFo4ShellActive()) {
			return out;
		}
		if (OpenBlockingOverlayMenu(RE::UI::GetSingleton(), true) != nullptr) {
			return out;
		}
		const auto* base = static_cast<const RE::InputEvent*>(a_event);
		if (base->eventType != RE::InputEvent::EventType::kButton ||
			(base->deviceType != RE::InputEvent::DeviceType::kKeyboard && base->deviceType != RE::InputEvent::DeviceType::kGamepad)) {
			return out;
		}
		const auto* button = static_cast<const RE::ButtonEvent*>(a_event);
		out.code = static_cast<std::uint32_t>(button->idCode);
		out.press = button->value > 0.0f && button->heldDownSecs == 0.0f;
		out.release = a_eventValueIsRelease(a_event);
		const std::string_view user = button->strUserEvent.c_str() ? std::string_view(button->strUserEvent.c_str()) : std::string_view{};

		bool cancel = user == "Cancel";
		if (base->deviceType == RE::InputEvent::DeviceType::kKeyboard) {
			for (std::size_t i = 0; i < g_cancelCount; ++i) {
				cancel = cancel || out.code == g_cancelCodes[i];
			}
			if (out.code == g_key) {
				out.intercept = true;
				out.isToggleKey = true;
			} else if (cancel) {
				out.intercept = true;
				out.isCancel = true;
				out.shellEvent = "Cancel"sv;
			} else {
				switch (out.code) {
				case 0x57: out.intercept = true; out.shellEvent = "Forward"sv; break;       // W -> prev page (unless consumed by page)
				case 0x53: out.intercept = true; out.shellEvent = "Back"sv; break;          // S -> next page
				case 0x21: out.intercept = true; out.shellEvent = "LTrigger"sv; break;      // PageUp -> prev page
				case 0x22: out.intercept = true; out.shellEvent = "RTrigger"sv; break;      // PageDown -> next page
				case 0x41: out.intercept = true; out.shellEvent = "StrafeLeft"sv; break;    // A -> prev tab
				case 0x44: out.intercept = true; out.shellEvent = "StrafeRight"sv; break;   // D -> next tab
				case 0x54: out.intercept = true; out.shellEvent = "YButton"sv; break;       // T -> Perk Chart / Grid View
				case 0x45: out.intercept = true; out.passToScaleformToo = true; break;      // E -> native Keyboard.E (UseStimpak)
				case 0x51: out.intercept = true; out.passToScaleformToo = true; out.shellEvent = "RShoulder"sv; break; // Q -> ToggleShowingEffects
				case 0x52: out.intercept = true; out.passToScaleformToo = true; out.shellEvent = "XButton"sv; break;   // R -> UseRadaway / Drop
				default: break;
				}
			}
		} else {
			if (cancel) {
				out.intercept = true;
				out.isCancel = true;
				out.shellEvent = "Cancel"sv;
			} else if (user == "LTrigger" || user == "RTrigger" || user == "LShoulder" || user == "RShoulder" ||
			           user == "XButton" || user == "YButton" || user == "StrafeLeft" || user == "StrafeRight" ||
			           user == "Forward" || user == "Back") {
				out.intercept = true;
				out.shellEvent = user;
			}
		}

		if (a_log && g_cancelLogged.load() < 40 && (out.intercept || out.press)) {
			++g_cancelLogged;
			REX::INFO("step=input id={} user_event=\"{}\" value={} held={} status={} cancel={} shell_event=\"{}\"",
				Hex(out.code), user, button->value, button->heldDownSecs,
				static_cast<std::uint32_t>(base->status), out.isCancel ? 1 : 0, out.shellEvent);
		}
		return out;
	}

	std::atomic<std::uint32_t> g_openPressSeq{ 0 };

	bool MenuShouldHandleEvent(void* a_input, const void* a_event)
	{
		if (PipboyMap::ShouldHandleInput(a_event)) {
			return true;
		}
		if (IsFo4ShellActive()) {
			const auto dec = InspectShellOpenButton(a_event, false);
			if (dec.intercept && static_cast<const RE::InputEvent*>(a_event)->status != RE::InputEvent::Status::kStop) {
				return true;
			}
			return g_engineShouldHandle(a_input, a_event);
		}
		const auto look = LookAtEvent(a_event, false);
		if (look.mine && static_cast<const RE::InputEvent*>(a_event)->status != RE::InputEvent::Status::kStop) {
			return true;
		}
		return g_engineShouldHandle(a_input, a_event);
	}

	void MenuOnButtonEvent(void* a_input, const void* a_event)
	{
		if (PipboyMap::OnButtonInput(a_event)) {
			return;
		}
		if (IsFo4ShellActive()) {
			const auto dec = InspectShellOpenButton(a_event, true);
			if (!dec.intercept) {
				g_engineOnButton(a_input, a_event);
				return;
			}
			if (dec.passToScaleformToo) {
				g_engineOnButton(a_input, a_event);
			}
			const_cast<RE::InputEvent*>(static_cast<const RE::InputEvent*>(a_event))->status = RE::InputEvent::Status::kStop;
			if (dec.isToggleKey) {
				if (dec.press && !g_keyInputHeld.exchange(true)) {
					const auto n = ++g_openPressSeq;
					if (g_task) {
						g_task->AddTask([n]() { Close(n, "key"); });
					}
				} else if (dec.release) {
					g_keyInputHeld = false;
				}
				return;
			}
			if (dec.isCancel) {
				if (dec.press && !g_cancelHeld.exchange(true)) {
					g_pendingCancelRelease = true;
					QueueShellUserEvent("Cancel", true);
				} else if (dec.release) {
					const bool hadPress = g_cancelHeld.exchange(false) || g_pendingCancelRelease.exchange(false);
					if (hadPress) {
						QueueShellUserEvent("Cancel", false);
					}
				}
				return;
			}
			if (!dec.shellEvent.empty() && (dec.press || dec.release)) {
				QueueShellUserEvent(dec.shellEvent, dec.press);
			}
			return;
		}
		const auto look = LookAtEvent(a_event, true);
		if (!look.mine) {
			g_engineOnButton(a_input, a_event);
			return;
		}
		const_cast<RE::InputEvent*>(static_cast<const RE::InputEvent*>(a_event))->status = RE::InputEvent::Status::kStop;
		// the game sends one press as several events (held=0, 0.009, 0.017, ...): close on the first only, and
		// not again until a release (value == 0) has been seen
		if (look.press && !g_cancelHeld.exchange(true)) {
			g_cancelNow = true;
		} else if (a_eventValueIsRelease(a_event)) {
			g_cancelHeld = false;
		}
	}

	// ------------------------------------------------------------------------------------------- Task 1 step 1k (UI-3): FO4SF_SpecialMenu
	// Opt-in second IMenu host (SpecialMenu=1, default 0, NOT WIRED to Vault 111 lift per R14) loading Fallout 4's
	// SPECIALMenu.swf staged privately on the PC (Interface/<SpecialMovie>.swf), installing a plain-Object BGSCodeObj
	// holder (Menu_mc.BGSCodeObj / CreateObject), enforcing SpecialMaxPoints=40 (refusing increments when pointsRemaining <= 0),
	// and handing the 7 chosen S.P.E.C.I.A.L. values to FO4SF_ProgressionQuest via FO4SFCoreValues.esm globals (0x000880..0x000887).
	const RE::BSFixedString& SpecialMenuName()
	{
		static auto* const name = new RE::BSFixedString(fo4sf::kOurSpecialMenuName);
		return *name;
	}

	constexpr std::array<const char*, 11> kSpecialCodeObjNames{
		"initMenu",
		"modValue",
		"startEditText",
		"endEditText",
		"confirmResetPoints",
		"tryCloseMenu",
		"playSound",
		"PlayPerkSound",
		"StopPerkSound",
		"OnScrollingStarted",
		"OnScrollingStopped",
	};

	const void*                 g_activeSpecialMenu = nullptr;
	RE::Scaleform::GFx::Value   g_specialEntryList;
	std::array<std::int32_t, 7> g_specialValues{ 1, 1, 1, 1, 1, 1, 1 };
	std::string                 g_specialPlayerName = "Sole Survivor";
	std::mutex                  g_specialEventLock;
	std::vector<PendingUserEvent> g_pendingSpecialEvents;
	std::atomic<bool>           g_specialCancelHeld{ false };
	std::atomic<std::uint32_t>  g_specialCodeCalls{ 0 };

	void QueueSpecialUserEvent(std::string_view a_name, bool a_isDown)
	{
		{
			std::scoped_lock lock(g_specialEventLock);
			if (g_pendingSpecialEvents.size() < 32) {
				g_pendingSpecialEvents.push_back({ std::string(a_name), a_isDown });
			}
		}
		if (g_task) {
			g_task->AddTask([]() {
				if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
					queue->AddMessage(SpecialMenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
				}
			});
		}
	}

	bool WriteCoreGlobalFloatVerified(std::uintptr_t a_globForm, std::size_t a_valAt, float a_want)
	{
		if (!a_globForm || !a_valAt) {
			return false;
		}
		float existing = 0.0f;
		if (!Peek(a_globForm + a_valAt, existing)) {
			return false;
		}
		*reinterpret_cast<float*>(a_globForm + a_valAt) = a_want;
		float rb = 0.0f;
		return Peek(a_globForm + a_valAt, rb) && std::isfinite(rb) && std::fabs(rb - a_want) <= 1e-4f;
	}

	// A3 & A12: Never call SetBaseActorValue directly in native code. Write the 7 chosen S.P.E.C.I.A.L. values into
	// FO4SFCoreValues.esm (0x000880..0x000886) and set FO4SF_SpecialMenuCommitRequested (0x000887) = 1.0 so
	// FO4SF_ProgressionQuest applies them through its single write path (recomputing skills & derived CarryWeight).
	void CommitSpecialMenuMainThread(std::array<std::int32_t, 7> a_vals, std::string a_name)
	{
		PageScan();
		FindGlobalValue();

		static bool                         s_loggedSpecialStoreResolve = false;
		static std::array<std::uintptr_t, 7> s_pendingGlobs{};
		static std::uintptr_t               s_commitReqGlob = 0;

		std::size_t fromCore = 0;
		for (std::size_t i = 0; i < kSpecialPendingEditorIds.size(); ++i) {
			std::string         detail;
			const std::uint32_t localId = kCoreSpecialMenuPendingFirstId + static_cast<std::uint32_t>(i);
			const auto          fid = KitFileForm("FO4SFCoreValues.esm", localId, "TESGlobal@@", detail);
			if (fid) {
				AcceptById(fid, kSpecialPendingEditorIds[i], "TESGlobal@@", kGlobalEditorIdAt, s_pendingGlobs[i]);
				if (s_pendingGlobs[i]) {
					++fromCore;
				}
			}
			if (!s_loggedSpecialStoreResolve) {
				LogCoreValueResolve(kSpecialPendingEditorIds[i], localId, s_pendingGlobs[i] ? fid : 0u);
			}
		}
		{
			std::string reqDetail;
			const auto  reqFid = KitFileForm("FO4SFCoreValues.esm", kCoreSpecialMenuCommitReqId, "TESGlobal@@", reqDetail);
			if (reqFid) {
				AcceptById(reqFid, "FO4SF_SpecialMenuCommitRequested", "TESGlobal@@", kGlobalEditorIdAt, s_commitReqGlob);
			}
			if (!s_loggedSpecialStoreResolve) {
				LogCoreValueResolve("FO4SF_SpecialMenuCommitRequested", kCoreSpecialMenuCommitReqId, s_commitReqGlob ? reqFid : 0u);
				s_loggedSpecialStoreResolve = true;
			}
		}

		const std::size_t valAt = g_forms.globalValueAt ? g_forms.globalValueAt : kGlobalValueAt;
		std::size_t       written = 0;
		if (fromCore == 7 && s_commitReqGlob) {
			for (std::size_t i = 0; i < 7; ++i) {
				const float v = static_cast<float>(std::clamp(a_vals[i], 1, 10));
				if (WriteCoreGlobalFloatVerified(s_pendingGlobs[i], valAt, v)) {
					++written;
				}
			}
			if (written == 7) {
				if (!WriteCoreGlobalFloatVerified(s_commitReqGlob, valAt, 1.0f)) {
					written = 0;
				}
			}
		}

		int sum = 0;
		for (const int v : a_vals) {
			sum += v;
		}
		const char* source = (written == 7) ? "FO4SFCoreValues.esm" : "unwritten";
		REX::INFO("step=special_done sum={} max_points={} written={} values={},{},{},{},{},{},{} name=\"{}\" source={}",
			sum, g_specialMaxPoints, written,
			a_vals[0], a_vals[1], a_vals[2], a_vals[3], a_vals[4], a_vals[5], a_vals[6],
			a_name, source);
		if (auto* ui = RE::UI::GetSingleton(); ui && ui->IsMenuOpen(SpecialMenuName())) {
			if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
				queue->AddMessage(SpecialMenuName(), RE::UI_MESSAGE_TYPE::kHide);
			}
		}
	}

	class SpecialCodeObjFunction final : public RE::Scaleform::GFx::FunctionHandler
	{
	public:
		void Name(const char* a_name) { _name = a_name; }

		void Call(const Params& a_params) override
		{
			const auto callN = ++g_specialCodeCalls;
			if (callN <= 128) {
				REX::INFO("step=special_call n={} name={} args={}", callN, _name, a_params.argCount);
			}
			if (g_specialClosing.load()) {
				return;
			}
			if (_name == "initMenu") {
				ShellVitalsSnapshot snap;
				{
					std::scoped_lock lock(g_shellSnapLock);
					snap = g_shellSnap;
				}
				g_specialPlayerName = snap.playerName.empty() ? "Sole Survivor" : snap.playerName;
				int initSum = 0;
				for (std::size_t i = 0; i < 7; ++i) {
					g_specialValues[i] = std::clamp(snap.special[i], 1, 10);
					initSum += g_specialValues[i];
				}
				if (initSum < 7 || static_cast<std::uint32_t>(initSum) >= g_specialMaxPoints) {
					g_specialValues = { 1, 1, 1, 1, 1, 1, 1 };
					initSum = 7;
				}
				auto* const root = g_activeSpecialMenu ? RootOf(g_activeSpecialMenu) : nullptr;
				if (root && a_params.argCount >= 1 && (a_params.args[0].IsArray() || a_params.args[0].IsObject())) {
					g_specialEntryList = a_params.args[0];
					ClearAs3ArrayInPlace(g_specialEntryList);
					RE::Scaleform::GFx::Value pushRes;
					// entryList[0]: Name_ListEntry (MUST NOT define `value`, so entry.value === undefined in UpdateCounterAndButtons)
					RE::Scaleform::GFx::Value nameRow;
					root->CreateObject(&nameRow);
					if (nameRow.IsObject()) {
						nameRow.SetMember("text", RE::Scaleform::GFx::Value(g_specialPlayerName.c_str()));
						g_specialEntryList.Invoke("push", &pushRes, &nameRow, 1);
					}
					for (std::size_t i = 0; i < 7; ++i) {
						RE::Scaleform::GFx::Value spRow;
						root->CreateObject(&spRow);
						if (spRow.IsObject()) {
							spRow.SetMember("text", RE::Scaleform::GFx::Value(kSpecialTitleNames[i]));
							spRow.SetMember("value", RE::Scaleform::GFx::Value(static_cast<std::uint32_t>(g_specialValues[i])));
							spRow.SetMember("description", RE::Scaleform::GFx::Value(""));
							g_specialEntryList.Invoke("push", &pushRes, &spRow, 1);
						}
					}
				}
				if (a_params.ret) {
					*a_params.ret = RE::Scaleform::GFx::Value(g_specialMaxPoints);
				}
				REX::INFO("step=special_init max_points={} initial_sum={} name=\"{}\"",
					g_specialMaxPoints, initSum, g_specialPlayerName);
				return;
			}
			if (_name == "modValue") {
				std::int32_t entryIdx = -1;
				std::int32_t delta = 0;
				if (a_params.argCount >= 2 && ExtractShellIndex(a_params.args[0], entryIdx, 7)) {
					if (a_params.args[1].IsInt()) {
						delta = a_params.args[1].GetInt();
					} else if (a_params.args[1].IsNumber() && std::isfinite(a_params.args[1].GetNumber())) {
						delta = static_cast<std::int32_t>(std::lround(a_params.args[1].GetNumber()));
					} else if (a_params.args[1].IsUInt()) {
						delta = static_cast<std::int32_t>(a_params.args[1].GetUInt());
					}
				}
				if (entryIdx >= 1 && entryIdx <= 7 && delta != 0) {
					const auto attrIdx = static_cast<std::size_t>(entryIdx - 1);
					int curSum = 0;
					for (const int v : g_specialValues) {
						curSum += v;
					}
					const int pointsRemaining = static_cast<int>(g_specialMaxPoints) - curSum;
					if (delta > 0 && pointsRemaining <= 0) {
						REX::INFO("step=special_mod_refused attr={} delta={} points_remaining={} sum={}/{}",
							kSpecialTitleNames[attrIdx], delta, pointsRemaining, curSum, g_specialMaxPoints);
						return;
					}
					const int cappedDelta = (delta > 0) ? std::min(delta, pointsRemaining) : delta;
					const int nextVal = std::clamp(g_specialValues[attrIdx] + cappedDelta, 1, 10);
					g_specialValues[attrIdx] = nextVal;
					if (g_specialEntryList.IsArray() || g_specialEntryList.IsObject()) {
						RE::Scaleform::GFx::Value elem;
						const auto                idxKey = std::to_string(entryIdx);
						if (g_specialEntryList.GetMember(idxKey.c_str(), &elem) && elem.IsObject()) {
							elem.SetMember("value", RE::Scaleform::GFx::Value(static_cast<std::uint32_t>(nextVal)));
						}
					}
					int sum = 0;
					for (const int v : g_specialValues) {
						sum += v;
					}
					REX::INFO("step=special_mod attr={} delta={} value={} sum={}/{}",
						kSpecialTitleNames[attrIdx], cappedDelta, nextVal, sum, g_specialMaxPoints);
				}
				return;
			}
			if (_name == "startEditText") {
				// Return Boolean(true) on PC so SPECIALMenu.onItemPress falls through 0x12 (iffalse) to this.StartEditText()
				if (a_params.ret) {
					*a_params.ret = RE::Scaleform::GFx::Value(true);
				}
				REX::INFO("step=special_edit_start allow_inline=1");
				return;
			}
			if (_name == "endEditText") {
				if (a_params.argCount >= 1 && a_params.args[0].IsString()) {
					const std::string edited = std::string(a_params.args[0].GetString()).substr(0, 64);
					if (!edited.empty()) {
						g_specialPlayerName = edited;
					}
				}
				REX::INFO("step=special_edit_end name=\"{}\"", g_specialPlayerName);
				return;
			}
			if (_name == "confirmResetPoints") {
				auto* const               root = g_activeSpecialMenu ? RootOf(g_activeSpecialMenu) : nullptr;
				RE::Scaleform::GFx::Value top, menuMc, res;
				bool                      called = false;
				if (root && root->GetVariable(&top, "root") && top.IsObject() &&
					top.GetMember("Menu_mc", &menuMc) && menuMc.IsObject()) {
					called = InvokeMovieTracked(menuMc, "ResetPoints", &res, nullptr, 0, "SpecialMenu.ResetPoints");
				}
				REX::INFO("step=special_reset called={}", called ? 1 : 0);
				return;
			}
			if (_name == "tryCloseMenu") {
				int sum = 0;
				for (const int v : g_specialValues) {
					sum += v;
				}
				if (sum != static_cast<int>(g_specialMaxPoints)) {
					REX::INFO("step=special_close_refused sum={} max_points={}", sum, g_specialMaxPoints);
					return;
				}
				if (g_task) {
					const auto valsCopy = g_specialValues;
					const auto nameCopy = g_specialPlayerName;
					g_task->AddTask([valsCopy, nameCopy]() { CommitSpecialMenuMainThread(valsCopy, nameCopy); });
				}
				return;
			}
			if (_name == "StopPerkSound") {
				StopActivePerkSound();
				return;
			}
			if (g_codeObjSound && (_name == "playSound" || _name == "PlayPerkSound") && a_params.argCount > 0) {
				StartSound(callN, &a_params.args[0], _name == "PlayPerkSound");
			}
		}

	private:
		std::string _name = "BGSCodeObj";
	};
	std::array<SpecialCodeObjFunction, kSpecialCodeObjNames.size()> g_specialCodeObjFns;

	void ClearSpecialSessionState()
	{
		g_specialOpen = false;
		g_specialClosing = false;
		g_specialCancelHeld = false;
		g_specialCodeObjMovie = nullptr;
		g_activeSpecialMenu = nullptr;
		g_specialEntryList = RE::Scaleform::GFx::Value{};
		g_specialCodeCalls = 0;
		std::scoped_lock lock(g_specialEventLock);
		g_pendingSpecialEvents.clear();
	}

	bool InstallSpecialCodeObjAndCreate(const void* a_menu)
	{
		if (g_specialClosing.load()) {
			return false;
		}
		const void* const movie = MovieOf(a_menu);
		if (!movie) {
			return false;
		}
		if (g_specialCodeObjMovie.load() == movie) {
			return true;
		}
		g_activeSpecialMenu = a_menu;
		auto* const               root = RootOf(a_menu);
		RE::Scaleform::GFx::Value top, menuMc, holder;
		if (!root || !root->GetVariable(&top, "root") || !top.IsObject() ||
			!top.GetMember("Menu_mc", &menuMc) || !menuMc.IsObject()) {
			return false;
		}
		const char* holderSource = "create_object";
		RE::Scaleform::GFx::Value existing;
		if (menuMc.GetMember("BGSCodeObj", &existing) && existing.IsObject() &&
			existing.GetType() != RE::Scaleform::GFx::Value::ValueType::kClosure) {
			holder = existing;
			holderSource = "menu_mc";
		} else {
			root->CreateObject(&holder, "Object");
		}
		if (!holder.IsObject() || holder.GetType() == RE::Scaleform::GFx::Value::ValueType::kClosure) {
			return false;
		}
		std::size_t attached = 0;
		for (std::size_t i = 0; i < kSpecialCodeObjNames.size(); ++i) {
			g_specialCodeObjFns[i].Name(kSpecialCodeObjNames[i]);
			RE::Scaleform::GFx::Value fn;
			root->CreateFunction(&fn, &g_specialCodeObjFns[i]);
			if (!fn.IsUndefined() && holder.SetMember(kSpecialCodeObjNames[i], fn)) {
				++attached;
			}
		}
		top.SetMember("BGSCodeObj", holder);
		menuMc.SetMember("BGSCodeObj", holder);
		if (attached != kSpecialCodeObjNames.size()) {
			return false;
		}
		g_specialCodeObjMovie = movie;
		REX::INFO("step=special_code_obj type=object source={} members={}", holderSource, attached);
		RE::Scaleform::GFx::Value res;
		const bool created = InvokeMovieTracked(menuMc, "onCodeObjCreate", &res, nullptr, 0, "SpecialMenu.onCodeObjCreate");
		REX::INFO("step=special_show_create called={}", created ? 1 : 0);
		return created;
	}

	void SpecialHideTeardown(const void* a_menu)
	{
		g_specialClosing = true;
		g_specialEntryList = RE::Scaleform::GFx::Value{};
		const void* const movie = MovieOf(a_menu);
		if (!movie || g_specialCodeObjMovie.load() != movie) {
			g_activeSpecialMenu = nullptr;
			return;
		}
		auto* const               root = RootOf(a_menu);
		RE::Scaleform::GFx::Value top, menuMc, fn, res;
		bool                      called = false;
		if (root && root->GetVariable(&top, "root") && top.IsObject() &&
			top.GetMember("Menu_mc", &menuMc) && menuMc.IsObject() &&
			menuMc.GetMember("onCodeObjDestruction", &fn) &&
			fn.GetType() == RE::Scaleform::GFx::Value::ValueType::kClosure) {
			called = InvokeMovieTracked(menuMc, "onCodeObjDestruction", &res, nullptr, 0, "SpecialMenu.onCodeObjDestruction");
		}
		g_activeSpecialMenu = nullptr;
		REX::INFO("step=special_hide movie={} called={}", Hex(reinterpret_cast<std::uintptr_t>(movie)), called ? 1 : 0);
	}

	void SpecialProcessPendingEvents(const void* a_menu)
	{
		if (g_specialClosing.load()) {
			return;
		}
		if (g_specialCodeObjMovie.load() != MovieOf(a_menu)) {
			InstallSpecialCodeObjAndCreate(a_menu);
			return;
		}
		std::vector<PendingUserEvent> batch;
		{
			std::scoped_lock lock(g_specialEventLock);
			batch.swap(g_pendingSpecialEvents);
		}
		if (batch.empty()) {
			return;
		}
		auto* const               root = RootOf(a_menu);
		RE::Scaleform::GFx::Value top, menuMc;
		if (!root || !root->GetVariable(&top, "root") || !top.IsObject() ||
			!top.GetMember("Menu_mc", &menuMc) || !menuMc.IsObject()) {
			return;
		}
		for (const auto& ev : batch) {
			RE::Scaleform::GFx::Value args[2]{
				RE::Scaleform::GFx::Value(ev.name.c_str()),
				RE::Scaleform::GFx::Value(ev.isDown),
			};
			RE::Scaleform::GFx::Value res;
			InvokeMovieTracked(menuMc, "ProcessUserEvent", &res, args, 2, "SpecialMenu.ProcessUserEvent", false);
		}
	}

	void* SpecialMenuDestroy(void* a_self, std::uint32_t a_flags)
	{
		ClearSpecialSessionState();
		g_engineDtor(a_self, a_flags & ~1u);
		if (a_flags & 1) {
			std::free(a_self);
		}
		return a_self;
	}

	const char* SpecialMenuGetName(const void*)
	{
		if (g_loadingSpecialMovie.load() && !g_specialMovie.empty()) {
			return g_specialMovie.c_str();
		}
		return fo4sf::kOurSpecialMenuName;
	}

	bool SpecialMenuLoadMovie(void* a_self, bool, bool a_arg2)
	{
		if (MovieOf(a_self)) {
			return true;
		}
		g_loadingSpecialMovie.store(true);
		const bool loaded = g_engineLoadMovie(a_self, false, a_arg2);
		g_loadingSpecialMovie.store(false);
		REX::INFO("step=special_load_movie result={} movie={} movie_name={}",
			loaded ? 1 : 0, Hex(reinterpret_cast<std::uintptr_t>(MovieOf(a_self))), g_specialMovie);
		return loaded && MovieOf(a_self) != nullptr;
	}

	RE::UI_MESSAGE_RESULT SpecialMenuProcessMessage(void* a_self, RE::UIMessageData& a_message)
	{
		const auto type = a_message.type;
		if (type == RE::UI_MESSAGE_TYPE::kShow) {
			g_specialClosing = false;
			if (!MovieOf(a_self)) {
				SpecialMenuLoadMovie(a_self, false, false);
			}
		} else if (type == RE::UI_MESSAGE_TYPE::kHide) {
			SpecialHideTeardown(a_self);
		}
		const auto result = g_engineProcessMessage(a_self, a_message);
		if (type == RE::UI_MESSAGE_TYPE::kShow) {
			g_specialOpen = true;
			if (!InstallSpecialCodeObjAndCreate(a_self) && g_task) {
				g_task->AddTask([]() {
					if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
						queue->AddMessage(SpecialMenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
					}
				});
			}
		} else if (type == RE::UI_MESSAGE_TYPE::kUpdate) {
			SpecialProcessPendingEvents(a_self);
		} else if (type == RE::UI_MESSAGE_TYPE::kHide) {
			ClearSpecialSessionState();
		}
		return result;
	}

	bool SpecialShouldHandleEvent(void* a_input, const void* a_event)
	{
		if (!a_event || !g_specialOpen.load()) {
			return g_engineShouldHandle(a_input, a_event);
		}
		const auto* base = static_cast<const RE::InputEvent*>(a_event);
		if (base->eventType == RE::InputEvent::EventType::kButton &&
			(base->deviceType == RE::InputEvent::DeviceType::kKeyboard || base->deviceType == RE::InputEvent::DeviceType::kGamepad) &&
			base->status != RE::InputEvent::Status::kStop) {
			return true;
		}
		return g_engineShouldHandle(a_input, a_event);
	}

	void SpecialOnButtonEvent(void* a_input, const void* a_event)
	{
		if (!a_event || !g_specialOpen.load()) {
			g_engineOnButton(a_input, a_event);
			return;
		}
		// Always forward to Scaleform first so inline Name TextField editing, arrow keys, and Enter work natively
		g_engineOnButton(a_input, a_event);
		const auto* base = static_cast<const RE::InputEvent*>(a_event);
		if (base->eventType != RE::InputEvent::EventType::kButton || base->deviceType != RE::InputEvent::DeviceType::kKeyboard) {
			return;
		}
		const auto* button = static_cast<const RE::ButtonEvent*>(a_event);
		const auto  vk = static_cast<std::uint32_t>(button->idCode);
		const bool  press = button->value > 0.0f && button->heldDownSecs == 0.0f;
		const bool  release = button->value == 0.0f;
		if (!press && !release) {
			return;
		}
		std::string_view mapped;
		switch (vk) {
		case 0x52: mapped = "XButton"sv; break;   // R -> Reset Points
		case 0x54: mapped = "YButton"sv; break;   // T -> Confirm / Exit (when all points allocated)
		case 0x1B:
		case 0x09: mapped = "Cancel"sv; break;    // Esc / Tab -> Cancel edit or confirm exit
		default: break;
		}
		if (!mapped.empty()) {
			const_cast<RE::InputEvent*>(base)->status = RE::InputEvent::Status::kStop;
			QueueSpecialUserEvent(mapped, press);
		}
	}

	RE::Scaleform::Ptr<RE::IMenu>* CreateSpecialMenu(RE::Scaleform::Ptr<RE::IMenu>* a_out)
	{
		const auto n = ++g_specialCreated;
		void*      menu = std::calloc(1, kMenuBytes);
		if (!menu) {
			REX::ERROR("refuse step=create menu=special n={} reason=out_of_memory", n);
			std::construct_at(a_out);
			return a_out;
		}
		g_ctor(menu);
		const auto base = reinterpret_cast<std::uintptr_t>(menu);
		auto*      refs = reinterpret_cast<volatile std::uint32_t*>(base + 0x08);
		const auto ctorRefs = *refs;
		*reinterpret_cast<std::uintptr_t*>(base) = reinterpret_cast<std::uintptr_t>(g_specialVtbl.slots.data());
		*reinterpret_cast<std::uintptr_t*>(base + 0x10) = reinterpret_cast<std::uintptr_t>(g_specialInputVtbl.slots.data());
		auto* imenu = static_cast<RE::IMenu*>(menu);
		imenu->menuName = SpecialMenuName();
		imenu->flags |= (0x19u | kPauseFlag);
		imenu->flagsUpdated = true;
		if (g_keepAlive && ctorRefs == 1) {
			REX::W32::InterlockedIncrement(refs);
		}
		REX::INFO("step=special_create n={} menu={} flags={}", n, Hex(base), Hex(imenu->flags));
		std::memcpy(static_cast<void*>(a_out), &menu, sizeof(menu));
		return a_out;
	}

	void OpenSpecialMenuMainThread(const char* a_by)
	{
		if (!g_specialMenu) {
			return;
		}
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue || !ui->IsMenuRegistered(SpecialMenuName()) || ui->IsMenuOpen(SpecialMenuName())) {
			return;
		}
		if (ui->IsMenuOpen(MenuName())) {
			queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kHide);
		}
		CollectShellVitalsMainThread(s_savedPage.load());
		queue->AddMessage(SpecialMenuName(), RE::UI_MESSAGE_TYPE::kShow);
		REX::INFO("step=special_open by={} movie={} max_points={}", a_by ? a_by : "trigger", g_specialMovie, g_specialMaxPoints);
	}

	const RE::BSFixedString& StartCardMenuName()
	{
		static const RE::BSFixedString s{ fo4sf::kOurStartCardMenuName };
		return s;
	}

	void* StartCardMenuDestroy(void* a_self, std::uint32_t a_flags)
	{
		g_startCardOpen.store(false);
		g_engineDtor(a_self, a_flags & ~1u);
		if (a_flags & 1) {
			std::free(a_self);
		}
		return a_self;
	}

	const char* StartCardMenuGetName(const void*)
	{
		if (g_loadingStartCardMovie.load()) {
			return "FO4SF_StartCard";
		}
		return fo4sf::kOurStartCardMenuName;
	}

	bool StartCardMenuLoadMovie(void* a_self, bool, bool a_arg2)
	{
		if (MovieOf(a_self)) {
			return true;
		}
		g_loadingStartCardMovie.store(true);
		const bool loaded = g_engineLoadMovie(a_self, false, a_arg2);
		g_loadingStartCardMovie.store(false);
		const bool ok = loaded && MovieOf(a_self) != nullptr;
		if (!ok && !g_startCardMissing.exchange(true)) {
			REX::INFO("step=start_card_skip reason=missing movie=FO4SF_StartCard");
		} else if (ok) {
			REX::INFO("step=start_card_load_movie result=1 movie=FO4SF_StartCard");
		}
		return ok;
	}

	RE::UI_MESSAGE_RESULT StartCardMenuProcessMessage(void* a_self, RE::UIMessageData& a_message)
	{
		const auto type = a_message.type;
		if (type == RE::UI_MESSAGE_TYPE::kShow && !MovieOf(a_self)) {
			if (!StartCardMenuLoadMovie(a_self, false, false)) {
				g_startCardOpen.store(false);
				return RE::UI_MESSAGE_RESULT::kHandled;
			}
		}
		const auto result = g_engineProcessMessage(a_self, a_message);
		if (type == RE::UI_MESSAGE_TYPE::kShow) {
			g_startCardOpen.store(true);
		} else if (type == RE::UI_MESSAGE_TYPE::kHide) {
			g_startCardOpen.store(false);
		}
		return result;
	}

	bool StartCardShouldHandleEvent(void*, const void*)
	{
		// Non-modal background card at depth=0: never consume keyboard, mouse, or controller input.
		return false;
	}

	RE::Scaleform::Ptr<RE::IMenu>* CreateStartCardMenu(RE::Scaleform::Ptr<RE::IMenu>* a_out)
	{
		const auto n = ++g_startCardCreated;
		void*      menu = std::calloc(1, kMenuBytes);
		if (!menu) {
			REX::ERROR("refuse step=create menu=start_card n={} reason=out_of_memory", n);
			std::construct_at(a_out);
			return a_out;
		}
		g_ctor(menu);
		const auto base = reinterpret_cast<std::uintptr_t>(menu);
		auto*      refs = reinterpret_cast<volatile std::uint32_t*>(base + 0x08);
		const auto ctorRefs = *refs;
		*reinterpret_cast<std::uintptr_t*>(base) = reinterpret_cast<std::uintptr_t>(g_startCardVtbl.slots.data());
		*reinterpret_cast<std::uintptr_t*>(base + 0x10) = reinterpret_cast<std::uintptr_t>(g_startCardInputVtbl.slots.data());
		auto* imenu = static_cast<RE::IMenu*>(menu);
		imenu->menuName = StartCardMenuName();
		// Strictly bottom UI layer (depth=0) with zero modal/pause/cursor flags so MessageBoxMenu & Console sit above it.
		*reinterpret_cast<std::uint8_t*>(base + 0x110) = 0;
		if (g_keepAlive && ctorRefs == 1) {
			REX::W32::InterlockedIncrement(refs);
		}
		REX::INFO("step=start_card_create n={} menu={} flags={} depth=0", n, Hex(base), Hex(imenu->flags));
		std::memcpy(static_cast<void*>(a_out), &menu, sizeof(menu));
		return a_out;
	}

	void* BlockedMapMenuDestroy(void* a_self, std::uint32_t a_flags)
	{
		g_engineDtor(a_self, a_flags & ~1u);
		if (a_flags & 1) {
			std::free(a_self);
		}
		return a_self;
	}

	const char* BlockedMapMenuGetName(const void* a_self)
	{
		if (a_self) {
			const auto* imenu = static_cast<const RE::IMenu*>(a_self);
			if (const char* nm = imenu->menuName.c_str(); nm && *nm) {
				return nm;
			}
		}
		return "GalaxyStarMapMenu";
	}

	bool BlockedMapMenuLoadMovie(void*, bool, bool)
	{
		// Stage-1 style minimal menu: never loads Starfield's star-map movie and closes itself on kShow.
		return true;
	}

	RE::UI_MESSAGE_RESULT BlockedMapMenuProcessMessage(void* a_self, RE::UIMessageData& a_message)
	{
		const auto type = a_message.type;
		const auto result = g_engineProcessMessage(a_self, a_message);
		if (type == RE::UI_MESSAGE_TYPE::kShow && a_self) {
			auto* imenu = static_cast<RE::IMenu*>(a_self);
			if (auto* queue = RE::UIMessageQueue::GetSingleton(); queue && !imenu->menuName.empty()) {
				queue->AddMessage(imenu->menuName, RE::UI_MESSAGE_TYPE::kHide);
			}
		}
		return result;
	}

	bool CreateBlockedMapMenuInstance(const char* a_menuName, RE::Scaleform::Ptr<RE::IMenu>* a_out)
	{
		if (!a_out || !g_ctor || !g_blockedMapVtbl.slots[0]) {
			return false;
		}
		constexpr std::size_t kBlockedMenuBytes = (kMenuBytes > 0x1000) ? kMenuBytes : 0x1000;
		const auto            n = ++g_blockedMapCreated;
		void*                 menu = std::calloc(1, kBlockedMenuBytes);
		if (!menu) {
			REX::ERROR("refuse step=create menu=blocked_map n={} reason=out_of_memory", n);
			return false;
		}
		g_ctor(menu);
		const auto base = reinterpret_cast<std::uintptr_t>(menu);
		*reinterpret_cast<std::uintptr_t*>(base) = reinterpret_cast<std::uintptr_t>(g_blockedMapVtbl.slots.data());
		*reinterpret_cast<std::uintptr_t*>(base + 0x10) = reinterpret_cast<std::uintptr_t>(g_blockedMapInputVtbl.slots.data());
		auto* imenu = static_cast<RE::IMenu*>(menu);
		imenu->menuName = RE::BSFixedString(a_menuName && *a_menuName ? a_menuName : "GalaxyStarMapMenu");
		imenu->flags = 0;
		imenu->flagsUpdated = true;
		*reinterpret_cast<std::uint8_t*>(base + 0x110) = 0;
		std::memcpy(static_cast<void*>(a_out), &menu, sizeof(menu));
		return true;
	}

	const RE::BSFixedString& SetupMenuName()
	{
		static const RE::BSFixedString s{ fo4sf::kOurSetupMenuName };
		return s;
	}

	void WriteStoreGlobalFloat(std::uintptr_t a_form, float a_value)
	{
		if (!a_form) {
			return;
		}
		const std::size_t valAt = g_forms.globalValueAt ? g_forms.globalValueAt : kGlobalValueAt;
		*reinterpret_cast<float*>(a_form + valAt) = a_value;
	}

	void CommitSetupMenuMainThread()
	{
		std::optional<fo4sf::setup::SetupCommitPayload> payload;
		std::string                                     lockedId;
		{
			std::scoped_lock lock(g_setupLock);
			payload = g_setupModel.Confirm();
			if (!payload.has_value()) {
				lockedId = g_setupModel.CurrentPlaceRow().id;
			}
		}
		if (!payload.has_value()) {
			REX::INFO("step=setup_confirm_refused id={} reason=unavailable", lockedId);
			if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
				queue->AddMessage(SetupMenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
			}
			return;
		}

		FindGlobalValue();
		std::string    detail;
		std::uintptr_t form = 0;

		if (const auto fid = KitFileForm("FO4SFCoreValues.esm", kCoreGameModeId, "TESGlobal@@", detail)) {
			form = 0;
			AcceptById(fid, "FO4SF_GameMode", "TESGlobal@@", kGlobalEditorIdAt, form);
			WriteStoreGlobalFloat(form, static_cast<float>(payload->modeVal));
		}
		if (const auto fid = KitFileForm("FO4SFCoreValues.esm", kCoreStoryLineId, "TESGlobal@@", detail)) {
			form = 0;
			AcceptById(fid, "FO4SF_StoryLine", "TESGlobal@@", kGlobalEditorIdAt, form);
			WriteStoreGlobalFloat(form, static_cast<float>(payload->storyChoiceIdx));
		}
		if (const auto fid = KitFileForm("FO4SFCoreValues.esm", kCoreSurvivalStartId, "TESGlobal@@", detail)) {
			form = 0;
			AcceptById(fid, "FO4SF_SurvivalStart", "TESGlobal@@", kGlobalEditorIdAt, form);
			WriteStoreGlobalFloat(form, static_cast<float>(payload->survival));
		}
		if (const auto fid = KitFileForm("FO4SFCoreValues.esm", kCoreSurvivalLockedId, "TESGlobal@@", detail)) {
			form = 0;
			AcceptById(fid, "FO4SF_SurvivalLocked", "TESGlobal@@", kGlobalEditorIdAt, form);
			WriteStoreGlobalFloat(form, static_cast<float>(payload->survival));
		}
		if (const auto fid = KitFileForm("FO4SFCoreValues.esm", kCoreStartDifficultyId, "TESGlobal@@", detail)) {
			form = 0;
			AcceptById(fid, "FO4SF_StartDifficulty", "TESGlobal@@", kGlobalEditorIdAt, form);
			WriteStoreGlobalFloat(form, static_cast<float>(payload->difficulty));
		}
		if (const auto fid = KitFileForm("FO4SFCoreValues.esm", kCoreWarfareFactionId, "TESGlobal@@", detail)) {
			form = 0;
			AcceptById(fid, "FO4SF_WarfareFaction", "TESGlobal@@", kGlobalEditorIdAt, form);
			WriteStoreGlobalFloat(form, static_cast<float>(payload->warfareFactionSlot));
		}
		if (const auto fid = KitFileForm("FO4SFCoreValues.esm", kCoreWarfareStartIndexId, "TESGlobal@@", detail)) {
			form = 0;
			AcceptById(fid, "FO4SF_WarfareStartIndex", "TESGlobal@@", kGlobalEditorIdAt, form);
			WriteStoreGlobalFloat(form, static_cast<float>(payload->warfareStartIdx));
		}
		if (const auto fid = KitFileForm("FO4SFCoreValues.esm", kCoreStartPlaceRowId, "TESGlobal@@", detail)) {
			form = 0;
			AcceptById(fid, "FO4SF_StartPlaceRow", "TESGlobal@@", kGlobalEditorIdAt, form);
			WriteStoreGlobalFloat(form, static_cast<float>(payload->startPlaceRow));
		}
		if (const auto fid = KitFileForm("FO4SFCoreValues.esm", kCoreStartCardOpenId, "TESGlobal@@", detail)) {
			form = 0;
			AcceptById(fid, "FO4SF_StartCardOpen", "TESGlobal@@", kGlobalEditorIdAt, form);
			WriteStoreGlobalFloat(form, 0.0f);
		}
		// Commit FO4SF_StartChoiceDone last so Papyrus observes all 8 choice globals settled.
		if (const auto fid = KitFileForm("FO4SFCoreValues.esm", kCoreStartChoiceDoneId, "TESGlobal@@", detail)) {
			form = 0;
			AcceptById(fid, "FO4SF_StartChoiceDone", "TESGlobal@@", kGlobalEditorIdAt, form);
			WriteStoreGlobalFloat(form, 1.0f);
		}

		if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
			queue->AddMessage(SetupMenuName(), RE::UI_MESSAGE_TYPE::kHide);
		}
		REX::INFO("step=setup_confirm mode={} story={} faction={} place={} survival={} difficulty={} row={}",
			payload->modeTag, payload->storyId, payload->warfareFactionSlot, payload->placeId,
			payload->survival, payload->difficulty, payload->startPlaceRow);
	}

	enum class SetupClickKind : std::uint8_t
	{
		kSelectRow,
		kPrevValue,
		kNextValue,
		kConfirm,
	};

	class SetupButtonHandler final : public RE::Scaleform::GFx::FunctionHandler
	{
	public:
		void Configure(SetupClickKind a_kind, int a_row)
		{
			_kind = a_kind;
			_row = a_row;
		}

		void Call(const Params&) override
		{
			if (_kind == SetupClickKind::kConfirm) {
				if (g_task) {
					g_task->AddTask([]() { CommitSetupMenuMainThread(); });
				}
				return;
			}
			{
				std::scoped_lock lock(g_setupLock);
				g_setupModel.SelectRow(_row);
				if (_kind == SetupClickKind::kPrevValue) {
					g_setupModel.AdjustRow(_row, -1);
				} else if (_kind == SetupClickKind::kNextValue) {
					g_setupModel.AdjustRow(_row, 1);
				}
			}
			if (g_task) {
				g_task->AddTask([]() {
					if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
						queue->AddMessage(SetupMenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
					}
				});
			}
		}

	private:
		SetupClickKind _kind = SetupClickKind::kSelectRow;
		int            _row = 0;
	};
	std::array<SetupButtonHandler, 16> g_setupButtonHandlers;

	void SetupListen(const void* a_menu)
	{
		auto* const root = RootOf(a_menu);
		const auto  movie = MovieOf(a_menu);
		if (!root || !movie || g_setupListenedMovie.load() == movie) {
			return;
		}
		g_setupListenedMovie.store(movie);
		RE::Scaleform::GFx::Value top;
		const bool                gotRoot = root->GetVariable(&top, "root") && top.IsObject();
		if (!gotRoot) {
			return;
		}
		std::size_t hIdx = 0;
		const auto  attach = [&](const std::string& a_name, SetupClickKind a_kind, int a_row) {
			if (hIdx >= g_setupButtonHandlers.size()) {
				return;
			}
			auto& handler = g_setupButtonHandlers[hIdx++];
			handler.Configure(a_kind, a_row);
			RE::Scaleform::GFx::Value btn, fn;
			if (ChildOf(top, a_name.c_str(), btn)) {
				root->CreateFunction(&fn, &handler);
				if (!fn.IsUndefined()) {
					std::array<RE::Scaleform::GFx::Value, 2> args{ "click", fn };
					btn.Invoke("addEventListener", nullptr, args.data(), args.size());
				}
			}
		};
		for (int i = 0; i < static_cast<int>(fo4sf::setup::kSetupRows); ++i) {
			attach(std::format("fo4sfSetupHit{}", i), SetupClickKind::kSelectRow, i);
			attach(std::format("fo4sfSetupPrev{}", i), SetupClickKind::kPrevValue, i);
			attach(std::format("fo4sfSetupNext{}", i), SetupClickKind::kNextValue, i);
		}
		attach("fo4sfSetupConfirm", SetupClickKind::kConfirm, 0);
	}

	void SetupWrite(const void* a_menu)
	{
		auto* const root = RootOf(a_menu);
		if (!root) {
			return;
		}
		RE::Scaleform::GFx::Value top;
		if (!root->GetVariable(&top, "root") || !top.IsObject()) {
			return;
		}
		std::array<std::string, fo4sf::setup::kSetupRows> rows{};
		std::string                                       status;
		{
			std::scoped_lock lock(g_setupLock);
			g_setupModel.RenderLines(rows, status);
		}
		for (std::size_t i = 0; i < rows.size(); ++i) {
			RE::Scaleform::GFx::Value field;
			const auto                fname = std::format("fo4sfSetupRow{}", i);
			if (ChildOf(top, fname.c_str(), field)) {
				field.SetMember("text", RE::Scaleform::GFx::Value(rows[i].c_str()));
			}
		}
		RE::Scaleform::GFx::Value statusField;
		if (ChildOf(top, "fo4sfSetupStatus", statusField)) {
			statusField.SetMember("text", RE::Scaleform::GFx::Value(status.c_str()));
		}
	}

	const RE::BSFixedString& LiftMenuName()
	{
		static const RE::BSFixedString s{ fo4sf::kOurLiftMenuName };
		return s;
	}

	std::array<int, fo4sf::lift::kSpecialCount> ReadInitialLiftSpecialMainThread(bool& a_outConfirmed)
	{
		FindGlobalValue();
		std::array<int, fo4sf::lift::kSpecialCount> vals{ 5, 5, 5, 5, 5, 5, 5 };
		const std::size_t valAt = g_forms.globalValueAt ? g_forms.globalValueAt : kGlobalValueAt;
		for (std::size_t i = 0; i < fo4sf::lift::kSpecialCount; ++i) {
			std::string         detail;
			const std::uint32_t localId = kCoreSpecialMenuPendingFirstId + static_cast<std::uint32_t>(i);
			std::uintptr_t      form = 0;
			if (const auto fid = KitFileForm("FO4SFCoreValues.esm", localId, "TESGlobal@@", detail)) {
				AcceptById(fid, kSpecialPendingEditorIds[i], "TESGlobal@@", kGlobalEditorIdAt, form);
			}
			float v = 5.0f;
			if (form && Peek(form + valAt, v) && std::isfinite(v) && v >= 1.0f && v <= 10.0f) {
				vals[i] = static_cast<int>(std::lround(v));
			}
		}
		a_outConfirmed = false;
		{
			std::string    reqDetail;
			std::uintptr_t reqForm = 0;
			if (const auto reqFid = KitFileForm("FO4SFCoreValues.esm", kCoreSpecialMenuCommitReqId, "TESGlobal@@", reqDetail)) {
				AcceptById(reqFid, "FO4SF_SpecialMenuCommitRequested", "TESGlobal@@", kGlobalEditorIdAt, reqForm);
			}
			float reqVal = 0.0f;
			if (reqForm && Peek(reqForm + valAt, reqVal) && std::isfinite(reqVal)) {
				a_outConfirmed = reqVal >= 0.5f;
			}
		}
		return vals;
	}

	void CommitLiftPayloadMainThread(const fo4sf::lift::LiftCommitPayload& a_payload)
	{
		FindGlobalValue();
		const std::size_t valAt = g_forms.globalValueAt ? g_forms.globalValueAt : kGlobalValueAt;
		if (a_payload.specialConfirmed) {
			std::array<std::uintptr_t, fo4sf::lift::kSpecialCount> pendingGlobs{};
			std::size_t                                            fromCore = 0;
			for (std::size_t i = 0; i < fo4sf::lift::kSpecialCount; ++i) {
				std::string         detail;
				const std::uint32_t localId = kCoreSpecialMenuPendingFirstId + static_cast<std::uint32_t>(i);
				if (const auto fid = KitFileForm("FO4SFCoreValues.esm", localId, "TESGlobal@@", detail)) {
					AcceptById(fid, kSpecialPendingEditorIds[i], "TESGlobal@@", kGlobalEditorIdAt, pendingGlobs[i]);
					if (pendingGlobs[i]) {
						++fromCore;
					}
				}
			}
			std::string    reqDetail;
			std::uintptr_t reqGlob = 0;
			if (const auto reqFid = KitFileForm("FO4SFCoreValues.esm", kCoreSpecialMenuCommitReqId, "TESGlobal@@", reqDetail)) {
				AcceptById(reqFid, "FO4SF_SpecialMenuCommitRequested", "TESGlobal@@", kGlobalEditorIdAt, reqGlob);
			}
			if (fromCore == fo4sf::lift::kSpecialCount && reqGlob) {
				std::size_t written = 0;
				for (std::size_t i = 0; i < fo4sf::lift::kSpecialCount; ++i) {
					const float sv = static_cast<float>(std::clamp(a_payload.special[i], 1, 10));
					if (WriteCoreGlobalFloatVerified(pendingGlobs[i], valAt, sv)) {
						++written;
					}
				}
				if (written == fo4sf::lift::kSpecialCount) {
					WriteCoreGlobalFloatVerified(reqGlob, valAt, 1.0f);
				}
			}
		}
		float code = 7.0f;
		if (a_payload.action == fo4sf::lift::CommitAction::kRide) {
			code = 6.0f;
		} else if (a_payload.action == fo4sf::lift::CommitAction::kChangeAppearance) {
			code = 8.0f;
		}
		std::string    detail;
		std::uintptr_t openForm = 0;
		if (const auto fid = KitFileForm("FO4SFCoreValues.esm", kCoreStartCardOpenId, "TESGlobal@@", detail)) {
			AcceptById(fid, "FO4SF_StartCardOpen", "TESGlobal@@", kGlobalEditorIdAt, openForm);
			WriteStoreGlobalFloat(openForm, code);
		}
		if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
			queue->AddMessage(LiftMenuName(), RE::UI_MESSAGE_TYPE::kHide);
		}
		REX::INFO("step=lift_confirm action={} confirmed={} values={},{},{},{},{},{},{}",
			static_cast<int>(a_payload.action), a_payload.specialConfirmed ? 1 : 0,
			a_payload.special[0], a_payload.special[1], a_payload.special[2], a_payload.special[3],
			a_payload.special[4], a_payload.special[5], a_payload.special[6]);
	}

	void HandleLiftActivateOrConfirmMainThread(bool a_fromConfirmButton)
	{
		fo4sf::lift::LiftCommitPayload payload;
		bool                           committed = false;
		{
			std::scoped_lock lock(g_liftLock);
			committed = g_liftModel.ActivateOrConfirm(a_fromConfirmButton, payload);
		}
		if (committed) {
			CommitLiftPayloadMainThread(payload);
		} else if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
			queue->AddMessage(LiftMenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
		}
	}

	void HandleLiftBackOrStayMainThread()
	{
		fo4sf::lift::LiftCommitPayload payload;
		bool                           committed = false;
		{
			std::scoped_lock lock(g_liftLock);
			committed = g_liftModel.BackOrStay(payload);
		}
		if (committed) {
			CommitLiftPayloadMainThread(payload);
		} else if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
			queue->AddMessage(LiftMenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
		}
	}

	class LiftButtonHandler final : public RE::Scaleform::GFx::FunctionHandler
	{
	public:
		void Configure(SetupClickKind a_kind, int a_row)
		{
			_kind = a_kind;
			_row = a_row;
		}

		void Call(const Params&) override
		{
			if (_kind == SetupClickKind::kConfirm) {
				if (g_task) {
					g_task->AddTask([]() { HandleLiftActivateOrConfirmMainThread(true); });
				}
				return;
			}
			if (_kind == SetupClickKind::kSelectRow) {
				bool activateOptions = false;
				{
					std::scoped_lock lock(g_liftLock);
					g_liftModel.SelectRow(_row);
					activateOptions = (g_liftModel.CurrentPage() == fo4sf::lift::Page::kOptions);
				}
				if (g_task) {
					if (activateOptions) {
						g_task->AddTask([]() { HandleLiftActivateOrConfirmMainThread(false); });
					} else {
						g_task->AddTask([]() {
							if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
								queue->AddMessage(LiftMenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
							}
						});
					}
				}
				return;
			}
			{
				std::scoped_lock lock(g_liftLock);
				g_liftModel.AdjustCurrentOrRow(_row, _kind == SetupClickKind::kPrevValue ? -1 : 1);
			}
			if (g_task) {
				g_task->AddTask([]() {
					if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
						queue->AddMessage(LiftMenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
					}
				});
			}
		}

	private:
		SetupClickKind _kind = SetupClickKind::kSelectRow;
		int            _row = 0;
	};
	std::array<LiftButtonHandler, fo4sf::lift::kLiftRows * 3 + 1> g_liftButtonHandlers;

	void LiftListen(const void* a_menu)
	{
		auto* const root = RootOf(a_menu);
		const auto  movie = MovieOf(a_menu);
		if (!root || !movie || g_liftListenedMovie.load() == movie) {
			return;
		}
		g_liftListenedMovie.store(movie);
		RE::Scaleform::GFx::Value top;
		if (!root->GetVariable(&top, "root") || !top.IsObject()) {
			return;
		}
		std::size_t hIdx = 0;
		const auto  attach = [&](const std::string& a_name, SetupClickKind a_kind, int a_row) {
			if (hIdx >= g_liftButtonHandlers.size()) {
				return;
			}
			auto& handler = g_liftButtonHandlers[hIdx++];
			handler.Configure(a_kind, a_row);
			RE::Scaleform::GFx::Value btn, fn;
			if (ChildOf(top, a_name.c_str(), btn)) {
				root->CreateFunction(&fn, &handler);
				if (!fn.IsUndefined()) {
					std::array<RE::Scaleform::GFx::Value, 2> args{ "click", fn };
					btn.Invoke("addEventListener", nullptr, args.data(), args.size());
				}
			}
		};
		for (int i = 0; i < static_cast<int>(fo4sf::lift::kLiftRows); ++i) {
			attach(std::format("fo4sfLiftHit{}", i), SetupClickKind::kSelectRow, i);
			attach(std::format("fo4sfLiftPrev{}", i), SetupClickKind::kPrevValue, i);
			attach(std::format("fo4sfLiftNext{}", i), SetupClickKind::kNextValue, i);
		}
		attach("fo4sfLiftConfirm", SetupClickKind::kConfirm, 0);
	}

	void LiftWrite(const void* a_menu)
	{
		auto* const root = RootOf(a_menu);
		if (!root) {
			return;
		}
		RE::Scaleform::GFx::Value top;
		if (!root->GetVariable(&top, "root") || !top.IsObject()) {
			return;
		}
		std::array<std::string, fo4sf::lift::kLiftRows> rows{};
		std::string                                     status;
		std::string                                     hint;
		{
			std::scoped_lock lock(g_liftLock);
			g_liftModel.RenderLines(rows, status, hint);
		}
		for (std::size_t i = 0; i < rows.size(); ++i) {
			RE::Scaleform::GFx::Value field;
			const auto                fname = std::format("fo4sfLiftRow{}", i);
			if (ChildOf(top, fname.c_str(), field)) {
				field.SetMember("text", RE::Scaleform::GFx::Value(rows[i].c_str()));
			}
		}
		RE::Scaleform::GFx::Value statusField;
		if (ChildOf(top, "fo4sfLiftStatus", statusField)) {
			statusField.SetMember("text", RE::Scaleform::GFx::Value(status.c_str()));
		}
		RE::Scaleform::GFx::Value hintField;
		if (ChildOf(top, "fo4sfLiftHint", hintField)) {
			hintField.SetMember("text", RE::Scaleform::GFx::Value(hint.c_str()));
		}
	}

	void* LiftMenuDestroy(void* a_self, std::uint32_t a_flags)
	{
		g_liftOpen.store(false);
		g_liftListenedMovie.store(nullptr);
		g_engineDtor(a_self, a_flags & ~1u);
		if (a_flags & 1) {
			std::free(a_self);
		}
		return a_self;
	}

	const char* LiftMenuGetName(const void*)
	{
		if (g_loadingLiftMovie.load()) {
			return "FO4SF_LiftScreen";
		}
		return fo4sf::kOurLiftMenuName;
	}

	bool LiftMenuLoadMovie(void* a_self, bool, bool a_arg2)
	{
		if (MovieOf(a_self)) {
			return true;
		}
		g_loadingLiftMovie.store(true);
		const bool loaded = g_engineLoadMovie(a_self, false, a_arg2);
		g_loadingLiftMovie.store(false);
		const bool ok = loaded && MovieOf(a_self) != nullptr;
		if (!ok && !g_liftMissing.exchange(true)) {
			REX::INFO("step=lift_skip reason=missing movie=FO4SF_LiftScreen");
		} else if (ok) {
			REX::INFO("step=lift_load_movie result=1 movie=FO4SF_LiftScreen");
		}
		return ok;
	}

	RE::UI_MESSAGE_RESULT LiftMenuProcessMessage(void* a_self, RE::UIMessageData& a_message)
	{
		const auto type = a_message.type;
		if (type == RE::UI_MESSAGE_TYPE::kShow && !MovieOf(a_self)) {
			if (!LiftMenuLoadMovie(a_self, false, false)) {
				g_liftOpen.store(false);
				return RE::UI_MESSAGE_RESULT::kHandled;
			}
		}
		const auto result = g_engineProcessMessage(a_self, a_message);
		if (type == RE::UI_MESSAGE_TYPE::kShow) {
			g_liftOpen.store(true);
			LiftListen(a_self);
			LiftWrite(a_self);
		} else if (type == RE::UI_MESSAGE_TYPE::kUpdate) {
			LiftListen(a_self);
			LiftWrite(a_self);
		} else if (type == RE::UI_MESSAGE_TYPE::kHide) {
			g_liftOpen.store(false);
			g_liftListenedMovie.store(nullptr);
		}
		return result;
	}

	bool LiftShouldHandleEvent(void* a_input, const void* a_event)
	{
		if (!a_event || !g_liftOpen.load()) {
			return g_engineShouldHandle ? g_engineShouldHandle(a_input, a_event) : false;
		}
		const auto* base = static_cast<const RE::InputEvent*>(a_event);
		if (base->eventType == RE::InputEvent::EventType::kButton &&
		    (base->deviceType == RE::InputEvent::DeviceType::kKeyboard ||
		     base->deviceType == RE::InputEvent::DeviceType::kGamepad) &&
		    base->status != RE::InputEvent::Status::kStop) {
			return true;
		}
		return g_engineShouldHandle ? g_engineShouldHandle(a_input, a_event) : false;
	}

	void LiftOnButtonEvent(void* a_input, const void* a_event)
	{
		if (g_engineOnButton) {
			g_engineOnButton(a_input, a_event);
		}
		if (!a_event || !g_liftOpen.load()) {
			return;
		}
		if (OpenBlockingOverlayMenu(RE::UI::GetSingleton(), true) != nullptr) {
			return;
		}
		const auto* base = static_cast<const RE::InputEvent*>(a_event);
		if (base->eventType != RE::InputEvent::EventType::kButton ||
		    base->deviceType != RE::InputEvent::DeviceType::kKeyboard) {
			return;
		}
		const auto* button = static_cast<const RE::ButtonEvent*>(a_event);
		if (!(button->value > 0.0f && button->heldDownSecs == 0.0f)) {
			return;
		}
		const auto vk = static_cast<std::uint32_t>(button->idCode);
		bool       handled = false;
		bool       wantActivate = false;
		bool       wantBackOrStay = false;
		{
			std::scoped_lock lock(g_liftLock);
			switch (vk) {
			case 0x26:   // VK_UP
			case 0x57:   // W
				g_liftModel.MoveCursor(-1);
				handled = true;
				break;
			case 0x28:   // VK_DOWN
			case 0x53:   // S
				g_liftModel.MoveCursor(1);
				handled = true;
				break;
			case 0x25:   // VK_LEFT
			case 0x41:   // A
				g_liftModel.AdjustCurrentOrRow(g_liftModel.Cursor(), -1);
				handled = true;
				break;
			case 0x27:   // VK_RIGHT
			case 0x44:   // D
				g_liftModel.AdjustCurrentOrRow(g_liftModel.Cursor(), 1);
				handled = true;
				break;
			case 0x0D:   // VK_RETURN
			case 0x45:   // E
				handled = true;
				wantActivate = true;
				break;
			case 0x1B:   // VK_ESCAPE
				handled = true;
				wantBackOrStay = true;
				break;
			default:
				break;
			}
		}
		if (!handled) {
			return;
		}
		const_cast<RE::InputEvent*>(base)->status = RE::InputEvent::Status::kStop;
		if (g_task) {
			if (wantActivate) {
				g_task->AddTask([]() { HandleLiftActivateOrConfirmMainThread(false); });
			} else if (wantBackOrStay) {
				g_task->AddTask([]() { HandleLiftBackOrStayMainThread(); });
			} else {
				g_task->AddTask([]() {
					if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
						queue->AddMessage(LiftMenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
					}
				});
			}
		}
	}

	RE::Scaleform::Ptr<RE::IMenu>* CreateLiftMenu(RE::Scaleform::Ptr<RE::IMenu>* a_out)
	{
		const auto n = ++g_liftCreated;
		void*      menu = std::calloc(1, kMenuBytes);
		if (!menu) {
			REX::ERROR("refuse step=create menu=lift n={} reason=out_of_memory", n);
			std::construct_at(a_out);
			return a_out;
		}
		g_ctor(menu);
		const auto base = reinterpret_cast<std::uintptr_t>(menu);
		auto*      refs = reinterpret_cast<volatile std::uint32_t*>(base + 0x08);
		const auto ctorRefs = *refs;
		*reinterpret_cast<std::uintptr_t*>(base) = reinterpret_cast<std::uintptr_t>(g_liftVtbl.slots.data());
		*reinterpret_cast<std::uintptr_t*>(base + 0x10) = reinterpret_cast<std::uintptr_t>(g_liftInputVtbl.slots.data());
		auto* imenu = static_cast<RE::IMenu*>(menu);
		imenu->menuName = LiftMenuName();
		imenu->flags |= (0x19u | kPauseFlag);
		imenu->flagsUpdated = true;
		if (g_keepAlive && ctorRefs == 1) {
			REX::W32::InterlockedIncrement(refs);
		}
		REX::INFO("step=lift_create n={} menu={} flags={}", n, Hex(base), Hex(imenu->flags));
		std::memcpy(static_cast<void*>(a_out), &menu, sizeof(menu));
		return a_out;
	}

	void* SetupMenuDestroy(void* a_self, std::uint32_t a_flags)
	{
		g_setupOpen.store(false);
		g_setupListenedMovie.store(nullptr);
		g_engineDtor(a_self, a_flags & ~1u);
		if (a_flags & 1) {
			std::free(a_self);
		}
		return a_self;
	}

	const char* SetupMenuGetName(const void*)
	{
		if (g_loadingSetupMovie.load()) {
			return "FO4SF_SetupScreen";
		}
		return fo4sf::kOurSetupMenuName;
	}

	bool SetupMenuLoadMovie(void* a_self, bool, bool a_arg2)
	{
		if (MovieOf(a_self)) {
			return true;
		}
		g_loadingSetupMovie.store(true);
		const bool loaded = g_engineLoadMovie(a_self, false, a_arg2);
		g_loadingSetupMovie.store(false);
		const bool ok = loaded && MovieOf(a_self) != nullptr;
		if (!ok && !g_setupMissing.exchange(true)) {
			REX::INFO("step=setup_skip reason=missing movie=FO4SF_SetupScreen");
		} else if (ok) {
			REX::INFO("step=setup_load_movie result=1 movie=FO4SF_SetupScreen");
		}
		return ok;
	}

	RE::UI_MESSAGE_RESULT SetupMenuProcessMessage(void* a_self, RE::UIMessageData& a_message)
	{
		const auto type = a_message.type;
		if (type == RE::UI_MESSAGE_TYPE::kShow && !MovieOf(a_self)) {
			if (!SetupMenuLoadMovie(a_self, false, false)) {
				g_setupOpen.store(false);
				return RE::UI_MESSAGE_RESULT::kHandled;
			}
		}
		const auto result = g_engineProcessMessage(a_self, a_message);
		if (type == RE::UI_MESSAGE_TYPE::kShow) {
			g_setupOpen.store(true);
			SetupListen(a_self);
			SetupWrite(a_self);
		} else if (type == RE::UI_MESSAGE_TYPE::kUpdate) {
			SetupListen(a_self);
			SetupWrite(a_self);
		} else if (type == RE::UI_MESSAGE_TYPE::kHide) {
			g_setupOpen.store(false);
			g_setupListenedMovie.store(nullptr);
		}
		return result;
	}

	bool SetupShouldHandleEvent(void* a_input, const void* a_event)
	{
		if (!a_event || !g_setupOpen.load()) {
			return g_engineShouldHandle ? g_engineShouldHandle(a_input, a_event) : false;
		}
		const auto* base = static_cast<const RE::InputEvent*>(a_event);
		if (base->eventType == RE::InputEvent::EventType::kButton &&
		    (base->deviceType == RE::InputEvent::DeviceType::kKeyboard ||
		     base->deviceType == RE::InputEvent::DeviceType::kGamepad) &&
		    base->status != RE::InputEvent::Status::kStop) {
			return true;
		}
		return g_engineShouldHandle ? g_engineShouldHandle(a_input, a_event) : false;
	}

	void SetupOnButtonEvent(void* a_input, const void* a_event)
	{
		if (g_engineOnButton) {
			g_engineOnButton(a_input, a_event);
		}
		if (!a_event || !g_setupOpen.load()) {
			return;
		}
		if (OpenBlockingOverlayMenu(RE::UI::GetSingleton(), true) != nullptr) {
			return;
		}
		const auto* base = static_cast<const RE::InputEvent*>(a_event);
		if (base->eventType != RE::InputEvent::EventType::kButton ||
		    base->deviceType != RE::InputEvent::DeviceType::kKeyboard) {
			return;
		}
		const auto* button = static_cast<const RE::ButtonEvent*>(a_event);
		if (!(button->value > 0.0f && button->heldDownSecs == 0.0f)) {
			return;
		}
		const auto vk = static_cast<std::uint32_t>(button->idCode);
		bool       handled = false;
		bool       wantCommit = false;
		{
			std::scoped_lock lock(g_setupLock);
			switch (vk) {
			case 0x26:   // VK_UP
			case 0x57:   // W
				g_setupModel.MoveCursor(-1);
				handled = true;
				break;
			case 0x28:   // VK_DOWN
			case 0x53:   // S
				g_setupModel.MoveCursor(1);
				handled = true;
				break;
			case 0x25:   // VK_LEFT
			case 0x41:   // A
				g_setupModel.AdjustRow(g_setupModel.SelectedRow(), -1);
				handled = true;
				break;
			case 0x27:   // VK_RIGHT
			case 0x44:   // D
				g_setupModel.AdjustRow(g_setupModel.SelectedRow(), 1);
				handled = true;
				break;
			case 0x0D:   // VK_RETURN
			case 0x45:   // E
				handled = true;
				wantCommit = true;
				break;
			default:
				break;
			}
		}
		if (!handled) {
			return;
		}
		const_cast<RE::InputEvent*>(base)->status = RE::InputEvent::Status::kStop;
		if (g_task) {
			if (wantCommit) {
				g_task->AddTask([]() { CommitSetupMenuMainThread(); });
			} else {
				g_task->AddTask([]() {
					if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
						queue->AddMessage(SetupMenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
					}
				});
			}
		}
	}

	RE::Scaleform::Ptr<RE::IMenu>* CreateSetupMenu(RE::Scaleform::Ptr<RE::IMenu>* a_out)
	{
		const auto n = ++g_setupCreated;
		void*      menu = std::calloc(1, kMenuBytes);
		if (!menu) {
			REX::ERROR("refuse step=create menu=setup n={} reason=out_of_memory", n);
			std::construct_at(a_out);
			return a_out;
		}
		g_ctor(menu);
		const auto base = reinterpret_cast<std::uintptr_t>(menu);
		auto*      refs = reinterpret_cast<volatile std::uint32_t*>(base + 0x08);
		const auto ctorRefs = *refs;
		*reinterpret_cast<std::uintptr_t*>(base) = reinterpret_cast<std::uintptr_t>(g_setupVtbl.slots.data());
		*reinterpret_cast<std::uintptr_t*>(base + 0x10) = reinterpret_cast<std::uintptr_t>(g_setupInputVtbl.slots.data());
		auto* imenu = static_cast<RE::IMenu*>(menu);
		imenu->menuName = SetupMenuName();
		imenu->flags |= (0x19u | kPauseFlag);
		imenu->flagsUpdated = true;
		if (g_keepAlive && ctorRefs == 1) {
			REX::W32::InterlockedIncrement(refs);
		}
		REX::INFO("step=setup_create n={} menu={} flags={}", n, Hex(base), Hex(imenu->flags));
		std::memcpy(static_cast<void*>(a_out), &menu, sizeof(menu));
		return a_out;
	}

	void PollStartCardGlobalMainThread()
	{
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue || !ui->IsMenuRegistered(StartCardMenuName())) {
			return;
		}
		FindGlobalValue();
		std::string    detail;
		std::uintptr_t form = 0;
		const auto     fid = KitFileForm("FO4SFCoreValues.esm", kCoreStartCardOpenId, "TESGlobal@@", detail);
		if (fid) {
			AcceptById(fid, "FO4SF_StartCardOpen", "TESGlobal@@", kGlobalEditorIdAt, form);
		}
		static bool s_loggedStartCardResolve = false;
		if (!s_loggedStartCardResolve && fid) {
			s_loggedStartCardResolve = true;
			LogCoreValueResolve("FO4SF_StartCardOpen", kCoreStartCardOpenId, form ? fid : 0u);
		}
		float v = 0.0f;
		if (form) {
			const std::size_t valAt = g_forms.globalValueAt ? g_forms.globalValueAt : kGlobalValueAt;
			if (!Peek(form + valAt, v) || !std::isfinite(v)) {
				v = 0.0f;
			}
		}
		static const RE::BSFixedString kLoadingMenu{ "LoadingMenu" };
		static const RE::BSFixedString kChargenMenu{ "ChargenMenu" };
		const bool blockedLoadOrChargen = ui->IsMenuOpen(kLoadingMenu) || ui->IsMenuOpen(kChargenMenu);

		// Paused Exit Lift + 40-pt S.P.E.C.I.A.L. Screen: FO4SF_StartCardOpen == 4.0 requests FO4SF_LiftMenu (acked 5.0; commit 6.0/7.0/8.0).
		const bool wantLift = (v >= 3.5f && v < 5.5f) && ui->IsMenuRegistered(LiftMenuName());
		const bool liftIsOpen = ui->IsMenuRegistered(LiftMenuName()) && ui->IsMenuOpen(LiftMenuName());
		if (wantLift) {
			if (ui->IsMenuOpen(StartCardMenuName())) {
				queue->AddMessage(StartCardMenuName(), RE::UI_MESSAGE_TYPE::kHide);
			}
			if (g_liftMissing.load()) {
				WriteStoreGlobalFloat(form, 0.0f);
				return;
			}
			if (!blockedLoadOrChargen) {
				if (!liftIsOpen) {
					bool alreadyConfirmed = false;
					auto initVals = ReadInitialLiftSpecialMainThread(alreadyConfirmed);
					{
						std::scoped_lock lock(g_liftLock);
						g_liftModel.Reset(initVals, alreadyConfirmed);
					}
					queue->AddMessage(LiftMenuName(), RE::UI_MESSAGE_TYPE::kShow);
					REX::INFO("step=lift_open confirmed={}", alreadyConfirmed ? 1 : 0);
				} else if (v < 4.5f) {
					WriteStoreGlobalFloat(form, 5.0f);
				}
			}
			return;
		}
		if (liftIsOpen) {
			queue->AddMessage(LiftMenuName(), RE::UI_MESSAGE_TYPE::kHide);
			REX::INFO("step=lift_open open=0");
		}

		// S1 Variant (b): FO4SF_StartCardOpen == 2.0 requests FO4SF_SetupMenu (acked as 3.0 once open).
		const bool wantSetup = (v >= 1.5f && v < 3.5f) && ui->IsMenuRegistered(SetupMenuName());
		const bool setupIsOpen = ui->IsMenuRegistered(SetupMenuName()) && ui->IsMenuOpen(SetupMenuName());
		if (wantSetup) {
			if (ui->IsMenuOpen(StartCardMenuName())) {
				queue->AddMessage(StartCardMenuName(), RE::UI_MESSAGE_TYPE::kHide);
			}
			if (g_setupMissing.load()) {
				// R10: FO4SF_SetupScreen.swf missing -> clear request immediately so Papyrus falls back to Variant (a).
				WriteStoreGlobalFloat(form, 0.0f);
				return;
			}
			if (!blockedLoadOrChargen) {
				if (!setupIsOpen) {
					std::size_t totalRows = 0;
					std::size_t availRows = 0;
					bool        fromFile = false;
					{
						std::scoped_lock lock(g_setupLock);
						auto rows = fo4sf::setup::LoadStartPlacesFileOrFallback(
							g_pluginDir / "FO4SFStartPlaces.json", fromFile);
						g_setupModel.Reset(std::move(rows), g_setupShowUnavailable);
						g_setupModelLoaded = true;
						totalRows = g_setupModel.TotalRows();
						availRows = g_setupModel.AvailableRows();
					}
					queue->AddMessage(SetupMenuName(), RE::UI_MESSAGE_TYPE::kShow);
					REX::INFO("step=setup_open rows={} available={} show_unavailable={} source={}",
						totalRows, availRows, g_setupShowUnavailable ? 1 : 0, fromFile ? "json" : "fallback");
				} else if (v < 2.5f) {
					WriteStoreGlobalFloat(form, 3.0f);
				}
			}
			return;
		}
		if (setupIsOpen) {
			queue->AddMessage(SetupMenuName(), RE::UI_MESSAGE_TYPE::kHide);
			REX::INFO("step=setup_open open=0");
		}

		const bool wantOpen = (v >= 0.5f && v < 1.5f) && !g_startCardMissing.load() && !blockedLoadOrChargen;
		const bool isOpen = ui->IsMenuOpen(StartCardMenuName());
		if (wantOpen && !isOpen) {
			queue->AddMessage(StartCardMenuName(), RE::UI_MESSAGE_TYPE::kShow);
			REX::INFO("step=start_card open=1 depth=0");
		} else if (!wantOpen && isOpen) {
			queue->AddMessage(StartCardMenuName(), RE::UI_MESSAGE_TYPE::kHide);
			REX::INFO("step=start_card open=0");
		}
	}

	void PollSpecialTriggerGlobalMainThread()
	{
		if (!g_specialMenu || g_specialOpen.load()) {
			return;
		}
		FindGlobalValue();
		const auto form = LookupFormByEditorIdChecked("FO4SF_OpenSpecialMenu", "TESGlobal@@");
		if (!form) {
			return;
		}
		const std::size_t valAt = g_forms.globalValueAt ? g_forms.globalValueAt : kGlobalValueAt;
		float             v = 0.0f;
		if (!Peek(form + valAt, v) || !std::isfinite(v) || v < 0.5f) {
			return;
		}
		*reinterpret_cast<float*>(form + valAt) = 0.0f;
		OpenSpecialMenuMainThread("global_FO4SF_OpenSpecialMenu");
	}

	RE::Scaleform::Ptr<RE::IMenu>* Create(RE::Scaleform::Ptr<RE::IMenu>* a_out)
	{
		const auto n = ++g_created;
		void*      menu = std::calloc(1, kMenuBytes);
		if (!menu) {
			REX::ERROR("refuse step=create n={} reason=out_of_memory", n);
			std::construct_at(a_out);
			return a_out;
		}
		g_ctor(menu);
		const auto base = reinterpret_cast<std::uintptr_t>(menu);
		const auto vtables = *reinterpret_cast<const std::uintptr_t*>(base) == Address(kVtblPrimary) &&
		                     *reinterpret_cast<const std::uintptr_t*>(base + 0x10) == Address(kVtblInput) &&
		                     *reinterpret_cast<const std::uintptr_t*>(base + 0x50) == Address(kVtblSink);
		auto*      refs = reinterpret_cast<volatile std::uint32_t*>(base + 0x08);   // Scaleform RefCountImplCore
		const auto ctorRefs = *refs;
		*reinterpret_cast<std::uintptr_t*>(base) = reinterpret_cast<std::uintptr_t>(g_vtbl.slots.data());
		if (g_stage >= 2 || PipboyMap::Enabled()) {
			*reinterpret_cast<std::uintptr_t*>(base + 0x10) = reinterpret_cast<std::uintptr_t>(g_inputVtbl.slots.data());
		}
		// what the engine's dynamic_cast reads on our object: the locator one slot before its primary vtable
		const auto rtti = *reinterpret_cast<const std::uintptr_t*>(*reinterpret_cast<const std::uintptr_t*>(base) - 8) ==
		                  *reinterpret_cast<const std::uintptr_t*>(Address(kVtblPrimary) - 8);
		auto* imenu = static_cast<RE::IMenu*>(menu);
		imenu->menuName = MenuName();
		const auto ctorFlags = imenu->flags;
		const auto extra = g_flags | (g_stage >= 3 ? FlagSet(n) : 0);   // stages c to e: this open's flag set
		g_ctorFlags = ctorFlags;
		if (extra) {
			imenu->flags |= extra;
			imenu->flagsUpdated = true;
		}
		if (g_keepAlive && ctorRefs == 1) {
			REX::W32::InterlockedIncrement(refs);   // a public precedent's count: never released to zero
		}
		REX::INFO("step=create n={} menu={} vtables={} rtti={} refcount={} keep_alive={} ctor_flags={} flags={} depth={}{}",
			n, Hex(base), vtables ? "engine" : "UNEXPECTED", rtti ? "engine" : "UNEXPECTED", ctorRefs, g_keepAlive ? 1 : 0,
			Hex(ctorFlags), Hex(imenu->flags), Hex(*reinterpret_cast<const std::uint8_t*>(base + 0x110)),
			g_stage >= 3 ? std::format(" set={}", FlagSetIndex(n)) : "");
		std::memcpy(static_cast<void*>(a_out), &menu, sizeof(menu));
		return a_out;
	}

	// ------------------------------------------------------------------------------------------- checks before use
	bool Refuse(std::string_view a_step, const std::string& a_what)
	{
		REX::ERROR("refuse step={} {}", a_step, a_what);
		return false;
	}

	bool CheckImage()
	{
		g_base = reinterpret_cast<std::uintptr_t>(REX::W32::GetModuleHandleW(nullptr));
		if (!g_base) {
			return Refuse("image", "reason=no_module");
		}
		const auto nt = g_base + *reinterpret_cast<const std::int32_t*>(g_base + 0x3C);
		if (*reinterpret_cast<const std::uint32_t*>(nt) != 0x00004550 ||               // "PE\0\0"
			*reinterpret_cast<const std::uint16_t*>(nt + 0x18) != 0x20B) {              // PE32+
			return Refuse("image", "reason=not_pe32plus");
		}
		g_imageSize = *reinterpret_cast<const std::uint32_t*>(nt + 0x18 + 0x38);       // SizeOfImage
		REX::INFO("step=image base={} size={}", Hex(g_base), Hex(g_imageSize));
		return true;
	}

	bool ReadAddressLibrary(const std::filesystem::path& a_file)
	{
		std::ifstream in(a_file, std::ios::binary);
		if (!in) {
			return Refuse("address_library", std::format("reason=missing file={}", a_file.filename().string()));
		}
		std::array<std::uint8_t, kHeaderBytes> head{};
		in.read(reinterpret_cast<char*>(head.data()), head.size());
		if (!in) {
			return Refuse("address_library", "reason=short_header");
		}
		const auto u32 = [&](std::size_t a_at) {
			std::uint32_t v;
			std::memcpy(&v, head.data() + a_at, sizeof v);
			return v;
		};
		// format, game version [4], name [64], pointer size, data format, offset count (libxse HEADER_V5)
		const auto format = u32(0);
		const REL::Version version{ static_cast<std::uint16_t>(u32(4)), static_cast<std::uint16_t>(u32(8)),
			static_cast<std::uint16_t>(u32(12)), static_cast<std::uint16_t>(u32(16)) };
		const auto pointerSize = u32(84);
		const auto count = u32(92);
		REX::INFO("step=address_library file={} format={} version={} pointer_size={} count={}", a_file.filename().string(),
			format, version.string(), pointerSize, count);
		if (format != 5 || version != kRuntime || pointerSize != 8) {
			return Refuse("address_library", "reason=header (format 5, version 1.16.244.0 and pointer size 8 expected)");
		}
		for (std::size_t i = 0; i < IdCount(); ++i) {
			const auto& id = kIds[i];
			if (id.id >= count) {
				return Refuse("id", std::format("name={} id={} reason=beyond_count count={}", id.name, id.id, count));
			}
			std::uint32_t offset = 0;
			in.seekg(static_cast<std::streamoff>(kHeaderBytes + 4ull * id.id));
			in.read(reinterpret_cast<char*>(&offset), sizeof offset);
			if (!in) {
				return Refuse("id", std::format("name={} id={} reason=short_file", id.name, id.id));
			}
			if (!offset) {
				return Refuse("id", std::format("name={} id={} reason=missing", id.name, id.id));
			}
			if (offset >= g_imageSize) {
				return Refuse("id", std::format("name={} id={} rva={} reason=outside_image", id.name, id.id, Hex(offset)));
			}
			g_rva[i] = offset;
			REX::INFO("step=id name={} id={} rva={} source={}", id.name, id.id, Hex(offset), id.source);
		}
		// the same ids through libxse (the lookups RE::UI and BSFixedString make): same file, same offsets
		for (std::size_t i = 0; i < IdCount(); ++i) {
			const auto viaLibrary = REL::ID(kIds[i].id).offset();
			if (viaLibrary != g_rva[i]) {
				return Refuse("id", std::format("name={} id={} reason=library_mismatch file={} libxse={}", kIds[i].name,
					kIds[i].id, Hex(g_rva[i]), Hex(viaLibrary)));
			}
		}
		return true;
	}

	bool CheckVtable(std::size_t a_id, std::uint32_t a_subobject, std::string_view a_which)
	{
		const auto vt = Address(a_id);
		if (!InImage(vt - 8, 8 + kSlots * 8)) {
			return Refuse("rtti", std::format("vtable={} reason=outside_image", a_which));
		}
		const auto col = *reinterpret_cast<const std::uintptr_t*>(vt - 8);
		if (!InImage(col, 0x14)) {
			return Refuse("rtti", std::format("vtable={} reason=locator_outside_image locator={}", a_which, Hex(col)));
		}
		const auto signature = *reinterpret_cast<const std::uint32_t*>(col);
		const auto offset = *reinterpret_cast<const std::uint32_t*>(col + 0x04);
		const auto typeDescriptor = g_base + *reinterpret_cast<const std::uint32_t*>(col + 0x0C);
		if (signature != 1 || offset != a_subobject) {
			return Refuse("rtti", std::format("vtable={} reason=locator signature={} offset={} expected_offset={}", a_which,
				signature, Hex(offset), Hex(a_subobject)));
		}
		if (!InImage(typeDescriptor + 0x10, sizeof kTypeName)) {
			return Refuse("rtti", std::format("vtable={} reason=type_outside_image", a_which));
		}
		const auto* name = reinterpret_cast<const char*>(typeDescriptor + 0x10);
		if (std::memcmp(name, kTypeName, sizeof kTypeName) != 0) {
			std::string seen;
			for (std::size_t i = 0; i < 48 && InImage(typeDescriptor + 0x10 + i, 1) && name[i]; ++i) {
				seen += (name[i] >= 0x20 && name[i] < 0x7F) ? name[i] : '?';
			}
			return Refuse("rtti", std::format("vtable={} reason=type type={}", a_which, seen));
		}
		if (typeDescriptor != Address(kRtti)) {
			return Refuse("rtti", std::format("vtable={} reason=type_descriptor locator={} rtti_id={}", a_which,
				Hex(typeDescriptor - g_base), Hex(g_rva[kRtti])));
		}
		REX::INFO("step=rtti vtable={} offset={} type={}", a_which, Hex(offset), kTypeName);
		return true;
	}

	bool CheckSlots()
	{
		const auto* slot = reinterpret_cast<const std::uintptr_t*>(Address(kVtblPrimary));
		const auto  want = [&](std::size_t a_slot, std::size_t a_id, std::string_view a_what) {
            if (slot[a_slot] == Address(a_id)) {
				return true;
			}
			return Refuse("slots", std::format("slot={} what={} have={} want={}", Hex(a_slot), a_what,
				InImage(slot[a_slot], 1) ? Hex(slot[a_slot] - g_base) : Hex(slot[a_slot]), Hex(g_rva[a_id])));
		};
		if (!want(0x00, kDtor, "scalar_deleting_dtor") || !want(0x06, kLoadMovie, "LoadMovie") ||
			!want(0x08, kProcessMessage, "ProcessMessage") || !want(0x0A, kIsMovieLoaded, "IsMovieLoaded")) {
			return false;
		}
		if (g_rva[kLoadMovie] != kLoadMovieRva) {
			return Refuse("slots", std::format("what=LoadMovie rva={} sfse_hook_rva={}", Hex(g_rva[kLoadMovie]), Hex(kLoadMovieRva)));
		}
		if (slot[0x03] != slot[0x04]) {
			return Refuse("slots", "what=GetName_GetRootPath reason=not_one_pure_virtual_stub");
		}
		std::string all;
		for (std::size_t i = 0; i <= 0x1A; ++i) {
			all += std::format("{}{}", i ? "," : "", InImage(slot[i], 1) ? Hex(slot[i] - g_base) : "outside");
		}
		REX::INFO("step=slots dtor=ok load_movie=ok process_message=ok is_movie_loaded=ok slot5_pure={} rvas={}",
			slot[0x05] == slot[0x03] ? "yes" : "no", all);
		return true;
	}

	bool CheckCtor()
	{
		const auto ctor = Address(kCtor);
		if (!InImage(ctor, kCtorScan + 7)) {
			return Refuse("ctor", "reason=outside_image");
		}
		const auto* code = reinterpret_cast<const std::uint8_t*>(ctor);
		for (std::size_t i = 0; i + 7 <= kCtorScan; ++i) {
			// lea r64, [rip+disp32]: REX.W (0x48-0x4F), 0x8D, ModRM mod=00 rm=101
			if ((code[i] & 0xF8) == 0x48 && code[i + 1] == 0x8D && (code[i + 2] & 0xC7) == 0x05) {
				std::int32_t disp;
				std::memcpy(&disp, code + i + 3, sizeof disp);
				if (ctor + i + 7 + static_cast<std::intptr_t>(disp) == Address(kVtblPrimary)) {
					REX::INFO("step=ctor rva={} vtable_ref_at={} precedent_offset={}", Hex(g_rva[kCtor]), Hex(i),
						g_rva[kCtor] == kPrecedentCtorRva ? "match" : "differs");
					return true;
				}
			}
		}
		return Refuse("ctor", std::format("rva={} reason=no_primary_vtable_reference first={}", Hex(g_rva[kCtor]), Hex(kCtorScan)));
	}

	// stage c: each Value function's offset is SFSE 0.2.21's own address for it, and each RTTI id names its type
	bool CheckChannelIds()
	{
		for (const auto& [id, rva] : kSfseRvas) {
			if (g_rva[id] != rva) {
				return Refuse("channel_ids", std::format("name={} rva={} sfse_rva={}", kIds[id].name, Hex(g_rva[id]), Hex(rva)));
			}
		}
		for (const auto& [id, tail] : kRttiNames) {
			const auto name = TypeNameAt(Address(id));
			if (!NameIs(name, tail)) {
				return Refuse("channel_ids", std::format("name={} type={} expected=.?AV{}", kIds[id].name,
					name.empty() ? "unreadable" : name, tail));
			}
		}
		REX::INFO("step=channel_ids value_functions=sfse_equal rtti_names=ok");
		return true;
	}

	// stage d: the data handler's id and the form lookup's id are SFSE 0.2.21's own addresses for them
	bool CheckPageIds()
	{
		for (const auto& [id, rva] : { std::pair{ kDataHandlerSingleton, kDataHandlerRva }, std::pair{ kLookupById, kLookupByIdRva } }) {
			if (g_rva[id] != rva) {
				return Refuse("page_ids", std::format("name={} rva={} sfse_rva={}", kIds[id].name, Hex(g_rva[id]), Hex(rva)));
			}
		}
		REX::INFO("step=page_ids data_handler=sfse_equal lookup_by_id=sfse_equal");
		return true;
	}

	bool CheckEverything(const std::filesystem::path& a_dir)
	{
		if (!CheckImage() || !ReadAddressLibrary(a_dir / "versionlib-1-16-244-0.bin") ||
			!CheckVtable(kVtblPrimary, 0x00, "primary") || !CheckVtable(kVtblInput, 0x10, "BSInputEventUser") ||
			!CheckVtable(kVtblSink, 0x50, "BSTEventSink") || !CheckSlots() || !CheckCtor() ||
			(ChannelIdsNeeded() && !CheckChannelIds()) || (g_stage >= 4 && !CheckPageIds())) {
			return false;
		}
		const auto* engine = reinterpret_cast<const std::uintptr_t*>(Address(kVtblPrimary));
		g_vtbl.locator = *reinterpret_cast<const std::uintptr_t*>(Address(kVtblPrimary) - 8);   // checked by CheckVtable
		std::copy_n(engine, kSlots, g_vtbl.slots.begin());
		g_ctor = reinterpret_cast<Ctor_t>(Address(kCtor));
		g_engineDtor = reinterpret_cast<Dtor_t>(engine[0x00]);
		g_engineLoadMovie = reinterpret_cast<LoadMovie_t>(engine[0x06]);
		g_engineProcessMessage = reinterpret_cast<ProcessMessage_t>(engine[0x08]);
		g_vtbl.slots[0x00] = reinterpret_cast<std::uintptr_t>(&MenuDestroy);
		g_vtbl.slots[0x03] = reinterpret_cast<std::uintptr_t>(&MenuGetName);
		g_vtbl.slots[0x04] = reinterpret_cast<std::uintptr_t>(&MenuGetRootPath);
		g_vtbl.slots[0x05] = reinterpret_cast<std::uintptr_t>(&MenuGetViewScaleMode);
		g_vtbl.slots[0x06] = reinterpret_cast<std::uintptr_t>(&MenuLoadMovie);
		g_vtbl.slots[0x08] = reinterpret_cast<std::uintptr_t>(&MenuProcessMessage);
		if (g_stage >= 2 || g_specialMenu || PipboyMap::Requested(a_dir / "FO4SFPipboyMenu.ini")) {   // G2 / FAL-414: install cancel input vtable at Stage >= 2
			const auto* input = reinterpret_cast<const std::uintptr_t*>(Address(kVtblInput));
			g_inputVtbl.locator = *reinterpret_cast<const std::uintptr_t*>(Address(kVtblInput) - 8);   // checked by CheckVtable
			std::copy_n(input, kInputSlots, g_inputVtbl.slots.begin());
			if (!InImage(input[1], 1) || !InImage(input[8], 1)) {
				return Refuse("slots", "what=input_vtable reason=slot_outside_image");
			}
			g_engineShouldHandle = reinterpret_cast<decltype(g_engineShouldHandle)>(input[1]);
			g_engineOnButton = reinterpret_cast<decltype(g_engineOnButton)>(input[8]);
			g_inputVtbl.slots[1] = reinterpret_cast<std::uintptr_t>(&MenuShouldHandleEvent);
			g_inputVtbl.slots[8] = reinterpret_cast<std::uintptr_t>(&MenuOnButtonEvent);
			REX::INFO("step=input_vtable replaced=0x01,0x08 should_handle={} on_button={} cancel_codes={}", Hex(input[1] - g_base),
				Hex(input[8] - g_base), g_cancelCount);
		}
		if (g_specialMenu) {
			g_specialVtbl.locator = g_vtbl.locator;
			std::copy_n(engine, kSlots, g_specialVtbl.slots.begin());
			g_specialVtbl.slots[0x00] = reinterpret_cast<std::uintptr_t>(&SpecialMenuDestroy);
			g_specialVtbl.slots[0x03] = reinterpret_cast<std::uintptr_t>(&SpecialMenuGetName);
			g_specialVtbl.slots[0x04] = reinterpret_cast<std::uintptr_t>(&MenuGetRootPath);
			g_specialVtbl.slots[0x05] = reinterpret_cast<std::uintptr_t>(&MenuGetViewScaleMode);
			g_specialVtbl.slots[0x06] = reinterpret_cast<std::uintptr_t>(&SpecialMenuLoadMovie);
			g_specialVtbl.slots[0x08] = reinterpret_cast<std::uintptr_t>(&SpecialMenuProcessMessage);
			const auto* input = reinterpret_cast<const std::uintptr_t*>(Address(kVtblInput));
			g_specialInputVtbl.locator = *reinterpret_cast<const std::uintptr_t*>(Address(kVtblInput) - 8);
			std::copy_n(input, kInputSlots, g_specialInputVtbl.slots.begin());
			g_specialInputVtbl.slots[1] = reinterpret_cast<std::uintptr_t>(&SpecialShouldHandleEvent);
			g_specialInputVtbl.slots[8] = reinterpret_cast<std::uintptr_t>(&SpecialOnButtonEvent);
		}
		if (g_stage >= 2) {
			g_startCardVtbl.locator = g_vtbl.locator;
			std::copy_n(engine, kSlots, g_startCardVtbl.slots.begin());
			g_startCardVtbl.slots[0x00] = reinterpret_cast<std::uintptr_t>(&StartCardMenuDestroy);
			g_startCardVtbl.slots[0x03] = reinterpret_cast<std::uintptr_t>(&StartCardMenuGetName);
			g_startCardVtbl.slots[0x04] = reinterpret_cast<std::uintptr_t>(&MenuGetRootPath);
			g_startCardVtbl.slots[0x05] = reinterpret_cast<std::uintptr_t>(&MenuGetViewScaleMode);
			g_startCardVtbl.slots[0x06] = reinterpret_cast<std::uintptr_t>(&StartCardMenuLoadMovie);
			g_startCardVtbl.slots[0x08] = reinterpret_cast<std::uintptr_t>(&StartCardMenuProcessMessage);
			const auto* input = reinterpret_cast<const std::uintptr_t*>(Address(kVtblInput));
			g_startCardInputVtbl.locator = *reinterpret_cast<const std::uintptr_t*>(Address(kVtblInput) - 8);
			std::copy_n(input, kInputSlots, g_startCardInputVtbl.slots.begin());
			g_startCardInputVtbl.slots[1] = reinterpret_cast<std::uintptr_t>(&StartCardShouldHandleEvent);

			g_setupVtbl.locator = g_vtbl.locator;
			std::copy_n(engine, kSlots, g_setupVtbl.slots.begin());
			g_setupVtbl.slots[0x00] = reinterpret_cast<std::uintptr_t>(&SetupMenuDestroy);
			g_setupVtbl.slots[0x03] = reinterpret_cast<std::uintptr_t>(&SetupMenuGetName);
			g_setupVtbl.slots[0x04] = reinterpret_cast<std::uintptr_t>(&MenuGetRootPath);
			g_setupVtbl.slots[0x05] = reinterpret_cast<std::uintptr_t>(&MenuGetViewScaleMode);
			g_setupVtbl.slots[0x06] = reinterpret_cast<std::uintptr_t>(&SetupMenuLoadMovie);
			g_setupVtbl.slots[0x08] = reinterpret_cast<std::uintptr_t>(&SetupMenuProcessMessage);
			g_setupInputVtbl.locator = *reinterpret_cast<const std::uintptr_t*>(Address(kVtblInput) - 8);
			std::copy_n(input, kInputSlots, g_setupInputVtbl.slots.begin());
			g_setupInputVtbl.slots[1] = reinterpret_cast<std::uintptr_t>(&SetupShouldHandleEvent);
			g_setupInputVtbl.slots[8] = reinterpret_cast<std::uintptr_t>(&SetupOnButtonEvent);

			g_liftVtbl.locator = g_vtbl.locator;
			std::copy_n(engine, kSlots, g_liftVtbl.slots.begin());
			g_liftVtbl.slots[0x00] = reinterpret_cast<std::uintptr_t>(&LiftMenuDestroy);
			g_liftVtbl.slots[0x03] = reinterpret_cast<std::uintptr_t>(&LiftMenuGetName);
			g_liftVtbl.slots[0x04] = reinterpret_cast<std::uintptr_t>(&MenuGetRootPath);
			g_liftVtbl.slots[0x05] = reinterpret_cast<std::uintptr_t>(&MenuGetViewScaleMode);
			g_liftVtbl.slots[0x06] = reinterpret_cast<std::uintptr_t>(&LiftMenuLoadMovie);
			g_liftVtbl.slots[0x08] = reinterpret_cast<std::uintptr_t>(&LiftMenuProcessMessage);
			g_liftInputVtbl.locator = *reinterpret_cast<const std::uintptr_t*>(Address(kVtblInput) - 8);
			std::copy_n(input, kInputSlots, g_liftInputVtbl.slots.begin());
			g_liftInputVtbl.slots[1] = reinterpret_cast<std::uintptr_t>(&LiftShouldHandleEvent);
			g_liftInputVtbl.slots[8] = reinterpret_cast<std::uintptr_t>(&LiftOnButtonEvent);

			g_blockedMapVtbl.locator = g_vtbl.locator;
			std::copy_n(engine, kSlots, g_blockedMapVtbl.slots.begin());
			g_blockedMapVtbl.slots[0x00] = reinterpret_cast<std::uintptr_t>(&BlockedMapMenuDestroy);
			g_blockedMapVtbl.slots[0x03] = reinterpret_cast<std::uintptr_t>(&BlockedMapMenuGetName);
			g_blockedMapVtbl.slots[0x04] = reinterpret_cast<std::uintptr_t>(&MenuGetRootPath);
			g_blockedMapVtbl.slots[0x05] = reinterpret_cast<std::uintptr_t>(&MenuGetViewScaleMode);
			g_blockedMapVtbl.slots[0x06] = reinterpret_cast<std::uintptr_t>(&BlockedMapMenuLoadMovie);
			g_blockedMapVtbl.slots[0x08] = reinterpret_cast<std::uintptr_t>(&BlockedMapMenuProcessMessage);
			g_blockedMapVtbl.slots[0x0A] = reinterpret_cast<std::uintptr_t>(&MenuIsMovieLoaded);
			g_blockedMapInputVtbl.locator = *reinterpret_cast<const std::uintptr_t*>(Address(kVtblInput) - 8);
			std::copy_n(input, kInputSlots, g_blockedMapInputVtbl.slots.begin());
			g_blockedMapInputVtbl.slots[1] = reinterpret_cast<std::uintptr_t>(&StartCardShouldHandleEvent);
		}
		if (g_stage == 1) {
			g_vtbl.slots[0x0A] = reinterpret_cast<std::uintptr_t>(&MenuIsMovieLoaded);
		}
		REX::INFO("step=ready stage={} replaced=0x00,0x03,0x04,0x05,0x06,0x08{} locator={}",
			g_stage == 1 ? "a" : g_stage == 2 ? "b" : g_stage == 3 ? "c" : g_stage == 4 ? "d" : "e", g_stage == 1 ? ",0x0A" : "",
			Hex(g_vtbl.locator - g_base));
		return true;
	}

	// ------------------------------------------------------------------------------------------- open, close, state
	std::atomic<std::int64_t>  g_stateCheckDueAt{ 0 };
	std::atomic<std::uint32_t> g_stateCheckN{ 0 };

	bool CheckPipboyWristOwnedAndWornMainThread(bool& a_outResolved, bool& a_outOwned, bool& a_outWorn)
	{
		a_outResolved = false;
		a_outOwned = false;
		a_outWorn = false;
		std::string detail;
		const auto wristFid = KitFileForm("FO4SFNewGame.esm", kNewGamePipboyWristId, "TESObjectARMO@@", detail);
		if (!wristFid) {
			return false;
		}
		a_outResolved = true;
		if (!CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk)) {
			return false;
		}
		const auto     player = Singleton(kPlayerSingleton);
		std::uintptr_t invList = 0;
		ObjectType     listType;
		ArrayHead      items{};
		if (!Peek(player + kInventoryListAt, invList) || !IsType(invList, "BGSInventoryList@@", listType) ||
		    !Peek(invList + kInventoryDataAt, items) || items.size > items.capacity || items.size > kKitMaxItems ||
		    (items.size && !items.data)) {
			return false;
		}
		for (std::uint32_t i = 0; i < items.size; ++i) {
			const auto     item = items.data + i * kInventoryItemSize;
			std::uintptr_t obj = 0;
			if (!Peek(item, obj) || !obj) {
				continue;
			}
			std::uint32_t fid = 0;
			if (!Peek(obj + kFormIdAt, fid) || fid != wristFid) {
				continue;
			}
			ArrayHead     stacks{};
			std::uint64_t total = 0;
			bool          okStacks = Peek(item + kItemStacksAt, stacks) && stacks.size <= stacks.capacity &&
			                         stacks.size <= kKitMaxItems && (!stacks.size || stacks.data);
			for (std::uint32_t s = 0; okStacks && s < stacks.size; ++s) {
				std::uint32_t cnt = 0;
				okStacks = Peek(stacks.data + s * kStackSize + kStackCountAt, cnt);
				total += cnt;
			}
			if (!okStacks || total == 0) {
				continue;
			}
			a_outOwned = true;
			std::uint32_t itemFlags = 0;
			if (Peek(item + kItemFlagsAt, itemFlags) && (itemFlags & 0x7u) != 0) {
				a_outWorn = true;
			}
		}
		return a_outOwned && a_outWorn;
	}

	// Step X2 & Step 1f (R13) & 2g-fix6: checks FO4SF_PipboyAcquired (FO4SFCoreValues.esm 0x000865) AND owned+worn FO4SF_PipboyWrist (0x80D)
	bool IsPipboyPickedUpMainThread(float& a_outVal, bool* a_outOwned = nullptr, bool* a_outWorn = nullptr)
	{
		a_outVal = 0.0f;
		if (a_outOwned) *a_outOwned = false;
		if (a_outWorn) *a_outWorn = false;
		FindGlobalValue();
		std::string    detail;
		std::uintptr_t form = 0;
		const auto     fid = KitFileForm("FO4SFCoreValues.esm", kCorePipboyAcquiredId, "TESGlobal@@", detail);
		if (fid) {
			AcceptById(fid, "FO4SF_PipboyAcquired", "TESGlobal@@", kGlobalEditorIdAt, form);
		}
		static bool s_loggedPipboyAcquiredResolve = false;
		if (!s_loggedPipboyAcquiredResolve) {
			s_loggedPipboyAcquiredResolve = true;
			LogCoreValueResolve("FO4SF_PipboyAcquired", kCorePipboyAcquiredId, form ? fid : 0u);
		}
		if (!form) {
			return false;
		}
		const std::size_t valAt = g_forms.globalValueAt ? g_forms.globalValueAt : kGlobalValueAt;
		float             v = 0.0f;
		if (!Peek(form + valAt, v) || !std::isfinite(v)) {
			return false;
		}
		a_outVal = v;
		bool wristResolved = false, wristOwned = false, wristWorn = false;
		const bool wristOk = CheckPipboyWristOwnedAndWornMainThread(wristResolved, wristOwned, wristWorn);
		if (a_outOwned) *a_outOwned = wristResolved ? wristOwned : (v >= 0.5f);
		if (a_outWorn) *a_outWorn = wristResolved ? wristWorn : (v >= 0.5f);
		if (v < 0.5f) {
			return false;
		}
		return wristResolved ? wristOk : true;
	}

	bool CheckOpenGateAndBootMainThread(std::uint32_t a_targetPage, const char* a_by)
	{
		if (g_stage != 2 || g_movie.empty()) {
			return true;
		}
		float acqVal = 0.0f;
		bool  owned = false;
		bool  worn = false;
		const bool needCheck = g_requirePickup || (g_bootOnFirstOpen && !g_bootMovie.empty() && !s_bootPlayed.load());
		const bool acquired = needCheck ? IsPipboyPickedUpMainThread(acqVal, &owned, &worn) : false;
		if (g_requirePickup && !acquired) {
			s_bootPlayed.store(false);
			REX::INFO("step=pipboy_pickup_required by={} page={} value={:.1f} owned={} worn={}",
				a_by ? a_by : "key", a_targetPage, acqVal, owned ? 1 : 0, worn ? 1 : 0);
			return false;
		}
		if (g_bootOnFirstOpen && !g_bootMovie.empty() && (acquired || !g_requirePickup) &&
			std::string_view(a_by ? a_by : "") != "boot_reopen") {
			if (!s_bootPlayed.exchange(true)) {
				g_playingBootMovie.store(true);
				REX::INFO("step=boot_sequence movie={} first_open=1 page={} loose={}",
					g_bootMovie, a_targetPage, BootMovieLooseFileExists() ? 1 : 0);
			}
		}
		return true;
	}

	fo4sf::pipboy::ScreenSourceMode ResolvePipboyScreenSourceMainThread()
	{
		std::optional<float> globVal;
		FindGlobalValue();
		std::string    detail;
		std::uintptr_t form = 0;
		const auto     fid = KitFileForm(
            fo4sf::pipboy::kPipboyScreenSourcePlugin,
            fo4sf::pipboy::kPipboyScreenSourceGlobLocalId,
            "TESGlobal@@",
            detail);
		if (fid) {
			AcceptById(
				fid,
				std::string(fo4sf::pipboy::kPipboyScreenSourceGlobEdid).c_str(),
				"TESGlobal@@",
				kGlobalEditorIdAt,
				form);
		}
		if (form) {
			const std::size_t valAt = g_forms.globalValueAt ? g_forms.globalValueAt : kGlobalValueAt;
			float             v = 0.0f;
			if (Peek(form + valAt, v) && std::isfinite(v)) {
				globVal = v;
			}
		}
		return fo4sf::pipboy::ResolvePipboyScreenSource(g_screenSourceIni, globVal);
	}

	void Toggle(std::uint32_t a_n)
	{
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue) {
			REX::ERROR("refuse step=toggle n={} reason=no_ui_or_queue", a_n);
			return;
		}
		const bool open = ui->IsMenuOpen(MenuName());
		if (!open) {
			if (const char* blocking = OpenBlockingOverlayMenu(ui)) {
				REX::INFO("step=toggle n={} ignored=menu_open menu={}", a_n, blocking);
				return;
			}
			if (!CheckOpenGateAndBootMainThread(s_savedPage.load(), "toggle")) {
				return;
			}
		} else if (const char* topModal = OpenBlockingOverlayMenu(ui, true)) {
			REX::INFO("step=toggle n={} ignored=menu_open menu={}", a_n, topModal);
			return;
		}
		g_cancelHeld = false;   // FAL-414: a release heard while the page was closed must not keep the gate shut
		if (g_stage == 2 && g_codeObj && !open) {
			CollectShellVitalsMainThread(s_savedPage.load());
		}
		if (g_stage == 4 && !open) {
			PageCollect();   // the page's text before the show
		}
		if (g_stage == 5 && !open) {
			KitCollect();    // the kit's screen before the show
		}
		if (open) {
			g_expectOpen = 0;
			queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kHide);
			REX::INFO("step=toggle n={} was_open=1 sent=hide", a_n);
			return;
		}
		const auto effectiveMode = ResolvePipboyScreenSourceMainThread();
		const auto openRes = fo4sf::pipboy::OpenPipboyScreenViaSource(
			effectiveMode,
			[&]() {
				g_expectOpen = 1;
				queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kShow);
				return true;
			},
			[]() { return false; });
		REX::INFO("step=toggle n={} was_open=0 sent={} screen_source={} fallback={} reason={}",
			a_n, openRes.opened ? "show" : "none",
			fo4sf::pipboy::ScreenSourceModeName(openRes.mode), openRes.fellBackTo2D ? 1 : 0, openRes.reason);
	}

	// stage d: the CLOSE button, heard on the menu's thread, closes the menu here, on the main thread, as F10 does
	// (and, FAL-614 proof 1c, the movie's HideMenu through the stand-in BGSCodeObj)
	void Close(std::uint32_t a_n, const char* a_by = "button")
	{
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue) {
			REX::ERROR("refuse step=close n={} reason=no_ui_or_queue", a_n);
			return;
		}
		const bool open = ui->IsMenuOpen(MenuName());
		g_lastShellTransitionMs.store(NowMs());
		g_cancelHeld = false;   // FAL-414: every close clears the cancel gate
		g_armPendingOpenN = 0;
		g_armWaitingRaiseGraph = false;
		g_armShowAt = 0;
		g_armPressAt = 0;
		g_expectOpen = 0;
		if (open) {
			queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kHide);
		}
		REX::INFO("step=close n={} by={} was_open={} sent={}", a_n, a_by, open ? 1 : 0, open ? "hide" : "none");
	}

	void CheckState(std::uint32_t a_n)
	{
		auto* ui = RE::UI::GetSingleton();
		if (!ui) {
			return;
		}
		const int open = ui->IsMenuOpen(MenuName()) ? 1 : 0;
		const int expected = g_expectOpen;
		g_open = open == 1;
		REX::INFO("step=state n={} open={} expected={} match={}", a_n, open, expected, open == expected ? "yes" : "no");
		if (g_stage >= 3) {
			Snapshot(open ? "main_after_open" : "main_after_close", true);
		}
	}

	// stages c, d and e, every 500 ms while the menu is open (and throttled vitals refresh at Stage=2 with CodeObj=1)
	void SendUpdate()
	{
		if (g_closing.load()) {
			return;
		}
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue || !ui->IsMenuOpen(MenuName())) {
			g_open = false;
			return;
		}
		if (const char* topModal = OpenBlockingOverlayMenu(ui, true)) {
			// Discard any Q/E/A/D shell keys pressed while Console or a modal popup is open
			g_shellKeyPending = 0;
			const std::string_view modalView(topModal);
			if (modalView == "MessageBoxMenu" || modalView == "MainMenu" || modalView == "LoadingMenu") {
				Close(0, "modal_preempt");
			}
			return;
		}
		if (g_stage == 2 && g_codeObj) {
			static std::int64_t lastShellVitalsMs = 0;
			const auto          now = NowMs();
			if (now - lastShellVitalsMs >= 500) {
				lastShellVitalsMs = now;
				CollectShellVitalsMainThread(s_savedPage.load());
			}
		}
		if (g_stage == 4) {
			PageCollect();
		}
		if (g_stage == 5) {
			KitCollect();
		}
		queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
	}

	bool GameInFront()
	{
		std::uint32_t pid = 0;
		W32_IMPL_GetWindowThreadProcessId(W32_IMPL_GetForegroundWindow(), &pid);
		return pid == W32_IMPL_GetCurrentProcessId();
	}

	// FAL-614 S1-c, every 30 ms on the key thread, stage b with ShellKeys=: a press (not a hold) of a shell key while the
	// menu is open and the game in front is noted for the menu's thread, and a kUpdate is sent to carry it there
	void ShellKeys(std::uint32_t& a_held)
	{
		const bool    live = g_open && GameInFront();
		std::uint32_t held = 0;
		for (std::size_t i = 0; live && i < g_shellKeyCount; ++i) {
			if (W32_IMPL_GetAsyncKeyState(static_cast<std::int32_t>(g_shellKeys[i].vk)) & 0x8000) {
				held |= 1u << i;
			}
		}
		const auto pressed = held & ~a_held;
		a_held = held;
		if (pressed) {
			g_shellKeyPending.fetch_or(pressed);
			g_task->AddTask([]() { SendUpdate(); });
		}
	}

	// main thread, ArmRaiseMs after the raise (or immediately on accepted=0 / refused): the screen's show.
	// N1 / R10: a missing or refused animation NEVER blocks the Pip-Boy; Toggle(a_n) always opens the shell unless already open.
	void ArmShow(std::uint32_t a_n)
	{
		auto* ui = RE::UI::GetSingleton();
		if (!ui || ui->IsMenuOpen(MenuName())) {
			const auto lower = (g_armState != 1 || !ArmLowerSet()) ? std::string("none") : g_lowerIdle ? ArmPlayIdle(g_lowerIdle) : ArmNotify(*g_lowerEvent);
			REX::INFO("step=arm_show n={} result=skipped reason={} lower={} t_ms={}", a_n, ui ? "already_open" : "no_ui", lower,
				SincePress());
			return;
		}
		Toggle(a_n);
		REX::INFO("step=arm_show n={} sent=show raise={} arm_ready={} t_ms={}", a_n,
			g_armRaiseOutcome.empty() ? "-" : g_armRaiseOutcome, g_armState == 1 ? 1 : 0, SincePress());
	}

	// FAL-852, the key thread's state check after an arm open or close: due at `at` (0 = none), for press n
	struct ArmCheck
	{
		std::uint32_t n = 0;
		std::int64_t  at = 0;
	};

	const RE::BSFixedString& DataMenuFixed()
	{
		static auto* const name = new RE::BSFixedString("DataMenu");
		return *name;
	}

	// C4-4: Hide-only DataMenu suppression (same proven safe pattern as SuppressVanillaMapMenus, zero initFunc replacement).
	// Never interferes with PauseMenu, Console, MainMenu, LoadingMenu, ChargenMenu, MessageBoxMenu, or save/load.
	bool SuppressDataMenuMainThread()
	{
		if (!g_suppressDataMenu || !IsFo4ShellActive()) {
			return false;
		}
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue || !ui->IsMenuRegistered(DataMenuFixed()) || !ui->IsMenuOpen(DataMenuFixed())) {
			return false;
		}
		if (OpenBlockingOverlayMenu(ui, true) != nullptr) {
			return false;
		}
		queue->AddMessage(DataMenuFixed(), RE::UI_MESSAGE_TYPE::kHide);
		const auto n = ++g_dataMenuSuppressions;
		if (n <= 64) {
			REX::INFO("step=data_menu_suppress n={} menu=DataMenu sent=hide", n);
		}
		return true;
	}

	// Step 1 & Step 8: shared main-thread open path for both Key (s_savedPage), MapKey (page 3), and C4-4 Tab key
	void RequestPipboyOpen(std::uint32_t a_targetPage, const char* a_by)
	{
		const std::uint32_t target = std::min<std::uint32_t>(a_targetPage, 4u);
		s_savedPage.store(target);

		auto* ui = RE::UI::GetSingleton();
		if (!ui || ui->IsMenuOpen(MenuName())) {
			return;
		}
		if (const char* blocking = OpenBlockingOverlayMenu(ui)) {
			const bool allowDataMenuClose = g_suppressDataMenu && a_by && std::string_view(a_by) == "tab_key" &&
			                                SameText(blocking, "DataMenu");
			if (!allowDataMenuClose) {
				REX::INFO("step=request_open by={} page={} ignored=menu_open menu={}", a_by ? a_by : "key", target, blocking);
				return;
			}
		}
		if (!CheckOpenGateAndBootMainThread(target, a_by)) {
			return;
		}

		const auto n = ++g_openPressSeq;
		if (g_arm) {
			const auto at = NowMs();
			const bool opening = g_armDispatching.load() || g_raiseRetry.state.load() != kRetryIdle || g_armShowAt.load() != 0;
			if (g_lowerRetry.state.load() != kRetryIdle) {
				REX::INFO("step=arm_key by={} ignored=lowering pending=1 t_ms={}", a_by ? a_by : "key", at - g_armPressAt.load());
				return;
			}
			if (at < g_armLowerUntil.load()) {
				REX::INFO("step=arm_key by={} ignored=lowering lock_left_ms={} t_ms={}", a_by ? a_by : "key",
					g_armLowerUntil.load() - at, at - g_armPressAt.load());
				return;
			}
			if (opening) {
				REX::INFO("step=arm_key by={} ignored=opening pending=1 t_ms={}", a_by ? a_by : "key", at - g_armPressAt.load());
				return;
			}
			g_armPressAt = at;
			g_armN = n;
			g_armPendingOpenN = n;
			REX::INFO("step=arm_key n={} by={} page={} open=0 t_ms=0", n, a_by ? a_by : "key", target);
			CollectShellVitalsMainThread(target);
			ArmRetryStart(g_raiseRetry, n);
			ArmRaise(n);
			return;
		}

		g_lastShellTransitionMs.store(NowMs());
		if (a_by && std::string_view(a_by) == "tab_key" && g_suppressDataMenu) {
			// Ensure Toggle() does not bail on a DataMenu frame whose kHide is still in flight
			if (g_stage == 2 && g_codeObj) {
				CollectShellVitalsMainThread(target);
			}
			g_cancelHeld = false;
			if (auto* queue = RE::UIMessageQueue::GetSingleton()) {
				const auto effectiveMode = ResolvePipboyScreenSourceMainThread();
				const auto openRes = fo4sf::pipboy::OpenPipboyScreenViaSource(
					effectiveMode,
					[&]() {
						g_expectOpen = 1;
						queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kShow);
						return true;
					},
					[]() { return false; });
				REX::INFO("step=toggle n={} was_open=0 sent={} by=tab_key screen_source={} fallback={} reason={}",
					n, openRes.opened ? "show" : "none",
					fo4sf::pipboy::ScreenSourceModeName(openRes.mode), openRes.fellBackTo2D ? 1 : 0, openRes.reason);
			}
		} else {
			Toggle(n);
		}
		g_stateCheckN.store(n);
		g_stateCheckDueAt.store(NowMs() + 750);
	}

	// C4-4: Track whenever any non-DataMenu blocking menu (DialogueMenu, ContainerMenu, WorkshopMenu, PauseMenu,
	// Console, etc.) is open on the main thread so pressing Tab to close a Starfield menu never pops the Pip-Boy.
	void RetryHudWatchHideMainThread(const char* a_when);

	void PollBlockingMenuStateMainThread()
	{
		auto* ui = RE::UI::GetSingleton();
		if (!ui) {
			return;
		}
		const char* blocking = OpenBlockingOverlayMenu(ui);
		const bool  nonDataBlocking = (blocking != nullptr) && !SameText(blocking, "DataMenu");
		g_nonDataBlockingOpen.store(nonDataBlocking);
		if (nonDataBlocking) {
			g_lastNonDataBlockingMs.store(NowMs());
		}
		if (g_hideStarfieldWatch && g_hudWatchRetryPending.load()) {
			RetryHudWatchHideMainThread("ui_poll");
		}
	}

	// C4-4: Main-thread handler for closed-Pip-Boy Tab press when TabOpensPipboy=1. Suppresses Starfield's DataMenu
	// and opens FO4SF_PipboyMenu on the saved page unless another blocking menu (Dialogue/Container/Workshop/Pause/
	// Console/etc.) is currently open OR was open within kBlockingMenuCooldownMs (500 ms, catching same-press Tab-back).
	void HandleClosedTabKeyMainThread(std::uint32_t a_n)
	{
		if (!g_tabOpensPipboy || !IsFo4ShellActive()) {
			return;
		}
		auto* ui = RE::UI::GetSingleton();
		if (!ui || ui->IsMenuOpen(MenuName())) {
			return;
		}
		if (const char* blocking = OpenBlockingOverlayMenu(ui)) {
			if (!SameText(blocking, "DataMenu")) {
				g_nonDataBlockingOpen.store(true);
				g_lastNonDataBlockingMs.store(NowMs());
				REX::INFO("step=tab_key n={} vk=0x9 ignored=menu_open menu={}", a_n, blocking);
				return;
			}
		}
		const auto now = NowMs();
		const auto lastBlock = g_lastNonDataBlockingMs.load();
		if (g_nonDataBlockingOpen.load() || (lastBlock > 0 && (now - lastBlock) < kBlockingMenuCooldownMs)) {
			REX::INFO("step=tab_key n={} vk=0x9 ignored=recent_blocking_menu ago_ms={}", a_n,
				lastBlock > 0 ? (now - lastBlock) : 0);
			return;
		}
		SuppressDataMenuMainThread();
		g_lastShellTransitionMs.store(now);
		const auto page = s_savedPage.load();
		REX::INFO("step=tab_key n={} vk=0x9 page={} sent=request_open", a_n, page);
		RequestPipboyOpen(page, "tab_key");
	}

	// FAL-852 / N1, Key at Arm=1 (game in front): checks Console/blocking menus and RequirePickup on the main thread
	// BEFORE raising or closing, so F7 with Console open logs step=toggle ignored=menu_open menu=Console and never raises bare wrist.
	void ArmKey(std::uint32_t& a_presses, ArmCheck& a_check)
	{
		const auto at = NowMs();
		const bool opening = g_armDispatching.load() || g_raiseRetry.state.load() != kRetryIdle || g_armShowAt.load() != 0 || a_check.at != 0;
		if (g_lowerRetry.state.load() != kRetryIdle) {
			REX::INFO("step=arm_key ignored=lowering pending=1 t_ms={}", at - g_armPressAt.load());
		} else if (at < g_armLowerUntil.load()) {
			REX::INFO("step=arm_key ignored=lowering lock_left_ms={} t_ms={}", g_armLowerUntil.load() - at, at - g_armPressAt.load());
		} else if (opening) {
			// A5 / R10: pressing the Pip-Boy key again while the wrist is raising skips the remaining raise delay
			if (auto pendingShow = g_armShowAt.load(); pendingShow > at) {
				g_armShowAt.store(at);
				REX::INFO("step=arm_raise_skip_wait n={} t_ms={}", g_armN.load(), at - g_armPressAt.load());
			} else {
				REX::INFO("step=arm_key ignored=opening pending=1 t_ms={}", at - g_armPressAt.load());
			}
		} else {
			const auto n = ++a_presses;
			const bool shown = g_armShown.load();
			if (shown) {
				g_armDispatching = true;
				a_check = { n, at + 750 };   // the engine handles the message on a later frame
				g_task->AddTask([n, at]() {
					g_armDispatching = false;
					auto* ui = RE::UI::GetSingleton();
					if (ui) {
						if (const char* topModal = OpenBlockingOverlayMenu(ui, true)) {
							REX::INFO("step=toggle n={} ignored=menu_open menu={}", n, topModal);
							return;
						}
					}
					REX::INFO("step=arm_key n={} open=1 t_ms={}", n, at - g_armPressAt.load());
					Close(n, "key");
				});
			} else {
				// Stamp press timestamp & active cycle token BEFORE arming g_armDispatching so ArmTick watchdog
				// cannot fire prematurely on a stale g_armPressAt from an earlier open cycle.
				g_armPressAt = at;
				g_armN = n;
				g_armPendingOpenN = n;
				g_armDispatching = true;
				g_task->AddTask([n, at]() {
					g_armDispatching = false;
					auto* ui = RE::UI::GetSingleton();
					if (!ui) {
						g_armPendingOpenN = 0;
						g_armPressAt = 0;
						return;
					}
					if (const char* blocking = OpenBlockingOverlayMenu(ui)) {
						g_armPendingOpenN = 0;
						g_armPressAt = 0;
						REX::INFO("step=toggle n={} ignored=menu_open menu={}", n, blocking);
						return;
					}
					if (g_requirePickup) {
						float acqVal = 0.0f;
						if (!IsPipboyPickedUpMainThread(acqVal)) {
							g_armPendingOpenN = 0;
							g_armPressAt = 0;
							s_bootPlayed.store(false);
							REX::INFO("step=pipboy_pickup_required by=arm_key page={} value={:.1f}", s_savedPage.load(), acqVal);
							return;
						}
					}
					if (g_armPendingOpenN.load() != n) {
						return;
					}
					g_armPressAt = at;
					g_armN = n;
					REX::INFO("step=arm_key n={} open=0 t_ms=0", n);
					ArmRetryStart(g_raiseRetry, n);
					CollectShellVitalsMainThread(s_savedPage.load());
					ArmRaise(n);
				});
			}
		}
	}

	// FAL-852 (FAL-725's tick, no sleep on the arm's path): every 30 ms, each due retry is queued (waiting -> in flight),
	// the screen's show ArmRaiseMs after the raise, and the state check 750 ms after a show or close
	void ArmTick(ArmCheck& a_check)
	{
		const auto tick = NowMs();
		static std::uint32_t s_armLoadPollTicks = 0;
		if (++s_armLoadPollTicks % 5 == 0 && g_task) {
			g_task->AddTask([]() { ArmPollLoadingTransitionMainThread(); });
		}
		for (auto* retry : { &g_raiseRetry, &g_lowerRetry }) {
			int waiting = kRetryWaiting;
			if (retry->state.load() == kRetryWaiting && tick >= retry->nextAt.load() &&
				retry->state.compare_exchange_strong(waiting, kRetryInFlight)) {
				const auto rn = retry->n.load();
				if (retry == &g_raiseRetry) {
					g_task->AddTask([rn]() { ArmRaise(rn); });
				} else {
					g_task->AddTask([rn]() { ArmLower(rn); });
				}
			}
		}
		// A5 / R10: hard non-blocking watchdog so a stalled wrist idle can NEVER block opening the Pip-Boy
		constexpr std::int64_t kArmWatchdogSlackMs = 500;
		const auto             pressAt = g_armPressAt.load();
		const auto             maxWaitMs = static_cast<std::int64_t>(g_armRaiseMs) + static_cast<std::int64_t>(g_armRetryMs) + kArmWatchdogSlackMs;
		if (pressAt > 0 && !g_armShown.load() && (tick - pressAt) >= maxWaitMs &&
			(g_armDispatching.load() || g_raiseRetry.state.load() != kRetryIdle || g_armShowAt.load() != 0)) {
			if (const auto sn = g_armPendingOpenN.exchange(0); sn != 0) {
				g_armDispatching = false;
				g_raiseRetry.state = kRetryIdle;
				g_armWaitingRaiseGraph = false;
				g_armShowAt = 0;
				g_armPressAt = 0;
				REX::INFO("step=arm_watchdog_open n={} elapsed_ms={}", sn, tick - pressAt);
				g_task->AddTask([sn]() { ArmShow(sn); });
				a_check = { sn, tick + 750 };
			}
		}
		if (auto showAt = g_armShowAt.load(); showAt && tick >= showAt && g_armShowAt.compare_exchange_strong(showAt, 0)) {
			if (const auto sn = g_armPendingOpenN.exchange(0); sn != 0) {
				g_armWaitingRaiseGraph = false;
				g_task->AddTask([sn]() { ArmShow(sn); });
				a_check = { sn, tick + 750 };
			}
		}
		if (a_check.at && tick >= a_check.at) {
			const auto cn = a_check.n;
			a_check.at = 0;
			g_task->AddTask([cn]() { CheckState(cn); });
		}
	}

	std::uint32_t KeyThread(void*)
	{
		std::uint32_t presses = 0;
		std::uint32_t ticks = 0;
		std::uint32_t shellTicks = 0;
		std::uint32_t dataMenuTicks = 0;
		std::uint32_t specialTicks = 0;
		bool          down = false;
		bool          tabDown = false;
		bool          specialKeyDown = false;
		bool          snapDown = false;
		ArmCheck      armCheck;     // FAL-852
		ArmCheck      stateCheck;   // non-blocking 750 ms state check (zero Sleep(750) on KeyThread)
		std::array<std::uint32_t, 6> kitHeld{};   // stage e: how many 30 ms ticks each kit key has been held
		std::uint32_t                shellHeld = 0;   // FAL-614 S1-c: the shell keys held at the last tick, one bit each
		for (;;) {
			REX::W32::Sleep(30);
			const auto tickMs = NowMs();

			// Step 5: 2 s busy watchdog around Scaleform movie calls (lock-synchronized snapshot of top stack frame)
			GfxWatchdogFrame activeGfx{};
			{
				std::scoped_lock lock(g_gfxWatchdogLock);
				activeGfx = g_gfxActiveFrame;
			}
			if (activeGfx.startMs > 0) {
				const auto busyMs = tickMs - activeGfx.startMs;
				if (busyMs >= kWatchdogBusyMs && g_gfxWatchdogLoggedSeq.exchange(activeGfx.seq) != activeGfx.seq) {
					REX::ERROR("step=watchdog_busy seq={} call={} busy_ms={}",
						activeGfx.seq, activeGfx.what ? activeGfx.what : "unknown", busyMs);
				}
			}

			if (auto due = g_stateCheckDueAt.load(); due && tickMs >= due && g_stateCheckDueAt.compare_exchange_strong(due, 0)) {
				const auto cn = g_stateCheckN.load();
				g_task->AddTask([cn]() { CheckState(cn); });
			}
			if (stateCheck.at && tickMs >= stateCheck.at) {
				const auto cn = stateCheck.n;
				stateCheck.at = 0;
				g_task->AddTask([cn]() { CheckState(cn); });
			}

			const bool now = (W32_IMPL_GetAsyncKeyState(static_cast<std::int32_t>(g_key)) & 0x8000) != 0;
			const bool shellHandlesOpenKey = IsFo4ShellActive() && g_open.load();
			if (!shellHandlesOpenKey) {
				if (now && !down && GameInFront() && g_arm) {   // FAL-852: the raise first, or the close (then the lower)
					ArmKey(presses, armCheck);
				} else if (now && !down && GameInFront()) {
					const auto n = ++presses;
					g_task->AddTask([n]() { Toggle(n); });
					stateCheck = { n, NowMs() + 750 };   // non-blocking state check on a later tick
				}
			}
			down = now;
			// C4-4: Opt-in closed-Pip-Boy Tab open (TabOpensPipboy=1) and hide-only DataMenu suppression (SuppressDataMenu=1).
			// Refreshes g_nonDataBlockingOpen / g_lastNonDataBlockingMs from main thread so Tab-closing a Starfield menu
			// (DialogueMenu, ContainerMenu, WorkshopMenu, etc.) within 500 ms never pops the Pip-Boy.
			if (IsFo4ShellActive()) {
				const auto dt = ++dataMenuTicks;
				if (g_tabOpensPipboy && !g_open.load() && (dt % 2 == 0)) {
					g_task->AddTask([]() { PollBlockingMenuStateMainThread(); });
				}
				const bool tabNow = (W32_IMPL_GetAsyncKeyState(0x09) & 0x8000) != 0;
				if (g_tabOpensPipboy && tabNow && !tabDown && !g_open.load() && GameInFront()) {
					const auto lastBlock = g_lastNonDataBlockingMs.load();
					const bool blockedAtDown = g_nonDataBlockingOpen.load() ||
					                           (lastBlock > 0 && (tickMs - lastBlock) < kBlockingMenuCooldownMs);
					const bool shellCooldown = (tickMs - g_lastShellTransitionMs.load()) < kShellTabCooldownMs;
					if (!blockedAtDown && !shellCooldown) {
						g_lastShellTransitionMs.store(tickMs);
						const auto tn = ++g_tabKeyPresses;
						g_task->AddTask([tn]() { HandleClosedTabKeyMainThread(tn); });
					}
				}
				tabDown = tabNow;
				if (g_suppressDataMenu) {
					const bool recentShellTransition = (tickMs - g_lastShellTransitionMs.load()) < 2500;
					if (recentShellTransition || (dt % 3 == 0)) {
						g_task->AddTask([]() { SuppressDataMenuMainThread(); });
					}
				}
			}
			if (g_arm) {
				ArmTick(armCheck);
			}
			if (g_stage == 2 && CodeObjPending() && ++ticks % 17 == 0) {   // FAL-614 proof 1b: retry the stand-in
				g_task->AddTask([]() { SendUpdate(); });   // nothing while the menu is closed
			}
			if (g_stage == 2 && g_shellKeyCount && !IsFo4ShellActive()) {   // FAL-614 S1-c: standalone probe shell keys
				ShellKeys(shellHeld);
			}
			if (g_stage == 2 && g_answerNow.exchange(false)) {   // S1-c: the shell asked for a page or tab (a click, a key)
				g_task->AddTask([]() { SendUpdate(); });
			}
			PipboyMap::Tick();
			if (g_hideStarfieldWatch && g_hudWatchRetryPending.load()) {
				static std::uint32_t hudWatchPollTicks = 0;
				if (++hudWatchPollTicks % 5 == 0) {
					g_task->AddTask([]() { RetryHudWatchHideMainThread("ui_poll"); });
				}
			}
			if (g_stage >= 2) {
				static std::uint32_t startCardTicks = 0;
				if (++startCardTicks % 8 == 0) {
					g_task->AddTask([]() { PollStartCardGlobalMainThread(); });
				}
			}
			if (g_specialMenu) {
				if (g_specialKey != 0) {
					const bool spNow = (W32_IMPL_GetAsyncKeyState(static_cast<std::int32_t>(g_specialKey)) & 0x8000) != 0;
					if (spNow && !specialKeyDown && GameInFront() && !g_specialOpen.load()) {
						g_task->AddTask([]() { OpenSpecialMenuMainThread("special_key"); });
					}
					specialKeyDown = spNow;
				}
				if (++specialTicks % 17 == 0) {
					g_task->AddTask([]() { PollSpecialTriggerGlobalMainThread(); });
				}
			}
			if (g_stage >= 2 && g_cancelNow.exchange(false)) {   // G2 / FAL-414: Tab or Esc closes FO4SF_PipboyMenu at Stage >= 2
				const auto n = ++presses;
				g_task->AddTask([n]() { Close(n, "cancel"); });
				stateCheck = { n, NowMs() + 750 };
			}
			if (g_stage < 3) {
				if (g_stage == 2 && g_codeObj && g_open.load() && ++shellTicks % 17 == 0) {
					g_task->AddTask([]() { SendUpdate(); });
				}
				continue;
			}
			if (g_stage == 5) {   // the kit's keys, only while the page is open and the game in front
				if (g_open && GameInFront()) {
					KitKeys(kitHeld);
				} else {
					kitHeld.fill(0);
				}
			}
			if (g_stage >= 4) {   // the buttons (and the kit's moves), heard on the menu's thread; a close counts as a press
				if (g_refreshNow.exchange(false)) {   // SendUpdate sends nothing once the menu is closed
					g_task->AddTask([]() { SendUpdate(); });
				}
				if (g_closeNow.exchange(false)) {
					const auto n = ++presses;
					g_task->AddTask([n]() { Close(n); });
					stateCheck = { n, NowMs() + 750 };
				}
			}
			// stage c: the snapshot key (a main-thread snapshot, the control), and the refresh while open
			const bool snap = g_snapshotKey && (W32_IMPL_GetAsyncKeyState(static_cast<std::int32_t>(g_snapshotKey)) & 0x8000) != 0;
			if (snap && !snapDown && GameInFront()) {
				g_task->AddTask([]() {
					Snapshot("key", true);
					if (g_stage == 5) {   // FAL-446: the mission's bytes, for the stage's offset
						LogKitQuestBytes();
						LogKitMapBytes();   // FAL-595: the player's angle and cell, for HeadingAt= and GridUnits=
					}
				});
			}
			snapDown = snap;
			if (g_open && ++ticks % 17 == 0) {   // 17 x 30 ms
				g_task->AddTask([]() { SendUpdate(); });
			}
		}
	}

	const RE::BSFixedString& HudMenuFixed()
	{
		static auto* const name = new RE::BSFixedString("HUDMenu");
		return *name;
	}

	// Round 11 Review #5: Retry pending HUDMenu watch-hide across MenuOpenCloseEvent transitions and reset state
	// when HUDMenu closes or LoadingMenu appears so retries never spin after HUDMenu unloads.
	class HudWatchMenuEventSink final : public RE::BSTEventSink<RE::MenuOpenCloseEvent>
	{
	public:
		RE::BSEventNotifyControl ProcessEvent(const RE::MenuOpenCloseEvent& a_event,
			RE::BSTEventSource<RE::MenuOpenCloseEvent>*) override
		{
			if (!g_hideStarfieldWatch || !a_event.menuName.c_str()) {
				return RE::BSEventNotifyControl::kContinue;
			}
			const char* name = a_event.menuName.c_str();
			if (SameText(name, "LoadingMenu")) {
				g_hudWatchHiddenMovie.store(nullptr);
				g_hudWatchTryCount.store(0);
				g_hudWatchRetryPending.store(false);
			} else if (SameText(name, "HUDMenu")) {
				if (!a_event.opening) {
					g_hudWatchHiddenMovie.store(nullptr);
					g_hudWatchTryCount.store(0);
					g_hudWatchRetryPending.store(false);
				} else if (g_hudWatchHiddenMovie.load() == nullptr || g_hudWatchRetryPending.load()) {
					g_hudWatchRetryPending.store(true);
					if (g_task) {
						g_task->AddTask([]() { RetryHudWatchHideMainThread("menu_open_close"); });
					}
				}
			} else if (g_hudWatchRetryPending.load() && g_task) {
				g_task->AddTask([]() { RetryHudWatchHideMainThread("menu_transition"); });
			}
			return RE::BSEventNotifyControl::kContinue;
		}
	};
	HudWatchMenuEventSink g_hudWatchMenuSink{};

	void Register()
	{
		auto* ui = RE::UI::GetSingleton();
		if (!ui) {
			Refuse("register", "reason=no_ui");
			return;
		}
		if (g_hideStarfieldWatch) {
			ui->RegisterSink<RE::MenuOpenCloseEvent>(&g_hudWatchMenuSink);
		}
		if (ui->IsMenuRegistered(MenuName())) {
			Refuse("register", "reason=name_taken");
			return;
		}
		ui->RegisterMenu(kMenuName, &Create);
		if (!ui->IsMenuRegistered(MenuName())) {
			Refuse("register", "reason=not_taken");
			return;
		}
		g_registered = true;
		const auto hooked = *reinterpret_cast<const std::uint8_t*>(Address(kLoadMovie)) == 0xE9;   // SFSE's branch
		REX::INFO("step=register result=ok name={} load_movie_hooked_by_sfse={}", kMenuName, hooked ? "yes" : "no");
		if (g_specialMenu && !ui->IsMenuRegistered(SpecialMenuName())) {
			ui->RegisterMenu(fo4sf::kOurSpecialMenuName, &CreateSpecialMenu);
			REX::INFO("step=special_register result={} name={} movie={} max_points={}",
				ui->IsMenuRegistered(SpecialMenuName()) ? "ok" : "failed",
				fo4sf::kOurSpecialMenuName, g_specialMovie, g_specialMaxPoints);
		}
		if (g_stage >= 2 && !ui->IsMenuRegistered(StartCardMenuName())) {
			ui->RegisterMenu(fo4sf::kOurStartCardMenuName, &CreateStartCardMenu);
			REX::INFO("step=start_card_register result={} name={} movie=FO4SF_StartCard",
				ui->IsMenuRegistered(StartCardMenuName()) ? "ok" : "failed", fo4sf::kOurStartCardMenuName);
		}
		if (g_stage >= 2 && !ui->IsMenuRegistered(SetupMenuName())) {
			ui->RegisterMenu(fo4sf::kOurSetupMenuName, &CreateSetupMenu);
			REX::INFO("step=setup_register result={} name={} movie=FO4SF_SetupScreen show_unavailable={}",
				ui->IsMenuRegistered(SetupMenuName()) ? "ok" : "failed",
				fo4sf::kOurSetupMenuName, g_setupShowUnavailable ? 1 : 0);
		}
		if (g_stage >= 2 && !ui->IsMenuRegistered(LiftMenuName())) {
			ui->RegisterMenu(fo4sf::kOurLiftMenuName, &CreateLiftMenu);
			REX::INFO("step=lift_register result={} name={} movie=FO4SF_LiftScreen",
				ui->IsMenuRegistered(LiftMenuName()) ? "ok" : "failed",
				fo4sf::kOurLiftMenuName);
		}
		World::Start(g_task);
		PipboyMap::SetHostCallbacks(&RequestPipboyOpen, &Close, &GfxWatchdogEnter, &GfxWatchdogExit, &CreateBlockedMapMenuInstance);
		PipboyMap::Start(g_task);
		const auto thread = REX::W32::CreateThread(nullptr, 0, &KeyThread, nullptr, 0, nullptr);
		if (!thread) {
			Refuse("key_thread", "reason=create_failed");
			return;
		}
		REX::W32::CloseHandle(thread);
		REX::INFO("step=key_thread key={}{}", Hex(g_key), g_stage >= 3 ? std::format(" snapshot_key={}", Hex(g_snapshotKey)) : "");
	}

	// Round 11 D7(b): Isolated ASMovieRootBase lookup for Starfield's HUDMenu that never mutates g_checkedMovie or
	// g_channelOff so a HUDMenu edge case can never disable the Pip-Boy Scaleform channel.
	RE::Scaleform::GFx::ASMovieRootBase* HudRootOf(const RE::IMenu* a_menu)
	{
		const auto movie = a_menu ? reinterpret_cast<std::uintptr_t>(MovieOf(a_menu)) : 0;
		if (!movie || g_rva[kMovieRootRtti] == 0) {
			return nullptr;
		}
		std::uintptr_t root = 0;
		ObjectType     rootType;
		std::uintptr_t vt = 0;
		if (!Peek(movie + kMovieRootAt, root) || !TypeOf(root, rootType) || rootType.descriptor != Address(kMovieRootRtti) ||
			!Peek(root, vt)) {
			return nullptr;
		}
		const auto* slot = reinterpret_cast<const std::uintptr_t*>(vt);
		if (!InImage(vt, (kGetVariableSlot + 1) * 8) || !InImage(slot[kGetVariableSlot], 1)) {
			return nullptr;
		}
		return reinterpret_cast<RE::Scaleform::GFx::ASMovieRootBase*>(root);
	}

	// Round 11 D7(b) + Review #5: Hide Starfield's bottom-left wrist watch (HUDMenu root.BottomLeftGroup_mc and its
	// watch/planet/O2/CO2 child clips from playerhudcomponents.swf) while keeping RightMeters_mc (Health/Ammo),
	// CenterGroup_mc (Crosshair), RolloverWidget_mc ([E] prompts), TopCenterGroup_mc, and EnemyHealthHolder_mc intact.
	// If no_root or missing_bottom_left occurs on an early attempt, sets g_hudWatchRetryPending so MenuOpenCloseEvent
	// transitions and the main-thread UI poll hook retry cleanly until hidden or HUDMenu unloads, logging try=<n>.
	// Gated behind HideStarfieldWatch=1 (one-line HideStarfieldWatch=0 rollback).
	void ApplyHudWatchHide(const RE::IMenu* a_menu, const char* a_when)
	{
		if (!g_hideStarfieldWatch || !a_menu) {
			return;
		}
		const void* const movie = MovieOf(a_menu);
		if (!movie) {
			g_hudWatchRetryPending.store(g_hudWatchTryCount.load() < kMaxHudWatchTries);
			return;
		}
		if (g_hudWatchHiddenMovie.load() == movie) {
			g_hudWatchRetryPending.store(false);
			return;
		}
		const auto attempt = ++g_hudWatchTryCount;
		auto* const root = HudRootOf(a_menu);
		if (!root) {
			g_hudWatchRetryPending.store(attempt < kMaxHudWatchTries);
			if (attempt <= 3 || attempt == kMaxHudWatchTries) {
				REX::INFO("step=hud_watch_hide when={} try={} movie={} ok=0 reason=no_root",
					a_when ? a_when : "on_movie_created", attempt, Hex(reinterpret_cast<std::uintptr_t>(movie)));
			}
			return;
		}
		RE::Scaleform::GFx::Value top;
		RE::Scaleform::GFx::Value bottomLeft;
		if (!root->GetVariable(&top, "root") || !top.IsObject() ||
			!ReadPath(top, "BottomLeftGroup_mc", bottomLeft) || !bottomLeft.IsObject()) {
			g_hudWatchRetryPending.store(attempt < kMaxHudWatchTries);
			if (attempt <= 3 || attempt == kMaxHudWatchTries) {
				REX::INFO("step=hud_watch_hide when={} try={} movie={} ok=0 reason=missing_bottom_left",
					a_when ? a_when : "on_movie_created", attempt, Hex(reinterpret_cast<std::uintptr_t>(movie)));
			}
			return;
		}
		const bool visOk = bottomLeft.SetMember("visible", RE::Scaleform::GFx::Value(false));
		(void)bottomLeft.SetMember("alpha", RE::Scaleform::GFx::Value(0.0));
		(void)bottomLeft.SetMember("x", RE::Scaleform::GFx::Value(-10000.0));

		// Also hide direct watch/planet/O2/CO2 child clips so any HUDMenu root fade tween (__motion_BottomLeftGroup_mcaf1)
		// that restores BottomLeftGroup_mc.alpha cannot reveal the Mars/O2/CO2 watch face.
		constexpr std::array<const char*, 17> kWatchChildren{
			"WatchFaceComponent_mc",
			"WatchOutline_mc",
			"WatchPointerOutline_mc",
			"WatchIconsWidget_mc",
			"O2CO2_mc",
			"O2CO2thin_mc",
			"locationNameBase_mc",
			"DayCycleBase_mc",
			"Grav_mc",
			"Oxygen_mc",
			"Temperature_mc",
			"EnvCondition_mc",
			"EnvConditionBase_mc",
			"BioCondition_mc",
			"BioConditionBase_mc",
			"BioAlertBG_mc",
			"OffPlanet_mc",
		};
		std::uint32_t childrenHidden = 0;
		for (const char* childName : kWatchChildren) {
			RE::Scaleform::GFx::Value child;
			if (bottomLeft.GetMember(childName, &child) && child.IsObject()) {
				if (child.SetMember("visible", RE::Scaleform::GFx::Value(false))) {
					++childrenHidden;
				}
				(void)child.SetMember("alpha", RE::Scaleform::GFx::Value(0.0));
			}
		}
		const bool hidden = visOk || childrenHidden > 0;
		if (hidden) {
			g_hudWatchHiddenMovie.store(movie);
			g_hudWatchRetryPending.store(false);
		} else {
			g_hudWatchRetryPending.store(attempt < kMaxHudWatchTries);
		}
		REX::INFO("step=hud_watch_hide when={} try={} movie={} ok={} target=BottomLeftGroup_mc children_hidden={}",
			a_when ? a_when : "on_movie_created", attempt, Hex(reinterpret_cast<std::uintptr_t>(movie)),
			hidden ? 1 : 0, childrenHidden);
	}

	void RetryHudWatchHideMainThread(const char* a_when)
	{
		if (!g_hideStarfieldWatch || !g_hudWatchRetryPending.load()) {
			return;
		}
		auto* ui = RE::UI::GetSingleton();
		if (!ui || !ui->IsMenuOpen(HudMenuFixed())) {
			g_hudWatchRetryPending.store(false);
			return;
		}
		if (g_hudWatchTryCount.load() >= kMaxHudWatchTries) {
			g_hudWatchRetryPending.store(false);
			return;
		}
		const auto hudMenu = ui->GetMenu(HudMenuFixed());
		if (!hudMenu) {
			g_hudWatchRetryPending.store(false);
			return;
		}
		ApplyHudWatchHide(hudMenu.get(), a_when);
	}

	void OnMovieCreated(RE::IMenu* a_menu)
	{
		World::OnMovieCreated(a_menu);
		PipboyMap::OnMovieCreated(a_menu);
		if (g_hideStarfieldWatch && a_menu && a_menu->menuName.c_str()) {
			if (SameText(a_menu->menuName.c_str(), "LoadingMenu")) {
				g_hudWatchHiddenMovie.store(nullptr);
				g_hudWatchTryCount.store(0);
				g_hudWatchRetryPending.store(false);
			} else if (SameText(a_menu->menuName.c_str(), "HUDMenu")) {
				if (g_hudWatchHiddenMovie.load() != MovieOf(a_menu)) {
					g_hudWatchTryCount.store(0);
				}
				ApplyHudWatchHide(a_menu, "on_movie_created");
			}
		}
		if (g_suppressDataMenu && IsFo4ShellActive() && g_task && a_menu && a_menu->menuName.c_str() &&
			SameText(a_menu->menuName.c_str(), "DataMenu")) {
			g_task->AddTask([]() { SuppressDataMenuMainThread(); });
		}
		if (IsOurs(a_menu)) {
			REX::INFO("step=sfse_movie_created menu={} movie={}", Hex(reinterpret_cast<std::uintptr_t>(a_menu)),
				Hex(reinterpret_cast<std::uintptr_t>(MovieOf(a_menu))));
		}
	}

	void ProbeQuestLabelRuntime();

	void OnMessage(SFSE::MessagingInterface::Message* a_msg)
	{
		if (a_msg && a_msg->type == SFSE::MessagingInterface::kPostDataLoad) {
			REX::INFO("step=post_data_load");
			g_task->AddTask([]() { Register(); });   // the first main-thread task after game data loaded
			if (g_stage == 2 && g_codeObj) {
				g_task->AddTask([]() { ProbeQuestLabelRuntime(); });
			}
		}
	}

	std::uint32_t ReadNumber(const std::filesystem::path& a_ini, const wchar_t* a_key, std::uint32_t a_default)
	{
		std::array<wchar_t, 64> text{};
		REX::W32::GetPrivateProfileStringW(L"FO4SFPipboyMenu", a_key, L"", text.data(), static_cast<std::uint32_t>(text.size()),
			a_ini.c_str());
		return text[0] ? static_cast<std::uint32_t>(std::wcstoul(text.data(), nullptr, 0)) : a_default;   // 0x.. or decimal
	}

	// a value as ASCII; any other character as '?'
	// FAL-614 proof 2a: long enough for CodeObjNames at its most, up to kMaxCodeNames names of 64 and their commas
	std::string ReadText(const std::filesystem::path& a_ini, const wchar_t* a_key)
	{
		std::array<wchar_t, kMaxCodeNames * (kMaxName + 1) + 1> text{};
		REX::W32::GetPrivateProfileStringW(L"FO4SFPipboyMenu", a_key, L"", text.data(), static_cast<std::uint32_t>(text.size()),
			a_ini.c_str());
		std::string out;
		for (const wchar_t* at = text.data(); *at; ++at) {
			out += (*at > 0x20 && *at < 0x7F) ? static_cast<char>(*at) : '?';
		}
		return out;
	}

	// FAL-614 proof 2b: CodeObjProbe= and CodeObjCalls=<path>,<path>,... (empty: none), 1 to kMaxCodeNames paths of 1 to 64
	// letters, digits, '_' and '.', each part between dots not empty
	bool ParsePaths(std::string_view a_list, std::array<std::string, kMaxCodeNames>& a_out, std::size_t& a_count,
		std::string_view a_key)
	{
		a_count = 0;
		if (a_list.empty()) {
			return true;
		}
		const std::string list(a_list);
		std::size_t       start = 0;
		while (start <= list.size()) {
			const auto end = std::min(list.find(',', start), list.size());
			const auto name = list.substr(start, end - start);
			const bool ok = !name.empty() && name.size() <= kMaxName && a_count < kMaxCodeNames && name.front() != '.' &&
			                name.back() != '.' && name.find("..") == std::string::npos &&
			                std::ranges::all_of(name, [](char a_c) {
				                return (a_c >= 'A' && a_c <= 'Z') || (a_c >= 'a' && a_c <= 'z') || (a_c >= '0' && a_c <= '9') ||
				                       a_c == '_' || a_c == '.';
			                });
			if (!ok) {
				Refuse("ini", std::format("{}={} (with CodeObj=1 only; 1 to {} paths of letters, digits, _ and .)", a_key, list,
					kMaxCodeNames));
				return false;
			}
			a_out[a_count++] = name;
			start = end + 1;
		}
		return true;
	}

	// FAL-614 S1-c: ShellKeys=<key>:<path>,... (empty: none), 1 to 8 entries; the key a virtual-key code (0x01 to 0xFE,
	// not Key, none twice), the path as one of CodeObjCalls=
	bool ParseShellKeys(std::string_view a_list)
	{
		g_shellKeyCount = 0;
		if (a_list.empty()) {
			return true;
		}
		const std::string list(a_list);
		std::size_t       start = 0;
		while (start <= list.size()) {
			const auto  end = std::min(list.find(',', start), list.size());
			const auto  entry = list.substr(start, end - start);
			const auto  colon = entry.find(':');
			char*       stop = nullptr;
			const auto  vk = colon == std::string::npos ? 0 : static_cast<std::uint32_t>(std::strtoul(entry.c_str(), &stop, 0));
			std::array<std::string, kMaxCodeNames> path{};
			std::size_t count = 0;
			const bool  ok = colon != std::string::npos && stop == entry.c_str() + colon && vk >= 1 && vk <= 0xFE && vk != g_key &&
			                g_shellKeyCount < kMaxShellKeys && colon + 1 < entry.size() &&
			                std::ranges::none_of(g_shellKeys.begin(), g_shellKeys.begin() + g_shellKeyCount,
								[&](const ShellKey& a_key) { return a_key.vk == vk; }) &&
			                ParsePaths(entry.substr(colon + 1), path, count, "shell_keys") && count == 1;
			if (!ok) {
				Refuse("ini", std::format("shell_keys={} (with CodeObj=1 only; 1 to {} <key>:<path>, the key 0x01 to 0xFE, not Key, "
										  "none twice)", list, kMaxShellKeys));
				g_shellKeyCount = 0;
				return false;
			}
			g_shellKeys[g_shellKeyCount++] = { vk, path[0] };
			start = end + 1;
		}
		return true;
	}

	// FAL-614 proof 1b: CodeObjNames=<name>,<name>,... (empty: PlaySound,HideMenu), 1 to 64 names of 1 to 64 letters,
	// digits and '_', none twice; each becomes one function on the stand-in BGSCodeObj
	bool ParseCodeObjNames(std::string_view a_list)
	{
		const std::string list = a_list.empty() ? std::string("PlaySound,HideMenu") : std::string(a_list);
		g_codeObjCount = 0;
		std::size_t start = 0;
		while (start <= list.size()) {
			const auto end = std::min(list.find(',', start), list.size());
			const auto name = list.substr(start, end - start);
			const bool ok = !name.empty() && name.size() <= kMaxName && g_codeObjCount < kMaxCodeNames &&
			                std::ranges::all_of(name, [](char a_c) {
				                return (a_c >= 'A' && a_c <= 'Z') || (a_c >= 'a' && a_c <= 'z') || (a_c >= '0' && a_c <= '9') || a_c == '_';
			                }) &&
			                std::ranges::find(g_codeObjNames.begin(), g_codeObjNames.begin() + g_codeObjCount, name) ==
			                    g_codeObjNames.begin() + g_codeObjCount;
			if (!ok) {
				Refuse("ini", std::format("code_obj_names={} (1 to {} names of letters, digits and _, none twice)", list, kMaxCodeNames));
				return false;
			}
			g_codeObjNames[g_codeObjCount] = name;
			g_codeObjFunctions[g_codeObjCount].Name(name);
			++g_codeObjCount;
			start = end + 1;
		}
		return true;
	}

	// stage c, FAL-246: ClickCall=<script>.<function>, two Papyrus names of up to 64 letters, digits and '_' (no digit
	// first); "" = off. False if malformed
	bool ParseClickCall(std::string_view a_call)
	{
		const auto name = [](std::string_view a_name) {
			if (a_name.empty() || a_name.size() > kMaxName || (a_name[0] >= '0' && a_name[0] <= '9')) {
				return false;
			}
			for (const char c : a_name) {
				if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_')) {
					return false;
				}
			}
			return true;
		};
		if (a_call.empty()) {
			return true;
		}
		const auto dot = a_call.find('.');
		if (dot == std::string_view::npos || !name(a_call.substr(0, dot)) || !name(a_call.substr(dot + 1))) {
			return false;
		}
		g_clickScript = a_call.substr(0, dot);
		g_clickFunction = a_call.substr(dot + 1);
		return true;
	}

	// stage c: FlagSets=<n>,<n>,..., stages d and e: PageFlagSets (up to four, 0x.. or decimal); open k uses entry
	// (k - 1) mod count
	void ReadFlagSets(const std::filesystem::path& a_ini, const wchar_t* a_key, const wchar_t* a_default)
	{
		std::array<wchar_t, 256> text{};
		REX::W32::GetPrivateProfileStringW(L"FO4SFPipboyMenu", a_key, a_default, text.data(),
			static_cast<std::uint32_t>(text.size()), a_ini.c_str());
		const wchar_t* at = text.data();
		while (*at && g_flagSetCount < kMaxFlagSets) {
			wchar_t*   end = nullptr;
			const auto value = std::wcstoul(at, &end, 0);
			if (end == at) {
				break;
			}
			g_flagSets[g_flagSetCount++] = static_cast<std::uint32_t>(value);
			at = end;
			while (*at == L',' || *at == L' ') {
				++at;
			}
		}
	}

	// FAL-852: an idle's editor id or an event's name from the ini: 1 to 96 letters, digits and '_'
	bool ArmName(std::string_view a_name)
	{
		return !a_name.empty() && a_name.size() <= kMaxIdleName && std::all_of(a_name.begin(), a_name.end(), [](char c) {
			return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_';
		});
	}

	// FAL-852, the arm (Stage=2 with Movie= only): at Arm=0 nothing more is read and nothing is logged. At Arm=1 Key (not
	// F10, the owner's faction device; not F5 or F9, the game's Quick Save and Quick Load; not WorldKey), the raise idle,
	// the lower (an idle or an event, at most one) and the three times (0 to 6000 ms) are checked, and any wrong one is
	// refused as the other ini checks are
	bool ReadArm(const std::filesystem::path& a_ini)
	{
		if (ReadNumber(a_ini, L"Arm", 0) == 0) {
			return true;
		}
		if (g_stage != 2 || g_movie.empty()) {
			return Refuse("ini", std::format("reason=arm_stage stage={} movie={} (Arm=1 with Stage=2 and Movie= only)", g_stage,
				g_movie.empty() ? "-" : g_movie));
		}
		const auto worldKey = ReadNumber(a_ini, L"WorldKey", 0x77);
		if (g_key == kF10 || g_key == kQuickSaveKey || g_key == kQuickLoadKey || g_key == worldKey) {
			return Refuse("ini", std::format("reason=arm_key key={} world_key={} (at Arm=1 the screen has its own key: not F10, "
				"the faction device; not F5 or F9, the game's Quick Save and Quick Load; not WorldKey)", Hex(g_key), Hex(worldKey)));
		}
		g_armRaiseIdle = ReadText(a_ini, L"ArmRaiseIdle");
		g_armLowerIdle = ReadText(a_ini, L"ArmLowerIdle");
		g_armLowerEvent = ReadText(a_ini, L"ArmLowerEvent");
		if (!ArmName(g_armRaiseIdle) || (!g_armLowerIdle.empty() && !ArmName(g_armLowerIdle)) ||
			(!g_armLowerEvent.empty() && !ArmName(g_armLowerEvent)) || (!g_armLowerIdle.empty() && !g_armLowerEvent.empty())) {
			return Refuse("ini", std::format("reason=arm_idle raise={} lower_idle={} lower_event={} (the raise an editor id; at "
				"most one of ArmLowerIdle and ArmLowerEvent; letters, digits, _)", g_armRaiseIdle.empty() ? "-" : g_armRaiseIdle,
				g_armLowerIdle.empty() ? "-" : g_armLowerIdle, g_armLowerEvent.empty() ? "-" : g_armLowerEvent));
		}
		g_armRaiseMs = ReadNumber(a_ini, L"ArmRaiseMs", 2000);
		g_armLowerMs = ReadNumber(a_ini, L"ArmLowerMs", 3500);
		g_armRetryMs = ReadNumber(a_ini, L"ArmRetryMs", 2000);
		if (g_armRaiseMs > kMaxArmMs || g_armLowerMs > kMaxArmMs || g_armRetryMs > kMaxArmMs) {
			return Refuse("ini", std::format("reason=arm_ms raise_ms={} lower_ms={} retry_ms={} (0 to {})", g_armRaiseMs, g_armLowerMs,
				g_armRetryMs, kMaxArmMs));
		}
		g_arm = true;
		REX::INFO("step=load_arm key={} raise_idle={} lower={} raise_ms={} lower_ms={} retry_ms={} flags={}", Hex(g_key),
			g_armRaiseIdle, !g_armLowerIdle.empty() ? "idle:" + g_armLowerIdle : !g_armLowerEvent.empty() ? "event:" + g_armLowerEvent : "none",
			g_armRaiseMs, g_armLowerMs, g_armRetryMs, Hex(g_flags));
		return true;
	}

	// FAL-852 & Step 8, Arm=1: checks TESForm::LookupByEditorID (47403), Actor.PlayIdle helper (102136), and PlayIdle
	// context getter (35720) in versionlib-1-16-244-0.bin and against libxse REL::ID
	bool CheckArmId(const std::filesystem::path& a_file)
	{
		std::ifstream in(a_file, std::ios::binary);
		std::uint32_t count = 0;
		in.seekg(92);   // libxse HEADER_V5: the offset count (ReadAddressLibrary checked the header)
		in.read(reinterpret_cast<char*>(&count), sizeof count);
		if (!in) {
			return Refuse("arm_id", "name=header reason=short_file");
		}
		struct ArmIdSpec
		{
			const char*    name;
			std::uint32_t  id;
			const char*    source;
			std::uint32_t* out;
		};
		const std::array<ArmIdSpec, 5> specs{ {
			{ "TESForm.LookupByEditorID", kLookupByEditorId, "libxse", &g_armLookupRva },
			{ "Actor.PlayIdle", kActorPlayIdleId, "verified", &g_armPlayIdleRva },
			{ "Actor.PlayIdleContext", kPlayIdleContextId, "verified", &g_armPlayIdleCtxRva },
			{ "BSTEventSource.RegisterSink", kRegisterSinkId, "libxse", &g_armRegSinkRva },
			{ "BSTEventSource.UnregisterSink", kUnregisterSinkId, "libxse", &g_armUnregSinkRva },
		} };
		for (const auto& s : specs) {
			if (s.id >= count) {
				return Refuse("arm_id", std::format("name={} id={} reason=beyond_count count={}", s.name, s.id, count));
			}
			std::uint32_t offset = 0;
			in.seekg(static_cast<std::streamoff>(kHeaderBytes + 4ull * s.id));
			in.read(reinterpret_cast<char*>(&offset), sizeof offset);
			if (!in || !offset || offset >= g_imageSize) {
				return Refuse("arm_id", std::format("name={} id={} rva={} reason={}", s.name, s.id,
					Hex(offset), !in ? "short_file" : !offset ? "missing" : "outside_image"));
			}
			const auto viaLibrary = REL::ID(s.id).offset();
			if (viaLibrary != offset) {
				return Refuse("arm_id", std::format("name={} id={} reason=library_mismatch file={} libxse={}",
					s.name, s.id, Hex(offset), Hex(viaLibrary)));
			}
			*s.out = offset;
			REX::INFO("step=arm_id name={} id={} rva={} source={}", s.name, s.id, Hex(offset), s.source);
		}
		return true;
	}

	// Steps 1 & 6: at Stage=2 with CodeObj=1, check TESDataHandler/LookupByID/LookupByEditorID and ActorEquipManager
	// IDs + RTTIs in versionlib-1-16-244-0.bin before collecting stats or consuming Stimpak/RadAway
	bool CheckShellIds(const std::filesystem::path& a_file)
	{
		std::ifstream in(a_file, std::ios::binary);
		std::uint32_t count = 0;
		in.seekg(92);
		in.read(reinterpret_cast<char*>(&count), sizeof count);
		if (!in) {
			return Refuse("id", "name=shell_ids reason=short_file");
		}
		struct ShellIdSpec
		{
			const char*    name;
			std::uint32_t  id;
			std::uint32_t* out;
			std::uint32_t  expectedRva;
			const char*    rttiTail;
		};
		const std::array<ShellIdSpec, 8> specs{ {
			{ "TESDataHandler.Singleton", 937572, &g_rva[kDataHandlerSingleton], kDataHandlerRva, nullptr },
			{ "TESForm.LookupByID", 47401, &g_rva[kLookupById], kLookupByIdRva, nullptr },
			{ "TESForm.LookupByEditorID", kLookupByEditorId, &g_shellLookupEditorIdRva, 0, nullptr },
			{ "ActorEquipManager.Singleton", kEquipManagerSingletonId, &g_equipMgrSingletonRva, 0, nullptr },
			{ "ActorEquipManager.RTTI", kEquipManagerRttiId, &g_equipMgrRttiRva, 0, "ActorEquipManager@@" },
			{ "ActorEquipManager.EquipObject", kEquipObjectId, &g_equipObjectRva, 0, nullptr },
			{ "BGSObjectInstance.ctor", kObjectInstanceCtorId, &g_objInstanceCtorRva, 0, nullptr },
			{ "AlchemyItem.RTTI", kAlchemyItemRttiId, &g_alchemyRttiRva, 0, "AlchemyItem@@" },
		} };
		for (const auto& s : specs) {
			if (s.id >= count) {
				return Refuse("id", std::format("name={} id={} reason=beyond_count count={}", s.name, s.id, count));
			}
			std::uint32_t offset = 0;
			in.seekg(static_cast<std::streamoff>(kHeaderBytes + 4ull * s.id));
			in.read(reinterpret_cast<char*>(&offset), sizeof offset);
			if (!in || !offset || offset >= g_imageSize) {
				return Refuse("id", std::format("name={} id={} rva={} reason={}", s.name, s.id, Hex(offset),
					!in ? "short_file" : !offset ? "missing" : "outside_image"));
			}
			const auto viaLibrary = REL::ID(s.id).offset();
			if (viaLibrary != offset) {
				return Refuse("id", std::format("name={} id={} reason=library_mismatch file={} libxse={}", s.name, s.id,
					Hex(offset), Hex(viaLibrary)));
			}
			if (s.expectedRva && offset != s.expectedRva) {
				return Refuse("page_ids", std::format("name={} rva={} sfse_rva={}", s.name, Hex(offset), Hex(s.expectedRva)));
			}
			if (s.rttiTail) {
				const auto seen = TypeNameAt(g_base + offset);
				if (!NameIs(seen, s.rttiTail)) {
					return Refuse("channel_ids", std::format("name={} type={} expected=.?AV{}", s.name,
						seen.empty() ? "unreadable" : seen, s.rttiTail));
				}
			}
			*s.out = offset;
		}
		// A8: ActorEquipManager.UnequipObject (101951) is checked ONLY when InvDataAnswers=1 and stays optional so 1a
		// (InvDataAnswers=0) never depends on 101951 and missing 101951 skips unequip cleanly without aborting init.
		g_unequipObjectRva = 0;
		if (g_invDataAnswers) {
			std::uint32_t unequipOff = 0;
			bool          unequipOk = false;
			if (kUnequipObjectId < count) {
				in.seekg(static_cast<std::streamoff>(kHeaderBytes + 4ull * kUnequipObjectId));
				if (in.read(reinterpret_cast<char*>(&unequipOff), sizeof unequipOff) && unequipOff > 0 && unequipOff < g_imageSize &&
					REL::ID(kUnequipObjectId).offset() == unequipOff) {
					g_unequipObjectRva = unequipOff;
					unequipOk = true;
				}
			}
			REX::INFO("step=shell_optional_id name=ActorEquipManager.UnequipObject id={} rva={} status={}",
				kUnequipObjectId, Hex(g_unequipObjectRva), unequipOk ? "ok" : "unresolved");
		}
		g_shellExtraIdsReady = true;
		REX::INFO("step=shell_ids result=ok equip_mgr={} equip_obj={} lookup_edid={}",
			Hex(g_equipMgrSingletonRva), Hex(g_equipObjectRva), Hex(g_shellLookupEditorIdRva));
		return true;
	}

	// Round 11 Review #9: Optional non-fatal watch-hide channel ID resolver for Stage=2 when ChannelIdsNeeded() is false.
	// Never aborts plugin load: if channel IDs (MovieRoot RTTI + SFSE Value functions) are unavailable, logs
	// step=hud_watch_hide_init ok=0 reason=channel_ids_unavailable and disables ONLY HideStarfieldWatch while
	// FO4SFPipboyMenu.dll stays loaded.
	void TryInitHudWatchIds(const std::filesystem::path& a_file)
	{
		if (!g_hideStarfieldWatch) {
			return;
		}
		auto idsReady = [&]() -> bool {
			if (g_rva[kMovieRootRtti] == 0) {
				return false;
			}
			for (const auto& [id, rva] : kSfseRvas) {
				if (g_rva[id] != rva) {
					return false;
				}
			}
			return NameIs(TypeNameAt(Address(kMovieRootRtti)), "MovieRoot@AS3@GFx@Scaleform@@");
		};
		if (idsReady()) {
			REX::INFO("step=hud_watch_hide_init ok=1 source=channel_ids movie_root_rtti={}", Hex(g_rva[kMovieRootRtti]));
			return;
		}
		bool ok = false;
		std::ifstream in(a_file, std::ios::binary);
		if (in) {
			std::array<std::uint8_t, kHeaderBytes> head{};
			in.read(reinterpret_cast<char*>(head.data()), head.size());
			if (in) {
				const auto u32 = [&](std::size_t a_at) {
					std::uint32_t v;
					std::memcpy(&v, head.data() + a_at, sizeof v);
					return v;
				};
				const auto         format = u32(0);
				const REL::Version version{ static_cast<std::uint16_t>(u32(4)), static_cast<std::uint16_t>(u32(8)),
					static_cast<std::uint16_t>(u32(12)), static_cast<std::uint16_t>(u32(16)) };
				const auto         pointerSize = u32(84);
				const auto         count = u32(92);
				if (format == 5 && version == kRuntime && pointerSize == 8) {
					constexpr std::array<std::size_t, 6> kWatchIds{
						kMovieRootRtti, kValueAddRef, kValueRelease, kValueGetMember, kValueSetMember, kValueInvoke
					};
					std::array<std::uint32_t, 6> resolved{};
					ok = true;
					for (std::size_t i = 0; i < kWatchIds.size(); ++i) {
						const auto& id = kIds[kWatchIds[i]];
						if (id.id >= count) {
							ok = false;
							break;
						}
						std::uint32_t offset = 0;
						in.seekg(static_cast<std::streamoff>(kHeaderBytes + 4ull * id.id));
						in.read(reinterpret_cast<char*>(&offset), sizeof offset);
						if (!in || !offset || offset >= g_imageSize || REL::ID(id.id).offset() != offset) {
							ok = false;
							break;
						}
						resolved[i] = offset;
					}
					if (ok) {
						for (const auto& [id, rva] : kSfseRvas) {
							const auto it = std::ranges::find(kWatchIds, id);
							if (it == kWatchIds.end() || resolved[static_cast<std::size_t>(it - kWatchIds.begin())] != rva) {
								ok = false;
								break;
							}
						}
					}
					if (ok && !NameIs(TypeNameAt(g_base + resolved[0]), "MovieRoot@AS3@GFx@Scaleform@@")) {
						ok = false;
					}
					if (ok) {
						for (std::size_t i = 0; i < kWatchIds.size(); ++i) {
							g_rva[kWatchIds[i]] = resolved[i];
						}
					}
				}
			}
		}
		if (!ok) {
			g_hideStarfieldWatch = false;
			REX::WARN("step=hud_watch_hide_init ok=0 reason=channel_ids_unavailable");
		} else {
			REX::INFO("step=hud_watch_hide_init ok=1 source=optional_resolve movie_root_rtti={}", Hex(g_rva[kMovieRootRtti]));
		}
	}

	std::string WideToSafeAscii(const wchar_t* a_ws)
	{
		if (!a_ws) {
			return {};
		}
		std::string out;
		for (const wchar_t* p = a_ws; *p; ++p) {
			const auto wc = static_cast<unsigned int>(*p);
			out.push_back((wc >= 0x20 && wc < 0x7F) ? static_cast<char>(wc) : '?');
		}
		return out;
	}

	void TryInitQuestLabelRuntimeIds(const std::filesystem::path& a_file)
	{
		g_questLabelRuntimeIdsOk.store(false);
		std::ifstream in(a_file, std::ios::binary);
		if (!in) {
			REX::INFO("step=hud_quest_label_ids ok=0 reason=addrlib_unreadable");
			return;
		}
		std::array<std::uint8_t, kHeaderBytes> head{};
		in.read(reinterpret_cast<char*>(head.data()), head.size());
		if (!in) {
			REX::INFO("step=hud_quest_label_ids ok=0 reason=addrlib_header");
			return;
		}
		const auto u32 = [&](std::size_t a_at) {
			std::uint32_t v;
			std::memcpy(&v, head.data() + a_at, sizeof v);
			return v;
		};
		const auto         format = u32(0);
		const REL::Version version{ static_cast<std::uint16_t>(u32(4)), static_cast<std::uint16_t>(u32(8)),
			static_cast<std::uint16_t>(u32(12)), static_cast<std::uint16_t>(u32(16)) };
		const auto         pointerSize = u32(84);
		const auto         count = u32(92);
		if (format != 5 || version != kRuntime || pointerSize != 8) {
			REX::INFO("step=hud_quest_label_ids ok=0 reason=addrlib_version");
			return;
		}
		auto readChecked = [&](std::uint64_t a_id, std::uint32_t& a_outRva) -> bool {
			if (a_id >= count) {
				return false;
			}
			std::uint32_t offset = 0;
			in.seekg(static_cast<std::streamoff>(kHeaderBytes + 4ull * a_id));
			in.read(reinterpret_cast<char*>(&offset), sizeof offset);
			if (!in || !offset || offset >= g_imageSize || REL::ID(a_id).offset() != offset) {
				return false;
			}
			a_outRva = offset;
			return true;
		};
		std::uint32_t singletonRva = 0;
		std::uint32_t translateRva = 0;
		std::uint32_t rttiRva = 0;
		if (!readChecked(RE::ID::BSScaleformManager::Singleton.id(), singletonRva) ||
		    !readChecked(RE::ID::BSScaleformManager::Translate.id(), translateRva) ||
		    !readChecked(RE::RTTI::BSScaleformManager.id(), rttiRva)) {
			REX::INFO("step=hud_quest_label_ids ok=0 reason=id_lookup_failed");
			return;
		}
		if (!NameIs(TypeNameAt(g_base + rttiRva), "BSScaleformManager@@")) {
			REX::INFO("step=hud_quest_label_ids ok=0 reason=rtti_mismatch");
			return;
		}
		g_scaleformSingletonRva = singletonRva;
		g_scaleformTranslateRva = translateRva;
		g_scaleformRttiRva = rttiRva;
		g_questLabelRuntimeIdsOk.store(true);
		REX::INFO("step=hud_quest_label_ids ok=1 singleton={} translate={} rtti={}",
			Hex(singletonRva), Hex(translateRva), Hex(rttiRva));
	}

	void ProbeQuestLabelRuntime()
	{
		if (g_stage != 2 || !g_codeObj) {
			return;
		}
		if (!g_questLabelRuntimeIdsOk.load()) {
			REX::INFO("step=hud_quest_label_runtime file={} file_ok={} runtime_ok=0 reason=scaleform_ids_unavailable",
				g_translateStatus.filePresent ? "present" : "absent",
				g_translateStatus.fileOk ? 1 : 0);
			return;
		}
		const auto* singletonPtr = reinterpret_cast<RE::BSScaleformManager* const*>(g_base + g_scaleformSingletonRva);
		auto*       mgr = singletonPtr ? *singletonPtr : nullptr;
		if (!mgr) {
			REX::INFO("step=hud_quest_label_runtime file={} file_ok={} runtime_ok=0 reason=manager_null",
				g_translateStatus.filePresent ? "present" : "absent",
				g_translateStatus.fileOk ? 1 : 0);
			return;
		}
		using TranslateFn_t = RE::BSFixedStringW* (*)(RE::BSScaleformManager*, RE::BSFixedStringW*, const wchar_t*);
		const auto translateFn = reinterpret_cast<TranslateFn_t>(g_base + g_scaleformTranslateRva);
		RE::BSFixedStringW statusRes;
		RE::BSFixedStringW newRes;
		translateFn(mgr, std::addressof(statusRes), L"$MISSION STATUS");
		translateFn(mgr, std::addressof(newRes), L"$MissionNew");
		const std::string statusAscii = WideToSafeAscii(statusRes.c_str());
		const std::string newAscii = WideToSafeAscii(newRes.c_str());
		const bool        runtimeOk = !g_questLabelCfg.Active() ||
		                       (statusAscii.find(g_questLabelCfg.questHudLabel) != std::string::npos &&
		                        newAscii.find(g_questLabelCfg.questHudLabel) != std::string::npos);
		REX::INFO("step=hud_quest_label_runtime file={} file_ok={} mission_status={} mission_new={} runtime_ok={}",
			g_translateStatus.filePresent ? "present" : "absent",
			g_translateStatus.fileOk ? 1 : 0,
			statusAscii.empty() ? "-" : statusAscii,
			newAscii.empty() ? "-" : newAscii,
			runtimeOk ? 1 : 0);
	}
}

SFSE_PLUGIN_LOAD(const SFSE::LoadInterface* a_sfse)
{
	SFSE::Init(a_sfse, { .trampoline = false, .hook = false });

	std::array<wchar_t, 1024> exePath{};
	const auto exeLen = REX::W32::GetModuleFileNameW(nullptr, exePath.data(), static_cast<std::uint32_t>(exePath.size()));
	if (exeLen > 0 && exeLen < exePath.size()) {
		g_gameDir = std::filesystem::path(std::wstring(exePath.data(), exeLen)).parent_path();
	}
	std::array<wchar_t, 1024> path{};
	const auto len = REX::W32::GetModuleFileNameW(REX::W32::GetCurrentModule(), path.data(), static_cast<std::uint32_t>(path.size()));
	const auto dir = std::filesystem::path(std::wstring(path.data(), len)).parent_path();
	g_pluginDir = dir;
	const auto ini = dir / "FO4SFPipboyMenu.ini";
	g_setupShowUnavailable = ReadNumber(ini, L"SetupShowUnavailable", 0) != 0;
	g_stage = static_cast<int>(ReadNumber(ini, L"Stage", 0));
	g_key = ReadNumber(ini, L"Key", 0x79);
	g_flags = ReadNumber(ini, L"Flags", 0);
	g_keepAlive = ReadNumber(ini, L"KeepAlive", 1) != 0;
	g_movie = ReadText(ini, L"Movie");   // FAL-614: checked below, after the stage
	g_codeObj = ReadNumber(ini, L"CodeObj", 0) != 0;   // FAL-614 proof 1b: with Movie= only
	g_codeObjHide = ReadNumber(ini, L"CodeObjHide", 0) != 0;   // FAL-614 proof 1c: with CodeObj=1 only
	g_codeObjSound = ReadNumber(ini, L"CodeObjSound", 0) != 0;   // FAL-614 proof 1d: with CodeObj=1 only
	g_codeObjInit = ReadText(ini, L"CodeObjInit");   // FAL-614 proof 2a: with CodeObj=1 only
	const auto probe = ReadText(ini, L"CodeObjProbe");   // FAL-614 proof 2b-i: with CodeObj=1 only
	const auto calls = ReadText(ini, L"CodeObjCalls");   // FAL-614 proof 2b-ii: with CodeObj=1 only
	g_codeObjAt = ReadText(ini, L"CodeObjAt");   // FAL-614 S1-c: with CodeObj=1 only
	g_codeObjPages = ReadNumber(ini, L"CodeObjPages", 0) != 0;   // S1-c: with CodeObjAt= only
	g_populateInCall = ReadNumber(ini, L"PopulateInCall", 0) != 0;
	g_lateInvalidate = ReadNumber(ini, L"LateInvalidate", 0) != 0;
	g_statActions = ReadNumber(ini, L"StatActions", 0) != 0;
	g_invDataAnswers = ReadNumber(ini, L"InvDataAnswers", 0) != 0;
	const bool fo4ShellIni = (g_stage == 2 && g_codeObj && g_codeObjAt == "Menu_mc");
	g_shellBackdrop = ReadNumber(ini, L"ShellBackdrop", 1) != 0;
	g_shellVitalsFill = ReadNumber(ini, L"ShellVitalsFill", 0) != 0;
	g_suppressDataMenu = ReadNumber(ini, L"SuppressDataMenu", 0) != 0;
	g_tabOpensPipboy = ReadNumber(ini, L"TabOpensPipboy", 0) != 0;
	g_hideStarfieldWatch = ReadNumber(ini, L"HideStarfieldWatch", 0) != 0;
	g_requirePickup = ReadNumber(ini, L"RequirePickup", 0) != 0;
	const auto screenSourceRaw = ReadText(ini, L"ScreenSource");
	const auto screenSourceOpt = fo4sf::pipboy::ParseScreenSourceIni(screenSourceRaw);
	if (!screenSourceOpt.has_value()) {
		Refuse("ini", std::format("ScreenSource={} (expected 2d_imenu or 3d_rtt)", screenSourceRaw));
		return true;
	}
	g_screenSourceIni = *screenSourceOpt;
	g_questLabelCfg = fo4sf::hud::LoadQuestLabelConfig(ini);
	g_bootMovie = ReadText(ini, L"BootMovie");
	g_bootOnFirstOpen = ReadNumber(ini, L"BootOnFirstOpen", 0) != 0;
	g_specialMenu = ReadNumber(ini, L"SpecialMenu", 0) != 0;
	g_specialMovie = ReadText(ini, L"SpecialMovie");
	if (g_specialMenu && g_specialMovie.empty()) {
		g_specialMovie = "fo4sf_specialmenu";
	}
	g_specialMaxPoints = std::clamp(ReadNumber(ini, L"SpecialMaxPoints", 40), 7u, 70u);
	g_specialKey = ReadNumber(ini, L"SpecialKey", 0);
	const auto shellKeys = ReadText(ini, L"ShellKeys");   // S1-c: with CodeObj=1 only
	const auto special = ReadText(ini, L"CodeObjSpecial");   // FAL-1025: with CodeObjAt= only
	// FAL-414: up to four keyboard ids that close the menu while it is open (0 = unused)
	g_cancelCodes = { ReadNumber(ini, L"CancelCode1", 0x1B), ReadNumber(ini, L"CancelCode2", 0x09), ReadNumber(ini, L"CancelCode3", 0),
		ReadNumber(ini, L"CancelCode4", 0) };
	g_cancelCount = 4;
	while (g_cancelCount && g_cancelCodes[g_cancelCount - 1] == 0) {
		--g_cancelCount;
	}
	const auto runtime = a_sfse->RuntimeVersion();
	REX::INFO("step=load runtime={} stage={} key={} flags={} keep_alive={}", runtime.string(), g_stage, Hex(g_key),
		Hex(g_flags), g_keepAlive ? 1 : 0);

	// true in every case: a plugin that stays loaded and idle leaves its refusal line, the finding the job card reads
	if (g_stage < 1 || g_stage > 5) {
		REX::INFO("step=off (Stage=1, 2, 3, 4 or 5 in FO4SFPipboyMenu.ini to probe)");
		return true;
	}
	// FAL-614: Movie=<name>, 1 to 64 letters, digits and '_', with Stage=2 only (no channel, page or kit drives it)
	if (!g_movie.empty()) {
		const bool name = g_movie.size() <= 64 && std::ranges::all_of(g_movie, [](char a_c) {
			return (a_c >= 'A' && a_c <= 'Z') || (a_c >= 'a' && a_c <= 'z') || (a_c >= '0' && a_c <= '9') || a_c == '_';
		});
		if (!name || g_stage != 2) {
			Refuse("ini", std::format("movie={} (Stage=2 only; 1 to 64 letters, digits and _)", g_movie));
			return true;
		}
		REX::INFO("step=movie name={} file=Interface/{}.swf code_obj={}", g_movie, g_movie, g_codeObj ? 1 : 0);
	}
	if (g_codeObj && g_movie.empty()) {
		Refuse("ini", "code_obj=1 (with Movie= only: our own movie has no code)");
		return true;
	}
	if (g_codeObj && !ParseCodeObjNames(ReadText(ini, L"CodeObjNames"))) {
		return true;
	}
	if (g_codeObjHide && !g_codeObj) {
		Refuse("ini", "code_obj_hide=1 (with CodeObj=1 only)");
		return true;
	}
	// FAL-614 S1-c: CodeObjAt=<path> (one path, as CodeObjCalls=)
	std::array<std::string, kMaxCodeNames> atPath{};
	std::size_t                            atCount = 0;
	if (!g_codeObjAt.empty() && (!g_codeObj || !ParsePaths(g_codeObjAt, atPath, atCount, "code_obj_at") || atCount != 1)) {
		Refuse("ini", std::format("code_obj_at={} (with CodeObj=1 only; one path of letters, digits, _ and .)", g_codeObjAt));
		return true;
	}
	if (!g_bootMovie.empty()) {
		const bool bootOk = g_stage == 2 && g_bootMovie.size() <= kMaxName && std::ranges::all_of(g_bootMovie, [](char a_c) {
			return (a_c >= 'A' && a_c <= 'Z') || (a_c >= 'a' && a_c <= 'z') || (a_c >= '0' && a_c <= '9') || a_c == '_';
		});
		if (!bootOk) {
			Refuse("ini", std::format("boot_movie={} (Stage=2 only; 1 to 64 letters, digits and _)", g_bootMovie));
			return true;
		}
	}
	if (g_specialMenu) {
		const bool spMovieOk = g_stage == 2 && g_codeObj && !g_specialMovie.empty() && g_specialMovie.size() <= kMaxName &&
		                       std::ranges::all_of(g_specialMovie, [](char a_c) {
			                       return (a_c >= 'A' && a_c <= 'Z') || (a_c >= 'a' && a_c <= 'z') ||
			                              (a_c >= '0' && a_c <= '9') || a_c == '_';
		                       });
		const bool spKeyOk = (g_specialKey == 0) || (g_specialKey <= 0xFE && g_specialKey != g_key && g_specialKey != kF10);
		if (!spMovieOk || !spKeyOk) {
			Refuse("ini", std::format("special_menu=1 movie={} key={} (Stage=2 and CodeObj=1; valid movie name; key 0 or 0x01..0xFE != Key/F10)",
				g_specialMovie, Hex(g_specialKey)));
			return true;
		}
	}

	// FAL-614 proof 1d: CodeObjSound=1, with CodeObj=1 and PlaySound among its names
	if (g_codeObjSound && (!g_codeObj || std::ranges::find(g_codeObjNames.begin(), g_codeObjNames.begin() + g_codeObjCount,
	                                         std::string("PlaySound")) == g_codeObjNames.begin() + g_codeObjCount)) {
		Refuse("ini", "code_obj_sound=1 (with CodeObj=1 and PlaySound in CodeObjNames only)");
		return true;
	}
	// FAL-614 proof 2a: CodeObjInit=<name>, 1 to 64 letters, digits and '_', with CodeObj=1 only
	if (!g_codeObjInit.empty() && (!g_codeObj || g_codeObjInit.size() > kMaxName || !std::ranges::all_of(g_codeObjInit, [](char a_c) {
			return (a_c >= 'A' && a_c <= 'Z') || (a_c >= 'a' && a_c <= 'z') || (a_c >= '0' && a_c <= '9') || a_c == '_';
		}))) {
		Refuse("ini", std::format("code_obj_init={} (with CodeObj=1 only; 1 to 64 letters, digits and _)", g_codeObjInit));
		return true;
	}
	if (!probe.empty() && !g_codeObj) {
		Refuse("ini", std::format("code_obj_probe={} (with CodeObj=1 only; 1 to {} paths of letters, digits, _ and .)", probe,
			kMaxCodeNames));
		return true;
	}
	if (!calls.empty() && !g_codeObj) {
		Refuse("ini", std::format("code_obj_calls={} (with CodeObj=1 only; 1 to {} paths of letters, digits, _ and .)", calls,
			kMaxCodeNames));
		return true;
	}
	if (!ParsePaths(probe, g_probeNames, g_probeCount, "code_obj_probe") ||
		!ParsePaths(calls, g_rootCallNames, g_rootCallCount, "code_obj_calls")) {
		return true;
	}
	const auto named = [](const char* a_name) {
		return std::ranges::find(g_codeObjNames.begin(), g_codeObjNames.begin() + g_codeObjCount, std::string(a_name)) !=
		       g_codeObjNames.begin() + g_codeObjCount;
	};
	if (g_codeObjPages && (g_codeObjAt.empty() || !named("onNewPage") || !named("onNewTab"))) {
		Refuse("ini", "code_obj_pages=1 (with CodeObjAt= and onNewPage and onNewTab in CodeObjNames only)");
		return true;
	}
	// FAL-1025: CodeObjSpecial=fill or clear (with CodeObjAt= only), <CodeObjAt>.DataObj.SPECIALList made safe before each
	// InvalidateData the plugin calls (SpecialReady)
	if (!special.empty()) {
		if ((special != "fill" && special != "clear") || g_codeObjAt.empty()) {
			Refuse("ini", std::format("code_obj_special={} (fill or clear, with CodeObjAt= only)", special));
			return true;
		}
		g_codeObjSpecial = special == "fill" ? kSpecialFill : kSpecialClear;
		REX::INFO("step=code_obj_special_ini mode={} list={}.DataObj.SPECIALList", special, g_codeObjAt);
	}
	if (!shellKeys.empty() && !g_codeObj) {
		Refuse("ini", std::format("shell_keys={} (with CodeObj=1 only)", shellKeys));
		return true;
	}
	if (!ParseShellKeys(shellKeys)) {
		return true;
	}
	if (g_codeObj) {
		std::string keys;
		for (std::size_t i = 0; i < g_shellKeyCount; ++i) {
			keys += std::format("{}{}:{}", i ? "," : "", Hex(g_shellKeys[i].vk), g_shellKeys[i].path);
		}
		REX::INFO("step=code_obj_shell at={} pages={} names_count={} shell_keys={}", g_codeObjAt.empty() ? "none" : g_codeObjAt,
			g_codeObjPages ? 1 : 0, g_codeObjCount, keys.empty() ? "none" : keys);
		if (fo4ShellIni) {
			REX::INFO("step=shell_c4_config shell_backdrop={} shell_vitals_fill={} suppress_data_menu={} tab_opens_pipboy={} hide_starfield_watch={}",
				g_shellBackdrop ? 1 : 0, g_shellVitalsFill ? 1 : 0, g_suppressDataMenu ? 1 : 0, g_tabOpensPipboy ? 1 : 0,
				g_hideStarfieldWatch ? 1 : 0);
		}
		REX::INFO("step=pipboy_screen_source mode={}", fo4sf::pipboy::ScreenSourceModeName(g_screenSourceIni));
		const auto dataDir = !g_gameDir.empty() ? (g_gameDir / "Data") : dir.parent_path().parent_path();
		g_translateStatus = fo4sf::hud::VerifyTranslateEnFile(dataDir, g_questLabelCfg);
		REX::INFO("{}", fo4sf::hud::FormatStartupLog(g_questLabelCfg, g_translateStatus));
	}
	if (g_codeObjSound) {
		g_soundDir = dir / kSoundFolder;
		REX::INFO("step=code_obj_sound folder={} max_playing={}", kSoundFolder, kMaxSoundsPlaying);
	}
	std::string clickCall;
	bool        clickCallOk = true;
	bool        pause = false;
	if (g_stage >= 3) {
		g_snapshotKey = ReadNumber(ini, L"SnapshotKey", 0x7A);
		if (g_stage >= 4) {   // (d) and (e)
			ReadFlagSets(ini, L"PageFlagSets", L"0x19");   // FAL-414: bit 4 (0x10) puts StopContextProcessing (78) on the control map stack, so Tab arrives as Cancel
			pause = ReadNumber(ini, L"Pause", 0) != 0;     // FAL-446, the owner's setting: 1 adds bit 1 (0x2), which paused the game in the PC's sweep
			for (std::size_t i = 0; pause && i < g_flagSetCount; ++i) {
				g_flagSets[i] |= kPauseFlag;
			}
		} else {
			ReadFlagSets(ini, L"FlagSets", L"0x0,0x8,0x9");
			clickCall = ReadText(ini, L"ClickCall");
			clickCallOk = ParseClickCall(clickCall);
		}
		std::string sets;
		for (std::size_t i = 0; i < g_flagSetCount; ++i) {
			sets += std::format("{}{}", i ? "," : "", Hex(g_flagSets[i]));
		}
		REX::INFO("step=load_{} flag_sets={} pause={} snapshot_key={} click_call={}", g_stage == 5 ? "e" : g_stage == 4 ? "d" : "c",
			sets.empty() ? "none" : sets, pause ? 1 : 0, Hex(g_snapshotKey), clickCall.empty() ? "none" : clickCall);
	}
	if (runtime != kRuntime) {
		Refuse("version", std::format("runtime={} expected={}", runtime.string(), kRuntime.string()));
		return true;
	}
	if (g_key == 0 || g_key > 0xFE) {
		Refuse("ini", std::format("key={}", Hex(g_key)));
		return true;
	}
	if (g_stage >= 3 && (g_snapshotKey > 0xFE || g_snapshotKey == g_key)) {
		Refuse("ini", std::format("snapshot_key={} key={}", Hex(g_snapshotKey), Hex(g_key)));
		return true;
	}
	if (!clickCallOk) {
		Refuse("ini", std::format("click_call={} (<script>.<function>: two Papyrus names, or empty)", clickCall));
		return true;
	}
	if (g_stage == 5 && (!ReadKitKeys(ini) || !ReadKit(ini))) {   // the kit's keys and pages, before any check of the game
		return true;
	}
	// FAL-852: Fallout 4's screen pauses the game as Fallout 4 does when Pause=1 (the owner's setting, read at stages d and
	// e above): the same bit 0x2, here in Flags
	if (g_stage == 2 && !g_movie.empty() && ReadNumber(ini, L"Pause", 0) != 0) {
		g_flags |= kPauseFlag;
		REX::INFO("step=load_b pause=1 flags={}", Hex(g_flags));
	}
	if (!ReadArm(ini)) {   // FAL-852: at Arm=0 (the default) nothing is read or logged
		return true;
	}
	if (!CheckEverything(dir)) {
		return true;
	}
	if (g_hideStarfieldWatch) {
		TryInitHudWatchIds(dir / "versionlib-1-16-244-0.bin");
	}
	if (g_stage == 2 && g_codeObj) {
		TryInitQuestLabelRuntimeIds(dir / "versionlib-1-16-244-0.bin");
	}
	if (g_stage == 2 && (g_codeObj || g_specialMenu) && !CheckShellIds(dir / "versionlib-1-16-244-0.bin")) {
		return true;
	}
	if (g_arm && !CheckArmId(dir / "versionlib-1-16-244-0.bin")) {
		return true;
	}
	World::Configure(ini, g_stage, g_key, g_base, g_imageSize);
	PipboyMap::Configure(ini, dir, g_stage, g_key, g_base, g_imageSize);
	const auto messaging = SFSE::GetMessagingInterface();
	g_task = SFSE::GetTaskInterface();
	if (!messaging || !g_task || !messaging->RegisterListener(&OnMessage)) {
		Refuse("listen", std::format("messaging={} task={}", messaging ? 1 : 0, g_task ? 1 : 0));
		return true;
	}
	if (const auto menus = SFSE::GetMenuInterface()) {
		menus->Register(&OnMovieCreated);
	}
	REX::INFO("step=listen (the menu registers on the first main-thread task after PostDataLoad)");
	return true;
}
