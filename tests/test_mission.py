"""The cut-down "When Freedom Calls" mission: the contract between dotnet/Mission (the plugin), FO4SF_Min00Quest.psc (the
quest script) and make_mission.py (staging and the log reader). Synthetic only; the C# writer's own self-test runs when
a dotnet SDK is on PATH (dotnet/Mission selftest: synthetic masters, write + check)."""
import os
import shutil
import subprocess
import sys
import json
import math
import re
import tempfile
import unittest
from unittest import mock

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts", "mission"))
import make_mission  # noqa: E402

PSC = os.path.join(ROOT, "scripts", "mission", "FO4SF_Min00Quest.psc")
CS = os.path.join(ROOT, "dotnet", "Mission", "Program.cs")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class ContractTests(unittest.TestCase):
    def test_script_properties_are_the_ones_the_plugin_fills(self):
        self.assertEqual(tuple(make_mission.mandatory_properties(read(PSC))), make_mission.PROPERTIES)
        cs = read(CS)
        for name in make_mission.PROPERTIES:
            self.assertIn(f'"{name}"', cs, f"Program.cs never writes the property {name}")

    def test_stages_match_between_plugin_and_script(self):
        cs = read(CS)
        stages = ", ".join(str(s) for s in make_mission.STAGES)
        self.assertIn("Stages = { " + stages + " }", cs)
        psc = read(PSC)
        for s in make_mission.STAGES:
            self.assertRegex(psc, rf"auiStageID == {s}\b", f"the script never handles stage {s}")
        for o in (10, 85, 86):                                   # Min00's objective indices, written by Program.cs
            self.assertIn(f"SetObjectiveDisplayed({o})", psc)
            self.assertIn(f"({o}, \"", cs)

    def test_mandatory_properties_parser(self):
        text = ("Actor Property A Auto Const Mandatory\nActor[] Property B Auto Const Mandatory\n"
                "int Property C = 1 Auto Const\n  MiscObject Property D Auto Const Mandatory\n")
        self.assertEqual(make_mission.mandatory_properties(text), ["A", "B", "D"])


class LogTests(unittest.TestCase):
    LINES = [
        "[10/18/2026 - 02:00:00PM] FO4SF_MISSION rt=10.5 init raiders=3",
        "[10/18/2026 - 02:00:00PM] FO4SF_MISSION rt=10.6 stage 10",
        "[10/18/2026 - 02:01:00PM] FO4SF_MISSION rt=70.1 startcombat raider 0 d=55.2",
        "[10/18/2026 - 02:01:00PM] FO4SF_MISSION rt=70.1 stage 20",
        "[10/18/2026 - 02:01:01PM] FO4SF rt=70.2 pos=1 2 3 ang=0 cell=none world=none loaded=True n=4",
        "[10/18/2026 - 02:03:00PM] FO4SF_MISSION rt=190.0 status stage=20 dead=3/3 nearest_raider=-1.0 preston=40.0 pos=1 2 3",
        "[10/18/2026 - 02:03:00PM] FO4SF_MISSION rt=190.0 stage 30",
        "[10/18/2026 - 02:04:00PM] FO4SF_MISSION rt=250.0 preston activated at stage 30",
        "[10/18/2026 - 02:04:00PM] FO4SF_MISSION rt=250.0 stage 40",
        "[10/18/2026 - 02:04:00PM] FO4SF_MISSION rt=250.0 reward credits=100",
        "[10/18/2026 - 02:04:00PM] FO4SF_MISSION rt=250.0 stage 200",
    ]

    def test_full_run(self):
        s = make_mission.summarize(self.LINES)
        self.assertEqual(s["stages"], [10, 20, 30, 40, 200])
        self.assertEqual(s["reward"], 100)
        self.assertEqual(s["startcombat"], 1)
        self.assertEqual(s["activated"], 1)
        self.assertTrue(s["status"].startswith("status stage=20 dead=3/3"))

    def test_partial_run_is_not_complete(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "fo4sf_mission.0.log")
            with open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(self.LINES[:4]) + "\n")
            self.assertEqual(make_mission.main(["log", "--file", p]), 1)
            with open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(self.LINES) + "\n")
            self.assertEqual(make_mission.main(["log", "--file", p]), 0)

    def test_other_log_lines_ignored(self):
        self.assertEqual(make_mission.summarize(["FO4SF rt=1 pos=1 2 3 n=1", "noise"])["stages"], [])


