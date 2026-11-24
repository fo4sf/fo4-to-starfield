"""Round 11 Step 3q unit tests: cell-independent S3 / S4 / S6 / S9 quest scaffolding.

Pure-stdlib, cross-OS path-safe, runs cleanly on Linux CI with ZERO local Starfield.esm or
Fallout4.esm dependencies. Executes translated real Papyrus functions from
`FO4SF_Codsworth01Quest.psc` and `FO4SF_Min00Quest.psc` and verifies strict default-OFF
(`--r11-full-mission 0`) gating plus optional binary ESM verification under
`FO4SF_DOTNET_TESTS=1`.
"""

from __future__ import annotations

import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_TERRAIN = REPO_ROOT / "scripts" / "terrain"
for _p in (str(SRC_DIR), str(SCRIPTS_TERRAIN)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PROGRAM_CS = REPO_ROOT / "dotnet" / "Mission" / "Program.cs"
CODSWORTH_PSC = REPO_ROOT / "scripts" / "mission" / "FO4SF_Codsworth01Quest.psc"
MIN00_PSC = REPO_ROOT / "scripts" / "mission" / "FO4SF_Min00Quest.psc"
ROACHES_PSC = REPO_ROOT / "scripts" / "mission" / "FO4SF_Vault111RoachesQuest.psc"
PICKUP_PSC = REPO_ROOT / "scripts" / "mission" / "FO4SF_S5S6ItemPickup.psc"


def _extract_fn(psc: str, name: str) -> tuple[list[tuple[str, str | None]], str]:
    m = re.search(
        rf"^(?:[A-Za-z_]\w*(?:\[\])?\s+)?(?:Function|Event)\s+{re.escape(name)}\s*\(([^)]*)\)\s*\n"
        rf"(.*?)^End(?:Function|Event)\b",
        psc,
        re.M | re.S,
    )
    if not m:
        raise AssertionError(f"Papyrus function/event {name!r} not found")
    raw_params = m.group(1).strip()
    params: list[tuple[str, str | None]] = []
    if raw_params:
        for part in raw_params.split(","):
            part = part.strip()
            default = None
            if "=" in part:
                left, default = part.split("=", 1)
                default = default.strip()
            else:
                left = part
            toks = left.strip().split()
            params.append((toks[-1], default))
    body = re.sub(r"\{.*?\}", "", m.group(2), flags=re.S)
    return params, body


def _replace_outside_strings(s: str, fn) -> str:
    out: list[str] = []
    pos = 0
    for m in re.finditer(r'"[^"]*"', s):
        out.append(fn(s[pos : m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(fn(s[pos:]))
    return "".join(out)


def _py_expr(expr: str) -> str:
    s = expr.strip()

    def _xform(code: str) -> str:
        code = re.sub(r"\bTrue\b", "True", code, flags=re.I)
        code = re.sub(r"\bFalse\b", "False", code, flags=re.I)
        code = re.sub(r"\bNone\b", "None", code, flags=re.I)
        code = re.sub(r"\bnew\s+(?:int|float)\[([^\]]+)\]", r"[0] * (\1)", code)
        code = re.sub(r"\bnew\s+bool\[([^\]]+)\]", r"[False] * (\1)", code)
        code = re.sub(r"\bnew\s+[A-Za-z_]\w*\[([^\]]+)\]", r"[None] * (\1)", code)
        code = re.sub(r"\s+as\s+[A-Za-z_]\w*(?:\[\])?", "", code)
        code = code.replace("&&", " and ").replace("||", " or ")
        code = re.sub(r"(?<!=)!=(?!=)", "__NE__", code)
        code = re.sub(r"!(?!=)", " not ", code)
        code = code.replace("__NE__", "!=")
        code = re.sub(r"\b([A-Za-z_]\w*)\.Length\b", r"len(\1)", code)
        return code

    s = _replace_outside_strings(s, _xform)
    trace_m = re.match(r"^Trace\((.*)\)$", s)
    if trace_m:
        return f"Trace({_py_expr(trace_m.group(1))})"
    s = re.sub(r'("[^"]*")\s*\+\s*([A-Za-z_]\w*)\b(?!\s*[(.])', r"\1 + _pstr(\2)", s)
    # Papyrus string concatenation with `+` accepts numbers/bools; rewrite `"..." + expr`
    if '"' in s and "+" in s:
        parts: list[str] = []
        buf: list[str] = []
        in_str = False
        depth = 0
        for ch in s:
            if ch == '"':
                in_str = not in_str
                buf.append(ch)
            elif not in_str and ch in "([":
                depth += 1
                buf.append(ch)
            elif not in_str and ch in ")]":
                depth -= 1
                buf.append(ch)
            elif not in_str and depth == 0 and ch == "+":
                parts.append("".join(buf).strip())
                buf = []
            else:
                buf.append(ch)
        if buf:
            parts.append("".join(buf).strip())
        if len(parts) > 1 and any(p.startswith('"') for p in parts):
            s = " + ".join(p if p.startswith('"') else f"_pstr({p})" for p in parts)
    return s


def _compile_papyrus(psc: str, fn_names: list[str], state_vars: set[str], ns: dict) -> None:
    ns["_pstr"] = lambda v: "true" if v is True else ("false" if v is False else str(v))
    ns["Math"] = SimpleNamespace(Sqrt=math.sqrt)
    for fn_name in fn_names:
        params, body = _extract_fn(psc, fn_name)
        sig_parts = []
        for pname, pdef in params:
            if pdef is not None:
                sig_parts.append(f"{pname}={_py_expr(pdef)}")
            else:
                sig_parts.append(pname)
        py_name = fn_name.replace(".", "_")
        lines = [f"def {py_name}({', '.join(sig_parts)}):"]
        if state_vars:
            lines.append("    global " + ", ".join(sorted(state_vars)))
        indent = 1
        for raw in body.splitlines():
            code = raw.split(";", 1)[0].strip()
            if not code:
                continue
            low = code.lower()
            if low in ("endif", "endwhile"):
                indent -= 1
                continue
            if low == "else":
                lines.append("    " * (indent - 1) + "else:")
                continue
            if low.startswith("elseif "):
                cond = _py_expr(code[7:])
                lines.append("    " * (indent - 1) + f"elif {cond}:")
                continue
            if low.startswith("if "):
                cond = _py_expr(code[3:])
                lines.append("    " * indent + f"if {cond}:")
                indent += 1
                continue
            if low.startswith("while "):
                cond = _py_expr(code[6:])
                lines.append("    " * indent + f"while {cond}:")
                indent += 1
                continue
            if low == "return":
                lines.append("    " * indent + "return None")
                continue
            if low.startswith("return "):
                lines.append("    " * indent + "return " + _py_expr(code[7:]))
                continue
            # Local typed variable declaration: `Type name = expr`
            decl_m = re.match(r"^(?:int|float|bool|string|var|Actor|ActorBase|Cell|Package|Form|Weapon|Ammo|Quest|ObjectReference|Scene|GlobalVariable|Message|FO4SF_[A-Za-z_]\w*(?:\[\])?|(?:int|float|bool|string|var|Actor|ObjectReference)\[\])\s+([A-Za-z_]\w*)\s*=\s*(.+)$", code)
            if decl_m:
                vname, vexpr = decl_m.group(1), _py_expr(decl_m.group(2))
                lines.append("    " * indent + f"{vname} = {vexpr}")
                continue
            assign_m = re.match(r"^([A-Za-z_]\w*)\s*(\+=|-=|=)\s*(.+)$", code)
            if assign_m:
                vname, op, vexpr = assign_m.group(1), assign_m.group(2), _py_expr(assign_m.group(3))
                lines.append("    " * indent + f"{vname} {op} {vexpr}")
                continue
            lines.append("    " * indent + _py_expr(code))
        if len(lines) == 1 or (len(lines) == 2 and lines[1].startswith("    global ")):
            lines.append("    pass")
        src = "\n".join(lines)
        exec(compile(src, f"<papyrus:{fn_name}>", "exec"), ns)


class _FakeActor:
    def __init__(self, name: str, x: float = 0.0, y: float = 0.0, z: float = 0.0, dead: bool = False, interior: bool = False):
        self.name = name
        self.x = x
        self.y = y
        self.z = z
        self.dead = dead
        self.interior = interior
        self.restrained = False
        self.talkable = False
        self.items: dict[str, int] = {}
        self.linked_ref = None
        self.eval_calls = 0
        self.combat_starts = 0
        self.async_calls: list[tuple[str, list]] = []
        self.moveto_calls: list[tuple[float, float, float]] = []

    def GetPositionX(self) -> float:
        return self.x

    def GetPositionY(self) -> float:
        return self.y

    def GetPositionZ(self) -> float:
        return self.z

    def SetPosition(self, x: float, y: float, z: float) -> None:
        self.x, self.y, self.z = float(x), float(y), float(z)

    def MoveTo(self, target, ox: float = 0.0, oy: float = 0.0, oz: float = 0.0, *_args) -> None:
        self.x = target.GetPositionX() + float(ox)
        self.y = target.GetPositionY() + float(oy)
        self.z = target.GetPositionZ() + float(oz)
        self.interior = False
        self.moveto_calls.append((self.x, self.y, self.z))

    def GetDistance(self, other) -> float:
        if getattr(other, "unmerged_world", False):
            return 3.4e38
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2)

    def GetCombatState(self) -> int:
        return 0

    def IsDead(self) -> bool:
        return self.dead

    def IsInInterior(self) -> bool:
        return self.interior

    def GetWorldSpace(self):
        return "Commonwealth"

    def GetParentCell(self):
        return "ExteriorCell"

    def SetRestrained(self, val: bool) -> bool:
        self.restrained = bool(val)
        return True

    def AllowPCDialogue(self, val: bool) -> None:
        self.talkable = bool(val)

    def BlockActivation(self, *_args) -> None:
        pass

    def IgnoreFriendlyHits(self, *_args) -> None:
        pass

    def AddItem(self, form, count: int = 1, _silent: bool = False) -> None:
        key = getattr(form, "name", str(form))
        self.items[key] = self.items.get(key, 0) + int(count)

    def GetItemCount(self, form) -> int:
        key = getattr(form, "name", str(form))
        return int(self.items.get(key, 0))

    def EquipItem(self, *_args) -> None:
        pass

    def StartCombat(self, *_args) -> None:
        pass

    def EnableNoWait(self, _fade: bool = False) -> None:
        pass

    def SetAngle(self, *_args) -> None:
        pass

    def SetLinkedRef(self, target, _kw=None, _promote: bool = True) -> None:
        self.linked_ref = target

    def EvaluatePackage(self, _reset: bool = False) -> None:
        self.eval_calls += 1

    def IsInCombat(self) -> bool:
        return False

    def GetCombatTarget(self):
        return None

    def Is3DLoaded(self) -> bool:
        return True

    def SetValue(self, *_args) -> None:
        pass

    def StartCombat(self, *_args) -> None:
        self.combat_starts += 1

    def CallFunctionNoWait(self, fn_name: str, args=None) -> None:
        self.async_calls.append((str(fn_name), list(args or [])))


class _FakeMarker:
    def __init__(self, name: str, x: float, y: float, z: float, unmerged_world: bool = False):
        self.name = name
        self.x = x
        self.y = y
        self.z = z
        self.unmerged_world = unmerged_world
        self.enabled = False
        self.locked = False
        self.lock_level = 0
        self.opened = False
        self.activation_blocked = False
        self.linked_ref = None
        self.added_to_map: list[bool] = []
        self.moveto_calls: list[tuple[float, float, float]] = []
        self.items: dict[str, int] = {}
        self.spawned_actors: list[_FakeActor] = []

    def GetPositionX(self) -> float:
        return self.x

    def GetPositionY(self) -> float:
        return self.y

    def GetPositionZ(self) -> float:
        return self.z

    def IsInInterior(self) -> bool:
        return False

    def GetWorldSpace(self):
        return "BaseWorld" if self.unmerged_world else "Commonwealth"

    def GetParentCell(self):
        return "BaseCell" if self.unmerged_world else "ExteriorCell"

    def EnableNoWait(self, _fade: bool = False) -> None:
        self.enabled = True

    def DisableNoWait(self, _fade: bool = False) -> None:
        self.enabled = False

    def IsDisabled(self) -> bool:
        return not self.enabled

    def SetAngle(self, *_args) -> None:
        pass

    def Lock(self, val: bool = True, *_args) -> None:
        self.locked = bool(val)

    def Unlock(self, *_args) -> None:
        self.locked = False

    def BlockActivation(self, blocked: bool = True, *_args) -> None:
        self.activation_blocked = bool(blocked)

    def SetLockLevel(self, lvl: int) -> None:
        self.lock_level = int(lvl)

    def SetOpen(self, val: bool = True) -> None:
        self.opened = bool(val)

    def IsLocked(self) -> bool:
        return self.locked

    def AddItem(self, form, count: int = 1, _silent: bool = False) -> None:
        key = getattr(form, "name", str(form))
        self.items[key] = self.items.get(key, 0) + int(count)

    def GetItemCount(self, form) -> int:
        key = getattr(form, "name", str(form))
        return int(self.items.get(key, 0))

    def PlaceActorAtMe(self, base, *_args):
        a = _FakeActor(f"{self.name}_{getattr(base, 'name', base)}", self.x, self.y, self.z)
        self.spawned_actors.append(a)
        return a

    def MoveTo(self, target, ox: float = 0.0, oy: float = 0.0, oz: float = 0.0, *_args) -> None:
        self.x = target.GetPositionX() + float(ox)
        self.y = target.GetPositionY() + float(oy)
        self.z = target.GetPositionZ() + float(oz)
        self.unmerged_world = False
        self.moveto_calls.append((self.x, self.y, self.z))

    def SetLinkedRef(self, target, _kw=None, _promote: bool = True) -> None:
        self.linked_ref = target

    def AddToMap(self, allow_ft: bool = False) -> None:
        self.added_to_map.append(bool(allow_ft))


class _FakeQuest:
    def __init__(self, name: str):
        self.name = name
        self.running = False
        self.completed = False
        self.stages: list[int] = []
        self.stage = 0
        self.objectives_displayed: list[int] = []
        self.objectives_completed: list[int] = []
        self.active = False
        self.codsworth_given = 0
        self.sturges_arrived = 0
        self.advance_calls: list[tuple[int, str]] = []

    def IsRunning(self) -> bool:
        return self.running

    def StartNoWait(self) -> bool:
        self.running = True
        return True

    def SetStage(self, st: int) -> None:
        self.stage = int(st)
        self.stages.append(int(st))

    def SetObjectiveDisplayed(self, idx: int, *_args) -> None:
        self.objectives_displayed.append(int(idx))

    def SetObjectiveCompleted(self, idx: int, *_args) -> None:
        self.objectives_completed.append(int(idx))

    def SetActive(self, val: bool) -> None:
        self.active = bool(val)

    def GiveFromCodsworth(self) -> None:
        self.codsworth_given += 1

    def OnSturgesArrivedFromConcord(self) -> None:
        self.sturges_arrived += 1

    def AdvanceTo(self, st: int, by: str = "Trigger") -> None:
        self.advance_calls.append((int(st), str(by)))
        self.SetStage(st)


def _build_codsworth_harness(
    enable_s3: bool = True,
    house1_actors=None,
    house2_actors=None,
    r11_glob_val: float | None = None,
    msg_buttons=None,
    codsworth_actor=None,
    player_actor=None,
    creature_slot_ready: bool = False,
    bloatfly_base=None,
    bloatfly_markers=None,
    stage50_scene=None,
):
    psc = CODSWORTH_PSC.read_text(encoding="utf-8")
    logs: list[str] = []
    stages: list[int] = []
    done_stages: set[int] = set()
    obj_disp: list[int] = []
    obj_done: list[int] = []
    timers: list[tuple[float, int]] = []
    min00_q = _FakeQuest("FO4SF_Min00")
    quest_state = {"stage": 0, "completed": False}
    btn_iter = iter(msg_buttons or [])
    fake_msg = SimpleNamespace(Show=lambda: next(btn_iter, -1))
    r11_glob = None if r11_glob_val is None else SimpleNamespace(GetValue=lambda: float(r11_glob_val))
    slot_glob = SimpleNamespace(GetValue=lambda: 1.0 if creature_slot_ready else 0.0)
    cods_obj = codsworth_actor or _FakeActor("Codsworth", -1146.7, 1293.8, 111.7)
    h1_marker = _FakeMarker("FO4SF_S3_House01Marker", -2313.44, -1372.02, 112.66)
    h2_marker = _FakeMarker("FO4SF_S3_House02Marker", -2296.17, -1424.97, 111.77)

    def set_stage(st: int) -> None:
        quest_state["stage"] = int(st)
        done_stages.add(int(st))
        stages.append(int(st))

    def complete_quest() -> None:
        quest_state["completed"] = True

    host_wb = _FakeMarker("FO4Core_SanctuaryWorkbenchRef", -2329.25, -1420.19, 112.08)
    clock = {"rt": 100.0}

    def get_form(fid: int, plugin: str):
        if plugin == "FO4TerrainCore.esm" and fid == 0x005C50:
            return host_wb
        if plugin == "FO4SFMission.esm" and fid == 0x000800:
            return min00_q
        if plugin == "FO4SFMission.esm" and fid == 0x000B8B:
            return r11_glob
        if plugin == "FO4SF_RA5Creatures.esm" and fid == 0x000809 and creature_slot_ready:
            return bloatfly_base or SimpleNamespace(name="FO4SF_RA5BloatflyTest")
        return None

    state_vars = {
        "applied", "completed", "pendingStage", "pendingStageBy", "dialogueSeen", "dialogueMenuOpen",
        "talkBoxOpen", "sceneTalkPending", "sceneMenuOpened", "scenePhase1Entered", "scenePhase1At",
        "sceneCheckTicks", "sceneRestartCount", "scenePostActive", "talkSessionId", "codsworthTalkReloaded",
        "choice1Seen", "choice2Seen", "choice3Seen", "choice4Seen", "choicesCount", "s3House1Started",
        "s3House1Cleared", "s3House1Dead", "s3House2Started", "s3House2Cleared", "s3House2Dead",
        "s3ConcordPointed", "s3Stage", "s3SpawnedHouse1", "s3SpawnedHouse2", "s3CreatureSlotEmpty",
        "s3EmptyLogged", "s3Stage50SceneStarted", "s3Stage50Retries", "s3Stage50MenuOpened", "s3Stage50AttemptOpened",
        "s3Stage50Pending", "s3Stage50Restarting", "s3Stage50Phase1", "s3Stage50Phase1At",
        "s3Stage50AttemptStartedAt", "s3Stage50CheckTicks", "ownSceneStopPending", "sceneAttemptStartedAt",
    }
    ns = {
        "EnableS3HouseSearch": enable_s3,
        "Codsworth": cods_obj,
        "S3House1Bloatflies": house1_actors,
        "S3House2Bloatflies": house2_actors,
        "S3House1Marker": h1_marker,
        "S3House2Marker": h2_marker,
        "S3House1TravelPack": None,
        "S3House2TravelPack": None,
        "S3Stage50Scene": stage50_scene,
        "S3CreatureSlotReady": slot_glob,
        "S3BloatflyMarkers": bloatfly_markers,
        "CreaturePlugin": "FO4SF_RA5Creatures.esm",
        "CreatureBloatflyNpcId": 0x000809,
        "S3ArrivalRadius": 10.0,
        "S3House1X": -2313.44,
        "S3House1Y": -1372.02,
        "S3House1Z": 112.66,
        "S3House2X": -2296.17,
        "S3House2Y": -1424.97,
        "S3House2Z": 111.77,
        "S3House1RequiredKills": 3,
        "S3House2RequiredKills": 3,
        "SceneOpenCheckSeconds": 1.5,
        "SceneMaxWaitChecks": 16,
        "MaxSceneRestarts": 3,
        "dialogueMenuOpen": False,
        "CodsworthTalkMsg": fake_msg,
        "CodsworthReply0Msg": fake_msg,
        "CodsworthReply1Msg": fake_msg,
        "CodsworthReply2Msg": fake_msg,
        "applied": 0,
        "completed": False,
        "pendingStage": -1,
        "pendingStageBy": "other",
        "dialogueSeen": False,
        "talkBoxOpen": False,
        "talkSessionId": 0,
        "codsworthTalkReloaded": False,
        "choice1Seen": False,
        "choice2Seen": False,
        "choice3Seen": False,
        "choice4Seen": False,
        "choicesCount": 0,
        "s3House1Started": False,
        "s3House1Cleared": False,
        "s3House1Dead": 0,
        "s3House2Started": False,
        "s3House2Cleared": False,
        "s3House2Dead": 0,
        "s3ConcordPointed": False,
        "s3Stage": 0,
        "s3SpawnedHouse1": None,
        "s3SpawnedHouse2": None,
        "s3CreatureSlotEmpty": False,
        "s3EmptyLogged": False,
        "dialogueMenuOpen": False,
        "sceneTalkPending": False,
        "sceneMenuOpened": False,
        "scenePhase1Entered": False,
        "scenePhase1At": 0.0,
        "sceneCheckTicks": 0,
        "sceneRestartCount": 0,
        "scenePostActive": False,
        "s3Stage50SceneStarted": False,
        "s3Stage50Retries": 0,
        "s3Stage50MenuOpened": False,
        "s3Stage50AttemptOpened": False,
        "s3Stage50Pending": False,
        "s3Stage50Restarting": False,
        "s3Stage50Phase1": False,
        "s3Stage50Phase1At": 0.0,
        "s3Stage50AttemptStartedAt": 0.0,
        "s3Stage50CheckTicks": 0,
        "ownSceneStopPending": False,
        "sceneAttemptStartedAt": 0.0,
        "SceneOpenCheckSeconds": 1.5,
        "SceneMaxWaitChecks": 16,
        "MaxSceneRestarts": 3,
        "talkProxy": None,
        "GetStage": lambda: quest_state["stage"],
        "GetStageDone": lambda st: int(st) in done_stages,
        "SetStage": set_stage,
        "SetObjectiveDisplayed": lambda idx, *_a: obj_disp.append(int(idx)),
        "SetObjectiveCompleted": lambda idx, *_a: obj_done.append(int(idx)),
        "SetActive": lambda _v: None,
        "StartTimer": lambda sec, tid: timers.append((float(sec), int(tid))),
        "CancelTimer": lambda _tid: None,
        "CompleteQuest": complete_quest,
        "ResolveCodsworth": lambda: cods_obj,
        "ResolveCodsworthScene": lambda: None,
        "ResolveCodsworthPostScene": lambda: None,
        "EnsureSafeCodsworthCameraDistance": lambda *_: None,
        "RestartOrFailCodsworthScene": lambda *_: None,
        "EnsureCodsworthAlias": lambda *_: None,
        "RegisterForRemoteEvent": lambda *_: None,
        "IsWarfareMode": lambda: False,
        "ShouldUseMessageBox": lambda: bool(msg_buttons),
        "Trace": lambda msg: logs.append(str(msg)),
        "Utility": SimpleNamespace(GetCurrentRealTime=lambda: clock["rt"]),
        "Game": SimpleNamespace(GetFormFromFile=get_form, GetPlayer=lambda: player_actor),
    }
    _compile_papyrus(
        psc,
        [
            "EffectiveStage",
            "ResolveTalkMsg",
            "AdvanceTo",
            "SyncProgress",
            "RunCodsworthTalk",
            "CountDeadActors",
            "InitS3SpawnedArrays",
            "ResolveCommonwealthHostAnchor",
            "PlaceMarkerInCommonwealth",
            "DriveCodsworthToS3Marker",
            "SpawnS3HouseBloatflies",
            "IsActorNearS3House",
            "GetCodsworthHouseDist",
            "IsArrivedAtS3House",
            "StartS3House1Search",
            "StartS3House2Search",
            "RecordS3BloatflyKill",
            "StartS3Stage50Scene",
            "RestartOrCompleteS3Stage50Scene",
            "CheckS3Stage50SceneOpen",
            "UpdateS3HouseSearchProgress",
            "CompleteS3AndPointToConcord",
            "OnMenuOpenCloseEvent",
            "Scene.OnBegin",
            "Scene.OnPhaseBegin",
            "Scene.OnEnd",
        ],
        state_vars,
        ns,
    )
    return SimpleNamespace(ns=ns, logs=logs, stages=stages, obj_disp=obj_disp, obj_done=obj_done, timers=timers, min00=min00_q, state=quest_state, cods=cods_obj, player=player_actor, h1_marker=h1_marker, h2_marker=h2_marker, clock=clock, host_wb=host_wb)


def _build_min00_harness(
    enable_s4: bool = True,
    enable_s6_s9: bool = True,
    keeper_only: bool = False,
    musket_id: int = 0,
    cell_id: int = 0,
    cap_id: int = 0,
    with_forms: bool = True,
    with_markers: bool = True,
    with_group: bool = True,
    unmerged_markers: bool = False,
    comp_musket_id: int = 0,
    comp_ammo_id: int = 0,
    bobby_pin_id: int = 0,
    stimpak_id: int = 0,
    stop_at_core: bool = True,
    museum_anchor=None,
    museum_cell=None,
    museum_raiders=None,
    museum_doors=None,
    museum_loot=None,
    preston_door=None,
    preston_exit_door=None,
    basement_gate=None,
    basement_term=None,
    medkit_ref=None,
    s4_display_musket_ref=None,
    s4_fusion_cell_refs=None,
    s6_preston_scene=None,
    s6_sturges_scene=None,
    use_msgbox: bool = False,
):
    psc = MIN00_PSC.read_text(encoding="utf-8")
    logs: list[str] = []
    msgboxes: list[str] = []
    host_wb = _FakeMarker("FO4Core_SanctuaryWorkbenchRef", -2329.25, -1420.19, 112.08)
    stages: list[int] = []
    done_stages: set[int] = set()
    obj_disp: list[int] = []
    obj_done: list[int] = []
    timers: list[tuple[float, int]] = []
    sanctuary_q = _FakeQuest("FO4SF_Sanctuary01")
    mq103_q = _FakeQuest("FO4SF_MQ103")
    minrecruit00_q = _FakeQuest("FO4SF_MinRecruit00")
    dc_marker = _FakeMarker("FO4SF_DiamondCityMapMarker", -1416.36, -3129.39, 21.80, unmerged_world=unmerged_markers)
    musket_form = SimpleNamespace(name="FO4_LaserMusket")
    comp_musket_form = SimpleNamespace(name="FO4_CompPrestonLaserMusket")
    cell_form = SimpleNamespace(name="FO4_AmmoFusionCell")
    comp_cell_form = SimpleNamespace(name="FO4_CompanionAmmoFusionCell")
    cap_form = SimpleNamespace(name="FO4_Bottlecap")
    pin_form = SimpleNamespace(name="FO4_BobbyPin")
    stimpak_form = SimpleNamespace(name="FO4SF_Stimpak")
    credits_form = SimpleNamespace(name="Starfield_Credits")

    preston = _FakeActor("Preston", -2011.14, -1697.54, 89.09)
    player = _FakeActor("Player", -2015.0, -1690.0, 89.0)
    group = [_FakeActor("Sturges", -2010.0, -1698.0, 89.0), _FakeActor("MamaMurphy", -2011.0, -1698.0, 89.0)] if with_group else None
    s4_marker = _FakeMarker("FO4SF_S4_PrestonBalconyMarker", -2010.51, -1697.71, 98.51) if with_markers else None
    s9_exit = _FakeMarker("FO4SF_S9_MuseumExitMarker", -2010.57, -1697.94, 89.26) if with_markers else None
    patrol_coords = [
        (-2061.23, -1657.46, 86.93),
        (-2112.00, -1634.00, 88.23),
        (-2140.00, -1608.00, 90.13),
        (-2174.00, -1574.00, 103.67),
        (-2206.00, -1528.00, 106.43),
        (-2278.00, -1532.00, 107.74),
        (-2332.00, -1474.00, 108.33),
        (-2356.32, -1470.44, 109.14),
    ]
    waypoints = [_FakeMarker(f"FO4SF_S9_PatrolWP_{i}", *c, unmerged_world=unmerged_markers) for i, c in enumerate(patrol_coords)] if with_markers else None
    clock = {"rt": 100.0}
    quest_state = {"stage": 0, "completed": False}
    keeper_mode_calls: list[tuple[bool, bool]] = []
    keeper_state = {"prestonFollow": False, "s4BalconyActive": False, "s9PatrolRelease": False}

    def keeper_apply_mode(balcony: bool, patrol: bool) -> None:
        keeper_mode_calls.append((bool(balcony), bool(patrol)))
        keeper_state["s4BalconyActive"] = bool(balcony)
        keeper_state["s9PatrolRelease"] = bool(patrol)
        if balcony or patrol:
            keeper_state["prestonFollow"] = True

    keeper_q = SimpleNamespace(ApplyPrestonMode=keeper_apply_mode, state=keeper_state, calls=keeper_mode_calls)
    self_sentinel = SimpleNamespace(name="SelfMin00")

    def set_stage(st: int) -> None:
        quest_state["stage"] = int(st)
        done_stages.add(int(st))
        stages.append(int(st))

    def get_form(fid: int, plugin: str):
        if plugin == "FO4SFMission.esm":
            if fid == 0x000814:
                return keeper_q
            if fid == 0x000817:
                return sanctuary_q
            if fid == 0x000A50:
                return mq103_q
            if fid == 0x000A20:
                return minrecruit00_q
            if fid == 0x000B8A:
                return dc_marker
        if plugin == "FO4TerrainCore.esm" and fid == 0x005C50:
            return host_wb
        if plugin == "FO4Port.esm":
            if fid == 0x00E2F4:
                return museum_cell
            if fid == 0x00E2F5:
                return museum_anchor
            if fid == 0x00EFA9:
                return preston_door
            if fid == 0x00EFAA:
                return preston_exit_door
            if fid == 0x00EDF0:
                return basement_gate
            if fid == 0x00E35E:
                return basement_term
            if fid == 0x00E3B6:
                return medkit_ref
        if plugin == "FO4SFCoreValues.esm" and with_forms:
            if musket_id and fid == musket_id:
                return musket_form
            if comp_musket_id and fid == comp_musket_id:
                return comp_musket_form
            if cell_id and fid == cell_id:
                return cell_form
            if comp_ammo_id and fid == comp_ammo_id:
                return comp_cell_form
            if cap_id and fid == cap_id:
                return cap_form
            if bobby_pin_id and fid == bobby_pin_id:
                return pin_form
            if stimpak_id and fid == stimpak_id:
                return stimpak_form
        return None

    state_vars = {
        "applied", "prestonHeld", "prestonHolds", "prestonMoves", "prestonOff", "prestonState",
        "prestonPlaced", "prestonFollow", "prestonTalkReloaded", "prestonDialogueMenuOpen",
        "prestonScenePending", "prestonSceneMenuOpened", "prestonScenePhase1", "prestonPhase1At",
        "prestonSceneChecks", "prestonSceneRestarts", "ownPrestonSceneStop", "prestonAttemptStartedAt",
        "prestonPostSceneActive", "prestonTalkBoxOpen", "prestonFallbackActive", "prestonTalkLogged",
        "prestonUsedFallback", "talkActivated", "talkStartedAt", "talkFailures",
        "s4BalconySetup", "s4BalconyActive", "s4PrestonArmed", "s4StreetCleared", "s4MusketTaken", "s4FusionCellsPlaced",
        "s5MuseumInitialized", "s5MuseumCleared", "s5MuseumRaidersDead", "s5RaiderEngageTicks", "s6BasementUnlockedPending",
        "min00Given", "pendingStage", "pendingStageBy",
        "s6RoomEventsRegistered", "s6RoomScenePending", "s6RoomSceneMenuOpened",
        "s6RoomSceneRestarting", "s6RoomScenePhase1", "s6RoomPhase1At", "s6RoomAttemptStartedAt", "s6RoomSceneRetries",
        "s6RoomSceneTicks", "s6SturgesScenePending", "s6SturgesSceneMenuOpened",
        "s6SturgesSceneRestarting", "s6SturgesScenePhase1", "s6SturgesPhase1At",
        "s6SturgesAttemptStartedAt", "s6SturgesSceneRetries", "s6SturgesSceneTicks", "s6FullStage",
        "s9LobbyCompleted", "s9DiamondCityRevealed", "s9DiamondCityMerged", "s9PatrolStarted",
        "s9PatrolRelease", "s9PatrolStartedAt", "s9PatrolElapsed", "s9GroupArrived", "s9ArrivalVia",
    }
    ns = {
        "Self": self_sentinel,
        "Preston": preston,
        "PrestonWeapon": SimpleNamespace(name="Orion"),
        "PrestonAmmo": SimpleNamespace(name="AmmoLaser"),
        "Credits": credits_form,
        "KeeperOnly": keeper_only,
        "EnableS4Balcony": enable_s4,
        "EnableS6ToS9Full": enable_s6_s9,
        "StopAtFusionCorePowerArmor": stop_at_core,
        "S4BalconyMarker": s4_marker,
        "S9MuseumExitMarker": s9_exit,
        "S9PatrolWaypoints": waypoints,
        "DiamondCityMapMarker": dc_marker if with_markers else None,
        "MinutemenGroup": group,
        "SturgesRef": group[0] if group else None,
        "S5MuseumRaiders": museum_raiders,
        "S5MuseumDoors": museum_doors,
        "S5MuseumLootMarkers": museum_loot,
        "S4DisplayMusketRef": s4_display_musket_ref,
        "S4FusionCellRefs": list(s4_fusion_cell_refs or []),
        "S6PrestonRoomScene": s6_preston_scene,
        "S6SturgesRoomScene": s6_sturges_scene,
        "PrestonSceneCheckSeconds": 1.5,
        "PrestonSceneMaxWaitChecks": 16,
        "PrestonMaxSceneRestarts": 3,
        "S4ExteriorRaiderCount": 3,
        "S4BalconyX": -2010.51,
        "S4BalconyY": -1697.71,
        "S4BalconyZ": 98.51,
        "S4BalconyZLabel": "98.51",
        "S9MuseumExitX": -2010.57,
        "S9MuseumExitY": -1697.94,
        "S9MuseumExitZ": 89.26,
        "DiamondCityMapMarkerId": 0x000B8A,
        "DiamondCityMapMarkerX": -1416.36,
        "DiamondCityMapMarkerY": -3129.39,
        "DiamondCityMapMarkerZ": 21.80,
        "PrestonLocalX": -811.14,
        "PrestonLocalY": 1002.46,
        "PrestonLocalZ": 89.09,
        "MergeOffsetX": -1200.0,
        "MergeOffsetY": -2700.0,
        "LaserMusketId": musket_id,
        "CompPrestonMusketId": comp_musket_id,
        "CompPrestonAmmoId": comp_ammo_id,
        "FusionCellId": cell_id,
        "BottlecapId": cap_id,
        "BobbyPinId": bobby_pin_id,
        "StimpakId": stimpak_id,
        "S4MusketFusionCells": 15,
        "S9RewardCaps": 100,
        "S9RewardFusionCells": 50,
        "S9PatrolFailsafeSeconds": 180.0,
        "S9SanctuaryX": -2356.32,
        "S9SanctuaryY": -1470.44,
        "S9SanctuaryZ": 109.14,
        "S9SanctuaryPlayerRadius": 120.0,
        "S9SanctuaryGroupFarDist": 150.0,
        "S9SanctuaryArrivalRadius": 35.0,
        "HoldRadius": 25.0,
        "HeldRadius": 3.0,
        "RelocateGap": 1500.0,
        "PlaceRadius": 300.0,
        "applied": 0,
        "prestonHeld": True,
        "prestonHolds": 0,
        "prestonMoves": 0,
        "prestonOff": 0.0,
        "prestonState": "none",
        "prestonPlaced": True,
        "prestonFollow": False,
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
        "prestonTalkBoxOpen": False,
        "prestonFallbackActive": False,
        "prestonTalkLogged": False,
        "prestonUsedFallback": False,
        "talkActivated": False,
        "talkStartedAt": 0.0,
        "talkFailures": 0,
        "s4BalconySetup": False,
        "s4BalconyActive": False,
        "s4PrestonArmed": False,
        "s4StreetCleared": False,
        "s4MusketTaken": False,
        "s4FusionCellsPlaced": False,
        "s5MuseumInitialized": False,
        "s5MuseumCleared": False,
        "s5MuseumRaidersDead": 0,
        "s5RaiderEngageTicks": 0,
        "min00Given": False,
        "pendingStage": -1,
        "pendingStageBy": "other",
        "s6BasementUnlockedPending": False,
        "s6RoomEventsRegistered": False,
        "s6RoomScenePending": False,
        "s6RoomSceneMenuOpened": False,
        "s6RoomSceneRestarting": False,
        "s6RoomScenePhase1": False,
        "s6RoomPhase1At": 0.0,
        "s6RoomAttemptStartedAt": 0.0,
        "s6RoomSceneRetries": 0,
        "s6RoomSceneTicks": 0,
        "s6SturgesScenePending": False,
        "s6SturgesSceneMenuOpened": False,
        "s6SturgesSceneRestarting": False,
        "s6SturgesScenePhase1": False,
        "s6SturgesPhase1At": 0.0,
        "s6SturgesAttemptStartedAt": 0.0,
        "s6SturgesSceneRetries": 0,
        "s6SturgesSceneTicks": 0,
        "s6FullStage": 0,
        "s9LobbyCompleted": False,
        "s9DiamondCityRevealed": False,
        "s9DiamondCityMerged": False,
        "s9PatrolStarted": False,
        "s9PatrolRelease": False,
        "s9PatrolStartedAt": 0.0,
        "s9PatrolElapsed": 0.0,
        "s9GroupArrived": False,
        "s9ArrivalVia": "",
        "EffectiveStage": lambda: quest_state["stage"],
        "AdvanceTo": lambda st, _by="info": set_stage(st),
        "GetStage": lambda: quest_state["stage"],
        "GetStageDone": lambda st: int(st) in done_stages,
        "SetStage": set_stage,
        "SetObjectiveDisplayed": lambda idx, *_a: obj_disp.append(int(idx)),
        "SetObjectiveCompleted": lambda idx, *_a: obj_done.append(int(idx)),
        "SetActive": lambda _v: None,
        "StartTimer": lambda sec, tid: timers.append((float(sec), int(tid))),
        "CancelTimer": lambda _tid: None,
        "RegisterForRemoteEvent": lambda *_a: None,
        "ShouldUseMessageBox": lambda: bool(use_msgbox),
        "CompleteQuest": lambda: quest_state.__setitem__("completed", True),
        "IsCommonwealthExterior": lambda p: p is not None and not p.IsInInterior(),
        "IsPlayerStableAt": lambda p, *_a: p is not None and not p.IsInInterior(),
        "IsTestModeEnabled": lambda: False,
        "SyncS5ExteriorDoors": lambda *_a: None,
        "Apply": lambda st, _by="other": quest_state.__setitem__("stage", int(st)),
        "EnsureActorTalkable": lambda a: a.AllowPCDialogue(True) if a else None,
        "ArmRaiderForCombat": lambda *_a: None,
        "EquipBalancedRaiderSidearm": lambda *_a: None,
        "Trace": lambda msg: logs.append(str(msg)),
        "ResolvePrestonScene": lambda: None,
        "ResolvePrestonPostScene": lambda: None,
        "RestartOrFailPrestonScene": lambda *_: None,
        "FallbackPrestonToMessageBox": lambda *_: None,
        "Utility": SimpleNamespace(GetCurrentRealTime=lambda: clock["rt"]),
        "Debug": SimpleNamespace(Notification=lambda _m: None, MessageBox=lambda m: msgboxes.append(str(m))),
        "Game": SimpleNamespace(GetFormFromFile=get_form, GetPlayer=lambda: player),
    }
    _compile_papyrus(
        psc,
        [
            "HeldState",
            "HoldDue",
            "EnsureActorTalkable",
            "HoldActor",
            "HoldPreston",
            "SpotOff",
            "PlaceAt",
            "PlacePreston",
            "LookupOptionalForm",
            "ApplyPrestonMode",
            "SyncKeeperPrestonMode",
            "MaintainS4PrestonBalcony",
            "RelocateMarkerToMergedWorld",
            "MoveActorToExteriorSpot",
            "ResolveCommonwealthHostAnchor",
            "PlaceMarkerInCommonwealth",
            "SyncS4DisplayPickups",
            "ArmPrestonBalconyMusket",
            "SetupS4BalconyEncounter",
            "TryGrantS4FallenMinutemanMusket",
            "IsPlayerInMuseum",
            "PlaceRefInMuseum",
            "UnlockS6RoomDoors",
            "RegisterS6RoomEvents",
            "InitializeS5MuseumEncounter",
            "UpdateS5MuseumEncounter",
            "PlayerHasBobbyPin",
            "TryOpenS6BasementGate",
            "TriggerS6RoomScene",
            "HandleS6RoomSceneEnded",
            "RestartOrFailS6RoomScene",
            "CheckS6RoomSceneOpen",
            "AdvanceS6PrestonGroupTalk",
            "AdvanceS6BasementGateOpened",
            "AdvanceS6FusionCorePicked",
            "ResolveDiamondCityMapMarker",
            "RevealDiamondCityMapMarker",
            "CompleteS9LobbyTalkAndReward",
            "PrepareAndChainS9PatrolWaypoints",
            "BeginS9MuseumExitAndPatrol",
            "ResumeS9PatrolAfterLoad",
            "CheckS9SanctuaryArrival",
            "OnMenuOpenCloseEvent",
            "Scene.OnPhaseBegin",
            "Scene.OnEnd",
        ],
        state_vars,
        ns,
    )
    return SimpleNamespace(
        ns=ns, logs=logs, msgboxes=msgboxes, stages=stages, obj_disp=obj_disp, obj_done=obj_done, timers=timers,
        preston=preston, player=player, group=group, waypoints=waypoints,
        dc_marker=dc_marker, sanctuary=sanctuary_q, mq103=mq103_q, minrecruit00=minrecruit00_q,
        keeper=keeper_q, clock=clock, state=quest_state, host_wb=host_wb,
    )


class TestR11Step3qDefaultOffGating(unittest.TestCase):
    """Hard gating rule: --r11-full-mission defaults to 0 (OFF) and runtime booleans default False."""

    def test_program_cs_flag_defaults_off_and_preserves_2g_stages(self):
        cs = PROGRAM_CS.read_text(encoding="utf-8")
        self.assertIn('BoolFlag(args, "--r11-full-mission", false)', cs)
        self.assertIn("bool r11FullMission = false", cs)
        self.assertIn("public static readonly ushort[] Stages = { 10, 20, 30, 35, 40, 200 };", cs)
        self.assertIn("public static readonly ushort[] CodsworthQuestStages = { 10, 20, 30, 40, 100 };", cs)
        self.assertIn("public static readonly ushort[] FullStages = { 10, 20, 30, 35, 40, 45, 50, 60, 65, 70, 75, 80, 90, 100, 150, 200 };", cs)
        self.assertIn("public static readonly ushort[] CodsworthFullStages = { 10, 20, 22, 24, 30, 32, 34, 36, 38, 40, 50, 100 };", cs)
        self.assertIn("public static readonly short[] CodsworthFullChoiceEndStages = { 20, 22, 24, 30 };", cs)
        self.assertIn("public const uint DiamondCityMapMarkerId = 0xB8A;", cs)
        self.assertIn("public const uint R11FullMissionGlobId = 0xB8B;", cs)
        # #552 safety guard: Mission.Points refuses .esm/.esp/.esl/.ba2 output paths
        self.assertIn("public static void ValidatePointsOutPath(string outPath)", cs)
        for ext in (".esm", ".esp", ".esl", ".ba2"):
            self.assertIn(f'"{ext}"', cs)

    def test_papyrus_properties_default_false_and_zero(self):
        cw = CODSWORTH_PSC.read_text(encoding="utf-8")
        m0 = MIN00_PSC.read_text(encoding="utf-8")
        self.assertIn("bool Property EnableS3HouseSearch = False Auto Const", cw)
        self.assertIn("bool Property EnableS4Balcony = False Auto Const", m0)
        self.assertIn("bool Property EnableS6ToS9Full = False Auto Const", m0)
        self.assertIn("int Property LaserMusketId = 0 Auto Const", m0)
        self.assertIn("int Property FusionCellId = 0 Auto Const", m0)
        self.assertIn("int Property BottlecapId = 0 Auto Const", m0)
        # Preserve Review Item #1 Preston talk unlock
        self.assertIn("prestonFallbackActive = False", m0)

    def test_default_off_runtime_is_strict_noop(self):
        ch = _build_codsworth_harness(enable_s3=False)
        self.assertFalse(ch.ns["StartS3House1Search"]())
        self.assertEqual(ch.ns["RecordS3BloatflyKill"](1), 0)
        ch.ns["UpdateS3HouseSearchProgress"]()
        self.assertEqual(ch.stages, [])
        self.assertEqual(ch.logs, [])

        mh = _build_min00_harness(enable_s4=False, enable_s6_s9=False)
        self.assertFalse(mh.ns["SetupS4BalconyEncounter"](mh.player))
        self.assertFalse(mh.ns["TryGrantS4FallenMinutemanMusket"](mh.player))
        self.assertFalse(mh.ns["AdvanceS6PrestonGroupTalk"]())
        self.assertFalse(mh.ns["CompleteS9LobbyTalkAndReward"](mh.player))
        self.assertFalse(mh.ns["BeginS9MuseumExitAndPatrol"](mh.player))
        self.assertFalse(mh.ns["CheckS9SanctuaryArrival"](mh.player, 200.0))
        self.assertEqual(mh.stages, [])
        self.assertEqual(mh.logs, [])


class TestR11S3HouseSearch(unittest.TestCase):
    """S3 Sanctuary House 1 (3 Bloatflies) + House 2 (3 Bloatflies) exact FO4 stage progression."""

    def test_exact_coordinates_and_3_plus_3_bloatflies(self):
        cw = CODSWORTH_PSC.read_text(encoding="utf-8")
        self.assertIn("float Property S3House1X = -2313.44 Auto Const", cw)
        self.assertIn("float Property S3House1Y = -1372.02 Auto Const", cw)
        self.assertIn("float Property S3House1Z = 112.66 Auto Const", cw)
        self.assertIn("float Property S3House2X = -2296.17 Auto Const", cw)
        self.assertIn("float Property S3House2Y = -1424.97 Auto Const", cw)
        self.assertIn("float Property S3House2Z = 111.77 Auto Const", cw)
        self.assertIn("int Property S3House1RequiredKills = 3 Auto Const", cw)
        self.assertIn("int Property S3House2RequiredKills = 3 Auto Const", cw)
        # Strictly Bloatflies in S3 House 1/2, never unverified Radroaches
        self.assertNotIn("Radroach", cw)

    def test_s3_stage_chain_via_kills_and_exact_log_lines(self):
        ch = _build_codsworth_harness(enable_s3=True)
        self.assertTrue(ch.ns["StartS3House1Search"]())
        self.assertEqual(ch.stages, [20, 30, 32])
        self.assertIn("codsworth01 stage 30 house=1", ch.logs)

        # Fewer than 3 kills must NOT clear House 1
        self.assertEqual(ch.ns["RecordS3BloatflyKill"](1), 1)
        self.assertEqual(ch.ns["RecordS3BloatflyKill"](1), 2)
        self.assertFalse(ch.ns["s3House1Cleared"])
        self.assertEqual(ch.stages, [20, 30, 32])

        # 3rd Bloatfly kill clears House 1 -> stage 34 -> starts House 2 -> stages 36, 38
        self.assertEqual(ch.ns["RecordS3BloatflyKill"](1), 3)
        self.assertTrue(ch.ns["s3House1Cleared"])
        self.assertIn("codsworth01 house1_cleared dead=3/3 stage=34", ch.logs)
        self.assertIn("codsworth01 stage 36 house=2", ch.logs)
        self.assertEqual(ch.stages, [20, 30, 32, 34, 36, 38])

        # Fewer than 3 kills in House 2 must NOT complete S3
        self.assertEqual(ch.ns["RecordS3BloatflyKill"](2), 1)
        self.assertEqual(ch.ns["RecordS3BloatflyKill"](2), 2)
        self.assertFalse(ch.ns["s3House2Cleared"])
        self.assertFalse(ch.state["completed"])

        # 3rd House 2 Bloatfly kill -> stages 40, 50, 100 + Concord handoff
        self.assertEqual(ch.ns["RecordS3BloatflyKill"](2), 3)
        self.assertEqual(ch.stages, [20, 30, 32, 34, 36, 38, 40, 50, 100])
        self.assertIn("codsworth01 house2_cleared dead=3/3 stage=40", ch.logs)
        self.assertIn("codsworth01 stage 100 concord_pointed=true", ch.logs)
        self.assertTrue(ch.state["completed"])
        self.assertEqual(ch.min00.codsworth_given, 1)

    def test_s3_actor_array_polling_drives_full_progression(self):
        h1 = [_FakeActor(f"BF1_{i}", dead=False) for i in range(3)]
        h2 = [_FakeActor(f"BF2_{i}", dead=False) for i in range(3)]
        ch = _build_codsworth_harness(enable_s3=True, house1_actors=h1, house2_actors=h2)
        # Pre-search choices 20/22/24 must NOT prematurely trigger House 1 before Choice 3 (stage 30)
        ch.ns["applied"] = 24
        ch.ns["UpdateS3HouseSearchProgress"]()
        self.assertEqual(ch.stages, [])
        ch.ns["applied"] = 30
        ch.ns["UpdateS3HouseSearchProgress"]()
        self.assertEqual(ch.stages, [30, 32])
        for a in h1:
            a.dead = True
        ch.ns["UpdateS3HouseSearchProgress"]()
        self.assertEqual(ch.stages, [30, 32, 34, 36, 38])
        for a in h2:
            a.dead = True
        ch.ns["UpdateS3HouseSearchProgress"]()
        self.assertEqual(ch.stages, [30, 32, 34, 36, 38, 40, 50, 100])
        self.assertTrue(ch.state["completed"])

    def test_s3_codsworth_talk_choice3_does_not_skip_s3_in_full_mission(self):
        """P1 #4: Under --r11-full-mission 1 (GLOB 0xB8B == 1), RunCodsworthTalk choice 3 ends at stage 30 (NOT 100)."""
        # Default 0 mode (GLOB 0xB8B absent): choice 3 completes at stage 100 (2g-fix parity)
        ch0 = _build_codsworth_harness(enable_s3=False, r11_glob_val=None, msg_buttons=[0, 1, 2, 3])
        ch0.ns["RunCodsworthTalk"]()
        self.assertEqual(ch0.stages, [20, 30, 40, 100])
        self.assertTrue(ch0.state["completed"])

        # Full mission mode (GLOB 0xB8B == 1): choices 0..3 hit 20, 22, 24, 30 (NOT 100!), then S3 runs
        h1 = [_FakeActor(f"BF1_{i}", dead=False) for i in range(3)]
        h2 = [_FakeActor(f"BF2_{i}", dead=False) for i in range(3)]
        ch1 = _build_codsworth_harness(enable_s3=True, house1_actors=h1, house2_actors=h2, r11_glob_val=1.0, msg_buttons=[0, 1, 2, 3])
        ch1.ns["RunCodsworthTalk"]()
        self.assertEqual(ch1.stages, [20, 22, 24, 30])
        self.assertFalse(ch1.state["completed"])
        self.assertIn((0.1, 1), ch1.timers)
        ch1.ns["UpdateS3HouseSearchProgress"]()
        self.assertTrue(ch1.ns["s3House1Started"])
        self.assertFalse(ch1.state["completed"])
        for a in h1:
            a.dead = True
        ch1.ns["UpdateS3HouseSearchProgress"]()
        for a in h2:
            a.dead = True
        ch1.ns["UpdateS3HouseSearchProgress"]()
        self.assertTrue(ch1.state["completed"])
        self.assertIn("codsworth01 stage 100 concord_pointed=true", ch1.logs)


class TestR11S4BalconyAndMusket(unittest.TestCase):
    """S4 Preston balcony placement (Z=98.51 m), 3 exterior raiders, obj 60/70, nullable Laser Musket."""

    def test_s4_balcony_placement_objectives_and_log(self):
        mh = _build_min00_harness(enable_s4=True, enable_s6_s9=True)
        self.assertTrue(mh.ns["SetupS4BalconyEncounter"](mh.player))
        self.assertAlmostEqual(mh.preston.x, -2010.51, places=2)
        self.assertAlmostEqual(mh.preston.y, -1697.71, places=2)
        self.assertAlmostEqual(mh.preston.z, 98.51, places=2)
        self.assertIn(60, mh.obj_disp)
        self.assertIn(70, mh.obj_disp)
        self.assertIn("s4 balcony preston_z=98.51 ext_raiders=3", mh.logs)
        # P1 #1(d): both 0x0800 and 0x0814 keeper yield street PlacePreston and maintain balcony Z=98.51
        self.assertTrue(mh.ns["prestonFollow"])
        self.assertTrue(mh.ns["s4BalconyActive"])
        self.assertEqual(mh.keeper.calls, [(True, False)])
        self.assertFalse(mh.ns["PlacePreston"](mh.player, "mission"))
        mh.preston.SetPosition(-2011.14, -1697.54, 89.09)
        mh.ns["MaintainS4PrestonBalcony"](mh.player, "keeper")
        self.assertAlmostEqual(mh.preston.z, 98.51, places=2)
        self.assertTrue(mh.preston.restrained)

    def test_s4_laser_musket_nullable_when_unbuilt_and_grants_36_cells_when_built(self):
        # Unbuilt weapon (LaserMusketId == 0): zero crash, clean skip
        mh0 = _build_min00_harness(enable_s4=True, musket_id=0, cell_id=0)
        self.assertFalse(mh0.ns["TryGrantS4FallenMinutemanMusket"](mh0.player))
        self.assertEqual(mh0.player.items, {})
        self.assertIn("s4 laser_musket skipped reason=not_built_yet", mh0.logs)

        # Built weapon + Fusion Cells: grants 1 musket + 15 cells, completes obj 70, idempotent
        mh1 = _build_min00_harness(enable_s4=True, musket_id=0x000901, cell_id=0x000902, with_forms=True)
        self.assertTrue(mh1.ns["TryGrantS4FallenMinutemanMusket"](mh1.player))
        self.assertEqual(mh1.player.items.get("FO4_LaserMusket"), 1)
        self.assertEqual(mh1.player.items.get("FO4_AmmoFusionCell"), 15)
        self.assertIn(70, mh1.obj_done)
        self.assertIn("s4 laser_musket granted cells=15", mh1.logs)
        self.assertFalse(mh1.ns["TryGrantS4FallenMinutemanMusket"](mh1.player))


class TestR11S6AndS9FullWiring(unittest.TestCase):
    """S6 stages 40/45/50 + S9 exact FO4 reward, Diamond City AddToMap(), P9 Red Rocket patrol, failsafe & HARD STOP."""

    def test_s9_red_rocket_patrol_coords_never_enter_east_quarry(self):
        cs = PROGRAM_CS.read_text(encoding="utf-8")
        m = re.search(r"S9RedRocketPatrolCoords\s*=\s*\{(.*?)\};", cs, re.S)
        self.assertIsNotNone(m, "S9RedRocketPatrolCoords missing in Program.cs")
        coords = [
            (float(x), float(y), float(z))
            for x, y, z in re.findall(r"new\(\s*(-?[\d.]+)f\s*,\s*(-?[\d.]+)f\s*,\s*(-?[\d.]+)f\s*\)", m.group(1))
        ]
        self.assertEqual(len(coords), 8)
        # Every waypoint stays strictly west of Concord east quarry (X <= -2060) and reaches Sanctuary (-2356.32)
        for wx, wy, _wz in coords:
            self.assertLessEqual(wx, -2060.0)
            self.assertGreaterEqual(wy, -1700.0)
            self.assertLessEqual(wy, -1450.0)
        self.assertAlmostEqual(coords[-1][0], -2356.32, places=2)
        self.assertAlmostEqual(coords[-1][1], -1470.44, places=2)

    def test_s6_stages_and_s9_lobby_reward_addtomap_patrol_walk_arrival(self):
        mh = _build_min00_harness(
            enable_s4=True, enable_s6_s9=True,
            cap_id=0x000903, cell_id=0x000902, with_forms=True,
        )
        # S6 out-of-order guard
        self.assertFalse(mh.ns["AdvanceS6BasementGateOpened"]())
        self.assertFalse(mh.ns["AdvanceS6FusionCorePicked"]())
        self.assertTrue(mh.ns["AdvanceS6PrestonGroupTalk"]())
        self.assertTrue(mh.ns["AdvanceS6BasementGateOpened"]())
        self.assertTrue(mh.ns["AdvanceS6FusionCorePicked"]())
        self.assertEqual(mh.stages, [40, 45, 50])
        self.assertIn("s6 stage 40 preston_group talk", mh.logs)
        self.assertIn("s6 stage 45 basement_gate opened", mh.logs)
        self.assertIn("s6 stage 50 fusion_core picked obj=95 stop=put_fusion_core_in_pa", mh.logs)
        self.assertIn(95, mh.obj_disp)

        # S9 lobby talk: 100 Caps + 50 Fusion Cells, 0 Starfield Credits, real 0xB8A MapMarker enabled + AddToMap, MQ103/MinRecruit00 @ 0
        self.assertTrue(mh.ns["CompleteS9LobbyTalkAndReward"](mh.player))
        self.assertEqual(mh.player.items.get("FO4_Bottlecap"), 100)
        self.assertEqual(mh.player.items.get("FO4_AmmoFusionCell"), 50)
        self.assertNotIn("Starfield_Credits", mh.player.items)
        self.assertTrue(mh.dc_marker.enabled)
        self.assertEqual(mh.dc_marker.added_to_map, [False])
        self.assertIn(90, mh.stages)
        self.assertIn(150, mh.stages)
        self.assertEqual(mh.mq103.stage, 0)
        self.assertFalse(mh.mq103.running)
        self.assertEqual(mh.minrecruit00.stage, 0)
        self.assertFalse(mh.minrecruit00.running)
        self.assertIn("s9 stage 90 reward caps=100 fusion_cells=50 credits=0 caps_form_ok=true cells_form_ok=true", mh.logs)
        self.assertIn("s9 stage 150 diamond_city addtomap=true mq103_stage=0 minrecruit00_stage=0", mh.logs)

        # S9 museum exit + P9 SetLinkedRef chain + keeper/mission PlacePreston release (P1 #1)
        self.assertTrue(mh.ns["BeginS9MuseumExitAndPatrol"](mh.player))
        self.assertIn("min01 museum_exit moveto_front=true", mh.logs)
        self.assertAlmostEqual(mh.preston.x, -2010.57, places=2)
        self.assertAlmostEqual(mh.preston.y, -1697.94, places=2)
        self.assertAlmostEqual(mh.preston.z, 89.26, places=2)
        self.assertFalse(mh.preston.restrained)
        self.assertTrue(mh.ns["prestonFollow"])
        self.assertTrue(mh.ns["s9PatrolRelease"])
        self.assertFalse(mh.ns["s4BalconyActive"])
        self.assertEqual(mh.keeper.calls[-1], (False, True))
        # Calling PlacePreston 1 s later must NOT re-restrain or yank Preston back to street door
        mh.preston.SetPosition(-2061.23, -1657.46, 86.93)
        self.assertFalse(mh.ns["PlacePreston"](mh.player, "mission"))
        self.assertFalse(mh.preston.restrained)
        self.assertAlmostEqual(mh.preston.x, -2061.23, places=2)
        self.assertIs(mh.preston.linked_ref, mh.waypoints[0])
        self.assertGreaterEqual(mh.preston.eval_calls, 1)
        for i in range(len(mh.waypoints) - 1):
            self.assertIs(mh.waypoints[i].linked_ref, mh.waypoints[i + 1])
        self.assertIsNone(mh.waypoints[-1].linked_ref)
        for m in mh.group:
            self.assertIs(m.linked_ref, mh.waypoints[0])

        # Normal P9 patrol walk arrival in Sanctuary + Sturges OnSturgesArrivedFromConcord (P1 #3)
        mh.preston.SetPosition(-2356.32, -1470.44, 109.14)
        self.assertTrue(mh.ns["CheckS9SanctuaryArrival"](mh.player, 1.0))
        self.assertIn("min01 group_arrived sanctuary=true via=p9_patrol_walk", mh.logs)
        self.assertIn("sanctuary01 stage 1000 obj=1000 hard_stop=true", mh.logs)
        self.assertTrue(mh.state["completed"])
        self.assertTrue(mh.sanctuary.running)
        self.assertEqual(mh.sanctuary.sturges_arrived, 1)
        self.assertEqual(mh.sanctuary.advance_calls, [(1000, "s9_arrival")])
        self.assertEqual(mh.sanctuary.stage, 1000)
        self.assertIn(1000, mh.sanctuary.objectives_displayed)
        self.assertEqual(mh.mq103.stage, 0)
        self.assertEqual(mh.minrecruit00.stage, 0)

    def test_s9_unmerged_waypoints_dc_marker_relocation_and_midpatrol_reload(self):
        """P1 #1(c) + #2: Base-world 0xB82..0xB8A markers relocate into player's merged exterior before SetLinkedRef/AddToMap, and reload resumes patrol."""
        mh = _build_min00_harness(enable_s4=True, enable_s6_s9=True, unmerged_markers=True)
        # Lobby talk indoors first: enables 0xB8A, defers merged-world MoveTo until exterior exit
        mh.player.interior = True
        self.assertTrue(mh.ns["CompleteS9LobbyTalkAndReward"](mh.player))
        self.assertTrue(mh.dc_marker.enabled)
        self.assertTrue(mh.dc_marker.unmerged_world)
        self.assertEqual(mh.dc_marker.added_to_map, [False])

        # Player exits to exterior -> BeginS9MuseumExitAndPatrol relocates 0xB8A AND all 8 0xB82..0xB89 waypoints into merged world
        mh.player.interior = False
        self.assertTrue(mh.ns["BeginS9MuseumExitAndPatrol"](mh.player))
        self.assertFalse(mh.dc_marker.unmerged_world)
        self.assertEqual(len(mh.dc_marker.moveto_calls), 1)
        self.assertEqual(mh.dc_marker.added_to_map, [False, False])
        for wp in mh.waypoints:
            self.assertFalse(wp.unmerged_world)
            self.assertEqual(len(wp.moveto_calls), 1)
        self.assertFalse(mh.preston.restrained)

        # Mid-patrol save reload: re-applies SetRestrained(False), SetLinkedRef, EvaluatePackage, keeper sync
        mh.preston.restrained = True
        mh.ns["prestonTalkReloaded"] = True
        evals_before = mh.preston.eval_calls
        self.assertTrue(mh.ns["ResumeS9PatrolAfterLoad"](mh.player))
        self.assertFalse(mh.preston.restrained)
        self.assertFalse(mh.ns["prestonTalkReloaded"])
        self.assertGreater(mh.preston.eval_calls, evals_before)
        self.assertEqual(mh.keeper.calls[-1], (False, True))
        self.assertIn("min01 patrol resumed_after_load", mh.logs)

    def test_s9_unloaded_failsafe_elapsed_180s_and_player_ahead_150m(self):
        # Branch 1: elapsed >= 180 s while Preston still on road
        mh1 = _build_min00_harness(enable_s4=True, enable_s6_s9=True)
        self.assertTrue(mh1.ns["CompleteS9LobbyTalkAndReward"](mh1.player))
        self.assertTrue(mh1.ns["BeginS9MuseumExitAndPatrol"](mh1.player))
        self.assertFalse(mh1.ns["CheckS9SanctuaryArrival"](mh1.player, 179.0))
        self.assertFalse(mh1.ns["s9GroupArrived"])
        self.assertTrue(mh1.ns["CheckS9SanctuaryArrival"](mh1.player, 1.0))
        self.assertIn("min01 group_arrived sanctuary=true via=unloaded_failsafe", mh1.logs)
        self.assertAlmostEqual(mh1.preston.x, -2356.32, places=2)
        self.assertEqual(mh1.sanctuary.stage, 1000)
        self.assertIn(1000, mh1.sanctuary.objectives_displayed)

        # Branch 2: player already in Sanctuary > 150 m ahead of group at t = 10 s
        mh2 = _build_min00_harness(enable_s4=True, enable_s6_s9=True)
        self.assertTrue(mh2.ns["CompleteS9LobbyTalkAndReward"](mh2.player))
        self.assertTrue(mh2.ns["BeginS9MuseumExitAndPatrol"](mh2.player))
        mh2.player.SetPosition(-2350.0, -1465.0, 109.0)
        self.assertTrue(mh2.ns["CheckS9SanctuaryArrival"](mh2.player, 10.0))
        self.assertIn("min01 group_arrived sanctuary=true via=unloaded_failsafe", mh2.logs)
        self.assertAlmostEqual(mh2.preston.x, -2356.32, places=2)
        self.assertEqual(mh2.sanctuary.stage, 1000)
        self.assertEqual(mh2.mq103.stage, 0)
        self.assertEqual(mh2.minrecruit00.stage, 0)


@unittest.skipUnless(os.environ.get("FO4SF_DOTNET_TESTS") == "1", "Set FO4SF_DOTNET_TESTS=1 to run Mission binary ESM selftest")
class TestR11Step3qBinaryEsm(unittest.TestCase):
    """Binary ESM verification of both --r11-full-mission 0 (default) and --r11-full-mission 1."""

    def test_selftest_binary_default_off_and_full_on(self):
        from fo4sf.planet.esm import Plugin

        with tempfile.TemporaryDirectory(prefix="r11_3q_esm_") as tmpdir:
            env = dict(os.environ)
            env.setdefault("DOTNET_ROLL_FORWARD", "Major")
            proc = subprocess.run(
                ["dotnet", "run", "-c", "Release", "--project", str(REPO_ROOT / "dotnet" / "Mission" / "Mission.csproj"), "--", "selftest", tmpdir],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=f"Mission selftest failed:\n{proc.stdout}\n{proc.stderr}")
            self.assertIn("selftest pass", proc.stdout)

            default_esm = Path(tmpdir) / "out" / "alias" / "FO4SFMission.esm"
            full_esm = Path(tmpdir) / "out" / "r11_full_mission" / "FO4SFMission.esm"
            self.assertTrue(default_esm.is_file())
            self.assertTrue(full_esm.is_file())

            def scan_records(esm_path: Path):
                refrs: dict[int, tuple[str, int, int, tuple[float, float, float], list[int], str]] = {}
                globs: dict[int, tuple[str, float]] = {}
                with Plugin(str(esm_path)) as plg:
                    self_idx = plg.self_index
                    for grp in plg.groups:
                        for start, end in plg.groups[grp]:
                            for item in plg.walk(start, end):
                                if item[0] != "REC":
                                    continue
                                rec = plg.record_at(item[1])
                                if ((rec.formid >> 24) & 0xFF) != self_idx:
                                    continue
                                local_id = rec.formid & 0xFFFFFF
                                if rec.sig == b"REFR":
                                    data = rec.get(b"DATA")
                                    pos = struct.unpack_from("<fff", data, 0) if data and len(data) >= 12 else (0.0, 0.0, 0.0)
                                    name_sub = rec.get(b"NAME")
                                    base_fid = struct.unpack_from("<I", name_sub, 0)[0] if name_sub and len(name_sub) >= 4 else 0
                                    full_sub = rec.get(b"FULL")
                                    full_txt = full_sub.rstrip(b"\x00").decode("utf-8", "replace") if full_sub else ""
                                    xlkr_targets = []
                                    for xlkr in rec.all(b"XLKR"):
                                        if len(xlkr) >= 8:
                                            _kw, ref_fid = struct.unpack_from("<II", xlkr, 0)
                                            xlkr_targets.append(ref_fid & 0xFFFFFF)
                                    refrs[local_id] = (rec.edid, rec.flags, base_fid, pos, xlkr_targets, full_txt)
                                elif rec.sig == b"GLOB":
                                    fltv = rec.get(b"FLTV")
                                    val = struct.unpack_from("<f", fltv, 0)[0] if fltv and len(fltv) >= 4 else 0.0
                                    globs[local_id] = (rec.edid, val)
                return refrs, globs

            # Default --r11-full-mission 0: ZERO 0xB80..0xB8A markers and ZERO 0xB8B GLOB
            default_refrs, default_globs = scan_records(default_esm)
            for mid in range(0xB80, 0xB8B):
                self.assertNotIn(mid, default_refrs)
            self.assertNotIn(0xB8B, default_globs)

            # Full --r11-full-mission 1: all 11 markers 0xB80..0xB8A + GLOB 0xB8B present
            full_refrs, full_globs = scan_records(full_esm)
            for mid in range(0xB80, 0xB8B):
                self.assertIn(mid, full_refrs)
            self.assertEqual(full_refrs[0xB80][0], "FO4SF_S4_PrestonBalconyMarker")
            self.assertAlmostEqual(full_refrs[0xB80][3][2], 98.51, places=2)
            self.assertEqual(full_refrs[0xB81][0], "FO4SF_S9_MuseumExitMarker")
            self.assertAlmostEqual(full_refrs[0xB81][3][2], 89.26, places=2)
            for idx in range(8):
                mid = 0xB82 + idx
                edid, _flags, _base, pos, xlkrs, _full = full_refrs[mid]
                self.assertEqual(edid, f"FO4SF_S9_PatrolWP_{idx}")
                self.assertLessEqual(pos[0], -2060.0)
                if idx < 7:
                    self.assertEqual(xlkrs, [mid + 1])
                else:
                    self.assertEqual(xlkrs, [])
            # Real Diamond City MapMarker 0xB8A (InitiallyDisabled 0x800 | Persistent 0x400, Base STAT 0x000010, FULL "Diamond City")
            dc_edid, dc_flags, dc_base, dc_pos, _dc_xlkr, dc_full = full_refrs[0xB8A]
            self.assertEqual(dc_edid, "FO4SF_DiamondCityMapMarker")
            self.assertEqual(dc_flags & 0xC00, 0xC00)
            self.assertEqual(dc_base, 0x000010)
            self.assertAlmostEqual(dc_pos[0], -1416.36, places=2)
            self.assertAlmostEqual(dc_pos[1], -3129.39, places=2)
            self.assertEqual(dc_full, "Diamond City")
            self.assertIn(0xB8B, full_globs)
            self.assertEqual(full_globs[0xB8B][0], "FO4SF_R11FullMission")
            self.assertAlmostEqual(full_globs[0xB8B][1], 1.0, places=5)

            # R12 S2-S6 records (0xB8C..0xBDC) + --fo4-human-anims OFF default vs ON verification
            anims_esm = Path(tmpdir) / "out" / "r11_full_mission_anims" / "FO4SFMission.esm"
            self.assertTrue(anims_esm.is_file())
            _, full_anims_globs = scan_records(anims_esm)
            self.assertAlmostEqual(full_globs[0xB8E][1], 0.0, places=5)
            self.assertAlmostEqual(full_anims_globs[0xB8E][1], 1.0, places=5)
            with Plugin(str(full_esm)) as pf, Plugin(str(anims_esm)) as pa:
                def collect_sigs(plg, only_group=None):
                    out = {}
                    sidx = plg.self_index
                    for grp in plg.groups:
                        grp_name = grp.decode("ascii", "ignore") if isinstance(grp, bytes) else str(grp)
                        if only_group and grp_name != only_group:
                            continue
                        for st, en in plg.groups[grp]:
                            for item in plg.walk(st, en):
                                if item[0] == "REC":
                                    r = plg.record_at(item[1])
                                    if ((r.formid >> 24) & 0xFF) == sidx:
                                        out[r.formid & 0xFFFFFF] = (r.sig.decode("ascii"), r.edid)
                    return out
                sf_recs = collect_sigs(pf)
                sf_cell_recs = collect_sigs(pf, "CELL")
                sf_wrld_recs = collect_sigs(pf, "WRLD")
                sa_recs = collect_sigs(pa)
            self.assertEqual(sf_recs[0xB60], ("CELL", "FO4SF_MissionHoldingCell"))
            self.assertEqual(sf_wrld_recs, {})
            for ext_id in (0xB80, 0xB81, 0xB82, 0xB83, 0xB84, 0xB85, 0xB86, 0xB87, 0xB88, 0xB89, 0xB8A, 0xB98, 0xB99, 0xBA1, 0xBA2, 0xBA3, 0xBA4, 0xBA5, 0xBA6, 0xBA8, 0xBAA, 0xBAB, 0xBAC):
                self.assertIn(ext_id, sf_cell_recs)
                self.assertNotIn(ext_id, sf_wrld_recs)
            self.assertEqual(sf_recs[0xB90], ("QUST", "FO4SF_Vault111Roaches"))
            self.assertEqual(sf_recs[0xB96], ("PACK", "FO4SF_S3_PackHouse01"))
            self.assertEqual(sf_recs[0xB97], ("PACK", "FO4SF_S3_PackHouse02"))
            self.assertEqual(sf_recs[0xB9A], ("SCEN", "FO4SF_S3_Stage50Scene"))
            self.assertEqual(sf_recs[0xBC9], ("SCEN", "FO4SF_S6_PrestonRoomScene"))
            self.assertEqual(sf_recs[0xBD0], ("SCEN", "FO4SF_S6_SturgesRoomScene"))
            self.assertNotIn(0xBDC, sf_recs)
            # M3: --fo4-human-anims links FO4SFHumanAnims.esm (0x01000800) without creating local 0xBDC
            import build_fo4port_r11_museum as ext  # local pure-Python ESM reader
            from fo4sf import beginning_pilot as bp

            self.assertNotIn(0xBDC, sa_recs)
            self.assertNotIn(0xBDC, sf_recs)
            anims_raw = anims_esm.read_bytes()
            anims_tes4, _ = ext.parse_top_level(anims_raw)
            anims_masters = [
                sp.rstrip(b"\x00").decode("ascii")
                for ss, sp in ext.iter_subrecords(anims_tes4.decompressed_body())
                if ss == b"MAST"
            ]
            self.assertIn("FO4SFHumanAnims.esm", anims_masters)
            fo4_anim_kw_fids = {
                r.fid & 0xFFF
                for r in ext.walk_all_records(anims_raw)
                if r.sig == b"NPC_"
                for ss, sp in ext.iter_subrecords(r.decompressed_body())
                if ss == b"KWDA" and 0x01000800 in [struct.unpack_from("<I", sp, i)[0] for i in range(0, len(sp), 4)]
            }
            self.assertEqual(fo4_anim_kw_fids, {0x801, 0x986, 0xA00, 0xBC3, 0xBC5, 0xBC7})

            # B1 + LoadDoorQuest + L3 + H2 + M2 checks on full_esm and creatures ESM
            bad_actis, placed_nifs = bp.find_bad_placed_activators(full_esm)
            self.assertEqual(bad_actis, [])
            self.assertIn("fo4sf\\powerarmor\\fusioncore.nif", placed_nifs)
            self.assertIn("fo4port\\setdressing\\doors\\paintedwooddoordoubleload01.nif", placed_nifs)
            self.assertIn("fo4port\\interiors\\building\\woodp\\doors\\bldwoodpdoorload01.nif", placed_nifs)
            self.assertIn("fo4port\\furniture\\terminals\\terminalwall01.nif", placed_nifs)

            self.assertEqual(sf_recs[0xBDE], ("QUST", "FO4SF_LoadDoor"))
            self.assertEqual(sf_recs[0xBE1], ("PACK", "FO4SF_S5_MuseumRaiderPursuePack"))
            self.assertEqual(sf_recs[0xBE4], ("ARMO", "FO4SF_S6_SettlerClothes_StandIn"))
            self.assertEqual(sf_recs[0xBE5], ("OTFT", "FO4SF_S6_SettlerOutfit_StandIn"))
            self.assertNotIn(0xBE2, sf_recs)
            self.assertNotIn(0xBE3, sf_recs)

            full_raw = full_esm.read_bytes()
            full_globs = {
                r.fid & 0xFFF: struct.unpack("<f", next(sp for ss, sp in ext.iter_subrecords(r.decompressed_body()) if ss == b"FLTV"))[0]
                for r in ext.walk_all_records(full_raw)
                if r.sig == b"GLOB"
            }
            self.assertEqual(full_globs[0xB8C], 0.0)
            self.assertEqual(full_globs[0xB8E], 0.0)

            cre_esm = Path(tmpdir) / "out" / "r11_full_mission_creatures" / "FO4SFMission.esm"
            cre_raw = cre_esm.read_bytes()
            cre_tes4, _ = ext.parse_top_level(cre_raw)
            cre_masters = [
                sp.rstrip(b"\x00").decode("ascii")
                for ss, sp in ext.iter_subrecords(cre_tes4.decompressed_body())
                if ss == b"MAST"
            ]
            self.assertIn("FO4SFCreatures.esm", cre_masters)
            cre_sigs = {r.fid & 0xFFF: r.sig.decode() for r in ext.walk_all_records(cre_raw) if r.sig != b"TES4"}
            self.assertEqual(cre_sigs[0xBE2], "NPC_")
            self.assertEqual(cre_sigs[0xBE3], "NPC_")


def _build_vault_roaches_harness(
    task1b_ready: bool = True,
    creature_slot_ready: bool = False,
    ng_stage: int = 20,
    in_cryo: bool = True,
):
    psc = ROACHES_PSC.read_text(encoding="utf-8")
    logs: list[str] = []
    stages: list[int] = []
    obj_disp: list[int] = []
    obj_done: list[int] = []
    state = {"stage": 0, "completed": False}
    cryo_cell = SimpleNamespace(name="FO4Port_Vault111Cryo")
    player = _FakeActor("Player", -40.0, 14.0, 0.0, interior=in_cryo)
    player.GetParentCell = lambda: cryo_cell if in_cryo else "OtherCell"
    vault_anchor = _FakeMarker("FO4Port_VaultAnchor", 1.531505, -7.385632, -0.738497)
    roach_markers = [_FakeMarker(f"FO4SF_S2_RadroachMarker_{i}", 0.0, 0.0, 0.0) for i in range(5)]
    roach_base = SimpleNamespace(name="FO4SF_RA5RadroachTest")
    slot_glob = SimpleNamespace(GetValue=lambda: 1.0 if creature_slot_ready else 0.0)
    t1b_glob = SimpleNamespace(GetValue=lambda: 1.0 if task1b_ready else 0.0)
    ng_quest = SimpleNamespace(GetStage=lambda: ng_stage)

    def get_form(fid: int, plugin: str):
        if plugin == "FO4SFNewGame.esm" and fid == 0x000800:
            return ng_quest
        if plugin == "FO4Port.esm":
            if fid == 0x0011F3:
                return cryo_cell
            if fid == 0x001338:
                return vault_anchor
        if plugin == "FO4SF_RA5Creatures.esm" and fid == 0x000804 and creature_slot_ready:
            return roach_base
        return None

    def set_stage(st: int) -> None:
        state["stage"] = int(st)
        stages.append(int(st))

    svars = {
        "roachX", "roachY", "roachZ", "roachStageReq", "spawnedRoaches", "wavePlaced",
        "markerSynced", "blockedLogged", "emptyLogged", "completed", "deadCount",
    }
    ns = {
        "RadroachMarkers": roach_markers,
        "CreatureSlotReadyGlob": slot_glob,
        "Task1bRecoveryReadyGlob": t1b_glob,
        "RequireTask1bVaultRecovery": True,
        "RequirePlayerInCryoCell": True,
        "NewGamePlugin": "FO4SFNewGame.esm",
        "NewGameQuestId": 0x000800,
        "PortPlugin": "FO4Port.esm",
        "VaultCryoCellId": 0x0011F3,
        "VaultAnchorId": 0x001338,
        "CoreValuesPlugin": "FO4SFCoreValues.esm",
        "GameModeGlobId": 0x000870,
        "CreaturePlugin": "FO4SF_RA5Creatures.esm",
        "CreatureRadroachNpcId": 0x000804,
        "VaultAnchorX": 1.531505,
        "VaultAnchorY": -7.385632,
        "VaultAnchorZ": -0.738497,
        "TriggerRadius": 12.0,
        "roachX": None,
        "roachY": None,
        "roachZ": None,
        "roachStageReq": None,
        "spawnedRoaches": None,
        "wavePlaced": None,
        "markerSynced": None,
        "blockedLogged": False,
        "emptyLogged": False,
        "completed": False,
        "deadCount": 0,
        "GetStage": lambda: state["stage"],
        "SetStage": set_stage,
        "SetObjectiveDisplayed": lambda idx, *_a: obj_disp.append(int(idx)),
        "SetObjectiveCompleted": lambda idx, *_a: obj_done.append(int(idx)),
        "CompleteQuest": lambda: state.__setitem__("completed", True),
        "Trace": lambda msg: logs.append(str(msg)),
        "Game": SimpleNamespace(GetFormFromFile=get_form, GetPlayer=lambda: player),
    }
    _compile_papyrus(
        psc,
        ["InitArrays", "IsWarfareMode", "IsTask1bRecoveryReady", "IsPlayerInCryoCell", "EvaluateVaultRoaches"],
        svars,
        ns,
    )
    return SimpleNamespace(ns=ns, logs=logs, stages=stages, obj_disp=obj_disp, obj_done=obj_done, state=state, player=player, markers=roach_markers)


class TestR12S2S3S5S6Missions(unittest.TestCase):
    """R12 Task 1d-1h unit tests for S2 Vault Roaches, S3 empty-slot & scene, S5 Museum, S6 Room & Core stop."""

    def test_s2_vault_roaches_gates_on_task1b_and_supports_empty_slot_or_5_spawns(self):
        # Task 1b gate OFF -> blocked cleanly without spawning or advancing
        h_blk = _build_vault_roaches_harness(task1b_ready=False, creature_slot_ready=True)
        self.assertFalse(h_blk.ns["EvaluateVaultRoaches"]())
        self.assertEqual(h_blk.stages, [])
        self.assertIn("s2 vault_roaches gated reason=task1b_vault_death_recovery_not_ready", h_blk.logs)

        # creature_slot=empty fallback: marks empty-slot stage progression -> completes cleanly at 100
        h_emp = _build_vault_roaches_harness(task1b_ready=True, creature_slot_ready=False)
        self.assertTrue(h_emp.ns["EvaluateVaultRoaches"]())
        self.assertTrue(h_emp.state["completed"])
        self.assertIn(100, h_emp.stages)
        self.assertIn("s2 vault_roaches creature_slot=empty fallback=stage_gate", h_emp.logs)

        # creature_slot=ready: spawns 5 radroaches across stages/proximity, completes on 5/5 deaths
        h_rdy = _build_vault_roaches_harness(task1b_ready=True, creature_slot_ready=True)
        self.assertTrue(h_rdy.ns["EvaluateVaultRoaches"]())
        self.assertFalse(h_rdy.state["completed"])
        for mk in h_rdy.markers:
            self.assertEqual(len(mk.spawned_actors), 1)
            mk.spawned_actors[0].dead = True
        self.assertTrue(h_rdy.ns["EvaluateVaultRoaches"]())
        self.assertTrue(h_rdy.state["completed"])
        self.assertIn("s2 vault_roaches complete dead=5/5 stage=100", h_rdy.logs)

    def test_h1_min00_stage_40_does_not_complete_200_when_full_mission_enabled(self):
        psc = MIN00_PSC.read_text(encoding="utf-8")
        # Full-mission mode (EnableS6ToS9Full=True): stage 40 stays open for basement gate & fusion core
        mh_full = _build_min00_harness(enable_s4=True, enable_s6_s9=True)
        _compile_papyrus(
            psc,
            ["EffectiveStage", "OnStageSet"],
            {"applied", "prestonUsedFallback", "talkActivated", "pendingStage", "pendingStageBy"},
            mh_full.ns,
        )
        mh_full.ns["SetStage"](40)
        mh_full.ns["OnStageSet"](40, 0)
        self.assertFalse(mh_full.state["completed"])
        self.assertNotIn(200, mh_full.stages)

        # Standalone 2g-fix mode (EnableS6ToS9Full=False): stage 40 completes Min00 at 200
        mh_2g = _build_min00_harness(enable_s4=False, enable_s6_s9=False)
        _compile_papyrus(
            psc,
            ["EffectiveStage", "OnStageSet"],
            {"applied", "prestonUsedFallback", "talkActivated", "pendingStage", "pendingStageBy"},
            mh_2g.ns,
        )
        mh_2g.ns["SetStage"](40)
        mh_2g.ns["OnStageSet"](40, 0)
        self.assertTrue(mh_2g.state["completed"])
        self.assertIn(200, mh_2g.stages)

    def test_m7_codsworth_only_s3_house_arrival_and_dist_log(self):
        # Player standing at House 1 while Codsworth is > 10 m away MUST NOT clear House 1
        cods = _FakeActor("Codsworth", -2360.0, -1420.0, 112.0)
        player = _FakeActor("Player", -2313.44, -1372.02, 112.66)
        ch = _build_codsworth_harness(
            enable_s3=True, r11_glob_val=1.0, codsworth_actor=cods, player_actor=player,
            creature_slot_ready=False,
        )
        ch.ns["applied"] = 30
        ch.ns["UpdateS3HouseSearchProgress"]()
        self.assertFalse(ch.ns["s3House1Cleared"])
        self.assertEqual(ch.stages, [30, 32])

        # Once Codsworth arrives within 10 m of House 1, clears House 1 & logs codsworth_dist=
        cods.SetPosition(-2313.0, -1372.5, 112.66)
        ch.ns["UpdateS3HouseSearchProgress"]()
        self.assertTrue(ch.ns["s3House1Cleared"])
        self.assertEqual(ch.stages, [30, 32, 34, 36, 38])
        self.assertTrue(any("codsworth01 s3 creature_slot=empty arrival house=1 codsworth_dist=" in l for l in ch.logs))

    def test_s5_museum_raider_reengages_combat_and_calls_path_to_reference(self):
        museum_cell = SimpleNamespace(name="FO4Port_ConcordMuseum01")
        anchor = _FakeMarker("FO4Port_MuseumAnchorRef", 8.228572, 0.000002, -0.914286)
        raiders = [_FakeActor(f"MR_{i}") for i in range(3)]
        mh = _build_min00_harness(
            enable_s4=True, enable_s6_s9=True,
            museum_anchor=anchor, museum_cell=museum_cell, museum_raiders=raiders,
        )
        mh.player.interior = True
        mh.player.GetParentCell = lambda: museum_cell
        mh.ns["UpdateS5MuseumEncounter"](mh.player)
        for r in raiders:
            self.assertGreaterEqual(r.eval_calls, 1)
            self.assertTrue(any(fn == "StartCombat" and args[0] is mh.player for fn, args in r.async_calls))
            self.assertTrue(any(fn == "PathToReference" and args[0] is mh.player for fn, args in r.async_calls))

    def test_b1_find_bad_placed_activators_rejects_marker_and_empty_modl(self):
        import build_fo4port_r11_museum as ext
        from fo4sf import beginning_pilot as bp

        with tempfile.TemporaryDirectory() as td:
            tes4 = ext.RawRecord(
                b"TES4", 1, 0, 0, 576, 0,
                ext.pack_subrecords([(b"HEDR", struct.pack("<fII", 0.96, 1, 0x802)), (b"MAST", b"Starfield.esm\x00"), (b"DATA", b"\x00" * 8)]),
            )
            bad_acti = ext.RawRecord(
                b"ACTI", 0, 0x01000800, 0, 576, 0,
                ext.pack_subrecords([(b"EDID", b"BadMarkerActi\x00"), (b"OBND", b"\x00" * 24), (b"MODL", b"Effects\\DecoratorMarker.nif\x00")]),
            )
            bad_ref = ext.RawRecord(
                b"REFR", 0, 0x01000801, 0, 576, 0,
                ext.pack_subrecords([(b"NAME", struct.pack("<I", 0x01000800)), (b"DATA", struct.pack("<6f", 0, 0, 0, 0, 0, 0))]),
            )
            bad_cell = ext.RawRecord(b"CELL", 0, 0x01000802, 0, 576, 0, ext.pack_subrecords([(b"EDID", b"TestCell\x00")]))
            esm_path = Path(td) / "BadActi.esm"
            esm_path.write_bytes(
                tes4.to_bytes()
                + ext.TopGrup(b"ACTI", 0, 0, 0, bad_acti.to_bytes()).to_bytes()
                + ext.TopGrup(b"CELL", 0, 0, 0, ext.wrap_cell_entry(bad_cell, [bad_ref], [])).to_bytes()
            )
            bad, _ = bp.find_bad_placed_activators(esm_path)
            self.assertTrue(any("DecoratorMarker" in err for err in bad))

    def test_s3_empty_slot_arrival_and_stage50_scene_f1_fallback(self):
        cods = _FakeActor("Codsworth", -2313.44, -1372.02, 112.66)
        playing = {"flag": False, "starts": 0, "stops": 0}
        on_end_hooks = []

        def _stop():
            playing["flag"] = False
            playing["stops"] += 1
            for cb in on_end_hooks:
                cb()

        def _start():
            playing["starts"] += 1
            playing["flag"] = True

        scn50 = SimpleNamespace(
            IsPlaying=lambda: playing["flag"],
            Start=_start,
            ForceStart=_start,
            Stop=_stop,
        )
        player = _FakeActor("Player", -2329.0, -1420.0, 112.0, interior=True)
        ch = _build_codsworth_harness(
            enable_s3=True, r11_glob_val=1.0, codsworth_actor=cods, player_actor=player,
            creature_slot_ready=False, stage50_scene=scn50,
        )
        on_end_hooks.append(lambda: ch.ns["Scene_OnEnd"](scn50))
        # Prove exterior S3 marker relocation resolves host Commonwealth worldspace even while player is indoors.
        ch.h1_marker.x, ch.h1_marker.y, ch.h1_marker.z = 0.0, 0.0, 0.0
        ch.h1_marker.enabled = False
        ch.ns["applied"] = 30
        ch.ns["UpdateS3HouseSearchProgress"]()
        self.assertTrue(ch.h1_marker.enabled)
        self.assertAlmostEqual(ch.h1_marker.x, -2313.44, places=2)
        self.assertTrue(ch.ns["s3House1Cleared"])
        self.assertIn("codsworth01 s3 creature_slot=empty fallback=arrival_advance", ch.logs)
        # Move Codsworth to House 02 -> House 02 clears -> stage 50 scene requested (F1 retry path)
        cods.SetPosition(-2296.17, -1424.97, 111.77)
        ch.ns["UpdateS3HouseSearchProgress"]()
        self.assertTrue(ch.ns["s3House2Cleared"])
        self.assertEqual(ch.stages, [30, 32, 34, 36, 38, 40, 50])
        self.assertFalse(ch.state["completed"])
        self.assertEqual(playing["starts"], 1)
        # Async-queued Scene.OnEnd + full SceneOpenCheckSeconds sub-window guard:
        # 1. Early sub-window Scene.OnEnd (< 1.45s) holds without immediate retry; 16 ticks before window holds; >= 1.5s retries.
        # 2. Stop() queues async OnEnd delivered *after* RestartOrCompleteS3Stage50Scene returns and is consumed cleanly.
        async_scn50_queue = []

        def _async_stop():
            playing["flag"] = False
            playing["stops"] += 1
            async_scn50_queue.append(lambda: ch.ns["Scene_OnEnd"](scn50))

        scn50.Stop = _async_stop
        # Early sub-window Scene.OnEnd does not increment retries
        ch.clock["rt"] += 0.4
        playing["flag"] = False
        ch.ns["Scene_OnEnd"](scn50)
        self.assertEqual(ch.ns["s3Stage50Retries"], 0)
        self.assertTrue(ch.ns["s3Stage50Pending"])
        # Advance across full 1.5 s window -> triggers retries cleanly with async Stop() OnEnd flushed AFTER return
        playing["flag"] = True
        for i in range(3):
            ch.ns["Scene_OnPhaseBegin"](scn50, 1)
            ch.clock["rt"] += 1.6
            ch.ns["CheckS3Stage50SceneOpen"]()
            self.assertEqual(ch.ns["s3Stage50Retries"], i + 1)
            self.assertTrue(ch.ns["s3Stage50Restarting"])
            while async_scn50_queue:
                async_scn50_queue.pop(0)()
            self.assertFalse(ch.ns["s3Stage50Restarting"])
            self.assertTrue(ch.ns["s3Stage50Pending"])
        self.assertEqual(ch.ns["s3Stage50Retries"], 3)
        self.assertEqual(playing["starts"], 4)
        self.assertEqual(playing["stops"], 3)
        self.assertFalse(ch.state["completed"])
        # 4th timeout exhausts retries: stops scene, flushes async OnEnd cleanly, leaves Codsworth talkable, logs ERROR (never skips stage 100!)
        ch.ns["Scene_OnPhaseBegin"](scn50, 1)
        ch.clock["rt"] += 1.6
        ch.ns["CheckS3Stage50SceneOpen"]()
        while async_scn50_queue:
            async_scn50_queue.pop(0)()
        self.assertFalse(ch.ns["s3Stage50Restarting"])
        self.assertFalse(playing["flag"])
        self.assertFalse(ch.ns["s3Stage50Pending"])
        self.assertTrue(cods.talkable)
        self.assertFalse(ch.state["completed"])
        self.assertNotIn(100, ch.stages)
        self.assertEqual(ch.min00.codsworth_given, 0)
        self.assertIn(
            "codsworth01 s3_stage50 ERROR scene_failed retries=3/3 reason=dialogue_menu_timeout actor_talkable=true",
            ch.logs,
        )

        # Explicitly enabled MessageBox fallback (TalkUseMessageBox=1) completes Stage 100 + hands off to Min00.
        cods_mb = _FakeActor("Codsworth", -2313.44, -1372.02, 112.66)
        ch_mb = _build_codsworth_harness(
            enable_s3=True, r11_glob_val=1.0, codsworth_actor=cods_mb,
            creature_slot_ready=False, stage50_scene=scn50, msg_buttons=[0],
        )
        ch_mb.ns["applied"] = 30
        ch_mb.ns["UpdateS3HouseSearchProgress"]()
        cods_mb.SetPosition(-2296.17, -1424.97, 111.77)
        ch_mb.ns["UpdateS3HouseSearchProgress"]()
        self.assertIn(100, ch_mb.stages)
        self.assertTrue(ch_mb.state["completed"])
        self.assertEqual(ch_mb.min00.codsworth_given, 1)

    def test_s5_7_museum_raiders_medkit_unlock_preston_door_and_s6_fusion_core_stop(self):
        museum_cell = SimpleNamespace(name="FO4Port_ConcordMuseum01")
        anchor = _FakeMarker("FO4Port_MuseumAnchorRef", 8.228572, 0.000002, -0.914286)
        raiders = [_FakeActor(f"MR_{i}") for i in range(7)]
        doors = [_FakeMarker(f"Door_{i}", 0.0, 0.0, 0.0) for i in range(4)]
        loot = [_FakeMarker(f"Loot_{i}", 0.0, 0.0, 0.0) for i in range(7)]
        preston_door = _FakeMarker("FO4Port_PrestonDoorREF", 0.0, 0.0, 0.0)
        preston_exit_door = _FakeMarker("FO4Port_PrestonExitDoor", 0.0, 0.0, 0.0)
        basement_gate = _FakeMarker("FO4Port_MQ03SecurityGateREF", 0.0, 0.0, 0.0)
        basement_gate.locked = True
        basement_term = _FakeMarker("FO4Port_TerminalREF", 0.0, 0.0, 0.0)
        basement_term.locked = True
        medkit = _FakeMarker("FO4Port_MedkitREF", 0.0, 0.0, 0.0)
        s4_musket = _FakeMarker("FO4SF_S4_DisplayMusketRef", 0.0, 0.0, 0.0)
        s4_cells = [_FakeMarker(f"FO4SF_S4_FusionCell_{i}", 0.0, 0.0, 0.0) for i in range(3)]
        sturges_playing = {"flag": False, "starts": 0, "stops": 0}
        on_end_hooks = []

        def _s_stop():
            sturges_playing["flag"] = False
            sturges_playing["stops"] += 1
            for cb in on_end_hooks:
                cb()

        def _s_start():
            sturges_playing["starts"] += 1
            sturges_playing["flag"] = True

        s6_sturges_scn = SimpleNamespace(
            IsPlaying=lambda: sturges_playing["flag"],
            Start=_s_start,
            ForceStart=_s_start,
            Stop=_s_stop,
        )
        mh = _build_min00_harness(
            enable_s4=True, enable_s6_s9=True, stimpak_id=0x000851, bobby_pin_id=0x0008A5,
            comp_musket_id=0x00089E, comp_ammo_id=0x00089C, stop_at_core=True,
            museum_anchor=anchor, museum_cell=museum_cell, museum_raiders=raiders,
            museum_doors=doors, museum_loot=loot, preston_door=preston_door,
            preston_exit_door=preston_exit_door, basement_gate=basement_gate,
            basement_term=basement_term, medkit_ref=medkit,
            s4_display_musket_ref=s4_musket, s4_fusion_cell_refs=s4_cells,
            s6_sturges_scene=s6_sturges_scn,
        )
        on_end_hooks.append(lambda: mh.ns["Scene_OnEnd"](s6_sturges_scn))
        # S4 balcony arms Preston w/ FO4_CompPrestonLaserMusket & relocates display pickups via 0x005C50 even when player is indoors
        mh.player.interior = True
        mh.ns["SetupS4BalconyEncounter"](mh.player)
        self.assertEqual(mh.preston.items.get("FO4_CompPrestonLaserMusket"), 1)
        self.assertTrue(s4_musket.enabled)
        self.assertAlmostEqual(s4_musket.x, -2015.41, places=2)
        self.assertTrue(all(c.enabled for c in s4_cells))
        # S5 initialization places doors/raiders/medkit stimpak & locks both 0x00EFA9 and 0x00EFAA
        mh.ns["UpdateS5MuseumEncounter"](mh.player)
        self.assertTrue(preston_door.locked)
        self.assertTrue(preston_exit_door.locked)
        self.assertTrue(basement_term.activation_blocked)
        self.assertEqual(medkit.items.get("FO4SF_Stimpak"), 1)
        self.assertEqual(mh.stages, [])
        for mr in raiders:
            mr.dead = True
        mh.ns["UpdateS5MuseumEncounter"](mh.player)
        self.assertEqual(mh.stages, [35])
        self.assertFalse(preston_door.locked)
        self.assertTrue(preston_door.opened)
        self.assertFalse(preston_exit_door.locked)
        self.assertTrue(preston_exit_door.opened)
        self.assertIn("s5 museum_cleared dead=7/7 stage=35 preston_door=unlocked", mh.logs)

        # S6 Sturges room scene F1 retry honors full PrestonSceneCheckSeconds window + 16-tick bound, async Stop OnEnd consumption, ERROR on exhaustion, and 0 Debug.MessageBox popups
        async_s6_queue = []

        def _async_s6_stop():
            sturges_playing["flag"] = False
            sturges_playing["stops"] += 1
            async_s6_queue.append(lambda: mh.ns["Scene_OnEnd"](s6_sturges_scn))

        s6_sturges_scn.Stop = _async_s6_stop
        mh.ns["TriggerS6RoomScene"](True, "test")
        self.assertEqual(sturges_playing["starts"], 1)
        for _ in range(16):
            mh.ns["CheckS6RoomSceneOpen"](True)
        # Sub-window ticks (< 1.45s elapsed) never retry prematurely
        self.assertEqual(mh.ns["s6SturgesSceneRetries"], 0)
        mh.clock["rt"] += 1.55
        mh.ns["CheckS6RoomSceneOpen"](True)
        self.assertEqual(mh.ns["s6SturgesSceneRetries"], 1)
        self.assertTrue(mh.ns["s6SturgesSceneRestarting"])
        while async_s6_queue:
            async_s6_queue.pop(0)()
        self.assertFalse(mh.ns["s6SturgesSceneRestarting"])
        self.assertTrue(mh.ns["s6SturgesScenePending"])
        for _ in range(3):
            mh.ns["Scene_OnPhaseBegin"](s6_sturges_scn, 1)
            mh.clock["rt"] += 1.6
            mh.ns["CheckS6RoomSceneOpen"](True)
            while async_s6_queue:
                async_s6_queue.pop(0)()
        self.assertFalse(mh.ns["s6SturgesSceneRestarting"])
        self.assertFalse(sturges_playing["flag"])
        self.assertFalse(mh.ns["s6SturgesScenePending"])
        self.assertEqual(mh.msgboxes, [])
        self.assertIn(
            "s6 sturges ERROR scene_failed retries=3/3 reason=dialogue_menu_timeout actor_talkable=true",
            mh.logs,
        )

        # S6 Preston 3F talk (stage 40), locked gate stays BlockActivation(True) w/ 0 Bobby Pins, then 0x08A5 Bobby Pin unlocks & clears BlockActivation
        self.assertTrue(basement_gate.activation_blocked)
        self.assertTrue(mh.ns["AdvanceS6PrestonGroupTalk"]())
        mh.player.AddItem(SimpleNamespace(name="Digipick"), 1)
        self.assertFalse(mh.ns["PlayerHasBobbyPin"](mh.player))
        self.assertTrue(basement_gate.locked)
        self.assertTrue(basement_gate.activation_blocked)
        mh.player.AddItem(SimpleNamespace(name="FO4_BobbyPin"), 1)
        self.assertTrue(mh.ns["PlayerHasBobbyPin"](mh.player))
        self.assertTrue(mh.ns["TryOpenS6BasementGate"]("bobby_pin"))
        self.assertFalse(basement_gate.locked)
        self.assertFalse(basement_gate.activation_blocked)
        self.assertTrue(basement_gate.opened)
        self.assertIn("basement_gate_unlock=bobby_pin", mh.logs)
        self.assertTrue(mh.ns["AdvanceS6FusionCorePicked"]())
        self.assertEqual(mh.stages, [35, 40, 45, 50])
        self.assertIn(95, mh.obj_disp)
        self.assertFalse(mh.state["completed"])
        self.assertIn("s6 stage 50 fusion_core picked obj=95 stop=put_fusion_core_in_pa", mh.logs)

        # Independent terminal unlock path clears BlockActivation and emits basement_gate_unlock=terminal
        term_gate = _FakeMarker("FO4Port_MQ03SecurityGateREF_Term", 0.0, 0.0, 0.0)
        term_gate.locked = True
        mh_term = _build_min00_harness(enable_s4=True, enable_s6_s9=True, basement_gate=term_gate)
        self.assertTrue(mh_term.ns["AdvanceS6PrestonGroupTalk"]())
        self.assertTrue(mh_term.ns["TryOpenS6BasementGate"]("terminal"))
        self.assertFalse(term_gate.locked)
        self.assertFalse(term_gate.activation_blocked)
        self.assertTrue(term_gate.opened)
        self.assertIn("basement_gate_unlock=terminal", mh_term.logs)

    def test_799_async_dialogue_open_and_close_races_s3_stage50_and_s6(self):
        # 1. Codsworth S3Stage50Scene: (a) Attempt 2 DialogueMenu Open must NOT clear s3Stage50Restarting before
        # stale Attempt 1 OnEnd arrives; (b) Attempt 2 DialogueMenu Close one frame BEFORE Attempt 2 OnEnd
        # must still complete S3 via s3Stage50AttemptOpened latch.
        cods = _FakeActor("Codsworth", -2313.44, -1372.02, 112.66)
        playing = {"flag": False, "starts": 0, "stops": 0}
        scn50 = SimpleNamespace(
            IsPlaying=lambda: playing["flag"],
            Start=lambda: (playing.__setitem__("flag", True), playing.__setitem__("starts", playing["starts"] + 1)),
            ForceStart=lambda: (playing.__setitem__("flag", True), playing.__setitem__("starts", playing["starts"] + 1)),
            Stop=lambda: (playing.__setitem__("flag", False), playing.__setitem__("stops", playing["stops"] + 1)),
        )
        ch = _build_codsworth_harness(
            enable_s3=True, r11_glob_val=0.0, codsworth_actor=cods,
            creature_slot_ready=False, stage50_scene=scn50, msg_buttons=None,
        )
        async_q = []

        def _async_stop():
            playing["flag"] = False
            playing["stops"] += 1
            async_q.append(lambda: ch.ns["Scene_OnEnd"](scn50))

        scn50.Stop = _async_stop
        ch.ns["applied"] = 30
        ch.ns["UpdateS3HouseSearchProgress"]()
        cods.SetPosition(-2296.17, -1424.97, 111.77)
        ch.ns["UpdateS3HouseSearchProgress"]()
        self.assertEqual(playing["starts"], 1)

        ch.ns["Scene_OnPhaseBegin"](scn50, 1)
        ch.clock["rt"] += 1.6
        ch.ns["CheckS3Stage50SceneOpen"]()
        self.assertEqual(ch.ns["s3Stage50Retries"], 1)
        self.assertTrue(ch.ns["s3Stage50Restarting"])
        self.assertTrue(playing["flag"])

        # Race 1a: Attempt 2 DialogueMenu opens BEFORE Attempt 1 Stop()->OnEnd arrives
        ch.ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
        self.assertTrue(ch.ns["s3Stage50MenuOpened"])
        self.assertTrue(ch.ns["s3Stage50AttemptOpened"])
        self.assertTrue(ch.ns["s3Stage50Restarting"])

        # Stale Attempt 1 OnEnd arrives while Attempt 2 DialogueMenu is open -> consumed without finishing S3!
        while async_q:
            async_q.pop(0)()
        self.assertFalse(ch.ns["s3Stage50Restarting"])
        self.assertFalse(ch.state["completed"])
        self.assertNotIn(100, ch.stages)
        self.assertEqual(ch.min00.codsworth_given, 0)
        self.assertTrue(ch.ns["s3Stage50AttemptOpened"])

        # Race 2: Player closes DialogueMenu one frame BEFORE Attempt 2 Scene.OnEnd arrives
        ch.ns["OnMenuOpenCloseEvent"]("DialogueMenu", False)
        self.assertFalse(ch.ns["s3Stage50MenuOpened"])
        self.assertTrue(ch.ns["s3Stage50AttemptOpened"])
        self.assertFalse(ch.state["completed"])

        playing["flag"] = False
        ch.ns["Scene_OnEnd"](scn50)
        self.assertTrue(ch.state["completed"])
        self.assertIn(100, ch.stages)
        self.assertEqual(ch.min00.codsworth_given, 1)
        self.assertFalse(ch.ns["s3Stage50AttemptOpened"])

        # 2. Min00 S6 Preston & Sturges room scenes: DialogueMenu Open before stale Attempt 1 OnEnd
        p_play = {"flag": False, "starts": 0, "stops": 0}
        s_play = {"flag": False, "starts": 0, "stops": 0}
        async_p_q = []
        async_s_q = []
        s6_p_scn = SimpleNamespace(
            IsPlaying=lambda: p_play["flag"],
            Start=lambda: (p_play.__setitem__("flag", True), p_play.__setitem__("starts", p_play["starts"] + 1)),
            ForceStart=lambda: (p_play.__setitem__("flag", True), p_play.__setitem__("starts", p_play["starts"] + 1)),
        )
        s6_s_scn = SimpleNamespace(
            IsPlaying=lambda: s_play["flag"],
            Start=lambda: (s_play.__setitem__("flag", True), s_play.__setitem__("starts", s_play["starts"] + 1)),
            ForceStart=lambda: (s_play.__setitem__("flag", True), s_play.__setitem__("starts", s_play["starts"] + 1)),
        )
        mh = _build_min00_harness(
            enable_s4=True, enable_s6_s9=True,
            s6_preston_scene=s6_p_scn, s6_sturges_scene=s6_s_scn,
        )
        s6_p_scn.Stop = lambda: (p_play.__setitem__("flag", False), p_play.__setitem__("stops", p_play["stops"] + 1), async_p_q.append(lambda: mh.ns["Scene_OnEnd"](s6_p_scn)))
        s6_s_scn.Stop = lambda: (s_play.__setitem__("flag", False), s_play.__setitem__("stops", s_play["stops"] + 1), async_s_q.append(lambda: mh.ns["Scene_OnEnd"](s6_s_scn)))

        mh.ns["applied"] = 35
        mh.ns["TriggerS6RoomScene"](False, "test")
        mh.ns["Scene_OnPhaseBegin"](s6_p_scn, 1)
        mh.clock["rt"] += 1.6
        mh.ns["CheckS6RoomSceneOpen"](False)
        self.assertTrue(mh.ns["s6RoomSceneRestarting"])
        mh.ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
        self.assertTrue(mh.ns["s6RoomSceneMenuOpened"])
        self.assertTrue(mh.ns["s6RoomSceneRestarting"])
        while async_p_q:
            async_p_q.pop(0)()
        self.assertFalse(mh.ns["s6RoomSceneRestarting"])
        self.assertLess(mh.ns["s6FullStage"], 40)
        self.assertNotIn(40, mh.stages)
        mh.ns["OnMenuOpenCloseEvent"]("DialogueMenu", False)
        self.assertFalse(mh.ns["s6RoomSceneMenuOpened"])
        self.assertEqual(mh.ns["s6FullStage"], 40)
        self.assertIn(40, mh.stages)

        mh.ns["TriggerS6RoomScene"](True, "test")
        mh.ns["Scene_OnPhaseBegin"](s6_s_scn, 1)
        mh.clock["rt"] += 1.6
        mh.ns["CheckS6RoomSceneOpen"](True)
        self.assertTrue(mh.ns["s6SturgesSceneRestarting"])
        mh.ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
        self.assertTrue(mh.ns["s6SturgesSceneMenuOpened"])
        self.assertTrue(mh.ns["s6SturgesSceneRestarting"])
        while async_s_q:
            async_s_q.pop(0)()
        self.assertFalse(mh.ns["s6SturgesSceneRestarting"])
        self.assertTrue(mh.ns["s6SturgesSceneMenuOpened"])


if __name__ == "__main__":
    unittest.main()
