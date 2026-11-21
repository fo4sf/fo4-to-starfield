#!/usr/bin/env python3
"""Tier 1 offline quest state-machine & fragility checker (W6 / W7).

Models quest stages, flags, globals, items, essential NPCs, and transition edges
from ``src/fo4sf/testing/quest_test_catalog.json`` and checks offline:

  (a) Reachability / No Dead Ends:
      From every reachable quest stage and every declared reachable player state
      (including out-of-order arrival, pre-cleared enemies, and — when
      ``--open-mode`` is passed — W7 Open Mode states where essential NPCs are
      dead), there must remain a valid directed path to a completion stage (or
      an explicit clean spine-continuation handoff for mutually exclusive side
      quests).
  (b) Single-Edge Fragility & Single-Route Rewards:
      Identifies every progression edge whose removal disconnects ``start_stage``
      from all ``completion_stages`` (cut-edge / single-edge chokepoint) and any
      reward reachable by only one sequence, outputting the deterministic
      ``FRAGILE`` list and exact per-tier quest counts.

Usage:
  python scripts/testing/check_quest_fragility.py
  python scripts/testing/check_quest_fragility.py --open-mode
  python scripts/testing/check_quest_fragility.py --game FO4 --open-mode --json
"""
from __future__ import annotations

import argparse
from collections import deque
import json
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

GAME_ORDER = {"FO4": 0, "FO3": 1, "FNV": 2}


def default_catalog_path() -> Path:
    """Resolve ``quest_test_catalog.json`` in repo layout or standalone scratch layout."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "src" / "fo4sf" / "testing" / "quest_test_catalog.json"
        if len(here.parents) >= 3
        else here.parent / "quest_test_catalog.json",
        here.parent / "quest_test_catalog.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def load_catalog(path: Optional[Path] = None) -> Dict[str, Any]:
    target = path or default_catalog_path()
    with target.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or "quests" not in data or not isinstance(data["quests"], list):
        raise ValueError(f"Invalid quest catalog structure in {target}")
    return data


def _edge_usable(
    edge: Dict[str, Any],
    *,
    dead_npcs: Set[str],
    open_mode: bool,
    allow_open_mode_fallbacks: bool,
) -> bool:
    """Return True if a transition edge can be traversed under the active mode and dead-NPC set."""
    if edge.get("open_mode_only", False) and not (open_mode and allow_open_mode_fallbacks):
        return False
    req_npcs = set(edge.get("requires_npcs") or ())
    if req_npcs & dead_npcs:
        return False
    return True


def _build_adjacency(
    transitions: Sequence[Dict[str, Any]],
    *,
    dead_npcs: Set[str],
    open_mode: bool,
    allow_open_mode_fallbacks: bool,
    skip_edge_index: Optional[int] = None,
) -> Dict[int, List[Tuple[int, int]]]:
    adj: Dict[int, List[Tuple[int, int]]] = {}
    for idx, edge in enumerate(transitions):
        if skip_edge_index is not None and idx == skip_edge_index:
            continue
        if not _edge_usable(
            edge,
            dead_npcs=dead_npcs,
            open_mode=open_mode,
            allow_open_mode_fallbacks=allow_open_mode_fallbacks,
        ):
            continue
        src = int(edge["from"])
        dst = int(edge["to"])
        adj.setdefault(src, []).append((dst, idx))
    return adj


def _reachable_from(start: int, adj: Dict[int, List[Tuple[int, int]]]) -> Set[int]:
    seen: Set[int] = {start}
    q: deque[int] = deque([start])
    while q:
        cur = q.popleft()
        for nxt, _ in adj.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return seen


def _can_reach_any(start: int, targets: Set[int], adj: Dict[int, List[Tuple[int, int]]]) -> bool:
    if start in targets:
        return True
    return bool(_reachable_from(start, adj) & targets)


def _find_cut_edges(
    quest: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Find every normal-play progression edge whose removal disconnects start_stage from primary completion."""
    start = int(quest["start_stage"])
    primary_completion = int(quest["completion_stages"][0])
    completions = {primary_completion}
    transitions = quest.get("transitions") or []

    def _normal_story_edge(e: Dict[str, Any]) -> bool:
        if e.get("open_mode_only", False):
            return False
        if e.get("kind") in ("mode_branch", "terminal_standdown"):
            return False
        return True

    story_transitions = [e for e in transitions if _normal_story_edge(e)]
    base_adj = _build_adjacency(
        story_transitions,
        dead_npcs=set(),
        open_mode=False,
        allow_open_mode_fallbacks=False,
    )
    if not _can_reach_any(start, completions, base_adj):
        return []

    cut_edges: List[Dict[str, Any]] = []
    for idx, edge in enumerate(story_transitions):
        if int(edge["from"]) in completions:
            continue
        adj_without = _build_adjacency(
            story_transitions,
            dead_npcs=set(),
            open_mode=False,
            allow_open_mode_fallbacks=False,
            skip_edge_index=idx,
        )
        if not _can_reach_any(start, completions, adj_without):
            cut_edges.append(
                {
                    "from": int(edge["from"]),
                    "to": int(edge["to"]),
                    "label": str(edge["label"]),
                    "kind": str(edge.get("kind", "primary")),
                    "fragile_reason": edge.get("fragile_reason") or "single-edge progression chokepoint",
                }
            )
    return cut_edges


