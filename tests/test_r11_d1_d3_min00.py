"""Round 11 (R11-W1) unit & binary ESM tests for:
- D1: Codsworth choice-list camera (FO4SF_CodsworthRace standing dialogue framing + Game.StopDialogueCamera on Phase >= 2),
- D3: Concord raider deterministic AmmoShotshell=60 + balanced Eon (10 dmg) / Ammo777mm x36 stand-in fight,
- D5 Part 3: Explicit ENAM (Flags=0, DoNotGrayOut clear) & INAM (SubtitlePriority=Low) on Preston & Codsworth choice INFOs,
- A2.2: FO4SF_Min00Quest.psc fallback vs late native greeting mutual exclusion (never both DialogueMenu & MessageBox),
- A2.4: KeeperOnly Timer 2 keeps CheckA4/A7/A7cdProximityStarts alive after both placement budgets reach 10,
- A2.5: EnsureSafeCodsworthCameraDistance ground-Z & Sanctuary Player House wall clearance.

Runs pure-stdlib cleanly under `python -I` from any working directory; set FO4SF_DOTNET_TESTS=1 to also verify
generated binary FO4SFMission.esm records via `dotnet run --project dotnet/Mission -- selftest`.
"""
import math
import os
import re
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
MISSION_CS = ROOT / "dotnet" / "Mission" / "Program.cs"
MIN00_PSC = ROOT / "scripts" / "mission" / "FO4SF_Min00Quest.psc"
CODS_PSC = ROOT / "scripts" / "mission" / "FO4SF_Codsworth01Quest.psc"
DOC_MD = ROOT / "docs" / "quests" / "r11-d1-d3-dialogue-camera-and-ammo.md"


class _PStr(str):
    def __add__(self, other):
        return _PStr(super().__add__(str(other)))

    def __radd__(self, other):
        return _PStr(str(other) + str(self))


class _PArray(list):
    @property
    def Length(self):
        return len(self)


def _extract_block(src, name):
    m = re.search(
        rf"(?m)^(?:(?:int|bool|float|string|Actor|Message|Scene|Activator|WorldSpace|Weapon|Ammo)\s+)?"
        rf"(?:Function|Event)\s+{re.escape(name)}\s*\(([^)]*)\)(.*?)^End(?:Function|Event)",
        src,
        re.S,
    )
    if not m:
        raise AssertionError(f"Could not find Papyrus block {name!r}")
    return m.group(1), m.group(2)


def _translate_psc(src, names, global_vars=()):
    out = ["from types import SimpleNamespace"]
    for full_name in names:
        params_raw, body = _extract_block(src, full_name)
        body = re.sub(r"\{.*?\}", "", body, flags=re.S)
        py_name = full_name.split(".")[-1]
        params = []
        for p in (x.strip() for x in params_raw.split(",") if x.strip()):
            toks = p.split("=")[0].split()
            params.append(toks[-1])
        out.append(f"def {py_name}({', '.join(params)}):")
        if global_vars:
            out.append("    global " + ", ".join(global_vars))
        depth = 1
        for raw_line in body.splitlines():
            line = re.sub(r'("(?:[^"\\]|\\.)*")|;.*', lambda m: m.group(1) or "", raw_line).strip()
            if not line or line.startswith("{") or line.endswith("}"):
                continue
            if line in ("endif", "endwhile"):
                depth -= 1
                continue
            if line.startswith(("elseif ", "else")):
                depth -= 1
            if "Trace(" in line:
                line = re.sub(r'"([^"\\]*(?:\\.[^"\\]*)*)"', r'_PStr("\1")', line)
            line = re.sub(r"^int\s+(\w+)\s*=\s*(.+)", r"\1 = int(\2)", line)
            line = re.sub(
                r"^(?:bool|float|string|Actor|ActorValue|Activator|Message|ObjectReference|Quest|GlobalVariable|Scene|ReferenceAlias|WorldSpace|Weapon|Ammo|FO4SF_\w+)\s+(\w+)\s*=",
                r"\1 =",
                line,
            )
            line = re.sub(
                r"\s+as\s+(?:Actor|ActorValue|Activator|Message|ObjectReference|Quest|GlobalVariable|Scene|ReferenceAlias|WorldSpace|Weapon|Ammo|FO4SF_\w+)\b",
                "",
                line,
            )
            line = re.sub(r"([\w.\[\]()]+)\s+as\s+int\b", r"int(\1)", line)
            parts = re.split(r'("(?:[^"\\]|\\.)*")', line)
            for idx in range(0, len(parts), 2):
                seg = re.sub(r"\btrue\b", "True", parts[idx], flags=re.I)
                seg = re.sub(r"\bfalse\b", "False", seg, flags=re.I)
                parts[idx] = re.sub(r"!(?!=)", "not ", seg).replace("&&", "and").replace("||", "or")
            line = "".join(parts)
            if line.startswith("elseif "):
                line = "elif " + line[7:]
            if line.startswith(("if ", "elif ", "while ")) or line == "else":
                out.append("    " * depth + line + ":")
                depth += 1
            else:
                out.append("    " * depth + line)
        if len(out) == 2 or out[-1].endswith(":"):
            out.append("    " * depth + "pass")
    return "\n".join(out)


