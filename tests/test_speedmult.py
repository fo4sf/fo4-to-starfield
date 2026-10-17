"""The run condition of a walk (2026-10-17): the player's speedmult read and set back to 100 before the travel
(console_plan.py SPEEDMULT_*, testqueue.py --speedmult, qstep.ps1 $consoleOk), a test that does not start at 100
judged INCONCLUSIVE RUNCOND, and a stale last_sent_tick.txt no longer read as the owner's input
(testqueue.read_tick_file), and the dedicated save matched by its exact file name (testqueue.dedicated_save).
Synthetic data; no game."""
import os
import re
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import console_plan as cp  # noqa: E402
import runner_features  # noqa: E402
import testqueue as tq  # noqa: E402
from test_testqueue import readf  # noqa: E402

GOOD = ["player.getav speedmult", "player.setav speedmult 100"]
BAD = ["player.setav speedmult 300", "player.setav speedmult 1000", "player.setav speedmult", "player.getav SpeedMult",
       "player.setav speedmult 100; tgm", "player.setav speedmult 100 ", "player.getav speedmult\n",
       "player.getav health", "player.setav health 100", "player.modav speedmult 100", "setav speedmult 100"]


def con(*pairs):
    """obs.console rows of the pre phase: (cmd, ocr)."""
    return {"console": [{"phase": "pre", "cmd": c, "ocr": o} for c, o in pairs]}


def got(v):
    return f"player.getav speedmult\nGetActorValue: SpeedMult >> {v}"


class WhitelistTests(unittest.TestCase):
    def test_only_the_read_and_the_reset_to_100_pass(self):
        for c in GOOD:
            self.assertTrue(cp.allowed(c), c)
        for c in BAD:
            self.assertFalse(cp.allowed(c), repr(c))

    def test_qstep_refuses_the_same_lines(self):
        src = readf(os.path.join(ROOT, "scripts", "game", "qstep.ps1"), encoding="utf-8")
        ps = re.compile("^(?:" + re.search(r"\$consoleOk = '\^\(\?:(.*)\)\\z'", src).group(1) + r")\Z")
        for c in GOOD:
            self.assertTrue(ps.match(c), c)
        for c in BAD:
            self.assertFalse(ps.match(c), repr(c))

    def test_the_feature_is_needed_and_known(self):
        t = cp.with_speedmult({"kind": "walk"})
        self.assertIn("speedmult", runner_features.needs([t]))
        self.assertIn("speedmult", runner_features.FEATURES)
        self.assertNotIn("speedmult", runner_features.needs([{"kind": "walk", "console_pre": ["SetLocalTime 12"]}]))


class ReplyTests(unittest.TestCase):
    def test_the_value_after_the_echo(self):
        self.assertEqual(cp.reply(cp.SPEEDMULT_GET, got("300.00")), {"status": "value", "value": "300.00", "note": ""})
        self.assertEqual(cp.reply(cp.SPEEDMULT_GET, "player.getav speedmult\nGetActorValue: SpeedMult >> 100,00")["value"],
                         "100.00")

    def test_an_older_reply_before_the_echo_is_not_read(self):
        ocr = "GetActorValue: SpeedMult >> 300.00\nplayer.getav speedmult\n"
        self.assertEqual(cp.reply(cp.SPEEDMULT_GET, ocr)["status"], "unread")
        self.assertEqual(cp.reply(cp.SPEEDMULT_GET, "")["status"], "unread")


class ConditionTests(unittest.TestCase):
    T = cp.with_speedmult({"kind": "walk", "console_pre": ["SetLocalTime 12"]})

    def test_with_speedmult_puts_the_lines_first_once(self):
        self.assertEqual(self.T["console_pre"], cp.SPEEDMULT_PRE + ["SetLocalTime 12"])
        self.assertEqual(cp.with_speedmult(self.T)["console_pre"], self.T["console_pre"])
        with self.assertRaises(ValueError):
            cp.with_speedmult({"console_pre": ["SetLocalTime 12"] * 10})

    def test_not_checked_without_the_read(self):
        self.assertIsNone(cp.speedmult_condition({"console_pre": ["SetLocalTime 12"]}, con()))

    def test_the_last_read_decides_and_every_read_is_named(self):
        ok, why = cp.speedmult_condition(self.T, con((cp.SPEEDMULT_GET, got("300.00")), (cp.SPEEDMULT_SET, ""),
                                                     (cp.SPEEDMULT_GET, got("100.00"))))
        self.assertTrue(ok)
        self.assertIn("300, set 100, 100", why)
        ok, why = cp.speedmult_condition(self.T, con((cp.SPEEDMULT_GET, got("300.00")), (cp.SPEEDMULT_SET, ""),
                                                     (cp.SPEEDMULT_GET, got("300.00"))))
        self.assertFalse(ok)
        self.assertIn("speedmult 300 at the start", why)

    def test_unread_or_untyped_is_not_ok(self):
        self.assertFalse(cp.speedmult_condition(self.T, con((cp.SPEEDMULT_GET, got("100")), (cp.SPEEDMULT_SET, ""),
                                                            (cp.SPEEDMULT_GET, "garbled")))[0])
        self.assertFalse(cp.speedmult_condition(self.T, con())[0])
        self.assertFalse(cp.speedmult_condition(self.T, {})[0])