def analyze_quest(quest: Dict[str, Any], *, open_mode: bool = False) -> Dict[str, Any]:
    """Run offline reachability, Open Mode essential-NPC-dead, and fragility checks on one quest."""
    qid = str(quest["id"])
    stages = {int(s) for s in quest["stages"]}
    start = int(quest["start_stage"])
    completions = {int(s) for s in quest["completion_stages"]}
    non_comp_terminals = {int(s) for s in quest.get("terminal_non_completion_stages") or ()}
    transitions = quest.get("transitions") or []
    essential_npcs = quest.get("essential_npcs") or []

    dead_ends: List[Dict[str, Any]] = []
    open_mode_failures: List[Dict[str, Any]] = []

    if start not in stages:
        dead_ends.append({"quest_id": qid, "state": "start_stage", "stage": start, "reason": "start_stage not in stages"})
    if not completions or not completions.issubset(stages):
        dead_ends.append(
            {
                "quest_id": qid,
                "state": "completion_stages",
                "stage": start,
                "reason": "completion_stages empty or not subset of stages",
            }
        )

    # 1. Standard graph reachability from every stage reachable from start_stage
    normal_adj = _build_adjacency(
        transitions,
        dead_npcs=set(),
        open_mode=False,
        allow_open_mode_fallbacks=False,
    )
    reachable_stages = _reachable_from(start, normal_adj)
    for st in sorted(reachable_stages):
        if st in completions or st in non_comp_terminals:
            continue
        if not _can_reach_any(st, completions, normal_adj):
            dead_ends.append(
                {
                    "quest_id": qid,
                    "state": f"stage_{st}",
                    "stage": st,
                    "reason": f"no path from reachable stage {st} to completion stages {sorted(completions)}",
                }
            )

    # 2. Declared reachable player entry states (out-of-order, pre-cleared, Open Mode)
    for entry in quest.get("reachable_entry_states") or ():
        entry_open_only = bool(entry.get("open_mode_only", False))
        if entry_open_only and not open_mode:
            continue
        st = int(entry["stage"])
        dead_set = set(entry.get("dead_npcs") or ())
        adj = _build_adjacency(
            transitions,
            dead_npcs=dead_set,
            open_mode=open_mode or entry_open_only,
            allow_open_mode_fallbacks=open_mode or entry_open_only,
        )
        ok_targets = set(completions)
        if entry.get("allows_clean_fail_handoff", False):
            ok_targets |= non_comp_terminals
        if st not in stages or not _can_reach_any(st, ok_targets, adj):
            rec = {
                "quest_id": qid,
                "state": str(entry["name"]),
                "stage": st,
                "dead_npcs": sorted(dead_set),
                "reason": f"entry state '{entry['name']}' cannot reach completion {sorted(ok_targets)}",
            }
            dead_ends.append(rec)
            if entry_open_only or dead_set:
                open_mode_failures.append(rec)

    # 3. W7 Open Mode exhaustive single-essential-NPC-dead check
    if open_mode and essential_npcs:
        for npc in essential_npcs:
            npc_id = str(npc["id"])
            if not str(npc.get("open_mode_fallback") or "").strip():
                rec = {
                    "quest_id": qid,
                    "state": f"open_mode_dead_{npc_id}",
                    "stage": start,
                    "dead_npcs": [npc_id],
                    "reason": f"essential NPC '{npc_id}' missing W7 open_mode_fallback description",
                }
                dead_ends.append(rec)
                open_mode_failures.append(rec)
                continue
            adj_dead = _build_adjacency(
                transitions,
                dead_npcs={npc_id},
                open_mode=True,
                allow_open_mode_fallbacks=True,
            )
            ok_targets = set(completions)
            if quest.get("open_mode_clean_bypass_stages"):
                ok_targets |= {int(s) for s in quest["open_mode_clean_bypass_stages"]}
            if not _can_reach_any(start, ok_targets, adj_dead):
                rec = {
                    "quest_id": qid,
                    "state": f"open_mode_dead_{npc_id}",
                    "stage": start,
                    "dead_npcs": [npc_id],
                    "reason": f"killing essential NPC '{npc_id}' in Open Mode leaves no path to {sorted(ok_targets)}",
                }
                dead_ends.append(rec)
                open_mode_failures.append(rec)

    # 4. Single-edge fragility & single-route reward detection
    cut_edges = _find_cut_edges(quest)
    fragile_cut_edges = [
        e for e in cut_edges if e["kind"] not in ("bootstrap_init", "auto_complete")
    ]

    fragile_rewards: List[Dict[str, Any]] = []
    for reward in quest.get("rewards") or ():
        routes = list(reward.get("routes") or ())
        if len(routes) < 2 or bool(reward.get("single_sequence_only", False)):
            fragile_rewards.append(
                {
                    "reward_id": str(reward["id"]),
                    "name": str(reward["name"]),
                    "routes": routes,
                    "reason": str(
                        reward.get("fragile_reason")
                        or f"reachable only via {len(routes)} route(s)"
                    ),
                }
            )

    explicit_reasons = list(quest.get("fragile_notes") or ())
    is_fragile = bool(fragile_cut_edges or fragile_rewards or explicit_reasons)

    return {
        "id": qid,
        "title": str(quest["title"]),
        "game": str(quest["game"]),
        "category": str(quest["category"]),
        "plugin": str(quest["plugin"]),
        "form_id": str(quest["form_id"]),
        "main_spine": bool(quest.get("main_spine", False)),
        "feel_item": bool(quest.get("feel_item", False)),
        "tiers": sorted(int(t) for t in quest.get("tiers") or ()),
        "stage_count": len(stages),
        "transition_count": len(transitions),
        "essential_npc_count": len(essential_npcs),
        "dead_ends": dead_ends,
        "open_mode_failures": open_mode_failures,
        "fragile": is_fragile,
        "fragile_cut_edges": fragile_cut_edges,
        "fragile_rewards": fragile_rewards,
        "fragile_notes": explicit_reasons,
    }


