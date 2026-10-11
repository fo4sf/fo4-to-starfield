"""npc_nav test kind: testqueue.py plan-npc / judge / control gate / report, qstep.ps1's step, parse_npc.py.
Synthetic data only: no game, no Windows calls, no PowerShell run."""
import json
import os
import re
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import parse_npc  # noqa: E402
import testqueue as tq  # noqa: E402

QSTEP = os.path.join(ROOT, "scripts", "game", "qstep.ps1")
N0 = {"label": "N0_ptr", "travel": "coc QASmoke", "npc": "0000CF96", "a": [-8, -4, 0], "b": [5, 10, 0],
      "method": "ptr_player", "reads_s": [0, 3, 8, 15, 30], "control": True, "expect": "PASS"}


def touch(d, name):
    open(os.path.join(d, name), "wb").close()
    return name


def walk_obs(d, t, reads, **kw):
    """Observations as qstep.ps1 writes them: spawn at A (+0.8 m), player at B, one confirmed read per sample."""
    off = list(kw.pop("offset", None) or [0.0, 0.0, 0.0])
    a = [t["a"][k] + off[k] for k in range(3)]
    b = [t["b"][k] + off[k] for k in range(3)]
    p0 = f"{a[0] + 0.8} {a[1]} {a[2]}"
    times = [x for x in t["reads_s"] if x > 0]
    o = {"spawn": {"isid": 1, "self": "FF000800", "read": p0}, "t0": {"isid": 1, "read": p0, "via": "prid"},
         "command_sent": True, "player_b": f"{b[0]} {b[1]} {b[2]}",
         "samples": [{"t_game": s, "isid": 1, "read": r, "shot": touch(d, f"npc{k}.png")}
                     for k, (s, r) in enumerate(zip(times, reads))]}
    if any(off):
        o["offset"], o["offset_from"] = off, "anchor"
    o.update(kw)
    return o


def towards(t, fractions, off=(0.0, 0.0, 0.0)):
    """Reads at these fractions of the way from the spawn to B."""
    ax, ay, az = t["a"][0] + 0.8 + off[0], t["a"][1] + off[1], t["a"][2] + off[2]
    bx, by = t["b"][0] + off[0], t["b"][1] + off[1]
    return [f"{ax + (bx - ax) * f:.2f} {ay + (by - ay) * f:.2f} {az:.2f}" for f in fractions]


class NpcJudgeTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.t = tq.npc_test(0, N0)

    def judge(self, obs, t=None):
        return tq.judge(t or self.t, obs, self.d)

    def test_arrived_or_walked_towards_b_is_a_pass(self):
        v, cls, detail = self.judge(walk_obs(self.d, self.t, towards(self.t, [0.2, 0.5, 0.9, 0.95])))
        self.assertEqual((v, cls), ("PASS", "PASS"), detail)
        self.assertIn("arrived", detail)
        self.assertIn("[expected PASS]", detail)
        v, cls, detail = self.judge(walk_obs(self.d, self.t, towards(self.t, [0.1, 0.2, 0.3, 0.4])))
        self.assertEqual(v, "PASS", detail)                # 0.4 x 18.6 m = 7.4 m towards B >= 5 m
        self.assertIn("towards B", detail)

    def test_never_moved_is_nonav(self):
        v, cls, detail = self.judge(walk_obs(self.d, self.t, towards(self.t, [0, 0, 0, 0])))
        self.assertEqual((v, cls), ("FAIL", "NONAV"), detail)
        self.assertIn("4/4 reads", detail)

    def test_moved_without_reaching_b_is_stalled(self):
        side = ["-6.2 -5.0 0.0", "-5.2 -6.0 0.0", "-6.2 -6.5 0.0", "-6.2 -6.5 0.0"]      # wandered, not towards B
        self.assertEqual(self.judge(walk_obs(self.d, self.t, side))[:2], ("FAIL", "STALLED"))

    def test_falling_through_is_a_world_problem(self):
        fell = towards(self.t, [0.1, 0.2]) + ["-6.0 -3.0 -60.0", "-6.0 -3.0 -400.0"]
        self.assertEqual(self.judge(walk_obs(self.d, self.t, fell))[:2], ("FAIL", "FELL"))

    def test_spawn_must_be_confirmed_and_at_a(self):
        ok = walk_obs(self.d, self.t, towards(self.t, [0.2, 0.5, 0.9, 0.95]))
        for isid in (0, None):
            self.assertEqual(self.judge(dict(ok, spawn=dict(ok["spawn"], isid=isid)))[:2], ("INCONCLUSIVE", "SPAWN"))
        far = dict(ok, spawn=dict(ok["spawn"], read="4.0 9.0 0.0"), t0={"isid": 1, "read": "4.0 9.0 0.0"})
        self.assertEqual(self.judge(far)[:2], ("INCONCLUSIVE", "SPAWN"))
        self.assertEqual(self.judge(None)[0], "INCONCLUSIVE")
        self.assertEqual(self.judge({"stopped": "input guard"})[:2], ("INCONCLUSIVE", "STOPPED"))

    def test_lost_handle_or_target_is_inconclusive(self):
        ok = walk_obs(self.d, self.t, towards(self.t, [0, 0, 0, 0]))
        self.assertEqual(self.judge(dict(ok, command_sent=False))[:2], ("INCONCLUSIVE", "HANDLE"))
        self.assertEqual(self.judge(dict(ok, player_b=None))[:2], ("INCONCLUSIVE", "TARGET"))
        self.assertEqual(self.judge(dict(ok, player_b="fail console 3"))[:2], ("INCONCLUSIVE", "TARGET"))
        self.assertEqual(self.judge(dict(ok, t0=None, spawn=dict(ok["spawn"], read=None)))[:2],
                         ("INCONCLUSIVE", "UNREAD"))

    def test_only_confirmed_reads_with_a_screenshot_count(self):
        still = walk_obs(self.d, self.t, towards(self.t, [0, 0, 0, 0]))
        unconfirmed = [dict(s) for s in still["samples"]]
        unconfirmed[-1]["isid"] = None                       # the last read could not confirm the selection
        self.assertEqual(self.judge(dict(still, samples=unconfirmed))[:2], ("INCONCLUSIVE", "UNREAD"))
        noshot = [dict(s) for s in still["samples"]]
        noshot[-1]["shot"] = "missing.png"
        self.assertEqual(self.judge(dict(still, samples=noshot))[:2], ("INCONCLUSIVE", "UNREAD"))
        self.assertEqual(self.judge(dict(still, samples=[]))[:2], ("INCONCLUSIVE", "UNREAD"))
        # a walk that is already observed passes even if a later read is missing
        early = walk_obs(self.d, self.t, towards(self.t, [0.5, 0.95]))
        self.assertEqual(self.judge(early)[0], "PASS")

    def test_positions_are_judged_in_the_worldspace_frame(self):
        t = tq.npc_test(0, dict(N0, control=False, expect="FAIL NONAV", a=[-987.4, 1128.2, 105.0],
                                b=[-976.5, 1144.7, 105.0], anchor={"ref": "02000800", "local": [-989.0, 1147.2, 105.1]}))
        off = (3000.0, -3500.0, -20.0)
        obs = walk_obs(self.d, t, towards(t, [0.3, 0.6, 0.9, 0.95], off), offset=list(off))
        self.assertEqual(self.judge(obs, t)[0], "PASS")
        self.assertEqual(self.judge(dict(obs, offset=None), t)[:2], ("INCONCLUSIVE", "ANCHOR"))
        still = walk_obs(self.d, t, towards(t, [0, 0, 0, 0], off), offset=list(off))
        v, cls, detail = self.judge(still, t)
        self.assertEqual((v, cls), ("FAIL", "NONAV"), detail)
        self.assertIn("[expected FAIL NONAV]", detail)


class NpcPlanTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        open(os.path.join(self.d, "FO4Port.esm"), "wb").write(b"TES4")

    def plan(self, tests, *extra):
        exp = tempfile.mkdtemp()
        json.dump(tests, open(os.path.join(exp, "plan.json"), "w"))
        out = os.path.join(self.d, "q")
        tq.main(["plan-npc", "--staging", self.d, "--exp-dir", exp, "--out", out, *extra])
        return json.load(open(os.path.join(out, "queue.json")))

    def test_n0_and_n1_plans(self):
        n1 = dict(N0, label="N1 ptr", control=False, expect="FAIL NONAV", travel="coc FO4CW_RedRocketSpawn",
                  a=[-987.4286, 1128.2286, 105.0286], b=[-976.4571, 1144.6857, 105.0286], drop=30, settle_ms=7000,
                  anchor={"ref": "02000800", "local": [-989.0286, 1147.2, 105.1434]},
                  spawn_local=[-989.0286, 1147.2, 105.1434], basis="hypothesis: no NAVM in the plugin world")
        q = self.plan([n1, N0], "--plugins", "FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm",
                      "--install-exp", os.path.join(self.d, "exp2b"), "--control-queue", os.path.join(self.d, "n0q"))
        t0, t1 = q["tests"]
        self.assertTrue(t0["control"] and not t1["control"])      # controls run first
        self.assertEqual([t0["id"], t1["id"]], ["0000_npc_nav_N0_ptr", "0001_npc_nav_N1_ptr"])
        self.assertEqual((t0["kind"], t0["cell"], t0["npc"], t0["method"]), ("npc_nav", "", "0000CF96", "ptr_player"))
        self.assertEqual(t0["reads_s"], [0.0, 3.0, 8.0, 15.0, 30.0])
        self.assertEqual((t0["radius"], t0["min_progress"], t0["nomove"]), (2.5, 5.0, 0.5))
        self.assertAlmostEqual(t0["heading_a"], 42.9, places=1)   # from A towards B: north-east
        self.assertAlmostEqual(t0["heading_b"], 222.9, places=1)
        self.assertEqual(t1["anchor"], {"ref": "02000800", "local": [-989.0286, 1147.2, 105.1434]})
        self.assertEqual((t1["drop"], t1["settle_ms"], t1["expect"]), (30.0, 7000, "FAIL NONAV"))
        self.assertEqual(q["control_queue"], os.path.join(self.d, "n0q"))
        pre = q["pre_launch"]
        self.assertEqual(pre[pre.index("--exp-dir") + 1], os.path.join(self.d, "exp2b"))
        self.assertIn("--pack", pre)
        self.assertEqual(q["launch_cell"], "Vault111Cryo")
        self.assertNotIn("pre_launch", self.plan([N0]))           # vanilla control: nothing to install

    def test_everything_typed_into_the_console_is_validated(self):
        bad = [{"travel": "coc QA Smoke"}, {"travel": "cow QASmoke 0 0"}, {"travel": "coc QASmoke|key:esc"},
               {"travel": ""}, {"npc": "0000CF9"}, {"npc": "0000CF96; tgm"}, {"npc": "player"},
               {"method": "moveto"}, {"method": "PathToRef player"}, {"pre": ["tgm"]}, {"pre": ["gnm; qqq"]},
               {"anchor": {"ref": "player", "local": [0, 0, 0]}}, {"anchor": {"ref": "02000800", "local": [0, 0]}},
               {"anchor": "02000800"}, {"a": [0, "x", 0]}, {"a": [0, 0]}, {"b": [float("nan"), 0, 0]},
               {"b": [1e9, 0, 0]}, {"reads_s": [0]}, {"reads_s": [0, 500]}, {"reads_s": "30"}, {"radius": -1},
               {"settle_ms": 10 ** 6}, {"spawn_local": [0, 0, 0, 0]}]
        for b in bad:
            with self.assertRaises(SystemExit, msg=str(b)):
                self.plan([dict(N0, **b)])
        with self.assertRaises(SystemExit):
            self.plan([])
        with self.assertRaises(SystemExit):
            self.plan(["coc QASmoke"])

    def test_qstep_types_only_the_planned_method_lines(self):
        # testqueue.NPC_METHODS and qstep.ps1's table must agree: every planned console line is in the step as written
        src = open(QSTEP, encoding="utf-8").read()
        for method, lines in tq.NPC_METHODS.items():
            self.assertIn(f"'{method}' = @(", src)
            for line in lines:
                self.assertIn(f"'{line}'", src, line)
        self.assertIn("@('gnm') -cnotcontains", src)


class NpcStepScriptTests(unittest.TestCase):
    def test_qstep_has_the_npc_step(self):
        src = open(QSTEP, encoding="utf-8").read()
        block = src[src.index("'npc_nav' {"):src.index("'recover' {")]
        for need in ("ClearConsole", "player.placeatme $npc 1", "'plr'", "GetIsID $npc", "'GetSelf'", "prid",
                     "'disable', 'GetDisabled'", "type:markfordelete", "Select-Npc", "$obs['samples']", "Save-Obs"):
            self.assertIn(need, block, need)
        # typed values are checked before anything is typed
        for check in ("'^coc [A-Za-z0-9_]+$'", "$npc -notmatch $hex8", "$methods.ContainsKey", "\"bad anchor\""):
            self.assertIn(check, block, check)
        # the walk command and the removal are only typed after a confirmed selection
        self.assertLess(block.index("$sel = Select-Npc"), block.index("$cmds += $methods"))
        self.assertLess(block.rindex("$sel = Select-Npc"), block.index("'disable', 'GetDisabled'"))
        # no position offset from a failed read ("fail console 3"): the numeric pattern, as the terrain step
        self.assertIn("$num3 = '^\\s*-?\\d+(\\.\\d+)?\\s+", block)

    def test_step_timeout_grows_with_reads(self):
        t = tq.npc_test(0, N0)
        self.assertGreater(tq.step_timeout(t), tq.step_timeout(dict(t, reads_s=[0, 5])))
        self.assertGreaterEqual(tq.step_timeout(t), 480 + 30)
        self.assertEqual(tq.step_timeout({"kind": "fall"}), 300)
        self.assertEqual(tq.step_timeout({"kind": "terrain", "points": [{}, {}]}), 150 + 90 * 3)


