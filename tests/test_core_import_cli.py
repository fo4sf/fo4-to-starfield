"""leader_import.py (docs/ai/leader-core.md section 3): queues, the deploy manifest and install records into a ledger
from the command line; idempotent, fail-closed per source, the report at the end. Synthetic folders; no game."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.core import import_cli as cli  # noqa: E402
from fo4sf.core.state import Ledger, fold  # noqa: E402
from fo4sf.core.import_queue import CampaignBound  # noqa: E402
from fo4sf.core.runner_events import check_binding, results_rows  # noqa: E402


def write_queue(d, name, tests, rows, build="abababab"):
    """A planned queue folder; rows=None is a queue that never ran (no results.jsonl yet); build=None a hand-made
    queue.json without a pin."""
    q = os.path.join(d, name)
    os.makedirs(q)
    rec = {"created": "2026-10-15T10:00:00", "tests": [{"id": t, "kind": "travel", "cell": "C", "ref": "0x1"} for t in tests]}
    if build:
        rec.update(staging="C:/staging", plugin_sha256=build[:2] * 32, build_id=build, commit="d628b56")
    with open(os.path.join(q, "queue.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f)
    if rows is None:
        return q
    with open(os.path.join(q, "results.jsonl"), "w", encoding="utf-8") as f:
        for t, verdict, cls in rows:
            f.write(json.dumps({"id": t, "kind": "travel", "cell": "C", "ref": "0x1", "attempt": 1, "verdict": verdict,
                                "class": cls, "detail": "", "dir": f"{t}_a1", "t": "t1"}) + "\n")
    return q


class ImportCliTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.d = d.name
        self.parent = os.path.join(self.d, "testqueue")
        os.makedirs(self.parent)
        self.leader = os.path.join(self.parent, "leader")                 # no queue.json: skipped by --queues
        os.makedirs(self.leader)
        self.q1 = write_queue(self.parent, "walk_1015", ["w1", "w2"], [("w1", "PASS", ""), ("w2", "FAIL", "NOLOAD")])
        self.q2 = write_queue(self.parent, "cave_1015", ["c1"], [("c1", "INCONCLUSIVE", "BREAKER")])
        with open(os.path.join(self.parent, "overnight.log"), "w", encoding="utf-8") as f:
            f.write("not a folder\n")

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(list(argv))
        return code, out.getvalue().strip().splitlines()

    def test_queues_under_a_parent_import_once_and_the_report_follows(self):
        code, lines = self.run_cli("--ledger", self.leader, "--queues", self.parent)
        self.assertEqual(code, 0, lines)
        self.assertIn(f"queue {self.q2}: 3 event(s) added", lines)       # pin + 1 test + 1 row (cave sorts first)
        self.assertIn(f"queue {self.q1}: 5 event(s) added", lines)       # pin + 2 tests + 2 rows
        self.assertIn(f"{self.leader}: skipped (no queue.json)", lines)
        self.assertIn(f"total: 8 event(s) added to {os.path.join(self.leader, 'ledger.jsonl')}", lines)
        bullets = [ln for ln in lines if ln.startswith("- ")]
        self.assertEqual(len(bullets), 8)
        self.assertIn("build_id=abababab", bullets[4])
        s = fold(Ledger(os.path.join(self.leader, "ledger.jsonl")).read())
        self.assertEqual({k: v["status"] for k, v in s.tasks.items()},
                         {"walk_1015/w1": "completed", "walk_1015/w2": "completed", "cave_1015/c1": "circuit_broken"})
        self.assertEqual(s.campaigns, {"walk_1015", "cave_1015"})
        code, lines = self.run_cli("--ledger", self.leader, "--queues", self.parent, "--no-report")
        self.assertEqual(code, 0)
        self.assertIn("total: 0 event(s) added", lines[-1])
        self.assertFalse(any(ln.startswith("- ") for ln in lines))

    def test_two_parents_both_import_and_the_newest_queue_pins_the_build(self):
        # R1 (the campaign on the owner's real records, 2026-10-17): C:\Modding\testqueue and D:\Modding\testqueue in
        # one command; a second --queues used to replace the first silently and still exit 0
        other = os.path.join(self.d, "D", "testqueue")
        os.makedirs(other)
        q3 = write_queue(other, "a_sorts_first_but_is_newest", ["d1"], [("d1", "PASS", "")], build="cdcdcdcd")
        with open(os.path.join(q3, "queue.json"), encoding="utf-8") as f:
            rec = json.load(f)
        rec["created"] = "2026-10-17T09:00:00"
        with open(os.path.join(q3, "queue.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f)
        code, lines = self.run_cli("--ledger", self.leader, "--queues", self.parent, "--queues", other, "--no-report")
        self.assertEqual(code, 0, lines)
        self.assertIn(f"queue {q3}: 3 event(s) added", lines)
        self.assertIn(f"queue {self.q1}: 5 event(s) added", lines)
        self.assertIn(f"queue {self.q2}: 3 event(s) added", lines)
        # R2: a parent's queues import oldest first by queue.json `created`, not by folder name, so the fold's current
        # build is the newest queue's (walk_core64g_1016 used to beat door_trip_sdm_round, planned a day later)
        order = [ln for ln in lines if ln.startswith("queue ")]
        self.assertTrue(order[-1].startswith(f"queue {q3}:"), order)
        s = fold(Ledger(os.path.join(self.leader, "ledger.jsonl")).read())
        self.assertEqual(s.build["build_id"], "cdcdcdcd")
        self.assertEqual(sorted(s.campaigns), ["a_sorts_first_but_is_newest", "cave_1015", "walk_1015"])
        # an explicit --queue keeps the order it was given in, and a folder named twice imports once
        code, lines = self.run_cli("--ledger", os.path.join(self.d, "L2"), "--queue", q3, "--queue", self.q2,
                                   "--queues", other, "--no-report")
        self.assertEqual([ln for ln in lines if ln.startswith("queue ")][:2],
                         [f"queue {q3}: 3 event(s) added", f"queue {self.q2}: 3 event(s) added"])
        self.assertEqual(sum(ln.startswith(f"queue {q3}:") for ln in lines), 1)

    def test_a_local_created_time_and_a_utc_file_time_order_on_one_clock(self):
        # Codex P2 on dca24a1: `created` is the planner's local wall clock (no zone); read as UTC and compared with a
        # UTC mtime, a queue planned at 10:00 Mountain (16:00Z) sorted before a queue whose file is from 13:00Z, so the
        # older queue imported last and pinned the wrong build. The host's zone is pretended to be UTC-6 here so the
        # test means the same on a UTC CI runner and on the owner's PC.
        import datetime
        from unittest import mock
        other = os.path.join(self.d, "D", "testqueue")
        os.makedirs(other)
        new_local = write_queue(other, "new_local", ["d1"], [("d1", "PASS", "")], build="bbbbbbbb")
        with open(os.path.join(new_local, "queue.json"), encoding="utf-8") as f:
            rec = json.load(f)
        rec["created"] = "2026-10-17T10:00:00"
        with open(os.path.join(new_local, "queue.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f)
        old_mtime = write_queue(other, "old_mtime", ["d1"], [("d1", "FAIL", "x")], build="aaaaaaaa")
        with open(os.path.join(old_mtime, "queue.json"), encoding="utf-8") as f:
            rec = json.load(f)
        del rec["created"]
        with open(os.path.join(old_mtime, "queue.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f)
        at = datetime.datetime(2026, 10, 17, 13, 0, tzinfo=datetime.timezone.utc).timestamp()
        os.utime(os.path.join(old_mtime, "queue.json"), (at, at))

        def mountain(s):   # what model.local_to_utc_iso does on a UTC-6 machine
            d = datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=-6)))
            return d.astimezone(datetime.timezone.utc).isoformat()

        self.assertIs(cli.local_to_utc_iso, __import__("fo4sf.core.model", fromlist=["x"]).local_to_utc_iso)
        with mock.patch.object(cli, "local_to_utc_iso", mountain):
            self.assertEqual(cli.queue_created(new_local).isoformat(), "2026-10-17T16:00:00+00:00")
            self.assertEqual(cli.queue_created(old_mtime).isoformat(), "2026-10-17T13:00:00+00:00")
            code, lines = self.run_cli("--ledger", self.leader, "--queues", other, "--no-report")
        self.assertEqual(code, 0, lines)
        order = [ln for ln in lines if ln.startswith("queue ")]
        # split at the label delimiter ": ", never at the first colon: a Windows path has one (C:\...)
        self.assertEqual([ln.split(": ")[0] for ln in order], [f"queue {old_mtime}", f"queue {new_local}"])
        s = fold(Ledger(os.path.join(self.leader, "ledger.jsonl")).read())
        self.assertEqual(s.build["build_id"], "bbbbbbbb")
        # an aware `created` is taken as written, whatever the zone (and without the pretended host zone)
        with open(os.path.join(new_local, "queue.json"), encoding="utf-8") as f:
            rec = json.load(f)
        rec["created"] = "2026-10-17T10:00:00-06:00"
        with open(os.path.join(new_local, "queue.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f)
        self.assertEqual(cli.queue_created(new_local), datetime.datetime(2026, 10, 17, 16, 0, tzinfo=datetime.timezone.utc))

    def test_an_unreadable_source_fails_alone_and_exits_one(self):
        with open(os.path.join(self.q2, "queue.json"), "w", encoding="utf-8") as f:
            f.write("{not json")
        code, lines = self.run_cli("--ledger", self.leader, "--queue", self.q1, "--queue", self.q2)
        self.assertEqual(code, 1)
        self.assertIn(f"queue {self.q1}: 5 event(s) added", lines)
        self.assertTrue(any(ln.startswith(f"queue {self.q2}: FAILED: ") for ln in lines), lines)
        self.assertIn("total: 5 event(s) added", lines[-9])
        self.assertIn("1 source(s) failed", lines[-9])
        self.assertEqual(len([ln for ln in lines if ln.startswith("- ")]), 8)   # the report still prints
        code, lines = self.run_cli("--ledger", self.leader, "--queues", os.path.join(self.d, "nowhere"))
        self.assertEqual(code, 1)
        self.assertIn("not a folder", lines[0])

    def test_a_requested_source_that_does_not_exist_fails_alone(self):
        # a mistyped recovery path must never read as "already imported": FAILED, exit 1, the valid queue still imports
        gone = os.path.join(self.d, "nonexistent")
        code, lines = self.run_cli("--ledger", self.leader, "--queue", gone, "--queue", self.q1, "--install", gone,
                                   "--deploy", gone, "--no-report")
        self.assertEqual(code, 1, lines)
        self.assertIn(f"queue {self.q1}: 5 event(s) added", lines)
        for label in (f"queue {gone}", f"install {gone}", f"deploy {gone}"):
            self.assertTrue(any(ln.startswith(f"{label}: FAILED: FileNotFoundError") for ln in lines), (label, lines))
        self.assertFalse(any("0 event(s) added" in ln for ln in lines[:-1]), lines)
        self.assertIn("total: 5 event(s) added", lines[-1])
        self.assertIn("3 source(s) failed", lines[-1])
        # a file that exists but is not a record (its top level is not an object) fails the same way
        with open(os.path.join(self.q2, "queue.json"), "w", encoding="utf-8") as f:
            json.dump(["not", "a", "queue"], f)
        code, lines = self.run_cli("--ledger", self.leader, "--queue", self.q2, "--no-report")
        self.assertEqual(code, 1, lines)
        self.assertTrue(any(ln.startswith(f"queue {self.q2}: FAILED: ValueError") for ln in lines), lines)
        # absence inside a valid queue is not an error: a planned queue that never ran has no results.jsonl
        planned = write_queue(self.d, "planned_1017", ["p1"], None)
        code, lines = self.run_cli("--ledger", self.leader, "--queue", planned, "--no-report")
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[0], f"queue {planned}: 2 event(s) added")                     # pin + 1 test
        self.assertEqual(fold(Ledger(os.path.join(self.leader, "ledger.jsonl")).read()).tasks["planned_1017/p1"]["status"], "queued")

    def test_two_folders_with_one_name_and_different_builds_never_fold_as_one_campaign(self):
        a = write_queue(os.path.join(self.d, "a"), "door_trip", ["door_1"], [("door_1", "FAIL", "FALL")], build="aaaaaaaa")
        b = write_queue(os.path.join(self.d, "b"), "door_trip", ["door_1"], [("door_1", "PASS", "")], build="bbbbbbbb")
        code, lines = self.run_cli("--ledger", self.leader, "--queue", a, "--queue", b, "--no-report")
        self.assertEqual(code, 1, lines)
        self.assertEqual(lines[0], f"queue {a}: 3 event(s) added")
        self.assertTrue(lines[1].startswith(f"queue {b}: FAILED: CampaignBound"), lines)      # a ValueError the runner tells apart
        self.assertIn("door_trip", lines[1])
        self.assertIn("bbbbbbbb", lines[1])
        self.assertIn("1 source(s) failed", lines[-1])
        ledger = Ledger(os.path.join(self.leader, "ledger.jsonl"))
        self.assertEqual(len(ledger.read()), 3)                                               # nothing of b was written
        s = fold(ledger.read())
        self.assertEqual({k: (v["outcome"], v["build_id"]) for k, v in s.tasks.items()}, {"door_trip/door_1": ("FAIL", "aaaaaaaa")})
        # the same queue relocated (archived: same name, same build) still imports under its campaign, and the
        # original folder stays idempotent
        archived = os.path.join(self.d, "archive", "door_trip")
        shutil.copytree(a, archived)
        code, lines = self.run_cli("--ledger", self.leader, "--queue", archived, "--queue", a, "--no-report")
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[:2], [f"queue {archived}: 3 event(s) added", f"queue {a}: 0 event(s) added"])
        s = fold(ledger.read())
        self.assertEqual({k: (v["outcome"], v["build_id"]) for k, v in s.tasks.items()}, {"door_trip/door_1": ("FAIL", "aaaaaaaa")})
        self.assertEqual(s.campaigns, {"door_trip"})

    def queue_at(self, parent, ref, verdict, cls=""):
        """A door_trip queue under parent: test door_1 on `ref`, build aaaaaaaa, one result row."""
        q = write_queue(os.path.join(self.d, parent), "door_trip", ["door_1"], [("door_1", verdict, cls)], build="aaaaaaaa")
        with open(os.path.join(q, "queue.json"), encoding="utf-8") as f:
            rec = json.load(f)
        rec["tests"][0]["ref"] = ref
        with open(os.path.join(q, "queue.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f)
        return q

    def test_one_build_two_plans_under_one_name_never_fold_as_one_campaign(self):
        # Codex review 5558689652: a/door_trip door_1 on ref 0x100 FAIL, b/door_trip door_1 on ref 0x200 PASS, both
        # build aaaaaaaa with the same plugin hash: the build alone does not make b a relocation of a
        a = self.queue_at("a", "0x100", "FAIL", "FALL")
        b = self.queue_at("b", "0x200", "PASS")
        code, lines = self.run_cli("--ledger", self.leader, "--queue", a, "--queue", b, "--no-report")
        self.assertEqual(code, 1, lines)
        self.assertEqual(lines[0], f"queue {a}: 3 event(s) added")
        self.assertTrue(lines[1].startswith(f"queue {b}: FAILED: CampaignBound"), lines)
        self.assertIn("the same build but another plan", lines[1])
        ledger = Ledger(os.path.join(self.leader, "ledger.jsonl"))
        self.assertEqual(len(ledger.read()), 3)
        self.assertEqual({k: v["outcome"] for k, v in fold(ledger.read()).tasks.items()}, {"door_trip/door_1": "FAIL"})

    def test_a_copy_of_the_plan_that_ran_apart_is_not_a_relocation(self):
        # the same queue.json (same created time, build and tests) in a second folder whose results diverge: a copy
        # that was run separately; its rows must not replace the bound folder's
        a = self.queue_at("a", "0x100", "FAIL", "FALL")
        b = os.path.join(self.d, "b", "door_trip")
        shutil.copytree(a, b)
        with open(os.path.join(b, "results.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"id": "door_1", "attempt": 1, "verdict": "PASS", "class": "", "dir": "d", "t": "t1"}) + "\n")
        code, lines = self.run_cli("--ledger", self.leader, "--queue", a, "--queue", b, "--no-report")
        self.assertEqual(code, 1, lines)
        self.assertTrue(lines[1].startswith(f"queue {b}: FAILED: CampaignBound"), lines)
        self.assertIn("results.jsonl line 1", lines[1])
        self.assertEqual({k: v["outcome"] for k, v in fold(Ledger(os.path.join(self.leader, "ledger.jsonl")).read()).tasks.items()},
                         {"door_trip/door_1": "FAIL"})
        # the same copy with the bound rows plus a later attempt (a relocated queue that ran on) still imports
        with open(os.path.join(a, "results.jsonl"), encoding="utf-8") as f:
            first = f.read()
        with open(os.path.join(b, "results.jsonl"), "w", encoding="utf-8") as f:
            f.write(first + json.dumps({"id": "door_1", "attempt": 2, "verdict": "PASS", "class": "", "dir": "d2",
                                        "t": "t2"}) + "\n")
        code, lines = self.run_cli("--ledger", self.leader, "--queue", b, "--no-report")
        self.assertEqual((code, lines[0]), (0, f"queue {b}: 4 event(s) added"), lines)   # pin, test, two rows

    def test_a_copy_without_the_bound_results_is_never_bound(self):
        # Codex on #199 at 05e8439: (1) a/door_trip imports with door_1 FAIL; (2) b/door_trip, the same queue.json and
        # no results.jsonl, passed vacuously and got bound; (3) b, now with door_1 PASS, imported from a bound folder
        # without any row comparison: the FAIL was laundered into a PASS
        a = self.queue_at("a", "0x100", "FAIL", "FALL")
        b = os.path.join(self.d, "b", "door_trip")
        os.makedirs(b)
        shutil.copy(os.path.join(a, "queue.json"), b)
        led = Ledger(os.path.join(self.leader, "ledger.jsonl"))
        self.assertEqual(self.run_cli("--ledger", self.leader, "--queue", a, "--no-report")[0], 0)
        code, lines = self.run_cli("--ledger", self.leader, "--queue", b, "--no-report")
        self.assertEqual(code, 1, lines)
        self.assertTrue(lines[0].startswith(f"queue {b}: FAILED: CampaignBound"), lines)
        self.assertIn("results.jsonl line 1 missing", lines[0])
        n = len(led.read())
        with open(os.path.join(b, "results.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"id": "door_1", "attempt": 1, "verdict": "PASS", "class": "", "dir": "d", "t": "t1"}) + "\n")
        code, lines = self.run_cli("--ledger", self.leader, "--queue", b, "--no-report")
        self.assertEqual(code, 1, lines)                                   # still refused: its line 1 disagrees
        self.assertEqual(len(led.read()), n)                               # nothing of b was ever written
        self.assertEqual({k: v["outcome"] for k, v in fold(led.read()).tasks.items()}, {"door_trip/door_1": "FAIL"})
        # the live runner's binding refuses the same copy before its first event
        with open(os.path.join(b, "queue.json"), encoding="utf-8") as f:
            q = json.load(f)
        with self.assertRaises(CampaignBound):
            check_binding(led.read(), b, q, rows=[])
        # a complete copy (every bound row present and agreeing) is still a relocation
        c = os.path.join(self.d, "c", "door_trip")
        shutil.copytree(a, c)
        code, lines = self.run_cli("--ledger", self.leader, "--queue", c, "--no-report")
        self.assertEqual((code, lines[0]), (0, f"queue {c}: 3 event(s) added"), lines)
        check_binding(led.read(), c, q, rows=results_rows(os.path.join(c, "results.jsonl"))[0])

    def test_a_ledger_without_queue_identities_never_accepts_another_folder(self):
        # a campaign bound by events written before queue_id: nothing proves the second folder is the same plan
        a = self.queue_at("a", "0x100", "FAIL", "FALL")
        led = os.path.join(self.leader, "ledger.jsonl")
        self.assertEqual(self.run_cli("--ledger", self.leader, "--queue", a, "--no-report")[0], 0)
        with open(led, encoding="utf-8") as f:
            old = [json.loads(ln) for ln in f if ln.strip()]
        for e in old:
            e.pop("queue_id", None)
            (e.get("fields") or {}).pop("queue_id", None)
        with open(led, "w", encoding="utf-8") as f:
            f.write("".join(json.dumps(e) + "\n" for e in old))
        archived = os.path.join(self.d, "archive", "door_trip")
        shutil.copytree(a, archived)
        code, lines = self.run_cli("--ledger", self.leader, "--queue", archived, "--no-report")
        self.assertEqual(code, 1, lines)
        self.assertIn("queue identity none recorded", lines[0])

    def test_the_identity_ignores_a_repin_in_place_and_sees_the_plan(self):
        from fo4sf.core.import_queue import queue_identity
        q = {"created": "2026-10-15T10:00:00", "build_id": "aaaaaaaa", "plugin_sha256": "aa" * 32, "commit": "c1",
             "tests": [{"id": "door_1", "ref": "0x100"}]}
        same = dict(q, game_version="1.16.244.0", commit="c2", staging="D:/elsewhere")
        self.assertEqual(queue_identity(q), queue_identity(same))
        for k, v in (("created", "2026-10-15T10:00:01"), ("build_id", "bbbbbbbb"), ("tests", [{"id": "door_1", "ref": "0x200"}])):
            self.assertNotEqual(queue_identity(q), queue_identity(dict(q, **{k: v})), k)

    def test_an_unpinned_queue_never_matches_a_bound_name(self):
        # without a build nothing tells a relocated copy from a different queue: a second folder of the name is refused
        a = write_queue(os.path.join(self.d, "a"), "hand_made", ["h1"], [("h1", "PASS", "")], build=None)
        b = write_queue(os.path.join(self.d, "b"), "hand_made", ["h1"], [("h1", "FAIL", "FALL")], build=None)
        code, lines = self.run_cli("--ledger", self.leader, "--queue", a, "--queue", b, "--no-report")
        self.assertEqual(code, 1, lines)
        self.assertEqual(lines[0], f"queue {a}: 2 event(s) added")                            # no pin: 1 test + 1 row
        self.assertTrue(lines[1].startswith(f"queue {b}: FAILED: CampaignBound"), lines)
        self.assertIn("holds build None", lines[1])
        ledger = Ledger(os.path.join(self.leader, "ledger.jsonl"))
        self.assertEqual(len(ledger.read()), 2)
        self.assertEqual({k: (v["outcome"], v["build_id"]) for k, v in fold(ledger.read()).tasks.items()}, {"hand_made/h1": ("PASS", None)})
        code, lines = self.run_cli("--ledger", self.leader, "--queue", a, "--no-report")       # the same folder again is fine
        self.assertEqual((code, lines[0]), (0, f"queue {a}: 0 event(s) added"))

    def test_a_source_of_another_shape_fails_alone_and_writes_nothing(self):
        # a file that exists and is a JSON object but not the record its writer produces (the expected top-level
        # schema): it must never read as "already imported", nor as a record with no plugins that clobbers the fold
        dep = os.path.join(self.d, "FO4Port.deploy.json")
        with open(dep, "w", encoding="utf-8") as f:
            json.dump({"files": ["FO4Port.esm"], "complete": True, "artifacts": {"FO4Port.esm": {"size": 1, "sha256": "ef" * 32}}}, f)
        inst = os.path.join(self.d, "FO4SFExp.install.json")
        with open(inst, "w", encoding="utf-8") as f:
            json.dump({"plugins": ["FO4SFExp.esm"], "plugins_replaced": [], "complete": True, "pack": "core64d"}, f)
        code, lines = self.run_cli("--ledger", self.leader, "--deploy", dep, "--install", inst, "--active-after-load", "yes", "--no-report")
        self.assertEqual(code, 0, lines)
        ledger = Ledger(os.path.join(self.leader, "ledger.jsonl"))
        self.assertEqual(len(ledger.read()), 2)
        # the two recovery paths swapped: the install record as --deploy, the deploy manifest as --install
        code, lines = self.run_cli("--ledger", self.leader, "--deploy", inst, "--install", dep, "--no-report")
        self.assertEqual(code, 1, lines)
        self.assertTrue(lines[0].startswith(f"deploy {inst}: FAILED: ValueError: deploy manifest lacks an artifacts object"), lines)
        self.assertTrue(lines[1].startswith(f"install {dep}: FAILED: ValueError: install record lacks a plugins or plugins_added list"), lines)
        self.assertEqual(lines[-1], f"total: 0 event(s) added to {ledger.path}; 2 source(s) failed")
        self.assertEqual(len(ledger.read()), 2)                                               # nothing was written
        self.assertEqual([(p["name"], p["active_after_load"]) for p in fold(ledger.read()).plugins],
                         [("FO4SFExp.esm", True)])                                                  # the plugins stand
        # a queue.json that is an object of another shape ({}, an install record, a test without an id) is not a queue
        qp = os.path.join(self.q2, "queue.json")
        for shape, why in (({}, "lacks a tests list"), ({"plugins": ["FO4SFExp.esm"], "complete": True}, "lacks a tests list"),
                           ({"build_id": "abababab", "tests": [{"kind": "travel"}]}, "test without an id")):
            with open(qp, "w", encoding="utf-8") as f:
                json.dump(shape, f)
            code, lines = self.run_cli("--ledger", self.leader, "--queue", self.q2, "--no-report")
            self.assertEqual(code, 1, (shape, lines))
            self.assertTrue(lines[0].startswith(f"queue {self.q2}: FAILED: ValueError: queue.json {why}"), (shape, lines))
        self.assertEqual(len(ledger.read()), 2)
        # a deploy manifest that pins nothing (no FO4Port.esm among its artifacts) is a failure, never zero events
        with open(dep, "w", encoding="utf-8") as f:
            json.dump({"files": [], "complete": True, "artifacts": {"FO4Port - Main.ba2": {"size": 1, "sha256": "cd" * 32}}}, f)
        code, lines = self.run_cli("--ledger", self.leader, "--deploy", dep, "--no-report")
        self.assertEqual(code, 1, lines)
        self.assertTrue(lines[0].startswith(f"deploy {dep}: FAILED: ValueError: deploy manifest pins nothing"), lines)
        # a bridge record names the one plugin it activated (bridge_install.py writes `plugin`, never `plugins`)
        bridge = os.path.join(self.d, "FO4SFBridge.install.json")
        with open(bridge, "w", encoding="utf-8") as f:
            json.dump({"schema": 2, "plugin": "FO4SFBridge.esm", "source_sha256": {}, "files": {}, "published_files": [], "complete": True}, f)
        code, lines = self.run_cli("--ledger", self.leader, "--install", bridge, "--no-report")
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[0], f"install {bridge}: 1 event(s) added")
        self.assertEqual([p["name"] for p in ledger.read()[-1].get("plugins")], ["FO4SFBridge.esm"])

    def test_deploy_and_install_records_after_the_queues(self):
        dep = os.path.join(self.d, "FO4Port.deploy.json")
        with open(dep, "w", encoding="utf-8") as f:
            json.dump({"files": ["FO4Port.esm"], "complete": True, "artifacts": {"FO4Port.esm": {"size": 1, "sha256": "ef" * 32}}}, f)
        inst = os.path.join(self.d, "FO4SFExp.install.json")
        with open(inst, "w", encoding="utf-8") as f:
            json.dump({"plugins": ["FO4SFExp.esm"], "plugins_replaced": [], "complete": True, "pack": "core64d"}, f)
        code, lines = self.run_cli("--ledger", os.path.join(self.leader, "ledger.jsonl"), "--queue", self.q1,
                                   "--deploy", dep, "--install", inst, "--active-after-load", "yes")
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[:3], [f"queue {self.q1}: 5 event(s) added", f"deploy {dep}: 1 event(s) added", f"install {inst}: 1 event(s) added"])
        s = fold(Ledger(os.path.join(self.leader, "ledger.jsonl")).read())
        self.assertEqual(s.build, {"build_id": "efefefef", "plugin_sha256": "ef" * 32})   # the deploy is the current pin
        # the entry also names its record and the sha256 the record holds for the plugin (none in this synthetic one)
        self.assertEqual([(p["name"], p["active_after_load"], p["source"], p["sha256"]) for p in s.plugins],
                         [("FO4SFExp.esm", True, "FO4SFExp.install.json", None)])
        self.assertIn("plugins: FO4SFExp.esm", [ln for ln in lines if ln.startswith("- Pins")][0])
        self.assertEqual(self.run_cli("--ledger", self.leader, "--queue", self.q1, "--deploy", dep, "--install", inst)[1][-9],
                         f"total: 0 event(s) added to {os.path.join(self.leader, 'ledger.jsonl')}")

    def test_nothing_to_import_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()):
                cli.main(["--ledger", self.leader])
        self.assertEqual(cm.exception.code, 2)

    def test_the_wrapper_runs_under_python_isolated(self):
        r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "leader_import.py"), "--ledger", self.leader,
                            "--queue", self.q1, "--no-report"], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("5 event(s) added", r.stdout)


if __name__ == "__main__":
    unittest.main()
