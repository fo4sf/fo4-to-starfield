"""Stage the Fallout 4 new game (docs/newgame/vault111-start.md): FO4SFNewGame.esm and its scripts, offline.

usage:
  python make_newgame.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only, no game: every native and event the four scripts use, looked up in Starfield's base sources
      (Scripts/Source of ContentResources.zip), and every source line naming MQ101Debug (how Starfield's debug start
      works). Exit 1 when a native of FO4SF_NewGameQuest is missing (do not stage); a missing native of the looks
      script (Game.ShowRaceMenu, the menu open/close event) only means --no-looks, one of the SPECIAL script
      (Actor.SetValue / GetValue) only --no-special, one of the version script (OnPlayerLoadGame) only --no-version.
  python make_newgame.py stage --out <dir> --fo4 <Fallout4.esm> --port <FO4Port.esm> --port-ids <formids.json>
                               --core <FO4TerrainCore.esm> [--starfield <Starfield.esm>] [--compiler <exe>]
                               [--content-resources <zip>] [--no-looks] [--race-menu-mode N] [--no-special]
                               [--no-version] [--build-version N] [--hold MQ00,MQ101,...] [--mq101debug N]
                               [--no-mq101debug] [--debug-after-hold N] [--pod-ref HEX] [--terminal-ref HEX]
                               [--keep-inventory | --vault-suit EDITORID] [--no-o2-fill] [--allow-temporary-anchor]
      1. dotnet/NewGame points (Fallout4.esm read only: the pod, the console, the cog door, the platform, the arrival,
         the cell's terminals);
      2. dotnet/NewGame write + check against the port and core given (offline_check.txt; its "vault anchor" line says
         whether the anchor is persistent or the temporary COC marker the script must center on first, and plan.json
         records that mode; a vault cell without a persistent reference is refused unless --allow-temporary-anchor);
      3. the Papyrus compile of FO4SF_NewGameQuest.psc (and FO4SF_NewGameLooks.psc unless --no-looks,
         FO4SF_NewGameSpecial.psc unless --no-special, FO4SF_NewGameVersion.psc unless --no-version);
      4. plan.json (the plugin's and scripts' SHA-256 and the port, its formids.json and the core it was checked
         against) and README.txt. Built in a new <out>.partial-<time>-<pid> and renamed to <out> only when every step
         passed; an existing <out> is refused.
  python make_newgame.py verify --exp-dir <dir> --plan <stage>\\plan.json [--port <FO4Port.esm>] [--core <FO4TerrainCore.esm>]
      the install preflight: the plugin and scripts in <exp-dir> are the staged ones; the port and core (in <exp-dir>,
      else the paths given) are the bytes the ids were checked against. Exit 1 on any mismatch: re-stage, do not install.
  python make_newgame.py fold --stage <stage dir> --core-dir <core experiment dir> --out <new dir>
      exp_install.py holds one experiment, so the new game goes in WITH a core set: a copy of it plus the plugin and its
      .pex, published only after verify passes on the result. Its README.txt is the core's with every exp_install.py
      install line naming EVERY plugin (the core's and FO4SFNewGame.esm, --pack), then the stage's README: the
      installer activates only the plugins listed (none listed: the first .esm alphabetically), so the core's own
      command would never install the new game.
  python make_newgame.py log [--file <fo4sf_newgame.0.log>]
      the run's user log as a summary (the start events that came, stages by the contract below, a hand back to
      Starfield's start, the fade in, held-off quests by pass, what ended the looks wait, the SPECIAL ending, the save
      version lines, the inventory reset, the centering of a temporary-anchor start, moves, the landing); exit 0 when
      stage 200 was reached.
Nothing here installs anything: the install is the owner's line, to the install session, after the current test.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "src"))
from fo4sf.core.core_values import CORE_VALUES_PLUGIN, core_form_id  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "NewGame")
PROGRESSION_SCRIPTS = os.path.join(REPO, "scripts", "progression")
SURVIVAL_SCRIPTS = os.path.join(REPO, "scripts", "survival")
REPUTATION_SCRIPTS = os.path.join(REPO, "scripts", "reputation")
MAPMARKERS_SCRIPTS = os.path.join(REPO, "scripts", "mapmarkers")
PLUGIN = "FO4SFNewGame.esm"
SCRIPT = "FO4SF_NewGameQuest"
LOOKS = "FO4SF_NewGameLooks"
SPECIAL = "FO4SF_NewGameSpecial"
VERSION = "FO4SF_NewGameVersion"
# The stage contract (NG-14): the stages FO4SF_NewGame publishes for later phases and other mods to listen to, with
# what each means. FO4SF_NewGameQuest.psc's header lists the same lines and tests/test_newgame.py holds them equal;
# docs/newgame/vault111-start.md section 9 is the published table. Stage 0 is the quest's start, not a QUST record.
STAGE_CONTRACT = {
    0: "started: as Starfield's startup quest, the guard, the move into the vault and the hold-off",
    1: "stood down: not a new game, or no move into the vault (Starfield's opening is asked to start if the game still loads)",
    5: "mode chosen: start mode and survival choice stored",
    10: "in the vault: the player stands at their pod",
    20: "looks done: character creation closed, or LooksWait passed",
    30: "cog door opened: from its console",
    40: "on the surface: the elevator ride is over",
    200: "complete: landed, or put on the fallback spot",
    210: "warfare complete: landed at the faction start spot",
}
STAGES = tuple(n for n in STAGE_CONTRACT if n > 0)           # the QUST's stage records (Program.cs Stages)
# the writer's default hold-off list (Program.cs DefaultHold, held equal by tests/test_newgame.py): the opening quests
# and the two MQ101's stage 9000 starts when it is stopped (NG-19, NG-N1). MQ101Debug: see below. The first build's
# override of 10 was the developer start at the pirate fight (28 Oct run 1: opening_stage=250, our quest stood down);
# the second build's 2 matched no start and hung the first load (28 Oct run 2). MQ00's stage 10 writes 10 but is not a
# start-up stage, so vanilla never does. SQ_ENV (248D20) is Starfield's environment system for the player: its alias
# gives 17 ENV abilities (hazard and suit-integrity damage, the O2 adjustment, afflictions; PC read 15 Nov), so
# holding it off is S13 row 2b's first step to "no Starfield environment damage" (owner decision 15 Nov; unverified
# in game). Not SQ_ENV's: HumanRace's two ENV_AFFL hit-spell abilities and placed local hazards.
HOLD_CORE = ("MQ00", "MQ101", "MQ101PostQuest", "MQ_TutorialQuest_Misc04", "SQ_ENV")
# S13 row 5, the first group (owner 15 Nov, "Companions first"; Program.cs HoldCompanions, held equal by
# tests/test_newgame.py): Starfield's companion and crew quests found running in our new game (result-pc-read-s13-5-partb).
HOLD_COMPANIONS = ("COM_Companion_SarahMorgan", "COM_Companion_SarahMorgan_SpeechChallenges",
                   "COM_Companion_Shared_Sarah", "Com_Companion_Barrett", "COM_Companion_Barrett_SpeechChallenges",
                   "COM_Companion_Shared_Barrett", "COM_Companion_Andreja", "COM_Companion_Andreja_SpeechChallenges",
                   "COM_Companion_Shared_Andreja", "COM_Companion_SamCoe", "COM_Companion_SamCoe_SpeechChallenges",
                   "COM_Companion_SamCoe_Cora", "COM_Companion_Shared_SamCoe", "COM_System_PlayerSharedLines",
                   "SQ_Companions", "SQ_Crew", "CREW_EliteCrew_Heller", "CREW_GenericCrew")
# S13 row 5, the second group (owner 15 Nov, "keep going ... until stuff starts to break", least risky first; Program.cs
# HoldAudioTutorials): the running audio-log quests and the two tutorials.
HOLD_AUDIO_TUTORIALS = ("AudioLogsQuest", "AudioLogsQuest_KT", "AudioLogsQuest_RQ", "AudioLogsQuest_LVC",
                        "AudioLogsQuest_PS", "AudioLogsQuest_JM", "AudioLogsQuest_OB", "AudioLogsQuest_BB",
                        "AudioLogsQuest_FAB", "AudioLogsQuest_AN", "AudioLogsQuest_WJS", "AudioLogsQuest_CT",
                        "SQ_ENV_Tutorial", "OutpostTutorial")
# S13 row 5, the third group (city and faction dialogue; Program.cs HoldCityFaction): the running quests that serve one
# Starfield city, settlement or faction. Generic, ship and main-quest dialogue stay for later groups.
HOLD_CITY_FACTION = ("City_AkilaLife07", "DialogueConstellation", "DialogueCrimsonFleet", "DialogueUCNewAtlantis",
                     "DialogueHopetown_Shared", "CityNewAtlantisTransitControl", "DialogueTheFirstNPCs",
                     "DialogueUCNewAtlantisSecurity", "City_NA_Viewport_Base", "CF_Unique",
                     "UC03_DeepMinesSupportQuest", "DialogueUCNewAtlantis_Shared", "CF_Post",
                     "DialogueUCFactionAlwaysOn", "DialogueFCClinic_IntroPost", "City_GG_Bet_SupportQuest", "CF_Main",
                     "DialogueKaiser", "DialogueFCClinic", "UC08_SupportQuest", "DialogueRedDevilsHQ", "CFSD01",
                     "Dialogue1OfAKindUC07", "DialogueUCNewAtlantis_Argos", "City_Neon_Gang_Dialogue",
                     "DialogueTrackersAllianceAgents", "DialogueFCAkilaCity", "DialogueFCNeonEstablishingScene",
                     "DialogueFCNeon", "City_Neon_Chem_Shared", "DialogueNewHomestead", "DialogueFreestarRangers",
                     "DialogueCydonia", "DialogueUCInfinityLTD", "DialogueUCFactionCydonia", "DialogueParadiso",
                     "DialogueGagarin_UC_GG", "DialogueUCNewAtlantis_LandryHollifeld", "DialogueFCRyujinTower",
                     "DialogueECSConstant", "DialogueGenericHouseVaruun", "DialogueEleosRetreat",
                     "DialogueSeokguhSyndicate", "DialogueCrucible", "DialogueUCTheLodge", "Settlement_Convo_NA",
                     "DialogueUCNewAtlantis_NadiaMuffaz", "UC05_EmbassySupportQuest", "DialogueUCTheDen",
                     "DialogueHopeTown", "RI_Support", "UC02_PerrysMeatsSupportQuest", "DialogueRedMile",
                     "DialogueUCFactionNewAtlantis", "DialogueWaggonerFarm_IntroScene", "DialogueWaggonerFarm",
                     "DialogueNeonConvo_SecurityCheckpoint_Controller", "City_NA_GuardPointer_Well",
                     "City_NA_GuardPointer_Botany", "City_NA_GuardPointer_Viewport", "City_NA_GuardPointer_NA02",
                     "DialogueFCNeon_PlayerHomeQuest", "City_AC_FAB_Quest05", "City_AC_FAB_Quest03",
                     "City_AC_FAB_Quest01", "City_AC_FAB_Quest02", "City_AC_FAB_Quest04", "City_AC_FAB_Quest06",
                     "City_AC_FAB_Quest11", "City_AC_FAB_Quest09", "City_AC_FAB_Quest07", "City_AC_FAB_Quest08",
                     "City_AC_FAB_Quest10", "City_AC_FAB_Quest12", "City_AC_FAB_Quest16", "City_AC_FAB_Quest14",
                     "City_AC_FAB_Quest13", "City_AC_FAB_Quest15", "City_AC_FAB_Quest17", "City_AC_FAB_Quest19")
# S13 row 5, the fourth group (Program.cs HoldGenericDialogue, HoldActivities): the rest of Gemini's city and faction
# dialogue batches, then the rest of its activities and misc batches. Radiant, ships and system stay for later groups.
HOLD_GENERIC_DIALOGUE = ("DialogueCrowds", "DialgoueSSNNScenes", "CR_Dialogue_Turret",
                         "DialogueTerrormorphThrallHuman", "DialogueGeneric_LISTOutpost", "DialogueGenericSpacers",
                         "DialogueGenericUnique_Crime_TheKey", "DialogueGenericChildren",
                         "CR_Dialogue_Terrormorph_Base", "DialogueGenericStarborn_Unique", "CR_Dialogue_QuadrupedB",
                         "DialogueMiniBot", "DialogueSettleBartenderRumors", "DialogueCrimeGuards",
                         "MQ105_AlwaysOnDialogueNeon", "DialogueGenericVendor_Chunks",
                         "DialogueGenericVendor_Terrabrew", "Staryard_StroudEklund_Dialogue",
                         "Staryard_Taiyo_Dialogue", "Staryard_Deimos_Dialogue", "DialogueGenericEclipticANDSoldiers",
                         "DialogueGenericUnique_Combat", "Staryard_TridentLuxury_Dialogue", "DialogueGenericCitizens",
                         "DialogueGenericScum", "DialogueGenericGuards", "DialogueGenericRobotModelA",
                         "DialogueGenericStarborn", "DialogueGenericRobotModelS", "DialogueGenericUnique_Crime",
                         "LC082_SuspiciousActors", "DialogueStarstations")
HOLD_ACTIVITIES = ("MQ207C_AlwaysOn", "Trait_RaisedEnlightenedBoxEnabler", "Traits_Shared", "MQ207C_Support_Fix01",
                   "Trait_RaisedUniversalBoxEnabler", "MQ206B_AlwaysOn", "SQ_Doctors", "AspirationalItems", "MS04",
                   "Patch_Hotfix", "Patch_Update03_FixFollower", "StarbornTempleQuest",
                   "SkillMag_CyberRunner_Handler", "SQ_PEO_SustenanceDialogue", "Patch_Update05", "SQ_Hoteliers")
# S13 row 5, the fifth and final holdable group (Program.cs HoldRadiant, HoldShips, HoldSystem): the remaining 9
# radiant quests, 21 holdable ship quests and 4 Starfield-only system/trait quests. Leaves only the 5 Warfare squad
# quests and 7 core engine quests running out of the 207 cold-start quests.
HOLD_RADIANT = ("MB_Parent", "SQ_PlayerClearedReward", "SE_AC01", "RE_Parent", "RQ_Parent", "OE_Dialogue", "SEDebug",
                "Rad01_LIST", "RQ_Dialogue")
HOLD_SHIPS = ("DialogueCrimeGuardShips", "DialogueCrimsonFleetShips", "DialogueGenericCitizensShips_MuddledChatter",
              "DialogueGenericGuardsShips_MuddledChatter", "DialogueGenericVendor_LIST", "DialogueGenericPiracyShips",
              "DialogueGenericSpacersShips", "DialogueGenericStarbornShips_Unique", "DialogueShipServices",
              "SQ_ShipVendors", "DialogueGenericGuardsShips", "DialogueGenericHouseVaruunShips",
              "DialogueTheFirstShips", "SE_Player_Attack_SharedLines", "SQ_OutpostCargoLink",
              "DialogueGenericCitizensShips", "DialogueGenericEclipticANDSoldierShips", "DialogueGenericScumShips",
              "DialogueGenericStarbornShips", "DialogueGenericUCGuardsShips", "SQ_CargoShips")
HOLD_SYSTEM = ("SQ_GravitationalTraits", "SQ_Traits", "SQ_ApplyVoices_OBSOLETE", "LDMasterQuest")
DEFAULT_HOLD = (HOLD_CORE + HOLD_COMPANIONS + HOLD_AUDIO_TUTORIALS + HOLD_CITY_FACTION + HOLD_GENERIC_DIALOGUE
                + HOLD_ACTIVITIES + HOLD_RADIANT + HOLD_SHIPS + HOLD_SYSTEM)
OMIT_HOLD_GROUPS = {
    "radiant": tuple(q for q in DEFAULT_HOLD if q not in set(HOLD_RADIANT)),
    "ships": tuple(q for q in DEFAULT_HOLD if q not in set(HOLD_SHIPS)),
    "system": tuple(q for q in DEFAULT_HOLD if q not in set(HOLD_SYSTEM)),
}
# GLOB MQ101Debug (Starfield.esm 0A7D31) at the start: the build overrides it NOT AT ALL by default (None). Each of MQ101's
# stage-0 entries that matches moves the player into the game (the intro's Item_02: moveto CharGenStartMarker, then
# WaitFor3dLoad); a value no entry matches moves nobody and the new game never leaves its loading screen (28 Oct run 2,
# value 2: the quest started, its version alias logged, but OnQuestInit never fired). With our own start (the plugin's
# StartupQuest_DO override, the owner's pick F) MQ101 never runs; the quest writes DEBUG_AFTER_HOLD (the value the main
# quests' developer skip-start stages write; a normal intro leaves 0) right after the hold-off's first pass, once the
# player has been moved, which opens PEO_SustenanceAllowed's "MQ101Debug != 0" (its normal route, MQ101 stage 310, is
# never reached); --debug-after-hold, 0 writes nothing.
DEFAULT_MQ101DEBUG = None
DEBUG_AFTER_HOLD = 2
DEBUG_INTRO = 0               # Starfield's own intro, entry 2
DEBUG_START_PIRATES = 10      # the first build's value: Fragment_Stage_0000_Item_10, SetStage 210 and 250 (28 Oct run 1)
DEBUG_UNMATCHED = 2           # the second build's value: no entry, no move, an endless loading screen (28 Oct run 2)
# Game.ShowRaceMenu's uiMode (Program.cs DefaultRaceMenuMode, the looks script's RaceMenuMode). FULL_CREATOR_MODE (0)
# is the full creator, with Starfield's Background and Traits pages. The owner chose a looks-only creator (NG-C3) and
# the strip-down rule takes Starfield's own new-game content out (system model S13), so the default is 2, the mode the
# C1 session saw as looks-only (15 Nov, owner PC: mode 2 opened the "Enhance!" creator with only BODY and FACE, closed
# by the ChargenMenu event, stage 20; mode 1 still showed TRAITS). --race-menu-mode 0 builds the old full creator.
FULL_CREATOR_MODE = 0
DEFAULT_RACE_MENU_MODE = 2
# SPECIAL at the vault terminal (NG-5 / NG-C4; Program.cs SpecialNames, SpecialExtraButtons, SpecialBase, SpecialPoints,
# SpecialMax and the SPECIAL script's defaults, held equal by tests/test_newgame.py): Fallout 4's rule, 1 in each stat,
# 21 points to spend, 10 at most in one stat. SPECIAL_BUTTONS is the allocation message's button order, the index
# Message.Show returns; special_press is the script's rule for one press, tested in Python. SPECIAL_MAX_PRESSES is the
# script's MaxPresses: the allocation ends as Leave after that many presses without Confirm or Leave (about 22 per
# pass; the guard against a message box that returns at once).
SPECIAL_STATS = ("Strength", "Perception", "Endurance", "Charisma", "Intelligence", "Agility", "Luck")
SPECIAL_AVIF_IDS = tuple(core_form_id(f"FO4SF_Special_{s}") for s in SPECIAL_STATS)
TEST_MODE_GLOBAL_ID = core_form_id("FO4SF_TestModeEnabled")
SPECIAL_BUTTONS = SPECIAL_STATS + ("Reset", "Confirm", "Leave")
SPECIAL_PAGE1_BUTTONS = ("Strength", "Perception", "Endurance", "Next (C / I / A / L)", "Reset", "Confirm", "Leave")
SPECIAL_PAGE2_BUTTONS = ("Charisma", "Intelligence", "Agility", "Luck", "Back (S / P / E)", "Confirm", "Leave")
SPECIAL_BASE, SPECIAL_POINTS, SPECIAL_MAX = 1, 21, 10
SPECIAL_MAX_PRESSES = 300
# The save version check (NG-15 / NG-L2; Program.cs DefaultBuildVersion, held equal by tests/test_newgame.py): the
# build's version number, written to GLOB FO4SF_NewGameVersion (constant) and recorded by the version script when a new
# game starts; on every load the script compares the two and logs "version load saved=<n> installed=<n>", then "version
# mismatch" and a notification when they differ. --build-version sets another number; bump it when a save made under
# the old build must not go on under the new one.
DEFAULT_BUILD_VERSION = 1
# Default pod stand step (Program.cs DefaultPodStep = -2.5f): steps 2.5 m along -Y out of REFR 0004A011 onto
# (9.143, -6.614, -1.029) m (walkable on PC, settle drop 0.12 m); heading stays 0 (do not turn the pod).
DEFAULT_POD_STEP = -2.5
# The starting inventory reset (NG-K8 / NG-N3; Program.cs DefaultClearInventory, held equal by tests/test_newgame.py):
# ON by default since S13 row 2: the strip-down rule takes Starfield's own new-game items (outfit, gear, credits) out,
# as FO4's MQ101 empties the inventory, and what Starfield leaves when MQ101 never runs is unresolved (run 4). The
# quest script calls RemoveAllItems (FO4's arguments; Starfield's third parameter is abRespectTargetCapacity, so
# whether quest items stay is unverified) once the player is in the vault and logs "inventory cleared removed=<n>
# left=<n>"; --vault-suit <EditorID> names the port's ARMO the script then adds and equips ("vault suit equipped
# ..."), resolved offline by the writer with the same owner checks as the other ids. Until the port has a vault suit
# the player starts with nothing. --keep-inventory builds the old start (Starfield's items kept); --clear-inventory
# (the default now) is kept for old command lines.
DEFAULT_CLEAR_INVENTORY = True
# The O2/CO2 dial with no suit (S13 row 2b; Program.cs DefaultO2Fill, held equal by tests/test_newgame.py): with the
# reset the quest tops 0002E2 (a pack's O2 capacity) up to 100 with ModValue right after it, which clears the dial
# (PC, 15 Nov), and logs "o2 capacity added=<n> value=<n>". --no-o2-fill leaves it out; --keep-inventory has none.
DEFAULT_O2_FILL = True
# The vault anchor's mode (Program.cs DefaultRequirePersistentAnchor, held equal by tests/test_newgame.py). The port
# installed on 21 Oct had no persistent reference in FO4Port_Vault111Cryo (0 of 1,166; its COC marker 001338 and every
# terminal temporary), and a temporary reference of an unloaded cell resolves to None (verified 16 Oct), so the writer
# can anchor on the temporary COC marker and have the quest script load the cell first (Debug.CenterOnCell, the
# AnchorTemporary / VaultCell properties). The port of run 3 (28 Oct) has the marker persistent. Since newgame_v11 the
# temporary mode is refused by default: its centering comes during our own start's first load, and when it moves nobody
# the start hands nothing back (29 Oct review on #588); --allow-temporary-anchor builds it on request, and
# --require-persistent-anchor (the default now) is kept for old command lines. check prints the mode after the anchor
# ("vault anchor FO4Port.esm:<id> persistent|temporary"), anchor_mode reads it into plan.json.
DEFAULT_REQUIRE_PERSISTENT_ANCHOR = True
ANCHOR_LINE = re.compile(r"vault anchor FO4Port\.esm:(?P<id>[0-9A-Fa-f]+) (?P<mode>persistent|temporary)\b")
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User",
                   "fo4sf_newgame.0.log")
LINE = re.compile(r"FO4SF_NEWGAME rt=(?P<rt>[-\d.]+) (?P<msg>.*)$")
# the natives each script calls and the events it handles, by the base script that must declare them (precheck).
# Events are declarations too (Event OnMenuOpenCloseEvent in ScriptObject.psc), looked up the same way.
NATIVES = {
    # the inventory reset (ClearInventory, on by default) calls RemoveAllItems, GetItemCount, AddItem, EquipItem and
    # IsEquipped with FO4's signatures; whether Starfield's declare them the same way is what this precheck reads. The
    # temporary-anchor mode calls Debug.CenterOnCell(string) (FO4's signature; Starfield's Debug.psc declares it too,
    # read in ContentResources.zip 29 Oct; whether it works in retail is unverified until the PC run).
    # Our own start: the events OnQuestStarted and OnQuestInit on Quest (Roleplayers' Alternate Start handles the first on
    # its startup quest), Game.FadeOutGame (its five-argument call), ObjectReference.WaitFor3DLoad (MQ101's own intro
    # waits so), Quest.StartNoWait and IsStarting (the hand back to MQ101, which waits for nothing)
    SCRIPT: {
        "Actor": ["GetLevel", "EquipItem", "IsEquipped", "ModValue", "GetValue", "AddToFaction", "OnPlayerLoadGame"],
        "Debug": ["OpenUserLog", "TraceUser", "Notification", "CenterOnCell"],
        "Game": ["GetPlayer", "GetFormFromFile", "SetInChargen", "SetCharGenHUDMode", "FadeOutGame", "IsFastTravelEnabled", "ShowRaceMenu", "ShowFirstPersonGeometry"],
        "GlobalVariable": ["GetValue", "SetValueInt", "SetValue"],
        "InputEnableLayer": ["Create", "EnableHandscanner"],
        "Message": ["Show"],
        "ObjectReference": ["MoveTo", "SetPosition", "SetAngle", "GetPositionX", "GetParentCell", "GetWorldSpace",
                            "IsInInterior", "Is3DLoaded", "WaitFor3DLoad", "GetOpenState", "SetOpen", "RemoveAllItems",
                            "GetItemCount", "AddItem", "GetFormID", "GetPositionY", "GetPositionZ", "GetAngleZ",
                            "SetMarkerDiscovered", "GetBaseObject", "PlayAnimation", "Enable", "DisableNoWait",
                            "BlockActivation", "OnActivate", "OnItemAdded"],
        "Quest": ["SetStage", "GetStage", "IsRunning", "IsStarting", "StartNoWait", "Stop", "CompleteQuest",
                  "SetObjectiveDisplayed", "SetObjectiveCompleted", "SetActive", "OnQuestStarted", "OnQuestInit", "OnStageSet"],
        "ScriptObject": ["StartTimer", "RegisterForAnimationEvent", "UnregisterForAnimationEvent", "OnAnimationEvent",
                         "RegisterForRemoteEvent", "UnregisterForRemoteEvent", "AddInventoryEventFilter",
                         "RegisterForMenuOpenCloseEvent", "UnregisterForMenuOpenCloseEvent", "OnMenuOpenCloseEvent"],
        "Utility": ["GetCurrentRealTime", "Wait"],
    },
    LOOKS: {
        "Debug": ["TraceUser"],
        "Game": ["ShowRaceMenu", "GetPlayer"],
        "Message": ["Show"],
        "ObjectReference": ["GetPositionX", "GetPositionY", "GetPositionZ", "GetAngleZ", "Is3DLoaded", "GetParentCell", "GetWorldSpace"],
        "Quest": ["SetStage", "GetStage", "OnQuestStarted", "OnQuestInit"],
        "ScriptObject": ["StartTimer", "RegisterForMenuOpenCloseEvent", "OnMenuOpenCloseEvent"],
        "Utility": ["Wait", "GetCurrentRealTime"],
    },
    # Actor.SetValue(ActorValue, float) / GetValue(ActorValue) are FO4's; whether Starfield's Actor.psc declares them
    # the same way is what this precheck reads (unverified until then)
    SPECIAL: {
        "Actor": ["SetValue", "GetValue"],
        "Debug": ["TraceUser", "Notification"],
        "Game": ["GetPlayer", "GetFormFromFile"],
        "Message": ["Show"],
        "ObjectReference": ["GetPositionX", "IsInInterior"],
        "Quest": ["GetStage", "OnQuestStarted", "OnQuestInit"],
        "ScriptObject": ["StartTimer"],
        "Utility": ["GetCurrentRealTime"],
    },
    # OnPlayerLoadGame is declared on ReferenceAlias (PC read 19 Oct, NG-L3); OnInit on ScriptObject is where the
    # script records the version when the alias fills
    VERSION: {
        "Debug": ["OpenUserLog", "TraceUser", "Notification"],
        "GlobalVariable": ["GetValue"],
        "ReferenceAlias": ["OnPlayerLoadGame"],
        "ScriptObject": ["OnInit"],
        "Utility": ["GetCurrentRealTime"],
    },
}
# the optional scripts: the stage option that drops each, and the precheck's advice when a native is missing
OPTIONAL = {LOOKS: "--no-looks", SPECIAL: "--no-special", VERSION: "--no-version"}


def run(cmd, cwd=None, check=True):
    print("+ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stdout.write(r.stderr)
        if check:
            sys.exit(f"{os.path.basename(cmd[0])} exit {r.returncode}")
    return r


def read_text(path):
    """The file's text, "" when there is none (a core set or stage without a README)."""
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def special_press(values, left, button, base=SPECIAL_BASE, points=SPECIAL_POINTS, maximum=SPECIAL_MAX):
    """FO4SF_NewGameSpecial.Allocate's rule for one press of SPECIAL_BUTTONS[button] on (values, left): the new
    (values, left, ending), ending None while the message shows again, "set" on Confirm with every point spent,
    "left" on Leave (or a closed message, button -1). A stat button with no points left or the stat at the maximum
    changes nothing; Confirm with points left changes nothing."""
    values = list(values)
    name = SPECIAL_BUTTONS[button] if 0 <= button < len(SPECIAL_BUTTONS) else "Leave"
    if name in SPECIAL_STATS:
        if left > 0 and values[button] < maximum:
            values[button] += 1
            left -= 1
        return values, left, None
    if name == "Reset":
        return [base] * len(SPECIAL_STATS), points, None
    if name == "Confirm":
        return values, left, "set" if left == 0 else None
    return values, left, "left"


