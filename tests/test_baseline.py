"""scripts/game/baseline.py, the vanilla baseline: prepare turns off every plugin the game does not ship and keeps
every other byte of Plugins.txt, refuses when the load set would not be vanilla, collect takes only a log written
after prepare, restore puts the bytes back (over the game's own rewrite, never over a ticked plugin unless forced),
compare groups a run's log against the baseline's. A made-up game folder, My Games folder and LOCALAPPDATA."""
import contextlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
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
        for patch in (mock.patch.dict(os.environ, {"LOCALAPPDATA": os.path.join(d, "local")}),
                      mock.patch.object(bl, "game_running", return_value=False)):
            patch.start()
            self.addCleanup(patch.stop)

    def run_bl(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = bl.main(list(argv))
        return code, buf.getvalue()

    def prepare(self):
        return self.run_bl("prepare", "--starfield", self.game, "--my-games", self.mg, "--out", self.out)

    def record(self):
        with open(os.path.join(self.out, bl.RECORD), encoding="utf-8") as f:
            return json.load(f)

    def log(self, text, age):
        p = write(os.path.join(self.mg, "Logs", "Script", "Papyrus.0.log"), text)
        t = self.record()["prepared_epoch"] + age
        os.utime(p, (t, t))
        return p

    def test_untick_keeps_every_other_byte(self):
        self.assertEqual(bl.untick(ORIGINAL), (PREPARED, ["FO4Port.esm", "FO4SFNewGame.esm"]))
        self.assertEqual(bl.untick(b"  *Mod.esp\n*notes.txt\n*BlueprintShips-Starfield.esm"),
                         (b"  Mod.esp\n*notes.txt\n*BlueprintShips-Starfield.esm", ["Mod.esp"]))
        with self.assertRaisesRegex(SystemExit, "not UTF-8"):
            bl.untick(b"*\xff.esm\n")

    def test_check_writes_nothing(self):
        code, out = self.run_bl("check", "--starfield", self.game, "--my-games", self.mg)
        self.assertEqual(code, 0, out)
        self.assertIn("prepare would turn off: FO4Port.esm, FO4SFNewGame.esm", out)
        self.assertIn("PASS    start: overrides of Starfield's start are the pinned ones: none", out)   # [] pinned
        self.assertIn("check: prepare would go ahead", out)
        self.assertEqual(read(self.pt), ORIGINAL)
        self.assertFalse(os.path.exists(self.out))

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
        with self.assertRaisesRegex(SystemExit, "already holds a baseline"):
            self.prepare()

    def test_prepare_refuses_and_changes_nothing(self):
        cases = [
            ("running", lambda: mock.patch.object(bl, "game_running", return_value=True), "Starfield is running"),
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
        with self.assertRaisesRegex(SystemExit, "no Data folder"):
            self.run_bl("prepare", "--starfield", self.d, "--my-games", self.mg, "--out", self.out)
        self.assertEqual(read(self.pt), ORIGINAL)
        self.assertFalse(os.path.exists(self.out))

    def test_prepare_that_loses_a_race_leaves_no_record(self):
        real = bl.launcher_restore.write_plugins_txt

        def changed_meanwhile(path, b64, sha):
            write(path, ORIGINAL + b"*Late.esm\r\n")
            return real(path, b64, sha)

        with mock.patch.object(bl.launcher_restore, "write_plugins_txt", changed_meanwhile), \
                self.assertRaisesRegex(SystemExit, "changed while restoring; nothing written"):
            self.prepare()
        self.assertFalse(os.path.exists(os.path.join(self.out, bl.RECORD)))
        self.assertEqual(read(self.pt), ORIGINAL + b"*Late.esm\r\n")

    def test_collect_takes_only_a_log_written_after_prepare(self):
        self.prepare()
        with self.assertRaisesRegex(SystemExit, "no Papyrus.0.log"):
            self.run_bl("collect", "--out", self.out)
        self.log(BASE_LOG, -60)
        with self.assertRaisesRegex(SystemExit, "last written before prepare"):
            self.run_bl("collect", "--out", self.out)
        self.log(BASE_LOG, 60)
        code, out = self.run_bl("collect", "--out", self.out)
        self.assertEqual(code, 0, out)
        self.assertIn("1 errors, 0 warnings, 1 notes", out)
        rec = self.record()
        self.assertEqual((rec["log"]["file"], rec["log"]["ours"], rec["log"]["counts"]["error"]), ("Papyrus.0.log", [], 1))
        self.assertEqual(read(os.path.join(self.out, "Papyrus.0.log")), BASE_LOG.encode("utf-8"))
        self.log(RUN_LOG, 120)                                     # a session that loaded our new game plugin
        code, out = self.run_bl("collect", "--out", self.out)
        self.assertEqual(code, 1)
        self.assertIn("the log names ours (FO4SF_NewGameScript, FO4SFNewGameQuest)", out)

    def test_restore_puts_the_bytes_back(self):
        self.prepare()
        code, out = self.run_bl("restore", "--out", self.out)
        self.assertEqual(code, 0, out)
        self.assertEqual(read(self.pt), ORIGINAL)
        self.assertEqual(self.record()["restore"], "byte for byte")
        self.assertIn("FO4Port.esm, FO4SFNewGame.esm back on", out)
        self.assertIn("already restored", self.run_bl("restore", "--out", self.out)[1])

    def test_restore_over_the_games_own_rewrite(self):
        self.prepare()
        write(self.pt, b"*SFBGS003.esm\nFO4Port.esm\n")           # the game rewrote it at startup: nothing ticked
        self.run_bl("restore", "--out", self.out)
        self.assertEqual(read(self.pt), ORIGINAL)
        self.assertEqual(self.record()["restore"], "over the game's own rewrite (it ticked no plugin)")

    def test_restore_refuses_a_ticked_plugin_unless_forced(self):
        self.prepare()
        ticked = PREPARED.replace(b"\r\nFO4Port.esm", b"\r\n*FO4Port.esm")
        write(self.pt, ticked)
        with self.assertRaisesRegex(SystemExit, "FO4Port.esm were ticked"):
            self.run_bl("restore", "--out", self.out)
        self.assertEqual(read(self.pt), ticked)
        with mock.patch.object(bl, "game_running", return_value=True), self.assertRaisesRegex(SystemExit, "running"):
            self.run_bl("restore", "--out", self.out, "--force")
        self.run_bl("restore", "--out", self.out, "--force")
        self.assertEqual(read(self.pt), ORIGINAL)
        self.assertEqual(read(os.path.join(self.out, bl.KEPT_AT_RESTORE)), ticked)
        self.assertTrue(self.record()["restore"].startswith("forced over a file with FO4Port.esm ticked"))

    def test_restore_when_already_back_or_gone(self):
        self.prepare()
        write(self.pt, ORIGINAL)                                   # put back by hand: nothing to write
        self.run_bl("restore", "--out", self.out)
        self.assertEqual(self.record()["restore"], "already the recorded one (nothing written)")
        os.remove(os.path.join(self.out, bl.RECORD))
        self.prepare()
        os.remove(self.pt)
        self.run_bl("restore", "--out", self.out)
        self.assertEqual(read(self.pt), ORIGINAL)

    def test_nothing_to_turn_off(self):
        write(self.pt, b"*SFBGS003.esm\n")
        code, out = self.prepare()
        self.assertEqual(code, 0, out)
        self.assertIn("turned off: nothing", out)
        self.assertEqual(read(self.pt), b"*SFBGS003.esm\n")
        self.assertIn("nothing to put back", self.run_bl("restore", "--out", self.out)[1])
        self.assertIn("never changed", self.run_bl("status", "--out", self.out)[1])

    def test_status(self):
        with self.assertRaisesRegex(SystemExit, "no baseline"):
            self.run_bl("status", "--out", self.out)
        self.prepare()
        out = self.run_bl("status", "--out", self.out)[1]
        self.assertIn("turned off FO4Port.esm, FO4SFNewGame.esm", out)
        self.assertIn("log: not collected yet", out)
        self.assertIn("as prepared, our plugins off", out)
        self.log(BASE_LOG, 60)
        self.run_bl("collect", "--out", self.out)
        self.run_bl("restore", "--out", self.out)
        out = self.run_bl("status", "--out", self.out)[1]
        self.assertIn("1 errors, 0 warnings", out)
        self.assertIn("restored", out)
        self.assertIn("now the recorded one", out)

    def test_compare(self):
        self.prepare()
        with self.assertRaisesRegex(SystemExit, "not collected yet"):
            self.run_bl("compare", "--out", self.out, "--run-log", "x")
        self.log(BASE_LOG, 60)
        self.run_bl("collect", "--out", self.out)
        self.run_bl("restore", "--out", self.out)
        run = write(os.path.join(self.d, "run", "Papyrus.0.log"), RUN_LOG)
        report = os.path.join(self.d, "compare.json")
        code, out = self.run_bl("compare", "--out", self.out, "--run-log", run, "--report", report)
        self.assertEqual(code, 0, out)
        self.assertIn("only in this run, naming one of ours: 1 kinds, 1 lines", out)
        self.assertIn("in both runs (Starfield's own, or the game's): 1 kinds, 1 lines", out)
        self.assertIn("built-in plugins: the same 2 as at the baseline (names and sizes)", out)
        with open(report, encoding="utf-8") as f:
            rep = json.load(f)
        self.assertEqual(rep["summary"]["ours"]["kinds"], 1)
        self.assertEqual(rep["baseline_record"], os.path.join(self.out, bl.RECORD))
        with open(os.path.join(self.data, "SFBGS003.esm"), "ab") as f:      # a Starfield update since the baseline
            f.write(b"\0")
        plugin(os.path.join(self.data, "SFBGS050.esm"))
        out = self.run_bl("compare", "--out", self.out, "--run-log", run)[1]
        self.assertIn("built-in plugins differ from the baseline's: added SFBGS050.esm; changed size SFBGS003.esm", out)
        with open(os.path.join(self.out, "Papyrus.0.log"), "a", encoding="utf-8") as f:
            f.write("[1] edited\n")
        with self.assertRaisesRegex(SystemExit, "changed since collect"):
            self.run_bl("compare", "--out", self.out, "--run-log", run)

    def test_the_record_is_written_before_plugins_txt(self):
        order = []
        real_json, real_write = bl.write_json, bl.launcher_restore.write_plugins_txt
        with mock.patch.object(bl, "write_json", lambda p, v: order.append("record") or real_json(p, v)), \
                mock.patch.object(bl.launcher_restore, "write_plugins_txt",
                                  lambda *a: order.append("plugins") or real_write(*a)):
            self.prepare()
        self.assertEqual(order, ["record", "plugins"])
        self.assertLess(abs(self.record()["prepared_epoch"] - time.time()), 60)


if __name__ == "__main__":
    unittest.main()
