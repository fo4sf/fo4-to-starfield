"""Codsworth inventory (read-only, run on the PC): what FO4 draws and voices him with, and what the Starfield
mini bot he stands in for is built from. Prints a short text report for the relay and writes the full JSON.

    python scripts/actors/codsworth_inventory.py --fo4-data "<FO4 Data>" --sf-data "<Starfield Data>" --out <dir>

Archives: FO4 "Fallout4 - Meshes*.ba2", "Fallout4 - Materials.ba2", "Fallout4 - Voices.ba2"; Starfield
"Starfield - Meshes*.ba2", "Starfield - Voices*.ba2". Every NIF matched is parsed with fo4sf.nif and summarised:
block types, node names, skin bone lists (BSSkin::Instance bone pointers resolved to node names) and the paths it
references (materials, .mesh files). Nothing is extracted to disk unless --keep is given (scratch only; never commit).
Tools probed: Wwise, the two Creation Kits, xWMAEncode, ffmpeg, vgmstream.
"""
import argparse
import glob
import json
import os
import shutil
import struct
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from fo4sf import nif as nifmod  # noqa: E402
from fo4sf.ba2 import Ba2  # noqa: E402

FO4_MESH_KEYS = ("mrhandy", "codsworth")
SF_MESH_KEYS = ("minibot",)
VOICE_KEYS = ("codsworth",)
NAMED = ("NiNode", "BSFadeNode", "BSLeafAnimNode", "BSTriShape", "BSSubIndexTriShape", "BSDynamicTriShape",
         "BSGeometry", "BSMeshLODTriShape", "NiTriShape")
MAX_NIFS = 40


def block_name(n, i):
    if n.type_of(i) not in NAMED or len(n.blocks[i]) < 4:
        return None
    k, = struct.unpack_from("<i", n.blocks[i], 0)
    return n.strings[k].decode("latin-1") if 0 <= k < len(n.strings) else None


def skin_bones(n, i):
    """BSSkin::Instance: i32 root, i32 bone data, u32 N, N x i32 bone nodes (FO4 layout; Starfield checked here)."""
    b = n.blocks[i]
    try:
        _root, _data, count = struct.unpack_from("<iiI", b, 0)
        if count > 512 or 12 + 4 * count > len(b):
            return {"error": f"bone count {count} does not fit {len(b)} bytes"}
        ptrs = struct.unpack_from(f"<{count}i", b, 12)
        return {"bones": [block_name(n, p) if 0 <= p < len(n.blocks) else None for p in ptrs]}
    except struct.error as e:
        return {"error": str(e)}


def summarize_nif(data):
    n = nifmod.parse(data)
    types = Counter(n.type_of(i) for i in range(len(n.blocks)))
    nodes = [block_name(n, i) for i in range(len(n.blocks)) if n.type_of(i) in ("NiNode", "BSFadeNode", "BSLeafAnimNode")]
    shapes = [block_name(n, i) for i in range(len(n.blocks)) if n.type_of(i) in NAMED and n.type_of(i) not in
              ("NiNode", "BSFadeNode", "BSLeafAnimNode")]
    skins = [skin_bones(n, i) for i in range(len(n.blocks)) if n.type_of(i) == "BSSkin::Instance"]
    try:
        paths = nifmod.referenced_paths(n)
    except Exception as e:  # report, never hide
        paths = [f"<referenced_paths failed: {e}>"]
    return {"bs_version": n.bs_version, "blocks": dict(types), "nodes": nodes, "shapes": shapes, "skins": skins,
            "paths": paths}


def archives(data_dir, pattern):
    return sorted(glob.glob(os.path.join(data_dir, pattern)))


def scan_meshes(data_dir, pattern, keys, keep_dir=None):
    found = {}
    for path in archives(data_dir, pattern):
        a = Ba2(path)
        for e in a.entries:
            low = e.name.lower().replace("/", "\\")
            if not any(k in low for k in keys):
                continue
            rec = {"archive": os.path.basename(path), "size": e.unpacked or e.packed}
            if low.endswith(".nif") and sum(1 for v in found.values() if "nif" in v) < MAX_NIFS:
                try:
                    data = a.read(e.name)
                    rec["nif"] = summarize_nif(data)
                    if keep_dir:
                        dst = os.path.join(keep_dir, low.replace("\\", os.sep))
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        with open(dst, "wb") as f:
                            f.write(data)
                except Exception as ex:
                    rec["nif_error"] = str(ex)
            found[low] = rec
    return found


