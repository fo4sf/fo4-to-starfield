"""testqueue.py run with a lease folder writes its own events to the ledger there (docs/ai/leader-core.md section
10): the queue's pin and tests, every attempt's start and row, the dedicated save; the importer adds nothing after
such a run and recovers the rows when a live write was lost. Synthetic data; no game, no Windows calls."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
sys.path.insert(0, os.path.join(ROOT, "src"))
import testqueue as tq  # noqa: E402
import test_testqueue as tt  # noqa: E402
from fo4sf.core import controller as c  # noqa: E402
from fo4sf.core import import_queue as imp  # noqa: E402
from fo4sf.core.state import Ledger, fold  # noqa: E402


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def quiet_log(r, msg):
    with open(r.log_p, "a", encoding="utf-8") as f:
        f.write(f"{tq.now()} {msg}\n")


class RunnerLedgerTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        tt.make_queue(self.d, n=3)
        self.leader = os.path.join(self.d, "leader")
        self.ctl = tt.FakeControls()

    def runner(self, step, lease=True, qdir=None, **kw):
        extra = dict(lease_dir=self.leader, lease_owner="Claude") if lease else {}
        r = tq.Runner(qdir or self.d, tt.args(**extra, **kw), ctl=self.ctl, step=step)
        r.log = lambda msg: quiet_log(r, msg)             # run.log only: the suite's output stays the result line
        r.session, r.cell = True, "C"
        r._ps = lambda *a, **k: (0, "at the cell")
        return r

    def events(self):
        return Ledger(os.path.join(self.leader, "ledger.jsonl")).read()

    @staticmethod
    def mixed_step(test, out):
        """0000: nothing observed (INCONCLUSIVE, retried); 0001: fell through (FAIL); 0002: landed (PASS)."""
        if test["id"] == "0000_fall":
            return 0
        return tt.RunnerTests.landing(None, -20 if test["id"] == "0001_fall" else 0.1)(test, out)

    def test_without_a_lease_folder_nothing_is_written(self):
        self.runner(self.mixed_step, lease=False, max_attempts=2).run()
        self.assertFalse(os.path.exists(self.leader))
        self.assertEqual(len(read(os.path.join(self.d, "results.jsonl")).splitlines()), 4)

    def test_a_run_writes_the_pin_the_queue_every_attempt_and_every_row(self):
        c.Controller(self.leader).claim("Claude", "window", 3600)
        self.runner(self.mixed_step, max_attempts=2).run()
        evs = self.events()
        kinds = [e.ev for e in evs]
        self.assertEqual(kinds[0], "controller_claimed")
        self.assertEqual(kinds.count("build_pinned"), 1)
        self.assertEqual(kinds.count("task_queued"), 3)
        self.assertEqual(kinds.count("task_started"), 4)               # 0000 twice, 0001, 0002
        self.assertEqual(kinds.count("task_finished"), 4)
        self.assertTrue(all(e.by == "testqueue:Claude" for e in evs if e.ev.startswith("task")))
        pin = next(e for e in evs if e.ev == "build_pinned")
        self.assertEqual((pin.get("build_id"), pin.get("plugin_sha256")), ("abcd1234", "x"))
        self.assertEqual(pin.get("src"), imp.pin_src(self.d, tt.jload(os.path.join(self.d, "queue.json"))))
        self.assertTrue(pin.get("src").startswith(os.path.join(self.d, "queue.json") + "#pin:"))
        queued = [e for e in evs if e.ev == "task_queued"]
        self.assertEqual([e.get("src") for e in queued], [os.path.join(self.d, "queue.json") + f"#{i:04d}_fall" for i in range(3)])
        self.assertEqual(queued[0].get("owner"), "Claude")
        finished = [e for e in evs if e.ev == "task_finished"]
        self.assertEqual([e.get("src") for e in finished], [os.path.join(self.d, "results.jsonl") + f":{n}" for n in (1, 2, 3, 4)])
        camp = os.path.basename(self.d)
        self.assertEqual([(e.get("task"), e.get("attempt"), e.get("outcome"), e.get("completed")) for e in finished],
                         [(f"{camp}/0000_fall", 1, "INCONCLUSIVE", False), (f"{camp}/0001_fall", 1, "FAIL", True),
                          (f"{camp}/0002_fall", 1, "PASS", True), (f"{camp}/0000_fall", 2, "INCONCLUSIVE", False)])
        self.assertEqual([e.get("task") for e in queued], [f"{camp}/{i:04d}_fall" for i in range(3)])
        self.assertEqual([e.get("task") for e in evs if e.ev == "task_started"][0], f"{camp}/0000_fall")
        self.assertTrue(finished[1].get("evidence")[0].endswith(os.path.join("0001_fall", "a1")))
        self.assertEqual(finished[1].get("pins"), {"build_id": "abcd1234", "commit": "0" * 40, "plugin_sha256": "x"})
        self.assertIn("FALL", finished[1].get("detail"))
        s = fold(evs)
        self.assertEqual({k: (v["status"], v["outcome"], v["attempt"]) for k, v in s.tasks.items()},
                         {f"{camp}/0000_fall": ("inconclusive", "INCONCLUSIVE", 2), f"{camp}/0001_fall": ("completed", "FAIL", 1),
                          f"{camp}/0002_fall": ("completed", "PASS", 1)})
        self.assertEqual(s.campaigns, {os.path.basename(self.d)})
        self.assertEqual(s.build["build_id"], "abcd1234")
        self.assertEqual(s.report()[7], "Next queue: empty")
        self.assertEqual(s.controller_status(), "held")
        # the importer, run on the same folder afterwards, has nothing to add
        self.assertEqual(imp.import_queue(self.d, Ledger(os.path.join(self.leader, "ledger.jsonl"))), 0)
        # and a fresh ledger imported from the files tells the same story (the recovery path)
        fresh = Ledger(os.path.join(self.d, "fresh", "ledger.jsonl"))
        imp.import_queue(self.d, fresh)
        t = fold(fresh.read()).tasks
        self.assertEqual({k: (v["status"], v["outcome"]) for k, v in t.items()},
                         {k: (v["status"], v["outcome"]) for k, v in s.tasks.items()})

    def test_precondition_and_breaker_rows_are_undecided_never_completed(self):
        n = tq.BREAKER + 2
        tt.make_queue(self.d, n=n)
        q = tt.jload(os.path.join(self.d, "queue.json"))
        q["tests"][0]["requires"] = {"queue": os.path.join(self.d, "other"), "test": "x", "verdict": "PASS"}
        tt.jdump(q, os.path.join(self.d, "queue.json"))
        c.Controller(self.leader).claim("Claude", "window", 3600)
        self.runner(lambda t, o: 0, max_attempts=1).run()
        s = fold(self.events())
        camp = os.path.basename(self.d)
        self.assertEqual(s.tasks[f"{camp}/0000_fall"]["status"], "skipped")             # PRECONDITION
        self.assertEqual(s.tasks[f"{camp}/{n - 1:04d}_fall"]["status"], "circuit_broken")   # BREAKER
        self.assertEqual(s.tasks[f"{camp}/0001_fall"]["status"], "inconclusive")
        self.assertEqual(s.tasks_by_status().get("completed"), None)
        finished = [e for e in self.events() if e.ev == "task_finished"]
        self.assertFalse(any(e.get("completed") for e in finished))
        self.assertEqual([e.get("attempt") for e in finished if e.get("task") == f"{camp}/0000_fall"], [0])
        self.assertEqual(imp.import_queue(self.d, Ledger(os.path.join(self.leader, "ledger.jsonl"))), 0)

    def test_a_resumed_run_queues_nothing_twice_and_starts_count_up(self):
        c.Controller(self.leader).claim("Claude", "window", 3600)
        self.runner(tt.RunnerTests.landing(None, 0.1), max_tests=1).run()
        self.runner(tt.RunnerTests.landing(None, 0.1)).run()
        kinds = [e.ev for e in self.events()]
        self.assertEqual((kinds.count("build_pinned"), kinds.count("task_queued")), (1, 3))
        self.assertEqual((kinds.count("task_started"), kinds.count("task_finished")), (3, 3))
        self.assertEqual(sorted(v["status"] for v in fold(self.events()).tasks.values()), ["completed"] * 3)

    def test_the_dedicated_save_is_a_recovery_point(self):
        c.Controller(self.leader).claim("Claude", "window", 3600)
        r = self.runner(tt.RunnerTests.landing(None, 0.1), max_attempts=1)
        r.session, r.cell = False, None                                  # the game has to be set up: save, god mode
        saves = os.path.join(self.d, "saves")
        os.makedirs(saves)

        def step(test, out):
            if test.get("kind") == "save":
                tt.touch(saves, "Save1_" + test["name"] + ".sfs")
                return 0
            if test.get("kind") in ("godmode", "companion_off", "load"):
                tt.jdump({"god": True, "reply": "ok"}, os.path.join(out, "obs.json"))
                return 0
            return tt.RunnerTests.landing(None, 0.1)(test, out)
        r.step = step
        with mock.patch.object(os.path, "isdir", lambda p: True if p.endswith("Saves") else os.path.exists(p)):
            with mock.patch("glob.glob", lambda pat: [os.path.join(saves, "Save1_fo4sf_test_abcd1234.sfs")]
                            if "fo4sf_test_abcd1234" in pat and os.path.exists(os.path.join(saves, "Save1_fo4sf_test_abcd1234.sfs")) else []):
                r.run()
        points = [e for e in self.events() if e.ev == "recovery_point"]
        self.assertEqual([(e.get("kind"), e.get("path"), e.get("build_id")) for e in points],
                         [("save", "fo4sf_test_abcd1234", "abcd1234")])
        self.assertEqual(fold(self.events()).recovery_points[0]["path"], "fo4sf_test_abcd1234")

    def test_a_ledger_failure_is_logged_once_and_the_run_completes(self):
        c.Controller(self.leader).claim("Claude", "window", 3600)
        original = Ledger.append

        def flaky(self_, ev):
            if ev.ev.startswith("controller_"):
                return original(self_, ev)
            raise OSError("disk full")
        with mock.patch.object(Ledger, "append", flaky):
            code = self.runner(tt.RunnerTests.landing(None, 0.1), max_attempts=1).run()
        self.assertEqual(code, 0)
        log = read(os.path.join(self.d, "run.log"))
        self.assertEqual(log.count("ledger: disk full"), 1)
        self.assertEqual(len(read(os.path.join(self.d, "results.jsonl")).splitlines()), 3)
        self.assertEqual([e.ev for e in self.events() if e.ev.startswith("task")], [])
        # the recovery path: the importer rebuilds the run from the files
        self.assertEqual(imp.import_queue(self.d, Ledger(os.path.join(self.leader, "ledger.jsonl"))), 1 + 3 + 3)
        self.assertEqual(sorted(v["status"] for v in fold(self.events()).tasks.values()), ["completed"] * 3)

    def test_a_queue_rebuilt_under_a_bound_name_writes_nothing_live(self):
        # the ledger binds this folder's name to an archived queue of another build (imported, or run live earlier):
        # the live writer refuses like the importer (import_queue.bind), so the two never fold into one task; the run
        # itself completes and its rows stay in results.jsonl
        c.Controller(self.leader).claim("Claude", "window", 3600)
        name = os.path.basename(self.d)
        archived = os.path.join(self.d, "archive", name)
        os.makedirs(archived)
        tt.make_queue(archived, n=1)
        q = tt.jload(os.path.join(archived, "queue.json"))
        q["build_id"] = "ffffffff"
        tt.jdump(q, os.path.join(archived, "queue.json"))
        with open(os.path.join(archived, "results.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"id": "0000_fall", "attempt": 1, "verdict": "FAIL", "class": "FALL", "dir": "x", "t": "t1"}) + "\n")
        ledger = Ledger(os.path.join(self.leader, "ledger.jsonl"))
        self.assertEqual(imp.import_queue(archived, ledger), 3)
        code = self.runner(tt.RunnerTests.landing(None, 0.1), max_attempts=1).run()      # build abcd1234, the same name
        self.assertEqual(code, 0)
        self.assertEqual(len(read(os.path.join(self.d, "results.jsonl")).splitlines()), 3)   # the run itself completed
        log = read(os.path.join(self.d, "run.log"))
        self.assertEqual(log.count("ledger: campaign"), 1)
        self.assertIn(f"campaign {name!r} is already bound to", log)
        self.assertIn("holds build abcd1234", log)
        self.assertIn("nothing of this run is written to the ledger", log)
        self.assertTrue(all(e.by == "import" for e in self.events() if e.ev.startswith("task") or e.ev == "build_pinned"))
        s = fold(self.events())
        self.assertEqual({k: (v["outcome"], v["build_id"]) for k, v in s.tasks.items()}, {f"{name}/0000_fall": ("FAIL", "ffffffff")})
        with self.assertRaises(imp.CampaignBound):                                        # and the importer refuses it too
            imp.import_queue(self.d, ledger)
        # the bound queue relocated (the same build under the same name) writes live under its campaign
        moved = os.path.join(self.d, "moved", name)
        shutil.copytree(archived, moved)
        code = self.runner(tt.RunnerTests.landing(None, 0.1), max_attempts=1, qdir=moved).run()
        self.assertEqual(code, 0)
        self.assertNotIn("ledger:", read(os.path.join(moved, "run.log")))
        live = [e for e in self.events() if e.by == "testqueue:Claude" and e.ev.startswith("task")]
        self.assertEqual([e.ev for e in live], ["task_queued", "task_started", "task_finished"])   # new path: new src keys
        self.assertEqual(live[2].get("src"), os.path.join(moved, "results.jsonl") + ":2")
        s = fold(self.events())
        self.assertEqual({k: (v["outcome"], v["build_id"]) for k, v in s.tasks.items()}, {f"{name}/0000_fall": ("PASS", "ffffffff")})
        self.assertEqual(s.campaigns, {name})

    def test_the_live_check_needs_the_same_plan_and_agreeing_rows(self):
        # runner_events.check_binding is the importer's rule (Codex review 5558689652): the same build is not enough
        from fo4sf.core import runner_events as rev
        name = "door_trip"
        a = os.path.join(self.d, "a", name)
        os.makedirs(a)
        q = {"created": "2026-10-15T10:00:00", "build_id": "aaaaaaaa", "plugin_sha256": "aa" * 32,
             "tests": [{"id": "door_1", "kind": "door_trip", "ref": "0x100"}]}
        tt.jdump(q, os.path.join(a, "queue.json"))
        with open(os.path.join(a, "results.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"id": "door_1", "attempt": 1, "verdict": "FAIL", "class": "FALL", "dir": "x", "t": "t1"}) + "\n")
        ledger = Ledger(os.path.join(self.leader, "ledger.jsonl"))
        imp.import_queue(a, ledger)
        events = ledger.read()
        b = os.path.join(self.d, "b", name)
        other = dict(q, tests=[{"id": "door_1", "kind": "door_trip", "ref": "0x200"}])
        with self.assertRaises(imp.CampaignBound):                                    # another plan, one build
            rev.check_binding(events, b, other)
        pass_row = [(1, {"id": "door_1", "attempt": 1, "verdict": "PASS", "class": ""})]
        with self.assertRaises(imp.CampaignBound):                                    # the same plan, a row that differs
            rev.check_binding(events, b, q, pass_row)
        rev.check_binding(events, b, q, rev.results_rows(os.path.join(a, "results.jsonl"))[0])   # a relocation
        # nothing run there yet: an empty copy would run the bound tests again under the campaign and could turn its
        # FAIL into a PASS (Codex on #199 at 05e8439), so it is refused like the importer refuses it
        for rows in (None, []):
            with self.assertRaises(imp.CampaignBound):
                rev.check_binding(events, b, q, rows)
        self.assertEqual(rev.task_queued(b, q, q["tests"][0], "x", "Claude").get("queue_id"), imp.queue_identity(q))

    def test_a_torn_results_tail_is_terminated_and_reported_not_merged(self):
        torn = '{"id": "0000_fall", "kind": "fall", "verd'
        with open(os.path.join(self.d, "results.jsonl"), "w", encoding="utf-8") as f:
            f.write(torn)                                                 # the row in flight when the power went
        c.Controller(self.leader).claim("Claude", "window", 3600)
        self.runner(tt.RunnerTests.landing(None, 0.1), max_attempts=1).run()
        lines = read(os.path.join(self.d, "results.jsonl")).split("\n")
        self.assertEqual(lines[0], torn)                                  # kept as evidence, on its own line
        self.assertEqual([json.loads(x)["id"] for x in lines[1:4]], ["0000_fall", "0001_fall", "0002_fall"])
        finished = [e for e in self.events() if e.ev == "task_finished"]
        self.assertEqual([e.get("src").rsplit(":", 1)[1] for e in finished], ["2", "3", "4"])
        live = Ledger(os.path.join(self.leader, "ledger.jsonl"))
        self.assertEqual(imp.import_queue(self.d, live), 1)               # only the report of the torn line is new
        rep = [e for e in live.read() if e.ev == "ledger_repaired"]
        self.assertEqual((len(rep), rep[0].get("dropped"), rep[0].get("src")), (1, torn, os.path.join(self.d, "results.jsonl") + ":1"))
        rows, corrupt = imp._rows(os.path.join(self.d, "results.jsonl"))
        self.assertEqual(([line for line, _ in rows], corrupt), ([2, 3, 4], [(1, torn)]))

    def test_a_row_recovered_by_an_import_never_replaces_a_newer_retry(self):
        """A lost task_finished write, a resumed run whose retry passes and is written live, then the import that
        recovers the lost row: the recovered older result stays in the ledger as evidence, but the fold keeps the
        retry's PASS, exactly as a fresh import of the same files reads them (Codex finding, PR #197)."""
        c.Controller(self.leader).claim("Claude", "window", 3600)
        calls = []

        def step(test, out):                                              # a1: nothing observed (retried); a2: landed
            calls.append(out)
            return 0 if len(calls) == 1 else tt.RunnerTests.landing(None, 0.1)(test, out)
        original = Ledger.append

        def lossy(self_, e):
            if e.ev == "task_finished":
                raise OSError("write lost")
            return original(self_, e)
        with mock.patch.object(Ledger, "append", lossy):
            self.assertEqual(self.runner(step, max_tests=1).run(), 4)    # attempt 1 ran; its row's event was lost
        live = Ledger(os.path.join(self.leader, "ledger.jsonl"))
        self.assertEqual([e.ev for e in live.read() if e.ev.startswith("task_")], ["task_queued"] * 3 + ["task_started"])
        self.assertEqual(self.runner(step, max_tests=1).run(), 4)        # resumed: attempt 2 PASS, written live
        camp = os.path.basename(self.d)
        tid = f"{camp}/0000_fall"
        rows = [json.loads(x) for x in read(os.path.join(self.d, "results.jsonl")).splitlines()]
        self.assertEqual([(r["id"], r["attempt"], r["verdict"]) for r in rows],
                         [("0000_fall", 1, "INCONCLUSIVE"), ("0000_fall", 2, "PASS")])
        before = fold(live.read()).tasks[tid]
        self.assertEqual((before["status"], before["outcome"], before["attempt"]), ("completed", "PASS", 2))
        self.assertEqual(imp.import_queue(self.d, live), 1)               # only the lost row's event is new
        evs = live.read()
        finished = [e for e in evs if e.ev == "task_finished"]
        self.assertEqual([(e.by, e.get("attempt"), e.get("outcome"), e.get("src").rsplit(":", 1)[1]) for e in finished],
                         [("testqueue:Claude", 2, "PASS", "2"), ("import", 1, "INCONCLUSIVE", "1")])   # append-only: kept as is
        after = fold(evs).tasks[tid]
        self.assertEqual((after["status"], after["outcome"], after["attempt"]), ("completed", "PASS", 2))
        self.assertEqual(fold(evs).tasks_by_status().get("completed"), [tid])
        # the repaired live ledger and a fresh import of the same untouched files tell the same story
        fresh = Ledger(os.path.join(self.d, "fresh", "ledger.jsonl"))
        self.assertEqual(imp.import_queue(self.d, fresh), 1 + 3 + 2)
        self.assertEqual({k: (v["status"], v["outcome"], v["attempt"]) for k, v in fold(fresh.read()).tasks.items()},
                         {k: (v["status"], v["outcome"], v["attempt"]) for k, v in fold(evs).tasks.items()})


if __name__ == "__main__":
    unittest.main()
