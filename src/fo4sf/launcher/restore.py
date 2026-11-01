"""Recorded restore: return Starfield's Data folder and Plugins.txt to a recorded state.

This formalises what the install thread's swap scripts do by hand (bridge uninstall, experiment uninstall, experiment
install, order, bridge install; the port deployment kept or swapped) on top of the existing installers, which own
every file they add and record it:

    FO4Port.deploy.json              scripts/deploy_starfield.py                   (the converted port, FO4Port.esm and its archives)
    FO4SFExp.install.json            scripts/game/exp_install.py                   (one experiment: the terrain core, mission, ...)
    FO4SFPlanetProbe.install.json    scripts/planet/planet_probe_install.py        (the planet probe)
    FO4SFQuestProbe.install.json     scripts/questprobe/questprobe_install.py      (the quest-engine probe)
    FO4SFCombinedProbe.install.json  scripts/combined_probes/probe_install.py      (the combined-core probe)
    FO4SFMapMarkers.install.json     scripts/game/map_markers_install.py           (the map markers plugin)
    FO4SFBridge.install.json         scripts/game/bridge_install.py                (the observation bridge)

Until 2026-10-31 only the port, the experiment and the bridge were known here, so the line of any other installed
plugin of ours in Plugins.txt read as the owner's edit and every restore with the map markers installed was refused.
Some ride on another component (RIDES_ON): the map markers plugin and the combined probe are staged against the
installed core (an experiment) and the quest probe against the installed FO4Port.esm, and their installers refuse
any other build. When that base is uninstalled, replaced or recovered, the rider comes off first and goes back on
after it (map_markers_install.py: "uninstall it before a core swap ... install it again after the swap"), even when
its own record did not change.

snapshot  records Plugins.txt (bytes), every top-level file in Data that is a plugin or an archive (name, size, time;
          plugins hashed), every install record above (verbatim), the live hash of every file those records own
          (loose files in subfolders included), and any extra watched files (INIs).
plan      compares the live state with a snapshot and lists the installer commands that would bring it back: uninstall
          what was added since, reinstall what the snapshot had (from the source folder its record names), in the
          swap scripts' order. Plugins.txt is restored byte for byte only when every line that differs names a
          plugin one of the installers owns; any other difference is the owner's edit and is a conflict.
          A file an installer owns that is missing or no longer matches its recorded hash is a conflict, now or in
          the snapshot itself (a snapshot taken over a changed owned file is refused as a target).
apply     refuses while Starfield runs or on any conflict, runs the plan through the installers (never deleting a
          file itself), restores Plugins.txt, then takes a new snapshot and checks it against the target.

Files in Data that no record owns and the snapshot did not have are reported and left alone. Nothing here hashes
Starfield's own multi-GB archives: they are identified by size and time.
"""
import base64
import hashlib
import json
import os
import subprocess
import sys

from . import files, port_restore

SCHEMA = 1
# component -> (record file in Data, installer script under the repo)
COMPONENTS = {
    "port": ("FO4Port.deploy.json", os.path.join("scripts", "deploy_starfield.py")),
    "experiment": ("FO4SFExp.install.json", os.path.join("scripts", "game", "exp_install.py")),
    "planet_probe": ("FO4SFPlanetProbe.install.json", os.path.join("scripts", "planet", "planet_probe_install.py")),
    "quest_probe": ("FO4SFQuestProbe.install.json", os.path.join("scripts", "questprobe", "questprobe_install.py")),
    "combined_probe": ("FO4SFCombinedProbe.install.json", os.path.join("scripts", "combined_probes", "probe_install.py")),
    "markers": ("FO4SFMapMarkers.install.json", os.path.join("scripts", "game", "map_markers_install.py")),
    "bridge": ("FO4SFBridge.install.json", os.path.join("scripts", "game", "bridge_install.py")),
}
# the swap scripts: bridge first off, last on; the map markers just inside it (cycle.ps1 orders them in that order)
INSTALL_ORDER = ("port", "experiment", "planet_probe", "quest_probe", "combined_probe", "markers", "bridge")
UNINSTALL_ORDER = tuple(reversed(INSTALL_ORDER))
# rider -> the component whose installed build its installer pins (module doc)
RIDES_ON = {"markers": "experiment", "combined_probe": "experiment", "quest_probe": "port"}
# records written by exp_install.py's code (exp_dir, plugins, pack, source_inputs) and by bridge_install.py's
# (dir, plugin, source_sha256)
EXP_KIT = ("experiment", "planet_probe")
BRIDGE_KIT = ("quest_probe", "combined_probe", "markers", "bridge")
WATCHED_EXT = (".esm", ".esp", ".esl", ".ba2", ".json")


