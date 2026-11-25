"""Offline simulation & contract model for Concord DN092 Wave 2, Deathclaw ambush, S7 roof & S9 walk home.

Mirrors the Papyrus runtime logic in `FO4SF_Min00Quest.psc` and the Mutagen builder constants in
`NextStoryMissionsS7S9.cs` so `respawnPool=8`, permanent boss non-respawn (`Gristle` & `RoofLookout`),
3-trigger Deathclaw spawning (`wave_kills | grate_proximity | timer_300s`), `deathclaw_slot=empty`,
and S9 never-teleport-in-view failsafe behavior are unit-tested deterministically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Dict, List, Optional, Sequence, Tuple

Vec3 = Tuple[float, float, float]

# Verified Fallout4.esm DN092 & Concord positions (meters in merged Commonwealth)
S7_ROOF_DOOR_POS: Vec3 = (-1990.58, -1724.19, 97.56)
S7_ROOF_FRAME_POS: Vec3 = (-1995.73, -1723.10, 97.54)
S7_ROOF_MINIGUN_POS: Vec3 = (-2004.72, -1715.40, 102.68)

DN092_START_STAGE = 75
DN092_SPAWN_STAGE = 77
DN092_DONE_STAGE = 79
DN092_RESPAWN_POOL = 8
DN092_WAVE_KILL_TARGET = 8
DN092_GRATE_RADIUS_M = 17.0
DN092_TIMER_LIMIT_S = 300.0
MIN_SPAWNER_DIST_M = 18.0
S9_NEVER_TELEPORT_VIEW_DIST_M = 65.0

GRATE_TRIGGER_POS: Vec3 = (-2068.22, -1640.23, 88.22)  # DN092ForceSpawnDeathclawTrigger 0009A144
DEATHCLAW_SPAWN_POS: Vec3 = (-2068.22, -1640.18, 88.22)  # ConcordAmbushDeathclaw 0001F15B
DEATHCLAW_FO4_BASE_ID = 0x0002C969  # DN092AmbushDeathclaw
DEATHCLAW_FO4_REF_ID = 0x0001F15B  # ConcordAmbushDeathclaw
DEATHCLAW_STATS: Dict[str, int] = {
    "health": 615,
    "dr": 100,
    "er": 150,
    "claw_damage": 60,
}

S9_LOBBY_PRESTON_POS: Vec3 = (-10.26, 3.60, 0.07)   # MQ102PrestonTravelMarker4 0001F5B6 in ConcordMuseum01
S9_LOBBY_MURPHY_POS: Vec3 = (-8.63, 2.62, 0.04)     # MQ102MamaMurphyTravelMarker4 0001F5B7 in ConcordMuseum01


@dataclass(frozen=True)
class WaveActorSpec:
    alias: str
    fo4_base_id: int
    fo4_marker_id: int
    pos: Vec3
    respawns: bool


WAVE_ALIASES: Tuple[WaveActorSpec, ...] = (
    WaveActorSpec("WaveRaider01", 0x000CE987, 0x00023F0B, (-2050.79, -1675.63, 88.40), True),
    WaveActorSpec("WaveRaider02", 0x000CE987, 0x0001F15D, (-2055.43, -1646.49, 91.59), True),
    WaveActorSpec("WaveRaider03", 0x0007B620, 0x0002C96B, (-2066.37, -1642.37, 88.17), True),
    WaveActorSpec("RoofLookout", 0x000CE987, 0x00023EFA, (-2042.53, -1690.99, 101.09), False),
    WaveActorSpec("Gristle", 0x00019567, 0x0002C96B, (-2066.37, -1642.37, 88.17), False),
)

WAVE_SPAWNERS: Tuple[Tuple[int, Vec3], ...] = (
    (0x00029BCD, (-2109.40, -1635.39, 88.27)),  # DN092WaveSpawner01
    (0x0002C987, (-2058.78, -1601.50, 88.65)),  # DN092WaveSpawner02
    (0x0003D241, (-2044.53, -1634.66, 88.59)),  # DN092WaveSpawner03
    (0x0002C988, (-2054.62, -1613.32, 88.15)),  # DN092WaveSpawner04
    (0x0002C989, (-2093.62, -1668.45, 88.55)),  # DN092WaveSpawner05
    (0x0003D242, (-2094.59, -1654.38, 88.47)),  # DN092WaveSpawner06
)

WAVE_FAILSAFE_SPAWNER: Tuple[int, Vec3] = (0x00023BC5, (-2055.35, -1646.86, 91.63))  # DN092_WavePost02


@dataclass
class WaveMemberState:
    spec: WaveActorSpec
    pos: Vec3
    alive: bool = True
    permanently_dead: bool = False
    respawn_count: int = 0


@dataclass
class DN092WaveController:
    """State machine matching `FO4SF_Min00Quest.psc` DN092 Wave 2 + Deathclaw rules."""

    respawn_pool: int = DN092_RESPAWN_POOL
    dn092_stage: int = DN092_START_STAGE
    wave_kills: int = 0
    elapsed_sec: float = 0.0
    creature_slot_available: bool = False
    deathclaw_spawned: bool = False
    deathclaw_trigger: Optional[str] = None
    deathclaw_slot_status: Optional[str] = None
    deathclaw_alive: bool = False
    next_spawner_cursor: int = 0
    members: Dict[str, WaveMemberState] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.members:
            for sp in WAVE_ALIASES:
                self.members[sp.alias] = WaveMemberState(spec=sp, pos=sp.pos)

    def pick_spawner(self, player_pos: Vec3) -> Tuple[str, Vec3]:
        """Select a spawner >= 18 m from `player_pos`, falling back to DN092_WavePost02 (00023BC5)."""
        n = len(WAVE_SPAWNERS)
        for offset in range(n):
            idx = (self.next_spawner_cursor + offset) % n
            fid, pos = WAVE_SPAWNERS[idx]
            if math.dist(player_pos, pos) >= MIN_SPAWNER_DIST_M:
                self.next_spawner_cursor = (idx + 1) % n
                return (f"WaveSpawner0{idx + 1}:0x{fid:06X}", pos)
        fid, pos = WAVE_FAILSAFE_SPAWNER
        return (f"failsafe_WavePost02:0x{fid:06X}", pos)

    def on_member_killed(self, alias: str, player_pos: Vec3) -> Optional[str]:
        """Handle death of a wave alias. Respawns ONLY WaveRaider01..03 while pool>0 and stage in [75, 79)."""
        m = self.members[alias]
        if not m.alive:
            return None
        m.alive = False
        self.wave_kills += 1

        if not m.spec.respawns:
            m.permanently_dead = True
            self.logs.append(f"s8 wave kill alias={alias} respawns=false wave_kills={self.wave_kills}")
        elif self.respawn_pool > 0 and DN092_START_STAGE <= self.dn092_stage < DN092_DONE_STAGE:
            self.respawn_pool -= 1
            sp_label, sp_pos = self.pick_spawner(player_pos)
            m.alive = True
            m.pos = sp_pos
            m.respawn_count += 1
            self.logs.append(
                f"s8 wave respawn alias={alias} pool_left={self.respawn_pool} wave_kills={self.wave_kills} spawner={sp_label}"
            )
        else:
            m.permanently_dead = True
            self.logs.append(f"s8 wave kill alias={alias} pool_left={self.respawn_pool} wave_kills={self.wave_kills}")

        return self.evaluate_deathclaw_triggers(player_pos, dt=0.0)

    def evaluate_deathclaw_triggers(self, player_pos: Vec3, dt: float = 0.0) -> Optional[str]:
        """Evaluate first-of (8 wave_kills | <=17m grate_proximity | 300s timer) -> stage 77 spawn, stage 79 on clear/300s."""
        if dt > 0.0:
            self.elapsed_sec += dt
        if self.deathclaw_spawned:
            if (
                not self.creature_slot_available
                and self.dn092_stage < DN092_DONE_STAGE
                and self.elapsed_sec >= DN092_TIMER_LIMIT_S
            ):
                self.dn092_stage = DN092_DONE_STAGE
                self.deathclaw_alive = False
                self.logs.append(f"s8 deathclaw timer_300s_complete deathclaw_slot=empty dn092_stage={self.dn092_stage}")
            return self.deathclaw_trigger

        trigger: Optional[str] = None
        if self.wave_kills >= DN092_WAVE_KILL_TARGET:
            trigger = "wave_kills"
        elif math.dist(player_pos, GRATE_TRIGGER_POS) <= DN092_GRATE_RADIUS_M:
            trigger = "grate_proximity"
        elif self.elapsed_sec >= DN092_TIMER_LIMIT_S:
            trigger = "timer_300s"

        if trigger is None:
            return None

        self.deathclaw_spawned = True
        self.deathclaw_trigger = trigger
        self.dn092_stage = DN092_SPAWN_STAGE
        self.logs.append(f"s8 deathclaw spawn trigger={trigger} dn092_stage={self.dn092_stage}")
        if self.creature_slot_available:
            self.deathclaw_slot_status = "bound"
            self.deathclaw_alive = True
            self.logs.append(
                f"s8 deathclaw creature_slot=bound hp={DEATHCLAW_STATS['health']} "
                f"dr={DEATHCLAW_STATS['dr']} er={DEATHCLAW_STATS['er']} claw={DEATHCLAW_STATS['claw_damage']}"
            )
        else:
            self.deathclaw_slot_status = "empty"
            self.deathclaw_alive = False
            if trigger == "timer_300s":
                self.dn092_stage = DN092_DONE_STAGE
                self.logs.append(f"s8 deathclaw deathclaw_slot=empty dn092_stage={self.dn092_stage}")
            else:
                self.logs.append(f"s8 deathclaw deathclaw_slot=empty dn092_stage={self.dn092_stage}")
        return trigger

    def on_deathclaw_killed(self) -> None:
        self.deathclaw_alive = False
        self.dn092_stage = DN092_DONE_STAGE
        self.logs.append("s8 deathclaw defeated dn092_stage=79")

    @property
    def is_wave_cleared(self) -> bool:
        return (
            self.deathclaw_spawned
            and self.dn092_stage >= DN092_DONE_STAGE
            and not self.deathclaw_alive
            and all(not m.alive for m in self.members.values())
        )


def s9_failsafe_can_teleport(
    *,
    player_dist_to_preston: float,
    preston_dist_to_sanctuary: float,
    preston_3d_loaded: bool,
    player_in_sanctuary: bool,
    patrol_elapsed_sec: float,
    failsafe_sec: float = 180.0,
    min_offscreen_dist: float = S9_NEVER_TELEPORT_VIEW_DIST_M,
    sanctuary_far_dist: float = 150.0,
    patrol_deployed: bool = True,
    group_members: Sequence[Tuple[bool, float]] = (),
) -> bool:
    """Guarantee S9 keeper failsafe waits for outdoor deployment and NEVER teleports Preston or group in close view."""
    if not patrol_deployed:
        return False
    wants_failsafe = (patrol_elapsed_sec >= failsafe_sec) or (
        player_in_sanctuary and preston_dist_to_sanctuary > sanctuary_far_dist
    )
    if not wants_failsafe:
        return False
    if preston_3d_loaded and player_dist_to_preston < min_offscreen_dist:
        return False
    for gm_loaded, gm_dist in group_members:
        if gm_loaded and gm_dist < min_offscreen_dist:
            return False
    return True
