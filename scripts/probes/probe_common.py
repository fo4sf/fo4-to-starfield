#!/usr/bin/env python3
"""Shared Round 12 probe validation, packaging, binary reuse, and atomic install helpers.

Consolidates R11/R12 probe conventions (standalone, zero bundle-installer dependency):
  - Preflight guards: `check_starfield_not_running`, `check_free_space_gb`, `check_out_dir_safe`
  - Hashing & safe staging: `sha256_file`, `copy_or_link_staged_file` (never hardlinks into frozen
    candidate/probe folders; copies `.esm`/`.pex`/`.json`/`.txt`/`.dll`/`.ini`/`.psc` with `st_nlink == 1`)
  - Tested binary reuse: `reuse_tested_binary`
  - Archive packing & hash verification: `pack_gnrl_ba2`, `pack_dx10_ba2`, `verify_ba2_entry_hashes`
  - P3 / Hop validation: `validate_batches_and_hops` (forbids `m`/`n`/`v` in batch filenames &
    console activate commands; `< 200 m`/axis hop checks from named anchors + interior cell guard)
  - ESM cleanliness checks: `scan_plugin_cleanliness` (forbids `WRLD`/`PNDT`/ext-`CELL` overrides
    on `FO4Core_Commonwealth`, and non-persistent cross-plugin `ObjectReference` VMAD properties)
  - Atomic install/uninstall/status: pre-checks `*.txt` collisions & base hashes (`FO4Port.esm`
    `07756819...`, warns if baseline != `candidate-2g-fix2`), writes planned swaps to receipt
    before file mutations, rolls back files and `Plugins.txt` on exception, stamps version tag.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys
import tempfile
import warnings
import zlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for _p in (str(SRC_DIR), str(SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deploy_starfield  # noqa: E402
from fo4sf.ba2 import Ba2  # noqa: E402
from fo4sf.core.cross_plugin_check import parse_binary_vmad_properties  # noqa: E402
from fo4sf.launcher.crashwatch import GAME_EXE, System  # noqa: E402
from fo4sf.planet.esm import PERSISTENT, Plugin, zstring  # noqa: E402

DEFAULT_MIN_FREE_GB = 60.0
DEFAULT_MAX_HOP_AXIS_M = 200.0
HASH_CHUNK_BYTES = 1 << 20
BA2_ALIGN = 0xBAADF00D
BA2_GNRL_FLAGS = 0x00100100

FROZEN_CANDIDATE_NAMES: Tuple[str, ...] = (
    "candidate-2",
    "candidate-2b",
    "candidate-2c",
    "candidate-2d",
    "candidate-2d-r7",
    "candidate-2e",
    "candidate-2f",
    "candidate-2g",
    "candidate-2g-fix",
    "candidate-2g-fix2",
)

FROZEN_PROBE_NAMES: Tuple[str, ...] = (
    "r11-p1-museum",
    "r11-p1-museum-v2",
    "r11-p4-10mm",
    "r11-p5-weapons",
)

COPY_ONLY_EXTENSIONS: frozenset[str] = frozenset({
    ".esm",
    ".pex",
    ".json",
    ".txt",
    ".dll",
    ".ini",
    ".psc",
})

# Pinned candidate-2g-fix2 core plugin hashes (player & test profiles).
CANDIDATE_2G_FIX2_HASHES: Dict[str, Union[str, Tuple[str, ...]]] = {
    "Data/FO4ActorRaider.esm": "bed4ef1adffdae8551e918091fbc7335df5ecbaf83efad6b3ffce797da9b01d3",
    "Data/FO4TerrainCore.esm": "dc75166449332f113825298adb94ec2c4b528145db440ebff450e6ec3e3c0fd9",
    "Data/FO4TerrainCore_Mars.esm": "8bba3ee91b1faa5f39619ffdf4d4d38fa1107ffe0a7889531714966ead885496",
    "Data/FO4SFCoreValues.esm": (
        "cc4a8a8a35ec08381fbed454996f23162b44db56a2aa61ea8afbddb70a7d14a6",  # player
        "ad5f259b64e061aee5498d0fdf7cec76bf145b7591686dc84eb524a79af0dab8",  # test
    ),
    "Data/FO4SFVaultGearDoor.esm": "7aada8bafa027bfd158c63e0728e10e7239401dde57429ba601b7b96a2ea8533",
    "Data/FO4SFExitLift.esm": "34d0db71d1116742d5d644a7772e8f31e43019b72bab9d01c91eec308665d9d4",
    "Data/FO4SFMission.esm": "b621c80ebc7637006a27734f4086271d131e6b44f79e417ceaf6bc812d991ba8",
    "Data/FO4SFNewGame.esm": (
        "0163600cbbe974a0344a858ddd483472a59e90b079632b394bac535cbd9d50f2",  # player
        "5c9edb843ced9eeaf505f8e0fd9255122d6bbbe4248308ccedbb36dbcc9a9e65",  # test
    ),
    "Data/FO4SFWorkshop.esm": "2a022bc720092cbb1118dea544fb2f2823041b3863919220b44e6c1a7dba67ad",
    "Data/FO4SFPowerArmor.esm": (
        "c3332aef3891f4cd647882e80da4f1c6238ba558b12d2c80c2fb32e5fd885c4c",  # player
        "d7f0fc494cca47c2cdf570b82368b6f7f4aca96b478aff179e230fed0a45e09d",  # test
    ),
}

BASE_FO4PORT_SHA256_PREFIX = "07756819"

TESTED_PIPBOY_DLL_SHA256_PREFIX = "7d5ba49c0c6ab2aa"
TESTED_PIPBOY_DLL_SHA256 = "7d5ba49c0c6ab2aa8db24ab1bfb643839259d12404cc95afaa38e2f42201c9a8"
TESTED_PIPBOY_DLL_SIZE = 1453568
TESTED_PIPBOY_SOURCE_HASHES: Dict[str, str] = {
    "xmake.lua": "00869296f54eeeadc4cdf4cf03cc580b87db27af953e5c8b29ef5b7ccbd9f472",
    "main.cpp": "c9c091a62349a498457dafdbfddadb4feb1985063c4c3cb858bf68db3b772acb",
    "pch.h": "7a64a825b8a26917ccc69c73c15f82f943252a038d406fab916234277e09122c",
    "pipboy_map.cpp": "cdf02e307d170bf92a1ac0c0c7d668ee075270132ed43ebf88800cfe0ee5a4cf",
    "pipboy_map.h": "1dcce102e16dfb75245908098a136dae3953e25b1cd95e9ed926d6f95cd4f2bb",
    "setup_places.h": "8e8661777d84c53edb103a36a1b5235c79f68ed4aabd8f6317339fbf70e7a354",
    "world.cpp": "eba9623a09f135ebb6f53fd823fa492c458499d5138f48ad8515dc761ed43982",
    "world.h": "040ba4591a37553adb9b7c7344640f5d70200ed521f767efb8f89303fe7ebcce",
    "FO4SFPipboyMenu.ini": "aa1b5ad3eb8538a12020bc3dadae6748d962c9133ae53a5ad4ab4f0687598162",
    "blocking_menus.h": "d41287aaf5c891eecb82edae4c880a1ff051936ff1c43dbe7ae798b22e96037d",
}
FO4CORE_COMMONWEALTH_LOCAL_ID = 0x000803
FO4CORE_COMMONWEALTH_WORLD_EDID = "FO4Core_Commonwealth"
FO4TERRAIN_CORE_PLUGIN = "FO4TerrainCore.esm"

LEGACY_DDS_FOURCC_TO_DXGI: Dict[bytes, int] = {
    b"DXT1": 71,
    b"DXT3": 74,
    b"DXT5": 77,
    b"ATI1": 80,
    b"BC4U": 80,
    b"BC4S": 81,
    b"ATI2": 83,
    b"BC5U": 83,
    b"BC5S": 84,
}


class ProbeError(RuntimeError):
    """Base error for Round 12 shared probe staging operations."""


class ProbePreflightError(ProbeError):
    """Game running or insufficient free disk space."""


class ProbeSafetyError(ProbeError):
    """Unsafe staging directory or frozen folder boundary violation."""


class ProbeValidationError(ProbeError):
    """Batch, hop, BA2 integrity, or ESM cleanliness rule failure."""


class ProbeInstallError(ProbeError):
    """Collision, base-hash mismatch, or atomic install/uninstall failure."""


@dataclass(frozen=True)
class BinaryReuseResult:
    """Result returned by `reuse_tested_binary`, usable directly as an `os.PathLike`."""

    path: Path
    reused: bool
    src_hash: str
    bin_sha256: str

    def __fspath__(self) -> str:
        return str(self.path)


@dataclass(frozen=True)
class AnchorPoint:
    """Named coordinate anchor for P3 hop validation."""

    name: str
    x: float
    y: float
    z: float
    cell_type: str = "exterior"
    cell: str = ""


@dataclass(frozen=True)
class HopSpec:
    """Target `setpos` hop anchored at a named reference point."""

    name: str
    from_anchor: str
    x: float
    y: float
    z: float
    cell_type: str = "exterior"
    cell: str = ""


# ---------------------------------------------------------------------------
# Hashing & Binary Reuse
# ---------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Union[str, os.PathLike[str]]) -> str:
    """Compute lowercase SHA-256 hex digest of a file in streaming chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(HASH_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def hash_source_files(src_files: Union[Union[str, os.PathLike[str]], Iterable[Union[str, os.PathLike[str]]]]) -> str:
    """Compute a worktree-independent SHA-256 digest over source files by sorted filename."""
    paths = [Path(src_files)] if isinstance(src_files, (str, os.PathLike)) else [Path(p) for p in src_files]
    if not paths:
        raise ProbeError("hash_source_files requires at least one file")
    records: List[Tuple[str, str]] = []
    for p in paths:
        if not p.is_file():
            raise FileNotFoundError(f"Source file missing: {p}")
        records.append((p.name.casefold(), sha256_file(p)))
    records.sort()
    h = hashlib.sha256()
    for name, fhash in records:
        h.update(f"{name}:{fhash}\n".encode("utf-8"))
    return h.hexdigest()


def _matches_hash_spec(actual_hex: str, expected_hex: str) -> bool:
    exp = expected_hex.strip().lower()
    if len(exp) < 8:
        raise ProbeError(f"Hash prefix must be at least 8 hex characters (got {expected_hex!r})")
    return actual_hex.lower().startswith(exp)


def reuse_tested_binary(
    src_files: Union[Union[str, os.PathLike[str]], Iterable[Union[str, os.PathLike[str]]]],
    tested_src_hash: Union[str, Mapping[str, str]],
    tested_bin_path: Union[str, os.PathLike[str]],
    fallback_build_fn: Callable[[], Union[str, os.PathLike[str]]],
    *,
    dst_path: Optional[Union[str, os.PathLike[str]]] = None,
) -> BinaryReuseResult:
    """Reuse a game-tested native/script binary whenever its sources still match `tested_src_hash`.

    `tested_src_hash` may be:
      - a full or prefix SHA-256 hex string matched against `hash_source_files(src_files)`
        (or single file `sha256_file` when exactly one file is passed), or
      - a mapping `{filename_or_path: sha256_hex}` matched per source file.
    """
    paths = [Path(src_files)] if isinstance(src_files, (str, os.PathLike)) else [Path(p) for p in src_files]
    if not paths:
        raise ProbeError("reuse_tested_binary requires non-empty src_files")
    for p in paths:
        if not p.is_file():
            raise FileNotFoundError(f"Source file for tested binary check does not exist: {p}")

    combined_hash = hash_source_files(paths)
    per_file_hashes = {p.name.casefold(): sha256_file(p) for p in paths}

    sources_match = False
    if isinstance(tested_src_hash, Mapping):
        if len(tested_src_hash) == len(paths):
            sources_match = all(
                (Path(k).name.casefold() in per_file_hashes)
                and _matches_hash_spec(per_file_hashes[Path(k).name.casefold()], v)
                for k, v in tested_src_hash.items()
            )
    else:
        single_hash = next(iter(per_file_hashes.values())) if len(paths) == 1 else ""
        sources_match = _matches_hash_spec(combined_hash, tested_src_hash) or (
            bool(single_hash) and _matches_hash_spec(single_hash, tested_src_hash)
        )

    tested_bin = Path(tested_bin_path)
    if sources_match and tested_bin.is_file() and tested_bin.stat().st_size > 0:
        out_p = tested_bin
        if dst_path is not None and Path(dst_path).resolve(strict=False) != tested_bin.resolve(strict=False):
            copy_or_link_staged_file(tested_bin, dst_path, allow_hardlink=False)
            out_p = Path(dst_path)
        return BinaryReuseResult(
            path=out_p,
            reused=True,
            src_hash=combined_hash,
            bin_sha256=sha256_file(out_p),
        )

    built_raw = fallback_build_fn()
    built = Path(built_raw)
    if not built.is_file() or built.stat().st_size == 0:
        raise ProbeError(f"fallback_build_fn did not produce a non-empty binary: {built}")
    out_p = built
    if dst_path is not None and Path(dst_path).resolve(strict=False) != built.resolve(strict=False):
        copy_or_link_staged_file(built, dst_path, allow_hardlink=False)
        out_p = Path(dst_path)
    return BinaryReuseResult(
        path=out_p,
        reused=False,
        src_hash=combined_hash,
        bin_sha256=sha256_file(out_p),
    )


# ---------------------------------------------------------------------------
# Preflight & Frozen-Folder Guards
# ---------------------------------------------------------------------------


def check_starfield_not_running(system: Optional[Any] = None) -> List[int]:
    """Raise `ProbePreflightError` if `Starfield.exe` is running or process inspection fails."""
    sys_obj = system if system is not None else System()
    try:
        pids = list(sys_obj.pids(GAME_EXE))
    except ValueError as exc:
        raise ProbePreflightError(str(exc)) from exc
    if pids:
        raise ProbePreflightError(f"{GAME_EXE} is running (PIDs={pids}); close the game before staging/installing.")
    return []


def check_free_space_gb(
    path_or_min: Union[str, os.PathLike[str], float, int] = "D:\\",
    min_gb: float = DEFAULT_MIN_FREE_GB,
    *,
    min: Optional[float] = None,  # noqa: A002 — matches brief kwarg `min=60.0`
) -> float:
    """Verify at least `min_gb` GiB free on the drive hosting `path_or_min`. Returns free GiB."""
    if isinstance(path_or_min, (int, float)):
        target_str = "D:\\"
        required_gb = float(min if min is not None else path_or_min)
    else:
        target_str = os.fspath(path_or_min)
        required_gb = float(min if min is not None else min_gb)

    probe = Path(os.path.abspath(target_str))
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    if not probe.exists():
        raise ProbePreflightError(f"Cannot resolve existing parent directory for free-space check: {target_str}")

    usage = shutil.disk_usage(str(probe))
    free_gb = usage.free / float(1024 ** 3)
    if free_gb < required_gb:
        raise ProbePreflightError(
            f"Insufficient free space at {probe}: {free_gb:.2f} GiB < {required_gb:.1f} GiB required."
        )
    return free_gb


def _frozen_folder_match(path: Path, extra_frozen_roots: Sequence[Union[str, os.PathLike[str]]] = ()) -> Optional[Path]:
    """Return matching frozen directory if `path` equals or lies inside a frozen candidate/probe dir."""
    resolved = Path(os.path.abspath(os.fspath(path)))
    for extra in extra_frozen_roots:
        er = Path(os.path.abspath(os.fspath(extra)))
        if resolved == er or er in resolved.parents:
            return er

    frozen_set = {n.casefold(): n for n in FROZEN_CANDIDATE_NAMES + FROZEN_PROBE_NAMES}
    chain = (resolved, *resolved.parents)
    for idx, node in enumerate(chain):
        low = node.name.casefold()
        if low in frozen_set and idx + 1 < len(chain):
            parent_low = chain[idx + 1].name.casefold()
            if low.startswith("candidate-") and parent_low == "gemini-core":
                return node
            if low.startswith("r11-p") and parent_low == "gemini-probes":
                return node
    return None


def is_frozen_probe_or_candidate_path(
    path: Union[str, os.PathLike[str]],
    extra_frozen_roots: Sequence[Union[str, os.PathLike[str]]] = (),
) -> bool:
    return _frozen_folder_match(Path(path), extra_frozen_roots) is not None


def _is_git_worktree_ancestor_or_child(path: Path) -> bool:
    resolved = Path(os.path.abspath(os.fspath(path)))
    for cand in (resolved, *resolved.parents):
        if (cand / ".git").exists():
            return True
    if (resolved / ".git").exists():
        return True
    return False


def _is_live_game_dir(path: Path) -> bool:
    resolved = Path(os.path.abspath(os.fspath(path)))
    for cand in (resolved, *resolved.parents):
        if (cand / GAME_EXE).is_file() or (cand / "Data" / "Starfield.esm").is_file():
            return True
    return False


def check_out_dir_safe(
    out_dir: Union[str, os.PathLike[str]],
    *,
    clean: bool = False,
    allow_inside_git: bool = False,
    extra_frozen_roots: Sequence[Union[str, os.PathLike[str]]] = (),
) -> Path:
    """Validate an output staging directory; refuse non-empty dirs unless `clean=True`."""
    raw = os.fspath(out_dir).strip()
    if not raw:
        raise ProbeSafetyError("Output directory must not be empty.")
    target = Path(os.path.abspath(raw))
    if target.parent == target:
        raise ProbeSafetyError(f"Refusing filesystem root as staging directory: {target}")
    if target.is_symlink():
        raise ProbeSafetyError(f"Refusing symlink/reparse point as staging directory: {target}")
    if target.name.casefold() in ("gemini-core", "gemini-probes", "fo4sf-owner-tests"):
        raise ProbeSafetyError(f"Refusing parent container directory as stage output: {target}")

    frozen_hit = _frozen_folder_match(target, extra_frozen_roots)
    if frozen_hit is not None:
        raise ProbeSafetyError(f"Refusing frozen directory {frozen_hit} as output target: {target}")
    if _is_live_game_dir(target):
        raise ProbeSafetyError(f"Refusing live Starfield installation path as staging output: {target}")
    if not allow_inside_git and _is_git_worktree_ancestor_or_child(target):
        raise ProbeSafetyError(f"Refusing Git repository/worktree directory as staging output: {target}")

    if target.exists():
        if not target.is_dir():
            raise ProbeSafetyError(f"Output path exists and is not a directory: {target}")
        if any(target.iterdir()):
            if not clean:
                raise ProbeSafetyError(
                    f"Output directory is non-empty ({target}); pass clean=True / --clean to overwrite."
                )
            for child in list(target.iterdir()):
                if child.is_symlink() or not child.is_dir():
                    child.unlink()
                else:
                    shutil.rmtree(child)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _atomic_copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".fo4sf_copy_", dir=str(dst.parent))
    os.close(fd)
    try:
        shutil.copy2(src, tmp_name)
        os.replace(tmp_name, dst)
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def copy_or_link_staged_file(
    src: Union[str, os.PathLike[str]],
    dst: Union[str, os.PathLike[str]],
    *,
    allow_hardlink: bool = True,
    extra_frozen_roots: Sequence[Union[str, os.PathLike[str]]] = (),
) -> str:
    """Stage `src` -> `dst`, returning `'copied'` or `'hardlinked'`.

    Safety invariants:
      - Never creates files or hardlinks inside frozen candidate/probe directories.
      - Never hardlinks *from* frozen `r11-p*` probe folders (nor any frozen folder when avoidable;
        copying guarantees frozen probe files retain `st_nlink == 1`).
      - `.esm`, `.pex`, `.json`, `.txt`, `.dll`, `.ini`, and `.psc` are ALWAYS atomically copied
        and verified to have `st_nlink == 1`.
    """
    src_p = Path(os.path.abspath(os.fspath(src)))
    dst_p = Path(os.path.abspath(os.fspath(dst)))
    if not src_p.is_file():
        raise FileNotFoundError(f"Staged source file does not exist: {src_p}")

    frozen_dst = _frozen_folder_match(dst_p, extra_frozen_roots)
    if frozen_dst is not None:
        raise ProbeSafetyError(f"Refusing to write or hardlink into frozen folder {frozen_dst}: {dst_p}")

    if src_p.resolve(strict=False) == dst_p.resolve(strict=False):
        if dst_p.suffix.lower() in COPY_ONLY_EXTENSIONS and os.lstat(dst_p).st_nlink != 1:
            raise ProbeSafetyError(f"Expected st_nlink == 1 on copy-only file {dst_p}")
        return "copied"

    src_frozen = _frozen_folder_match(src_p, extra_frozen_roots)
    must_copy = (
        not allow_hardlink
        or src_p.suffix.lower() in COPY_ONLY_EXTENSIONS
        or dst_p.suffix.lower() in COPY_ONLY_EXTENSIONS
        or src_frozen is not None
    )

    if not must_copy:
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        if dst_p.exists() or dst_p.is_symlink():
            dst_p.unlink()
        try:
            os.link(src_p, dst_p)
            return "hardlinked"
        except OSError:
            pass

    _atomic_copy_file(src_p, dst_p)
    nlink = os.lstat(dst_p).st_nlink
    if dst_p.suffix.lower() in COPY_ONLY_EXTENSIONS and nlink != 1:
        raise ProbeSafetyError(f"Copied file {dst_p} unexpectedly has st_nlink={nlink} (expected 1)")
    return "copied"


