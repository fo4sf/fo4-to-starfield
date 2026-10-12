"""Install / uninstall a staged in-game experiment (a plugin plus loose files) next to the converted build, reversibly.

usage: python exp_install.py install|uninstall|status --exp-dir <staged dir> --starfield <game dir> [--pack]
                             [--needs light,console]
       python exp_install.py order --starfield <game dir>

The staged dir holds one or more <name>.esm files (only those listed with --plugins are activated, default: the first
one alphabetically) and a Data\\ tree of loose files (e.g. Data\\Terrain\\*.btd). install refuses to overwrite any existing
file, records everything it adds in Data\\FO4SFExp.install.json, and appends "*<plugin>" to Plugins.txt. uninstall removes
exactly what the record lists (files unchanged since install only) and only the Plugins.txt lines it added; it never
touches FO4Port's own deployment (deploy_starfield.py).

--pack (Starfield reads no loose files on this install) packs the whole Data tree, textures included, into the first
plugin's own "<plugin> - Main.ba2" (Archive2 -format=General, stored). That is how vanilla ships terrain textures: all
7,761 textures/terrain/* files in Starfield's Data (463 overlay masks) are in General archives ("Starfield -
DensityMaps.ba2"; SFBGS00D's 44 overlay masks in "SFBGS00D - Main.ba2" although "SFBGS00D - Textures.ba2" exists), none
in a DDS archive (read-only BA2 name scan, 2026-10-11). The archive is built in a temporary folder, so the staged
experiment folder (often another track's) is only read. A staged folder without a Data tree (a plugin-only experiment
such as the converted raider) installs its plugins and no archive.

--needs (a queue's pre_launch, testqueue.py plan-*): install only when this checkout's runner has those features
(runner_features.py); the queue runs this script by a path relative to the runner's checkout, so it is the runner's own
copy, and a copy from before --needs existed refuses the option (argparse, exit 2): an older runner stops before it
launches the game instead of running a queue without its time of day or console lines.

order (cycle.ps1 runs it after deploy_starfield.py has activated FO4Port.esm, right before the launch): every plugin
this install activated loads after each of its masters that Plugins.txt lists. install appends the experiment's
plugins before the launch, and cycle.ps1's deploy appends "*FO4Port.esm" after them on every launch, so a plugin that
masters FO4Port.esm (the slice's door plugin, docs/slice/redrocket-door.md) would otherwise load before its own master.
A master that is neither listed in Plugins.txt nor one of the game's own implicit files (Starfield.esm, the official
ESMs) cannot be loaded at all: exit 6, Plugins.txt unchanged. Lines are only moved, never added or removed, so both
uninstalls (this script's and deploy_starfield.py's, which remove lines by their text) still find theirs.
"""
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

RECORD = "FO4SFExp.install.json"
# files the game loads on its own, never listed in Plugins.txt (Starfield.esm, the official masters); compared
# case-insensitively, "sfbgs" as a prefix (SFBGS003.esm ... SFBGS047.esm on this install)
IMPLICIT = ("starfield.esm", "blueprintships-starfield.esm", "constellation.esm", "oldmars.esm", "shatteredspace.esm")


def plugin_masters(path):
    """The master file names in a plugin's TES4 header (MAST subrecords, in header order). Raises ValueError for a
    file that is not a TES4 plugin."""
    with open(path, "rb") as f:
        head = f.read(24)
        if len(head) < 24 or head[:4] != b"TES4":
            raise ValueError(f"{path}: not a TES4 plugin")
        size = struct.unpack_from("<I", head, 4)[0]
        data = f.read(size)
    out, pos = [], 0
    big = None                                            # XXXX: the next subrecord's real size (u32)
    while pos + 6 <= len(data):
        typ = data[pos:pos + 4]
        n = struct.unpack_from("<H", data, pos + 4)[0]
        if typ == b"XXXX":
            big = struct.unpack_from("<I", data, pos + 6)[0]
            pos += 6 + n
            continue
        if big is not None:
            n, big = big, None
        if typ == b"MAST":
            out.append(data[pos + 6:pos + 6 + n].split(b"\0")[0].decode("utf-8", "replace"))
        pos += 6 + n
    return out


