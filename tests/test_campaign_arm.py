"""scripts/game/campaign_arm.py: a chain of planned queues is armed only with the night-run caps, on the installed set,
away from held cells (synthetic queue folders; nothing launched)."""
import io
import json
import os
import sys
import tempfile
import re
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import campaign_arm as ca  # noqa: E402
import testqueue as tq  # noqa: E402

CAPS = {"max_attempts": 1, "max_relaunch": 1, "crash_budget": 1, "min_free_gb": 43, "dump_drive": "D:\\"}
PLUGINS = ["FO4TerrainCore.esm", "FO4TerrainCore_Mars.esm", "FO4ActorRaider.esm", "FO4SFMission.esm"]


STARFIELD_T = ca.STARFIELD


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.staging = os.path.join(self.d, "integ_v6")
        os.makedirs(self.staging)
        with open(os.path.join(self.staging, "FO4Port.esm"), "wb") as f:
            f.write(b"port")
        self.exp = os.path.join(self.d, "v6e")
        self.sf = os.path.join(self.d, "SF")                              # the experiment already installed there
        os.makedirs(os.path.join(self.sf, "Data"))
        self.receipt(self.exp)
        self.stage = os.path.join(self.d, "stage")                       # the judges' rounds.json and presence.json
        os.makedirs(self.stage)
        for n in ("rounds.json", "presence.json"):
            with open(os.path.join(self.stage, n), "w") as f:
                json.dump({"tests": []}, f)

    def receipt(self, exp, plugins=PLUGINS, **extra):
        with open(os.path.join(self.sf, "Data", "FO4SFExp.install.json"), "w") as f:
            json.dump(dict({"exp_dir": exp, "files": {p: {} for p in plugins}, "complete": True}, **extra), f)

    def queue(self, name, tests, pre=None, **extra):
        q = os.path.join(self.d, name)
        os.makedirs(q)
        digest = tq.sha256(os.path.join(self.staging, "FO4Port.esm"))
        body = dict({"staging": self.staging, "plugin_sha256": digest, "build_id": digest[:8], "experiment": self.stage,
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
        # Codex on #391: the walk (no cell) launches into the queue's launch cell first, so that cell counts too
        self.assertEqual(ca.cells(tq.load(os.path.join(stairs, "queue.json"))), ["Vault111Cryo", "BostonPublicLibrary02"])
        held = self.queue("held", [{"kind": "terrain", "cell": "", "world_coc": "FO4Port_X"}],
                          launch_cell="FO4Core_RedRocketSpawn")
        ok, why = self.check(self.camp([("held", held)]))
        self.assertFalse(ok)
        self.assertIn("FO4Core_RedRocketSpawn: held (red_rocket)", " ".join(why))

    def test_a_red_rocket_start_is_held_until_released(self):
        q = self.queue("walk", [{"travel": "coc FO4Core_RedRocketSpawn"}])
        ok, why = self.check(self.camp([("walk", q)]))
        self.assertFalse(ok)
        self.assertIn("held (red_rocket)", why[0])
        self.assertEqual(self.check(self.camp([("walk", q)]), {"red_rocket"}), (True, []))
        ok, why = self.check(self.camp([("walk", q)]), {"sanctuary"})
        self.assertIn("does not have", why[-1])

    def test_only_the_installed_experiment_may_be_installed_before_launch(self):
        exp = [sys.executable, "scripts\\game\\exp_install.py", "install", "--exp-dir", self.exp, "--starfield", self.sf,
               "--plugins", ",".join(PLUGINS), "--pack"]
        q = self.queue("walk", [{"coc": "FO4Port_X"}], pre=exp)
        self.assertEqual(self.check(self.camp([("walk", q)], starfield=self.sf + os.sep)), (True, []))
        # Codex on #391: the experiment goes into the Starfield folder the chain launches (the default when unset)
        self.assertIn("pre_launch installs into %s, the campaign runs" % self.sf,
                      " ".join(self.check(self.camp([("walk", q)]))[1]))
        # Codex on #391: with no record, or another experiment's, the "reinstall" would change the installed set
        for rec, want in ((None, "no readable install record"), ((os.path.join(self.d, "v6c"),), "would replace"),
                          ((self.exp, PLUGINS[:1]), "would replace"), ((self.exp, PLUGINS, {"complete": False}), "incomplete")):
            with self.subTest(rec=rec):
                os.remove(os.path.join(self.sf, "Data", "FO4SFExp.install.json"))
                if rec:
                    self.receipt(rec[0], *(rec[1:2]), **(rec[2] if len(rec) > 2 else {}))
                ok, why = self.check(self.camp([("walk", q)], starfield=self.sf))
                self.assertFalse(ok)
                self.assertIn(want, " ".join(why))
                self.receipt(self.exp)
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
                         ["Vault111Cryo", "FO4Core_RedRocketSpawn", "FO4Port_SuperDuperMart01"])
        ok, why = self.check(self.camp([("doors", q)]))
        self.assertFalse(ok)
        self.assertIn("FO4Core_RedRocketSpawn", " ".join(why))


    def test_a_door_trip_into_a_held_interior_is_held(self):
        # Codex on #391: the test starts outside, then enters its "inside" cell through the door
        q = self.queue("doors", [{"kind": "door_trip", "cell": "", "travel": "coc FO4Port_SuperDuperMart01",
                                  "outside": {"start": [0, 0, 0]}, "inside": {"cell": "FO4Port_RedRocket01"}}])
        self.assertIn("FO4Port_RedRocket01", ca.cells(ca.tq.load(os.path.join(q, "queue.json"))))
        c = self.camp([("doors", q)], holds={"red_rocket": ["FO4Port_RedRocket01"]})
        ok, why = self.check(c)
        self.assertFalse(ok)
        self.assertIn("FO4Port_RedRocket01: held (red_rocket)", " ".join(why))
        self.assertTrue(self.check(c, ["red_rocket"])[0])


    def test_a_travel_into_a_held_cell_is_held(self):
        # Codex on #391: plan's travel test records the cell behind its load door in dest_cell
        q = self.queue("travel", [{"kind": "travel", "cell": "SanctuaryExt", "dest_cell": "FO4Port_RedRocket01"}])
        ok, why = self.check(self.camp([("travel", q)], holds={"red_rocket": ["FO4Port_RedRocket01"]}))
        self.assertFalse(ok)
        self.assertIn("FO4Port_RedRocket01: held (red_rocket)", " ".join(why))

    def test_a_queue_with_no_launch_left_is_refused(self):
        # Codex on #391: a clean stop after the launch leaves relaunches 1, and --max-relaunch 1 refuses at once
        q = self.queue("a", [{"coc": "FO4Port_X"}, {"coc": "FO4Port_Y"}])
        with open(os.path.join(q, "state.json"), "w") as f:
            json.dump({"done": {"0000_t": "PASS"}, "relaunches": 1, "crashes": 0, "status": "stopped"}, f)
        ok, why = self.check(self.camp([("a", q)]))
        self.assertFalse(ok)
        self.assertIn("used 1 of 1 launch(es)", " ".join(why))
        with open(os.path.join(q, "state.json"), "w") as f:
            json.dump({"done": {"0000_t": "PASS"}, "relaunches": 0, "crashes": 0, "status": "stopped"}, f)
        self.assertTrue(self.check(self.camp([("a", q)]))[0])


    def test_travel_other_than_coc_and_relative_queues_are_refused(self):
        # Codex on #391: cow and player.moveto go where the holds can not see; a relative queue names another folder
        for travel in ("cow Commonwealth 0 0", "player.moveto 0001A2B3"):
            with self.subTest(travel=travel):
                q = self.queue(travel.split()[0].replace(".", "_"), [{"kind": "terrain", "cell": "", "world_coc": "FO4Port_X",
                                                                      "travel": travel}])
                ok, why = self.check(self.camp([("a", q)]))
                self.assertFalse(ok)
                self.assertIn("can not be checked against the holds", " ".join(why))
        q = self.queue("rel", [{"coc": "FO4Port_X"}])
        ok, why = self.check(self.camp([("a", os.path.relpath(q))]))
        self.assertFalse(ok)
        self.assertIn("is not a full path", " ".join(why))
        self.assertTrue(self.check(self.camp([("a", q)]))[0])


    def test_probe_moveto_booleans_and_a_relative_experiment_are_refused(self):
        # Codex on #391: MoveTo can load a held cell; JSON true passed as 1 and ran as "True"; a relative experiment
        # names two different rounds files from the check and from the judge in the checkout
        moveto = 'cgf "FO4SF_Probe.MoveTo" "FO4TerrainCore.esm" 2048 0.0 0.0 0.0'
        q = self.queue("mv", [{"coc": "FO4Port_X", "console_post": [moveto]}])
        ok, why = self.check(self.camp([("a", q)]))
        self.assertFalse(ok)
        self.assertIn("FO4SF_Probe.MoveTo in 0000_t", " ".join(why))
        q = self.queue("ok", [{"coc": "FO4Port_X"}])
        for k, v in (("max_relaunch", True), ("crash_budget", True), ("max_attempts", True), ("max_attempts", 1.0)):
            with self.subTest(k=k, v=v):
                ok, why = self.check(self.camp([("a", q)], caps=dict(CAPS, **{k: v})))
                self.assertFalse(ok)
                self.assertIn(k, " ".join(why))
        q = self.queue("relexp", [{"coc": "FO4Port_X"}], experiment="stage")
        c = self.camp([("a", q)])
        c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", q]
        ok, why = self.check(c)
        self.assertFalse(ok)
        self.assertIn("not a full path", " ".join(why))


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
        self.assertIn("'run' '--queue' '%s' '--starfield' 'D:\\SteamLibrary\\steamapps\\common\\Starfield'" % q, text)
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

    def test_the_chain_sets_the_launch_mode_and_runs_only_the_manifest_it_was_written_from(self):
        # Codex on #391: the script ignored "launch", and a manifest edited after the script still passed the check
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        cp, out = os.path.join(self.d, "c.json"), os.path.join(self.d, "chain.ps1")
        with open(cp, "w") as f:
            json.dump(self.camp([("a", q)], launch="exe"), f)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ca.main(["script", "--campaign", cp, "--out", out]), 0)
        with open(out, newline="") as f:
            text = f.read()
        self.assertIn("$env:FO4SF_LAUNCH = 'exe'", text)
        digest = re.search(r"--sha256 ([0-9a-f]{64})", text).group(1)
        self.assertLess(text.index("FO4SF_LAUNCH"), text.index("testqueue.py"))

        def check(*extra):
            with redirect_stdout(io.StringIO()) as buf:
                return ca.main(["check", "--campaign", cp, *extra]), buf.getvalue()
        self.assertEqual(check("--sha256", digest)[0], 0)
        with open(cp, "w") as f:
            json.dump(self.camp([("a", q)]), f)                              # edited after the script was written
        rc, outp = check("--sha256", digest)
        self.assertEqual(rc, 1)
        self.assertIn("changed since the chain was written", outp)

    def test_each_queue_is_checked_again_against_its_pin_right_before_its_run(self):
        # Codex on #391: a later queue re-planned while an earlier one ran was loaded unchecked
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        qb = self.queue("b", [{"coc": "FO4Port_Y"}])
        cp, out = os.path.join(self.d, "c.json"), os.path.join(self.d, "chain.ps1")
        with open(cp, "w") as f:
            json.dump(self.camp([("a", qa), ("b", qb)]), f)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ca.main(["script", "--campaign", cp, "--out", out]), 0)
        with open(out, newline="") as f:
            text = f.read()
        pins = re.findall(r"--only '(\w+)' --queue-sha256 ([0-9a-f]{64})", text)
        self.assertEqual([n for n, _ in pins], ["a", "b"])
        self.assertLess(text.index("--only 'b'"), text.index("'--queue' '%s'" % qb))
        self.assertLess(text.index("gate --queue '%s'" % qa), text.index("--only 'b'"))
        digest = re.search(r"--sha256 ([0-9a-f]{64})", text).group(1)

        def recheck(name, pin):
            with redirect_stdout(io.StringIO()) as buf:
                return ca.main(["check", "--campaign", cp, "--sha256", digest, "--only", name,
                                "--queue-sha256", pin]), buf.getvalue()
        self.assertEqual(recheck("b", pins[1][1])[0], 0)
        with open(os.path.join(qb, "queue.json"), "w") as f:            # re-planned into the held arrival
            json.dump({"staging": self.staging, "plugin_sha256": tq.sha256(os.path.join(self.staging, "FO4Port.esm")),
                       "tests": [{"id": "0000_t", "coc": "FO4Core_RedRocketSpawn"}]}, f)
        rc, outp = recheck("b", pins[1][1])
        self.assertEqual(rc, 1)
        self.assertIn("changed since the chain was armed", outp)
        self.assertIn("held (red_rocket)", outp)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ca.main(["check", "--campaign", cp, "--only", "c", "--queue-sha256", pins[0][1]]), 1)
            self.assertEqual(ca.main(["check", "--campaign", cp, "--only", "a"]), 1)

    def test_the_judges_definition_file_is_pinned_with_the_queue(self):
        # Codex on #391: door_rounds.py and presence.py read their rounds or presence file only at judge time
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        other = os.path.join(self.d, "other_rounds.json")
        with open(other, "w") as f:
            json.dump({"tests": []}, f)
        for judge, path in ((["--queue", q], os.path.join(self.stage, "rounds.json")), (["--queue", q, "--rounds", other], other)):
            with self.subTest(judge=judge):
                e = {"name": "a", "queue": q, "judge": ["scripts/bridge/door_rounds.py", "judge"] + judge}
                c = self.camp([])
                c["queues"] = [e]
                self.assertTrue(self.check(c)[0])
                pin = ca.queue_sha256(e)
                self.assertEqual(ca.recheck(e, c, set(), pin), [])
                with open(path, "w") as f:
                    json.dump({"tests": [{"test": 0}]}, f)                 # edited while an earlier queue ran
                self.assertIn("judge's definition file changed", " ".join(ca.recheck(e, c, set(), pin)))
        e = {"name": "a", "queue": q, "judge": ["scripts/bridge/presence.py", "judge", "--queue", q]}
        self.assertNotEqual(ca.queue_sha256(e), ca.queue_sha256({"name": "a", "queue": q}))
        for bad, want in ((["--rounds", "rel.json"], "relative"), (["--rounds=" + other], "once"),
                          (["--rounds", other, "--rounds", other], "once"), (["--rounds", other + ".gone"], "missing")):
            with self.subTest(bad=bad):
                c = self.camp([("a", q)])
                c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", q] + bad
                self.assertIn(want, " ".join(self.check(c)[1]))

    def test_the_chain_names_the_campaign_by_its_full_path(self):
        # Codex on #391: the chain runs Set-Location to the checkout before its check
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        cp = os.path.join(self.d, "c.json")
        with open(cp, "w") as f:
            json.dump(self.camp([("a", q)]), f)
        old = os.getcwd()
        os.chdir(self.d)
        try:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(ca.main(["script", "--campaign", "c.json", "--out", "chain.ps1"]), 0)
        finally:
            os.chdir(old)
        with open(os.path.join(self.d, "chain.ps1"), newline="") as f:
            text = f.read()
        self.assertIn("check --campaign '%s' --sha256" % os.path.abspath(cp), text)
        self.assertNotIn("--campaign 'c.json'", text)

    def test_the_chain_has_no_time_in_it(self):
        # Codex on #391: the same manifest and inputs write the same chain
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        cp = os.path.join(self.d, "c.json")
        with open(cp, "w") as f:
            json.dump(self.camp([("a", q)]), f)
        texts = []
        for n in ("one.ps1", "two.ps1"):
            with redirect_stdout(io.StringIO()):
                ca.main(["script", "--campaign", cp, "--out", os.path.join(self.d, n)])
            with open(os.path.join(self.d, n), newline="") as f:
                texts.append(f.read())
        self.assertEqual(texts[0], texts[1])
        # Codex on #391: a missing checkout stops the chain before the first Python step
        self.assertIn("try { Set-Location -LiteralPath 'D:\\Modding\\wt_nightrun' -ErrorAction Stop } catch {", texts[0])
        self.assertLess(texts[0].index("Set-Location"), texts[0].index("& $py"))
        self.assertNotRegex(texts[0], r"\d{4}-\d\d-\d\dT")

    def test_repeated_pre_launch_options_are_refused(self):
        # Codex on #391: argparse runs the last --exp-dir, the check read the first
        for extra in (["--exp-dir", os.path.join(self.d, "v6c")], ["--starfield", "E:\\SF"],
                      ["--plugins", "Other.esm"]):
            with self.subTest(extra=extra):
                pre = [sys.executable, "scripts\\game\\exp_install.py", "install", "--exp-dir", self.exp,
                       "--starfield", STARFIELD_T, "--plugins", ",".join(PLUGINS), "--pack", *extra]
                q = self.queue("w" + str(len(extra[1])), [{"coc": "FO4Port_X"}], pre=pre)
                self.assertIn("each option once", " ".join(self.check(self.camp([("w", q)]))[1]))
        pre = [sys.executable, "scripts\\game\\exp_install.py", "install", "--exp-dir=" + self.exp,
               "--starfield", STARFIELD_T, "--plugins", ",".join(PLUGINS)]
        q = self.queue("eq", [{"coc": "FO4Port_X"}], pre=pre)
        self.assertIn("--option=value", " ".join(self.check(self.camp([("w", q)]))[1]))

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

    def test_a_queue_changed_while_an_earlier_one_ran_stops_the_chain(self):
        # Codex on #391: the chain checked every queue once at the start
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        qb = self.queue("b", [{"coc": "FO4Port_Y"}])
        inner = self.fake([0, 0], {"status": "finished", "crashes": 0})

        def call(argv, env):
            with open(os.path.join(qb, "queue.json"), "a") as f:          # b re-planned while a runs
                f.write(" ")
            return inner(argv, env)
        rc = ca.run_chain(self.camp([("a", qa), ("b", qb)]), self.lines.append, call)
        self.assertEqual(rc, 1)
        self.assertEqual(len(self.calls), 1)                                  # b never started
        self.assertIn("b: STOP before the run", self.lines[-1])
        self.assertIn("changed since the chain was armed", self.lines[-1])

    def test_run_uses_the_campaign_checkout_and_python(self):
        # Codex on #391: run started the runner from this module's repo with this interpreter
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        self.assertEqual(ca.run_chain(self.camp([("a", q)], checkout=os.path.join(self.d, "nope")), self.lines.append), 1)
        self.assertIn("checkout", self.lines[-1])
        seen = []
        import subprocess

        class Done:
            returncode = 0

        def fake_run(argv, cwd=None, env=None):
            seen.append((argv[0], cwd))
            if "testqueue.py" in argv[1]:
                with open(os.path.join(q, "state.json"), "w") as f:
                    json.dump({"status": "finished"}, f)
            return Done()
        old, subprocess.run = subprocess.run, fake_run
        try:
            rc = ca.run_chain(self.camp([("a", q)], checkout=self.d), self.lines.append)
        finally:
            subprocess.run = old
        self.assertEqual(rc, 0)
        self.assertEqual(seen, [("C:\\py\\python.exe", self.d)])

    def test_holds_launch_and_released_come_from_the_campaign(self):
        q = self.queue("walk", [{"coc": "FO4Core_RedRocketSpawn"}])
        self.assertEqual(ca.run_chain(self.camp([("walk", q)]), self.lines.append, self.fake([])), 1)
        self.assertEqual(self.calls, [])
        self.assertEqual(ca.run_chain(self.camp([("walk", q)], launch="cmd"), self.lines.append, self.fake([])), 1)
        self.assertEqual(ca.run_chain(self.camp([("walk", q)], released="red_rocket"), self.lines.append, self.fake([])), 1)
        rc = ca.run_chain(self.camp([("walk", q)], released=["red_rocket"]), self.lines.append,
                          self.fake([0], {"status": "finished"}))
        self.assertEqual(rc, 0)
