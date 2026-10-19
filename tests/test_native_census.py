"""native_census: wrapper/native split, Starfield declarations elsewhere, FO4 call sites, on synthetic zips."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/research"))
spec = importlib.util.spec_from_file_location("native_census", ROOT / "scripts/research/native_census.py")
nc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nc)

FO4_ACTOR = """ScriptName Actor extends ObjectReference Native Hidden
Function AddSpell(Spell akSpell, bool abVerbose = true) native
Function SetCompanion(bool abSet = true)
EndFunction
Function StartCombat(Actor a) native
"""


class NativeCensusTest(unittest.TestCase):
    def test_census(self):
        with tempfile.TemporaryDirectory() as t:
            sfz, f4z = os.path.join(t, "sf", "CR.zip"), os.path.join(t, "f4", "Base.zip")
            os.makedirs(os.path.dirname(sfz)); os.makedirs(os.path.dirname(f4z))
            with zipfile.ZipFile(sfz, "w") as z:
                z.writestr("Scripts/Source/Actor.psc", "ScriptName Actor\nFunction StartCombat(Actor a) native\n")
                z.writestr("Scripts/Source/ObjectReference.psc", "ScriptName ObjectReference\nFunction AddSpell(Spell s) native\n")
            with zipfile.ZipFile(f4z, "w") as z:
                z.writestr("Actor.psc", FO4_ACTOR)
                z.writestr("HC_ManagerScript.psc", "ScriptName HC_ManagerScript\n PlayerRef.AddSpell(x)\n PlayerRef.addspell (y)\n")
            out = os.path.join(t, "out", "c.json")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(nc.main(["--sf-zip", sfz, "--fo4-zip", f4z, "--out", out]), 0)
            rows = {r["name"]: r for r in json.load(open(out))}
            self.assertTrue(rows["AddSpell"]["native"])
            self.assertEqual(rows["AddSpell"]["sf_declared_in"], ["ObjectReference"])
            self.assertEqual(rows["AddSpell"]["fo4_calls"], 2)
            self.assertFalse(rows["SetCompanion"]["native"])
            self.assertIn("actor.AddSpell: native", buf.getvalue())
            self.assertEqual(nc.main(["--sf-zip", sfz, "--fo4-zip", f4z, "--out", os.path.join(t, "sf", "x.json")]), 2)


if __name__ == "__main__":
    unittest.main()
