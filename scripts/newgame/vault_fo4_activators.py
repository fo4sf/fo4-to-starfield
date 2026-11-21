"""Build and verify the kept Fallout-look Vault 111 activator NIFs for A1(c).

Replaces Round 8 V3's temporary Starfield Deimos WallTech08.nif (0x143492) template on
FO4SF_PipboyCorpsePickup (0A00080E -> 0A00080F) and FO4SF_GearDoorConsole (0A000818 -> 0A000819)
with two stage-built Starfield BS-173 NIFs containing:
  1. ZERO Starfield geometry or materials (100% existing FO4Port Fallout 4 .mesh and .mat references);
  2. One watertight layer-1 (COL_STATIC) convex Havok body (hknpBoxShape -> hknpConvexShape, BSXFlags=0x2)
     attached directly to root NiNode [0], matching vanilla interactive ACTIs (PoweredLever01 0x1FC88B,
     CFCredTank 0x183A25, UC_GG_Connect_CourierScanner 0x143492).

Nothing of any game archive is committed to Git; NIFs are generated at stage time from the local install.
"""
from __future__ import annotations

import glob
import hashlib
import math
import os
import struct
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "src"))

from fo4sf import ba2, nif as nifmod, sfbodies, sfcollision, sfnif  # noqa: E402
from fo4sf.launcher.crashwatch import GAME_EXE, System  # noqa: E402

PIPBOY_MODL = r"fo4sf\newgame\v111_pipboy_pickup.nif"
CONSOLE_MODL = r"fo4sf\newgame\v111_geardoor_console.nif"

PIPBOY_STAGED_REL = "Data/meshes/fo4sf/newgame/v111_pipboy_pickup.nif"
CONSOLE_STAGED_REL = "Data/meshes/fo4sf/newgame/v111_geardoor_console.nif"

PORT_PIPBOY_SOURCE_NIF = r"meshes\fo4port\animobjects\npcpipboygroundtake01\npcpipboygroundtake01.nif"
PORT_CONSOLE_SOURCE_NIF = r"meshes\fo4port\interiors\vault\vault111\setdressing\v111geardoorconsole01.nif"

# Vanilla Starfield NIFs carrying a 6,168-byte identity-rotation layer-1 (COL_STATIC) hknpBoxShape body on root NiNode:
# PoweredLever01.nif (ACTI 0x001FC88B FC03_RepairPanel03, FULL + ATTX) first, then CFCredTank (0x00183A25) and Akila floor.
VANILLA_BOX_TEMPLATE_CANDIDATES = (
    r"meshes\setdressing\outpost\switches\poweredlever01.nif",
    r"meshes\setdressing\credtank\credtank_01.nif",
    r"meshes\architecture\city\akila\aggriculture\ak_agggreenhouse_pod_floor_01.nif",
)

# Placement offsets matching dotnet/NewGame/Program.cs (PipboyWorldCenter & ConsoleWorldPos):
# 0A00080F sits at pbPos + RotateZ(rz)*(0.10, 0.836, 0.145); shifting BSGeometry by (-0.10, -0.836, -0.1445) aligns the
# Fallout 4 Pip-Boy 3000 0.5 mm proud of 02001616's Pip-Boy on the floor (zero Z-fighting, zero visible shift).
PIPBOY_LOCAL_OFFSET = (0.10, 0.836, 0.145)
PIPBOY_GEOM_SHIFT = (-0.10, -0.836, -0.1445)
PIPBOY_COLLISION_CENTER = (0.000, -0.020, -0.055)
PIPBOY_COLLISION_HALF = (0.210, 0.130, 0.100)  # 42 x 26 x 20 cm -> strictly encloses 02001616 Collision0 + Pip-Boy (Z_world [0.6209, 0.8209] m)

# 0A000819 sits at conPos + R_console*(0, 0, 0.085); shifting BSGeometry by (0, 0, -0.0846) aligns the Fallout 4
# Vault 111 console 0.4 mm proud of 02001319's console deck while wrapping the 1.08 x 0.44 m deck in 1 layer-1 hull.
CONSOLE_NORMAL_OFFSET = 0.085
CONSOLE_GEOM_SHIFT = (0.0, 0.0, -0.0846)
CONSOLE_COLLISION_CENTER = (0.0, 0.0, 0.015)
CONSOLE_COLLISION_HALF = (0.550, 0.235, 0.080)  # 110 x 47 x 16 cm -> console-local z [+0.020, +0.180] m (+2.61 cm > lid)

