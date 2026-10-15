"""copy_attempt_logs: bridge.log always, papyrus.log when the game's Papyrus.0.log exists beside the bridge log's folder."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import testqueue  # noqa: E402


class AttemptLogsTests(unittest.TestCase):
    def layout(self, tmp, papyrus):
        user = os.path.join(tmp, "Logs", "Script", "User")
        os.makedirs(user)
        bridge = os.path.join(user, "fo4sf.0.log")
        open(bridge, "w").write("[12:00:00] FO4SF rt=1 pos=0 0 0\n")
        if papyrus:
            open(os.path.join(tmp, "Logs", "Script", "Papyrus.0.log"), "w").write("[12:00:00] error: stack\n")
        out = os.path.join(tmp, "a1")
        os.makedirs(out)
        return bridge, out

    def test_both_logs_copied(self):
        with tempfile.TemporaryDirectory() as tmp:
            bridge, out = self.layout(tmp, papyrus=True)
            msgs = []
            testqueue.copy_attempt_logs(bridge, out, msgs.append)
            self.assertEqual(msgs, [])
            self.assertIn("FO4SF rt=1", open(os.path.join(out, "bridge.log")).read())
            self.assertIn("error: stack", open(os.path.join(out, "papyrus.log")).read())

    def test_no_papyrus_log_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            bridge, out = self.layout(tmp, papyrus=False)
            msgs = []
            testqueue.copy_attempt_logs(bridge, out, msgs.append)
            self.assertEqual(msgs, [])
            self.assertTrue(os.path.exists(os.path.join(out, "bridge.log")))
            self.assertFalse(os.path.exists(os.path.join(out, "papyrus.log")))

    def test_missing_bridge_log_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a1")
            os.makedirs(out)
            msgs = []
            testqueue.copy_attempt_logs(os.path.join(tmp, "none", "fo4sf.0.log"), out, msgs.append)
            self.assertEqual(len(msgs), 1)
            self.assertIn("bridge log not copied", msgs[0])


if __name__ == "__main__":
    unittest.main()