class RestoreRefused(RuntimeError):
    pass


def plugins_txt_default():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Starfield", "Plugins.txt")


def _plugins_txt_path(path):
    """Bind snapshots and installers to one LOCALAPPDATA/Starfield/Plugins.txt address."""
    try:
        requested = os.fspath(path)
    except TypeError:
        raise RestoreRefused("Plugins.txt path must be a filesystem path") from None
    if not isinstance(requested, str) or not requested:
        raise RestoreRefused("Plugins.txt path must be nonempty text")
    requested = os.path.abspath(requested)
    parent = os.path.dirname(requested)
    if os.path.basename(requested).casefold() != "plugins.txt" or os.path.basename(parent).casefold() != "starfield":
        raise RestoreRefused("Plugins.txt must address LOCALAPPDATA/Starfield/Plugins.txt")
    canonical = os.path.join(os.path.dirname(parent), "Starfield", "Plugins.txt")
    if requested != canonical:
        for given, actual in ((parent, os.path.dirname(canonical)), (requested, canonical)):
            present, actual_present = os.path.exists(given), os.path.exists(actual)
            if present != actual_present or (present and os.path.realpath(given) != os.path.realpath(actual)):
                raise RestoreRefused("Plugins.txt case alias addresses a different installer namespace")
    return canonical


def _read(path):
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return f.read()


def take(starfield, plugins_txt=None, watch=()):
    """The snapshot dict of a Starfield install (read only)."""
    data = os.path.join(os.path.abspath(starfield), "Data")
    pt = _plugins_txt_path(plugins_txt or plugins_txt_default())
    raw = _read(pt)
    top = {}
    if os.path.isdir(data):
        for n in sorted(os.listdir(data)):
            p = os.path.join(data, n)
            if os.path.isfile(p) and n.lower().endswith(WATCHED_EXT):
                top[n] = files.identity(p, None if n.lower().endswith((".esm", ".esp", ".esl", ".json")) else 0)
    records = {}
    for comp, (rec_name, _script) in COMPONENTS.items():
        b = _read(os.path.join(data, rec_name))
        records[comp] = None if b is None else json.loads(b.decode("utf-8-sig"))
    owned_live = {}
    for comp, rec in records.items():
        if rec:
            owned_live[comp] = {rel: (files.sha256(path) if os.path.isfile(path) else None)
                                for rel, path in ((r, os.path.join(data, *r.replace("\\", "/").split("/")))
                                                  for r in sorted(owned_expected(comp, rec)))}
    watched = {}
    for w in watch:
        b = _read(w)
        watched[os.path.abspath(w)] = None if b is None else hashlib.sha256(b).hexdigest()
    return {"schema": SCHEMA, "starfield": os.path.abspath(starfield), "plugins_txt": os.path.abspath(pt),
            "plugins_txt_b64": None if raw is None else base64.b64encode(raw).decode("ascii"),
            "plugins_txt_sha256": None if raw is None else hashlib.sha256(raw).hexdigest(),
            "data_top": top, "records": records, "owned_live": owned_live, "watched": watched}


