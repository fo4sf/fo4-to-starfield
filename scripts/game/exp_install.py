"""Install / uninstall a staged in-game experiment (a plugin plus loose files) next to the converted build, reversibly.

usage: python exp_install.py install|uninstall|status --exp-dir <staged dir> --starfield <game dir>
                             [--pack] [--needs door_trip,door_check,plugin_order]
       python exp_install.py order --starfield <game dir>

The staged dir holds one or more <name>.esm files (only those listed with --plugins are activated, default: the first
one alphabetically) and a Data\\ tree of loose files (e.g. Data\\Terrain\\*.btd). install refuses to overwrite any existing
file, records everything it adds in Data\\FO4SFExp.install.json, and appends "*<plugin>" to Plugins.txt. uninstall removes
exactly what the record lists (files unchanged since install only) and only the Plugins.txt lines it added; it never
touches FO4Port's own deployment (deploy_starfield.py).

--pack builds one stored General archive, including terrain overlay masks, outside the staged input folder.
This matches Claude's current terrain packing policy; runtime terrain acceptance is a separate game test.
Plugin-only experiments need no archive. --needs refuses queues this runner cannot execute before installing.
order moves every selected experiment plugin after its active masters immediately before launch, using a guarded
Plugins.txt rewrite. It refuses missing/disabled masters, cycles, changed plugins and incomplete installs.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
from itertools import islice
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

# Reuse the converter deployer's tested atomic writes and no-overwrite publication.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deploy_starfield as deployment  # noqa: E402
from verify_packed_experiment import verify_archive  # noqa: E402

RECORD = "FO4SFExp.install.json"
PACKING_POLICY = "general-stored-verified-v2"
_UNSET = object()


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
        if len(data) != size:
            raise ValueError(f"{path}: truncated TES4 header")
    out, pos = [], 0
    big = None                                            # XXXX: the next subrecord's real size (u32)
    while pos < len(data):
        if pos + 6 > len(data):
            raise ValueError(f"{path}: truncated TES4 subrecord header")
        typ = data[pos:pos + 4]
        n = struct.unpack_from("<H", data, pos + 4)[0]
        if typ == b"XXXX":
            if n != 4 or pos + 10 > len(data) or big is not None:
                raise ValueError(f"{path}: malformed extended subrecord size")
            big = struct.unpack_from("<I", data, pos + 6)[0]
            pos += 6 + n
            continue
        if big is not None:
            n, big = big, None
        if pos + 6 + n > len(data):
            raise ValueError(f"{path}: truncated TES4 subrecord")
        if typ == b"MAST":
            value = data[pos + 6:pos + 6 + n]
            if not value or not value.endswith(b"\0") or not value[:-1] or b"\0" in value[:-1]:
                raise ValueError(f"{path}: malformed master name")
            try:
                out.append(value[:-1].decode("utf-8"))
            except UnicodeDecodeError as error:
                raise ValueError(f"{path}: invalid master name encoding") from error
        pos += 6 + n
    if big is not None:
        raise ValueError(f"{path}: extended size without a subrecord")
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
    for p in plugins:
        at = [k for k, ln in enumerate(out) if name(ln) == p.casefold()]
        if len(at) != 1 or not out[at[0]].strip().startswith("*"):
            raise ValueError(f"experiment plugin is missing, inactive or duplicated: {p}")
        for m in masters.get(p, []):
            idx = [k for k, ln in enumerate(out) if name(ln) == m.casefold()]
            if len(idx) > 1:
                raise ValueError(f"master has duplicate Plugins.txt entries: {m}")
            if (idx and not out[idx[0]].strip().startswith("*")) or (not idx and not implicit(m)):
                if (p, m) not in missing:
                    missing.append((p, m))
    if missing:
        return list(lines), [], missing
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
    # Bounded passes cannot satisfy cyclic or self dependencies. Never publish a partial ordering.
    positions = {name(ln): k for k, ln in enumerate(out)}
    for p in plugins:
        for m in masters.get(p, []):
            if m.casefold() in positions and positions[m.casefold()] >= positions[p.casefold()]:
                raise ValueError(f"cyclic or unsatisfied plugin order: {p} needs {m} before it")
    return out, moved, missing


def order(a):
    """Plugins.txt: the plugins this install activated after their masters (module doc). 0 ok, 6 a master missing."""
    data = os.path.join(a.starfield, "Data")
    rec_p = os.path.join(data, RECORD)
    if not os.path.exists(rec_p):
        print("nothing installed: no order to fix")
        return 0
    try:
        require_complete_master(data)
        rec = read_json(rec_p)
        if not rec.get("complete", True) or rec.get("cleanup_pending"):
            raise ValueError("incomplete experiment install; finish recovery before ordering")
        # New receipts track selected plugins even when their lines existed before this install.
        plugins = rec.get("plugins")
        if plugins is None:
            plugins = [x.lstrip("*").strip() for x in rec.get("plugins_added", [])]
            plugins += [x["active"].lstrip("*").strip() for x in rec.get("plugins_replaced", [])]
        masters = {}
        for p in plugins:
            f = data_path(data, p)
            if p in rec["files"] and digest(f) != rec["files"][p]:
                raise ValueError(f"experiment plugin changed since installation: {p}")
            masters[p] = plugin_masters(f)
        p_txt = plugins_txt()
        recorded = rec.get("plugins_txt", p_txt)
        if os.path.normcase(os.path.abspath(recorded)) != os.path.normcase(os.path.abspath(p_txt)):
            raise ValueError("recorded Plugins.txt does not match the current user path")
        original = read_bytes(p_txt)
        lines, bom, nl = plugin_lines(original)
        new, moved, missing = order_lines(lines, plugins, masters)
        if missing:
            raise ValueError("; ".join(f"{p} needs active master {m}" for p, m in missing))
        if new != lines:
            write_plugins(p_txt, new, bom, nl, original)
            print(f"moved after their masters: {', '.join(moved)}")
        else:
            print("order ok: every installed plugin loads after its masters")
    except (OSError, ValueError) as error:
        print(f"not ordered: {error}")
        return 6
    return 0


def active(a):
    """Read-only: is every plugin this install activated still active ("*") in Plugins.txt? 0 yes or nothing installed,
    8 no. Starfield itself can deactivate them while running (2026-10-13: answering "Save" to its "different Creations
    Load Order" dialog after Continue rewrote Plugins.txt with every experiment plugin inactive; coc then froze)."""
    rec_p = os.path.join(a.starfield, "Data", RECORD)
    if not os.path.exists(rec_p):
        print("nothing installed")
        return 0
    rec = read_json(rec_p)
    plugins = rec.get("plugins")
    if plugins is None:
        plugins = [x.lstrip("*").strip() for x in rec.get("plugins_added", [])]
        plugins += [x["active"].lstrip("*").strip() for x in rec.get("plugins_replaced", [])]
    lines, _, _ = read_plugins(plugins_txt())
    on = {ln.strip()[1:].strip().casefold() for ln in lines if ln.strip().startswith("*")}
    off = [p for p in plugins if p.casefold() not in on]
    if off:
        print(f"inactive in Plugins.txt: {', '.join(off)}")
        return 8
    print(f"active: {', '.join(plugins)}")
    return 0


def read_json(p):
    with open(p) as f:
        return json.load(f)


def require_complete_master(data):
    """Never mutate activation bytes needed by an interrupted main-build recovery."""
    manifest = os.path.join(data, deployment.MANIFEST)
    if os.path.exists(manifest):
        state = read_json(manifest)
        if state.get("complete") is not True or state.get("cleanup_pending"):
            raise ValueError("incomplete FO4Port deployment; finish its recovery before changing experiments")


def plugins_txt():
    local = os.environ.get("LOCALAPPDATA", "")
    if not local or not os.path.isabs(local):
        sys.exit("LOCALAPPDATA must identify an absolute Starfield user profile directory")
    return os.path.join(local, "Starfield", "Plugins.txt")


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
    content = (bom + (nl.join(lines) + nl).encode("utf-8") if expected_current is _UNSET
               else deployment.render_lines(lines, expected_current))
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


def _verify_workers(workers):
    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= 4:
        raise ValueError('verification workers must be an integer between 1 and 4')
    return workers


def _hash_files(files, *, workers=1):
    """Hash every named file afresh, serial by default; up to four readers/32 queued paths.

    No inode, timestamp or cross-call digest cache: even hard-linked aliases are
    checked against their recorded contents. Ordered results keep reports stable.
    """
    def hash_one(item):
        name, path = item
        return name, digest(path)

    workers = _verify_workers(workers)
    if workers == 1:
        for item in files:
            yield hash_one(item)
        return
    files = iter(files)
    batch = list(islice(files, 32))
    if len(batch) <= 1:
        for item in batch:
            yield hash_one(item)
        return
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="fo4sf-verify") as pool:
        while batch:
            yield from pool.map(hash_one, batch)
            batch = list(islice(files, 32))