def evaluate_catalog(
    catalog: Dict[str, Any],
    *,
    game: str = "ALL",
    open_mode: bool = False,
) -> Dict[str, Any]:
    """Evaluate all selected quests and compute deterministic FRAGILE list & tier counts."""
    quests = list(catalog["quests"])
    if game.upper() != "ALL":
        want = game.upper()
        quests = [q for q in quests if str(q["game"]).upper() == want]

    quests.sort(key=lambda q: (GAME_ORDER.get(str(q["game"]), 99), int(q.get("order", 9999)), str(q["id"])))

    results = [analyze_quest(q, open_mode=open_mode) for q in quests]
    dead_ends = [de for r in results for de in r["dead_ends"]]
    open_mode_failures = [om for r in results for om in r["open_mode_failures"]]
    fragile_quests = [r for r in results if r["fragile"]]

    tier_counts: Dict[str, Dict[str, int]] = {}
    for tier in (1, 2, 3, 4):
        per_game = {"FO4": 0, "FO3": 0, "FNV": 0, "total": 0}
        for r in results:
            if tier in r["tiers"]:
                g = r["game"]
                per_game[g] = per_game.get(g, 0) + 1
                per_game["total"] += 1
        tier_counts[f"tier_{tier}"] = per_game

    fragile_by_game = {"FO4": 0, "FO3": 0, "FNV": 0, "total": len(fragile_quests)}
    for r in fragile_quests:
        g = r["game"]
        fragile_by_game[g] = fragile_by_game.get(g, 0) + 1

    return {
        "schema_version": catalog.get("schema_version", 1),
        "game_filter": game.upper(),
        "open_mode": open_mode,
        "quests_checked": len(results),
        "dead_end_count": len(dead_ends),
        "open_mode_failure_count": len(open_mode_failures),
        "fragile_count": len(fragile_quests),
        "fragile_by_game": fragile_by_game,
        "tier_counts": tier_counts,
        "dead_ends": dead_ends,
        "open_mode_failures": open_mode_failures,
        "fragile_list": [
            {
                "id": r["id"],
                "game": r["game"],
                "title": r["title"],
                "form_id": r["form_id"],
                "cut_edges": r["fragile_cut_edges"],
                "fragile_rewards": r["fragile_rewards"],
                "notes": r["fragile_notes"],
            }
            for r in fragile_quests
        ],
        "quests": results,
    }