class ParseNpcTests(unittest.TestCase):
    P = staticmethod(parse_npc.parse)

    def test_condition_replies_and_echoes(self):
        self.assertEqual(self.P("GetIsID 0000CF96\nGetIsID >> 1.00\n")["isid"], 1)
        self.assertEqual(self.P("GetIsID 0000CF96\nGetIsID: 0.00\n")["isid"], 0)
        self.assertEqual(self.P("Get Is ID 0000CF96\nGetlsID > > 1.00\n")["isid"], 1)     # OCR splits and l for I
        self.assertEqual(self.P("GetIsID 0000CF96\nGetIsID 1 00\n")["isid"], 1)          # '>>' and '.' dropped
        self.assertIsNone(self.P("GetIsID 0000CF96\nMissing reference\n")["isid"])       # the echo is no reply
        self.assertIsNone(self.P("GetIsID 1001F3E8\n")["isid"])
        self.assertIsNone(self.P("GetIsID >> 1.00\n")["isid"])                           # no echo: not attributable

    def test_a_reply_before_the_last_echo_is_stale(self):
        # ClearConsole did not clear: the previous session's lines are still on screen above this session's
        stale = ("GetIsID 0000CF96\nGetIsID >> 1.00\ngetpos x\nGetPos: X >> 1.00\ngetpos y\nGetPos: Y >> 2.00\n"
                 "getpos z\nGetPos: Z >> 3.00\nGetIsID 0000CF96\nMissing reference\ngetpos x\nMissing reference\n")
        r = self.P(stale)
        self.assertIsNone(r["isid"])
        self.assertIsNone(r["pos"])

    def test_positions_need_the_confirming_echo(self):
        text = ("GetIsID 0000CF96\nGetIsID >> 1.00\ngetpos x\nGetPos: X >> -7.20\ngetpos y\nGetPos: Y >> -4.00\n"
                "getpos z\nGetPos: Z >> 0.50\n")
        self.assertEqual(self.P(text)["pos"], "-7.20 -4.00 0.50")
        self.assertIsNone(self.P(text.split("\n", 2)[2])["pos"])                         # no GetIsID echo

    def test_getself_formats(self):
        for reply in ("GetSelf >> FF000800", "GetSelf >> (FF000800)", "GetSelf: 0xff000800", "GetSelf >> 4278192128.00",
                      "FF000800", "GetSelf >> FFOOO800"):
            self.assertEqual(self.P(f"GetSelf\n{reply}\n")["self"], "FF000800", reply)
        self.assertIsNone(self.P("GetSelf\nGetSelf >> 0000CF96\n")["self"])             # not a runtime ref
        self.assertIsNone(self.P("GetSelf\n")["self"])                                   # echo, no reply
        self.assertIsNone(self.P("GetSelf >> FF000801\nGetSelf\nScript command not found\n")["self"])   # stale

    def test_disabled(self):
        self.assertEqual(self.P("disable\nGetDisabled\nGetDisabled >> 1.00\n")["disabled"], 1)
        self.assertIsNone(self.P("GetDisabled >> 1.00\n")["disabled"])


class FakeControls:
    def __init__(self):
        self.last_sent_tick = None

    def stop_file(self):
        return None

    def guardian_mode(self):
        return "running"

    def idle_s(self):
        return 10 ** 6

    def foreign_input(self):
        return False

    def mark_sent(self):
        pass

    def game_in_front(self):
        return True

    def game_pid(self):
        return 42

    def owned_pid(self):
        return 42

    def refocus_game(self):
        return True


def run_args(**kw):
    base = dict(max_tests=10 ** 6, max_hours=1.0, min_idle=900, max_attempts=2, max_relaunch=3, wait_for_idle=False,
                refocus=False, dry_run=False, starfield="")
    base.update(kw)
    return SimpleNamespace(**base)


