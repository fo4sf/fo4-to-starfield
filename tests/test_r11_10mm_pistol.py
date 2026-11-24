"""Offline cross-OS tests for Round 11 Step 3a (A4.1 — FO4_10mmPistol + FO4_Ammo10mm ALONE).

Covers:
  1. BSConnectPoint::Parents welding (P-Grip & rotated WeaponMagazine P-Mag) on synthetic BS-130
     Fallout 4 NIFs -> BS-173 fo4_10mmpistol.nif + .mesh/.mat/.dds asset-tree verifier & negative
     tamper checks (missing .mesh/.mat/.dds, forbidden Starfield weapon material leak).
  2. Safety guards on stage_r11_10mm.py (repo/game-dir output refusal & Starfield.exe process check).
  3. Translated FO4SF_NewGameQuest.psc OnItemAdded auto-equip (EquipItem(VaultPistolBase, False, False))
     + `pistol picked equipped=True base=FO4_10mmPistol` & `pistol ammo picked ... base=FO4_Ammo10mm` logs.
  4. Binary CoreValues (`--fo4-10mm 1` vs `0`) & NewGame (`--fo4-10mm 1`, auto-detect, and `0` rollback)
     record/VMAD parity + `cross_plugin_check.validate_staged_esms` (`0` errors, strictly 1 WEAP + 1 AMMO,
     zero Laser Musket / Pipe Gun / Minigun records).
  5. Hygiene & optional real-archive staging gate (skipped cleanly on Linux CI when game archives absent).
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[1]
SRC_DIR = REPO_ROOT / "src"
WEAPONS_DIR = REPO_ROOT / "scripts" / "weapons"
NEWGAME_DIR = REPO_ROOT / "scripts" / "newgame"

for _p in (str(REPO_ROOT), str(SRC_DIR), str(WEAPONS_DIR), str(NEWGAME_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import stage_r11_10mm as s10  # noqa: E402
from fo4sf import nif, sfmesh, sfnif  # noqa: E402
from fo4sf.core import cross_plugin_check as cpc  # noqa: E402
from tests.test_exit_arrival import Reference, translated_functions  # noqa: E402

NEWGAME_PSC = NEWGAME_DIR / "FO4SF_NewGameQuest.psc"
STAGE_10MM_PY = WEAPONS_DIR / "stage_r11_10mm.py"
COREVALUES_CS = REPO_ROOT / "dotnet" / "CoreValues" / "Program.cs"
NEWGAME_CS = REPO_ROOT / "dotnet" / "NewGame" / "Program.cs"

DRIVE_PATH_RX = re.compile(r"\b[A-Za-z]:[\\/]")
IDENT_ROT = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def _av_fields(name_idx: int, trans: tuple[float, float, float], rot: tuple[float, ...], scale: float = 1.0, extra_refs: tuple[int, ...] = ()) -> bytes:
    return (
        struct.pack("<iI", name_idx, len(extra_refs))
        + (struct.pack(f"<{len(extra_refs)}i", *extra_refs) if extra_refs else b"")
        + struct.pack("<iI", -1, 0xE)
        + struct.pack("<3f", *trans)
        + struct.pack("<9f", *rot)
        + struct.pack("<fi", scale, -1)
    )


def _fo4_trishape_block(
    name_idx: int,
    pts: list[tuple[float, float, float]],
    tris: list[tuple[int, int, int]],
    trans: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bytes:
    vsize = 16 + 4 + 4 + 4
    desc = ((0x1 | 0x2 | 0x8 | 0x10 | 0x400) << 44) | (vsize // 4) | (4 << 8) | (5 << 16) | (6 << 20)
    verts = b"".join(
        struct.pack("<3ff", *p, 0.0)
        + struct.pack("<2e", 0.0, 0.0)
        + bytes([128, 128, 255, 128])
        + bytes([255, 128, 128, 128])
        for p in pts
    )
    head = (
        _av_fields(name_idx, trans, IDENT_ROT, 1.0)
        + struct.pack("<4f", 0.0, 0.0, 0.0, 10.0)
        + struct.pack("<iii", -1, -1, -1)
        + struct.pack("<Q", desc)
        + struct.pack("<IHI", len(tris), len(pts), vsize * len(pts) + 6 * len(tris))
    )
    return head + verts + b"".join(struct.pack("<HHH", *t) for t in tris)


def _connect_points_parents_block(
    name_idx: int,
    entries: list[tuple[bytes, bytes, tuple[float, float, float, float], tuple[float, float, float], float]],
) -> bytes:
    buf = bytearray(struct.pack("<iI", name_idx, len(entries)))
    for parent_b, cp_b, quat, tr, sc in entries:
        buf += struct.pack("<I", len(parent_b)) + parent_b
        buf += struct.pack("<I", len(cp_b)) + cp_b
        buf += struct.pack("<4f", *quat)
        buf += struct.pack("<4f", *tr, sc)
    return bytes(buf)


def _build_synthetic_fo4_10mm_part_nifs() -> tuple[bytes, bytes, bytes]:
    """Create synthetic BS-130 receiver (6 shapes + P-Grip & rotated WeaponMagazine P-Mag), grip, and mag NIFs."""
    rec = nif.NifFile(bs_version=130, author=b"t\x00", process_script=b"\x00", export_script=b"\x00", max_filepath=b"\x00")
    s_weap = rec.string_index(b"WEAPON")
    s_cpa = rec.string_index(b"CPA")
    s_rnode = rec.string_index(b"Pistol10mmReceiver")
    s_mnode = rec.string_index(b"WeaponMagazine")
    s_pnode = rec.string_index(b"ProjectileNode")
    s_tnode = rec.string_index(b"WeaponTrigger")
    s_bnode = rec.string_index(b"WeaponBolt")
    s_e1node = rec.string_index(b"WeaponExtra1")
    s_e2node = rec.string_index(b"WeaponExtra2")
    s_e3node = rec.string_index(b"WeaponExtra3")

    shape_names = [
        b"Pistol10mmBolt:0",
        b"Pistol10mmRelease:0",
        b"Pistol10mmHammer:0",
        b"Pistol10mmBoltRelease:0",
        b"10mmTrigger:0",
        b"Pistol10mmReceiver:0",
    ]
    shape_sids = [rec.string_index(nm) for nm in shape_names]

    # Exact FO4 10mm WeaponMagazine extraction angle (+26.52 deg around X) & P-Mag inverse quaternion:
    ang = math.radians(26.52)
    ca, sa = math.cos(ang), math.sin(ang)
    mag_node_rot = (1.0, 0.0, 0.0, 0.0, ca, sa, 0.0, -sa, ca)
    q_half = math.radians(26.52 / 2.0)
    p_mag_quat = (math.cos(q_half), math.sin(q_half), 0.0, 0.0)

    #Rotated hammer pivot (+50 deg around X) matching FO4 10mmpistol_1.nif WeaponExtra2:
    hang = math.radians(50.0)
    hca, hsa = math.cos(hang), math.sin(hang)
    hammer_rot = (1.0, 0.0, 0.0, 0.0, hca, hsa, 0.0, -hsa, hca)

    # Blocks matching real FO4 10mmpistol_1.nif hierarchy:
    #   [0] WEAPON (extra=[1], children=[2..9])
    #   [1] BSConnectPoint::Parents
    #   [2] Pistol10mmReceiver -> [4 (ProjectileNode), 14 (10mmTrigger:0), 15 (Pistol10mmReceiver:0)]
    #   [3] WeaponMagazine
    #   [4] ProjectileNode
    #   [5] WeaponTrigger
    #   [6] WeaponBolt -> [10 (Pistol10mmBolt:0)]
    #   [7] WeaponExtra1 -> [11 (Pistol10mmRelease:0)]
    #   [8] WeaponExtra2 -> [12 (Pistol10mmHammer:0)]
    #   [9] WeaponExtra3 -> [13 (Pistol10mmBoltRelease:0)]
    children_0 = [2, 3, 5, 6, 7, 8, 9]
    rec.add_block(
        "NiNode",
        _av_fields(s_weap, (0.0, 0.0, 0.0), IDENT_ROT, 1.0, extra_refs=(1,))
        + struct.pack(f"<I{len(children_0)}i", len(children_0), *children_0),
    )
    rec.add_block(
        "BSConnectPoint::Parents",
        _connect_points_parents_block(
            s_cpa,
            [
                (b"Pistol10mmReceiver", b"P-Grip", (1.0, 0.0, 0.0, 0.0), (-0.0228, -0.6014, -2.3742), 1.0),
                (b"WeaponMagazine", b"P-Mag", p_mag_quat, (-0.0052, -0.2040, -0.7424), 1.0),
                (b"Pistol10mmReceiver", b"P-Casing", (1.0, 0.0, 0.0, 0.0), (-0.0124, 2.4238, 7.8119), 1.0),
            ],
        ),
    )
    rec.add_block("NiNode", _av_fields(s_rnode, (0.0, 0.0, 0.0), IDENT_ROT, 1.0) + struct.pack("<I3i", 3, 4, 14, 15))
    rec.add_block("NiNode", _av_fields(s_mnode, (-0.0167, 0.1352, -1.2742), mag_node_rot, 1.0) + struct.pack("<I", 0))
    rec.add_block("NiNode", _av_fields(s_pnode, (-0.035, 18.497, 4.931), IDENT_ROT, 1.0) + struct.pack("<I", 0))
    rec.add_block("NiNode", _av_fields(s_tnode, (0.237, 4.674, 1.163), IDENT_ROT, 1.0) + struct.pack("<I", 0))
    rec.add_block("NiNode", _av_fields(s_bnode, (-0.104, 6.950, 0.301), IDENT_ROT, 1.0) + struct.pack("<Ii", 1, 10))
    rec.add_block("NiNode", _av_fields(s_e1node, (-0.0386, 15.6468, 2.2969), IDENT_ROT, 1.0) + struct.pack("<Ii", 1, 11))
    rec.add_block("NiNode", _av_fields(s_e2node, (0.0083, -0.9840, 3.3679), hammer_rot, 1.0) + struct.pack("<Ii", 1, 12))
    rec.add_block("NiNode", _av_fields(s_e3node, (-2.1373, 5.4487, 2.2715), IDENT_ROT, 1.0) + struct.pack("<Ii", 1, 13))

    quad_tris = [(0, 1, 2), (0, 2, 3)]
    for idx, sid in enumerate(shape_sids):
        y0 = float(idx) * 2.0
        pts = [(-1.5, y0, 1.0), (1.5, y0, 1.0), (1.5, y0 + 4.0, 5.0), (-1.5, y0 + 4.0, 5.0)]
        rec.add_block("BSTriShape", _fo4_trishape_block(sid, pts, quad_tris))
    rec.footer = struct.pack("<II", 1, 0)

    def single_part_nif(shape_nm: bytes, pts: list[tuple[float, float, float]]) -> bytes:
        fn = nif.NifFile(bs_version=130, author=b"t\x00", process_script=b"\x00", export_script=b"\x00", max_filepath=b"\x00")
        sr = fn.string_index(b"Root")
        ss = fn.string_index(shape_nm)
        fn.add_block("NiNode", _av_fields(sr, (0.0, 0.0, 0.0), IDENT_ROT, 1.0) + struct.pack("<Ii", 1, 1))
        fn.add_block("BSTriShape", _fo4_trishape_block(ss, pts, quad_tris))
        fn.footer = struct.pack("<II", 1, 0)
        return nif.serialize(fn)

    grip_bytes = single_part_nif(
        b"10mmGrip:0",
        [(-1.6, -2.0, -5.5), (1.6, -2.0, -5.5), (1.6, 2.5, 3.0), (-1.6, 2.5, 3.0)],
    )
    # Magazine local vertices run from z=-6.2 to z=+7.0 FO4 units; under cancelled R_WeaponMagazine * R_P_Mag == I,
    # its X width [-1.0, +1.0] sits strictly inside the grip [-1.6, +1.6].
    mag_bytes = single_part_nif(
        b"Magazine:0",
        [(-1.0, -1.5, -6.2), (1.0, -1.5, -6.2), (1.0, 1.5, 7.0), (-1.0, 1.5, 7.0)],
    )
    return nif.serialize(rec), grip_bytes, mag_bytes


def _write_synthetic_mat_and_dds(staging_root: Path, mat_rel: str, tex_prefix: str) -> None:
    dds_rels = [f"textures/{tex_prefix}_{suffix}.dds" for suffix in ("color", "normal", "rough")]
    for dr in dds_rels:
        dp = staging_root / dr
        dp.parent.mkdir(parents=True, exist_ok=True)
        dp.write_bytes(b"DDS " + b"\x00" * 144)
    mp = staging_root / mat_rel
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps({"Textures": dds_rels}, indent=2), encoding="utf-8")


class R11Pistol10mmTests(unittest.TestCase):
    def test_connect_point_welding_p_grip_and_p_mag_and_asset_verifier(self) -> None:
        rec_b, grip_b, mag_b = _build_synthetic_fo4_10mm_part_nifs()
        mat_weap = "materials/fo4sf/weapons/10mmpistol/10mmpistol.mat"
        welded = s10.build_welded_10mm_nif(
            rec_b,
            grip_b,
            mag_b,
            conv=None,
            weapon_collision_blob=None,
            default_material=mat_weap,
        )
        self.assertEqual(len(welded.shape_names), 8)
        self.assertIn("10mmGrip:0", welded.shape_names)
        self.assertIn("Magazine:0", welded.shape_names)
        self.assertNotIn("WEAPON", welded.node_to_shapes)
        self.assertEqual(welded.node_to_shapes["MiscA06"], ["Pistol10mmBolt:0"])
        self.assertEqual(welded.node_to_shapes["Magazine"], ["Magazine:0"])
        self.assertEqual(welded.node_to_shapes["TRIGGER"], ["10mmTrigger:0"])
        self.assertEqual(welded.node_to_shapes["WeaponExtra1"], ["Pistol10mmRelease:0"])
        self.assertEqual(welded.node_to_shapes["WeaponExtra2"], ["Pistol10mmHammer:0"])
        self.assertEqual(welded.node_to_shapes["WeaponExtra3"], ["Pistol10mmBoltRelease:0"])
        self.assertEqual(sorted(welded.node_to_shapes["Pistol10mmReceiver"]), ["10mmGrip:0", "Pistol10mmReceiver:0"])

        # Verify P-Mag quaternion cancelled WeaponMagazine's +26.52 deg tilt (world rotation == identity to 1e-4)
        rec_nf = nif.parse(rec_b)
        cps = s10.parse_connect_point_parents(rec_nf)
        nw = s10.parse_named_node_world_transforms(rec_nf)
        _, mag_wrot, _ = s10.connect_point_world_transform(nw, cps["P-Mag"])
        for got, want in zip(mag_wrot, IDENT_ROT):
            self.assertAlmostEqual(got, want, places=4)

        # Verify ProjectileNode & TRIGGER match FO4 / 70.0 metre coordinates aligned to XM2311 frame
        self.assertAlmostEqual(welded.named_nodes_m["ProjectileNode"][1], 18.497 / 70.0, places=4)
        self.assertAlmostEqual(welded.named_nodes_m["ProjectileNode"][2], 4.931 / 70.0, places=4)
        self.assertAlmostEqual(welded.named_nodes_m["TRIGGER"][1], 4.674 / 70.0, places=4)

        # Stage welded weapon + synthetic ammo NIF into a temp dir and run verify_staged_10mm
        with tempfile.TemporaryDirectory() as td:
            stg = Path(td)
            weap_p = stg / s10.WEAP_10MM_REL
            weap_p.parent.mkdir(parents=True, exist_ok=True)
            weap_p.write_bytes(welded.nif_bytes)
            for (d_hex, f_hex), mb in welded.meshes.items():
                mp = stg / "geometries" / d_hex / f"{f_hex}.mesh"
                mp.parent.mkdir(parents=True, exist_ok=True)
                mp.write_bytes(mb)
            _write_synthetic_mat_and_dds(stg, mat_weap, "fo4sf/weapons/10mmpistol/10mmpistol")

            # Build synthetic 10mmammo.nif with 1 external .mesh + .mat + 3 .dds
            mat_ammo = "materials/fo4core/ammo/10mm/10mm.mat"
            ammo_m = sfmesh.SfMesh(version=2)
            ammo_m.scale, ammo_m.positions = sfmesh.encode_positions(
                [(-0.04, -0.02, 0.0), (0.04, -0.02, 0.0), (0.04, 0.02, 0.03), (-0.04, 0.02, 0.03)]
            )
            ammo_m.triangles = [(0, 1, 2), (0, 2, 3)]
            sfmesh.build_meshlets(ammo_m)
            ammo_mb = sfmesh.serialize(ammo_m)
            ad_hex, af_hex = s10.convert_static.mesh_file_path(ammo_mb)
            (stg / "geometries" / ad_hex).mkdir(parents=True, exist_ok=True)
            (stg / "geometries" / ad_hex / f"{af_hex}.mesh").write_bytes(ammo_mb)
            pts_dec = [sfmesh.decode_position(p, ammo_m.scale) for p in ammo_m.positions]
            sph, bx = sfnif.bounds_from_points(pts_dec)
            ammo_nf = sfnif.build_static_nif(
                b"10mmammo",
                [
                    sfnif.StaticShape(
                        name=b"Box:0",
                        mesh_path=f"{ad_hex}\\{af_hex}".encode("ascii"),
                        indices_size=6,
                        num_verts=4,
                        material_path=mat_ammo,
                        sphere=sph,
                        box=bx,
                    )
                ],
            )
            ammo_p = stg / s10.AMMO_10MM_REL
            ammo_p.parent.mkdir(parents=True, exist_ok=True)
            ammo_p.write_bytes(nif.serialize(ammo_nf))
            _write_synthetic_mat_and_dds(stg, mat_ammo, "fo4core/ammo/10mm/10mm")

            res = s10.verify_staged_10mm(str(stg), require_converted_materials=True, require_collision=False)
            self.assertEqual(res["weapon"]["bs_geometry_count"], 8)
            self.assertEqual(res["weapon"]["missing_meshes"], [])
            self.assertEqual(res["weapon"]["missing_mats"], [])
            self.assertEqual(res["weapon"]["missing_dds"], [])
            self.assertIn("rigid and do not move", res["rigid_parts_disclosure"])

            # Negative 1: missing .dds texture must fail verify_staged_10mm
            dds_victim = stg / "textures" / "fo4sf" / "weapons" / "10mmpistol" / "10mmpistol_rough.dds"
            dds_victim.unlink()
            with self.assertRaises(s10.Stage10mmError):
                s10.verify_staged_10mm(str(stg), require_converted_materials=True, require_collision=False)
            dds_victim.write_bytes(b"DDS " + b"\x00" * 144)

            # Negative 2: missing .mesh file must fail verify_staged_10mm
            first_mesh = next((stg / "geometries").rglob("*.mesh"))
            saved_mesh = first_mesh.read_bytes()
            first_mesh.unlink()
            with self.assertRaises(s10.Stage10mmError):
                s10.verify_staged_10mm(str(stg), require_converted_materials=True, require_collision=False)
            first_mesh.write_bytes(saved_mesh)

            # Negative 3: Starfield donor weapon material leak must fail verify_staged_10mm
            leaked = s10.build_welded_10mm_nif(
                rec_b, grip_b, mag_b, conv=None, weapon_collision_blob=None, default_material=r"Materials\Weapons\M1919\M1919.mat"
            )
            weap_p.write_bytes(leaked.nif_bytes)
            with self.assertRaises(s10.Stage10mmError):
                s10.verify_staged_10mm(str(stg), require_converted_materials=False, require_collision=False)

    def test_safety_guards_refuse_repo_game_dir_and_running_starfield(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fake_fo4 = os.path.join(td, "fo4_data")
            fake_sf = os.path.join(td, "sf_data")
            non_empty = os.path.join(td, "non_empty")
            os.makedirs(fake_fo4)
            os.makedirs(fake_sf)
            os.makedirs(non_empty)
            Path(non_empty, "x.txt").write_text("x", encoding="utf-8")

            with self.assertRaises(s10.Stage10mmError):
                s10.refuse_unsafe_staging_dir(str(REPO_ROOT / "bad_out"))
            with self.assertRaises(s10.Stage10mmError):
                s10.refuse_unsafe_staging_dir(os.path.join(fake_fo4, "sub"), fo4_data=fake_fo4)
            with self.assertRaises(s10.Stage10mmError):
                s10.refuse_unsafe_staging_dir(os.path.join(fake_sf, "sub"), sf_data=fake_sf)
            with self.assertRaises(s10.Stage10mmError):
                s10.refuse_unsafe_staging_dir(non_empty)

            clean_out = os.path.join(td, "clean_stage")
            s10.refuse_unsafe_staging_dir(clean_out, fo4_data=fake_fo4, sf_data=fake_sf)

        with mock.patch.object(s10.System, "pids", return_value=[4242]):
            with self.assertRaises(s10.Stage10mmError):
                s10.require_starfield_not_running()

    def test_newgame_psc_on_item_added_auto_equips_10mm_and_logs_ammo(self) -> None:
        psc = NEWGAME_PSC.read_text(encoding="utf-8")
        funcs = ("EnsureVaultInteractivesRegistered", "ObjectReference.OnItemAdded")
        vars_csv = (
            "itemWatchRegistered, pipboyRegistered, cogDoorRegistered, cogDoorWatchedRef, "
            "consoleRegistered, consoleWatchedRef, portConsoleRegistered, portConsoleWatchedRef, "
            "consoleOpening, pistolPickedLogged"
        )
        player = Reference(None, (-57.0, 30.0, 1.29), form_id=0x00000014)
        equip_calls: list[tuple[object, bool, bool]] = []
        equipped_set: set[object] = set()
        player.EquipItem = lambda item, prevent=False, silent=False: (  # type: ignore[attr-defined]
            equip_calls.append((item, prevent, silent)),
            equipped_set.add(item),
        )
        player.IsEquipped = lambda item: item in equipped_set  # type: ignore[attr-defined]

        pistol_10mm = object()
        ammo_10mm = object()
        unrelated_item = object()
        traces: list[str] = []
        call_order: list[tuple[object, ...]] = []

        def get_form(fid: int, plg: str):
            if plg == "FO4SFCoreValues.esm" and fid == 0x000898:
                return ammo_10mm
            return None

        ns = dict(
            Trace=traces.append,
            itemWatchRegistered=False,
            pipboyRegistered=True,
            cogDoorRegistered=True,
            cogDoorWatchedRef=None,
            consoleRegistered=True,
            consoleWatchedRef=None,
            portConsoleRegistered=True,
            portConsoleWatchedRef=None,
            consoleOpening=False,
            pistolPickedLogged=False,
            VaultPistolBase=pistol_10mm,
            VaultPistolId=0x000899,
            PipboyCorpseRef=None,
            GearDoorConsoleRef=None,
            CogDoorId=0,
            ConsoleRefId=0,
            LiftId=0x126F,
            VaultPlugin="FO4Port.esm",
            TestModeGlobal=None,
            Game=SimpleNamespace(GetPlayer=lambda: player, GetFormFromFile=get_form),
            AddInventoryEventFilter=lambda f: call_order.append(("filter", f)),
            RegisterForRemoteEvent=lambda target, ev: call_order.append(("register", target, ev)),
            GetStage=lambda: 20,
        )
        exec(compile(translated_functions(psc, funcs, vars_csv), str(NEWGAME_PSC), "exec"), ns)

        ns["EnsureVaultInteractivesRegistered"]()
        self.assertEqual(call_order[0], ("filter", pistol_10mm))
        self.assertEqual(call_order[1], ("filter", ammo_10mm))
        self.assertEqual(call_order[2], ("register", player, "OnItemAdded"))

        # Unrelated item does nothing
        ns["OnItemAdded"](player, unrelated_item, 1, None, None, 0)
        self.assertEqual(equip_calls, [])
        self.assertFalse(ns["pistolPickedLogged"])

        # Picking up FO4_10mmPistol auto-equips into hand and logs equipped=True base=FO4_10mmPistol
        ns["OnItemAdded"](player, pistol_10mm, 1, None, None, 0)
        self.assertTrue(ns["pistolPickedLogged"])
        self.assertEqual(equip_calls, [(pistol_10mm, False, False)])
        self.assertTrue(any(t.startswith("pistol picked item=") and "count=1" in t for t in traces), traces)
        self.assertTrue(
            any(t.startswith("pistol picked ") and "equipped=True" in t and "base=FO4_10mmPistol" in t for t in traces),
            traces,
        )

        # Picking up FO4_Ammo10mm AFTER pistol pickup still logs ammo pickup verification
        ns["OnItemAdded"](player, ammo_10mm, 48, None, None, 0)
        self.assertTrue(
            any(t.startswith("pistol ammo picked item=") and "count=48 base=FO4_Ammo10mm" in t for t in traces),
            traces,
        )

    @unittest.skipUnless(shutil.which("dotnet") is not None, "dotnet SDK required for binary .esm verification")
    def test_dotnet_corevalues_and_newgame_fo4_10mm_and_cross_plugin_parity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            cv_proj = REPO_ROOT / "dotnet" / "CoreValues" / "CoreValues.csproj"
            ng_proj = REPO_ROOT / "dotnet" / "NewGame" / "NewGame.csproj"

            # CoreValues selftest exercises --fo4-10mm 1, --fo4-10mm 0 rollback, determinism & negative tamper checks
            r_cv = subprocess.run(
                ["dotnet", "run", "--project", str(cv_proj), "-c", "Release", "--", "selftest", str(tmp / "cv_st")],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(r_cv.returncode, 0, r_cv.stdout + "\n" + r_cv.stderr)
            self.assertIn("CoreValues selftest: ok", r_cv.stdout)

            # Inspect generated pistol10mm_on vs pistol10mm_off binary plugins directly:
            # strictly 1 AMMO (0x000898 FO4_Ammo10mm) + 1 WEAP (0x000899 FO4_10mmPistol), ZERO other guns!
            cv_10mm_esm = tmp / "cv_st" / "pistol10mm_on" / "FO4SFCoreValues.esm"
            cv_off_esm = tmp / "cv_st" / "pistol10mm_off" / "FO4SFCoreValues.esm"
            rep_on = cpc.inspect_esm_binary(str(cv_10mm_esm))
            rep_off = cpc.inspect_esm_binary(str(cv_off_esm))

            weaps_on = {fid: edid for fid, (rt, edid) in rep_on.own_records.items() if rt == "WEAP"}
            ammos_on = {fid: edid for fid, (rt, edid) in rep_on.own_records.items() if rt == "AMMO"}
            self.assertEqual(weaps_on, {0x000899: "FO4_10mmPistol"})
            self.assertEqual(ammos_on, {0x000898: "FO4_Ammo10mm"})
            self.assertEqual(
                {fid: rt for fid, (rt, _) in rep_off.own_records.items() if rt in ("WEAP", "AMMO")},
                {},
            )

            # Verify Step 4 P5 (--fo4-p5-weapons 1 vs 0 rollback) binary outputs from CoreValues selftest:
            cv_p5_on = cpc.inspect_esm_binary(str(tmp / "cv_st" / "p5_weapons_on" / "FO4SFCoreValues.esm"))
            cv_p5_only10 = cpc.inspect_esm_binary(str(tmp / "cv_st" / "p5_only_10mm" / "FO4SFCoreValues.esm"))
            self.assertEqual(
                {fid: edid for fid, (rt, edid) in cv_p5_only10.own_records.items() if rt == "WEAP"},
                {0x000899: "FO4_10mmPistol"},
            )
            self.assertEqual(
                {fid: edid for fid, (rt, edid) in cv_p5_on.own_records.items() if rt == "WEAP"},
                {
                    0x000899: "FO4_10mmPistol",
                    0x00089A: "FO4_Baton",
                    0x00089D: "FO4_LaserMusket",
                    0x00089E: "FO4_CompPrestonLaserMusket",
                    0x0008A0: "FO4_Minigun",
                },
            )
            self.assertEqual(
                {fid: edid for fid, (rt, edid) in cv_p5_on.own_records.items() if rt == "AMMO"},
                {
                    0x000898: "FO4_Ammo10mm",
                    0x00089B: "FO4_AmmoFusionCell",
                    0x00089C: "FO4_CompanionAmmoFusionCell",
                    0x00089F: "FO4_Ammo5mm",
                },
            )

            # Run NewGame selftest (leaves cv_with_10mm and cv_rollback_10mm0 under out/) and verify cross_plugin_check
            ng_st = tmp / "ng_st"
            r_ng = subprocess.run(
                ["dotnet", "run", "--project", str(ng_proj), "-c", "Release", "--", "selftest", str(ng_st)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(r_ng.returncode, 0, r_ng.stdout + "\n" + r_ng.stderr)
            self.assertIn("selftest pass", r_ng.stdout)

            # Validate staged binary pair [FO4SFCoreValues.esm (--fo4-10mm 1), FO4SFNewGame.esm (auto-detected 10mm)]
            ng_10mm_esm = ng_st / "out" / "cv_with_10mm" / "FO4SFNewGame.esm"
            rep_ng_10 = cpc.inspect_esm_binary(str(ng_10mm_esm))
            self.assertIn(
                ("REFR:FO4SF_Vault111PistolRef.NAME", "FO4SFCoreValues.esm", 0x000899),
                rep_ng_10.cross_plugin_item_refs,
            )
            self.assertIn(
                ("REFR:FO4SF_Vault111AmmoRef.NAME", "FO4SFCoreValues.esm", 0x000898),
                rep_ng_10.cross_plugin_item_refs,
            )
            catalog, dups = cpc.build_writer_catalog(str(REPO_ROOT))
            self.assertEqual(dups, [])
            # NewGame.SelfTest() places synthetic Starfield.esm MQ101 & MQ101Debug at 0x000902 & 0x000900:
            catalog["Starfield.esm"][0x000902] = ("QUST", "MQ101")
            catalog["Starfield.esm"][0x000900] = ("GLOB", "MQ101Debug")
            psc_props = cpc.collect_psc_props_by_script(str(REPO_ROOT))
            errs = cpc.validate_staged_esms([str(cv_10mm_esm), str(ng_10mm_esm)], catalog, psc_props)
            self.assertEqual(errs, [], f"validate_staged_esms errors: {errs}")

    def test_step_3a_hygiene_and_strict_single_gun_scope(self) -> None:
        for path in (STAGE_10MM_PY, HERE, COREVALUES_CS, NEWGAME_CS, NEWGAME_PSC):
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM in {path.name}")
            txt = raw.decode("utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(txt), f"Drive-letter path leak in {path.name}")

        s10_txt = STAGE_10MM_PY.read_text(encoding="utf-8")
        for forbidden_edid in ("FO4_LaserMusket", "FO4_PipePistol", "FO4_PipeRifle", "FO4_Minigun"):
            self.assertNotIn(forbidden_edid, s10_txt, f"Out-of-scope gun {forbidden_edid} leaked into stage_r11_10mm.py")

        cv_txt = COREVALUES_CS.read_text(encoding="utf-8")
        for gate_tok in ("--fo4-10mm", "--fo4-p5-weapons", "--fo4-arsenal", "opts.Fo4P5Weapons != 0", "opts.Fo4Arsenal != 0"):
            self.assertIn(gate_tok, cv_txt, f"Missing CoreValues CLI/gating token {gate_tok}")
        if shutil.which("dotnet") is not None:
            cv_proj = REPO_ROOT / "dotnet" / "CoreValues" / "CoreValues.csproj"
            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td)
                r_st = subprocess.run(
                    ["dotnet", "run", "--project", str(cv_proj), "-c", "Release", "--", "selftest", str(tmp / "st")],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(r_st.returncode, 0, r_st.stdout + "\n" + r_st.stderr)
                ars_sf = tmp / "st" / "arsenal_fixture" / "Starfield.esm"
                only10_dir = tmp / "only_10mm"
                r_bld = subprocess.run(
                    [
                        "dotnet", "run", "--project", str(cv_proj), "-c", "Release", "--",
                        "build", str(ars_sf), str(only10_dir),
                        "--fo4-10mm", "1", "--fo4-p5-weapons", "0", "--fo4-arsenal", "0",
                    ],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(r_bld.returncode, 0, r_bld.stdout + "\n" + r_bld.stderr)
                rep_only10 = cpc.inspect_esm_binary(str(only10_dir / "FO4SFCoreValues.esm"))
                weap_edids = {edid for rt, edid in rep_only10.own_records.values() if rt == "WEAP"}
                self.assertEqual(weap_edids, {"FO4_10mmPistol"})
                for gated_pipe in ("FO4_PipePistol", "FO4_PipeRifle"):
                    self.assertNotIn(gated_pipe, weap_edids)

    @unittest.skipUnless(
        bool(os.environ.get("FO4SF_FO4_DATA")) and bool(os.environ.get("FO4SF_STARFIELD_DATA")),
        "Set FO4SF_FO4_DATA and FO4SF_STARFIELD_DATA to run real-archive 10mm staging test",
    )
    def test_optional_real_archive_10mm_staging_when_present(self) -> None:
        if s10.System.pids(s10.GAME_EXE):
            self.skipTest(f"{s10.GAME_EXE} is currently running; skipping real-archive read")
        fo4_data = os.environ["FO4SF_FO4_DATA"]
        sf_data = os.environ["FO4SF_STARFIELD_DATA"]
        with tempfile.TemporaryDirectory() as td:
            stg = os.path.join(td, "stage_10mm")
            manifest = s10.stage_r11_10mm(fo4_data, sf_data, stg)
            self.assertEqual(len(manifest["welded_shapes"]), 8)
            self.assertEqual(manifest["verification"]["weapon"]["missing_dds"], [])
            self.assertEqual(manifest["verification"]["ammo"]["missing_dds"], [])


if __name__ == "__main__":
    unittest.main()
