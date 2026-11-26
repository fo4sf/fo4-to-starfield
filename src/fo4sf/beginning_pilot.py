"""Offline bundle readiness verifier and console-free log evaluator for the Fallout 4 beginning pilot (`V1`).

Covers the eight console-free Story-mode beginning steps (`B1`..`B8`) documented in
`docs/testing/fo4-beginning-pilot.md`:
  - `B1_pod`: Mode choice (`mode choice ... mode=story`), cryo pod step-out (`pod settle ok=true`), Starfield quest hold-off
  - `B2_gear_door`: Vault pistol (`pistol picked`), Pip-Boy pickup (`pipboy pickup equipped flag=1`), and gear-door console (`cog door console activated` -> `stage 30`)
  - `B3_exit_lift`: `40`-point S.P.E.C.I.A.L. confirmation (`special set` sum == 40, never `special skipped`), `map setup done`, and `+21.6 m` lift ride (`ascent carried confirmed`)
  - `B4_surface_landing`: Commonwealth hilltop placement (`FinishSurface` `stage 40`) & landing check (`stage 200`, `fallback=false`)
  - `B5_codsworth_sanctuary`: Story gate (`mission gate mode=1 started=true` after `stage 200`), Sanctuary Codsworth keeper, and `MQ102`-lite talk (`codsworth talk end -> min00 stage 10`, `min00 given by=codsworth|concord`)
  - `B6_concord_raiders`: Concord street ambush & `WFC-01` anti-stall (`stages 10 -> 20 -> 30`, reload & `raider cleared absent` support)
  - `B7_preston_turnin`: Preston `DialogueMenu` turn-in (`preston talk end info=<id> -> stage 40`, failing `REACHABLE` on `stage 40 by=fallback`) -> `reward credits=100` -> `stage 200`
  - `B8_sanctuary_bench`: First-settlement hand-over objective on Sanctuary workbench `0250FE` / `0x005C50` (`min01 bench activated -> stage 100`)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union

from fo4sf.ba2 import Ba2, Ba2Error
from fo4sf.core.cross_plugin_check import CORE_VALUES_ARSENAL_RECORDS
from fo4sf.planet.esm import EsmError, Plugin as RawEsmPlugin


@dataclass(frozen=True)
class BeginningStepSpec:
    step_id: str
    title: str
    label: str
    plugins: Tuple[str, ...]
    scripts: Tuple[str, ...]
    actor: str
    owner_pass: str
    owner_fail: str


BEGINNING_STEPS: Tuple[BeginningStepSpec, ...] = (
    BeginningStepSpec(
        step_id="B1_pod",
        title="Story Mode Choice, Pod Walk-Out & Starfield Quest Hold-Off",
        label="REACHABLE",
        plugins=("FO4SFCoreValues.esm", "FO4SFNewGame.esm"),
        scripts=("FO4SF_NewGameQuest.pex", "FO4SF_NewGameLooks.pex"),
        actor="claude_pc_then_owner",
        owner_pass="Player picks Story mode before world fade-in; cryo pod step-out settles cleanly; zero Starfield quest banners.",
        owner_fail="Mode choice skipped or Warfare started on Story walk, pod collision snag, or Starfield quest left running.",
    ),
    BeginningStepSpec(
        step_id="B2_gear_door",
        title="Vault Pistol, Pip-Boy Pickup & Gear-Door Console Activation",
        label="REACHABLE",
        plugins=("FO4SFVaultGearDoor.esm", "FO4SFNewGame.esm"),
        scripts=("FO4SF_NewGameQuest.pex",),
        actor="claude_pc_then_owner",
        owner_pass="Player picks up placeholder pistol and Pip-Boy, then activates the vault console ('cog door console activated') to roll open the gear door and catwalk.",
        owner_fail="Gear door opens by proximity or direct door E without console activation, console works before Pip-Boy pickup, or pistol missing.",
    ),
    BeginningStepSpec(
        step_id="B3_exit_lift",
        title="Lift 40-Point S.P.E.C.I.A.L., Map Setup & Ascent",
        label="REACHABLE",
        plugins=("FO4SFExitLift.esm", "FO4SFNewGame.esm", "FO4SFProgression.esm"),
        scripts=("FO4SF_NewGameQuest.pex", "FO4SF_ProgressionQuest.pex"),
        actor="claude_pc_then_owner",
        owner_pass="Lift offers S.P.E.C.I.A.L. before Continue (showing a modal notice if Continue is chosen first); S.P.E.C.I.A.L. confirms 40 points; map setup finishes during +21.6 m ascent ('ascent carried confirmed').",
        owner_fail="'special skipped' logged, S.P.E.C.I.A.L. sum != 40, missing 'map setup done', or 'exit failed reason=lift_*'.",
    ),
    BeginningStepSpec(
        step_id="B4_surface_landing",
        title="Commonwealth Hilltop Surface Landing",
        label="REACHABLE",
        plugins=("FO4TerrainCore.esm", "FO4SFNewGame.esm"),
        scripts=("FO4SF_NewGameQuest.pex",),
        actor="claude_pc_then_owner",
        owner_pass="FinishSurface sets stage 40 on merged hilltop cell and CheckLanding reaches stage 200 on solid terrain with Vault 111 discovered and fallback=false.",
        owner_fail="Player falls > 3 m ('fell z='), 'fallback=true', 'exit failed reason=', or mission starts before stage 200.",
    ),
    BeginningStepSpec(
        step_id="B5_codsworth_sanctuary",
        title="Story Gate & Codsworth MQ102-Lite Talk -> Concord Objective",
        label="REACHABLE",
        plugins=("FO4TerrainCore.esm", "FO4SFMission.esm"),
        scripts=("FO4SF_Min00Quest.pex", "FO4SF_Codsworth01Quest.pex"),
        actor="claude_pc_then_owner",
        owner_pass="Mission starts silently after stage 200 in Story mode ('mission gate mode=1 started=true'); Codsworth renders brushed steel, opens DialogueMenu on E, and Choice 4 points to Concord ('codsworth talk end -> min00 stage 10').",
        owner_fail="Mission starts in vault or in Warfare, Codsworth renders black or lacks E talk prompt, or objective 10 never triggers.",
    ),
    BeginningStepSpec(
        step_id="B6_concord_raiders",
        title="Concord Street Raider Fight & WFC-01 Anti-Stall",
        label="REACHABLE",
        plugins=("FO4TerrainCore.esm", "FO4ActorRaider.esm", "FO4SFMission.esm"),
        scripts=("FO4SF_Min00Quest.pex",),
        actor="claude_pc_then_owner",
        owner_pass="Raiders actively engage with combat/sandbox AI packages; stage 20 survives save-quit-reload and rescues/clears stragglers ('raider cleared absent') to reach stage 30.",
        owner_fail="Fight stalls at stage 20, relocation failure budget exhausted, or Preston dies or turns hostile.",
    ),
    BeginningStepSpec(
        step_id="B7_preston_turnin",
        title="Preston Garvey DialogueMenu Turn-In -> Stage 40 & 200",
        label="REACHABLE",
        plugins=("FO4SFMission.esm",),
        scripts=("FO4SF_Min00Quest.pex", "FO4SF_COMPreston.pex"),
        actor="claude_pc_then_owner",
        owner_pass="Pressing E on HumanRace Preston opens 3-choice DialogueMenu ('preston talk end info=0x092A -> stage 40'), grants 100 placeholder Credits, and reaches stage 200.",
        owner_fail="'stage 40 by=fallback' triggered instead of DialogueMenu scene, missing 100-Credit reward, or door hold re-applied over armed test follow.",
    ),
    BeginningStepSpec(
        step_id="B8_sanctuary_bench",
        title="First Settlement Hand-Over -> Sanctuary Workbench (0250FE)",
        label="REACHABLE",
        plugins=("FO4TerrainCore.esm", "FO4SFMission.esm"),
        scripts=("FO4SF_Sanctuary01Quest.pex",),
        actor="claude_pc_then_owner",
        owner_pass="Stage 200 starts FO4SF_Sanctuary01 objective 10 on Sanctuary workbench 0x005C50 (0250FE); pressing E opens Starfield build mode and logs 'min01 bench activated -> stage 100'.",
        owner_fail="FO4SF_Sanctuary01 never starts at stage 200, bench lacks build prompt, or 'min01 bench activated -> stage 100' missing.",
    ),
)

CODSWORTH_NIF_REL = "meshes/fo4port/actors/codsworth/codsworth.nif"
PRESTON_OUTFIT_NIF_REL = "meshes/fo4port/armor/preston_garvey/prestongarveyoutfit_m.nif"
PRESTON_HAT_NIF_REL = "meshes/fo4port/armor/preston_garvey/prestongarveyhat_m.nif"
CONCORD_RAIDER_NIF_REL = "meshes/fo4core/armor/raider04/concord_raider_m.nif"
B5_REQUIRED_ACTOR_NIFS: Tuple[Tuple[str, str], ...] = (
    ("Codsworth NIF", CODSWORTH_NIF_REL),
    ("Preston outfit NIF", PRESTON_OUTFIT_NIF_REL),
    ("Preston hat NIF", PRESTON_HAT_NIF_REL),
    ("Concord Raider NIF", CONCORD_RAIDER_NIF_REL),
)
CODSWORTH_VOICE_DIR_REL = "sound/voice/fo4sfmission.esm/fo4sf_codsworthvoice"
MIN_CODSWORTH_WEMS = 25
MAX_PROTECTED_UNSTOPPED_HOLD_QUESTS = 4

MAP_MARKERS_DIRNAME = "map-markers"
MAP_MARKERS_PLUGIN = "FO4SFMapMarkers.esm"
MAP_MARKERS_ARCHIVE = "FO4SFMapMarkers - Main.ba2"
MAP_MARKERS_PEX_REL = "Scripts/FO4SF_MapMarkers.pex"
MAP_MARKERS_SCRIPT = "FO4SF_MapMarkers"
NEWGAME_QUEST_SCRIPT = "FO4SF_NewGameQuest"
PEX_MAGIC = 0xFA57C0DE

_PEX_FIXED_OP_ARGS: Dict[int, int] = {
    0x00: 0,
    0x01: 3, 0x02: 3, 0x03: 3, 0x04: 3, 0x05: 3, 0x06: 3, 0x07: 3, 0x08: 3, 0x09: 3,
    0x0A: 2, 0x0B: 2, 0x0C: 2, 0x0D: 2, 0x0E: 2,
    0x0F: 3, 0x10: 3, 0x11: 3, 0x12: 3, 0x13: 3,
    0x14: 1, 0x15: 2, 0x16: 2,
    0x1A: 1, 0x1B: 3, 0x1C: 3, 0x1D: 3,
    0x1E: 2, 0x1F: 2, 0x20: 3, 0x21: 3, 0x22: 4, 0x23: 4,
    0x24: 3, 0x25: 1, 0x26: 3, 0x27: 3, 0x28: 5, 0x29: 5,
    0x2A: 3, 0x2B: 3, 0x2C: 1, 0x2D: 3, 0x2E: 1,
    0x2F: 6,
}
_PEX_VARARG_OP_ARGS: Dict[int, int] = {0x17: 3, 0x18: 2, 0x19: 3}
_PEX_DST0_OPS: frozenset[int] = frozenset({
    0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09,
    0x0A, 0x0B, 0x0C, 0x0D, 0x0E,
    0x0F, 0x10, 0x11, 0x12, 0x13,
    0x1B, 0x1E, 0x1F, 0x20, 0x24, 0x25, 0x26,
})
_PEX_DST1_OPS: frozenset[int] = frozenset({0x18, 0x22, 0x23, 0x28, 0x29})
_PEX_DST2_OPS: frozenset[int] = frozenset({0x17, 0x19, 0x1C})

NOT_BUILT_MUSEUM_CONTENT: Tuple[str, ...] = (
    "laser musket",
    "balcony talk",
    "power armor + fusion core",
    "minigun",
    "second wave",
    "deathclaw",
    "preston's group moving to sanctuary",
)

VALID_STAGE_CAUSES: frozenset[str] = frozenset(
    {"scene", "info", "trigger", "bench", "vault_console"}
)

CANONICAL_CAUSE_TRIGGER = "Trigger"
CANONICAL_SOURCE_LIFT = "Lift"
CANONICAL_WHY_RELOAD = "Reload"

# H00(a): Single canonical Session 2 PASS table shared by `docs/testing/lead-run-order.md`,
# `check_beginning_pilot.py`, and `tests/test_lead_cards_beginning.py`.
SESSION2_SHEET_PASS_SPECS: Tuple[Tuple[str, str], ...] = (
    ("Card A", "FO4SFLIST rt=<rt> init speaker_present=True arrival_present=True end=true"),
    ("Card A", "FO4SFLIST rt=<rt> summary ok=true host_menu=DialogueMenu replaced_swf=false end=true"),
    ("Card 1", "step=core_value_resolve name=FO4SF_PipboyAcquired source=FO4SFCoreValues.esm:000865 found=1 form=<hex>"),
    ("Card 1", "step=boot_sequence movie=pipboybootsequence first_open=1 page=<page> loose=<0|1>"),
    ("Card 1", "step=boot_sequence finished=1 reopen_page=<page>"),
    ("Card 1", "step=map_markers n=<k> discovered=1 undiscovered=<u_cnt> player_idx=<idx> corners_set=3/3 read_back=match"),
    ("Card 1", "step=map_check_hardcore idx=<idx> source=FO4SFCoreValues.esm:000841 allow=1"),
    ("Card 2", "FO4SF_NEWGAME rt=<rt> start room ready by=<by> loaded=true cell=<cell> backdrop=empty_cell"),
    ("Card 2", "FO4SF_NEWGAME rt=<rt> mode choice mode=story survival=0"),
    ("Card 2", "FO4SF_NEWGAME rt=<rt> start record mode=story story=fo4_commonwealth faction=-1 place=fo4_vault111 survival=0 difficulty=1 backdrop=empty_cell"),
    ("Card 2", f"FO4SF_NEWGAME rt=<rt> stage 10 by={CANONICAL_CAUSE_TRIGGER}"),
    ("Card 2", "FO4SF_NEWGAME rt=<rt> stage 20 by=scene"),
    ("Card 2", "FO4SF_NEWGAME rt=<rt> pistol picked item=<form> count=<n> equipped=<equipped> base=<base>"),
    ("Card 2", "FO4SF_NEWGAME rt=<rt> pipboy pickup equipped flag=1 worn=true"),
    ("Card 2", "FO4SF_NEWGAME rt=<rt> cog door console activated ref=<ref> before=<s0> after=<s1>"),
    ("Card 2", "FO4SF_NEWGAME rt=<rt> stage 30 by=vault_console"),
    ("Card 2", "FO4SF_NEWGAME rt=<rt> special box shown box=FO4SF_ProgSpecialPage1Msg buttons=7 unspent=<u0> step=1"),
    ("Card 2", f"FO4SF_NEWGAME rt=<rt> special set S=<s> P=<p> E=<e> C=<c> I=<i> A=<a> L=<l> sum=40 source={CANONICAL_SOURCE_LIFT}"),
    ("Card 2", "FO4SF_NEWGAME rt=<rt> ascent carried confirmed elapsed=<sec> z=<z1>"),
    ("Card 2", "FO4SF_NEWGAME rt=<rt> surface pre_setposition target=<tx> <ty> <tz> cell=<cell> world=<world>"),
    ("Card 2", f"FO4SF_NEWGAME rt=<rt> stage 40 by={CANONICAL_CAUSE_TRIGGER}"),
    ("Card 2", "FO4SF_NEWGAME rt=<rt> landed z=<z> confirmed=True fallback=false world=<world>"),
    ("Card 2", f"FO4SF_NEWGAME rt=<rt> stage 200 by={CANONICAL_CAUSE_TRIGGER}"),
    ("Card 5", "FO4SF_MISSION rt=<rt> mission gate mode=1 started=true"),
    ("Card 5", "FO4SF_MISSION rt=<rt> min00 given by=codsworth"),
    ("Card 5", "FO4SF_MISSION rt=<rt> stage 10 by=info"),
    ("Card 5", f"FO4SF_MISSION rt=<rt> stage 20 by={CANONICAL_CAUSE_TRIGGER}"),
    ("Card 5", "FO4SF_MISSION rt=<rt> reload mission stage=20 relocate_fails=0"),
    ("Card 5", f"FO4SF_MISSION rt=<rt> stage 30 by={CANONICAL_CAUSE_TRIGGER}"),
    ("Card 5", "FO4SF_MISSION rt=<rt> stage 35 by=info"),
    ("Card 5", "FO4SF_MISSION rt=<rt> preston talk end info=0x092A -> stage 40"),
    ("Card 5", "FO4SF_MISSION rt=<rt> stage 40 by=info"),
    ("Card 5", f"FO4SF_MISSION rt=<rt> stage 200 by={CANONICAL_CAUSE_TRIGGER}"),
    ("Card 5", "FO4SF_MISSION rt=<rt> sanctuary01 stage 100 by=bench"),
    ("Card 5", "FO4SF_MISSION rt=<rt> min01 bench activated -> stage 100"),
    ("Card 3", "FO4SFHC rt=<rt> hardcore source gpof=0 start=1 enabled=1 why=start_choice end=true"),
    ("Card 3", f"FO4SFHC rt=<rt> hardcore source gpof=0 start=1 enabled=1 why={CANONICAL_WHY_RELOAD} end=true"),
    ("Card 4", "FO4SF_NEWGAME rt=<rt> warfare pick faction=0 start=minutemen_sanctuary difficulty=<diff>"),
    ("Card 4", "FO4SF_NEWGAME rt=<rt> start record mode=warfare story=none faction=0 place=minutemen_sanctuary survival=<0|1> difficulty=<diff> backdrop=empty_cell"),
    ("Card 4", f"FO4SF_NEWGAME rt=<rt> stage 210 by={CANONICAL_CAUSE_TRIGGER}"),
    ("Card 4", "FO4SF_MISSION rt=<rt> mission gate mode=2 started=false"),
)


def compile_sheet_line_pattern(sheet_line: str) -> re.Pattern[str]:
    """Compile a case-sensitive regex from a sheet PASS template (`<...>` -> non-empty inline value)."""
    parts = re.split(r"<[^>\r\n]+>", sheet_line)
    regex_str = r"[^\r\n]+?".join(re.escape(p) for p in parts) + r"\s*$"
    return re.compile(regex_str)


def evaluate_session2_sheet_lines(log_dir: str) -> List[Dict[str, Optional[str]]]:
    """Match every `SESSION2_SHEET_PASS_SPECS` entry against all `.log` files in `log_dir` (read-only)."""
    all_lines: List[str] = []
    if log_dir and os.path.isdir(log_dir):
        for entry in sorted(os.listdir(log_dir)):
            if entry.lower().endswith(".log"):
                full = os.path.join(log_dir, entry)
                if os.path.isfile(full):
                    with open(full, encoding="utf-8", errors="replace") as fp:
                        all_lines.extend(ln.rstrip("\r\n") for ln in fp)
    out: List[Dict[str, Optional[str]]] = []
    for card_id, spec_line in SESSION2_SHEET_PASS_SPECS:
        pat = compile_sheet_line_pattern(spec_line)
        first_hit = next((ln for ln in all_lines if pat.search(ln)), None)
        out.append(
            {
                "card": card_id,
                "expected": spec_line,
                "status": "found" if first_hit is not None else "missing",
                "match": first_hit,
            }
        )
    return out


_DISALLOWED_MARKER_TOKENS = ("decoratormarker", "xmarker", "marker", "editor")


def is_disallowed_marker_model(model_path: Optional[str]) -> bool:
    """Return True if an ACTI MODL path is missing/empty or uses a disallowed marker mesh."""
    if not model_path or not isinstance(model_path, str):
        return True
    norm = model_path.replace("/", "\\").strip()
    if not norm:
        return True
    norm_low = norm.lower()
    stem_low = os.path.splitext(os.path.basename(norm))[0].lower()
    return any(tok in norm_low or tok in stem_low for tok in _DISALLOWED_MARKER_TOKENS)


def _iter_esm_subrecords(body: bytes):
    i, n = 0, len(body)
    ext_len: Optional[int] = None
    while i + 6 <= n:
        sig = body[i : i + 4]
        sz = struct.unpack_from("<H", body, i + 4)[0]
        i += 6
        if sig == b"XXXX" and sz == 4 and i + 4 <= n:
            ext_len = struct.unpack_from("<I", body, i)[0]
            i += 4
            continue
        if ext_len is not None:
            sz = ext_len
            ext_len = None
        if i + sz > n:
            break
        yield sig, body[i : i + sz]
        i += sz


def find_bad_placed_activators(esm_path: str) -> Tuple[List[str], List[str]]:
    """Inspect esm_path for any placed ACTI with empty/missing/marker MODL or zero OBND.

    Returns (problems, sorted_distinct_placed_acti_models).
    """
    with open(esm_path, "rb") as fp:
        raw = fp.read()
    if len(raw) < 24 or raw[:4] != b"TES4":
        return [], []
    hdr_sz = struct.unpack_from("<I", raw, 4)[0]
    pos = 24 + hdr_sz
    if pos >= len(raw):
        return [], []

    actis: Dict[int, Tuple[str, Optional[str], bytes]] = {}
    placed_refs: List[Tuple[int, str, int]] = []

    def _walk(start: int, end: int) -> None:
        cur = start
        while cur + 24 <= end:
            sig = raw[cur : cur + 4]
            sz = struct.unpack_from("<I", raw, cur + 4)[0]
            if sig == b"GRUP":
                if sz < 24 or cur + sz > end:
                    break
                _walk(cur + 24, cur + sz)
                cur += sz
                continue
            rflags = struct.unpack_from("<I", raw, cur + 8)[0]
            rfid = struct.unpack_from("<I", raw, cur + 12)[0]
            rbody_end = min(end, cur + 24 + sz)
            if sig in (b"ACTI", b"REFR") and rbody_end - (cur + 24) >= 0:
                payload = raw[cur + 24 : rbody_end]
                if (rflags & 0x40000) and len(payload) >= 4:
                    try:
                        payload = zlib.decompress(payload[4:])
                    except zlib.error:
                        payload = b""
                if sig == b"ACTI":
                    edid, modl, obnd = "", None, b""
                    for ss, sp in _iter_esm_subrecords(payload):
                        if ss == b"EDID":
                            edid = sp.rstrip(b"\x00").decode("utf-8", errors="replace")
                        elif ss == b"MODL":
                            modl = sp.rstrip(b"\x00").decode("utf-8", errors="replace")
                        elif ss == b"OBND":
                            obnd = sp
                    actis[rfid] = (edid, modl, obnd)
                else:
                    redid, base_fid = "", 0
                    for ss, sp in _iter_esm_subrecords(payload):
                        if ss == b"EDID":
                            redid = sp.rstrip(b"\x00").decode("utf-8", errors="replace")
                        elif ss == b"NAME" and len(sp) == 4:
                            base_fid = struct.unpack("<I", sp)[0]
                    if base_fid:
                        placed_refs.append((rfid, redid, base_fid))
            cur = rbody_end

    _walk(pos, len(raw))

    problems: List[str] = []
    models: Set[str] = set()
    reported_bad: Set[Tuple[int, int]] = set()
    esm_name = os.path.basename(esm_path)
    for rfid, redid, base_fid in placed_refs:
        if base_fid not in actis:
            continue
        edid, modl, obnd = actis[base_fid]
        bad_reasons: List[str] = []
        if is_disallowed_marker_model(modl):
            bad_reasons.append(f"invalid/marker MODL={modl!r}")
        if len(obnd) != 24:
            bad_reasons.append(f"missing OBND (len={len(obnd)})")
        else:
            x0, y0, z0, x1, y1, z1 = struct.unpack("<6f", obnd)
            if (x1 - x0) <= 1e-3 or (y1 - y0) <= 1e-3 or (z1 - z0) <= 1e-3:
                bad_reasons.append(f"zero ObjectBounds ({x0:.2f}..{x1:.2f}, {y0:.2f}..{y1:.2f}, {z0:.2f}..{z1:.2f})")
        if bad_reasons and (rfid, base_fid) not in reported_bad:
            reported_bad.add((rfid, base_fid))
            problems.append(
                f"{esm_name}: placed ACTI {edid or hex(base_fid)} (0x{base_fid:08X}) on "
                f"{redid or hex(rfid)} (0x{rfid:08X}) has " + "; ".join(bad_reasons)
            )
        elif modl:
            models.add(modl.replace("/", "\\").lstrip("\\"))
    return problems, sorted(models)


def verify_placed_acti_assets(
    esm_path: str,
    data_dir: str,
    extra_ba2_paths: Sequence[str] = (),
) -> List[str]:
    """Verify .nif, .mesh, .mat, and .dds dependencies exist for placed ACTIs in esm_path."""
    problems, placed_models = find_bad_placed_activators(esm_path)
    if not placed_models:
        return problems

    from . import nif as fo4_nif, sfnif as sf_nif
    from .ba2 import Ba2

    opened_ba2s: List[Tuple[Ba2, Dict[str, str]]] = []
    for bp in extra_ba2_paths:
        if bp and os.path.isfile(bp):
            arch = Ba2(bp)
            idx = {e.name.replace("/", "\\").lstrip("\\").lower(): e.name for e in arch.entries}
            opened_ba2s.append((arch, idx))

    def _read_asset(rel_backslash: str, require_port_ba2: bool = False) -> Tuple[Optional[bytes], bool]:
        rel_clean = rel_backslash.replace("/", "\\").lstrip("\\")
        fs_path = os.path.join(data_dir, *rel_clean.split("\\"))
        if os.path.isfile(fs_path):
            with open(fs_path, "rb") as fp:
                return fp.read(), True
        low = rel_clean.lower()
        for arch, idx in opened_ba2s:
            if low in idx:
                return arch.read(idx[low]), True
        if require_port_ba2 and not opened_ba2s:
            return None, False
        return None, True

    checked_mats: Set[str] = set()
    for rel_modl in placed_models:
        low_modl = rel_modl.lower()
        nif_rel = rel_modl if low_modl.startswith("meshes\\") else f"meshes\\{rel_modl}"
        is_port_asset = "\\fo4port\\" in f"\\{low_modl}" or low_modl.startswith("fo4port\\")
        nif_bytes, can_verify_asset = _read_asset(nif_rel, require_port_ba2=is_port_asset)
        if not can_verify_asset:
            continue
        if nif_bytes is None:
            problems.append(f"B1: missing ACTI NIF asset Data/{nif_rel.replace(os.sep, '/')}")
            continue
        parsed = fo4_nif.parse(nif_bytes)
        for i, blk in enumerate(parsed.blocks):
            if parsed.type_of(i) == "BSGeometry":
                for mesh in sf_nif.parse_bsgeometry(blk).meshes:
                    if mesh is not None:
                        mrel = "geometries\\" + mesh.path.decode("latin-1").replace("/", "\\").lstrip("\\") + ".mesh"
                        mbytes, m_checked = _read_asset(mrel, require_port_ba2=is_port_asset)
                        if m_checked and mbytes is None:
                            problems.append(f"B1: missing .mesh {mrel} referenced by {nif_rel}")
        for raw_str in parsed.strings:
            sp = raw_str.decode("latin-1").replace("/", "\\").lstrip("\\")
            sp_low = sp.lower()
            if sp_low.startswith("materials\\fo4") and sp_low.endswith(".mat") and sp_low not in checked_mats:
                checked_mats.add(sp_low)
                mat_bytes, mat_checked = _read_asset(sp, require_port_ba2=is_port_asset)
                if not mat_checked:
                    continue
                if mat_bytes is None:
                    problems.append(f"B1: missing .mat {sp} referenced by {nif_rel}")
                    continue
                mat_obj = json.loads(mat_bytes.decode("utf-8-sig"))
                stack: List[object] = [mat_obj]
                while stack:
                    cur = stack.pop()
                    if isinstance(cur, dict):
                        stack.extend(cur.values())
                    elif isinstance(cur, list):
                        stack.extend(cur)
                    elif isinstance(cur, str):
                        tp = cur.replace("/", "\\").lstrip("\\")
                        tp_low = tp.lower()
                        if tp_low.startswith("data\\"):
                            tp = tp[5:]
                            tp_low = tp.lower()
                        if tp_low.startswith("textures\\fo4") and tp_low.endswith(".dds"):
                            dbytes, d_checked = _read_asset(tp, require_port_ba2=is_port_asset)
                            if d_checked and dbytes is None:
                                problems.append(f"B1: missing .dds {tp} referenced by {sp}")
    return problems


BASE_SKIP_ACTI_PLUGINS: frozenset[str] = frozenset({
    "fo4actorraider.esm",
    "fo4terraincore.esm",
    "fo4terraincore_mars.esm",
})


def _is_tes4_plugin(path: str) -> bool:
    try:
        with open(path, "rb") as fp:
            hdr = fp.read(24)
        return len(hdr) == 24 and hdr[:4] == b"TES4"
    except OSError:
        return False


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _pex_read_wstr(buf: bytes, pos: int) -> Tuple[str, int]:
    if pos + 2 > len(buf):
        raise ValueError(f"truncated PEX string length at {pos}")
    n = struct.unpack_from("<H", buf, pos)[0]
    pos += 2
    if pos + n > len(buf):
        raise ValueError(f"truncated PEX string ({n} bytes) at {pos}")
    return buf[pos:pos + n].decode("utf-8", "replace"), pos + n


def _pex_read_var_data(buf: bytes, pos: int, strings: Sequence[str]) -> Tuple[Tuple[str, object], int]:
    if pos >= len(buf):
        raise ValueError(f"truncated PEX variable value at {pos}")
    vtype = buf[pos]
    pos += 1
    if vtype == 0:
        return ("null", None), pos
    if vtype in (1, 2):
        if pos + 2 > len(buf):
            raise ValueError(f"truncated PEX string index at {pos}")
        idx = struct.unpack_from("<H", buf, pos)[0]
        if idx >= len(strings):
            raise ValueError(f"PEX string index {idx} out of range ({len(strings)})")
        return ("id" if vtype == 1 else "str", strings[idx]), pos + 2
    if vtype == 3:
        if pos + 4 > len(buf):
            raise ValueError(f"truncated PEX int at {pos}")
        return ("int", struct.unpack_from("<i", buf, pos)[0]), pos + 4
    if vtype == 4:
        if pos + 4 > len(buf):
            raise ValueError(f"truncated PEX float at {pos}")
        return ("float", struct.unpack_from("<f", buf, pos)[0]), pos + 4
    if vtype == 5:
        if pos >= len(buf):
            raise ValueError(f"truncated PEX bool at {pos}")
        return ("bool", bool(buf[pos])), pos + 1
    raise ValueError(f"unsupported PEX variable data type {vtype} at {pos - 1}")


def _pex_read_fn_body(buf: bytes, pos: int, strings: Sequence[str]) -> Tuple[dict, int]:
    if pos + 11 > len(buf):
        raise ValueError(f"truncated PEX function header at {pos}")
    ret_idx, _doc, _uflags, flags, pcnt = struct.unpack_from("<HHIBH", buf, pos)
    pos += 11
    params: List[Tuple[str, str]] = []
    for _ in range(pcnt):
        if pos + 4 > len(buf):
            raise ValueError(f"truncated PEX parameter at {pos}")
        pnm, ptp = struct.unpack_from("<HH", buf, pos)
        pos += 4
        params.append((strings[pnm], strings[ptp]))
    if pos + 2 > len(buf):
        raise ValueError(f"truncated PEX local count at {pos}")
    lcnt = struct.unpack_from("<H", buf, pos)[0]
    pos += 2
    locals_list: List[Tuple[str, str]] = []
    for _ in range(lcnt):
        if pos + 4 > len(buf):
            raise ValueError(f"truncated PEX local at {pos}")
        lnm, ltp = struct.unpack_from("<HH", buf, pos)
        pos += 4
        locals_list.append((strings[lnm], strings[ltp]))
    if pos + 2 > len(buf):
        raise ValueError(f"truncated PEX instruction count at {pos}")
    icnt = struct.unpack_from("<H", buf, pos)[0]
    pos += 2
    instructions: List[Tuple[int, List[object]]] = []
    for _ in range(icnt):
        if pos >= len(buf):
            raise ValueError(f"truncated PEX instruction at {pos}")
        op = buf[pos]
        pos += 1
        args: List[object] = []
        if op in _PEX_FIXED_OP_ARGS:
            for _ in range(_PEX_FIXED_OP_ARGS[op]):
                val, pos = _pex_read_var_data(buf, pos, strings)
                args.append(val)
        elif op in _PEX_VARARG_OP_ARGS:
            for _ in range(_PEX_VARARG_OP_ARGS[op]):
                val, pos = _pex_read_var_data(buf, pos, strings)
                args.append(val)
            vc_arg, pos = _pex_read_var_data(buf, pos, strings)
            if vc_arg[0] != "int" or not isinstance(vc_arg[1], int) or vc_arg[1] < 0:
                raise ValueError(f"invalid PEX vararg count {vc_arg!r} at {pos}")
            vargs: List[Tuple[str, object]] = []
            for _ in range(vc_arg[1]):
                val, pos = _pex_read_var_data(buf, pos, strings)
                vargs.append(val)
            args.append(vargs)
        else:
            raise ValueError(f"unsupported PEX opcode 0x{op:02X} at {pos - 1}")
        instructions.append((op, args))
    return {
        "return_type": strings[ret_idx],
        "flags": flags,
        "params": params,
        "locals": locals_list,
        "instructions": instructions,
    }, pos


def _parse_pex_objects(buf: bytes) -> Dict[str, Dict[str, object]]:
    """Parse a compiled Papyrus `.pex` binary into `{object_name: {'vars': ..., 'functions': ...}}`."""
    if len(buf) < 16:
        raise ValueError("truncated PEX header")
    magic, major, minor, _gid = struct.unpack_from("<IBBH", buf, 0)
    if magic != PEX_MAGIC:
        raise ValueError(f"not a little-endian PEX file (magic=0x{magic:08X})")
    pos = 16
    for _ in range(3):
        _, pos = _pex_read_wstr(buf, pos)
    if pos + 2 > len(buf):
        raise ValueError("truncated PEX string table count")
    scount = struct.unpack_from("<H", buf, pos)[0]
    pos += 2
    strings: List[str] = []
    for _ in range(scount):
        s, pos = _pex_read_wstr(buf, pos)
        strings.append(s)

    if pos >= len(buf):
        raise ValueError("truncated PEX debug flag")
    has_debug = buf[pos]
    pos += 1
    if has_debug:
        pos += 8
        if pos + 2 > len(buf):
            raise ValueError("truncated PEX debug function count")
        fc = struct.unpack_from("<H", buf, pos)[0]
        pos += 2
        for _ in range(fc):
            pos += 7
            if pos + 2 > len(buf):
                raise ValueError("truncated PEX debug line count")
            ic = struct.unpack_from("<H", buf, pos)[0]
            pos += 2 + (ic * 2)
        if (major, minor) >= (3, 9):
            pgc = struct.unpack_from("<H", buf, pos)[0]
            pos += 2
            for _ in range(pgc):
                pos += 10
                nc = struct.unpack_from("<H", buf, pos)[0]
                pos += 2 + (nc * 2)
            soc = struct.unpack_from("<H", buf, pos)[0]
            pos += 2
            for _ in range(soc):
                pos += 4
                nc = struct.unpack_from("<H", buf, pos)[0]
                pos += 2 + (nc * 2)

    if pos + 2 > len(buf):
        raise ValueError("truncated PEX user flags")
    ufc = struct.unpack_from("<H", buf, pos)[0]
    pos += 2 + (ufc * 3)
    if pos + 2 > len(buf):
        raise ValueError("truncated PEX object count")
    ocount = struct.unpack_from("<H", buf, pos)[0]
    pos += 2

    objects: Dict[str, Dict[str, object]] = {}
    for _ in range(ocount):
        if pos + 17 > len(buf):
            raise ValueError(f"truncated PEX object header at {pos}")
        oname_idx, _osize = struct.unpack_from("<HI", buf, pos)
        pos += 6
        pos += 11  # parent, docstring, constFlag, userFlags, autoStateName
        if (major, minor) >= (3, 9):
            st_cnt = struct.unpack_from("<H", buf, pos)[0]
            pos += 2
            for _ in range(st_cnt):
                _sn, mc = struct.unpack_from("<HH", buf, pos)
                pos += 4
                for _ in range(mc):
                    pos += 8
                    _, pos = _pex_read_var_data(buf, pos, strings)
                    pos += 3

        vc = struct.unpack_from("<H", buf, pos)[0]
        pos += 2
        obj_vars: List[Tuple[str, str]] = []
        for _ in range(vc):
            vn_idx, vt_idx, _vu = struct.unpack_from("<HHI", buf, pos)
            pos += 8
            _, pos = _pex_read_var_data(buf, pos, strings)
            if (major, minor) >= (3, 9):
                pos += 1
            obj_vars.append((strings[vn_idx], strings[vt_idx]))

        if (major, minor) >= (3, 10):
            gc = struct.unpack_from("<H", buf, pos)[0]
            pos += 2 + (gc * 2)

        pc = struct.unpack_from("<H", buf, pos)[0]
        pos += 2
        for _ in range(pc):
            _pn, _pt, _pd, _pu, pf = struct.unpack_from("<HHHIB", buf, pos)
            pos += 11
            if pf & 4:
                pos += 2
            else:
                if pf & 1:
                    _, pos = _pex_read_fn_body(buf, pos, strings)
                if pf & 2:
                    _, pos = _pex_read_fn_body(buf, pos, strings)

        stc = struct.unpack_from("<H", buf, pos)[0]
        pos += 2
        fns: Dict[Tuple[str, str], dict] = {}
        for _ in range(stc):
            sn_idx, fnc = struct.unpack_from("<HH", buf, pos)
            pos += 4
            state_name = strings[sn_idx]
            for _ in range(fnc):
                fn_idx = struct.unpack_from("<H", buf, pos)[0]
                pos += 2
                body, pos = _pex_read_fn_body(buf, pos, strings)
                fns[(state_name, strings[fn_idx])] = body
        objects[strings[oname_idx]] = {"vars": obj_vars, "functions": fns}

    if pos != len(buf):
        raise ValueError(f"PEX parse ended at byte {pos}, expected {len(buf)}")
    return objects


def pex_defined_functions(buf: bytes, script_name: str = MAP_MARKERS_SCRIPT) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Return `(default_state_map, all_states_map)` of `{fn_casefold: fn_name}` defined on `script_name`."""
    objects = _parse_pex_objects(buf)
    target = next((obj for name, obj in objects.items() if name.casefold() == script_name.casefold()), None)
    if target is None:
        raise ValueError(f"PEX lacks script object {script_name}")
    default_fns: Dict[str, str] = {}
    all_fns: Dict[str, str] = {}
    for (state_name, fn_name) in target["functions"]:
        low = fn_name.casefold()
        all_fns.setdefault(low, fn_name)
        if state_name == "":
            default_fns.setdefault(low, fn_name)
    return default_fns, all_fns


