"""Fallout 4 next-gen BA2 headers (v7, v8) read with the v1 layout; unknown versions still refused. Synthetic only."""
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from fo4sf.ba2 import Ba2, Ba2Error  # noqa: E402
from ba2_fixture import general_archive  # noqa: E402


class NextGenVersionTests(unittest.TestCase):
    def write(self, data):
        t = tempfile.NamedTemporaryFile(suffix=".ba2", delete=False)
        t.write(data)
        t.close()
        self.addCleanup(os.remove, t.name)
        return t.name

    def test_v7_and_v8_read_like_v1(self):
        files = {"meshes/a.nif": b"one", "scripts/b.pex": b"two" * 50}
        for version in (1, 7, 8):
            for compressed in (False, True):
                with self.subTest(version=version, compressed=compressed):
                    a = Ba2(self.write(general_archive(files, compressed=compressed, version=version)))
                    self.assertEqual(a.version, version)
                    self.assertEqual(a.read("meshes/a.nif"), b"one")
                    self.assertEqual(a.read("scripts/b.pex"), b"two" * 50)

    def test_unknown_version_refused(self):
        data = bytearray(general_archive({"a.txt": b"x"}, version=1))
        struct.pack_into("<I", data, 4, 9)
        with self.assertRaises(Ba2Error):
            Ba2(self.write(bytes(data)))


if __name__ == "__main__":
    unittest.main()
