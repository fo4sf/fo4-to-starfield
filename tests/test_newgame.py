"""The Fallout 4 new game (docs/newgame/vault111-start.md): the contract between dotnet/NewGame (the plugin),
FO4SF_NewGameQuest.psc / FO4SF_NewGameLooks.psc (the scripts) and make_newgame.py (precheck, staging, verify, fold, the
log reader). Synthetic only; the C# writer's own self-test runs when a dotnet SDK is on PATH."""
import io
import unittest.mock
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts", "newgame"))
import make_newgame as ng  # noqa: E402

PSC = os.path.join(ROOT, "scripts", "newgame", "FO4SF_NewGameQuest.psc")
LOOKS = os.path.join(ROOT, "scripts", "newgame", "FO4SF_NewGameLooks.psc")
CS = os.path.join(ROOT, "dotnet", "NewGame", "Program.cs")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def written_properties(cs):
    """The property names Program.cs writes: the Properties() table plus the three object properties."""
    body = cs[cs.index("public static List<(string Name, object Value)> Properties"):]
    body = body[:body.index("};")]
    names = set(re.findall(r'\("(\w+)",', body))
    names |= set(re.findall(r'Obj\("(\w+)"', cs)) - {""}
    names |= set(re.findall(r'Name = "(\w+)", Flags = SF\.ScriptProperty', cs))
    return names


