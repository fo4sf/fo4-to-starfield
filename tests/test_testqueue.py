"""Queued test runner (scripts/game/testqueue.py): judges never pass on missing observations, the run checkpoints after
every test and resumes, retries are limited, and the owner's controls stop it. Synthetic data; no game, no Windows calls."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import testqueue as tq  # noqa: E402


def readb(p):
    with open(p, "rb") as f:
        return f.read()


def jdump(obj, p):
    with open(p, "w") as f:
        json.dump(obj, f)


def jload(p):
    with open(p) as f:
        return json.load(f)


def readf(p, mode="r", **kw):
    with open(p, mode, **kw) as f:
        return f.read()


def writef(p, data, mode="wb"):
    with open(p, mode) as f:
        f.write(data)


def touch(d, name):
    open(os.path.join(d, name), "wb").close()
    return name


class JudgeTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_no_observations_is_inconclusive(self):
        for kind in ("fall", "movable", "travel", "stairs", "door"):
            self.assertEqual(tq.judge({"kind": kind}, None, self.d)[0], "INCONCLUSIVE")
            self.assertEqual(tq.judge({"kind": kind}, {"stopped": "input guard"}, self.d)[0], "INCONCLUSIVE")

    def test_fall(self):
        t = {"kind": "fall", "point": [1.0, 2.0, 3.0]}
        shot = touch(self.d, "fall.png")
        self.assertEqual(tq.judge(t, {"end_read": "1.0 2.0 3.1", "shot": shot}, self.d)[0], "PASS")
        self.assertEqual(tq.judge(t, {"end_read": "1.0 2.0 -20", "shot": shot}, self.d)[:2], ("FAIL", "FALL"))
        self.assertEqual(tq.judge(t, {"end_read": "1.0 2.0 1.5", "shot": shot}, self.d)[:2], ("INCONCLUSIVE", "LOWER"))
        self.assertEqual(tq.judge(t, {"end_read": "9.0 2.0 3.0", "shot": shot}, self.d)[:2], ("INCONCLUSIVE", "MOVED"))
        # a perfect landing without the screenshot is not a pass
        self.assertEqual(tq.judge(t, {"end_read": "1.0 2.0 3.0", "shot": "missing.png"}, self.d)[0], "INCONCLUSIVE")
        self.assertEqual(tq.judge(t, {"end_read": None, "shot": shot}, self.d)[0], "INCONCLUSIVE")

    def test_movable(self):
        t = {"kind": "movable"}
        b, a = touch(self.d, "before.png"), touch(self.d, "after.png")
        base = {"item_before": "5.0 5.0 1.0", "player_end": "5.3 5.0 1.0", "shot_before": b, "shot_after": a}
        self.assertEqual(tq.judge(t, dict(base, item_after="5.4 5.1 1.0"), self.d)[0], "PASS")
        self.assertEqual(tq.judge(t, dict(base, item_after="5.0 5.0 1.0"), self.d)[:2], ("FAIL", "NOTMOVED"))
        self.assertEqual(tq.judge(t, dict(base, item_after="5.0 5.0 -4.0"), self.d)[:2], ("FAIL", "ITEMFELL"))
        far = dict(base, item_after="5.0 5.0 1.0", player_end="9.0 9.0 1.0")
        self.assertEqual(tq.judge(t, far, self.d)[:2], ("INCONCLUSIVE", "MISSED"))
        self.assertEqual(tq.judge(t, dict(base, item_after=None), self.d)[0], "INCONCLUSIVE")

    def test_movable_walk_over_the_item(self):
        # batch_full 0095 (2026-10-12): start 1.1 m before a book, walked over it (0.01 m), ended 3.2 m past it
        t = {"kind": "movable"}
        b, a = touch(self.d, "before.png"), touch(self.d, "after.png")
        obs = {"item_before": "44.92 87.04 11.02", "item_after": "44.92 87.04 11.02", "player_start": "44.37 86.09 10.97",
               "player_end": "46.45 89.85 10.87", "shot_before": b, "shot_after": a}
        v, c, d = tq.judge(t, obs, self.d)
        self.assertEqual((v, c), ("FAIL", "NOTMOVED"), d)
        self.assertIn("passed 0.02 m", d)
        # a walk that never comes near the item stays MISSED
        side = dict(obs, player_start="40.0 80.0 11.0", player_end="41.0 80.0 11.0")
        self.assertEqual(tq.judge(t, side, self.d)[:2], ("INCONCLUSIVE", "MISSED"))
        self.assertAlmostEqual(tq.seg_dist_xy((0, 0, 0), (0, 0, 0), (3, 4, 0)), 5.0)

    def test_travel(self):
        t = {"kind": "travel", "start": [0.0, 0.0, 0.0], "arrival": [100.0, 50.0, 2.0], "dest_cell": "B"}
        s = touch(self.d, "arrival.png")
        ok = {"start_read": "0.2 0.1 0.0", "prompt": True, "end_read": "101.0 50.5 2.0", "shot": s, "load_s": 9}
        self.assertEqual(tq.judge(t, ok, self.d)[0], "PASS")
        self.assertEqual(tq.judge(t, dict(ok, prompt=False), self.d)[:2], ("FAIL", "NOPROMPT"))
        self.assertEqual(tq.judge(t, dict(ok, end_read="0.5 0.2 0.0"), self.d)[:2], ("FAIL", "NOTRAVEL"))
        self.assertEqual(tq.judge(t, dict(ok, start_read="30 30 0"), self.d)[0], "INCONCLUSIVE")
        self.assertEqual(tq.judge(t, dict(ok, shot=None), self.d)[0], "INCONCLUSIVE")

    def test_route_uses_route_eval(self):
        routes = {"routes": [{"kind": "stairs", "start": [0, 0, 0],
                              "expect": {"low": [0, 0, 0], "high": [0, 3, 2], "min_rise": 1.6}}]}
        rf = os.path.join(self.d, "routes.json")
        jdump(routes, rf)
        t = {"kind": "stairs", "routes_file": rf, "route_index": 0}
        up = {"result": {"start_read": "0 0 0", "end_read": "0 2.5 1.9"}, "shots": ["r0.png"]}
        self.assertEqual(tq.judge(t, up, self.d)[0], "PASS")
        stuck = {"result": {"start_read": "0 0 0", "end_read": "0 0.5 0.1"}, "shots": ["r0.png"]}
        self.assertEqual(tq.judge(t, stuck, self.d)[:2], ("FAIL", "STUCK"))
        self.assertEqual(tq.judge(t, dict(up, shots=[]), self.d)[0], "INCONCLUSIVE")
        self.assertEqual(tq.judge(t, {"result": {"skipped": "start not reached"}, "shots": ["x"]}, self.d)[0], "INCONCLUSIVE")


class FakeControls:
    def __init__(self):
        self.stop, self.mode, self.idle, self.foreign, self.fg, self.pid = None, "running", 10 ** 6, False, "starfield.exe", 42
        self.last_sent_tick = None

    def stop_file(self):
        return self.stop

    def guardian_mode(self):
        return self.mode

    def idle_s(self):
        return self.idle

    def foreign_input(self):
        return self.foreign

    def mark_sent(self):
        pass

    def game_in_front(self):
        return bool(self.pid) and self.fg == "starfield.exe"

    def game_pid(self):
        return self.pid

    def owned_pid(self):
        return 42

    def refocus_game(self):
        return True

    def close_game(self):
        self.closed = getattr(self, "closed", 0) + 1
        self.pid = None
        return True


def make_queue(d, n=3, kind="fall"):
    tests = [{"id": f"{k:04d}_{kind}", "kind": kind, "cell": "C", "ref": f"pt{k}", "model": "m.nif",
              "point": [0.0, 0.0, 0.0], "heading": 0} for k in range(n)]
    jdump({"build_id": "abcd1234", "commit": "0" * 40, "staging": d, "plugin_sha256": "x", "save": "fo4sf_test_abcd1234",
           "plugin_index": "02", "hours": [[0, 24]], "tests": tests}, os.path.join(d, "queue.json"))


def args(**kw):
    base = dict(max_tests=10 ** 6, max_hours=1.0, min_idle=900, max_attempts=2, max_relaunch=3, wait_for_idle=False,
                refocus=False, dry_run=False, starfield="")
    base.update(kw)
    return SimpleNamespace(**base)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        make_queue(self.d)
        self.ctl = FakeControls()

    def runner(self, step, **kw):
        r = tq.Runner(self.d, args(**kw), ctl=self.ctl, step=step)
        r.session, r.cell = True, "C"                     # game already set up in the test cell
        r._ps = lambda *a, **k: (0, "at the cell")        # coc after an unknown state: never a real PowerShell here
        return r

    def landing(self, z):
        def step(test, out):
            jdump({"end_read": f"0 0 {z}", "shot": touch(out, "fall.png")}, os.path.join(out, "obs.json"))
            return 0
        return step

    def results(self):
        return [json.loads(x) for x in readf(os.path.join(self.d, "results.jsonl")).splitlines()]

    def test_checkpoint_after_every_test_and_resume(self):
        self.runner(self.landing(0.1), max_tests=2).run()
        st = jload(os.path.join(self.d, "state.json"))
        self.assertEqual(len(st["done"]), 2)
        calls = []

        def step(test, out):
            calls.append(test["id"])
            return self.landing(0.1)(test, out)
        self.runner(step).run()
        self.assertEqual(calls, ["0002_fall"])           # only the test that was left
        self.assertEqual(len(jload(os.path.join(self.d, "state.json"))["done"]), 3)
        self.assertTrue(os.path.exists(os.path.join(self.d, "report.md")))

    def test_inconclusive_is_retried_up_to_the_limit_and_fail_is_final(self):
        calls = {}

        def step(test, out):
            calls[test["id"]] = calls.get(test["id"], 0) + 1
            if test["id"] == "0000_fall":
                return 0                                  # writes nothing: inconclusive
            return self.landing(-20)(test, out)           # fell through: FAIL
        self.runner(step, max_attempts=2).run()
        self.assertEqual(calls, {"0000_fall": 2, "0001_fall": 1, "0002_fall": 1})
        done = jload(os.path.join(self.d, "state.json"))["done"]
        self.assertEqual(done["0000_fall"]["verdict"], "INCONCLUSIVE")
        self.assertEqual(done["0001_fall"]["verdict"], "FAIL")
        rep = jload(os.path.join(self.d, "report.json"))
        self.assertEqual(rep["ranked"][0]["class"], "FALL")
        self.assertEqual(rep["ranked"][0]["count"], 2)

    def test_stop_file_and_guardian_stop_before_any_input(self):
        for setup in (lambda: setattr(self.ctl, "stop", "STOP"), lambda: setattr(self.ctl, "mode", "paused")):
            self.ctl = FakeControls()
            setup()
            calls = []
            r = self.runner(lambda t, o: calls.append(t) or 0)
            self.assertEqual(r.run(), 3)
            self.assertEqual(calls, [])
            self.assertTrue(jload(os.path.join(self.d, "state.json"))["status"].startswith("stopped"))

    def test_owner_input_or_other_window_stops_without_counting_an_attempt(self):
        self.ctl.fg = "chrome.exe"
        calls = []
        self.assertEqual(self.runner(lambda t, o: calls.append(t) or 0).run(), 3)
        self.assertEqual(calls, [])
        self.ctl.fg = "starfield.exe"
        n = [0]

        def step(test, out):
            n[0] += 1
            return 2                                      # input guard tripped mid-step
        self.assertEqual(self.runner(step).run(), 3)
        st = jload(os.path.join(self.d, "state.json"))
        self.assertEqual(st["done"], {})
        self.assertEqual(st["attempts"]["0000_fall"], 0)

    def test_a_popup_that_takes_the_focus_mid_step_reruns_the_test(self):
        # movable_1019c 0009 (2026-10-18): "Assert-Foreground : ABORT: foreground window belongs to 'AMDAutoUpdate',
        # not 'Starfield'. No input sent." with no owner input since the runner's last one: a popup, not the owner
        self.ctl.last_sent_tick = 1000
        n = {}
        logs = []

        def step(test, out):
            n[test["id"]] = n.get(test["id"], 0) + 1
            if test["id"] == "0000_fall" and n[test["id"]] == 1:
                with open(os.path.join(out, "step.log"), "w", encoding="utf-8") as f:
                    f.write("Assert-Foreground : ABORT: foreground window belongs to 'AMDAutoUpdate', not 'Starfield'. "
                            "No input sent.\n")
                return 2
            return self.landing(0.1)(test, out)
        r = self.runner(step, refocus=True)
        r.log = logs.append
        self.assertEqual(r.run(), 0)
        self.assertEqual(n["0000_fall"], 2)
        self.assertEqual(len(jload(os.path.join(self.d, "state.json"))["done"]), 3)
        self.assertTrue(any("AMDAutoUpdate took the focus mid-step without owner input (popup)" in x for x in logs), logs)
        # the interrupted attempt's evidence survives the rerun, which writes a1 afresh (Codex on #341 at f2fe7bf)
        a1 = os.path.join(self.d, "tests", "0000_fall", "a1")
        kept = readf(os.path.join(a1 + "_popup1", "step.log"))
        self.assertIn("foreground window belongs to 'AMDAutoUpdate'", kept)
        self.assertTrue(os.path.exists(os.path.join(a1, "obs.json")))
        self.assertFalse(os.path.exists(os.path.join(a1, "step.log")) and "AMDAutoUpdate" in readf(os.path.join(a1, "step.log")))

    def test_a_resumed_run_keeps_every_interrupted_attempt(self):
        # Codex on #341 at 446b5a9: a second Runner (resumed after a stop) starts its popup count again; its archive
        # must not reuse a1_popup1, which already holds the first run's interrupted attempt
        self.ctl.last_sent_tick = 1000
        a1 = os.path.join(self.d, "tests", "0000_fall", "a1")
        calls = [0]

        def popup_then_stop(test, out):
            calls[0] += 1
            with open(os.path.join(out, "step.log"), "w", encoding="utf-8") as f:
                f.write(f"run {calls[0]}: foreground window belongs to 'AMDAutoUpdate', not 'Starfield'\n")
            if calls[0] == 2:
                self.ctl.foreign = True                   # the owner typed: the first run stops here
            return 2
        self.assertEqual(self.runner(popup_then_stop, refocus=True).run(), 3)
        self.ctl.foreign = False
        self.assertEqual(self.runner(popup_then_stop, refocus=True, max_tests=1).run() in (0, 3, 4), True)
        # every interrupted attempt's step.log is still on disk: none was overwritten by a rerun or the resumed run
        logs = []
        for root, _dirs, files in os.walk(os.path.join(self.d, "tests")):
            logs += [readf(os.path.join(root, f)) for f in files if f == "step.log"]
        self.assertEqual(sorted(x.split(":")[0] for x in logs), sorted(f"run {k}" for k in range(1, calls[0] + 1)))
        self.assertIn("run 1:", readf(os.path.join(a1 + "_popup1", "step.log")))
        kept = sorted(x for x in os.listdir(os.path.dirname(a1)) if x.startswith("a1_popup"))
        self.assertGreaterEqual(len(kept), 2, kept)                    # the resumed run's popup got a fresh name
        self.assertEqual(tq.unused_name(a1 + "_popup"), a1 + f"_popup{len(kept) + 1}")

    def test_a_popup_rerun_is_capped_and_owner_input_still_stops(self):
        self.ctl.last_sent_tick = 1000
        n = [0]

        def step(test, out):
            n[0] += 1
            return 2
        self.assertEqual(self.runner(step, refocus=True).run(), 3)
        # each of the 3 tests rerun at the end of the queue until the first runs out of reruns, then the stop as before
        self.assertEqual(n[0], 3 * tq.POPUP_RETRIES + 1)
        self.assertEqual(jload(os.path.join(self.d, "state.json"))["done"], {})
        n[0] = 0

        def typed(test, out):                             # the owner typed during the step: no rerun
            n[0] += 1
            self.ctl.foreign = True
            return 2
        self.assertEqual(self.runner(typed, refocus=True).run(), 3)
        self.assertEqual(n[0], 1)

    def test_the_window_that_took_the_focus_is_read_from_the_step_log(self):
        d = tempfile.mkdtemp()
        self.assertIsNone(tq.foreground_thief(d))
        with open(os.path.join(d, "step.log"), "w", encoding="utf-8") as f:
            f.write("x\nAssert-Foreground : ABORT: foreground window belongs to 'AMDAutoUpdate', not 'Starfield'.\n")
        self.assertEqual(tq.foreground_thief(d), "AMDAutoUpdate")

    def test_coc_reads_the_arrival_from_the_bridge_when_the_queue_has_one(self):
        # v6e stairs 2026-10-21: the HUD's O2 dial over the console's last lines made every OCR read of the arrival fail
        for bridge, want in ((None, False), ({"dir": "b"}, True)):
            with self.subTest(bridge=bridge):
                self.setUp()
                q = jload(os.path.join(self.d, "queue.json"))
                if bridge:
                    q["bridge"] = bridge
                jdump(q, os.path.join(self.d, "queue.json"))
                calls = []
                r = self.runner(self.landing(0.1), max_tests=1)
                r.cell = "Elsewhere"
                r._ps = lambda script, args, timeout, steal=False: (calls.append((script, args)), (0, "at"))[1]
                r.ensure_game("C")
                cocs = [a for sc, a in calls if sc == "coc.ps1"]
                self.assertEqual(len(cocs), 1)
                self.assertEqual("-Bridge" in cocs[0], want)

    def test_coc_ps1_takes_a_fresh_loaded_bridge_line_at_the_marker_before_the_console(self):
        src = readf(os.path.join(ROOT, "scripts", "game", "coc.ps1"))
        self.assertIn("[switch]$Bridge", src)
        b = src.index("if ($Bridge) {")
        self.assertLess(b, src.index("readpos.ps1"))                    # the bridge first, the OCR only after it
        block = src[b:src.index("readpos.ps1")]
        self.assertIn("'latest', '--max-age', '2'", block)               # a fresh line only
        self.assertIn("$j.loaded -eq $true", block)
        self.assertIn("if ($d -le 5)", block)                           # the same 5 m as the console read
        cyc = readf(os.path.join(ROOT, "scripts", "game", "cycle.ps1"))
        self.assertIn("if (Test-Path (Join-Path $sf 'Data\\FO4SFBridge.install.json')) { $cocArgs += '-Bridge' }", cyc)

    def test_coc_ps1_hops_through_another_cell_when_the_first_coc_misses_the_marker(self):
        # v6e stairs retest 2026-10-21: the save stood inside the library at its door's arrival, 54 m from the marker
        src = readf(os.path.join(ROOT, "scripts", "game", "coc.ps1"))
        self.assertIn("[string]$Via = ''", src)
        tail = src[src.index("Enter-Cell $Cell\nTest-Arrival"):]
        self.assertIn("if ($script:arrived) { exit 0 }", tail)
        hop = tail[tail.index("Enter-Cell $Via"):]
        self.assertTrue(hop.startswith("Enter-Cell $Via\nEnter-Cell $Cell\nTest-Arrival\nif ($script:arrived) { exit 0 }\nexit 1"))
        self.assertIn("if ($f.BaseName -eq $Cell) { continue }", tail)  # never hops through the target itself
        self.assertNotIn("if (Test-Arrival)", src)                       # its printed lines would make the if always true
        self.assertNotIn("return $true", src)

    def test_crash_is_recorded_and_not_a_pass(self):
        def step(test, out):
            self.ctl.pid = None                           # the game exited during the step
            return 0
        r = self.runner(step, max_tests=1)
        r.run()
        self.assertEqual(self.results()[0]["class"], "CRASH")
        self.assertEqual(jload(os.path.join(self.d, "state.json"))["crashes"], 1)

    def test_a_game_that_vanishes_and_fails_the_input_is_a_crash_not_the_owner(self):
        # doors_rounds 2026-10-21: Starfield exited silently mid-step, input.ps1 found no process, no dump was written
        def step(test, out):
            self.ctl.pid = None
            return 2
        r = self.runner(step, max_tests=1)
        r.run()
        self.assertEqual(self.results()[0]["class"], "CRASH")
        self.assertEqual(jload(os.path.join(self.d, "state.json"))["crashes"], 1)
        self.assertNotIn("owner took over", readf(os.path.join(self.d, "run.log")))

    def test_a_game_that_vanishes_and_hides_the_hud_is_a_crash_not_a_menu(self):
        def step(test, out):
            self.ctl.pid = None
            return 3
        r = self.runner(step, max_tests=1)
        r.recover = lambda: self.fail("no Escapes into a game that is gone")
        r.run()
        self.assertEqual(self.results()[0]["class"], "CRASH")
        self.assertNotIn("menu or overlay", readf(os.path.join(self.d, "run.log")))

    def test_a_game_that_vanishes_while_travelling_is_a_crash(self):
        for exit_code in (1, 2):                          # Codex on #446: exit 2 (input guard) is not the owner then
            with self.subTest(exit_code=exit_code):
                self.setUp()

                def ps(script, args, timeout, steal=False):
                    self.ctl.pid = None                   # the game exits during the coc
                    return exit_code, "no arrival"
                r = self.runner(lambda test, out: 0, max_tests=1)
                r.cell, r._ps = "Elsewhere", ps
                r.recover = lambda: self.fail("no Escapes into a game that is gone")
                r.run()
                row = self.results()[0]
                self.assertEqual((row["verdict"], row["class"]), ("INCONCLUSIVE", "CRASH"))
                self.assertEqual(jload(os.path.join(self.d, "state.json"))["crashes"], 1)
                self.assertNotIn("owner", readf(os.path.join(self.d, "run.log")))

    def test_a_game_that_vanished_between_tests_counts_against_the_crash_budget(self):
        r = self.runner(lambda test, out: 0, crash_budget=1, min_free_gb=0)
        r.live_pid, self.ctl.pid = 42, None               # up after the last test, gone before the next one
        r.run()
        log = readf(os.path.join(self.d, "run.log"))
        self.assertIn("exited between tests", log)
        self.assertEqual(jload(os.path.join(self.d, "state.json"))["crashes"], 1)
        self.assertIn("--crash-budget 1", log)            # stopped before launching again
        self.assertFalse(os.path.exists(os.path.join(self.d, "results.jsonl")))

    def test_a_game_closed_for_a_fresh_test_is_not_a_crash(self):
        r = self.runner(self.landing(0.1), max_tests=2)
        r.game_used, r.live_pid = True, 42
        q = jload(os.path.join(self.d, "queue.json"))
        q["tests"][0]["fresh"] = True
        jdump(q, os.path.join(self.d, "queue.json"))
        r.q = q
        r.run()
        self.assertEqual(jload(os.path.join(self.d, "state.json"))["crashes"], 0)

    def test_a_second_crash_in_the_same_test_is_a_final_fail(self):
        def step(test, out):
            self.ctl.pid = None                           # the game exits during every attempt
            return 0
        self.runner(step, max_tests=1).run()
        first = self.results()[0]
        self.assertEqual((first["verdict"], first["class"]), ("INCONCLUSIVE", "CRASH"))
        self.ctl.pid = self.ctl.owned_pid()
        self.runner(step, max_tests=1).run()              # a later run of the same queue: the same test again
        second = self.results()[1]
        self.assertEqual((second["id"], second["verdict"], second["class"]), (first["id"], "FAIL", "CRASH"))
        st = jload(os.path.join(self.d, "state.json"))
        self.assertEqual(st["done"][first["id"]]["verdict"], "FAIL")
        self.assertEqual(st["test_crashes"][first["id"]], 2)
        # review pass on #402: the FAIL CRASH counted as decided and closed the breaker for the kind for good
        self.assertTrue(st.get("breaker"))
        self.assertEqual({k: v["decided"] for k, v in st["breaker"].items()}, {k: 0 for k in st["breaker"]})

    def test_a_crash_recorded_before_the_count_existed_still_counts(self):
        # Codex on #402: a queue paused after an INCONCLUSIVE CRASH has no test_crashes in its state
        def step(test, out):
            self.ctl.pid = None
            return 0
        self.runner(step, max_tests=1).run()
        p = os.path.join(self.d, "state.json")
        st = jload(p)
        del st["test_crashes"]
        jdump(st, p)
        self.ctl.pid = self.ctl.owned_pid()
        self.runner(step, max_tests=1).run()
        second = self.results()[1]
        self.assertEqual((second["verdict"], second["class"]), ("FAIL", "CRASH"), second["detail"])
        self.assertEqual(jload(p)["test_crashes"], {second["id"]: 2})

    def test_a_crash_row_whose_checkpoint_was_lost_still_counts(self):
        # Codex on #402: the row was recorded, then the run stopped before state.json kept the new count
        def step(test, out):
            self.ctl.pid = None
            return 0
        self.runner(step, max_tests=1).run()
        p = os.path.join(self.d, "state.json")
        st = jload(p)
        tid = self.results()[0]["id"]
        st["test_crashes"] = {tid: 0}                     # the checkpoint before the crash
        jdump(st, p)
        self.ctl.pid = self.ctl.owned_pid()
        self.runner(step, max_tests=1).run()
        second = self.results()[1]
        self.assertEqual((second["id"], second["verdict"], second["class"]), (tid, "FAIL", "CRASH"), second["detail"])

    def test_a_recorded_fail_crash_is_final_after_a_lost_checkpoint(self):
        # Codex on #402: the second (final) crash row was recorded, the checkpoint after it was not
        calls = []

        def step(test, out):
            calls.append(test["id"])
            self.ctl.pid = None
            return 0
        self.runner(step, max_tests=1).run()
        p = os.path.join(self.d, "state.json")
        before = jload(p)                                 # the state as the second crash found it
        self.ctl.pid = self.ctl.owned_pid()
        self.runner(step, max_tests=1).run()
        tid = self.results()[1]["id"]
        self.assertEqual(self.results()[1]["verdict"], "FAIL")
        jdump(before, p)                                  # that run's checkpoint lost
        self.ctl.pid = self.ctl.owned_pid()
        calls.clear()
        self.runner(step, max_tests=1).run()
        self.assertNotIn(tid, calls)                      # no third launch into the crash
        self.assertEqual(jload(p)["done"][tid]["verdict"], "FAIL")

    def test_a_count_kept_for_an_excluded_crash_does_not_count(self):
        # Codex on #402: a state count with no eligible CRASH row behind it is dropped, not kept by max()
        def step(test, out):
            self.ctl.pid = None
            return 0
        p = os.path.join(self.d, "state.json")
        self.runner(lambda t, o: 0, max_tests=0).run()
        st = jload(p)
        st["test_crashes"] = {k["id"]: 1 for k in jload(os.path.join(self.d, "queue.json"))["tests"]}
        jdump(st, p)
        self.ctl.pid = self.ctl.owned_pid()
        self.runner(step, max_tests=1).run()
        first = self.results()[-1]
        self.assertEqual((first["verdict"], first["class"]), ("INCONCLUSIVE", "CRASH"), first["detail"])

    def test_someone_elses_game_is_never_touched(self):
        self.ctl.pid = 7                                  # not the pid cycle.ps1 recorded
        calls = []
        r = tq.Runner(self.d, args(), ctl=self.ctl, step=lambda t, o: calls.append(t) or 0)
        self.assertEqual(r.run(), 3)
        self.assertEqual(calls, [])

    def test_launch_waits_for_an_idle_pc(self):
        self.ctl.pid, self.ctl.idle = None, 30            # no game yet, owner active 30 s ago
        r = tq.Runner(self.d, args(min_idle=900), ctl=self.ctl, step=lambda t, o: 0)
        r._ps = lambda *a, **k: self.fail("must not launch while the owner is active")
        self.assertEqual(r.run(), 3)


class StepScriptTests(unittest.TestCase):
    def test_qstep_handles_every_planned_kind(self):
        # the supervised run 2026-10-11 found "unknown kind stairs": the planner's kinds must all reach a step
        src = readf(os.path.join(ROOT, "scripts", "game", "qstep.ps1"), encoding="utf-8")
        for kind in tq.KINDS:
            self.assertTrue(f"'{kind}'" in src, kind)
        self.assertIn("$kind -in 'stairs', 'door'", src)
        self.assertIn("enabled|disabled", src)


class ProbePointTests(unittest.TestCase):
    def test_floor_pieces_by_file_name_not_folder(self):
        import subprocess
        d = tempfile.mkdtemp()
        kit = "Interiors\Building\Deco\Small_FloorCeilKit\\"
        refs = [{"type": "Static", "model": kit + name, "pos": [70.0 * k * 5, 0.0, 0.0]} for k, name in
                enumerate(["BldDecoSmCeilOnly03.nif", "BldDecoSmFlrOnly04.nif", "BldWlpSmFlrCeil01.nif",
                           "SubPlatformWall03.nif", "BldWoodPSmStairsHalfTiny03.nif"])]
        jdump({"cell": "C", "refs": refs}, os.path.join(d, "c.json"))
        out = os.path.join(d, "pts.txt")
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "game", "probe_points.py"), os.path.join(d, "c.json"),
                        out, "10"], check=True, capture_output=True)
        names = sorted(line.split(" ", 3)[3] for line in readf(out).splitlines())
        self.assertEqual(names, ["BldDecoSmFlrOnly04.nif", "BldWlpSmFlrCeil01.nif", "BldWoodPSmStairsHalfTiny03.nif"])


class RecoverTests(RunnerTests):
    def test_menu_over_the_hud_is_escaped_once_then_the_test_retried(self):
        calls = []

        def step(test, out):
            calls.append(test["kind"])
            if test["kind"] == "recover":
                jdump({"hud_before": False, "escapes": 1, "hud_after": True}, os.path.join(out, "obs.json"))
                return 0
            if calls.count("fall") == 1:
                jdump({"stopped": "console not opened safely (3)"}, os.path.join(out, "obs.json"))
                return 3
            return self.landing(0.1)(test, out)
        self.runner(step, max_tests=2).run()
        self.assertEqual(calls[:3], ["fall", "recover", "fall"])

    def test_menu_that_stays_stops_the_run(self):
        def step(test, out):
            if test["kind"] == "recover":
                jdump({"hud_before": False, "escapes": 3, "hud_after": False}, os.path.join(out, "obs.json"))
                return 0
            jdump({"stopped": "console not opened safely (3)"}, os.path.join(out, "obs.json"))
            return 3
        self.assertEqual(self.runner(step).run(), 3)
        self.assertEqual(jload(os.path.join(self.d, "state.json"))["status"], "stopped: menu or overlay")

    def test_no_escape_after_owner_input(self):
        calls = []

        def step(test, out):
            calls.append(test["kind"])
            self.ctl.foreign = True                       # the owner touched the PC during the step
            jdump({"stopped": "console not opened safely (3)"}, os.path.join(out, "obs.json"))
            return 3
        self.assertEqual(self.runner(step).run(), 3)
        self.assertNotIn("recover", calls)


class BreakerTests(unittest.TestCase):
    def test_a_kind_that_never_decides_is_switched_off(self):
        d = tempfile.mkdtemp()
        make_queue(d, n=12)
        calls = []
        r = tq.Runner(d, args(max_attempts=1), ctl=FakeControls(), step=lambda t, o: calls.append(t) or 0)
        r.session, r.cell, r._ps = True, "C", (lambda *a, **k: (0, ""))
        r.run()
        self.assertEqual(len(calls), tq.BREAKER)
        done = jload(os.path.join(d, "state.json"))["done"]
        self.assertEqual(sum(v["class"] == "BREAKER" for v in done.values()), 12 - tq.BREAKER)

    def test_an_open_breaker_never_rewrites_a_test_that_ran(self):
        # #220: with --max-attempts 2 the six first attempts open the breaker; each pending retry was then recorded as
        # a BREAKER row "not run", attempt 0, which replaced the real INCONCLUSIVE attempt as the test's last row
        d = tempfile.mkdtemp()
        make_queue(d, n=tq.BREAKER)
        r = tq.Runner(d, args(max_attempts=2), ctl=FakeControls(), step=lambda t, o: 0)   # never an obs.json
        r.session, r.cell, r._ps = True, "C", (lambda *a, **k: (0, ""))
        r.log = lambda msg: None
        r.run()
        st = jload(os.path.join(d, "state.json"))
        with open(os.path.join(d, "results.jsonl"), encoding="utf-8") as f:
            rows = [json.loads(x) for x in f if x.strip()]
        for t in st["done"]:
            last = [x for x in rows if x["id"] == t][-1]
            self.assertEqual(st["done"][t]["attempts"], st["attempts"][t], t)
            self.assertEqual(st["done"][t]["attempts"], last["attempt"], t)
            self.assertNotEqual(last["class"], "BREAKER", last)
            self.assertEqual((st["done"][t]["verdict"], st["done"][t]["class"]), (last["verdict"], last["class"]))

    def test_a_kind_with_a_verdict_keeps_running(self):
        d = tempfile.mkdtemp()
        make_queue(d, n=10)
        calls = []

        def step(t, o):
            calls.append(t)
            if len(calls) == 1:
                jdump({"end_read": "0 0 0.1", "shot": touch(o, "fall.png")}, os.path.join(o, "obs.json"))
            return 0
        r = tq.Runner(d, args(max_attempts=1), ctl=FakeControls(), step=step)
        r.session, r.cell, r._ps = True, "C", (lambda *a, **k: (0, ""))
        r.run()
        self.assertEqual(len(calls), 10)


class PopupTests(RunnerTests):
    def test_focus_lost_without_input_is_taken_back(self):
        refocused = []
        self.ctl.refocus_game = lambda: refocused.append(1) or setattr(self.ctl, "fg", "starfield.exe") or True
        r = self.runner(self.landing(0.1), refocus=True)
        r.ctl.last_sent_tick = 1
        self.ctl.fg = "steamwebhelper.exe"
        self.assertEqual(r.run(), 0)
        self.assertEqual(refocused, [1])

    def test_focus_lost_after_owner_input_is_not_taken_back(self):
        self.ctl.refocus_game = lambda: self.fail("must not refocus after owner input")
        r = self.runner(self.landing(0.1), refocus=True)
        r.ctl.last_sent_tick = 1
        self.ctl.fg, self.ctl.foreign = "chrome.exe", True
        self.assertEqual(r.run(), 3)


class ParseGetposTests(unittest.TestCase):
    def parse(self, text):
        import subprocess
        p = os.path.join(tempfile.mkdtemp(), "ocr.txt")
        writef(p, text, "w")
        return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "game", "parse_getpos.py"), p],
                              capture_output=True, text=True).stdout.strip()

    def test_ocr_quirks(self):
        self.assertEqual(self.parse("GetPos: X >> -10.07\nGetPos: Y >> 43.95\nGetPos: Z >> -10.95\n"),
                         "-10.07 43.95 -10.95")
        # seen 2026-10-11: ">>" dropped, "Po s" split, older lines above the latest reply
        self.assertEqual(self.parse("GetPos: z 1.00\nprid 0200BA55\nGet Po s: X > > 9.71\nGetPos: Y > > -66.58\n"
                                    "GetPos: z 7.95\n"), "9.71 -66.58 7.95")


class ControlTests(unittest.TestCase):
    def test_hours(self):
        ctl = FakeControls()
        h = __import__("time").localtime().tm_hour
        self.assertIsNone(tq.blocked_reason(ctl, {"hours": [[0, 24]]}))
        self.assertIn("hours", tq.blocked_reason(ctl, {"hours": [[(h + 1) % 24, (h + 1) % 24 + 1]]}))


if __name__ == "__main__":
    unittest.main()


class TerrainTests(unittest.TestCase):
    def test_terrain_judge(self):
        d = tempfile.mkdtemp()
        shot = touch(d, "spawn.png")
        t = {"kind": "terrain", "points": [{"label": "ground", "x": -60.0, "y": -60.0, "expect": 10.0},
                                           {"label": "padA", "x": 30.0, "y": 30.0, "expect": 35.0}]}
        ok = {"shot": shot, "points": [{"read": "-60.0 -60.0 10.1"}, {"read": "30.0 30.0 35.0"}]}
        self.assertEqual(tq.judge(t, ok, d)[0], "PASS")
        scaled = {"shot": shot, "points": [{"read": "-60.0 -60.0 80.0"}, {"read": "30.0 30.0 280.0"}]}
        self.assertEqual(tq.judge(t, scaled, d)[:2], ("FAIL", "HEIGHTS"))
        void = {"shot": shot, "points": [{"read": "-60.0 -60.0 -400.0"}, {"read": "30.0 30.0 -380.0"}]}
        self.assertEqual(tq.judge(t, void, d)[:2], ("FAIL", "NOTERRAIN"))
        self.assertEqual(tq.judge(t, {"shot": shot, "points": [{"read": None}, {"read": "30 30 35"}]}, d)[0],
                         "INCONCLUSIVE")
        self.assertEqual(tq.judge(t, dict(ok, shot=None), d)[0], "INCONCLUSIVE")

    def test_plan_terrain(self):
        d = tempfile.mkdtemp()
        writef(os.path.join(d, "FO4Port.esm"), b"TES4")
        exp = {b: {"ground": 10.0, "padA_x20-40_y20-40": h, "padB_x60-80_y20-40": 22.5, "pitC_x20-40_y60-80": 5.0}
               for b, h in (("FO4TX_World01.btd", 35.0), ("FO4TX_Shared02.btd", 45.0), ("FO4TX_World03.btd", 55.0))}
        jdump(exp, os.path.join(d, "expected.json"))
        out = os.path.join(d, "q")
        tq.main(["plan-terrain", "--staging", d, "--exp-dir", d, "--out", out])
        q = jload(os.path.join(out, "queue.json"))
        self.assertEqual([t["world_coc"] for t in q["tests"]], ["FO4TX_W01Spawn", "FO4TX_W02Spawn", "FO4TX_W03Spawn"])
        self.assertEqual([t["points"][1]["expect"] for t in q["tests"]], [35.0, 45.0, 55.0])
        self.assertTrue(all(t["cell"] == "" for t in q["tests"]))

    def test_plan_takes_routes_planned_again_from_another_folder(self):
        # a routes.py fix re-plans the routes of the SAME pinned build: the queue keeps the build's plugin hash and
        # staging, the stairs tests point at the new route files
        st, rd = tempfile.mkdtemp(), tempfile.mkdtemp()
        writef(os.path.join(st, "FO4Port.esm"), b"TES4")
        jdump({"cell": "CellA", "refs": []}, os.path.join(st, "CellA.json"))
        old = {"routes": [{"kind": "stairs", "ref": "000001:Fallout4.esm", "model": "Old.nif"}]}
        new = {"routes": [{"kind": "stairs", "ref": "000002:Fallout4.esm", "model": "New.nif", "lane": 0.75}],
               "stairs_checked": []}
        jdump(old, os.path.join(st, "routesfull_CellA.json"))
        jdump(new, os.path.join(rd, "routesfull_CellA.json"))
        out = os.path.join(st, "q_new")
        tq.main(["plan", "--staging", st, "--out", out, "--kinds", "stairs", "--routes-prefix", "routesfull_",
                 "--routes-dir", rd])
        q = jload(os.path.join(out, "queue.json"))
        self.assertEqual([t["ref"] for t in q["tests"]], ["000002:Fallout4.esm"])
        # the queue runs and judges its own copy (QA on PR #111: re-planning the routes folder must not change how an
        # existing queue is judged), and records the copy's hash
        own = os.path.join(os.path.abspath(out), "routes", "routesfull_CellA.json")
        self.assertEqual(q["tests"][0]["routes_file"], own)
        self.assertEqual(q["routes_sha256"], {"routesfull_CellA.json": tq.sha256(own)})
        jdump({"routes": [{"kind": "stairs", "ref": "000003:Fallout4.esm", "model": "Newer.nif"}]},
              os.path.join(rd, "routesfull_CellA.json"))
        self.assertEqual(jload(own)["routes"][0]["ref"], "000002:Fallout4.esm")
        self.assertEqual(q["routes_dir"], os.path.abspath(rd))
        self.assertEqual(q["staging"], os.path.abspath(st))
        out_old = os.path.join(st, "q_old")
        tq.main(["plan", "--staging", st, "--out", out_old, "--kinds", "stairs", "--routes-prefix", "routesfull_"])
        q_old = jload(os.path.join(out_old, "queue.json"))
        self.assertEqual([t["ref"] for t in q_old["tests"]], ["000001:Fallout4.esm"])
        self.assertNotIn("routes_dir", q_old)
        self.assertEqual(q_old["build_id"], q["build_id"])
        with self.assertRaises(SystemExit):                  # an empty routes folder is a mistake, not zero tests
            tq.main(["plan", "--staging", st, "--out", os.path.join(st, "q_bad"), "--routes-prefix", "routesfull_",
                     "--routes-dir", tempfile.mkdtemp()])

    def test_judge_reads_the_queue_copy_of_the_routes(self):
        # a route changed in the source folder after planning does not change the verdict of the planned queue
        st, rd = tempfile.mkdtemp(), tempfile.mkdtemp()
        writef(os.path.join(st, "FO4Port.esm"), b"TES4")
        jdump({"cell": "CellA", "refs": []}, os.path.join(st, "CellA.json"))
        route = {"kind": "stairs", "ref": "000002:Fallout4.esm", "model": "New.nif", "start": [0, 0, 0.3],
                 "heading": 0, "walk_ms": 900, "expect": {"low": [0, 1, 0], "high": [0, 4, 2.0], "min_rise": 1.6}}
        jdump({"routes": [route]}, os.path.join(rd, "routesfull_CellA.json"))
        out = os.path.join(st, "q")
        tq.main(["plan", "--staging", st, "--out", out, "--kinds", "stairs", "--routes-prefix", "routesfull_",
                 "--routes-dir", rd])
        t = jload(os.path.join(out, "queue.json"))["tests"][0]
        harder = dict(route, expect=dict(route["expect"], min_rise=5.0))
        jdump({"routes": [harder]}, os.path.join(rd, "routesfull_CellA.json"))
        shot = os.path.join(out, "r.png")
        writef(shot, b"png")
        obs = {"result": {"start_read": "0 0 0", "end_read": "0 4.2 2.0", "kind": "stairs"}, "shots": ["r.png"]}
        self.assertEqual(tq.judge(t, obs, out)[0], "PASS")

    def test_plan_puts_listed_references_first_or_keeps_only_them(self):
        tests = [{"kind": "stairs", "ref": f"{r}:Fallout4.esm"} for r in ("0EBECC", "0EBED6", "0EBEDE", "0EBED7")]
        tests.append({"kind": "door", "ref": "0EBED6:Fallout4.esm", "side": -1})
        got = tq.order_by_refs(tests, first="0ebede,0EBED6")
        self.assertEqual([(t["ref"][:6], t["kind"]) for t in got],
                         [("0EBEDE", "stairs"), ("0EBED6", "stairs"), ("0EBED6", "door"), ("0EBECC", "stairs"),
                          ("0EBED7", "stairs")])
        only = tq.order_by_refs(tests, refs="0EBED7,0EBECC")
        self.assertEqual([t["ref"][:6] for t in only], ["0EBED7", "0EBECC"])
        self.assertEqual(tq.order_by_refs(tests), tests)

    def test_qstep_has_the_terrain_step(self):
        src = readf(os.path.join(ROOT, "scripts", "game", "qstep.ps1"), encoding="utf-8")
        self.assertIn("'terrain' {", src)
        self.assertIn("'recover' {", src)


class ExpInstallTests(unittest.TestCase):
    def test_install_and_uninstall_leave_nothing_behind(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
        import exp_install
        root = tempfile.mkdtemp()
        game, exp, local = (os.path.join(root, x) for x in ("game", "exp", "local"))
        os.makedirs(os.path.join(game, "Data"))
        os.makedirs(os.path.join(exp, "Data", "Terrain"))
        os.makedirs(os.path.join(local, "Starfield"))
        writef(os.path.join(exp, "Exp.esm"), b"TES4")
        writef(os.path.join(exp, "Data", "Terrain", "W.btd"), b"BTDB")
        plugins = os.path.join(local, "Starfield", "Plugins.txt")
        original = b"\xef\xbb\xbf# comment\r\n*FO4Port.esm\r\n"
        writef(plugins, original)
        old = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = local
        try:
            exp_install.main(["install", "--exp-dir", exp, "--starfield", game])
            self.assertTrue(os.path.exists(os.path.join(game, "Data", "Terrain", "W.btd")))
            self.assertEqual(readf(plugins, "rb"), original + b"*Exp.esm\r\n")
            exp_install.main(["install", "--exp-dir", exp, "--starfield", game])   # same experiment again: no-op
            self.assertEqual(readf(plugins, "rb"), original + b"*Exp.esm\r\n")
            other = os.path.join(root, "other")
            os.makedirs(other)
            writef(os.path.join(other, "Other.esm"), b"TES4")
            with self.assertRaises(SystemExit):           # a different experiment refuses
                exp_install.main(["install", "--exp-dir", other, "--starfield", game])
            exp_install.main(["uninstall", "--starfield", game])
            self.assertEqual(readf(plugins, "rb"), original)
            self.assertEqual(sorted(os.listdir(os.path.join(game, "Data"))), [])
        finally:
            if old is None:
                os.environ.pop("LOCALAPPDATA")
            else:
                os.environ["LOCALAPPDATA"] = old

    def test_never_overwrites_game_files(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
        import exp_install
        root = tempfile.mkdtemp()
        game, exp = os.path.join(root, "game"), os.path.join(root, "exp")
        os.makedirs(os.path.join(game, "Data"))
        os.makedirs(exp)
        writef(os.path.join(exp, "Exp.esm"), b"new")
        writef(os.path.join(game, "Data", "Exp.esm"), b"theirs")
        with self.assertRaises(SystemExit):
            exp_install.main(["install", "--exp-dir", exp, "--starfield", game])
        self.assertEqual(readf(os.path.join(game, "Data", "Exp.esm"), "rb"), b"theirs")


class LaunchIdleTests(unittest.TestCase):
    def test_runner_input_does_not_count_as_owner_activity_for_a_relaunch(self):
        ctl = FakeControls()
        ctl.idle, ctl.last_sent_tick = 5, 123             # only the runner's own keys a moment ago
        self.assertIsNone(tq.blocked_reason(ctl, {"hours": [[0, 24]]}, launching=True, min_idle=900))
        ctl.foreign = True                                # the owner touched the PC after that
        self.assertIn("owner active", tq.blocked_reason(ctl, {"hours": [[0, 24]]}, launching=True, min_idle=900))
        ctl.foreign, ctl.last_sent_tick = False, None     # nothing known: needs real idle time
        self.assertIn("owner active", tq.blocked_reason(ctl, {"hours": [[0, 24]]}, launching=True, min_idle=900))


class PreLaunchTests(unittest.TestCase):
    def run_with(self, pre):
        d = tempfile.mkdtemp()
        make_queue(d, n=1)
        q = jload(os.path.join(d, "queue.json"))
        q["pre_launch"] = pre
        jdump(q, os.path.join(d, "queue.json"))
        ctl = FakeControls()
        ctl.pid = None                                    # no game yet: the runner has to launch
        launched = []
        r = tq.Runner(d, args(), ctl=ctl, step=lambda t, o: 0)
        r.pinned_ok = lambda: True
        r._ps = lambda script, *a, **k: launched.append(script) or (1, "launch refused in the test")
        r.run()
        return launched, readf(os.path.join(d, "run.log"))

    def test_pre_launch_runs_right_before_the_launch(self):
        launched, log = self.run_with([sys.executable, "-c", "print('installed')"])
        self.assertIn("pre-launch exit 0: installed", log)
        self.assertEqual(launched[:1], ["cycle.ps1"])

    def test_failed_pre_launch_stops_without_launching(self):
        launched, log = self.run_with([sys.executable, "-c", "import sys; sys.exit(3)"])
        self.assertEqual(launched, [])
        self.assertIn("pre-launch exit 3", log)


class PlanJsonTests(unittest.TestCase):
    def test_experiment_with_its_own_plan(self):
        d = tempfile.mkdtemp()
        writef(os.path.join(d, "FO4Port.esm"), b"TES4")
        plan = [{"coc": "FO4CW_RedRocketSpawn", "label": "Red Rocket patch", "drop_z": 140,
                 "points": [{"label": "v0", "x": -1000.0, "y": 300.0, "expect": 101.2}]}]
        jdump(plan, os.path.join(d, "plan.json"))
        out = os.path.join(d, "q")
        tq.main(["plan-terrain", "--staging", d, "--exp-dir", d, "--out", out])
        t = jload(os.path.join(out, "queue.json"))["tests"]
        self.assertEqual([x["world_coc"] for x in t], ["FO4CW_RedRocketSpawn"])
        self.assertEqual(t[0]["drop_z"], 140.0)
        self.assertEqual(t[0]["beyond"], {"x": -500.0, "y": 300.0})
        self.assertNotIn("rounds_sha256", jload(os.path.join(out, "queue.json")))
        rounds = json.dumps({"tests": [], "plan_sha256": hashlib.sha256(readb(os.path.join(d, "plan.json"))).hexdigest()})
        writef(os.path.join(d, "rounds.json"), rounds.encode())      # a door rounds stage: its digest is recorded
        out2 = os.path.join(d, "q2")
        tq.main(["plan-terrain", "--staging", d, "--exp-dir", d, "--out", out2])
        self.assertEqual(jload(os.path.join(out2, "queue.json"))["rounds_sha256"], hashlib.sha256(rounds.encode()).hexdigest())
        # Codex on #401: a plan.json edited after staging, or a rounds.json without plan_sha256, is refused
        for body, why in ((json.dumps({"tests": []}), "no plan_sha256"),
                          (json.dumps({"tests": [], "plan_sha256": "0" * 64}), "plan_sha256 differs")):
            writef(os.path.join(d, "rounds.json"), body.encode())
            with self.subTest(why=why), self.assertRaisesRegex(SystemExit, why):
                tq.main(["plan-terrain", "--staging", d, "--exp-dir", d, "--out", os.path.join(d, "q3")])
            self.assertFalse(os.path.exists(os.path.join(d, "q3")))
        os.remove(os.path.join(d, "rounds.json"))
        jdump([{"coc": "bad name; quit", "points": []}], os.path.join(d, "plan.json"))
        with self.assertRaises(SystemExit):               # typed into the console: letters, digits, _ only
            tq.main(["plan-terrain", "--staging", d, "--exp-dir", d, "--out", out])

    def test_terrain_points_are_validated(self):
        # #219: no points, a NaN / missing / non-numeric value are refused at planning, like the other planners
        d = tempfile.mkdtemp()
        writef(os.path.join(d, "FO4Port.esm"), b"TES4")
        out = os.path.join(d, "q")
        for points in ([], None, ["v0"], [{"label": "v0", "x": 0.0, "y": 0.0, "expect": float("nan")}],
                       [{"label": "v0", "x": 0.0, "y": 0.0}], [{"label": "v0", "x": 0.0, "y": 0.0, "expect": "high"}]):
            jdump([{"coc": "FO4CW_X", "points": points, "beyond": {"x": 0.0, "y": 0.0}}], os.path.join(d, "plan.json"))
            with self.assertRaises(SystemExit, msg=points), mock.patch("builtins.print"):
                tq.main(["plan-terrain", "--staging", d, "--exp-dir", d, "--out", out])
        jdump([{"coc": "FO4CW_X", "points": [{"label": "v0", "x": 0, "y": "2", "expect": "15"}]}],
              os.path.join(d, "plan.json"))
        with mock.patch("builtins.print"):
            tq.main(["plan-terrain", "--staging", d, "--exp-dir", d, "--out", out])
        self.assertEqual(jload(os.path.join(out, "queue.json"))["tests"][0]["points"],
                         [{"label": "v0", "x": 0.0, "y": 2.0, "expect": 15.0}])

    def test_plan_movable_pins_the_bridge_it_was_given(self):
        # #218: plan_movable built queue_extras' options without --bridge: no pin, no bridge_reads, no "bridge" need,
        # and a missing bridge folder was not refused
        d = tempfile.mkdtemp()
        writef(os.path.join(d, "FO4Port.esm"), b"TES4")
        br = os.path.join(d, "bridge")
        os.makedirs(os.path.join(br, "Data", "Scripts"))
        writef(os.path.join(br, "FO4SFBridge.esm"), b"plugin")
        writef(os.path.join(br, "Data", "Scripts", "FO4SF_Bridge.pex"), b"pex")
        jdump([{"label": "C_burntbook", "travel": "coc QASmoke", "base": "0200CE2A", "mass_kg": 25.0,
                "spot": [-3.0, 4.0, 0.0]}], os.path.join(d, "plan.json"))
        out = os.path.join(d, "q")
        with mock.patch("builtins.print"):
            tq.main(["plan-movable", "--staging", d, "--exp-dir", d, "--out", out, "--bridge", br])
        q = jload(os.path.join(out, "queue.json"))
        self.assertIn("bridge", q)
        self.assertTrue(q["tests"][0].get("bridge_reads"))
        self.assertIn("bridge", q.get("needs", []))
        with self.assertRaises(SystemExit), mock.patch("builtins.print"):
            tq.main(["plan-movable", "--staging", d, "--exp-dir", d, "--out", out, "--bridge", os.path.join(d, "no")])

    def test_the_terrain_judge_never_passes_a_test_without_usable_points(self):
        # #219: a queue planned before the check: no points judged PASS on a screenshot alone, a NaN expect passed a
        # read 400 m below, a string expect raised TypeError
        d = tempfile.mkdtemp()
        writef(os.path.join(d, "spawn.png"), b"x" * 2000)
        for points, reads in (([], []), ([{"label": "v0", "x": 0.0, "y": 0.0, "expect": float("nan")}], ["0 0 -400"]),
                              ([{"label": "v0", "x": 0.0, "y": 0.0, "expect": "15"}], ["0 0 15"])):
            test = {"id": "0000_terrain_X", "kind": "terrain", "points": points}
            obs = {"shot": "spawn.png", "points": [{"read": r} for r in reads]}
            self.assertEqual(tq.judge(test, obs, d)[:2], ("INCONCLUSIVE", "PLAN"), points)


class ExpPackTests(unittest.TestCase):
    def test_pack_installs_the_plugin_archive_instead_of_loose_files(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
        import exp_install
        root = tempfile.mkdtemp()
        game, exp, local = (os.path.join(root, x) for x in ("game", "exp", "local"))
        os.makedirs(os.path.join(game, "Data"))
        os.makedirs(os.path.join(exp, "Data", "Terrain"))
        os.makedirs(os.path.join(local, "Starfield"))
        writef(os.path.join(exp, "Exp.esm"), b"TES4")
        writef(os.path.join(exp, "Data", "Terrain", "W.btd"), b"BTDB")
        writef(os.path.join(local, "Starfield", "Plugins.txt"), b"*FO4Port.esm\r\n")

        def fake_ba2(a, data_root, out, folders=None, fmt="General"):
            from pathlib import Path
            if os.path.dirname(os.path.abspath(__file__)) not in sys.path:   # tests/ (discover adds it; -m unittest tests.x does not)
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from ba2_fixture import archive_from_tree
            writef(out, archive_from_tree(Path(data_root)))
            return out
        old_env, old_build = os.environ.get("LOCALAPPDATA"), exp_install.build_ba2
        os.environ["LOCALAPPDATA"], exp_install.build_ba2 = local, fake_ba2
        try:
            exp_install.main(["install", "--exp-dir", exp, "--starfield", game, "--pack"])
            self.assertEqual(sorted(os.listdir(os.path.join(game, "Data"))),
                             ["Exp - Main.ba2", "Exp.esm", exp_install.RECORD])
            exp_install.main(["uninstall", "--starfield", game])
            self.assertEqual(os.listdir(os.path.join(game, "Data")), [])
        finally:
            exp_install.build_ba2 = old_build
            if old_env is None:
                os.environ.pop("LOCALAPPDATA")
            else:
                os.environ["LOCALAPPDATA"] = old_env


class SpawnOffsetTests(unittest.TestCase):
    def test_points_are_judged_at_the_spawn_offset(self):
        d = tempfile.mkdtemp()
        shot = touch(d, "spawn.png")
        t = {"kind": "terrain", "points": [{"label": "padA", "x": 30.0, "y": 30.0, "expect": 35.0}]}
        obs = {"shot": shot, "offset": [3050.0, -3491.0], "points": [{"read": "3080.0 -3461.0 35.1"}]}
        self.assertEqual(tq.judge(t, obs, d)[0], "PASS")
        self.assertEqual(tq.judge(t, dict(obs, offset=None), d)[:2], ("INCONCLUSIVE", "MOVED"))


class AnchorOffsetTests(unittest.TestCase):
    def test_heights_are_judged_in_the_overlay_frame(self):
        d = tempfile.mkdtemp()
        shot = touch(d, "spawn.png")
        t = {"kind": "terrain", "points": [{"label": "padA", "x": 30.0, "y": 30.0, "expect": 35.0},
                                           {"label": "ground", "x": -60.0, "y": -60.0, "expect": 10.0}]}
        obs = {"shot": shot, "offset": [3000.0, -3500.0, -23.94], "offset_from": "anchor",
               "points": [{"read": "3030.0 -3470.0 11.06"}, {"read": "2940.0 -3560.0 -13.94"}]}
        v, cls, detail = tq.judge(t, obs, d)
        self.assertEqual(v, "PASS", detail)
        self.assertIn("from anchor", detail)
        flat = dict(obs, points=[{"read": "3030.0 -3470.0 -13.9"}, {"read": "2940.0 -3560.0 -13.94"}])
        self.assertEqual(tq.judge(t, flat, d)[:2], ("FAIL", "HEIGHTS"))


class NumericReadTests(unittest.TestCase):
    def test_offsets_only_from_numeric_reads(self):
        # 2026-10-11 World03: a failed spawn read "fail console 3" produced the offset (0, 0, -7)
        src = readf(os.path.join(ROOT, "scripts", "game", "qstep.ps1"), encoding="utf-8")
        self.assertEqual(src.count("-match '^\s*-?\d+"), 3)


class ZRefTests(unittest.TestCase):
    def test_height_offset_from_a_reference_probe(self):
        d = tempfile.mkdtemp()
        shot = touch(d, "spawn.png")
        t = {"kind": "terrain", "z_ref": "ground",
             "points": [{"label": "ground", "x": -60.0, "y": -60.0, "expect": 10.0},
                        {"label": "padA", "x": 30.0, "y": 30.0, "expect": 35.0}]}
        obs = {"shot": shot, "offset": [3000.0, -3500.0, -500.0], "offset_from": "spawn",   # spawn read mid-fall
               "points": [{"read": "2940.0 -3560.0 -13.94"}, {"read": "3030.0 -3470.0 11.06"}]}
        self.assertEqual(tq.judge(t, obs, d)[0], "PASS")
        flat = dict(obs, points=[{"read": "2940.0 -3560.0 -13.94"}, {"read": "3030.0 -3470.0 -13.94"}])
        self.assertEqual(tq.judge(t, flat, d)[:2], ("FAIL", "HEIGHTS"))


class StoredArchiveTests(unittest.TestCase):
    def test_experiment_archives_are_stored_uncompressed(self):
        from unittest.mock import patch
        import exp_install

        with tempfile.TemporaryDirectory() as root:
            game = os.path.join(root, "game")
            tool = os.path.join(game, "Tools", "Archive2", "Archive2.exe")
            os.makedirs(os.path.dirname(tool))
            with open(tool, "wb") as stream:
                stream.write(b"synthetic tool; never executed")
            data = os.path.join(root, "Data")
            os.makedirs(os.path.join(data, "Terrain"))
            with open(os.path.join(data, "Terrain", "World.btd"), "wb") as stream:
                stream.write(b"synthetic terrain")

            def pack(command, **kwargs):
                output = next(arg[len("-create="):] for arg in command if arg.startswith("-create="))
                with open(output, "wb") as stream:
                    stream.write(b"BTDX" + bytes(20))
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.object(exp_install.subprocess, "run", side_effect=pack) as process:
                exp_install.build_ba2(SimpleNamespace(starfield=game), data, os.path.join(root, "terrain.ba2"))
            command = process.call_args.args[0]
            self.assertIn("-compression=None", command)
            self.assertNotIn("-compression=Default", command)
            self.assertIn("-format=General", command)


class FreshTests(RunnerTests):
    def test_fresh_tests_relaunch_after_the_first(self):
        q = json.load(open(os.path.join(self.d, "queue.json")))
        for t in q["tests"]:
            t["fresh"] = True
        json.dump(q, open(os.path.join(self.d, "queue.json"), "w"))
        launches = []
        r = self.runner(self.landing(0.1))

        def ps(script, *a, **k):
            launches.append(script)
            self.ctl.pid = 42                             # cycle.ps1 started the game again
            return (0, "ok")
        r._ps = ps
        r.setup_session = lambda cell: setattr(r, "session", True)
        r.pinned_ok = lambda: True
        r.run()
        self.assertEqual(getattr(self.ctl, "closed", 0), 2)       # before tests 2 and 3
        self.assertEqual(launches.count("cycle.ps1"), 2)


class FreshBudgetTests(RunnerTests):
    def test_fresh_relaunches_do_not_use_up_the_crash_budget(self):
        # 2026-10-11 exp2c: three intended relaunches hit --max-relaunch 3 and the fourth test never ran
        make_queue(self.d, n=5)
        q = json.load(open(os.path.join(self.d, "queue.json")))
        for t in q["tests"]:
            t["fresh"] = True
        json.dump(q, open(os.path.join(self.d, "queue.json"), "w"))
        r = self.runner(self.landing(0.1), max_relaunch=1)

        def ps(script, *a, **k):
            self.ctl.pid = 42
            return (0, "ok")
        r._ps = ps
        r.setup_session = lambda cell: setattr(r, "session", True)
        r.pinned_ok = lambda: True
        self.assertEqual(r.run(), 0)
        st = json.load(open(os.path.join(self.d, "state.json")))
        self.assertEqual(len(st["done"]), 5)
        self.assertEqual(st["fresh_launches"], 4)


class BreakerBeforeFreshTests(RunnerTests):
    def test_an_open_breaker_skips_without_a_relaunch(self):
        # 2026-10-11 core64: with the terrain breaker open, every skipped "fresh" retry still closed and relaunched
        make_queue(self.d, n=tq.BREAKER + 3)
        q = json.load(open(os.path.join(self.d, "queue.json")))
        for t in q["tests"]:
            t["fresh"] = True
        json.dump(q, open(os.path.join(self.d, "queue.json"), "w"))
        r = tq.Runner(self.d, args(max_attempts=1), ctl=self.ctl, step=lambda t, o: 0)   # never an observation

        def ps(script, *a, **k):
            self.ctl.pid = 42
            return (0, "ok")
        r._ps = ps
        r.setup_session = lambda cell: setattr(r, "session", True)
        r.pinned_ok = lambda: True
        self.assertEqual(r.run(), 0)
        self.assertEqual(getattr(self.ctl, "closed", 0), tq.BREAKER - 1)   # only between the tests that ran
        done = json.load(open(os.path.join(self.d, "state.json")))["done"]
        self.assertEqual(sum(v["class"] == "BREAKER" for v in done.values()), 3)


class CompanionTests(unittest.TestCase):
    def test_the_companion_is_disabled_after_god_mode(self):
        # 2026-10-12: the save's companion stood in front of FortHagen01's load door (NOPROMPT) and in every NPC shot
        d = tempfile.mkdtemp()
        make_queue(d, n=1)
        kinds = []
        r = tq.Runner(d, args(), ctl=FakeControls(), step=lambda t, o: kinds.append((t["kind"], t.get("ref"))) or 0)
        r.setup_session("C")
        self.assertEqual([k for k, _ in kinds][-2:], ["godmode", "companion_off"])
        self.assertEqual(kinds[-1][1], tq.COMPANION_REF)
        src = open(os.path.join(ROOT, "scripts", "game", "qstep.ps1"), encoding="utf-8").read()
        self.assertIn("'companion_off' {", src)
        self.assertIn("-notmatch '^[0-9A-Fa-f]{8}$'", src)

    def test_a_queue_can_keep_the_companion(self):
        d = tempfile.mkdtemp()
        make_queue(d, n=1)
        q = json.load(open(os.path.join(d, "queue.json")))
        q["companion"] = "keep"
        json.dump(q, open(os.path.join(d, "queue.json"), "w"))
        kinds = []
        r = tq.Runner(d, args(), ctl=FakeControls(), step=lambda t, o: kinds.append(t["kind"]) or 0)
        r.setup_session("C")
        self.assertNotIn("companion_off", kinds)


class Exp3RecoveryTests(unittest.TestCase):
    def test_hang_reread_and_tab_recovery_present(self):
        src = open(os.path.join(ROOT, "scripts", "game", "qstep.ps1"), encoding="utf-8").read()
        self.assertIn("[Math]::Abs([double]$Matches[1] - $dropz) -lt 0.05", src)
        self.assertIn("Send 'key:tab|wait:2000'", src)


class HopTests(unittest.TestCase):
    def test_hop_options_reach_the_step(self):
        d = tempfile.mkdtemp()
        open(os.path.join(d, "FO4Port.esm"), "wb").write(b"TES4")
        plan = [{"coc": "FO4Core_RedRocketSpawn", "drop_z": 245, "hop_m": 300, "hop_wait_ms": 7000,
                 "points": [{"label": "a", "x": 0.0, "y": 0.0, "expect": 1.0}]}]
        json.dump(plan, open(os.path.join(d, "plan.json"), "w"))
        out = os.path.join(d, "q")
        tq.main(["plan-terrain", "--staging", d, "--exp-dir", d, "--out", out])
        t = json.load(open(os.path.join(out, "queue.json")))["tests"][0]
        self.assertEqual((t["hop_m"], t["hop_wait_ms"]), (300, 7000))
        src = open(os.path.join(ROOT, "scripts", "game", "qstep.ps1"), encoding="utf-8").read()
        self.assertIn("if ($t.hop_m)", src)


class WatchdogTests(unittest.TestCase):
    def test_watchdog_rules(self):
        src = open(os.path.join(ROOT, "scripts", "game", "watchdog.ps1"), encoding="utf-8").read()
        self.assertIn("threshold_hours = 3.0", src)                  # default inactivity before it acts
        self.assertIn("if (Stopped)", src)                           # STOP files win
        self.assertIn("-not $running -and (QueueLeft) -gt 0", src)   # never a second chain, never an empty one
        self.assertIn("--grep '^Claude'", src)                       # Claude's commits count as activity
        self.assertIn("-s workspace-write", src)                     # Codex runs sandboxed
        self.assertNotIn("dangerously", src)
        runbook = open(os.path.join(ROOT, "docs", "ai", "codex-runbook.md"), encoding="utf-8").read()
        self.assertIn("No input to Starfield", runbook)


class BridgeQueueTests(unittest.TestCase):
    """plan-* --bridge: the queue pins the staged bridge's hashes and every test is marked for bridge reads."""
    def test_apply_bridge_marks_tests_and_pins_hashes(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "Data", "Scripts"))
            writef(os.path.join(d, "FO4SFBridge.esm"), b"plugin")
            writef(os.path.join(d, "Data", "Scripts", "FO4SF_Bridge.pex"), b"pex")
            tests = [{"kind": "walk"}, {"kind": "door_trip"}]
            extra = tq.apply_bridge(tests, SimpleNamespace(bridge=d))
            self.assertTrue(all(t["bridge_reads"] for t in tests))
            self.assertEqual(extra["bridge"]["plugin"], "FO4SFBridge.esm")
            self.assertEqual(sorted(extra["bridge"]["sha256"]), ["Data\Scripts\FO4SF_Bridge.pex", "FO4SFBridge.esm"]
                             if os.sep == "\\" else ["Data/Scripts/FO4SF_Bridge.pex", "FO4SFBridge.esm"])
            self.assertIn("bridge", tq.runner_features.needs(tests))
            self.assertIsNone(tq.bridge_mismatch(extra["bridge"]))
            writef(os.path.join(d, "Data", "Scripts", "FO4SF_Bridge.pex"), b"pex-v2")
            self.assertIn("changed", tq.bridge_mismatch(extra["bridge"]))
            os.remove(os.path.join(d, "FO4SFBridge.esm"))
            self.assertIn("missing", tq.bridge_mismatch(extra["bridge"]))

    def test_without_bridge_nothing_is_marked(self):
        tests = [{"kind": "walk"}]
        self.assertEqual(tq.apply_bridge(tests, SimpleNamespace(bridge="")), {})
        self.assertNotIn("bridge_reads", tests[0])
        self.assertNotIn("bridge", tq.runner_features.needs(tests))

    def test_a_missing_staged_file_stops_the_plan(self):
        with tempfile.TemporaryDirectory() as d:
            writef(os.path.join(d, "FO4SFBridge.esm"), b"plugin")
            with self.assertRaises(SystemExit):
                tq.apply_bridge([{"kind": "walk"}], SimpleNamespace(bridge=d))
