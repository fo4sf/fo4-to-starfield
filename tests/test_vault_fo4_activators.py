"""Offline unit, tamper-rejection, cross-OS path, and 3D raycast hit-coverage tests for A1(c):
Kept Fallout-Look Vault 111 Pip-Boy Pickup (0A00080E / 0A00080F) & Gear-Door Console (0A000818 / 0A000819).

Proves offline (100% synthetic, zero game archives required on Linux CI):
  1. Stage-built BS-173 NIFs carry ZERO Starfield geometry/materials (no WallTech08.nif / Deimos / EditorMarker),
     100% Fallout 4 FO4Port BSGeometry + BSLightingShaderProperty + MaterialID CRC32s, BSXFlags=0x2, and a single
     root-node layer-1 (COL_STATIC) watertight convex Havok body (hknpBoxShape -> hknpConvexShape).
  2. SkeletonHand01 is stripped from v111_pipboy_pickup.nif so 0A00080F renders ONLY the Fallout 4 Pip-Boy 3000.
  3. 100% 3D raycast hit coverage across both standing (1.65 m) and crouching (1.05 m) player eye heights in the
     Vault 111 control room: every sightline aimed at the Fallout 4 Pip-Boy 3000 or Fallout 4 Vault Door Console
     intersects our layer-1 activator hull strictly before FO4Port.esm's underlying 02001616 / 02001319 bodies.
  4. Cross-OS path safety (posixpath simulation) and make_newgame verify/fold + make_core_bundle output extraction.
"""
from __future__ import annotations

import io
import json
import math
import os
import posixpath
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Sequence, Tuple
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "src", ROOT / "scripts" / "newgame", ROOT / "scripts" / "core", ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fo4sf import hktagfile, nif, sfbodies, sfcollision, sfnif  # noqa: E402
import ba2_fixture  # noqa: E402
import make_core_bundle as mcb  # noqa: E402
import make_newgame as ng  # noqa: E402
import vault_fo4_activators as vfa  # noqa: E402
from test_sfbodies import TagWriter, add_bodies, body_types  # noqa: E402


def build_synthetic_box_template(layer: int = 1) -> bytes:
    """Build a valid 6,168-byte Havok TAG0 hknpBoxShape template blob with configurable collision layer."""
    def _make(pad: int) -> bytearray:
        w = TagWriter()
        body_types(w, "hknpBoxShape")
        w.type("hknpBoxShape", 800)
        w.type("p" * pad, 4)
        box_item = w.item("hknpBoxShape", bytes(800))
        add_bodies(w, [(box_item, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))], layer=layer)
        return bytearray(w.build())

    blob = _make(1 + sfcollision.BLOB_SIZE - len(_make(1)))
    tf = hktagfile.Tagfile(bytes(blob))
    box = next(it for it in tf.items[1:] if tf.type_name(it.type) == "hknpBoxShape")
    assert len(blob) == sfcollision.BLOB_SIZE
    assert tf.data_start + box.offset <= 528 < 784 <= tf.data_start + box.offset + 800
    for k in range(3):
        struct.pack_into("<3f", blob, 528 + 16 * k, *(float(a == k) for a in range(3)))
    return bytes(blob)


