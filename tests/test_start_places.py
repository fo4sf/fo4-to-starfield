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
        rows = sp.load_start_places()
        self.assertEqual(len(rows), 17)
        avail = [r for r in rows if r.available]
        unavail = [r for r in rows if not r.available]
        self.assertEqual(
            [r.id for r in avail],
            ["fo4_vault111", "minutemen_sanctuary", "gunners_plaza", "raiders_corvega"],
        )
        self.assertEqual(len(unavail), 13)

        unavail_story_ids = {r.id for r in unavail if r.mode == "story"}
        self.assertEqual(
            unavail_story_ids,
            {"fo3_vault101", "fnv_goodsprings", "fo76_vault76", "fo1_vault13", "fo2_arroyo", "fot_bunkeralpha"},
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
        for row in unavail:
            self.assertTrue(row.unavailable_reason)
            self.assertNotIn("\n", row.unavailable_reason)
            self.assertNotIn("\r", row.unavailable_reason)

    def test_refuses_unloadable_available_true_or_missing_unavailable_reason(self):
        all_req_plugins = (
            "Starfield.esm",
            "FO4Port.esm",
            "FO4TerrainCore.esm",
            "FO4SFNewGame.esm",
            "FO4SFCoreValues.esm",
            "FO4SFReputation.esm",
            "FO4SFProgression.esm",
            "FO4SFCompanions.esm",
            "FO4SFMission.esm",
        )
        with self.assertRaises(ValueError):
            sp.load_start_places(known_plugins=("Starfield.esm", "FO4Port.esm"))
        with self.assertRaisesRegex(ValueError, "FO4SFCoreValues.esm"):
            sp.load_start_places(known_plugins=("Starfield.esm", "FO4Port.esm", "FO4SFNewGame.esm"))
        with self.assertRaises(ValueError):
            sp.load_start_places(
                known_plugins=all_req_plugins,
                known_marker_edids=("WrongMarker",),
            )

        # Strict Story & exterior-cell gating: refuse Story != fo4_vault111 claiming available=true, and missing cell
        with self.assertRaisesRegex(ValueError, "exterior cell"):
            sp.load_start_places(
                known_plugins=all_req_plugins,
                known_marker_edids=("FO4Core_CommonwealthMapMarkerSanctuary", "FO4Core_CommonwealthAnchor"),
                known_exterior_cells=((-12, 12),),
            )

        raw = json.loads(Path(sp.START_PLACES_JSON).read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:
            bad_p = Path(td) / "bad_reason.json"
            bad_story = json.loads(json.dumps(raw))
            bad_story["places"][2]["available"] = True
            bad_p.write_text(json.dumps(bad_story), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "before Task 6"):
                sp.load_start_places(str(bad_p))

            bad_empty = json.loads(json.dumps(raw))
            bad_empty["places"][2]["unavailable_reason"] = ""
            bad_p.write_text(json.dumps(bad_empty), encoding="utf-8")
            with self.assertRaises(ValueError):
                sp.load_start_places(str(bad_p))

            bad_empty["places"][2]["unavailable_reason"] = "two\nlines"
            bad_p.write_text(json.dumps(bad_empty), encoding="utf-8")
            with self.assertRaises(ValueError):
                sp.load_start_places(str(bad_p))

    def test_default_leaves_unavailable_starts_off_and_commits_exact_start_record(self):
        self.assertFalse(sp.DEFAULT_SHOW_UNAVAILABLE_STARTS)
        rows = sp.load_start_places()
        model = sp.SetupScreenModel(rows)

        lines, status = model.render_lines()
        self.assertEqual(lines[0], "> MODE: STORY")
        self.assertEqual(lines[1], "  STORY LINE: FALLOUT 4: COMMONWEALTH")
        self.assertEqual(lines[2], "  START PLACE: VAULT 111 (COMMONWEALTH)")
        self.assertEqual(lines[3], "  SURVIVAL: OFF")
        self.assertEqual(lines[4], "  DIFFICULTY: NORMAL")
        self.assertEqual(status, "READY: PRESS CONFIRM (ENTER) TO BEGIN")

        # Cycling Story Line when show_unavailable=False keeps only Fallout 4: Commonwealth
        model.adjust_row(1, 1)
        self.assertEqual(model.current_place_row().id, "fo4_vault111")

        model.adjust_row(3, 1)  # Survival -> ON
        model.adjust_row(4, 1)  # Difficulty -> HARD (2)
        story_payload = model.confirm()
        self.assertIsNotNone(story_payload)
        assert story_payload is not None
        self.assertEqual(
            story_payload.start_record_line("setup_menu"),
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

        # Story mode: index 0 is available FO4, indices 1..6 are all 6 unavailable Fallout games
        self.assertIsNotNone(model.confirm())
        seen_locked_stories = set()
        for _ in range(6):
            model.adjust_row(1, 1)
            cur = model.current_place_row()
            self.assertFalse(cur.available)
            seen_locked_stories.add(cur.id)
            lines, status = model.render_lines()
            self.assertIn("[LOCKED]", lines[1])
            self.assertIn("[LOCKED]", lines[2])
            self.assertTrue(status.startswith("LOCKED: "))
            self.assertIsNone(model.confirm(), f"confirm() must refuse unavailable start {cur.id}")
        self.assertEqual(len(seen_locked_stories), 6)

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
