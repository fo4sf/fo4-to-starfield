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
        root = tempfile.mkdtemp(prefix="fo4sf_snaps_")             # never the owner's C:\Modding\snapshots
        before = set()
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", hot, "-TestFire"],
                           capture_output=True, text=True, timeout=60, env=dict(os.environ, FO4SF_SNAPSHOT_ROOT=root))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pressed", r.stdout)
        import time
        for _ in range(30):
            after = set(os.listdir(root))
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


    def run_snapshot(self, out, answer):
        env = dict(os.environ, FO4SF_ASK_ANSWER=answer)          # stands in for the typed text: no window opens
        return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT, "-Out", out,
                               "-MaxAge", "1", "-Ask"], capture_output=True, text=True, timeout=120, env=env)

    def test_ask_saves_the_description_with_the_capture(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            r = self.run_snapshot(out, "the door at Red Rocket does not open")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("described=yes", r.stdout)
            state = json.load(open(os.path.join(out, "state.json"), encoding="utf-8-sig"))
            self.assertEqual(state["description"], "the door at Red Rocket does not open")
            self.assertEqual(open(os.path.join(out, "description.txt"), encoding="utf-8-sig").read().strip(),
                             "the door at Red Rocket does not open")
            self.assertTrue(os.path.exists(os.path.join(out, "screen.png")))

    def test_screenshot_only_when_the_box_is_left_empty(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            r = self.run_snapshot(out, "   ")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            state = json.load(open(os.path.join(out, "state.json"), encoding="utf-8-sig"))
            self.assertIsNone(state["description"])
            self.assertFalse(os.path.exists(os.path.join(out, "description.txt")))

    def test_the_ask_setting_switches_the_main_key(self):
        hot = os.path.join(ROOT, "scripts", "game", "look_hotkey.ps1")
        d = tempfile.mkdtemp(prefix="fo4sf_ask_")                 # the presses' snapshots land here after the test returns
        env = dict(os.environ, FO4SF_LOOK_SETTINGS=os.path.join(d, "look.settings.json"),
                   FO4SF_SNAPSHOT_ROOT=d, FO4SF_ASK_ANSWER=" ")   # " ": Windows drops an empty variable
        ps = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", hot]
        run = lambda *a: subprocess.run(ps + list(a), capture_output=True, text=True, timeout=60, env=env)
        self.assertIn("ask=False", run("-TestFire").stdout, "off by default: screenshots only")
        self.assertEqual(run("-SetAsk", "on").returncode, 0)
        self.assertIn("ask=True", run("-TestFire").stdout)
        self.assertIn("ask=True", run("-TestAsk").stdout, "the second key always asks")
        run("-SetAsk", "off")
        self.assertIn("ask=False", run("-TestFire").stdout)


if __name__ == "__main__":
    unittest.main()
