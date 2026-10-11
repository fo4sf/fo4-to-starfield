"""Install / uninstall a staged in-game experiment (a plugin plus loose files) next to the converted build, reversibly.

usage: python exp_install.py install|uninstall|status --exp-dir <staged dir> --starfield <game dir> [--pack]

The staged dir holds one or more <name>.esm files (only those listed with --plugins are activated, default: the first
one alphabetically) and a Data\\ tree of loose files (e.g. Data\\Terrain\\*.btd). install refuses to overwrite any existing
file, records everything it adds in Data\\FO4SFExp.install.json, and appends "*<plugin>" to Plugins.txt. uninstall removes
exactly what the record lists (files unchanged since install only) and only the Plugins.txt lines it added; it never
touches FO4Port's own deployment (deploy_starfield.py).

--pack (Starfield reads no loose files on this install) packs the Data tree into the first plugin's own archives, as
deploy_starfield.py does for FO4Port: Data\\textures into "<plugin> - Textures.ba2" (Archive2 -format=DDS, .dds files
only) and every other top-level folder into "<plugin> - Main.ba2" (-format=General).
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

RECORD = "FO4SFExp.install.json"


def plugins_txt():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Starfield", "Plugins.txt")


def read_plugins(p):
    """(lines, bom, newline) of Plugins.txt, so a rewrite keeps the file's own BOM and line endings."""
    if not os.path.exists(p):
        return [], b"", "\r\n"
    raw = open(p, "rb").read()
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    text = raw[len(bom):].decode("utf-8")
    return text.splitlines(), bom, ("\r\n" if "\r\n" in text else "\n")


def write_plugins(p, lines, bom, nl):
    tmp = p + ".fo4sfexp.tmp"
    with open(tmp, "wb") as f:
        f.write(bom + (nl.join(lines) + nl).encode("utf-8"))
    os.replace(tmp, p)


def digest(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def staged_files(exp_dir, plugins):
    """(source, path relative to the game's Data folder) for the plugins and the Data tree."""
    out = [(os.path.join(exp_dir, p), p) for p in plugins]
    data = os.path.join(exp_dir, "Data")
    for root, _, files in os.walk(data):
        for f in files:
            src = os.path.join(root, f)
            out.append((src, os.path.relpath(src, data)))
    return out


TEXTURES = "textures"                                     # packed with -format=DDS, like FO4Port - Textures.ba2


def build_ba2(a, root, out, folders=None, fmt="General"):
    """Pack top-level folders under root (default: all of them) into one BA2 with the official Archive2, as
    deploy_starfield.py does: format General for meshes, terrain and materials, DDS for textures."""
    tool = os.path.join(a.starfield, "Tools", "Archive2", "Archive2.exe")
    if not os.path.exists(tool):
        sys.exit(f"Archive2 not found at {tool} (Starfield Creation Kit)")
    if folders is None:
        folders = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    if not folders:
        sys.exit(f"nothing to pack under {root}")
    tmp = out + ".tmp.ba2"
    if os.path.exists(tmp):
        os.remove(tmp)
    r = subprocess.run([tool, ",".join(folders), f"-create={tmp}", f"-root={root}", f"-format={fmt}",
                        "-compression=Default"], cwd=root, capture_output=True, text=True)
    ok =r.returncode == 0 and os.path.isfile(tmp)
    if ok:
        with open(tmp, "rb") as f:
            ok = f.read(4) == b"BTDX"
    if not ok:
        sys.exit("Archive2 failed:\n" + (r.stdout or "") + (r.stderr or ""))
    os.replace(tmp, out)
    return out


def pack(a, plugins):
    """[(built archive, name in Data)] for the staged Data tree: textures -> '<plugin> - Textures.ba2' (DDS), every
    other top-level folder -> '<plugin> - Main.ba2' (General). Checked before anything is built."""
    root = os.path.join(a.exp_dir, "Data")
    tops = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))) if os.path.isdir(root) else []
    tex = [d for d in tops if d.lower() == TEXTURES]
    main = [d for d in tops if d.lower() != TEXTURES]
    if not tops:
        sys.exit(f"nothing to pack under {root}")
    other = [os.path.relpath(os.path.join(r, f), root) for d in tex for r, _, fs in os.walk(os.path.join(root, d))
             for f in fs if not f.lower().endswith(".dds")]
    if other:                                             # a DDS archive holds textures only
        sys.exit(f"not a .dds file under Data\\textures (move it out of textures): {other}")
    stem = os.path.splitext(plugins[0])[0]
    out = []
    for folders, fmt, name in ((main, "General", f"{stem} - Main.ba2"), (tex, "DDS", f"{stem} - Textures.ba2")):
        if folders:
            out.append((build_ba2(a, root, os.path.join(a.exp_dir, name), folders, fmt), name))
    return out


