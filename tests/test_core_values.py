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
    core_form_id,
    core_values_by_edid,
    load_core_values,
)


class CoreValuesSchemaTests(unittest.TestCase):
    def test_schema_invariants_and_pipboy_rads_id(self) -> None:
        plugin, next_id, records = load_core_values()
        self.assertEqual(plugin, CORE_VALUES_PLUGIN)
        self.assertEqual(next_id, 0x000861)
        by_edid = core_values_by_edid()
        # Pip-Boy native lookup scans local id 0x800 for FO4SF_Rads
        self.assertEqual(core_form_id("FO4SF_Rads"), 0x000800)
        self.assertEqual(by_edid["FO4SF_Rads"].record_type, "AVIF")
        # 7 SPECIAL + 13 Skills + Karma + Stimpak + TestModeEnabled = 0
        self.assertEqual(len(by_edid["FO4SF_SpecialAVList"].items), 7)
        self.assertEqual(len(by_edid["FO4SF_SkillAVList"].items), 13)
        self.assertEqual(core_form_id("FO4SF_Special_Perception"), 0x000811)
        self.assertEqual(core_form_id("FO4SF_Skill_Guns"), 0x000823)
        self.assertEqual(core_form_id("FO4SF_Karma"), 0x000830)
        self.assertEqual(core_form_id("FO4SF_HardcoreEnabled"), 0x000840)
        self.assertEqual(core_form_id("FO4SF_Stimpak"), 0x000851)
        self.assertEqual(core_form_id("FO4SF_TestModeEnabled"), 0x000860)
        self.assertEqual(by_edid["FO4SF_TestModeEnabled"].default, 0.0)
        self.assertEqual(len(records), 42)

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
