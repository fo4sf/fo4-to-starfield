"""Offline bundle readiness verifier and console-free log evaluator for the Fallout 4 beginning pilot.

Covers the seven playable-beginning steps (`B1`..`B7`) documented in `docs/testing/fo4-beginning-pilot.md`:
  - `B1_pod`: Vault 111 cryo pod awakening, `-2.5 m` pod step-out, O2 dial clear, Starfield quest hold-off
  - `B2_gear_door`: Vault 111 gear door console/door activation (`stage 30`) and catwalk bridge
  - `B3_exit_lift`: Floor-level elevator platform (`(-77.74, -3.96, -1.75)`) and `+21.6 m` ascent (`stage 40`)
  - `B4_surface_landing`: Commonwealth Vault 111 hilltop arrival (`(-2467.78, -1406.92, 128.11)`, `stage 200`)
  - `B5_codsworth_sanctuary`: Sanctuary Hills walk & `FO4SF_CodsworthKeeper` mesh/voice hold (`(-2346.71, -1406.16, 111.73)`)
  - `B6_concord_raiders`: Red Rocket road -> Concord street ambush (`FO4SF_Min00Quest` `stages 10 -> 20 -> 30`)
  - `B7_preston_turnin`: Preston Garvey console-free turn-in & reward (`stages 30 -> 40 -> 200`, `100` Credits)
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


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
        owner_pass="Pressing E at the gear door console rolls the vault plug aside, extends the catwalk, and opens doorway collision without popping the lift prompt.",
        owner_fail="Gear plug does not open, invisible doorway collision blocks entry onto catwalk, or lift prompt fires early at the console.",
    ),
    BeginningStepSpec(
        step_id="B3_exit_lift",
        title="Vault 111 Floor Platform & Lift Ascent",
        plugins=("FO4SFExitLift.esm", "FO4SFNewGame.esm"),
        scripts=("FO4SF_NewGameQuest.pex",),
        actor="claude_pc_then_owner",
        owner_pass="Elevator platform waits flush at floor level with open gates; stepping aboard offers Ride up; gates close and lift rises smoothly outdoors.",
        owner_fail="Platform starts high up shaft out of reach, gates block boarding, player clips through rising floor, or ride fails to exit Vault 111.",
    ),
    BeginningStepSpec(
        step_id="B4_surface_landing",
        title="Commonwealth Hilltop Surface Landing",
        plugins=("FO4TerrainCore.esm", "FO4SFNewGame.esm"),
        scripts=("FO4SF_NewGameQuest.pex",),
        actor="claude_pc_then_owner",
        owner_pass="Player lands on solid Vault 111 hilltop terrain overlooking Sanctuary Hills with 'When Freedom Calls: find the Last Minutemen' displayed.",
        owner_fail="Player falls > 3 m through terrain onto fallback marker, lands in void/water, or freezes on exterior cell transfer.",
    ),
    BeginningStepSpec(
        step_id="B5_codsworth_sanctuary",
        title="Sanctuary Hills & Codsworth Keeper",
        plugins=("FO4TerrainCore.esm", "FO4SFMission.esm"),
        scripts=("FO4SF_Min00Quest.pex",),
        actor="claude_pc_then_owner",
        owner_pass="Walking ~120 m east down into Sanctuary Hills shows Codsworth hovering in front of the cul-de-sac house with intact Mister Handy model and voiced greeting on E.",
        owner_fail="Codsworth missing/invisible, drifted > 25 m off spot, missing mesh/purple material, or silent/crashing on E.",
    ),
    BeginningStepSpec(
        step_id="B6_concord_raiders",
        title="Red Rocket Approach & Concord Raider Fight",
        plugins=("FO4TerrainCore.esm", "FO4ActorRaider.esm", "FO4SFMission.esm"),
        scripts=("FO4SF_Min00Quest.pex",),
        actor="claude_pc_then_owner",
        owner_pass="Walking past Red Rocket into Concord spawns street raiders and Preston; approaching within 60 m starts 'kill the raiders'; defeating all raiders advances to 'talk to Preston Garvey' with Preston friendly.",
        owner_fail="Crash approaching Concord/Museum, raiders missing or underground, Preston turns hostile on stray shots, or objective stays stuck at stage 20 after last raider dies.",
    ),
    BeginningStepSpec(
        step_id="B7_preston_turnin",
        title="Preston Garvey Turn-In & 100-Credit Completion",
        plugins=("FO4SFMission.esm",),
        scripts=("FO4SF_Min00Quest.pex", "FO4SF_COMPreston.pex"),
        actor="claude_pc_then_owner",
        owner_pass="Standing within 3 m of Preston or pressing E after the fight awards 100 Credits and displays 'When Freedom Calls: complete' while Preston remains calm at the Museum entrance.",
        owner_fail="Pressing E or standing within 3 m of Preston at stage 30 fails to award 100 Credits or never reaches 'When Freedom Calls: complete'.",
    ),
)

CODSWORTH_NIF_REL = "meshes/fo4port/actors/codsworth/codsworth.nif"
CODSWORTH_VOICE_DIR_REL = "sound/voice/fo4sfmission.esm/robotminibota"
MIN_CODSWORTH_WEMS = 20


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

_NG_STAGE_RE = re.compile(r"\bstage\s+(\d+)\b", re.IGNORECASE)
_NG_HOLD2_RE = re.compile(r"hold-off pass 2 stopped=(\d+)\s+of\s+(\d+)", re.IGNORECASE)
_NG_POD_RE = re.compile(r"pod settle ok=(true|false)", re.IGNORECASE)
_NG_EXIT_FAIL_RE = re.compile(r"\b(exit failure|landed on fallback|fall drop)\b", re.IGNORECASE)

_MS_STAGE_RE = re.compile(r"FO4SF_MISSION\s+rt=[-\d.]+\s+stage\s+(\d+)\b")
_MS_REWARD_RE = re.compile(r"FO4SF_MISSION\s+rt=[-\d.]+\s+reward\s+credits=(\d+)")
_MS_CODS_RE = re.compile(
    r"FO4SF_MISSION\s+rt=[-\d.]+\s+(?:codsworth|place codsworth|hold codsworth|keeper load.*codsworth)",
    re.IGNORECASE,
)
_MS_CODS_FAIL_RE = re.compile(r"codsworth.*fails=([1-9]\d*)", re.IGNORECASE)
_MS_RELOC_FAIL_RE = re.compile(r"relocateFails=([1-9]\d*)", re.IGNORECASE)
_MS_FOLLOW_RE = re.compile(r"follow preston test-only.*filled=1.*linked=player.*released=True", re.IGNORECASE)
_MS_HOLD_PRESTON_RE = re.compile(r"FO4SF_MISSION\s+rt=[-\d.]+\s+hold preston\b", re.IGNORECASE)


def _read_lines(path: Optional[str]) -> List[str]:
    if not path or not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as fp:
        return [ln.rstrip("\r\n") for ln in fp]


def evaluate_beginning_logs(
    newgame_log_path: Optional[str] = None,
    mission_log_path: Optional[str] = None,
    min_hold_pass2: int = 162,
) -> Dict[str, object]:
    """Evaluate `fo4sf_newgame.0.log` and `fo4sf_mission.0.log` into per-step `PASS` / `FAIL` / `UNTESTED` verdicts."""
    ng_lines = _read_lines(newgame_log_path)
    ms_lines = _read_lines(mission_log_path)

    ng_stages: set[int] = set()
    pod_ok: Optional[bool] = None
    hold_stopped: Optional[int] = None
    hold_total: Optional[int] = None
    saw_exit_fail = False

    for ln in ng_lines:
        for m in _NG_STAGE_RE.finditer(ln):
            ng_stages.add(int(m.group(1)))
        mp = _NG_POD_RE.search(ln)
        if mp:
            pod_ok = mp.group(1).lower() == "true"
        mh = _NG_HOLD2_RE.search(ln)
        if mh:
            hold_stopped, hold_total = int(mh.group(1)), int(mh.group(2))
        if _NG_EXIT_FAIL_RE.search(ln):
            saw_exit_fail = True

    ms_stages: List[int] = []
    reward_credits = 0
    saw_codsworth_active = False
    codsworth_failed = False
    relocate_exhausted = False
    follow_idx: Optional[int] = None
    hold_after_follow = False

    for idx, ln in enumerate(ms_lines):
        mst = _MS_STAGE_RE.search(ln)
        if mst:
            st_val = int(mst.group(1))
            if st_val not in ms_stages:
                ms_stages.append(st_val)
        mrw = _MS_REWARD_RE.search(ln)
        if mrw:
            reward_credits = max(reward_credits, int(mrw.group(1)))
        if _MS_CODS_RE.search(ln) or "codsworthState=held" in ln or "hold codsworth" in ln.lower() or "place codsworth" in ln.lower():
            saw_codsworth_active = True
        mcf = _MS_CODS_FAIL_RE.search(ln)
        if mcf and int(mcf.group(1)) >= 10:
            codsworth_failed = True
        mrf = _MS_RELOC_FAIL_RE.search(ln)
        if mrf and int(mrf.group(1)) >= 10:
            relocate_exhausted = True
        if _MS_FOLLOW_RE.search(ln):
            follow_idx = idx
        elif follow_idx is not None and _MS_HOLD_PRESTON_RE.search(ln):
            hold_after_follow = True

    verdicts: Dict[str, Dict[str, str]] = {}

    # B1: Pod walk-out & hold-off
    if not ng_lines:
        verdicts["B1_pod"] = {"status": "UNTESTED", "detail": "no fo4sf_newgame log supplied"}
    elif 1 in ng_stages:
        verdicts["B1_pod"] = {"status": "FAIL", "detail": "FO4SF_NewGameQuest stood down at stage 1"}
    elif pod_ok is False:
        verdicts["B1_pod"] = {"status": "FAIL", "detail": "pod settle ok=false (snagged/dropped at pod)"}
    elif pod_ok is True and (hold_stopped is not None and hold_stopped >= min_hold_pass2):
        verdicts["B1_pod"] = {
            "status": "PASS",
            "detail": f"pod settle ok=true, hold-off pass 2 stopped={hold_stopped}/{hold_total}",
        }
    else:
        verdicts["B1_pod"] = {
            "status": "FAIL" if (hold_stopped is not None and hold_stopped < min_hold_pass2) else "UNTESTED",
            "detail": f"pod_ok={pod_ok}, hold_pass2={hold_stopped}/{hold_total}",
        }

    # B2: Gear door (stage 30)
    if 30 in ng_stages:
        verdicts["B2_gear_door"] = {"status": "PASS", "detail": "stage 30 reached (Vault 111 gear door opened)"}
    else:
        verdicts["B2_gear_door"] = {"status": "UNTESTED", "detail": "stage 30 not reached in log"}

    # B3: Exit lift (stage 40)
    if 40 in ng_stages:
        verdicts["B3_exit_lift"] = {"status": "PASS", "detail": "stage 40 reached (Vault 111 lift ride completed)"}
    else:
        verdicts["B3_exit_lift"] = {"status": "UNTESTED", "detail": "stage 40 not reached in log"}

    # B4: Surface landing (stage 200 without fallback failure)
    if saw_exit_fail:
        verdicts["B4_surface_landing"] = {"status": "FAIL", "detail": "surface landing fell onto fallback or logged exit failure"}
    elif 200 in ng_stages:
        verdicts["B4_surface_landing"] = {"status": "PASS", "detail": "stage 200 reached cleanly on Commonwealth hilltop"}
    else:
        verdicts["B4_surface_landing"] = {"status": "UNTESTED", "detail": "stage 200 not reached in log"}

    # B5: Sanctuary & Codsworth
    if not ms_lines:
        verdicts["B5_codsworth_sanctuary"] = {"status": "UNTESTED", "detail": "no fo4sf_mission log supplied"}
    elif codsworth_failed:
        verdicts["B5_codsworth_sanctuary"] = {"status": "FAIL", "detail": "Codsworth relocation/hold exhausted failure budget"}
    elif saw_codsworth_active:
        verdicts["B5_codsworth_sanctuary"] = {"status": "PASS", "detail": "Codsworth placed/held in Sanctuary without failures"}
    else:
        verdicts["B5_codsworth_sanctuary"] = {"status": "UNTESTED", "detail": "player has not walked within 300 m of Codsworth spot"}

    # B6: Concord street fight (stages 10 -> 20 -> 30)
    if not ms_lines:
        verdicts["B6_concord_raiders"] = {"status": "UNTESTED", "detail": "no fo4sf_mission log supplied"}
    elif relocate_exhausted:
        verdicts["B6_concord_raiders"] = {"status": "FAIL", "detail": "Concord raider/Preston relocation exhausted failure budget"}
    elif all(s in ms_stages for s in (10, 20, 30)):
        verdicts["B6_concord_raiders"] = {"status": "PASS", "detail": "When Freedom Calls stages 10 -> 20 -> 30 completed"}
    elif 20 in ms_stages and 30 not in ms_stages:
        verdicts["B6_concord_raiders"] = {"status": "FAIL", "detail": "fight started (stage 20) but never reached stage 30"}
    else:
        verdicts["B6_concord_raiders"] = {"status": "UNTESTED", "detail": f"mission stages seen={ms_stages}"}

    # B7: Preston turn-in & reward (stages 40 -> 200 + reward credits=100; plus optional follow check)
    if not ms_lines:
        verdicts["B7_preston_turnin"] = {"status": "UNTESTED", "detail": "no fo4sf_mission log supplied"}
    elif hold_after_follow:
        verdicts["B7_preston_turnin"] = {"status": "FAIL", "detail": "door hold re-applied after FO4SF_COMPreston follow armed"}
    elif 40 in ms_stages and 200 in ms_stages and reward_credits >= 100:
        extra = " + follow armed" if follow_idx is not None else " (door-held; console-free follow is Card B-Card-2)"
        verdicts["B7_preston_turnin"] = {
            "status": "PASS",
            "detail": f"stages 40 -> 200 reached, reward={reward_credits} credits{extra}",
        }
    elif 30 in ms_stages and 200 not in ms_stages:
        verdicts["B7_preston_turnin"] = {"status": "FAIL", "detail": "stage 30 reached but turn-in/reward never completed stage 200"}
    else:
        verdicts["B7_preston_turnin"] = {"status": "UNTESTED", "detail": "Preston turn-in not reached yet"}

    any_fail = any(v["status"] == "FAIL" for v in verdicts.values())
    all_pass = all(v["status"] == "PASS" for v in verdicts.values())
    return {
        "ok": not any_fail,
        "all_pass": all_pass,
        "steps": verdicts,
    }
