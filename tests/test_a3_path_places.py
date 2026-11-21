"""Offline unit, synthetic-port patch, W6 reachability, and doc-guard tests for A3 Places + A4 Next Missions."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[1]

A3_SCRIPT = REPO_ROOT / "scripts" / "terrain" / "a3_path_places.py"
VMAD_SCRIPT = REPO_ROOT / "scripts" / "terrain" / "vmad_patch.py"
LOAD_DOOR_PSC = REPO_ROOT / "scripts" / "door_bridge" / "FO4SF_LoadDoor.psc"
DOC_A3 = REPO_ROOT / "docs" / "quests" / "first-missions-places.md"
DOC_A4 = REPO_ROOT / "docs" / "quests" / "next-story-missions-a4.md"

sys.path.insert(0, str(REPO_ROOT / "scripts" / "terrain"))
sys.path.insert(0, str(REPO_ROOT / "src"))

_spec = importlib.util.spec_from_file_location("a3_path_places", A3_SCRIPT)
assert _spec is not None and _spec.loader is not None
a3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a3)

import vmad_patch  # noqa: E402

DRIVE_PATH_RX = re.compile(r"\b[A-Za-z]:[\\/]")
FENCED_BLOCK_RE = re.compile(r"```([A-Za-z0-9_-]*)\r?\n(.*?)```", re.S)
FORBIDDEN_MOD_PATTERNS = [
    re.compile(r"\b" + ("UF" + "O4P") + r"\b", re.I),
    re.compile(r"\b" + ("Unofficial" + r"\s+" + "Fallout") + r"\b", re.I),
    re.compile(r"\b" + ("Yuki" + "chigai" + "|" + "Y" + "UP") + r"\b", re.I),
    re.compile(r"\b" + ("GAM" + "MA") + r"\b", re.I),
    re.compile(r"\b" + ("Buff" + "out") + r"\b", re.I),
    re.compile(r"\b" + ("Role" + "players" + r"'?\s+" + "Alternate") + r"\b", re.I),
]


def _make_group(gtype: int, label_bytes: bytes, children_bytes: bytes) -> bytes:
    return struct.pack("<4sI4si8s", b"GRUP", 24 + len(children_bytes), label_bytes, gtype, b"\0" * 8) + children_bytes


def _make_record(sig: bytes, fid: int, flags: int, fields: list[tuple[bytes, bytes]], version: int = 0x0240) -> bytes:
    payload = b"".join(vmad_patch.encode_field(s, d) for s, d in fields)
    return struct.pack("<4sIIIHH4s", sig, len(payload), flags, fid, 0, version, b"\0\0\0\0") + payload


def _build_synthetic_port_esm(
    path: Path,
    cell_id: int,
    cell_edid: str,
    door_refs: list[int],
    extra_static_id: int,
    next_obj_id: int,
) -> None:
    """Build a minimal valid Starfield FO4Port.esm with 1 master (Starfield.esm), 1 CELL, and temporary door REFRs."""
    masters_idx = 1  # 1 master (Starfield.esm) -> own records carry prefix 0x01
    full_cell = (masters_idx << 24) | cell_id
    # TES4 header
    num_records = 1 + len(door_refs) + 1  # CELL + door REFRs + 1 untouched STAT/REFR
    hedr = struct.pack("<fII", 0.96, num_records, next_obj_id)
    tes4 = _make_record(
        b"TES4",
        0,
        1,  # Master flag
        [
            (b"HEDR", hedr),
            (b"CNAM", b"synthetic\0"),
            (b"MAST", b"Starfield.esm\0"),
            (b"DATA", struct.pack("<Q", 0)),
        ],
    )
    # CELL record
    cell_rec = _make_record(
        b"CELL",
        full_cell,
        0,
        [(b"EDID", (cell_edid + "\0").encode("ascii"))],
    )
    temp_children = []
    for did in door_refs:
        temp_children.append(
            _make_record(
                b"REFR",
                (masters_idx << 24) | did,
                0,
                [
                    (b"NAME", struct.pack("<I", 0x0000003B)),
                    (b"DATA", struct.pack("<6f", 1.0, 2.0, 3.0, 0.0, 0.0, 0.0)),
                ],
            )
        )
    # One untouched temporary REFR to prove byte-identical preservation
    temp_children.append(
        _make_record(
            b"REFR",
            (masters_idx << 24) | extra_static_id,
            0,
            [
                (b"NAME", struct.pack("<I", 0x0000003B)),
                (b"DATA", struct.pack("<6f", 9.0, 8.0, 7.0, 0.0, 0.0, 0.0)),
            ],
        )
    )
    temp_grp = _make_group(vmad_patch.GROUP_TEMPORARY, struct.pack("<I", full_cell), b"".join(temp_children))
    cell_children_grp = _make_group(vmad_patch.GROUP_CELL_CHILDREN, struct.pack("<I", full_cell), temp_grp)
    cell_top = _make_group(0, b"CELL", cell_rec + cell_children_grp)
    path.write_bytes(tes4 + cell_top)


class A3PathPlacesPlanTests(unittest.TestCase):
    def test_a3_and_all_plan_counts_and_unique_ids(self) -> None:
        plan_a3 = a3.build_door_plan(groups=["a3_all"])
        self.assertEqual(plan_a3["real_mesh_count"], 13)
        self.assertEqual(plan_a3["autoload_activator_count"], 1)
        self.assertEqual(plan_a3["port_next_before"], "074CD3")
        self.assertEqual(plan_a3["port_next_after"], "074CE0")

        plan_all = a3.build_door_plan(groups=["all"])
        self.assertEqual(plan_all["real_mesh_count"], 18)
        self.assertEqual(plan_all["autoload_activator_count"], 2)
        self.assertEqual(plan_all["port_next_after"], "074CE5")

        # Every marker & ref ID must be unique and within 24-bit plugin-local bounds
        p_markers = [d["int_arrival_marker"] for d in plan_all["real_mesh_doors"]]
        c_markers = [d["ext_arrival_marker"] for d in plan_all["real_mesh_doors"]]
        i_refs = [d["int_port_ref"] for d in plan_all["real_mesh_doors"]]
        e_refs = [d["ext_core_ref"] for d in plan_all["real_mesh_doors"]]
        self.assertEqual(len(p_markers), len(set(p_markers)))
        self.assertEqual(len(c_markers), len(set(c_markers)))
        self.assertEqual(len(i_refs), len(set(i_refs)))
        self.assertEqual(len(e_refs), len(set(e_refs)))

        # Verify Red Rocket Mole Rat Den & Corvega sewer pipe are flagged as autoload_activator
        auto_ids = {d["id"] for d in plan_all["autoload_doors"]}
        self.assertEqual(auto_ids, {"red_rocket_mole_rat_cave", "corvega_sewer_pipe"})

    def test_vmad_six_property_roundtrip_and_merged_math(self) -> None:
        plan = a3.build_door_plan(groups=["concord_museum"])
        self.assertEqual(plan["real_mesh_count"], 3)
        for entry in plan["real_mesh_doors"]:
            loc = entry["ext_arrival_local"]
            mrg = entry["ext_arrival_merged"]
            self.assertAlmostEqual(mrg[0], loc[0] - 1200.0, places=4)
            self.assertAlmostEqual(mrg[1], loc[1] - 2700.0, places=4)
            self.assertAlmostEqual(mrg[2], loc[2], places=4)

            ext_vmad = bytes.fromhex(entry["ext_to_int_vmad_hex"])
            int_vmad = bytes.fromhex(entry["int_to_ext_vmad_hex"])
            plugin_e, id_e, pos_e = vmad_patch.load_door_target(ext_vmad)
            plugin_i, id_i, pos_i = vmad_patch.load_door_target(int_vmad)
            self.assertEqual(plugin_e, "FO4Port.esm")
            self.assertEqual(id_e, int(entry["int_arrival_marker"], 16))
            self.assertIsNotNone(pos_e)
            self.assertEqual(plugin_i, "FO4TerrainCore.esm")
            self.assertEqual(id_i, int(entry["ext_arrival_marker"], 16))
            self.assertIsNotNone(pos_i)
            for idx in range(3):
                self.assertAlmostEqual(pos_e[idx], entry["int_arrival"][idx], places=3)
                self.assertAlmostEqual(pos_i[idx], mrg[idx], places=3)

    def test_r10_load_door_psc_contract_matches(self) -> None:
        text = LOAD_DOOR_PSC.read_text(encoding="utf-8")
        self.assertIn("int Property MoveRetries = 2 Auto", text)
        self.assertIn("bool Property UseDestinationPosition = False Auto", text)
        self.assertIn("FO4SF_LoadDoor load door arrival failed", text)
        self.assertEqual(a3.LOAD_DOOR_R10_CONTRACT["total_attempts_budget"], 3)

    def test_synthetic_port_patch_preserves_untouched_records_and_keeps_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            port_src = root / "port_src"
            core_src = root / "core_src"
            port_out = root / "port_out"
            port_src.mkdir()
            core_src.mkdir()

            # Synthetic port with 1 existing door (013030) + 2 new Museum doors (01303B, 013048) + 1 untouched ref (013050)
            # Highest own local ID is 0x013050 -> HEDR nextObjectId = 0x013051
            cell_id = 0x012540
            _build_synthetic_port_esm(
                port_src / "FO4Port.esm",
                cell_id=cell_id,
                cell_edid="FO4Port_ConcordMuseum01",
                door_refs=[0x013030, 0x01303B, 0x013048],
                extra_static_id=0x013050,
                next_obj_id=0x013051,
            )
            (port_src / "formids.json").write_text(
                json.dumps({"CELL:FO4Port_ConcordMuseum01": cell_id}), encoding="utf-8"
            )
            keep_doors = {
                "doors": [
                    {"src": "02C087:Fallout4.esm", "marker": "00E175"},
                ]
            }
            keep_path = root / "keep_doors.json"
            keep_path.write_text(json.dumps(keep_doors), encoding="utf-8")

            # Synthetic core with 1 kept door + 2 new Museum doors (front + roof)
            museum_plan = a3.build_door_plan(groups=["concord_museum"], port_next_id=0x013051, core_next_marker_id=0x0A7800)
            front = next(d for d in museum_plan["real_mesh_doors"] if d["id"] == "museum_front")
            roof = next(d for d in museum_plan["real_mesh_doors"] if d["id"] == "museum_roof")
            # Re-seat roof marker ID consecutively after front (0x013051 -> 0x013052) since balcony isn't in this synthetic core
            roof["destination"]["id"] = 0x013052

            kept_entry = {
                "src": "02C087:Fallout4.esm",
                "edid": "FO4Core_door_kept",
                "destination": {
                    "plugin": "FO4Port.esm",
                    "id": 0x00E175,
                    "ref": "013030",
                    "cell": f"{cell_id:06X}",
                    "cell_edid": "FO4Port_ConcordMuseum01",
                    "arrival": {"pos": [1.0, 2.0, 3.0], "rot": [0.0, 0.0, 0.0]},
                },
                "arrival": {"pos": [10.0, 20.0, 5.0], "rot": [0.0, 0.0, 0.0]},
            }
            core_objects = {"doors": [kept_entry, front, roof]}
            core_formids = {
                "plugin": "FO4TerrainCore.esm",
                "doors": {
                    "02C087:Fallout4.esm": {"base": "0A7720", "ref": "001000", "arrival": "0A773F"},
                    front["src"]: {"base": "0A7721", "ref": front["ext_core_ref"], "arrival": front["ext_arrival_marker"]},
                    roof["src"]: {"base": "0A7722", "ref": roof["ext_core_ref"], "arrival": roof["ext_arrival_marker"]},
                },
            }
            (core_src / "objects.json").write_text(json.dumps(core_objects), encoding="utf-8")
            (core_src / "formids.json").write_text(json.dumps(core_formids), encoding="utf-8")
            (core_src / "overlays_params.json").write_text(
                json.dumps({"overlays": [{"world": "FO4Core_Commonwealth", "planet_target_cell": [-12, -27]}]}),
                encoding="utf-8",
            )

            src_bytes_before = (port_src / "FO4Port.esm").read_bytes()
            rc = a3.main(
                [
                    "patch-port",
                    "--port",
                    str(port_src),
                    "--core",
                    str(core_src),
                    "--out",
                    str(port_out),
                    "--keep-markers",
                    str(keep_path),
                    "--allow-new-doors",
                ]
            )
            self.assertEqual(rc, 0)
            # Pinned input must be byte-for-byte unchanged
            self.assertEqual((port_src / "FO4Port.esm").read_bytes(), src_bytes_before)
            # Output doors.json has all 3 doors (1 kept + 2 Museum) with exact marker IDs
            out_doors = json.loads((port_out / "doors.json").read_text(encoding="utf-8"))
            markers_by_src = {d["src"]: d["marker"] for d in out_doors["doors"]}
            self.assertEqual(markers_by_src["02C087:Fallout4.esm"], "00E175")
            self.assertEqual(markers_by_src[front["src"]], "013051")
            self.assertEqual(markers_by_src[roof["src"]], "013052")
            # vmad_patch.cmd_check confirms every untouched record is byte-identical
            chk_rc = vmad_patch.cmd_check(
                a3.argparse.Namespace(port=str(port_src), out=str(port_out), core=str(core_src))
            )
            self.assertEqual(chk_rc, 0)


class A4NextMissionsW6Tests(unittest.TestCase):
    def test_a4_missions_clean_pass_and_in_place_sanctuary_id(self) -> None:
        rep = a3.evaluate_a4_missions()
        self.assertTrue(rep["pass"], rep)
        self.assertEqual(rep["missions_checked"], 3)
        self.assertEqual(rep["dead_end_count"], 0)
        self.assertEqual(rep["open_mode_failure_count"], 0)

        by_id = {m["id"]: m for m in a3.A4_NEXT_MISSIONS}
        # In-place rule: Sanctuary MUST remain 0x000817, never a second quest
        self.assertIn("0x000817", by_id["FO4SF_Sanctuary01"]["starfield_quest_id"])
        # Reserved A4 quests must avoid FO4SFMission.esm's 0x800..0x9FF block
        self.assertIn("0x000A20", by_id["FO4SF_MinRecruit00"]["starfield_quest_id"])
        self.assertIn("0x000A50", by_id["FO4SF_MQ103"]["starfield_quest_id"])
        for m in a3.A4_NEXT_MISSIONS:
            self.assertIn("FO4SF_GameMode == 1", m["mission_gate"])
            self.assertEqual(len(m["break_it_cases"]), 4)

    def test_mutation_detects_a4_dead_end_and_missing_open_mode_fallback(self) -> None:
        mutated_de = copy.deepcopy(a3.A4_NEXT_MISSIONS)
        sanc = next(m for m in mutated_de if m["id"] == "FO4SF_Sanctuary01")
        sanc["transitions"] = [t for t in sanc["transitions"] if t["from"] != 1200]
        rep_de = a3.evaluate_a4_missions(mutated_de)
        self.assertFalse(rep_de["pass"])
        self.assertGreater(rep_de["dead_end_count"], 0)

        mutated_om = copy.deepcopy(a3.A4_NEXT_MISSIONS)
        mq103 = next(m for m in mutated_om if m["id"] == "FO4SF_MQ103")
        mq103["transitions"] = [t for t in mq103["transitions"] if not t.get("open_mode_only")]
        rep_om = a3.evaluate_a4_missions(mutated_om)
        self.assertFalse(rep_om["pass"])
        self.assertGreater(rep_om["open_mode_failure_count"], 0)


class A3A4DocsAndCliTests(unittest.TestCase):
    def test_docs_clean_room_p3_and_zero_drive_leaks(self) -> None:
        for doc in (DOC_A3, DOC_A4, A3_SCRIPT):
            text = doc.read_text(encoding="utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(text), f"Windows drive-letter leak in {doc.name}")
            for pat in FORBIDDEN_MOD_PATTERNS:
                self.assertIsNone(pat.search(text), f"Forbidden mod name {pat.pattern} in {doc.name}")

        for doc in (DOC_A3, DOC_A4):
            text = doc.read_text(encoding="utf-8")
            self.assertIn("Titles: Fallout 4", text[:500])
            self.assertIn("unproven in game", text[:600].lower())
            # P3 zero M/N/V rule inside ```console``` blocks
            for lang, body in FENCED_BLOCK_RE.findall(text):
                if lang.strip().lower() == "console":
                    for bad in ("m", "n", "v"):
                        self.assertNotIn(bad, body.lower(), f"P3 violation ({bad}) in console block of {doc.name}: {body!r}")

        a4_text = DOC_A4.read_text(encoding="utf-8")
        self.assertIn("09000817", a4_text)
        self.assertIn("in place", a4_text.lower())

    def test_cli_plan_and_audit_a4_subprocesses(self) -> None:
        p1 = subprocess.run(
            [sys.executable, str(A3_SCRIPT), "plan", "--groups", "a3_all"],
            capture_output=True,
            text=True,
            check=True,
        )
        d1 = json.loads(p1.stdout)
        self.assertEqual(d1["real_mesh_count"], 13)

        p2 = subprocess.run(
            [sys.executable, str(A3_SCRIPT), "audit-a4"],
            capture_output=True,
            text=True,
            check=True,
        )
        d2 = json.loads(p2.stdout)
        self.assertTrue(d2["pass"])


if __name__ == "__main__":
    unittest.main()
