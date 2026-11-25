"""Validate and stage Mr. Handy Codsworth race/rig assets from a #854 (`robot-anim`) bundle."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from fo4sf.planet import esm

HANDY_TEMPLATE_PLUGIN = "FO4SF_RA2Handy.esm"
HANDY_RACE_EDID = "FO4SF_HandyRace"
HANDY_BPTD_EDID = "FO4SF_HandyBodyPartData"
HANDY_MESH_REL = "fo4sf/actors/handy/handy.nif"
DEFAULT_CODSWORTH_RACE_EDID = "FO4SF_PrewarCodsworthRace"

HANDY_ASSET_DIRS: Tuple[str, ...] = (
    "geometries/",
    "materials/fo4sf/",
    "meshes/actors/fo4sf/handy/",
    "meshes/fo4sf/actors/handy/",
    "textures/fo4sf/",
)
HANDY_MANIFEST_DIRS: Tuple[str, ...] = (
    "AnimationFileData",
    "AnimationOffsets",
    "AnimationStanceData",
    "DynamicIdleData",
)


def _crc_table() -> List[int]:
    table: List[int] = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ 0xEDB88320 if (c & 1) else (c >> 1)
        table.append(c)
    return table


_CRC_TABLE = _crc_table()


def bs_crc32(data: bytes, crc: int = 0) -> int:
    """Bethesda string CRC-32 (reflected polynomial 0xEDB88320, init 0, no final xor)."""
    for b in data:
        crc = _CRC_TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc


def manifest_key(graph_path: str, folders: Sequence[str]) -> int:
    """Return u64 `AnimTextData` manifest filename key `(folders_hash << 32) | graph_hash`."""
    g_bytes = graph_path.replace("/", "\\").lower().encode("cp1252")
    g_hash = bs_crc32(g_bytes)
    if not folders:
        f_hash = 0
    else:
        f_bytes = "|".join(folders).replace("/", "\\").lower().encode("cp1252")
        f_hash = bs_crc32(f_bytes)
    return (f_hash << 32) | g_hash


def race_subgraph_sets(race: esm.Record) -> List[Tuple[str, List[str]]]:
    """Extract `(graph_path, folders)` tuples from a Starfield `RACE` record (`NAM6`, `SGNM`, `SAPT`)."""
    out: List[Tuple[str, List[str]]] = []
    root = race.get(b"NAM6")
    if root is not None:
        out.append((esm.zstring(root), []))
    cur: Tuple[str, List[str]] | None = None
    for sig, data in race.subs:
        if sig == b"SGNM":
            cur = (esm.zstring(data), [])
            out.append(cur)
        elif sig == b"SAPT" and cur is not None:
            cur[1].append(esm.zstring(data))
    return out


@dataclass(frozen=True)
class HandyBundleSpec:
    """Validated `#854` Mr. Handy bundle layout and mapped destination files."""

    bundle_dir: str
    template_esm: str
    race_edid: str
    bptd_edid: str
    subgraph_count: int
    files_to_copy: Dict[str, str]


def inspect_handy_bundle(
    bundle_dir: str,
    target_race_edid: str = DEFAULT_CODSWORTH_RACE_EDID,
) -> HandyBundleSpec:
    """Validate `--codsworth-handy <dir>` (`FO4SF_RA2Handy.esm` + `Data/`) and map its files."""
    src = os.path.abspath(bundle_dir)
    template = os.path.join(src, HANDY_TEMPLATE_PLUGIN)
    data_root = os.path.join(src, "Data")
    if not os.path.isfile(template) or not os.path.isdir(data_root):
        raise FileNotFoundError(
            f"--codsworth-handy {bundle_dir} requires {HANDY_TEMPLATE_PLUGIN} and Data\\"
        )

    with esm.Plugin(template) as plugin:
        races = plugin.records("RACE", [b"RACE"])
        race = next((r for r in races if r.edid == HANDY_RACE_EDID), None)
        if race is None:
            raise ValueError(f"{template} missing RACE {HANDY_RACE_EDID}")
        bptds = plugin.records("BPTD", [b"BPTD"])
        bptd = next((b for b in bptds if b.edid == HANDY_BPTD_EDID), None)
        if bptd is None:
            raise ValueError(f"{template} missing BPTD {HANDY_BPTD_EDID}")

    subgraphs = race_subgraph_sets(race)
    try:
        from fo4sf import handy_race as hr  # type: ignore
        keys = {f"{hr.manifest_key(g, f)}.txt" for g, f in hr.race_subgraph_sets(race)}
    except ImportError:
        keys = {f"{manifest_key(g, f)}.txt" for g, f in subgraphs}

    want_gsd = f"meshes/animtextdata/generatedsubgraphdata/{HANDY_RACE_EDID.lower()}.txt"
    mapped: Dict[str, str] = {}
    manifest_dir_lows = {d.lower() for d in HANDY_MANIFEST_DIRS}

    for dirpath, _dirs, files in os.walk(data_root):
        for fname in sorted(files):
            rel = os.path.relpath(os.path.join(dirpath, fname), data_root).replace(os.sep, "/")
            low = rel.lower()
            parts = low.split("/")
            if low == want_gsd:
                mapped[rel] = (
                    "meshes/AnimTextData/GeneratedSubgraphData/"
                    + target_race_edid.lower()
                    + ".txt"
                )
            elif low.startswith(HANDY_ASSET_DIRS):
                mapped[rel] = rel
            elif (
                len(parts) == 4
                and parts[:2] == ["meshes", "animtextdata"]
                and parts[2] in manifest_dir_lows
                and fname in keys
            ):
                mapped[rel] = rel

    want_mesh = "meshes/" + HANDY_MESH_REL.lower()
    if not any(dst.lower() == want_mesh for dst in mapped.values()):
        raise ValueError(f"--codsworth-handy bundle missing Data/{want_mesh}")
    if want_gsd not in {k.lower() for k in mapped}:
        raise ValueError(f"--codsworth-handy bundle missing {want_gsd}")

    return HandyBundleSpec(
        bundle_dir=src,
        template_esm=template,
        race_edid=HANDY_RACE_EDID,
        bptd_edid=HANDY_BPTD_EDID,
        subgraph_count=len(subgraphs),
        files_to_copy=mapped,
    )


def copy_handy_assets(
    bundle_dir: str,
    dest_data_dir: str,
    target_race_edid: str = DEFAULT_CODSWORTH_RACE_EDID,
) -> Tuple[HandyBundleSpec, List[str]]:
    """Copy verified Handy rig/animation/mesh files into `dest_data_dir` without overwriting."""
    spec = inspect_handy_bundle(bundle_dir, target_race_edid=target_race_edid)
    copied: List[str] = []
    for src_rel, dst_rel in sorted(spec.files_to_copy.items()):
        dst = os.path.join(dest_data_dir, *dst_rel.split("/"))
        if os.path.exists(dst):
            raise FileExistsError(f"--codsworth-handy refuses to overwrite existing {dst}")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(spec.bundle_dir, "Data", *src_rel.split("/")), dst)
        copied.append(dst_rel)
    return spec, copied