def _iter_esm_records(data, sigs=None):
    def walk(p, e):
        while p + 24 <= e:
            sig = data[p:p + 4]
            sz = struct.unpack_from("<I", data, p + 4)[0]
            if sig == b"GRUP":
                yield from walk(p + 24, p + sz)
                p += sz
            else:
                flags, fid = struct.unpack_from("<II", data, p + 8)
                body = data[p + 24:p + 24 + sz]
                if sigs is None or sig in sigs:
                    if flags & 0x40000:
                        body = zlib.decompress(body[4:])
                    yield sig, fid, flags, body
                p += 24 + sz
    yield from walk(0, len(data))


def _iter_subrecords(body):
    p, e = 0, len(body)
    big = None
    while p + 6 <= e:
        tag = body[p:p + 4]
        ln = struct.unpack_from("<H", body, p + 4)[0]
        if tag == b"XXXX":
            big = struct.unpack_from("<I", body, p + 6)[0]
            p += 6 + ln
            continue
        if big is not None:
            ln = big
            big = None
        yield tag, body[p + 6:p + 6 + ln]
        p += 6 + ln


class R11W1Tests(unittest.TestCase):
    def test_d1_codsworth_race_metadata_and_phase2_stop_dialogue_camera(self):
        """D1: FO4SF_CodsworthRace upgrades away from MiniBotA Size.Small/DialogueMiniBot framing, and
        FO4SF_Codsworth01Quest.OnPhaseBegin stops Starfield's low C_Chassis dialogue camera on phase >= 2."""
        cs = MISSION_CS.read_text(encoding="utf-8")
        c_psc = CODS_PSC.read_text(encoding="utf-8")

        self.assertIn("codsRace.Size = SF.Size.Medium;", cs)
        self.assertIn("codsRace.DialogueQuest.Clear();", cs)
        self.assertIn("SF.Race.Flag.HeadAxisBit0", cs)
        self.assertIn("0x0080000000000000UL", cs)
        self.assertIn("SfModelARaceId = 0x005629", cs)
        self.assertIn("Game.StopDialogueCamera(False, True)", c_psc)

        logs = []
        stop_cam_calls = []
        timers = []
        cancelled = []
        scene = SimpleNamespace(IsPlaying=lambda: True)
        ns = {
            "_PStr": _PStr,
            "Trace": logs.append,
            "CodsworthScene": scene,
            "SceneOpenCheckSeconds": 1.5,
            "sceneTalkPending": True,
            "sceneMenuOpened": False,
            "dialogueMenuOpen": False,
            "scenePhase1Entered": False,
            "scenePhase1At": 0.0,
            "applied": 10,
            "GetStage": lambda: 10,
            "StartTimer": lambda s, tid: timers.append((float(s), int(tid))),
            "CancelTimer": lambda tid: cancelled.append(int(tid)),
            "Utility": SimpleNamespace(GetCurrentRealTime=lambda: 122.4),
            "Game": SimpleNamespace(
                GetFormFromFile=lambda *_: scene,
                StopDialogueCamera=lambda resume=False, to1p=False: stop_cam_calls.append((bool(resume), bool(to1p))),
            ),
        }
        code = _translate_psc(
            c_psc,
            ("EffectiveStage", "ResolveCodsworthScene", "Scene.OnPhaseBegin"),
            ("sceneTalkPending", "sceneMenuOpened", "dialogueMenuOpen", "scenePhase1Entered", "scenePhase1At", "applied"),
        )
        exec(compile(code, "FO4SF_Codsworth01Quest.psc", "exec"), ns)

        # Phase 1 (greeting): resets 1.5 s timer, does NOT call StopDialogueCamera
        ns["OnPhaseBegin"](scene, 1)
        self.assertEqual(stop_cam_calls, [])
        self.assertEqual(timers, [(1.5, 2)])

        # Phase 2 (TOPLEVELNEST choices) & loop-back Phase 2: stops dialogue camera back to eye-height 1st person
        ns["OnPhaseBegin"](scene, 2)
        ns["OnPhaseBegin"](scene, 2)
        self.assertEqual(stop_cam_calls, [(False, True), (False, True)])
        self.assertEqual(sum(1 for ln in logs if "codsworth talk dialogue_camera stopped phase=2" in ln), 2)

    def test_d3_raider_ammo_deterministic_60_and_balanced_eon_sidearm(self):
        """D3: LL_Ammo_Shotshell spawn rolls (30, 10, 30, 30, 20, plus >60 overflow) all normalize to exact 60,
        then EquipBalancedRaiderSidearm removes Coachman + AmmoShotshell and locks Eon (abPreventRemoval=True) +
        exact 36 Ammo777mm so SelectBestWeapon never reverts to Coachman; RaiderSidearm=None retains Coachman x60."""
        cs = MISSION_CS.read_text(encoding="utf-8")
        m_psc = MIN00_PSC.read_text(encoding="utf-8")
        self.assertIn("SfRaiderSidearmId = 0x0476C4", cs)
        self.assertIn("SfRaiderSidearmAmmoId = 0x04AD3E", cs)
        self.assertIn('Obj("RaiderSidearm", raiderSidearm.FormKey)', cs)
        self.assertIn('Obj("RaiderSidearmAmmo", raiderSidearmAmmo.FormKey)', cs)

        class _Raider:
            def __init__(self, shells, ammo777=0):
                self.inv = {"Coachman": 1, "AmmoShotshell": shells}
                if ammo777:
                    self.inv["Ammo777mm"] = ammo777
                self.equipped = [("Coachman", False)]
                self.unequipped = []
                self.restrained = True
                self.avs = {}
                self.evals = 0

            def IsDead(self): return False
            def SetRestrained(self, v): self.restrained = bool(v)
            def SetValue(self, av, val): self.avs[av] = float(val)
            def GetItemCount(self, item): return self.inv.get(item, 0)
            def AddItem(self, item, cnt, _silent=False): self.inv[item] = self.inv.get(item, 0) + int(cnt)
            def RemoveItem(self, item, cnt, _silent=False): self.inv[item] = max(0, self.inv.get(item, 0) - int(cnt))
            def UnequipItem(self, item, *_): self.unequipped.append(item)
            def EquipItem(self, item, prevent_removal=False, _silent=False): self.equipped.append((item, bool(prevent_removal)))
            def EvaluatePackage(self): self.evals += 1

        # Exact candidate-2g LL_Ammo_Shotshell rolls + an overflow case (85)
        rolls = [30, 10, 30, 30, 20, 85]
        raiders = [_Raider(s, ammo777=(50 if i == 5 else 0)) for i, s in enumerate(rolls)]
        logs = []
        ns = {
            "_PStr": _PStr,
            "Trace": logs.append,
            "RaiderWeapon": "Coachman",
            "RaiderAmmo": "AmmoShotshell",
            "RaiderSidearm": "Eon",
            "RaiderSidearmAmmo": "Ammo777mm",
            "raiderArmed": _PArray([False] * len(raiders)),
            "Game": SimpleNamespace(
                GetAggressionAV=lambda: "Aggression",
                GetConfidenceAV=lambda: "Confidence",
            ),
        }
        code = _translate_psc(m_psc, ("ArmRaiderForCombat", "EquipBalancedRaiderSidearm"), ("raiderArmed",))
        exec(compile(code, "FO4SF_Min00Quest.psc", "exec"), ns)

        for idx, r in enumerate(raiders):
            ns["ArmRaiderForCombat"](r, idx)
            self.assertEqual(r.inv["AmmoShotshell"], 60, f"raider {idx} shell count != 60 after ArmRaiderForCombat")
            ns["EquipBalancedRaiderSidearm"](r, idx)
            self.assertEqual(r.inv["Coachman"], 0, f"raider {idx} Coachman must be removed to prevent AI re-equip")
            self.assertEqual(r.inv["AmmoShotshell"], 0, f"raider {idx} AmmoShotshell must be removed after sidearm swap")
            self.assertEqual(r.inv["Ammo777mm"], 36, f"raider {idx} 7.77mm count != 36")
            self.assertEqual(r.unequipped, ["Coachman"])
            self.assertEqual(r.equipped[-1], ("Eon", True))
            self.assertFalse(r.restrained)
            self.assertEqual(r.avs, {"Aggression": 2.0, "Confidence": 4.0})
            self.assertTrue(ns["raiderArmed"][idx])
            self.assertIn(f"arm raider {idx} ammo=60", logs[-2])
            self.assertIn(f"arm raider {idx} sidearm=eon sidearm_ammo=36", logs[-1])

        # Fallback path when RaiderSidearm is None: retains Coachman (1) + deterministic AmmoShotshell (60)
        fallback_r = _Raider(10)
        ns["RaiderSidearm"] = None
        ns["raiderArmed"].append(False)
        ns["ArmRaiderForCombat"](fallback_r, len(raiders))
        ns["EquipBalancedRaiderSidearm"](fallback_r, len(raiders))
        self.assertEqual(fallback_r.inv["Coachman"], 1)
        self.assertEqual(fallback_r.inv["AmmoShotshell"], 60)
        self.assertEqual(fallback_r.equipped[-1], ("Coachman", False))

    def test_d5_preston_and_codsworth_choice_infos_carry_enam_zero_and_inam_low(self):
        """D5 Part 3: BuildTopScene sets explicit ENAM (Flags=0, ResetHours=0, DoNotGrayOut clear) and
        SubtitlePriority=Low on all greetInfo, pcInfo, and npcInfo records."""
        cs = MISSION_CS.read_text(encoding="utf-8")
        build_scene = cs[cs.index("static SF.Scene BuildTopScene("):cs.index("public sealed record MqVoiceSpec")]
        self.assertIn("Flags = new SF.DialogResponseFlags { Flags = 0, ResetHours = 0f }", build_scene)
        self.assertIn("SubtitlePriority = SF.DialogResponses.SubtitlePriorityLevel.Low", build_scene)
        self.assertNotIn("Flag.DoNotGrayOut", build_scene)
        self.assertIn("R11 D5: Preston choice", cs)
        self.assertIn("Preston choice 0 missing ENAM flags (D5)", cs)
        self.assertIn("Preston choice 0 sets DoNotGrayOut (D5)", cs)

    def test_a2_2_preston_never_coexists_messagebox_and_late_dialoguemenu(self):
        """A2.2: Neither a 1.45 s timeout + late native greeting NOR a concurrent run3 OnActivate overwrite
        can ever allow DialogueMenu and MessageBox to coexist."""
        m_psc = MIN00_PSC.read_text(encoding="utf-8")

        def make_env(msg_clicks=(3,)):
            logs = []
            rt = [343.18]
            stages = {10, 20, 30}
            cur_stage = [30]
            timers = []
            cancelled = []

            class _Scene:
                def __init__(self):
                    self.playing = False
                    self.start_calls = 0
                    self.stop_calls = 0

                def IsPlaying(self): return self.playing
                def Start(self): self.start_calls += 1; self.playing = True; return True
                def ForceStart(self): return self.Start()
                def Stop(self): self.stop_calls += 1; self.playing = False

            scene = _Scene()

            class _Msg:
                def __init__(self):
                    self.clicks = list(msg_clicks)
                    self.shown = 0

                def Show(self):
                    self.shown += 1
                    return self.clicks.pop(0) if self.clicks else 3

            msg = _Msg()
            preston = SimpleNamespace(StopCombat=lambda: None, IgnoreFriendlyHits=lambda *_: None)
            player = SimpleNamespace(AddItem=mock.MagicMock())
            sanctuary_q = SimpleNamespace(IsRunning=lambda: False, StartNoWait=mock.MagicMock(return_value=True))
            glob_obj = SimpleNamespace(GetValue=lambda: 0.0)
            alias_ref = SimpleNamespace(actor=None)
            alias_ref.GetActorRef = lambda: alias_ref.actor
            alias_ref.ForceRefTo = lambda a: setattr(alias_ref, "actor", a)

            def set_stage(n):
                stages.add(int(n))
                if int(n) > cur_stage[0]:
                    cur_stage[0] = int(n)

            ns = {
                "_PStr": _PStr,
                "KeeperOnly": False,
                "Trace": logs.append,
                "Preston": preston,
                "Credits": "StarfieldCredits",
                "RewardCount": 100,
                "PrestonTalkScene": scene,
                "PrestonTalkMsg": msg,
                "PrestonReply0Msg": msg,
                "PrestonReply1Msg": msg,
                "PrestonReply2Msg": msg,
                "TalkUseMessageBox": glob_obj,
                "PrestonSceneCheckSeconds": 1.5,
                "PrestonSceneMaxWaitChecks": 16,
                "min00Given": True,
                "applied": 30,
                "pendingStage": -1,
                "pendingStageBy": "other",
                "prestonFound": True,
                "talkActivated": False,
                "talkStartedAt": 0.0,
                "prestonUsedFallback": False,
                "prestonTalkLogged": False,
                "prestonTalkBoxOpen": False,
                "prestonFallbackActive": False,
                "talkSessionId": 0,
                "prestonTalkReloaded": False,
                "prestonDialogueMenuOpen": False,
                "prestonScenePending": False,
                "prestonSceneMenuOpened": False,
                "prestonScenePhase1": False,
                "prestonPhase1At": 0.0,
                "prestonSceneChecks": 0,
                "sanctuaryStartRetries": 0,
                "IsRunning": lambda: True,
                "Start": lambda: True,
                "IsCompleted": lambda: cur_stage[0] >= 200,
                "GetStage": lambda: cur_stage[0],
                "GetStageDone": lambda s: int(s) in stages,
                "SetStage": set_stage,
                "GetAlias": lambda idx: alias_ref if idx == 0 else None,
                "SetObjectiveDisplayed": lambda *_: None,
                "SetObjectiveCompleted": lambda *_: None,
                "SetActive": lambda *_: None,
                "StartTimer": lambda sec, tid: timers.append((float(sec), int(tid))),
                "CancelTimer": lambda tid: cancelled.append(int(tid)),
                "CompleteQuest": mock.MagicMock(),
                "RegisterForRemoteEvent": lambda *_: None,
                "Utility": SimpleNamespace(GetCurrentRealTime=lambda: rt[0]),
                "Game": SimpleNamespace(
                    GetPlayer=lambda: player,
                    GetFormFromFile=lambda fid, plg: (
                        scene if (fid, plg) == (0x000900, "FO4SFMission.esm")
                        else sanctuary_q if (fid, plg) == (0x000817, "FO4SFMission.esm")
                        else glob_obj if (fid, plg) == (0x000979, "FO4SFMission.esm")
                        else None
                    ),
                ),
            }
            fns = (
                "IsWarfareMode", "ShouldUseMessageBox", "EffectiveStage", "EnsurePrestonAlias",
                "ResolvePrestonScene", "ResolvePrestonSceneLogged", "RegisterPrestonSceneEvents",
                "AdvanceTo", "OnStageSet", "Apply", "FoundPreston", "ResolvePrestonMsg", "RunPrestonTalk",
                "FallbackPrestonToMessageBox", "CheckPrestonSceneOpen", "OnMenuOpenCloseEvent",
                "Scene.OnBegin", "Scene.OnPhaseBegin", "Scene.OnEnd", "ObjectReference.OnActivate",
            )
            gvars = (
                "min00Given", "applied", "pendingStage", "pendingStageBy", "prestonFound",
                "talkActivated", "talkStartedAt", "prestonUsedFallback", "prestonTalkLogged",
                "prestonTalkBoxOpen", "prestonFallbackActive", "talkSessionId", "prestonTalkReloaded",
                "prestonDialogueMenuOpen", "prestonScenePending", "prestonSceneMenuOpened",
                "prestonScenePhase1", "prestonPhase1At", "prestonSceneChecks", "sanctuaryStartRetries",
            )
            code = _translate_psc(m_psc, fns, gvars)
            exec(compile(code, "FO4SF_Min00Quest.psc", "exec"), ns)
            return SimpleNamespace(ns=ns, logs=logs, rt=rt, scene=scene, msg=msg, preston=preston, player=player, timers=timers)

        # Scenario 1: 1.5 s fallback latches prestonFallbackActive -> late native OnPhaseBegin / OnMenuOpenCloseEvent suppressed!
        e1 = make_env(msg_clicks=[-1])  # MessageBox returns -1 so stage stays 30 while fallback is active
        e1.ns["OnActivate"](e1.preston, e1.player)
        e1.ns["OnBegin"](e1.scene)
        e1.ns["OnPhaseBegin"](e1.scene, 1)
        e1.rt[0] += 1.5
        e1.ns["CheckPrestonSceneOpen"]()
        self.assertTrue(e1.ns["prestonFallbackActive"])
        self.assertEqual(e1.msg.shown, 1)
        stops_after_timeout = e1.scene.stop_calls
        # Late native greeting tries to advance phase and open DialogueMenu -> MUST stop scene & never mark menu opened!
        e1.scene.playing = True
        e1.ns["OnPhaseBegin"](e1.scene, 1)
        self.assertEqual(e1.scene.stop_calls, stops_after_timeout + 1)
        self.assertFalse(e1.scene.playing)
        e1.ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
        self.assertEqual(e1.scene.stop_calls, stops_after_timeout + 2)
        self.assertFalse(e1.ns["prestonSceneMenuOpened"])
        self.assertTrue(any("preston scene suppressed reason=single_talk" in ln for ln in e1.logs), e1.logs)

        # Scenario 2: DialogueMenu opens FIRST (run3 concurrent DEVT race) -> FallbackPrestonToMessageBox & RunPrestonTalk refused!
        e2 = make_env()
        e2.scene.playing = True
        e2.ns["OnPhaseBegin"](e2.scene, 1)
        e2.ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
        self.assertTrue(e2.ns["prestonSceneMenuOpened"])
        timers_before = len(e2.timers)
        e2.ns["OnActivate"](e2.preston, e2.player)  # must NOT overwrite prestonSceneMenuOpened or arm Timer 3!
        self.assertTrue(e2.ns["prestonSceneMenuOpened"])
        self.assertEqual(len(e2.timers), timers_before)
        e2.ns["FallbackPrestonToMessageBox"]("late_timer")
        e2.ns["RunPrestonTalk"](30, e2.msg)
        self.assertEqual(e2.msg.shown, 0)
        self.assertTrue(any("preston fallback suppressed reason=dialogue_active" in ln for ln in e2.logs), e2.logs)
        self.assertTrue(any("preston messagebox suppressed reason=dialogue_menu_open" in ln for ln in e2.logs), e2.logs)

    def test_a2_4_keeper_timer2_continues_for_proximity_starts_when_both_budgets_exhaust(self):
        """A2.4: KeeperOnly Timer 2 still reschedules when codsworthFails == 10, prestonFails == 10, and holds == 0."""
        m_psc = MIN00_PSC.read_text(encoding="utf-8")
        timers = []
        prox_calls = []

        def run_keep(keeper_only):
            timers.clear()
            prox_calls.clear()
            ns = {
                "_PStr": _PStr,
                "KeeperOnly": keeper_only,
                "Codsworth": SimpleNamespace(),
                "codsworthFails": 10,
                "codsworthHolds": 0,
                "prestonFails": 10,
                "prestonHolds": 0,
                "keeperChecks": 1,
                "KeeperStatusEvery": 12,
                "CodsworthCheck": 5.0,
                "codsworthState": "gave up",
                "Trace": lambda *_: None,
                "CheckPostConcordSanctuaryHandoff": lambda: None,
                "ReleaseCodsworthInFight": lambda *_: None,
                "PlaceCodsworth": lambda *_: False,
                "KeepPreston": lambda *_: None,
                "TraceCodsworth": lambda *_: None,
                "CheckA4ProximityStarts": lambda _p: prox_calls.append("a4"),
                "CheckA7ProximityStarts": lambda _p: prox_calls.append("a7"),
                "CheckA7cdProximityStarts": lambda _p: prox_calls.append("a7cd"),
                "StartTimer": lambda sec, tid: timers.append((float(sec), int(tid))),
                "IsTestModeEnabled": lambda: False,
                "Debug": SimpleNamespace(Notification=lambda *_: None),
                "Game": SimpleNamespace(GetPlayer=lambda: SimpleNamespace()),
            }
            code = _translate_psc(
                m_psc,
                ("KeepCodsworth",),
                ("codsworthFails", "codsworthHolds", "prestonFails", "prestonHolds", "codsworthState"),
            )
            exec(compile(code, "FO4SF_Min00Quest.psc", "exec"), ns)
            ns["KeepCodsworth"]()

        # KeeperOnly=True: proximity starts run AND Timer 2 reschedules even with both budgets exhausted!
        run_keep(True)
        self.assertEqual(prox_calls, ["a4", "a7", "a7cd"])
        self.assertEqual(timers, [(5.0, 2)])

        # KeeperOnly=False: non-keeper Timer 2 still stops once codsworthFails == 10 && codsworthHolds == 0
        run_keep(False)
        self.assertEqual(prox_calls, [])
        self.assertEqual(timers, [])

    def test_a2_5_codsworth_camera_guard_validates_ground_z_and_sanctuary_house_wall(self):
        """A2.5: EnsureSafeCodsworthCameraDistance skips on ground-Z mismatch and redirects NW wall-bound
        step-backs onto the unobstructed Sanctuary yard/street at exact 1.85 m."""
        c_psc = CODS_PSC.read_text(encoding="utf-8")
        cods_pos = [-2346.709, -1406.163, 111.734]

        def run_guard(p_start):
            logs = []
            p_pos = list(p_start)
            calls = []

            def set_pos(x, y, z):
                calls.append((x, y, z))
                p_pos[:] = [x, y, z]

            cods = SimpleNamespace(
                GetPositionX=lambda: cods_pos[0], GetPositionY=lambda: cods_pos[1],
                GetPositionZ=lambda: cods_pos[2], GetAngleZ=lambda: 0.0,
            )
            player = SimpleNamespace(
                IsInInterior=lambda: False,
                GetPositionX=lambda: p_pos[0], GetPositionY=lambda: p_pos[1], GetPositionZ=lambda: p_pos[2],
                SetPosition=set_pos,
            )
            ns = {
                "_PStr": _PStr,
                "Trace": logs.append,
                "MinTalkCameraDistance": 1.65,
                "SafeTalkCameraDistance": 1.85,
                "Math": SimpleNamespace(Sqrt=math.sqrt, Sin=math.sin, Cos=math.cos),
            }
            code = _translate_psc(c_psc, ("EnsureSafeCodsworthCameraDistance",), ())
            exec(compile(code, "FO4SF_Codsworth01Quest.psc", "exec"), ns)
            ns["EnsureSafeCodsworthCameraDistance"](player, cods)
            return calls, p_pos, logs

        # 1. Ground-Z mismatch (+2.2 m above Codsworth, e.g. roof/ledge) -> MUST skip SetPosition!
        calls_z, pos_z, logs_z = run_guard([cods_pos[0] + 0.5, cods_pos[1] - 0.5, cods_pos[2] + 2.2])
        self.assertEqual(calls_z, [])
        self.assertTrue(any("skipped reason=ground_z_mismatch" in ln for ln in logs_z), logs_z)

        # 2. Player directly NW toward Player House wall (normal (-0.6428, +0.7660)) -> redirects clear of wall at 1.85 m!
        calls_w, pos_w, logs_w = run_guard([cods_pos[0] - 0.45, cods_pos[1] + 0.45, cods_pos[2] + 0.05])
        self.assertEqual(len(calls_w), 1)
        self.assertAlmostEqual(math.hypot(pos_w[0] - cods_pos[0], pos_w[1] - cods_pos[1]), 1.85, places=2)
        wall_proj = (pos_w[0] - cods_pos[0]) * (-0.6428) + (pos_w[1] - cods_pos[1]) * 0.7660
        self.assertLessEqual(wall_proj, 1.0, f"step-back still penetrated NW house wall: wall_proj={wall_proj}")
        self.assertTrue(any("wall_avoid=True" in ln for ln in logs_w), logs_w)

        # 3. Player on open SE street -> steps straight back along direct ray (wall_avoid=False) at 1.85 m!
        calls_s, pos_s, logs_s = run_guard([cods_pos[0] + 0.5, cods_pos[1] - 0.5, cods_pos[2]])
        self.assertEqual(len(calls_s), 1)
        self.assertAlmostEqual(math.hypot(pos_s[0] - cods_pos[0], pos_s[1] - cods_pos[1]), 1.85, places=2)
        self.assertTrue(any("wall_avoid=False" in ln for ln in logs_s), logs_s)

    def test_docs_report_exists_and_honestly_splits_offline_vs_game_only(self):
        txt = DOC_MD.read_text(encoding="utf-8")
        for token in ("MiniBotA", "0.506", "StopDialogueCamera", "LL_Ammo_Shotshell", "30, 70, 30, 30, 20",
                      "0x0476C4", "DoNotGrayOut", "cannot be proven from the ESM bytes", "Game-only"):
            self.assertIn(token, txt, f"doc missing {token!r}")

    @unittest.skipUnless(os.environ.get("FO4SF_DOTNET_TESTS") == "1", "Set FO4SF_DOTNET_TESTS=1 for binary ESM check")
    def test_dotnet_selftest_binary_esm_r11_w1_records(self):
        """Binary verification of generated FO4SFMission.esm for D1 RACE, D3 RaiderSidearm VMAD, and D5 ENAM/INAM."""
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ)
            env.setdefault("DOTNET_ROLL_FORWARD", "Major")
            proc = subprocess.run(
                ["dotnet", "run", "--project", str(ROOT / "dotnet" / "Mission"), "-c", "Release", "--", "selftest", td],
                cwd=str(ROOT), capture_output=True, text=True, env=env,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + "\n" + proc.stderr)
            self.assertIn("selftest pass", proc.stdout)
            esm_bytes = (Path(td) / "out" / "alias" / "FO4SFMission.esm").read_bytes()

            # Check D5 Part 3: ENAM (Flags=0) and INAM (1) present on Preston pcInfo 0x918..0x91A & Codsworth 0x958..0x95B
            pc_checked = {}
            for sig, fid, _fl, body in _iter_esm_records(esm_bytes, {b"INFO"}):
                lid = fid & 0xFFFFFF
                if lid in (0x918, 0x919, 0x91A, 0x958, 0x959, 0x95A, 0x95B):
                    subs = dict(_iter_subrecords(body))
                    enam = struct.unpack_from("<H", subs[b"ENAM"], 0)[0] if b"ENAM" in subs else None
                    inam = struct.unpack_from("<I", subs[b"INAM"], 0)[0] if b"INAM" in subs else None
                    pc_checked[lid] = (enam, inam)
            self.assertEqual(set(pc_checked.keys()), {0x918, 0x919, 0x91A, 0x958, 0x959, 0x95A, 0x95B})
            for lid, (enam, inam) in pc_checked.items():
                self.assertEqual(enam, 0, f"INFO 0x{lid:X} ENAM={enam} != 0")
                self.assertEqual(inam, 1, f"INFO 0x{lid:X} INAM={inam} != 1")

            # Check D1: FO4SF_CodsworthRace (0x818) has no DialogueQuest (QSTI) and Size=Medium (1) in DAT2[0x30]
            races = {}
            for sig, fid, _fl, body in _iter_esm_records(esm_bytes, {b"RACE"}):
                lid = fid & 0xFFFFFF
                if lid == 0x818:
                    subs = dict(_iter_subrecords(body))
                    races[lid] = subs
            self.assertIn(0x818, races)
            self.assertNotIn(b"QSTI", races[0x818])
            dat2 = races[0x818][b"DAT2"]
            self.assertEqual(struct.unpack_from("<I", dat2, 0x30)[0], 1)  # Size.Medium == 1


if __name__ == "__main__":
    unittest.main()
