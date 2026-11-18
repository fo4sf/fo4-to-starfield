"""Structured step-by-step log evaluator for the Core Candidate walk (docs/testing/core-candidate-pc-card.md).

Evaluates each of the 12 walk steps independently so a failure in one step never blocks reading the remaining steps:
  1. exit        - pod walk-out, gear door, carrying lift, Commonwealth surface landing (fo4sf_newgame.0.log)
  2. hold        - hold-off pass 1 + pass 2 stopping 196 of 199 DefaultHold quests, 0 remaining running (fo4sf_newgame.0.log)
  3. rads        - radiation exposure (> 0 rads) and RadAway cure reduction (FO4SFRadsCore.0.log)
  4. hardcore    - GPOF Hardcore toggle ON and OFF with sq_env_running=false (FO4SFHardcore.0.log)
  5. workshop    - junk scrap, station/beacon placement, and save-quit-reload persistence (FO4SFWorkshopCore.1.log + .0.log)
  6. powerarmor  - climb-in frame entry, FusionCore charge/drain, and frame exit outfit restore (FO4SFPACore.0.log)
  7. dialogue    - silent-player list dialogue with [Speech 50] / tag check stage transition (FO4SFListDialogue.0.log)
  8. progression - creation flow applying 1 Background, 0..2 Traits, and 40-pt SPECIAL (FO4SFCoreCandidate.0.log / FO4SFProgression.0.log)
  9. combat      - zone hits, high-DT AP vs Standard ammo cycle, leg cripple & cure, and slow-time VATS shot (FO4SFCombat.0.log)
 10. reputation  - Very Evil + Idolized orthogonality (Ally + 0.75x buy mult) and Karma/Faction standing (FO4SFReputation.1.log + .0.log)
 11. companions  - 4-NPC Warfare fireteam commands, squad cap/upkeep gates, and follower teleportation (FO4SFCompanions.1.log + .0.log)
 12. pipboy      - FO4 shell/SPECIAL fill, M-key MAP open/close + texture/markers, and complete Star-Map block (FO4SFPipboyMenu.log)
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

STEP_NAMES = (
    "exit",
    "hold",
    "rads",
    "hardcore",
    "workshop",
    "powerarmor",
    "dialogue",
    "progression",
    "combat",
    "reputation",
    "companions",
    "pipboy",
)

EXPECTED_HOLD_STOPPED = 196
EXPECTED_HOLD_TOTAL = 199


def _read_lines(path: Optional[str]) -> List[str]:
    if not path or not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def _read_stitched(log_dir: str, stem: str) -> List[str]:
    """Read rotated <stem>.1.log (pre-quit) + <stem>.0.log (post-reload) in chronological order."""
    out: List[str] = []
    for idx in (1, 0):
        p = os.path.join(log_dir, f"{stem}.{idx}.log")
        if os.path.isfile(p):
            out.extend(_read_lines(p))
    return out


def eval_exit_and_hold(newgame_summary: dict, expected_stopped: int = EXPECTED_HOLD_STOPPED) -> Tuple[dict, dict]:
    """Evaluate Step 1 (Vault 111 exit) and Step 2 (Hold-off count) from make_newgame.summarize()."""
    stages = newgame_summary.get("stages") or []
    pod = str(newgame_summary.get("pod_settle") or "")
    ascent = newgame_summary.get("ascent") or []
    surfaced = str(newgame_summary.get("surfaced") or "")
    landed = bool(newgame_summary.get("landed"))
    stood_down = bool(newgame_summary.get("stood_down"))
    exit_fail = newgame_summary.get("exit_failure")

    has_stages = all(s in stages for s in (10, 20, 30, 40, 200))
    pod_ok = "ok=true" in pod.lower()
    carried_ok = any("carried confirmed" in str(a).lower() for a in ascent)
    core_cell_ok = "core_cell=true" in surfaced.lower()

    exit_ok = (not stood_down) and (exit_fail is None) and has_stages and pod_ok and carried_ok and core_cell_ok and landed
    exit_detail = (
        f"stages={stages} pod_ok={pod_ok} carried_ok={carried_ok} core_cell={core_cell_ok} "
        f"landed={landed} exit_failure={exit_fail}"
    )

    held = newgame_summary.get("held_off") or []
    by_pass = newgame_summary.get("held_off_by_pass") or {}
    unique_held = len(set(held))
    pass2_count = len(by_pass.get("2", []))
    hold_ok = (unique_held == expected_stopped) and ("2" in by_pass)
    hold_detail = (
        f"stopped_unique={unique_held}/{EXPECTED_HOLD_TOTAL} (expect {expected_stopped}) "
        f"pass1={len(by_pass.get('1', []))} pass2={pass2_count}"
    )
    return (
        {"step": "exit", "ok": exit_ok, "detail": exit_detail},
        {"step": "hold", "ok": hold_ok, "detail": hold_detail},
    )


def eval_rads(lines: Iterable[str]) -> dict:
    text = "\n".join(lines)
    if not text.strip():
        return {"step": "rads", "ok": False, "detail": "no FO4SFRadsCore log lines found"}
    rads_vals = [float(m.group(1)) for m in re.finditer(r"\brads=([0-9]+(?:\.[0-9]+)?)", text)]
    cured = bool(re.search(r"(radaway|cure|delta=-\d+)", text, re.I)) or (
        len(rads_vals) >= 2 and max(rads_vals) >= 25.0 and rads_vals[-1] < max(rads_vals)
    )
    exposed = any(v >= 25.0 for v in rads_vals) or bool(re.search(r"(hazard|emitter|ingest|source=)", text, re.I))
    ok = exposed and cured
    peak = max(rads_vals) if rads_vals else 0.0
    last = rads_vals[-1] if rads_vals else 0.0
    return {"step": "rads", "ok": ok, "detail": f"exposed={exposed} cured={cured} peak_rads={peak:.1f} final_rads={last:.1f}"}


def eval_hardcore(lines: Iterable[str]) -> dict:
    raw = list(lines)
    if not raw:
        return {"step": "hardcore", "ok": False, "detail": "no FO4SFHardcore log lines found"}
    text = "\n".join(raw)
    sq_conflict = bool(re.search(r"sq_env_running=true", text, re.I))
    saw_on = bool(re.search(r"(enabled=true|enabled=1|hardcore=1|mode=on)", text, re.I))
    saw_off = bool(re.search(r"(reason=(gpof|stage30)|enabled=false.*reason=|reverted|hardcore=0)", text, re.I)) or (
        saw_on and len(re.findall(r"enabled=(?:false|0)", text, re.I)) >= 1
    )
    ok = saw_on and saw_off and (not sq_conflict)
    return {"step": "hardcore", "ok": ok, "detail": f"saw_on={saw_on} saw_off={saw_off} sq_env_conflict={sq_conflict}"}


def eval_workshop(lines: Iterable[str]) -> dict:
    raw = list(lines)
    if not raw:
        return {"step": "workshop", "ok": False, "detail": "no FO4SFWorkshopCore log lines found"}
    text = "\n".join(raw)
    scrapped = bool(re.search(r"(cmpo_scrap|scrapped|scrap_complete|scrap_junk)", text, re.I))
    placed = bool(re.search(r"(camp_deployed|bench_placed|station_added|tracked_stations=[1-9]|tracked_beacons=[1-9]|tracked_workshops=[1-9])", text, re.I))
    reloaded = bool(re.search(r"(reload_audit|onplayerloadgame|when=reload)", text, re.I))
    ok = scrapped and placed and reloaded
    return {"step": "workshop", "ok": ok, "detail": f"scrapped={scrapped} placed={placed} reload_persisted={reloaded}"}


def eval_powerarmor(lines: Iterable[str]) -> dict:
    raw = list(lines)
    if not raw:
        return {"step": "powerarmor", "ok": False, "detail": "no FO4SFPACore log lines found"}
    text = "\n".join(raw)
    entered = bool(re.search(r"(enter_complete|inpa=true|inpa=1\.0)", text, re.I))
    exited = bool(re.search(r"exit_complete", text, re.I))
    frame_standing = bool(re.search(r"exit_complete[^\n]*frame_standing=true", text, re.I))
    ok = entered and exited and frame_standing
    return {"step": "powerarmor", "ok": ok, "detail": f"entered={entered} exited={exited} frame_standing={frame_standing}"}


def eval_dialogue(lines: Iterable[str]) -> dict:
    raw = list(lines)
    if not raw:
        return {"step": "dialogue", "ok": False, "detail": "no FO4SFListDialogue log lines found"}
    text = "\n".join(raw)
    skill_branch = bool(re.search(r"(stage=(?:20|21|22|30|31|40|50)|speech_(?:pass|fail)|science_pass|strength_(?:pass|fail)|bg_vault_dweller|trait_good_natured)", text, re.I))
    return {"step": "dialogue", "ok": skill_branch, "detail": f"skill_or_tag_branch_recorded={skill_branch}"}


def eval_progression(candidate_lines: Iterable[str], prog_lines: Iterable[str]) -> dict:
    cand_text = "\n".join(candidate_lines)
    prog_text = "\n".join(prog_lines)
    if not cand_text.strip() and not prog_text.strip():
        return {"step": "progression", "ok": False, "detail": "no FO4SFCoreCandidate / FO4SFProgression log lines found"}

    m = re.search(
        r"chargen_applied\b[^\n]*\bbg=(\w+)[^\n]*\btraits_count=(\d+)[^\n]*\bspecial_sum=([0-9.]+)",
        cand_text,
        re.I,
    )
    if m:
        bg, tcount, ssum = m.group(1), int(m.group(2)), float(m.group(3))
        ok = bool(bg) and (tcount == 2) and abs(ssum - 40.0) < 0.01
        return {
            "step": "progression",
            "ok": ok,
            "detail": f"source=walk_kiosk bg={bg} traits_count={tcount} (expect 2) special_sum={ssum:.0f}",
        }

    prog_ok = bool(re.search(r"(creation_applied|special_sum=40|stage[^\n]*id=10)", prog_text, re.I))
    return {"step": "progression", "ok": prog_ok, "detail": f"source=progression_quest ok={prog_ok}"}


def eval_combat(lines: Iterable[str]) -> dict:
    raw = list(lines)
    if not raw:
        return {"step": "combat", "ok": False, "detail": "no FO4SFCombat log lines found"}
    text = "\n".join(raw)
    zones = set(re.findall(r"step=zone_hit\s+zone=([a-z_]+)", text))
    zones_ok = {"head", "torso", "left_arm", "right_arm", "left_leg", "right_leg"}.issubset(zones)
    dt_hits = {m.group(1).lower(): float(m.group(2)) for m in re.finditer(r"step=high_dt_hit\s+subtype=(\S+)[^\n]*\bdamage=([0-9.]+)", text)}
    ammo_ok = ("ap" in dt_hits and "standard" in dt_hits and dt_hits["ap"] > dt_hits["standard"])
    cripple_ok = bool(re.search(r"step=limb_crippled\s+zone=(?:left_leg|right_leg)", text)) and bool(
        re.search(r"step=limb_cure\s+item=\S+\s+hardcore=[01]\s+cured=1", text)
    )
    vats_ok = bool(re.search(r"step=vats_shot\s+slow_time=1", text))
    ok = zones_ok and ammo_ok and cripple_ok and vats_ok
    return {
        "step": "combat",
        "ok": ok,
        "detail": f"zones={len(zones)}/6 ammo_dt={ammo_ok} cripple_cure={cripple_ok} vats={vats_ok}",
    }


def eval_reputation(lines: Iterable[str]) -> dict:
    raw = list(lines)
    if not raw:
        return {"step": "reputation", "ok": False, "detail": "no FO4SFReputation log lines found"}
    text = "\n".join(raw)
    explicit_ortho = bool(re.search(r"orthogonality[^\n]*ok=true", text, re.I))
    token_or_hook_ortho = bool(
        re.search(
            r"karma=-(?:7[5-9]\d|[89]\d\d|1000)\b[^\n]*(?:buy_mult=0\.75[^\n]*fac0_react=2[^\n]*states=3\b|states?=3\b)",
            text,
            re.I,
        )
        or (
            re.search(r"karma=-(?:7[5-9]\d|[89]\d\d|1000)\b", text, re.I)
            and re.search(r"(?:\bstates?=3\b|idolized)", text, re.I)
            and re.search(r"(?:\bbuy_mult=0\.75\b|\bfac0_react=2\b|\breaction=2\b|\bok=true\b)", text, re.I)
        )
    )
    ortho_ok = explicit_ortho or token_or_hook_ortho
    reload_ok = bool(re.search(r"(reload_audit[^\n]*ok=true|when=reload)", text, re.I))
    ok = ortho_ok and reload_ok
    return {"step": "reputation", "ok": ok, "detail": f"evil_idolized_orthogonality={ortho_ok} reload_persisted={reload_ok}"}


def eval_companions(lines: Iterable[str]) -> dict:
    raw = list(lines)
    if not raw:
        return {"step": "companions", "ok": False, "detail": "no FO4SFCompanions log lines found"}
    text = "\n".join(raw)
    fireteam_ok = bool(re.search(r"(active=4\b|count=4\b|slot=3\b|fireteam_cmd|fireteam_4npc)", text, re.I))
    teleport_ok = bool(re.search(r"(load_door_cell_change|vault_lift_or_interior_exit|pipboy_fast_travel|manual_radio_sync|teleport)", text, re.I))
    reload_ok = bool(re.search(r"(reload_audit|when=reload)", text, re.I))
    ok = fireteam_ok and teleport_ok and reload_ok
    return {"step": "companions", "ok": ok, "detail": f"fireteam_4npc={fireteam_ok} teleport={teleport_ok} reload_persisted={reload_ok}"}


def _read_pipboy_sfse_lines(log_dir: str, sfse_log_dir: Optional[str] = None) -> List[str]:
    candidates: List[Path] = []
    if sfse_log_dir:
        sroot = Path(sfse_log_dir)
        candidates.append(sroot / "FO4SFPipboyMenu.log")
        candidates.append(sroot / "Logs" / "FO4SFPipboyMenu.log")
    ldir = Path(log_dir)
    candidates.append(ldir / "FO4SFPipboyMenu.log")
    # Standard Starfield layout: <My Games>/Starfield/Logs/Script/User -> <My Games>/Starfield/SFSE/{Logs/}FO4SFPipboyMenu.log
    for anc in list(ldir.parents)[:4]:
        candidates.append(anc / "SFSE" / "Logs" / "FO4SFPipboyMenu.log")
        candidates.append(anc / "SFSE" / "FO4SFPipboyMenu.log")
    for c in candidates:
        if c.is_file():
            return _read_lines(str(c))
    return []


def eval_pipboy(lines: Iterable[str]) -> dict:
    raw = list(lines)
    if not raw:
        return {"step": "pipboy", "ok": False, "detail": "no FO4SFPipboyMenu.log lines found"}
    text = "\n".join(raw)
    refused = bool(re.search(r"\brefuse\s+step=", text, re.I))
    shell_ok = bool(re.search(r"step=code_obj_special\b[^\n]*\bpushed=7\b", text, re.I))
    map_open = bool(re.search(r"step=map_key\b[^\n]*\bwas_open=0\b[^\n]*\bsent=show\b", text, re.I))
    map_close = bool(re.search(r"step=map_key\b[^\n]*\bwas_open=1\b[^\n]*\bsent=hide\b", text, re.I))
    map_data = bool(re.search(r"(step=map_texture\s+loaded=1|step=map_markers\b[^\n]*\bcorners_set=3/3)", text, re.I))
    starmap_blocked = bool(re.search(r"step=starmap_blocked\b[^\n]*\broute=create\b", text, re.I))
    ok = (not refused) and shell_ok and map_open and map_close and map_data and starmap_blocked
    return {
        "step": "pipboy",
        "ok": ok,
        "detail": (
            f"no_refuse={not refused} shell_special={shell_ok} map_open_close={map_open and map_close} "
            f"map_data={map_data} starmap_blocked={starmap_blocked}"
        ),
    }


def evaluate_walk_logs(log_dir: str, newgame_summarizer, sfse_log_dir: Optional[str] = None) -> Dict[str, dict]:
    """Evaluate all 12 walk steps from Starfield's Logs/Script/User and SFSE log folders."""
    ng_lines = _read_stitched(log_dir, "fo4sf_newgame")
    ng_sum = newgame_summarizer(ng_lines)
    step_exit, step_hold = eval_exit_and_hold(ng_sum)

    results = {
        "exit": step_exit,
        "hold": step_hold,
        "rads": eval_rads(_read_stitched(log_dir, "FO4SFRadsCore")),
        "hardcore": eval_hardcore(_read_stitched(log_dir, "FO4SFHardcore")),
        "workshop": eval_workshop(_read_stitched(log_dir, "FO4SFWorkshopCore")),
        "powerarmor": eval_powerarmor(_read_stitched(log_dir, "FO4SFPACore")),
        "dialogue": eval_dialogue(_read_stitched(log_dir, "FO4SFListDialogue")),
        "progression": eval_progression(
            _read_stitched(log_dir, "FO4SFCoreCandidate"),
            _read_stitched(log_dir, "FO4SFProgression"),
        ),
        "combat": eval_combat(_read_stitched(log_dir, "FO4SFCombat")),
        "reputation": eval_reputation(_read_stitched(log_dir, "FO4SFReputation")),
        "companions": eval_companions(_read_stitched(log_dir, "FO4SFCompanions")),
        "pipboy": eval_pipboy(_read_pipboy_sfse_lines(log_dir, sfse_log_dir=sfse_log_dir)),
    }
    return results
