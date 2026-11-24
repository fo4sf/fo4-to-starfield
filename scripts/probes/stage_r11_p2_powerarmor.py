#!/usr/bin/env python3
"""stage_r11_p2_powerarmor.py: Round 11 Probe P2 (Concord Roof Power Armor Frame, T-45, Fusion Core Gate & Vertibird Minigun) stager, verifier & installer.

Builds the standalone Probe P2 folder outside Git worktrees, outside Starfield\\Data, and outside candidate-*:
  <out-dir>/
    core/
      FO4SFCoreValues.esm                    (with 0x00089F FO4_Ammo5mm + 0x0008A0 FO4_Minigun)
      FO4SFPowerArmor.esm                    (0x0801 FURN FO4 mesh, 0x0802 RACE.NAM4=0x09150B, 0x0809 Fusion Core,
                                              T-45 ARMOs/ARMAs, 0x081E ModFallingDamage=0 perk, 0 "FO4SF " FULLs)
    assets/
      meshes/fo4sf/powerarmor/{powerarmorfurniture,vertibirdminigun,fusioncore,pa_exit_terminal,frame,frame_exo,t45_*}.nif
      meshes/fo4sf/weapons/minigun/fo4_minigun.nif
      meshes/fo4core/ammo/5mm/5mmammo.nif
      geometries/...                         (external .mesh v2)
      materials/...                          (.mat)
      textures/...                           (BC1/BC4/BC5 DX10 .dds)
    exp/
      FO4SF_R11P2PowerArmor.esm              (0 WRLD/PNDT/ext-CELL overrides; persistent roof/exit refs + QUST)
      FO4SF_R11P2PowerArmor - Main.ba2       (BTDX v2 GNRL: .pex + .nif + .mesh + .mat)
      FO4SF_R11P2PowerArmor - Textures.ba2   (BTDX v2 DX10: .dds)
      Data/Scripts/{FO4SF_PowerArmorCoreQuest.pex,FO4SF_R11P2Quest.pex}
    sfse/SFSE/Plugins/FO4SFPipboyMenu.{dll,ini}  (reused verified binary sha256 7d5ba49c... when unmodified)
    bat/{p2h1,p2h2,p2r,p2f,p2g,p2w,p2d,p2c,p2x,p2s,p2q}.txt
    manifest.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SRC_DIR = REPO / "src"
PA_SCRIPTS_DIR = REPO / "scripts" / "powerarmor"
ACTORS_SCRIPTS_DIR = REPO / "scripts" / "actors"

for _p in (str(HERE), str(SRC_DIR), str(PA_SCRIPTS_DIR), str(ACTORS_SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_power_armor_core as pacore  # noqa: E402
import probe_common  # noqa: E402
import stage_c5_actor_looks as c5  # noqa: E402
from fo4sf import ba2 as ba2mod, convert_static, nif as nifmod, pipeline, sfnif, textures  # noqa: E402
from fo4sf.planet.esm import PERSISTENT, Plugin, parse_subrecords  # noqa: E402

PROBE_ID = "r11_p2_powerarmor"
PROBE_NAME = "r11-p2-powerarmor"
PROBE_STEM = "FO4SF_R11P2PowerArmor"
PROBE_PLUGIN = f"{PROBE_STEM}.esm"
PROBE_MAIN_BA2 = f"{PROBE_STEM} - Main.ba2"
PROBE_TEX_BA2 = f"{PROBE_STEM} - Textures.ba2"
DEFAULT_PIPBOY_SRC_DIR = REPO / "sfse" / "FO4SFPipboyMenu"

STANDIN_DISCLOSURE = (
    "PA furniture (0x0801 PowerArmorFurniture.nif), T-45 chest/helmet/arms/legs/exoskeleton NIFs, "
    "RACE.NAM4=0x0009150B (MaterialActorMetalLarge), StandingTerminal01 exit activator (0x0803), "
    "and Vertibird Minigun (0001F582/0001F583) use converted Fallout 4 meshes. Entry/exit uses a "
    "scripted FadeOutGame+equip stand-in; true Power Armor climb-in/out and movement animations belong "
    "to Claude's animation track."
)

# Master indices in FO4SF_R11P2PowerArmor.esm:
#   0x00 Starfield.esm
#   0x01 FO4SFCoreValues.esm
#   0x02 FO4SFPowerArmor.esm
#   0x03 FO4SF_R11P2PowerArmor.esm (local)
M_SF = 0x00
M_CV = 0x01
M_PA = 0x02
M_LOCAL = 0x03

SF_AV_HEALTH = 0x0002D4
CV_AMMO_5MM = (M_CV << 24) | 0x00089F
CV_WEAP_MINIGUN = (M_CV << 24) | 0x0008A0

PA_FRAME_FURN = (M_PA << 24) | 0x000801
PA_RACE = (M_PA << 24) | 0x000802
PA_CORE_QUEST = (M_PA << 24) | 0x000805
PA_FUSION_CORE = (M_PA << 24) | 0x000809
PA_NO_FALL_PERK = (M_PA << 24) | 0x00081E
EXPECTED_METAL_MATT_ID = 0x0009150B

FID_ACTI_MINIGUN = (M_LOCAL << 24) | 0x000801
FID_CELL_HOLDING = (M_LOCAL << 24) | 0x000802
FID_ACTI_EXIT = (M_LOCAL << 24) | 0x000803
FID_REF_ROOF_FRAME = (M_LOCAL << 24) | 0x000810
FID_REF_ROOF_MINIGUN = (M_LOCAL << 24) | 0x000811
FID_REF_ROOF_SPARE_CORE = (M_LOCAL << 24) | 0x000812
FID_REF_ROOF_EXIT = (M_LOCAL << 24) | 0x000813
FID_REF_STREET_EXIT = (M_LOCAL << 24) | 0x000814
QUST_P2_LOCAL_ID = 0x000820
FID_QUST_P2 = (M_LOCAL << 24) | QUST_P2_LOCAL_ID

QUST_DNAM_START_GAME_AND_REPEAT = 0x00000009
VANILLA_COLLISION_DONOR = r"meshes\setdressing\outpost\switches\poweredlever01.nif"
EXIT_TERMINAL_FO4_SRC = r"Meshes\SetDressing\Terminals\StandingTerminal01.nif"
EXIT_TERMINAL_SF_REL = "meshes/fo4sf/powerarmor/pa_exit_terminal.nif"
EXIT_TERMINAL_MODL = b"fo4sf\\powerarmor\\pa_exit_terminal.nif\x00"

EXPECTED_STATIC_NIFS: Tuple[str, ...] = (
    "meshes/fo4sf/powerarmor/powerarmorfurniture.nif",
    "meshes/fo4sf/powerarmor/vertibirdminigun.nif",
    "meshes/fo4sf/powerarmor/fusioncore.nif",
    EXIT_TERMINAL_SF_REL,
)
EXPECTED_SKINNED_NIFS: Tuple[str, ...] = (
    "meshes/fo4sf/powerarmor/frame.nif",
    "meshes/fo4sf/powerarmor/frame_exo.nif",
    "meshes/fo4sf/powerarmor/t45_body.nif",
    "meshes/fo4sf/powerarmor/t45_helmet.nif",
    "meshes/fo4sf/powerarmor/t45_larm.nif",
    "meshes/fo4sf/powerarmor/t45_rarm.nif",
    "meshes/fo4sf/powerarmor/t45_lleg.nif",
    "meshes/fo4sf/powerarmor/t45_rleg.nif",
)
EXPECTED_MINIGUN_NIFS: Tuple[str, ...] = (
    "meshes/fo4sf/weapons/minigun/fo4_minigun.nif",
    "meshes/fo4core/ammo/5mm/5mmammo.nif",
)
MINIGUN_CONTROLLER_SIDECAR = "meshes/fo4sf/weapons/minigun/fo4_minigun_controllers.json"
ALL_EXPECTED_NIFS: Tuple[str, ...] = EXPECTED_STATIC_NIFS + EXPECTED_SKINNED_NIFS + EXPECTED_MINIGUN_NIFS

SANCTUARY_POS = (-2329.00, -1420.00, 99.00)
MID_HOP_1_POS = (-2170.00, -1560.00, 102.00)
CONCORD_FRONT_POS = (-2012.50, -1697.94, 88.70)
# P2-F1: FO4 0002C1C6 XTEL exterior landing right beside roof frame 000370E3 (-1995.73, -1723.10, 97.54)
MUSEUM_ROOF_ARRIVAL_POS = (-1990.58, -1724.19, 97.56)
ROOF_VERTIBIRD_PERCH_POS = (-2004.72, -1717.00, 102.40)
# P2-F8: Clear ~18 m street drop above Concord ground (~86.5 m), exceeding Mars 0.38g velocity min (10.0 m/s)
STREET_DROP_OVER_LEDGE_POS = (-1995.73, -1738.00, 104.54)

P2_ANCHORS: Dict[str, probe_common.AnchorPoint] = {
    "sanctuary_wb": probe_common.AnchorPoint("sanctuary_wb", *SANCTUARY_POS, "exterior"),
    "mid_hop_1": probe_common.AnchorPoint("mid_hop_1", *MID_HOP_1_POS, "exterior"),
    "concord_marker": probe_common.AnchorPoint("concord_marker", *CONCORD_FRONT_POS, "exterior"),
}

P2_HOPS: Tuple[probe_common.HopSpec, ...] = (
    probe_common.HopSpec("p2h1", "sanctuary_wb", *MID_HOP_1_POS, "exterior"),
    probe_common.HopSpec("p2h2", "mid_hop_1", *CONCORD_FRONT_POS, "exterior"),
    probe_common.HopSpec("p2r", "concord_marker", *MUSEUM_ROOF_ARRIVAL_POS, "exterior"),
    probe_common.HopSpec("p2w", "concord_marker", *ROOF_VERTIBIRD_PERCH_POS, "exterior"),
    probe_common.HopSpec("p2d", "concord_marker", *STREET_DROP_OVER_LEDGE_POS, "exterior"),
    probe_common.HopSpec("p2c", "concord_marker", *STREET_DROP_OVER_LEDGE_POS, "exterior"),
)

UNSTAMPED_SLOT_TOKEN = "XX"
STAMPED_SETSTAGE_BATCHES: Tuple[str, ...] = (
    "p2r.txt",
    "p2f.txt",
    "p2g.txt",
    "p2w.txt",
    "p2d.txt",
    "p2c.txt",
    "p2x.txt",
    "p2s.txt",
    "p2q.txt",
)


class ProbeP2Error(ValueError):
    """Raised when P2 staging, asset validation, or verification fails."""


def build_p2_powerarmor_esm() -> bytes:
    """Build FO4SF_R11P2PowerArmor.esm (ZERO WRLD/PNDT/ext-CELL overrides)."""
    acti_minigun = probe_common.rec_bytes(
        b"ACTI",
        FID_ACTI_MINIGUN,
        [
            (b"EDID", b"FO4SF_P2_MinigunActi\x00"),
            (b"OBND", struct.pack("<6f", -0.45, -0.45, -0.45, 0.45, 0.45, 0.45)),
            (b"ODTY", struct.pack("<I", 0)),
            (b"FULL", b"Vertibird Minigun\x00"),
            (b"MODL", b"fo4sf\\powerarmor\\vertibirdminigun.nif\x00"),
            (b"ATTX", b"Take Minigun\x00"),
            (b"FNAM", struct.pack("<H", 0)),
        ],
    )
    acti_exit = probe_common.rec_bytes(
        b"ACTI",
        FID_ACTI_EXIT,
        [
            (b"EDID", b"FO4SF_P2_ExitActi\x00"),
            (b"OBND", struct.pack("<6f", -0.38, -0.77, 0.0, 0.38, 0.77, 2.39)),
            (b"ODTY", struct.pack("<I", 0)),
            (b"FULL", b"Power Armor Exit Terminal\x00"),
            (b"MODL", EXIT_TERMINAL_MODL),
            (b"ATTX", b"Exit Power Armor\x00"),
            (b"FNAM", struct.pack("<H", 0)),
        ],
    )

    holding_cell = probe_common.rec_bytes(
        b"CELL",
        FID_CELL_HOLDING,
        [
            (b"EDID", b"FO4SF_P2_HoldingCell\x00"),
            (b"DATA", struct.pack("<I", 1)),
            (b"LTMP", struct.pack("<I", 0x0006BCF8)),
            (b"XCIM", struct.pack("<I", 0x00122393)),
            (b"XEMP", b"Data\\Textures\\Cubemaps\\Cell_HiTechHallCube.dds\x00"),
        ],
    )

    ref_frame = probe_common.refr_item(
        FID_REF_ROOF_FRAME,
        "FO4SF_P2_RoofFrameRef",
        PA_FRAME_FURN,
        (0.0, 0.0, 0.0),
        (0.0, 0.0, math.radians(351.07)),
        flags=PERSISTENT,
    )
    ref_minigun = probe_common.refr_item(
        FID_REF_ROOF_MINIGUN,
        "FO4SF_P2_RoofMinigunRef",
        FID_ACTI_MINIGUN,
        (4.0, 0.0, 0.5),
        (math.radians(-0.86), math.radians(13.47), math.radians(292.55)),
        flags=PERSISTENT,
    )
    ref_spare_core = probe_common.refr_item(
        FID_REF_ROOF_SPARE_CORE,
        "FO4SF_P2_RoofSpareCoreRef",
        PA_FUSION_CORE,
        (-3.0, 0.0, 0.1),
        flags=PERSISTENT,
    )
    ref_roof_exit = probe_common.refr_item(
        FID_REF_ROOF_EXIT,
        "FO4SF_P2_RoofExitRef",
        FID_ACTI_EXIT,
        (2.0, -2.0, 0.0),
        (0.0, 0.0, math.radians(315.0)),
        flags=PERSISTENT,
    )
    ref_street_exit = probe_common.refr_item(
        FID_REF_STREET_EXIT,
        "FO4SF_P2_StreetExitRef",
        FID_ACTI_EXIT,
        (-2.0, -4.0, 0.0),
        flags=PERSISTENT,
    )

    cell_lbl = struct.pack("<I", FID_CELL_HOLDING)
    pers_grup = probe_common.grup_bytes(
        cell_lbl, 8, ref_frame + ref_minigun + ref_spare_core + ref_roof_exit + ref_street_exit
    )
    cell_children = probe_common.grup_bytes(cell_lbl, 6, pers_grup)
    local_cell_id = FID_CELL_HOLDING & 0xFFFFFF
    subblock_grup = probe_common.grup_bytes(struct.pack("<i", (local_cell_id // 10) % 10), 3, holding_cell + cell_children)
    block_grup = probe_common.grup_bytes(struct.pack("<i", local_cell_id % 10), 2, subblock_grup)

    props = [
        {"name": "RoofFrameRef", "type": probe_common.VMAD_T_OBJECT, "status": 1, "value": {"form": FID_REF_ROOF_FRAME, "alias": -1}},
        {"name": "RoofMinigunRef", "type": probe_common.VMAD_T_OBJECT, "status": 1, "value": {"form": FID_REF_ROOF_MINIGUN, "alias": -1}},
        {"name": "RoofSpareCoreRef", "type": probe_common.VMAD_T_OBJECT, "status": 1, "value": {"form": FID_REF_ROOF_SPARE_CORE, "alias": -1}},
        {"name": "RoofExitRef", "type": probe_common.VMAD_T_OBJECT, "status": 1, "value": {"form": FID_REF_ROOF_EXIT, "alias": -1}},
        {"name": "StreetExitRef", "type": probe_common.VMAD_T_OBJECT, "status": 1, "value": {"form": FID_REF_STREET_EXIT, "alias": -1}},
        {"name": "HealthAV", "type": probe_common.VMAD_T_OBJECT, "status": 1, "value": {"form": SF_AV_HEALTH, "alias": -1}},
        {"name": "EnableLog", "type": probe_common.VMAD_T_BOOL, "status": 1, "value": True},
        {"name": "LogName", "type": probe_common.VMAD_T_STRING, "status": 1, "value": "fo4sf_r11p2"},
    ]
    q_vmad = probe_common.encode_vmad_v6(
        [{"name": "FO4SF_R11P2Quest", "status": 0, "properties": props}],
        tail=probe_common.QUST_VMAD_TAIL,
    )

    q_subs: List[Tuple[bytes, bytes]] = [
        (b"EDID", b"FO4SF_R11P2Quest\x00"),
        (b"VMAD", q_vmad),
        (b"FULL", b"R11 P2 Power Armor Probe\x00"),
        (b"DNAM", struct.pack("<III", QUST_DNAM_START_GAME_AND_REPEAT, 50, 0)),
        (b"QTYP", struct.pack("<I", 0x00047600)),
    ]
    for st in (10, 20, 30, 40, 50, 60, 70, 75, 80):
        q_subs.append((b"INDX", struct.pack("<I", st)))
        q_subs.append((b"QSDT", b"\x00"))
    quest_rec = probe_common.rec_bytes(b"QUST", FID_QUST_P2, q_subs, flags=0, version=581)

    body = (
        probe_common.grup_bytes(b"ACTI", 0, acti_minigun + acti_exit)
        + probe_common.grup_bytes(b"CELL", 0, block_grup)
        + probe_common.grup_bytes(b"QUST", 0, quest_rec)
    )
    masters = ("Starfield.esm", "FO4SFCoreValues.esm", "FO4SFPowerArmor.esm")
    return probe_common.build_esm(masters, body, 0x000821, flags=1, version=576, hedr_version=0.96)


# ---------------------------------------------------------------------------
# FO4 + Starfield asset conversion and transitive NIF verification
# ---------------------------------------------------------------------------
def _safe_texconv(texconv_exe, src, out_dir, fmt, extra=()):
    """Invoke xtexconv.exe using cp437 decoding because BC1_UNORM_SRGB logs non-UTF8 symbols."""
    mips = () if "-m" in extra else ("-m", "0")
    r = subprocess.run(
        [texconv_exe, "-nologo", "-y", *mips, "-dx10", "-f", fmt, *extra, "-o", out_dir, src],
        capture_output=True,
        text=True,
        encoding="cp437",
        errors="replace",
    )
    if r.returncode != 0 or "FAILED" in (r.stdout or ""):
        raise textures.DdsError(
            f"texconv failed for {src}: {(r.stdout or '').strip()[-300:]} {(r.stderr or '').strip()[-200:]}"
        )


_ORIG_C5_BONE_MAPPER = c5.fo4_human_bone_to_sf


def _pa_bone_mapper(fo4_bone: Optional[str], available: Sequence[str]) -> str:
    if fo4_bone and "pauldron" in fo4_bone.lower():
        side = "L" if fo4_bone.lower().startswith("l") else "R"
        for cand in (f"{side}_Deltoid", f"{side}_Biceps", f"{side}_Clavicle"):
            if cand in available:
                return cand
    return _ORIG_C5_BONE_MAPPER(fo4_bone, available)


def _collect_nif_transitive_deps(assets_root: Path, nif_rel: str) -> List[str]:
    """Return sorted relative posix paths (.nif, .mesh, .mat, .dds) required by `nif_rel`."""
    def _norm(p: str) -> str:
        s = re.sub(r"/+", "/", p.replace("\\", "/").strip()).lstrip("/")
        if s.lower().startswith("data/"):
            s = s[5:].lstrip("/")
        return s.lower()

    deps = {_norm(nif_rel)}
    nf = nifmod.parse((assets_root / nif_rel).read_bytes())
    for bi in range(len(nf.blocks)):
        if nf.type_of(bi) != "BSGeometry":
            continue
        g = sfnif.parse_bsgeometry(nf.blocks[bi])
        for m in g.meshes:
            if m is not None:
                mp = _norm(m.path.decode("latin-1"))
                deps.add(f"geometries/{mp}.mesh")
        if 0 <= g.shader < len(nf.blocks):
            sh_nidx, = struct.unpack_from("<i", nf.blocks[g.shader], 0)
            if 0 <= sh_nidx < len(nf.strings):
                mat_rel = _norm(nf.strings[sh_nidx].decode("latin-1"))
                deps.add(mat_rel)
                mat_file = assets_root / mat_rel
                if mat_file.is_file():
                    mat_txt = mat_file.read_text(encoding="utf-8", errors="replace")
                    for tex in re.findall(r'"([^"]+\.dds)"', mat_txt, re.I):
                        deps.add(_norm(tex))
    return sorted(deps)


def convert_p2_assets(
    assets_dir: Path,
    *,
    fo4_data: Path,
    sf_data: Path,
    cr_zip: Path,
    texconv_exe: Path,
    weapons_assets_dir: Path,
) -> Dict[str, Any]:
    """Convert FO4 Power Armor static + exit activator + skinned T-45 NIFs and stage Minigun/5mm assets."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    fo4 = pipeline.Fo4Archives(str(fo4_data))
    sf_meshes = [ba2mod.Ba2(str(p)) for p in sorted(sf_data.glob("Starfield - Meshes*.ba2"))]

    def sf_read(sub_rel: str) -> bytes:
        norm = sub_rel.replace("/", "\\")
        for arc in sf_meshes:
            idx = arc.find(norm)
            if idx is not None:
                return arc.read(idx)
        raise FileNotFoundError(f"Missing {sub_rel} in Starfield - Meshes*.ba2")

    tmpl_raw = sf_read(VANILLA_COLLISION_DONOR)
    coll_tmpl = convert_static.collision_template_from_nif(tmpl_raw)
    body_tmpl = sf_read(c5.SF_BODY_TEMPLATE)
    hat_tmpl = sf_read(c5.SF_HAT_TEMPLATE)

    orig_texconv = textures.texconv
    orig_mapper = c5.fo4_human_bone_to_sf
    textures.texconv = _safe_texconv
    c5.fo4_human_bone_to_sf = _pa_bone_mapper
    skinned_reports: Dict[str, Any] = {}
    static_reports: Dict[str, Any] = {}
    try:
        conv = pipeline.Converter(
            fo4,
            str(assets_dir),
            str(texconv_exe),
            str(cr_zip),
            collision_template=coll_tmpl,
            prefix="fo4sf/powerarmor",
        )

        # 1. Static FO4 PowerArmorFurniture, VertibirdMinigun, FusionCore, and PA Exit Terminal
        for src_rel, dst_rel, inc_skin in (
            (r"Meshes\Furniture\PowerArmor\CharacterAssets\PowerArmorFurniture.nif", "meshes/fo4sf/powerarmor/powerarmorfurniture.nif", True),
            (r"Meshes\Weapons\Minigun\VertibirdMinigun.nif", "meshes/fo4sf/powerarmor/vertibirdminigun.nif", False),
            (r"Meshes\Ammo\FusionCore\FusionCore.nif", "meshes/fo4sf/powerarmor/fusioncore.nif", False),
            (EXIT_TERMINAL_FO4_SRC, EXIT_TERMINAL_SF_REL, False),
        ):
            raw = fo4.mesh(src_rel)
            nf = nifmod.parse(raw)
            mat_paths: List[Optional[str]] = []
            for ts in nifmod.fo4_trishapes(nf):
                mat_paths.append(conv._shape_material(nf, ts))
            out_files = convert_static.convert_static(
                raw,
                dst_rel[len("meshes/"):-4],
                material_paths=mat_paths,
                collision_template=coll_tmpl,
                include_skinned=inc_skin,
            )
            for rel, blob in out_files.items():
                dst_p = assets_dir / rel
                dst_p.parent.mkdir(parents=True, exist_ok=True)
                dst_p.write_bytes(blob)
            static_reports[dst_rel] = {
                "source": src_rel,
                "include_skinned": inc_skin,
                "shapes": len([m for m in mat_paths if m is not None]),
            }

        # 2. Skinned FO4 Power Armor Frame + T-45 stand-in armor pieces
        skinned_specs = (
            ("meshes/fo4sf/powerarmor/frame.nif", body_tmpl, r"Meshes\Actors\PowerArmor\CharacterAssets\Frame.nif", ("PAFrame01:0",)),
            ("meshes/fo4sf/powerarmor/frame_exo.nif", body_tmpl, r"Meshes\Actors\PowerArmor\CharacterAssets\Frame.nif", ("BaseMaleHands_reduced:0", "basesuit_reduced:0")),
            ("meshes/fo4sf/powerarmor/t45_body.nif", body_tmpl, r"Meshes\Actors\PowerArmor\CharacterAssets\Mods\PA_T45_Body.nif", ()),
            ("meshes/fo4sf/powerarmor/t45_helmet.nif", hat_tmpl, r"Meshes\Actors\PowerArmor\CharacterAssets\Mods\PA_T45_Helmet.nif", ()),
            ("meshes/fo4sf/powerarmor/t45_larm.nif", body_tmpl, r"Meshes\Actors\PowerArmor\CharacterAssets\Mods\PA_T45_LArm.nif", ()),
            ("meshes/fo4sf/powerarmor/t45_rarm.nif", body_tmpl, r"Meshes\Actors\PowerArmor\CharacterAssets\Mods\PA_T45_RArm.nif", ()),
            ("meshes/fo4sf/powerarmor/t45_lleg.nif", body_tmpl, r"Meshes\Actors\PowerArmor\CharacterAssets\Mods\PA_T45_LLeg.nif", ()),
            ("meshes/fo4sf/powerarmor/t45_rleg.nif", body_tmpl, r"Meshes\Actors\PowerArmor\CharacterAssets\Mods\PA_T45_RLeg.nif", ()),
        )
        for dst_rel, tmpl_bytes, src_rel, skip in skinned_specs:
            raw = fo4.mesh(src_rel)
            nf = nifmod.parse(raw)
            mats: Dict[str, str] = {}
            actual_skip = list(skip)
            for ts in nifmod.fo4_trishapes(nf):
                sname = ts.name.decode("latin-1")
                if sname in skip:
                    continue
                mpath = conv._shape_material(nf, ts)
                if mpath is None:
                    actual_skip.append(sname)
                else:
                    mats[sname] = mpath
            res = c5.rebind_human_skin_attach(tmpl_bytes, [(src_rel, raw, mats)], skip_shapes=tuple(actual_skip))
            dst_nif = assets_dir / dst_rel
            dst_nif.parent.mkdir(parents=True, exist_ok=True)
            dst_nif.write_bytes(res.nif)
            for (d, f), mb in res.meshes.items():
                fname = f if str(f).lower().endswith(".mesh") else f"{f}.mesh"
                mp = assets_dir / "geometries" / d / fname
                mp.parent.mkdir(parents=True, exist_ok=True)
                mp.write_bytes(mb)
            skinned_reports[dst_rel] = {
                "source": src_rel,
                "groups": res.report["groups"],
                "bound": res.report["bound"],
            }
    finally:
        textures.texconv = orig_texconv
        c5.fo4_human_bone_to_sf = orig_mapper

    # 3. Bundle FO4_Minigun + FO4_Ammo5mm transitive assets cleanly (read-only copy, post-F1/F2/F5/F6)
    minigun_copied: List[str] = []
    if not weapons_assets_dir.is_dir():
        raise ProbeP2Error(f"Missing weapons assets dir for Minigun/5mm: {weapons_assets_dir}")
    for rel_nif in EXPECTED_MINIGUN_NIFS:
        if not (weapons_assets_dir / rel_nif).is_file():
            raise ProbeP2Error(f"Missing weapon asset NIF: {weapons_assets_dir / rel_nif}")
        for dep in _collect_nif_transitive_deps(weapons_assets_dir, rel_nif):
            src_f = weapons_assets_dir / dep
            if not src_f.is_file():
                raise ProbeP2Error(f"Missing weapon transitive dependency {dep} in {weapons_assets_dir}")
            dst_f = assets_dir / dep
            probe_common.copy_or_link_staged_file(src_f, dst_f, allow_hardlink=False)
            minigun_copied.append(dep)
    ctrl_src = weapons_assets_dir / MINIGUN_CONTROLLER_SIDECAR
    if not ctrl_src.is_file():
        raise ProbeP2Error(f"Missing post-F6 Minigun controller sidecar: {ctrl_src}")
    probe_common.copy_or_link_staged_file(ctrl_src, assets_dir / MINIGUN_CONTROLLER_SIDECAR, allow_hardlink=False)
    minigun_copied.append(MINIGUN_CONTROLLER_SIDECAR)
    _verify_minigun_moving_parts_nif(assets_dir / "meshes/fo4sf/weapons/minigun/fo4_minigun.nif")

    # 4. Verify every expected NIF's full transitive closure exists in assets_dir
    for rel_nif in ALL_EXPECTED_NIFS:
        if not (assets_dir / rel_nif).is_file():
            raise ProbeP2Error(f"Missing converted NIF {rel_nif}")
        for dep in _collect_nif_transitive_deps(assets_dir, rel_nif):
            if not (assets_dir / dep).is_file():
                raise ProbeP2Error(f"Broken transitive asset dependency {dep} referenced by {rel_nif}")

    return {
        "static": static_reports,
        "skinned": skinned_reports,
        "minigun_transitive_count": len(sorted(set(minigun_copied))),
        "converter_stats": conv.stats,
        "converter_errors": conv.material_errors,
    }