def owned_expected(comp, rec):
    """{path relative to Data: sha256} of every file a recorded install says it put there, loose files in subfolders
    included. The experiment and bridge records keep a hash per file; the port's deploy record lists its files and
    keeps size and hash per artifact name."""
    fl = (rec or {}).get("files")
    if isinstance(fl, dict):
        return {str(k): v for k, v in fl.items()}
    if isinstance(fl, list):
        arts = (rec or {}).get("artifacts") or {}
        out = {}
        for r in fl:
            a = arts.get(os.path.basename(str(r).replace("\\", "/"))) if isinstance(arts, dict) else None
            out[str(r)] = a.get("sha256") if isinstance(a, dict) else None
        return out
    return {}


def owned_problems(snap):
    """[problems]: files an install record in this snapshot owns that are missing now or no longer match the hash the
    record keeps. An equal record is no proof its files are still there."""
    out = []
    for comp, rec in (snap.get("records") or {}).items():
        if not rec:
            continue
        live = (snap.get("owned_live") or {}).get(comp)
        if live is None:
            out.append(f"{comp}: its installed files were not checked (snapshot without owned_live)")
            continue
        for rel, want in sorted(owned_expected(comp, rec).items()):
            have = live.get(rel)
            if have is None:
                out.append(f"{comp}: Data/{rel} is recorded as installed but missing")
            elif want is not None and have != want:
                out.append(f"{comp}: Data/{rel} changed since it was installed (not the recorded file)")
    return out


def record_identity(comp, rec):
    """What makes two installs of a component the same install: the files it owns and their hashes, plus its source
    folder and plugin list. Volatile fields (pending flags, saved Plugins.txt bytes) are left out."""
    if rec is None:
        return None
    if comp in EXP_KIT and rec.get("pack") and rec.get("source_inputs"):
        # a packed archive is rebuilt by Archive2 on every install; the staged inputs it was packed from identify it
        keep = {"source_inputs": rec.get("source_inputs"), "plugins": rec.get("plugins"), "pack": True}
    elif comp in BRIDGE_KIT and rec.get("source_sha256"):
        keep = {"source_sha256": rec.get("source_sha256"), "plugin": rec.get("plugin")}
    else:
        keep = {"files": rec.get("files"), "artifacts": rec.get("artifacts"), "plugins": rec.get("plugins"),
                "exp_dir": rec.get("exp_dir"), "dir": rec.get("dir"), "pack": rec.get("pack")}
    return hashlib.sha256(json.dumps(keep, sort_keys=True).encode()).hexdigest()


def owned_plugins(*snaps):
    """Every plugin name (casefolded) any recorded install in these snapshots owns."""
    names = set()
    for s in snaps:
        for comp, rec in (s.get("records") or {}).items():
            if not rec:
                continue
            fl = rec.get("files")
            cands = list(fl) if isinstance(fl, (dict, list)) else []
            cands += list(rec.get("plugins") or [])
            if rec.get("plugin"):
                cands.append(rec["plugin"])
            for a in rec.get("artifacts") or []:
                cands.append(a if isinstance(a, str) else a.get("name", "") if isinstance(a, dict) else "")
            if comp == "port":
                cands.append("FO4Port.esm")
            for c in cands:
                if isinstance(c, str) and c.lower().endswith((".esm", ".esp", ".esl")):
                    names.add(os.path.basename(c.replace("\\", "/")).casefold())
    return names


def owned_files(*snaps):
    """Casefolded top-level Data names an installer owns in any of these snapshots: its record file, the files and
    artifacts it lists, and its plugins."""
    names = {v[0].casefold() for v in COMPONENTS.values()} | owned_plugins(*snaps)
    for s in snaps:
        for rec in (s.get("records") or {}).values():
            fl = (rec or {}).get("files")
            if isinstance(fl, (dict, list)):
                names.update(os.path.basename(str(f).replace("\\", "/")).casefold() for f in fl)
            for a in (rec or {}).get("artifacts") or []:
                n = a.get("name") if isinstance(a, dict) else a
                if isinstance(n, str):
                    names.add(os.path.basename(n).casefold())
            for f in (rec or {}).get("published_files") or []:
                if isinstance(f, str):
                    names.add(os.path.basename(f.replace("\\", "/")).casefold())
    return names


