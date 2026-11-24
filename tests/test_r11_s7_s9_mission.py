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
        self.assertEqual(dn092_wave.S7_ROOF_DOOR_POS, (-1990.58, -1724.19, 97.56))
        self.assertEqual(dn092_wave.S7_ROOF_FRAME_POS, (-1995.73, -1723.10, 97.54))
        self.assertEqual(dn092_wave.S7_ROOF_MINIGUN_POS, (-2004.72, -1715.40, 102.68))

        for token in (
            "S7RoofFrameRef",  # F12 persistent frame REFR (0xC0D)
            "0x000809",        # FO4SF_FusionCore from 2h/S6
            "0x000805",        # FO4SF_PowerArmorCoreQuest EnterFrame receiver
            "SyncS7RoofFrameGate(player)",
            "S7RoofFrameRef.BlockActivation(True, False)",
            "player.AddItem(r5mm, 1200, False)",
            "s7 roof confirmed frame_no_core=true frame_persistent=",
            "ReadActorHealth(player)",
            "hp_before=",
        ):
            self.assertIn(token, MIN00_PSC)
        # Finding 5: Min00 must NOT directly AddPerk(0x00081E); FO4SF_PowerArmorCoreQuest owns PA fall-damage perk on enter/exit.
        self.assertNotIn(".AddPerk(", MIN00_PSC)
        for token in (
            "CoreMinigunId = 0x0008A0",
            "CoreAmmo5mmId = 0x00089F",
            "vertibirdminigun.nif",
            "powerarmorfurniture.nif",
            "S7RoofFrameRefId = 0xC0D",
        ):
            self.assertIn(token, S7S9_CS)

    def test_s7_frame_activation_blocks_without_fusion_core_and_unlocks_with_core(self) -> None:
        from types import SimpleNamespace
        from tests.test_r11_cell_independent_quest import _compile_papyrus

        block_calls: list[tuple[bool, bool]] = []
        enter_calls: list[tuple[str, list]] = []
        logs: list[str] = []
        notifs: list[str] = []
        fc_count = [0]
        obj_done: set[int] = set()
        frame_ref = SimpleNamespace(BlockActivation=lambda blk, abs_off=False: block_calls.append((bool(blk), bool(abs_off))))
        pa_quest = SimpleNamespace(CallFunction=lambda fn, args: enter_calls.append((str(fn), list(args))))
        player = SimpleNamespace(GetItemCount=lambda _f: fc_count[0])
        ns = {
            "S7RoofFrameRef": frame_ref,
            "Game": SimpleNamespace(
                GetFormFromFile=lambda fid, plg: (
                    pa_quest if fid == 0x000805 else ("FC", fid, plg)
                )
            ),
            "IsTestModeEnabled": lambda: True,
            "IsObjectiveDisplayed": lambda idx: int(idx) == 95,
            "IsObjectiveCompleted": lambda idx: int(idx) in obj_done,
            "SetObjectiveCompleted": lambda idx: obj_done.add(int(idx)),
            "Debug": SimpleNamespace(Notification=lambda msg: notifs.append(str(msg))),
            "Trace": lambda msg: logs.append(str(msg)),
        }
        _compile_papyrus(MIN00_PSC, ["SyncS7RoofFrameGate", "OnS7RoofFrameActivated"], set(), ns)
        ns["SyncS7RoofFrameGate"](player)
        ns["OnS7RoofFrameActivated"](player)
        self.assertEqual(block_calls[-1], (True, False))
        self.assertEqual(enter_calls, [])
        self.assertNotIn(95, obj_done)
        self.assertTrue(any("refused reason=no_fusion_core" in lg for lg in logs))
        self.assertEqual(len(notifs), 1)

        fc_count[0] = 1
        ns["SyncS7RoofFrameGate"](player)
        ns["OnS7RoofFrameActivated"](player)
        self.assertEqual(block_calls[-1], (True, False))
        self.assertEqual(enter_calls, [("EnterFrame", [frame_ref, "s7_roof_frame"])])
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

        # Kill 8 (wave_kills == 8) fires wave_kills trigger, sets stage 77 (F8: NOT 79!), logs deathclaw_slot=empty
        trig8 = ctl.on_member_killed("WaveRaider03", far_player)
        self.assertEqual(trig8, "wave_kills")
        self.assertEqual(ctl.dn092_stage, 77)
        self.assertEqual(ctl.deathclaw_slot_status, "empty")
        self.assertTrue(any("deathclaw_slot=empty dn092_stage=77" in lg for lg in ctl.logs))

        # At stage 77 (< 79 window), WaveRaider01 still respawns using remaining pool until timer_300s advances stage to 79
        ctl.on_member_killed("WaveRaider01", far_player)
        self.assertTrue(ctl.members["WaveRaider01"].alive)
        self.assertEqual(ctl.respawn_pool, 1)

        # F8 empty-slot 300s timer completes DN092 77 -> 79; clearing remaining 3 clears the wave cleanly
        ctl.evaluate_deathclaw_triggers(far_player, dt=300.0)
        self.assertEqual(ctl.dn092_stage, 79)
        self.assertTrue(any("timer_300s_complete deathclaw_slot=empty dn092_stage=79" in lg for lg in ctl.logs))
        for alias in ("WaveRaider01", "WaveRaider02", "WaveRaider03"):
            ctl.on_member_killed(alias, far_player)
        self.assertTrue(ctl.is_wave_cleared)
        self.assertEqual(ctl.respawn_pool, 1)

    def test_respawn_pool_exhausts_at_zero_when_all_8_wave_kills_are_respawnables(self) -> None:
        ctl = dn092_wave.DN092WaveController(creature_slot_available=True)
        far_player = (-2000.0, -1700.0, 88.0)
        for i in range(8):
            alias = f"WaveRaider0{(i % 3) + 1}"
            ctl.on_member_killed(alias, far_player)
        self.assertEqual(ctl.respawn_pool, 0)
        self.assertEqual(ctl.deathclaw_trigger, "wave_kills")
        self.assertEqual(ctl.dn092_stage, 77)
        self.assertEqual(ctl.deathclaw_slot_status, "bound")
        self.assertTrue(ctl.deathclaw_alive)
        self.assertTrue(
            any("creature_slot=bound hp=615 dr=100 er=150 claw=60" in lg for lg in ctl.logs)
        )
        # Wave stays uncleared until Deathclaw dies (which advances DN092 77 -> 79) + all wave actors + bosses are dead
        for alias in ("WaveRaider01", "WaveRaider02", "WaveRaider03", "RoofLookout", "Gristle"):
            ctl.on_member_killed(alias, far_player)
        self.assertFalse(ctl.is_wave_cleared)
        ctl.on_deathclaw_killed()
        self.assertEqual(ctl.dn092_stage, 79)
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
        # Grate trigger at <= 17.0m of DN092ForceSpawnDeathclawTrigger 0009A144 sets stage 77 (F8: NOT 79!)
        ctl_grate = dn092_wave.DN092WaveController()
        gx, gy, gz = dn092_wave.GRATE_TRIGGER_POS
        self.assertIsNone(ctl_grate.evaluate_deathclaw_triggers((gx + 17.2, gy, gz), dt=5.0))
        self.assertEqual(ctl_grate.dn092_stage, 75)
        self.assertEqual(ctl_grate.evaluate_deathclaw_triggers((gx + 16.5, gy, gz), dt=1.0), "grate_proximity")
        self.assertEqual(ctl_grate.dn092_stage, 77)
        self.assertTrue(any("trigger=grate_proximity dn092_stage=77" in lg for lg in ctl_grate.logs))
        ctl_grate.evaluate_deathclaw_triggers((gx + 16.5, gy, gz), dt=299.0)
        self.assertEqual(ctl_grate.dn092_stage, 79)

        # 300s timer trigger when neither wave_kills nor grate_proximity fired sets 79 for empty slot
        ctl_timer = dn092_wave.DN092WaveController()
        far_player = (-1980.0, -1720.0, 88.0)
        self.assertIsNone(ctl_timer.evaluate_deathclaw_triggers(far_player, dt=299.0))
        self.assertEqual(ctl_timer.evaluate_deathclaw_triggers(far_player, dt=1.5), "timer_300s")
        self.assertEqual(ctl_timer.dn092_stage, 79)
        self.assertTrue(any("deathclaw_slot=empty dn092_stage=79" in lg for lg in ctl_timer.logs))

    def test_s8_papyrus_respawning_guard_prevents_premature_completion_and_holding_cell_is_used(self) -> None:
        from types import SimpleNamespace
        from tests.test_r11_cell_independent_quest import _compile_papyrus

        # Findings 2 & 3: 0xBF5 holding cell in S7S9_CS, zero `- MergeOffset` offsets, host anchor fallback, no Resurrect (F12)
        self.assertIn("S7S9HoldingCellId = 0xBF5", S7S9_CS)
        self.assertNotIn("- MergeOffset", S7S9_CS)
        self.assertIn("RelocateHoldingRefToCommonwealth(", MIN00_PSC)
        self.assertIn("ResolveCommonwealthHostAnchor()", MIN00_PSC)
        self.assertNotIn(".Resurrect(", MIN00_PSC)

        # F12: Kill #8 spawns a FRESH actor out of view via PlaceAtMe while s8RespawningCount guards premature clear!
        dead_flags = [True, True, True, True, True]
        disabled_calls: list[int] = []
        reg_deaths: list[object] = []

        def _make_actor(idx: int):
            return SimpleNamespace(
                idx=idx,
                IsDead=lambda i=idx: dead_flags[i],
                IsDisabled=lambda: False,
                DisableNoWait=lambda _f=False, i=idx: disabled_calls.append(i),
                GetLeveledActorBase=lambda: "WaveRaiderBase",
            )

        actors = [_make_actor(i) for i in range(5)]
        live_actors = list(actors)
        fresh_actor = SimpleNamespace(
            idx=0,
            IsDead=lambda: dead_flags[0],
            EnableNoWait=lambda _f=False: dead_flags.__setitem__(0, False),
            IsDisabled=lambda: False,
            DisableNoWait=lambda _f=False: None,
            GetLeveledActorBase=lambda: "WaveRaiderBase",
        )

        def _place_at_me(_base, *_rest):
            # Inside check_during_place (before fresh spawns), S8 MUST stay uncleared because s8RespawningCount == 1!
            ns["CheckS8WaveAndDeathclaw"](player, 0.0)
            self.assertFalse(ns["s8WaveCleared"])
            return fresh_actor

        spawners = [SimpleNamespace(
            GetDistance=lambda _p: 30.0,
            GetPositionX=lambda: -2090.0,
            GetPositionY=lambda: -1650.0,
            GetPositionZ=lambda: 88.5,
            PlaceAtMe=_place_at_me,
        )]
        logs: list[str] = []
        stages_set: list[int] = []
        objs_done: list[int] = []
        objs_disp: list[int] = []
        player = SimpleNamespace(GetDistance=lambda _r: 30.0)
        ns = {
            "EnableS6ToS9Full": True,
            "KeeperOnly": False,
            "s8WaveStarted": True,
            "s8WaveCleared": False,
            "s8WavePermDead": [False] * 5,
            "S8WaveActors": actors,
            "S8WaveActorBases": ["BoltBase", "BoltBase", "HeavyBase", "BoltBase", "GristleBase"],
            "s8LiveWaveActors": live_actors,
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
            "RegisterForRemoteEvent": lambda ref, ev: reg_deaths.append((ref, ev)),
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
            "s8WaveStarted", "s8WaveCleared", "s8WavePermDead", "s8LiveWaveActors",
            "s8RespawnPool", "s8RespawningCount", "s8WaveKills", "s8Dn092Stage",
            "s8SpawnerCursor", "s8ElapsedSec", "s8DeathclawSpawned", "s8DeathclawCleared",
            "s8DeathclawTrigger", "s8DeathclawRef", "s6FullStage",
        }
        _compile_papyrus(
            MIN00_PSC,
            ["PickS8WaveSpawner", "SpawnS8Deathclaw", "CheckS8WaveAndDeathclaw", "OnS8MemberKilled"],
            gvars,
            ns,
        )
        # Kill #8 calls PlaceAtMe -> check inside _place_at_me sees s8RespawningCount == 1 & refuses clear;
        # then fresh_actor replaces live_actors[0], disables old corpse, registers OnDeath, and stays alive.
        ns["OnS8MemberKilled"](0, actors[0], player)
        self.assertIs(ns["s8LiveWaveActors"][0], fresh_actor)
        self.assertEqual(disabled_calls, [0])
        self.assertIn((fresh_actor, "OnDeath"), reg_deaths)
        self.assertFalse(dead_flags[0])
        self.assertFalse(ns["s8WaveCleared"])
        self.assertEqual(ns["s8RespawningCount"], 0)
        # F8: Even with fresh_actor killed, while DN092 < 79 (still 77/75) S8 waits for Deathclaw / 300s timer;
        # once Deathclaw dies or 300s timer sets stage 79, CheckS8WaveAndDeathclaw clears cleanly to stage 80!
        dead_flags[0] = True
        ns["s8Dn092Stage"] = 77
        ns["OnS8MemberKilled"](0, fresh_actor, player)
        self.assertFalse(ns["s8WaveCleared"])
        ns["s8Dn092Stage"] = 79
        ns["CheckS8WaveAndDeathclaw"](player, 0.0)
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
        # F2: Undeployed patrol while player still indoors MUST NOT teleport
        self.assertFalse(
            dn092_wave.s9_failsafe_can_teleport(
                player_dist_to_preston=95.0,
                preston_dist_to_sanctuary=220.0,
                preston_3d_loaded=False,
                player_in_sanctuary=True,
                patrol_elapsed_sec=240.0,
                patrol_deployed=False,
            )
        )
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
        # F2: Any MinutemenGroup member loaded & <= 65m blocks teleport even when Preston is far away
        self.assertFalse(
            dn092_wave.s9_failsafe_can_teleport(
                player_dist_to_preston=95.0,
                preston_dist_to_sanctuary=220.0,
                preston_3d_loaded=True,
                player_in_sanctuary=True,
                patrol_elapsed_sec=240.0,
                group_members=[(True, 25.0), (False, 120.0)],
            )
        )
        # Player moved > 65m away from all loaded members -> failsafe teleport allowed
        self.assertTrue(
            dn092_wave.s9_failsafe_can_teleport(
                player_dist_to_preston=95.0,
                preston_dist_to_sanctuary=220.0,
                preston_3d_loaded=True,
                player_in_sanctuary=True,
                patrol_elapsed_sec=190.0,
                group_members=[(True, 80.0), (False, 12.0)],
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
        self.assertIn("deferred_until_exterior=true", MIN00_PSC)

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
            "FO4SF_MISSION rt=10.0 s7 roof confirmed frame_no_core=true frame_persistent=true minigun_enabled=true",
            "FO4SF_MISSION rt=15.0 s7 minigun grabbed count_minigun=1 count_5mm=1200 has_weap=true has_ammo=true",
            "FO4SF_MISSION rt=20.0 s7 street_drop z=88.50 no_fall_perk=true hp_before=120.0 hp_after=120.0 dmg=0.0",
            "FO4SF_MISSION rt=21.0 s8 wave2 started obj=65 dn092_stage=75 respawn_pool=8",
            "FO4SF_MISSION rt=40.0 s8 wave respawn idx=0 fresh=true pool_left=7 wave_kills=1 spawner=0xBEB",
            "FO4SF_MISSION rt=95.0 s8 deathclaw spawn trigger=wave_kills dn092_stage=77",
            "FO4SF_MISSION rt=95.0 s8 deathclaw deathclaw_slot=empty dn092_stage=77 waiting_timer=300s",
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
            (0xC06, "ACTI"),
            (0xC07, "REFR"),
            (0xC08, "REFR"),
            (0xC09, "REFR"),
            (0xC0A, "NPC_"),
            (0xC0B, "NPC_"),
            (0xC0C, "FURN"),
            (0xC0D, "REFR"),
            (0xC10, "NPC_"),
            (0xC11, "WEAP"),
            (0xC12, "WEAP"),
        ):
            self.assertEqual(m_tbl[fid][0], rtype, f"fid=0x{fid:X} -> {m_tbl.get(fid)}")
        self.assertEqual(catalog["FO4SFCoreValues.esm"][0x0008A4], ("MISC", "FO4_Caps"))
        self.assertEqual(catalog["FO4SFPowerArmor.esm"][0x00081E], ("PERK", "FO4SF_PANoFallDamagePerk"))

    def test_s9_lobby_scene_async_on_end_suppression_prevents_retry_burn(self) -> None:
        from types import SimpleNamespace
        from tests.test_r11_cell_independent_quest import _compile_papyrus

        scn_state = {"playing": True, "stops": 0, "starts": 0}
        stage_done = [80]
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
            "applied": 80,
            "GetStage": lambda: stage_done[0],
            "GetStageDone": lambda st: stage_done[0] >= int(st),
            "ShouldUseMessageBox": lambda: False,
            "EffectiveStage": lambda: stage_done[0],
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
            "prestonDialogueMenuOpen", "s8RespawningCount", "applied",
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

        # F13: Early escape BEFORE stage 90 must NOT pay reward or start patrol!
        ns["prestonDialogueMenuOpen"] = False
        self.assertTrue(ns["TryS9LobbyDialogueMenuClose"]())
        ns["HandleS9LobbySceneEnd"]()
        self.assertEqual(completed_calls, [])
        self.assertTrue(any("cancelled_early stage=80 reward=0" in lg for lg in logs))

        # Re-open -> reply advances stage to 90 -> DialogueMenu closes BEFORE Scene.OnEnd -> pays reward + patrol!
        ns["TryTriggerS9LobbyActivate"](player)
        self.assertTrue(ns["TryS9LobbyDialogueMenuOpen"](80))
        stage_done[0] = 90
        ns["applied"] = 90
        ns["prestonDialogueMenuOpen"] = False
        self.assertTrue(ns["TryS9LobbyDialogueMenuClose"]())
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

    def test_f2_f5_f6_f10_f13_review_fixes_in_scripts_and_mission_writer(self) -> None:
        from types import SimpleNamespace
        from tests.test_r11_cell_independent_quest import _compile_papyrus

        # F2: BeginS9MuseumExitAndPatrol defers while player is indoors, then deploys + chains outdoors
        deployed_pos: list[tuple] = []
        wps_chained = [0]
        preston_mock = SimpleNamespace(SetRestrained=lambda *_: None)
        mm_mocks = [SimpleNamespace(SetRestrained=lambda *_: None) for _ in range(4)]
        logs: list[str] = []
        player_in_int = [True]
        player = SimpleNamespace(IsInInterior=lambda: player_in_int[0])
        ns = {
            "EnableS6ToS9Full": True,
            "KeeperOnly": False,
            "s9LobbyCompleted": True,
            "s9PatrolStarted": False,
            "s9PatrolDeployed": False,
            "s9PatrolStartedAt": 0.0,
            "s9PatrolElapsed": 0.0,
            "s9DiamondCityMerged": True,
            "Preston": preston_mock,
            "prestonHeld": True,
            "MinutemenGroup": mm_mocks,
            "S9MuseumExitMarker": object(),
            "S9MuseumExitX": -2010.57,
            "S9MuseumExitY": -1697.94,
            "S9MuseumExitZ": 89.26,
            "IsCommonwealthExterior": lambda _p: True,
            "SyncKeeperPrestonMode": lambda *_: None,
            "MoveActorToExteriorSpot": lambda a, nm, *_r: deployed_pos.append((nm, player_in_int[0])),
            "RevealDiamondCityMapMarker": lambda _p: None,
            "PrepareAndChainS9PatrolWaypoints": lambda _p: (wps_chained.__setitem__(0, wps_chained[0] + 1), 6)[1],
            "Utility": SimpleNamespace(GetCurrentRealTime=lambda: 100.0),
            "Trace": lambda msg: logs.append(str(msg)),
        }
        gvars = {"s9PatrolStarted", "s9PatrolDeployed", "s9PatrolStartedAt", "s9PatrolElapsed", "prestonHeld"}
        _compile_papyrus(MIN00_PSC, ["BeginS9MuseumExitAndPatrol", "DeployS9PatrolExterior"], gvars, ns)

        self.assertTrue(ns["BeginS9MuseumExitAndPatrol"](player))
        self.assertFalse(ns["s9PatrolDeployed"])
        self.assertEqual(deployed_pos, [])
        self.assertEqual(wps_chained[0], 0)
        self.assertTrue(any("deferred_until_exterior=true" in lg for lg in logs))

        player_in_int[0] = False
        self.assertTrue(ns["DeployS9PatrolExterior"](player))
        self.assertTrue(ns["s9PatrolDeployed"])
        self.assertEqual(len(deployed_pos), 5)
        self.assertTrue(all(not indoors for _, indoors in deployed_pos))
        self.assertEqual(wps_chained[0], 1)

        # F5: Min01 Objective 1000 uses FO4 sheltered beds text with FO4SF_Min01BedPercent
        a4_cs = (ROOT / "dotnet" / "Mission" / "NextStoryMissionsA4.cs").read_text(encoding="utf-8")
        self.assertIn("Build sheltered beds for Sanctuary settlers (<Global=FO4SF_Min01BedPercent>%)", a4_cs)
        self.assertIn("UpdateCurrentInstanceGlobal(gPct)", SANC01_PSC)

        # F6 + F13: Sanctuary01 starts at 20 (NO Obj 10) under S9 hard stop & refuses direct_no_scene with ERROR
        adv: list[tuple[int, str]] = []
        objs_disp_sanc: list[int] = []
        sanc_logs: list[str] = []
        sanc_ns = {
            "instanceStarted": False,
            "HasS9HardStop": lambda: True,
            "IsWarfareMode": lambda: False,
            "IsRunning": lambda: True,
            "Start": lambda: None,
            "TryBindBench": lambda _p: None,
            "RegisterForRemoteEvent": lambda *_: None,
            "RegisterMenuGuards": lambda: None,
            "EnsureGuideMarker": lambda *_: None,
            "SetObjectiveDisplayed": lambda o, *_a: objs_disp_sanc.append(int(o)),
            "SetActive": lambda *_: None,
            "StartTimer": lambda *_: None,
            "HasFullMin01": lambda: True,
            "AdvanceTo": lambda st, by="": adv.append((int(st), str(by))),
            "Game": SimpleNamespace(GetPlayer=lambda: None),
            "Debug": SimpleNamespace(OpenUserLog=lambda *_: None),
            "LogName": "FO4SF_Mission",
            "IsAnyMenuOrWorkshopOpen": lambda: False,
            "completed": False,
            "talkBoxOpen": False,
            "talkSessionId": 1,
            "EffectiveStage": lambda: 220,
            "ShouldUseMessageBox": lambda: False,
            "S9SturgesIntroScene": None,
            "S9SturgesIntroFallbackMsg": None,
            "Trace": lambda msg: sanc_logs.append(str(msg)),
        }
        _compile_papyrus(SANC01_PSC, ["StartQuestInstance", "RunSturgesTalk"], {"instanceStarted", "talkBoxOpen"}, sanc_ns)
        sanc_ns["StartQuestInstance"]()
        self.assertEqual(adv, [(20, "Trigger")])
        self.assertEqual(objs_disp_sanc, [])
        sanc_ns["RunSturgesTalk"]()
        self.assertEqual(adv, [(20, "Trigger")])  # MUST NOT advance to 1000 via direct_no_scene!
        self.assertTrue(any("ERROR min01_sturges_intro missing S9SturgesIntroScene" in lg for lg in sanc_logs))

        # F10: PA records are loaded dynamically by cross_plugin_check (no hand-registered FO4SF_PANoFallDamagePerk)
        cpc_py = (ROOT / "src" / "fo4sf" / "core" / "cross_plugin_check.py").read_text(encoding="utf-8")
        self.assertNotIn("FO4SF_PANoFallDamagePerk", cpc_py)

    @unittest.skipUnless(
        shutil.which("dotnet") and os.environ.get("FO4SF_DOTNET_TESTS"),
        "set FO4SF_DOTNET_TESTS=1 with dotnet SDK on PATH to verify offline F3 Deathclaw C# builder",
    )
    def test_f3_deathclaw_builder_behind_creature_slots_offline_selftest(self) -> None:
        # F3: Verify NextStoryMissionsS7S9 constructs 0xC0E claw WEAP (60 dmg) & 0xC0F Deathclaw NPC_ (615/100/150)
        # from FO4 0002C969 behind --creature-slots and passes offline Mission selftest (default OFF + slots ON).
        for tok in (
            "S8DeathclawClawWeapId = 0xC0E",
            "S8DeathclawNpcId = 0xC0F",
            "DeathclawHealth = 615.0f",
            "DeathclawPhysicalDr = 100.0f",
            "DeathclawEnergyEr = 150.0f",
            "DeathclawClawDamage = 60.0f",
            "BuildCreatureNpcFromSlot",
            "FO4SF_S8_DeathclawNpc",
        ):
            self.assertIn(tok, S7S9_CS)
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ, DOTNET_ROLL_FORWARD="Major")
            r = subprocess.run(
                ["dotnet", "run", "-c", "Release", "--project", str(ROOT / "dotnet" / "Mission"), "--", "selftest", td],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("selftest pass", r.stdout)


if __name__ == "__main__":
    unittest.main()
