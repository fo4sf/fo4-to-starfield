"""Synthetic execution of the production arrival branches with native calls substituted.

This small translator executes only the straight-line/if Papyrus functions below. It is
not a Papyrus compiler or native-engine model; native placement/discovery remain PC gates.
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


FUNCTIONS = ("FinishSurface", "CheckLanding", "RequestArrivalDiscovery", "AtArrival", "Near")
VARIABLES = "arrivalWorld, surfaceSets, surfaceMovedAt, arrivedAt, fallbackPending, discoveryMarkerMoved, landingChecks"


def translated_functions(text, names=FUNCTIONS, variables=VARIABLES):
    out = []
    for name in names:
        match = re.search(rf"(?m)^(?:bool )?Function {name}\(([^)]*)\)\n(.*?)^EndFunction", text, re.S)
        args, body = match.groups()
        out += [f"def {name}({', '.join(a.split()[-1] for a in args.split(',') if a.strip())}):",
                "    global " + variables]
        depth = 1
        body = re.sub(r"\{.*?\}", "", body, flags=re.S)
        for line in body.splitlines():
            line = line.split(";", 1)[0].strip()
            if not line:
                continue
            if line.startswith("Trace("):
                line = "pass"
            if line == "endif":
                depth -= 1
                continue
            if line.startswith(("elseif ", "else")):
                depth -= 1
            line = re.sub(r"\b(?:bool|float|int|WorldSpace|Cell|Form|ObjectReference) (\w+) =", r"\1 =", line)
            line = re.sub(r" as ObjectReference\b", "", line)
            line = re.sub(r"\btrue\b", "True", line, flags=re.I)
            line = re.sub(r"\bfalse\b", "False", line, flags=re.I)
            line = re.sub(r"!(?!=)", "not ", line).replace("&&", "and").replace("||", "or")
            line = line.replace(" / 16777216", " // 16777216")
            if line.startswith("elseif "):
                line = "elif " + line[7:]
            if line.startswith(("if ", "elif ")) or line == "else":
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
        self.discovery_calls = 0

    def GetWorldSpace(self): return self.world
    def GetParentCell(self): return self.cell
    def GetFormID(self): return self.form_id
    def GetPositionX(self): return self.pos[0]
    def GetPositionY(self): return self.pos[1]
    def GetPositionZ(self): return self.pos[2]
    def Is3DLoaded(self): return self.loaded
    def IsInInterior(self): return self.interior
    def SetAngle(self, *args): pass

    def Enable(self, fade=False):
        self.enables.append(fade)

    def MoveTo(self, target, dx=0.0, dy=0.0, dz=0.0, match_rot=False, match_dead=False):
        self.moveto_calls.append((target, dx, dy, dz))
        if self.take_move:
            self.world = target.GetWorldSpace()
            self.pos = (target.GetPositionX() + dx, target.GetPositionY() + dy, target.GetPositionZ() + dz)

    def SetPosition(self, *pos):
        self.moves.append(pos)
        if self.take_position:
            self.pos = pos
            if self.on_set_position is not None:
                self.on_set_position(pos)

    def SetMarkerDiscovered(self):
        self.discovery_calls += 1


class ArrivalExecutionTests(unittest.TestCase):
    def setUp(self):
        self.world = object()  # runtime MarsPlanetWorld (0xFF......) differs from FO4Core_Commonwealth (0x03000803)
        self.player = Reference(self.world, (-1200.0, -2700.0, 100.0))
        self.marker = Reference(self.world, (-1210.0, -2720.0, 95.0))
        self.failures, self.stages = [], []
        self.now = 10.0
        self.ns = dict(arrivalWorld=self.world, ArrivalX=0.0, ArrivalY=0.0, ArrivalZ=100.0,
                       ArrivalHeading=0.0, MergeOffsetX=-1200.0, MergeOffsetY=-2700.0,
                       FallbackX=-10.0, FallbackY=-20.0, FallbackZ=95.0, FallDrop=3.0,
                       ExitAnchorId=0x0A775B, ArrivalDiscoveryId=0x0A775B, CorePlugin="FO4TerrainCore.esm",
                       SurfaceWait=10.0, SurfaceTries=3, surfaceMoves=1, surfaceSets=0,
                       surfaceMovedAt=1.0, arrivedAt=1.0, fallbackPending=False,
                       discoveryMarkerMoved=False, landingChecks=0,
                       Game=SimpleNamespace(GetFormFromFile=lambda *_: self.marker, IsFastTravelEnabled=lambda: True),
                       Utility=SimpleNamespace(GetCurrentRealTime=lambda: self.now),
                       FailExit=self.failures.append, AdvanceTo=self.stages.append)
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
        self.run_branch("CheckLanding")  # still within the three-second settling interval
        self.assertEqual(self.marker.discovery_calls, 0)
        self.now += 3.0
        self.run_branch("CheckLanding")
        self.assertEqual(self.marker.discovery_calls, 1)
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

    def test_ignored_fallback_cannot_complete(self):
        self.player.pos = (-1200.0, -2700.0, 90.0)
        self.player.take_position = False
        self.run_branch("CheckLanding")
        self.run_branch("CheckLanding")
        self.assertEqual(self.failures, ["landing_position_not_confirmed"])
        self.assertEqual(self.marker.discovery_calls, 0)
        self.assertEqual(self.stages, [])

    def test_same_coordinates_in_wrong_player_world_cannot_discover(self):
        self.player.world = object()
        self.run_branch("CheckLanding")
        self.assertEqual(self.failures, ["landing_world_changed"])
        self.assertEqual(self.marker.discovery_calls, 0)

    def test_unattached_or_misplaced_marker_that_refuses_move_has_bounded_wait(self):
        for world, pos in [(None, self.marker.pos), (object(), self.marker.pos),
                           (self.world, (0.0, 0.0, 95.0))]:
            with self.subTest(world=world, pos=pos):
                self.setUp()
                self.marker.world, self.marker.pos = world, pos
                self.marker.take_move = False
                self.marker.take_position = False
                self.ns["landingChecks"] = 29
                self.run_branch("CheckLanding")
                self.assertEqual(self.failures, ["arrival_marker_not_attached"])
                self.assertEqual(len(self.marker.moveto_calls), 1)
                self.assertEqual(self.marker.discovery_calls, 0)
                self.assertEqual(self.stages, [])

    def test_indoor_unloaded_and_wrong_height_never_request_discovery(self):
        for field, value in [("interior", True), ("loaded", False), ("pos", (-1200.0, -2700.0, 110.0))]:
            with self.subTest(field=field):
                old = getattr(self.player, field)
                setattr(self.player, field, value)
                self.run_branch("CheckLanding")
                self.assertEqual(self.marker.discovery_calls, 0)
                self.assertEqual(self.stages, [])
                setattr(self.player, field, old)

    def test_leaving_during_marker_reads_prevents_the_call(self):
        def fast_read():
            self.player.pos = (1000.0, 1000.0, 100.0)
            return True
        self.ns["Game"].IsFastTravelEnabled = fast_read
        self.run_branch("CheckLanding")
        self.assertEqual(self.marker.discovery_calls, 0)
        self.assertEqual(self.stages, [])

    def test_custom_exit_discovery_is_disabled_and_writer_pins_canonical_marker(self):
        self.ns["ArrivalDiscoveryId"] = 0
        self.run_branch("CheckLanding")
        self.assertEqual(self.marker.discovery_calls, 0)
        self.assertEqual(self.stages, [200])
        self.assertIn('("ArrivalDiscoveryId", o.ExitAnchor == ExitAnchorEdid ? (int)p.ExitAnchor : 0)', read(CS))
        code = re.sub(r"\{.*?\}|;[^\n]*", "", read(PSC), flags=re.S)
        self.assertEqual(code.count(".SetMarkerDiscovered()"), 1)
        self.assertNotIn(".AddToMap(", code)


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


if __name__ == "__main__":
    unittest.main()