def compile_p2_scripts(
    out_scripts_dir: Path,
    *,
    compiler_exe: Path,
    cr_zip: Path,
) -> Dict[str, str]:
    """Compile FO4SF_PowerArmorCoreQuest.psc and FO4SF_R11P2Quest.psc into `out_scripts_dir`."""
    out_scripts_dir.mkdir(parents=True, exist_ok=True)
    pa_psc = PA_SCRIPTS_DIR / "FO4SF_PowerArmorCoreQuest.psc"
    p2_psc = HERE / "FO4SF_R11P2Quest.psc"
    for p in (pa_psc, p2_psc):
        if not p.is_file():
            raise ProbeP2Error(f"Missing Papyrus source: {p}")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        flg_rel: Optional[str] = None
        with zipfile.ZipFile(cr_zip, "r") as zf:
            for name in zf.namelist():
                if name.startswith("Scripts/Source/") and (name.endswith(".psc") or name.endswith(".flg")):
                    out = tmp / name
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(zf.read(name))
                    if name.lower().endswith(".flg"):
                        flg_rel = name
        if flg_rel is None:
            raise ProbeP2Error(f"Starfield_Papyrus_Flags.flg missing in {cr_zip}")
        src_dir = tmp / "Scripts" / "Source"
        shutil.copy2(pa_psc, src_dir / pa_psc.name)
        shutil.copy2(p2_psc, src_dir / p2_psc.name)
        flg = tmp / flg_rel
        for stem in ("FO4SF_PowerArmorCoreQuest", "FO4SF_R11P2Quest"):
            cmd = [str(compiler_exe), stem, f"-i={src_dir}", f"-o={out_scripts_dir}", f"-f={flg}"]
            proc = subprocess.run(cmd, cwd=str(src_dir), capture_output=True, text=True)
            if proc.returncode != 0:
                raise ProbeP2Error(f"Papyrus compile failed for {stem}: {proc.stdout}\n{proc.stderr}")

    out_hashes: Dict[str, str] = {}
    for pex_name in ("FO4SF_PowerArmorCoreQuest.pex", "FO4SF_R11P2Quest.pex"):
        p = out_scripts_dir / pex_name
        if not p.is_file() or p.stat().st_size == 0:
            raise ProbeP2Error(f"Missing compiled PEX output: {p}")
        out_hashes[pex_name] = probe_common.sha256_file(p)
    return out_hashes


