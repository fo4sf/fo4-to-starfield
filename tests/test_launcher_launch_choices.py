"""Tests for pre-launch Story/Warfare, Survival, and filtered start-place choices (R12 Task 5 / R13)."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from fo4sf.core import start_places as sp  # noqa: E402
from fo4sf.launcher import crashwatch, gui, launch_choices, settings, start_cover  # noqa: E402
from test_launcher_crashwatch import FakeSystem  # noqa: E402

ALL_REQ_PLUGINS = (
    "Starfield.esm",
    "FO4Port.esm",
    "FO4TerrainCore.esm",
    "FO4SFNewGame.esm",
    "FO4SFCoreValues.esm",
    "FO4SFHardcore.esm",
    "FO4SFReputation.esm",
    "FO4SFProgression.esm",
    "FO4SFCompanions.esm",
    "FO4SFMission.esm",
)


def _subrec(sig: bytes, data: bytes) -> bytes:
    return sig + struct.pack("<H", len(data)) + data


def _record(sig: bytes, fid: int, body: bytes, *, flags: int = 0) -> bytes:
    return sig + struct.pack("<IIII", len(body), flags, fid, 0) + b"\x00\x00\x00\x00" + body


def _grup(label: bytes, gtype: int, payload: bytes) -> bytes:
    return b"GRUP" + struct.pack("<I", 24 + len(payload)) + label + struct.pack("<iII", gtype, 0, 0) + payload


def _build_minimal_tes4_plugin(
    *,
    interior_cells: tuple[tuple[int, str], ...] = (),
    exterior_cells: tuple[tuple[int, int, int, tuple[tuple[int, str], ...]], ...] = (),
) -> bytes:
    """Build a valid TES4 plugin binary with interior CELLs and exterior WRLD/CELL/persistent REFRs."""
    hedr = struct.pack("<fIi", 0.96, 1, 0x800)
    tes4 = _record(b"TES4", 0, _subrec(b"HEDR", hedr) + _subrec(b"CNAM", b"Test\0"), flags=1)
    chunks: list[bytes] = [tes4]
    if interior_cells:
        cell_recs = b"".join(
            _record(b"CELL", fid, _subrec(b"EDID", edid.encode("ascii") + b"\0"), flags=0x0001)
            for fid, edid in interior_cells
        )
        chunks.append(_grup(b"CELL", 0, cell_recs))
    if exterior_cells:
        wrld_rec = _record(b"WRLD", 0x01000800, _subrec(b"EDID", b"FO4Core_Commonwealth\0"))
        cell_blocks: list[bytes] = []
        for fid, gx, gy, refs in exterior_cells:
            cell_rec = _record(
                b"CELL",
                fid,
                _subrec(b"XCLC", struct.pack("<2iI", gx, gy, 0)),
                flags=0,
            )
            cell_blocks.append(cell_rec)
            if refs:
                ref_bytes = b"".join(
                    _record(b"REFR", rfid, _subrec(b"EDID", redid.encode("ascii") + b"\0"), flags=0x0400)
                    for rfid, redid in refs
                )
                cell_blocks.append(_grup(struct.pack("<I", fid), 8, ref_bytes))
        wrld_children = _grup(struct.pack("<I", 0x01000800), 1, b"".join(cell_blocks))
        chunks.append(_grup(b"WRLD", 0, wrld_rec + wrld_children))
    return b"".join(chunks)


class LaunchChoicesTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        self.local = self.root / "local"
        self.game = self.root / "Starfield"
        self.data = self.game / "Data"
        self.data.mkdir(parents=True)
        (self.game / "Starfield.exe").write_bytes(b"MZ")
        (self.game / "sfse_loader.exe").write_bytes(b"MZ")
        (self.data / "Starfield.esm").write_bytes(_build_minimal_tes4_plugin())
        (self.data / "FO4Port.esm").write_bytes(
            _build_minimal_tes4_plugin(interior_cells=((0x01000800, "FO4Port_Vault111Cryo"),))
        )
        (self.data / "FO4TerrainCore.esm").write_bytes(
            _build_minimal_tes4_plugin(
                exterior_cells=(
                    (0x01000D30, -12, 12, ((0x01000810, "FO4Core_CommonwealthMapMarkerSanctuary"),)),
                    (0x01000F9A, -2, -11, ((0x01000800, "FO4Core_CommonwealthAnchor"),)),
                    (0x01000EAA, -6, 5, ()),
                )
            )
        )
        for dep in ALL_REQ_PLUGINS:
            p = self.data / dep
            if not p.exists():
                p.write_bytes(_build_minimal_tes4_plugin())

    def test_scan_detects_real_tes4_data_flagged_interior_cell(self):
        # Real Starfield/FO4 plugins set DATA[0] & 0x01 with record flags == 0 under GRUP(CELL)
        hedr = struct.pack("<fIi", 0.96, 1, 0x800)
        tes4 = _record(b"TES4", 0, _subrec(b"HEDR", hedr) + _subrec(b"CNAM", b"Test\0"), flags=1)
        cell_rec = _record(
            b"CELL",
            0x010049B4,
            _subrec(b"EDID", b"FO4Port_Vault111Cryo\0") + _subrec(b"DATA", struct.pack("<I", 1)),
            flags=0,
        )
        (self.data / "FO4Port.esm").write_bytes(tes4 + _grup(b"CELL", 0, cell_rec))
        scanned = launch_choices.scan_data_dir_places(str(self.data))
        self.assertIsNotNone(scanned)
        assert scanned is not None
        self.assertIn("FO4Port_Vault111Cryo", scanned["interior_cells"])

    def test_filters_strictly_by_mode_and_loaded_plugins_and_places(self):
        scanned = launch_choices.scan_data_dir_places(str(self.data))
        self.assertIsNotNone(scanned)
        assert scanned is not None
        self.assertIn((-12, 12), scanned["exterior_cells"])
        self.assertIn((-2, -11), scanned["exterior_cells"])
        self.assertIn((-6, 5), scanned["exterior_cells"])
        self.assertIn("FO4Port_Vault111Cryo", scanned["interior_cells"])
        self.assertIn("FO4Core_CommonwealthAnchor", scanned["markers"])

        story_avail, _ = launch_choices.evaluate_start_places(
            mode="story", loaded_plugins=ALL_REQ_PLUGINS, loaded_places=scanned
        )
        self.assertEqual([r.id for r in story_avail], ["fo4_vault111"])

        # Also test Pre-War Sanctuary (#863) when prewar plugins + cell/marker are loaded vs absent (#860)
        self.assertNotIn("fo4_prewar_sanctuary", [r.id for r in story_avail])
        prewar_avail, _ = launch_choices.evaluate_start_places(
            mode="story",
            loaded_plugins=ALL_REQ_PLUGINS + ("FO4SFPrewar.esm", "FO4SFPrewar_Sanctuary.esm"),
            loaded_places={
                "markers": set(scanned["markers"]) | {"FO4SF_PrewarHouseSpawnMarker"},
                "interior_cells": set(scanned["interior_cells"]),
                "exterior_cells": set(scanned["exterior_cells"]) | {(0, -1)},
            },
        )
        self.assertEqual([r.id for r in prewar_avail], ["fo4_prewar_sanctuary", "fo4_vault111"])

        warfare_avail, _ = launch_choices.evaluate_start_places(
            mode="warfare", loaded_plugins=ALL_REQ_PLUGINS, loaded_places=scanned
        )
        self.assertEqual(
            [r.id for r in warfare_avail],
            ["minutemen_sanctuary", "gunners_plaza", "raiders_corvega"],
        )

        # Missing cell (-2, -11) drops gunners_plaza cleanly and explains why
        partial = {
            "markers": set(scanned["markers"]),
            "interior_cells": set(scanned["interior_cells"]),
            "exterior_cells": {(-12, 12), (-6, 5)},
        }
        wf_partial, reasons = launch_choices.evaluate_start_places(
            mode="warfare", loaded_plugins=ALL_REQ_PLUGINS, loaded_places=partial
        )
        self.assertEqual([r.id for r in wf_partial], ["minutemen_sanctuary", "raiders_corvega"])
        self.assertIn("(-2, -11)", reasons["gunners_plaza"])

        # Missing FO4TerrainCore.esm drops every Warfare row cleanly
        wf_no_tc, wf_reasons = launch_choices.evaluate_start_places(
            mode="warfare",
            loaded_plugins=("Starfield.esm", "FO4Port.esm", "FO4SFNewGame.esm", "FO4SFCoreValues.esm"),
            loaded_places=scanned,
        )
        self.assertEqual(wf_no_tc, [])
        self.assertIn("FO4TerrainCore.esm", wf_reasons["minutemen_sanctuary"])

        # F9: Missing FO4SFCoreValues.esm / FO4SFNewGame.esm / FO4SFMission.esm drops dependent rows cleanly
        no_mission = tuple(p for p in ALL_REQ_PLUGINS if p != "FO4SFMission.esm")
        wf_no_mission, miss_reasons = launch_choices.evaluate_start_places(
            mode="warfare", loaded_plugins=no_mission, loaded_places=scanned
        )
        self.assertEqual([r.id for r in wf_no_mission], ["gunners_plaza", "raiders_corvega"])
        self.assertIn("FO4SFMission.esm", miss_reasons["minutemen_sanctuary"])

        no_cv = tuple(p for p in ALL_REQ_PLUGINS if p != "FO4SFCoreValues.esm")
        st_no_cv, st_cv_reasons = launch_choices.evaluate_start_places(
            mode="story", loaded_plugins=no_cv, loaded_places=scanned
        )
        self.assertEqual(st_no_cv, [])
        self.assertIn("FO4SFCoreValues.esm", st_cv_reasons["fo4_vault111"])

        # Missing FO4Port.esm drops Vault 111 cleanly
        st_no_port, st_reasons = launch_choices.evaluate_start_places(
            mode="story", loaded_plugins=tuple(p for p in ALL_REQ_PLUGINS if p != "FO4Port.esm"), loaded_places=scanned
        )
        self.assertEqual(st_no_port, [])
        self.assertIn("FO4Port.esm", st_reasons["fo4_vault111"])

    def test_refuses_survival_on_when_hardcore_plugin_absent(self):
        # F9: --survival on / start.survival=True MUST refuse when FO4SFHardcore.esm is absent
        entries_no_hc = [(p, True) for p in ALL_REQ_PLUGINS if p != "FO4SFHardcore.esm"]
        vals = settings.defaults()
        vals.update({"start.mode": "warfare", "start.survival": True, "start.place": "gunners_plaza"})
        with self.assertRaisesRegex(ValueError, "FO4SFHardcore.esm"):
            launch_choices.resolve_and_build_launch_choices(
                vals, starfield_dir=str(self.game), entries=entries_no_hc, nonce="hc_miss", strict_session=True
            )

        # CLI check with FO4SFHardcore.esm removed from Data/
        (self.data / "FO4SFHardcore.esm").unlink()
        spec = importlib.util.spec_from_file_location("launcher_cli_hc", str(ROOT / "scripts" / "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(self.local)}):
            rc = cli.main([
                "launch-choices", "--starfield", str(self.game), "--mode", "warfare",
                "--survival", "on", "--place", "gunners_plaza",
            ])
        self.assertEqual(rc, 2)

    def test_refuses_non_vault111_story_row_claiming_available_until_task6(self):
        raw = json.loads(Path(sp.START_PLACES_JSON).read_text(encoding="utf-8"))
        for entry in raw["places"]:
            if entry["id"] == "fo3_vault101":
                entry["available"] = True
                break
        bad_json = self.root / "bad_story.json"
        bad_json.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "before Task 6"):
            sp.load_start_places(str(bad_json))

        fake_story = sp.StartPlaceRow(
            id="fo3_vault101",
            mode="story",
            story_id="fo3_cw",
            story_label="Fallout 3",
            faction_slot=-1,
            faction_label="",
            name="Vault 101",
            space="Vault101",
            is_interior=True,
            plugin="FO4Port.esm",
            marker_source="vault_anchor",
            marker_edid="",
            quests=(),
            quest_mask=0,
            warfare_key="",
            min_difficulty=0,
            max_difficulty=3,
            available=True,
            start_variant="quick",
        )
        avail, reasons = launch_choices.evaluate_start_places([fake_story], mode="story")
        self.assertEqual(avail, [])
        self.assertIn("Task 6", reasons["fo3_vault101"])

    def test_writes_only_restart_only_keys_and_cross_os_paths(self):
        entries = [(p, True) for p in ALL_REQ_PLUGINS]
        values = settings.defaults()
        values.update({"start.mode": "warfare", "start.survival": True, "start.place": "raiders_corvega"})
        payload = launch_choices.resolve_and_build_launch_choices(
            values, starfield_dir=str(self.game), entries=entries, nonce="abc123", created_at=1795500000, strict_session=True
        )
        self.assertEqual(launch_choices.LAUNCH_CHOICES_SCHEMA_VERSION, 2)
        self.assertEqual(launch_choices.ALLOWED_STORY_IDS, ("fo4_prewar_sanctuary", "fo4_vault111"))
        self.assertNotIn("route", launch_choices.RESTART_ONLY_KEYS)
        self.assertEqual(set(payload), set(launch_choices.RESTART_ONLY_KEYS))
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["mode"], "warfare")
        self.assertEqual(payload["game_mode"], 2)
        self.assertEqual(payload["start_variant"], "none")
        self.assertTrue(payload["survival"])
        self.assertEqual(payload["survival_start"], 1)
        self.assertEqual(payload["survival_locked"], 1)
        self.assertEqual(payload["warfare_faction_slot"], 7)
        self.assertEqual(payload["warfare_start_idx"], 2)
        self.assertEqual(payload["place_id"], "raiders_corvega")
        self.assertEqual(payload["start_place_row"], 3)
        self.assertEqual(payload["min_difficulty"], 2)  # F11: raiders_corvega min_difficulty
        self.assertEqual(payload["created_at"], 1795500000)
        self.assertEqual(payload["nonce"], "abc123")
        for forbidden in ("difficulty", "special", "traits", "appearance", "skills", "route"):
            self.assertNotIn(forbidden, payload)

        # #860 story default (no FO4SFPrewar.esm): fo4_vault111 -> start_place_row == 0, start_variant == "quick"
        story_vals = dict(settings.defaults(), **{"start.mode": "story"})
        story_860 = launch_choices.resolve_and_build_launch_choices(
            story_vals, starfield_dir=str(self.game), entries=entries, nonce="st860", created_at=1795500001, strict_session=True
        )
        self.assertEqual(story_860["schema_version"], 2)
        self.assertEqual(story_860["place_id"], "fo4_vault111")
        self.assertEqual(story_860["start_variant"], "quick")
        self.assertEqual(story_860["start_place_row"], 0)

        # #863 story with FO4SFPrewar.esm + FO4SFPrewar_Sanctuary.esm loaded: fo4_prewar_sanctuary == 0, fo4_vault111 == 1, raiders_corvega == 4
        prewar_plugins = ALL_REQ_PLUGINS + ("FO4SFPrewar.esm", "FO4SFPrewar_Sanctuary.esm")
        prewar_places = {
            "markers": {"FO4SF_PrewarHouseSpawnMarker", "FO4Core_CommonwealthMapMarkerSanctuary", "FO4Core_CommonwealthAnchor"},
            "interior_cells": {"FO4Port_Vault111Cryo"},
            "exterior_cells": {(0, -1), (-12, 12), (-2, -11), (-6, 5)},
        }
        story_863_norm = launch_choices.resolve_and_build_launch_choices(
            dict(settings.defaults(), **{"start.mode": "story", "start.variant": "normal"}),
            loaded_plugins=prewar_plugins,
            loaded_places=prewar_places,
            nonce="st863n",
            created_at=1795500002,
            strict_session=True,
        )
        self.assertEqual(story_863_norm["schema_version"], 2)
        self.assertEqual(story_863_norm["place_id"], "fo4_prewar_sanctuary")
        self.assertEqual(story_863_norm["start_variant"], "normal")
        self.assertEqual(story_863_norm["start_place_row"], 0)

        story_863_quick = launch_choices.resolve_and_build_launch_choices(
            dict(settings.defaults(), **{"start.mode": "story", "start.variant": "quick"}),
            loaded_plugins=prewar_plugins,
            loaded_places=prewar_places,
            nonce="st863q",
            created_at=1795500003,
            strict_session=True,
        )
        self.assertEqual(story_863_quick["place_id"], "fo4_vault111")
        self.assertEqual(story_863_quick["start_variant"], "quick")
        self.assertEqual(story_863_quick["start_place_row"], 1)

        wf_863 = launch_choices.resolve_and_build_launch_choices(
            dict(settings.defaults(), **{"start.mode": "warfare", "start.place": "raiders_corvega"}),
            loaded_plugins=prewar_plugins,
            loaded_places=prewar_places,
            nonce="wf863",
            created_at=1795500004,
            strict_session=True,
        )
        self.assertEqual(wf_863["start_place_row"], 4)
        self.assertEqual(wf_863["start_variant"], "none")

        # Variant compatibility & unavailability checks
        with self.assertRaisesRegex(ValueError, "incompatible"):
            launch_choices.resolve_and_build_launch_choices(
                dict(settings.defaults(), **{"start.mode": "story", "start.variant": "normal", "start.place": "fo4_vault111"}),
                loaded_plugins=prewar_plugins,
                loaded_places=prewar_places,
                nonce="badvar1",
                created_at=1795500005,
                strict_session=True,
            )
        with self.assertRaisesRegex(ValueError, "only valid for mode='story'"):
            launch_choices.resolve_and_build_launch_choices(
                dict(settings.defaults(), **{"start.mode": "warfare", "start.variant": "normal"}),
                loaded_plugins=prewar_plugins,
                loaded_places=prewar_places,
                nonce="badvar2",
                created_at=1795500006,
                strict_session=True,
            )
        with self.assertRaisesRegex(ValueError, "FO4SFPrewar"):
            launch_choices.resolve_and_build_launch_choices(
                dict(settings.defaults(), **{"start.mode": "story", "start.variant": "normal"}),
                starfield_dir=str(self.game),
                entries=entries,
                nonce="badvar3",
                created_at=1795500007,
                strict_session=True,
            )

        with self.assertRaisesRegex(ValueError, "non-restart keys"):
            launch_choices.write_launch_choices(
                str(self.local / "bad.json"), dict(payload, difficulty=3)
            )
        with self.assertRaisesRegex(ValueError, "nonce"):
            launch_choices.write_launch_choices(
                str(self.local / "bad_nonce.json"), dict(payload, nonce="")
            )
        with self.assertRaisesRegex(ValueError, "created_at"):
            launch_choices.write_launch_choices(
                str(self.local / "bad_ts.json"), dict(payload, created_at=0)
            )

        out = launch_choices.default_launch_choices_path({"LOCALAPPDATA": str(self.local)})
        launch_choices.write_launch_choices(out, payload)
        self.assertEqual(launch_choices.read_launch_choices(out), payload)

        drv = "C" + ":"
        self.assertTrue(
            launch_choices.default_launch_choices_path({"LOCALAPPDATA": drv + "\\UsersData\\Local"}).endswith(
                "FO4SF\\launch_choices.json"
            )
        )
        self.assertEqual(
            launch_choices.default_launch_choices_path({"LOCALAPPDATA": "/tmp/fo4sf_state"}),
            "/tmp/fo4sf_state/FO4SF/launch_choices.json",
        )

    def test_settings_problems_and_gui_filtered_options(self):
        bad_mode_place = dict(settings.defaults(), **{"start.mode": "warfare", "start.place": "fo4_vault111"})
        self.assertTrue(any("mode='story'" in p for p in settings.problems(bad_mode_place)))

        bad_locked = dict(settings.defaults(), **{"start.mode": "story", "start.place": "fo3_vault101"})
        self.assertTrue(any("unavailable" in p for p in settings.problems(bad_locked)))

        with self.assertRaises(ValueError):
            settings.coerce("start.place", "nonexistent_place")

        entries = [(p, True) for p in ALL_REQ_PLUGINS]
        self.assertEqual(
            launch_choices.available_place_options("story", starfield_dir=str(self.game), entries=entries),
            ["", "fo4_vault111"],
        )
        self.assertEqual(
            launch_choices.available_place_options("story", variant="normal", starfield_dir=str(self.game), entries=entries),
            [""],
        )
        self.assertEqual(
            launch_choices.available_place_options("story", variant="quick", starfield_dir=str(self.game), entries=entries),
            ["", "fo4_vault111"],
        )
        self.assertEqual(
            launch_choices.available_place_options("warfare", starfield_dir=str(self.game), entries=entries),
            ["", "minutemen_sanctuary", "gunners_plaza", "raiders_corvega"],
        )

        # GUI disabled unavailable rows formatting + non-interactive Text widget check
        items, text = gui.format_unavailable_start_places("story", starfield_dir=str(self.game), entries=entries)
        by_id = {it["id"]: it for it in items}
        self.assertIn("fo4_prewar_sanctuary", by_id)
        self.assertEqual(by_id["fo4_prewar_sanctuary"]["start_variant"], "normal")
        self.assertIn("FO4SFPrewar.esm", by_id["fo4_prewar_sanctuary"]["reason"])
        self.assertIn("fo3_vault101_birth", by_id)
        self.assertIn("fo3_vault101", by_id)
        self.assertIn("fnv_goodsprings", by_id)
        self.assertIn("fnv_goodsprings_door", by_id)
        self.assertIn("[normal]", text)
        self.assertIn("[quick]", text)
        self.assertIn(by_id["fo3_vault101"]["reason"], text)

        gui_src = (ROOT / "src" / "fo4sf" / "launcher" / "gui.py").read_text(encoding="utf-8")
        self.assertIn("self.start_places_unavailable_box = unavail_box", gui_src)
        self.assertIn('state="disabled"', gui_src)
        self.assertNotIn("self.widgets.append((unavail_box", gui_src)
        self.assertGreater(gui_src.index("refresh_start_place_choices"), gui_src.index("start_places_unavailable_box"))

        try:
            import tkinter as tk
        except ImportError:
            tk = None

        if tk is not None:
            try:
                tk_root = tk.Tk()
            except tk.TclError:
                tk_root = None
            if tk_root is not None:
                try:
                    tk_root.withdraw()
                    pal = gui.select_palette(False)
                    txt = tk.Text(
                        tk_root,
                        height=6,
                        wrap="word",
                        state="disabled",
                        background=pal["panel"],
                        foreground=pal["muted"],
                        relief="flat",
                        takefocus=0,
                        cursor="arrow",
                        exportselection=False,
                    )
                    txt.configure(state="normal")
                    txt.insert("1.0", text)
                    txt.configure(state="disabled")
                    self.assertEqual(str(txt.cget("state")), "disabled")
                    self.assertIn("Sanctuary Hills (Pre-War)", txt.get("1.0", "end"))
                finally:
                    tk_root.destroy()

        # GUI control mapping stays 1:1 with SPEC
        keys = [c["key"] for c in gui.controls()]
        self.assertIn("start.mode", keys)
        self.assertIn("start.variant", keys)
        self.assertIn("start.survival", keys)
        self.assertIn("start.place", keys)

    def test_crashwatch_play_writes_choices_clears_stale_signal_and_cli_works(self):
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(self.local)}):
            stale_sig = start_cover.default_signal_path()
            start_cover.write_fake_ready_signal(stale_sig, stage="stale")
            self.assertTrue(os.path.isfile(stale_sig))

            dumps = self.root / "dumps"
            dumps.mkdir()
            procdump = self.root / "procdump64.exe"
            procdump.write_bytes(b"")

            sys_real = crashwatch.System()
            fake = FakeSystem([(42, 0, 100, 0)])
            fake.entries = [(p, True) for p in ALL_REQ_PLUGINS]
            fake.write_start_choices = sys_real.write_start_choices

            vals = settings.defaults()
            vals.update({
                "crash_watch.enabled": True,
                "crash_watch.folder": str(dumps),
                "crash_watch.procdump": str(procdump),
                "load_order": "off",
                "start.mode": "warfare",
                "start.survival": True,
                "start.place": "raiders_corvega",
            })

            # Dry run validates but neither removes signal nor writes launch_choices.json
            said = []
            dry = crashwatch.play(vals, str(self.game), system=fake, say=said.append, dry_run=True)
            self.assertTrue(dry["dry_run"])
            self.assertEqual(dry["start_choices"]["place_id"], "raiders_corvega")
            self.assertTrue(os.path.isfile(stale_sig))
            self.assertFalse(os.path.isfile(launch_choices.default_launch_choices_path()))

            # Live play clears stale signal and writes launch_choices.json atomically before start_game
            live = crashwatch.play(vals, str(self.game), system=fake, say=said.append, launch_nonce="n99")
            self.assertTrue(live["started"])
            self.assertFalse(os.path.isfile(stale_sig))
            written = launch_choices.read_launch_choices(launch_choices.default_launch_choices_path())
            assert written is not None
            self.assertEqual(written["place_id"], "raiders_corvega")
            self.assertTrue(written["survival"])
            self.assertEqual(written["min_difficulty"], 2)
            self.assertGreater(written["created_at"], 0)
            self.assertEqual(written["nonce"], "n99")

            # CLI launch-choices subcommand (including --variant and --place/--variant compatibility)
            spec = importlib.util.spec_from_file_location("launcher_cli_lc", str(ROOT / "scripts" / "launcher.py"))
            cli = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cli)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli.main([
                    "launch-choices", "--starfield", str(self.game), "--mode", "warfare",
                    "--survival", "on", "--place", "gunners_plaza", "--nonce", "cli77", "--write", "--json",
                ])
            self.assertEqual(rc, 0)
            rep = json.loads(out.getvalue())
            self.assertEqual(rep["choices"]["schema_version"], 2)
            self.assertEqual(rep["choices"]["start_variant"], "none")
            self.assertEqual(rep["choices"]["place_id"], "gunners_plaza")
            self.assertEqual(rep["choices"]["min_difficulty"], 1)
            self.assertEqual(
                launch_choices.read_launch_choices(launch_choices.default_launch_choices_path())["place_id"],
                "gunners_plaza",
            )

            out_story = io.StringIO()
            with redirect_stdout(out_story):
                rc_s = cli.main([
                    "launch-choices", "--starfield", str(self.game), "--mode", "story",
                    "--variant", "quick", "--survival", "off", "--nonce", "cli78", "--write", "--json",
                ])
            self.assertEqual(rc_s, 0)
            rep_s = json.loads(out_story.getvalue())
            self.assertEqual(rep_s["choices"]["schema_version"], 2)
            self.assertEqual(rep_s["choices"]["place_id"], "fo4_vault111")
            self.assertEqual(rep_s["choices"]["start_variant"], "quick")
            self.assertEqual(rep_s["choices"]["start_place_row"], 0)

            rc_bad_var = cli.main([
                "launch-choices", "--starfield", str(self.game), "--mode", "story",
                "--place", "fo4_vault111", "--variant", "normal",
            ])
            self.assertEqual(rc_bad_var, 2)

            # Unticking FO4TerrainCore.esm refuses warfare play cleanly before start_game
            fake.entries = [(p, p != "FO4TerrainCore.esm") for p in ALL_REQ_PLUGINS]
            with self.assertRaisesRegex(ValueError, "FO4TerrainCore.esm"):
                crashwatch.play(vals, str(self.game), system=fake, say=said.append)

    def test_cpp_setup_places_launch_choices_f2_guards_f11_difficulty_and_consume_delete(self):
        cxx = shutil.which("cl") or shutil.which("g++") or shutil.which("clang++")
        if not cxx:
            self.skipTest("no host C++ compiler (cl/g++/clang++) on PATH")
        now_epoch = int(time.time())
        entries = [(p, True) for p in ALL_REQ_PLUGINS]
        vals = settings.defaults()
        vals.update({"start.mode": "warfare", "start.survival": True, "start.place": "raiders_corvega"})
        payload = launch_choices.resolve_and_build_launch_choices(
            vals,
            starfield_dir=str(self.game),
            entries=entries,
            nonce="cpp_sync_9",
            created_at=now_epoch,
            strict_session=True,
        )
        choices_p = self.local / "FO4SF" / "launch_choices.json"
        launch_choices.write_launch_choices(str(choices_p), payload)

        # Negative payloads: Story != available table / missing plugin / schema_version=1 / mismatched start_variant / empty nonce / stale timestamp
        bad_p = self.local / "FO4SF" / "bad_choices.json"
        bad_payload = dict(payload, mode="story", game_mode=1, story_id="fo3_cw", story_choice_idx=1, start_variant="quick", place_id="fo3_vault101")
        bad_p.write_text(json.dumps(bad_payload), encoding="utf-8")

        bad_nonce_p = self.local / "FO4SF" / "bad_nonce.json"
        bad_nonce_p.write_text(json.dumps(dict(payload, nonce="")), encoding="utf-8")

        stale_p = self.local / "FO4SF" / "stale_choices.json"
        stale_p.write_text(json.dumps(dict(payload, created_at=now_epoch - 30000)), encoding="utf-8")

        v1_p = self.local / "FO4SF" / "v1_choices.json"
        v1_p.write_text(json.dumps(dict(payload, schema_version=1)), encoding="utf-8")

        prewar_plugins = ALL_REQ_PLUGINS + ("FO4SFPrewar.esm", "FO4SFPrewar_Sanctuary.esm")
        prewar_places = {
            "markers": {"FO4SF_PrewarHouseSpawnMarker", "FO4Core_CommonwealthMapMarkerSanctuary", "FO4Core_CommonwealthAnchor"},
            "interior_cells": {"FO4Port_Vault111Cryo"},
            "exterior_cells": {(0, -1), (-12, 12), (-2, -11), (-6, 5)},
        }
        prewar_vals = dict(settings.defaults(), **{"start.mode": "story", "start.variant": "normal"})
        prewar_payload = launch_choices.resolve_and_build_launch_choices(
            prewar_vals,
            loaded_plugins=prewar_plugins,
            loaded_places=prewar_places,
            nonce="prewar_cpp_1",
            created_at=now_epoch,
            strict_session=True,
        )
        prewar_p = self.local / "FO4SF" / "prewar_choices.json"
        launch_choices.write_launch_choices(str(prewar_p), prewar_payload)

        prewar_bad_var_p = self.local / "FO4SF" / "prewar_bad_var.json"
        prewar_bad_var_p.write_text(json.dumps(dict(prewar_payload, start_variant="quick")), encoding="utf-8")

        sp_copy_p = self.local / "FO4SF" / "FO4SFStartPlaces.json"
        sp_copy_p.write_text(Path(sp.START_PLACES_JSON).read_text(encoding="utf-8"), encoding="utf-8")
        sp_disabled_obj = json.loads(Path(sp.START_PLACES_JSON).read_text(encoding="utf-8"))
        for row in sp_disabled_obj["places"]:
            if row["id"] == "fo4_prewar_sanctuary":
                row["available"] = False
                row["unavailable_reason"] = "Disabled for test"
        sp_disabled_p = self.local / "FO4SF" / "FO4SFStartPlaces_disabled.json"
        sp_disabled_p.write_text(json.dumps(sp_disabled_obj), encoding="utf-8")

        cpp_src = self.root / "cpp_lc_check.cpp"
        exe = self.root / ("cpp_lc_check.exe" if sys.platform == "win32" else "cpp_lc_check")
        hdr = (ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "setup_places.h").as_posix()
        cpp_src.write_text(
            f"""#include <cassert>
