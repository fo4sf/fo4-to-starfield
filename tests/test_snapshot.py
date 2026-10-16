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
    def test_a_failed_capture_never_leaves_a_stale_screen(self):
        # Codex's review of #175: a reused folder held the previous screen.png; the capture's exit code was ignored
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            os.makedirs(out)
            open(os.path.join(out, "screen.png"), "wb").write(b"OLD!")               # the previous call's picture
            stub = os.path.join(d, "shot_fails.ps1")
            open(stub, "w").write("param([string]$Out)\nexit 2\n")
            env = dict(os.environ, FO4SF_SHOT_SCRIPT=stub)
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT, "-Out", out, "-MaxAge", "1"],
                               capture_output=True, text=True, timeout=120, env=env)
            self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
            state = json.load(open(os.path.join(out, "state.json"), encoding="utf-8-sig"))
            self.assertIsNone(state["screen"])
            self.assertIn("exit 2", state["screen_error"])
            self.assertFalse(os.path.exists(os.path.join(out, "screen.png")), "the stale picture must be gone")

    def test_the_look_button_press_takes_a_snapshot(self):
        # look_hotkey.ps1 -TestFire runs the press handler once (no hotkey registered): a snapshot appears
        hot = os.path.join(ROOT, "scripts", "game", "look_hotkey.ps1")
        before = set(os.listdir(r"C:\Modding\snapshots")) if os.path.isdir(r"C:\Modding\snapshots") else set()
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", hot, "-TestFire"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pressed", r.stdout)
        import time
        for _ in range(30):
            after = set(os.listdir(r"C:\Modding\snapshots")) if os.path.isdir(r"C:\Modding\snapshots") else set()
            if after - before:
                break
            time.sleep(1)
        self.assertTrue(after - before, "no new snapshot folder")

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
