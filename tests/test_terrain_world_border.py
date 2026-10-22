"""The world's border fields through the actual terrain writer (dotnet/TerrainOverlays) on the synthetic master of
test_terrain_reference_identity, never a game: without params "world_data" the WRLD keeps the template's (LC172World:
SmallWorld, HNAM 0); with make_core64c.py --world-border city's {"small_world": false, "hnam": 5} it carries
NewAtlantis's (DATA without SmallWorld, HNAM 5). Whether those fields stop the planet border in game is not yet proven
(docs/terrain/border.md)."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts" / "terrain"))
import test_terrain_reference_identity as tri  # noqa: E402
import test_terrain_lights_writer as tlw  # noqa: E402
import test_terrain_map_marker_writer as tmm  # noqa: E402
import make_core64c as mk  # noqa: E402

SMALL_WORLD = 0x01


class TerrainWorldBorderTests(unittest.TestCase):
    run_writer = tri.TerrainReferenceIdentityTests.run_writer
    setUpClass = classmethod(tmm.TerrainMapMarkerWriterTests.setUpClass.__func__)

    def world(self, world_data, name):
        params = self.params
        self.params = copy.deepcopy(params)
        if world_data is not None:
            self.params["world_data"] = world_data
        try:
            proc, stage = self.run_writer(self.objects, name)
        finally:
            self.params = params
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        worlds = [r for r in tri.records(stage / "Synthetic.esm").values()
                  if r[0] == b"WRLD" and tlw.field(r[1], b"EDID") == b"SyntheticWorld\0"]
        self.assertEqual(len(worlds), 1)
        payload = worlds[0][1]
        return tlw.field(payload, b"DATA")[0], tlw.field(payload, b"HNAM")

    def test_the_template_fields_stay_without_world_data(self):
        self.assertEqual(self.world(mk.WORLD_DATA["template"], "border-template"), (SMALL_WORLD, b"\x00"))

    def test_city_clears_small_world_and_sets_hnam_5(self):
        self.assertEqual(self.world(mk.WORLD_DATA["city"], "border-city"), (0, b"\x05"))


if __name__ == "__main__":
    unittest.main()
