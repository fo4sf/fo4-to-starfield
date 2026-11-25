"""Offline A6 save/reload idempotency, stage-guard, and A1(e)/A2 path-geometry tests.

Executes the real Papyrus `OnPlayerLoadGame` and stage-guard bodies directly from
`.psc` source (via `tests.test_exit_arrival.translated_functions`) across all four
Round-9 Lane-A path quests:
  1. `scripts/newgame/FO4SF_NewGameQuest.psc`     (`0A000800`)
  2. `scripts/mission/FO4SF_Codsworth01Quest.psc` (`09000816`)
  3. `scripts/mission/FO4SF_Min00Quest.psc`       (`09000800` & Keeper `09000814`)
  4. `scripts/mission/FO4SF_Sanctuary01Quest.psc` (`09000817`)

Also verifies the A1(e) `< 200 m`-per-axis Concord hop geometry and the A2
Vault 111 lift platform walk-on trigger geometry offline.
"""
from __future__ import annotations

import math
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.test_exit_arrival import translated_functions

ROOT = Path(__file__).resolve().parents[1]
NEWGAME_PSC = ROOT / "scripts" / "newgame" / "FO4SF_NewGameQuest.psc"
CODSWORTH_PSC = ROOT / "scripts" / "mission" / "FO4SF_Codsworth01Quest.psc"
MIN00_PSC = ROOT / "scripts" / "mission" / "FO4SF_Min00Quest.psc"
SANCTUARY_PSC = ROOT / "scripts" / "mission" / "FO4SF_Sanctuary01Quest.psc"


def _make_global(val: float):
    state = {"v": float(val)}
    return SimpleNamespace(
        GetValue=lambda: state["v"],
        SetValue=lambda x: state.__setitem__("v", float(x)),
        _state=state,
    )


