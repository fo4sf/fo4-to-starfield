"""scripts/bridge/door_batch.py: door round trips per interior batch (the synthetic core and port of
test_door_rounds.py)."""
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "bridge"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import door_batch as db  # noqa: E402
import door_rounds as dr  # noqa: E402
from test_door_rounds import build  # noqa: E402


def load(d, *name):
    with open(os.path.join(d, *name)) as f:
        return json.load(f)


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def batch(self, cells, name="b1.json"):
        p = os.path.join(self.d, name)
        with open(p, "w") as f:
            if name.endswith(".json"):
                json.dump({"name": "b1", "cells": cells}, f)
            else:
                f.write("\n".join(cells))
        return p

    def stage(self, cells, *extra, out="out", **kw):
        core, port, _ = build(os.path.join(self.d, "b"), **kw) if not os.path.exists(os.path.join(self.d, "b")) else \
            (os.path.join(self.d, "b", "core"), os.path.join(self.d, "b", "port"), None)
        o = os.path.join(self.d, out)
        with redirect_stdout(io.StringIO()):
            db.main(["stage", "--batch", self.batch(cells), "--core", core, "--port", port, "--core-index", "02",
                     "--port-index", "06", "--out", o, *extra])
        return o

    def test_out_legs_by_default_with_coverage_per_cell(self):
        o = self.stage(["SuperDuperMart01", "FO4Port_Vault95", "fo4port_superdupermart01"], "--min-out-m", "0")
        cov = load(o, "coverage.json")
        self.assertEqual([(r["cell"], r["state"]) for r in cov["cells"]],
                         [("SuperDuperMart01", "doors"), ("FO4Port_Vault95", "not_in_port")])   # the duplicate dropped
        self.assertEqual(cov["counts"], {"doors": 1, "too_near": 0, "doors_skipped": 0, "not_wired": 0, "coc_only": 0, "no_door": 0,
                                         "not_in_port": 1})
        plan, rounds = load(o, "chunk_00", "plan.json"), load(o, "chunk_00", "rounds.json")
        self.assertEqual([p["coc"] for p in plan], ["FO4Port_SuperDuperMart01"])     # never the Red Rocket arrival
        self.assertEqual([(t["test"], t["leg"], t["ack"]) for t in rounds["tests"]], [(0, "out", "door-ret-0")])
        self.assertEqual((rounds["core_index"], rounds["port_index"], rounds["batch"]), ("02", "06", "b1"))
        with open(os.path.join(o, "chunk_00", "plan.json"), "rb") as f:     # #401: plan-terrain checks this digest
            self.assertEqual(rounds["plan_sha256"], hashlib.sha256(f.read()).hexdigest())
        with open(os.path.join(o, "README.txt")) as f:
            self.assertIn("--crash-budget 1", f.read())

    def test_both_legs_stay_together_and_match_door_rounds_stage(self):
        o = self.stage(["SuperDuperMart01"], "--legs", "both", "--chunk", "2")
        core, port = os.path.join(self.d, "b", "core"), os.path.join(self.d, "b", "port")
        ref = os.path.join(self.d, "ref")
        with redirect_stdout(io.StringIO()):
            dr.main(["stage", "--core", core, "--port", port, "--core-index", "02", "--port-index", "06", "--out", ref])
        self.assertEqual(load(o, "chunk_00", "plan.json"), load(ref, "plan.json"))
        self.assertEqual(load(o, "chunk_00", "rounds.json")["tests"], load(ref, "rounds.json")["tests"])
        with open(os.path.join(o, "README.txt")) as f:                 # Codex on #397: no direct run past the hold
            text = f.read()
        self.assertNotIn("testqueue.py run", text)
        self.assertIn("campaign_arm.py", text)

    def test_nothing_is_written_when_no_door_is_left(self):
        with self.assertRaises(SystemExit) as cm:
            self.stage(["SuperDuperMart01"], "--min-out-m", "99999")
        self.assertIn("no door to plan", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(self.d, "out")))

    def test_allow_empty_writes_only_the_readiness_report(self):
        o = self.stage(["SuperDuperMart01", "Vault95"], "--min-out-m", "99999", "--allow-empty")
        cov = load(o, "coverage.json")
        self.assertEqual(cov["chunks"], [])
        # review pass on #397: a door --min-out-m dropped is not planned, so its cell is too_near, not doors
        self.assertEqual((cov["counts"]["doors"], cov["counts"]["too_near"]), (0, 1))
        row = next(r for r in cov["cells"] if r["state"] == "too_near")
        self.assertEqual((row["doors"], len(row["near"])), ([], 1))
        self.assertFalse(any(n.startswith("chunk_") for n in os.listdir(o)))

    def test_a_cell_whose_doors_fail_their_checks_is_doors_skipped(self):
        with self.assertRaises(SystemExit) as cm:
            self.stage(["SuperDuperMart01"], port_marker_target=0x901)
        self.assertIn("SuperDuperMart01 doors_skipped", str(cm.exception))

    def test_an_existing_out_and_bad_options_are_refused(self):
        o = self.stage(["SuperDuperMart01"], "--min-out-m", "0")
        with self.assertRaises(SystemExit):
            self.stage(["SuperDuperMart01"], "--min-out-m", "0", out=os.path.basename(o))
        for extra in (["--chunk", "1"], ["--min-out-m", "nan"], ["--min-out-m", "-1"]):
            with self.subTest(extra=extra), self.assertRaises(SystemExit):
                self.stage(["SuperDuperMart01"], *extra, out="bad")
            self.assertFalse(os.path.exists(os.path.join(self.d, "bad")))


