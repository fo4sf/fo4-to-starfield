"""Unit tests for `src/fo4sf/core/start_places.py`, `start_places.json`, and `S1`/`S3` contracts."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = str(REPO / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from fo4sf.core import start_places as sp  # noqa: E402


class StartPlacesTests(unittest.TestCase):
    def test_table_has_loadable_commonwealth_starts_and_all_s3_unavailable_scope_starts(self):
        self.assertEqual(sp.ALLOWED_STORY_START_IDS, ("fo4_prewar_sanctuary", "fo4_vault111"))
        rows = sp.load_start_places()
        self.assertEqual(len(rows), 20)
        avail = [r for r in rows if r.available]
        unavail = [r for r in rows if not r.available]
        self.assertEqual(
            [r.id for r in avail],
            ["fo4_prewar_sanctuary", "fo4_vault111", "minutemen_sanctuary", "gunners_plaza", "raiders_corvega"],
        )
        self.assertEqual(len(unavail), 15)

        unavail_story_ids = {r.id for r in unavail if r.mode == "story"}
        self.assertEqual(
            unavail_story_ids,
            {
                "fo3_vault101_birth",
                "fo3_vault101",
                "fnv_goodsprings",
                "fnv_goodsprings_door",
                "fo76_vault76",
                "fo1_vault13",
                "fo2_arroyo",
                "fot_bunkeralpha",
            },
        )
        unavail_warfare_ids = {r.id for r in unavail if r.mode == "warfare"}
        self.assertEqual(
            unavail_warfare_ids,
            {
                "brotherhood_airport",
                "railroad_oldnorth",
                "institute_concourse",
                "enclave_ravenrock",
                "settlers_diamondcity",
                "ncr_camp_mccarran",
                "legion_fort",
            },
        )
        by_id = {r.id: r for r in rows}
        self.assertEqual(by_id["fo4_prewar_sanctuary"].start_variant, "normal")
        self.assertEqual(by_id["fo4_prewar_sanctuary"].plugin, "FO4SFPrewar.esm")
        self.assertEqual(
            by_id["fo4_prewar_sanctuary"].required_plugins,
            ("FO4SFPrewar_Sanctuary.esm", "FO4SFPrewar.esm", "FO4SFNewGame.esm", "FO4SFCoreValues.esm"),
        )
        self.assertEqual(by_id["fo4_prewar_sanctuary"].pos, (52.82, -2.46, 112.23))
        self.assertEqual(by_id["fo4_prewar_sanctuary"].cell, (0, -1))
        self.assertEqual(by_id["fo4_prewar_sanctuary"].quests, ("FO4SF_PrewarQuest", "FO4SF_NewGame"))
        self.assertEqual(by_id["fo4_prewar_sanctuary"].quest_mask, 1)
        self.assertEqual(by_id["fo4_vault111"].start_variant, "quick")
        self.assertEqual(by_id["fo3_vault101_birth"].start_variant, "normal")
        self.assertEqual(by_id["fo3_vault101"].start_variant, "quick")
        self.assertEqual(by_id["fnv_goodsprings"].start_variant, "normal")
        self.assertEqual(by_id["fnv_goodsprings_door"].start_variant, "quick")
        for sid in ("fo76_vault76", "fo1_vault13", "fo2_arroyo", "fot_bunkeralpha"):
            self.assertEqual(by_id[sid].start_variant, "normal")
        for row in rows:
            if row.mode == "story":
                self.assertIn(row.start_variant, ("normal", "quick"))
            else:
                self.assertEqual(row.start_variant, "")
        for row in unavail:
            self.assertTrue(row.unavailable_reason)
            self.assertNotIn("\n", row.unavailable_reason)
            self.assertNotIn("\r", row.unavailable_reason)

    def test_refuses_unloadable_available_true_or_missing_unavailable_reason(self):
        all_req_plugins = (
            "Starfield.esm",
            "FO4Port.esm",
            "FO4TerrainCore.esm",
            "FO4SFPrewar_Sanctuary.esm",
            "FO4SFPrewar.esm",
            "FO4SFNewGame.esm",
            "FO4SFCoreValues.esm",
            "FO4SFReputation.esm",
            "FO4SFProgression.esm",
            "FO4SFCompanions.esm",
            "FO4SFMission.esm",
        )
        ok_rows = sp.load_start_places(
            known_plugins=all_req_plugins,
            known_marker_edids=(
                "FO4SF_PrewarHouseSpawnMarker",
                "FO4Core_CommonwealthMapMarkerSanctuary",
                "FO4Core_CommonwealthAnchor",
            ),
            known_exterior_cells=((0, -1), (-12, 12), (-2, -11), (-6, 5)),
        )
        self.assertEqual(len(ok_rows), 20)

        with self.assertRaises(ValueError):
            sp.load_start_places(known_plugins=("Starfield.esm", "FO4Port.esm"))
        with self.assertRaisesRegex(ValueError, "FO4SFPrewar_Sanctuary.esm"):
            sp.load_start_places(
                known_plugins=tuple(p for p in all_req_plugins if p != "FO4SFPrewar_Sanctuary.esm")
            )
        with self.assertRaisesRegex(ValueError, "FO4SFCoreValues.esm"):
            sp.load_start_places(
                known_plugins=("Starfield.esm", "FO4Port.esm", "FO4SFPrewar_Sanctuary.esm", "FO4SFPrewar.esm", "FO4SFNewGame.esm")
            )
        with self.assertRaises(ValueError):
            sp.load_start_places(
                known_plugins=all_req_plugins,
                known_marker_edids=("WrongMarker",),
            )

        # Strict exterior-cell gating: refuse missing exterior cell (including Prewar (0, -1) or Gunners (-2, -11))
        with self.assertRaisesRegex(ValueError, "exterior cell"):
            sp.load_start_places(
                known_plugins=all_req_plugins,
                known_marker_edids=(
                    "FO4SF_PrewarHouseSpawnMarker",
                    "FO4Core_CommonwealthMapMarkerSanctuary",
                    "FO4Core_CommonwealthAnchor",
                ),
                known_exterior_cells=((-12, 12), (-2, -11), (-6, 5)),
            )

        raw = json.loads(Path(sp.START_PLACES_JSON).read_text(encoding="utf-8"))
        fo3_idx = next(i for i, e in enumerate(raw["places"]) if e["id"] == "fo3_vault101_birth")
        wf_idx = next(i for i, e in enumerate(raw["places"]) if e["id"] == "minutemen_sanctuary")
        with tempfile.TemporaryDirectory() as td:
            bad_p = Path(td) / "bad_reason.json"
            bad_story = json.loads(json.dumps(raw))
            bad_story["places"][fo3_idx]["available"] = True
            bad_p.write_text(json.dumps(bad_story), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "before Task 6"):
                sp.load_start_places(str(bad_p))

            bad_empty = json.loads(json.dumps(raw))
            bad_empty["places"][fo3_idx]["unavailable_reason"] = ""
            bad_p.write_text(json.dumps(bad_empty), encoding="utf-8")
            with self.assertRaises(ValueError):
                sp.load_start_places(str(bad_p))

            bad_empty["places"][fo3_idx]["unavailable_reason"] = "two\nlines"
            bad_p.write_text(json.dumps(bad_empty), encoding="utf-8")
            with self.assertRaises(ValueError):
                sp.load_start_places(str(bad_p))

            bad_var = json.loads(json.dumps(raw))
            bad_var["places"][0]["start_variant"] = "invalid_variant"
            bad_p.write_text(json.dumps(bad_var), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "start_variant"):
                sp.load_start_places(str(bad_p))

            bad_wf_var = json.loads(json.dumps(raw))
            bad_wf_var["places"][wf_idx]["start_variant"] = "normal"
            bad_p.write_text(json.dumps(bad_wf_var), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "start_variant"):
                sp.load_start_places(str(bad_p))

    def test_default_leaves_unavailable_starts_off_and_commits_exact_start_record(self):
        self.assertFalse(sp.DEFAULT_SHOW_UNAVAILABLE_STARTS)
        rows = sp.load_start_places()
        model = sp.SetupScreenModel(rows)

        lines, status = model.render_lines()
        self.assertEqual(lines[0], "> MODE: STORY")
        self.assertEqual(lines[1], "  STORY LINE: FALLOUT 4: COMMONWEALTH")
        self.assertEqual(lines[2], "  START PLACE: SANCTUARY HILLS (PRE-WAR)")
        self.assertEqual(lines[3], "  SURVIVAL: OFF")
        self.assertEqual(lines[4], "  DIFFICULTY: NORMAL")
        self.assertEqual(status, "READY: PRESS CONFIRM (ENTER) TO BEGIN")

        # Cycling Story Line when show_unavailable=False keeps only Fallout 4: Commonwealth
        model.adjust_row(1, 1)
        self.assertEqual(model.current_place_row().id, "fo4_prewar_sanctuary")

        model.adjust_row(3, 1)  # Survival -> ON
        model.adjust_row(4, 1)  # Difficulty -> HARD (2)
        prewar_payload = model.confirm()
        self.assertIsNotNone(prewar_payload)
        assert prewar_payload is not None
        self.assertEqual(prewar_payload.start_place_row, 0)
        self.assertEqual(
            prewar_payload.start_record_line("setup_menu"),
            "start record mode=story story=fo4_commonwealth faction=-1 place=fo4_prewar_sanctuary survival=1 difficulty=2 backdrop=setup_menu",
        )

        # Cycling Start Place in FO4 Commonwealth Story switches between Pre-War Normal and Vault 111 Quick
        model.adjust_row(2, 1)
        self.assertEqual(model.current_place_row().id, "fo4_vault111")
        vault_payload = model.confirm()
        self.assertIsNotNone(vault_payload)
        assert vault_payload is not None
        self.assertEqual(vault_payload.start_place_row, 1)
        self.assertEqual(
            vault_payload.start_record_line("setup_menu"),
            "start record mode=story story=fo4_commonwealth faction=-1 place=fo4_vault111 survival=1 difficulty=2 backdrop=setup_menu",
        )

        # Switch to Warfare -> cycles Minutemen -> Gunners -> Commonwealth Raiders when show_unavailable=False
        model.adjust_row(0, 1)
        self.assertEqual(model.current_place_row().id, "minutemen_sanctuary")
        wf_payload = model.confirm()
        self.assertIsNotNone(wf_payload)
        assert wf_payload is not None
        self.assertEqual(
            wf_payload.start_record_line("setup_menu"),
            "start record mode=warfare story=none faction=0 place=minutemen_sanctuary survival=1 difficulty=2 backdrop=setup_menu",
        )
        model.adjust_row(1, 1)
        self.assertEqual(model.current_place_row().id, "gunners_plaza")
        model.adjust_row(1, 1)
        self.assertEqual(model.current_place_row().id, "raiders_corvega")
        model.adjust_row(1, 1)
        self.assertEqual(model.current_place_row().id, "minutemen_sanctuary")

    def test_show_unavailable_renders_locked_rows_and_never_confirms_unavailable_starts(self):
        rows = sp.load_start_places()
        model = sp.SetupScreenModel(rows, show_unavailable=True)

        # Story mode: index 0 is available FO4 (2 variants), indices 1..6 are all 6 unavailable Fallout games (8 rows)
        self.assertIsNotNone(model.confirm())
        seen_locked_stories = set()
        for _ in range(6):
            model.adjust_row(1, 1)
            cur = model.current_place_row()
            self.assertFalse(cur.available)
            seen_locked_stories.add(cur.id)
            if cur.story_id in ("fo3_capital_wasteland", "fnv_mojave"):
                model.adjust_row(2, 1)
                cur2 = model.current_place_row()
                self.assertFalse(cur2.available)
                self.assertNotEqual(cur2.id, cur.id)
                seen_locked_stories.add(cur2.id)
                self.assertIsNone(model.confirm(), f"confirm() must refuse unavailable start {cur2.id}")
            lines, status = model.render_lines()
            self.assertIn("[LOCKED]", lines[1])
            self.assertIn("[LOCKED]", lines[2])
            self.assertTrue(status.startswith("LOCKED: "))
            self.assertIsNone(model.confirm(), f"confirm() must refuse unavailable start {cur.id}")
        self.assertEqual(len(seen_locked_stories), 8)

        # Warfare mode: index 0 is available Minutemen; 7 faction groups are unavailable; Gunners & Raiders are available
        model.adjust_row(0, 1)
        self.assertEqual(model.current_place_row().id, "minutemen_sanctuary")
        self.assertIsNotNone(model.confirm())

        seen_locked_warfare = set()
        seen_avail_warfare = {"minutemen_sanctuary"}
        for _ in range(9):
            model.adjust_row(1, 1)
            cur = model.current_place_row()
            lines, status = model.render_lines()
            if cur.available:
                seen_avail_warfare.add(cur.id)
                self.assertEqual(status, "READY: PRESS CONFIRM (ENTER) TO BEGIN")
                self.assertIsNotNone(model.confirm())
            else:
                seen_locked_warfare.add(cur.id)
                self.assertIn("[LOCKED]", lines[1])
                self.assertIn("[LOCKED]", lines[2])
                self.assertTrue(status.startswith("LOCKED: "))
                self.assertIsNone(model.confirm(), f"confirm() must refuse unavailable warfare start {cur.id}")
        self.assertEqual(seen_avail_warfare, {"minutemen_sanctuary", "gunners_plaza", "raiders_corvega"})
        self.assertEqual(len(seen_locked_warfare), 7)

    def test_blocking_menus_header_keeps_38_entries_and_declares_setup_menu_name(self):
        hdr = (REPO / "sfse" / "common" / "blocking_menus.h").read_text(encoding="utf-8")
        self.assertIn('kOurSetupMenuName = "FO4SF_SetupMenu"', hdr)
        self.assertIn("std::array<const char*, 38> kBlockingMenus", hdr)


if __name__ == "__main__":
    unittest.main()