def source_inventory(exp_dir, plugins, *, workers=1):
    """Pin staged inputs, including loose inputs used to build a packed archive."""
    workers = _verify_workers(workers)
    inputs = {"plugin/" + name: digest(os.path.join(exp_dir, name)) for name in plugins}
    data = os.path.join(exp_dir, "Data")
    def loose_files():
        for root, dirs, files in os.walk(data):
            dirs.sort()
            for name in sorted(files):
                path = os.path.join(root, name)
                relative = os.path.relpath(path, data).replace("\\", "/")
                yield "Data/" + relative, path
    inputs.update(_hash_files(loose_files(), workers=workers))
    return inputs


def plan_activation(lines, plugins):
    updated, added, replaced = list(lines), [], []
    for name in plugins:
        matches = [(i, line) for i, line in enumerate(updated)
                   if line.strip().lstrip("*").casefold() == name.casefold()]
        if len(matches) > 1:
            raise ValueError(f"duplicate plugin entries in Plugins.txt: {name}")
        if matches:
            index, original = matches[0]
            if original.strip().startswith("*"):
                continue
            active = "*" + original.strip()
            updated[index] = active
            replaced.append({"active": active, "original": original})
        else:
            active = "*" + name
            updated.append(active)
            added.append(active)
    return updated, added, replaced


