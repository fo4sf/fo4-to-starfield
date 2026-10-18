"""The cut-down "When Freedom Calls" mission: the contract between dotnet/Mission (the plugin), FO4SF_Min00Quest.psc (the
quest script) and make_mission.py (staging and the log reader). Synthetic only; the C# writer's own self-test runs when
a dotnet SDK is on PATH (dotnet/Mission selftest: synthetic masters, write + check)."""
import os
import shutil
import subprocess
import sys
import json
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


class StageAndInstallTests(unittest.TestCase):
    """Codex review 5563368986: a failed rebuild keeps the earlier stage; the pins are checked before install."""

    def fake_stage(self, d, out, fail_at=None):
        def fake_run(cmd, cwd=None):
            if "points" in cmd:
                with open(cmd[-1], "w", encoding="utf-8") as f:
                    json.dump({"raiders": [{"src": "046458", "dist_m": 18.9}], "preston": {"pos": [1, 2, 3]}}, f)
            elif "write" in cmd:
                _write(os.path.join(cmd[cmd.index("write") + 5], make_mission.PLUGIN), b"plugin-" + out.encode())
            elif "check" in cmd:
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
                               "--raider", raider, "--compiler", "compiler", "--content-resources", zf])

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
