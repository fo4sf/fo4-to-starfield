"""src/fo4sf/planet/biom.py: the planet's biome map copied out of a synthetic "Starfield - PlanetData.ba2"
(tests/ba2_fixture.py; no game data) under our planet's name, into both candidate folders."""
import hashlib
import os
import struct
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
from ba2_fixture import general_archive  # noqa: E402
from fo4sf.planet import biom  # noqa: E402

BIOMES = (0x0007F88A, 0x000FD00D)


def biom_bytes(ids=BIOMES, body=b"\x11" * 64):
    return struct.pack(f"<HI{len(ids)}I", biom.MAGIC, len(ids), *ids) + body


class BiomTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = os.path.join(self.tmp.name, "Data")
        os.makedirs(self.data)
        self.out = os.path.join(self.tmp.name, "stage")
        self.map = biom_bytes()
        with open(os.path.join(self.data, biom.ARCHIVE), "wb") as f:
            f.write(general_archive({"planetdata/biomemaps/jemison.biom": self.map,
                                     "planetdata/biomemaps/mars.biom": biom_bytes((5,))}, compressed=True))

    def test_copy_goes_to_both_paths_unchanged(self):
        rep = biom.copy_biome_map(self.data, "Jemison", "FO4SF Probe", "FO4SFPlanet.esm", self.out,
                                  expect_biomes=list(reversed(BIOMES)))
        self.assertEqual(rep["files"], ["Data/PlanetData/BiomeMaps/fo4sf probe.biom",
                                        "Data/PlanetData/BiomeMaps/fo4sfplanet.esm/fo4sf probe.biom"])
        self.assertEqual(rep["biomes"], ["0007F88A", "000FD00D"])
        self.assertTrue(rep["biomes_match"])
        self.assertEqual(rep["sha256"], hashlib.sha256(self.map).hexdigest())
        for rel in rep["files"]:
            with open(os.path.join(self.out, *rel.split("/")), "rb") as f:
                self.assertEqual(f.read(), self.map)

    def test_a_map_for_other_biomes_is_refused_or_reported(self):
        with self.assertRaises(biom.BiomError):
            biom.copy_biome_map(self.data, "Jemison", "P", "FO4SFPlanet.esm", self.out, expect_biomes=[1, 2])
        self.assertFalse(os.path.exists(self.out))
        rep = biom.copy_biome_map(self.data, "Jemison", "P", "FO4SFPlanet.esm", self.out, expect_biomes=[1, 2],
                                  strict=False)
        self.assertEqual((rep["biomes_match"], rep["planet_biomes"]), (False, ["00000001", "00000002"]))
        self.assertTrue(os.path.isfile(os.path.join(self.out, "Data", "PlanetData", "BiomeMaps", "p.biom")))
        self.assertIsNone(biom.copy_biome_map(self.data, "Jemison", "P", "FO4SFPlanet.esm", self.out)["biomes_match"])

    def test_missing_archive_or_planet(self):
        with self.assertRaises(biom.BiomError):
            biom.copy_biome_map(self.data, "Nowhere", "P", "FO4SFPlanet.esm", self.out)
        with self.assertRaises(biom.BiomError):
            biom.copy_biome_map(os.path.join(self.tmp.name, "none"), "Jemison", "P", "FO4SFPlanet.esm", self.out)

    def test_header_checks(self):
        self.assertEqual(biom.biome_ids(biom_bytes((1, 2, 3))), [1, 2, 3])
        with self.assertRaises(biom.BiomError):
            biom.biome_ids(b"\x05\x01")
        with self.assertRaises(biom.BiomError):
            biom.biome_ids(struct.pack("<HI", 0x0104, 0))
        with self.assertRaises(biom.BiomError):
            biom.biome_ids(struct.pack("<HI", biom.MAGIC, 5) + bytes(8))


if __name__ == "__main__":
    unittest.main()
