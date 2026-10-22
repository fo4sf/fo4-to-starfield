"""File identity helpers shared by the manifest, the driver, restore and the same-ids check."""
import hashlib
import json
import os

CHUNK = 1 << 20
PLUGIN_EXT = (".esm", ".esp", ".esl")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def identity(path, hash_limit=None):
    """{"size", "mtime_ns"[, "sha256"]} of a file. The content hash is taken when hash_limit is None (always) or the
    file is at most hash_limit bytes; bigger files are identified by size and time only, the checkpoint policy of
    docs/RESUMING-BUILDS.md (archives must stay immutable during a run)."""
    st = os.stat(path)
    out = {"size": st.st_size, "mtime_ns": st.st_mtime_ns}
    if hash_limit is None or st.st_size <= hash_limit:
        out["sha256"] = sha256(path)
    return out


def tree(root, hash_limit=None, hash_ext=PLUGIN_EXT + (".json",)):
    """{relative/path: identity} of every file under root (sorted, "/" separators). Files with an extension in
    hash_ext are always hashed; others follow hash_limit."""
    files = {}
    for d, dirs, names in os.walk(root):
        dirs.sort()
        for n in sorted(names):
            p = os.path.join(d, n)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            files[rel] = identity(p, None if n.lower().endswith(hash_ext) else hash_limit)
    return files


def load_json(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path, value):
    """Atomic write (temp file + os.replace), so an interrupted run leaves the old file or the new one, never half."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=1, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
