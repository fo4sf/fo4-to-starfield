"""World-state-driven radiant mission generator and verifier for the A-Life SDK (Round 9 X9, prototype, offline).

Generates contextual requests from the simulated A-Life world state (node captures, squad casualties,
active raids, nearby hostile garrisons, resource nodes, and allied supply routes) rather than isolated
dice rolls. Includes:
  - 5 request types (fetch_or_rescue, kill_named_threat, avenge_or_investigate, clear_or_retake_node,
    escort_or_deliver) held by local area NPCs (settler, trader, guard) and surfaced on the secondary
    faction device's tabbed pages (bounties, settlements, warfare, faction_comms),
  - W7 Open-Mode dead-giver handling (deputy role succession -> faction-comms dropbox fallback ->
    failed_with_consequence when an escorted charge dies, plus graceful resolution if another A-Life
    squad clears the target first),
  - Save/reload-safe fixed-slot integer/float array serialization within Papyrus's 128-element limit
    and a hard cap on active requests,
  - QualityGuard preventing target/template repetition and verify_mission_completable() checking
    reachability, faction coherence, deadlines, and non-deadlocking turn-in across >= 20 seeds.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from . import schema, sim_math

REQUEST_TYPES: tuple[str, ...] = (
    "fetch_or_rescue",
    "kill_named_threat",
    "avenge_or_investigate",
    "clear_or_retake_node",
    "escort_or_deliver",
)

GIVER_ROLES: tuple[str, ...] = ("settler", "trader", "guard")

SECONDARY_DEVICE_TABS: tuple[str, ...] = (
    "map",
    "quests",
    "warfare",
    "settlements",
    "bounties",
    "faction_comms",
)

MISSION_STATES: tuple[str, ...] = (
    "offered",
    "active",
    "completed",
    "completed_via_deputy",
    "completed_via_comms",
    "resolved_by_alife_ally",
    "failed_with_consequence",
    "expired_with_consequence",
)

TERMINAL_STATES: frozenset[str] = frozenset({
    "completed",
    "completed_via_deputy",
    "completed_via_comms",
    "resolved_by_alife_ally",
    "failed_with_consequence",
    "expired_with_consequence",
})

DEFAULT_MAX_ACTIVE = 3
MAX_ALLOWED_SLOTS = 5
DEFAULT_COOLDOWN_HISTORY = 8
PAPYRUS_ARRAY_LIMIT = 128


def cross_os_basename(raw_path: str) -> str:
    """Delegate to schema.path_basename so Windows drive, UNC, POSIX, and mixed paths behave identically."""
    return schema.path_basename(raw_path)


@dataclass(frozen=True)
class WorldStateSnapshot:
    """Structured A-Life world state derived from a normalized config + sim_math run."""

    config: dict[str, Any]
    graph: sim_math.Graph
    seed: int
    ticks: int
    sim_seconds: float
    initial_owners: tuple[int, ...]
    node_owners: tuple[int, ...]
    hostile: tuple[tuple[bool, ...], ...]
    faction_ids: tuple[str, ...]
    faction_Index_by_id: Mapping[str, int]
    captures: tuple[dict[str, Any], ...]
    battles: tuple[dict[str, Any], ...]
    casualties: tuple[dict[str, Any], ...]
    active_raids: tuple[dict[str, Any], ...]
    live_squad_nodes: Mapping[int, tuple[int, ...]]


@dataclass(frozen=True)
class RadiantMission:
    """One world-state-triggered request with components, W7 fallback, and UI routing."""

    mission_id: str
    seed: int
    request_type: str
    giver_node_index: int
    giver_node_id: str
    giver_role: str
    giver_npc_tag: str
    giver_faction_index: int
    giver_faction_id: str
    target_node_index: int
    target_node_id: str
    target_faction_index: int
    target_faction_id: str | None
    what_tag: str
    route_nodes: tuple[int, ...]
    distance_m: float
    trigger: Mapping[str, Any]
    reward_caps: int
    reward_fame: int
    deadline_s: float
    consequence_on_success: Mapping[str, Any]
    consequence_on_failure: Mapping[str, Any]
    giver_died_fallback: Mapping[str, Any]
    secondary_device_tab: str
    pipboy_quest_list_on_accept: bool = True
    state: str = "offered"


@dataclass
class QualityGuard:
    """Anti-repetition and anti-nonsense filter across successive mission draws."""

    cooldown_window: int = DEFAULT_COOLDOWN_HISTORY
    recent_pairs: list[tuple[str, int]] = field(default_factory=list)
    recent_targets: list[int] = field(default_factory=list)
    recent_types: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.cooldown_window < 1 or self.cooldown_window > PAPYRUS_ARRAY_LIMIT:
            raise ValueError(f"cooldown_window must be 1..{PAPYRUS_ARRAY_LIMIT}")

    def allows(self, request_type: str, target_node: int, batch_targets: set[int]) -> bool:
        if target_node in batch_targets:
            return False
        if (request_type, target_node) in self.recent_pairs:
            return False
        return True

    def novelty_bonus(self, request_type: str, target_node: int, batch_types: set[str]) -> float:
        bonus = 0.0
        if request_type not in batch_types:
            bonus += 25.0
        if request_type not in self.recent_types[-3:]:
            bonus += 12.0
        if target_node not in self.recent_targets[-4:]:
            bonus += 15.0
        return bonus

    def record(self, mission: RadiantMission) -> None:
        self.recent_pairs.append((mission.request_type, mission.target_node_index))
        self.recent_targets.append(mission.target_node_index)
        self.recent_types.append(mission.request_type)
        if len(self.recent_pairs) > self.cooldown_window:
            self.recent_pairs = self.recent_pairs[-self.cooldown_window:]
        if len(self.recent_targets) > self.cooldown_window:
            self.recent_targets = self.recent_targets[-self.cooldown_window:]
        if len(self.recent_types) > self.cooldown_window:
            self.recent_types = self.recent_types[-self.cooldown_window:]


def snapshot_from_simulation(
    cfg: Mapping[str, Any] | str,
    sim_result: Mapping[str, Any] | None = None,
    *,
    ticks: int = 600,
    seed: int = 42,
) -> WorldStateSnapshot:
    """Build a deterministic WorldStateSnapshot from an A-Life config and simulation trace."""
    if isinstance(cfg, str):
        cfg = schema.load_alife_config(cfg)
    norm = schema.checked(cfg)
    if sim_result is None or "events" not in sim_result:
        sim_result = sim_math.simulate(norm, ticks=ticks, seed=seed, record_events=True)

    facs = norm["factions"]
    nodes = norm["nodes"]
    f_count = len(facs)
    fac_ids = tuple(f["id"] for f in facs)
    fac_idx = {fid: i for i, fid in enumerate(fac_ids)}
    rel = schema.relations_flat(norm)
    hostile = tuple(
        tuple(rel[a * f_count + b] < 0 for b in range(f_count))
        for a in range(f_count)
    )
    graph = sim_math.Graph(nodes, norm["edges"])
    initial_owners = tuple(int(n["initial_owner"]) for n in nodes)
    final_owners_raw = sim_result["final_owners"]
    node_owners = tuple(fac_idx[fid] if fid is not None else -1 for fid in final_owners_raw)

    squad_fac: dict[int, int] = {}
    squad_node: dict[int, int] = {}
    squad_alive: dict[int, bool] = {}
    squad_raid_goal: dict[int, tuple[int, int, int]] = {}  # sid -> (tick, origin, goal)

    captures: list[dict[str, Any]] = []
    battles: list[dict[str, Any]] = []
    casualties: list[dict[str, Any]] = []

    for tick, step, payload in sim_result.get("events", ()):
        if step == "squad_spawn":
            sid = int(payload["squad"])
            f_i = fac_idx[payload["faction"]]
            n_i = int(payload["node"])
            squad_fac[sid] = f_i
            squad_node[sid] = n_i
            squad_alive[sid] = True
        elif step == "order":
            sid = int(payload["squad"])
            origin = int(payload["node"])
            goal = int(payload["goal"])
            squad_node[sid] = origin
            if payload.get("order") == "raid":
                squad_raid_goal[sid] = (int(tick), origin, goal)
            else:
                squad_raid_goal.pop(sid, None)
        elif step in ("node_arrive", "garrison"):
            sid = int(payload["squad"])
            squad_node[sid] = int(payload["node"])
            if step == "garrison":
                squad_raid_goal.pop(sid, None)
        elif step == "capture":
            captures.append({
                "tick": int(tick),
                "squad": int(payload["squad"]),
                "node": int(payload["node"]),
                "owner_from": int(payload["owner_from"]),
                "owner_to": int(payload["owner_to"]),
            })
        elif step == "battle":
            sid_a = int(payload["squad"])
            sid_b = int(payload["loser"])
            raw_node = int(payload["node"])
            resolved_node = raw_node if raw_node >= 0 else squad_node.get(sid_a, squad_node.get(sid_b, 0))
            battles.append({
                "tick": int(tick),
                "node": resolved_node,
                "on_edge": raw_node < 0,
                "squad_a": sid_a,
                "fac_a": squad_fac.get(sid_a, -1),
                "squad_b": sid_b,
                "fac_b": squad_fac.get(sid_b, -1),
            })
        elif step == "squad_defeated":
            sid = int(payload["squad"])
            squad_alive[sid] = False
            squad_raid_goal.pop(sid, None)
            casualties.append({
                "tick": int(tick),
                "squad": sid,
                "faction": fac_idx[payload["faction"]],
                "node": squad_node.get(sid, 0),
            })

    active_raids = [
        {
            "tick": r_tick,
            "squad": sid,
            "faction": squad_fac[sid],
            "origin_node": origin,
            "target_node": goal,
        }
        for sid, (r_tick, origin, goal) in sorted(squad_raid_goal.items())
        if squad_alive.get(sid, False)
    ]

    by_fac_nodes: dict[int, list[int]] = {i: [] for i in range(f_count)}
    for sid, alive_flag in sorted(squad_alive.items()):
        if alive_flag and sid in squad_fac and sid in squad_node:
            by_fac_nodes[squad_fac[sid]].append(squad_node[sid])

    return WorldStateSnapshot(
        config=norm,
        graph=graph,
        seed=int(sim_result.get("seed", seed)),
        ticks=int(sim_result.get("ticks", ticks)),
        sim_seconds=float(sim_result.get("sim_seconds", ticks * float(norm["simulation"]["tick_real_s"]))),
        initial_owners=initial_owners,
        node_owners=node_owners,
        hostile=hostile,
        faction_ids=fac_ids,
        faction_Index_by_id=fac_idx,
        captures=tuple(captures),
        battles=tuple(battles),
        casualties=tuple(casualties),
        active_raids=tuple(active_raids),
        live_squad_nodes={k: tuple(v) for k, v in by_fac_nodes.items()},
    )


def select_friendly_faction(snapshot: WorldStateSnapshot, friendly_faction: str | int | None = None) -> int:
    """Resolve the faction offering local requests (defaults to ally -> neutral -> index 0)."""
    facs = snapshot.config["factions"]
    if isinstance(friendly_faction, int):
        if 0 <= friendly_faction < len(facs):
            return friendly_faction
        raise ValueError(f"friendly_faction index {friendly_faction} out of range")
    if isinstance(friendly_faction, str):
        if friendly_faction not in snapshot.faction_Index_by_id:
            raise ValueError(f"unknown friendly_faction {friendly_faction!r}")
        return snapshot.faction_Index_by_id[friendly_faction]
    for rel_pref in ("ally", "neutral"):
        for f in facs:
            if f["player_relation"] == rel_pref:
                return int(f["index"])
    return 0


def _giver_nodes_for_faction(snapshot: WorldStateSnapshot, f_idx: int) -> list[int]:
    nodes = snapshot.config["nodes"]
    owned = [
        i for i, o in enumerate(snapshot.node_owners)
        if o == f_idx and nodes[i]["capacity"] > 0
    ]
    if owned:
        return owned
    # If wiped from all owned bases, surviving neutral/unowned non-hostile checkpoints/bases can host refugees/scouts
    fallback = [
        i for i, o in enumerate(snapshot.node_owners)
        if nodes[i]["capacity"] > 0 and (o < 0 or not snapshot.hostile[f_idx][o])
    ]
    return fallback


def _nearest_giver(snapshot: WorldStateSnapshot, giver_nodes: Sequence[int], target_node: int) -> int | None:
    best = None
    best_d = math.inf
    for g_idx in giver_nodes:
        if g_idx == target_node:
            continue
        d = snapshot.graph.dist[g_idx][target_node]
        if not math.isinf(d) and (d < best_d - 1e-9 or (abs(d - best_d) <= 1e-9 and (best is None or g_idx < best))):
            best = g_idx
            best_d = d
    return best


def _build_mission(
    snapshot: WorldStateSnapshot,
    *,
    seq_num: int,
    request_type: str,
    giver_node: int,
    giver_role: str,
    giver_fac: int,
    target_node: int,
    target_fac: int,
    what_tag: str,
    trigger: dict[str, Any],
    consequence_success: dict[str, Any],
    consequence_failure: dict[str, Any],
    secondary_tab: str,
    all_giver_nodes: Sequence[int],
) -> RadiantMission:
    nodes = snapshot.config["nodes"]
    facs = snapshot.config["factions"]
    step_speed = max(0.5, float(snapshot.config["simulation"]["offline_step_m_per_s"]))
    route = tuple(snapshot.graph.route(giver_node, target_node) or ())
    dist_m = round(float(snapshot.graph.dist[giver_node][target_node]), 2)
    risk_power = float(facs[target_fac]["combat_power"]) if target_fac >= 0 else 1.0
    type_base_caps = {
        "fetch_or_rescue": 90,
        "escort_or_deliver": 100,
        "avenge_or_investigate": 120,
        "kill_named_threat": 140,
        "clear_or_retake_node": 175,
    }[request_type]
    reward_caps = int(round((type_base_caps + 0.12 * dist_m) * max(1.0, risk_power), -1))
    reward_fame = 5 if request_type in ("fetch_or_rescue", "escort_or_deliver") else 10
    min_travel_s = dist_m / step_speed
    deadline_s = float(max(300, int(math.ceil((min_travel_s * 4.5 + 180.0) / 60.0) * 60)))

    backup_giver_node = next((n for n in all_giver_nodes if n != giver_node), giver_node)
    deputy_role = "guard" if giver_role != "guard" else "quartermaster"
    giver_died_fallback = {
        "deputy_role": deputy_role,
        "deputy_node_index": backup_giver_node,
        "deputy_node_id": nodes[backup_giver_node]["id"],
        "comms_turnin_tab": "faction_comms",
        "escort_charge_mortal": request_type == "escort_or_deliver",
    }

    giver_fid = facs[giver_fac]["id"]
    target_fid = facs[target_fac]["id"] if target_fac >= 0 else None
    return RadiantMission(
        mission_id=f"rad_s{snapshot.seed}_{seq_num:02d}_{request_type[:6]}",
        seed=snapshot.seed,
        request_type=request_type,
        giver_node_index=giver_node,
        giver_node_id=nodes[giver_node]["id"],
        giver_role=giver_role,
        giver_npc_tag=f"{giver_fid}_{giver_role}_n{giver_node}",
        giver_faction_index=giver_fac,
        giver_faction_id=giver_fid,
        target_node_index=target_node,
        target_node_id=nodes[target_node]["id"],
        target_faction_index=target_fac,
        target_faction_id=target_fid,
        what_tag=what_tag,
        route_nodes=route,
        distance_m=dist_m,
        trigger=trigger,
        reward_caps=max(50, reward_caps),
        reward_fame=reward_fame,
        deadline_s=deadline_s,
        consequence_on_success=consequence_success,
        consequence_on_failure=consequence_failure,
        giver_died_fallback=giver_died_fallback,
        secondary_device_tab=secondary_tab,
        pipboy_quest_list_on_accept=True,
        state="offered",
    )


def generate_missions_from_world_state(
    snapshot: WorldStateSnapshot,
    *,
    friendly_faction: str | int | None = None,
    max_missions: int = DEFAULT_MAX_ACTIVE,
    seed: int | None = None,
    quality_guard: QualityGuard | None = None,
) -> list[RadiantMission]:
    """Generate up to max_missions high-coherence requests grounded in snapshot's world state."""
    if max_missions < 1 or max_missions > MAX_ALLOWED_SLOTS:
        raise ValueError(f"max_missions must be 1..{MAX_ALLOWED_SLOTS}")
    f_idx = select_friendly_faction(snapshot, friendly_faction)
    facs = snapshot.config["factions"]
    if facs[f_idx]["player_relation"] == "enemy":
        return []

    giver_nodes = _giver_nodes_for_faction(snapshot, f_idx)
    if not giver_nodes:
        return []

    guard = quality_guard if quality_guard is not None else QualityGuard()
    rng = random.Random(snapshot.seed if seed is None else seed)
    nodes = snapshot.config["nodes"]
    hostile = snapshot.hostile[f_idx]

    # Collect scored world-state candidates: (base_priority, tie_jitter, builder_args)
    candidates: list[tuple[float, dict[str, Any]]] = []

    # 1. clear_or_retake_node: lost nodes or hostile-captured nodes, then hostile frontline bases/checkpoints/lairs
    captured_by_enemy: dict[int, dict[str, Any]] = {}
    for cap_ev in reversed(snapshot.captures):
        t_node = cap_ev["node"]
        cur_owner = snapshot.node_owners[t_node]
        if cur_owner >= 0 and hostile[cur_owner] and t_node not in captured_by_enemy:
            captured_by_enemy[t_node] = cap_ev

    for t_node, cur_owner in enumerate(snapshot.node_owners):
        if cur_owner < 0 or not hostile[cur_owner] or nodes[t_node]["capacity"] <= 0:
            continue
        g_node = _nearest_giver(snapshot, giver_nodes, t_node)
        if g_node is None:
            continue
        was_ours = snapshot.initial_owners[t_node] == f_idx or (
            t_node in captured_by_enemy and captured_by_enemy[t_node]["owner_from"] == f_idx
        )
        if was_ours or t_node in captured_by_enemy or nodes[t_node]["kind"] in ("base", "checkpoint"):
            cap_ev = captured_by_enemy.get(t_node)
            trig = {
                "kind": "hostile_captured_node" if cap_ev else "hostile_frontline_occupation",
                "tick": cap_ev["tick"] if cap_ev else snapshot.ticks,
                "was_friendly_owned": was_ours,
                "occupying_faction": facs[cur_owner]["id"],
            }
            prio = 95.0 if was_ours else (84.0 if cap_ev else 72.0)
            candidates.append((prio + rng.uniform(0.0, 2.0), {
                "request_type": "clear_or_retake_node",
                "giver_node": g_node,
                "giver_role": "guard",
                "target_node": t_node,
                "target_fac": cur_owner,
                "what_tag": f"retake_{nodes[t_node]['id']}" if was_ours else f"clear_{nodes[t_node]['id']}",
                "trigger": trig,
                "consequence_success": {"api": "SetNodeOwner", "node": t_node, "faction": facs[f_idx]["id"]},
                "consequence_failure": {"api": "OrderRaid", "faction": facs[cur_owner]["id"], "target_node": g_node},
                "secondary_tab": "warfare",
            }))

    # 2. avenge_or_investigate: friendly squad defeated or friendly battle site
    seen_avenge_nodes: set[int] = set()
    for cas in reversed(snapshot.casualties):
        if cas["faction"] != f_idx:
            continue
        t_node = cas["node"]
        if t_node in seen_avenge_nodes or nodes[t_node]["capacity"] <= 0:
            continue
        g_node = _nearest_giver(snapshot, giver_nodes, t_node)
        if g_node is None:
            continue
        seen_avenge_nodes.add(t_node)
        culprit_fac = snapshot.node_owners[t_node]
        if culprit_fac < 0 or not hostile[culprit_fac]:
            # Find hostile faction from battle at same node, or first hostile faction
            culprit_fac = next(
                (
                    b["fac_a"] if b["fac_b"] == f_idx else b["fac_b"]
                    for b in reversed(snapshot.battles)
                    if b["node"] == t_node and (b["fac_a"] == f_idx or b["fac_b"] == f_idx)
                ),
                next((i for i, is_h in enumerate(hostile) if is_h), -1),
            )
        if culprit_fac >= 0 and hostile[culprit_fac]:
            candidates.append((88.0 + rng.uniform(0.0, 2.0), {
                "request_type": "avenge_or_investigate",
                "giver_node": g_node,
                "giver_role": "settler",
                "target_node": t_node,
                "target_fac": culprit_fac,
                "what_tag": f"fallen_squad_{cas['squad']}_tags",
                "trigger": {
                    "kind": "friendly_squad_defeated",
                    "tick": cas["tick"],
                    "lost_squad": cas["squad"],
                    "culprit_faction": facs[culprit_fac]["id"],
                },
                "consequence_success": {"fame_delta": 10, "recover_squad_slot": True},
                "consequence_failure": {"api": "OrderRaid", "faction": facs[culprit_fac]["id"], "target_node": g_node},
                "secondary_tab": "bounties",
            }))

    # Fallback battle investigation if friendly faction suffered 0 full wipeouts but fought a battle
    if not seen_avenge_nodes:
        for bat in reversed(snapshot.battles):
            if bat["fac_a"] != f_idx and bat["fac_b"] != f_idx:
                continue
            other_fac = bat["fac_b"] if bat["fac_a"] == f_idx else bat["fac_a"]
            t_node = bat["node"]
            if other_fac < 0 or not hostile[other_fac] or nodes[t_node]["capacity"] <= 0:
                continue
            g_node = _nearest_giver(snapshot, giver_nodes, t_node)
            if g_node is None:
                continue
            seen_avenge_nodes.add(t_node)
            candidates.append((80.0 + rng.uniform(0.0, 2.0), {
                "request_type": "avenge_or_investigate",
                "giver_node": g_node,
                "giver_role": "guard",
                "target_node": t_node,
                "target_fac": other_fac,
                "what_tag": f"skirmish_casualty_site_s{bat['squad_a']}",
                "trigger": {
                    "kind": "skirmish_casualty_report",
                    "tick": bat["tick"],
                    "hostile_faction": facs[other_fac]["id"],
                },
                "consequence_success": {"fame_delta": 10, "patrol_morale_bonus": True},
                "consequence_failure": {"hostile_patrol_pressure": True},
                "secondary_tab": "bounties",
            }))
            break

    # 3. kill_named_threat: active hostile raid staging node or hostile lair/base boss
    seen_threat_nodes: set[int] = set()
    for raid in snapshot.active_raids:
        rfac = raid["faction"]
        if not hostile[rfac]:
            continue
        t_node = raid["origin_node"]
        if nodes[t_node]["capacity"] <= 0 or t_node in seen_threat_nodes:
            continue
        g_node = _nearest_giver(snapshot, giver_nodes, t_node)
        if g_node is None:
            continue
        seen_threat_nodes.add(t_node)
        candidates.append((86.0 + rng.uniform(0.0, 2.0), {
            "request_type": "kill_named_threat",
            "giver_node": g_node,
            "giver_role": "guard",
            "target_node": t_node,
            "target_fac": rfac,
            "what_tag": f"{facs[rfac]['id']}_raid_warlord_sq{raid['squad']}",
            "trigger": {
                "kind": "active_hostile_raid_order",
                "tick": raid["tick"],
                "raid_squad": raid["squad"],
                "raid_goal_node": raid["target_node"],
            },
            "consequence_success": {"disrupt_raid_squad": raid["squad"], "fame_delta": 10},
            "consequence_failure": {"api": "OrderRaid", "faction": facs[rfac]["id"], "target_node": g_node},
            "secondary_tab": "bounties",
        }))

    for t_node, cur_owner in enumerate(snapshot.node_owners):
        if cur_owner >= 0 and hostile[cur_owner] and t_node not in seen_threat_nodes and nodes[t_node]["capacity"] > 0:
            g_node = _nearest_giver(snapshot, giver_nodes, t_node)
            if g_node is None:
                continue
            seen_threat_nodes.add(t_node)
            candidates.append((76.0 + rng.uniform(0.0, 2.0), {
                "request_type": "kill_named_threat",
                "giver_node": g_node,
                "giver_role": "trader",
                "target_node": t_node,
                "target_fac": cur_owner,
                "what_tag": f"{facs[cur_owner]['id']}_ringleader_n{t_node}",
                "trigger": {
                    "kind": "hostile_garrison_threat",
                    "tick": snapshot.ticks,
                    "hostile_faction": facs[cur_owner]["id"],
                },
                "consequence_success": {"weaken_garrison_node": t_node, "fame_delta": 10},
                "consequence_failure": {"caravan_ambush_risk_up": True},
                "secondary_tab": "bounties",
            }))

    # 4. fetch_or_rescue: resource node salvage or post-battle stranded scout rescue
    for t_node, n_info in enumerate(nodes):
        if n_info["capacity"] <= 0:
            continue
        cur_owner = snapshot.node_owners[t_node]
        if cur_owner == f_idx:
            continue
        if n_info["kind"] in ("resource", "lair"):
            g_node = _nearest_giver(snapshot, giver_nodes, t_node)
            if g_node is None:
                continue
            is_rescue = cur_owner >= 0 and hostile[cur_owner] and any(b["node"] == t_node for b in snapshot.battles)
            t_fac = cur_owner if (cur_owner >= 0 and hostile[cur_owner]) else -1
            candidates.append(((82.0 if is_rescue else 74.0) + rng.uniform(0.0, 2.0), {
                "request_type": "fetch_or_rescue",
                "giver_node": g_node,
                "giver_role": "settler",
                "target_node": t_node,
                "target_fac": t_fac,
                "what_tag": f"captured_scout_at_{n_info['id']}" if is_rescue else f"salvage_cache_at_{n_info['id']}",
                "trigger": {
                    "kind": "captured_scout_after_battle" if is_rescue else "settlement_resource_need",
                    "tick": snapshot.ticks,
                    "node_kind": n_info["kind"],
                },
                "consequence_success": {"api": "SpawnSquadAtNode", "faction": facs[f_idx]["id"], "node": g_node},
                "consequence_failure": {"garrison_supply_shortage": g_node},
                "secondary_tab": "settlements",
            }))

    # 5. escort_or_deliver: verified non-hostile corridor between two distinct friendly/unowned nodes
    safe_dests = [
        i for i, cur_owner in enumerate(snapshot.node_owners)
        if nodes[i]["capacity"] > 0 and (cur_owner < 0 or not hostile[cur_owner])
    ]
    for g_node in giver_nodes:
        for d_node in safe_dests:
            if d_node == g_node or math.isinf(snapshot.graph.dist[g_node][d_node]):
                continue
            dest_owner = snapshot.node_owners[d_node]
            is_allied_pair = dest_owner == f_idx
            candidates.append(((79.0 if is_allied_pair else 70.0) + rng.uniform(0.0, 2.0), {
                "request_type": "escort_or_deliver",
                "giver_node": g_node,
                "giver_role": "trader",
                "target_node": d_node,
                "target_fac": dest_owner if dest_owner >= 0 else f_idx,
                "what_tag": f"medical_and_ammo_convoy_to_{nodes[d_node]['id']}",
                "trigger": {
                    "kind": "allied_supply_corridor" if is_allied_pair else "frontier_outpost_relief",
                    "tick": snapshot.ticks,
                    "destination_owner": facs[dest_owner]["id"] if dest_owner >= 0 else None,
                },
                "consequence_success": {"api": "SpawnSquadAtNode", "faction": facs[f_idx]["id"], "node": d_node},
                "consequence_failure": {"supply_convoy_lost": True},
                "secondary_tab": "settlements",
            }))

    selected: list[RadiantMission] = []
    batch_targets: set[int] = set()
    batch_types: set[str] = set()
    remaining = list(candidates)

    while len(selected) < max_missions and remaining:
        best_idx = -1
        best_score = -math.inf
        for idx, (base_prio, spec) in enumerate(remaining):
            if not guard.allows(spec["request_type"], spec["target_node"], batch_targets):
                continue
            score = base_prio + guard.novelty_bonus(spec["request_type"], spec["target_node"], batch_types)
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx < 0:
            break
        _, chosen = remaining.pop(best_idx)
        mission = _build_mission(
            snapshot,
            seq_num=len(selected) + 1,
            request_type=chosen["request_type"],
            giver_node=chosen["giver_node"],
            giver_role=chosen["giver_role"],
            giver_fac=f_idx,
            target_node=chosen["target_node"],
            target_fac=chosen["target_fac"],
            what_tag=chosen["what_tag"],
            trigger=chosen["trigger"],
            consequence_success=chosen["consequence_success"],
            consequence_failure=chosen["consequence_failure"],
            secondary_tab=chosen["secondary_tab"],
            all_giver_nodes=giver_nodes,
        )
        ok, _ = verify_mission_completable(mission, snapshot)
        if ok:
            selected.append(mission)
            batch_targets.add(mission.target_node_index)
            batch_types.add(mission.request_type)
            guard.record(mission)

    return selected


