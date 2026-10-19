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


if __name__ == "__main__":
    unittest.main()
