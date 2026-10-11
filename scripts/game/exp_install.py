"""Install / uninstall a staged in-game experiment (a plugin plus loose files) next to the converted build, reversibly.

usage: python exp_install.py install|uninstall|status --exp-dir <staged dir> --starfield <game dir>

The staged dir holds one or more <name>.esm files (only those listed with --plugins are activated, default: the first
one alphabetically) and a Data\\ tree of loose files (e.g. Data\\Terrain\\*.btd). install refuses to overwrite any existing
file, records everything it adds in Data\\FO4SFExp.install.json, and appends "*<plugin>" to Plugins.txt. uninstall removes
exactly what the record lists (files unchanged since install only) and only the Plugins.txt lines it added; it never
touches FO4Port's own deployment (deploy_starfield.py).
"""
import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys

# Reuse the converter deployer's tested atomic writes and no-overwrite publication.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deploy_starfield as deployment  # noqa: E402

RECORD = "FO4SFExp.install.json"
_UNSET = object()


def plugins_txt():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Starfield", "Plugins.txt")


def read_bytes(p):
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        return f.read()


def plugin_lines(raw):
    """(lines, bom, newline) from one snapshot of Plugins.txt."""
    if raw is None:
        return [], b"", "\r\n"
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    text = raw[len(bom):].decode("utf-8")
    return text.splitlines(), bom, ("\r\n" if "\r\n" in text else "\n")


def read_plugins(p):
    return plugin_lines(read_bytes(p))


def write_plugins(p, lines, bom, nl, expected_current=_UNSET):
    content = bom + (nl.join(lines) + nl).encode("utf-8")
    kwargs = {} if expected_current is _UNSET else {"expected_current": expected_current}
    os.makedirs(os.path.dirname(p), exist_ok=True)
    deployment.atomic_write_bytes(p, content, ".fo4sfexp-plugins-", **kwargs)


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


def data_path(data, rel):
    """Resolve only targets inside this installation's Data folder."""
    root = os.path.realpath(data)
    target = os.path.realpath(os.path.join(data, rel))
    if os.path.commonpath((root, target)) != root or target == root:
        raise ValueError(f"experiment path is outside Data: {rel!r}")
    return target


def cleanup(data, rec_p, rec):
    """Undo confirmed publications; preserve changed/unproven files and a retryable journal."""
    targets = {rel: data_path(data, rel) for rel in rec["files"]}
    directories = {rel: data_path(data, rel) for rel in rec["dirs"]}
    p = plugins_txt()
    if os.path.normcase(os.path.abspath(rec.get("plugins_txt", p))) != os.path.normcase(os.path.abspath(p)):
        raise ValueError("recorded Plugins.txt does not match the current user path")
    errors = []
    try:
        if not rec.get("complete", True):
            if rec.get("plugins_restore_pending"):
                deployment.restore_plugins(rec)
                rec["plugins_restore_pending"] = False
                rec["plugins_added"] = []
        elif rec["plugins_added"] and os.path.exists(p):
            original = read_bytes(p)
            lines, bom, nl = plugin_lines(original)
            added = {x.casefold() for x in rec["plugins_added"]}
            write_plugins(p, [ln for ln in lines if ln.strip().casefold() not in added], bom, nl, original)
            rec["plugins_added"] = []
    except OSError as e:
        errors.append(str(e))
    published = set(rec.get("published_files", []))
    kept = {}
    for rel, h in rec["files"].items():
        dst = targets[rel]
        try:
            if os.path.exists(dst):
                if not rec.get("complete", True) and rel not in published:
                    raise OSError(f"destination was not confirmed as published; preserved: {rel}")
                if digest(dst) != h:
                    raise OSError(f"file changed since install; preserved: {rel}")
                os.remove(dst)
        except OSError as e:
            kept[rel] = h
            errors.append(str(e))
    rec["files"] = kept
    rec["published_files"] = [rel for rel in rec.get("published_files", []) if rel in kept]
    for rel in sorted(directories, key=len, reverse=True):
        full = directories[rel]
        try:
            if os.path.isdir(full) and not os.listdir(full):
                os.rmdir(full)
        except OSError as e:
            errors.append(str(e))
    if errors:
        rec["cleanup_pending"] = True
        deployment.write_manifest(rec_p, rec)
        raise OSError(f"recovery record retained at {rec_p}: {'; '.join(errors)}")
    os.remove(rec_p)


def build_ba2(a, root, out):
    """Build a fresh general BA2, preserving the previous archive if validation fails."""
    folders = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    if not folders:
        sys.exit(f"nothing to pack under {root}")
    deployment.build_archive(argparse.Namespace(starfield=a.starfield, staging=root), out, folders, "General")
    return out


