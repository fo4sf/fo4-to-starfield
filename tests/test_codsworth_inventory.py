"""Codsworth inventory: archive scan, NIF summary and voice-folder counts on synthetic BA2s."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fo4sf import nif, sfnif  # noqa: E402
from ba2_fixture import general_archive  # noqa: E402

spec = importlib.util.spec_from_file_location("codsworth_inventory", ROOT / "scripts/actors/codsworth_inventory.py")
inv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inv)


class CodsworthInventoryTest(unittest.TestCase):
    def test_scan(self):
        shape = sfnif.StaticShape(b"Body", b"aa\\bb", 3, 3, "materials/x.mat", (0, 0, 0, 1), (0, 0, 0, 1, 1, 1))
        nif_bytes = nif.serialize(sfnif.build_static_nif(b"MiniBot", [shape]))
        with tempfile.TemporaryDirectory() as d:
            fo4, sf, out = Path(d, "fo4"), Path(d, "sf"), Path(d, "out")
            fo4.mkdir(); sf.mkdir()
            (fo4 / "Fallout4 - Meshes.ba2").write_bytes(general_archive({"Meshes\\Actors\\MrHandy\\Codsworth.nif": nif_bytes,
                                                                          "Meshes\\Other.nif": nif_bytes}))
            (fo4 / "Fallout4 - Voices.ba2").write_bytes(general_archive({
                "Sound\\Voice\\Fallout4.esm\\RobotMrHandyCodsworth\\00012345_1.fuz": b"x",
                "Sound\\Voice\\Fallout4.esm\\RobotMrHandyCodsworth\\00012346_1.fuz": b"x",
                "Sound\\Voice\\Fallout4.esm\\NPCMPrestonGarvey\\00000001_1.fuz": b"x"}))
            (sf / "Starfield - Meshes01.ba2").write_bytes(general_archive({"meshes\\actors\\minibot\\minibot.nif": nif_bytes}))
            (sf / "Starfield - Voices01.ba2").write_bytes(general_archive({"sound\\voice\\starfield.esm\\npcmsam\\0001_1.wem": b"x"}))
            self.assertEqual(inv.main(["--fo4-data", str(fo4), "--sf-data", str(sf), "--out", str(out)]), 0)
            text = (out / "codsworth_inventory.txt").read_text()
        self.assertIn("meshes\\actors\\mrhandy\\codsworth.nif", text)
        self.assertNotIn("other.nif", text)
        self.assertIn("minibot.nif", text)
        self.assertIn("fallout4.esm\\robotmrhandycodsworth: 2 {'.fuz': 2}", text)
        self.assertNotIn("prestongarvey", text)
        self.assertIn("starfield.esm\\npcmsam: 1 {'.wem': 1}", text)


if __name__ == "__main__":
    unittest.main()