def verify_relaunch(a, data, plugins, packed, rec):
    workers = _verify_workers(getattr(a, 'verify_workers', 1))
    if packed and rec.get("packing_policy") != PACKING_POLICY:
        sys.exit("experiment packing policy changed or is unknown; uninstall before relaunching")
    active = {line.strip()[1:].casefold() for line in read_plugins(plugins_txt())[0]
              if line.strip().startswith("*")}
    if any(name.casefold() not in active for name in plugins):
        sys.exit("experiment plugin is inactive; recover the installation before relaunching")
    if packed and os.path.splitext(plugins[0])[0] + " - Main.ba2" not in rec["files"]:
        sys.exit("packed experiment archive is not recorded; uninstall before relaunching")
    def installed_files():
        for relative in rec["files"]:
            target = data_path(data, relative)
            if not os.path.isfile(target):
                sys.exit(f"installed experiment file is missing or changed: {relative}")
            yield relative, target
    for relative, identity in _hash_files(installed_files(), workers=workers):
        if identity != rec["files"][relative]:
            sys.exit(f"installed experiment file is missing or changed: {relative}")
    if rec.get("source_inputs") is None:
        sys.exit("legacy experiment input identity is unavailable; uninstall before relaunching")
    if source_inventory(a.exp_dir, plugins, workers=workers) != rec["source_inputs"]:
        sys.exit("experiment source inputs changed; uninstall before relaunching")


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
                rec["plugins_replaced"] = []
        elif (rec["plugins_added"] or rec.get("plugins_replaced")) and os.path.exists(p):
            original = read_bytes(p)
            lines, bom, nl = plugin_lines(original)
            added = {x.casefold() for x in rec["plugins_added"]}
            replaced = {item["active"].casefold(): item["original"] for item in rec.get("plugins_replaced", [])}
            restored = [replaced.get(ln.strip().casefold(), ln) for ln in lines
                        if ln.strip().casefold() not in added]
            write_plugins(p, restored, bom, nl, original)
            rec["plugins_added"] = []
            rec["plugins_replaced"] = []
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
    if any(os.path.isfile(os.path.join(root, name)) for name in os.listdir(root)):
        sys.exit("cannot pack root-level Data files; place resources in supported subfolders")
    folders = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    if not folders:
        sys.exit(f"nothing to pack under {root}")
    # Vanilla terrain BTDs/masks use stored General entries. Do not apply the ordinary mesh archive compression.
    deployment.build_archive(argparse.Namespace(starfield=a.starfield, staging=root), out, folders, "General",
                             compression="None")
    return out


