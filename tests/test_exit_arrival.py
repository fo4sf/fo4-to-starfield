"""Synthetic execution of the production exit/arrival branches with native calls substituted.

This small translator executes the Papyrus functions under test directly from `.psc` source.
It is not a Papyrus compiler or native-engine model; native placement/discovery remain PC gates.
It tests the actual branch bodies, so removing a production guard changes these results.
"""
import contextlib
import io
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest

from tests.test_newgame import CS, PSC, read, ng


FUNCTIONS = ("FinishSurface", "CheckLanding", "RequestArrivalDiscovery", "DiscoverMarkerViaMapMarkers", "AtArrival", "Near")
VARIABLES = (
    "arrivalWorld, surfaceSets, surfaceMovedAt, arrivedAt, fallbackPending, "
    "discoveryMarkerMoved, discoveryAttachPending, landingChecks"
)


class _PStr(str):
    """String wrapper allowing Papyrus-style `'text=' + non_str` concatenation in translated functions."""

    def __add__(self, other):
        return _PStr(super().__add__(str(other)))

    def __radd__(self, other):
        return _PStr(str(other) + str(self))


def _wrap_pstr_literals(expr: str) -> str:
    return re.sub(r'"([^"\\]*(?:\\.[^"\\]*)*)"', r'_PStr("\1")', expr)


def _strip_psc_line_comment(line: str) -> str:
    return re.sub(r'("(?:[^"\\]|\\.)*")|;.*', lambda m: m.group(1) or "", line)


def _rewrite_outside_strings(expr: str, fn) -> str:
    parts = re.split(r'("(?:[^"\\]|\\.)*")', expr)
    for idx in range(0, len(parts), 2):
        parts[idx] = fn(parts[idx])
    return "".join(parts)


def translated_functions(text, names=FUNCTIONS, variables=VARIABLES):
    clean_text = re.sub(r"\{[^}]*\}", "", text)
    out = [
        "class _PStr(str):",
        "    def __add__(self, other): return _PStr(super().__add__(str(other)))",
        "    def __radd__(self, other): return _PStr(str(other) + str(self))",
        "if 'Trace' not in globals(): Trace = lambda *_: None",
        "if 'Debug' not in globals(): globals()['Debug'] = type('_Dbg', (), {'Notification': staticmethod(lambda *_: None), 'TraceUser': staticmethod(lambda *_: True)})()",
        "def _p_cast_as(obj, name): return None if obj is None else (obj.CastAs(name) if hasattr(obj, 'CastAs') else obj)",
        "def _p_call_fn(obj, fn, args=()): return obj.CallFunction(fn, args) if hasattr(obj, 'CallFunction') else getattr(obj, fn)(*args)",
        "if 'self' not in globals(): globals()['self'] = None",
        "for _k, _v in (('ExitNeedAttrMsg', None), ('TestModeGlobal', None), ('RouteLootRefIds', []), ('MapMarkerQuestIds', []), ('H00SkipLoadingHookGlobal', None), ('H00ClearChargenGlobal', None), ('H00SkipArrivalDiscoveryGlobal', None), ('H00SkipMapSetupGlobal', None), ('H00SkipRouteLootGlobal', None), ('H00SkipMissionActorsGlobal', None), ('H00SkipLandingQuestsGlobal', None), ('H00SkipSurfaceSetPosGlobal', None), ('loadingHookRegistered', False), ('loadingMenuOpen', False), ('loadingMenuClosedSeen', False), ('landingLoadingMode', False), ('landingAwaitingFadeIn', False), ('landingFadeGuardRan', False), ('ascentGapStartedAt', 0.0), ('h00SuspectsRead', False), ('h00SkipLoading', False), ('h00ClearChargen', False), ('h00SkipDiscovery', False), ('h00SkipMap', False), ('h00SkipLoot', False), ('h00SkipActors', False), ('h00SkipQuests', False), ('h00SkipSetPos', False), ('portConsoleRegistered', False), ('portConsoleWatchedRef', None), ('consoleOpening', False), ('SilentArrivalDiscovery', True), ('ArrivalDiscoveryMethod', 'add_to_map'), ('SilentStarterStrip', True), ('StarterStripItems', []), ('SinglePassLandingFade', True), ('ArrivalWeatherId', 0x0027CF9B), ('ArrivalWeatherPlugin', 'Starfield.esm'), ('ArrivalWeatherOverride', True), ('VaultSuitFallbackId', 0x0001D1D7), ('VaultSuitFallbackPlugin', 'Starfield.esm'), ('surfaceFadeInDone', False), ('PodExitMode', 'safe_spawn'), ('PodEntryStep', -2.5), ('PodSafeStep', -3.2), ('PodSafeHeading', 270.0), ('podExitDone', False), ('liftPairActive', False), ('liftPairDescending', False), ('liftPairDone', False), ('liftPairTransferred', False), ('liftPairTransferPending', False), ('liftPairFadeStarted', False), ('liftPairActiveRef', None), ('liftPairStartCell', None), ('liftPairStartWorld', None), ('liftPairStartedAt', 0.0), ('liftPairStartX', 0.0), ('liftPairStartY', 0.0), ('liftPairStartZ', 0.0), ('liftPairTransferRetries', 0), ('liftPairTransferRetryAt', 0.0), ('surfaceCogRef', None), ('surfaceCogActivationRegistered', False), ('surfaceCogLoggedArrival', False), ('surfaceCogRefs', None), ('surfaceCogActivationReg', None), ('surfaceCogLogged', None), ('surfaceCogStates', None), ('surfaceCogRisePending', False), ('surfaceCogRising', False), ('surfaceCogRiseStartedAt', 0.0), ('surfaceCogDone', False), ('interiorLiftState', 'A'), ('interiorLiftDescending', False), ('interiorLiftDescendAt', 0.0), ('interiorLiftDescendDone', False), ('liftPairUpArriveEventPending', False), ('ActiveLiftPairId', 'fo4.vault111_exit'), ('LiftPairIds', ['fo4.vault111_exit']), ('LiftRise', 21.6), ('LiftSeconds', 9.8667), ('LiftResetSeconds', 23.8333), ('LiftFadeLead', 1.1), ('LiftDoneMargin', 0.25), ('LiftPlayEvent', 'Play01'), ('LiftResetEvent', 'Play02'), ('SurfaceCogPlugins', ['FO4SFExitLift.esm']), ('SurfaceCogLocalX', [-1275.5824]), ('SurfaceCogLocalY', [1296.0703]), ('SurfaceCogLocalZ', [33.253544]), ('SurfaceCogPadRadius', [3.2]), ('SurfaceLiftDrop', [59.1425]), ('SurfaceLiftSeconds', [18.6667]), ('SurfaceLiftFadeAt', [7.533]), ('SurfaceLiftDoneMargin', [0.25]), ('SurfaceLiftPlayEvents', ['Play01']), ('SurfaceLiftResetEvents', ['Play02']), ('SurfaceLiftAscendClips', ['StateB_Play']), ('SurfaceLiftAscendSeconds', [11.6667]), ('SurfaceLiftAscendRise', [25.9932]), ('SurfaceCoreStaticBaseIds', [0x0A2D4B]), ('leftArrivalPad', False), ('returnLiftArmed', False), ('returnAsked', False), ('returnVaultAsked', False), ('returnHasExteriorSample', False), ('returnLastExteriorX', 0.0), ('returnLastExteriorY', 0.0)):",
        "    if _k not in globals(): globals()[_k] = _v",
        "for _fn in ('ReadH00SuspectsOnce', 'ApplyH00PreSurfaceOverrides', 'RegisterStartLoadingHook', 'UnregisterStartLoadingHook', 'ForceFadeIn', 'CompleteLandingFadeIn', 'PlaySurfaceCogRise', 'FinishSurfaceCogRise', 'SuppressMapMarkersDarkHold', 'CancelTimer', 'RunPodExitHook', 'EnsurePipboyWristEquipped', 'EnsureSurfaceLiftCog', 'RecoverPairedLiftOnLoad', 'CheckPairedLiftRide', 'StartPairedLiftRide', 'ResetSurfaceLiftCog', 'EnsurePairCogStorage', 'EmitLiftPairArrived', 'SendCustomEvent', 'ApplyArrivalWeather'):",
        "    if _fn not in globals(): globals()[_fn] = lambda *_a: None",
        "if 'PairIndex' not in globals(): globals()['PairIndex'] = lambda _p='': 0",
        "if 'UnspentSpecialPool' not in globals(): globals()['UnspentSpecialPool'] = lambda *_a: 0",
        "if 'GetPairCogState' not in globals(): globals()['GetPairCogState'] = lambda _p='': 'A' if globals().get('surfaceCogStates') is None else (surfaceCogStates[0] or 'A')",
        "if 'SetPairCogState' not in globals(): globals()['SetPairCogState'] = lambda _p, st: globals().__setitem__('surfaceCogStates', [st])",
        "if 'GetPairSurfaceCog' not in globals(): globals()['GetPairSurfaceCog'] = lambda _p='': globals().get('surfaceCogRef') if globals().get('surfaceCogRefs') is None else (surfaceCogRefs[0] if surfaceCogRefs else None)",
        "if 'SetPairSurfaceCog' not in globals(): globals()['SetPairSurfaceCog'] = lambda _p, c: (globals().__setitem__('surfaceCogRef', c), globals().__setitem__('surfaceCogRefs', [c]))",
        "if 'GetPairCogActivationReg' not in globals(): globals()['GetPairCogActivationReg'] = lambda _p='': globals().get('surfaceCogActivationRegistered', False) if globals().get('surfaceCogActivationReg') is None else bool(surfaceCogActivationReg[0])",
        "if 'SetPairCogActivationReg' not in globals(): globals()['SetPairCogActivationReg'] = lambda _p, v: (globals().__setitem__('surfaceCogActivationRegistered', v), globals().__setitem__('surfaceCogActivationReg', [v]))",
        "if 'GetPairCogLogged' not in globals(): globals()['GetPairCogLogged'] = lambda _p='': globals().get('surfaceCogLoggedArrival', False) if globals().get('surfaceCogLogged') is None else bool(surfaceCogLogged[0])",
        "if 'SetPairCogLogged' not in globals(): globals()['SetPairCogLogged'] = lambda _p, v: (globals().__setitem__('surfaceCogLoggedArrival', v), globals().__setitem__('surfaceCogLogged', [v]))",
        "if 'PairSurfaceCogPadRadius' not in globals(): globals()['PairSurfaceCogPadRadius'] = lambda _p='': float(SurfaceCogPadRadius[0]) if SurfaceCogPadRadius else 3.2",
        "if 'PairSurfaceCogLocalX' not in globals(): globals()['PairSurfaceCogLocalX'] = lambda _p='': float(SurfaceCogLocalX[0]) if SurfaceCogLocalX else -1275.5824",
        "if 'PairSurfaceCogLocalY' not in globals(): globals()['PairSurfaceCogLocalY'] = lambda _p='': float(SurfaceCogLocalY[0]) if SurfaceCogLocalY else 1296.0703",
        "if 'PairSurfaceCogLocalZ' not in globals(): globals()['PairSurfaceCogLocalZ'] = lambda _p='': float(SurfaceCogLocalZ[0]) if SurfaceCogLocalZ else 33.253544",
        "if 'PairSurfaceLiftSeconds' not in globals(): globals()['PairSurfaceLiftSeconds'] = lambda _p='': float(SurfaceLiftSeconds[0]) if SurfaceLiftSeconds else 18.6667",
        "if 'PairSurfaceLiftFadeAt' not in globals(): globals()['PairSurfaceLiftFadeAt'] = lambda _p='': float(SurfaceLiftFadeAt[0]) if SurfaceLiftFadeAt else 7.533",
        "if 'PairSurfaceLiftDoneMargin' not in globals(): globals()['PairSurfaceLiftDoneMargin'] = lambda _p='': float(SurfaceLiftDoneMargin[0]) if SurfaceLiftDoneMargin else 0.25",
        "if 'PairSurfacePlayEvent' not in globals(): globals()['PairSurfacePlayEvent'] = lambda _p='': SurfaceLiftPlayEvents[0] if SurfaceLiftPlayEvents else 'Play01'",
        "if 'PairSurfaceResetEvent' not in globals(): globals()['PairSurfaceResetEvent'] = lambda _p='': SurfaceLiftResetEvents[0] if SurfaceLiftResetEvents else 'Play02'",
        "if 'PairSurfaceAscendClip' not in globals(): globals()['PairSurfaceAscendClip'] = lambda _p='': SurfaceLiftAscendClips[0] if SurfaceLiftAscendClips else 'StateB_Play'",
        "if 'PairSurfaceAscendSeconds' not in globals(): globals()['PairSurfaceAscendSeconds'] = lambda _p='': float(SurfaceLiftAscendSeconds[0]) if SurfaceLiftAscendSeconds else 11.6667",
        "if 'PairSurfaceAscendRise' not in globals(): globals()['PairSurfaceAscendRise'] = lambda _p='': float(SurfaceLiftAscendRise[0]) if SurfaceLiftAscendRise else 25.9932",
        "if 'PairCoreStaticCogBaseId' not in globals(): globals()['PairCoreStaticCogBaseId'] = lambda _p='': int(SurfaceCoreStaticBaseIds[0]) if SurfaceCoreStaticBaseIds else 0x0A2D4B",
        "if 'GetStage' not in globals(): globals()['GetStage'] = lambda: globals().get('applied', 30)",
        "if 'ReadH00Glob' not in globals(): globals()['ReadH00Glob'] = lambda g, _fid: bool(g is not None and g.GetValue() >= 0.5)",
        "if 'BoolBit' not in globals(): globals()['BoolBit'] = lambda f: 1 if f else 0",
    ]
    for name in names:
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
                if rhs.lower() == "true":
                    rhs = "True"
                elif rhs.lower() == "false":
                    rhs = "False"
                elif rhs.lower() == "none":
                    rhs = "None"
                py_args.append(f"{p_name}={rhs}")
            else:
                py_args.append(raw_arg.split()[-1])
        fn_py_name = name.split(".")[-1]
        out.append(f"def {fn_py_name}({', '.join(py_args)}):")
        if variables.strip():
            out.append("    global " + variables + ", portConsoleRegistered, portConsoleWatchedRef, consoleOpening, surfaceFadeInDone, podExitDone, loadingMenuOpen, loadingMenuClosedSeen, landingLoadingMode, landingAwaitingFadeIn, landingFadeGuardRan, ascentGapStartedAt, liftPairActive, liftPairDescending, liftPairDone, liftPairTransferred, liftPairTransferPending, liftPairFadeStarted, liftPairActiveRef, liftPairStartCell, liftPairStartWorld, liftPairStartedAt, liftPairStartX, liftPairStartY, liftPairStartZ, liftPairTransferRetries, liftPairTransferRetryAt, surfaceCogRefs, surfaceCogActivationReg, surfaceCogLogged, surfaceCogStates, surfaceCogRisePending, surfaceCogRising, surfaceCogRiseStartedAt, surfaceCogDone, interiorLiftState, interiorLiftDescending, interiorLiftDescendAt, interiorLiftDescendDone, liftPairUpArriveEventPending, leftArrivalPad, returnLiftArmed, returnAsked, returnVaultAsked, returnHasExteriorSample, returnLastExteriorX, returnLastExteriorY")
        depth = 1
        body = re.sub(r"\{.*?\}", "", body, flags=re.S)
        for line in body.splitlines():
            line = _strip_psc_line_comment(line).strip()
            if not line:
                continue
            if line in ("endif", "endwhile"):
                depth -= 1
                continue
            if line.startswith(("elseif ", "else")):
                depth -= 1
            if any(tok in line for tok in ("Trace(", "Debug.TraceUser(", "LogLine(", "LogNewGameLine(", "Debug.Notification(")):
                line = _wrap_pstr_literals(line)
            if line.startswith(("bool ", "int ", "float ", "string ")) and "=" in line:
                pass
            line = re.sub(r"\bint\[\]\s+(\w+)\s*=\s*new\s+int\[(\d+)\]", r"\1 = [0] * \2", line)
            line = re.sub(r"\bfloat\[\]\s+(\w+)\s*=\s*new\s+float\[(\d+)\]", r"\1 = [0.0] * \2", line)
            line = re.sub(r"\bbool\[\]\s+(\w+)\s*=\s*new\s+bool\[(\d+)\]", r"\1 = [False] * \2", line)
            line = re.sub(r"\bstring\[\]\s+(\w+)\s*=\s*new\s+string\[(\d+)\]", r"\1 = [''] * \2", line)
            line = re.sub(r"\bObjectReference\[\]\s+(\w+)\s*=\s*new\s+ObjectReference\[(\d+)\]", r"\1 = [None] * \2", line)
            line = re.sub(r"\bVar\[\]\s+(\w+)\s*=\s*new\s+Var\[(\d+)\]", r"\1 = [None] * \2", line)
            line = re.sub(r"\b(\w+)\s*=\s*new\s+(?:ObjectReference|Var)\[(\d+)\]", r"\1 = [None] * \2", line)
            line = re.sub(r"\b(\w+)\s*=\s*new\s+bool\[(\d+)\]", r"\1 = [False] * \2", line)
            line = re.sub(r"\b(\w+)\s*=\s*new\s+int\[(\d+)\]", r"\1 = [0] * \2", line)
            line = re.sub(r"\b(\w+)\s*=\s*new\s+string\[(\d+)\]", r"\1 = [''] * \2", line)
            line = re.sub(r"\bnew\s+Var\[0\]", "[]", line)
            line = re.sub(r"^int\s+(\w+)\s*=\s*(.+)", r"\1 = int(\2)", line)
            line = re.sub(
                r"^(?:bool|float|string|WorldSpace|Cell|Form|ObjectReference|Weapon|Armor|Actor|Quest|Faction|GlobalVariable|ActorValue|Idle|ScriptObject|Var|Weather|FO4SF_\w+)\s+(\w+)\s*=",
                r"\1 =",
                line,
            )
            line = re.sub(
                r"\s+as\s+(?:ObjectReference|Weapon|Armor|Actor|Quest|Faction|GlobalVariable|ActorValue|Idle|ScriptObject|Var|Weather|FO4SF_\w+)\b",
                "",
                line,
            )
            line = re.sub(r"(\(\w+\)|\b\w+)\.CastAs\(([^()]+)\)", r"_p_cast_as(\1, \2)", line)
            line = re.sub(r"(\(\w+\)|\b\w+)\.CallFunction\(([^,]+),\s*([^\n)]+)\)", r"_p_call_fn(\1, \2, \3)", line)
            line = re.sub(r"((?:_p_call_fn\([^)]+\)|[\w.\[\]]+(?:\([^()]*(?:\([^()]*\))?\))?))\s+as\s+float\b", r"float(\1)", line)
            line = re.sub(r"((?:_p_call_fn\([^)]+\)|[\w.\[\]]+(?:\([^()]*(?:\([^()]*\))?\))?))\s+as\s+int\b", r"int(\1)", line)
            line = re.sub(r"((?:_p_call_fn\([^)]+\)|[\w.\[\]]+(?:\([^()]*(?:\([^()]*\))?\))?))\s+as\s+bool\b", r"bool(\1)", line)
            def _ops(seg: str) -> str:
                seg = re.sub(r"\b(\w+)\.Length\b", r"len(\1)", seg)
                seg = re.sub(r"\btrue\b", "True", seg, flags=re.I)
                seg = re.sub(r"\bfalse\b", "False", seg, flags=re.I)
                return re.sub(r"!(?!=)", "not ", seg).replace("&&", "and").replace("||", "or")

            line = _rewrite_outside_strings(line, _ops)
            if line.startswith("elseif "):
                line = "elif " + line[7:]
            if line.startswith(("if ", "elif ", "while ")) or line == "else":
                line += ":"
                out.append("    " * depth + line)
                depth += 1
            else:
                out.append("    " * depth + line)
        if depth != 1:
            raise AssertionError(f"unbalanced source: {name}")
    return "\n".join(out)


