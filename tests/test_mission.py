"""The cut-down "When Freedom Calls" mission: the contract between dotnet/Mission (the plugin), FO4SF_Min00Quest.psc (the
quest script) and make_mission.py (staging and the log reader). Synthetic only; the C# writer's own self-test runs when
a dotnet SDK is on PATH (dotnet/Mission selftest: synthetic masters, write + check)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

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
