"""Unit tests for `scripts/terrain/make_cw_dlc_override.py` (`WB5` & `WB5b`).

Runs completely offline on synthetic ESM / JSON fixtures (zero game files needed).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts" / "terrain") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "terrain"))

import make_cw_dlc_override as cw_dlc  # noqa: E402
import vmad_patch  # noqa: E402
from fo4sf import fo4land  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_synthetic_core_stage(core_dir: Path) -> None:
    """Create a minimal synthetic `FO4TerrainCore.esm` + `objects.json` + `formids.json` + `overlays_params.json`."""
    core_dir.mkdir(parents=True, exist_ok=True)
    own = 0x01000000

    # STAT 0x01001810 (shared crate) + STAT 0x01001811 (alt crate) + ACTI 0x01001820 (door activator)
    stat_crate = cw_dlc._stat_record(own | 0x001810, "FO4Core_woodcrate01", r"fo4core\clutter\woodcrate01.nif")
    stat_alt = cw_dlc._stat_record(own | 0x001811, "FO4Core_metalcrate01", r"fo4core\clutter\metalcrate01.nif")
    acti_door = vmad_patch.record_bytes(
        b"ACTI",
        own | 0x001820,
        0,
        [
            (b"EDID", b"FO4Core_door_transit01\x00"),
            (b"OBND", b"\x00" * 24),
            (b"ODTY", b"\x00" * 4),
            (b"FULL", b"Door\x00"),
            (b"MODL", b"fo4core\\doors\\indmetaldbdoorload01.nif\x00"),
        ],
    )

    wrld_rec = vmad_patch.record_bytes(
        b"WRLD",
        own | 0x000803,
        0x04,
        [(b"EDID", b"FO4Core_Commonwealth\x00")],
    )
    pers_cell = vmad_patch.record_bytes(b"CELL", own | 0x001805, 0, [(b"DATA", struct.pack("<I", 1))])
    pers_anchor = cw_dlc._refr_record(own | 0x000800, 0x0000003B, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], flags=0x0400)
    pers_grp = vmad_patch.Group(
        struct.pack("<I", pers_cell.fid),
        cw_dlc.GROUP_CELL_CHILDREN,
        b"\x00" * 8,
        [vmad_patch.Group(struct.pack("<I", pers_cell.fid), cw_dlc.GROUP_CELL_PERSISTENT, b"\x00" * 8, [pers_anchor])],
    )

    # Two exterior cells: (0, 0) = 0x01001000 and (1, 0) = 0x01001001
    cell_00 = vmad_patch.record_bytes(
        b"CELL",
        own | 0x001000,
        0,
        [(b"DATA", struct.pack("<I", 0)), (b"XCLC", struct.pack("<iiI", 0, 0, 0))],
    )
    cell_10 = vmad_patch.record_bytes(
        b"CELL",
        own | 0x001001,
        0,
        [(b"DATA", struct.pack("<I", 0)), (b"XCLC", struct.pack("<iiI", 1, 0, 0))],
    )
    # Existing core REFRs in cell (0, 0):
    # - 0x00611C: will be deleted by DLC -> must become InitiallyDisabled (0x0800), NEVER Deleted (0x0020)
    # - 0x006126: will be moved + scaled + base_changed by DLC
    # - 0x006240: identical_override in DLC -> no-op
    ref_del = cw_dlc._refr_record(own | 0x00611C, own | 0x001810, [10.0, 10.0, 1.0], [0.0, 0.0, 0.0])
    ref_mov = cw_dlc._refr_record(own | 0x006126, own | 0x001810, [12.0, 15.0, 2.0], [0.0, 0.0, 0.5])
    ref_idn = cw_dlc._refr_record(own | 0x006240, own | 0x001810, [20.0, 20.0, 3.0], [0.0, 0.0, 0.0])

    c00_children = vmad_patch.Group(
        struct.pack("<I", cell_00.fid),
        cw_dlc.GROUP_CELL_CHILDREN,
        b"\x00" * 8,
        [
            vmad_patch.Group(
                struct.pack("<I", cell_00.fid),
                cw_dlc.GROUP_CELL_TEMPORARY,
                b"\x00" * 8,
                [ref_del, ref_mov, ref_idn],
            )
        ],
    )
    subblock = vmad_patch.Group(
        struct.pack("<hh", 0, 0),
        cw_dlc.GROUP_EXT_CELL_SUBBLOCK,
        b"\x00" * 8,
        [cell_00, c00_children, cell_10],
    )
    block = vmad_patch.Group(
        struct.pack("<hh", 0, 0),
        cw_dlc.GROUP_EXT_CELL_BLOCK,
        b"\x00" * 8,
        [subblock],
    )
    wrld_children = vmad_patch.Group(
        struct.pack("<I", wrld_rec.fid),
        cw_dlc.GROUP_WORLD_CHILDREN,
        b"\x00" * 8,
        [pers_cell, pers_grp, block],
    )

    top_groups = [
        vmad_patch.Group(b"ACTI", 0, b"\x00" * 8, [acti_door]),
        vmad_patch.Group(b"STAT", 0, b"\x00" * 8, [stat_crate, stat_alt]),
        vmad_patch.Group(b"WRLD", 0, b"\x00" * 8, [wrld_rec, wrld_children]),
    ]
    tes4 = cw_dlc._build_tes4_record(("Starfield.esm",), cw_dlc._count_tree_items(top_groups), 0x006241)
    (core_dir / "FO4TerrainCore.esm").write_bytes(tes4.serialize() + b"".join(g.serialize() for g in top_groups))

    (core_dir / "overlays_params.json").write_text(
        json.dumps({"overlays": [{"world": "FO4Core_Commonwealth", "planet_target_cell": [-12, -27]}]}),
        encoding="utf-8",
    )
    (core_dir / "objects.json").write_text(
        json.dumps(
            {
                "world": "FO4Core_Commonwealth",
                "edid_prefix": "FO4Core_",
                "bases": [
                    {
                        "edid": "FO4Core_woodcrate01",
                        "model": r"fo4core\clutter\woodcrate01.nif",
                        "source": r"meshes\Clutter\WoodCrate01.nif",
                    },
                    {
                        "edid": "FO4Core_metalcrate01",
                        "model": r"fo4core\clutter\metalcrate01.nif",
                        "source": r"meshes\Clutter\MetalCrate01.nif",
                    },
                    {
                        "edid": "FO4Core_indmetaldbdoorload01",
                        "model": r"fo4core\doors\indmetaldbdoorload01.nif",
                        "source": r"meshes\Interiors\Industrial\Doors\IndMetalDbDoorLoad01.nif",
                    },
                ],
                "refs": [],
                "doors": [
                    {
                        "src": "04BAF6:Fallout4.esm",
                        "edid": "FO4Core_door_transit01",
                        "model": r"fo4core\doors\indmetaldbdoorload01.nif",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (core_dir / "formids.json").write_text(
        json.dumps(
            {
                "plugin": "FO4TerrainCore.esm",
                "world": "FO4Core_Commonwealth",
                "bases": {
                    "FO4Core_woodcrate01": "001810",
                    "FO4Core_metalcrate01": "001811",
                    "FO4Core_indmetaldbdoorload01": "001812",
                },
                "doors": {
                    "04BAF6:Fallout4.esm": {"base": "001820", "ref": "006000", "arrival": "006001"},
                },
            }
        ),
        encoding="utf-8",
    )


def _write_synthetic_dlc_stage(dlc_dir: Path) -> str:
    """Create a minimal synthetic `FO4DLC.esm` + companion `FO4DLCTextures2.esm` + `formids.json` + `manifest_merged.json`."""
    dlc_dir.mkdir(parents=True, exist_ok=True)
    own = 0x01000000  # FO4DLC.esm has 1 master: Starfield.esm

    stat_shared = cw_dlc._stat_record(own | 0x000801, "FO4DLC_woodcrate01", r"fo4dlc\clutter\woodcrate01.nif")
    stat_dlc_only = cw_dlc._stat_record(own | 0x000802, "FO4DLC_nukastatue01", r"fo4dlc\dlc04\nukastatue01.nif")
    door_vault = vmad_patch.record_bytes(
        b"DOOR",
        own | 0x000803,
        0,
        [
            (b"EDID", b"FO4DLC_paintedwooddoorload01\x00"),
            (b"OBND", b"\x00" * 24),
            (b"ODTY", b"\x00" * 4),
            (b"FULL", b"Door\x00"),
            (b"MODL", b"fo4dlc\\doors\\paintedwooddoorload01.nif\x00"),
        ],
    )
    door_transit = vmad_patch.record_bytes(
        b"DOOR",
        own | 0x000804,
        0,
        [
            (b"EDID", b"FO4DLC_indmetaldbdoorload01\x00"),
            (b"OBND", b"\x00" * 24),
            (b"ODTY", b"\x00" * 4),
            (b"FULL", b"Door\x00"),
            (b"MODL", b"fo4dlc\\doors\\indmetaldbdoorload01.nif\x00"),
        ],
    )

    # Interior cell 1: FO4DLC_DLC06VaultWorkshop (0x01000900), temporary door REFR 0x01000901
    cell_v88 = vmad_patch.record_bytes(
        b"CELL",
        own | 0x000900,
        0x01,
        [(b"EDID", b"FO4DLC_DLC06VaultWorkshop\x00"), (b"DATA", struct.pack("<I", 1))],
    )
    ref_v88_door = cw_dlc._refr_record(own | 0x000901, own | 0x000803, [-135.0, -72.0, 6.5], [0.0, 0.0, 5.2])
    c_v88_grp = vmad_patch.Group(
        struct.pack("<I", cell_v88.fid),
        cw_dlc.GROUP_CELL_CHILDREN,
        b"\x00" * 8,
        [vmad_patch.Group(struct.pack("<I", cell_v88.fid), cw_dlc.GROUP_CELL_TEMPORARY, b"\x00" * 8, [ref_v88_door])],
    )

    # Interior cell 2: FO4DLC_DLC04TransitCenter01 (0x01000902), temporary door REFR 0x01000903
    cell_nwt = vmad_patch.record_bytes(
        b"CELL",
        own | 0x000902,
        0x01,
        [(b"EDID", b"FO4DLC_DLC04TransitCenter01\x00"), (b"DATA", struct.pack("<I", 1))],
    )
    ref_nwt_door = cw_dlc._refr_record(own | 0x000903, own | 0x000804, [-24.0, 16.5, 3.6], [0.0, 0.0, 1.57])
    c_nwt_grp = vmad_patch.Group(
        struct.pack("<I", cell_nwt.fid),
        cw_dlc.GROUP_CELL_CHILDREN,
        b"\x00" * 8,
        [vmad_patch.Group(struct.pack("<I", cell_nwt.fid), cw_dlc.GROUP_CELL_TEMPORARY, b"\x00" * 8, [ref_nwt_door])],
    )

    cell_sub = vmad_patch.Group(struct.pack("<I", 0), 3, b"\x00" * 8, [cell_v88, c_v88_grp, cell_nwt, c_nwt_grp])
    cell_blk = vmad_patch.Group(struct.pack("<I", 0), 2, b"\x00" * 8, [cell_sub])

    top_groups = [
        vmad_patch.Group(b"DOOR", 0, b"\x00" * 8, [door_vault, door_transit]),
        vmad_patch.Group(b"STAT", 0, b"\x00" * 8, [stat_shared, stat_dlc_only]),
        vmad_patch.Group(b"CELL", 0, b"\x00" * 8, [cell_blk]),
    ]
    # Highest own local ID is 0x000903 -> next = 0x000904
    tes4 = cw_dlc._build_tes4_record(("Starfield.esm",), cw_dlc._count_tree_items(top_groups), 0x000904)
    (dlc_dir / "FO4DLC.esm").write_bytes(tes4.serialize() + b"".join(g.serialize() for g in top_groups))

    # Empty texture companion plugin to verify vmad_patch TEXTURE_COMPANION skips FO4DLCTextures2.esm cleanly
    tes4_comp = cw_dlc._build_tes4_record(("Starfield.esm",), 0, 0x000800)
    (dlc_dir / "FO4DLCTextures2.esm").write_bytes(tes4_comp.serialize())

    formids = {
        "STAT:FO4DLC_woodcrate01": 0x000801,
        "STAT:FO4DLC_nukastatue01": 0x000802,
        "DOOR:FO4DLC_paintedwooddoorload01": 0x000803,
        "DOOR:FO4DLC_indmetaldbdoorload01": 0x000804,
        "CELL:FO4DLC_DLC06VaultWorkshop": 0x000900,
        "REFR:FO4DLC_DLC06VaultWorkshop:003CBF:DLCworkshop03.esm": 0x000901,
        "CELL:FO4DLC_DLC04TransitCenter01": 0x000902,
        "REFR:FO4DLC_DLC04TransitCenter01:00ADB3:DLCNukaWorld.esm": 0x000903,
    }
    fids_path = dlc_dir / "formids.json"
    fids_path.write_text(json.dumps(formids, indent=2), encoding="utf-8")

    (dlc_dir / "manifest_merged.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "editor_id": "FO4DLC_woodcrate01",
                        "model": r"fo4dlc\clutter\woodcrate01.nif",
                        "source": r"Meshes\Clutter\WoodCrate01.nif",
                    },
                    {
                        "editor_id": "FO4DLC_nukastatue01",
                        "model": r"fo4dlc\dlc04\nukastatue01.nif",
                        "source": r"Meshes\DLC04\NukaStatue01.nif",
                    },
                    {
                        "editor_id": "FO4DLC_paintedwooddoorload01",
                        "model": r"fo4dlc\doors\paintedwooddoorload01.nif",
                        "source": r"Meshes\SetDressing\Doors\PaintedWoodDoorLoad01.nif",
                    },
                    {
                        "editor_id": "FO4DLC_indmetaldbdoorload01",
                        "model": r"fo4dlc\doors\indmetaldbdoorload01.nif",
                        "source": r"Meshes\Interiors\Industrial\Doors\IndMetalDbDoorLoad01.nif",
                    },
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return _sha256(fids_path)


class CwDlcOverrideTests(unittest.TestCase):
    def test_cli_help_runs_clean_without_pythonpath(self) -> None:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        script = str(ROOT / "scripts" / "terrain" / "make_cw_dlc_override.py")
        for sub in ([], ["build"], ["check"], ["install"], ["uninstall"], ["undo"], ["status"]):
            proc = subprocess.run(
                [sys.executable, "-B", script, *sub, "--help"],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("usage:", proc.stdout.lower())

    def test_refuses_output_inside_worktree_and_mismatched_dlc_formids_hash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            core_dir = base / "core"
            dlc_dir = base / "dlc"
            _write_synthetic_core_stage(core_dir)
            _write_synthetic_dlc_stage(dlc_dir)
            edits_path = base / "dlc_edits.json"
            edits_path.write_text(json.dumps({"winning_dlc_edits": []}), encoding="utf-8")

            # 1. Output inside Git worktree must be refused
            unsafe_out = ROOT / "tmp_forbidden_wb5_out"
            rc_unsafe = cw_dlc.main(
                [
                    "build",
                    "--edits",
                    str(edits_path),
                    "--core",
                    str(core_dir),
                    "--dlc",
                    str(dlc_dir),
                    "--out",
                    str(unsafe_out),
                ]
            )
            self.assertEqual(rc_unsafe, 2)
            self.assertFalse(unsafe_out.exists())

            # 2. Mismatched FO4DLC formids.json SHA-256 must be refused
            safe_out = base / "out_refused"
            rc_bad_sha = cw_dlc.main(
                [
                    "build",
                    "--edits",
                    str(edits_path),
                    "--core",
                    str(core_dir),
                    "--dlc",
                    str(dlc_dir),
                    "--out",
                    str(safe_out),
                    "--expected-dlc-formids-sha256",
                    "0" * 64,
                ]
            )
            self.assertEqual(rc_bad_sha, 2)
            self.assertFalse((safe_out / cw_dlc.OVERRIDE_PLUGIN_NAME).exists())

    def test_wb5_and_wb5b_end_to_end_on_synthetic_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            core_dir = base / "core"
            dlc_dir = base / "dlc"
            out_dir = base / "cw-dlc-override"
            doors_out_dir = base / "fo4dlc-stage-doors"

            _write_synthetic_core_stage(core_dir)
            dlc_fids_sha = _write_synthetic_dlc_stage(dlc_dir)
            core_sha_initial = _sha256(core_dir / "FO4TerrainCore.esm")

            # Extra manifest includes BOTH a duplicate FO4DLC model (must NEVER be re-authored!)
            # AND a genuinely new model neither core nor FO4DLC holds (must get a FO4DLC_ base in override!)
            extra_manifest_path = base / "extra_manifest.json"
            extra_manifest_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "editor_id": "FO4Port_nukastatue01",
                                "model": r"fo4port\dlc04\nukastatue01.nif",
                                "source": r"Meshes\DLC04\NukaStatue01.nif",
                            },
                            {
                                "editor_id": "FO4Port_coastbuoy01",
                                "model": r"fo4port\dlc03\coastbuoy01.nif",
                                "source": r"Meshes\DLC03\CoastBuoy01.nif",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            edits_doc = {
                "base_catalog": {
                    "bases": {
                        "010001:Fallout4.esm": {
                            "sig": "STAT",
                            "edid": "WoodCrate01",
                            "model": r"Clutter\WoodCrate01.nif",
                        },
                        "010002:Fallout4.esm": {
                            "sig": "STAT",
                            "edid": "MetalCrate01",
                            "model": r"Clutter\MetalCrate01.nif",
                        },
                        "020001:DLCNukaWorld.esm": {
                            "sig": "STAT",
                            "edid": "DLC04NukaStatue01",
                            "model": r"DLC04\NukaStatue01.nif",
                        },
                        "030001:DLCCoast.esm": {
                            "sig": "SCOL",
                            "edid": "DLC03CoastBuoy01",
                            "model": r"DLC03\CoastBuoy01.nif",
                        },
                        "030002:DLCCoast.esm": {
                            "sig": "STAT",
                            "edid": "DLC03UnconvertedRock",
                            "model": r"DLC03\UnconvertedRock.nif",
                        },
                        "00003B:Fallout4.esm": {
                            "sig": "STAT",
                            "edid": "XMarker",
                            "model": r"MarkerX.nif",
                        },
                        "005BC5:DLCworkshop03.esm": {
                            "sig": "DOOR",
                            "edid": "PaintedWoodDoorLoadD01MinUse",
                            "model": r"SetDressing\Doors\PaintedWoodDoorLoad01.nif",
                        },
                        "018C8C:Fallout4.esm": {
                            "sig": "DOOR",
                            "edid": "IndMetalDbDoorLoad01",
                            "model": r"Interiors\Industrial\Doors\IndMetalDbDoorLoad01.nif",
                        },
                    },
                    "doors": {
                        "003CC5:DLCworkshop03.esm": {
                            "edid": "",
                            "base": "005BC5:DLCworkshop03.esm",
                            "pos": [1400.0, 1400.0, 70.0],
                            "rot": [0.0, 0.0, 1.0],
                            "xtel": {
                                "door": "003CBF:DLCworkshop03.esm",
                                "pos": [-9450.0, -5040.0, 455.0],
                                "rot": [0.0, 0.0, 2.0],
                                "flags": 0,
                            },
                        },
                        "003CBF:DLCworkshop03.esm": {
                            "edid": "",
                            "base": "005BC5:DLCworkshop03.esm",
                            "pos": [-9471.0, -5025.0, 455.0],
                            "rot": [0.0, 0.0, 5.2],
                            "xtel": {
                                "door": "003CC5:DLCworkshop03.esm",
                                "pos": [1470.0, 1470.0, 70.0],
                                "rot": [0.0, 0.0, 0.5],
                                "flags": 0,
                            },
                        },
                        "00AD1B:DLCNukaWorld.esm": {
                            "edid": "",
                            "base": "018C8C:Fallout4.esm",
                            "pos": [2100.0, 2100.0, 140.0],
                            "rot": [0.0, 0.0, 0.0],
                            "xtel": {
                                "door": "00ADB3:DLCNukaWorld.esm",
                                "pos": [-1701.0, 1155.0, 252.0],
                                "rot": [0.0, 0.0, 1.57],
                                "flags": 0,
                            },
                        },
                        "00ADB3:DLCNukaWorld.esm": {
                            "edid": "DLC04TransitStationLoadDoorR",
                            "base": "018C8C:Fallout4.esm",
                            "pos": [-1736.0, 1152.0, 252.0],
                            "rot": [0.0, 0.0, 1.57],
                            "xtel": {
                                "door": "00AD1B:DLCNukaWorld.esm",
                                "pos": [2170.0, 2170.0, 140.0],
                                "rot": [0.0, 0.0, 3.14],
                                "flags": 0,
                            },
                        },
                    },
                },
                "winning_dlc_edits": [
                    # 1. Core deletion -> InitiallyDisabled (0x0800), NEVER Deleted (0x0020)
                    {
                        "form_key": "02761B:Fallout4.esm",
                        "winning_plugin": "DLCNukaWorld.esm",
                        "kind": "deleted",
                        "reasons": ["deleted"],
                        "core": {"status": "resolved", "core_ref_id": "00611C", "core_section": "refs"},
                        "base_record": {"base": "010001:Fallout4.esm"},
                        "winning_record": {"base": "010001:Fallout4.esm", "deleted": True},
                    },
                    # 2. Core move across cell (0,0) -> (1,0) + base_changed + scale
                    {
                        "form_key": "027625:Fallout4.esm",
                        "winning_plugin": "DLCNukaWorld.esm",
                        "kind": "moved",
                        "reasons": ["base_changed", "moved", "scaled"],
                        "core": {"status": "resolved", "core_ref_id": "006126", "core_section": "refs"},
                        "base_record": {"base": "010001:Fallout4.esm"},
                        "winning_record": {
                            "base": "010002:Fallout4.esm",
                            "pos": [8400.0, 1400.0, 210.0],  # (120m, 20m, 3m) -> cell (1, 0)
                            "rot": [0.0, 0.0, 1.25],
                            "scale": 1.5,
                            "disabled": False,
                        },
                    },
                    # 3. Core identical_override -> resolved no-op
                    {
                        "form_key": "02784F:Fallout4.esm",
                        "winning_plugin": "DLCNukaWorld.esm",
                        "kind": "identical_override",
                        "reasons": [],
                        "core": {"status": "resolved", "core_ref_id": "006240", "core_section": "refs"},
                        "base_record": {"base": "010001:Fallout4.esm"},
                        "winning_record": {"base": "010001:Fallout4.esm", "pos": [1400.0, 1400.0, 210.0], "rot": [0.0, 0.0, 0.0], "scale": 1.0},
                    },
                    # 4. Non-added reference absent from core -> listed in not_in_core
                    {
                        "form_key": "197B2D:Fallout4.esm",
                        "winning_plugin": "DLCNukaWorld.esm",
                        "kind": "deleted",
                        "reasons": ["deleted"],
                        "core": {"status": "new", "core_ref_id": None, "core_section": None},
                        "base_record": {"base": "00003B:Fallout4.esm"},
                        "winning_record": {"base": "00003B:Fallout4.esm", "deleted": True},
                    },
                    # 5. Added ref whose model exists in BOTH core and FO4DLC -> must reuse core (0x01001810)
                    {
                        "form_key": "000897:DLCRobot.esm",
                        "winning_plugin": "DLCRobot.esm",
                        "kind": "added",
                        "reasons": ["added"],
                        "core": {"status": "new", "core_ref_id": None},
                        "winning_record": {
                            "base": "010001:Fallout4.esm",
                            "pos": [700.0, 700.0, 70.0],
                            "rot": [0.0, 0.0, 0.0],
                            "scale": 1.0,
                            "disabled": False,
                            "is_load_door": False,
                        },
                    },
                    # 6. Added ref whose model is in FO4DLC (and also in extra_manifest!) -> must reuse FO4DLC (0x02000802), NO duplicate base!
                    {
                        "form_key": "000898:DLCNukaWorld.esm",
                        "winning_plugin": "DLCNukaWorld.esm",
                        "kind": "added",
                        "reasons": ["added"],
                        "core": {"status": "new", "core_ref_id": None},
                        "winning_record": {
                            "base": "020001:DLCNukaWorld.esm",
                            "pos": [1050.0, 1050.0, 70.0],
                            "rot": [0.0, 0.0, 0.0],
                            "scale": 1.0,
                            "disabled": False,
                            "is_load_door": False,
                        },
                    },
                    # 7. Added ref whose model neither core nor FO4DLC holds -> authored in override (0x03XXXXXX) with FO4DLC_ / fo4dlc\ prefix
                    {
                        "form_key": "000899:DLCCoast.esm",
                        "winning_plugin": "DLCCoast.esm",
                        "kind": "added",
                        "reasons": ["added"],
                        "core": {"status": "new", "core_ref_id": None},
                        "winning_record": {
                            "base": "030001:DLCCoast.esm",
                            "pos": [1400.0, 700.0, 0.0],
                            "rot": [0.0, 0.0, 0.0],
                            "scale": 1.0,
                            "disabled": False,
                            "is_load_door": False,
                        },
                    },
                    # 8. Added ref with unconverted mesh -> listed in missing_bases
                    {
                        "form_key": "000900:DLCCoast.esm",
                        "winning_plugin": "DLCCoast.esm",
                        "kind": "added",
                        "reasons": ["added"],
                        "core": {"status": "new", "core_ref_id": None},
                        "winning_record": {
                            "base": "030002:DLCCoast.esm",
                            "pos": [1400.0, 700.0, 0.0],
                            "rot": [0.0, 0.0, 0.0],
                            "scale": 1.0,
                            "disabled": False,
                            "is_load_door": False,
                        },
                    },
                    # 9 & 10. WB5b two-way load doors into DLC06VaultWorkshop and DLC04TransitCenter01
                    {
                        "form_key": "003CC5:DLCworkshop03.esm",
                        "winning_plugin": "DLCworkshop03.esm",
                        "kind": "added",
                        "reasons": ["added"],
                        "core": {"status": "new", "core_ref_id": None},
                        "winning_record": {
                            "base": "005BC5:DLCworkshop03.esm",
                            "pos": [1400.0, 1400.0, 70.0],
                            "rot": [0.0, 0.0, 1.0],
                            "scale": 1.0,
                            "disabled": False,
                            "is_load_door": True,
                            "xtel_door": "003CBF:DLCworkshop03.esm",
                        },
                    },
                    {
                        "form_key": "00AD1B:DLCNukaWorld.esm",
                        "winning_plugin": "DLCNukaWorld.esm",
                        "kind": "added",
                        "reasons": ["added"],
                        "core": {"status": "new", "core_ref_id": None},
                        "winning_record": {
                            "base": "018C8C:Fallout4.esm",
                            "pos": [2100.0, 2100.0, 140.0],
                            "rot": [0.0, 0.0, 0.0],
                            "scale": 1.0,
                            "disabled": False,
                            "is_load_door": True,
                            "xtel_door": "00ADB3:DLCNukaWorld.esm",
                        },
                    },
                ],
            }
            edits_path = base / "dlc_edits.json"
            edits_path.write_text(json.dumps(edits_doc, indent=2), encoding="utf-8")

            rc_build = cw_dlc.main(
                [
                    "build",
                    "--edits",
                    str(edits_path),
                    "--core",
                    str(core_dir),
                    "--dlc",
                    str(dlc_dir),
                    "--extra-manifest",
                    str(extra_manifest_path),
                    "--expected-dlc-formids-sha256",
                    dlc_fids_sha,
                    "--out",
                    str(out_dir),
                    "--dlc-doors-out",
                    str(doors_out_dir),
                ]
            )
            self.assertEqual(rc_build, 0)
            self.assertEqual(_sha256(core_dir / "FO4TerrainCore.esm"), core_sha_initial)

            rc_check = cw_dlc.main(
                [
                    "check",
                    "--out",
                    str(out_dir),
                    "--core",
                    str(core_dir),
                    "--dlc",
                    str(dlc_dir),
                    "--dlc-doors-out",
                    str(doors_out_dir),
                    "--expected-dlc-formids-sha256",
                    dlc_fids_sha,
                ]
            )
            self.assertEqual(rc_check, 0)

            rep = json.loads((out_dir / "wb5_report.json").read_text(encoding="utf-8"))
            c = rep["counts"]
            self.assertEqual(c["deleted_set_initially_disabled"], 1)
            self.assertEqual(c["overridden_moved"], 1)
            self.assertEqual(c["identical_override_noop"], 1)
            self.assertEqual(c["not_in_core"], 1)
            self.assertEqual([x["form_key"] for x in rep["not_in_core"]], ["197B2D:Fallout4.esm"])
            self.assertEqual(c["override_authored_distinct_bases"], 1)
            self.assertEqual(rep["override_authored_bases"][0]["edid"], "FO4DLC_coastbuoy01")
            self.assertEqual(rep["override_authored_bases"][0]["model"], r"fo4dlc\dlc03\coastbuoy01.nif")
            self.assertEqual(c["added_missing_refs"], 1)
            self.assertEqual(rep["missing_bases"][0]["base_edid"], "DLC03UnconvertedRock")
            self.assertEqual(c["wb5b_doors_wired"], 2)

            # Inspect written plugin binary directly
            plugin = vmad_patch.Plugin.read(str(out_dir / cw_dlc.OVERRIDE_PLUGIN_NAME))
            self.assertEqual(plugin.masters(), ["Starfield.esm", "FO4TerrainCore.esm", "FO4DLC.esm"])
            top_sigs = [g.label.decode("latin-1") for g in plugin.items if isinstance(g, vmad_patch.Group)]
            self.assertEqual(top_sigs, ["STAT", "WRLD"])

            recs = plugin.records()
            # Deleted core ref 0x0100611C -> InitiallyDisabled (0x0800), NEVER Deleted (0x0020)
            self.assertIn(0x0100611C, recs)
            self.assertTrue(recs[0x0100611C][1] & cw_dlc.RECORD_FLAG_INITIALLY_DISABLED)
            self.assertFalse(recs[0x0100611C][1] & cw_dlc.RECORD_FLAG_DELETED)

            # Moved core ref 0x01006126 -> base 0x01001811, scale 1.5, moved into cell (1, 0) = 0x01001001
            self.assertIn(0x01006126, recs)
            mov_flds = dict(fo4land.iter_subrecords(recs[0x01006126][2]))
            self.assertEqual(struct.unpack("<I", mov_flds[b"NAME"])[0], 0x01001811)
            self.assertAlmostEqual(struct.unpack("<f", mov_flds[b"XSCL"])[0], 1.5, places=5)
            self.assertEqual(recs[0x01006126][3][-1], (cw_dlc.GROUP_CELL_TEMPORARY, 0x01001001))

            # Companion FO4DLCTextures2.esm was hard-linked/copied cleanly into doors_out_dir
            self.assertTrue((doors_out_dir / "FO4DLCTextures2.esm").is_file())

            # Verify reversible install / uninstall session (refusing running Starfield.exe and restoring byte-for-byte)
            (doors_out_dir / "FO4DLC - Main.ba2").write_bytes(b"BTDX_SYNTH_MAIN")
            (doors_out_dir / "FO4DLC - Textures.ba2").write_bytes(b"BTDX_SYNTH_TEX")
            (doors_out_dir / "FO4DLCTextures2 - Textures.ba2").write_bytes(b"BTDX_SYNTH_TEX2")

            fake_game = base / "fake_starfield"
            fake_data = fake_game / "Data"
            fake_data.mkdir(parents=True)
            (fake_data / "FO4TerrainCore.esm").write_bytes((core_dir / "FO4TerrainCore.esm").read_bytes())
            fake_local = base / "fake_localappdata"
            (fake_local / "Starfield").mkdir(parents=True)
            ptxt = fake_local / "Starfield" / "Plugins.txt"
            orig_ptxt = b"*FO4Port.esm\r\n*FO4TerrainCore.esm\r\n*FO4TerrainCore_Mars.esm\r\n"
            ptxt.write_bytes(orig_ptxt)

            class _FakeRunningSys:
                def pids(self, _exe: str) -> list[int]:
                    return [4242]

            class _FakeClosedSys:
                def pids(self, _exe: str) -> list[int]:
                    return []

            old_local = os.environ.get("LOCALAPPDATA")
            os.environ["LOCALAPPDATA"] = str(fake_local)
            try:
                with self.assertRaises(RuntimeError):
                    cw_dlc.install_override_session(
                        stage_dir=out_dir,
                        dlc_doors_dir=doors_out_dir,
                        starfield_dir=fake_game,
                        system=_FakeRunningSys(),
                    )
                # WB5b F1 guard: refuses when FO4SFBridge.esm (FO4SF_LoadDoor.pex) is on disk but unticked in Plugins.txt
                (fake_data / "FO4SFBridge.esm").write_bytes(b"TES4")
                with self.assertRaisesRegex(ValueError, "FO4SFBridge.esm"):
                    cw_dlc.install_override_session(
                        stage_dir=out_dir,
                        dlc_doors_dir=doors_out_dir,
                        starfield_dir=fake_game,
                        system=_FakeClosedSys(),
                    )
                (fake_data / "FO4SFBridge.esm").unlink()

                rec_ins = cw_dlc.install_override_session(
                    stage_dir=out_dir,
                    dlc_doors_dir=doors_out_dir,
                    starfield_dir=fake_game,
                    system=_FakeClosedSys(),
                )
                self.assertEqual(
                    rec_ins["activated_plugins"],
                    ["FO4DLC.esm", "FO4DLCTextures2.esm", "FO4TerrainCore_DLC.esm"],
                )
                installed_lines = ptxt.read_text(encoding="utf-8").splitlines()
                self.assertEqual(
                    installed_lines,
                    [
                        "*FO4Port.esm",
                        "*FO4TerrainCore.esm",
                        "*FO4DLC.esm",
                        "*FO4DLCTextures2.esm",
                        "*FO4TerrainCore_DLC.esm",
                        "*FO4TerrainCore_Mars.esm",
                    ],
                )
                with self.assertRaises(RuntimeError):
                    cw_dlc.uninstall_override_session(starfield_dir=fake_game, system=_FakeRunningSys())
                res_un = cw_dlc.uninstall_override_session(starfield_dir=fake_game, system=_FakeClosedSys())
                self.assertEqual(ptxt.read_bytes(), orig_ptxt)
                self.assertFalse((fake_data / "FO4TerrainCore_DLC.esm").exists())
                self.assertFalse((fake_data / "FO4DLC.esm").exists())
                self.assertFalse(res_un["restored_fo4dlc"])
            finally:
                if old_local is None:
                    os.environ.pop("LOCALAPPDATA", None)
                else:
                    os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    unittest.main()
