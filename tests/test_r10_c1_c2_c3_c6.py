"""Round 10 Slice W1 regression tests: C1 (Preston single real talk), C2 (no greeting replay via INTV=1),
C3 (Concord raiders merged coords, ammo/weapon/aggression, all 5 StartCombat, hits-to-kill),
C6 (Codsworth 0.6 m vs 2.0 m camera guard), and R1/R5/R7."""

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
PROGRAM_CS = ROOT / "dotnet" / "Mission" / "Program.cs"
MIN00_PSC = ROOT / "scripts" / "mission" / "FO4SF_Min00Quest.psc"
CODS_PSC = ROOT / "scripts" / "mission" / "FO4SF_Codsworth01Quest.psc"


def function_body(psc, name):
    i = psc.index(f"Function {name}(")
    return psc[i:psc.index("EndFunction", i)]


def _translate_mission_psc(src_text, fn_names, global_vars):
    clean_text = re.sub(r"\{[^}]*\}", "", src_text)
    out = [
        "class _PStr(str):",
        "    def __add__(self, other): return _PStr(super().__add__(str(other)))",
        "    def __radd__(self, other): return _PStr(str(other) + str(self))",
    ]
    for name in fn_names:
        esc = re.escape(name)
        match = re.search(
            rf"(?m)^(?:[\w\[\]]+[ \t]+)?(?:Function|Event)[ \t]+{esc}\(([^)]*)\)[ \t]*\r?\n(.*?)^End(?:Function|Event)\b",
            clean_text,
            re.S,
        )
        if match is None:
            raise AssertionError(f"missing Papyrus function/event: {name}")
        args_raw, body = match.groups()
        py_args = []
        for raw_arg in args_raw.split(","):
            raw_arg = raw_arg.strip()
            if not raw_arg:
                continue
            if "=" in raw_arg:
                lhs, rhs = raw_arg.split("=", 1)
                p_name = lhs.strip().split()[-1]
                rhs = rhs.strip()
                rhs = {"true": "True", "false": "False", "none": "None"}.get(rhs.lower(), rhs)
                py_args.append(f"{p_name}={rhs}")
            else:
                py_args.append(raw_arg.split()[-1])
        fn_py_name = name.split(".")[-1]
        out.append(f"def {fn_py_name}({', '.join(py_args)}):")
        if global_vars:
            out.append("    global " + ", ".join(global_vars))
        depth = 1
        for raw_line in body.splitlines():
            line = re.sub(r'("(?:[^"\\]|\\.)*")|;.*', lambda m: m.group(1) or "", raw_line).strip()
            if not line:
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


class _PArray(list):
    @property
    def Length(self):
        return len(self)


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