def render_p2_batches(slot_prefix: str = UNSTAMPED_SLOT_TOKEN) -> Dict[str, str]:
    """Generate P3-clean console batch files (0 m/n/v in stems or typed lines; <200m/axis hops)."""
    qf = f"{slot_prefix}000820"
    return {
        "p2h1.txt": (
            "; R11 P2 exterior mid-hop from Sanctuary (-2329,-1420,99) toward Concord (<160 m/axis)\n"
            f"player.setpos x {MID_HOP_1_POS[0]:.2f}\n"
            f"player.setpos y {MID_HOP_1_POS[1]:.2f}\n"
            f"player.setpos z {MID_HOP_1_POS[2]:.2f}\n"
            "player.setangle z 135\n"
        ),
        "p2h2.txt": (
            "; R11 P2 exterior hop from mid_hop_1 to Concord Museum street front (<158 m/axis)\n"
            f"player.setpos x {CONCORD_FRONT_POS[0]:.2f}\n"
            f"player.setpos y {CONCORD_FRONT_POS[1]:.2f}\n"
            f"player.setpos z {CONCORD_FRONT_POS[2]:.2f}\n"
            "player.setangle z 90\n"
        ),
        "p2r.txt": (
            "; R11 P2 Museum roof door arrival beside 000370E3 (<27 m/axis from concord_marker) + sync roof refs\n"
            f"player.setpos x {MUSEUM_ROOF_ARRIVAL_POS[0]:.2f}\n"
            f"player.setpos y {MUSEUM_ROOF_ARRIVAL_POS[1]:.2f}\n"
            f"player.setpos z {MUSEUM_ROOF_ARRIVAL_POS[2]:.2f}\n"
            "player.setangle z 282\n"
            f"SetStage {qf} 20\n"
        ),
        "p2f.txt": (
            "; R11 P2 trigger roof PA frame entry (refuses with log when 0 cores; equips T-45 stand-in when >=1)\n"
            f"SetStage {qf} 10\n"
        ),
        "p2g.txt": (
            "; R11 P2 grant 1x Fusion Core (0x0809)\n"
            f"SetStage {qf} 40\n"
        ),
        "p2w.txt": (
            "; R11 P2 perch beside Vertibird minigun & acquire Minigun + 1200x 5mm rounds\n"
            f"player.setpos x {ROOF_VERTIBIRD_PERCH_POS[0]:.2f}\n"
            f"player.setpos y {ROOF_VERTIBIRD_PERCH_POS[1]:.2f}\n"
            f"player.setpos z {ROOF_VERTIBIRD_PERCH_POS[2]:.2f}\n"
            "player.setangle z 0\n"
            f"SetStage {qf} 50\n"
        ),
        "p2d.txt": (
            "; R11 P2 armored drop from roof ledge above Concord street (logs hp_before/hp_after; 0 fall dmg in PA)\n"
            f"SetStage {qf} 75\n"
            f"player.setpos x {STREET_DROP_OVER_LEDGE_POS[0]:.2f}\n"
            f"player.setpos y {STREET_DROP_OVER_LEDGE_POS[1]:.2f}\n"
            f"player.setpos z {STREET_DROP_OVER_LEDGE_POS[2]:.2f}\n"
            "player.setangle z 180\n"
        ),
        "p2c.txt": (
            "; R11 P2 unarmored control drop from exact same spot (-1995.73,-1738.00,104.54; run after exiting PA)\n"
            f"SetStage {qf} 80\n"
            f"player.setpos x {STREET_DROP_OVER_LEDGE_POS[0]:.2f}\n"
            f"player.setpos y {STREET_DROP_OVER_LEDGE_POS[1]:.2f}\n"
            f"player.setpos z {STREET_DROP_OVER_LEDGE_POS[2]:.2f}\n"
            "player.setangle z 180\n"
        ),
        "p2x.txt": (
            "; R11 P2 scripted exit Power Armor stand-in fallback\n"
            f"SetStage {qf} 30\n"
        ),
        "p2s.txt": (
            "; R11 P2 sync/reset probe roof objects\n"
            f"SetStage {qf} 60\n"
        ),
        "p2q.txt": (
            "; R11 P2 query stages & append status snapshot to fo4sf_r11p2.0.log\n"
            f"getstage {qf}\n"
            f"sqs {qf}\n"
            f"SetStage {qf} 70\n"
        ),
    }


