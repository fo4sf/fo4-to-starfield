"""Install / uninstall converted files into a Starfield install for testing (reversible).

install  : packs <staging>/{meshes,geometries,materials} into "FO4Port - Main.ba2" and <staging>/textures into\n           "FO4Port - Textures.ba2" with the official Archive2
           (shipped with the Starfield Creation Kit), copies it and FO4Port.esm into Starfield\\Data, and enables the plugin
           in %LOCALAPPDATA%\\Starfield\\Plugins.txt. Starfield loads a plugin's "<name> - Main.ba2" automatically, so no
           ini change is needed. It refuses to overwrite existing files; everything it adds is recorded in
           Data/FO4Port.deploy.json.
install --batch: installs an interior batch's built port as it is (scripts/terrain/interior_batch.py build): every
           file of <stage>/result.json's install set from <stage>/port (FO4Port.esm, its archives and each texture
           companion FO4PortTexturesN.esm with "FO4PortTexturesN - Textures.ba2"), each checked against the sha256 the
           build pinned, nothing packed. Plugins.txt gets FO4Port.esm and then the companions, in number order, right
           after it. It refuses when the copies would leave less than --min-free-gb free on the game's drive, and
           when Data's FO4TerrainCore.esm is not the core the batch's door returns were wired to (--other-core).
uninstall: removes exactly what the manifest lists, including the Plugins.txt lines.

usage: python deploy_starfield.py install|uninstall --staging <dir> --starfield <game dir> [--dry-run]
       python deploy_starfield.py install --batch <interior batch stage> --starfield <game dir> [--min-free-gb 40] [--other-core]
                                    [--dry-run]
"""
import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

PLUGIN = "FO4Port.esm"
ARCHIVE = "FO4Port - Main.ba2"
TEX_ARCHIVE = "FO4Port - Textures.ba2"
MANIFEST = "FO4Port.deploy.json"
MAIN_DIRS = ("meshes", "geometries", "materials")
DEPLOYED_FILES = frozenset((PLUGIN, ARCHIVE, TEX_ARCHIVE))
# an interior batch's texture companions (interior_batch.py COMPANION_PLUGIN / COMPANION_ARCHIVE): N = 2, 3, ...
COMPANION_RX = re.compile(r"^FO4PortTextures([2-9]|[1-9]\d+)(\.esm| - Textures\.ba2)$")
BATCH_RESULT = "result.json"
CORE_PLUGIN = "FO4TerrainCore.esm"   # the core whose exterior doors a batch's door returns were wired to (vmad_patch.py)
_UNSET = object()


class ConcurrentUpdateError(OSError):
    """The expected file changed; the guarded replacement did not happen."""


def plugins_txt_path():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Starfield", "Plugins.txt")


