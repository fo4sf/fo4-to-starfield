"""snapshot.ps1: the owner's "look": a screenshot, the bridge's newest line and the log tail, nothing sent to the game."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "game", "snapshot.ps1")


@unittest.skipUnless(os.name == "nt", "PowerShell and the screen: Windows only")
class SnapshotTests(unittest.TestCase):
    def test_writes_state_and_screen_without_a_game(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            log = os.path.join(d, "fo4sf.0.log")
            open(log, "w").write("[12:00:00] FO4SF rt=1.0 pos=-2189.257080 -1553.485718 105.260857 ang=0.000000 cell=33557935 world=-16708427 loaded=true n=1\n")
            env = dict(os.environ, FO4SF_BRIDGE_LOG=log)
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT, "-Out", out,
                                "-Note", "test", "-MaxAge", "999999999"], capture_output=True, text=True, timeout=120, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("snapshot", r.stdout)
            state = json.load(open(os.path.join(out, "state.json"), encoding="utf-8-sig"))
            self.assertEqual(state["note"], "test")
            self.assertIn("game_running", state)
            self.assertTrue(os.path.exists(os.path.join(out, "screen.png")), "the screenshot")
            # the bridge line is read from $FO4SF_BRIDGE_LOG only when the tool is told; here the real log may or may not
            # exist, so only the shape is checked
            self.assertIn("bridge", state)


if __name__ == "__main__":
    unittest.main()
