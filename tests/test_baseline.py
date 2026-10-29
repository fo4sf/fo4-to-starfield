"""scripts/game/baseline.py, the vanilla baseline: prepare turns off every plugin the game does not ship and keeps
every other byte of Plugins.txt, refuses when the load set would not be vanilla or an earlier baseline was never
restored (the open-baseline note finds one anywhere), collect joins the logs written after prepare and before restore
and never keeps one as the baseline when the session was not vanilla (its log names ours, a plugin was ticked again,
SFSE ran), restore puts the bytes back (over the game's own rewrite, never over a ticked plugin unless forced, keeping
the file it writes over, never from a damaged record, and a restore that stopped before its record is finished by the
next), compare groups a run's log against the baseline's and never writes its report over the baseline's files or into
the game's folders. A made-up game folder, My Games folder, LOCALAPPDATA and runner state folder, and a clock that
moves 10 s at every read (prepare and restore never share a time, as they can on a coarse clock)."""
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
        clock = [time.time()]

        def tick():
            clock[0] += 10
            return clock[0]

        for patch in (mock.patch.dict(os.environ, env), mock.patch.object(bl, "game_running", return_value=False),
                      mock.patch.object(bl, "time", SimpleNamespace(time=tick))):
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
                self.assertRaisesRegex(SystemExit, "changed while restoring; nothing written"):
            self.prepare()
        self.assertFalse(os.path.exists(os.path.join(self.out, bl.RECORD)) or os.path.exists(self.note))
        self.assertEqual(read(self.pt), ORIGINAL + b"*Late.esm\r\n")

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
        code, out = self.prepare(later)                                 # a note naming no baseline is stale
        self.assertEqual(code, 0, out)
        self.assertEqual(bl.read_json(self.note)["out"], later)
        self.run_bl("restore", "--out", later)
        self.assertFalse(os.path.exists(self.note))
        blocked = write(os.path.join(self.d, "blocked"), b"a file, not a folder")   # the note cannot be written
        os.remove(os.path.join(self.out, bl.RECORD))
        with mock.patch.dict(os.environ, {"FO4_AI_TEAM_STATE": os.path.join(blocked, "state")}), \
                self.assertRaisesRegex(SystemExit, "open-baseline note .* could not be written"):
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
        with self.assertRaisesRegex(SystemExit, "session was not vanilla .*names ours"):
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
        self.assertEqual(read(os.path.join(self.out, bl.KEPT_AT_RESTORE)), b"*Mod\xe9.esm\n")

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
        self.assertEqual((rec["restored_at"], rec["restoring"]), (None, {"ticked": [], "how": "byte for byte"}))
        self.assertTrue(os.path.exists(self.note))                      # still open: the runner launches nothing
        self.assertIn("back, but the restore stopped before it updated the record",
                      self.run_bl("status", "--out", self.out)[1])
        self.log(BASE_LOG, 5)                                           # the baseline session's
        with self.assertRaisesRegex(SystemExit, "stopped before it updated the record: run restore again first"):
            self.run_bl("collect", "--out", self.out)                   # it would read our plugins as ticked again
        code, out = self.run_bl("restore", "--out", self.out)
        self.assertEqual(code, 0, out)
        rec = self.record()
        self.assertEqual((rec["restore"], rec["ticked_at_restore"]), ("byte for byte", []))   # not ours, back on
        self.assertNotIn("restoring", rec)
        self.assertNotIn("collect will not take", out)
        self.assertFalse(os.path.exists(self.note))
        self.assertEqual(self.run_bl("collect", "--out", self.out)[0], 0)

    def test_restore_refuses_a_damaged_record(self):
        self.prepare()
        rec = self.record()
        for copy in (bl.b64(b"*SFBGS003.esm\r\n"), "not base64!"):     # edited by hand, or damaged
            bl.write_json(os.path.join(self.out, bl.RECORD), dict(rec, plugins_txt_b64=copy))
            with self.subTest(copy), self.assertRaisesRegex(SystemExit, "does not match its sha256.*changed or damaged"):
                self.run_bl("restore", "--out", self.out)
            self.assertEqual(read(self.pt), PREPARED)
            self.assertIsNone(self.record()["restored_at"])

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
        self.assertIn("nothing to put back", self.run_bl("restore", "--out", self.out)[1])
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
        self.assertEqual({p: read(p) for p in kept}, kept)
        mine = os.path.join(self.out, "compare_run.json")                # the runbook's place for it
        self.assertEqual(self.run_bl("compare", "--out", self.out, "--run-log", run, "--report", mine)[0], 0)
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