# ---------------------------------------------------------------------------
# GNRL / DX10 BA2 Packing & Verification
# ---------------------------------------------------------------------------


def bs_crc32(text: str) -> int:
    """Bethesda BA2 CRC32 (poly 0xEDB88320, init 0, no final xor) on lowercase backslash text."""
    return zlib.crc32(text.lower().replace("/", "\\").encode("latin-1"), 0xFFFFFFFF) ^ 0xFFFFFFFF


def _normalize_ba2_relpath(raw: str) -> str:
    norm = raw.replace("\\", "/").lstrip("/")
    if not norm or ":" in norm:
        raise ProbeValidationError(f"Invalid archive entry path: {raw!r}")
    parts = PurePosixPath(norm).parts
    if any(p in ("", ".", "..") for p in parts):
        raise ProbeValidationError(f"Traversal/empty segment in archive entry path: {raw!r}")
    return "/".join(parts).lower()


def _ba2_entry_hashes_and_ext(norm_rel: str) -> Tuple[int, bytes, int]:
    bs_path = norm_rel.replace("/", "\\")
    parent, _, base = bs_path.rpartition("\\")
    if "." in base:
        stem, _, ext_str = base.rpartition(".")
    else:
        stem, ext_str = base, ""
    ext_bytes = ext_str.lower().encode("ascii", "replace")[:4].ljust(4, b"\0")
    return bs_crc32(stem), ext_bytes, bs_crc32(parent)


