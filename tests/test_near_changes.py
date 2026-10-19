"""near_changes.py lists what changed between two core builds around one spot (v6 Red Rocket crash, 2026-10-19)."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "terrain"))
import near_changes  # noqa: E402


def build(bases, refs, **promoted):
    return dict({"world": "W", "edid_prefix": "FO4Core_", "bases": bases, "refs": refs}, **promoted)


class NearChangesTests(unittest.TestCase):
    def setUp(self):
        door = {"model": "fo4port/reddoor", "collision": "fo4-native"}
        can = {"model": "fo4port/tincan01", "collision": "fo4-native"}
        self.old = build([door, can], [
            {"src": "00D9B6:Fallout4.esm", "base": 0, "pos": [-1000, 1130, 105]},
            {"src": "000AAA:Fallout4.esm", "base": 1, "pos": [-1010, 1140, 105]},
            {"src": "000FAR:Fallout4.esm", "base": 1, "pos": [0, 0, 0]}])
        self.new = build([dict(door, door={"rig": "native"}), can], [
            {"src": "00D9B6:Fallout4.esm", "base": 0, "pos": [-1000, 1130, 105]},
            {"src": "000AAA:Fallout4.esm", "base": 1, "pos": [-1010, 1140, 105]},
            {"src": "000FAR:Fallout4.esm", "base": 0, "pos": [0, 0, 0]}],
            workshops=[{"src": "054BAE:Fallout4.esm", "edid": "FO4Core_wkshp", "pos": [-1005, 1136, 105], "radius": 250}])

    def test_changes_near_the_spot_are_listed_and_far_ones_are_not(self):
        rows = {r["src"]: r["kinds"] for r in near_changes.changes(self.old, self.new, (-1005, 1136), 300)}
        self.assertEqual(rows, {"00D9B6:Fallout4.esm": ["base.door"], "054BAE:Fallout4.esm": ["only_new"]})

    def test_moves_turns_scale_and_door_destinations_are_changes(self):
        """Codex on #375: a moved, turned or rescaled reference and a new door destination were reported as unchanged."""
        import copy
        door = {"src": "00D9B7:Fallout4.esm", "edid": "FO4Core_door", "pos": [-1000, 1130, 105],
                "destination": {"plugin": "FO4Port.esm", "id": 0x10}, "arrival": {"pos": [1, 2, 3]}}
        for change, kind in ((lambda o: o["refs"][1].update(pos=[-990, 1140, 105]), "placement.pos"),
                             (lambda o: o["refs"][1].update(rot=[0, 0, 1.5]), "placement.rot"),
                             (lambda o: o["refs"][1].update(scale=2.0), "placement.scale"),
                             (lambda o: o["doors"][0]["destination"].update(id=0x11), "promoted.destination")):
            old, new = copy.deepcopy(self.old), copy.deepcopy(self.old)
            old["doors"], new["doors"] = [dict(door)], [copy.deepcopy(door)]
            change(new)
            rows = [k for r in near_changes.changes(old, new, (-1005, 1136), 300) for k in r["kinds"]]
            self.assertEqual(rows, [kind])
        old = copy.deepcopy(self.old)
        new = copy.deepcopy(self.old)
        new["refs"][1]["pos"] = [-1010.0004, 1140, 105]                               # rounding, not a move
        self.assertEqual(near_changes.changes(old, new, (-1005, 1136), 300), [])

    def test_conversion_differences_come_from_the_manifests(self):
        old_conv = {"fo4port/tincan01": {"collision_source": "fo4-native"}}
        new_conv = {"fo4port/tincan01": {"collision_source": "fo4-native", "movable_kg": 1.0}}
        rows = {r["src"]: r["kinds"] for r in near_changes.changes(self.old, self.new, (-1005, 1136), 300,
                                                                    old_conv, new_conv)}
        self.assertEqual(rows["000AAA:Fallout4.esm"], ["conversion.movable_kg"])

    def test_cli_reads_two_builds(self):
        with tempfile.TemporaryDirectory() as d:
            for name, obj in (("a", self.old), ("b", self.new)):
                os.makedirs(os.path.join(d, name))
                with open(os.path.join(d, name, "objects.json"), "w", encoding="utf-8") as f:
                    json.dump(obj, f)
            man = os.path.join(d, "manifest.json")
            with open(man, "w", encoding="utf-8") as f:
                json.dump({"items": [{"model": "fo4port/TinCan01", "movable": {"mass_kg": 1.0}}]}, f)
            self.assertEqual(near_changes.conversions([man]), {"fo4port/tincan01": {"movable_kg": 1.0}})
            self.assertEqual(near_changes.main(["--old", os.path.join(d, "a"), "--new", os.path.join(d, "b"),
                                                "--center=-1005,1136"]), 0)
            moved = json.loads(json.dumps(self.old))
            moved["refs"][1]["pos"] = [-990, 1140, 105]
            with open(os.path.join(d, "b", "objects.json"), "w", encoding="utf-8") as f:
                json.dump(moved, f)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                near_changes.main(["--old", os.path.join(d, "a"), "--new", os.path.join(d, "b"), "--center=-1005,1136"])
            summary = json.loads(out.getvalue().splitlines()[-1])
            self.assertEqual(summary, {"by_kind": {"placement.pos": 1}, "changed_references": 1})


if __name__ == "__main__":
    unittest.main()