def scan_voices(data_dir, pattern, keys=None, samples=6):
    """Voice folders (sound\\voice\\<plugin>\\<type>\\...) with file counts and extensions; keys filter the type."""
    folders = defaultdict(lambda: {"count": 0, "ext": Counter(), "sample": []})
    for path in archives(data_dir, pattern):
        for e in Ba2(path).entries:
            parts = e.name.lower().replace("/", "\\").split("\\")
            if len(parts) < 5 or parts[0] != "sound" or parts[1] != "voice":
                continue
            vt = f"{parts[2]}\\{parts[3]}"
            if keys and not any(k in parts[3] for k in keys):
                continue
            f = folders[vt]
            f["count"] += 1
            f["ext"][os.path.splitext(parts[-1])[1]] += 1
            if len(f["sample"]) < samples:
                f["sample"].append(e.name)
    return {k: {"count": v["count"], "ext": dict(v["ext"]), "sample": v["sample"]} for k, v in folders.items()}


def probe_tools(fo4_data, sf_data):
    roots = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
    found = {
        "wwise": [p for r in roots for p in glob.glob(os.path.join(r, "Audiokinetic", "*"))],
        "sf_ck": [p for p in (os.path.join(sf_data, "..", "CreationKit.exe"),) if os.path.exists(p)],
        "sf_tools": sorted(os.listdir(os.path.join(sf_data, "..", "Tools"))) if os.path.isdir(os.path.join(sf_data, "..", "Tools")) else [],
        "fo4_ck": [p for p in glob.glob(os.path.join(fo4_data, "..", "..", "..", "common", "Fallout 4", "CreationKit.exe"))],
        "xwmaencode": [p for p in glob.glob(os.path.join(fo4_data, "..", "..", "..", "common", "Fallout 4", "Tools", "Audio", "xWMAEncode.exe"))],
    }
    for exe in ("ffmpeg", "vgmstream-cli", "WwiseConsole"):
        found[exe] = shutil.which(exe)
    return found


def short_report(rep):
    out = []
    for side in ("fo4_meshes", "sf_meshes"):
        out.append(f"== {side}: {len(rep[side])} entries")
        for name, r in sorted(rep[side].items()):
            line = f"{name} ({r['archive']}, {r['size']} B)"
            if "nif" in r:
                s = r["nif"]
                bones = [b for sk in s["skins"] for b in sk.get("bones", [])]
                line += (f" bs{s['bs_version']} shapes={s['shapes'][:8]} skinbones={len(bones)}:{sorted(set(filter(None, bones)))[:40]}"
                         f" paths={s['paths'][:6]}")
            if "nif_error" in r:
                line += f" ERROR {r['nif_error']}"
            out.append(line)
    for side in ("fo4_voice", "sf_voice_sample"):
        out.append(f"== {side}")
        for vt, v in sorted(rep[side].items(), key=lambda kv: -kv[1]["count"])[:12]:
            out.append(f"{vt}: {v['count']} {v['ext']} e.g. {v['sample'][:3]}")
    out.append(f"== tools {json.dumps(rep['tools'])}")
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--fo4-data", required=True)
    p.add_argument("--sf-data", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--keep", action="store_true", help="also extract the matched NIFs under <out>/nifs (scratch only)")
    a = p.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    keep = os.path.join(a.out, "nifs") if a.keep else None
    rep = {
        "fo4_meshes": scan_meshes(a.fo4_data, "Fallout4 - Meshes*.ba2", FO4_MESH_KEYS, keep),
        "sf_meshes": scan_meshes(a.sf_data, "Starfield - Meshes*.ba2", SF_MESH_KEYS, keep),
        "fo4_voice": scan_voices(a.fo4_data, "Fallout4 - Voices*.ba2", VOICE_KEYS),
        "sf_voice_sample": dict(list(scan_voices(a.sf_data, "Starfield - Voices*.ba2", None, 3).items())[:4]),
        "tools": probe_tools(a.fo4_data, a.sf_data),
    }
    with open(os.path.join(a.out, "codsworth_inventory.json"), "w") as f:
        json.dump(rep, f, indent=1)
    text = short_report(rep)
    with open(os.path.join(a.out, "codsworth_inventory.txt"), "w") as f:
        f.write(text)
    print(text[:7000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
