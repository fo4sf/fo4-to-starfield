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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inventory as inv  # noqa: E402
import testqueue as tq  # noqa: E402
import test_testqueue as tt  # noqa: E402  (FakeControls, args: the runner without Windows or a game)


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
        for extra in (["--cells", "CellC"], ["--cells", "Gone"], ["--cells", "coc CellA"], ["--smoke-per-cell", "0"],
                      ["--bridge", os.path.join(self.d, "no_bridge")]):           # review pass on #405
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
        self.assertIn("CellA.json", jload(os.path.join(self.out, "staging_files.json")))
        self.assertNotIn("probe_CellA_1.txt", jload(os.path.join(self.out, "staging_files.json")))
        with self.assertRaises(SystemExit) as cm:                        # nothing ran: every cell held
            self.run_inv("promote", "--inventory", self.out)
        self.assertIn("no cell passed tier 1", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(self.out, "tier2")))
        for k in ("bogus", ""):
            with self.subTest(kinds=k), self.assertRaises(SystemExit):
                self.run_inv("promote", "--inventory", self.out, "--kinds", k)
        with open(os.path.join(self.out, "promotion.json"), "rb") as f:
            held = f.read()                                              # the no-pass promote's record
        with open(os.path.join(self.st, "Meshes.ba2"), "wb") as f:      # same plugin, another archive (Codex on #405)
            f.write(b"BTDX rebuilt")
        with self.assertRaises(SystemExit) as cm:
            self.run_inv("promote", "--inventory", self.out)
        self.assertIn("the staging changed since the smoke tier was planned (1 file(s): Meshes.ba2)", str(cm.exception))
        os.remove(os.path.join(self.st, "Meshes.ba2"))
        with open(os.path.join(self.st, "CellA.json"), "a") as f:
            f.write(" ")
        with self.assertRaisesRegex(SystemExit, "CellA.json"):
            self.run_inv("promote", "--inventory", self.out)
        with open(os.path.join(self.out, "promotion.json"), "rb") as f:
            self.assertEqual(f.read(), held)                             # a refused promote rewrites nothing
        self.assertFalse(os.path.exists(os.path.join(self.out, "tier2")))
        with open(os.path.join(self.st, "FO4Port.esm"), "ab") as f:
            f.write(b"!")                                                # rebuilt: the ids are another build's
        with self.assertRaises(SystemExit) as cm:
            self.run_inv("promote", "--inventory", self.out)
        self.assertIn("plan the inventory again", str(cm.exception))

    def passed_tier1(self):
        self.run_inv("plan", "--staging", self.st, "--out", self.out)
        ids = {c["cell"]: c.get("tests") for c in jload(os.path.join(self.out, "inventory.json"))["cells"]}
        self.results([{"id": ids["CellA"][0], "verdict": "PASS", "class": "PASS"}])

    def test_a_refused_tier2_plan_leaves_no_tier2_folder(self):
        # Codex on #405: a bridge gone at promotion left tier2/ behind, and every later promote was refused
        self.passed_tier1()
        p = os.path.join(self.out, "inventory.json")
        i = jload(p)
        i["bridge"] = os.path.join(self.d, "no_bridge")
        jdump(i, p)
        with self.assertRaises(SystemExit):
            self.run_inv("promote", "--inventory", self.out, "--kinds", "stairs")
        self.assertFalse(os.path.exists(os.path.join(self.out, "tier2")))
        i["bridge"] = ""
        jdump(i, p)
        self.run_inv("promote", "--inventory", self.out, "--kinds", "stairs")
        self.assertTrue(os.path.exists(os.path.join(self.out, "tier2", "queue.json")))

    def test_the_runner_refuses_a_staging_changed_after_the_plan(self):
        # Codex on #405: the tier 2 queue pinned only FO4Port.esm, so a rebuilt archive ran under the old build id
        self.passed_tier1()
        self.run_inv("promote", "--inventory", self.out, "--kinds", "stairs")
        for tier in ("tier1", "tier2"):
            with self.subTest(tier=tier):
                qdir = os.path.join(self.out, tier)
                self.assertEqual(jload(os.path.join(qdir, "queue.json"))["staging_files"],
                                 jload(os.path.join(self.out, "staging_files.json")))
                r = tq.Runner(qdir, tt.args(), ctl=tt.FakeControls(), step=lambda t, o: 0)
                self.assertIsNone(r.staging_mismatch())
                with open(os.path.join(self.st, "Meshes.ba2"), "wb") as f:
                    f.write(b"BTDX rebuilt")
                self.assertIn("1 file(s): Meshes.ba2", r.staging_mismatch())
                self.assertTrue(r.pinned_ok())                   # the plugin alone would have let it run
                os.remove(os.path.join(self.st, "Meshes.ba2"))

    def test_tier2_travel_needs_both_cells_promoted(self):
        # Codex on #405: plan builds travel from every staged cell, so a promoted cell's door led into a held one
        def door(fk, other, pos):
            return {"formkey": fk, "model": "D.nif", "pos": pos, "teleport_destination": {"door": other, "pos": pos}}
        jdump({"cell": "CellA", "refs": [door("00000A:FO4Port.esm", "00000B:FO4Port.esm", [1, 0, 0]),
                                         door("00000C:FO4Port.esm", "00000D:FO4Port.esm", [2, 0, 0])]},
              os.path.join(self.st, "CellA.json"))
        jdump({"cell": "CellB", "refs": [door("00000B:FO4Port.esm", "00000A:FO4Port.esm", [3, 0, 0])]},
              os.path.join(self.st, "CellB.json"))
        jdump({"cell": "CellC", "refs": [door("00000D:FO4Port.esm", "00000C:FO4Port.esm", [4, 0, 0])]},
              os.path.join(self.st, "CellC.json"))
        self.run_inv("plan", "--staging", self.st, "--out", self.out)
        ids = {c["cell"]: c.get("tests") for c in jload(os.path.join(self.out, "inventory.json"))["cells"]}
        self.results([{"id": ids["CellA"][0], "verdict": "PASS", "class": "PASS"},
                      {"id": ids["CellB"][0], "verdict": "PASS", "class": "PASS"}])   # CellC: no point, held
        out = self.run_inv("promote", "--inventory", self.out, "--kinds", "travel")
        q = jload(os.path.join(self.out, "tier2", "queue.json"))
        self.assertEqual(sorted((t["cell"], t["dest_cell"]) for t in q["tests"]),
                         [("CellA", "CellB"), ("CellB", "CellA")])
        self.assertIn("1 travel test(s) into a held cell dropped", out)

    def test_the_staging_is_checked_before_every_test_in_a_live_game(self):
        # Codex on #405: the pin was checked only at launch, so tier 2 right after tier 1 reused the game unchecked
        self.run_inv("plan", "--staging", self.st, "--out", self.out, "--cells", "CellA,CellB")
        qdir = os.path.join(self.out, "tier1")
        ctl = tt.FakeControls()                                          # the runner's own game is up
        calls = []

        def step(test, out):
            calls.append(test["id"])
            with open(os.path.join(self.st, "Meshes.ba2"), "wb") as f:  # rebuilt while the queue runs
                f.write(b"BTDX rebuilt")
            jdump({"end_read": "1 2 3", "shot": ""}, os.path.join(out, "obs.json"))
            return 0
        r = tq.Runner(qdir, tt.args(), ctl=ctl, step=step)
        r.session, r.cell = True, "CellA"
        r._ps = lambda *a, **k: (0, "at the cell")
        self.assertEqual(r.run(), 3)
        self.assertEqual(len(calls), 1)                                  # the second test never ran
        with open(os.path.join(qdir, "run.log"), encoding="utf-8") as f:
            self.assertIn("staging changed since the queue was planned (1 file(s): Meshes.ba2)", f.read())

    def test_an_unchanged_staging_is_hashed_once(self):
        self.run_inv("plan", "--staging", self.st, "--out", self.out)
        r = tq.Runner(os.path.join(self.out, "tier1"), tt.args(), ctl=tt.FakeControls(), step=lambda t, o: 0)
        hashed = []
        real = tq.sha256
        tq.sha256 = lambda p: hashed.append(p) or real(p)
        self.addCleanup(setattr, tq, "sha256", real)
        self.assertIsNone(r.staging_mismatch())
        n = len(hashed)
        self.assertGreater(n, 0)
        self.assertIsNone(r.staging_mismatch())
        self.assertEqual(len(hashed), n)                                 # same sizes and mtimes: no rehash
        with open(os.path.join(self.st, "CellA.json"), "a") as f:
            f.write(" ")
        self.assertIn("CellA.json", r.staging_mismatch())

    def test_a_same_size_replace_with_the_old_mtime_is_rehashed(self):
        # Codex on #405: the cache trusted size and mtime alone
        self.run_inv("plan", "--staging", self.st, "--out", self.out)
        r = tq.Runner(os.path.join(self.out, "tier1"), tt.args(), ctl=tt.FakeControls(), step=lambda t, o: 0)
        self.assertIsNone(r.staging_mismatch())
        p = os.path.join(self.st, "FO4Port.esm")
        st = os.stat(p)
        new = os.path.join(self.d, "new.esm")
        with open(new, "wb") as f:
            f.write(b"TES5")                                             # same length, other bytes
        os.utime(new, ns=(st.st_atime_ns, st.st_mtime_ns))
        os.replace(new, p)
        self.assertEqual((os.stat(p).st_size, os.stat(p).st_mtime_ns), (st.st_size, st.st_mtime_ns))
        self.assertIn("FO4Port.esm", r.staging_mismatch())

    def test_the_archives_the_deploy_packs_are_not_a_build_change(self):
        # Codex on #405: deploy_starfield.py install writes "FO4Port - Main.ba2" into the staging on the first launch
        self.run_inv("plan", "--staging", self.st, "--out", self.out)
        r = tq.Runner(os.path.join(self.out, "tier1"), tt.args(), ctl=tt.FakeControls(), step=lambda t, o: 0)
        for n in ("FO4Port - Main.ba2", "FO4Port - Textures.ba2"):
            with open(os.path.join(self.st, n), "wb") as f:
                f.write(b"BTDX packed")
        os.makedirs(os.path.join(self.st, ".fo4port-archive-x1"))
        with open(os.path.join(self.st, ".fo4port-archive-x1", "FO4Port - Main.ba2"), "wb") as f:
            f.write(b"BTDX")
        self.assertIsNone(r.staging_mismatch())
        os.makedirs(os.path.join(self.st, "meshes"))
        with open(os.path.join(self.st, "meshes", "FO4Port - Main.ba2"), "wb") as f:
            f.write(b"x")                                                # the same name below the root is an input
        self.assertIn("meshes/FO4Port - Main.ba2", r.staging_mismatch())


if __name__ == "__main__":
    unittest.main()