def implicit(name):
    low = name.casefold()
    return low in IMPLICIT or low.startswith("sfbgs")


def order_lines(lines, plugins, masters):
    """(new lines, moved, missing): every plugin in `plugins` (activated by this install, in that order) moved right
    after the last line naming one of its masters, when it stands before it. masters: {plugin: [master, ...]}.
    missing: (plugin, master) pairs whose master is neither on a line nor implicit."""
    def name(ln):
        return ln.strip().lstrip("*").strip().casefold()
    out = list(lines)
    moved, missing = [], []
    for _ in range(len(plugins) + 1):                     # a chain of masters settles within len(plugins) passes
        changed = False
        for p in plugins:
            at = [k for k, ln in enumerate(out) if name(ln) == p.casefold()]
            if not at:
                continue
            i = at[0]
            last = -1
            for m in masters.get(p, []):
                idx = [k for k, ln in enumerate(out) if name(ln) == m.casefold()]
                if idx:
                    last = max(last, max(idx))
                elif not implicit(m) and (p, m) not in missing:
                    missing.append((p, m))
            if last > i:
                ln = out.pop(i)
                out.insert(last, ln)                       # last shifted down by one after the pop: right after it
                if p not in moved:
                    moved.append(p)
                changed = True
        if not changed:
            break
    return out, moved, missing


def order(a):
    """Plugins.txt: the plugins this install activated after their masters (module doc). 0 ok, 6 a master missing."""
    data = os.path.join(a.starfield, "Data")
    rec_p = os.path.join(data, RECORD)
    if not os.path.exists(rec_p):
        print("nothing installed: no order to fix")
        return 0
    rec = read_json(rec_p)
    plugins = [x.lstrip("*") for x in rec.get("plugins_added", [])]
    masters = {}
    for p in plugins:
        f = os.path.join(data, p)
        if os.path.exists(f):
            masters[p] = plugin_masters(f)
    p_txt = plugins_txt()
    lines, bom, nl = read_plugins(p_txt)
    new, moved, missing = order_lines(lines, plugins, masters)
    if missing:
        print("not ordered: " + "; ".join(f"{p} needs {m}, which Plugins.txt does not list" for p, m in missing))
        return 6
    if new != lines:
        write_plugins(p_txt, new, bom, nl)
        print(f"moved after their masters: {', '.join(moved)}")
    else:
        print("order ok: every installed plugin loads after its masters")
    return 0


def read_json(p):
    with open(p) as f:
        return json.load(f)


def plugins_txt():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Starfield", "Plugins.txt")


def read_plugins(p):
    """(lines, bom, newline) of Plugins.txt, so a rewrite keeps the file's own BOM and line endings."""
    if not os.path.exists(p):
        return [], b"", "\r\n"
    with open(p, "rb") as f:
        raw = f.read()
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


