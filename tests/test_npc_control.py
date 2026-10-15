"""scripts/actors/npc_control.py (the N0b control plan, the wander table, the N1 / N2 plans derived from earlier ones)
and the judge they need in testqueue.py (plan keys precommand_m / arrive_progress, runner feature npc_t0): N0's own
reads (2026-10-12, numbers only) judged by the old rule and by N0b's, the verifier's pre-command drift cases of PR #77,
walks and wanders on the N0b pair, the control gate with N0b as the control queue. Synthetic data only."""
import json
import math
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "actors"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import npc_control as nc  # noqa: E402
import runner_features  # noqa: E402
import testqueue as tq  # noqa: E402

OLD = {"travel": "coc QASmoke", "a": [-8, -4, 0], "b": [5, 10, 0], "drop": 0.5, "settle_ms": 1500,
       "reads_s": [0, 3, 8, 15, 30], "radius": 2.5, "min_progress": 5.0}               # npc_nav_n0's plan values
# what qstep.ps1 read in npc_nav_n0 (tests/<id>/a1/obs.json): spawn read, t0 read, then the reads at 3 / 8 / 15 / 30 s
N0_READS = {
    "N0_base": ("none", "-7.83 -5.28 0.00", "-7.83 -5.28 0.00",
                ["-7.83 -5.28 0.00", "-8.28 -4.46 0.00", "-10.37 -0.68 0.00", "0.02 -3.72 0.00"]),
    "N0_ptr": ("ptr_player", "-8.45 -5.54 0.00", "-8.45 -5.54 0.00",
               ["-11.43 -0.36 0.00", "-6.89 -2.44 0.00", "-3.14 -1.03 0.00", "-3.14 -1.03 0.00"]),
    "N0_cf": ("cf_pathto_player", "-7.78 -5.31 0.00", "-4.36 -2.46 0.00",
              ["-3.37 -1.48 0.00", "-10.39 -6.11 0.00", "-0.09 -3.05 0.00", "-0.08 -3.05 0.00"]),
    "N0_follow": ("follow_player", "-7.44 -5.68 0.00", "-7.44 -5.68 0.00", ["-7.44 -5.68 0.00"] * 4),
    "N0_ptr_lvl": ("ptr_player", "-7.62 -5.25 0.00", "-7.62 -5.25 0.00",
                   ["-2.45 -1.85 0.00", "-2.45 -1.85 0.00", "-7.27 -0.70 0.00", "-2.26 1.96 0.00"]),
}
# navmesh_points.py analyze on QASmoke (2026-10-12, version 2): the chosen pair
CHOSEN = {"a": [5.5, -4.5, 0.0], "b": [-12.0, 12.0, -0.0], "distance": 24.052, "segment_clearance": 2.844,
          "segment_clearance_exact": 2.82, "a_clearance_exact": 3.042, "b_clearance_exact": 2.82,
          "drift_progress": 11.679, "drift_to": [-11.43, -0.36], "b_from_trace": 12.373, "b_from_arrival": 15.671,
          "a_from_arrival": 9.527, "attractor_progress": 8.381, "a_clearance": 3.008, "b_clearance": 2.844,
          "free_path_ratio": 1.0}
PAIR18 = {"a": [-12.0, 12.0, 0.0], "b": [6.0, 12.0, 0.0]}            # the first N0b plan's pair (PR #77 as reviewed)


def touch(d, name):
    open(os.path.join(d, name), "wb").close()
    return name


def obs_of(d, spawn, t0, reads, player_b, times):
    return {"spawn": {"ref": "FF010CD0", "self": "FF010CD0", "isid": 1, "read": spawn, "confirmed": True, "why": ""},
            "t0": {"isid": 1, "read": t0, "via": "prid"}, "command_sent": True, "player_b": player_b,
            "samples": [{"t_game": t, "isid": 1, "read": r, "shot": touch(d, f"npc{k}.png")}
                        for k, (t, r) in enumerate(zip(times, reads))]}


def along(a, b, metres, side=0.0):
    """Points metres from a towards b (and side metres to the left of that line), as getpos reads."""
    d = math.dist(a[:2], b[:2])
    ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
    return [f"{a[0] + ux * m - uy * side:.2f} {a[1] + uy * m + ux * side:.2f} 0.00" for m in metres]


def points_file(d, chosen=CHOSEN):
    p = os.path.join(d, "points.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"chosen": chosen, "old_pair": {"segment_clearance": 3.821, "segment_clearance_exact": 3.845,
                                                  "drift_progress": 8.516}}, f)
    return p


