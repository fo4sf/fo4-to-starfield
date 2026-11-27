"""Round 15 Wave A Items 3, 4, 5 & Per-Game Start Data Seam verification tests.

Covers:
1. Per-game data seam (`src/fo4sf/core/game_start_config.json`): `fo4` defaults + documented `fo3`/`fnv` entries,
   verified Starfield.esm starter armor FormIDs, zero hardcoded Vault 111 / Commonwealth assumptions.
2. Item 3 — Leaks behind per-game flags in `FO4SF_NewGameQuest.psc`:
   - `MuteArrivalDiscoveryPopup`: skips `SetMarkerDiscovered()` while keeping marker attach intact.
   - `SilentStarterStrip` + `StarterStripItems` + Starfield.esm fallback: `UnequipItem(..., false, true)` +
     `RemoveItem(..., count, true)` before `RemoveAllItems(None, false, false)`.
   - `SinglePassLandingFade`: single `ForceFadeIn("story_landing")` in `FinishSurface` / `ReleaseStoryLandingFade`,
     no Timer 5 re-dims, `OnTimer(5)` guarded.
3. Item 4 — Lift flow (`sfse/FO4SFPipboyMenu/src/lift_menu.h` + `FO4SF_NewGameQuest.psc`):
   - `LiftMenuModel::ActivateOrConfirm` case 0 rides immediately even with 5 unspent S.P.E.C.I.A.L. points.
   - `PromptVaultExitLift` never bounces paused-lift `Ride` (`button == 0`) back to allocation.
   - `FinishSurface` triggers `ForceFadeIn("story_landing")` immediately, `CheckLanding` wait is 0.25 s, Timer 1 is 0.15 s.
4. Item 5 — Pod exit (`Stage 15` + `RunPodExitHook`):
   - `safe_spawn` clears pod/curb onto `Y = -7.314` main aisle facing `270.0` deg (`v111_door_1_closed`), once only.
   - `cryopod_anim` leaves clean hook seam without touching fade or exit lift.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
import unittest

from tests.test_exit_arrival import Reference, _PStr, translated_functions
from tests.test_newgame import PSC, read


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "src" / "fo4sf" / "core" / "game_start_config.json"
LIFT_MENU_H = ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "lift_menu.h"
STARFIELD_ESM = Path(r"D:\SteamLibrary\steamapps\common\Starfield\Data\Starfield.esm")


class GameStartConfigTests(unittest.TestCase):
    def test_game_start_config_schema_and_per_game_entries(self):
        self.assertTrue(CONFIG_PATH.is_file(), f"missing {CONFIG_PATH}")
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(cfg["schema_version"], 1)
        self.assertEqual(cfg["default_game"], "fo4")
        self.assertEqual(cfg["arrival_discovery_methods_supported"], ["during_fade", "add_to_map"])
        self.assertIn("safe_spawn", cfg["pod_exit_modes_supported"])
        self.assertIn("cryopod_anim", cfg["pod_exit_modes_supported"])

        games = cfg["games"]
        for game_key in ("fo4", "fo3", "fnv"):
            self.assertIn(game_key, games)
            entry = games[game_key]
            for req_key in (
                "silent_arrival_discovery",
                "arrival_discovery_method",
                "silent_starter_strip",
                "starter_strip_starfield_armor_ids",
                "pod_exit_mode",
                "pod_entry_step_m",
                "pod_safe_step_m",
                "pod_safe_heading_deg",
                "single_pass_landing_fade",
                "autosave_points",
            ):
                self.assertIn(req_key, entry, f"{game_key} missing {req_key}")

        fo4 = games["fo4"]
        self.assertTrue(fo4["silent_arrival_discovery"])
        self.assertEqual(fo4["arrival_discovery_method"], "add_to_map")
        self.assertNotIn("starter_strip_starfield_armor_ids", cfg)
        self.assertTrue(fo4["silent_starter_strip"])
        self.assertEqual(fo4["pod_exit_mode"], "cryopod_anim")
        self.assertAlmostEqual(fo4["pod_entry_step_m"], -2.5, places=3)
        self.assertAlmostEqual(fo4["pod_safe_step_m"], -3.2, places=3)
        self.assertAlmostEqual(fo4["pod_safe_heading_deg"], 270.0, places=3)
        self.assertTrue(fo4["single_pass_landing_fade"])
        self.assertEqual(fo4["autosave_points"], ["pod_exit", "pipboy_pickup"])
        self.assertNotIn("pod_safe_pos_override", fo4)
        self.assertIn("pod_anim", fo4)
        pod_anim = fo4["pod_anim"]
        self.assertEqual(pod_anim["plugin"], "FO4SFVaultPod.esm")
        self.assertEqual(pod_anim["ref_id"], "0x000801")
        self.assertEqual(pod_anim["static_ref_plugin"], "FO4Port.esm")
        self.assertEqual(pod_anim["static_ref_id"], "0x001617")
        self.assertEqual(pod_anim["open_event"], "Play01")
        self.assertAlmostEqual(pod_anim["open_seconds"], 5.3333, places=4)
        self.assertAlmostEqual(pod_anim["done_margin"], 0.25, places=3)
        self.assertAlmostEqual(pod_anim["open_timeout_s"], 8.0, places=3)
        self.assertAlmostEqual(pod_anim["seat_step_m"], -0.55, places=3)
        self.assertAlmostEqual(pod_anim["seat_heading_deg"], 180.0, places=3)
        self.assertAlmostEqual(pod_anim["step_out_to_m"], -2.5, places=3)
        self.assertAlmostEqual(pod_anim["push_tolerance_m"], 0.35, places=3)
        self.assertAlmostEqual(pod_anim["exit_timeout_s"], 20.0, places=3)
        self.assertFalse(pod_anim["creator_in_pod"])
        # No FO4 start may use safe_spawn directly (quick start wakes in the closed pod too).
        for g_key, g_val in games.items():
            if g_key.startswith("fo4"):
                self.assertNotEqual(g_val.get("pod_exit_mode"), "safe_spawn")

        ids = fo4["starter_strip_starfield_armor_ids"]
        for expected_id in ("0x001E2B17", "0x001E2B18", "0x001E2B19", "0x0001D1E7", "0x000D4893"):
            self.assertIn(expected_id, ids)

        # Ensure documented FO3/FNV placeholders do not inherit FO4 pod step/heading or autosave points
        self.assertEqual(games["fo3"]["pod_exit_mode"], "none")
        self.assertEqual(games["fnv"]["pod_exit_mode"], "none")
        self.assertEqual(games["fo3"]["arrival_discovery_method"], "during_fade")
        self.assertEqual(games["fnv"]["arrival_discovery_method"], "during_fade")
        self.assertAlmostEqual(games["fo3"]["pod_entry_step_m"], 0.0, places=3)
        self.assertAlmostEqual(games["fnv"]["pod_entry_step_m"], 0.0, places=3)
        self.assertEqual(games["fo3"]["autosave_points"], [])
        self.assertEqual(games["fnv"]["autosave_points"], [])


class Item3LeaksBehindFlagsTests(unittest.TestCase):
    def test_discovery_popup_muted_by_flag_and_still_attaches_marker(self):
        psc = read(PSC)
        compiled = compile(
            translated_functions(
                psc,
                ("RequestArrivalDiscovery", "DiscoverMarkerViaMapMarkers", "CheckLanding", "Near"),
                "arrivalWorld, fallbackPending, discoveryMarkerMoved, discoveryAttachPending, landingChecks",
            ),
            PSC,
            "exec",
        )
        world = object()
        other_world = object()
        player = Reference(world, (-1200.0, -2700.0, 100.0))
        marker = Reference(other_world, (-10.0, -20.0, 95.0))
        traces, stages, mm_calls = [], [], []
        mm_quest = SimpleNamespace(
            CastAs=lambda cls: SimpleNamespace(
                CallFunction=lambda fn, args: (
                    mm_calls.append((fn, list(args))),
                    args[0].AddToMap(True) if fn == "DiscoverSingleMarkerSilent" and args[1] == "add_to_map"
                    else args[0].SetMarkerDiscovered(),
                )
            )
        )
        ns = dict(
            _PStr=_PStr,
            Trace=traces.append,
            arrivalWorld=world,
            ArrivalX=0.0,
            ArrivalY=0.0,
            ArrivalZ=100.0,
            FallbackX=-10.0,
            FallbackY=-20.0,
            FallbackZ=95.0,
            MergeOffsetX=-1200.0,
            MergeOffsetY=-2700.0,
            FallDrop=3.0,
            ExitAnchorId=0x0A775B,
            ArrivalDiscoveryId=0x0A775B,
            CorePlugin="FO4TerrainCore.esm",
            MapMarkerQuestIds=[0x800],
            arrivedAt=0.0,
            fallbackPending=False,
            discoveryMarkerMoved=False,
            discoveryAttachPending=False,
            landingChecks=0,
            SilentArrivalDiscovery=True,
            ArrivalDiscoveryMethod="add_to_map",
            Game=SimpleNamespace(
                GetFormFromFile=lambda fid, plg: mm_quest if plg == "FO4SFMapMarkers.esm" else marker,
                IsFastTravelEnabled=lambda: True,
            ),
            Utility=SimpleNamespace(GetCurrentRealTime=lambda: 10.0),
            FailExit=lambda *_: None,
            AdvanceTo=stages.append,
        )
        exec(compiled, ns)
        ns["CheckLanding"](player)  # tick 1: attaches unmerged marker cleanly
        self.assertEqual(len(marker.moveto_calls), 1)
        self.assertEqual(marker.add_to_map_calls, [])
        self.assertEqual(marker.discovery_calls, 0)
        self.assertEqual(stages, [])
        ns["CheckLanding"](player)  # tick 2: never returns early -> silent discovery via AddToMap(True) + stage 200
        self.assertEqual(marker.add_to_map_calls, [True])
        self.assertEqual(marker.discovery_calls, 0)
        self.assertEqual(mm_calls, [("DiscoverSingleMarkerSilent", [marker, "add_to_map"])])
        self.assertEqual(stages, [200])
        self.assertTrue(
            any("arrival discovery silent=True method=add_to_map visible=True can_travel=True ref=" in t for t in traces),
            traces,
        )

        # during_fade method calls DiscoverSingleMarkerSilent with method="during_fade"
        traces.clear()
        mm_calls.clear()
        ns["ArrivalDiscoveryMethod"] = "during_fade"
        ns["CheckLanding"](player)
        self.assertEqual(marker.discovery_calls, 1)
        self.assertEqual(mm_calls, [("DiscoverSingleMarkerSilent", [marker, "during_fade"])])
        self.assertTrue(
            any("arrival discovery silent=True method=during_fade visible=True can_travel=True ref=" in t for t in traces),
            traces,
        )

        # Flag off restores DiscoverSingleMarker / SetMarkerDiscovered()
        traces.clear()
        mm_calls.clear()
        ns["SilentArrivalDiscovery"] = False
        ns["CheckLanding"](player)
        self.assertEqual(marker.discovery_calls, 2)
        self.assertEqual(mm_calls, [("DiscoverSingleMarker", [marker])])
        self.assertTrue(
            any("arrival discovery silent=False method=during_fade visible=True can_travel=True ref=" in t for t in traces),
            traces,
        )

    def test_silent_starter_strip_unequips_and_removes_silently_before_remove_all_items(self):
        psc = read(PSC)
        compiled = compile(
            translated_functions(psc, ("ResetInventory", "StripStarterItemsSilently"), ""),
            PSC,
            "exec",
        )

        class _Item:
            def __init__(self, name):
                self.name = name

        helmet = _Item("Spacesuit_Constellation_Helmet_01")
        suit = _Item("Spacesuit_Constellation_01")
        pack = _Item("Spacesuit_Constellation_Backpack_01")
        junk = _Item("MiscJunk")
        events = []

        class _Player:
            def __init__(self):
                self.items = {helmet: 1, suit: 1, pack: 1, junk: 2}
                self.equipped = {helmet, suit, pack}

            def GetItemCount(self, form):
                if form is None:
                    return sum(self.items.values())
                return self.items.get(form, 0)

            def IsEquipped(self, form):
                return form in self.equipped

            def UnequipItem(self, form, prevent=False, silent=False):
                events.append(("unequip", form.name, prevent, silent))
                self.equipped.discard(form)

            def RemoveItem(self, form, count=1, silent=False, dest=None):
                events.append(("remove", form.name, count, silent))
                self.items[form] = max(0, self.items.get(form, 0) - count)
                return count

            def RemoveAllItems(self, dest=None, keep_own=False, respect_cap=False):
                events.append(("remove_all", sorted(x.name for x in self.equipped), sum(self.items.values())))
                self.items.clear()
                self.equipped.clear()

            def AddItem(self, form, count=1, silent=False):
                events.append(("add", form, count, silent))

            def EquipItem(self, form, prevent=False, silent=False):
                events.append(("equip", form, prevent, silent))
                self.equipped.add(form)

        # 1) Test fallback Game.GetFormFromFile resolution when StarterStripItems is empty
        player = _Player()
        traces = []
        sf_map = {0x001E2B17: helmet, 0x001E2B18: suit, 0x001E2B19: pack}
        ns = dict(
            _PStr=_PStr,
            Trace=traces.append,
            SilentStarterStrip=True,
            StarterStripItems=[],
            VaultSuitId=0,
            VaultPlugin="FO4Port.esm",
            Game=SimpleNamespace(GetFormFromFile=lambda fid, plg: sf_map.get(fid) if plg == "Starfield.esm" else None),
        )
        exec(compiled, ns)
        ns["ResetInventory"](player)
        self.assertEqual(events[0], ("unequip", "Spacesuit_Constellation_Helmet_01", False, True))
        self.assertEqual(events[1], ("remove", "Spacesuit_Constellation_Helmet_01", 1, True))
        # By the time RemoveAllItems runs, all 3 starter pieces were silently unequipped & removed (only junk left!)
        remove_all_ev = next(e for e in events if e[0] == "remove_all")
        self.assertEqual(remove_all_ev, ("remove_all", [], 2))
        self.assertIn("inventory starter_strip silent=True stripped=3 left=0", traces)
        self.assertIn("inventory cleared removed=5 left=0", traces)

        # 2) Test explicit StarterStripItems property + SilentStarterStrip=False
        player2 = _Player()
        events.clear()
        traces.clear()
        ns["SilentStarterStrip"] = False
        ns["StarterStripItems"] = [helmet, suit, pack]
        ns["ResetInventory"](player2)
        self.assertEqual(events[0], ("remove_all", sorted([helmet.name, suit.name, pack.name]), 5))
        self.assertIn("inventory starter_strip silent=False stripped=0 left=0", traces)

    def test_single_pass_landing_fade_skips_timer5_and_guards_ontimer5(self):
        psc = read(PSC)
        ev_timer = re.search(r"Event OnTimer\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        wrapped = psc + f"\nFunction TimerEvent({ev_timer[1]})\n{ev_timer[2]}EndFunction\n"
        compiled = compile(
            translated_functions(
                wrapped,
                ("ForceFadeIn", "CompleteLandingFadeIn", "ReleaseStoryLandingFade", "FinishSurface", "ApplyStage", "AdvanceTo", "ClearVaultSaveLock", "TimerEvent", "BeginSurfaceCogWait3D", "PollSurfaceCogWait3D", "QueueSharedMapSetup", "SetLoadingBlackCover", "SqrtF", "HexDigit", "HexFormId"),
                "faded, surfaceFadeInDone, storyFadeTicks, arrivalWorld, surfaceSets, surfaceMovedAt, arrivedAt, applied, pendingStage, pendingStageBy, exitUsedFallback, h00SkipSetPos, vaultSavingRelocked",
            ),
            PSC,
            "exec",
        )
        world = object()
        core_cell = SimpleNamespace(GetFormID=lambda: 0x03000CF0)
        anchor = Reference(world, (-1210.0, -2720.0, 95.0), form_id=0x030A775B)
        player = Reference(world, (-1200.0, -2700.0, 100.0))
        player.cell = core_cell
        fades, timers, traces = [], [], []
        cur_stage = [30]
        now = [20.0]
        ns = dict(
            _PStr=_PStr,
            Trace=traces.append,
            SinglePassLandingFade=True,
            surfaceFadeInDone=False,
            faded=True,  # already faded in Vault 111
            storyFadeTicks=0,
            arrivalWorld=None,
            surfaceSets=0,
            surfaceMovedAt=1.0,
            arrivedAt=0.0,
            applied=30,
            pendingStage=-1,
            pendingStageBy="other",
            exitUsedFallback=False,
            h00SkipSetPos=False,
            vaultSavingRelocked=False,
            ArrivalX=0.0,
            ArrivalY=0.0,
            ArrivalZ=100.0,
            ArrivalHeading=0.0,
            MergeOffsetX=-1200.0,
            MergeOffsetY=-2700.0,
            FallDrop=3.0,
            SurfaceWait=10.0,
            SurfaceTries=3,
            StartLoadTimeout=15.0,
            CorePlugin="FO4TerrainCore.esm",
            ExitAnchorId=0x0A775B,
            LandingHandoff="single_quest",
            Game=SimpleNamespace(
                GetPlayer=lambda: player,
                GetFormFromFile=lambda *_: anchor,
                ShowFirstPersonGeometry=lambda *_: None,
                FadeOutGame=lambda *a: fades.append(a),
                SetInChargen=lambda *_: None,
                SetCharGenHUDMode=lambda *_: None,
            ),
            Utility=SimpleNamespace(GetCurrentRealTime=lambda: now[0], Wait=lambda *_: None),
            UnregisterStartLoadingHook=lambda: None,
            DisableHandScanner=lambda: None,
            CancelTimer=lambda *_: None,
            StartTimer=lambda s, tid: timers.append((s, tid)),
            GetStage=lambda: cur_stage[0],
            SetStage=lambda n: cur_stage.__setitem__(0, n),
            SetObjectiveDisplayed=lambda *_: None,
            SetObjectiveCompleted=lambda *_: None,
            SetActive=lambda *_: None,
            CompleteQuest=lambda: None,
            StartLandingQuests=lambda: None,
            RunPodExitHook=lambda *_: None,
            TriggerVaultPodRecoveryAutosave=lambda *_: None,
        )
        exec(compiled, ns)
        ns["FinishSurface"](player)
        now[0] += 3.1
        ns["PollSurfaceCogWait3D"](player)
        self.assertTrue(ns["surfaceFadeInDone"])
        self.assertEqual(len(fades), 1)
        self.assertIn("story_fade single_pass=true path=immediate loading_menu_open=False", traces)
        self.assertIn("ascent gap_closed=true fade_in_at_surface=true", traces)
        self.assertTrue(any(t.startswith("ascent gap_ms=") for t in traces), traces)

        # Stage 200 -> ReleaseStoryLandingFade() must NOT fade again or start Timer 5
        ns["AdvanceTo"](200)
        self.assertEqual(len(fades), 1)
        self.assertEqual(timers, [])
        self.assertFalse(any("already_faded" in t for t in traces), traces)

        # Even if Timer 5 fired, SinglePassLandingFade=True guards it
        ns["TimerEvent"](5)
        self.assertEqual(len(fades), 1)
        self.assertEqual(timers, [])


class Item4LiftFlowTests(unittest.TestCase):
    def test_g12c_lift_menu_header_refuses_ride_with_unspent_special_on_ascent_and_descent(self):
        hdr = LIFT_MENU_H.read_text(encoding="utf-8")
        cpp = (ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "main.cpp").read_text(encoding="utf-8")
        swf_py = (ROOT / "scripts" / "ui" / "make_probe_swf.py").read_text(encoding="utf-8")

        # Reset handles descending flag; fix7 immediate-ride text is gone
        self.assertIn("bool a_descending = false", hdr)
        self.assertNotIn("CHOOSE RIDE LIFT TO SURFACE NOW, OR EDIT S.P.E.C.I.A.L.", hdr)

        # case 0 refuses CommitAction::kRide when Remaining() > 0, opens S.P.E.C.I.A.L. editor, and Confirm refuses
        case0 = hdr[hdr.index("case 0:"):hdr.index("case 1:")]
        self.assertIn("if (Remaining() > 0)", case0)
        self.assertIn("EnterSpecialPage();", case0)
        self.assertIn("return false;", case0)
        self.assertLess(case0.index("return false;"), case0.index("a_out.action = CommitAction::kRide;"))

        special_blk = hdr[hdr.index("if (page_ == Page::kSpecial)"):hdr.index("switch (cursor_)")]
        self.assertIn("if (Remaining() > 0 && a_allowSpecialFinish)", special_blk)

        # Row labels show SPEND <N> POINTS FIRST while pool > 0 for both surface ascent and hilltop return
        self.assertIn("RIDE LIFT TO SURFACE", hdr)
        self.assertIn("RIDE LIFT DOWN TO VAULT 111", hdr)
        self.assertIn("(SPEND {} {} FIRST)", hdr)
        self.assertIn("STAY ON SURFACE", hdr)
        self.assertIn("> RIDE LIFT TO SURFACE (SPEND 5 POINTS FIRST)", swf_py)

        # Edit S.P.E.C.I.A.L. on row 1 remains intact
        case1 = hdr[hdr.index("case 1:"):hdr.index("case 2:")]
        self.assertIn("EnterSpecialPage();", case1)

        # main.cpp passes descending=(4.1..4.4), guards kRide with poolLeft > 0, and logs action + pool
        self.assertIn("const bool descending = (v >= 4.1f && v < 4.4f);", cpp)
        self.assertIn("g_liftModel.Reset(initVals, alreadyConfirmed, descending);", cpp)
        self.assertIn('REX::INFO("step=lift_confirm action={} pool={} confirmed={}', cpp)
        self.assertIn("a_payload.action == fo4sf::lift::CommitAction::kRide && poolLeft > 0", cpp)

    def test_g12c_harness_pool5_never_reaches_lift_menu_action_ride(self):
        psc = read(PSC)
        compiled = compile(
            translated_functions(
                psc,
                ("UnspentSpecialPool", "ShowPausedExitLiftMenu", "PromptVaultExitLift", "StartPairedLiftRide", "CheckReturnLift"),
                "asked, liftSpecConfirmed, liftPairActive, liftPairTransferred, liftPairTransferPending, interiorLiftDescending, surfaceCogRising, landingAwaitingFadeIn, returnAsked, returnVaultAsked, returnLiftArmed, returnSurfacePending, returnArmTicks, returnHasExteriorSample, returnLastExteriorX, returnLastExteriorY, arrivalWorld",
            ),
            PSC,
            "exec",
        )
        stats = [5, 5, 5, 5, 5, 5, 5]  # Total 35 -> pool = 5 unspent!
        stat_avs = [SimpleNamespace(idx=i) for i in range(7)]
        stat_globs = [SimpleNamespace(idx=i, GetValue=lambda idx=i: float(stats[idx]), SetValue=lambda v, idx=i: None) for i in range(7)]
        open_glob = SimpleNamespace(v=0.0, GetValue=lambda: open_glob.v, SetValue=lambda x: setattr(open_glob, "v", x))
        req_glob = SimpleNamespace(v=0.0, GetValue=lambda: req_glob.v, SetValue=lambda x: setattr(req_glob, "v", x))
        vault_cell = SimpleNamespace(GetFormID=lambda: 0x020011F3)
        core_cell = SimpleNamespace(GetFormID=lambda: 0x03000CF0)
        vault_world = object()
        surface_world = object()
        lift_base = object()
        cog_base = object()
        interior_lift = Reference(vault_world, (-77.742, -3.958, -1.751), form_id=0x02001618)
        interior_lift.interior = True
        interior_lift.cell = vault_cell
        interior_lift.GetBaseObject = lambda: lift_base
        interior_lift.PlayAnimation = lambda *_: True
        surface_cog = Reference(surface_world, (-2475.5824, -1403.9297, 33.253544), form_id=0xFF001234)
        surface_cog.cell = core_cell
        surface_cog.PlayAnimation = lambda *_: True

        player = Reference(vault_world, (-77.742, -3.958, -1.751))
        player.interior = True
        player.cell = vault_cell
        player.GetValue = lambda av: float(stats[av.idx])
        player.SetValue = lambda av, v: stats.__setitem__(av.idx, int(v))

        alloc_calls, traces = [], []
        cur_stage = [30]

        def fake_wait(_s):
            if open_glob.v in (4.0, 4.2):
                open_glob.v = 5.0
            elif open_glob.v == 5.0:
                open_glob.v = 6.0  # Harness tries to force Ride!

        def get_form(fid, plg):
            if plg == "FO4SFCoreValues.esm":
                if 0x810 <= fid <= 0x816:
                    return stat_avs[fid - 0x810]
                if 0x880 <= fid <= 0x886:
                    return stat_globs[fid - 0x880]
                if fid == 0x887:
                    return req_glob
            if plg == "FO4Port.esm":
                if fid == 0x1618:
                    return interior_lift
                if fid == 0x1619:
                    return lift_base
            if plg == "FO4TerrainCore.esm" and fid == 0x0A2D4B:
                return cog_base
            return None

        ns = dict(
            _PStr=_PStr,
            Trace=traces.append,
            StartCardOpenGlobal=open_glob,
            TestModeGlobal=None,
            ExitMessage=SimpleNamespace(Show=lambda: 2),
            ExitNeedAttrMsg=SimpleNamespace(Show=lambda: None),
            ExitFallbackMessage=SimpleNamespace(Show=lambda: 0),
            asked=False,
            liftSpecConfirmed=False,
            liftPairActive=False,
            liftPairTransferred=False,
            liftPairTransferPending=False,
            interiorLiftDescending=False,
            surfaceCogRising=False,
            landingAwaitingFadeIn=False,
            returnAsked=False,
            returnVaultAsked=False,
            returnLiftArmed=True,
            returnSurfacePending=False,
            returnArmTicks=0,
            returnHasExteriorSample=False,
            returnLastExteriorX=0.0,
            returnLastExteriorY=0.0,
            arrivalWorld=surface_world,
            leftArrivalPad=True,
            exitFailures=0,
            LiftId=0x1618,
            LiftBaseId=0x1619,
            VaultPlugin="FO4Port.esm",
            CorePlugin="FO4TerrainCore.esm",
            PlatformX=-77.742,
            PlatformY=-3.958,
            PlatformZ=-1.751,
            PlatformRadius=2.0,
            ArrivalX=-1275.5824,
            ArrivalY=1296.0703,
            ArrivalZ=33.253544,
            MergeOffsetX=-1200.0,
            MergeOffsetY=-2700.0,
            Game=SimpleNamespace(
                GetPlayer=lambda: player,
                GetFormFromFile=get_form,
                FindClosestReferenceOfType=lambda *_: surface_cog,
            ),
            Utility=SimpleNamespace(Wait=fake_wait, GetCurrentRealTime=lambda: 100.0),
            ReadH00SuspectsOnce=lambda: None,
            OpenLiftAttributeAllocation=lambda: alloc_calls.append("special"),
            GetStage=lambda: cur_stage[0],
            StandsInVault=lambda _p: True,
            Near=lambda _p, x, y, z, r: True,
            ResolveHostWorld=lambda: surface_world,
            EnsureSurfaceLiftCog=lambda _p: surface_cog,
            StartTimer=lambda *_: None,
            RegisterForAnimationEvent=lambda *_: None,
            UnregisterForAnimationEvent=lambda *_: None,
            RunSharedMapSetup=lambda: None,
            PrepareArrivalMarkerDuringRide=lambda: None,
        )
        exec(compiled, ns)

        # Pool == 5: Vault exit prompt refuses ride -> NEVER reaches 'lift menu action=ride'
        ns["PromptVaultExitLift"](player)
        self.assertFalse(any("lift menu action=ride" in t for t in traces), traces)
        self.assertIn("lift menu ride_refused pool=5", traces)
        self.assertEqual(alloc_calls, ["special"])
        self.assertFalse(ns["StartPairedLiftRide"](player, False))
        self.assertIn("lift_pair refused reason=special_points_remaining dir=up pool=5", traces)

        # Pool == 5: Hilltop return & vault return back up ALSO refuse ride!
        cur_stage[0] = 200
        player.interior = False
        player.world = surface_world
        player.cell = core_cell
        player.pos = (-2475.5824, -1403.9297, 33.253544)
        ns["CheckReturnLift"](player)
        self.assertFalse(any("lift menu action=ride" in t for t in traces), traces)
        self.assertFalse(ns["StartPairedLiftRide"](player, True))
        self.assertIn("lift_pair refused reason=special_points_remaining dir=down pool=5", traces)

        player.interior = True
        player.world = vault_world
        player.cell = vault_cell
        player.pos = (-77.742, -3.958, -1.751)
        ns["returnVaultAsked"] = False
        ns["CheckReturnLift"](player)
        self.assertFalse(any("lift menu action=ride" in t for t in traces), traces)

        # Spend all 5 points (40 total -> pool == 0): now Ride succeeds cleanly!
        stats[:] = [6, 6, 6, 6, 6, 5, 5]
        traces.clear()
        cur_stage[0] = 30
        ns["asked"] = False
        ns["PromptVaultExitLift"](player)
        self.assertIn("lift menu action=ride", traces)
        self.assertTrue(ns["liftPairActive"])

    def test_paused_lift_ride_never_bounces_and_timer1_closes_black_gap(self):
        psc = read(PSC)
        ev_timer = re.search(r"Event OnTimer\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        wrapped = psc + f"\nFunction TimerEvent({ev_timer[1]})\n{ev_timer[2]}EndFunction\n"
        compiled = compile(
            translated_functions(
                wrapped,
                ("ShowPausedExitLiftMenu", "PromptVaultExitLift", "TimerEvent"),
                "asked, liftSpecConfirmed, liftPairActive, liftPairTransferred, liftPairTransferPending, surfaceMovedAt, ticks",
            ),
            PSC,
            "exec",
        )
        open_glob = SimpleNamespace(v=0.0, GetValue=lambda: open_glob.v, SetValue=lambda x: setattr(open_glob, "v", x))
        req_glob = SimpleNamespace(v=0.0, GetValue=lambda: req_glob.v, SetValue=lambda x: setattr(req_glob, "v", x))
        player = Reference(None, (-77.742, -3.958, -1.751))
        ascents, need_attr, timers, traces = [], [], [], []
        cur_stage = [30]

        def fake_wait(_s):
            if open_glob.v == 4.0:
                open_glob.v = 5.0
            elif open_glob.v == 5.0:
                open_glob.v = 6.0  # Ride chosen immediately (even if reqGlob stayed 0!)

        ns = dict(
            _PStr=_PStr,
            Trace=traces.append,
            StartCardOpenGlobal=open_glob,
            TestModeGlobal=None,
            ExitMessage=SimpleNamespace(Show=lambda: 2),
            ExitNeedAttrMsg=SimpleNamespace(Show=lambda: need_attr.append(1)),
            ExitFallbackMessage=SimpleNamespace(Show=lambda: 0),
            asked=False,
            liftSpecConfirmed=False,
            liftPairActive=False,
            liftPairTransferred=False,
            liftPairTransferPending=False,
            surfaceMovedAt=0.0,
            exitFailures=0,
            LiftId=0x1618,
            ticks=0,
            applied=30,
            looksSetStage20=False,
            SinglePassLandingFade=True,
            Game=SimpleNamespace(
                GetPlayer=lambda: player,
                GetFormFromFile=lambda fid, plg: req_glob if (fid == 0x887 and plg == "FO4SFCoreValues.esm") else None,
            ),
            Utility=SimpleNamespace(Wait=fake_wait),
            ReadH00SuspectsOnce=lambda: None,
            EnsureLoadHookRegistered=lambda *_: None,
            StartPairedLiftRide=lambda p, desc=False: (ascents.append((p, desc)), True)[1],
            OpenLiftAttributeAllocation=lambda: None,
            StartTimer=lambda s, tid: timers.append((s, tid)),
            GetStage=lambda: cur_stage[0],
            CheckLanding=lambda *_: None,
        )
        exec(compiled, ns)
        ns["PromptVaultExitLift"](player)
        self.assertEqual(ascents, [(player, False)])
        self.assertEqual(need_attr, [])
        self.assertTrue(ns["liftSpecConfirmed"])

        # Timer 1 schedules 0.15 s at stage 40 (and during liftPairActive / surfaceMovedAt > 0.0)
        cur_stage[0] = 40
        ns["applied"] = 40
        ns["TimerEvent"](1)
        self.assertEqual(timers[-1], (0.15, 1))


class Item5PodExitTests(unittest.TestCase):
    def test_pod_exit_safe_spawn_clears_pod_facing_corridor_once_and_supports_cryopod_anim_hook(self):
        psc = read(PSC)
        compiled = compile(
            translated_functions(
                psc,
                ("PodEntryY", "PodSafeY", "RunPodExitHook", "NoteLooksStage20", "ApplyStage", "AdvanceTo", "StandsInVault"),
                "applied, looksSetStage20, podExitDone, pendingStage, pendingStageBy, exitUsedFallback",
            ),
            PSC,
            "exec",
        )
        vault_cell = SimpleNamespace(GetFormID=lambda: 0x020011F3)
        vault_anchor = Reference(None, (-60.0, 0.0, -1.0))
        vault_anchor.cell = vault_cell
        player = Reference(None, (9.143, -6.614, -0.729))
        player.interior = True
        player.cell = vault_cell
        angles, traces, autosaves, stages = [], [], [], []
        player.SetAngle = lambda rx, ry, rz: angles.append((rx, ry, rz))
        player.GetAngleZ = lambda: angles[-1][2] if angles else 0.0
        cur_stage = [10]

        def set_stage(n):
            cur_stage[0] = n
            stages.append(n)

        def make_ns(mode="safe_spawn", pod_y=-6.614, entry_step=-2.5):
            traces.clear()
            angles.clear()
            autosaves.clear()
            stages.clear()
            cur_stage[0] = 10
            player.pos = (9.143, pod_y, -0.729)
            return dict(
                _PStr=_PStr,
                Trace=traces.append,
                PodExitMode=mode,
                PodEntryStep=entry_step,
                PodSafeStep=-3.2,
                PodSafeHeading=270.0,
                PodX=9.143,
                PodY=pod_y,
                PodZ=-1.029,
                PodLift=0.3,
                PodHeading=0.0,
                VaultPlugin="FO4Port.esm",
                VaultAnchorId=0x805,
                applied=10,
                looksSetStage20=False,
                podExitDone=False,
                pendingStage=0,
                pendingStageBy="",
                exitUsedFallback=False,
                Game=SimpleNamespace(GetPlayer=lambda: player, GetFormFromFile=lambda *_: vault_anchor),
                GetStage=lambda: cur_stage[0],
                SetStage=set_stage,
                SetObjectiveDisplayed=lambda *_: None,
                SetObjectiveCompleted=lambda *_: None,
                SetActive=lambda *_: None,
                CompleteQuest=lambda: None,
                StartLandingQuests=lambda: None,
                ClearVaultSaveLock=lambda: None,
                ReleaseStoryLandingFade=lambda: None,
                TriggerVaultPodRecoveryAutosave=autosaves.append,
            )

        # 1) safe_spawn from legacy -2.5m PodY (-6.614) -> steps to Y=-7.314 corridor centerline facing 270 deg
        ns1 = make_ns(mode="safe_spawn", pod_y=-6.614)
        exec(compiled, ns1)
        ns1["NoteLooksStage20"]()
        self.assertEqual(cur_stage[0], 20)
        self.assertEqual(stages, [15, 20])
        self.assertEqual(autosaves, [20])
        self.assertAlmostEqual(player.pos[0], 9.143, places=3)
        self.assertAlmostEqual(player.pos[1], -7.314, places=3)
        self.assertAlmostEqual(player.pos[2], -0.729, places=3)
        self.assertEqual(angles, [(0.0, 0.0, 270.0)])
        self.assertIn("stage 15 by=safe_spawn", traces)
        self.assertTrue(
            any(
                t.lower().startswith("pod_exit mode=safe_spawn hook_stage=15 moved=true pos=9.143 -7.314 ")
                and t.endswith(" heading=270.0")
                for t in traces
            ),
            traces,
        )
        # Idempotent: walking away and re-entering ApplyStage(20) never snaps back
        player.pos = (-5.0, -7.314, 0.0)
        ns1["ApplyStage"](20, "Trigger")
        self.assertEqual(player.pos, (-5.0, -7.314, 0.0))

        # 2) cryopod_anim mode leaves player & fade untouched when pod plugin isn't installed and logs mode=cryopod_anim
        ns3 = make_ns(mode="cryopod_anim", pod_y=-6.614)
        exec(compiled, ns3)
        ns3["NoteLooksStage20"]()
        self.assertEqual(stages, [15, 20])
        self.assertEqual(player.pos, (9.143, -6.614, -0.729))
        self.assertEqual(angles, [])
        self.assertIn("stage 15 by=cryopod_anim", traces)
        self.assertTrue(
            any("pod_exit mode=cryopod_anim hook_stage=15 moved=false pos=9.143 -6.614 -0.729 " in t.lower() for t in traces),
            traces,
        )

    def test_pod_exit_hook_runs_stage_15_before_20_on_lookswait_nolooks_and_preworld(self):
        """G6 + I1: LooksWait, no-looks, and preworld routes invoke StartPodOpen / RunPodExitHook(15) before stage 20."""
        psc = read(PSC)
        timer_start = psc.index("Event OnTimer(int aiTimerID)")
        timer_src = psc[timer_start:psc.index("EndEvent", timer_start)]
        preworld_src = psc[psc.index("Function SpawnAtStoryStartPlace"):psc.index("int Function RunModeChoiceChain")]
        self.assertIn("StartPodOpen(", timer_src)
        self.assertIn("StartPodOpen(", preworld_src)
        self.assertNotIn("NoteLooksStage20()", timer_src)
        self.assertNotIn("NoteLooksStage20()", preworld_src)

        stage10_branch = timer_src[timer_src.index("elseif stage == 10"):timer_src.index("elseif stage == 20 || stage == 30")]
        self.assertIn("preworldLooksDone", stage10_branch)
        self.assertIn("LooksWait", stage10_branch)
        self.assertLess(stage10_branch.index("EnsureFadedInForChoice()"), stage10_branch.index("StartPodOpen(player)"))

        # Synthetic route verification for safe_spawn legacy hook (when PodExitMode="safe_spawn")
        vault_cell = SimpleNamespace(GetFormID=lambda: 0x020011F3)
        vault_anchor = Reference(None, (-60.0, 0.0, -1.0))
        vault_anchor.cell = vault_cell
        player = Reference(None, (9.143, -6.614, -0.729))
        player.interior = True
        player.cell = vault_cell
        traces, stages, autosaves = [], [], []
        angles = []
        player.SetAngle = lambda rx, ry, rz: angles.append((rx, ry, rz))
        player.GetAngleZ = lambda: angles[-1][2] if angles else 0.0
        cur_stage = [10]

        def set_stage(n):
            cur_stage[0] = n
            stages.append(n)

        compiled = compile(
            translated_functions(
                psc,
                ("PodEntryY", "PodSafeY", "RunPodExitHook", "ApplyStage", "AdvanceTo", "StandsInVault"),
                "applied, looksSetStage20, podExitDone, pendingStage, pendingStageBy, exitUsedFallback",
            ),
            PSC,
            "exec",
        )
        for route, looks_wait, cause in (
            ("LooksWait", 30.0, "fallback"),
            ("no-looks", 0.0, "Trigger"),
            ("preworld", 30.0, "Trigger"),
        ):
            with self.subTest(route=route):
                traces.clear()
                stages.clear()
                autosaves.clear()
                angles.clear()
                cur_stage[0] = 10
                player.pos = (9.143, -6.614, -0.729)
                ns = dict(
                    _PStr=_PStr,
                    Trace=traces.append,
                    PodExitMode="safe_spawn",
                    PodEntryStep=-2.5,
                    PodSafeStep=-3.2,
                    PodSafeHeading=270.0,
                    PodX=9.143,
                    PodY=-6.614,
                    PodZ=-1.029,
                    PodLift=0.3,
                    PodHeading=0.0,
                    VaultPlugin="FO4Port.esm",
                    VaultAnchorId=0x805,
                    applied=10,
                    looksSetStage20=False,
                    podExitDone=False,
                    pendingStage=0,
                    pendingStageBy="",
                    exitUsedFallback=False,
                    Game=SimpleNamespace(GetPlayer=lambda: player, GetFormFromFile=lambda *_: vault_anchor),
                    GetStage=lambda: cur_stage[0],
                    SetStage=set_stage,
                    SetObjectiveDisplayed=lambda *_: None,
                    SetObjectiveCompleted=lambda *_: None,
                    SetActive=lambda *_: None,
                    CompleteQuest=lambda: None,
                    StartLandingQuests=lambda: None,
                    ClearVaultSaveLock=lambda: None,
                    ReleaseStoryLandingFade=lambda: None,
                    TriggerVaultPodRecoveryAutosave=autosaves.append,
                )
                exec(compiled, ns)
                ns["RunPodExitHook"](player)
                ns["AdvanceTo"](20, cause)
                self.assertEqual(stages, [15, 20])
                self.assertLess(traces.index("stage 15 by=safe_spawn"), traces.index(f"stage 20 by={cause}"))
                self.assertTrue(any("pod_exit mode=safe_spawn hook_stage=15 moved=true " in t.lower() for t in traces), traces)
                self.assertAlmostEqual(player.pos[1], -7.314, places=3)
                self.assertEqual(angles, [(0.0, 0.0, 270.0)])

    def test_i1_cryopod_anim_all_six_paths_looks_done_wait_black_and_clearance(self):
        """I1: Full Papyrus state machine across all 6 exit paths, Looks.Done, creator_in_pod, reload, OnDying, and clearance gate."""
        from tests.test_newgame import LOOKS
        from scripts.newgame import make_anim_console as mac

        psc = read(PSC)
        looks_psc = read(LOOKS)
        ev_timer = re.search(r"Event OnTimer\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        ev_anim = re.search(r"Event OnAnimationEvent\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        ev_load = re.search(r"Event Actor\.OnPlayerLoadGame\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        ev_dying = re.search(r"Event Actor\.OnDying\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        wrapped = (
            psc
            + f"\nFunction TimerEvent({ev_timer[1]})\n{ev_timer[2]}EndFunction\n"
            + f"\nFunction AnimEvent({ev_anim[1]})\n{ev_anim[2]}EndFunction\n"
            + f"\nFunction LoadEvent({ev_load[1]})\n{ev_load[2]}EndFunction\n"
            + f"\nFunction DyingEvent({ev_dying[1]})\n{ev_dying[2]}EndFunction\n"
        )
        funcs = (
            "PodEntryX", "PodEntryY", "PodSafeX", "PodSafeY", "PodSeatPosX", "PodSeatPosY",
            "PodAnimReady", "ShouldSkipMenuDelay", "EnsureFadedInForChoice", "PrepareBeforeCreator",
            "NoteLooksDone", "HoldInPod", "ReleasePodHold", "CompleteLooksStage20AfterPodExit",
            "PodFallback", "StartPodOpen", "HandlePodAnimTimer", "RunPodExitHook",
            "ApplyStage", "AdvanceTo", "StandsInVault", "EnterVault", "FadeIn", "CheckPod",
            "TimerEvent", "AnimEvent", "LoadEvent", "DyingEvent",
        )
        vars_csv = (
            "applied, looksSetStage20, pendingStage, pendingStageBy, exitUsedFallback, "
            "faded, vaultMoves, podChecked, entered, ticks, startedAt, startRoomMoves, "
            "preworldLooksDone, preworldLooksHow, preworldLooksBy, "
            "vaultPodAutosaved, vaultSavingRelocked, vaultRecoveryTriggered, vaultPodAutosaveSkips, "
            "loadHookRegistered, dyingHookRegistered, "
            "pipboyPickedUp, pipboyGranted, pipboyPickupAutosaved, returnSurfacePending, returnVaultAsked, returnSurfaceWaitTicks, returnSurfaceTries"
        )
        compiled = compile(translated_functions(wrapped, funcs, vars_csv), PSC, "exec")
        looks_compiled = compile(translated_functions(looks_psc, ("Done",), ""), LOOKS, "exec")

        def run_pod_scenario(*, has_plugin=True, play_accepted=True, creator_in_pod=False):
            vault_cell = SimpleNamespace(GetFormID=lambda: 0x020011F3)
            vault_anchor = Reference(None, (-60.0, 0.0, -1.0))
            vault_anchor.cell = vault_cell
            static_pod = SimpleNamespace(disabled=False, IsDisabled=lambda: static_pod.disabled, DisableNoWait=lambda: setattr(static_pod, "disabled", True))
            pod_ref = SimpleNamespace(
                loaded=True,
                blocked=[],
                plays=[],
                Is3DLoaded=lambda: pod_ref.loaded,
                WaitFor3DLoad=lambda: None,
                BlockActivation=lambda b1, b2: pod_ref.blocked.append((b1, b2)),
                PlayAnimation=lambda ev: (pod_ref.plays.append(ev), play_accepted)[1],
            )
            player = Reference(None, (0.0, 0.0, 0.0))
            player.interior = True
            player.cell = vault_cell
            angles, traces, stages, timers, fades, layers, first_person, reg_anim, unreg_anim, av_restores = [], [], [], [], [], [], [], [], [], []
            player.SetAngle = lambda rx, ry, rz: angles.append((rx, ry, rz))
            player.GetAngleZ = lambda: angles[-1][2] if angles else 0.0
            player.RestoreValue = lambda av, v: av_restores.append(v)

            def fake_moveto(target, dx=0.0, dy=0.0, dz=0.0, *_):
                player.pos = (target.pos[0] + dx, target.pos[1] + dy, target.pos[2] + dz)

            def fake_setpos(x, y, z):
                player.pos = (x, y, z)

            player.MoveTo = fake_moveto
            player.SetPosition = fake_setpos
            cur_time = [10.0]
            cur_stage = [0]

            class _Layer:
                def __init__(self):
                    self.disabled_args = None
                    self.deleted = False
                    layers.append(self)

                def DisablePlayerControls(self, *args):
                    self.disabled_args = args

                def Delete(self):
                    self.deleted = True

            def set_stage(n):
                cur_stage[0] = n
                stages.append(n)

            def get_form(fid, plg):
                if plg == "FO4SFVaultPod.esm" and fid in (0x000800, 0x000801):
                    return pod_ref if has_plugin else None
                if plg == "FO4Port.esm" and fid == 0x001617:
                    return static_pod
                if plg == "FO4Port.esm" and fid == 0x000805:
                    return vault_anchor
                if plg == "Starfield.esm" and fid == 0x0002D4:
                    return object()
                return None

            ns = dict(
                _PStr=_PStr,
                Trace=traces.append,
                LogName="fo4sf_newgame",
                Math=SimpleNamespace(sin=lambda deg: __import__("math").sin(__import__("math").radians(deg)),
                                     cos=lambda deg: __import__("math").cos(__import__("math").radians(deg)),
                                     sqrt=lambda x: __import__("math").sqrt(x)),
                InputEnableLayer=SimpleNamespace(Create=lambda: _Layer()),
                Utility=SimpleNamespace(GetCurrentRealTime=lambda: cur_time[0], Wait=lambda dt: cur_time.__setitem__(0, cur_time[0] + dt)),
                Game=SimpleNamespace(
                    GetPlayer=lambda: player,
                    GetFormFromFile=get_form,
                    ForceFirstPerson=lambda: first_person.append(1),
                    ShowFirstPersonGeometry=lambda *_: None,
                    FadeOutGame=lambda *args: fades.append(args),
                    SetInChargen=lambda *_: None,
                    SetCharGenHUDMode=lambda *_: None,
                ),
                Debug=SimpleNamespace(OpenUserLog=lambda *_: True, Notification=lambda *_: None, CenterOnCell=lambda *_: None),
                GetStage=lambda: cur_stage[0],
                SetStage=set_stage,
                SetObjectiveDisplayed=lambda *_: None,
                SetObjectiveCompleted=lambda *_: None,
                SetActive=lambda *_: None,
                CompleteQuest=lambda: None,
                StartLandingQuests=lambda: None,
                ClearVaultSaveLock=lambda: None,
                RelockVaultSaving=lambda *_: None,
                ReleaseStoryLandingFade=lambda: None,
                TriggerVaultPodRecoveryAutosave=lambda *_: None,
                EnsureLoadHookRegistered=lambda *_: None,
                EnsurePipboyWristEquipped=lambda *_: None,
                RecoverPairedLiftOnLoad=lambda *_: None,
                SyncPipboyOwnedWornState=lambda *_: None,
                DisableHandScanner=lambda: None,
                UnregisterStartLoadingHook=lambda: None,
                CancelTimer=lambda *_: None,
                StartTimer=lambda s, tid: timers.append((s, tid)),
                RegisterForAnimationEvent=lambda ref, ev: reg_anim.append((ref, ev)),
                UnregisterForAnimationEvent=lambda ref, ev: unreg_anim.append((ref, ev)),
                GameModeGlobal=SimpleNamespace(GetValue=lambda: 1.0),
                LooksWait=30.0,
                PodExitMode="cryopod_anim",
                PodEntryStep=-2.5,
                PodSafeStep=-3.2,
                PodSafeHeading=270.0,
                PodOriginX=9.142858,
                PodOriginY=-4.114286,
                PodOriginZ=-1.0285715,
                PodSeatX=9.142858,
                PodSeatY=-4.664286,
                PodSeatZ=-1.0285715,
                PodX=9.142858,
                PodY=-6.614286,
                PodZ=-1.0285715,
                PodLift=0.3,
                PodDrop=0.5,
                PodRadius=1.0,
                PodHeading=0.0,
                AnchorX=-60.0,
                AnchorY=0.0,
                AnchorZ=-1.0,
                VaultPlugin="FO4Port.esm",
                VaultAnchorId=0x000805,
                AnchorTemporary=False,
                PodAnimPlugin="FO4SFVaultPod.esm",
                PodAnimRefId=0x000801,
                PodStaticRefPlugin="FO4Port.esm",
                PodStaticRefId=0x001617,
                PodOpenEvent="Play01",
                PodOpenSeconds=5.3333,
                PodDoneMargin=0.25,
                PodOpenTimeoutS=8.0,
                PodSeatStepM=-0.55,
                PodSeatHeadingDeg=180.0,
                PodStepOutToM=-2.5,
                PodPushToleranceM=0.35,
                PodExitTimeoutS=20.0,
                PodCreatorInPod=creator_in_pod,
                applied=0,
                looksSetStage20=False,
                pendingStage=-1,
                pendingStageBy="",
                exitUsedFallback=False,
                faded=False,
                vaultMoves=0,
                podChecked=False,
                entered=False,
                ticks=0,
                startedAt=0.0,
                startRoomMoves=0,
                preworldLooksDone=False,
                preworldLooksHow="",
                preworldLooksBy="",
                vaultPodAutosaved=False,
                vaultSavingRelocked=False,
                vaultRecoveryTriggered=False,
                vaultPodAutosaveSkips=0,
                loadHookRegistered=False,
                dyingHookRegistered=False,
                pipboyPickedUp=False,
                pipboyGranted=False,
                pipboyPickupAutosaved=False,
                returnSurfacePending=False,
                returnVaultAsked=False,
                returnSurfaceWaitTicks=0,
                returnSurfaceTries=0,
            )
            exec(compiled, ns)
            return SimpleNamespace(
                ns=ns, player=player, pod_ref=pod_ref, static_pod=static_pod,
                angles=angles, traces=traces, stages=stages, timers=timers,
                fades=fades, layers=layers, first_person=first_person,
                reg_anim=reg_anim, unreg_anim=unreg_anim, cur_time=cur_time, cur_stage=cur_stage,
            )

        # Path 1: Normal Done + walk-out >= 1.0 m (also checks FO4SF_NewGameLooks.Done & Wait-under-black + creator_in_pod=False)
        s1 = run_pod_scenario(has_plugin=True, creator_in_pod=False)
        self.assertTrue(s1.ns["PodAnimReady"]())
        self.assertTrue(s1.ns["ShouldSkipMenuDelay"]())
        self.assertTrue(s1.ns["EnterVault"](s1.player))
        self.assertAlmostEqual(s1.player.pos[1], -4.664286, places=4)
        self.assertEqual(s1.angles[-1], (0.0, 0.0, 180.0))
        self.assertTrue(any("mode=pod_seat" in t for t in s1.traces), s1.traces)
        # Menu stays enabled (index 8 == False), move/fight/cam/look/sneak/activate/VATS/favorites disabled
        self.assertEqual(s1.layers[0].disabled_args, (True, True, True, True, True, False, True, False, True, True, True))
        self.assertEqual(s1.pod_ref.blocked, [(True, True)])
        self.assertEqual(s1.first_person, [1])
        # creator_in_pod=False moves to entry point under black then returns to seat before StartPodOpen
        s1.ns["PrepareBeforeCreator"]()
        self.assertAlmostEqual(s1.player.pos[1], -6.614286, places=4)
        looks_ns = dict(GetStage=lambda: s1.cur_stage[0], SetStage=lambda st: s1.cur_stage.__setitem__(0, st),
                        TracePosition=lambda *_: None, Trace=s1.traces.append,
                        self=SimpleNamespace(NoteLooksDone=s1.ns["NoteLooksDone"]))
        exec(looks_compiled, looks_ns)
        looks_ns["Done"]("creator closed")
        self.assertAlmostEqual(s1.player.pos[1], -4.664286, places=4)
        self.assertFalse(s1.ns["podExitDone"])
        self.assertEqual(s1.stages, [15])
        self.assertIn("stage 15 by=cryopod_anim", s1.traces)
        self.assertTrue(s1.static_pod.disabled)
        self.assertEqual(s1.pod_ref.plays, ["Play01"])
        self.assertIn("pod_open play=Play01 accepted=True", s1.traces)
        # Early Done is ignored; Done at >= open_seconds - margin opens door & releases hold
        s1.cur_time[0] += 1.0
        s1.ns["AnimEvent"](s1.pod_ref, "Done")
        self.assertFalse(s1.ns["podDoorDone"])
        s1.cur_time[0] += 4.2
        s1.ns["AnimEvent"](s1.pod_ref, "Done")
        self.assertTrue(s1.ns["podDoorDone"])
        s1.ns["TimerEvent"](8)
        self.assertTrue(s1.layers[0].deleted)
        self.assertIn("pod_step_out by=walk", s1.traces)
        self.assertFalse(s1.ns["podExitDone"])
        # Walk >= 1.0 m -> pod_exit moved=true by=walk -> Stage 20; NO SetPosition snap after fade-in
        s1.player.pos = (9.142858, -6.0, -0.7285715)
        s1.ns["TimerEvent"](8)
        self.assertTrue(s1.ns["podExitDone"])
        self.assertEqual(s1.stages, [15, 20])
        self.assertTrue(any("pod_exit mode=cryopod_anim hook_stage=15 moved=true " in t and t.endswith(" by=walk") for t in s1.traces), s1.traces)
        # OnPlayerLoadGame re-plays open pose when podExitDone
        s1.ns["LoadEvent"](s1.player)
        self.assertIn("pod_state on_load=open", s1.traces)
        self.assertEqual(s1.pod_ref.plays, ["Play01", "Play01"])

        # Path 2: open_timeout
        s2 = run_pod_scenario(has_plugin=True)
        s2.ns["EnterVault"](s2.player)
        s2.ns["StartPodOpen"](s2.player)
        s2.cur_time[0] += 8.5
        s2.ns["TimerEvent"](8)
        self.assertTrue(s2.ns["podExitDone"])
        self.assertEqual(s2.stages, [15, 20])
        self.assertIn("pod_exit mode=safe_spawn fallback_from=cryopod_anim reason=open_timeout", s2.traces)

        # Path 3: exit_timeout (door opens, player stays in pod >= 20s)
        s3 = run_pod_scenario(has_plugin=True)
        s3.ns["EnterVault"](s3.player)
        s3.ns["StartPodOpen"](s3.player)
        s3.cur_time[0] += 5.33
        s3.ns["AnimEvent"](s3.pod_ref, "Done")
        s3.ns["TimerEvent"](8)
        s3.cur_time[0] += 20.5
        s3.ns["TimerEvent"](8)
        self.assertTrue(s3.ns["podExitDone"])
        self.assertEqual(s3.stages, [15, 20])
        self.assertTrue(any("pod_exit mode=cryopod_anim hook_stage=15 moved=false " in t and t.endswith(" by=timeout") for t in s3.traces), s3.traces)

        # Path 4: play_refused
        s4 = run_pod_scenario(has_plugin=True, play_accepted=False)
        s4.ns["EnterVault"](s4.player)
        s4.ns["StartPodOpen"](s4.player)
        self.assertTrue(s4.ns["podExitDone"])
        self.assertEqual(s4.stages, [15, 20])
        self.assertIn("pod_exit mode=safe_spawn fallback_from=cryopod_anim reason=play_refused", s4.traces)

        # Path 5: pushed (pre-choice CheckPod stays stage <= 10 at entry point -> post-choice StartPodOpen finishes 20)
        s5 = run_pod_scenario(has_plugin=True)
        s5.cur_stage[0] = 10
        s5.ns["EnterVault"](s5.player)
        s5.player.pos = (9.142858, -5.5, -0.7285715)  # > 0.35m from seat
        s5.ns["CheckPod"](s5.player)
        self.assertTrue(s5.ns["podFellBack"])
        self.assertEqual(s5.cur_stage[0], 10)
        self.assertIn("pod_exit mode=safe_spawn fallback_from=cryopod_anim reason=pushed", s5.traces)
        self.assertAlmostEqual(s5.player.pos[1], -6.614286, places=4)
        s5.ns["StartPodOpen"](s5.player)
        self.assertEqual(s5.stages, [15, 20])
        self.assertTrue(s5.ns["podExitDone"])

        # Path 6: no_pod_plugin (PodAnimReady == False -> fallback)
        s6 = run_pod_scenario(has_plugin=False)
        self.assertFalse(s6.ns["PodAnimReady"]())
        s6.ns["StartPodOpen"](s6.player)
        self.assertTrue(s6.ns["podExitDone"])
        self.assertIn("pod_exit mode=safe_spawn fallback_from=cryopod_anim reason=no_pod_plugin", s6.traces)

        # OnDying under pod hold releases input layer
        s7 = run_pod_scenario(has_plugin=True)
        s7.ns["EnterVault"](s7.player)
        self.assertFalse(s7.layers[0].deleted)
        s7.ns["DyingEvent"](s7.player, None)
        self.assertTrue(s7.layers[0].deleted)

        # Offline clearance gate refuses intersecting body unless explicitly dropped
        ident = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        with self.assertRaises(ValueError):
            mac.evaluate_pod_clearance(
                [{"bone": "door", "centre_m": [0.0, -0.55, 1.5], "half_m": [0.7, 0.45, 1.2], "rotation_row_major": ident, "moving": True, "dropped": False}],
                seat_step_m=-0.55,
            )
        ok_clear = mac.evaluate_pod_clearance(
            [
                {"bone": "door", "centre_m": [0.0, -0.55, 1.5], "half_m": [0.7, 0.45, 1.2], "rotation_row_major": ident, "moving": True, "dropped": True},
                {"bone": "arm3", "centre_m": [0.0, -1.08, 2.1], "half_m": [0.62, 0.12, 0.72], "rotation_row_major": ident, "moving": True, "dropped": False},
            ],
            seat_step_m=-0.55,
        )
        self.assertGreater(ok_clear["min_clearance_m"], 0.05)


class G5G12PipboyEquipAndAutosaveTests(unittest.TestCase):
    def test_pickup_forces_first_person_sheathes_autosaves_and_reload_reequips_after_unequip(self):
        psc = read(PSC)
        compiled = compile(
            translated_functions(
                psc,
                (
                    "HandlePipboyPickup",
                    "EnsurePipboyWristEquipped",
                    "LogPipboyWrist3DNodes",
                    "SyncPipboyOwnedWornState",
                    "TriggerVaultPickupAutosave",
                    "Actor.OnPlayerLoadGame",
                    "OnTimer",
                    "StandsInVault",
                ),
                "pipboyPickedUp, pipboyGranted, pipboyPickupAutosaved, vaultPodAutosaved, vaultRecoveryTriggered, vaultSavingRelocked, "
                "h00SuspectsRead, rideActive, rideDone, rideTransferred, rideFadeStarted, ridingLift, ridingCell, "
                "surfaceMovedAt, surfaceMoves, surfaceSets, surfaceFadeInDone, exitUsedFallback, asked, "
                "returnSurfacePending, returnVaultAsked, returnSurfaceWaitTicks, returnSurfaceTries",
            ),
            PSC,
            "exec",
        )
        vault_cell = SimpleNamespace(GetFormID=lambda: 0x020011F3)
        vault_anchor = Reference(None, (-60.0, 0.0, -1.0))
        vault_anchor.cell = vault_cell
        wrist = object()
        corpse = SimpleNamespace(disabled=False, DisableNoWait=lambda *_: setattr(corpse, "disabled", True))
        examine_idle = object()

        state = {
            "count": 0,
            "equipped": False,
            "equips": [],
            "sheathed": 0,
            "first_person": 0,
            "played_idles": [],
            "autosaves": 0,
            "chargens": [],
            "timers": [],
            "traces": [],
            "glob": 0.0,
            "stage": 20,
        }

        class _Player:
            def __init__(self):
                self.interior = True
                self.cell = vault_cell

            def IsDead(self): return False
            def Is3DLoaded(self): return True
            def IsInInterior(self): return self.interior
            def GetParentCell(self): return self.cell
            def GetItemCount(self, item): return state["count"] if item is wrist else 0
            def AddItem(self, item, n, silent=False):
                if item is wrist:
                    state["count"] += int(n)
            def IsEquipped(self, item): return bool(item is wrist and state["equipped"])
            def EquipItem(self, item, prevent_removal=False, silent=False):
                if item is wrist:
                    state["equips"].append((prevent_removal, silent))
                    state["equipped"] = True
            def SheatheWeapon(self): state["sheathed"] += 1
            def PlayIdle(self, idle):
                state["played_idles"].append(idle)
                return True
            def HasNode(self, node_name):
                return node_name in ("FO4WristHousingM_1", "PipboyScreen")

        player = _Player()
        glob = SimpleNamespace(
            GetValue=lambda: state["glob"],
            SetValue=lambda v: state.__setitem__("glob", float(v)),
        )
        ns = dict(
            _PStr=_PStr,
            Trace=state["traces"].append,
            LogName="fo4sf_newgame",
            pipboyPickedUp=False,
            pipboyGranted=False,
            pipboyPickupAutosaved=False,
            vaultPodAutosaved=True,
            vaultRecoveryTriggered=False,
            vaultSavingRelocked=True,
            h00SuspectsRead=False,
            rideActive=False,
            rideDone=False,
            rideTransferred=False,
            rideFadeStarted=False,
            ridingLift=None,
            ridingCell=None,
            surfaceMovedAt=0.0,
            surfaceMoves=0,
            surfaceSets=0,
            surfaceFadeInDone=False,
            exitUsedFallback=False,
            asked=False,
            returnSurfacePending=False,
            returnVaultAsked=False,
            returnSurfaceWaitTicks=0,
            returnSurfaceTries=0,
            PipboyWristArmor=wrist,
            PipboyWristSlotLabel="55",
            PipboyAcquiredGlobal=glob,
            PipboyCorpseRef=corpse,
            PortPipboyStaticId=0,
            VaultPlugin="FO4Port.esm",
            VaultAnchorId=0x805,
            GameModeGlobal=SimpleNamespace(GetValue=lambda: 1.0),
            Game=SimpleNamespace(
                GetPlayer=lambda: player,
                GetFormFromFile=lambda fid, plg: examine_idle if (fid == 0x000C154F and plg == "Starfield.esm") else vault_anchor,
                ForceFirstPerson=lambda: state.__setitem__("first_person", state["first_person"] + 1),
                SetInChargen=lambda a, b, c: state["chargens"].append((a, b, c)),
                RequestAutoSave=lambda: state.__setitem__("autosaves", state["autosaves"] + 1),
            ),
            Debug=SimpleNamespace(OpenUserLog=lambda *_: True, TraceUser=lambda *_: True, Notification=lambda *_: None),
            GetStage=lambda: state["stage"],
            UnregisterForRemoteEvent=lambda *_: None,
            EnsureLoadHookRegistered=lambda *_: None,
            RelockVaultSaving=lambda *_: None,
            RecoverPairedLiftOnLoad=lambda *_: None,
            StartTimer=lambda s, tid: state["timers"].append((s, tid)),
        )
        exec(compiled, ns)

        # 1. Pickup equips wrist, logs slot=55 (data), queues 1s timer 8 for 3D node log, forces 1st person & sheathes, plays idle, triggers pickup autosave
        ns["HandlePipboyPickup"](player)
        self.assertTrue(ns["pipboyGranted"])
        self.assertTrue(ns["pipboyPickedUp"])
        self.assertEqual(state["first_person"], 1)
        self.assertEqual(state["sheathed"], 1)
        self.assertEqual(state["played_idles"], [examine_idle])
        self.assertEqual(state["autosaves"], 1)
        self.assertFalse(ns["vaultSavingRelocked"])
        self.assertIn((False, False, False), state["chargens"])
        self.assertIn((1.5, 6), state["timers"])
        self.assertIn((1.0, 9), state["timers"])
        self.assertIn("vault_death_recovery=autosave stage=20 after=pipboy_pickup", state["traces"])
        self.assertTrue(any("slot=55" in t for t in state["traces"]), state["traces"])
        self.assertFalse(any("SSChronoMark" in t for t in state["traces"]), state["traces"])
        ns["OnTimer"](9)
        self.assertIn("pipboy wrist 3d housing=True screen=True", state["traces"])
        self.assertIn('QueueSharedMapSetup("pickup")', read(PSC))

        # 2. Grant -> unequip -> save -> load re-equips unconditionally with (true, true)
        state["equipped"] = False
        ns["SyncPipboyOwnedWornState"](player)
        self.assertEqual(state["glob"], 0.0)
        ns["OnPlayerLoadGame"](player)
        self.assertTrue(state["equipped"])
        self.assertEqual(state["glob"], 1.0)
        self.assertGreaterEqual(len(state["equips"]), 2)
        self.assertEqual(state["equips"][-1], (True, True))

        # Even if IsEquipped was already True on load, OnPlayerLoadGame re-applies EquipItem(true, true)
        equips_before = len(state["equips"])
        ns["OnPlayerLoadGame"](player)
        self.assertEqual(len(state["equips"]), equips_before + 1)
        self.assertEqual(state["equips"][-1], (True, True))


if __name__ == "__main__":
    unittest.main()