def _differs(x, y):
    """Compare by content when both sides were hashed; otherwise by the size-and-time identity the snapshot took
    (Starfield's big archives are not hashed), so a same-length rewrite is still caught by its new time."""
    if x.get("sha256") and y.get("sha256"):
        return (x.get("size"), x["sha256"]) != (y.get("size"), y["sha256"])
    return (x.get("size"), x.get("mtime_ns")) != (y.get("size"), y.get("mtime_ns"))


def _lines(b64):
    if b64 is None:
        return []
    return base64.b64decode(b64).decode("utf-8-sig", errors="replace").splitlines()


def _name(line):
    v = line.strip()
    return (v[1:] if v.startswith("*") else v).casefold()


def install_argv(comp, rec, repo, starfield, port_staging=None):
    """The installer command that recreates a recorded install, or None when the record does not say where its
    source is (the port's deploy record keeps no staging path: pass --port-staging)."""
    script = os.path.join(repo, COMPONENTS[comp][1])
    if comp == "experiment":
        if not rec.get("exp_dir"):
            return None
        argv = [sys.executable, script, "install", "--exp-dir", rec["exp_dir"], "--starfield", starfield]
        if rec.get("plugins"):
            argv += ["--plugins", ",".join(rec["plugins"])]
        if rec.get("pack"):
            argv.append("--pack")
        return argv
    if comp == "planet_probe":            # exp_install's record; the tool re-reads plugins and --pack from plan.json
        return [sys.executable, script, "install", "--dir", rec["exp_dir"], "--starfield", starfield] \
            if rec.get("exp_dir") else None
    if comp in BRIDGE_KIT:
        return [sys.executable, script, "install", "--dir", rec["dir"], "--starfield", starfield] if rec.get("dir") else None
    return [sys.executable, script, "install", "--staging", port_staging, "--restore-stdin",
            "--starfield", starfield] if port_staging else None


def source_dir(comp, rec):
    """The staged folder a recorded install came from (None for the port, whose record names none)."""
    return (rec or {}).get("exp_dir" if comp in EXP_KIT else "dir") if comp != "port" else None