def read_lines(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig") as f:
        return f.read().splitlines()


def plugin_name(line):
    value = line.strip()
    return value[1:] if value.startswith("*") else value


def deployable(rel):
    """A file name this deployment may own in Data: the port's three, or a texture companion's plugin or archive."""
    return rel in DEPLOYED_FILES or COMPANION_RX.match(rel) is not None


def is_companion_plugin(name):
    m = COMPANION_RX.match(name)
    return m is not None and m.group(2) == ".esm"


def plan_plugin_activation(lines, companions=()):
    """Return the activated list plus the exact plugin lines this install owns. Companions (texture companion plugins,
    in load order) are added as active lines right after FO4Port.esm's; a list that already names one is refused, since
    that line is not this install's to own."""
    updated, added, replaced = plan_port_activation(lines)
    if not companions:
        return updated, added, replaced
    stale = [plugin_name(ln) for ln in updated if plugin_name(ln).casefold() in {c.casefold() for c in companions}]
    if stale:
        raise ValueError(f"Plugins.txt already lists {', '.join(stale)}; remove those lines (an earlier hand install?) "
                         "and install again")
    at = next(i for i, ln in enumerate(updated) if plugin_name(ln).casefold() == PLUGIN.casefold())
    lines_added = [f"*{c}" for c in companions]
    return updated[:at + 1] + lines_added + updated[at + 1:], added + lines_added, replaced


def plan_port_activation(lines):
    """FO4Port.esm's own line: already active, activated in place, or appended."""
    for line in lines:
        if line.strip().startswith("*") and plugin_name(line).casefold() == PLUGIN.casefold():
            return list(lines), [], []
    for index, line in enumerate(lines):
        if plugin_name(line).casefold() == PLUGIN.casefold():
            active = f"*{plugin_name(line)}"
            updated = list(lines)
            updated[index] = active
            return updated, [active], [{"active": active, "original": line}]
    active = f"*{PLUGIN}"
    return [*lines, active], [active], []


def write_manifest(p, state):
    fd, temporary = tempfile.mkstemp(prefix=".fo4port-deploy-", dir=os.path.dirname(p))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, p)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def atomic_write_bytes(p, content, prefix, expected_current=_UNSET):
    fd, temporary = tempfile.mkstemp(prefix=prefix, dir=os.path.dirname(p))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        if expected_current is not _UNSET:
            current = None
            if os.path.exists(p):
                with open(p, "rb") as existing:
                    current = existing.read()
            if current != expected_current:
                raise ConcurrentUpdateError("Plugins.txt changed during update; preserving concurrent edits")
        os.replace(temporary, p)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def restore_plugins(state):
    p = state["plugins_txt"]
    original = state["plugins_original"]
    original_bytes = base64.b64decode(original) if original is not None else None
    current = None
    if os.path.exists(p):
        with open(p, "rb") as f:
            current = f.read()
    expected = state.get("plugins_activated")
    expected_bytes = base64.b64decode(expected) if isinstance(expected, str) else None
    if current == original_bytes:
        return
    if expected_bytes is None or current != expected_bytes:
        raise OSError("Plugins.txt changed since interrupted install; preserved")
    if original_bytes is None:
        if os.path.exists(p):
            os.remove(p)
    else:
        atomic_write_bytes(p, original_bytes, ".fo4port-plugins-", expected_current=current)


def validate_plugin_cleanup(manifest):
    added = manifest.get("plugins_added", [])
    replaced = manifest.get("plugins_replaced", [])
    if (not isinstance(added, list) or
            any(not isinstance(line, str) or not line.startswith("*") or
                (line.casefold() != f"*{PLUGIN}".casefold() and not is_companion_plugin(line[1:]))
                for line in added) or
            len({line.casefold() for line in added}) != len(added)):
        sys.exit("unexpected plugin cleanup entry in manifest; refusing cleanup")
    if not isinstance(replaced, list) or len(replaced) > 1:
        sys.exit("unexpected plugin restoration entry in manifest; refusing cleanup")
    for item in replaced:
        if (not isinstance(item, dict) or
                not isinstance(item.get("active"), str) or
                item["active"].casefold() != f"*{PLUGIN}".casefold() or
                not isinstance(item.get("original"), str) or
                item["original"].strip().startswith("*") or
                plugin_name(item["original"]).casefold() != PLUGIN.casefold()):
            sys.exit("unexpected plugin restoration entry in manifest; refusing cleanup")
def render_lines(lines, original=None):
    if original is None:
        bom, newline, trailing = b"", "\r\n", True
    else:
        bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
        content = original[len(bom):]
        newline = "\r\n" if b"\r\n" in content else "\n" if b"\n" in content else "\r" if b"\r" in content else "\r\n"
        trailing = content.endswith((b"\r", b"\n"))
    text = newline.join(lines) + (newline if lines and trailing else "")
    return bom + text.encode("utf-8")


def write_lines(p, lines, original=None):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    atomic_write_bytes(p, render_lines(lines, original), ".fo4port-plugins-", expected_current=original)


