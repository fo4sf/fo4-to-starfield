"""Retain private historical experiment receipts before cleanup changes them.

Only metadata is stored. A historical receipt does not prove live installation,
engine-loaded bytes, successful cleanup or a passing native test.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zlib


def receipt_directory():
    configured = os.environ.get("FO4SF_EXPERIMENT_RECEIPTS")
    if configured is not None:
        if not configured or not Path(configured).is_absolute():
            raise ValueError("FO4SF_EXPERIMENT_RECEIPTS must be an absolute private path")
        return Path(configured).resolve()
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "state"))
    return (base / "FO4SF" / "experiment-receipts").resolve()


def verify_copy(path, raw):
    if path.is_symlink() or not path.is_file():
        raise ValueError("historical receipt is not a regular file")
    # Bound decompression to the known source size, including the EOF/CRC check.
    try:
        with gzip.open(path, "rb") as saved:
            recovered = saved.read(len(raw) + 1)
    except (EOFError, zlib.error) as error:
        raise ValueError(f"historical receipt is incomplete or corrupt: {path}") from error
    if recovered != raw:
        raise ValueError(f"historical receipt differs from its source: {path}")


def preserve_receipt(record_path):
    """Create/reopen a content-addressed copy; never replace existing history.

    Failure is propagated before the caller changes Plugins.txt or game files.
    The active recovery record remains the only input to cleanup/resumption.
    """
    source = Path(record_path)
    raw = source.read_bytes()
    record = json.loads(raw)
    if not isinstance(record, dict):
        raise ValueError("experiment receipt must be an object")
    root = receipt_directory()
    excluded = [source.parent.parent.resolve()]
    if record.get("exp_dir"):
        excluded.append(Path(record["exp_dir"]).resolve())
    if any(root.is_relative_to(path) for path in excluded):
        raise ValueError("historical receipts must be outside the game and staging directories")
    root.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha256(raw).hexdigest() + ".json.gz"
    target = root / name
    if not target.exists() and not target.is_symlink():
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(prefix="receipt-", suffix=".tmp", dir=root, delete=False) as out:
                temporary = Path(out.name)
                out.write(gzip.compress(raw, compresslevel=6, mtime=0))
                out.flush()
                os.fsync(out.fileno())
            verify_copy(temporary, raw)
            try:
                # Same-volume hard-link publication is atomic and never replaces
                # another writer's file. Unlinking the temp leaves the snapshot.
                os.link(temporary, target)
            except FileExistsError:
                pass
        finally:
            if temporary is not None:
                temporary.unlink()
    verify_copy(target, raw)
    if source.read_bytes() != raw:
        raise ValueError("active experiment receipt changed while preserving it")
    return target