FORBIDDEN_PATH_TOKENS = ("walltech", "deimos", "nativeconsole", "editormarker", "ships/interior", "ships\\interior")


class ActivatorNifError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractedShape:
    name: bytes
    mesh_path: bytes
    indices_size: int
    num_verts: int
    mesh_flags: int
    material_path: str
    translation: Tuple[float, float, float]
    rotation: Tuple[float, ...]
    scale: float
    sphere: Tuple[float, float, float, float]
    box: Tuple[float, ...]


def normalize_archive_rel(path_str: str) -> str:
    """Cross-OS normalization for Bethesda archive / MODL relative paths (forward slashes, lowercase, no leading slash)."""
    return path_str.strip().replace("\\", "/").lstrip("/").lower()


def cross_os_basename(path_str: str) -> str:
    """Split on both '/' and '\\' regardless of host OS (Linux CI safe)."""
    norm = path_str.rstrip("/\\")
    if not norm:
        return ""
    idx = max(norm.rfind("/"), norm.rfind("\\"))
    return norm[idx + 1 :] if idx >= 0 else norm


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_fo4port_shapes(
    source_nif_bytes: bytes,
    exclude_name_prefixes: Sequence[bytes] = (),
) -> List[ExtractedShape]:
    """Extract BSGeometry + BSLightingShaderProperty shapes from a converted FO4Port Starfield NIF."""
    nf = nifmod.parse(source_nif_bytes)
    shapes: List[ExtractedShape] = []
    for i, blk in enumerate(nf.blocks):
        if nf.type_of(i) != "BSGeometry":
            continue
        g = sfnif.parse_bsgeometry(blk)
        name_b = nf.strings[g.name_idx] if 0 <= g.name_idx < len(nf.strings) else b""
        if any(name_b.lower().startswith(pfx.lower()) for pfx in exclude_name_prefixes):
            continue
        m0 = g.meshes[0]
        if m0 is None or not m0.path:
            raise ActivatorNifError(f"BSGeometry block {i} ({name_b!r}) has no LOD0 external .mesh path")
        if not (0 <= g.shader < len(nf.blocks)) or nf.type_of(g.shader) != "BSLightingShaderProperty":
            raise ActivatorNifError(f"BSGeometry block {i} ({name_b!r}) lacks BSLightingShaderProperty")
        sh_name_idx, = struct.unpack_from("<i", nf.blocks[g.shader], 0)
        if not (0 <= sh_name_idx < len(nf.strings)):
            raise ActivatorNifError(f"BSLightingShaderProperty {g.shader} has invalid material string index")
        mat_path = nf.strings[sh_name_idx].decode("latin-1")
        mat_norm = normalize_archive_rel(mat_path)
        if "fo4port/" not in mat_norm or any(tok in mat_norm for tok in FORBIDDEN_PATH_TOKENS):
            raise ActivatorNifError(f"refused non-FO4Port material {mat_path!r} on shape {name_b!r}")
        shapes.append(
            ExtractedShape(
                name=name_b,
                mesh_path=m0.path,
                indices_size=m0.indices_size,
                num_verts=m0.num_verts,
                mesh_flags=m0.flags,
                material_path=mat_path,
                translation=g.translation,
                rotation=g.rotation,
                scale=g.scale,
                sphere=g.sphere,
                box=g.box,
            )
        )
    if not shapes:
        raise ActivatorNifError("no Fallout 4 BSGeometry shapes extracted from source NIF")
    return shapes