def _materialize_entries(
    inputs: Union[Mapping[str, Union[bytes, os.PathLike[str], str]], Sequence[Tuple[str, Union[bytes, os.PathLike[str], str]]]],
) -> List[Tuple[str, bytes]]:
    items = list(inputs.items()) if isinstance(inputs, Mapping) else list(inputs)
    if not items:
        raise ProbeValidationError("Cannot pack empty BA2 archive.")
    seen: Set[str] = set()
    out: List[Tuple[str, bytes]] = []
    for raw_name, payload in items:
        norm = _normalize_ba2_relpath(raw_name)
        if norm in seen:
            raise ProbeValidationError(f"Duplicate BA2 entry path after normalization: {norm!r}")
        seen.add(norm)
        if isinstance(payload, (bytes, bytearray, memoryview)):
            data = bytes(payload)
        else:
            data = Path(payload).read_bytes()
        out.append((norm, data))
    return out


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".fo4sf_ba2_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def pack_gnrl_ba2(
    inputs: Union[Mapping[str, Union[bytes, os.PathLike[str], str]], Sequence[Tuple[str, Union[bytes, os.PathLike[str], str]]]],
    out_path: Union[str, os.PathLike[str]],
    *,
    compress: bool = False,
) -> Path:
    """Pack general files (meshes, scripts, audio, materials) into a Starfield v2 GNRL BA2."""
    entries = _materialize_entries(inputs)
    out = Path(out_path)
    extra = struct.pack("<II", 1, 0)
    offset = 24 + len(extra) + 36 * len(entries)
    records: List[bytes] = []
    payloads: List[bytes] = []
    names: List[bytes] = []

    for norm_name, data in entries:
        nh, ext, dh = _ba2_entry_hashes_and_ext(norm_name)
        payload = zlib.compress(data) if compress else data
        packed_sz = len(payload) if compress else 0
        records.append(
            struct.pack("<I4sIIQIII", nh, ext, dh, BA2_GNRL_FLAGS, offset, packed_sz, len(data), BA2_ALIGN)
        )
        payloads.append(payload)
        enc = norm_name.encode("utf-8")
        names.append(struct.pack("<H", len(enc)) + enc)
        offset += len(payload)

    header = struct.pack("<4sI4sIQ", b"BTDX", 2, b"GNRL", len(entries), offset)
    _atomic_write_bytes(out, header + extra + b"".join(records) + b"".join(payloads) + b"".join(names))
    return out


pack_gnrl_ba2_v2 = pack_gnrl_ba2


def _parse_dds_for_dx10(dds: bytes, name: str) -> Tuple[int, int, int, int, bool, bytes]:
    if len(dds) < 128 or dds[:4] != b"DDS ":
        raise ProbeValidationError(f"{name}: not a valid DDS file (missing 'DDS ' magic or < 128 bytes)")
    dw_size, _flags, height, width, _pitch, _depth, mips = struct.unpack_from("<7I", dds, 4)
    if dw_size != 124 or width <= 0 or height <= 0:
        raise ProbeValidationError(f"{name}: invalid DDS header dimensions ({width}x{height})")
    mips = max(mips, 1)
    pf_flags = struct.unpack_from("<I", dds, 80)[0]
    fourcc = dds[84:88]
    caps2 = struct.unpack_from("<I", dds, 112)[0]
    if fourcc == b"DX10":
        if len(dds) < 148:
            raise ProbeValidationError(f"{name}: truncated DX10 DDS header (< 148 bytes)")
        dxgi, _res_dim, misc_flag = struct.unpack_from("<3I", dds, 128)
        cubemap = bool(misc_flag & 0x4)
        body = dds[148:]
    else:
        cubemap = bool(caps2 & 0x200)
        if fourcc in LEGACY_DDS_FOURCC_TO_DXGI:
            dxgi = LEGACY_DDS_FOURCC_TO_DXGI[fourcc]
        elif pf_flags & 0x40:
            dxgi = 87  # uncompressed B8G8R8A8_UNORM
        else:
            raise ProbeValidationError(f"{name}: unsupported legacy DDS pixel format fourcc={fourcc!r}")
        body = dds[128:]
    if not body:
        raise ProbeValidationError(f"{name}: DDS contains 0 pixel payload bytes")
    return width, height, mips, dxgi, cubemap, body


