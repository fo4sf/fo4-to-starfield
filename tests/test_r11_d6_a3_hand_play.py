"""Offline cross-OS tests for Round 11 Slice W5: D6 measured-speed walk table, overshoot margins, extended place legs & A3 Vault exit hand-play proof."""
from __future__ import annotations

import json
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[1]
NEWGAME_DIR = REPO_ROOT / "scripts" / "newgame"
SRC_DIR = REPO_ROOT / "src"
for _p in (str(NEWGAME_DIR), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import walk_headings as wh  # noqa: E402
from fo4sf.planet.esm import ESM, HEADER_FORM_VERSION, HEDR_VERSION, Record, group_bytes, zbytes  # noqa: E402

WALK_SCRIPT = NEWGAME_DIR / "walk_headings.py"
NEWGAME_PSC = NEWGAME_DIR / "FO4SF_NewGameQuest.psc"
WALK_DOC = REPO_ROOT / "docs" / "testing" / "console-free-walk-list.md"

DRIVE_PATH_RX = re.compile(r"\b[A-Za-z]:[\\/]")
FORBIDDEN_MOD_PATTERNS = (
    re.compile(r"\b" + ("UF" + "O4P") + r"\b", re.I),
    re.compile(r"\b" + ("Unofficial" + r"\s+" + "Fallout") + r"\b", re.I),
    re.compile(r"\b" + ("Yuki" + "chigai" + "|" + "Y" + "UP") + r"\b", re.I),
    re.compile(r"\b" + ("GAM" + "MA") + r"\b", re.I),
    re.compile(r"\b" + ("Buff" + "out") + r"\b", re.I),
)


def _write_synthetic_museum_navm_esm(
    path: Path,
    quad_local: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
) -> None:
    """Build a minimal Fallout4-style TES4 plugin with CELL 0x017DF7 (ConcordMuseum01) and a 2-triangle v15 NAVM."""
    fo4_verts = [
        (p[0] / wh.FO4_TO_SF_SCALE, p[1] / wh.FO4_TO_SF_SCALE, p[2] / wh.FO4_TO_SF_SCALE)
        for p in quad_local
    ]
    nvnm = bytearray(struct.pack("<5I", 15, 0xA5E9A03C, 0x00000000, 0x00017DF7, len(fo4_verts)))
    for v in fo4_verts:
        nvnm += struct.pack("<3f", *v)
    nvnm += struct.pack("<I", 2)
    nvnm += struct.pack("<6Hf5B", 0, 1, 2, 0xFFFF, 1, 0xFFFF, 0.0, 0, 0, 0, 0, 0)
    nvnm += struct.pack("<6Hf5B", 0, 2, 3, 0, 0xFFFF, 0xFFFF, 0.0, 0, 0, 0, 0, 0)

    cell_rec = Record(b"CELL", 0x00017DF7, [(b"EDID", zbytes("ConcordMuseum01"))])
    navm_rec = Record(b"NAVM", 0x00197BB0, [(b"NVNM", bytes(nvnm))])
    cell_children = group_bytes(struct.pack("<I", 0x00017DF7), navm_rec.to_bytes(compress=False), gtype=6)
    top = group_bytes("CELL", cell_rec.to_bytes(compress=False) + cell_children, gtype=0)
    hsubs = [(b"HEDR", struct.pack("<fII", HEDR_VERSION, 3, 0x001000))]
    tes4 = Record(b"TES4", 0, hsubs, ESM, 0, HEADER_FORM_VERSION, 0)
    path.write_bytes(tes4.to_bytes(compress=False) + top)


def _write_synthetic_quest_esm(path: Path, quests: list[tuple[int, str, list[tuple[int, str, list[int]]]]]) -> None:
    """Build a minimal Starfield-style TES4 plugin with QUST QOBJ/NNAM/QSTA subrecords."""
    stream = bytearray()
    for qid, edid, objs in quests:
        subs = [(b"EDID", zbytes(edid))]
        for oidx, otext, aliases in objs:
            subs.append((b"QOBJ", struct.pack("<H", oidx)))
            subs.append((b"NNAM", zbytes(otext)))
            for aid in aliases:
                subs.append((b"QSTA", struct.pack("<iI", aid, 0)))
        stream += Record(b"QUST", qid, subs).to_bytes(compress=False)
    top = group_bytes("QUST", bytes(stream), gtype=0)
    hsubs = [
        (b"HEDR", struct.pack("<fII", HEDR_VERSION, len(quests) + 1, 0x001000)),
        (b"MAST", zbytes("Starfield.esm")),
    ]
    tes4 = Record(b"TES4", 0, hsubs, ESM, 0, HEADER_FORM_VERSION, 0)
    path.write_bytes(tes4.to_bytes(compress=False) + top)


def _write_synthetic_v111_port_esm(path: Path, door_locks: dict[int, tuple[int, bool]]) -> None:
    """Build a minimal FO4Port-style plugin with FO4Port_Vault111Cryo and its 4 corridor/gear door REFRs."""
    cell_rec = Record(b"CELL", 0x010011F3, [(b"EDID", zbytes("FO4Port_Vault111Cryo"))])
    child_stream = bytearray()
    for lid, (lock_lvl, is_open) in door_locks.items():
        subs = [(b"DATA", struct.pack("<6f", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))]
        if lock_lvl > 0:
            subs.append((b"XLOC", struct.pack("<B3xI4x", lock_lvl, 0)))
        if is_open:
            subs.append((b"ONAM", b""))
        child_stream += Record(b"REFR", 0x01000000 | lid, subs).to_bytes(compress=False)
    cell_children = group_bytes(struct.pack("<I", 0x010011F3), bytes(child_stream), gtype=6)
    top = group_bytes("CELL", cell_rec.to_bytes(compress=False) + cell_children, gtype=0)
    hsubs = [
        (b"HEDR", struct.pack("<fII", HEDR_VERSION, len(door_locks) + 2, 0x001000)),
        (b"MAST", zbytes("Starfield.esm")),
    ]
    tes4 = Record(b"TES4", 0, hsubs, ESM, 0, HEADER_FORM_VERSION, 0)
    path.write_bytes(tes4.to_bytes(compress=False) + top)


def _write_synthetic_exitlift_esm(path: Path, full_name: str | None = None) -> None:
    """Build a minimal FO4SFExitLift-style plugin with ACTI 0x0100E0E6 (optional FULL subrecord)."""
    subs = [(b"EDID", zbytes("FO4Port_acti_0244ef_fallout4"))]
    if full_name is not None:
        subs.append((b"FULL", zbytes(full_name)))
    top = group_bytes("ACTI", Record(b"ACTI", 0x0100E0E6, subs).to_bytes(compress=False), gtype=0)
    hsubs = [
        (b"HEDR", struct.pack("<fII", HEDR_VERSION, 2, 0x001000)),
        (b"MAST", zbytes("Starfield.esm")),
    ]
    tes4 = Record(b"TES4", 0, hsubs, ESM, 0, HEADER_FORM_VERSION, 0)
    path.write_bytes(tes4.to_bytes(compress=False) + top)


class R11D6AndA3HandPlayTests(unittest.TestCase):
    def test_d6_measured_run_speed_parameter_and_exact_targets(self) -> None:
        self.assertAlmostEqual(wh.RUN_SPEED_MPS, 4.80, places=2)
        self.assertAlmostEqual(wh.MEASURED_RUN_SPEED_MIN_MPS, 4.60, places=2)
        self.assertAlmostEqual(wh.MEASURED_RUN_SPEED_MAX_MPS, 5.00, places=2)

        rows_48 = {r["seg_id"]: r for r in wh.compute_route_rows(run_speed_mps=4.8)}
        rows_50 = {r["seg_id"]: r for r in wh.compute_route_rows(run_speed_mps=5.0)}
        rows_46 = {r["seg_id"]: r for r in wh.compute_route_rows(run_speed_mps=4.6)}

        # 5a (33.45 m, 210.8 deg confirmed exact in 2g): 33.45 / 4.8 = 6.97 s (not old 9.04 s at 3.7 m/s)
        self.assertAlmostEqual(rows_48["5a"]["heading_deg"], 210.77, places=1)
        self.assertAlmostEqual(rows_48["5a"]["hold_w_run_sec"], 6.97, places=2)
        self.assertLess(rows_50["5a"]["hold_w_run_sec"], rows_48["5a"]["hold_w_run_sec"])
        self.assertGreater(rows_46["5a"]["hold_w_run_sec"], rows_48["5a"]["hold_w_run_sec"])
        self.assertEqual(rows_48["5a"]["target"], rows_50["5a"]["target"])
        self.assertEqual(rows_48["5a"]["heading_deg"], rows_50["5a"]["heading_deg"])

        # CLI --run-speed honors custom speed parameter
        p_json = subprocess.run(
            [sys.executable, str(WALK_SCRIPT), "json", "--scope", "opening", "--run-speed", "5.0"],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(p_json.returncode, 0, p_json.stderr)
        data = json.loads(p_json.stdout)
        self.assertAlmostEqual(data["run_speed_mps"], 5.0, places=2)
        self.assertEqual(data["measured_run_speed_range_mps"], [4.6, 5.0])
        seg_5a = next(r for r in data["segments"] if r["seg_id"] == "5a")
        self.assertAlmostEqual(seg_5a["hold_w_run_sec"], 6.69, places=2)

    def test_d6_safe_overshoot_margins_and_hazards_on_every_segment(self) -> None:
        rows = wh.compute_route_rows(wh.ALL_WALK_SEGMENTS)
        self.assertEqual(len(rows), 97)
        by_id = {r["seg_id"]: r for r in rows}

        for r in rows:
            self.assertGreater(r["safe_overshoot_m"], 0.0, f"{r['seg_id']} missing positive safe_overshoot_m")
            self.assertTrue(r["overshoot_hazard"].strip(), f"{r['seg_id']} missing overshoot_hazard description")

        # Critical physical overshoot guardrails
        self.assertLessEqual(by_id["1b"]["safe_overshoot_m"], 1.5)
        self.assertIn("0200126E", by_id["1b"]["overshoot_hazard"])
        self.assertLessEqual(by_id["1c"]["safe_overshoot_m"], 1.5)
        self.assertIn("02001234", by_id["1c"]["overshoot_hazard"])
        self.assertLessEqual(by_id["3c"]["safe_overshoot_m"], 2.0)
        self.assertIn("railing", by_id["3c"]["overshoot_hazard"].lower())
        self.assertLessEqual(by_id["3d"]["safe_overshoot_m"], 1.5)
        self.assertIn("house wall", by_id["5a"]["overshoot_hazard"].lower())
        self.assertIn("still 14", by_id["5b"]["overshoot_hazard"].lower())
        self.assertLessEqual(by_id["5c"]["safe_overshoot_m"], 2.0)
        self.assertIn("parapet", by_id["9e"]["overshoot_hazard"].lower())

    def test_d6_extended_place_legs_sanctuary_and_museum_continuity(self) -> None:
        cont = wh.check_route_continuity(wh.ALL_WALK_SEGMENTS)
        self.assertTrue(cont["pass"], cont["issues"])
        self.assertEqual(cont["segment_count"], 97)
        self.assertEqual(set(cont["leg_totals_m"].keys()), {"L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9"})

        ext = {s.seg_id: s for s in wh.EXTENDED_PLACE_WALK_SEGMENTS}
        # L6 Sanctuary houses loop starts/ends at Codsworth and visits Player House, Search Houses 1 & 2, Workbench
        self.assertEqual(ext["6a"].start, (-2344.709, -1408.163, 111.734))
        self.assertEqual(ext["6t"].target, (-2344.709, -1408.163, 111.734))
        self.assertEqual(ext["6g"].target, (-2313.440, -1372.020, 112.670))
        self.assertEqual(ext["6l"].target, (-2285.440, -1431.280, 111.750))
        self.assertIn("04005C50", ext["6q"].action_at_target)

        # L7 Museum lobby -> Preston room; L8 Preston room -> Basement Terminal & Security Gate; L9 -> Roof PA & Minigun
        self.assertEqual(ext["7a"].start, (8.057, 0.000, -0.914))
        self.assertEqual(ext["7v"].target, (8.500, -5.000, 9.140))
        self.assertEqual(ext["8a"].start, (8.500, -5.000, 9.140))
        self.assertIn("020125AB", ext["8o"].action_at_target)
        self.assertIn("02013042", ext["8p"].action_at_target)
        self.assertIn("02012585", ext["8p"].action_at_target)
        self.assertEqual(ext["9b"].zone, "interior_museum")
        self.assertEqual(ext["9c"].zone, "exterior_commonwealth")
        self.assertIn("04008913", ext["9c"].action_at_target)
        self.assertIn("04005119", ext["9e"].action_at_target)

    def test_museum_3d_navm_verifier_passes_and_rejects_off_navmesh_or_wrong_floor(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fo4_syn = Path(td) / "Fallout4_museum_syn.esm"
            _write_synthetic_museum_navm_esm(
                fo4_syn,
                (
                    (0.0, -10.0, 9.14),
                    (12.0, -10.0, 9.14),
                    (12.0, 0.0, 9.14),
                    (0.0, 0.0, 9.14),
                ),
            )
            on_seg = wh.WalkSegment(
                "L7", "7_ok", "interior_museum", "On 3rd-floor navmesh",
                (2.0, -7.0, 9.14), (8.5, -5.0, 9.14), 0.0, "ok", "museum_preston_room",
            )
            r_ok = wh.verify_museum_navm_segments(fo4_syn, segments=(on_seg,), step_m=0.5)
            self.assertTrue(r_ok["pass"], r_ok["issues"])
            self.assertEqual(r_ok["hits"], r_ok["sampled_points"])

            # Same XY but wrong floor (basement z=-3.5 vs 3rd-floor navmesh z=+9.14) MUST FAIL
            wrong_floor = wh.WalkSegment(
                "L8", "8_wrong_z", "interior_museum", "Wrong floor Z",
                (2.0, -7.0, -3.50), (8.5, -5.0, -3.50), 0.0, "bad", "museum_basement_terminal",
            )
            r_bad_z = wh.verify_museum_navm_segments(fo4_syn, segments=(wrong_floor,), step_m=0.5)
            self.assertFalse(r_bad_z["pass"])
            self.assertTrue(any("8_wrong_z" in e for e in r_bad_z["issues"]))

            # Off-navmesh XY MUST FAIL
            off_xy = wh.WalkSegment(
                "L7", "7_off_xy", "interior_museum", "Off XY navmesh",
                (2.0, -7.0, 9.14), (25.0, -5.0, 9.14), 0.0, "bad", "museum_preston_room",
            )
            r_bad_xy = wh.verify_museum_navm_segments(fo4_syn, segments=(off_xy,), step_m=0.5)
            self.assertFalse(r_bad_xy["pass"])
            self.assertTrue(any("7_off_xy" in e for e in r_bad_xy["issues"]))

    def test_a3_newgame_lift_control_onactivate_contract_and_regression_guard(self) -> None:
        psc = NEWGAME_PSC.read_text(encoding="utf-8")
        # 2g auto-platform path preserved
        self.assertIn("bool onPlatform = Near(player, PlatformX, PlatformY, PlatformZ, PlatformRadius)", psc)
        self.assertIn("Function PromptVaultExitLift(Actor player)", psc)
        self.assertIn('Trace("lift platform waiting cage_door=open")', psc)
        self.assertIn('Trace("elevator prompt button=" + button)', psc)
        # R11 A3 direct lift control activation wired safely
        self.assertIn('RegisterForRemoteEvent(liftWatchedRef, "OnActivate")', psc)
        self.assertIn('Trace("lift control registered ref="', psc)
        self.assertIn("Function HandleLiftControlActivate(Actor player, ObjectReference akSender)", psc)
        self.assertIn('Trace("lift control refused: cog_door_closed")', psc)
        self.assertIn('Trace("lift control outside_platform")', psc)
        self.assertIn('Trace("lift control activated ref=" + akSender)', psc)
        # Safety: direct activation only re-opens prompt when player is inside PlatformRadius
        fn_start = psc.index("Function HandleLiftControlActivate(")
        fn_body = psc[fn_start : psc.index("EndFunction", fn_start)]
        self.assertIn("if !Near(player, PlatformX, PlatformY, PlatformZ, PlatformRadius)", fn_body)
        self.assertLess(fn_body.index("outside_platform"), fn_body.index("PromptVaultExitLift(player)"))

    def test_a3_audit_vault111_handplay_synthetic_and_honest_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            ng_esm = tmp / "FO4SFNewGame.esm"
            ms_esm = tmp / "FO4SFMission.esm"
            port_ok = tmp / "FO4Port_ok.esm"
            port_locked = tmp / "FO4Port_locked.esm"
            exitlift_esm = tmp / "FO4SFExitLift.esm"

            _write_synthetic_quest_esm(ng_esm, [
                (0x03000800, "FO4SF_NewGame", [(10, "Leave Vault 111", [])]),
            ])
            _write_synthetic_quest_esm(ms_esm, [
                (0x03000816, "FO4SF_Codsworth01", [(10, "Go home", [0])]),
                (0x03000800, "FO4SF_Min00", [(10, "Find the Last Minutemen", [0]), (85, "Kill the Raiders", []), (86, "Talk to Preston Garvey", [0])]),
            ])
            _write_synthetic_v111_port_esm(port_ok, {
                0x00126E: (0, False),
                0x001234: (0, False),
                0x001608: (0, True),
                0x00126D: (0, False),
            })
            _write_synthetic_exitlift_esm(exitlift_esm, full_name=None)

            res = wh.audit_vault111_handplay(newgame_esm=ng_esm, mission_esm=ms_esm, port_esm=port_ok, exitlift_esm=exitlift_esm)
            self.assertTrue(res["pass"], res["issues"])
            self.assertTrue(res["offline_only_unproven_in_game"])
            self.assertTrue(res["first_person_reach"]["pipboy_0A00080F"]["within_2m_reach"])
            self.assertTrue(res["first_person_reach"]["console_0A000819"]["within_2m_reach"])
            self.assertTrue(res["lift_platform"]["programmatic_lift_onactivate_guard_wired"])
            self.assertEqual(res["lift_platform"]["lift_base_0x0100E0E6_full_name"], "")
            self.assertFalse(res["lift_platform"]["lift_base_has_full_name"])
            self.assertIn("0x08C94A", res["lift_platform"]["retrigger_after_stay"])
            self.assertIn("asked=false", res["lift_platform"]["retrigger_after_stay"])
            self.assertEqual(len(res["vault111_doors"]), 4)
            self.assertTrue(any("FO4SF_NewGame Obj 10" in g for g in res["known_offline_gaps"]))
            self.assertGreaterEqual(len(res["only_game_can_prove"]), 5)

            # Negative mutation: lock Door 1 (0200126E) -> hand-play audit MUST fail
            _write_synthetic_v111_port_esm(port_locked, {
                0x00126E: (25, False),
                0x001234: (0, False),
                0x001608: (0, True),
                0x00126D: (0, False),
            })
            res_bad = wh.audit_vault111_handplay(newgame_esm=ng_esm, mission_esm=ms_esm, port_esm=port_locked)
            self.assertFalse(res_bad["pass"])
            self.assertTrue(any("door_1_V111Door01" in e for e in res_bad["issues"]))

    def test_console_free_walk_list_doc_sync_handplay_steps_and_hygiene(self) -> None:
        doc = WALK_DOC.read_text(encoding="utf-8")
        # Both opening (34 rows) and extended (63 rows) generated tables must match doc verbatim
        for scope in ("opening", "extended"):
            p_tbl = subprocess.run(
                [sys.executable, str(WALK_SCRIPT), "table", "--scope", scope],
                capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(p_tbl.returncode, 0, p_tbl.stderr)
            for line in p_tbl.stdout.splitlines():
                self.assertIn(line, doc, f"Missing {scope} table line in console-free-walk-list.md: {line}")

        # Section 5 HAND-PLAY steps must be pure keyboard+mouse (zero console commands)
        hp_marker = "## 5. Owner's Plain Console-Free Vault Exit `HAND-PLAY` Steps (`A3`)"
        self.assertIn(hp_marker, doc)
        hp_start = doc.index(hp_marker)
        hp_end = doc.index("## 6. Remaining Diagnostic-Only Batches", hp_start)
        hp_section = doc[hp_start:hp_end]
        for step_num in range(1, 9):
            self.assertIn(f"\n{step_num}. ", hp_section, f"Missing HAND-PLAY step {step_num}")
        # R15 honesty: ACTI 0x0100E0E6 has no FULL name (no wall button), so HAND-PLAY Step 5 uses Stay->step out->step back in
        self.assertNotIn("press **`E`** on the elevator", hp_section)
        self.assertIn("step `~2 m` back out the open cage entrance", hp_section)
        for forbidden in ("moveto", "setpos", "bat ", "tgm", "coc "):
            self.assertNotIn(forbidden, hp_section.lower(), f"Console command {forbidden!r} leaked into HAND-PLAY steps")

        # Zero drive-path leaks and zero forbidden mod names across all W5 owned files
        for path in (WALK_SCRIPT, WALK_DOC, NEWGAME_PSC, HERE):
            txt = path.read_text(encoding="utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(txt), f"Drive path leak in {path.name}")
            for pat in FORBIDDEN_MOD_PATTERNS:
                self.assertIsNone(pat.search(txt), f"Forbidden mod name in {path.name}")


if __name__ == "__main__":
    unittest.main()
