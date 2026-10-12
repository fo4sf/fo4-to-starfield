"""scripts/actors/npc_control.py (the N0b control plan and the N1 / N2 plans derived from earlier ones) and what the N0b
rule does in testqueue.py's existing judge: N0's own reads (2026-10-12, numbers only) judged by the old rule and by
N0b's, walks and wanders on the N0b pair, the control gate with N0b as the control queue. Synthetic data only."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "actors"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import npc_control as nc  # noqa: E402
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
CHOSEN = {"a": [-12.0, 12.0, -0.0], "b": [6.0, 12.0, -0.0], "distance": 18.0, "segment_clearance": 2.833,
          "drift_progress": 5.318, "b_from_trace": 13.001, "b_from_arrival": 16.124, "a_from_arrival": 15.671,
          "attractor_progress": 1.876, "a_clearance": 2.844, "b_clearance": 2.833, "free_path_ratio": 1.0}


def touch(d, name):
    open(os.path.join(d, name), "wb").close()
    return name


def obs_of(d, spawn, t0, reads, player_b, times):
    return {"spawn": {"ref": "FF010CD0", "self": "FF010CD0", "isid": 1, "read": spawn, "confirmed": True, "why": ""},
            "t0": {"isid": 1, "read": t0, "via": "prid"}, "command_sent": True, "player_b": player_b,
            "samples": [{"t_game": t, "isid": 1, "read": r, "shot": touch(d, f"npc{k}.png")}
                        for k, (t, r) in enumerate(zip(times, reads))]}


def line(a, b, fractions, z=0.0):
    return [f"{a[0] + (b[0] - a[0]) * f:.2f} {a[1] + (b[1] - a[1]) * f:.2f} {z:.2f}" for f in fractions]


def points_file(d, chosen=CHOSEN):
    p = os.path.join(d, "points.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"chosen": chosen, "old_pair": {"segment_clearance": 3.821, "drift_progress": 8.516}}, f)
    return p


class N0UnderTheN0bRule(unittest.TestCase):
    """N0's measured reads: the old rule passed two commands that did nothing visible; N0b's rule does not."""

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
        rule = {k: nc.RULE[k] for k in ("radius", "min_progress")}
        self.assertEqual(self.verdicts(rule), {
            "N0_base": ("PASS", "PASS"), "N0_ptr": ("FAIL", "STALLED"), "N0_cf": ("FAIL", "STALLED"),
            "N0_follow": ("FAIL", "NONAV"), "N0_ptr_lvl": ("FAIL", "STALLED")})


class N0bPlanTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.tests = nc.n0b_tests(CHOSEN["a"], CHOSEN["b"], CHOSEN)

    def test_plan_shape_and_runner_validation(self):
        by = {w["label"]: w for w in self.tests}
        self.assertEqual(sorted(by), ["N0b_base", "N0b_combat", "N0b_ptr", "N0b_spacer_base", "N0b_spacer_combat",
                                      "N0b_spacer_ptr"])
        self.assertEqual({(w["npc"], w["method"]) for w in self.tests},
                         {(n, m) for n in (nc.CITIZEN, nc.SPACER) for m in ("none", "ptr_player", "combat_player")})
        for w in self.tests:
            self.assertEqual((w["a"], w["b"], w["travel"]), (CHOSEN["a"], CHOSEN["b"], "coc QASmoke"))
            self.assertEqual((w["radius"], w["min_progress"], w["reads_s"]), (3.0, 12.0, [0, 1, 3, 8, 15, 30]))
            self.assertEqual(w["control"], w["method"] != "none")
            self.assertEqual(w.get("handle_tol"), 3.0 if w["npc"] == nc.SPACER else None)
            self.assertTrue(w["expect"] and w["basis"])
        planned = nc.check(self.tests)                      # testqueue.npc_test accepts every key and value
        self.assertEqual(sum(t["baseline"] for t in planned), 2)

    def test_cli_writes_plan_and_readme_and_plan_npc_takes_it(self):
        out = os.path.join(self.d, "n0b")
        nc.main(["n0b", "--points", points_file(self.d), "--out", out])
        with open(os.path.join(out, "plan.json"), encoding="utf-8") as f:
            plan = json.load(f)
        self.assertEqual([w["a"] for w in plan], [[-12.0, 12.0, 0.0]] * 6)        # -0.0 written as 0.0
        with open(os.path.join(out, "README.txt"), encoding="utf-8") as f:
            readme = f.read()
        for s in ("10.8 m", "5.4 m", "No script named Actor", "plan-npc", "npc_nav_n0b", "--fresh"):
            self.assertIn(s, readme)
        touch(self.d, "FO4Port.esm")
        q = os.path.join(self.d, "q")
        tq.main(["plan-npc", "--staging", self.d, "--exp-dir", out, "--out", q, "--fresh"])
        with open(os.path.join(q, "queue.json"), encoding="utf-8") as f:
            qq = json.load(f)
        self.assertEqual([t["ref"] for t in qq["tests"]][:2], ["N0b_base", "N0b_spacer_base"])   # baselines first
        self.assertTrue(all(t["fresh"] for t in qq["tests"]))
        self.assertEqual((qq["tests"][0]["heading_a"], qq["tests"][0]["heading_b"]), (90.0, 270.0))
        self.assertNotIn("needs", qq)                       # nothing an integration-1012 runner lacks

    def test_no_chosen_pair_stops(self):
        with self.assertRaises(SystemExit):
            nc.main(["n0b", "--points", points_file(self.d, chosen=None), "--out", os.path.join(self.d, "x")])


class N0bJudgeTests(unittest.TestCase):
    """The N0b pair (18 m) under the N0b rule, judged by testqueue.py as it is."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.by = {w["label"]: w for w in nc.n0b_tests(CHOSEN["a"], CHOSEN["b"], CHOSEN)}
        self.times = [1, 3, 8, 15, 30]

    def judge(self, label, reads, t0=None):
        t = tq.npc_test(0, self.by[label])
        sp = "-11.20 12.00 0.00"                            # placeatme: 0.8 m from the player at A
        return tq.judge(t, obs_of(self.d, sp, t0 or sp, reads, "6.00 12.00 0.00", self.times), self.d)

    def test_a_walk_to_the_player_passes(self):
        a, b = (-11.2, 12.0), (6.0, 12.0)
        v, cls, detail = self.judge("N0b_ptr", line(a, b, [0.05, 0.2, 0.55, 0.9, 0.92]))
        self.assertEqual((v, cls), ("PASS", "PASS"), detail)
        self.assertIn("arrived within 3.0 m", detail)

    def test_stopping_at_weapon_range_passes_only_beyond_12_m(self):
        v, _c, detail = self.judge("N0b_spacer_combat", [f"{x:.2f} 12.00 0.00" for x in (-10, -6, -2, 1.0, 1.0)])
        self.assertEqual(v, "PASS", detail)                 # 17.2 -> 5.0 m from the player: 12.2 m closer
        self.assertIn("walked 12.2 m", detail)
        v, cls, detail = self.judge("N0b_spacer_combat", [f"{x:.2f} 12.00 0.00" for x in (-10, -6, -2, 0.5, 0.5)])
        self.assertEqual((v, cls), ("FAIL", "STALLED"), detail)   # 11.7 m closer, stopped 5.5 m short: not enough
        v, cls, detail = self.judge("N0b_spacer_combat", [f"{x:.2f} 12.00 0.00" for x in (-10, -6, -3, -3, -3)])
        self.assertEqual((v, cls), ("FAIL", "STALLED"), detail)

    def test_n0_like_drift_and_a_flight_do_not_pass(self):
        # N0's base pattern moved to this pair: the actor drifts 8 m towards the middle of the room
        drift = ["-10.50 10.00 0.00", "-8.00 7.00 0.00", "-5.00 5.00 0.00", "-3.10 3.00 0.00", "-3.10 3.00 0.00"]
        self.assertEqual(self.judge("N0b_base", drift)[:2], ("PASS", "PASS"))       # stayed away: < 12 m closer
        self.assertEqual(self.judge("N0b_ptr", drift)[:2], ("FAIL", "STALLED"))
        flee = ["-12.00 11.00 0.00", "-13.00 9.00 0.00", "-13.50 5.00 0.00", "-13.50 0.00 0.00", "-13.50 -5.00 0.00"]
        v, cls, detail = self.judge("N0b_combat", flee)
        self.assertEqual((v, cls), ("FAIL", "STALLED"), detail)
        self.assertIn("end d 25.9 m", detail)               # further from the player than at t0 (17.2 m)

    def test_a_hostile_baseline_that_comes_is_wander(self):
        v, cls, _ = self.judge("N0b_spacer_base", line((-11.2, 12.0), (6.0, 12.0), [0.2, 0.5, 0.8, 0.8, 0.8]))
        self.assertEqual((v, cls), ("FAIL", "WANDER"))


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

    def test_n1_keeps_ptr_adds_combat_and_a_baseline(self):
        out, notes = nc.derive(self.n1)
        self.assertEqual([(w["label"], w["method"]) for w in out],
                         [("N1c_base", "none"), ("N1c_ptr_player", "ptr_player"),
                          ("N1c_combat_player", "combat_player"), ("N1c_cross_ptr", "ptr_player")])
        for w in out:
            self.assertEqual((w["radius"], w["min_progress"], w["reads_s"]), (3.0, 12.0, [0, 1, 3, 8, 15, 30]))
            self.assertEqual(w["requires"]["queue"], os.path.join(self.d, "terrain_exp2d"))   # world check kept
            self.assertEqual(w["anchor"]["ref"], "02000800")
        base = out[0]
        self.assertFalse(base["control"])
        self.assertEqual((base["a"], base["b"]), (self.n1[0]["a"], self.n1[0]["b"]))          # the main pair only
        self.assertEqual(out[3]["a"], [-988.0, 1162.0, 105.0293])                              # cross pair untouched
        self.assertEqual(len([n for n in notes if n.startswith("dropped")]), 2)
        self.assertIn("unresolved", out[2]["expect"])
        self.assertIn("npc_nav_n0b", out[1]["basis"])
        nc.check(out)
        self.assertEqual(nc.derive(self.n1)[0], out)                                           # deterministic

    def test_n2a_moves_to_the_n0b_pair_and_keeps_its_gates(self):
        out, _ = nc.derive(self.n2a, pair=(CHOSEN["a"], CHOSEN["b"]))
        by = {w["label"]: w for w in out}
        self.assertEqual(sorted(by), ["N2a_base", "N2a_combat", "N2a_ptr"])
        for w in out:
            self.assertEqual((w["a"], w["b"]), (CHOSEN["a"], CHOSEN["b"]))
        self.assertEqual(by["N2a_combat"]["control_npc"], "002B211C")
        self.assertEqual(by["N2a_combat"]["requires"], {"test": "N2a_base", "verdict": "DECIDED"})
        self.assertIn("002B211C", by["N2a_combat"]["expect"])
        self.assertNotIn("control_npc", by["N2a_base"])
        nc.check(out)

    def test_n2b_requires_follows_the_new_n2a_queue(self):
        new_q = os.path.join(self.d, "npc_nav_n2a_b")
        out, notes = nc.derive(self.n2b, pair=(CHOSEN["a"], CHOSEN["b"]), map_queue={self.old_n2a_q: new_q})
        self.assertEqual([w["label"] for w in out], ["N2b_spacer_base", "N2b_base"])          # baselines only
        self.assertEqual(out[1]["requires"]["queue"], new_q)
        self.assertEqual(out[0]["handle_tol"], 3.0)
        self.assertEqual(len(notes), 2)                                                       # nothing dropped or added
        self.assertIn("moved to the N0b pair", notes[0])
        self.assertIn(new_q, notes[1])

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

    def test_end_to_end_gate_with_n0b_as_the_control_queue(self):
        """N1c_b's FAILs count where N0b's control (same method) and baseline passed, and stay INCONCLUSIVE CONTROL
        where N0b's control failed (the combat twin here)."""
        touch(self.d, "FO4Port.esm")
        exp0 = os.path.join(self.d, "s_n0b")
        nc.main(["n0b", "--points", points_file(self.d), "--out", exp0])
        q0 = os.path.join(self.d, "q_n0b")
        tq.main(["plan-npc", "--staging", self.d, "--exp-dir", exp0, "--out", q0])
        with open(os.path.join(q0, "queue.json"), encoding="utf-8") as f:
            ids = {t["ref"]: t["id"] for t in json.load(f)["tests"]}
        done = {ids["N0b_base"]: {"verdict": "PASS", "class": "PASS"},
                ids["N0b_ptr"]: {"verdict": "PASS", "class": "PASS"},
                ids["N0b_combat"]: {"verdict": "FAIL", "class": "STALLED"}}
        with open(os.path.join(q0, "state.json"), "w", encoding="utf-8") as f:
            json.dump({"done": done}, f)
        out, _ = nc.derive([dict(w, requires=None) for w in self.n1])
        tests = [dict(w) for w in out]
        for w in tests:
            w.pop("requires")
        exp1 = os.path.join(self.d, "s_n1c_b")
        os.makedirs(exp1)
        with open(os.path.join(exp1, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(tests, f)
        q1 = os.path.join(self.d, "q_n1c_b")
        tq.main(["plan-npc", "--staging", self.d, "--exp-dir", exp1, "--out", q1, "--control-queue", q0])
        with open(os.path.join(q1, "queue.json"), encoding="utf-8") as f:
            q = json.load(f)
        by = {t["ref"]: t for t in q["tests"]}
        v, cls, detail = tq.control_gate(q1, q, by["N1c_ptr_player"], "FAIL", "NONAV", "never moved")
        self.assertEqual((v, cls), ("FAIL", "NONAV"), detail)
        self.assertIn("N0b_ptr", detail)
        v, cls, detail = tq.control_gate(q1, q, by["N1c_combat_player"], "FAIL", "NONAV", "never moved")
        self.assertEqual((v, cls), ("INCONCLUSIVE", "CONTROL"), detail)


if __name__ == "__main__":
    unittest.main()
