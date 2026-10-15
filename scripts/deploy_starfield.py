"""Install / uninstall converted files into a Starfield install for testing (reversible).

install  : packs <staging>/{meshes,geometries,materials} into "FO4Port - Main.ba2" and <staging>/textures into\n           "FO4Port - Textures.ba2" with the official Archive2
           (shipped with the Starfield Creation Kit), copies it and FO4Port.esm into Starfield\\Data, and enables the plugin
           in %LOCALAPPDATA%\\Starfield\\Plugins.txt. Starfield loads a plugin's "<name> - Main.ba2" automatically, so no
           ini change is needed. It refuses to overwrite existing files; everything it adds is recorded in
           Data/FO4Port.deploy.json.
uninstall: removes exactly what the manifest lists, including the Plugins.txt line.

usage: python deploy_starfield.py install|uninstall --staging <dir> --starfield <game dir> [--dry-run]
"""
import argparse
import base64
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

PLUGIN = "FO4Port.esm"
ARCHIVE = "FO4Port - Main.ba2"
TEX_ARCHIVE = "FO4Port - Textures.ba2"
MANIFEST = "FO4Port.deploy.json"
MAIN_DIRS = ("meshes", "geometries", "materials")
DEPLOYED_FILES = frozenset((PLUGIN, ARCHIVE, TEX_ARCHIVE))
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


