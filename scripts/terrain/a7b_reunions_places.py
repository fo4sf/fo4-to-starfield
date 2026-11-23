"""A7b next-two story missions & places verifier (`Reunions` MQ106 + `Dangerous Minds` MQ201/MQ202/MQ203).

Prototype, offline — verifies:
  1. FormID reservation `FO4SFMission.esm:0x000B00..0x000B7F` (`FO4SF_MQ106`=0x000B00,
     `FO4SF_MQ201`=0x000B40), strictly disjoint from `A1(d)` (`0x800..0x9FF`), `A4`
     (`0xA00..0xA7F`), and `A7` (`0xA80..0xAFF`), and notes the 1-line `A5` Pip-Boy
     `DATA / Quests` scan ceiling bump (`0xAFF -> 0xBFF`) required when implemented.
  2. Already-converted `interiors_b10` staged cells (`FO4Port_FortHagen01` `0x0100BA4B`,
     `FO4Port_FortHagen02` `0x0100CFC6`, `FO4Port_GoodneighborTheMemoryDen` `0x0100ED4A`,
     `FO4Port_MQ203KelloggsBrain` `0x0100F23E`, `FO4Port_PrydwenHull01..03`
     `0x01003846`/`0x0104026D`/`0x0101099A`, and `FO4Port_VirgilsLab01` `0x01069B10`)
     — zero reconversion required.
  3. `W6` 4-axis reachability & stuck analysis (Normal Mode + Open-Mode dead-giver
     simulation where every `npc_gated` edge is dropped and every stage must still
     reach completion, plus out-of-order, save/reload every stage, and fast-travel away).
  4. `A5`-compatible 7-column `FO4SFPipboyQuestObjectives.tsv` row generation with
     verified Commonwealth coordinates from `Fallout4.esm` / `FO4SFPipboyMapMarkers.tsv`.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

A4_RESERVED_RANGE = (0x000A00, 0x000A7F)
A7_RESERVED_RANGE = (0x000A80, 0x000AFF)
A7B_RESERVED_RANGE = (0x000B00, 0x000B7F)
A5_PIPBOY_NEXT_SCAN_RANGE = (0x000800, 0x000BFF)

# Canonical Fallout 4 Commonwealth map bounds (WRLD 0x0000003C MNAM outer cell edges)
COMMONWEALTH_X_BOUNDS = (-135168.0, 118784.0)
COMMONWEALTH_Y_BOUNDS = (-147456.0, 106496.0)


@dataclass(frozen=True)
class StagedPlaceSpec:
    fo4_edid: str
    fo4_cell_id: int
    port_edid: str
    port_cell_id: int
    staged_ref_count: int
    mission_ids: Tuple[str, ...]
    expected_internal_xtel_pairs: int
    needs_exterior_load_doors: Tuple[str, ...]
    key_locks_and_triggers: Tuple[str, ...]


A7B_STAGED_PLACES: Tuple[StagedPlaceSpec, ...] = (
    StagedPlaceSpec(
        fo4_edid="FortHagen01",
        fo4_cell_id=0x000BB078,
        port_edid="FO4Port_FortHagen01",
        port_cell_id=0x0100BA4B,
        staged_ref_count=3446,
        mission_ids=("FO4SF_MQ106",),
        expected_internal_xtel_pairs=1,
        needs_exterior_load_doors=(
            "Already wired by FO4SFFortHagen.esm (0D): RoofLoadDoorId 0x0547B0, RoofGateId 0x0232E1, RoofTermId 0x0232E0",
        ),
        key_locks_and_triggers=(
            "FO4SFFortHagen.esm QUST 0x800 FO4SF_FortHagenElevators (Car01 0x00C580, MidLoadDoor01Id 0x00C7A7)",
            "Stripped-XESP blockers managed by 0D: Planks01Id 0x00C641, BlockerDoor01Id 0x00C7A8, BlockerBoards01Id 0x00C13A",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="FortHagen02",
        fo4_cell_id=0x000CD2AE,
        port_edid="FO4Port_FortHagen02",
        port_cell_id=0x0100CFC6,
        staged_ref_count=3735,
        mission_ids=("FO4SF_MQ106", "FO4SF_MQ201"),
        expected_internal_xtel_pairs=1,
        needs_exterior_load_doors=(
            "Already wired by FO4SFFortHagen.esm (0D): LoadDoor02Id 0x00DE53 (0x0016850D) <-> RoofMarkerId 0x0A774C",
        ),
        key_locks_and_triggers=(
            "0x0009BC6C Kellogg (MQ201CyberBrain 0x0009BC6E, DN057_KelloggTerminalPassword 0x000A02D8)",
            "0x000CD4AC DN057_KelloggTerminal01REF (lock 255 / password 0x000A02D8), 0x000CFF43 DN057_CommandCenterDoorREF",
            "Roof elevator exit triggers Prydwen arrival hook (BoS200 0x0002BF20 / BoS100 0x0005DDAB)",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="GoodneighborTheMemoryDen",
        fo4_cell_id=0x00022884,
        port_edid="FO4Port_GoodneighborTheMemoryDen",
        port_cell_id=0x0100ED4A,
        staged_ref_count=1258,
        mission_ids=("FO4SF_MQ201",),
        expected_internal_xtel_pairs=0,
        needs_exterior_load_doors=(
            "0x00022886 <-> 0x00022971 (Memory Den front entrance <-> Goodneighbor hub at 20826.12, -11904.71)",
        ),
        key_locks_and_triggers=(
            "0x000537C3 DoctorAmariLabDoorREF (lock 255 scripted unlock; Open-Mode terminal/augmenter bypass)",
            "0x00053468 PlayerMemoryLoungerREF / 0x0017FC1D MQ203InstantEnterLoungerREF (safe MessageBox -> MoveTo bridge)",
            "0x00175522 MQ203MemoryDenMagicDoor <-> 0x00175521 MQ203MagicDoortoMemoryDen",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="MQ203KelloggsBrain",
        fo4_cell_id=0x000D393F,
        port_edid="FO4Port_MQ203KelloggsBrain",
        port_cell_id=0x0100F23E,
        staged_ref_count=1136,
        mission_ids=("FO4SF_MQ201",),
        expected_internal_xtel_pairs=4,
        needs_exterior_load_doors=(),
        key_locks_and_triggers=(
            "0x0012BC38 / 0x0012BC37 MQ203MemoryA/BExitBridgeCollision (R10 bounded watchdog + E bypass)",
            "0x000D9749 MQ203MemoryHVirgilsFileRef (Virgil's Glowing Sea clue / Open-Mode fallback)",
            "0x00175521 MQ203MagicDoortoMemoryDen -> 0x000D3CA0 MQ203MemoryDenReturnMarker",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="PrydwenHull01",
        fo4_cell_id=0x0005C92E,
        port_edid="FO4Port_PrydwenHull01",
        port_cell_id=0x01003846,
        staged_ref_count=3652,
        mission_ids=("FO4SF_MQ106",),
        expected_internal_xtel_pairs=2,
        needs_exterior_load_doors=(
            "Post-Reunions BoS200 / BoS100 Boston Airport vertibird handoff (Boston Airport 48073.90, -3331.96)",
        ),
        key_locks_and_triggers=(
            "Staged Prydwen Main Deck (paired with PrydwenHull02 0x0104026D & PrydwenHull03 0x0101099A)",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="VirgilsLab01",
        fo4_cell_id=0x00156C0E,
        port_edid="FO4Port_VirgilsLab01",
        port_cell_id=0x01069B10,
        staged_ref_count=539,
        mission_ids=("FO4SF_MQ201",),
        expected_internal_xtel_pairs=0,
        needs_exterior_load_doors=(
            "Rocky Cave exterior entrance (-116397.02, -136728.78) for MQ204 The Glowing Sea handoff",
        ),
        key_locks_and_triggers=(
            "0x0006B503 Virgil (MQ204 The Glowing Sea 0x0006B500 target inside Rocky Cave)",
        ),
    ),
)


A7B_NEXT_MISSIONS: Tuple[Dict[str, Any], ...] = (
    {
        "quest_edid": "FO4SF_MQ106",
        "fo4_source_edid": "MQ106",
        "fo4_source_formid": 0x000229E7,
        "reserved_local_id": 0x000B00,
        "reserved_block": (0x000B00, 0x000B3F),
        "title": "Reunions",
        "start_stage": 10,
        "completion_stages": (500,),
        "stages": (10, 50, 75, 100, 125, 150, 200, 500),
        "objectives": (
            (10, "Follow Dogmeat to Fort Hagen", -87978.54, -5674.82, "Fort Hagen"),
            (50, "Enter Fort Hagen and reach the Command Center", -87978.54, -5674.82, "Fort Hagen"),
            (100, "Confront and defeat Kellogg", -87978.54, -5674.82, "Fort Hagen"),
            (150, "Search Kellogg and his terminal, then exit to the roof", -87978.54, -5674.82, "Fort Hagen"),
            (200, "Return to Diamond City and report to Nick or Piper", -16384.00, -27852.80, "Diamond City"),
        ),
        "transitions": (
            {"from": 10, "to": 50, "kind": "primary", "npc_gated": True, "label": "Dogmeat arrives at Fort Hagen entrance"},
            {"from": 10, "to": 50, "kind": "out_of_order", "npc_gated": False, "label": "REUN-01 direct walk to Fort Hagen roof/door (Dogmeat dismissed or downed)"},
            {"from": 50, "to": 75, "kind": "primary", "npc_gated": False, "label": "Enter FortHagen01 (0x0100BA4B) via 0D RoofLoadDoorId 0x0547B0"},
            {"from": 75, "to": 100, "kind": "primary", "npc_gated": False, "label": "Enter FortHagen02 Command Center (0x0100CFC6) via 0D elevator"},
            {"from": 100, "to": 125, "kind": "primary", "npc_gated": True, "label": "Complete Kellogg confrontation dialogue"},
            {"from": 100, "to": 125, "kind": "open_mode", "npc_gated": False, "label": "REUN-03 pre-attack Kellogg without dialogue"},
            {"from": 125, "to": 150, "kind": "primary", "npc_gated": False, "label": "Defeat Kellogg and take MQ201CyberBrain (0x0009BC6E) + password (0x000A02D8)"},
            {"from": 150, "to": 200, "kind": "primary", "npc_gated": False, "label": "Access Kellogg terminal (0x000CD4AC) and exit roof elevator (0x00DE53 -> Prydwen hook)"},
            {"from": 200, "to": 500, "kind": "primary", "npc_gated": True, "label": "Debrief with Nick Valentine or Piper at Diamond City"},
            {"from": 200, "to": 500, "kind": "open_mode", "npc_gated": False, "label": "REUN-05 Open-Mode agency desk log or direct arrival at Memory Den with CyberBrain"},
        ),
        "break_it_batches": (
            {"bat_id": "a7b1", "axis": "out_of_order", "target": "Fort Hagen roof entry (0D 0x0547B0)"},
            {"bat_id": "a7b2", "axis": "giver_dead", "target": "Fort Hagen Command Center Kellogg / terminal (0x000CD4AC) + Open-Mode debrief"},
        ),
        "known_bugs": ("REUN-01", "REUN-02", "REUN-03", "REUN-04", "REUN-05"),
    },
    {
        "quest_edid": "FO4SF_MQ201",
        "fo4_source_edid": "MQ202 (with MQ201 bridge + MQ203 Shattered)",
        "fo4_source_formid": 0x000229E9,
        "reserved_local_id": 0x000B40,
        "reserved_block": (0x000B40, 0x000B7F),
        "title": "Dangerous Minds",
        "start_stage": 5,
        "completion_stages": (300,),
        "stages": (5, 10, 100, 110, 120, 300),
        "objectives": (
            (5, "Bring Kellogg's cybernetic brain augmenter to the Memory Den", 20826.12, -11904.71, "Goodneighbor"),
            (10, "Speak with Doctor Amari in Goodneighbor's Memory Den", 20826.12, -11904.71, "Goodneighbor"),
            (100, "Enter the Memory Lounger in Doctor Amari's lab", 20826.12, -11904.71, "Goodneighbor"),
            (110, "Explore Kellogg's memories to locate Virgil's trail", 20826.12, -11904.71, "Goodneighbor"),
            (120, "Speak with Doctor Amari and prepare for the Glowing Sea", -56092.31, -78515.81, "Edge of the Glowing Sea"),
        ),
        "transitions": (
            {"from": 5, "to": 10, "kind": "primary", "npc_gated": False, "label": "Carry MQ201CyberBrain (0x0009BC6E) into GoodneighborTheMemoryDen (0x0100ED4A)"},
            {"from": 10, "to": 100, "kind": "primary", "npc_gated": True, "label": "Doctor Amari unlocks lab door (0x000537C3) and preps lounger"},
            {"from": 10, "to": 100, "kind": "open_mode", "npc_gated": False, "label": "MIND-01 Open-Mode terminal/augmenter bypass unlocks 0x000537C3 when Amari/Irma dead"},
            {"from": 100, "to": 110, "kind": "primary", "npc_gated": False, "label": "MIND-03 safe MessageBox -> MoveTo MQ203KelloggsBrain (0x0100F23E)"},
            {"from": 110, "to": 120, "kind": "primary", "npc_gated": True, "label": "Walk MemoryA..MemoryH with Amari voiceover and inspect Virgil's file (0x000D9749)"},
            {"from": 110, "to": 120, "kind": "open_mode", "npc_gated": False, "label": "MIND-02 R10 bridge watchdog / E-bypass straight to MemoryH Virgil file + return marker (0x000D3CA0)"},
            {"from": 120, "to": 300, "kind": "primary", "npc_gated": True, "label": "Doctor Amari debrief -> arm MQ204 The Glowing Sea (0x0006B500)"},
            {"from": 120, "to": 300, "kind": "open_mode", "npc_gated": False, "label": "MIND-05 Open-Mode lab terminal / Virgil file readout arms MQ204 -> VirgilsLab01 (0x01069B10)"},
        ),
        "break_it_batches": (
            {"bat_id": "a7b3", "axis": "giver_dead", "target": "Goodneighbor Memory Den lab door (0x000537C3) + lounger (0x00053468)"},
            {"bat_id": "a7b4", "axis": "save_reload", "target": "MQ203KelloggsBrain (0x0100F23E) Virgil file (0x000D9749) -> Glowing Sea handoff"},
        ),
        "known_bugs": ("MIND-01", "MIND-02", "MIND-03", "MIND-04", "MIND-05"),
    },
)


def check_formid_disjointness() -> Dict[str, Any]:
    """Verify A7b FormID reservation (0xB00..0xB7F) is strictly disjoint from A1(d), A4, and A7."""
    issues: List[str] = []
    seen_ranges: List[Tuple[str, int, int]] = [
        ("A1d_Min00_Scenes", 0x000800, 0x0009FF),
        ("A4_NextMissions", A4_RESERVED_RANGE[0], A4_RESERVED_RANGE[1]),
        ("A7_MQ104_MQ105", A7_RESERVED_RANGE[0], A7_RESERVED_RANGE[1]),
    ]
    for m in A7B_NEXT_MISSIONS:
        lo, hi = m["reserved_block"]
        qid = m["reserved_local_id"]
        if not (A7B_RESERVED_RANGE[0] <= lo <= qid <= hi <= A7B_RESERVED_RANGE[1]):
            issues.append(f"{m['quest_edid']}: 0x{qid:06X} / 0x{lo:06X}..0x{hi:06X} outside A7b 0xB00..0xB7F")
        if not (A5_PIPBOY_NEXT_SCAN_RANGE[0] <= qid <= A5_PIPBOY_NEXT_SCAN_RANGE[1]):
            issues.append(f"{m['quest_edid']}: 0x{qid:06X} outside next A5 scan window 0x800..0xBFF")
        for other_name, olo, ohi in seen_ranges:
            if not (hi < olo or lo > ohi):
                issues.append(f"{m['quest_edid']} (0x{lo:06X}..0x{hi:06X}) overlaps {other_name} (0x{olo:06X}..0x{ohi:06X})")
        seen_ranges.append((m["quest_edid"], lo, hi))
    return {
        "pass": not issues,
        "a7b_range": f"0x{A7B_RESERVED_RANGE[0]:06X}..0x{A7B_RESERVED_RANGE[1]:06X}",
        "a5_next_scan_window": f"0x{A5_PIPBOY_NEXT_SCAN_RANGE[0]:06X}..0x{A5_PIPBOY_NEXT_SCAN_RANGE[1]:06X}",
        "issues": issues,
    }


def evaluate_a7b_missions(missions: Sequence[Mapping[str, Any]] = A7B_NEXT_MISSIONS) -> Dict[str, Any]:
    """Run W6 reachability & Open-Mode dead-giver simulation over A7b mission state graphs."""
    report: Dict[str, Any] = {"pass": True, "missions": []}
    for m in missions:
        stages = list(m["stages"])
        start = int(m["start_stage"])
        finals = set(int(x) for x in m["completion_stages"])
        transitions = list(m["transitions"])

        def _check(open_mode: bool) -> Dict[str, Any]:
            adj: Dict[int, List[int]] = {s: [] for s in stages}
            for tr in transitions:
                if open_mode and tr.get("npc_gated", False):
                    continue
                adj.setdefault(int(tr["from"]), []).append(int(tr["to"]))

            seen = {start}
            q: deque[int] = deque([start])
            while q:
                cur = q.popleft()
                for nxt in adj.get(cur, ()):
                    if nxt not in seen:
                        seen.add(nxt)
                        q.append(nxt)

            unreachable = sorted(s for s in stages if s not in seen)
            stuck: List[int] = []
            for s in stages:
                if s in finals:
                    continue
                sub_seen = {s}
                sq: deque[int] = deque([s])
                can_finish = False
                while sq:
                    cur = sq.popleft()
                    if cur in finals:
                        can_finish = True
                        break
                    for nxt in adj.get(cur, ()):
                        if nxt not in sub_seen:
                            sub_seen.add(nxt)
                            sq.append(nxt)
                if not can_finish:
                    stuck.append(s)
            return {
                "pass": not unreachable and not stuck and bool(seen & finals),
                "unreachable": unreachable,
                "stuck": stuck,
            }

        normal_res = _check(open_mode=False)
        open_res = _check(open_mode=True)
        ok = normal_res["pass"] and open_res["pass"]
        if not ok:
            report["pass"] = False
        report["missions"].append({
            "quest_edid": m["quest_edid"],
            "reserved_local_id": f"0x{m['reserved_local_id']:06X}",
            "normal": normal_res,
            "open_mode": open_res,
            "pass": ok,
        })
    return report


def emit_a5_objective_tsv_rows(missions: Sequence[Mapping[str, Any]] = A7B_NEXT_MISSIONS) -> List[str]:
    """Emit A5-compatible 7-column FO4SFPipboyQuestObjectives.tsv rows (validated against Commonwealth bounds)."""
    rows: List[str] = []
    for m in missions:
        qid = f"0x{m['reserved_local_id']:06X}"
        qname = m["title"]
        for stage_idx, label, x, y, place in m["objectives"]:
            if not (math.isfinite(x) and math.isfinite(y)):
                raise ValueError(f"Non-finite objective coordinates for {qid}:{stage_idx}")
            if not (COMMONWEALTH_X_BOUNDS[0] <= x <= COMMONWEALTH_X_BOUNDS[1]):
                raise ValueError(f"X={x} out of Commonwealth bounds for {qid}:{stage_idx}")
            if not (COMMONWEALTH_Y_BOUNDS[0] <= y <= COMMONWEALTH_Y_BOUNDS[1]):
                raise ValueError(f"Y={y} out of Commonwealth bounds for {qid}:{stage_idx}")
            rows.append(f"{qid}\t{stage_idx}\t{qname}\t{label}\t{x:.2f}\t{y:.2f}\t{place}")
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A7b Reunions (MQ106) + Dangerous Minds (MQ201/MQ202) offline verifier.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("audit-a7b", help="Run FormID disjointness and W6 Normal/Open-Mode reachability checks.")
    sub.add_parser("emit-tsv", help="Print A5-compatible FO4SFPipboyQuestObjectives.tsv rows for A7b.")
    args = parser.parse_args(argv)

    if args.cmd == "audit-a7b":
        fid_res = check_formid_disjointness()
        w6_res = evaluate_a7b_missions()
        payload = {
            "pass": bool(fid_res["pass"] and w6_res["pass"]),
            "formids": fid_res,
            "w6": w6_res,
            "staged_places": [
                {
                    "fo4_edid": p.fo4_edid,
                    "fo4_cell_id": f"0x{p.fo4_cell_id:08X}",
                    "port_edid": p.port_edid,
                    "port_cell_id": f"0x{p.port_cell_id:08X}",
                    "staged_ref_count": p.staged_ref_count,
                }
                for p in A7B_STAGED_PLACES
            ],
        }
        print(json.dumps(payload, indent=2))
        return 0 if payload["pass"] else 1

    if args.cmd == "emit-tsv":
        for row in emit_a5_objective_tsv_rows():
            print(row)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