def _verify_minigun_moving_parts_nif(nif_path: Path) -> None:
    if not nif_path.is_file():
        raise ProbeP2Error(f"Missing Minigun NIF: {nif_path}")
    nf = nifmod.parse(nif_path.read_bytes())
    names = {s.decode("latin-1", "replace") for s in nf.strings}
    missing = [n for n in ("MiscA01", "Magazine", "ProjectileNode", "Minigun_Barrel") if n not in names]
    if missing:
        raise ProbeP2Error(f"{nif_path} missing F1/F2 Minigun NiNodes {missing}; expected post-F1 arsenal asset")


def _verify_core_values_has_minigun_and_5mm(cv_path: Path) -> None:
    if not cv_path.is_file():
        raise ProbeP2Error(f"Missing FO4SFCoreValues.esm: {cv_path}")
    found: Dict[int, str] = {}
    ammo_5mm_wt: Optional[float] = None
    minigun_mod4: Optional[str] = None
    for sig, fid, _fl, data in probe_common.walk_esm_records(cv_path.read_bytes()):
        lid = fid & 0xFFFFFF
        if lid in (0x000815, 0x00089F, 0x0008A0):
            subs = dict(parse_subrecords(data))
            edid = (subs.get(b"EDID") or b"").rstrip(b"\x00").decode("latin-1", "replace")
            found[lid] = f"{sig}:{edid}"
            if lid == 0x00089F and sig == "AMMO":
                raw_data = subs.get(b"DATA") or b""
                if len(raw_data) >= 8:
                    _val, ammo_5mm_wt = struct.unpack("<If", raw_data[:8])
            if lid == 0x0008A0 and sig == "WEAP":
                minigun_mod4 = (subs.get(b"MOD4") or subs.get(b"MODL") or b"").rstrip(b"\x00").decode("latin-1", "replace")
    for req_id, label in ((0x000815, "FO4SF_Special_Agility"), (0x00089F, "FO4_Ammo5mm"), (0x0008A0, "FO4_Minigun")):
        if req_id not in found:
            raise ProbeP2Error(f"{cv_path} missing required CoreValues record 0x{req_id:06X} ({label})")
    if ammo_5mm_wt is None or abs(ammo_5mm_wt - 0.009) > 1e-4:
        raise ProbeP2Error(f"{cv_path} FO4_Ammo5mm (0x00089F) DATA weight={ammo_5mm_wt!r} != 0.009 (post-F5 required)")
    if not minigun_mod4 or minigun_mod4.lower().replace("/", "\\") != r"fo4sf\weapons\minigun\fo4_minigun.nif":
        raise ProbeP2Error(f"{cv_path} FO4_Minigun (0x0008A0) MOD4={minigun_mod4!r} != fo4sf\\weapons\\minigun\\fo4_minigun.nif")