def install(a):
    data = os.path.join(a.starfield, "Data")
    rec_p = os.path.join(data, RECORD)
    plugins = [p.strip() for p in a.plugins.split(",") if p.strip()] if a.plugins else \
        sorted(f for f in os.listdir(a.exp_dir) if f.lower().endswith(".esm"))[:1]
    if os.path.exists(rec_p):
        rec = json.load(open(rec_p))
        same = os.path.normcase(rec.get("exp_dir", "")) == os.path.normcase(os.path.abspath(a.exp_dir)) and \
            all(p in rec["files"] for p in plugins)
        if same:                                          # a relaunch of the same experiment: nothing to do
            print("already installed")
            return
        sys.exit(f"another experiment is installed ({rec_p}); uninstall it first")
    files = staged_files(a.exp_dir, plugins)
    if a.pack:
        # Starfield reads no loose files here (Starfield.ini sResourceDataDirsFinal=STRINGS\ only; terrain experiment 1,
        # 2026-10-11, got procedural planet ground because its loose BTDs were never seen). A plugin's own
        # "<name> - Main.ba2" and "<name> - Textures.ba2" load with it, so the staged Data tree goes into those.
        files = [(s, r) for s, r in files if r in plugins] + pack(a, plugins)
    clash = [rel for _, rel in files if os.path.exists(os.path.join(data, rel))]
    if clash:
        sys.exit(f"refusing to overwrite existing game files: {clash}")
    rec = {"exp_dir": os.path.abspath(a.exp_dir), "files": {}, "dirs": [], "plugins_added": []}
    for src, rel in files:
        dst = os.path.join(data, rel)
        d = os.path.dirname(dst)
        if not os.path.isdir(d):
            os.makedirs(d)
            rec["dirs"].append(os.path.relpath(d, data))
        shutil.copyfile(src, dst)
        rec["files"][rel] = digest(dst)
    p = plugins_txt()
    lines, bom, nl = read_plugins(p)
    names = {ln.lstrip("*").strip().casefold() for ln in lines}
    for plug in plugins:
        if plug.casefold() not in names:
            lines.append("*" + plug)
            rec["plugins_added"].append("*" + plug)
    write_plugins(p, lines, bom, nl)
    with open(rec_p, "w") as f:
        json.dump(rec, f, indent=1)
    print(f"installed {len(rec['files'])} files, plugins {rec['plugins_added']}")


def uninstall(a):
    data = os.path.join(a.starfield, "Data")
    rec_p = os.path.join(data, RECORD)
    if not os.path.exists(rec_p):
        print("nothing installed")
        return
    rec = json.load(open(rec_p))
    kept = []
    for rel, h in rec["files"].items():
        dst = os.path.join(data, rel)
        if os.path.exists(dst):
            if digest(dst) != h:
                kept.append(rel)                          # changed since install: not ours any more
                continue
            os.remove(dst)
    for d in sorted(rec["dirs"], key=len, reverse=True):
        full = os.path.join(data, d)
        if os.path.isdir(full) and not os.listdir(full):
            os.rmdir(full)
    p = plugins_txt()
    if os.path.exists(p) and rec["plugins_added"]:
        added = {x.casefold() for x in rec["plugins_added"]}
        lines, bom, nl = read_plugins(p)
        write_plugins(p, [ln for ln in lines if ln.strip().casefold() not in added], bom, nl)
    if kept:
        rec["files"] = {k: rec["files"][k] for k in kept}
        json.dump(rec, open(rec_p, "w"), indent=1)
        sys.exit(f"kept files that changed since install: {kept}")
    os.remove(rec_p)
    print("uninstalled")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("install", "uninstall", "status"))
    ap.add_argument("--exp-dir", default="")
    ap.add_argument("--starfield", required=True)
    ap.add_argument("--plugins", default="", help="comma-separated plugin file names to activate")
    ap.add_argument("--pack", action="store_true", help="install the staged Data tree as '<first plugin> - Main.ba2' "
                                                         "and Data\\textures as '<first plugin> - Textures.ba2'")
    a = ap.parse_args(argv)
    if a.cmd == "install":
        if not a.exp_dir:
            sys.exit("--exp-dir is required")
        return install(a)
    if a.cmd == "uninstall":
        return uninstall(a)
    rec_p = os.path.join(a.starfield, "Data", RECORD)
    print(open(rec_p).read() if os.path.exists(rec_p) else "nothing installed")


if __name__ == "__main__":
    main()
