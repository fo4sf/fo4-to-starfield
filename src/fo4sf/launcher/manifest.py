"""The build manifest: what a build was made from (Fallout 4 masters and archives, DLC presence, tool and game pins)
and what it made (plugins, assets, hashes). One JSON file per build; two manifests compare recorded inputs/pins
before outputs. Content identity is confirmed only for files whose hashes were recorded.

Inputs are read only. Masters are always hashed (a different Fallout4.esm is a different build). Archives (.ba2) are
recorded by size, modification time and BA2 version unless hash_archives is set: hashing the full FO4 + DLC archive
set reads tens of GB. Paths/timestamps are informational in cross-PC comparison; content proof requires hashes.
"""
import glob
import os
import platform
import re
import subprocess
import sys

from . import files

SCHEMA = 1
BASE_MASTER = "Fallout4.esm"
# The six official DLC masters (Bethesda's file names). The project assumes all six; a missing one is reported by
# name, never silently built around.
DLC_MASTERS = {
    "DLCRobot.esm": "Automatron",
    "DLCworkshop01.esm": "Wasteland Workshop",
    "DLCCoast.esm": "Far Harbor",
    "DLCworkshop02.esm": "Contraptions Workshop",
    "DLCworkshop03.esm": "Vault-Tec Workshop",
    "DLCNukaWorld.esm": "Nuka-World",
}
# Starfield files whose identity pins a game build. The executable and the loader are hashed; Starfield.esm by size
# and time (its hash is one more large read; pass hash_game_esm for it).
GAME_FILES = ("Starfield.exe", "sfse_loader.exe")
GAME_TOOLS = ("CreationKit.exe", os.path.join("Tools", "Archive2", "Archive2.exe"))


def find_ci(dirs, name):
    """First path of `name` (case-insensitive) directly in one of dirs, or None."""
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for n in os.listdir(d):
            if n.casefold() == name.casefold():
                return os.path.join(d, n)
    return None


def fo4_inputs(data_dirs, hash_archives=False):
    """The Fallout 4 side: the base master and each DLC master (found in any of data_dirs, since Steam depots keep
    DLC in their own Data folders), and every .ba2 next to them. Raises FileNotFoundError without Fallout4.esm."""
    data_dirs = [os.path.abspath(d) for d in data_dirs]
    base = find_ci(data_dirs, BASE_MASTER)
    if base is None:
        raise FileNotFoundError(f"{BASE_MASTER} not found in {data_dirs}")
    masters = {BASE_MASTER: dict(files.identity(base), path=base)}
    dlc = {}
    for name, title in DLC_MASTERS.items():
        p = find_ci(data_dirs, name)
        dlc[name] = {"title": title, "present": p is not None}
        if p:
            masters[name] = dict(files.identity(p), path=p)
    archives, duplicates = {}, {}
    for d in data_dirs:
        for p in sorted(glob.glob(os.path.join(d, "*.ba2"))):
            name = os.path.basename(p)
            if name in archives:
                # the same archive name in two Data folders (the owner's depot-split install has Meshes.ba2 twice):
                # the later folder wins, as before; both paths are recorded so the choice is visible
                duplicates.setdefault(name, [archives[name]["path"]]).append(p)
            archives[name] = dict(files.identity(p, None if hash_archives else 0), path=p,
                                  ba2_version=ba2_header_version(p))
    return {"data_dirs": data_dirs, "masters": masters, "dlc": dlc,
            "dlc_missing": [f"{n} ({v['title']})" for n, v in dlc.items() if not v["present"]],
            "archives": archives, "archive_identity": "sha256" if hash_archives else "size+mtime",
            "archive_duplicates": duplicates}


def ba2_header_version(path):
    """The BA2 header's version field (Fallout 4: 1 before the 2024 next-gen update, 7 or 8 after), or None."""
    with open(path, "rb") as f:
        head = f.read(8)
    if len(head) < 8 or head[:4] != b"BTDX":
        return None
    return int.from_bytes(head[4:8], "little")


def game_pins(starfield_dir, hash_game_esm=False):
    """Starfield's own files: executable, SFSE loader, Starfield.esm, Creation Kit and Archive2 presence."""
    root = os.path.abspath(starfield_dir)
    out = {"dir": root, "files": {}}
    for rel in GAME_FILES + GAME_TOOLS:
        p = os.path.join(root, rel)
        out["files"][rel.replace(os.sep, "/")] = files.identity(p) if os.path.isfile(p) else None
    esm = os.path.join(root, "Data", "Starfield.esm")
    out["files"]["Data/Starfield.esm"] = (files.identity(esm, None if hash_game_esm else 0)
                                          if os.path.isfile(esm) else None)
    # the SFSE runtime DLLs next to the loader, hashed (small); their names come from the folder, never assumed
    out["sfse_dlls"] = {n: files.identity(os.path.join(root, n)) for n in sorted(os.listdir(root))
                        if n.casefold().startswith("sfse_") and n.casefold().endswith(".dll")
                        and os.path.isfile(os.path.join(root, n))} if os.path.isdir(root) else {}
    out["sfse"] = out["files"]["sfse_loader.exe"] is not None
    out["creation_kit"] = out["files"]["CreationKit.exe"] is not None
    return out