class Reference:
    def __init__(self, world, pos, form_id=0x030A775B):
        self.world, self.pos, self.form_id = world, pos, form_id
        self.interior = False
        self.loaded = True
        self.cell = SimpleNamespace(GetFormID=lambda: 0x03000CF0)
        self.take_position = True
        self.take_move = True
        self.on_set_position = None
        self.moves = []
        self.moveto_calls = []
        self.enables = []
        self.add_to_map_calls = []
        self.enable_fast_travel_calls = []
        self.resets = 0
        self.discovery_calls = 0
        self.equipped = set()
        self.equip_calls = []

    def GetWorldSpace(self): return self.world
    def GetParentCell(self): return self.cell
    def GetFormID(self): return self.form_id
    def GetPositionX(self): return self.pos[0]
    def GetPositionY(self): return self.pos[1]
    def GetPositionZ(self): return self.pos[2]
    def Is3DLoaded(self): return self.loaded
    def IsInInterior(self): return self.interior
    def SetAngle(self, *args): pass
    def IsEquipped(self, item): return item in self.equipped

    def EquipItem(self, item, prevent_removal=False, silent=False):
        self.equip_calls.append((item, prevent_removal, silent))
        self.equipped.add(item)

    def Enable(self, fade=False):
        self.enables.append(fade)

    def MoveTo(self, target, dx=0.0, dy=0.0, dz=0.0, match_rot=False, match_dead=False):
        self.moveto_calls.append((target, dx, dy, dz))
        if self.take_move:
            self.world = target.GetWorldSpace()
            self.cell = target.GetParentCell()
            self.interior = target.IsInInterior()
            self.pos = (target.GetPositionX() + dx, target.GetPositionY() + dy, target.GetPositionZ() + dz)

    def SetPosition(self, *pos):
        self.moves.append(pos)
        if self.take_position:
            self.pos = pos
            if self.on_set_position is not None:
                self.on_set_position(pos)

    def SetMarkerDiscovered(self):
        self.discovery_calls += 1

    def AddToMap(self, allow_fast_travel=False):
        self.add_to_map_calls.append(allow_fast_travel)

    def IsMapMarkerVisible(self):
        return len(self.add_to_map_calls) > 0 or self.discovery_calls > 0

    def CanFastTravelToMarker(self):
        return (True in self.add_to_map_calls) or self.discovery_calls > 0

    def EnableFastTravel(self, enable=True):
        self.enable_fast_travel_calls.append(enable)

    def Reset(self, target=None):
        self.resets += 1


