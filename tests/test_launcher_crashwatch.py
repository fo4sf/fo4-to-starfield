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
    def __init__(self, sys_, argv, out_path=None):
        self.sys, self.argv, self.out_path = sys_, argv, out_path

    def poll(self):
        return self.sys.procdump_quits

    def wait(self, timeout=None):
        if self.sys.procdump_hangs:
            raise crashwatch.subprocess.TimeoutExpired(self.argv, timeout)
        if self.sys.dump_name:
            with open(os.path.join(self.argv[-1], self.sys.dump_name), "wb") as f:
                f.write(b"MDMP")
            with open(self.out_path, "wb") as f:              # ProcDump's own report, in UTF-16 as on the PC
                f.write(("[12:00:00]Dump 1 initiated\r\n" + ("[12:00:02]Dump 1 complete: 145 MB written in 2.0 seconds\r\n"
                         if self.sys.dump_completes else "[12:00:02]Dump 1 error writing dump file\r\n"))
                        .encode("utf-16-le"))
        return 0


class FakeSystem:
    """A clock and a process table. `script` lists (pid, starts_at, ends_at, exit_code) after start_game."""

    def __init__(self, script, free=100.0, running=()):
        self.t, self.script, self.free = 1000.0, script, free
        self.started_at = None
        self.running = list(running)
        self.spawned, self.ran, self.calls = [], [], []
        self.procdump_hangs, self.dump_name = False, None
        self.dump_completes = True
        self.procdump_quits, self.spawn_error = None, None
        self.refuse_handle = False
        self.toggle_status = {"off": [], "owned": []}
        self.toggle_out = "back on: FO4SFBridge.esm"
        self.toggle_code = 0
        self.active = {"fo4sfbridge.esm"}

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
        return None if self.refuse_handle else pid

    def wait_exit(self, handle):
        for pid, _a, b, code in self.script:
            if pid == handle:
                self.t = max(self.t, self.started_at + b)
                return code
        return None

    def spawn(self, argv, log_path):
        if self.spawn_error:
            raise self.spawn_error
        self.spawned.append(argv)
        return FakeProc(self, argv, log_path)

    def run(self, argv):
        self.ran.append(argv[2:])
        if argv[2] == "status":
            return 0, json.dumps(self.toggle_status) + "\n"
        if self.toggle_code:
            return self.toggle_code, "not changed: refused"
        return 0, self.toggle_out if argv[2] == "on" else "held off: FO4SFBridge.esm"

    def free_gb(self, path):
        return self.free.pop(0) if isinstance(self.free, list) else self.free

    def plugins_active(self):
        return self.active


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
        self.assertTrue(d["crash_watch.dump_on_exit"])           # the owner's choice: silent exits leave a dump
        self.assertEqual(set(settings.LABELS), set(settings.KEYS))
        shown = "\n".join(settings.describe(d))
        self.assertIn("Crash dump on every exit (off = log only): crash_watch.dump_on_exit = true", shown)
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

    def test_numbers_must_be_finite(self):
        for key in ("crash_watch.min_free_gb", "crash_watch.settle_s"):
            for bad in ("nan", "inf", "-inf", "NaN"):
                with self.assertRaises(ValueError):
                    settings.assign(settings.defaults(), [f"{key}={bad}"])
        self.assertEqual(settings.assign(settings.defaults(), ["crash_watch.settle_s=5"])["crash_watch.settle_s"], 5.0)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.json")
            with open(path, "w") as f:
                f.write('{"crash_watch.min_free_gb": NaN}')
            with self.assertRaises(ValueError):
                settings.load(path)
            for root in ("[]", '"on"', "3"):
                with open(path, "w") as f:
                    f.write(root)
                with self.assertRaises(ValueError):
                    settings.load(path)

    def test_problems(self):
        v = settings.assign(settings.defaults(), ["crash_watch.enabled=on", "bridge=on", "papyrus_logging=off"])
        p = settings.problems(v)
        self.assertEqual(len(p), 5, p)         # folder, procdump, logging off, bridge needs logging on, my_games
        for pairs, ok in ((["papyrus_logging=off"], False),            # an active bridge would go blind
                          (["papyrus_logging=off", "bridge=off"], True),
                          (["bridge=on"], False),                        # the INI may hold logging off today
                          (["bridge=on", "papyrus_logging=on"], True),
                          (["bridge=off"], True)):
            v = settings.assign(settings.defaults(), pairs + ["my_games=x"])
            with self.subTest(pairs=pairs):
                self.assertEqual(settings.problems(v) == [], ok, settings.problems(v))

    def test_procdump_argv(self):
        v = self.values()
        self.assertEqual(crashwatch.procdump_argv(v, 42),
                         [self.procdump, "-accepteula", "-mm", "-e", "1", "-f", "80000003", "-t", "-n", "2", "42",
                          self.dumps])
        v = self.values(crash_watch__dump_on_exit=False)
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

    def test_watch_attaches_to_a_game_it_did_not_start(self):
        sys_ = FakeSystem([(31, 0, 400, 0xC0000409)])
        sys_.started_at = sys_.t                                    # the test runner launched it
        r = crashwatch.watch(self.values(), system=sys_, say=self.said.append)
        self.assertEqual(sys_.calls, [])                            # started nothing, changed nothing
        self.assertEqual(sys_.ran, [])
        self.assertEqual((r[0]["pid"], r[0]["armed"]), (31, True))
        self.assertIn("-t", sys_.spawned[0])                        # a dump at every exit, as the settings say
        log = self.log()
        self.assertIn("watch: waiting for the next Starfield.exe", log)
        self.assertIn("ended: process 31, 0xC0000409", log)

    def test_watch_repeat_follows_each_game_of_a_queue(self):
        sys_ = FakeSystem([(10, 0, 100, 0), (11, 130, 132, 0), (20, 150, 300, 0xC0000005)])
        sys_.started_at = sys_.t
        r = crashwatch.watch(self.values(crash_watch__dump_on_exit=False), system=sys_, say=self.said.append,
                             repeat=True, start_timeout_s=60)
        self.assertEqual([x.get("pid") for x in r], [10, 20, None])  # the last search found no next game
        self.assertEqual(r[1]["early"], [11])                       # a short-lived launcher process is skipped
        self.assertEqual([a[-2] for a in sys_.spawned], ["10", "20"])
        self.assertNotIn("-t", sys_.spawned[0])
        self.assertIn("ended: process 20, 0xC0000005", self.log())

    def test_watch_repeat_stops_when_dumps_fill_the_drive(self):
        sys_ = FakeSystem([(10, 0, 100, 0), (20, 150, 300, 0)], free=[100.0, 4.0])
        sys_.started_at = sys_.t
        r = crashwatch.watch(self.values(), system=sys_, say=self.said.append, repeat=True, start_timeout_s=60)
        self.assertEqual([x.get("pid") for x in r], [10, None])
        self.assertIn("not watching the next game", r[1]["stopped"])
        self.assertEqual(len(sys_.spawned), 1)
        self.assertIn("watch stopped", self.log())

    def test_watch_exit_code_says_whether_every_game_was_armed(self):
        spec = importlib.util.spec_from_file_location("launcher_cli2", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        a = type("A", (), {"settings": os.path.join(self.dir, "none.json"), "pid": None, "repeat": True,
                           "timeout": 60.0, "dry_run": False})()
        for results, code in (([{"started": True, "armed": True}, {"started": False}], 0),
                              ([{"started": True, "armed": False}, {"started": False}], 1),
                              ([{"started": True, "armed": True}, {"started": False, "stopped": "disk"}], 1),
                              ([{"started": False}], 1)):
            real = cli.crashwatch.watch
            cli.crashwatch.watch = lambda *x, **k: results
            try:
                self.assertEqual(cli.cmd_watch(a), code, results)
            finally:
                cli.crashwatch.watch = real

    def test_watch_pid_and_refusals(self):
        sys_ = FakeSystem([(10, 0, 100, 0), (12, 0, 200, 0)])
        sys_.started_at = sys_.t
        r = crashwatch.watch(self.values(), system=sys_, say=self.said.append, pid=12)
        self.assertEqual(r[0]["pid"], 12)
        with self.assertRaises(ValueError) as e:
            crashwatch.watch(self.values(crash_watch__enabled=False), system=FakeSystem([]), say=self.said.append)
        self.assertIn("crash watcher is off", str(e.exception))
        with self.assertRaises(ValueError):
            crashwatch.watch(self.values(), system=FakeSystem([], free=3.0), say=self.said.append)
        r = crashwatch.watch(self.values(), system=FakeSystem([]), say=self.said.append, dry_run=True)
        self.assertIn("a dump on every exit", r[0]["plan"][1])

    def test_procdump_output_is_folded_into_the_log_decoded(self):
        os.makedirs(self.dumps, exist_ok=True)
        out, log = os.path.join(self.dumps, "procdump_7.out"), os.path.join(self.dumps, "crashwatch.log")
        with open(out, "wb") as f:
            f.write("\ufeffProcDump v11.0 - Sysinternals process dump utility\r\n\r\nDump 1 initiated\r\n"
                    .encode("utf-16-le"))
        crashwatch.fold_output(out, log)
        text = self.log()
        self.assertIn("  procdump: ProcDump v11.0 - Sysinternals process dump utility\n", text)
        self.assertIn("  procdump: Dump 1 initiated\n", text)
        self.assertNotIn("\x00", text)
        self.assertFalse(os.path.exists(out))
        with open(out, "wb") as f:                                # the PC's mix: an 8-bit banner, then UTF-16LE
            f.write(b"\r\nProcDump v11.0 - Sysinternals process dump utility\r\nCopyright (C) 2009-2022\r\n"
                    + "[20:55:49]The process has exited.\r\n[20:55:49]Dump count not reached.\r\n".encode("utf-16-le"))
        crashwatch.fold_output(out, log)
        text = self.log()
        self.assertIn("  procdump: Copyright (C) 2009-2022\n", text)
        self.assertIn("  procdump: [20:55:49]Dump count not reached.\n", text)
        with open(out, "wb") as f:
            f.write(b"odd\n" + "Exception: 406D1388\n".encode("utf-16-le"))   # UTF-16 at an odd offset
        crashwatch.fold_output(out, log)
        self.assertIn("  procdump: Exception: 406D1388\n", self.log())
        with open(out, "wb") as f:
            f.write(b"plain line\n")
        crashwatch.fold_output(out, log)
        self.assertIn("  procdump: plain line", self.log())
        crashwatch.fold_output(out, log)                          # no file: nothing happens

    def test_an_earlier_games_dump_is_never_listed(self):
        os.makedirs(self.dumps, exist_ok=True)
        old = os.path.join(self.dumps, "Starfield.exe_261021_202458.dmp")
        with open(old, "wb") as f:
            f.write(b"MDMP")
        os.utime(old, (5000.0, 5000.0))                          # a file time later than this game's start
        sys_ = FakeSystem([(33840, 0, 722, 0)])
        sys_.started_at = sys_.t
        r = crashwatch.watch(self.values(), system=sys_, say=self.said.append)
        self.assertEqual(r[0]["dumps"], [])
        self.assertIn("dumps: none", self.log())
        sys_ = FakeSystem([(33841, 0, 300, 0xC0000005)])
        sys_.started_at = sys_.t
        sys_.dump_name = "Starfield.exe_261021_210000.dmp"
        r = crashwatch.watch(self.values(), system=sys_, say=self.said.append)
        self.assertEqual(r[0]["dumps"], ["Starfield.exe_261021_210000.dmp"])

    def test_full_dumps_need_room_for_every_dump(self):
        self.assertEqual(crashwatch.needed_free_gb(self.values()), 25.0)
        self.assertEqual(crashwatch.needed_free_gb(self.values(crash_watch__dump="full")), 40.0)       # -n 2
        self.assertEqual(crashwatch.needed_free_gb(self.values(crash_watch__dump="full",
                                                               crash_watch__dump_on_exit=False)), 25.0)
        with self.assertRaises(ValueError) as e:
            self.play(self.values(crash_watch__dump="full"), FakeSystem([(5, 0, 100, 0)], free=30.0))
        self.assertIn("room for 2 full dumps", str(e.exception))
        with self.assertRaises(ValueError):
            crashwatch.watch(self.values(crash_watch__dump="full"), system=FakeSystem([], free=30.0),
                             say=self.said.append)

    def test_decoder_keeps_characters_outside_latin1(self):
        data = b"ProcDump v11.0\r\n" + "Dump folder: D:\\\u30c0\u30f3\u30d7\\\r\n".encode("utf-16-le")
        self.assertEqual(crashwatch.decode_mixed(data), "ProcDump v11.0\r\nDump folder: D:\\\u30c0\u30f3\u30d7\\\r\n")
        self.assertEqual(crashwatch.decode_mixed(b"just text\n"), "just text\n")

    def test_a_dump_procdump_did_not_finish_is_not_reported_usable(self):
        sys_ = FakeSystem([(40, 0, 300, 0xC0000005)])
        sys_.started_at = sys_.t
        sys_.dump_name = "Starfield.exe_261022_010000.dmp"
        r = crashwatch.watch(self.values(), system=sys_, say=self.said.append)
        self.assertNotIn("dumps_unconfirmed", r[0])                 # "Dump 1 complete" was reported
        sys_ = FakeSystem([(41, 0, 300, 0xC0000005)])
        sys_.started_at = sys_.t
        sys_.dump_name, sys_.dump_completes = "Starfield.exe_261022_020000.dmp", False
        r = crashwatch.watch(self.values(), system=sys_, say=self.said.append)
        self.assertTrue(r[0]["dumps_unconfirmed"])
        self.assertIn("did not report every dump complete", self.log())
        self.assertTrue(any("NOT confirmed complete" in x for x in self.said))
        self.assertFalse(crashwatch.dumps_confirmed("", ["a.dmp"]))
        self.assertTrue(crashwatch.dumps_confirmed("Dump 1 complete: 1 MB\nDump 2 complete: 1 MB", ["a.dmp", "b.dmp"]))

    def test_watch_counts_seconds_from_when_the_game_appeared(self):
        sys_ = FakeSystem([(31, 300, 900, 0)])
        sys_.started_at = sys_.t                                  # the watch begins 300 s before the game shows up
        r = crashwatch.watch(self.values(), system=sys_, say=self.said.append)
        self.assertEqual(r[0]["seconds"], 600)
        self.assertIn("after 600 s up", self.log())

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

    def test_a_new_dump_folder_is_made_before_the_game_starts(self):
        new = os.path.join(self.dir, "new", "dumps")
        r = self.play(self.values(crash_watch__folder=new), FakeSystem([(5, 0, 100, 0)]))
        self.assertTrue(r["armed"])
        self.assertTrue(os.path.isfile(os.path.join(new, "crashwatch.log")))
        blocked = os.path.join(self.dir, "a_file")
        open(blocked, "w").close()
        sys_ = FakeSystem([(5, 0, 100, 0)])
        with self.assertRaises(ValueError) as e:
            self.play(self.values(crash_watch__folder=os.path.join(blocked, "dumps")), sys_)
        self.assertIn("cannot write", str(e.exception))
        self.assertEqual(sys_.calls, [])                           # refused before the game starts

    def test_procdump_that_does_not_attach_is_not_called_armed(self):
        sys_ = FakeSystem([(5, 0, 300, 0xC0000005)])
        sys_.procdump_quits = -2
        r = self.play(self.values(), sys_)
        self.assertFalse(r["armed"])
        self.assertEqual(r["exit"], "0xC0000005 ACCESS_VIOLATION")      # the exit code is still logged
        self.assertIn("NOT armed on process 5: ProcDump exited at once (code -2)", self.log())
        self.assertNotIn("armed: process", self.log())
        sys_ = FakeSystem([(5, 0, 300, 0)])
        sys_.spawn_error = PermissionError(13, "Access is denied")
        r = self.play(self.values(), sys_)
        self.assertFalse(r["armed"])
        self.assertIn("ProcDump did not start (Access is denied)", self.log())
        self.assertIn("ended: process 5", self.log())

    def test_without_a_handle_the_process_is_followed_by_its_id(self):
        sys_ = FakeSystem([(5, 0, 700, 0)])
        sys_.refuse_handle = True
        r = self.play(self.values(), sys_)
        self.assertEqual(r["exit"], "unknown (no handle on the game)")
        self.assertGreaterEqual(r["seconds"], 700)             # not reported ended while it still ran
        self.assertTrue(any("following it by process id" in s for s in self.said))

    def test_a_failed_ini_write_leaves_the_live_ini_whole(self):
        mg = os.path.join(self.dir, "mgx")
        os.makedirs(mg)
        ini = os.path.join(mg, "StarfieldCustom.ini")
        with open(ini, "w", encoding="utf-8") as f:
            f.write("[Display]\nbFull Screen=1\n")
        v = self.values(bridge="off", papyrus_logging="on", my_games=mg)
        from unittest import mock
        with mock.patch.object(crashwatch.os, "replace", side_effect=OSError(28, "No space left on device")):
            with self.assertRaises(ValueError):
                crashwatch.apply_papyrus(v, self.said.append)
        with open(ini, encoding="utf-8") as f:
            self.assertEqual(f.read(), "[Display]\nbFull Screen=1\n")
        self.assertEqual(sorted(n for n in os.listdir(mg) if not n.startswith("StarfieldCustom.ini.bak-")),
                         ["StarfieldCustom.ini"])                 # no temporary file left behind

    def test_logging_goes_on_before_the_bridge_comes_back(self):
        mg = os.path.join(self.dir, "mg")
        os.makedirs(os.path.join(mg, "StarfieldCustom.ini"))      # a folder where the INI should be: the write fails
        sys_ = FakeSystem([(5, 0, 100, 0)])
        sys_.toggle_status = {"off": ["FO4SFBridge.esm"], "owned": ["FO4SFBridge.esm"]}
        with self.assertRaises(ValueError):
            self.play(self.values(bridge="on", papyrus_logging="on", my_games=mg), sys_)
        self.assertEqual((sys_.ran, sys_.calls), ([], []))       # the bridge stayed held, nothing started

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
        self.assertIn("a dump on every exit", r["plan"][-1])
        r = self.play(self.values(crash_watch__dump_on_exit=False), FakeSystem([(5, 0, 100, 0)]), dry_run=True)
        self.assertIn("log only", r["plan"][-1])
        self.assertEqual((sys_.calls, sys_.ran, sys_.spawned), ([], [], []))

    def test_bridge_setting_goes_through_plugin_toggle(self):
        sys_ = FakeSystem([(5, 0, 100, 0)])
        sys_.toggle_status = {"off": [], "owned": ["FO4SFBridge.esm"]}
        self.play(self.values(bridge="off"), sys_)
        self.assertEqual(sys_.ran[1][:3], ["off", "--plugins", "FO4SFBridge.esm"])
        sys_ = FakeSystem([(5, 0, 100, 0)])
        sys_.toggle_status = {"off": ["FO4SFBridge.esm"], "owned": ["FO4SFBridge.esm"]}
        self.play(self.values(bridge="off"), sys_)
        self.assertEqual(sys_.ran[1][:3], ["off", "--plugins", "FO4SFBridge.esm"])   # held: off again, the game
        #                                                          may have ticked it since
        sys_ = FakeSystem([(5, 0, 100, 0)])
        sys_.toggle_status = {"off": ["FO4SFBridge.esm"], "owned": ["FO4SFBridge.esm"]}
        mg = os.path.join(self.dir, "mg")
        os.makedirs(mg)
        self.play(self.values(bridge="on", papyrus_logging="on", my_games=mg), sys_)
        self.assertEqual(sys_.ran[1][:3], ["on", "--plugins", "FO4SFBridge.esm"])
        sys_ = FakeSystem([(5, 0, 100, 0)])                       # not held, and active: nothing to do
        sys_.toggle_status = {"off": [], "owned": ["FO4SFBridge.esm"]}
        self.play(self.values(bridge="on", papyrus_logging="on", my_games=mg), sys_)
        self.assertEqual(len(sys_.ran), 1)
        for active in (set(), None):                               # not held but unticked, or no Plugins.txt
            sys_ = FakeSystem([(5, 0, 100, 0)])
            sys_.toggle_status = {"off": [], "owned": ["FO4SFBridge.esm"]}
            sys_.active = active
            with self.assertRaises(ValueError):
                self.play(self.values(bridge="on", papyrus_logging="on", my_games=mg), sys_)
            self.assertEqual(sys_.calls, [])
        sys_ = FakeSystem([(5, 0, 100, 0)])                       # released but left unticked: refused
        sys_.toggle_status = {"off": ["FO4SFBridge.esm"], "owned": ["FO4SFBridge.esm"]}
        sys_.toggle_out = "back on: none; released, left unticked (cannot load): FO4SFBridge.esm: file missing"
        with self.assertRaises(ValueError) as e:
            self.play(self.values(bridge="on", papyrus_logging="on", my_games=mg), sys_)
        self.assertIn("did not come back on", str(e.exception))
        self.assertEqual(sys_.calls, [])
        self.assertFalse(crashwatch.bridge_came_back("back on: FO4SFBridgeX.esm"))
        self.assertTrue(crashwatch.bridge_came_back("back on: A.esm, fo4sfbridge.esm; still held off: B.esm"))
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
        self.play(self.values(papyrus_logging="off", bridge="off", my_games=mg), FakeSystem([(5, 0, 100, 0)]))
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
        self.assertEqual(cli.main(["watch", "--settings", path, "--repeat", "--dry-run"]), 0)


if __name__ == "__main__":
    unittest.main()
