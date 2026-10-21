"""Synthetic tests for scripts/game/nif_float_scan.py: a NIF built with fo4sf.nif holding the float 0.02 in a box blob's
half-extent (as sfcollision.box_blob writes a clamped door leaf) and, unaligned, in another block."""
import contextlib
import importlib.util
import io
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nif_float_scan", ROOT / "scripts" / "game" / "nif_float_scan.py")
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)
nifmod, sfcollision = scan.nifmod, scan.sfcollision


def template():
    t = bytearray(sfcollision.BLOB_SIZE)
    t[:8] = b"\x00\x00\x18\x18TAG0"
    t[2000:2012] = b"hknpBoxShape"
    struct.pack_into("<3f", t, 528, 1, 0, 0)
    struct.pack_into("<3f", t, 544, 0, 1, 0)
    struct.pack_into("<3f", t, 560, 0, 0, 1)
    return bytes(t)


def build():
    n = nifmod.NifFile()
    n.add_block("NiNode", b"\0" * 16)
    blob = sfcollision.box_blob(template(), (0, 0, 0.5), (0.4, 0.02, 1.0))
    n.add_block("bhkPhysicsSystem", struct.pack("<I", len(blob)) + blob)
    n.add_block("NiStringExtraData", b"\x01" + struct.pack("<f", 0.02))
    return nifmod.serialize(n)


class NifFloatScan(unittest.TestCase):
    def test_hits_name_the_block_and_the_half_extent(self):
        hits = scan.scan(build(), 0x3CA3D70A)
        self.assertIn((1, "bhkPhysicsSystem", 4 + 556, "box half-extent hy"), hits)
        self.assertIn((2, "NiStringExtraData", 1, "unaligned"), hits)
        self.assertFalse([h for h in hits if h[0] == 0])

    def test_main_filters_by_name_and_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            for stem in ("bldcounterdoor01", "other"):
                with open(os.path.join(tmp, stem + ".nif"), "wb") as f:
                    f.write(build())
            out = os.path.join(tmp, "out.json")
            with contextlib.redirect_stdout(io.StringIO()) as text:
                self.assertEqual(scan.main([tmp, "--names", "BldCounterDoor01|safedoor01", "--json", out]), 0)
            self.assertIn("1 NIFs scanned, 1 hold 0x3ca3d70a", text.getvalue())
            with open(out) as f:
                self.assertEqual(list(json.load(f)["found"]), ["bldcounterdoor01.nif"])


if __name__ == "__main__":
    unittest.main()
