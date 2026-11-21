"""Offline bundle readiness verifier and console-free log evaluator for the Fallout 4 beginning pilot.

Covers the seven beginning steps (`B1`..`B7`) documented in `docs/testing/fo4-beginning-pilot.md`:
  - `B1_pod`: Vault 111 cryo pod awakening, `-2.5 m` pod step-out, O2 dial clear, Starfield quest hold-off
  - `B2_gear_door`: Vault 111 gear door proximity/door open (`stage 30`) and catwalk bridge (`#803`)
  - `B3_exit_lift`: Floor-level elevator platform (`(-77.74, -3.96, -1.75)`) and `+21.6 m` ascent (`ascent carried confirmed`, `#803`)
  - `B4_surface_landing`: Commonwealth Vault 111 hilltop placement (`FinishSurface` `stage 40`) & landing check (`stage 200`)
  - `B5_codsworth_sanctuary`: Sanctuary Hills walk & `FO4SF_CodsworthKeeper` relocation/hold (`(-2346.71, -1406.16, 111.73)`)
  - `B6_concord_raiders`: Red Rocket road -> Concord street ambush (`FO4SF_Min00Quest` `stages 10 -> 20 -> 30`)
  - `B7_preston_turnin`: Preston Garvey console-free proximity/activate turn-in & placeholder `100`-Credit reward (`stages 30 -> 40 -> 200`)
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple


@dataclass(frozen=True)
class BeginningStepSpec:
    step_id: str
    title: str
    plugins: Tuple[str, ...]
    scripts: Tuple[str, ...]
    actor: str
    owner_pass: str
    owner_fail: str


BEGINNING_STEPS: Tuple[BeginningStepSpec, ...] = (
    BeginningStepSpec(
        step_id="B1_pod",
        title="Pod Walk-Out & Starfield Quest Hold-Off",
        plugins=("FO4SFNewGame.esm",),
        scripts=("FO4SF_NewGameQuest.pex", "FO4SF_NewGameLooks.pex"),
        actor="claude_pc_then_owner",
        owner_pass="Screen fades in at Vault 111 cryo pod; pressing W walks cleanly into the aisle; O2 dial is clear; zero Starfield quest popups.",
        owner_fail="Infinite New Game spinner, pod collision snag/rubber-band to COC marker, red O2 dial, or any Starfield quest banner.",
    ),
    BeginningStepSpec(
        step_id="B2_gear_door",
        title="Vault 111 Gear Door & Catwalk",
        plugins=("FO4SFVaultGearDoor.esm", "FO4SFNewGame.esm"),
        scripts=("FO4SF_NewGameQuest.pex",),
        actor="claude_pc_then_owner",
        owner_pass="Approaching the gear-door console (2.5 m radius) or activating the door rolls the vault plug aside, extends the catwalk, and opens doorway collision without popping the lift prompt.",
        owner_fail="Gear plug does not open, invisible doorway collision blocks entry onto catwalk, or lift prompt fires early at the console.",
    ),
    BeginningStepSpec(
        step_id="B3_exit_lift",
        title="Vault 111 Floor Platform & Lift Ascent",
        plugins=("FO4SFExitLift.esm", "FO4SFNewGame.esm"),
        scripts=("FO4SF_NewGameQuest.pex",),
        actor="claude_pc_then_owner",
        owner_pass="Elevator platform waits flush at floor level with open gates; stepping aboard offers Ride up; platform rises +21.6 m smoothly ('ascent carried confirmed') into exterior transition.",
        owner_fail="Platform starts high up shaft out of reach, gates block boarding, player clips through rising floor, or 'exit failed reason=lift_*' occurs.",
    ),
    BeginningStepSpec(
        step_id="B4_surface_landing",
        title="Commonwealth Hilltop Surface Landing",
        plugins=("FO4TerrainCore.esm", "FO4SFNewGame.esm"),
        scripts=("FO4SF_NewGameQuest.pex",),
        actor="claude_pc_then_owner",
        owner_pass="FinishSurface sets stage 40 on merged hilltop cell and CheckLanding reaches stage 200 on solid terrain without fallback placement or exit failure.",
        owner_fail="Player falls > 3 m ('fell z=') onto fallback marker, 'exit failed reason=' is logged, lands in non-core cell/void, or freezes on exterior cell transfer.",
    ),
    BeginningStepSpec(
        step_id="B5_codsworth_sanctuary",
        title="Sanctuary Hills & Codsworth Keeper",
        plugins=("FO4TerrainCore.esm", "FO4SFMission.esm"),
        scripts=("FO4SF_Min00Quest.pex",),
        actor="claude_pc_then_owner",
        owner_pass="Walking ~120 m east down into Sanctuary Hills relocates/holds Codsworth (MiniBotA placeholder with codsworth.nif skin) in front of the cul-de-sac house with voiced Hello greeting on E.",
        owner_fail="Codsworth missing/invisible, keeper relocation budget exhausted, drifted > 25 m off spot, missing mesh/purple material, or silent/crashing on E.",
    ),
    BeginningStepSpec(
        step_id="B6_concord_raiders",
        title="Red Rocket Approach & Concord Raider Fight",
        plugins=("FO4TerrainCore.esm", "FO4ActorRaider.esm", "FO4SFMission.esm"),
        scripts=("FO4SF_Min00Quest.pex",),
        actor="claude_pc_then_owner",
        owner_pass="Walking past Red Rocket into Concord relocates street raiders and Preston; approaching within 60 m starts 'kill the raiders' (stage 20); defeating all raiders advances to stage 30 with Preston friendly.",
        owner_fail="Crash approaching Concord/Museum, raider/Preston relocation fails >= 10 times, Preston dies or targets player, or objective stalls after raiders die.",
    ),
    BeginningStepSpec(
        step_id="B7_preston_turnin",
        title="Preston Garvey Turn-In & Placeholder 100-Credit Completion",
        plugins=("FO4SFMission.esm",),
        scripts=("FO4SF_Min00Quest.pex", "FO4SF_COMPreston.pex"),
        actor="claude_pc_then_owner",
        owner_pass="Standing within 3 m of Preston (calm-raider NPC placeholder) or pressing E at stage 30 awards 100 placeholder Starfield Credits (stage 40) and completes stage 200.",
        owner_fail="Approaching/pressing E on Preston at stage 30 fails to award 100 Credits, never reaches stage 200, or door hold overrides an armed follow test.",
    ),
)

CODSWORTH_NIF_REL = "meshes/fo4port/actors/codsworth/codsworth.nif"
CODSWORTH_VOICE_DIR_REL = "sound/voice/fo4sfmission.esm/robotminibota"
MIN_CODSWORTH_WEMS = 20
MAX_PROTECTED_UNSTOPPED_HOLD_QUESTS = 4


def _is_tes4_plugin(path: str) -> bool:
    try:
        with open(path, "rb") as fp:
            hdr = fp.read(24)
        return len(hdr) == 24 and hdr[:4] == b"TES4"
    except OSError:
        return False


def verify_bundle_beginning_readiness(bundle_dir: str) -> Dict[str, object]:
    """Check offline that `bundle_dir` contains every plugin, script, mesh, and voice asset for `B1`..`B7`."""
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
            "status": "PASS" if not step_issues else "FAIL",
            "issues": step_issues,
        }

    return {
        "ok": len(problems) == 0,
        "steps": step_results,
        "problems": problems,
    }


# ---------------------------------------------------------------------------
# Log Evaluator (`fo4sf_newgame.0.log` + `fo4sf_mission.0.log`)
# ---------------------------------------------------------------------------

_NG_STAGE_RE = re.compile(r"FO4SF_NEWGAME(?:\s+rt=[-\d.]+)?\s+stage\s+(\d+)\s*$", re.IGNORECASE)
_NG_HOLD1_RE = re.compile(r"hold-off pass 1 stopped=(\d+)\s+of\s+(\d+)", re.IGNORECASE)
_NG_HOLD2_RE = re.compile(r"hold-off pass 2 stopped=(\d+)\s+of\s+(\d+)", re.IGNORECASE)
_NG_HOLD2_STILL_RUNNING_RE = re.compile(r"\bheld off\b.*?\brunning_after=true\b.*?\bpass=2\b", re.IGNORECASE)
_NG_POD_RE = re.compile(r"\bpod settle ok=(true|false)\b", re.IGNORECASE)
_NG_STAND_DOWN_RE = re.compile(r"\b(?:no move into the vault:|not a new game:.*standing down)\b", re.IGNORECASE)
_NG_COG_FAIL_RE = re.compile(r"\bcog door\s+\S+\s+does not resolve\b", re.IGNORECASE)
_NG_ASCENT_PLAY_RE = re.compile(r"\bascent play accepted=(true|false)\b", re.IGNORECASE)
_NG_ASCENT_CONFIRMED_RE = re.compile(r"\bascent carried confirmed\b", re.IGNORECASE)
_NG_EXIT_FAIL_REASON_RE = re.compile(r"\bexit failed reason=([A-Za-z0-9_]+)", re.IGNORECASE)
_NG_FELL_RE = re.compile(r"\bfell z=([-\d.]+):\s*fallback pos=", re.IGNORECASE)
_NG_LANDED_FALLBACK_RE = re.compile(r"\blanded z=[-\d.]+.*?\bfallback=true\b", re.IGNORECASE)
_NG_EXIT_ANCHOR_FAIL_RE = re.compile(r"\bexit anchor\s+\S+\s+does not resolve\b", re.IGNORECASE)
_NG_SURFACE_MOVETO_RE = re.compile(r"\bsurface moveto\b", re.IGNORECASE)
_NG_SURFACE_MISSED_RE = re.compile(r"\bsurface missed:\s*still inside\b", re.IGNORECASE)

_MS_STAGE_RE = re.compile(r"FO4SF_MISSION\s+rt=[-\d.]+\s+stage\s+(\d+)\s*$", re.IGNORECASE)
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


def _read_lines(path: Optional[str]) -> List[str]:
    if not path or not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as fp:
        return [ln.rstrip("\r\n") for ln in fp]


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
    newgame_log_path: Optional[str] = None,
    mission_log_path: Optional[str] = None,
    min_hold_pass2: Optional[int] = None,
) -> Dict[str, object]:
    """Evaluate `fo4sf_newgame.0.log` and `fo4sf_mission.0.log` into `PASS` / `FAIL` / `IN_PROGRESS` / `UNTESTED`."""
    ng_lines = _read_lines(newgame_log_path)
    ms_lines = _read_lines(mission_log_path)

    ng_stages: set[int] = set()
    pod_ok: Optional[bool] = None
    hold1_stopped = 0
    hold_stopped: Optional[int] = None
    hold_total: Optional[int] = None
    hold2_still_running = False
    saw_stand_down = False
    saw_cog_fail = False
    saw_ascent_play = False
    ascent_play_refused = False
    ascent_confirmed_idx: Optional[int] = None
    lift_fail_reasons: List[Tuple[int, str]] = []
    surface_fail_reasons: List[str] = []
    fell_z_values: List[str] = []
    saw_landed_fallback = False
    saw_exit_anchor_fail = False
    saw_surface_moveto = False
    saw_surface_missed = False

    for idx, ln in enumerate(ng_lines):
        mstg = _NG_STAGE_RE.search(ln)
        if mstg:
            ng_stages.add(int(mstg.group(1)))
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
        if _NG_COG_FAIL_RE.search(ln):
            saw_cog_fail = True
        mapl = _NG_ASCENT_PLAY_RE.search(ln)
        if mapl:
            if mapl.group(1).lower() == "true":
                saw_ascent_play = True
            else:
                ascent_play_refused = True
        if _NG_ASCENT_CONFIRMED_RE.search(ln):
            ascent_confirmed_idx = idx
        mef = _NG_EXIT_FAIL_REASON_RE.search(ln)
        if mef:
            reason = mef.group(1)
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

    for idx, ln in enumerate(ms_lines):
        mst = _MS_STAGE_RE.search(ln)
        if mst:
            st_val = int(mst.group(1))
            if st_val not in ms_stages:
                ms_stages.append(st_val)
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

    # B1: Pod walk-out & dynamic hold-off check
    hold_ok = (
        hold_stopped is not None
        and hold_total is not None
        and not hold2_still_running
        and _hold_pass2_satisfies(hold_stopped, hold_total, hold1_stopped=hold1_stopped, min_hold_pass2=min_hold_pass2)
    )
    if not ng_lines:
        verdicts["B1_pod"] = {"status": "UNTESTED", "detail": "no fo4sf_newgame log supplied"}
    elif 1 in ng_stages or saw_stand_down:
        verdicts["B1_pod"] = {"status": "FAIL", "detail": "FO4SF_NewGameQuest stood down (stage 1 / no vault move)"}
    elif pod_ok is False:
        verdicts["B1_pod"] = {"status": "FAIL", "detail": "pod settle ok=false (snagged/dropped at pod)"}
    elif hold2_still_running:
        verdicts["B1_pod"] = {"status": "FAIL", "detail": "hold-off pass 2 left a stopped quest with running_after=true"}
    elif hold_stopped is not None and hold_total is not None and not hold_ok:
        verdicts["B1_pod"] = {
            "status": "FAIL",
            "detail": f"hold-off pass 2 stopped={hold_stopped}/{hold_total} failed dynamic threshold",
        }
    elif pod_ok is True and hold_ok:
        verdicts["B1_pod"] = {
            "status": "PASS",
            "detail": f"pod settle ok=true, hold-off pass 2 stopped={hold_stopped}/{hold_total}",
        }
    else:
        verdicts["B1_pod"] = {
            "status": "IN_PROGRESS" if (10 in ng_stages or hold_ok) else "UNTESTED",
            "detail": f"pod_ok={pod_ok}, hold_pass2={hold_stopped}/{hold_total}",
        }

    # B2: Gear door (stage 30 without missing cog door)
    if not ng_lines:
        verdicts["B2_gear_door"] = {"status": "UNTESTED", "detail": "no fo4sf_newgame log supplied"}
    elif saw_cog_fail:
        verdicts["B2_gear_door"] = {"status": "FAIL", "detail": "cog door reference did not resolve"}
    elif 30 in ng_stages:
        verdicts["B2_gear_door"] = {"status": "PASS", "detail": "stage 30 reached (Vault 111 gear door opened)"}
    else:
        verdicts["B2_gear_door"] = {"status": "UNTESTED", "detail": "stage 30 not reached in log"}

    # B3: Exit lift ('ascent carried confirmed' with zero later/any 'exit failed reason=lift_*'; NOT stage 40!)
    later_lift_fails = [
        r for i, r in lift_fail_reasons if ascent_confirmed_idx is None or i >= ascent_confirmed_idx
    ]
    if not ng_lines:
        verdicts["B3_exit_lift"] = {"status": "UNTESTED", "detail": "no fo4sf_newgame log supplied"}
    elif lift_fail_reasons or ascent_play_refused:
        reason_list = later_lift_fails or [r for _, r in lift_fail_reasons]
        reasons = ", ".join(reason_list) if reason_list else "ascent play accepted=false"
        verdicts["B3_exit_lift"] = {"status": "FAIL", "detail": f"Vault 111 lift exit failed (reason={reasons})"}
    elif ascent_confirmed_idx is not None:
        verdicts["B3_exit_lift"] = {
            "status": "PASS",
            "detail": "ascent carried confirmed (Vault 111 lift ride completed without lift_ failure)",
        }
    elif saw_ascent_play:
        verdicts["B3_exit_lift"] = {
            "status": "IN_PROGRESS",
            "detail": "lift Play01 started; awaiting ascent carried confirmed",
        }
    else:
        verdicts["B3_exit_lift"] = {
            "status": "UNTESTED",
            "detail": "ascent carried confirmed not seen in log (stage 40 is FinishSurface placement, not lift completion)",
        }

    # B4: Surface landing (FinishSurface stage 40 -> CheckLanding stage 200 without exit failure or fallback)
    has_surface_or_fallback_fail = bool(
        surface_fail_reasons
        or fell_z_values
        or saw_landed_fallback
        or saw_exit_anchor_fail
        or (saw_surface_missed and 200 not in ng_stages)
        or (lift_fail_reasons and (saw_surface_moveto or 40 in ng_stages or 200 in ng_stages))
    )
    if not ng_lines:
        verdicts["B4_surface_landing"] = {"status": "UNTESTED", "detail": "no fo4sf_newgame log supplied"}
    elif has_surface_or_fallback_fail:
        parts: List[str] = []
        if surface_fail_reasons:
            parts.append("exit failed reason=" + ",".join(surface_fail_reasons))
        if lift_fail_reasons and (saw_surface_moveto or 40 in ng_stages or 200 in ng_stages):
            parts.append("exit failed reason=" + ",".join(r for _, r in lift_fail_reasons))
        if fell_z_values:
            parts.append("fell z=" + ",".join(fell_z_values) + " (fallback placement)")
        elif saw_landed_fallback:
            parts.append("landed fallback=true")
        if saw_exit_anchor_fail:
            parts.append("exit anchor did not resolve")
        if saw_surface_missed and 200 not in ng_stages:
            parts.append("surface missed still inside")
        verdicts["B4_surface_landing"] = {
            "status": "FAIL",
            "detail": "; ".join(parts),
        }
    elif 200 in ng_stages:
        verdicts["B4_surface_landing"] = {
            "status": "PASS",
            "detail": "stage 200 reached cleanly on Commonwealth hilltop (no exit failure or fallback)",
        }
    elif 40 in ng_stages or saw_surface_moveto:
        verdicts["B4_surface_landing"] = {
            "status": "IN_PROGRESS",
            "detail": "FinishSurface stage 40 / surface moveto reached; awaiting CheckLanding stage 200",
        }
    else:
        verdicts["B4_surface_landing"] = {"status": "UNTESTED", "detail": "stage 200 not reached in log"}

    # B5: Sanctuary & Codsworth (must NEVER pass on quest-init 'keeper load codsworth')
    if not ms_lines:
        verdicts["B5_codsworth_sanctuary"] = {"status": "UNTESTED", "detail": "no fo4sf_mission log supplied"}
    elif codsworth_failed:
        verdicts["B5_codsworth_sanctuary"] = {
            "status": "FAIL",
            "detail": "Codsworth relocation/hold failed or keeper gave up",
        }
    elif saw_codsworth_active:
        verdicts["B5_codsworth_sanctuary"] = {
            "status": "PASS",
            "detail": "Codsworth relocated/held near Sanctuary spot without failures",
        }
    else:
        verdicts["B5_codsworth_sanctuary"] = {
            "status": "UNTESTED",
            "detail": "no proximity 'moved Codsworth' / 'hold Codsworth' line seen (init 'keeper load' ignored)",
        }

    # B6: Concord street fight (stages 10 -> 20 -> 30; stage 20 without 30 is IN_PROGRESS unless failure logged)
    relocate_exhausted = mission_reloc_fails >= 10 or preston_gave_up
    if not ms_lines:
        verdicts["B6_concord_raiders"] = {"status": "UNTESTED", "detail": "no fo4sf_mission log supplied"}
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
    elif 20 in ms_stages and 30 in ms_stages:
        verdicts["B6_concord_raiders"] = {"status": "PASS", "detail": "When Freedom Calls stages 10 -> 20 -> 30 completed"}
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

    # B7: Preston turn-in & reward (stage 30 without 200 is IN_PROGRESS unless failure logged)
    if not ms_lines:
        verdicts["B7_preston_turnin"] = {"status": "UNTESTED", "detail": "no fo4sf_mission log supplied"}
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
    elif 200 in ms_stages and (40 not in ms_stages or reward_credits < 100):
        verdicts["B7_preston_turnin"] = {
            "status": "FAIL",
            "detail": f"stage 200 reached without stage 40 / 100-credit reward (credits={reward_credits})",
        }
    elif 40 in ms_stages and 200 in ms_stages and reward_credits >= 100:
        extra = " + follow armed" if follow_idx is not None else " (door-held; console-free follow is Card B-Card-2)"
        verdicts["B7_preston_turnin"] = {
            "status": "PASS",
            "detail": f"stages 40 -> 200 reached, reward={reward_credits} placeholder credits{extra}",
        }
    elif 30 in ms_stages or 40 in ms_stages:
        verdicts["B7_preston_turnin"] = {
            "status": "IN_PROGRESS",
            "detail": "stage 30 reached; awaiting Preston turn-in completion (stage 200)",
        }
    else:
        verdicts["B7_preston_turnin"] = {"status": "UNTESTED", "detail": "Preston turn-in not reached yet"}

    any_fail = any(v["status"] == "FAIL" for v in verdicts.values())
    all_pass = all(v["status"] == "PASS" for v in verdicts.values())
    return {
        "ok": not any_fail,
        "all_pass": all_pass,
        "steps": verdicts,
    }
