"""Actual CLI source-world identity and truthful terrain coverage checks."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_placement_frame import rec, grup

ROOT = Path(__file__).resolve().parents[1]


def plugin(path, masters, world, *, land=False, refs=True, position=(1., 1., 0.), parent=(0, 0), persistent=False):
    fields = [(b"HEDR", struct.pack("<fII", 1., 0, 0))]
    for master in masters:
        fields += [(b"MAST", master.encode() + b"\0"), (b"DATA", bytes(8))]
    own = len(masters) << 24
    cell_id = own | 0x100
    cell = rec(b"CELL", cell_id, [(b"XCLC", struct.pack("<iiI", *parent, 0))])
    children = []
    if land:
        children.append(rec(b"LAND", own | 0x101, [(b"VHGT", struct.pack("<f", 0.) + bytes(1092))]))
    if refs:
        fields_ref = [(b"NAME", struct.pack("<I", 0x10))]
        if position is not None:
            fields_ref += [(b"DATA", struct.pack("<6f", *position, 0., 0., 0.))]
        children.append(rec(b"ACHR", own | 0x200, fields_ref))
    body = cell + grup(cell_id, 6, [grup(cell_id, 9, children)])
    if not persistent:
        body = grup(bytes(4), 4, [grup(bytes(4), 5, [body])])
    world_record = rec(b"WRLD", world, [(b"EDID", b"TestWorld\0")])
    path.write_bytes(rec(b"TES4", 0, fields) + grup(b"WRLD", 0, [world_record, grup(world, 1, [body])]))


class PlacementWorldIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.core = self.base / "core.esp"
        self.mission = self.base / "mission.esp"
        plugin(self.core, ["Starfield.esm"], 0x01000803, land=True, refs=False)

    def run_cli(self, *extra):
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [self.core, self.mission]}
        result = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "scripts/oracles/placement_frame.py"),
                                 "--core", str(self.core), "--plugin", str(self.mission),
                                 "--world-edid", "TestWorld", "--json", *extra],
                                capture_output=True, text=True, timeout=30, cwd=self.base)
        self.assertEqual(before, {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [self.core, self.mission]})
        self.assertNotIn("Traceback", result.stderr)
        return result

    def test_same_raw_world_with_different_owner_is_rejected(self):
        plugin(self.mission, ["Other.esm"], 0x01000803)
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["identity_ok"])
        self.assertEqual(report["refs"][0]["reason"], "world_identity")

    def test_rebased_same_owner_is_accepted_with_casefolded_master(self):
        for masters, fid in [(["CORE.ESP", "Starfield.esm"], 0x803),
                             (["Starfield.esm", "core.esp"], 0x01000803)]:
            with self.subTest(masters=masters):
                plugin(self.mission, masters, fid)
                result = self.run_cli()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report["world_key"], report["plugin_world_key"])
                self.assertEqual(report["world_key"], {"plugin": "core.esp", "local_id": "000803"})

    def test_empty_exterior_cells_do_not_prove_missing_terrain(self):
        plugin(self.core, ["Starfield.esm"], 0x01000803, land=False, refs=False)
        plugin(self.mission, ["core.esp"], 0x803)
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        row = json.loads(result.stdout)["refs"][0]
        self.assertIsNone(row["core_has_coverage"])
        self.assertEqual(row["reason"], "coverage_unknown")
        self.assertNotIn("no_coverage", result.stdout)

    def test_outside_local_land_is_unknown_not_terrain_absence(self):
        plugin(self.mission, ["core.esp"], 0x803, position=(150., 1., 0.), parent=(1, 0))
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["refs"][0]["reason"], "coverage_unknown")

    def test_missing_data_and_spatial_parent_guards_are_retained(self):
        for position, reason in [(None, "missing_or_invalid_position"), ((100., 1., 0.), "parent_mismatch")]:
            with self.subTest(reason=reason):
                plugin(self.mission, ["core.esp"], 0x803, position=position)
                result = self.run_cli()
                self.assertEqual(result.returncode, 1)
                self.assertEqual(json.loads(result.stdout)["refs"][0]["reason"], reason)

    def test_persistent_parent_does_not_constrain_spatial_grid(self):
        plugin(self.core, ["Starfield.esm"], 0x01000803, land=True, refs=False, parent=(-1, 0))
        plugin(self.mission, ["core.esp"], 0x803, position=(-1., 1., 0.), persistent=True)
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_invalid_master_slot_is_clean_read_error(self):
        plugin(self.mission, [], 0x02000803)
        result = self.run_cli()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("world", result.stderr)

    def test_malformed_or_ambiguous_master_identity_is_refused(self):
        cases = [(["core.esp", "CORE.ESP"], 0x803), (["mission.esp"], 0x803),
                 (["../core.esp"], 0x803), (["core.esp"], 0), (["core.esp"], 0xFF000803)]
        for masters, fid in cases:
            with self.subTest(masters=masters, fid=fid):
                plugin(self.mission, masters, fid)
                result = self.run_cli()
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("world", result.stderr)

    def test_world_mismatch_does_not_succeed_with_zero_refs(self):
        plugin(self.mission, ["Other.esm"], 0x01000803, refs=False)
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["identity_ok"])

    def test_unimplemented_anchor_is_refused_instead_of_ignored(self):
        plugin(self.mission, ["core.esp"], 0x803)
        result = self.run_cli("--anchor", "Good")
        self.assertEqual(result.returncode, 2)
        self.assertIn("anchor", result.stderr)


if __name__ == "__main__":
    unittest.main()
