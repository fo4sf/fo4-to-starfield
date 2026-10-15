"""Per-model checkpoints with content-verified generated dependencies.

Archive identity includes a streaming SHA-256 digest, so same-size edits with
preserved timestamps invalidate resume data. Archives must remain immutable
throughout the conversion run. Small tools/templates and converter
sources also use content hashes.

Windows fingerprints hold a read-sharing handle through the final metadata
check. Other platforms retain best-effort mutation detection; callers must
keep source archives immutable on every platform, including after return.
"""
import hashlib
import json
import os
import struct
from pathlib import Path
import tempfile
from contextlib import contextmanager

from . import nif, sfnif


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _stat_identity(stat):
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _path_identity(stat):
    # On Windows, an explicit utime restore can make path and open-handle
    # ctime reports differ even though the opened file is stable.
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)


def _hash_open_file(stream):
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(chunk)
    return h.hexdigest()


@contextmanager
def _open_archive_windows(path):
    """Deny writers, writable mappings and deletion while this stream is open."""
    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                           wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                           wintypes.HANDLE)
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    name = str(path)
    if not name.startswith("\\\\?\\"):
        name = "\\\\?\\UNC\\" + name[2:] if name.startswith("\\\\") else "\\\\?\\" + name
    # GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING, sequential cached reads.
    # Fail closed on incompatible existing access; never retry with write sharing.
    handle = create_file(name, 0x80000000, 0x1, None, 3, 0x08000080, None)
    if handle == wintypes.HANDLE(-1).value:
        error = ctypes.WinError(ctypes.get_last_error())
        error.filename = str(path)
        raise error
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY | os.O_NOINHERIT)
    except BaseException:
        close_handle(handle)
        raise
    # open_osfhandle transfers ownership to the CRT descriptor. Keep explicit
    # ownership: fdopen may fail after constructing/closing a partial stream.
    try:
        with os.fdopen(fd, "rb", closefd=False) as stream:
            yield stream
    finally:
        os.close(fd)


def archive_identity(path):
    path = Path(path).resolve()
    with (_open_archive_windows(path) if os.name == "nt" else path.open("rb")) as stream:
        before = os.fstat(stream.fileno())
        content_hash = _hash_open_file(stream)
        after = os.fstat(stream.fileno())
        current_path = path.stat()
        if (_stat_identity(before) != _stat_identity(after)
                or _path_identity(after) != _path_identity(current_path)):
            raise OSError(f"archive changed while fingerprinting: {path}")
        return [str(path), after.st_size, content_hash]


def reusable_result(result):
    """Retry degraded/failing conversions rather than freezing a placeholder."""
    return (result.get("ok") is True
            and not result.get("fallback_materials")
            and not result.get("door_error"))


def local_path(staging, relative):
    root = Path(staging).resolve()
    path = (root / relative.replace("\\", "/")).resolve()
    if not path.is_relative_to(root):
        raise ValueError("checkpoint output escapes staging")
    return path


def staged_path(staging, relative):
    """Resolve generated game paths case-insensitively on case-sensitive hosts."""
    root = Path(staging).resolve()
    requested = local_path(root, relative)
    current = root
    for part in requested.relative_to(root).parts:
        direct = current / part
        if direct.exists():
            current = direct
        elif current.is_dir():
            matches = [child for child in current.iterdir() if child.name.casefold() == part.casefold()]
            if len(matches) > 1:
                raise ValueError("ambiguous case-insensitive checkpoint output path")
            current = matches[0] if matches else direct
        else:
            current = direct
        # A differently cased directory may be a symlink. Check its resolved
        # target before traversing the next component or returning a file.
        current = local_path(root, current.relative_to(root).as_posix())
    return current


def output_inventory(staging, result, prefix="fo4port"):
    """Follow generated NIF -> mesh/material -> texture dependencies."""
    paths = {"meshes/" + result["out_name"] + ".nif"}
    model = nif.parse(staged_path(staging, next(iter(paths))).read_bytes())
    for i, block in enumerate(model.blocks):
        if model.type_of(i) == "BSGeometry":
            for mesh in sfnif.parse_bsgeometry(block).meshes:
                if mesh is not None:
                    paths.add("geometries/" + mesh.path.decode("latin-1").replace("\\", "/") + ".mesh")
    materials = set()
    for value in model.strings:
        name = value.decode("latin-1").replace("\\", "/")
        if name.lower().startswith(f"materials/{prefix}/") and name.lower().endswith(".mat"):
            materials.add(name)
    paths.update(materials)

    def textures(value):
        if isinstance(value, dict):
            for child in value.values():
                textures(child)
        elif isinstance(value, list):
            for child in value:
                textures(child)
        elif isinstance(value, str):
            name = value.replace("\\", "/")
            if name.lower().startswith("data/"):
                name = name[5:]
            if name.lower().startswith(f"textures/{prefix}/") and name.lower().endswith(".dds"):
                paths.add(name)

    for name in materials:
        with staged_path(staging, name).open(encoding="utf-8-sig") as f:
            textures(json.load(f))
    inventory = {}
    root = Path(staging).resolve()
    for name in sorted(paths):
        path = staged_path(root, name)
        canonical_name = path.relative_to(root).as_posix()
        inventory[canonical_name] = digest(path)
    return inventory


class Checkpoints:
    def __init__(self, staging, signature):
        self.staging = Path(staging)
        self.signature = signature
        self.directory = self.staging / ".checkpoints"
        self.expected = {}

    def path(self, source):
        key = source.replace("\\", "/").lower()
        return self.directory / (hashlib.sha256(key.encode()).hexdigest() + ".json")

    def load(self, source):
        try:
            with self.path(source).open(encoding="utf-8") as f:
                cached = json.load(f)
            if not isinstance(cached, dict) or not isinstance(cached.get("outputs"), dict) or not isinstance(cached.get("result"), dict):
                return None
            if cached["signature"] != self.signature or not cached["outputs"]:
                return None
            result = cached["result"]
            if not isinstance(result.get("out_name"), str) or not result["out_name"]:
                return None
            if any(type(result.get(field)) is not int or result[field] < 0
                   for field in ("shapes", "fallback_materials")):
                return None
            if not reusable_result(result):
                return None
            if output_inventory(self.staging, result) != cached["outputs"]:
                return None
            self.expected[source] = cached["outputs"]
            return cached["result"]
        except (OSError, ValueError, KeyError, TypeError, struct.error):
            return None

    def save(self, source, result):
        if not reusable_result(result):
            self.path(source).unlink(missing_ok=True)
            return False  # Retry degraded/failing conversions rather than freezing a placeholder.
        try:
            outputs = output_inventory(self.staging, result)
        except (OSError, ValueError, KeyError, TypeError, struct.error):
            # The batch runner may continue after checkpoint I/O errors. Keep an
            # explicit failed expectation so it cannot publish an unverified build.
            self.expected[source] = None
            raise
        self.expected[source] = outputs
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=self.directory, prefix=".pending-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"signature": self.signature, "result": result, "outputs": outputs}, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, self.path(source))
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)
        return True

    def verify_batch(self):
        """Recheck expectations after all writes, including dependencies shared by models."""
        actual, errors = {}, []
        for source, outputs in self.expected.items():
            if not isinstance(outputs, dict):
                errors.append({"source": source, "output": "<dependency inventory unavailable>"})
                continue
            for relative, expected in outputs.items():
                path = local_path(self.staging, relative)
                if path not in actual:
                    try:
                        actual[path] = digest(path)
                    except OSError:
                        actual[path] = None
                if actual[path] != expected:
                    errors.append({"source": source, "output": relative})
        return errors
