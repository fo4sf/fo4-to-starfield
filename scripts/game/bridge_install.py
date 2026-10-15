"""Install / uninstall the observation bridge next to the converted build (docs/ai/test-queue.md "Bridge").

The bridge is its own small deployment, independent of the queue's experiment (exp_install.py keeps exactly one
experiment record; the bridge rides along with any of them): FO4SFBridge.esm and "FO4SFBridge - Main.ba2" (the
compiled script FO4SF_Bridge.pex, packed from the staged Data tree the way exp_install packs experiments: loose
scripts are not read on this install) go into the game's Data folder, "*FO4SFBridge.esm" goes to the end of
Plugins.txt, and Data\\FO4SFBridge.install.json records what was added. install is idempotent: the same staged bridge
already in place (same file hashes) is left alone and only its Plugins.txt line is checked; a different one is
refused until uninstalled. uninstall removes exactly the recorded files (unchanged ones only) and the Plugins.txt line
it added. exp_install.py uninstall never touches the bridge; the chain may leave it installed between queues.

usage: python bridge_install.py install|uninstall|status --dir <staged bridge dir> --starfield <game dir>
       (the staged dir: scripts/bridge/make_bridge.py stage, e.g. C:\\Modding\\staging\\bridge_t0)
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exp_install  # noqa: E402
from exp_install import deployment  # noqa: E402

RECORD = "FO4SFBridge.install.json"
PLUGIN = "FO4SFBridge.esm"
ARCHIVE = "FO4SFBridge - Main.ba2"
PEX = os.path.join("Data", "Scripts", "FO4SF_Bridge.pex")


def record_path(a):
    data = os.path.abspath(os.path.join(a.starfield, "Data"))
    return data, os.path.join(data, RECORD)


def read_record(rec_p):
    with open(rec_p, encoding="utf-8") as f:
        return json.load(f)


def plugin_line_present(lines, plugin):
    """The index of the active line for plugin in Plugins.txt's lines, else None."""
    for k, ln in enumerate(lines):
        if ln.strip().casefold() == ("*" + plugin).casefold():
            return k
    return None


def activate(plugin):
    """Plugins.txt with "*<plugin>" as its last line (any earlier line for the plugin, active or not, removed and
    recorded so uninstall can put it back). Returns the record fields."""
    p = exp_install.plugins_txt()
    original = exp_install.read_bytes(p)
    lines, bom, nl = exp_install.plugin_lines(original)
    removed = [ln for ln in lines if ln.strip().lstrip("*").casefold() == plugin.casefold()]
    kept = [ln for ln in lines if ln not in removed]
    new = kept + ["*" + plugin]
    if original is None:
        exp_install.write_plugins(p, new, bom, nl)
    else:
        exp_install.write_plugins(p, new, bom, nl, original)
    return {"plugins_txt": p, "plugin_line_added": "*" + plugin, "plugin_lines_removed": removed}


def deactivate(rec):
    """Undo activate: the added line goes, the removed ones come back (at the end)."""
    p = exp_install.plugins_txt()
    if os.path.normcase(os.path.abspath(rec.get("plugins_txt", p))) != os.path.normcase(os.path.abspath(p)):
        raise ValueError("recorded Plugins.txt does not match the current user path")
    original = exp_install.read_bytes(p)
    if original is None:
        return
    lines, bom, nl = exp_install.plugin_lines(original)
    added = (rec.get("plugin_line_added") or "").strip().casefold()
    new = [ln for ln in lines if ln.strip().casefold() != added] + list(rec.get("plugin_lines_removed") or [])
    if new != lines:
        exp_install.write_plugins(p, new, bom, nl, original)


def staged(a):
    d = os.path.abspath(a.dir)
    plugin = os.path.join(d, PLUGIN)
    pex = os.path.join(d, PEX)
    for p in (plugin, pex):
        if not os.path.exists(p):
            sys.exit(f"staged bridge incomplete: {p} missing (scripts/bridge/make_bridge.py stage)")
    return d, plugin, pex


