"""Synthetic unit tests for `scripts/terrain/dlc_edits.py` (`WD4`)."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from fo4sf.terrain.path_guard import OutputPathRefusedError  # noqa: E402

_spec = importlib.util.spec_from_file_location("dlc_edits_mod", ROOT / "scripts" / "terrain" / "dlc_edits.py")
dlc_edits = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(dlc_edits)


def _sub(sig: bytes, data: bytes) -> bytes:
    return sig + struct.pack("<H", len(data)) + data


def _rec(sig: bytes, fid: int, subs: list[tuple[bytes, bytes]], flags: int = 0) -> bytes:
    payload = b"".join(_sub(s, d) for s, d in subs)
    return struct.pack("<4sIIIIHH", sig, len(payload), flags, fid, 0, 131, 0) + payload


def _grup(label: bytes | int, items: list[bytes], gtype: int = 0) -> bytes:
    if isinstance(label, int):
        label = struct.pack("<I", label)
    body = b"".join(items)
    return struct.pack("<4sI4siHHHH", b"GRUP", 24 + len(body), label, gtype, 0, 0, 0, 0) + body


def _z(text: str) -> bytes:
    return text.encode("cp1252") + b"\x00"


def _write_synthetic_load_order(
    depot_path: str,
    ng_path: str,
    dlc1_path: str,
    dlc2_path: str,
    formids_path: str,
) -> None:
    tes4_base = _rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 10, 0x0900))], flags=0x1)

    # Depot Fallout4.esm: refs 000810 (static), 000811 (container), 000812 (to be deleted by DLC1), 000813 (modified in NG)
    r_810 = _rec(
        b"REFR",
        0x000810,
        [(b"NAME", struct.pack("<I", 0x000801)), (b"DATA", struct.pack("<6f", 100.0, 100.0, 0.0, 0.0, 0.0, 0.0))],
    )
    r_811 = _rec(
        b"REFR",
        0x000811,
        [(b"NAME", struct.pack("<I", 0x000802)), (b"DATA", struct.pack("<6f", 200.0, 200.0, 0.0, 0.0, 0.0, 0.0))],
    )
    r_812 = _rec(
        b"REFR",
        0x000812,
        [(b"NAME", struct.pack("<I", 0x000801)), (b"DATA", struct.pack("<6f", 300.0, 300.0, 0.0, 0.0, 0.0, 0.0))],
    )
    r_813_dp = _rec(
        b"REFR",
        0x000813,
        [(b"NAME", struct.pack("<I", 0x000801)), (b"DATA", struct.pack("<6f", 400.0, 400.0, 0.0, 0.0, 0.0, 0.0))],
    )

    def make_cw_plugin(tes4: bytes, top_refs: list[bytes], ext_refs: list[bytes]) -> bytes:
        top_cell = _rec(b"CELL", 0x000820, [(b"XCLC", struct.pack("<iiI", 0, 0, 0))], flags=0x400)
        ext_cell = _rec(b"CELL", 0x000821, [(b"XCLC", struct.pack("<iiI", 1, 2, 0))])
        w_items = [
            top_cell,
            _grup(0x000820, [_grup(0x000820, top_refs, 8)], 6),
            _grup(
                struct.pack("<hh", 0, 0),
                [_grup(struct.pack("<hh", 0, 0), [ext_cell, _grup(0x000821, [_grup(0x000821, ext_refs, 9)], 6)], 5)],
                4,
            ),
        ]
        return tes4 + _grup(b"WRLD", [_rec(b"WRLD", 0x00003C, [(b"EDID", _z("Commonwealth"))]), _grup(0x00003C, w_items, 1)])

    Path(depot_path).write_bytes(make_cw_plugin(tes4_base, [], [r_810, r_811, r_812, r_813_dp]))

    # Next-Gen Fallout4.esm: moves 000813 and adds 000814
    r_813_ng = _rec(
        b"REFR",
        0x000813,
        [(b"NAME", struct.pack("<I", 0x000801)), (b"DATA", struct.pack("<6f", 450.0, 400.0, 0.0, 0.0, 0.0, 0.0))],
    )
    r_814_ng = _rec(
        b"REFR",
        0x000814,
        [(b"NAME", struct.pack("<I", 0x000801)), (b"DATA", struct.pack("<6f", 500.0, 500.0, 0.0, 0.0, 0.0, 0.0))],
    )
    Path(ng_path).write_bytes(make_cw_plugin(tes4_base, [], [r_810, r_811, r_812, r_813_ng, r_814_ng]))

    tes4_dlc = _rec(
        b"TES4",
        0,
        [
            (b"HEDR", struct.pack("<fII", 1.0, 10, 0x0900)),
            (b"MAST", _z("Fallout4.esm")),
            (b"DATA", struct.pack("<Q", 0)),
        ],
        flags=0x1,
    )
    # DLC1 (DLCCoast.esm): moves 000810 (later overridden again by DLC2!), deletes 000812, adds 01000850 (boat door) + persistent marker 01000851
    r_810_dlc1 = _rec(
        b"REFR",
        0x000810,
        [(b"NAME", struct.pack("<I", 0x000801)), (b"DATA", struct.pack("<6f", 120.0, 100.0, 0.0, 0.0, 0.0, 0.0))],
    )
    r_812_del = _rec(b"REFR", 0x000812, [], flags=0x20)
    r_boat = _rec(
        b"REFR",
        0x01000850,
        [
            (b"NAME", struct.pack("<I", 0x01000805)),
            (b"XTEL", struct.pack("<I6fI", 0x01000999, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)),
            (b"DATA", struct.pack("<6f", 150.0, 150.0, 0.0, 0.0, 0.0, 0.0)),
        ],
    )
    r_marker = _rec(
        b"REFR",
        0x01000851,
        [(b"NAME", struct.pack("<I", 0x000010)), (b"XMRK", b""), (b"DATA", struct.pack("<6f", 150.0, 150.0, 0.0, 0.0, 0.0, 0.0))],
        flags=0x400,
    )
    Path(dlc1_path).write_bytes(make_cw_plugin(tes4_dlc, [r_marker], [r_810_dlc1, r_812_del, r_boat]))

    # DLC2 (DLCNukaWorld.esm): wins on 000810 (moves to 180.0), disables container 000811, adds 01000860
    r_810_dlc2 = _rec(
        b"REFR",
        0x000810,
        [(b"NAME", struct.pack("<I", 0x000801)), (b"DATA", struct.pack("<6f", 180.0, 100.0, 0.0, 0.0, 0.0, 0.0))],
    )
    r_811_dis = _rec(
        b"REFR",
        0x000811,
        [(b"NAME", struct.pack("<I", 0x000802)), (b"DATA", struct.pack("<6f", 200.0, 200.0, 0.0, 0.0, 0.0, 0.0))],
        flags=0x800,
    )
    r_nw_new = _rec(
        b"REFR",
        0x01000860,
        [(b"NAME", struct.pack("<I", 0x01000809)), (b"DATA", struct.pack("<6f", 600.0, 600.0, 0.0, 0.0, 0.0, 0.0))],
    )
    Path(dlc2_path).write_bytes(make_cw_plugin(tes4_dlc, [], [r_810_dlc2, r_811_dis, r_nw_new]))

    formids = {
        "plugin": "FO4TerrainCore.esm",
        "world": "FO4Core_Commonwealth",
        "refs": {"000810:Fallout4.esm": "004010", "000812:Fallout4.esm": "004012", "000813:Fallout4.esm": "004013"},
        "containers": {"000811:Fallout4.esm": {"base": "0A2001", "ref": "004011"}},
    }
    Path(formids_path).write_text(json.dumps(formids), encoding="utf-8")


class DlcEditsTests(unittest.TestCase):
    def test_separates_base_drift_from_winning_dlc_edits_and_resolves_core_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            in_dir = os.path.join(tmp, "in")
            out_dir = os.path.join(tmp, "out")
            os.makedirs(in_dir, exist_ok=True)
            depot = os.path.join(in_dir, "Depot_Fallout4.esm")
            # Depot file must still resolve its own Commonwealth records; name it inside subdir as Fallout4.esm
            os.makedirs(os.path.join(in_dir, "depot"), exist_ok=True)
            depot = os.path.join(in_dir, "depot", "Fallout4.esm")
            ng = os.path.join(in_dir, "Fallout4.esm")
            dlc1 = os.path.join(in_dir, "DLCCoast.esm")
            dlc2 = os.path.join(in_dir, "DLCNukaWorld.esm")
            fids = os.path.join(in_dir, "formids.json")
            _write_synthetic_load_order(depot, ng, dlc1, dlc2, fids)

            rc = dlc_edits.main(
                [
                    "--nextgen-fo4",
                    ng,
                    "--depot-fo4",
                    depot,
                    "--dlc",
                    dlc1,
                    "--dlc",
                    dlc2,
                    "--core-formids",
                    fids,
                    "--out",
                    out_dir,
                ]
            )
            self.assertEqual(rc, 0)

            summary = json.loads(Path(out_dir, "dlc_edits_summary.json").read_text(encoding="utf-8"))
            full = json.loads(Path(out_dir, "dlc_edits.json").read_text(encoding="utf-8"))

            # Base-game diff isolated cleanly from DLC edits
            bg = summary["base_game_diff"]
            self.assertEqual(bg["added_in_nextgen"], 1)  # 000814
            self.assertEqual(bg["modified_in_nextgen"], 1)  # 000813
            self.assertEqual(bg["resolved_in_core"], 1)  # 000813
            self.assertEqual(bg["marked_new"], 1)  # 000814

            # Per-DLC raw counts vs winning counts (DLC2 overrides 000810 over DLC1!)
            c1 = summary["per_dlc"]["DLCCoast.esm"]
            self.assertEqual(c1["raw_cells"], 1)  # persistent cell excluded from exterior cell count
            self.assertEqual(c1["raw_refs"], 4)
            self.assertEqual(c1["raw_map_markers"], 1)
            self.assertEqual(c1["raw_load_doors"], 1)
            self.assertEqual(c1["winning_refs_total"], 3)  # 000812 deleted + 000850 + 000851

            c2 = summary["per_dlc"]["DLCNukaWorld.esm"]
            self.assertEqual(c2["raw_refs"], 3)
            self.assertEqual(c2["winning_refs_total"], 3)  # wins on 000810 + 000811 + 000860

            by_fk = {e["form_key"]: e for e in full["winning_dlc_edits"]}
            self.assertEqual(by_fk["000810:Fallout4.esm"]["winning_plugin"], "DLCNukaWorld.esm")
            self.assertEqual(by_fk["000810:Fallout4.esm"]["kind"], "moved")
            self.assertEqual(by_fk["000810:Fallout4.esm"]["core"], {"status": "resolved", "core_ref_id": "004010", "core_section": "refs"})

            self.assertEqual(by_fk["000811:Fallout4.esm"]["kind"], "disabled")
            self.assertEqual(by_fk["000811:Fallout4.esm"]["core"], {"status": "resolved", "core_ref_id": "004011", "core_section": "containers"})

            self.assertEqual(by_fk["000812:Fallout4.esm"]["kind"], "deleted")
            self.assertEqual(by_fk["000812:Fallout4.esm"]["core"]["core_ref_id"], "004012")

            self.assertEqual(by_fk["000850:DLCCoast.esm"]["kind"], "added")
            self.assertEqual(by_fk["000850:DLCCoast.esm"]["core"]["status"], "new")
            self.assertEqual(by_fk["000851:DLCCoast.esm"]["winning_record"]["cell"], "persistent")

            # R4 path guard refuses writing inside a Git worktree
            fake_wt = os.path.join(tmp, "wt")
            os.makedirs(os.path.join(fake_wt, ".git"), exist_ok=True)
            with self.assertRaises(OutputPathRefusedError):
                dlc_edits.main(["--nextgen-fo4", ng, "--core-formids", fids, "--out", os.path.join(fake_wt, "out")])


if __name__ == "__main__":
    unittest.main()