def rule_keys(rule):
    return {k: rule[k] for k in ("radius", "min_progress", "arrive_progress", "precommand_m")}


class RuleTests(unittest.TestCase):
    def test_p_is_the_pair_less_six_metres(self):
        self.assertEqual(rule_keys(nc.rule_for(CHOSEN["a"], CHOSEN["b"])),
                         {"radius": 3.0, "min_progress": 18.0, "arrive_progress": 18.0, "precommand_m": 3.0})
        self.assertEqual(nc.rule_for([-985, 1139, 0], [-972, 1153, 0])["min_progress"], 13.0)    # N1's 19.1 m pair
        self.assertEqual(nc.rule_for([-988, 1162, 0], [-1003, 1153, 0])["min_progress"], 11.0)   # 17.5 m
        self.assertEqual(nc.rule_for(PAIR18["a"], PAIR18["b"])["min_progress"], 12.0)
        with self.assertRaises(SystemExit):
            nc.rule_for([0, 0, 0], [15, 0, 0])                                                    # P 9 m


class N0UnderTheN0bRule(unittest.TestCase):
    """N0's measured reads: the old rule passed two commands that did nothing visible; N0b's rule does not, and it
    does not judge N0_cf, whose citizen came 4.4 m towards the player before the command."""

    def setUp(self):
        self.d = tempfile.mkdtemp()

    def verdicts(self, rule):
        out = {}
        for label, (method, spawn, t0, reads) in N0_READS.items():
            w = dict(OLD, label=label, npc="002B211C", method=method, control=method != "none", **rule)
            t = tq.npc_test(0, w)
            out[label] = tq.judge(t, obs_of(self.d, spawn, t0, reads, "5.00 10.00 0.00", [3, 8, 15, 30]), self.d)[:2]
        return out

    def test_old_rule_reproduces_the_n0_report(self):
        self.assertEqual(self.verdicts({}), {
            "N0_base": ("FAIL", "WANDER"), "N0_ptr": ("PASS", "PASS"), "N0_cf": ("FAIL", "STALLED"),
            "N0_follow": ("FAIL", "NONAV"), "N0_ptr_lvl": ("PASS", "PASS")})

    def test_n0b_rule_reads_them_as_wander(self):
        rule = rule_keys(nc.rule_for(OLD["a"], OLD["b"]))                  # 19.1 m: P 13 m
        self.assertEqual(self.verdicts(rule), {
            "N0_base": ("PASS", "PASS"), "N0_ptr": ("FAIL", "STALLED"), "N0_cf": ("INCONCLUSIVE", "PRECOMMAND"),
            "N0_follow": ("FAIL", "NONAV"), "N0_ptr_lvl": ("FAIL", "STALLED")})