class NextStageTests(unittest.TestCase):
    """make_mission.next_stage mirrors the script's NextStage (Codex review 5563368986: progress must not depend on
    this script having issued StartCombat)."""
    def test_fight_started_by_anyone_advances(self):
        self.assertEqual(make_mission.next_stage(10, 0, 5, True, False), 20)      # already fighting at start/reload
        self.assertEqual(make_mission.next_stage(10, 0, 5, False, False), 10)     # nothing yet

    def test_dead_before_next_check(self):
        self.assertEqual(make_mission.next_stage(10, 2, 5, False, False), 20)
        self.assertEqual(make_mission.next_stage(10, 5, 5, False, False), 30)     # all died between two checks
        self.assertEqual(make_mission.next_stage(20, 5, 5, False, False), 30)

    def test_preston_only_after_the_raiders(self):
        self.assertEqual(make_mission.next_stage(20, 4, 5, True, True), 20)
        self.assertEqual(make_mission.next_stage(30, 5, 5, False, True), 40)
        self.assertEqual(make_mission.next_stage(30, 5, 5, False, False), 30)

    def test_never_goes_back_and_no_raiders_never_counts_as_cleared(self):
        self.assertEqual(make_mission.next_stage(40, 0, 5, False, False), 40)
        self.assertEqual(make_mission.next_stage(10, 0, 0, False, False), 10)

    def test_script_carries_the_same_rule(self):
        psc = read(PSC)
        for cond in ("s < 20 && (fighting || dead > 0)", "s < 30 && total > 0 && dead == total", "s == 30 && atPreston"):
            self.assertIn(cond, psc)
        self.assertNotIn("GetCombatState() == 0\n", psc)


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


