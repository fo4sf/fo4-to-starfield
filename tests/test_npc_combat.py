"""npc_nav combat_reads (docs/ai/test-queue.md "Combat engagement"): the combat manager asked in every sample's console
session (GetCombatState, GetCombatTarget, GetLineOfSight player), parse_npc.py's reading of the replies, testqueue.py's
ENGAGED / NOCOMBAT judge, plan-npc's validation, runner feature npc_combat and qstep.ps1's whitelist. Synthetic data
only: no game, no Windows calls, no PowerShell run (tests/test_qstep_sandbox.py runs the step itself)."""
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import parse_npc  # noqa: E402
import runner_features  # noqa: E402
import testqueue as tq  # noqa: E402

QSTEP = os.path.join(ROOT, "scripts", "game", "qstep.ps1")
SPACER = {"label": "C1_spacer", "travel": "coc QASmoke", "npc": "00270255", "a": [5.5, -4.5, 0.0], "b": [-12.0, 12.0, 0.0],
          "method": "none", "reads_s": [0, 1, 3, 8, 15, 30], "radius": 3.0, "min_progress": 18.0, "arrive_progress": 18.0,
          "precommand_m": 3.0, "handle_tol": 6.0, "spawn_tol": 6.0, "control": False, "combat_reads": True,
          "expect": "PASS ENGAGED"}
COMBAT = ["isid", "x", "y", "z", "combat", "target", "los"]        # what a combat_reads sample session expects
TYPED = ["FF000800", "00270255"]                                   # prid <id>, GetIsID <npc>: the session's own ids
# OCR of such a session as the two layouts of 2026-10-11 would show it; the combat replies are HYPOTHESES (a condition
# function's decimal, the target in parentheses like GetSelf's reply)
INLINE = ("Clear Console\nprid FF000800\nGetlsID 00270255\nGetlslD > > 1.00\ngetpos x\nGet Po s: X > > 6.30\ngetpos y\n"
          "GetPos: Y > > -4.50\ngetpos z\nGetPos: Z > > 0.00\nGet Combat State\nGetCombatState > > 1.00\nGetCombatTarget\n"
          "GetCombatTarget > > (00000014)\nGetLlneOfSight player\nGetLineOfSight > > 1.00")
COLUMN = ("Clear Console\nprid\nGetlsID\nGetlslD > >\ngetpos\nGet Po s: X > >\ngetpos\nGetPos: Y > >\ngetpos\nGetPos: Z > >\n"
          "Get Combat State\nGetCombatState > >\nGetCombatTarget\nGetCombatTarget > >\nGetLineOfSight\nGetLineOfSight > >\n"
          "FF000800\n00270255\n1.00\nx\n6.30\n-4.50\nz\n0.00\n1.00\n(00000014)\nplayer\n1.00")
REFUSED = ("Clear Console\nprid FF000800\nGetlsID 00270255\nGetlslD > > 1.00\ngetpos x\nGet Po s: X > > 6.30\ngetpos y\n"
           "GetPos: Y > > -4.50\ngetpos z\nGetPos: Z > > 0.00\nGetCombatState\nScript command not found\nGetCombatTarget\n"
           "Script command not found\nGetLineOfSight player\nScript command not found")


def touch(d, name):
    open(os.path.join(d, name), "wb").close()
    return name


def combat_obs(d, t, combat, reads=None, **kw):
    """Observations as qstep.ps1 writes them for a combat_reads test: the spawn confirmed at A, the player at B, one
    confirmed sample per read; combat = [(state, target, los) | None] per sample (None: nothing parsed); reads = the
    actor's positions (default: it holds its ground at A, as the Spacer did)."""
    a, b = t["a"], t["b"]
    p0 = f"{a[0] + 0.8} {a[1]} {a[2]}"
    times = [x for x in t["reads_s"] if x > 0]
    reads = reads or [p0] * len(times)
    samples = []
    for k, (s, r, c) in enumerate(zip(times, reads, combat)):
        smp = {"t_game": s, "isid": 1, "read": r, "via": "prid", "shot": touch(d, f"npc{k}.png"),
               "combat": None, "target": None, "los": None, "combat_ocr": "GetCombatState Script command not found"}
        if c is not None:
            smp.update(combat=c[0], target=c[1], los=c[2], combat_ocr="GetCombatState > > 1.00 GetCombatTarget > > (00000014)")
        samples.append(smp)
    o = {"spawn": {"ref": "FF000800", "self": "FF000800", "isid": 1, "read": p0, "dist_a": 0.8, "confirmed": True, "why": ""},
         "t0": {"isid": 1, "read": p0, "via": "prid"}, "command_sent": True, "command": "",
         "player_b": f"{b[0]} {b[1]} {b[2]}", "samples": samples}
    o.update(kw)
    return o