def plan_plugin_activation(lines):
    """Return the activated list plus the exact plugin lines this install owns."""
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
    if expected_current is not _UNSET:
        update_plugins_config(p, content, expected_current)
        return
    fd, temporary = tempfile.mkstemp(prefix=prefix, dir=os.path.dirname(p))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, p)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def check_regular_config(p):
    """Refuse a non-regular file/reparse point before moving or reading it."""
    metadata = os.lstat(p)
    if (not stat.S_ISREG(metadata.st_mode) or
            getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
        raise OSError("Plugins.txt is not an ordinary file; preserving it")


def read_config_bytes(p):
    """Validate/read the captured file inside our unique recovery directory."""
    check_regular_config(p)
    with open(p, "rb") as stream:
        return stream.read()


def config_path_exists(p):
    """Only FileNotFoundError establishes absence; access/inspection failures propagate."""
    try:
        os.lstat(p)
    except FileNotFoundError:
        return False
    return True


def require_resolved_config_recovery(p):
    """Do not let a retry forget an unresolved capture merely because the target is absent."""
    parent = os.path.dirname(os.path.abspath(p))
    try:
        metadata = os.stat(parent)
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(metadata.st_mode):
        raise OSError("Plugins.txt configuration parent is not a directory")
    with os.scandir(parent) as entries:
        directories = [entry.path for entry in entries
                       if entry.name.startswith(".fo4port-config-") and entry.is_dir(follow_symlinks=False)]
    for directory in directories:
        before = os.path.join(directory, "before.txt")
        intended = os.path.join(directory, "intended.txt")
        try:
            with open(os.path.join(directory, "transaction.json"), encoding="utf-8") as stream:
                record = json.load(stream)
            target = record["target"]
            if not isinstance(target, str):
                raise ValueError("invalid transaction target")
        except FileNotFoundError:
            if config_path_exists(before):
                raise OSError(f"Plugins.txt recovery journal unreadable; preserving copies at {directory}")
            continue
        except (OSError, ValueError, KeyError, TypeError):
            if config_path_exists(before) or config_path_exists(intended):
                raise OSError(f"Plugins.txt recovery journal unreadable; preserving copies at {directory}")
            continue
        if os.path.normcase(os.path.abspath(target)) != os.path.normcase(os.path.abspath(p)):
            continue
        if record.get("complete") is True and record.get("status") in ("published", "removed"):
            continue
        if (record.get("status") == "interrupted" and
                (record.get("restoration") == "captured file restored without replacement" or
                 (record.get("capture_attempted") is False and not config_path_exists(before)))):
            continue
        raise OSError(f"Plugins.txt recovery remains unresolved; preserving copies at {directory}")


def update_plugins_config(p, content, expected_current):
    """Capture before comparing, then publish without replacing a new pathname.

    Keep both the before-image and intended file, even on success: an editor with
    an old open handle may finish writing the captured file after validation.
    This preserves bytes, not continuous name visibility or a deployment lock.
    """
    require_resolved_config_recovery(p)
    if expected_current is None:
        if config_path_exists(p):
            raise ConcurrentUpdateError("Plugins.txt changed during update; preserving concurrent edits")
    else:
        check_regular_config(p)
    directory = tempfile.mkdtemp(prefix=".fo4port-config-", dir=os.path.dirname(os.path.abspath(p)))
    before = os.path.join(directory, "before.txt")
    intended = os.path.join(directory, "intended.txt")
    journal = os.path.join(directory, "transaction.json")
    record = {
        "version": 1, "target": os.path.abspath(p), "operation": "remove" if content is None else "write",
        "expected_sha256": hashlib.sha256(expected_current).hexdigest() if expected_current is not None else None,
        "intended_sha256": hashlib.sha256(content).hexdigest() if content is not None else None,
        "complete": False, "status": "prepared", "capture_attempted": False,
    }

    def record_status():
        atomic_write_bytes(journal, (json.dumps(record, indent=1) + "\n").encode("utf-8"), ".journal-")

    publication_attempted = False
    capture_attempted = False
    try:
        fd = os.open(intended, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content if content is not None else b"")
            stream.flush()
            os.fsync(stream.fileno())
        record_status()                         # recoverable intent exists before the target moves
        probe = os.path.join(directory, "link-probe")
        os.link(intended, probe)                 # unsupported filesystems fail before capture
        os.remove(probe)
        if expected_current is not None:
            record["capture_attempted"] = True
            record_status()
            capture_attempted = True
            os.replace(p, before)               # capture the actual final-boundary file, not an earlier read
            if read_config_bytes(before) != expected_current:
                raise ConcurrentUpdateError("Plugins.txt changed during update; captured owner edits preserved")
        if content is not None:
            publication_attempted = True
            os.link(intended, p)                # atomic creation: a newly appeared owner file cannot be replaced
        elif config_path_exists(p):
            raise OSError("Plugins.txt appeared during removal; preserving the new file")
        record.update(complete=True, status="removed" if content is None else "published")
        record_status()
    except BaseException as error:
        restoration = "no capture attempted"
        if capture_attempted:
            try:
                captured_exists = config_path_exists(before)
            except OSError as inspection_error:
                restoration = f"capture inspection unavailable; recovery retained: {inspection_error}"
            else:
                restoration = "capture outcome unresolved; captured pathname absent"
                if captured_exists:
                    try:
                        os.link(before, p, follow_symlinks=False)
                        restoration = "captured file restored without replacement"
                    except FileExistsError:
                        restoration = "current target retained; captured file also retained"
                    except OSError as restore_error:
                        restoration = f"captured file retained; restoration unavailable: {restore_error}"
        record.update(complete=False, status="interrupted", error=str(error), restoration=restoration,
                      capture_attempted=capture_attempted)
        try:
            record_status()
        except OSError:
            pass                                # the prepared journal and any captured bytes remain
        if isinstance(error, OSError):
            safe_refusal = (not publication_attempted and isinstance(error, ConcurrentUpdateError) and
                            (not capture_attempted or restoration == "captured file restored without replacement"))
            error_type = ConcurrentUpdateError if safe_refusal else OSError
            raise error_type(f"Plugins.txt changed or update failed; preserving recovery copies at {directory}: "
                             f"{error}; {restoration}") from error
        raise


def restore_plugins(state):
    p = state["plugins_txt"]
    require_resolved_config_recovery(p)
    original = state["plugins_original"]
    original_bytes = base64.b64decode(original) if original is not None else None
    current = None
    if config_path_exists(p):
        with open(p, "rb") as f:
            current = f.read()
    expected = state.get("plugins_activated")
    expected_bytes = base64.b64decode(expected) if isinstance(expected, str) else None
    if current == original_bytes:
        return
    if expected_bytes is None or current != expected_bytes:
        raise OSError("Plugins.txt changed since interrupted install; preserved")
    if original_bytes is None:
        update_plugins_config(p, None, expected_bytes)
    else:
        atomic_write_bytes(p, original_bytes, ".fo4port-plugins-", expected_current=current)


def validate_plugin_cleanup(manifest):
    added = manifest.get("plugins_added", [])
    replaced = manifest.get("plugins_replaced", [])
    if (not isinstance(added, list) or len(added) > 1 or
            any(not isinstance(line, str) or line.casefold() != f"*{PLUGIN}".casefold()
                for line in added)):
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
    # 2) record intent first, then copy; any failure rolls back what was copied
    identities = {os.path.basename(dst): artifact_identity(src) for src, dst in zip(built, targets)}
    state = {"files": [], "published_files": [], "plugins_txt": pt, "plugins_added": pl_add,
             "plugins_replaced": [], "complete": False, "artifacts": identities}
    plugins_existed = os.path.exists(pt)
    plugins_original = None
    if plugins_existed:
        with open(pt, "rb") as f:
            plugins_original = f.read()
    # Archive builds can be long; merge activation into the current list,
    # not the preflight snapshot from before the build.
    pl = plugins_original.decode("utf-8-sig").splitlines() if plugins_original is not None else []
    activated, pl_add, pl_replaced = plan_plugin_activation(pl)
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
        if not isinstance(rel, str) or rel not in DEPLOYED_FILES:
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
            require_resolved_config_recovery(plugins_path)
            plugins_original = None
            if config_path_exists(plugins_path):
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
                    update_plugins_config(plugins_path, None, plugins_original)
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
    ap.add_argument("--starfield", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    (install if args.action == "install" else uninstall)(args)