class PartsTests(unittest.TestCase):
    def test_read_batch_text_comments_dedupe_and_bad_names(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "batch7.txt")
        with open(p, "w") as f:
            f.write("# batch 7\nVault81Main\n\nFO4Port_Vault81Main  # again\nDiamondCity01\n")
        self.assertEqual(db.read_batch(p), ("batch7", ["Vault81Main", "DiamondCity01"], {}))
        with self.assertRaises(SystemExit):
            db.read_batch(p, 2)
        with open(p, "w") as f:
            f.write("coc Vault81Main\n")
        with self.assertRaises(SystemExit):
            db.read_batch(p)
        with open(p, "w") as f:
            f.write("# nothing\n")
        with self.assertRaises(SystemExit):
            db.read_batch(p)

    def test_coverage_states(self):
        rounds = [{"cell_edid": "FO4Port_A", "src": "1:Fallout4.esm"}]
        skipped = [{"src": "2:Fallout4.esm", "why": "base moved", "cell_edid": "FO4Port_B"},
                   {"src": "3:Fallout4.esm", "why": "x", "cell_edid": "FO4Port_A"}, {"src": "4", "why": "y"}]
        rows = db.coverage(["A", "B", "C", "D"], rounds, skipped, {"c": "FO4Port_C"})
        self.assertEqual([r["state"] for r in rows], ["doors", "doors_skipped", "no_door", "not_in_port"])
        self.assertEqual(rows[0]["skipped"], [{"src": "3:Fallout4.esm", "why": "x"}])
        self.assertEqual(rows[2]["cell"], "FO4Port_C")

    def test_the_interiors_plan_marks_unwired_and_coc_only_cells(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "interior-door-rounds.json")
        with open(p, "w") as f:
            json.dump({"batches": [{"batch": 2, "name": "interiors_b02", "cells": [
                {"cell": "MassFusion01", "commonwealth_doors": [{"src": "1"}]},
                {"cell": "HardwareTown01", "commonwealth_doors": []}]}]}, f)
        name, cells, plan = db.read_batch(p, 2)
        self.assertEqual((name, cells), ("interiors_b02", ["MassFusion01", "HardwareTown01"]))
        rows = db.coverage(cells, [], [], {"massfusion01": "FO4Port_MassFusion01",
                                           "hardwaretown01": "FO4Port_HardwareTown01"}, plan)
        self.assertEqual([r["state"] for r in rows], ["not_wired", "coc_only"])
        # Codex on #397: a skipped door with no destination marker (no cell_edid) stays on its cell through the plan
        rows = db.coverage(cells, [], [{"src": "1", "why": "marker missing"}],
                           {"massfusion01": "FO4Port_MassFusion01", "hardwaretown01": "FO4Port_HardwareTown01"}, plan)
        self.assertEqual([r["state"] for r in rows], ["doors_skipped", "coc_only"])
        self.assertEqual(rows[0]["skipped"], [{"src": "1", "why": "marker missing"}])
        for n in (None, 3):
            with self.subTest(n=n), self.assertRaises(SystemExit):
                db.read_batch(p, n)

    def test_chunks_never_split_a_door(self):
        groups = [(0, ["i0", "o0"]), (1, ["i1", "o1"]), (2, ["i2", "o2"])]
        self.assertEqual(db.chunks(groups, 3), [["i0", "o0"], ["i1", "o1"], ["i2", "o2"]])
        self.assertEqual(db.chunks(groups, 4), [["i0", "o0", "i1", "o1"], ["i2", "o2"]])
        self.assertEqual(db.chunks([(0, ["o0"]), (1, ["o1"]), (2, ["o2"])], 2), [["o0", "o1"], ["o2"]])


if __name__ == "__main__":
    unittest.main()
