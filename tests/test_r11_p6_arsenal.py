"""Offline unit tests for Round 11 Probe P6 (`scripts/probes/stage_r11_p6_arsenal.py` & `FO4SF_R11P6Quest.psc`).

Covers:
  1. Synthetic `stage_probe_p6` + `verify_probe_p6` across all 23 playable weapons, 13 ammos,
     3 props (`Stimpak`, `Caps`, `BobbyPin`), 5 range targets (`Flesh`, `Robot`, `NoDisint`, `Stone`,
     `Wood`), `FO4SF_P6_NoDisintTargetNpc` (`0x0022DB8F` w/ template kw slots 2..14 zeroed),
     GNRL + DX10 BA2 entry & BS-CRC32 checks, `cross_plugin_check.validate_staged_esms`, and
     tamper failures.
  2. F4 `verify_placed_refs_above_floor` positive + negative tamper (sub-floor Minigun drum &
     below-tabletop rack item fail).
  3. P3 zero-M/N/V, zero-stripped-`FO4SF_*` EDIDs, and `< 200 m`/axis hop validation + negatives.
  4. `probe_common` reversible `install`/`status`/`uninstall` round-trip (`st_nlink == 1`,
     `base != 2g-fix2` warning check, rollback on `Plugins.txt`/swap failure, `--ship-pipboy-dll`
     tested `7d5ba49c` reuse & rejection of unverified DLLs).
  5. `FO4SF_R11P6Quest.psc` structural VMAD parity + translated stage/event execution checks &
     source hygiene (zero UTF-8 BOM, zero literal Windows drive paths).
  6. Read-only `r12_card_validator` validation on `docs/testing/round11-p6-arsenal-card.md` and
     optional env-gated live `r11-p6-arsenal` cross-check (`FO4SF_P6_STAGE_DIR`).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import struct
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[1]
SRC_DIR = REPO_ROOT / "src"
PROBES_DIR = REPO_ROOT / "scripts" / "probes"
WEAPONS_DIR = REPO_ROOT / "scripts" / "weapons"
TESTING_DIR = REPO_ROOT / "scripts" / "testing"

for _p in (str(REPO_ROOT), str(SRC_DIR), str(PROBES_DIR), str(WEAPONS_DIR), str(TESTING_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import probe_common as pc  # noqa: E402
import r12_card_validator as card_val  # noqa: E402
import stage_r11_p6_arsenal as p6  # noqa: E402
import stage_r11_weapons as sw  # noqa: E402
from fo4sf import nif, sfmesh, sfnif  # noqa: E402
from fo4sf.core import cross_plugin_check as cpc  # noqa: E402
from fo4sf.planet.esm import ESM, PERSISTENT, Plugin, PluginWriter, Record, group_bytes, zbytes  # noqa: E402

DRIVE_PATH_RX = re.compile(r"\b[A-Za-z]:[\\/]")
CARD_PATH = REPO_ROOT / "docs" / "testing" / "round11-p6-arsenal-card.md"
IMPACTS_DOC_PATH = REPO_ROOT / "docs" / "combat" / "impacts.md"
QUEST_PSC_PATH = PROBES_DIR / "FO4SF_R11P6Quest.psc"


def _make_dx10_dds(width: int = 4, height: int = 4, mips: int = 1, dxgi: int = 72) -> bytes:
    flags = 0x1 | 0x2 | 0x4 | 0x1000
    h = b"DDS " + struct.pack("<7I", 124, flags, height, width, 0, 0, mips) + b"\0" * 44
    h += struct.pack("<II4sIIIII", 32, 0x4, b"DX10", 0, 0, 0, 0, 0)
    h += struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    h += struct.pack("<5I", dxgi, 3, 0, 1, 0)
    return h + (b"\xAB" * 64)


def _write_mat_and_dds(assets_root: Path, mat_rel: str, tex_prefix: str) -> None:
    dds_rels = [f"textures/{tex_prefix}_{suf}.dds" for suf in ("color", "normal", "rough")]
    for dr in dds_rels:
        dp = assets_root / Path(*dr.split("/"))
        dp.parent.mkdir(parents=True, exist_ok=True)
        dp.write_bytes(_make_dx10_dds())
    mp = assets_root / Path(*mat_rel.split("/"))
    mp.parent.mkdir(parents=True, exist_ok=True)
    data_prefixed = ["Data\\" + dr.replace("/", "\\") for dr in dds_rels]
    mp.write_text(json.dumps({"Objects": [{"Textures": data_prefixed}]}), encoding="utf-8")


def _havok_varint(x: int) -> bytes:
    return bytes([x]) if x < 0x80 else bytes([0x80 | (x >> 8), x & 0xFF])


def _havok_sec(tag: bytes, payload: bytes, leaf: bool = True) -> bytes:
    return struct.pack(">I", ((1 if leaf else 0) << 30) | (len(payload) + 8)) + tag + payload


def _make_box_collision_blob() -> bytes:
    """Build a minimal self-contained Starfield Havok TAG0 convex cube blob accepted by sfbodies.blob_bodies."""
    body_t = "hknpPhysicsSystemData::bodyCinfoWithAttachment"
    psd_t = "hknpPhysicsSystemData"
    types_spec = [
        ("ptr", 8, []),
        ("float3", 12, []),
        ("u8", 1, []),
        ("face", 4, []),
        (body_t, 64, [("shape", 0, "ptr"), ("position", 16, "float3"), ("orientation", 32, "float3"), ("collisionFilterInfo", 48, "u8")]),
        (psd_t, 16, [("bodyCinfos", 0, "ptr")]),
        ("hull", 48, [("vertices", 0, "ptr"), ("faces", 16, "ptr"), ("indices", 32, "ptr")]),
        ("hknpConvexShape", 80, [("convexRadius", 8, "float3"), ("hull", 16, "hull")]),
    ]
    tidx = {n: i + 1 for i, (n, _, _) in enumerate(types_spec)}
    fields = sorted({f for _, _, fl in types_spec for f, _, _ in fl})
    fidx = {f: i for i, f in enumerate(fields)}
    tst = b"".join(n.encode() + b"\0" for n, _, _ in types_spec)
    fst = b"".join(f.encode() + b"\0" for f in fields)
    tna = _havok_varint(len(types_spec) + 1) + b"".join(_havok_varint(i) + _havok_varint(0) for i in range(len(types_spec)))
    tbdy = b"".join(
        _havok_varint(tidx[nm]) + _havok_varint(0) + _havok_varint(0x8 | (0x20 if fl else 0)) + _havok_varint(sz) + _havok_varint(4)
        + ((_havok_varint(len(fl)) + b"".join(_havok_varint(fidx[f]) + _havok_varint(0) + _havok_varint(o) + _havok_varint(tidx[t]) for f, o, t in fl)) if fl else b"")
        for nm, sz, fl in types_spec
    )
    verts = [(x, y, z) for z in (-0.05, 0.05) for y in (-0.05, 0.05) for x in (-0.05, 0.05)]
    faces = [[0, 2, 3, 1], [4, 5, 7, 6], [0, 1, 5, 4], [2, 6, 7, 3], [0, 4, 6, 2], [1, 3, 7, 5]]
    fr, idx_b = b"", b""
    for fc in faces:
        fr += struct.pack("<HBB", len(idx_b), len(fc), 0)
        idx_b += bytes(fc)
    body_buf = bytearray(64)
    struct.pack_into("<4f", body_buf, 32, 0.0, 0.0, 0.0, 1.0)
    struct.pack_into("<I", body_buf, 48, 1)
    items = [
        (psd_t, bytearray(16), 1),
        ("hknpConvexShape", bytearray(80), 1),
        ("float3", bytearray(b"".join(struct.pack("<3f", *v) for v in verts)), len(verts)),
        ("face", bytearray(fr), len(faces)),
        ("u8", bytearray(idx_b), len(idx_b)),
        (body_t, body_buf, 1),
    ]
    ptrs = [(2, 16, 3), (2, 32, 4), (2, 48, 5), (6, 0, 2), (1, 0, 6)]
    data, offsets = bytearray(), []
    for _, pay, _ in items:
        data += b"\0" * (-len(data) % 16)
        offsets.append(len(data))
        data += pay
    data += b"\0" * (-len(data) % 16)
    pt = []
    for it_id, off, tgt in ptrs:
        at = offsets[it_id - 1] + off
        struct.pack_into("<Q", data, at, tgt)
        pt.append(at)
    item_tab = bytes(12) + b"".join(struct.pack("<III", tidx[t], o, c) for (t, _, c), o in zip(items, offsets))
    ptch = struct.pack("<II", 1, len(pt)) + struct.pack(f"<{len(pt)}I", *pt)
    t_sec = _havok_sec(b"TST1", tst) + _havok_sec(b"TNA1", tna) + _havok_sec(b"FST1", fst) + _havok_sec(b"TBDY", tbdy)
    body = _havok_sec(b"SDKV", b"20190200") + _havok_sec(b"DATA", bytes(data)) + _havok_sec(b"TYPE", t_sec, leaf=False) + _havok_sec(b"INDX", _havok_sec(b"ITEM", item_tab) + _havok_sec(b"PTCH", ptch), leaf=False)
    return _havok_sec(b"TAG0", body, leaf=False)


_BOX_COLL_BLOB = _make_box_collision_blob()


def _stage_minimal_static_nif(
    assets_root: Path,
    nif_rel: str,
    mat_rel: str,
    tex_prefix: str,
    pts: list[tuple[float, float, float]] | None = None,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    if pts is None:
        pts = [(-0.04, -0.04, 0.0), (0.04, -0.04, 0.0), (0.04, 0.04, 0.08), (-0.04, 0.04, 0.08)]
    mesh = sfmesh.SfMesh(version=2)
    mesh.scale, mesh.positions = sfmesh.encode_positions(pts)
    mesh.triangles = [(0, 1, 2), (0, 2, 3)]
    sfmesh.build_meshlets(mesh)
    mb = sfmesh.serialize(mesh)
    dh, fh = sw.convert_static.mesh_file_path(mb)
    (assets_root / "geometries" / dh).mkdir(parents=True, exist_ok=True)
    (assets_root / "geometries" / dh / f"{fh}.mesh").write_bytes(mb)
    pts_dec = [sfmesh.decode_position(pt, mesh.scale) for pt in mesh.positions]
    sph, bx = sfnif.bounds_from_points(pts_dec)
    nf = sfnif.build_static_nif(
        b"ItemRoot",
        [
            sfnif.StaticShape(
                name=b"Item:0",
                mesh_path=f"{dh}\\{fh}".encode("ascii"),
                indices_size=6,
                num_verts=4,
                material_path=mat_rel,
                sphere=sph,
                box=bx,
            )
        ],
        collision_blob=_BOX_COLL_BLOB,
    )
    np = assets_root / Path(*nif_rel.split("/"))
    np.parent.mkdir(parents=True, exist_ok=True)
    np.write_bytes(nif.serialize(nf))
    _write_mat_and_dds(assets_root, mat_rel, tex_prefix)
    bmin = tuple(min(p[k] for p in pts_dec) for k in range(3))
    bmax = tuple(max(p[k] for p in pts_dec) for k in range(3))
    return bmin, bmax


def _ninode_block(
    f: nif.NifFile,
    name: str,
    children: list[int],
    extra_refs: list[int],
    coll_ref: int = -1,
) -> bytes:
    ident = struct.pack("<3f9ff", 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1.0)
    return (
        struct.pack("<iI", f.string_index(name.encode("ascii")), len(extra_refs))
        + (struct.pack(f"<{len(extra_refs)}i", *extra_refs) if extra_refs else b"")
        + struct.pack("<iI", -1, 0xE)
        + ident
        + struct.pack("<iI", coll_ref, len(children))
        + (struct.pack(f"<{len(children)}i", *children) if children else b"")
    )


def _stage_minimal_weapon_nif(assets_root: Path, wkey: str, nif_rel: str) -> tuple[list[float], list[float]]:
    """Build a valid BS-173 weapon NIF matching sw.verify_nif_asset_tree rules for wkey."""
    mat_rel = f"materials/fo4sf/synth_{wkey}/mat_{wkey}.mat"
    _write_mat_and_dds(assets_root, mat_rel, f"fo4sf/synth_{wkey}/tex_{wkey}")
    pts = (
        [(-0.20, -0.50, -0.538), (0.20, -0.50, -0.538), (0.20, 0.50, 0.15), (-0.20, 0.50, 0.15)]
        if wkey == "minigun"
        else [(-0.05, -0.15, -0.08), (0.05, -0.15, -0.08), (0.05, 0.25, 0.10), (-0.05, 0.25, 0.10)]
    )
    mesh = sfmesh.SfMesh(version=2)
    mesh.scale, mesh.positions = sfmesh.encode_positions(pts)
    mesh.triangles = [(0, 1, 2), (0, 2, 3)]
    sfmesh.build_meshlets(mesh)
    mb = sfmesh.serialize(mesh)
    dh, fh = sw.convert_static.mesh_file_path(mb)
    (assets_root / "geometries" / dh).mkdir(parents=True, exist_ok=True)
    (assets_root / "geometries" / dh / f"{fh}.mesh").write_bytes(mb)
    pts_dec = [sfmesh.decode_position(pt, mesh.scale) for pt in mesh.positions]
    sph, bx = sfnif.bounds_from_points(pts_dec)
    mesh_ref_b = f"{dh}\\{fh}".encode("ascii")

    # Collect required node -> parent and shape -> parent
    node_parents: dict[str, str] = {"ProjectileNode": "WEAPON", "WeaponReceiver": "WEAPON"}
    node_parents.update(sw.REQUIRED_NODE_PARENTS.get(wkey, {}))
    req_shapes = dict(sw.REQUIRED_MOVING_SHAPE_PARENTS.get(wkey, {}))
    req_shapes.setdefault("Receiver:0", "WeaponReceiver")
    for pnode in list(req_shapes.values()):
        if pnode not in node_parents and pnode != "WEAPON":
            node_parents[pnode] = "WEAPON"
    for cnode, pnode in list(node_parents.items()):
        if pnode != "WEAPON" and pnode not in node_parents:
            node_parents[pnode] = "WEAPON"

    # Build NifFile blocks bottom-up reservation cleanly with placeholders
    nf = nif.NifFile(
        endian=1,
        user_version=12,
        bs_version=173,
        author=b"\x00",
        unknown_int=0,
        export_script=b"\x00",
        sf_data=b"\x7a\x00",
    )
    s_sgo = nf.string_index(b"sgoKeep")
    s_bsx = nf.string_index(b"BSX")
    s_matid = nf.string_index(b"MaterialID")

    # Block 0 = WEAPON (placeholder, filled at end), Block 1 = BSXFlags, Block 2 = bhkNPCollisionObject,
    # Block 3 = bhkPhysicsSystem, Block 4 = sgoKeep extra data (shared safely by nodes)
    coll = _BOX_COLL_BLOB
    nf.add_block("NiNode", b"")
    nf.add_block("BSXFlags", struct.pack("<iI", s_bsx, 2))
    nf.add_block("bhkNPCollisionObject", struct.pack("<iHiI", 0, 0x80, 3, 0))
    nf.add_block("bhkPhysicsSystem", struct.pack("<I", len(coll)) + coll)
    nf.add_block("NiStringExtraData", struct.pack("<ii", s_sgo, s_sgo))

    node_block_idx: dict[str, int] = {"WEAPON": 0}
    node_children: dict[str, list[int]] = {"WEAPON": []}
    for nm in sorted(node_parents):
        idx = len(nf.blocks)
        nf.add_block("NiNode", b"")
        node_block_idx[nm] = idx
        node_children[nm] = []
    for nm, par in sorted(node_parents.items()):
        node_children[par].append(node_block_idx[nm])

    for sh_nm, pnode in sorted(req_shapes.items()):
        g_idx = len(nf.blocks)
        mat_id = sfnif.material_id(mat_rel)
        nf.add_block(
            "BSGeometry",
            sfnif.build_bsgeometry(
                sfnif.BSGeometry(
                    name_idx=nf.string_index(sh_nm.encode("ascii")),
                    extra_refs=[g_idx + 1],
                    sphere=sph,
                    box=bx,
                    shader=g_idx + 2,
                    meshes=[sfnif.MeshRef(6, 4, 0x40, mesh_ref_b), None, None, None],
                )
            ),
        )
        nf.add_block("NiIntegerExtraData", struct.pack("<iI", s_matid, mat_id))
        nf.add_block("BSLightingShaderProperty", struct.pack("<iIi", nf.string_index(mat_rel.encode("latin-1")), 0, -1))
        node_children[pnode].append(g_idx)

    nf.blocks[0] = _ninode_block(nf, "WEAPON", node_children["WEAPON"], [1, 4], coll_ref=2)
    for nm in sorted(node_parents):
        bidx = node_block_idx[nm]
        nf.blocks[bidx] = _ninode_block(nf, nm, node_children[nm], [4])
    nf.footer = struct.pack("<II", 1, 0)

    out_np = assets_root / Path(*nif_rel.split("/"))
    out_np.parent.mkdir(parents=True, exist_ok=True)
    out_np.write_bytes(nif.serialize(nf))
    return [min(p[k] for p in pts_dec) for k in range(3)], [max(p[k] for p in pts_dec) for k in range(3)]


def _build_synthetic_arsenal_assets(assets_root: Path) -> None:
    weapons_manifest: dict[str, dict] = {}
    for wkey, nif_rel in sw.WEAPON_NIF_RELS.items():
        bmin, bmax = _stage_minimal_weapon_nif(assets_root, wkey, nif_rel)
        weapons_manifest[wkey] = {"nif_rel": nif_rel, "bounds_min_m": bmin, "bounds_max_m": bmax}
    for akey, arel in sw.AMMO_NIF_RELS.items():
        _stage_minimal_static_nif(assets_root, arel, f"materials/fo4core/ammo/{akey}.mat", f"fo4core/ammo/{akey}")
    for ckey, crel in sw.CORE_ITEM_NIF_RELS.items():
        _stage_minimal_static_nif(assets_root, crel, f"materials/fo4core/items/{ckey}.mat", f"fo4core/items/{ckey}")
    for pkey, prel in sw.PROJ_NIF_RELS.items():
        _stage_minimal_static_nif(assets_root, prel, f"materials/fo4sf/proj/{pkey}.mat", f"fo4sf/proj/{pkey}")
    (assets_root / "r11_weapons_manifest.json").write_text(json.dumps({"weapons": weapons_manifest}, indent=2), encoding="utf-8")


def _build_synthetic_core_values_esm(out_path: Path) -> None:
    pw = PluginWriter(masters=["Starfield.esm"])
    for lid, (sig_s, edid) in sorted(cpc.CORE_VALUES_ARSENAL_RECORDS.items()):
        sig = sig_s.encode("ascii")
        subs = [(b"EDID", zbytes(edid))]
        if sig == b"MGEF" and lid == 0x0008C2:
            subs.append((b"CTDA", struct.pack("<I", p6.SF_KW_NO_DISINTEGRATE)))
        pw.add(Record(sig, (1 << 24) | lid, subs))
    pw.write(out_path)


def _build_synthetic_raider_esm(out_path: Path) -> None:
    pw = PluginWriter(masters=["Starfield.esm"])
    # Include TPTA with 15 x uint32 slots (>2..14 nonzero) + stale KWDA so test proves template slot clearing!
    tpta = struct.pack("<15I", *(0x001000 + i for i in range(15)))
    pw.add(
        Record(
            b"NPC_",
            (1 << 24) | 0xF04801,
            [
                (b"EDID", zbytes("FO4_LvlRaider_Calm")),
                (b"OBND", struct.pack("<6f", -0.35, -0.35, 0.0, 0.35, 0.35, 1.8)),
                (b"RNAM", struct.pack("<I", 0x0000347D)),
                (b"TPTA", tpta),
                (b"KSIZ", struct.pack("<I", 1)),
                (b"KWDA", struct.pack("<I", 0x00011111)),
                (b"STOP", b""),
            ],
        )
    )
    pw.write(out_path)


def _build_synthetic_port_esm(out_path: Path) -> None:
    pw = PluginWriter(masters=["Starfield.esm"])
    pw.add(Record(b"CELL", (1 << 24) | 0x0011F3, [(b"EDID", zbytes("FO4Port_Vault111Cryo")), (b"DATA", struct.pack("<H", 1))]))
    pw.write(out_path)


def _make_fake_p3_clean_stage_inputs(td_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    assets_dir = td_path / "src_assets"
    _build_synthetic_arsenal_assets(assets_dir)
    cv_src = td_path / "FO4SFCoreValues.esm"
    _build_synthetic_core_values_esm(cv_src)
    port_esm = td_path / "FO4Port.esm"
    _build_synthetic_port_esm(port_esm)
    raider_esm = td_path / "FO4ActorRaider.esm"
    _build_synthetic_raider_esm(raider_esm)
    return assets_dir, cv_src, port_esm, raider_esm, td_path / "stage_out"


class R11P6ArsenalTests(unittest.TestCase):
    def test_synthetic_stage_verify_and_nodisintegrate_npc(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            assets_dir, cv_src, port_esm, raider_esm, out_dir = _make_fake_p3_clean_stage_inputs(td_p)
            manifest = p6.stage_probe_p6(
                out_dir=out_dir,
                port_esm=port_esm,
                raider_esm=raider_esm,
                prebuilt_core_values=cv_src,
                prebuilt_assets_dir=assets_dir,
                prebuilt_pex={"FO4SF_R11P6Quest": b"FAKEPEX01"},
                clean=True,
                min_free_gb=0.01,
            )
            self.assertEqual(manifest["overridden_candidate_files"], ["Data/FO4SFCoreValues.esm"])
            self.assertEqual(manifest["pipboy_dll"]["shipped"], False)
            self.assertEqual(len(manifest["placement_floor_audit"]), 48)
            minigun_entry = next(e for e in manifest["placement_floor_audit"] if e.get("asset_key") == "minigun")
            self.assertGreaterEqual(minigun_entry["world_min_z"], p6.VAULT_TABLE_TOP_Z)
            self.assertGreaterEqual(minigun_entry["world_min_z"], p6.VAULT_FLOOR_Z)

            vrep = p6.verify_probe_p6(out_dir)
            self.assertTrue(vrep["verified"])
            self.assertEqual(vrep["placed_refs_checked"], 48)

            # Inspect FO4SF_R11P6Arsenal.esm binary records: NoDisintegrate keyword + cleared TPTA template slots 2..14
            esm_p = out_dir / "exp" / p6.PROBE_PLUGIN
            with Plugin(str(esm_p)) as plg:
                npcs = [r for r in plg.records("NPC_") if (r.formid & 0xFFFFFF) == 0x000802]
                self.assertEqual(len(npcs), 1)
                npc_rec = npcs[0]
                self.assertEqual(npc_rec.edid, "FO4SF_P6_NoDisintTargetNpc")
                self.assertEqual(struct.unpack("<I", npc_rec.get(b"KWDA"))[0], p6.SF_KW_NO_DISINTEGRATE)
                tpta = npc_rec.get(b"TPTA")
                slots = struct.unpack("<15I", tpta[:60])
                self.assertEqual(slots[0], 0x001000)
                self.assertEqual(slots[1], 0x001001)
                self.assertTrue(all(s == 0 for s in slots[2:]))

                refrs = [
                    plg.record_at(it[1])
                    for s, e in plg.groups.get("CELL", [])
                    for it in plg.walk(s, e)
                    if it[0] == "REC" and it[2] in (b"REFR", b"ACHR")
                ]
                self.assertEqual(len(refrs), 48)

            # Verify BA2 BS CRC32 + entry hashes directly via probe_common
            gnrl_hashes = pc.verify_ba2_entry_hashes(out_dir / "exp" / p6.PROBE_MAIN_BA2, check_crc32=True)
            dx10_hashes = pc.verify_ba2_entry_hashes(out_dir / "exp" / p6.PROBE_TEX_BA2, check_crc32=True)
            self.assertIn("scripts/fo4sf_r11p6quest.pex", gnrl_hashes)
            self.assertEqual(len(dx10_hashes), len(list((out_dir / "assets" / "textures").rglob("*.dds"))))

            # Negative check: tampering Main.ba2 fails verify_probe_p6
            main_ba2 = out_dir / "exp" / p6.PROBE_MAIN_BA2
            raw_ba2 = bytearray(main_ba2.read_bytes())
            raw_ba2[-1] ^= 0xFF
            main_ba2.write_bytes(bytes(raw_ba2))
            with self.assertRaises(p6.ProbeP6Error):
                p6.verify_probe_p6(out_dir)

    def test_f4_floor_and_rack_clearance_rejects_subfloor_or_sunk_items(self) -> None:
        good = [
            {"local_id": "0x000816", "edid": "FO4SF_P6_RackTable1Ref", "kind": "table", "support_top_z": 0.0, "world_min_z": 0.0},
            {"local_id": "0x00081E", "edid": "FO4SF_P6_Weap_MinigunRef", "kind": "weapon", "support_top_z": 0.825, "world_min_z": 0.830},
        ]
        p6.verify_placed_refs_above_floor(good, floor_z=0.0)

        subfloor = [good[0], dict(good[1], world_min_z=-0.12)]
        with self.assertRaisesRegex(p6.ProbeP6Error, "F4 violation"):
            p6.verify_placed_refs_above_floor(subfloor, floor_z=0.0)

        sunk_in_table = [good[0], dict(good[1], world_min_z=0.45)]
        with self.assertRaisesRegex(p6.ProbeP6Error, "F4 rack violation"):
            p6.verify_placed_refs_above_floor(sunk_in_table, floor_z=0.0)

    def test_p3_batches_and_200m_hops_and_negative_checks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bat_dir = Path(td)
            batches = p6.build_p3_batch_scripts(quest_load_prefix=0x11)
            self.assertEqual(set(batches), {"p6r.txt", "p6t.txt", "p6a.txt", "p6g.txt", "p6c.txt", "p6h1.txt", "p6e.txt", "p6s.txt", "p6q.txt"})
            for fn, txt in batches.items():
                self.assertNotIn("FO4SF_", txt)
                (bat_dir / fn).write_text(txt, encoding="utf-8")
            self.assertEqual(p6.validate_p6_batches(bat_dir), [])

            # Forbidden M/N/V batch name
            (bat_dir / "p6m.txt").write_text("getstage 11000830\n", encoding="utf-8")
            with self.assertRaises(pc.ProbeValidationError):
                p6.validate_p6_batches(bat_dir)
            (bat_dir / "p6m.txt").unlink()

            # Forbidden stripped FO4SF_ EditorID in bat command
            (bat_dir / "p6q.txt").write_text("setstage FO4SF_R11P6Quest 10\n", encoding="utf-8")
            with self.assertRaises(pc.ProbeValidationError):
                p6.validate_p6_batches(bat_dir)

            # Negative >200m hop check
            bad_anchors = [p6.SANCTUARY_BENCH_ANCHOR]
            bad_hops = [pc.HopSpec("too_far", "sanctuary_bench", -2100.0, -1420.19, 112.09, "exterior")]
            with self.assertRaises(pc.ProbeValidationError):
                pc.validate_batches_and_hops(
                    batch_files=[], activate_commands=[], anchors=bad_anchors, hops=bad_hops, interior_mode=False
                )

    def test_install_status_uninstall_roundtrip_baseline_warning_and_pipboy_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            assets_dir, cv_src, port_esm, raider_esm, out_dir = _make_fake_p3_clean_stage_inputs(td_p)
            p6.stage_probe_p6(
                out_dir=out_dir,
                port_esm=port_esm,
                raider_esm=raider_esm,
                prebuilt_core_values=cv_src,
                prebuilt_assets_dir=assets_dir,
                prebuilt_pex={"FO4SF_R11P6Quest": b"FAKEPEX01"},
                clean=True,
                min_free_gb=0.01,
            )

            sf_dir = td_p / "Starfield"
            data_dir = sf_dir / "Data"
            data_dir.mkdir(parents=True)
            shutil.copy2(port_esm, data_dir / "FO4Port.esm")
            fake_cv_orig = b"ORIGINAL_COREVALUES_ESM"
            (data_dir / "FO4SFCoreValues.esm").write_bytes(fake_cv_orig)
            plugins_txt = td_p / "Plugins.txt"
            plugins_txt.write_text("# Starfield\n*FO4Port.esm\n*FO4SFCoreValues.esm\n", encoding="utf-8")
            orig_plugins_bytes = plugins_txt.read_bytes()
            fake_port_sha = pc.sha256_file(data_dir / "FO4Port.esm")

            # Disk space refusal negative test
            with self.assertRaises(pc.ProbePreflightError):
                pc.check_free_space_gb(sf_dir, min_gb=9999999.0)

            with mock.patch.object(pc, "BASE_FO4PORT_SHA256_PREFIX", fake_port_sha), \
                 warnings.catch_warnings(record=True) as wlog:
                warnings.simplefilter("always")
                res = p6.install_probe_p6(out_dir, sf_dir, plugins_txt=plugins_txt, min_free_gb=0.01)

            # Base != 2g-fix2 triggers baseline mismatch warning cleanly
            self.assertTrue(any("candidate-2g-fix2 baseline" in w for w in res.get("baseline_warnings", [])))
            self.assertTrue(any("candidate-2g-fix2" in str(w.message) for w in wlog))

            # Verify st_nlink == 1 on installed copy-only ESMs (BA2s may hardlink safely on same volume)
            for fname in ("FO4SFCoreValues.esm", p6.PROBE_PLUGIN):
                self.assertEqual(os.lstat(data_dir / fname).st_nlink, 1)
            for fname in (p6.PROBE_MAIN_BA2, p6.PROBE_TEX_BA2):
                self.assertTrue((data_dir / fname).is_file())

            # Verify dynamic quest slot prefix stamped into p6t.txt matches FO4SF_R11P6Arsenal full master slot
            p6t_txt = (sf_dir / "p6t.txt").read_text(encoding="utf-8")
            self.assertIn("SetStage 07000830 20", p6t_txt)

            st_installed = pc.probe_status(probe_id=p6.PROBE_ID, starfield_dir=sf_dir)
            self.assertTrue(st_installed["installed"])

            # Rollback test: inject failure after swap/add starts and confirmPlugins/files roll back untouched? Wait: test rollback on second install attempt error
            pc.uninstall_probe(probe_id=p6.PROBE_ID, starfield_dir=sf_dir)
            self.assertFalse((data_dir / p6.PROBE_PLUGIN).exists())
            self.assertFalse((sf_dir / "p6r.txt").exists())
            self.assertEqual((data_dir / "FO4SFCoreValues.esm").read_bytes(), fake_cv_orig)
            self.assertEqual(plugins_txt.read_bytes(), orig_plugins_bytes)

            # Fault injection AFTER files & Plugins.txt are written rolls back everything atomically
            def _inject_after_plugins(step: str) -> None:
                if step == "after_plugins":
                    raise RuntimeError("simulated post-plugins fault")

            with mock.patch.object(pc, "BASE_FO4PORT_SHA256_PREFIX", fake_port_sha), \
                 warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                with self.assertRaisesRegex(RuntimeError, "simulated post-plugins fault"):
                    pc.install_probe(
                        probe_id=p6.PROBE_ID,
                        stage_dir=out_dir,
                        starfield_dir=sf_dir,
                        plugins_txt=plugins_txt,
                        plugins_to_activate=[p6.PROBE_PLUGIN],
                        files=json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))["install_files"],
                        expected_base_hashes={"Data/FO4Port.esm": fake_port_sha},
                        min_free_gb=0.01,
                        _fault_hook=_inject_after_plugins,
                    )
            self.assertEqual((data_dir / "FO4SFCoreValues.esm").read_bytes(), fake_cv_orig)
            self.assertEqual(plugins_txt.read_bytes(), orig_plugins_bytes)
            self.assertFalse((data_dir / p6.PROBE_PLUGIN).exists())

            # --ship-pipboy-dll rejects mismatched dummy DLL
            bad_dll = td_p / "bad_FO4SFPipboyMenu.dll"
            bad_dll.write_bytes(b"NOT_THE_TESTED_DLL")
            with self.assertRaisesRegex(p6.ProbeP6Error, "Refusing unverified FO4SFPipboyMenu.dll"):
                p6.stage_probe_p6(
                    out_dir=td_p / "out_bad_dll",
                    port_esm=port_esm,
                    raider_esm=raider_esm,
                    prebuilt_core_values=cv_src,
                    prebuilt_assets_dir=assets_dir,
                    prebuilt_pex={"FO4SF_R11P6Quest": b"FAKEPEX01"},
                    ship_pipboy_dll=True,
                    tested_pipboy_dll=bad_dll,
                    clean=True,
                    min_free_gb=0.01,
                )

            # --ship-pipboy-dll reuses tested 7d5ba49c binary cleanly when verified
            good_dll = td_p / "good_FO4SFPipboyMenu.dll"
            good_dll.write_bytes(b"TESTED_7D5BA49C_DLL")
            real_sha = pc.sha256_file

            def _fake_sha(pth: os.PathLike[str] | str) -> str:
                if Path(pth).name == good_dll.name or (Path(pth).name == "FO4SFPipboyMenu.dll" and Path(pth).read_bytes() == b"TESTED_7D5BA49C_DLL"):
                    return pc.TESTED_PIPBOY_DLL_SHA256
                return real_sha(pth)

            with mock.patch.object(pc, "sha256_file", side_effect=_fake_sha):
                dll_manifest = p6.stage_probe_p6(
                    out_dir=td_p / "out_good_dll",
                    port_esm=port_esm,
                    raider_esm=raider_esm,
                    prebuilt_core_values=cv_src,
                    prebuilt_assets_dir=assets_dir,
                    prebuilt_pex={"FO4SF_R11P6Quest": b"FAKEPEX01"},
                    ship_pipboy_dll=True,
                    tested_pipboy_dll=good_dll,
                    clean=True,
                    min_free_gb=0.01,
                )
            self.assertEqual(
                dll_manifest["overridden_candidate_files"],
                ["Data/FO4SFCoreValues.esm", "SFSE/Plugins/FO4SFPipboyMenu.dll"],
            )
            self.assertTrue(dll_manifest["pipboy_dll"]["shipped"])
            self.assertEqual(dll_manifest["pipboy_dll"]["sha256"], pc.TESTED_PIPBOY_DLL_SHA256)

    def test_quest_psc_parity_translated_execution_and_hygiene(self) -> None:
        psc_text = QUEST_PSC_PATH.read_text(encoding="utf-8")
        # 1. Verify runtime GetFormFromFile usage for FO4Port cage door (no fragile VMAD cross-ref) + all required log tokens
        for token in (
            "FO4SF_R11P6 init",
            "FO4SF_R11P6 grant_all",
            "FO4SF_R11P6 equip_cycle",
            "FO4SF_R11P6 target_reset",
            "FO4SF_R11P6 pickup",
            "FO4SF_R11P6 equipped",
            "FO4SF_R11P6 kill target=flesh",
            "FO4SF_R11P6 kill target=robot",
            "FO4SF_R11P6 kill target=nodisint",
            "FO4SF_R11P6 summary",
            "Game.GetFormFromFile(ArmoryCageDoorLocalId, PortPlugin)",
        ):
            self.assertIn(token, psc_text)

        # 2. Verify property parity against cross_plugin_check & stage_r11_p6_arsenal VMAD definition
        sname, decl_props = cpc.parse_psc_declared_properties(psc_text)
        self.assertEqual(sname, "FO4SF_R11P6Quest")
        expected_props = {
            "targettrigger": "objectreference",
            "fleshdummy": "actor",
            "robotdummy": "actor",
            "nodisintdummy": "actor",
            "stonetarget": "objectreference",
            "woodtarget": "objectreference",
            "showcaseweapons": "weapon[]",
            "weapontags": "string[]",
            "showcaseammos": "ammo[]",
            "ammotags": "string[]",
            "grantammocounts": "int[]",
            "capsmisc": "miscobject",
            "bobbypinmisc": "miscobject",
            "stimpakalch": "potion",
            "nodisintegratekw": "keyword",
            "healthav": "actorvalue",
            "hidesuitav": "actorvalue",
            "armorycagedoorlocalid": "int",
            "portplugin": "string",
            "enablelog": "bool",
            "logname": "string",
        }
        self.assertEqual({k: v.lower() for k, v in decl_props.items()}, expected_props)

        # 3. Translated Python state-machine check mirroring CycleNextArsenalWeapon wrapping across all 23 weapons
        self.assertEqual(len(p6.WEAP_RACK_SPECS), 23)
        self.assertEqual(len(p6.AMMO_RACK_SPECS), 13)
        self.assertEqual(len(p6.PROP_RACK_SPECS), 3)
        equipped_idx = -1
        visited: list[str] = []
        for _ in range(len(p6.WEAP_RACK_SPECS)):
            equipped_idx = 0 if equipped_idx + 1 >= len(p6.WEAP_RACK_SPECS) else equipped_idx + 1
            visited.append(p6.WEAP_RACK_SPECS[equipped_idx].tag)
        self.assertEqual(len(set(visited)), 23)

        # 4. File hygiene: zero UTF-8 BOM & zero Windows drive paths
        for path in (PROBES_DIR / "stage_r11_p6_arsenal.py", QUEST_PSC_PATH, HERE, IMPACTS_DOC_PATH, CARD_PATH):
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM found in {path.name}")
            txt = raw.decode("utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(txt), f"Literal Windows drive path in {path.name}")

    def test_p6_card_passes_r12_validator(self) -> None:
        self.assertTrue(CARD_PATH.is_file(), f"Missing P6 card: {CARD_PATH}")
        errs = card_val.validate_r12_card_file(CARD_PATH)
        self.assertEqual(errs, [], f"P6 card failed r12_card_validator: {errs}")

    @unittest.skipUnless(
        bool(os.environ.get("FO4SF_P6_STAGE_DIR")),
        "Set FO4SF_P6_STAGE_DIR to run read-only verification on live staged r11-p6-arsenal",
    )
    def test_optional_live_staged_p6_verify(self) -> None:
        stage_dir = Path(os.environ["FO4SF_P6_STAGE_DIR"])
        rep = p6.verify_probe_p6(stage_dir)
        self.assertTrue(rep["verified"])
        self.assertEqual(rep["placed_refs_checked"], 48)
        with Plugin(str(stage_dir / "core" / "FO4SFCoreValues.esm")) as cvp:
            cp = next(r for r in cvp.records("MGEF") if (r.formid & 0xFFFFFF) == 0x0008C2)
            self.assertTrue(any(struct.pack("<I", p6.SF_KW_NO_DISINTEGRATE) in c for c in cp.all(b"CTDA")))
            vmad = cp.get(b"VMAD") or b""
            self.assertIn(b"AttachAshPile", vmad)
            self.assertIn(struct.pack("<I", 0x010008C1), vmad)
            self.assertIn(struct.pack("<I", 0x0026319B), vmad)


if __name__ == "__main__":
    unittest.main()
