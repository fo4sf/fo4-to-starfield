"""Offline verification tests for A7d Act II Glowing Sea (MQ204) & Molecular Level (MQ206) places and doors."""
from __future__ import annotations

import copy
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
TERRAIN_DIR = REPO_ROOT / "scripts" / "terrain"
SRC_DIR = REPO_ROOT / "src"
for _p in (str(TERRAIN_DIR), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import a7d_glowing_sea_places as a7d  # noqa: E402
from fo4sf.planet.esm import ESM, HEADER_FORM_VERSION, HEDR_VERSION, Record, group_bytes, zbytes  # noqa: E402

A7D_DOC = REPO_ROOT / "docs" / "quests" / "next-story-missions-a7d.md"
A7D_SCRIPT = TERRAIN_DIR / "a7d_glowing_sea_places.py"
DRIVE_PATH_RX = re.compile(r"\b[A-Za-z]:[\\/]")
FORBIDDEN_MOD_PATTERNS = (
    re.compile(r"\b" + ("UF" + "O4P") + r"\b", re.I),
    re.compile(r"\b" + ("Unofficial" + r"\s+" + "Fallout") + r"\b", re.I),
    re.compile(r"\b" + ("Yuki" + "chigai" + "|" + "Y" + "UP") + r"\b", re.I),
    re.compile(r"\b" + ("GAM" + "MA") + r"\b", re.I),
    re.compile(r"\b" + ("Buff" + "out") + r"\b", re.I),
)


def _write_synthetic_port_esm(
    path: Path,
    places: tuple[a7d.StagedPlaceSpec, ...] = a7d.A7D_STAGED_PLACES,
    omit_edids: set[str] | None = None,
    xtel_override: dict[str, int] | None = None,
) -> None:
    """Build a minimal valid TES4 plugin with CELL records + child REFR/XTEL records for offline binary tests."""
    omit = omit_edids or set()
    xov = xtel_override or {}
    cell_stream = bytearray()
    next_ref = 0x01090000
    rec_count = 0
    for spec in places:
        if spec.port_edid in omit:
            continue
        cell_rec = Record(b"CELL", spec.port_cell_id, [(b"EDID", zbytes(spec.port_edid))])
        cell_stream += cell_rec.to_bytes(compress=False)
        rec_count += 1
        xtel_n = xov.get(spec.port_edid, spec.expected_internal_xtel_count)
        child_stream = bytearray()
        for i in range(max(1, xtel_n)):
            subs = []
            if i < xtel_n:
                subs.append((b"XTEL", struct.pack("<I", next_ref + 1)))
            refr = Record(b"REFR", next_ref, subs)
            next_ref += 1
            child_stream += refr.to_bytes(compress=False)
            rec_count += 1
        # Cell children group (type 6) labelled with cell formid
        cell_stream += group_bytes(struct.pack("<I", spec.port_cell_id), bytes(child_stream), gtype=6)

    top_cell = group_bytes("CELL", bytes(cell_stream), gtype=0)
    hsubs = [
        (b"HEDR", struct.pack("<fII", HEDR_VERSION, rec_count + 1, 0x074CD3)),
        (b"MAST", zbytes("Starfield.esm")),
    ]
    tes4 = Record(b"TES4", 0, hsubs, ESM, 0, HEADER_FORM_VERSION, 0)
    path.write_bytes(tes4.to_bytes(compress=False) + top_cell)


def _write_synthetic_doors_json(path: Path, include_prydwen: bool = True, marker: str = "00E183") -> None:
    doors = []
    if include_prydwen:
        doors.append({
            "src": a7d.PRYDWEN_WIRED_DOOR["src"],
            "cell_edid": a7d.PRYDWEN_WIRED_DOOR["cell_edid"],
            "cell": a7d.PRYDWEN_WIRED_DOOR["cell_local_id"],
            "interior_door": a7d.PRYDWEN_WIRED_DOOR["interior_door"],
            "marker": marker,
            "return_destination": {
                "plugin": a7d.PRYDWEN_WIRED_DOOR["return_plugin"],
                "id": a7d.PRYDWEN_WIRED_DOOR["return_id"],
                "local": list(a7d.PRYDWEN_WIRED_DOOR["return_local"]),
                "merged": list(a7d.PRYDWEN_WIRED_DOOR["return_merged"]),
            },
        })
    path.write_text(json.dumps({"doors": doors}, indent=2), encoding="utf-8")


class A7dGlowingSeaPlacesTests(unittest.TestCase):
    def test_formid_disjointness_and_a5_act2_scan_window(self) -> None:
        res = a7d.check_formid_disjointness()
        self.assertTrue(res["pass"], res["issues"])
        self.assertEqual(res["a7d_range"], "0x000B10..0x000B6F")
        self.assertEqual(res["a5_act2_scan_window"], "0x000800..0x000BFF")
        self.assertEqual(res["issues"], [])

    def test_all_20_staged_cells_wired_prydwen_and_missing_transitions_cataloged(self) -> None:
        self.assertEqual(len(a7d.A7D_STAGED_PLACES), 20)
        by_edid = {p.fo4_edid: p for p in a7d.A7D_STAGED_PLACES}
        self.assertEqual(by_edid["VirgilsLab01"].port_cell_id, 0x01069B10)
        self.assertEqual(by_edid["GreenetechGenetics01"].port_cell_id, 0x01056471)
        self.assertEqual(by_edid["RailroadHQ01"].port_cell_id, 0x0103CC9F)
        self.assertEqual(by_edid["InstituteConcourse"].port_cell_id, 0x0103D252)
        self.assertEqual(by_edid["InstituteConcourse"].exterior_door_status, "scripted_relay")
        self.assertEqual(by_edid["PrydwenHull01"].port_cell_id, 0x01003846)
        self.assertEqual(by_edid["PrydwenHull01"].exterior_door_status, "wired")

        wired = [p.fo4_edid for p in a7d.A7D_STAGED_PLACES if p.exterior_door_status == "wired"]
        self.assertEqual(wired, ["PrydwenHull01"])
        unwired = {p.fo4_edid for p in a7d.A7D_STAGED_PLACES if p.exterior_door_status == "unwired"}
        for must_unwired in (
            "VirgilsLab01",
            "GreenetechGenetics01",
            "OldNorthChurch01",
            "GoodneighborTheMemoryDen",
            "BostonAirportRuins01",
        ):
            self.assertIn(must_unwired, unwired)

        missing_by_edid = {m.fo4_edid: m for m in a7d.A7D_MISSING_CELLS}
        self.assertEqual(missing_by_edid["ElevTransHiTechInstitute"].fo4_cell_id, 0x0021A107)
        self.assertEqual(missing_by_edid["ElevTransHiTechInstitute"].category, "transition_cell")
        self.assertEqual(missing_by_edid["MassFusion02Trans"].fo4_cell_id, 0x0014FC9B)
        self.assertEqual(missing_by_edid["MassFusion02Trans"].category, "transition_cell")

    def test_binary_staged_verifier_passes_and_catches_negative_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            esm_ok = tmp / "FO4Port.esm"
            doors_ok = tmp / "doors.json"
            _write_synthetic_port_esm(esm_ok)
            _write_synthetic_doors_json(doors_ok)

            res = a7d.verify_staged_interiors_b10(esm_ok, doors_ok)
            self.assertTrue(res["pass"], res["issues"])
            self.assertEqual(res["verified_present"], 20)
            self.assertTrue(res["prydwen_wired_door_ok"])
            self.assertIn("FO4Port_ElevTransHiTechInstitute", res["missing_cells_confirmed_absent"])
            self.assertIn("FO4Port_MassFusion02Trans", res["missing_cells_confirmed_absent"])

            # Mutation 1: missing VirgilsLab01 cell rejected
            esm_miss = tmp / "FO4Port_missing.esm"
            _write_synthetic_port_esm(esm_miss, omit_edids={"FO4Port_VirgilsLab01"})
            r_miss = a7d.verify_staged_interiors_b10(esm_miss, doors_ok)
            self.assertFalse(r_miss["pass"])
            self.assertTrue(any("FO4Port_VirgilsLab01" in e for e in r_miss["issues"]))

            # Mutation 2: broken internal XTEL link on InstituteConcourse rejected
            esm_xtel = tmp / "FO4Port_badxtel.esm"
            _write_synthetic_port_esm(esm_xtel, xtel_override={"FO4Port_InstituteConcourse": 2})
            r_xtel = a7d.verify_staged_interiors_b10(esm_xtel, doors_ok)
            self.assertFalse(r_xtel["pass"])
            self.assertTrue(any("FO4Port_InstituteConcourse" in e for e in r_xtel["issues"]))

            # Mutation 3: missing PrydwenHull01 wired door or wrong marker ID in doors.json rejected
            doors_bad = tmp / "doors_bad.json"
            _write_synthetic_doors_json(doors_bad, include_prydwen=False)
            r_door = a7d.verify_staged_interiors_b10(esm_ok, doors_bad)
            self.assertFalse(r_door["pass"])
            self.assertFalse(r_door["prydwen_wired_door_ok"])

            doors_bad_marker = tmp / "doors_bad_marker.json"
            _write_synthetic_doors_json(doors_bad_marker, include_prydwen=True, marker="009999")
            r_mk = a7d.verify_staged_interiors_b10(esm_ok, doors_bad_marker)
            self.assertFalse(r_mk["pass"])
            self.assertFalse(r_mk["prydwen_wired_door_ok"])

    def test_w6_normal_and_open_mode_pass_and_catch_removed_fallbacks(self) -> None:
        res = a7d.evaluate_a7d_missions()
        self.assertTrue(res["pass"], res)
        self.assertEqual(len(res["missions"]), 2)
        for m in res["missions"]:
            self.assertTrue(m["pass"], m)
            self.assertEqual(m["normal"]["unreachable"], [])
            self.assertEqual(m["normal"]["stuck"], [])
            self.assertEqual(m["open_mode"]["stuck"], [])

        # Mutation 1: drop dead-Virgil terminal fallback on MQ204 (50 -> 200)
        m1 = copy.deepcopy(list(a7d.A7D_NEXT_MISSIONS))
        m1[0]["transitions"] = [
            tr for tr in m1[0]["transitions"]
            if not (tr["from"] == 50 and tr["to"] == 200 and not tr.get("npc_gated", False))
        ]
        r1 = a7d.evaluate_a7d_missions(m1)
        self.assertTrue(r1["missions"][0]["normal"]["pass"])
        self.assertFalse(r1["missions"][0]["open_mode"]["pass"])
        self.assertIn(50, r1["missions"][0]["open_mode"]["stuck"])

        # Mutation 2: drop dead-Railroad TinkerTomScanner fallback on MQ206 (20 -> 65)
        m2 = copy.deepcopy(list(a7d.A7D_NEXT_MISSIONS))
        m2[1]["transitions"] = [
            tr for tr in m2[1]["transitions"]
            if not (tr["from"] == 20 and tr["to"] == 65)
        ]
        r2 = a7d.evaluate_a7d_missions(m2)
        self.assertFalse(r2["missions"][1]["open_mode"]["pass"])
        self.assertIn(20, r2["missions"][1]["open_mode"]["stuck"])

        # Mutation 3: drop solo self-build fallback on MQ206 (200 -> 300)
        m3 = copy.deepcopy(list(a7d.A7D_NEXT_MISSIONS))
        m3[1]["transitions"] = [
            tr for tr in m3[1]["transitions"]
            if not (tr["from"] == 200 and tr["to"] == 300 and not tr.get("npc_gated", False))
        ]
        r3 = a7d.evaluate_a7d_missions(m3)
        self.assertTrue(r3["missions"][1]["normal"]["pass"])
        self.assertFalse(r3["missions"][1]["open_mode"]["pass"])
        self.assertIn(200, r3["missions"][1]["open_mode"]["stuck"])

    def test_a5_tsv_rows_valid_and_rejects_bad_coords(self) -> None:
        rows = a7d.emit_a5_objective_tsv_rows()
        self.assertEqual(len(rows), 9)
        for row in rows:
            cols = row.split("\t")
            self.assertEqual(len(cols), 7, row)
            self.assertTrue(cols[0] in {"0x000B10", "0x000B30"})
            int(cols[1])
            x, y = float(cols[4]), float(cols[5])
            self.assertGreaterEqual(x, a7d.COMMONWEALTH_X_BOUNDS[0])
            self.assertLessEqual(x, a7d.COMMONWEALTH_X_BOUNDS[1])
            self.assertGreaterEqual(y, a7d.COMMONWEALTH_Y_BOUNDS[0])
            self.assertLessEqual(y, a7d.COMMONWEALTH_Y_BOUNDS[1])

        bad = copy.deepcopy(list(a7d.A7D_NEXT_MISSIONS))
        o0 = bad[0]["objectives"][0]
        bad[0]["objectives"] = ((o0[0], o0[1], float("nan"), o0[3], o0[4]),)
        with self.assertRaises(ValueError):
            a7d.emit_a5_objective_tsv_rows(bad)

    def test_cli_subcommands_audit_a7d_and_emit_tsv(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            esm_ok = tmp / "FO4Port.esm"
            doors_ok = tmp / "doors.json"
            _write_synthetic_port_esm(esm_ok)
            _write_synthetic_doors_json(doors_ok)

            p1 = subprocess.run(
                [sys.executable, str(A7D_SCRIPT), "audit-a7d", "--port-esm", str(esm_ok), "--doors-json", str(doors_ok)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(p1.returncode, 0, p1.stderr)
            data = json.loads(p1.stdout)
            self.assertTrue(data["pass"])
            self.assertEqual(len(data["staged_places"]), 20)
            self.assertTrue(data["staged_binary_verification"]["pass"])

            p2 = subprocess.run(
                [sys.executable, str(A7D_SCRIPT), "emit-tsv"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(p2.returncode, 0, p2.stderr)
            self.assertEqual(len([ln for ln in p2.stdout.splitlines() if ln.strip()]), 9)

    def test_p3_safe_batch_ids_have_zero_m_n_v(self) -> None:
        bat_ids = [b["bat_id"] for m in a7d.A7D_NEXT_MISSIONS for b in m["break_it_batches"]]
        self.assertEqual(len(bat_ids), 4)
        for bid in bat_ids:
            cmd = f"bat {bid}"
            for forbidden in ("m", "n", "v"):
                self.assertNotIn(forbidden, cmd.lower(), f"P3 violation in {cmd}")

    def test_doc_hygiene_canonical_header_and_zero_leaks(self) -> None:
        doc = A7D_DOC.read_text(encoding="utf-8")
        first_line = doc.splitlines()[0]
        self.assertIn("Titles:", first_line)
        self.assertIn("Modes:", first_line)
        self.assertIn("Track:", first_line)
        for req in (
            "prototype, offline",
            "OFFLINE ONLY — UNPROVEN IN GAME",
            "0x000B10",
            "0x000B30",
            "PrydwenHull01",
            "0x0045AD",
            "0x00E183",
            "0x0A774D",
            "ElevTransHiTechInstitute",
            "MassFusion02Trans",
            "Track 1",
            "Track 2",
            "Consolidated Owner Questions",
            "MOL-01",
            "MOL-02",
            "MOL-03",
            "GLOW-04",
            "MOL-05",
        ):
            self.assertIn(req, doc, f"Missing required content in A7d doc: {req}")

        for path in (A7D_DOC, A7D_SCRIPT, HERE):
            txt = path.read_text(encoding="utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(txt), f"Drive path leak in {path.name}")
            for pat in FORBIDDEN_MOD_PATTERNS:
                self.assertIsNone(pat.search(txt), f"Forbidden mod name in {path.name}")


if __name__ == "__main__":
    unittest.main()