# the guard's day limit (FO4SF_NewGameQuest MaxNewGameDays, held equal by tests/test_newgame.py). Starfield's clock
# starts at GameHour 8 (the record's value, docs/ai/test-queue.md) and GameDaysPassed carries the hour, so a new game
# reads about 0.3335 one second in: verified in game 28 Oct, two runs (0.333530 with MQ101 at stage 0, 0.333537 at
# 250). The first build's 0.25 stood every new game down on this test alone; a player's save should never start the
# startup quest (supported hypothesis), so one game day is the bound here.
MAX_NEW_GAME_DAYS = 1.0
NEW_GAME_DAYS_MEASURED = 0.3335


def is_new_game(days, level, max_days=MAX_NEW_GAME_DAYS, max_level=1):
    """FO4SF_NewGameQuest.IsNewGame, the whole guard: fewer than max_days game days passed and the player at most
    max_level. Only a New Game (or a New Game+, which keeps the player's level) should start the startup quest, never
    a save (supported hypothesis, the doc's section 1 step 2), so newgame_v9's opening-stage test (is_fresh_start, 21
    Oct review on #393) had nothing left to judge. A console start under a day at level 1 passes, as a New Game does."""
    return days < max_days and level <= max_level


def declared_properties(psc_text):
    """{name: mandatory?} of every Property the script declares."""
    out = {}
    for m in re.finditer(r"^\s*[\w\[\]]+\s+Property\s+(\w+)(?:\s*=\s*[^\n]*?)?\s+Auto(\s+Const)?(\s+Mandatory)?\b",
                         psc_text, re.M | re.I):
        out[m.group(1)] = bool(m.group(3))
    return out


