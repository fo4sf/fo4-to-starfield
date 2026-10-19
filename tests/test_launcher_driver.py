"""Resumable build driver and build manifest (src/fo4sf/launcher/driver.py, manifest.py) on synthetic recipes whose
steps are tiny Python scripts written here; no game files, no converter run."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import driver, files, manifest  # noqa: E402

# copy <src> to <dst>, appending a line; exit with the code in <root>/fail_<name> if that file exists
STEP = r'''
import os, sys
src, dst, name = sys.argv[1:4]
root = os.path.dirname(dst)
fail = os.path.join(root, "fail_" + name)
with open(os.path.join(root, "calls.log"), "a") as f:
    f.write(name + "\n")
if os.path.exists(fail):
    sys.exit(int(open(fail).read() or 3))
if os.path.exists(os.path.join(root, "nooutput_" + name)):
    sys.exit(0)
if os.path.exists(os.path.join(root, "sleep_" + name)):
    import time; time.sleep(5)
data = open(src).read() if os.path.exists(src) else ""
with open(dst, "w") as f:
    f.write(data + name + "\n")
'''


class DriverTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = t.name
        self.script = os.path.join(self.root, "step.py")
        with open(self.script, "w") as f:
            f.write(STEP)
        with open(os.path.join(self.root, "input.txt"), "w") as f:
            f.write("fo4\n")
        self.lines = []

    def recipe(self, **extra):
        r = {"name": "synthetic", "state_dir": "{w}/.launcher", "vars": {"w": self.root},
             "steps": [
                 {"id": "select", "argv": ["{python}", self.script, "{w}/input.txt", "{w}/a.txt", "select"],
                  "inputs": ["{w}/input.txt"], "outputs": ["{w}/a.txt"], "code": []},
                 {"id": "stage", "argv": ["{python}", self.script, "{w}/a.txt", "{w}/b.txt", "stage"],
                  "inputs": ["{w}/a.txt"], "outputs": ["{w}/b.txt"], "after": ["select"]},
                 {"id": "check", "argv": ["{python}", self.script, "{w}/b.txt", "{w}/c.txt", "check"],
                  "inputs": ["{w}/b.txt"], "outputs": ["{w}/c.txt"], "after": ["stage"], "timeout_s": 2}]}
        r.update(extra)
        p = os.path.join(self.root, "recipe.json")
        with open(p, "w") as f:
            json.dump(r, f)
        return driver.load_recipe(p, repo=ROOT)[0]

    def run_it(self, **kw):
        return driver.build(self.recipe(), ROOT, echo=self.lines.append, **kw)

    def calls(self):
        p = os.path.join(self.root, "calls.log")
        return open(p).read().split() if os.path.exists(p) else []

    def statuses(self, rep):
        return [s["status"] for s in rep["steps"]]

    def touch(self, name, text=""):
        with open(os.path.join(self.root, name), "w") as f:
            f.write(text)

    def test_runs_then_reuses(self):
        rep = self.run_it()
        self.assertTrue(rep["complete"])
        self.assertEqual(self.statuses(rep), ["done", "done", "done"])
        rep = self.run_it()
        self.assertEqual(self.statuses(rep), ["reused"] * 3)
        self.assertTrue(rep["complete"])
        self.assertEqual(rep["counts"], {"reused": 3})       # reuse is never counted as done
        self.assertEqual(self.calls(), ["select", "stage", "check"])

    def test_changed_input_reruns_the_step_and_its_dependants(self):
        self.run_it()
        self.touch("input.txt", "fo4 v2\n")
        rep = self.run_it()
        self.assertEqual(self.statuses(rep), ["done", "done", "done"])

    def test_failure_blocks_dependants_and_resume_reuses_finished_steps(self):
        self.touch("fail_stage", "4")
        rep = self.run_it()
        self.assertFalse(rep["complete"])
        self.assertEqual(self.statuses(rep), ["done", "failed", "not_run"])
        self.assertEqual(rep["steps"][1]["returncode"], 4)
        os.remove(os.path.join(self.root, "fail_stage"))
        rep = self.run_it()
        self.assertEqual(self.statuses(rep), ["reused", "done", "done"])
        self.assertTrue(rep["complete"])

    def test_keep_going_marks_dependants_blocked(self):
        self.touch("fail_stage", "2")
        rep = self.run_it(keep_going=True)
        self.assertEqual(self.statuses(rep), ["done", "failed", "blocked"])
        self.assertIn("depends on stage", rep["steps"][2]["note"])

    def test_exit_zero_without_outputs_is_a_failure(self):
        self.touch("nooutput_select")
        rep = self.run_it()
        self.assertEqual(self.statuses(rep)[0], "failed")
        self.assertEqual(rep["steps"][0]["returncode"], 0)
        self.assertFalse(rep["complete"])

    def test_deleted_output_reruns(self):
        self.run_it()
        os.remove(os.path.join(self.root, "c.txt"))
        rep = self.run_it()
        self.assertEqual(self.statuses(rep), ["reused", "reused", "done"])

    def test_interrupted_running_step_is_rerun(self):
        self.run_it()
        state_p = os.path.join(self.root, ".launcher", "state.json")
        st = files.load_json(state_p)
        st["steps"]["stage"]["status"] = "running"
        files.save_json(state_p, st)
        rep = self.run_it()
        self.assertEqual(self.statuses(rep), ["reused", "done", "done"])

    def test_timeout(self):
        self.touch("sleep_check")
        rep = self.run_it()
        self.assertEqual(self.statuses(rep), ["done", "done", "timeout"])
        self.assertFalse(rep["complete"])

    def test_lock_refuses_a_second_driver(self):
        os.makedirs(os.path.join(self.root, ".launcher"))
        self.touch(os.path.join(".launcher", "driver.lock"), "pid 1")
        with self.assertRaises(driver.RecipeError):
            self.run_it()
        self.assertEqual(self.calls(), [])
        self.assertTrue(self.run_it(break_lock=True)["complete"])

    def test_disk_floor_blocks_before_running(self):
        rep = self.run_it(min_free_gb=10 ** 9)
        self.assertEqual(self.statuses(rep), ["blocked", "not_run", "not_run"])
        self.assertEqual(self.calls(), [])

    def test_step_need_adds_to_the_floor(self):
        r = self.recipe()
        r["steps"][1]["need_gb"] = 10 ** 9
        rep = driver.build(r, ROOT, echo=self.lines.append)
        self.assertEqual(self.statuses(rep), ["done", "blocked", "not_run"])
        self.assertIn("this step needs", rep["steps"][1]["note"])
        self.assertEqual(self.calls(), ["select"])

    def test_status_is_read_only_and_reports_each_step(self):
        st = driver.status(self.recipe(), ROOT)
        self.assertEqual([(s["last"], s["would"]) for s in st["steps"]], [("never run", "run")] * 3)
        self.assertIsNone(st["last_run"])
        self.assertFalse(os.path.exists(os.path.join(self.root, ".launcher")))
        self.touch("fail_check", "4")
        self.run_it()
        st = driver.status(self.recipe(), ROOT)
        self.assertEqual([s["last"] for s in st["steps"]], ["done", "done", "failed"])
        self.assertEqual([s["would"] for s in st["steps"]], ["reuse", "reuse", "run"])
        self.assertTrue(st["steps"][2]["log"].endswith("check.1.log"))
        self.assertFalse(st["last_run"]["complete"])
        self.assertIsNone(st["lock"])
        # a step left running with no driver holding the lock reads as interrupted
        state_path = os.path.join(self.root, ".launcher", "state.json")
        state = files.load_json(state_path)
        state["steps"]["check"]["status"] = "running"
        files.save_json(state_path, state)
        self.assertEqual(driver.status(self.recipe(), ROOT)["steps"][2]["last"], "interrupted")
        self.touch(os.path.join(".launcher", "driver.lock"), "pid 7")
        st = driver.status(self.recipe(), ROOT)
        self.assertEqual(st["lock"], "pid 7")
        self.assertEqual(st["steps"][2]["last"], "running")

    def test_status_cli(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("launcher_cli", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        self.recipe()
        p = os.path.join(self.root, "recipe.json")
        out = os.path.join(self.root, "status.json")
        self.assertEqual(cli.main(["status", p, "--json", out]), 1)
        self.assertEqual(cli.main(["build", p]), 0)
        self.assertEqual(cli.main(["status", p]), 0)
        self.assertEqual(len(files.load_json(out)["steps"]), 3)

    def test_import_closure_follows_repo_imports_only(self):
        repo = os.path.join(self.root, "repo")
        os.makedirs(os.path.join(repo, "src", "pkg"))
        os.makedirs(os.path.join(repo, "scripts"))
        files_ = {"scripts/run.py": "import os, json\nimport helper\nfrom pkg import a\n",
                  "scripts/helper.py": "X = 1\n",
                  "scripts/unused.py": "Y = 2\n",
                  "src/pkg/__init__.py": "",
                  "src/pkg/a.py": "from . import b\n",
                  "src/pkg/b.py": "Z = 3\n",
                  "src/pkg/c.py": "W = 4\n"}
        for rel, text in files_.items():
            with open(os.path.join(repo, rel), "w") as f:
                f.write(text)
        got = [os.path.relpath(p, repo).replace(os.sep, "/")
               for p in driver.import_closure([os.path.join(repo, "scripts", "run.py")], repo)]
        self.assertEqual(got, ["scripts/helper.py", "scripts/run.py", "src/pkg/__init__.py", "src/pkg/a.py",
                               "src/pkg/b.py"])
        step = {"code": [], "argv": ["python", os.path.join(repo, "scripts", "run.py")]}
        before = driver.code_hash(driver.code_paths(step, repo))
        with open(os.path.join(repo, "src", "pkg", "c.py"), "w") as f:
            f.write("W = 5\n")                         # not imported: no rerun
        self.assertEqual(driver.code_hash(driver.code_paths(step, repo)), before)
        with open(os.path.join(repo, "src", "pkg", "b.py"), "w") as f:
            f.write("Z = 4\n")                         # imported two levels down: rerun
        self.assertNotEqual(driver.code_hash(driver.code_paths(step, repo)), before)

    def test_closure_of_the_launcher_cli_covers_its_package(self):
        got = {os.path.relpath(p, ROOT).replace(os.sep, "/")
               for p in driver.import_closure([os.path.join(ROOT, "scripts", "launcher.py")], ROOT)}
        for rel in ("scripts/launcher.py", "src/fo4sf/launcher/driver.py", "src/fo4sf/launcher/same_ids.py",
                    "src/fo4sf/launcher/files.py"):
            self.assertIn(rel, got)
        self.assertNotIn("src/fo4sf/ba2.py", got)

    def test_dry_run_changes_nothing(self):
        rep = self.run_it(dry_run=True)
        self.assertEqual([w for _id, w, _ in rep["plan"]], ["run", "run", "run"])
        self.assertEqual(self.calls(), [])
        self.assertFalse(os.path.exists(os.path.join(self.root, ".launcher", "state.json")))

    def test_until_and_force(self):
        rep = self.run_it(until="select")
        self.assertEqual(self.statuses(rep), ["done", "not_run", "not_run"])
        self.run_it()
        rep = self.run_it(force=["stage"])
        self.assertEqual(self.statuses(rep), ["reused", "done", "done"])

    def test_recipe_errors(self):
        p = os.path.join(self.root, "bad.json")
        for bad in ({"steps": [{"id": "a", "argv": ["{nope}"]}]},
                    {"steps": [{"id": "a", "argv": ["x"], "after": ["b"]}]},
                    {"steps": [{"id": "a", "argv": ["x"]}, {"id": "a", "argv": ["y"]}]},
                    {"steps": []}):
            with open(p, "w") as f:
                json.dump(bad, f)
            with self.assertRaises(driver.RecipeError):
                driver.load_recipe(p, repo=ROOT)
        with open(p, "w") as f:
            json.dump({"vars": {"a": "1"}, "steps": [{"id": "s", "argv": ["{a}", "{b}"]}]}, f)
        rec, _ = driver.load_recipe(p, ["b=2"], repo=ROOT)
        self.assertEqual(rec["steps"][0]["argv"], ["1", "2"])

    def test_example_recipe_needs_its_paths_and_then_loads(self):
        ex = os.path.join(ROOT, "scripts", "launcher_recipes", "core_restage_same_ids.example.json")
        with self.assertRaisesRegex(driver.RecipeError, "against"):
            driver.load_recipe(ex, repo=ROOT)
        sets = [f"{k}={self.root}/{k}" for k in ("work", "core", "sf_esm", "cluster", "navmesh", "sf_data", "fo4", "against", "out")]
        rec, _ = driver.load_recipe(ex, sets, repo=ROOT)
        self.assertEqual([s["id"] for s in rec["steps"]], ["stage", "check", "compare_ids", "same_ids"])
        self.assertIn(f"{self.root}/out", rec["steps"][0]["argv"])
        self.assertIn("--sf-data", rec["steps"][1]["argv"])            # check fails without the vanilla records
        rep = driver.build(rec, ROOT, dry_run=True, echo=self.lines.append)
        self.assertEqual([w for _id, w, _ in rep["plan"]], ["run"] * 4)

    def test_manifest_written_when_complete(self):
        r = self.recipe(manifest={"outputs": ["{w}/c.txt"], "path": "{w}/build_manifest.json"})
        rep = driver.build(r, ROOT, echo=self.lines.append)
        m = files.load_json(rep["manifest"])
        out = m["outputs"][os.path.join(self.root, "c.txt")]["c.txt"]
        self.assertEqual(out["sha256"], files.sha256(os.path.join(self.root, "c.txt")))
        self.assertEqual(m["extra"]["recipe"], "synthetic")


class ManifestTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.base = os.path.join(t.name, "depot_base", "Data")
        self.dlc = os.path.join(t.name, "depot_dlc", "Data")
        for d in (self.base, self.dlc):
            os.makedirs(d)
        for d, n, b in ((self.base, "Fallout4.esm", b"TES4base"), (self.dlc, "dlcrobot.esm", b"TES4robot"),
                        (self.base, "Fallout4 - Meshes.ba2", b"BTDX" + b"0" * 100)):
            with open(os.path.join(d, n), "wb") as f:
                f.write(b)

    def test_masters_across_depots_and_missing_dlc_named(self):
        f = manifest.fo4_inputs([self.base, self.dlc])
        self.assertEqual(sorted(f["masters"]), ["DLCRobot.esm", "Fallout4.esm"])
        self.assertIn("sha256", f["masters"]["DLCRobot.esm"])
        self.assertTrue(f["dlc"]["DLCRobot.esm"]["present"])
        self.assertIn("DLCNukaWorld.esm (Nuka-World)", f["dlc_missing"])
        self.assertEqual(len(f["dlc_missing"]), 5)
        arc = f["archives"]["Fallout4 - Meshes.ba2"]
        self.assertNotIn("sha256", arc)                    # size and time unless --hash-archives
        self.assertIn("sha256", manifest.fo4_inputs([self.base], hash_archives=True)["archives"]["Fallout4 - Meshes.ba2"])

    def test_no_base_master_refused(self):
        with self.assertRaises(FileNotFoundError):
            manifest.fo4_inputs([self.dlc])

    def test_compare_inputs_ignores_paths_and_finds_a_changed_master(self):
        a = {"fo4": manifest.fo4_inputs([self.base, self.dlc]), "tools": {"python": "3.12"}}
        b = json.loads(json.dumps(a))
        for v in b["fo4"]["masters"].values():
            v["path"] = "E:/elsewhere/" + os.path.basename(v["path"])
        self.assertEqual(manifest.compare_inputs(a, b), [])
        b["fo4"]["masters"]["Fallout4.esm"]["sha256"] = "0" * 64
        self.assertEqual(len(manifest.compare_inputs(a, b)), 1)

    def test_game_pins(self):
        game = os.path.join(os.path.dirname(self.base), "..", "sf")
        os.makedirs(os.path.join(game, "Data"))
        with open(os.path.join(game, "Starfield.exe"), "wb") as f:
            f.write(b"MZ")
        g = manifest.game_pins(game)
        self.assertFalse(g["sfse"])
        self.assertFalse(g["creation_kit"])
        self.assertIn("sha256", g["files"]["Starfield.exe"])

    def test_tool_pins_read_the_mutagen_version(self):
        pins = manifest.tool_pins(ROOT)
        self.assertTrue(any(p.startswith("Mutagen.Bethesda.Starfield ") for p in pins["mutagen"]))


if __name__ == "__main__":
    unittest.main()
