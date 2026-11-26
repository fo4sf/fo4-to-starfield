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
        self.assertIn("safe_spawn", cfg["pod_exit_modes_supported"])
        self.assertIn("cryopod_anim", cfg["pod_exit_modes_supported"])

        games = cfg["games"]
        for game_key in ("fo4", "fo3", "fnv"):
            self.assertIn(game_key, games)
            entry = games[game_key]
            for req_key in (
                "mute_arrival_discovery_popup",
                "silent_starter_strip",
                "starter_strip_starfield_armor_ids",
                "pod_exit_mode",
                "pod_safe_step_m",
                "pod_safe_heading_deg",
                "single_pass_landing_fade",
                "autosave_points",
            ):
                self.assertIn(req_key, entry, f"{game_key} missing {req_key}")

        fo4 = games["fo4"]
        self.assertTrue(fo4["mute_arrival_discovery_popup"])
        self.assertTrue(fo4["silent_starter_strip"])
        self.assertEqual(fo4["pod_exit_mode"], "safe_spawn")
        self.assertAlmostEqual(fo4["pod_safe_step_m"], -3.2, places=3)
        self.assertAlmostEqual(fo4["pod_safe_heading_deg"], 270.0, places=3)
        self.assertTrue(fo4["single_pass_landing_fade"])
        self.assertEqual(fo4["autosave_points"], ["pod_exit", "pipboy_pickup"])
        self.assertEqual(fo4["pod_safe_pos_override"], {"x": 9.143, "y": -7.314, "z": -1.029})

        ids = fo4["starter_strip_starfield_armor_ids"]
        for expected_id in ("0x001E2B17", "0x001E2B18", "0x001E2B19", "0x0001D1E7", "0x000D4893"):
            self.assertIn(expected_id, ids)

        # Ensure documented FO3/FNV placeholders do not inherit FO4 pod step/heading or autosave points
        self.assertEqual(games["fo3"]["pod_exit_mode"], "none")
        self.assertEqual(games["fnv"]["pod_exit_mode"], "none")
        self.assertEqual(games["fo3"]["autosave_points"], [])
        self.assertEqual(games["fnv"]["autosave_points"], [])


