"""Process lookup failures must not authorize launch or establish game termination.

All process observations and actions are stand-ins; no host process table is read.
"""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.launcher import crashwatch  # noqa: E402

SPEC = importlib.util.spec_from_file_location("process_query_cli", ROOT / "scripts" / "launcher.py")
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)


class StartAttempt(Exception):
    """Trap a launch attempt without creating a process."""


class ProcessQueryTests(unittest.TestCase):
    def setUp(self):
        # Select the Windows adapter branch without changing global os.name.
        os_values = dict(vars(crashwatch.os))
        os_values["name"] = "nt"
        os_patch = mock.patch.object(crashwatch, "os", SimpleNamespace(**os_values))
        os_patch.start()
        self.addCleanup(os_patch.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.values = crashwatch.settings_mod.defaults()
        self.values.update({"crash_watch.enabled": False, "route": "steam", "crash_watch.settle_s": 1.})

        class Probe(crashwatch.System):
            def __init__(self):
                self.calls = []
                self.t = 1000.

            def now(self):
                return self.t

            def sleep(self, seconds):
                self.t += seconds

            def start_game(self, *args):
                self.calls.append("start_game")
                raise StartAttempt("synthetic launch trap; no process started")

            def open_process(self, pid):
                self.calls.append("open_fake_handle")
                return None

            def wait_exit(self, *args):
                raise AssertionError("Native wait must not run")

            def spawn(self, *args):
                raise AssertionError("ProcDump must not run")

            def run(self, *args):
                raise AssertionError("Settings subprocess must not run")

        self.Probe = Probe

    @staticmethod
    def failed(stdout=""):
        return subprocess.CompletedProcess(["tasklist"], 5, stdout, "synthetic lookup denied")

    @staticmethod
    def busy():
        return subprocess.CompletedProcess(
            ["tasklist"], 0, '"Starfield.exe","5678","Console","1","100 K"\n', "")

    def assert_query_refused(self, response):
        with mock.patch.object(crashwatch.subprocess, "run", return_value=response):
            with self.assertRaisesRegex(ValueError, "tasklist"):
                crashwatch.System().pids()

    def test_nonzero_empty_query_is_unknown_not_absent(self):
        self.assert_query_refused(self.failed())

    def test_nonzero_stale_rows_are_not_accepted_as_process_evidence(self):
        self.assert_query_refused(self.failed(self.busy().stdout))

    def test_unavailable_tasklist_has_the_existing_refusal_type(self):
        with mock.patch.object(crashwatch.subprocess, "run", side_effect=FileNotFoundError("synthetic missing tasklist")):
            with self.assertRaisesRegex(ValueError, "tasklist"):
                crashwatch.System().pids()

    def test_play_query_failure_precedes_settings_changes_and_start(self):
        probe = self.Probe()
        failure = None
        with mock.patch.object(crashwatch.subprocess, "run", return_value=self.failed()), \
                mock.patch.object(crashwatch, "apply_bridge") as bridge, \
                mock.patch.object(crashwatch, "apply_papyrus") as ini:
            try:
                crashwatch.play(self.values, str(self.base / "game"), system=probe, say=lambda _: None)
            except Exception as error:
                failure = error
        self.assertEqual(probe.calls, [], str(failure))
        bridge.assert_not_called()
        ini.assert_not_called()
        self.assertIsInstance(failure, ValueError)

    def test_actual_cli_returns_a_readable_refusal_before_start(self):
        probe = self.Probe()
        config = self.base / "settings.json"
        crashwatch.settings_mod.save(config, self.values)
        original = config.read_bytes()
        stdout = io.StringIO()
        code = failure = None
        with mock.patch.object(crashwatch, "System", return_value=probe), \
                mock.patch.object(crashwatch.subprocess, "run", return_value=self.failed()), \
                mock.patch.object(crashwatch, "apply_bridge"), \
                mock.patch.object(crashwatch, "apply_papyrus"), contextlib.redirect_stdout(stdout):
            try:
                code = CLI.main(["play", "--settings", str(config), "--starfield", str(self.base / "game")])
            except Exception as error:
                failure = error
        self.assertEqual(code, 2, str(failure))
        self.assertEqual(probe.calls, [])
        self.assertIn("tasklist", stdout.getvalue())
        self.assertEqual(config.read_bytes(), original)

    def test_no_handle_follow_lookup_failure_is_not_a_game_exit(self):
        probe = self.Probe()
        failure = result = None
        messages = []
        with mock.patch.object(crashwatch.subprocess, "run", side_effect=[self.busy(), self.busy(), self.busy(), self.failed()]):
            try:
                result = crashwatch._follow(self.values, probe, messages.append, probe.now(), None, 10., 10.)
            except Exception as error:
                failure = error
        self.assertIsInstance(failure, ValueError, str(result))
        self.assertFalse(any("Starfield ended" in line for line in messages))
        self.assertNotIn("start_game", probe.calls)

    def test_successful_running_process_remains_detected(self):
        with mock.patch.object(crashwatch.subprocess, "run", return_value=self.busy()):
            self.assertEqual(crashwatch.System().pids(), [5678])

    def test_successful_absence_remains_empty(self):
        response = subprocess.CompletedProcess(
            ["tasklist"], 0, "INFO: No tasks are running which match the specified criteria.\n", "")
        with mock.patch.object(crashwatch.subprocess, "run", return_value=response):
            self.assertEqual(crashwatch.System().pids(), [])


if __name__ == "__main__":
    unittest.main()