class PreCommandDriftTests(unittest.TestCase):
    """The blocking finding on PR #77: with min_progress 12 the integration-1012 judge's pre-command guard is 12 m and
    an arrival counts whatever came before the command. Every case of the finding, judged both ways."""

    def setUp(self):
        self.d = tempfile.mkdtemp()

    def judge(self, pair, rule, method, spawn_m, t0_m, after_m, side=0.0):
        a, b = pair["a"], pair["b"]
        w = dict(label="x", npc=nc.CITIZEN, travel="coc QASmoke", a=a, b=b, method=method, reads_s=nc.READS,
                 control=method != "none", **rule)
        t = tq.npc_test(0, w)
        pb = f"{b[0]:.2f} {b[1]:.2f} 0.00"
        o = obs_of(self.d, along(a, b, [spawn_m])[0], along(a, b, [t0_m], side)[0], along(a, b, after_m, side), pb,
                   [1, 3, 8, 15, 30])
        return tq.judge(t, o, self.d)

    def test_the_verifiers_case_passed_before_and_is_precommand_now(self):
        # spawn (-11.2, 12), 11.5 m towards B before t0, 3.5 m after the command (the finding's numbers, 18 m pair)
        old = {"radius": 3.0, "min_progress": 12.0}
        after = [12.8, 13.5, 14.2, 14.9, 15.8]
        v, cls, detail = self.judge(PAIR18, old, "ptr_player", 0.8, 12.3, after)
        self.assertEqual((v, cls), ("PASS", "PASS"), detail)                # the integration-1012 judge
        self.assertIn("moved 3.5 m", detail)
        new = rule_keys(nc.rule_for(PAIR18["a"], PAIR18["b"]))
        v, cls, detail = self.judge(PAIR18, new, "ptr_player", 0.8, 12.3, after)
        self.assertEqual((v, cls), ("INCONCLUSIVE", "PRECOMMAND"), detail)
        self.assertIn("limit 3 m", detail)
        # N1c_ptr_player's 9.5 m before the command, then N0_base's 8 m, both pointed at the player: passed too
        self.assertEqual(self.judge(PAIR18, old, "ptr_player", 0.8, 10.3, [12, 14, 16, 18.3, 18.3])[:2],
                         ("PASS", "PASS"))
        self.assertEqual(self.judge(PAIR18, new, "ptr_player", 0.8, 10.3, [12, 14, 16, 18.3, 18.3])[:2],
                         ("INCONCLUSIVE", "PRECOMMAND"))
        # N0_cf's 4.45 m, then N0_ptr_lvl's 9.0 m: 3.8 m from the player, 0.8 m short of a PASS even then
        v, cls, detail = self.judge(PAIR18, old, "ptr_player", 0.8, 5.25, [7, 9, 11, 14.25, 14.25])
        self.assertEqual((v, cls), ("FAIL", "STALLED"), detail)
        self.assertIn("min d 3.8 m", detail)

    def test_recorded_approaches_plus_recorded_wander_never_pass_on_the_n0b_pair(self):
        rule = rule_keys(nc.rule_for(CHOSEN["a"], CHOSEN["b"]))
        for method in ("ptr_player", "combat_player"):
            # N1c_ptr_player's 9.5 m before t0, then N0_base's 8 m, all of it towards B
            v, cls, d = self.judge(CHOSEN, rule, method, 0.8, 10.3, [12, 14, 16, 18.3, 18.3])
            self.assertEqual((v, cls), ("INCONCLUSIVE", "PRECOMMAND"), d)
            # N0_cf's 4.4 m before t0, then N0_ptr_lvl's 9.0 m
            v, cls, d = self.judge(CHOSEN, rule, method, 0.8, 5.2, [7, 9, 11, 14.2, 14.2])
            self.assertEqual((v, cls), ("INCONCLUSIVE", "PRECOMMAND"), d)
            # no approach before t0, then the largest move from t0 on record (N1c_cross_ptr, 14.1 m) towards B
            v, cls, d = self.judge(CHOSEN, rule, method, 0.8, 0.8, [3, 7, 11, 14.9, 14.9])
            self.assertEqual((v, cls), ("FAIL", "STALLED"), d)
        v, cls, d = self.judge(CHOSEN, rule, "none", 0.8, 0.8, [3, 7, 11, 14.9, 14.9])
        self.assertEqual((v, cls), ("PASS", "PASS"), d)                    # 14.1 m < 18 m: stayed away
        self.assertIn("largest approach 14.1 m", d)

    def test_a_walk_passes_from_t0_and_a_short_one_is_inconclusive(self):
        rule = rule_keys(nc.rule_for(CHOSEN["a"], CHOSEN["b"]))
        v, cls, d = self.judge(CHOSEN, rule, "ptr_player", 0.8, 0.8, [2.5, 6, 13, 21.5, 22.5])
        self.assertEqual((v, cls), ("PASS", "PASS"), d)
        self.assertIn("closer than at t0", d)
        # 2.9 m before t0 (under the 3 m limit), then to 3.0 m from the player: 17.4 m from t0, short of 18
        v, cls, d = self.judge(CHOSEN, rule, "ptr_player", 0.8, 3.7, [5, 9, 15, 21.05, 21.05])
        self.assertEqual((v, cls), ("INCONCLUSIVE", "SHORT"), d)
        # stopped 4.5 m short of the player, 18.3 m from t0: the progress rule
        v, cls, d = self.judge(CHOSEN, rule, "combat_player", 0.8, 0.8, [3, 8, 14, 19.1, 19.1])
        self.assertEqual((v, cls), ("PASS", "PASS"), d)
        self.assertIn("walked 18.3 m", d)

    def test_a_baseline_wander_counts_between_any_two_reads(self):
        rule = rule_keys(nc.rule_for(CHOSEN["a"], CHOSEN["b"]))
        # out and back after t0: 18.5 m towards B at 15 s, back to 5 m at 30 s (the old rule saw 4.2 m: PASS)
        v, cls, d = self.judge(CHOSEN, rule, "none", 0.8, 0.8, [3, 9, 15, 19.3, 5])
        self.assertEqual((v, cls), ("FAIL", "WANDER"), d)
        old = {"radius": 3.0, "min_progress": 18.0}
        self.assertEqual(self.judge(CHOSEN, old, "none", 0.8, 0.8, [3, 9, 15, 19.3, 5])[:2], ("PASS", "PASS"))
        # 9 m before t0 and 9.5 m after it: 18.5 m from the spawn read
        v, cls, d = self.judge(CHOSEN, rule, "none", 0.8, 9.8, [12, 15, 17, 19.3, 19.3])
        self.assertEqual((v, cls), ("FAIL", "WANDER"), d)
        # N1c_ptr_player's 9.5 m approach, then away: stays a PASS
        v, cls, d = self.judge(CHOSEN, rule, "none", 0.8, 10.3, [8, 5, 3, 2, 2])
        self.assertEqual((v, cls), ("PASS", "PASS"), d)

    def test_without_the_new_keys_the_judge_is_unchanged(self):
        # the integration-1012 semantics for every queue planned before: precommand at min_progress, no SHORT
        old = {"radius": 3.0, "min_progress": 12.0}
        v, cls, _ = self.judge(PAIR18, old, "ptr_player", 0.8, 5.0, [8, 11, 14, 15.5, 15.5])     # 4.2 m before t0
        self.assertEqual((v, cls), ("PASS", "PASS"))
        t = tq.npc_test(0, dict(label="x", npc=nc.CITIZEN, travel="coc QASmoke", a=PAIR18["a"], b=PAIR18["b"],
                                **old))
        self.assertNotIn("precommand_m", t)
        self.assertNotIn("arrive_progress", t)
        self.assertEqual(runner_features.needs([t]), [])