def verify_mission_completable(mission: RadiantMission, snapshot: WorldStateSnapshot) -> tuple[bool, list[str]]:
    """Verify graph reachability, faction coherence, deadlines, UI routing, and W7 dead-giver safety."""
    problems: list[str] = []
    nodes = snapshot.config["nodes"]
    facs = snapshot.config["factions"]
    n_count = len(nodes)
    f_count = len(facs)

    if mission.request_type not in REQUEST_TYPES:
        problems.append(f"invalid request_type {mission.request_type!r}")
    if mission.giver_role not in GIVER_ROLES:
        problems.append(f"invalid giver_role {mission.giver_role!r}")

    g_idx = mission.giver_node_index
    t_idx = mission.target_node_index
    if not (0 <= g_idx < n_count):
        problems.append(f"giver_node_index {g_idx} out of range")
    if not (0 <= t_idx < n_count):
        problems.append(f"target_node_index {t_idx} out of range")
    if g_idx == t_idx:
        problems.append("giver_node_index equals target_node_index (self-loop request)")

    if problems:
        return False, problems

    if nodes[g_idx]["capacity"] <= 0:
        problems.append(f"giver node {g_idx} has zero capacity")
    if nodes[t_idx]["capacity"] <= 0:
        problems.append(f"target node {t_idx} has zero capacity")

    expected_route = snapshot.graph.route(g_idx, t_idx)
    if not expected_route or len(expected_route) < 2:
        problems.append(f"target node {t_idx} unreachable from giver node {g_idx}")
    elif tuple(expected_route) != tuple(mission.route_nodes):
        problems.append("route_nodes does not match shortest graph route")

    dist = snapshot.graph.dist[g_idx][t_idx]
    if math.isinf(dist) or dist <= 0.0:
        problems.append(f"invalid route distance {dist}")

    gf = mission.giver_faction_index
    tf = mission.target_faction_index
    if not (0 <= gf < f_count):
        problems.append(f"invalid giver_faction_index {gf}")
    else:
        if facs[gf]["player_relation"] == "enemy":
            problems.append("enemy faction cannot offer standard friendly area requests")
        giver_owner = snapshot.node_owners[g_idx]
        if giver_owner >= 0 and snapshot.hostile[gf][giver_owner]:
            problems.append("giver node is currently occupied by a faction hostile to giver")

        if mission.request_type in ("kill_named_threat", "clear_or_retake_node", "avenge_or_investigate"):
            if not (0 <= tf < f_count) or not snapshot.hostile[gf][tf]:
                problems.append(f"{mission.request_type} requires a hostile target faction")
        elif mission.request_type == "escort_or_deliver":
            dest_owner = snapshot.node_owners[t_idx]
            if dest_owner >= 0 and snapshot.hostile[gf][dest_owner]:
                problems.append("escort_or_deliver destination is occupied by a hostile faction")
            if 0 <= tf < f_count and snapshot.hostile[gf][tf]:
                problems.append("escort_or_deliver recipient faction is hostile to giver")
        elif mission.request_type == "fetch_or_rescue":
            if tf >= 0 and (tf >= f_count or not snapshot.hostile[gf][tf]):
                problems.append("fetch_or_rescue contested target faction must be hostile or -1")

    if not mission.trigger or not mission.trigger.get("kind"):
        problems.append("missing world-state trigger metadata")

    step_speed = max(0.5, float(snapshot.config["simulation"]["offline_step_m_per_s"]))
    if not math.isinf(dist) and mission.deadline_s < (dist / step_speed) * 2.5:
        problems.append("deadline_s too short for graph travel distance")
    if mission.reward_caps <= 0 or mission.reward_fame <= 0:
        problems.append("non-positive reward values")

    fb = mission.giver_died_fallback
    if not fb or not fb.get("deputy_role") or fb.get("comms_turnin_tab") != "faction_comms":
        problems.append("missing W7 giver_died_fallback deputy or faction_comms turn-in")

    if mission.secondary_device_tab not in ("bounties", "settlements", "warfare", "faction_comms"):
        problems.append(f"invalid secondary_device_tab {mission.secondary_device_tab!r}")
    if not mission.pipboy_quest_list_on_accept:
        problems.append("accepted requests must appear in the quest list")

    return len(problems) == 0, problems