def has_function(source, name):
    """True when a base script's source declares Function <name> (native or not) or Event <name>."""
    return re.search(rf"^\s*(?:[\w\[\]:]+\s+)?(?:Function|Event)\s+{re.escape(name)}\s*\(", source, re.M | re.I) is not None


def parent_of(source):
    """The base script a source extends ("Scriptname Actor extends ObjectReference"), or None."""
    m = re.search(r"^\s*Scriptname\s+[\w:]+\s+extends\s+([\w:]+)", source, re.M | re.I)
    return m.group(1) if m else None


def declares(sources, base, name, depth=8):
    """True when base's source, or one it extends (Actor extends ObjectReference extends Form ...), declares name. The
    Papyrus compiler resolves an inherited call the same way: FO4SF_NewGameSpecial compiled on the PC (newgame_v7) while
    a check of Actor.psc alone said Actor.SetValue was missing (28 Oct), so the two are declared above Actor. Bounded
    by depth and by a seen set (a cycle in the sources stops the walk)."""
    seen = set()
    while base and base.lower() not in seen and len(seen) < depth:
        seen.add(base.lower())
        source = sources.get(base.lower(), "")
        if has_function(source, name):
            return True
        base = parent_of(source)
    return False


def precheck_zip(zip_path):
    """{"natives": {script: {"Base.Function": bool}}, "mq101debug": [file:line: text], "missing_core": [...]}."""
    sources, debug = {}, []
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if not name.lower().endswith(".psc"):
                continue
            text = z.read(name).decode("utf-8", errors="replace")
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"]:
                sources[parts[2][:-4].lower()] = text
            for i, line in enumerate(text.splitlines(), 1):
                if "mq101debug" in line.lower():
                    debug.append(f"{name}:{i}: {line.strip()}")
    natives = {}
    for script, bases in NATIVES.items():
        natives[script] = {f"{b}.{f}": declares(sources, b, f) for b, fs in bases.items() for f in fs}
    missing = [k for k, ok in natives[SCRIPT].items() if not ok]
    drop = [opt for script, opt in OPTIONAL.items() if not all(natives[script].values())]
    return {"natives": natives, "mq101debug": debug, "missing_core": missing, "drop": drop}