def build_ba2(a, root, out):
    """Pack every top-level folder under root into a general BA2 with the official Archive2 (as deploy_starfield.py)."""
    tool = os.path.join(a.starfield, "Tools", "Archive2", "Archive2.exe")
    if not os.path.exists(tool):
        sys.exit(f"Archive2 not found at {tool} (Starfield Creation Kit)")
    folders = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    if not folders:
        sys.exit(f"nothing to pack under {root}")
    tmp = out + ".tmp.ba2"
    if os.path.exists(tmp):
        os.remove(tmp)
    # stored, not compressed: all 2,112 vanilla BTDs (and every official plugin's Main.ba2) are stored uncompressed,
    # and the engine streams BTD blocks by offset from the archive; zlib-packed BTDs read as raw 0 everywhere
    # (terrain runs 2026-10-11: flat at exactly the ENAM minimum)
    r = subprocess.run([tool, ",".join(folders), f"-create={tmp}", f"-root={root}", "-format=General",
                        "-compression=None"], cwd=root, capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.isfile(tmp)
    if ok:
        with open(tmp, "rb") as f:
            ok = f.read(4) == b"BTDX"
    if not ok:
        sys.exit("Archive2 failed:\n" + (r.stdout or "") + (r.stderr or ""))
    os.replace(tmp, out)
    return out


def install(a):
    data = os.path.join(a.starfield, "Data")
    rec_p = os.path.join(data, RECORD)
    plugins = [p.strip() for p in a.plugins.split(",") if p.strip()] if a.plugins else \
        sorted(f for f in os.listdir(a.exp_dir) if f.lower().endswith(".esm"))[:1]
    if os.path.exists(rec_p):
        rec = read_json(rec_p)
        same = os.path.normcase(rec.get("exp_dir", "")) == os.path.normcase(os.path.abspath(a.exp_dir)) and \
            all(p in rec["files"] for p in plugins)
        if same:                                          # a relaunch of the same experiment: nothing to do
            print("already installed")
            return
        sys.exit(f"another experiment is installed ({rec_p}); uninstall it first")
    files = staged_files(a.exp_dir, plugins)
    if not a.pack:
        return copy_in(data, rec_p, a.exp_dir, plugins, files)
    if not any(rel not in plugins for _, rel in files):
        # a plugin-only experiment (actor_raider1: one NPC_, no assets): nothing to archive, the plugins alone go in
        print("no Data tree staged: installing the plugins without an archive")
        return copy_in(data, rec_p, a.exp_dir, plugins, files)
    # Starfield reads no loose files here (Starfield.ini sResourceDataDirsFinal=STRINGS\ only; terrain experiment 1,
    # 2026-10-11, got procedural planet ground because its loose BTDs were never seen). A plugin's own
    # "<name> - Main.ba2" loads with it, so the staged Data tree goes into that archive instead, built outside the
    # staged folder.
    work = tempfile.mkdtemp(prefix="fo4sf_exp_pack_")
    try:
        ba2 = os.path.splitext(plugins[0])[0] + " - Main.ba2"
        built = build_ba2(a, os.path.join(a.exp_dir, "Data"), os.path.join(work, ba2))
        return copy_in(data, rec_p, a.exp_dir, plugins, [(s, r) for s, r in files if r in plugins] + [(built, ba2)])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def copy_in(data, rec_p, exp_dir, plugins, files):
    """Copy (source, path in Data) into the game's Data folder, never over an existing file; record it; activate."""
    clash = [rel for _, rel in files if os.path.exists(os.path.join(data, rel))]
    if clash:
        sys.exit(f"refusing to overwrite existing game files: {clash}")
    rec = {"exp_dir": os.path.abspath(exp_dir), "files": {}, "dirs": [], "plugins_added": []}
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
    rec = read_json(rec_p)
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
        with open(rec_p, "w") as f:
            json.dump(rec, f, indent=1)
        sys.exit(f"kept files that changed since install: {kept}")
    os.remove(rec_p)
    print("uninstalled")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("install", "uninstall", "status", "order"))
    ap.add_argument("--exp-dir", default="")
    ap.add_argument("--starfield", required=True)
    ap.add_argument("--plugins", default="", help="comma-separated plugin file names to activate")
    ap.add_argument("--pack", action="store_true", help="install the staged Data tree as '<first plugin> - Main.ba2'")
    ap.add_argument("--needs", default="", help="runner features the queue needs (runner_features.py); refuse without")
    a = ap.parse_args(argv)
    if a.cmd == "install":
        if not a.exp_dir:
            sys.exit("--exp-dir is required")
        need = [x.strip() for x in a.needs.split(",") if x.strip()]
        if need:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import runner_features
            miss = runner_features.missing(need)
            if miss:
                print(f"not installed: this runner lacks {', '.join(miss)} (runner_features.py has "
                      f"{', '.join(runner_features.FEATURES)}); update its checkout first")
                sys.exit(5)
        return install(a)
    if a.cmd == "uninstall":
        return uninstall(a)
    if a.cmd == "order":
        sys.exit(order(a))
    rec_p = os.path.join(a.starfield, "Data", RECORD)
    if not os.path.exists(rec_p):
        print("nothing installed")
        return
    with open(rec_p) as f:
        print(f.read())


if __name__ == "__main__":
    main()
