"""W1 safe-defaults regression guard (`Round 7`).

Fails immediately if any known in-game crash, stall, or Track-2 experimental slice
flips back ON by default in `make_core_bundle.py`, `make_newgame.py`, `dotnet/NewGame/Program.cs`,
`FO4SF_NewGameQuest.psc`, `FO4SF_NewGameSpecial.psc`, `make_pipboy_stage_ini.py`,
`sfse/FO4SFPipboyMenu/FO4SFPipboyMenu.ini`, or `docs/known-issues.md`.
"""
from __future__ import annotations

import inspect
import json
import math
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
for _p in (
    str(ROOT / "src"),
    str(ROOT / "scripts" / "core"),
    str(ROOT / "scripts" / "newgame"),
    str(ROOT / "scripts" / "ui"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_core_bundle as mcb  # noqa: E402
import make_newgame as mng  # noqa: E402
import make_pipboy_stage_ini as mpsi  # noqa: E402
from tests import test_core_bundle as tcb  # noqa: E402
from tests.test_exit_arrival import translated_functions  # noqa: E402


EXPECTED_TRACK1_PLAYER_PLUGINS = (
    "FO4ActorRaider.esm",
    "FO4TerrainCore.esm",
    "FO4TerrainCore_Mars.esm",
    "FO4SFCoreValues.esm",
    "FO4SFVaultGearDoor.esm",
    "FO4SFExitLift.esm",
    "FO4SFVaultPod.esm",
    "FO4SFMission.esm",
    "FO4SFNewGame.esm",
    "FO4SFWorkshop.esm",
    "FO4SFPowerArmor.esm",
    "FO4SFFortHagen.esm",
    "FO4SFPipboyProbe.esm",
    "FO4SFPipboyTravel.esm",
)

TRACK2_EXPERIMENTAL_ESMS = (
    "FO4SFRads.esm",
    "FO4SFHardcore.esm",
    "FO4SFProgression.esm",
    "FO4SFListDialogue.esm",
    "FO4SFCombat.esm",
    "FO4SFReputation.esm",
    "FO4SFCompanions.esm",
    "FO4SFALife.esm",
    "FO4SFCoreCandidate.esm",
)


class SafeDefaultsTests(unittest.TestCase):
    def test_w1_bundle_lists_and_cli_defaults_keep_routeloot_bridge_and_track2_off(self) -> None:
        self.assertEqual(len(EXPECTED_TRACK1_PLAYER_PLUGINS), 14)
        self.assertEqual(mcb.PLAYER_BUNDLE_PLUGINS, EXPECTED_TRACK1_PLAYER_PLUGINS)
        self.assertNotIn("FO4SFRouteLoot.esm", mcb.PLAYER_BUNDLE_PLUGINS)
        self.assertNotIn("FO4SFRouteLoot.esm", mcb.CORE_BUNDLE_PLUGINS)
        self.assertNotIn("FO4SFBridge.esm", mcb.PLAYER_BUNDLE_PLUGINS)
        self.assertNotIn("FO4SFBridge.esm", mcb.CORE_BUNDLE_PLUGINS)
        self.assertIn("fo4sfbridge.esm", mcb.DROPPED_SLICE_ESMS)
        for t2_esm in TRACK2_EXPERIMENTAL_ESMS:
            self.assertNotIn(t2_esm, mcb.PLAYER_BUNDLE_PLUGINS, f"{t2_esm} leaked into Track-1 PLAYER_BUNDLE_PLUGINS")
            self.assertIn(t2_esm, mcb.CORE_BUNDLE_PLUGINS)
        self.assertEqual(len(mcb.CORE_BUNDLE_PLUGINS), 23)

        sig_fold = inspect.signature(mcb.fold_bundle)
        self.assertIs(sig_fold.parameters["with_route_loot"].default, False)
        self.assertIs(sig_fold.parameters["with_experimental_core"].default, False)
        self.assertEqual(sig_fold.parameters["profile"].default, "player")

        captured: list[tuple[str, object]] = []
        orig_build, orig_fold = mcb.cmd_build, mcb.cmd_fold
        try:
            mcb.cmd_build = lambda a, system=None: (captured.append(("build", a)), 0)[1]
            mcb.cmd_fold = lambda a, system=None: (captured.append(("fold", a)), 0)[1]
            mcb.main([
                "build", "--owner-set", "ow", "--out", "out", "--work", "wk",
                "--starfield-dir", "sf", "--fo4-data", "fo4", "--port", "port.esm",
                "--port-ids", "ids.json", "--door-anim-dll", "calumi.dll",
                "--collision-template", "col.nif", "--texconv", "texconv.exe",
            ])
            mcb.main(["fold", "--owner-set", "ow", "--stages-root", "st", "--out", "out"])
        finally:
            mcb.cmd_build, mcb.cmd_fold = orig_build, orig_fold

        for cmd_name, parsed in captured:
            self.assertEqual(parsed.profile, "player", cmd_name)
            self.assertFalse(parsed.with_route_loot, cmd_name)
            self.assertFalse(parsed.with_experimental_core, cmd_name)
            self.assertFalse(parsed.fade_hold, cmd_name)

        # Verify verify_bundle refuses FO4SFBridge.esm, unapproved FO4SFRouteLoot.esm (both profiles), and Track 2 on player
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            helper = tcb.CoreBundleTests()
            owner, stages_root, port_esm, _ = helper._build_synthetic_owner_and_stages(root)

            out_player = root / "player-13"
            self.assertEqual(
                mcb.main(
                    ["fold", "--owner-set", str(owner), "--stages-root", str(stages_root), "--out", str(out_player), "--port", str(port_esm)],
                    system=tcb._FakeSystemClosed(),
                ),
                0,
            )
            pplan = json.loads((out_player / "bundle_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(len(pplan["plugins"]), 12)  # 14 minus 2 optional Pip-Boy ESMs when --with-pipboy omitted
            self.assertFalse(pplan["with_route_loot"])
            self.assertFalse(pplan["with_experimental_core"])

            # Injecting FO4SFBridge.esm must fail verify
            bridge_sha = tcb._make_tes4_esm(out_player / "FO4SFBridge.esm", extra_tag=b"bridge")
            bad_bridge = dict(pplan, plugins=[*pplan["plugins"], "FO4SFBridge.esm"])
            bad_bridge["components"] = dict(pplan["components"], bridge={"plugins": ["FO4SFBridge.esm"], "outputs": {"FO4SFBridge.esm": bridge_sha}})
            bad_bridge_p = root / "bad_bridge_plan.json"
            bad_bridge_p.write_text(json.dumps(bad_bridge, indent=1), encoding="utf-8")
            probs_bridge, _ = mcb.verify_bundle(str(out_player), str(bad_bridge_p), port_esm=str(port_esm))
            self.assertTrue(any("FO4SFBridge.esm" in p for p in probs_bridge), probs_bridge)

            # Injecting FO4SFRads.esm into player profile with_experimental_core=False must fail verify
            rads_bytes = (stages_root / "04-rads" / "FO4SFRads.esm").read_bytes()
            (out_player / "FO4SFRads.esm").write_bytes(rads_bytes)
            bad_t2 = dict(pplan, plugins=[*pplan["plugins"], "FO4SFRads.esm"])
            bad_t2["components"] = dict(pplan["components"], rads={"plugins": ["FO4SFRads.esm"], "outputs": {"FO4SFRads.esm": tcb._sha256_bytes(rads_bytes)}})
            bad_t2_p = root / "bad_t2_plan.json"
            bad_t2_p.write_text(json.dumps(bad_t2, indent=1), encoding="utf-8")
            probs_t2, _ = mcb.verify_bundle(str(out_player), str(bad_t2_p), port_esm=str(port_esm))
            self.assertTrue(any("Track 2 experimental" in p for p in probs_t2), probs_t2)

            # Test profile also excludes FO4SFRouteLoot.esm by default and refuses it when with_route_loot=False
            out_test = root / "test-no-rl"
            self.assertEqual(
                mcb.main(
                    ["fold", "--owner-set", str(owner), "--stages-root", str(stages_root), "--out", str(out_test), "--port", str(port_esm), "--profile", "test"],
                    system=tcb._FakeSystemClosed(),
                ),
                0,
            )
            tplan = json.loads((out_test / "bundle_plan.json").read_text(encoding="utf-8"))
            self.assertFalse(tplan["with_route_loot"])
            self.assertNotIn("FO4SFRouteLoot.esm", tplan["plugins"])

    def test_w1_stage_from_checkout_passes_fade_hold_only_on_test_or_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            helper = tcb.CoreBundleTests()
            owner, _stages_root, port_esm, _ = helper._build_synthetic_owner_and_stages(root)
            port_ids = root / "ids.json"
            port_ids.write_text("{}", encoding="utf-8")

            ng_invocations: list[tuple[str, list[str]]] = []
            slice_invocations: list[str] = []
            orig_run_py = mcb._run_py

            def _spy_run_py(py_exe: str, script_rel: str, args):
                arg_list = list(args)
                out_flag = "--out" if "--out" in arg_list else "--staging"
                out_dir = Path(arg_list[arg_list.index(out_flag) + 1])
                out_dir.mkdir(parents=True, exist_ok=True)
                if script_rel == "scripts/newgame/make_newgame.py":
                    ng_invocations.append((out_dir.name, arg_list))
                    (out_dir / "plan.json").write_text(
                        json.dumps({
                            "options": {
                                "hold": ",".join(f"Q{i}" for i in range(199)),
                                "fade_hold": "--fade-hold" in arg_list,
                            },
                            "points": {"pod": {"step_m": -2.5}},
                        }),
                        encoding="utf-8",
                    )
                    return
                slice_invocations.append(script_rel)

            mcb._run_py = _spy_run_py
            try:
                base_kwargs = dict(
                    work=str(root / "work"),
                    out=str(root / "out"),
                    render_python=None,
                    starfield_dir=str(root / "sf"),
                    fo4_data=str(root / "fo4"),
                    port=str(port_esm),
                    port_ids=str(port_ids),
                    door_anim_dll=str(root / "calumi.dll"),
                    collision_template=str(root / "col.nif"),
                    texconv=str(root / "texconv.exe"),
                    owner_set=str(owner),
                    commonlibsf=None,
                    msvc_env=None,
                    no_walk_harness=True,
                    allow_starfield_standins=True,
                )
                # 1. Default --profile player: NO --fade-hold, NO Track 2 slice scripts, NO route loot!
                mcb.stage_from_checkout(SimpleNamespace(**base_kwargs, profile="player"))
                self.assertEqual(len(ng_invocations), 1)
                self.assertEqual(ng_invocations[0][0], "03-newgame")
                self.assertNotIn("--fade-hold", ng_invocations[0][1])
                for forbidden_script in (
                    "scripts/rads/make_rads_core.py",
                    "scripts/survival/make_hardcore.py",
                    "scripts/progression/make_progression.py",
                    "scripts/dialogue/make_list_dialogue.py",
                    "scripts/combat/make_combat_core.py",
                    "scripts/reputation/make_reputation_core.py",
                    "scripts/companions/make_companions_core.py",
                    "scripts/alife/make_alife.py",
                    "scripts/loot/make_route_loot.py",
                ):
                    self.assertNotIn(forbidden_script, slice_invocations)

                # 2. --profile test: passes --fade-hold into separate 03-newgame-fadehold stage, still NO route loot!
                slice_invocations.clear()
                mcb.stage_from_checkout(SimpleNamespace(**base_kwargs, profile="test"))
                self.assertEqual(len(ng_invocations), 2)
                self.assertEqual(ng_invocations[1][0], "03-newgame-fadehold")
                self.assertIn("--fade-hold", ng_invocations[1][1])
                self.assertIn("scripts/progression/make_progression.py", slice_invocations)
                self.assertNotIn("scripts/loot/make_route_loot.py", slice_invocations)
            finally:
                mcb._run_py = orig_run_py

    def test_w1_pipboy_stage_ini_and_shipped_ini_safe_defaults(self) -> None:
        shipped_ini = (ROOT / "sfse" / "FO4SFPipboyMenu" / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
        for req in ("MapBlockStarMap=0", "Arm=1", "BootOnFirstOpen=0"):
            self.assertIn(f"\n{req}\n", "\n" + shipped_ini, req)

        fmt_default = mpsi.format_stage_ini(["HideMenu"], boot_movie="pipboybootsequence")
        for req in ("MapBlockStarMap=0", "Arm=1", "BootOnFirstOpen=0"):
            self.assertIn(f"\n{req}\n", "\n" + fmt_default, req)

        parsed_default = mpsi.build_parser().parse_args(["--stage", "dummy"])
        self.assertEqual(parsed_default.map_block_starmap, 0)
        self.assertEqual(parsed_default.arm, 1)
        self.assertEqual(parsed_default.boot_on_first_open, 0)

        parsed_opt = mpsi.build_parser().parse_args([
            "--stage", "dummy", "--arm", "1", "--boot-on-first-open", "1", "--map-block-starmap", "1"
        ])
        self.assertEqual((parsed_opt.arm, parsed_opt.boot_on_first_open, parsed_opt.map_block_starmap), (1, 1, 1))

    def test_w1_fade_hold_false_direct_vault_story_and_single_looks_box_at_stage_10(self) -> None:
        cs = (ROOT / "dotnet" / "NewGame" / "Program.cs").read_text(encoding="utf-8")
        psc = (ROOT / "scripts" / "newgame" / "FO4SF_NewGameQuest.psc").read_text(encoding="utf-8")
        looks_psc = (ROOT / "scripts" / "newgame" / "FO4SF_NewGameLooks.psc").read_text(encoding="utf-8")

        self.assertIn("public const bool DefaultFadeHold = false;", cs)
        self.assertFalse(mng.DEFAULT_FADE_HOLD)
        self.assertIn("bool Property FadeHold = false Auto Const", psc)

        stage_default = mng.fade_hold_option(SimpleNamespace(fade_hold=False, no_fade_hold=False))
        stage_alias = mng.fade_hold_option(SimpleNamespace(fade_hold=False, no_fade_hold=True))
        stage_opt_in = mng.fade_hold_option(SimpleNamespace(fade_hold=True, no_fade_hold=False))
        self.assertFalse(stage_default)
        self.assertFalse(stage_alias)
        self.assertTrue(stage_opt_in)

        ev_timer = re.search(r"Event OnTimer\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        assert ev_timer is not None
        wrapped = psc + f"\nFunction TimerEvent({ev_timer[1]})\n{ev_timer[2]}EndFunction\n"
        funcs = (
            "BackdropName", "UsePreworldRoom", "EnterVault", "StandsInVault", "ResetInventory", "FillO2",
            "FadeIn", "DisableHandScanner", "PodEntryX", "PodEntryY", "PodSafeX", "PodSafeY",
            "EnsureFadedInForChoice", "PrepareBeforeCreator",
            "PodAnimReady", "ShouldSkipMenuDelay", "NoteLooksDone",
            "NoteLooksStage20", "CompleteLooksStage20AfterPodExit", "StartPodOpen", "RunPodExitHook",
            "IsPreworldLooksHandled", "FindStoryStartPlaceRow", "ApplyStage", "AdvanceTo",
            "RunModeChoiceChain", "TimerEvent",
        )
        vars_csv = (
            "faded, entered, startRoomMoves, startRoomEntered, startRoomUiPrepared, "
            "loadingMenuOpen, loadingMenuClosedSeen, loadingHookRegistered, startUiReady, h00SkipLoading, "
            "modeChoiceRan, modeBoxWaiting, modeBoxWaitSeconds, preworldLooksDone, preworldLooksHow, preworldLooksBy, "
            "podLooksDone, podLooksHow, podLooksBy, podExitDone, podExitStarted, podFellBack, "
            "applied, pendingStage, pendingStageBy, looksSetStage20, exitUsedFallback, vaultMoves, centered, centerTries, "
            "ticks, startedAt, scannerLayer, podChecked, rideActive, surfaceMovedAt, returnSurfacePending, asked"
        )
        compiled = compile(translated_functions(wrapped, funcs, vars_csv), "FO4SF_NewGameQuest.psc", "exec")

        logs: list[str] = []
        mode_box_calls: list[int] = []
        cur_stage = [0]
        globs = {k: 0.0 for k in ("GameMode", "StoryLine", "SurvivalStart", "SurvivalLocked", "StartDifficulty", "WarfareFaction", "WarfareStartIndex", "StartPlaceRow", "StartChoiceDone")}

        def _glob(name: str):
            return SimpleNamespace(GetValue=lambda: globs[name], SetValue=lambda v: globs.__setitem__(name, float(v)))

        vault_anchor = SimpleNamespace(GetParentCell=lambda: "FO4Port_Vault111Cryo")
        player = SimpleNamespace(
            pos=(9.143, -6.614, -0.729),
            cell="FO4Port_Vault111Cryo",
            GetPositionX=lambda: player.pos[0],
            GetPositionY=lambda: player.pos[1],
            GetPositionZ=lambda: player.pos[2],
            SetPosition=lambda x, y, z: setattr(player, "pos", (x, y, z)),
            SetAngle=lambda *a: None,
            MoveTo=lambda *a: None,
            GetParentCell=lambda: player.cell,
            GetWorldSpace=lambda: None,
            IsInInterior=lambda: True,
            Is3DLoaded=lambda: True,
            GetItemCount=lambda *a: 0,
            RemoveAllItems=lambda *a: None,
            AddItem=lambda *a: None,
            EquipItem=lambda *a: None,
            IsEquipped=lambda *a: True,
            GetValue=lambda *a: 100.0,
            ModValue=lambda *a: None,
        )
        ns = dict(
            FadeHold=False, StartChoiceBackdrop=1, StartLoadTimeout=15.0, LooksWait=120.0, RaceMenuMode=2,
            PodExitMode="safe_spawn", PodAnimPlugin="FO4SFVaultPod.esm", PodCreatorInPod=False,
            PodOriginX=0.0, PodOriginY=0.0, PodOriginZ=0.0,
            PodEntryStep=-2.5, PodSafeStep=-3.2, PodSafeHeading=270.0,
            podLooksDone=False, podLooksHow="", podLooksBy="Trigger", podExitDone=False, podExitStarted=False, podFellBack=False,
            ClearInventory=True, VaultSuitId=0, AnchorTemporary=False, O2Capacity=None, O2CapacityAmount=0.0,
            faded=False, entered=True, startRoomMoves=0, startRoomEntered=False, startRoomUiPrepared=False,
            loadingMenuOpen=False, loadingMenuClosedSeen=False, loadingHookRegistered=False, startUiReady=False, h00SkipLoading=False,
            modeChoiceRan=False, modeBoxWaiting=False, modeBoxWaitSeconds=0,
            preworldLooksDone=False, preworldLooksHow="", preworldLooksBy="Trigger",
            applied=0, pendingStage=-1, pendingStageBy="other", looksSetStage20=False,
            exitUsedFallback=False, vaultMoves=1, centered=0, centerTries=0, ticks=0, startedAt=0.0,
            podChecked=False, rideActive=False, surfaceMovedAt=0.0, returnSurfacePending=False, asked=False,
            VaultAnchorId=0x805, VaultPlugin="FO4Port.esm", VaultCell="FO4Port_Vault111Cryo", CenterTicks=30,
            AnchorX=0.0, AnchorY=0.0, AnchorZ=0.0, PodX=9.143, PodY=-6.614, PodZ=-1.029, PodLift=0.3, PodHeading=0.0,
            StartRoomMarkerRef=SimpleNamespace(GetParentCell=lambda: "FO4SF_StartRoomCell"),
            GameModeGlobal=_glob("GameMode"),
            StoryLineGlobal=_glob("StoryLine"),
            SurvivalStartGlobal=_glob("SurvivalStart"),
            SurvivalLockedGlobal=_glob("SurvivalLocked"),
            StartDifficultyGlobal=_glob("StartDifficulty"),
            WarfareFactionGlobal=_glob("WarfareFaction"),
            WarfareStartIndexGlobal=_glob("WarfareStartIndex"),
            StartPlaceRowGlobal=_glob("StartPlaceRow"),
            StartChoiceDoneGlobal=_glob("StartChoiceDone"),
            TestModeGlobal=SimpleNamespace(GetValue=lambda: 0.0),
            ModePickMsg=SimpleNamespace(Show=lambda: (mode_box_calls.append(1), 0)[1]),
            StartPlaceIds=["fo4_vault111"],
            StartPlaceModes=[1],
            StartPlaceStories=["fo4_commonwealth"],
            Game=SimpleNamespace(
                GetPlayer=lambda: player,
                ShowFirstPersonGeometry=lambda *a: None,
                FadeOutGame=lambda *a: None,
                SetInChargen=lambda *a: None,
                SetCharGenHUDMode=lambda *a: None,
                GetFormFromFile=lambda fid, plg: vault_anchor if (fid, plg) == (0x805, "FO4Port.esm") else None,
            ),
            Utility=SimpleNamespace(Wait=lambda s: None, GetCurrentRealTime=lambda: 5.0),
            Debug=SimpleNamespace(Notification=lambda *a: None),
            InputEnableLayer=SimpleNamespace(Create=lambda: None),
            scannerLayer=None,
            UnregisterForMenuOpenCloseEvent=lambda m: None,
            StartTimer=lambda *a: None,
            SetStage=lambda n: cur_stage.__setitem__(0, n),
            GetStage=lambda: cur_stage[0],
            SetObjectiveDisplayed=lambda *a: None,
            SetObjectiveCompleted=lambda *a: None,
            SetActive=lambda *a: None,
            CompleteQuest=lambda: None,
            StartLandingQuests=lambda: None,
            EnsureLoadHookRegistered=lambda p: None,
            TriggerVaultPodRecoveryAutosave=lambda *a: None,
            HoldOffPass=lambda p: None,
            Trace=lambda m: logs.append(m),
        )
        exec(compiled, ns)
        self.assertFalse(ns["UsePreworldRoom"]())

        ns["TimerEvent"](1)
        self.assertEqual(mode_box_calls, [])  # T3 avoided: ModePickMsg NEVER called when FadeHold=False!
        self.assertEqual(cur_stage[0], 10)
        self.assertEqual(globs["GameMode"], 1.0)
        self.assertEqual(globs["SurvivalStart"], 0.0)
        self.assertEqual(globs["StartChoiceDone"], 1.0)
        self.assertIn("start record mode=story story=fo4_commonwealth faction=-1 place=fo4_vault111 survival=0 difficulty=1 backdrop=none", logs)
        # Critical W1 check: IsPreworldLooksHandled() MUST be False at stage 10 when FadeHold=False so FO4SF_NewGameLooks runs!
        self.assertFalse(ns["IsPreworldLooksHandled"]())

        looks_ev = re.search(r"Event OnTimer\((.*?)\)\n(.*?)EndEvent", looks_psc, re.S)
        assert looks_ev is not None
        looks_compiled = compile(
            translated_functions(looks_psc + f"\nFunction LooksTimer({looks_ev[1]})\n{looks_ev[2]}EndFunction\n", ("LooksTimer", "Done", "TracePosition"), "shown, waiting"),
            "FO4SF_NewGameLooks.psc",
            "exec",
        )
        vault_looks_prompts: list[int] = []
        fake_ng_quest = SimpleNamespace(
            IsPreworldLooksHandled=ns["IsPreworldLooksHandled"],
            NoteLooksStage20=ns["NoteLooksStage20"],
            NoteLooksDone=ns["NoteLooksDone"],
            ShouldSkipMenuDelay=ns["ShouldSkipMenuDelay"],
            EnsureFadedInForChoice=ns["EnsureFadedInForChoice"],
            PrepareBeforeCreator=ns["PrepareBeforeCreator"],
        )
        lns = dict(
            self=fake_ng_quest,
            shown=False, waiting=False, MenuDelay=2.0, MenuName="ChargenMenu", RaceMenuMode=2,
            GetStage=lambda: cur_stage[0],
            SetStage=lambda n: cur_stage.__setitem__(0, n),
            StartMessage=SimpleNamespace(Show=lambda: (vault_looks_prompts.append(1), 0)[1]),
            Game=SimpleNamespace(GetPlayer=lambda: SimpleNamespace(GetPositionX=lambda: 0.0, GetPositionY=lambda: 0.0, GetPositionZ=lambda: 0.0, GetAngleZ=lambda: 0.0, Is3DLoaded=lambda: True, GetParentCell=lambda: "FO4Port_Vault111Cryo", GetWorldSpace=lambda: None)),
            Utility=SimpleNamespace(Wait=lambda s: None, GetCurrentRealTime=lambda: 7.0),
            StartTimer=lambda *a: None,
            Trace=lambda m: logs.append("LOOKS:" + str(m)),
        )
        exec(looks_compiled, lns)
        lns["LooksTimer"](2)
        self.assertEqual(vault_looks_prompts, [1])
        self.assertEqual(cur_stage[0], 20)
        self.assertTrue(ns["IsPreworldLooksHandled"]())

    def test_w1_track2_pex_decoupling_lift_special_fallback_and_u1_pipboy_placement(self) -> None:
        psc = (ROOT / "scripts" / "newgame" / "FO4SF_NewGameQuest.psc").read_text(encoding="utf-8")
        special_psc = (ROOT / "scripts" / "newgame" / "FO4SF_NewGameSpecial.psc").read_text(encoding="utf-8")
        mk_py = (ROOT / "scripts" / "newgame" / "make_newgame.py").read_text(encoding="utf-8")
        cs = (ROOT / "dotnet" / "NewGame" / "Program.cs").read_text(encoding="utf-8")

        # 1. Zero hard Track-2 script type declarations or `as FO4SF_*` casts in FO4SF_NewGameQuest.psc
        code_no_comments = "\n".join(
            ln.split(";", 1)[0] for ln in re.sub(r"\{.*?\}", "", psc, flags=re.S).splitlines()
        )
        for track2_type in ("FO4SF_HardcoreQuest", "FO4SF_ProgressionQuest", "FO4SF_ReputationQuest", "FO4SF_MapMarkers"):
            self.assertIsNone(
                re.search(rf"\b{track2_type}\s+\w+", code_no_comments),
                f"hard variable type {track2_type} remains in FO4SF_NewGameQuest.psc",
            )
            self.assertIsNone(
                re.search(rf"\bas\s+{track2_type}\b", code_no_comments),
                f"hard cast 'as {track2_type}' remains in FO4SF_NewGameQuest.psc",
            )
            self.assertIn(f'CastAs("{track2_type}")', psc)

        compile_fn_src = mk_py[mk_py.index("def compile_script("):mk_py.index("def new_partial(")]
        for track2_inc in ("PROGRESSION_SCRIPTS", "SURVIVAL_SCRIPTS", "REPUTATION_SCRIPTS", "MAPMARKERS_SCRIPTS"):
            self.assertNotIn(track2_inc, compile_fn_src)

        # 2. Lift S.P.E.C.I.A.L. falls back to FO4SF_NewGameSpecial.AllocateFromLift when FO4SFProgression.esm is absent
        self.assertIn("bool Function AllocateFromLift(Actor player)", special_psc)
        compiled_lift = compile(
            translated_functions(psc, ("OpenLiftAttributeAllocation",), "liftSpecConfirmed, asked"),
            "FO4SF_NewGameQuest.psc",
            "exec",
        )
        lift_logs: list[str] = []
        spec_calls: list[object] = []
        fake_player = SimpleNamespace(name="PlayerRef")
        fake_self = SimpleNamespace(
            CastAs=lambda name: SimpleNamespace(
                CallFunction=lambda fn, args: (spec_calls.append((fn, list(args))), True)[1]
            ) if name == "FO4SF_NewGameSpecial" else None
        )
        l_ns = dict(
            self=fake_self,
            liftSpecConfirmed=False,
            asked=True,
            Game=SimpleNamespace(GetFormFromFile=lambda fid, plg: None, GetPlayer=lambda: fake_player),
            StartTimer=lambda *a: None,
            Trace=lambda m: lift_logs.append(str(m)),
        )
        exec(compiled_lift, l_ns)
        l_ns["OpenLiftAttributeAllocation"]()
        self.assertEqual(spec_calls, [("AllocateFromLift", [fake_player])])
        self.assertTrue(l_ns["liftSpecConfirmed"])
        self.assertFalse(l_ns["asked"])
        self.assertTrue(any("fallback=FO4SF_NewGameSpecial edited=True confirmed=True" in m for m in lift_logs), lift_logs)

        # 3. U1 / V3 / A1(c): pipboyActi & gearConsoleActi use Fallout-only layer-1 activator NIFs above 0x01001616 (z_max=0.7722 m)
        vfa_cs = (ROOT / "dotnet" / "NewGame" / "VaultFalloutActivators.cs").read_text(encoding="utf-8")
        self.assertIn("VaultFalloutActivators.ConfigurePipboyActivator(pipboyActi);", cs)
        self.assertIn("VaultFalloutActivators.ConfigureGearConsoleActivator(gearConsoleActi);", cs)
        self.assertNotIn("actiTpl.Duplicate(", cs)
        self.assertIn("PipboyPickupScale = 1.0f", cs)
        self.assertIn("ConsoleActivatorScale = 1.0f", cs)
        self.assertIn(r'PipboyPickupModel = @"fo4sf\newgame\v111_pipboy_pickup.nif"', vfa_cs)
        self.assertIn(r'GearDoorConsoleModel = @"fo4sf\newgame\v111_geardoor_console.nif"', vfa_cs)
        self.assertIn("PipboyWorldCenter(pbPos, pbRot.Z)", cs)
        self.assertIn("ConsoleWorldPos(", cs)
        pb_x, pb_y, pb_z = -54.455524, -0.324950, 0.630884
        rz = 3.804386
        cx = pb_x + 0.10 * math.cos(rz) + 0.836 * math.sin(rz)
        cy = pb_y - 0.10 * math.sin(rz) + 0.836 * math.cos(rz)
        cz = pb_z + 0.145
        dist_xy = math.hypot(cx - pb_x, cy - pb_y)
        self.assertAlmostEqual(dist_xy, math.hypot(0.10, 0.836), places=4)
        self.assertAlmostEqual(cx, -55.0488, places=3)
        self.assertAlmostEqual(cy, -0.9224, places=3)
        self.assertAlmostEqual(cz, 0.7759, places=3)
        self.assertGreater(cz, 0.7722)  # strictly above FO4Port.esm:0x01001616 static collision top (0.7722 m)

    def test_v3_v4_vault_interactives_dual_console_registration_and_catwalk_hint(self) -> None:
        cs = (ROOT / "dotnet" / "NewGame" / "Program.cs").read_text(encoding="utf-8")
        psc = (ROOT / "scripts" / "newgame" / "FO4SF_NewGameQuest.psc").read_text(encoding="utf-8")

        # ConsoleWorldPos steps +0.085 m along the 45-deg console deck normal (0, +0.0601, +0.0601) m
        con_x, con_y, con_z = -54.3644, -1.8748, 1.6940
        rx, ry = math.pi / 4.0, 0.0
        wx = con_x - math.sin(ry) * 0.085
        wy = con_y + math.sin(rx) * math.cos(ry) * 0.085
        wz = con_z + math.cos(rx) * math.cos(ry) * 0.085
        self.assertAlmostEqual(wx, -54.3644, places=3)
        self.assertAlmostEqual(wy, -1.8147, places=3)
        self.assertAlmostEqual(wz, 1.7541, places=3)
        self.assertIn('pipboyActi.ActivateTextOverride = "Take";', cs)
        self.assertIn('gearConsoleActi.ActivateTextOverride = "Activate";', cs)

        funcs = (
            "EnsureVaultInteractivesRegistered",
            "ObjectReference.OnActivate",
            "ActivateGearDoorConsole",
        )
        vars_csv = (
            "itemWatchRegistered, pipboyRegistered, pipboyEquipWatchRegistered, cogDoorRegistered, cogDoorWatchedRef, "
            "consoleRegistered, consoleWatchedRef, portConsoleRegistered, portConsoleWatchedRef, "
            "consoleOpening, pistolPickedLogged"
        )
        compiled = compile(translated_functions(psc, funcs, vars_csv), "FO4SF_NewGameQuest.psc", "exec")

        def _make_ref(label: str, fid: int, pos: tuple[float, float, float]):
            return SimpleNamespace(
                label=label,
                GetFormID=lambda: fid,
                GetPositionX=lambda: pos[0],
                GetPositionY=lambda: pos[1],
                GetPositionZ=lambda: pos[2],
                PlayAnimation=lambda clip: anims.append((label, clip)),
            )

        for trigger_via_port_console in (False, True):
            logs: list[str] = []
            notifs: list[str] = []
            regs: list[tuple[object, str]] = []
            anims: list[tuple[str, str]] = []
            stages: list[tuple[int, str]] = []
            pipboy_pickups: list[object] = []
            cur_stage = [20]
            door_state = [3]

            player = _make_ref("PlayerRef", 0x14, (-54.36, -0.90, 0.589))
            pipboy_ref = _make_ref("FO4SF_PipboyCorpsePickupRef", 0x0A00080F, (-55.0488, -0.9224, 0.7759))
            own_console = _make_ref("FO4SF_GearDoorConsoleRef", 0x0A000819, (-54.3644, -1.8147, 1.7541))
            port_console = _make_ref("FO4Port_GearDoorConsoleRef", 0x02001319, (-54.3644, -1.8748, 1.6940))
            lift_ref = _make_ref("FO4Port_ExitLiftRef", 0x0200132F, (-30.6914, -1.5529, 4.9488))
            cog_door = SimpleNamespace(
                BlockActivation=lambda *a: None,
                GetOpenState=lambda: door_state[0],
                SetOpen=lambda open_flag: door_state.__setitem__(0, 2 if open_flag else 3),
            )

            port_ready = [not trigger_via_port_console]

            def _get_form(fid: int, plg: str):
                if plg == "FO4Port.esm":
                    if fid == 0x126D:
                        return cog_door
                    if fid == 0x1319:
                        return port_console if port_ready[0] else None
                    if fid == 0x132F:
                        return lift_ref
                return None

            sender = port_console if trigger_via_port_console else own_console
            double_tapped = [False]

            def _wait_with_double_tap(_s: float) -> None:
                if not double_tapped[0]:
                    double_tapped[0] = True
                    ns["OnActivate"](sender, player)

            ns = dict(
                itemWatchRegistered=True,
                pipboyRegistered=False,
                pipboyEquipWatchRegistered=False,
                PipboyWristArmor=None,
                cogDoorRegistered=False,
                cogDoorWatchedRef=None,
                consoleRegistered=False,
                consoleWatchedRef=None,
                portConsoleRegistered=False,
                portConsoleWatchedRef=None,
                consoleOpening=False,
                pistolPickedLogged=False,
                VaultPistolBase=None,
                VaultPistolId=0,
                PipboyCorpseRef=pipboy_ref,
                GearDoorConsoleRef=own_console,
                CogDoorId=0x126D,
                ConsoleRefId=0x1319,
                LiftId=0x132F,
                VaultPlugin="FO4Port.esm",
                TestModeGlobal=None,
                PipboyAcquiredGlobal=SimpleNamespace(GetValue=lambda: 1.0),
                NoPipboyMsg=SimpleNamespace(Show=lambda: 0),
                Game=SimpleNamespace(GetPlayer=lambda: player, GetFormFromFile=_get_form),
                Utility=SimpleNamespace(Wait=_wait_with_double_tap),
                Debug=SimpleNamespace(Notification=lambda msg: notifs.append(str(msg))),
                RegisterForRemoteEvent=lambda ref, ev: regs.append((ref, str(ev))),
                HandlePipboyPickup=lambda p: pipboy_pickups.append(p),
                GetStage=lambda: cur_stage[0],
                AdvanceTo=lambda st, by="Trigger": (cur_stage.__setitem__(0, st), stages.append((st, str(by)))),
                Trace=lambda m: logs.append(str(m)),
            )
            exec(compiled, ns)
            ns["EnsureVaultInteractivesRegistered"]()
            if not port_ready[0]:
                # Early pre-3D tick: persistent own_console registered, temporary port_console still pending retry!
                self.assertIn((own_console, "OnActivate"), regs)
                self.assertNotIn((port_console, "OnActivate"), regs)
                port_ready[0] = True
                ns["EnsureVaultInteractivesRegistered"]()

            # Both own 0A000819 AND FO4Port's ConsoleRefId (portCon) must be registered for OnActivate
            self.assertIn((pipboy_ref, "OnActivate"), regs)
            self.assertIn((own_console, "OnActivate"), regs)
            self.assertIn((port_console, "OnActivate"), regs)
            self.assertTrue(any("pipboy activator registered ref=" in m and "pos=-55.0488 -0.9224 0.7759" in m for m in logs), logs)
            self.assertTrue(any("console activator registered ref=" in m and "pos=-54.3644 -1.8147 1.7541" in m for m in logs), logs)
            self.assertTrue(any("console port activator registered ref=" in m for m in logs), logs)

            # First-person E on PipboyCorpseRef routes to HandlePipboyPickup
            ns["OnActivate"](pipboy_ref, player)
            self.assertEqual(pipboy_pickups, [player])

            # First-person E on EITHER own_console (0A000819) OR port_console (02001319) opens cog door, advances to stage 30,
            # and shows V4 catwalk hint strictly once even when double-tapped during Utility.Wait(2.0) and after stage 30!
            ns["OnActivate"](sender, player)
            ns["OnActivate"](sender, player)
            self.assertTrue(double_tapped[0])
            self.assertEqual(cur_stage[0], 30)
            self.assertEqual(stages, [(30, "vault_console")])
            self.assertEqual(notifs, ["Vault door open - follow the catwalk to the elevator platform."])
            self.assertEqual(logs.count("catwalk hint shown"), 1)
            if trigger_via_port_console:
                self.assertTrue(any("console port ref activated ref=" in m for m in logs), logs)

    def test_w1_known_issues_doc_exists_covers_all_breaks_and_stays_public_clean(self) -> None:
        ki_path = ROOT / "docs" / "known-issues.md"
        self.assertTrue(ki_path.is_file(), "docs/known-issues.md is missing")
        txt = ki_path.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", txt), "drive path leaked in docs/known-issues.md")
        self.assertIsNone(re.search(r"/(?:users|home)/", txt, re.I), "private user path leaked in docs/known-issues.md")

        for required_entry in (
            "T1",
            "FO4SFRouteLoot.esm",
            "0x41efd6",
            "T2",
            "MapBlockStarMap=0",
            "0x2540dc6",
            "FO4SFBridge.esm",
            "T3",
            "FO4SF_StartRoomCell",
            "FadeHold = false",
            "T4",
            "21 Nov",
            "U1",
            "0x00080F",
            "0A00080F.Activate 14",
            "<XX>00080F.Activate 14",
            "T5",
            "T6",
            "0x2814",
            "T7",
            "Arm=0",
            "BootOnFirstOpen=0",
            "Track 2",
            "UNPROVEN IN GAME",
        ):
            self.assertIn(required_entry, txt, f"docs/known-issues.md missing {required_entry!r}")


if __name__ == "__main__":
    unittest.main()
