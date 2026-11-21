"""Execute the actual evidence functions with changing native-read substitutes.

The tiny straight-line/if translator below checks log arithmetic and Done's guard,
not Papyrus compilation, atomic engine reads, actor physics or walkability.
"""
from collections import Counter
import re
from types import SimpleNamespace
import unittest

from tests.test_newgame import LOOKS, PSC, ng, read


def execute_functions(text, names, ns):
    translated = []
    for name in names:
        match = re.search(rf"(?m)^Function {name}\(([^)]*)\)\n(.*?)^EndFunction", text, re.S)
        args, body = match.groups()
        translated += [f"def {name}({', '.join(a.split()[-1] for a in args.split(',') if a.strip())}):",
                       "    global podChecked"]
        depth = 1
        for line in re.sub(r"\{.*?\}", "", body, flags=re.S).splitlines():
            line = line.split(";", 1)[0].strip()
            if not line:
                continue
            if line == "endif":
                depth -= 1
                continue
            line = re.sub(r"^(?:float|bool|int|Actor|Cell|WorldSpace) (\w+) =", r"\1 =", line)
            line = re.sub(r"\btrue\b", "True", line, flags=re.I)
            line = re.sub(r"\bfalse\b", "False", line, flags=re.I)
            line = line.replace("&&", "and").replace("||", "or")
            if line.startswith("Trace("):
                # All trace operands in these functions are literals/cached scalars.
                # Papyrus concatenates them as text; Python needs explicit coercion.
                operands = re.split(r"\s+\+\s+", line[len("Trace("):-1])
                line = "record([" + ", ".join(operands) + "])"
            if line.startswith("if "):
                translated.append("    " * depth + line + ":")
                depth += 1
            else:
                translated.append("    " * depth + line)
        if depth != 1:
            raise AssertionError(f"unbalanced source: {name}")
    exec(compile("\n".join(translated), "pod-evidence-functions", "exec"), ns)


class ChangingActor:
    """A second reading deliberately returns a different coordinate."""
    def __init__(self):
        self.calls = Counter()

    def coordinate(self, axis, first):
        self.calls[axis] += 1
        return first + 100 * (self.calls[axis] - 1)

    def GetPositionX(self): return self.coordinate("x", 9.6)
    def GetPositionY(self): return self.coordinate("y", -3.2)
    def GetPositionZ(self): return self.coordinate("z", 0.9)
    def GetAngleZ(self): return 270.0
    def Is3DLoaded(self): return True
    def GetParentCell(self): return "Vault111Cryo"
    def GetWorldSpace(self): return None


