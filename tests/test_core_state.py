"""Leader core (docs/ai/leader-core.md): synthetic ledgers and queue folders only; nothing touches a game."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.core.model import CapabilityState, Event, Outcome, Source, local_to_utc_iso, outcome_from_queue  # noqa: E402
from fo4sf.core.state import Ledger, fold  # noqa: E402
from fo4sf.core import filelock, import_queue as imp  # noqa: E402


def ev(kind, **f):
    return Event(kind, "test", t=f.pop("t", "2026-10-15T12:00:00+00:00"), fields=f)


class ModelTests(unittest.TestCase):
    def test_only_pass_and_fail_are_decided(self):
        self.assertEqual([o for o in Outcome if o.decided], [Outcome.PASS, Outcome.FAIL])

    def test_queue_verdicts_map_onto_outcomes(self):
        self.assertEqual(outcome_from_queue("PASS"), Outcome.PASS)
        self.assertEqual(outcome_from_queue("FAIL", "NOTMOVED"), Outcome.FAIL)
        self.assertEqual(outcome_from_queue("INCONCLUSIVE", "BREAKER"), Outcome.CIRCUIT_BROKEN)
        self.assertEqual(outcome_from_queue("INCONCLUSIVE", "PRECONDITION"), Outcome.SKIPPED)
        self.assertEqual(outcome_from_queue("INCONCLUSIVE", "CONTROL"), Outcome.INCONCLUSIVE)

    def test_undecided_outcome_cannot_be_reported_completed(self):
        with self.assertRaises(ValueError):
            ev("task_finished", task="a", outcome="SKIPPED", completed=True)
        with self.assertRaises(ValueError):
            ev("task_finished", task="a", outcome="DONE")

    def test_unknown_event_types_are_opaque_and_known_ones_need_their_key(self):
        e = ev("task_cancelled", task="a", reason="the owner said so")          # a newer checkout's event
        self.assertFalse(e.known)
        back = Event.from_json(e.to_json())
        self.assertEqual((back.ev, back.get("reason")), ("task_cancelled", "the owner said so"))
        s = fold([ev("task_queued", task="a"), back])
        self.assertEqual((s.tasks["a"]["status"], s.unknown_events, s.events), ("queued", 1, 2))
        for kind, key in (("task_finished", "task"), ("task_started", "task"), ("capability_result", "capability"),
                          ("blocker_opened", "blocker")):
            with self.assertRaises(ValueError, msg=kind) as cm:
                ev(kind, outcome="PASS", source="IN_GAME")
            self.assertIn(f"needs a {key}", str(cm.exception))
        with self.assertRaises(ValueError):
            Event("", "x")

    def test_the_header_wins_over_a_field_of_the_same_name(self):
        line = ev("task_finished", task="a", outcome="PASS", ev="controller_claimed", by="mallory").to_json()
        back = Event.from_json(line)
        self.assertEqual((back.ev, back.by, back.get("task")), ("task_finished", "test", "a"))

    def test_runner_local_times_are_stored_as_utc(self):
        self.assertEqual(local_to_utc_iso("2026-10-16T12:00:00+00:00"), "2026-10-16T12:00:00+00:00")
        self.assertEqual(local_to_utc_iso("not a time"), "not a time")
        import datetime
        local = datetime.datetime(2026, 10, 16, 14, 0, 0)
        expected = local.astimezone().astimezone(datetime.timezone.utc).isoformat()
        self.assertEqual(local_to_utc_iso("2026-10-16T14:00:00"), expected)
        self.assertTrue(local_to_utc_iso("2026-10-16T14:00:00").endswith("+00:00"))


class LedgerTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.path = os.path.join(d.name, "leader", "ledger.jsonl")

    def test_truncated_last_line_is_not_an_event_and_is_repaired_on_append(self):
        led = Ledger(self.path)
        led.append(ev("leader_started", commit="abc1234"))
        led.append(ev("task_started", task="walk_1"))
        with open(self.path, "a", encoding="utf-8") as f:
            f.write('{"t": "2026-10-15T12:01:00+00:00", "ev": "task_finished", "task": "walk_1", "outc')  # power cut
        events = led.read()
        self.assertEqual([e.ev for e in events], ["leader_started", "task_started"])
        self.assertTrue(led.truncated.startswith('{"t"'))
        self.assertEqual(fold(events).tasks["walk_1"]["status"], "running")     # running or lost, never done
        led.append(ev("task_finished", task="walk_1", outcome="INCONCLUSIVE", detail="lost in the power cut"))
        kinds = [e.ev for e in led.read()]
        self.assertEqual(kinds, ["leader_started", "task_started", "ledger_repaired", "task_finished"])
        self.assertIsNone(led.truncated)

    def test_append_takes_the_ledger_lock_and_a_stale_lock_is_taken_over(self):
        led = Ledger(self.path)
        led.append(ev("leader_started", commit="abc1234"))
        lock = self.path + ".lock"
        self.assertFalse(os.path.exists(lock))                              # released after the append
        with open(lock, "w") as f:
            f.write("4242 0\n")
        os.utime(lock, (0, 0))                                               # a crashed holder, long ago
        led.append(ev("leader_started", commit="def5678"))                 # taken over
        self.assertEqual(len(led.read()), 2)
        self.assertFalse(os.path.exists(lock))
        with open(lock, "w") as f:
            f.write("4243 0\n")                                             # a live holder
        with self.assertRaises(OSError):
            with filelock.locked(lock, timeout_s=0.1):
                pass
        os.unlink(lock)
        with filelock.locked(lock, timeout_s=0.1):
            self.assertTrue(os.path.exists(lock))
        self.assertFalse(os.path.exists(lock))

    def test_a_stale_lock_that_cannot_be_removed_is_waited_for(self):
        lock = self.path + ".lock"
        os.makedirs(os.path.dirname(lock), exist_ok=True)
        with open(lock, "w") as f:
            f.write("4244 0\n")
        os.utime(lock, (0, 0))                                               # older than stale_s, and
        tries = []

        def held_open(path):                                                 # its holder still has it open (Windows)
            tries.append(path)
            if len(tries) > 1000:
                raise RuntimeError("spun on the lock without waiting")
            raise PermissionError(32, "The process cannot access the file because it is being used", path)

        with mock.patch.object(filelock.os, "unlink", held_open), self.assertRaises(TimeoutError):
            with filelock.locked(lock, timeout_s=0.2, poll_s=0.02):
                pass
        self.assertLess(len(tries), 100)                                     # it slept between tries
        os.unlink(lock)

    def test_a_lock_whose_age_cannot_be_read_is_waited_for(self):
        lock = self.path + ".lock"
        os.makedirs(os.path.dirname(lock), exist_ok=True)
        with open(lock, "w") as f:
            f.write("4244 0\n")
        real, tries = os.stat, []

        def unreadable(path, *a, **k):                                       # a dangling link, a denied lookup
            if path != lock:
                return real(path, *a, **k)
            tries.append(path)
            if len(tries) > 1000:
                raise RuntimeError("spun on the lock without waiting")
            raise PermissionError(13, "Access is denied", path)

        with mock.patch.object(filelock.os, "stat", unreadable), self.assertRaises(TimeoutError):
            with filelock.locked(lock, timeout_s=0.2, poll_s=0.02):
                pass
        self.assertLess(len(tries), 100)                                     # it slept between tries
        os.unlink(lock)

    def test_corrupt_middle_line_raises(self):
        for bad in ("not json", '{"t": "2026-10-15T12:00:00+00:00", "by": "x"}', "[]", '"ev"'):   # not an event
            led = Ledger(self.path + bad[:2].encode("ascii").hex())
            led.append(ev("leader_started", commit="abc1234"))
            with open(led.path, "a", encoding="utf-8") as f:
                f.write(bad + "\n")
            led.append(ev("leader_started", commit="def5678"))
            with self.assertRaises(ValueError, msg=bad):
                led.read()

    def test_whole_last_event_without_newline_is_kept_by_read_and_append(self):
        # the cut came after the closing brace: the event is complete, only its newline is missing
        led = Ledger(self.path)
        led.append(ev("leader_started", commit="abc1234"))
        led.append(ev("task_finished", task="walk_1", outcome="PASS"))
        with open(self.path, "rb+") as f:
            f.seek(-1, os.SEEK_END)
            f.truncate()
        self.assertEqual([e.ev for e in led.read()], ["leader_started", "task_finished"])
        self.assertIsNone(led.truncated)
        led.append(ev("task_queued", task="walk_2"))
        self.assertEqual([e.ev for e in led.read()], ["leader_started", "task_finished", "task_queued"])
        with open(self.path, "rb") as f:
            self.assertEqual(f.read().count(b"\n"), 3)


class FoldTests(unittest.TestCase):
    def test_skipped_and_circuit_broken_are_terminal_but_never_completed(self):
        s = fold([ev("task_queued", task="a"), ev("task_queued", task="b"), ev("task_queued", task="c"),
                  ev("task_finished", task="a", outcome="SKIPPED"),
                  ev("task_finished", task="b", outcome="CIRCUIT_BROKEN"),
                  ev("task_finished", task="c", outcome="PASS")])
        self.assertEqual({k: v["status"] for k, v in s.tasks.items()},
                         {"a": "skipped", "b": "circuit_broken", "c": "completed"})
        self.assertEqual(s.tasks_by_status().get("completed"), ["c"])

    def test_a_tasks_results_fold_in_row_order_not_in_append_order(self):
        """An import that recovers a lost live write appends an older results row after a newer result (§3, §10), so
        the fold orders a task's results by their results.jsonl line: the recovered older row never replaces the
        retry's verdict, a later row wins whatever its attempt number (a BREAKER row is attempt 0), and a result
        without a row (a worker's) still folds in append order."""
        rp = "C:\\Modding\\testqueue\\walk\\results.jsonl"
        older = ev("task_finished", task="walk/w1", outcome="INCONCLUSIVE", attempt=1, detail="NOOBS", src=rp + ":1")
        newer = ev("task_finished", task="walk/w1", outcome="PASS", attempt=2, completed=True, src=rp + ":2")
        for order in ((older, newer), (newer, older)):
            s = fold([ev("task_queued", task="walk/w1"), *order])
            t = s.tasks["walk/w1"]
            self.assertEqual((t["status"], t["outcome"], t["attempt"], t["detail"]), ("completed", "PASS", 2, ""))
            self.assertEqual((s.events, s.bad_events), (3, []))               # the older row is kept and counted
        breaker = ev("task_finished", task="walk/w1", outcome="CIRCUIT_BROKEN", attempt=0, src=rp + ":7")
        for order in ((older, newer, breaker), (breaker, older, newer)):
            t = fold(list(order)).tasks["walk/w1"]
            self.assertEqual((t["status"], t["attempt"]), ("circuit_broken", 0))
        worker = ev("task_finished", task="walk/w1", outcome="FAIL", attempt=3)
        self.assertEqual(fold([newer, worker]).tasks["walk/w1"]["outcome"], "FAIL")
        self.assertEqual(fold([worker, newer]).tasks["walk/w1"]["outcome"], "PASS")

    def test_only_an_in_game_pass_verifies(self):
        base = [ev("build_pinned", build_id="b1"), ev("capability_declared", capability="walk")]
        self.assertEqual(fold(base).capability("walk"), CapabilityState.UNTESTED)
        for src in (Source.OFFLINE, Source.SIMULATED, Source.HYPOTHESIS):
            s = fold(base + [ev("capability_result", capability="walk", outcome="PASS", source=src.value)])
            self.assertEqual(s.capability("walk"), CapabilityState.INCONCLUSIVE, src)
        for out in ("SKIPPED", "CIRCUIT_BROKEN"):
            s = fold(base + [ev("capability_result", capability="walk", outcome=out, source="IN_GAME")])
            self.assertEqual(s.capability("walk"), CapabilityState.UNTESTED, out)
        s = fold(base + [ev("capability_result", capability="walk", outcome="PASS", source="IN_GAME")])
        self.assertEqual(s.capability("walk"), CapabilityState.VERIFIED)
        # an offline result after the in-game verdict does not overwrite it; a new build starts untested
        s = fold(base + [ev("capability_result", capability="walk", outcome="PASS", source="IN_GAME"),
                         ev("capability_result", capability="walk", outcome="PASS", source="OFFLINE")])
        self.assertEqual(s.capability("walk"), CapabilityState.VERIFIED)
        self.assertEqual(s.capability("walk", "b2"), CapabilityState.UNTESTED)
        s = fold(base + [ev("capability_result", capability="walk", outcome="FAIL", source="IN_GAME")])
        self.assertEqual(s.capability("walk"), CapabilityState.FAILED)
        # a result pinned to another build stays out of the pinned build's bullets until that build is the pin
        s = fold(base + [ev("capability_result", capability="walk", outcome="PASS", source="IN_GAME", build_id="b2")])
        self.assertEqual(s.capability("walk"), CapabilityState.UNTESTED)
        self.assertNotIn("walk", s.report()[1])
        s = fold(base + [ev("capability_result", capability="walk", outcome="PASS", source="IN_GAME", build_id="b2"),
                         ev("build_pinned", build_id="b2")])
        self.assertEqual(s.capability("walk"), CapabilityState.VERIFIED)
        self.assertIn("walk", s.report()[1])

    def test_the_queue_bullet_lists_the_pinned_builds_tasks_only(self):
        s = fold([ev("task_queued", task="old/0000_fall", build_id="b1"), ev("task_queued", task="new/0000_fall", build_id="b2"),
                  ev("task_queued", task="hand/x"), ev("build_pinned", build_id="b2")])
        self.assertEqual(s.report()[7], "Next queue: new/0000_fall, hand/x")
        self.assertEqual(s.tasks_by_status()["queued"], ["old/0000_fall", "new/0000_fall", "hand/x"])

    def test_expired_lease_without_release_is_ambiguous(self):
        claim = ev("controller_claimed", owner="Claude", purpose="walk gate", expires="2026-10-15T13:00:00+00:00")
        self.assertEqual(fold([]).controller_status(), "none")
        self.assertEqual(fold([claim]).controller_status("2026-10-15T12:30:00+00:00"), "held")
        self.assertEqual(fold([claim]).controller_status("2026-10-15T13:00:00+00:00"), "ambiguous")
        renewed = ev("controller_renewed", owner="Claude", expires="2026-10-15T14:00:00+00:00")
        self.assertEqual(fold([claim, renewed]).controller_status("2026-10-15T13:30:00+00:00"), "held")
        self.assertEqual(fold([claim, ev("controller_released", owner="Claude")]).controller_status(), "released")
        # a renewal by someone else does not extend the holder's lease
        other = ev("controller_renewed", owner="Codex", expires="2026-10-15T20:00:00+00:00")
        self.assertEqual(fold([claim, other]).controller_status("2026-10-15T13:30:00+00:00"), "ambiguous")

    def test_plugins_verified_merges_by_name(self):
        exp = ev("plugins_verified", plugins=[{"name": "FO4SFExp.esm", "active_after_load": None}])
        bridge = ev("plugins_verified", plugins=[{"name": "FO4SFBridge.esm", "active_after_load": None}])
        s = fold([ev("build_pinned", build_id="b1"), exp, bridge])
        self.assertEqual([p["name"] for p in s.plugins], ["FO4SFExp.esm", "FO4SFBridge.esm"])   # one event per record, both kept
        # a later check of one plugin updates it in place (name matched without case); an unknown keeps the known value
        # while nothing says the file changed
        later = ev("plugins_verified", plugins=[{"name": "fo4sfexp.esm", "active_after_load": True}])
        s = fold([exp, bridge, later, exp])
        self.assertEqual([(p["name"], p["active_after_load"]) for p in s.plugins],
                         [("FO4SFExp.esm", True), ("FO4SFBridge.esm", None)])
        # a different sha256 is a different file: its load confirmation starts over (Codex on #136, 4ac6d46); an
        # explicit False stands; the same sha256 keeps the confirmation
        a = ev("plugins_verified", plugins=[{"name": "FO4SFExp.esm", "sha256": "aa" * 32, "active_after_load": True}])
        b = ev("plugins_verified", plugins=[{"name": "FO4SFExp.esm", "sha256": "bb" * 32, "active_after_load": None}])
        s = fold([a, b])
        self.assertEqual([(p["sha256"], p["active_after_load"]) for p in s.plugins], [("bb" * 32, None)])
        self.assertIn("FO4SFExp.esm (not confirmed after load)", s.report()[4])
        same = ev("plugins_verified", plugins=[{"name": "FO4SFExp.esm", "sha256": "aa" * 32, "active_after_load": None}])
        self.assertEqual(fold([a, same]).plugins[0]["active_after_load"], True)
        off = ev("plugins_verified", plugins=[{"name": "FO4SFExp.esm", "sha256": "aa" * 32, "active_after_load": False}])
        self.assertIs(fold([a, off]).plugins[0]["active_after_load"], False)
        # a record's event owns the names it lists: a rewritten record drops a plugin, an emptied one drops them all,
        # another record's entries stay; an event without a source removes nothing
        exp2 = ev("plugins_verified", source="FO4SFExp.install.json",
                  plugins=[{"name": "FO4SFExp.esm", "active_after_load": True}, {"name": "FO4TerrainCore.esm", "active_after_load": True}])
        br = ev("plugins_verified", source="FO4SFBridge.install.json", plugins=[{"name": "FO4SFBridge.esm", "active_after_load": True}])
        exp3 = ev("plugins_verified", source="FO4SFExp.install.json", plugins=[{"name": "FO4SFExp.esm", "active_after_load": True}])
        s = fold([exp2, br, exp3])
        self.assertEqual([p["name"] for p in s.plugins], ["FO4SFExp.esm", "FO4SFBridge.esm"])
        self.assertEqual([p.get("source") for p in s.plugins], ["FO4SFExp.install.json", "FO4SFBridge.install.json"])
        s = fold([exp2, br, ev("plugins_verified", source="FO4SFExp.install.json", plugins=[])])
        self.assertEqual([p["name"] for p in s.plugins], ["FO4SFBridge.esm"])
        s = fold([exp2, br, ev("plugins_verified", plugins=[{"name": "FO4SFBridge.esm", "active_after_load": False}])])
        self.assertEqual([p["name"] for p in s.plugins], ["FO4SFExp.esm", "FO4TerrainCore.esm", "FO4SFBridge.esm"])
        self.assertEqual(s.plugins[2]["source"], "FO4SFBridge.install.json")
        # a full snapshot replaces the list; a new pin clears it
        snap = ev("plugins_verified", replace=True, plugins=[{"name": "FO4SFBridge.esm", "active_after_load": True}],
                  load_order=["FO4SFBridge.esm"])
        s = fold([exp, bridge, snap])
        self.assertEqual([p["name"] for p in s.plugins], ["FO4SFBridge.esm"])
        self.assertEqual(s.load_order, ["FO4SFBridge.esm"])
        self.assertEqual(fold([exp, bridge, ev("build_pinned", build_id="b2")]).plugins, [])

    def test_report_counts_the_pinned_builds_tests(self):
        # F4 (the campaign on the owner's real records): runner results name no capability, so 88 FAILs read
        # "Failed: none"; a failed or skipped test must never read as success (project topic)
        s = fold([ev("build_pinned", build_id="b1"),
                  ev("task_finished", task="q/0001_walk", outcome="FAIL", completed=True, build_id="b1"),
                  ev("task_finished", task="q/0002_walk", outcome="PASS", completed=True, build_id="b1"),
                  ev("task_finished", task="q/0003_door", outcome="SKIPPED", build_id="b1"),
                  ev("task_finished", task="q/0004_door", outcome="CIRCUIT_BROKEN", build_id="b1"),
                  ev("task_finished", task="q/0005_cave", outcome="INCONCLUSIVE", build_id="b1"),
                  ev("task_finished", task="old/0009_walk", outcome="FAIL", completed=True, build_id="b0")])
        rep = s.report()
        self.assertEqual(rep[1], "Newly worked in game: nothing verified on this build; tests passed: 1 (0002_walk)")
        self.assertEqual(rep[2], "Failed: none; tests failed: 1 (0001_walk)")          # b0's failure is another build's
        self.assertEqual(rep[3], "Untested: none declared; tests not decided: 1 skipped, 1 circuit broken, 1 inconclusive")
        many = [ev("task_finished", task=f"q/{i:04d}_t", outcome="FAIL", completed=True) for i in range(8)]
        self.assertIn("tests failed: 8 (0000_t, 0001_t, 0002_t, 0003_t, 0004_t, 0005_t, +2 more)", fold(many).report()[2])
        self.assertEqual(fold([ev("build_pinned", build_id="b1")]).report()[2], "Failed: none")   # no tests: as before

    def test_report_has_the_eight_bullets(self):
        s = fold([ev("leader_started", commit="8cae1db"), ev("build_pinned", build_id="b1", commit="d628b56"),
                  ev("plugins_verified", plugins=[{"name": "FO4SFExp.esm", "active_after_load": True}]),
                  ev("capability_declared", capability="cave_entry"),
                  ev("capability_result", capability="walk_rr_sanctuary", outcome="PASS", source="IN_GAME"),
                  ev("controller_claimed", owner="Claude", purpose="walk gate", expires="2026-10-15T13:00:00+00:00"),
                  ev("blocker_opened", blocker="plugins deactivated after load", evidence=["#32 2026-10-13"]),
                  ev("task_queued", task="cave_probes11"), ev("task_queued", task="r05_medkit")])
        rep = s.report("2026-10-15T12:30:00+00:00")
        self.assertEqual(len(rep), 8)
        self.assertIn("walk_rr_sanctuary", rep[1])
        self.assertIn("cave_entry", rep[3])
        self.assertIn("build_id=b1", rep[4])
        self.assertIn("Claude (held", rep[5])
        self.assertIn("#32 2026-10-13", rep[6])
        self.assertEqual(rep[7], "Next queue: cave_probes11, r05_medkit")


class ImportTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.q = os.path.join(d.name, "walk_1015")
        os.makedirs(self.q)
        self.led = Ledger(os.path.join(d.name, "leader", "ledger.jsonl"))
        with open(os.path.join(self.q, "queue.json"), "w", encoding="utf-8") as f:
            json.dump({"created": "2026-10-15T10:00:00", "staging": "C:/staging", "plugin_sha256": "ab" * 32,
                       "build_id": "abababab", "commit": "d628b56",
                       "tests": [{"id": "w1", "kind": "travel", "cell": "SanctuaryExt", "ref": "0x1"},
                                 {"id": "w2", "kind": "travel", "cell": "SanctuaryExt", "ref": "0x2"},
                                 {"id": "w3", "kind": "stairs", "cell": "Library", "ref": "0x3"}]}, f)
        rows = [{"id": "w1", "kind": "travel", "cell": "SanctuaryExt", "ref": "0x1", "attempt": 1,
                 "verdict": "INCONCLUSIVE", "class": "UNREAD", "detail": "no shot", "dir": "w1_a1", "t": "t1"},
                {"id": "w1", "kind": "travel", "cell": "SanctuaryExt", "ref": "0x1", "attempt": 2,
                 "verdict": "PASS", "class": "", "detail": "", "dir": "w1_a2", "t": "t2"},
                {"id": "w3", "kind": "stairs", "cell": "Library", "ref": "0x3", "attempt": 0,
                 "verdict": "INCONCLUSIVE", "class": "BREAKER", "detail": "not run", "dir": "", "t": "t3"}]
        with open(os.path.join(self.q, "results.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            f.write('{"id": "w2", "verd')                  # the row in flight when the power went

    def test_import_is_idempotent_and_keeps_undecided_undecided(self):
        self.assertEqual(imp.import_queue(self.q, self.led), 1 + 3 + 3)
        self.assertEqual(imp.import_queue(self.q, self.led), 0)
        s = fold(self.led.read())
        self.assertEqual(s.build["build_id"], "abababab")
        self.assertEqual(s.tasks["walk_1015/w1"]["status"], "completed")
        self.assertEqual(s.tasks["walk_1015/w2"]["status"], "queued")  # its partial row is not a result
        self.assertEqual(s.tasks["walk_1015/w3"]["status"], "circuit_broken")
        self.assertEqual(s.campaigns, {"walk_1015"})
        self.assertNotIn("walk_1015/w3", s.tasks_by_status().get("completed", []))
        pin = next(e for e in self.led.read() if e.ev == "build_pinned")
        self.assertTrue(pin.t.endswith("+00:00"), pin.t)                   # the queue's local time stored as UTC
        # the source files were not written to
        with open(os.path.join(self.q, "results.jsonl"), encoding="utf-8") as f:
            self.assertTrue(f.read().endswith('{"id": "w2", "verd'))

    def test_campaigns_with_the_same_test_ids_never_merge(self):
        d = os.path.dirname(self.q)
        other = os.path.join(d, "walk_1016")
        shutil.copytree(self.q, other)
        with open(os.path.join(other, "results.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"id": "w1", "attempt": 1, "verdict": "FAIL", "class": "FALL", "dir": "w1_a1", "t": "t1"}) + "\n")
        imp.import_queue(self.q, self.led)
        imp.import_queue(other, self.led)
        s = fold(self.led.read())
        self.assertEqual((s.tasks["walk_1015/w1"]["outcome"], s.tasks["walk_1016/w1"]["outcome"]), ("PASS", "FAIL"))
        self.assertEqual(s.campaigns, {"walk_1015", "walk_1016"})

    def test_a_pin_rewritten_in_place_is_a_new_event_and_a_bom_is_fine(self):
        self.assertEqual(imp.import_queue(self.q, self.led), 7)
        qp = os.path.join(self.q, "queue.json")
        with open(qp, encoding="utf-8") as f:
            q = json.load(f)
        q["game_version"] = "1.16.244.0"
        with open(qp, "wb") as f:
            f.write(b"\xef\xbb\xbf" + json.dumps(q).encode("utf-8"))      # pin-game-version, then a hand edit with a BOM
        self.assertEqual(imp.import_queue(self.q, self.led), 1)               # one new build_pinned, nothing else twice
        s = fold(self.led.read())
        self.assertEqual(s.build.get("game_version"), "1.16.244.0")
        self.assertEqual(len([e for e in self.led.read() if e.ev == "task_queued"]), 3)

    def test_install_and_deploy_records(self):
        d = os.path.dirname(self.q)
        inst = os.path.join(d, "FO4SFExp.install.json")
        with open(inst, "w", encoding="utf-8") as f:
            json.dump({"plugins": ["FO4SFExp.esm"], "plugins_replaced": [{"active": "*FO4SFBridge.esm", "original": ""}],
                       "complete": True, "pack": "core64c"}, f)
        dep = os.path.join(d, "FO4Port.deploy.json")

        def deploy(sha, complete=True):                                 # the shape deploy_starfield.py install writes
            with open(dep, "w", encoding="utf-8") as f:
                json.dump({"files": ["FO4Port.esm", "FO4Port - Main.ba2"], "published_files": ["FO4Port.esm"],
                           "plugins_added": ["*FO4Port.esm"], "plugins_replaced": [], "complete": complete,
                           "artifacts": {"FO4Port.esm": {"size": 12, "sha256": sha},
                                         "FO4Port - Main.ba2": {"size": 34, "sha256": "cd" * 32}}}, f)
        deploy("ab" * 32)
        # a pin comes first; plugins are verified against it (a later re-pin clears them again)
        self.assertEqual(imp.import_deploy(dep, self.led), 1)
        self.assertEqual(imp.import_deploy(dep, self.led), 0)
        self.assertEqual(imp.import_install(inst, self.led), 1)
        self.assertEqual(imp.import_install(inst, self.led), 0)
        s = fold(self.led.read())
        self.assertEqual([p["name"] for p in s.plugins], ["FO4SFExp.esm", "FO4SFBridge.esm"])
        self.assertIsNone(s.plugins[0]["active_after_load"])            # unknown until exp_install.py active says so
        self.assertEqual(s.build, {"build_id": "abababab", "plugin_sha256": "ab" * 32})
        # the same path rewritten by the next deploy is a new pin, and an interrupted install is recorded as such
        deploy("ef" * 32, complete=False)
        self.assertEqual(imp.import_deploy(dep, self.led), 1)
        s = fold(self.led.read())
        self.assertEqual(s.build, {"build_id": "efefefef", "plugin_sha256": "ef" * 32})
        self.assertEqual(s.plugins, [])                                   # a new pin clears the verified plugins
        self.assertIs([e for e in self.led.read() if e.ev == "build_pinned"][-1].get("complete"), False)
        # an install record rewritten with new content is a new event too
        with open(inst, "w", encoding="utf-8") as f:
            json.dump({"plugins": ["FO4SFExp.esm"], "plugins_replaced": [], "complete": True, "pack": "core64d"}, f)
        self.assertEqual(imp.import_install(inst, self.led), 1)
        self.assertEqual([p["name"] for p in fold(self.led.read()).plugins], ["FO4SFExp.esm"])
        # a re-deploy of the first build (the same bytes, a new file) is a new pin, not "already imported"
        deploy("ab" * 32)
        os.utime(dep, (1_800_000_000, 1_800_000_000))
        self.assertEqual(imp.import_deploy(dep, self.led), 1)
        self.assertEqual(fold(self.led.read()).build["build_id"], "abababab")

    def test_install_record_shapes(self):
        d = os.path.dirname(self.q)
        bridge = os.path.join(d, "FO4SFBridge.install.json")       # bridge_install.py: one `plugin`
        with open(bridge, "w", encoding="utf-8") as f:
            json.dump({"schema": 2, "plugin": "FO4SFBridge.esm", "files": {}, "complete": True}, f)
        old = os.path.join(d, "FO4SFExp.install.json")             # exp_install.py before 270b0ec: `plugins_added` only
        with open(old, "w", encoding="utf-8") as f:
            json.dump({"plugins_added": ["*FO4SFExp.esm"], "plugins_replaced": [], "complete": True}, f)
        self.assertEqual(imp.import_install(old, self.led, active_after_load=True), 1)
        self.assertEqual(imp.import_install(bridge, self.led), 1)
        s = fold(self.led.read())
        self.assertEqual([p["name"] for p in s.plugins], ["FO4SFExp.esm", "FO4SFBridge.esm"])   # both records, both plugins
        self.assertIn("plugins: FO4SFExp.esm, FO4SFBridge.esm (not confirmed after load)", s.report()[4])
        # a current exp record names the plugin in `plugins` and `plugins_added` alike: once, and the known
        # active_after_load survives an import that does not know it
        with open(old, "w", encoding="utf-8") as f:
            json.dump({"plugins": ["FO4SFExp.esm"], "plugins_added": ["*FO4SFExp.esm"], "plugins_replaced": [],
                       "complete": True, "pack": "core64d"}, f)
        self.assertEqual(imp.import_install(old, self.led), 1)
        s = fold(self.led.read())
        self.assertEqual([(p["name"], p["active_after_load"]) for p in s.plugins],
                         [("FO4SFExp.esm", True), ("FO4SFBridge.esm", None)])
        self.assertEqual(imp.record_plugins({"plugins": ["A.esm"], "plugins_added": ["*a.esm", "*B.esm"], "plugin": "C.esm",
                                             "plugins_replaced": [{"active": "*D.esm", "original": ""}, "junk"]}),
                         ["A.esm", "B.esm", "C.esm", "D.esm"])

    def test_install_record_identity_and_ownership(self):
        d = os.path.dirname(self.q)
        exp = os.path.join(d, "FO4SFExp.install.json")
        bridge = os.path.join(d, "FO4SFBridge.install.json")

        def write(path, body):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(body, f)
        # the record's file digests ride on the event; the bridge record keeps its plugin's digest in source_sha256
        write(exp, {"plugins": ["FO4SFExp.esm", "FO4TerrainCore.esm"], "plugins_replaced": [], "complete": True,
                    "files": {"FO4SFExp.esm": "aa" * 32, "FO4SFExp - Main.ba2": "cc" * 32, "FO4TerrainCore.esm": "dd" * 32}})
        write(bridge, {"schema": 2, "plugin": "FO4SFBridge.esm", "source_sha256": {"FO4SFBridge.esm": "ee" * 32},
                       "files": {"FO4SFBridge - Main.ba2": "ff" * 32}, "complete": True})
        self.assertEqual(imp.import_install(exp, self.led, active_after_load=True), 1)
        self.assertEqual(imp.import_install(bridge, self.led, active_after_load=True), 1)
        s = fold(self.led.read())
        self.assertEqual([(p["name"], p["sha256"], p["active_after_load"], p["source"]) for p in s.plugins],
                         [("FO4SFExp.esm", "aa" * 32, True, "FO4SFExp.install.json"),
                          ("FO4TerrainCore.esm", "dd" * 32, True, "FO4SFExp.install.json"),
                          ("FO4SFBridge.esm", "ee" * 32, True, "FO4SFBridge.install.json")])
        # the same receipt rewritten with a new plugin file and no load check: that plugin is unconfirmed again, the
        # unchanged one keeps its confirmation, the bridge is untouched (Codex on #136, 4ac6d46, first P2)
        write(exp, {"plugins": ["FO4SFExp.esm", "FO4TerrainCore.esm"], "plugins_replaced": [], "complete": True,
                    "files": {"FO4SFExp.esm": "ab" * 32, "FO4SFExp - Main.ba2": "cc" * 32, "FO4TerrainCore.esm": "dd" * 32}})
        self.assertEqual(imp.import_install(exp, self.led), 1)
        s = fold(self.led.read())
        self.assertEqual([(p["name"], p["active_after_load"]) for p in s.plugins],
                         [("FO4SFExp.esm", None), ("FO4TerrainCore.esm", True), ("FO4SFBridge.esm", True)])
        self.assertIn("FO4SFExp.esm (not confirmed after load), FO4TerrainCore.esm, FO4SFBridge.esm", s.report()[4])
        # the receipt rewritten without Terrain: Terrain goes, the bridge record's entry stays (second P2); an emptied
        # receipt drops the rest of its own entries and nothing else
        write(exp, {"plugins": ["FO4SFExp.esm"], "plugins_replaced": [], "complete": True, "files": {"FO4SFExp.esm": "ab" * 32}})
        self.assertEqual(imp.import_install(exp, self.led), 1)
        self.assertEqual([p["name"] for p in fold(self.led.read()).plugins], ["FO4SFExp.esm", "FO4SFBridge.esm"])
        write(exp, {"plugins": [], "plugins_added": [], "plugins_replaced": [], "complete": True, "files": {}})
        self.assertEqual(imp.import_install(exp, self.led), 1)
        self.assertEqual([p["name"] for p in fold(self.led.read()).plugins], ["FO4SFBridge.esm"])
        self.assertEqual(imp.record_sha256({"files": {"Data\\Sub\\X.esm": "11" * 32}}, "x.esm"), "11" * 32)
        self.assertIsNone(imp.record_sha256({"files": "junk"}, "x.esm"))

    def test_deploy_pins_explicit_keys_win(self):
        self.assertEqual(imp.deploy_pins({"artifacts": {"FO4Port.esm": {"sha256": "ab" * 32}}}),
                         {"plugin_sha256": "ab" * 32, "build_id": "abababab"})
        self.assertEqual(imp.deploy_pins({"build_id": "custom01", "artifacts": {"FO4Port.esm": {"sha256": "ab" * 32}}}),
                         {"build_id": "custom01", "plugin_sha256": "ab" * 32})
        self.assertEqual(imp.deploy_pins({"files": ["FO4Port.esm"]}), {})


if __name__ == "__main__":
    unittest.main()
