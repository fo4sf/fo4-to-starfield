"""Read-only multi-title Fallout & Starfield quest, script, and shared-systems census tool.

Scans local read-only game installations without modifying any source file, launching any executable,
or extracting any copyrighted game prose/dialogue/descriptions. Outputs strictly numeric counts,
record/subrecord signatures, hex FormIDs, EditorIDs, and script/function/event identifiers.

Supported archive and binary formats (100% Python stdlib + fo4sf.ba2):
  - Classic Isometric:
      * Fallout 1 `DAT` v1 (big-endian directory tree + raw `0x20` / LZSS `0x40` block streams)
      * Fallout 2 `DAT` v2 (little-endian footer + zlib directory tree and entry streams)
      * Interplay SSL `.int` compiled bytecode (procedure table + `0x80A1..0x8155` engine opcodes)
      * Fallout Tactics `.bos` PKZIP archives + `.mis` `<world>` zlib FSM trigger/action streams
  - Bethesda TES4 / Creation Engine:
      * Streaming 24-byte `GRUP` & record walker (`0x00040000` zlib + `XXXX` 32-bit subrecords)
        across Fallout 3, Fallout: New Vegas, Fallout 4, Fallout 76, and Starfield `.esm` masters
      * BSA v104 (`0x68`) archive header, directory/file record, and `0x0100` embedded-name reader
      * Fallout 3 & New Vegas `SCPT` + embedded `SCTX` ObScript tokenizer (`Begin` blocks + GECK calls)
      * Fallout 4 & Starfield `.psc` source archive scanner (`Base.zip`, `DLC*.zip`, `ContentResources.zip`)
      * Fallout 4 (`v3.9`), Starfield (`v3.12`), and Fallout 76 (`v3.15`) `.pex` (`0xFA57C0DE`) header,
        string-table, and bytecode (`CallMethod` / `CallParent` / `CallStatic` / `Event`) walker
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import struct
import sys
import time
import zipfile
import zlib
from collections import Counter
from dataclasses import dataclass
from typing import BinaryIO, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from fo4sf.ba2 import Ba2  # noqa: E402

# ---------------------------------------------------------------------------
# Interplay SSL (.int) Engine Opcode Table (0x80A1..0x8155)
# Verified against Fallout 1 / Fallout 2 SSL VM registration order.
# ---------------------------------------------------------------------------
SSL_ENGINE_OPCODES: Dict[int, str] = {
    0x80A1: "give_exp_points",
    0x80A2: "scr_return",
    0x80A3: "play_sfx",
    0x80A4: "obj_name",
    0x80A5: "sfx_build_open_name",
    0x80A6: "get_pc_stat",
    0x80A7: "tile_contains_pid_obj",
    0x80A8: "set_map_start",
    0x80A9: "override_map_start",
    0x80AA: "has_skill",
    0x80AB: "using_skill",
    0x80AC: "roll_vs_skill",
    0x80AD: "skill_contest",
    0x80AE: "do_check",
    0x80AF: "is_success",
    0x80B0: "is_critical",
    0x80B1: "how_much",
    0x80B2: "mark_area_known",
    0x80B3: "reaction_influence",
    0x80B4: "random",
    0x80B5: "roll_dice",
    0x80B6: "move_to",
    0x80B7: "create_object_sid",
    0x80B8: "display_msg",
    0x80B9: "script_overrides",
    0x80BA: "obj_is_carrying_obj_pid",
    0x80BB: "tile_contains_obj_pid",
    0x80BC: "self_obj",
    0x80BD: "source_obj",
    0x80BE: "target_obj",
    0x80BF: "dude_obj",
    0x80C0: "obj_being_used_with",
    0x80C1: "local_var",
    0x80C2: "set_local_var",
    0x80C3: "map_var",
    0x80C4: "set_map_var",
    0x80C5: "global_var",
    0x80C6: "set_global_var",
    0x80C7: "script_action",
    0x80C8: "obj_type",
    0x80C9: "obj_item_subtype",
    0x80CA: "get_critter_stat",
    0x80CB: "set_critter_stat",
    0x80CC: "animate_stand_obj",
    0x80CD: "animate_stand_reverse_obj",
    0x80CE: "animate_move_obj_to_tile",
    0x80CF: "tile_in_tile_rect",
    0x80D0: "attack_complex",
    0x80D1: "terminate_combat",
    0x80D2: "tile_distance",
    0x80D3: "tile_distance_objs",
    0x80D4: "tile_num",
    0x80D5: "tile_num_in_direction",
    0x80D6: "pickup_obj",
    0x80D7: "drop_obj",
    0x80D8: "add_obj_to_inven",
    0x80D9: "rm_obj_from_inven",
    0x80DA: "wield_obj_critter",
    0x80DB: "use_obj",
    0x80DC: "obj_can_see_obj",
    0x80DD: "attack",
    0x80DE: "start_gdialog",
    0x80DF: "end_dialogue",
    0x80E0: "dialogue_reaction",
    0x80E1: "metarule3",
    0x80E2: "set_map_music",
    0x80E3: "set_obj_visibility",
    0x80E4: "load_map",
    0x80E5: "wm_area_set_pos",
    0x80E6: "set_exit_grids",
    0x80E7: "anim_busy",
    0x80E8: "critter_heal",
    0x80E9: "set_light_level",
    0x80EA: "game_time",
    0x80EB: "game_time_in_seconds",
    0x80EC: "elevation",
    0x80ED: "kill_critter",
    0x80EE: "kill_critter_type",
    0x80EF: "critter_dmg",
    0x80F0: "add_timer_event",
    0x80F1: "rm_timer_event",
    0x80F2: "game_ticks",
    0x80F3: "has_trait",
    0x80F4: "destroy_object",
    0x80F5: "obj_can_hear_obj",
    0x80F6: "game_time_hour",
    0x80F7: "fixed_param",
    0x80F8: "tile_is_visible",
    0x80F9: "cur_map_index",
    0x80FA: "action_being_used",
    0x80FB: "critter_state",
    0x80FC: "game_time_advance",
    0x80FD: "radiation_inc",
    0x80FE: "radiation_dec",
    0x80FF: "critter_attempt_placement",
    0x8100: "obj_pid",
    0x8101: "cur_town",
    0x8102: "critter_add_trait",
    0x8103: "critter_rm_trait",
    0x8104: "proto_data",
    0x8105: "message_str",
    0x8106: "critter_inven_obj",
    0x8107: "obj_set_light_level",
    0x8108: "world_map",
    0x8109: "inven_cmds",
    0x810A: "float_msg",
    0x810B: "metarule",
    0x810C: "anim",
    0x810D: "obj_carrying_pid_obj",
    0x810E: "reg_anim_func",
    0x810F: "reg_anim_animate",
    0x8110: "reg_anim_animate_reverse",
    0x8111: "reg_anim_obj_move_to_obj",
    0x8112: "reg_anim_obj_run_to_obj",
    0x8113: "reg_anim_obj_move_to_tile",
    0x8114: "reg_anim_obj_run_to_tile",
    0x8115: "play_gmovie",
    0x8116: "add_mult_objs_to_inven",
    0x8117: "rm_mult_objs_from_inven",
    0x8118: "gdialog_mod_barter",
    0x8119: "gdialog_get_barter_mod",
    0x811A: "explosion",
    0x811B: "days_since_visited",
    0x811C: "gsay_start",
    0x811D: "gsay_end",
    0x811E: "gsay_reply",
    0x811F: "gsay_option",
    0x8120: "gsay_message",
    0x8121: "giq_option",
    0x8122: "poison",
    0x8123: "get_poison",
    0x8124: "party_add",
    0x8125: "party_remove",
    0x8126: "reg_anim_animate_forever",
    0x8127: "critter_injure",
    0x8128: "combat_is_initialized",
    0x8129: "gdialog_barter",
    0x812A: "difficulty_level",
    0x812B: "running_burning_guy",
    0x812C: "inven_unwield",
    0x812D: "obj_is_locked",
    0x812E: "obj_lock",
    0x812F: "obj_unlock",
    0x8130: "obj_is_open",
    0x8131: "obj_open",
    0x8132: "obj_close",
    0x8133: "game_ui_disable",
    0x8134: "game_ui_enable",
    0x8135: "game_ui_is_disabled",
    0x8136: "gfade_out",
    0x8137: "gfade_in",
    0x8138: "item_caps_total",
    0x8139: "item_caps_adjust",
    0x813A: "anim_action_frame",
    0x813B: "reg_anim_play_sfx",
    0x813C: "critter_mod_skill",
    0x813D: "sfx_build_char_name",
    0x813E: "sfx_build_ambient_name",
    0x813F: "sfx_build_interface_name",
    0x8140: "sfx_build_item_name",
    0x8141: "sfx_build_weapon_name",
    0x8142: "sfx_build_scenery_name",
    0x8143: "attack_setup",
    0x8144: "destroy_mult_objs",
    0x8145: "use_obj_on_obj",
    0x8146: "dialogue_system_enter",
    0x8147: "move_obj_inven_to_obj",
    0x8148: "endgame_slideshow",
    0x8149: "obj_art_fid",
    0x814A: "art_anim",
    0x814B: "party_member_obj",
    0x814C: "rotation_to_tile",
    0x814D: "jam_lock",
    0x814E: "gdialog_set_barter_mod",
    0x814F: "combat_difficulty",
    0x8150: "obj_on_screen",
    0x8151: "critter_is_fleeing",
    0x8152: "critter_set_flee_state",
    0x8153: "terminate_combat_ext",
    0x8154: "debug_msg",
    0x8155: "critter_stop_attacking",
}

SSL_ENGINE_CALLBACKS = {
    "start",
    "critter_p_proc",
    "pickup_p_proc",
    "talk_p_proc",
    "destroy_p_proc",
    "look_at_p_proc",
    "description_p_proc",
    "use_p_proc",
    "use_obj_on_p_proc",
    "use_skill_on_p_proc",
    "damage_p_proc",
    "map_enter_p_proc",
    "map_exit_p_proc",
    "map_update_p_proc",
    "timed_event_p_proc",
    "combat_p_proc",
    "spatial_p_proc",
    "is_dropping_p_proc",
    "drop_p_proc",
    "push_p_proc",
    "combat_is_starting_p_proc",
    "combat_is_over_p_proc",
}

# ---------------------------------------------------------------------------
# Canonical GECK / ObScript Function Dictionary (FO3 & FNV)
# Includes short aliases mapped to canonical names so unit tests work offline.
# ---------------------------------------------------------------------------
CANONICAL_GECK_FUNCTIONS: Tuple[str, ...] = (
    "Activate", "AddAchievement", "AddFlames", "AddItem", "AddItemHealthPercent",
    "AddNote", "AddPerk", "AddReputation", "AddReputationExact", "AddScriptPackage",
    "AddSpecialAnimation", "AddSpell", "AddTagSkills", "AddToFaction", "AdvancePCLevel",
    "AdvancePCSkill", "AgeRace", "Autosave", "Cast", "CastImmediateOnSelf",
    "ClearActorsFactionsPlayerEnemyFlag", "ClearDestruction", "ClearFactionPlayerEnemyFlag",
    "ClearNoActivationSound", "ClearOpenState", "ClearOwnership", "CloseAllMenus",
    "CompleteAllObjectives", "CompleteQuest", "DamageActorValue", "DamageObject",
    "DamageWeapon", "DeactivateAllHighlights", "Disable", "DisableAllActors",
    "DisableLinkedPathPoints", "DisableNavMesh", "DisablePlayerControls", "Dispel",
    "DispelAllSpells", "Drop", "DropMe", "DuplicateAllItems", "DuplicateNPCStats",
    "Enable", "EnableFastTravel", "EnableLinkedPathPoints", "EnableNavMesh",
    "EnablePlayerControls", "EnterTrigger", "EquipItem", "EquipItem2", "EssentialDeathReload",
    "EvaluatePackage", "Exists", "ExitGame", "FadeSFX", "FireWeapon", "ForceActiveQuest",
    "ForceActorValue", "ForceFlee", "ForceRadioStationUpdate", "ForceTakeCover",
    "ForceTerminalBack", "ForceWeather", "FriendDispositionBoost", "GetActionRef",
    "GetActorCrimePlayerEnemy", "GetActorFactionPlayerEnemy", "GetActorValue",
    "GetAlarmed", "GetAmountSoldStolen", "GetAngle", "GetAnimAction", "GetArmorRating",
    "GetArmorRatingUpperBody", "GetAttacked", "GetBarterGold", "GetBaseActorValue",
    "GetBaseObject", "GetButtonPressed", "GetCannibal", "GetCauseofDeath", "GetClothingValue",
    "GetCombatTarget", "GetConcussed", "GetContainer", "GetCrime", "GetCrimeKnown",
    "GetCrosshairRef", "GetCurrentAIPackage", "GetCurrentAIProcedure", "GetCurrentTime",
    "GetCurrentWeatherPercent", "GetDayOfWeek", "GetDead", "GetDeadCount", "GetDefaultOpen",
    "GetDestroyed", "GetDestructionStage", "GetDetected", "GetDialogueEmotion",
    "GetDialogueEmotionValue", "GetDisabled", "GetDisease", "GetDisposition", "GetDistance",
    "GetEquipped", "GetFactionCombatReaction", "GetFactionRank", "GetFactionRankDifference",
    "GetFactionRelation", "GetFatiguePercentage", "GetForceRun", "GetForceSneak",
    "GetFriendHit", "GetFurnitureMarkerID", "GetGameSetting", "GetGlobalValue", "GetGold",
    "GetGroupMemberCount", "GetGroupTargetCount", "GetHasNote", "GetHeadingAngle",
    "GetHealthPercentage", "GetHelper", "GetHitLocation", "GetIgnoreCrime", "GetIgnoreFriendlyHits",
    "GetInCell", "GetInCellParam", "GetInFaction", "GetInSameCell", "GetInWorldspace",
    "GetInZone", "GetIsAlerted", "GetIsAlignment", "GetIsClass", "GetIsCreature",
    "GetIsCreatureType", "GetIsCurrentPackage", "GetIsCurrentWeather", "GetIsFormType",
    "GetIsGhost", "GetIsID", "GetIsLockBroken", "GetIsObjectType", "GetIsPlayableRace",
    "GetIsRace", "GetIsReference", "GetIsSex", "GetIsUsedItem", "GetIsUsedItemEquipType",
    "GetIsUsedItemType", "GetIsVoiceType", "GetItemCount", "GetKillingBlowLimb", "GetKnockedState",
    "GetLastHitCritical", "GetLastPlayerAction", "GetLevel", "GetLineOfSight", "GetLinkedRef",
    "GetLockLevel", "GetLocked", "GetMapMarkerVisible", "GetMinorCrimeCount", "GetMajorCrimeCount",
    "GetObjectiveCompleted", "GetObjectiveDisplayed", "GetObjectEffect", "GetOffersServicesNow",
    "GetOpenState", "GetOwnerLastTarget", "GetPackageTarget", "GetParentRef", "GetPCEnemyOfFaction",
    "GetPCExpelled", "GetPCFactionAttack", "GetPCFactionMurder", "GetPCInFaction", "GetPCIsClass",
    "GetPCIsRace", "GetPCIsSex", "GetPCMiscStat", "GetPCRank", "GetPCSleepHours",
    "GetPermanentActorValue", "GetPersuasionNumber", "GetPlantedExplosive", "GetPlayerAction",
    "GetPlayerControlsDisabled", "GetPlayerGrabbedRef", "GetPlayerName", "GetPlayerTeammate",
    "GetPlayerTeammateCount", "GetPos", "GetQuestCompleted", "GetQuestRunning", "GetQuestVariable",
    "GetRadiationLevel", "GetRandomPercent", "GetRefCount", "GetReputation", "GetReputationPct",
    "GetReputationThreshold", "GetRestrained", "GetScale", "GetScriptVariable", "GetSecondsPassed",
    "GetSelf", "GetShouldAttack", "GetSitting", "GetSleeping", "GetStage", "GetStageDone",
    "GetStartingAngle", "GetStartingPos", "GetTalkedToPC", "GetTalkedToPCParam", "GetThreatRatio",
    "GetTimeDead", "GetTotalPersuasionNumber", "GetTrespassWarningLevel", "GetUnconscious",
    "GetUsedItemActivate", "GetUsedItemLevel", "GetVampire", "GetVATSMode", "GetVATSValue",
    "GetWalkSpeed", "GetWeaponAnimType", "GetWeaponHealthPerc", "GetWeaponType", "GetWindSpeed",
    "GetXPForNextLevel", "HasEffectShader", "HasFlames", "HasLoaded3D", "HasMagicEffect",
    "HasPerk", "HasFriendDisposition", "HolsterWeapon", "IgnoreCrime", "imod",
    "IncrementPlayerSkillUse", "IsActionRef", "IsActor", "IsActorAVictim", "IsActorEvil",
    "IsActorTalkingThroughActivator", "IsActorUsingATorch", "IsAnimPlaying", "IsCellOwner",
    "IsChild", "IsCloudy", "IsCombatTarget", "IsCompassHostile", "IsContinuingPackagePCNear",
    "IsCurrentFurnitureObj", "IsCurrentFurnitureRef", "IsEssential", "IsFacingUp",
    "IsGoreDisabled", "IsGreetingPlayer", "IsGuard", "IsHardcore", "IsHorseStolen",
    "IsIdlePlaying", "IsImageSpaceActive", "IsInCombat", "IsInCriticalStage",
    "IsInDangerousWater", "IsInInterior", "IsInList", "IsInMyOwnedCell", "IsKiller",
    "IsKillerObject", "IsLastIdlePlayed", "IsLeftUp", "IsLimbGone", "IsLoadDoor",
    "IsMoving", "IsOwner", "IsPC1stPerson", "IsPCAMurderer", "IsPCSleeping",
    "IsPlayerActionActive", "IsPlayerGrabbedRef", "IsPlayerInRegion", "IsPlayerMovingIntoNewSpace",
    "IsPlayerTagSkill", "IsPlayersLastRiddenHorse", "IsPleasant", "IsPS3", "IsRaining",
    "IsRidingHorse", "IsRunning", "IsSameEditorLocAsRef", "IsScripted", "IsShieldOut",
    "IsSneaking", "IsSnowing", "IsSpellTarget", "IsSwimming", "IsTalking",
    "IsTalkingActivatorActor", "IsTimePassing", "IsTorchOut", "IsTrespassing", "IsTurning",
    "IsUndead", "IsWaterObject", "IsWaiting", "IsWeaponInList", "IsWeaponOut",
    "IsWeaponSkillType", "IsWin32", "IsXBox", "Kill", "KillActor", "KillAllActors",
    "Lock", "LoopGroup", "MarkForDelete", "MatchFaceGeometry", "MatchRace", "MenuMode",
    "ModActorValue", "ModAmountSoldStolen", "ModBarterGold", "ModDisposition", "ModFactionRank",
    "ModFactionReaction", "ModPCAttribute", "ModPCMiscStat", "ModPCSkill", "ModScale",
    "ModWeaponHealthPerc", "MoveTo", "MoveToMarker", "MoveToMarkerWithFade", "OpenTeammateContainer",
    "PickIdle", "PipBoyRadio", "PipBoyRadioOff", "PlaceAtMe", "PlaceAtMeHealthPercent",
    "PlaceLeveledActorAtMe", "PlayBink", "PlayGroup", "PlayIdle", "PlayMagicEffectVisuals",
    "PlayMagicShaderVisuals", "PlayMusic", "PlaySound", "PlaySound3D", "PreloadMagicEffect",
    "PurgeCellBuffers", "PushActorAway", "ReleaseWeatherOverride", "RemoveAllItems",
    "RemoveAllTypedItems", "RemoveFlames", "RemoveFromAllFactions", "RemoveFromFaction",
    "RemoveImageSpaceModifier", "RemoveItem", "RemoveItemTarget", "RemoveMe", "RemoveMerchantContainer",
    "RemoveNote", "RemovePerk", "RemoveRecurringFromChallenge", "RemoveReputation",
    "RemoveReputationExact", "RemoveScriptPackage", "RemoveSpell", "Reset3DState",
    "ResetAI", "ResetFallDamageTimer", "ResetHealth", "ResetInterior", "ResetPipboyManager",
    "ResetQuest", "RestoreActorValue", "Resurrect", "ResurrectActor", "RewardKarma",
    "RewardXP", "rimod", "Rotate", "SameFaction", "SameFactionAsPC", "SameRace",
    "SameRaceAsPC", "SameSex", "SameSexAsPC", "Say", "SayTo", "ScriptEffectElapsedSeconds",
    "Search", "SendAssaultAlarm", "SendSheriffsToJail", "SendTrespassAlarm", "SetActorAlpha",
    "SetActorFullName", "SetActorRefraction", "SetActorValue", "SetAlert", "SetAllReachable",
    "SetAllVisible", "SetAlly", "SetAngle", "SetAtStart", "SetAudioMultithreading",
    "SetBarterGold", "SetBroadcastState", "SetCameraShake", "SetCanUsePowerArmor",
    "SetCellFullName", "SetCellImageSpace", "SetCellOwnership", "SetCellPublicFlag",
    "SetClass", "SetCombatStyle", "SetCriticalStage", "SetDefaultOpen", "SetDestroyed",
    "SetDisposition", "SetEnemy", "SetEssential", "SetFactionRank", "SetForceRun",
    "SetForceSneak", "SetGhost", "SetGlobalTimeMultiplier", "SetIgnoreFriendlyHits",
    "SetImageSpace", "SetInCharGen", "SetItemValue", "SetLastExtDoorActivated",
    "SetLevel", "SetLocationSpecificLoadScreensOnly", "SetMerchantContainer", "SetMinimalUse",
    "SetName", "SetNoActivationSound", "SetNoAvoidance", "SetNoRumors", "SetNPCRadio",
    "SetNumericGameSetting", "SetObjectiveCompleted", "SetObjectiveDisplayed", "SetOpenState",
    "SetOwnership", "SetPackDuration", "SetPCEnemyOfFaction", "SetPCExpelled",
    "SetPCFactionAttack", "SetPCFactionMurder", "SetPCYoung", "SetPlayerTagSkill",
    "SetPlayerTeammate", "SetPos", "SetQuestDelay", "SetQuestObject", "SetReputation",
    "SetRestrained", "SetRigidBodyMass", "SetRumble", "SetScale", "SetSceneIsComplex",
    "SetShowQuestItems", "SetSize", "SetSpecialPoints", "SetStage", "SetTagSkills",
    "SetTalkingActivatorActor", "SetTerminalMenuPos", "SetToDefault", "SetUnconscious",
    "SetVATSValue", "SetWeather", "SetWeaponHealthPerc", "SetZoneRespawns", "SexChange",
    "ShowBarberMenu", "ShowBlacksmithMenu", "ShowBarterMenu", "ShowCaravanMenu",
    "ShowChargenMenu", "ShowChargenMenuModValues", "ShowChargenMenuParams", "ShowClassMenu",
    "ShowComputersInterface", "ShowDialogSubtitles", "ShowHackingMiniGame", "ShowLockpickMenu",
    "ShowLockpickMenuDebug", "ShowLoveTesterMenuParams", "ShowMap", "ShowMessage",
    "ShowNameMenu", "ShowPlasticSurgeonMenu", "ShowQuestStages", "ShowQuestVars",
    "ShowRaceMenu", "ShowRecipeMenu", "ShowRepairMenu", "ShowSelectCompanionMenu",
    "ShowSpellMaking", "ShowTraitMenu", "ShowTutorialMenu", "ShowViewerStrings",
    "ShowWarning", "Sin", "Sqrt", "StartCannibal", "StartCombat", "StartConversation",
    "StartMisterSandman", "StartQuest", "StartRadioConversation", "StopCombat",
    "StopCombatAlarmOnActor", "StopLook", "StopMagicEffectVisuals", "StopMagicShaderVisuals",
    "StopQuest", "StopWaiting", "StreamMusic", "SwapTexture", "Tan", "TriggerHUDShudder",
    "TriggerHitShader", "TriggerScreenBlood", "TrapUpdate", "TurnOffFire", "UnEquipItem",
    "Unlock", "UseWeapon", "WakeUpPC", "WhichServiceMenu",
)

GECK_SHORT_ALIASES: Dict[str, str] = {
    "evp": "EvaluatePackage",
    "getav": "GetActorValue",
    "setav": "SetActorValue",
    "modav": "ModActorValue",
    "forceav": "ForceActorValue",
    "damageav": "DamageActorValue",
    "restoreav": "RestoreActorValue",
    "getbaseav": "GetBaseActorValue",
    "getpermav": "GetPermanentActorValue",
    "movetomarker": "MoveTo",
    "pmod": "ModPCMiscStat",
    "saa": "SetActorAlpha",
    "playidle": "PlayIdle",
    "cios": "CastImmediateOnSelf",
    "additem": "AddItem",
    "removeitem": "RemoveItem",
    "imod": "ApplyImageSpaceModifier",
    "rimod": "RemoveImageSpaceModifier",
}

GECK_LOOKUP: Dict[str, str] = {fn.lower(): fn for fn in CANONICAL_GECK_FUNCTIONS}
GECK_LOOKUP.update(GECK_SHORT_ALIASES)

# CTDA function ID categories (TES4/FO3/FNV vs FO4/FO76/Starfield)
CTDA_NAMES_FO3NV: Dict[int, str] = {
    1: "GetDistance",
    5: "GetLocked",
    12: "GetSecondsPassed",
    14: "GetActorValue",
    18: "GetCurrentTime",
    24: "GetScale",
    27: "GetLineOfSight",
    32: "GetInSameCell",
    35: "GetDisabled",
    36: "MenuMode",
    39: "GetDisease",
    42: "GetClothingValue",
    43: "SameFaction",
    44: "SameRace",
    45: "SameSex",
    46: "GetDead",
    47: "GetItemCount",
    48: "GetGold",
    49: "GetSleeping",
    50: "GetTalkedToPC",
    53: "GetScriptVariable",
    56: "GetQuestRunning",
    58: "GetStage",
    59: "GetStageDone",
    60: "GetFactionRankDifference",
    61: "GetAlarmed",
    67: "GetInCell",
    68: "GetIsClass",
    69: "GetIsRace",
    70: "GetIsSex",
    71: "GetInFaction",
    72: "GetIsID",
    73: "GetFactionRank",
    74: "GetGlobalValue",
    79: "GetQuestVariable",
    80: "GetLevel",
    84: "GetDeadCount",
    98: "GetRandomPercent",
    106: "IsWeaponOut",
    122: "GetCrime",
    127: "HasMagicEffect",
    136: "GetIsReference",
    149: "GetIsCurrentWeather",
    172: "IsPCAMurderer",
    180: "GetIsCurrentPackage",
    223: "IsSpellTarget",
    242: "GetBaseActorValue",
    246: "IsOwner",
    258: "IsWorn",
    285: "IsSwimming",
    289: "IsInCombat",
    300: "IsInInterior",
    314: "IsActorEvil",
    365: "IsChild",
    427: "GetIsVoiceType",
    448: "HasPerk",
    449: "GetFactionRelation",
    454: "GetPlayerTeammate",
    455: "GetPlayerTeammateCount",
    492: "GetMapMarkerVisible",
    515: "IsCombatTarget",
    598: "GetReputation",
    599: "GetReputationPct",
    600: "GetReputationThreshold",
    601: "IsHardcore",
}

CTDA_NAMES_CE2: Dict[int, str] = {
    **CTDA_NAMES_FO3NV,
    14: "GetValue",
    242: "GetBaseValue",
    598: "GetLocationCleared",
    812: "LocationHasKeyword",
    560: "HasKeyword",
}

# Starfield protected cold-start quests (from CF-2 / dotnet/NewGame/Program.cs)
STARFIELD_PROTECTED_QUESTS: Tuple[str, ...] = (
    # 5 Warfare squad & follower plumbing quests:
    "SQ_Followers",
    "SQ_Groups",
    "SQ_COM_CREW_AngerCombatOverride",
    "SQ_Captive",
    "SQ_Airlock",
    # 7 Core engine plumbing quests:
    "SQ_PlayerShip",
    "SQ_Parent",
    "PlayerSkills",
    "DialogueGeneric",
    "DialogueGenericPlayer",
    "SpeechChallenge",
    "Achievements_Quest",
)

# Official vanilla plugin manifests (prevents counting local experiment or CC plugins)
OFFICIAL_ESMS: Dict[str, Tuple[str, ...]] = {
    "FO3": (
        "Fallout3.esm",
        "Anchorage.esm",
        "ThePitt.esm",
        "BrokenSteel.esm",
        "PointLookout.esm",
        "Zeta.esm",
    ),
    "FNV": (
        "FalloutNV.esm",
        "DeadMoney.esm",
        "HonestHearts.esm",
        "OldWorldBlues.esm",
        "LonesomeRoad.esm",
        "GunRunnersArsenal.esm",
        "CaravanPack.esm",
        "ClassicPack.esm",
        "MercenaryPack.esm",
        "TribalPack.esm",
    ),
    "FO4": (
        "Fallout4.esm",
        "DLCRobot.esm",
        "DLCworkshop01.esm",
        "DLCworkshop02.esm",
        "DLCworkshop03.esm",
        "DLCCoast.esm",
        "DLCNukaWorld.esm",
    ),
    "FO76": (
        "SeventySix.esm",
        "NW.esm",
    ),
    "SF": (
        "Starfield.esm",
        "BlueprintShips-Starfield.esm",
        "SFBGS003.esm",
        "SFBGS004.esm",
        "SFBGS006.esm",
        "SFBGS007.esm",
        "SFBGS008.esm",
        "SFBGS00D.esm",
        "SFBGS047.esm",
    ),
}

SHARED_SYSTEM_SIGS: Tuple[str, ...] = (
    "FACT", "REPU", "PERK", "AVIF", "GLOB", "GPOF", "BPTD",
    "AMMO", "AMEF", "RCPE", "COBJ", "CMPO", "IRES", "IMOD",
    "OMOD", "PACK", "HAZD", "WATR", "FURN", "RACE", "WRLD",
    "CELL", "LCTN", "CAMS", "CPTH", "DMGT", "PCRD", "LOUT",
)

# Job 4 target quests (20 FO3 + 20 FNV = 40 quests)
FO3_MAIN_10: Tuple[str, ...] = (
    "CG01", "CG02", "CG03", "CG04",
    "MQ01", "MQ02", "MQ03", "MQ04", "MQ05", "MQ06",
)
FO3_SIDE_10: Tuple[str, ...] = (
    "MS01", "MS02", "MS03", "MS04", "MS05",
    "MS06", "MS08", "MS09", "MS10", "MS11",
)
FNV_MAIN_10: Tuple[str, ...] = (
    "VCG01", "VCG02", "VMQ01", "VMQTops", "VMQHouse1",
    "VMQYesMan01", "VMQ02", "VMQ03a", "VMQ04", "VMQ05",
)
FNV_SIDE_10: Tuple[str, ...] = (
    "VMS16", "VMS16b", "VMS02", "VMS33", "VMS44",
    "VMS53", "VMS01", "VMS03", "VMS20", "VMS29",
)


# ===========================================================================
# 1. Classic Isometric Readers: Fallout 1 DAT v1, Fallout 2 DAT v2, SSL .INT
# ===========================================================================
def fo1_lzss_decompress(data: bytes, expected_unpacked: int) -> bytes:
    """Decompress a Fallout 1 DAT v1 (`attrs == 0x40`) LZSS block stream."""
    out = bytearray()
    pos = 0
    n = len(data)
    ring = bytearray(b" " * 4096)
    while pos + 2 <= n and len(out) < expected_unpacked:
        hdr = struct.unpack_from(">h", data, pos)[0]
        pos += 2
        if hdr == 0:
            break
        if hdr < 0:
            raw_len = -hdr
            out.extend(data[pos : pos + raw_len])
            pos += raw_len
        else:
            block_end = min(n, pos + hdr)
            ring[:] = b" " * 4096
            r = 4078
            flags = 0
            while pos < block_end and len(out) < expected_unpacked:
                flags >>= 1
                if not (flags & 0x100):
                    flags = data[pos] | 0xFF00
                    pos += 1
                if flags & 1:
                    if pos >= block_end:
                        break
                    c = data[pos]
                    pos += 1
                    out.append(c)
                    ring[r] = c
                    r = (r + 1) & 0xFFF
                else:
                    if pos + 1 >= block_end:
                        break
                    b1 = data[pos]
                    b2 = data[pos + 1]
                    pos += 2
                    offset = b1 | ((b2 & 0xF0) << 4)
                    length = (b2 & 0x0F) + 3
                    for k in range(length):
                        c = ring[(offset + k) & 0xFFF]
                        out.append(c)
                        ring[r] = c
                        r = (r + 1) & 0xFFF
                        if len(out) >= expected_unpacked:
                            break
    return bytes(out)


@dataclass(frozen=True)
class DatEntry:
    name: str
    compressed: bool
    offset: int
    unpacked_size: int
    packed_size: int


class Fo1DatReader:
    """Big-endian Fallout 1 DAT v1 archive reader."""

    def __init__(self, path_or_stream: str | BinaryIO):
        if isinstance(path_or_stream, str):
            self._owned = True
            self._fp: BinaryIO = open(path_or_stream, "rb")
        else:
            self._owned = False
            self._fp = path_or_stream

        self._fp.seek(0)
        hdr = self._fp.read(16)
        if len(hdr) != 16:
            raise ValueError("Truncated FO1 DAT v1 header")
        dir_count = struct.unpack(">IIII", hdr)[0]
        dirs: List[str] = []
        for _ in range(dir_count):
            nlen_b = self._fp.read(1)
            if not nlen_b:
                raise ValueError("Truncated FO1 DAT directory name length")
            dirs.append(self._fp.read(nlen_b[0]).decode("latin-1", "replace"))

        self.entries: List[DatEntry] = []
        self._index: Dict[str, DatEntry] = {}
        for d in dirs:
            thdr = self._fp.read(16)
            if len(thdr) != 16:
                raise ValueError("Truncated FO1 DAT directory table header")
            fcnt = struct.unpack(">IIII", thdr)[0]
            for _ in range(fcnt):
                flen = self._fp.read(1)[0]
                fname = self._fp.read(flen).decode("latin-1", "replace")
                attrs, off, unp, pck = struct.unpack(">IIII", self._fp.read(16))
                full = fname if d in ("", ".") else f"{d}\\{fname}"
                norm = full.replace("/", "\\").lstrip(".\\")
                ent = DatEntry(
                    name=norm,
                    compressed=bool(attrs & 0x40),
                    offset=off,
                    unpacked_size=unp,
                    packed_size=pck if (attrs & 0x40) else unp,
                )
                self.entries.append(ent)
                self._index[norm.lower()] = ent

    def close(self) -> None:
        if self._owned:
            self._fp.close()

    def __enter__(self) -> "Fo1DatReader":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def read(self, name: str) -> bytes:
        key = name.replace("/", "\\").lstrip(".\\").lower()
        ent = self._index[key]
        self._fp.seek(ent.offset)
        if ent.compressed:
            raw = self._fp.read(ent.packed_size)
            return fo1_lzss_decompress(raw, ent.unpacked_size)
        return self._fp.read(ent.unpacked_size)


class Fo2DatReader:
    """Little-endian Fallout 2 DAT v2 archive reader."""

    def __init__(self, path_or_stream: str | BinaryIO):
        if isinstance(path_or_stream, str):
            self._owned = True
            self._fp: BinaryIO = open(path_or_stream, "rb")
        else:
            self._owned = False
            self._fp = path_or_stream

        self._fp.seek(0, os.SEEK_END)
        actual_size = self._fp.tell()
        if actual_size < 12:
            raise ValueError("Truncated FO2 DAT v2 archive")
        self._fp.seek(actual_size - 8)
        tree_size, dat_size = struct.unpack("<II", self._fp.read(8))
        if dat_size > actual_size or tree_size + 8 > dat_size:
            raise ValueError(f"Invalid FO2 DAT v2 footer (tree={tree_size}, dat={dat_size}, actual={actual_size})")
        self._fp.seek(dat_size - 8 - tree_size)
        fcnt = struct.unpack("<I", self._fp.read(4))[0]
        tree_buf = self._fp.read(tree_size - 4)
        pos = 0
        self.entries: List[DatEntry] = []
        self._index: Dict[str, DatEntry] = {}
        for _ in range(fcnt):
            nlen = struct.unpack_from("<I", tree_buf, pos)[0]
            pos += 4
            name = tree_buf[pos : pos + nlen].decode("latin-1", "replace").replace("/", "\\")
            pos += nlen
            comp, unp, pck, off = struct.unpack_from("<BIII", tree_buf, pos)
            pos += 13
            ent = DatEntry(
                name=name,
                compressed=bool(comp),
                offset=off,
                unpacked_size=unp,
                packed_size=pck if comp else unp,
            )
            self.entries.append(ent)
            self._index[name.lower()] = ent

    def close(self) -> None:
        if self._owned:
            self._fp.close()

    def __enter__(self) -> "Fo2DatReader":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def read(self, name: str) -> bytes:
        key = name.replace("/", "\\").lower()
        ent = self._index[key]
        self._fp.seek(ent.offset)
        raw = self._fp.read(ent.packed_size)
        return zlib.decompress(raw) if ent.compressed else raw


def parse_ssl_int(raw: bytes) -> Dict[str, object]:
    """Parse an Interplay compiled SSL `.int` binary for procedure & engine-opcode counts."""
    if len(raw) < 46:
        return {"procedures": 0, "callbacks": Counter(), "opcodes": Counter()}
    proc_cnt = struct.unpack_from(">I", raw, 42)[0]
    pos = 46
    if pos + proc_cnt * 24 + 4 > len(raw):
        return {"procedures": 0, "callbacks": Counter(), "opcodes": Counter()}

    procs = [struct.unpack_from(">IIIIII", raw, pos + i * 24) for i in range(proc_cnt)]
    ib_pos = pos + proc_cnt * 24
    ib_sz = struct.unpack_from(">I", raw, ib_pos)[0]
    ib_end = min(len(raw), ib_pos + 4 + ib_sz)
    ident_region = raw[ib_pos:ib_end]

    callbacks: Counter = Counter()
    body_offsets: List[int] = []
    for name_off, _flg, _dly, _coff, boff, _nargs in procs:
        if 0 < boff < len(raw):
            body_offsets.append(boff)
        if 4 <= name_off < len(ident_region):
            nul = ident_region.find(0, name_off)
            end_i = nul if nul >= 0 else len(ident_region)
            pname = ident_region[name_off:end_i].decode("latin-1", "replace").strip().lower()
            if pname in SSL_ENGINE_CALLBACKS or pname.endswith("_p_proc"):
                callbacks[f"proc:{pname}"] += 1

    opcodes: Counter = Counter()
    if body_offsets:
        ip = min(body_offsets)
        n = len(raw)
        while ip + 2 <= n:
            op = struct.unpack_from(">H", raw, ip)[0]
            ip += 2
            if op in (0xC001, 0x9801, 0x9001, 0xA001):
                ip += 4
            elif op in SSL_ENGINE_OPCODES:
                opcodes[SSL_ENGINE_OPCODES[op]] += 1
            elif 0x80A1 <= op <= 0x8200:
                opcodes[f"ssl_op_0x{op:04X}"] += 1

    return {
        "procedures": proc_cnt,
        "callbacks": callbacks,
        "opcodes": opcodes,
    }


MSG_ID_RE = re.compile(rb"\{\s*(\d+)\s*\}")
GAM_VAR_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:=", re.MULTILINE)


def _count_msg_entries(raw: bytes) -> int:
    # Count `{numeric_id}` entries without decoding or storing any message string text
    count = 0
    for line in raw.splitlines():
        s = line.lstrip()
        if s.startswith(b"{") and not s.startswith(b"#"):
            if MSG_ID_ID := MSG_ID_RE.match(s):
                _ = MSG_ID_ID
                count += 1
    return count


def _parse_map_header_fo12(raw: bytes) -> Dict[str, int]:
    if len(raw) < 236:
        return {"version": 0, "local_vars": 0, "global_vars": 0, "script_id": -1}
    ver = struct.unpack_from(">I", raw, 0)[0]
    # Header: ver(4), map_name(16), def_pos(4), def_elev(4), def_ori(4), num_local_vars(4 @ 32),
    # script_id(4 @ 36), flags(4 @ 40), darkness(4 @ 44), num_global_vars(4 @ 48), map_id(4 @ 52)
    num_lvars, script_id, flags, _dark, num_mvars = struct.unpack_from(">iiiii", raw, 32)
    elevs = 3 - bin((flags >> 1) & 0x7).count("1")
    return {
        "version": ver,
        "local_vars": max(0, num_lvars),
        "map_vars": max(0, num_mvars),
        "script_id": script_id,
        "elevations": max(1, elevs),
    }


ITEM_SUBTYPE_NAMES = {
    0: "armor",
    1: "container",
    2: "drug",
    3: "weapon",
    4: "ammo",
    5: "misc_item",
    6: "key",
}


def scan_classic_dat_set(
    readers: Sequence[Tuple[str, Fo1DatReader | Fo2DatReader]],
    title_key: str,
) -> Dict[str, object]:
    """Scan a layered set of FO1 or FO2 `.dat` archives (counts and identifiers only)."""
    archive_stats = []
    merged: Dict[str, Tuple[str, Fo1DatReader | Fo2DatReader, DatEntry]] = {}
    override_count = 0
    for label, rdr in readers:
        archive_stats.append({"archive": label, "entries": len(rdr.entries)})
        for ent in rdr.entries:
            k = ent.name.lower()
            if k in merged:
                override_count += 1
            merged[k] = (label, rdr, ent)

    ext_counts: Counter = Counter()
    pro_categories: Counter = Counter()
    item_subtypes: Counter = Counter()
    msg_files = 0
    msg_entries = 0
    dialog_msg_files = 0
    int_scripts = 0
    total_procs = 0
    func_freq: Counter = Counter()
    gam_files = 0
    vault13_gvars = 0
    map_mvars_total = 0
    map_files = 0
    map_scripts_attached = 0
    quests_txt_rows = 0
    quests_txt_locations = set()
    data_table_rows: Dict[str, int] = {}

    for k, (_lbl, rdr, ent) in sorted(merged.items()):
        ext = os.path.splitext(k)[1].lower()
        ext_counts[ext] += 1
        if ext == ".int":
            int_scripts += 1
            raw = rdr.read(ent.name)
            res = parse_ssl_int(raw)
            total_procs += int(res["procedures"])
            func_freq.update(res["callbacks"])
            func_freq.update(res["opcodes"])
        elif ext == ".msg":
            # Only count primary English table entries to avoid multi-language inflation if present
            if "\\french\\" in k or "\\german\\" in k or "\\spanish\\" in k:
                continue
            msg_files += 1
            if "\\dialog\\" in k:
                dialog_msg_files += 1
            raw = rdr.read(ent.name)
            msg_entries += _count_msg_entries(raw)
        elif ext == ".gam":
            gam_files += 1
            txt = rdr.read(ent.name).decode("latin-1", "replace")
            n_vars = len(GAM_VAR_RE.findall(txt))
            if k.endswith("data\\vault13.gam"):
                vault13_gvars = n_vars
            else:
                map_mvars_total += n_vars
        elif ext == ".map":
            map_files += 1
            hdr = _parse_map_header_fo12(rdr.read(ent.name))
            if hdr["script_id"] >= 0:
                map_scripts_attached += 1
        elif ext == ".pro":
            parts = k.split("\\")
            cat = parts[1] if len(parts) >= 3 and parts[0] == "proto" else "other"
            pro_categories[cat] += 1
            if cat == "items":
                raw = rdr.read(ent.name)
                if len(raw) >= 36:
                    sub_id = struct.unpack_from(">I", raw, 32)[0]
                    item_subtypes[ITEM_SUBTYPE_NAMES.get(sub_id, f"subtype_{sub_id}")] += 1
        elif k in (
            "data\\quests.txt",
            "data\\karmavar.txt",
            "data\\genrep.txt",
            "data\\party.txt",
            "data\\city.txt",
        ):
            raw = rdr.read(ent.name).decode("latin-1", "replace")
            active = [
                ln.strip()
                for ln in raw.splitlines()
                if ln.strip() and not ln.strip().startswith(("#", ";", "//"))
            ]
            tname = os.path.basename(k)
            data_table_rows[tname] = len(active)
            if k == "data\\quests.txt":
                quests_txt_rows = len(active)
                for ln in active:
                    cols = [c.strip() for c in ln.split(",")]
                    if cols and cols[0].isdigit():
                        quests_txt_locations.add(int(cols[0]))

    top_40 = [{"name": name, "count": cnt} for name, cnt in func_freq.most_common(40)]
    return {
        "title": title_key,
        "archives": archive_stats,
        "unique_entries": len(merged),
        "override_entries": override_count,
        "extensions": dict(ext_counts.most_common(25)),
        "quests": {
            "vault13_gam_gvars": vault13_gvars,
            "quests_txt_rows": quests_txt_rows,
            "quests_txt_distinct_locations": len(quests_txt_locations),
            "gam_files": gam_files,
            "map_mvars_total": map_mvars_total,
            "msg_files_english": msg_files,
            "dialog_msg_files_english": dialog_msg_files,
            "msg_entries_english": msg_entries,
            "maps": map_files,
            "maps_with_header_script": map_scripts_attached,
        },
        "scripts": {
            "runtime": "Interplay SSL VM (.int big-endian stack bytecode)",
            "compiled_int_count": int_scripts,
            "ssl_source_count": 0,
            "total_procedures": total_procs,
            "distinct_functions_and_events": len(func_freq),
            "top_40": top_40,
        },
        "shared_systems": {
            "prototypes_by_category": dict(pro_categories),
            "item_prototypes_by_subtype": dict(item_subtypes),
            "data_tables": data_table_rows,
        },
    }


# ===========================================================================
# 2. Fallout Tactics Reader (.bos PKZIP + .mis <world> zlib FSM walker)
# ===========================================================================
TACTICS_CVAR_RE = re.compile(rb"\b(CVAR_[A-Za-z0-9_]+|M[0-9]{2}_[A-Za-z0-9_]+)\b")


def parse_tactics_mis_bytes(raw: bytes) -> Dict[str, object]:
    """Decompress a Fallout Tactics `.mis` mission file and count FSM triggers, actions, and variables."""
    if not raw.startswith(b"<world>"):
        return {"triggers": 0, "game_events": 0, "speech_nodes": 0, "fsm_nodes": Counter(), "vars": set()}
    zidx = raw.find(b"\x78\x9c", 8, 64)
    if zidx < 0:
        zidx = raw.find(b"\x78\xda", 8, 64)
    dec = zlib.decompress(raw[zidx:]) if zidx >= 0 else raw

    triggers = dec.count(b"<Trigger>\x00")
    game_events = dec.count(b"<gameEvent>\x00")
    speech_nodes = dec.count(b"<speech_node>\x00")
    objectives_add = dec.count(b"Add Objective<esh>\x00")

    fsm_nodes: Counter = Counter()
    # Every FSM action/condition before `<esh>\x00` is framed as `<uint32_le_len><ASCII_Name><esh>\x00`
    needle = b"<esh>\x00"
    start = 0
    while True:
        idx = dec.find(needle, start)
        if idx < 0:
            break
        start = idx + len(needle)
        # Check candidate lengths 3..48 immediately preceding `idx`
        matched_name = None
        max_len = min(48, idx - 4)
        for cand_len in range(3, max_len + 1):
            lpos = idx - cand_len - 4
            decl_len = struct.unpack_from("<I", dec, lpos)[0]
            if decl_len == cand_len:
                cand_bytes = dec[idx - cand_len : idx]
                if all(32 <= b <= 122 for b in cand_bytes):
                    s = cand_bytes.decode("ascii")
                    if re.match(r"^[A-Za-z][A-Za-z0-9 _/-]+$", s):
                        matched_name = s.strip()
                        break
        if matched_name:
            fsm_nodes[matched_name] += 1

    vars_found = {m.group(1).decode("ascii") for m in TACTICS_CVAR_RE.finditer(dec)}
    return {
        "triggers": triggers,
        "game_events": game_events,
        "speech_nodes": speech_nodes,
        "add_objective_actions": objectives_add,
        "fsm_nodes": fsm_nodes,
        "vars": vars_found,
    }


def scan_tactics_bos_archives(bos_paths: Sequence[str]) -> Dict[str, object]:
    """Scan Fallout Tactics `.bos` PKZIP archives for missions, FSM nodes, entities, and tables."""
    ext_counts: Counter = Counter()
    ent_categories: Counter = Counter()
    mis_by_group: Counter = Counter()
    fsm_freq: Counter = Counter()
    campaign_vars: set = set()
    total_entries = 0
    total_triggers = 0
    total_game_events = 0
    total_speech_nodes = 0
    total_objectives = 0
    scb_files = 0
    locale_table_counts: Dict[str, int] = {}
    seen_mis: set = set()
    seen_ent: set = set()

    for zp in sorted(bos_paths):
        with zipfile.ZipFile(zp, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                total_entries += 1
                norm = info.filename.replace("\\", "/").lstrip("/")
                low = norm.lower()
                ext = os.path.splitext(low)[1]
                ext_counts[ext] += 1
                if ext == ".scb":
                    scb_files += 1
                elif ext == ".ent" and low not in seen_ent:
                    seen_ent.add(low)
                    parts = norm.split("/")
                    cat = parts[1] if len(parts) >= 3 and parts[0].lower() == "entities" else parts[0]
                    ent_categories[cat] += 1
                elif ext == ".mis" and low not in seen_mis:
                    seen_mis.add(low)
                    if "/core/" in low:
                        mis_by_group["campaign_core"] += 1
                    elif "/random/" in low:
                        mis_by_group["random_encounters"] += 1
                    elif "/multi/" in low or "mplayer" in low:
                        mis_by_group["multiplayer"] += 1
                    elif "tutor" in low:
                        mis_by_group["tutorials"] += 1
                    else:
                        mis_by_group["other"] += 1
                    parsed = parse_tactics_mis_bytes(zf.read(info.filename))
                    total_triggers += int(parsed["triggers"])
                    total_game_events += int(parsed["game_events"])
                    total_speech_nodes += int(parsed["speech_nodes"])
                    total_objectives += int(parsed["add_objective_actions"])
                    fsm_freq.update(parsed["fsm_nodes"])
                    campaign_vars.update(parsed["vars"])
                elif low.startswith("locale/game/") and ext == ".txt" and not low.endswith("~") and "copy of" not in low:
                    raw = zf.read(info.filename)
                    # UTF-16LE or Latin-1 key-value lines `key = { ... }` — count keys only, zero text!
                    text = raw.decode("utf-16-le", "replace") if raw[:2] == b"\xff\xfe" else raw.decode("latin-1", "replace")
                    key_lines = sum(1 for ln in text.splitlines() if "=" in ln and not ln.lstrip().startswith("//"))
                    locale_table_counts[os.path.basename(low)] = key_lines

    if total_triggers:
        fsm_freq["Event:<Trigger>"] = total_triggers
    if total_game_events:
        fsm_freq["Event:<gameEvent>"] = total_game_events

    return {
        "title": "Fallout Tactics",
        "bos_archive_count": len(bos_paths),
        "total_archive_entries": total_entries,
        "extensions": dict(ext_counts.most_common(20)),
        "quests": {
            "mis_total": len(seen_mis),
            "mis_by_group": dict(mis_by_group),
            "triggers_total": total_triggers,
            "add_objective_actions": total_objectives,
            "speech_nodes_total": total_speech_nodes,
            "campaign_and_mission_vars": len(campaign_vars),
        },
        "scripts": {
            "runtime": "Tactics C++ <Trigger>/<esh> Binary FSM (embedded in .mis)",
            "mis_fsm_files": len(seen_mis),
            "scb_files": scb_files,
            "game_events_total": total_game_events,
            "distinct_functions_and_events": len(fsm_freq),
            "top_40": [{"name": k, "count": v} for k, v in fsm_freq.most_common(40)],
        },
        "shared_systems": {
            "unique_ent_total": len(seen_ent),
            "entities_by_category": dict(ent_categories),
            "zar_bitmaps": ext_counts.get(".zar", 0),
            "locale_game_key_counts": locale_table_counts,
        },
    }


# ===========================================================================
# 3. Minimal Stdlib BSA v104 (0x68) Reader for Fallout 3 & Fallout: New Vegas
# ===========================================================================
@dataclass(frozen=True)
class BsaFileEntry:
    name: str
    offset: int
    size: int
    compressed: bool


class BsaV104Reader:
    """Pure-stdlib read-only BSA v104 (`0x68`) archive reader."""

    def __init__(self, path_or_stream: str | BinaryIO):
        if isinstance(path_or_stream, str):
            self._owned = True
            self._fp: BinaryIO = open(path_or_stream, "rb")
        else:
            self._owned = False
            self._fp = path_or_stream

        self._fp.seek(0, os.SEEK_END)
        total_len = self._fp.tell()
        self._fp.seek(0)
        hdr = self._fp.read(36)
        if len(hdr) != 36:
            raise ValueError("Truncated BSA header")
        (
            magic,
            version,
            folder_offset,
            archive_flags,
            folder_count,
            file_count,
            _total_folder_name_len,
            total_file_name_len,
            self.file_flags,
        ) = struct.unpack("<4s8I", hdr)
        if magic != b"BSA\x00" or version != 104 or folder_offset != 36:
            raise ValueError(f"Unsupported BSA header (magic={magic!r}, version={version})")

        self.version = version
        self.archive_flags = archive_flags
        self.embed_names = bool(archive_flags & 0x0100)
        default_comp = bool(archive_flags & 0x0004)

        folders = []
        for _ in range(folder_count):
            _fhash, fcnt, foff = struct.unpack("<QII", self._fp.read(16))
            folders.append((fcnt, foff - total_file_name_len))

        raw_files = []
        for fcnt, block_off in folders:
            self._fp.seek(block_off)
            dlen = self._fp.read(1)[0]
            dname = self._fp.read(dlen).rstrip(b"\x00").decode("latin-1").replace("/", "\\").strip("\\")
            for _ in range(fcnt):
                _ehash, rsize, doff = struct.unpack("<QII", self._fp.read(16))
                sz = rsize & 0x3FFFFFFF
                is_comp = default_comp ^ bool(rsize & (1 << 30))
                if doff + sz > total_len:
                    raise ValueError("BSA entry exceeds archive bounds")
                raw_files.append((dname, doff, sz, is_comp))

        name_block = self._fp.read(total_file_name_len)
        bnames = name_block.split(b"\x00")
        if bnames and bnames[-1] == b"":
            bnames = bnames[:-1]

        self.entries: List[BsaFileEntry] = []
        self._index: Dict[str, BsaFileEntry] = {}
        for bname, (dname, doff, sz, is_comp) in zip(bnames, raw_files):
            fn = bname.decode("latin-1").replace("/", "\\").lstrip("\\")
            full = f"{dname}\\{fn}" if dname else fn
            ent = BsaFileEntry(name=full, offset=doff, size=sz, compressed=is_comp)
            self.entries.append(ent)
            self._index[full.lower()] = ent

    @property
    def names(self) -> List[str]:
        return [e.name for e in self.entries]

    def read(self, name: str) -> bytes:
        ent = self._index[name.replace("/", "\\").lstrip("\\").lower()]
        self._fp.seek(ent.offset)
        blob = self._fp.read(ent.size)
        pos = 0
        if self.embed_names:
            pos = 1 + blob[0]
        if not ent.compressed:
            return blob[pos:]
        unp = struct.unpack_from("<I", blob, pos)[0]
        if unp == 0 and pos + 4 == len(blob):
            return b""
        return zlib.decompress(blob[pos + 4 :])

    def close(self) -> None:
        if self._owned:
            self._fp.close()

    def __enter__(self) -> "BsaV104Reader":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# ===========================================================================
# 4. Bethesda TES4 / Creation Engine ESM, ObScript,PSC & PEX Parsers
# ===========================================================================
def iter_esm_records(
    path_or_stream: str | BinaryIO,
    *,
    skip_world_cell_children: bool = True,
) -> Iterator[Tuple[bytes, int, int, bytes]]:
    """Stream 24-byte `GRUP` and major records from a TES4/FO3/FNV/FO4/FO76/SF `.esm`."""
    if isinstance(path_or_stream, str):
        fp: BinaryIO = open(path_or_stream, "rb")
        owned = True
    else:
        fp = path_or_stream
        owned = False

    try:
        fp.seek(0, os.SEEK_END)
        end = fp.tell()
        fp.seek(0)
        tes4 = fp.read(24)
        if len(tes4) < 24 or tes4[:4] != b"TES4":
            raise ValueError("Invalid TES4 header")
        tes4_size = struct.unpack_from("<I", tes4, 4)[0]
        fp.seek(24 + tes4_size)
        while fp.tell() + 24 <= end:
            hdr = fp.read(24)
            rt = hdr[:4]
            if rt == b"GRUP":
                gsz, _glbl, gtype = struct.unpack_from("<I4sI", hdr, 4)
                # gtype 1 = World Children, 6 = Cell Children, 8 = Cell Persistent, 9 = Cell Temporary
                # Keeping gtype 0, 7 (Topic Children), 10 (Quest Children) visits all QUST, DIAL, INFO, SCEN, WRLD, and interior CELL headers!
                if skip_world_cell_children and gtype in (1, 6, 8, 9):
                    fp.seek(fp.tell() - 24 + gsz)
                continue
            rdsz, rflg, rfid = struct.unpack_from("<III", hdr, 4)
            payload = fp.read(rdsz)
            if rflg & 0x00040000:
                payload = zlib.decompress(payload[4:]) if len(payload) > 4 else b""
            yield rt, rfid, rflg, payload
    finally:
        if owned:
            fp.close()


def iter_subrecords(payload: bytes) -> Iterator[Tuple[bytes, bytes]]:
    """Iterate subrecords inside an uncompressed record payload, handling `XXXX` 32-bit sizes."""
    sp = 0
    n = len(payload)
    while sp + 6 <= n:
        stp = payload[sp : sp + 4]
        ssz = struct.unpack_from("<H", payload, sp + 4)[0]
        sp += 6
        if stp == b"XXXX":
            if sp + 10 > n:
                break
            ssz = struct.unpack_from("<I", payload, sp)[0]
            sp += 4
            stp = payload[sp : sp + 4]
            sp += 6
        yield stp, payload[sp : sp + ssz]
        sp += ssz


OBSCRIPT_STR_RE = re.compile(r'"[^"]*"')
OBSCRIPT_BEGIN_RE = re.compile(r"^begin\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
IDENT_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
OBSCRIPT_KEYWORDS = {
    "scn", "scriptname", "short", "int", "long", "float", "ref", "reference",
    "begin", "end", "if", "elseif", "else", "endif", "while", "loop", "return",
    "set", "to", "player", "playerref",
}


def tokenize_obscript_sctx(text: str) -> Tuple[Counter, Counter]:
    """Extract `Begin <BlockType>` blocks and canonical GECK function calls from ObScript `SCTX`."""
    blocks: Counter = Counter()
    calls: Counter = Counter()
    for raw_line in text.splitlines():
        clean = OBSCRIPT_STR_RE.sub('""', raw_line).split(";", 1)[0].strip()
        if not clean:
            continue
        bm = OBSCRIPT_BEGIN_RE.match(clean)
        if bm:
            bname = bm.group(1)
            # Normalize standard GECK block casing
            low = bname.lower()
            canon_block = {
                "gamemode": "GameMode",
                "menumode": "MenuMode",
                "onactivate": "OnActivate",
                "ondeath": "OnDeath",
                "onload": "OnLoad",
                "ontriggerenter": "OnTriggerEnter",
                "ontrigger": "OnTrigger",
                "ontriggerleave": "OnTriggerLeave",
                "onadd": "OnAdd",
                "ondrop": "OnDrop",
                "onequip": "OnEquip",
                "onunequip": "OnUnequip",
                "onhit": "OnHit",
                "onhitwith": "OnHitWith",
                "onmurder": "OnMurder",
                "oncombatend": "OnCombatEnd",
                "onstartcombat": "OnStartCombat",
                "onpackageend": "OnPackageEnd",
                "onpackagestart": "OnPackageStart",
                "onpackagechange": "OnPackageChange",
                "onreset": "OnReset",
                "scripteffectstart": "ScriptEffectStart",
                "scripteffectupdate": "ScriptEffectUpdate",
                "scripteffectfinish": "ScriptEffectFinish",
                "saytodone": "SayToDone",
                "ondestructionstagechange": "OnDestructionStageChange",
            }.get(low, bname)
            blocks[f"Begin:{canon_block}"] += 1
            continue
        toks = IDENT_TOKEN_RE.findall(clean)
        if not toks:
            continue
        first_low = toks[0].lower()
        if first_low in ("short", "int", "long", "float", "ref", "reference", "scn", "scriptname"):
            continue
        for tok in toks:
            tl = tok.lower()
            if tl in OBSCRIPT_KEYWORDS:
                continue
            canon = GECK_LOOKUP.get(tl)
            if canon is not None:
                calls[canon] += 1
    return blocks, calls


def scan_esm_file(
    path: str,
    *,
    is_ce2: bool = False,
    parse_obscript: bool = False,
) -> Dict[str, object]:
    """Scan a single `.esm` file for quest, dialogue, CTDA, shared-system, and ObScript counts."""
    rec_counts: Counter = Counter()
    qust_stages = 0
    qust_objectives = 0
    qust_aliases = 0
    qust_scripted = 0
    qust_start_enabled = 0
    qust_repeatable = 0
    qust_radiant = 0
    start_enabled_edids: List[str] = []

    info_ctda_total = 0
    ctda_funcs: Counter = Counter()
    ctda_skill_av = 0
    ctda_perk = 0
    ctda_repu_faction = 0

    perk_traits = 0
    perk_playable = 0

    scpt_types: Counter = Counter()  # 0=Object, 1=Quest, 2=MagicEffect
    scpt_vars_total = 0
    scpt_with_sctx = 0
    embedded_sctx_records: Counter = Counter()
    ob_blocks: Counter = Counter()
    ob_calls: Counter = Counter()

    ctda_map = CTDA_NAMES_CE2 if is_ce2 else CTDA_NAMES_FO3NV

    for rt, _rfid, _rflg, pay in iter_esm_records(path, skip_world_cell_children=True):
        sig = rt.decode("ascii", "replace")
        rec_counts[sig] += 1

        if rt == b"QUST":
            has_script = False
            has_alias = False
            qflags = 0
            edid = ""
            for stp, sdat in iter_subrecords(pay):
                if stp == b"EDID":
                    edid = sdat.rstrip(b"\x00").decode("latin-1", "replace")
                elif stp == b"INDX":
                    qust_stages += 1
                elif stp == b"QOBJ":
                    qust_objectives += 1
                elif stp in (b"ALST", b"ALLS"):
                    qust_aliases += 1
                    has_alias = True
                elif stp in (b"VMAD", b"SCRI"):
                    has_script = True
                elif stp == b"DATA" and not is_ce2 and len(sdat) >= 1:
                    qflags = sdat[0]
                elif stp == b"DNAM" and is_ce2 and len(sdat) >= 2:
                    qflags = struct.unpack_from("<H", sdat, 0)[0]
            if has_script:
                qust_scripted += 1
            if qflags & 0x01:
                qust_start_enabled += 1
                if edid:
                    start_enabled_edids.append(edid)
            if qflags & 0x08:
                qust_repeatable += 1
            if has_alias and (qflags & 0x08):
                qust_radiant += 1

        elif rt == b"INFO":
            has_emb = False
            for stp, sdat in iter_subrecords(pay):
                if stp == b"CTDA" and len(sdat) >= 10:
                    info_ctda_total += 1
                    fn_id = struct.unpack_from("<H", sdat, 8)[0]
                    fn_name = ctda_map.get(fn_id, f"Func_{fn_id}")
                    ctda_funcs[fn_name] += 1
                    if fn_id in (14, 242):
                        ctda_skill_av += 1
                    elif fn_id == 448:
                        ctda_perk += 1
                    elif fn_id in (71, 73, 449, 598, 599, 600) and not (is_ce2 and fn_id == 598):
                        ctda_repu_faction += 1
                    elif is_ce2 and fn_id in (71, 73, 449):
                        ctda_repu_faction += 1
                elif parse_obscript and stp == b"SCTX" and len(sdat) > 1:
                    has_emb = True
                    bks, cls = tokenize_obscript_sctx(sdat.rstrip(b"\x00").decode("latin-1", "replace"))
                    ob_blocks.update(bks)
                    ob_calls.update(cls)
            if has_emb:
                embedded_sctx_records["INFO"] += 1

        elif rt == b"PERK":
            for stp, sdat in iter_subrecords(pay):
                if stp == b"DATA":
                    if not is_ce2 and len(sdat) >= 4:
                        is_trait, _lvl, _ranks, is_play = sdat[0], sdat[1], sdat[2], sdat[3]
                        if is_trait:
                            perk_traits += 1
                        if is_play:
                            perk_playable += 1
                    elif is_ce2 and len(sdat) >= 5:
                        if sdat[0]:
                            perk_traits += 1
                        if sdat[3]:
                            perk_playable += 1
                elif parse_obscript and stp == b"SCTX" and len(sdat) > 1:
                    embedded_sctx_records["PERK"] += 1
                    bks, cls = tokenize_obscript_sctx(sdat.rstrip(b"\x00").decode("latin-1", "replace"))
                    ob_blocks.update(bks)
                    ob_calls.update(cls)

        elif parse_obscript and rt == b"SCPT":
            has_sctx = False
            for stp, sdat in iter_subrecords(pay):
                if stp == b"SCHR" and len(sdat) >= 20:
                    _unk, _rcnt, _csz, vcnt, stype, _is_en = struct.unpack_from("<4sIIIHH", sdat, 0)
                    scpt_vars_total += vcnt
                    tname = {0: "Object", 1: "Quest", 0x100: "MagicEffect"}.get(stype, f"Type_{stype}")
                    scpt_types[tname] += 1
                elif stp == b"SCTX" and len(sdat) > 0:
                    has_sctx = True
                    bks, cls = tokenize_obscript_sctx(sdat.rstrip(b"\x00").decode("latin-1", "replace"))
                    ob_blocks.update(bks)
                    ob_calls.update(cls)
            if has_sctx:
                scpt_with_sctx += 1

        elif parse_obscript and rt in (b"PACK", b"TERM"):
            for stp, sdat in iter_subrecords(pay):
                if stp == b"SCTX" and len(sdat) > 1:
                    embedded_sctx_records[sig] += 1
                    bks, cls = tokenize_obscript_sctx(sdat.rstrip(b"\x00").decode("latin-1", "replace"))
                    ob_blocks.update(bks)
                    ob_calls.update(cls)

    return {
        "file": os.path.basename(path),
        "records": dict(rec_counts),
        "qust_detail": {
            "quests": rec_counts.get("QUST", 0),
            "stages_indx": qust_stages,
            "objectives_qobj": qust_objectives,
            "aliases": qust_aliases,
            "scripted_quests": qust_scripted,
            "start_game_enabled": qust_start_enabled,
            "repeatable_stages_flag": qust_repeatable,
            "radiant_alias_repeatable": qust_radiant,
            "start_enabled_edids": start_enabled_edids,
        },
        "dialogue_detail": {
            "dial_topics": rec_counts.get("DIAL", 0),
            "info_responses": rec_counts.get("INFO", 0),
            "scen_scenes": rec_counts.get("SCEN", 0),
            "info_ctda_total": info_ctda_total,
            "info_ctda_skill_or_av": ctda_skill_av,
            "info_ctda_perk": ctda_perk,
            "info_ctda_repu_or_faction": ctda_repu_faction,
            "top_ctda_functions": dict(ctda_funcs.most_common(20)),
        },
        "perk_detail": {
            "total": rec_counts.get("PERK", 0),
            "playable": perk_playable,
            "trait_flag": perk_traits,
        },
        "obscript_detail": {
            "scpt_records": rec_counts.get("SCPT", 0),
            "scpt_with_sctx": scpt_with_sctx,
            "scpt_local_vars": scpt_vars_total,
            "scpt_types": dict(scpt_types),
            "embedded_sctx_records": dict(embedded_sctx_records),
            "blocks": ob_blocks,
            "calls": ob_calls,
        },
    }


# ---------------------------------------------------------------------------
# Papyrus `.psc` Source Zip Scanner & `.pex` (`0xFA57C0DE`) Bytecode Reader
# ---------------------------------------------------------------------------
PSC_DOC_COMMENT_RE = re.compile(r"\{[^}]*\}", re.DOTALL)
PSC_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')
PSC_HEADER_RE = re.compile(r"^\s*ScriptName\s+([A-Za-z0-9_:]+)(.*)$", re.IGNORECASE | re.MULTILINE)
PSC_EVENT_RE = re.compile(r"^\s*Event\s+([A-Za-z_][A-Za-z0-9_.]*)\s*\(", re.IGNORECASE | re.MULTILINE)
PSC_FUNC_DEF_RE = re.compile(
    r"^\s*(?:[A-Za-z0-9_:\[\]]+\s+)?Function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.IGNORECASE | re.MULTILINE,
)
PSC_CALL_RE = re.compile(r"(?:([A-Za-z_][A-Za-z0-9_]*)\s*\.\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\(")
PSC_NOT_CALLS = {"if", "elseif", "while", "function", "event", "new", "return", "as", "is"}
PAPYRUS_BUILTIN_STATICS = {
    "game", "utility", "debug", "math", "input", "ui", "commonarrayfunctions",
    "defaultscriptfunctions", "actor", "objectreference", "weather", "sound",
    "soundcategory", "wwiseevent",
}


def _fold_papyrus_counter(raw_counts: Counter) -> Counter:
    """Group case-insensitive Papyrus identifiers under their most frequent mixed-case spelling."""
    totals: Counter = Counter()
    spellings: Dict[str, Counter] = {}
    for name, cnt in raw_counts.items():
        low = name.lower()
        totals[low] += cnt
        spellings.setdefault(low, Counter())[name] += cnt

    folded: Counter = Counter()
    for low, total_cnt in totals.items():
        # Prefer spellings with uppercase letters (e.g. `Debug.Trace` over `debug.trace`) when present
        cands = spellings[low]
        upper_cands = [(sp, c) for sp, c in cands.items() if any(ch.isupper() for ch in sp)]
        best = max(upper_cands or cands.items(), key=lambda kv: (kv[1], sum(1 for ch in kv[0] if ch.isupper())))[0]
        if "." in best and not best.startswith("Event:"):
            lhs, rhs = best.split(".", 1)
            best = f"{lhs[0].upper() + lhs[1:]}.{rhs[0].upper() + rhs[1:]}"
        folded[best] = total_cnt
    return folded


def scan_psc_zip(zip_path: str) -> Dict[str, object]:
    """Scan `.psc` Papyrus source files inside a Creation Kit `.zip` archive (zero source lines stored)."""
    psc_total = 0
    native_scripts = 0
    compiled_scripts = 0
    events_freq: Counter = Counter()
    calls_freq: Counter = Counter()
    known_script_classes = set(PAPYRUS_BUILTIN_STATICS)

    with zipfile.ZipFile(zip_path, "r") as zf:
        psc_infos = [i for i in zf.infolist() if not i.is_dir() and i.filename.lower().endswith(".psc")]
        for info in psc_infos:
            base_cls = os.path.splitext(os.path.basename(info.filename))[0].lower()
            known_script_classes.add(base_cls)

        for info in psc_infos:
            psc_total += 1
            raw_text = zf.read(info.filename).decode("utf-8", "replace")
            # Strip `{ ... }` documentation blocks, `"..."` strings, and `;` line comments
            no_doc = PSC_DOC_COMMENT_RE.sub("", raw_text)
            clean_lines = []
            for ln in no_doc.splitlines():
                ln_nostr = PSC_STRING_RE.sub('""', ln)
                clean_lines.append(ln_nostr.split(";", 1)[0])
            clean = "\n".join(clean_lines)

            hm = PSC_HEADER_RE.search(clean)
            if hm:
                s_cls = hm.group(1).split(":")[-1].lower()
                known_script_classes.add(s_cls)
                if "native" in hm.group(2).lower().split():
                    native_scripts += 1
                else:
                    compiled_scripts += 1
            else:
                compiled_scripts += 1

            for em in PSC_EVENT_RE.finditer(clean):
                ev_name = em.group(1)
                events_freq[f"Event:{ev_name}"] += 1

            # Remove Function/Event declaration lines before counting call sites
            body_no_decl = PSC_EVENT_RE.sub("", PSC_FUNC_DEF_RE.sub("", clean))
            for cm in PSC_CALL_RE.finditer(body_no_decl):
                recv, fn = cm.group(1), cm.group(2)
                fl = fn.lower()
                if fl in PSC_NOT_CALLS:
                    continue
                if recv and recv.lower() in known_script_classes:
                    calls_freq[f"{recv}.{fn}"] += 1
                else:
                    calls_freq[fn] += 1

    folded_events = _fold_papyrus_counter(events_freq)
    folded_calls = _fold_papyrus_counter(calls_freq)
    combined = Counter()
    combined.update(folded_events)
    combined.update(folded_calls)
    return {
        "zip_name": os.path.basename(zip_path),
        "psc_total": psc_total,
        "native_headers": native_scripts,
        "non_native_scripts": compiled_scripts,
        "distinct_events": len(folded_events),
        "distinct_calls": len(folded_calls),
        "distinct_functions_and_events": len(combined),
        "combined": combined,
        "top_40": [{"name": k, "count": v} for k, v in combined.most_common(40)],
    }


PEX_FIXED_ARGS: Dict[int, int] = {
    0x00: 0,
    0x01: 3, 0x02: 3, 0x03: 3, 0x04: 3, 0x05: 3, 0x06: 3, 0x07: 3, 0x08: 3, 0x09: 3,
    0x0A: 2, 0x0B: 2, 0x0C: 2, 0x0D: 2, 0x0E: 2,
    0x0F: 3, 0x10: 3, 0x11: 3, 0x12: 3, 0x13: 3,
    0x14: 1, 0x15: 2, 0x16: 2,
    0x17: 3, 0x18: 2, 0x19: 3,
    0x1A: 1, 0x1B: 3, 0x1C: 3, 0x1D: 3,
    0x1E: 2, 0x1F: 2, 0x20: 3, 0x21: 3, 0x22: 4, 0x23: 4,
    0x24: 3, 0x25: 1, 0x26: 3, 0x27: 3, 0x28: 5, 0x29: 5,
    0x2A: 3, 0x2B: 3, 0x2C: 1, 0x2D: 3, 0x2E: 1,
    0x2F: 6, 0x30: 0, 0x31: 0, 0x32: 1,
}
PEX_VARIADIC_OPS = {0x17, 0x18, 0x19, 0x30, 0x31, 0x32}


def _read_pex_var_data(raw: bytes, p: int) -> Tuple[int, int, int]:
    vtype = raw[p]
    if vtype == 0:
        return vtype, 0, p + 1
    if vtype in (1, 2):
        return vtype, struct.unpack_from("<H", raw, p + 1)[0], p + 3
    if vtype == 3:
        return vtype, struct.unpack_from("<i", raw, p + 1)[0], p + 5
    if vtype == 4:
        return vtype, 0, p + 5
    if vtype == 5:
        return vtype, raw[p + 1], p + 2
    raise ValueError(f"Unsupported PEX VarData type {vtype} at offset {p}")


def parse_pex_bytes(raw: bytes) -> Dict[str, object]:
    """Parse a little-endian Papyrus `.pex` (`0xFA57C0DE`) header, string table, and bytecode calls/events."""
    if len(raw) < 24:
        raise ValueError("Truncated PEX file")
    magic, maj, minv, game_id, _ctime = struct.unpack_from("<IBBHQ", raw, 0)
    if magic != 0xFA57C0DE:
        raise ValueError(f"Invalid PEX magic 0x{magic:08X} (expected 0xFA57C0DE)")
    pos = 16
    for _ in range(3):
        slen = struct.unpack_from("<H", raw, pos)[0]
        pos += 2 + slen

    scnt = struct.unpack_from("<H", raw, pos)[0]
    pos += 2
    string_table: List[str] = []
    for _ in range(scnt):
        slen = struct.unpack_from("<H", raw, pos)[0]
        pos += 2
        string_table.append(raw[pos : pos + slen].decode("utf-8", "replace"))
        pos += slen

    has_dbg = raw[pos]
    pos += 1
    if has_dbg:
        pos += 8
        fcnt = struct.unpack_from("<H", raw, pos)[0]
        pos += 2
        for _ in range(fcnt):
            icnt = struct.unpack_from("<H", raw, pos + 7)[0]
            pos += 9 + icnt * 2
        if (maj, minv) >= (3, 9):
            pg_cnt = struct.unpack_from("<H", raw, pos)[0]
            pos += 2
            for _ in range(pg_cnt):
                pcnt = struct.unpack_from("<H", raw, pos + 10)[0]
                pos += 12 + pcnt * 2
            so_cnt = struct.unpack_from("<H", raw, pos)[0]
            pos += 2
            for _ in range(so_cnt):
                vcnt = struct.unpack_from("<H", raw, pos + 4)[0]
                pos += 6 + vcnt * 2

    uf_cnt = struct.unpack_from("<H", raw, pos)[0]
    pos += 2 + uf_cnt * 3
    obj_cnt = struct.unpack_from("<H", raw, pos)[0]
    pos += 2

    def parse_fn(p: int) -> Tuple[int, int, int, List[str]]:
        fflags = raw[p + 8]
        p += 9
        param_cnt = struct.unpack_from("<H", raw, p)[0]
        p += 2 + param_cnt * 4
        local_cnt = struct.unpack_from("<H", raw, p)[0]
        p += 2 + local_cnt * 4
        inst_cnt = struct.unpack_from("<H", raw, p)[0]
        p += 2
        calls: List[str] = []
        for _ in range(inst_cnt):
            op = raw[p]
            p += 1
            fargs = []
            for _ in range(PEX_FIXED_ARGS[op]):
                vt, vv, p = _read_pex_var_data(raw, p)
                fargs.append((vt, vv))
            if op in PEX_VARIADIC_OPS:
                _, vcnt, p = _read_pex_var_data(raw, p)
                for _ in range(vcnt):
                    _, _, p = _read_pex_var_data(raw, p)
            if op == 0x17:
                calls.append(string_table[fargs[0][1]])
            elif op == 0x18:
                calls.append(string_table[fargs[0][1]])
            elif op == 0x19:
                calls.append(f"{string_table[fargs[0][1]]}.{string_table[fargs[1][1]]}")
        return p, fflags, inst_cnt, calls

    events: List[str] = []
    calls_all: List[str] = []
    total_instructions = 0
    is_native_obj = False
    non_native_fn_count = 0

    for _ in range(obj_cnt):
        _oname_idx, osize = struct.unpack_from("<HI", raw, pos)
        obj_end = pos + 2 + osize
        p = pos + 6
        p += 4  # parentClass, docString
        if (maj, minv) >= (3, 9):
            p += 1  # constFlag
        obj_uflags = struct.unpack_from("<I", raw, p)[0]
        if obj_uflags & 0x01:
            is_native_obj = True
        p += 6  # userFlags(I) + autoStateName(H)
        if (maj, minv) >= (3, 9):
            struct_cnt = struct.unpack_from("<H", raw, p)[0]
            p += 2
            for _ in range(struct_cnt):
                p += 2
                mcnt = struct.unpack_from("<H", raw, p)[0]
                p += 2
                for _ in range(mcnt):
                    p += 8
                    _, _, p = _read_pex_var_data(raw, p)
                    p += 3
        var_cnt = struct.unpack_from("<H", raw, p)[0]
        p += 2
        for _ in range(var_cnt):
            p += 8
            _, _, p = _read_pex_var_data(raw, p)
            if (maj, minv) >= (3, 9):
                p += 1
        if game_id == 4:  # Starfield Guards (placed immediately after variables)
            gcnt = struct.unpack_from("<H", raw, p)[0]
            p += 2 + gcnt * 2
        prop_cnt = struct.unpack_from("<H", raw, p)[0]
        p += 2
        for _ in range(prop_cnt):
            p += 10
            pflags = raw[p]
            p += 1
            if pflags & 0x04:
                p += 2
            else:
                if pflags & 0x01:
                    p, _, ic, c = parse_fn(p)
                    total_instructions += ic
                    calls_all.extend(c)
                if pflags & 0x02:
                    p, _, ic, c = parse_fn(p)
                    total_instructions += ic
                    calls_all.extend(c)
        state_cnt = struct.unpack_from("<H", raw, p)[0]
        p += 2
        for _ in range(state_cnt):
            p += 2  # stateName
            fn_cnt = struct.unpack_from("<H", raw, p)[0]
            p += 2
            for _ in range(fn_cnt):
                fname_idx = struct.unpack_from("<H", raw, p)[0]
                p += 2
                fname = string_table[fname_idx]
                p, fflags, ic, c = parse_fn(p)
                total_instructions += ic
                calls_all.extend(c)
                if not (fflags & 0x02):
                    non_native_fn_count += 1
                    if fname.lower().startswith("on"):
                        events.append(f"Event:{fname}")
        if game_id == 3:  # FO76 v3.15 trailing networked variable index table
            iv_cnt = struct.unpack_from("<H", raw, p)[0]
            p += 2 + iv_cnt * 2
        if p != obj_end:
            raise ValueError(f"PEX ObjectData size mismatch ({p} != {obj_end})")
        pos = obj_end

    return {
        "version": f"{maj}.{minv}",
        "game_id": game_id,
        "string_count": scnt,
        "identifiers": [s for s in string_table if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", s)],
        "is_native_header": is_native_obj and total_instructions == 0,
        "is_empty_stub": (not is_native_obj) and total_instructions == 0,
        "non_native_functions": non_native_fn_count,
        "instructions": total_instructions,
        "events": events,
        "calls": [c for c in calls_all if not c.startswith("::")],
    }


def scan_ba2_pex_set(ba2_paths: Sequence[str]) -> Dict[str, object]:
    """Scan `.pex` scripts across one or more `.ba2` archives."""
    seen: Dict[str, Tuple[Ba2, str]] = {}
    per_archive = []
    for bp in ba2_paths:
        if not os.path.isfile(bp):
            continue
        b = Ba2(bp)
        pex_in_b = [n for n in b.names if n.lower().endswith(".pex")]
        per_archive.append({"archive": os.path.basename(bp), "version": b.version, "entries": len(b.names), "pex": len(pex_in_b)})
        for n in pex_in_b:
            seen[n.replace("/", "\\").lower()] = (b, n)

    freq: Counter = Counter()
    versions: Counter = Counter()
    native_hdrs = 0
    empty_stubs = 0
    active_scripts = 0
    total_instructions = 0
    unique_identifiers: set = set()

    for _k, (b, orig_name) in sorted(seen.items()):
        res = parse_pex_bytes(b.read(orig_name))
        versions[f"v{res['version']}_game{res['game_id']}"] += 1
        unique_identifiers.update(res["identifiers"])
        total_instructions += int(res["instructions"])
        if res["is_native_header"]:
            native_hdrs += 1
        elif res["is_empty_stub"]:
            empty_stubs += 1
        else:
            active_scripts += 1
        for ev in res["events"]:
            freq[ev] += 1
        for cl in res["calls"]:
            freq[cl] += 1

    folded_freq = _fold_papyrus_counter(freq)
    return {
        "archives": per_archive,
        "unique_pex_total": len(seen),
        "pex_versions": dict(versions),
        "native_header_pex": native_hdrs,
        "active_compiled_pex": active_scripts,
        "empty_stub_pex": empty_stubs,
        "total_instructions": total_instructions,
        "unique_string_identifiers": len(unique_identifiers),
        "distinct_functions_and_events": len(folded_freq),
        "top_40": [{"name": k, "count": v} for k, v in folded_freq.most_common(40)],
    }


# ===========================================================================
# 5. Job 4: FO3 & FNV 40-Quest Readiness Dependency Extractor
# ===========================================================================
def extract_fo3_fnv_quest_dependencies(
    esm_path: str,
    main_edids: Sequence[str],
    side_edids: Sequence[str],
) -> Dict[str, object]:
    """Extract exact FormID, stage/objective counts, SCPT/INFO/PACK dependencies, and GECK calls for target quests."""
    wanted = set(main_edids) | set(side_edids)
    edids_by_fid: Dict[int, str] = {}
    scpt_data: Dict[int, Dict[str, object]] = {}
    raw_quests: Dict[str, Dict[str, object]] = {}

    # Pass 1: collect all EDIDs, SCPT AST summaries, and target QUST records
    for rt, rfid, _rflg, pay in iter_esm_records(esm_path, skip_world_cell_children=True):
        edid = ""
        for stp, sdat in iter_subrecords(pay):
            if stp == b"EDID":
                edid = sdat.rstrip(b"\x00").decode("latin-1", "replace")
                edids_by_fid[rfid] = edid
                break
        if rt == b"SCPT":
            blocks = Counter()
            calls = Counter()
            scros: List[int] = []
            vcnt = 0
            for stp, sdat in iter_subrecords(pay):
                if stp == b"SCHR" and len(sdat) >= 20:
                    vcnt = struct.unpack_from("<I", sdat, 12)[0]
                elif stp == b"SCRO" and len(sdat) >= 4:
                    scros.append(struct.unpack_from("<I", sdat, 0)[0])
                elif stp == b"SCTX" and len(sdat) > 0:
                    bks, cls = tokenize_obscript_sctx(sdat.rstrip(b"\x00").decode("latin-1", "replace"))
                    blocks.update(bks)
                    calls.update(cls)
            scpt_data[rfid] = {
                "form_id": f"0x{rfid:06X}",
                "edid": edid,
                "vars": vcnt,
                "blocks": dict(blocks),
                "top_calls": [k for k, _ in calls.most_common(12)],
                "scros": scros,
            }
        elif rt == b"QUST" and edid in wanted:
            scri = 0
            stages: List[int] = []
            objs: List[int] = []
            qflags = 0
            for stp, sdat in iter_subrecords(pay):
                if stp == b"SCRI" and len(sdat) >= 4:
                    scri = struct.unpack_from("<I", sdat, 0)[0]
                elif stp == b"INDX" and len(sdat) >= 2:
                    stages.append(struct.unpack_from("<H", sdat, 0)[0])
                elif stp == b"QOBJ" and len(sdat) >= 4:
                    objs.append(struct.unpack_from("<i", sdat, 0)[0])
                elif stp == b"DATA" and len(sdat) >= 1:
                    qflags = sdat[0]
            raw_quests[edid] = {
                "edid": edid,
                "form_id_int": rfid,
                "form_id": f"0x{rfid:06X}",
                "scri_int": scri,
                "stage_count": len(stages),
                "stages": sorted(set(stages)),
                "objective_count": len(objs),
                "flags": f"0x{qflags:02X}",
            }

    target_fids = {q["form_id_int"]: edid for edid, q in raw_quests.items()}
    dial_qsti: Counter = Counter()
    info_qsti: Counter = Counter()
    info_scro_refs: Counter = Counter()
    info_result_scripts: Counter = Counter()
    info_skill_checks: Counter = Counter()
    info_perk_checks: Counter = Counter()
    info_repu_checks: Counter = Counter()
    pack_refs: Dict[str, List[str]] = {k: [] for k in wanted}
    external_scpts: Dict[str, List[str]] = {k: [] for k in wanted}

    for sc_fid, sinfo in scpt_data.items():
        for r_fid in sinfo["scros"]:
            if r_fid in target_fids:
                qed = target_fids[r_fid]
                if sc_fid != raw_quests[qed]["scri_int"]:
                    external_scpts[qed].append(f"{sinfo['edid'] or sinfo['form_id']} ({sinfo['form_id']})")

    # Pass 2: link DIAL, INFO (both direct QSTI and cross-quest SCRO/CTDA references), and PACK
    for rt, rfid, _rflg, pay in iter_esm_records(esm_path, skip_world_cell_children=True):
        if rt == b"DIAL":
            for stp, sdat in iter_subrecords(pay):
                if stp == b"QSTI" and len(sdat) >= 4:
                    qid = struct.unpack_from("<I", sdat, 0)[0]
                    if qid in target_fids:
                        dial_qsti[target_fids[qid]] += 1
        elif rt == b"INFO":
            qsti_q = None
            scro_qs = set()
            has_sctx = False
            has_av = False
            has_pk = False
            has_rep = False
            for stp, sdat in iter_subrecords(pay):
                if stp == b"QSTI" and len(sdat) >= 4:
                    qid = struct.unpack_from("<I", sdat, 0)[0]
                    if qid in target_fids:
                        qsti_q = target_fids[qid]
                elif stp == b"SCRO" and len(sdat) >= 4:
                    qid = struct.unpack_from("<I", sdat, 0)[0]
                    if qid in target_fids:
                        scro_qs.add(target_fids[qid])
                elif stp == b"SCTX" and len(sdat) > 1:
                    has_sctx = True
                elif stp == b"CTDA" and len(sdat) >= 16:
                    fn_id = struct.unpack_from("<H", sdat, 8)[0]
                    p1 = struct.unpack_from("<I", sdat, 12)[0]
                    if p1 in target_fids:
                        scro_qs.add(target_fids[p1])
                    if fn_id in (14, 242):
                        has_av = True
                    elif fn_id == 448:
                        has_pk = True
                    elif fn_id in (71, 73, 449, 598, 599, 600):
                        has_rep = True
            touched = set(scro_qs)
            if qsti_q:
                info_qsti[qsti_q] += 1
                touched.add(qsti_q)
            for qed in scro_qs:
                if qed != qsti_q:
                    info_scro_refs[qed] += 1
            for qed in touched:
                if has_sctx:
                    info_result_scripts[qed] += 1
                if has_av:
                    info_skill_checks[qed] += 1
                if has_pk:
                    info_perk_checks[qed] += 1
                if has_rep:
                    info_repu_checks[qed] += 1
        elif rt == b"PACK":
            pedid = edids_by_fid.get(rfid, f"0x{rfid:06X}")
            q_touched = set()
            for stp, sdat in iter_subrecords(pay):
                if stp == b"CTDA" and len(sdat) >= 16:
                    p1 = struct.unpack_from("<I", sdat, 12)[0]
                    if p1 in target_fids:
                        q_touched.add(target_fids[p1])
                elif stp == b"SCRO" and len(sdat) >= 4:
                    p1 = struct.unpack_from("<I", sdat, 0)[0]
                    if p1 in target_fids:
                        q_touched.add(target_fids[p1])
            for qed in q_touched:
                pack_refs[qed].append(f"{pedid} (0x{rfid:06X})")

    def build_group(edid_list: Sequence[str], kind: str) -> List[Dict[str, object]]:
        rows = []
        for idx, qed in enumerate(edid_list, 1):
            q = raw_quests[qed]
            scri_fid = q["scri_int"]
            smeta = scpt_data.get(scri_fid, {}) if scri_fid else {}
            rows.append({
                "order": idx,
                "category": kind,
                "edid": qed,
                "form_id": q["form_id"],
                "flags": q["flags"],
                "stage_count": q["stage_count"],
                "objective_count": q["objective_count"],
                "quest_script": f"{smeta.get('edid', 'None')} (0x{scri_fid:06X})" if scri_fid else "None",
                "quest_script_vars": smeta.get("vars", 0),
                "quest_script_blocks": smeta.get("blocks", {}),
                "quest_script_top_calls": smeta.get("top_calls", []),
                "external_scpt_count": len(external_scpts[qed]),
                "external_scpt_samples": sorted(external_scpts[qed])[:8],
                "dial_topics_owned": dial_qsti[qed],
                "info_owned": info_qsti[qed],
                "info_cross_quest_refs": info_scro_refs[qed],
                "info_result_scripts": info_result_scripts[qed],
                "info_skill_av_checks": info_skill_checks[qed],
                "info_perk_checks": info_perk_checks[qed],
                "info_repu_faction_checks": info_repu_checks[qed],
                "pack_count": len(pack_refs[qed]),
                "pack_samples": sorted(pack_refs[qed])[:6],
            })
        return rows

    return {
        "esm": os.path.basename(esm_path),
        "main_10": build_group(main_edids, "main"),
        "side_10": build_group(side_edids, "side"),
    }


# ===========================================================================
# 6. Full 8-Game Orchestrator & Output Writer
# ===========================================================================
def _aggregate_esms(esm_scans: Sequence[Dict[str, object]]) -> Dict[str, object]:
    rec_sum: Counter = Counter()
    qust_sum: Counter = Counter()
    dial_sum: Counter = Counter()
    perk_sum: Counter = Counter()
    ctda_fn_sum: Counter = Counter()
    ob_blocks_sum: Counter = Counter()
    ob_calls_sum: Counter = Counter()
    scpt_types_sum: Counter = Counter()
    emb_sum: Counter = Counter()
    scpt_records = 0
    scpt_sctx = 0
    scpt_vars = 0

    for s in esm_scans:
        rec_sum.update(s["records"])
        for k, v in s["qust_detail"].items():
            if isinstance(v, int):
                qust_sum[k] += v
        for k, v in s["dialogue_detail"].items():
            if isinstance(v, int):
                dial_sum[k] += v
            elif k == "top_ctda_functions":
                ctda_fn_sum.update(v)
        for k, v in s["perk_detail"].items():
            if isinstance(v, int):
                perk_sum[k] += v
        ob = s["obscript_detail"]
        scpt_records += ob["scpt_records"]
        scpt_sctx += ob["scpt_with_sctx"]
        scpt_vars += ob["scpt_local_vars"]
        scpt_types_sum.update(ob["scpt_types"])
        emb_sum.update(ob["embedded_sctx_records"])
        ob_blocks_sum.update(ob["blocks"])
        ob_calls_sum.update(ob["calls"])

    shared = {sig: rec_sum.get(sig, 0) for sig in SHARED_SYSTEM_SIGS}
    return {
        "esm_count": len(esm_scans),
        "esm_files": [s["file"] for s in esm_scans],
        "quests": dict(qust_sum),
        "dialogue": {**dict(dial_sum), "top_ctda_functions": dict(ctda_fn_sum.most_common(20))},
        "perks": dict(perk_sum),
        "shared_systems": shared,
        "obscript": {
            "scpt_records": scpt_records,
            "scpt_with_sctx": scpt_sctx,
            "scpt_local_vars": scpt_vars,
            "scpt_types": dict(scpt_types_sum),
            "embedded_sctx_records": dict(emb_sum),
            "blocks": dict(ob_blocks_sum),
            "calls": ob_calls_sum,
        },
    }


def _scan_bsa_dir(data_dir: str) -> Dict[str, object]:
    bsa_files = sorted(fn for fn in os.listdir(data_dir) if fn.lower().endswith(".bsa"))
    unique_paths: set = set()
    exts: Counter = Counter()
    per_bsa = []
    for fn in bsa_files:
        with BsaV104Reader(os.path.join(data_dir, fn)) as rdr:
            per_bsa.append({"archive": fn, "entries": len(rdr.entries), "flags": f"0x{rdr.archive_flags:04X}"})
            for e in rdr.entries:
                low = e.name.lower()
                if low not in unique_paths:
                    unique_paths.add(low)
                    exts[os.path.splitext(low)[1]] += 1
    return {
        "bsa_count": len(bsa_files),
        "unique_entries": len(unique_paths),
        "extensions": dict(exts.most_common(15)),
        "archives": per_bsa,
    }


def run_all_games_census(common_dir: str, out_dir: str) -> Dict[str, object]:
    """Run the complete read-only census across all 8 installed titles and write JSON/TSV artifacts."""
    os.makedirs(out_dir, exist_ok=True)
    t_start = time.time()
    results: Dict[str, object] = {}

    # 1. Fallout 1
    fo1_dir = os.path.join(common_dir, "Fallout")
    with Fo1DatReader(os.path.join(fo1_dir, "MASTER.DAT")) as m1, Fo1DatReader(os.path.join(fo1_dir, "CRITTER.DAT")) as c1:
        results["FO1"] = scan_classic_dat_set([("MASTER.DAT", m1), ("CRITTER.DAT", c1)], "Fallout 1")

    # 2. Fallout 2
    fo2_dir = os.path.join(common_dir, "Fallout 2")
    fo2_open = []
    try:
        for fn in ("critter.dat", "master.dat", "patch000.dat"):
            p = os.path.join(fo2_dir, fn)
            if os.path.isfile(p):
                fo2_open.append((fn, Fo2DatReader(p)))
        results["FO2"] = scan_classic_dat_set(fo2_open, "Fallout 2")
    finally:
        for _, r in fo2_open:
            r.close()

    # 3. Fallout Tactics
    fot_core = os.path.join(common_dir, "Fallout Tactics", "core")
    bos_paths = [os.path.join(fot_core, fn) for fn in sorted(os.listdir(fot_core)) if fn.lower().endswith(".bos")]
    results["FOT"] = scan_tactics_bos_archives(bos_paths)

    # 4 & 5. Fallout 3 GOTY & Fallout: New Vegas
    for key, title_label, folder in [
        ("FO3", "Fallout 3 GOTY", "Fallout 3 goty"),
        ("FNV", "Fallout: New Vegas", "Fallout New Vegas"),
    ]:
        ddir = os.path.join(common_dir, folder, "Data")
        esms = [os.path.join(ddir, fn) for fn in OFFICIAL_ESMS[key] if os.path.isfile(os.path.join(ddir, fn))]
        scans = [scan_esm_file(p, is_ce2=False, parse_obscript=True) for p in esms]
        base = _aggregate_esms([scans[0]])
        total = _aggregate_esms(scans)
        ob_combined = Counter(total["obscript"]["blocks"])
        ob_combined.update(total["obscript"]["calls"])
        base_combined = Counter(base["obscript"]["blocks"])
        base_combined.update(base["obscript"]["calls"])
        # Pop raw Counter before JSON serialization
        del base["obscript"]["calls"]
        del total["obscript"]["calls"]
        bsa_info = _scan_bsa_dir(ddir)
        results[key] = {
            "title": title_label,
            "bsa_archives": bsa_info,
            "base_esm": base,
            "all_official_esms": total,
            "scripts": {
                "runtime": "GECK ObScript (SCPT + embedded INFO/PACK/PERK/TERM SCTX/SCDA)",
                "base_scpt_records": base["obscript"]["scpt_records"],
                "base_scpt_with_sctx": base["obscript"]["scpt_with_sctx"],
                "all_dlc_scpt_records": total["obscript"]["scpt_records"],
                "all_dlc_scpt_with_sctx": total["obscript"]["scpt_with_sctx"],
                "all_dlc_embedded_sctx": total["obscript"]["embedded_sctx_records"],
                "all_dlc_scpt_types": total["obscript"]["scpt_types"],
                "all_dlc_local_vars": total["obscript"]["scpt_local_vars"],
                "all_dlc_blocks": total["obscript"]["blocks"],
                "distinct_functions_and_events": len(ob_combined),
                "base_top_40": [{"name": k, "count": v} for k, v in base_combined.most_common(40)],
                "top_40": [{"name": k, "count": v} for k, v in ob_combined.most_common(40)],
            },
        }

    # 6. Fallout 4
    fo4_data = os.path.join(common_dir, "Fallout 4", "Data")
    fo4_esms = [os.path.join(fo4_data, fn) for fn in OFFICIAL_ESMS["FO4"] if os.path.isfile(os.path.join(fo4_data, fn))]
    fo4_scans = [scan_esm_file(p, is_ce2=True, parse_obscript=False) for p in fo4_esms]
    fo4_base = _aggregate_esms([fo4_scans[0]])
    fo4_total = _aggregate_esms(fo4_scans)
    del fo4_base["obscript"]
    del fo4_total["obscript"]

    fo4_src_base = scan_psc_zip(os.path.join(fo4_data, "Scripts", "Source", "Base", "Base.zip"))
    fo4_dlc_zips = []
    fo4_all_psc_combined = Counter(fo4_src_base["combined"])
    fo4_all_psc_total = int(fo4_src_base["psc_total"])
    for dz in ("DLC01", "DLC02", "DLC03", "DLC04", "DLC05", "DLC06"):
        zp = os.path.join(fo4_data, "Scripts", "Source", dz, f"{dz}.zip")
        if os.path.isfile(zp):
            ds = scan_psc_zip(zp)
            fo4_all_psc_combined.update(ds["combined"])
            fo4_all_psc_total += int(ds["psc_total"])
            fo4_dlc_zips.append({"zip": f"{dz}.zip", "psc_total": ds["psc_total"]})
    fo4_all_psc_combined = _fold_papyrus_counter(fo4_all_psc_combined)
    del fo4_src_base["combined"]

    fo4_pex_ba2s = [
        os.path.join(fo4_data, "Fallout4 - Misc.ba2"),
        os.path.join(fo4_data, "DLCRobot - Main.ba2"),
        os.path.join(fo4_data, "DLCworkshop01 - Main.ba2"),
        os.path.join(fo4_data, "DLCworkshop02 - Main.ba2"),
        os.path.join(fo4_data, "DLCworkshop03 - Main.ba2"),
        os.path.join(fo4_data, "DLCCoast - Main.ba2"),
        os.path.join(fo4_data, "DLCNukaWorld - Main.ba2"),
    ]
    fo4_pex_info = scan_ba2_pex_set(fo4_pex_ba2s)
    results["FO4"] = {
        "title": "Fallout 4",
        "base_esm": fo4_base,
        "all_official_esms": fo4_total,
        "scripts": {
            "runtime": "Papyrus VM v3.9 (Creation Engine 64-bit)",
            "base_zip": fo4_src_base,
            "dlc_source_zips": fo4_dlc_zips,
            "all_psc_total_base_plus_dlc": fo4_all_psc_total,
            "ba2_pex": fo4_pex_info,
            "distinct_functions_and_events": fo4_src_base["distinct_functions_and_events"],
            "top_40": fo4_src_base["top_40"],
            "all_dlc_psc_top_40": [{"name": k, "count": v} for k, v in fo4_all_psc_combined.most_common(40)],
        },
    }

    # 7. Fallout 76
    fo76_data = os.path.join(common_dir, "Fallout76", "Data")
    fo76_esms = [os.path.join(fo76_data, fn) for fn in OFFICIAL_ESMS["FO76"] if os.path.isfile(os.path.join(fo76_data, fn))]
    fo76_scans = [scan_esm_file(p, is_ce2=True, parse_obscript=False) for p in fo76_esms]
    fo76_base = _aggregate_esms([fo76_scans[0]])
    fo76_total = _aggregate_esms(fo76_scans)
    del fo76_base["obscript"]
    del fo76_total["obscript"]

    fo76_pex_info = scan_ba2_pex_set([os.path.join(fo76_data, "SeventySix - MiscClient.ba2")])
    results["FO76"] = {
        "title": "Fallout 76",
        "base_esm": fo76_base,
        "all_official_esms": fo76_total,
        "scripts": {
            "runtime": "Papyrus VM v3.15 Client/Server Split (SeventySix - MiscClient.ba2; server quest .pex omitted)",
            "psc_source_count": 0,
            "ba2_pex": fo76_pex_info,
            "distinct_functions_and_events": fo76_pex_info["distinct_functions_and_events"],
            "top_40": fo76_pex_info["top_40"],
        },
    }

    # 8. Starfield
    sf_root = os.path.join(common_dir, "Starfield")
    sf_data = os.path.join(sf_root, "Data")
    sf_esms = [os.path.join(sf_data, fn) for fn in OFFICIAL_ESMS["SF"] if os.path.isfile(os.path.join(sf_data, fn))]
    sf_scans = [scan_esm_file(p, is_ce2=True, parse_obscript=False) for p in sf_esms]
    sf_base_start_edids = sf_scans[0]["qust_detail"]["start_enabled_edids"]
    sf_base = _aggregate_esms([sf_scans[0]])
    sf_total = _aggregate_esms(sf_scans)
    del sf_base["obscript"]
    del sf_total["obscript"]

    sf_src = scan_psc_zip(os.path.join(sf_root, "Tools", "ContentResources.zip"))
    del sf_src["combined"]
    sf_pex_ba2s = [
        os.path.join(sf_data, fn)
        for fn in sorted(os.listdir(sf_data))
        if fn.lower().endswith(".ba2")
        and (fn.lower() == "starfield - misc.ba2" or (fn.lower().startswith("sfbgs") and fn.lower().endswith("main.ba2")))
    ]
    sf_pex_info = scan_ba2_pex_set(sf_pex_ba2s)

    protected_set = set(STARFIELD_PROTECTED_QUESTS)
    present_protected = sorted(q for q in sf_base_start_edids if q in protected_set)
    results["SF"] = {
        "title": "Starfield",
        "base_esm": sf_base,
        "all_official_esms": sf_total,
        "cold_start_boundary": {
            "starfield_esm_start_enabled_count": len(sf_base_start_edids),
            "protected_quests_defined": list(STARFIELD_PROTECTED_QUESTS),
            "protected_quests_start_enabled_in_esm": present_protected,
        },
        "scripts": {
            "runtime": "Papyrus VM v3.12 / v4.2 Source (Guard lock opcodes 0x30..0x32)",
            "content_resources_zip": sf_src,
            "ba2_pex": sf_pex_info,
            "distinct_functions_and_events": sf_src["distinct_functions_and_events"],
            "top_40": sf_src["top_40"],
        },
    }

    # 9. FO3 & FNV 40-Quest Readiness Data
    fo3_q = extract_fo3_fnv_quest_dependencies(
        os.path.join(common_dir, "Fallout 3 goty", "Data", "Fallout3.esm"),
        FO3_MAIN_10,
        FO3_SIDE_10,
    )
    fnv_q = extract_fo3_fnv_quest_dependencies(
        os.path.join(common_dir, "Fallout New Vegas", "Data", "FalloutNV.esm"),
        FNV_MAIN_10,
        FNV_SIDE_10,
    )

    elapsed = round(time.time() - t_start, 2)
    summary_doc = {
        "schema_version": 1,
        "elapsed_seconds": elapsed,
        "titles": results,
    }

    # Write JSON & TSV artifacts to out_dir
    with open(os.path.join(out_dir, "all_games_census.json"), "w", encoding="utf-8", newline="\n") as fp:
        json.dump(summary_doc, fp, indent=2)

    with open(os.path.join(out_dir, "fo3_fnv_40_quests.json"), "w", encoding="utf-8", newline="\n") as fp:
        json.dump({"FO3": fo3_q, "FNV": fnv_q}, fp, indent=2)

    # Write Top-40 TSV across all 8 titles
    with open(os.path.join(out_dir, "top_40_functions_by_title.tsv"), "w", encoding="utf-8", newline="\n") as fp:
        fp.write("title\trank\tidentifier\tcount\n")
        for tkey in ("FO1", "FO2", "FOT", "FO3", "FNV", "FO4", "FO76", "SF"):
            top_list = results[tkey]["scripts"]["top_40"]
            for rank, item in enumerate(top_list, 1):
                fp.write(f"{tkey}\t{rank}\t{item['name']}\t{item['count']}\n")

    # Write Bethesda Shared Systems TSV (base ESM + all official ESMs)
    with open(os.path.join(out_dir, "bethesda_shared_systems_counts.tsv"), "w", encoding="utf-8", newline="\n") as fp:
        cols = ["title", "scope", "QUST", "DIAL", "INFO", "SCEN"] + list(SHARED_SYSTEM_SIGS)
        fp.write("\t".join(cols) + "\n")
        for tkey in ("FO3", "FNV", "FO4", "FO76", "SF"):
            for scope in ("base_esm", "all_official_esms"):
                blk = results[tkey][scope]
                row = [
                    tkey,
                    scope,
                    str(blk["quests"]["quests"]),
                    str(blk["dialogue"]["dial_topics"]),
                    str(blk["dialogue"]["info_responses"]),
                    str(blk["dialogue"]["scen_scenes"]),
                ]
                for sig in SHARED_SYSTEM_SIGS:
                    row.append(str(blk["shared_systems"].get(sig, 0)))
                fp.write("\t".join(row) + "\n")

    # Write FO3/FNV 40 Quests TSV
    with open(os.path.join(out_dir, "fo3_fnv_40_quests.tsv"), "w", encoding="utf-8", newline="\n") as fp:
        fp.write(
            "title\tcategory\torder\tedid\tform_id\tstages\tobjectives\tquest_script\t"
            "external_scpts\tdial_owned\tinfo_owned\tinfo_cross_refs\tinfo_result_scripts\t"
            "info_skill_checks\tinfo_perk_checks\tinfo_repu_checks\tpack_count\n"
        )
        for tkey, qdoc in (("FO3", fo3_q), ("FNV", fnv_q)):
            for grp in ("main_10", "side_10"):
                for r in qdoc[grp]:
                    fp.write(
                        f"{tkey}\t{r['category']}\t{r['order']}\t{r['edid']}\t{r['form_id']}\t"
                        f"{r['stage_count']}\t{r['objective_count']}\t{r['quest_script']}\t"
                        f"{r['external_scpt_count']}\t{r['dial_topics_owned']}\t{r['info_owned']}\t"
                        f"{r['info_cross_quest_refs']}\t{r['info_result_scripts']}\t"
                        f"{r['info_skill_av_checks']}\t{r['info_perk_checks']}\t"
                        f"{r['info_repu_faction_checks']}\t{r['pack_count']}\n"
                    )

    return summary_doc


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only multi-title quest, script, and shared-systems census.")
    ap.add_argument("--common-dir", required=True, help="Directory containing installed game folders (read-only).")
    ap.add_argument("--out-dir", required=True, help="Output directory for JSON and TSV census tables.")
    args = ap.parse_args(argv)

    doc = run_all_games_census(args.common_dir, args.out_dir)
    print(f"census: ok ({doc['elapsed_seconds']:.2f}s) -> {len(doc['titles'])} titles written")
    for tkey, tdata in doc["titles"].items():
        sc = tdata["scripts"]
        top1 = sc["top_40"][0] if sc["top_40"] else {"name": "none", "count": 0}
        print(f"  {tkey:4s}: distinct_fn_events={sc['distinct_functions_and_events']:4d} top1={top1['name']}({top1['count']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