def precheck(a):
    r = precheck_zip(a.content_resources)
    for script, found in r["natives"].items():
        for k, ok in found.items():
            print(f"{'ok  ' if ok else 'MISSING'}  {script}: {k}")
    print(f"MQ101Debug: {len(r['mq101debug'])} line(s)")
    for line in r["mq101debug"][:80]:
        print("  " + line)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=1)
    print("precheck: " + ("ok" if not r["missing_core"] else f"{len(r['missing_core'])} native(s) missing; do not stage")
          + "".join(f"; {script} cannot compile: stage with {opt}" for script, opt in OPTIONAL.items() if opt in r["drop"]))
    return 0 if not r["missing_core"] else 1


def extract_sources(zip_path, work):
    """Every base script (Scripts/Source/*.psc, top level) and the flags file, as make_mission.py does."""
    src = os.path.join(work, "Source")
    os.makedirs(src, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and (
                    parts[2].lower().endswith(".psc") or parts[2] == "Starfield_Papyrus_Flags.flg"):
                with z.open(name) as f, open(os.path.join(src, parts[2]), "wb") as o:
                    shutil.copyfileobj(f, o)
                n += 1
    if not os.path.exists(os.path.join(src, "Starfield_Papyrus_Flags.flg")) or n < 2:
        sys.exit(f"{zip_path}: no Scripts/Source base scripts or flags file")
    return src


def compile_script(compiler, name, src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    inc = ";".join((HERE, PROGRESSION_SCRIPTS, SURVIVAL_SCRIPTS, REPUTATION_SCRIPTS, MAPMARKERS_SCRIPTS, src_dir))
    r = run([compiler, name + ".psc", "-f=Starfield_Papyrus_Flags.flg", f"-i={inc}", f"-o={out_dir}"],
            cwd=HERE, check=False)
    pex = os.path.join(out_dir, name + ".pex")
    if r.returncode != 0 or "Compilation succeeded" not in r.stdout or not os.path.exists(pex):
        hint = f" (stage again with {OPTIONAL[name]})" if name in OPTIONAL else ""
        sys.exit(f"the Papyrus compile of {name}.psc did not produce {name}.pex{hint}")
    return pex


def new_partial(final, create=True):
    base = f"{final}.partial-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    out, n = base, 1
    while os.path.exists(out):
        out, n = f"{base}-{n}", n + 1
    if create:
        os.makedirs(out)
    return out


def hold_option(a):
    """Comma-joined hold list for the writer and plan.json: --hold, --omit-hold-group, or DEFAULT_HOLD."""
    omit = getattr(a, "omit_hold_group", None)
    if a.hold and omit:
        sys.exit("--hold and --omit-hold-group contradict each other")
    if omit:
        return ",".join(OMIT_HOLD_GROUPS[omit])
    return a.hold or ",".join(DEFAULT_HOLD)


def tool_options(a):
    opts = []
    if getattr(a, "exit_lift", None):
        opts.append("--animated-exit-lift")
    if a.hold or getattr(a, "omit_hold_group", None):
        opts += ["--hold", hold_option(a)]
    if a.no_mq101debug:
        opts.append("--no-mq101debug")
    elif a.mq101debug is not None:
        opts += ["--mq101debug", str(a.mq101debug)]
    if a.debug_after_hold is not None:
        opts += ["--debug-after-hold", str(a.debug_after_hold)]
    if not a.looks:
        opts.append("--no-looks")
    if a.race_menu_mode is not None:
        opts += ["--race-menu-mode", str(a.race_menu_mode)]
    if not a.special:
        opts.append("--no-special")
    if not a.version:
        opts.append("--no-version")
    if a.build_version is not None:
        opts += ["--build-version", str(a.build_version)]
    if a.keep_inventory:
        if a.clear_inventory:
            sys.exit("--keep-inventory and --clear-inventory contradict each other")
        if a.vault_suit:
            sys.exit("--vault-suit is equipped by the inventory reset: --keep-inventory turns it off")
        opts.append("--keep-inventory")
    elif a.vault_suit:
        opts += ["--vault-suit", a.vault_suit]
    if a.allow_temporary_anchor:
        if a.require_persistent_anchor:
            sys.exit("--allow-temporary-anchor and --require-persistent-anchor contradict each other")
        opts.append("--allow-temporary-anchor")
    if a.no_o2_fill:
        opts.append("--no-o2-fill")
    if getattr(a, "no_fade_hold", False):
        opts.append("--no-fade-hold")
    if getattr(a, "start_choice_backdrop", None):
        opts += ["--start-choice-backdrop", str(a.start_choice_backdrop)]
    if getattr(a, "warfare_starts", None):
        opts += ["--warfare-starts", a.warfare_starts]
    if getattr(a, "start_places", None):
        opts += ["--start-places", a.start_places]
    return opts


def clear_inventory_option(a):
    """Whether the build empties the inventory at the pod: DEFAULT_CLEAR_INVENTORY (on) unless --keep-inventory."""
    return DEFAULT_CLEAR_INVENTORY and not a.keep_inventory


def o2_fill_option(a):
    """Whether the quest tops the O2 capacity up after the reset: DEFAULT_O2_FILL with the reset, unless --no-o2-fill."""
    return DEFAULT_O2_FILL and clear_inventory_option(a) and not a.no_o2_fill


def mq101debug_option(a):
    """The GLOB MQ101Debug override the build writes at the start: None (no override, the default since 28 Oct run 2, and
    under --no-mq101debug), else the value given with --mq101debug (experiments only)."""
    if a.no_mq101debug:
        return None
    return DEFAULT_MQ101DEBUG if a.mq101debug is None else a.mq101debug


def debug_after_hold_option(a):
    """The value the quest writes into MQ101Debug right after the hold-off (0: nothing)."""
    return DEBUG_AFTER_HOLD if a.debug_after_hold is None else a.debug_after_hold


def build_version_option(a):
    """The version number the build writes to GLOB FO4SF_NewGameVersion: None under --no-version, else the value
    given or the default."""
    if not a.version:
        return None
    return DEFAULT_BUILD_VERSION if a.build_version is None else a.build_version


def anchor_mode(check_text):
    """The vault anchor as check printed it: {"id": "<hex>", "mode": "persistent" | "temporary"}; None when the text has
    no such line (a check that never reached the anchor). "temporary" means the quest script centers on the vault cell
    before the marker resolves (AnchorTemporary); plan.json records it as "anchor"."""
    m = ANCHOR_LINE.search(check_text)
    return {"id": m.group("id").upper(), "mode": m.group("mode")} if m else None


def pins(a):
    return {"FO4Port.esm": sha256(a.port), "formids.json": sha256(a.port_ids), "FO4TerrainCore.esm": sha256(a.core)}


def cog_door_component(folder, port, starfield):
    """Validate the separate production Vault 111 gear-door stage, refusing probe kits and file drift."""
    import make_anim_probe as probe_a
    import make_cog_door as mcd
    with open(os.path.join(folder, "plan.json"), encoding="utf-8") as f:
        plan = json.load(f)
    ref = str(plan.get("ref") or "").lower().removeprefix("0x").lstrip("0")
    if plan.get("kind") != mcd.COG_KIND or plan.get("plugins") != [mcd.COG_PLUGIN] or ref != "126d":
        sys.exit("--cog-door needs the production Vault 111 gear door component, never a cog-door probe")
    files = probe_a.stage_files(folder)
    if files != plan.get("outputs") or any(p != mcd.COG_PLUGIN and not p.startswith(("Data/meshes/", "Data/geometries/", "Data/materials/")) for p in files):
        sys.exit("cog door assets changed, are missing, or include a probe script")
    if mcd.COG_PLUGIN not in files or len(files) < 2:
        sys.exit("cog door component has no plugin/assets")
    for name, path in (("FO4Port.esm", port), ("Starfield.esm", starfield)):
        if plan.get("inputs", {}).get(name, {}).get("sha256") != sha256(path):
            sys.exit(f"cog door was built against different {name} bytes")
    return plan


def exit_lift_component(folder, port, starfield):
    """Validate the separate production asset stage, refusing all probe kits and any file drift."""
    import make_anim_console as mac
    with open(os.path.join(folder, "plan.json"), encoding="utf-8") as f:
        plan = json.load(f)
    if (plan.get("kind") != mac.LIFT_KIND or plan.get("plugins") != [mac.LIFT_PLUGIN]
            or plan.get("states") != mac.LIFT_STATES or plan.get("rise_m") != 21.6
            or plan.get("seconds") != 9.8667 or plan.get("event") != "Play01"):
        sys.exit("--exit-lift needs the production floor-start lift component, never an animation probe")
    files = mac.probe_a.stage_files(folder)
    if files != plan.get("outputs") or any(p != mac.LIFT_PLUGIN and not p.startswith(("Data/meshes/", "Data/geometries/", "Data/materials/")) for p in files):
        sys.exit("exit lift assets changed, are missing, or include a probe script")
    if mac.LIFT_PLUGIN not in files or len(files) < 2:
        sys.exit("exit lift component has no plugin/assets")
    for name, path in (("FO4Port.esm", port), ("Starfield.esm", starfield)):
        if plan.get("inputs", {}).get(name, {}).get("sha256") != sha256(path):
            sys.exit(f"exit lift was built against different {name} bytes")
    return plan


def points_options(a):
    """The optional flags `stage` hands to `dotnet NewGame points` (none given: the tool's DefaultPodStep = -2.5)."""
    return ((["--pod-ref", a.pod_ref] if a.pod_ref else [])
            + (["--terminal-ref", a.terminal_ref] if a.terminal_ref else [])
            + (["--pod-step", repr(float(a.pod_step))] if getattr(a, "pod_step", None) is not None else []))


def refuse_forbidden_out_dir(out_dir):
    full = os.path.abspath(out_dir)
    cur = full
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            sys.exit(f"refused: output folder inside Git worktree is forbidden ({full})")
        if os.path.isfile(os.path.join(cur, "Starfield.exe")):
            sys.exit(f"refused: output folder inside game install is forbidden ({full})")
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent


def stage(a):
    final = os.path.abspath(a.out)
    refuse_forbidden_out_dir(final)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    before = pins(a)
    cog_folder = getattr(a, "cog_door", None)
    cog = cog_door_component(cog_folder, a.port, a.starfield) if cog_folder else None
    lift_folder = getattr(a, "exit_lift", None)
    lift = exit_lift_component(lift_folder, a.port, a.starfield) if lift_folder else None
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work)
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    points = os.path.join(work, "points.json")
    run(tool + ["points", a.fo4, points] + points_options(a))
    opts = tool_options(a)
    masters = [a.starfield, a.port, a.port_ids, a.core, points]
    run(tool + ["write", a.starfield, a.port, a.port_ids, a.core, points, out] + opts)
    check = run(tool + ["check", os.path.join(out, PLUGIN)] + masters + opts).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(check)
    anchor = anchor_mode(check)
    if anchor is None:
        sys.exit(f"check printed no vault anchor line (persistent or temporary); attempt kept in {out}")
    src = extract_sources(a.content_resources, work)
    scripts = [SCRIPT] + ([LOOKS] if a.looks else []) + ([SPECIAL] if a.special else []) + ([VERSION] if a.version else [])
    pex = {s: compile_script(a.compiler, s, src, os.path.join(out, "Data", "Scripts")) for s in scripts}
    for s in scripts:
        shutil.copy(os.path.join(HERE, s + ".psc"), os.path.join(out, s + ".psc"))
    drift = [f"{n}: {before[n]} at the start, {h} now" for n, h in pins(a).items() if h != before[n]]
    if drift:
        sys.exit("an input changed during the build, nothing published (" + "; ".join(drift) + f"); attempt kept in {out}")
    staged_assets = {}
    for label, comp, folder, checker in (("cog door", cog, cog_folder, cog_door_component),
                                         ("lift", lift, lift_folder, exit_lift_component)):
        if comp:
            if checker(folder, a.port, a.starfield) != comp:
                sys.exit(f"{label} component changed during the build")
            for rel, want in comp["outputs"].items():
                dest = os.path.join(out, *rel.split("/"))
                if os.path.exists(dest):
                    if rel.startswith("Data/") and staged_assets.get(rel) == want and sha256(dest) == want:
                        continue
                    sys.exit(f"{label} asset collides with staged output: {rel}")
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copyfile(os.path.join(folder, *rel.split("/")), dest)
                if sha256(dest) != want:
                    sys.exit(f"{label} asset changed while copying: {rel}")
                staged_assets[rel] = want
    with open(points, encoding="utf-8") as f:
        pts = json.load(f)
    o_show_unavailable = getattr(a, "show_unavailable_starts", 0)
    plan = {"kind": "newgame", "plugin": PLUGIN, "plugin_sha256": sha256(os.path.join(out, PLUGIN)),
            "scripts": {s: sha256(p) for s, p in pex.items()}, "checked_against_sha256": before,
            "options": {"hold": hold_option(a), "mq101debug": mq101debug_option(a), "debug_after_hold": debug_after_hold_option(a), "looks": a.looks,
                        "race_menu_mode": DEFAULT_RACE_MENU_MODE if a.race_menu_mode is None else a.race_menu_mode,
                        "special": a.special, "version": a.version,
                        "build_version": build_version_option(a),
                        "clear_inventory": clear_inventory_option(a), "vault_suit": a.vault_suit if clear_inventory_option(a) else None,
                        "o2_fill": o2_fill_option(a),
                        "fade_hold": not bool(getattr(a, "no_fade_hold", False)),
                        "start_choice_backdrop": getattr(a, "start_choice_backdrop", None) or "empty_cell",
                        "show_unavailable_starts": int(bool(o_show_unavailable)),
                        "allow_temporary_anchor": bool(a.allow_temporary_anchor)},
            "anchor": anchor,
            "stages": {str(n): what for n, what in STAGE_CONTRACT.items()}, "points": pts,
            "log": "<My Games>/Starfield/Logs/Script/User/fo4sf_newgame.0.log"}
    if cog:
        plan["cog_door"] = cog
    if lift:
        plan["exit_lift"] = lift
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Fallout 4 new game (Claude-cloud, {datetime.date.today().isoformat()}). docs/newgame/vault111-start.md
{PLUGIN} (sha256 {plan['plugin_sha256']}): QUST FO4SF_NewGame "{pts['quest_name']}" (run once, Starfield's startup quest: DFOB StartupQuest_DO overridden),
MESG FO4SF_NewGameElevator and FO4SF_NewGameStart{f', FO4SF_NewGameTerminal and FO4SF_NewGameSpecial (7 AVIF in {CORE_VALUES_PLUGIN})' if a.special else ''}{f', GLOB FO4SF_NewGameVersion = {build_version_option(a)} and a player alias (the save version check)' if a.version else ''};
masters Starfield.esm and {CORE_VALUES_PLUGIN}. Scripts: {', '.join(s + '.pex' for s in scripts)} in Data\\Scripts.
Checked against (the ids it resolves at run time must stay): {json.dumps(before)}. Re-stage after a port or core change.
Pod {pts['pod']['src']} {pts['pod'].get('edid')}; arrival {pts['arrival']['pos']} m (core-local); {len(pts.get('terminals', []))} terminal(s) in the cell.
Inventory reset at the pod: {('ON, the default (whether quest items stay is unverified; left= says how many stayed, not which), vault suit ' + (a.vault_suit or 'none: the player should start with nothing; unverified until the first run')) if clear_inventory_option(a) else 'off (--keep-inventory: the player keeps what Starfield gives)'}.
Starfield environment: {'SQ_ENV held off (its 17 ENV abilities: suit, hazard soak, water and O2; unverified until the PC run; placed local hazards and the race hit-spell abilities do not come from SQ_ENV)' if 'SQ_ENV' in hold_option(a).split(',') else 'SQ_ENV runs (Starfield hazards on)'}; O2 capacity {'topped up to 100 after the reset (clears the O2/CO2 dial)' if o2_fill_option(a) else 'untouched'}.
Vault anchor FO4Port.esm:{anchor['id']} {anchor['mode']}{' (the script centers on the vault cell first: the log says "centered on ...")' if anchor['mode'] == 'temporary' else ''}.
Options {json.dumps(plan['options'])}.
Install: not now. When the owner says so (game closed): fold into a core set (the folded README gives the exp_install.py
command, every plugin listed), verify, then exp_install.py.
In game: a NEW game from the main menu only (a save should never start the quest, nor a coc from the menu). Read the run:
  python scripts\\newgame\\make_newgame.py log
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {len(scripts)} script(s), offline_check.txt, plan.json, README.txt")
    return 0


def load_plan(path):
    with open(path, encoding="utf-8") as f:
        plan = json.load(f)
    missing = [k for k in ("plugin", "plugin_sha256", "scripts", "checked_against_sha256") if k not in plan]
    if missing or plan.get("kind") != "newgame":
        sys.exit(f"{path} is not a new-game plan (missing {missing})")
    return plan


def verify_dir(exp_dir, plan, port=None, core=None):
    problems = []

    def same(label, path, want):
        if not path or not os.path.isfile(path):
            problems.append(f"{label}: {path} missing")
        elif sha256(path) != want:
            problems.append(f"{label}: {path} sha256 {sha256(path)} is not the plan's {want}")

    same("plugin", os.path.join(exp_dir, plan["plugin"]), plan["plugin_sha256"])
    for s, want in plan["scripts"].items():
        same("script", os.path.join(exp_dir, "Data", "Scripts", s + ".pex"), want)
    for rel, want in plan.get("cog_door", {}).get("outputs", {}).items():
        same("cog door", os.path.join(exp_dir, *rel.split("/")), want)
    for rel, want in plan.get("exit_lift", {}).get("outputs", {}).items():
        same("exit lift", os.path.join(exp_dir, *rel.split("/")), want)
    pinned = plan["checked_against_sha256"]
    for name, given in (("FO4Port.esm", port), ("FO4TerrainCore.esm", core)):
        path = os.path.join(exp_dir, name)
        same(f"checked against {name}", path if os.path.isfile(path) else given, pinned[name])
    return problems


def verify(a):
    problems = verify_dir(a.exp_dir, load_plan(a.plan), a.port, a.core)
    for p in problems:
        print("FAIL  " + p)
    print("verify: ok" if not problems else f"verify: {len(problems)} problem(s); do not install")
    return 0 if not problems else 1


INSTALL_LINE = re.compile(r"exp_install\.py install\b.*--plugins (?P<plugins>\S+)")


def core_plugins(core_dir, readme):
    """The core set's plugins in install order: the --plugins list of its README's exp_install.py install line when it
    has one (the first named plugin names the --pack archive), else its .esm files sorted. The README's list must be
    exactly the .esm files present: a README naming another set is a core set that cannot be installed as it says."""
    present = sorted(f for f in os.listdir(core_dir) if f.lower().endswith(".esm"))
    if not present:
        sys.exit(f"fold refused: {core_dir} holds no .esm")
    m = INSTALL_LINE.search(readme)
    if not m:
        return present
    listed = m.group("plugins").split(",")
    if sorted(listed) != present:
        sys.exit(f"fold refused: {core_dir}'s README installs {listed} but the folder holds {present}")
    return listed


def install_command(plugins):
    return f"scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> --plugins {','.join(plugins)} --pack"


def folded_readme(core_readme, stage_readme, plugins, plugin, stage):
    """The folded set's README.txt: the core's, with the --plugins list of every exp_install.py install line widened to
    the whole set, then the stage's README and the one install command. exp_install.py installs only the plugins
    listed (none listed: the first .esm alphabetically), so the core's own command, copied as it was, would install the
    core and never the new game (Codex review on #393)."""
    def widen(line):
        m = INSTALL_LINE.search(line)
        return line[:m.start("plugins")] + ",".join(plugins) + line[m.end("plugins"):] if m else line

    return "\n".join([widen(line) for line in core_readme.splitlines()] + ["", f"==== {plugin} folded in ({datetime.date.today().isoformat()}) from {stage} ====",
                             stage_readme.rstrip("\n"), "",
                             f"Install (game closed): this folder, EVERY plugin listed. exp_install.py activates only "
                             f"the plugins of --plugins (none: the first .esm alphabetically), so a core-only or "
                             f"plugin-less command never installs {plugin}:",
                             "  " + install_command(plugins)]) + "\n"


def fold(a):
    final = os.path.abspath(a.out)
    refuse_forbidden_out_dir(final)
    if os.path.exists(final):
        sys.exit(f"{final} exists: fold into a new folder")
    plan = load_plan(os.path.join(a.stage, "plan.json"))
    if os.path.exists(os.path.join(a.core_dir, plan["plugin"])):
        sys.exit(f"{a.core_dir} already holds {plan['plugin']}")
    core_readme = read_text(os.path.join(a.core_dir, "README.txt"))
    stage_readme = read_text(os.path.join(a.stage, "README.txt"))
    cog_outputs = plan.get("cog_door", {}).get("outputs", {})
    cog_plugins = plan.get("cog_door", {}).get("plugins", [])
    lift_outputs = plan.get("exit_lift", {}).get("outputs", {})
    lift_plugins = plan.get("exit_lift", {}).get("plugins", [])
    plugins = core_plugins(a.core_dir, core_readme) + cog_plugins + lift_plugins + [plan["plugin"]]
    if len(set(plugins)) != len(plugins):
        sys.exit("fold refused: duplicate cog/lift/new-game plugins in core set")
    out = new_partial(final, create=False)
    shutil.copytree(a.core_dir, out)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(folded_readme(core_readme, stage_readme, plugins, plan["plugin"], os.path.abspath(a.stage)))
    shutil.copy2(os.path.join(a.stage, plan["plugin"]), os.path.join(out, plan["plugin"]))
    folded_assets = {}
    for label, outputs in (("cog door", cog_outputs), ("lift", lift_outputs)):
        for rel, want in outputs.items():
            dst = os.path.join(out, *rel.split("/"))
            core_src = os.path.join(a.core_dir, *rel.split("/"))
            if os.path.exists(core_src):
                if (rel.startswith("Data/") and os.path.isfile(core_src) and sha256(core_src) == want
                        and os.path.isfile(dst) and sha256(dst) == want):
                    folded_assets[rel] = want
                    continue
                sys.exit(f"fold refused: core set already has {label} asset {rel} with differing sha256 (attempt kept in {out})")
            if os.path.exists(dst):
                if rel.startswith("Data/") and os.path.isfile(dst) and folded_assets.get(rel) == want and sha256(dst) == want:
                    continue
                sys.exit(f"fold refused: {label} asset {rel} collides with differing staged asset (attempt kept in {out})")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(a.stage, *rel.split("/")), dst)
            folded_assets[rel] = want
    for s, want in plan["scripts"].items():
        dst = os.path.join(out, "Data", "Scripts", s + ".pex")
        if os.path.exists(dst):
            if os.path.isfile(dst) and sha256(dst) == want:
                continue
            sys.exit(f"fold refused: the core set already has Data/Scripts/{s}.pex with differing sha256 (attempt kept in {out})")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(a.stage, "Data", "Scripts", s + ".pex"), dst)
    problems = verify_dir(out, plan, a.port, a.core)
    if problems:
        for p in problems:
            print("FAIL  " + p)
        sys.exit(f"fold refused: {len(problems)} problem(s); nothing published (attempt kept in {out})")
    os.replace(out, final)
    print(f"folded {final}: {a.core_dir} + {plan['plugin']} + {len(plan['scripts'])} script(s); verify ok")
    print("install (game closed): " + install_command(plugins))
    return 0