def install(a):
    data = os.path.abspath(os.path.join(a.starfield, "Data"))
    rec_p = os.path.join(data, RECORD)
    plugins = [p.strip() for p in a.plugins.split(",") if p.strip()] if a.plugins else \
        sorted(f for f in os.listdir(a.exp_dir) if f.lower().endswith(".esm"))[:1]
    packed = bool(getattr(a, "pack", False))
    if packed and not plugins:
        sys.exit("packing requires at least one experiment plugin")
    if os.path.exists(rec_p):
        with open(rec_p) as f:
            rec = json.load(f)
        if not rec.get("complete", True) or rec.get("cleanup_pending"):
            sys.exit(f"incomplete experiment install ({rec_p}); uninstall it first")
        same = os.path.normcase(rec.get("exp_dir", "")) == os.path.normcase(os.path.abspath(a.exp_dir)) and \
            all(p in rec["files"] for p in plugins)
        if same:                                          # a relaunch of the same experiment: nothing to do
            if bool(rec.get("pack", False)) != packed:
                sys.exit("experiment packing mode changed; uninstall it before changing modes")
            print("already installed")
            return
        sys.exit(f"another experiment is installed ({rec_p}); uninstall it first")
    files = staged_files(a.exp_dir, plugins)
    names = [rel for _, rel in files]
    if packed:
        # Starfield reads no loose files here (Starfield.ini sResourceDataDirsFinal=STRINGS\ only; terrain experiment 1,
        # 2026-10-11, got procedural planet ground because its loose BTDs were never seen). A plugin's own
        # "<name> - Main.ba2" loads with it, so the staged Data tree goes into that archive instead.
        ba2 = os.path.splitext(plugins[0])[0] + " - Main.ba2"
        files = [(s, r) for s, r in files if r in plugins]
        names = [rel for _, rel in files] + [ba2]
    targets = {rel: data_path(data, rel) for rel in names}
    clash = [rel for rel in names if os.path.exists(targets[rel])]
    if clash:
        sys.exit(f"refusing to overwrite existing game files: {clash}")
    # Validate all sources and snapshot activation before publishing anything.
    identities = {rel: digest(src) for src, rel in files}
    if packed:
        built = build_ba2(a, os.path.join(a.exp_dir, "Data"), os.path.join(a.exp_dir, ba2))
        files.append((built, ba2))
        identities[ba2] = digest(built)
    p = plugins_txt()
    original = read_bytes(p)
    lines, bom, nl = plugin_lines(original)
    rec = {"exp_dir": os.path.abspath(a.exp_dir), "files": {}, "dirs": [], "plugins_added": [],
           "complete": False, "pack": packed, "published_files": [], "plugins_txt": p,
           "plugins_original": base64.b64encode(original).decode("ascii") if original is not None else None,
           "plugins_restore_pending": False}
    names = {ln.lstrip("*").strip().casefold() for ln in lines}
    for plug in plugins:
        if plug.casefold() not in names:
            lines.append("*" + plug)
            rec["plugins_added"].append("*" + plug)
    activated = bom + (nl.join(lines) + nl).encode("utf-8")
    rec["plugins_activated"] = base64.b64encode(activated).decode("ascii")
    deployment.write_manifest(rec_p, rec)
    try:
        for src, rel in files:
            dst = targets[rel]
            missing = []
            d = os.path.dirname(dst)
            while d != data and not os.path.isdir(d):
                missing.append(os.path.relpath(d, data))
                d = os.path.dirname(d)
            rec["dirs"].extend(reversed(missing))
            rec["files"][rel] = identities[rel]
            deployment.write_manifest(rec_p, rec)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            deployment.copy_new_artifact(src, dst)
            rec["published_files"].append(rel)
            if digest(dst) != identities[rel]:
                raise OSError(f"installed file differs from validated source: {rel}")
            deployment.write_manifest(rec_p, rec)
        if rec["plugins_added"]:
            if read_bytes(p) != original:
                raise OSError("Plugins.txt changed during install; preserving concurrent edits")
            rec["plugins_restore_pending"] = True
            deployment.write_manifest(rec_p, rec)
            write_plugins(p, lines, bom, nl, original)
        rec["complete"] = True
        deployment.write_manifest(rec_p, rec)
    except Exception as e:
        rec["complete"] = False
        try:
            cleanup(data, rec_p, rec)
        except (OSError, ValueError) as recovery:
            sys.exit(f"install failed: {e}; {recovery}")
        sys.exit(f"install failed and was rolled back: {e}")
    print(f"installed {len(rec['files'])} files, plugins {rec['plugins_added']}")


def uninstall(a):
    data = os.path.join(a.starfield, "Data")
    rec_p = os.path.join(data, RECORD)
    if not os.path.exists(rec_p):
        print("nothing installed")
        return
    with open(rec_p) as f:
        rec = json.load(f)
    try:
        cleanup(data, rec_p, rec)
    except (OSError, ValueError) as e:
        sys.exit(f"uninstall incomplete: {e}")
    print("uninstalled")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("install", "uninstall", "status"))
    ap.add_argument("--exp-dir", default="")
    ap.add_argument("--starfield", required=True)
    ap.add_argument("--plugins", default="", help="comma-separated plugin file names to activate")
    ap.add_argument("--pack", action="store_true", help="install the staged Data tree as '<first plugin> - Main.ba2'")
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