def install(a):
    data, rec_p = record_path(a)
    try:
        exp_install.require_complete_master(data)
    except (OSError, ValueError) as error:
        sys.exit(f"bridge not installed: {error}")
    d, plugin_src, pex = staged(a)
    source = {PLUGIN: exp_install.digest(plugin_src), PEX: exp_install.digest(pex)}
    targets = {PLUGIN: exp_install.data_path(data, PLUGIN), ARCHIVE: exp_install.data_path(data, ARCHIVE)}
    if os.path.exists(rec_p):
        rec = read_record(rec_p)
        if rec.get("complete") is not True or rec.get("cleanup_pending"):
            sys.exit(f"incomplete bridge install ({rec_p}); uninstall it first")
        same = rec.get("source_sha256") == source and all(
            os.path.exists(targets[rel]) and exp_install.digest(targets[rel]) == h for rel, h in rec["files"].items())
        if not same:
            sys.exit(f"another bridge is installed ({rec_p}: {rec.get('dir')}); uninstall it first")
        lines, _, _ = exp_install.read_plugins(exp_install.plugins_txt())
        if plugin_line_present(lines, PLUGIN) is None:    # e.g. a deploy rewrote Plugins.txt: activate again
            rec.update(activate(PLUGIN))
            deployment.write_manifest(rec_p, rec)
            print(f"already installed; {PLUGIN} activated again")
        else:
            print("already installed")
        return
    clash = [rel for rel in targets if os.path.exists(targets[rel])]
    if clash:
        sys.exit(f"refusing to overwrite existing game files: {clash}")
    rec = {"dir": d, "plugin": PLUGIN, "source_sha256": source, "files": {}, "complete": False}
    with tempfile.TemporaryDirectory(prefix="fo4sf-bridge-pack-") as tmp:
        ba2 = exp_install.build_ba2(SimpleNamespace(starfield=a.starfield), os.path.join(d, "Data"),
                                    os.path.join(tmp, ARCHIVE))
        deployment.write_manifest(rec_p, rec)             # the record first: a crash leaves it incomplete, not silent
        for rel, src in ((PLUGIN, plugin_src), (ARCHIVE, ba2)):
            shutil.copy2(src, targets[rel])
            rec["files"][rel] = exp_install.digest(targets[rel])
            deployment.write_manifest(rec_p, rec)
    rec.update(activate(PLUGIN))
    rec["complete"] = True
    deployment.write_manifest(rec_p, rec)
    print(f"installed {PLUGIN} + \"{ARCHIVE}\" from {d}; {PLUGIN} active")


def uninstall(a):
    data, rec_p = record_path(a)
    if not os.path.exists(rec_p):
        print("bridge not installed")
        return
    rec = read_record(rec_p)
    errors = []
    try:
        deactivate(rec)
        rec["plugin_line_added"] = ""
        rec["plugin_lines_removed"] = []
    except (OSError, ValueError) as e:
        errors.append(str(e))
    kept = {}
    for rel, h in list(rec.get("files", {}).items()):
        dst = exp_install.data_path(data, rel)
        try:
            if os.path.exists(dst):
                if exp_install.digest(dst) != h:
                    raise OSError(f"file changed since install; preserved: {rel}")
                os.remove(dst)
        except OSError as e:
            kept[rel] = h
            errors.append(str(e))
    rec["files"] = kept
    if errors:
        rec["cleanup_pending"] = True
        deployment.write_manifest(rec_p, rec)
        sys.exit(f"bridge partly uninstalled, record retained at {rec_p}: {'; '.join(errors)}")
    os.remove(rec_p)
    print("uninstalled")


def status(a):
    data, rec_p = record_path(a)
    if not os.path.exists(rec_p):
        print(json.dumps({"installed": False}))
        return
    rec = read_record(rec_p)
    lines, _, _ = exp_install.read_plugins(exp_install.plugins_txt())
    print(json.dumps(dict(rec, installed=True, active=plugin_line_present(lines, PLUGIN) is not None)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("install", "uninstall", "status"))
    ap.add_argument("--dir", default="", help="the staged bridge folder (install)")
    ap.add_argument("--starfield", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "install":
        if not a.dir:
            sys.exit("install needs --dir")
        install(a)
    elif a.cmd == "uninstall":
        uninstall(a)
    else:
        status(a)


if __name__ == "__main__":
    main()
