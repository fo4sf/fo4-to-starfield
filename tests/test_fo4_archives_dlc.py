"""pipeline.Fo4Archives with a DLC's Data folder: the base game's archives answer first, DLC archives fill in."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ba2_fixture import general_archive  # noqa: E402
from fo4sf import pipeline  # noqa: E402


class DlcArchiveTests(unittest.TestCase):
    def test_base_first_then_dlc_main_and_textures(self):
        with tempfile.TemporaryDirectory() as t:
            base, dlc = os.path.join(t, "Data"), os.path.join(t, "DlcData")
            os.makedirs(base)
            os.makedirs(dlc)
            files = {
                (base, "Fallout4 - Meshes.ba2"): {"meshes/a.nif": b"base-a"},
                (base, "Fallout4 - Materials.ba2"): {"materials/a.bgsm": b"base-mat"},
                (base, "Fallout4 - Textures1.ba2"): {"textures/a_d.dds": b"base-tex"},
                (dlc, "DLCRobot - Main.ba2"): {"meshes/a.nif": b"dlc-a", "meshes/dlc01/b.nif": b"dlc-b",
                                               "materials/dlc01/b.bgsm": b"dlc-mat"},
                (dlc, "DLCRobot - Textures.ba2"): {"textures/dlc01/b_d.dds": b"dlc-tex"},
                (dlc, "DLCRobot - Voices_en.ba2"): {"sound/v.fuz": b"voice"},
                (dlc, "Other - Main.ba2"): {"meshes/c.nif": b"not-a-dlc"},
            }
            for (d, name), entries in files.items():
                with open(os.path.join(d, name), "wb") as f:
                    f.write(general_archive(entries))
            plain = pipeline.Fo4Archives(base)
            self.assertIsNone(plain.mesh("meshes/dlc01/b.nif"))
            src = pipeline.Fo4Archives(base, [dlc])
            self.assertEqual(src.mesh("meshes/a.nif"), b"base-a")                # the base game wins: same bytes as before
            self.assertEqual(src.mesh("meshes/dlc01/b.nif"), b"dlc-b")
            self.assertEqual(src.material("materials/dlc01/b.bgsm"), b"dlc-mat")
            self.assertEqual(src.texture("dlc01/b_d.dds"), b"dlc-tex")
            self.assertEqual(src.texture("a_d.dds"), b"base-tex")
            self.assertIsNone(src.mesh("meshes/c.nif"))                          # only DLC*.ba2 from the extra folder
            self.assertEqual(len(src.meshes), 2)                                 # the voices archive is not opened


if __name__ == "__main__":
    unittest.main()
