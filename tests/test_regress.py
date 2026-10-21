"""scripts/game/regress.py: two builds' results matched by what each test checks (synthetic queue folders)."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import regress as rg  # noqa: E402


def queue(d, name, build, tests, results=(), judged=None, torn=False):
    q = os.path.join(d, name)
    os.makedirs(q)
    with open(os.path.join(q, "queue.json"), "w") as f:
        json.dump({"build_id": build, "tests": [dict(t, id=f"{i:04d}_{t['kind']}") for i, t in enumerate(tests)]}, f)
    with open(os.path.join(q, "results.jsonl"), "w") as f:
        for i, v in results:
            f.write(json.dumps({"id": f"{i:04d}_{tests[i]['kind']}", "verdict": v, "class": "X", "detail": "d"}) + "\n")
        if torn:
            f.write('{"id": "0000_st')
    if judged is not None:
        with open(os.path.join(q, "door_rounds_judge.json"), "w") as f:
            json.dump({"results": judged}, f)
    return q


def door(k, leg, edid, src="1:Fallout4.esm"):
    """A door round test as plan-terrain writes it from door_rounds.py's plan.json: label in model, ack in console_post."""
    label = f"door round {k} IN ({edid}, FO4 {src}): walk" if leg == "in" else f"door round {k} OUT ({edid}): coc inside"
    tag = f"door-{'fwd' if leg == 'in' else 'ret'}-{k}"
    return {"kind": "terrain", "cell": "", "ref": edid, "model": label,
            "console_post": [f'cgf "FO4SF_Probe.Ack" "{tag}"']}


def jrow(k, leg, edid, src="1:Fallout4.esm", **kw):
    """door_rounds.py judge's row for that test."""
    return dict({"door": k, "leg": leg, "cell_edid": edid, "src": src, "ack": f"door-{'fwd' if leg == 'in' else 'ret'}-{k}",
                 "verdict": "PASS", "why": "", "id": f"{k:04d}_terrain"}, **kw)


STAIRS = {"kind": "stairs", "cell": "BostonPublicLibrary02", "ref": "0EBEDE"}
FALL = {"kind": "fall", "cell": "BostonPublicLibrary02", "ref": "pt1"}
WALK = {"kind": "walk", "cell": "", "ref": "RedRocket_to_Sanctuary"}
MOVE = {"kind": "movable_control", "cell": "", "ref": "C_can"}


