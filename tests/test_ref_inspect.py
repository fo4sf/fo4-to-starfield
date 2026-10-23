"""scripts/terrain/ref_inspect.py: one reference, its base, XTEL, scripts and neighbours, read-only, on a synthetic plugin."""
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_inspect  # noqa: E402
import vmad_patch as vp  # noqa: E402
from test_vmad_patch import OWN, rec, tiny_plugin  # noqa: E402


class InspectTests(unittest.TestCase):
    def _write(self, d, **kw):
        path = os.path.join(d, "FO4Port.esm")
        with open(path, "wb") as f:
            f.write(tiny_plugin(**kw))
        return path

    def test_base_scripts_xtel_and_neighbours(self):
        hatch = rec(b"REFR", OWN | 0x805, [(b"NAME", struct.pack("<I", OWN | 0x800)),
                                           (b"DATA", struct.pack("<6f", 2.0, 3.0, 6.0, 0, 0, 0)),
                                           (b"XTEL", struct.pack("<I", 0x0100ABCD) + bytes(28)),
                                           (b"VMAD", vp.load_door_vmad("FO4TerrainCore.esm", 0x123))])
        far = rec(b"REFR", OWN | 0x806, [(b"NAME", struct.pack("<I", OWN | 0x800)),
                                         (b"DATA", struct.pack("<6f", 40.0, 3.0, 0.0, 0, 0, 0))])
        with tempfile.TemporaryDirectory() as d:
            out = ref_inspect.inspect(self._write(d, extra=[hatch, far]), 0x805, radius=4.0)
        self.assertEqual(out["base_sig"], "STAT")
        self.assertEqual(out["base_edid"], "FO4Port_door02")
        self.assertEqual(out["cell"], f"{OWN | 0x801:08X}")
        self.assertEqual(out["pos"], [2.0, 3.0, 6.0])
        self.assertEqual(out["xtel_door"], "0100ABCD")
        self.assertEqual(out["scripts"][0]["name"], "FO4SF_LoadDoor")
        self.assertEqual([r["ref"] for r in out["near"]], [f"{OWN | 0x803:08X}"])   # the 40 m one is out of reach
        self.assertEqual(out["near"][0]["dz"], -3.0)

    def test_missing_ref(self):
        with tempfile.TemporaryDirectory() as d:
            out = ref_inspect.inspect(self._write(d), 0x899)
        self.assertEqual(out["error"], "missing")


if __name__ == "__main__":
    unittest.main()
