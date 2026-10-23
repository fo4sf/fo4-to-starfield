"""Reference format for the per-save sidecar file an SFSE plugin would keep beside each game save.

Why a sidecar (combined-core-notes/engine-feasibility.md, "In short" and section 1; the SFSE facts are verified there,
the sidecar design is the note's supported hypothesis until probe P1 runs): SFSE has no
working co-save (serialization disabled since 0.2.12, still off in 0.2.21), but it sends PreSaveGame, PostSaveGame,
PreLoadGame and PostLoadGame messages to plugins with the save name, so a plugin can write its own file keyed to that
name on save and read it back on load. SFSE says nothing when a save is deleted, so sidecars can be orphaned;
orphans() lists them and never deletes. Steam Cloud skipping the sidecar is a listed risk, not handled here.

This module is the offline codec of that file (the note's prototype item (c): "sidecar format and versioning as a
pure C++/Python codec with round-trip tests"). It runs on this PC, in Python, and claims nothing about the game: a
plugin would mirror the format, not import this. The body is JSON, sorted keys, so the same state writes the same
bytes:

    {"format": FORMAT, "schema": SCHEMA, "save_name": <exact save name>,
     "world_state": <WorldState.to_json() parsed>, "sha256": <hex sha256 of WorldState.to_json()>}

The checksum covers the canonical world state (model.WorldState.to_json, sort_keys JSON), so an edited or truncated
body fails read() with ValueError instead of loading half-right. The world state carries its own schema
(model.SCHEMA_VERSION); SCHEMA here versions only the envelope. Writes go to a temp file in the same directory and
then os.replace, so a crash mid-write leaves the old sidecar intact. Every number here is a placeholder or a
labelled assumption; there is no clock and no randomness.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile

from .model import WorldState

FORMAT = "focc-sidecar"
SCHEMA = 1
EXTENSION = ".focc"                  # engine-feasibility.md section 1 names "<save name>.focc"

# File-name rule: the save name with everything outside [A-Za-z0-9_.-] replaced by "_", cut to SAFE_NAME_MAX
# characters, then "-" and the first HASH_CHARS hex digits of sha256(save name), so two save names that differ only in
# replaced characters or beyond the cut still get distinct files. SAFE_NAME_MAX is an ASSUMPTION about path limits
# (kept well under common 255-byte file-name caps), not a measured engine fact.
SAFE_NAME_MAX = 80
HASH_CHARS = 8
_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")


def canonical_state(ws: WorldState) -> str:
    """The text the checksum covers: the world state's own sorted-keys JSON."""
    return ws.to_json()


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sidecar_name(save_name: str) -> str:
    """File name for `save_name` (module docstring rule). Raises ValueError for an empty name."""
    if not isinstance(save_name, str) or not save_name:
        raise ValueError("save name must be a non-empty string")
    safe = _UNSAFE.sub("_", save_name)[:SAFE_NAME_MAX].strip(".") or "save"
    return f"{safe}-{checksum(save_name)[:HASH_CHARS]}{EXTENSION}"


def sidecar_path(path_dir: str, save_name: str) -> str:
    return os.path.join(path_dir, sidecar_name(save_name))


def encode(save_name: str, ws: WorldState) -> str:
    """The sidecar body as text, deterministic for a given state."""
    state = canonical_state(ws)
    body = {"format": FORMAT, "schema": SCHEMA, "save_name": save_name,
            "world_state": json.loads(state), "sha256": checksum(state)}
    return json.dumps(body, sort_keys=True)


def decode(text: str, save_name: str | None = None) -> WorldState:
    """Parse and verify a sidecar body: format, schema, checksum and (when given) the save name must match, or
    ValueError. The world state is then loaded through WorldState.from_json, which checks its own schema."""
    try:
        body = json.loads(text)
    except ValueError as e:
        raise ValueError(f"sidecar is not JSON: {e}") from None
    if not isinstance(body, dict) or body.get("format") != FORMAT:
        raise ValueError(f"not a {FORMAT} file (format {body.get('format') if isinstance(body, dict) else None!r})")
    if body.get("schema") != SCHEMA:
        raise ValueError(f"unknown sidecar schema {body.get('schema')!r}, want {SCHEMA}")
    if save_name is not None and body.get("save_name") != save_name:
        raise ValueError(f"sidecar belongs to save {body.get('save_name')!r}, not {save_name!r}")
    if "world_state" not in body or "sha256" not in body:
        raise ValueError("sidecar lacks world_state or sha256")
    state = json.dumps(body["world_state"], sort_keys=True)
    if checksum(state) != body["sha256"]:
        raise ValueError("sidecar checksum mismatch: body edited or truncated")
    return WorldState.from_json(state)


def write(path_dir: str, save_name: str, ws: WorldState) -> str:
    """Write the sidecar for `save_name` under `path_dir` atomically (temp file, fsync, os.replace). Returns the
    path. An existing sidecar for the same save is replaced whole or not at all."""
    path = sidecar_path(path_dir, save_name)
    fd, tmp = tempfile.mkstemp(prefix=".focc-", suffix=".tmp", dir=path_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(encode(save_name, ws))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def read(path_dir: str, save_name: str) -> WorldState:
    """Load and verify the sidecar for `save_name`. FileNotFoundError when there is none (the plugin's cue to start
    from the Papyrus floor), ValueError on any mismatch or tamper."""
    with open(sidecar_path(path_dir, save_name), encoding="utf-8") as f:
        return decode(f.read(), save_name)


def orphans(sidecar_dir: str, existing_save_names) -> list[str]:
    """Sidecar files in `sidecar_dir` whose save is not in `existing_save_names`, sorted. Never deletes anything:
    SFSE gives no delete message (module docstring), so the plugin decides what to do with the list."""
    wanted = {sidecar_name(s) for s in existing_save_names}
    out = []
    for name in sorted(os.listdir(sidecar_dir)):
        if name.endswith(EXTENSION) and name not in wanted:
            out.append(os.path.join(sidecar_dir, name))
    return out