def build_activator_nif_bytes(
    root_name: bytes,
    shapes: Sequence[ExtractedShape],
    geom_shift: Tuple[float, float, float],
    box_template_blob: bytes,
    coll_center: Tuple[float, float, float],
    coll_half: Tuple[float, float, float],
) -> bytes:
    """Build a BS-173 activator NIF with 1 root layer-1 hknpBoxShape body (BSXFlags=0x2) and shifted Fallout shapes."""
    if not shapes:
        raise ActivatorNifError("cannot build activator NIF with zero shapes")
    sfcollision.check_template(box_template_blob)
    tmpl_bodies = sfbodies.blob_bodies(box_template_blob)
    if len(tmpl_bodies) != 1 or tmpl_bodies[0]["layer"] != 1:
        raise ActivatorNifError(f"box template must have 1 layer-1 body, got {[(b['shape'], b['layer']) for b in tmpl_bodies]}")

    coll_blob = sfcollision.box_blob(box_template_blob, coll_center, coll_half)

    f = nifmod.NifFile(
        endian=1,
        user_version=12,
        bs_version=173,
        author=b"\x00",
        unknown_int=0,
        export_script=b"\x00",
        sf_data=b"\x7a\x00",
    )
    s_node = f.string_index(root_name)
    s_bsx = f.string_index(b"BSX")
    s_matid = f.string_index(b"MaterialID")
    ident = struct.pack("<3f9ff", 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0)

    first = 4
    children = [first + 3 * i for i in range(len(shapes))]
    f.add_block(
        "NiNode",
        struct.pack("<iIiiI", s_node, 1, 1, -1, 0xE)
        + ident
        + struct.pack("<iI", 2, len(children))
        + struct.pack(f"<{len(children)}i", *children),
    )
    f.add_block("BSXFlags", struct.pack("<iI", s_bsx, 0x2))
    f.add_block("bhkNPCollisionObject", struct.pack("<iHiI", 0, 0x80, 3, 0))
    f.add_block("bhkPhysicsSystem", struct.pack("<I", len(coll_blob)) + coll_blob)

    dx, dy, dz = geom_shift
    for i, s in enumerate(shapes):
        base = first + 3 * i
        shifted_tr = (s.translation[0] + dx, s.translation[1] + dy, s.translation[2] + dz)
        # Note: verified on Starfield - Meshes01.ba2 (erroricon.nif): BSGeometry.sphere and .box remain in mesh-local
        # space before BSGeometry.translation is applied.
        g = sfnif.BSGeometry(
            name_idx=f.string_index(s.name),
            extra_refs=[base + 1],
            flags=0xE,
            translation=shifted_tr,
            rotation=s.rotation,
            scale=s.scale,
            sphere=s.sphere,
            box=s.box,
            shader=base + 2,
            meshes=[sfnif.MeshRef(s.indices_size, s.num_verts, s.mesh_flags, s.mesh_path), None, None, None],
        )
        f.add_block("BSGeometry", sfnif.build_bsgeometry(g))
        f.add_block("NiIntegerExtraData", struct.pack("<iI", s_matid, sfnif.material_id(s.material_path)))
        f.add_block(
            "BSLightingShaderProperty",
            struct.pack("<iIi", f.string_index(s.material_path.encode("latin-1")), 0, -1),
        )
    f.footer = struct.pack("<II", 1, 0)
    raw = nifmod.serialize(f)
    verify_activator_nif_bytes(raw, expected_center=coll_center, expected_half=coll_half)
    return raw


