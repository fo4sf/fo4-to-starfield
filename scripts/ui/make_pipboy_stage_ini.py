#!/usr/bin/env python3
"""Generate the shipped FO4SFPipboyMenu.ini for a private Pip-Boy stage folder (Task 1 steps 1a, 1f, 1g).

Inspects every staged SWF movie under <stage>/Data/Interface via AVM2 DoABC bytecode (no committed name list in Git),
extracts every BGSCodeObj method called by the movies (both BGSExternalInterface.call and direct BGSCodeObj/codeObj
calls), optionally stages pipboybootsequence.swf from Fallout4 - Interface.ba2, enforces a strict coverage check so
the stage fails if any movie calls an unregistered name (unless --allow-omit <name> is passed for negative crash tests),
and writes a clean Stage=2 FO4SFPipboyMenu.ini with Pause=1 default and ZERO [Kit], [Page ...], or Kit* entries.

Refuses any output path inside a Git worktree or a game installation directory (Rule R4).
"""
from __future__ import annotations

import argparse
import os
import re
import struct
import sys
import zlib
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (str(HERE), str(REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pipboy_map_store  # noqa: E402
import swf_names  # noqa: E402

MAX_CODE_NAMES = 64
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
CODE_HOLDERS = frozenset({"BGSCodeObj", "codeObj", "_codeObj"})
DEFAULT_MAP_MENUS = "GalaxyStarMapMenu,SurfaceMap,MapMenu"
DEFAULT_BOOT_MOVIE = "pipboybootsequence"
DEFAULT_SPECIAL_MOVIE = "fo4sf_specialmenu"
SPECIAL_MENU_SWFS = frozenset({"specialmenu.swf", "fo4sf_specialmenu.swf"})
NON_SHELL_AUX_SWFS = frozenset({"fo4sf_startcard.swf", "fo4sf_setupscreen.swf"})
SPECIAL_MENU_SUPPORTED_CODEOBJ = frozenset({
    "initMenu",
    "modValue",
    "startEditText",
    "endEditText",
    "confirmResetPoints",
    "tryCloseMenu",
    "playSound",
    "PlayPerkSound",
    "StopPerkSound",
    "OnScrollingStarted",
    "OnScrollingStopped",
})

CANONICAL_MOVIE_PRIORITY = (
    "fo4sf_fo4shell.swf",
    "pipboymenu.swf",
    "pipboy_statspage.swf",
    "pipboy_invpage.swf",
    "pipboy_datapage.swf",
    "pipboy_mappage.swf",
    "pipboy_radiopage.swf",
    "components/pipboymessagebox.swf",
    "pipboymessagebox.swf",
    "pipboybootsequence.swf",
    "fo4sf_fo4boot.swf",
)


class StageIniError(ValueError):
    pass


def refuse_unsafe_output_path(path: os.PathLike | str) -> Path:
    """Refuse writing staged files inside any Git worktree or game folder (Rule R4)."""
    try:
        resolved = pipboy_map_store.refuse_unsafe_output_path(path)
    except pipboy_map_store.MapStoreError as exc:
        raise StageIniError(str(exc)) from exc
    return Path(resolved)


def _read_abc_consts_and_pools(abc_bytes: bytes) -> Tuple[List[str], List[str], Dict[str, str]]:
    """Return `(multiname_names, strings, const_string_traits)` from raw AVM2 ABC bytes."""
    r = swf_names.Reader(abc_bytes)
    if len(abc_bytes) < 8:
        raise StageIniError("ABC block too short")
    r.skip(4)  # minor, major
    for _ in range(2):  # int, uint pools
        cnt = r.u30()
        for _i in range(max(cnt - 1, 0)):
            r.u30()
    dbl_cnt = r.u30()
    r.skip(8 * max(dbl_cnt - 1, 0))

    strings = [""]
    for _ in range(max(r.u30() - 1, 0)):
        slen = r.u30()
        strings.append(bytes(r.b[r.at:r.at + slen]).decode("utf-8", errors="replace"))
        r.skip(slen)

    for _ in range(max(r.u30() - 1, 0)):  # namespaces
        r.u8()
        r.u30()
    for _ in range(max(r.u30() - 1, 0)):  # namespace sets
        for _j in range(r.u30()):
            r.u30()

    mns = [""]
    for _ in range(max(r.u30() - 1, 0)):
        kind = r.u8()
        if kind in (0x07, 0x0D):  # QName, QNameA
            r.u30()
            sidx = r.u30()
            mns.append(strings[sidx] if 0 <= sidx < len(strings) else "")
        elif kind in (0x0F, 0x10):  # RTQName, RTQNameA
            sidx = r.u30()
            mns.append(strings[sidx] if 0 <= sidx < len(strings) else "")
        elif kind in (0x11, 0x12):  # RTQNameL, RTQNameLA
            mns.append("*")
        elif kind in (0x09, 0x0E):  # Multiname, MultinameA
            sidx = r.u30()
            r.u30()
            mns.append(strings[sidx] if 0 <= sidx < len(strings) else "")
        elif kind in (0x1B, 0x1C):  # MultinameL, MultinameLA
            r.u30()
            mns.append("*")
        elif kind == 0x1D:  # TypeName (Vector.<T>)
            r.u30()
            for _p in range(r.u30()):
                r.u30()
            mns.append("")
        else:
            raise StageIniError(f"unsupported ABC multiname kind 0x{kind:02x}")

    if r.at >= len(abc_bytes):
        return mns, strings, {}

    for _ in range(r.u30()):  # method_info
        pcnt = r.u30()
        r.u30()
        for _p in range(pcnt):
            r.u30()
        r.u30()
        flags = r.u8()
        if flags & 0x08:
            for _o in range(r.u30()):
                r.u30()
                r.u8()
        if flags & 0x80:
            for _p in range(pcnt):
                r.u30()

    for _ in range(r.u30()):  # metadata
        r.u30()
        for _m in range(r.u30()):
            r.u30()
            r.u30()

    consts: Dict[str, str] = {}

    def _scan_traits() -> None:
        for _t in range(r.u30()):
            tname_idx = r.u30()
            kb = r.u8()
            kind = kb & 0x0F
            tname = mns[tname_idx] if 0 <= tname_idx < len(mns) else ""
            if kind in (0, 6):  # Slot / Const
                r.u30()
                r.u30()
                vidx = r.u30()
                if vidx:
                    vkind = r.u8()
                    if kind == 6 and vkind == 0x01 and 0 <= vidx < len(strings) and tname:
                        consts[tname] = strings[vidx]
            elif kind in (1, 2, 3, 4, 5):
                r.u30()
                r.u30()
            else:
                raise StageIniError(f"unsupported ABC trait kind {kind}")
            if kb & 0x40:
                for _m in range(r.u30()):
                    r.u30()

    cls_cnt = r.u30()
    for _ in range(cls_cnt):
        r.u30()
        r.u30()
        flags = r.u8()
        if flags & 0x08:
            r.u30()
        for _i in range(r.u30()):
            r.u30()
        r.u30()
        _scan_traits()
    for _ in range(cls_cnt):
        r.u30()
        _scan_traits()
    for _ in range(r.u30()):
        r.u30()
        _scan_traits()

    return mns, strings, consts


def _decode_abc_body(code: bytes, mns: Sequence[str], strings: Sequence[str]) -> List[Tuple[int, object, object]]:
    r = swf_names.Reader(code)
    out: List[Tuple[int, object, object]] = []
    while r.at < len(code):
        op = r.u8()
        if op in swf_names._NONE:
            out.append((op, None, None))
        elif op in swf_names._U30:
            out.append((op, r.u30(), None))
        elif op in swf_names._MN:
            idx = r.u30()
            out.append((op, mns[idx] if 0 <= idx < len(mns) else "", idx))
        elif op in swf_names._MN_ARGS:
            idx = r.u30()
            argc = r.u30()
            out.append((op, mns[idx] if 0 <= idx < len(mns) else "", argc))
        elif op in swf_names._S24:
            r.skip(3)
            out.append((op, None, None))
        elif op == swf_names.OP_PUSHSTRING:
            idx = r.u30()
            out.append((op, strings[idx] if 0 <= idx < len(strings) else "", None))
        elif op == swf_names.OP_NEWFUNCTION:
            out.append((op, r.u30(), None))
        elif op in (swf_names.OP_PUSHBYTE, swf_names.OP_GETSCOPEOBJECT):
            out.append((op, r.u8(), None))
        elif op in (swf_names.OP_HASNEXT2, swf_names.OP_CALLMETHOD, swf_names.OP_CALLSTATIC):
            out.append((op, r.u30(), r.u30()))
        elif op == swf_names.OP_LOOKUPSWITCH:
            r.skip(3)
            cnt = r.u30()
            r.skip(3 * (cnt + 1))
            out.append((op, None, None))
        elif op == swf_names.OP_DEBUG:
            r.u8()
            r.u30()
            r.u8()
            r.u30()
            out.append((op, None, None))
        else:
            break
    return out


def extract_swf_codeobj_calls(swf_bytes: bytes) -> List[str]:
    """Extract all BGSCodeObj method names invoked in an AVM2 SWF movie, in discovery order."""
    if len(swf_bytes) < 8 or swf_bytes[:3] not in (b"CWS", b"FWS"):
        raise StageIniError("input is not an uncompressed (FWS) or zlib-compressed (CWS) SWF")
    body = zlib.decompress(swf_bytes[8:]) if swf_bytes[:3] == b"CWS" else swf_bytes[8:]
    if not body:
        return []
    nbits = body[0] >> 3
    pos = (5 + 4 * nbits + 7) // 8 + 4
    ordered: List[str] = []
    seen: Set[str] = set()

    def _record(name: str) -> None:
        if IDENT_RE.fullmatch(name) and name not in seen:
            seen.add(name)
            ordered.append(name)

    while pos + 2 <= len(body):
        head = struct.unpack_from("<H", body, pos)[0]
        code, size = head >> 6, head & 0x3F
        pos += 2
        if size == 0x3F:
            if pos + 4 > len(body):
                raise StageIniError("truncated SWF long tag header")
            size = struct.unpack_from("<I", body, pos)[0]
            pos += 4
        payload = bytes(body[pos:pos + size])
        pos += size
        abc_raw: Optional[bytes] = None
        if code == 82:  # DoABC
            nul = payload.find(b"\x00", 4)
            if nul >= 0:
                abc_raw = payload[nul + 1:]
        elif code == 72:  # DoABC1
            abc_raw = payload

        if abc_raw:
            abc = swf_names.Abc(abc_raw)
            mns, strings, consts = _read_abc_consts_and_pools(abc_raw)
            for _meth_id, bcode in abc.bodies:
                insns = _decode_abc_body(bcode, mns, strings)
                for idx, (op, arg1, arg2) in enumerate(insns):
                    # 1. BGSExternalInterface.call(codeObjExpr, methodNameExpr, ...)
                    if op in (0x46, 0x4F) and arg1 == "call" and isinstance(arg2, int) and arg2 >= 2:
                        bgs_i: Optional[int] = None
                        for j in range(idx - 1, max(-1, idx - 48), -1):
                            if insns[j][1] == "BGSExternalInterface":
                                bgs_i = j
                                break
                        if bgs_i is not None:
                            for k in range(bgs_i + 1, idx):
                                kop, ka1, _ = insns[k]
                                cand: Optional[str] = None
                                if kop == swf_names.OP_PUSHSTRING and isinstance(ka1, str) and ka1 not in CODE_HOLDERS:
                                    cand = ka1
                                elif kop in (0x60, 0x66) and isinstance(ka1, str) and ka1 in consts:
                                    cand = consts[ka1]
                                if cand and IDENT_RE.fullmatch(cand):
                                    _record(cand)
                                    break
                    # 2. Direct BGSCodeObj.<method>(...) or codeObj.<method>(...)
                    elif op in (0x46, 0x4F) and isinstance(arg1, str) and arg1 != "call" and IDENT_RE.fullmatch(arg1):
                        if isinstance(arg2, int) and arg2 == 0:
                            if idx >= 1 and insns[idx - 1][0] in (0x60, 0x66) and insns[idx - 1][1] in CODE_HOLDERS:
                                _record(arg1)
                        elif isinstance(arg2, int) and arg2 >= 1:
                            # Receiver must precede the pushed argument(s), so j < idx - arg2
                            for j in range(max(0, idx - 8 - arg2), idx - arg2):
                                if insns[j][0] in (0x60, 0x66) and insns[j][1] in CODE_HOLDERS:
                                    if not any(insns[m][0] in (0x46, 0x4F) for m in range(j + 1, idx)):
                                        _record(arg1)
                                        break
        if code == 0:
            break
    return ordered


def _movie_sort_key(rel_posix: str) -> Tuple[int, str]:
    low = rel_posix.lower()
    for i, pat in enumerate(CANONICAL_MOVIE_PRIORITY):
        if low == pat:
            return (i, low)
    return (len(CANONICAL_MOVIE_PRIORITY), low)


def collect_stage_codeobj_calls(
    interface_dir: os.PathLike | str,
    *,
    exclude_swfs: Iterable[str] = SPECIAL_MENU_SWFS | NON_SHELL_AUX_SWFS,
) -> Tuple[Dict[str, List[str]], List[str]]:
    """Scan all Pip-Boy `.swf` files under `<interface_dir>` and return `(per_movie_calls, ordered_union)`."""
    iface = Path(interface_dir)
    if not iface.is_dir():
        raise StageIniError(f"missing Data/Interface directory: {iface}")
    excluded = {s.lower() for s in exclude_swfs}
    swf_files = sorted(
        (
            p
            for p in iface.rglob("*.swf")
            if p.is_file() and p.relative_to(iface).as_posix().lower() not in excluded
        ),
        key=lambda p: _movie_sort_key(p.relative_to(iface).as_posix()),
    )
    if not swf_files:
        raise StageIniError(f"no .swf movies found under {iface}")

    per_movie: Dict[str, List[str]] = {}
    union_ordered: List[str] = []
    seen: Set[str] = set()
    for swf_path in swf_files:
        rel = swf_path.relative_to(iface).as_posix()
        calls = extract_swf_codeobj_calls(swf_path.read_bytes())
        per_movie[rel] = calls
        for name in calls:
            if name not in seen:
                seen.add(name)
                union_ordered.append(name)
    return per_movie, union_ordered


def extract_swf_avm2_strings(swf_bytes: bytes) -> Set[str]:
    """Return the set of all non-empty strings in every DoABC / DoABC1 constant pool of `swf_bytes`."""
    if len(swf_bytes) < 8 or swf_bytes[:3] not in (b"CWS", b"FWS"):
        raise StageIniError("input is not an uncompressed (FWS) or zlib-compressed (CWS) SWF")
    body = zlib.decompress(swf_bytes[8:]) if swf_bytes[:3] == b"CWS" else swf_bytes[8:]
    if not body:
        return set()
    nbits = body[0] >> 3
    pos = (5 + 4 * nbits + 7) // 8 + 4
    pool: Set[str] = set()
    while pos + 2 <= len(body):
        head = struct.unpack_from("<H", body, pos)[0]
        code, size = head >> 6, head & 0x3F
        pos += 2
        if size == 0x3F:
            if pos + 4 > len(body):
                raise StageIniError("truncated SWF long tag header")
            size = struct.unpack_from("<I", body, pos)[0]
            pos += 4
        payload = bytes(body[pos : pos + size])
        pos += size
        abc_raw: Optional[bytes] = None
        if code == 82:
            nul = payload.find(b"\x00", 4)
            if nul >= 0:
                abc_raw = payload[nul + 1 :]
        elif code == 72:
            abc_raw = payload
        if abc_raw:
            _mns, strings, _consts = _read_abc_consts_and_pools(abc_raw)
            for s in strings:
                if s:
                    pool.add(s)
        if code == 0:
            break
    return pool


def parse_expect_file(expect_file: os.PathLike | str) -> List[str]:
    """Parse expected BGSCodeObj callback names from `<expect_file>` (never committed)."""
    p = Path(expect_file)
    if not p.is_file():
        raise StageIniError(f"--expect-file not found: {p}")
    names: List[str] = []
    seen: Set[str] = set()
    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].split(";", 1)[0].strip()
        if not line:
            continue
        for tok in re.split(r"[\s,]+", line):
            if not tok:
                continue
            if not IDENT_RE.fullmatch(tok):
                raise StageIniError(f"invalid identifier in --expect-file: {tok!r}")
            if tok not in seen:
                seen.add(tok)
                names.append(tok)
    return names


def check_expect_file_against_stage(
    interface_dir: os.PathLike | str,
    per_movie_calls: Dict[str, Sequence[str]],
    expect_names: Sequence[str],
) -> None:
    """Cross-check per-movie extracted callback names against each movie's AVM2 string pool and `expect_names` (A9)."""
    iface = Path(interface_dir)
    for rel, calls in sorted(per_movie_calls.items()):
        swf_p = iface / Path(*rel.split("/"))
        pool = extract_swf_avm2_strings(swf_p.read_bytes())
        call_set = set(calls)

        missing_from_pool = [fn for fn in calls if fn not in pool]
        if missing_from_pool:
            raise StageIniError(
                f"--expect-file check failed for {rel}: extractor listed name(s) absent from movie string pool: "
                f"{', '.join(missing_from_pool)}"
            )

        missed_by_extractor = [nm for nm in expect_names if nm in pool and nm not in call_set]
        if missed_by_extractor:
            raise StageIniError(
                f"--expect-file check failed for {rel}: expected name(s) present in movie string pool but missing from "
                f"extractor list: {', '.join(missed_by_extractor)}"
            )


def check_codeobj_coverage(
    per_movie_calls: Dict[str, Sequence[str]],
    registered_names: Sequence[str],
    allow_omit: Iterable[str] = (),
) -> None:
    """Fail if any staged movie calls a BGSCodeObj method absent from `registered_names` (unless explicitly allowed)."""
    reg_set = set(registered_names)
    allowed = set(allow_omit)
    uncovered: List[str] = []
    for rel, calls in sorted(per_movie_calls.items()):
        for fn in calls:
            if fn not in reg_set and fn not in allowed:
                uncovered.append(f"{rel}:{fn}")
    if uncovered:
        raise StageIniError(
            f"coverage check failed: staged movie(s) call unregistered BGSCodeObj name(s): {', '.join(uncovered)}"
        )


def format_stage_ini(
    code_obj_names: Sequence[str],
    *,
    movie: str = "FO4SF_Fo4Shell",
    key_hex: str = "0x76",
    flags_hex: str = "0x19",
    pause: int = 1,
    populate_in_call: int = 0,
    late_invalidate: int = 0,
    arm: int = 0,
    stat_actions: int = 0,
    inv_data_answers: int = 0,
    require_pickup: int = 0,
    boot_movie: str = "",
    boot_on_first_open: int = 0,
    special_menu: int = 0,
    special_movie: str = "",
    special_max_points: int = 40,
    code_obj_sound: int = 0,
    map_enabled: int = 1,
    map_menus: str = DEFAULT_MAP_MENUS,
    map_block_starmap: int = 0,
    map_heading_at: str = "88",
    setup_show_unavailable: int = 0,
) -> str:
    """Format a clean Stage=2 FO4SFPipboyMenu.ini with zero [Kit], [Page ...], or Kit* entries."""
    if not code_obj_names:
        raise StageIniError("CodeObjNames list cannot be empty")
    if len(code_obj_names) > MAX_CODE_NAMES:
        raise StageIniError(f"CodeObjNames count {len(code_obj_names)} exceeds kMaxCodeNames ({MAX_CODE_NAMES})")
    seen: Set[str] = set()
    for nm in code_obj_names:
        if not IDENT_RE.fullmatch(nm):
            raise StageIniError(f"invalid BGSCodeObj identifier: {nm!r}")
        if nm in seen:
            raise StageIniError(f"duplicate BGSCodeObj identifier: {nm!r}")
        seen.add(nm)

    clamped_max_pts = max(7, min(70, int(special_max_points)))
    eff_special_movie = special_movie if special_menu else ""

    lines = [
        "; Generated by scripts/ui/make_pipboy_stage_ini.py from staged Pip-Boy SWF DoABC bytecode.",
        "; Shipped Stage=2 Fallout 4 Pip-Boy shell configuration only.",
        "[FO4SFPipboyMenu]",
        "Stage=2",
        f"Movie={movie}",
        f"Key={key_hex}",
        f"Flags={flags_hex}",
        f"Pause={1 if pause else 0}",
        "KeepAlive=1",
        "CodeObj=1",
        f"CodeObjNames={','.join(code_obj_names)}",
        "CodeObjHide=1",
        f"CodeObjSound={1 if code_obj_sound else 0}",
        "CodeObjInit=",
        "CodeObjProbe=",
        "CodeObjCalls=Menu_mc.onCodeObjCreate",
        "CodeObjSpecial=fill",
        "CodeObjAt=Menu_mc",
        "CodeObjPages=1",
        f"PopulateInCall={1 if populate_in_call else 0}",
        f"LateInvalidate={1 if late_invalidate else 0}",
        f"StatActions={1 if stat_actions else 0}",
        f"InvDataAnswers={1 if inv_data_answers else 0}",
        f"RequirePickup={1 if require_pickup else 0}",
        f"BootMovie={boot_movie}",
        f"BootOnFirstOpen={1 if (boot_movie and boot_on_first_open) else 0}",
        f"SpecialMenu={1 if special_menu else 0}",
        f"SpecialMovie={eff_special_movie}",
        f"SpecialMaxPoints={clamped_max_pts}",
        "SpecialKey=0",
        "ShellKeys=",
        f"Arm={1 if arm else 0}",
        "ArmRaiseIdle=idleexaminewatch",
        "ArmRaiseMs=2000",
        "ArmLowerIdle=",
        "ArmLowerEvent=",
        "ArmLowerMs=3500",
        "ArmRetryMs=2000",
        "CancelCode1=0x1B",
        "CancelCode2=0x09",
        "CancelCode3=0",
        "CancelCode4=0",
        "World=0",
        "WorldKey=0x77",
        "WorldMenu=",
        "WorldMovie=",
        f"Map={1 if map_enabled else 0}",
        "MapKey=0x4D",
        "MapPage=3",
        f"MapMenus={map_menus}",
        f"MapBlockStarMap={1 if map_block_starmap else 0}",
        "MapStore=FO4SFPipboyMapMarkers.tsv",
        "MapTravelPlugin=FO4SFPipboyTravel.esm",
        "MapTravelScript=FO4SF_PipboyTravel.Go",
        "MapSurvival=0",
        f"MapHeadingAt={map_heading_at}",
        "MapGlobalValueAt=0",
        "MapGameHourId=0x38",
        "MapGameDaysPassedId=0x39",
        "MapFileCollectionAt=0x1580",
        "MapFileNameAt=0x38",
        "MapFileCompileIndexAt=0x1B7",
        "MapFileIndexAt=0x218",
        "MapExtraListAt=0xC8",
        "MapMarkerFlagsAt=0x18",
        "MapMarkerDiscoveredMask=0x20",
        f"SetupShowUnavailable={1 if setup_show_unavailable else 0}",
    ]
    return "\n".join(lines) + "\n"


def assert_no_kit_entries(ini_text: str) -> None:
    """Assert that a stage INI text contains no [Kit], [Page ...], or Kit* keys."""
    for line_no, raw in enumerate(ini_text.splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith(";"):
            continue
        if s.startswith("[") and s.endswith("]"):
            sec = s[1:-1].strip()
            if sec == "Kit" or sec.startswith("Page "):
                raise StageIniError(f"forbidden section [{sec}] at line {line_no}")
            continue
        if "=" in s:
            key = s.split("=", 1)[0].strip()
            if key.lower().startswith("kit"):
                raise StageIniError(f"forbidden Kit* key {key!r} at line {line_no}")


def generate_stage_ini(
    stage_dir: os.PathLike | str,
    *,
    out_ini: Optional[os.PathLike | str] = None,
    fo4_ba2: Optional[os.PathLike | str] = None,
    fo4_data: Optional[os.PathLike | str] = None,
    movie: str = "FO4SF_Fo4Shell",
    pause: int = 1,
    populate_in_call: int = 0,
    late_invalidate: int = 0,
    arm: int = 0,
    stat_actions: int = 0,
    inv_data_answers: int = 0,
    require_pickup: int = 0,
    boot_movie_name: str = DEFAULT_BOOT_MOVIE,
    boot_on_first_open: int = 0,
    special_menu: int = 0,
    special_movie_name: str = DEFAULT_SPECIAL_MOVIE,
    special_max_points: int = 40,
    map_menus: str = DEFAULT_MAP_MENUS,
    map_block_starmap: int = 0,
    setup_show_unavailable: int = 0,
    omit: Sequence[str] = (),
    allow_omit: Sequence[str] = (),
    expect_file: Optional[os.PathLike | str] = None,
) -> Dict[str, object]:
    """Build and write `SFSE/Plugins/FO4SFPipboyMenu.ini` for `stage_dir`, returning a summary dictionary."""
    stage = refuse_unsafe_output_path(stage_dir)
    target_ini = refuse_unsafe_output_path(out_ini) if out_ini else (stage / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini")
    refuse_unsafe_output_path(target_ini)

    iface_dir = stage / "Data" / "Interface"
    ba2_path: Optional[Path] = None
    if fo4_ba2:
        ba2_path = Path(fo4_ba2)
    elif fo4_data:
        cand = Path(fo4_data) / "Fallout4 - Interface.ba2"
        if cand.is_file():
            ba2_path = cand

    staged_boot = False
    staged_special = False
    if ba2_path is not None:
        if not ba2_path.is_file():
            raise StageIniError(f"Fallout4 - Interface.ba2 not found: {ba2_path}")
        pipboy_map_store.stage_fo4_boot_movie(str(ba2_path), str(iface_dir), dst_name=boot_movie_name)
        staged_boot = True
        if special_menu:
            pipboy_map_store.stage_fo4_special_movie(str(ba2_path), str(iface_dir), dst_name=special_movie_name)
            staged_special = True

    boot_swf_present = (iface_dir / f"{boot_movie_name}.swf").is_file()
    special_swf_path = iface_dir / f"{special_movie_name}.swf"
    special_swf_present = special_swf_path.is_file()
    excluded_swfs = set(SPECIAL_MENU_SWFS) | set(NON_SHELL_AUX_SWFS) | {f"{special_movie_name.lower()}.swf"}
    per_movie, discovered = collect_stage_codeobj_calls(iface_dir, exclude_swfs=excluded_swfs)
    if expect_file is not None:
        check_expect_file_against_stage(iface_dir, per_movie, parse_expect_file(expect_file))

    # A9: Always register HideMenu in the generated callback name list
    if "HideMenu" not in discovered:
        discovered = [*discovered, "HideMenu"]

    special_calls: List[str] = []
    if special_menu and special_swf_present:
        special_calls = extract_swf_codeobj_calls(special_swf_path.read_bytes())
        check_codeobj_coverage({f"{special_movie_name}.swf": special_calls}, sorted(SPECIAL_MENU_SUPPORTED_CODEOBJ))

    omit_set = set(omit)
    registered = [nm for nm in discovered if nm not in omit_set]
    check_codeobj_coverage(per_movie, registered, allow_omit=allow_omit)

    reg_set = set(registered)
    for rel, calls in per_movie.items():
        reg_cnt = sum(1 for fn in calls if fn in reg_set)
        print(f"movie {rel}: extracted={len(calls)} registered={reg_cnt}")

    sounds_dir = target_ini.parent / "FO4SFPipboyMenuSounds"
    has_sounds = sounds_dir.is_dir() and any(p.suffix.lower() == ".wav" for p in sounds_dir.iterdir())

    ini_text = format_stage_ini(
        registered,
        movie=movie,
        pause=pause,
        populate_in_call=populate_in_call,
        late_invalidate=late_invalidate,
        arm=arm,
        stat_actions=stat_actions,
        inv_data_answers=inv_data_answers,
        require_pickup=require_pickup,
        boot_movie=boot_movie_name if boot_swf_present else "",
        boot_on_first_open=boot_on_first_open if boot_swf_present else 0,
        special_menu=special_menu,
        special_movie=special_movie_name if special_menu else "",
        special_max_points=special_max_points,
        code_obj_sound=1 if has_sounds else 0,
        map_menus=map_menus,
        map_block_starmap=map_block_starmap,
        setup_show_unavailable=setup_show_unavailable,
    )
    assert_no_kit_entries(ini_text)

    target_ini.parent.mkdir(parents=True, exist_ok=True)
    target_ini.write_text(ini_text, encoding="utf-8", newline="\n")

    # If the stage also holds a legacy root/sfse copy of FO4SFPipboyMenu.ini, keep it synchronized
    for extra_rel in (("FO4SFPipboyMenu.ini",), ("sfse", "FO4SFPipboyMenu.ini")):
        extra_p = stage.joinpath(*extra_rel)
        if out_ini is None and extra_p.is_file() and extra_p.resolve() != target_ini.resolve():
            extra_p.write_text(ini_text, encoding="utf-8", newline="\n")

    return {
        "ini_path": str(target_ini),
        "movies_scanned": len(per_movie),
        "per_movie": per_movie,
        "discovered_names": discovered,
        "registered_names": registered,
        "boot_movie": boot_movie_name if boot_swf_present else "",
        "boot_staged": staged_boot,
        "special_menu": bool(special_menu),
        "special_movie": special_movie_name if special_menu else "",
        "special_staged": staged_special,
        "special_calls": special_calls,
    }


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Generate Stage=2 FO4SFPipboyMenu.ini from staged Pip-Boy SWFs.")
    ap.add_argument("--stage", required=True, help="Pip-Boy stage root directory containing Data/Interface/*.swf")
    ap.add_argument("--out", help="Explicit output INI path (defaults to <stage>/SFSE/Plugins/FO4SFPipboyMenu.ini)")
    ap.add_argument("--fo4-ba2", help="Optional path to Fallout4 - Interface.ba2 to stage boot / SPECIAL movies")
    ap.add_argument("--fo4-data", help="Optional path to Fallout 4 Data folder containing Fallout4 - Interface.ba2")
    ap.add_argument("--movie", default="FO4SF_Fo4Shell", help="Shell SWF base name (default FO4SF_Fo4Shell)")
    ap.add_argument("--pause", type=int, choices=(0, 1), default=1, help="Pause game while open (default 1)")
    ap.add_argument("--populate-in-call", type=int, choices=(0, 1), default=0, help="Enable 1b PopulateInCall (default 0)")
    ap.add_argument("--late-invalidate", type=int, choices=(0, 1), default=0, help="Enable LateInvalidate (default 0)")
    ap.add_argument("--arm", type=int, choices=(0, 1), default=0, help="Opt-in 1i/N1 first-person arm PlayIdle (default 0: T7 off)")
    ap.add_argument("--stat-actions", type=int, choices=(0, 1), default=0, help="Enable 1j STAT actions (default 0)")
    ap.add_argument("--inv-data-answers", type=int, choices=(0, 1), default=0, help="Enable 1k INV/DATA answers (default 0)")
    ap.add_argument("--require-pickup", type=int, choices=(0, 1), default=0, help="Enable X2 RequirePickup (default 0)")
    ap.add_argument("--boot-movie", default=DEFAULT_BOOT_MOVIE, help="Boot sequence SWF base name")
    ap.add_argument("--boot-on-first-open", type=int, choices=(0, 1), default=0, help="Opt-in boot movie once after pickup (default 0: T7 off)")
    ap.add_argument("--special-menu", type=int, choices=(0, 1), default=0, help="Enable 1k FO4SF_SpecialMenu host (default 0)")
    ap.add_argument("--special-movie", default=DEFAULT_SPECIAL_MOVIE, help="Staged SPECIALMenu SWF base name")
    ap.add_argument("--special-max-points", type=int, default=40, help="S.P.E.C.I.A.L. point pool (default 40)")
    ap.add_argument("--map-menus", default=DEFAULT_MAP_MENUS, help="Comma-separated Starfield map menus to block")
    ap.add_argument(
        "--map-block-starmap",
        type=int,
        choices=(0, 1),
        default=0,
        help="T2: 0 = hide-only default via SuppressVanillaMapMenus (outdoor M-key safe); 1 = non-null minimal blocked IMenu",
    )
    ap.add_argument(
        "--setup-show-unavailable",
        type=int,
        choices=(0, 1),
        default=0,
        help="Show available:false start rows greyed out on FO4SF_SetupMenu (default 0: leave off)",
    )
    ap.add_argument("--expect-file", default=None, help="Optional file of expected BGSCodeObj names to cross-check against SWF string pools")
    ap.add_argument("--omit", action="append", default=[], help="Omit a BGSCodeObj name from CodeObjNames= (repeatable)")
    ap.add_argument(
        "--allow-omit",
        action="append",
        default=[],
        help="Allow an omitted BGSCodeObj name in the coverage check (for negative crash proof tests)",
    )
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        res = generate_stage_ini(
            args.stage,
            out_ini=args.out,
            fo4_ba2=args.fo4_ba2,
            fo4_data=args.fo4_data,
            movie=args.movie,
            pause=args.pause,
            populate_in_call=args.populate_in_call,
            late_invalidate=args.late_invalidate,
            arm=args.arm,
            stat_actions=args.stat_actions,
            inv_data_answers=args.inv_data_answers,
            require_pickup=args.require_pickup,
            boot_movie_name=args.boot_movie,
            boot_on_first_open=args.boot_on_first_open,
            special_menu=args.special_menu,
            special_movie_name=args.special_movie,
            special_max_points=args.special_max_points,
            map_menus=args.map_menus,
            map_block_starmap=args.map_block_starmap,
            setup_show_unavailable=args.setup_show_unavailable,
            omit=args.omit,
            allow_omit=args.allow_omit,
            expect_file=args.expect_file,
        )
    except StageIniError as exc:
        sys.stderr.write(f"make_pipboy_stage_ini error: {exc}\n")
        return 1
    names = res["registered_names"]
    assert isinstance(names, list)
    print(
        f"wrote {res['ini_path']} ({len(names)} CodeObjNames across {res['movies_scanned']} SWF(s), "
        f"boot={res['boot_movie'] or 'none'})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
