"""npc_nav test kind: testqueue.py plan-npc / judge / control gate / precondition / report, qstep.ps1's step,
parse_npc.py. Synthetic data only: no game, no Windows calls, no PowerShell run (see test_qstep_sandbox.py for that)."""
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
SELECT = ["isid", "x", "y", "z"]                     # what qstep's Select-Npc session expects: GetIsID, getpos x/y/z


def touch(d, name):
    open(os.path.join(d, name), "wb").close()
    return name


def jdump(obj, p):
    with open(p, "w") as f:
        json.dump(obj, f)


def jload(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def text(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def npc_block():
    src = text(QSTEP)
    return src[src.index("'npc_nav' {"):src.index("'recover' {")]


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

    def test_a_warp_is_not_a_walk(self):
        # at B by the first read (3 s): no position on the way, a warp to the player is not ruled out
        v, cls, detail = self.judge(walk_obs(self.d, self.t, towards(self.t, [0.95, 0.95, 0.95, 0.95])))
        self.assertEqual((v, cls), ("INCONCLUSIVE", "EARLY"), detail)
        # a jump faster than max_speed (8 m/s, +2 s slack) between two reads: 100 m from 8 s to 15 s
        jump = towards(self.t, [0.05, 0.1]) + ["92.0 -4.0 0.0", "92.0 -4.0 0.0"]
        v, cls, detail = self.judge(walk_obs(self.d, self.t, jump))
        self.assertEqual((v, cls), ("INCONCLUSIVE", "WARP"), detail)
        fast = tq.npc_test(0, dict(N0, max_speed=20))
        self.assertEqual(self.judge(walk_obs(self.d, fast, jump), fast)[:2], ("FAIL", "STALLED"))

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
        # samples cut by the step budget: a FAIL needs every planned read
        self.assertEqual(self.judge(dict(still, samples=still["samples"][:2], samples_cut="step budget"))[:2],
                         ("INCONCLUSIVE", "UNREAD"))
        # a walk that is already observed passes even if a later read is missing
        early = walk_obs(self.d, self.t, towards(self.t, [0.3, 0.6]))
        self.assertEqual(self.judge(early)[0], "PASS")

    def test_positions_are_judged_in_the_worldspace_frame(self):
        t = tq.npc_test(0, dict(N0, control=False, expect="FAIL NONAV", a=[-987.4, 1128.2, 105.0],
                                b=[-976.5, 1144.7, 105.0], anchor={"ref": "02000800", "local": [-989.0, 1147.2, 105.1]}))
        off = (3000.0, -3500.0, -20.0)
        obs = walk_obs(self.d, t, towards(t, [0.3, 0.6, 0.9, 0.95], off), offset=list(off))
        self.assertEqual(self.judge(obs, t)[0], "PASS")
        self.assertEqual(self.judge(dict(obs, offset=None), t)[:2], ("INCONCLUSIVE", "ANCHOR"))
        v, cls, detail = self.judge({"offset_missing": "the arrival was still moving"}, t)
        self.assertEqual((v, cls), ("INCONCLUSIVE", "ANCHOR"))
        self.assertIn("still moving", detail)
        still = walk_obs(self.d, t, towards(t, [0, 0, 0, 0], off), offset=list(off))
        v, cls, detail = self.judge(still, t)
        self.assertEqual((v, cls), ("FAIL", "NONAV"), detail)
        self.assertIn("[expected FAIL NONAV]", detail)

    def test_baseline_passes_when_the_actor_stays_away(self):
        base = tq.npc_test(0, dict(N0, label="N0_base", method="none", control=False, expect="PASS"))
        self.assertTrue(base["baseline"])
        v, cls, detail = self.judge(walk_obs(self.d, base, towards(base, [0, 0.05, 0, 0.05])), base)
        self.assertEqual((v, cls), ("PASS", "PASS"), detail)
        v, cls, detail = self.judge(walk_obs(self.d, base, towards(base, [0.1, 0.2, 0.3, 0.4])), base)
        self.assertEqual((v, cls), ("FAIL", "WANDER"), detail)      # its own package brought it 7 m closer
        part = walk_obs(self.d, base, towards(base, [0, 0]))
        self.assertEqual(self.judge(part, base)[:2], ("INCONCLUSIVE", "UNREAD"))


class NpcPlanTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        touch(self.d, "FO4Port.esm")

    def plan(self, tests, *extra):
        exp = tempfile.mkdtemp()
        jdump(tests, os.path.join(exp, "plan.json"))
        out = os.path.join(self.d, "q")
        tq.main(["plan-npc", "--staging", self.d, "--exp-dir", exp, "--out", out, *extra])
        return jload(os.path.join(out, "queue.json"))

    def test_n0_and_n1_plans(self):
        n1 = dict(N0, label="N1 ptr", control=False, expect="FAIL NONAV", travel="coc FO4CW_RedRocketSpawn",
                  a=[-987.4286, 1128.2286, 105.0286], b=[-976.4571, 1144.6857, 105.0286], drop=30, settle_ms=7000,
                  anchor={"ref": "02000800", "local": [-989.0286, 1147.2, 105.1434]},
                  spawn_local=[-989.0286, 1147.2, 105.1434], basis="hypothesis: no NAVM in the plugin world")
        base = dict(N0, label="N0_base", method="none", control=False)
        q = self.plan([n1, N0, base], "--plugins", "FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm",
                      "--install-exp", os.path.join(self.d, "exp2b"), "--control-queue", os.path.join(self.d, "n0q"))
        tb, t0, t1 = q["tests"]
        self.assertTrue(tb["baseline"] and not tb["control"])     # baseline first, then the controls
        self.assertTrue(t0["control"] and not t1["control"] and not t1["baseline"])
        self.assertEqual([t["id"] for t in q["tests"]], ["0000_npc_nav_N0_base", "0001_npc_nav_N0_ptr", "0002_npc_nav_N1_ptr"])
        self.assertEqual((t0["kind"], t0["cell"], t0["npc"], t0["method"]), ("npc_nav", "", "0000CF96", "ptr_player"))
        self.assertEqual(t0["reads_s"], [0.0, 3.0, 8.0, 15.0, 30.0])
        self.assertEqual((t0["radius"], t0["min_progress"], t0["nomove"], t0["max_speed"]), (2.5, 5.0, 0.5, 8.0))
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
               {"settle_ms": 10 ** 6}, {"spawn_local": [0, 0, 0, 0]}, {"max_speed": 0},
               {"method": "none", "control": True},                                  # a baseline gates the controls
               {"requires": "terrain_exp2b"}, {"requires": {"queue": "q", "test": "a b"}},
               {"requires": {"queue": "", "test": "x"}}, {"requires": {"queue": "q", "test": "x", "verdict": "OK"}}]
        for b in bad:
            with self.assertRaises(SystemExit, msg=str(b)):
                self.plan([dict(N0, **b)])
        with self.assertRaises(SystemExit):
            self.plan([])
        with self.assertRaises(SystemExit):
            self.plan(["coc QASmoke"])

    def test_a_required_test_must_have_measured_the_installed_world(self):
        world = os.path.join(self.d, "terrain_exp2b2")
        terr = os.path.join(self.d, "terrain_exp2b3")
        os.makedirs(terr)
        jdump({"experiment": world, "tests": [{"id": "0000_terrain_FO4CW_RedRocketSpawn"}]},
              os.path.join(terr, "queue.json"))
        n1 = dict(N0, control=False, requires={"queue": terr, "test": "0000_terrain_FO4CW_RedRocketSpawn"})
        inst = ["--plugins", "FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm"]
        q = self.plan([n1], *inst, "--install-exp", world)
        self.assertEqual(q["tests"][0]["requires"],
                         {"queue": terr, "test": "0000_terrain_FO4CW_RedRocketSpawn", "verdict": "PASS"})
        with self.assertRaises(SystemExit):                       # the terrain queue tested another staged folder
            self.plan([n1], *inst, "--install-exp", os.path.join(self.d, "terrain_exp2b"))
        with self.assertRaises(SystemExit):                       # no such test there
            self.plan([dict(n1, requires={"queue": terr, "test": "0001_other"})], *inst, "--install-exp", world)
        with self.assertRaises(SystemExit):                       # no such queue
            self.plan([dict(n1, requires={"queue": os.path.join(self.d, "none"), "test": "x"})], *inst,
                      "--install-exp", world)

    def test_qstep_types_only_the_planned_method_lines(self):
        # testqueue.NPC_METHODS and qstep.ps1's table must agree: every planned console line is in the step as written
        src = text(QSTEP)
        for method, lines in tq.NPC_METHODS.items():
            self.assertIn(f"'{method}' = @(", src)
            for line in lines:
                self.assertIn(f"'{line}'", src, line)
        self.assertIn("'none' = @()", src)
        self.assertIn("@('gnm') -cnotcontains", src)


class NpcStepScriptTests(unittest.TestCase):
    def test_qstep_has_the_npc_step(self):
        block = npc_block()
        for need in ("ClearConsole", "player.placeatme $npc 1", "'plr'", "GetIsID $npc", "'GetSelf'", "prid",
                     "'disable', 'GetDisabled'", "type:markfordelete", "Select-Npc", "$obs['samples']", "Save-Obs"):
            self.assertIn(need, block, need)
        # typed values are checked before anything is typed
        for check in ("'^coc [A-Za-z0-9_]+$'", "$npc -notmatch $hex8", "$methods.ContainsKey", "\"bad anchor\""):
            self.assertIn(check, block, check)
        # the walk command and the removal are only typed after a confirmed selection
        self.assertLess(block.index("$sel = Select-Npc"), block.index("$cmds += $lines"))
        self.assertLess(block.rindex("$sel = Select-Npc"), block.index("'disable', 'GetDisabled'"))
        # no position offset from a failed read ("fail console 3"): the numeric pattern, as the terrain step
        self.assertIn("$num3 = '^\\s*-?\\d+(\\.\\d+)?\\s+", block)

    def test_anchor_that_reads_its_local_position_falls_back_to_the_arrival(self):
        # exp2b a1 (2026-10-11): anchor_read -989.03 1147.20 105.14 = its local position; the real offset came from
        # the arrival. Without the fallback A and B were used as world coordinates, 2.3 km off the overlay.
        block = npc_block()
        fb = block[block.index("if ($t.anchor) {"):block.index("$ax = [double]$t.a[0]")]
        self.assertIn("[Math]::Abs($ox) -lt 0.01 -and [Math]::Abs($oy) -lt 0.01 -and $t.spawn_local", fb)
        self.assertIn("$obs.Remove('offset')", fb)
        self.assertIn("$obs['anchor_unmerged'] = $true", fb)
        self.assertLess(fb.index("anchor_unmerged"), fb.index("$obs['offset_from'] = 'spawn'"))

    def test_the_offset_comes_from_a_settled_arrival(self):
        block = npc_block()
        self.assertIn("$arr = Read-Settled", block)
        self.assertIn("if ($arr.settled) {", block)
        self.assertLess(block.index("$arr = Read-Settled"), block.index("$obs['offset_from'] = 'spawn'"))
        self.assertIn("still moving", block)

    def test_send_keeps_double_quotes(self):
        # Windows PowerShell 5.1 strips '"' inside a native argument; Send writes them as \" (checked end to end in
        # test_qstep_sandbox.test_cf_is_typed_with_its_quotes)
        src = text(QSTEP)
        send = src[src.index("function Send($seq) {"):src.index("function Console-Open")]
        self.assertIn("$arg = $seq -replace '\"', '\\\"'", send)
        self.assertIn("-Seq $arg", send)

    def test_samples_stop_in_time_for_the_removal(self):
        block = npc_block()
        self.assertIn("$budget = if ($t.budget_s)", block)
        loop = block[block.index("foreach ($s in @($t.reads_s))"):block.index("# 7. remove the actor")]
        self.assertIn("if ((Left-S) - $wait -lt $reserve)", loop)
        self.assertIn("samples_cut", loop)

    def test_removal_by_id_needs_the_ref_near_a_or_b(self):
        block = npc_block()
        rid = block[block.index("if (-not $sel -and $spawnSelf) {"):block.index("if ($sel) {\n      $d = Npc-Capture")]
        self.assertIn("'getpos x', 'getpos y', 'getpos z'", rid)
        self.assertIn("-eq $spawnSelf -and $near", rid)

    def test_each_capture_tells_the_parser_what_it_typed(self):
        block = npc_block()
        self.assertIn('"--expect=$($exp -join \',\')"', block)
        self.assertIn('"--typed=$($typed -join \',\')"', block)

    def test_step_timeout_covers_the_worst_case_and_grows_with_reads(self):
        t = tq.npc_test(0, N0)
        self.assertGreater(tq.step_timeout(t), tq.step_timeout(dict(t, reads_s=[0, 5])))
        # worst case: every read needs three Select-Npc sessions, plus the removal reserve
        self.assertGreaterEqual(tq.step_timeout(t), 4 * 3 * tq.NPC_SESSION_S + tq.NPC_REMOVE_S + 30)
        n1 = tq.npc_test(0, dict(N0, reads_s=[0, 5, 15, 30, 60], settle_ms=7000))
        self.assertGreater(tq.step_timeout(n1), 915)              # the old limit was cut by the Select-Npc fallbacks
        self.assertEqual(tq.step_timeout({"kind": "fall"}), 300)
        self.assertEqual(tq.step_timeout({"kind": "terrain", "points": [{}, {}]}), 150 + 90 * 3)

    def test_the_spec_carries_the_step_budget(self):
        d = tempfile.mkdtemp()
        t = tq.npc_test(0, N0)
        r = tq.Runner.__new__(tq.Runner)
        r.q = {"plugin_index": "02"}
        seen = {}

        def ps(script, args, timeout, steal=False):
            seen["timeout"], seen["spec"] = timeout, jload(args[args.index("-Spec") + 1])
            return 0, ""
        r._ps = ps
        r._step(t, d)
        self.assertEqual(seen["timeout"], tq.step_timeout(t))
        self.assertEqual(seen["spec"]["budget_s"], tq.step_timeout(t) - 60)
        r._step({"kind": "fall", "id": "f"}, d)
        self.assertNotIn("budget_s", seen["spec"])


# Console OCR texts. The layouts are modelled on real OCR of this PC's console (2026-10-11): inline
# ("Get Pos: X > > -10.07", '>>' sometimes dropped: "GetPos: X -989.03"), and column (labels first, then the values,
# the arguments 'x' / 'z' drifting into the value column, 'y' lost: "Get Pos: Z > > player.getpos ... tgm 3.66 x
# -10.07 43.95 z -10.95").
INLINE = "GetIsID 0000CF96\nGetIsID > > 1.00\ngetpos x\nGet Pos: X > > -8.01\ngetpos\nGet Pos: Y > > -4.02\ngetpos z\nGetPos: Z > > 0.01"
COLUMN = ("GetIsID\nGetIsID > >\ngetpos\nGet Pos: X > >\ngetpos\nGet Pos: Y > >\ngetpos\nGetPos: Z > >\n"
          "0000CF96\n1.00\nx\n-8.01\n-4.02\nz\n0.01")
NO_ARROWS = "prid 02000800\nget pos x\nGetPos: X -989.03\nget pos y\nGetPos: Y 1147.20\ngetpos z\nGetPos: Z 105.14"


class ParseNpcTests(unittest.TestCase):
    def P(self, raw, expect=SELECT, typed=()):
        return parse_npc.parse(raw, expect, typed)

    def test_inline_and_column_layouts(self):
        for name, raw in (("inline", INLINE), ("column", COLUMN),
                          ("column, id kept", COLUMN.replace("GetIsID\n", "GetIsID 0000CF96\n", 1)
                           .replace("0000CF96\n1.00", "1.00")),
                          ("split words", INLINE.replace("GetIsID", "Get Is ID")),
                          ("l for I", INLINE.replace("GetIsID > >", "GetlsID > >"))):
            r = self.P(raw)
            self.assertEqual((r["isid"], r["pos"]), (1, "-8.01 -4.02 0.01"), name)
        self.assertEqual(self.P(NO_ARROWS, ["x", "y", "z"], ["02000800"])["pos"], "-989.03 1147.20 105.14")

    def test_condition_replies(self):
        self.assertEqual(self.P("GetIsID 0000CF96\nGetIsID: 0.00\n", ["isid"])["isid"], 0)
        self.assertEqual(self.P("GetIsID 0000CF96\nGetIsID 1 00\n", ["isid"])["isid"], 1)       # '>>' and '.' lost
        self.assertIsNone(self.P("GetIsID 0000CF96\nMissing reference\n", ["isid"])["isid"])   # the echo is no reply
        self.assertIsNone(self.P("GetIsID 1001F3E8\n", ["isid"])["isid"])
        self.assertIsNone(self.P("GetIsID >> 1.00\n", ["isid"])["isid"])                      # no echo: not ours
        self.assertIsNone(self.P(INLINE.replace("> > 1.00", "> > 0.50"))["isid"])              # misaligned: no flag

    def test_a_reply_older_than_this_session_is_never_read(self):
        # ClearConsole did not clear: the previous session's lines are still on screen above this session's
        stale = ("GetIsID 0000CF96\nGetIsID >> 1.00\ngetpos x\nGetPos: X >> 1.00\ngetpos y\nGetPos: Y >> 2.00\n"
                 "getpos z\nGetPos: Z >> 3.00\nGetIsID 0000CF96\nMissing reference\ngetpos x\nMissing reference\n")
        r = self.P(stale)
        self.assertEqual((r["isid"], r["pos"]), (None, None))
        again = stale.replace("Missing reference\ngetpos x\nMissing reference\n",
                              "GetIsID >> 1.00\ngetpos x\nGetPos: X >> 5.00\ngetpos y\nGetPos: Y >> 6.00\n"
                              "getpos z\nGetPos: Z >> 7.00\n")
        r = self.P(again)
        self.assertEqual((r["isid"], r["pos"], r["how"]), (1, "5.00 6.00 7.00", "inline"))
        # in the column layout an old session cannot be told apart: nothing is read
        col = "GetIsID\nGetIsID > >\ngetpos\nGet Pos: X > >\nGetIsID\nMissing reference\ngetpos\nMissing reference\n1.00\n3.00"
        r = self.P(col)
        self.assertEqual((r["isid"], r["pos"]), (None, None))

    def test_a_lone_value_is_never_a_coordinate(self):
        # the old bare-number fallback took GetIsID's "1.00" on its own line as X when a GetPos value was missing
        raw = ("GetIsID 0000CF96\nGetIsID > >\n1.00\ngetpos x\nGet Pos: X > >\n-7.20\ngetpos y\nGet Pos: Y > >\n"
               "-4.00\ngetpos z\nGet Pos: Z > >\n")
        r = self.P(raw)
        self.assertIsNone(r["pos"])
        self.assertEqual(r["isid"], 1)

    def test_numbers_that_are_not_values(self):
        # an echoed integer, form ids and a decimal form id are never values; "-0 85" is -0.85
        spawn = "player.placeatme 0000CF96 1\nplr\nGetIsID 0000CF96\nGetIsID > >\nGetSelf\nGetSelf > >\n1.00\nFF000D6E"
        r = self.P(spawn, ["isid", "self"])
        self.assertEqual((r["isid"], r["self"], r["how"]), (1, "FF000D6E", "order"))
        r = self.P(INLINE.replace("-8.01", "-0 85"))
        self.assertEqual(r["pos"], "-0.85 -4.02 0.01")

    def test_getself(self):
        for reply in ("GetSelf >> FF000800", "GetSelf >> (FF000800)", "GetSelf: 0xff000800", "GetSelf >> 4278192128.00",
                      "FF000800", "GetSelf >> FFOOO800"):
            self.assertEqual(self.P(f"GetSelf\n{reply}\n", ["self"])["self"], "FF000800", reply)
        self.assertIsNone(self.P("GetSelf\nGetSelf >> 0000CF96\n", ["self"])["self"])         # not a runtime ref
        self.assertIsNone(self.P("GetSelf\n", ["self"])["self"])                              # echo, no reply
        self.assertIsNone(self.P("GetSelf >> FF000801\nGetSelf\nScript command not found\n", ["self"])["self"])

    def test_getself_after_prid_needs_the_reply_not_just_the_echo(self):
        ok = "prid FF000D6E\nGetSelf\nGetSelf > > FF000D6E\n"
        self.assertEqual(self.P(ok, ["self"], ["FF000D6E"])["self"], "FF000D6E")
        col = "prid\nGetSelf\nGetSelf > >\nFF000D6E\nFF000D6E"                               # column layout
        self.assertEqual(self.P(col, ["self"], ["FF000D6E"])["self"], "FF000D6E")
        for failed in ("prid FF000D6E\nGetSelf\n", "prid\nGetSelf\nFF000D6E"):                # only our argument
            self.assertIsNone(self.P(failed, ["self"], ["FF000D6E"])["self"], failed)
        by_id = ("prid FF000D6E\nGetSelf\nGetSelf > > FF000D6E\ngetpos x\nGet Pos: X > > -8.01\ngetpos\n"
                 "Get Pos: Y > > -4.02\ngetpos z\nGetPos: Z > > 0.01")
        r = self.P(by_id, ["self", "x", "y", "z"], ["FF000D6E"])
        self.assertEqual((r["self"], r["pos"]), ("FF000D6E", "-8.01 -4.02 0.01"))

    def test_disabled(self):
        self.assertEqual(self.P("disable\nGetDisabled\nGetDisabled > > 1.00\n", ["disabled"])["disabled"], 1)
        self.assertEqual(self.P("disable\nGetDisabled\nGetDisabled > >\n1.00\n", ["disabled"])["disabled"], 1)
        self.assertIsNone(self.P("GetDisabled >> 1.00\n", ["disabled"])["disabled"])

    def test_command_line(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "ocr.txt")
        with open(p, "w", encoding="utf-8-sig") as f:
            f.write(COLUMN)
        import contextlib
        import io
        for argv, want in (([p, "--expect=isid,x,y,z", "--typed="], (1, "-8.01 -4.02 0.01")),
                           ([p, "--expect=", "--typed="], (None, None))):               # the walk session: OCR only
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                parse_npc.main(argv)
            r = json.loads(buf.getvalue())
            self.assertEqual((r["isid"], r["pos"]), want, argv)
            self.assertIn("GetIsID", r["ocr"])
        with self.assertRaises(SystemExit):
            parse_npc.main([p, "--expect=isid,w"])


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
        jdump(q, os.path.join(d, "queue.json"))

    def run_queue(self, d, outcome):
        """outcome: test id -> 'walk' | 'still' | 'lost' (or a list, one per attempt); returns {id: step calls}."""
        calls = {}

        def step(t, out):
            n = calls[t["id"]] = calls.get(t["id"], 0) + 1
            o = outcome[t["id"]]
            o = o[min(n, len(o)) - 1] if isinstance(o, list) else o
            fr = [0.2, 0.4, 0.7, 0.9] if o == "walk" else [0, 0, 0, 0]
            obs = walk_obs(out, t, towards(t, fr))
            if o == "lost":
                obs["command_sent"] = False
            jdump(obs, os.path.join(out, "obs.json"))
            return 0
        r = tq.Runner(d, run_args(), ctl=FakeControls(), step=step)
        r.session, r._ps = True, (lambda *a, **k: (0, ""))
        r.run()
        return calls

    def done(self, d):
        return jload(os.path.join(d, "state.json"))["done"]

    def make_tests(self):
        n0 = tq.npc_test(0, N0)
        n1 = tq.npc_test(1, dict(N0, label="N1", control=False, expect="FAIL NONAV"))
        return n0, n1

    def test_a_fail_counts_only_after_the_control_passed(self):
        d = tempfile.mkdtemp()
        n0, n1 = self.make_tests()
        self.queue(d, [n0, n1])
        self.run_queue(d, {n0["id"]: "walk", n1["id"]: "still"})
        done = self.done(d)
        self.assertEqual((done[n1["id"]]["verdict"], done[n1["id"]]["class"]), ("FAIL", "NONAV"))
        rep = jload(os.path.join(d, "report.json"))
        exp = {e["id"]: e for e in rep["expectations"]}
        self.assertEqual(exp[n1["id"]]["result"], "FAIL NONAV")
        self.assertIn("| yes |", text(os.path.join(d, "report.md")))

    def test_failed_control_makes_the_others_inconclusive_and_final(self):
        d = tempfile.mkdtemp()
        n0, n1 = self.make_tests()
        self.queue(d, [n0, n1])
        calls = self.run_queue(d, {n0["id"]: "still", n1["id"]: "still"})
        done = self.done(d)
        self.assertEqual(done[n0["id"]]["class"], "NONAV")             # the control itself is judged as it is
        self.assertEqual((done[n1["id"]]["verdict"], done[n1["id"]]["class"]), ("INCONCLUSIVE", "CONTROL"))
        self.assertEqual(done[n1["id"]]["raw"][:2], ["FAIL", "NONAV"])
        self.assertEqual(calls[n1["id"]], 1)                            # not retried: a retry cannot change it
        with open(os.path.join(d, "results.jsonl")) as f:
            line = [json.loads(x) for x in f][-1]
        self.assertIn("raw verdict FAIL NONAV", line["detail"])
        self.assertEqual(line["expect"], "FAIL NONAV")

    def test_a_control_retried_at_the_end_still_counts_in_the_report(self):
        # the control's first attempt is inconclusive (handle lost), N1 is gated, the retried control passes
        d = tempfile.mkdtemp()
        n0, n1 = self.make_tests()
        self.queue(d, [n0, n1])
        self.run_queue(d, {n0["id"]: ["lost", "walk"], n1["id"]: "still"})
        self.assertEqual(self.done(d)[n0["id"]]["verdict"], "PASS")
        rep = jload(os.path.join(d, "report.json"))
        self.assertEqual({e["id"]: e for e in rep["expectations"]}[n1["id"]]["result"], "FAIL NONAV")
        self.assertIn("gated again at report time", text(os.path.join(d, "report.md")))

    def test_control_from_another_queue(self):
        n0, n1 = self.make_tests()
        ctrl = tempfile.mkdtemp()
        self.queue(ctrl, [n0])
        for state, want in ((None, "CONTROL"), ("FAIL", "CONTROL"), ("PASS", "NONAV")):
            d = tempfile.mkdtemp()
            self.queue(d, [n1], control_queue=ctrl)
            if state:
                jdump({"done": {n0["id"]: {"verdict": state, "class": "X", "attempts": 1}}},
                      os.path.join(ctrl, "state.json"))
            self.run_queue(d, {n1["id"]: "still"})
            self.assertEqual(self.done(d)[n1["id"]]["class"], want, state)

    def test_n1_run_before_n0_is_gated_again_once_n0_passed(self):
        n0, n1 = self.make_tests()
        ctrl, d = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.queue(ctrl, [n0])
        self.queue(d, [n1], control_queue=ctrl)
        self.run_queue(d, {n1["id"]: "still"})                           # N0 has no result yet
        self.assertEqual(jload(os.path.join(d, "report.json"))["tally"]["npc_nav"], {"INCONCLUSIVE": 1})
        jdump({"done": {n0["id"]: {"verdict": "PASS", "class": "PASS", "attempts": 1}}}, os.path.join(ctrl, "state.json"))
        rep = tq.write_report(d)
        self.assertEqual(rep["tally"]["npc_nav"], {"FAIL": 1})
        self.assertEqual(rep["expectations"][0]["result"], "FAIL NONAV")

    def test_a_baseline_that_came_to_b_voids_the_control(self):
        base = tq.npc_test(0, dict(N0, label="N0_base", method="none", control=False))
        n0, n1 = self.make_tests()
        for b_outcome, want in (("walk", "CONTROL"), ("still", "NONAV")):
            d = tempfile.mkdtemp()
            self.queue(d, [base, n0, n1])
            self.run_queue(d, {base["id"]: b_outcome, n0["id"]: "walk", n1["id"]: "still"})
            done = self.done(d)
            self.assertEqual(done[base["id"]]["class"], "WANDER" if b_outcome == "walk" else "PASS")
            self.assertEqual(done[n1["id"]]["class"], want, b_outcome)
        with open(os.path.join(d, "results.jsonl")) as f:
            self.assertIn("baseline", [json.loads(x) for x in f][-1]["detail"])

    def test_pass_and_unconfigured_queues_are_not_gated(self):
        n0, n1 = self.make_tests()
        q = {"tests": [n1]}
        self.assertEqual(tq.control_gate(tempfile.mkdtemp(), q, n1, "FAIL", "NONAV", "x"), ("FAIL", "NONAV", "x"))
        q = {"tests": [n0, n1]}
        self.assertEqual(tq.control_gate(tempfile.mkdtemp(), q, n1, "PASS", "PASS", "x"), ("PASS", "PASS", "x"))
        other = dict(n1, method="follow_player")                       # the control has to match the method
        d = tempfile.mkdtemp()
        jdump({"done": {n0["id"]: {"verdict": "PASS", "class": "PASS", "attempts": 1}}}, os.path.join(d, "state.json"))
        jdump(q, os.path.join(d, "queue.json"))
        self.assertEqual(tq.control_gate(d, q, other, "FAIL", "NONAV", "x")[1], "CONTROL")
        self.assertEqual(tq.control_gate(d, q, n1, "FAIL", "NONAV", "x")[1], "NONAV")


class PreconditionTests(unittest.TestCase):
    def test_a_test_whose_world_was_not_verified_is_not_run(self):
        terr, d = tempfile.mkdtemp(), tempfile.mkdtemp()
        tid = "0000_terrain_FO4CW_RedRocketSpawn"
        n1 = tq.npc_test(0, dict(N0, label="N1", control=False, requires={"queue": terr, "test": tid}))
        jdump({"build_id": "abcd1234", "commit": "0" * 40, "staging": d, "plugin_sha256": "x", "save": "s",
               "plugin_index": "02", "hours": [[0, 24]], "tests": [n1]}, os.path.join(d, "queue.json"))
        gate = ControlGateTests()
        for state, ran in ((None, False), ({"verdict": "INCONCLUSIVE", "class": "MOVED"}, False),
                           ({"verdict": "FAIL", "class": "HEIGHTS"}, False), ({"verdict": "PASS", "class": "PASS"}, True)):
            for f in ("state.json", "results.jsonl"):
                if os.path.exists(os.path.join(d, f)):
                    os.remove(os.path.join(d, f))
            if state:
                jdump({"done": {tid: dict(state, attempts=1)}}, os.path.join(terr, "state.json"))
            calls = gate.run_queue(d, {n1["id"]: "walk"})
            done = gate.done(d)[n1["id"]]
            self.assertEqual(bool(calls), ran, state)
            if not ran:
                self.assertEqual((done["verdict"], done["class"], done["attempts"]), ("INCONCLUSIVE", "PRECONDITION", 0))
            else:
                self.assertEqual(done["verdict"], "PASS")
        self.assertIsNone(tq.precondition(tq.npc_test(0, N0)))


if __name__ == "__main__":
    unittest.main()