def pack_dx10_ba2(
    inputs: Union[Mapping[str, Union[bytes, os.PathLike[str], str]], Sequence[Tuple[str, Union[bytes, os.PathLike[str], str]]]],
    out_path: Union[str, os.PathLike[str]],
    *,
    compress: bool = False,
) -> Path:
    """Pack `.dds` textures into a Starfield v2 DX10 BA2 archive."""
    entries = _materialize_entries(inputs)
    out = Path(out_path)
    extra = struct.pack("<II", 1, 0)
    offset = 24 + len(extra) + 48 * len(entries)
    records: List[bytes] = []
    payloads: List[bytes] = []
    names: List[bytes] = []

    for norm_name, dds in entries:
        width, height, mips, dxgi, cubemap, body = _parse_dds_for_dx10(dds, norm_name)
        nh, ext, dh = _ba2_entry_hashes_and_ext(norm_name)
        chunk_data = zlib.compress(body) if compress else body
        packed_sz = len(chunk_data) if compress else 0
        flags = 1 if cubemap else 0
        records.append(
            struct.pack("<I4sIBBHHHBBBB", nh, ext, dh, 0, 1, 24, height, width, mips, dxgi, flags, 8)
            + struct.pack("<QIIHHI", offset, packed_sz, len(body), 0, mips - 1, BA2_ALIGN)
        )
        payloads.append(chunk_data)
        enc = norm_name.encode("utf-8")
        names.append(struct.pack("<H", len(enc)) + enc)
        offset += len(chunk_data)

    header = struct.pack("<4sI4sIQ", b"BTDX", 2, b"DX10", len(entries), offset)
    _atomic_write_bytes(out, header + extra + b"".join(records) + b"".join(payloads) + b"".join(names))
    return out


pack_dx10_ba2_v2 = pack_dx10_ba2
pack_textures_ba2 = pack_dx10_ba2


def _inspect_ba2_entry_crc_headers(ba2_path: Path, expected_names: Sequence[str]) -> None:
    with open(ba2_path, "rb") as f:
        hdr = f.read(24)
        magic, version, kind_b, count, _ = struct.unpack("<4sI4sIQ", hdr)
        if magic != b"BTDX":
            raise ProbeValidationError(f"{ba2_path}: not a BA2 archive")
        extra_len = 8 if version == 2 else 12 if version == 3 else 0
        f.seek(24 + extra_len)
        if count != len(expected_names):
            raise ProbeValidationError(f"{ba2_path}: header entry count mismatch")
        for idx, raw_name in enumerate(expected_names):
            norm = _normalize_ba2_relpath(raw_name)
            exp_nh, exp_ext, exp_dh = _ba2_entry_hashes_and_ext(norm)
            if kind_b == b"GNRL":
                nh, ext, dh, _fl, _off, _pk, _up, _al = struct.unpack("<I4sIIQIII", f.read(36))
            else:
                nh, ext, dh, _u, nch, _csz, _h, _w, _m, _fmt, _fl, _tl = struct.unpack("<I4sIBBHHHBBBB", f.read(24))
                f.read(24 * nch)
            if nh != exp_nh or dh != exp_dh or ext.lower() != exp_ext.lower():
                raise ProbeValidationError(
                    f"{ba2_path}: entry {idx} ({raw_name}) bad BS CRC32/ext header "
                    f"(got nh=0x{nh:08X} dh=0x{dh:08X} ext={ext!r}, "
                    f"expected nh=0x{exp_nh:08X} dh=0x{exp_dh:08X} ext={exp_ext!r})"
                )


def verify_ba2_entry_hashes(
    ba2_path: Union[str, os.PathLike[str]],
    expected_hashes: Optional[Mapping[str, str]] = None,
    *,
    source_files: Optional[Mapping[str, Union[str, os.PathLike[str]]]] = None,
    check_crc32: bool = True,
) -> Dict[str, str]:
    """Verify BA2 structure, BS CRC32 headers, and unpacked entry SHA-256 hashes.

    Returns `{normalized_rel_path: sha256_of_unpacked_bytes}`.
    """
    bp = Path(ba2_path)
    if not bp.is_file():
        raise ProbeValidationError(f"BA2 file missing: {bp}")
    arc = Ba2(str(bp))
    if check_crc32:
        _inspect_ba2_entry_crc_headers(bp, arc.names)

    actual_hashes: Dict[str, str] = {}
    actual_body_hashes: Dict[str, str] = {}
    for idx, entry in enumerate(arc.entries):
        norm = _normalize_ba2_relpath(entry.name)
        data = arc.read(idx)
        actual_hashes[norm] = sha256_bytes(data)
        if arc.kind == "DX10" and len(data) >= 148:
            actual_body_hashes[norm] = sha256_bytes(data[148:])

    if expected_hashes is not None:
        exp_norm = {_normalize_ba2_relpath(k): v.lower() for k, v in expected_hashes.items()}
        if set(actual_hashes) != set(exp_norm):
            missing = sorted(set(exp_norm) - set(actual_hashes))
            extra = sorted(set(actual_hashes) - set(exp_norm))
            raise ProbeValidationError(f"{bp}: BA2 entry set mismatch missing={missing} extra={extra}")
        for norm, exp_h in exp_norm.items():
            if actual_hashes[norm] != exp_h and actual_body_hashes.get(norm) != exp_h:
                raise ProbeValidationError(
                    f"{bp}: entry {norm} SHA-256 mismatch (got {actual_hashes[norm]}, expected {exp_h})"
                )

    if source_files is not None:
        src_norm = {_normalize_ba2_relpath(k): Path(v) for k, v in source_files.items()}
        if set(actual_hashes) != set(src_norm):
            missing = sorted(set(src_norm) - set(actual_hashes))
            extra = sorted(set(actual_hashes) - set(src_norm))
            raise ProbeValidationError(f"{bp}: BA2 vs source coverage mismatch missing={missing} extra={extra}")
        for norm, src_p in src_norm.items():
            raw = src_p.read_bytes()
            if arc.kind == "GNRL":
                exp_h = sha256_bytes(raw)
                if actual_hashes[norm] != exp_h:
                    raise ProbeValidationError(f"{bp}: GNRL entry {norm} differs from source {src_p}")
            else:
                w, h, mips, dxgi, cubemap, body = _parse_dds_for_dx10(raw, norm)
                ent = arc.entries[arc.find(norm)]
                if (ent.width, ent.height, ent.mips, ent.dxgi, ent.cubemap) != (w, h, mips, dxgi, cubemap):
                    raise ProbeValidationError(f"{bp}: DX10 metadata mismatch on {norm}")
                if actual_body_hashes.get(norm) != sha256_bytes(body):
                    raise ProbeValidationError(f"{bp}: DX10 pixel data mismatch on {norm} vs {src_p}")

    return actual_hashes


# ---------------------------------------------------------------------------
# P3 Batches, Console Activate Rules & <200m/Axis Hop Checks
# ---------------------------------------------------------------------------

_MNV_RE = re.compile(r"[mnv]", re.I)
_STRIPPED_FO4SF_CMD_RE = re.compile(r"^\s*(?:set|help|setstage)\s+FO4SF_", re.I)
_BAT_INVOKE_RE = re.compile(r"^\s*bat\s+([^\s;#]+)", re.I)


def _coerce_anchor(item: Union[AnchorPoint, Mapping[str, Any]]) -> AnchorPoint:
    if isinstance(item, AnchorPoint):
        return item
    return AnchorPoint(
        name=str(item["name"]),
        x=float(item["x"]),
        y=float(item["y"]),
        z=float(item["z"]),
        cell_type=str(item.get("cell_type", "exterior")).lower(),
        cell=str(item.get("cell", "")),
    )


def _coerce_hop(item: Union[HopSpec, Mapping[str, Any]]) -> HopSpec:
    if isinstance(item, HopSpec):
        return item
    return HopSpec(
        name=str(item["name"]),
        from_anchor=str(item["from_anchor"]),
        x=float(item["x"]),
        y=float(item["y"]),
        z=float(item["z"]),
        cell_type=str(item.get("cell_type", "exterior")).lower(),
        cell=str(item.get("cell", "")),
    )


