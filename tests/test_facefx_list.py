"""facefx_list: name-table scan on a synthetic General BA2."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from ba2_fixture import general_archive  # noqa: E402

spec = importlib.util.spec_from_file_location("facefx_list", ROOT / "scripts/research/facefx_list.py")
fl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fl)


class FaceFxListTest(unittest.TestCase):
    def test_scan(self):
        with tempfile.TemporaryDirectory() as t:
            open(os.path.join(t, "Starfield - FaceFX.ba2"), "wb").write(general_archive({
                "facefx/human/actor.facefx": b"x", "facefx/human/actoranalysis.facefx": b"y",
                "sound/voice/starfield.esm/npcmeven/a.ffxanim": b"z", "other.txt": b"w"}, version=2))
            open(os.path.join(t, "broken.ba2"), "wb").write(b"nope")
            open(os.path.join(t, "loose.facefx"), "wb").write(b"l")
            r = fl.scan(t)
            self.assertEqual(len(r["facefx"]), 3)
            self.assertEqual(r["ffxanim"], {"Starfield - FaceFX.ba2": 1})
            self.assertEqual(len(r["skipped"]), 1)
            self.assertEqual(fl.main([t]), 0)


if __name__ == "__main__":
    unittest.main()
