"""Install / uninstall / status of the staged combined-core probe plugin (docs/spikes/combined-core-probes.md
"Stage and install"), next to the installed core, reversibly: scripts/game/bridge_install.py's pattern for a second
small deployment that rides along with the queue's experiment record (exp_install.py keeps exactly one of those).

usage: python scripts/combined_probes/probe_install.py install --dir <stage> --starfield <game dir>
       python scripts/combined_probes/probe_install.py uninstall --starfield <game dir>
       python scripts/combined_probes/probe_install.py status --starfield <game dir>

install: FO4SFCombinedProbe.esm and "FO4SFCombinedProbe - Main.ba2" (the stage's Data\\Scripts\\*.pex packed the way
exp_install packs experiments: loose scripts are not read on this install) go into the game's Data folder,
"*FO4SFCombinedProbe.esm" to the END of Plugins.txt (so the queue's planned load indices do not shift, rule 3 of the
runbook), and Data\\FO4SFCombinedProbe.install.json records what was added, with the stage's plan.json variant and
build id. It refuses: a stage whose plan.json hashes do not match its files (runbook rule 6); an incomplete core
(exp_install's record); an active FO4SFMission.esm or another probe variant already installed (runbook rule 2: both
override the core's persistent cell, never together); any existing game file. The same stage already in place is a
no-op (its Plugins.txt line is re-added if a deploy dropped it).
uninstall removes exactly the recorded files (unchanged ones only) and the Plugins.txt line it added.
status prints one JSON object: installed, active (the Plugins.txt line present), variant, build_id, dir, mission_active.
Game closed for install and uninstall (Starfield rewrites Plugins.txt on launch). Nothing of the game enters the repo.
"""
import argparse
import json
import os
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "game"))
import bridge_install  # noqa: E402  (activate / deactivate / plugin_line_present / validate_profile / archive_inputs)
import exp_install  # noqa: E402
from exp_install import deployment  # noqa: E402

RECORD = "FO4SFCombinedProbe.install.json"
PLUGIN = "FO4SFCombinedProbe.esm"
ARCHIVE = "FO4SFCombinedProbe - Main.ba2"
MISSION = "FO4SFMission.esm"                              # overrides the same core cell: never beside the probe
PEXES = tuple(os.path.join("Data", "Scripts", n + ".pex") for n in ("FOCC_ProbeQuest", "FOCC_Probe", "FOCC_P10Quest"))


def record_path(a):
    data = os.path.abspath(os.path.join(a.starfield, "Data"))
    return data, os.path.join(data, RECORD)


def read_record(rec_p):
    with open(rec_p, encoding="utf-8") as f:
        return json.load(f)


def mission_active(lines):
    return bridge_install.plugin_line_present(lines, MISSION) is not None


def staged(a):
    """The stage folder checked against its own plan.json: the plugin, the three .pex files and the recorded hashes.
    Returns (dir, plugin path, plan)."""
    d = os.path.abspath(a.dir)
    plan_p = os.path.join(d, "plan.json")
    if not os.path.exists(plan_p):
        sys.exit(f"staged probe incomplete: {plan_p} missing (scripts/combined_probes/make_combined_probe.py stage)")
    with open(plan_p, encoding="utf-8") as f:
        plan = json.load(f)
    if plan.get("kind") != "combined-probe" or plan.get("plugin") != PLUGIN:
        sys.exit(f"{plan_p} is not a combined-probe stage of {PLUGIN}")
    plugin = os.path.join(d, PLUGIN)
    for rel in (PLUGIN,) + PEXES:
        if not os.path.exists(os.path.join(d, rel)):
            sys.exit(f"staged probe incomplete: {os.path.join(d, rel)} missing")
    outputs = plan.get("outputs") or {}
    for rel, want in outputs.items():
        path = os.path.join(d, rel.replace("/", os.sep))
        if not os.path.exists(path) or exp_install.digest(path) != want:
            sys.exit(f"stage changed after it was built: {rel} does not match plan.json (runbook rule 6)")
    if outputs.get(PLUGIN) != plan.get("plugin_sha256"):
        sys.exit("plan.json: outputs and plugin_sha256 disagree")
    return d, plugin, plan


