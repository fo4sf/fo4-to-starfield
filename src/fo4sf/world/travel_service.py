"""Multi-world travel-service contract, pending-trip state machine, and D1-D6 validation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

WORLD_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "core" / "world_registry.json"

DEFAULT_RELOAD_RECOVERY = "finish_if_dest_ready_else_abort_clear (recommended default; pending owner decision)"


class TravelState(IntEnum):
    """Persistent state machine phases stored in travel globals before/during/after fade."""

    IDLE = 0
    PENDING_WRITE = 1
    FADING_OUT = 2
    MOVING = 3
    WAITING_3D = 4
    ARRIVED = 5
    RECOVERED_FROM_RELOAD = 6
    CLEARED = 7
    FAILED = -1


class TravelMode(IntEnum):
    """Arrival transport mechanism evaluated by the travel service."""

    MOVETO_SETPOS = 0
    GAME_FAST_TRAVEL = 1
    TRANSIT_INTERIOR = 2


ALLOWED_TRANSITIONS: Mapping[TravelState, frozenset[TravelState]] = {
    TravelState.IDLE: frozenset({TravelState.PENDING_WRITE}),
    TravelState.PENDING_WRITE: frozenset({TravelState.FADING_OUT, TravelState.RECOVERED_FROM_RELOAD, TravelState.FAILED}),
    TravelState.FADING_OUT: frozenset({TravelState.MOVING, TravelState.RECOVERED_FROM_RELOAD, TravelState.FAILED}),
    TravelState.MOVING: frozenset({TravelState.WAITING_3D, TravelState.RECOVERED_FROM_RELOAD, TravelState.FAILED}),
    TravelState.WAITING_3D: frozenset({TravelState.ARRIVED, TravelState.RECOVERED_FROM_RELOAD, TravelState.FAILED}),
    TravelState.ARRIVED: frozenset({TravelState.CLEARED}),
    TravelState.RECOVERED_FROM_RELOAD: frozenset({TravelState.WAITING_3D, TravelState.CLEARED, TravelState.FAILED}),
    TravelState.CLEARED: frozenset({TravelState.IDLE, TravelState.PENDING_WRITE}),
    TravelState.FAILED: frozenset({TravelState.CLEARED, TravelState.IDLE}),
}


class TravelTransitionError(ValueError):
    """Raised on an invalid pending-trip transition or contract violation."""


@dataclass
class PendingTripRecord:
    """Single active cross-world or intra-world trip record written BEFORE FadeOutGame.

    The SFSE UI/menu layer resolves map markers and passes metadata to Papyrus; Papyrus owns
    the single-trip lock, pending-record persistence in save GLOBs, FadeOutGame, MoveTo /
    WaitFor3DLoad / SetPosition / SetAngle, SQ_FollowersScript handoff, and post-arrival clear.
    """

    seq: int = 0
    source_world: str = ""
    dest_world: str = ""
    source_plugin_code: int = 0
    dest_plugin_code: int = 0
    mode: TravelMode = TravelMode.MOVETO_SETPOS
    target_x: float = 0.0
    target_y: float = 0.0
    target_z: float = 0.0
    target_angle_z: float = 0.0
    transit_hop: bool = False
    state: TravelState = TravelState.IDLE
    follower_synced: bool = False
    carried_items_preserved: bool = False
    elapsed_real_s: float = 0.0

    def transition(self, nxt: TravelState) -> "PendingTripRecord":
        """Advance to `nxt`, enforcing the state machine and preserving single-trip safety."""
        allowed = ALLOWED_TRANSITIONS.get(self.state, frozenset())
        if nxt not in allowed:
            raise TravelTransitionError(f"illegal transition {self.state.name} -> {nxt.name}")
        self.state = nxt
        return self

    def begin(
        self,
        seq: int,
        source_world: str,
        dest_world: str,
        source_plugin_code: int,
        dest_plugin_code: int,
        *,
        mode: TravelMode = TravelMode.MOVETO_SETPOS,
        target_x: float = 0.0,
        target_y: float = 0.0,
        target_z: float = 0.0,
        target_angle_z: float = 0.0,
        transit_hop: bool = False,
    ) -> "PendingTripRecord":
        """Write pending trip fields BEFORE FadeOutGame (D5: single active trip lock)."""
        if self.state not in (TravelState.IDLE, TravelState.CLEARED):
            raise TravelTransitionError(
                f"cannot begin trip seq={seq}: active trip seq={self.seq} is in state {self.state.name}"
            )
        if not dest_world:
            raise TravelTransitionError("dest_world must be non-empty")
        self.seq = seq
        self.source_world = source_world
        self.dest_world = dest_world
        self.source_plugin_code = source_plugin_code
        self.dest_plugin_code = dest_plugin_code
        self.mode = TravelMode(mode)
        self.target_x = float(target_x)
        self.target_y = float(target_y)
        self.target_z = float(target_z)
        self.target_angle_z = float(target_angle_z)
        self.transit_hop = bool(transit_hop)
        self.follower_synced = False
        self.carried_items_preserved = False
        self.elapsed_real_s = 0.0
        self.state = TravelState.PENDING_WRITE
        return self

    def recover_on_load(self, *, dest_anchor_loaded: bool) -> str:
        """Handle a save reload interrupted mid-trip (D1: OnPlayerLoadGame recovery).

        If state was strictly between PENDING_WRITE and WAITING_3D, move forward to clear
        when the destination anchor is already loaded, or abort fade and clear cleanly when
        reloaded pre-move so no player stays stuck faded-out or locked.
        """
        if self.state in (TravelState.IDLE, TravelState.CLEARED):
            return "noop_idle"
        if self.state == TravelState.ARRIVED:
            self.transition(TravelState.CLEARED)
            return "finalized_clear"
        if self.state in (
            TravelState.PENDING_WRITE,
            TravelState.FADING_OUT,
            TravelState.MOVING,
            TravelState.WAITING_3D,
        ):
            self.transition(TravelState.RECOVERED_FROM_RELOAD)
            if dest_anchor_loaded:
                self.transition(TravelState.WAITING_3D)
                self.transition(TravelState.ARRIVED)
                self.transition(TravelState.CLEARED)
                return "recovered_completed_at_dest"
            self.transition(TravelState.FAILED)
            self.transition(TravelState.CLEARED)
            return "aborted_pre_move_lock_cleared"
        if self.state == TravelState.FAILED:
            self.transition(TravelState.CLEARED)
            return "cleared_failed"
        return "noop"

    def to_dict(self) -> Dict[str, Any]:
        raw = asdict(self)
        raw["mode"] = int(self.mode)
        raw["state"] = int(self.state)
        raw["state_name"] = self.state.name
        return raw


def resolve_registered_destinations(
    registry_path: Path | str = WORLD_REGISTRY_PATH,
    *,
    world_keys: Optional[Iterable[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Read destination metadata from `world_registry.json` without hardcoding map offsets."""
    data = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    wanted = None if world_keys is None else set(world_keys)
    out: Dict[str, Dict[str, Any]] = {}
    for entry in data.get("worlds", []):
        key = entry.get("key")
        if not key or (wanted is not None and key not in wanted):
            continue
        planned = entry.get("planned_starfield_world") or {}
        if not planned.get("plugin") or not planned.get("world_edid"):
            continue
        out[key] = {
            "key": key,
            "plugin": planned["plugin"],
            "world_edid": planned["world_edid"],
            "host_planet": planned.get("host_planet"),
            "pipboy_plugin_code": planned.get("pipboy_plugin_code"),
            "reachability": planned.get("reachability"),
            "coc_spawn": planned.get("coc_spawn"),
            "planet_position": planned.get("planet_position"),
        }
    return out