class JudgeTests(unittest.TestCase):
    T = dict(cp.with_speedmult({"kind": "walk", "id": "0000_walk_x"}), expect="PASS")

    def judge(self, kind_verdict, value):
        obs = con((cp.SPEEDMULT_GET, got(value)), (cp.SPEEDMULT_SET, ""), (cp.SPEEDMULT_GET, got(value)))
        with mock.patch.object(tq, "judge_kind", return_value=kind_verdict):
            return tq.judge(self.T, obs, tempfile.gettempdir())

    def test_a_walk_at_another_speed_is_inconclusive_whatever_the_judge_said(self):
        for kv in (("FAIL", "STUCK", "3 legs without movement"), ("FAIL", "JUMP", "39.8 m in 2.2 s"),
                   ("PASS", "PASS", "goal reached")):
            v, cls, detail = self.judge(kv, "300.00")
            self.assertEqual((v, cls), ("INCONCLUSIVE", "RUNCOND"), kv)
            self.assertIn(f"the judge said {kv[0]} {kv[1]}", detail)

    def test_at_100_the_verdict_stands_and_shows_the_reads(self):
        v, cls, detail = self.judge(("FAIL", "STUCK", "stuck"), "100.00")
        self.assertEqual((v, cls), ("FAIL", "STUCK"))
        self.assertIn("[speedmult 100 at the start", detail)

    def test_an_inconclusive_keeps_its_own_class(self):
        self.assertEqual(self.judge(("INCONCLUSIVE", "UNREAD", "no leg"), "300.00")[:2], ("INCONCLUSIVE", "UNREAD"))


class PlannerTests(unittest.TestCase):
    def test_speedmult_tests(self):
        tests = [{"kind": "walk"}, {"kind": "walk", "console_pre": ["SetLocalTime 12"]}]
        self.assertEqual(tq.speedmult_tests(tests, SimpleNamespace(speedmult=False)), tests)
        out = tq.speedmult_tests(tests, SimpleNamespace(speedmult=True))
        self.assertTrue(all(t["console_pre"][:3] == cp.SPEEDMULT_PRE for t in out))

    def test_both_planners_take_the_option(self):
        src = readf(os.path.join(ROOT, "scripts", "game", "testqueue.py"), encoding="utf-8")
        self.assertEqual(src.count('add_argument("--speedmult"'), 2)
        self.assertEqual(src.count("speedmult_tests("), 3)            # the definition, plan-walk, plan-movable


class TickFileTests(unittest.TestCase):
    def setUp(self):
        self.p = os.path.join(tempfile.mkdtemp(), "last_sent_tick.txt")

    def write(self, text):
        with open(self.p, "w") as f:
            f.write(text)

    def test_a_fresh_tick_counts(self):
        now = time.time()
        self.write(f"5000000 {now - 30:.0f}")
        self.assertEqual(tq.read_tick_file(self.p, now, lambda: 5030000), 5000000)

    def test_a_stale_or_unknown_tick_is_ignored(self):
        now = time.time()
        self.write(f"5000000 {now - tq.TICK_FRESH_S - 60:.0f}")             # an earlier run's
        self.assertIsNone(tq.read_tick_file(self.p, now, lambda: 9000000))
        self.write("5000000")                                                 # the old format: no time
        self.assertIsNone(tq.read_tick_file(self.p, now, lambda: 5030000))
        self.write(f"5000000 {now + 600:.0f}")                                # written in the future
        self.assertIsNone(tq.read_tick_file(self.p, now, lambda: 5030000))
        self.write(f"5000000 {now - 30:.0f}")                                 # the PC restarted since
        self.assertIsNone(tq.read_tick_file(self.p, now, lambda: 1000))
        self.assertIsNone(tq.read_tick_file(self.p + ".none", now, lambda: 1000))

    def test_mark_sent_writes_the_time(self):
        src = readf(os.path.join(ROOT, "scripts", "game", "testqueue.py"), encoding="utf-8")
        self.assertIn('f.write(f"{self.last_sent_tick} {time.time():.0f}")', src)
        self.assertIn("read_tick_file(self.tick_file, time.time(), self._tick)", src)


class DedicatedSaveTests(unittest.TestCase):
    def saves(self, *names):
        d = tempfile.mkdtemp()
        for n in names:
            open(os.path.join(d, n), "w").close()
        return d

    def test_only_the_exact_file_name(self):
        d = self.saves("fo4sf_test_1d4591b6.sfs.bak", "fo4sf_test_1d4591b6_s100.sfs", "Autosave2.sfs")
        self.assertIsNone(tq.dedicated_save(d, "fo4sf_test_1d4591b6"))
        self.assertEqual(tq.dedicated_save(d, "fo4sf_test_1d4591b6_s100"), os.path.join(d, "fo4sf_test_1d4591b6_s100.sfs"))
        d = self.saves("FO4SF_TEST_1D4591B6.SFS", "fo4sf_test_1d4591b6.sfs.bak")
        self.assertEqual(tq.dedicated_save(d, "fo4sf_test_1d4591b6"), os.path.join(d, "FO4SF_TEST_1D4591B6.SFS"))
        self.assertIsNone(tq.dedicated_save(os.path.join(d, "missing"), "fo4sf_test_1d4591b6"))

    def test_the_session_uses_it(self):
        src = readf(os.path.join(ROOT, "scripts", "game", "testqueue.py"), encoding="utf-8")
        self.assertNotIn('f"*{name}*"', src)
        self.assertEqual(src.count("dedicated_save(saves, name)"), 3)       # the definition and both uses


if __name__ == "__main__":
    unittest.main()
