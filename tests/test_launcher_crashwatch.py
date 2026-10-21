"""Launcher settings and the crash watcher that follows one game (src/fo4sf/launcher/settings.py, crashwatch.py), on a
stand-in for Windows: no game, no ProcDump, no Steam."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import crashwatch, settings  # noqa: E402


class FakeProc:
    def __init__(self, sys_, argv):
        self.sys, self.argv = sys_, argv

    def wait(self, timeout=None):
        if self.sys.procdump_hangs:
            raise crashwatch.subprocess.TimeoutExpired(self.argv, timeout)
        if self.sys.dump_name:
            with open(os.path.join(self.argv[-1], self.sys.dump_name), "wb") as f:
                f.write(b"MDMP")
        return 0


class FakeSystem:
    """A clock and a process table. `script` lists (pid, starts_at, ends_at, exit_code) after start_game."""

    def __init__(self, script, free=100.0, running=()):
        self.t, self.script, self.free = 1000.0, script, free
        self.started_at = None
        self.running = list(running)
        self.spawned, self.ran, self.calls = [], [], []
        self.procdump_hangs, self.dump_name = False, None
        self.toggle_status = {"off": [], "owned": []}
        self.toggle_code = 0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s

    def pids(self, image=crashwatch.GAME_EXE):
        if self.started_at is None:
            return list(self.running)
        el = self.t - self.started_at
        return [pid for pid, a, b, _c in self.script if a <= el < b]

    def start_game(self, route, starfield):
        self.calls.append(("start", route))
        self.started_at = self.t

    def open_process(self, pid):
        return pid

    def wait_exit(self, handle):
        for pid, _a, b, code in self.script:
            if pid == handle:
                self.t = max(self.t, self.started_at + b)
                return code
        return None

    def spawn(self, argv, log_path):
        self.spawned.append(argv)
        return FakeProc(self, argv)

    def run(self, argv):
        self.ran.append(argv[2:])
        if argv[2] == "status":
            return 0, json.dumps(self.toggle_status) + "\n"
        return self.toggle_code, "not changed: refused" if self.toggle_code else ""

    def free_gb(self, path):
        return self.free


class CrashWatchTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.dir = t.name
        self.dumps = os.path.join(t.name, "dumps")
        os.makedirs(self.dumps)
        self.procdump = os.path.join(t.name, "procdump64.exe")
        open(self.procdump, "wb").close()
        self.game = os.path.join(t.name, "Starfield")
        os.makedirs(self.game)
        self.said = []

    def values(self, **kw):
        v = settings.defaults()
        v.update({"crash_watch.enabled": True, "crash_watch.folder": self.dumps, "crash_watch.procdump": self.procdump})
        v.update({k.replace("__", "."): x for k, x in kw.items()})
        return v

    def play(self, values, system, **kw):
        return crashwatch.play(values, self.game, system=system, say=self.said.append, **kw)

    def log(self):
        with open(os.path.join(self.dumps, "crashwatch.log"), encoding="utf-8") as f:
            return f.read()

    def test_settings_default_changes_nothing_and_round_trip(self):
        d = settings.defaults()
        self.assertFalse(d["crash_watch.enabled"])
        self.assertEqual((d["bridge"], d["papyrus_logging"], d["crash_watch.dump"]), ("unchanged", "unchanged", "mini"))
        path = os.path.join(self.dir, "s", "launcher_settings.json")
        v = settings.assign(settings.load(path), ["crash_watch.enabled=on", "crash_watch.dump=full",
                                                  "crash_watch.min_free_gb=30"])
        settings.save(path, v)
        with open(path) as f:
            self.assertEqual(json.load(f), {"crash_watch.dump": "full", "crash_watch.enabled": True,
                                            "crash_watch.min_free_gb": 30.0})        # only what differs
        self.assertEqual(settings.load(path), v)
        for bad in (["nope=1"], ["crash_watch.dump=huge"], ["crash_watch.enabled=maybe"], ["bridge"],
                    ["crash_watch.min_free_gb=-1"]):
            with self.assertRaises(ValueError):
                settings.assign(v, bad)
        with open(path, "w") as f:
            json.dump({"crash_watch.enabeld": True}, f)
        with self.assertRaises(ValueError):                                          # a typo is never ignored
            settings.load(path)

    def test_problems(self):
        v = settings.assign(settings.defaults(), ["crash_watch.enabled=on", "bridge=on", "papyrus_logging=off"])
        p = settings.problems(v)
        self.assertEqual(len(p), 4, p)                 # folder, procdump, bridge needs logging, my_games

    def test_procdump_argv(self):
        v = self.values()
        self.assertEqual(crashwatch.procdump_argv(v, 42),
                         [self.procdump, "-accepteula", "-mm", "-e", "1", "-f", "80000003", "-n", "1", "42", self.dumps])
        v = self.values(crash_watch__dump="full", crash_watch__catch_assertion=False, crash_watch__dump_on_exit=True)
        self.assertEqual(crashwatch.procdump_argv(v, 7),
                         [self.procdump, "-accepteula", "-ma", "-e", "-t", "-n", "2", "7", self.dumps])
        self.assertNotIn("-w", crashwatch.procdump_argv(v, 7))       # never attach at the instant of start

    def test_watcher_arms_after_settling_and_logs_the_crash(self):
        sys_ = FakeSystem([(4242, 3, 600, 0xC0000005)])
        sys_.dump_name = "Starfield.exe_261021_120000.dmp"
        r = self.play(self.values(), sys_)
        self.assertEqual(r["pid"], 4242)
        self.assertEqual(r["exit"], "0xC0000005 ACCESS_VIOLATION")
        self.assertEqual(r["dumps"], ["Starfield.exe_261021_120000.dmp"])
        self.assertEqual(len(sys_.spawned), 1)
        self.assertEqual(sys_.spawned[0][-2], "4242")
        log = self.log()
        self.assertIn("armed: process 4242", log)
        self.assertIn("ended: process 4242, 0xC0000005 ACCESS_VIOLATION", log)
        self.assertIn("Starfield.exe_261021_120000.dmp", log)

    def test_silent_exit_is_logged_with_its_code(self):
        sys_ = FakeSystem([(10, 1, 900, 0xC0000409)])
        r = self.play(self.values(), sys_)
        self.assertEqual(r["dumps"], [])
        self.assertIn("0xC0000409 STACK_BUFFER_OVERRUN", self.log())
        self.assertIn("a crash code and no dump", self.log())
        sys_ = FakeSystem([(11, 1, 900, 0)])
        self.play(self.values(), sys_)
        self.assertIn("ended: process 11, 0x00000000 normal exit", self.log())

    def test_a_first_process_that_ends_early_is_skipped(self):
        # the first launch of a session can end within about 2 s; the next process is the game
        sys_ = FakeSystem([(1, 0, 2, 0), (2, 5, 400, 0)])
        r = self.play(self.values(), sys_)
        self.assertEqual((r["pid"], r["early"]), (2, [1]))
        self.assertEqual([a[-2] for a in sys_.spawned], ["2"])
        self.assertIn("process 1 ended before it settled", self.log())

    def test_game_that_never_stays_up(self):
        sys_ = FakeSystem([(1, 0, 2, 1)])
        r = self.play(self.values(), sys_, start_timeout_s=60)
        self.assertFalse(r["started"])
        self.assertEqual(sys_.spawned, [])

    def test_watcher_off_starts_the_game_without_procdump(self):
        sys_ = FakeSystem([(5, 0, 100, 0)])
        v = settings.defaults()
        r = self.play(v, sys_)
        self.assertTrue(r["started"])
        self.assertEqual(sys_.spawned, [])
        self.assertNotIn("dumps", r)
        self.assertFalse(os.path.exists(os.path.join(self.dumps, "crashwatch.log")))

    def test_procdump_still_writing_is_never_killed(self):
        sys_ = FakeSystem([(5, 0, 100, 0x80000003)])
        sys_.procdump_hangs = True
        r = self.play(self.values(), sys_)
        self.assertTrue(r["procdump_running"])
        self.assertTrue(any("left running" in s for s in self.said))

    def test_refusals_start_nothing(self):
        cases = [
            (self.values(crash_watch__procdump=os.path.join(self.dir, "missing.exe")), {}, "not found"),
            (self.values(), {"free": 3.0}, "GB free for dumps"),
            (self.values(), {"running": [99]}, "already running"),
            (self.values(route="exe"), {}, "Starfield.exe not found"),
        ]
        for v, kw, text in cases:
            sys_ = FakeSystem([(5, 0, 100, 0)], **kw)
            with self.subTest(text=text):
                with self.assertRaises(ValueError) as e:
                    self.play(v, sys_)
                self.assertIn(text, str(e.exception))
                self.assertEqual(sys_.calls, [])

    def test_dry_run_changes_nothing(self):
        sys_ = FakeSystem([(5, 0, 100, 0)])
        r = self.play(self.values(bridge="off"), sys_, dry_run=True)
        self.assertTrue(r["dry_run"])
        self.assertEqual((sys_.calls, sys_.ran, sys_.spawned), ([], [], []))

    def test_bridge_setting_goes_through_plugin_toggle(self):
        sys_ = FakeSystem([(5, 0, 100, 0)])
        sys_.toggle_status = {"off": [], "owned": ["FO4SFBridge.esm"]}
        self.play(self.values(bridge="off"), sys_)
        self.assertEqual(sys_.ran[1][:3], ["off", "--plugins", "FO4SFBridge.esm"])
        sys_ = FakeSystem([(5, 0, 100, 0)])
        sys_.toggle_status = {"off": ["FO4SFBridge.esm"], "owned": ["FO4SFBridge.esm"]}
        self.play(self.values(bridge="off"), sys_)
        self.assertEqual(len(sys_.ran), 1)                         # already held: status only
        sys_ = FakeSystem([(5, 0, 100, 0)])
        sys_.toggle_status = {"off": ["FO4SFBridge.esm"], "owned": ["FO4SFBridge.esm"]}
        self.play(self.values(bridge="on"), sys_)
        self.assertEqual(sys_.ran[1][:3], ["on", "--plugins", "FO4SFBridge.esm"])
        sys_ = FakeSystem([(5, 0, 100, 0)])
        sys_.toggle_status = {"off": [], "owned": ["FO4SFBridge.esm"]}
        sys_.toggle_code = 1
        with self.assertRaises(ValueError):
            self.play(self.values(bridge="off"), sys_)
        self.assertEqual(sys_.calls, [])                           # refused before the game starts
        sys_ = FakeSystem([(5, 0, 100, 0)])
        self.play(self.values(bridge="off"), sys_)                 # not installed: nothing to do
        self.assertEqual(len(sys_.ran), 1)

    def test_papyrus_setting_edits_only_its_keys_and_keeps_a_copy(self):
        mg = os.path.join(self.dir, "My Games", "Starfield")
        os.makedirs(mg)
        ini = os.path.join(mg, "StarfieldCustom.ini")
        with open(ini, "w") as f:
            f.write("[General]\nsLanguage=en\n[Papyrus]\nbEnableLogging=1\nbEnableTrace=1\nfOther=2\n[Display]\nx=1\n")
        self.play(self.values(papyrus_logging="off", my_games=mg), FakeSystem([(5, 0, 100, 0)]))
        with open(ini) as f:
            self.assertEqual(f.read(), "[General]\nsLanguage=en\n[Papyrus]\nbEnableLogging=0\nbEnableTrace=0\nfOther=2\n"
                                       "bLoadDebugInformation=0\n[Display]\nx=1\n")
        self.assertEqual(len([n for n in os.listdir(mg) if ".bak-" in n]), 1)
        new, changed = crashwatch.set_papyrus("", True)
        self.assertEqual((new, changed), ("[Papyrus]\nbEnableLogging=1\nbEnableTrace=1\nbLoadDebugInformation=1\n", True))
        self.assertFalse(crashwatch.set_papyrus(new, True)[1])

    def test_exit_names(self):
        self.assertEqual(crashwatch.exit_name(-1073741819), "0xC0000005 ACCESS_VIOLATION")    # signed as Windows gives
        self.assertIn("not a known crash code", crashwatch.exit_name(0x1234))
        self.assertIn("unknown", crashwatch.exit_name(None))

    def test_cli(self):
        spec = importlib.util.spec_from_file_location("launcher_cli", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        path = os.path.join(self.dir, "cli.json")
        self.assertEqual(cli.main(["settings", "--settings", path, "--set", "crash_watch.enabled=on"]), 0)
        self.assertEqual(cli.main(["settings", "--settings", path, "--set", "crash_watch.dump=enormous"]), 2)
        self.assertTrue(settings.load(path)["crash_watch.enabled"])
        self.assertEqual(cli.main(["play", "--starfield", self.game, "--settings", path, "--dry-run"]), 2)  # no folder
        cli.main(["settings", "--settings", path, "--set", f"crash_watch.folder={self.dumps}",
                  "--set", f"crash_watch.procdump={self.procdump}",
                  "--set", "crash_watch.min_free_gb=0"])           # the real disk check: CI runners have little free
        self.assertEqual(cli.main(["play", "--starfield", self.game, "--settings", path, "--dry-run"]), 0)


if __name__ == "__main__":
    unittest.main()
