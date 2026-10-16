"""testqueue.py pin-game-version (docs/ai/leader-core.md section 7): the queue's game_version pin the preflight gate
compares Starfield.exe against. Synthetic queues; no game, no Windows calls."""
import contextlib
import io
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
from fo4sf.core import preflight as pf  # noqa: E402


class PinGameVersionTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        tt.make_queue(self.d, n=1)

    def queue(self):
        with open(os.path.join(self.d, "queue.json"), encoding="utf-8") as f:
            return json.load(f)

    def pin(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = tq.main(["pin-game-version", "--queue", self.d, *argv])
        return code, out.getvalue().strip()

    def test_pins_by_version_and_the_gate_reads_it(self):
        before = self.queue()
        code, out = self.pin("--version", "1.16.244.0")
        self.assertEqual((code, out), (0, f"game_version 1.16.244.0 pinned in {os.path.join(self.d, 'queue.json')}"))
        after = self.queue()
        self.assertEqual(after.pop("game_version"), "1.16.244.0")
        self.assertEqual(after, before)                                   # nothing else in the queue changed
        r = tq.Runner(self.d, tt.args(starfield=os.path.join(self.d, "game")), ctl=tt.FakeControls(), step=lambda t, o: 0)
        probe = tq.PreflightProbe(r)
        with mock.patch.object(tq, "exe_file_version", return_value="1.16.244.0"):
            self.assertEqual(pf.check_game_version(probe).status, pf.PASS)
        with mock.patch.object(tq, "exe_file_version", return_value="1.17.0.0"):
            self.assertEqual(pf.check_game_version(probe).status, pf.FAIL)
        self.assertEqual(self.pin("--version", "1.16.244.0")[0], 0)        # the same pin again is fine

    def test_refusals(self):
        for bad in ("1.16.244.0 beta", "1.16.244", "1.16", "v1.16.244.0"):
            with self.assertRaises(SystemExit) as cm:
                self.pin("--version", bad)
            self.assertIn("four-part", str(cm.exception))
        self.assertNotIn("game_version", self.queue())
        self.pin("--version", "1.16.244.0")
        with self.assertRaises(SystemExit) as cm:
            self.pin("--version", "1.17.0.0")
        self.assertIn("already pins game_version 1.16.244.0", str(cm.exception))
        self.assertEqual(self.queue()["game_version"], "1.16.244.0")
        code, out = self.pin("--version", "1.17.0.0", "--force")
        self.assertEqual(code, 0)
        self.assertIn("(was 1.16.244.0)", out)
        self.assertEqual(self.queue()["game_version"], "1.17.0.0")
        with self.assertRaises(SystemExit) as cm:
            tq.main(["pin-game-version", "--queue", os.path.join(self.d, "nowhere"), "--version", "1.0"])
        self.assertIn("no queue.json", str(cm.exception))

    def test_reads_the_exe_on_windows_only(self):
        with mock.patch.object(tq, "exe_file_version", return_value=None):
            with self.assertRaises(SystemExit) as cm:
                self.pin("--starfield", os.path.join(self.d, "game"))
            self.assertIn("pass --version", str(cm.exception))
        with mock.patch.object(tq, "exe_file_version", return_value="1.16.244.0") as read:
            self.assertEqual(self.pin("--starfield", os.path.join(self.d, "game"))[0], 0)
        read.assert_called_once_with(os.path.join(self.d, "game", "Starfield.exe"))
        self.assertEqual(self.queue()["game_version"], "1.16.244.0")


if __name__ == "__main__":
    unittest.main()