def validate_batches_and_hops(
    *,
    batch_files: Sequence[Union[str, os.PathLike[str]]] = (),
    activate_commands: Sequence[str] = (),
    anchors: Union[Mapping[str, Union[AnchorPoint, Mapping[str, Any]]], Sequence[Union[AnchorPoint, Mapping[str, Any]]]] = (),
    hops: Sequence[Union[HopSpec, Mapping[str, Any]]] = (),
    max_axis_m: float = DEFAULT_MAX_HOP_AXIS_M,
    interior_mode: bool = False,
    raise_on_error: bool = True,
) -> List[str]:
    """Validate P3 zero-`M/N/V` batch/activate naming and `< 200 m`/axis hop rules + interior cell guard.

    Returns error strings (`[]` if clean). When `raise_on_error=True`, raises `ProbeValidationError`.
    """
    errors: List[str] = []

    for bf in batch_files:
        p = Path(bf)
        if _MNV_RE.search(p.name):
            errors.append(f"P3 forbids letters M/N/V in batch filename: {p.name!r}")
        if p.is_file():
            for ln_no, raw in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                line = raw.strip()
                if not line or line.startswith(";"):
                    continue
                if _STRIPPED_FO4SF_CMD_RE.match(line):
                    errors.append(f"{p.name}:{ln_no}: stripped FO4SF_* EditorID forbidden in batch: {line!r}")

    for cmd in activate_commands:
        line = cmd.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        if _MNV_RE.search(line):
            errors.append(f"P3 forbids letters M/N/V in console activate/command line: {line!r}")
        m_bat = _BAT_INVOKE_RE.match(line)
        if m_bat and _MNV_RE.search(m_bat.group(1)):
            errors.append(f"P3 forbids letters M/N/V in activated batch name: {m_bat.group(1)!r}")
        if _STRIPPED_FO4SF_CMD_RE.match(line):
            errors.append(f"P3 forbids stripped FO4SF_* EditorID in console command: {line!r}")

    anchor_map: Dict[str, AnchorPoint] = {}
    anchor_items = anchors.values() if isinstance(anchors, Mapping) else anchors
    for item in anchor_items:
        anc = _coerce_anchor(item)
        if not (math.isfinite(anc.x) and math.isfinite(anc.y) and math.isfinite(anc.z)):
            errors.append(f"Anchor {anc.name!r} has non-finite coordinates")
        if anc.cell_type not in ("exterior", "interior"):
            errors.append(f"Anchor {anc.name!r} has invalid cell_type {anc.cell_type!r}")
        anchor_map[anc.name] = anc

    for raw_hop in hops:
        hop = _coerce_hop(raw_hop)
        if not (math.isfinite(hop.x) and math.isfinite(hop.y) and math.isfinite(hop.z)):
            errors.append(f"Hop {hop.name!r} has non-finite coordinates")
            continue
        if hop.cell_type not in ("exterior", "interior"):
            errors.append(f"Hop {hop.name!r} has invalid cell_type {hop.cell_type!r}")
            continue
        if interior_mode and hop.cell_type != "interior":
            errors.append(f"Interior cell guard: exterior hop {hop.name!r} not allowed in interior-only probe")
            continue
        anc = anchor_map.get(hop.from_anchor)
        if anc is None:
            errors.append(f"Hop {hop.name!r} references unknown anchor {hop.from_anchor!r}")
            continue
        if anc.cell_type != hop.cell_type:
            errors.append(
                f"Interior cell guard: hop {hop.name!r} ({hop.cell_type}) cannot setpos from "
                f"{anc.name!r} ({anc.cell_type})"
            )
            continue
        if hop.cell_type == "interior" and anc.cell and hop.cell and anc.cell.casefold() != hop.cell.casefold():
            errors.append(
                f"Interior cell guard: hop {hop.name!r} cell {hop.cell!r} != anchor {anc.name!r} cell {anc.cell!r}"
            )
            continue

        dx, dy, dz = abs(hop.x - anc.x), abs(hop.y - anc.y), abs(hop.z - anc.z)
        if max(dx, dy, dz) >= max_axis_m:
            errors.append(
                f"Hop {hop.name!r} from {anc.name!r} exceeds <{max_axis_m:g}m/axis limit: "
                f"dx={dx:.2f}, dy={dy:.2f}, dz={dz:.2f}"
            )

    if raise_on_error and errors:
        raise ProbeValidationError("; ".join(errors))
    return errors


# ---------------------------------------------------------------------------
# ESM Binary Cleanliness Scanner
# ---------------------------------------------------------------------------


def _scan_single_esm_for_index(
    esm_path: Path,
    ref_index: Dict[Tuple[str, int], Tuple[str, str, bool]],
) -> None:
    plugin_key = esm_path.name.casefold()
    with Plugin(str(esm_path)) as plg:
        masters = tuple(plg.masters)
        self_idx = plg.self_index
        for grp in plg.groups:
            for start, end in plg.groups[grp]:
                for item in plg.walk(start, end):
                    if item[0] != "REC":
                        continue
                    sig_b = item[2]
                    if sig_b not in (b"REFR", b"ACHR"):
                        continue
                    rec = plg.record_at(item[1])
                    owner_idx = (rec.formid >> 24) & 0xFF
                    local_id = rec.formid & 0xFFFFFF
                    if owner_idx == self_idx or owner_idx >= len(masters):
                        tgt_key = plugin_key
                    else:
                        tgt_key = masters[owner_idx].casefold()
                    is_pers = bool(rec.flags & PERSISTENT)
                    key = (tgt_key, local_id)
                    if owner_idx == self_idx or key not in ref_index or not is_pers:
                        ref_index[key] = (sig_b.decode("latin1"), rec.edid, is_pers)


def _walk_wrld_group_cleanliness(
    plg: Plugin,
    plugin_name: str,
    masters: Sequence[str],
    tc_idx: Optional[int],
    errors: List[str],
    start: int,
    end: int,
    in_commonwealth_wrld: bool = False,
) -> None:
    self_idx = plg.self_index
    current_wrld_is_cw = in_commonwealth_wrld
    off = start
    while off < end:
        sig = bytes(plg.buf[off:off + 4])
        if sig == b"GRUP":
            _, size, _label, gtype, _, _ = struct.unpack_from("<4sI4siII", plg.buf, off)
            child_cw = current_wrld_is_cw if gtype == 1 else in_commonwealth_wrld
            _walk_wrld_group_cleanliness(
                plg, plugin_name, masters, tc_idx, errors, off + 24, off + size, child_cw
            )
            off += size
            continue

        size = struct.unpack_from("<I", plg.buf, off + 4)[0]
        rec = plg.record_at(off)
        owner_idx = (rec.formid >> 24) & 0xFF
        local_id = rec.formid & 0xFFFFFF
        edid = rec.edid

        if sig == b"WRLD":
            is_cw_override = (
                (tc_idx is not None and owner_idx == tc_idx and local_id == FO4CORE_COMMONWEALTH_LOCAL_ID)
                or (
                    edid.casefold() == FO4CORE_COMMONWEALTH_WORLD_EDID.casefold()
                    and plugin_name.casefold() != FO4TERRAIN_CORE_PLUGIN.casefold()
                )
            )
            current_wrld_is_cw = is_cw_override
            if is_cw_override:
                errors.append(
                    f"{plugin_name}: forbidden WRLD override on {FO4CORE_COMMONWEALTH_WORLD_EDID} "
                    f"(0x{rec.formid:08X})"
                )
        elif sig == b"CELL":
            data_sub = rec.get(b"DATA")
            cell_flags = struct.unpack_from("<H", data_sub, 0)[0] if data_sub and len(data_sub) >= 2 else 0
            is_interior = bool(cell_flags & 0x0001)
            is_master_override = owner_idx < self_idx
            is_tc_override = tc_idx is not None and owner_idx == tc_idx
            if current_wrld_is_cw or (not is_interior and is_tc_override) or (
                not is_interior and rec.get(b"XCLC") is not None and is_master_override and tc_idx is not None
            ):
                if not is_interior:
                    errors.append(
                        f"{plugin_name}: forbidden exterior CELL override on {FO4CORE_COMMONWEALTH_WORLD_EDID} "
                        f"(0x{rec.formid:08X} {edid!r})"
                    )
        off += 24 + size