class ControlGateTests(unittest.TestCase):
    def queue(self, d, tests, **extra):
        q = {"build_id": "abcd1234", "commit": "0" * 40, "staging": d, "plugin_sha256": "x", "save": "s",
             "plugin_index": "02", "hours": [[0, 24]], "tests": tests}
        q.update(extra)
        json.dump(q, open(os.path.join(d, "queue.json"), "w"))

    def run_queue(self, d, outcome):
        """outcome: test id -> 'walk' | 'still'; returns {id: number of step calls}."""
        calls = {}

        def step(t, out):
            calls[t["id"]] = calls.get(t["id"], 0) + 1
            fr = [0.2, 0.5, 0.9, 0.95] if outcome[t["id"]] == "walk" else [0, 0, 0, 0]
            json.dump(walk_obs(out, t, towards(t, fr)), open(os.path.join(out, "obs.json"), "w"))
            return 0
        r = tq.Runner(d, run_args(), ctl=FakeControls(), step=step)
        r.session, r._ps = True, (lambda *a, **k: (0, ""))
        r.run()
        return calls

    def make_tests(self):
        n0 = tq.npc_test(0, N0)
        n1 = tq.npc_test(1, dict(N0, label="N1", control=False, expect="FAIL NONAV"))
        return n0, n1

    def test_a_fail_counts_only_after_the_control_passed(self):
        d = tempfile.mkdtemp()
        n0, n1 = self.make_tests()
        self.queue(d, [n0, n1])
        self.run_queue(d, {n0["id"]: "walk", n1["id"]: "still"})
        done = json.load(open(os.path.join(d, "state.json")))["done"]
        self.assertEqual((done[n1["id"]]["verdict"], done[n1["id"]]["class"]), ("FAIL", "NONAV"))
        rep = json.load(open(os.path.join(d, "report.json")))
        exp = {e["id"]: e for e in rep["expectations"]}
        self.assertEqual(exp[n1["id"]]["result"], "FAIL NONAV")
        self.assertIn("| yes |", open(os.path.join(d, "report.md")).read())

    def test_failed_control_makes_the_others_inconclusive_and_final(self):
        d = tempfile.mkdtemp()
        n0, n1 = self.make_tests()
        self.queue(d, [n0, n1])
        calls = self.run_queue(d, {n0["id"]: "still", n1["id"]: "still"})
        done = json.load(open(os.path.join(d, "state.json")))["done"]
        self.assertEqual(done[n0["id"]]["class"], "NONAV")             # the control itself is judged as it is
        self.assertEqual((done[n1["id"]]["verdict"], done[n1["id"]]["class"]), ("INCONCLUSIVE", "CONTROL"))
        self.assertEqual(calls[n1["id"]], 1)                            # not retried: a retry cannot change it
        line = [json.loads(x) for x in open(os.path.join(d, "results.jsonl"))][-1]
        self.assertIn("raw verdict FAIL NONAV", line["detail"])
        self.assertEqual(line["expect"], "FAIL NONAV")

    def test_control_from_another_queue(self):
        n0, n1 = self.make_tests()
        ctrl = tempfile.mkdtemp()
        self.queue(ctrl, [n0])
        for state, want in ((None, "CONTROL"), ("FAIL", "CONTROL"), ("PASS", "NONAV")):
            d = tempfile.mkdtemp()
            self.queue(d, [n1], control_queue=ctrl)
            if state:
                json.dump({"done": {n0["id"]: {"verdict": state, "class": "X", "attempts": 1}}},
                          open(os.path.join(ctrl, "state.json"), "w"))
            self.run_queue(d, {n1["id"]: "still"})
            done = json.load(open(os.path.join(d, "state.json")))["done"]
            self.assertEqual(done[n1["id"]]["class"], want, state)

    def test_pass_and_unconfigured_queues_are_not_gated(self):
        n0, n1 = self.make_tests()
        q = {"tests": [n1]}
        self.assertEqual(tq.control_gate(tempfile.mkdtemp(), q, n1, "FAIL", "NONAV", "x"), ("FAIL", "NONAV", "x"))
        q = {"tests": [n0, n1]}
        self.assertEqual(tq.control_gate(tempfile.mkdtemp(), q, n1, "PASS", "PASS", "x"), ("PASS", "PASS", "x"))
        other = dict(n1, method="follow_player")                       # the control has to match the method
        d = tempfile.mkdtemp()
        json.dump({"done": {n0["id"]: {"verdict": "PASS", "class": "PASS", "attempts": 1}}},
                  open(os.path.join(d, "state.json"), "w"))
        json.dump(q, open(os.path.join(d, "queue.json"), "w"))
        self.assertEqual(tq.control_gate(d, q, other, "FAIL", "NONAV", "x")[1], "CONTROL")
        self.assertEqual(tq.control_gate(d, q, n1, "FAIL", "NONAV", "x")[1], "NONAV")


if __name__ == "__main__":
    unittest.main()