def _run(argv, cwd=None):
    try:
        r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def tool_pins(repo):
    """The converter's own identity: repo commit and whether the tree is dirty, Python and its numeric libraries,
    the dotnet SDK (when on PATH) and the Mutagen version every dotnet project references."""
    pins = {"repo_commit": _run(["git", "rev-parse", "HEAD"], cwd=repo),
            "repo_dirty": None, "python": sys.version.split()[0], "platform": platform.platform()}
    status = _run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=repo)
    if status is not None:
        pins["repo_dirty"] = bool(status)
    for mod in ("numpy", "PIL"):
        try:
            pins[mod] = __import__(mod).__version__
        except Exception:  # noqa: BLE001 - a missing library is a pin of its own
            pins[mod] = None
    pins["dotnet"] = _run(["dotnet", "--version"])
    mutagen = set()
    for proj in glob.glob(os.path.join(repo, "dotnet", "*", "*.csproj")):
        with open(proj, encoding="utf-8") as f:
            mutagen.update(re.findall(r'Include="(Mutagen\.[\w.]+)"\s+Version="([^"]+)"', f.read()))
    pins["mutagen"] = sorted(f"{n} {v}" for n, v in mutagen)
    return pins


def outputs(paths, hash_limit=None):
    """Every file under each output folder (or the file itself): plugins and json always hashed, the rest hashed up to
    hash_limit bytes (None: everything)."""
    out = {}
    for p in paths:
        p = os.path.abspath(p)
        if os.path.isfile(p):
            out[p] = {os.path.basename(p): files.identity(p)}
        elif os.path.isdir(p):
            out[p] = files.tree(p, hash_limit)
        else:
            out[p] = None
    return out


def build_manifest(*, repo, fo4_data=(), starfield="", output_paths=(), hash_archives=False, hash_limit=None,
                   hash_game_esm=False, extra=None):
    m = {"schema": SCHEMA, "tools": tool_pins(repo)}
    if fo4_data:
        m["fo4"] = fo4_inputs(fo4_data, hash_archives)
    if starfield:
        m["game"] = game_pins(starfield, hash_game_esm)
    m["outputs"] = outputs(output_paths, hash_limit)
    if extra:
        m["extra"] = extra
    return m


def compare_inputs(a, b):
    """Differences in compared input metadata/hashes and pins. Empty does not prove unhashed file content equal.
    Paths/timestamps are informational across PCs; archive version, size and available hashes are compared."""
    diffs = []
    fa, fb = a.get("fo4") or {}, b.get("fo4") or {}
    for name in sorted(set(fa.get("masters", {})) | set(fb.get("masters", {}))):
        x, y = fa.get("masters", {}).get(name), fb.get("masters", {}).get(name)
        if (x or {}).get("sha256") != (y or {}).get("sha256"):
            diffs.append(f"master {name}: {(x or {}).get('sha256', 'missing')} vs {(y or {}).get('sha256', 'missing')}")
    for name in sorted(set(fa.get("archives", {})) | set(fb.get("archives", {}))):
        x, y = fa.get("archives", {}).get(name), fb.get("archives", {}).get(name)
        if x is None or y is None:
            diffs.append(f"archive {name}: only in {'second' if x is None else 'first'}")
        else:
            if x.get("size") != y.get("size") or x.get("sha256") != y.get("sha256"):
                diffs.append(f"archive {name}: size or hash differs")
            if x.get("ba2_version") != y.get("ba2_version"):
                diffs.append(f"archive {name}: BA2 version differs ({x.get('ba2_version')} vs {y.get('ba2_version')})")
    ta, tb = a.get("tools", {}), b.get("tools", {})
    for k in ("repo_commit", "repo_dirty", "python", "numpy", "PIL", "dotnet", "mutagen"):
        if ta.get(k) != tb.get(k):
            diffs.append(f"tool {k}: {ta.get(k)} vs {tb.get(k)}")
    ga, gb = (a.get("game") or {}).get("files", {}), (b.get("game") or {}).get("files", {})
    for k in sorted(set(ga) | set(gb)):
        x, y = ga.get(k), gb.get(k)
        if (x is None) != (y is None) or (x and y and (x.get("size"), x.get("sha256")) != (y.get("size"), y.get("sha256"))):
            diffs.append(f"game {k}: differs")
    sa, sb = (a.get("game") or {}).get("sfse_dlls") or {}, (b.get("game") or {}).get("sfse_dlls") or {}
    for k in sorted(set(sa) | set(sb)):
        x, y = sa.get(k), sb.get(k)
        if x is None or y is None:
            diffs.append(f"game {k}: only in {'second' if x is None else 'first'}")
        elif (x.get("size"), x.get("sha256")) != (y.get("size"), y.get("sha256")):
            diffs.append(f"game {k}: differs")
    return diffs