def install(a):
    if getattr(a, "pack", False):
        with tempfile.TemporaryDirectory(prefix="fo4sf-exp-pack-") as packing_dir:
            return _install(a, packing_dir)
    return _install(a)


def _install(a, packing_dir=None):
    data = os.path.abspath(os.path.join(a.starfield, "Data"))
    rec_p = os.path.join(data, RECORD)
    try:
        require_complete_master(data)
    except (OSError, ValueError) as error:
        sys.exit(f"experiment not installed: {error}")
    plugins = [p.strip() for p in a.plugins.split(",") if p.strip()] if a.plugins else \
        sorted(f for f in os.listdir(a.exp_dir) if f.lower().endswith(".esm"))[:1]
    requested_pack = bool(getattr(a, "pack", False))
    if requested_pack and not plugins:
        sys.exit("packing requires at least one experiment plugin")
    files = staged_files(a.exp_dir, plugins)
    packed = requested_pack and any(rel not in plugins for _, rel in files)
    if os.path.exists(rec_p):
        with open(rec_p) as f:
            rec = json.load(f)
        if not rec.get("complete", True) or rec.get("cleanup_pending"):
            sys.exit(f"incomplete experiment install ({rec_p}); uninstall it first")
        same = os.path.normcase(rec.get("exp_dir", "")) == os.path.normcase(os.path.abspath(a.exp_dir)) and \
            all(p in rec["files"] for p in plugins)
        if same:                                          # a relaunch of the same experiment: nothing to do
            if bool(rec.get("pack", False)) != requested_pack:
                sys.exit("experiment packing mode changed; uninstall it before changing modes")
            verify_relaunch(a, data, plugins, packed, rec)
            print("already installed")
            return
        sys.exit(f"another experiment is installed ({rec_p}); uninstall it first")
    names = [rel for _, rel in files]
    if packed:
        # Starfield reads no loose files here (Starfield.ini sResourceDataDirsFinal=STRINGS\ only; terrain experiment 1,
        # 2026-10-11, got procedural planet ground because its loose BTDs were never seen). A plugin's own
        # "<name> - Main.ba2" loads with it, so the staged Data tree goes into that archive instead.
        ba2 = os.path.splitext(plugins[0])[0] + " - Main.ba2"
        files = [(s, r) for s, r in files if r in plugins]
        names = [rel for _, rel in files] + [ba2]
    targets = {rel: data_path(data, rel) for rel in names}
    destinations = [os.path.normcase(targets[rel]) for rel in names]
    if len(destinations) != len(set(destinations)):
        sys.exit("duplicate experiment destination paths; nothing installed")
    clash = [rel for rel in names if os.path.exists(targets[rel])]
    if clash:
        sys.exit(f"refusing to overwrite existing game files: {clash}")
    # Validate all sources and snapshot activation before publishing anything.
    inputs = source_inventory(a.exp_dir, plugins)
    plugin_sources = {os.path.abspath(os.path.join(a.exp_dir, name)): name for name in plugins}
    identities = {}
    selected = set()
    for src, relative in files:
        plugin = plugin_sources.get(os.path.abspath(src))
        key = "plugin/" + plugin if plugin is not None else "Data/" + relative.replace("\\", "/")
        selected.add(key)
    if not selected.issubset(inputs) or (not packed and selected != set(inputs)):
        sys.exit("experiment file inventory changed during preparation; nothing installed")
    for src, relative in files:
        plugin = plugin_sources.get(os.path.abspath(src))
        key = "plugin/" + plugin if plugin is not None else "Data/" + relative.replace("\\", "/")
        identities[relative] = inputs[key]
    if packed:
        built = build_ba2(a, os.path.join(a.exp_dir, "Data"), os.path.join(packing_dir, ba2))
        files.append((built, ba2))
        identities[ba2] = digest(built)
    if source_inventory(a.exp_dir, plugins) != inputs:
        sys.exit("experiment source inputs changed during preparation; nothing installed")
    if packed:
        try:
            verify_archive(built, inputs)
        except (OSError, ValueError) as error:
            sys.exit(f"experiment archive validation failed; nothing installed: {error}")
    p = plugins_txt()
    original = read_bytes(p)
    lines, bom, nl = plugin_lines(original)
    lines, added, replaced = plan_activation(lines, plugins)
    rec = {"exp_dir": os.path.abspath(a.exp_dir), "files": {}, "dirs": [], "plugins_added": added,
           "plugins_replaced": replaced, "source_inputs": inputs,
           "complete": False, "pack": requested_pack, "plugins": plugins,
           "packing_policy": PACKING_POLICY if packed else None,
           "published_files": [], "plugins_txt": p,
           "plugins_original": base64.b64encode(original).decode("ascii") if original is not None else None,
           "plugins_restore_pending": False}
    activated = deployment.render_lines(lines, original)
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
            try:
                deployment.copy_new_artifact(src, dst, expected_sha256=identities[rel])
            except FileExistsError:
                if rel not in rec["published_files"]:
                    # Exclusive creation proves this call did not publish the destination.
                    rec["files"].pop(rel, None)
                    deployment.write_manifest(rec_p, rec)
                raise
            rec["published_files"].append(rel)
            deployment.write_manifest(rec_p, rec)
            if digest(dst) != identities[rel]:
                raise OSError(f"installed file differs from validated source: {rel}")
        if rec["plugins_added"] or rec["plugins_replaced"]:
            if read_bytes(p) != original:
                raise OSError("Plugins.txt changed during install; preserving concurrent edits")
            rec["plugins_restore_pending"] = True
            deployment.write_manifest(rec_p, rec)
            try:
                write_plugins(p, lines, bom, nl, original)
            except deployment.ConcurrentUpdateError:
                # This typed failure proves the original configuration was never replaced.
                rec["plugins_restore_pending"] = False
                rec["plugins_added"] = []
                rec["plugins_replaced"] = []
                deployment.write_manifest(rec_p, rec)
                raise
        rec["complete"] = True
        deployment.write_manifest(rec_p, rec)
    except Exception as e:
        rec["complete"] = False
        try:
            cleanup(data, rec_p, rec)
        except (OSError, ValueError) as recovery:
            sys.exit(f"install failed: {e}; {recovery}")
        sys.exit(f"install failed and was rolled back: {e}")
    print(f"installed {len(rec['files'])} files, plugins {plugins}")


