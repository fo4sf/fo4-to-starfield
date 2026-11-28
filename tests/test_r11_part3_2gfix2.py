"""Round 11 Part 3 Step 1 Slice 1A unit & binary ESM tests for candidate-2g-fix2 (#598 / #609):
- E1: Remove Game.StopDialogueCamera(False, True) regression from FO4SF_Codsworth01Quest.psc (keep 2g race default),
- E2: EnsureSafeCodsworthCameraDistance rotates player to face Codsworth via SetAngle(0, 0, facingDeg) + logs facing_deg=,
- Item 3: Zero MessageBox fallback when TalkUseMessageBox (0x0979) == 0; bounded 1..3 scene restarts + loud ERROR,
- Item 4: Repeatable voiced post-mission Starfield Scenes on FO4SF_CodsworthKeeper (0x0814):
          FO4SF_PrestonPostScene (0x0990, alias 0, GetStage >= 200) and
          FO4SF_CodsworthPostScene (0x09C0, alias 1, GetStage >= 100),
- Item 5 (E3): Softened 3-dmg FO4SF_ConcordRaiderSidearm (WEAP 0x097A, AmmoList cleared) + deterministic sidearm_ammo=36,
- Item 6 (E5): Dead Concord raiders preserved/rescued across cold reload (wfc01 rescue_dead) at stage 20/30/200 & KeepPreston.

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
        body = re.sub(r"new\s+(?:float|bool|int)\[(\w+)\]", r"_PArray([0] * \1)", body)
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


class _SceneMock:
    def __init__(self, label, starts=True):
        self.label = label
        self.starts = starts
        self.playing = False
        self.start_calls = 0
        self.force_calls = 0
        self.stop_calls = 0

    def __repr__(self):
        return self.label

    def IsPlaying(self):
        return self.playing

    def Start(self):
        self.start_calls += 1
        if self.starts:
            self.playing = True
        return self.playing

    def ForceStart(self):
        self.force_calls += 1
        if self.starts:
            self.playing = True
        return self.playing

    def Stop(self):
        self.stop_calls += 1
        self.playing = False


class _MsgMock:
    def __init__(self, clicks=(3,)):
        self.clicks = list(clicks)
        self.shown = 0

    def Show(self):
        self.shown += 1
        return self.clicks.pop(0) if self.clicks else 3


class _AliasMock:
    def __init__(self):
        self.actor = None
        self.force_calls = 0

    def GetActorRef(self):
        return self.actor

    def ForceRefTo(self, a):
        self.actor = a
        self.force_calls += 1


class R11Part3Slice1ATests(unittest.TestCase):
    def test_e1_codsworth_removes_stop_dialogue_camera_and_keeps_2g_race_default(self):
        """E1: Game.StopDialogueCamera is completely removed from FO4SF_Codsworth01Quest.psc;
        --codsworth-race-framing stays default false (exact 2g race)."""
        c_psc = CODS_PSC.read_text(encoding="utf-8")
        cs = MISSION_CS.read_text(encoding="utf-8")
        self.assertNotIn("StopDialogueCamera", c_psc)
        self.assertNotIn("dialogue_camera stopped", c_psc)
        self.assertIn('Mission.BoolFlag(args, "--codsworth-race-framing", false)', cs)

        logs = []
        stop_cam = []
        scene = _SceneMock("FO4SF_Codsworth01_Scene(09000940)")
        post_scene = _SceneMock("FO4SF_CodsworthPostScene(090009C0)")
        ns = {
            "_PStr": _PStr,
            "Trace": logs.append,
            "CodsworthScene": scene,
            "CodsworthPostScene": post_scene,
            "SceneOpenCheckSeconds": 1.5,
            "sceneTalkPending": True,
            "sceneMenuOpened": False,
            "dialogueMenuOpen": False,
            "scenePhase1Entered": False,
            "scenePhase1At": 0.0,
            "applied": 10,
            "GetStage": lambda: 10,
            "StartTimer": lambda *_: None,
            "CancelTimer": lambda *_: None,
            "Utility": SimpleNamespace(GetCurrentRealTime=lambda: 50.0),
            "Game": SimpleNamespace(
                GetFormFromFile=lambda *_: None,
                StopDialogueCamera=lambda *a: stop_cam.append(a),
            ),
        }
        code = _translate_psc(
            c_psc,
            ("EffectiveStage", "ResolveCodsworthScene", "ResolveCodsworthPostScene", "Scene.OnPhaseBegin"),
            ("sceneTalkPending", "sceneMenuOpened", "dialogueMenuOpen", "scenePhase1Entered", "scenePhase1At", "applied"),
        )
        exec(compile(code, "FO4SF_Codsworth01Quest.psc", "exec"), ns)
        for ph in (0, 1, 2, 2):
            ns["OnPhaseBegin"](scene, ph)
            ns["OnPhaseBegin"](post_scene, ph)
        self.assertEqual(stop_cam, [])
        self.assertFalse(any("dialogue_camera" in ln for ln in logs), logs)

    def test_e2_codsworth_camera_guard_faces_codsworth_all_quadrants_and_keeps_walkup(self):
        """E2: EnsureSafeCodsworthCameraDistance calls player.SetAngle(0, 0, facingDeg) aimed toward Codsworth
        for all 4 quadrants + 4 cardinal directions + zero-distance overlap, logs facing_deg=, and leaves >= 1.65 m untouched."""
        c_psc = CODS_PSC.read_text(encoding="utf-8")
        self.assertIn("player.SetAngle(0.0, 0.0, facingDeg)", c_psc)
        self.assertIn("facing_deg=", c_psc)

        cods_pos = [-2346.709, -1406.163, 111.734]
        code = _translate_psc(c_psc, ("EnsureSafeCodsworthCameraDistance",), ())

        def run_case(offset_xy, cods_z_angle=0.0):
            logs = []
            p_pos = [cods_pos[0] + offset_xy[0], cods_pos[1] + offset_xy[1], cods_pos[2]]
            pos_calls = []
            angle_calls = []

            def set_pos(x, y, z):
                pos_calls.append((x, y, z))
                p_pos[:] = [x, y, z]

            def set_angle(ax, ay, az):
                angle_calls.append((ax, ay, az))

            cods = SimpleNamespace(
                GetPositionX=lambda: cods_pos[0], GetPositionY=lambda: cods_pos[1],
                GetPositionZ=lambda: cods_pos[2], GetAngleZ=lambda: cods_z_angle,
            )
            player = SimpleNamespace(
                IsInInterior=lambda: False,
                GetPositionX=lambda: p_pos[0], GetPositionY=lambda: p_pos[1], GetPositionZ=lambda: p_pos[2],
                SetPosition=set_pos, SetAngle=set_angle,
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
            exec(compile(code, "FO4SF_Codsworth01Quest.psc", "exec"), ns)
            ns["EnsureSafeCodsworthCameraDistance"](player, cods)
            return p_pos, pos_calls, angle_calls, logs

        # Test all 4 quadrants + 4 cardinals + zero-distance overlap
        close_offsets = [
            (0.6, 0.5),    # NE -> player steps NE, faces SW
            (0.5, -0.5),   # SE -> player steps SE, faces NW (315 deg)
            (-0.6, -0.4),  # SW -> player steps SW, faces NE
            (-0.45, 0.45), # NW (wall_avoid redirects to street) -> still faces Codsworth!
            (0.0, 0.6),    # N
            (0.6, 0.0),    # E
            (0.0, -0.6),   # S
            (-0.6, 0.0),   # W
            (0.0, 0.0),    # exact overlap
        ]
        for off in close_offsets:
            p_pos, pos_calls, angle_calls, logs = run_case(off, cods_z_angle=45.0)
            self.assertEqual(len(pos_calls), 1, f"off={off}")
            self.assertEqual(len(angle_calls), 1, f"off={off}")
            ax, ay, facing = angle_calls[0]
            self.assertEqual((ax, ay), (0.0, 0.0))
            self.assertTrue(0.0 <= facing < 360.0, f"facing out of [0,360): {facing} for off={off}")
            to_x = cods_pos[0] - p_pos[0]
            to_y = cods_pos[1] - p_pos[1]
            dist = math.hypot(to_x, to_y)
            self.assertAlmostEqual(dist, 1.85, places=2, msg=f"off={off}")
            # CE Z heading: sin(deg) == to_x / dist, cos(deg) == to_y / dist
            self.assertAlmostEqual(math.sin(math.radians(facing)), to_x / dist, places=2, msg=f"off={off} facing={facing}")
            self.assertAlmostEqual(math.cos(math.radians(facing)), to_y / dist, places=2, msg=f"off={off} facing={facing}")
            self.assertTrue(any("facing_deg=" in ln for ln in logs), logs)

        # Normal walk-up (2.0 m >= 1.65 m): zero SetPosition and zero SetAngle
        _, pos_calls, angle_calls, logs = run_case((1.4, -1.5))
        self.assertEqual(pos_calls, [])
        self.assertEqual(angle_calls, [])
        self.assertEqual(logs, [])

    def _build_talk_harnesses(self, *, glob_val=0.0, cods_starts=True, preston_starts=True,
                              cods_post_starts=True, preston_post_starts=True,
                              cods_scene_none=False, preston_scene_none=False):
        c_psc = CODS_PSC.read_text(encoding="utf-8")
        m_psc = MIN00_PSC.read_text(encoding="utf-8")
        logs = []
        rt = [100.0]

        class _Actor:
            def __init__(self, name, pos):
                self.name = name
                self.pos = list(pos)
                self.allow_pc = 0
                self.unblock = 0
                self.disabled = False
                self.dead = False

            def __repr__(self): return self.name
            def AllowPCDialogue(self, v):
                if v: self.allow_pc += 1
            def BlockActivation(self, b, _h=False):
                if not b: self.unblock += 1
            def IgnoreFriendlyHits(self, *_): pass
            def StopCombat(self): pass
            def IsDisabled(self): return self.disabled
            def IsDead(self): return self.dead
            def Is3DLoaded(self): return True
            def IsDeleted(self): return False
            def GetPositionX(self): return self.pos[0]
            def GetPositionY(self): return self.pos[1]
            def GetPositionZ(self): return self.pos[2]
            def SetPosition(self, x, y, z): self.pos = [float(x), float(y), float(z)]
            def GetAngleZ(self): return 0.0
            def SetScale(self, *_): pass
            def EnableNoWait(self, *_): return True
            def DisableNoWait(self, *_): pass
            def PlaceAtMe(self, *_): return _Actor("CodsworthTalkProxy(09000970)", tuple(self.pos))

        player_pos = [-2345.0, -1408.0, 111.8]
        player = SimpleNamespace(
            IsInInterior=lambda: False,
            GetPositionX=lambda: player_pos[0], GetPositionY=lambda: player_pos[1], GetPositionZ=lambda: player_pos[2],
            SetPosition=lambda x, y, z: player_pos.__setitem__(slice(None), [float(x), float(y), float(z)]),
            SetAngle=lambda *_: None,
            AddItem=mock.MagicMock(),
        )
        cods = _Actor("Codsworth(09000811)", (-2346.709, -1406.163, 111.734))
        preston = _Actor("Preston(09000802)", (-2011.14, -1697.54, 89.09))
        cods_scn = None if cods_scene_none else _SceneMock("FO4SF_Codsworth01_Scene(09000940)", starts=cods_starts)
        cods_post = None if cods_scene_none else _SceneMock("FO4SF_CodsworthPostScene(090009C0)", starts=cods_post_starts)
        preston_scn = None if preston_scene_none else _SceneMock("FO4SF_Min00_PrestonScene(09000900)", starts=preston_starts)
        preston_post = None if preston_scene_none else _SceneMock("FO4SF_PrestonPostScene(09000990)", starts=preston_post_starts)

        cods_alias = _AliasMock()
        preston_alias = _AliasMock()
        keeper_a0 = _AliasMock()
        keeper_a1 = _AliasMock()
        keeper_q = SimpleNamespace(
            IsRunning=lambda: True, Start=lambda: True, StartNoWait=lambda: True,
            GetAlias=lambda idx: keeper_a0 if idx == 0 else keeper_a1 if idx == 1 else None,
        )
        sanctuary_q = SimpleNamespace(IsRunning=lambda: False, StartNoWait=mock.MagicMock(return_value=True))
        glob_obj = SimpleNamespace(GetValue=lambda: float(glob_val))

        c_msg = _MsgMock([3, 3, 3])
        p_msg = _MsgMock([3, 3, 3])
        m_stages = set()
        m_cur = [0]
        m_timers = []
        m_cancels = []
        m_menu_regs = []
        m_remote_regs = []
        wfc_calls = []

        def m_set_stage(n):
            m_stages.add(int(n))
            if int(n) > m_cur[0]:
                m_cur[0] = int(n)

        m_ns = {
            "_PStr": _PStr,
            "Trace": logs.append,
            "LogName": "fo4sf_mission",
            "KeeperOnly": False,
            "Preston": preston,
            "Codsworth": cods,
            "Credits": "Credits",
            "RewardCount": 100,
            "PrestonTalkScene": preston_scn,
            "PrestonPostTalkScene": preston_post,
            "PrestonTalkMsg": p_msg,
            "PrestonReply0Msg": p_msg,
            "PrestonReply1Msg": p_msg,
            "PrestonReply2Msg": p_msg,
            "TalkUseMessageBox": glob_obj,
            "PrestonSceneCheckSeconds": 1.5,
            "PrestonSceneMaxWaitChecks": 16,
            "PrestonMaxSceneRestarts": 3,
            "min00Given": False,
            "applied": 0,
            "pendingStage": -1,
            "pendingStageBy": "other",
            "prestonFound": False,
            "talkActivated": False,
            "talkStartedAt": 0.0,
            "talkNearSec": 0.0,
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
            "relocateFails": 0,
            "prestonHeld": False,
            "IsRunning": lambda: True,
            "Start": lambda: True,
            "IsCompleted": lambda: m_cur[0] >= 200,
            "GetStage": lambda: m_cur[0],
            "GetStageDone": lambda s: int(s) in m_stages,
            "SetStage": m_set_stage,
            "GetAlias": lambda idx: preston_alias if idx == 0 else None,
            "SetObjectiveDisplayed": lambda *_: None,
            "SetObjectiveCompleted": lambda *_: None,
            "SetActive": lambda *_: None,
            "StartTimer": lambda sec, tid: m_timers.append((float(sec), int(tid))),
            "CancelTimer": lambda tid: m_cancels.append(int(tid)),
            "CompleteQuest": mock.MagicMock(),
            "RegisterForRemoteEvent": lambda o, ev: m_remote_regs.append((o, ev)),
            "RegisterForMenuOpenCloseEvent": lambda m: m_menu_regs.append(m),
            "Debug": SimpleNamespace(OpenUserLog=lambda *_: None),
            "InitRaiderTracking": lambda: None,
            "CheckConcordRaidersWfc01": lambda p, adv: wfc_calls.append(adv),
            "Utility": SimpleNamespace(GetCurrentRealTime=lambda: rt[0]),
            "Game": SimpleNamespace(
                GetPlayer=lambda: player,
                GetFormFromFile=lambda fid, plg: (
                    sanctuary_q if (fid, plg) == (0x000817, "FO4SFMission.esm")
                    else keeper_q if (fid, plg) == (0x000814, "FO4SFMission.esm")
                    else preston_scn if (fid, plg) == (0x000900, "FO4SFMission.esm")
                    else preston_post if (fid, plg) == (0x000990, "FO4SFMission.esm")
                    else glob_obj if (fid, plg) == (0x000979, "FO4SFMission.esm")
                    else None
                ),
            ),
        }
        m_code = _translate_psc(
            m_psc,
            ("IsWarfareMode", "ShouldUseMessageBox", "EffectiveStage", "EnsurePrestonAlias",
             "EnsureKeeperPrestonAlias", "EnsureActorTalkable", "ResolvePrestonScene",
             "ResolvePrestonSceneLogged", "ResolvePrestonPostScene", "ResolveActivePrestonScene",
             "RegisterPrestonSceneEvents", "GiveFromCodsworth", "Actor.OnPlayerLoadGame",
             "AdvanceTo", "OnStageSet", "Apply", "FoundPreston", "ResolvePrestonMsg",
             "RunPrestonTalk", "FallbackPrestonToMessageBox", "RestartOrFailPrestonScene",
             "CheckPrestonSceneOpen", "OnMenuOpenCloseEvent", "Scene.OnBegin",
             "Scene.OnPhaseBegin", "Scene.OnEnd", "ObjectReference.OnActivate"),
            ("min00Given", "applied", "pendingStage", "pendingStageBy", "prestonFound",
             "talkActivated", "talkStartedAt", "talkNearSec", "talkFailures",
             "prestonUsedFallback", "prestonTalkLogged", "prestonTalkBoxOpen",
             "prestonFallbackActive", "talkSessionId", "prestonTalkReloaded",
             "prestonDialogueMenuOpen", "prestonScenePending", "prestonSceneMenuOpened",
             "prestonScenePhase1", "prestonPhase1At", "prestonSceneChecks",
             "prestonSceneRestarts", "ownPrestonSceneStop", "prestonAttemptStartedAt",
             "prestonPostSceneActive", "sanctuaryStartRetries",
             "relocateFails", "prestonHeld"),
        )
        exec(compile(m_code, "FO4SF_Min00Quest.psc", "exec"), m_ns)

        min00_give_calls = []
        min00_obj = SimpleNamespace(
            IsRunning=lambda: True, StartNoWait=lambda: True,
            GiveFromCodsworth=lambda: (min00_give_calls.append(1), m_ns["GiveFromCodsworth"]()),
        )

        c_stages = {10}
        c_cur = [10]
        c_timers = []
        c_cancels = []
        c_menu_regs = []
        c_remote_regs = []

        def c_set_stage(n):
            c_stages.add(int(n))
            if int(n) > c_cur[0]:
                c_cur[0] = int(n)

        c_ns = {
            "_PStr": _PStr,
            "Trace": logs.append,
            "LogName": "fo4sf_mission",
            "Codsworth": cods,
            "CodsworthScene": cods_scn,
            "CodsworthPostScene": cods_post,
            "CodsworthTalkActi": "CodsworthTalkActi(09000970)",
            "CodsworthTalkMsg": c_msg,
            "CodsworthReply0Msg": c_msg,
            "CodsworthReply1Msg": c_msg,
            "CodsworthReply2Msg": c_msg,
            "TalkUseMessageBox": glob_obj,
            "CodsworthLocalX": -1146.709,
            "CodsworthLocalY": 1293.837,
            "CodsworthLocalZ": 111.734,
            "MergeOffsetX": -1200.0,
            "MergeOffsetY": -2700.0,
            "ProxyHoldRadius": 25.0,
            "ProxyBindRadius": 180.0,
            "ProxyZOffset": 1.36,
            "ProxyScale": 1.6,
            "ProxyResyncDrift": 0.25,
            "MinTalkCameraDistance": 1.65,
            "SafeTalkCameraDistance": 1.85,
            "SceneOpenCheckSeconds": 1.5,
            "SceneMaxWaitChecks": 16,
            "MaxSceneRestarts": 3,
            "instanceStarted": True,
            "dialogueSeen": False,
            "dialogueMenuOpen": False,
            "talkBoxOpen": False,
            "talkSessionId": 0,
            "codsworthTalkReloaded": False,
            "concordCleared": False,
            "sceneTalkPending": False,
            "sceneMenuOpened": False,
            "scenePhase1Entered": False,
            "scenePhase1At": 0.0,
            "sceneCheckTicks": 0,
            "sceneRestartCount": 0,
            "ownSceneStopPending": False,
            "sceneAttemptStartedAt": 0.0,
            "scenePostActive": False,
            "talkProxy": None,
            "proxyLogged": False,
            "proxyLastX": 0.0,
            "proxyLastY": 0.0,
            "proxyLastZ": 0.0,
            "applied": 10,
            "pendingStage": -1,
            "pendingStageBy": "other",
            "choice1Seen": False,
            "choice2Seen": False,
            "choice3Seen": False,
            "choice4Seen": False,
            "choicesCount": 0,
            "completed": False,
            "GetStage": lambda: c_cur[0],
            "GetStageDone": lambda s: int(s) in c_stages,
            "SetStage": c_set_stage,
            "IsRunning": lambda: True,
            "Start": lambda: True,
            "GetAlias": lambda idx: cods_alias if idx == 0 else None,
            "SetObjectiveDisplayed": lambda *_: None,
            "SetObjectiveDisplayedAtTop": lambda *_: None,
            "SetObjectiveCompleted": lambda *_: None,
            "SetActive": lambda *_: None,
            "CompleteQuest": mock.MagicMock(),
            "StartTimer": lambda sec, tid: c_timers.append((float(sec), int(tid))),
            "CancelTimer": lambda tid: c_cancels.append(int(tid)),
            "RegisterForRemoteEvent": lambda o, ev: c_remote_regs.append((o, ev)),
            "RegisterForMenuOpenCloseEvent": lambda m: c_menu_regs.append(m),
            "Debug": SimpleNamespace(OpenUserLog=lambda *_: None),
            "Math": SimpleNamespace(
                Sqrt=math.sqrt,
                Sin=lambda d: math.sin(math.radians(d)),
                Cos=lambda d: math.cos(math.radians(d)),
                atan=lambda v: math.degrees(math.atan(v)),
            ),
            "Utility": SimpleNamespace(GetCurrentRealTime=lambda: rt[0]),
            "Game": SimpleNamespace(
                GetPlayer=lambda: player,
                GetFormFromFile=lambda fid, plg: (
                    min00_obj if (fid, plg) == (0x000800, "FO4SFMission.esm")
                    else keeper_q if (fid, plg) == (0x000814, "FO4SFMission.esm")
                    else cods_scn if (fid, plg) == (0x000940, "FO4SFMission.esm")
                    else cods_post if (fid, plg) == (0x0009C0, "FO4SFMission.esm")
                    else glob_obj if (fid, plg) == (0x000979, "FO4SFMission.esm")
                    else None
                ),
            ),
        }
        c_code = _translate_psc(
            c_psc,
            ("EffectiveStage", "ResolveCodsworth", "ResolveTalkActi", "ResolveTalkMsg",
             "ResolveCodsworthScene", "ResolveCodsworthPostScene", "ResolveActiveCodsworthScene",
             "ShouldUseMessageBox", "EnsureCodsworthAlias", "EnsureKeeperCodsworthAlias",
             "RegisterCodsworthSceneEvents", "BindCodsworthActivation", "EnsureTalkProxy",
             "AdvanceTo", "IsWarfareMode", "Actor.OnPlayerLoadGame", "OnMenuOpenCloseEvent",
             "EnsureSafeCodsworthCameraDistance", "RestartOrFailCodsworthScene",
             "Scene.OnBegin", "Scene.OnPhaseBegin", "Scene.OnEnd", "CheckCodsworthSceneOpen",
             "ObjectReference.OnActivate", "RunCodsworthTalk", "OnStageSet", "SyncProgress"),
            ("dialogueSeen", "dialogueMenuOpen", "talkBoxOpen", "talkSessionId", "codsworthTalkReloaded",
             "concordCleared", "sceneTalkPending", "sceneMenuOpened", "scenePhase1Entered", "scenePhase1At",
             "sceneCheckTicks", "sceneRestartCount", "ownSceneStopPending", "sceneAttemptStartedAt",
             "scenePostActive", "talkProxy", "proxyLogged",
             "proxyLastX", "proxyLastY", "proxyLastZ", "applied", "pendingStage", "pendingStageBy",
             "choice1Seen", "choice2Seen", "choice3Seen", "choice4Seen", "choicesCount", "completed"),
        )
        exec(compile(c_code, "FO4SF_Codsworth01Quest.psc", "exec"), c_ns)

        return SimpleNamespace(
            logs=logs, rt=rt, player=player, cods=cods, preston=preston,
            cods_scn=cods_scn, cods_post=cods_post, preston_scn=preston_scn, preston_post=preston_post,
            keeper_a0=keeper_a0, keeper_a1=keeper_a1, c_msg=c_msg, p_msg=p_msg,
            c_ns=c_ns, m_ns=m_ns, c_cur=c_cur, m_cur=m_cur, c_set_stage=c_set_stage, m_set_stage=m_set_stage,
            c_menu_regs=c_menu_regs, m_menu_regs=m_menu_regs, c_remote_regs=c_remote_regs, m_remote_regs=m_remote_regs,
            min00_give_calls=min00_give_calls, wfc_calls=wfc_calls,
        )

    def test_item3_zero_messagebox_when_glob_zero_bounded_restarts_and_loud_error(self):
        """Item 3: When TalkUseMessageBox == 0 (default), neither Codsworth nor Preston ever opens a MessageBox;
        scene failures run 1..3 bounded restarts, then emit loud ERROR and keep both actors talkable."""
        h = self._build_talk_harnesses(glob_val=0.0, cods_starts=False, preston_starts=True)
        h.c_ns["BindCodsworthActivation"]()

        # Direct MessageBox helper calls MUST self-suppress when glob == 0
        h.c_ns["RunCodsworthTalk"]()
        h.m_ns["RunPrestonTalk"](30, h.p_msg)
        h.m_ns["FallbackPrestonToMessageBox"]("manual")
        self.assertEqual(h.c_msg.shown, 0)
        self.assertEqual(h.p_msg.shown, 0)
        self.assertTrue(any("codsworth messagebox suppressed reason=glob_off" in ln for ln in h.logs), h.logs)
        self.assertTrue(any("preston messagebox suppressed reason=glob_off" in ln for ln in h.logs), h.logs)
        self.assertTrue(any("preston fallback suppressed reason=glob_off" in ln for ln in h.logs), h.logs)

        # Codsworth scene_inactive -> 1/3, 2/3, 3/3 retries -> loud ERROR -> actor still talkable, 0 MessageBox
        h.c_ns["OnActivate"](h.cods, h.player)
        for _ in range(4):
            h.rt[0] += 1.5
            h.c_ns["CheckCodsworthSceneOpen"]()
        self.assertEqual(h.c_msg.shown, 0)
        for n in (1, 2, 3):
            self.assertTrue(any(f"codsworth talk scene_restart retry={n}/3 reason=scene_inactive" in ln for ln in h.logs), h.logs)
        self.assertTrue(any("codsworth talk ERROR scene_failed retries=3 reason=scene_inactive actor_talkable=true" in ln for ln in h.logs), h.logs)
        self.assertGreater(h.cods.allow_pc, 0)
        self.assertGreater(h.cods.unblock, 0)

        # Fresh E press resets retry counter cleanly
        h.c_ns["OnActivate"](h.cods, h.player)
        self.assertEqual(h.c_ns["sceneRestartCount"], 0)

        # Preston dialogue_menu_timeout -> 1/3, 2/3, 3/3 retries -> loud ERROR -> actor still talkable, 0 MessageBox
        h.m_ns["AdvanceTo"](10, "Trigger")
        h.m_ns["AdvanceTo"](20, "Trigger")
        h.m_ns["AdvanceTo"](30, "Trigger")
        h.m_ns["OnActivate"](h.preston, h.player)
        for _ in range(4):
            h.m_ns["OnBegin"](h.preston_scn)
            h.m_ns["OnPhaseBegin"](h.preston_scn, 1)
            h.rt[0] += 1.5
            h.m_ns["CheckPrestonSceneOpen"]()
        self.assertEqual(h.p_msg.shown, 0)
        for n in (1, 2, 3):
            self.assertTrue(any(f"preston talk scene_restart retry={n}/3 reason=dialogue_menu_timeout" in ln for ln in h.logs), h.logs)
        self.assertTrue(any("preston talk ERROR scene_failed retries=3 reason=dialogue_menu_timeout actor_talkable=true" in ln for ln in h.logs), h.logs)
        self.assertGreater(h.preston.allow_pc, 0)
        self.assertGreater(h.preston.unblock, 0)
        self.assertFalse(any("fallback=messagebox" in ln for ln in h.logs), h.logs)

        # Scene == None -> immediate loud ERROR (retries=0, F1 accurate count), 0 MessageBox
        h_none = self._build_talk_harnesses(glob_val=0.0, cods_scene_none=True, preston_scene_none=True)
        h_none.c_ns["OnActivate"](h_none.cods, h_none.player)
        h_none.m_ns["AdvanceTo"](10, "Trigger")
        h_none.m_ns["AdvanceTo"](20, "Trigger")
        h_none.m_ns["AdvanceTo"](30, "Trigger")
        h_none.m_ns["OnActivate"](h_none.preston, h_none.player)
        self.assertEqual(h_none.c_msg.shown, 0)
        self.assertEqual(h_none.p_msg.shown, 0)
        self.assertTrue(any("codsworth talk ERROR scene_failed retries=0 reason=no_scene actor_talkable=true" in ln for ln in h_none.logs))
        self.assertTrue(any("preston talk ERROR scene_failed retries=0 reason=no_scene actor_talkable=true" in ln for ln in h_none.logs))

    def test_item4_post_mission_repeat_talks_preston_0990_and_codsworth_09c0_after_reload(self):
        """Item 4: After stage 100 (Codsworth) and stage 200 (Preston) — including after a save reload —
        pressing E repeatedly opens repeatable voiced Starfield Scenes 0x09C0 and 0x0990 on keeper 0x0814
        with ZERO MessageBox, ZERO duplicate stage/reward triggers, and full DialogueMenu open/close tracking."""
        h = self._build_talk_harnesses(glob_val=0.0)
        h.c_ns["BindCodsworthActivation"]()

        # Complete Codsworth01 via primary 0x0940
        h.c_ns["OnActivate"](h.c_ns["talkProxy"], h.player)
        h.c_ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
        h.c_set_stage(100)
        h.c_ns["OnStageSet"](100, 0)
        h.cods_scn.playing = False
        h.c_ns["OnMenuOpenCloseEvent"]("DialogueMenu", False)
        h.c_ns["OnEnd"](h.cods_scn)
        self.assertTrue(h.c_ns["completed"])
        self.assertEqual(len(h.min00_give_calls), 1)

        # Save reload post-100 -> BindCodsworthActivation re-registers DialogueMenu + 0x09C0 + fills keeper alias 1
        h.c_menu_regs.clear()
        h.c_remote_regs.clear()
        h.c_ns["OnPlayerLoadGame"](h.player)
        self.assertEqual(h.keeper_a1.actor, h.cods)
        self.assertIn("DialogueMenu", h.c_menu_regs)
        self.assertIn((h.cods_post, "OnBegin"), h.c_remote_regs)

        # 3 repeat E presses on Codsworth (both proxy and direct actor) -> 0x09C0 starts 3 times, 0 MessageBox, 0 duplicate Min00 handoff!
        for rep, target in enumerate((h.c_ns["talkProxy"], h.cods, h.c_ns["talkProxy"]), start=1):
            h.c_ns["OnActivate"](target, h.player)
            self.assertEqual(h.cods_post.start_calls, rep)
            h.c_ns["OnBegin"](h.cods_post)
            h.c_ns["OnPhaseBegin"](h.cods_post, 1)
            h.c_ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
            self.assertTrue(h.c_ns["sceneMenuOpened"])
            h.cods_post.playing = False
            h.c_ns["OnMenuOpenCloseEvent"]("DialogueMenu", False)
            h.c_ns["OnEnd"](h.cods_post)
        self.assertEqual(h.cods_scn.start_calls, 1)
        self.assertEqual(h.c_msg.shown, 0)
        self.assertEqual(len(h.min00_give_calls), 1)

        # Complete Min00 via primary 0x0900 -> stage 200
        h.m_ns["AdvanceTo"](20, "Trigger")
        h.m_ns["AdvanceTo"](30, "Trigger")
        h.m_ns["OnActivate"](h.preston, h.player)
        h.m_ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
        h.m_set_stage(35)
        h.m_ns["OnStageSet"](35, 0)
        h.preston_scn.playing = False
        h.m_ns["OnMenuOpenCloseEvent"]("DialogueMenu", False)
        h.m_ns["OnEnd"](h.preston_scn)
        self.assertEqual(h.m_cur[0], 200)
        self.assertEqual(h.player.AddItem.call_count, 1)

        # Save reload post-200 -> re-registers DialogueMenu + 0x0990 + fills keeper alias 0 + runs WFC-01 dead-raider check
        h.m_menu_regs.clear()
        h.m_remote_regs.clear()
        h.wfc_calls.clear()
        h.m_ns["OnPlayerLoadGame"](h.player)
        self.assertEqual(h.keeper_a0.actor, h.preston)
        self.assertIn("DialogueMenu", h.m_menu_regs)
        self.assertIn((h.preston_post, "OnBegin"), h.m_remote_regs)
        self.assertEqual(h.wfc_calls, [False])

        # 3 repeat E presses on Preston post-200 -> 0x0990 starts 3 times, DialogueMenu opens (NOT suppressed!), 0 MessageBox, 0 extra Credits!
        for rep in range(1, 4):
            h.m_ns["OnActivate"](h.preston, h.player)
            self.assertEqual(h.preston_post.start_calls, rep)
            h.m_ns["OnBegin"](h.preston_post)
            h.m_ns["OnPhaseBegin"](h.preston_post, 1)
            h.m_ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
            self.assertTrue(h.m_ns["prestonSceneMenuOpened"], f"repeat {rep} DialogueMenu was suppressed!")
            self.assertEqual(h.preston_post.stop_calls, 0)
            h.preston_post.playing = False
            h.m_ns["OnMenuOpenCloseEvent"]("DialogueMenu", False)
            h.m_ns["OnEnd"](h.preston_post)
        self.assertEqual(h.preston_scn.start_calls, 1)
        self.assertEqual(h.p_msg.shown, 0)
        self.assertEqual(h.player.AddItem.call_count, 1)
        self.assertFalse(any("fallback=messagebox" in ln for ln in h.logs), h.logs)

    def test_item5_e3_concord_raider_3dmg_sidearm_and_deterministic_36_ammo(self):
        """Item 5 (E3 + R13 + fix4): WEAP 0x097B (6.0 dmg Coachman, NonPlayable, ObjectTemplates+AttachParentSlots intact) +
        WEAP 0x097A (AttackDamage=1.5, ObjectTemplates+AttachParentSlots intact, AmmoList=null) + ArmRaiderForCombat
        UnequipItem-only weapon swap (preserving FO4 0x0988 outfits!) + EquipBalancedRaiderSidearm clamping Ammo777mm=36."""
        cs = MISSION_CS.read_text(encoding="utf-8")
        m_psc = MIN00_PSC.read_text(encoding="utf-8")
        self.assertIn("ConcordRaiderPrimaryWeapId = 0x97B", cs)
        self.assertIn("ConcordRaiderPrimaryDamage = 6.0f", cs)
        self.assertIn("ConcordRaiderSidearmWeapId = 0x97A", cs)
        self.assertIn("ConcordRaiderSidearmDamage = 1.5f", cs)
        self.assertIn("concordSidearm.AttackDamage = ConcordRaiderSidearmDamage;", cs)
        self.assertIn("concordSidearm.AmmoList.SetToNull();", cs)
        self.assertNotIn("concordSidearm.ObjectTemplates = null;", cs)
        self.assertNotIn("concordPrimary.ObjectTemplates = null;", cs)
        self.assertNotIn("concordSidearm.AttachParentSlots?.Clear();", cs)
        self.assertNotIn("concordPrimary.AttachParentSlots?.Clear();", cs)
        self.assertNotIn("(Raider Stand-In)", cs)
        self.assertNotIn("(Post-mission stand-in)", cs)
        self.assertNotIn("(Stand-In)", cs)
        self.assertIn('Obj("RaiderWeapon", concordPrimary.FormKey)', cs)
        self.assertIn('Obj("RaiderSidearm", concordSidearm.FormKey)', cs)
        self.assertIn('Flt("RaiderPrimaryRecordDamage", primaryRecordDamage)', cs)
        self.assertIn('Flt("RaiderSidearmRecordDamage", sidearmRecordDamage)', cs)
        self.assertNotIn("RaiderSidearmDamage = 3.0", m_psc)

        # Verify weapon-only UnequipItem precedes EquipItem(RaiderWeapon) with zero UnequipAll() so outfits stay worn
        arm_src = _extract_block(m_psc, "ArmRaiderForCombat")[1]
        self.assertNotIn("UnequipAll", arm_src)
        self.assertLess(arm_src.index("r.UnequipItem(curW, False, True)"), arm_src.index("r.EquipItem(RaiderWeapon"))
        fn_src = _extract_block(m_psc, "EquipBalancedRaiderSidearm")[1]
        self.assertLess(fn_src.index("r.AddItem(RaiderSidearm"), fn_src.index("int curSidearmAmmo = r.GetItemCount(RaiderSidearmAmmo)"))
        self.assertLess(fn_src.index("r.EquipItem(RaiderSidearm"), fn_src.index("int curSidearmAmmo = r.GetItemCount(RaiderSidearmAmmo)"))

        class _BonusAmmoRaider:
            def __init__(self, shells, bonus_add, bonus_equip):
                self.inv = {"ConcordCoachman097B": 1, "AmmoShotshell": shells}
                self.bonus_add = bonus_add
                self.bonus_equip = bonus_equip
                self.equipped = [("VanillaSpacerGun", False)]
                self.outfit_worn = True
                self.unequip_all_calls = 0

            def IsDead(self): return False
            def SetRestrained(self, *_): pass
            def SetValue(self, *_): pass
            def GetValue(self, *_): return 0.0
            def GetItemCount(self, item): return self.inv.get(item, 0)
            def AddItem(self, item, cnt, _s=False):
                self.inv[item] = self.inv.get(item, 0) + int(cnt)
                if item == "ConcordEon097A":
                    self.inv["Ammo777mm"] = self.inv.get("Ammo777mm", 0) + self.bonus_add
            def RemoveItem(self, item, cnt, _s=False):
                self.inv[item] = max(0, self.inv.get(item, 0) - int(cnt))
            def UnequipAll(self):
                self.unequip_all_calls += 1
                self.outfit_worn = False
                self.equipped.clear()
            def UnequipItem(self, item, *_):
                self.equipped = [e for e in self.equipped if e[0] != item]
            def EquipItem(self, item, prevent=False, _s=False):
                self.equipped.append((item, bool(prevent)))
                if item == "ConcordEon097A":
                    self.inv["Ammo777mm"] = self.inv.get("Ammo777mm", 0) + self.bonus_equip
            def GetEquippedWeapon(self, idx=0): return self.equipped[-1][0] if self.equipped else None
            def EvaluatePackage(self): pass

        logs = []
        # Exact 2g-fix observed variances (12, 16, 20, 12, 24 bonus rounds) -> ALL must clamp to exact 36!
        raiders = [
            _BonusAmmoRaider(30, 12, 0),
            _BonusAmmoRaider(70, 16, 0),
            _BonusAmmoRaider(30, 20, 0),
            _BonusAmmoRaider(30, 6, 6),
            _BonusAmmoRaider(20, 24, 0),
        ]
        ns = {
            "_PStr": _PStr,
            "Trace": logs.append,
            "RaiderWeapon": "ConcordCoachman097B",
            "RaiderAmmo": "AmmoShotshell",
            "RaiderSidearm": "ConcordEon097A",
            "RaiderPrimaryRecordDamage": 6.0,
            "RaiderSidearmRecordDamage": 1.5,
            "AttackDamageMult": None,
            "RaiderSidearmAmmo": "Ammo777mm",
            "raiderArmed": _PArray([False] * 5),
            "Game": SimpleNamespace(GetAggressionAV=lambda: "Agg", GetConfidenceAV=lambda: "Conf"),
        }
        code = _translate_psc(m_psc, ("ComputeEffectiveWeaponDamage", "ArmRaiderForCombat", "EquipBalancedRaiderSidearm"), ("raiderArmed",))
        exec(compile(code, "FO4SF_Min00Quest.psc", "exec"), ns)
        for i, r in enumerate(raiders):
            ns["ArmRaiderForCombat"](r, i)
            self.assertEqual(r.unequip_all_calls, 0)
            self.assertTrue(r.outfit_worn)
            self.assertNotIn(("VanillaSpacerGun", False), r.equipped)
            self.assertEqual(r.equipped[-1], ("ConcordCoachman097B", False))
            self.assertIn("eff_dmg=6.0", logs[-1])
            ns["EquipBalancedRaiderSidearm"](r, i)
            self.assertEqual(r.inv["Ammo777mm"], 36, f"raider {i} got {r.inv['Ammo777mm']} instead of 36")
            self.assertEqual(r.inv["ConcordCoachman097B"], 0)
            self.assertEqual(r.inv["AmmoShotshell"], 0)
            self.assertEqual(r.equipped[-1], ("ConcordEon097A", True))
            self.assertIn(f"arm raider {i} sidearm=eon sidearm_ammo=36", logs[-1])
            self.assertIn("eff_dmg=1.5", logs[-1])

    def test_item6_e5_dead_raiders_preserved_in_concord_across_cold_reload(self):
        """Item 6 (E5): Dead raiders killed in Concord street are tracked in raiderCorpseX/Y/Z and rescued back
        from 2.9 km away (-3229, -4392, 261) on reload and KeepPreston with wfc01 rescue_dead, while disabled
        written-off raiders are skipped and .MoveTo( count remains exact 3."""
        m_psc = MIN00_PSC.read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"\.MoveTo\(", m_psc)), 3, ".MoveTo( invariant broken!")

        fo4_world = "WorldSpace<MarsPlanetWorld>"
        logs = []

        class _Actor:
            def __init__(self, name, pos, world=fo4_world):
                self.name = name
                self.pos = list(pos)
                self.world = world
                self.interior = False
                self.dead = False
                self.disabled = False
                self.eval_calls = 0
                self.move_calls = 0

            def IsInInterior(self): return self.interior
            def GetWorldSpace(self): return self.world
            def GetPositionX(self): return self.pos[0]
            def GetPositionY(self): return self.pos[1]
            def GetPositionZ(self): return self.pos[2]
            def SetPosition(self, x, y, z): self.pos = [float(x), float(y), float(z)]
            def MoveTo(self, ref, dx, dy, dz, *_):
                self.move_calls += 1
                self.interior = ref.IsInInterior()
                self.world = ref.GetWorldSpace()
                self.pos = [ref.GetPositionX() + dx, ref.GetPositionY() + dy, ref.GetPositionZ() + dz]
            def IsDead(self): return self.dead
            def IsDisabled(self): return self.disabled
            def Is3DLoaded(self): return True
            def EvaluatePackage(self): self.eval_calls += 1
            def GetDistance(self, o):
                return math.sqrt(sum((a - b) ** 2 for a, b in zip(self.pos, o.pos)))

        merged_spots = [
            (-2029.18, -1698.26, 88.33),
            (-2041.36, -1681.12, 88.19),
            (-2049.84, -1673.09, 88.11),
            (-2047.25, -1658.47, 88.15),
            (-2050.82, -1690.53, 88.22),
        ]
        raiders = _PArray([_Actor(f"Raider{i}", p) for i, p in enumerate(merged_spots)])
        player = _Actor("Player", (-2015.0, -1700.0, 89.1))
        preston = _Actor("Preston", (-2011.14, -1697.54, 89.09))
        v111 = SimpleNamespace(GetWorldSpace=lambda: fo4_world)
        min00_done = [True]

        ns = {
            "_PStr": _PStr,
            "_PArray": _PArray,
            "Trace": logs.append,
            "KeeperOnly": True,
            "Preston": preston,
            "Raiders": raiders,
            "MergeOffsetX": -1200.0,
            "MergeOffsetY": -2700.0,
            "PrestonLocalX": -811.14,
            "PrestonLocalY": 1002.46,
            "PrestonLocalZ": 89.09,
            "RelocateRadius": 800.0,
            "Wfc01CheckRadius": 150.0,
            "Wfc01DoorRadius": 100.0,
            "Wfc01SubterraneanDrop": 8.0,
            "Wfc01MaxDrift": 140.0,
            "Wfc01AbsentDistance": 250.0,
            "Wfc01AbsentLimit": 60.0,
            "Wfc01StuckMoveRadius": 2.0,
            "Wfc01StuckLimit": 60.0,
            "KeeperStatusEvery": 12,
            "prestonPlaced": True,
            "prestonFails": 0,
            "prestonState": "at spot",
            "keeperChecks": 0,
            "raiderTargetX": None,
            "raiderTargetY": None,
            "raiderTargetZ": None,
            "raiderCorpseX": None,
            "raiderCorpseY": None,
            "raiderCorpseZ": None,
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
            "healthAvCache": "HealthAV",
            "ReleaseInFight": lambda *_: False,
            "PlacePreston": lambda *_: False,
            "TracePreston": lambda *_: None,
            "IsTestModeEnabled": lambda: False,
            "GetRaiderHealth": lambda *_: 0.0,
            "WriteOffRaider": lambda *_: None,
            "Math": SimpleNamespace(Sqrt=math.sqrt),
            "Debug": SimpleNamespace(Notification=lambda *_: None),
            "Game": SimpleNamespace(
                GetFormFromFile=lambda fid, plg: (
                    v111 if fid == 0x0A775B
                    else SimpleNamespace(IsCompleted=lambda: min00_done[0]) if (fid, plg) == (0x000800, "FO4SFMission.esm")
                    else None
                )
            ),
        }
        code = _translate_psc(
            m_psc,
            ("ResolveCommonwealthWorld", "IsCommonwealthExterior", "IsPlayerStableAt", "SpotOff",
             "InitRaiderTracking", "CheckConcordRaidersWfc01", "IsStoryQuestComplete", "KeepPreston"),
            ("raiderTargetX", "raiderTargetY", "raiderTargetZ", "raiderCorpseX", "raiderCorpseY", "raiderCorpseZ",
             "raiderAbsentSec", "raiderCleared", "raiderRescued", "raiderEngaged", "raiderArmed",
             "raiderStartCombatAt", "raiderRescueSec", "raiderRescueX", "raiderRescueY", "raiderRescueZ",
             "raiderRescueHp", "prestonFails", "prestonState", "keeperChecks"),
        )
        exec(compile(code, "FO4SF_Min00Quest.psc", "exec"), ns)

        # Fight in Concord street: raiders move 10 m and die where they fought
        ns["InitRaiderTracking"]()
        death_spots = []
        for i, r in enumerate(raiders):
            r.pos = [r.pos[0] + 6.0, r.pos[1] - 4.0, r.pos[2]]
            death_spots.append(tuple(r.pos))
            r.dead = True
        ns["CheckConcordRaidersWfc01"](player, False)
        for i, want in enumerate(death_spots):
            self.assertAlmostEqual(ns["raiderCorpseX"][i], want[0], places=2)
            self.assertAlmostEqual(ns["raiderCorpseY"][i], want[1], places=2)

        # Cold reload snaps all 5 dead raiders 2.9 km away to exact 2g-fix failure coords (-3229, -4392, 261)!
        # Mark raider 4 disabled (as if previously written off) -> must stay untouched.
        for r in raiders:
            r.pos = [-3229.0, -4392.0, 261.0]
        raiders[4].disabled = True

        # N2: KeeperOnly KeepPreston must NOT run CheckConcordRaidersWfc01 (corpse-pile hazard removed); rescue stays in Min00
        ns["KeepPreston"](player)
        for i in range(5):
            self.assertEqual(raiders[i].move_calls, 0, "KeepPreston must not touch Concord raider corpses")

        # Min00 CheckConcordRaidersWfc01 rescues raiders 0..3 back to their Concord corpse spots!
        ns["CheckConcordRaidersWfc01"](player, False)
        for i in range(4):
            self.assertAlmostEqual(raiders[i].pos[0], death_spots[i][0], places=2)
            self.assertAlmostEqual(raiders[i].pos[1], death_spots[i][1], places=2)
            self.assertAlmostEqual(raiders[i].pos[2], death_spots[i][2], places=2)
            self.assertEqual(raiders[i].move_calls, 1)
            self.assertEqual(raiders[i].eval_calls, 0, "dead corpse must not call EvaluatePackage")
            self.assertFalse(ns["raiderRescued"][i], "dead corpse must not enter living stuck-writeoff tracking")
        self.assertEqual(raiders[4].move_calls, 0, "disabled written-off raider must not be rescued")
        self.assertEqual(sum(1 for ln in logs if "wfc01 rescue_dead raider=" in ln), 4)

    @unittest.skipUnless(os.environ.get("FO4SF_DOTNET_TESTS") == "1", "Set FO4SF_DOTNET_TESTS=1 for binary ESM check")
    def test_dotnet_selftest_binary_esm_r11_part3_records(self):
        """Binary ESM proof: WEAP 0x097A (AttackDamage=3.0f, no WAM2 AmmoList), keeper 0x0814 aliases 0/1,
        and repeatable post-mission SCEN 0x0990 (Preston) & 0x09C0 (Codsworth) with DEVT, alias 0/1, INTV=1."""
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

            weaps = {}
            scens = {}
            infos = {}
            cells = {}
            for sig, fid, _fl, body in _iter_esm_records(esm_bytes, {b"WEAP", b"SCEN", b"INFO", b"CELL"}):
                lid = fid & 0xFFFFFF
                if sig == b"WEAP" and lid in (0x97A, 0x97B):
                    weaps[lid] = list(_iter_subrecords(body))
                elif sig == b"SCEN" and lid in (0x990, 0x9C0):
                    scens[lid] = list(_iter_subrecords(body))
                elif sig == b"INFO" and (0x991 <= lid <= 0x9BA or 0x9C1 <= lid <= 0x9EB):
                    infos[lid] = dict(_iter_subrecords(body))
                elif sig == b"CELL" and lid == 0xB60:
                    cells[lid] = dict(_iter_subrecords(body))

            # E3 + fix4: WEAP 0x097A FO4SF_ConcordRaiderSidearm ("Eon", AttackDamage=1.5f, AmmoList=0, ObjectTemplates+APPR kept, NonPlayable)
            # and WEAP 0x097B FO4SF_ConcordRaiderPrimary ("Coachman", AttackDamage=6.0f, AmmoList=0, ObjectTemplates+APPR kept, NonPlayable)
            self.assertIn(0x97A, weaps)
            w_subs = dict(weaps[0x97A])
            self.assertEqual(w_subs[b"EDID"].rstrip(b"\x00").decode(), "FO4SF_ConcordRaiderSidearm")
            self.assertEqual(w_subs[b"FULL"].rstrip(b"\x00").decode(), "Eon")
            self.assertIn(b"OBTS", w_subs)
            self.assertIn(b"APPR", w_subs)
            self.assertIn(b"WAM2", w_subs)
            wam2_ammo, wam2_list = struct.unpack_from("<II", w_subs[b"WAM2"], 0)
            self.assertEqual(wam2_ammo, 0x0004AD3E, f"WAM2 Ammo expected 0x04AD3E, got 0x{wam2_ammo:08X}")
            self.assertEqual(wam2_list, 0, f"WAM2 AmmoList must be cleared (0), got 0x{wam2_list:08X}")
            self.assertIn(b"WDMG", w_subs)
            dmg = struct.unpack_from("<f", w_subs[b"WDMG"], 0)[0]
            self.assertAlmostEqual(dmg, 1.5, places=4, msg=f"AttackDamage expected 1.5, got {dmg}")

            self.assertIn(0x97B, weaps)
            p_subs = dict(weaps[0x97B])
            self.assertEqual(p_subs[b"EDID"].rstrip(b"\x00").decode(), "FO4SF_ConcordRaiderPrimary")
            self.assertEqual(p_subs[b"FULL"].rstrip(b"\x00").decode(), "Coachman")
            self.assertIn(b"OBTS", p_subs)
            self.assertIn(b"APPR", p_subs)
            pwam2_ammo, pwam2_list = struct.unpack_from("<II", p_subs[b"WAM2"], 0)
            self.assertEqual(pwam2_ammo, 0x002B4AFB, f"WAM2 Primary Ammo expected 0x2B4AFB, got 0x{pwam2_ammo:08X}")
            self.assertEqual(pwam2_list, 0, f"WAM2 Primary AmmoList must be cleared (0), got 0x{pwam2_list:08X}")
            pdmg = struct.unpack_from("<f", p_subs[b"WDMG"], 0)[0]
            self.assertAlmostEqual(pdmg, 6.0, places=4, msg=f"Primary AttackDamage expected 6.0, got {pdmg}")

            self.assertIn(0xB60, cells)
            cell_full = cells[0xB60].get(b"FULL", b"").rstrip(b"\x00").decode()
            self.assertNotIn("FO4SF", cell_full)
            self.assertEqual(cell_full, "Commonwealth Holding")

            # Step 3 / Item 4: SCEN 0x0990 (Preston post, alias 0) & SCEN 0x09C0 (Codsworth post, alias 1)
            # Single-choice FO4 post-mission goodbye stand-in (zero Concord/MQ102 choice replay or audio mismatch)
            for lid, want_edid, want_alias in ((0x990, "FO4SF_PrestonPostScene", 0), (0x9C0, "FO4SF_CodsworthPostScene", 1)):
                self.assertIn(lid, scens, f"SCEN 0x{lid:X} missing from FO4SFMission.esm")
                s_dict = dict(scens[lid])
                self.assertEqual(s_dict[b"EDID"].rstrip(b"\x00").decode(), want_edid)
                self.assertIn(b"DEVT", s_dict)
                self.assertNotIn(b"SCPI", s_dict)
                self.assertEqual(struct.unpack_from("<I", s_dict[b"FNAM"], 0)[0], 0x1814)
                self.assertEqual(struct.unpack_from("<I", s_dict[b"ALID"], 0)[0], want_alias)

            # Only the single-choice goodbye INFOs (0x9A8/0x9B8 Preston, 0x9D8/0x9E8 Codsworth) exist; old replay choices removed
            for lid in (0x9A8, 0x9D8):
                self.assertIn(lid, infos, f"post-scene pcInfo 0x{lid:X} missing")
                self.assertEqual(struct.unpack_from("<H", infos[lid][b"ENAM"], 0)[0], 0)
                self.assertEqual(struct.unpack_from("<I", infos[lid][b"INAM"], 0)[0], 1)
            for lid, idict in infos.items():
                for raw in idict.values():
                    self.assertNotIn(b"stand-in", raw.lower(), f"post-scene INFO 0x{lid:X} still leaks stand-in label")
            for lid in (0x9B8, 0x9E8):
                self.assertIn(lid, infos, f"post-scene goodbye npcInfo 0x{lid:X} missing")
            for removed_lid in (0x9A9, 0x9AA, 0x9B9, 0x9D9, 0x9DA, 0x9DB, 0x9E9, 0x9EA):
                self.assertNotIn(removed_lid, infos, f"old replay post-scene INFO 0x{removed_lid:X} must be absent")

            # Task 1i: 0 WRLD overrides and interior holding CELL 0x0B60 present
            wrld_cnt = sum(1 for _sig, _fid, _fl, _body in _iter_esm_records(esm_bytes, {b"WRLD"}))
            self.assertEqual(wrld_cnt, 0, "Task 1i: FO4SFMission.esm must have 0 WRLD overrides")
            holding_cells = [
                dict(_iter_subrecords(body))
                for _sig, fid, _fl, body in _iter_esm_records(esm_bytes, {b"CELL"})
                if (fid & 0xFFFFFF) == 0xB60
            ]
            self.assertEqual(len(holding_cells), 1, "Task 1i: missing holding CELL 0x000B60")
            self.assertEqual(holding_cells[0][b"EDID"].rstrip(b"\x00").decode(), "FO4SF_MissionHoldingCell")


if __name__ == "__main__":
    unittest.main()