def _verify_p2_esms(pa_esm: Path, p2_esm: Path) -> None:
    prefixed_fulls: List[str] = []
    race_nam4_ok = False
    has_nofall_perk = False
    fusion_core_model_ok = False
    exit_acti_model_ok = False
    leaked_armo_subs: List[str] = []
    p2_persistent_refs: set[int] = set()
    quest_stages: List[int] = []
    quest_props: Dict[str, int] = {}

    for esm_p in (pa_esm, p2_esm):
        for sig, fid, fl, data in probe_common.walk_esm_records(esm_p.read_bytes()):
            subs = parse_subrecords(data)
            d = {t: v for t, v in subs}
            full = (d.get(b"FULL") or b"").rstrip(b"\x00").decode("latin-1", "replace")
            if full.startswith("FO4SF "):
                prefixed_fulls.append(f"{esm_p.name}:0x{fid:08X} ({full!r})")
            if esm_p == pa_esm and sig == "RACE" and (fid & 0xFFFFFF) == 0x0802:
                nam4 = d.get(b"NAM4")
                if nam4 and len(nam4) == 4 and struct.unpack("<I", nam4)[0] == EXPECTED_METAL_MATT_ID:
                    race_nam4_ok = True
            if esm_p == pa_esm and sig == "PERK" and (fid & 0xFFFFFF) == 0x081E:
                has_nofall_perk = True
            if esm_p == pa_esm and sig == "MISC" and (fid & 0xFFFFFF) == 0x0809:
                modl = (d.get(b"MODL") or b"").rstrip(b"\x00").decode("latin-1", "replace")
                if modl.lower().replace("/", "\\") == r"fo4sf\powerarmor\fusioncore.nif":
                    fusion_core_model_ok = True
            if esm_p == pa_esm and sig == "ARMO" and (fid & 0xFFFFFF) in {
                0x0816, 0x0817, 0x0818, 0x0819, 0x081A, 0x081B, 0x082A, 0x082B, 0x082C, 0x082D
            }:
                bad_tags = [t.decode("latin-1") for t, _v in subs if t in (b"INRD", b"OBTE", b"MOD2", b"MOD4")]
                if bad_tags:
                    leaked_armo_subs.append(f"0x{fid:08X}:{sorted(set(bad_tags))}")
            if esm_p == p2_esm and sig == "ACTI" and (fid & 0xFFFFFF) == 0x0803:
                modl = (d.get(b"MODL") or b"").rstrip(b"\x00").decode("latin-1", "replace")
                norm_modl = modl.lower().replace("/", "\\")
                if norm_modl == r"fo4sf\powerarmor\pa_exit_terminal.nif" and "marker" not in norm_modl:
                    exit_acti_model_ok = True
            if esm_p == p2_esm and sig == "REFR" and (fl & PERSISTENT):
                p2_persistent_refs.add(fid & 0xFFFFFF)
            if esm_p == p2_esm and sig == "QUST" and (fid & 0xFFFFFF) == QUST_P2_LOCAL_ID:
                quest_stages = [struct.unpack("<I", v)[0] for t, v in subs if t == b"INDX" and len(v) == 4]
                if b"VMAD" in d:
                    quest_props = probe_common.decode_vmad_v6_prop_names(d[b"VMAD"])

    if prefixed_fulls:
        raise ProbeP2Error(f"Found forbidden 'FO4SF ' prefix in FULL: {prefixed_fulls}")
    if not race_nam4_ok:
        raise ProbeP2Error("FO4SF_PowerArmorRace (0x0802) missing RACE.NAM4 = 0x0009150B")
    if not has_nofall_perk:
        raise ProbeP2Error("FO4SF_PANoFallDamagePerk (0x081E) missing from FO4SFPowerArmor.esm")
    if not fusion_core_model_ok:
        raise ProbeP2Error("FO4SF_FusionCore (0x0809) missing MODL = fo4sf\\powerarmor\\fusioncore.nif")
    if not exit_acti_model_ok:
        raise ProbeP2Error("FO4SF_P2_ExitActi (0x0803) missing visible non-marker MODL = fo4sf\\powerarmor\\pa_exit_terminal.nif")
    missing_refs = sorted({0x0810, 0x0811, 0x0812, 0x0813, 0x0814} - p2_persistent_refs)
    if missing_refs:
        raise ProbeP2Error(f"FO4SF_R11P2PowerArmor.esm missing persistent REFRs: {[hex(x) for x in missing_refs]}")
    for st in (10, 20, 30, 40, 50, 60, 70, 75, 80):
        if st not in quest_stages:
            raise ProbeP2Error(f"FO4SF_R11P2Quest (0x0820) missing INDX stage {st}")
    for req_prop in ("RoofFrameRef", "RoofMinigunRef", "RoofSpareCoreRef", "RoofExitRef", "StreetExitRef", "HealthAV"):
        if req_prop not in quest_props:
            raise ProbeP2Error(f"FO4SF_R11P2Quest (0x0820) VMAD missing property {req_prop}")
    if leaked_armo_subs:
        raise ProbeP2Error(f"PA/Salvaged ARMO retains template subrecords (INRD/OBTE/MOD2/MOD4): {leaked_armo_subs}")


