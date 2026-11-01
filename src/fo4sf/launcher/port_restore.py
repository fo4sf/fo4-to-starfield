"""Read-only validation of the already-built artifacts a recorded port restore must replay."""
import os
import re

from . import files

PLUGIN = "FO4Port.esm"
ARCHIVE = "FO4Port - Main.ba2"
TEX_ARCHIVE = "FO4Port - Textures.ba2"
CORE = "FO4TerrainCore.esm"
DEPLOYED_FILES = frozenset((PLUGIN, ARCHIVE, TEX_ARCHIVE))
COMPANION_RX = re.compile(r"^FO4PortTextures([2-9]|[1-9]\d+)(\.esm| - Textures\.ba2)$")


def snapshot_spec(target):
    rec = target["records"].get("port") or {}
    cores = [v for k, v in target.get("data_top", {}).items() if k.casefold() == CORE.casefold()]
    if len(cores) > 1:
        raise ValueError("snapshot has ambiguous core filenames")
    core = cores[0]["sha256"] if cores else None
    return {"schema": 1, "files": rec.get("files"), "artifacts": rec.get("artifacts"), "core_sha256": core}


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_spec(spec):
    if not isinstance(spec, dict) or spec.get("schema") != 1 or "core_sha256" not in spec:
        raise ValueError("recorded port spec needs schema 1 and its target core identity")
    names, arts = spec.get("files"), spec.get("artifacts")
    if (not isinstance(names, list) or not all(isinstance(n, str) and
            (n in DEPLOYED_FILES or COMPANION_RX.fullmatch(n)) for n in names)
            or len(set(names)) != len(names) or PLUGIN not in names or ARCHIVE not in names
            or not isinstance(arts, dict) or set(names) != set(arts)):
        raise ValueError("recorded port files/artifacts must describe the same complete port set")
    companions = [n for n in names if n.endswith(".esm") and n != PLUGIN]
    paired = {n for n in names if COMPANION_RX.fullmatch(n) and not n.endswith(".esm")}
    if paired != {n[:-4] + " - Textures.ba2" for n in companions}:
        raise ValueError("recorded port texture companion cohort is incomplete")
    for name in names:
        identity = arts[name]
        if (not isinstance(identity, dict) or set(identity) != {"size", "sha256"} or
                not _sha(identity.get("sha256")) or
                type(identity.get("size")) is not int or identity["size"] < 16):
            raise ValueError(f"recorded {name} needs its complete size and sha256 identity")
    if spec["core_sha256"] is not None and not _sha(spec["core_sha256"]):
        raise ValueError("recorded target core sha256 is missing or malformed")
    return companions


def check_stage(stage, spec):
    """Return (source/name/identity tuples, companions), or refuse; never build or modify an artifact."""
    companions = validate_spec(spec)
    if not stage or not os.path.isdir(stage):
        raise ValueError("port staging folder is missing")
    root = os.path.realpath(stage)
    artifact_root = root
    if (os.path.isdir(os.path.join(root, "port")) and
            not any(os.path.isfile(os.path.join(root, d, PLUGIN)) for d in ("", "Data"))):
        artifact_root = os.path.join(root, "port")
    metadata_roots = {root, artifact_root}
    if (os.path.basename(root).casefold() == "port" and
            os.path.isfile(os.path.join(os.path.dirname(root), "result.json"))):
        metadata_roots.add(os.path.dirname(root))
    for directory in sorted(metadata_roots):
        for filename, flag in (("build-state.json", "complete"), ("result.json", "pass")):
            path = os.path.join(directory, filename)
            if os.path.exists(path):
                state = files.load_json(path)
                if not isinstance(state, dict) or state.get(flag) is not True:
                    raise ValueError(f"port {filename} is incomplete or failed")
    items = []
    for name in spec["files"]:
        candidates = [os.path.join(artifact_root, d, name) for d in ("Data", "")]
        source = next((p for p in candidates if os.path.isfile(p)), None)
        if source is None:
            raise ValueError(f"port staged {name} is missing")
        if os.path.commonpath((root, os.path.realpath(source))) != root:
            raise ValueError(f"port staged {name} leaves its source folder")
        want = spec["artifacts"][name]
        with open(source, "rb") as stream:
            head = stream.read(4)
        if (head != (b"TES4" if name.endswith(".esm") else b"BTDX") or
                os.path.getsize(source) != want["size"] or files.sha256(source) != want["sha256"]):
            raise ValueError(f"port staged {name} differs from the snapshot")
        items.append((source, name, dict(want)))
    return items, companions


def check_core(data, spec):
    validate_spec(spec)
    names = [n for n in os.listdir(data) if n.casefold() == CORE.casefold()]
    if len(names) > 1:
        raise ValueError("installed core filenames are ambiguous")
    have = files.sha256(os.path.join(data, names[0])) if names else None
    if have != spec["core_sha256"]:
        raise ValueError("installed core differs from the recorded restore target")