class RunnerFeatureTests(unittest.TestCase):
    def test_the_new_keys_need_npc_t0(self):
        self.assertEqual(runner_features.needs([{"precommand_m": 3.0}]), ["npc_t0"])
        self.assertEqual(runner_features.needs([{"arrive_progress": 0.0}]), ["npc_t0"])
        self.assertEqual(runner_features.missing(["npc_t0"]), [])           # this checkout has it
        self.assertEqual(runner_features.main(["check", "npc_t0,light"]), 0)
        self.assertEqual(runner_features.main(["check", "npc_t0,teleport9"]), 5)
        for bad in ({"precommand_m": 0}, {"precommand_m": "x"}, {"arrive_progress": -1}):
            with self.assertRaises(SystemExit, msg=str(bad)):
                tq.npc_test(0, dict(label="x", npc=nc.CITIZEN, travel="coc QASmoke", a=[0, 0, 0], b=[20, 0, 0],
                                    **bad))


class N0bPlanTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.tests = nc.n0b_tests(CHOSEN["a"], CHOSEN["b"], CHOSEN)

    def test_plan_shape_and_runner_validation(self):
        by = {w["label"]: w for w in self.tests}
        self.assertEqual(sorted(by), ["N0b_base", "N0b_base2", "N0b_combat", "N0b_ptr", "N0b_spacer_base"])
        self.assertEqual(sorted((w["npc"], w["method"]) for w in self.tests),
                         sorted([(nc.CITIZEN, "none"), (nc.CITIZEN, "none"), (nc.CITIZEN, "ptr_player"),
                                 (nc.CITIZEN, "combat_player"), (nc.SPACER, "none")]))
        for w in self.tests:
            self.assertEqual((w["a"], w["b"], w["travel"]), (CHOSEN["a"], CHOSEN["b"], "coc QASmoke"))
            self.assertEqual(rule_keys(w), rule_keys(nc.rule_for(CHOSEN["a"], CHOSEN["b"])))
            self.assertEqual(w["reads_s"], [0, 1, 3, 8, 15, 30])
            self.assertEqual(w["control"], w["method"] != "none")
            self.assertEqual(w.get("handle_tol"), 3.0 if w["npc"] == nc.SPACER else None)
            self.assertTrue(w["expect"] and w["basis"])
        self.assertEqual(by["N0b_ptr"]["expect"], "FAIL STALLED")
        planned = nc.check(self.tests)                      # testqueue.npc_test accepts every key and value
        self.assertEqual(sum(t["baseline"] for t in planned), 3)

    def test_cli_writes_plan_and_readme_and_plan_npc_takes_it(self):
        out = os.path.join(self.d, "n0b")
        nc.main(["n0b", "--points", points_file(self.d), "--out", out])
        with open(os.path.join(out, "plan.json"), encoding="utf-8") as f:
            plan = json.load(f)
        self.assertEqual([w["b"] for w in plan], [[-12.0, 12.0, 0.0]] * 5)       # -0.0 written as 0.0
        with open(os.path.join(out, "README.txt"), encoding="utf-8") as f:
            readme = f.read()
        for s in ("10.8 m", "5.4 m", "No script named Actor", "plan-npc", "npc_nav_n0b", "--fresh", "npc_t0",
                  "P = 18 m", "INCONCLUSIVE SHORT", "2.82 m (exact"):
            self.assertIn(s, readme)
        touch(self.d, "FO4Port.esm")
        q = os.path.join(self.d, "q")
        tq.main(["plan-npc", "--staging", self.d, "--exp-dir", out, "--out", q, "--fresh"])
        with open(os.path.join(q, "queue.json"), encoding="utf-8") as f:
            qq = json.load(f)
        self.assertEqual([t["ref"] for t in qq["tests"]][:3], ["N0b_base", "N0b_base2", "N0b_spacer_base"])
        self.assertTrue(all(t["fresh"] for t in qq["tests"]))
        self.assertEqual(qq["tests"][0]["precommand_m"], 3.0)
        self.assertEqual(qq["tests"][0]["arrive_progress"], 18.0)
        # an older runner refuses the queue: "needs" and the runner's own feature check before the launch
        self.assertEqual(qq["needs"], ["npc_t0"])
        self.assertEqual(qq["pre_launch"][1:], [os.path.join("scripts", "game", "runner_features.py"), "check",
                                                "npc_t0"])

    def test_no_chosen_pair_stops(self):
        with self.assertRaises(SystemExit):
            nc.main(["n0b", "--points", points_file(self.d, chosen=None), "--out", os.path.join(self.d, "x")])