class ContractTests(unittest.TestCase):
    def test_saving_and_hud_restored_after_the_hold_off(self):
        """MQ101's stage 0 turns saving off and hides the HUD; its stop (stage 9000) restores neither (PC read of
        QF_MQ101_00003448.psc, 19 Oct). The quest restores both right after stopping it, before the move."""
        psc = read(PSC)
        body = psc[psc.index("Event OnTimer"):]
        hold = body.index("HoldOffStart()")
        self.assertLess(hold, body.index("Game.SetInChargen(false, false, false)"))
        self.assertLess(body.index("Game.SetInChargen(false, false, false)"), body.index("EnterVault(player)"))
        self.assertLess(hold, body.index("Game.SetCharGenHUDMode(0)"))

    def test_every_mandatory_property_is_written_and_every_written_one_declared(self):
        declared = ng.declared_properties(read(PSC))
        written = written_properties(read(CS))
        mandatory = {n for n, m in declared.items() if m}
        self.assertEqual(mandatory - written, set(), "mandatory properties the plugin never fills")
        self.assertEqual(written - set(declared), set(), "properties the plugin writes that the script lacks")
        self.assertIn("HoldOff", written)
        self.assertIn("LooksWait", written)                  # 0 in a --no-looks build, so the quest does not wait

    def test_stages_match(self):
        cs, psc = read(CS), read(PSC)
        self.assertIn("Stages = { " + ", ".join(str(s) for s in ng.STAGES) + " }", cs)
        for s in ng.STAGES:
            if s not in (20, 30):                            # 20 is set by the looks script or the wait, 30 by the cog door
                self.assertRegex(psc, rf"AdvanceTo\({s}\)")
        self.assertIn("SetStage(20)", read(LOOKS))
        self.assertIn("AdvanceTo(30)", psc)
        self.assertIn("SetObjectiveDisplayed(10)", psc)
        self.assertIn("Objective = 10", cs)

    def test_script_names_and_log_name(self):
        cs = read(CS)
        self.assertIn(f'ScriptName = "{ng.SCRIPT}"', cs)
        self.assertIn(f'LooksScript = "{ng.LOOKS}"', cs)
        self.assertIn(f'Plugin = "{ng.PLUGIN}"', cs)
        self.assertRegex(read(PSC), rf"Scriptname {ng.SCRIPT} extends Quest")
        self.assertRegex(read(LOOKS), rf"Scriptname {ng.LOOKS} extends Quest")
        self.assertIn('"FO4SF_NEWGAME rt="', read(PSC))

    def test_merge_offset_is_the_measured_one(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
        import vmad_patch
        x, y, _ = vmad_patch.MERGE_MEASURED
        self.assertIn(f"MergeX = {x:g}f, MergeY = {y:g}f", read(CS))
        self.assertIn(f"MergeOffsetX = {x}", read(PSC))
        self.assertIn(f"MergeOffsetY = {y}", read(PSC))

    def test_the_guard_rule_matches_the_script(self):
        self.assertIn("return days < MaxNewGameDays && level <= MaxNewGameLevel", read(PSC))
        self.assertTrue(ng.is_new_game(0.0, 1))
        self.assertTrue(ng.is_new_game(0.2, 1))
        self.assertFalse(ng.is_new_game(0.25, 1))            # six game hours in: not a fresh start
        self.assertFalse(ng.is_new_game(0.0, 2))
        self.assertFalse(ng.is_new_game(12.5, 30))           # the owner's test saves

    def test_every_native_the_script_calls_is_prechecked(self):
        psc = read(PSC)
        calls = set(re.findall(r"\.(\w+)\(", psc))
        listed = {f for bases in ng.NATIVES[ng.SCRIPT].values() for f in bases}
        own = set(re.findall(r"^\s*\w*\s*Function\s+(\w+)", psc, re.M))
        # GetPositionY/Z share GetPositionX's script; GetDistance is not used; the rest must be listed or our own
        missing = calls - listed - own - {"GetPositionY", "GetPositionZ"}
        self.assertEqual(missing, set())
        # Starfield's Utility.psc has no IsInMenuMode (precheck on the PC, 2026-10-19): neither script may call it
        self.assertNotIn("IsInMenuMode(", psc)
        self.assertNotIn("IsInMenuMode(", read(LOOKS))
        looks_calls = set(re.findall(r"\.(\w+)\(", read(LOOKS)))
        looks_listed = {f for bases in ng.NATIVES[ng.LOOKS].values() for f in bases}
        self.assertEqual(looks_calls - looks_listed - {"TraceUser", "SetStage", "StartTimer", "GetStage"}, set())

    def test_declared_properties_parser(self):
        text = ("Quest[] Property A Auto Const Mandatory\nfloat Property B = 0.25 Auto Const\n"
                "string Property C = \"x.esm\" Auto Const\n  int Property D Auto Const Mandatory\n")
        self.assertEqual(ng.declared_properties(text), {"A": True, "B": False, "C": False, "D": True})


# Starfield's Game.psc declarations (PC read, 19 Oct): the restore after the hold-off calls both
CHARGEN = ("Function SetInChargen(bool abDisableSaving, bool abDisableWaiting, bool abShowControlsDisabledMessage) "
           "native global\nFunction SetCharGenHUDMode(int aiCGHUDMode) native global\n")


def fake_zip(path, game=None, utility=None, extra=None):
    base = {
        "Actor": "Scriptname Actor extends ObjectReference\nint Function GetLevel() native\n",
        "Debug": "Function OpenUserLog(string a) native global\nbool Function TraceUser(string a, string b) native global\n"
                 "Function Notification(string a) native global\n",
        "Game": game if game is not None else "Actor Function GetPlayer() native global\n"
                                              "Form Function GetFormFromFile(int a, string b) native global\n"
                                              "Function ShowRaceMenu(ObjectReference a = None) native global\n"
                                              + CHARGEN,
        "GlobalVariable": "float Function GetValue() native\n",
        "Message": "int Function Show(float a = 0.0) native\n",
        "ObjectReference": "\n".join(f"Function {f}() native" for f in ng.NATIVES[ng.SCRIPT]["ObjectReference"]),
        "Quest": "\n".join(f"Function {f}() native" for f in ng.NATIVES[ng.SCRIPT]["Quest"]),
        "ScriptObject": "Function StartTimer(float a, int b = 0) native\n",
        "Utility": utility if utility is not None else "float Function GetCurrentRealTime() native global\n"
                                                       "bool Function IsInMenuMode() native global\nFunction Wait(float a) native global\n",
    }
    with zipfile.ZipFile(path, "w") as z:
        for name, text in base.items():
            z.writestr(f"Scripts/Source/{name}.psc", text)
        z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "")
        z.writestr("Scripts/Source/Fragments/Quests/QF_MQ101_00003448.psc",
                   extra if extra is not None else "if MQ101Debug.GetValue() == 8\n  ; start in the spaceport\nendif\n")


class PrecheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_all_found(self):
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z)
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], [])
        self.assertTrue(all(r["natives"][ng.LOOKS].values()))
        self.assertEqual(len(r["mq101debug"]), 1)
        self.assertIn("QF_MQ101_00003448.psc:1:", r["mq101debug"][0])

    def test_missing_show_race_menu_only_drops_the_looks(self):
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z, game="Actor Function GetPlayer() native global\nForm Function GetFormFromFile(int a, string b) native global\n"
                    + CHARGEN)
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], [])
        self.assertFalse(r["natives"][ng.LOOKS]["Game.ShowRaceMenu"])
        out = os.path.join(self.tmp, "p.json")
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            rc = ng.main(["precheck", "--content-resources", z, "--out", out])
        self.assertEqual(rc, 0)
        self.assertIn("--no-looks", o.getvalue())
        self.assertTrue(os.path.isfile(out))

    def test_missing_core_native_fails(self):
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z, utility="Function Wait(float a) native global\n")
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], ["Utility.GetCurrentRealTime"])
        with unittest.mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(ng.main(["precheck", "--content-resources", z]), 1)

    def test_has_function_needs_the_declaration(self):
        self.assertTrue(ng.has_function("bool Function IsInMenuMode() native global", "IsInMenuMode"))
        self.assertFalse(ng.has_function("; IsInMenuMode() is not here\nFunction IsInMenuModeX()", "IsInMenuMode"))