class DiffTests(unittest.TestCase):
    def test_matches_by_what_is_tested_not_the_test_number(self):
        d = tempfile.mkdtemp()
        old = queue(d, "old", "aaaa", [STAIRS, FALL, WALK, MOVE],
                    [(0, "PASS"), (1, "PASS"), (2, "FAIL"), (3, "INCONCLUSIVE"), (2, "FAIL")])
        new = queue(d, "new", "bbbb", [WALK, STAIRS, FALL, {"kind": "stairs", "cell": "X", "ref": "1"}],
                    [(0, "PASS"), (1, "FAIL"), (2, "INCONCLUSIVE"), (3, "PASS")], torn=True)
        r = rg.diff([old], [new])
        self.assertEqual((r["old_builds"], r["new_builds"]), (["aaaa"], ["bbbb"]))
        self.assertEqual([x["key"] for x in r["regressed"]], [["stairs", "BostonPublicLibrary02", "0EBEDE", ""]])
        self.assertEqual([x["key"] for x in r["lost"]], [["fall", "BostonPublicLibrary02", "pt1", ""]])
        self.assertEqual([x["key"] for x in r["fixed"]], [["walk", "", "RedRocket_to_Sanctuary", ""]])
        self.assertEqual([x["key"] for x in r["new"]], [["stairs", "X", "1", ""]])
        self.assertEqual([x["key"] for x in r["gone"]], [["movable_control", "", "C_can", ""]])

    def test_the_last_row_is_final_and_unrun_tests_count_as_lost(self):
        d = tempfile.mkdtemp()
        old = queue(d, "old", "a", [STAIRS], [(0, "INCONCLUSIVE"), (0, "PASS")])
        new = queue(d, "new", "b", [STAIRS], [])
        r = rg.diff([old], [new])
        self.assertEqual(r["lost"][0]["new"], "NOT_RUN")

    def test_the_door_judge_replaces_the_runner_verdicts(self):
        d = tempfile.mkdtemp()
        doors = [door(0, "out", "FO4Port_Vault95")]
        old = queue(d, "old", "a", doors, [(0, "PASS")],
                    judged=[jrow(0, "out", "FO4Port_Vault95", why="0.5 m")])
        new = queue(d, "new", "b", doors, [(0, "PASS")],
                    judged=[jrow(0, "out", "FO4Port_Vault95", verdict="FAIL", why="STAYED")])
        r = rg.diff([old], [new])
        self.assertEqual(r["regressed"][0]["key"], ["door", "FO4Port_Vault95", "out", "1:Fallout4.esm"])
        self.assertEqual(r["regressed"][0]["detail"], "STAYED")

    def test_exit_code_and_report_file(self):
        d = tempfile.mkdtemp()
        old = queue(d, "old", "a", [STAIRS], [(0, "PASS")])
        same = queue(d, "same", "b", [STAIRS], [(0, "PASS")])
        worse = queue(d, "worse", "c", [STAIRS], [(0, "FAIL")])
        out = os.path.join(d, "r.json")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(rg.main(["--old", old, "--new", same]), 0)
            self.assertEqual(rg.main(["--old", old, "--new", worse, "--out", out]), 1)
            with self.assertRaises(SystemExit):
                rg.main(["--old", old, "--new", worse, "--out", out])
        with open(out) as f:
            self.assertEqual(json.load(f)["counts"]["regressed"], 1)

    def test_missing_or_torn_queues_are_refused_not_read_as_empty(self):
        # Codex on #401: an absent --new folder or a torn queue.json read as an empty queue, so a PASS became "gone", exit 0
        d = tempfile.mkdtemp()
        old = queue(d, "old", "a", [STAIRS], [(0, "PASS")])
        torn = queue(d, "torn", "b", [STAIRS], [(0, "PASS")])
        with open(os.path.join(torn, "queue.json"), "w") as f:
            f.write('{"build_id": "b", "tests": [')
        empty = queue(d, "empty", "c", [], [])
        out = os.path.join(d, "r.json")
        for args in (["--old", old, "--new", os.path.join(d, "nope")], ["--old", old, "--new", torn],
                     ["--old", torn, "--new", old], ["--old", os.path.join(d, "nope"), "--new", old]):
            with self.subTest(args=args), redirect_stdout(io.StringIO()) as buf:
                self.assertEqual(rg.main(args + ["--out", out]), 2)
            self.assertIn("not compared", buf.getvalue())
            self.assertFalse(os.path.exists(out))
        with redirect_stdout(io.StringIO()):                      # a valid empty queue still compares: the PASS is gone
            self.assertEqual(rg.main(["--old", old, "--new", empty]), 0)

    def test_an_unjudged_or_torn_judged_door_queue_is_refused(self):
        # Codex on #401: without a readable judge, a door queue fell back to the runner's terrain PASS
        d = tempfile.mkdtemp()
        exp = os.path.join(d, "exp")
        os.makedirs(exp)
        with open(os.path.join(exp, "rounds.json"), "w") as f:
            json.dump({"tests": []}, f)
        doors = [door(0, "out", "FO4Port_Vault95")]
        row = jrow(0, "out", "FO4Port_Vault95")
        old = queue(d, "old", "a", doors, [(0, "PASS")], judged=[row])
        new = queue(d, "new", "b", doors, [(0, "PASS")])
        with open(os.path.join(new, "queue.json")) as f:
            q = json.load(f)
        with open(os.path.join(new, "queue.json"), "w") as f:
            json.dump(dict(q, experiment=exp), f)
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(rg.main(["--old", old, "--new", new]), 2)
        self.assertIn("not judged yet", buf.getvalue())
        with open(os.path.join(new, "door_rounds_judge.json"), "w") as f:
            f.write('{"results": [')
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(rg.main(["--old", old, "--new", new]), 2)
        self.assertIn("unreadable or without a results list", buf.getvalue())
        archived = queue(d, "archived", "c", [{"kind": "terrain", "cell": "", "ref": "FO4Port_Vault95",
                                               "model": "door round 0 OUT (FO4Port_Vault95): coc inside"}], [(0, "PASS")])
        with open(os.path.join(archived, "queue.json")) as f:              # its stage folder moved away (Codex on #401)
            q2 = json.load(f)
        with open(os.path.join(archived, "queue.json"), "w") as f:
            json.dump(dict(q2, experiment=os.path.join(d, "moved_away")), f)
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(rg.main(["--old", old, "--new", archived]), 2)
        self.assertIn("not judged yet", buf.getvalue())
        with open(os.path.join(new, "door_rounds_judge.json"), "w") as f:
            json.dump({"results": [dict(row, verdict="NOT_RUN")]}, f)    # judged, never run: lost, exit 1
        with redirect_stdout(io.StringIO()):
            self.assertEqual(rg.main(["--old", old, "--new", new]), 1)

    def test_judge_rows_of_tests_the_queue_never_planned_are_left_out(self):
        # Codex on #401: plan-terrain --only queues got an id-less INCONCLUSIVE row for every unplanned expectation
        d = tempfile.mkdtemp()
        doors = [door(0, "out", "FO4Port_Vault95")]
        row = jrow(0, "out", "FO4Port_Vault95")
        phantom = {k: v for k, v in jrow(1, "in", "FO4Port_Museum", "2:Fallout4.esm", verdict="INCONCLUSIVE",
                                         why="the queue has no such test").items() if k != "id"}
        partial = queue(d, "partial", "b", doors, [(0, "PASS")], judged=[row, phantom])
        two = doors + [door(1, "in", "FO4Port_Museum", "2:Fallout4.esm")]
        full = queue(d, "full", "a", two, [(0, "PASS")], judged=[row, dict(phantom, id="0001_terrain", verdict="PASS")])
        r = rg.diff([full], [partial])
        self.assertEqual(r["lost"], [])
        self.assertEqual([x["key"] for x in r["gone"]], [["door", "FO4Port_Museum", "in", "2:Fallout4.esm"]])

    def test_a_judge_missing_a_queued_door_is_refused(self):
        # Codex on #401: a judge --rounds subset left doors out, so a PASS became "gone", exit 0
        d = tempfile.mkdtemp()
        two = [door(0, "out", "FO4Port_Vault95"), door(1, "in", "FO4Port_Museum", "2:Fallout4.esm")]
        row = jrow(0, "out", "FO4Port_Vault95")
        row1 = jrow(1, "in", "FO4Port_Museum", "2:Fallout4.esm")
        old = queue(d, "old", "a", two, [], judged=[row, row1])
        subset = queue(d, "subset", "b", two, [], judged=[row])
        twice = queue(d, "twice", "c", two, [], judged=[row, row1, dict(row1, verdict="FAIL")])
        for new, why in ((subset, "0001_terrain (0 rows)"), (twice, "0001_terrain (2 rows)")):
            with self.subTest(why=why), redirect_stdout(io.StringIO()) as buf:
                self.assertEqual(rg.main(["--old", old, "--new", new]), 2)
            self.assertIn(why, buf.getvalue())

    def test_a_judge_older_than_the_queue_is_refused(self):
        # Codex on #401: a queue judged, then resumed, compared on the old judge's verdicts
        d = tempfile.mkdtemp()
        doors = [door(0, "out", "FO4Port_Vault95")]
        row = jrow(0, "out", "FO4Port_Vault95", verdict="INCONCLUSIVE", attempt="a1")
        old = queue(d, "old", "a", doors, [(0, "PASS")], judged=[dict(row, verdict="PASS")])
        os.makedirs(os.path.join(old, "tests", "0000_terrain", "a1"))
        new = queue(d, "new", "b", doors, [(0, "PASS")], judged=[row])
        for a in ("a1", "a2"):
            os.makedirs(os.path.join(new, "tests", "0000_terrain", a))
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(rg.main(["--old", old, "--new", new]), 2)
        self.assertIn("judged at attempt a1 of 0000_terrain, the queue now has a2", buf.getvalue())
        with open(os.path.join(new, "door_rounds_judge.json"), "w") as f:
            json.dump({"results": [dict(row, attempt="a2")]}, f)           # judged again: compared
        with redirect_stdout(io.StringIO()):
            self.assertEqual(rg.main(["--old", old, "--new", new]), 1)
        unrun = queue(d, "unrun", "c", doors, [], judged=[{k: v for k, v in row.items() if k != "attempt"}])
        os.makedirs(os.path.join(unrun, "tests", "0000_terrain", "a1"))   # judged NOT_RUN, ran since
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(rg.main(["--old", old, "--new", unrun]), 2)
        self.assertIn("judged at attempt none", buf.getvalue())

    def test_a_judge_of_another_rounds_file_is_refused(self):
        # Codex on #401: a judge of another rounds file with the same test numbers passed the row count
        d = tempfile.mkdtemp()
        doors = [door(0, "out", "FO4Port_Vault95"), door(1, "in", "FO4Port_Museum", "2:Fallout4.esm")]
        good = [jrow(0, "out", "FO4Port_Vault95"), jrow(1, "in", "FO4Port_Museum", "2:Fallout4.esm")]
        old = queue(d, "old", "a", doors, [], judged=good)
        for n, (rows_, why) in enumerate((
                ([good[0], jrow(1, "in", "FO4Port_Library", "2:Fallout4.esm")], "'cell_edid': 'FO4Port_Library'"),
                ([good[0], jrow(1, "in", "FO4Port_Museum", "9:Fallout4.esm")], "'src': '9:Fallout4.esm'"),
                ([good[0], jrow(1, "out", "FO4Port_Museum", "2:Fallout4.esm")], "'leg': 'out'"),
                ([good[0], dict(good[1], ack="door-fwd-7")], "does not send the ack 'door-fwd-7'"))):
            new = queue(d, f"new{n}", "b", doors, [], judged=rows_)
            with self.subTest(why=why), redirect_stdout(io.StringIO()) as buf:
                self.assertEqual(rg.main(["--old", old, "--new", new]), 2)
            self.assertIn(why, buf.getvalue())
        plain = queue(d, "plain", "c", [STAIRS], [], judged=[dict(good[0], id="0000_stairs")])
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(rg.main(["--old", old, "--new", plain]), 2)
        self.assertIn("0000_stairs is not a door round test", buf.getvalue())

    def test_an_npc_control_row_is_gated_again_as_the_report_does(self):
        # Codex on #401: a raw FAIL kept as INCONCLUSIVE CONTROL read as lost, while the report shows it as FAIL
        d = tempfile.mkdtemp()
        nav = {"kind": "npc_nav", "cell": "C", "ref": "walk", "npc": "N", "method": "pt"}
        ctrl = dict(nav, ref="ctrl", control=True)
        old = queue(d, "old", "a", [nav, ctrl], [(0, "PASS"), (1, "PASS")])
        new = queue(d, "new", "b", [nav, ctrl], [(1, "PASS")])
        with open(os.path.join(new, "results.jsonl"), "a") as f:
            f.write(json.dumps({"id": "0000_npc_nav", "verdict": "INCONCLUSIVE", "class": "CONTROL",
                                "detail": "control has no result", "raw": ["FAIL", "NOREACH", "stopped 9 m short"]}) + "\n")
        with open(os.path.join(new, "state.json"), "w") as f:      # the control passed after the test ran
            json.dump({"done": {"0001_npc_nav": {"verdict": "PASS", "class": "PASS", "attempts": 1}}}, f)
        r = rg.diff([old], [new])
        self.assertEqual([x["key"] for x in r["regressed"]], [["npc_nav", "C", "walk", ""]])
        self.assertIn("stopped 9 m short (control 0001_npc_nav passed) (gated again at report time)",
                      r["regressed"][0]["detail"])

    def test_repeated_keys_are_reported(self):
        d = tempfile.mkdtemp()
        a = queue(d, "a", "x", [STAIRS], [(0, "PASS")])
        b = queue(d, "b", "x", [STAIRS], [(0, "FAIL")])
        r = rg.diff([a, b], [a])
        self.assertEqual(r["duplicates"]["old"], [["stairs", "BostonPublicLibrary02", "0EBEDE", ""]])
        self.assertEqual(r["counts"]["fixed"], 1)                         # the later old queue (FAIL) won

    def test_a_doors_two_sides_are_two_matches(self):
        # review pass on #401: both sides shared one key, so side 1 going PASS to FAIL printed "unchanged", exit 0
        d = tempfile.mkdtemp()
        door = {"kind": "door", "cell": "Vault95", "ref": "0A1B2C:Fallout4.esm"}
        sides = [dict(door, side=1), dict(door, side=-1)]
        old = queue(d, "old", "a", sides, [(0, "PASS"), (1, "PASS")])
        new = queue(d, "new", "b", sides, [(0, "FAIL"), (1, "PASS")])
        r = rg.diff([old], [new])
        self.assertEqual([x["key"] for x in r["regressed"]], [["door", "Vault95", "0A1B2C:Fallout4.esm", "1"]])
        self.assertEqual(r["counts"]["unchanged"], 1)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(rg.main(["--old", old, "--new", new]), 1)

    def test_a_key_repeated_inside_one_queue_is_refused(self):
        d = tempfile.mkdtemp()
        twice = queue(d, "twice", "a", [STAIRS, STAIRS], [(0, "PASS"), (1, "FAIL")])
        other = queue(d, "other", "b", [STAIRS], [(0, "PASS")])
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(rg.main(["--old", twice, "--new", other]), 2)
        self.assertIn("share the key", buf.getvalue())
        # terrain tests from one coc are told apart by their label
        walks = [{"kind": "terrain", "cell": "", "ref": "FO4Port_X", "model": m} for m in ("walk north", "walk south")]
        old = queue(d, "wo", "a", walks, [(0, "PASS"), (1, "PASS")])
        new = queue(d, "wn", "b", walks, [(0, "PASS"), (1, "FAIL")])
        self.assertEqual([x["key"][-1] for x in rg.diff([old], [new])["regressed"]], ["walk south"])

    def test_not_run_to_fail_is_a_new_failure_and_other_changes_are_shown(self):
        # review pass on #401: NOT_RUN to FAIL went into the never printed "unchanged" group, exit 0
        d = tempfile.mkdtemp()
        old = queue(d, "old", "a", [STAIRS, FALL, WALK], [(1, "FAIL"), (2, "INCONCLUSIVE")])
        new = queue(d, "new", "b", [STAIRS, FALL, WALK], [(0, "FAIL"), (1, "INCONCLUSIVE"), (2, "INCONCLUSIVE")])
        r = rg.diff([old], [new])
        self.assertEqual([(x["old"], x["new"]) for x in r["new_failure"]], [("NOT_RUN", "FAIL")])
        self.assertEqual([(x["old"], x["new"]) for x in r["changed"]], [("FAIL", "INCONCLUSIVE")])
        self.assertEqual([(x["old"], x["new"]) for x in r["unchanged"]], [("INCONCLUSIVE", "INCONCLUSIVE")])
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(rg.main(["--old", old, "--new", new]), 1)
        self.assertIn("new_failure", buf.getvalue())
        self.assertIn("changed", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
