"""Unit tests for the single shared store (`FO4SFCoreValues.esm` / `core_values.json`)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.core.core_values import (  # noqa: E402
    CORE_VALUES_PLUGIN,
    START_MODE_GLOB_EDIDS,
    core_form_id,
    core_values_by_edid,
    load_core_values,
)
from fo4sf.core.cross_plugin_check import build_writer_catalog  # noqa: E402


class CoreValuesSchemaTests(unittest.TestCase):
    def test_schema_invariants_and_pipboy_rads_id(self) -> None:
        plugin, next_id, records = load_core_values()
        self.assertEqual(plugin, CORE_VALUES_PLUGIN)
        self.assertEqual(next_id, 0x000877)
        by_edid = core_values_by_edid()
        # Pip-Boy native lookup scans local id 0x800 for FO4SF_Rads
        self.assertEqual(core_form_id("FO4SF_Rads"), 0x000800)
        self.assertEqual(by_edid["FO4SF_Rads"].record_type, "AVIF")
        # 7 SPECIAL + 13 Skills + Karma + Stimpak + TestModeEnabled + S1 mode/start GLOBs
        self.assertEqual(len(by_edid["FO4SF_SpecialAVList"].items), 7)
        self.assertEqual(len(by_edid["FO4SF_SkillAVList"].items), 13)
        self.assertEqual(core_form_id("FO4SF_Special_Perception"), 0x000811)
        self.assertEqual(core_form_id("FO4SF_Skill_Guns"), 0x000823)
        self.assertEqual(core_form_id("FO4SF_Karma"), 0x000830)
        self.assertEqual(core_form_id("FO4SF_HardcoreEnabled"), 0x000840)
        self.assertEqual(core_form_id("FO4SF_Stimpak"), 0x000851)
        self.assertEqual(core_form_id("FO4SF_TestModeEnabled"), 0x000860)
        self.assertEqual(by_edid["FO4SF_TestModeEnabled"].default, 0.0)
        # S1: start & mode GLOBs 0x870..0x876
        expected_s1 = {
            "FO4SF_GameMode": (0x000870, 0.0),
            "FO4SF_SurvivalStart": (0x000871, 0.0),
            "FO4SF_SurvivalLocked": (0x000872, 0.0),
            "FO4SF_StartDifficulty": (0x000873, 0.0),
            "FO4SF_WarfareFaction": (0x000874, -1.0),
            "FO4SF_WarfareStartIndex": (0x000875, -1.0),
            "FO4SF_StartChoiceDone": (0x000876, 0.0),
        }
        self.assertEqual(tuple(expected_s1.keys()), START_MODE_GLOB_EDIDS)
        for edid, (want_id, want_def) in expected_s1.items():
            self.assertEqual(core_form_id(edid), want_id)
            rec = by_edid[edid]
            self.assertEqual(rec.record_type, "GLOB")
            self.assertEqual(rec.default, want_def)
            self.assertNotIn("Constant", rec.flags)
        self.assertEqual(len(records), 49)

    def test_start_mode_globals_owned_exclusively_by_core_values(self) -> None:
        catalog, problems = build_writer_catalog(ROOT)
        self.assertEqual(problems, [])

        def find_duplicate_owners(cat: dict[str, dict[int, tuple[str, str]]]) -> dict[str, list[str]]:
            owners: dict[str, set[str]] = {edid: set() for edid in START_MODE_GLOB_EDIDS}
            for plugin, recs in cat.items():
                for _, (_, edid) in recs.items():
                    for target in START_MODE_GLOB_EDIDS:
                        if edid.lower() == target.lower():
                            owners[target].add(plugin)
            return {edid: sorted(plugs) for edid, plugs in owners.items() if plugs != {CORE_VALUES_PLUGIN}}

        self.assertEqual(find_duplicate_owners(catalog), {})

        # Negative test: fails if any start/mode EditorID appears in a second plugin
        tampered = {k: dict(v) for k, v in catalog.items()}
        tampered.setdefault("FO4SFNewGame.esm", {})[0x000899] = ("GLOB", "FO4SF_GameMode")
        dups = find_duplicate_owners(tampered)
        self.assertIn("FO4SF_GameMode", dups)
        self.assertEqual(dups["FO4SF_GameMode"], ["FO4SFCoreValues.esm", "FO4SFNewGame.esm"])

    @unittest.skipUnless(
        os.environ.get("FO4SF_DOTNET_TESTS") == "1" and shutil.which("dotnet"),
        "set FO4SF_DOTNET_TESTS=1 with dotnet on PATH to run Mutagen selftest",
    )
    def test_dotnet_core_values_selftest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [
                    "dotnet",
                    "run",
                    "--project",
                    os.path.join(ROOT, "dotnet", "CoreValues", "CoreValues.csproj"),
                    "--",
                    "selftest",
                    tmp,
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main()
