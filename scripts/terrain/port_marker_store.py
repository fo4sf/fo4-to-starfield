"""Reservation-only journal for #280. Never publishes plugins or clears recovery.

Keep session() open through the caller's separate paired-output transaction.
Crashes leave evidence; recover() requires both externally selected state pins.
Uses file flush/fsync and same-directory replacement. Hardware power-loss and
network filesystems are not validated by the process-interruption tests.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid

import port_marker_ids as ids


class BusyError(OSError):
    pass


class RecoveryRequired(OSError):
    pass


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _plain(path, directory=False):
    info = path.lstat()
    if (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            or (not directory and info.st_nlink != 1)):
        raise OSError(f"unproven reservation path: {path}")
    return info


def _root(path):
    path = Path(path).absolute()
    for parent in reversed((path, *path.parents)):
        _plain(parent, directory=True)
    return path


def _identity(info):
    return info.st_dev, info.st_ino


def _read(path):
    before = _plain(path)
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read()
        after = os.fstat(stream.fileno())
    current = _plain(path)
    if (_identity(before) != _identity(opened) or _identity(opened) != _identity(current)
            or (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
            or (after.st_size, after.st_mtime_ns) != (current.st_size, current.st_mtime_ns)):
        raise OSError("reservation file changed while reading")
    return raw


def _write_once(path, raw):
    if os.path.lexists(path):
        if _read(path) != raw:
            raise RecoveryRequired(f"existing reservation evidence differs: {path.name}")
        return
    # An interrupted write is retained; no deletion or replacement of evidence.
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _sync_directory(root):
    if os.name != "nt":
        fd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


@contextmanager
def _lease(directory):
    root = _root(directory)
    root_id = _identity(root.stat())
    path = root / "writer.lock"
    _plain(path)
    with path.open("r+b") as stream:
        acquired = False
        try:
            try:
                if os.name == "nt":
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError as err:
                raise BusyError("another reservation writer owns this store") from err

            def verify():
                if (_identity(_plain(root, directory=True)) != root_id
                        or _identity(_plain(path)) != _identity(os.fstat(stream.fileno()))):
                    raise OSError("reservation lock/root identity changed")
                _root(root)

            verify()
            yield root, verify
        finally:
            if acquired:
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _intent(before, after):
    raw = (json.dumps({"format": 1, "before": before, "after": after}, sort_keys=True) + "\n").encode()
    return _sha(raw), raw


def _pending(root):
    pending = []
    for path in root.glob("intent-*.json"):
        raw = _read(path)
        data = ids._json(raw)
        if (not isinstance(data, dict) or set(data) != {"format", "before", "after"}
                or type(data["format"]) is not int or data["format"] != 1):
            raise RecoveryRequired("invalid reservation intent")
        for key in ("before", "after"):
            digest = data[key]
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise RecoveryRequired("invalid reservation intent pin")
        token, expected = _intent(data["before"], data["after"])
        if raw != expected or path.name != f"intent-{token}.json":
            raise RecoveryRequired("reservation intent identity differs")
        complete = root / f"committed-{token}.json"
        if os.path.lexists(complete):
            if _read(complete) != raw:
                raise RecoveryRequired("reservation completion evidence differs")
        else:
            pending.append((data, token, raw))
    return pending


def _replace_state(root, prepared, verify, expected):
    temporary = root / f"pending-{uuid.uuid4().hex}.json"
    _write_once(temporary, prepared)
    _sync_directory(root)
    verify()
    if _read(root / "state.json") != expected:
        raise RecoveryRequired("reservation state changed before replacement")
    # Writers must share the lease. This is not a CAS against actors bypassing it.
    os.replace(temporary, root / "state.json")
    _sync_directory(root)


def initialize(directory, *bootstrap_args, **bootstrap_kwargs):
    """Explicit checked bootstrap, only in a brand-new dedicated directory.

    Any interrupted initialization remains in place and refuses reinitialization.
    Never use this to recreate missing state beside existing output generations.
    """
    plan = ids.bootstrap(*bootstrap_args, **bootstrap_kwargs)
    root = Path(directory).absolute()
    _root(root.parent)
    root.mkdir()  # Existing/partial stores refuse; no reset or automatic adoption.
    _write_once(root / "writer.lock", b"0")
    with _lease(root) as (root, verify):
        _write_once(root / f"prepared-{plan.sha256}.json", plan.state)
        verify()
        _write_once(root / "state.json", plan.state)
        _sync_directory(root)
        if _read(root / "state.json") != plan.state:
            raise RecoveryRequired("initial state differs from checked bootstrap")
    return plan


class Writer:
    def __init__(self, root, verify, raw):
        self.root, self._verify_lease, self.raw = root, verify, raw
        self.active = True

    def _verify(self):
        if not self.active:
            raise OSError("reservation session is closed")
        self._verify_lease()
        if _read(self.root / "state.json") != self.raw:
            raise RecoveryRequired("reservation state changed during session")
        if _pending(self.root):
            raise RecoveryRequired("reservation preparation requires explicit recovery")

    def reserve(self, base_raw, base_map_raw, sources, *, plugin):
        self._verify()
        plan = ids.reserve(self.raw, _sha(self.raw), base_raw, base_map_raw, sources, plugin=plugin)
        if plan.state == self.raw:
            return plan
        old = self.raw
        token, intent = _intent(_sha(old), plan.sha256)
        _write_once(self.root / f"previous-{_sha(old)}.json", old)
        _write_once(self.root / f"prepared-{plan.sha256}.json", plan.state)
        _write_once(self.root / f"intent-{token}.json", intent)
        _sync_directory(self.root)
        _replace_state(self.root, plan.state, self._verify_lease, old)
        if _read(self.root / "state.json") != plan.state:
            raise RecoveryRequired("published reservation state differs")
        _write_once(self.root / f"committed-{token}.json", intent)
        _sync_directory(self.root)
        self.raw = plan.state
        return plan


@contextmanager
def session(directory, expected_sha256):
    """Hold this context through the caller's separate paired-output transaction."""
    with _lease(directory) as (root, verify):
        raw = _read(root / "state.json")
        ids.validate_state(raw, expected_sha256)
        writer = Writer(root, verify, raw)
        try:
            writer._verify()
            yield writer
            writer._verify()
        finally:
            writer.active = False


