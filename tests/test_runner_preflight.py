"""testqueue.py run --preflight (docs/ai/leader-core.md section 7, task T3): off by default and then absent from the
run; on, the checklist goes to run.log before the first launch and one FAIL or UNKNOWN stops the run before any step,
in a dry run too, with a blocker_opened in the ledger when there is one. The PC-side probe is exercised on this box
only where it reads nothing Windows-specific. Synthetic data; no game."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
sys.path.insert(0, os.path.join(ROOT, "src"))
import testqueue as tq  # noqa: E402
import test_testqueue as tt  # noqa: E402
import test_core_preflight as tcp  # noqa: E402  (FakeProbe)
from fo4sf.core import controller as c  # noqa: E402
from fo4sf.core import preflight as pf  # noqa: E402
from fo4sf.core.model import Event  # noqa: E402
from fo4sf.core.state import Ledger, fold  # noqa: E402

deploy = tq.exp_install.deployment                        # scripts/deploy_starfield.py, as exp_install imports it


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def quiet_log(r, msg):
    with open(r.log_p, "a", encoding="utf-8") as f:
        f.write(f"{tq.now()} {msg}\n")


class RunnerPreflightTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = tmp.name
        tt.make_queue(self.d, n=2)
        self.leader = os.path.join(self.d, "leader")
        self.ctl = tt.FakeControls()
        self.calls = []

    def runner(self, probe=None, **kw):
        r = tq.Runner(self.d, tt.args(**kw), ctl=self.ctl, step=lambda t, o: self.calls.append(t["id"]) or 0)
        r.log = lambda msg: quiet_log(r, msg)             # run.log only: the suite's output stays the result line
        r.session, r.cell = True, "C"
        r._ps = lambda *a, **k: (0, "at the cell")
        if probe is not None:
            r.preflight_probe = lambda runner: probe
        return r

    def status(self):
        with open(os.path.join(self.d, "state.json"), encoding="utf-8") as f:
            return json.load(f)["status"]

    def test_off_by_default_nothing_runs(self):
        r = self.runner(probe=tcp.FakeProbe(version=None))      # would refuse if it ran
        r.run()
        self.assertTrue(self.calls)
        self.assertNotIn("preflight", read(os.path.join(self.d, "run.log")))

    def test_a_refusal_stops_before_any_step_and_logs_the_checklist(self):
        r = self.runner(probe=tcp.FakeProbe(version=None, guard=("paused", "db")), preflight=True)
        self.assertEqual(r.run(), 3)
        self.assertEqual(self.calls, [])
        log = read(os.path.join(self.d, "run.log"))
        self.assertIn("preflight: REFUSED: game_version UNKNOWN, guardian FAIL", log)
        self.assertIn("  PASS    pin:", log)
        self.assertIn("  FAIL    guardian: Resource Guardian mode paused", log)
        self.assertEqual(self.status(), "stopped: preflight refused (game_version UNKNOWN, guardian FAIL)")

    def test_a_refusal_leaves_a_blocker_in_the_ledger_when_there_is_one(self):
        c.Controller(self.leader).claim("Claude", "window", 3600)
        r = self.runner(probe=tcp.FakeProbe(save=None), preflight=True, lease_dir=self.leader, lease_owner="Claude")
        self.assertEqual(r.run(), 3)
        events = Ledger(os.path.join(self.leader, "ledger.jsonl")).read()
        self.assertEqual([e.ev for e in events], ["controller_claimed", "blocker_opened"])
        self.assertEqual(events[-1].by, "testqueue:Claude")
        self.assertEqual(events[-1].fields["checks"]["recovery_save"], "UNKNOWN")
        s = fold(events)
        self.assertTrue(s.blockers["preflight"]["open"])
        self.assertIn("Blockers: preflight: UNKNOWN recovery_save", s.report()[6])

    def test_a_passing_gate_closes_the_blocker_an_earlier_refusal_opened(self):
        c.Controller(self.leader).claim("Claude", "window", 3600)
        self.assertEqual(self.runner(probe=tcp.FakeProbe(save=None), preflight=True, lease_dir=self.leader, lease_owner="Claude").run(), 3)
        led = Ledger(os.path.join(self.leader, "ledger.jsonl"))
        self.assertTrue(fold(led.read()).blockers["preflight"]["open"])
        r = self.runner(probe=tcp.FakeProbe(), preflight=True, lease_dir=self.leader, lease_owner="Claude", max_attempts=1)
        r.run()
        s = fold(led.read())
        self.assertFalse(s.blockers["preflight"]["open"])
        self.assertEqual([e.ev for e in led.read()].count("blocker_closed"), 1)
        self.assertEqual(s.report()[6], "Blockers: none open")
        r = self.runner(probe=tcp.FakeProbe(), preflight=True, lease_dir=self.leader, lease_owner="Claude", max_attempts=1)
        r.run()                                                                     # a second pass closes nothing twice
        self.assertEqual([e.ev for e in led.read()].count("blocker_closed"), 1)

    def test_every_check_passing_lets_the_run_go_on(self):
        r = self.runner(probe=tcp.FakeProbe(), preflight=True, max_attempts=1)
        r.run()
        self.assertEqual(sorted(set(self.calls)), ["0000_fall", "0001_fall"])
        log = read(os.path.join(self.d, "run.log"))
        self.assertIn("preflight: every check passed", log)
        self.assertEqual(self.status(), "finished")

    def test_dry_run_prints_the_checklist_and_still_refuses(self):
        r = self.runner(probe=tcp.FakeProbe(lease=("fail", "held by Codex")), preflight=True, dry_run=True)
        self.assertEqual(r.run(), 3)
        log = read(os.path.join(self.d, "run.log"))
        self.assertIn("  FAIL    lease: held by Codex", log)
        self.assertNotIn("dry run: would run", log)
        r = self.runner(probe=tcp.FakeProbe(), preflight=True, dry_run=True)
        self.assertEqual(r.run(), 0)
        self.assertIn("dry run: would run 0000_fall", read(os.path.join(self.d, "run.log")))


class PreflightReportTests(unittest.TestCase):
    """--preflight-report: the same checklist, logged and written to preflight.json, never a refusal or a ledger line."""
    setUp, runner, status = RunnerPreflightTests.setUp, RunnerPreflightTests.runner, RunnerPreflightTests.status

    def test_report_only_names_what_it_would_refuse_and_runs_on(self):
        c.Controller(self.leader).claim("Claude", "window", 3600)
        r = self.runner(probe=tcp.FakeProbe(version=None, guard=("paused", "db")), preflight_report=True,
                        lease_dir=self.leader, lease_owner="Claude", max_attempts=1)
        r.run()
        self.assertEqual(sorted(set(self.calls)), ["0000_fall", "0001_fall"])
        log = read(os.path.join(self.d, "run.log"))
        self.assertIn("preflight (report only): would refuse: game_version UNKNOWN, guardian FAIL", log)
        self.assertIn("  FAIL    guardian: Resource Guardian mode paused", log)
        self.assertNotIn("REFUSED", log)
        self.assertEqual(self.status(), "finished")
        rep = tt.jload(os.path.join(self.d, "preflight.json"))
        self.assertEqual((rep["mode"], rep["ok"], rep["would_refuse"]), ("report", False, ["game_version", "guardian"]))
        self.assertEqual([x["name"] for x in rep["checks"]], list(pf.CHECKS))
        events = Ledger(os.path.join(self.leader, "ledger.jsonl")).read()
        self.assertNotIn("blocker_opened", [e.ev for e in events])

    def test_a_passing_report_and_a_probe_that_breaks(self):
        self.runner(probe=tcp.FakeProbe(), preflight_report=True, max_attempts=1).run()
        self.assertIn("preflight (report only): every check passed", read(os.path.join(self.d, "run.log")))
        self.assertTrue(tt.jload(os.path.join(self.d, "preflight.json"))["ok"])
        self.calls.clear()
        os.remove(os.path.join(self.d, "state.json"))
        r = self.runner(preflight_report=True, max_attempts=1)
        r.preflight_probe = lambda runner: (_ for _ in ()).throw(RuntimeError("no probe"))
        r.run()
        self.assertIn("preflight (report only): not run: RuntimeError: no probe", read(os.path.join(self.d, "run.log")))
        self.assertTrue(self.calls)
        rep = tt.jload(os.path.join(self.d, "preflight.json"))       # never the earlier run's pass (Codex on #403)
        self.assertEqual((rep["ok"], rep["checks"], rep["not_run"]), (False, [], "RuntimeError: no probe"))

    def test_the_enforcing_gate_wins_when_both_are_on(self):
        r = self.runner(probe=tcp.FakeProbe(save=None), preflight=True, preflight_report=True)
        self.assertEqual(r.run(), 3)
        self.assertNotIn("report only", read(os.path.join(self.d, "run.log")))
        self.assertFalse(os.path.exists(os.path.join(self.d, "preflight.json")))

    def test_main_reads_the_report_switch_from_the_environment(self):
        seen = {}

        class FakeRunner:
            def __init__(self, qdir, a):
                seen["a"] = a

            def run(self):
                return 0
        for value, want in (("1", True), ("on", True), ("0", False), ("", False)):
            with mock.patch.dict(os.environ, {"FO4SF_PREFLIGHT_REPORT": value}), mock.patch.object(tq, "Runner", FakeRunner):
                tq.main(["run", "--queue", self.d])
            self.assertIs(seen["a"].preflight_report, want, value)
        with mock.patch.dict(os.environ, {"FO4SF_PREFLIGHT_REPORT": ""}), mock.patch.object(tq, "Runner", FakeRunner):
            tq.main(["run", "--queue", self.d, "--preflight-report"])
        self.assertIs(seen["a"].preflight_report, True)


class ProbeOnThisBoxTests(unittest.TestCase):
    """The PC-side readings that can be taken anywhere: paths, absent files, the lease, the Guardian database."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = tmp.name
        tt.make_queue(self.d, n=1)
        self.r = tq.Runner(self.d, tt.args(starfield=os.path.join(self.d, "game")), ctl=tt.FakeControls(), step=lambda t, o: 0)
        self.p = tq.PreflightProbe(self.r)

    def test_absent_files_read_as_absent_not_as_errors(self):
        self.assertIsNone(self.p.staged_plugin_sha256())             # make_queue stages no FO4Port.esm
        self.assertIsNone(self.p.deploy_manifest())
        self.assertIsNone(self.p.install_record())
        with mock.patch.object(tq.PreflightProbe, "saves_dirs", return_value=[os.path.join(self.d, "saves")]):
            self.assertEqual(self.p.ini_texts(), [])                   # never the owner's real My Games folder
        self.assertEqual(self.p.plugin_masters("FO4SFExp.esm"), [])
        self.assertTrue(self.p.implicit("Starfield.esm"))
        self.assertFalse(self.p.implicit("FO4Port.esm"))
        with open(os.path.join(self.d, "FO4Port.esm"), "wb") as f:
            f.write(b"TES4")
        self.assertEqual(self.p.staged_plugin_sha256(), tq.sha256(os.path.join(self.d, "FO4Port.esm")))
        self.assertIsNone(self.p.data_file_sha256("FO4Port.esm"))      # no game folder at all
        os.makedirs(os.path.join(self.d, "game", "Data", "Terrain"))
        with open(os.path.join(self.d, "game", "Data", "Terrain", "W.btd"), "wb") as f:
            f.write(b"BTDB")
        self.assertEqual(self.p.data_file_sha256(os.path.join("Terrain", "W.btd")), tq.sha256(os.path.join(self.d, "game", "Data", "Terrain", "W.btd")))
        self.assertIsNone(self.p.data_file_sha256("FO4Port.esm"))
        with self.assertRaises(ValueError):                               # a record naming a path outside Data: UNKNOWN
            self.p.data_file_sha256(os.path.join("..", "Starfield.exe"))

    def test_the_load_set_readings_come_from_the_game_and_my_games_folders(self):
        from fo4sf.planet import esm
        home, local = os.path.join(self.d, "home"), os.path.join(self.d, "local")
        mg = os.path.join(home, "Documents", "My Games", "Starfield")
        saves = [os.path.join(home, "OneDrive", "Documents", "My Games", "Starfield", "Saves"), os.path.join(mg, "Saves")]
        data = os.path.join(self.d, "game", "Data")
        for d in (os.path.join(mg, "Data"), data, os.path.join(local, "Starfield")):
            os.makedirs(d)

        def plugin(path, sig=None, fid=0):
            w = esm.PluginWriter(["Starfield.esm"])
            if sig:
                w.add(esm.Record(sig, fid, [(b"EDID", esm.zbytes("X"))]))
            w.write(path)

        env = {"LOCALAPPDATA": local}
        with mock.patch.object(tq.PreflightProbe, "saves_dirs", return_value=saves), mock.patch.dict(os.environ, env):
            self.assertEqual(self.p.my_games(), [mg])                        # OneDrive's Documents is not there
            self.assertTrue(self.p.my_games_known())
            self.assertEqual((self.p.ini_test_files(), self.p.ccc_files(), self.p.shadow_plugins()), ([], [], []))
            self.assertEqual(self.p.start_overrides(), ([], []))              # no Plugins.txt yet, nothing staged
            self.assertEqual(pf.check_loaders(self.p).status, pf.PASS)
            plugin(os.path.join(data, "Other.esm"), b"DFOB", 0x0000562D)     # StartupQuest_DO
            plugin(os.path.join(data, "FO4Port.esm"))                         # the installed port: no override
            plugin(os.path.join(self.d, "FO4Port.esm"), b"GLOB", 0x000A7D31)  # the staged one, deployed at the launch
            plugin(os.path.join(data, "SFBGS003.esm"), b"QUST", 0x00003448)   # the game's own: never counted
            with open(os.path.join(local, "Starfield", "Plugins.txt"), "w", encoding="utf-8") as f:
                f.write("# comment\n*Other.esm\n*FO4Port.esm\n*SFBGS003.esm\nOff.esm\n")
            hits, bad = self.p.start_overrides()
            self.assertEqual((sorted(hits), bad), ([("FO4Port.esm", "MQ101Debug", "0A7D31"),
                                                    ("Other.esm", "StartupQuest_DO", "00562D")], []))
            c = pf.check_start(self.p)
            self.assertEqual(c.status, pf.FAIL)
            self.assertIn("Other.esm:StartupQuest_DO: a plugin not ours", c.detail)
            installed = self.pin(port={"mode": "installed", "plugin_sha256": "x"})   # the run loads Data's port
            self.assertEqual(installed.start_overrides()[0], [("Other.esm", "StartupQuest_DO", "00562D")])
            bdir = os.path.join(self.d, "bridge")                            # bridge_install.py installs it at the launch
            os.makedirs(bdir)
            plugin(os.path.join(bdir, "FO4SFBridge.esm"), b"QUST", 0x00003448)
            bridged = self.pin(bridge={"dir": bdir, "plugin": "FO4SFBridge.esm", "sha256": {}})
            self.assertEqual(bridged.staged_at_launch()[-1], ("FO4SFBridge.esm", os.path.join(bdir, "FO4SFBridge.esm")))
            self.assertEqual(bridged.start_overrides()[0], [("Other.esm", "StartupQuest_DO", "00562D"),
                                                            ("FO4SFBridge.esm", "MQ101", "003448")])
            with open(os.path.join(mg, "StarfieldCustom.ini"), "w", encoding="utf-8") as f:
                f.write("[General]\nsTestFile1=Other.esm\n")
            with open(os.path.join(mg, "Starfield.ccc"), "w", encoding="utf-8") as f:
                f.write("SFBGS003.esm\nMod.esm\n")
            plugin(os.path.join(mg, "Data", "Other.esm"))
            self.assertEqual(self.p.ini_test_files(), [(os.path.join(mg, "StarfieldCustom.ini"), 2, "sTestFile1", "Other.esm")])
            self.assertEqual(self.p.ccc_files(), [(os.path.join(mg, "Starfield.ccc"), ["SFBGS003.esm", "Mod.esm"])])
            self.assertEqual(self.p.shadow_plugins(), [(os.path.join(mg, "Data", "Other.esm"), "Other.esm")])
            c = pf.check_loaders(self.p)
            self.assertEqual(c.status, pf.FAIL)
            for part in ("sTestFile1=Other.esm", "lists Mod.esm", "a copy of Data\\Other.esm"):
                self.assertIn(part, c.detail)
        with mock.patch.object(tq.PreflightProbe, "saves_dirs", return_value=[os.path.join(self.d, "none", "Saves")]):
            self.assertEqual(pf.check_loaders(self.p).status, pf.UNKNOWN)    # no My Games folder: nothing checked
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": ""}):
            self.assertEqual(pf.check_start(self.p).status, pf.UNKNOWN)      # Plugins.txt not locatable

    def pin(self, **fields):
        """The queue with these fields, read by a fresh probe (the Runner loads queue.json once)."""
        q = tt.jload(os.path.join(self.d, "queue.json"))
        q.update(fields)
        tt.jdump(q, os.path.join(self.d, "queue.json"))
        r = tq.Runner(self.d, tt.args(starfield=os.path.join(self.d, "game")), ctl=tt.FakeControls(), step=lambda t, o: 0)
        return tq.PreflightProbe(r)

    def test_a_half_finished_deploy_uninstall_fails_the_deploy_check(self):
        # Codex on #182: deploy_starfield.py uninstall with a changed archive removes FO4Port.esm, keeps the archive and
        # the manifest (complete still true, the plugin's historical hash still in artifacts); the gate passed on it
        data = os.path.join(self.d, "game", "Data")
        os.makedirs(data)
        esm, ba2 = os.path.join(data, deploy.PLUGIN), os.path.join(data, deploy.ARCHIVE)
        with open(esm, "wb") as f:
            f.write(b"TES4" + bytes(32))
        with open(ba2, "wb") as f:
            f.write(b"BTDX" + bytes(32))
        pt = os.path.join(self.d, "Plugins.txt")
        with open(pt, "w", encoding="utf-8") as f:
            f.write("*Other.esm\n*FO4Port.esm\n")
        sha = tq.sha256(esm)
        man = {"files": [deploy.PLUGIN, deploy.ARCHIVE], "published_files": [deploy.PLUGIN, deploy.ARCHIVE], "plugins_txt": pt,
               "plugins_added": [], "plugins_replaced": [], "complete": True, "plugins_restore_pending": False,
               "artifacts": {deploy.PLUGIN: deploy.artifact_identity(esm), deploy.ARCHIVE: deploy.artifact_identity(ba2)}}
        deploy.write_manifest(os.path.join(data, deploy.MANIFEST), man)
        p = self.pin(plugin_sha256=sha)
        self.assertEqual(pf.check_deploy(p).status, pf.PASS)              # the complete deploy of the pinned build
        with open(ba2, "ab") as f:
            f.write(b"!")                                                  # the archive changed: uninstall preserves it
        with mock.patch.object(deploy, "plugins_txt_path", return_value=pt), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, "uninstall incomplete"):
                deploy.uninstall(SimpleNamespace(starfield=os.path.join(self.d, "game"), dry_run=False))
        self.assertFalse(os.path.exists(esm))
        left = p.deploy_manifest()
        self.assertEqual((left["complete"], left["files"], left["artifacts"][deploy.PLUGIN]["sha256"]), (True, [deploy.ARCHIVE], sha))
        c = pf.check_deploy(p)
        self.assertEqual(c.status, pf.FAIL, c.detail)
        self.assertIn("half-finished uninstall: FO4Port.esm removed", c.detail)
        rep = pf.run_gate(p, ["pin", "deploy"])                            # the staging copy is intact: pin alone says nothing
        self.assertEqual({x.name: x.status for x in rep.checks}["deploy"], pf.FAIL)
        with open(os.path.join(data, deploy.MANIFEST), "w", encoding="utf-8") as f:
            json.dump(dict(man, files=[deploy.PLUGIN, deploy.ARCHIVE]), f)       # a stale record claiming both: the bytes decide
        c = pf.check_deploy(p)
        self.assertEqual((c.status, "is not there" in c.detail), (pf.FAIL, True))

    def test_a_half_finished_experiment_uninstall_fails_the_experiment_check(self):
        # Codex on #182: exp_install.py uninstall with a changed terrain file removes the plugin, keeps the file and the
        # record (complete true, cleanup_pending true, source_inputs still the staged ones); installed_identity dropped
        # the flag and the gate compared staged inputs only
        staging, game = os.path.join(self.d, "exp"), os.path.join(self.d, "game")
        os.makedirs(os.path.join(staging, "Data", "Terrain"))
        os.makedirs(os.path.join(game, "Data"))
        with open(os.path.join(staging, "FO4SFExp.esm"), "wb") as f:
            f.write(b"TES4" + bytes(16))
        with open(os.path.join(staging, "Data", "Terrain", "W.btd"), "wb") as f:
            f.write(b"BTDB")
        local = os.path.join(self.d, "local")
        os.makedirs(os.path.join(local, "Starfield"))
        with open(os.path.join(local, "Starfield", "Plugins.txt"), "wb") as f:
            f.write(b"*FO4Port.esm\r\n")
        a = SimpleNamespace(starfield=game, exp_dir=staging, plugins="FO4SFExp.esm", pack=False)
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": local}), contextlib.redirect_stdout(io.StringIO()):
            tq.exp_install.install(a)
            p = self.pin(experiment_identity=tq.experiment_identity(staging, ["FO4SFExp.esm"]))
            self.assertEqual(pf.check_experiment(p).status, pf.PASS)    # the pinned experiment, installed and intact
            with open(os.path.join(game, "Data", "Terrain", "W.btd"), "ab") as f:
                f.write(b"!")                                              # an installed file changed: uninstall preserves it
            with self.assertRaisesRegex(SystemExit, "uninstall incomplete"):
                tq.exp_install.uninstall(a)
        self.assertFalse(os.path.exists(os.path.join(game, "Data", "FO4SFExp.esm")))
        inst = tq.installed_identity(game)
        self.assertEqual((inst["complete"], inst["cleanup_pending"], list(inst["files"])), (True, True, [os.path.join("Terrain", "W.btd")]))
        self.assertEqual(inst["source_inputs"], p.queue["experiment_identity"]["inputs"])
        self.assertEqual(p.install_record(), inst)                        # the probe carries the flag through
        c = pf.check_experiment(p)
        self.assertEqual(c.status, pf.FAIL, c.detail)
        self.assertIn("cleanup pending", c.detail)
        self.assertIn("cleanup pending", tq.install_mismatch(p.queue, inst))   # and a result on it is INCONCLUSIVE INSTALL
        rec_p = os.path.join(game, "Data", tq.exp_install.RECORD)
        with open(rec_p, encoding="utf-8") as f:
            rec = json.load(f)
        rec.pop("cleanup_pending")
        with open(rec_p, "w", encoding="utf-8") as f:
            json.dump(rec, f)                                              # the flag lost: the inventory still says so
        c = pf.check_experiment(p)
        self.assertEqual((c.status, "owns no installed ['FO4SFExp.esm']" in c.detail), (pf.FAIL, True))

    def test_plugins_txt_location(self):
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": ""}):
            self.assertIsNone(self.p.plugins_txt_lines())
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": self.d}):
            self.assertEqual(self.p.plugins_txt_lines(), [])
            os.makedirs(os.path.join(self.d, "Starfield"))
            with open(os.path.join(self.d, "Starfield", "Plugins.txt"), "w", encoding="utf-8") as f:
                f.write("*FO4Port.esm\nFO4SFExp.esm\n")
            self.assertEqual(self.p.plugins_txt_lines(), ["*FO4Port.esm", "FO4SFExp.esm"])

    @unittest.skipUnless(os.name == "nt", "reads a real version resource through version.dll: Windows only")
    def test_the_exe_version_of_a_real_windows_dll(self):
        import re
        dll = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "kernel32.dll")
        v = tq.exe_file_version(dll)
        self.assertIsNotNone(v, dll)
        self.assertTrue(re.fullmatch(r"\d+\.\d+\.\d+\.\d+", v), v)
        self.assertIsNone(tq.exe_file_version(os.path.join(self.d, "missing.exe")))

    def test_main_reads_the_preflight_switch_from_the_environment(self):
        seen = {}

        class FakeRunner:
            def __init__(self, qdir, a):
                seen["a"] = a

            def run(self):
                return 0
        for value, want in (("1", True), ("true", True), ("YES", True), ("on", True), ("0", False), ("", False), ("maybe", False)):
            with mock.patch.dict(os.environ, {"FO4SF_PREFLIGHT": value}), mock.patch.object(tq, "Runner", FakeRunner):
                tq.main(["run", "--queue", self.d])
            self.assertIs(seen["a"].preflight, want, value)
        with mock.patch.dict(os.environ, {"FO4SF_PREFLIGHT": "1"}), mock.patch.object(tq, "Runner", FakeRunner):
            tq.main(["run", "--queue", self.d, "--no-preflight"])           # the flag turns it off for one run
        self.assertIs(seen["a"].preflight, False)
        with mock.patch.dict(os.environ, {"FO4SF_PREFLIGHT": ""}), mock.patch.object(tq, "Runner", FakeRunner):
            tq.main(["run", "--queue", self.d, "--preflight"])
        self.assertIs(seen["a"].preflight, True)

    def test_the_exe_version_decoding(self):
        import ctypes
        fixed = (ctypes.c_uint32 * 13)()
        fixed[0] = 0xFEEF04BD                                                        # VS_FIXEDFILEINFO.dwSignature
        fixed[2] = (1 << 16) | 16                                                    # dwFileVersionMS: 1.16
        fixed[3] = (244 << 16) | 0                                                   # dwFileVersionLS: 244.0

        class FakeVersionDll:
            def GetFileVersionInfoSizeW(self, path, handle):
                return 64

            def GetFileVersionInfoW(self, path, handle, size, buf):
                return 1

            def VerQueryValueW(self, buf, sub, ptr, length):
                ptr._obj.value = ctypes.addressof(fixed)
                length._obj.value = ctypes.sizeof(fixed)
                return 1
        self.assertEqual(tq.exe_file_version("Starfield.exe", _ver=FakeVersionDll()), "1.16.244.0")

        class NoResource(FakeVersionDll):
            def GetFileVersionInfoSizeW(self, path, handle):
                return 0
        self.assertIsNone(tq.exe_file_version("Starfield.exe", _ver=NoResource()))

        class NoValue(FakeVersionDll):
            def VerQueryValueW(self, buf, sub, ptr, length):
                return 0
        self.assertIsNone(tq.exe_file_version("Starfield.exe", _ver=NoValue()))

    def test_the_probe_reads_the_ledger_pin_and_a_staged_plugins_masters(self):
        import struct
        leader = os.path.join(self.d, "leader")
        c.Controller(leader).claim("Claude", "window", 3600)
        Ledger(os.path.join(leader, "ledger.jsonl")).append(
            Event("build_pinned", "t", fields={"build_id": "b1", "game_version": "1.16.244.0"}))
        r = tq.Runner(self.d, tt.args(lease_dir=leader, lease_owner="Claude"), ctl=tt.FakeControls(), step=lambda t, o: 0)
        self.assertEqual(tq.PreflightProbe(r).ledger_game_version(), "1.16.244.0")
        exp = os.path.join(self.d, "exp")
        os.makedirs(exp)

        def sub(sig, payload):
            return sig + struct.pack("<H", len(payload)) + payload
        body = sub(b"HEDR", struct.pack("<fII", 0.96, 0, 0x800)) + sub(b"MAST", b"Starfield.esm\0") + sub(b"DATA", bytes(8)) \
            + sub(b"MAST", b"FO4Port.esm\0") + sub(b"DATA", bytes(8))
        with open(os.path.join(exp, "FO4SFExp.esm"), "wb") as f:
            f.write(b"TES4" + struct.pack("<IIIIHH", len(body), 0, 0, 0, 0, 0) + body)
        q = tt.jload(os.path.join(self.d, "queue.json"))
        q["experiment_identity"] = {"exp_dir": exp, "plugins": ["FO4SFExp.esm"], "inputs": {}}
        tt.jdump(q, os.path.join(self.d, "queue.json"))
        r = tq.Runner(self.d, tt.args(), ctl=tt.FakeControls(), step=lambda t, o: 0)
        self.assertEqual(tq.PreflightProbe(r).plugin_masters("FO4SFExp.esm"), ["Starfield.esm", "FO4Port.esm"])
        self.assertEqual(tq.PreflightProbe(r).plugin_masters("Missing.esm"), [])

    def test_stop_dirs_guardian_saves_and_the_lease(self):
        dirs = self.p.stop_dirs()
        self.assertEqual(len(dirs), 3)
        self.assertEqual(dirs[0][0], os.path.join(self.d, "STOP"))
        self.assertEqual(dirs[0][1:], (True, True))
        with mock.patch.object(tq.Controls, "state_dir", os.path.join(self.d, "state")):
            self.assertEqual(self.p.guardian()[0], "missing")
            os.makedirs(os.path.join(self.d, "state"))
            with open(os.path.join(self.d, "state", "guardian.db"), "wb") as f:
                f.write(b"")
            self.assertEqual(self.p.guardian(), ("running", os.path.join(self.d, "state", "guardian.db")))   # FakeControls says running
        with mock.patch.object(tq.PreflightProbe, "saves_dirs", staticmethod(lambda: [os.path.join(self.d, "nope")])):
            self.assertIsNone(self.p.save_present("fo4sf_test_abcd1234"))
        saves = os.path.join(self.d, "Saves")
        os.makedirs(saves)
        with mock.patch.object(tq.PreflightProbe, "saves_dirs", staticmethod(lambda: [saves])):
            self.assertFalse(self.p.save_present("fo4sf_test_abcd1234"))
            for other in ("fo4sf_test_abcd1234.sfs.bak", "fo4sf_test_abcd1234_s100.sfs"):   # not the dedicated save
                with open(os.path.join(saves, other), "wb") as f:
                    f.write(b"")
            self.assertFalse(self.p.save_present("fo4sf_test_abcd1234"))
            with open(os.path.join(saves, "fo4sf_test_abcd1234.sfs"), "wb") as f:     # what `save <name>` writes
                f.write(b"")
            self.assertTrue(self.p.save_present("fo4sf_test_abcd1234"))
        self.assertEqual(self.p.lease_status()[0], "unknown")
        self.assertIsNone(self.p.ledger_game_version())
        leader = os.path.join(self.d, "leader")
        c.Controller(leader).claim("Claude", "window", 3600)
        r2 = tq.Runner(self.d, tt.args(lease_dir=leader, lease_owner="Claude"), ctl=tt.FakeControls(), step=lambda t, o: 0)
        self.assertEqual(tq.PreflightProbe(r2).lease_status()[0], "ok")
        if os.name != "nt":
            self.assertIsNone(self.p.game_version())
        self.assertIsNone(tq.exe_file_version(os.path.join(self.d, "missing.exe")))


if __name__ == "__main__":
    unittest.main()