class CombatParseTests(unittest.TestCase):
    def P(self, raw, expect=COMBAT, typed=TYPED):
        return parse_npc.parse(raw, expect, typed)

    def test_both_layouts_read_state_target_and_los_with_the_position(self):
        for name, raw in (("inline", INLINE), ("column", COLUMN), ("split", INLINE.replace("GetCombatTarget", "Get Combat Target")),
                          ("no arrows", INLINE.replace("GetCombatState > > 1.00", "GetCombatState 1.00"))):
            r = self.P(raw)
            self.assertEqual((r["isid"], r["pos"]), (1, "6.30 -4.50 0.00"), name)
            self.assertEqual((r["combat"], r["target"], r["los"]), (1, "00000014", 1), name)

    def test_integer_state_and_bare_or_0x_target(self):
        # GetDisabled replies an integer: GetCombatState may too; the target may come without parentheses
        for tgt in ("00000014", "0x00000014", "(00000014)"):
            r = self.P(INLINE.replace("GetCombatState > > 1.00", "GetCombatState > > 2").replace("(00000014)", tgt))
            self.assertEqual((r["combat"], r["target"], r["los"]), (2, "00000014", 1), tgt)
        r = self.P(INLINE.replace("GetCombatState > > 1.00", "GetCombatState > > 0.00").replace("(00000014)", "(00000000)"))
        self.assertEqual((r["combat"], r["target"]), (0, "00000000"))

    def test_an_unreadable_reply_is_null_never_a_value(self):
        r = self.P(REFUSED)
        self.assertEqual((r["isid"], r["pos"]), (1, "6.30 -4.50 0.00"))      # the position still reads
        self.assertEqual((r["combat"], r["target"], r["los"]), (None, None, None))
        r = self.P(INLINE.replace("GetCombatState > > 1.00", "GetCombatState > > 12.00"))     # not a combat state
        self.assertIsNone(r["combat"])
        self.assertEqual(r["target"], "00000014")
        r = self.P(INLINE.replace("GetLineOfSight > > 1.00", "GetLineOfSight > > 3.00"))
        self.assertIsNone(r["los"])

    def test_the_sessions_own_ids_are_never_the_target(self):
        # in the column layout prid's and GetIsID's arguments drift into the value column, after the reply labels
        r = self.P(COLUMN.replace("(00000014)\n", ""))
        self.assertIsNone(r["target"])
        r = self.P(INLINE.replace("(00000014)", "(FF000800)"))                 # the actor's own id: not a reply
        self.assertIsNone(r["target"])
        r = self.P(INLINE.replace("(00000014)", "(ff000801)"))                 # another actor: a target
        self.assertEqual(r["target"], "FF000801")

    def test_a_session_without_combat_reads_is_unchanged(self):
        r = self.P("GetIsID 0000CF96\nGetIsID > > 1.00\ngetpos x\nGet Pos: X > > -8.01\ngetpos y\nGet Pos: Y > > -4.02\n"
                   "getpos z\nGetPos: Z > > 0.01", ["isid", "x", "y", "z"], [])
        self.assertEqual((r["isid"], r["pos"], r["how"]), (1, "-8.01 -4.02 0.01", "order"))
        self.assertEqual((r["combat"], r["target"], r["los"]), (None, None, None))
        with self.assertRaises(SystemExit):
            parse_npc.main(["x.txt", "--expect", "isid,fight"])

    def test_an_older_sessions_combat_reply_is_not_read(self):
        # the previous sample's replies stay on screen above this session's ClearConsole; this session's state read 0
        older = "GetCombatState > > 1.00\nGetCombatTarget > > (00000014)\n"
        r = self.P(older + INLINE.replace("GetCombatState > > 1.00", "GetCombatState > > 0.00").replace("(00000014)", "(00000000)"))
        self.assertEqual((r["combat"], r["target"]), (0, "00000000"))


class CombatJudgeTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.t = tq.npc_test(0, SPACER)

    def judge(self, obs, t=None):
        return tq.judge(t or self.t, obs, self.d)

    def test_in_combat_with_the_player_is_engaged_whatever_the_walk(self):
        c = [(0, "00000000", 1), (0, "00000000", 1), (1, "00000014", 1), (1, "00000014", 0), (1, "00000014", 1)]
        v, cls, detail = self.judge(combat_obs(self.d, self.t, c))
        self.assertEqual((v, cls), ("PASS", "ENGAGED"), detail)
        self.assertIn("from t 8.0 s (state 1, target 00000014, LOS 1), 3 of 5 reads", detail)
        self.assertIn("walk: PASS PASS, stayed away from B without a command", detail)     # the Spacer held its ground
        self.assertIn("[expected PASS ENGAGED]", detail)
        # a hostile actor that also came for the player: still ENGAGED, the approach is detail
        a, b = self.t["a"], self.t["b"]
        reads = [f"{a[0] + (b[0] - a[0]) * f:.2f} {a[1] + (b[1] - a[1]) * f:.2f} 0.00" for f in (0.1, 0.4, 0.8, 0.9, 0.95)]
        v, cls, detail = self.judge(combat_obs(self.d, self.t, c, reads))
        self.assertEqual((v, cls), ("PASS", "ENGAGED"), detail)
        self.assertIn("walk: FAIL WANDER", detail)

    def test_all_reads_state_zero_is_nocombat(self):
        v, cls, detail = self.judge(combat_obs(self.d, self.t, [(0, "00000000", 1)] * 5))
        self.assertEqual((v, cls), ("FAIL", "NOCOMBAT"), detail)
        self.assertIn("5 of 5 reads state 0", detail)
        # a state 0 whose target did not parse is still a read of "no combat"
        v, cls, detail = self.judge(combat_obs(self.d, self.t, [(0, None, None)] * 5))
        self.assertEqual((v, cls), ("FAIL", "NOCOMBAT"), detail)

    def test_unreadable_replies_are_inconclusive_not_nocombat(self):
        v, cls, detail = self.judge(combat_obs(self.d, self.t, [None] * 5))
        self.assertEqual((v, cls), ("INCONCLUSIVE", "COMBATREAD"), detail)
        self.assertIn("read in 0 of 5 samples", detail)
        self.assertIn("Script command not found", detail)                     # the raw OCR is shown
        v, cls, detail = self.judge(combat_obs(self.d, self.t, [(0, "00000000", 1)] * 4 + [None]))
        self.assertEqual((v, cls), ("INCONCLUSIVE", "COMBATREAD"), detail)     # 4 of 5: not every sample read
        # in combat, but with whom? the target did not parse / was another ref
        v, cls, detail = self.judge(combat_obs(self.d, self.t, [(1, None, 1)] * 5))
        self.assertEqual((v, cls), ("INCONCLUSIVE", "COMBATREAD"), detail)
        self.assertIn("target was not read", detail)
        v, cls, detail = self.judge(combat_obs(self.d, self.t, [(1, "FF000801", 1)] * 5))
        self.assertEqual((v, cls), ("INCONCLUSIVE", "OTHERTARGET"), detail)
        self.assertIn("with FF000801, not the player 00000014", detail)

    def test_only_confirmed_samples_with_a_screenshot_count(self):
        obs = combat_obs(self.d, self.t, [(1, "00000014", 1)] * 5)
        obs["samples"][0]["isid"] = None                                       # the selection was not confirmed
        obs["samples"][1]["shot"] = "missing.png"
        v, cls, detail = self.judge(obs)
        self.assertEqual((v, cls), ("PASS", "ENGAGED"), detail)
        self.assertIn("3 of 3 reads", detail)
        for s in obs["samples"]:
            s["isid"] = None
        v, cls, detail = self.judge(obs)
        self.assertEqual((v, cls), ("INCONCLUSIVE", "UNREAD"), detail)
        obs = combat_obs(self.d, self.t, [(1, "00000014", 1)] * 5)
        obs["samples"] = []
        self.assertEqual(self.judge(obs)[:2], ("INCONCLUSIVE", "UNREAD"))

    def test_the_walk_preconditions_still_hold(self):
        obs = combat_obs(self.d, self.t, [(1, "00000014", 1)] * 5)
        obs["spawn"] = dict(obs["spawn"], isid=0, confirmed=False, why="GetIsID 00270255 read 0")
        self.assertEqual(self.judge(obs)[:2], ("INCONCLUSIVE", "SPAWN"))
        obs = combat_obs(self.d, self.t, [(1, "00000014", 1)] * 5, player_b="fail")
        self.assertEqual(self.judge(obs)[:2], ("INCONCLUSIVE", "TARGET"))
        obs = combat_obs(self.d, self.t, [(1, "00000014", 1)] * 5, command_sent=False)
        self.assertEqual(self.judge(obs)[:2], ("INCONCLUSIVE", "HANDLE"))

    def test_startcombat_player_is_judged_the_same_way(self):
        t = tq.npc_test(1, dict(SPACER, label="C1_cmd", method="combat_player", npc="002B211C", expect="FAIL NOCOMBAT"))
        v, cls, detail = self.judge(combat_obs(self.d, t, [(0, "00000000", 1)] * 5, command="StartCombat player"), t)
        self.assertEqual((v, cls), ("FAIL", "NOCOMBAT"), detail)
        self.assertIn("walk: FAIL NONAV", detail)                              # N0b_combat: the citizen froze
        v, cls, detail = self.judge(combat_obs(self.d, t, [(1, "00000014", 1)] * 5), t)
        self.assertEqual((v, cls), ("PASS", "ENGAGED"), detail)

    def test_combat_read_takes_values_only(self):
        self.assertEqual(tq.combat_read({"combat": 1.0, "target": "00000014", "los": 0.0}), (1, "00000014", 0))
        self.assertEqual(tq.combat_read({"combat": True, "target": "0000014", "los": True}), (None, None, None))
        self.assertEqual(tq.combat_read({"combat": 12, "target": "player", "los": 2}), (None, None, None))
        self.assertEqual(tq.combat_read({"combat": "1", "target": "(00000014)", "los": "1"}), (None, None, None))
        self.assertEqual(tq.combat_read({"combat": 2, "target": "ff000801"}), (2, "FF000801", None))
        self.assertEqual(tq.combat_read("x"), (None, None, None))
        # the combat capture's own GetIsID read 0: another ref answered, nothing counts (None: not read, still counts)
        self.assertEqual(tq.combat_read({"combat": 1, "target": "00000014", "los": 1, "combat_isid": 0}), (None, None, None))
        self.assertEqual(tq.combat_read({"combat": 1, "target": "00000014", "los": 1, "combat_isid": None}), (1, "00000014", 1))
        self.assertEqual(tq.combat_read({"combat": 1, "target": "00000014", "los": 1, "combat_isid": 1}), (1, "00000014", 1))

    def test_no_control_gate_for_a_combat_test(self):
        # a queue with controls configured gates a FAIL of a commanded test; a combat FAIL stands on its own replies
        qdir = tempfile.mkdtemp()
        q = {"tests": [dict(self.t), {"id": "0001_npc_nav_ctrl", "kind": "npc_nav", "npc": "00270255", "method": "ptr_player",
                                       "control": True, "baseline": False}]}
        v, cls, detail = tq.control_gate(qdir, q, self.t, "FAIL", "NOCOMBAT", "never in combat")
        self.assertEqual((v, cls, detail), ("FAIL", "NOCOMBAT", "never in combat"))
        v, cls, detail = tq.control_gate(qdir, q, self.t, "PASS", "ENGAGED", "in combat")
        self.assertEqual(detail, "in combat")                                 # no baseline note either
        self.assertEqual(tq.SEVERITY[("npc_nav", "NOCOMBAT")], 3)


class CombatPlanTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        open(os.path.join(self.d, "FO4Port.esm"), "wb").close()

    def plan(self, tests, *extra):
        import json
        exp = tempfile.mkdtemp()
        with open(os.path.join(exp, "plan.json"), "w") as f:
            json.dump(tests, f)
        out = os.path.join(self.d, "q")
        tq.main(["plan-npc", "--staging", self.d, "--exp-dir", exp, "--out", out, *extra])
        with open(os.path.join(out, "queue.json"), encoding="utf-8-sig") as f:
            return json.load(f)

    def test_combat_reads_is_planned_and_needs_the_runner_feature(self):
        citizen = dict(SPACER, label="C1_citizen", npc="002B211C", expect="FAIL NOCOMBAT")
        raider = dict(SPACER, label="C1_raider", npc="02F04800")
        q = self.plan([SPACER, citizen, raider], "--fresh")
        self.assertEqual([t["ref"] for t in q["tests"]], ["C1_spacer", "C1_citizen", "C1_raider"])
        for t in q["tests"]:
            self.assertIs(t["combat_reads"], True)
            self.assertFalse(t["baseline"] or t["control"])                   # neither a wander baseline nor a control
            self.assertEqual((t["method"], t["fresh"], t["handle_tol"], t["spawn_tol"]), ("none", True, 6.0, 6.0))
        self.assertEqual(q["needs"], ["npc_combat", "npc_t0"])
        self.assertEqual(q["pre_launch"][1:], [os.path.join("scripts", "game", "runner_features.py"), "check",
                                               "npc_combat,npc_t0"])
        q = self.plan([dict(SPACER, method="combat_player", npc="002B211C")])
        self.assertEqual(q["needs"], ["npc_combat", "npc_t0"])
        q = self.plan([dict(SPACER, combat_reads=False)])                     # false: the walk judge as before
        self.assertNotIn("combat_reads", q["tests"][0])
        self.assertTrue(q["tests"][0]["baseline"])
        self.assertEqual(q["needs"], ["npc_t0"])

    def test_combat_reads_is_validated(self):
        for bad in ({"method": "ptr_player"}, {"method": "follow_player"}, {"control": True},
                    {"control_npc": "002B211C"}, {"combat_reads": "yes"}, {"combat_reads": 1}):
            with self.assertRaises(SystemExit, msg=str(bad)):
                self.plan([dict(SPACER, **bad)])

    def test_runner_feature_npc_combat(self):
        self.assertIn("npc_combat", runner_features.FEATURES)
        self.assertEqual(runner_features.needs([{"combat_reads": True}]), ["npc_combat"])
        self.assertEqual(runner_features.needs([{"combat_reads": False}, {"method": "combat_player"}]), [])
        self.assertEqual(runner_features.missing(["npc_combat", "npc_t0"]), [])
        self.assertEqual(runner_features.main(["check", "npc_combat"]), 0)

    def test_step_timeout_grows_with_the_combat_lines(self):
        t = tq.npc_test(0, SPACER)
        plain = tq.npc_test(0, dict(SPACER, combat_reads=False))
        n = len([x for x in t["reads_s"] if x > 0])
        self.assertEqual(tq.step_timeout(t) - tq.step_timeout(plain), n * tq.NPC_COMBAT_S)   # one more capture a read
        self.assertGreaterEqual(tq.NPC_COMBAT_S, tq.NPC_SESSION_S)


