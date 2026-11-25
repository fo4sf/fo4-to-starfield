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
            line = re.sub(r"\bnew\s+float\[([^\]]+)\]", r"[0.0] * (\1)", line)
            line = re.sub(r"\bnew\s+bool\[([^\]]+)\]", r"[False] * (\1)", line)
            line = re.sub(r"\bnew\s+int\[([^\]]+)\]", r"[0] * (\1)", line)
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
        """D1 + E1 (#598): --codsworth-race-framing defaults to 0 (OFF, exact 2g race parity) and opts into
        the 5 standing-robot edits only when 1; FO4SF_Codsworth01Quest MUST NOT call Game.StopDialogueCamera on phase >= 2."""
        cs = MISSION_CS.read_text(encoding="utf-8")
        c_psc = CODS_PSC.read_text(encoding="utf-8")

        self.assertIn('Mission.BoolFlag(args, "--codsworth-race-framing", false)', cs)
        self.assertIn("bool codsworthRaceFraming = false", cs)
        self.assertIn("if (codsworthRaceFraming)", cs)
        self.assertIn("codsRace.Size = SF.Size.Medium;", cs)
        self.assertIn("codsRace.DialogueQuest.Clear();", cs)
        self.assertIn("SF.Race.Flag.HeadAxisBit0", cs)
        self.assertIn("0x0080000000000000UL", cs)
        self.assertIn("SfModelARaceId = 0x005629", cs)
        self.assertNotIn("StopDialogueCamera", c_psc)

        logs = []
        stop_cam_calls = []
        timers = []
        cancelled = []
        scene = SimpleNamespace(IsPlaying=lambda: True)
        ns = {
            "_PStr": _PStr,
            "Trace": logs.append,
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
                GetFormFromFile=lambda fid, plg: scene if (fid, plg) == (0x000940, "FO4SFMission.esm") else None,
                StopDialogueCamera=lambda resume=False, to1p=False: stop_cam_calls.append((bool(resume), bool(to1p))),
            ),
        }
        code = _translate_psc(
            c_psc,
            ("EffectiveStage", "ResolveCodsworthScene", "ResolveCodsworthPostScene", "Scene.OnPhaseBegin"),
            ("sceneTalkPending", "sceneMenuOpened", "dialogueMenuOpen", "scenePhase1Entered", "scenePhase1At", "applied"),
        )
        exec(compile(code, "FO4SF_Codsworth01Quest.psc", "exec"), ns)

        # Phase 1 (greeting): resets 1.5 s timer, does NOT call StopDialogueCamera
        ns["OnPhaseBegin"](scene, 1)
        self.assertEqual(stop_cam_calls, [])
        self.assertEqual(timers, [(1.5, 2)])

        # Phase 2 (TOPLEVELNEST choices) & loop-back Phase 2: E1 restores 2g camera (ZERO StopDialogueCamera calls)
        ns["OnPhaseBegin"](scene, 2)
        ns["OnPhaseBegin"](scene, 2)
        self.assertEqual(stop_cam_calls, [])
        self.assertEqual(sum(1 for ln in logs if "dialogue_camera stopped" in ln), 0)

    def test_d3_raider_ammo_deterministic_60_and_balanced_eon_sidearm(self):
        """D3 + R13 E3 + fix4 + Task 0d: LL_Ammo_Shotshell spawn rolls normalize to exact 60 with softened 0x97B Coachman
        (4.0 dmg, NonPlayable, ObjectTemplates+AttachParentSlots intact), then EquipBalancedRaiderSidearm equips
        WEAP 0x097A (1.5-dmg FO4SF_ConcordRaiderSidearm, ObjectTemplates+AttachParentSlots intact, AmmoList=null),
        strips 0x97B + AmmoShotshell, clamps Ammo777mm=36, and preserves raider FO4 0x0988 outfits (no UnequipAll)."""
        cs = MISSION_CS.read_text(encoding="utf-8")
        m_psc = MIN00_PSC.read_text(encoding="utf-8")
        self.assertIn("SfRaiderSidearmId = 0x0476C4", cs)
        self.assertIn("ConcordRaiderPrimaryWeapId = 0x97B", cs)
        self.assertIn("ConcordRaiderPrimaryDamage = 4.0f", cs)
        self.assertIn("ConcordRaiderSidearmWeapId = 0x97A", cs)
        self.assertIn("ConcordRaiderSidearmDamage = 1.5f", cs)
        self.assertIn("concordPrimary.AmmoList.SetToNull();", cs)
        self.assertNotIn("concordPrimary.ObjectTemplates = null;", cs)
        self.assertIn("concordSidearm.AmmoList.SetToNull();", cs)
        self.assertNotIn("concordSidearm.ObjectTemplates = null;", cs)
        self.assertIn("SfRaiderSidearmAmmoId = 0x04AD3E", cs)
        self.assertIn('Obj("RaiderWeapon", concordPrimary.FormKey)', cs)
        self.assertIn('Flt("RaiderPrimaryRecordDamage", primaryRecordDamage)', cs)
        self.assertIn('Obj("RaiderSidearm", concordSidearm.FormKey)', cs)
        self.assertIn('Obj("RaiderSidearmAmmo", raiderSidearmAmmo.FormKey)', cs)
        self.assertIn('Flt("RaiderSidearmRecordDamage", sidearmRecordDamage)', cs)

        class _Raider:
            def __init__(self, shells, ammo777=0, bonus_on_sidearm=16, atk_mult=0.0):
                self.inv = {"Coachman097B": 1, "AmmoShotshell": shells}
                if ammo777:
                    self.inv["Ammo777mm"] = ammo777
                self.bonus_on_sidearm = bonus_on_sidearm
                self.equipped = [("SpacerGun", False)]
                self.outfit_worn = True
                self.unequipped = []
                self.unequipped_all = 0
                self.restrained = True
                self.avs = {"AttackDamageMult": atk_mult}
                self.evals = 0

            def IsDead(self): return False
            def SetRestrained(self, v): self.restrained = bool(v)
            def SetValue(self, av, val): self.avs[av] = float(val)
            def GetValue(self, av): return float(self.avs.get(av, 0.0))
            def GetItemCount(self, item): return self.inv.get(item, 0)
            def AddItem(self, item, cnt, _silent=False):
                self.inv[item] = self.inv.get(item, 0) + int(cnt)
                if item == "Eon097A" and self.bonus_on_sidearm:
                    self.inv["Ammo777mm"] = self.inv.get("Ammo777mm", 0) + self.bonus_on_sidearm
            def RemoveItem(self, item, cnt, _silent=False): self.inv[item] = max(0, self.inv.get(item, 0) - int(cnt))
            def UnequipAll(self):
                self.unequipped_all += 1
                self.outfit_worn = False
                self.equipped.clear()
            def UnequipItem(self, item, *_):
                self.unequipped.append(item)
                self.equipped = [e for e in self.equipped if e[0] != item]
            def EquipItem(self, item, prevent_removal=False, _silent=False): self.equipped.append((item, bool(prevent_removal)))
            def GetEquippedWeapon(self, idx=0): return self.equipped[-1][0] if self.equipped else None
            def EvaluatePackage(self): self.evals += 1

        # Exact candidate-2g LL_Ammo_Shotshell rolls + an overflow case (85)
        rolls = [30, 10, 30, 30, 20, 85]
        raiders = [_Raider(s, ammo777=(50 if i == 5 else 0)) for i, s in enumerate(rolls)]
        logs = []
        ns = {
            "_PStr": _PStr,
            "Trace": logs.append,
            "RaiderWeapon": "Coachman097B",
            "RaiderAmmo": "AmmoShotshell",
            "RaiderSidearm": "Eon097A",
            "RaiderPrimaryRecordDamage": 4.0,
            "RaiderSidearmRecordDamage": 1.5,
            "AttackDamageMult": None,
            "RaiderSidearmAmmo": "Ammo777mm",
            "raiderArmed": _PArray([False] * len(raiders)),
            "Game": SimpleNamespace(
                GetAggressionAV=lambda: "Aggression",
                GetConfidenceAV=lambda: "Confidence",
            ),
        }
        code = _translate_psc(m_psc, ("ComputeEffectiveWeaponDamage", "ArmRaiderForCombat", "EquipBalancedRaiderSidearm"), ("raiderArmed",))
        exec(compile(code, "FO4SF_Min00Quest.psc", "exec"), ns)

        for idx, r in enumerate(raiders):
            ns["ArmRaiderForCombat"](r, idx)
            self.assertEqual(r.unequipped_all, 0)
            self.assertTrue(r.outfit_worn)
            self.assertEqual(r.inv["AmmoShotshell"], 60, f"raider {idx} shell count != 60 after ArmRaiderForCombat")
            self.assertIn("eff_dmg=4.0", logs[-1])
            ns["EquipBalancedRaiderSidearm"](r, idx)
            self.assertEqual(r.inv["Coachman097B"], 0, f"raider {idx} Coachman must be removed to prevent AI re-equip")
            self.assertEqual(r.inv["AmmoShotshell"], 0, f"raider {idx} AmmoShotshell must be removed after sidearm swap")
            self.assertEqual(r.inv["Ammo777mm"], 36, f"raider {idx} 7.77mm count != 36")
            self.assertEqual(r.unequipped, ["SpacerGun", "Coachman097B"])
            self.assertEqual(r.equipped[-1], ("Eon097A", False))
            self.assertFalse(r.restrained)
            self.assertEqual(r.avs["Aggression"], 2.0)
            self.assertEqual(r.avs["Confidence"], 4.0)
            self.assertTrue(ns["raiderArmed"][idx])
            self.assertIn(f"arm raider {idx} ammo=60", logs[-2])
            self.assertIn("eff_dmg=4.0", logs[-2])
            self.assertIn(f"arm raider {idx} sidearm=eon sidearm_ammo=36", logs[-1])
            self.assertIn("eff_dmg=1.5", logs[-1])

        # Fallback path + resolved AttackDamageMult scaling check
        ns["AttackDamageMult"] = "AttackDamageMult"
        fallback_r = _Raider(10, atk_mult=1.5)
        ns["RaiderSidearm"] = None
        ns["raiderArmed"].append(False)
        ns["ArmRaiderForCombat"](fallback_r, len(raiders))
        ns["EquipBalancedRaiderSidearm"](fallback_r, len(raiders))
        self.assertEqual(fallback_r.inv["Coachman097B"], 1)
        self.assertEqual(fallback_r.inv["AmmoShotshell"], 60)
        self.assertEqual(fallback_r.equipped[-1], ("Coachman097B", False))
        self.assertIn("eff_dmg=6.0", logs[-1])

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
        """A2.2 + R11 Part 3 (#598): Under explicit glob=1.0 MessageBox mode, MessageBox & late DialogueMenu never
        coexist; under default glob=0.0 Starfield Scene mode, MessageBox is NEVER opened (retries 1..3 + post-200
        PrestonPostTalkScene 0x0990)."""
        m_psc = MIN00_PSC.read_text(encoding="utf-8")

        def make_env(msg_clicks=(3,), glob_val=0.0):
            logs = []
            rt = [343.18]
            stages = {10, 20, 30}
            cur_stage = [30]
            timers = []
            cancelled = []

            class _Scene:
                def __init__(self, name="PrestonTalkScene"):
                    self.name = name
                    self.playing = False
                    self.start_calls = 0
                    self.stop_calls = 0

                def IsPlaying(self): return self.playing
                def Start(self): self.start_calls += 1; self.playing = True; return True
                def ForceStart(self): return self.Start()
                def Stop(self): self.stop_calls += 1; self.playing = False

            scene = _Scene("PrestonTalkScene")
            post_scene = _Scene("PrestonPostTalkScene")

            class _Msg:
                def __init__(self):
                    self.clicks = list(msg_clicks)
                    self.shown = 0

                def Show(self):
                    self.shown += 1
                    return self.clicks.pop(0) if self.clicks else 3

            msg = _Msg()
            preston = SimpleNamespace(
                StopCombat=lambda: None,
                IgnoreFriendlyHits=lambda *_: None,
                AllowPCDialogue=lambda *_: None,
                BlockActivation=lambda *_: None,
            )
            player = SimpleNamespace(AddItem=mock.MagicMock())
            sanctuary_q = SimpleNamespace(IsRunning=lambda: False, StartNoWait=mock.MagicMock(return_value=True))
            glob_obj = SimpleNamespace(GetValue=lambda: float(glob_val))
            alias_ref = SimpleNamespace(actor=None)
            alias_ref.GetActorRef = lambda: alias_ref.actor
            alias_ref.ForceRefTo = lambda a: setattr(alias_ref, "actor", a)
            keeper_alias = SimpleNamespace(actor=None)
            keeper_alias.GetActorRef = lambda: keeper_alias.actor
            keeper_alias.ForceRefTo = lambda a: setattr(keeper_alias, "actor", a)
            keeper_q = SimpleNamespace(
                IsRunning=lambda: True,
                Start=lambda: True,
                GetAlias=lambda idx: keeper_alias if idx == 0 else None,
            )

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
                "PrestonTalkMsg": msg,
                "PrestonReply0Msg": msg,
                "PrestonReply1Msg": msg,
                "PrestonReply2Msg": msg,
                "TalkUseMessageBox": glob_obj,
                "PrestonSceneCheckSeconds": 1.5,
                "PrestonSceneMaxWaitChecks": 16,
                "PrestonMaxSceneRestarts": 3,
                "min00Given": True,
                "applied": 30,
                "pendingStage": -1,
                "pendingStageBy": "other",
                "prestonFound": True,
                "talkActivated": False,
                "talkStartedAt": 0.0,
                "talkFailures": 0,
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
                "prestonSceneRestarts": 0,
                "prestonPostSceneActive": False,
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
                        else post_scene if (fid, plg) == (0x000990, "FO4SFMission.esm")
                        else keeper_q if (fid, plg) == (0x000814, "FO4SFMission.esm")
                        else sanctuary_q if (fid, plg) == (0x000817, "FO4SFMission.esm")
                        else glob_obj if (fid, plg) == (0x000979, "FO4SFMission.esm")
                        else None
                    ),
                ),
            }
            fns = (
                "IsWarfareMode", "ShouldUseMessageBox", "EffectiveStage", "EnsurePrestonAlias",
                "EnsureActorTalkable", "ResolvePrestonScene", "ResolvePrestonSceneLogged",
                "ResolvePrestonPostScene", "ResolveActivePrestonScene", "EnsureKeeperPrestonAlias",
                "RegisterPrestonSceneEvents", "AdvanceTo", "OnStageSet", "Apply", "FoundPreston",
                "ResolvePrestonMsg", "RunPrestonTalk", "FallbackPrestonToMessageBox",
                "RestartOrFailPrestonScene", "CheckPrestonSceneOpen", "OnMenuOpenCloseEvent",
                "Scene.OnBegin", "Scene.OnPhaseBegin", "Scene.OnEnd", "ObjectReference.OnActivate",
            )
            gvars = (
                "min00Given", "applied", "pendingStage", "pendingStageBy", "prestonFound",
                "talkActivated", "talkStartedAt", "talkFailures", "prestonUsedFallback", "prestonTalkLogged",
                "prestonTalkBoxOpen", "prestonFallbackActive", "talkSessionId", "prestonTalkReloaded",
                "prestonDialogueMenuOpen", "prestonScenePending", "prestonSceneMenuOpened",
                "prestonScenePhase1", "prestonPhase1At", "prestonSceneChecks",
                "prestonSceneRestarts", "prestonPostSceneActive", "sanctuaryStartRetries",
            )
            code = _translate_psc(m_psc, fns, gvars)
            exec(compile(code, "FO4SF_Min00Quest.psc", "exec"), ns)
            return SimpleNamespace(
                ns=ns, logs=logs, rt=rt, scene=scene, post_scene=post_scene,
                msg=msg, preston=preston, player=player, timers=timers,
            )

        # Scenario 1 (glob=1.0 explicit MessageBox mode): While MessageBox is actively open inside Show(),
        # late native OnPhaseBegin / OnMenuOpenCloseEvent MUST be suppressed (never both); exiting < 35 clears latches.
        late_checks = {}
        e1 = make_env(msg_clicks=[-1], glob_val=1.0)

        orig_show = e1.msg.Show
        def _show_with_late_greeting():
            late_checks["fallback_during_show"] = e1.ns["prestonFallbackActive"]
            late_checks["box_during_show"] = e1.ns["prestonTalkBoxOpen"]
            stops_before = e1.scene.stop_calls
            e1.scene.playing = True
            e1.ns["OnPhaseBegin"](e1.scene, 1)
            late_checks["stop_after_phase"] = e1.scene.stop_calls - stops_before
            late_checks["playing_after_phase"] = e1.scene.playing
            e1.ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
            late_checks["stop_after_menu"] = e1.scene.stop_calls - stops_before
            late_checks["menu_opened_flag"] = e1.ns["prestonSceneMenuOpened"]
            e1.ns["prestonDialogueMenuOpen"] = False
            return orig_show()

        e1.msg.Show = _show_with_late_greeting
        e1.ns["OnActivate"](e1.preston, e1.player)
        self.assertTrue(late_checks["fallback_during_show"])
        self.assertTrue(late_checks["box_during_show"])
        self.assertEqual(late_checks["stop_after_phase"], 1)
        self.assertFalse(late_checks["playing_after_phase"])
        self.assertEqual(late_checks["stop_after_menu"], 1)
        self.assertFalse(late_checks["menu_opened_flag"])
        self.assertEqual(e1.msg.shown, 1)
        self.assertTrue(any("preston scene suppressed reason=single_talk" in ln for ln in e1.logs), e1.logs)
        self.assertFalse(e1.ns["prestonTalkBoxOpen"])
        self.assertFalse(e1.ns["prestonFallbackActive"])

        # Scenario 2 (glob=0.0 default): DialogueMenu opens FIRST -> FallbackPrestonToMessageBox & RunPrestonTalk refused!
        e2 = make_env(glob_val=0.0)
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
        self.assertTrue(any("preston fallback suppressed reason=glob_off" in ln for ln in e2.logs), e2.logs)
        self.assertTrue(any("preston messagebox suppressed reason=glob_off" in ln for ln in e2.logs), e2.logs)

        # Scenario 3 (glob=1.0 — late_dialogue_open): DialogueMenu opens during scn.Stop() inside
        # FallbackPrestonToMessageBox -> MUST clear prestonFallbackActive = False before returning!
        e3 = make_env(glob_val=1.0)
        e3.scene.playing = True
        orig_stop = e3.scene.Stop
        def _stop_opening_dialogue():
            orig_stop()
            e3.ns["prestonDialogueMenuOpen"] = True
        e3.scene.Stop = _stop_opening_dialogue
        e3.ns["FallbackPrestonToMessageBox"]("dialogue_menu_timeout")
        self.assertFalse(e3.ns["prestonFallbackActive"], "late_dialogue_open leaked prestonFallbackActive=True!")
        self.assertEqual(e3.msg.shown, 0)
        self.assertTrue(any("preston fallback suppressed reason=late_dialogue_open" in ln for ln in e3.logs), e3.logs)

        # Scenario 4 (post-200 press): glob=1.0 uses MessageBox; glob=0.0 launches PrestonPostTalkScene (0x0990)
        # with ZERO MessageBox and never re-runs stage-30 scene or rewards!
        e4 = make_env(msg_clicks=[3, 3], glob_val=1.0)
        e4.ns["FallbackPrestonToMessageBox"]("glob")
        self.assertEqual(e4.ns["EffectiveStage"](), 200)
        self.assertFalse(e4.ns["prestonTalkBoxOpen"])
        self.assertFalse(e4.ns["prestonFallbackActive"])
        e4.ns["prestonFallbackActive"] = True  # simulate stale latch
        scene_starts_before = e4.scene.start_calls
        rewards_before = e4.player.AddItem.call_count
        e4.ns["OnActivate"](e4.preston, e4.player)
        self.assertEqual(e4.msg.shown, 2, "post-200 press was blocked by stale prestonFallbackActive")
        self.assertEqual(e4.scene.start_calls, scene_starts_before, "post-200 press re-ran stage-30 scene!")
        self.assertEqual(e4.player.AddItem.call_count, rewards_before, "post-200 press re-granted stage-40 reward!")

        e5 = make_env(glob_val=0.0)
        e5.ns["applied"] = 200
        e5.ns["SetStage"](200)
        e5.ns["prestonTalkLogged"] = True
        e5.ns["OnActivate"](e5.preston, e5.player)
        self.assertEqual(e5.post_scene.start_calls, 1)
        self.assertEqual(e5.scene.start_calls, 0)
        self.assertEqual(e5.msg.shown, 0)

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
            angles = []

            def set_pos(x, y, z):
                calls.append((x, y, z))
                p_pos[:] = [x, y, z]

            def set_angle(ax, ay, az):
                angles.append((ax, ay, az))

            cods = SimpleNamespace(
                GetPositionX=lambda: cods_pos[0], GetPositionY=lambda: cods_pos[1],
                GetPositionZ=lambda: cods_pos[2], GetAngleZ=lambda: 0.0,
            )
            player = SimpleNamespace(
                IsInInterior=lambda: False,
                GetPositionX=lambda: p_pos[0], GetPositionY=lambda: p_pos[1], GetPositionZ=lambda: p_pos[2],
                SetPosition=set_pos,
                SetAngle=set_angle,
            )
            ns = {
                "_PStr": _PStr,
                "Trace": logs.append,
                "MinTalkCameraDistance": 1.65,
                "SafeTalkCameraDistance": 1.85,
                "Math": SimpleNamespace(
                    Sqrt=math.sqrt,
                    Sin=lambda d: math.sin(math.radians(d)),
                    Cos=lambda d: math.cos(math.radians(d)),
                    atan=lambda v: math.degrees(math.atan(v)),
                ),
            }
            code = _translate_psc(c_psc, ("EnsureSafeCodsworthCameraDistance",), ())
            exec(compile(code, "FO4SF_Codsworth01Quest.psc", "exec"), ns)
            ns["EnsureSafeCodsworthCameraDistance"](player, cods)
            return calls, angles, p_pos, logs

        # 1. Ground-Z mismatch (+2.2 m above Codsworth, e.g. roof/ledge) -> MUST skip SetPosition!
        calls_z, angles_z, pos_z, logs_z = run_guard([cods_pos[0] + 0.5, cods_pos[1] - 0.5, cods_pos[2] + 2.2])
        self.assertEqual(calls_z, [])
        self.assertEqual(angles_z, [])
        self.assertTrue(any("skipped reason=ground_z_mismatch" in ln for ln in logs_z), logs_z)

        # 2. Player directly NW toward Player House wall (normal (-0.6428, +0.7660)) -> redirects clear of wall at 1.85 m + faces Codsworth!
        calls_w, angles_w, pos_w, logs_w = run_guard([cods_pos[0] - 0.45, cods_pos[1] + 0.45, cods_pos[2] + 0.05])
        self.assertEqual(len(calls_w), 1)
        self.assertEqual(len(angles_w), 1)
        self.assertAlmostEqual(math.hypot(pos_w[0] - cods_pos[0], pos_w[1] - cods_pos[1]), 1.85, places=2)
        wall_proj = (pos_w[0] - cods_pos[0]) * (-0.6428) + (pos_w[1] - cods_pos[1]) * 0.7660
        self.assertLessEqual(wall_proj, 1.0, f"step-back still penetrated NW house wall: wall_proj={wall_proj}")
        self.assertTrue(any("wall_avoid=True" in ln and "facing_deg=" in ln for ln in logs_w), logs_w)

        # 3. Player on open SE street -> steps straight back along direct ray (wall_avoid=False) at 1.85 m + faces Codsworth (~315 deg)!
        calls_s, angles_s, pos_s, logs_s = run_guard([cods_pos[0] + 0.5, cods_pos[1] - 0.5, cods_pos[2]])
        self.assertEqual(len(calls_s), 1)
        self.assertEqual(len(angles_s), 1)
        self.assertAlmostEqual(math.hypot(pos_s[0] - cods_pos[0], pos_s[1] - cods_pos[1]), 1.85, places=2)
        self.assertAlmostEqual(angles_s[0][2], 315.0, places=1)
        self.assertTrue(any("wall_avoid=False" in ln and "facing_deg=" in ln for ln in logs_s), logs_s)

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

            # Check D1 + Review Item #6 (default --codsworth-race-framing 0): FO4SF_CodsworthRace (0x818)
            # preserves exact 2g MiniBotARace defaults (Size.Small == 0, QSTI DialogueQuest present, zero DAT2Unknown3).
            def read_cods_race(esm_path):
                raw = esm_path.read_bytes()
                for sig, fid, _fl, body in _iter_esm_records(raw, {b"RACE"}):
                    if (fid & 0xFFFFFF) == 0x818:
                        return dict(_iter_subrecords(body))
                raise AssertionError(f"RACE 0x818 not found in {esm_path}")

            default_race = read_cods_race(Path(td) / "out" / "alias" / "FO4SFMission.esm")
            self.assertIn(b"QSTI", default_race)
            self.assertEqual(struct.unpack_from("<I", default_race[b"DAT2"], 0x30)[0], 0)  # Size.Small == 0
            self.assertEqual(default_race[b"DAT2"][0xA0:0xA0 + 61], b"\x00" * 61)

            # Check variant --codsworth-race-framing 1: FO4SF_CodsworthRace (0x818) enables Size.Medium (1),
            # clears QSTI, and copies non-zero ModelARace DAT2Unknown3 framing bytes.
            variant_race = read_cods_race(Path(td) / "out" / "codsworth_race_framing" / "FO4SFMission.esm")
            self.assertNotIn(b"QSTI", variant_race)
            self.assertEqual(struct.unpack_from("<I", variant_race[b"DAT2"], 0x30)[0], 1)  # Size.Medium == 1
            self.assertNotEqual(variant_race[b"DAT2"][0xA0:0xA0 + 61], b"\x00" * 61)


if __name__ == "__main__":
    unittest.main()