class LogTests(unittest.TestCase):
    LINES = [
        "[10/20/2026 - 09:00:00AM] FO4SF_NEWGAME rt=5.0 init holdoff=2 vault=FO4Port.esm:2049 core=FO4TerrainCore.esm:685915",
        "[10/20/2026 - 09:00:01AM] FO4SF_NEWGAME rt=6.0 held off [Quest < (00012345)>] running_after=False",
        "[10/20/2026 - 09:00:01AM] FO4SF_NEWGAME rt=6.0 not running [Quest < (00054321)>]",
        "[10/20/2026 - 09:00:02AM] FO4SF_NEWGAME rt=7.0 enter vault ok=True pos=11 20 1 target=11 20 1 cell=[Cell <FO4Port_Vault111Cryo>]",
        "[10/20/2026 - 09:00:02AM] FO4SF_NEWGAME rt=7.0 stage 10",
        "[10/20/2026 - 09:00:03AM] FO4SF rt=7.5 pos=1 2 3 (another log's line)",
        "[10/20/2026 - 09:01:00AM] FO4SF_NEWGAME rt=60.0 status stage=20 pos=50 10 0 cell=x world=None",
        "[10/20/2026 - 09:02:00AM] FO4SF_NEWGAME rt=120.0 elevator prompt button=0",
        "[10/20/2026 - 09:02:00AM] FO4SF_NEWGAME rt=120.1 surface setposition pos=-2450 -1410 110 target=-2450 -1410 110",
        "[10/20/2026 - 09:02:00AM] FO4SF_NEWGAME rt=120.1 stage 40",
        "[10/20/2026 - 09:02:04AM] FO4SF_NEWGAME rt=124.0 landed z=110.0",
        "[10/20/2026 - 09:02:04AM] FO4SF_NEWGAME rt=124.0 stage 200",
    ]

    def test_summary(self):
        s = ng.summarize(self.LINES)
        self.assertEqual(s["stages"], [10, 40, 200])
        self.assertEqual(s["held_off"], ["[Quest < (00012345)>]"])
        self.assertTrue(s["entered_vault"])
        self.assertTrue(s["landed"])
        self.assertFalse(s["fell"])
        self.assertFalse(s["stood_down"])
        self.assertIn("stage=20", s["last_status"])

    def test_stood_down_and_exit_code(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, "fo4sf_newgame.0.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write("[x] FO4SF_NEWGAME rt=3.0 not a new game: days=41.2 level=12: standing down\n"
                    "[x] FO4SF_NEWGAME rt=3.0 stage 1\n")
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            self.assertEqual(ng.main(["log", "--file", path]), 1)
        self.assertTrue(json.loads(o.getvalue())["stood_down"])
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.LINES))
        with unittest.mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(ng.main(["log", "--file", path]), 0)


    def run_log(self, text):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, "fo4sf_newgame.0.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            code = ng.main(["log", "--file", path])
        return code, json.loads(o.getvalue())

    def test_an_older_completion_never_passes_a_newer_run(self):
        """Codex review on #393: the log is appended across sessions, so only the latest run is judged."""
        done = "\n".join(self.LINES) + "\n"
        init = "[y] FO4SF_NEWGAME rt=2.0 init holdoff=2 vault=FO4Port.esm:2049 core=FO4TerrainCore.esm:685915\n"
        cases = {
            "failed": init + "[y] FO4SF_NEWGAME rt=3.0 enter vault ok=False pos=0 0 0 target=11 20 1 cell=None\n",
            "stood down": init + "[y] FO4SF_NEWGAME rt=3.0 not a new game: days=41.2 level=12: standing down\n"
                                 "[y] FO4SF_NEWGAME rt=3.0 stage 1\n",
            "init only": init,
        }
        for name, newer in cases.items():
            with self.subTest(name):
                code, s = self.run_log(done + newer)
                self.assertEqual(code, 1)
                self.assertEqual(s["runs"], 2)
                self.assertTrue(s["earlier_completed"])
                self.assertNotIn(200, s["stages"])
        self.assertFalse(self.run_log(done + cases["failed"])[1]["entered_vault"])
        self.assertTrue(self.run_log(done + cases["stood down"])[1]["stood_down"])

    def test_the_latest_run_completing_passes(self):
        failed = "[y] FO4SF_NEWGAME rt=2.0 init holdoff=2 vault=FO4Port.esm:2049 core=FO4TerrainCore.esm:685915\n" \
                 "[y] FO4SF_NEWGAME rt=3.0 enter vault ok=False pos=0 0 0 target=11 20 1 cell=None\n"
        code, s = self.run_log(failed + "\n".join(self.LINES) + "\n")
        self.assertEqual(code, 0)
        self.assertEqual(s["runs"], 2)
        self.assertFalse(s["earlier_completed"])
        self.assertTrue(s["entered_vault"])

    def test_split_runs(self):
        lines = ["[a] FO4SF_NEWGAME rt=1 status stage=20", "[b] other log", "[c] FO4SF_NEWGAME rt=2 init x",
                 "[d] FO4SF_NEWGAME rt=3 stage 10", "[e] FO4SF_NEWGAME rt=4 init y"]
        self.assertEqual(ng.split_runs(lines, ng.LINE), [["status stage=20"], ["init x", "stage 10"], ["init y"]])
        self.assertEqual(ng.split_runs([], ng.LINE), [])

class VerifyFoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        t = self.tmp
        self.stage = os.path.join(t, "stage")
        os.makedirs(os.path.join(self.stage, "Data", "Scripts"))
        files = {ng.PLUGIN: b"plugin", "Data/Scripts/FO4SF_NewGameQuest.pex": b"pex1"}
        for rel, data in files.items():
            with open(os.path.join(self.stage, *rel.split("/")), "wb") as f:
                f.write(data)
        self.core_dir = os.path.join(t, "core_set")
        os.makedirs(self.core_dir)
        for name, data in (("FO4TerrainCore.esm", b"core"), ("Mars.esm", b"mars")):
            with open(os.path.join(self.core_dir, name), "wb") as f:
                f.write(data)
        self.port = os.path.join(t, "FO4Port.esm")
        with open(self.port, "wb") as f:
            f.write(b"port")
        plan = {"kind": "newgame", "plugin": ng.PLUGIN, "plugin_sha256": ng.sha256(os.path.join(self.stage, ng.PLUGIN)),
                "scripts": {"FO4SF_NewGameQuest": ng.sha256(os.path.join(self.stage, "Data", "Scripts", "FO4SF_NewGameQuest.pex"))},
                "checked_against_sha256": {"FO4Port.esm": ng.sha256(self.port), "formids.json": "x",
                                           "FO4TerrainCore.esm": ng.sha256(os.path.join(self.core_dir, "FO4TerrainCore.esm"))}}
        with open(os.path.join(self.stage, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(plan, f)

    def fold(self, out, **kw):
        args = ["fold", "--stage", self.stage, "--core-dir", self.core_dir, "--out", out]
        for k, v in kw.items():
            args += [f"--{k}", v]
        with unittest.mock.patch("sys.stdout", io.StringIO()):
            return ng.main(args)

    def test_fold_then_verify(self):
        out = os.path.join(self.tmp, "folded")
        self.assertEqual(self.fold(out, port=self.port), 0)
        self.assertTrue(os.path.isfile(os.path.join(out, "Mars.esm")))
        with unittest.mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(ng.main(["verify", "--exp-dir", out, "--plan", os.path.join(self.stage, "plan.json"),
                                      "--port", self.port]), 0)

    def test_fold_refuses_another_port(self):
        other = os.path.join(self.tmp, "other_port.esm")
        with open(other, "wb") as f:
            f.write(b"rebuilt port")
        out = os.path.join(self.tmp, "folded")
        with self.assertRaises(SystemExit):
            self.fold(out, port=other)
        self.assertFalse(os.path.exists(out))                # nothing published; the attempt stays beside it

    def test_verify_catches_a_changed_core(self):
        out = os.path.join(self.tmp, "folded")
        self.assertEqual(self.fold(out, port=self.port), 0)
        with open(os.path.join(out, "FO4TerrainCore.esm"), "wb") as f:
            f.write(b"another core")
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            self.assertEqual(ng.main(["verify", "--exp-dir", out, "--plan", os.path.join(self.stage, "plan.json"),
                                      "--port", self.port]), 1)
        self.assertIn("FO4TerrainCore.esm", o.getvalue())

    def test_existing_out_refused(self):
        out = os.path.join(self.tmp, "folded")
        os.makedirs(out)
        with self.assertRaises(SystemExit):
            self.fold(out, port=self.port)


@unittest.skipUnless(shutil.which("dotnet"), "no dotnet SDK on PATH")
class WriterSelfTest(unittest.TestCase):
    def test_selftest(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        r = subprocess.run(["dotnet", "run", "-c", "Release", "--project", os.path.join(ROOT, "dotnet", "NewGame"), "--",
                            "selftest", tmp], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
        self.assertIn("selftest pass", r.stdout)


if __name__ == "__main__":
    unittest.main()