class CombatStepScriptTests(unittest.TestCase):
    def block(self):
        with open(QSTEP, encoding="utf-8") as f:
            src = f.read()
        return src[src.index("'npc_nav' {"):src.index("'recover' {")]

    def test_qstep_types_exactly_the_planned_combat_lines(self):
        block = self.block()
        self.assertIn("$combatCmds = @(" + ", ".join(f"'{c}'" for c in tq.NPC_COMBAT_READS) + ")", block)
        # no other combat command anywhere in the step (nothing else is whitelisted)
        lines = set(re.findall(r"'(Get(?:Combat|LineOfSight|LOS)[^']*)'", block))
        self.assertEqual(lines, set(tq.NPC_COMBAT_READS))
        self.assertNotIn("GetLOS", block)
        # the three lines follow the confirmed position capture as a second capture in the same console open (the
        # console shows about nine lines: one capture of everything scrolled the position off), with GetIsID again
        for need in ("function Select-Npc([switch]$Combat)", "Select-Npc -Combat:$combatReads",
                     "$exp += 'combat'", "$exp += 'target'", "$exp += 'los'", "$smp['combat_ocr']", "$smp['combat_isid']",
                     "$c = Npc-Capture (@(\"GetIsID $npc\") + $combatCmds) @('isid') 'npc_combat'",
                     "$o['combat_isid'] = $c.isid; $o['combat'] = $c.combat; $o['target'] = $c.target; $o['los'] = $c.los"):
            self.assertIn(need, block, need)
        # only after the position capture confirmed the selection (inside its isid -eq 1 branch, console still open)
        sel = block[block.index("function Select-Npc"):block.index("# 1. travel")]
        self.assertLess(sel.index("if ($r -and $r.isid -eq 1)"), sel.index("if ($Combat) {"))
        self.assertLess(sel.index("if ($Combat) {"), sel.index("Send 'key:grave|wait:600'"))
        # validated before anything is typed: a bool, methods none / combat_player only
        self.assertIn('"bad combat_reads"; exit 4', block)
        self.assertIn("@('none', 'combat_player') -cnotcontains", block)
        self.assertEqual(tuple(sorted(tq.NPC_COMBAT_METHODS)), ("combat_player", "none"))
        # the session's own ids go to the parser, so neither is ever read as the target
        self.assertIn("$exp += 'isid'; $typed += $Matches[1]", block)
        # the combat replies never decide whether the position session counts (isid and the position do)
        self.assertIn("'getpos x', 'getpos y', 'getpos z') @('isid', 'pos')", sel)


if __name__ == "__main__":
    unittest.main()
