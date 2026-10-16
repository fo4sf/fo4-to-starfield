"""Leader core (docs/ai/leader-core.md): synthetic ledgers and queue folders only; nothing touches a game."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.core.model import CapabilityState, Event, Outcome, Source, outcome_from_queue  # noqa: E402
from fo4sf.core.state import Ledger, fold  # noqa: E402
from fo4sf.core import import_queue as imp  # noqa: E402


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
        with self.assertRaises(ValueError):
            ev("made_up_event")


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
        self.assertEqual(s.tasks["w1"]["status"], "completed")
        self.assertEqual(s.tasks["w2"]["status"], "queued")            # its partial row is not a result
        self.assertEqual(s.tasks["w3"]["status"], "circuit_broken")
        self.assertEqual(s.campaigns, {"walk_1015"})
        self.assertNotIn("w3", s.tasks_by_status().get("completed", []))
        # the source files were not written to
        with open(os.path.join(self.q, "results.jsonl"), encoding="utf-8") as f:
            self.assertTrue(f.read().endswith('{"id": "w2", "verd'))

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

    def test_deploy_pins_explicit_keys_win(self):
        self.assertEqual(imp.deploy_pins({"artifacts": {"FO4Port.esm": {"sha256": "ab" * 32}}}),
                         {"plugin_sha256": "ab" * 32, "build_id": "abababab"})
        self.assertEqual(imp.deploy_pins({"build_id": "custom01", "artifacts": {"FO4Port.esm": {"sha256": "ab" * 32}}}),
                         {"build_id": "custom01", "plugin_sha256": "ab" * 32})
        self.assertEqual(imp.deploy_pins({"files": ["FO4Port.esm"]}), {})


if __name__ == "__main__":
    unittest.main()
