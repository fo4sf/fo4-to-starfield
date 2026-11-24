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
            "0x00081E",  # FO4SF_PANoFallDamagePerk
            "player.AddItem(r5mm, 1200, False)",
            "s7 roof confirmed frame_no_core=true",
            "s7 street_drop z=",
        ):
            self.assertIn(token, MIN00_PSC)
        for token in ("CoreMinigunId = 0x0008A0", "CoreAmmo5mmId = 0x00089F", "vertibirdminigun.nif"):
            self.assertIn(token, S7S9_CS)


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
        self.assertIn("0x000BF4", SANC01_PSC)
        self.assertIn("001188B4", SANC01_PSC)
        self.assertIn("AdvanceTo(1000, \"sturges_intro\")", SANC01_PSC)
        self.assertIn("HasS9HardStop()", SANC01_PSC)
        self.assertIn("0x000BF5", MINREC_PSC)
        self.assertIn("0x000BF5", MQ103_PSC)
        self.assertIn("65, \"Clear Concord of Hostiles\"", PROGRAM_CS)

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
            (0xBF4, "MESG"),
            (0xBF5, "GLOB"),
        ):
            self.assertEqual(m_tbl[fid][0], rtype)
        self.assertEqual(catalog["FO4SFCoreValues.esm"][0x0008A4], ("MISC", "FO4_Caps"))
        self.assertEqual(catalog["FO4SFPowerArmor.esm"][0x00081E], ("PERK", "FO4SF_PANoFallDamagePerk"))


if __name__ == "__main__":
    unittest.main()