def write_obs(qdir, tid, att, obs):
    d = os.path.join(qdir, "tests", tid, att)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "obs.json"), "w", encoding="utf-8") as f:
        json.dump(obs, f)


class WanderTests(unittest.TestCase):
    def test_rows_and_largest(self):
        q = tempfile.mkdtemp()
        tests = [{"id": "0000_npc_nav_X_base", "kind": "npc_nav", "ref": "X_base", "npc": nc.CITIZEN, "method": "none"},
                 {"id": "0001_npc_nav_X_ptr", "kind": "npc_nav", "ref": "X_ptr", "npc": nc.CITIZEN,
                  "method": "ptr_player"},
                 {"id": "0002_npc_nav_X_lost", "kind": "npc_nav", "ref": "X_lost", "npc": nc.CITIZEN,
                  "method": "ptr_player"}]
        with open(os.path.join(q, "queue.json"), "w", encoding="utf-8") as f:
            json.dump({"tests": tests}, f)
        pb = "20.00 0.00 0.00"

        def obs(spawn, t0, reads):
            return {"spawn": {"isid": 1, "confirmed": True, "read": spawn}, "t0": {"read": t0}, "player_b": pb,
                    "samples": [{"isid": 1, "read": r} for r in reads] + [{"isid": 0, "read": "19.00 0.00 0.00"}]}
        # 2 m towards the player before t0, then 5 m sideways, then 8 m back towards it
        write_obs(q, tests[0]["id"], "a1", obs("0.00 0.00 0.00", "2.00 0.00 0.00",
                                               ["2.00 5.00 0.00", "10.00 5.00 0.00"]))
        # a run whose spawn was not confirmed is no evidence
        o = obs("0.00 0.00 0.00", "0.00 0.00 0.00", ["15.00 0.00 0.00"])
        o["spawn"]["confirmed"] = False
        write_obs(q, tests[2]["id"], "a1", o)
        write_obs(q, tests[1]["id"], "a2", obs("0.00 0.00 0.00", "0.00 0.00 0.00", ["-3.00 4.00 0.00"]))
        rows = nc.wander_rows([q])
        name = os.path.basename(q)
        self.assertEqual([r["run"] for r in rows], [f"{name}/X_base/a1", f"{name}/X_ptr/a2"])
        r = rows[0]
        self.assertEqual((r["early"], r["pre_moved"], r["reads"]), (2.0, 2.0, 2))
        self.assertAlmostEqual(r["approach_t0"], 18.0 - math.hypot(10, 5), places=2)
        self.assertAlmostEqual(r["approach_any"], 20.0 - math.hypot(10, 5), places=2)
        self.assertAlmostEqual(r["moved_t0"], math.hypot(8, 5), places=2)
        self.assertEqual(rows[1]["moved_t0"], 5.0)
        self.assertEqual(rows[1]["approach_t0"], -round(math.hypot(23, 4) - 20, 2))
        s = nc.wander_summary(rows)
        self.assertEqual(s["moved_t0"], [round(math.hypot(8, 5), 2), rows[0]["run"]])
        table = nc.wander_table(rows, 18.0)
        self.assertIn("margin to 18 m", table)
        out = os.path.join(q, "w.json")
        nc.main(["wander", "--queue", q, "--out", out])
        with open(out, encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)["rows"]), 2)


class DeriveTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        base = {"travel": "coc FO4CW_RedRocketSpawn", "npc": "002B211C", "a": [-985.0, 1139.0, 105.0293],
                "b": [-972.0, 1153.0, 105.0293], "drop": 30, "settle_ms": 7000, "reads_s": [0, 3, 8, 15, 30],
                "radius": 2.5, "min_progress": 5.0, "control": False, "fresh": True,
                "anchor": {"ref": "02000800", "local": [-989.0286, 1147.2, 105.1434]},
                "spawn_local": [-989.0286, 1147.2, 105.2609],
                "requires": {"queue": os.path.join(self.d, "terrain_exp2d"), "test": "0000_terrain_X",
                             "verdict": "PASS"},
                "expect": "PASS", "basis": "converted navmesh"}
        self.n1 = [dict(base, label="N1c_ptr_player", method="ptr_player"),
                   dict(base, label="N1c_cf_pathto_player", method="cf_pathto_player"),
                   dict(base, label="N1c_follow_player", method="follow_player"),
                   dict(base, label="N1c_cross_ptr", method="ptr_player", a=[-988.0, 1162.0, 105.0293],
                        b=[-1003.0, 1153.0, 105.3718])]
        qs = {"travel": "coc QASmoke", "a": [-8, -4, 0], "b": [5, 10, 0], "drop": 0.5, "settle_ms": 1500,
              "reads_s": [0, 3, 8, 15, 30], "radius": 2.5, "min_progress": 5.0, "control": False, "expect": "PASS",
              "basis": "calm probe"}
        req = {"test": "N2a_base", "verdict": "DECIDED"}
        self.n2a = [dict(qs, label="N2a_base", npc="02F04801", method="none"),
                    dict(qs, label="N2a_ptr", npc="02F04801", method="ptr_player", control_npc="002B211C",
                         requires=req),
                    dict(qs, label="N2a_cf", npc="02F04801", method="cf_pathto_player", control_npc="002B211C",
                         requires=req),
                    dict(qs, label="N2a_follow", npc="02F04801", method="follow_player", control_npc="002B211C",
                         requires=req)]
        self.old_n2a_q = os.path.join(self.d, "npc_nav_n2a")
        self.n2b = [dict(qs, label="N2b_spacer_base", npc="00270255", method="none", handle_tol=3.0),
                    dict(qs, label="N2b_base", npc="02F04800", method="none", handle_tol=3.0,
                         requires=dict(req, queue=self.old_n2a_q))]
        self.n0b = nc.n0b_tests(CHOSEN["a"], CHOSEN["b"], CHOSEN)

    def test_n1_keeps_ptr_and_adds_a_baseline_with_the_rule_of_its_own_pair(self):
        out, notes = nc.derive(self.n1)
        self.assertEqual([(w["label"], w["method"]) for w in out],
                         [("N1c_base", "none"), ("N1c_ptr_player", "ptr_player"), ("N1c_cross_ptr", "ptr_player")])
        for w in out:
            self.assertEqual(w["requires"]["queue"], os.path.join(self.d, "terrain_exp2d"))   # world check kept
            self.assertEqual(w["anchor"]["ref"], "02000800")
            self.assertEqual((w["radius"], w["precommand_m"], w["reads_s"]), (3.0, 3.0, [0, 1, 3, 8, 15, 30]))
        self.assertEqual([w["min_progress"] for w in out], [13.0, 13.0, 11.0])                  # 19.1 / 17.5 m
        self.assertEqual([w["arrive_progress"] for w in out], [13.0, 13.0, 11.0])
        base = out[0]
        self.assertFalse(base["control"])
        self.assertEqual((base["a"], base["b"]), (self.n1[0]["a"], self.n1[0]["b"]))          # the main pair only
        self.assertEqual(out[2]["a"], [-988.0, 1162.0, 105.0293])                              # cross pair untouched
        self.assertEqual(len([n for n in notes if n.startswith("dropped")]), 2)
        self.assertIn("npc_nav_n0b", out[1]["basis"])
        self.assertIn("conditional: queue this plan only once `npc_control.py ready`", out[1]["basis"])
        self.assertNotIn("conditional", base["basis"])
        self.assertIn("does not open or close the FAIL gate", base["basis"])
        nc.check(out)
        self.assertEqual(nc.derive(self.n1)[0], out)                                           # deterministic

    def test_twins_only_when_asked(self):
        out, notes = nc.derive(self.n1, twins=("combat_player",))
        self.assertEqual([w["label"] for w in out],
                         ["N1c_base", "N1c_ptr_player", "N1c_combat_player", "N1c_cross_ptr"])
        self.assertIn("unresolved", out[2]["expect"])
        self.assertIn("added N1c_combat_player (combat_player twin of N1c_ptr_player)", notes)

    def test_n2a_moves_to_the_n0b_pair_and_keeps_its_gates(self):
        out, _ = nc.derive(self.n2a, pair=(CHOSEN["a"], CHOSEN["b"]))
        by = {w["label"]: w for w in out}
        self.assertEqual(sorted(by), ["N2a_base", "N2a_ptr"])
        for w in out:
            self.assertEqual((w["a"], w["b"]), (CHOSEN["a"], CHOSEN["b"]))
            self.assertEqual(w["min_progress"], 18.0)
        self.assertEqual(by["N2a_ptr"]["control_npc"], "002B211C")
        self.assertEqual(by["N2a_ptr"]["requires"], {"test": "N2a_base", "verdict": "DECIDED"})
        self.assertIn("control of 002B211C", by["N2a_ptr"]["basis"])
        self.assertNotIn("control_npc", by["N2a_base"])
        nc.check(out)

    def test_n2b_follows_the_new_n2a_queue_and_drops_the_repeat_of_n0b(self):
        new_q = os.path.join(self.d, "npc_nav_n2a_b")
        out, notes = nc.derive(self.n2b, pair=(CHOSEN["a"], CHOSEN["b"]), map_queue={self.old_n2a_q: new_q},
                               control_tests=self.n0b)
        self.assertEqual([w["label"] for w in out], ["N2b_base"])
        self.assertEqual(out[0]["requires"]["queue"], new_q)
        self.assertEqual(out[0]["handle_tol"], 3.0)
        self.assertIn("dropped N2b_spacer_base: the same actor, method, cell and points as N0b_spacer_base", notes[0])
        self.assertEqual(notes[1], f"moved to the N0b pair A {CHOSEN['a']} -> B {CHOSEN['b']}: N2b_base")
        readme = nc.derive_readme("old.json", self.d, notes, out)
        self.assertIn(f"{new_q} is planned", readme)
        self.assertNotIn("ready --plan", readme)                                 # nothing commanded to gate

    def test_plan_command_comes_from_the_old_queue(self):
        old = os.path.join(self.d, "npc_nav_n1c")
        os.makedirs(old)
        with open(os.path.join(old, "queue.json"), "w", encoding="utf-8") as f:
            json.dump({"staging": "S:\\staging\\integ", "control_queue": "Q:\\npc_nav_n0",
                       "pre_launch": ["py", "scripts\\game\\exp_install.py", "install", "--exp-dir", "S:\\exp2d",
                                      "--starfield", "G:\\Starfield", "--plugins", "A.esm,B.esm", "--pack"],
                       "tests": [{"fresh": True}, {"fresh": True}]}, f)
        cmd = nc.plan_command("S:\\npc_nav_n1c_b", old, "Q:\\npc_nav_n1c_b", "Q:\\npc_nav_n0b")
        self.assertIn("--staging S:\\staging\\integ --exp-dir S:\\npc_nav_n1c_b --out Q:\\npc_nav_n1c_b", cmd)
        self.assertIn("--install-exp S:\\exp2d --plugins A.esm,B.esm --control-queue Q:\\npc_nav_n0b --fresh", cmd)
        out, notes = nc.derive(self.n1)
        readme = nc.derive_readme("old.json", "S:\\npc_nav_n1c_b", notes, out, cmd, "Q:\\npc_nav_n0b")
        self.assertIn("ready --plan", readme)
        self.assertIn("19.1 m pair, P = 13 m", readme)