def verify_activator_nif_bytes(
    nif_bytes: bytes,
    expected_center: Optional[Tuple[float, float, float]] = None,
    expected_half: Optional[Tuple[float, float, float]] = None,
) -> Dict[str, object]:
    """Parse and strictly validate a Fallout-look Vault 111 activator NIF."""
    nf = nifmod.parse(nif_bytes)
    if nf.bs_version != 173:
        raise ActivatorNifError(f"expected bs_version 173, got {nf.bs_version}")
    if len(nf.blocks) < 7 or nf.type_of(0) != "NiNode" or nf.type_of(1) != "BSXFlags":
        raise ActivatorNifError("invalid root NiNode / BSXFlags layout")
    _, bsx_flags = struct.unpack_from("<iI", nf.blocks[1], 0)
    if bsx_flags != 0x2:
        raise ActivatorNifError(f"expected BSXFlags == 0x2 (HAVOK, non-EditorMarker), got 0x{bsx_flags:X}")

    if nf.type_of(2) != "bhkNPCollisionObject" or nf.type_of(3) != "bhkPhysicsSystem":
        raise ActivatorNifError("expected root bhkNPCollisionObject [2] and bhkPhysicsSystem [3]")
    tgt, cflags, cdata, body_id = struct.unpack_from("<iHiI", nf.blocks[2], 0)
    if (tgt, cflags, cdata, body_id) != (0, 0x80, 3, 0):
        raise ActivatorNifError(f"unexpected bhkNPCollisionObject header {(tgt, cflags, cdata, body_id)}")

    nbytes, = struct.unpack_from("<I", nf.blocks[3], 0)
    blob = nf.blocks[3][4 : 4 + nbytes]
    sfcollision.check_template(blob)
    bodies = sfbodies.blob_bodies(blob)
    if len(bodies) != 1 or bodies[0]["layer"] != 1 or bodies[0]["shape"] != "hknpBoxShape":
        raise ActivatorNifError(f"expected 1 layer-1 hknpBoxShape body, got {[(b['shape'], b['layer']) for b in bodies]}")

    got_center, got_half = sfcollision.read_box(blob)
    if not all(math.isfinite(v) for v in (*got_center, *got_half)):
        raise ActivatorNifError("non-finite Havok box corners")
    if expected_center is not None:
        for a in range(3):
            if abs(got_center[a] - expected_center[a]) > 1e-4:
                raise ActivatorNifError(f"collision center {got_center} != expected {expected_center}")
    if expected_half is not None:
        for a in range(3):
            if abs(got_half[a] - expected_half[a]) > 1e-4:
                raise ActivatorNifError(f"collision half-extents {got_half} != expected {expected_half}")

    for raw_s in nf.strings:
        s_low = normalize_archive_rel(raw_s.decode("latin-1", "replace"))
        for tok in FORBIDDEN_PATH_TOKENS:
            if tok in s_low:
                raise ActivatorNifError(f"forbidden Starfield/marker token {tok!r} in NIF string {s_low!r}")

    shape_count = 0
    total_verts = 0
    total_tris = 0
    materials: List[str] = []
    for i, blk in enumerate(nf.blocks):
        if nf.type_of(i) != "BSGeometry":
            continue
        g = sfnif.parse_bsgeometry(blk)
        nm = nf.strings[g.name_idx].decode("latin-1", "replace") if 0 <= g.name_idx < len(nf.strings) else ""
        if "editormarker" in nm.lower():
            raise ActivatorNifError(f"EditorMarker geometry {nm!r} is forbidden in Route 1 Fallout activator NIF")
        m0 = g.meshes[0]
        if m0 is None or m0.num_verts <= 0 or m0.indices_size <= 0 or m0.indices_size % 3 != 0:
            raise ActivatorNifError(f"BSGeometry {nm!r} has invalid LOD0 mesh reference")
        if len(g.extra_refs) != 1 or nf.type_of(g.extra_refs[0]) != "NiIntegerExtraData":
            raise ActivatorNifError(f"BSGeometry {nm!r} missing MaterialID NiIntegerExtraData")
        _, got_crc = struct.unpack_from("<iI", nf.blocks[g.extra_refs[0]], 0)
        if not (0 <= g.shader < len(nf.blocks)) or nf.type_of(g.shader) != "BSLightingShaderProperty":
            raise ActivatorNifError(f"BSGeometry {nm!r} missing BSLightingShaderProperty")
        sh_idx, = struct.unpack_from("<i", nf.blocks[g.shader], 0)
        mat = nf.strings[sh_idx].decode("latin-1")
        mat_norm = normalize_archive_rel(mat)
        if "fo4port/" not in mat_norm:
            raise ActivatorNifError(f"BSGeometry {nm!r} uses non-FO4Port material {mat!r}")
        if got_crc != sfnif.material_id(mat):
            raise ActivatorNifError(f"BSGeometry {nm!r} MaterialID 0x{got_crc:08X} != expected 0x{sfnif.material_id(mat):08X}")
        shape_count += 1
        total_verts += m0.num_verts
        total_tris += m0.indices_size // 3
        materials.append(mat)

    if shape_count == 0:
        raise ActivatorNifError("activator NIF contains zero BSGeometry shapes")

    return {
        "bs_version": nf.bs_version,
        "bsx_flags": bsx_flags,
        "shape_count": shape_count,
        "total_verts": total_verts,
        "total_tris": total_tris,
        "materials": materials,
        "collision_shape": bodies[0]["shape"],
        "collision_layer": bodies[0]["layer"],
        "collision_center": got_center,
        "collision_half": got_half,
        "starfield_tris": 0,
    }


def build_pair_from_source_bytes(
    pipboy_source_nif: bytes,
    console_source_nif: bytes,
    box_template_blob: bytes,
) -> Tuple[bytes, bytes]:
    """Build `(pipboy_pickup_nif_bytes, geardoor_console_nif_bytes)` from raw source NIFs and a vanilla box template."""
    # Exclude SkeletonHand01 from 0A00080E so the pickup activator carries ONLY the Fallout 4 Pip-Boy 3000 itself.
    pb_shapes = extract_fo4port_shapes(pipboy_source_nif, exclude_name_prefixes=(b"SkeletonHand",))
    con_shapes = extract_fo4port_shapes(console_source_nif)
    pb_nif = build_activator_nif_bytes(
        b"v111_pipboy_pickup",
        pb_shapes,
        PIPBOY_GEOM_SHIFT,
        box_template_blob,
        PIPBOY_COLLISION_CENTER,
        PIPBOY_COLLISION_HALF,
    )
    con_nif = build_activator_nif_bytes(
        b"v111_geardoor_console",
        con_shapes,
        CONSOLE_GEOM_SHIFT,
        box_template_blob,
        CONSOLE_COLLISION_CENTER,
        CONSOLE_COLLISION_HALF,
    )
    return pb_nif, con_nif