#include <filesystem>
#include <iostream>
#include <string>
#include <vector>
#include "{hdr}"
int main(int argc, char** argv) {{
    using namespace fo4sf::setup;
    const std::int64_t nowEpoch = {now_epoch};
    LaunchChoicesPayload good;
    assert(LoadLaunchChoicesFile(argv[1], good, nowEpoch));
    assert(good.valid && good.schemaVersion == 2 && good.modeVal == 2 && good.modeTag == "warfare");
    assert(good.startVariant == "none");
    assert(good.survivalStart == 1 && good.survivalLocked == 1);
    assert(good.warfareFactionSlot == 7 && good.warfareStartIdx == 2);
    assert(good.placeId == "raiders_corvega" && good.startPlaceRow == 3);
    assert(good.minDifficulty == 2 && ResolveLaunchMinDifficulty(good) == 2);
    assert(good.nonce == "cpp_sync_9");

    // F11 fallback lookup when min_difficulty field omitted in JSON
    LaunchChoicesPayload noDiff = good;
    noDiff.minDifficulty = -1;
    assert(ResolveLaunchMinDifficulty(noDiff) == 2);

    LaunchChoicesPayload bad;
    assert(!LoadLaunchChoicesFile(argv[2], bad, nowEpoch));  // fo3_vault101 unavailable in table
    assert(!LoadLaunchChoicesFile(argv[4], bad, nowEpoch));  // empty nonce rejected
    assert(!LoadLaunchChoicesFile(argv[5], bad, nowEpoch));  // stale created_at rejected
    assert(!LoadLaunchChoicesFile(argv[6], bad, nowEpoch));  // schema_version=1 rejected

    // Real start_places.json verification: fo4_prewar_sanctuary accepted when prewar plugins loaded, refused otherwise
    bool fromFile = false;
    auto tableRows = LoadStartPlacesFileOrFallback(argv[7], fromFile);
    assert(fromFile);
    const std::vector<std::string> withPrewarPlugins = {{
        "Starfield.esm", "FO4Port.esm", "FO4TerrainCore.esm",
        "FO4SFPrewar_Sanctuary.esm", "FO4SFPrewar.esm", "FO4SFNewGame.esm", "FO4SFCoreValues.esm"
    }};
    const std::vector<std::string> noPrewarPlugins = {{
        "Starfield.esm", "FO4Port.esm", "FO4TerrainCore.esm", "FO4SFNewGame.esm", "FO4SFCoreValues.esm"
    }};
    LaunchChoicesPayload pwGood;
    std::string reason;
    assert(LoadLaunchChoicesFile(argv[8], tableRows, withPrewarPlugins, pwGood, nowEpoch, 21600, true, &reason));
    assert(pwGood.valid && pwGood.schemaVersion == 2 && pwGood.placeId == "fo4_prewar_sanctuary");
    assert(pwGood.startVariant == "normal" && pwGood.startPlaceRow == 0);

    LaunchChoicesPayload pwRefused;
    assert(!LoadLaunchChoicesFile(argv[8], tableRows, noPrewarPlugins, pwRefused, nowEpoch, 21600, true, &reason));
    assert(reason.find("missing_plugin:") != std::string::npos);

    assert(!LoadLaunchChoicesFile(argv[9], tableRows, withPrewarPlugins, pwRefused, nowEpoch, 21600, true, &reason));
    assert(reason == "start_variant_mismatch");

    bool disFromFile = false;
    auto disRows = LoadStartPlacesFileOrFallback(argv[10], disFromFile);
    assert(disFromFile);
    assert(!LoadLaunchChoicesFile(argv[8], disRows, withPrewarPlugins, pwRefused, nowEpoch, 21600, true, &reason));
    assert(reason == "row_unavailable");

    // F2 guard state machine: genuine New Game hydrates; loaded save (even with StartChoiceDone==0) NEVER hydrates!
    LaunchChoicesGuardState st;
    st.hasPayload = true;
    st.payloadValid = true;
    st.payloadFresh = true;
    st.loadGameSeen = false;
    st.mainMenuOpen = false;
    st.pauseMenuOpen = false;
    st.newGameQuestResolved = true;
    st.handshakeRequested = true;
    st.startChoiceDone = 0.0f;
    st.gameDaysPassed = 0.0f;
    st.playerLevel = 1;
    assert(EvaluateLaunchChoicesHydration(st) == LaunchHydrationDecision::kHydrateNow);

    // Waiting while MainMenu is open or before New Game quest handshake pulses -1.0
    auto waitMain = st;
    waitMain.mainMenuOpen = true;
    assert(EvaluateLaunchChoicesHydration(waitMain) == LaunchHydrationDecision::kWait);

    auto waitNoHandshake = st;
    waitNoHandshake.handshakeRequested = false;
    assert(EvaluateLaunchChoicesHydration(waitNoHandshake) == LaunchHydrationDecision::kWait);

    // F2 CRITICAL: Loaded save MUST return kDisarmConsume even if StartChoiceDone < 0.5!
    auto loadSave = st;
    loadSave.loadGameSeen = true;
    loadSave.startChoiceDone = 0.0f;
    loadSave.handshakeRequested = false;
    assert(EvaluateLaunchChoicesHydration(loadSave) == LaunchHydrationDecision::kDisarmConsume);

    auto loadEvenIfHandshake = st;
    loadEvenIfHandshake.loadGameSeen = true;
    assert(EvaluateLaunchChoicesHydration(loadEvenIfHandshake) == LaunchHydrationDecision::kDisarmConsume);

    auto oldSaveDays = st;
    oldSaveDays.gameDaysPassed = 1.2f;
    assert(EvaluateLaunchChoicesHydration(oldSaveDays) == LaunchHydrationDecision::kDisarmConsume);

    auto leveledSave = st;
    leveledSave.playerLevel = 4;
    assert(EvaluateLaunchChoicesHydration(leveledSave) == LaunchHydrationDecision::kDisarmConsume);

    // Consume-and-delete removes launch_choices.json immediately and idempotently
    assert(std::filesystem::exists(argv[1]));
    assert(ConsumeLaunchChoicesFile(argv[1]));
    assert(!std::filesystem::exists(argv[1]));
    assert(ConsumeLaunchChoicesFile(argv[1]));

    assert(WriteStartReadyAtomic(argv[3], good.nonce, "post_data_load", 4242));
    std::cout << "cpp_launch_choices_ok\\n";
    return 0;
}}
""",
            encoding="utf-8",
        )
        is_msvc = Path(cxx).stem.lower() == "cl"
        if is_msvc:
            cmd = [cxx, "/nologo", "/std:c++20", "/EHsc", str(cpp_src), f"/Fe:{exe}", f"/Fo:{self.root / 'lc.obj'}"]
        else:
            cmd = [cxx, "-std=c++20", str(cpp_src), "-o", str(exe)]
        comp = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(comp.returncode, 0, comp.stdout + "\n" + comp.stderr)
        run = subprocess.run(
            [
                str(exe),
                str(choices_p),
                str(bad_p),
                str(self.local / "FO4SF"),
                str(bad_nonce_p),
                str(stale_p),
                str(v1_p),
                str(sp_copy_p),
                str(prewar_p),
                str(prewar_bad_var_p),
                str(sp_disabled_p),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(run.returncode, 0, run.stdout + "\n" + run.stderr)
        self.assertIn("cpp_launch_choices_ok", run.stdout)
        self.assertFalse(choices_p.exists())

        sig_path = str(self.local / "FO4SF" / "start_ready.json")
        ok, info = start_cover.read_ready_signal(sig_path, expected_nonce="cpp_sync_9")
        self.assertTrue(ok)
        self.assertEqual(info["stage"], "post_data_load")
        self.assertEqual(info["pid"], 4242)
        ok_bad, _ = start_cover.read_ready_signal(sig_path, expected_nonce="wrong")
        self.assertFalse(ok_bad)


if __name__ == "__main__":
    unittest.main()