def _resolve_starfield_paths(
    starfield_dir: Optional[Path],
    *,
    sf_data: Optional[Path] = None,
    starfield_esm: Optional[Path] = None,
    compiler_exe: Optional[Path] = None,
    cr_zip: Optional[Path] = None,
    texconv_exe: Optional[Path] = None,
) -> Tuple[Path, Path, Path, Path, Path]:
    resolved_sf_data = sf_data or (starfield_dir / "Data" if starfield_dir else None)
    resolved_esm = starfield_esm or (resolved_sf_data / "Starfield.esm" if resolved_sf_data else None)
    resolved_comp = compiler_exe or (starfield_dir / "Tools" / "Papyrus Compiler" / "PapyrusCompiler.exe" if starfield_dir else None)
    resolved_cr = cr_zip or (starfield_dir / "Tools" / "ContentResources.zip" if starfield_dir else None)
    resolved_texconv = texconv_exe or (starfield_dir / "Tools" / "AssetWatcher" / "Plugins" / "Starfield" / "xtexconv.exe" if starfield_dir else None)
    missing = [
        nm
        for nm, val in (
            ("sf_data / --starfield-dir", resolved_sf_data),
            ("starfield_esm / --starfield-dir", resolved_esm),
            ("compiler_exe / --starfield-dir", resolved_comp),
            ("cr_zip / --starfield-dir", resolved_cr),
            ("texconv_exe / --starfield-dir", resolved_texconv),
        )
        if val is None
    ]
    if missing:
        raise ProbeP2Error(f"Missing required Starfield input path(s): {', '.join(missing)}")
    assert resolved_sf_data and resolved_esm and resolved_comp and resolved_cr and resolved_texconv
    return resolved_sf_data, resolved_esm, resolved_comp, resolved_cr, resolved_texconv


