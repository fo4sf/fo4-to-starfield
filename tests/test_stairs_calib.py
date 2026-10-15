"""The offline-walk calibration against in-game stairs results (scripts/game/stairs_calib.py) on synthetic collision
and a synthetic queue folder: a stop agrees only at the same place (QA on PR #111), superseded attempts and
INCONCLUSIVE results are left out, route files are replayed. No game data."""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stairs_calib as sc  # noqa: E402
from test_walksim import box, floor, ramp, scene  # noqa: E402

ROUTE = {"kind": "stairs", "ref": "000001:Fallout4.esm", "model": "Stairs.nif", "start": [0.0, -0.8, 0.3],
         "heading": 0.0, "walk_ms": 1300, "expect": {"low": [0, 0, 0], "high": [0, 4, 2.0], "min_rise": 1.6}}


def flight(*extra):
    return scene(("lower", floor(-3, 3, -4, 0, 0.0)), ("stair", ramp(-1.83, 1.83, 0, 4, 0.0, 2.0)),
                 ("upper", floor(-3, 3, 4, 8, 2.0)), *extra)


class AgreementTests(unittest.TestCase):
    def test_a_stop_agrees_only_at_the_same_place(self):
        # batch_full 0002: both STUCK, but the offline walk stopped at the start, 1.95 m from the game's stop
        self.assertEqual(sc.agreement("STUCK", "STUCK", [24.35, 27.23, 5.58], [26.26, 27.64, 4.12]), "verdict")
        self.assertEqual(sc.agreement("STUCK", "STUCK", [-4.29, -25.40, -13.67], [-4.28, -25.39, -13.59]), "same")
        self.assertEqual(sc.agreement("STUCK", "STUCK", [0, 0, 0], [0, 0.5, 0.6]), "verdict")     # too far in height
        self.assertEqual(sc.agreement("PASS", "PASS", [0, 0, 0], [5, 5, 5]), "same")
        self.assertEqual(sc.agreement("STUCK", "PASS", [0, 0, 0], [0, 0, 0]), "no")
        self.assertEqual(sc.agreement("FALL", "FALL", None, [0, 0, 0]), "verdict")


class ReplayTests(unittest.TestCase):
    def test_verdicts(self):
        self.assertEqual(sc.replay(flight(), ROUTE)[0], "PASS")
        stuck = sc.replay(flight(("chunk", box(-3, 3, 1.5, 1.9, 0.0, 3.0))), ROUTE)
        self.assertEqual(stuck[0], "STUCK")
        self.assertIn("chunk", stuck[1])
        void = dict(ROUTE, start=[0.0, -10.0, 0.3])
        self.assertEqual(sc.replay(flight(), void)[0], "FALL")


class FakeScenes:
    def __init__(self, *a, **k):
        pass

    def around(self, cellname, route):
        return flight(("chunk", box(-3, 3, 1.5, 1.9, 0.0, 3.0))) if route["ref"].startswith("000002") else flight()


class QueueTests(unittest.TestCase):
    def queue(self):
        d = tempfile.mkdtemp()
        routes = os.path.join(d, "routes.json")
        stuck_route = dict(ROUTE, ref="000002:Fallout4.esm")
        with open(routes, "w") as f:
            json.dump({"routes": [ROUTE, stuck_route]}, f)
        tests = [{"id": f"000{k}_stairs_CellA_00000{k + 1}", "kind": "stairs", "cell": "CellA",
                  "ref": f"00000{k + 1}:Fallout4.esm", "model": "Stairs.nif", "routes_file": routes, "route_index": k}
                 for k in range(2)]
        tests.append({"id": "0002_door_CellA_000003", "kind": "door", "cell": "CellA", "ref": "000003:Fallout4.esm"})
        with open(os.path.join(d, "queue.json"), "w") as f:
            json.dump({"tests": tests}, f)
        recs = []
        for k, (verdict, cls, end) in enumerate([("PASS", "PASS", "0 4.5 2.0"), ("FAIL", "STUCK", "0 0.2 0.1")]):
            a = os.path.join(d, "tests", tests[k]["id"], "a1")
            os.makedirs(a)
            with open(os.path.join(a, "obs.json"), "w") as f:
                json.dump({"result": {"start_read": "0 -0.8 0.0", "end_read": end}}, f)
            recs.append({"id": tests[k]["id"], "verdict": verdict, "class": cls, "detail": "", "dir": a})
        # an INCONCLUSIVE first attempt that a later decided attempt supersedes, and a door test: neither counts twice
        recs.insert(0, {"id": tests[0]["id"], "verdict": "INCONCLUSIVE", "class": "UNREAD", "dir": ""})
        recs.append({"id": tests[2]["id"], "verdict": "PASS", "class": "PASS", "dir": ""})
        with open(os.path.join(d, "results.jsonl"), "w") as f:
            f.write("".join(json.dumps(r) + "\n" for r in recs))
        return d

    def test_results_count_verdict_and_place(self):
        q = self.queue()
        self.assertEqual([t["id"] for t, _, _ in sc.decided_results(q)],
                         ["0000_stairs_CellA_000001", "0001_stairs_CellA_000002"])
        out = os.path.join(q, "calib.json")
        with patch.object(sc, "Scenes", FakeScenes):
            sc.main(["results", "--queue", q, "--staging", q, "--fo4-data", q, "--json", out])
        with open(out) as f:
            got = json.load(f)
        self.assertEqual(got["tally"], {"same": 1, "verdict": 1})       # the game stopped 0.9 m before the offline stop
        rows = {r["ref"]: r for r in got["rows"]}
        self.assertEqual((rows["000002:Fallout4.esm"]["game"], rows["000002:Fallout4.esm"]["sim"]), ("STUCK", "STUCK"))

    def test_routes_replay(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "routesfull_CellA.json"), "w") as f:
            json.dump({"routes": [ROUTE, dict(ROUTE, ref="000002:Fallout4.esm"),
                                  {"kind": "door", "ref": "000003:Fallout4.esm"}]}, f)
        out = os.path.join(d, "replay.json")
        with patch.object(sc, "Scenes", FakeScenes):
            sc.main(["routes", "--routes-dir", d, "--staging", d, "--fo4-data", d, "--json", out])
        with open(out) as f:
            self.assertEqual(json.load(f)["tally"], {"PASS": 1, "STUCK": 1})


if __name__ == "__main__":
    unittest.main()
