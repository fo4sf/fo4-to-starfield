"""Build, compile, verify, and offline-stage the two-landing travel probe + Option B loading screens."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for _p in (str(SRC_DIR), str(SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fo4sf.core.cross_plugin_check import parse_binary_vmad_properties  # noqa: E402
from fo4sf.planet.esm import (  # noqa: E402
    ESM,
    GROUP_ORDER,
    HEDR_VERSION,
    LOCALIZED,
    PERSISTENT,
    Plugin,
    Record,
    group_bytes,
    zbytes,
)
from fo4sf.world.load_screens import verify_load_screens_plugin, write_load_screens_plugin  # noqa: E402

PROBE_PLUGIN = "FO4SFTravelProbe.esm"
LOAD_SCREENS_PLUGIN = "FO4SFLoadScreens.esm"
PROBE_SCRIPT_NAME = "FO4SF_TravelProbeQuest"
PROBE_PSC_PATH = Path(__file__).resolve().parent / f"{PROBE_SCRIPT_NAME}.psc"

# Starfield.esm static & clutter FormIDs (mirrors dotnet/TestCell conventions).
SF_XMARKER_HEADING = 0x00000034
SF_TRANSIT_PLATFORM = 0x00050776
SF_OMNI_LIGHT = 0x0003D38C
SF_LIGHTING_TEMPLATE = 0x00006658
SF_IMAGE_SPACE = 0x00122393
TOKEN_PREF_EDIDS = ("Misc_Junk_Fork", "Junk_Fork", "Misc_Fork", "Misc_Cup", "Misc_Mug")

PROBE_GLOBALS: Tuple[Tuple[int, str, float], ...] = (
    (0x000800, "FO4SF_TravelState", 0.0),
    (0x000801, "FO4SF_TravelSourceCode", 0.0),
    (0x000802, "FO4SF_TravelDestCode", 0.0),
    (0x000803, "FO4SF_TravelMode", 0.0),
    (0x000804, "FO4SF_TravelSeq", 0.0),
    (0x000805, "FO4SF_TravelHopIndex", 0.0),
    (0x000806, "FO4SF_TravelFollowerOK", 0.0),
    (0x000807, "FO4SF_TravelItemsOK", 0.0),
    (0x000808, "FO4SF_TravelLoadedOK", 0.0),
    (0x000809, "FO4SF_TravelDestX", 0.0),
    (0x00080A, "FO4SF_TravelDestY", 0.0),
    (0x00080B, "FO4SF_TravelDestZ", 0.0),
)

PROBE_QUEST_LOCAL_ID = 0x000820
PROBE_TRANSIT_CELL_ID = 0x000830
PROBE_TRANSIT_MARKER_ID = 0x000831
PROBE_TRANSIT_FLOOR_ID = 0x000832
PROBE_TRANSIT_LIGHT_ID = 0x000833
PROBE_TOKEN_LOCAL_ID = 0x000810
PROBE_STAGES = (0, 10, 20, 30, 40, 50, 90)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _pack_quest_vmad(script_name: str) -> bytes:
    sb = script_name.encode("cp1252")
    # version=6, object_format=2, script_count=1, slen, sname, status=0, prop_count=0
    return struct.pack("<HHH", 6, 2, 1) + struct.pack("<H", len(sb)) + sb + struct.pack("<BH", 0, 0)


def _clone_misc_token(starfield_esm: Optional[Path | str], self_index: int) -> Optional[Record]:
    if not starfield_esm or not Path(starfield_esm).is_file():
        return None
    picked: Optional[Record] = None
    with Plugin(str(starfield_esm)) as sf:
        all_misc = list(sf.records("MISC"))
        by_edid = {r.edid.lower(): r for r in all_misc if r.edid}
        for pref in TOKEN_PREF_EDIDS:
            if pref.lower() in by_edid:
                picked = by_edid[pref.lower()]
                break
        if picked is None:
            for r in sorted(all_misc, key=lambda rec: rec.formid):
                if r.edid and r.get(b"MODL") is not None:
                    picked = r
                    break
    if picked is None:
        return None
    new_subs: List[Tuple[bytes, bytes]] = []
    for sig, data in picked.subs:
        if sig == b"EDID":
            new_subs.append((b"EDID", zbytes("FO4SF_TravelToken")))
        elif sig == b"FULL":
            new_subs.append((b"FULL", zbytes("FO4SF Travel Token")))
        elif sig == b"VMAD":
            continue
        else:
            new_subs.append((sig, data))
    if not any(s == b"EDID" for s, _ in new_subs):
        new_subs.insert(0, (b"EDID", zbytes("FO4SF_TravelToken")))
    return Record(
        b"MISC",
        (self_index << 24) | PROBE_TOKEN_LOCAL_ID,
        new_subs,
        flags=picked.flags & ~LOCALIZED,
        vc=0,
        version=581,
        unknown=0,
    )


def build_travel_probe_bytes(starfield_esm: Optional[Path | str] = None) -> bytes:
    """Build `FO4SFTravelProbe.esm` (`Starfield.esm` master only, zero edits to core ESMs)."""
    self_index = 1
    own = lambda local_id: (self_index << 24) | (local_id & 0xFFFFFF)  # noqa: E731

    glob_recs = [
        Record(b"GLOB", own(lid), [(b"EDID", zbytes(edid)), (b"FLTV", struct.pack("<f", float(val)))], version=581)
        for lid, edid, val in PROBE_GLOBALS
    ]
    misc_rec = _clone_misc_token(starfield_esm, self_index)

    q_subs: List[Tuple[bytes, bytes]] = [
        (b"EDID", zbytes(PROBE_SCRIPT_NAME)),
        (b"VMAD", _pack_quest_vmad(PROBE_SCRIPT_NAME)),
        (b"FULL", zbytes("FO4SF Travel Probe")),
        (b"DNAM", struct.pack("<HBBII", 0x0100, 0, 0, 35, 0)),
    ]
    for st in PROBE_STAGES:
        q_subs.append((b"INDX", struct.pack("<HBB", st, 0, 0)))
        q_subs.append((b"QSDT", b"\x00"))
    quest_rec = Record(b"QUST", own(PROBE_QUEST_LOCAL_ID), q_subs, version=581)

    cid = own(PROBE_TRANSIT_CELL_ID)
    cell_rec = Record(
        b"CELL",
        cid,
        [
            (b"EDID", zbytes("FO4SF_TravelTransitCell")),
            (b"FULL", zbytes("FO4SF Travel Transit Room")),
            (b"DATA", struct.pack("<I", 0x00000001)),  # IsInteriorCell
            (b"LTMP", struct.pack("<I", SF_LIGHTING_TEMPLATE)),
            (b"XCLW", struct.pack("<I", 0x7F7FFFFF)),
            (b"XCIM", struct.pack("<I", SF_IMAGE_SPACE)),
        ],
        version=581,
    )
    marker_ref = Record(
        b"REFR",
        own(PROBE_TRANSIT_MARKER_ID),
        [
            (b"EDID", zbytes("FO4SF_TravelTransitMarker")),
            (b"NAME", struct.pack("<I", SF_XMARKER_HEADING)),
            (b"DATA", struct.pack("<6f", 0.0, 0.0, 0.5, 0.0, 0.0, 0.0)),
        ],
        flags=PERSISTENT,
        version=581,
    )
    floor_ref = Record(
        b"REFR",
        own(PROBE_TRANSIT_FLOOR_ID),
        [
            (b"EDID", zbytes("FO4SF_TravelTransitFloor")),
            (b"NAME", struct.pack("<I", SF_TRANSIT_PLATFORM)),
            (b"DATA", struct.pack("<6f", -4.0, -4.0, 0.0, 0.0, 0.0, 0.0)),
        ],
        version=581,
    )
    light_ref = Record(
        b"REFR",
        own(PROBE_TRANSIT_LIGHT_ID),
        [
            (b"EDID", zbytes("FO4SF_TravelTransitLight")),
            (b"NAME", struct.pack("<I", SF_OMNI_LIGHT)),
            (b"DATA", struct.pack("<6f", 0.0, 0.0, 4.0, 0.0, 0.0, 0.0)),
        ],
        version=581,
    )

    # Nested CELL group hierarchy: CELL(0) -> Block(2) -> SubBlock(3) -> CellChildren(6) -> Persistent(8) / Temp(9).
    pers_grup = group_bytes(struct.pack("<I", cid), marker_ref.to_bytes(compress=False), gtype=8)
    temp_grup = group_bytes(
        struct.pack("<I", cid),
        floor_ref.to_bytes(compress=False) + light_ref.to_bytes(compress=False),
        gtype=9,
    )
    cell_children = group_bytes(struct.pack("<I", cid), pers_grup + temp_grup, gtype=6)
    sub_block = group_bytes(struct.pack("<I", (cid // 10) % 10), cell_rec.to_bytes(compress=False) + cell_children, gtype=3)
    top_block = group_bytes(struct.pack("<I", cid % 10), sub_block, gtype=2)

    groups: List[bytes] = [
        group_bytes("GLOB", b"".join(r.to_bytes(compress=False) for r in glob_recs)),
    ]
    if misc_rec is not None:
        groups.append(group_bytes("MISC", misc_rec.to_bytes(compress=False)))
    groups.append(group_bytes("CELL", top_block))
    groups.append(group_bytes("QUST", quest_rec.to_bytes(compress=False)))

    all_records = list(glob_recs) + ([misc_rec] if misc_rec else []) + [cell_rec, marker_ref, floor_ref, light_ref, quest_rec]
    total_count = len(all_records) + len(groups) + 4  # +4 nested CELL subgroups
    max_local = max((r.formid & 0xFFFFFF) for r in all_records)
    head = Record(
        b"TES4",
        0,
        [
            (b"HEDR", struct.pack("<fII", HEDR_VERSION, total_count, max_local + 1)),
            (b"CNAM", zbytes("FO4SF")),
            (b"SNAM", zbytes("FO4SF Round 14 Two-Landing Travel Probe")),
            (b"MAST", zbytes("Starfield.esm")),
        ],
        flags=ESM,
        version=576,
    )
    return head.to_bytes(compress=False) + b"".join(groups)


def compile_probe_script(compiler_exe: Path, content_resources: Path, out_scripts_dir: Path) -> Path:
    """Compile `FO4SF_TravelProbeQuest.psc` against Starfield ContentResources into `out_scripts_dir`."""
    out_scripts_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fo4sf-travel-psc-") as td:
        tmp = Path(td)
        imp_dir = tmp / "imp"
        imp_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROBE_PSC_PATH, imp_dir / PROBE_PSC_PATH.name)
        flags_path = imp_dir / "Starfield_Papyrus_Flags.flg"
        # Minimal extract of ContentResources.zip base sources using python zipfile cleanly.
        import zipfile

        with zipfile.ZipFile(content_resources) as z:
            for member in z.namelist():
                if member.startswith("Scripts/Source/") and (member.lower().endswith(".psc") or member.lower().endswith(".flg")):
                    rel_name = Path(member).name
                    (imp_dir / rel_name).write_bytes(z.read(member))
        cmd = [
            str(compiler_exe),
            PROBE_SCRIPT_NAME,
            f"-i={imp_dir}",
            f"-o={out_scripts_dir}",
            f"-f={flags_path.name}",
            "-q",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            raise RuntimeError(f"PapyrusCompiler failed ({res.returncode}):\n{res.stdout}\n{res.stderr}")
    pex = out_scripts_dir / f"{PROBE_SCRIPT_NAME}.pex"
    if not pex.is_file():
        raise RuntimeError(f"expected compiled script missing: {pex}")
    return pex


def verify_travel_probe_plugin(plugin_path: Path | str) -> Dict[str, Any]:
    """Validate structure, VMAD binding, GLOBs, transit CELL, and zero cross-master pollution."""
    with Plugin(str(plugin_path)) as p:
        if p.masters != ["Starfield.esm"]:
            raise AssertionError(f"expected masters ['Starfield.esm'], got {p.masters}")
        if p.localized:
            raise AssertionError("FO4SFTravelProbe.esm must not set LOCALIZED")
        globs = {g.edid for g in p.records("GLOB")}
        want_globs = {edid for _, edid, _ in PROBE_GLOBALS}
        if not want_globs.issubset(globs):
            raise AssertionError(f"missing GLOBs: {sorted(want_globs - globs)}")
        quests = list(p.records("QUST"))
        if len(quests) != 1 or quests[0].edid != PROBE_SCRIPT_NAME:
            raise AssertionError(f"expected single QUST {PROBE_SCRIPT_NAME}")
        vmad = quests[0].get(b"VMAD")
        if vmad is None:
            raise AssertionError("FO4SF_TravelProbeQuest QUST missing VMAD")
        parse_binary_vmad_properties(vmad, p.masters, PROBE_PLUGIN, quests[0].edid)

        cell_recs = []
        refr_edids = set()
        for start, end in p.groups.get("CELL", []):
            for item in p.walk(start, end):
                if item[0] == "REC":
                    rec = p.record_at(item[1])
                    if rec.sig == b"CELL":
                        cell_recs.append(rec)
                    elif rec.sig == b"REFR":
                        refr_edids.add(rec.edid)
        if not cell_recs or cell_recs[0].edid != "FO4SF_TravelTransitCell":
            raise AssertionError("missing FO4SF_TravelTransitCell interior cell")
        if "FO4SF_TravelTransitMarker" not in refr_edids:
            raise AssertionError("missing persistent FO4SF_TravelTransitMarker inside transit cell")
    return {"ok": True, "glob_count": len(globs), "quest": PROBE_SCRIPT_NAME, "transit_cell": "FO4SF_TravelTransitCell"}


def stage_travel_probe(
    starfield_esm: Path,
    out_dir: Path,
    *,
    compiler_exe: Optional[Path] = None,
    content_resources: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build and verify both `FO4SFTravelProbe.esm` + `.pex` and `FO4SFLoadScreens.esm` into `out_dir`."""
    partial = out_dir.parent / f".{out_dir.name}.partial-{os.getpid()}"
    if partial.exists():
        shutil.rmtree(partial)
    data_dir = partial / "Data"
    scripts_dir = data_dir / "Scripts"
    data_dir.mkdir(parents=True, exist_ok=True)

    probe_esm = data_dir / PROBE_PLUGIN
    probe_esm.write_bytes(build_travel_probe_bytes(starfield_esm=starfield_esm))
    probe_check = verify_travel_probe_plugin(probe_esm)

    compiled_pex: Optional[Path] = None
    if compiler_exe and content_resources:
        compiled_pex = compile_probe_script(compiler_exe, content_resources, scripts_dir)

    lscr_esm = data_dir / LOAD_SCREENS_PLUGIN
    lscr_build = write_load_screens_plugin(
        starfield_esm,
        lscr_esm,
        write_blank_icon_under_data=data_dir,
    )
    lscr_build["out_path"] = Path(lscr_build["out_path"]).relative_to(partial).as_posix()
    if "blank_dds_path" in lscr_build:
        lscr_build["blank_dds_path"] = Path(lscr_build["blank_dds_path"]).relative_to(partial).as_posix()
    lscr_check = verify_load_screens_plugin(lscr_esm, starfield_esm)

    files: List[Dict[str, Any]] = []
    for p in sorted(partial.rglob("*")):
        if p.is_file():
            files.append({
                "rel": p.relative_to(partial).as_posix(),
                "bytes": p.stat().st_size,
                "sha256": sha256_file(p),
            })

    manifest = {
        "probe": "r14-travel-probe",
        "plugins": [PROBE_PLUGIN, LOAD_SCREENS_PLUGIN],
        "probe_check": probe_check,
        "load_screens_build": lscr_build,
        "load_screens_check": lscr_check,
        "compiled_script": compiled_pex.relative_to(partial).as_posix() if compiled_pex else None,
        "files": files,
    }
    (partial / "probe_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    partial.rename(out_dir)
    return manifest


def check_staged_dir(out_dir: Path, starfield_esm: Path) -> Dict[str, Any]:
    """Offline verify staged `out_dir` (`probe_manifest.json`, SHA-256, both ESMs)."""
    manifest_path = out_dir / "probe_manifest.json"
    if not manifest_path.is_file():
        raise AssertionError(f"missing {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        fp = out_dir / entry["rel"]
        if not fp.is_file():
            raise AssertionError(f"missing staged file: {fp}")
        if sha256_file(fp) != entry["sha256"]:
            raise AssertionError(f"SHA-256 mismatch on {fp}")
    p_rep = verify_travel_probe_plugin(out_dir / "Data" / PROBE_PLUGIN)
    l_rep = verify_load_screens_plugin(out_dir / "Data" / LOAD_SCREENS_PLUGIN, starfield_esm)
    return {"ok": True, "files_verified": len(manifest["files"]), "probe": p_rep, "load_screens": l_rep}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build/stage/check Round 14 two-landing travel probe")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_stage = sub.add_parser("stage", help="Stage FO4SFTravelProbe.esm + .pex + FO4SFLoadScreens.esm")
    p_stage.add_argument("--starfield", required=True, type=Path, help="Path to Starfield.esm")
    p_stage.add_argument("--out", required=True, type=Path, help="Output stage directory")
    p_stage.add_argument("--compiler", type=Path, default=None, help="Optional PapyrusCompiler.exe path")
    p_stage.add_argument("--content-resources", type=Path, default=None, help="Optional ContentResources.zip path")

    p_chk = sub.add_parser("check", help="Offline check staged travel probe directory")
    p_chk.add_argument("--dir", required=True, type=Path, help="Staged probe directory")
    p_chk.add_argument("--starfield", required=True, type=Path, help="Path to Starfield.esm")

    args = parser.parse_args(argv)
    if args.cmd == "stage":
        rep = stage_travel_probe(
            args.starfield,
            args.out,
            compiler_exe=args.compiler,
            content_resources=args.content_resources,
        )
        print(json.dumps(rep, indent=2))
        return 0
    rep = check_staged_dir(args.dir, args.starfield)
    print(json.dumps(rep, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
