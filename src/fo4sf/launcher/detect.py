"""detect: can this PC build the port? The launcher's first stage (research/next-phase launcher-architecture.md §2),
read only.

    Fallout 4   Fallout4.esm present and its hash in the known-sources table (unknown versions are refused unless
                allow_unknown: Wabbajack and TTW refuse sources they cannot match); the six DLC masters, missing ones
                named (the port assumes all six, so a missing DLC is a refusal unless allow_missing_dlc)
    Starfield   Starfield.exe and Data present; Archive2 present (packing needs it: required); Creation Kit and SFSE
                presence reported (both allowed as requirements by the owner, 2026-10-19; required only if asked)
    Disk        free space on the output drive, minus the floor that must stay free (40 GB on the owner's D:), against
                the space the build needs

The known-sources table (scripts/launcher_recipes/known_sources.json) maps master hashes to a version label. It starts
empty: entries come from a real install with `launcher.py sources-add --manifest <build manifest>`, never typed in.
"""
import os
import shutil

from . import files
from . import manifest as mf

DEFAULT_FLOOR_GB = 40.0


def load_sources(path):
    if not path or not os.path.isfile(path):
        return {"schema": 1, "sources": []}
    return files.load_json(path)


def add_sources(table, man, label):
    """Entries for every master in a build manifest, under one label. Returns the number added (duplicates skipped)."""
    have = {(s["file"].casefold(), s["sha256"]) for s in table["sources"]}
    n = 0
    for name, m in sorted(((man.get("fo4") or {}).get("masters") or {}).items()):
        if not m.get("sha256"):
            continue
        key = (name.casefold(), m["sha256"])
        if key not in have:
            table["sources"].append({"file": name, "sha256": m["sha256"], "size": m.get("size"), "label": label})
            have.add(key)
            n += 1
    return n


def match_source(table, name, sha):
    for s in table["sources"]:
        if s["file"].casefold() == name.casefold() and s["sha256"] == sha:
            return s["label"]
    return None


def free_gb(path):
    probe = os.path.abspath(path)
    while not os.path.exists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    return shutil.disk_usage(probe).free / 2 ** 30


def detect(*, fo4_data, starfield, sources=None, out_dir=None, need_gb=0.0, floor_gb=DEFAULT_FLOOR_GB,
           allow_unknown=False, allow_missing_dlc=False, require_ck=False, require_sfse=False):
    """{"ready": bool, "refusals": [...], "warnings": [...], "fo4": {...}, "game": {...}, "disk": {...}}."""
    refusals, warnings = [], []
    table = sources if isinstance(sources, dict) else load_sources(sources)
    out = {"fo4": None, "game": None, "disk": None}
    try:
        fo4 = mf.fo4_inputs(fo4_data)
    except FileNotFoundError as e:
        refusals.append(f"Fallout 4: {e}")
        fo4 = None
    if fo4:
        versions = {}
        for name, m in fo4["masters"].items():
            label = match_source(table, name, m["sha256"])
            versions[name] = label
            if label is None:
                (warnings if allow_unknown else refusals).append(
                    f"Fallout 4: {name} (sha256 {m['sha256'][:12]}...) is not a known version")
        if fo4["dlc_missing"]:
            (warnings if allow_missing_dlc else refusals).append("DLC missing: " + ", ".join(fo4["dlc_missing"]))
        out["fo4"] = {"masters": {n: {"sha256": m["sha256"], "size": m["size"], "version": versions[n]}
                                  for n, m in fo4["masters"].items()},
                      "dlc_missing": fo4["dlc_missing"], "archives": len(fo4["archives"])}
    if starfield and os.path.isdir(starfield):
        g = mf.game_pins(starfield)
        f = g["files"]
        if f.get("Starfield.exe") is None:
            refusals.append("Starfield: Starfield.exe not found")
        if not os.path.isdir(os.path.join(starfield, "Data")):
            refusals.append("Starfield: no Data folder")
        if f.get("Tools/Archive2/Archive2.exe") is None:
            refusals.append("Starfield: Archive2 not found (Tools\\Archive2, installed with the free Creation Kit)")
        if not g["creation_kit"]:
            (refusals if require_ck else warnings).append("Starfield: Creation Kit not installed")
        if not g["sfse"]:
            (refusals if require_sfse else warnings).append("Starfield: SFSE not installed")
        out["game"] = {"sfse": g["sfse"], "creation_kit": g["creation_kit"],
                       "archive2": f.get("Tools/Archive2/Archive2.exe") is not None,
                       "exe_sha256": (f.get("Starfield.exe") or {}).get("sha256")}
    else:
        refusals.append(f"Starfield: folder {starfield!r} not found")
    if out_dir:
        free = free_gb(out_dir)
        usable = free - floor_gb
        out["disk"] = {"path": os.path.abspath(out_dir), "free_gb": round(free, 1), "floor_gb": floor_gb,
                       "need_gb": need_gb, "usable_gb": round(usable, 1)}
        if usable < need_gb:
            refusals.append(f"Disk: {free:.1f} GB free on {out_dir}, {floor_gb:g} GB must stay free, the build needs "
                            f"{need_gb:g} GB")
    out.update(ready=not refusals, refusals=refusals, warnings=warnings)
    return out


def measure(root):
    """Disk use of a folder counting each hard-linked file once: {"files", "bytes_listed", "bytes_unique",
    "bytes_shared", "frees_if_deleted"}. bytes_shared is the part of bytes_unique in files that also have links
    outside this folder (their space stays held elsewhere), so deleting the folder frees bytes_unique - bytes_shared."""
    inodes, listed, n = {}, 0, 0
    for d, _dirs, names in os.walk(root):
        for name in names:
            st = os.stat(os.path.join(d, name))
            n += 1
            listed += st.st_size
            key = (st.st_dev, st.st_ino) if st.st_ino else ("path", os.path.join(d, name))
            if key in inodes:
                inodes[key][2] += 1
            else:
                inodes[key] = [st.st_size, st.st_nlink, 1]
    unique = sum(v[0] for v in inodes.values())
    shared = sum(v[0] for v in inodes.values() if v[1] > v[2])
    return {"files": n, "bytes_listed": listed, "bytes_unique": unique, "bytes_shared": shared,
            "frees_if_deleted": unique - shared}