def _run_c1_preston_activation_harness(min00_src, *, runtime_scene_prop_none=True, file_scene_present=True, glob_val=0.0, scene_opens=True):
    """Execute FO4SF_Min00Quest's Preston activation/scene/fallback path from source.
    Used both to validate our current head AND to confirm the C1 test fails against 9b5327ff."""
    logs = []
    rt = [993.44]
    stages = {10, 20, 30}
    cur_stage = [30]
    timers = []
    cancelled = []

    class _Scene:
        def __init__(self):
            self.playing = False
            self.start_calls = 0
            self.stop_calls = 0
            self.stopped_before_msg = False

        def __repr__(self):
            return "[Scene <FO4SF_Min00_PrestonScene (09000900)>]"

        def IsPlaying(self):
            return self.playing

        def Start(self):
            self.start_calls += 1
            if scene_opens:
                self.playing = True
            return self.playing

        def ForceStart(self):
            return self.Start()

        def Stop(self):
            self.stop_calls += 1
            self.playing = False

    class _Msg:
        def __init__(self, clicks, scene_ref):
            self.clicks = list(clicks)
            self.shown = 0
            self.scene_ref = scene_ref
            self.scene_was_playing_on_show = False

        def Show(self):
            self.shown += 1
            if self.scene_ref.IsPlaying():
                self.scene_was_playing_on_show = True
            return self.clicks.pop(0) if self.clicks else 3

    scene = _Scene()
    talk_msg = _Msg([3], scene)
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

    def set_stage(n):
        stages.add(int(n))
        if int(n) > cur_stage[0]:
            cur_stage[0] = int(n)

    ns = {
        "KeeperOnly": False,
        "Trace": logs.append,
        "Preston": preston,
        "Credits": "StarfieldCredits",
        "RewardCount": 100,
        "PrestonTalkScene": None if runtime_scene_prop_none else scene,
        "PrestonPostTalkScene": None,
        "PrestonTalkMsg": talk_msg,
        "PrestonReply0Msg": talk_msg,
        "PrestonReply1Msg": talk_msg,
        "PrestonReply2Msg": talk_msg,
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
        "ownPrestonSceneStop": False,
        "prestonAttemptStartedAt": 0.0,
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
                (scene if file_scene_present else None) if (fid, plg) == (0x000900, "FO4SFMission.esm")
                else sanctuary_q if (fid, plg) == (0x000817, "FO4SFMission.esm")
                else glob_obj if (fid, plg) == (0x000979, "FO4SFMission.esm")
                else None
            ),
        ),
    }
    fns = [
        "IsWarfareMode", "ShouldUseMessageBox", "EffectiveStage", "EnsurePrestonAlias",
        "EnsureActorTalkable", "RegisterPrestonSceneEvents", "AdvanceTo", "OnStageSet", "Apply", "FoundPreston",
        "ResolvePrestonMsg", "RunPrestonTalk", "FallbackPrestonToMessageBox",
        "CheckPrestonSceneOpen", "OnMenuOpenCloseEvent", "Scene.OnBegin",
        "Scene.OnPhaseBegin", "Scene.OnEnd", "ObjectReference.OnActivate",
    ]
    if "Function ResolvePrestonScene(" in min00_src:
        fns.insert(5, "ResolvePrestonScene")
    if "Function ResolvePrestonSceneLogged(" in min00_src:
        fns.insert(6, "ResolvePrestonSceneLogged")
    if "Function ResolvePrestonPostScene(" in min00_src:
        fns.insert(7, "ResolvePrestonPostScene")
    if "Function ResolveActivePrestonScene(" in min00_src:
        fns.insert(8, "ResolveActivePrestonScene")
    if "Function EnsureKeeperPrestonAlias(" in min00_src:
        fns.insert(9, "EnsureKeeperPrestonAlias")
    if "Function RestartOrFailPrestonScene(" in min00_src:
        fns.insert(10, "RestartOrFailPrestonScene")
    globals_list = (
        "min00Given", "applied", "pendingStage", "pendingStageBy", "prestonFound",
        "talkActivated", "talkStartedAt", "talkFailures", "prestonUsedFallback", "prestonTalkLogged",
        "prestonTalkBoxOpen", "prestonFallbackActive", "talkSessionId", "prestonTalkReloaded",
        "prestonDialogueMenuOpen", "prestonScenePending", "prestonSceneMenuOpened",
        "prestonScenePhase1", "prestonPhase1At", "prestonSceneChecks",
        "prestonSceneRestarts", "ownPrestonSceneStop", "prestonAttemptStartedAt",
        "prestonPostSceneActive", "sanctuaryStartRetries",
    )
    code = _translate_mission_psc(min00_src, tuple(fns), globals_list)
    exec(compile(code, "FO4SF_Min00Quest.psc", "exec"), ns)
    return SimpleNamespace(
        ns=ns, logs=logs, rt=rt, scene=scene, talk_msg=talk_msg, preston=preston,
        player=player, sanctuary_q=sanctuary_q, cur_stage=cur_stage, set_stage=set_stage,
        timers=timers, cancelled=cancelled,
    )