def stage_problems(target, change, notes, port_staging=None):
    """Read-only checks of inputs to be reinstalled, before any uninstall. Legacy experiment gaps go to notes.

    Pins refer to the target receipts, not the currently installed base that restore is about to replace. Installers
    still recheck their own inputs: this preflight does not lock stage folders against later concurrent edits.
    """
    problems = []

    def inventory(value):
        if not isinstance(value, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                              for k, v in value.items()):
            raise ValueError("source inventory must be a filename-to-sha256 mapping")
        normalized = {k.replace("\\", "/"): v for k, v in value.items()}
        if len(normalized) != len(value):
            raise ValueError("source inventory has duplicate normalized filenames")
        return normalized

    def staged_path(directory, relative):
        if not isinstance(relative, str) or not relative or any(
                p in ("", ".", "..") or ":" in p for p in relative.replace("\\", "/").split("/")):
            raise ValueError(f"invalid staged filename {relative!r}")
        root = os.path.realpath(directory)
        path = os.path.realpath(os.path.join(root, *relative.replace("\\", "/").split("/")))
        if os.path.commonpath((root, path)) != root or path == root:
            raise ValueError(f"staged filename leaves its source folder: {relative!r}")
        return path

    def unreadable(error):
        raise error

    for comp in INSTALL_ORDER:
        if change.get(comp) not in ("install", "replace", "recover"):
            continue
        if comp == "port":
            if port_staging:
                try:
                    port_restore.check_stage(port_staging, port_restore.snapshot_spec(target))
                except (OSError, ValueError, TypeError, KeyError) as error:
                    problems.append(f"port: recorded stage cannot be restored: {error}")
            continue
        rec = target["records"].get(comp) or {}
        directory = source_dir(comp, rec)
        if not directory or not os.path.isdir(directory):
            continue                                    # the existing install loop reports missing source folders
        key = "source_inputs" if comp in EXP_KIT else "source_sha256"
        try:
            if comp in EXP_KIT and rec.get(key) is None:
                notes.append(f"{comp}: snapshot has no source_inputs; staged contents cannot be preflighted")
            else:
                wanted = inventory(rec.get(key))
                plugins = rec.get("plugins") if comp in EXP_KIT else [rec.get("plugin")]
                if not isinstance(plugins, list) or not plugins:
                    raise ValueError("record names no staged plugins")
                have = {}
                for name in plugins:
                    path = staged_path(directory, name)
                    have[("plugin/" if comp in EXP_KIT else "") + name.replace("\\", "/")] = files.sha256(path)
                data = staged_path(directory, "Data")
                if os.path.lexists(data):                 # a plugin-only stage need not have a Data tree
                    for root, dirs, names in os.walk(data, onerror=unreadable):
                        dirs.sort()
                        for name in sorted(names):
                            relative = os.path.relpath(os.path.join(root, name), directory).replace("\\", "/")
                            have[relative] = files.sha256(staged_path(directory, relative))
                for name in sorted(set(wanted) | set(have)):
                    if wanted.get(name) != have.get(name):
                        why = "missing" if name not in have else "unrecorded" if name not in wanted else "changed"
                        problems.append(f"{comp}: staged {name} {why} since the snapshot; restore refused")
        except (OSError, ValueError, TypeError) as error:
            problems.append(f"{comp}: staged inputs cannot be checked: {error}")

        pin_file = "core.json" if comp == "markers" else "plan.json" if comp == "quest_probe" else None
        if pin_file is None:
            continue                                    # combined probe's installer enforces no base hash
        try:
            pin = files.load_json(staged_path(directory, pin_file))
            if comp == "markers":
                masters = pin["masters"]
                if not isinstance(masters, dict) or not masters:
                    raise ValueError("masters must be a nonempty filename-to-sha256 mapping")
                base = (target["records"].get("experiment") or {}).get("files") or {}
                base = {k.casefold(): v for k, v in base.items()}
                for name, digest in masters.items():
                    if not isinstance(name, str) or not isinstance(digest, str) or not digest:
                        raise ValueError("masters must name a file and sha256")
                    have = base.get(name.casefold())
                    if not have or have != digest:
                        problems.append(f"markers: core.json pin for {name} differs from the target experiment "
                                        "or its target master is missing")
            else:
                pins = pin["checked_against_sha256"]
                wanted = {k.casefold(): v for k, v in pins.items()}.get("fo4port.esm")
                artifacts = (target["records"].get("port") or {}).get("artifacts") or {}
                artifact = {k.casefold(): v for k, v in artifacts.items()}.get("fo4port.esm") or {}
                have = artifact.get("sha256")
                if not isinstance(wanted, str) or not wanted or not have or wanted != have:
                    problems.append("quest_probe: plan.json pin for FO4Port.esm differs from the target port "
                                    "or its target artifact is missing")
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            problems.append(f"{comp}: {pin_file} cannot be checked: {error}")
    return problems


def order_step(repo, starfield):
    return {"what": "order experiment plugins",
            "argv": [sys.executable, os.path.join(repo, COMPONENTS["experiment"][1]), "order", "--starfield", starfield]}


