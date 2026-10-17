"""Map-marker LCSR through the actual terrain writer (dotnet/TerrainOverlays) on the synthetic master of
test_terrain_reference_identity (dotnet/TerrainIdentityFixture map-marker extra arg), never a game: Grid from
spawn_cell and Unknown -1 serialize as the vanilla 0xFFFFFFFF tail (docs/terrain/map-markers.md)."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import test_terrain_reference_identity as tri  # noqa: E402
import test_terrain_lights_writer as tlw  # noqa: E402

subrecords, field = tlw.subrecords, tlw.field
MAPMARKER_REF_TYPE = 0x0002271F
LCSR_TAIL = 0xFFFFFFFF


class TerrainMapMarkerWriterTests(unittest.TestCase):
    run_writer = tri.TerrainReferenceIdentityTests.run_writer
    promote = tri.TerrainReferenceIdentityTests.promote

    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet")
        if not cls.dotnet:
            raise unittest.SkipTest(".NET 9 SDK/runtime needed for actual writer test")
        sdks = subprocess.run([cls.dotnet, "--list-sdks"], capture_output=True, text=True, check=True)
        if not any(line.startswith("9.") for line in sdks.stdout.splitlines()):
            raise unittest.SkipTest(".NET 9 SDK/runtime needed for actual writer test")
        build = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet/TerrainIdentityFixture"),
                                "-c", "Release", "--nologo"], capture_output=True, text=True)
        if build.returncode:
            raise AssertionError(build.stdout + build.stderr)
        temporary = tempfile.TemporaryDirectory(prefix="fo4sf-mapmarker-")
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        cls.master = cls.root / "master/Starfield.esm"
        fixture = ROOT / "dotnet/TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll"
        subprocess.run([cls.dotnet, str(fixture), str(cls.master), "map-marker"], capture_output=True, check=True)
        cls.writer = Path(os.environ.get("FO4SF_TERRAIN_WRITER",
                                         ROOT / "dotnet/TerrainOverlays/bin/Release/net9.0/TerrainOverlays.dll"))
        cls.params = {
            "plugin": "Synthetic.esm", "hmin": 0, "hmax": 1, "alignment": "absolute", "hnam": 0,
            "objects": "objects.json", "overlays": [{"world": "SyntheticWorld", "block": "SyntheticBlock",
            "location": "SyntheticLocation", "tag": "Synthetic", "n": 2, "cell_min": 0, "cell_max": 1,
            "btd_path": "Terrain/Synthetic.btd", "fnam": [0] * 4, "bounds_min_m": 0, "bounds_max_m": 200,
            "spawn": [1, 1, 2], "spawn_cell": [1, 0], "coc": "SyntheticSpawn",
            "anchor": {"form_id": 0x800, "edid": "SyntheticAnchor", "local": [1, 1, 2]}}]}
        cls.objects = {"world": "SyntheticWorld", "bases": [{"edid": "SyntheticBase", "model": "synthetic.nif"}],
                       "refs": [{"src": f"{i + 1:06X}:Synthetic.esm", "base": 0, "cell": cell,
                                 "pos": pos, "rot": [0, 0, i / 10], "scale": 1 + i / 10, "disabled": False}
                                for i, (cell, pos) in enumerate(zip(([0, 0], [0, 1], [1, 1]),
                                                                   ([1, 2, 3], [4, 101, 6], [101, 102, 9])))]}

    def test_lcsr_tail_is_ffffffff_and_grid_follows_spawn_cell(self):
        proc, stage = self.run_writer(self.objects, "map-marker-lcsr")
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        ids = json.loads((stage / "formids.json").read_text())
        self.assertIn("map_markers", ids)
        marker = int(ids["map_markers"]["SyntheticWorld"], 16)
        recs = tri.records(stage / "Synthetic.esm")
        lctn = next(r for r in recs.values() if r[0] == b"LCTN")
        lcsr = field(lctn[1], b"LCSR")
        self.assertIsNotNone(lcsr)
        self.assertEqual(len(lcsr), 20)
        lcrt, refr, wrld, grid, tail = struct.unpack_from("<5I", lcsr)
        self.assertEqual(lcrt, MAPMARKER_REF_TYPE)
        self.assertEqual(refr & 0xFFFFFF, marker)
        self.assertEqual(grid, struct.unpack("<I", struct.pack("<hh", 0, 1))[0])  # Y then X of spawn_cell [1, 0]
        self.assertEqual(tail, LCSR_TAIL)
        self.assertEqual(recs[marker][0], b"REFR")
        self.assertEqual(recs[marker][3] & 0xC00, 0xC00)

    def test_missing_template_skips_map_marker_restore(self):
        identity = tri.TerrainReferenceIdentityTests()
        identity.dotnet = self.dotnet
        identity.writer = self.writer
        identity.params = self.params
        identity.objects = self.objects
        identity.root = self.root
        identity.master = self.root / "master-plain/Starfield.esm"
        fixture = ROOT / "dotnet/TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll"
        identity.master.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([self.dotnet, str(fixture), str(identity.master)], capture_output=True, check=True)
        proc, stage = identity.run_writer(self.objects, "map-marker-skip")
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        ids = json.loads((stage / "formids.json").read_text())
        self.assertNotIn("map_markers", ids)
        self.assertIn("003E5E12 missing", proc.stdout + proc.stderr)