class ArrivalExecutionTests(unittest.TestCase):
    def setUp(self):
        self.world = object()  # runtime MarsPlanetWorld (0xFF......) differs from FO4Core_Commonwealth (0x03000803)
        self.player = Reference(self.world, (-1200.0, -2700.0, 100.0))
        self.marker = Reference(self.world, (-1210.0, -2720.0, 95.0))
        self.failures, self.stages, self.traces = [], [], []
        self.now = 10.0
        self.ns = dict(
            _PStr=_PStr,
            Trace=self.traces.append,
            arrivalWorld=self.world, ArrivalX=0.0, ArrivalY=0.0, ArrivalZ=100.0,
            ArrivalHeading=0.0, MergeOffsetX=-1200.0, MergeOffsetY=-2700.0,
            FallbackX=-10.0, FallbackY=-20.0, FallbackZ=95.0, FallDrop=3.0,
            ExitAnchorId=0x0A775B, ArrivalDiscoveryId=0x0A775B, CorePlugin="FO4TerrainCore.esm",
            MapMarkerQuestIds=[], SilentArrivalDiscovery=False, ArrivalDiscoveryMethod="during_fade",
            SinglePassLandingFade=True, surfaceFadeInDone=False,
            SurfaceWait=10.0, SurfaceTries=3, surfaceMoves=1, surfaceSets=0,
            surfaceMovedAt=1.0, arrivedAt=1.0, fallbackPending=False,
            discoveryMarkerMoved=False, discoveryAttachPending=False, landingChecks=0,
            Game=SimpleNamespace(GetFormFromFile=lambda *_: self.marker, IsFastTravelEnabled=lambda: True),
            Utility=SimpleNamespace(GetCurrentRealTime=lambda: self.now),
            FailExit=self.failures.append, AdvanceTo=self.stages.append,
        )
        exec(compile(translated_functions(read(PSC)), PSC, "exec"), self.ns)

    def run_branch(self, name):
        self.ns[name](self.player)

    def test_non_core_moveto_cell_becomes_core_after_setposition(self):
        """MoveTo lands at unmerged (-1275.3, 1305.3) in procedural Surface (FF00A492); SetPosition shifts into core 03000CF0."""
        self.player.pos = (-1275.3, 1305.3, 119.4)
        self.player.cell = SimpleNamespace(GetFormID=lambda: 0xFF00A492)

        def shift_to_merged_core(pos):
            if abs(pos[0] - (-1200.0)) < 1.0 and abs(pos[1] - (-2700.0)) < 1.0:
                self.player.cell = SimpleNamespace(GetFormID=lambda: 0x03000CF0)

        self.player.on_set_position = shift_to_merged_core
        self.run_branch("FinishSurface")
        self.assertEqual(self.player.moves, [(-1200.0, -2700.0, 100.0)])
        self.assertEqual(self.stages, [40])
        self.assertEqual(self.failures, [])

    def test_translator_catches_untruncated_float_formid_divide(self):
        """Without storing both / 16777216 quotients in int, 03000CF0/16777216 != 030A775B/16777216 fails as float."""
        buggy = re.sub(
            r"bool coreCell = false.*?endif",
            "bool coreCell = afterCell != None && afterCell.GetFormID() / 16777216 == anchor.GetFormID() / 16777216",
            read(PSC),
            count=1,
            flags=re.S,
        )
        ns = dict(self.ns)
        failures, stages = [], []
        ns["FailExit"] = failures.append
        ns["AdvanceTo"] = stages.append
        ns["surfaceSets"] = 0
        exec(compile(translated_functions(buggy), "<buggy>", "exec"), ns)
        for _ in range(3):
            ns["FinishSurface"](self.player)
        self.assertEqual(failures, ["surface_cell_not_core"])
        self.assertEqual(stages, [])

    def test_post_setposition_cell_still_non_core_retries_then_fails(self):
        self.player.cell = SimpleNamespace(GetFormID=lambda: 0xFF00A492)
        for _ in range(3):
            self.run_branch("FinishSurface")
        self.assertEqual(len(self.player.moves), 3)
        self.assertEqual(self.failures, ["surface_cell_not_core"])
        self.assertEqual(self.stages, [])
        self.assertEqual(self.marker.discovery_calls, 0)

    def test_failed_setposition_budget_never_advances_or_discovers(self):
        self.player.pos = (0.0, 0.0, 100.0)
        self.player.take_position = False
        for _ in range(3):
            self.run_branch("FinishSurface")
        self.assertEqual(self.failures, ["surface_position_not_confirmed"])
        self.assertEqual(self.stages, [])
        self.assertEqual(self.marker.discovery_calls, 0)

    def test_loaded_primary_arrival_requests_one_marker_then_completes(self):
        self.run_branch("FinishSurface")
        self.assertEqual(self.stages, [40])
        self.assertEqual(self.marker.discovery_calls, 0)
        self.run_branch("CheckLanding")  # still within the 0.25 s settling interval
        self.assertEqual(self.marker.discovery_calls, 0)
        self.now += 0.25
        self.run_branch("CheckLanding")
        self.assertEqual(self.marker.discovery_calls, 1)
        self.assertTrue(any(t.startswith("arrival discovery silent=False method=during_fade visible=True can_travel=True ") for t in self.traces), self.traces)
        self.assertEqual(self.stages, [40, 200])
        self.assertEqual(self.failures, [])

    def test_self_attaches_unmerged_marker_when_map_mover_absent_then_confirms_next_tick(self):
        """Without FO4SFMapMarkers.esm, persistent 030A775B sits in 03000803 at unmerged XY; attach once, confirm next tick."""
        overlay_world = object()
        self.marker.world = overlay_world
        self.marker.pos = (-10.0, -20.0, 95.0)
        self.run_branch("CheckLanding")
        self.assertEqual(self.marker.enables, [False])
        self.assertEqual(len(self.marker.moveto_calls), 1)
        self.assertEqual(self.marker.moves, [(-1210.0, -2720.0, 95.0)])
        self.assertEqual(self.marker.discovery_calls, 0)
        self.assertEqual(self.stages, [])
        self.run_branch("CheckLanding")
        self.assertEqual(self.marker.discovery_calls, 1)
        self.assertEqual(self.stages, [200])
        self.assertEqual(self.failures, [])

    def test_fallback_requires_a_later_observation(self):
        self.player.pos = (-1200.0, -2700.0, 90.0)
        self.run_branch("CheckLanding")
        self.assertEqual(self.player.moves, [(-1210.0, -2720.0, 96.0)])
        self.assertEqual(self.marker.discovery_calls, 0)
        self.assertEqual(self.stages, [])
        self.run_branch("CheckLanding")
        self.assertEqual(self.marker.discovery_calls, 1)
        self.assertEqual(self.stages, [200])

    def test_b2_player_walked_beyond_5m_in_arrival_world_still_confirms_landing_and_discovers(self):
        """B2: Landing confirms once outside in arrivalWorld with 3D loaded, even if the player walked > 5 m away."""
        self.player.pos = (-1150.0, -2660.0, 102.0)  # > 60 m from ArrivalX/Y, still in arrivalWorld with 3D loaded
        self.run_branch("CheckLanding")
        self.assertEqual(self.failures, [])
        self.assertEqual(self.marker.discovery_calls, 1)
        self.assertEqual(self.stages, [200])

    def test_b2_failed_or_missing_marker_discovery_logs_failure_and_still_advances_to_stage_200(self):
        """B2: Missing or unattachable marker logs arrival discovery failed and STILL advances to stage 200."""
        # Case 1: Marker missing (None) -> logs failure immediately and advances to stage 200
        self.setUp()
        self.ns["Game"].GetFormFromFile = lambda *_: None
        self.run_branch("CheckLanding")
        self.assertEqual(self.failures, [])
        self.assertEqual(self.marker.discovery_calls, 0)
        self.assertTrue(any("arrival discovery failed reason=marker_missing" in t for t in self.traces), self.traces)
        self.assertEqual(self.stages, [200])

        # Case 2: Unattached or misplaced marker that refuses MoveTo/SetPosition -> tries attach on tick 1, logs failure + stage 200 on tick 2
        for world, pos in [(None, self.marker.pos), (object(), self.marker.pos), (self.world, (0.0, 0.0, 95.0))]:
            with self.subTest(world=world, pos=pos):
                self.setUp()
                self.marker.world, self.marker.pos = world, pos
                self.marker.take_move = False
                self.marker.take_position = False
                self.run_branch("CheckLanding")
                self.assertEqual(self.stages, [])  # 1 tick given for the attach MoveTo to settle
                self.assertEqual(len(self.marker.moveto_calls), 1)
                self.run_branch("CheckLanding")
                self.assertEqual(self.failures, [])
                self.assertEqual(self.marker.discovery_calls, 0)
                self.assertTrue(
                    any("arrival discovery failed reason=marker_not_attached" in t for t in self.traces),
                    self.traces,
                )
                self.assertEqual(self.stages, [200])

    def test_same_coordinates_in_wrong_player_world_cannot_discover(self):
        self.player.world = object()
        self.run_branch("CheckLanding")
        self.assertEqual(self.failures, ["landing_world_changed"])
        self.assertEqual(self.marker.discovery_calls, 0)
        self.assertEqual(self.stages, [])

    def test_indoor_and_unloaded_never_request_discovery(self):
        for field, value in [("interior", True), ("loaded", False)]:
            with self.subTest(field=field):
                self.setUp()
                setattr(self.player, field, value)
                self.run_branch("CheckLanding")
                self.assertEqual(self.marker.discovery_calls, 0)
                self.assertEqual(self.stages, [])

    def test_leaving_world_during_marker_reads_prevents_discovery_call(self):
        def fast_read():
            self.player.world = object()
            return True

        self.ns["Game"].IsFastTravelEnabled = fast_read
        self.run_branch("CheckLanding")
        self.assertEqual(self.marker.discovery_calls, 0)
        self.assertTrue(any("arrival discovery failed reason=state_changed_before_discover" in t for t in self.traces))
        self.assertEqual(self.stages, [200])

    def test_custom_exit_discovery_is_disabled_and_writer_pins_canonical_marker(self):
        self.ns["ArrivalDiscoveryId"] = 0
        self.run_branch("CheckLanding")
        self.assertEqual(self.marker.discovery_calls, 0)
        self.assertEqual(self.stages, [200])
        self.assertIn('("ArrivalDiscoveryId", o.ExitAnchor == ExitAnchorEdid ? (int)p.ExitAnchor : 0)', read(CS))
        code = re.sub(r"\{.*?\}|;[^\n]*", "", read(PSC), flags=re.S)
        req_code = code[code.index("bool Function RequestArrivalDiscovery"):code.index("bool Function AtArrival")]
        self.assertIn("DiscoverMarkerViaMapMarkers(marker)", req_code)
        self.assertIn(".IsMapMarkerVisible()", req_code)
        self.assertIn(".CanFastTravelToMarker()", req_code)
        self.assertIn("DiscoverSingleMarkerSilent", req_code)
        self.assertIn(".AddToMap(True)", req_code)
        self.assertIn(".SetMarkerDiscovered()", req_code)
        ft_code = code[code.index("Function TryFastTravelSurface"):code.index("Function TrySurfaceExteriorFallbacks")]
        self.assertNotIn(".AddToMap(", ft_code)
        self.assertNotIn(".SetMarkerDiscovered()", ft_code)
        self.assertIn(".EnableFastTravel(True)", ft_code)
        self.assertIn("Game.FastTravel(", ft_code)


class _LiftRef(Reference):
    def __init__(self, cell):
        super().__init__(None, (-70.392, -2.742, -0.114), form_id=0x02001618)
        self.interior = True
        self.cell = cell
        self.base = object()
        self.plays = []
        self.accepted = True

    def GetBaseObject(self):
        return self.base

    def PlayAnimation(self, name):
        self.plays.append(name)
        return self.accepted