def split_runs(lines, line_re, start="init ", carry=()):
    """The messages of each run, oldest first: a user log is appended across game sessions, so a run starts at each
    message beginning with `start` (the script's OnInit trace); messages before the first one form a run of their own.
    A message beginning with one of `carry` that comes right before a `start` belongs to that new run: another
    script's init can trace before the quest's own (21 Oct review on #393, the version script). Lines of other logs
    are dropped."""
    runs, pending = [], []
    for line in lines:
        m = line_re.search(line)
        if not m:
            continue
        msg = m.group("msg")
        if carry and msg.startswith(carry):
            pending.append(msg)
            continue
        if msg.startswith(start) or not runs:
            runs.append([])
            if msg.startswith(start):
                runs[-1] += pending
                pending = []
        runs[-1] += pending + [msg]
        pending = []
    if pending:
        if not runs:
            runs.append([])
        runs[-1] += pending
    return runs


def summarize(lines):
    """The LATEST run of the new-game log as {"stages", "stages_named", "held_off", "held_off_by_pass", "looks_done",
    "special", "version_saved", "version_load", "version_mismatch", "inventory_cleared", "vault_suit", "o2_capacity",
    "centered", "entered_vault", "pod_settle", "surfaced", "landed", "fell", "stood_down", "stand_down", "handing_back",
    "handed_back", "start", "start_events", "start_wait", "waiting_3d", "fade", "guard", "last_status", "runs",
    "earlier_completed"}.
    Our own start (newgame_v11, the startup quest): "start" is the start's first line ("<route> player_loaded=<bool>
    cell=<cell> loading=<bool>", the start event that ran it, its two readings and whether either said the game was
    still loading, which decides a hand back), "start_events" every start event that came, the one that ran the start
    first, then any "came after the start" (which fire on 1.16.244 is what run 4 shows), "start_wait" the end of the
    start's wait for the player's 3D ("loaded=<bool>": false leaves the fade to the timer), "waiting_3d" the timer's
    last line while it still waits for that 3D ("tick=<n> vault_moves=<n> centered=<n> cell=<cell>", every 10 ticks;
    None when the 3D came sooner, or the timer never ran then) and "fade" the one fade in ("by=<start|timer>
    loaded=<bool> cell=<cell>; ..."); an older build's log has none of them (None, and no events).
    "stood_down" is true on either stand-down ("not a new game: ..." or "no move into the vault: ...", the line in
    "stand_down"). The hand back to Starfield's opening writes two lines: "handing_back" is the first ("<why>;
    mq101debug=<n>"), written before the request, and "handed_back" the second ("requested=<bool> opening
    starting=<bool> running=<bool> stage=<n>"), MQ101's state right after a request that waits for nothing: no
    verdict. Both None when nothing was handed back (a stand-down whose readings both said the game runs, or a start
    that went on); "handing_back" alone means the request never returned.
    "guard" is the guard's readings line ("days=<n> level=<n> opening_stage=<n> opening_running=<bool> mq101debug=<n>
    write_after_hold=<n>"; newgame_v9 and v10 also wrote "fresh=<bool>"; None in a build before 28 Oct).
    "mq101debug_written" is the write right after hold-off pass 1 ("<n> was=<n>"; None when the build writes nothing,
    or when the hold-off never ran: run 2 of 28 Oct has only the version line, the game never finished its first load).
    "inventory_cleared" is the reset's line ("removed=<n> left=<n>"; None when the build kept the inventory) and
    "vault_suit" the suit's ("equipped <armor> worn=<bool>", or that it did not resolve; None when none was named).
    "o2_capacity" is the O2 fill's line ("added=<n> value=<n>"; None when the build has none).
    "centered" is the temporary-anchor mode's first centering line ("<cell> attempt=1 tick=<n>: ..."; None in the
    persistent mode, which never centers, or when the anchor resolved at once). "entered_vault" is the last move's
    verdict, or true once the timer confirms after the load that the start's move took ("enter vault confirmed").
    "pod_settle" is where the player stood the first loaded tick after the move into the pod ("ok=<bool> pos=<x y z>
    dx=<n> dy=<n> drop=<n>"; None in a build before newgame_v10, which had no such line: run 3 of 28 Oct sank under the
    pod's z and the game put the player on the COC marker). "surfaced" is the last "surface setposition" line: since
    newgame_v10 it says whether the merged arrival took ("ok=<bool> set=<n> pos=... target=...").
    "stages_named" reads each stage reached by the contract (STAGE_CONTRACT); "held_off_by_pass" says what each
    hold-off pass stopped (since newgame_v11 pass 1 in the start right after the move, pass 2 once the vault has loaded;
    before it pass 1 came before the move and pass 2 a tick later); "looks_done" says what ended the looks wait
    ("creator closed", "quick start", or the quest's "LooksWait fallback ..."); "special"
    is the SPECIAL script's ending ("set S=.. P=.. ..." or "skipped: ..." when the player left the vault without it;
    "later" and "left" prompts are not endings). "version_saved" is the build version the version script recorded
    when the new game started, "version_load" the last "saved=<n> installed=<n>" line of a save load (a load logs no
    "init", so it joins the run before it) and "version_mismatch" whether any load found the two apart. Only the
    latest run is judged; "runs" counts the runs in the file and "earlier_completed" says whether an older one reached
    stage 200 (kept as history, never as the current result). Lines of other logs are ignored."""
    s = {"stages": [], "stages_named": [], "held_off": [], "held_off_by_pass": {}, "looks_done": None, "special": None,
         "version_saved": None, "version_load": None, "version_mismatch": False,
         "inventory_cleared": None, "vault_suit": None, "o2_capacity": None, "centered": None,
         "entered_vault": None, "pod_settle": None, "surfaced": None, "landed": None, "fell": False, "stood_down": False,
         "stand_down": None, "handing_back": None, "handed_back": None, "start": None, "start_events": [],
         "start_wait": None, "waiting_3d": None, "fade": None,
         "guard": None, "mq101debug_written": None, "last_status": None, "runs": 0, "earlier_completed": False,
         "arrival_discovery_requested": None, "exit_failure": None, "ascent": [], "looks_positions": [],
         "landing_quests": None, "pipboy_pickup": None, "mode_fade_held": False, "mode_choice": None,
         "mode_load_default": None, "warfare_pick": None, "warfare_gear": None,
         "map_setup": None, "pistol_picked": None, "exit_retries": [], "exit_fallback": None,
         "arrival_discovery_failed": None, "special_default": None,
         "stage_causes": {}, "mode_fade_requests": 0, "mode_box_waits": [], "mode_neutral_spot": False,
         "mode_fade_lifted": None, "start_record": None, "entered_start_room": None,
         "h00_suspects": {}, "surface_pre_setposition": None}
    runs = split_runs(lines, LINE, carry=("version saved=",))
    s["runs"] = len(runs)
    s["earlier_completed"] = any(
        any(m == "stage 200" or m.startswith("stage 200 ") or m == "stage 210" or m.startswith("stage 210 ") for m in r)
        for r in runs[:-1]
    )
    for msg in runs[-1] if runs else []:
        if msg.startswith("stage "):
            parts = msg.split()
            n = int(parts[1])
            s["stages"].append(n)
            s["stages_named"].append(f"{n} {STAGE_CONTRACT.get(n, 'not in the contract')}")
            by_val = next((p.split("=", 1)[1] for p in parts[2:] if p.startswith("by=")), None)
            s["stage_causes"][n] = by_val
        elif msg.startswith("held off "):
            quest, _, rest = msg[len("held off "):].partition(" running_after=")
            s["held_off"].append(quest)
            m = re.search(r"\bpass=(\d+)", rest)
            s["held_off_by_pass"].setdefault(m.group(1) if m else "1", []).append(quest)
        elif msg.startswith("looks done: "):
            if s["looks_done"] is None:                      # the first ending counts; a later one changes nothing
                s["looks_done"] = msg[len("looks done: "):]
        elif msg.startswith("special set ") or msg.startswith("special skipped"):
            if s["special"] is None:
                s["special"] = msg[len("special "):]
        elif msg.startswith("version saved="):
            if s["version_saved"] is None:
                s["version_saved"] = msg[len("version saved="):].split()[0]
        elif msg.startswith("version load "):
            s["version_load"] = msg[len("version load "):]
        elif msg.startswith("version mismatch"):
            s["version_mismatch"] = True
        elif msg.startswith("inventory cleared "):
            s["inventory_cleared"] = msg[len("inventory cleared "):]
        elif msg.startswith("vault suit "):
            s["vault_suit"] = msg[len("vault suit "):]
        elif msg.startswith("o2 capacity "):
            s["o2_capacity"] = msg[len("o2 capacity "):]
        elif msg.startswith("centered on "):
            if s["centered"] is None:                        # the first centering; a second one is the bound's retry
                s["centered"] = msg[len("centered on "):]
        elif msg.startswith("enter vault ok="):
            # Starfield's Papyrus prints a bool as "true" / "false" (the 28 Oct log: anchor_temporary=true), FO4's
            # tests wrote "True"; both read
            s["entered_vault"] = msg.split()[2].lower() == "ok=true"
        elif msg.startswith("enter vault confirmed "):
            s["entered_vault"] = True                        # the start's move took: the timer saw the vault cell
        elif msg.startswith("pod settle "):
            if s["pod_settle"] is None:                      # the script checks once
                s["pod_settle"] = msg[len("pod settle "):]
        elif msg.startswith("looks position "):
            s["looks_positions"].append(msg[len("looks position "):])
        elif msg.startswith("surface pre_setposition "):
            s["surface_pre_setposition"] = msg
        elif msg.startswith("h00 suspect "):
            kv = msg[len("h00 suspect "):].strip()
            if "=" in kv:
                k, v = kv.split("=", 1)
                s["h00_suspects"][k.strip()] = int(v.strip().split()[0])
        elif msg.startswith("surface setposition "):
            s["surfaced"] = msg
        elif msg.startswith("landed "):
            s["landed"] = True
        elif msg.startswith("arrival discovery requested "):
            s["arrival_discovery_requested"] = msg[len("arrival discovery requested "):]
        elif msg.startswith("arrival discovery failed "):
            s["arrival_discovery_failed"] = msg[len("arrival discovery failed "):]
        elif msg.startswith("special default "):
            s["special_default"] = msg[len("special default "):]
        elif msg.startswith("exit retry "):
            s["exit_retries"].append(msg[len("exit retry "):])
        elif msg.startswith("exit fallback "):
            s["exit_fallback"] = msg[len("exit fallback "):]
        elif msg.startswith("landing quests started "):
            s["landing_quests"] = msg[len("landing quests started "):]
        elif msg.startswith("pipboy pickup "):
            s["pipboy_pickup"] = msg[len("pipboy pickup "):]
        elif msg.startswith("mode fade held"):
            s["mode_fade_held"] = True
            s["mode_fade_requests"] += 1
        elif msg.startswith("mode box waiting s="):
            s["mode_box_waits"].append(int(msg[len("mode box waiting s="):].split()[0]))
        elif msg.startswith("mode neutral spot active"):
            s["mode_neutral_spot"] = True
        elif msg.startswith("mode fade lifted "):
            s["mode_fade_lifted"] = msg[len("mode fade lifted "):]
        elif msg.startswith("enter start room ok="):
            s["entered_start_room"] = msg.split()[3].lower() == "ok=true"
        elif msg.startswith("enter start room confirmed "):
            s["entered_start_room"] = True
        elif msg.startswith("start record "):
            s["start_record"] = msg[len("start record "):]
        elif msg.startswith("mode choice "):
            s["mode_choice"] = msg[len("mode choice "):]
        elif msg.startswith("mode load default="):
            s["mode_load_default"] = msg[len("mode load default="):]
        elif msg.startswith("warfare pick "):
            s["warfare_pick"] = msg[len("warfare pick "):]
        elif msg.startswith("warfare gear n="):
            s["warfare_gear"] = msg[len("warfare gear n="):]
        elif msg.startswith("map setup done "):
            s["map_setup"] = msg[len("map setup done "):]
        elif msg.startswith("pistol picked "):
            s["pistol_picked"] = msg[len("pistol picked "):]
        elif msg.startswith("ascent "):
            s["ascent"].append(msg[len("ascent "):])
        elif msg.startswith("exit failed reason="):
            s["exit_failure"] = msg[len("exit failed reason="):]
        elif msg.startswith("fell "):
            s["fell"] = True
        elif msg.startswith("not a new game") or msg.startswith("no move into the vault"):
            s["stood_down"] = True
            s["stand_down"] = msg
        elif msg.startswith("handing back to Starfield's start: "):
            s["handing_back"] = msg[len("handing back to Starfield's start: "):]
        elif msg.startswith("handed back: "):
            s["handed_back"] = msg[len("handed back: "):]
        elif msg.startswith("start route="):
            s["start"] = msg[len("start route="):]
            # the event that ran the start: first, since the script writes the other event's line after this one
            # (Begin's lateRoute, 29 Oct review on #588)
            s["start_events"].append(s["start"].split()[0])
        elif msg.startswith("start event "):
            s["start_events"].append(msg.split()[2])         # "start event <route> came after the start: ..."
        elif msg.startswith("3d wait over "):
            s["start_wait"] = msg[len("3d wait over "):]
        elif msg.startswith("waiting for the 3d "):
            s["waiting_3d"] = msg[len("waiting for the 3d "):]
        elif msg.startswith("fade in by="):
            if s["fade"] is None:                            # the script fades in once
                s["fade"] = msg[len("fade in "):]
        elif msg.startswith("guard "):
            s["guard"] = msg[len("guard "):]
        elif msg.startswith("mq101debug written="):
            s["mq101debug_written"] = msg[len("mq101debug written="):]
        elif msg.startswith("status "):
            s["last_status"] = msg
    return s