def scan_plugin_cleanliness(
    esm_paths: Sequence[Union[str, os.PathLike[str]]],
    *,
    reference_esms: Sequence[Union[str, os.PathLike[str]]] = (),
    allow_pndt_plugins: Iterable[str] = (),
    raise_on_error: bool = True,
) -> List[str]:
    """Scan `.esm` plugins for forbidden Commonwealth host overrides and non-persistent VMAD refs.

    Checks every plugin in `esm_paths`:
      1. Zero `WRLD`, `PNDT`, or exterior `CELL` overrides touching `FO4Core_Commonwealth`
         (and zero `PNDT` records unless the plugin basename is in `allow_pndt_plugins` AND
         does not override a master `PNDT`).
      2. Zero cross-plugin VMAD `Object` / `Object[]` properties targeting a non-persistent
         (`flags & 0x0400 == 0`) `REFR` / `ACHR` found across `esm_paths + reference_esms`.
    """
    errors: List[str] = []
    targets = [Path(p) for p in esm_paths]
    all_esms = list(dict.fromkeys([*targets, *(Path(p) for p in reference_esms)]))
    allow_pndt = {name.casefold() for name in allow_pndt_plugins}

    ref_index: Dict[Tuple[str, int], Tuple[str, str, bool]] = {}
    for p in all_esms:
        if not p.is_file():
            errors.append(f"ESM file missing: {p}")
            continue
        _scan_single_esm_for_index(p, ref_index)

    for p in targets:
        if not p.is_file():
            continue
        plugin_name = p.name
        plugin_key = plugin_name.casefold()
        with Plugin(str(p)) as plg:
            masters = tuple(plg.masters)
            self_idx = plg.self_index
            masters_low = [m.casefold() for m in masters]
            tc_idx = masters_low.index(FO4TERRAIN_CORE_PLUGIN.casefold()) if FO4TERRAIN_CORE_PLUGIN.casefold() in masters_low else None

            # 1. PNDT check
            for start, end in plg.groups.get("PNDT", []):
                for item in plg.walk(start, end):
                    if item[0] == "REC" and item[2] == b"PNDT":
                        rec = plg.record_at(item[1])
                        owner_idx = (rec.formid >> 24) & 0xFF
                        if plugin_key not in allow_pndt or owner_idx < self_idx:
                            errors.append(
                                f"{plugin_name}: forbidden PNDT record/override (0x{rec.formid:08X} {rec.edid!r})"
                            )

            # 2. WRLD & exterior CELL check
            for start, end in plg.groups.get("WRLD", []):
                _walk_wrld_group_cleanliness(plg, plugin_name, masters, tc_idx, errors, start, end, False)

            for start, end in plg.groups.get("CELL", []):
                for item in plg.walk(start, end):
                    if item[0] == "REC" and item[2] == b"CELL":
                        rec = plg.record_at(item[1])
                        owner_idx = (rec.formid >> 24) & 0xFF
                        data_sub = rec.get(b"DATA")
                        cell_flags = struct.unpack_from("<H", data_sub, 0)[0] if data_sub and len(data_sub) >= 2 else 0
                        is_interior = bool(cell_flags & 0x0001)
                        if tc_idx is not None and owner_idx == tc_idx and not is_interior:
                            errors.append(
                                f"{plugin_name}: forbidden exterior CELL override in CELL group "
                                f"(0x{rec.formid:08X} {rec.edid!r})"
                            )

            # 3. VMAD cross-plugin non-persistent ObjectReference check
            for grp in plg.groups:
                for start, end in plg.groups[grp]:
                    for item in plg.walk(start, end):
                        if item[0] != "REC":
                            continue
                        rec = plg.record_at(item[1])
                        vmad_raw = rec.get(b"VMAD")
                        if vmad_raw is None:
                            continue
                        rec_label = rec.edid or f"0x{rec.formid & 0xFFFFFF:06X}"
                        for prop in parse_binary_vmad_properties(vmad_raw, masters, plugin_name, rec_label):
                            for _alias, tgt_plg, tgt_local in prop.object_refs:
                                if tgt_plg.casefold() == plugin_key:
                                    continue
                                info = ref_index.get((tgt_plg.casefold(), tgt_local))
                                if info is not None:
                                    tgt_sig, tgt_edid, is_pers = info
                                    if tgt_sig in ("REFR", "ACHR") and not is_pers:
                                        errors.append(
                                            f"{plugin_name}:{rec_label} {prop.script_name}.{prop.prop_name} "
                                            f"references non-persistent cross-plugin {tgt_sig} "
                                            f"{tgt_plg}:0x{tgt_local:06X} ({tgt_edid!r})"
                                        )

    if raise_on_error and errors:
        raise ProbeValidationError("\n".join(errors))
    return errors


# ---------------------------------------------------------------------------
# Atomic Install, Uninstall, Status & Version Tagging
# ---------------------------------------------------------------------------