class RelocateContractTests(unittest.TestCase):
    """In game 18 Oct: the core's persistent cell keeps its references at their local position in the base world, so the
    script moves its actors by the core's merge offset; that offset must be the one the door writer uses."""

    def test_script_merge_offset_is_the_measured_one(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
        import vmad_patch
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        got = {k: float(v) for k, v in re.findall(r"float Property MergeOffset([XY]) = (-?[\d.]+) Auto Const", psc)}
        self.assertEqual((got["X"], got["Y"]), vmad_patch.MERGE_MEASURED[:2])

    def test_no_exponent_float_literals(self):
        """Papyrus has no 1.0e30 literals (PC compile of 6ee0896: "required (...)+ loop did not match anything at
        input 'e30'"); comments and doc strings are exempt."""
        with open(PSC, encoding="utf-8") as f:
            code = re.sub(r"\{[^}]*\}", "", f.read())
        code = "\n".join(line.split(";")[0] for line in code.splitlines())
        self.assertIsNone(re.search(r"\d[eE][-+]?\d", code))

    def test_relocate_decides_by_position(self):
        """In game 18 Oct 14:40 the unmoved actors read a finite distance of about 2,955 (the offset's length), and the
        "finite means reachable" test skipped the move: the gap must sit between the radius and that length."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        num = lambda name: float(re.search(r"float Property %s = (-?[\d.]+) Auto Const" % name, psc).group(1))
        offset = (num("MergeOffsetX") ** 2 + num("MergeOffsetY") ** 2) ** 0.5
        radius, gap = num("RelocateRadius"), num("RelocateGap")
        self.assertLess(radius, gap)
        self.assertLess(gap, offset - radius)
        self.assertNotIn("1000000000", psc)

    def test_relocate_is_per_actor_and_retries(self):
        """Codex 5564899342: no global "relocated" flag (a no-op or partial move must be retried, a moved actor never
        offset twice), and no move from an interior."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        self.assertNotIn("relocated = true", psc)
        self.assertIn("if player.IsInInterior()", psc)
        self.assertRegex(psc, r"if relocateFails < 10\s+Relocate\(player\)")

    def test_relocate_rule_model(self):
        """The PSC's per-actor rule on plain numbers: unmoved (same world at the local spot, or another world), moved,
        a no-op MoveTo, and a partial pass followed by a retry."""
        far = float("inf")
        ox, oy, radius, gap = -1200.0, -2700.0, 800.0, 1500.0

        def step(player, actors, moveto_works):
            for a in actors:
                dist = far if a["world"] != "merged" else math.dist(player, a["pos"])
                tx, ty = a["pos"][0] + ox, a["pos"][1] + oy
                if dist < gap or math.dist(player, (tx, ty)) > radius:
                    continue
                if moveto_works(a):
                    a["pos"], a["world"] = (tx, ty), "merged"

        street = (-2011.1, -1697.2)
        for world in ("merged", "base"):
            actors = [{"pos": (-811.1, 1002.5), "world": world}, {"pos": (-790.0, 1010.0), "world": world}]
            step(street, actors, lambda a: False)                       # no-op MoveTo: still pending
            self.assertTrue(all(a["pos"] == (-811.1, 1002.5) or a["pos"] == (-790.0, 1010.0) for a in actors))
            step(street, actors, lambda a: a is actors[0])              # partial: only the first arrives
            self.assertEqual(actors[0]["pos"], (-2011.1, -1697.5))
            self.assertEqual(actors[1]["pos"], (-790.0, 1010.0))
            step(street, actors, lambda a: True)                        # retry: the second arrives, the first stays
            self.assertEqual(actors[0]["pos"], (-2011.1, -1697.5))
            self.assertEqual(actors[1]["pos"], (-1990.0, -1690.0))
            step(street, actors, lambda a: True)                        # nothing moves twice
            self.assertEqual(actors[1]["pos"], (-1990.0, -1690.0))
        away = [{"pos": (-811.1, 1002.5), "world": "merged"}]
        step((-1276.0, -3032.0), away, lambda a: True)                  # Red Rocket: not at the museum yet
        self.assertEqual(away[0]["pos"], (-811.1, 1002.5))

    def test_codsworth_is_kept_after_the_mission(self):
        """Review 20 Oct: Codsworth has his own timer (2) and failure budget, which stage 200 does not cancel, and the
        mission's Relocate no longer moves him."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        keep = psc[psc.index("Function KeepCodsworth()"):psc.index("bool Function MoveOver")]
        self.assertIn("codsworthFails += 1", keep)
        self.assertRegex(keep, r"if codsworthFails < 10\s+StartTimer\(CodsworthCheck, 2\)")
        self.assertNotIn("GetStage", keep)
        relocate = psc[psc.index("Function Relocate("):psc.index("Function KeepCodsworth()")]
        self.assertNotIn("MoveOver(Codsworth", relocate)
        self.assertIn("CancelTimer(1)", psc)
        self.assertNotIn("CancelTimer(2)", psc)
        self.assertRegex(psc, r"if aiTimerID == 2\s+KeepCodsworth\(\)")
        self.assertEqual(psc.count("KeepCodsworthStart()"), 3)          # defined, from OnQuestInit, from timer 1

    def test_moves_trace_the_worlds(self):
        """Codex's world-identity point (#353): every move logs the player's and the actor's world before it and the
        actor's world after it, so the anchor gate can be designed from evidence."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        move = psc[psc.index("bool Function MoveOver"):psc.index("Function Trace(")]
        self.assertIn("player.GetWorldSpace()", move)
        self.assertIn("a.GetWorldSpace()", move)
        self.assertLess(move.index('" player="'), move.index("a.MoveTo("))
        self.assertGreater(move.index('" player="'), move.index("RelocateRadius * RelocateRadius"))   # moves only
        self.assertGreater(move.index('" after="'), move.index("a.MoveTo("))

    def test_codsworth_is_an_optional_property(self):
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        self.assertRegex(psc, r"(?m)^Actor Property Codsworth Auto Const$")
        self.assertNotIn("Codsworth", make_mission.mandatory_properties(psc))


class StageAndInstallTests(unittest.TestCase):
    """Codex review 5563368986: a failed rebuild keeps the earlier stage; the pins are checked before install."""

    def fake_stage(self, d, out, fail_at=None, during_check=None, extra=(), writes=None):
        def fake_run(cmd, cwd=None):
            if "points" in cmd:
                with open(cmd[-1], "w", encoding="utf-8") as f:
                    json.dump({"raiders": [{"src": "046458", "dist_m": 18.9}], "preston": {"pos": [1, 2, 3]},
                               "codsworth": {"src": "01CA7D", "name": "Codsworth", "pos": [4, 5, 6], "rot": [0, 0, 1]}}, f)
            elif "write" in cmd:
                if writes is not None:
                    writes.append(cmd)
                _write(os.path.join(cmd[cmd.index("write") + 5], make_mission.PLUGIN), b"plugin-" + out.encode())
            elif "check" in cmd:
                if writes is not None:
                    writes.append(cmd)
                if during_check:
                    during_check()
                if fail_at == "check":
                    sys.exit("check exit 1")
                return "all checks pass"
            elif "PapyrusCompiler" in cmd[0] or cmd[0] == "compiler":
                _write(os.path.join(cmd[-1][3:], make_mission.SCRIPT + ".pex"), b"pex")
                return "Compilation succeeded"
            return ""
        core, raider = os.path.join(d, "FO4TerrainCore.esm"), os.path.join(d, "FO4ActorRaider.esm")
        for p, b in ((core, b"core"), (raider, b"raider")):
            if not os.path.exists(p):
                _write(p, b)
        zf = os.path.join(d, "cr.zip")
        if not os.path.exists(zf):
            import zipfile
            with zipfile.ZipFile(zf, "w") as z:
                z.writestr("Scripts/Source/Quest.psc", "Scriptname Quest")
                z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "")
        with mock.patch.object(make_mission, "run", side_effect=fake_run):
            make_mission.main(["stage", "--out", out, "--fo4", "f4", "--starfield", "sf", "--core", core,
                               "--raider", raider, "--compiler", "compiler", "--content-resources", zf, *extra])

    def test_codsworth_is_in_the_plan_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            out, writes = os.path.join(d, "m"), []
            self.fake_stage(d, out, writes=writes)
            with open(os.path.join(out, "plan.json"), encoding="utf-8") as f:
                plan = json.load(f)
            self.assertEqual(plan["codsworth"]["src"], "01CA7D")
            self.assertNotIn("--no-codsworth", writes[0])
            self.assertIn("check", writes[1])
            self.assertNotIn("--no-codsworth", writes[1])

    def test_no_codsworth_reaches_the_writer_and_the_plan(self):
        with tempfile.TemporaryDirectory() as d:
            out, writes = os.path.join(d, "m"), []
            self.fake_stage(d, out, extra=["--no-codsworth"], writes=writes)
            with open(os.path.join(out, "plan.json"), encoding="utf-8") as f:
                plan = json.load(f)
            self.assertIsNone(plan["codsworth"])
            self.assertIn("--no-codsworth", writes[0])
            self.assertIn("--no-codsworth", writes[1])   # check expects the same mode (Codex review 5564480667)

    def test_codsworth_assets_reach_the_writer_fold_and_verify(self):
        """The Codsworth thread's model (PR #361): stage copies the asset folders (not the report), names the mesh to the
        writer and check, pins each file in the plan; fold carries them and verify catches a changed one."""
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "codsworth_1018b")
            files = {"meshes/fo4port/actors/codsworth/codsworth.nif": b"nif", "geometries/ab/cd.mesh": b"mesh",
                     "materials/fo4port/texsets/actors/handy/body.mat": b"mat",
                     "textures/fo4port/actors/handy/body_color.dds": b"dds", "codsworth_report.json": b"{}"}
            for rel, b in files.items():
                _write(os.path.join(src, *rel.split("/")), b)
            out, writes = os.path.join(d, "m"), []
            self.fake_stage(d, out, extra=["--codsworth-assets", src], writes=writes)
            for cmd in writes:
                self.assertEqual(cmd[cmd.index("--codsworth-model") + 1], make_mission.CODSWORTH_MESH)
            with open(os.path.join(out, "plan.json"), encoding="utf-8") as f:
                plan = json.load(f)
            self.assertEqual(sorted(plan["assets"]), sorted(r for r in files if r != "codsworth_report.json"))
            core_dir = os.path.join(d, "coreset")
            _write(os.path.join(core_dir, "FO4TerrainCore.esm"), b"core")
            folded = os.path.join(d, "folded")
            raider = os.path.join(d, "FO4ActorRaider.esm")
            self.assertEqual(make_mission.main(["fold", "--mission", out, "--core-dir", core_dir, "--out", folded,
                                                "--raider", raider]), 0)
            nif = os.path.join(folded, "Data", "meshes", "fo4port", "actors", "codsworth", "codsworth.nif")
            self.assertTrue(os.path.isfile(nif))
            self.assertFalse(os.path.exists(os.path.join(folded, "Data", "codsworth_report.json")))
            _write(nif, b"other")
            self.assertEqual(make_mission.main(["verify", "--exp-dir", folded, "--plan", os.path.join(out, "plan.json"),
                                                "--raider", raider]), 1)

    def test_codsworth_voice_reaches_the_writer_and_the_plan(self):
        """His voice (PR #361): each lines.tsv row's <info>_<response>.wem is copied under his voice type's folder, named
        by its WEMFile id; voice.json carries the text and the sex rule ("sir" male, "mum" female) to the writer."""
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "voice")
            rows = [("000F1F6E", "1", "Yes?"), ("000F1F78", "1", "Sir?"), ("000F1F80", "1", "Right away, mum.")]
            os.makedirs(src)
            with open(os.path.join(src, "lines.tsv"), "w", encoding="utf-8", newline="") as f:
                f.write("quest\tsubtype\ttopic\tinfo\tresponse\tvoice\ttext\n")
                for info, resp, text in rows:
                    f.write(f"COMCodsworth\tHELO\tCOMCodsworthHellos\t{info}\t{resp}\tv.fuz\t{text}\n")
                    _write(os.path.join(src, "wem", "Windows", f"{info.lower()}_{resp}.wem"), info.encode())
            out, writes = os.path.join(d, "m"), []
            self.fake_stage(d, out, extra=["--codsworth-voice", src], writes=writes)
            voice_json = writes[0][writes[0].index("--codsworth-voice") + 1]
            self.assertEqual(writes[1][writes[1].index("--codsworth-voice") + 1], voice_json)
            with open(os.path.join(out, "plan.json"), encoding="utf-8") as f:
                plan = json.load(f)
            base = make_mission.VOICE_DIR
            self.assertEqual(sorted(plan["assets"]), [f"{base}/00f4c001.wem", f"{base}/00f4c002.wem", f"{base}/00f4c003.wem"])
            with open(os.path.join(out, "Data", *base.split("/"), "00f4c002.wem"), "rb") as f:
                self.assertEqual(f.read(), b"000F1F78")

    def test_voice_sex_rule_and_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "voice")
            os.makedirs(src)
            with open(os.path.join(src, "lines.tsv"), "w", encoding="utf-8", newline="") as f:
                f.write("info\tresponse\ttext\nAA\t1\tYes, sir.\nBB\t1\tMum!\nCC\t1\tSirius\n")
            for n in ("aa_1", "bb_1", "cc_1"):
                _write(os.path.join(src, "wem", f"{n}.wem"), b"x")
            vj = os.path.join(d, "voice.json")
            make_mission.copy_voice(src, os.path.join(d, "data"), vj)
            with open(vj, encoding="utf-8") as f:
                self.assertEqual([l["sex"] for l in json.load(f)], ["male", "female", None])
            os.remove(os.path.join(src, "wem", "bb_1.wem"))
            with self.assertRaises(SystemExit):
                make_mission.copy_voice(src, os.path.join(d, "data2"), vj)

    def test_codsworth_assets_need_the_mesh(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "empty")
            os.makedirs(src)
            with self.assertRaises(SystemExit):
                self.fake_stage(d, os.path.join(d, "m"), extra=["--codsworth-assets", src])

    def snapshot(self, root):
        got = {}
        for base, _, files in os.walk(root):
            for n in files:
                p = os.path.join(base, n)
                with open(p, "rb") as f:
                    got[os.path.relpath(p, root)] = f.read()
        return got

    def test_rebuild_into_existing_stage_refused_and_failure_leaves_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            first = os.path.join(d, "wfc1")
            self.fake_stage(d, first)
            before = self.snapshot(first)
            self.assertIn("plan.json", before)
            with self.assertRaises(SystemExit):
                self.fake_stage(d, first)                       # occupied output
            self.assertEqual(self.snapshot(first), before)
            second = os.path.join(d, "wfc2")
            with self.assertRaises(SystemExit):
                self.fake_stage(d, second, fail_at="check")     # a failed rebuild publishes nothing
            self.assertFalse(os.path.exists(second))
            self.assertEqual(self.snapshot(first), before)
            # the failed attempt is kept, and a retry neither reuses nor deletes it
            failed = [n for n in os.listdir(d) if n.startswith("wfc2.partial-")]
            self.assertEqual(len(failed), 1)
            _write(os.path.join(d, failed[0], "failed-run.txt"), b"evidence")
            kept = self.snapshot(os.path.join(d, failed[0]))
            with self.assertRaises(SystemExit):
                self.fake_stage(d, second, fail_at="check")
            self.assertEqual(self.snapshot(os.path.join(d, failed[0])), kept)
            self.assertEqual(len([n for n in os.listdir(d) if n.startswith("wfc2.partial-")]), 2)
            self.fake_stage(d, second)                          # and a good retry still publishes
            self.assertTrue(os.path.exists(os.path.join(second, "plan.json")))
            self.assertEqual(self.snapshot(os.path.join(d, failed[0])), kept)

    def test_master_changed_during_build_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            core = os.path.join(d, "FO4TerrainCore.esm")
            _write(core, b"core A")
            out = os.path.join(d, "wfc1")
            with self.assertRaises(SystemExit) as e:
                self.fake_stage(d, out, during_check=lambda: _write(core, b"core B"))
            self.assertIn("changed during the build", str(e.exception))
            self.assertFalse(os.path.exists(out))

    def test_fold_and_verify(self):
        with tempfile.TemporaryDirectory() as d:
            stage = os.path.join(d, "wfc1")
            self.fake_stage(d, stage)
            core_dir = os.path.join(d, "coreset")
            _write(os.path.join(core_dir, "FO4TerrainCore.esm"), b"core")
            _write(os.path.join(core_dir, "Data", "Terrain", "x.btd"), b"btd")
            raider = os.path.join(d, "FO4ActorRaider.esm")
            folded = os.path.join(d, "folded")
            self.assertEqual(make_mission.main(["fold", "--mission", stage, "--core-dir", core_dir, "--out", folded,
                                                "--raider", raider]), 0)
            plan = os.path.join(stage, "plan.json")
            self.assertEqual(make_mission.main(["verify", "--exp-dir", folded, "--plan", plan, "--raider", raider]), 0)
            self.assertTrue(os.path.exists(os.path.join(folded, "Data", "Terrain", "x.btd")))
            # the masters or the staged files changed: verify refuses
            _write(raider, b"other raider")
            self.assertEqual(make_mission.main(["verify", "--exp-dir", folded, "--plan", plan, "--raider", raider]), 1)
            _write(raider, b"raider")
            self.assertEqual(make_mission.main(["verify", "--exp-dir", folded, "--plan", plan]), 1)   # raider missing
            _write(os.path.join(folded, "FO4TerrainCore.esm"), b"newer core")
            self.assertEqual(make_mission.main(["verify", "--exp-dir", folded, "--plan", plan, "--raider", raider]), 1)
            # fold against a different core is refused and writes nothing
            _write(os.path.join(core_dir, "FO4TerrainCore.esm"), b"newer core")
            with self.assertRaises(SystemExit):
                make_mission.main(["fold", "--mission", stage, "--core-dir", core_dir, "--out", os.path.join(d, "f2"),
                                   "--raider", raider])
            self.assertFalse(os.path.exists(os.path.join(d, "f2")))
            self.assertFalse(os.path.exists(os.path.join(d, "f2.partial")))


@unittest.skipUnless(shutil.which("dotnet") and os.environ.get("FO4SF_DOTNET_TESTS"),
                     "set FO4SF_DOTNET_TESTS=1 with a dotnet SDK on PATH to run the C# self-test")
class WriterSelfTest(unittest.TestCase):
    def test_selftest(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, DOTNET_ROLL_FORWARD="Major")
            r = subprocess.run(["dotnet", "run", "-c", "Release", "--project", os.path.join(ROOT, "dotnet", "Mission"),
                                "--", "selftest", d], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("selftest pass", r.stdout)


if __name__ == "__main__":
    unittest.main()
