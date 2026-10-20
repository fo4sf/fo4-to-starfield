"""Recorded restore: return Starfield's Data folder and Plugins.txt to a recorded state.

This formalises what the install thread's swap scripts do by hand (bridge uninstall, experiment uninstall, experiment
install, order, bridge install; the port deployment kept or swapped) on top of the three existing installers, which
own every file they add and record it:

    FO4Port.deploy.json        scripts/deploy_starfield.py      (the converted port, FO4Port.esm and its archives)
    FO4SFExp.install.json      scripts/game/exp_install.py      (one experiment: the terrain core, mission, ...)
    FO4SFBridge.install.json   scripts/game/bridge_install.py   (the observation bridge)

snapshot  records Plugins.txt (bytes), every top-level file in Data that is a plugin or an archive (name, size, time;
          plugins hashed), the three install records (verbatim), the live hash of every file those records own
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

from . import files

SCHEMA = 1
# component -> (record file in Data, installer script under the repo, plugin names the component may own)
COMPONENTS = {
    "port": ("FO4Port.deploy.json", os.path.join("scripts", "deploy_starfield.py")),
    "experiment": ("FO4SFExp.install.json", os.path.join("scripts", "game", "exp_install.py")),
    "bridge": ("FO4SFBridge.install.json", os.path.join("scripts", "game", "bridge_install.py")),
}
UNINSTALL_ORDER = ("bridge", "experiment", "port")       # the swap scripts: bridge first off, last on
INSTALL_ORDER = ("port", "experiment", "bridge")
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
    if comp == "experiment" and rec.get("pack") and rec.get("source_inputs"):
        # a packed archive is rebuilt by Archive2 on every install; the staged inputs it was packed from identify it
        keep = {"source_inputs": rec.get("source_inputs"), "plugins": rec.get("plugins"), "pack": True}
    elif comp == "bridge" and rec.get("source_sha256"):
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
    if comp == "bridge":
        return [sys.executable, script, "install", "--dir", rec["dir"], "--starfield", starfield] if rec.get("dir") else None
    return [sys.executable, script, "install", "--staging", port_staging, "--starfield", starfield] if port_staging else None


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
    for comp in UNINSTALL_ORDER:
        if change.get(comp) in ("uninstall", "replace", "recover"):
            steps.append({"what": f"uninstall {comp}",
                          "argv": [sys.executable, os.path.join(repo, COMPONENTS[comp][1]), "uninstall",
                                   "--starfield", starfield]})
    for comp in INSTALL_ORDER:
        if change.get(comp) in ("install", "replace", "recover"):
            argv = install_argv(comp, target["records"][comp], repo, starfield, port_staging)
            if argv is None:
                conflicts.append(f"{comp}: the snapshot had it installed but its record names no source folder"
                                 + (" (pass --port-staging)" if comp == "port" else ""))
            elif comp == "experiment" and not os.path.isdir(target["records"][comp]["exp_dir"]):
                conflicts.append(f"experiment: source folder {target['records'][comp]['exp_dir']} is gone")
            else:
                steps.append({"what": f"install {comp}", "argv": argv})
                if comp == "experiment":
                    steps.append({"what": "order experiment plugins",
                                  "argv": [sys.executable, os.path.join(repo, COMPONENTS["experiment"][1]), "order",
                                           "--starfield", starfield]})
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
    """Guarded rewrite: refuses if Plugins.txt changed after the plan was made."""
    path = _plugins_txt_path(path)
    cur = _read(path)
    if (None if cur is None else hashlib.sha256(cur).hexdigest()) != expected_sha256:
        raise RestoreRefused("Plugins.txt changed while restoring; nothing written")
    if target_b64 is None:
        if cur is not None:
            os.remove(path)
        return
    tmp = f"{path}.fo4sf-restore.tmp"
    with open(tmp, "wb") as f:
        f.write(base64.b64decode(target_b64))
    os.replace(tmp, path)


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
        r = run(st["argv"], cwd=repo, env=env)
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