class PodEvidenceTests(unittest.TestCase):
    def namespace(self, stage=10):
        self.player = ChangingActor()
        self.logs, self.stages = [], []
        self.times = iter((100.0, 100.8))
        ns = dict(podChecked=False, PodX=9.14, PodY=-3.11, PodZ=-1.03, PodLift=0.3,
                  PodRadius=1.0, PodDrop=0.5, current_stage=stage,
                  Utility=SimpleNamespace(GetCurrentRealTime=lambda: next(self.times)),
                  Game=SimpleNamespace(GetPlayer=lambda: self.player),
                  record=lambda operands: self.logs.append("".join(map(str, operands))))
        ns["GetStage"] = lambda: ns["current_stage"]
        def set_stage(n):
            ns["current_stage"] = n
            self.stages.append(n)
        ns["SetStage"] = set_stage
        return ns

    def test_settle_deltas_and_printed_position_use_the_same_readings(self):
        ns = self.namespace()
        execute_functions(read(PSC), ("CheckPod",), ns)
        ns["CheckPod"](self.player)
        self.assertTrue(ns["podChecked"])
        self.assertEqual(self.player.calls, dict(x=1, y=1, z=1))
        line = self.logs[0]
        pos = list(map(float, re.search(r"pos=(.*?) dx=", line)[1].split()))
        target = list(map(float, re.search(r"target=(.*?) heading=", line)[1].split()))
        dx, dy, drop = (float(re.search(rf"\b{key}=([^ ]+)", line)[1]) for key in ("dx", "dy", "drop"))
        self.assertAlmostEqual(dx, pos[0] - target[0])
        self.assertAlmostEqual(dy, pos[1] - target[1])
        self.assertAlmostEqual(drop, target[2] - pos[2])
        self.assertIn("ok=True", line)  # historical threshold unchanged; high is not a walkability pass
        self.assertIn("sample_start=100.0 sample_end=100.8", line)
        for field in ("heading=270.0", "loaded=True", "cell=Vault111Cryo", "world=None"):
            self.assertIn(field, line)

    def test_looks_sample_is_bounded_and_reads_each_coordinate_once(self):
        ns = self.namespace()
        execute_functions(read(LOOKS), ("TracePosition",), ns)
        ns["TracePosition"]("before creator")
        self.assertEqual(self.player.calls, dict(x=1, y=1, z=1))
        self.assertEqual(self.logs, ["looks position phase=before creator pos=9.6 -3.2 0.9 heading=270.0 "
                                     "loaded=True cell=Vault111Cryo world=None stage=10 "
                                     "sample_start=100.0 sample_end=100.8"])

    def test_done_keeps_reason_and_stage_order_and_ignores_duplicate_close(self):
        for how in ("creator closed", "quick start"):
            with self.subTest(how=how):
                ns = self.namespace()
                execute_functions(read(LOOKS), ("TracePosition", "Done"), ns)
                ns["Done"](how)
                self.assertIn(f"phase=done: {how} ", self.logs[0])
                self.assertEqual(self.logs[1:], [f"looks done: {how}", "stage 20"])
                self.assertEqual(self.stages, [20])
                ns["Done"](how)  # would exhaust both native-read time values if not guarded
                self.assertEqual(len(self.logs), 3)
                self.assertEqual(self.player.calls, dict(x=1, y=1, z=1))

    def test_new_traces_do_not_change_movement_or_creator_routing(self):
        quest, looks = read(PSC), read(LOOKS)
        check = re.search(r"(?ms)^Function CheckPod\(.*?^EndFunction", quest)[0]
        sample = re.search(r"(?ms)^Function TracePosition\(.*?^EndFunction", looks)[0]
        for text in (check, sample):
            for call in ("MoveTo(", "SetPosition(", "SetAngle(", "Wait(", "SetInChargen(", "SetGhost("):
                self.assertNotIn(call, text)
        self.assertEqual(quest.count("CheckPod(player)"), 1)
        self.assertLess(looks.index('TracePosition("before creator")'), looks.index("        Game.ShowRaceMenu("))
        quick = looks[looks.index("if button == 1"):looks.index("RegisterForMenuOpenCloseEvent(MenuName)")]
        self.assertIn('Done("quick start")', quick)
        self.assertIn("return", quick)
        self.assertNotIn("TracePosition", quick)  # Done supplies its sole boundary sample

    def test_summary_preserves_all_samples_from_latest_run_only(self):
        def log(msg): return "[x] FO4SF_NEWGAME rt=1.0 " + msg
        lines = [log("init old"), log("looks position phase=done: creator closed pos=OLD"),
                 log("init current"), log("looks position phase=before creator pos=NEW"),
                 log("looks position phase=done: creator closed pos=NEWER"),
                 log("looks position phase=done: creator closed pos=DUPLICATE")]
        self.assertEqual(ng.summarize(lines)["looks_positions"], [
            "phase=before creator pos=NEW", "phase=done: creator closed pos=NEWER",
            "phase=done: creator closed pos=DUPLICATE"])

    def test_older_and_no_looks_fallback_logs_have_no_invented_boundary_samples(self):
        for ending in ("creator closed", "LooksWait fallback after 300.0 s"):
            summary = ng.summarize(["[x] FO4SF_NEWGAME rt=1.0 init current",
                                    "[x] FO4SF_NEWGAME rt=2.0 looks done: " + ending])
            self.assertEqual(summary["looks_done"], ending)
            self.assertEqual(summary["looks_positions"], [])


if __name__ == "__main__":
    unittest.main()