def plan(target, current, repo, port_staging=None):
    """{"steps": [{"what", "argv"}], "plugins_txt": "same" | "restore" | "conflict", "conflicts": [...],
    "notes": [...]}: what apply would do to turn `current` into `target`."""
    try:
        target_pt = _plugins_txt_path(target.get("plugins_txt"))
        current_pt = _plugins_txt_path(current.get("plugins_txt"))
        if os.path.realpath(target_pt) != os.path.realpath(current_pt):
            raise RestoreRefused("Plugins.txt snapshots address different installer namespaces")
    except RestoreRefused as error:
        return {"steps": [], "plugins_txt": "conflict", "conflicts": [str(error)], "notes": []}
    starfield = target["starfield"]
    steps, conflicts, notes = [], [], []
    # a snapshot taken before restore knew a component has no key for it: without its record file in Data then, it
    # was not installed; with one, what was installed is unknown and nothing can be planned for it
    taken = {n.casefold() for n in target.get("data_top") or {}}
    unknown = [c for c, (rec_name, _s) in COMPONENTS.items()
               if c not in target["records"] and rec_name.casefold() in taken]
    if unknown:
        return {"steps": [], "plugins_txt": "conflict", "notes": [],
                "conflicts": [f"snapshot: taken before restore knew {c} ({COMPONENTS[c][0]} was in Data, its record "
                              "was not kept); take a new snapshot" for c in unknown]}
    target = dict(target, records={c: target["records"].get(c) for c in COMPONENTS})
    change = {}
    for comp in COMPONENTS:
        t, c = target["records"].get(comp), current["records"].get(comp)
        ti, ci = record_identity(comp, t), record_identity(comp, c)
        if ti == ci:
            # an interrupted install (not complete, or cleanup left pending): its own uninstall recovers it. A complete
            # install keeps plugins_restore_pending set on purpose (it owns the later uninstall's Plugins.txt
            # restoration), so that flag alone is a healthy install, not a recovery case
            if c is not None and (c.get("complete") is False or c.get("cleanup_pending")):
                change[comp] = "recover"
            continue
        change[comp] = "uninstall" if t is None else ("install" if c is None else "replace")
    for rider, base in RIDES_ON.items():
        # a rider's installer pins its base's build: off before the base changes, back on after it (module doc). A
        # rider not in `change` is the same install on both sides (any difference was caught above), or on neither
        if base in change and rider not in change and current["records"].get(rider) is not None:
            change[rider] = "replace"
            notes.append(f"{rider}: taken off and put back around the {base} change (its installer pins the "
                         f"installed {base})")
    conflicts.extend(stage_problems(target, change, notes, port_staging))
    for comp in UNINSTALL_ORDER:
        if change.get(comp) in ("uninstall", "replace", "recover"):
            steps.append({"what": f"uninstall {comp}",
                          "argv": [sys.executable, os.path.join(repo, COMPONENTS[comp][1]), "uninstall",
                                   "--starfield", starfield]})
    # A recorded port pins the target's installed core, so that core must be back before the port is replayed.
    install_order = ("experiment", "port") + INSTALL_ORDER[2:]
    for comp in install_order:
        if change.get(comp) in ("install", "replace", "recover"):
            argv = install_argv(comp, target["records"][comp], repo, starfield, port_staging)
            if argv is None:
                conflicts.append(f"{comp}: the snapshot had it installed but its record names no source folder"
                                 + (" (pass --port-staging)" if comp == "port" else ""))
            elif comp != "port" and not os.path.isdir(source_dir(comp, target["records"][comp])):
                conflicts.append(f"{comp}: source folder {source_dir(comp, target['records'][comp])} is gone")
            else:
                step = {"what": f"install {comp}", "argv": argv}
                if comp == "port":
                    try:
                        step["input"] = json.dumps(port_restore.snapshot_spec(target))
                    except (TypeError, KeyError, ValueError) as error:
                        conflicts.append(f"port: invalid recorded target: {error}")
                steps.append(step)
                # exp_install.py order refuses a plugin whose master is not active, and an experiment plugin can master
                # FO4Port.esm (a slice door plugin): when the port goes back on too, order runs after it. install itself
                # checks no masters, so the core still goes on before the port for the port's core pin
                if comp == "experiment" and change.get("port") not in ("install", "replace", "recover"):
                    steps.append(order_step(repo, starfield))
                elif comp == "port" and change.get("experiment") in ("install", "replace", "recover"):
                    steps.append(order_step(repo, starfield))
    # files an installer owns must still be the files it recorded; a changed or missing one is refused, not repaired.
    # The same holds for the target: a snapshot taken while an owned file was changed or missing is not a state the
    # installers can give back, so restoring to it would report success on different bytes
    for problem in owned_problems(target):
        conflicts.append("snapshot: " + problem + "; take a new snapshot once that component is installed cleanly")
    for problem in owned_problems(current):
        conflicts.append(problem + "; uninstall or reinstall that component by hand first")
    # Plugins.txt: the installers put their own lines back; what is left must be ours alone to rewrite
    owned = owned_plugins(target, current)
    tl, cl = _lines(target["plugins_txt_b64"]), _lines(current["plugins_txt_b64"])
    if target["plugins_txt_sha256"] == current["plugins_txt_sha256"] and not steps:
        pt = "same"
    else:
        foreign_t = [l for l in tl if _name(l) and _name(l) not in owned]
        foreign_c = [l for l in cl if _name(l) and _name(l) not in owned]
        if foreign_t != foreign_c:
            pt = "conflict"
            conflicts.append("Plugins.txt: lines that no installer owns differ (an edit of the owner's; kept): "
                             + json.dumps({"snapshot": [l for l in foreign_t if l not in foreign_c],
                                           "now": [l for l in foreign_c if l not in foreign_t]}))
        else:
            pt = "restore"
    # Data files that appeared and nobody owns, or vanished
    tt, ct = target["data_top"], current["data_top"]
    mine = owned_files(target, current)
    for n in sorted(set(ct) - set(tt)):
        if n.casefold() not in mine:
            notes.append(f"Data/{n}: not in the snapshot and no installer owns it; left alone")
    for n in sorted(set(tt) - set(ct)):
        if n.casefold() not in mine:
            conflicts.append(f"Data/{n}: in the snapshot, gone now, and no installer can bring it back")
    for n in sorted(set(tt) & set(ct)):
        if n.casefold() not in mine and _differs(tt[n], ct[n]):
            conflicts.append(f"Data/{n}: changed since the snapshot and no installer owns it")
    for w, h in (target.get("watched") or {}).items():
        if (current.get("watched") or {}).get(w, h) != h:
            notes.append(f"{w}: changed since the snapshot (watched only; restore does not write it)")
    return {"steps": steps, "plugins_txt": pt, "conflicts": conflicts, "notes": notes}


