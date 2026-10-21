"""Synthetic tests for scripts/terrain/arrival_ground.py: ground under door-exit arrivals, in the core's local frame.
No game data: the BTD is a made-up 2 x 2-cell slope and the judge rows are invented."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf import btd  # noqa: E402
from fo4sf import terrain_grid as tg  # noqa: E402

spec = importlib.util.spec_from_file_location("arrival_ground", ROOT / "scripts" / "terrain" / "arrival_ground.py")
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)

MERGE = (-1200.0, -2700.0, 0.0)


def core_dir(tmp):
    """A core folder with a 2 x 2-cell BTD whose ground is z = 10 + x / 10 (local metres) and the measured merge."""
    n = 2
    xs = tg.sample_coords(n)
    metres = np.tile(10.0 + xs / 10.0, (n * 128, 1))
    raw = btd.quantize(metres, -50.0, 50.0)
    t = btd.Btd(6, -50.0, 50.0, [0x10861], raw, np.zeros_like(raw), np.zeros((2 * n, 2 * n, 8), np.uint8))
    os.makedirs(os.path.join(tmp, "Data", "Terrain"))
    with open(os.path.join(tmp, "Data", "Terrain", "W.btd"), "wb") as f:
        f.write(btd.write(t))
    with open(os.path.join(tmp, "overlays_params.json"), "w") as f:
        json.dump({"overlays": [{"world": "W", "planet_target_cell": [-12, -27], "btd_file": "Data/Terrain/W.btd"}]}, f)
    with open(os.path.join(tmp, "formids.json"), "w") as f:
        json.dump({"world": "W"}, f)
    return tmp


def row(i, why, pos, got, leg="out"):
    return {"id": f"{i:04d}_t", "leg": leg, "src": f"00000{i}:Fallout4.esm", "cell_edid": f"C{i}", "why": why,
            "pos": [pos[k] + MERGE[k] for k in range(3)], "got": {"pos": [got[k] + MERGE[k] for k in range(3)]}}


class ArrivalGround(unittest.TestCase):
    def test_reads_marker_and_landing_against_the_btd(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = core_dir(tmp)
            judge = {"results": [
                # floating marker: ground 10 at x 0, marker at 22, the player fell to the ground
                row(1, "WRONG_PLACE: 0.0 m off in xy, 12.0 m in z", (0.0, 0.0, 22.0), (0.0, 0.0, 10.0)),
                # buried marker: ground 15 at x 50, marker at 5, the player was lifted 16 m (onto something)
                row(2, "WRONG_PLACE: 0.0 m off in xy, 16.0 m in z", (50.0, 0.0, 5.0), (50.0, 0.0, 21.0)),
                {"id": "0003_t", "leg": "out", "why": "PASS", "pos": [0, 0, 0], "got": {"pos": [0, 0, 0]}},
                {"id": "0004_t", "leg": "out", "why": "WRONG_PLACE: no read"},
                # an interior (in) row: interior-cell coordinates, never read against the core's terrain
                row(5, "WRONG_PLACE: 3.0 m off in xy", (1.0, 2.0, 3.0), (4.0, 2.0, 3.0), leg="in"),
                # outside the 2 x 2-cell BTD: clamped edge heights are not ground
                row(6, "WRONG_PLACE: 0.0 m off in xy, 1.0 m in z", (500.0, 0.0, 5.0), (500.0, 0.0, 6.0))]}
            path = os.path.join(tmp, "judge.json")
            with open(path, "w") as f:
                json.dump(judge, f)
            offset = ag.vmad_patch.merge_offset(core)
            found = ag.read(ag.core_terrain(core), offset, ag.rows(ag.load(path)))
            self.assertEqual([f["id"] for f in found], ["0001_t", "0002_t", "0006_t"])
            a, b, c = found
            self.assertEqual(a["marker_local"], [0.0, 0.0, 22.0])
            self.assertEqual(sorted(a["ground_at_marker"]), ["bilinear", "tri_nw_se", "tri_sw_ne"])
            self.assertAlmostEqual(a["ground_at_marker"]["bilinear"], 10.0, delta=0.01)
            self.assertEqual((a["marker"], a["got"]), ("12.0 m above ground", "on ground"))
            self.assertAlmostEqual(b["ground_at_marker"]["tri_sw_ne"], 15.0, delta=0.01)
            self.assertEqual((b["marker"], b["got"]), ("10.0 m below ground", "6.0 m above ground"))
            self.assertEqual((c["ground_at_marker"], c["marker"]), (None, "outside the BTD"))
            self.assertEqual(len(ag.rows(ag.load(path), everything=True)), 4)

    def test_rules_that_disagree_leave_it_unresolved(self):
        # a saddle quad: corners 0, 2, 2, 0; at its centre bilinear gives 1.0, the SW-NE split 0.0, the NW-SE split 2.0
        class Saddle:
            origin, raw = 0.0, np.zeros((2, 2), np.uint16)

            def window(self, *_):
                return np.array([[0.0, 2.0], [2.0, 0.0]]), 0.0, 0.0
        h = ag.ground(Saddle(), tg.SF_STEP_M / 2, tg.SF_STEP_M / 2)
        self.assertEqual(sorted(h.values()), [0.0, 1.0, 2.0])
        self.assertEqual(ag.classify(1.0, h), "unresolved: -1.0 to +1.0 m from the ground under the three rules")
        self.assertEqual(ag.classify(5.0, h), "3.0 to 5.0 m above ground")
        self.assertEqual(ag.classify(-3.0, h), "3.0 to 5.0 m below ground")

    def test_refuses_a_core_without_one_btd_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "overlays_params.json"), "w") as f:
                json.dump({"overlays": [{"world": "W"}]}, f)
            with self.assertRaises(ValueError):
                ag.core_terrain(tmp)


if __name__ == "__main__":
    unittest.main()
