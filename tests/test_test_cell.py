"""dotnet/TestCell on a synthetic FO4Port.esm (its own `fixture` command), never a game: the object test room holds one
interior cell with the COC marker, floor tiles, lights and one reference per resolved spot, and lists what it could
not find (tools/testcell/README.md)."""
import json
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
from test_map_markers_plugin import build  # noqa: E402

LAYOUT = {
    "cell": "FO4SF_TestCell", "spacing_m": 4,
    "rows": [
        {"row": "A", "title": "doors", "items": [
            {"vanilla": "0AA24A", "name": "Akila door"},
            {"from_cell": "FO4Port_Vault95", "type": "DOOR", "max": 4},
            {"from_cell": "FO4Port_NoSuchCell", "type": "DOOR"}]},
        {"row": "B", "items": [
            {"edid": "FO4Port_TrashcanMetalOffice01"},
            {"edid": "FO4Port_PryDoor01"},
            {"edid": "FO4Port_NotConverted"}]},
    ],
}


class TestCellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet")
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        cls.tool = build(cls.dotnet, "TestCell")
        temporary = tempfile.TemporaryDirectory(prefix="fo4sf-testcell-")
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        subprocess.run([cls.dotnet, str(cls.tool), "fixture", str(cls.root / "port")], capture_output=True, check=True)
        layout = cls.root / "layout.json"
        layout.write_text(json.dumps(LAYOUT))
        cls.proc = subprocess.run([cls.dotnet, str(cls.tool), "build", str(cls.root / "port/FO4Port.esm"), str(layout),
                                   str(cls.root / "out")], capture_output=True, text=True)
        cls.sheet = json.loads((cls.root / "out/spots.json").read_text()) if cls.proc.returncode == 0 else None

    def test_build_succeeds_and_reports_the_missing(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stdout + self.proc.stderr)
        self.assertIn("6 objects in 8 spots (2 missing)", self.proc.stdout)
        missing = [s["spot"] for s in self.sheet["spots"] if s["missing"]]
        self.assertEqual(missing, ["A5", "B3"])

    def test_spots_resolve_in_order(self):
        spots = {s["spot"]: s for s in self.sheet["spots"]}
        self.assertEqual(spots["A1"]["base"], "0AA24A:Starfield.esm")
        # the cell's distinct doors in placement order (VltDoor01 twice, the stair is not a door), the persistent load
        # door between the temporary ones (review of #430)
        self.assertEqual([spots[k]["name"] for k in ("A2", "A3", "A4")],
                         ["FO4Port_VltDoor01", "FO4Port_VltLoadDoor01", "FO4Port_VltDoor02"])
        self.assertEqual(spots["B1"]["type"], "MSTT")
        self.assertEqual(spots["B2"]["name"], "FO4Port_PryDoor01")                 # the clash-suffixed editor ID
        self.assertEqual(spots["B2"]["base"], "000804:FO4Port.esm")
        self.assertEqual((spots["A3"]["x"], spots["A3"]["y"], spots["B1"]["x"], spots["B1"]["y"]), (8, 0, 0, 4))

    def test_plugin_records(self):
        plugin = self.root / "out/FO4SFTestCell.esm"
        recs = tri.records(plugin)
        sig, payload, _, _ = recs[0x800]
        self.assertEqual(sig, b"CELL")
        self.assertEqual(tlw.field(payload, b"EDID").rstrip(b"\0"), b"FO4SF_TestCell")
        refs = {fid: r for fid, r in recs.items() if r[0] == b"REFR"}
        self.assertTrue(all(r[2] == 0x800 for r in refs.values()))                 # all in the test cell
        names = [struct.unpack("<I", tlw.field(p, b"NAME"))[0] for _, p, _, _ in refs.values()]
        self.assertEqual(names.count(0x000032), 1)                                 # one COC marker
        self.assertGreater(names.count(0x050776), 0)                               # floor tiles
        self.assertGreater(names.count(0x03D38C), 0)                               # lights
        self.assertEqual(names.count(0x0AA24A), 1)                                 # the vanilla door, master index 0
        self.assertEqual(sorted(n for n in names if n >> 24 == 1), [0x01000800, 0x01000801, 0x01000803, 0x01000804, 0x01000805])
        self.assertIn(b"FO4Port.esm", plugin.read_bytes()[:400])                   # the port is the second master


if __name__ == "__main__":
    unittest.main()