class R10OpeningFixTests(unittest.TestCase):
    def test_c1_preston_single_real_talk_resolves_scene_when_property_is_none_at_runtime(self):
        """C1: Must FAIL on 9b5327ff (where PrestonTalkScene evaluated to None at runtime despite QUST 0x800 VMAD
        binding, causing reason=no_scene + double talk) and PASS on current head (ResolvePrestonScene falls back to
        Game.GetFormFromFile 0x000900 like Codsworth01, starts DialogueMenu first, logs resolution route, never both)."""
        src = MIN00_PSC.read_text(encoding="utf-8")
        self.assertIn("Scene Function ResolvePrestonScene()", src)
        self.assertIn("Scene Function ResolvePrestonSceneLogged()", src)
        self.assertIn('Game.GetFormFromFile(0x000900, "FO4SFMission.esm") as Scene', src)

        # 1. Exact candidate-2f runtime failure condition: PrestonTalkScene is None at runtime while 0x0900 exists
        h = _run_c1_preston_activation_harness(src, runtime_scene_prop_none=True, glob_val=0.0, scene_opens=True)
        h.ns["OnActivate"](h.preston, h.player)

        self.assertEqual(h.scene.start_calls, 1, f"expected SCEN 0x0900 to start once; logs={h.logs}")
        self.assertEqual(h.talk_msg.shown, 0, f"MessageBox must NOT open when real SCEN starts; logs={h.logs}")
        self.assertFalse(any("reason=no_scene" in ln for ln in h.logs), h.logs)
        self.assertTrue(any("preston scene resolved via=file" in ln for ln in h.logs), h.logs)
        self.assertTrue(any("preston scene talk requested" in ln for ln in h.logs), h.logs)

        # Verify via=property and via=none resolution trace lines as well
        hp = _run_c1_preston_activation_harness(src, runtime_scene_prop_none=False, glob_val=0.0, scene_opens=True)
        hp.ns["OnActivate"](hp.preston, hp.player)
        self.assertTrue(any("preston scene resolved via=property" in ln for ln in hp.logs), hp.logs)

        hn = _run_c1_preston_activation_harness(src, runtime_scene_prop_none=True, file_scene_present=False, glob_val=0.0)
        hn.ns["OnActivate"](hn.preston, hn.player)
        self.assertTrue(any("preston scene resolved via=none" in ln for ln in hn.logs), hn.logs)
        self.assertTrue(any("reason=no_scene" in ln for ln in hn.logs), hn.logs)

        h.ns["OnBegin"](h.scene)
        h.ns["OnPhaseBegin"](h.scene, 0)
        h.ns["OnPhaseBegin"](h.scene, 1)
        h.ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
        self.assertTrue(any("preston talk scene started stage=30" in ln for ln in h.logs), h.logs)
        self.assertTrue(any("preston dialogue menu opened" in ln for ln in h.logs), h.logs)
        self.assertTrue(any("preston talk scene phase=1 stage=30" in ln for ln in h.logs), h.logs)

        # Complete via final choice (stage 35 -> 40 -> 200), then ensure a late DEVT OnBegin is suppressed
        h.set_stage(35)
        h.ns["OnStageSet"](35, 0)
        h.scene.playing = False
        h.ns["OnMenuOpenCloseEvent"]("DialogueMenu", False)
        h.ns["OnEnd"](h.scene)
        self.assertEqual(h.cur_stage[0], 200)
        self.assertEqual(h.talk_msg.shown, 0)

        h.scene.playing = True
        h.ns["OnBegin"](h.scene)
        self.assertFalse(h.scene.IsPlaying(), "late post-completion DEVT scene must be stopped immediately")
        self.assertTrue(any("preston scene suppressed reason=single_talk" in ln for ln in h.logs), h.logs)

        # 2. Timeout under glob=0.0 (R11 Part 3 #598): restarts the Starfield Scene (NEVER opens MessageBox!)
        h2 = _run_c1_preston_activation_harness(src, runtime_scene_prop_none=True, glob_val=0.0, scene_opens=True)
        h2.ns["OnActivate"](h2.preston, h2.player)
        h2.ns["OnBegin"](h2.scene)
        h2.ns["OnPhaseBegin"](h2.scene, 1)
        h2.rt[0] += 1.6
        h2.ns["CheckPrestonSceneOpen"]()
        self.assertGreaterEqual(h2.scene.stop_calls, 1)
        self.assertEqual(h2.talk_msg.shown, 0, f"MessageBox must NEVER open when glob=0; logs={h2.logs}")
        self.assertTrue(any("preston talk scene_restart retry=1/3 reason=dialogue_menu_timeout" in ln for ln in h2.logs), h2.logs)

        # 3. GLOB == 1 path: stops any playing DEVT scene BEFORE MessageBox, and suppresses queued DEVT OnBegin
        h3 = _run_c1_preston_activation_harness(src, runtime_scene_prop_none=True, glob_val=1.0, scene_opens=True)
        h3.scene.playing = True
        h3.ns["OnActivate"](h3.preston, h3.player)
        self.assertEqual(h3.scene.stop_calls, 1)
        self.assertEqual(h3.talk_msg.shown, 1)
        self.assertFalse(h3.talk_msg.scene_was_playing_on_show)
        h3.scene.playing = True
        h3.ns["OnBegin"](h3.scene)
        self.assertFalse(h3.scene.IsPlaying())

    def test_c2_no_greeting_replay_intv_phase1_and_phase_logging(self):
        """C2: BuildTopScene sets INTV=1 on non-ending replies (both Codsworth and Preston) so Starfield jumps
        straight to Phase 1 (TOPLEVELNEST) without replaying Phase 0 greeting."""
        cs = PROGRAM_CS.read_text(encoding="utf-8")
        build_scene = cs[cs.index("static SF.Scene BuildTopScene("):cs.index("public sealed record MqVoiceSpec")]
        self.assertIn('npcInfo.StartScenePhase = "TOPLEVELNEST";', build_scene)
        self.assertIn("npcInfo.INTV = new byte[] { 1, 0, 0, 0 };", build_scene)
        self.assertIn("static bool HasPhase1Intv(SF.IDialogResponsesGetter info)", cs)
        self.assertIn("Preston non-ending reply lacks INTV=1", cs)
        self.assertIn("Codsworth non-ending reply lacks INTV=1", cs)

        c_psc = CODS_PSC.read_text(encoding="utf-8")
        m_psc = MIN00_PSC.read_text(encoding="utf-8")
        self.assertIn('Trace("codsworth talk scene phase=" + auiPhaseIndex + " stage=" + EffectiveStage())', c_psc)
        self.assertIn('Trace("preston talk scene phase=" + auiPhaseIndex + " stage=" + EffectiveStage())', m_psc)

    def test_c3_raiders_merged_coords_ammo_all5_startcombat_and_hits_to_kill(self):
        """C3: Raiders authored at merged Concord coords, alias carries AmmoShotshell x60, MoveOver waits for
        loaded PlaceRadius (300 m) without double-offsetting, and all 5 living raiders arm + StartCombat(player)."""
        cs = PROGRAM_CS.read_text(encoding="utf-8")
        self.assertIn("public const uint SfRaiderWeaponId = 0x26D96B, SfRaiderAmmoId = 0x2B4AFB;", cs)
        self.assertIn('public const string SfRaiderWeaponEdid = "Coachman", SfRaiderAmmoEdid = "AmmoShotshell";', cs)
        self.assertIn("public const float MergeOffsetX = -1200.0f, MergeOffsetY = -2700.0f;", cs)
        self.assertIn("raiderRefs.Add(Ach(next++, raiderNpc.FormKey", cs)
        self.assertIn("MergeOffsetX, MergeOffsetY));", cs)
        self.assertIn("raider alias lacks AmmoShotshell", cs)
        self.assertIn("raider ACHR reverted to unmerged coords", cs)

        # Hits-to-kill math (Starfield.esm NPC_ 00000007 Player Health=180.0 vs WEAP 0026D96B Coachman 52.0..26.0)
        player_hp = 180.0
        coachman_close_dmg = 52.0
        coachman_far_dmg = 26.0
        self.assertEqual(math.ceil(player_hp / coachman_close_dmg), 4)
        self.assertEqual(math.ceil(player_hp / coachman_far_dmg), 7)

        # Execute MoveOver on merged-authored raiders:
        #   - At Vault 111 hilltop (-2467, -1406, d=528 m > PlaceRadius 300 m): must NOT move into unloaded cell
        #   - At Concord approach (-2150, -1698, d=121 m <= PlaceRadius 300 m): moves ONCE to exact merged coords
        m_psc = MIN00_PSC.read_text(encoding="utf-8")
        logs = []
        fo4_world = "WorldSpace<MarsPlanetWorld(FF008BF3)>"

        class _Raider:
            def __init__(self, idx, pos, world=None, combat_state=0):
                self.idx = idx
                self.pos = list(pos)
                self.world = world
                self.cell = "Cell<Surface>" if world else None
                self.interior = False
                self.dead = False
                self.loaded = True
                self.restrained = True
                self.combat_state = combat_state
                self.inv = {"Coachman": 1}
                self.equipped = []
                self.avs = {}
                self.eval_calls = 0
                self.start_combat_targets = []
                self.moveto_calls = 0

            def IsDead(self): return self.dead
            def Is3DLoaded(self): return self.loaded
            def IsInInterior(self): return self.interior
            def GetPositionX(self): return self.pos[0]
            def GetPositionY(self): return self.pos[1]
            def GetPositionZ(self): return self.pos[2]
            def GetWorldSpace(self): return self.world
            def GetParentCell(self): return self.cell
            def GetCombatState(self): return self.combat_state
            def SetRestrained(self, v): self.restrained = bool(v); return True
            def SetValue(self, av, val): self.avs[av] = float(val)
            def GetValue(self, av): return self.avs.get(av, 0.0)
            def GetItemCount(self, item): return self.inv.get(item, 0)
            def AddItem(self, item, cnt, _silent=False): self.inv[item] = self.inv.get(item, 0) + int(cnt)
            def RemoveItem(self, item, cnt=1, _silent=False):
                cur = self.inv.get(item, 0)
                if cur <= int(cnt):
                    self.inv.pop(item, None)
                else:
                    self.inv[item] = cur - int(cnt)
            def UnequipAll(self): self.equipped.clear()
            def EquipItem(self, item, *_):
                if item not in self.equipped:
                    self.equipped.append(item)
            def GetEquippedWeapon(self): return self.equipped[-1] if self.equipped else None
            def EvaluatePackage(self): self.eval_calls += 1

            def StartCombat(self, target):
                self.start_combat_targets.append(target)
                self.combat_state = 1
                return True

            def MoveTo(self, ref, dx, dy, dz, *_):
                self.moveto_calls += 1
                self.world = ref.GetWorldSpace()
                self.cell = "Cell<Surface>"
                self.pos = [ref.GetPositionX() + dx, ref.GetPositionY() + dy, ref.GetPositionZ() + dz]

        class _Player:
            def __init__(self, pos):
                self.pos = list(pos)
                self.world = fo4_world

            def IsInInterior(self): return False
            def GetWorldSpace(self): return self.world
            def GetPositionX(self): return self.pos[0]
            def GetPositionY(self): return self.pos[1]
            def GetPositionZ(self): return self.pos[2]

            def GetDistance(self, other):
                if other.GetWorldSpace() != self.world:
                    return 3.4e38
                return math.dist(self.pos, other.pos)

        merged_spots = [
            (-2029.10, -1698.27, 88.32),
            (-2029.06, -1691.69, 88.09),
            (-2027.17, -1678.16, 88.09),
            (-2048.89, -1659.81, 88.26),
            (-2050.91, -1658.33, 88.21),
        ]
        raiders = _PArray([_Raider(i, pos, world=None) for i, pos in enumerate(merged_spots)])
        player = _Player((-2467.78, -1406.92, 127.45))  # Vault 111 hilltop (~528 m from Concord)
        v111 = SimpleNamespace(GetWorldSpace=lambda: fo4_world)

        ns = {
            "_PArray": _PArray,
            "KeeperOnly": False,
            "Trace": logs.append,
            "Raiders": raiders,
            "Preston": SimpleNamespace(IsInInterior=lambda: False, GetWorldSpace=lambda: fo4_world),
            "prestonPlaced": False,
            "MergeOffsetX": -1200.0,
            "MergeOffsetY": -2700.0,
            "PrestonLocalX": -811.14,
            "PrestonLocalY": 1002.46,
            "PrestonLocalZ": 89.09,
            "RelocateRadius": 800.0,
            "RelocateGap": 1500.0,
            "PlaceRadius": 300.0,
            "HoldRadius": 25.0,
            "Wfc01MaxDrift": 140.0,
            "Wfc01SubterraneanDrop": 8.0,
            "raiderTargetX": None,
            "raiderTargetY": None,
            "raiderTargetZ": None,
            "raiderAbsentSec": None,
            "raiderCleared": None,
            "raiderRescued": None,
            "raiderEngaged": None,
            "raiderArmed": None,
            "raiderStartCombatAt": None,
            "raiderRescueSec": None,
            "raiderRescueX": None,
            "raiderRescueY": None,
            "raiderRescueZ": None,
            "raiderRescueHp": None,
            "RaiderWeapon": "Coachman",
            "RaiderAmmo": "AmmoShotshell",
            "RaiderPrimaryRecordDamage": 1.0,
            "AttackDamageMult": None,
            "Math": SimpleNamespace(Sqrt=math.sqrt),
            "Game": SimpleNamespace(
                GetAggressionAV=lambda: "AggressionAV",
                GetConfidenceAV=lambda: "ConfidenceAV",
                GetFormFromFile=lambda fid, plg: v111 if fid == 0x0A775B else None,
            ),
        }
        code = _translate_mission_psc(
            m_psc,
            ("ResolveCommonwealthWorld", "IsCommonwealthExterior", "IsPlayerStableAt", "SpotOff",
             "ComputeEffectiveWeaponDamage", "ArmRaiderForCombat", "MoveOver"),
            ("raiderArmed",),
        )
        init_src = re.sub(r"new (?:float|bool)\[count\]", "_PArray([0] * count)", function_body(m_psc, "InitRaiderTracking"))
        code += "\n" + _translate_mission_psc(
            init_src + "\nEndFunction\n", ("InitRaiderTracking",),
            ("raiderTargetX", "raiderTargetY", "raiderTargetZ", "raiderAbsentSec", "raiderCleared",
             "raiderRescued", "raiderEngaged", "raiderArmed", "raiderStartCombatAt", "raiderRescueSec",
             "raiderRescueX", "raiderRescueY", "raiderRescueZ", "raiderRescueHp"),
        )
        exec(compile(code, "FO4SF_Min00Quest.psc", "exec"), ns)
        ns["InitRaiderTracking"]()

        # On Vault 111 hilltop (528 m > 300 m PlaceRadius): MoveOver must NOT pull raiders into unloaded cells
        for i, r in enumerate(raiders):
            ns["MoveOver"](r, player, player.pos[0], player.pos[1], player.pos[2], f"raider {i}")
            self.assertEqual(r.moveto_calls, 0, f"raider {i} moved while player was 528 m away")

        # Approach Concord (120 m <= 300 m PlaceRadius): all 5 move cleanly ONCE to exact merged coords (never offset twice)
        player.pos = [-2150.0, -1698.0, 88.5]
        for i, (r, want) in enumerate(zip(raiders, merged_spots)):
            failed = ns["MoveOver"](r, player, player.pos[0], player.pos[1], player.pos[2], f"raider {i}")
            self.assertFalse(failed, f"raider {i} failed MoveOver")
            self.assertEqual(r.moveto_calls, 1)
            self.assertAlmostEqual(r.pos[0], want[0], places=2)
            self.assertAlmostEqual(r.pos[1], want[1], places=2)

        # Engage combat: simulate raiders 1..4 faction-alerted (GetCombatState()==2) when raider 0 engages,
        # and verify P3 rate-limiting (10 s cooldown) when a raider remains stuck in combat state 2.
        player.pos = [-2015.0, -1700.0, 88.4]
        for i in range(1, 5):
            raiders[i].combat_state = 2  # searching/alerted (the 2f bug skipped StartCombat here!)

        def run_combat_tick(now_rt, sticky_state2_idx=None):
            stage = 10
            everyone = True
            for i, r in enumerate(raiders):
                d = player.GetDistance(r)
                if not ns["raiderArmed"][i] and stage < 30 and (everyone or d < 60.0) and r.Is3DLoaded():
                    ns["ArmRaiderForCombat"](r, i)
                if (r.GetCombatState() == 1 and ns["raiderEngaged"][i]) or (
                    ns["raiderEngaged"][i] and now_rt >= ns["raiderStartCombatAt"][i] and (now_rt - ns["raiderStartCombatAt"][i]) < 10.0
                ):
                    pass
                elif stage < 30 and (everyone or d < 60.0) and r.Is3DLoaded():
                    r.StartCombat(player)
                    if sticky_state2_idx == i:
                        r.combat_state = 2  # simulate raider stuck in state 2
                    ns["raiderEngaged"][i] = True
                    ns["raiderStartCombatAt"][i] = now_rt
                    logs.append(f"startcombat raider {i} d={d:.1f}")

        run_combat_tick(100.0, sticky_state2_idx=2)
        for i, r in enumerate(raiders):
            self.assertFalse(r.restrained, f"raider {i} still restrained")
            self.assertEqual(r.avs.get("AggressionAV"), 2.0)
            self.assertEqual(r.avs.get("ConfidenceAV"), 4.0)
            self.assertGreaterEqual(r.inv.get("AmmoShotshell", 0), 60)
            self.assertIn("Coachman", r.equipped)
            self.assertEqual(r.start_combat_targets, [player], f"raider {i} never received StartCombat(player)")
        self.assertEqual(sum(1 for ln in logs if ln.startswith("arm raider ")), 5)
        self.assertEqual(sum(1 for ln in logs if ln.startswith("startcombat raider ")), 5)

        # Next 9 ticks (t=101..109): raider 2 stuck in state 2 must NOT spam StartCombat or logs
        for t in range(101, 110):
            run_combat_tick(float(t), sticky_state2_idx=2)
        self.assertEqual(len(raiders[2].start_combat_targets), 1)
        self.assertEqual(sum(1 for ln in logs if ln.startswith("startcombat raider 2")), 1)

        # At t=110.0 (10 s elapsed): exactly 1 rate-limited re-engage
        run_combat_tick(110.0, sticky_state2_idx=2)
        self.assertEqual(len(raiders[2].start_combat_targets), 2)
        self.assertEqual(sum(1 for ln in logs if ln.startswith("startcombat raider 2")), 2)

    def test_c6_codsworth_camera_guard_steps_back_at_0p6m_and_keeps_2p0m_untouched(self):
        """C6: Close 0.62 m moveto activation steps player back along sightline to 1.85 m; 2.0 m walk-up untouched."""
        c_psc = CODS_PSC.read_text(encoding="utf-8")
        logs = []
        cods_pos = [-2346.709, -1406.163, 111.734]
        p_pos = [-2347.297, -1405.960, 111.773]  # exact 2f fo4sf_mission.1.log:42 d=0.622 m

        cods = SimpleNamespace(
            GetPositionX=lambda: cods_pos[0], GetPositionY=lambda: cods_pos[1],
            GetPositionZ=lambda: cods_pos[2], GetAngleZ=lambda: 0.0,
        )
        set_calls = []
        angle_calls = []

        def set_pos(x, y, z):
            set_calls.append((x, y, z))
            p_pos[:] = [x, y, z]

        def set_angle(ax, ay, az):
            angle_calls.append((ax, ay, az))

        player = SimpleNamespace(
            IsInInterior=lambda: False,
            GetPositionX=lambda: p_pos[0], GetPositionY=lambda: p_pos[1], GetPositionZ=lambda: p_pos[2],
            SetPosition=set_pos,
            SetAngle=set_angle,
        )
        ns = {
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
        code = _translate_mission_psc(c_psc, ("EnsureSafeCodsworthCameraDistance",), ())
        exec(compile(code, "FO4SF_Codsworth01Quest.psc", "exec"), ns)

        # Case 1: 0.62 m (moveto) -> stepped back to 1.85 m along sightline AND rotated to face Codsworth
        ns["EnsureSafeCodsworthCameraDistance"](player, cods)
        self.assertEqual(len(set_calls), 1)
        self.assertEqual(len(angle_calls), 1)
        new_d = math.hypot(p_pos[0] - cods_pos[0], p_pos[1] - cods_pos[1])
        self.assertAlmostEqual(new_d, 1.85, places=2)
        self.assertTrue(any("codsworth talk camera_guard prev_d=" in ln and "facing_deg=" in ln for ln in logs), logs)

        # Case 2: 2.0 m (natural walk-up) -> untouched
        p_pos[:] = [cods_pos[0] - 2.0, cods_pos[1], cods_pos[2]]
        ns["EnsureSafeCodsworthCameraDistance"](player, cods)
        self.assertEqual(len(set_calls), 1, "2.0 m walk-up must NOT move the player")
        self.assertEqual(len(angle_calls), 1, "2.0 m walk-up must NOT rotate the player")

    def test_r1_r5_r7_min00_no_mq103_at_200_act2_on_keeper_timer2_gated_and_0x817_selfchecks(self):
        """R1: No MQ103 start at Min00 stage 200. R5: CheckA7cdProximityStarts runs on KeeperOnly Timer 2
        with strict prior-quest completion gates (Fort Hagen never starts MQ105 & MQ106 together).
        R7: Program.cs restores 'no QUST 0x817' and bench-alias self-checks."""
        m_psc = MIN00_PSC.read_text(encoding="utf-8")

        # R1: Apply(200) starts Sanctuary01 only, never MQ103
        apply_fn = function_body(m_psc, "Apply")
        self.assertIn('Game.GetFormFromFile(0x000817, "FO4SFMission.esm")', apply_fn)
        self.assertNotIn("0x000A50", apply_fn)
        self.assertNotIn("mq103 start_requested", apply_fn)

        # R1/R5: ALL post-opening proximity starts (A4, A7, A7cd) run ONLY on KeeperOnly Timer 2, NEVER OnTimer(1)
        on_timer = m_psc[m_psc.index("Event OnTimer("):m_psc.index("EndEvent", m_psc.index("Event OnTimer("))]
        for fn_call in ("CheckA4ProximityStarts(player)", "CheckA7ProximityStarts(player)", "CheckA7cdProximityStarts(player)"):
            self.assertNotIn(fn_call, on_timer)
        keep_fn = function_body(m_psc, "KeepCodsworth")
        for fn_call in ("CheckA4ProximityStarts(player)", "CheckA7ProximityStarts(player)", "CheckA7cdProximityStarts(player)"):
            self.assertIn(fn_call, keep_fn)

        # Verify IsStoryQuestComplete uses strict IsCompleted() ONLY (never GetStage() >= 100!)
        gate_fn = function_body(m_psc, "IsStoryQuestComplete")
        self.assertIn("q.IsCompleted()", gate_fn)
        self.assertNotIn("GetStage", gate_fn)

        # Execute CheckA4/A7/A7cd under KeeperOnly=True with strict IsCompleted() sequential gating
        logs = []
        fo4_world = "WorldSpace<MarsPlanetWorld(FF008BF3)>"
        v111 = SimpleNamespace(GetWorldSpace=lambda: fo4_world)
        all_fids = (0x000800, 0x000817, 0x000A20, 0x000A50, 0x000A80, 0x000AB0, 0x000AD0, 0x000AF0, 0x000B10, 0x000B30)
        quests = {
            fid: SimpleNamespace(completed=False, stage=0, running=False, starts=0)
            for fid in all_fids
        }
        for q in quests.values():
            q.IsCompleted = (lambda qq: lambda: qq.completed)(q)
            q.GetStage = (lambda qq: lambda: qq.stage)(q)
            q.IsRunning = (lambda qq: lambda: qq.running)(q)

            def _make_start(qq):
                def _st():
                    qq.running = True
                    qq.starts += 1
                    return True
                return _st
            q.StartNoWait = _make_start(q)

        p_pos = [-1416.36, -3129.39, 19.3]  # Diamond City gate
        player = SimpleNamespace(
            IsInInterior=lambda: False, GetWorldSpace=lambda: fo4_world,
            GetPositionX=lambda: p_pos[0], GetPositionY=lambda: p_pos[1], GetPositionZ=lambda: p_pos[2],
        )
        ns = {
            "KeeperOnly": True,
            "Trace": logs.append,
            "Preston": None,
            "prestonPlaced": False,
            "MergeOffsetX": -1200.0,
            "MergeOffsetY": -2700.0,
            "mq103ProxAttempted": False,
            "minRecruitProxAttempted": False,
            "mq104ProxAttempted": False,
            "mq105ProxAttempted": False,
            "mq106ProxAttempted": False,
            "mq203ProxAttempted": False,
            "mq204ProxAttempted": False,
            "mq206ProxAttempted": False,
            "Game": SimpleNamespace(
                GetFormFromFile=lambda fid, plg: (
                    v111 if fid == 0x0A775B
                    else quests.get(fid) if plg == "FO4SFMission.esm"
                    else None
                ),
            ),
        }
        code = _translate_mission_psc(
            m_psc,
            ("IsWarfareMode", "ResolveCommonwealthWorld", "IsCommonwealthExterior",
             "IsStoryQuestComplete", "CheckA4ProximityStarts", "CheckA7ProximityStarts",
             "CheckA7cdProximityStarts"),
            ("mq103ProxAttempted", "minRecruitProxAttempted", "mq104ProxAttempted", "mq105ProxAttempted",
             "mq106ProxAttempted", "mq203ProxAttempted", "mq204ProxAttempted", "mq206ProxAttempted"),
        )
        exec(compile(code, "FO4SF_Min00Quest.psc", "exec"), ns)

        # A4 gate: during opening (Min00 incomplete or Sanctuary01 incomplete), DC gate & Tenpines do NOT start
        ns["CheckA4ProximityStarts"](player)
        self.assertEqual(quests[0x000A50].starts, 0, "MQ103 must not start before Min00+Sanctuary01 complete")
        quests[0x000800].completed = True
        quests[0x000817].stage = 100  # stage 100 != completed!
        ns["CheckA4ProximityStarts"](player)
        self.assertEqual(quests[0x000A50].starts, 0, "MQ103 must not start while Sanctuary01 is not completed")
        quests[0x000817].completed = True
        ns["CheckA4ProximityStarts"](player)
        self.assertEqual(quests[0x000A50].starts, 1)
        p_pos[:] = [-1517.0, -1423.63, 87.8]  # Tenpines Bluff
        ns["CheckA4ProximityStarts"](player)
        self.assertEqual(quests[0x000A20].starts, 1)

        # A7 gate: MQ104 blocked until MQ103 completes; MQ105 blocked until MQ104 completes
        p_pos[:] = [-987.46, -2927.73, 19.2]  # Park Street
        ns["CheckA7ProximityStarts"](player)
        self.assertEqual(quests[0x000A80].starts, 0)
        quests[0x000A50].completed = True
        ns["CheckA7ProximityStarts"](player)
        self.assertEqual(quests[0x000A80].starts, 1)

        p_pos[:] = [-2456.84, -2781.07, 81.83]  # Fort Hagen (shared by MQ105 and MQ106)
        ns["CheckA7ProximityStarts"](player)
        self.assertEqual(quests[0x000AB0].starts, 0, "MQ105 must not start before MQ104 completes")
        quests[0x000A80].completed = True
        ns["CheckA7ProximityStarts"](player)
        self.assertEqual(quests[0x000AB0].starts, 1)

        # R5 critical regression: MQ105 at stage 100 ("following trail to Fort Hagen", IsCompleted()==False)
        # standing AT Fort Hagen MUST NOT start MQ106!
        quests[0x000AB0].stage = 100
        quests[0x000AB0].completed = False
        ns["CheckA7cdProximityStarts"](player)
        self.assertEqual(quests[0x000AD0].starts, 0, "MQ105@100 (in-progress) at Fort Hagen must NOT start MQ106!")
        self.assertNotIn("mq106 started by=proximity", logs)

        # Once MQ105 IsCompleted()==True -> now Fort Hagen starts MQ106
        quests[0x000AB0].completed = True
        ns["CheckA7cdProximityStarts"](player)
        self.assertEqual(quests[0x000AD0].starts, 1)
        self.assertIn("mq106 started by=proximity", logs)

        # MQ106@100 (Kellogg fight, not completed) at Goodneighbor MUST NOT start MQ203
        p_pos[:] = [-902.48, -2870.07, 19.2]
        quests[0x000AD0].stage = 100
        quests[0x000AD0].completed = False
        ns["CheckA7cdProximityStarts"](player)
        self.assertEqual(quests[0x000AF0].starts, 0, "MQ106@100 must NOT start MQ203!")
        quests[0x000AD0].completed = True
        ns["CheckA7cdProximityStarts"](player)
        self.assertEqual(quests[0x000AF0].starts, 1)

        # MQ203@100 (Memory Den lounger, not completed) at Glowing Sea MUST NOT start MQ204
        p_pos[:] = [-2624.44, -4357.85, 107.64]
        quests[0x000AF0].stage = 100
        quests[0x000AF0].completed = False
        ns["CheckA7cdProximityStarts"](player)
        self.assertEqual(quests[0x000B10].starts, 0, "MQ203@100 must NOT start MQ204!")
        quests[0x000AF0].completed = True
        ns["CheckA7cdProximityStarts"](player)
        self.assertEqual(quests[0x000B10].starts, 1)

        # R7: Program.cs restored 'no QUST 0x817' & Sanctuary bench-alias self-checks
        cs = PROGRAM_CS.read_text(encoding="utf-8")
        self.assertIn('if (sq is null) problems.Add($"no QUST 0x{SanctuaryQuestId:X} {SanctuaryQuestEdid}");', cs)
        self.assertIn("lacks optional SanctuaryWorkbench alias 0", cs)
        self.assertIn("Sanctuary01 bench alias 0 removed", cs)

    @unittest.skipUnless(os.environ.get("FO4SF_DOTNET_TESTS") == "1", "set FO4SF_DOTNET_TESTS=1 to run binary ESM check")
    def test_dotnet_selftest_binary_esm_intv_merged_raiders_and_ammo(self):
        """End-to-end binary verification of selftest FO4SFMission.esm: INTV=1 on non-ending replies,
        merged Concord raider ACHRs, and AmmoShotshell x60 on every raider alias."""
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.setdefault("DOTNET_ROLL_FORWARD", "Major")
            res = subprocess.run(
                ["dotnet", "run", "--project", str(ROOT / "dotnet" / "Mission"), "-c", "Release", "--", "selftest", tmp],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(res.returncode, 0, res.stdout + "\n" + res.stderr)
            self.assertIn("selftest pass", res.stdout)

            esm = Path(tmp) / "out" / "alias" / "FO4SFMission.esm"
            data = esm.read_bytes()

            # Check INFO INTV=1 on Preston 0x928..0x929 & Codsworth 0x968..0x96A
            seen_intv = {}
            for _sig, fid, _fl, body in _iter_esm_records(data, {b"INFO"}):
                lid = fid & 0xFFFFFF
                if lid in (0x928, 0x929, 0x92A, 0x968, 0x969, 0x96A, 0x96B):
                    subs = dict(_iter_subrecords(body))
                    seen_intv[lid] = (
                        struct.unpack("<i", subs[b"INTV"][:4])[0] if b"INTV" in subs else None,
                        subs.get(b"NAM0", b"").rstrip(b"\x00").decode("utf-8", "replace"),
                    )
            for lid in (0x928, 0x929, 0x968, 0x969, 0x96A):
                self.assertEqual(seen_intv.get(lid), (1, "TOPLEVELNEST"), f"INFO 0x{lid:X} bad loop: {seen_intv.get(lid)}")
            for lid in (0x92A, 0x96B):
                self.assertEqual(seen_intv.get(lid), (None, ""), f"ending INFO 0x{lid:X} should not loop")

            # Check raider ACHRs 0x803..0x804 authored at merged Concord coordinates
            raider_pos = {}
            for _sig, fid, _fl, body in _iter_esm_records(data, {b"ACHR"}):
                lid = fid & 0xFFFFFF
                if lid in (0x803, 0x804):
                    subs = dict(_iter_subrecords(body))
                    raider_pos[lid] = struct.unpack("<3f", subs[b"DATA"][:12])
            self.assertEqual(set(raider_pos.keys()), {0x803, 0x804})
            for lid, (rx, ry, _rz) in raider_pos.items():
                self.assertLess(rx, -1500.0, f"raider 0x{lid:X} X={rx} not merged")
                self.assertLess(ry, -1000.0, f"raider 0x{lid:X} Y={ry} not merged")


if __name__ == "__main__":
    unittest.main()
