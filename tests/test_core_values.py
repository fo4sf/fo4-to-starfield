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
    H00_SUSPECT_GLOB_EDIDS,
    START_MODE_GLOB_EDIDS,
    core_form_id,
    core_values_by_edid,
    load_core_values,
)
from fo4sf.core.cross_plugin_check import (  # noqa: E402
    NATIVE_CORE_VALUE_SPECS,
    build_writer_catalog,
    validate_native_core_value_refs,
)

# parity not applicable: ordered by S1, A6, A12, B8, H00, and N2 (0x000865..0x000866 + start/mode GLOBs 0x000870..0x000879 + SpecialMenuPending 0x000880..0x000887 + H00 suspect GLOBs 0x000890..0x000897)
PINNED_CORE_VALUES_PLAYER_SHA256 = "d8712abb0d7d029490b2af89f5bf84a24e5d77f841fe6a473f6c2ae0cd7db2cf"
# parity not applicable: ordered by S1, A5, A6, A12, B8, H00, and N2 (test profile builds FO4SFCoreValues.esm with --test-mode 1)
PINNED_CORE_VALUES_TEST_SHA256 = "fefea45074233d146e3c0edfbf8e80640214defae5df99a53b73f4692595c9cd"


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class CoreValuesSchemaTests(unittest.TestCase):
    def test_schema_invariants_and_pipboy_shared_ids(self) -> None:
        # parity not applicable: ordered by S1, A6, A12, B8, and H00 (0x000870..0x000877 beginning-real start/mode GLOBs + 0x000880..0x000887 SpecialMenu + 0x000890..0x000897 H00 surface suspects)
        plugin, next_id, records = load_core_values()
        self.assertEqual(plugin, CORE_VALUES_PLUGIN)
        self.assertEqual(next_id, 0x000898)
        by_edid = core_values_by_edid()
        # Pip-Boy native lookup reads local id 0x800 for FO4SF_Rads
        self.assertEqual(core_form_id("FO4SF_Rads"), 0x000800)
        self.assertEqual(by_edid["FO4SF_Rads"].record_type, "AVIF")
        # 7 SPECIAL + 13 Skills + Karma + Stimpak + TestModeEnabled + PipboyAcquired + S1 mode/start GLOBs
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
        # N2 (R13): FO4SF_StartCardOpen owned in FO4SFCoreValues.esm at 0x000866, default 0.0, constant=False
        self.assertEqual(core_form_id("FO4SF_StartCardOpen"), 0x000866)
        self.assertEqual(by_edid["FO4SF_StartCardOpen"].record_type, "GLOB")
        self.assertEqual(by_edid["FO4SF_StartCardOpen"].default, 0.0)
        self.assertFalse(by_edid["FO4SF_StartCardOpen"].constant)
        # S1 + B8 + N2: start & mode GLOBs 0x870..0x879
        expected_s1 = {
            "FO4SF_GameMode": (0x000870, 0.0),
            "FO4SF_SurvivalStart": (0x000871, 0.0),
            "FO4SF_SurvivalLocked": (0x000872, 0.0),
            "FO4SF_StartDifficulty": (0x000873, 0.0),
            "FO4SF_WarfareFaction": (0x000874, -1.0),
            "FO4SF_WarfareStartIndex": (0x000875, -1.0),
            "FO4SF_StartChoiceDone": (0x000876, 0.0),
            "FO4SF_StartNeutralSpot": (0x000877, 0.0),
            "FO4SF_StoryLine": (0x000878, 0.0),
            "FO4SF_StartPlaceRow": (0x000879, 0.0),
        }
        self.assertEqual(tuple(expected_s1.keys()), START_MODE_GLOB_EDIDS)
        for edid, (want_id, want_def) in expected_s1.items():
            self.assertEqual(core_form_id(edid), want_id)
            rec = by_edid[edid]
            self.assertEqual(rec.record_type, "GLOB")
            self.assertEqual(rec.default, want_def)
            self.assertNotIn("Constant", rec.flags)
            self.assertFalse(rec.constant)
        # A12: 7 pending S.P.E.C.I.A.L. GLOBs (0x000880..0x000886) + commit flag (0x000887)
        for off, ltr in enumerate(("S", "P", "E", "C", "I", "A", "L")):
            ed = f"FO4SF_SpecialMenuPending{ltr}"
            self.assertEqual(core_form_id(ed), 0x000880 + off)
            self.assertEqual(by_edid[ed].record_type, "GLOB")
            self.assertEqual(by_edid[ed].default, 5.0)
            self.assertFalse(by_edid[ed].constant)
        self.assertEqual(core_form_id("FO4SF_SpecialMenuCommitRequested"), 0x000887)
        self.assertEqual(by_edid["FO4SF_SpecialMenuCommitRequested"].record_type, "GLOB")
        self.assertEqual(by_edid["FO4SF_SpecialMenuCommitRequested"].default, 0.0)
        self.assertFalse(by_edid["FO4SF_SpecialMenuCommitRequested"].constant)
        # H00: 8 per-suspect store globals (0x000890..0x000897, default 0.0, mutable for console setting in Vault 111)
        self.assertEqual(len(H00_SUSPECT_GLOB_EDIDS), 8)
        for off, ed in enumerate(H00_SUSPECT_GLOB_EDIDS):
            self.assertEqual(core_form_id(ed), 0x000890 + off)
            self.assertEqual(by_edid[ed].record_type, "GLOB")
            self.assertEqual(by_edid[ed].default, 0.0)
            self.assertFalse(by_edid[ed].constant)
        self.assertEqual(len(records), 70)

    def test_start_mode_globals_owned_exclusively_by_core_values(self) -> None:
        catalog, problems = build_writer_catalog(ROOT)
        self.assertEqual(problems, [])

        tracked = START_MODE_GLOB_EDIDS + H00_SUSPECT_GLOB_EDIDS

        def find_duplicate_owners(cat: dict[str, dict[int, tuple[str, str]]]) -> dict[str, list[str]]:
            owners: dict[str, set[str]] = {edid: set() for edid in tracked}
            for plugin, recs in cat.items():
                for _, (_, edid) in recs.items():
                    for target in tracked:
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

    def test_r13_native_core_value_lookups_match_schema_and_catch_wrong_or_split_ids(self) -> None:
        catalog, dup_errors = build_writer_catalog(ROOT)
        self.assertEqual(dup_errors, [], "\n".join(dup_errors))
        native_errors = validate_native_core_value_refs(ROOT, catalog)
        self.assertEqual(native_errors, [], "\n".join(native_errors))
        self.assertTrue(any(s.edid == "FO4SF_PipboyAcquired" and s.local_id == 0x000865 for s in NATIVE_CORE_VALUE_SPECS))
        self.assertTrue(any(s.edid == "FO4SF_StartCardOpen" and s.local_id == 0x000866 for s in NATIVE_CORE_VALUE_SPECS))

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
