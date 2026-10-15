"""console_pre / console_post of queued terrain and npc_nav tests (scripts/game/console_plan.py, testqueue.py, qstep.ps1):
only whitelisted console lines pass planning and the step, the console reply is read from the OCR after the command's
last echo, and the judge and the report show the replies. Synthetic data; no game. The step itself runs against the
simulated console in tests/test_qstep_sandbox.py (opt-in)."""
import json
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import console_plan as cp  # noqa: E402
import sky_light as sl  # noqa: E402
import testqueue as tq  # noqa: E402
from test_testqueue import FakeControls, args, jdump, jload, readf, touch, writef  # noqa: E402

BORDER = ['GetINI "bBorderRegionsEnabled:General"', 'GetINI "fPlayableAreaX:General"',
          'GetINI "uPlayableSpaceOverlayCellBuffer:Planet"', 'SetINI "bBorderRegionsEnabled:General" 0',
          'GetINI "bBorderRegionsEnabled:General"']
GOOD = BORDER + ['SetINI "fPlayableAreaX:General" -1.5', 'SetINI "uMaximumPlayableAreaWorldCoord:General" 100000',
                 "SetLocalTime 12", "SetLocalTime 9.5 1", "SetLocalTime 0", "SetLocalTime 23.99",
                 'cgf "Game.SetLocalTime" 12', "fw 0000015E", "fw 0000015e 1"]
BAD = ["qqq", "player.additem 0000000F 100", "tgm", "coc FO4Core_RedRocketSpawn", "GetINI bBorderRegionsEnabled:General",
       'GetINI "bBorderRegionsEnabled"', 'GetINI "bBorder Regions:General"', 'GetINI "bBorderRegionsEnabled:General" 1',
       'getini "bBorderRegionsEnabled:General"', 'SetINI "bBorderRegionsEnabled:General"',
       'SetINI "bBorderRegionsEnabled:General" abc', 'SetINI "bBorderRegionsEnabled:General" 0; tgm',
       'SetINI "bBorderRegionsEnabled:General" 0|key:enter|type:tgm', 'GetINI "bBorderRegionsEnabled:General"\n',
       'GetINI "bBorderRegionsEnabled:General" ', ' GetINI "bBorderRegionsEnabled:General"',
       "GetINI “bBorderRegionsEnabled:General”", 'GetINI "a:b";qqq', 'SetINI "a:b" 1e9',
       "SetLocalTime 24", "SetLocalTime 12 2", "SetLocalTime -1", "SetLocalTime 12.345", 'cgf "Game.PassTime" 12',
       'cgf "Game.SetLocalTime" 12 1', "fw 15E", "fw 0000015E 2", "set gamehour to 12", "PassTime 4", "", None, 12,
       'GetINI "' + "a" * 65 + ':General"']


class Bad(Exception):
    pass


def fail(msg):
    raise Bad(msg)


class WhitelistTests(unittest.TestCase):
    def test_allowed_and_refused(self):
        for c in GOOD:
            self.assertTrue(cp.allowed(c), c)
        for c in BAD:
            self.assertFalse(cp.allowed(c), repr(c))

    def test_time_of_day_commands_pass_the_whitelist(self):
        for t in ({"time_of_day": h, "weather": "0000015E", "weather_lock": True} for h in (0.0, 6.25, 12.0, 23.99)):
            for c in sl.commands(t):
                self.assertTrue(cp.allowed(c), c)

    def test_qstep_has_the_same_pattern(self):
        src = readf(os.path.join(ROOT, "scripts", "game", "qstep.ps1"), encoding="utf-8")
        m = re.search(r"\$consoleOk = '\^\(\?:(.*)\)\\z'", src)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), cp.PATTERN)
        ps = re.compile("^(?:" + m.group(1) + r")\Z")            # .NET \z is Python \Z
        for c in GOOD:
            self.assertTrue(ps.match(c), c)
        for c in BAD:
            self.assertFalse(isinstance(c, str) and ps.match(c), repr(c))
        # terrain, npc_nav, door_trip, walk and movable_control
        self.assertEqual(src.count("Run-Console $preCmds 'pre'"), 5)
        self.assertEqual(src.count("Run-Console $postCmds 'post'"), 4)
        self.assertIn("-cnotmatch $consoleOk", src)

    def test_fields(self):
        self.assertEqual(cp.console_fields({}, fail), {})
        self.assertEqual(cp.console_fields({"console_pre": BORDER, "console_post": []}, fail), {"console_pre": BORDER})
        for w in ({"console_pre": "GetINI \"a:b\""}, {"console_pre": ["qqq"]}, {"console_post": ["player.additem 0000000F 1"]},
                  {"console_pre": ['GetINI "a:b"'] * 13}, {"console_post": [None]}):
            with self.assertRaises(Bad, msg=w):
                cp.console_fields(w, fail)


