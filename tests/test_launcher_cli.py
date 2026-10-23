"""CLI of scripts/launcher.py settings/watch/play via isolated subprocess (#458 task 5).

Never starts a game, Steam, or ProcDump: every play/watch call uses --dry-run, and
LOCALAPPDATA is redirected so a missing --settings cannot touch the player's file.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER = os.path.join(ROOT, "scripts", "launcher.py")
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import settings  # noqa: E402

# Every key the settings command is expected to print, with the plain label on the same line.
EXPECTED_LINES = tuple(f"{settings.LABELS[k]}: {k} =" for k, _d, _t, _w in settings.SPEC)


class LauncherCliTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.dir = t.name
        self.settings = os.path.join(self.dir, "launcher_settings.json")
        self.local = os.path.join(self.dir, "Local")
        os.makedirs(self.local)
        self.starfield = os.path.join(self.dir, "Starfield")
        os.makedirs(self.starfield)
        open(os.path.join(self.starfield, "sfse_loader.exe"), "wb").close()   # play starts the game through SFSE
        self.dumps = os.path.join(self.dir, "dumps")
        os.makedirs(self.dumps)
        self.procdump = os.path.join(self.dir, "procdump64.exe")
        open(self.procdump, "wb").close()
        self.env = {**os.environ, "LOCALAPPDATA": self.local, "PYTHONPATH": ""}

    def run_cli(self, *args, timeout=30):
        return subprocess.run(
            [sys.executable, "-I", "-B", LAUNCHER, *args],
            capture_output=True, text=True, env=self.env, cwd=self.dir, timeout=timeout,
        )

    def run_settings(self, *extra):
        return self.run_cli("settings", "--settings", self.settings, *extra)

    def assert_no_traceback(self, result):
        blob = (result.stdout or "") + (result.stderr or "")
        self.assertNotIn("Traceback", blob, blob)

    def test_settings_prints_every_key_with_its_plain_label(self):
        r = self.run_settings()
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assert_no_traceback(r)
        for line in EXPECTED_LINES:
            self.assertIn(line, r.stdout, r.stdout)
        for key, label in settings.LABELS.items():
            self.assertIn(key, r.stdout)
            self.assertIn(label, r.stdout)

    def test_set_enabled_on_without_folder_or_procdump_saves_and_warns(self):
        # differs from #458 task 5: settings --set crash_watch.enabled=on without a
        # folder or ProcDump is not a nonzero exit. cmd_settings saves and prints
        # "play would refuse:" then returns 0. play/watch refuse later with exit 2.
        r = self.run_settings("--set", "crash_watch.enabled=on")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assert_no_traceback(r)
        self.assertIn("play would refuse: crash_watch.folder is not set (needed while the crash watcher is on)",
                      r.stdout)
        self.assertIn("crash_watch.procdump is not set (needed while the crash watcher is on)", r.stdout)
        with open(self.settings, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"crash_watch.enabled": True})
        play = self.run_cli("play", "--starfield", self.starfield, "--settings", self.settings, "--dry-run")
        self.assertEqual(play.returncode, 2, play.stderr + play.stdout)
        self.assert_no_traceback(play)
        self.assertIn("play:", play.stdout)
        self.assertIn("crash_watch.folder is not set (needed while the crash watcher is on)", play.stdout)

    def test_set_nan_is_refused_without_traceback(self):
        r = self.run_settings("--set", "crash_watch.min_free_gb=nan")
        self.assertEqual(r.returncode, 2, r.stderr + r.stdout)
        self.assert_no_traceback(r)
        self.assertIn("settings: crash_watch.min_free_gb: 'nan' is not a finite number", r.stdout)
        self.assertFalse(os.path.isfile(self.settings))

    def test_set_inf_is_refused_without_traceback(self):
        r = self.run_settings("--set", "crash_watch.min_free_gb=inf")
        self.assertEqual(r.returncode, 2, r.stderr + r.stdout)
        self.assert_no_traceback(r)
        self.assertIn("settings: crash_watch.min_free_gb: 'inf' is not a finite number", r.stdout)
        self.assertFalse(os.path.isfile(self.settings))

    def test_set_unknown_key_is_refused_without_traceback(self):
        r = self.run_settings("--set", "not_a_key=1")
        self.assertEqual(r.returncode, 2, r.stderr + r.stdout)
        self.assert_no_traceback(r)
        self.assertIn("settings: unknown setting 'not_a_key'", r.stdout)
        self.assertFalse(os.path.isfile(self.settings))

    def test_settings_file_whose_root_is_a_list_is_refused_without_traceback(self):
        with open(self.settings, "w", encoding="utf-8") as f:
            f.write("[]\n")
        with open(self.settings, "rb") as f:
            before = f.read()
        r = self.run_settings()
        self.assertEqual(r.returncode, 2, r.stderr + r.stdout)
        self.assert_no_traceback(r)
        self.assertIn("settings:", r.stdout)
        self.assertIn("expected an object of settings, found list", r.stdout)
        with open(self.settings, "rb") as f:
            self.assertEqual(f.read(), before)

    def test_set_then_reset_leaves_the_file_unchanged(self):
        with open(self.settings, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=1, sort_keys=True)
            f.write("\n")
        with open(self.settings, "rb") as f:
            before = f.read()
        on = self.run_settings("--set", "crash_watch.dump=full")
        self.assertEqual(on.returncode, 0, on.stderr + on.stdout)
        with open(self.settings, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"crash_watch.dump": "full"})
        off = self.run_settings("--set", "crash_watch.dump=mini")
        self.assertEqual(off.returncode, 0, off.stderr + off.stdout)
        with open(self.settings, "rb") as f:
            self.assertEqual(f.read(), before)

    def _arm_watcher(self):
        for pair in (
            "crash_watch.enabled=on",
            f"crash_watch.folder={self.dumps}",
            f"crash_watch.procdump={self.procdump}",
            "crash_watch.min_free_gb=0",
        ):
            r = self.run_settings("--set", pair)
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)

    def test_play_dry_run_prints_plan_and_exits_0_when_settings_are_valid(self):
        # the default route starts through SFSE and needs a listed runtime: this stand-in folder has none (Codex, #487)
        r = self.run_cli("play", "--starfield", self.starfield, "--settings", self.settings, "--dry-run")
        self.assertEqual(r.returncode, 2, r.stderr + r.stdout)
        self.assertIn("route=sfse:", r.stdout)
        self.assertEqual(self.run_settings("--set", "route=steam").returncode, 0)
        r = self.run_cli("play", "--starfield", self.starfield, "--settings", self.settings, "--dry-run")
        self.assert_no_traceback(r)
        self.assertFalse(os.path.isfile(os.path.join(self.starfield, "Starfield.exe")))
        self.assertEqual(os.listdir(self.dumps), [])
        if "Starfield is already running" in r.stdout:
            # differs from #458 task 5: play --dry-run still refuses while Starfield.exe
            # is running (crashwatch.play checks System.pids before printing the plan).
            self.assertEqual(r.returncode, 2, r.stderr + r.stdout)
            self.assertIn("play: Starfield is already running: close it first", r.stdout)
            return
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("bridge: unchanged", r.stdout)
        self.assertIn("papyrus logging: unchanged", r.stdout)
        self.assertIn("start: steam", r.stdout)
        self.assertIn("crash watcher: off", r.stdout)

    def test_watch_dry_run_prints_plan_and_exits_0_when_watcher_is_on(self):
        self._arm_watcher()
        r = self.run_cli("watch", "--settings", self.settings, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assert_no_traceback(r)
        self.assertIn("watch: the next Starfield.exe, attaching after 20 s", r.stdout)
        self.assertIn(f"crash watcher: on, mini dumps to {self.dumps}, a dump on every exit", r.stdout)
        self.assertEqual(os.listdir(self.dumps), [])

    def test_watch_refuses_when_watcher_is_off(self):
        # differs from #458 task 5: watch with the watcher off exits 2, not 1.
        # cmd_watch raises ValueError; launcher.main prints "watch: ..." and returns 2.
        r = self.run_cli("watch", "--settings", self.settings, "--dry-run")
        self.assertEqual(r.returncode, 2, r.stderr + r.stdout)
        self.assert_no_traceback(r)
        self.assertIn(
            "watch: crash watcher is off in the launcher settings (crash_watch.enabled): nothing to watch with",
            r.stdout,
        )


if __name__ == "__main__":
    unittest.main()
