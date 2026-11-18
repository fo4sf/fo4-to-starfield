"""Unit tests for the single shared store (`FO4SFCoreValues.esm` / `core_values.json`)."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.core.core_values import (  # noqa: E402
    CORE_VALUES_PLUGIN,
    core_form_id,
    core_values_by_edid,
    load_core_values,
)
from fo4sf.core.cross_plugin_check import (  # noqa: E402
    NATIVE_CORE_VALUE_SPECS,
    build_writer_catalog,
    validate_native_core_value_refs,
)

# parity not applicable: ordered by A6 (FO4SF_PipboyAcquired moved into FO4SFCoreValues.esm at 0x000865)
PINNED_CORE_VALUES_PLAYER_SHA256 = "ec4bf5489a3822c9e438c07545b511495a699f91450b76a3c9a00d8641b1c41c"
# parity not applicable: ordered by A5 (test profile builds FO4SFCoreValues.esm with --test-mode 1)
PINNED_CORE_VALUES_TEST_SHA256 = "83918f6ac60a9d72d4362bd11f82bb2a2d0dfee64cfaec15adc66c3806e6eca7"


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class CoreValuesSchemaTests(unittest.TestCase):
    def test_schema_invariants_and_pipboy_shared_ids(self) -> None:
        # parity not applicable: ordered by A6
        plugin, next_id, records = load_core_values()
        self.assertEqual(plugin, CORE_VALUES_PLUGIN)
        self.assertEqual(next_id, 0x000866)
        by_edid = core_values_by_edid()
        # Pip-Boy native lookup reads local id 0x800 for FO4SF_Rads
        self.assertEqual(core_form_id("FO4SF_Rads"), 0x000800)
        self.assertEqual(by_edid["FO4SF_Rads"].record_type, "AVIF")
        self.assertEqual(len(by_edid["FO4SF_SpecialAVList"].items), 7)
        self.assertEqual(len(by_edid["FO4SF_SkillAVList"].items), 13)
        self.assertEqual(core_form_id("FO4SF_Special_Perception"), 0x000811)
        self.assertEqual(core_form_id("FO4SF_Skill_Guns"), 0x000823)
        self.assertEqual(core_form_id("FO4SF_Karma"), 0x000830)
        self.assertEqual(core_form_id("FO4SF_HardcoreEnabled"), 0x000840)
        self.assertEqual(core_form_id("FO4SF_HardcoreFastTravelBlocked"), 0x000841)
        self.assertEqual(core_form_id("FO4SF_Stimpak"), 0x000851)
        self.assertEqual(core_form_id("FO4SF_TestModeEnabled"), 0x000860)
        self.assertEqual(by_edid["FO4SF_TestModeEnabled"].default, 0.0)
        # A6: FO4SF_PipboyAcquired owned in FO4SFCoreValues.esm at 0x000865, default 0.0, constant=False
        self.assertEqual(core_form_id("FO4SF_PipboyAcquired"), 0x000865)
        self.assertEqual(by_edid["FO4SF_PipboyAcquired"].record_type, "GLOB")
        self.assertEqual(by_edid["FO4SF_PipboyAcquired"].default, 0.0)
        self.assertFalse(by_edid["FO4SF_PipboyAcquired"].constant)
        self.assertEqual(len(records), 43)

    def test_r13_native_core_value_lookups_match_schema_and_catch_wrong_or_split_ids(self) -> None:
        catalog, dup_errors = build_writer_catalog(ROOT)
        self.assertEqual(dup_errors, [], "\n".join(dup_errors))
        native_errors = validate_native_core_value_refs(ROOT, catalog)
        self.assertEqual(native_errors, [], "\n".join(native_errors))
        self.assertTrue(any(s.edid == "FO4SF_PipboyAcquired" and s.local_id == 0x000865 for s in NATIVE_CORE_VALUE_SPECS))

        main_rel = "sfse/FO4SFPipboyMenu/src/main.cpp"
        main_txt = (Path(ROOT) / main_rel).read_text(encoding="utf-8")

        # Wrong local ID in C++ must fail
        wrong_id_cpp = main_txt.replace("kCorePipboyAcquiredId = 0x865;", "kCorePipboyAcquiredId = 0x899;")
        errs_wrong = validate_native_core_value_refs(ROOT, catalog, cpp_overrides={main_rel: wrong_id_cpp})
        self.assertTrue(errs_wrong)
        self.assertIn("kCorePipboyAcquiredId", "\n".join(errs_wrong))

        # Split plugin lookup (pointing FO4SF_PipboyAcquired at FO4SFNewGame.esm instead of FO4SFCoreValues.esm) must fail
        split_cat = {k: dict(v) for k, v in catalog.items()}
        split_cat.setdefault("FO4SFNewGame.esm", {})[0x00080C] = ("GLOB", "FO4SF_PipboyAcquired")
        split_cpp = main_txt.replace(
            'KitFileForm("FO4SFCoreValues.esm", kCorePipboyAcquiredId, "TESGlobal@@", detail)',
            'KitFileForm("FO4SFNewGame.esm", 0x80C, "TESGlobal@@", detail)',
        )
        errs_split = validate_native_core_value_refs(ROOT, split_cat, cpp_overrides={main_rel: split_cpp})
        self.assertTrue(errs_split)
        self.assertIn("split native lookup", "\n".join(errs_split))

    def test_dotnet_core_values_selftest_and_pinned_store_hashes(self) -> None:
        if not shutil.which("dotnet"):
            self.skipTest("dotnet CLI is not on PATH; skipping Mutagen CoreValues build & hash pin check")
        proj = os.path.join(ROOT, "dotnet", "CoreValues", "CoreValues.csproj")
        dll = os.path.join(ROOT, "dotnet", "CoreValues", "bin", "Release", "net9.0", "CoreValues.dll")
        base_cmd = ["dotnet", dll] if os.path.isfile(dll) else ["dotnet", "run", "--project", proj, "--"]

        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run([*base_cmd, "selftest", tmp], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

            # parity not applicable: ordered by A6 (player profile store hash)
            player_esm = os.path.join(tmp, "default", CORE_VALUES_PLUGIN)
            self.assertEqual(_sha256_file(player_esm), PINNED_CORE_VALUES_PLAYER_SHA256)

            # parity not applicable: ordered by A5 (test profile store hash with --test-mode 1)
            sf_fix = os.path.join(tmp, "fixture", "Starfield.esm")
            test_out = os.path.join(tmp, "test_profile")
            proc_test = subprocess.run(
                [*base_cmd, "build", sf_fix, test_out, "--test-mode", "1"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_test.returncode, 0, proc_test.stderr or proc_test.stdout)
            self.assertEqual(_sha256_file(os.path.join(test_out, CORE_VALUES_PLUGIN)), PINNED_CORE_VALUES_TEST_SHA256)


if __name__ == "__main__":
    unittest.main()
