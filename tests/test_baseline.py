"""scripts/game/baseline.py, the vanilla baseline: prepare turns off every plugin the game does not ship and keeps
every other byte of Plugins.txt, refuses when the load set would not be vanilla or an earlier baseline may be open (the
open-baseline note finds one anywhere, and one it names that cannot be read counts), collect joins the logs written
after prepare and before restore, never one that was there at prepare, and never keeps one as the baseline when the
session was not vanilla (its log names ours, a plugin was ticked again, SFSE ran) or the game changed since prepare,
restore puts the bytes back (over the game's own rewrite, never over a ticked plugin unless forced, keeping the file it
writes over, never from a damaged record, and a restore that stopped before its record is finished by the next, also
after the game rewrote Plugins.txt), compare groups a run's log against the baseline's and never writes its report over
the baseline's files or into the game's folders; prepare, collect and restore run one at a time. A made-up game folder,
My Games folder, LOCALAPPDATA and runner state folder, and a clock that moves 10 s at every read (prepare and restore
never share a time, as they can on a coarse clock)."""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
sys.path.insert(0, os.path.join(ROOT, "src"))
import baseline as bl  # noqa: E402
from fo4sf.planet import esm  # noqa: E402

PAPYRUS_ON = "[Papyrus]\nbEnableLogging=1\nbEnableTrace=1\nbLoadDebugInformation=1\n"
ORIGINAL = (b"\xef\xbb\xbf# This file is used by Starfield to keep track of your downloaded content.\r\n"
            b"*FO4Port.esm\r\n*FO4SFNewGame.esm\r\nInactive.esm\r\n*SFBGS003.esm\r\n")
PREPARED = (b"\xef\xbb\xbf# This file is used by Starfield to keep track of your downloaded content.\r\n"
            b"FO4Port.esm\r\nFO4SFNewGame.esm\r\nInactive.esm\r\n*SFBGS003.esm\r\n")
BASE_LOG = ("[05:20:01] Papyrus log opened (PC-64)\n"
            "[05:20:02] error: Cannot call Disable() on a None object, aborting function call\n"
            "stack:\n\t[Q (00012345)].QScript.Shutdown() - \"QScript.psc\" Line 51\n")
RUN_LOG = BASE_LOG + ("[05:30:04] error: Cannot call SetValue() on a None object, aborting function call\n"
                      "stack:\n\t[FO4SFNewGameQuest (0A000800)].FO4SF_NewGameScript.OnStageSet() - "
                      "\"FO4SF_NewGameScript.psc\" Line 30\n")
SECOND_LOG = ("[06:00:01] Papyrus log opened (PC-64)\n"
              "[06:00:05] warning: Property Q on script QScript attached to Q (00012345) cannot be bound\n")


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(data, bytes) else "w", **({} if isinstance(data, bytes) else {"encoding": "utf-8"})) as f:
        f.write(data)
    return path


def plugin(path, masters=("Starfield.esm",), records=()):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    w = esm.PluginWriter(list(masters))
    for sig, fid in records:
        w.add(esm.Record(sig, fid, [(b"EDID", esm.zbytes("X"))]))
    w.write(path)


def read(path):
    with open(path, "rb") as f:
        return f.read()


def plugins_txt_denied():
    """os.replace onto Plugins.txt fails as it does on Windows for a read-only file; every other rename works."""
    real = os.replace

    def replace(src, dst):
        if os.path.basename(dst) == "Plugins.txt":
            raise PermissionError("Access is denied")
        return real(src, dst)

    return mock.patch.object(os, "replace", replace)


class BaselineTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = self.d = tmp.name
        self.game = os.path.join(d, "game")
        data = self.data = os.path.join(self.game, "Data")
        plugin(os.path.join(data, "Starfield.esm"), masters=())
        plugin(os.path.join(data, "SFBGS003.esm"), records=[(b"QUST", 0x00003448)])   # the game's own: fine
        plugin(os.path.join(data, "FO4Port.esm"))
        plugin(os.path.join(data, "FO4SFNewGame.esm"), records=[(b"GLOB", 0x000A7D31)])
        write(os.path.join(self.game, "Starfield.exe"), b"MZ")
        self.mg = os.path.join(d, "mg")
        write(os.path.join(self.mg, "StarfieldCustom.ini"), PAPYRUS_ON)
        self.pt = write(os.path.join(d, "local", "Starfield", "Plugins.txt"), ORIGINAL)
        self.out = os.path.join(d, "baseline_1")
        self.note = os.path.join(d, "state", bl.OPEN_NOTE)
        env = {"LOCALAPPDATA": os.path.join(d, "local"), "FO4_AI_TEAM_STATE": os.path.join(d, "state")}
        clock = self.clock = [time.time()]

        def tick():
            clock[0] += 10
            return clock[0]

        for patch in (mock.patch.dict(os.environ, env), mock.patch.object(bl, "game_running", return_value=False),
                      mock.patch.object(bl, "time", SimpleNamespace(time=tick)),
                      mock.patch.object(bl, "LOCK_WAIT_S", 0.05)):
            patch.start()
            self.addCleanup(patch.stop)

    def run_bl(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = bl.main(list(argv))
        return code, buf.getvalue()

    def prepare(self, out=None, *more):
        return self.run_bl("prepare", "--starfield", self.game, "--my-games", self.mg, "--out", out or self.out, *more)

    def record(self):
        with open(os.path.join(self.out, bl.RECORD), encoding="utf-8") as f:
            return json.load(f)

    def log(self, text, age, name="Papyrus.0.log"):
        """A log in My Games, last written age seconds after prepare."""
        p = write(os.path.join(self.mg, "Logs", "Script", name), text)
        t = self.record()["prepared_epoch"] + age
        os.utime(p, (t, t))
        return p

    def between(self, path):
        """Marks a file as written after prepare and before restore."""
        rec = self.record()
        t = (rec["prepared_epoch"] + rec["restored_epoch"]) / 2
        os.utime(path, (t, t))

    def test_untick_keeps_every_other_byte(self):
        self.assertEqual(bl.untick(ORIGINAL), (PREPARED, ["FO4Port.esm", "FO4SFNewGame.esm"]))
        self.assertEqual(bl.untick(b"  *Mod.esp\n*notes.txt\n*BlueprintShips-Starfield.esm"),
                         (b"  Mod.esp\n*notes.txt\n*BlueprintShips-Starfield.esm", ["Mod.esp"]))
        with self.assertRaisesRegex(SystemExit, "not UTF-8"):
            bl.untick(b"*\xff.esm\n")
        self.assertEqual(bl.untick(b"**Mod.esm\r\n"), (b"Mod.esm\r\n", ["Mod.esm"]))   # every star, not the first
        with self.assertRaisesRegex(SystemExit, "Mod.esm cannot be unticked"):
            bl.untick(b"* *Mod.esm\n")                                    # it would still read as active

    def test_check_writes_nothing(self):
        code, out = self.run_bl("check", "--starfield", self.game, "--my-games", self.mg)
        self.assertEqual(code, 0, out)
        self.assertIn("prepare would turn off: FO4Port.esm, FO4SFNewGame.esm", out)
        self.assertIn("PASS    start: overrides of Starfield's start are the pinned ones: none", out)   # [] pinned
        self.assertIn("check: prepare would go ahead", out)
        self.assertEqual(read(self.pt), ORIGINAL)
        self.assertFalse(os.path.exists(self.out) or os.path.exists(self.note))

    def test_prepare_records_then_turns_off(self):
        code, out = self.prepare()
        self.assertEqual(code, 0, out)
        self.assertEqual(read(self.pt), PREPARED)
        rec = self.record()
        self.assertEqual(rec["turned_off"], ["FO4Port.esm", "FO4SFNewGame.esm"])
        self.assertEqual(sorted(rec["builtins"]), ["SFBGS003.esm", "Starfield.esm"])
        self.assertEqual(len(rec["builtins"]["Starfield.esm"]["sha256"]), 64)
        self.assertEqual(rec["starfield_exe"]["size"], 2)
        self.assertEqual((rec["log"], rec["restored_at"], rec["my_games"]), (None, None, [self.mg]))
        self.assertIn("turned off: FO4Port.esm, FO4SFNewGame.esm", out)
        self.assertEqual(bl.read_json(self.note)["out"], self.out)        # the open baseline, wherever it is
        with self.assertRaisesRegex(SystemExit, "never restored.*run restore --out"):
            self.prepare()                                             # the record holds the only original
        self.run_bl("restore", "--out", self.out)
        self.assertFalse(os.path.exists(self.note))
        with self.assertRaisesRegex(SystemExit, "already holds a baseline"):
            self.prepare()

    def test_prepare_refuses_and_changes_nothing(self):
        cases = [
            ("running", lambda: mock.patch.object(bl, "game_running", return_value=True), "Starfield is running"),
            ("started meanwhile", lambda: mock.patch.object(bl, "game_running", side_effect=[False, True]),
             "started while prepare read the game folder"),             # the hashing takes a while
            ("started last", lambda: mock.patch.object(bl, "game_running",   # after the record and its note
                                                       side_effect=lambda: os.path.exists(self.note)),
             "started while prepare ran, so nothing changed and the record is removed"),
            ("logging", lambda: mock.patch.object(bl.preflight, "papyrus_logging_on", return_value=False),
             "would write no log"),
        ]
        for what, patch, why in cases:
            with self.subTest(what), patch(), self.assertRaisesRegex(SystemExit, why):
                self.prepare()
        write(os.path.join(self.mg, "Starfield.ccc"), "FO4Port.esm\n")           # it would load anyway
        with self.assertRaisesRegex(SystemExit, "FAIL    loaders: .*lists FO4Port.esm"):
            self.prepare()
        os.remove(os.path.join(self.mg, "Starfield.ccc"))
        write(os.path.join(self.mg, "StarfieldCustom.ini"), PAPYRUS_ON + "[General]\nsTestFile1=FO4Port.esm\n")
        code, out = self.run_bl("check", "--starfield", self.game, "--my-games", self.mg)
        self.assertEqual(code, 1)
        self.assertIn("refused: FAIL    loaders: sTestFile1=FO4Port.esm", out)
        with self.assertRaisesRegex(SystemExit, "FAIL    loaders: sTestFile1=FO4Port.esm"):
            self.prepare()
        write(os.path.join(self.mg, "StarfieldCustom.ini"), PAPYRUS_ON)
        with self.assertRaisesRegex(SystemExit, "no Data folder"):
            self.run_bl("prepare", "--starfield", self.d, "--my-games", self.mg, "--out", self.out)
        for inside, why in ((os.path.join(self.mg, "Logs", "Script"), f"is in a My Games folder, {self.mg}"),
                            (os.path.join(self.game, "baseline"), f"is in the game folder, {self.game}"),
                            (os.path.join(os.path.dirname(self.pt), "baseline"), "is in Plugins.txt's folder")):
            with self.subTest(inside), self.assertRaisesRegex(SystemExit, re.escape(why)):
                self.prepare(inside)                                    # collect would write over the game's log
            self.assertFalse(os.path.exists(os.path.join(inside, bl.RECORD)))
        self.assertEqual(read(self.pt), ORIGINAL)
        self.assertFalse(os.path.exists(os.path.join(self.out, bl.RECORD)) or os.path.exists(self.note))

    def test_prepare_that_loses_a_race_leaves_no_record(self):
        real = bl.launcher_restore.write_plugins_txt

        def changed_meanwhile(path, b64, sha):
            write(path, ORIGINAL + b"*Late.esm\r\n")
            return real(path, b64, sha)

        with mock.patch.object(bl.launcher_restore, "write_plugins_txt", changed_meanwhile), \
                self.assertRaisesRegex(SystemExit, "changed after prepare read it .*nothing changed and the record is removed"):
            self.prepare()
        self.assertFalse(os.path.exists(os.path.join(self.out, bl.RECORD)) or os.path.exists(self.note))
        self.assertEqual(read(self.pt), ORIGINAL + b"*Late.esm\r\n")

    def test_prepare_collect_and_restore_never_overlap(self):
        inner = []

        def running():                                                  # a second prepare while this one reads
            if not inner:
                try:
                    inner.append(self.prepare(os.path.join(self.d, "baseline_2")))
                except SystemExit as e:
                    inner.append(str(e))
            return False

        with mock.patch.object(bl, "game_running", side_effect=running):
            self.assertEqual(self.prepare()[0], 0)
        self.assertRegex(inner[0], "another baseline.py prepare, collect or restore is running .*nothing changed")
        self.assertEqual(read(self.pt), PREPARED)
        self.assertEqual(self.record()["turned_off"], ["FO4Port.esm", "FO4SFNewGame.esm"])   # the record survives
        self.assertEqual(bl.read_json(self.note)["out"], self.out)       # and so does its note
        self.assertFalse(os.path.exists(os.path.join(self.d, "baseline_2")))
        lock = os.path.join(self.d, "state", bl.LOCK)
        self.assertFalse(os.path.exists(lock))                          # let go when the command ends
        with bl.filelock.locked(lock):                                  # another command holds it
            for cmd in ("collect", "restore"):
                with self.subTest(cmd), self.assertRaisesRegex(SystemExit, f"{cmd}: another baseline.py prepare.* "
                                                                           f"held by another process for"):
                    self.run_bl(cmd, "--out", self.out)                 # the lock's own reason
            self.assertIn("as prepared", self.run_bl("status", "--out", self.out)[1])   # reading takes no lock
        self.assertEqual(read(self.pt), PREPARED)
        write(lock, b"1 0\n")                                           # left by a command that stopped
        old = time.time() - bl.LOCK_STALE_S - 60
        os.utime(lock, (old, old))
        self.assertEqual(self.run_bl("restore", "--out", self.out)[0], 0)
        self.assertEqual(read(self.pt), ORIGINAL)

    def test_a_log_from_while_prepare_hashed_is_not_the_baselines(self):
        start = self.clock[0]                                           # prepare reads the clock, hashes, reads again
        p = write(os.path.join(self.mg, "Logs", "Script", "Papyrus.0.log"), RUN_LOG)
        os.utime(p, (start + 15, start + 15))                           # a session that ended while it hashed
        self.prepare()
        with self.assertRaisesRegex(SystemExit, "last written before prepare"):
            self.run_bl("collect", "--out", self.out)

    def test_a_baseline_next_to_the_new_one_is_found_without_the_note(self):
        self.prepare()                                                  # never restored
        write(self.pt, PREPARED.replace(b"\r\nFO4Port.esm", b"\r\n*FO4Port.esm"))   # ours ticked again
        later = os.path.join(self.d, "baseline_2")                      # next to baseline_1
        with mock.patch.dict(os.environ, {"FO4_AI_TEAM_STATE": os.path.join(self.d, "state2")}), \
                self.assertRaisesRegex(SystemExit, "baseline_1 holds a baseline of this Plugins.txt that was never "
                                                   "restored"):
            self.prepare(later)                                         # the note lost
        self.assertFalse(os.path.exists(later))

    def test_an_unrestored_baseline_is_never_taken_for_the_original(self):
        self.prepare()                                                  # the session ended before restore
        later = os.path.join(self.d, "baseline_2")
        with self.assertRaisesRegex(SystemExit, "baseline_1 holds a baseline of this Plugins.txt that was never restored"):
            self.prepare(later)
        code, out = self.run_bl("check", "--starfield", self.game, "--my-games", self.mg)
        self.assertEqual(code, 1)
        self.assertIn(f"{self.out} holds a baseline of this Plugins.txt that was never restored", out)
        self.assertIn("FO4Port.esm, FO4SFNewGame.esm are off in Plugins.txt already", out)
        elsewhere = os.path.join(self.d, "other", "baseline_3")         # no folder next to baseline_1
        write(self.pt, PREPARED + b"*SomeMod.esp\r\n")                  # a mod ticked again: something to turn off
        with self.assertRaisesRegex(SystemExit, "baseline_1 holds a baseline of this Plugins.txt that was never restored"):
            self.prepare(elsewhere)                                     # the note names it
        self.assertFalse(os.path.exists(later) or os.path.exists(elsewhere))
        self.assertEqual(read(self.pt), PREPARED + b"*SomeMod.esp\r\n")
        write(self.pt, PREPARED)
        with mock.patch.dict(os.environ, {"FO4_AI_TEAM_STATE": os.path.join(self.d, "state2")}):   # the note lost
            with self.assertRaisesRegex(SystemExit, "--allow-off if no baseline turned them off"):
                self.prepare(elsewhere)
            write(self.pt, PREPARED + b"*SomeMod.esp\r\n")              # another mod on, ours still off
            with self.assertRaisesRegex(SystemExit, "none of ours is on, and FO4Port.esm, FO4SFNewGame.esm are off"):
                self.prepare(elsewhere)
            self.assertEqual(read(self.pt), PREPARED + b"*SomeMod.esp\r\n")
            write(self.pt, PREPARED)
            code, out = self.prepare(elsewhere, "--allow-off")
        self.assertEqual(code, 0, out)                                   # off anyway: nothing to turn off
        self.assertIsNone(bl.load_record(elsewhere)["prepared_sha256"])

    def test_the_open_note_follows_the_baseline(self):
        write(self.pt, b"*SFBGS003.esm\n")
        self.prepare()                                                  # nothing turned off: nothing open
        self.assertFalse(os.path.exists(self.note))
        write(self.pt, ORIGINAL)
        gone = os.path.join(self.d, "gone")
        write(self.note, json.dumps({"schema": 1, "out": gone, "plugins_txt": self.pt}))
        later = os.path.join(self.d, "other", "baseline_2")
        with self.assertRaisesRegex(SystemExit, "names .*gone, whose record cannot be read"):
            self.prepare(later)                                         # on a drive not there? it may be open
        self.assertFalse(os.path.exists(later))
        self.assertEqual(bl.read_json(self.note)["out"], gone)          # the only pointer to it is kept
        os.makedirs(gone)                                               # there, and it holds no baseline: stale
        code, out = self.prepare(later)
        self.assertEqual(code, 0, out)
        self.assertEqual(bl.read_json(self.note)["out"], later)
        self.run_bl("restore", "--out", later)
        self.assertFalse(os.path.exists(self.note))
        os.remove(os.path.join(self.out, bl.RECORD))
        os.makedirs(self.note)                                          # a note that cannot be read: a folder there
        with self.assertRaisesRegex(SystemExit, "open-baseline note .* cannot be read, so a baseline may be open"):
            self.prepare()
        os.rmdir(self.note)
        real = bl.write_json

        def note_fails(path, value):                                    # the note cannot be written (a full disk)
            if path == bl.open_note_path():
                raise OSError(28, "No space left on device", path)
            return real(path, value)

        with mock.patch.object(bl, "write_json", note_fails), \
                self.assertRaisesRegex(SystemExit, "open-baseline note .* could not be written"):
            self.prepare()
        self.assertFalse(os.path.exists(os.path.join(self.out, bl.RECORD)))
        self.assertEqual(read(self.pt), ORIGINAL)
        blocked = write(os.path.join(self.d, "blocked"), b"a file, not a folder")   # no state folder, so no lock
        with mock.patch.dict(os.environ, {"FO4_AI_TEAM_STATE": os.path.join(blocked, "state")}), \
                self.assertRaisesRegex(SystemExit, "the baseline lock .* could not be made .*nothing changed"):
            self.prepare()
        self.assertFalse(os.path.exists(os.path.join(self.out, bl.RECORD)))
        self.assertEqual(read(self.pt), ORIGINAL)

    def test_prepare_that_cannot_write_leaves_no_record(self):
        with plugins_txt_denied(), \
                self.assertRaisesRegex(SystemExit, "could not be written .*Access is denied.*read-only"):
            self.prepare()
        self.assertFalse(os.path.exists(os.path.join(self.out, bl.RECORD)) or os.path.exists(self.note))
        self.assertEqual(read(self.pt), ORIGINAL)
        self.assertEqual(os.listdir(os.path.dirname(self.pt)), ["Plugins.txt"])   # no temp file left
        with mock.patch.object(bl.os, "access", return_value=False), \
                self.assertRaisesRegex(SystemExit, "Plugins.txt is read-only"):
            self.prepare()                                              # seen before anything is written
        self.assertEqual(self.prepare()[0], 0)

    def test_prepare_refuses_a_linked_plugins_txt(self):
        real = write(os.path.join(self.d, "elsewhere", "Plugins.txt"), ORIGINAL)
        os.remove(self.pt)
        try:
            os.symlink(real, self.pt)
        except (OSError, NotImplementedError) as e:
            self.skipTest(f"no file links here: {e}")
        with self.assertRaisesRegex(SystemExit, "is a link: prepare would put a plain file in its place"):
            self.prepare()
        self.assertTrue(os.path.islink(self.pt))
        self.assertEqual(read(real), ORIGINAL)

    def test_my_games_is_recorded_absolute(self):
        cwd = os.getcwd()
        os.chdir(self.d)
        try:
            self.run_bl("prepare", "--starfield", "game", "--my-games", "mg", "--out", "baseline_1")
        finally:
            os.chdir(cwd)
        rec = self.record()
        self.assertEqual((rec["my_games"], rec["starfield"]), ([self.mg], self.game))

    def test_collect_takes_only_a_log_written_after_prepare(self):
        self.prepare()
        with self.assertRaisesRegex(SystemExit, "no Papyrus.0.log"):
            self.run_bl("collect", "--out", self.out)
        self.log(BASE_LOG, -60)
        with self.assertRaisesRegex(SystemExit, "last written before prepare"):
            self.run_bl("collect", "--out", self.out)
        p = self.log(BASE_LOG, 60)
        with mock.patch.object(bl, "game_running", return_value=True), self.assertRaisesRegex(SystemExit, "quit"):
            self.run_bl("collect", "--out", self.out)                  # the log is complete only after the quit
        code, out = self.run_bl("collect", "--out", self.out)
        self.assertEqual(code, 0, out)
        self.assertIn("1 errors, 0 warnings, 1 notes", out)
        rec = self.record()
        self.assertEqual((rec["log"]["file"], rec["log"]["ours"], rec["log"]["counts"]["error"]), ("Papyrus.0.log", [], 1))
        self.assertEqual([s["path"] for s in rec["log"]["sources"]], [p])
        self.assertEqual(read(os.path.join(self.out, "Papyrus.0.log")), BASE_LOG.encode("utf-8"))
        self.assertEqual(sorted(os.listdir(self.out)), ["Papyrus.0.log", bl.RECORD])

    def test_collect_joins_every_log_of_the_baseline(self):
        self.prepare()
        self.log(RUN_LOG, -60, "Papyrus.2.log")                          # a session before prepare: not this one
        first = self.log(BASE_LOG.rstrip("\n"), 60, "Papyrus.1.log")    # the 10 minutes; no newline at its end
        second = self.log(b"\xef\xbb\xbf" + SECOND_LOG.encode("utf-8"), 120)   # a start that quit at the menu
        code, out = self.run_bl("collect", "--out", self.out)
        self.assertEqual(code, 0, out)
        self.assertIn("2 sessions wrote a log after prepare; their logs are joined, oldest first", out)
        self.assertIn("1 errors, 1 warnings, 2 notes", out)
        self.assertEqual(read(os.path.join(self.out, "Papyrus.0.log")), (BASE_LOG + SECOND_LOG).encode("utf-8"))
        self.assertEqual([s["path"] for s in self.record()["log"]["sources"]], [first, second])

    def test_collect_takes_one_log_only(self):
        self.prepare()
        self.log(BASE_LOG, 60)
        self.run_bl("collect", "--out", self.out)
        self.run_bl("restore", "--out", self.out)
        self.log(RUN_LOG.replace("FO4SF", "Other"), 7200)               # a later session, nothing of ours named
        with self.assertRaisesRegex(SystemExit, "collected already"):
            self.run_bl("collect", "--out", self.out)
        self.assertEqual(read(os.path.join(self.out, "Papyrus.0.log")), BASE_LOG.encode("utf-8"))
        self.assertEqual(self.record()["log"]["sha256"], bl.files.sha256(os.path.join(self.out, "Papyrus.0.log")))

    def test_collect_refuses_a_log_written_after_restore(self):
        self.prepare()
        self.run_bl("restore", "--out", self.out)
        self.log(BASE_LOG, 7200)                                        # the plugins were back on by then
        with self.assertRaisesRegex(SystemExit, "written after restore"):
            self.run_bl("collect", "--out", self.out)
        self.assertIsNone(self.record()["log"])
        self.between(self.log(BASE_LOG, 0))                             # the baseline session's, collected late
        self.assertEqual(self.run_bl("collect", "--out", self.out)[0], 0)

    def test_a_log_naming_ours_is_no_baseline(self):
        self.prepare()
        self.log(RUN_LOG, 60)                                           # a session that loaded our new game plugin
        code, out = self.run_bl("collect", "--out", self.out)
        self.assertEqual(code, 1)
        self.assertIn("not a vanilla session (the log names ours: FO4SF_NewGameScript, FO4SFNewGameQuest)", out)
        rec = self.record()
        self.assertIsNone(rec["log"])
        self.assertEqual((rec["not_vanilla"]["file"], rec["not_vanilla"]["ours"]),
                         (bl.NOT_VANILLA, ["FO4SF_NewGameScript", "FO4SFNewGameQuest"]))
        self.assertFalse(os.path.exists(os.path.join(self.out, "Papyrus.0.log")))
        self.assertEqual(read(os.path.join(self.out, bl.NOT_VANILLA)), RUN_LOG.encode("utf-8"))
        with self.assertRaisesRegex(SystemExit, "session is no baseline .*names ours"):
            self.run_bl("collect", "--out", self.out)
        run = write(os.path.join(self.d, "run", "Papyrus.0.log"), RUN_LOG)
        with self.assertRaisesRegex(SystemExit, "not vanilla .*names ours.*no baseline"):
            self.run_bl("compare", "--out", self.out, "--run-log", run)
        self.assertIn("not vanilla (the log names ours: FO4SF_NewGameScript, FO4SFNewGameQuest), kept as "
                      "Papyrus.0.log.not-vanilla", self.run_bl("status", "--out", self.out)[1])

    def test_a_session_with_a_plugin_ticked_again_is_no_baseline(self):
        self.prepare()
        ticked = PREPARED + b"*SomeMod.esp\r\n"                          # the Creations menu, a mod manager...
        write(self.pt, ticked)
        self.assertIn("SomeMod.esp ticked again", self.run_bl("status", "--out", self.out)[1])
        self.log(BASE_LOG, 60)                                          # its log names nothing of ours
        code, out = self.run_bl("collect", "--out", self.out)
        self.assertEqual(code, 1, out)
        self.assertIn("not a vanilla session (Plugins.txt had SomeMod.esp ticked again)", out)
        self.assertEqual(self.record()["not_vanilla"]["ticked"], ["SomeMod.esp"])
        run = write(os.path.join(self.d, "run", "Papyrus.0.log"), RUN_LOG)
        with self.assertRaisesRegex(SystemExit, "not vanilla"):
            self.run_bl("compare", "--out", self.out, "--run-log", run)

    def test_a_restore_that_finds_a_plugin_ticked_again_ends_the_baseline(self):
        self.prepare()
        write(self.pt, PREPARED + b"*SomeMod.esp\r\n")
        code, out = self.run_bl("restore", "--out", self.out, "--force")       # restore first, collect after
        self.assertEqual(code, 0, out)
        self.assertIn("SomeMod.esp were ticked in Plugins.txt before restore", out)
        self.assertEqual(self.record()["ticked_at_restore"], ["SomeMod.esp"])
        self.between(self.log(BASE_LOG, 0))
        code, out = self.run_bl("collect", "--out", self.out)
        self.assertEqual(code, 1, out)
        self.assertIn("Plugins.txt had SomeMod.esp ticked again", out)
        self.assertIn("restore found SomeMod.esp ticked", self.run_bl("status", "--out", self.out)[1])

    def test_an_sfse_session_is_no_baseline(self):
        self.prepare()
        self.log(BASE_LOG, 60)
        sfse = write(os.path.join(self.mg, "SFSE", "Logs", "sfse.log"), "SFSE runtime: initialize\n")
        t = self.record()["prepared_epoch"] + 30
        os.utime(sfse, (t, t))
        code, out = self.run_bl("collect", "--out", self.out)
        self.assertEqual(code, 1, out)
        self.assertIn(f"SFSE wrote {sfse} (a start through sfse_loader.exe)", out)
        self.assertEqual(self.record()["not_vanilla"]["sfse"], [sfse])

    def test_an_sfse_log_from_before_prepare_is_not_the_baselines(self):
        old = write(os.path.join(self.mg, "SFSE", "Logs", "FOCCPing.log"), "a modded session, before prepare\n")
        self.prepare()
        t = self.record()["prepared_epoch"] - 60
        os.utime(old, (t, t))
        self.log(BASE_LOG, 60)
        self.assertEqual(self.run_bl("collect", "--out", self.out)[0], 0)

    def test_an_sfse_session_after_restore_is_not_the_baselines(self):
        self.prepare()
        self.run_bl("restore", "--out", self.out)
        self.between(self.log(BASE_LOG, 0))
        sfse = write(os.path.join(self.mg, "SFSE", "Logs", "sfse.log"), "a modded session, after restore\n")
        t = self.record()["restored_epoch"] + 60
        os.utime(sfse, (t, t))
        self.assertEqual(self.run_bl("collect", "--out", self.out)[0], 0)

    def test_an_sfse_session_restore_saw_stays_seen(self):
        self.prepare()
        sfse = write(os.path.join(self.mg, "SFSE", "Logs", "sfse.log"), "SFSE runtime: initialize\n")
        t = self.record()["prepared_epoch"] + 5
        os.utime(sfse, (t, t))                                          # a start through sfse_loader.exe
        code, out = self.run_bl("restore", "--out", self.out)
        self.assertEqual(code, 0, out)
        self.assertIn(f"restore: SFSE wrote {sfse} during the baseline's time", out)
        self.assertEqual(self.record()["sfse_at_restore"], [sfse])
        t = self.record()["restored_epoch"] + 60
        os.utime(sfse, (t, t))                                          # a later SFSE start writes it again
        self.between(self.log(BASE_LOG, 0))
        code, out = self.run_bl("collect", "--out", self.out)
        self.assertEqual(code, 1, out)
        self.assertIn(f"SFSE wrote {sfse} (a start through sfse_loader.exe)", out)
        self.assertIn("restore found SFSE logs of the baseline's time", self.run_bl("status", "--out", self.out)[1])

    def test_a_stopped_restores_sfse_finding_outlives_a_later_sfse_start(self):
        self.prepare()
        self.log(BASE_LOG, 5)
        sfse = write(os.path.join(self.mg, "SFSE", "Logs", "sfse.log"), "SFSE runtime: initialize\n")
        t = self.record()["prepared_epoch"] + 5
        os.utime(sfse, (t, t))                                          # the baseline session started through SFSE
        found = self.stop_restore()
        self.assertEqual(found["sfse"], [sfse])
        t = found["epoch"] + 50
        os.utime(sfse, (t, t))                                          # a later SFSE start wrote it again
        self.assertEqual(self.run_bl("restore", "--out", self.out)[0], 0)
        self.assertEqual(self.record()["sfse_at_restore"], [sfse])      # the rerun's own look no longer finds it
        self.assertEqual(self.run_bl("collect", "--out", self.out)[0], 1)
        self.assertEqual(self.record()["not_vanilla"]["sfse"], [sfse])

    def test_restore_puts_the_bytes_back(self):
        self.prepare()
        code, out = self.run_bl("restore", "--out", self.out)
        self.assertEqual(code, 0, out)
        self.assertEqual(read(self.pt), ORIGINAL)
        self.assertEqual((self.record()["restore"], self.record()["ticked_at_restore"]), ("byte for byte", []))
        self.assertIn("FO4Port.esm, FO4SFNewGame.esm back on", out)
        self.assertNotIn("ticked", out)
        self.assertIn("already restored", self.run_bl("restore", "--out", self.out)[1])
        self.assertEqual(sorted(os.listdir(self.out)), [bl.RECORD])     # nothing kept: it was prepare's own file

    def test_restore_over_the_games_own_rewrite(self):
        self.prepare()
        rewrite = b"*SFBGS003.esm\nFO4Port.esm\nNewMod.esm\n"            # the game's rewrite, or the owner's edit
        write(self.pt, rewrite)
        self.run_bl("restore", "--out", self.out)
        self.assertEqual(read(self.pt), ORIGINAL)
        self.assertEqual(self.record()["restore"],
                         "over the game's own rewrite (it ticked no plugin; kept as Plugins.txt.at-restore)")
        self.assertEqual(read(os.path.join(self.out, bl.KEPT_AT_RESTORE)), rewrite)

    def test_restore_refuses_a_ticked_plugin_unless_forced(self):
        self.prepare()
        ticked = PREPARED.replace(b"\r\nFO4Port.esm", b"\r\n*FO4Port.esm")
        write(self.pt, ticked)
        with self.assertRaisesRegex(SystemExit, "FO4Port.esm were ticked"):
            self.run_bl("restore", "--out", self.out)
        self.assertEqual(read(self.pt), ticked)
        with mock.patch.object(bl, "game_running", return_value=True), self.assertRaisesRegex(SystemExit, "running"):
            self.run_bl("restore", "--out", self.out, "--force")
        code, out = self.run_bl("restore", "--out", self.out, "--force")
        self.assertEqual(read(self.pt), ORIGINAL)
        self.assertEqual(read(os.path.join(self.out, bl.KEPT_AT_RESTORE)), ticked)
        self.assertTrue(self.record()["restore"].startswith("forced over a file with FO4Port.esm ticked"))
        self.assertIn("collect will not take its log as the baseline", out)

    def test_restore_over_a_file_that_is_not_utf8(self):
        self.prepare()
        write(self.pt, b"*SFBGS003.esm\nMod\xe9.esm\n")                 # a name in the Windows code page
        self.run_bl("restore", "--out", self.out)
        self.assertEqual(read(self.pt), ORIGINAL)
        self.assertEqual(self.record()["restore"],
                         "over the game's own rewrite (it ticked no plugin; kept as Plugins.txt.at-restore)")
        os.remove(os.path.join(self.out, bl.RECORD))
        self.prepare()
        write(self.pt, b"*Mod\xe9.esm\n")
        with self.assertRaisesRegex(SystemExit, "Mod�.esm were ticked"):
            self.run_bl("restore", "--out", self.out)
        self.run_bl("restore", "--out", self.out, "--force")            # the documented way out works
        self.assertEqual(read(self.pt), ORIGINAL)
        self.assertEqual(read(os.path.join(self.out, bl.KEPT_AT_RESTORE + ".2")), b"*Mod\xe9.esm\n")
        self.assertEqual(read(os.path.join(self.out, bl.KEPT_AT_RESTORE)), b"*SFBGS003.esm\nMod\xe9.esm\n")   # kept
        self.assertTrue(self.record()["restore"].endswith("(kept as Plugins.txt.at-restore.2)"))

    def test_restore_that_cannot_write_says_so(self):
        self.prepare()
        real = bl.launcher_restore.write_plugins_txt

        def changed_meanwhile(path, b64, sha):
            write(path, PREPARED + b"*Late.esm\r\n")
            return real(path, b64, sha)

        with mock.patch.object(bl.launcher_restore, "write_plugins_txt", changed_meanwhile), \
                self.assertRaisesRegex(SystemExit, "changed while restoring; nothing written .*run restore again"):
            self.run_bl("restore", "--out", self.out)
        self.assertIsNone(self.record()["restored_at"])
        self.assertNotIn("restoring", self.record())                    # what it found need not hold any more
        self.assertTrue(os.path.exists(self.note))                      # still open
        write(self.pt, PREPARED)
        with plugins_txt_denied(), \
                self.assertRaisesRegex(SystemExit, "could not be written .*run restore again"):
            self.run_bl("restore", "--out", self.out)
        self.assertEqual((read(self.pt), self.record()["restored_at"]), (PREPARED, None))
        self.assertNotIn("restoring", self.record())
        self.log(BASE_LOG, 5)
        self.assertEqual(self.run_bl("collect", "--out", self.out)[0], 0)   # nothing written: collect still works
        self.run_bl("restore", "--out", self.out)
        self.assertEqual(read(self.pt), ORIGINAL)

    def test_a_restore_that_stops_before_its_record_is_finished_by_the_next(self):
        self.prepare()
        with mock.patch.object(bl, "write_json", side_effect=OSError("disk full")), \
                self.assertRaisesRegex(SystemExit, "could not be written .*disk full.*so nothing was written"):
            self.run_bl("restore", "--out", self.out)                   # the note of what it found: nothing written
        self.assertEqual(read(self.pt), PREPARED)
        real, writes = bl.write_json, []

        def record_fails(path, value):
            writes.append(path)
            if len(writes) == 2:                                        # the finished record, after Plugins.txt
                raise OSError("disk full")
            return real(path, value)

        with mock.patch.object(bl, "write_json", record_fails), \
                self.assertRaisesRegex(SystemExit, "Plugins.txt is back, but .*run restore again, which finishes"):
            self.run_bl("restore", "--out", self.out)
        self.assertEqual(read(self.pt), ORIGINAL)
        rec = self.record()
        found = rec["restoring"]
        self.assertEqual((rec["restored_at"], found["ticked"], found["how"], found["sfse"]),
                         (None, [], "byte for byte", []))
        self.assertTrue(os.path.exists(self.note))                      # still open: the runner launches nothing
        self.assertIn(f"Plugins.txt: back. A restore at {found['at']} stopped before it updated the record, and the "
                      f"baseline's time ended then; collect waits for the record: restore again finishes the record",
                      self.run_bl("status", "--out", self.out)[1])
        first = self.log(BASE_LOG, 5, "Papyrus.1.log")                  # the baseline session's
        later = write(os.path.join(self.mg, "Logs", "Script", "Papyrus.0.log"), RUN_LOG.replace("FO4SF", "Other"))
        os.utime(later, (found["epoch"] + 5, found["epoch"] + 5))       # a session with the plugins back on
        with self.assertRaisesRegex(SystemExit, "stopped before it updated the record: run restore again first"):
            self.run_bl("collect", "--out", self.out)                   # it would read our plugins as ticked again
        code, out = self.run_bl("restore", "--out", self.out)
        self.assertEqual(code, 0, out)
        rec = self.record()
        self.assertEqual((rec["restore"], rec["ticked_at_restore"]), ("byte for byte", []))   # not ours, back on
        self.assertEqual((rec["restored_epoch"], rec["restored_at"]), (found["epoch"], found["at"]))   # its time
        self.assertNotIn("restoring", rec)
        self.assertNotIn("collect will not take", out)
        self.assertFalse(os.path.exists(self.note))
        self.assertEqual(self.run_bl("collect", "--out", self.out)[0], 0)
        self.assertEqual([x["path"] for x in self.record()["log"]["sources"]], [first])   # not the later session

    def stop_restore(self):
        """A restore that writes Plugins.txt back, then cannot write its record (the marker of what it found stays)."""
        real, writes = bl.write_json, []

        def record_fails(path, value):
            writes.append(path)
            if len(writes) == 2:                                        # the finished record, after Plugins.txt
                raise OSError("disk full")
            return real(path, value)

        with mock.patch.object(bl, "write_json", record_fails), \
                self.assertRaisesRegex(SystemExit, "Plugins.txt is back, but .*run restore again, which finishes"):
            self.run_bl("restore", "--out", self.out)
        self.assertEqual(read(self.pt), ORIGINAL)
        return self.record()["restoring"]

    def test_a_stopped_restore_is_finished_after_the_games_rewrite(self):
        self.prepare()
        first = self.log(BASE_LOG, 5)                                   # the baseline session's
        found = self.stop_restore()
        rewrite = ORIGINAL.replace(b"*SFBGS003.esm\r\n", b"")          # a start drops the implicit plugin
        write(self.pt, rewrite)
        out = self.run_bl("status", "--out", self.out)[1]               # not "ours ticked again"
        self.assertIn(f"Plugins.txt: the same plugins on in other bytes (the game's rewrite at startup?). A restore "
                      f"at {found['at']} stopped before it updated the record", out)
        self.assertIn("restore again writes the recorded one back, keeping this file, and finishes the record", out)
        code, out = self.run_bl("restore", "--out", self.out)          # not "since prepare, ours were ticked"
        self.assertEqual(code, 0, out)
        rec = self.record()
        self.assertEqual(rec["restore"], f"written back over a file with the same plugins on in other bytes (kept as "
                                         f"{bl.KEPT_AT_RESTORE}), after a restore that stopped at {found['at']}")
        self.assertEqual((rec["restored_epoch"], rec["ticked_at_restore"]), (found["epoch"], []))
        self.assertEqual(read(self.pt), ORIGINAL)                       # byte for byte again
        self.assertEqual(read(os.path.join(self.out, bl.KEPT_AT_RESTORE)), rewrite)
        self.assertFalse(os.path.exists(self.note))
        self.assertEqual(self.run_bl("collect", "--out", self.out)[0], 0)
        self.assertEqual([x["path"] for x in self.record()["log"]["sources"]], [first])

    def test_status_says_what_restore_then_does(self):
        rewrite = ORIGINAL.replace(b"*SFBGS003.esm\r\n", b"")         # the game's rewrite of the original
        prepared_rewrite = PREPARED.replace(b"*SFBGS003.esm\r\n", b"")
        one = PREPARED.replace(b"\r\nFO4Port.esm", b"\r\n*FO4Port.esm")  # one of ours ticked again
        keeps = "writes the recorded one back, keeping this file, and finishes the record"
        refuses = "refuses unless --force (which keeps this file and writes the recorded one back)"
        cases = [   # (what, a restore stopped first, Plugins.txt then (None: gone), status: its state, what restore
            # then does, which restore does)
            ("back", True, ORIGINAL, "back", "finishes the record", "finishes"),
            ("as prepared", True, PREPARED, "as prepared, the plugins off", "puts it back and finishes the record",
             "writes"),
            ("gone", True, None, "gone", "writes the recorded one back and finishes the record", "writes"),
            ("same plugins", True, rewrite, "the same plugins on in other bytes (the game's rewrite at startup?)",
             keeps, "writes"),
            ("another mod", True, ORIGINAL + b"*SomeMod.esp\r\n",
             "FO4Port.esm, FO4SFNewGame.esm, SomeMod.esp ticked, not the same set as the plugins prepare turned off",
             refuses, "refuses"),
            ("one of ours", True, one, "FO4Port.esm ticked, not the same set as the plugins prepare turned off",
             refuses, "refuses"),
            ("prepared, rewritten", True, prepared_rewrite, "rewritten, with no plugin the game does not ship ticked",
             keeps, "writes"),
            ("put back by hand", False, ORIGINAL, "the recorded original already (nothing is off)", "records that",
             "finishes"),
            ("open, as prepared", False, PREPARED, "as prepared, the plugins off", "puts it back", "writes"),
            ("open, gone", False, None, "gone", "writes the recorded one back", "writes"),
            ("ticked again", False, one, "changed since prepare (FO4Port.esm ticked again)", refuses, "refuses"),
            ("open, same plugins", False, rewrite, "changed since prepare (FO4Port.esm, FO4SFNewGame.esm ticked again)",
             refuses, "refuses"),                                       # no restore stopped: the session had them on
            ("the game's rewrite", False, prepared_rewrite,
             "changed since prepare (the game's rewrite at startup, or another tool)",
             "puts it back, keeping this file", "writes"),
        ]
        for n, (what, stop, now, state, then, does) in enumerate(cases):
            row = os.path.join(self.d, f"row{n}")                       # its own: one that fails leaves the rest be
            with self.subTest(what), mock.patch.dict(os.environ, {"FO4_AI_TEAM_STATE": os.path.join(row, "state")}):
                write(self.pt, ORIGINAL)
                self.out, self.note = os.path.join(row, "baseline"), os.path.join(row, "state", bl.OPEN_NOTE)
                self.assertEqual(self.prepare()[0], 0)
                found = self.stop_restore() if stop else None
                if now is None:
                    os.remove(self.pt)
                else:
                    write(self.pt, now)
                says = (f"Plugins.txt: {state}. A restore at {found['at']} stopped before it updated the record, and "
                        f"the baseline's time ended then; collect waits for the record: restore again {then}\n" if stop
                        else f"Plugins.txt: {state}; restore {then}\n")
                self.assertIn(says, self.run_bl("status", "--out", self.out)[1])
                if does == "refuses":
                    with self.assertRaisesRegex(SystemExit, "refused, nothing written"):
                        self.run_bl("restore", "--out", self.out)
                    self.assertEqual(read(self.pt), now)
                    self.assertEqual(self.run_bl("restore", "--out", self.out, "--force")[0], 0)
                else:
                    code, out = self.run_bl("restore", "--out", self.out)
                    self.assertEqual(code, 0, out)
                kept = os.path.join(self.out, bl.KEPT_AT_RESTORE)
                self.assertEqual(os.path.exists(kept), "keep" in then)   # as status said, the file written over
                if "keep" in then:
                    self.assertEqual(read(kept), now)
                self.assertEqual(read(self.pt), ORIGINAL)
                self.assertFalse(os.path.exists(self.note))

    def test_a_restore_note_out_of_restores_own_shape_counts_as_none(self):
        self.prepare()
        self.log(BASE_LOG, 5)
        full = {"ticked": [], "how": "by hand", "sfse": [], "epoch": 1.0, "at": "by hand"}   # restore's own shape
        for marker in ({}, "by hand", {"how": "by hand"}, dict(full, ticked="FO4Port.esm"), dict(full, sfse=[1]),
                       dict(full, epoch="1.0"), dict(full, epoch=True), dict(full, epoch=float("nan")),
                       dict(full, epoch=1793000000), dict(full, epoch=10 ** 400), dict(full, at=""), dict(full, at=5),
                       dict(full, how=None)):                           # restore, status and collect read it alike
            bl.write_json(os.path.join(self.out, bl.RECORD), dict(self.record(), restoring=marker))
            with self.subTest(marker):
                self.assertIn("Plugins.txt: as prepared, the plugins off; restore puts it back",
                              self.run_bl("status", "--out", self.out)[1])
        self.assertEqual(self.run_bl("collect", "--out", self.out)[0], 0)   # it waits for no restore
        code, out = self.run_bl("restore", "--out", self.out)
        self.assertEqual(code, 0, out)
        rec = self.record()
        self.assertEqual((read(self.pt), rec["restore"]), (ORIGINAL, "byte for byte"))
        self.assertNotIn("restoring", rec)
        self.out = os.path.join(self.d, "baseline_2")
        self.prepare()
        self.log(SECOND_LOG, 5)                                         # a session that does not name ours
        bl.write_json(os.path.join(self.out, bl.RECORD), dict(self.record(), restoring={"how": "by hand"}))
        write(self.pt, ORIGINAL)                                        # and ours ticked again since (a deploy)
        code, out = self.run_bl("restore", "--out", self.out)
        self.assertEqual(code, 0, out)
        rec = self.record()                                             # what Plugins.txt says, not the edit
        self.assertEqual((rec["restore"], rec["ticked_at_restore"]),
                         ("already the recorded one (nothing written)", ["FO4Port.esm", "FO4SFNewGame.esm"]))
        self.assertEqual(self.run_bl("collect", "--out", self.out)[0], 1)   # so the session is no baseline
        rec = self.record()
        self.assertEqual((rec["log"], rec["not_vanilla"]["ticked"]), (None, ["FO4Port.esm", "FO4SFNewGame.esm"]))
        self.out = os.path.join(self.d, "baseline_3")
        write(self.pt, b"*SFBGS003.esm\n")
        self.prepare()                                                  # nothing turned off: no restore wrote
        bl.write_json(os.path.join(self.out, bl.RECORD),
                      dict(self.record(), restoring={"ticked": ["Hand.esp"], "how": "by hand", "sfse": [], "epoch": 1.0,
                                                     "at": "by hand"}))
        self.assertEqual(self.run_bl("restore", "--out", self.out)[0], 0)
        rec = self.record()
        self.assertEqual((rec["restored_at"] == "by hand", rec["ticked_at_restore"]), (False, []))   # its own

    def test_a_second_copy_after_a_stopped_restore_is_numbered(self):
        self.prepare()
        prepared_rewrite = PREPARED.replace(b"*SFBGS003.esm\r\n", b"")
        write(self.pt, prepared_rewrite)                                # the session's start rewrote it
        self.stop_restore()                                             # kept that, wrote the original, stopped
        rewrite = ORIGINAL.replace(b"*SFBGS003.esm\r\n", b"")
        write(self.pt, rewrite)                                         # a start rewrote the original since
        code, out = self.run_bl("restore", "--out", self.out)
        self.assertEqual(code, 0, out)
        self.assertEqual(read(self.pt), ORIGINAL)
        self.assertEqual(read(os.path.join(self.out, bl.KEPT_AT_RESTORE)), prepared_rewrite)   # never written over
        self.assertEqual(read(os.path.join(self.out, bl.KEPT_AT_RESTORE + ".2")), rewrite)
        self.assertIn(f"kept as {bl.KEPT_AT_RESTORE}.2", self.record()["restore"])

    def test_a_restore_stopped_before_its_write_puts_back_another_programs_order(self):
        write(self.pt, ORIGINAL + b"*SomeMod.esp\r\n")
        self.prepare()                                                  # turns ours and SomeMod off
        first = self.log(BASE_LOG, 5)

        def closed(*a):                                                 # the window closed after the note of it
            raise KeyboardInterrupt

        with mock.patch.object(bl.launcher_restore, "write_plugins_txt", closed), self.assertRaises(KeyboardInterrupt):
            self.run_bl("restore", "--out", self.out)
        found = self.record()["restoring"]
        self.assertEqual(read(self.pt), PREPARED + b"SomeMod.esp\r\n")  # nothing was written back
        reordered = PREPARED.replace(b"\r\nFO4Port.esm\r\nFO4SFNewGame.esm", b"") + \
            b"*SomeMod.esp\r\n*FO4SFNewGame.esm\r\n*FO4Port.esm\r\n"      # a deploy ticks the same ones, in its order
        write(self.pt, reordered)
        self.assertIn("Plugins.txt: the same plugins on in other bytes", self.run_bl("status", "--out", self.out)[1])
        code, out = self.run_bl("restore", "--out", self.out)
        self.assertEqual(code, 0, out)
        self.assertEqual(read(self.pt), ORIGINAL + b"*SomeMod.esp\r\n")  # the owner's order, byte for byte
        self.assertEqual(read(os.path.join(self.out, bl.KEPT_AT_RESTORE)), reordered)
        rec = self.record()
        self.assertEqual((rec["restored_epoch"], rec["restored_at"], rec["ticked_at_restore"]),
                         (found["epoch"], found["at"], []))           # its time and findings, not the deploy's
        self.assertEqual(self.run_bl("collect", "--out", self.out)[0], 0)
        self.assertEqual([x["path"] for x in self.record()["log"]["sources"]], [first])

    def test_a_stopped_restore_then_another_plugin_ticked_names_the_stop(self):
        self.prepare()
        first = self.log(BASE_LOG, 5)
        found = self.stop_restore()
        write(self.pt, ORIGINAL + b"*SomeMod.esp\r\n")                # the owner turned another mod on since
        with self.assertRaisesRegex(SystemExit, "a restore of this baseline at .* stopped before it updated the "
                                                "record, and Plugins.txt has changed since"):
            self.run_bl("restore", "--out", self.out)
        code, out = self.run_bl("restore", "--out", self.out, "--force")
        self.assertEqual(code, 0, out)
        rec = self.record()
        self.assertEqual((rec["restored_epoch"], rec["ticked_at_restore"]), (found["epoch"], []))   # its time and
        self.assertEqual(read(self.pt), ORIGINAL)                                                  # findings
        self.assertEqual(read(os.path.join(self.out, bl.KEPT_AT_RESTORE)), ORIGINAL + b"*SomeMod.esp\r\n")
        self.assertEqual(self.run_bl("collect", "--out", self.out)[0], 0)
        self.assertEqual([x["path"] for x in self.record()["log"]["sources"]], [first])

    def test_a_moved_baseline_folder_closes_its_note(self):
        self.prepare()
        moved = os.path.join(self.d, "moved", "baseline_1")
        os.makedirs(os.path.dirname(moved))
        shutil.move(self.out, moved)
        self.assertEqual(self.run_bl("restore", "--out", moved)[0], 0)
        self.assertEqual(read(self.pt), ORIGINAL)
        self.assertFalse(os.path.exists(self.note))                     # the runner is free again

    def test_an_open_baseline_whose_record_cannot_be_read_is_never_lost(self):
        write(self.pt, ORIGINAL + b"*SomeMod.esp\r\n")
        self.prepare()                                                  # turns ours and SomeMod off
        away = self.out + "_unplugged"
        os.rename(self.out, away)                                       # its drive is not there
        write(self.pt, PREPARED.replace(b"\r\nFO4Port.esm", b"\r\n*FO4Port.esm") + b"SomeMod.esp\r\n")  # deployed
        later = os.path.join(self.d, "other", "baseline_2")
        code, out = self.run_bl("check", "--starfield", self.game, "--my-games", self.mg)
        self.assertEqual(code, 1, out)
        self.assertIn(f"names {self.out}, whose record cannot be read", out)
        with self.assertRaisesRegex(SystemExit, f"names {re.escape(self.out)}, whose record cannot be read"):
            self.prepare(later)
        self.assertFalse(os.path.exists(later))
        self.assertEqual(bl.read_json(self.note)["out"], self.out)       # the only pointer to the original stays
        os.rename(away, self.out)                                       # plugged in again
        write(os.path.join(self.out, bl.RECORD), b'{"schema": 1, "prepared')   # and its record damaged
        with self.assertRaisesRegex(SystemExit, "whose record cannot be read"):
            self.prepare(later)

    def test_a_note_or_record_that_cannot_be_looked_up_counts_as_open(self):
        self.prepare()
        real = os.lstat
        for blocked in (self.note, os.path.join(self.out, bl.RECORD)):
            def denied(path, *a, blocked=blocked, **k):                 # no permission, a drive that does not answer
                if os.path.abspath(path) == blocked:
                    raise PermissionError(13, "Access is denied", path)
                return real(path, *a, **k)

            with self.subTest(blocked), mock.patch.object(bl.os, "lstat", denied):
                self.assertEqual((bl.noted(os.path.dirname(self.note)) or [None])[0], self.out)   # not "absent"

    def test_restore_refuses_a_damaged_record(self):
        self.prepare()
        rec = self.record()
        with mock.patch.object(bl.launcher_restore, "write_plugins_txt", side_effect=KeyboardInterrupt), \
                self.assertRaises(KeyboardInterrupt):
            self.run_bl("restore", "--out", self.out)                   # one that stopped before its write
        held = self.record()
        one = PREPARED.replace(b"\r\nFO4Port.esm", b"\r\n*FO4Port.esm")  # one of ours ticked again
        damaged = ("Plugins.txt: not the recorded original, and the record's copy of it does not match its sha256 (the "
                   "record was changed or damaged since prepare): restore refuses to write it")
        for base in (rec, held):
            for copy in (bl.b64(b"*SFBGS003.esm\r\n"), "not base64!"):     # edited by hand, or damaged
                for now in (ORIGINAL, PREPARED, one):
                    bl.write_json(os.path.join(self.out, bl.RECORD), dict(base, plugins_txt_b64=copy))
                    write(self.pt, now)
                    if now == ORIGINAL:                                 # nothing to write, so no copy is needed
                        stop = held["restoring"]
                        self.assertIn(f"Plugins.txt: back. A restore at {stop['at']} stopped before it updated the "
                                      f"record, and the baseline's time ended then; collect waits for the record: "
                                      f"restore again finishes the record\n" if base is held else
                                      "Plugins.txt: the recorded original already (nothing is off); restore records "
                                      "that\n", self.run_bl("status", "--out", self.out)[1])
                        code, out = self.run_bl("restore", "--out", self.out)
                        self.assertEqual(code, 0, out)
                        done = self.record()
                        self.assertEqual(done["restore"], stop["how"] if base is held else
                                         "already the recorded one (nothing written)")
                        if base is held:
                            self.assertEqual(done["restored_epoch"], stop["epoch"])
                        continue
                    for force in ((), ("--force",)):                    # the first refusal names it: --force is no help
                        with self.subTest(stopped=base is held, copy=copy, now=now, force=force), \
                                self.assertRaisesRegex(SystemExit, "^restore: refused, nothing written: the record's "
                                                                   "copy of Plugins.txt does not match its sha256"):
                            self.run_bl("restore", "--out", self.out, *force)
                    self.assertEqual(read(self.pt), now)
                    self.assertIsNone(self.record()["restored_at"])
                    out = self.run_bl("status", "--out", self.out)[1]
                    self.assertIn(damaged + (f". A restore at {held['restoring']['at']} stopped before it updated the "
                                             f"record, and the baseline's time ended then; collect waits for the "
                                             f"record, which restore finishes only once Plugins.txt is the recorded "
                                             f"original again\n" if base is held else "\n"), out)

    def test_restore_when_already_back_or_gone(self):
        self.prepare()
        write(self.pt, ORIGINAL)                                   # put back by hand: nothing to write
        code, out = self.run_bl("restore", "--out", self.out)
        rec = self.record()
        self.assertEqual(rec["restore"], "already the recorded one (nothing written)")
        self.assertEqual(rec["ticked_at_restore"], ["FO4Port.esm", "FO4SFNewGame.esm"])   # when? not known
        self.assertIn("collect will not take its log as the baseline", out)
        for gone in (lambda: os.remove(self.pt), lambda: shutil.rmtree(os.path.dirname(self.pt))):
            os.remove(os.path.join(self.out, bl.RECORD))
            self.prepare()
            gone()                                                      # the file, or its folder too
            self.assertEqual(self.run_bl("restore", "--out", self.out)[0], 0)
            self.assertEqual(read(self.pt), ORIGINAL)
            self.assertEqual(self.record()["restore"], "written back (the file was gone)")

    def test_nothing_to_turn_off(self):
        write(self.pt, b"*SFBGS003.esm\n")
        code, out = self.prepare()
        self.assertEqual(code, 0, out)
        self.assertIn("turned off: nothing", out)
        self.assertEqual(read(self.pt), b"*SFBGS003.esm\n")
        self.assertIn("never changed (nothing was turned off)", self.run_bl("status", "--out", self.out)[1])
        bl.write_json(os.path.join(self.out, bl.RECORD), dict(self.record(), plugins_txt_b64="not base64!"))
        write(self.pt, b"*SFBGS003.esm\n*SomeMod.esp\n")              # changed since, and the copy damaged:
        self.assertIn("nothing to put back", self.run_bl("restore", "--out", self.out)[1])   # neither matters
        self.assertIsNotNone(self.record()["restored_epoch"])          # it still ends the baseline's time
        self.assertIn("restore ran", self.run_bl("status", "--out", self.out)[1])
        self.log(BASE_LOG, 7200)                                        # a modded session days later
        with self.assertRaisesRegex(SystemExit, "written after restore"):
            self.run_bl("collect", "--out", self.out)

    def test_status(self):
        with self.assertRaisesRegex(SystemExit, "no baseline"):
            self.run_bl("status", "--out", self.out)
        self.prepare()
        out = self.run_bl("status", "--out", self.out)[1]
        self.assertIn("turned off FO4Port.esm, FO4SFNewGame.esm", out)
        self.assertIn("log: not collected yet", out)
        self.assertIn("as prepared, the plugins off", out)
        write(self.pt, ORIGINAL)                                         # put back by hand
        self.assertIn("the recorded original already (nothing is off)", self.run_bl("status", "--out", self.out)[1])
        write(self.pt, b"*SFBGS003.esm\n")                               # the game's rewrite
        self.assertIn("changed since prepare (the game's rewrite at startup, or another tool)",
                      self.run_bl("status", "--out", self.out)[1])
        os.remove(self.pt)
        self.assertIn("Plugins.txt: gone", self.run_bl("status", "--out", self.out)[1])
        write(self.pt, PREPARED)
        p = self.log(BASE_LOG, 60)
        self.run_bl("collect", "--out", self.out)
        self.run_bl("restore", "--out", self.out)
        out = self.run_bl("status", "--out", self.out)[1]
        self.assertIn(f"from {p}: 1 errors, 0 warnings", out)
        self.assertIn("restored", out)
        self.assertIn("now the recorded one", out)

    def test_compare(self):
        self.prepare()
        with self.assertRaisesRegex(SystemExit, "not collected yet"):
            self.run_bl("compare", "--out", self.out, "--run-log", "x")
        self.log(BASE_LOG, 60)
        self.run_bl("collect", "--out", self.out)
        self.run_bl("restore", "--out", self.out)
        with self.assertRaisesRegex(SystemExit, "is not there"):
            self.run_bl("compare", "--out", self.out, "--run-log", os.path.join(self.d, "no.log"))
        run = write(os.path.join(self.d, "run", "Papyrus.0.log"), RUN_LOG)
        report = os.path.join(self.d, "compare.json")
        code, out = self.run_bl("compare", "--out", self.out, "--run-log", run, "--report", report)
        self.assertEqual(code, 0, out)
        self.assertIn("only in this run, naming one of ours: 1 kinds, 1 lines", out)
        self.assertIn("in both runs (Starfield's own, or the game's): 1 kinds, 1 lines", out)
        self.assertIn("built-in plugins: the same 2 as at the baseline (names and sizes)", out)
        self.assertIn("Starfield.exe: the same as at the baseline (size and sha256)", out)
        self.assertNotIn("also turned off", out)                         # only ours were on
        with open(report, encoding="utf-8") as f:
            rep = json.load(f)
        self.assertEqual(rep["summary"]["ours"]["kinds"], 1)
        self.assertEqual(rep["baseline_record"], os.path.join(self.out, bl.RECORD))
        self.assertEqual((rep["starfield_exe"], rep["also_off"]),
                         ("Starfield.exe: the same as at the baseline (size and sha256)", ""))
        with open(os.path.join(self.data, "SFBGS003.esm"), "ab") as f:      # a Starfield update since the baseline
            f.write(b"\0")
        plugin(os.path.join(self.data, "SFBGS050.esm"))
        write(os.path.join(self.game, "Starfield.exe"), b"ZM")             # the same size, other bytes
        out = self.run_bl("compare", "--out", self.out, "--run-log", run)[1]
        self.assertIn("built-in plugins differ from the baseline's: added SFBGS050.esm; changed size SFBGS003.esm", out)
        self.assertIn("Starfield.exe differs from the baseline's (a Starfield update? re-run the baseline)", out)
        with open(os.path.join(self.out, "Papyrus.0.log"), "a", encoding="utf-8") as f:
            f.write("[1] edited\n")
        with self.assertRaisesRegex(SystemExit, "changed since collect"):
            self.run_bl("compare", "--out", self.out, "--run-log", run)

    def test_compare_never_writes_over_the_baselines_files(self):
        self.prepare()
        self.log(BASE_LOG, 60)
        self.run_bl("collect", "--out", self.out)
        run = write(os.path.join(self.d, "run", "Papyrus.0.log"), RUN_LOG)
        kept = {p: read(p) for p in (os.path.join(self.out, bl.RECORD), os.path.join(self.out, "Papyrus.0.log"),
                                     run, self.pt)}
        for target, what in ((bl.RECORD, "the baseline's baseline.json"), ("Papyrus.0.log", "the baseline's Papyrus.0.log"),
                             (bl.KEPT_AT_RESTORE, "the baseline's Plugins.txt.at-restore")):
            with self.subTest(target), self.assertRaisesRegex(SystemExit, f"would write over {what}"):
                self.run_bl("compare", "--out", self.out, "--run-log", run, "--report", os.path.join(self.out, target))
        for target, what in ((run, "the run's log"), (self.pt, "Plugins.txt"), (self.note, "the open-baseline note")):
            with self.subTest(what), self.assertRaisesRegex(SystemExit, f"would write over {what}"):
                self.run_bl("compare", "--out", self.out, "--run-log", run, "--report", target)
        game_files = [write(os.path.join(self.data, "Starfield.json"), b"{}"),     # files of the game's own
                      write(os.path.join(self.mg, "Data", "x.json"), b"{}"),
                      write(os.path.join(os.path.dirname(self.pt), "x.json"), b"{}")]
        kept.update({p: read(p) for p in game_files + [self.note]})
        for target, why in ((os.path.join(self.out, "compare.txt"), "it is not a .json file"),
                            (game_files[0], f"it is in the game folder, {self.game}"),
                            (game_files[1], f"it is in a My Games folder, {self.mg}"),
                            (game_files[2], "it is in Plugins.txt's folder"),
                            (os.path.join(self.mg, "Logs", "Script", "new.json"), "it is in a My Games folder")):
            with self.subTest(why), self.assertRaisesRegex(SystemExit, re.escape(why)):
                self.run_bl("compare", "--out", self.out, "--run-log", run, "--report", target)
        self.assertFalse(os.path.exists(os.path.join(self.out, "compare.txt")))
        others = [write(os.path.join(self.d, "old", bl.RECORD), json.dumps({"schema": 1})),   # another baseline's
                  write(os.path.join(self.d, "queue", "queue.json"), b"{}")]                  # a test queue's
        kept.update({p: read(p) for p in others})
        for target in others:
            with self.subTest(target), self.assertRaisesRegex(SystemExit, "a file that is not a compare report"):
                self.run_bl("compare", "--out", self.out, "--run-log", run, "--report", target)
        self.assertEqual({p: read(p) for p in kept}, kept)
        mine = os.path.join(self.out, "compare_run.json")                # the runbook's place for it
        self.assertEqual(self.run_bl("compare", "--out", self.out, "--run-log", run, "--report", mine)[0], 0)
        self.assertEqual(self.run_bl("compare", "--out", self.out, "--run-log", run, "--report", mine)[0], 0)  # again
        self.assertEqual(self.run_bl("restore", "--out", self.out)[0], 0)  # the record still restores

    def test_compare_names_the_plugins_not_ours_the_baseline_turned_off(self):
        write(self.pt, ORIGINAL + b"*SomeMod.esp\r\n")                    # someone else's mod was on too
        self.prepare()
        self.assertEqual(self.record()["turned_off"], ["FO4Port.esm", "FO4SFNewGame.esm", "SomeMod.esp"])
        self.log(BASE_LOG, 60)
        self.run_bl("collect", "--out", self.out)
        self.run_bl("restore", "--out", self.out)
        run = write(os.path.join(self.d, "run", "Papyrus.0.log"), RUN_LOG)
        out = self.run_bl("compare", "--out", self.out, "--run-log", run)[1]
        self.assertIn("the baseline also turned off plugins not ours (SomeMod.esp): in a run with any of them on, "
                      "their errors count as Starfield's own", out)

    def test_a_link_leads_where_it_points(self):
        self.prepare()
        self.log(BASE_LOG, 60)
        self.run_bl("collect", "--out", self.out)
        run = write(os.path.join(self.d, "run", "Papyrus.0.log"), RUN_LOG)
        try:
            os.symlink(self.game, os.path.join(self.d, "gamelink"), target_is_directory=True)
            os.symlink(self.out, os.path.join(self.d, "outlink"), target_is_directory=True)
        except (OSError, NotImplementedError) as e:
            self.skipTest(f"no directory links here: {e}")
        for target, why in ((os.path.join(self.d, "outlink", bl.RECORD),
                             "would write over the baseline's baseline.json"),
                            (os.path.join(self.d, "gamelink", "Data", "x.json"),
                             f"it is in the game folder, {self.game}")):
            with self.subTest(why), self.assertRaisesRegex(SystemExit, re.escape(why)):
                self.run_bl("compare", "--out", self.out, "--run-log", run, "--report", target)
        with self.assertRaisesRegex(SystemExit, re.escape(f"is in the game folder, {self.game}")):
            self.prepare(os.path.join(self.d, "gamelink", "baseline"))

    def test_every_write_is_on_disk_before_it_takes_its_name(self):
        order, real_sync, real_replace = [], os.fsync, os.replace

        def steps(run):
            del order[:]
            with mock.patch.object(os, "fsync", lambda fd: order.append("fsync") or real_sync(fd)), \
                    mock.patch.object(os, "replace", lambda a, b: order.append(os.path.basename(b)) or real_replace(a, b)):
                run()
            return list(order)

        self.assertEqual(steps(self.prepare), ["fsync", bl.RECORD, "fsync", bl.OPEN_NOTE, "fsync", "Plugins.txt"])
        self.log(BASE_LOG, 5)
        self.assertEqual(steps(lambda: self.run_bl("collect", "--out", self.out)),
                         ["fsync", bl.LOG_NAME, "fsync", bl.RECORD])
        write(self.pt, PREPARED.replace(b"*SFBGS003.esm\r\n", b""))    # the game's rewrite: restore keeps a copy
        self.assertEqual(steps(lambda: self.run_bl("restore", "--out", self.out)),
                         ["fsync", "fsync", bl.RECORD, "fsync", "Plugins.txt", "fsync", bl.RECORD])   # the copy first

    def test_a_log_the_game_moved_on_by_copying_is_not_the_baselines(self):
        old = write(os.path.join(self.mg, "Logs", "Script", "Papyrus.0.log"), RUN_LOG)   # a modded session's, before
        os.utime(old, (1, 1))
        self.prepare()
        moved = os.path.join(self.mg, "Logs", "Script", "Papyrus.1.log")
        shutil.copyfile(old, moved)                                     # moved on by a copy that takes a new time
        t = self.record()["prepared_epoch"] + 5
        os.utime(moved, (t, t))
        self.log(BASE_LOG, 60)                                          # the baseline session's own
        code, out = self.run_bl("collect", "--out", self.out)
        self.assertEqual(code, 0, out)
        self.assertEqual([x["path"] for x in self.record()["log"]["sources"]],
                         [os.path.join(self.mg, "Logs", "Script", "Papyrus.0.log")])

    def test_a_game_that_changed_since_prepare_gives_no_baseline(self):
        changes = (lambda: write(os.path.join(self.game, "Starfield.exe"), b"MZ, updated"),
                   lambda: plugin(os.path.join(self.data, "SFBGS003.esm"),
                                  records=[(b"QUST", 0x00003448), (b"QUST", 0x00003449)]))
        for i, change in enumerate(changes):
            with self.subTest(i):
                shutil.rmtree(self.out, ignore_errors=True)
                write(self.pt, ORIGINAL)
                self.prepare()
                self.log(BASE_LOG.replace("05:20:01", f"07:0{i}:01"), 5)   # each session's own log
                change()                                                # Steam updated it before the session?
                code, out = self.run_bl("collect", "--out", self.out)
                self.assertEqual(code, 1, out)
                self.assertIn("not a session of the recorded game (the game changed since prepare", out)
                self.assertIsNone(self.record()["log"])
                self.run_bl("restore", "--out", self.out)
        shutil.rmtree(self.out)
        write(self.pt, ORIGINAL)
        self.prepare()
        self.log(BASE_LOG.replace("05:20:01", "07:09:01"), 5)
        os.rename(self.game, self.game + "_away")                       # its drive is not there
        with self.assertRaisesRegex(SystemExit, "whether the game changed since prepare is not known"):
            self.run_bl("collect", "--out", self.out)
        self.assertIsNone(self.record()["log"] or self.record()["not_vanilla"])   # nothing changed: run it again
        os.rename(self.game + "_away", self.game)
        self.assertEqual(self.run_bl("collect", "--out", self.out)[0], 0)

    def test_the_record_is_written_before_plugins_txt(self):
        order = []
        real_json, real_write = bl.write_json, bl.launcher_restore.write_plugins_txt
        with mock.patch.object(bl, "write_json", lambda p, v: order.append(os.path.basename(p)) or real_json(p, v)), \
                mock.patch.object(bl.launcher_restore, "write_plugins_txt",
                                  lambda *a: order.append("Plugins.txt") or real_write(*a)):
            self.prepare()
        self.assertEqual(order, [bl.RECORD, bl.OPEN_NOTE, "Plugins.txt"])
        self.assertLess(abs(self.record()["prepared_epoch"] - time.time()), 60)

    def test_a_name_the_console_cannot_print_never_fails_a_step(self):
        write(self.pt, ORIGINAL + "*Modж.esm\r\n".encode("utf-8"))
        self.prepare()
        env = dict(os.environ, PYTHONIOENCODING="cp1252")                # strict, as Windows' piped stdout
        script = os.path.join(ROOT, "scripts", "game", "baseline.py")
        r = subprocess.run([sys.executable, script, "status", "--out", self.out], env=env, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(b"Mod\\u0436.esm", r.stdout)


if __name__ == "__main__":
    unittest.main()