def _receipt_path(starfield_dir: Path, probe_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", probe_id)
    return starfield_dir / "Data" / f".fo4sf_probe_{safe_id}.json"


def _backup_root(starfield_dir: Path, probe_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", probe_id)
    return starfield_dir / "Data" / ".fo4sf_probe_backup" / safe_id


def _normalize_target_rel(rel: str) -> str:
    clean = rel.replace("\\", "/").lstrip("/")
    if not clean or ":" in clean or any(p in ("", ".", "..") for p in PurePosixPath(clean).parts):
        raise ProbeInstallError(f"Unsafe target relative path: {rel!r}")
    return clean


def _load_stage_file_specs(
    stage_dir: Path,
    files: Optional[Sequence[Mapping[str, Any]]],
) -> List[Dict[str, Any]]:
    if files is None:
        manifest_p = stage_dir / "manifest.json"
        if not manifest_p.is_file():
            raise ProbeInstallError(f"Stage manifest missing: {manifest_p}")
        manifest = json.loads(manifest_p.read_text(encoding="utf-8-sig"))
        raw_files = manifest.get("files") or manifest.get("install_files") or manifest.get("staged_files")
        if isinstance(raw_files, Mapping):
            specs = [dict({"target_rel": k}, **v) if isinstance(v, Mapping) else {"target_rel": k, "src_rel": v}
                     for k, v in raw_files.items()]
        elif isinstance(raw_files, list):
            specs = [dict(x) for x in raw_files]
        else:
            raise ProbeInstallError(f"Manifest {manifest_p} lacks 'files' list or mapping")
    else:
        specs = [dict(x) for x in files]

    if not specs:
        raise ProbeInstallError("No files declared for probe installation")
    return specs


def _resolve_plugins_txt(starfield_dir: Path, plugins_txt: Optional[Union[str, os.PathLike[str]]]) -> Path:
    if plugins_txt is not None:
        return Path(plugins_txt)
    p = deploy_starfield.plugins_txt_path()
    if p and os.path.dirname(p):
        return Path(p)
    return starfield_dir / "Plugins.txt"


def _plan_plugins_txt(
    plugins_path: Path,
    plugins_to_activate: Sequence[str],
) -> Tuple[Optional[bytes], Optional[bytes], List[str], List[Dict[str, str]]]:
    if not plugins_to_activate:
        orig = plugins_path.read_bytes() if plugins_path.is_file() else None
        return orig, orig, [], []

    original_bytes = plugins_path.read_bytes() if plugins_path.is_file() else None
    lines = original_bytes.decode("utf-8-sig").splitlines() if original_bytes is not None else []
    added: List[str] = []
    replaced: List[Dict[str, str]] = []
    cur = list(lines)
    for plugin in plugins_to_activate:
        cur, step_added, step_replaced = deploy_starfield.plan_port_activation(cur, plugin_esm=plugin)
        added.extend(step_added)
        replaced.extend(step_replaced)
    planned_bytes = deploy_starfield.render_lines(cur, original_bytes)
    return original_bytes, planned_bytes, added, replaced


def _write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".fo4sf_rcpt_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def check_baseline_against_2g_fix2(
    starfield_dir: Path,
    baseline_2g_fix2_hashes: Optional[Mapping[str, Union[str, Sequence[str]]]] = None,
) -> List[str]:
    """Compare installed base files against pinned `candidate-2g-fix2` hashes; return warning strings."""
    ref_map = CANDIDATE_2G_FIX2_HASHES if baseline_2g_fix2_hashes is None else baseline_2g_fix2_hashes
    warn_msgs: List[str] = []
    for rel, expected in sorted(ref_map.items()):
        p = starfield_dir / _normalize_target_rel(rel)
        if not p.is_file():
            continue
        actual = sha256_file(p)
        accepted = (expected,) if isinstance(expected, str) else tuple(expected)
        if not any(_matches_hash_spec(actual, exp) for exp in accepted):
            exp_desc = "/".join(e[:16] + "..." for e in accepted)
            msg = (
                f"WARNING: installed {rel} (sha256={actual[:16]}...) does not match "
                f"candidate-2g-fix2 baseline ({exp_desc})"
            )
            warn_msgs.append(msg)
            warnings.warn(msg, RuntimeWarning, stacklevel=2)
    return warn_msgs


def stamp_version_in_card(
    card_path: Union[str, os.PathLike[str]],
    version_tag: str,
) -> Path:
    """Stamp `version_tag` into a staged probe card (`Version Tag:` line or appended metadata line)."""
    p = Path(card_path)
    if not p.is_file():
        raise FileNotFoundError(f"Card file does not exist for version stamping: {p}")
    text = p.read_text(encoding="utf-8")
    if not version_tag:
        return p

    pattern = re.compile(r"(?m)^([>\-\s]*\*\*Version Tag:\*\*)\s*.*$")
    if pattern.search(text):
        updated = pattern.sub(rf"\1 `{version_tag}`", text, count=1)
    else:
        lines = text.splitlines()
        insert_at = 1 if lines else 0
        lines.insert(insert_at, f"> - **Version Tag:** `{version_tag}`")
        updated = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    p.write_text(updated, encoding="utf-8", newline="\n")
    return p


def _other_receipts_owned_paths(starfield_dir: Path, current_probe_id: str) -> Dict[str, str]:
    data_dir = starfield_dir / "Data"
    owned: Dict[str, str] = {}
    if not data_dir.is_dir():
        return owned
    own_name = _receipt_path(starfield_dir, current_probe_id).name.casefold()
    for p in data_dir.glob(".fo4sf_probe_*.json"):
        if p.name.casefold() == own_name:
            continue
        try:
            other = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        other_id = str(other.get("probe_id", p.stem))
        for item in other.get("planned_adds", ()) + other.get("planned_swaps", ()):
            t_rel = item.get("target_rel")
            if isinstance(t_rel, str):
                owned[t_rel.casefold()] = other_id
    return owned


def _restore_from_receipt(starfield_dir: Path, receipt: Dict[str, Any], *, force: bool = False) -> None:
    errors: List[str] = []

    # 1. Restore Plugins.txt first if we mutated it or flagged restore
    plugins_path = Path(receipt["plugins_txt"])
    orig_b64 = receipt.get("plugins_original_b64")
    planned_b64 = receipt.get("plugins_planned_b64")
    if orig_b64 != planned_b64:
        orig_bytes = base64.b64decode(orig_b64) if isinstance(orig_b64, str) else None
        planned_bytes = base64.b64decode(planned_b64) if isinstance(planned_b64, str) else None
        cur_bytes = plugins_path.read_bytes() if plugins_path.is_file() else None
        if cur_bytes != orig_bytes:
            if not force and cur_bytes is not None and planned_bytes is not None and cur_bytes != planned_bytes:
                # Try targeted line removal/restoration matching deploy_starfield pattern
                try:
                    lines = cur_bytes.decode("utf-8-sig").splitlines()
                    added_cf = {ln.casefold() for ln in receipt.get("plugins_added", ())}
                    replaced_cf = {
                        item["active"].casefold(): item["original"]
                        for item in receipt.get("plugins_replaced", ())
                    }
                    restored_lines: List[str] = []
                    for ln in lines:
                        k = ln.casefold()
                        if k in replaced_cf:
                            restored_lines.append(replaced_cf.pop(k))
                        elif k in added_cf:
                            added_cf.remove(k)
                        else:
                            restored_lines.append(ln)
                    new_bytes = deploy_starfield.render_lines(restored_lines, cur_bytes)
                    deploy_starfield.atomic_write_bytes(str(plugins_path), new_bytes, ".fo4sf-plg-", expected_current=cur_bytes)
                except Exception as exc:
                    errors.append(f"Plugins.txt concurrent edit prevented clean restore: {exc}")
            elif orig_bytes is None:
                if plugins_path.is_file():
                    plugins_path.unlink()
            else:
                deploy_starfield.atomic_write_bytes(
                    str(plugins_path), orig_bytes, ".fo4sf-plg-", expected_current=cur_bytes
                )

    # 2. Remove added files (planned_adds were verified absent pre-install)
    remaining_adds: List[Dict[str, Any]] = []
    for item in receipt.get("planned_adds", ()):
        rel = item["target_rel"]
        dst = starfield_dir / rel
        if not dst.exists() and not dst.is_symlink():
            continue
        if not dst.is_symlink() and not force and sha256_file(dst) != item["new_sha256"]:
            errors.append(f"Added file changed since install (preserved): {rel}")
            remaining_adds.append(item)
            continue
        try:
            dst.unlink()
        except OSError as exc:
            errors.append(f"Failed removing {rel}: {exc}")
            remaining_adds.append(item)
    receipt["planned_adds"] = remaining_adds

    # 3. Restore backed-up swaps
    remaining_swaps: List[Dict[str, Any]] = []
    for item in receipt.get("planned_swaps", ()):
        rel = item["target_rel"]
        dst = starfield_dir / rel
        bkp = Path(item["backup_path"])
        if not bkp.is_file():
            errors.append(f"Missing backup for swapped file {rel}: {bkp}")
            remaining_swaps.append(item)
            continue
        if sha256_file(bkp) != item["pre_sha256"]:
            errors.append(f"Corrupt backup SHA-256 for {rel}")
            remaining_swaps.append(item)
            continue
        try:
            _atomic_copy_file(bkp, dst)
            if sha256_file(dst) != item["pre_sha256"]:
                raise ProbeInstallError(f"Post-restore SHA-256 mismatch on {rel}")
            bkp.unlink()
        except Exception as exc:
            errors.append(f"Failed restoring {rel}: {exc}")
            remaining_swaps.append(item)
    receipt["planned_swaps"] = remaining_swaps

    rcpt_path = _receipt_path(starfield_dir, receipt["probe_id"])
    bkp_dir = _backup_root(starfield_dir, receipt["probe_id"])
    if errors:
        _write_json_atomic(rcpt_path, receipt)
        raise ProbeInstallError("; ".join(errors))

    if bkp_dir.exists():
        shutil.rmtree(bkp_dir, ignore_errors=True)
    if rcpt_path.exists():
        rcpt_path.unlink()


def install_probe(
    *,
    probe_id: str,
    stage_dir: Union[str, os.PathLike[str]],
    starfield_dir: Union[str, os.PathLike[str]],
    plugins_txt: Optional[Union[str, os.PathLike[str]]] = None,
    plugins_to_activate: Sequence[str] = (),
    files: Optional[Sequence[Mapping[str, Any]]] = None,
    expected_base_hashes: Optional[Mapping[str, str]] = None,
    baseline_2g_fix2_hashes: Optional[Mapping[str, Union[str, Sequence[str]]]] = None,
    version_tag: str = "",
    card_path: Optional[Union[str, os.PathLike[str]]] = None,
    min_free_gb: float = DEFAULT_MIN_FREE_GB,
    allow_hardlink: bool = True,
    extra_frozen_roots: Sequence[Union[str, os.PathLike[str]]] = (),
    system: Optional[Any] = None,
    _fault_hook: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Atomically install a staged probe into `starfield_dir`, backing up swaps before mutation.

    Pre-checks:
      - `Starfield.exe` closed and free disk space >= `min_free_gb` GiB.
      - No existing installation receipt for `probe_id` and no ownership conflict with other receipts.
      - `*.txt` target collision pre-check (case-insensitive duplicates and unowned pre-existing `.txt`).
      - Required `expected_base_hashes` match, plus `candidate-2g-fix2` baseline mismatch warning.
    Writes the full planned swap/add plan to the receipt BEFORE any target files or `Plugins.txt`
    are modified, and automatically rolls back all changes + `Plugins.txt` if any exception occurs.
    """
    check_starfield_not_running(system)
    stage_p = Path(stage_dir)
    sf_p = Path(starfield_dir)
    check_free_space_gb(sf_p, min_gb=min_free_gb)

    rcpt_p = _receipt_path(sf_p, probe_id)
    if rcpt_p.exists():
        raise ProbeInstallError(f"Probe {probe_id!r} already has an active/pending receipt at {rcpt_p}")

    # 1. Baseline 2g-fix2 warning check + required base-hash checks
    baseline_warnings = check_baseline_against_2g_fix2(sf_p, baseline_2g_fix2_hashes)
    if expected_base_hashes:
        for rel, exp_h in expected_base_hashes.items():
            norm_rel = _normalize_target_rel(rel)
            tgt = sf_p / norm_rel
            if not tgt.is_file():
                raise ProbeInstallError(f"Required base file missing for {probe_id!r}: {norm_rel}")
            act_h = sha256_file(tgt)
            if not _matches_hash_spec(act_h, exp_h):
                raise ProbeInstallError(
                    f"Base hash mismatch on {norm_rel}: got {act_h}, expected {exp_h}"
                )

    # 2. Load staged files, check collisions & other probe ownership
    specs = _load_stage_file_specs(stage_p, files)
    other_owned = _other_receipts_owned_paths(sf_p, probe_id)
    seen_targets: Set[str] = set()
    planned_adds: List[Dict[str, Any]] = []
    planned_swaps: List[Dict[str, Any]] = []
    bkp_dir = _backup_root(sf_p, probe_id)

    for entry in specs:
        src_rel = str(entry.get("src_rel") or entry.get("src") or entry.get("target_rel"))
        tgt_rel = _normalize_target_rel(str(entry.get("target_rel") or entry.get("dst") or src_rel))
        tgt_key = tgt_rel.casefold()
        if tgt_key in seen_targets:
            raise ProbeInstallError(f"Duplicate target path in probe plan (case collision): {tgt_rel}")
        seen_targets.add(tgt_key)

        if tgt_key in other_owned:
            raise ProbeInstallError(f"Target collision with active probe {other_owned[tgt_key]!r}: {tgt_rel}")

        src_file = Path(src_rel) if os.path.isabs(src_rel) else (stage_p / src_rel)
        if not src_file.is_file():
            raise ProbeInstallError(f"Staged source file missing: {src_file}")
        new_hash = sha256_file(src_file)
        if entry.get("sha256") and not _matches_hash_spec(new_hash, str(entry["sha256"])):
            raise ProbeInstallError(f"Staged SHA-256 mismatch on {src_file}: {new_hash} != {entry['sha256']}")

        tgt_file = sf_p / tgt_rel
        allow_swap = bool(entry.get("allow_swap") or entry.get("swap") or (
            expected_base_hashes and any(_normalize_target_rel(k).casefold() == tgt_key for k in expected_base_hashes)
        ))
        if tgt_file.exists() or tgt_file.is_symlink():
            if tgt_file.is_symlink():
                raise ProbeInstallError(f"Refusing symlink/dangling-symlink target path: {tgt_rel}")
            if tgt_rel.lower().endswith(".txt") and not allow_swap:
                raise ProbeInstallError(f"Pre-check *.txt collision: unowned {tgt_rel} already exists")
            if not allow_swap:
                raise ProbeInstallError(
                    f"Target already exists without declared swap approval: {tgt_rel}"
                )
            pre_hash = sha256_file(tgt_file)
            bkp_path = bkp_dir / tgt_rel
            _atomic_copy_file(tgt_file, bkp_path)
            if sha256_file(bkp_path) != pre_hash:
                raise ProbeInstallError(f"Backup verification failed for {tgt_rel}")
            planned_swaps.append({
                "src_path": str(src_file),
                "target_rel": tgt_rel,
                "pre_sha256": pre_hash,
                "new_sha256": new_hash,
                "backup_path": str(bkp_path),
            })
        else:
            planned_adds.append({
                "src_path": str(src_file),
                "target_rel": tgt_rel,
                "new_sha256": new_hash,
            })

    # 3. Plan Plugins.txt BEFORE mutation
    plg_path = _resolve_plugins_txt(sf_p, plugins_txt)
    orig_b, planned_b, plg_added, plg_replaced = _plan_plugins_txt(plg_path, plugins_to_activate)

    receipt: Dict[str, Any] = {
        "schema": "fo4sf.r12_probe_receipt.v1",
        "probe_id": probe_id,
        "version_tag": version_tag,
        "stage_dir": str(stage_p),
        "starfield_dir": str(sf_p),
        "complete": False,
        "baseline_warnings": baseline_warnings,
        "plugins_txt": str(plg_path),
        "plugins_original_b64": base64.b64encode(orig_b).decode("ascii") if orig_b is not None else None,
        "plugins_planned_b64": base64.b64encode(planned_b).decode("ascii") if planned_b is not None else None,
        "plugins_added": plg_added,
        "plugins_replaced": plg_replaced,
        "plugins_requested": [f"*{deploy_starfield.plugin_name(p)}" for p in plugins_to_activate],
        "planned_adds": planned_adds,
        "planned_swaps": planned_swaps,
        "published_files": [],
    }
    # Write planned swaps/adds BEFORE creating links/files or touching Plugins.txt
    _write_json_atomic(rcpt_p, receipt)

    try:
        if _fault_hook:
            _fault_hook("before_files")

        for item in planned_swaps + planned_adds:
            dst = sf_p / item["target_rel"]
            copy_or_link_staged_file(
                item["src_path"],
                dst,
                allow_hardlink=allow_hardlink,
                extra_frozen_roots=extra_frozen_roots,
            )
            if sha256_file(dst) != item["new_sha256"]:
                raise ProbeInstallError(f"Post-install SHA-256 verification failed on {item['target_rel']}")
            receipt["published_files"].append(item["target_rel"])
            if _fault_hook:
                _fault_hook(f"after_file:{item['target_rel']}")

        if planned_b != orig_b and planned_b is not None:
            plg_path.parent.mkdir(parents=True, exist_ok=True)
            deploy_starfield.atomic_write_bytes(
                str(plg_path), planned_b, ".fo4sf-plg-", expected_current=orig_b
            )
            if _fault_hook:
                _fault_hook("after_plugins")

        receipt["complete"] = True
        receipt["installed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        _write_json_atomic(rcpt_p, receipt)

        if card_path is not None and version_tag:
            stamp_version_in_card(card_path, version_tag)

        return receipt
    except BaseException:
        try:
            _restore_from_receipt(sf_p, receipt, force=True)
        except Exception as rollback_exc:
            raise ProbeInstallError(
                f"Install aborted and rollback also encountered error: {rollback_exc}"
            ) from rollback_exc
        raise


def uninstall_probe(
    *,
    probe_id: str,
    starfield_dir: Union[str, os.PathLike[str]],
    force: bool = False,
    system: Optional[Any] = None,
) -> Dict[str, Any]:
    """Atomically uninstall a probe and restore `Plugins.txt` and backed-up swaps by SHA-256."""
    check_starfield_not_running(system)
    sf_p = Path(starfield_dir)
    rcpt_p = _receipt_path(sf_p, probe_id)
    if not rcpt_p.is_file():
        raise ProbeInstallError(f"No probe receipt found for {probe_id!r} at {rcpt_p}")
    receipt = json.loads(rcpt_p.read_text(encoding="utf-8"))
    summary = {
        "probe_id": probe_id,
        "version_tag": receipt.get("version_tag", ""),
        "restored_swaps": [x["target_rel"] for x in receipt.get("planned_swaps", ())],
        "removed_adds": [x["target_rel"] for x in receipt.get("planned_adds", ())],
    }
    _restore_from_receipt(sf_p, receipt, force=force)
    return summary


def probe_status(
    *,
    probe_id: str,
    starfield_dir: Union[str, os.PathLike[str]],
    baseline_2g_fix2_hashes: Optional[Mapping[str, Union[str, Sequence[str]]]] = None,
) -> Dict[str, Any]:
    """Read-only status check for an installed (or absent/partial) probe."""
    sf_p = Path(starfield_dir)
    rcpt_p = _receipt_path(sf_p, probe_id)
    baseline_warnings = check_baseline_against_2g_fix2(sf_p, baseline_2g_fix2_hashes)
    if not rcpt_p.is_file():
        return {
            "probe_id": probe_id,
            "installed": False,
            "state": "not_installed",
            "version_tag": "",
            "baseline_warnings": baseline_warnings,
            "file_problems": [],
        }

    receipt = json.loads(rcpt_p.read_text(encoding="utf-8"))
    file_problems: List[str] = []
    for item in receipt.get("planned_adds", ()) + receipt.get("planned_swaps", ()):
        rel = item["target_rel"]
        tgt = sf_p / rel
        if not tgt.is_file():
            file_problems.append(f"missing: {rel}")
        elif sha256_file(tgt) != item["new_sha256"]:
            file_problems.append(f"sha256_mismatch: {rel}")

    plugins_ok = True
    plg_path = Path(receipt["plugins_txt"])
    expected_active: List[str] = []
    seen_active: Set[str] = set()
    for ln in (
        list(receipt.get("plugins_added", ()))
        + [
            item["active"]
            for item in receipt.get("plugins_replaced", ())
            if isinstance(item, Mapping) and isinstance(item.get("active"), str)
        ]
        + list(receipt.get("plugins_requested", ()))
    ):
        k = ln.casefold()
        if k not in seen_active:
            seen_active.add(k)
            expected_active.append(ln)
    if expected_active:
        lines = plg_path.read_text(encoding="utf-8-sig").splitlines() if plg_path.is_file() else []
        lines_cf = {ln.casefold() for ln in lines}
        for pl in expected_active:
            if pl.casefold() not in lines_cf:
                plugins_ok = False
                file_problems.append(f"plugins_txt_missing_active: {pl}")

    complete = bool(receipt.get("complete", False))
    state = "installed" if (complete and not file_problems) else ("partial" if not complete else "degraded")
    return {
        "probe_id": probe_id,
        "installed": complete and not file_problems,
        "state": state,
        "version_tag": receipt.get("version_tag", ""),
        "baseline_warnings": baseline_warnings or receipt.get("baseline_warnings", []),
        "plugins_ok": plugins_ok,
        "file_problems": file_problems,
    }