def extract_mapmarker_calls_from_pex(
    buf: bytes,
    script_name: str = MAP_MARKERS_SCRIPT,
    caller_object: Optional[str] = NEWGAME_QUEST_SCRIPT,
) -> List[str]:
    """Extract member function names called on `script_name` (via `CastAs` + `CallFunction` or typed refs) from PEX."""
    objects = _parse_pex_objects(buf)
    target_low = script_name.casefold()
    called: Dict[str, str] = {}

    selected_objs = [
        obj for name, obj in objects.items()
        if caller_object is None or name.casefold() == caller_object.casefold()
    ]
    for obj in selected_objs:
        typed_obj_vars = {vn.casefold() for vn, vt in obj["vars"] if vt.casefold() == target_low}
        for _fn_key, body in obj["functions"].items():
            typed_vars = set(typed_obj_vars)
            for vn, vt in body["params"] + body["locals"]:
                if vt.casefold() == target_low:
                    typed_vars.add(vn.casefold())
            mm_vars = set(typed_vars)

            for op, args in body["instructions"]:
                if op == 0x17:
                    method = str(args[0][1])
                    recv = args[1]
                    dst = args[2]
                    vargs = args[3]
                    if recv[0] == "id" and str(recv[1]).casefold() in mm_vars:
                        m_low = method.casefold()
                        if m_low in ("callfunction", "callfunctionnowait"):
                            if vargs and vargs[0][0] == "str" and str(vargs[0][1]):
                                tgt = str(vargs[0][1])
                                called.setdefault(tgt.casefold(), tgt)
                        elif m_low != "castas":
                            called.setdefault(m_low, method)
                    if dst[0] == "id":
                        dst_low = str(dst[1]).casefold()
                        if (
                            method.casefold() == "castas"
                            and vargs
                            and vargs[0][0] == "str"
                            and str(vargs[0][1]).casefold() == target_low
                        ):
                            mm_vars.add(dst_low)
                        elif dst_low not in typed_vars:
                            mm_vars.discard(dst_low)
                    continue

                if op in (0x0D, 0x0E):
                    dst, src = args[0], args[1]
                    if dst[0] == "id":
                        dst_low = str(dst[1]).casefold()
                        if src[0] == "id" and str(src[1]).casefold() in mm_vars:
                            mm_vars.add(dst_low)
                        elif dst_low not in typed_vars:
                            mm_vars.discard(dst_low)
                    continue

                dst_idx = 0 if op in _PEX_DST0_OPS else 1 if op in _PEX_DST1_OPS else 2 if op in _PEX_DST2_OPS else None
                if dst_idx is not None and dst_idx < len(args):
                    dst = args[dst_idx]
                    if isinstance(dst, tuple) and dst[0] == "id":
                        dst_low = str(dst[1]).casefold()
                        if dst_low not in typed_vars:
                            mm_vars.discard(dst_low)

    return sorted(called.values())


