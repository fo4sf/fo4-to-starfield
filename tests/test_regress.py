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
        self.assertEqual([x["key"] for x in r["regressed"]], [["stairs", "BostonPublicLibrary02", "0EBEDE"]])
        self.assertEqual([x["key"] for x in r["lost"]], [["fall", "BostonPublicLibrary02", "pt1"]])
        self.assertEqual([x["key"] for x in r["fixed"]], [["walk", "", "RedRocket_to_Sanctuary"]])
        self.assertEqual([x["key"] for x in r["new"]], [["stairs", "X", "1"]])
        self.assertEqual([x["key"] for x in r["gone"]], [["movable_control", "", "C_can"]])

    def test_the_last_row_is_final_and_unrun_tests_count_as_lost(self):
        d = tempfile.mkdtemp()
        old = queue(d, "old", "a", [STAIRS], [(0, "INCONCLUSIVE"), (0, "PASS")])
        new = queue(d, "new", "b", [STAIRS], [])
        r = rg.diff([old], [new])
        self.assertEqual(r["lost"][0]["new"], "NOT_RUN")

    def test_the_door_judge_replaces_the_runner_verdicts(self):
        d = tempfile.mkdtemp()
        doors = [{"kind": "terrain", "cell": "", "ref": "door round 0 OUT"}]
        old = queue(d, "old", "a", doors, [(0, "PASS")],
                    judged=[{"cell_edid": "FO4Port_Vault95", "leg": "out", "src": "1:Fallout4.esm", "verdict": "PASS",
                             "why": "0.5 m", "id": "0000_terrain"}])
        new = queue(d, "new", "b", doors, [(0, "PASS")],
                    judged=[{"cell_edid": "FO4Port_Vault95", "leg": "out", "src": "1:Fallout4.esm", "verdict": "FAIL",
                             "why": "STAYED", "id": "0000_terrain"}])
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

    def test_repeated_keys_are_reported(self):
        d = tempfile.mkdtemp()
        a = queue(d, "a", "x", [STAIRS], [(0, "PASS")])
        b = queue(d, "b", "x", [STAIRS], [(0, "FAIL")])
        r = rg.diff([a, b], [a])
        self.assertEqual(r["duplicates"]["old"], [["stairs", "BostonPublicLibrary02", "0EBEDE"]])
        self.assertEqual(r["counts"]["fixed"], 1)                         # the later old queue (FAIL) won


if __name__ == "__main__":
    unittest.main()
