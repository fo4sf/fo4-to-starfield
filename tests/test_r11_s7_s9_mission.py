#!/usr/bin/env python3
"""Offline tests for Round 11 S7 (Concord roof), S8 (DN092 Wave 2 respawnPool=8 & Deathclaw), and S9 (lobby + Red Rocket walk home + Min01 1000 hard stop)."""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS_MISSION = ROOT / "scripts" / "mission"
for _p in (str(SRC), str(SCRIPTS_MISSION)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_mission  # noqa: E402
from fo4sf.core.cross_plugin_check import build_writer_catalog  # noqa: E402
from fo4sf.mission import dn092_wave  # noqa: E402

MIN00_PSC = (SCRIPTS_MISSION / "FO4SF_Min00Quest.psc").read_text(encoding="utf-8")
SANC01_PSC = (SCRIPTS_MISSION / "FO4SF_Sanctuary01Quest.psc").read_text(encoding="utf-8")
MINREC_PSC = (SCRIPTS_MISSION / "FO4SF_MinRecruit00Quest.psc").read_text(encoding="utf-8")
MQ103_PSC = (SCRIPTS_MISSION / "FO4SF_MQ103Quest.psc").read_text(encoding="utf-8")
S7S9_CS = (ROOT / "dotnet" / "Mission" / "NextStoryMissionsS7S9.cs").read_text(encoding="utf-8")
PROGRAM_CS = (ROOT / "dotnet" / "Mission" / "Program.cs").read_text(encoding="utf-8")


class S7RoofAndMinigunContractTests(unittest.TestCase):
    def test_s7_roof_coords_empty_frame_and_minigun_contract(self) -> None:
        self.assertEqual(dn092_wave.S7_ROOF_DOOR_POS, (-2008.49, -1722.39, 97.42))
        self.assertEqual(dn092_wave.S7_ROOF_FRAME_POS, (-1995.73, -1723.10, 97.54))
        self.assertEqual(dn092_wave.S7_ROOF_MINIGUN_POS, (-2004.72, -1715.40, 102.68))

        for token in (
            "0x000801",  # FO4SFPowerArmor FURN frame (no pre-installed core)
            "0x000809",  # FO4SF_FusionCore from 2h/S6
            "SyncS7RoofFrameGate(player)",
            "s7RoofFrameRef.BlockActivation(cores <= 0, False)",
            "player.AddItem(r5mm, 1200, False)",
            "s7 roof confirmed frame_no_core=true",
        ):
            self.assertIn(token, MIN00_PSC)
        # Finding 5: Min00 must NOT directly AddPerk(0x00081E); FO4SF_PowerArmorCoreQuest owns PA fall-damage perk on enter/exit.
        self.assertNotIn(".AddPerk(", MIN00_PSC)
        for token in ("CoreMinigunId = 0x0008A0", "CoreAmmo5mmId = 0x00089F", "vertibirdminigun.nif"):
            self.assertIn(token, S7S9_CS)

    def test_s7_frame_activation_blocks_without_fusion_core_and_unlocks_with_core(self) -> None:
        from types import SimpleNamespace
        from tests.test_r11_cell_independent_quest import _compile_papyrus

        block_calls: list[tuple[bool, bool]] = []
        logs: list[str] = []
        notifs: list[str] = []
        fc_count = [0]
        obj_done: set[int] = set()
        frame_ref = SimpleNamespace(BlockActivation=lambda blk, abs_off=False: block_calls.append((bool(blk), bool(abs_off))))
        player = SimpleNamespace(GetItemCount=lambda _f: fc_count[0])
        ns = {
            "s7RoofFrameRef": frame_ref,
            "Game": SimpleNamespace(GetFormFromFile=lambda fid, plg: ("FC", fid, plg)),
            "IsTestModeEnabled": lambda: True,
            "IsObjectiveDisplayed": lambda idx: int(idx) == 95,
            "IsObjectiveCompleted": lambda idx: int(idx) in obj_done,
            "SetObjectiveCompleted": lambda idx: obj_done.add(int(idx)),
            "Debug": SimpleNamespace(Notification=lambda msg: notifs.append(str(msg))),
            "Trace": lambda msg: logs.append(str(msg)),
        }
        _compile_papyrus(MIN00_PSC, ["SyncS7RoofFrameGate", "OnS7RoofFrameActivated"], {"s7RoofFrameRef"}, ns)
        ns["SyncS7RoofFrameGate"](player)
        ns["OnS7RoofFrameActivated"](player)
        self.assertEqual(block_calls[-1], (True, False))
        self.assertNotIn(95, obj_done)
        self.assertTrue(any("refused reason=no_fusion_core" in lg for lg in logs))
        self.assertEqual(len(notifs), 1)

        fc_count[0] = 1
        ns["SyncS7RoofFrameGate"](player)
        ns["OnS7RoofFrameActivated"](player)
        self.assertEqual(block_calls[-1], (False, False))
        self.assertIn(95, obj_done)
        self.assertTrue(any("roof_frame entered core=0x0809 cores=1" in lg for lg in logs))


class S8DN092RespawnPoolAndDeathclawTests(unittest.TestCase):
    def test_respawn_pool_8_respawns_only_wave_raiders_01_to_03_between_stage_75_and_79(self) -> None:
        ctl = dn092_wave.DN092WaveController(creature_slot_available=False)
        self.assertEqual(ctl.dn092_stage, 75)
        self.assertEqual(ctl.respawn_pool, 8)
        self.assertEqual(len(dn092_wave.WAVE_ALIASES), 5)

        far_player = (-2000.0, -1700.0, 88.0)

        # Gristle & RoofLookout must stay permanently dead and NEVER consume respawn_pool
        ctl.on_member_killed("Gristle", far_player)
        ctl.on_member_killed("RoofLookout", far_player)
        self.assertEqual(ctl.respawn_pool, 8)
        self.assertTrue(ctl.members["Gristle"].permanently_dead)
        self.assertTrue(ctl.members["RoofLookout"].permanently_dead)
        self.assertFalse(ctl.members["Gristle"].alive)
        self.assertFalse(ctl.members["RoofLookout"].alive)
        self.assertEqual(ctl.dn092_stage, 75)

        # Kills 3..7 burn respawnPool on WaveRaider01..03 and move them across DN092WaveSpawner01..06
        for ki, alias in enumerate(("WaveRaider01", "WaveRaider02", "WaveRaider03", "WaveRaider01", "WaveRaider02")):
            trig = ctl.on_member_killed(alias, far_player)
            self.assertIsNone(trig)
            self.assertEqual(ctl.respawn_pool, 7 - ki)
            self.assertTrue(ctl.members[alias].alive)
            self.assertEqual(ctl.dn092_stage, 75)

        # Kill 8 (wave_kills == 8) fires wave_kills trigger, sets stage 79, logs deathclaw_slot=empty
        trig8 = ctl.on_member_killed("WaveRaider03", far_player)
        self.assertEqual(trig8, "wave_kills")
        self.assertEqual(ctl.dn092_stage, 79)
        self.assertEqual(ctl.deathclaw_slot_status, "empty")
        self.assertTrue(any("deathclaw_slot=empty dn092_stage=79" in lg for lg in ctl.logs))

        # Now at stage 79 (above 75..79 window) + pool exhausted, killing remaining 3 clears the wave cleanly
        for alias in ("WaveRaider01", "WaveRaider02", "WaveRaider03"):
            ctl.on_member_killed(alias, far_player)
        self.assertTrue(ctl.is_wave_cleared)
        self.assertGreaterEqual(ctl.respawn_pool, 2)  # remaining pool unused after stage 79

    def test_respawn_pool_exhausts_at_zero_when_all_8_wave_kills_are_respawnables(self) -> None:
        ctl = dn092_wave.DN092WaveController(creature_slot_available=True)
        far_player = (-2000.0, -1700.0, 88.0)
        for i in range(8):
            alias = f"WaveRaider0{(i % 3) + 1}"
            ctl.on_member_killed(alias, far_player)
        self.assertEqual(ctl.respawn_pool, 0)
        self.assertEqual(ctl.deathclaw_trigger, "wave_kills")
        self.assertEqual(ctl.dn092_stage, 79)
        self.assertEqual(ctl.deathclaw_slot_status, "bound")
        self.assertTrue(ctl.deathclaw_alive)
        self.assertTrue(
            any("creature_slot=bound hp=615 dr=100 er=150 claw=60" in lg for lg in ctl.logs)
        )
        # Wave stays uncleared until Deathclaw + all wave actors + bosses are dead
        for alias in ("WaveRaider01", "WaveRaider02", "WaveRaider03", "RoofLookout", "Gristle"):
            ctl.on_member_killed(alias, far_player)
        self.assertFalse(ctl.is_wave_cleared)
        ctl.on_deathclaw_killed()
        self.assertTrue(ctl.is_wave_cleared)

    def test_spawner_picks_failsafe_wavepost02_when_player_blocks_all_six_spawners(self) -> None:
        # Place player within 18m of WaveSpawner04 (-2054.62, -1613.32, 88.15), check rotation picks away spawner,
        # and verify direct failsafe fallback when distances are artificially < 18m
        ctl = dn092_wave.DN092WaveController()
        near_ws1 = dn092_wave.WAVE_SPAWNERS[0][1]
        label, pos = ctl.pick_spawner(near_ws1)
        self.assertNotIn("WaveSpawner01", label)
        self.assertNotEqual(pos, near_ws1)

        with unittest.mock.patch("fo4sf.mission.dn092_wave.MIN_SPAWNER_DIST_M", 500.0):
            fs_label, fs_pos = ctl.pick_spawner(near_ws1)
        self.assertIn("failsafe_WavePost02", fs_label)
        self.assertEqual(fs_pos, dn092_wave.WAVE_FAILSAFE_SPAWNER[1])

    def test_deathclaw_grate_proximity_17m_and_300s_timer_triggers(self) -> None:
        # Grate trigger at <= 17.0m of DN092ForceSpawnDeathclawTrigger 0009A144
        ctl_grate = dn092_wave.DN092WaveController()
        gx, gy, gz = dn092_wave.GRATE_TRIGGER_POS
        self.assertIsNone(ctl_grate.evaluate_deathclaw_triggers((gx + 17.2, gy, gz), dt=5.0))
        self.assertEqual(ctl_grate.dn092_stage, 75)
        self.assertEqual(ctl_grate.evaluate_deathclaw_triggers((gx + 16.5, gy, gz), dt=1.0), "grate_proximity")
        self.assertEqual(ctl_grate.dn092_stage, 79)
        self.assertTrue(any("trigger=grate_proximity dn092_stage=79" in lg for lg in ctl_grate.logs))

        # 300s timer trigger when neither wave_kills nor grate_proximity fired
        ctl_timer = dn092_wave.DN092WaveController()
        far_player = (-1980.0, -1720.0, 88.0)
        self.assertIsNone(ctl_timer.evaluate_deathclaw_triggers(far_player, dt=299.0))
        self.assertEqual(ctl_timer.evaluate_deathclaw_triggers(far_player, dt=1.5), "timer_300s")
        self.assertEqual(ctl_timer.dn092_stage, 79)
        self.assertTrue(any("trigger=timer_300s dn092_stage=79" in lg for lg in ctl_timer.logs))


    def test_s8_papyrus_respawning_guard_prevents_premature_completion_and_holding_cell_is_used(self) -> None:
        from types import SimpleNamespace
        from tests.test_r11_cell_independent_quest import _compile_papyrus

        # Findings 2 & 3: 0xBF5 holding cell in S7S9_CS, zero `- MergeOffset` offsets, host anchor fallback
        self.assertIn("S7S9HoldingCellId = 0xBF5", S7S9_CS)
        self.assertNotIn("- MergeOffset", S7S9_CS)
        self.assertIn("RelocateHoldingRefToCommonwealth(", MIN00_PSC)
        self.assertIn("ResolveCommonwealthHostAnchor()", MIN00_PSC)

        # Finding 4: Simulate kill + CheckS8WaveAndDeathclaw while a wave raider is mid-Utility.Wait(0.5) respawn
        dead_flags = [True, True, True, True, True]
        actors = [SimpleNamespace(IsDead=lambda i=i: dead_flags[i], Resurrect=lambda i=i: dead_flags.__setitem__(i, False)) for i in range(5)]
        spawners = [SimpleNamespace(GetPositionX=lambda: -2090.0, GetPositionY=lambda: -1650.0, GetPositionZ=lambda: 88.5)]
        logs: list[str] = []
        stages_set: list[int] = []
        objs_done: list[int] = []
        objs_disp: list[int] = []

        def check_during_wait(_dt: float) -> None:
            # Even if Deathclaw + everyone else look dead while Utility.Wait(0.5) is paused, S8 MUST stay open!
            ns["CheckS8WaveAndDeathclaw"](player, 0.0)
            self.assertFalse(ns["s8WaveCleared"])

        player = SimpleNamespace(GetDistance=lambda _r: 30.0)
        ns = {
            "EnableS6ToS9Full": True,
            "KeeperOnly": False,
            "s8WaveStarted": True,
            "s8WaveCleared": False,
            "s8WavePermDead": [False] * 5,
            "S8WaveActors": actors,
            "S8WaveSpawners": spawners,
            "S8WaveFailsafeMarker": spawners[0],
            "S8GrateTriggerMarker": None,
            "S8DeathclawSpawnMarker": spawners[0],
            "S8SpawnerMinPlayerDist": 18.0,
            "S8GrateTriggerRadius": 17.0,
            "S8DeathclawTimerSeconds": 300.0,
            "DeathclawBaseOverride": None,
            "DeathclawCreaturePlugin": "",
            "DeathclawCreatureFormId": 0,
            "s8RespawnPool": 1,
            "s8RespawningCount": 0,
            "s8WaveKills": 7,
            "s8Dn092Stage": 75,
            "s8SpawnerCursor": 0,
            "s8ElapsedSec": 0.0,
            "s8DeathclawSpawned": True,
            "s8DeathclawCleared": True,
            "s8DeathclawTrigger": "wave_kills",
            "s8DeathclawRef": None,
            "s6FullStage": 65,
            "Utility": SimpleNamespace(Wait=check_during_wait),
            "MoveActorToExteriorSpot": lambda *a: None,
            "EnsureS8TrackingArrays": lambda: None,
            "FO4SF_Sanctuary01Quest": SimpleNamespace(EngageTarget=lambda *a: None),
            "IsCommonwealthExterior": lambda _p: True,
            "SetObjectiveCompleted": lambda o: objs_done.append(o),
            "SetObjectiveDisplayed": lambda o, *_a: objs_disp.append(o),
            "SetStage": lambda s: stages_set.append(s),
            "SetActive": lambda *_a: None,
            "Trace": lambda msg: logs.append(str(msg)),
        }
        gvars = {
            "s8WaveStarted", "s8WaveCleared", "s8WavePermDead", "s8RespawnPool",
            "s8RespawningCount", "s8WaveKills", "s8Dn092Stage", "s8SpawnerCursor",
            "s8ElapsedSec", "s8DeathclawSpawned", "s8DeathclawCleared", "s8DeathclawTrigger",
            "s8DeathclawRef", "s6FullStage",
        }
        _compile_papyrus(
            MIN00_PSC,
            ["PickS8WaveSpawner", "SpawnS8Deathclaw", "CheckS8WaveAndDeathclaw", "OnS8MemberKilled"],
            gvars,
            ns,
        )
        # Kill #8 triggers Utility.Wait(0.5); inside check_during_wait s8RespawningCount == 1 prevents premature clear,
        # then Resurrect() brings WaveRaider01 back alive (dead_flags[0] == False), so S8 stays uncleared afterward too.
        ns["OnS8MemberKilled"](0, actors[0], player)
        self.assertFalse(dead_flags[0])
        self.assertFalse(ns["s8WaveCleared"])
        self.assertEqual(ns["s8RespawningCount"], 0)
        # Now finish resurrected WaveRaider01 -> pool exhausted (0), clears cleanly!
        dead_flags[0] = True
        ns["OnS8MemberKilled"](0, actors[0], player)
        self.assertTrue(ns["s8WaveCleared"])
        self.assertEqual(stages_set, [80])
        self.assertIn(65, objs_done)
        self.assertIn(140, objs_disp)


class S9LobbyWalkHomeAndHardStopTests(unittest.TestCase):
    def test_s9_lobby_reward_order_and_zero_credits(self) -> None:
        for token in (
            "lobby_markers=0001F5B6,0001F5B7",
            "sanctuaryQuest.SetStage(20)",
            "SetStage(100)",
            "s9 sequence dialogue_concord_area=50 min01_stage=20 min00_stage=100 credits=0",
            "RevealDiamondCityMapMarker(player)",
            "SetStage(150)",
        ):
            self.assertIn(token, MIN00_PSC)
        self.assertNotIn("AddItem(Credits", MIN00_PSC.split("CompleteS9LobbyTalkAndReward", 1)[1].split("EndFunction", 1)[0])
        self.assertIn("CoreBottlecapId = 0x0008A4", S7S9_CS)
        self.assertIn("CoreFusionCellId = 0x00089B", S7S9_CS)

    def test_s9_never_teleport_in_view_failsafe(self) -> None:
        # Close to Preston while 3D loaded -> MUST NOT teleport even after 180s
        self.assertFalse(
            dn092_wave.s9_failsafe_can_teleport(
                player_dist_to_preston=25.0,
                preston_dist_to_sanctuary=220.0,
                preston_3d_loaded=True,
                player_in_sanctuary=False,
                patrol_elapsed_sec=240.0,
            )
        )
        # Player moved > 65m away -> failsafe teleport allowed
        self.assertTrue(
            dn092_wave.s9_failsafe_can_teleport(
                player_dist_to_preston=95.0,
                preston_dist_to_sanctuary=220.0,
                preston_3d_loaded=True,
                player_in_sanctuary=True,
                patrol_elapsed_sec=190.0,
            )
        )
        # Unloaded cell (`preston_3d_loaded=False`) -> failsafe teleport allowed cleanly
        self.assertTrue(
            dn092_wave.s9_failsafe_can_teleport(
                player_dist_to_preston=12.0,
                preston_dist_to_sanctuary=220.0,
                preston_3d_loaded=False,
                player_in_sanctuary=False,
                patrol_elapsed_sec=190.0,
            )
        )
        self.assertIn("failsafe_deferred reason=in_player_view", MIN00_PSC)

    def test_s9_sanctuary_220_sturges_intro_and_1000_hard_stop(self) -> None:
        self.assertIn("sancScript.AdvanceTo(220, \"s9_arrival\")", MIN00_PSC)
        self.assertIn("PlaceRefInMuseumOffset(", MIN00_PSC)
        self.assertIn("58101", MIN00_PSC)  # 0x00E2F5 ConcordMuseum01 anchor without false 0E2 literal
        self.assertIn("0x000BF4", SANC01_PSC)  # HasS9HardStop GLOB
        self.assertIn("0x000C05", SANC01_PSC)  # Gated fallback MESG
        self.assertIn("S9SturgesIntroScene", SANC01_PSC)
        self.assertIn("(st == 220 && ShouldUseMessageBox())", SANC01_PSC)
        self.assertIn("001188B4", SANC01_PSC)
        self.assertIn("AdvanceTo(1000, \"sturges_intro\")", SANC01_PSC)
        self.assertIn("HasS9HardStop()", SANC01_PSC)
        self.assertIn("0x000BF4", MINREC_PSC)
        self.assertIn("0x000BF4", MQ103_PSC)
        self.assertIn("65, \"Clear Concord of Hostiles\"", PROGRAM_CS)
        self.assertIn("S9PrestonLobbyScene", S7S9_CS)
        self.assertIn("S9SturgesIntroScene", S7S9_CS)
        self.assertIn("SF.Quest.Flag.HasDialogueData", S7S9_CS)
        # Finding 1: deleted dummy Sturges MESG must NEVER reappear in scripts/Program.cs, and CheckS7S9 forbids it in the plugin
        for txt in (PROGRAM_CS, SANC01_PSC, MIN00_PSC):
            self.assertNotIn("FO4SF_S9_SturgesIntroMsg", txt)
        self.assertIn('need(!plug.Messages.Any(m => m.EditorID == "FO4SF_S9_SturgesIntroMsg")', S7S9_CS)
        self.assertEqual(len(make_mission.S9_LOBBY_CLIP_SPECS), 2)
        self.assertEqual(len(make_mission.S9_STURGES_CLIP_SPECS), 2)
        self.assertEqual(make_mission.FIRST_S9_WEM, 0x00F4C301)

    def test_make_mission_summarize_tracks_s7_to_s9_and_cross_plugin_check(self) -> None:
        sample_log = [
            "FO4SF_MISSION rt=10.0 s7 roof confirmed frame_no_core=true frame_spawned=true minigun_enabled=true",
            "FO4SF_MISSION rt=15.0 s7 minigun grabbed count_minigun=1 count_5mm=1200 has_weap=true has_ammo=true",
            "FO4SF_MISSION rt=20.0 s7 street_drop z=88.50 no_fall_perk=true dmg=0",
            "FO4SF_MISSION rt=21.0 s8 wave2 started obj=65 dn092_stage=75 respawn_pool=8",
            "FO4SF_MISSION rt=40.0 s8 wave respawn idx=0 pool_left=7 wave_kills=1 spawner=0xBEB",
            "FO4SF_MISSION rt=95.0 s8 deathclaw spawn trigger=wave_kills dn092_stage=79",
            "FO4SF_MISSION rt=95.0 s8 deathclaw deathclaw_slot=empty dn092_stage=79",
            "FO4SF_MISSION rt=110.0 s9 sequence dialogue_concord_area=50 min01_stage=20 min00_stage=100 credits=0",
            "FO4SF_MISSION rt=290.0 sanctuary01 min01_sturges_intro form=001188B4 -> stage 1000",
            "FO4SF_MISSION rt=295.0 sanctuary01 s9_hard_stop minrecruit00=0 mq103=0",
        ]
        summary = make_mission.summarize(sample_log)
        self.assertEqual(len(summary["s7_events"]), 3)
        self.assertEqual(len(summary["s8_events"]), 4)
        self.assertEqual(len(summary["s9_events"]), 3)

        catalog, dups = build_writer_catalog(str(ROOT))
        self.assertEqual(dups, [])
        m_tbl = catalog["FO4SFMission.esm"]
        for fid, rtype in (
            (0xBE0, "ACTI"),
            (0xBE1, "REFR"),
            (0xBE4, "NPC_"),
            (0xBE6, "ACHR"),
            (0xBEB, "REFR"),
            (0xBF2, "REFR"),
            (0xBF3, "REFR"),
            (0xBF4, "GLOB"),
            (0xBF5, "CELL"),
            (0xBF6, "SCEN"),
            (0xBFD, "SCEN"),
            (0xC04, "MESG"),
            (0xC05, "MESG"),
        ):
            self.assertEqual(m_tbl[fid][0], rtype)
        self.assertEqual(catalog["FO4SFCoreValues.esm"][0x0008A4], ("MISC", "FO4_Caps"))
        self.assertEqual(catalog["FO4SFPowerArmor.esm"][0x00081E], ("PERK", "FO4SF_PANoFallDamagePerk"))

    def test_s9_lobby_scene_async_on_end_suppression_prevents_retry_burn(self) -> None:
        from types import SimpleNamespace
        from tests.test_r11_cell_independent_quest import _compile_papyrus

        scn_state = {"playing": True, "stops": 0, "starts": 0}
        lobby_scn = SimpleNamespace(
            IsPlaying=lambda: scn_state["playing"],
            Stop=lambda: (scn_state.__setitem__("stops", scn_state["stops"] + 1), scn_state.__setitem__("playing", False)),
            Start=lambda: (scn_state.__setitem__("starts", scn_state["starts"] + 1), scn_state.__setitem__("playing", True)),
        )
        completed_calls: list[str] = []
        reg_events: list[str] = []
        logs: list[str] = []
        player = object()
        ns = {
            "KeeperOnly": False,
            "Preston": SimpleNamespace(),
            "PrestonMaxSceneRestarts": 3,
            "PrestonSceneCheckSeconds": 1.5,
            "PrestonSceneMaxWaitChecks": 16,
            "S9PrestonLobbyScene": lobby_scn,
            "S9PrestonLobbyFallbackMsg": None,
            "s9LobbyCompleted": False,
            "s9LobbyScenePending": True,
            "s9LobbySceneMenuOpened": False,
            "s9LobbySceneAttemptOpened": False,
            "s9LobbyScenePhase1": False,
            "s9LobbyScenePhase1At": 0.0,
            "s9LobbySceneChecks": 0,
            "s9LobbySceneRestarts": 3,
            "ownS9LobbyStopPending": False,
            "prestonDialogueMenuOpen": False,
            "s8RespawningCount": 2,
            "ShouldUseMessageBox": lambda: False,
            "EffectiveStage": lambda: 80,
            "EnsurePrestonAlias": lambda: None,
            "EnsureActorTalkable": lambda _a: None,
            "RegisterForRemoteEvent": lambda _o, ev: reg_events.append(str(ev)),
            "EnterS9MuseumLobby": lambda _p: None,
            "CancelTimer": lambda _tid: None,
            "StartTimer": lambda _s, _tid: None,
            "CompleteS9LobbyTalkAndReward": lambda _p: (completed_calls.append("reward"), ns.__setitem__("s9LobbyCompleted", True)),
            "BeginS9MuseumExitAndPatrol": lambda _p: completed_calls.append("patrol"),
            "Game": SimpleNamespace(GetPlayer=lambda: player),
            "Utility": SimpleNamespace(GetCurrentRealTime=lambda: 100.0),
            "Trace": lambda msg: logs.append(str(msg)),
        }
        gvars = {
            "s9LobbyCompleted", "s9LobbyScenePending", "s9LobbySceneMenuOpened",
            "s9LobbySceneAttemptOpened", "s9LobbyScenePhase1", "s9LobbyScenePhase1At",
            "s9LobbySceneChecks", "s9LobbySceneRestarts", "ownS9LobbyStopPending",
            "prestonDialogueMenuOpen", "s8RespawningCount",
        }
        _compile_papyrus(
            MIN00_PSC,
            [
                "EnsureS9LobbySceneEvents",
                "ResetS9LobbyRuntimeState",
                "IsS9LobbySceneBusy",
                "RestartOrFailS9LobbyScene",
                "TryS9LobbyDialogueMenuOpen",
                "TryS9LobbyDialogueMenuClose",
                "TryTriggerS9LobbyActivate",
                "HandleS9LobbySceneEnd",
            ],
            gvars,
            ns,
        )
        # Finding 3: reload reset MUST NOT zero s8RespawningCount
        ns["ResetS9LobbyRuntimeState"]()
        self.assertEqual(ns["s8RespawningCount"], 2)

        # Finding 4: Fresh [E] activation resets exhausted restarts (3 -> 0) and registers scene listeners
        ns["s9LobbySceneRestarts"] = 3
        ns["TryTriggerS9LobbyActivate"](player)
        self.assertEqual(ns["s9LobbySceneRestarts"], 0)
        self.assertEqual(sorted(reg_events), ["OnBegin", "OnEnd", "OnPhaseBegin"])

        # Finding 2: Attempt 1 stops while playing -> Attempt 2 opens DialogueMenu BEFORE Attempt 1's async OnEnd arrives!
        ns["RestartOrFailS9LobbyScene"]("no_dialoguemenu")
        self.assertEqual(ns["s9LobbySceneRestarts"], 1)
        self.assertTrue(ns["ownS9LobbyStopPending"])

        self.assertTrue(ns["TryS9LobbyDialogueMenuOpen"](80))
        self.assertTrue(ns["s9LobbySceneAttemptOpened"])
        self.assertTrue(ns["ownS9LobbyStopPending"])  # MUST stay True until stale OnEnd consumes it!

        # Stale Attempt 1 OnEnd arrives -> suppressed cleanly!
        ns["HandleS9LobbySceneEnd"]()
        self.assertFalse(ns["ownS9LobbyStopPending"])
        self.assertEqual(completed_calls, [])
        self.assertTrue(ns["s9LobbySceneAttemptOpened"])

        # Finding 1: DialogueMenu closes BEFORE Attempt 2's Scene.OnEnd fires -> wasOpened still completes S9 Lobby!
        ns["prestonDialogueMenuOpen"] = False
        self.assertTrue(ns["TryS9LobbyDialogueMenuClose"]())
        self.assertFalse(ns["s9LobbySceneMenuOpened"])
        self.assertTrue(ns["s9LobbySceneAttemptOpened"])
        ns["HandleS9LobbySceneEnd"]()
        self.assertEqual(completed_calls, ["reward", "patrol"])
        self.assertFalse(ns["s9LobbySceneAttemptOpened"])

    def test_s9_sturges_intro_dialogue_close_before_on_end_stale_stop_and_museum_anchor(self) -> None:
        from types import SimpleNamespace
        from tests.test_r11_cell_independent_quest import _compile_papyrus

        scn_state = {"playing": True, "stops": 0, "starts": 0}
        intro_scn = SimpleNamespace(
            IsPlaying=lambda: scn_state["playing"],
            Stop=lambda: (scn_state.__setitem__("stops", scn_state["stops"] + 1), scn_state.__setitem__("playing", False)),
            Start=lambda: (scn_state.__setitem__("starts", scn_state["starts"] + 1), scn_state.__setitem__("playing", True)),
        )
        reg_events: list[str] = []
        advances: list[tuple[int, str]] = []
        objs_done: list[int] = []
        logs: list[str] = []
        moves: list[tuple] = []
        ns = {
            "MissionPlugin": "FO4SFMission.esm",
            "S9SturgesIntroScene": intro_scn,
            "S9SturgesIntroFallbackMsg": None,
            "S9IntroMaxSceneRestarts": 3,
            "S9IntroSceneCheckSeconds": 1.5,
            "S9IntroSceneMaxWaitChecks": 16,
            "talkBoxOpen": False,
            "completed": False,
            "benchMenuOpen": False,
            "workshopMenuOpen": False,
            "cleanBenchSawWorkshop": False,
            "cleanBenchVerifyPending": False,
            "talkSessionId": 1,
            "sturgesNearSec": 0.0,
            "s9IntroDialogueOpen": False,
            "s9IntroScenePending": False,
            "s9IntroSceneMenuOpened": False,
            "s9IntroSceneAttemptOpened": False,
            "s9IntroScenePhase1": False,
            "s9IntroScenePhase1At": 0.0,
            "s9IntroSceneChecks": 0,
            "s9IntroSceneRestarts": 3,
            "ownS9IntroStopPending": False,
            "ShouldUseMessageBox": lambda: False,
            "IsAnyMenuOrWorkshopOpen": lambda: False,
            "EffectiveStage": lambda: 220,
            "BindSturges": lambda: None,
            "ResolveSturges": lambda: SimpleNamespace(AllowPCDialogue=lambda *_: None, BlockActivation=lambda *_: None),
            "RegisterForRemoteEvent": lambda _o, ev: reg_events.append(str(ev)),
            "CancelTimer": lambda _tid: None,
            "StartTimer": lambda _s, _tid: None,
            "SetObjectiveCompleted": lambda o: objs_done.append(int(o)),
            "AdvanceTo": lambda st, by="other": advances.append((int(st), str(by))),
            "Utility": SimpleNamespace(GetCurrentRealTime=lambda: 200.0),
            "Game": SimpleNamespace(GetFormFromFile=lambda *_: None),
            "Trace": lambda msg: logs.append(str(msg)),
        }
        gvars = {
            "talkBoxOpen", "cleanBenchSawWorkshop", "cleanBenchVerifyPending",
            "workshopMenuOpen", "sturgesNearSec", "s9IntroDialogueOpen",
            "s9IntroScenePending", "s9IntroSceneMenuOpened", "s9IntroSceneAttemptOpened",
            "s9IntroScenePhase1", "s9IntroScenePhase1At", "s9IntroSceneChecks",
            "s9IntroSceneRestarts", "ownS9IntroStopPending",
        }
        _compile_papyrus(
            SANC01_PSC,
            [
                "RegisterS9IntroSceneEvents",
                "OnMenuOpenCloseEvent",
                "RestartOrFailS9IntroScene",
                "Scene.OnBegin",
                "Scene.OnEnd",
                "RunSturgesTalk",
                "PlaceRefInMuseumOffset",
            ],
            gvars,
            ns,
        )
        # Finding 4: RunSturgesTalk resets exhausted restarts (3 -> 0) and registers listeners
        ns["RunSturgesTalk"]()
        self.assertEqual(ns["s9IntroSceneRestarts"], 0)
        self.assertEqual(sorted(reg_events), ["OnBegin", "OnEnd", "OnPhaseBegin"])
        self.assertTrue(ns["s9IntroScenePending"])

        # Finding 2: Retry stops active scene -> Attempt 2 opens DialogueMenu BEFORE stale OnEnd fires
        ns["RestartOrFailS9IntroScene"]("no_dialoguemenu")
        self.assertTrue(ns["ownS9IntroStopPending"])
        ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
        self.assertTrue(ns["s9IntroSceneAttemptOpened"])
        self.assertTrue(ns["ownS9IntroStopPending"])

        ns["OnEnd"](intro_scn)  # Stale Attempt 1 OnEnd
        self.assertFalse(ns["ownS9IntroStopPending"])
        self.assertEqual(advances, [])

        # Finding 1: DialogueMenu closes BEFORE Attempt 2's Scene.OnEnd -> 220 still advances to 1000!
        ns["OnMenuOpenCloseEvent"]("DialogueMenu", False)
        self.assertFalse(ns["s9IntroDialogueOpen"])
        self.assertFalse(ns["s9IntroSceneMenuOpened"])
        self.assertTrue(ns["s9IntroSceneAttemptOpened"])
        ns["OnEnd"](intro_scn)
        self.assertEqual(advances, [(1000, "sturges_intro")])
        self.assertIn(220, objs_done)

        # Finding 4: PlaceRefInMuseumOffset dynamically uses anchor.GetPositionX/Y/Z (NOT hardcoded 8.228572)
        anchor = SimpleNamespace(GetPositionX=lambda: 100.0, GetPositionY=lambda: 200.0, GetPositionZ=lambda: 50.0)
        ref = SimpleNamespace(MoveTo=lambda a, dx, dy, dz, *_rest: moves.append((a, round(dx, 4), round(dy, 4), round(dz, 4))))
        ns["PlaceRefInMuseumOffset"](ref, anchor, 12.5, -3.5, 4.0)
        self.assertEqual(moves, [(anchor, -87.5, -203.5, -46.0)])

    def test_2h_stacked_integration_contracts(self) -> None:
        # S9 Lobby uses timer 7 (never colliding with S6 room scene timers 5/6) and S9 reset runs inside RegisterPrestonSceneEvents
        self.assertIn("elseif aiTimerID == 7", MIN00_PSC)
        self.assertIn("CheckS9LobbySceneOpen()", MIN00_PSC)
        self.assertNotIn("StartTimer(PrestonSceneCheckSeconds, 5)\n    Trace(\"s9", MIN00_PSC)
        # S7-S9 stacked onto S2-S6 preserves 4-member MinutemenGroup, forces StopAtFusionCorePowerArmor=false, and strips 0x3D094D on wave NPCs
        self.assertIn("StopAtFusionCorePowerArmor", S7S9_CS)
        self.assertIn("existingMm", S7S9_CS)
        prog_cs = (ROOT / "dotnet" / "Mission" / "Program.cs").read_text(encoding="utf-8")
        self.assertIn("var waveRaiderTpl = mod.Npcs.FirstOrDefault(n => n.FormKey.ID == FalloutActorLooks.ConcordRaiderNpcId)", prog_cs)
        self.assertLess(prog_cs.index("PopulateS2S6Missions("), prog_cs.index("PopulateS7S9("))


if __name__ == "__main__":
    unittest.main()