def verify(target, after):
    """[differences] between a target snapshot and the state after apply (empty: restored)."""
    try:
        target_pt = _plugins_txt_path(target.get("plugins_txt"))
        after_pt = _plugins_txt_path(after.get("plugins_txt"))
        if os.path.realpath(target_pt) != os.path.realpath(after_pt):
            raise RestoreRefused("Plugins.txt snapshots address different installer namespaces")
    except RestoreRefused as error:
        return [str(error)]
    diffs = []
    if target["plugins_txt_sha256"] != after["plugins_txt_sha256"]:
        diffs.append("Plugins.txt bytes differ")
    for comp in COMPONENTS:
        if record_identity(comp, target["records"].get(comp)) != record_identity(comp, after["records"].get(comp)):
            diffs.append(f"{comp} install differs")
    diffs += ["snapshot: " + p for p in owned_problems(target)]
    diffs += owned_problems(after)               # and the files those records own are really there, unchanged
    # an owned file the record keeps no hash for is checked against the bytes the snapshot saw; a hashed one is
    # already held to its record on both sides (a packed archive is rebuilt with a new hash on every install)
    tl, al = target.get("owned_live") or {}, after.get("owned_live") or {}
    for comp in COMPONENTS:
        te = owned_expected(comp, target["records"].get(comp))
        ae = owned_expected(comp, after["records"].get(comp))
        x, y = tl.get(comp) or {}, al.get(comp) or {}
        for rel in sorted(r for r in set(te) & set(ae) if te[r] is None and ae[r] is None):
            if x.get(rel) != y.get(rel):
                diffs.append(f"{comp}: Data/{rel} differs from the snapshot")
    tt, at = target["data_top"], after["data_top"]
    mine = owned_files(target, after)            # installer-owned files are compared through their records above
    for n in sorted(set(tt) | set(at)):
        if n.casefold() in mine:
            continue
        x, y = tt.get(n), at.get(n)
        if (x is None) != (y is None) or (x and y and _differs(x, y)):
            diffs.append(f"Data/{n} differs")
    return diffs