def uninstall(a):
    data = os.path.join(a.starfield, "Data")
    rec_p = os.path.join(data, RECORD)
    if not os.path.exists(rec_p):
        print("nothing installed")
        return
    try:
        require_complete_master(data)
    except (OSError, ValueError) as error:
        sys.exit(f"experiment not uninstalled: {error}")
    with open(rec_p) as f:
        rec = json.load(f)
    try:
        rec["cleanup_pending"] = True
        deployment.write_manifest(rec_p, rec)
        cleanup(data, rec_p, rec)
    except (OSError, ValueError) as e:
        sys.exit(f"uninstall incomplete: {e}")
    print("uninstalled")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("install", "uninstall", "status", "order", "active"))
    ap.add_argument("--exp-dir", default="")
    ap.add_argument("--starfield", required=True)
    ap.add_argument("--plugins", default="", help="comma-separated plugin file names to activate")
    ap.add_argument("--pack", action="store_true", help="install the staged Data tree as '<first plugin> - Main.ba2'")
    ap.add_argument("--verify-workers", type=int, choices=range(1, 5), default=1,
                    help="full-content relaunch verification readers (default: 1, serial); opt in after measuring")
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
    if a.cmd == "active":
        sys.exit(active(a))
    rec_p = os.path.join(a.starfield, "Data", RECORD)
    if not os.path.exists(rec_p):
        print("nothing installed")
        return
    with open(rec_p) as f:
        print(f.read())


if __name__ == "__main__":
    main()
