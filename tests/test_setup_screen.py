"""Parity tests for Variant (b) setup screen and Grok #5984954658 canonical `warfare_starts.json` indexing.

Verifies that `SetupCommitPayload.warfare_start_idx` (`FO4SF_WarfareStartIndex` / C++ `warfareStartIdx`)
resolves against canonical `warfare_starts.json` / `FO4SFWarfareStarts.json` row order rather than
available-only ordinal when intermediate Warfare rows are unavailable.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
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
                # First available Warfare row is minutemen_sanctuary (canonical index 0)
                p0 = model.confirm()
                self.assertIsNotNone(p0)
                assert p0 is not None
                self.assertEqual(p0.place_id, "minutemen_sanctuary")
                self.assertEqual(p0.warfare_start_idx, 0)

                # Advance to settlers_diamondcity (skipping locked brotherhood_airport when show_unavail=True)
                model.adjust_row(1, 1)
                if show_unavail:
                    self.assertIsNone(model.confirm())
                    model.adjust_row(1, 1)
                p2 = model.confirm()
                self.assertIsNotNone(p2)
                assert p2 is not None
                self.assertEqual(p2.place_id, "settlers_diamondcity")
                # Must be canonical index 2 in warfare_starts.json, NOT available-only ordinal 1
                self.assertEqual(p2.warfare_start_idx, 2)
                self.assertEqual(p2.start_place_row, 2)  # 0=fo4_vault111, 1=minutemen_sanctuary, 2=settlers_diamondcity

    def test_warfare_starts_json_order_overrides_start_places_order_and_supports_sibling_filename(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            places_p = root / "FO4SFStartPlaces.json"
            wf_sibling = root / "FO4SFWarfareStarts.json"
            places_p.write_text(json.dumps(_make_sparse_places_doc()), encoding="utf-8")
            # Deliberately reordered vs start_places.json: settlers_diamondcity is row 0, minutemen_sanctuary is row 2
            wf_sibling.write_text(
                json.dumps(_make_warfare_starts_doc(["settlers_diamondcity", "brotherhood_airport", "minutemen_sanctuary"])),
                encoding="utf-8",
            )

            rows = sp.load_start_places(str(places_p))
            model = sp.SetupScreenModel(rows, warfare_starts_path=str(root / "warfare_starts.json"))
            model.adjust_row(0, 1)  # Warfare -> minutemen_sanctuary
            p_mm = model.confirm()
            self.assertIsNotNone(p_mm)
            assert p_mm is not None
            self.assertEqual(p_mm.warfare_start_idx, 2)

            model.adjust_row(1, 1)  # -> settlers_diamondcity
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
            model.adjust_row(0, 1)  # Warfare
            model.adjust_row(1, 1)  # settlers_diamondcity
            payload = model.confirm()
            self.assertIsNotNone(payload)
            assert payload is not None
            self.assertEqual(payload.place_id, "settlers_diamondcity")
            # Even without warfare_starts.json, intermediate unavailable brotherhood_airport preserves canonical index 2
            self.assertEqual(payload.warfare_start_idx, 2)

    def test_cpp_setup_places_header_has_exact_warfare_starts_parity_contract(self):
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
        ):
            self.assertIn(sym, hdr, f"setup_places.h missing Grok #5984954658 symbol {sym}")
        # Confirm() must not regress to counting available-only warfare rows
        confirm_body = hdr[hdr.index("std::optional<SetupCommitPayload> Confirm() const"):hdr.index("private:")]
        self.assertIn("ResolveWarfareStartIdx(cur)", confirm_body)
        self.assertNotIn("for (const auto& r : _availRows) {\n\t\t\t\tif (r.mode == \"warfare\")", confirm_body)

    def test_cpp_and_python_live_parity_when_host_cpp_compiler_present(self):
        cxx = shutil.which("g++") or shutil.which("clang++")
        if not cxx:
            self.skipTest("no host g++/clang++ on PATH for native setup_places.h parity check")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            places_p = root / "FO4SFStartPlaces.json"
            wf_p = root / "FO4SFWarfareStarts.json"
            places_p.write_text(json.dumps(_make_sparse_places_doc()), encoding="utf-8")
            wf_p.write_text(
                json.dumps(_make_warfare_starts_doc(["minutemen_sanctuary", "brotherhood_airport", "settlers_diamondcity"])),
                encoding="utf-8",
            )
            harness = root / "parity.cpp"
            exe = root / ("parity.exe" if sys.platform == "win32" else "parity")
            harness.write_text(
                f"""#include <cassert>
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
""",
                encoding="utf-8",
            )
            comp = subprocess.run([cxx, "-std=c++20", str(harness), "-o", str(exe)], capture_output=True, text=True)
            self.assertEqual(comp.returncode, 0, comp.stdout + "\n" + comp.stderr)
            run = subprocess.run([str(exe), str(places_p)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + "\n" + run.stderr)
            self.assertIn("cpp_parity_ok", run.stdout)


if __name__ == "__main__":
    unittest.main()