def _strip_psc_comments_and_docs(psc_text: str) -> str:
    """Strip Papyrus `{ ... }` docstrings and `; ...` line comments while preserving string literals."""
    out: List[str] = []
    i = 0
    n = len(psc_text)
    in_str = False
    in_doc = False
    while i < n:
        ch = psc_text[i]
        if in_doc:
            if ch == "}":
                in_doc = False
            elif ch == "\n":
                out.append("\n")
            i += 1
            continue
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(psc_text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "{":
            in_doc = True
            i += 1
            continue
        if ch == ";":
            while i < n and psc_text[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def extract_mapmarker_calls_from_psc(psc_text: str, script_name: str = MAP_MARKERS_SCRIPT) -> List[str]:
    """Extract member function names called on `script_name` from Papyrus source (`CastAs` + `CallFunction` / typed calls)."""
    cleaned = _strip_psc_comments_and_docs(psc_text)
    esc = re.escape(script_name)
    mm_vars: Set[str] = set()
    for m in re.finditer(rf"\b([A-Za-z_]\w*)\s*=\s*[^\r\n;]*\.CastAs\(\s*\"{esc}\"\s*\)", cleaned, re.IGNORECASE):
        mm_vars.add(m.group(1).casefold())
    for m in re.finditer(rf"^\s*{esc}\s+(?:Property\s+)?([A-Za-z_]\w*)\b", cleaned, re.IGNORECASE | re.MULTILINE):
        mm_vars.add(m.group(1).casefold())
    for m in re.finditer(rf"\b([A-Za-z_]\w*)\s*=\s*[^\r\n;]*\bas\s+{esc}\b", cleaned, re.IGNORECASE):
        mm_vars.add(m.group(1).casefold())

    called: Dict[str, str] = {}
    for var_low in sorted(mm_vars):
        var_esc = re.escape(var_low)
        for m in re.finditer(
            rf"\b{var_esc}\s*\.\s*CallFunction(?:NoWait)?\(\s*\"([A-Za-z_]\w*)\"",
            cleaned,
            re.IGNORECASE,
        ):
            fn = m.group(1)
            called.setdefault(fn.casefold(), fn)
        for m in re.finditer(rf"\b{var_esc}\s*\.\s*([A-Za-z_]\w*)\s*\(", cleaned, re.IGNORECASE):
            fn = m.group(1)
            if fn.casefold() not in ("castas", "callfunction", "callfunctionnowait"):
                called.setdefault(fn.casefold(), fn)

    for m in re.finditer(
        rf"\.CastAs\(\s*\"{esc}\"\s*\)\s*\.\s*CallFunction(?:NoWait)?\(\s*\"([A-Za-z_]\w*)\"",
        cleaned,
        re.IGNORECASE,
    ):
        fn = m.group(1)
        called.setdefault(fn.casefold(), fn)
    for m in re.finditer(rf"\bas\s+{esc}\s*\)\s*\.\s*([A-Za-z_]\w*)\s*\(", cleaned, re.IGNORECASE):
        fn = m.group(1)
        if fn.casefold() not in ("castas", "callfunction", "callfunctionnowait"):
            called.setdefault(fn.casefold(), fn)

    return sorted(called.values())


def verify_map_markers_bundle_compatibility(bundle_dir: str, repo_root: Optional[str] = None) -> List[str]:
    """Verify staged `FO4SFMapMarkers.esm`, `FO4SFMapMarkers - Main.ba2`, `core.json`, and `FO4SF_NewGameQuest` calls."""
    b_abs = os.path.abspath(bundle_dir)
    issues: List[str] = []

    mm_subdir = os.path.join(b_abs, MAP_MARKERS_DIRNAME)
    if os.path.isdir(mm_subdir):
        mm_root = mm_subdir
        rel_prefix = MAP_MARKERS_DIRNAME + "/"
        require_core_json = True
    elif os.path.isfile(os.path.join(b_abs, MAP_MARKERS_PLUGIN)) or os.path.isfile(os.path.join(b_abs, MAP_MARKERS_ARCHIVE)):
        mm_root = b_abs
        rel_prefix = ""
        require_core_json = False
    else:
        return [f"missing {MAP_MARKERS_DIRNAME}/{MAP_MARKERS_PLUGIN} and {MAP_MARKERS_DIRNAME}/{MAP_MARKERS_ARCHIVE}"]

    mm_esm = os.path.join(mm_root, MAP_MARKERS_PLUGIN)
    if not os.path.isfile(mm_esm):
        issues.append(f"missing {rel_prefix}{MAP_MARKERS_PLUGIN}")
    else:
        try:
            with RawEsmPlugin(mm_esm) as mm_plg:
                masters_low = {m.casefold() for m in mm_plg.masters}
                if "fo4terraincore.esm" not in masters_low:
                    issues.append(f"{rel_prefix}{MAP_MARKERS_PLUGIN} does not master FO4TerrainCore.esm")
        except (OSError, EsmError) as exc:
            issues.append(f"invalid TES4 plugin {rel_prefix}{MAP_MARKERS_PLUGIN}: {exc}")

    core_json_p = os.path.join(mm_root, "core.json")
    bundle_core_p = os.path.join(b_abs, "FO4TerrainCore.esm")
    if require_core_json or os.path.isfile(core_json_p):
        if not os.path.isfile(core_json_p):
            issues.append(f"missing {rel_prefix}core.json")
        else:
            try:
                with open(core_json_p, encoding="utf-8") as fp:
                    pin_doc = json.load(fp)
                masters = pin_doc.get("masters") if isinstance(pin_doc, dict) else None
                if not isinstance(masters, dict):
                    raise ValueError("core.json missing 'masters' object")
                pinned_core = next(
                    (str(v).lower() for k, v in masters.items() if str(k).casefold() == "fo4terraincore.esm"),
                    None,
                )
                if not pinned_core:
                    raise ValueError("core.json lacks FO4TerrainCore.esm sha256")
                if os.path.isfile(bundle_core_p):
                    actual_core = _sha256_file(bundle_core_p).lower()
                    if pinned_core != actual_core:
                        issues.append(
                            f"{rel_prefix}core.json pins FO4TerrainCore.esm {pinned_core[:12]}... "
                            f"!= bundle FO4TerrainCore.esm {actual_core[:12]}..."
                        )
            except (OSError, ValueError) as exc:
                issues.append(f"invalid {rel_prefix}core.json: {exc}")

    mm_ba2 = os.path.join(mm_root, MAP_MARKERS_ARCHIVE)
    packed_pex: Optional[bytes] = None
    if not os.path.isfile(mm_ba2):
        issues.append(f"missing {rel_prefix}{MAP_MARKERS_ARCHIVE}")
    else:
        try:
            arc = Ba2(mm_ba2)
            if arc.kind != "GNRL":
                issues.append(f"{rel_prefix}{MAP_MARKERS_ARCHIVE} must be GNRL archive (found {arc.kind})")
            else:
                idx = arc.find(MAP_MARKERS_PEX_REL)
                if idx is None:
                    issues.append(f"{rel_prefix}{MAP_MARKERS_ARCHIVE} missing {MAP_MARKERS_PEX_REL}")
                else:
                    packed_pex = arc.read(idx)
        except (OSError, Ba2Error) as exc:
            issues.append(f"unreadable BA2 {rel_prefix}{MAP_MARKERS_ARCHIVE}: {exc}")

    loose_candidates: List[Tuple[str, str]] = [
        (f"{rel_prefix}Data/{MAP_MARKERS_PEX_REL}", os.path.join(mm_root, "Data", *MAP_MARKERS_PEX_REL.split("/")))
    ]
    if mm_root != b_abs:
        loose_candidates.append((f"Data/{MAP_MARKERS_PEX_REL}", os.path.join(b_abs, "Data", *MAP_MARKERS_PEX_REL.split("/"))))

    loose_pex_blobs: List[Tuple[str, bytes]] = []
    for loose_rel, loose_path in loose_candidates:
        if os.path.isfile(loose_path):
            try:
                loose_bytes = Path(loose_path).read_bytes()
            except OSError as exc:
                issues.append(f"unreadable loose {loose_rel}: {exc}")
                continue
            loose_pex_blobs.append((loose_rel, loose_bytes))
            if packed_pex is not None and loose_bytes != packed_pex:
                issues.append(
                    f"loose {loose_rel} differs from {MAP_MARKERS_PEX_REL} inside {rel_prefix}{MAP_MARKERS_ARCHIVE}"
                )

    required_calls: List[str] = []
    ng_pex_path = os.path.join(b_abs, "Data", "Scripts", f"{NEWGAME_QUEST_SCRIPT}.pex")
    ng_is_real_pex = False
    if os.path.isfile(ng_pex_path):
        try:
            ng_bytes = Path(ng_pex_path).read_bytes()
            if len(ng_bytes) >= 4 and struct.unpack_from("<I", ng_bytes, 0)[0] == PEX_MAGIC:
                ng_is_real_pex = True
                required_calls = extract_mapmarker_calls_from_pex(ng_bytes, MAP_MARKERS_SCRIPT, NEWGAME_QUEST_SCRIPT)
        except (OSError, ValueError) as exc:
            issues.append(f"unreadable {NEWGAME_QUEST_SCRIPT}.pex: {exc}")

    if not ng_is_real_pex:
        repo_base = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
        ng_psc_path = repo_base / "scripts" / "newgame" / f"{NEWGAME_QUEST_SCRIPT}.psc"
        if not ng_psc_path.is_file():
            issues.append(f"cannot extract {MAP_MARKERS_SCRIPT} calls: missing {ng_psc_path}")
        else:
            required_calls = extract_mapmarker_calls_from_psc(
                ng_psc_path.read_text(encoding="utf-8", errors="replace"),
                MAP_MARKERS_SCRIPT,
            )

    if not required_calls and not any("unreadable" in msg or "cannot extract" in msg for msg in issues):
        issues.append(f"no {MAP_MARKERS_SCRIPT} member-function calls found in {NEWGAME_QUEST_SCRIPT}")

    pex_sources_to_check: List[Tuple[str, bytes]] = []
    if packed_pex is not None:
        pex_sources_to_check.append((f"{rel_prefix}{MAP_MARKERS_ARCHIVE} ({MAP_MARKERS_PEX_REL})", packed_pex))
    for loose_rel, loose_bytes in loose_pex_blobs:
        if packed_pex is None or loose_bytes != packed_pex:
            pex_sources_to_check.append((loose_rel, loose_bytes))

    for src_label, pex_bytes in pex_sources_to_check:
        try:
            default_fns, all_fns = pex_defined_functions(pex_bytes, MAP_MARKERS_SCRIPT)
        except ValueError as exc:
            issues.append(f"{src_label} is not a valid compiled PEX ({exc})")
            continue
        for req_fn in required_calls:
            req_low = req_fn.casefold()
            if req_low not in default_fns:
                if req_low in all_fns:
                    issues.append(
                        f"{src_label} defines {req_fn}() only in a non-default state, not callable on {MAP_MARKERS_SCRIPT}"
                    )
                else:
                    issues.append(
                        f"{src_label} lacks {MAP_MARKERS_SCRIPT}.{req_fn}() called by {NEWGAME_QUEST_SCRIPT}"
                    )

    return issues


def _read_arsenal_weaps_from_esm(cv_path: str) -> Dict[int, str]:
    """Read own WEAP `{local_form_id: editor_id}` entries from `FO4SFCoreValues.esm`."""
    found: Dict[int, str] = {}
    with RawEsmPlugin(cv_path) as plg:
        self_idx = plg.self_index
        for rec in plg.records("WEAP"):
            if (rec.formid >> 24) == self_idx:
                found[rec.formid & 0x00FFFFFF] = rec.edid
    return found


def _mission_has_s2_s6_markers(mission_path: str) -> bool:
    """Return True if `FO4SFMission.esm` carries S2-S6 quests (`FO4SF_Vault111Roaches` / `FO4SF_LoadDoor`)."""
    if not _is_tes4_plugin(mission_path):
        return False
    try:
        with RawEsmPlugin(mission_path) as plg:
            for rec in plg.records("QUST"):
                if rec.edid.casefold() in ("fo4sf_vault111roaches", "fo4sf_loaddoor"):
                    return True
    except (OSError, EsmError):
        return False
    return False


EXPECTED_ARSENAL_WEAPS: Dict[int, str] = {
    fid: edid for fid, (rtype, edid) in CORE_VALUES_ARSENAL_RECORDS.items() if rtype == "WEAP"
}


def verify_core_values_arsenal_weaps(
    bundle_dir: str,
    *,
    require_arsenal: Optional[bool] = None,
) -> Dict[str, object]:
    """Verify bundled/staged `FO4SFCoreValues.esm` holds `EXPECTED_ARSENAL_WEAPS` when required or detected."""
    b_abs = os.path.abspath(bundle_dir)
    cv_candidates = (
        os.path.join(b_abs, "FO4SFCoreValues.esm"),
        os.path.join(b_abs, "Data", "FO4SFCoreValues.esm"),
    )
    cv_path = next((p for p in cv_candidates if os.path.isfile(p)), cv_candidates[0])
    mission_candidates = (
        os.path.join(b_abs, "FO4SFMission.esm"),
        os.path.join(b_abs, "Data", "FO4SFMission.esm"),
    )
    mission_path = next((p for p in mission_candidates if os.path.isfile(p)), mission_candidates[0])

    bplan: Mapping[str, object] = {}
    bplan_path = os.path.join(b_abs, "bundle_plan.json")
    if os.path.isfile(bplan_path):
        try:
            with open(bplan_path, encoding="utf-8") as fp:
                bplan = json.load(fp)
        except (OSError, ValueError):
            bplan = {}
    bargs = bplan.get("args") if isinstance(bplan.get("args"), Mapping) else {}
    plan_wants_arsenal = bargs.get("fo4_arsenal") == 1

    found_weaps: Dict[int, str] = {}
    read_err: Optional[str] = None
    if os.path.isfile(cv_path):
        try:
            found_weaps = _read_arsenal_weaps_from_esm(cv_path)
        except (OSError, EsmError) as exc:
            read_err = str(exc)

    if require_arsenal is False:
        should_check = False
    elif require_arsenal is True:
        should_check = True
    else:
        should_check = _mission_has_s2_s6_markers(mission_path) or bool(found_weaps) or plan_wants_arsenal

    if not should_check:
        return {
            "status": "SKIP",
            "issues": [],
            "found_count": len(found_weaps),
            "expected_count": len(EXPECTED_ARSENAL_WEAPS),
            "detail": "not required (non-arsenal / candidate-2g-fix7b bundle)",
        }

    issues: List[str] = []
    if not os.path.isfile(cv_path):
        issues.append("missing FO4SFCoreValues.esm")
    elif read_err is not None:
        issues.append(f"unreadable FO4SFCoreValues.esm ({read_err})")
    else:
        missing = [
            f"0x{fid:06X} ({edid})"
            for fid, edid in sorted(EXPECTED_ARSENAL_WEAPS.items())
            if fid not in found_weaps
        ]
        mismatched = [
            f"0x{fid:06X} expected {edid}, got {found_weaps[fid]!r}"
            for fid, edid in sorted(EXPECTED_ARSENAL_WEAPS.items())
            if fid in found_weaps and found_weaps[fid] != edid
        ]
        if missing:
            issues.append(f"missing {len(missing)}/{len(EXPECTED_ARSENAL_WEAPS)} arsenal WEAP(s): {', '.join(missing[:6])}" + ("..." if len(missing) > 6 else ""))
        if mismatched:
            issues.append(f"EditorID mismatch on {len(mismatched)} arsenal WEAP(s): {', '.join(mismatched[:4])}")

    if issues:
        return {
            "status": "FAIL",
            "issues": issues,
            "found_count": len(found_weaps),
            "expected_count": len(EXPECTED_ARSENAL_WEAPS),
            "detail": "; ".join(issues),
        }
    return {
        "status": "PASS",
        "issues": [],
        "found_count": len(found_weaps),
        "expected_count": len(EXPECTED_ARSENAL_WEAPS),
        "detail": f"{len(EXPECTED_ARSENAL_WEAPS)}/{len(EXPECTED_ARSENAL_WEAPS)} arsenal WEAPs verified (0x000899..0x0008D6)",
    }


def verify_bundle_beginning_readiness(
    bundle_dir: str,
    *,
    require_map_markers: bool = True,
    require_arsenal: Optional[bool] = None,
) -> Dict[str, object]:
    """Check offline that `bundle_dir` contains every plugin, script, mesh, and voice asset for `B1`..`B8`."""
    b_abs = os.path.abspath(bundle_dir)
    problems: List[str] = []
    step_results: Dict[str, Dict[str, object]] = {}

    bplan: Mapping[str, object] = {}
    bplan_path = os.path.join(b_abs, "bundle_plan.json")
    if os.path.isfile(bplan_path):
        with open(bplan_path, encoding="utf-8") as fp:
            bplan = json.load(fp)
    active_plugins = {str(p).casefold() for p in (bplan.get("plugins") or [])}
    components = bplan.get("components") if isinstance(bplan.get("components"), Mapping) else {}

    for spec in BEGINNING_STEPS:
        step_issues: List[str] = []
        use_player_special_fallback = (
            spec.step_id == "B3_exit_lift"
            and bool(active_plugins)
            and "fo4sfprogression.esm" not in active_plugins
        )
        req_plugins = (
            tuple(p for p in spec.plugins if p.casefold() != "fo4sfprogression.esm")
            if use_player_special_fallback
            else spec.plugins
        )
        req_scripts = (
            tuple("FO4SF_NewGameSpecial.pex" if s == "FO4SF_ProgressionQuest.pex" else s for s in spec.scripts)
            if use_player_special_fallback
            else spec.scripts
        )
        for p in req_plugins:
            p_full = os.path.join(b_abs, p)
            if not _is_tes4_plugin(p_full):
                step_issues.append(f"missing or invalid TES4 plugin: {p}")
            else:
                if active_plugins and p.casefold() not in active_plugins:
                    step_issues.append(f"plugin {p} missing from bundle_plan.json plugins list")
                if p.casefold() not in BASE_SKIP_ACTI_PLUGINS:
                    bad_actis, _ = find_bad_placed_activators(p_full)
                    step_issues.extend(bad_actis)

        for sc in req_scripts:
            sc_full = os.path.join(b_abs, "Data", "Scripts", sc)
            if not os.path.isfile(sc_full) or os.path.getsize(sc_full) < 16:
                step_issues.append(f"missing compiled Papyrus script: Data/Scripts/{sc}")

        if spec.step_id == "B2_gear_door" and isinstance(components, Mapping) and components:
            cog = components.get("cog_door")
            if not isinstance(cog, Mapping) or len(cog.get("outputs") or {}) < 2:
                step_issues.append("bundle_plan.json missing cog_door mesh/material outputs")

        if spec.step_id == "B3_exit_lift":
            if isinstance(components, Mapping) and components:
                lift = components.get("exit_lift")
                if not isinstance(lift, Mapping) or len(lift.get("outputs") or {}) < 2:
                    step_issues.append("bundle_plan.json missing exit_lift mesh/material outputs")
            mars_esm = os.path.join(b_abs, "FO4TerrainCore_Mars.esm")
            if _is_tes4_plugin(mars_esm):
                from pathlib import Path as _P
                import sys as _sys
                _core_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts", "core")
                if _core_dir not in _sys.path:
                    _sys.path.insert(0, _core_dir)
                import make_core_bundle as _mcb
                g_val = _mcb.read_planet_gravity_g(_P(mars_esm))
                if g_val is not None and abs(g_val - _mcb.EARTH_GRAVITY_G) > 0.02:
                    step_issues.append(f"FO4TerrainCore_Mars.esm PNDT gravity is {g_val:.4f}g, expected {_mcb.EARTH_GRAVITY_G:.2f}g (Earth)")
            if require_map_markers:
                step_issues.extend(verify_map_markers_bundle_compatibility(b_abs))

        if spec.step_id == "B1_vault_start":
            pb_ini = os.path.join(b_abs, "SFSE", "Plugins", "FO4SFPipboyMenu.ini")
            if os.path.isfile(pb_ini):
                ini_txt = open(pb_ini, encoding="utf-8", errors="ignore").read().lower()
                if "requirepickup=" in ini_txt and "requirepickup=1" not in ini_txt:
                    step_issues.append("FO4SFPipboyMenu.ini must set RequirePickup=1")

        if spec.step_id == "B5_codsworth_sanctuary":
            mission_esm_full = os.path.join(b_abs, "FO4SFMission.esm")
            mission_is_tes4 = _is_tes4_plugin(mission_esm_full)
            arma_model_paths: Set[str] = set()
            if mission_is_tes4:
                try:
                    with RawEsmPlugin(mission_esm_full) as mplg:
                        for rec in mplg.records("ARMA"):
                            for tag in (b"MOD2", b"MOD3", b"MODL"):
                                raw_m = rec.get(tag)
                                if not raw_m:
                                    continue
                                norm_m = (
                                    raw_m.split(b"\x00", 1)[0]
                                    .decode("latin-1", errors="replace")
                                    .replace("\\", "/")
                                    .strip()
                                    .casefold()
                                )
                                if norm_m:
                                    arma_model_paths.add(norm_m)
                                    if norm_m.startswith("meshes/"):
                                        arma_model_paths.add(norm_m[len("meshes/"):])
                except (OSError, EsmError) as exc:
                    step_issues.append(f"unreadable FO4SFMission.esm ARMA records ({exc})")

            for label, nif_rel in B5_REQUIRED_ACTOR_NIFS:
                nif_full = os.path.join(b_abs, "Data", *nif_rel.split("/"))
                if not os.path.isfile(nif_full):
                    step_issues.append(f"missing {label}: Data/{nif_rel}")
                mod_rel = nif_rel[len("meshes/"):] if nif_rel.startswith("meshes/") else nif_rel
                if mission_is_tes4 and mod_rel.casefold() not in arma_model_paths and nif_rel.casefold() not in arma_model_paths:
                    step_issues.append(f"FO4SFMission.esm does not reference {label} ({mod_rel})")

            v_dir = os.path.join(b_abs, "Data", *CODSWORTH_VOICE_DIR_REL.split("/"))
            wems = [f for f in os.listdir(v_dir) if f.lower().endswith(".wem")] if os.path.isdir(v_dir) else []
            if len(wems) < MIN_CODSWORTH_WEMS:
                step_issues.append(
                    f"Codsworth voice WEM count {len(wems)} < {MIN_CODSWORTH_WEMS} under Data/{CODSWORTH_VOICE_DIR_REL}"
                )

        problems.extend(f"{spec.step_id}: {msg}" for msg in step_issues)
        step_results[spec.step_id] = {
            "title": spec.title,
            "label": spec.label,
            "status": "PASS" if not step_issues else "FAIL",
            "issues": step_issues,
        }

    arsenal_res = verify_core_values_arsenal_weaps(b_abs, require_arsenal=require_arsenal)
    if arsenal_res["status"] == "FAIL":
        problems.extend(f"arsenal_weap: {msg}" for msg in arsenal_res["issues"])

    return {
        "ok": len(problems) == 0,
        "steps": step_results,
        "arsenal_weaps": arsenal_res,
        "problems": problems,
    }


# ---------------------------------------------------------------------------
# Log Evaluator (`fo4sf_newgame.*.log` + `fo4sf_mission.*.log` + optional `FO4SFProgression.*.log`)
# ---------------------------------------------------------------------------

_NG_RT_RE = re.compile(r"FO4SF_NEWGAME\s+rt=([-\d.]+)\s+", re.IGNORECASE)
_NG_STAGE_RE = re.compile(
    r"FO4SF_NEWGAME(?:\s+rt=([-\d.]+))?\s+stage\s+(\d+)(?:\s+by=([A-Za-z0-9_]+))?\s*$",
    re.IGNORECASE,
)
_NG_MODE_CHOICE_RE = re.compile(r"\bmode choice\b.*?\bmode=(story|warfare|1|2)\b", re.IGNORECASE)
_NG_HOLD1_RE = re.compile(r"hold-off pass 1 stopped=(\d+)\s+of\s+(\d+)", re.IGNORECASE)
_NG_HOLD2_RE = re.compile(r"hold-off pass 2 stopped=(\d+)\s+of\s+(\d+)", re.IGNORECASE)
_NG_HOLD2_STILL_RUNNING_RE = re.compile(r"\bheld off\b.*?\brunning_after=true\b.*?\bpass=2\b", re.IGNORECASE)
_NG_POD_RE = re.compile(r"\bpod settle ok=(true|false)\b", re.IGNORECASE)
_NG_STAND_DOWN_RE = re.compile(r"\b(?:no move into the vault:|not a new game:.*standing down)\b", re.IGNORECASE)

_NG_PISTOL_PICKED_RE = re.compile(r"\bpistol picked\b", re.IGNORECASE)
_NG_PIPBOY_EQUIPPED_RE = re.compile(r"\bpipboy pickup equipped flag=1\b", re.IGNORECASE)
_NG_COG_CONSOLE_RE = re.compile(r"\bcog door console activated\b", re.IGNORECASE)
_NG_COG_OPEN_FAIL_RE = re.compile(r"\bcog door open failed\b", re.IGNORECASE)
_NG_COG_DIRECT_RE = re.compile(r"\bcog door opened directly\b", re.IGNORECASE)
_NG_COG_FAIL_RE = re.compile(r"\bcog door\s+\S+\s+does not resolve\b", re.IGNORECASE)

_NG_SPECIAL_SKIPPED_RE = re.compile(r"\bspecial skipped\b", re.IGNORECASE)
_SPECIAL_DEFAULT_RE = re.compile(r"\bspecial[ _]default\b", re.IGNORECASE)
_NG_SPECIAL_SET_7_RE = re.compile(
    r"\bspecial set\s+S=(\d+)\s+P=(\d+)\s+E=(\d+)\s+C=(\d+)\s+I=(\d+)\s+A=(\d+)\s+L=(\d+)\b",
    re.IGNORECASE,
)
_NG_SPECIAL_SET_SUM_RE = re.compile(r"\bspecial set\b.*?\b(?:special_sum|sum)=(\d+)\b", re.IGNORECASE)
_NG_SPECIAL_FALLBACK_LIFT_RE = re.compile(
    r"\belevator attribute_allocation fallback=FO4SF_NewGameSpecial\b",
    re.IGNORECASE,
)
_NG_MAP_SETUP_RE = re.compile(r"\bmap setup done\b(?:.*?\bmarkers=(\d+))?", re.IGNORECASE)

_NG_ASCENT_PLAY_RE = re.compile(r"\bascent play accepted=(true|false)\b", re.IGNORECASE)
_NG_ASCENT_CONFIRMED_RE = re.compile(r"\bascent carried confirmed\b", re.IGNORECASE)
_NG_EXIT_FAIL_REASON_RE = re.compile(r"\bexit failed reason=([A-Za-z0-9_]+)", re.IGNORECASE)
_NG_EXIT_RETRY_REASON_RE = re.compile(r"\bexit retry\s+n=(\d+)\s+reason=([A-Za-z0-9_]+)", re.IGNORECASE)
_NG_EXIT_FALLBACK_MOVE_RE = re.compile(r"\bexit fallback by=move\b", re.IGNORECASE)
_NG_FELL_RE = re.compile(r"\bfell z=([-\d.]+):\s*fallback pos=", re.IGNORECASE)
_NG_LANDED_FALLBACK_RE = re.compile(r"\blanded z=[-\d.]+.*?\bfallback=true\b", re.IGNORECASE)
_NG_EXIT_ANCHOR_FAIL_RE = re.compile(r"\bexit anchor\s+\S+\s+does not resolve\b", re.IGNORECASE)
_NG_SURFACE_MOVETO_RE = re.compile(r"\bsurface moveto\b", re.IGNORECASE)
_NG_SURFACE_MISSED_RE = re.compile(r"\bsurface missed:\s*still inside\b", re.IGNORECASE)
_NG_FADE_TIMEOUT_RE = re.compile(r"\bmode fade lifted by=timeout\b", re.IGNORECASE)
_NG_START_PLACE_FAIL_RE = re.compile(r"\bstart place move failed\b", re.IGNORECASE)

_MS_RT_RE = re.compile(r"FO4SF_MISSION\s+rt=([-\d.]+)\s+", re.IGNORECASE)
_MS_STAGE_RE = re.compile(
    r"FO4SF_MISSION\s+rt=[-\d.]+\s+stage\s+(\d+)(?:\s+by=([A-Za-z0-9_]+))?\s*$",
    re.IGNORECASE,
)
_MS_CODS_STAGE_RE = re.compile(
    r"FO4SF_MISSION\s+rt=[-\d.]+\s+codsworth01\s+stage\s+(\d+)(?:\s+by=([A-Za-z0-9_]+))?\s*$",
    re.IGNORECASE,
)
_MS_SANCT_STAGE_RE = re.compile(
    r"FO4SF_MISSION\s+rt=[-\d.]+\s+sanctuary01\s+stage\s+(\d+)(?:\s+by=([A-Za-z0-9_]+))?\s*$",
    re.IGNORECASE,
)
_MS_GATE_RE = re.compile(
    r"FO4SF_MISSION\s+rt=[-\d.]+\s+mission gate mode=(\d+)\s+started=(true|false)(?:\s+quest=(\S+))?",
    re.IGNORECASE,
)
_MS_GIVEN_BY_RE = re.compile(r"FO4SF_MISSION\s+rt=[-\d.]+\s+min00 given by=(codsworth|concord)\b", re.IGNORECASE)
_MS_CODS_TALK_END_RE = re.compile(r"\bcodsworth talk end -> min00 stage 10\b", re.IGNORECASE)
_MS_PRESTON_TALK_END_RE = re.compile(r"\bpreston talk end info=(\S+)\s*->\s*stage 40\b", re.IGNORECASE)
_MS_PRESTON_SCENE_END_RE = re.compile(
    r"\bpreston talk scene ended\s+stage=(\d+)(?:\s+end_info=(true|false))?",
    re.IGNORECASE,
)
_MS_STAGE40_FALLBACK_RE = re.compile(r"\bstage 40 by=fallback\b", re.IGNORECASE)
_MS_MIN01_STAGE10_RE = re.compile(r"\b(?:min01 stage 10 objective bench|sanctuary01 init stage=10)\b", re.IGNORECASE)
_MS_MIN01_BENCH_DONE_RE = re.compile(r"\bmin01 bench activated -> stage 100\b", re.IGNORECASE)
_MS_RAIDER_ABSENT_RE = re.compile(r"\braider cleared (?:absent|stuck)\b", re.IGNORECASE)
_MS_RELOAD_RE = re.compile(r"\breload mission stage=(\d+)\s+relocate_fails=0\b", re.IGNORECASE)

_MS_INIT_RAIDERS_RE = re.compile(r"FO4SF_MISSION\s+rt=[-\d.]+\s+init\s+raiders=(\d+)\b", re.IGNORECASE)
_MS_REWARD_RE = re.compile(r"FO4SF_MISSION\s+rt=[-\d.]+\s+reward\s+credits=(\d+)\b", re.IGNORECASE)
_MS_CODS_MOVED_RE = re.compile(
    r"FO4SF_MISSION\s+rt=[-\d.]+\s+moved\s+codsworth\b.*?\bfailed=(true|false)\b",
    re.IGNORECASE,
)
_MS_CODS_PLACE_RE = re.compile(r"FO4SF_MISSION\s+rt=[-\d.]+\s+place\s+codsworth\b", re.IGNORECASE)
_MS_CODS_HOLD_RE = re.compile(
    r"FO4SF_MISSION\s+rt=[-\d.]+\s+hold\s+codsworth\b.*?\boff=([-\d.]+)\b.*?\bok=(true|false)\b",
    re.IGNORECASE,
)
_MS_CODS_GAVE_UP_RE = re.compile(r"\bkeeper gave up codsworth\s+fails=(\d+)\b", re.IGNORECASE)
_MS_CODS_SPOT_STATE_RE = re.compile(
    r"\bkeeper\s+(?:load|status)\s+codsworth\b.*?\bdead=(true|false)\b.*?\bfails=(\d+)\b",
    re.IGNORECASE,
)
_MS_RELOC_MOVE_FAIL_RE = re.compile(
    r"FO4SF_MISSION\s+rt=[-\d.]+\s+moved\s+(?:preston\b.*?\bfailed=true\b.*?\bby=mission\b|raider\s+\d+\b.*?\bfailed=true\b)",
    re.IGNORECASE,
)
_MS_PRESTON_GAVE_UP_RE = re.compile(r"\bkeeper gave up preston\s+fails=(\d+)\b", re.IGNORECASE)
_MS_PRESTON_SPOT_STATE_RE = re.compile(
    r"\bkeeper\s+(?:load|status)\s+preston\b.*?\bdead=(true|false)\b.*?\bfails=(\d+)\b",
    re.IGNORECASE,
)
_MS_PRESTON_HOSTILE_RE = re.compile(r"\bpreston was targeting the player:\s*stopcombat\b", re.IGNORECASE)
_MS_FOLLOW_OK_RE = re.compile(
    r"\bfollow preston test-only\s+alias=\S+\s+filled=(\d+)\s+linked=player\s+released=(true|false)\b",
    re.IGNORECASE,
)
_MS_FOLLOW_REFUSED_RE = re.compile(r"\bfollow preston test-only refused\b", re.IGNORECASE)
_MS_HOLD_PRESTON_RE = re.compile(r"FO4SF_MISSION\s+rt=[-\d.]+\s+hold preston\b", re.IGNORECASE)


def discover_rotated_logs(log_dir: str, channel_prefix: str) -> List[str]:
    """Return rotated log files in chronological order (`*.3.log`, `*.2.log`, `*.1.log`, `*.0.log`)."""
    if not log_dir or not os.path.isdir(log_dir):
        return []
    rot_pat = re.compile(rf"^{re.escape(channel_prefix)}(?:\.(\d+))?\.log$", re.IGNORECASE)
    matched: List[Tuple[int, str]] = []
    for entry in os.listdir(log_dir):
        m = rot_pat.match(entry)
        if not m:
            continue
        full = os.path.join(log_dir, entry)
        if not os.path.isfile(full):
            continue
        # Higher rotation suffix (.3.log, .2.log, .1.log) is older than .0.log; bare .log sorts newest (-1).
        rot_num = int(m.group(1)) if m.group(1) is not None else -1
        matched.append((-rot_num, full))
    matched.sort(key=lambda item: (item[0], os.path.basename(item[1]).lower()))
    return [p for _, p in matched]


def _resolve_channel_paths(
    path_or_paths: Optional[Union[str, Sequence[str]]],
    log_dir: Optional[str],
    channel_prefix: str,
) -> List[str]:
    if isinstance(path_or_paths, str):
        stripped = path_or_paths.strip()
        if not stripped:
            return discover_rotated_logs(log_dir, channel_prefix) if log_dir else []
        if os.path.isdir(stripped):
            return discover_rotated_logs(stripped, channel_prefix)
        return [stripped]
    if path_or_paths is not None:
        resolved: List[str] = []
        for item in path_or_paths:
            if not item:
                continue
            if os.path.isdir(item):
                resolved.extend(discover_rotated_logs(item, channel_prefix))
            else:
                resolved.append(item)
        return resolved
    if log_dir:
        return discover_rotated_logs(log_dir, channel_prefix)
    return []


def _read_channel_entries(
    path_or_paths: Optional[Union[str, Sequence[str]]],
    log_dir: Optional[str],
    channel_prefix: str,
) -> Tuple[List[Tuple[int, str]], int]:
    """Read one or more log files in chronological order, returning `(file_index_from_end, line)` pairs."""
    paths = [p for p in _resolve_channel_paths(path_or_paths, log_dir, channel_prefix) if os.path.isfile(p)]
    total_files = len(paths)
    entries: List[Tuple[int, str]] = []
    for pos, path in enumerate(paths):
        # Align sessions from the newest file backward (0 = newest `.0.log`, -1 = `.1.log`, etc.)
        rel_session = pos - (total_files - 1)
        with open(path, encoding="utf-8", errors="replace") as fp:
            for ln in fp:
                entries.append((rel_session, ln.rstrip("\r\n")))
    return entries, total_files


def _is_valid_cause(cause: Optional[str], allowed: Optional[frozenset[str]] = None) -> bool:
    if not cause:
        return False
    low = cause.lower()
    if low not in VALID_STAGE_CAUSES:
        return False
    if allowed is not None and low not in allowed:
        return False
    return True


def _hold_pass2_satisfies(
    hold_stopped: int,
    hold_total: int,
    hold1_stopped: int = 0,
    min_hold_pass2: Optional[int] = None,
) -> bool:
    """Evaluate `hold-off pass 2 stopped=X of N` dynamically against `N` from that same log line."""
    if hold_total <= 0:
        return False
    effective = min(hold_total, hold_stopped + max(0, hold1_stopped))
    if min_hold_pass2 is not None:
        return effective >= min_hold_pass2
    if hold_total < 5:
        return effective == hold_total
    return effective > 0 and (hold_total - effective) <= MAX_PROTECTED_UNSTOPPED_HOLD_QUESTS


def evaluate_beginning_logs(
    newgame_log_path: Optional[Union[str, Sequence[str]]] = None,
    mission_log_path: Optional[Union[str, Sequence[str]]] = None,
    min_hold_pass2: Optional[int] = None,
    progression_log_path: Optional[Union[str, Sequence[str]]] = None,
    log_dir: Optional[str] = None,
) -> Dict[str, object]:
    """Evaluate `fo4sf_newgame` and `fo4sf_mission` logs (single or rotated multi-session) into `B1`..`B8` verdicts."""
    ng_entries, ng_file_count = _read_channel_entries(newgame_log_path, log_dir, "fo4sf_newgame")
    ms_entries, ms_file_count = _read_channel_entries(mission_log_path, log_dir, "fo4sf_mission")
    pr_entries, pr_file_count = _read_channel_entries(progression_log_path, log_dir, "FO4SFProgression")
    ng_lines = [ln for _, ln in ng_entries]
    ms_lines = [ln for _, ln in ms_entries]
    pr_lines = [ln for _, ln in pr_entries]

    ng_stages: set[int] = set()
    ng_stage_idx: Dict[int, int] = {}
    ng_stage_causes: Dict[int, str] = {}
    ng_bad_stage_causes: Dict[int, str] = {}
    ng_stage200_pos: Optional[Tuple[int, float]] = None
    mode_choice: Optional[str] = None
    pod_ok: Optional[bool] = None
    hold1_stopped = 0
    hold_stopped: Optional[int] = None
    hold_total: Optional[int] = None
    hold2_still_running = False
    saw_stand_down = False
    saw_fade_timeout = False
    saw_start_place_fail = False

    pistol_picked_idx: Optional[int] = None
    pipboy_pickup_idx: Optional[int] = None
    cog_console_idx: Optional[int] = None
    saw_cog_open_fail = False
    saw_cog_direct = False
    saw_cog_fail = False

    saw_special_skipped = False
    saw_special_default = any(_SPECIAL_DEFAULT_RE.search(ln) for ln in pr_lines)
    special_sums: List[int] = []
    map_setup_idx: Optional[int] = None
    map_setup_markers: Optional[int] = None

    saw_ascent_play = False
    ascent_play_refused = False
    ascent_confirmed_idx: Optional[int] = None
    saw_exit_fallback_move = False
    lift_fail_reasons: List[Tuple[int, str]] = []
    surface_fail_reasons: List[str] = []
    fell_z_values: List[str] = []
    saw_landed_fallback = False
    saw_exit_anchor_fail = False
    saw_surface_moveto = False
    saw_surface_missed = False

    for idx, (rel_sess, ln) in enumerate(ng_entries):
        mstg = _NG_STAGE_RE.search(ln)
        if mstg:
            st_num = int(mstg.group(2))
            cause = (mstg.group(3) or "").lower()
            ng_stages.add(st_num)
            ng_stage_idx.setdefault(st_num, idx)
            ng_stage_causes[st_num] = cause or "missing"
            if st_num in (10, 20, 30, 40, 200) and not _is_valid_cause(cause):
                ng_bad_stage_causes[st_num] = cause or "missing"
            if st_num == 200 and mstg.group(1) is not None and ng_stage200_pos is None:
                ng_stage200_pos = (rel_sess, float(mstg.group(1)))

        mmc = _NG_MODE_CHOICE_RE.search(ln)
        if mmc:
            raw_m = mmc.group(1).lower()
            mode_choice = "story" if raw_m in ("story", "1") else "warfare"

        mp = _NG_POD_RE.search(ln)
        if mp:
            pod_ok = mp.group(1).lower() == "true"
        mh1 = _NG_HOLD1_RE.search(ln)
        if mh1:
            hold1_stopped = int(mh1.group(1))
        mh2 = _NG_HOLD2_RE.search(ln)
        if mh2:
            hold_stopped, hold_total = int(mh2.group(1)), int(mh2.group(2))
        if _NG_HOLD2_STILL_RUNNING_RE.search(ln):
            hold2_still_running = True
        if _NG_STAND_DOWN_RE.search(ln):
            saw_stand_down = True
        if _NG_FADE_TIMEOUT_RE.search(ln):
            saw_fade_timeout = True
        if _NG_START_PLACE_FAIL_RE.search(ln):
            saw_start_place_fail = True

        if _NG_PISTOL_PICKED_RE.search(ln) and pistol_picked_idx is None:
            pistol_picked_idx = idx
        if _NG_PIPBOY_EQUIPPED_RE.search(ln) and pipboy_pickup_idx is None:
            pipboy_pickup_idx = idx
        if _NG_COG_CONSOLE_RE.search(ln):
            cog_console_idx = idx
            saw_cog_open_fail = False
        if _NG_COG_OPEN_FAIL_RE.search(ln):
            saw_cog_open_fail = True
        if _NG_COG_DIRECT_RE.search(ln):
            saw_cog_direct = True
        if _NG_COG_FAIL_RE.search(ln):
            saw_cog_fail = True

        if _NG_SPECIAL_SKIPPED_RE.search(ln):
            saw_special_skipped = True
        if _SPECIAL_DEFAULT_RE.search(ln):
            saw_special_default = True
        ms7 = _NG_SPECIAL_SET_7_RE.search(ln)
        if ms7:
            special_sums.append(sum(int(ms7.group(g)) for g in range(1, 8)))
        else:
            mss = _NG_SPECIAL_SET_SUM_RE.search(ln)
            if mss:
                special_sums.append(int(mss.group(1)))

        mms = _NG_MAP_SETUP_RE.search(ln)
        if mms and map_setup_idx is None:
            map_setup_idx = idx
            map_setup_markers = int(mms.group(1)) if mms.group(1) is not None else 1

        mapl = _NG_ASCENT_PLAY_RE.search(ln)
        if mapl:
            if mapl.group(1).lower() == "true":
                saw_ascent_play = True
                ascent_play_refused = False
            else:
                ascent_play_refused = True
        if _NG_ASCENT_CONFIRMED_RE.search(ln):
            ascent_confirmed_idx = idx
        if _NG_EXIT_FALLBACK_MOVE_RE.search(ln):
            saw_exit_fallback_move = True
        mef = _NG_EXIT_FAIL_REASON_RE.search(ln)
        if mef:
            reason = mef.group(1)
            if reason.lower().startswith("lift_"):
                lift_fail_reasons.append((idx, reason))
            else:
                surface_fail_reasons.append(reason)
        mer = _NG_EXIT_RETRY_REASON_RE.search(ln)
        if mer:
            reason = mer.group(2)
            if reason.lower().startswith("lift_"):
                lift_fail_reasons.append((idx, reason))
            else:
                surface_fail_reasons.append(reason)
        mfell = _NG_FELL_RE.search(ln)
        if mfell:
            fell_z_values.append(mfell.group(1))
        if _NG_LANDED_FALLBACK_RE.search(ln):
            saw_landed_fallback = True
        if _NG_EXIT_ANCHOR_FAIL_RE.search(ln):
            saw_exit_anchor_fail = True
        if _NG_SURFACE_MOVETO_RE.search(ln):
            saw_surface_moveto = True
        if _NG_SURFACE_MISSED_RE.search(ln):
            saw_surface_missed = True

    ms_stages: List[int] = []
    ms_stage_causes: Dict[int, str] = {}
    ms_bad_stage_causes: Dict[int, str] = {}
    cods_bad_stage_causes: Dict[int, str] = {}
    sanct_bad_stage_causes: Dict[int, str] = {}
    first_ms_pos: Optional[Tuple[int, float]] = None
    mission_gate_ok: Optional[bool] = None
    min00_given_by: Optional[str] = None
    saw_codsworth_talk_end = False
    preston_talk_info: Optional[str] = None
    saw_preston_scene_incomplete = False
    saw_stage40_fallback = False
    saw_min01_stage10 = False
    saw_min01_bench_done = False
    raider_absent_clears = 0
    mission_reloads = 0

    raiders_init_zero = False
    reward_credits = 0
    saw_codsworth_active = False
    codsworth_move_fails = 0
    codsworth_failed = False
    mission_reloc_fails = 0
    preston_gave_up = False
    preston_dead = False
    preston_hostile = False
    follow_idx: Optional[int] = None
    follow_bad = False
    hold_after_follow = False

    for idx, (rel_sess, ln) in enumerate(ms_entries):
        if _SPECIAL_DEFAULT_RE.search(ln):
            saw_special_default = True
        mrt = _MS_RT_RE.search(ln)
        if mrt and first_ms_pos is None:
            first_ms_pos = (rel_sess, float(mrt.group(1)))

        mst = _MS_STAGE_RE.search(ln)
        if mst:
            st_val = int(mst.group(1))
            cause = (mst.group(2) or "").lower()
            if st_val not in ms_stages:
                ms_stages.append(st_val)
            ms_stage_causes[st_val] = cause or "missing"
            if st_val in (10, 20, 30, 35, 40, 200) and not _is_valid_cause(cause):
                ms_bad_stage_causes[st_val] = cause or "missing"
            if st_val == 35 and cause == "info":
                saw_preston_scene_incomplete = False

        mcst = _MS_CODS_STAGE_RE.search(ln)
        if mcst:
            cst_val = int(mcst.group(1))
            ccause = (mcst.group(2) or "").lower()
            if not _is_valid_cause(ccause):
                cods_bad_stage_causes[cst_val] = ccause or "missing"

        msst = _MS_SANCT_STAGE_RE.search(ln)
        if msst:
            sst_val = int(msst.group(1))
            scause = (msst.group(2) or "").lower()
            expected_sanct = frozenset({"bench"}) if sst_val == 100 else None
            if not _is_valid_cause(scause, expected_sanct):
                sanct_bad_stage_causes[sst_val] = scause or "missing"

        mgate = _MS_GATE_RE.search(ln)
        if mgate and mgate.group(3) is None:
            g_mode = int(mgate.group(1))
            g_started = mgate.group(2).lower() == "true"
            mission_gate_ok = g_mode == 1 and g_started

        mgiv = _MS_GIVEN_BY_RE.search(ln)
        if mgiv and min00_given_by is None:
            min00_given_by = mgiv.group(1).lower()

        if _MS_CODS_TALK_END_RE.search(ln):
            saw_codsworth_talk_end = True

        mpte = _MS_PRESTON_TALK_END_RE.search(ln)
        if mpte:
            preston_talk_info = mpte.group(1)

        mpse = _MS_PRESTON_SCENE_END_RE.search(ln)
        if mpse:
            end_st = int(mpse.group(1))
            end_info_str = (mpse.group(2) or "").lower()
            if end_info_str == "false" or (end_info_str == "" and end_st < 35 and 35 not in ms_stages):
                saw_preston_scene_incomplete = True

        if _MS_STAGE40_FALLBACK_RE.search(ln):
            saw_stage40_fallback = True

        if _MS_MIN01_STAGE10_RE.search(ln):
            saw_min01_stage10 = True
        if _MS_MIN01_BENCH_DONE_RE.search(ln):
            saw_min01_bench_done = True

        if _MS_RAIDER_ABSENT_RE.search(ln):
            raider_absent_clears += 1
        if _MS_RELOAD_RE.search(ln):
            mission_reloads += 1

        mir = _MS_INIT_RAIDERS_RE.search(ln)
        if mir and int(mir.group(1)) == 0:
            raiders_init_zero = True
        mrw = _MS_REWARD_RE.search(ln)
        if mrw:
            reward_credits = max(reward_credits, int(mrw.group(1)))

        mcm = _MS_CODS_MOVED_RE.search(ln)
        if mcm:
            if mcm.group(1).lower() == "false":
                saw_codsworth_active = True
            else:
                codsworth_move_fails += 1
                if codsworth_move_fails >= 10:
                    codsworth_failed = True

        if _MS_CODS_PLACE_RE.search(ln) and "failed=true" not in ln.lower():
            saw_codsworth_active = True

        mch = _MS_CODS_HOLD_RE.search(ln)
        if mch:
            off_val = float(mch.group(1))
            ok_val = mch.group(2).lower() == "true"
            if ok_val and 0.0 <= off_val <= 25.0:
                saw_codsworth_active = True
            elif not ok_val:
                codsworth_failed = True

        mcgu = _MS_CODS_GAVE_UP_RE.search(ln)
        if mcgu and int(mcgu.group(1)) >= 10:
            codsworth_failed = True

        mcss = _MS_CODS_SPOT_STATE_RE.search(ln)
        if mcss:
            if mcss.group(1).lower() == "true" or int(mcss.group(2)) >= 10:
                codsworth_failed = True

        if _MS_RELOC_MOVE_FAIL_RE.search(ln):
            mission_reloc_fails += 1

        mpgu = _MS_PRESTON_GAVE_UP_RE.search(ln)
        if mpgu and int(mpgu.group(1)) >= 10:
            preston_gave_up = True

        mpss = _MS_PRESTON_SPOT_STATE_RE.search(ln)
        if mpss:
            if mpss.group(1).lower() == "true":
                preston_dead = True
            if int(mpss.group(2)) >= 10:
                preston_gave_up = True

        if _MS_PRESTON_HOSTILE_RE.search(ln):
            preston_hostile = True

        if _MS_FOLLOW_REFUSED_RE.search(ln):
            follow_bad = True

        mfok = _MS_FOLLOW_OK_RE.search(ln)
        if mfok:
            filled = int(mfok.group(1))
            released = mfok.group(2).lower() == "true"
            if filled >= 1 and released:
                follow_idx = idx
            else:
                follow_bad = True
        elif follow_idx is not None and _MS_HOLD_PRESTON_RE.search(ln):
            hold_after_follow = True

    if codsworth_move_fails > 0 and not saw_codsworth_active:
        codsworth_failed = True

    verdicts: Dict[str, Dict[str, str]] = {}

    # B1: Story mode choice + pod walk-out + Starfield quest hold-off
    hold_ok = (
        hold_stopped is not None
        and hold_total is not None
        and not hold2_still_running
        and _hold_pass2_satisfies(hold_stopped, hold_total, hold1_stopped=hold1_stopped, min_hold_pass2=min_hold_pass2)
    )
    b1_bad_stage = {s: ng_bad_stage_causes[s] for s in (10, 20) if s in ng_bad_stage_causes}
    if not ng_lines:
        verdicts["B1_pod"] = {"status": "UNTESTED", "detail": "no fo4sf_newgame log supplied"}
    elif 1 in ng_stages or saw_stand_down:
        verdicts["B1_pod"] = {"status": "FAIL", "detail": "FO4SF_NewGameQuest stood down (stage 1 / no vault move)"}
    elif saw_fade_timeout:
        verdicts["B1_pod"] = {
            "status": "FAIL",
            "detail": "LoadingMenu close timed out before start choice ('mode fade lifted by=timeout')",
        }
    elif saw_start_place_fail:
        verdicts["B1_pod"] = {
            "status": "FAIL",
            "detail": "chosen Story start place failed to load and fell back ('start place move failed')",
        }
    elif b1_bad_stage:
        verdicts["B1_pod"] = {
            "status": "FAIL",
            "detail": f"invalid or missing stage cause in fo4sf_newgame: {b1_bad_stage}",
        }
    elif mode_choice == "warfare":
        verdicts["B1_pod"] = {"status": "FAIL", "detail": "mode choice picked warfare on Story beginning pilot"}
    elif mode_choice is None and any(s >= 20 for s in ng_stages):
        verdicts["B1_pod"] = {"status": "FAIL", "detail": "missing 'mode choice ... mode=story' before vault walk"}
    elif pod_ok is False:
        verdicts["B1_pod"] = {"status": "FAIL", "detail": "pod settle ok=false (snagged/dropped at pod)"}
    elif hold2_still_running:
        verdicts["B1_pod"] = {"status": "FAIL", "detail": "hold-off pass 2 left a stopped quest with running_after=true"}
    elif hold_stopped is not None and hold_total is not None and not hold_ok:
        verdicts["B1_pod"] = {
            "status": "FAIL",
            "detail": f"hold-off pass 2 stopped={hold_stopped}/{hold_total} failed dynamic threshold",
        }
    elif mode_choice == "story" and pod_ok is True and hold_ok and 10 in ng_stages and 20 in ng_stages:
        verdicts["B1_pod"] = {
            "status": "PASS",
            "detail": f"mode=story, pod settle ok=true, hold-off pass 2 stopped={hold_stopped}/{hold_total}",
        }
    elif mode_choice == "story" and pod_ok is True and hold_ok and not ng_stages:
        verdicts["B1_pod"] = {
            "status": "PASS",
            "detail": f"mode=story, pod settle ok=true, hold-off pass 2 stopped={hold_stopped}/{hold_total}",
        }
    else:
        verdicts["B1_pod"] = {
            "status": "IN_PROGRESS" if (10 in ng_stages or hold_ok or mode_choice == "story") else "UNTESTED",
            "detail": f"mode={mode_choice}, pod_ok={pod_ok}, hold_pass2={hold_stopped}/{hold_total}",
        }

    # B2: Vault pistol + Pip-Boy pickup + gear-door console activation -> stage 30 (by=vault_console)
    stage30_idx = ng_stage_idx.get(30)
    stage30_cause = ng_stage_causes.get(30)
    if not ng_lines:
        verdicts["B2_gear_door"] = {"status": "UNTESTED", "detail": "no fo4sf_newgame log supplied"}
    elif saw_cog_fail or saw_cog_open_fail:
        verdicts["B2_gear_door"] = {"status": "FAIL", "detail": "cog door reference failed or did not open on console press"}
    elif saw_cog_direct:
        verdicts["B2_gear_door"] = {"status": "FAIL", "detail": "cog door opened directly instead of console activation"}
    elif 30 in ng_stages and stage30_cause != "vault_console":
        verdicts["B2_gear_door"] = {
            "status": "FAIL",
            "detail": f"stage 30 requires by=vault_console (got by={stage30_cause})",
        }
    elif 30 in ng_stages and cog_console_idx is None:
        verdicts["B2_gear_door"] = {
            "status": "FAIL",
            "detail": "stage 30 reached without 'cog door console activated'",
        }
    elif cog_console_idx is not None and pipboy_pickup_idx is None:
        verdicts["B2_gear_door"] = {
            "status": "FAIL",
            "detail": "console activated without prior 'pipboy pickup equipped flag=1'",
        }
    elif cog_console_idx is not None and pipboy_pickup_idx is not None and pipboy_pickup_idx > cog_console_idx:
        verdicts["B2_gear_door"] = {
            "status": "FAIL",
            "detail": "'pipboy pickup equipped flag=1' appeared after 'cog door console activated'",
        }
    elif 30 in ng_stages and (pistol_picked_idx is None or (stage30_idx is not None and pistol_picked_idx > stage30_idx)):
        verdicts["B2_gear_door"] = {
            "status": "FAIL",
            "detail": "stage 30 reached without 'pistol picked' before the gear door",
        }
    elif (
        30 in ng_stages
        and stage30_cause == "vault_console"
        and pistol_picked_idx is not None
        and pipboy_pickup_idx is not None
        and cog_console_idx is not None
        and (stage30_idx is None or cog_console_idx <= stage30_idx)
    ):
        verdicts["B2_gear_door"] = {
            "status": "PASS",
            "detail": "pistol picked, Pip-Boy equipped (flag=1), and cog door console activated -> stage 30 by=vault_console",
        }
    elif pistol_picked_idx is not None or pipboy_pickup_idx is not None or cog_console_idx is not None:
        verdicts["B2_gear_door"] = {
            "status": "IN_PROGRESS",
            "detail": "vault items/console in progress; awaiting stage 30",
        }
    else:
        verdicts["B2_gear_door"] = {"status": "UNTESTED", "detail": "stage 30 not reached in log"}

    # B3: Exit lift (40-point S.P.E.C.I.A.L. on every allocator, never 'special skipped'/'special default'/'exit fallback by=move')
    later_lift_fails = [
        r for i, r in lift_fail_reasons if ascent_confirmed_idx is None or i >= ascent_confirmed_idx
    ]
    allowed_special_sums = {40}
    bad_special = [s for s in special_sums if s not in allowed_special_sums]
    matched_special = next((s for s in reversed(special_sums) if s in allowed_special_sums), None)
    has_valid_special = matched_special is not None
    map_ok = map_setup_idx is not None and (map_setup_markers is None or map_setup_markers > 0)
    if not ng_lines:
        verdicts["B3_exit_lift"] = {"status": "UNTESTED", "detail": "no fo4sf_newgame log supplied"}
    elif saw_exit_fallback_move:
        verdicts["B3_exit_lift"] = {"status": "FAIL", "detail": "'exit fallback by=move' used instead of lift ride"}
    elif saw_special_default:
        verdicts["B3_exit_lift"] = {"status": "FAIL", "detail": "'special default' standard spread fallback used"}
    elif saw_special_skipped:
        verdicts["B3_exit_lift"] = {"status": "FAIL", "detail": "'special skipped' logged on normal walk"}
    elif bad_special and not has_valid_special:
        verdicts["B3_exit_lift"] = {
            "status": "FAIL",
            "detail": f"S.P.E.C.I.A.L. sum {bad_special[-1]} != required 40 points",
        }
    elif later_lift_fails or ascent_play_refused:
        reasons = ", ".join(later_lift_fails) if later_lift_fails else "ascent play accepted=false"
        verdicts["B3_exit_lift"] = {"status": "FAIL", "detail": f"Vault 111 lift exit failed (reason={reasons})"}
    elif (ascent_confirmed_idx is not None or 40 in ng_stages) and not has_valid_special:
        verdicts["B3_exit_lift"] = {
            "status": "FAIL",
            "detail": "lift ascent completed without 'special set' confirmation",
        }
    elif (ascent_confirmed_idx is not None or 40 in ng_stages) and not map_ok:
        verdicts["B3_exit_lift"] = {
            "status": "FAIL",
            "detail": "lift ascent completed without 'map setup done' (markers > 0)",
        }
    elif ascent_confirmed_idx is not None and has_valid_special and map_ok:
        verdicts["B3_exit_lift"] = {
            "status": "PASS",
            "detail": f"special set (sum={matched_special}), map setup done (markers={map_setup_markers}), ascent carried confirmed",
        }
    elif saw_ascent_play or has_valid_special or map_ok:
        verdicts["B3_exit_lift"] = {
            "status": "IN_PROGRESS",
            "detail": "lift sequence started; awaiting special set, map setup done, and ascent carried confirmed",
        }
    else:
        verdicts["B3_exit_lift"] = {"status": "UNTESTED", "detail": "lift ascent not started in log"}

    # B4: Surface landing (FinishSurface stage 40 + CheckLanding stage 200 with valid causes)
    b4_bad_stage = {s: ng_bad_stage_causes[s] for s in (40, 200) if s in ng_bad_stage_causes}
    if not ng_lines:
        verdicts["B4_surface_landing"] = {"status": "UNTESTED", "detail": "no fo4sf_newgame log supplied"}
    elif saw_exit_fallback_move:
        verdicts["B4_surface_landing"] = {"status": "FAIL", "detail": "surface reached via 'exit fallback by=move'"}
    elif b4_bad_stage:
        verdicts["B4_surface_landing"] = {
            "status": "FAIL",
            "detail": f"invalid or missing stage cause on surface landing: {b4_bad_stage}",
        }
    elif surface_fail_reasons or saw_surface_missed or saw_exit_anchor_fail:
        reasons = ", ".join(surface_fail_reasons) or (
            "surface_missed" if saw_surface_missed else "exit_anchor_unresolved"
        )
        verdicts["B4_surface_landing"] = {"status": "FAIL", "detail": f"surface landing failed ({reasons})"}
    elif fell_z_values or saw_landed_fallback:
        verdicts["B4_surface_landing"] = {
            "status": "FAIL",
            "detail": f"surface landing fell onto fallback marker (fell_z={fell_z_values}, fallback={saw_landed_fallback})",
        }
    elif 40 in ng_stages and 200 in ng_stages:
        verdicts["B4_surface_landing"] = {
            "status": "PASS",
            "detail": "stages 40 -> 200 reached cleanly on Commonwealth hilltop (no exit failure or fallback)",
        }
    elif 40 in ng_stages or saw_surface_moveto:
        verdicts["B4_surface_landing"] = {
            "status": "IN_PROGRESS",
            "detail": "FinishSurface stage 40 / surface moveto reached; awaiting CheckLanding stage 200",
        }
    else:
        verdicts["B4_surface_landing"] = {"status": "UNTESTED", "detail": "stage 200 not reached in log"}

    # B5: Story gate + Codsworth Sanctuary keeper & MQ102-lite talk -> Min00 stage 10
    started_in_vault = False
    if first_ms_pos is not None and ng_stage200_pos is not None:
        ms_sess, first_ms_rt = first_ms_pos
        ng_sess, ng_stage200_rt = ng_stage200_pos
        if ms_sess < ng_sess or (ms_sess == ng_sess and first_ms_rt + 0.001 < ng_stage200_rt):
            started_in_vault = True
    if not ms_lines:
        verdicts["B5_codsworth_sanctuary"] = {"status": "UNTESTED", "detail": "no fo4sf_mission log supplied"}
    elif started_in_vault:
        verdicts["B5_codsworth_sanctuary"] = {
            "status": "FAIL",
            "detail": f"mission started in vault before NewGame stage 200 (mission={first_ms_pos} < stage200={ng_stage200_pos})",
        }
    elif cods_bad_stage_causes or (10 in ms_bad_stage_causes):
        verdicts["B5_codsworth_sanctuary"] = {
            "status": "FAIL",
            "detail": f"invalid or missing stage cause on Codsworth01/Min00 stage 10 (cods={cods_bad_stage_causes}, min00_10={ms_bad_stage_causes.get(10)})",
        }
    elif mission_gate_ok is False:
        verdicts["B5_codsworth_sanctuary"] = {
            "status": "FAIL",
            "detail": "mission gate blocked start (mission gate mode=2 started=false)",
        }
    elif codsworth_failed:
        verdicts["B5_codsworth_sanctuary"] = {
            "status": "FAIL",
            "detail": "Codsworth relocation/hold failed or keeper gave up",
        }
    elif any(s >= 20 for s in ms_stages) and (mission_gate_ok is not True or min00_given_by is None):
        verdicts["B5_codsworth_sanctuary"] = {
            "status": "FAIL",
            "detail": f"Concord fight started without Story gate or 'min00 given by=' (gate={mission_gate_ok}, given_by={min00_given_by})",
        }
    elif (
        mission_gate_ok is True
        and saw_codsworth_active
        and saw_codsworth_talk_end
        and min00_given_by in ("codsworth", "concord")
        and 10 in ms_stages
    ):
        verdicts["B5_codsworth_sanctuary"] = {
            "status": "PASS",
            "detail": f"mission gate mode=1, Codsworth held & talk ended -> min00 stage 10 (given by={min00_given_by})",
        }
    elif mission_gate_ok is True or saw_codsworth_active or saw_codsworth_talk_end:
        verdicts["B5_codsworth_sanctuary"] = {
            "status": "IN_PROGRESS",
            "detail": f"gate={mission_gate_ok}, codsworth_held={saw_codsworth_active}, talk_end={saw_codsworth_talk_end}, given_by={min00_given_by}",
        }
    else:
        verdicts["B5_codsworth_sanctuary"] = {
            "status": "UNTESTED",
            "detail": "no Story mission gate / Codsworth Sanctuary activity seen",
        }

    # B6: Concord street fight (stages 10 -> 20 -> 30 with valid causes)
    relocate_exhausted = mission_reloc_fails >= 10 or preston_gave_up
    b6_bad_stage = {s: ms_bad_stage_causes[s] for s in (10, 20, 30) if s in ms_bad_stage_causes}
    if not ms_lines:
        verdicts["B6_concord_raiders"] = {"status": "UNTESTED", "detail": "no fo4sf_mission log supplied"}
    elif b6_bad_stage:
        verdicts["B6_concord_raiders"] = {
            "status": "FAIL",
            "detail": f"invalid or missing stage cause in Concord encounter: {b6_bad_stage}",
        }
    elif raiders_init_zero:
        verdicts["B6_concord_raiders"] = {"status": "FAIL", "detail": "FO4SF_Min00 initialized with raiders=0"}
    elif preston_dead:
        verdicts["B6_concord_raiders"] = {"status": "FAIL", "detail": "Preston died during Concord encounter"}
    elif preston_hostile:
        verdicts["B6_concord_raiders"] = {
            "status": "FAIL",
            "detail": "Preston targeted the player during Concord fight",
        }
    elif relocate_exhausted:
        verdicts["B6_concord_raiders"] = {
            "status": "FAIL",
            "detail": f"Concord relocation exhausted failure budget (mission_move_fails={mission_reloc_fails}, keeper_gave_up={preston_gave_up})",
        }
    elif 10 in ms_stages and 20 in ms_stages and 30 in ms_stages:
        verdicts["B6_concord_raiders"] = {
            "status": "PASS",
            "detail": f"stages 10 -> 20 -> 30 completed (reloads={mission_reloads}, cleared={raider_absent_clears})",
        }
    elif 20 in ms_stages:
        verdicts["B6_concord_raiders"] = {
            "status": "IN_PROGRESS",
            "detail": "Concord fight in progress at stage 20 (stage 30 not reached yet)",
        }
    else:
        verdicts["B6_concord_raiders"] = {
            "status": "UNTESTED",
            "detail": f"Concord fight not started yet (stages seen={ms_stages})",
        }

    # B7: Preston DialogueMenu turn-in (requires stage 35 by=info -> 'preston talk end info=... -> stage 40' -> stage 40 by=info -> stage 200)
    b7_bad_stage = {s: ms_bad_stage_causes[s] for s in (35, 40, 200) if s in ms_bad_stage_causes}
    if not ms_lines:
        verdicts["B7_preston_turnin"] = {"status": "UNTESTED", "detail": "no fo4sf_mission log supplied"}
    elif saw_stage40_fallback or ms_stage_causes.get(40) == "fallback":
        verdicts["B7_preston_turnin"] = {
            "status": "FAIL",
            "detail": "'stage 40 by=fallback' triggered (DialogueMenu talk required for REACHABLE)",
        }
    elif b7_bad_stage:
        verdicts["B7_preston_turnin"] = {
            "status": "FAIL",
            "detail": f"invalid or missing stage cause on Preston turn-in: {b7_bad_stage}",
        }
    elif saw_preston_scene_incomplete and 35 not in ms_stages:
        verdicts["B7_preston_turnin"] = {
            "status": "FAIL",
            "detail": "Preston talk scene ended before final exchange (stage 35 not reached)",
        }
    elif (40 in ms_stages or 200 in ms_stages) and (
        35 not in ms_stages or ms_stage_causes.get(35) != "info" or ms_stage_causes.get(40) != "info"
    ):
        verdicts["B7_preston_turnin"] = {
            "status": "FAIL",
            "detail": f"stage 40/200 reached without stage 35 by=info -> stage 40 by=info (causes={ms_stage_causes})",
        }
    elif hold_after_follow:
        verdicts["B7_preston_turnin"] = {
            "status": "FAIL",
            "detail": "door hold re-applied after FO4SF_COMPreston follow armed",
        }
    elif follow_bad:
        verdicts["B7_preston_turnin"] = {
            "status": "FAIL",
            "detail": "FO4SF_COMPreston follow stand-in refused or failed alias/release check",
        }
    elif preston_dead or (preston_gave_up and (30 in ms_stages or 40 in ms_stages)):
        verdicts["B7_preston_turnin"] = {
            "status": "FAIL",
            "detail": "Preston dead or keeper gave up relocating Preston before/after turn-in",
        }
    elif (40 in ms_stages or 200 in ms_stages) and preston_talk_info is None:
        verdicts["B7_preston_turnin"] = {
            "status": "FAIL",
            "detail": "stage 40/200 reached without 'preston talk end info=<id> -> stage 40'",
        }
    elif 200 in ms_stages and (40 not in ms_stages or reward_credits < 100):
        verdicts["B7_preston_turnin"] = {
            "status": "FAIL",
            "detail": f"stage 200 reached without stage 40 / 100-credit reward (credits={reward_credits})",
        }
    elif (
        preston_talk_info is not None
        and 35 in ms_stages
        and 40 in ms_stages
        and 200 in ms_stages
        and ms_stage_causes.get(35) == "info"
        and ms_stage_causes.get(40) == "info"
        and reward_credits >= 100
    ):
        verdicts["B7_preston_turnin"] = {
            "status": "PASS",
            "detail": f"preston talk end info={preston_talk_info} -> stages 35 -> 40 (by=info) -> 200, reward={reward_credits} placeholder credits",
        }
    elif 30 in ms_stages or 35 in ms_stages or 40 in ms_stages:
        verdicts["B7_preston_turnin"] = {
            "status": "IN_PROGRESS",
            "detail": "stage 30 reached; awaiting Preston DialogueMenu turn-in completion (stage 35 -> 40 -> 200)",
        }
    else:
        verdicts["B7_preston_turnin"] = {"status": "UNTESTED", "detail": "Preston turn-in not reached yet"}

    # B8: Sanctuary workbench hand-over ('min01 bench activated -> stage 100' + valid sanctuary01 stage cause)
    if not ms_lines:
        verdicts["B8_sanctuary_bench"] = {"status": "UNTESTED", "detail": "no fo4sf_mission log supplied"}
    elif sanct_bad_stage_causes:
        verdicts["B8_sanctuary_bench"] = {
            "status": "FAIL",
            "detail": f"invalid or missing stage cause on Sanctuary01: {sanct_bad_stage_causes}",
        }
    elif saw_min01_bench_done:
        verdicts["B8_sanctuary_bench"] = {
            "status": "PASS",
            "detail": "min01 bench activated -> stage 100 (Sanctuary workbench 0250FE / 0x005C50 claimed)",
        }
    elif saw_min01_stage10 or 200 in ms_stages:
        verdicts["B8_sanctuary_bench"] = {
            "status": "IN_PROGRESS",
            "detail": "FO4SF_Sanctuary01 objective 10 started; awaiting 'min01 bench activated -> stage 100'",
        }
    else:
        verdicts["B8_sanctuary_bench"] = {
            "status": "UNTESTED",
            "detail": "Sanctuary workbench hand-over not started yet",
        }

    any_fail = any(v["status"] == "FAIL" for v in verdicts.values())
    all_pass = all(v["status"] == "PASS" for v in verdicts.values())
    return {
        "ok": not any_fail,
        "all_pass": all_pass,
        "files_read": {
            "newgame": ng_file_count,
            "mission": ms_file_count,
            "progression": pr_file_count,
        },
        "steps": verdicts,
    }