class ReplyTests(unittest.TestCase):
    def test_getini_value_after_the_last_echo(self):
        ocr = ('Get Po s: X > > 1.0\nGetlNl "bBorderRegionsEnabled:General"\n'
               'lNlSetting bBorderRegionsEnabIed:General > > 1\nGetlNl "fPlayableAreaX:General"\n'
               'lNlSetting fPlayableAreaX:General > > 3200.0000\nSetINI "bBorderRegionsEnabled:General" 0\n'
               'GetlNl "bBorderRegionsEnabled:General"\nlNlSetting bBorderRegionsEnabled:General > > 0\n')
        self.assertEqual(cp.reply(BORDER[4], ocr), {"status": "value", "value": "0", "note": ""})
        self.assertEqual(cp.reply(BORDER[1], ocr)["value"], "3200.0000")
        self.assertEqual(cp.reply(BORDER[3], ocr)["status"], "no reply")

    def test_a_missing_reply_is_not_taken_from_an_older_line(self):
        ocr = ('GetINI "bBorderRegionsEnabled:General"\nINISetting bBorderRegionsEnabled:General >> 1\n'
               'GetINI "bBorderRegionsEnabled:General"\n')
        self.assertEqual(cp.reply(BORDER[0], ocr)["status"], "unread")

    def test_echo_without_quotes_still_marks_the_start(self):
        ocr = 'INISetting bBorderRegionsEnabled:General >> 1\nGetlNl bBorderRegionsEnabled:General\n' \
              'INISetting bBorderRegionsEnabled:General >> 0'
        self.assertEqual(cp.reply(BORDER[0], ocr)["value"], "0")

    def test_not_found_errors_and_strings(self):
        self.assertEqual(cp.reply('GetINI "x:General"', 'GetINI "x:General"\nINISetting x:General > > NOT FOUND')["status"],
                         "not found")
        r = cp.reply('SetINI "x:General" 0', 'SetINI "x:General" 0\nINI setting "x:General" does not exist')
        self.assertEqual((r["status"], r["note"]), ("error", 'INI setting "x:General" does not exist'))
        r = cp.reply('SetINI "fPlayableAreaX:General" 0', 'SetINI "fPlayableAreaX:General" 0\n'
                     'INI setting "fPlayableAreaX:General" is not a float')
        self.assertEqual(r["status"], "error")
        other = cp.reply('SetINI "a:General" 0', 'SetINI "a:General" 0\nINI setting "b:General" does not exist')
        self.assertEqual(other["status"], "no reply")                    # another setting's error is not this one's
        self.assertEqual(cp.reply('GetINI "s:Planet"', "GetINI s:Planet\nINISetting s:Planet >> 'abc'")["value"], "abc")
        self.assertEqual(cp.reply("SetLocalTime 12", "SetLocalTime 12\nSetLocalTime only works on a planet.")["status"],
                         "error")
        self.assertEqual(cp.reply("fw 0000015E", "fw 0000015E")["status"], "no reply")
        self.assertEqual(cp.reply(BORDER[0], "")["status"], "unread")
        self.assertEqual(cp.reply(BORDER[0], None)["status"], "unread")


def console_obs(*pairs, phase="pre"):
    return [{"phase": phase, "cmd": c, "ocr": o, "shot": f"console_{k}.png"} for k, (c, o) in enumerate(pairs, 1)]


TERRAIN = {"kind": "terrain", "points": [{"label": "ground", "x": 0.0, "y": 0.0, "expect": 10.0}]}