def game_running():
    """True while Starfield.exe runs (Windows tasklist); False elsewhere."""
    if os.name != "nt":
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Starfield.exe", "/NH"], capture_output=True,
                             text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return True                                   # unknown is treated as running
    return "starfield.exe" in out.casefold()


def write_plugins_txt(path, target_b64, expected_sha256):
    """Guarded rewrite: refuses if Plugins.txt changed after the plan was made. A write that fails (a read-only
    Plugins.txt, or one another program holds open, on Windows) leaves Plugins.txt as it was and removes the temp file,
    then raises."""
    path = _plugins_txt_path(path)
    cur = _read(path)
    if (None if cur is None else hashlib.sha256(cur).hexdigest()) != expected_sha256:
        raise RestoreRefused("Plugins.txt changed while restoring; nothing written")
    if target_b64 is None:
        if cur is not None:
            os.remove(path)
        return
    tmp = f"{path}.fo4sf-restore.tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(base64.b64decode(target_b64))
            f.flush()
            os.fsync(f.fileno())                          # on disk before it takes the name (a power cut)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def apply(target, repo, *, port_staging=None, running=game_running, run=subprocess.run, echo=print, watch=()):
    """Bring the install back to `target`. Returns the list of remaining differences (empty: restored). Raises
    RestoreRefused before touching anything when the game runs or the plan has conflicts."""
    target = dict(target, plugins_txt=_plugins_txt_path(target.get("plugins_txt")))
    if running():
        raise RestoreRefused("Starfield is running (or its state is unknown); close it first")
    current = take(target["starfield"], target["plugins_txt"], watch or tuple(target.get("watched") or ()))
    p = plan(target, current, repo, port_staging)
    if p["conflicts"]:
        raise RestoreRefused("conflicts, nothing changed:\n  " + "\n  ".join(p["conflicts"]))
    env = dict(os.environ)
    env["LOCALAPPDATA"] = os.path.dirname(os.path.dirname(target["plugins_txt"]))
    for st in p["steps"]:
        echo(f"  {st['what']}: {' '.join(st['argv'][1:])}")
        extra = {"input": st["input"], "text": True} if "input" in st else {}
        r = run(st["argv"], cwd=repo, env=env, **extra)
        if r.returncode != 0:
            raise RestoreRefused(f"{st['what']} failed (exit {r.returncode}); the installers' own records hold the "
                                 "partial state, rerun restore after fixing it")
    mid = take(target["starfield"], target["plugins_txt"], tuple(target.get("watched") or ()))
    if mid["plugins_txt_sha256"] != target["plugins_txt_sha256"]:
        again = plan(target, mid, repo, port_staging)
        if again["plugins_txt"] == "conflict":
            raise RestoreRefused("after the installers ran, Plugins.txt has lines no installer owns that differ; kept")
        write_plugins_txt(target["plugins_txt"], target["plugins_txt_b64"], mid["plugins_txt_sha256"])
        echo("  Plugins.txt: restored byte for byte")
    after = take(target["starfield"], target["plugins_txt"], tuple(target.get("watched") or ()))
    return verify(target, after)
