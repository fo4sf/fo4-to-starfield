"""testqueue.py run --preflight (docs/ai/leader-core.md section 7, task T3): off by default and then absent from the
run; on, the checklist goes to run.log before the first launch and one FAIL or UNKNOWN stops the run before any step,
in a dry run too, with a blocker_opened in the ledger when there is one. The PC-side probe is exercised on this box
only where it reads nothing Windows-specific. Synthetic data; no game."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
sys.path.insert(0, os.path.join(ROOT, "src"))
import testqueue as tq  # noqa: E402
import test_testqueue as tt  # noqa: E402
import test_core_preflight as tcp  # noqa: E402  (FakeProbe)
from fo4sf.core import controller as c  # noqa: E402
from fo4sf.core.model import Event  # noqa: E402
from fo4sf.core.state import Ledger, fold  # noqa: E402


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


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
            with open(os.path.join(saves, "Save12_fo4sf_test_abcd1234_x.sfs"), "wb") as f:
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