class JudgeReportTests(unittest.TestCase):
    def test_summary_and_judge_detail(self):
        d = tempfile.mkdtemp()
        t = dict(TERRAIN, console_pre=BORDER[:2] + [BORDER[3]], console_post=[BORDER[0]])
        obs = {"shot": touch(d, "spawn.png"), "points": [{"read": "0 0 10.1"}],
               "console": console_obs((BORDER[0], 'GetINI "bBorderRegionsEnabled:General"\n'
                                                  "INISetting bBorderRegionsEnabled:General >> 1"),
                                      (BORDER[1], 'GetINI "fPlayableAreaX:General"'))}
        v = tq.judge(t, obs, d)
        self.assertEqual(v[:2], ("PASS", "PASS"))                        # replies are shown, never judged
        self.assertIn("[console pre: GetINI bBorderRegionsEnabled:General = 1; GetINI fPlayableAreaX:General (unread: "
                      "no INISetting reply read); 2 of 3 typed] [console post: 0 of 1 typed]", v[2])
        self.assertNotIn("console", tq.judge(TERRAIN, obs, d)[2])        # nothing planned: nothing shown
        npc = tq.npc_test(0, {"travel": "coc QASmoke", "npc": "0000CF96", "a": [0, 0, 0], "b": [10, 0, 0],
                              "console_pre": [BORDER[0]]})
        self.assertIn("[console pre: 0 of 1 typed]", tq.judge(npc, {"console": []}, d)[2])

    def test_runner_records_and_report(self):
        d = tempfile.mkdtemp()
        test = dict(TERRAIN, id="0000_terrain_A", cell="", ref="A", model="core64", console_pre=BORDER)
        jdump({"build_id": "abcd1234", "commit": "0" * 40, "staging": d, "plugin_sha256": "x", "save": "s",
               "plugin_index": "02", "hours": [[0, 24]], "tests": [test]}, os.path.join(d, "queue.json"))
        replies = ["INISetting bBorderRegionsEnabled:General >> 1", "INISetting fPlayableAreaX:General >> 3200.0000",
                   "INISetting uPlayableSpaceOverlayCellBuffer:Planet >> 2", "",
                   "INISetting bBorderRegionsEnabled:General >> 0"]

        def step(t, out):
            jdump({"shot": touch(out, "spawn.png"), "points": [{"read": "0 0 10.0"}],
                   "console": console_obs(*[(c, c + "\n" + r) for c, r in zip(BORDER, replies)])},
                  os.path.join(out, "obs.json"))
            return 0
        r = tq.Runner(d, args(), ctl=FakeControls(), step=step)
        r.session = True
        r.run()
        rec = [json.loads(x) for x in readf(os.path.join(d, "results.jsonl")).splitlines()][0]
        self.assertEqual(rec["verdict"], "PASS")
        self.assertEqual([(c["status"], c["value"]) for c in rec["console"]],
                         [("value", "1"), ("value", "3200.0000"), ("value", "2"), ("no reply", None), ("value", "0")])
        rep = readf(os.path.join(d, "report.md"), encoding="utf-8")
        self.assertIn("## Console replies", rep)
        self.assertIn('| 0000_terrain_A | pre | `SetINI "bBorderRegionsEnabled:General" 0` | no reply |  |', rep)
        self.assertIn('| 0000_terrain_A | pre | `GetINI "bBorderRegionsEnabled:General"` | 0 |  |', rep)
        self.assertEqual(len(jload(os.path.join(d, "report.json"))["console"]), 5)


class PlanTimeoutTests(unittest.TestCase):
    def test_plan_terrain_keeps_the_console_fields_and_refuses_others(self):
        d = tempfile.mkdtemp()
        writef(os.path.join(d, "FO4Port.esm"), b"TES4")
        pts = [{"label": "p", "x": 1.0, "y": 2.0, "expect": 3.0}]
        jdump([{"coc": "A", "points": pts, "console_pre": BORDER, "console_post": [BORDER[0]]}],
              os.path.join(d, "plan.json"))
        out = os.path.join(d, "q")
        tq.main(["plan-terrain", "--staging", d, "--exp-dir", d, "--out", out, "--fresh"])
        t = jload(os.path.join(out, "queue.json"))["tests"][0]
        self.assertEqual((t["console_pre"], t["console_post"]), (BORDER, [BORDER[0]]))
        for bad in (["qqq"], ["player.additem 0000000F 100"]):
            jdump([{"coc": "A", "points": pts, "console_pre": bad}], os.path.join(d, "plan.json"))
            with self.assertRaises(SystemExit):
                tq.main(["plan-terrain", "--staging", d, "--exp-dir", d, "--out", out])
        with self.assertRaises(SystemExit):
            tq.npc_test(0, {"travel": "coc QASmoke", "npc": "0000CF96", "a": [0, 0, 0], "b": [1, 0, 0],
                            "console_post": ["qqq"]})

    def test_step_timeout(self):
        base = tq.step_timeout(TERRAIN)
        self.assertEqual(tq.step_timeout(dict(TERRAIN, console_pre=BORDER, console_post=[BORDER[0]])),
                         base + 6 * tq.CONSOLE_CMD_S)
        n = tq.npc_test(0, {"travel": "coc QASmoke", "npc": "0000CF96", "a": [0, 0, 0], "b": [10, 0, 0]})
        self.assertEqual(tq.step_timeout(dict(n, console_pre=BORDER)), tq.step_timeout(n) + 5 * tq.CONSOLE_CMD_S)

    def test_hops_and_settle_count_in_the_terrain_timeout(self):
        pts = [{"label": "a", "x": 0.0, "y": 0.0, "expect": 0.0}, {"label": "b", "x": 205.0, "y": 0.0, "expect": 0.0},
               {"label": "c", "x": 1000.0, "y": 0.0, "expect": 0.0}, {"label": "d", "x": 3000.0, "y": 0.0, "expect": 0.0}]
        t = {"kind": "terrain", "points": pts}
        self.assertEqual(tq.terrain_hops(t), 0)
        self.assertEqual(tq.terrain_hops(dict(t, hop_m=300)), 0 + 2 + 6)  # ceil(795/300)-1, ceil(2000/300)-1
        base = tq.step_timeout(t)
        self.assertEqual(base, 150 + 90 * 5)
        self.assertEqual(tq.step_timeout(dict(t, hop_m=300, hop_wait_ms=7000)), base + 8 * (tq.HOP_S + 7))
        self.assertEqual(tq.step_timeout(dict(t, settle_ms=10500)), 150 + 96 * 5)


if __name__ == "__main__":
    unittest.main()
