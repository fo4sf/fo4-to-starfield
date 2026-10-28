"""The deployment gate (docs/ai/leader-core.md section 7, task T3): every check with a synthetic PASS and FAIL (and
UNKNOWN where a reading can be missing), the refusal and its ledger line. A fake probe; nothing touches a PC."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.core import preflight as pf  # noqa: E402
from fo4sf.core.model import Event  # noqa: E402

SHA = "ab" * 32
OTHER = "cd" * 32
PAPYRUS_OK = "[General]\nsLanguage=en\n[Papyrus]\nbEnableLogging=1\nbEnableTrace=1\nbLoadDebugInformation=1\n"
PAPYRUS_OFF = "[Papyrus]\nbEnableLogging=0\nbEnableTrace=1\n"
PAPYRUS_PARTIAL = "[Papyrus]\nbEnableLogging=1\n"


class FakeProbe:
    """Every reading a PASS by default; a test flips one."""

    def __init__(self, **kw):
        self.queue = {"plugin_sha256": SHA, "staging": "C:/staging/b1", "save": "fo4sf_test_abababab",
                      "plugin_index": "02", "game_version": "1.16.244.0"}
        self.state = {}
        self.staged = SHA
        self.manifest = {"complete": True, "files": ["FO4Port.esm", "FO4Port - Main.ba2"], "plugins_restore_pending": True,
                         "artifacts": {"FO4Port.esm": {"sha256": SHA}, "FO4Port - Main.ba2": {"sha256": "ee" * 32}}}
        self.inputs = {"FO4SFExp.esm": "11" * 32}
        self.record = None
        self.data_files = {"FO4Port.esm": SHA, "FO4SFExp.esm": "11" * 32}      # what is on disk under Data
        self.lines = ["*FO4Port.esm"]
        self.masters = {}
        self.version = "1.16.244.0"
        self.ledger_version = None
        self.lease = ("ok", "Claude holds the lease")
        self.stops = [("q/STOP", True, True), ("STOP_ALL", True, True), ("state/testqueue.STOP", False, False)]
        self.guard = ("running", "guardian.db")
        self.save = True
        self.inis = [PAPYRUS_OK]
        self.__dict__.update(kw)

    def staged_plugin_sha256(self):
        return self.staged

    def deploy_manifest(self):
        return self.manifest

    def experiment_inputs(self, exp_dir, plugins):
        if isinstance(self.inputs, Exception):
            raise self.inputs
        return self.inputs

    def install_record(self):
        return self.record

    def data_file_sha256(self, rel):
        return self.data_files.get(rel)

    def plugins_txt_lines(self):
        return self.lines

    def plugin_masters(self, name):
        return self.masters.get(name, [])

    def implicit(self, name):
        return name.casefold() in ("starfield.esm", "blueprintships-starfield.esm")

    def game_version(self):
        return self.version

    def ledger_game_version(self):
        return self.ledger_version

    def lease_status(self):
        return self.lease

    def stop_dirs(self):
        return self.stops

    def guardian(self):
        return self.guard

    def save_present(self, name):
        return self.save

    def ini_texts(self):
        return self.inis


def pinned(**extra):
    q = FakeProbe().queue
    q["experiment_identity"] = {"exp_dir": "C:/staging/exp", "plugins": ["FO4SFExp.esm"], "inputs": {"FO4SFExp.esm": "11" * 32}}
    q.update(extra)
    return q


def one(name, **kw):
    return pf.run_gate(FakeProbe(**kw), [name]).checks[0]


class GateTests(unittest.TestCase):
    def test_every_check_passes_on_a_clean_pc(self):
        rep = pf.run_gate(FakeProbe())
        self.assertEqual([c.name for c in rep.checks], list(pf.CHECKS))
        self.assertTrue(rep.ok, rep.lines())
        self.assertEqual(rep.lines()[0], "preflight: every check passed")
        self.assertEqual(rep.failing, [])

    def test_one_unknown_refuses_like_a_fail(self):
        rep = pf.run_gate(FakeProbe(version=None))
        self.assertFalse(rep.ok)
        self.assertEqual([c.name for c in rep.failing], ["game_version"])
        self.assertTrue(rep.lines()[0].startswith("preflight: REFUSED: game_version UNKNOWN"))
        ev = rep.blocker_event("testqueue:Claude")
        self.assertIsInstance(ev, Event)
        self.assertEqual((ev.ev, ev.fields["blocker"], ev.fields["checks"]["game_version"]), ("blocker_opened", "preflight", "UNKNOWN"))
        self.assertEqual(len(ev.fields["evidence"]), 1)
        self.assertIn("not readable", ev.fields["evidence"][0])

    def test_a_reading_that_raises_is_unknown_and_the_rest_still_run(self):
        rep = pf.run_gate(FakeProbe(inputs=OSError("disk gone"), queue=pinned()))
        by = {c.name: c for c in rep.checks}
        self.assertEqual(by["experiment"].status, pf.UNKNOWN)
        self.assertIn("OSError: disk gone", by["experiment"].detail)
        self.assertEqual(by["pin"].status, pf.PASS)
        self.assertEqual(len(rep.checks), len(pf.CHECKS))


class CheckTests(unittest.TestCase):
    def test_pin(self):
        self.assertEqual(one("pin").status, pf.PASS)
        self.assertEqual(one("pin", staged=None).status, pf.UNKNOWN)
        c = one("pin", staged=OTHER)
        self.assertEqual((c.status, c.expected, c.observed), (pf.FAIL, SHA, OTHER))
        self.assertEqual(one("pin", queue={"staging": "x"}).status, pf.UNKNOWN)

    def test_deploy(self):
        self.assertEqual(one("deploy").status, pf.PASS)
        self.assertEqual(one("deploy", manifest=None).status, pf.PASS)              # deployed at the launch
        self.assertEqual(one("deploy", manifest={"complete": False, "artifacts": {}}).status, pf.FAIL)
        c = one("deploy", manifest={"complete": True, "artifacts": {"FO4Port.esm": {"sha256": OTHER}}}, data_files={"FO4Port.esm": OTHER})
        self.assertEqual(c.status, pf.FAIL)
        self.assertIn("wrong build", c.detail)
        c = one("deploy", queue={"staging": "x"})                                    # nothing pinned: say so, no claim
        self.assertEqual((c.status, "pins nothing" in c.detail), (pf.PASS, True))
        self.assertEqual(one("deploy", manifest={"complete": True, "artifacts": {}}).status, pf.UNKNOWN)
        # Codex on #182: deploy_starfield.py uninstall removed FO4Port.esm, kept a changed archive and the manifest,
        # complete still true with the plugin's old hash: the record is no proof the pinned plugin is in the game folder
        half = dict(FakeProbe().manifest, files=["FO4Port - Main.ba2"])
        c = one("deploy", manifest=half, data_files={})
        self.assertEqual(c.status, pf.FAIL)
        self.assertIn("half-finished uninstall: FO4Port.esm removed", c.detail)
        self.assertEqual((c.expected, c.observed), (["FO4Port - Main.ba2", "FO4Port.esm"], ["FO4Port - Main.ba2"]))

    def test_deploy_of_a_queue_that_tests_the_installed_port(self):
        # plan --port installed (2026-10-28): the run tests the install as it is, pinned at plan time, not the staging
        q = dict(FakeProbe().queue, port={"mode": "installed", "plugin_sha256": OTHER})
        installed = {"complete": True, "files": ["FO4Port.esm"], "artifacts": {"FO4Port.esm": {"sha256": OTHER}}}
        c = one("deploy", queue=q, manifest=installed, data_files={"FO4Port.esm": OTHER})
        self.assertEqual(c.status, pf.PASS, c.detail)                         # another build than the staging's
        self.assertEqual(one("deploy", queue=q).status, pf.FAIL)              # the staging's build is not the pin
        c = one("deploy", queue=q, manifest=None)
        self.assertEqual(c.status, pf.FAIL)                                   # nothing to test, nothing deployed later
        self.assertIn("--port installed", c.detail)
        c = one("deploy", manifest=dict(FakeProbe().manifest, files=[]), data_files={})   # the files gone, the manifest not
        self.assertEqual((c.status, "nothing kept" in c.detail), (pf.FAIL, True))
        self.assertEqual(one("deploy", manifest=dict(FakeProbe().manifest, cleanup_pending=True)).status, pf.FAIL)
        c = one("deploy", data_files={})                                             # a stale record: the plugin is not there
        self.assertEqual((c.status, "is not there" in c.detail), (pf.FAIL, True))
        c = one("deploy", data_files={"FO4Port.esm": OTHER})                        # on disk not what the manifest recorded
        self.assertEqual((c.status, "changed since the deploy" in c.detail, c.observed), (pf.FAIL, True, OTHER))
        self.assertEqual(one("deploy", manifest=dict(FakeProbe().manifest, plugins_restore_pending=False)).status, pf.PASS)
        legacy = {"complete": True, "artifacts": {"FO4Port.esm": {"sha256": SHA}}}   # no files list: judged by the bytes
        self.assertEqual(one("deploy", manifest=legacy).status, pf.PASS)
        self.assertEqual(one("deploy", manifest=legacy, data_files={}).status, pf.FAIL)

    def test_experiment(self):
        self.assertEqual(one("experiment").status, pf.PASS)                       # no experiment at all
        self.assertEqual(one("experiment", queue=pinned()).status, pf.PASS)         # staged as planned, installs at launch
        c = one("experiment", queue=pinned(), inputs={"FO4SFExp.esm": OTHER})
        self.assertEqual(c.status, pf.FAIL)
        self.assertIn("changed since planning", c.detail)
        leftover = {"exp_dir": "C:/staging/terrain_core64c", "plugins": ["FO4TerrainCore.esm"], "source_inputs": {}, "complete": True}
        c = one("experiment", record=leftover)                                     # a plain plan queue, an old install
        self.assertEqual(c.status, pf.FAIL)
        self.assertIn("pins no experiment but one is installed", c.detail)
        self.assertEqual(one("experiment", record={"error": "PermissionError"}).status, pf.UNKNOWN)
        q = pinned()
        del q["experiment_identity"]
        q["pre_launch"] = ["python", "exp_install.py"]
        self.assertEqual(one("experiment", queue=q).status, pf.UNKNOWN)
        good = {"exp_dir": "C:/staging/exp", "plugins": ["FO4SFExp.esm"], "source_inputs": {"FO4SFExp.esm": "11" * 32},
                "files": {"FO4SFExp.esm": "11" * 32}, "complete": True, "cleanup_pending": None}
        self.assertEqual(one("experiment", queue=pinned(), record=good).status, pf.PASS)
        self.assertEqual(one("experiment", queue=pinned(), record=dict(good, complete=False)).status, pf.FAIL)
        self.assertEqual(one("experiment", queue=pinned(), record=dict(good, exp_dir="C:/staging/other")).status, pf.FAIL)
        self.assertEqual(one("experiment", queue=pinned(), record=dict(good, plugins=["Other.esm"])).status, pf.FAIL)
        self.assertEqual(one("experiment", queue=pinned(), record=dict(good, source_inputs={})).status, pf.FAIL)
        self.assertEqual(one("experiment", queue=pinned(), record={"error": "PermissionError"}).status, pf.UNKNOWN)
        # Codex on #182: exp_install.py uninstall removed the plugin, kept a changed file and the record, complete still
        # true and cleanup_pending set, the staged inputs still the pinned ones: the record is not the installed inventory
        half = dict(good, cleanup_pending=True, files={"Terrain/W.btd": "22" * 32})
        c = one("experiment", queue=pinned(), record=half, data_files={"Terrain/W.btd": "22" * 32})
        self.assertEqual((c.status, "cleanup pending" in c.detail), (pf.FAIL, True))
        c = one("experiment", queue=pinned(), record=dict(good, files={"Terrain/W.btd": "22" * 32}),   # the flag lost too
                data_files={"Terrain/W.btd": "22" * 32})
        self.assertEqual((c.status, "owns no installed ['FO4SFExp.esm']" in c.detail), (pf.FAIL, True))
        c = one("experiment", queue=pinned(), record=good, data_files={})            # a stale record: the plugin is gone
        self.assertEqual((c.status, "file missing" in c.detail), (pf.FAIL, True))
        c = one("experiment", queue=pinned(), record=good, data_files={"FO4SFExp.esm": OTHER})
        self.assertEqual((c.status, "changed since the install" in c.detail, c.observed), (pf.FAIL, True, OTHER))
        self.assertEqual(one("experiment", queue=pinned(), record=dict(good, files=None)).status, pf.UNKNOWN)
        # a healthy record keeps plugins_restore_pending (exp_install.py never clears it after a completed activation)
        self.assertEqual(one("experiment", queue=pinned(), record=dict(good, plugins_restore_pending=True)).status, pf.PASS)
        packed = dict(good, files={"FO4SFExp.esm": "11" * 32, "FO4SFExp - Main.ba2": "33" * 32})
        self.assertEqual(one("experiment", queue=pinned(), record=packed,
                             data_files={"FO4SFExp.esm": "11" * 32, "FO4SFExp - Main.ba2": "33" * 32}).status, pf.PASS)
        self.assertEqual(one("experiment", queue=pinned(), record=packed, data_files={"FO4SFExp.esm": "11" * 32}).status, pf.FAIL)

    def test_plugins_active(self):
        self.assertEqual(one("plugins_active", lines=None).status, pf.UNKNOWN)
        c = one("plugins_active", queue=pinned(), lines=["*FO4Port.esm"])
        self.assertEqual(c.status, pf.PASS)
        self.assertIn("installed at the launch: FO4SFExp.esm", c.detail)
        c = one("plugins_active", queue=pinned(), lines=["*FO4Port.esm", "FO4SFExp.esm"])
        self.assertEqual(c.status, pf.FAIL)
        self.assertIn("inactive in Plugins.txt: FO4SFExp.esm", c.detail)
        c = one("plugins_active", queue=pinned(), lines=["*FO4Port.esm", "*FO4SFExp.esm", "*fo4sfexp.esm"])
        self.assertEqual(c.status, pf.FAIL)
        self.assertIn("duplicated", c.detail)
        c = one("plugins_active", queue=pinned(bridge={"dir": "b"}), lines=["*FO4SFExp.esm", "*FO4Port.esm", "FO4SFBridge.esm"])
        self.assertEqual((c.status, "FO4SFBridge.esm" in c.detail), (pf.FAIL, True))
        c = one("plugins_active", lines=[])                                           # a PC before its first deploy
        self.assertEqual(c.status, pf.PASS)

    def test_load_order(self):
        masters = {"FO4SFExp.esm": ["Starfield.esm", "FO4Port.esm", "FO4TerrainCore.esm"]}
        self.assertEqual(one("load_order", lines=None).status, pf.UNKNOWN)
        c = one("load_order", queue=pinned(), masters=masters, lines=["*FO4SFExp.esm", "*FO4Port.esm"])
        self.assertEqual(c.status, pf.FAIL)
        self.assertIn("FO4SFExp.esm needs FO4TerrainCore.esm", c.detail)
        c = one("load_order", queue=pinned(), masters=masters, lines=["*FO4SFExp.esm", "*FO4Port.esm", "*FO4TerrainCore.esm"])
        self.assertEqual(c.status, pf.PASS)
        self.assertIn("exp_install.py order moves at the launch: FO4SFExp.esm before its master FO4Port.esm", c.detail)
        self.assertEqual(c.observed, ["fo4sfexp.esm", "fo4port.esm", "fo4terraincore.esm"])
        c = one("load_order", queue=pinned(), masters={"FO4SFExp.esm": ["FO4Port.esm"]}, lines=["*FO4SFExp.esm"])
        self.assertEqual(c.status, pf.PASS)                                          # FO4Port.esm comes with the deploy
        q = pinned()
        q["experiment_identity"]["plugins"] = ["FO4TerrainCore.esm", "FO4SliceRedRocketCore.esm"]
        c = one("load_order", queue=q, masters={"FO4SliceRedRocketCore.esm": ["FO4TerrainCore.esm", "FO4Port.esm"]}, lines=[])
        self.assertEqual(c.status, pf.PASS)                                          # a sibling of the pin installs at the launch
        c = one("load_order", queue=q, masters={"FO4SliceRedRocketCore.esm": ["Other.esm"]}, lines=[])
        self.assertEqual(c.status, pf.FAIL)
        c = one("load_order", queue=pinned(bridge={"dir": "b"}), lines=["*FO4SFBridge.esm", "*FO4Port.esm"])
        self.assertEqual(c.status, pf.PASS)
        self.assertIn("the bridge is not last", c.detail)
        self.assertIn("not verified", c.detail)                                      # the absolute index stays unresolved

    def test_game_version(self):
        self.assertEqual(one("game_version").status, pf.PASS)
        q = dict(FakeProbe().queue)
        del q["game_version"]
        self.assertEqual(one("game_version", queue=q).status, pf.UNKNOWN)
        self.assertEqual(one("game_version", queue=q, ledger_version="1.16.244.0").status, pf.PASS)
        c = one("game_version", version=None)
        self.assertEqual(c.status, pf.UNKNOWN)
        self.assertIn("pin-game-version --version", c.detail)
        c = one("game_version", version="1.17.0.0")
        self.assertEqual((c.status, c.expected, c.observed), (pf.FAIL, "1.16.244.0", "1.17.0.0"))

    def test_lease(self):
        self.assertEqual(one("lease").status, pf.PASS)
        c = one("lease", lease=("fail", "held by Codex"))
        self.assertEqual((c.status, c.detail), (pf.FAIL, "held by Codex"))
        self.assertEqual(one("lease", lease=("unknown", "no lease folder")).status, pf.UNKNOWN)

    def test_stop_controls(self):
        self.assertEqual(one("stop_controls").status, pf.PASS)
        self.assertEqual(one("stop_controls", stops=[]).status, pf.UNKNOWN)
        c = one("stop_controls", stops=[("q/STOP", True, False), ("STOP_ALL", True, True)])
        self.assertEqual((c.status, "q/STOP" in c.detail), (pf.FAIL, True))
        self.assertEqual(one("stop_controls", stops=[("q/STOP", True, True), ("STOP_ALL", False, False)]).status, pf.FAIL)
        self.assertEqual(one("stop_controls", stops=[("q/STOP", True, True), ("STOP_ALL", True, True), ("s", True, False)]).status, pf.FAIL)

    def test_guardian(self):
        self.assertEqual(one("guardian").status, pf.PASS)
        for mode in ("missing", "unreadable", "paused", "stopped"):
            c = one("guardian", guard=(mode, "db"))
            self.assertEqual(c.status, pf.FAIL, mode)

    def test_recovery_save(self):
        self.assertEqual(one("recovery_save").status, pf.PASS)
        self.assertEqual(one("recovery_save", save=None).status, pf.UNKNOWN)
        self.assertEqual(one("recovery_save", save=False).status, pf.PASS)           # created on the first launch
        c = one("recovery_save", save=False, state={"save_file": True})
        self.assertEqual((c.status, "is gone" in c.detail), (pf.FAIL, True))
        self.assertEqual(one("recovery_save", queue={}).status, pf.UNKNOWN)

    def test_log_capture(self):
        self.assertEqual(one("log_capture").status, pf.PASS)                         # no bridge: nothing to capture
        self.assertEqual(one("log_capture", queue=pinned(bridge={"dir": "b"})).status, pf.PASS)
        self.assertEqual(one("log_capture", queue=pinned(bridge={"dir": "b"}), inis=[]).status, pf.UNKNOWN)
        c = one("log_capture", queue=pinned(bridge={"dir": "b"}), inis=[PAPYRUS_OFF, "[Display]\nx=1\n"])
        self.assertEqual(c.status, pf.FAIL)
        self.assertIn("make_bridge.py ini", c.detail)
        self.assertEqual(one("log_capture", queue=pinned(bridge={"dir": "b"}), inis=[PAPYRUS_OFF, PAPYRUS_OK]).status, pf.PASS)
        # the override (last) turns logging off although the game folder's ini (first) sets it: not in effect
        self.assertEqual(one("log_capture", queue=pinned(bridge={"dir": "b"}), inis=[PAPYRUS_OK, PAPYRUS_OFF]).status, pf.FAIL)
        # an override that sets only one key leaves the others from the game folder's ini in effect
        self.assertEqual(one("log_capture", queue=pinned(bridge={"dir": "b"}), inis=[PAPYRUS_OK, PAPYRUS_PARTIAL]).status, pf.PASS)

    def test_papyrus_keys_parse(self):
        self.assertTrue(pf.papyrus_logging_on(PAPYRUS_OK))
        self.assertTrue(pf.papyrus_logging_on("[papyrus]\n benablelogging = 1 \nbEnableTrace=1\nbLoadDebugInformation=1\n[Other]\nbEnableLogging=0\n"))
        self.assertFalse(pf.papyrus_logging_on(PAPYRUS_OFF))
        self.assertFalse(pf.papyrus_logging_on("[General]\nbEnableLogging=1\nbEnableTrace=1\nbLoadDebugInformation=1\n"))
        self.assertFalse(pf.papyrus_logging_on(""))
        self.assertTrue(pf.papyrus_logging_on([PAPYRUS_OK]))
        self.assertFalse(pf.papyrus_logging_on([PAPYRUS_OK, PAPYRUS_OFF]))
        self.assertEqual(pf.papyrus_keys(PAPYRUS_OFF), {"benablelogging": "0", "benabletrace": "1"})


if __name__ == "__main__":
    unittest.main()
