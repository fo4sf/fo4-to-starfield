"""Compile and read synthetic FO4 quest/VMAD records through the actual census."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOTNET = shutil.which("dotnet")
if not DOTNET and Path(r"C:\Program Files\dotnet\dotnet.exe").exists():
    DOTNET = r"C:\Program Files\dotnet\dotnet.exe"


@unittest.skipUnless(DOTNET, ".NET SDK required")
class QuestCensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(os.environ.get("FO4SF_CENSUS_EVIDENCE", cls.temp.name))
        cls.root.mkdir(parents=True, exist_ok=True)
        for project in ("QuestCensus", "QuestCensusFixture"):
            run = subprocess.run([DOTNET, "build", str(ROOT / "dotnet" / project), "-c", "Release", "--nologo"], capture_output=True, text=True)
            if run.returncode:
                raise AssertionError(run.stdout + run.stderr)
        cls.executable = ROOT / "dotnet/QuestCensus/bin/Release/net9.0/QuestCensus.dll"
        fixture = ROOT / "dotnet/QuestCensusFixture/bin/Release/net9.0/QuestCensusFixture.dll"
        cls.source = cls.root / "Synthetic.esm"
        run = subprocess.run([DOTNET, str(fixture), str(cls.source)], capture_output=True, text=True)
        if run.returncode:
            raise AssertionError(run.stdout + run.stderr)
        cls.before = hashlib.sha256(cls.source.read_bytes()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def census(self, selection, code=0):
        folder = self.root / self._testMethodName
        folder.mkdir()
        selector = folder / "selection.json"
        selector.write_text(json.dumps(selection), encoding="utf-8")
        report = folder / "report.json"
        run = subprocess.run([DOTNET, str(type(self).executable), str(self.source), str(selector), str(report)], capture_output=True, text=True)
        (folder / "run.log").write_text(run.stdout + run.stderr, encoding="utf-8")
        self.assertEqual(run.returncode, code, run.stdout + run.stderr)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.before)
        return json.loads(report.read_bytes()), selector, report

    def test_explicit_cell_and_scripts(self):
        data, _, _ = self.census({"cell_editor_ids": ["SelectedRoom"]})
        quest = next(q for q in data["quests"] if q["editor_id"] == "DirectQuest")
        self.assertEqual(quest["alias_count"], 2)
        self.assertEqual(quest["aliases_without_forced_reference"], 1)
        self.assertEqual({m["target"] for m in quest["matches"]}, {"000800:Synthetic.esm", "000801:Synthetic.esm", "000802:Synthetic.esm", "000803:Synthetic.esm"})
        scripts = {s["name"]: s for s in data["scripts"]}
        self.assertTrue(scripts["SyntheticAliasScript"]["matches"])
        self.assertTrue(scripts["SyntheticFragmentScript"]["matches"])
        self.assertTrue(scripts["PlacedScript"]["matches"])
        self.assertEqual(scripts["PlacedScript"]["owner_selection"]["relation"], "reference_in_explicit_cell")
        self.assertTrue(scripts["PackageFragmentProperties"]["matches"])
        self.assertIn("PackageChange", scripts)
        self.assertEqual(data["counts"]["non_quest_fragment_groups"], 1)
        self.assertEqual(scripts["StringOnly"]["matches"], [])
        self.assertTrue(next(q for q in data["quests"] if q["source"] == "000812:Synthetic.esm")["deleted"])
        self.assertIn("000803:Synthetic.esm", {m["target"] for m in scripts["SyntheticQuestScript"]["matches"]})
        self.assertIn("SyntheticStage", scripts)
        self.assertFalse(data["runtime_dependencies_resolved"])

    def test_partial_cell_does_not_claim_neighbor_converted(self):
        data, _, _ = self.census({"references": ["000801:Synthetic.esm"]})
        q = next(q for q in data["quests"] if q["editor_id"] == "DirectQuest")
        relations = {m["target"]: m["relation"] for m in q["matches"]}
        self.assertEqual(relations["000802:Synthetic.esm"], "unselected_reference_in_partial_cell")
        self.assertEqual(relations["000801:Synthetic.esm"], "selected_reference")

    def test_foreign_plugin_same_local_id_is_unresolved(self):
        data, _, _ = self.census({"references": ["000801:Other.esm"]}, 2)
        self.assertFalse(data["selection_complete"])
        self.assertEqual(data["scope"]["selected_reference_count"], 0)
        self.assertTrue(all(not q["matches"] for q in data["quests"]))

    def test_missing_named_cell_is_unresolved(self):
        data, _, _ = self.census({"cell_editor_ids": ["Missing"]}, 2)
        self.assertFalse(data["selection_complete"])

    def test_reference_map_is_pinned_and_selects_refs(self):
        path = self.root / "core-map.json"
        path.write_text(json.dumps({"refs": {"000801:Synthetic.esm": "123456"}, "containers": {"000802:Synthetic.esm": "654321"}}))
        data, _, _ = self.census({"reference_map": str(path)})
        self.assertEqual(data["scope"]["selected_reference_count"], 2)
        self.assertEqual(len(data["input_pins"]), 3)
        self.assertIn(hashlib.sha256(path.read_bytes()).hexdigest(), {p["sha256"] for p in data["input_pins"]})

    def test_existing_report_never_overwritten(self):
        _, selector, report = self.census({"cells": ["000800:Synthetic.esm"]})
        before = report.read_bytes()
        run = subprocess.run([DOTNET, str(type(self).executable), str(self.source), str(selector), str(report)], capture_output=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(report.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