def install(a):
    data, rec_p = record_path(a)
    try:
        exp_install.require_complete_master(data)
    except (OSError, ValueError) as error:
        sys.exit(f"probe not installed: {error}")
    d, plugin_src, plan = staged(a)
    lines, _, _ = exp_install.read_plugins(exp_install.plugins_txt())
    if mission_active(lines):
        sys.exit(f"probe not installed: {MISSION} is active in Plugins.txt; both override the core's persistent cell "
                 "(runbook rule 2): uninstall the mission first")
    source = _source_inventory(d)                           # every packed file: another script set is another probe
    targets = {PLUGIN: exp_install.data_path(data, PLUGIN), ARCHIVE: exp_install.data_path(data, ARCHIVE)}
    if os.path.exists(rec_p):
        rec = read_record(rec_p)
        if rec.get("complete") is not True or rec.get("cleanup_pending"):
            sys.exit(f"incomplete probe install ({rec_p}); uninstall it first")
        same = (rec.get("source_sha256") == source and isinstance(rec.get("files"), dict)
                and set(rec["files"]) == set(targets) and all(
            os.path.exists(targets[rel]) and exp_install.digest(targets[rel]) == h for rel, h in rec["files"].items()))
        if not same:
            sys.exit(f"another probe variant is installed ({rec_p}: variant {rec.get('variant')}, build "
                     f"{rec.get('build_id')} from {rec.get('dir')}); uninstall it first (runbook rule 2)")
        exp_install.verify_archive(targets[ARCHIVE], bridge_install.archive_inputs(source))
        if bridge_install.plugin_line_present(lines, PLUGIN) is None:    # e.g. a deploy rewrote Plugins.txt
            rec.setdefault("published_files", list(rec["files"]))
            bridge_install.activate(PLUGIN, rec, rec_p)
            rec["complete"] = True
            deployment.write_manifest(rec_p, rec)
            print(f"already installed; {PLUGIN} activated again")
        else:
            print("already installed")
        return
    clash = [rel for rel in targets if os.path.exists(targets[rel])]
    if clash:
        sys.exit(f"refusing to overwrite existing game files: {clash}")
    rec = {"schema": 2, "dir": d, "plugin": PLUGIN, "variant": plan.get("variant"), "build_id": plan.get("build_id"),
           "plugin_sha256": plan.get("plugin_sha256"), "skip": plan.get("skip", []), "source_sha256": source,
           "files": {}, "published_files": [], "complete": False}
    with tempfile.TemporaryDirectory(prefix="fo4sf-probe-pack-") as tmp:
        ba2 = exp_install.build_ba2(SimpleNamespace(starfield=a.starfield), os.path.join(d, "Data"),
                                    os.path.join(tmp, ARCHIVE))
        if _source_inventory(d) != source:
            raise OSError("probe stage changed while packing; nothing installed")
        exp_install.verify_archive(ba2, bridge_install.archive_inputs(source))
        identities = {PLUGIN: source[PLUGIN], ARCHIVE: exp_install.digest(ba2)}
        deployment.write_manifest(rec_p, rec)
        try:
            for rel, src in ((PLUGIN, plugin_src), (ARCHIVE, ba2)):
                rec["files"][rel] = identities[rel]                  # intent before publication
                deployment.write_manifest(rec_p, rec)
                try:
                    deployment.copy_new_artifact(src, targets[rel], expected_sha256=identities[rel])
                except FileExistsError:
                    rec["files"].pop(rel)                            # exclusive creation proves this isn't ours
                    rec.setdefault("not_published", []).append(rel)
                    deployment.write_manifest(rec_p, rec)
                    raise
                rec["published_files"].append(rel)
                deployment.write_manifest(rec_p, rec)
                if exp_install.digest(targets[rel]) != identities[rel]:
                    raise OSError(f"installed probe differs from pinned source: {rel}")
            bridge_install.activate(PLUGIN, rec, rec_p)
            rec["complete"] = True
            deployment.write_manifest(rec_p, rec)
        except BaseException:
            rec["complete"] = False
            try:
                uninstall(a, _recovery=rec)
            except (OSError, ValueError, SystemExit) as recovery:
                print(f"probe recovery incomplete; preserve {rec_p}: {recovery}", file=sys.stderr)
            raise
    print(f"installed {PLUGIN} (variant {plan.get('variant')}, build {plan.get('build_id')}) + \"{ARCHIVE}\" from {d}; "
          f"{PLUGIN} active (last in Plugins.txt)")


