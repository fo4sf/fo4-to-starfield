"""Parity tests for Variant (b) setup screen, schema_version=2 launch_choices, and canonical indexing."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = str(REPO / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from fo4sf.core import start_places as sp  # noqa: E402


def _make_sparse_places_doc() -> dict:
    """Synthetic start_places.json with an unavailable Warfare row between two available Warfare rows."""
    return {
        "schema_version": 1,
        "places": [
            {
                "id": "fo4_vault111",
                "mode": "story",
                "start_variant": "quick",
                "story_id": "fo4_commonwealth",
                "story_label": "Fallout 4: Commonwealth",
                "faction_slot": -1,
                "faction_label": "",
                "name": "Vault 111 (Commonwealth)",
                "space": "FO4Port_Vault111Cryo",
                "is_interior": True,
                "plugin": "FO4Port.esm",
                "marker_source": "vault_anchor",
                "quests": ["FO4SF_NewGame"],
                "quest_mask": 1,
                "warfare_key": "",
                "min_difficulty": 0,
                "max_difficulty": 3,
                "available": True,
                "unavailable_reason": "",
            },
            {
                "id": "minutemen_sanctuary",
                "mode": "warfare",
                "start_variant": "",
                "story_id": "none",
                "story_label": "",
                "faction_slot": 0,
                "faction_label": "Minutemen",
                "name": "Sanctuary Hills",
                "space": "FO4Core_Commonwealth",
                "is_interior": False,
                "plugin": "FO4TerrainCore.esm",
                "marker_edid": "FO4Core_CommonwealthMapMarkerSanctuary",
                "quests": [],
                "quest_mask": 0,
                "warfare_key": "minutemen_sanctuary",
                "min_difficulty": 0,
                "max_difficulty": 3,
                "available": True,
                "unavailable_reason": "",
            },
            {
                "id": "brotherhood_airport",
                "mode": "warfare",
                "start_variant": "",
                "story_id": "none",
                "story_label": "",
                "faction_slot": 1,
                "faction_label": "Brotherhood of Steel",
                "name": "Boston Airport",
                "space": "FO4Core_Commonwealth",
                "is_interior": False,
                "plugin": "FO4TerrainCore.esm",
                "marker_edid": "FO4Core_CommonwealthMapMarkerBostonAirport",
                "quests": [],
                "quest_mask": 0,
                "warfare_key": "brotherhood_airport",
                "min_difficulty": 0,
                "max_difficulty": 3,
                "available": False,
                "unavailable_reason": "Brotherhood Airport kit not wired yet",
            },
            {
                "id": "settlers_diamondcity",
                "mode": "warfare",
                "start_variant": "",
                "story_id": "none",
                "story_label": "",
                "faction_slot": 4,
                "faction_label": "Commonwealth Settlers",
                "name": "Diamond City Market",
                "space": "FO4Core_Commonwealth",
                "is_interior": False,
                "plugin": "FO4TerrainCore.esm",
                "marker_edid": "FO4Core_CommonwealthMapMarkerDiamondCity",
                "quests": [],
                "quest_mask": 0,
                "warfare_key": "settlers_diamondcity",
                "min_difficulty": 0,
                "max_difficulty": 3,
                "available": True,
                "unavailable_reason": "",
            },
        ],
    }


def _make_warfare_starts_doc(keys: list[str]) -> dict:
    return {
        "schema_version": 1,
        "starts": [
            {
                "key": k,
                "faction_slot": idx,
                "faction_name": f"Faction {idx}",
                "name": f"Start {idx}",
                "marker_edid": f"FO4Core_Marker_{idx}",
                "min_difficulty": 0,
                "max_difficulty": 3,
                "fame": 0.0,
                "karma": 0.0,
                "squad_cap": 4,
                "gear": [{"plugin": "Starfield.esm", "id": "0x01D1D7", "count": 1, "equip": True}],
            }
            for idx, k in enumerate(keys)
        ],
    }


def _compile_and_run_cpp(root: Path, cpp_name: str, src_text: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    cxx = shutil.which("cl") or shutil.which("g++") or shutil.which("clang++")
    if not cxx:
        raise unittest.SkipTest("no host C++ compiler (cl/g++/clang++) on PATH for native setup_places.h check")
    harness = root / cpp_name
    exe = root / (Path(cpp_name).stem + (".exe" if sys.platform == "win32" else ""))
    harness.write_text(src_text, encoding="utf-8")
    if Path(cxx).stem.lower() == "cl":
        obj = root / (Path(cpp_name).stem + ".obj")
        cmd = [cxx, "/nologo", "/std:c++20", "/EHsc", str(harness), f"/Fe:{exe}", f"/Fo:{obj}"]
    else:
        cmd = [cxx, "-std=c++20", str(harness), "-o", str(exe)]
    comp = subprocess.run(cmd, capture_output=True, text=True)
    if comp.returncode != 0:
        raise AssertionError(f"C++ compile failed:\n{comp.stdout}\n{comp.stderr}")
    run = subprocess.run([str(exe), *args], capture_output=True, text=True)
    if run.returncode != 0:
        raise AssertionError(f"C++ run failed (rc={run.returncode}):\n{run.stdout}\n{run.stderr}")
    return run


class SetupScreenWarfareIndexParityTests(unittest.TestCase):
    def test_warfare_start_idx_uses_warfare_starts_json_row_index_across_unavailable_gaps(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            places_p = root / "start_places.json"
            wf_p = root / "warfare_starts.json"
            places_p.write_text(json.dumps(_make_sparse_places_doc()), encoding="utf-8")
            # Canonical order puts brotherhood_airport at 1 and settlers_diamondcity at 2
            wf_p.write_text(
                json.dumps(_make_warfare_starts_doc(["minutemen_sanctuary", "brotherhood_airport", "settlers_diamondcity"])),
                encoding="utf-8",
            )

            rows = sp.load_start_places(str(places_p))
            for show_unavail in (False, True):
                model = sp.SetupScreenModel(
                    rows,
                    show_unavailable=show_unavail,
                    warfare_starts_path=str(wf_p),
                )
                model.adjust_row(0, 1)  # Story -> Warfare
                p0 = model.confirm()
                self.assertIsNotNone(p0)
                assert p0 is not None
                self.assertEqual(p0.place_id, "minutemen_sanctuary")
                self.assertEqual(p0.warfare_start_idx, 0)

                model.adjust_row(1, 1)
                if show_unavail:
                    self.assertIsNone(model.confirm())
                    model.adjust_row(1, 1)
                p2 = model.confirm()
                self.assertIsNotNone(p2)
                assert p2 is not None
                self.assertEqual(p2.place_id, "settlers_diamondcity")
                self.assertEqual(p2.warfare_start_idx, 2)
                self.assertEqual(p2.start_place_row, 2)

    def test_warfare_starts_json_order_overrides_start_places_order_and_supports_sibling_filename(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            places_p = root / "FO4SFStartPlaces.json"
            wf_sibling = root / "FO4SFWarfareStarts.json"
            places_p.write_text(json.dumps(_make_sparse_places_doc()), encoding="utf-8")
            wf_sibling.write_text(
                json.dumps(_make_warfare_starts_doc(["settlers_diamondcity", "brotherhood_airport", "minutemen_sanctuary"])),
                encoding="utf-8",
            )

            rows = sp.load_start_places(str(places_p))
            model = sp.SetupScreenModel(rows, warfare_starts_path=str(root / "warfare_starts.json"))
            model.adjust_row(0, 1)
            p_mm = model.confirm()
            self.assertIsNotNone(p_mm)
            assert p_mm is not None
            self.assertEqual(p_mm.warfare_start_idx, 2)

            model.adjust_row(1, 1)
            p_dc = model.confirm()
            self.assertIsNotNone(p_dc)
            assert p_dc is not None
            self.assertEqual(p_dc.warfare_start_idx, 0)

    def test_fallback_without_warfare_starts_file_still_uses_canonical_all_rows_order(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            places_p = root / "start_places.json"
            places_p.write_text(json.dumps(_make_sparse_places_doc()), encoding="utf-8")
            rows = sp.load_start_places(str(places_p))
            model = sp.SetupScreenModel(
                rows,
                show_unavailable=False,
                warfare_starts_path=str(root / "missing_warfare_starts.json"),
            )
            model.adjust_row(0, 1)
            model.adjust_row(1, 1)
            payload = model.confirm()
            self.assertIsNotNone(payload)
            assert payload is not None
            self.assertEqual(payload.place_id, "settlers_diamondcity")
            self.assertEqual(payload.warfare_start_idx, 2)

    def test_cpp_setup_places_header_has_exact_warfare_starts_and_r14_validation_contract(self):
        hdr = (REPO / "sfse" / "FO4SFPipboyMenu" / "src" / "setup_places.h").read_text(encoding="utf-8")
        for sym in (
            "ParseWarfareStartKeysJsonText",
            "LoadWarfareStartKeysFile",
            "LoadSiblingWarfareStartKeys",
            "ApplyWarfareStartIndices",
            "ResolveWarfareStartIdx",
            "FO4SFWarfareStarts.json",
            "warfare_starts.json",
            "_warfareKeys",
            "warfareStartIndex",
            "startVariant",
            "requiredPlugins",
            "ValidateLaunchChoicesAgainstStartTable",
            "ParseAndCheckFreshLaunchChoicesFile",
            "a_out.schemaVersion != 2",
        ):
            self.assertIn(sym, hdr, f"setup_places.h missing expected symbol {sym}")
        self.assertNotIn('a_out.placeId != "fo4_vault111"', hdr)
        confirm_body = hdr[hdr.index("std::optional<SetupCommitPayload> Confirm() const"):hdr.index("private:")]
        self.assertIn("ResolveWarfareStartIdx(cur)", confirm_body)
        self.assertNotIn("for (const auto& r : _availRows) {\n\t\t\t\tif (r.mode == \"warfare\")", confirm_body)

        cpp_main = (REPO / "sfse" / "FO4SFPipboyMenu" / "src" / "main.cpp").read_text(encoding="utf-8")
        self.assertIn("CollectLoadedPluginNames()", cpp_main)
        self.assertIn("ValidateLaunchChoicesAgainstStartTable", cpp_main)

    def test_cpp_and_python_live_parity_when_host_cpp_compiler_present(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            places_p = root / "FO4SFStartPlaces.json"
            wf_p = root / "FO4SFWarfareStarts.json"
            places_p.write_text(json.dumps(_make_sparse_places_doc()), encoding="utf-8")
            wf_p.write_text(
                json.dumps(_make_warfare_starts_doc(["minutemen_sanctuary", "brotherhood_airport", "settlers_diamondcity"])),
                encoding="utf-8",
            )
            src = f"""#include <cassert>