class ExitRetryAndFallbackExecutionTests(unittest.TestCase):
    """B1 + R10: Translated-execution tests proving lift failures return to the platform & offer retry, then fallback after 3."""

    EXIT_FUNCTIONS = (
        "InVault",
        "PromptVaultExitLift",
        "StartPairedLiftRide",
        "OnAnimationEvent",
        "CheckPairedLiftRide",
        "RecoverPairedLiftOnLoad",
        "FailPairedLift",
        "Surface",
        "FinishSurface",
        "FailExit",
        "Near",
        "ReturnPlayerToVaultPlatform",
        "ResetVaultExitLift",
        "TryFastTravelSurface",
        "TrySurfaceExteriorFallbacks",
        "FallbackExitToSurface",
        "ClearVaultSaveLock",
        "RelockVaultSaving",
        "Actor.OnPlayerLoadGame",
    )
    EXIT_VARS = (
        "asked, liftSpecConfirmed, liftPairActiveRef, liftPairStartCell, liftPairStartWorld, liftPairStartedAt, "
        "liftPairStartX, liftPairStartY, liftPairStartZ, liftPairActive, liftPairDescending, liftPairDone, "
        "liftPairTransferred, liftPairTransferPending, liftPairFadeStarted, liftPairTransferRetries, "
        "exitFailures, exitUsedFallback, surfaceMovedAt, surfaceMoves, surfaceSets, arrivalWorld, arrivedAt, "
        "fallbackPending, discoveryMarkerMoved, discoveryAttachPending, landingChecks, "
        "vaultPodAutosaved, vaultSavingRelocked, vaultRecoveryTriggered"
    )

    def setUp(self):
        self.now = 10.0
        self.vault_cell = SimpleNamespace(GetFormID=lambda: 0x020011F3)
        self.surface_world = object()
        self.core_cell = SimpleNamespace(GetFormID=lambda: 0x03000CF0)

        self.vault_anchor = Reference(None, (-60.0, 0.0, -1.0), form_id=0x02000805)
        self.vault_anchor.interior = True
        self.vault_anchor.cell = self.vault_cell

        self.exit_anchor = Reference(self.surface_world, (-1275.3, 1305.3, 108.2), form_id=0x030A775B)
        self.exit_anchor.interior = False
        self.exit_anchor.cell = SimpleNamespace(GetFormID=lambda: 0xFF00A492)

        self.lift = _LiftRef(self.vault_cell)
        self.player = Reference(None, (-77.742, -3.958, -1.72), form_id=0x00000014)
        self.player.interior = True
        self.player.cell = self.vault_cell

        def on_player_set_pos(pos):
            if not self.player.interior and abs(pos[0] - (-1200.0)) < 1.0 and abs(pos[1] - (-2700.0)) < 1.0:
                self.player.cell = self.core_cell

        self.player.on_set_position = on_player_set_pos

        self.stage = 30
        self.stages = []
        self.traces = []
        self.fades = []
        self.timers = []
        self.cancels = []
        self.chargens = []
        self.huds = []
        self.fast_travels = []
        self.waits = []
        self.core_anchor = Reference(self.surface_world, (0.0, 0.0, 100.0), form_id=0x03000800)
        self.core_anchor.interior = False
        self.core_anchor.cell = self.core_cell
        self.land_marker = Reference(self.surface_world, (-1959.0, -493.0, 100.0), form_id=0x100008F2)
        self.land_marker.interior = False
        self.land_marker.cell = self.core_cell
        self.exit_prompts = 0
        self.exit_button = 0
        self.fallback_prompts = 0
        self.fallback_button = 0
        self.unregistrations = []

        def advance_to(n):
            self.stage = n
            self.stages.append(n)

        def get_form(fid, plg):
            if plg == "FO4Port.esm":
                if fid == 0x805:
                    return self.vault_anchor
                if fid == 0x1618:
                    return self.lift
                if fid == 0x1619:
                    return self.lift.base
            if plg == "FO4TerrainCore.esm":
                if fid == 0x0A775B:
                    return self.exit_anchor
                if fid == 0x000800:
                    return self.core_anchor
            if plg == "FO4SFMapMarkers.esm" and fid == 0x0008F2:
                return self.land_marker
            return None

        def exit_show():
            self.exit_prompts += 1
            return self.exit_button

        def fallback_show():
            self.fallback_prompts += 1
            return self.fallback_button

        self.ns = dict(
            _PStr=_PStr,
            LogName="fo4sf_newgame",
            Trace=self.traces.append,
            asked=False,
            liftSpecConfirmed=True,
            TestModeGlobal=None,
            GameModeGlobal=SimpleNamespace(GetValue=lambda: 1.0, SetValue=lambda v: None),
            CogDoorId=0x126D,
            VaultPlugin="FO4Port.esm",
            VaultAnchorId=0x805,
            AnchorX=-60.0,
            AnchorY=0.0,
            AnchorZ=-1.0,
            ConsoleX=-53.7,
            ConsoleY=-3.7,
            ConsoleZ=0.53,
            ConsoleRadius=2.5,
            PlatformX=-77.742,
            PlatformY=-3.958,
            PlatformZ=-1.751,
            PlatformRadius=2.0,
            LiftId=0x1618,
            LiftBaseId=0x1619,
            LiftRise=21.6,
            LiftSeconds=9.8667,
            LiftFadeLead=1.1,
            LiftDoneMargin=0.25,
            LiftPlayEvent="Play01",
            LiftResetEvent="Play02",
            ActiveLiftPairId="fo4.vault111_exit",
            LiftPairIds=["fo4.vault111_exit"],
            CorePlugin="FO4TerrainCore.esm",
            ExitAnchorId=0x0A775B,
            ArrivalDiscoveryId=0x0A775B,
            ArrivalX=0.0,
            ArrivalY=0.0,
            ArrivalZ=100.0,
            ArrivalHeading=0.0,
            FallbackX=-10.0,
            FallbackY=-20.0,
            FallbackZ=95.0,
            MergeOffsetX=-1200.0,
            MergeOffsetY=-2700.0,
            FallDrop=3.0,
            SurfaceWait=10.0,
            SurfaceTries=3,
            liftPairActiveRef=None,
            liftPairStartCell=None,
            liftPairStartWorld=None,
            liftPairStartedAt=0.0,
            liftPairStartX=0.0,
            liftPairStartY=0.0,
            liftPairStartZ=0.0,
            liftPairActive=False,
            liftPairDescending=False,
            liftPairDone=False,
            liftPairTransferred=False,
            liftPairTransferPending=False,
            liftPairFadeStarted=False,
            liftPairTransferRetries=0,
            exitFailures=0,
            exitUsedFallback=False,
            surfaceMovedAt=0.0,
            surfaceMoves=0,
            surfaceSets=0,
            arrivalWorld=None,
            arrivedAt=0.0,
            fallbackPending=False,
            discoveryMarkerMoved=False,
            discoveryAttachPending=False,
            landingChecks=0,
            vaultPodAutosaved=False,
            vaultSavingRelocked=False,
            vaultRecoveryTriggered=False,
            Game=SimpleNamespace(
                GetFormFromFile=get_form,
                GetPlayer=lambda: self.player,
                FadeOutGame=lambda *args: self.fades.append(args),
                SetInChargen=lambda *args: self.chargens.append(args),
                SetCharGenHUDMode=lambda m: self.huds.append(m),
                FastTravel=lambda target: (self.fast_travels.append(target), self.player.MoveTo(target, 0.0, 0.0, 0.0, True, False)),
            ),
            Debug=SimpleNamespace(OpenUserLog=lambda *_: None, Notification=lambda *_: None),
            Utility=SimpleNamespace(GetCurrentRealTime=lambda: self.now, Wait=lambda s: self.waits.append(s)),
            ExitMessage=SimpleNamespace(Show=exit_show),
            ExitFallbackMessage=SimpleNamespace(Show=fallback_show),
            EnsureVaultInteractivesRegistered=lambda: None,
            EnsureLoadHookRegistered=lambda *_: None,
            TriggerVaultPodRecoveryAutosave=lambda *_: None,
            PrepareArrivalMarkerDuringRide=lambda: None,
            CancelTimer=lambda tid: self.cancels.append(tid),
            ReadH00SuspectsOnce=lambda: None,
            ShowPausedExitLiftMenu=lambda *_: -1,
            SyncPipboyOwnedWornState=lambda *_: False,
            OpenLiftAttributeAllocation=lambda: None,
            OpenLiftCharacterRespec=lambda: None,
            RunSharedMapSetup=lambda: 4,
            StandsInVault=lambda p: p.GetParentCell() == self.vault_cell,
            RegisterForAnimationEvent=lambda *_: None,
            UnregisterForAnimationEvent=lambda *args: self.unregistrations.append(args),
            StartTimer=lambda *args: self.timers.append(args),
            GetStage=lambda: self.stage,
            AdvanceTo=advance_to,
        )
        exec(compile(translated_functions(read(PSC), self.EXIT_FUNCTIONS, self.EXIT_VARS), PSC, "exec"), self.ns)

    def assert_at_platform(self):
        self.assertTrue(self.player.interior)
        self.assertEqual(self.player.cell, self.vault_cell)
        self.assertAlmostEqual(self.player.pos[0], -77.742, places=3)
        self.assertAlmostEqual(self.player.pos[1], -3.958, places=3)
        self.assertAlmostEqual(self.player.pos[2], -1.551, places=3)
        self.assertTrue(self.ns["Near"](self.player, -77.742, -3.958, -1.751, 2.0))

    def test_b1_timeout_stepped_off_and_refused_play_each_return_to_platform_and_fourth_reaches_stage_40_by_fallback(self):
        # 1) Lift timeout: rider stays mid-shaft past LiftSeconds + 30 -> returns to platform, logs exit retry n=1, prompt ready again
        self.ns["InVault"](self.player, 30)
        self.assertEqual(self.exit_prompts, 1)
        self.assertTrue(self.ns["liftPairActive"])
        self.player.pos = (-77.742, -3.958, 8.0)  # mid-shaft
        self.now += 41.0
        self.ns["CheckPairedLiftRide"](self.player)
        self.assertFalse(self.ns["liftPairActive"])
        self.assertFalse(self.ns["asked"])
        self.assertEqual(self.ns["exitFailures"], 1)
        self.assert_at_platform()
        self.assertIn("exit retry n=1 reason=timeout stage=30", self.traces)

        # Prompt is offered again on the next InVault tick; 2) Rider stepped off platform before play -> exit retry n=2
        def step_off_during_register(*_):
            self.player.pos = (-72.0, -3.958, -1.72)  # stepped off onto catwalk (> 2 m from platform)

        self.ns["RegisterForAnimationEvent"] = step_off_during_register
        self.ns["InVault"](self.player, 30)
        self.assertEqual(self.exit_prompts, 2)
        self.assertFalse(self.ns["liftPairActive"])
        self.assertFalse(self.ns["asked"])
        self.assertEqual(self.ns["exitFailures"], 2)
        self.assertIn("exit retry n=2 reason=lift_rider_left_before_play stage=30", self.traces)
        self.ns["RegisterForAnimationEvent"] = lambda *_: None
        self.player.pos = (-77.742, -3.958, -1.551)

        # Prompt is offered again on the next InVault tick; 3) Refused Play01 -> exit retry n=3
        self.lift.accepted = False
        self.ns["InVault"](self.player, 30)
        self.assertEqual(self.exit_prompts, 3)
        self.assertFalse(self.ns["liftPairActive"])
        self.assertFalse(self.ns["asked"])
        self.assertEqual(self.ns["exitFailures"], 3)
        self.assertIn("exit retry n=3 reason=play_refused stage=30", self.traces)

        # Prompt is offered again on the 4th attempt; after 3 failures, offers plain way up -> logs exit fallback by=move -> stage 40!
        self.fallback_button = 0  # "Go up to the Commonwealth"
        self.ns["InVault"](self.player, 30)
        self.assertEqual(self.exit_prompts, 4)
        self.assertEqual(self.fallback_prompts, 1)
        self.assertIn("exit fallback by=move", self.traces)
        self.assertEqual(self.fades[-1], (True, True, 0.0, 0.2, False))
        self.assertGreater(self.ns["surfaceMovedAt"], 0.0)
        self.now += 1.0
        self.ns["FinishSurface"](self.player)
        self.assertEqual(self.stages, [40])
        self.assertEqual(self.stage, 40)

    def test_b1_rider_stepped_off_before_arrival_also_returns_to_platform_for_retry(self):
        self.ns["InVault"](self.player, 30)
        self.now += 10.0
        self.player.pos = (-77.742, -3.958, 19.88)
        self.ns["OnAnimationEvent"](self.lift, "Done")
        self.ns["UnregisterForAnimationEvent"] = lambda *args: (
            self.unregistrations.append(args),
            setattr(self.player, "pos", (-72.0, -3.958, 19.88)),
        )
        self.ns["CheckPairedLiftRide"](self.player)
        self.assertEqual(self.ns["exitFailures"], 1)
        self.assertFalse(self.ns["liftPairTransferred"])
        self.assertFalse(self.ns["asked"])
        self.assert_at_platform()
        self.assertIn("exit retry n=1 reason=lift_rider_left_before_arrival stage=30", self.traces)
        # Verify the prompt fires again immediately on the next InVault tick
        self.exit_button = 3  # Stay
        self.ns["InVault"](self.player, 30)
        self.assertEqual(self.exit_prompts, 2)

    def test_b1_reload_recovery_clears_mid_ride_returns_player_to_platform_and_restarts_timer(self):
        self.ns["InVault"](self.player, 30)
        self.assertTrue(self.ns["liftPairActive"])
        self.player.pos = (-77.742, -3.958, 11.5)  # stuck mid-shaft on save/reload
        self.timers.clear()
        self.ns["OnPlayerLoadGame"](self.player)
        self.assertFalse(self.ns["liftPairActive"])
        self.assertFalse(self.ns["liftPairTransferred"])
        self.assertFalse(self.ns["asked"])
        self.assertEqual(self.unregistrations, [(self.lift, "Done")])
        self.assert_at_platform()
        self.assertIn((1.0, 1), self.timers)
        self.assertTrue(any("lift_pair reload recovered dir=up stage=30" in t for t in self.traces), self.traces)

    def test_task0a_death_reload_surface_clears_save_lock_and_falls_back_via_core_anchor_or_fast_travel(self):
        # 1) When MoveTo(0x0A775B) succeeds (moves player exterior during Wait(0.25)), fallbacks stay idle.
        self.ns["vaultSavingRelocked"] = True
        self.ns["Surface"](self.player)
        self.assertFalse(self.ns["vaultSavingRelocked"])
        self.assertIn((False, False, False), self.chargens)
        self.assertIn(0, self.huds)
        self.assertEqual(self.exit_anchor.enables, [False])
        self.assertEqual(self.fast_travels, [])
        self.assertEqual(self.core_anchor.enables, [])

        # 2) Death-reload case A: MoveTo(0x0A775B) leaves player inside Vault 111 -> 0x000800 fallback moves player out -> stage 40!
        self.setUp()
        self.ns["vaultSavingRelocked"] = True
        self.player.take_move = False

        def core_only_move(target, dx=0.0, dy=0.0, dz=0.0, *rest):
            self.player.moveto_calls.append((target, dx, dy, dz))
            if target is self.core_anchor:
                self.player.world = self.surface_world
                self.player.cell = self.core_cell
                self.player.interior = False
                self.player.pos = (0.0, 0.0, 100.0)

        self.player.MoveTo = core_only_move
        self.ns["Surface"](self.player)
        self.assertFalse(self.ns["vaultSavingRelocked"])
        self.assertEqual(self.exit_anchor.enables, [False])
        self.assertEqual(self.core_anchor.enables, [])
        self.assertEqual(self.fast_travels, [])
        self.now += 11.0
        self.ns["FinishSurface"](self.player)
        self.now += 11.0
        self.ns["FinishSurface"](self.player)
        self.assertEqual(self.core_anchor.enables, [False])
        self.assertEqual(self.fast_travels, [])
        self.assertTrue(any(t.startswith("surface fallback anchor=") for t in self.traces), self.traces)
        self.ns["FinishSurface"](self.player)
        self.assertEqual(self.stages, [40])

        # 3) Death-reload case B: both 0x0A775B & 0x000800 leave player interior -> last-resort FastTravel(0x0008F2) instantiates exterior -> stage 40!
        self.setUp()
        self.ns["vaultSavingRelocked"] = True

        def ft_only_move(target, dx=0.0, dy=0.0, dz=0.0, *rest):
            self.player.moveto_calls.append((target, dx, dy, dz))
            if target is self.land_marker and target in self.fast_travels:
                self.player.world = self.surface_world
                self.player.cell = self.core_cell
                self.player.interior = False
                self.player.pos = (-1959.0, -493.0, 100.0)

        self.player.MoveTo = ft_only_move
        self.ns["Surface"](self.player)
        self.assertEqual(self.fast_travels, [])
        self.now += 11.0
        self.ns["FinishSurface"](self.player)
        self.now += 11.0
        self.ns["FinishSurface"](self.player)
        self.assertEqual(self.fast_travels, [self.land_marker])
        self.assertEqual(self.land_marker.enables, [False])
        self.assertEqual(self.land_marker.add_to_map_calls, [])
        self.assertEqual(self.land_marker.discovery_calls, 0)
        self.assertEqual(self.land_marker.enable_fast_travel_calls, [True])
        self.assertTrue(any(t.startswith("surface fallback last_resort fasttravel target=") for t in self.traces), self.traces)
        self.ns["FinishSurface"](self.player)
        self.assertEqual(self.stages, [40])

        # 4) Death-reload case C: 0x0008F2 absent -> FastTravel falls back to primary anchor 0x0A775B -> stage 40!
        self.setUp()
        self.land_marker = None

        def anchor_ft_move(target, dx=0.0, dy=0.0, dz=0.0, *rest):
            self.player.moveto_calls.append((target, dx, dy, dz))
            if target is self.exit_anchor and target in self.fast_travels:
                self.player.world = self.surface_world
                self.player.cell = self.core_cell
                self.player.interior = False
                self.player.pos = (-1275.3, 1305.3, 108.2)

        self.player.MoveTo = anchor_ft_move
        self.ns["Surface"](self.player)
        self.assertEqual(self.fast_travels, [])
        self.now += 11.0
        self.ns["FinishSurface"](self.player)
        self.now += 11.0
        self.ns["FinishSurface"](self.player)
        self.assertEqual(self.fast_travels, [self.exit_anchor])
        self.assertEqual(self.exit_anchor.add_to_map_calls, [])
        self.assertEqual(self.exit_anchor.discovery_calls, 0)
        self.assertEqual(self.exit_anchor.enable_fast_travel_calls, [True])
        self.ns["FinishSurface"](self.player)
        self.assertEqual(self.stages, [40])


