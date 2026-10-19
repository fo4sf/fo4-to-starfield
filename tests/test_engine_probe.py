"""engine_probe: declaration parsing, zip scan, query and the output-folder refusal, on synthetic data."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("engine_probe", ROOT / "scripts/research/engine_probe.py")
ep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ep)

ACTOR = """ScriptName Actor extends ObjectReference Native Hidden
Function StartCombat(Actor akTarget) native
bool Function IsInPowerArmor() native
Event OnDeath(ObjectReference akKiller)
EndEvent
; Function NotThis()
Function EvaluatePackage(bool abResetAI = false) native
"""


class EngineProbeTest(unittest.TestCase):
    def test_declarations(self):
        d = ep.declarations(ACTOR)
        self.assertEqual([x["name"] for x in d], ["StartCombat", "IsInPowerArmor", "OnDeath", "EvaluatePackage"])
        self.assertTrue(d[0]["native"])
        self.assertEqual(d[2]["kind"], "event")

    def test_scan_and_query(self):
        with tempfile.TemporaryDirectory() as t:
            z = os.path.join(t, "ContentResources.zip")
            with zipfile.ZipFile(z, "w") as f:
                f.writestr("Scripts/Source/Actor.psc", ACTOR)
                f.writestr("Scripts/Source/CompanionActorScript.psc", "ScriptName CompanionActorScript\n")
            s = ep.scan_zip(z)
            self.assertEqual(s["psc_count"], 2)
            q = ep.query(s)
            self.assertTrue(q["scripts"]["CompanionActorScript"])
            self.assertFalse(q["scripts"]["FollowersScript"])
            self.assertTrue(q["functions"]["IsInPowerArmor"])
            self.assertFalse(q["functions"]["SwitchToPowerArmor"])
            self.assertIsNone(ep.query(ep.scan_zip(os.path.join(t, "missing.zip"))))

    def test_main_writes_and_refuses(self):
        with tempfile.TemporaryDirectory() as t:
            tools = os.path.join(t, "Tools")
            os.makedirs(tools)
            open(os.path.join(tools, "Starfield_Papyrus_Flags.flg"), "w").close()
            z = os.path.join(tools, "ContentResources.zip")
            with zipfile.ZipFile(z, "w") as f:
                f.writestr("Scripts/Source/Actor.psc", ACTOR)
            fo4 = os.path.join(t, "FO4Data")
            os.makedirs(os.path.join(fo4, "Scripts", "Source", "Base"))
            with open(os.path.join(fo4, "Scripts", "Source", "Base", "Actor.psc"), "w") as fh:
                fh.write(ACTOR)
            self.assertEqual(ep.main(["--sf-zip", z, "--sf-tools", tools, "--out", os.path.join(tools, "o.json")]), 2)
            out = os.path.join(t, "out", "probe.json")
            self.assertEqual(ep.main(["--sf-zip", z, "--sf-tools", tools, "--fo4-data", fo4, "--out", out]), 0)
            doc = json.load(open(out))
            self.assertEqual(doc["starfield_flags_files"], ["Starfield_Papyrus_Flags.flg"])
            self.assertFalse(doc["fo4"][0]["base_zip"]["exists"])
            self.assertTrue(doc["fo4"][0]["source_base"]["exists"])
            self.assertTrue(doc["fo4"][0]["query"]["functions"]["IsInPowerArmor"])

    def test_ck_layout_and_native_gap(self):
        # the FO4 CK puts Base.zip inside Data\Scripts\Source\Base, with DLC zips beside it
        with tempfile.TemporaryDirectory() as t:
            sfz = os.path.join(t, "sf", "ContentResources.zip")
            os.makedirs(os.path.dirname(sfz))
            with zipfile.ZipFile(sfz, "w") as f:
                f.writestr("Scripts/Source/Actor.psc", "ScriptName Actor\nFunction StartCombat(Actor a) native\n")
            fo4 = os.path.join(t, "FO4Data")
            for sub in ("Base", "DLC01"):
                os.makedirs(os.path.join(fo4, "Scripts", "Source", sub))
            with zipfile.ZipFile(os.path.join(fo4, "Scripts", "Source", "Base", "Base.zip"), "w") as f:
                f.writestr("Actor.psc", ACTOR)
            with zipfile.ZipFile(os.path.join(fo4, "Scripts", "Source", "DLC01", "DLC01.zip"), "w") as f:
                f.writestr("DLC01Script.psc", "ScriptName DLC01Script\n")
            out = os.path.join(t, "out", "p.json")
            self.assertEqual(ep.main(["--sf-zip", sfz, "--fo4-data", fo4, "--out", out]), 0)
            e = json.load(open(out))["fo4"][0]
            self.assertTrue(e["base_zip"]["exists"])
            self.assertEqual(e["source_zips"], {"Base/Base.zip": 1, "DLC01/DLC01.zip": 1})
            g = e["native_gap"]["actor"]
            self.assertEqual(g["fo4_only"], ["EvaluatePackage", "IsInPowerArmor", "OnDeath"])
            self.assertEqual((g["shared_count"], g["sf_only_count"]), (1, 0))


if __name__ == "__main__":
    unittest.main()