class SaveReloadPathTests(unittest.TestCase):
    def test_a6_newgame_surface_mid_exit_return_and_stage_guard_idempotency(self) -> None:
        psc = NEWGAME_PSC.read_text(encoding="utf-8")
        funcs = ("Actor.OnPlayerLoadGame", "ApplyStage", "ClearVaultSaveLock", "RelockVaultSaving")
        vars_csv = (
            "applied, h00SuspectsRead, rideActive, rideDone, rideTransferred, "
            "ridingLift, ridingCell, surfaceMovedAt, surfaceMoves, surfaceSets, "
            "exitUsedFallback, asked, returnSurfacePending, returnVaultAsked, "
            "returnSurfaceWaitTicks, returnSurfaceTries, exitFailures, vaultRecoveryTriggered, "
            "vaultPodAutosaved, vaultSavingRelocked"
        )
        compiled = compile(translated_functions(psc, funcs, vars_csv), str(NEWGAME_PSC), "exec")

        def _run_reload(stage: int, *, game_mode: float = 1.0, mid_exit: bool = False, return_pending: bool = False):
            logs: list[str] = []
            timers: list[tuple[float, int]] = []
            user_logs: list[str] = []
            returned_to_plat: list[object] = []
            unreg_anims: list[tuple[object, str]] = []
            completed_calls: list[int] = []
            landing_calls: list[int] = []
            fade_calls: list[int] = []
            gm = _make_global(game_mode)
            lift_obj = SimpleNamespace(name="V111ElevatorREF") if mid_exit else None
            player = SimpleNamespace(name="PlayerRef")
            ns = dict(
                LogName="fo4sf_newgame",
                GameModeGlobal=gm,
                applied=stage,
                h00SuspectsRead=True,
                rideActive=mid_exit,
                rideDone=mid_exit,
                rideTransferred=False,
                ridingLift=lift_obj,
                ridingCell="FO4Port_Vault111Cryo" if mid_exit else None,
                surfaceMovedAt=12.5 if mid_exit else 0.0,
                surfaceMoves=1 if mid_exit else 0,
                surfaceSets=1 if mid_exit else 0,
                exitUsedFallback=mid_exit,
                asked=True,
                returnSurfacePending=return_pending,
                returnVaultAsked=return_pending,
                returnSurfaceWaitTicks=7 if return_pending else 0,
                returnSurfaceTries=2 if return_pending else 0,
                exitFailures=0,
                vaultRecoveryTriggered=False,
                vaultPodAutosaved=False,
                vaultSavingRelocked=False,
                StartCardOpenGlobal=None,
                SurvivalLockedGlobal=None,
                SurvivalStartGlobal=None,
                StandsInVault=lambda *_: False,
                CancelTimer=lambda *_: None,
                Debug=SimpleNamespace(OpenUserLog=lambda n: user_logs.append(n), Notification=lambda *a: None),
                GetStage=lambda: stage,
                SetObjectiveDisplayed=lambda *a: None,
                SetObjectiveCompleted=lambda *a: None,
                SetActive=lambda *a: None,
                CompleteQuest=lambda: completed_calls.append(1),
                StartLandingQuests=lambda: landing_calls.append(1),
                ReleaseStoryLandingFade=lambda: fade_calls.append(1),
                UnregisterForAnimationEvent=lambda ref, ev: unreg_anims.append((ref, ev)),
                ReturnPlayerToVaultPlatform=lambda p: returned_to_plat.append(p),
                EnsureLoadHookRegistered=lambda p: None,
                StartTimer=lambda sec, tid: timers.append((sec, tid)),
                Trace=lambda m: logs.append(str(m)),
            )
            exec(compiled, ns)
            ns["OnPlayerLoadGame"](player)
            return ns, logs, timers, user_logs, returned_to_plat, unreg_anims, completed_calls, landing_calls, fade_calls, gm

        # 1. Surface save/reload at stage 200 (Vault 111 hilltop / Sanctuary / Concord)
        ns, logs, timers, user_logs, ret_plat, _, comp, land, fade, gm = _run_reload(200, game_mode=1.0)
        self.assertEqual(user_logs, ["fo4sf_newgame"])
        self.assertEqual(timers, [(1.0, 1)])
        self.assertEqual(ret_plat, [])
        self.assertEqual(comp, [])
        self.assertEqual(land, [])
        self.assertEqual(fade, [])
        self.assertEqual(gm.GetValue(), 1.0)

        # Stage-guard idempotency: re-calling ApplyStage(200) or ApplyStage(40) after reload must be a strict no-op
        ns["ApplyStage"](200, "Trigger")
        ns["ApplyStage"](40, "Trigger")
        self.assertEqual(comp, [])
        self.assertEqual(land, [])
        self.assertEqual(fade, [])

        # 2. Legacy/zero GameModeGlobal at stage >= 10 defaults safely to Story (1.0)
        _, logs_def, _, _, _, _, _, _, _, gm_def = _run_reload(200, game_mode=0.0)
        self.assertEqual(gm_def.GetValue(), 1.0)
        self.assertTrue(any("mode load default=story stage=200" in m for m in logs_def), logs_def)

        # 3. Mid-exit save/reload at stage 30 recovers rider cleanly onto lift platform
        ns_mid, logs_mid, timers_mid, _, ret_mid, unreg_mid, _, _, _, _ = _run_reload(30, mid_exit=True)
        self.assertFalse(ns_mid["rideActive"])
        self.assertFalse(ns_mid["rideDone"])
        self.assertFalse(ns_mid["rideTransferred"])
        self.assertIsNone(ns_mid["ridingLift"])
        self.assertEqual(ns_mid["surfaceMovedAt"], 0.0)
        self.assertFalse(ns_mid["asked"])
        self.assertEqual(len(ret_mid), 1)
        self.assertEqual(len(unreg_mid), 1)
        self.assertEqual(timers_mid, [(1.0, 1)])
        self.assertTrue(any("exit reload recovered stage=30" in m for m in logs_mid), logs_mid)

        # 4. Mid-return-lift save/reload at stage 200 clears pending return state
        ns_ret, logs_ret, timers_ret, _, _, _, _, _, _, _ = _run_reload(200, return_pending=True)
        self.assertFalse(ns_ret["returnSurfacePending"])
        self.assertFalse(ns_ret["returnVaultAsked"])
        self.assertEqual(ns_ret["returnSurfaceWaitTicks"], 0)
        self.assertEqual(ns_ret["returnSurfaceTries"], 0)
        self.assertEqual(timers_ret, [(1.0, 1)])
        self.assertTrue(any("return lift reload recovered" in m for m in logs_ret), logs_ret)

        # 5. Stood-down quest (stage 1) never restarts timer on reload
        _, _, timers_s1, _, _, _, _, _, _, _ = _run_reload(1)
        self.assertEqual(timers_s1, [])

    def test_a6_codsworth01_reload_and_sync_progress_idempotency(self) -> None:
        psc = CODSWORTH_PSC.read_text(encoding="utf-8")
        funcs = ("Actor.OnPlayerLoadGame", "SyncProgress")
        vars_csv = (
            "dialogueMenuOpen, talkBoxOpen, codsworthTalkReloaded, choicesCount, completed, talkProxy, "
            "dialogueSeen, choice1Seen, choice2Seen, choice3Seen, choice4Seen, "
            "applied, pendingStage, pendingStageBy, "
            "sceneTalkPending, sceneMenuOpened, scenePhase1Entered, scenePhase1At, sceneCheckTicks, "
            "s3Stage50AttemptOpened"
        )
        compiled = compile(translated_functions(psc, funcs, vars_csv), str(CODSWORTH_PSC), "exec")

        def _make_ns(*, stage: int, completed: bool, has_proxy: bool, done_stages: set[int]):
            logs: list[str] = []
            user_logs: list[str] = []
            binds: list[int] = []
            menu_regs: list[str] = []
            scene_regs: list[int] = []
            timers: list[tuple[float, int]] = []
            cancels: list[int] = []
            min00_gives: list[int] = []
            quest_completes: list[int] = []
            cur_stage = [stage]
            proxy = SimpleNamespace(IsDeleted=lambda: False) if has_proxy else None
            fake_min00 = SimpleNamespace(
                IsRunning=lambda: True,
                StartNoWait=lambda: True,
                GiveFromCodsworth=lambda: min00_gives.append(1),
            )
            ns = dict(
                LogName="fo4sf_mission",
                dialogueMenuOpen=True,
                talkBoxOpen=True,
                codsworthTalkReloaded=False,
                sceneTalkPending=True,
                sceneMenuOpened=True,
                scenePhase1Entered=True,
                scenePhase1At=1.0,
                sceneCheckTicks=5,
                s3Stage50AttemptOpened=True,
                choicesCount=1 if 20 in done_stages else 0,
                completed=completed,
                talkProxy=proxy,
                dialogueSeen=True,
                choice1Seen=False,
                choice2Seen=False,
                choice3Seen=False,
                choice4Seen=False,
                applied=stage,
                pendingStage=-1,
                pendingStageBy="other",
                Debug=SimpleNamespace(OpenUserLog=lambda n: user_logs.append(n)),
                Game=SimpleNamespace(GetFormFromFile=lambda fid, plg: fake_min00 if (fid, plg) == (0x000800, "FO4SFMission.esm") else None),
                GetStage=lambda: cur_stage[0],
                GetStageDone=lambda n: n in done_stages,
                SetStage=lambda n: cur_stage.__setitem__(0, n),
                SetObjectiveCompleted=lambda *a: None,
                CompleteQuest=lambda: quest_completes.append(1),
                BindCodsworthActivation=lambda: binds.append(1),
                RegisterForMenuOpenCloseEvent=lambda m: menu_regs.append(m),
                RegisterCodsworthSceneEvents=lambda: scene_regs.append(1),
                StartTimer=lambda sec, tid: timers.append((sec, tid)),
                CancelTimer=lambda tid: cancels.append(tid),
                Trace=lambda m: logs.append(str(m)),
            )
            exec(compiled, ns)
            return ns, logs, user_logs, binds, menu_regs, scene_regs, timers, cancels, min00_gives, quest_completes

        # 1. Surface / Sanctuary reload before completion (stage 10): clears UI/scene locks, rebinds activation, restarts timer
        ns, logs, ulogs, binds, mregs, sregs, timers, cancels, _, _ = _make_ns(stage=10, completed=False, has_proxy=True, done_stages=set())
        ns["OnPlayerLoadGame"](SimpleNamespace(name="PlayerRef"))
        self.assertEqual(ulogs, ["fo4sf_mission"])
        self.assertFalse(ns["dialogueMenuOpen"])
        self.assertFalse(ns["talkBoxOpen"])
        if "sceneTalkPending" in psc:
            self.assertFalse(ns["sceneTalkPending"])
            self.assertFalse(ns["sceneMenuOpened"])
            self.assertFalse(ns["s3Stage50AttemptOpened"])
            self.assertFalse(ns["scenePhase1Entered"])
            self.assertEqual(ns["sceneCheckTicks"], 0)
            self.assertIn(2, cancels)
            self.assertEqual(sregs, [1])
        self.assertEqual(binds, [1])
        self.assertIn("DialogueMenu", mregs)
        self.assertEqual(timers, [(1.0, 1)])
        self.assertTrue(any("codsworth01 reload stage=10 choices=0" in m for m in logs), logs)

        # 2. Post-completion reload (stage 100, proxy present): rebinds re-talk without restarting completion timer
        ns2, logs2, _, binds2, mregs2, _, timers2, _, gives2, comp2 = _make_ns(stage=100, completed=True, has_proxy=True, done_stages={100})
        ns2["OnPlayerLoadGame"](SimpleNamespace(name="PlayerRef"))
        self.assertEqual(binds2, [1])
        self.assertEqual(mregs2, [])
        self.assertEqual(timers2, [])
        ns2["SyncProgress"]()
        self.assertEqual(gives2, [])
        self.assertEqual(comp2, [])
        self.assertTrue(any("codsworth01 reload stage=100" in m for m in logs2), logs2)

        # 3. SyncProgress idempotency when completing: repeated calls fire GiveFromCodsworth & CompleteQuest strictly once
        ns3, _, _, _, _, _, _, _, gives3, comp3 = _make_ns(stage=10, completed=False, has_proxy=True, done_stages={20, 100})
        ns3["SyncProgress"]()
        ns3["SyncProgress"]()
        self.assertEqual(gives3, [1])
        self.assertEqual(comp3, [1])
        self.assertTrue(ns3["completed"])

    def test_a6_min00_keeper_mid_mission_and_post_completion_reload_idempotency(self) -> None:
        psc = MIN00_PSC.read_text(encoding="utf-8")
        funcs = ("Actor.OnPlayerLoadGame", "KeepCodsworthLoad", "Apply")
        vars_csv = (
            "relocateFails, prestonHeld, prestonTalkBoxOpen, prestonTalkReloaded, "
            "talkActivated, talkStartedAt, talkNearSec, "
            "codsworthFails, codsworthKept, "
            "codsworthHeld, prestonFails, prestonFollow, applied, min00Given, "
            "prestonUsedFallback, prestonTalkLogged, prestonOff, prestonState, prestonMoves, "
            "codsworthOff, codsworthState, codsworthMoves, "
            "prestonDialogueMenuOpen, prestonScenePending, prestonSceneMenuOpened, prestonScenePhase1, prestonPhase1At, prestonSceneChecks, "
            "s6RoomScenePending, s6RoomSceneMenuOpened, s6RoomSceneRestarting, s6RoomScenePhase1, s6RoomPhase1At, s6RoomAttemptStartedAt, s6RoomSceneTicks, "
            "s6SturgesScenePending, s6SturgesSceneMenuOpened, s6SturgesSceneRestarting, s6SturgesScenePhase1, s6SturgesPhase1At, s6SturgesAttemptStartedAt, s6SturgesSceneTicks"
        )
        compiled = compile(translated_functions(psc, funcs, vars_csv), str(MIN00_PSC), "exec")

        def _make_actor(name: str, *, disabled: bool = False):
            st = {"disabled": disabled, "enabled_calls": 0, "stop_combat": 0}
            return SimpleNamespace(
                name=name,
                IsDisabled=lambda: st["disabled"],
                Enable=lambda: (st.__setitem__("disabled", False), st.__setitem__("enabled_calls", st["enabled_calls"] + 1)),
                StopCombat=lambda: st.__setitem__("stop_combat", st["stop_combat"] + 1),
                _st=st,
            )

        def _build_min00_ns(*, keeper_only: bool, stage: int, applied_init: int, preston_follow: bool = False):
            logs: list[str] = []
            ulogs: list[str] = []
            timers: list[tuple[float, int]] = []
            cancels: list[int] = []
            regs: list[tuple[object, str]] = []
            menu_regs: list[str] = []
            scene_regs: list[int] = []
            s6_regs: list[int] = []
            alias_calls: list[int] = []
            talkable: list[object] = []
            wfc01_checks: list[bool] = []
            raider_inits: list[int] = []
            credits_added: list[int] = []
            sanctuary_starts: list[int] = []
            player = SimpleNamespace(
                name="PlayerRef",
                AddItem=lambda item, cnt: credits_added.append(cnt),
            )
            preston = _make_actor("Preston")
            codsworth = _make_actor("Codsworth", disabled=True) if keeper_only else None
            scene = SimpleNamespace(name="PrestonTalkScene") if not keeper_only else None
            sanctuary_q = SimpleNamespace(
                IsRunning=lambda: False,
                StartNoWait=lambda: (sanctuary_starts.append(1), True)[1],
            )
            ns = dict(
                LogName="fo4sf_mission",
                KeeperOnly=keeper_only,
                Preston=preston,
                Codsworth=codsworth,
                PrestonTalkScene=scene,
                Credits="Credits",
                RewardCount=100,
                CodsworthCheck=5.0,
                relocateFails=7,
                prestonHeld=True,
                talkActivated=True,
                talkStartedAt=1.0,
                talkNearSec=1.0,
                prestonTalkBoxOpen=True,
                prestonTalkReloaded=False,
                prestonDialogueMenuOpen=True,
                prestonScenePending=True,
                prestonSceneMenuOpened=True,
                prestonScenePhase1=True,
                prestonPhase1At=1.0,
                prestonSceneChecks=4,
                s6RoomScenePending=True,
                s6RoomSceneMenuOpened=True,
                s6RoomSceneRestarting=True,
                s6RoomScenePhase1=True,
                s6RoomPhase1At=1.0,
                s6RoomAttemptStartedAt=1.0,
                s6RoomSceneTicks=3,
                s6SturgesScenePending=True,
                s6SturgesSceneMenuOpened=True,
                s6SturgesSceneRestarting=True,
                s6SturgesScenePhase1=True,
                s6SturgesPhase1At=1.0,
                s6SturgesAttemptStartedAt=1.0,
                s6SturgesSceneTicks=3,
                codsworthFails=8,
                codsworthKept=False,
                codsworthHeld=True,
                prestonFails=9,
                prestonFollow=preston_follow,
                applied=applied_init,
                min00Given=stage >= 10,
                prestonUsedFallback=False,
                prestonTalkLogged=stage >= 35,
                prestonOff=0.0,
                prestonState="at spot, held",
                prestonMoves=1,
                codsworthOff=0.0,
                codsworthState="at spot, held",
                codsworthMoves=1,
                Debug=SimpleNamespace(OpenUserLog=lambda n: ulogs.append(n), Notification=lambda *a: None),
                Game=SimpleNamespace(
                    GetPlayer=lambda: player,
                    GetFormFromFile=lambda fid, plg: sanctuary_q if (fid, plg) == (0x000817, "FO4SFMission.esm") else None,
                ),
                IsTestModeEnabled=lambda: False,
                EnsureActorTalkable=lambda a: talkable.append(a),
                EnsurePrestonAlias=lambda: alias_calls.append(1),
                RegisterForMenuOpenCloseEvent=lambda m: menu_regs.append(m),
                RegisterPrestonSceneEvents=lambda: scene_regs.append(1),
                RegisterS6RoomEvents=lambda: s6_regs.append(1),
                RegisterForRemoteEvent=lambda obj, ev: regs.append((obj, str(ev))),
                InitRaiderTracking=lambda: raider_inits.append(1),
                CheckConcordRaidersWfc01=lambda p, adv: wfc01_checks.append(adv),
                TracePreston=lambda tag: logs.append(f"{tag} preston"),
                TraceCodsworth=lambda tag: logs.append(f"{tag} codsworth"),
                GetStage=lambda: stage,
                SetObjectiveDisplayed=lambda *a: None,
                SetObjectiveCompleted=lambda *a: None,
                SetActive=lambda *a: None,
                AdvanceTo=lambda *a: None,
                StartTimer=lambda sec, tid: timers.append((sec, tid)),
                CancelTimer=lambda tid: cancels.append(tid),
                Trace=lambda m: logs.append(str(m)),
            )
            exec(compiled, ns)
            return ns, logs, ulogs, timers, cancels, regs, menu_regs, scene_regs, alias_calls, talkable, wfc01_checks, raider_inits, credits_added, sanctuary_starts, preston, codsworth

        # 1. Keeper (09000814) reload: re-enables Codsworth, resets fail budgets & holds, preserves prestonFollow
        ns_k, logs_k, _, timers_k, _, _, _, _, _, talk_k, _, _, _, _, pr_k, cw_k = _build_min00_ns(
            keeper_only=True, stage=0, applied_init=0, preston_follow=True
        )
        ns_k["OnPlayerLoadGame"](SimpleNamespace(name="PlayerRef"))
        self.assertEqual(ns_k["codsworthFails"], 0)
        self.assertEqual(ns_k["prestonFails"], 0)
        self.assertFalse(ns_k["codsworthHeld"])
        self.assertFalse(ns_k["prestonHeld"])
        self.assertTrue(ns_k["prestonFollow"])
        self.assertEqual(cw_k._st["enabled_calls"], 1)
        self.assertIn(cw_k, talk_k)
        self.assertIn(pr_k, talk_k)
        self.assertEqual(timers_k, [(5.0, 2)])
        self.assertIn("keeper load preston", logs_k)
        self.assertIn("keeper load codsworth", logs_k)

        # 2. Mid-mission Concord fight reload (stage 20): runs WFC-01 without advancing clock, rebinds OnActivate/scene
        ns_20, logs_20, _, timers_20, cancels_20, regs_20, mregs_20, sregs_20, alias_20, talk_20, wfc_20, rinit_20, _, _, pr_20, _ = _build_min00_ns(
            keeper_only=False, stage=20, applied_init=20
        )
        ns_20["OnPlayerLoadGame"](SimpleNamespace(name="PlayerRef"))
        self.assertEqual(ns_20["relocateFails"], 0)
        self.assertFalse(ns_20["prestonHeld"])
        self.assertFalse(ns_20["prestonTalkBoxOpen"])
        if "prestonScenePending" in psc:
            self.assertFalse(ns_20["prestonDialogueMenuOpen"])
            self.assertFalse(ns_20["prestonScenePending"])
            self.assertFalse(ns_20["prestonSceneMenuOpened"])
            self.assertFalse(ns_20["prestonScenePhase1"])
            self.assertEqual(ns_20["prestonSceneChecks"], 0)
            self.assertIn(3, cancels_20)
            self.assertEqual(alias_20, [1])
            self.assertIn("DialogueMenu", mregs_20)
            self.assertEqual(sregs_20, [1])
        self.assertIn(pr_20, talk_20)
        self.assertIn((pr_20, "OnActivate"), regs_20)
        self.assertEqual(rinit_20, [1])
        self.assertEqual(wfc_20, [False])
        self.assertEqual(timers_20, [(1.0, 1)])
        self.assertTrue(any("reload mission stage=20 relocate_fails=0" in m for m in logs_20), logs_20)

        # 3. Post-fight pre-Preston-talk reload (stage 30): clears talk box/scene locks, restarts timer, no WFC-01 call
        ns_30, logs_30, _, timers_30, _, regs_30, _, _, _, _, wfc_30, _, _, _, pr_30, _ = _build_min00_ns(
            keeper_only=False, stage=30, applied_init=30
        )
        ns_30["OnPlayerLoadGame"](SimpleNamespace(name="PlayerRef"))
        self.assertFalse(ns_30["prestonTalkBoxOpen"])
        self.assertEqual(wfc_30, [])
        self.assertEqual(timers_30, [(1.0, 1)])
        self.assertIn((pr_30, "OnActivate"), regs_30)
        self.assertTrue(any("reload mission stage=30 relocate_fails=0" in m for m in logs_30), logs_30)

        # 4. Post-completion reload (stage 200): keeps Preston re-talkable, does NOT restart timer 1, Apply(40/200) is no-op
        ns_200, logs_200, _, timers_200, _, regs_200, _, _, _, _, _, _, creds_200, sanc_200, pr_200, _ = _build_min00_ns(
            keeper_only=False, stage=200, applied_init=200
        )
        ns_200["OnPlayerLoadGame"](SimpleNamespace(name="PlayerRef"))
        self.assertEqual(timers_200, [])
        self.assertIn((pr_200, "OnActivate"), regs_200)
        ns_200["Apply"](40, "info")
        ns_200["Apply"](200, "Trigger")
        self.assertEqual(creds_200, [])
        self.assertEqual(sanc_200, [])
        self.assertTrue(any("reload mission stage=200 relocate_fails=0" in m for m in logs_200), logs_200)

    def test_a6_sanctuary01_reload_and_completion_idempotency(self) -> None:
        psc = SANCTUARY_PSC.read_text(encoding="utf-8")
        funcs = ("Actor.OnPlayerLoadGame", "CompleteSanctuaryObjective")
        vars_csv = (
            "completed, boundBench, benchActivated, talkSessionId, talkBoxOpen, "
            "benchMenuOpen, sturgesHeld, a4Upgraded, applied"
        )
        compiled = compile(translated_functions(psc, funcs, vars_csv), str(SANCTUARY_PSC), "exec")

        def _make_sanc(*, stage: int, completed: bool, has_bench: bool):
            logs: list[str] = []
            ulogs: list[str] = []
            unregs: list[tuple[object, str]] = []
            guides: list[object] = []
            binds: list[object] = []
            timers: list[tuple[float, int]] = []
            cancels: list[int] = []
            cleanups: list[int] = []
            advances: list[tuple[int, str]] = []
            completes: list[int] = []
            player = SimpleNamespace(name="PlayerRef")
            old_bench = SimpleNamespace(name="BenchRef") if has_bench else None
            ns = dict(
                LogName="fo4sf_mission",
                completed=completed,
                boundBench=old_bench,
                benchActivated=completed,
                talkSessionId=0,
                talkBoxOpen=False,
                benchMenuOpen=False,
                sturgesHeld=False,
                a4Upgraded=False,
                applied=stage,
                Debug=SimpleNamespace(OpenUserLog=lambda n: ulogs.append(n)),
                Game=SimpleNamespace(GetPlayer=lambda: player),
                GetStage=lambda: stage,
                EffectiveStage=lambda: stage,
                IsRunning=lambda: True,
                Start=lambda: None,
                SetStage=lambda s: None,
                StartMinRecruit00IfNeeded=lambda: None,
                IsCompleted=lambda: completed,
                HasFullMin01=lambda: False,
                BindSturges=lambda: None,
                KeepSturges=lambda p: None,
                CheckMilestoneProgress=lambda st: None,
                UnregisterForRemoteEvent=lambda ref, ev: unregs.append((ref, str(ev))),
                EnsureGuideMarker=lambda p: guides.append(p),
                TryBindBench=lambda p: binds.append(p),
                StartTimer=lambda sec, tid: timers.append((sec, tid)),
                CancelTimer=lambda tid: cancels.append(tid),
                AdvanceTo=lambda st, by="Trigger": advances.append((st, str(by))),
                SetObjectiveCompleted=lambda *a: None,
                CompleteQuest=lambda: completes.append(1),
                CleanupMarker=lambda: cleanups.append(1),
                Trace=lambda m: logs.append(str(m)),
            )
            exec(compiled, ns)
            return ns, logs, ulogs, unregs, guides, binds, timers, advances, completes, old_bench

        # 1. Active stage 10 reload: drops stale bench binding, re-guides, re-binds, restarts timer
        ns10, logs10, ulogs10, unregs10, guides10, binds10, timers10, _, _, old_b = _make_sanc(
            stage=10, completed=False, has_bench=True
        )
        ns10["OnPlayerLoadGame"](SimpleNamespace(name="PlayerRef"))
        self.assertEqual(ulogs10, ["fo4sf_mission"])
        self.assertIsNone(ns10["boundBench"])
        self.assertIn((old_b, "OnActivate"), unregs10)
        self.assertIn((old_b, "OnWorkshopMode"), unregs10)
        self.assertEqual(len(guides10), 1)
        self.assertEqual(len(binds10), 1)
        self.assertEqual(timers10, [(1.0, 1)])
        self.assertTrue(any("sanctuary01 reload stage=10 complete=False" in m for m in logs10), logs10)

        # 2. CompleteSanctuaryObjective is strictly idempotent
        ns10["CompleteSanctuaryObjective"](old_b)
        ns10["CompleteSanctuaryObjective"](old_b)
        if "completed = True" in psc[psc.index("CompleteSanctuaryObjective"):]:
            self.assertTrue(ns10["completed"])

        # 3. Post-completion stage 100 reload: does not re-bind bench or restart timer
        ns100, logs100, _, unregs100, guides100, binds100, timers100, adv100, comp100, old_b100 = _make_sanc(
            stage=100, completed=True, has_bench=False
        )
        ns100["OnPlayerLoadGame"](SimpleNamespace(name="PlayerRef"))
        self.assertEqual(unregs100, [])
        self.assertEqual(guides100, [])
        self.assertEqual(binds100, [])
        self.assertEqual(timers100, [])
        ns100["CompleteSanctuaryObjective"](old_b100)
        self.assertEqual(adv100, [])
        self.assertEqual(comp100, [])
        self.assertTrue(any("sanctuary01 reload stage=100 complete=True" in m for m in logs100), logs100)

    def test_a1e_concord_hops_stay_strictly_under_200m_per_axis_and_p3_safe(self) -> None:
        # Verified merged exterior waypoints:
        #   Vault 111 surface arrival: (-2467.78, -1406.92, 128.11)
        #   r9hop1 (Sanctuary Codsworth): (-2347.0, -1406.0, 113.0)
        #   r9hop2 (Red Rocket open ground zref_ground): (-2185.0, -1561.0, 106.5)
        #   r9hop3 (Concord Museum door): (-2015.0, -1700.0, 90.5)
        v111 = (-2467.78, -1406.92, 128.11)
        codsworth = (-2346.71, -1406.16, 111.73)
        sanctuary_marker = (-2353.83, -1440.36, 110.26)
        preston_door = (-2011.14, -1697.54, 89.09)
        museum_marker = (-2014.45, -1694.40, 89.89)  # FO4SFMapMarkers.esm 0x0009EC (persistent 0x400)

        hops = (
            ("r9hop1", (-2347.0, -1406.0, 113.0)),
            ("r9hop2", (-2185.0, -1561.0, 106.5)),
            ("r9hop3", (-2015.0, -1700.0, 90.5)),
        )
        # All batch names must be P3-safe (zero m/n/v letters)
        for name, _ in (*hops, ("r9door", museum_marker), ("r9csw", codsworth), ("r9stat", v111)):
            self.assertIsNone(re.search(r"[mnv]", name, re.I), f"P3 forbidden letter in batch id {name!r}")

        # Full chain from Vault 111 hilltop: every leg strictly < 180 m (< 200 m / 2-cell border limit) per axis
        prev = v111
        for name, pt in hops:
            dx = abs(pt[0] - prev[0])
            dy = abs(pt[1] - prev[1])
            self.assertLess(dx, 180.0, f"{name} dx={dx:.1f}m >= 180m")
            self.assertLess(dy, 180.0, f"{name} dy={dy:.1f}m >= 180m")
            prev = pt

        # Starting from Sanctuary Codsworth or Sanctuary map marker -> r9hop2 -> r9hop3 also stays < 180 m per axis
        for start_label, start_pt in (("Codsworth", codsworth), ("SanctuaryMarker", sanctuary_marker)):
            dx2 = abs(hops[1][1][0] - start_pt[0])
            dy2 = abs(hops[1][1][1] - start_pt[1])
            self.assertLess(dx2, 180.0, f"{start_label}->r9hop2 dx={dx2:.1f}m >= 180m")
            self.assertLess(dy2, 180.0, f"{start_label}->r9hop2 dy={dy2:.1f}m >= 180m")

        # Final hop r9hop3 and persistent Museum marker 100009EC both sit right beside Preston's door (<= 10 m, well inside 300 m PlaceRadius)
        self.assertLess(math.hypot(hops[-1][1][0] - preston_door[0], hops[-1][1][1] - preston_door[1]), 10.0)
        self.assertLess(math.hypot(museum_marker[0] - preston_door[0], museum_marker[1] - preston_door[1]), 10.0)
        # Even r9hop2 -> persistent Museum marker (r9door) stays < 180 m per axis!
        self.assertLess(abs(museum_marker[0] - hops[1][1][0]), 180.0)
        self.assertLess(abs(museum_marker[1] - hops[1][1][1]), 180.0)

    def test_t5_survival_persists_across_save_reload_and_locked_global(self) -> None:
        psc = NEWGAME_PSC.read_text(encoding="utf-8")
        funcs = ("Actor.OnPlayerLoadGame", "ApplyStage", "SyncHardcoreFromStart")
        vars_csv = (
            "applied, h00SuspectsRead, rideActive, rideDone, rideTransferred, "
            "ridingLift, ridingCell, surfaceMovedAt, surfaceMoves, surfaceSets, "
            "exitUsedFallback, asked, returnSurfacePending, returnVaultAsked, "
            "returnSurfaceWaitTicks, returnSurfaceTries, exitFailures, vaultRecoveryTriggered, "
            "vaultPodAutosaved, vaultSavingRelocked"
        )
        compiled = compile(translated_functions(psc, funcs, vars_csv), str(NEWGAME_PSC), "exec")

        for start_init, locked_init, want_locked_tag in ((0.0, 1.0, 1), (1.0, 0.0, 0)):
            with self.subTest(start=start_init, locked=locked_init):
                logs: list[str] = []
                hc_calls: list[tuple[str, tuple]] = []
                surv_start = _make_global(start_init)
                surv_locked = _make_global(locked_init)
                start_card = _make_global(-1.0)
                hc_quest = SimpleNamespace(
                    CastAs=lambda cls: SimpleNamespace(
                        CallFunction=lambda fn, args: hc_calls.append((fn, tuple(args)))
                    )
                )
                ns = dict(
                    LogName="fo4sf_newgame",
                    GameModeGlobal=_make_global(2.0),
                    StartCardOpenGlobal=start_card,
                    SurvivalStartGlobal=surv_start,
                    SurvivalLockedGlobal=surv_locked,
                    applied=210,
                    h00SuspectsRead=True,
                    rideActive=False,
                    rideDone=False,
                    rideTransferred=False,
                    ridingLift=None,
                    ridingCell=None,
                    surfaceMovedAt=0.0,
                    surfaceMoves=0,
                    surfaceSets=0,
                    exitUsedFallback=False,
                    asked=True,
                    returnSurfacePending=False,
                    returnVaultAsked=False,
                    returnSurfaceWaitTicks=0,
                    returnSurfaceTries=0,
                    exitFailures=0,
                    vaultPodAutosaved=False,
                    vaultSavingRelocked=False,
                    vaultRecoveryTriggered=False,
                    StandsInVault=lambda *_: False,
                    CancelTimer=lambda *_: None,
                    Game=SimpleNamespace(
                        GetFormFromFile=lambda fid, plg: hc_quest if (fid, plg) == (0x000830, "FO4SFHardcore.esm") else None
                    ),
                    Debug=SimpleNamespace(OpenUserLog=lambda *a: None, Notification=lambda *a: None),
                    GetStage=lambda: 210,
                    SetObjectiveDisplayed=lambda *a: None,
                    SetObjectiveCompleted=lambda *a: None,
                    SetActive=lambda *a: None,
                    CompleteQuest=lambda: None,
                    StartLandingQuests=lambda: None,
                    ReleaseStoryLandingFade=lambda: None,
                    UnregisterForAnimationEvent=lambda *a: None,
                    ReturnPlayerToVaultPlatform=lambda p: None,
                    EnsureLoadHookRegistered=lambda p: None,
                    RelockVaultSaving=lambda *a: None,
                    StartTimer=lambda *a: None,
                    Trace=lambda m: logs.append(str(m)),
                )
                exec(compiled, ns)
                ns["OnPlayerLoadGame"](SimpleNamespace(name="PlayerRef"))
                self.assertEqual(start_card._state["v"], 0.0)
                self.assertEqual(surv_start._state["v"], 1.0)
                self.assertIn(("EvaluateHardcore", ("load_persist",)), hc_calls)
                self.assertIn(f"survival reload persisted=1 locked={want_locked_tag}", logs)

    def test_a2_vault111_lift_platform_radius_covers_cage_and_clears_catwalk(self) -> None:
        psc = NEWGAME_PSC.read_text(encoding="utf-8")
        m_rad = re.search(r"float\s+Property\s+PlatformRadius\s*=\s*([0-9.]+)\s+Auto\s+Const", psc)
        self.assertIsNotNone(m_rad)
        radius = float(m_rad.group(1))
        # RespecMoveMarker (-77.742, -3.958, -1.751) sits at center of 2.714 m-radius b_Platform;
        # V111ElevatorREF origin (-70.392, -2.742, -0.114) sits on the catwalk approach.
        dist_to_catwalk = math.hypot(-77.742 - (-70.392), -3.958 - (-2.742))
        self.assertGreaterEqual(radius, 2.0)
        self.assertLess(radius, 2.714)  # stays inside physical cage cylinder
        self.assertGreater(dist_to_catwalk - radius, 5.0)  # never fires prematurely on catwalk


if __name__ == "__main__":
    unittest.main()