#include <iostream>
#include "{(REPO / "sfse" / "FO4SFPipboyMenu" / "src" / "setup_places.h").as_posix()}"
int main(int argc, char** argv) {{
    bool fromFile = false;
    auto rows = fo4sf::setup::LoadStartPlacesFileOrFallback(argv[1], fromFile);
    assert(fromFile);
    fo4sf::setup::SetupScreenModel model;
    model.Reset(rows, false);
    model.AdjustRow(0, 1); // Warfare
    auto p0 = model.Confirm();
    assert(p0.has_value() && p0->placeId == "minutemen_sanctuary" && p0->warfareStartIdx == 0);
    model.AdjustRow(1, 1); // settlers_diamondcity
    auto p2 = model.Confirm();
    assert(p2.has_value() && p2->placeId == "settlers_diamondcity" && p2->warfareStartIdx == 2);
    // Explicit warfareKeys override test (reversed order)
    model.Reset(rows, false, {{"settlers_diamondcity", "brotherhood_airport", "minutemen_sanctuary"}});
    model.AdjustRow(0, 1);
    auto pr0 = model.Confirm();
    assert(pr0.has_value() && pr0->warfareStartIdx == 2);
    model.AdjustRow(1, 1);
    auto pr1 = model.Confirm();
    assert(pr1.has_value() && pr1->warfareStartIdx == 0);
    std::cout << "cpp_parity_ok\\n";
    return 0;
}}
"""
            run = _compile_and_run_cpp(root, "parity.cpp", src, [str(places_p)])
            self.assertIn("cpp_parity_ok", run.stdout)

    def test_cpp_launch_choices_v2_start_variant_and_prewar_plugin_gating(self):
        now_epoch = int(time.time())
        real_table_path = REPO / "src" / "fo4sf" / "core" / "start_places.json"
        raw_table = json.loads(real_table_path.read_text(encoding="utf-8"))
        disabled_table = json.loads(json.dumps(raw_table))
        disabled_table["places"][0]["available"] = False
        disabled_table["places"][0]["unavailable_reason"] = "Pre-War disabled in test copy"

        prewar_choice = {
            "schema_version": 2,
            "mode": "story",
            "game_mode": 1,
            "start_variant": "normal",
            "survival": False,
            "survival_start": 0,
            "survival_locked": 0,
            "story_id": "fo4_commonwealth",
            "story_choice_idx": 0,
            "warfare_faction_slot": -1,
            "warfare_start_idx": -1,
            "place_id": "fo4_prewar_sanctuary",
            "start_place_row": 0,
            "min_difficulty": 0,
            "created_at": now_epoch,
            "nonce": "r14_prewar_ok",
        }
        v1_choice = dict(prewar_choice, schema_version=1)
        vault_choice = dict(
            prewar_choice,
            start_variant="quick",
            place_id="fo4_vault111",
            start_place_row=1,
            nonce="r14_vault_ok",
        )
        fo3_birth_choice = dict(
            prewar_choice,
            story_id="fo3_capital_wasteland",
            story_choice_idx=1,
            place_id="fo3_vault101_birth",
            nonce="r14_fo3_no",
        )
        fnv_door_choice = dict(
            prewar_choice,
            start_variant="quick",
            story_id="fnv_mojave",
            story_choice_idx=2,
            place_id="fnv_goodsprings_door",
            nonce="r14_fnv_no",
        )
        warfare_bad_var = {
            "schema_version": 2,
            "mode": "warfare",
            "game_mode": 2,
            "start_variant": "normal",
            "survival": False,
            "survival_start": 0,
            "survival_locked": 0,
            "story_id": "none",
            "story_choice_idx": -1,
            "warfare_faction_slot": 7,
            "warfare_start_idx": 2,
            "place_id": "raiders_corvega",
            "start_place_row": 4,
            "min_difficulty": 2,
            "created_at": now_epoch,
            "nonce": "r14_wf_bad",
        }
        prewar_wrong_var = dict(prewar_choice, start_variant="quick", nonce="r14_bad_var")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            disabled_table_p = root / "start_places_disabled.json"
            disabled_table_p.write_text(json.dumps(disabled_table), encoding="utf-8")

            p_prewar = root / "lc_prewar.json"
            p_v1 = root / "lc_v1.json"
            p_vault = root / "lc_vault.json"
            p_fo3 = root / "lc_fo3.json"
            p_fnv = root / "lc_fnv.json"
            p_wf_bad = root / "lc_wf_bad.json"
            p_var_bad = root / "lc_var_bad.json"

            p_prewar.write_text(json.dumps(prewar_choice), encoding="utf-8")
            p_v1.write_text(json.dumps(v1_choice), encoding="utf-8")
            p_vault.write_text(json.dumps(vault_choice), encoding="utf-8")
            p_fo3.write_text(json.dumps(fo3_birth_choice), encoding="utf-8")
            p_fnv.write_text(json.dumps(fnv_door_choice), encoding="utf-8")
            p_wf_bad.write_text(json.dumps(warfare_bad_var), encoding="utf-8")
            p_var_bad.write_text(json.dumps(prewar_wrong_var), encoding="utf-8")

            hdr = (REPO / "sfse" / "FO4SFPipboyMenu" / "src" / "setup_places.h").as_posix()
            src = f"""#include <cassert>