def format_text_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    mode_tag = "OPEN-MODE (W7)" if report["open_mode"] else "NORMAL"
    lines.append(
        f"FO4SF Tier 1 Quest Fragility Report | filter={report['game_filter']} | mode={mode_tag}"
    )
    lines.append(
        f"Quests checked: {report['quests_checked']} | Dead ends: {report['dead_end_count']} "
        f"| Open-mode failures: {report['open_mode_failure_count']} | FRAGILE: {report['fragile_count']}"
    )
    lines.append("")
    lines.append("Per-Tier Quest Counts:")
    for tier_key in ("tier_1", "tier_2", "tier_3", "tier_4"):
        tc = report["tier_counts"][tier_key]
        lines.append(
            f"  {tier_key.upper()}: total={tc['total']} "
            f"(FO4={tc['FO4']}, FO3={tc['FO3']}, FNV={tc['FNV']})"
        )
    lines.append("")
    if report["dead_ends"]:
        lines.append("DEAD ENDS (FAIL):")
        for de in report["dead_ends"]:
            lines.append(
                f"  - {de['quest_id']} [{de['state']} @ stage {de['stage']}]: {de['reason']}"
            )
        lines.append("")
    lines.append(f"FRAGILE LIST ({report['fragile_count']} quests):")
    for item in report["fragile_list"]:
        reasons: List[str] = []
        for ce in item["cut_edges"]:
            reasons.append(f"edge {ce['from']}->{ce['to']} ({ce['label']}): {ce['fragile_reason']}")
        for rw in item["fragile_rewards"]:
            reasons.append(f"reward {rw['reward_id']}: {rw['reason']}")
        for note in item["notes"]:
            reasons.append(note)
        reason_str = "; ".join(reasons) if reasons else "single-sequence path"
        lines.append(
            f"  - [{item['game']}] {item['id']} ({item['form_id']}) -- {item['title']}: {reason_str}"
        )
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Tier 1 offline quest state-machine, Open Mode, and fragility checker."
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="Path to quest_test_catalog.json (defaults to src/fo4sf/testing/quest_test_catalog.json).",
    )
    parser.add_argument(
        "--game",
        choices=("ALL", "FO4", "FO3", "FNV"),
        default="ALL",
        help="Filter quests by game title.",
    )
    parser.add_argument(
        "--open-mode",
        action="store_true",
        help="Also verify W7 Open Mode essential-NPC-dead reachability.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--fail-on-fragile",
        action="store_true",
        help="Return exit code 2 if any FRAGILE quests are detected.",
    )
    args = parser.parse_args(argv)

    catalog = load_catalog(args.catalog)
    report = evaluate_catalog(catalog, game=args.game, open_mode=args.open_mode)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_text_report(report))

    if report["dead_end_count"] > 0:
        return 1
    if args.fail_on_fragile and report["fragile_count"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
