"""A7 next-two story missions & places verifier (`Unlikely Valentine` MQ104 + `Getting a Clue` MQ105).

Prototype, offline — verifies:
  1. FormID reservation `FO4SFMission.esm:0x000A80..0x000AFF` (strictly disjoint from
     `A1(d)` `0x800..0x9FF` and `A4` `0xA00..0xA7F`, and inside `A5`'s `0x800..0xAFF`
     Pip-Boy `DATA / Quests` live scan window).
  2. Already-converted `interiors_b10` staged cells (`FO4Port_Vault114` `0x01002593`,
     `FO4Port_Vault11402` `0x010109FA`, `FO4Port_DmndValentines01` `0x01006B30`,
     `FO4Port_DmndStandsKellogg01` `0x0106B72C`, `FO4Port_FortHagen01` `0x0100BA4B`,
     `FO4Port_FortHagen02` `0x0100CFC6`) — zero reconversion required.
  3. `W6` 4-axis reachability & stuck analysis (Normal Mode + Open-Mode dead-giver
     simulation where every `npc_gated` transition is dropped and every stage must
     still reach completion, plus out-of-order, save/reload every stage, and fast-travel
     away checks).
  4. `A5` `FO4SFPipboyQuestObjectives.tsv` row generation with verified Commonwealth
     coordinates from `FO4SFPipboyMapMarkers.tsv`.
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
A5_PIPBOY_SCAN_RANGE = (0x000800, 0x000AFF)

# Canonical Fallout 4 Commonwealth map bounds (WRLD 0x0000003C MNAM outer cell edges)
COMMONWEALTH_X_BOUNDS = (-135168.0, 118784.0)
COMMONWEALTH_Y_BOUNDS = (-147456.0, 106496.0)


@dataclass(frozen=True)
class StagedPlaceSpec:
    fo4_edid: str
    fo4_cell_id: int
    port_edid: str
    port_cell_id: int
    mission_ids: Tuple[str, ...]
    expected_internal_xtel_pairs: int
    needs_exterior_load_doors: Tuple[str, ...]
    key_locks_and_triggers: Tuple[str, ...]


A7_STAGED_PLACES: Tuple[StagedPlaceSpec, ...] = (
    StagedPlaceSpec(
        fo4_edid="Vault114",
        fo4_cell_id=0x000428E4,
        port_edid="FO4Port_Vault114",
        port_cell_id=0x01002593,
        mission_ids=("FO4SF_MQ104",),
        expected_internal_xtel_pairs=2,
        needs_exterior_load_doors=(
            "0x0008E70F <-> 0x0004BAF6 (Park Street Station main metro entrance)",
            "0x000428E6 MQ104ServiceLadderREF <-> 0x00042908 (Boston Common escape ladder)",
        ),
        key_locks_and_triggers=(
            "0x0007C051 (Vault11402 exit elevator door, lock 255 scripted unlock)",
            "0x00083FB6 MQ104SkinnyMaloneMarker01 (confrontation chamber)",
            "0x0004BC21 / 0x0013B6EB (side doors lock 75)",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="Vault11402",
        fo4_cell_id=0x0007BEF3,
        port_edid="FO4Port_Vault11402",
        port_cell_id=0x010109FA,
        mission_ids=("FO4SF_MQ104",),
        expected_internal_xtel_pairs=2,
        needs_exterior_load_doors=(),
        key_locks_and_triggers=(
            "0x0007E7A4 NickPrisonDoorREF (lock 25 Novice OR Overseer terminal 0x000ADA18)",
            "0x0008A80C MQ104NickDoor02REF (lock 255 scripted escape door)",
            "0x0011B183 Vault114AtriumGoonsEnableMarker (Triggermen ambush enable)",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="DmndValentines01",
        fo4_cell_id=0x00001E47,
        port_edid="FO4Port_DmndValentines01",
        port_cell_id=0x01006B30,
        mission_ids=("FO4SF_MQ104", "FO4SF_MQ105"),
        expected_internal_xtel_pairs=0,
        needs_exterior_load_doors=(
            "0x000022CB <-> Diamond City hub / DmndGateREF bridge (agency front door)",
        ),
        key_locks_and_triggers=(
            "0x00002F25 NickValentineREF (agency debrief & chair alias 60)",
            "0x000371A5 IntroSceneValentinesStart",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="DmndStandsKellogg01",
        fo4_cell_id=0x00001E50,
        port_edid="FO4Port_DmndStandsKellogg01",
        port_cell_id=0x0106B72C,
        mission_ids=("FO4SF_MQ105",),
        expected_internal_xtel_pairs=0,
        needs_exterior_load_doors=(
            "0x000021B4 KelloggHouseDoorREF (lock 100 Master OR Geneva/Mayor key) <-> Diamond City hub bridge",
        ),
        key_locks_and_triggers=(
            "0x0011E23B MQ105KelloggDesk + 0x0011E23C KelloggSecretDoorButtonREF (under-desk button)",
            "0x0011E235 MQ106KelloggSecretDoorREF (lock 254 hidden armory door)",
            "0x00065F88 MQ105KelloggItemsEnableMarker + 0x0014586A MQ105InvestigateTableEnableMarker (KelloggCigar01)",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="FortHagen01",
        fo4_cell_id=0x000BB078,
        port_edid="FO4Port_FortHagen01",
        port_cell_id=0x0100BA4B,
        mission_ids=("FO4SF_MQ105",),
        expected_internal_xtel_pairs=1,
        needs_exterior_load_doors=(
            "Already wired by FO4SFFortHagen.esm (0D): RoofLoadDoorId 0x0547B0, RoofGateId 0x0232E1, RoofTermId 0x0232E0",
        ),
        key_locks_and_triggers=(
            "FO4SFFortHagen.esm QUST 0x800 FO4SF_FortHagenElevators (two elevator rigs + roof security gate)",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="FortHagen02",
        fo4_cell_id=0x000CD2AE,
        port_edid="FO4Port_FortHagen02",
        port_cell_id=0x0100CFC6,
        mission_ids=("FO4SF_MQ105",),
        expected_internal_xtel_pairs=1,
        needs_exterior_load_doors=(
            "Already wired by FO4SFFortHagen.esm (0D): LoadDoor02Id 0x00DE53 <-> RoofMarkerId 0x0A774C",
        ),
        key_locks_and_triggers=(
            "0x0009BC71 KelloggREF + 0x000CD4AC DN057_KelloggTerminal01REF (MQ106 Reunions handoff)",
        ),
    ),
)


A7_NEXT_MISSIONS: Tuple[Dict[str, Any], ...] = (
    {
        "quest_edid": "FO4SF_MQ104",
        "fo4_source_edid": "MQ104",
        "fo4_source_formid": 0x0001F25E,
        "reserved_local_id": 0x000A80,
        "reserved_block": (0x000A80, 0x000AAF),
        "title": "Unlikely Valentine",
        "start_stage": 10,
        "completion_stages": (200,),
        "stages": (10, 20, 40, 60, 85, 100, 200),
        "objectives": (
            (10, "Search Park Street Station for Nick Valentine", 14878.14, -15941.30, "Park Street Station"),
            (20, "Rescue Nick Valentine inside Vault 114", 8019.57, -18075.20, "Vault 114"),
            (30, "Escape Vault 114 with Nick Valentine", 8019.57, -18075.20, "Vault 114"),
            (40, "Meet Nick Valentine at his agency in Diamond City", -16384.00, -27852.80, "Diamond City"),
        ),
        "key_npcs": (
            {"edid": "CompanionNickValentine", "fo4_id": 0x00002F24, "fo4_essential": True},
            {"edid": "MQ104SkinnyMalone", "fo4_id": 0x00083FB4, "fo4_essential": False},
            {"edid": "MQ104Darla", "fo4_id": 0x000969D9, "fo4_essential": False},
            {"edid": "MQ104MobsterTaunter", "fo4_id": 0x0017412F, "fo4_essential": False},
        ),
        "transitions": (
            # Stage 10 -> 20: Enter Vault 114 (Park Street Station)
            {"from": 10, "to": 20, "kind": "primary", "npc_gated": False, "label": "Enter Park Street Station / Vault 114"},
            # Stage 20 -> 40: Reach Vault 11402 & unlock Nick's cell (terminal 0x000ADA18 or Lockpick 25)
            {"from": 20, "to": 40, "kind": "primary", "npc_gated": False, "label": "Unlock NickPrisonDoorREF (0x0007E7A4) or terminal 0x000ADA18"},
            # Stage 40 -> 60: Speak with Nick (primary) OR read Nick's case note if Nick dead in Open Mode
            {"from": 40, "to": 60, "kind": "primary", "npc_gated": True, "label": "Speak with Nick Valentine in Overseer office"},
            {"from": 40, "to": 60, "kind": "open_mode_fallback", "npc_gated": False, "label": "Open Mode: recover Nick's case notes/key from Overseer office"},
            # Stage 60 -> 85: Unlock MQ104NickDoor02REF (0x0008A80C) & exit Vault11402 to ambush chamber
            {"from": 60, "to": 85, "kind": "primary", "npc_gated": True, "label": "Nick unlocks MQ104NickDoor02REF (0x0008A80C) -> Vault114 exit"},
            {"from": 60, "to": 85, "kind": "open_mode_fallback", "npc_gated": False, "label": "R10/Open Mode: proximity/key override unlocks 0x0008A80C & 0x0007C051"},
            # Stage 85 -> 100: Resolve Skinny Malone / Darla confrontation (Speech OR combat)
            {"from": 85, "to": 100, "kind": "primary", "npc_gated": True, "label": "Persuade Skinny Malone or Darla to stand down"},
            {"from": 85, "to": 100, "kind": "out_of_order_or_combat", "npc_gated": False, "label": "Defeat Skinny Malone & Triggermen guards (or pre-cleared)"},
            # Stage 100 -> 200: Exit to Boston Common & debrief at agency (or log notes in Open Mode)
            {"from": 100, "to": 200, "kind": "primary", "npc_gated": True, "label": "Exit Vault 114 and speak with Nick outside or at agency"},
            {"from": 100, "to": 200, "kind": "open_mode_fallback", "npc_gated": False, "label": "Open Mode: reach Boston Common surface / inspect agency case file"},
        ),
        "known_bugs": (
            "UVAL-01",
            "UVAL-02",
            "UVAL-03",
            "UVAL-04",
            "UVAL-05",
        ),
        "w6_break_it": {
            "giver_dead": "If Ellie/Nick die in Open Mode (W7), Vault11402 Overseer terminal + case file still advance 40->60->85->100->200 and unlock FO4SF_MQ105.",
            "out_of_order": "Entering Vault 114 directly without visiting Valentine's Agency starts FO4SF_MQ104 at stage 20; killing Skinny Malone before dialogue advances 85->100 immediately.",
            "save_reload_every_stage": "All 7 stages (10,20,40,60,85,100,200) re-sync door lock states (0x0007E7A4, 0x0008A80C, 0x0007C051) and Nick tether on OnPlayerLoadGame.",
            "fast_travel_away": "Fast traveling away from Boston Common or leaving Vault 114 mid-escape preserves stage progress and re-arms door/tether triggers on return.",
        },
    },
    {
        "quest_edid": "FO4SF_MQ105",
        "fo4_source_edid": "MQ105",
        "fo4_source_formid": 0x000229E6,
        "reserved_local_id": 0x000AB0,
        "reserved_block": (0x000AB0, 0x000AFF),
        "title": "Getting a Clue",
        "start_stage": 10,
        "completion_stages": (200,),
        "stages": (10, 30, 60, 80, 100, 200),
        "objectives": (
            (10, "Sit down and brief Nick Valentine at his agency", -16384.00, -27852.80, "Diamond City"),
            (30, "Gain access to Kellogg's house in Diamond City", -16384.00, -27852.80, "Diamond City"),
            (60, "Search Kellogg's house for a hidden room and clues", -16384.00, -27852.80, "Diamond City"),
            (80, "Follow the cigar trail to Fort Hagen", -87978.54, -5674.82, "Fort Hagen"),
        ),
        "key_npcs": (
            {"edid": "CompanionNickValentine", "fo4_id": 0x00002F24, "fo4_essential": True},
            {"edid": "ElliePerkins", "fo4_id": 0x000222A2, "fo4_essential": True},
            {"edid": "Geneva", "fo4_id": 0x00002F0A, "fo4_essential": True},
            {"edid": "MayorMcDonough", "fo4_id": 0x00002F08, "fo4_essential": True},
            {"edid": "Kellogg", "fo4_id": 0x0009BC6C, "fo4_essential": False},
        ),
        "transitions": (
            # Stage 10 -> 30: Brief Nick in DmndValentines01 OR read agency Kellogg dossier in Open Mode
            {"from": 10, "to": 30, "kind": "primary", "npc_gated": True, "label": "Sit in agency chair and brief Nick Valentine"},
            {"from": 10, "to": 30, "kind": "open_mode_fallback", "npc_gated": False, "label": "Open Mode: read Kellogg dossier on Valentine's desk"},
            # Stage 30 -> 60: Enter Kellogg's House (Mayor/Geneva key OR pickpocket/desk key OR Master lockpick 100)
            {"from": 30, "to": 60, "kind": "primary", "npc_gated": True, "label": "Obtain Kellogg's house key from Mayor McDonough or Geneva"},
            {"from": 30, "to": 60, "kind": "out_of_order_or_lockpick", "npc_gated": False, "label": "Pick Master lock (0x000021B4) or loot key from MayorDesk"},
            # Stage 60 -> 80: Press under-desk button (0x0011E23C) -> open secret door (0x0011E235) -> inspect KelloggCigar01
            {"from": 60, "to": 80, "kind": "primary", "npc_gated": False, "label": "Activate KelloggSecretDoorButtonREF (0x0011E23C) and inspect KelloggCigar01"},
            # Stage 80 -> 100: Give cigar to Dogmeat (primary) OR depart directly toward Fort Hagen
            {"from": 80, "to": 100, "kind": "primary", "npc_gated": True, "label": "Let Dogmeat track Kellogg's cigar scent outside Diamond City"},
            {"from": 80, "to": 100, "kind": "open_mode_fallback", "npc_gated": False, "label": "Open Mode / anti-stall: inspect cigar & mark Fort Hagen directly"},
            # Stage 100 -> 200: Reach Fort Hagen (00090A / FO4SFFortHagen.esm RoofLoadDoorId 0x0547B0) -> MQ106 Reunions handoff
            {"from": 100, "to": 200, "kind": "primary", "npc_gated": False, "label": "Arrive at Fort Hagen (00090A) / FortHagen01 entry -> hand off to MQ106"},
        ),
        "known_bugs": (
            "CLUE-01",
            "CLUE-02",
            "CLUE-03",
            "CLUE-04",
            "CLUE-05",
        ),
        "w6_break_it": {
            "giver_dead": "If Nick, Geneva, McDonough, or Dogmeat die/are absent in Open Mode (W7), agency dossier + MayorDesk key/lockpick + direct Fort Hagen discovery complete every stage.",
            "out_of_order": "Lockpicking KelloggHouseDoorREF (0x000021B4) or finding Fort Hagen early still advances stages cleanly without requiring Geneva dialogue or Dogmeat pathing.",
            "save_reload_every_stage": "All 6 stages (10,30,60,80,100,200) re-assert secret door state (0x0011E235), clue enable marker (0x00065F88), and Fort Hagen arrival check on OnPlayerLoadGame.",
            "fast_travel_away": "Fast traveling away mid-trail never breaks Dogmeat tracking because reaching Fort Hagen exterior (00090A) or FortHagen01 directly completes stage 200.",
        },
    },
)


def evaluate_a7_missions(missions: Sequence[Mapping[str, Any]] = A7_NEXT_MISSIONS) -> Dict[str, Any]:
    """Run strict W6 reachability & Open-Mode dead-giver analysis across A7 missions.

    In Open Mode (`open_mode=True`), EVERY transition tagged `npc_gated=True` is dropped,
    and EVERY stage in `stages` must still have a directed path to `completion_stages`.
    """
    results: Dict[str, Any] = {}
    all_pass = True

    for m in missions:
        qid = str(m["quest_edid"])
        stages = tuple(int(s) for s in m["stages"])
        stage_set = set(stages)
        start = int(m["start_stage"])
        completions = set(int(s) for s in m["completion_stages"])
        transitions = list(m["transitions"])

        def _check(open_mode: bool) -> Dict[str, Any]:
            adj: Dict[int, List[int]] = {s: [] for s in stages}
            radj: Dict[int, List[int]] = {s: [] for s in stages}
            for t in transitions:
                if open_mode and bool(t.get("npc_gated", False)):
                    continue
                u, v = int(t["from"]), int(t["to"])
                if u in stage_set and v in stage_set:
                    adj[u].append(v)
                    radj[v].append(u)

            # Forward reachability from start_stage
            reachable: set[int] = set()
            q = deque([start])
            reachable.add(start)
            while q:
                cur = q.popleft()
                for nxt in adj[cur]:
                    if nxt not in reachable:
                        reachable.add(nxt)
                        q.append(nxt)

            # Backward reachability from completion_stages
            can_finish: set[int] = set(completions)
            rq = deque(completions)
            while rq:
                cur = rq.popleft()
                for prv in radj[cur]:
                    if prv not in can_finish:
                        can_finish.add(prv)
                        rq.append(prv)

            unreachable = sorted(s for s in stages if s not in reachable)
            stuck_stages = sorted(s for s in stages if s not in can_finish)
            ok = (not unreachable) and (not stuck_stages) and bool(reachable & completions)
            return {
                "ok": ok,
                "unreachable": unreachable,
                "stuck_stages": stuck_stages,
            }

        normal = _check(open_mode=False)
        open_mode = _check(open_mode=True)
        w6_keys = set(m.get("w6_break_it", {}).keys())
        w6_complete = {"giver_dead", "out_of_order", "save_reload_every_stage", "fast_travel_away"}.issubset(w6_keys)
        local_id = int(m["reserved_local_id"])
        id_in_a7 = A7_RESERVED_RANGE[0] <= local_id <= A7_RESERVED_RANGE[1]
        id_in_a5 = A5_PIPBOY_SCAN_RANGE[0] <= local_id <= A5_PIPBOY_SCAN_RANGE[1]
        id_disjoint_a4 = not (A4_RESERVED_RANGE[0] <= local_id <= A4_RESERVED_RANGE[1])

        quest_ok = normal["ok"] and open_mode["ok"] and w6_complete and id_in_a7 and id_in_a5 and id_disjoint_a4
        if not quest_ok:
            all_pass = False

        results[qid] = {
            "ok": quest_ok,
            "reserved_local_id": f"0x{local_id:06X}",
            "normal": normal,
            "open_mode": open_mode,
            "w6_complete": w6_complete,
            "id_in_a7_and_a5": id_in_a7 and id_in_a5 and id_disjoint_a4,
            "known_bug_count": len(m.get("known_bugs", ())),
        }

    return {"pass": all_pass, "missions": results}


def build_a7_pipboy_objective_rows(missions: Sequence[Mapping[str, Any]] = A7_NEXT_MISSIONS) -> List[str]:
    """Emit A5-compatible `FO4SFPipboyQuestObjectives.tsv` rows for all A7 missions."""
    lines: List[str] = []
    for m in missions:
        local_id = int(m["reserved_local_id"])
        for obj_num, text, x_fo4, y_fo4, loc_label in m["objectives"]:
            if not (math.isfinite(x_fo4) and math.isfinite(y_fo4)):
                raise ValueError(f"non-finite coords for {m['quest_edid']} obj {obj_num}")
            if not (COMMONWEALTH_X_BOUNDS[0] <= x_fo4 <= COMMONWEALTH_X_BOUNDS[1]):
                raise ValueError(f"x_fo4 out of bounds: {x_fo4}")
            if not (COMMONWEALTH_Y_BOUNDS[0] <= y_fo4 <= COMMONWEALTH_Y_BOUNDS[1]):
                raise ValueError(f"y_fo4 out of bounds: {y_fo4}")
            lines.append(
                f"FO4SFMission.esm\t{local_id:06X}\t{int(obj_num)}\t{x_fo4:.2f}\t{y_fo4:.2f}\t{loc_label}\t{text}"
            )
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Offline A7 verifier for Unlikely Valentine (MQ104) & Getting a Clue (MQ105).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("audit-a7", help="Run W6 normal & Open-Mode dead-giver reachability checks")
    sub.add_parser("emit-tsv", help="Print A5-compatible FO4SFPipboyQuestObjectives.tsv rows for A7")
    args = ap.parse_args(argv)

    if args.cmd == "audit-a7":
        res = evaluate_a7_missions()
        print(json.dumps(res, indent=2))
        return 0 if res["pass"] else 1
    if args.cmd == "emit-tsv":
        for row in build_a7_pipboy_objective_rows():
            print(row)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
