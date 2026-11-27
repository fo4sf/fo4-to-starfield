"""F0: Fallout 4 opening scene reference exporter and citation verifier.

Reads Fallout 4 masters via dotnet/Fo4Export, Base.zip Papyrus sources, and
Fallout4 - Animations.ba2 (event-to-clip names only), and writes a private
reference pack outside any Git worktree with built-in citation self-checking.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fo4sf.ba2 import Ba2  # noqa: E402

DEFAULT_FO4_DATA = Path(r"D:\SteamLibrary\steamapps\common\Fallout 4\Data")
DEFAULT_OUT_DIR = Path(r"D:\FO4SF-Owner-Tests\fo4-reference")
DEFAULT_WORLD = "0000003C"

DEFAULT_QUESTS = [
    "MQ101",
    "MQ102",
    "DialogueVault111",
    "DialogueCodsworthPostWar",
    "Min00",
    "DialogueConcordArea",
    "Tutorial",
]

DEFAULT_INTERIORS = [
    "Vault111Cryo",
    "ConcordMuseum01",
]

DEFAULT_EXTERIOR_ANCHORS = [
    ("000998E3", 60.0, "vault111_ext_lift_door"),
    ("0009F272", 60.0, "vault111_map_marker"),
    ("0019E136", 40.0, "sanctuary_house_marker1"),
    ("0019E143", 40.0, "sanctuary_house_marker2"),
    ("0001F22E", 40.0, "concord_street_musket"),
]


class PrivacyError(ValueError):
    """Raised when an output directory would land inside a Git worktree or game folder."""


def validate_output_dir(out_dir: Path, forbidden_roots: Sequence[Path] = ()) -> Path:
    """Refuse any output directory inside a Git worktree or forbidden game data root."""
    resolved = out_dir.resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            raise PrivacyError(
                f"refused --out inside Git worktree '{candidate}': private FO4 exports must never sit in Git"
            )
    for root in forbidden_roots:
        r_root = root.resolve()
        if resolved == r_root or r_root in resolved.parents or resolved in r_root.parents:
            raise PrivacyError(
                f"refused --out '{resolved}' overlapping protected folder '{r_root}'"
            )
    if any(part.lower() == "steamlibrary" for part in resolved.parts):
        raise PrivacyError(f"refused --out inside SteamLibrary '{resolved}'")
    return resolved


def strip_papyrus_comments(lines: Sequence[str]) -> List[str]:
    """Return lines with `;...` and `{...}` Papyrus comments blanked while preserving 1-based line numbers."""
    out: List[str] = []
    in_block = False
    for raw in lines:
        buf: List[str] = []
        i = 0
        n = len(raw)
        in_str = False
        while i < n:
            ch = raw[i]
            if in_block:
                if ch == "}":
                    in_block = False
                i += 1
                continue
            if in_str:
                buf.append(ch)
                if ch == "\\" and i + 1 < n:
                    buf.append(raw[i + 1])
                    i += 2
                    continue
                if ch == '"':
                    in_str = False
                i += 1
                continue
            if ch == '"':
                in_str = True
                buf.append(ch)
                i += 1
                continue
            if ch == ";":
                break
            if ch == "{":
                in_block = True
                i += 1
                continue
            buf.append(ch)
            i += 1
        out.append("".join(buf))
    return out


class BaseZipIndex:
    """Read-only index over Fallout 4 Base.zip Papyrus source files."""

    def __init__(self, zip_path: Path):
        self.zip_path = zip_path
        self._by_norm: Dict[str, str] = {}
        self._by_stem: Dict[str, List[str]] = defaultdict(list)
        self._lines_cache: Dict[str, List[str]] = {}
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir() or not info.filename.lower().endswith(".psc"):
                    continue
                norm = info.filename.replace("\\", "/").lstrip("/").lower()
                self._by_norm[norm] = info.filename
                stem = Path(norm).stem
                self._by_stem[stem].append(info.filename)

    def resolve_entry(self, script_name: str) -> Optional[str]:
        s = script_name.strip().replace(":", "/").replace("\\", "/").lstrip("/")
        if not s:
            return None
        cand = (s if s.lower().endswith(".psc") else s + ".psc").lower()
        if cand in self._by_norm:
            return self._by_norm[cand]
        stem = Path(cand).stem.lower()
        matches = self._by_stem.get(stem, [])
        if len(matches) == 1:
            return matches[0]
        if matches:
            for m in matches:
                if m.replace("\\", "/").lower().endswith("/" + cand):
                    return m
            return sorted(matches)[0]
        return None

    def has_entry(self, entry_path: str) -> Optional[str]:
        norm = entry_path.strip().replace("\\", "/").lstrip("/").lower()
        return self._by_norm.get(norm)

    def read_lines(self, entry_path: str) -> List[str]:
        actual = self.has_entry(entry_path) or entry_path
        if actual not in self._lines_cache:
            with zipfile.ZipFile(self.zip_path, "r") as zf:
                text = zf.read(actual).decode("utf-8", errors="replace")
            self._lines_cache[actual] = text.splitlines()
        return self._lines_cache[actual]


_FUNC_START_RE = re.compile(r"^\s*(?:[\w\[\]]+\s+)*Function\s+([A-Za-z0-9_]+)\s*\(", re.IGNORECASE)
_FUNC_END_RE = re.compile(r"^\s*EndFunction\b", re.IGNORECASE)
_CALL_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("RegisterForAnimationEvent", re.compile(r"\bRegisterForAnimationEvent\s*\([^)]*\)", re.IGNORECASE)),
    ("WaitForAnimationEvent", re.compile(r"\bWaitForAnimationEvent\s*\([^)]*\)", re.IGNORECASE)),
    ("RegisterForRemoteEvent", re.compile(r"\bRegisterForRemoteEvent\w*\s*\([^)]*\)", re.IGNORECASE)),
    ("PlayAnimation", re.compile(r"\b(?:PlayAnimation(?:AndWait)?|PlayGamebryoAnimation)\s*\([^)]*\)", re.IGNORECASE)),
    ("PlayIdle", re.compile(r"\bPlayIdle(?:WithTarget)?\s*\([^)]*\)", re.IGNORECASE)),
    ("Game", re.compile(r"\bGame\.[A-Za-z0-9_]+\s*\([^)]*\)", re.IGNORECASE)),
    ("MoveTo", re.compile(r"\bMoveTo(?:Node|IfUnloaded|WhenUnloaded)?\s*\([^)]*\)", re.IGNORECASE)),
    ("SetPosition", re.compile(r"\bSetPosition\s*\([^)]*\)", re.IGNORECASE)),
    ("Activate", re.compile(r"\bActivate\s*\([^)]*\)", re.IGNORECASE)),
    ("SetOpen", re.compile(r"\bSetOpen\s*\([^)]*\)", re.IGNORECASE)),
    ("Lock", re.compile(r"\bLock\s*\([^)]*\)", re.IGNORECASE)),
    (
        "InputLayer",
        re.compile(
            r"\b(?:InputEnableLayer\.[A-Za-z0-9_]+|\w+\.(?:DisablePlayerControls|EnablePlayerControls|Reset|Delete))\s*\([^)]*\)",
            re.IGNORECASE,
        ),
    ),
]
_ANIM_STRING_ARG_RE = re.compile(
    r'\b(?:RegisterForAnimationEvent|WaitForAnimationEvent)\s*\([^,]+,\s*"([^"]+)"\s*\)',
    re.IGNORECASE,
)
_ON_ANIM_EVENT_CMP_RE = re.compile(
    r'\b(?:asEventName|eventName)\s*==\s*"([^"]+)"|"([^"]+)"\s*==\s*\b(?:asEventName|eventName)',
    re.IGNORECASE,
)
_PLAY_ANIM_ARG_RE = re.compile(
    r'\b(?:PlayAnimation(?:AndWait)?|PlayGamebryoAnimation)\s*\(\s*"([^"]+)"',
    re.IGNORECASE,
)


def find_function_span(lines: Sequence[str], func_name: str) -> Optional[Tuple[int, int]]:
    """Return 1-based inclusive (start, end) line numbers of `Function <func_name>`."""
    cleaned = strip_papyrus_comments(lines)
    target = func_name.strip().lower()
    start_line: Optional[int] = None
    for idx, line in enumerate(cleaned, 1):
        if start_line is None:
            m = _FUNC_START_RE.match(line)
            if m and m.group(1).lower() == target:
                start_line = idx
        else:
            if _FUNC_END_RE.match(line):
                return (start_line, idx)
    return None


def extract_script_calls_and_events(entry_path: str, lines: Sequence[str]) -> Dict[str, Any]:
    """Extract categorized engine calls and animation event names with exact Base.zip file:line citations."""
    cleaned = strip_papyrus_comments(lines)
    calls: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    anim_events: List[Dict[str, Any]] = []
    anim_sequences: List[Dict[str, Any]] = []
    seen_event_keys = set()

    for line_no, line in enumerate(cleaned, 1):
        if not line.strip():
            continue
        cite = f"Base.zip:{entry_path}:{line_no}"
        for cat, pat in _CALL_PATTERNS:
            for m in pat.finditer(line):
                calls[cat].append({"citation": cite, "line": line_no, "call": m.group(0).strip()})
        for m in _ANIM_STRING_ARG_RE.finditer(line):
            ev = m.group(1)
            k = (ev.lower(), line_no, "wait_or_register")
            if k not in seen_event_keys:
                seen_event_keys.add(k)
                anim_events.append({"event": ev, "kind": "wait_or_register", "citation": cite, "line": line_no})
        for m in _ON_ANIM_EVENT_CMP_RE.finditer(line):
            ev = m.group(1) or m.group(2)
            if ev:
                k = (ev.lower(), line_no, "OnAnimationEvent")
                if k not in seen_event_keys:
                    seen_event_keys.add(k)
                    anim_events.append({"event": ev, "kind": "OnAnimationEvent", "citation": cite, "line": line_no})
        for m in _PLAY_ANIM_ARG_RE.finditer(line):
            anim_sequences.append({"sequence": m.group(1), "citation": cite, "line": line_no})

    return {
        "entry": entry_path,
        "line_count": len(lines),
        "calls": dict(calls),
        "animation_events": anim_events,
        "play_animations": anim_sequences,
    }


def scan_animations_ba2(ba2_path: Path, event_names: Iterable[str]) -> Dict[str, List[str]]:
    """Scan .hkx payloads inside `Fallout4 - Animations.ba2` in memory; return matching clip filenames only."""
    targets = sorted({ev.strip() for ev in event_names if ev.strip()})
    results: Dict[str, List[str]] = {ev: [] for ev in targets}
    if not targets:
        return results

    exact_tokens = [(ev, b"\x00" + ev.encode("ascii", errors="ignore") + b"\x00") for ev in targets]
    lower_tokens = [(ev, b"\x00" + ev.lower().encode("ascii", errors="ignore") + b"\x00") for ev in targets]

    archive = Ba2(str(ba2_path))
    for idx, entry in enumerate(archive.entries):
        if not entry.name.lower().endswith(".hkx"):
            continue
        blob = archive.read(idx)
        blob_lower: Optional[bytes] = None
        for ev, tok in exact_tokens:
            if tok and tok in blob:
                results[ev].append(entry.name)
                continue
            if len(ev) >= 4:
                if blob_lower is None:
                    blob_lower = blob.lower()
                ltok = dict(lower_tokens)[ev]
                if ltok and ltok in blob_lower:
                    results[ev].append(entry.name)

    return {ev: sorted(set(clips)) for ev, clips in results.items()}


def _run_fo4export(fo4export_dll: Path, esm_path: Path, extra_masters: Sequence[Path], subcmd: List[str]) -> str:
    cmd = ["dotnet", "exec", str(fo4export_dll), str(esm_path)]
    for m in extra_masters:
        cmd.extend(["--master", str(m)])
    cmd.extend(subcmd)
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Fo4Export failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr}\n{proc.stdout}")
    return proc.stdout


def _build_fo4export_dll() -> Path:
    csproj = REPO_ROOT / "dotnet" / "Fo4Export" / "Fo4Export.csproj"
    proc = subprocess.run(["dotnet", "build", str(csproj)], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"dotnet build Fo4Export failed:\n{proc.stdout}\n{proc.stderr}")
    dll = REPO_ROOT / "dotnet" / "Fo4Export" / "bin" / "Debug" / "net9.0" / "Fo4Export.dll"
    if not dll.is_file():
        raise FileNotFoundError(f"built Fo4Export.dll not found at {dll}")
    return dll


def _script_entry_and_analysis(
    script_name: str,
    zip_idx: BaseZipIndex,
    analyzed_scripts: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    entry = zip_idx.resolve_entry(script_name)
    if not entry:
        return None
    if entry not in analyzed_scripts:
        lines = zip_idx.read_lines(entry)
        analyzed_scripts[entry] = extract_script_calls_and_events(entry, lines)
    return analyzed_scripts[entry]


def _render_quest_md(q: Dict[str, Any], anim_clips: Dict[str, List[str]]) -> str:
    lines: List[str] = []
    lines.append(f"# {q['editor_id']} (`Fallout4.esm {q['form_id']}`)")
    lines.append("")
    lines.append(f"- **Name:** {q.get('name') or '(none)'}")
    lines.append(f"- **Flags:** `{q.get('flags', '')}` | **Priority:** `{q.get('priority')}`")
    lines.append("")

    # Stages
    lines.append(f"## Stages ({len(q.get('stages', []))})")
    lines.append("")
    for st in q.get("stages", []):
        lines.append(f"### Stage {st['index']} (`flags: {st.get('flags', '')}`)")
        for le in st.get("log_entries", []):
            entry_txt = (le.get("entry") or "").replace("\r", " ").replace("\n", " ")
            lines.append(f"- Log (`{le.get('flags', '')}`): {entry_txt or '(empty)'}")
        for frag in st.get("fragments", []):
            cite = frag.get("citation")
            cite_txt = f"`{cite}`" if cite else f"`{frag.get('script_name')}.{frag.get('fragment_name')}` (unresolved in Base.zip)"
            lines.append(f"- Fragment `{frag.get('fragment_name')}`: {cite_txt}")
        lines.append("")

    # Objectives
    lines.append(f"## Objectives ({len(q.get('objectives', []))})")
    lines.append("")
    for ob in q.get("objectives", []):
        lines.append(f"- **{ob['index']}** (`{ob.get('flags', '')}`): {ob.get('display_text') or '(empty)'}")
        for tgt in ob.get("targets", []):
            lines.append(f"  - Target alias `{tgt.get('alias_id')}` (`{tgt.get('flags', '')}`)")
    lines.append("")

    # Aliases
    lines.append(f"## Aliases ({len(q.get('aliases', []))})")
    lines.append("")
    for al in q.get("aliases", []):
        lines.append(f"### Alias {al['id']}: `{al['name']}` (`{al.get('fill_type', '')}`, flags `{al.get('flags', '')}`)")
        if al.get("forced_reference"):
            fr = al["forced_reference"]
            lines.append(
                f"- Forced ref: `Fallout4.esm {fr['form_id']}` `{fr.get('editor_id', '')}` "
                f"(base `{fr.get('base_type', '')}` `Fallout4.esm {fr.get('base_form_id') or fr.get('form_id')}` `{fr.get('base_editor_id', '')}`)"
            )
        if al.get("reference_type"):
            rt = al["reference_type"]
            lines.append(f"- LocationRefType: `Fallout4.esm {rt['form_id']}` `{rt.get('editor_id', '')}`")
        for sc in al.get("scripts", []):
            cite = sc.get("source_citation")
            lines.append(f"- Script `{sc['name']}`: {f'`{cite}`' if cite else '(source not in Base.zip)'}")
            for p in sc.get("properties", []):
                res_parts = []
                for r in p.get("resolved", []):
                    if r.get("record_type") == "Unresolved":
                        res_parts.append(f"`0x{r['form_id']}` (engine/unresolved)")
                    else:
                        res_parts.append(f"`Fallout4.esm {r['form_id']}` `{r.get('editor_id', '')}`")
                res_s = ", ".join(res_parts)
                lines.append(f"  - prop `{p.get('name')}` = {res_s or repr(p.get('value'))}")
        for pk in al.get("packages", []):
            lines.append(f"- Package: `Fallout4.esm {pk['form_id']}` `{pk.get('editor_id', '')}` (`{pk.get('type', '')}`)")
        lines.append("")

    # Scenes
    lines.append(f"## Scenes ({len(q.get('scenes', []))})")
    lines.append("")
    for sc in q.get("scenes", []):
        lines.append(f"### Scene `{sc['editor_id']}` (`Fallout4.esm {sc['form_id']}`, flags `{sc.get('flags', '')}`)")
        for sf_ref in sc.get("fragment_citations", []):
            lines.append(f"- Fragment `{sf_ref['role']}` `{sf_ref['function']}`: `{sf_ref['citation']}`")
        for ph in sc.get("phases", []):
            lines.append(f"- Phase {ph['index']} `{ph.get('name', '')}` (start_conds={len(ph.get('start_conditions', []))}, end_conds={len(ph.get('completion_conditions', []))})")
        for act in sc.get("actions", []):
            topic = act.get("topic")
            topic_s = f" topic=`Fallout4.esm {topic['form_id']}`" if topic else ""
            pkg_s = ", ".join(f"`Fallout4.esm {p['form_id']}` `{p.get('editor_id', '')}`" for p in act.get("packages", []))
            pkg_note = f" pkgs=[{pkg_s}]" if pkg_s else ""
            tmr_note = f" timer={act['timer_seconds']}" if act.get("timer_seconds") is not None else ""
            lines.append(
                f"- Action #{act.get('index')} `{act.get('type')}` `{act.get('name', '')}` alias={act.get('actor_id')} "
                f"phases={act.get('start_phase')}..{act.get('end_phase')} flags=`{act.get('flags', '')}`{topic_s}{pkg_note}{tmr_note}"
            )
        lines.append("")

    # Terminals
    lines.append(f"## Terminals ({len(q.get('terminals', []))})")
    lines.append("")
    for tm in q.get("terminals", []):
        lines.append(f"### Terminal `{tm['editor_id']}` (`Fallout4.esm {tm['form_id']}`)")
        for fc in tm.get("fragment_citations", []):
            lines.append(f"- Fragment `{fc['function']}`: `{fc['citation']}`")
        for mi in tm.get("menu_items", []):
            lines.append(f"- Item {mi['item_id']} (`{mi.get('type', '')}`): `{mi.get('item_text', '')}` -> `{mi.get('response_text', '')}`")
        lines.append("")

    # Attached scripts + engine calls
    lines.append(f"## Attached Scripts & Engine Calls ({len(q.get('attached_scripts', []))})")
    lines.append("")
    for ascr in q.get("attached_scripts", []):
        src = ascr.get("source_citation") or "(source not in Base.zip)"
        lines.append(
            f"### `{ascr['script_name']}` ({ascr['owner_kind']} "
            + (
                f"`0x{ascr['owner_form_id']}`"
                if ascr.get("owner_kind") == "Unresolved"
                else f"`Fallout4.esm {ascr['owner_form_id']}`"
            )
            + f" `{ascr.get('owner_editor_id', '')}`)"
        )
        lines.append(f"- Source: `{src}`")
        analysis = ascr.get("analysis")
        if analysis:
            for cat, items in analysis.get("calls", {}).items():
                for it in items:
                    lines.append(f"  - [{cat}] `{it['citation']}` `{it['call']}`")
            for ev in analysis.get("animation_events", []):
                clips = anim_clips.get(ev["event"], [])
                lines.append(
                    f"  - [AnimEvent `{ev['event']}` ({ev['kind']})] `{ev['citation']}` (BA2 matches: {len(clips)})"
                )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_interior_md(data: Dict[str, Any], zip_idx: BaseZipIndex) -> str:
    lines: List[str] = []
    fid = (data.get("formkey") or "").split(":")[0].zfill(8)
    lines.append(f"# Interior Cell `{data.get('cell')}` (`Fallout4.esm {fid}`)")
    lines.append("")
    lines.append(f"- Refs exported: {len(data.get('refs', []))} | Deferred (actors/traps): {len(data.get('deferred_refs', []))}")
    scripted_refs = [r for r in data.get("refs", []) if r.get("scripts")]
    lines.append(f"- Scripted refs: {len(scripted_refs)}")
    lines.append("")
    lines.append("## Scripted References")
    lines.append("")
    for r in scripted_refs:
        rfid = (r.get("formkey") or "").split(":")[0].zfill(8)
        bfid = (r.get("base_formkey") or "").split(":")[0].zfill(8)
        lines.append(
            f"- `Fallout4.esm {rfid}` (`{r.get('type')}` `Fallout4.esm {bfid}` `{r.get('base_editor_id')}` pos={r.get('pos')})"
        )
        for s in r.get("scripts", []):
            entry = zip_idx.resolve_entry(s.get("name", ""))
            lines.append(f"  - Script `{s.get('name')}`" + (f" (`Base.zip:{entry}:1-{len(zip_idx.read_lines(entry))}`)" if entry else ""))
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_exterior_md(data: Dict[str, Any], zip_idx: BaseZipIndex) -> str:
    lines: List[str] = []
    w = data["worldspace"]
    lines.append(f"# Exterior Anchors in `{w['editor_id']}` (`Fallout4.esm {w['form_id']}`)")
    lines.append("")
    for anc in data["anchors"]:
        lines.append(
            f"## Anchor `Fallout4.esm {anc['anchor_form_id']}` `{anc.get('anchor_editor_id', '')}` (radius {anc['radius_m']} m, refs={anc['ref_count']})"
        )
        lines.append(f"- Position: {anc['anchor_pos']}")
        lines.append("")
        scripted_or_special = [
            r for r in anc["refs"]
            if r.get("scripts") or r.get("base_scripts") or r.get("teleport_destination") or r.get("linked_references") or r.get("form_id") == anc["anchor_form_id"]
        ]
        lines.append(f"### Key / Scripted / Linked Refs ({len(scripted_or_special)} of {anc['ref_count']})")
        for r in scripted_or_special[:150]:
            lines.append(
                f"- `Fallout4.esm {r['form_id']}` `{r.get('editor_id', '')}` "
                f"(`{r.get('base_type')}` `Fallout4.esm {r.get('base_form_id') or r['form_id']}` `{r.get('base_editor_id', '')}`, dist={r['dist_xy_m']}m)"
            )
            for sc in (r.get("scripts") or []):
                entry = zip_idx.resolve_entry(sc.get("name", ""))
                lines.append(f"  - ref script `{sc['name']}`" + (f" (`Base.zip:{entry}:1-{len(zip_idx.read_lines(entry))}`)" if entry else ""))
            for sc in (r.get("base_scripts") or []):
                entry = zip_idx.resolve_entry(sc.get("name", ""))
                lines.append(f"  - base script `{sc['name']}`" + (f" (`Base.zip:{entry}:1-{len(zip_idx.read_lines(entry))}`)" if entry else ""))
            if r.get("teleport_destination"):
                td = r["teleport_destination"]
                d = td.get("door")
                if d:
                    lines.append(f"  - XTEL -> `Fallout4.esm {d['form_id']}` flags=0x{td.get('flags', 0):X} pos={td.get('pos')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


_ZIP_CITE_RE = re.compile(r"Base\.zip:([A-Za-z0-9_./\\-]+\.psc):(\d+)(?:-(\d+))?")
_ESM_CITE_RE = re.compile(r"Fallout4\.esm\s+(?:0x)?([0-9A-Fa-f]{6,8})\b")


def self_check_pack(
    out_dir: Path,
    base_zip_path: Path,
    verify_ids_fn: Callable[[Sequence[str]], Tuple[int, int, List[str]]],
    target_files: Optional[Sequence[Path]] = None,
) -> Tuple[int, int, List[str]]:
    """Verify every Base.zip path:line[-end] and Fallout4.esm FormID citation in generated pack files."""
    if target_files is None:
        target_files = []
        for sub in ("index.md", "quests", "interiors", "exteriors", "animations"):
            p = out_dir / sub
            if p.is_file():
                target_files.append(p)
            elif p.is_dir():
                target_files.extend(sorted(f for f in p.iterdir() if f.is_file() and f.suffix in (".md", ".json")))

    zip_idx = BaseZipIndex(base_zip_path)
    zip_cites: List[Tuple[str, int, int, str]] = []
    esm_ids: List[str] = []
    seen_esm = set()

    for path in target_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in _ZIP_CITE_RE.finditer(text):
            entry = m.group(1).replace("\\", "/")
            s_ln = int(m.group(2))
            e_ln = int(m.group(3) or s_ln)
            zip_cites.append((entry, s_ln, e_ln, f"{path.name}: Base.zip:{entry}:{s_ln}-{e_ln}"))
        for m in _ESM_CITE_RE.finditer(text):
            fid = m.group(1).upper().zfill(8)
            if fid not in seen_esm:
                seen_esm.add(fid)
                esm_ids.append(fid)

    errors: List[str] = []
    resolved_zip = 0
    for entry, s_ln, e_ln, label in zip_cites:
        actual = zip_idx.has_entry(entry)
        if not actual:
            errors.append(f"unresolved zip path: {label}")
            continue
        lines = zip_idx.read_lines(actual)
        if s_ln < 1 or e_ln < s_ln or e_ln > len(lines):
            errors.append(f"out-of-bounds line span (len={len(lines)}): {label}")
            continue
        resolved_zip += 1

    resolved_esm, total_esm, missing_esm = verify_ids_fn(esm_ids)
    for fid in missing_esm:
        errors.append(f"unresolved Fallout4.esm FormID: {fid}")

    resolved = resolved_zip + resolved_esm
    total = len(zip_cites) + total_esm
    return resolved, total, errors


def build_pack(
    fo4_data: Path,
    base_zip_path: Path,
    anim_ba2_path: Path,
    out_dir: Path,
    quests: Sequence[str],
    interiors: Sequence[str],
    world: str,
    exterior_anchors: Sequence[Tuple[str, float, str]],
    extra_masters: Sequence[Path] = (),
) -> Dict[str, Any]:
    out_dir = validate_output_dir(out_dir, forbidden_roots=(fo4_data,))
    esm_path = fo4_data / "Fallout4.esm"
    if not esm_path.is_file():
        raise FileNotFoundError(f"Fallout4.esm not found at {esm_path}")
    if not base_zip_path.is_file():
        raise FileNotFoundError(f"Base.zip not found at {base_zip_path}")
    if not anim_ba2_path.is_file():
        raise FileNotFoundError(f"Animations BA2 not found at {anim_ba2_path}")

    for sub in ("quests", "interiors", "exteriors", "animations"):
        (out_dir / sub).mkdir(parents=True, exist_ok=True)

    fo4export_dll = _build_fo4export_dll()
    zip_idx = BaseZipIndex(base_zip_path)
    analyzed_scripts: Dict[str, Dict[str, Any]] = {}

    # 1. Export all requested quests together
    raw_quests_json = out_dir / "quests" / "_all_quests_raw.json"
    _run_fo4export(fo4export_dll, esm_path, extra_masters, ["quest-ref", str(raw_quests_json), *quests])
    quests_payload = json.loads(raw_quests_json.read_text(encoding="utf-8"))
    raw_quests_json.unlink(missing_ok=True)

    all_anim_events = set()
    enriched_quests: List[Dict[str, Any]] = []
    for q in quests_payload["quests"]:
        # Enrich stage fragments with Base.zip line ranges
        for st in q.get("stages", []):
            for frag in st.get("fragments", []):
                entry = zip_idx.resolve_entry(frag.get("script_name", ""))
                if entry:
                    lines = zip_idx.read_lines(entry)
                    span = find_function_span(lines, frag.get("fragment_name", ""))
                    if span:
                        frag["citation"] = f"Base.zip:{entry}:{span[0]}-{span[1]}"
                    else:
                        frag["citation"] = f"Base.zip:{entry}:1-{len(lines)}"
        # Enrich alias scripts
        for al in q.get("aliases", []):
            for sc in al.get("scripts", []):
                an = _script_entry_and_analysis(sc.get("name", ""), zip_idx, analyzed_scripts)
                if an:
                    sc["source_citation"] = f"Base.zip:{an['entry']}:1-{an['line_count']}"
        # Enrich scene fragments
        for sc in q.get("scenes", []):
            fcites = []
            vm = sc.get("vmad") or {}
            sf = vm.get("script_fragments") or {}
            checks: List[Tuple[str, str, str]] = []
            if sf.get("on_begin") and sf["on_begin"].get("script_name"):
                checks.append(("begin", sf["on_begin"]["script_name"], sf["on_begin"].get("fragment_name", "")))
            if sf.get("on_end") and sf["on_end"].get("script_name"):
                checks.append(("end", sf["on_end"]["script_name"], sf["on_end"].get("fragment_name", "")))
            for pf in sf.get("phase_fragments") or []:
                if pf.get("script_name"):
                    checks.append((f"phase_{pf.get('index')}", pf["script_name"], pf.get("fragment_name", "")))
            for role, sname, fname in checks:
                entry = zip_idx.resolve_entry(sname)
                if entry:
                    lines = zip_idx.read_lines(entry)
                    span = find_function_span(lines, fname) if fname else None
                    cite = f"Base.zip:{entry}:{span[0]}-{span[1]}" if span else f"Base.zip:{entry}:1-{len(lines)}"
                    fcites.append({"role": role, "script_name": sname, "function": fname, "citation": cite})
            sc["fragment_citations"] = fcites
        # Enrich terminal fragments
        for tm in q.get("terminals", []):
            fcites = []
            vm = tm.get("vmad") or {}
            sf = vm.get("script_fragments") or {}
            for tf in sf.get("fragments") or []:
                sname = tf.get("script_name", "")
                fname = tf.get("fragment_name", "")
                entry = zip_idx.resolve_entry(sname)
                if entry:
                    lines = zip_idx.read_lines(entry)
                    span = find_function_span(lines, fname) if fname else None
                    cite = f"Base.zip:{entry}:{span[0]}-{span[1]}" if span else f"Base.zip:{entry}:1-{len(lines)}"
                    fcites.append({"item_id": tf.get("item_id"), "script_name": sname, "function": fname, "citation": cite})
            tm["fragment_citations"] = fcites
        # Enrich attached scripts with calls + events
        for ascr in q.get("attached_scripts", []):
            an = _script_entry_and_analysis(ascr.get("script_name", ""), zip_idx, analyzed_scripts)
            if an:
                ascr["source_citation"] = f"Base.zip:{an['entry']}:1-{an['line_count']}"
                ascr["analysis"] = an
                for ev in an.get("animation_events", []):
                    all_anim_events.add(ev["event"])
        enriched_quests.append(q)

    # 2. Scan BA2 for animation events -> clip filenames
    anim_clips = scan_animations_ba2(anim_ba2_path, sorted(all_anim_events))
    (out_dir / "animations" / "events.json").write_text(
        json.dumps({"events": anim_clips}, indent=2), encoding="utf-8"
    )
    ev_md = ["# Animation Events -> Matching Clips (`Fallout4 - Animations.ba2`)", ""]
    for ev_name, clips in sorted(anim_clips.items()):
        ev_md.append(f"## `{ev_name}` ({len(clips)} clips)")
        for cl in clips[:40]:
            ev_md.append(f"- `{cl}`")
        if len(clips) > 40:
            ev_md.append(f"- ... (+{len(clips) - 40} more in `events.json`)")
        ev_md.append("")
    (out_dir / "animations" / "events.md").write_text("\n".join(ev_md), encoding="utf-8")

    # 3. Write quests
    total_stages = 0
    total_scenes = 0
    total_terms = set()
    total_scripts = set()
    for q in enriched_quests:
        ed = q["editor_id"] or q["form_id"]
        (out_dir / "quests" / f"{ed}.json").write_text(json.dumps(q, indent=2), encoding="utf-8")
        (out_dir / "quests" / f"{ed}.md").write_text(_render_quest_md(q, anim_clips), encoding="utf-8")
        total_stages += len(q.get("stages", []))
        total_scenes += len(q.get("scenes", []))
        for tm in q.get("terminals", []):
            total_terms.add(tm["form_id"])
        for ascr in q.get("attached_scripts", []):
            total_scripts.add(ascr["script_name"].lower())

    # 4. Export interiors
    interior_summaries: List[Tuple[str, str, int]] = []
    for cell_edid in interiors:
        out_j = out_dir / "interiors" / f"{cell_edid}.json"
        _run_fo4export(fo4export_dll, esm_path, extra_masters, ["export", cell_edid, str(out_j)])
        cdata = json.loads(out_j.read_text(encoding="utf-8"))
        (out_dir / "interiors" / f"{cell_edid}.md").write_text(_render_interior_md(cdata, zip_idx), encoding="utf-8")
        fid = (cdata.get("formkey") or "").split(":")[0].zfill(8)
        interior_summaries.append((cell_edid, fid, len(cdata.get("refs", []))))

    # 5. Export exterior anchors
    anchor_specs = [f"{fid}:{rad}" for fid, rad, _ in exterior_anchors]
    ext_json = out_dir / "exteriors" / "commonwealth_anchors.json"
    _run_fo4export(fo4export_dll, esm_path, extra_masters, ["exterior-anchor", str(ext_json), world, *anchor_specs])
    ext_data = json.loads(ext_json.read_text(encoding="utf-8"))
    (out_dir / "exteriors" / "commonwealth_anchors.md").write_text(_render_exterior_md(ext_data, zip_idx), encoding="utf-8")

    # 6. Write index.md first (without final self-check count), then run self-check, then stamp self-check count
    idx_lines = [
        "# Fallout 4 Opening Reference Pack (F0)",
        "",
        f"- **Master:** `{esm_path}`",
        f"- **Scripts:** `{base_zip_path}`",
        f"- **Animations:** `{anim_ba2_path}`",
        "",
        "## Quests Exported",
        "",
    ]
    for q in enriched_quests:
        rq_s = ", ".join(f"{r['editor_id']} (`{r['form_id']}`)" for r in q.get("referenced_quests", []))
        idx_lines.append(
            f"- `{q['editor_id']}` (`Fallout4.esm {q['form_id']}`) — stages={len(q.get('stages', []))}, "
            f"objectives={len(q.get('objectives', []))}, aliases={len(q.get('aliases', []))}, "
            f"scenes={len(q.get('scenes', []))}, terminals={len(q.get('terminals', []))}, "
            f"scripts={len(q.get('attached_scripts', []))}"
            + (f" | refs: {rq_s}" if rq_s else "")
        )
    idx_lines.extend(["", "## Interior Cells", ""])
    for ed, fid, rcnt in interior_summaries:
        idx_lines.append(f"- `{ed}` (`Fallout4.esm {fid}`, {rcnt} placed refs)")
    idx_lines.extend(["", "## Exterior Anchors", ""])
    for anc, (_fid, _rad, label) in zip(ext_data["anchors"], exterior_anchors):
        idx_lines.append(
            f"- `{label}` (`Fallout4.esm {anc['anchor_form_id']}`, radius {anc['radius_m']} m, {anc['ref_count']} refs)"
        )
    idx_lines.extend([
        "",
        "## Totals",
        "",
        f"- Quests: {len(enriched_quests)}",
        f"- Stages: {total_stages}",
        f"- Scenes: {total_scenes}",
        f"- Scripts (unique attached): {len(total_scripts)}",
        f"- Terminals (unique): {len(total_terms)}",
        f"- Animation events scanned: {len(anim_clips)}",
        "",
    ])
    index_md = out_dir / "index.md"
    index_md.write_text("\n".join(idx_lines), encoding="utf-8")

    def _verify_esm_ids(ids: Sequence[str]) -> Tuple[int, int, List[str]]:
        if not ids:
            return 0, 0, []
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf:
            tf.write("\n".join(ids) + "\n")
            tmp_path = Path(tf.name)
        try:
            cmd = ["dotnet", "exec", str(fo4export_dll), str(esm_path)]
            for m in extra_masters:
                cmd.extend(["--master", str(m)])
            cmd.extend(["verify-ids", str(tmp_path)])
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            res = json.loads(proc.stdout.strip().splitlines()[-1])
            return int(res["resolved"]), int(res["total"]), list(res["missing"])
        finally:
            tmp_path.unlink(missing_ok=True)

    resolved, total, errs = self_check_pack(out_dir, base_zip_path, _verify_esm_ids)
    idx_lines.append(f"- **Self-check:** citations resolved / total: `{resolved} / {total}` (errors: {len(errs)})")
    index_md.write_text("\n".join(idx_lines) + "\n", encoding="utf-8")

    return {
        "out_dir": str(out_dir),
        "quests": len(enriched_quests),
        "stages": total_stages,
        "scenes": total_scenes,
        "scripts": len(total_scripts),
        "terminals": len(total_terms),
        "events": len(anim_clips),
        "citations_resolved": resolved,
        "citations_total": total,
        "errors": errs,
    }


def _parse_anchor_arg(raw: str) -> Tuple[str, float, str]:
    parts = raw.split(":")
    fid = parts[0].strip()
    rad = float(parts[1]) if len(parts) >= 2 and parts[1] else 50.0
    label = parts[2].strip() if len(parts) >= 3 and parts[2] else fid
    return fid, rad, label


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build Fallout 4 opening scene reference pack (F0).")
    parser.add_argument("--fo4-data", type=Path, default=DEFAULT_FO4_DATA)
    parser.add_argument("--base-zip", type=Path, default=None)
    parser.add_argument("--anim-ba2", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--quests", nargs="+", default=DEFAULT_QUESTS)
    parser.add_argument("--interiors", nargs="+", default=DEFAULT_INTERIORS)
    parser.add_argument("--world", default=DEFAULT_WORLD)
    parser.add_argument("--exterior-anchors", nargs="+", default=None)
    parser.add_argument("--master", type=Path, action="append", default=[])
    args = parser.parse_args(argv)

    base_zip = args.base_zip or (args.fo4_data / "Scripts" / "Source" / "Base" / "Base.zip")
    anim_ba2 = args.anim_ba2 or (args.fo4_data / "Fallout4 - Animations.ba2")
    anchors = (
        [_parse_anchor_arg(a) for a in args.exterior_anchors]
        if args.exterior_anchors
        else DEFAULT_EXTERIOR_ANCHORS
    )

    try:
        summary = build_pack(
            fo4_data=args.fo4_data,
            base_zip_path=base_zip,
            anim_ba2_path=anim_ba2,
            out_dir=args.out,
            quests=args.quests,
            interiors=args.interiors,
            world=args.world,
            exterior_anchors=anchors,
            extra_masters=args.master,
        )
    except PrivacyError as exc:
        print(f"PRIVACY ERROR: {exc}", file=sys.stderr)
        return 2

    print(
        f"pack built: quests={summary['quests']} stages={summary['stages']} scenes={summary['scenes']} "
        f"scripts={summary['scripts']} terminals={summary['terminals']} events={summary['events']}"
    )
    print(f"citations resolved / total: {summary['citations_resolved']} / {summary['citations_total']}")
    for err in summary["errors"][:20]:
        print(f"ERROR: {err}", file=sys.stderr)
    return 0 if not summary["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