class GateTests(unittest.TestCase):
    """The control gate with N0b as the control queue: a control counts with the baselines of its own queue only."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        touch(self.d, "FO4Port.esm")
        exp0 = os.path.join(self.d, "s_n0b")
        nc.main(["n0b", "--points", points_file(self.d), "--out", exp0])
        self.q0 = os.path.join(self.d, "q_n0b")
        tq.main(["plan-npc", "--staging", self.d, "--exp-dir", exp0, "--out", self.q0])
        with open(os.path.join(self.q0, "queue.json"), encoding="utf-8") as f:
            self.ids0 = {t["ref"]: t["id"] for t in json.load(f)["tests"]}
        base = {"travel": "coc FO4CW_RedRocketSpawn", "npc": "002B211C", "a": [-985.0, 1139.0, 105.0],
                "b": [-972.0, 1153.0, 105.0], "control": False, "expect": "PASS", "basis": "x"}
        out, _ = nc.derive([dict(base, label="N1c_ptr_player", method="ptr_player"),
                            dict(base, label="N1c_cross_ptr", method="combat_player", b=[-1003.0, 1153.0, 105.0])],
                           twins=())
        exp1 = os.path.join(self.d, "s_n1c_b")
        os.makedirs(exp1)
        with open(os.path.join(exp1, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(out, f)
        self.q1 = os.path.join(self.d, "q_n1c_b")
        tq.main(["plan-npc", "--staging", self.d, "--exp-dir", exp1, "--out", self.q1, "--control-queue", self.q0])
        with open(os.path.join(self.q1, "queue.json"), encoding="utf-8") as f:
            self.q = json.load(f)
        self.by = {t["ref"]: t for t in self.q["tests"]}
        self.plan1 = out

    def state(self, qdir, done):
        with open(os.path.join(qdir, "state.json"), "w", encoding="utf-8") as f:
            json.dump({"done": done}, f)

    def n0b(self, **res):
        self.state(self.q0, {self.ids0[k]: {"verdict": v.split()[0], "class": v.split()[-1]} for k, v in res.items()})

    def gate(self, label="N1c_ptr_player"):
        return tq.control_gate(self.q1, self.q, self.by[label], "FAIL", "NONAV", "never moved")

    def test_fails_count_where_n0bs_control_and_both_baselines_passed(self):
        self.n0b(N0b_base="PASS PASS", N0b_base2="PASS PASS", N0b_ptr="PASS PASS", N0b_combat="FAIL STALLED")
        v, cls, detail = self.gate()
        self.assertEqual((v, cls), ("FAIL", "NONAV"), detail)
        self.assertIn("N0b_ptr", detail)
        self.assertEqual(self.gate("N1c_cross_ptr")[:2], ("INCONCLUSIVE", "CONTROL"))      # N0b_combat failed
        ok, lines = nc.ready(self.plan1, self.q0)
        self.assertFalse(ok)
        self.assertTrue(lines[0].startswith("N1c_ptr_player (ptr_player, gated by 002B211C): open"), lines[0])
        self.assertIn("closed", lines[1])

    def test_one_wandering_baseline_closes_the_gate(self):
        # N0b_base came on its own, N0b_base2 stayed away: the control's PASS may be wander
        self.n0b(N0b_base="FAIL WANDER", N0b_base2="PASS PASS", N0b_ptr="PASS PASS")
        v, cls, detail = self.gate()
        self.assertEqual((v, cls), ("INCONCLUSIVE", "CONTROL"), detail)
        self.assertIn("came to B without a command", detail)
        self.assertFalse(nc.ready([w for w in self.plan1 if w["label"] == "N1c_ptr_player"], self.q0)[0])

    def test_this_queues_own_baseline_neither_opens_nor_closes_the_gate(self):
        own = self.by["N1c_base"]["id"]
        self.n0b(N0b_base="FAIL WANDER", N0b_base2="FAIL WANDER", N0b_ptr="PASS PASS")
        self.state(self.q1, {own: {"verdict": "PASS", "class": "PASS"}})
        self.assertEqual(self.gate()[:2], ("INCONCLUSIVE", "CONTROL"))                    # was FAIL before
        self.n0b(N0b_base="PASS PASS", N0b_base2="PASS PASS", N0b_ptr="PASS PASS")
        self.state(self.q1, {own: {"verdict": "FAIL", "class": "WANDER"}})
        self.assertEqual(self.gate()[:2], ("FAIL", "NONAV"))
        self.assertTrue(nc.ready(self.plan1[:2], self.q0)[0])
        # a PASS here is not credited to the command when its own world's baseline came on its own
        _v, _c, detail = tq.control_gate(self.q1, self.q, self.by["N1c_ptr_player"], "PASS", "PASS", "walked")
        self.assertIn("not credited to the command", detail)

    def test_ready_cli(self):
        p = os.path.join(self.d, "s_n1c_b", "plan.json")
        self.assertEqual(nc.main(["ready", "--plan", p, "--control-queue", self.q0]), 4)      # no results yet
        self.n0b(N0b_base="PASS PASS", N0b_base2="PASS PASS", N0b_ptr="PASS PASS", N0b_combat="PASS PASS")
        self.assertEqual(nc.main(["ready", "--plan", p, "--control-queue", self.q0]), 0)


if __name__ == "__main__":
    unittest.main()