def build_synthetic_fo4port_nif(
    shapes: Sequence[Tuple[bytes, bytes, str, Tuple[float, float, float], Tuple[float, float, float, float, float, float]]],
) -> bytes:
    """Build a synthetic converted FO4Port BS-173 NIF containing BSGeometry + BSLightingShaderProperty blocks."""
    f = nif.NifFile(
        endian=1,
        user_version=12,
        bs_version=173,
        author=b"\x00",
        unknown_int=0,
        export_script=b"\x00",
        sf_data=b"\x7a\x00",
    )
    s_root = f.string_index(b"Scene Root")
    s_bsx = f.string_index(b"BSX")
    s_matid = f.string_index(b"MaterialID")
    ident_rot = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    ident_xf = struct.pack("<3f9ff", 0.0, 0.0, 0.0, *ident_rot, 1.0)

    first = 2
    children = [first + 3 * i for i in range(len(shapes))]
    f.add_block(
        "NiNode",
        struct.pack("<iIiiI", s_root, 1, 1, -1, 0xE)
        + ident_xf
        + struct.pack("<iI", -1, len(children))
        + struct.pack(f"<{len(children)}i", *children),
    )
    f.add_block("BSXFlags", struct.pack("<iI", s_bsx, 0x2))

    for i, (nm, mesh_path, mat_path, tr, box6) in enumerate(shapes):
        base = first + 3 * i
        sphere = (box6[0], box6[1], box6[2], max(box6[3], box6[4], box6[5]))
        g = sfnif.BSGeometry(
            name_idx=f.string_index(nm),
            extra_refs=[base + 1],
            flags=0xE,
            translation=tr,
            rotation=ident_rot,
            scale=1.0,
            sphere=sphere,
            box=box6,
            shader=base + 2,
            meshes=[sfnif.MeshRef(12, 8, 64, mesh_path), None, None, None],
        )
        f.add_block("BSGeometry", sfnif.build_bsgeometry(g))
        f.add_block("NiIntegerExtraData", struct.pack("<iI", s_matid, sfnif.material_id(mat_path)))
        f.add_block(
            "BSLightingShaderProperty",
            struct.pack("<iIi", f.string_index(mat_path.encode("latin-1")), 0, -1),
        )
    f.footer = struct.pack("<II", 1, 0)
    return nif.serialize(f)


def gamebryo_rot_matrix(rx: float, ry: float, rz: float) -> Tuple[Tuple[float, float, float], ...]:
    """Gamebryo / Starfield REFR rotation matrix R = Rx(-rx) * Ry(-ry) * Rz(-rz) (matches Program.cs PipboyWorldCenter & ConsoleWorldPos)."""
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)

    # Rz(-rz)
    rz_m = (
        (cz, sz, 0.0),
        (-sz, cz, 0.0),
        (0.0, 0.0, 1.0),
    )
    # Ry(-ry)
    ry_m = (
        (cy, 0.0, -sy),
        (0.0, 1.0, 0.0),
        (sy, 0.0, cy),
    )
    # Rx(-rx)
    rx_m = (
        (1.0, 0.0, 0.0),
        (0.0, cx, sx),
        (0.0, -sx, cx),
    )

    def _mul(a, b):
        return tuple(
            tuple(sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3))
            for r in range(3)
        )

    return _mul(rx_m, _mul(ry_m, rz_m))


def local_to_world(
    pos: Tuple[float, float, float],
    rot: Tuple[float, float, float],
    local_pt: Tuple[float, float, float],
) -> Tuple[float, float, float]:
    m = gamebryo_rot_matrix(*rot)
    return (
        pos[0] + m[0][0] * local_pt[0] + m[0][1] * local_pt[1] + m[0][2] * local_pt[2],
        pos[1] + m[1][0] * local_pt[0] + m[1][1] * local_pt[1] + m[1][2] * local_pt[2],
        pos[2] + m[2][0] * local_pt[0] + m[2][1] * local_pt[1] + m[2][2] * local_pt[2],
    )


def ray_hit_obb(
    origin: Tuple[float, float, float],
    direction: Tuple[float, float, float],
    obj_pos: Tuple[float, float, float],
    obj_rot: Tuple[float, float, float],
    box_center: Tuple[float, float, float],
    box_half: Tuple[float, float, float],
) -> Optional[float]:
    """Return distance `t >= 0` along normalized `direction` where ray hits oriented box, or None on miss."""
    m = gamebryo_rot_matrix(*obj_rot)
    rel = (origin[0] - obj_pos[0], origin[1] - obj_pos[1], origin[2] - obj_pos[2])
    # Transform into object-local space via R^T:
    ro = tuple(m[0][a] * rel[0] + m[1][a] * rel[1] + m[2][a] * rel[2] for a in range(3))
    rd = tuple(m[0][a] * direction[0] + m[1][a] * direction[1] + m[2][a] * direction[2] for a in range(3))

    t_min = 0.0
    t_max = float("inf")
    for a in range(3):
        lo = box_center[a] - box_half[a]
        hi = box_center[a] + box_half[a]
        if abs(rd[a]) < 1e-12:
            if ro[a] < lo or ro[a] > hi:
                return None
        else:
            t1 = (lo - ro[a]) / rd[a]
            t2 = (hi - ro[a]) / rd[a]
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
            if t_min > t_max:
                return None
    return t_min


class VaultFalloutActivatorsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.box_tmpl = build_synthetic_box_template(layer=1)
        self.pb_src = build_synthetic_fo4port_nif(
            [
                (
                    b"PipboyBody:0",
                    b"fo4port\\animobjects\\npcpipboygroundtake01\\pb_body",
                    r"materials\fo4port\animobjects\pipboy\pipboy01.mat",
                    (0.024, 0.816, 0.068),
                    (0.0, 0.0, 0.0, 0.100, 0.098, 0.076),
                ),
                (
                    b"PipboyScreen:1",
                    b"fo4port\\animobjects\\npcpipboygroundtake01\\pb_screen",
                    r"materials\fo4port\animobjects\pipboy\pipboyscreen01.mat",
                    (0.030, 0.820, 0.095),
                    (0.0, 0.0, 0.0, 0.045, 0.040, 0.015),
                ),
                (
                    b"SkeletonHand01:0",
                    b"fo4port\\animobjects\\npcpipboygroundtake01\\skel_hand",
                    r"materials\fo4port\actors\character\skeleton\skeletonhand.mat",
                    (0.180, 0.850, 0.020),
                    (0.0, 0.0, 0.0, 0.120, 0.080, 0.040),
                ),
            ]
        )
        self.con_src = build_synthetic_fo4port_nif(
            [
                (
                    b"V111GearDoorConsole01:0",
                    b"fo4port\\interiors\\vault\\vault111\\console_deck",
                    r"materials\fo4port\interiors\vault\v111console01.mat",
                    (0.0, 0.0, 0.0),
                    (0.0, 0.0, 0.0, 0.538, 0.219, 0.105),
                ),
                (
                    b"Button:0",
                    b"fo4port\\interiors\\vault\\vault111\\console_button",
                    r"materials\fo4port\interiors\vault\v111buttonred01.mat",
                    (-0.189, -0.025, 0.115),
                    (0.0, 0.0, 0.0, 0.050, 0.050, 0.025),
                ),
                (
                    b"Lid:2",
                    b"fo4port\\interiors\\vault\\vault111\\console_lid",
                    r"materials\fo4port\interiors\vault\v111glass01.mat",
                    (-0.189, -0.025, 0.126),
                    (0.0, 0.0, 0.0, 0.104, 0.080, 0.022),
                ),
            ]
        )

    def test_synthetic_nif_generation_and_skeleton_exclusion(self) -> None:
        pb_nif, con_nif = vfa.build_pair_from_source_bytes(self.pb_src, self.con_src, self.box_tmpl)

        pb_meta = vfa.verify_activator_nif_bytes(
            pb_nif,
            expected_center=vfa.PIPBOY_COLLISION_CENTER,
            expected_half=vfa.PIPBOY_COLLISION_HALF,
        )
        con_meta = vfa.verify_activator_nif_bytes(
            con_nif,
            expected_center=vfa.CONSOLE_COLLISION_CENTER,
            expected_half=vfa.CONSOLE_COLLISION_HALF,
        )

        # SkeletonHand01:0 stripped from Pip-Boy pickup; all 3 console shapes preserved
        self.assertEqual(pb_meta["shape_count"], 2)
        self.assertEqual(con_meta["shape_count"], 3)
        self.assertEqual(pb_meta["bsx_flags"], 0x2)
        self.assertEqual(con_meta["bsx_flags"], 0x2)
        self.assertEqual(pb_meta["collision_layer"], 1)
        self.assertEqual(con_meta["collision_layer"], 1)
        self.assertEqual(pb_meta["collision_shape"], "hknpBoxShape")
        self.assertEqual(con_meta["collision_shape"], "hknpBoxShape")
        self.assertEqual(pb_meta["starfield_tris"], 0)
        self.assertEqual(con_meta["starfield_tris"], 0)

        # Verify SkeletonHand string is completely absent and BSGeometry bounds remain mesh-local while translation shifts
        nf_pb = nif.parse(pb_nif)
        joined_strings = b"|".join(nf_pb.strings).lower()
        self.assertNotIn(b"skeletonhand", joined_strings)
        self.assertNotIn(b"walltech", joined_strings)
        self.assertNotIn(b"editormarker", joined_strings)
        g0 = sfnif.parse_bsgeometry(nf_pb.blocks[4])
        self.assertAlmostEqual(g0.translation[0], 0.024 + vfa.PIPBOY_GEOM_SHIFT[0], places=5)
        self.assertAlmostEqual(g0.translation[1], 0.816 + vfa.PIPBOY_GEOM_SHIFT[1], places=5)
        self.assertAlmostEqual(g0.translation[2], 0.068 + vfa.PIPBOY_GEOM_SHIFT[2], places=5)
        self.assertEqual(g0.box[:3], (0.0, 0.0, 0.0))

    def test_tamper_and_starfield_mesh_leak_rejection(self) -> None:
        pb_nif, _ = vfa.build_pair_from_source_bytes(self.pb_src, self.con_src, self.box_tmpl)

        # 1. Layer-2 (COL_ANIMSTATIC) Havok template must be refused
        layer2_tmpl = build_synthetic_box_template(layer=2)
        with self.assertRaisesRegex(vfa.ActivatorNifError, "layer-1"):
            vfa.build_pair_from_source_bytes(self.pb_src, self.con_src, layer2_tmpl)

        # 2. BSXFlags = 0x2A (EDITOR_MARKER bit) must be refused on verify
        nf_marker_flag = nif.parse(pb_nif)
        s_bsx, _ = struct.unpack_from("<iI", nf_marker_flag.blocks[1], 0)
        nf_marker_flag.blocks[1] = struct.pack("<iI", s_bsx, 0x2A)
        with self.assertRaisesRegex(vfa.ActivatorNifError, "BSXFlags == 0x2"):
            vfa.verify_activator_nif_bytes(nif.serialize(nf_marker_flag))

        # 3. Starfield Deimos / WallTech08 material or string leak must be refused
        leaked_src = build_synthetic_fo4port_nif(
            [
                (
                    b"WallTech08:0",
                    b"ships\\interior\\deimos\\walltech08",
                    r"materials\ships\interior\deimos\paintedmetalpanel01_white01.mat",
                    (0.0, 0.0, 0.0),
                    (0.0, 0.0, 0.0, 0.14, 0.07, 0.08),
                )
            ]
        )
        with self.assertRaisesRegex(vfa.ActivatorNifError, "refused non-FO4Port material"):
            vfa.extract_fo4port_shapes(leaked_src)

        # 4. Tampered MaterialID CRC32 must be refused
        nf_bad_crc = nif.parse(pb_nif)
        s_matid, got_crc = struct.unpack_from("<iI", nf_bad_crc.blocks[5], 0)
        nf_bad_crc.blocks[5] = struct.pack("<iI", s_matid, got_crc ^ 0xFFFFFFFF)
        with self.assertRaisesRegex(vfa.ActivatorNifError, "MaterialID"):
            vfa.verify_activator_nif_bytes(nif.serialize(nf_bad_crc))

        # 5. Live game install guard refuses staging if Starfield.exe is running
        with tempfile.TemporaryDirectory() as td:
            fake_game = Path(td) / "Starfield"
            fake_data = fake_game / "Data"
            fake_data.mkdir(parents=True)
            (fake_game / vfa.GAME_EXE).write_bytes(b"MZ")
            fake_sys = type("FakeSys", (), {"pids": staticmethod(lambda exe: [4242] if exe == vfa.GAME_EXE else [])})()
            with self.assertRaisesRegex(vfa.ActivatorNifError, "is running"):
                vfa.ensure_game_closed_if_live_install(str(fake_data), system=fake_sys)

    def test_standing_and_crouching_3d_raycast_coverage_pipboy_and_console(self) -> None:
        # Verify Gamebryo rotation helper matches Program.cs PipboyWorldCenter & ConsoleWorldPos formulas
        pb_pos = (-54.455524, -0.324950, 0.630884)
        pb_rot = (0.0, 0.0, 3.804386)
        pb_center = local_to_world(pb_pos, pb_rot, vfa.PIPBOY_LOCAL_OFFSET)
        self.assertAlmostEqual(pb_center[0], -55.0488, places=3)
        self.assertAlmostEqual(pb_center[1], -0.9224, places=3)
        self.assertAlmostEqual(pb_center[2], 0.7759, places=3)

        con_pos = (-54.3644, -1.8748, 1.6940)
        con_rot = (math.pi / 4.0, 0.0, math.pi)
        con_center = local_to_world(con_pos, con_rot, (0.0, 0.0, vfa.CONSOLE_NORMAL_OFFSET))
        self.assertAlmostEqual(con_center[0], -54.3644, places=3)
        self.assertAlmostEqual(con_center[1], -1.8147, places=3)
        self.assertAlmostEqual(con_center[2], 1.7541, places=3)

        # Vault 111 control room floor Z ~ 0.589 m -> standing eye Z = 2.239 m (+1.65 m), crouching eye Z = 1.639 m (+1.05 m)
        eye_heights_world = (0.589 + 1.65, 0.589 + 1.05)

        # --- Part A: Floor Pip-Boy 3000 (0A00080F vs FO4Port.esm:0x01001616 Collision0 hknpCompressedMeshShape) ---
        # Forensic bounds of 0x01001616 Collision0 in pb_pos frame: [-0.0772..+0.2766, +0.7636..+0.9081, -0.0023..+0.1413]
        port_pb_coll_center = ((0.2766 - 0.0772) * 0.5, (0.9081 + 0.7636) * 0.5, (0.1413 - 0.0023) * 0.5)
        port_pb_coll_half = ((0.2766 + 0.0772) * 0.5, (0.9081 - 0.7636) * 0.5, (0.1413 + 0.0023) * 0.5)

        # 5x5x3 target grid across the Fallout 4 Pip-Boy 3000 wrist unit visual bounds in pb_pos frame:
        # [-0.0765..+0.1239, +0.7183..+0.9139, 0.00..+0.1439]
        pb_targets = [
            local_to_world(
                pb_pos,
                pb_rot,
                (
                    -0.070 + 0.047 * ix,
                    0.725 + 0.045 * iy,
                    0.010 + 0.065 * iz,
                ),
            )
            for ix in range(5)
            for iy in range(5)
            for iz in range(3)
        ]

        pb_rays = 0
        pb_hits_first = 0
        for eye_z in eye_heights_world:
            for radius in (0.55, 1.00, 1.45, 1.90):
                for az_idx in range(12):
                    ang = 2.0 * math.pi * az_idx / 12.0
                    eye = (pb_center[0] + radius * math.cos(ang), pb_center[1] + radius * math.sin(ang), eye_z)
                    for tgt in pb_targets:
                        dx, dy, dz = tgt[0] - eye[0], tgt[1] - eye[1], tgt[2] - eye[2]
                        ln = math.sqrt(dx * dx + dy * dy + dz * dz)
                        d = (dx / ln, dy / ln, dz / ln)
                        t_acti = ray_hit_obb(eye, d, pb_center, pb_rot, vfa.PIPBOY_COLLISION_CENTER, vfa.PIPBOY_COLLISION_HALF)
                        t_port = ray_hit_obb(eye, d, pb_pos, pb_rot, port_pb_coll_center, port_pb_coll_half)
                        pb_rays += 1
                        if t_acti is not None and (t_port is None or t_acti < t_port):
                            pb_hits_first += 1

        self.assertGreaterEqual(pb_rays, 7200)
        self.assertEqual(pb_hits_first, pb_rays, f"Pip-Boy raycast coverage {pb_hits_first}/{pb_rays} (< 100%)")

        # --- Part B: Vault Door Console (0A000819 vs all 5 COL_STATIC convex hulls of FO4Port.esm:0x01001319) ---
        # Forensic bounds of the 5 convex hulls in v111geardoorconsole01.nif (console-local space, max z = +0.1539 m):
        port_con_boxes = (
            ((0.0, 0.0, -0.0247), (0.5379, 0.2194, 0.1292)),       # main console body (z <= +0.1045)
            ((-0.1893, -0.0250, 0.1262), (0.1041, 0.0800, 0.0277)), # glass safety lid Lid:2 (z <= +0.1539)
            ((-0.1895, -0.0250, 0.1150), (0.0504, 0.0504, 0.0246)), # red button Button:0 (z <= +0.1396)
            ((0.2150, -0.0150, 0.1020), (0.1150, 0.0950, 0.0380)),  # right Pip-Boy plug socket (z <= +0.1400)
            ((0.0, 0.1450, 0.0650), (0.5200, 0.0700, 0.0550)),      # upper console bezel (z <= +0.1200)
        )

        # Target points across every interactive zone on the Fallout 4 console face (button, glass lid, socket, center label, wings):
        con_targets = [
            local_to_world(con_pos, con_rot, (-0.48 + 0.12 * ix, -0.18 + 0.09 * iy, 0.105))
            for ix in range(9)
            for iy in range(5)
        ] + [
            local_to_world(con_pos, con_rot, (-0.189, -0.025, 0.148)),  # top of glass safety lid
            local_to_world(con_pos, con_rot, (-0.189, -0.025, 0.139)),  # top of red button
            local_to_world(con_pos, con_rot, (0.215, -0.015, 0.138)),   # Pip-Boy plug socket
            local_to_world(con_pos, con_rot, (0.0, 0.0, 0.105)),        # center Vault-Tec label panel
        ]

        con_rays = 0
        con_hits_first = 0
        for eye_z in eye_heights_world:
            for ex in (-55.05, -54.70, -54.3644, -54.00, -53.65):
                for ey in (-1.20, -0.95, -0.70, -0.45):
                    eye = (ex, ey, eye_z)
                    for tgt in con_targets:
                        dx, dy, dz = tgt[0] - eye[0], tgt[1] - eye[1], tgt[2] - eye[2]
                        ln = math.sqrt(dx * dx + dy * dy + dz * dz)
                        d = (dx / ln, dy / ln, dz / ln)
                        t_acti = ray_hit_obb(eye, d, con_center, con_rot, vfa.CONSOLE_COLLISION_CENTER, vfa.CONSOLE_COLLISION_HALF)
                        port_hits = [
                            t for c_c, c_h in port_con_boxes
                            for t in (ray_hit_obb(eye, d, con_pos, con_rot, c_c, c_h),)
                            if t is not None
                        ]
                        t_port_min = min(port_hits) if port_hits else None
                        con_rays += 1
                        if t_acti is not None and (t_port_min is None or t_acti < t_port_min):
                            con_hits_first += 1

        self.assertGreaterEqual(con_rays, 1900)
        self.assertEqual(con_hits_first, con_rays, f"Console raycast coverage {con_hits_first}/{con_rays} (< 100%)")

    def test_cross_os_paths_and_make_newgame_and_core_bundle_wiring(self) -> None:
        # Simulate Linux os.path (posixpath) to prove cross-OS separator handling
        with mock.patch("os.path", posixpath):
            self.assertEqual(
                vfa.cross_os_basename(r"meshes\fo4sf\newgame\v111_pipboy_pickup.nif"),
                "v111_pipboy_pickup.nif",
            )
            self.assertEqual(
                vfa.cross_os_basename("Data/meshes/fo4sf/newgame/v111_geardoor_console.nif/"),
                "v111_geardoor_console.nif",
            )
            self.assertEqual(
                vfa.cross_os_basename(r"\\server\share\meshes/fo4sf\v111_pipboy_pickup.nif"),
                "v111_pipboy_pickup.nif",
            )
            self.assertEqual(
                vfa.normalize_archive_rel(r"\Meshes\FO4SF\NewGame\v111_pipboy_pickup.nif"),
                "meshes/fo4sf/newgame/v111_pipboy_pickup.nif",
            )

        # Verify C# helper has no host-OS Path.GetFileName traps and zero local drive-letter leaks
        vfa_cs = (ROOT / "dotnet" / "NewGame" / "VaultFalloutActivators.cs").read_text(encoding="utf-8")
        vfa_py = (ROOT / "scripts" / "newgame" / "vault_fo4_activators.py").read_text(encoding="utf-8")
        self.assertNotIn("Path.GetFileName", vfa_cs)
        for label, txt in (("VaultFalloutActivators.cs", vfa_cs), ("vault_fo4_activators.py", vfa_py)):
            self.assertNotRegex(txt, r"\b[A-Za-z]:[\\/]", f"local drive path leak in {label}")

        # Verify make_newgame verify_dir + fold + make_core_bundle.extract_component_outputs wire both staged NIFs
        pb_nif, con_nif = vfa.build_pair_from_source_bytes(self.pb_src, self.con_src, self.box_tmpl)
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            stage_dir = t / "03-newgame"
            (stage_dir / "Data" / "Scripts").mkdir(parents=True)
            (stage_dir / ng.PLUGIN).write_bytes(b"TES4_NEWGAME")
            (stage_dir / "Data" / "Scripts" / "FO4SF_NewGameQuest.pex").write_bytes(b"PEX_QUEST")
            (stage_dir / "README.txt").write_text("Fallout 4 new game (Claude-cloud). Install: not now.\n", encoding="utf-8")

            act_assets = {}
            for rel, payload in ((vfa.PIPBOY_STAGED_REL, pb_nif), (vfa.CONSOLE_STAGED_REL, con_nif)):
                dst = stage_dir.joinpath(*rel.split("/"))
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(payload)
                act_assets[rel] = vfa.sha256_bytes(payload)

            port_esm = t / "FO4Port.esm"
            core_esm = t / "FO4TerrainCore.esm"
            port_esm.write_bytes(b"PORT")
            core_esm.write_bytes(b"CORE")

            plugin_sha = ng.sha256(str(stage_dir / ng.PLUGIN))
            pex_sha = ng.sha256(str(stage_dir / "Data" / "Scripts" / "FO4SF_NewGameQuest.pex"))
            plan = {
                "kind": "newgame",
                "plugin": ng.PLUGIN,
                "plugin_sha256": plugin_sha,
                "scripts": {"FO4SF_NewGameQuest": pex_sha},
                "activator_assets": act_assets,
                "outputs": {
                    ng.PLUGIN: plugin_sha,
                    "Data/Scripts/FO4SF_NewGameQuest.pex": pex_sha,
                    **act_assets,
                },
                "checked_against_sha256": {
                    "FO4Port.esm": ng.sha256(str(port_esm)),
                    "formids.json": "x",
                    "FO4TerrainCore.esm": ng.sha256(str(core_esm)),
                },
            }
            plan_path = stage_dir / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            # 1. make_core_bundle.extract_component_outputs("newgame", stage_dir) extracts plugin + PEX + both NIFs
            plugins, outputs = mcb.extract_component_outputs("newgame", str(stage_dir))
            self.assertEqual(plugins, [ng.PLUGIN])
            self.assertEqual(outputs[ng.PLUGIN], plugin_sha)
            self.assertIn(vfa.PIPBOY_STAGED_REL, outputs)
            self.assertIn(vfa.CONSOLE_STAGED_REL, outputs)
            self.assertIn("Data/Scripts/FO4SF_NewGameQuest.pex", outputs)

            # 2. make_newgame fold copies both activator NIFs and verify_dir passes
            core_dir = t / "core_set"
            (core_dir / "Data" / "Terrain").mkdir(parents=True)
            (core_dir / "FO4TerrainCore.esm").write_bytes(b"CORE")
            (core_dir / "README.txt").write_text(
                "Terrain core.\n  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> "
                "--plugins FO4TerrainCore.esm --pack\n",
                encoding="utf-8",
            )
            folded = t / "folded"
            with mock.patch("sys.stdout", io.StringIO()):
                rc = ng.main(["fold", "--stage", str(stage_dir), "--core-dir", str(core_dir), "--out", str(folded), "--port", str(port_esm)])
            self.assertEqual(rc, 0)
            self.assertEqual(ng.verify_dir(str(folded), plan, str(port_esm), str(core_esm)), [])
            self.assertEqual(folded.joinpath(*vfa.PIPBOY_STAGED_REL.split("/")).read_bytes(), pb_nif)
            self.assertEqual(folded.joinpath(*vfa.CONSOLE_STAGED_REL.split("/")).read_bytes(), con_nif)

            # 3. Tampering with a folded activator NIF fails verify_dir cleanly
            folded.joinpath(*vfa.CONSOLE_STAGED_REL.split("/")).write_bytes(b"tampered")
            probs = ng.verify_dir(str(folded), plan, str(port_esm), str(core_esm))
            self.assertTrue(any("vault activator" in p for p in probs), probs)

    def test_stage_vault_activators_end_to_end_from_synthetic_ba2_archives(self) -> None:
        # Build a synthetic vanilla Starfield NIF containing a 6,168-byte layer-1 hknpBoxShape bhkPhysicsSystem
        vanilla_f = nif.NifFile(
            endian=1,
            user_version=12,
            bs_version=173,
            author=b"\x00",
            unknown_int=0,
            export_script=b"\x00",
            sf_data=b"\x7a\x00",
        )
        s_root = vanilla_f.string_index(b"PoweredLever01")
        s_bsx = vanilla_f.string_index(b"BSX")
        ident_xf = struct.pack("<3f9ff", 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0)
        vanilla_f.add_block("NiNode", struct.pack("<iIiiI", s_root, 1, 1, -1, 0xE) + ident_xf + struct.pack("<iI", 2, 0))
        vanilla_f.add_block("BSXFlags", struct.pack("<iI", s_bsx, 0x2))
        vanilla_f.add_block("bhkNPCollisionObject", struct.pack("<iHiI", 0, 0x80, 3, 0))
        vanilla_f.add_block("bhkPhysicsSystem", struct.pack("<I", len(self.box_tmpl)) + self.box_tmpl)
        vanilla_f.footer = struct.pack("<II", 1, 0)
        vanilla_nif = nif.serialize(vanilla_f)

        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            sf_data = t / "Starfield" / "Data"
            port_data = t / "PortStage"
            out_dir = t / "staged"
            sf_data.mkdir(parents=True)
            port_data.mkdir(parents=True)
            out_dir.mkdir(parents=True)

            sf_esm = sf_data / "Starfield.esm"
            port_esm = port_data / "FO4Port.esm"
            sf_esm.write_bytes(b"TES4")
            port_esm.write_bytes(b"TES4")

            (port_data / "FO4Port - Main.ba2").write_bytes(
                ba2_fixture.general_archive(
                    {
                        vfa.PORT_PIPBOY_SOURCE_NIF: self.pb_src,
                        vfa.PORT_CONSOLE_SOURCE_NIF: self.con_src,
                    },
                    compressed=True,
                )
            )
            (sf_data / "Starfield - Meshes01.ba2").write_bytes(
                ba2_fixture.general_archive(
                    {
                        vfa.VANILLA_BOX_TEMPLATE_CANDIDATES[0]: vanilla_nif,
                    },
                    compressed=True,
                )
            )

            closed_sys = type("ClosedSys", (), {"pids": staticmethod(lambda _exe: [])})()
            outputs = vfa.stage_vault_activators(str(out_dir), str(port_esm), str(sf_esm), system=closed_sys)
            self.assertEqual(set(outputs), {vfa.PIPBOY_STAGED_REL, vfa.CONSOLE_STAGED_REL})

            pb_disk = out_dir.joinpath(*vfa.PIPBOY_STAGED_REL.split("/")).read_bytes()
            con_disk = out_dir.joinpath(*vfa.CONSOLE_STAGED_REL.split("/")).read_bytes()
            self.assertEqual(outputs[vfa.PIPBOY_STAGED_REL], vfa.sha256_bytes(pb_disk))
            self.assertEqual(outputs[vfa.CONSOLE_STAGED_REL], vfa.sha256_bytes(con_disk))
            self.assertEqual(vfa.verify_activator_nif_bytes(pb_disk)["shape_count"], 2)
            self.assertEqual(vfa.verify_activator_nif_bytes(con_disk)["shape_count"], 3)


if __name__ == "__main__":
    unittest.main()