#include <iostream>
#include <string>
#include <vector>
#include "{hdr}"

int main(int argc, char** argv) {{
    using namespace fo4sf::setup;
    const std::int64_t nowEpoch = {now_epoch};
    assert(argc == 10);

    // 1. BuiltinFallbackStartPlaces defaults
    const auto fb = BuiltinFallbackStartPlaces();
    assert(!fb.empty());
    assert(fb[0].id == "fo4_vault111");
    assert(fb[0].startVariant == "quick");
    assert(fb[0].plugin == "FO4Port.esm");
    assert(fb[0].requiredPlugins.size() == 3);

    // 2. Real start_places.json parsing captures start_variant, plugin, required_plugins
    bool fromFile = false;
    const auto rows = LoadStartPlacesFileOrFallback(argv[1], fromFile);
    assert(fromFile && rows.size() == 20);
    assert(rows[0].id == "fo4_prewar_sanctuary");
    assert(rows[0].startVariant == "normal");
    assert(rows[0].plugin == "FO4SFPrewar.esm");
    assert(rows[0].requiredPlugins.size() == 4);
    assert(rows[0].requiredPlugins[0] == "FO4SFPrewar_Sanctuary.esm");
    assert(rows[1].id == "fo4_vault111");
    assert(rows[1].startVariant == "quick");

    bool disFromFile = false;
    const auto disabledRows = LoadStartPlacesFileOrFallback(argv[2], disFromFile);
    assert(disFromFile && !disabledRows[0].available);

    const std::vector<std::string> withPrewarPlugins{{
        "Starfield.esm",
        "fo4port.esm",
        "fo4sfprewar_sanctuary.esm",  // case-insensitive match
        "FO4SFPrewar.esm",
        "FO4SFNewGame.esm",
        "FO4SFCoreValues.esm",
    }};
    const std::vector<std::string> missingPrewarPlugin{{
        "Starfield.esm",
        "FO4Port.esm",
        "FO4SFPrewar_Sanctuary.esm",
        "FO4SFNewGame.esm",
        "FO4SFCoreValues.esm",
    }};
    const std::vector<std::string> missingSanctuaryPlugin{{
        "Starfield.esm",
        "FO4Port.esm",
        "FO4SFPrewar.esm",
        "FO4SFNewGame.esm",
        "FO4SFCoreValues.esm",
    }};
    const std::vector<std::string> allPortPlugins{{
        "Starfield.esm",
        "FO4Port.esm",
        "FO3Port.esm",
        "FNVPort.esm",
        "FO4SFNewGame.esm",
        "FO4SFCoreValues.esm",
    }};

    // 3. ACCEPTED: fo4_prewar_sanctuary when available=true and FO4SFPrewar_Sanctuary.esm + FO4SFPrewar.esm loaded
    LaunchChoicesPayload out;
    std::string reason;
    assert(LoadLaunchChoicesFile(argv[3], rows, withPrewarPlugins, out, nowEpoch, 21600, true, &reason));
    assert(out.valid && out.schemaVersion == 2 && out.placeId == "fo4_prewar_sanctuary");
    assert(out.startVariant == "normal" && reason.empty());

    // Explicit rows overload (without plugin check) accepts fo4_prewar_sanctuary too
    LaunchChoicesPayload outRowsOnly;
    assert(LoadLaunchChoicesFile(argv[3], rows, outRowsOnly, nowEpoch));
    assert(outRowsOnly.placeId == "fo4_prewar_sanctuary");

    // 4. REFUSED: fo4_prewar_sanctuary when FO4SFPrewar.esm or FO4SFPrewar_Sanctuary.esm absent
    assert(!LoadLaunchChoicesFile(argv[3], rows, missingPrewarPlugin, out, nowEpoch, 21600, true, &reason));
    assert(!out.valid && reason == "missing_plugin:FO4SFPrewar.esm");
    assert(!LoadLaunchChoicesFile(argv[3], rows, missingSanctuaryPlugin, out, nowEpoch, 21600, true, &reason));
    assert(!out.valid && reason == "missing_plugin:FO4SFPrewar_Sanctuary.esm");

    // 5. REFUSED: fo4_prewar_sanctuary when disabled (available=false) even with all plugins loaded
    assert(!LoadLaunchChoicesFile(argv[3], disabledRows, withPrewarPlugins, out, nowEpoch, 21600, true, &reason));
    assert(!out.valid && reason == "row_unavailable");

    // 6. REFUSED: schema_version=1, mismatched start_variant, unbuilt FO3/FNV rows, warfare with story variant
    assert(!LoadLaunchChoicesFile(argv[4], rows, withPrewarPlugins, out, nowEpoch, 21600, true, &reason));
    assert(reason == "invalid_json_or_schema");
    assert(!LoadLaunchChoicesFile(argv[9], rows, withPrewarPlugins, out, nowEpoch, 21600, true, &reason));
    assert(reason == "start_variant_mismatch");
    assert(!LoadLaunchChoicesFile(argv[6], rows, allPortPlugins, out, nowEpoch, 21600, true, &reason));
    assert(reason == "row_unavailable");
    assert(!LoadLaunchChoicesFile(argv[7], rows, allPortPlugins, out, nowEpoch, 21600, true, &reason));
    assert(reason == "row_unavailable");
    assert(!LoadLaunchChoicesFile(argv[8], rows, withPrewarPlugins, out, nowEpoch, 21600, true, &reason));
    assert(reason == "invalid_json_or_schema");

    // 7. fo4_vault111 ACCEPTED with core/port plugins (without Prewar) & via 3-arg fallback overload; REFUSED without FO4Port.esm
    assert(LoadLaunchChoicesFile(argv[5], rows, allPortPlugins, out, nowEpoch, 21600, true, &reason));
    assert(out.placeId == "fo4_vault111" && out.startVariant == "quick");
    LaunchChoicesPayload fbVault;
    assert(LoadLaunchChoicesFile(argv[5], fbVault, nowEpoch));
    assert(fbVault.placeId == "fo4_vault111");
    assert(!LoadLaunchChoicesFile(argv[5], rows, {{"Starfield.esm", "FO4SFNewGame.esm", "FO4SFCoreValues.esm"}}, out, nowEpoch, 21600, true, &reason));
    assert(reason == "missing_plugin:FO4Port.esm");

    std::cout << "cpp_r14_t1_ok\\n";
    return 0;
}}
"""
            run = _compile_and_run_cpp(
                root,
                "r14_t1_check.cpp",
                src,
                [
                    str(real_table_path),
                    str(disabled_table_p),
                    str(p_prewar),
                    str(p_v1),
                    str(p_vault),
                    str(p_fo3),
                    str(p_fnv),
                    str(p_wf_bad),
                    str(p_var_bad),
                ],
            )
            self.assertIn("cpp_r14_t1_ok", run.stdout)


if __name__ == "__main__":
    unittest.main()
