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

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union


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
        owner_pass="Lift offers S.P.E.C.I.A.L. and Character before Continue; S.P.E.C.I.A.L. confirms 40 points; map setup finishes during +21.6 m ascent ('ascent carried confirmed').",
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
CODSWORTH_VOICE_DIR_REL = "sound/voice/fo4sfmission.esm/fo4sf_codsworthvoice"
MIN_CODSWORTH_WEMS = 25
MAX_PROTECTED_UNSTOPPED_HOLD_QUESTS = 4

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


def _is_tes4_plugin(path: str) -> bool:
    try:
        with open(path, "rb") as fp:
            hdr = fp.read(24)
        return len(hdr) == 24 and hdr[:4] == b"TES4"
    except OSError:
        return False


def verify_bundle_beginning_readiness(bundle_dir: str) -> Dict[str, object]:
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
        for p in spec.plugins:
            p_full = os.path.join(b_abs, p)
            if not _is_tes4_plugin(p_full):
                step_issues.append(f"missing or invalid TES4 plugin: {p}")
            elif active_plugins and p.casefold() not in active_plugins:
                step_issues.append(f"plugin {p} missing from bundle_plan.json plugins list")

        for sc in spec.scripts:
            sc_full = os.path.join(b_abs, "Data", "Scripts", sc)
            if not os.path.isfile(sc_full) or os.path.getsize(sc_full) < 16:
                step_issues.append(f"missing compiled Papyrus script: Data/Scripts/{sc}")

        if spec.step_id == "B2_gear_door" and isinstance(components, Mapping) and components:
            cog = components.get("cog_door")
            if not isinstance(cog, Mapping) or len(cog.get("outputs") or {}) < 2:
                step_issues.append("bundle_plan.json missing cog_door mesh/material outputs")

        if spec.step_id == "B3_exit_lift" and isinstance(components, Mapping) and components:
            lift = components.get("exit_lift")
            if not isinstance(lift, Mapping) or len(lift.get("outputs") or {}) < 2:
                step_issues.append("bundle_plan.json missing exit_lift mesh/material outputs")

        if spec.step_id == "B5_codsworth_sanctuary":
            nif_full = os.path.join(b_abs, "Data", *CODSWORTH_NIF_REL.split("/"))
            if not os.path.isfile(nif_full):
                step_issues.append(f"missing Codsworth NIF: Data/{CODSWORTH_NIF_REL}")
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

    return {
        "ok": len(problems) == 0,
        "steps": step_results,
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

    # B3: Exit lift (40-point S.P.E.C.I.A.L., never 'special skipped'/'special default'/'exit fallback by=move')
    later_lift_fails = [
        r for i, r in lift_fail_reasons if ascent_confirmed_idx is None or i >= ascent_confirmed_idx
    ]
    bad_special = [s for s in special_sums if s != 40]
    has_special_40 = 40 in special_sums
    map_ok = map_setup_idx is not None and (map_setup_markers is None or map_setup_markers > 0)
    if not ng_lines:
        verdicts["B3_exit_lift"] = {"status": "UNTESTED", "detail": "no fo4sf_newgame log supplied"}
    elif saw_exit_fallback_move:
        verdicts["B3_exit_lift"] = {"status": "FAIL", "detail": "'exit fallback by=move' used instead of lift ride"}
    elif saw_special_default:
        verdicts["B3_exit_lift"] = {"status": "FAIL", "detail": "'special default' standard spread fallback used"}
    elif saw_special_skipped:
        verdicts["B3_exit_lift"] = {"status": "FAIL", "detail": "'special skipped' logged on normal walk"}
    elif bad_special and not has_special_40:
        verdicts["B3_exit_lift"] = {
            "status": "FAIL",
            "detail": f"S.P.E.C.I.A.L. sum {bad_special[-1]} != required 40 points",
        }
    elif later_lift_fails or ascent_play_refused:
        reasons = ", ".join(later_lift_fails) if later_lift_fails else "ascent play accepted=false"
        verdicts["B3_exit_lift"] = {"status": "FAIL", "detail": f"Vault 111 lift exit failed (reason={reasons})"}
    elif (ascent_confirmed_idx is not None or 40 in ng_stages) and not has_special_40:
        verdicts["B3_exit_lift"] = {
            "status": "FAIL",
            "detail": "lift ascent completed without 40-point 'special set' confirmation",
        }
    elif (ascent_confirmed_idx is not None or 40 in ng_stages) and not map_ok:
        verdicts["B3_exit_lift"] = {
            "status": "FAIL",
            "detail": "lift ascent completed without 'map setup done' (markers > 0)",
        }
    elif ascent_confirmed_idx is not None and has_special_40 and map_ok:
        verdicts["B3_exit_lift"] = {
            "status": "PASS",
            "detail": f"special set (sum=40), map setup done (markers={map_setup_markers}), ascent carried confirmed",
        }
    elif saw_ascent_play or has_special_40 or map_ok:
        verdicts["B3_exit_lift"] = {
            "status": "IN_PROGRESS",
            "detail": "lift sequence started; awaiting special=40, map setup done, and ascent carried confirmed",
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