def recover(directory, *, before_sha256, after_sha256):
    """Complete one explicitly pinned reservation preparation; no plugin recovery.

    Preserve old/new/intent bytes. A pre-replacement crash also retains the
    planned reservations instead of making their IDs available to another source.
    """
    with _lease(directory) as (root, verify):
        pending = _pending(root)
        if len(pending) != 1:
            raise RecoveryRequired("expected exactly one unresolved reservation preparation")
        data, token, intent = pending[0]
        if data["before"] != before_sha256 or data["after"] != after_sha256:
            raise RecoveryRequired("recovery pins differ from intent")
        before = _read(root / f"previous-{before_sha256}.json")
        after = _read(root / f"prepared-{after_sha256}.json")
        old = ids.validate_state(before, before_sha256)
        new = ids.validate_state(after, after_sha256)
        if (old["base"]["plugin"] != new["base"]["plugin"]
                or old["base"]["masters"] != new["base"]["masters"]
                or any(new["reservations"].get(k) != v for k, v in old["reservations"].items())
                or any(new["base"]["source_ids"].get(k) != v for k, v in old["base"]["source_ids"].items())
                or any(new["base"]["records"].get(k) != v for k, v in old["base"]["records"].items())
                or any(v < max(old["next_id"], new["base"]["next_id"])
                       for k, v in new["reservations"].items() if k not in old["reservations"])
                or new["next_id"] < old["next_id"]):
            raise RecoveryRequired("prepared state is not an append-only reservation transition")
        current = _read(root / "state.json")
        if current == before:
            _replace_state(root, after, verify, before)
        elif current != after:
            raise RecoveryRequired("current state is neither pinned recovery endpoint")
        verify()
        if _read(root / "state.json") != after:
            raise RecoveryRequired("recovered state differs")
        _write_once(root / f"committed-{token}.json", intent)
        _sync_directory(root)
        return after_sha256