def build_archive(a, out, folders, fmt, compression="Default"):
    tool = os.path.join(a.starfield, "Tools", "Archive2", "Archive2.exe")
    if not os.path.exists(tool):
        sys.exit(f"Archive2 not found at {tool} (install the Starfield Creation Kit)")
    # A previous output must not masquerade as a successful new build.
    with tempfile.TemporaryDirectory(prefix=".fo4port-archive-", dir=os.path.dirname(os.path.abspath(out))) as temporary:
        fresh = os.path.join(temporary, os.path.basename(out))
        r = subprocess.run([tool, ",".join(folders), f"-create={fresh}", f"-root={a.staging}", f"-format={fmt}",
                            f"-compression={compression}"], cwd=a.staging, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.isfile(fresh):
            sys.exit("Archive2 failed (no successful fresh output):\n" + (r.stdout or "") + (r.stderr or ""))
        with open(fresh, "rb") as stream:
            head = stream.read(4)
        if os.path.getsize(fresh) < 16 or head != b"BTDX":
            sys.exit("Archive2 produced an invalid archive; previous build preserved")
        os.replace(fresh, out)


def artifact_identity(path):
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return {"size": size, "sha256": digest.hexdigest()}


def copy_new_artifact(src, dst, expected_sha256=None):
    """Publish without replacing a target, preferring an atomic same-directory link."""
    fd, temporary = tempfile.mkstemp(prefix=".fo4port-install-", dir=os.path.dirname(dst))
    os.close(fd)
    try:
        shutil.copyfile(src, temporary)
        copied = artifact_identity(temporary)
        if copied != artifact_identity(src):
            raise OSError(f"temporary copy differs from source: {os.path.basename(dst)}")
        if expected_sha256 is not None and copied["sha256"] != expected_sha256:
            raise OSError(f"source changed since preflight: {os.path.basename(dst)}")
        # Same-directory hard-link creation is atomic and fails if dst exists.
        try:
            os.link(temporary, dst)
        except FileExistsError:
            raise
        except OSError:
            # Some filesystems do not support hard links. Exclusive creation
            # retains no-overwrite behavior there, though the copy is not atomic.
            created = False
            try:
                with open(dst, "xb") as output, open(temporary, "rb") as source:
                    created = True
                    shutil.copyfileobj(source, output)
            except BaseException:
                if created:
                    try:
                        os.remove(dst)
                    except OSError:
                        pass
                raise
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def install(a):
    if getattr(a, "batch", ""):
        return install_batch(a)
    build_state = os.path.join(a.staging, "build-state.json")
    if os.path.exists(build_state):
        with open(build_state, encoding="utf-8") as f:
            state = json.load(f)
        if state.get("complete") is not True:
            sys.exit("staging build is interrupted or inconsistent; finish conversion before installing")
    data = os.path.join(a.starfield, "Data")
    man_path = os.path.join(data, MANIFEST)
    if os.path.exists(man_path):
        sys.exit("already installed (manifest exists); uninstall first")
    esm = next((p for p in (os.path.join(a.staging, "Data", PLUGIN), os.path.join(a.staging, PLUGIN)) if os.path.exists(p)), None)
    if not esm:
        sys.exit(f"{PLUGIN} not found in staging")
    main_dirs = [d for d in MAIN_DIRS if os.path.isdir(os.path.join(a.staging, d))]
    has_tex = os.path.isdir(os.path.join(a.staging, "textures"))
    targets = [os.path.join(data, PLUGIN), os.path.join(data, ARCHIVE)] + ([os.path.join(data, TEX_ARCHIVE)] if has_tex else [])
    clash = [t for t in targets if os.path.exists(t)]
    if clash:
        sys.exit("refusing to overwrite existing files:\n  " + "\n  ".join(clash))
    pt = plugins_txt_path()
    pl = read_lines(pt)
    _, pl_add, _ = plan_plugin_activation(pl)
    print(f"install: {[os.path.basename(x) for x in targets]} -> {data}\nPlugins.txt ({pt}): activate {pl_add or 'nothing'}")
    if a.dry_run:
        return
    # 1) build and validate EVERYTHING before touching the game folder
    built = [esm, os.path.join(a.staging, ARCHIVE)]
    build_archive(a, built[1], main_dirs, "General")
    if has_tex:
        built.append(os.path.join(a.staging, TEX_ARCHIVE))
        build_archive(a, built[2], ["textures"], "DDS")
    for index, b in enumerate(built):
        with open(b, "rb") as f:
            head = f.read(4)
        expected_head = b"TES4" if index == 0 else b"BTDX"
        if os.path.getsize(b) < 16 or head != expected_head:
            sys.exit(f"build output looks invalid, nothing installed: {b}")
    publish(data, man_path, built, targets, {os.path.basename(dst): artifact_identity(src) for src, dst in zip(built, targets)})


def publish(data, man_path, built, targets, identities, companions=()):
    """Record intent first, then copy built[i] to targets[i]; any failure rolls back what was copied. identities:
    {target name: artifact_identity} each copy must match. companions: plugins activated right after FO4Port.esm."""
    pt = plugins_txt_path()
    state = {"files": [], "published_files": [], "plugins_txt": pt, "plugins_added": [],
             "plugins_replaced": [], "complete": False, "artifacts": identities}
    plugins_existed = os.path.exists(pt)
    plugins_original = None
    if plugins_existed:
        with open(pt, "rb") as f:
            plugins_original = f.read()
    # Archive builds can be long; merge activation into the current list,
    # not the preflight snapshot from before the build.
    pl = plugins_original.decode("utf-8-sig").splitlines() if plugins_original is not None else []
    try:
        activated, pl_add, pl_replaced = plan_plugin_activation(pl, companions)
    except ValueError as error:
        sys.exit(f"nothing installed: {error}")
    state["plugins_added"] = pl_add
    state["plugins_replaced"] = pl_replaced
    state["plugins_original"] = base64.b64encode(plugins_original).decode("ascii") if plugins_existed else None
    state["plugins_activated"] = base64.b64encode(render_lines(activated, plugins_original)).decode("ascii")
    state["plugins_restore_pending"] = False
    write_manifest(man_path, state)
    installed_files = set()
    try:
        for src, dst in zip(built, targets):
            rel = os.path.basename(dst)
            state["files"].append(rel)
            write_manifest(man_path, state)
            copy_new_artifact(src, dst)
            installed_files.add(rel)
            if artifact_identity(dst) != identities[rel]:
                raise OSError(f"installed artifact differs from validated build: {rel}")
            state["published_files"].append(rel)
            write_manifest(man_path, state)
        if pl_add:
            current_plugins = None
            if os.path.exists(pt):
                with open(pt, "rb") as f:
                    current_plugins = f.read()
            if current_plugins != plugins_original:
                raise OSError("Plugins.txt changed during install; activation aborted to preserve user edits")
            state["plugins_restore_pending"] = True
            write_manifest(man_path, state)
            write_lines(pt, activated, plugins_original)
        state["complete"] = True
        write_manifest(man_path, state)
    except Exception as e:                                   # noqa: BLE001 (roll back, then report)
        state["complete"] = False
        errors = []
        if state["plugins_restore_pending"]:
            try:
                restore_plugins(state)
                state["plugins_restore_pending"] = False
            except OSError as cleanup_error:
                errors.append(str(cleanup_error))
        remaining = []
        for rel in state["files"]:
            p = os.path.join(data, rel)
            try:
                if os.path.exists(p):
                    if rel not in installed_files:
                        raise OSError(f"destination appeared during install; preserved: {rel}")
                    if artifact_identity(p) != identities[rel]:
                        raise OSError(f"installed artifact changed during rollback; preserved: {rel}")
                    os.remove(p)
            except OSError as cleanup_error:
                remaining.append(rel)
                errors.append(str(cleanup_error))
        state["files"] = remaining
        if errors:
            write_manifest(man_path, state)
            sys.exit(f"install failed: {e}; recovery manifest retained at {man_path}. "
                     f"Retry uninstall after resolving: {'; '.join(errors)}")
        os.remove(man_path)
        sys.exit(f"install failed and was rolled back: {type(e).__name__}: {e}")
    print("installed. Undo with: python deploy_starfield.py uninstall --starfield <game dir>")


def read_head(path, n=4):
    with open(path, "rb") as f:
        return f.read(n)


def batch_install_set(stage):
    """[(source, target name, sha256)] in install order plus the companion plugins in load order, from an interior
    batch's result.json (interior_batch.py finish). Exits when the batch failed, the set is malformed, a file is
    missing or unpinned, or a file is not what its name says."""
    path = os.path.join(stage, BATCH_RESULT)
    try:
        with open(path, encoding="utf-8") as f:
            result = json.load(f)
        files = result["install"]["files"]
        order = result["install"]["plugins_txt"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        sys.exit(f"not an interior batch stage ({path}: {error})")
    if result.get("pass") is not True:
        sys.exit(f"batch {result.get('batch')} did not pass ({result.get('error')}); nothing installed")
    if (not isinstance(files, list) or not all(isinstance(n, str) and deployable(n) for n in files)
            or len(set(files)) != len(files) or PLUGIN not in files or ARCHIVE not in files):
        sys.exit(f"{path}: install.files is not a port's set: {files!r}")
    companions = [n for n in files if is_companion_plugin(n)]
    archives = {n for n in files if COMPANION_RX.match(n) and not is_companion_plugin(n)}
    if order != [PLUGIN] + companions or archives != {n[:-4] + " - Textures.ba2" for n in companions}:
        sys.exit(f"{path}: install.plugins_txt {order!r} does not match the files' companions")
    pins = dict(((result.get("steps") or {}).get("pack") or {}).get("sha256") or {})
    pins[PLUGIN] = (result.get("pins") or {}).get("plugin")
    port = os.path.join(stage, "port")
    out = []
    for name in files:
        src = os.path.join(port, name)
        if not os.path.isfile(src):
            sys.exit(f"missing from the stage: {src}")
        if not isinstance(pins.get(name), str):
            sys.exit(f"{path}: no sha256 pinned for {name}")
        want = b"TES4" if name.endswith(".esm") else b"BTDX"
        if os.path.getsize(src) < 16 or read_head(src) != want:
            sys.exit(f"not a {'plugin' if want == b'TES4' else 'BA2 archive'}: {src}")
        out.append((src, name, pins[name].lower()))
    return out, companions, result


def core_check(result, data):
    """None when Data's core is the one the batch's door returns were wired to (result.json pins.core_plugin, the
    sha256 interior_batch.py took of --core's plugin at build time), else why not: a return door made against another
    core build may name an arrival marker that core lacks."""
    live = os.path.join(data, CORE_PLUGIN)
    if not os.path.isfile(live):
        return None                                            # no core installed: nothing to land on either way
    want = (result.get("pins") or {}).get("core_plugin")
    if not isinstance(want, str):
        return f"the batch pins no core (built before pins.core_plugin): restage it against Data\\{CORE_PLUGIN}'s core"
    got = artifact_identity(live)["sha256"]
    return None if got == want.lower() else (
        f"the batch's doors were wired against core {want[:8]}, Data\\{CORE_PLUGIN} is {got[:8]}: "
        "restage the batch against the installed core, or pass --other-core to install it anyway")


def install_batch(a):
    data = os.path.join(a.starfield, "Data")
    man_path = os.path.join(data, MANIFEST)
    if os.path.exists(man_path):
        sys.exit("already installed (manifest exists); uninstall first")
    items, companions, result = batch_install_set(a.batch)
    problem = core_check(result, data)
    if problem and not a.other_core:
        sys.exit(f"nothing installed: {problem}")
    if problem:
        print(f"--other-core: {problem}")
    targets = [os.path.join(data, name) for _, name, _ in items]
    clash = [t for t in targets if os.path.exists(t)]
    if clash:
        sys.exit("refusing to overwrite existing files:\n  " + "\n  ".join(clash))
    need = sum(os.path.getsize(src) for src, _, _ in items)
    free = shutil.disk_usage(data).free
    if free - need < a.min_free_gb * 1024 ** 3:
        sys.exit(f"nothing installed: {need / 1024 ** 3:.1f} GB to copy would leave {(free - need) / 1024 ** 3:.1f} GB "
                 f"free on the game's drive, under --min-free-gb {a.min_free_gb}")
    try:
        plan_plugin_activation(read_lines(plugins_txt_path()), companions)
    except ValueError as error:
        sys.exit(f"nothing installed: {error}")
    print(f"install batch {a.batch}: {[name for _, name, _ in items]} -> {data} ({need / 1024 ** 3:.2f} GB)\n"
          f"Plugins.txt ({plugins_txt_path()}): *{PLUGIN} then {['*' + c for c in companions]}")
    if a.dry_run:
        return
    identities = {}
    for src, name, want in items:
        identities[name] = artifact_identity(src)
        if identities[name]["sha256"] != want:
            sys.exit(f"nothing installed: {src} is not the file the build pinned "
                     f"(sha256 {identities[name]['sha256'][:12]}..., pinned {want[:12]}...)")
    publish(data, man_path, [src for src, _, _ in items], targets, identities, companions)


def uninstall(a):
    data = os.path.join(a.starfield, "Data")
    man_path = os.path.join(data, MANIFEST)
    if not os.path.exists(man_path):
        sys.exit("nothing to uninstall (no manifest)")
    with open(man_path) as f:
        m = json.load(f)
    expected_plugins = plugins_txt_path()
    recorded_plugins = m.get("plugins_txt") if isinstance(m, dict) else None
    if (not isinstance(recorded_plugins, str) or
            os.path.normcase(os.path.abspath(recorded_plugins)) !=
            os.path.normcase(os.path.abspath(expected_plugins))):
        sys.exit("Plugins.txt path in manifest does not match the current user path; refusing cleanup")
    validate_plugin_cleanup(m)
    print(f"removing {m['files']} and Plugins.txt entries {m['plugins_added']}")
    if a.dry_run:
        return
    remaining, errors = [], []
    published = m.get("published_files", [])
    published = {item for item in published if isinstance(item, str)} if isinstance(published, list) else set()
    for rel in m["files"]:
        if not isinstance(rel, str) or not deployable(rel):
            remaining.append(rel)
            errors.append(f"unexpected deployment path; preserved: {rel!r}")
            continue
        p = os.path.join(data, rel)
        try:
            if os.path.exists(p):
                if not m.get("complete", True) and rel not in published:
                    raise OSError(f"destination was not confirmed as published; preserved: {rel}")
                expected = m.get("artifacts", {}).get(rel)
                if expected is not None and artifact_identity(p) != expected:
                    raise OSError(f"artifact changed since installation; preserved: {rel}")
                os.remove(p)
        except OSError as e:
            remaining.append(rel)
            errors.append(str(e))
    m["files"] = remaining
    if isinstance(m.get("published_files"), list):
        m["published_files"] = [rel for rel in m["published_files"] if rel in remaining]
    try:
        if not m.get("complete", True) and m.get("plugins_restore_pending"):
            restore_plugins(m)
        elif m["plugins_added"]:
            added = {line.casefold() for line in m["plugins_added"]}
            replaced = {item["active"].casefold(): item["original"]
                        for item in m.get("plugins_replaced", [])}
            restored = set()
            removed = set()
            plugins_path = m["plugins_txt"]
            plugins_original = None
            if os.path.exists(plugins_path):
                with open(plugins_path, "rb") as f:
                    plugins_original = f.read()
            pl = (plugins_original.decode("utf-8-sig").splitlines()
                  if plugins_original is not None else [])
            updated = []
            for line in pl:
                key = line.casefold()
                if key in replaced and key not in restored:
                    updated.append(replaced[key])
                    restored.add(key)
                elif key in added and key not in removed:
                    removed.add(key)
                else:
                    updated.append(line)
            if updated:
                write_lines(plugins_path, updated, plugins_original)
            elif plugins_original is not None:
                if m.get("plugins_original") is None:
                    os.remove(m["plugins_txt"])
                else:
                    write_lines(plugins_path, [], plugins_original)
        m["plugins_added"] = []
        m["plugins_replaced"] = []
        m["plugins_restore_pending"] = False
    except OSError as e:
        errors.append(str(e))
    if errors:
        write_manifest(man_path, m)
        sys.exit(f"uninstall incomplete; recovery manifest retained at {man_path}. "
                 f"Retry after resolving: {'; '.join(errors)}")
    os.remove(man_path)
    print("uninstalled")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["install", "uninstall"])
    ap.add_argument("--staging", default="")
    ap.add_argument("--batch", default="", help="an interior batch stage: install its built port as it is")
    ap.add_argument("--other-core", action="store_true",
                    help="--batch: install even though the installed core is not the one the batch's doors were wired to")
    ap.add_argument("--min-free-gb", type=float, default=40.0, help="--batch: free space the game's drive keeps")
    ap.add_argument("--starfield", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.batch and (args.staging or args.action != "install"):
        ap.error("--batch is for install alone, without --staging")
    (install if args.action == "install" else uninstall)(args)