def resolve_mission_outcome(
    mission: RadiantMission,
    *,
    objective_done: bool,
    giver_alive: bool = True,
    deputy_alive: bool = True,
    escort_alive: bool = True,
    cleared_by_alife_ally: bool = False,
    elapsed_s: float = 0.0,
) -> tuple[RadiantMission, dict[str, Any]]:
    """Resolve turn-in, expiration, ally pre-clear, or W7 giver-death without stranding the quest."""
    if mission.request_type == "escort_or_deliver" and not escort_alive:
        updated = RadiantMission(**{**mission.__dict__, "state": "failed_with_consequence"})
        return updated, {
            "terminal": True,
            "outcome": "failed_with_consequence",
            "reason": "escort_charge_died",
            "world_effect": dict(mission.consequence_on_failure),
            "reward_caps": 0,
        }

    if elapsed_s > mission.deadline_s and not objective_done and not cleared_by_alife_ally:
        updated = RadiantMission(**{**mission.__dict__, "state": "expired_with_consequence"})
        return updated, {
            "terminal": True,
            "outcome": "expired_with_consequence",
            "reason": "deadline_exceeded",
            "world_effect": dict(mission.consequence_on_failure),
            "reward_caps": 0,
        }

    if cleared_by_alife_ally and not objective_done:
        half_caps = max(25, mission.reward_caps // 2)
        updated = RadiantMission(**{**mission.__dict__, "state": "resolved_by_alife_ally"})
        return updated, {
            "terminal": True,
            "outcome": "resolved_by_alife_ally",
            "reason": "target_resolved_by_friendly_alife_squad",
            "world_effect": dict(mission.consequence_on_success),
            "reward_caps": half_caps if (giver_alive or deputy_alive) else half_caps,
        }

    if not objective_done:
        updated = RadiantMission(**{**mission.__dict__, "state": "active"})
        return updated, {"terminal": False, "outcome": "active", "reason": "in_progress", "reward_caps": 0}

    if giver_alive:
        new_state = "completed"
        turnin_channel = f"npc:{mission.giver_npc_tag}"
    elif deputy_alive:
        new_state = "completed_via_deputy"
        turnin_channel = f"deputy:{mission.giver_died_fallback['deputy_role']}@{mission.giver_died_fallback['deputy_node_id']}"
    else:
        new_state = "completed_via_comms"
        turnin_channel = f"device:{mission.giver_died_fallback['comms_turnin_tab']}"

    updated = RadiantMission(**{**mission.__dict__, "state": new_state})
    return updated, {
        "terminal": True,
        "outcome": new_state,
        "turnin_channel": turnin_channel,
        "world_effect": dict(mission.consequence_on_success),
        "reward_caps": mission.reward_caps,
    }


class MissionBoardState:
    """Active request tracker enforcing the slot cap and flat-array save/reload serialization."""

    def __init__(self, max_active: int = DEFAULT_MAX_ACTIVE) -> None:
        if max_active < 1 or max_active > MAX_ALLOWED_SLOTS:
            raise ValueError(f"max_active must be 1..{MAX_ALLOWED_SLOTS}")
        self.max_active = max_active
        self.slots: list[RadiantMission | None] = [None] * max_active

    def active_missions(self) -> list[RadiantMission]:
        return [m for m in self.slots if m is not None and m.state not in TERMINAL_STATES]

    def accept(self, mission: RadiantMission) -> int:
        if any(m is not None and m.mission_id == mission.mission_id for m in self.slots):
            raise ValueError(f"mission {mission.mission_id!r} is already in a slot")
        for idx, cur in enumerate(self.slots):
            if cur is None or cur.state in TERMINAL_STATES:
                self.slots[idx] = RadiantMission(**{**mission.__dict__, "state": "active"})
                return idx
        raise ValueError(f"active radiant mission cap ({self.max_active}) reached")

    def resolve_slot(self, slot_index: int, **kwargs: Any) -> dict[str, Any]:
        cur = self.slots[slot_index]
        if cur is None:
            raise ValueError(f"slot {slot_index} is empty")
        updated, receipt = resolve_mission_outcome(cur, **kwargs)
        self.slots[slot_index] = updated
        if receipt["terminal"]:
            self.slots[slot_index] = None
        return receipt

    def to_papyrus_arrays(self) -> dict[str, list[Any]]:
        """Serialize active slots to parallel primitive arrays (matching Papyrus <=128 array limits)."""
        state_idx = {name: i for i, name in enumerate(MISSION_STATES)}
        type_idx = {name: i for i, name in enumerate(REQUEST_TYPES)}
        role_idx = {name: i for i, name in enumerate(GIVER_ROLES)}
        tab_idx = {name: i for i, name in enumerate(SECONDARY_DEVICE_TABS)}

        arrays: dict[str, list[Any]] = {
            "max_active": [self.max_active],
            "slot_occupied": [],
            "slot_state": [],
            "slot_type": [],
            "slot_role": [],
            "slot_tab": [],
            "slot_seed": [],
            "slot_giver_node": [],
            "slot_target_node": [],
            "slot_giver_fac": [],
            "slot_target_fac": [],
            "slot_reward_caps": [],
            "slot_reward_fame": [],
            "slot_deadline_s": [],
            "slot_distance_m": [],
            "slot_id": [],
            "slot_what": [],
            "slot_trigger_kind": [],
        }
        for m in self.slots:
            if m is None:
                arrays["slot_occupied"].append(0)
                for k in (
                    "slot_state", "slot_type", "slot_role", "slot_tab", "slot_seed",
                    "slot_giver_node", "slot_target_node", "slot_giver_fac",
                    "slot_target_fac", "slot_reward_caps", "slot_reward_fame",
                ):
                    arrays[k].append(-1)
                arrays["slot_deadline_s"].append(0.0)
                arrays["slot_distance_m"].append(0.0)
                arrays["slot_id"].append("")
                arrays["slot_what"].append("")
                arrays["slot_trigger_kind"].append("")
            else:
                arrays["slot_occupied"].append(1)
                arrays["slot_state"].append(state_idx[m.state])
                arrays["slot_type"].append(type_idx[m.request_type])
                arrays["slot_role"].append(role_idx[m.giver_role])
                arrays["slot_tab"].append(tab_idx[m.secondary_device_tab])
                arrays["slot_seed"].append(m.seed)
                arrays["slot_giver_node"].append(m.giver_node_index)
                arrays["slot_target_node"].append(m.target_node_index)
                arrays["slot_giver_fac"].append(m.giver_faction_index)
                arrays["slot_target_fac"].append(m.target_faction_index)
                arrays["slot_reward_caps"].append(m.reward_caps)
                arrays["slot_reward_fame"].append(m.reward_fame)
                arrays["slot_deadline_s"].append(float(m.deadline_s))
                arrays["slot_distance_m"].append(float(m.distance_m))
                arrays["slot_id"].append(m.mission_id)
                arrays["slot_what"].append(m.what_tag)
                arrays["slot_trigger_kind"].append(str(m.trigger.get("kind", "restored")))

        for k, vals in arrays.items():
            if len(vals) > PAPYRUS_ARRAY_LIMIT:
                raise ValueError(f"serialized array {k!r} length {len(vals)} exceeds {PAPYRUS_ARRAY_LIMIT}")
        return arrays

    @classmethod
    def from_papyrus_arrays(cls, arrays: Mapping[str, Sequence[Any]], snapshot: WorldStateSnapshot) -> "MissionBoardState":
        max_active = int(arrays["max_active"][0])
        board = cls(max_active=max_active)
        nodes = snapshot.config["nodes"]
        facs = snapshot.config["factions"]
        for i in range(max_active):
            if int(arrays["slot_occupied"][i]) == 0:
                board.slots[i] = None
                continue
            g_node = int(arrays["slot_giver_node"][i])
            t_node = int(arrays["slot_target_node"][i])
            g_fac = int(arrays["slot_giver_fac"][i])
            t_fac = int(arrays["slot_target_fac"][i])
            rtype = REQUEST_TYPES[int(arrays["slot_type"][i])]
            grole = GIVER_ROLES[int(arrays["slot_role"][i])]
            stab = SECONDARY_DEVICE_TABS[int(arrays["slot_tab"][i])]
            mstate = MISSION_STATES[int(arrays["slot_state"][i])]
            giver_nodes = _giver_nodes_for_faction(snapshot, g_fac)
            rebuilt = _build_mission(
                snapshot,
                seq_num=i + 1,
                request_type=rtype,
                giver_node=g_node,
                giver_role=grole,
                giver_fac=g_fac,
                target_node=t_node,
                target_fac=t_fac,
                what_tag=str(arrays["slot_what"][i]),
                trigger={"kind": str(arrays["slot_trigger_kind"][i]), "tick": snapshot.ticks},
                consequence_success={"fame_delta": int(arrays["slot_reward_fame"][i])},
                consequence_failure={"restored_penalty": True},
                secondary_tab=stab,
                all_giver_nodes=giver_nodes or [g_node],
            )
            board.slots[i] = RadiantMission(
                **{
                    **rebuilt.__dict__,
                    "mission_id": str(arrays["slot_id"][i]),
                    "seed": int(arrays["slot_seed"][i]),
                    "reward_caps": int(arrays["slot_reward_caps"][i]),
                    "reward_fame": int(arrays["slot_reward_fame"][i]),
                    "deadline_s": float(arrays["slot_deadline_s"][i]),
                    "distance_m": float(arrays["slot_distance_m"][i]),
                    "giver_node_id": nodes[g_node]["id"],
                    "target_node_id": nodes[t_node]["id"],
                    "giver_faction_id": facs[g_fac]["id"],
                    "target_faction_id": facs[t_fac]["id"] if t_fac >= 0 else None,
                    "state": mstate,
                }
            )
        return board


def run_multi_seed_verification(
    cfg: Mapping[str, Any] | str,
    *,
    num_seeds: int = 25,
    start_seed: int = 1,
    ticks: int = 600,
    max_per_seed: int = DEFAULT_MAX_ACTIVE,
    friendly_faction: str | int | None = None,
) -> dict[str, Any]:
    """Run A-Life simulation + mission generation over >= 20 seeds and verify 100% completability."""
    if num_seeds < 20:
        raise ValueError("num_seeds must be >= 20 per Round 9 X9 verification rule")
    if isinstance(cfg, str):
        cfg = schema.load_alife_config(cfg)
    norm = schema.checked(cfg)

    guard = QualityGuard(cooldown_window=DEFAULT_COOLDOWN_HISTORY)
    type_counts: dict[str, int] = {t: 0 for t in REQUEST_TYPES}
    tab_counts: dict[str, int] = {}
    trigger_counts: dict[str, int] = {}
    target_nodes_seen: set[int] = set()
    sample_missions: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    total_generated = 0

    for offset in range(num_seeds):
        s = start_seed + offset
        snap = snapshot_from_simulation(norm, ticks=ticks, seed=s)
        batch = generate_missions_from_world_state(
            snap,
            friendly_faction=friendly_faction,
            max_missions=max_per_seed,
            seed=s,
            quality_guard=guard,
        )
        for m in batch:
            total_generated += 1
            ok, probs = verify_mission_completable(m, snap)
            if not ok:
                failures.append({"seed": s, "mission_id": m.mission_id, "problems": probs})
            type_counts[m.request_type] += 1
            tab_counts[m.secondary_device_tab] = tab_counts.get(m.secondary_device_tab, 0) + 1
            tk = str(m.trigger["kind"])
            trigger_counts[tk] = trigger_counts.get(tk, 0) + 1
            target_nodes_seen.add(m.target_node_index)
            if len(sample_missions) < 10:
                sample_missions.append({
                    "seed": s,
                    "mission_id": m.mission_id,
                    "request_type": m.request_type,
                    "giver": f"{m.giver_role}@{m.giver_node_id} ({m.giver_faction_id})",
                    "target": f"{m.target_node_id} ({m.target_faction_id or 'unowned'})",
                    "what": m.what_tag,
                    "trigger": m.trigger["kind"],
                    "distance_m": m.distance_m,
                    "hops": len(m.route_nodes) - 1,
                    "reward_caps": m.reward_caps,
                    "deadline_s": m.deadline_s,
                    "device_tab": m.secondary_device_tab,
                    "dead_giver_fallback": f"{m.giver_died_fallback['deputy_role']} -> {m.giver_died_fallback['comms_turnin_tab']}",
                })

    return {
        "mod_name": norm["mod_name"],
        "num_seeds": num_seeds,
        "ticks_per_seed": ticks,
        "total_missions_generated": total_generated,
        "completable_missions": total_generated - len(failures),
        "all_completable": len(failures) == 0 and total_generated > 0,
        "failures": failures,
        "by_request_type": type_counts,
        "by_secondary_device_tab": tab_counts,
        "by_trigger": trigger_counts,
        "unique_target_nodes": len(target_nodes_seen),
        "sample_missions": sample_missions,
    }
