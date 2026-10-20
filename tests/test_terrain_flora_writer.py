"""FLOR Ingredient through the actual terrain writer (dotnet/TerrainOverlays) on the synthetic master of
test_terrain_reference_identity (dotnet/TerrainIdentityFixture), never a game: default seed and a custom MISC both
serialize to PFIG; a STAT ingredient is refused before publication (docs/terrain/flora.md)."""
import copy
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import test_terrain_reference_identity as tri  # noqa: E402
import test_terrain_lights_writer as tlw  # noqa: E402

subrecords, field = tlw.subrecords, tlw.field
SEED, FIBER = 0x00260DF2, 0x000055AF


class TerrainFloraWriterTests(unittest.TestCase):
    setUpClass = classmethod(tri.TerrainReferenceIdentityTests.setUpClass.__func__)
    run_writer = tri.TerrainReferenceIdentityTests.run_writer
    promote = tri.TerrainReferenceIdentityTests.promote

    def with_flora(self, objects, ingredient="00260DF2:Starfield.esm", edid="FO4Core_flor_01c25e_synthetic"):
        obj = copy.deepcopy(objects)
        r = obj["refs"][0]
        obj["flora"] = [dict(r, reference_index=0, edid=edid, model="synthetic_melon.nif",
                             name="Melon Vine", ingredient=ingredient)]
        obj["refs"] = obj["refs"][1:]
        return obj

    def pfig(self, stage, src="000001:Synthetic.esm"):
        ids = json.loads((stage / "formids.json").read_text())
        recs = tri.records(stage / "Synthetic.esm")
        flor = recs[int(ids["flora"][src]["base"], 16)]
        self.assertEqual(flor[0], b"FLOR")
        return struct.unpack("<I", field(flor[1], b"PFIG"))[0], ids, recs, flor

    def test_default_seed_serializes_to_pfig(self):
        base = self.promote([])
        proc, stage = self.run_writer(self.with_flora(base), "flora-default")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        pfig, ids, recs, flor = self.pfig(stage)
        self.assertEqual(pfig, SEED)
        self.assertEqual(field(flor[1], b"EDID"), b"FO4Core_flor_01c25e_synthetic\0")
        self.assertIn(struct.pack("<I", 0x00222E03), field(flor[1], b"KWDA") or b"")
        self.assertEqual(recs[int(ids["flora"]["000001:Synthetic.esm"]["ref"], 16)][0], b"REFR")

    def test_custom_misc_ingredient_serializes_to_pfig(self):
        base = self.promote([])
        proc, stage = self.run_writer(self.with_flora(base, ingredient="00055AF:Starfield.esm"), "flora-fiber")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        pfig, _ids, _recs, _flor = self.pfig(stage)
        self.assertEqual(pfig, FIBER)

    def test_stat_ingredient_is_refused_before_publication(self):
        base = self.promote([])
        proc, stage = self.run_writer(self.with_flora(base), "flora-refusals")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        pinned = {n: (stage / n).read_bytes() for n in ("Synthetic.esm", "formids.json")}
        proc, _ = self.run_writer(self.with_flora(base, ingredient="000010:Starfield.esm"), "flora-refusals")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("MISC or LVLI", proc.stderr + proc.stdout)
        self.assertEqual({n: (stage / n).read_bytes() for n in pinned}, pinned)
        proc, _ = self.run_writer(self.with_flora(base, ingredient="3807C6:Starfield.esm"), "flora-refusals")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("MISC or LVLI", proc.stderr + proc.stdout)
        self.assertEqual({n: (stage / n).read_bytes() for n in pinned}, pinned)