class Item3LeaksBehindFlagsTests(unittest.TestCase):
    def test_discovery_popup_muted_by_flag_and_still_attaches_marker(self):
        psc = read(PSC)
        compiled = compile(
            translated_functions(
                psc,
                ("RequestArrivalDiscovery", "CheckLanding", "Near"),
                "arrivalWorld, fallbackPending, discoveryMarkerMoved, discoveryAttachPending, landingChecks",
            ),
            PSC,
            "exec",
        )
        world = object()
        other_world = object()
        player = Reference(world, (-1200.0, -2700.0, 100.0))
        marker = Reference(other_world, (-10.0, -20.0, 95.0))
        traces, stages = [], []
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
            arrivedAt=0.0,
            fallbackPending=False,
            discoveryMarkerMoved=False,
            discoveryAttachPending=False,
            landingChecks=0,
            MuteArrivalDiscoveryPopup=True,
            Game=SimpleNamespace(GetFormFromFile=lambda *_: marker, IsFastTravelEnabled=lambda: True),
            Utility=SimpleNamespace(GetCurrentRealTime=lambda: 10.0),
            FailExit=lambda *_: None,
            AdvanceTo=stages.append,
        )
        exec(compiled, ns)
        ns["CheckLanding"](player)  # tick 1: attaches unmerged marker cleanly
        self.assertEqual(len(marker.moveto_calls), 1)
        self.assertEqual(marker.discovery_calls, 0)
        self.assertEqual(stages, [])
        ns["CheckLanding"](player)  # tick 2: muted discovery -> no SetMarkerDiscovered(), completes stage 200
        self.assertEqual(marker.discovery_calls, 0)
        self.assertEqual(stages, [200])
        self.assertTrue(any("arrival discovery muted=true reason=per_game_flag ref=" in t for t in traces), traces)

        # Flag off restores original SetMarkerDiscovered() behavior
        ns["MuteArrivalDiscoveryPopup"] = False
        ns["CheckLanding"](player)
        self.assertEqual(marker.discovery_calls, 1)
        self.assertTrue(any("arrival discovery requested ref=" in t for t in traces), traces)

    def test_silent_starter_strip_unequips_and_removes_silently_before_remove_all_items(self):
        psc = read(PSC)
        compiled = compile(
            translated_functions(psc, ("ResetInventory",), ""),
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
                ("ForceFadeIn", "ReleaseStoryLandingFade", "FinishSurface", "ApplyStage", "AdvanceTo", "ClearVaultSaveLock", "TimerEvent"),
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
            Game=SimpleNamespace(
                GetPlayer=lambda: player,
                GetFormFromFile=lambda *_: anchor,
                ShowFirstPersonGeometry=lambda *_: None,
                FadeOutGame=lambda *a: fades.append(a),
                SetInChargen=lambda *_: None,
                SetCharGenHUDMode=lambda *_: None,
            ),
            Utility=SimpleNamespace(GetCurrentRealTime=lambda: 20.0, Wait=lambda *_: None),
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
        self.assertTrue(ns["surfaceFadeInDone"])
        self.assertEqual(len(fades), 1)
        self.assertIn("ascent gap_closed=true fade_in_at_surface=true", traces)

        # Stage 200 -> ReleaseStoryLandingFade() must NOT fade again or start Timer 5
        ns["AdvanceTo"](200)
        self.assertEqual(len(fades), 1)
        self.assertEqual(timers, [])
        self.assertIn("story_fade single_pass=true already_faded=True", traces)

        # Even if Timer 5 fired, SinglePassLandingFade=True guards it
        ns["TimerEvent"](5)
        self.assertEqual(len(fades), 1)
        self.assertEqual(timers, [])


class Item4LiftFlowTests(unittest.TestCase):
    def test_lift_menu_header_rides_immediately_even_with_unspent_special(self):
        hdr = LIFT_MENU_H.read_text(encoding="utf-8")
        case0 = hdr[hdr.index("case 0:"):hdr.index("case 1:")]
        self.assertNotIn("EnterSpecialPage", case0)
        self.assertNotIn("Remaining()", case0)
        self.assertIn("a_out.action = CommitAction::kRide;", case0)
        self.assertIn("a_out.specialConfirmed = true;", case0)
        self.assertIn("return true;", case0)
        # Edit S.P.E.C.I.A.L. on row 1 remains intact
        case1 = hdr[hdr.index("case 1:"):hdr.index("case 2:")]
        self.assertIn("EnterSpecialPage();", case1)
        self.assertIn("CHOOSE RIDE LIFT TO SURFACE NOW, OR EDIT S.P.E.C.I.A.L.", hdr)

    def test_paused_lift_ride_never_bounces_and_timer1_closes_black_gap(self):
        psc = read(PSC)
        ev_timer = re.search(r"Event OnTimer\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        wrapped = psc + f"\nFunction TimerEvent({ev_timer[1]})\n{ev_timer[2]}EndFunction\n"
        compiled = compile(
            translated_functions(
                wrapped,
                ("ShowPausedExitLiftMenu", "PromptVaultExitLift", "TimerEvent"),
                "asked, liftSpecConfirmed, rideActive, rideTransferred, surfaceMovedAt, ticks",
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
            rideActive=False,
            rideTransferred=False,
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
            StartAscent=ascents.append,
            OpenLiftAttributeAllocation=lambda: None,
            StartTimer=lambda s, tid: timers.append((s, tid)),
            GetStage=lambda: cur_stage[0],
            CheckLanding=lambda *_: None,
        )
        exec(compiled, ns)
        ns["PromptVaultExitLift"](player)
        self.assertEqual(ascents, [player])
        self.assertEqual(need_attr, [])
        self.assertTrue(ns["liftSpecConfirmed"])

        # Timer 1 schedules 0.15 s at stage 40 (and during rideActive / surfaceMovedAt > 0.0)
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
                ("RunPodExitHook", "NoteLooksStage20", "ApplyStage", "StandsInVault"),
                "applied, looksSetStage20, podExitDone",
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
        angles, traces, autosaves = [], [], []
        player.SetAngle = lambda rx, ry, rz: angles.append((rx, ry, rz))
        player.GetAngleZ = lambda: angles[-1][2] if angles else 0.0
        cur_stage = [10]

        def make_ns(mode="safe_spawn", override=False, pod_y=-6.614):
            traces.clear()
            angles.clear()
            autosaves.clear()
            cur_stage[0] = 10
            player.pos = (9.143, pod_y, -0.729)
            return dict(
                _PStr=_PStr,
                Trace=traces.append,
                PodExitMode=mode,
                PodSafeStep=-3.2,
                PodSafeHeading=270.0,
                HasPodSafeExitOverride=override,
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
                Game=SimpleNamespace(GetPlayer=lambda: player, GetFormFromFile=lambda *_: vault_anchor),
                GetStage=lambda: cur_stage[0],
                SetStage=lambda n: cur_stage.__setitem__(0, n),
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
        ns1 = make_ns(mode="safe_spawn", override=False, pod_y=-6.614)
        exec(compiled, ns1)
        ns1["NoteLooksStage20"]()
        self.assertEqual(cur_stage[0], 20)
        self.assertEqual(autosaves, [20])
        self.assertAlmostEqual(player.pos[0], 9.143, places=3)
        self.assertAlmostEqual(player.pos[1], -7.314, places=3)
        self.assertAlmostEqual(player.pos[2], -0.729, places=3)
        self.assertEqual(angles, [(0.0, 0.0, 270.0)])
        self.assertIn("stage 15 by=safe_spawn", traces)
        self.assertTrue(
            any(
                t.startswith("pod_exit mode=safe_spawn hook_stage=15 clear=true pos=9.143 -7.314 ")
                and t.endswith(" heading=270.0")
                for t in traces
            ),
            traces,
        )
        # Idempotent: walking away and re-entering ApplyStage(20) never snaps back
        player.pos = (-5.0, -7.314, 0.0)
        ns1["ApplyStage"](20, "Trigger")
        self.assertEqual(player.pos, (-5.0, -7.314, 0.0))

        # 2) HasPodSafeExitOverride=True with PodY already at -7.314 does not double-step
        ns2 = make_ns(mode="safe_spawn", override=True, pod_y=-7.314)
        exec(compiled, ns2)
        ns2["NoteLooksStage20"]()
        self.assertAlmostEqual(player.pos[1], -7.314, places=3)

        # 3) cryopod_anim hook mode leaves player & fade untouched and logs hook seam
        ns3 = make_ns(mode="cryopod_anim", override=False, pod_y=-6.614)
        exec(compiled, ns3)
        ns3["NoteLooksStage20"]()
        self.assertEqual(player.pos, (9.143, -6.614, -0.729))
        self.assertEqual(angles, [])
        self.assertIn("stage 15 by=cryopod_anim", traces)
        self.assertTrue(
            any("pod_exit mode=cryopod_anim_hook hook_stage=15 clear=true pos=9.143 -6.614 -0.729 " in t for t in traces),
            traces,
        )


class G5G12PipboyEquipAndAutosaveTests(unittest.TestCase):
    def test_pickup_forces_first_person_sheathes_autosaves_and_reload_reequips_after_unequip(self):
        psc = read(PSC)
        compiled = compile(
            translated_functions(
                psc,
                (
                    "HandlePipboyPickup",
                    "EnsurePipboyWristEquipped",
                    "SyncPipboyOwnedWornState",
                    "TriggerVaultPickupAutosave",
                    "Actor.OnPlayerLoadGame",
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
            PipboyWristSlotLabel="54,55",
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

        # 1. Pickup equips wrist, logs slot=54,55 (data), forces 1st person & sheathes, plays idle, triggers pickup autosave
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
        self.assertIn("vault_death_recovery=autosave stage=20 after=pipboy_pickup", state["traces"])
        self.assertTrue(any("slot=54,55" in t for t in state["traces"]), state["traces"])
        self.assertFalse(any("SSChronoMark" in t for t in state["traces"]), state["traces"])

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
