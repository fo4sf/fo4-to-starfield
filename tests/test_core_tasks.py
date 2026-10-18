"""Task cards, the worker result contract and the report CLI (docs/ai/leader-core.md section 8): synthetic ledgers
only; nothing runs a task or touches a game."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.core import report, tasks, worker  # noqa: E402
from fo4sf.core.model import CapabilityState, Event  # noqa: E402
from fo4sf.core.state import Ledger, fold  # noqa: E402

T0 = "2026-10-16T07:00:00+00:00"


def card(**kw):
    base = dict(id="walk_rr", objective="walk Red Rocket -> Sanctuary on the pinned build", owner="Claude",
                acceptance=["goal reached within 1 m", "every read via the bridge"], evidence_required=["bridge reads"],
                capability="walk_rr_sanctuary", campaign="final-1016", timeout_s=600, max_attempts=2)
    base.update(kw)
    return tasks.TaskCard(**base)


class CardTests(unittest.TestCase):
    def test_round_trip_and_defaults(self):
        c = card()
        again = tasks.TaskCard.from_json(c.to_json())
        self.assertEqual(again, c)
        self.assertEqual(again.inputs, [])
        self.assertEqual(again.max_attempts, 2)
        self.assertIn("checkpoint", again.recovery)

    def test_refusals_name_the_field(self):
        cases = [
            (dict(objective=" "), "objective"), (dict(owner=""), "owner"), (dict(id=""), "id"),
            (dict(acceptance=[]), "acceptance"), (dict(evidence_required=[]), "evidence_required"),
            (dict(acceptance=["ok", ""]), "acceptance"), (dict(timeout_s=0), "timeout_s"),
            (dict(max_attempts=True), "max_attempts"), (dict(max_attempts=-1), "max_attempts"),
            (dict(dependencies=["walk_rr"]), "dependencies"), (dict(capability=""), "capability"),
            (dict(inputs="PR #136"), "inputs"), (dict(recovery=None), "recovery"), (dict(recovery=" "), "recovery"),
        ]
        for kw, field in cases:
            with self.assertRaises(tasks.CardError, msg=kw) as cm:
                card(**kw)
            self.assertIn(field, str(cm.exception), kw)
        with self.assertRaises(tasks.CardError) as cm:
            tasks.TaskCard.from_dict(dict(card().to_dict(), colour="red"))
        self.assertIn("unknown card field(s): colour", str(cm.exception))
        with self.assertRaises(tasks.CardError) as cm:
            tasks.TaskCard.from_dict({"id": "x", "objective": "y"})
        self.assertIn("missing: owner, acceptance, evidence_required", str(cm.exception))
        with self.assertRaises(tasks.CardError) as cm:
            tasks.TaskCard.from_json("{not json")
        self.assertIn("not JSON", str(cm.exception))
        with self.assertRaises(tasks.CardError):
            tasks.TaskCard.from_dict(["a", "list"])

    def test_the_evidence_rule_none_is_a_choice(self):
        self.assertTrue(card().needs_evidence)
        self.assertFalse(card(evidence_required=["none"]).needs_evidence)
        self.assertFalse(card(evidence_required=[" None "]).needs_evidence)
        self.assertTrue(card(evidence_required=["none", "a read"]).needs_evidence)

    def test_queueing_events_and_readiness(self):
        c = card()
        evs = c.events("leader", t=T0)
        self.assertEqual([e.ev for e in evs], ["task_queued"])
        self.assertEqual((evs[0].get("owner"), evs[0].get("campaign"), evs[0].get("capability")), ("Claude", "final-1016", "walk_rr_sanctuary"))
        self.assertEqual(evs[0].get("card")["acceptance"], c.acceptance)
        self.assertEqual(tasks.TaskCard.from_event(evs[0]), c)
        with self.assertRaises(tasks.CardError):
            tasks.TaskCard.from_event(Event("task_started", "t", fields={"task": "walk_rr"}))
        s = fold(evs)
        self.assertEqual((s.tasks["walk_rr"]["status"], s.tasks["walk_rr"]["owner"]), ("queued", "Claude"))
        self.assertEqual(tasks.TaskCard.from_event(s.cards["walk_rr"]), c)
        dep = card(id="cave_door", dependencies=["walk_rr"])
        self.assertIn("not in the ledger", dep.not_ready(fold([])))
        self.assertIn("queued", dep.not_ready(s))
        s = fold(evs + [Event("task_started", "t", fields={"task": "walk_rr"})])
        self.assertIn("running", dep.not_ready(s))
        s = fold(evs + [Event("task_finished", "t", fields={"task": "walk_rr", "outcome": "FAIL"})])
        self.assertIn("FAIL", dep.not_ready(s))
        s = fold(evs + [Event("task_finished", "t", fields={"task": "walk_rr", "outcome": "PASS"})])
        self.assertIsNone(dep.not_ready(s))


class WorkerTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = os.path.join(d.name, "leader")
        self.led = Ledger(os.path.join(self.dir, "ledger.jsonl"))
        self.led.append(Event("build_pinned", "t", t=T0, fields={"build_id": "b1", "plugin_sha256": "ab" * 32}))
        self.card = card()
        for e in self.card.events("leader", t=T0):
            self.led.append(e)
        self.w = worker.Worker(self.led, "test")

    def result(self, **kw):
        base = dict(task="walk_rr", attempt=1, outcome="PASS", source="IN_GAME", evidence=["bridge.log:42"],
                    pins={"build_id": "b1", "commit": "33a9079"})
        base.update(kw)
        return worker.WorkerResult(**base)

    def kinds(self):
        return [e.ev for e in self.led.read()]

    def test_start_finish_pass_verifies_the_capability_on_the_pinned_build(self):
        self.w.start(self.card, now=T0)
        s = fold(self.led.read())
        self.assertEqual((s.tasks["walk_rr"]["status"], s.tasks["walk_rr"]["attempt"]), ("running", 1))
        evs = self.w.finish(self.card, self.result(), now="2026-10-16T07:10:00+00:00")
        self.assertEqual([e.ev for e in evs], ["task_finished", "capability_result"])
        self.assertIs(evs[0].get("completed"), True)
        s = fold(self.led.read())
        self.assertEqual(s.tasks["walk_rr"]["status"], "completed")
        self.assertEqual(s.capability("walk_rr_sanctuary"), CapabilityState.VERIFIED)
        self.assertIn("walk_rr_sanctuary", s.report()[1])
        self.assertEqual(s.campaigns, {"final-1016"})

    def test_undecided_outcomes_never_complete_and_never_verify(self):
        for outcome, status, cap in (("SKIPPED", "skipped", CapabilityState.UNTESTED),
                                     ("CIRCUIT_BROKEN", "circuit_broken", CapabilityState.UNTESTED),
                                     ("INCONCLUSIVE", "inconclusive", CapabilityState.INCONCLUSIVE)):
            c = card(id=f"t_{outcome.lower()}", capability=f"cap_{outcome.lower()}")
            for e in c.events("leader", t=T0):
                self.led.append(e)
            self.w.start(c, now=T0)
            evs = self.w.finish(c, self.result(task=c.id, outcome=outcome, evidence=[]), now=T0)
            self.assertIs(evs[0].get("completed"), False)
            # a skip or a broken circuit says nothing about the capability: only INCONCLUSIVE leaves a capability_result
            self.assertEqual(len(evs), 2 if outcome == "INCONCLUSIVE" else 1, outcome)
            s = fold(self.led.read())
            self.assertEqual(s.tasks[c.id]["status"], status, outcome)
            self.assertEqual(s.capability(c.capability), cap, outcome)
            self.assertNotIn(c.id, s.tasks_by_status().get("completed", []))

    def test_a_fail_completes_and_marks_the_capability_failed(self):
        self.w.start(self.card, now=T0)
        self.w.finish(self.card, self.result(outcome="FAIL", detail="1.0 m from the door, no load"), now=T0)
        s = fold(self.led.read())
        self.assertEqual((s.tasks["walk_rr"]["status"], s.tasks["walk_rr"]["outcome"]), ("completed", "FAIL"))
        self.assertEqual(s.capability("walk_rr_sanctuary"), CapabilityState.FAILED)
        self.assertIn("walk_rr_sanctuary", s.report()[2])

    def test_contract_violations_are_refused_before_anything_is_written(self):
        self.w.start(self.card, now=T0)
        n = len(self.led.read())
        cases = [
            (dict(evidence=[]), "needs evidence"),
            (dict(attempt=3), "beyond the card's max_attempts"),
            (dict(started="2026-10-16T07:00:00"), "naive time"),
            (dict(finished="later"), "not an ISO timestamp"),
            (dict(started=""), "started: an ISO timestamp"),
            (dict(attempt=0), "attempt"),
            (dict(outcome="DONE"), "outcome: unknown"),
            (dict(source="GUESS"), "source: unknown"),
            (dict(source="OFFLINE", verified=True), "only an IN_GAME PASS verifies"),
            (dict(outcome="FAIL", verified=True), "only an IN_GAME PASS verifies"),
            (dict(task="other"), "task:"),
            (dict(evidence=["", "x"]), "evidence:"),
            (dict(pins=[]), "pins:"),
        ]
        for kw, msg in cases:
            with self.assertRaises(worker.ContractError, msg=kw) as cm:
                self.w.finish(self.card, self.result(**kw), now=T0)
            self.assertIn(msg, str(cm.exception), kw)
            self.assertEqual(len(self.led.read()), n, kw)
        plain = card(id="doc", capability=None)
        self.assertIn("names no capability", "; ".join(worker.violations(plain, self.result(task="doc", verified=True))))
        none = card(id="doc", capability=None, evidence_required=["none"])
        self.assertEqual(worker.violations(none, self.result(task="doc", evidence=[])), [])   # "none" is a choice
        with self.assertRaises(worker.ContractError) as cm:
            self.w.finish(self.card, self.result(), now="2026-10-16T07:10:00")                # a naive now
        self.assertIn("now: a naive time", str(cm.exception))
        self.assertEqual(len(self.led.read()), n)
        offline_pass = self.result(source="OFFLINE")            # allowed: recorded, the fold keeps it inconclusive
        self.assertEqual(worker.violations(self.card, offline_pass), [])
        self.w.finish(self.card, offline_pass, now=T0)
        self.assertEqual(fold(self.led.read()).capability("walk_rr_sanctuary"), CapabilityState.INCONCLUSIVE)

    def test_transitions_follow_the_ledger(self):
        with self.assertRaises(worker.ContractError) as cm:
            self.w.finish(self.card, self.result(), now=T0)
        self.assertIn("not running", str(cm.exception))
        self.w.start(self.card, now=T0)
        with self.assertRaises(worker.ContractError) as cm:
            self.w.start(self.card, now=T0)
        self.assertIn("running or lost", str(cm.exception))
        with self.assertRaises(worker.ContractError) as cm:
            self.w.finish(self.card, self.result(attempt=2), now=T0)
        self.assertIn("attempt 1 is running", str(cm.exception))
        self.w.finish(self.card, self.result(outcome="INCONCLUSIVE", evidence=[]), now=T0)
        for given, msg in ((1, "the ledger's next attempt of walk_rr is 2"), (3, "the ledger's next attempt"),
                           (0, "attempt: a positive integer"), (True, "attempt: a positive integer"), (-1, "positive")):
            with self.assertRaises(worker.ContractError, msg=given) as cm:
                self.w.start(self.card, attempt=given, now=T0)   # an explicit attempt is the ledger's next, or refused
            self.assertIn(msg, str(cm.exception))
        self.w.start(self.card, attempt=2, now=T0)                # attempt 2, the last the card allows
        self.assertEqual(fold(self.led.read()).tasks["walk_rr"]["attempt"], 2)
        self.w.finish(self.card, self.result(attempt=2, outcome="INCONCLUSIVE", evidence=[]), now=T0)
        with self.assertRaises(worker.ContractError) as cm:
            self.w.start(self.card, now=T0)
        self.assertIn("beyond the card's max_attempts", str(cm.exception))
        done = card(id="done_one")
        for e in done.events("leader", t=T0):
            self.led.append(e)
        self.w.start(done, now=T0)
        self.w.finish(done, self.result(task="done_one"), now=T0)
        with self.assertRaises(worker.ContractError) as cm:
            self.w.start(done, now=T0)
        self.assertIn("is completed", str(cm.exception))
        dep = card(id="cave_door", dependencies=["walk_rr"])
        for e in dep.events("leader", t=T0):
            self.led.append(e)
        with self.assertRaises(worker.ContractError) as cm:
            self.w.start(dep, now=T0)
        self.assertIn("not a PASS", str(cm.exception))

    def test_a_timeout_expires_as_inconclusive_and_the_task_can_be_retried(self):
        self.w.start(self.card, now=T0)
        self.assertEqual(self.w.running_since("walk_rr"), (1, T0))
        self.assertIsNone(self.w.expire(self.card, now="2026-10-16T07:05:00+00:00"))
        ev = self.w.expire(self.card, now="2026-10-16T07:10:01+00:00")
        self.assertEqual((ev.ev, ev.get("outcome"), ev.get("expired"), ev.get("completed")), ("task_finished", "INCONCLUSIVE", True, False))
        self.assertIn("timeout: attempt 1 ran 601 s, the card allows 600 s", ev.get("detail"))
        self.assertEqual(self.kinds()[-2:], ["task_finished", "capability_result"])   # as a worker's INCONCLUSIVE would
        s = fold(self.led.read())
        self.assertEqual(s.tasks["walk_rr"]["status"], "inconclusive")
        self.assertEqual(s.capability("walk_rr_sanctuary"), CapabilityState.INCONCLUSIVE)
        self.assertIn("inconclusive: walk_rr_sanctuary", s.report()[2])
        self.assertIsNone(self.w.running_since("walk_rr"))
        self.assertIsNone(self.w.expire(self.card, now="2026-10-16T08:00:00+00:00"))
        self.w.start(self.card, now="2026-10-16T07:11:00+00:00")
        self.assertEqual(fold(self.led.read()).tasks["walk_rr"]["attempt"], 2)
        with self.assertRaises(worker.ContractError):
            self.w.expire(self.card, now="2026-10-16 09:00:00")                         # a naive now never ages a task

    def test_a_crash_between_the_two_appends_loses_no_verdict(self):
        self.w.start(self.card, now=T0)
        self.w.finish(self.card, self.result(by="runner", verified=True), now="2026-10-16T07:10:00+00:00")
        evs = self.led.read()
        self.assertEqual((evs[-2].ev, evs[-1].ev), ("task_finished", "capability_result"))
        self.assertEqual((evs[-2].get("worker"), evs[-2].get("verified")), ("runner", True))
        self.assertEqual((evs[-2].get("capability"), evs[-2].get("build_id")), ("walk_rr_sanctuary", "b1"))
        s = fold(evs[:-1])                                                               # the power went before the second
        self.assertEqual(s.tasks["walk_rr"]["status"], "completed")
        self.assertEqual(s.capability("walk_rr_sanctuary"), CapabilityState.VERIFIED)
        self.assertEqual(s.capabilities, fold(evs).capabilities)                         # the second append repeats it

    def test_a_result_pinned_to_another_build_waits_for_that_pin(self):
        self.w.start(self.card, now=T0)
        self.w.finish(self.card, self.result(pins={"build_id": "b2"}), now=T0)
        s = fold(self.led.read())
        self.assertEqual(s.capability("walk_rr_sanctuary"), CapabilityState.UNTESTED)   # the pin is b1
        self.assertEqual(s.capability("walk_rr_sanctuary", "b2"), CapabilityState.VERIFIED)
        self.assertIn("nothing verified on this build", s.report()[1])
        self.led.append(Event("build_pinned", "t", t=T0, fields={"build_id": "b2"}))
        self.assertIn("walk_rr_sanctuary", fold(self.led.read()).report()[1])

    def test_the_queued_card_is_the_authority(self):
        self.assertEqual(self.w.queue(self.card), [])                                   # queued already (setUp): nothing twice
        other = card(id="walk_rr", timeout_s=99999, max_attempts=9)
        with self.assertRaises(worker.ContractError) as cm:
            self.w.queue(other)
        self.assertIn("differs from the one queued", str(cm.exception))
        self.assertIn("max_attempts", str(cm.exception))
        for call in (lambda: self.w.start(other, now=T0), lambda: self.w.finish(other, self.result(), now=T0),
                     lambda: self.w.expire(other, now=T0)):
            with self.assertRaises(worker.ContractError) as cm:
                call()
            self.assertIn("differs from the one queued", str(cm.exception))
        fresh = card(id="never_queued")
        with self.assertRaises(worker.ContractError) as cm:
            self.w.start(fresh, now=T0)
        self.assertIn("not queued", str(cm.exception))
        self.assertEqual([e.ev for e in self.w.queue(fresh, now=T0)], ["task_queued"])
        self.w.start(fresh, now=T0)
        # two writers queue two cards under one id: the first stands and nothing runs until the ledger says which
        twin = card(id="twin")
        self.led.append(twin.events("a", t=T0)[0])
        self.led.append(card(id="twin", objective="something else").events("b", t=T0)[0])
        s = fold(self.led.read())
        self.assertEqual((s.card_conflicts, s.cards["twin"]["objective"]), ({"twin"}, twin.objective))
        with self.assertRaises(worker.ContractError) as cm:
            self.w.start(twin, now=T0)
        self.assertIn("two different cards", str(cm.exception))
        self.assertIn("two cards queued under one id: twin", s.report()[6])
        bare = Event("task_queued", "runner", fields={"task": "bare"})                   # a runner's line carries no card
        self.led.append(bare)
        with self.assertRaises(worker.ContractError) as cm:
            self.w.queue(card(id="bare"))
        self.assertIn("without a card", str(cm.exception))

    def test_a_resumed_leader_rebuilds_the_card_from_the_ledger(self):
        self.w.start(self.card, now=T0)
        again = worker.Worker(Ledger(self.led.path), "resumed")                          # another process, same file
        s = again.state()
        rebuilt = tasks.TaskCard.from_event(s.cards["walk_rr"])
        self.assertEqual(rebuilt, self.card)
        ev = again.expire(rebuilt, now="2026-10-16T07:10:01+00:00")
        self.assertEqual((ev.by, ev.get("expired")), ("resumed", True))
        again.start(rebuilt, now="2026-10-16T07:11:00+00:00")
        self.assertEqual(again.state().tasks["walk_rr"]["attempt"], 2)


class ReportCliTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = os.path.join(d.name, "leader")
        led = Ledger(os.path.join(self.dir, "ledger.jsonl"))
        for e in (Event("leader_started", "t", t=T0, fields={"commit": "33a9079", "branch": "claude/leader-core-tasks"}),
                  Event("build_pinned", "t", t=T0, fields={"build_id": "b1", "plugin_sha256": "ab" * 32}),
                  Event("plugins_verified", "t", t=T0, fields={"plugins": [{"name": "FO4SFExp.esm", "active_after_load": True}]}),
                  Event("capability_declared", "t", t=T0, fields={"capability": "cave_door"}),
                  Event("capability_result", "t", t=T0, fields={"capability": "walk_rr_sanctuary", "outcome": "PASS", "source": "IN_GAME"}),
                  Event("controller_claimed", "t", t=T0, fields={"owner": "Claude", "purpose": "window", "expires": "2026-10-16T08:00:00+00:00"}),
                  Event("blocker_opened", "t", t=T0, fields={"blocker": "preflight", "evidence": ["UNKNOWN game_version"]}),
                  Event("task_queued", "t", t=T0, fields={"task": "r05_medkit"})):
            led.append(e)

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = report.main(list(argv))
        return code, out.getvalue().strip().splitlines()

    def test_eight_bullets_from_a_folder_or_a_file(self):
        code, lines = self.run_cli("--ledger", self.dir, "--now", "2026-10-16T07:30:00+00:00")
        self.assertEqual(code, 0)
        self.assertEqual(len(lines), 8)
        self.assertTrue(all(ln.startswith("- ") for ln in lines))
        self.assertEqual(lines[0], "- Core changes: 33a9079")
        self.assertEqual(lines[1], "- Newly worked in game: walk_rr_sanctuary")
        self.assertEqual(lines[3], "- Untested: cave_door")
        self.assertIn("build_id=b1", lines[4])
        self.assertIn("Claude (held, window)", lines[5])
        self.assertIn("preflight: UNKNOWN game_version", lines[6])
        self.assertEqual(lines[7], "- Next queue: r05_medkit")
        code, lines2 = self.run_cli("--ledger", os.path.join(self.dir, "ledger.jsonl"), "--now", "2026-10-16T07:30:00+00:00")
        self.assertEqual((code, lines2), (0, lines))
        code, lines3 = self.run_cli("--ledger", self.dir, "--now", "2026-10-16T09:00:00+00:00")   # the lease has expired
        self.assertIn("Claude (ambiguous, window)", lines3[5])

    def test_json_and_failures(self):
        code, lines = self.run_cli("--ledger", self.dir, "--json", "--now", "2026-10-16T07:30:00+00:00")
        j = json.loads(lines[0])
        self.assertEqual((code, len(j["bullets"]), j["controller"], j["events"], j["blockers"]), (0, 8, "held", 8, ["preflight"]))
        self.assertEqual(j["tasks"], {"queued": ["r05_medkit"]})
        code, lines = self.run_cli("--ledger", os.path.join(self.dir, "nope"))
        self.assertEqual(code, 1)
        self.assertIn("no ledger at", lines[0])
        with open(os.path.join(self.dir, "ledger.jsonl"), "a", encoding="utf-8") as f:
            f.write("corrupt\n{\"t\": \"x\", \"ev\": \"leader_started\", \"by\": \"t\"}\n")
        code, lines = self.run_cli("--ledger", self.dir)
        self.assertEqual(code, 1)
        self.assertIn("corrupt line", lines[0])

    def test_a_wrongly_shaped_field_is_a_blocker_in_the_report_not_a_traceback(self):
        # parseable JSON, the key field present, but a dict where a task name belongs, and a lease whose expiry is a
        # number: the fold skips each line, the report names them, the rest of the ledger still reads
        with open(os.path.join(self.dir, "ledger.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": T0, "ev": "task_finished", "by": "t", "task": {"id": "r05"}, "outcome": "PASS",
                                "source": "IN_GAME"}) + "\n")
            f.write(json.dumps({"t": T0, "ev": "controller_claimed", "by": "t", "owner": "Codex", "expires": 42}) + "\n")
        code, lines = self.run_cli("--ledger", self.dir, "--now", "2026-10-16T07:30:00+00:00")
        self.assertEqual(code, 0, lines)
        self.assertEqual(len(lines), 8)
        self.assertIn("ledger: 2 event(s) the fold could not read (#9 task_finished: TypeError", lines[6])
        self.assertIn("#10 controller_claimed:", lines[6])
        self.assertIn("Claude (held, window)", lines[5])                                 # the bad claim did not take the lease
        self.assertEqual(lines[7], "- Next queue: r05_medkit")
        s = fold(Ledger(os.path.join(self.dir, "ledger.jsonl")).read())
        self.assertEqual([(i, ev) for i, ev, _ in s.bad_events], [(9, "task_finished"), (10, "controller_claimed")])

    def test_the_wrapper_runs_under_python_isolated(self):
        r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "leader_report.py"), "--ledger", self.dir,
                            "--now", "2026-10-16T07:30:00+00:00"], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(r.stdout.strip().splitlines()), 8)


if __name__ == "__main__":
    unittest.main()