class ArrivalReceiptTests(unittest.TestCase):
    def test_void_call_and_global_true_do_not_become_discovery_proof(self):
        result = ng.summarize([
            "FO4SF_NEWGAME rt=20 arrival discovery requested ref=V111 world=FF000123 fast_before=True fast_after=True",
            "FO4SF_NEWGAME rt=21 landed z=100 confirmed=True fallback=False world=FF000123",
            "FO4SF_NEWGAME rt=22 stage 200",
        ])
        self.assertIn("fast_before=True", result["arrival_discovery_requested"])
        self.assertNotIn("discovered", result)
        self.assertIsNone(result["exit_failure"])

    def test_failure_survives_a_later_stage_and_new_run_drops_old_success(self):
        result = ng.summarize([
            "FO4SF_NEWGAME rt=1 init old", "FO4SF_NEWGAME rt=2 stage 200",
            "FO4SF_NEWGAME rt=3 init new",
            "FO4SF_NEWGAME rt=4 exit failed reason=surface_position_not_confirmed stage=30",
            "FO4SF_NEWGAME rt=5 stage 200",
        ])
        self.assertTrue(result["earlier_completed"])
        self.assertIn("surface_position_not_confirmed", result["exit_failure"])
        self.assertIsNone(result["arrival_discovery_requested"])
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "failure.log"
            log.write_text("FO4SF_NEWGAME rt=4 exit failed reason=surface_position_not_confirmed stage=30\n"
                           "FO4SF_NEWGAME rt=5 stage 200\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ng.main(["log", "--file", str(log)]), 1)


class H00SurfaceSuspectIsolationTests(unittest.TestCase):
    """H00: 8 store globals isolate surface-arrival suspects in one session without rebuilding; LoadingMenu unregisters once mode is chosen."""

    def test_eight_suspects_log_once_per_ride_and_isolate_loading_actors_loot_discovery_and_setposition(self):
        from fo4sf.core.core_values import H00_SUSPECT_GLOB_EDIDS, core_form_id

        self.assertEqual(len(H00_SUSPECT_GLOB_EDIDS), 8)
        self.assertEqual([core_form_id(e) for e in H00_SUSPECT_GLOB_EDIDS], list(range(0x000890, 0x000898)))

        psc = read(PSC)
        ev_menu = re.search(r"Event OnMenuOpenCloseEvent\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        wrapped = psc + f"\nFunction MenuEvent({ev_menu[1]})\n{ev_menu[2]}EndFunction\n"

        traces, menu_regs, menu_unregs, fades, disabled_forms = [], [], [], [], []
        glob_vals = {fid: 0.0 for fid in range(0x000890, 0x000898)}
        world = object()
        player = Reference(world, (-1275.3, 1305.3, 119.4))
        anchor = Reference(world, (-1275.3, 1305.3, 119.4), form_id=0x030A775B)

        class _DisableableRef:
            def __init__(self, key):
                self.key = key
            def DisableNoWait(self, fade=False):
                disabled_forms.append(self.key)

        def get_form(fid, plg):
            if plg == "FO4SFCoreValues.esm" and fid in glob_vals:
                return SimpleNamespace(GetValue=lambda f=fid: glob_vals[f])
            if (fid, plg) == (0x0A775B, "FO4TerrainCore.esm"):
                return anchor
            if plg == "FO4SFMission.esm" or (plg == "FO4TerrainCore.esm" and fid in (0x016780, 0x016781)):
                return _DisableableRef((plg, fid))
            return None

        stages = []
        ns = dict(
            _PStr=_PStr,
            Trace=traces.append,
            faded=False, modeChoiceRan=False, warfareWaitingCreator=False,
            loadingMenuOpen=False, loadingMenuClosedSeen=False, loadingHookRegistered=False,
            h00SuspectsRead=False, h00SkipLoading=False, h00ClearChargen=False,
            h00SkipDiscovery=False, h00SkipMap=False, h00SkipLoot=False,
            h00SkipActors=False, h00SkipQuests=False, h00SkipSetPos=False,
            H00SkipLoadingHookGlobal=None, H00ClearChargenGlobal=None,
            H00SkipArrivalDiscoveryGlobal=None, H00SkipMapSetupGlobal=None,
            H00SkipRouteLootGlobal=None, H00SkipMissionActorsGlobal=None,
            H00SkipLandingQuestsGlobal=None, H00SkipSurfaceSetPosGlobal=None,
            RouteLootRefIds=[0x016780, 0x016781],
            ExitAnchorId=0x0A775B, ArrivalDiscoveryId=0x0A775B, CorePlugin="FO4TerrainCore.esm",
            LiftId=0x1618, ArrivalX=-1267.8, ArrivalY=1293.1, ArrivalZ=128.1, ArrivalHeading=0.0,
            MergeOffsetX=-1200.0, MergeOffsetY=-2700.0, FallbackX=-10.0, FallbackY=-20.0, FallbackZ=95.0,
            FallDrop=3.0, SurfaceWait=10.0, SurfaceTries=3,
            surfaceMoves=0, surfaceSets=0, surfaceMovedAt=0.0, arrivedAt=0.0,
            arrivalWorld=None, fallbackPending=False, discoveryMarkerMoved=False,
            discoveryAttachPending=False, landingChecks=0, rideMarkerPrepared=False, mapSetupDone=False,
            vaultSavingRelocked=False,
            CoreMarkerIds=[0x0A775B], MapMarkerQuestIds=[],
            Game=SimpleNamespace(
                GetFormFromFile=get_form,
                FadeOutGame=lambda *a: fades.append(a),
                SetInChargen=lambda *a: None,
                SetCharGenHUDMode=lambda *a: None,
                IsFastTravelEnabled=lambda: True,
                FastTravel=lambda *a: None,
            ),
            Utility=SimpleNamespace(GetCurrentRealTime=lambda: 20.0, Wait=lambda *a: None),
            CancelTimer=lambda *a: None,
            RegisterForMenuOpenCloseEvent=menu_regs.append,
            UnregisterForMenuOpenCloseEvent=menu_unregs.append,
            GetStage=lambda: stages[-1] if stages else 0,
            FailExit=lambda r: AssertionError(r),
            AdvanceTo=stages.append,
        )
        funcs = (
            "RegisterStartLoadingHook", "UnregisterStartLoadingHook", "ReadH00Glob", "BoolBit",
            "ReadH00SuspectsOnce", "ApplyH00PreSurfaceOverrides", "MenuEvent",
            "ClearVaultSaveLock", "TryFastTravelSurface", "TrySurfaceExteriorFallbacks",
            "Surface", "FinishSurface", "PrepareArrivalMarkerDuringRide",
            "PreAttachArrivalMarker", "RequestArrivalDiscovery", "RunSharedMapSetup",
        )
        vars_csv = (
            "faded, modeChoiceRan, warfareWaitingCreator, loadingMenuOpen, loadingMenuClosedSeen, "
            "loadingHookRegistered, h00SuspectsRead, h00SkipLoading, h00ClearChargen, h00SkipDiscovery, "
            "h00SkipMap, h00SkipLoot, h00SkipActors, h00SkipQuests, h00SkipSetPos, "
            "surfaceMoves, surfaceSets, surfaceMovedAt, arrivedAt, arrivalWorld, fallbackPending, "
            "discoveryMarkerMoved, discoveryAttachPending, landingChecks, rideMarkerPrepared, mapSetupDone, "
            "vaultSavingRelocked"
        )
        exec(compile(translated_functions(wrapped, funcs, vars_csv), PSC, "exec"), ns)

        # 1. Start-choice LoadingMenu hook registers at stage 0, then unregisters & ignores arrival LoadingMenu once modeChoiceRan/faded!
        ns["RegisterStartLoadingHook"]()
        self.assertEqual(menu_regs, ["LoadingMenu"])
        ns["modeChoiceRan"] = True
        ns["faded"] = True
        ns["MenuEvent"]("LoadingMenu", False)
        self.assertEqual(menu_unregs, ["LoadingMenu"])
        self.assertNotIn("mode loading menu closed", traces)

        # 2. Default (all 0.0) logs all 8 H00 globals ONCE and does not re-log on second call in the same ride
        ns["ReadH00SuspectsOnce"]()
        ns["ReadH00SuspectsOnce"]()
        h00_lines = [t for t in traces if t.startswith("h00 suspect ")]
        self.assertEqual(len(h00_lines), 8)
        self.assertTrue(all(t.endswith("=0") for t in h00_lines), h00_lines)

        # 3. Quicksave reload reset (h00SuspectsRead = False) + setting suspects by console isolates actors, loot, discovery, map, chargen & setpos
        traces.clear()
        ns["h00SuspectsRead"] = False
        for fid in (0x000891, 0x000892, 0x000893, 0x000894, 0x000895, 0x000897):
            glob_vals[fid] = 1.0
        ns["Surface"](player)
        h00_lines2 = [t for t in traces if t.startswith("h00 suspect ")]
        self.assertEqual(len(h00_lines2), 8)
        self.assertIn("h00 suspect FO4SF_H00_SkipMissionActors=1", h00_lines2)
        self.assertIn("h00 suspect FO4SF_H00_SkipRouteLoot=1", h00_lines2)
        self.assertIn("h00 cleared chargen and fade before surface", traces)
        # Codsworth (0x811) + Preston (0x802) + 8 Concord raiders (0x803..0x80A) + 2 RouteLoot refs disabled before MoveTo
        self.assertIn(("FO4SFMission.esm", 0x000811), disabled_forms)
        self.assertIn(("FO4SFMission.esm", 0x000802), disabled_forms)
        self.assertEqual(len([d for d in disabled_forms if d[0] == "FO4SFMission.esm"]), 10)
        self.assertEqual([d for d in disabled_forms if d[0] == "FO4TerrainCore.esm"], [("FO4TerrainCore.esm", 0x016780), ("FO4TerrainCore.esm", 0x016781)])
        self.assertEqual(ns["RunSharedMapSetup"](), 0)
        self.assertEqual(anchor.enables, [False])
        ns["PrepareArrivalMarkerDuringRide"]()
        self.assertEqual(anchor.enables, [False])

        # FinishSurface logs surface pre_setposition and skips SetPosition when FO4SF_H00_SkipSurfaceSetPos=1
        player.moves.clear()
        ns["FinishSurface"](player)
        self.assertEqual(player.moves, [])
        self.assertTrue(any(t.startswith("surface pre_setposition ") for t in traces), traces)
        self.assertTrue(any(t.startswith("h00 skipped surface setposition ") for t in traces), traces)
        self.assertEqual(stages, [40])


class ReturnLiftB3HopSpikeTests(unittest.TestCase):
    """B3 (candidate-2e in-game fix): FO4SF_MapMarkersHop reload hop must never falsely arm or trigger the Vault 111 return lift."""

    RETURN_FUNCTIONS = ("ResolveHostWorld", "CheckReturnLift", "Near")
    RETURN_VARS = (
        "arrivalWorld, leftArrivalPad, returnLiftArmed, returnArmTicks, "
        "returnHasExteriorSample, returnLastExteriorX, returnLastExteriorY, "
        "returnAsked, returnVaultAsked, returnSurfacePending, returnSurfaceWaitTicks, returnSurfaceTries"
    )

    def setUp(self):
        self.surface_world = object()
        self.core_cell = SimpleNamespace(GetFormID=lambda: 0x04000CF0)
        self.hop_cell = SimpleNamespace(GetFormID=lambda: 0x100008F4)
        self.vault_cell = SimpleNamespace(GetFormID=lambda: 0x020011F3)

        self.exit_anchor = Reference(self.surface_world, (-1275.3, 1305.3, 108.2), form_id=0x040A775B)
        self.exit_anchor.cell = self.core_cell
        self.vault_anchor = Reference(None, (-60.0, 0.0, -1.0), form_id=0x02000805)
        self.vault_anchor.interior = True
        self.vault_anchor.cell = self.vault_cell

        # Exact Vault 111 hilltop merged coordinates from candidate-2e (-2467.78, -1406.92, 127.45)
        self.pad_pos = (-2467.78, -1406.92, 127.45)
        self.player = Reference(self.surface_world, self.pad_pos, form_id=0x00000014)
        self.player.cell = self.core_cell

        self.traces = []
        self.return_prompts = 0
        self.return_button = 1  # Stay by default

        def get_form(fid, plg):
            if plg == "FO4TerrainCore.esm" and fid == 0x0A775B:
                return self.exit_anchor
            if plg == "FO4Port.esm" and fid == 0x805:
                return self.vault_anchor
            return None

        self.prompt_calls = []
        self.started_rides = []
        self.start_refuse = False

        def show_paused(player_arg, descending=False):
            self.return_prompts += 1
            self.prompt_calls.append(descending)
            return self.return_button

        def start_paired(player_arg, descending=False):
            self.started_rides.append((player_arg, descending))
            if self.start_refuse:
                self.traces.append(f"lift_pair refused reason=test_refused dir={'down' if descending else 'up'}")
                return False
            if descending:
                player_arg.MoveTo(self.vault_anchor, -17.742, -3.958, -0.551, False, False)
            return True

        self.ns = dict(
            _PStr=_PStr,
            Trace=self.traces.append,
            arrivalWorld=self.surface_world,
            ArrivalX=-1267.78,
            ArrivalY=1293.08,
            ArrivalZ=128.11,
            ArrivalHeading=0.0,
            MergeOffsetX=-1200.0,
            MergeOffsetY=-2700.0,
            PlatformX=-77.742,
            PlatformY=-3.958,
            PlatformZ=-1.751,
            PlatformRadius=2.0,
            AnchorX=-60.0,
            AnchorY=0.0,
            AnchorZ=-1.0,
            VaultPlugin="FO4Port.esm",
            VaultAnchorId=0x805,
            LiftId=0x1618,
            CorePlugin="FO4TerrainCore.esm",
            ExitAnchorId=0x0A775B,
            ActiveLiftPairId="fo4.vault111_exit",
            LiftPairIds=["fo4.vault111_exit"],
            SurfaceCogPadRadius=[3.2],
            leftArrivalPad=False,
            returnLiftArmed=False,
            returnArmTicks=0,
            returnHasExteriorSample=False,
            returnLastExteriorX=0.0,
            returnLastExteriorY=0.0,
            returnAsked=False,
            returnVaultAsked=False,
            returnSurfacePending=False,
            returnSurfaceWaitTicks=0,
            returnSurfaceTries=0,
            ShowPausedExitLiftMenu=show_paused,
            StartPairedLiftRide=start_paired,
            ExitMessage=SimpleNamespace(Show=lambda: (_ for _ in ()).throw(AssertionError("Starfield ExitMessage forbidden"))),
            ReturnMessage=SimpleNamespace(Show=lambda: (_ for _ in ()).throw(AssertionError("Starfield ReturnMessage forbidden"))),
            OpenLiftAttributeAllocation=lambda: None,
            StandsInVault=lambda p: p.GetParentCell() == self.vault_cell,
            Game=SimpleNamespace(GetFormFromFile=get_form),
        )
        exec(compile(translated_functions(read(PSC), self.RETURN_FUNCTIONS, self.RETURN_VARS), PSC, "exec"), self.ns)

    def test_b3_mapmarkers_hop_interior_and_99109_comeback_spike_never_arm_or_prompt(self):
        # 1. FO4SF_MapMarkersHop (100008F4) interior hop at (414.5, -268.3, -38.0)
        self.player.interior = True
        self.player.world = None
        self.player.cell = self.hop_cell
        self.player.pos = (414.5, -268.3, -38.0)
        self.ns["CheckReturnLift"](self.player)
        self.assertFalse(self.ns["returnLiftArmed"])
        self.assertFalse(self.ns["leftArrivalPad"])
        self.assertEqual(self.return_prompts, 0)

        # 2. Even if IsInInterior raced during VM yield while cell is still FO4SF_MapMarkersHop (100008F4), non-core cell is rejected
        self.player.interior = False
        self.player.world = object()
        self.player.cell = self.hop_cell
        self.player.pos = (414.5, -268.3, -38.0)
        self.ns["CheckReturnLift"](self.player)
        self.assertFalse(self.ns["returnLiftArmed"])
        self.assertEqual(self.return_prompts, 0)

        # 3. Exact candidate-2e ComeBack transient anchor spike: dist_sq = 99109.320312 (~314.816 m away in FO4TerrainCore) for 1 tick,
        #    followed by SetPosition snap back onto the Vault 111 hilltop (-2467.78, -1406.92, 127.45)
        self.player.interior = False
        self.player.world = self.surface_world
        self.player.cell = self.core_cell
        spike_dist = (99109.320312) ** 0.5
        self.player.pos = (-2467.78 + spike_dist, -1406.92, 106.5)
        self.ns["CheckReturnLift"](self.player)
        self.assertFalse(self.ns["returnLiftArmed"])
        self.assertEqual(self.ns["returnArmTicks"], 0)

        # Snap back onto hilltop pad and stay there across multiple stage-200 timer ticks
        self.player.pos = self.pad_pos
        for _ in range(5):
            self.ns["CheckReturnLift"](self.player)
        self.assertFalse(self.ns["returnLiftArmed"])
        self.assertFalse(self.ns["leftArrivalPad"])
        self.assertEqual(self.return_prompts, 0)
        self.assertFalse(any("return lift armed" in t for t in self.traces), self.traces)

    def test_b3_single_tick_sub200m_glitch_ignored_while_real_two_tick_walk_arms_and_prompts_on_return(self):
        # Single-tick 120 m exterior blip followed by snap-back does NOT arm (requires >= 2 consecutive valid ticks)
        self.player.pos = (-2347.0, -1406.0, 113.0)
        self.ns["CheckReturnLift"](self.player)
        self.assertEqual(self.ns["returnArmTicks"], 1)
        self.assertFalse(self.ns["returnLiftArmed"])

        self.player.pos = self.pad_pos
        self.ns["CheckReturnLift"](self.player)
        self.assertEqual(self.ns["returnArmTicks"], 0)
        self.assertFalse(self.ns["returnLiftArmed"])
        self.assertEqual(self.return_prompts, 0)

        # Real player walk > 12 m across 2 consecutive ticks arms the return lift
        self.player.pos = (-2450.0, -1406.92, 126.0)  # +17.78 m
        self.ns["CheckReturnLift"](self.player)
        self.assertFalse(self.ns["returnLiftArmed"])
        self.player.pos = (-2440.0, -1406.92, 125.0)  # +27.78 m
        self.ns["CheckReturnLift"](self.player)
        self.assertTrue(self.ns["returnLiftArmed"])
        self.assertTrue(self.ns["leftArrivalPad"])
        self.assertTrue(any("return lift armed dist_sq=" in t for t in self.traces), self.traces)

        # Walking back onto the hilltop pad now prompts green FO4SF_LiftMenu (descending=True) and calls StartPairedLiftRide(player, True)
        self.return_button = 0
        self.player.pos = self.pad_pos
        self.ns["CheckReturnLift"](self.player)
        self.assertEqual(self.return_prompts, 1)
        self.assertEqual(self.prompt_calls, [True])
        self.assertEqual(self.started_rides, [(self.player, True)])
        self.assertTrue(self.player.interior)
        self.assertEqual(self.player.cell, self.vault_cell)

    def test_g8_both_return_prompts_reach_start_paired_lift_ride_via_green_menu_and_reset_on_refusal(self):
        # 1) Vault return prompt uses green ShowPausedExitLiftMenu(player, False) and reaches StartPairedLiftRide(player, False)
        self.player.interior = True
        self.player.cell = self.vault_cell
        self.player.pos = (-77.742, -3.958, -1.751)
        self.return_button = 0
        self.ns["CheckReturnLift"](self.player)
        self.assertEqual(self.prompt_calls, [False])
        self.assertEqual(self.started_rides, [(self.player, False)])

        # 2) Hilltop prompt checks ~3.2 m cog pad radius without altering 2.0 m PlatformRadius and resets returnAsked on refusal
        self.player.interior = False
        self.player.world = self.surface_world
        self.player.cell = self.core_cell
        self.ns["returnLiftArmed"] = True
        self.ns["returnAsked"] = False
        self.start_refuse = True
        # At 2.6 m off center: outside 2.0 m PlatformRadius, inside 3.2 m CogPadRadius -> still prompts and attempts ride!
        self.player.pos = (self.pad_pos[0] + 2.6, self.pad_pos[1], self.pad_pos[2])
        self.ns["CheckReturnLift"](self.player)
        self.assertEqual(self.prompt_calls, [False, True])
        self.assertEqual(self.started_rides[-1], (self.player, True))
        self.assertFalse(self.ns["returnAsked"])  # reset on failure
        self.assertTrue(any("lift_pair refused reason=" in t for t in self.traces))

    def test_b3_legitimate_fast_travel_beyond_200m_arms_after_two_settled_ticks_at_destination(self):
        # > 200 m jump to Concord (-2015, -1700) does not arm on the jump tick itself, then arms after 2 settled ticks there
        self.player.pos = (-2015.0, -1700.0, 90.5)
        self.ns["CheckReturnLift"](self.player)
        self.assertFalse(self.ns["returnLiftArmed"])
        self.ns["CheckReturnLift"](self.player)
        self.assertFalse(self.ns["returnLiftArmed"])
        self.ns["CheckReturnLift"](self.player)
        self.assertTrue(self.ns["returnLiftArmed"])

    def test_b3_unauthored_runtime_ff_exterior_cells_in_arrival_world_still_arm_cleanly(self):
        # Unauthored exterior Commonwealth grid cells carry runtime temporary 0xFF00xxxx CELL FormIDs while keeping arrivalWorld
        self.player.cell = SimpleNamespace(GetFormID=lambda: 0xFF00A492)
        self.player.world = self.surface_world
        self.player.pos = (-2450.0, -1406.92, 126.0)
        self.ns["CheckReturnLift"](self.player)
        self.assertEqual(self.ns["returnArmTicks"], 1)
        self.assertFalse(self.ns["returnLiftArmed"])

        self.player.pos = (-2440.0, -1406.92, 125.0)
        self.ns["CheckReturnLift"](self.player)
        self.assertTrue(self.ns["returnLiftArmed"])

        self.assertTrue(self.ns["leftArrivalPad"])

        # Fallback when arrivalWorld is None resolves wantWorld from ExitAnchorId
        self.setUp()
        self.ns["arrivalWorld"] = None
        self.player.cell = SimpleNamespace(GetFormID=lambda: 0xFF00A492)
        self.player.world = self.surface_world
        self.player.pos = (-2450.0, -1406.92, 126.0)
        self.ns["CheckReturnLift"](self.player)
        self.player.pos = (-2440.0, -1406.92, 125.0)
        self.ns["CheckReturnLift"](self.player)
        self.assertTrue(self.ns["returnLiftArmed"])


class G7AndG12eLiftOrderAndFadeTests(unittest.TestCase):
    """Round 15 G7(a/b/c/d) & G12(e): top arrivals via StateB_Play/Play02 after fade-in, interior down state, retries, and LoadingMenu single-pass landing fade."""

    def _compile_harness(self):
        psc = read(PSC)
        ev_timer = re.search(r"Event OnTimer\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        ev_menu = re.search(r"Event OnMenuOpenCloseEvent\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        ev_anim = re.search(r"Event OnAnimationEvent\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        self.assertIsNotNone(ev_timer)
        self.assertIsNotNone(ev_menu)
        self.assertIsNotNone(ev_anim)
        wrapped = (
            psc
            + f"\nFunction TimerEvent({ev_timer[1]})\n{ev_timer[2]}EndFunction\n"
            + f"\nFunction MenuEvent({ev_menu[1]})\n{ev_menu[2]}EndFunction\n"
            + f"\nFunction AnimEvent({ev_anim[1]})\n{ev_anim[2]}EndFunction\n"
        )
        funcs = (
            "Surface", "FinishSurface", "CheckLanding", "FailExit", "ReturnPlayerToVaultPlatform", "ResetVaultExitLift",
            "ForceFadeIn", "CompleteLandingFadeIn", "ReleaseStoryLandingFade", "RegisterStartLoadingHook", "UnregisterStartLoadingHook",
            "SuppressMapMarkersDarkHold", "EnsurePipboyWristEquipped", "SyncPipboyOwnedWornState",
            "PairIndex", "EnsurePairCogStorage", "GetPairCogState", "SetPairCogState",
            "GetPairSurfaceCog", "SetPairSurfaceCog", "GetPairCogActivationReg", "SetPairCogActivationReg",
            "GetPairCogLogged", "SetPairCogLogged",
            "PairSurfaceCogLocalX", "PairSurfaceCogLocalY", "PairSurfaceCogLocalZ", "PairSurfaceCogPadRadius",
            "PairSurfaceLiftSeconds", "PairSurfaceLiftFadeAt", "PairSurfaceLiftDoneMargin",
            "PairSurfacePlayEvent", "PairSurfaceResetEvent", "PairSurfaceAscendClip",
            "PairSurfaceAscendSeconds", "PairSurfaceAscendRise", "PairCoreStaticCogBaseId",
            "EmitLiftPairArrived", "ResetSurfaceLiftCog", "EnsureSurfaceLiftCog", "PlaySurfaceCogRise", "FinishSurfaceCogRise",
            "HexFormId", "HexDigit",
            "FailPairedLift", "StartPairedLiftRide", "CheckPairedLiftRide", "RecoverPairedLiftOnLoad",
            "Near", "StandsInVault", "ApplyStage", "AdvanceTo", "ClearVaultSaveLock", "RelockVaultSaving",
            "RequestArrivalDiscovery", "TrySurfaceExteriorFallbacks", "ResolveHostWorld",
            "RunSharedMapSetup", "PrepareArrivalMarkerDuringRide",
            "TimerEvent", "MenuEvent", "AnimEvent",
        )
        vars_csv = (
            "faded, loadingHookRegistered, loadingMenuOpen, loadingMenuClosedSeen, "
            "landingLoadingMode, landingAwaitingFadeIn, landingFadeGuardRan, ascentGapStartedAt, "
            "surfaceFadeInDone, surfaceMovedAt, surfaceMoves, surfaceSets, arrivedAt, arrivalWorld, "
            "fallbackPending, discoveryMarkerMoved, discoveryAttachPending, landingChecks, asked, "
            "exitFailures, exitUsedFallback, applied, pendingStage, pendingStageBy, looksSetStage20, "
            "vaultSavingRelocked, modeChoiceRan, startUiReady, h00SuspectsRead, h00SkipLoading, "
            "h00ClearChargen, h00SkipDiscovery, h00SkipMap, h00SkipLoot, h00SkipActors, h00SkipQuests, "
            "h00SkipSetPos, mapSetupDone, rideMarkerPrepared, pipboyPickedUp, ticks"
        )
        return compile(translated_functions(wrapped, funcs, vars_csv), PSC, "exec")

    def _build_env(self):
        code = self._compile_harness()
        vault_world = object()
        surface_world = object()
        vault_cell = SimpleNamespace(GetFormID=lambda: 0x020011F3)
        core_cell = SimpleNamespace(GetFormID=lambda: 0x03000CF0)
        unmerged_cell = SimpleNamespace(GetFormID=lambda: 0xFF001122)

        class AnimRef(Reference):
            def __init__(self, world, cell, pos, form_id, base=None):
                super().__init__(world, pos, form_id=form_id)
                self.cell = cell
                self.interior = (world is vault_world)
                self.base = base
                self.plays = []
                self.accept_clips = True
                self.reject_clips = set()
                self.rotz = 0.0

            def GetBaseObject(self): return self.base
            def GetAngleZ(self): return self.rotz
            def PlayAnimation(self, clip):
                self.plays.append(clip)
                return self.accept_clips and clip not in self.reject_clips

        cog_base = object()
        lift_base = object()
        vault_anchor = AnimRef(vault_world, vault_cell, (-70.0, -3.0, -1.751), 0x02000805)
        exit_anchor = AnimRef(surface_world, unmerged_cell, (-1210.0, -2720.0, 95.0), 0x030A775B)
        interior_lift = AnimRef(vault_world, vault_cell, (-77.742, -3.958, -1.751), 0x02001618, base=lift_base)
        surface_cog = AnimRef(surface_world, core_cell, (-2475.5824, -1403.9297, 33.253544), 0xFF001234, base=cog_base)

        player = Reference(vault_world, (-77.742, -3.958, -1.751), form_id=0x14)
        player.interior = True
        player.cell = vault_cell
        player.items = {}
        player.GetItemCount = lambda item: player.items.get(item, 0)
        player.AddItem = lambda item, cnt=1, silent=True: player.items.__setitem__(item, player.items.get(item, 0) + cnt)
        player.on_set_position = lambda _pos: setattr(player, "cell", core_cell) if not player.interior else None

        pipboy_armor = object()
        pipboy_glob = SimpleNamespace(v=1.0, GetValue=lambda: pipboy_glob.v, SetValue=lambda val: setattr(pipboy_glob, "v", val))
        suppressed = []
        mm_quest = SimpleNamespace(CallFunction=lambda fn, _a=(): (suppressed.append(fn) if fn == "SuppressArrivalDarkHold" else None, 0)[1])
        mm_form = SimpleNamespace(CastAs=lambda name: mm_quest if name == "FO4SF_MapMarkers" else None)

        events, traces, fades, timers, cancels, custom_events, anim_regs, anim_unregs, menu_regs, menu_unregs = (
            [], [], [], [], [], [], [], [], [], []
        )
        now = [100.0]
        cur_stage = [30]

        def get_form(fid, plg):
            if (fid, plg) == (0x805, "FO4Port.esm"):
                return vault_anchor
            if (fid, plg) == (0x1618, "FO4Port.esm"):
                return interior_lift
            if (fid, plg) == (0x1619, "FO4Port.esm"):
                return lift_base
            if (fid, plg) == (0x0A775B, "FO4TerrainCore.esm"):
                return exit_anchor
            if (fid, plg) == (0x0A2D4B, "FO4TerrainCore.esm"):
                return cog_base
            if (fid, plg) == (0x000800, "FO4SFMapMarkers.esm"):
                return mm_form
            return None

        def find_closest(base, x, y, z, radius):
            if base is cog_base:
                dx = surface_cog.pos[0] - x
                dy = surface_cog.pos[1] - y
                dz = surface_cog.pos[2] - z
                if dx * dx + dy * dy + dz * dz <= radius * radius:
                    return surface_cog
            return None

        def fade_out(*args):
            fades.append(args)
            events.append(("fade", args[0]))

        orig_equip = player.EquipItem

        def track_equip(item, prevent=False, silent=False):
            events.append(("equip_wrist",))
            return orig_equip(item, prevent, silent)

        player.EquipItem = track_equip

        orig_play_cog = surface_cog.PlayAnimation

        def track_cog_play(clip):
            events.append(("cog_play", clip, player.pos[2]))
            return orig_play_cog(clip)

        surface_cog.PlayAnimation = track_cog_play

        ns = dict(
            _PStr=_PStr,
            Trace=lambda msg: traces.append(str(msg)),
            Utility=SimpleNamespace(GetCurrentRealTime=lambda: now[0], Wait=lambda dt: now.__setitem__(0, now[0] + dt)),
            Game=SimpleNamespace(
                GetPlayer=lambda: player,
                GetFormFromFile=get_form,
                FindClosestReferenceOfType=find_closest,
                ShowFirstPersonGeometry=lambda *_: None,
                FadeOutGame=fade_out,
                SetInChargen=lambda *_: None,
                SetCharGenHUDMode=lambda *_: None,
                IsFastTravelEnabled=lambda: True,
                FastTravel=lambda *_: None,
            ),
            InputEnableLayer=SimpleNamespace(Create=lambda: None),
            RegisterForMenuOpenCloseEvent=lambda m: menu_regs.append(m),
            UnregisterForMenuOpenCloseEvent=lambda m: menu_unregs.append(m),
            RegisterForAnimationEvent=lambda ref, ev: anim_regs.append((ref, ev)),
            UnregisterForAnimationEvent=lambda ref, ev: anim_unregs.append((ref, ev)),
            RegisterForRemoteEvent=lambda *_: None,
            UnregisterForRemoteEvent=lambda *_: None,
            SendCustomEvent=lambda name, args: custom_events.append((name, list(args))),
            StartTimer=lambda s, tid: timers.append((s, tid)),
            CancelTimer=lambda tid: cancels.append(tid),
            GetStage=lambda: cur_stage[0],
            DisableHandScanner=lambda: None,
            SetStage=lambda st: cur_stage.__setitem__(0, st),
            SetObjectiveDisplayed=lambda *_: None,
            SetObjectiveCompleted=lambda *_: None,
            SetActive=lambda *_: None,
            CompleteQuest=lambda: None,
            StartLandingQuests=lambda: None,
            RunPodExitHook=lambda *_: None,
            TriggerVaultPodRecoveryAutosave=lambda *_: None,
            applied=30,
            pendingStage=-1,
            pendingStageBy="other",
            looksSetStage20=False,
            mapSetupDone=False,
            rideMarkerPrepared=False,
            pipboyPickedUp=False,
            ticks=0,
            faded=True,
            surfaceMovedAt=0.0,
            surfaceMoves=0,
            surfaceSets=0,
            arrivedAt=0.0,
            arrivalWorld=None,
            fallbackPending=False,
            discoveryMarkerMoved=False,
            discoveryAttachPending=False,
            landingChecks=0,
            asked=False,
            exitFailures=0,
            exitUsedFallback=False,
            vaultSavingRelocked=False,
            modeChoiceRan=True,
            startUiReady=True,
            VaultPlugin="FO4Port.esm",
            VaultAnchorId=0x805,
            LiftId=0x1618,
            LiftBaseId=0x1619,
            PlatformX=-77.742,
            PlatformY=-3.958,
            PlatformZ=-1.751,
            PlatformRadius=2.0,
            AnchorX=-70.0,
            AnchorY=-3.0,
            AnchorZ=-1.751,
            CorePlugin="FO4TerrainCore.esm",
            ExitAnchorId=0x0A775B,
            ArrivalDiscoveryId=0,
            ArrivalX=-1275.5824,
            ArrivalY=1296.0703,
            ArrivalZ=33.253544,
            ArrivalHeading=180.0,
            FallbackX=-10.0,
            FallbackY=-20.0,
            FallbackZ=127.0,
            MergeOffsetX=-1200.0,
            MergeOffsetY=-2700.0,
            SurfaceWait=10.0,
            SurfaceTries=3,
            FallDrop=3.0,
            StartLoadTimeout=15.0,
            SinglePassLandingFade=True,
            PipboyWristArmor=pipboy_armor,
            PipboyAcquiredGlobal=pipboy_glob,
            MapMarkerQuestIds=[0x000800],
            CoreMarkerIds=[],
            LiftRise=21.6,
            LiftSeconds=9.8667,
            LiftResetSeconds=23.8333,
            LiftFadeLead=1.1,
            LiftDoneMargin=0.25,
            LiftPlayEvent="Play01",
            LiftResetEvent="Play02",
        )
        exec(code, ns)
        return SimpleNamespace(
            ns=ns,
            player=player,
            interior_lift=interior_lift,
            surface_cog=surface_cog,
            vault_world=vault_world,
            vault_cell=vault_cell,
            surface_world=surface_world,
            core_cell=core_cell,
            now=now,
            cur_stage=cur_stage,
            fades=fades,
            events=events,
            traces=traces,
            timers=timers,
            cancels=cancels,
            custom_events=custom_events,
            suppressed=suppressed,
            menu_regs=menu_regs,
            menu_unregs=menu_unregs,
        )

    def test_first_and_repeat_top_arrivals_rise_through_opening_hatches_and_interior_down_tracks_state(self):
        env = self._build_env()
        ns, player = env.ns, env.player

        # 1) First ride UP from Vault 111
        self.assertTrue(ns["StartPairedLiftRide"](player, False))
        self.assertEqual(ns["interiorLiftState"], "B")
        self.assertEqual(env.interior_lift.plays, ["Play01"])

        env.now[0] += 9.8
        player.pos = (-77.742, -3.958, -1.751 + 21.6)
        ns["AnimEvent"](env.interior_lift, "Done")
        ns["CheckPairedLiftRide"](player)
        self.assertEqual(env.suppressed, ["SuppressArrivalDarkHold"])
        self.assertIn("LoadingMenu", env.menu_regs)
        self.assertTrue(any(f[0] is True for f in env.fades))

        # Exterior FinishSurface: places rider at ArrivalZ - 25.9932, lifts fade, equips wrist, THEN plays StateB_Play!
        env.now[0] += 0.3
        ns["FinishSurface"](player)
        self.assertEqual(env.cur_stage[0], 40)
        self.assertAlmostEqual(player.pos[2], 33.253544 - 25.9932, places=3)
        self.assertIn("story_fade single_pass=true path=immediate loading_menu_open=False", env.traces)
        self.assertTrue(any(t.startswith("ascent gap_ms=") for t in env.traces))
        self.assertTrue(any(t.startswith("lift_pair surface_cog state=A player_z=7.2603") for t in env.traces), env.traces)
        self.assertEqual(env.surface_cog.plays, ["StateB_Play"])

        # Ordering check: fade lifted -> wrist equipped -> cog rise started
        fade_in_idx = max(i for i, e in enumerate(env.events) if e == ("fade", False))
        equip_idx = env.events.index(("equip_wrist",))
        cog_play_idx = next(i for i, e in enumerate(env.events) if e[0] == "cog_play")
        self.assertLess(fade_in_idx, equip_idx)
        self.assertLess(equip_idx, cog_play_idx)

        # While StateB_Play is still rising, CheckLanding must NOT fall-rescue or finish stage 200!
        ns["CheckLanding"](player)
        self.assertEqual(env.cur_stage[0], 40)
        self.assertFalse(ns["fallbackPending"])

        # Complete cog rise via Done -> player at top -> FallDrop check passes -> stage 200
        env.now[0] += 11.7
        player.pos = (-2475.5824, -1403.9297, 33.253544)
        ns["AnimEvent"](env.surface_cog, "Done")
        ns["CheckLanding"](player)
        self.assertFalse(ns["surfaceCogRising"])
        self.assertEqual(ns["GetPairCogState"]("fo4.vault111_exit"), "A")
        env.now[0] += 0.3
        ns["CheckLanding"](player)
        self.assertEqual(env.cur_stage[0], 200)

        # 2) Ride DOWN: cog plays Play01 (state -> "B"); because interiorLiftState == "B", places on raised platform and rides Play02 down!
        env.fades.clear()
        self.assertTrue(ns["StartPairedLiftRide"](player, True))
        self.assertEqual(ns["GetPairCogState"]("fo4.vault111_exit"), "B")
        self.assertEqual(env.surface_cog.plays, ["StateB_Play", "Play01"])

        env.now[0] += 18.6
        player.pos = (-2475.5824, -1403.9297, 25.0)
        ns["AnimEvent"](env.surface_cog, "Done")
        ns["CheckPairedLiftRide"](player)
        self.assertTrue(player.interior)
        self.assertAlmostEqual(player.pos[2], -1.751 + 21.6 + 0.2, places=3)

        # First interior tick places rider at raised platform, lifts fade, plays Play02
        ns["CheckPairedLiftRide"](player)
        self.assertFalse(env.fades[-1][0])
        self.assertTrue(ns["interiorLiftDescending"])
        self.assertEqual(env.interior_lift.plays, ["Play01", "Play02"])

        # Interior Play02 completes -> interiorLiftState returns to "A", NO extra ResetVaultExitLift after landing!
        env.now[0] += 23.8
        player.pos = (-77.742, -3.958, -1.751 + 0.2)
        ns["AnimEvent"](env.interior_lift, "Done")
        ns["CheckPairedLiftRide"](player)
        self.assertFalse(ns["interiorLiftDescending"])
        self.assertEqual(ns["interiorLiftState"], "A")
        self.assertEqual(env.interior_lift.plays, ["Play01", "Play02"])
        self.assertTrue(any("lift_pair ride arrived dir=down" in t for t in env.traces))

        # 3) Repeat ride UP (cog state == "B"): arrives at ArrivalZ - 25.9932, lifts fade, plays Play02!
        env.traces.clear()
        env.events.clear()
        self.assertTrue(ns["StartPairedLiftRide"](player, False))
        self.assertEqual(ns["interiorLiftState"], "B")
        env.now[0] += 9.8
        player.pos = (-77.742, -3.958, -1.751 + 21.6)
        ns["AnimEvent"](env.interior_lift, "Done")
        ns["CheckPairedLiftRide"](player)
        env.now[0] += 0.2
        ns["FinishSurface"](player)
        self.assertTrue(any(t.startswith("lift_pair surface_cog state=B player_z=7.2603") for t in env.traces), env.traces)
        self.assertEqual(env.surface_cog.plays, ["StateB_Play", "Play01", "Play02"])
        env.now[0] += 11.7
        player.pos = (-2475.5824, -1403.9297, 33.253544)
        ns["AnimEvent"](env.surface_cog, "Done")
        ns["CheckPairedLiftRide"](player)
        self.assertEqual(ns["GetPairCogState"]("fo4.vault111_exit"), "A")
        self.assertEqual(env.custom_events[-1][0], "LiftPairArrived")
        self.assertEqual(env.custom_events[-1][1][1], "up")

    def test_loading_menu_close_and_2s_guard_and_down_never_lowers_when_already_at_floor(self):
        # Case A: LoadingMenu is open at FinishSurface, then closes -> fade lifts, wrist equips, cog rises
        env = self._build_env()
        ns, player = env.ns, env.player
        ns["StartPairedLiftRide"](player, False)
        env.now[0] += 9.8
        player.pos = (-77.742, -3.958, -1.751 + 21.6)
        ns["AnimEvent"](env.interior_lift, "Done")
        ns["CheckPairedLiftRide"](player)
        ns["MenuEvent"]("LoadingMenu", True)
        ns["FinishSurface"](player)
        self.assertTrue(ns["landingAwaitingFadeIn"])
        self.assertFalse(ns["surfaceFadeInDone"])
        self.assertIn((2.0, 5), env.timers)
        self.assertEqual(env.surface_cog.plays, [])
        self.assertNotIn(("equip_wrist",), env.events)

        ns["MenuEvent"]("LoadingMenu", False)
        self.assertTrue(ns["surfaceFadeInDone"])
        self.assertIn(5, env.cancels)
        self.assertIn("story_fade single_pass=true path=loading_close loading_menu_open=False", env.traces)
        self.assertEqual(env.surface_cog.plays, ["StateB_Play"])
        # Subsequent guard Timer 5 does nothing (keyed off loadingMenuClosedSeen!)
        fades_before = len(env.fades)
        ns["TimerEvent"](5)
        self.assertEqual(len(env.fades), fades_before)

        # Case B: LoadingMenu never closes -> 2 s guard runs AT MOST ONCE (no unconditional re-assert pulse)
        env2 = self._build_env()
        ns2, p2 = env2.ns, env2.player
        ns2["StartPairedLiftRide"](p2, False)
        env2.now[0] += 9.8
        p2.pos = (-77.742, -3.958, -1.751 + 21.6)
        ns2["AnimEvent"](env2.interior_lift, "Done")
        ns2["CheckPairedLiftRide"](p2)
        ns2["MenuEvent"]("LoadingMenu", True)
        ns2["FinishSurface"](p2)
        fades_pre_guard = len(env2.fades)
        ns2["TimerEvent"](5)
        self.assertTrue(ns2["surfaceFadeInDone"])
        self.assertIn("story_fade single_pass=true path=guard loading_menu_open=True", env2.traces)
        self.assertEqual(len(env2.fades), fades_pre_guard + 1)
        self.assertEqual(env2.surface_cog.plays, ["StateB_Play"])
        # Firing Timer 5 again does NOT pulse fade again!
        ns2["TimerEvent"](5)
        self.assertEqual(len(env2.fades), fades_pre_guard + 1)

        # Case C: Ride down when interiorLiftState == "A" NEVER calls Play02 after landing
        env3 = self._build_env()
        ns3, p3 = env3.ns, env3.player
        ns3["cur_stage"] = 200
        env3.cur_stage[0] = 200
        ns3["interiorLiftState"] = "A"
        p3.interior = False
        p3.world = env3.surface_world
        p3.cell = env3.core_cell
        p3.pos = (-2475.5824, -1403.9297, 33.253544)
        self.assertTrue(ns3["StartPairedLiftRide"](p3, True))
        env3.now[0] += 18.6
        p3.pos = (-2475.5824, -1403.9297, 25.0)
        ns3["AnimEvent"](env3.surface_cog, "Done")
        ns3["CheckPairedLiftRide"](p3)
        ns3["CheckPairedLiftRide"](p3)
        self.assertEqual(env3.interior_lift.plays, [])
        self.assertAlmostEqual(p3.pos[2], -1.751 + 0.2, places=3)
        self.assertFalse(env3.fades[-1][0])

    def test_down_retry_cap_up_timeout_and_every_abort_lifts_fade(self):
        # 1) Down transfer retries cap at 3, log lift_pair transfer retry n=<n>, then FailPairedLift lifts fade & returns to surface cog pad
        env = self._build_env()
        ns, player = env.ns, env.player
        env.cur_stage[0] = 200
        player.interior = False
        player.world = env.surface_world
        player.cell = env.core_cell
        player.pos = (-2475.5824, -1403.9297, 33.253544)
        player.take_move = False  # Simulate down MoveTo stuck outside!
        self.assertTrue(ns["StartPairedLiftRide"](player, True))
        env.now[0] += 18.6
        player.pos = (-2475.5824, -1403.9297, 25.0)
        ns["AnimEvent"](env.surface_cog, "Done")
        ns["CheckPairedLiftRide"](player)
        for expected_n in (1, 2, 3):
            env.now[0] += 20.0
            ns["CheckPairedLiftRide"](player)
            self.assertIn(f"lift_pair transfer retry n={expected_n}", env.traces)
        # 4th timeout fails & lifts fade & returns player to surface pad
        env.now[0] += 6.0
        ns["CheckPairedLiftRide"](player)
        self.assertIn("lift_pair fail reason=down_transfer_timeout", env.traces)
        self.assertFalse(env.fades[-1][0])
        self.assertAlmostEqual(player.pos[0], -2475.5824, places=2)
        self.assertAlmostEqual(player.pos[2], 33.253544, places=2)

        # 2) Pending up transfer timeout > SurfaceWait * 3.0 lifts fade and returns rider to start pad
        env2 = self._build_env()
        ns2, p2 = env2.ns, env2.player
        ns2["StartPairedLiftRide"](p2, False)
        p2.take_move = False
        env2.now[0] += 9.8
        p2.pos = (-77.742, -3.958, -1.751 + 21.6)
        ns2["AnimEvent"](env2.interior_lift, "Done")
        ns2["CheckPairedLiftRide"](p2)
        self.assertTrue(any(f[0] is True for f in env2.fades))
        env2.now[0] += 35.0
        ns2["FinishSurface"](p2)
        self.assertIn("exit retry n=1 reason=lift_surface_timeout stage=30", env2.traces)
        self.assertFalse(env2.fades[-1][0])
        self.assertAlmostEqual(p2.pos[2], -1.751 + 0.2, places=2)

        # 3) Every abort path (cell_changed, world_changed, timeout, play_refused, RecoverPairedLiftOnLoad) ends with fade lifted!
        for reason in ("cell_changed", "world_changed", "timeout", "play_refused", "reload"):
            env_a = self._build_env()
            ns_a, pa = env_a.ns, env_a.player
            ns_a["liftPairFadeStarted"] = True
            env_a.fades.append((True, True, 0.0, 1.0, True))
            if reason == "play_refused":
                env_a.interior_lift.accept_clips = False
                ns_a["StartPairedLiftRide"](pa, False)
            elif reason == "reload":
                ns_a["liftPairActive"] = True
                ns_a["RecoverPairedLiftOnLoad"](pa)
            else:
                ns_a["FailPairedLift"](reason)
            self.assertFalse(env_a.fades[-1][0], f"Abort {reason} left fade down!")



if __name__ == "__main__":
    unittest.main()
