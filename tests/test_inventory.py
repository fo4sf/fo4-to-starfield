"""scripts/game/inventory.py: tier 1 smoke queue per cell, tier 2 only for the cells that passed it. Synthetic
staging; no game."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import inventory as inv  # noqa: E402


def jdump(o, p):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f)


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = tmp.name
        self.st = os.path.join(self.d, "staging")
        os.makedirs(self.st)
        with open(os.path.join(self.st, "FO4Port.esm"), "wb") as f:
            f.write(b"TES4")
        jdump({"x": 1}, os.path.join(self.st, "formids.json"))
        for c in ("CellA", "CellB", "CellC"):
            jdump({"cell": c, "refs": []}, os.path.join(self.st, c + ".json"))
        for c in ("CellA", "CellB"):                         # CellC: no floor point
            with open(os.path.join(self.st, f"probe_{c}_1.txt"), "w") as f:
                f.write("1.0 2.0 3.0 Floor.nif\n")
        open(os.path.join(self.st, "probe_CellC_1.txt"), "w").close()
        jdump({"routes": [{"kind": "stairs", "ref": "000001:Fallout4.esm", "model": "S.nif"}]},
              os.path.join(self.st, "routes_CellA.json"))
        jdump({"routes": [{"kind": "stairs", "ref": "000002:Fallout4.esm", "model": "S.nif"}]},
              os.path.join(self.st, "routes_CellB.json"))
        self.out = os.path.join(self.d, "inv")

    def run_inv(self, *argv):
        with redirect_stdout(io.StringIO()) as buf:
            inv.main(list(argv))
        return buf.getvalue()

    def results(self, rows):
        with open(os.path.join(self.out, "tier1", "results.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            f.write('{"id": "torn')                          # a torn last line is not a row

    def test_plan_writes_tier1_and_every_cells_state(self):
        self.run_inv("plan", "--staging", self.st, "--out", self.out, "--cells", "CellA,CellC,Gone,CellA")
        i = jload(os.path.join(self.out, "inventory.json"))
        self.assertEqual([(c["cell"], c["state"]) for c in i["cells"]],
                         [("CellA", "smoke"), ("CellC", "no_point"), ("Gone", "not_in_staging")])
        self.assertEqual(i["counts"], {"smoke": 1, "no_point": 1, "not_in_staging": 1})
        q = jload(os.path.join(self.out, "tier1", "queue.json"))
        self.assertEqual([(t["kind"], t["cell"], t["point"]) for t in q["tests"]], [("fall", "CellA", [1.0, 2.0, 3.0])])
        self.assertEqual(i["plugin_sha256"], q["plugin_sha256"])
        self.assertEqual(i["cells"][0]["tests"], [q["tests"][0]["id"]])

    def test_a_batch_of_the_interiors_plan(self):
        b = os.path.join(self.d, "interior-batches.json")
        jdump({"batches": [{"batch": 1, "cells": [{"editor_id": "CellB"}]},
                           {"batch": 2, "cells": [{"editor_id": "CellA"}, {"editor_id": "CellB"}]}]}, b)
        self.run_inv("plan", "--staging", self.st, "--out", self.out, "--batch", b, "--batch-number", "2")
        i = jload(os.path.join(self.out, "inventory.json"))
        self.assertEqual([c["cell"] for c in i["cells"]], ["CellA", "CellB"])
        self.assertEqual(i["source"]["batch_number"], 2)
        for n in ("3", None):
            with self.subTest(n=n), self.assertRaises(SystemExit):
                self.run_inv("plan", "--staging", self.st, "--out", os.path.join(self.d, "x"), "--batch", b,
                             *(["--batch-number", n] if n else []))
            self.assertFalse(os.path.exists(os.path.join(self.d, "x")))

    def test_plan_refusals_leave_nothing_behind(self):
        self.run_inv("plan", "--staging", self.st, "--out", self.out)
        with self.assertRaises(SystemExit):                              # never over an existing inventory
            self.run_inv("plan", "--staging", self.st, "--out", self.out)
        bad = os.path.join(self.d, "bad")
        for extra in (["--cells", "CellC"], ["--cells", "Gone"], ["--cells", "coc CellA"], ["--smoke-per-cell", "0"]):
            with self.subTest(extra=extra), self.assertRaises(SystemExit):
                self.run_inv("plan", "--staging", self.st, "--out", bad, *extra)
            self.assertFalse(os.path.exists(bad))

    def test_promote_plans_tier2_only_for_cells_that_passed(self):
        self.run_inv("plan", "--staging", self.st, "--out", self.out)
        ids = {c["cell"]: c.get("tests") for c in jload(os.path.join(self.out, "inventory.json"))["cells"]}
        self.results([{"id": ids["CellA"][0], "verdict": "INCONCLUSIVE", "class": "UNREAD"},
                      {"id": ids["CellA"][0], "verdict": "PASS", "class": "PASS"},       # the last row counts
                      {"id": ids["CellB"][0], "verdict": "FAIL", "class": "FALL", "detail": "dropped 9 m"}])
        self.run_inv("promote", "--inventory", self.out, "--kinds", "stairs")
        p = jload(os.path.join(self.out, "promotion.json"))
        self.assertEqual([(c["cell"], c["state"]) for c in p["cells"]],
                         [("CellA", "promoted"), ("CellB", "held"), ("CellC", "held")])
        self.assertIn("FAIL FALL: dropped 9 m", p["cells"][1]["why"])
        self.assertIn("no_point", p["cells"][2]["why"])
        q = jload(os.path.join(self.out, "tier2", "queue.json"))
        self.assertEqual([(t["kind"], t["cell"]) for t in q["tests"]], [("stairs", "CellA")])
        with self.assertRaises(SystemExit):                              # tier 2 is planned once
            self.run_inv("promote", "--inventory", self.out)

    def test_promote_refuses_another_build_and_a_tier1_with_no_pass(self):
        self.run_inv("plan", "--staging", self.st, "--out", self.out)
        with self.assertRaises(SystemExit) as cm:                        # nothing ran: every cell held
            self.run_inv("promote", "--inventory", self.out)
        self.assertIn("no cell passed tier 1", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(self.out, "tier2")))
        for k in ("bogus", ""):
            with self.subTest(kinds=k), self.assertRaises(SystemExit):
                self.run_inv("promote", "--inventory", self.out, "--kinds", k)
        with open(os.path.join(self.st, "FO4Port.esm"), "ab") as f:
            f.write(b"!")                                                # rebuilt: the ids are another build's
        with self.assertRaises(SystemExit) as cm:
            self.run_inv("promote", "--inventory", self.out)
        self.assertIn("plan the inventory again", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
