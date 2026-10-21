"""scripts/game/campaign_arm.py: a chain of planned queues is armed only with the night-run caps, on the installed set,
away from held cells (synthetic queue folders; nothing launched)."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import campaign_arm as ca  # noqa: E402
import testqueue as tq  # noqa: E402

CAPS = {"max_attempts": 1, "max_relaunch": 1, "crash_budget": 1, "min_free_gb": 43, "dump_drive": "D:\\"}
PLUGINS = ["FO4TerrainCore.esm", "FO4TerrainCore_Mars.esm", "FO4ActorRaider.esm", "FO4SFMission.esm"]


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.staging = os.path.join(self.d, "integ_v6")
        os.makedirs(self.staging)
        with open(os.path.join(self.staging, "FO4Port.esm"), "wb") as f:
            f.write(b"port")
        self.exp = os.path.join(self.d, "v6e")

    def queue(self, name, tests, pre=None, **extra):
        q = os.path.join(self.d, name)
        os.makedirs(q)
        digest = tq.sha256(os.path.join(self.staging, "FO4Port.esm"))
        body = dict({"staging": self.staging, "plugin_sha256": digest, "build_id": digest[:8],
                     "tests": [dict(t, id=f"{i:04d}_t") for i, t in enumerate(tests)]}, **extra)
        if pre is not None:
            body["pre_launch"] = pre
        with open(os.path.join(q, "queue.json"), "w") as f:
            json.dump(body, f)
        return q

    def camp(self, queues, **over):
        c = {"name": "v6e", "checkout": "D:\\Modding\\wt_nightrun", "python": "C:\\py\\python.exe",
             "staging": self.staging, "installed_exp": self.exp, "installed_plugins": PLUGINS, "caps": dict(CAPS),
             "holds": {"red_rocket": ["FO4Core_RedRocketSpawn"]},
             "queues": [{"name": n, "queue": q} for n, q in queues]}
        c.update(over)
        return c

    def check(self, camp, release=()):
        res, ok = ca.check(camp, set(release))
        return ok, [w for _, why, _ in res["queues"] for w in why] + res["caps"]


class CheckTests(Base):
    def test_an_interior_queue_on_the_installed_set_is_armed(self):
        q = self.queue("doors_out", [{"coc": "FO4Port_Vault95", "travel": "coc FO4Port_Vault95"}])
        self.assertEqual(self.check(self.camp([("doors_out", q)])), (True, []))
        stairs = self.queue("stairs", [{"kind": "stairs", "cell": "BostonPublicLibrary02"}, {"kind": "walk", "cell": ""}])
        self.assertEqual(ca.cells(tq.load(os.path.join(stairs, "queue.json"))), ["BostonPublicLibrary02"])

    def test_a_red_rocket_start_is_held_until_released(self):
        q = self.queue("walk", [{"travel": "coc FO4Core_RedRocketSpawn"}])
        ok, why = self.check(self.camp([("walk", q)]))
        self.assertFalse(ok)
        self.assertIn("held (red_rocket)", why[0])
        self.assertEqual(self.check(self.camp([("walk", q)]), {"red_rocket"}), (True, []))
        ok, why = self.check(self.camp([("walk", q)]), {"sanctuary"})
        self.assertIn("does not have", why[-1])

    def test_only_the_installed_experiment_may_be_installed_before_launch(self):
        exp = [sys.executable, "scripts\\game\\exp_install.py", "install", "--exp-dir", self.exp, "--starfield", "D:\\SF",
               "--plugins", ",".join(PLUGINS), "--pack"]
        q = self.queue("walk", [{"coc": "FO4Port_X"}], pre=exp)
        self.assertEqual(self.check(self.camp([("walk", q)])), (True, []))
        other = list(exp)
        other[4] = os.path.join(self.d, "v6c")
        q2 = self.queue("walk2", [{"coc": "FO4Port_X"}], pre=other)
        fewer = list(exp)
        fewer[8] = "FO4TerrainCore.esm"
        q3 = self.queue("walk3", [{"coc": "FO4Port_X"}], pre=fewer)
        q4 = self.queue("walk4", [{"coc": "FO4Port_X"}], pre=[sys.executable, "scripts\\game\\bridge_install.py", "uninstall"])
        feat = self.queue("feat", [{"coc": "FO4Port_X"}], pre=[sys.executable, "scripts/game/runner_features.py", "check", "bridge"])
        for q, want in ((q2, "would install"), (q3, "would activate"), (q4, "not a runner check")):
            with self.subTest(q=q):
                ok, why = self.check(self.camp([("q", q)]))
                self.assertFalse(ok)
                self.assertIn(want, why[0])
        self.assertTrue(self.check(self.camp([("feat", feat)]))[0])

    def test_another_or_changed_build_is_refused(self):
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        with open(os.path.join(self.staging, "FO4Port.esm"), "wb") as f:
            f.write(b"rebuilt")
        self.assertIn("changed since the plan", self.check(self.camp([("a", q)]))[1][0])
        q2 = self.queue("b", [{"coc": "FO4Port_X"}], staging=os.path.join(self.d, "other"))
        self.assertIn("pins the staging", self.check(self.camp([("b", q2)]))[1][0])

    def test_the_caps_must_be_the_night_run_caps(self):
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        for change in ({"max_relaunch": 3}, {"crash_budget": 0}, {"min_free_gb": 25}, {"min_free_gb": float("nan")},
                       {"max_attempts": 5}, {"dump_drive": "D:\\dumps"}):
            with self.subTest(change=change):
                ok, why = self.check(self.camp([("a", q)], caps=dict(CAPS, **change)))
                self.assertFalse(ok)
                self.assertEqual(len(why), 1)

    def test_used_queues_bad_judges_and_missing_queues_are_refused(self):
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        with open(os.path.join(q, "state.json"), "w") as f:
            json.dump({"crashes": 0, "start_deaths": 1, "done": {}}, f)
        self.assertIn("dead start", self.check(self.camp([("a", q)]))[1][0])
        q2 = self.queue("b", [{"coc": "FO4Port_X"}])
        with open(os.path.join(q2, "state.json"), "w") as f:
            json.dump({"done": {"0000_t": {"verdict": "PASS"}}}, f)
        self.assertIn("already done", self.check(self.camp([("b", q2)]))[1][0])
        q3 = self.queue("c", [{"coc": "FO4Port_X"}])
        c = self.camp([("c", q3)])
        c["queues"][0]["judge"] = ["scripts/game/cycle.ps1"]
        self.assertIn("is not door_rounds.py judge", self.check(c)[1][0])
        c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", q3]
        self.assertTrue(self.check(c)[0])
        # Codex on #391: a judge of another queue folder (or of none, or of two) is refused
        q4 = self.queue("d", [{"coc": "FO4Port_X"}])
        for bad in (["--queue", q4], [], ["--queue", q3, "--queue", q4], ["--queue=" + q3], ["--queue"]):
            with self.subTest(bad=bad):
                c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge"] + bad
                self.assertIn("does not judge this queue", " ".join(self.check(c)[1]))
        c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", q3.upper() + "\\"]
        self.assertTrue(self.check(c)[0])                                   # the same folder, written otherwise
        self.assertIn("no planned queue", self.check(self.camp([("x", os.path.join(self.d, "nope"))]))[1][0])
        self.assertIn("no queues", self.check(self.camp([]))[1][0])
        self.assertIn("repeated", self.check(self.camp([("c", q3), ("c", q3)]))[1][-1])


    def test_a_queue_bridge_needs_the_campaign_bridge_and_holds_need_lists(self):
        # Codex on #391: a pinned bridge passed when the campaign named none; a hold written as a string held nothing
        q = self.queue("a", [{"coc": "FO4Core_RedRocketSpawn"}], bridge={"dir": "C:\\b\\bridge_t4"})
        ok, why = self.check(self.camp([("a", q)], holds={"red_rocket": "FO4Core_RedRocketSpawn"}))
        self.assertFalse(ok)
        self.assertTrue(any("campaign names no bridge" in w for w in why), why)
        self.assertTrue(any("is not a list of cell editor ids" in w for w in why), why)
        for bad in (["FO4Core_RedRocketSpawn", 3], ["coc X"], {"a": 1}):
            with self.subTest(bad=bad):
                self.assertIn("is not a list of cell editor ids", " ".join(self.check(self.camp([("a", q)],
                              bridge="C:\\b\\bridge_t4", holds={"red_rocket": bad}))[1]))


class PlanTerrainHoldTests(Base):
    def test_a_plan_terrain_door_in_leg_is_held(self):
        # review pass on #391: plan-terrain writes no "coc"; an IN leg starts at world_coc with an empty travel
        # (testqueue.py plan-terrain, door_rounds.py's IN leg), so the red_rocket hold never saw it
        q = self.queue("doors", [{"kind": "terrain", "cell": "", "ref": "FO4Core_RedRocketSpawn",
                                  "world_coc": "FO4Core_RedRocketSpawn", "travel": ""},
                                 {"kind": "terrain", "cell": "", "ref": "FO4Port_SuperDuperMart01",
                                  "world_coc": "FO4Port_SuperDuperMart01", "travel": "coc FO4Port_SuperDuperMart01"}])
        self.assertEqual(ca.cells(ca.tq.load(os.path.join(q, "queue.json"))),
                         ["FO4Core_RedRocketSpawn", "FO4Port_SuperDuperMart01"])
        ok, why = self.check(self.camp([("doors", q)]))
        self.assertFalse(ok)
        self.assertIn("FO4Core_RedRocketSpawn", " ".join(why))


class ScriptAndGateTests(Base):
    def test_the_chain_carries_the_caps_and_stops_on_the_gate(self):
        q = self.queue("doors_out", [{"coc": "FO4Port_Vault95"}])
        c = self.camp([("doors_out", q)])
        c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", q]
        cp, out = os.path.join(self.d, "c.json"), os.path.join(self.d, "chain.ps1")
        with open(cp, "w") as f:
            json.dump(c, f)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ca.main(["script", "--campaign", cp, "--out", out]), 0)
        with open(out, newline="") as f:
            text = f.read()
        self.assertIn("'--max-relaunch' '1' '--crash-budget' '1' '--min-free-gb' '43' '--dump-drive' 'D:\\'", text)
        self.assertIn("'scripts\\bridge\\door_rounds.py' 'judge'", text)
        self.assertIn("$jr = $LASTEXITCODE", text)                          # Codex on #391: the judge exit counts
        self.assertIn("--run-exit $rc --judge-exit $jr", text)
        self.assertLess(text.index("$jr = $LASTEXITCODE"), text.index("gate --queue"))
        self.assertLess(text.index("campaign_arm.py check"), text.index("testqueue.py"))
        self.assertLess(text.index("testqueue.py"), text.index("gate --queue"))
        self.assertIn("\r\n", text)
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()):      # a new file only
            ca.main(["script", "--campaign", cp, "--out", out])

    def test_a_refused_campaign_writes_no_chain(self):
        q = self.queue("walk", [{"coc": "FO4Core_RedRocketSpawn"}])
        cp, out = os.path.join(self.d, "c.json"), os.path.join(self.d, "chain.ps1")
        with open(cp, "w") as f:
            json.dump(self.camp([("walk", q)]), f)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ca.main(["script", "--campaign", cp, "--out", out]), 1)
        self.assertFalse(os.path.exists(out))

    def test_the_gate_passes_only_a_clean_finished_run(self):
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        with open(os.path.join(q, "state.json"), "w") as f:
            json.dump({"status": "finished", "crashes": 0, "start_deaths": 0}, f)
        self.assertTrue(ca.gate(q, 0)[0])
        self.assertFalse(ca.gate(q, 4)[0])                                     # paused: tests left
        with open(os.path.join(q, "state.json"), "w") as f:
            json.dump({"status": "finished", "crashes": 1}, f)                 # a crash in the last test
        self.assertFalse(ca.gate(q, 0)[0])

    def test_the_gate_refuses_a_missing_unfinished_or_torn_state_and_a_failed_judge(self):
        # Codex on #391: a missing state.json or a running one passed as "clean: None" / "clean: running"
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        sp = os.path.join(q, "state.json")

        def cli(*extra):
            with redirect_stdout(io.StringIO()) as buf:
                rc = ca.main(["gate", "--queue", q, "--run-exit", "0", *extra])
            return rc, buf.getvalue()
        self.assertEqual(cli(), (1, f"STOP no readable state.json in {q}: nothing proves the queue ran\n"))
        for st, why in (({"status": "running", "crashes": 0}, "'running', not finished"),
                        ({"status": "new"}, "'new', not finished"), (["finished"], "no readable state.json")):
            with self.subTest(st=st):
                with open(sp, "w") as f:
                    json.dump(st, f)
                rc, out = cli()
                self.assertEqual(rc, 1)
                self.assertIn(why, out)
        with open(sp, "w") as f:
            f.write('{"status": "fini')
        self.assertIn("no readable state.json", ca.gate(q, 0)[1])
        with open(sp, "w") as f:
            json.dump({"status": "finished", "crashes": 0, "start_deaths": 0}, f)
        self.assertEqual(cli(), (0, "OK ran clean: finished (the verdicts are in the judge's report)\n"))
        self.assertEqual(cli("--judge-exit", "0")[0], 0)
        self.assertEqual(cli("--judge-exit", "2"), (1, "STOP the judge exited 2\n"))


if __name__ == "__main__":
    unittest.main()


class RunChainTests(Base):
    def setUp(self):
        super().setUp()
        self.calls, self.lines = [], []

    def fake(self, codes, state=None):
        def call(argv, env):
            self.calls.append((argv[1:3], env.get("FO4SF_LAUNCH")))
            if state is not None and "testqueue.py" in argv[1]:
                q = argv[argv.index("--queue") + 1]
                with open(os.path.join(q, "state.json"), "w") as f:
                    json.dump(state, f)
            return codes.pop(0)
        return call

    def test_runs_each_queue_with_the_caps_and_stops_at_a_crash(self):
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        qb = self.queue("b", [{"coc": "FO4Port_Y"}])
        c = self.camp([("a", qa), ("b", qb)], launch="exe")
        c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", qa]
        rc = ca.run_chain(c, self.lines.append, self.fake([0, 0], {"status": "finished", "crashes": 1}))
        self.assertEqual(rc, 1)
        self.assertEqual([a for a, _ in self.calls], [[os.path.join("scripts", "game", "testqueue.py"), "run"],
                                                      [os.path.join("scripts", "bridge", "door_rounds.py"), "judge"]])
        self.assertEqual({e for _, e in self.calls}, {"exe"})
        self.assertIn("a: STOP", self.lines[-1])

    def test_a_failed_judge_stops_the_chain(self):
        # Codex on #391: a judge exit 2 was only logged; the next queue ran and the chain ended 0
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        qb = self.queue("b", [{"coc": "FO4Port_Y"}])
        c = self.camp([("a", qa), ("b", qb)])
        c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", qa]
        rc = ca.run_chain(c, self.lines.append, self.fake([0, 2], {"status": "finished", "crashes": 0}))
        self.assertEqual(rc, 1)
        self.assertEqual([a[1] for a, _ in self.calls], ["run", "judge"])          # b never started
        self.assertEqual(self.lines[-1], "a: STOP the judge exited 2")
        with open(os.path.join(qa, "state.json")) as f:                         # the run's evidence stays
            self.assertEqual(json.load(f)["status"], "finished")

    def test_a_run_that_wrote_no_state_stops_the_chain(self):
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        qb = self.queue("b", [{"coc": "FO4Port_Y"}])
        rc = ca.run_chain(self.camp([("a", qa), ("b", qb)]), self.lines.append, self.fake([0]))
        self.assertEqual(rc, 1)
        self.assertEqual(len(self.calls), 1)
        self.assertIn("a: STOP no readable state.json", self.lines[-1])

    def test_a_clean_chain_runs_every_queue(self):
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        qb = self.queue("b", [{"coc": "FO4Port_Y"}])
        rc = ca.run_chain(self.camp([("a", qa), ("b", qb)]), self.lines.append,
                          self.fake([0, 0], {"status": "finished", "crashes": 0}))
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual({e for _, e in self.calls}, {"steam"})

    def test_holds_launch_and_released_come_from_the_campaign(self):
        q = self.queue("walk", [{"coc": "FO4Core_RedRocketSpawn"}])
        self.assertEqual(ca.run_chain(self.camp([("walk", q)]), self.lines.append, self.fake([])), 1)
        self.assertEqual(self.calls, [])
        self.assertEqual(ca.run_chain(self.camp([("walk", q)], launch="cmd"), self.lines.append, self.fake([])), 1)
        self.assertEqual(ca.run_chain(self.camp([("walk", q)], released="red_rocket"), self.lines.append, self.fake([])), 1)
        rc = ca.run_chain(self.camp([("walk", q)], released=["red_rocket"]), self.lines.append,
                          self.fake([0], {"status": "finished"}))
        self.assertEqual(rc, 0)