def _source_inventory(directory):
    """sha256 of the plugin and of every file under the stage's Data tree (another script set is another probe)."""
    source = {PLUGIN: exp_install.digest(os.path.join(directory, PLUGIN))}
    for root, dirs, names in os.walk(os.path.join(directory, "Data")):
        dirs.sort()
        for name in sorted(names):
            path = os.path.join(root, name)
            source[os.path.relpath(path, directory)] = exp_install.digest(path)
    return source


def uninstall(a, _recovery=None):
    data, rec_p = record_path(a)
    if not os.path.exists(rec_p):
        print("probe not installed")
        return
    rec = read_record(rec_p) if _recovery is None else _recovery
    bridge_install.validate_profile(rec)
    if not isinstance(rec.get("files"), dict) or set(rec["files"]) - {PLUGIN, ARCHIVE}:
        raise ValueError("unexpected probe file ownership; record preserved")
    errors = []
    try:
        if not rec.get("complete"):
            if rec.get("plugins_restore_pending"):
                deployment.restore_plugins(rec)
        else:
            bridge_install.deactivate(rec)
        rec["plugins_restore_pending"] = False
        rec["plugin_line_added"] = ""
        rec["plugin_lines_removed"] = []
    except (OSError, ValueError) as e:
        errors.append(str(e))
    kept = {}
    removed = []
    for rel, h in list(rec.get("files", {}).items()):
        dst = exp_install.data_path(data, rel)
        try:
            if os.path.exists(dst):
                if not rec.get("complete") and rel not in rec.get("published_files", []):
                    raise OSError(f"unconfirmed probe publication; preserved: {rel}")
                if exp_install.digest(dst) != h:
                    raise OSError(f"file changed since install; preserved: {rel}")
                os.remove(dst)
                removed.append(rel)
        except OSError as e:
            kept[rel] = h
            errors.append(str(e))
    rec["files"] = kept
    for rel in (PLUGIN, ARCHIVE):
        if (rel not in rec["files"] and rel not in rec.get("not_published", [])
                and os.path.exists(exp_install.data_path(data, rel))):
            errors.append(f"untracked probe file; preserved: {rel}")
    if errors:
        rec["cleanup_pending"] = True
        deployment.write_manifest(rec_p, rec)
        sys.exit(f"probe partly uninstalled, record retained at {rec_p}: {'; '.join(errors)}")
    os.remove(rec_p)
    for rel in removed:
        print(f"removed Data\\{rel}")
    print(f"uninstalled ({PLUGIN} line removed from Plugins.txt)")


def status(a):
    data, rec_p = record_path(a)
    lines, _, _ = exp_install.read_plugins(exp_install.plugins_txt())
    out = {"installed": False, "mission_active": mission_active(lines)}
    if os.path.exists(rec_p):
        rec = read_record(rec_p)
        out.update({"installed": True, "complete": rec.get("complete") is True and not rec.get("cleanup_pending"),
                    "active": bridge_install.plugin_line_present(lines, PLUGIN) is not None,
                    "variant": rec.get("variant"), "build_id": rec.get("build_id"), "dir": rec.get("dir"),
                    "skip": rec.get("skip", []), "files": rec.get("files", {})})
    print(json.dumps(out, sort_keys=True))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("install", "uninstall", "status"))
    ap.add_argument("--dir", default="", help="the staged probe folder (install)")
    ap.add_argument("--starfield", required=True, help="the game folder (Starfield.exe)")
    a = ap.parse_args(argv)
    if a.cmd == "install":
        if not a.dir:
            sys.exit("install needs --dir <stage>")
        install(a)
    elif a.cmd == "uninstall":
        uninstall(a)
    else:
        status(a)


if __name__ == "__main__":
    main()