def _find_in_archives(archives: Iterable[ba2.Ba2], rel_path: str) -> Optional[bytes]:
    norm = rel_path.replace("/", "\\").lower()
    for arc in archives:
        hit = arc.find(norm)
        if hit is not None:
            return arc.read(hit)
    return None


def load_box_template_from_archives(sf_archives: Sequence[ba2.Ba2]) -> bytes:
    """Locate a verified 6,168-byte layer-1 hknpBoxShape Havok blob from Starfield's mesh archives."""
    for cand in VANILLA_BOX_TEMPLATE_CANDIDATES:
        raw_nif = _find_in_archives(sf_archives, cand)
        if not raw_nif:
            continue
        nf = nifmod.parse(raw_nif)
        for i, blk in enumerate(nf.blocks):
            if nf.type_of(i) == "bhkPhysicsSystem":
                sz, = struct.unpack_from("<I", blk, 0)
                blob = blk[4 : 4 + sz]
                try:
                    sfcollision.check_template(blob)
                    bds = sfbodies.blob_bodies(blob)
                    if len(bds) == 1 and bds[0]["layer"] == 1:
                        return blob
                except (ValueError, sfcollision.CollisionError):
                    continue
    raise ActivatorNifError("could not find a 6,168-byte layer-1 hknpBoxShape template in Starfield - Meshes*.ba2")


def ensure_game_closed_if_live_install(sf_data_dir: str, system=None) -> None:
    """R4/ownership guard: refuse reading live game archives while Starfield.exe is running."""
    parent = os.path.dirname(os.path.abspath(sf_data_dir))
    if os.path.isfile(os.path.join(parent, GAME_EXE)):
        sys_obj = system if system is not None else System()
        pids = sys_obj.pids(GAME_EXE)
        if pids:
            raise ActivatorNifError(f"{GAME_EXE} is running ({pids}); close the game before staging")


def stage_vault_activators(out_dir: str, port_esm: str, starfield_esm: str, system=None) -> Dict[str, str]:
    """Generate both Fallout-look Vault 111 activator NIFs under `<out_dir>/Data/meshes/fo4sf/newgame/`
    and return `{staged_rel_posix: sha256}`."""
    sf_data = os.path.dirname(os.path.abspath(starfield_esm))
    port_data = os.path.dirname(os.path.abspath(port_esm))
    ensure_game_closed_if_live_install(sf_data, system=system)
    if os.path.normcase(port_data) != os.path.normcase(sf_data):
        ensure_game_closed_if_live_install(port_data, system=system)

    port_ba2_candidates = [
        os.path.join(port_data, "FO4Port - Main.ba2"),
        os.path.join(sf_data, "FO4Port - Main.ba2"),
    ]
    port_ba2_path = next((p for p in port_ba2_candidates if os.path.isfile(p)), None)
    if port_ba2_path is None:
        raise ActivatorNifError(f"missing FO4Port - Main.ba2 alongside {port_esm}")

    sf_mesh_paths = sorted(glob.glob(os.path.join(sf_data, "Starfield - Meshes*.ba2")))
    if not sf_mesh_paths:
        raise ActivatorNifError(f"missing Starfield - Meshes*.ba2 alongside {starfield_esm}")

    port_arc = ba2.Ba2(port_ba2_path)
    pb_src = _find_in_archives((port_arc,), PORT_PIPBOY_SOURCE_NIF)
    con_src = _find_in_archives((port_arc,), PORT_CONSOLE_SOURCE_NIF)
    if pb_src is None:
        raise ActivatorNifError(f"FO4Port - Main.ba2 lacks {PORT_PIPBOY_SOURCE_NIF}")
    if con_src is None:
        raise ActivatorNifError(f"FO4Port - Main.ba2 lacks {PORT_CONSOLE_SOURCE_NIF}")

    sf_arcs = [ba2.Ba2(p) for p in sf_mesh_paths]
    box_tmpl = load_box_template_from_archives(sf_arcs)

    pb_nif, con_nif = build_pair_from_source_bytes(pb_src, con_src, box_tmpl)

    outputs: Dict[str, str] = {}
    for rel_posix, payload in ((PIPBOY_STAGED_REL, pb_nif), (CONSOLE_STAGED_REL, con_nif)):
        dst = os.path.join(out_dir, *rel_posix.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(payload)
        outputs[rel_posix] = sha256_bytes(payload)
    return outputs