def stage_probe(
    *,
    stage_dir: Path,
    fo4_data: Path,
    core_values_src: Path,
    weapons_assets_dir: Path,
    tested_pipboy_dll: Path,
    starfield_dir: Optional[Path] = None,
    sf_data: Optional[Path] = None,
    starfield_esm: Optional[Path] = None,
    compiler_exe: Optional[Path] = None,
    cr_zip: Optional[Path] = None,
    texconv_exe: Optional[Path] = None,
    pipboy_src_dir: Path = DEFAULT_PIPBOY_SRC_DIR,
    clean: bool = False,
    min_free_gb: float = probe_common.DEFAULT_MIN_FREE_GB,
    system: Optional[Any] = None,
) -> Dict[str, Any]:
    resolved_sf_data, resolved_esm, resolved_comp, resolved_cr, resolved_texconv = _resolve_starfield_paths(
        starfield_dir,
        sf_data=sf_data,
        starfield_esm=starfield_esm,
        compiler_exe=compiler_exe,
        cr_zip=cr_zip,
        texconv_exe=texconv_exe,
    )
    probe_common.check_starfield_not_running(system)
    probe_common.check_out_dir_safe(stage_dir, clean=clean)
    free_gb = probe_common.check_free_space_gb(stage_dir, min_gb=min_free_gb)
    stage_dir.mkdir(parents=True, exist_ok=True)

    core_dir = stage_dir / "core"
    assets_dir = stage_dir / "assets"
    exp_dir = stage_dir / "exp"
    scripts_dir = exp_dir / "Data" / "Scripts"
    sfse_plugins_dir = stage_dir / "sfse" / "SFSE" / "Plugins"
    bat_dir = stage_dir / "bat"
    for d in (core_dir, assets_dir, exp_dir, scripts_dir, sfse_plugins_dir, bat_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Core ESMs: FO4SFCoreValues.esm (validated copy) + FO4SFPowerArmor.esm (--no-test-cell)
    _verify_core_values_has_minigun_and_5mm(core_values_src)
    cv_dst = core_dir / "FO4SFCoreValues.esm"
    probe_common.copy_or_link_staged_file(core_values_src, cv_dst, allow_hardlink=False)

    with tempfile.TemporaryDirectory() as pa_tmp:
        pa_out = Path(pa_tmp) / "out"
        pacore.stage(
            argparse.Namespace(
                out=str(pa_out),
                starfield=str(resolved_esm),
                compiler=str(resolved_comp),
                content_resources=str(resolved_cr),
                control=pacore.DEFAULT_CONTROL,
                override_dfob=False,
                no_test_cell=True,
            )
        )
        pa_esm_src = pa_out / "FO4SFPowerArmor.esm"
        probe_common.copy_or_link_staged_file(pa_esm_src, core_dir / "FO4SFPowerArmor.esm", allow_hardlink=False)

    # 2. Papyrus compilation (both FO4SF_PowerArmorCoreQuest.pex and FO4SF_R11P2Quest.pex)
    pex_hashes = compile_p2_scripts(scripts_dir, compiler_exe=resolved_comp, cr_zip=resolved_cr)

    # 3. Assets (FO4 PA frame/T-45/minigun/core/exit terminal + Minigun/5mm transitive bundle)
    asset_report = convert_p2_assets(
        assets_dir,
        fo4_data=fo4_data,
        sf_data=resolved_sf_data,
        cr_zip=resolved_cr,
        texconv_exe=resolved_texconv,
        weapons_assets_dir=weapons_assets_dir,
    )

    # 4. Probe plugin ESM
    probe_esm_path = exp_dir / PROBE_PLUGIN
    probe_esm_path.write_bytes(build_p2_powerarmor_esm())

    # 5. BA2 archives (Main: .pex + .nif + .mesh + .mat ; Textures: .dds)
    main_inputs: Dict[str, bytes] = {}
    tex_inputs: Dict[str, bytes] = {}
    for pex_name in ("FO4SF_PowerArmorCoreQuest.pex", "FO4SF_R11P2Quest.pex"):
        main_inputs[f"scripts/{pex_name}"] = (scripts_dir / pex_name).read_bytes()

    for fp in sorted(assets_dir.rglob("*")):
        if not fp.is_file():
            continue
        rel = fp.relative_to(assets_dir).as_posix().lower()
        if rel.endswith(".dds"):
            tex_inputs[rel] = fp.read_bytes()
        elif rel.endswith((".nif", ".mesh", ".mat", "_controllers.json")):
            main_inputs[rel] = fp.read_bytes()

    main_ba2 = exp_dir / PROBE_MAIN_BA2
    tex_ba2 = exp_dir / PROBE_TEX_BA2
    probe_common.pack_gnrl_ba2(main_inputs, main_ba2, compress=False)
    probe_common.pack_dx10_ba2(tex_inputs, tex_ba2, compress=False)
    main_ba2_hashes = probe_common.verify_ba2_entry_hashes(main_ba2)
    tex_ba2_hashes = probe_common.verify_ba2_entry_hashes(tex_ba2)

    # 6. Reuse tested FO4SFPipboyMenu.dll (7d5ba49c) without rebuilding
    resolved_pipboy_srcs: List[Path] = []
    for key in probe_common.TESTED_PIPBOY_SOURCE_HASHES:
        direct = pipboy_src_dir / key
        nested = pipboy_src_dir / "src" / key
        common = pipboy_src_dir.parent / "common" / key
        if direct.is_file():
            resolved_pipboy_srcs.append(direct)
        elif nested.is_file():
            resolved_pipboy_srcs.append(nested)
        elif common.is_file():
            resolved_pipboy_srcs.append(common)
        else:
            raise ProbeP2Error(f"Missing SFSE source file for binary reuse check: {key}")

    def _reuse_7d5ba49c_without_rebuild() -> Path:
        if not tested_pipboy_dll.is_file():
            raise ProbeP2Error(f"Missing tested FO4SFPipboyMenu.dll: {tested_pipboy_dll}")
        actual_dll_sha = probe_common.sha256_file(tested_pipboy_dll)
        if actual_dll_sha != probe_common.TESTED_PIPBOY_DLL_SHA256:
            raise ProbeP2Error(
                f"Tested binary mismatch at {tested_pipboy_dll}: {actual_dll_sha} != {probe_common.TESTED_PIPBOY_DLL_SHA256}"
            )
        return tested_pipboy_dll

    bin_res = probe_common.reuse_tested_binary(
        resolved_pipboy_srcs,
        probe_common.TESTED_PIPBOY_SOURCE_HASHES,
        tested_pipboy_dll,
        _reuse_7d5ba49c_without_rebuild,
        dst_path=sfse_plugins_dir / "FO4SFPipboyMenu.dll",
    )
    if bin_res.bin_sha256 != probe_common.TESTED_PIPBOY_DLL_SHA256:
        raise ProbeP2Error("FO4SFPipboyMenu.dll SHA-256 verification failed")
    ini_src = pipboy_src_dir / "FO4SFPipboyMenu.ini"
    probe_common.copy_or_link_staged_file(ini_src, sfse_plugins_dir / "FO4SFPipboyMenu.ini", allow_hardlink=False)

    # 7. P3-clean unstamped batch templates & hop validation (live slot stamped at install time)
    batches = render_p2_batches(UNSTAMPED_SLOT_TOKEN)
    written_bats: List[Path] = []
    for name, body in batches.items():
        bp = bat_dir / name
        bp.write_text(body, encoding="utf-8", newline="\n")
        written_bats.append(bp)
    probe_common.validate_batches_and_hops(
        batch_files=written_bats,
        anchors=P2_ANCHORS,
        hops=P2_HOPS,
        max_axis_m=200.0,
        interior_mode=False,
        raise_on_error=True,
    )

    # 8. ESM cleanliness scan (ZERO WRLD/PNDT/ext-CELL overrides, 0 non-persistent cross-plugin VMAD)
    probe_common.scan_plugin_cleanliness(
        [core_dir / "FO4SFPowerArmor.esm", probe_esm_path],
        reference_esms=[cv_dst, core_dir / "FO4SFPowerArmor.esm"],
        raise_on_error=True,
    )
    _verify_p2_esms(core_dir / "FO4SFPowerArmor.esm", probe_esm_path)

    manifest = {
        "schema": "fo4sf.r11_p2_powerarmor.v2",
        "probe_id": PROBE_ID,
        "staged_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "free_disk_gb": free_gb,
        "standin_disclosure": STANDIN_DISCLOSURE,
        "files": {
            "core/FO4SFCoreValues.esm": {"size": cv_dst.stat().st_size, "sha256": probe_common.sha256_file(cv_dst)},
            "core/FO4SFPowerArmor.esm": {
                "size": (core_dir / "FO4SFPowerArmor.esm").stat().st_size,
                "sha256": probe_common.sha256_file(core_dir / "FO4SFPowerArmor.esm"),
            },
            f"exp/{PROBE_PLUGIN}": {"size": probe_esm_path.stat().st_size, "sha256": probe_common.sha256_file(probe_esm_path)},
            f"exp/{PROBE_MAIN_BA2}": {"size": main_ba2.stat().st_size, "sha256": probe_common.sha256_file(main_ba2), "entries": len(main_ba2_hashes)},
            f"exp/{PROBE_TEX_BA2}": {"size": tex_ba2.stat().st_size, "sha256": probe_common.sha256_file(tex_ba2), "entries": len(tex_ba2_hashes)},
            "sfse/SFSE/Plugins/FO4SFPipboyMenu.dll": {"size": bin_res.path.stat().st_size, "sha256": bin_res.bin_sha256, "reused": bin_res.reused},
        },
        "pex_hashes": pex_hashes,
        "nif_hashes": {rel: probe_common.sha256_file(assets_dir / rel) for rel in ALL_EXPECTED_NIFS},
        "assets_summary": asset_report,
        "hops_validated": [h.name for h in P2_HOPS],
    }
    manifest_p = stage_dir / "manifest.json"
    manifest_p.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_staged(stage_dir: Path) -> Dict[str, Any]:
    """Verify staged Probe P2 folder completeness, hashes, BA2s, cleanliness, P3 batches, and copy-only links."""
    if not stage_dir.is_dir():
        raise ProbeP2Error(f"Missing P2 stage dir: {stage_dir}")

    req_paths = [
        stage_dir / "core" / "FO4SFCoreValues.esm",
        stage_dir / "core" / "FO4SFPowerArmor.esm",
        stage_dir / "exp" / PROBE_PLUGIN,
        stage_dir / "exp" / PROBE_MAIN_BA2,
        stage_dir / "exp" / PROBE_TEX_BA2,
        stage_dir / "exp" / "Data" / "Scripts" / "FO4SF_PowerArmorCoreQuest.pex",
        stage_dir / "exp" / "Data" / "Scripts" / "FO4SF_R11P2Quest.pex",
        stage_dir / "sfse" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll",
        stage_dir / "sfse" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini",
        stage_dir / "manifest.json",
    ]
    for p in req_paths:
        if not p.is_file() or p.stat().st_size == 0:
            raise ProbeP2Error(f"Missing or empty required file: {p}")

    # 1. st_nlink == 1 across copy-only extensions
    nlink_failures: List[str] = []
    for fp in stage_dir.rglob("*"):
        if fp.is_file() and fp.suffix.lower() in probe_common.COPY_ONLY_EXTENSIONS:
            st = fp.stat()
            if st.st_nlink != 1:
                nlink_failures.append(f"{fp}: st_nlink={st.st_nlink}")
    if nlink_failures:
        raise ProbeP2Error(f"Hardlink check failed: {'; '.join(nlink_failures)}")

    # 2. Tested Pipboy binary hash
    dll_sha = probe_common.sha256_file(stage_dir / "sfse" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll")
    if dll_sha != probe_common.TESTED_PIPBOY_DLL_SHA256:
        raise ProbeP2Error(f"FO4SFPipboyMenu.dll hash {dll_sha} != {probe_common.TESTED_PIPBOY_DLL_SHA256}")

    # 3. CoreValues & PowerArmorCore checks (0 "FO4SF " FULLs, NAM4=0x09150B, 0x081E, FusionCore.nif, exit ACTI, clean ARMOs, F5 5mm+Minigun)
    _verify_core_values_has_minigun_and_5mm(stage_dir / "core" / "FO4SFCoreValues.esm")
    pa_esm = stage_dir / "core" / "FO4SFPowerArmor.esm"
    p2_esm = stage_dir / "exp" / PROBE_PLUGIN
    _verify_p2_esms(pa_esm, p2_esm)

    # 4. BA2 hashes and asset completeness
    main_entries = probe_common.verify_ba2_entry_hashes(stage_dir / "exp" / PROBE_MAIN_BA2)
    tex_entries = probe_common.verify_ba2_entry_hashes(stage_dir / "exp" / PROBE_TEX_BA2)
    assets_dir = stage_dir / "assets"
    for nif_rel in ALL_EXPECTED_NIFS:
        if nif_rel not in main_entries:
            raise ProbeP2Error(f"{PROBE_MAIN_BA2} missing {nif_rel}")
        for dep in _collect_nif_transitive_deps(assets_dir, nif_rel):
            bucket = tex_entries if dep.endswith(".dds") else main_entries
            if dep not in bucket:
                raise ProbeP2Error(f"BA2 archive missing transitive dep {dep} for {nif_rel}")
    if MINIGUN_CONTROLLER_SIDECAR not in main_entries or not (assets_dir / MINIGUN_CONTROLLER_SIDECAR).is_file():
        raise ProbeP2Error(f"Missing post-F6 controller sidecar {MINIGUN_CONTROLLER_SIDECAR}")
    _verify_minigun_moving_parts_nif(assets_dir / "meshes/fo4sf/weapons/minigun/fo4_minigun.nif")

    # 5. Batches & Hops + Plugin Cleanliness
    bat_files = sorted((stage_dir / "bat").glob("*.txt"))
    bat_names = {bp.name for bp in bat_files}
    missing_bats = [name for name in STAMPED_SETSTAGE_BATCHES if name not in bat_names]
    if missing_bats:
        raise ProbeP2Error(f"Missing required P2 batch file(s) in {stage_dir / 'bat'}: {missing_bats}")
    probe_common.validate_batches_and_hops(
        batch_files=bat_files,
        anchors=P2_ANCHORS,
        hops=P2_HOPS,
        max_axis_m=200.0,
        interior_mode=False,
        raise_on_error=True,
    )
    probe_common.scan_plugin_cleanliness(
        [pa_esm, p2_esm],
        reference_esms=[stage_dir / "core" / "FO4SFCoreValues.esm", pa_esm],
        raise_on_error=True,
    )

    return {
        "verified": True,
        "stage_dir": str(stage_dir),
        "main_ba2_entries": len(main_entries),
        "tex_ba2_entries": len(tex_entries),
        "batch_count": len(bat_files),
        "dll_sha256": dll_sha,
    }


def _install_plan(
    stage_dir: Path,
    *,
    batch_files: Optional[Sequence[Path]] = None,
    include_sfse: bool = False,
) -> List[Dict[str, Any]]:
    plan: List[Dict[str, Any]] = [
        {"src_rel": "core/FO4SFCoreValues.esm", "target_rel": "Data/FO4SFCoreValues.esm", "allow_swap": True},
        {"src_rel": "core/FO4SFPowerArmor.esm", "target_rel": "Data/FO4SFPowerArmor.esm", "allow_swap": True},
        {"src_rel": f"exp/{PROBE_PLUGIN}", "target_rel": f"Data/{PROBE_PLUGIN}", "allow_swap": True},
        {"src_rel": f"exp/{PROBE_MAIN_BA2}", "target_rel": f"Data/{PROBE_MAIN_BA2}", "allow_swap": True},
        {"src_rel": f"exp/{PROBE_TEX_BA2}", "target_rel": f"Data/{PROBE_TEX_BA2}", "allow_swap": True},
        {"src_rel": "exp/Data/Scripts/FO4SF_PowerArmorCoreQuest.pex", "target_rel": "Data/Scripts/FO4SF_PowerArmorCoreQuest.pex", "allow_swap": True},
        {"src_rel": "exp/Data/Scripts/FO4SF_R11P2Quest.pex", "target_rel": "Data/Scripts/FO4SF_R11P2Quest.pex", "allow_swap": True},
    ]
    bats = list(batch_files) if batch_files is not None else sorted((stage_dir / "bat").glob("*.txt"))
    for bp in sorted(bats, key=lambda p: p.name):
        src_val = str(bp) if batch_files is not None else f"bat/{bp.name}"
        plan.append({"src_rel": src_val, "target_rel": bp.name, "allow_swap": True})
    if include_sfse:
        plan.append({"src_rel": "sfse/SFSE/Plugins/FO4SFPipboyMenu.dll", "target_rel": "Data/SFSE/Plugins/FO4SFPipboyMenu.dll", "allow_swap": True})
        plan.append({"src_rel": "sfse/SFSE/Plugins/FO4SFPipboyMenu.ini", "target_rel": "Data/SFSE/Plugins/FO4SFPipboyMenu.ini", "allow_swap": True})
    return plan


def install_probe_p2(
    *,
    stage_dir: Path,
    starfield_dir: Path,
    plugins_txt: Optional[Path] = None,
    include_sfse: bool = False,
    version_tag: str = "p2-v2",
    card_path: Optional[Path] = None,
    min_free_gb: float = probe_common.DEFAULT_MIN_FREE_GB,
    allow_hardlink: bool = False,
    system: Optional[Any] = None,
) -> Dict[str, Any]:
    """Verify, stamp live full-master slot prefixes on batches, and atomically install Probe P2."""
    verify_staged(stage_dir)
    plg_txt = probe_common._resolve_plugins_txt(starfield_dir, plugins_txt)
    plugins_to_activate = ["FO4SFCoreValues.esm", "FO4SFPowerArmor.esm", PROBE_PLUGIN]

    with tempfile.TemporaryDirectory(prefix="p2_bat_") as td:
        bat_tmp = Path(td)
        stamped_map: Dict[str, str] = {
            bp.name: bp.read_text(encoding="utf-8")
            for bp in sorted((stage_dir / "bat").glob("*.txt"))
        }
        live_prefix = probe_common.stamp_batch_formid_prefix(
            stamped_map,
            starfield_dir / "Data",
            plg_txt,
            PROBE_PLUGIN,
            local_ids=(QUST_P2_LOCAL_ID,),
            out_dir=bat_tmp,
            plugins_to_activate=plugins_to_activate,
        )
        prefix_byte = live_prefix[2:].upper()
        quest_form_id = f"{prefix_byte}{QUST_P2_LOCAL_ID:06X}"
        stamped_files = sorted(bat_tmp.glob("*.txt"))
        for bp in stamped_files:
            txt = bp.read_text(encoding="utf-8")
            if f"{UNSTAMPED_SLOT_TOKEN}{QUST_P2_LOCAL_ID:06X}" in txt:
                raise ProbeP2Error(f"Unstamped placeholder remained in {bp.name}")

        receipt = probe_common.install_probe(
            probe_id=PROBE_ID,
            stage_dir=stage_dir,
            starfield_dir=starfield_dir,
            plugins_txt=plg_txt,
            plugins_to_activate=plugins_to_activate,
            files=_install_plan(stage_dir, batch_files=stamped_files, include_sfse=include_sfse),
            baseline_2g_fix2_hashes=probe_common.CANDIDATE_2G_FIX4_HASHES,
            baseline_label="candidate-2g-fix4",
            version_tag=version_tag,
            card_path=card_path,
            live_prefix=live_prefix,
            receipt_extra={
                "live_slot_index": int(prefix_byte, 16),
                "quest_form_id": quest_form_id,
            },
            min_free_gb=min_free_gb,
            allow_hardlink=allow_hardlink,
            system=system,
        )

    return {
        "installed": True,
        "plugins_txt": receipt["plugins_txt"],
        "live_prefix": live_prefix,
        "quest_form_id": quest_form_id,
        "version_tag": version_tag,
        "receipt_path": str(probe_common.receipt_path(starfield_dir, PROBE_ID)),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Stage, verify, install, and inspect status of Round 11 Probe P2.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp_stage = sub.add_parser("stage", help="Build and stage Probe P2 outside repository & candidate folders.")
    sp_stage.add_argument("--stage-dir", required=True, type=Path)
    sp_stage.add_argument("--fo4-data", required=True, type=Path)
    sp_stage.add_argument("--starfield-dir", required=True, type=Path)
    sp_stage.add_argument("--sf-data", default=None, type=Path)
    sp_stage.add_argument("--starfield-esm", default=None, type=Path)
    sp_stage.add_argument("--compiler", default=None, type=Path)
    sp_stage.add_argument("--content-resources", default=None, type=Path)
    sp_stage.add_argument("--texconv", default=None, type=Path)
    sp_stage.add_argument("--core-values", required=True, type=Path)
    sp_stage.add_argument("--weapons-assets", required=True, type=Path)
    sp_stage.add_argument("--tested-pipboy-dll", required=True, type=Path)
    sp_stage.add_argument("--pipboy-src-dir", default=DEFAULT_PIPBOY_SRC_DIR, type=Path)
    sp_stage.add_argument("--min-free-gb", default=probe_common.DEFAULT_MIN_FREE_GB, type=float)
    sp_stage.add_argument("--clean", action="store_true")

    sp_verify = sub.add_parser("verify", help="Verify staged Probe P2 folder.")
    sp_verify.add_argument("--stage-dir", required=True, type=Path)

    sp_inst = sub.add_parser("install", help="Atomically install Probe P2 into Starfield folder (game closed).")
    sp_inst.add_argument("--stage-dir", required=True, type=Path)
    sp_inst.add_argument("--starfield-dir", required=True, type=Path)
    sp_inst.add_argument("--plugins-txt", default=None, type=Path)
    sp_inst.add_argument("--include-sfse", action="store_true")
    sp_inst.add_argument("--version-tag", default="p2-v2")
    sp_inst.add_argument("--card-path", default=None, type=Path)
    sp_inst.add_argument("--min-free-gb", default=probe_common.DEFAULT_MIN_FREE_GB, type=float)

    sp_un = sub.add_parser("uninstall", help="Atomically uninstall Probe P2.")
    sp_un.add_argument("--starfield-dir", required=True, type=Path)
    sp_un.add_argument("--force", action="store_true")

    sp_st = sub.add_parser("status", help="Inspect Probe P2 installation status.")
    sp_st.add_argument("--starfield-dir", required=True, type=Path)

    args = ap.parse_args(argv)
    if args.cmd == "stage":
        res = stage_probe(
            stage_dir=args.stage_dir,
            fo4_data=args.fo4_data,
            starfield_dir=args.starfield_dir,
            sf_data=args.sf_data,
            starfield_esm=args.starfield_esm,
            compiler_exe=args.compiler,
            cr_zip=args.content_resources,
            texconv_exe=args.texconv,
            core_values_src=args.core_values,
            weapons_assets_dir=args.weapons_assets,
            tested_pipboy_dll=args.tested_pipboy_dll,
            pipboy_src_dir=args.pipboy_src_dir,
            min_free_gb=float(args.min_free_gb),
            clean=bool(args.clean),
        )
        print(json.dumps(res, indent=2))
        return 0

    if args.cmd == "verify":
        res = verify_staged(args.stage_dir)
        print(json.dumps(res, indent=2))
        return 0

    if args.cmd == "install":
        out = install_probe_p2(
            stage_dir=args.stage_dir,
            starfield_dir=args.starfield_dir,
            plugins_txt=args.plugins_txt,
            include_sfse=bool(args.include_sfse),
            version_tag=args.version_tag,
            card_path=args.card_path,
            min_free_gb=float(args.min_free_gb),
        )
        print(json.dumps(out, indent=2))
        return 0

    if args.cmd == "uninstall":
        res = probe_common.uninstall_probe(probe_id=PROBE_ID, starfield_dir=args.starfield_dir, force=bool(args.force))
        print(json.dumps(res, indent=2))
        return 0

    if args.cmd == "status":
        res = probe_common.probe_status(
            probe_id=PROBE_ID,
            starfield_dir=args.starfield_dir,
            baseline_2g_fix2_hashes=probe_common.CANDIDATE_2G_FIX4_HASHES,
        )
        print(json.dumps(res, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
