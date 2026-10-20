"""Named-anchor source-coordinate measurements through the actual CLI."""
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_placement_frame import rec, grup

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/oracles/placement_frame.py"
ACTOR = {"fid": 0x02000300, "type": b"ACHR", "pos": (3., 4., 0.)}
ANCHOR = {"fid": 0x01000200, "edid": "Anchor", "pos": (0., 0., 0.)}


def write_plugin(path, masters, world, refs, cell_local=0x100):
    header = [(b"HEDR", struct.pack("<fII", 1., 0, 0))]
    for master in masters:
        header += [(b"MAST", master.encode() + b"\0"), (b"DATA", bytes(8))]
    own = len(masters) << 24
    cell_id = own | cell_local
    records = [rec(b"LAND", cell_id + 1, [(b"VHGT", struct.pack("<f", 0.) + bytes(1092))])]
    for r in refs:
        fields = [(b"NAME", struct.pack("<I", 0x10))]
        if r.get("edid") is not None:
            fields += [(b"EDID", r["edid"].encode() + b"\0")]
        if r.get("pos") is not None:
            fields += [(b"DATA", struct.pack("<6f", *r["pos"], 0., 0., 0.))]
        data = bytearray(rec(r.get("type", b"REFR"), r["fid"], fields))
        struct.pack_into("<I", data, 8, r.get("flags", 0))
        records.append(bytes(data))
    cell = rec(b"CELL", cell_id, [(b"XCLC", struct.pack("<iiI", 0, 0, 0))])
    children = cell + grup(cell_id, 6, [grup(cell_id, 9, records)])
    children = grup(bytes(4), 4, [grup(bytes(4), 5, [children])])
    wrld = rec(b"WRLD", world, [(b"EDID", b"TestWorld\0")])
    path.write_bytes(rec(b"TES4", 0, header) + grup(b"WRLD", 0, [wrld, grup(world, 1, [children])]))


class PlacementAnchorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.core = Path(self.temp.name) / "core.esp"
        self.mission = Path(self.temp.name) / "mission.esp"
        write_plugin(self.core, ["Starfield.esm"], 0x01000803, [ANCHOR])
        write_plugin(self.mission, ["core.esp", "Starfield.esm"], 0x803, [ACTOR])

    def run_cli(self, anchor="Anchor", text=False, same_file=False):
        paths = [self.core, self.mission]
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        command = [sys.executable, "-I", "-B", str(SCRIPT), "--core", str(self.core),
                   "--plugin", str(self.core if same_file else self.mission),
                   "--world-edid", "TestWorld", "--anchor", anchor]
        if not text:
            command += ["--json"]
        result = subprocess.run(command, capture_output=True, text=True, cwd=self.core.parent, timeout=30)
        self.assertEqual(before, {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
        self.assertNotIn("Traceback", result.stderr)
        return result

    def test_core_anchor_reports_distance_with_canonical_key_and_frame(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["anchor"]["status"], "ok")
        self.assertEqual(data["anchor"]["source_role"], "core")
        self.assertEqual(data["anchor"]["source_key"], {"plugin": "core.esp", "local_id": "000200"})
        self.assertEqual(data["refs"][0]["anchor_distance_m"], 5.)
        self.assertIn("source", data["anchor"]["distance_frame"])

    def test_three_dimensional_distance_and_text_output(self):
        write_plugin(self.mission, ["core.esp", "Starfield.esm"], 0x803, [dict(ACTOR, pos=(3., 4., 12.))])
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["refs"][0]["anchor_distance_m"], 13.)
        result = self.run_cli(text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("anchor_distance_m=13.0", result.stdout)

    def test_mission_anchor_and_casefolded_name(self):
        anchor = dict(ANCHOR, fid=0x02000200)
        write_plugin(self.core, ["Starfield.esm"], 0x01000803, [])
        write_plugin(self.mission, ["core.esp", "Starfield.esm"], 0x803, [anchor, ACTOR])
        result = self.run_cli("aNChOr")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["anchor"]["source_role"], "plugin")
        distances = {r["fid"]: r["anchor_distance_m"] for r in data["refs"]}
        self.assertEqual(distances, {"02000200": 0., "02000300": 5.})

    def test_rebased_plugin_override_replaces_core_anchor_position(self):
        override = dict(ANCHOR, fid=0x200, pos=(0., 0., 12.))
        write_plugin(self.mission, ["core.esp", "Starfield.esm"], 0x803, [override, ACTOR])
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["anchor"]["source_role"], "plugin")
        self.assertEqual(data["anchor"]["source_key"]["plugin"], "core.esp")
        actor = next(r for r in data["refs"] if r["fid"] == "02000300")
        self.assertEqual(actor["anchor_distance_m"], 13.)

    def test_missing_or_ambiguous_anchor_has_no_invented_distance(self):
        result = self.run_cli("Absent")
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertEqual(data["anchor"]["status"], "missing")
        self.assertTrue(all(r["anchor_distance_m"] is None for r in data["refs"]))
        write_plugin(self.core, ["Starfield.esm"], 0x01000803, [ANCHOR, dict(ANCHOR, fid=0x01000201)])
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["anchor"]["status"], "ambiguous")

    def test_nonfinite_or_missing_anchor_position_is_inconclusive(self):
        for position in [None, (math.nan, 0., 0.)]:
            with self.subTest(position=position):
                write_plugin(self.core, ["Starfield.esm"], 0x01000803, [dict(ANCHOR, pos=position)])
                result = self.run_cli()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data["anchor"]["status"], "invalid_position")
                self.assertIsNone(data["refs"][0]["anchor_distance_m"])

    def test_wrong_world_never_measures_distance(self):
        write_plugin(self.mission, ["Other.esm"], 0x01000803, [dict(ACTOR, fid=0x01000300)])
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["anchor"]["status"], "world_identity")
        self.assertIsNone(data["refs"][0]["anchor_distance_m"])

    def test_renamed_or_deleted_override_never_falls_back_to_old_anchor(self):
        for change, status in [({"edid": "Renamed"}, "missing"), ({"flags": 0x20}, "deleted")]:
            with self.subTest(change=change):
                override = dict(ANCHOR, fid=0x200, **change)
                write_plugin(self.mission, ["core.esp", "Starfield.esm"], 0x803, [override, ACTOR])
                result = self.run_cli()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["anchor"]["status"], status)

    def test_duplicate_source_key_is_clean_error_not_last_record_wins(self):
        write_plugin(self.core, ["Starfield.esm"], 0x01000803, [ANCHOR, ANCHOR])
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn("duplicate", result.stderr)

    def test_same_file_inputs_deduplicate_anchor(self):
        result = self.run_cli(same_file=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["anchor"]["status"], "ok")
        self.assertEqual(data["refs"][0]["anchor_distance_m"], 0.)

    def test_distance_uses_unrounded_source_position(self):
        write_plugin(self.mission, ["core.esp", "Starfield.esm"], 0x803, [dict(ACTOR, pos=(0.004, 0., 0.))])
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)["refs"][0]
        self.assertEqual(row["pos"][0], 0.)
        self.assertAlmostEqual(row["anchor_distance_m"], 0.004, places=8)

    def test_override_moved_to_another_world_does_not_use_old_core_position(self):
        other = self.core.parent / "other.esp"
        write_plugin(other, ["core.esp", "Starfield.esm"], 0x02000804,
                     [dict(ANCHOR, fid=0x200, pos=(50., 50., 50.))], cell_local=0x1100)
        first = self.mission.read_bytes()
        second = other.read_bytes().replace(b"TestWorld\0", b"OtherWrld\0")
        first_body = 24 + struct.unpack_from("<I", first, 4)[0]
        second_body = 24 + struct.unpack_from("<I", second, 4)[0]
        combined = grup(b"WRLD", 0, [first[first_body + 24:], second[second_body + 24:]])
        self.mission.write_bytes(first[:first_body] + combined)
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["anchor"]["status"], "outside_selected_world")
        self.assertTrue(all(r["anchor_distance_m"] is None for r in report["refs"]))

    def test_initially_disabled_reference_only_supplies_source_coordinates(self):
        write_plugin(self.core, ["Starfield.esm"], 0x01000803, [dict(ANCHOR, flags=0x800)])
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["anchor"]["record_flags"], 0x800)
        self.assertEqual(report["refs"][0]["anchor_distance_m"], 5.)
        self.assertIn("no runtime", report["anchor"]["distance_frame"])

    def test_blank_anchor_is_usage_error(self):
        result = self.run_cli(" ")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("nonempty", result.stderr)


if __name__ == "__main__":
    unittest.main()