def log(a):
    with open(a.file, encoding="utf-8", errors="replace") as f:
        s = summarize(f)
    print(json.dumps(s, indent=1))
    return 0 if (200 in s["stages"] or 210 in s["stages"]) and not s["stood_down"] and not s["exit_failure"] else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    cr = os.path.join(STARFIELD, "Tools", "ContentResources.zip")
    pc = sub.add_parser("precheck")
    pc.add_argument("--content-resources", default=cr)
    pc.add_argument("--out", default=None)
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--cog-door", default=None, help="validated make_cog_door.py --production-cog stage; includes FO4SFVaultGearDoor.esm and its assets")
    s.add_argument("--exit-lift", default=None, help="validated make_anim_console.py --production-lift stage; enables the carrying ascent and includes its assets")
    s.add_argument("--fo4", required=True)
    s.add_argument("--port", required=True)
    s.add_argument("--port-ids", required=True)
    s.add_argument("--core", required=True)
    s.add_argument("--starfield", default=os.path.join(STARFIELD, "Data", "Starfield.esm"))
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--content-resources", default=cr)
    s.add_argument("--no-looks", dest="looks", action="store_false")
    s.add_argument("--race-menu-mode", type=int, default=None,
                   help=f"Game.ShowRaceMenu's uiMode for the looks script (default {DEFAULT_RACE_MENU_MODE}, looks only: "
                        f"body and face; {FULL_CREATOR_MODE} is the full creator with Starfield's backgrounds and traits)")
    s.add_argument("--no-special", dest="special", action="store_false",
                   help="no SPECIAL terminal: no FO4SF_NewGameSpecial script, AVIF or its two MESG")
    s.add_argument("--terminal-ref", default=None, help="the SPECIAL terminal in Vault111Cryo, FO4 hex id (default: the cell's terminals, nearest the pod first)")
    s.add_argument("--no-version", dest="version", action="store_false",
                   help="no save version check: no FO4SF_NewGameVersion script, player alias or GLOB")
    s.add_argument("--build-version", type=int, default=None,
                   help=f"the build's version number, GLOB FO4SF_NewGameVersion (default {DEFAULT_BUILD_VERSION})")
    s.add_argument("--hold", default=None, help=f"Starfield start quests to stop, by EditorID (default {','.join(DEFAULT_HOLD)})")
    s.add_argument("--omit-hold-group", choices=tuple(OMIT_HOLD_GROUPS), default=None,
                   help="narrowing flag omitting one Group 5 list from DEFAULT_HOLD: radiant (190), ships (178), or system (195)")
    s.add_argument("--mq101debug", type=float, default=None,
                   help=f"override GLOB MQ101Debug, experiments only (default: no override). MQ101 never runs with our own "
                        f"start, so it matters only when the start hands back to MQ101 (a New Game+, or no move into the vault): "
                        f"{DEBUG_INTRO} is the intro, {DEBUG_START_PIRATES} the pirate-fight developer start of 28 Oct run 1, "
                        f"{DEBUG_UNMATCHED} matched no entry and never left the loading screen (run 2)")
    s.add_argument("--no-mq101debug", action="store_true",
                   help="kept for old command lines: the default already writes no override; it still cancels a --mq101debug given with it")
    s.add_argument("--debug-after-hold", type=int, default=None,
                   help=f"the value the quest writes into MQ101Debug right after the hold-off's first pass (default "
                        f"{DEBUG_AFTER_HOLD}, the developer skip-start value, which opens the sustenance condition; 0 writes nothing)")
    s.add_argument("--pod-step", type=float, default=None, help=f"metres from the pod to the start point along the pod's facing (tool default {DEFAULT_POD_STEP})")
    s.add_argument("--pod-ref", default=None, help="the player's pod in Vault111Cryo, FO4 hex id (when points finds several)")
    s.add_argument("--keep-inventory", action="store_true",
                   help="no inventory reset: the player keeps what Starfield gives. By default the quest empties the "
                        "player's inventory once the player is confirmed in the vault, before stage 10 (NG-K8, S13 row 2; "
                        "whether quest items stay is unverified)")
    s.add_argument("--clear-inventory", action="store_true",
                   help="kept for old command lines: the default already empties the inventory")
    s.add_argument("--vault-suit", default=None, metavar="EDITORID",
                   help="the port's ARMO the script adds and equips after the reset, by EditorID (refused with --keep-inventory)")
    s.add_argument("--no-o2-fill", action="store_true",
                   help="no O2 capacity after the reset: with no suit the O2/CO2 dial then reads red (S13 row 2b; "
                        "on by default with the reset)")
    s.add_argument("--no-fade-hold", action="store_true",
                   help="disable pre-world start room setup and enter Vault 111 directly")
    s.add_argument("--start-choice-backdrop", choices=("empty_cell", "title_card", "setup_menu", "none"), default=None,
                   help="N2/S1 backdrop variant (R5): empty_cell (default), title_card (FO4SF_StartCardMenu), setup_menu (FO4SF_SetupMenu), or none")
    s.add_argument("--show-unavailable-starts", type=int, choices=(0, 1), default=0,
                   help="S3 unavailable-start policy: 0 leaves available:false rows off (default), 1 displays them greyed out on FO4SF_SetupMenu")
    s.add_argument("--warfare-starts", default=None,
                   help="path to warfare_starts.json (default: src/fo4sf/core/warfare_starts.json)")
    s.add_argument("--start-places", default=None,
                   help="path to start_places.json (default: src/fo4sf/core/start_places.json)")
    s.add_argument("--allow-temporary-anchor", action="store_true",
                   help="build on a port whose vault cell has no persistent reference: anchor on its temporary COC "
                        "marker, and the script centers on the cell first (unverified during our own start's first load, "
                        "and a centering that moves nobody hands nothing back; refused by default)")
    s.add_argument("--require-persistent-anchor", action="store_true",
                   help="kept for old command lines: the default since newgame_v11 already refuses a vault cell without "
                        "a persistent reference")
    v = sub.add_parser("verify")
    v.add_argument("--exp-dir", required=True)
    v.add_argument("--plan", required=True)
    v.add_argument("--port", default=None)
    v.add_argument("--core", default=None)
    fo = sub.add_parser("fold")
    fo.add_argument("--stage", required=True)
    fo.add_argument("--core-dir", required=True)
    fo.add_argument("--out", required=True)
    fo.add_argument("--port", default=None)
    fo.add_argument("--core", default=None)
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    a = p.parse_args(argv)
    return {"precheck": precheck, "stage": stage, "verify": verify, "fold": fold, "log": log}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
