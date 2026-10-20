"""Play settings as data for the combined core: survival presets, raid pressure and the chronological story mode.

Design questions this encodes (combined-core design, defaults to argue with): CC-40 survival module off/light/full
presets, off by default; CC-41 raid pressure as a player setting with three presets; CC-50 the chronological story
option, which "mutes the sandbox's pressure on story places while a story is active". engine-feasibility.md
sections 8 and 9 place the in-game switches in Gameplay Options and two globals (story mode, story active); this
module is the offline data they would mirror, nothing more.

Survival presets are data only. There is no player-needs model in the simulation yet, so the per-day food and water
numbers are stored, validated and serialized but read by nothing; they are PLACEHOLDERS (unverified, not Fallout 4
Survival values) until a needs prototype exists (engine-feasibility.md section 8, "needs-decay math in Python").

Pure data: no engine code, no randomness, no clock. `Settings` lives on WorldState and rides along in its JSON.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SURVIVAL_PRESET_NAMES = ("off", "light", "full")
RAID_PRESSURE_NAMES = ("low", "normal", "high")

DEFAULT_SURVIVAL = "off"
DEFAULT_RAID_PRESSURE = "normal"


@dataclass(frozen=True)
class SurvivalPreset:
    """Player needs per game day (PLACEHOLDER numbers, unverified; not wired into the simulation)."""
    enabled: bool
    food_per_day: int
    water_per_day: int


SURVIVAL_PRESETS = {
    "off": SurvivalPreset(enabled=False, food_per_day=0, water_per_day=0),
    "light": SurvivalPreset(enabled=True, food_per_day=1, water_per_day=1),
    "full": SurvivalPreset(enabled=True, food_per_day=2, water_per_day=3),
}

# Multiplier on the faction attack chance and the caravan raid chance (PLACEHOLDERS to tune; "normal" is 1.0 so the
# default world replays the first prototype exactly).
RAID_PRESSURE_MULTIPLIER = {"low": 0.5, "normal": 1.0, "high": 2.0}

# Story mode: no attack targets a place within this many route-hours of a story-locked place whose story is active
# (PLACEHOLDER radius). The locked place itself never changes hands anyway (CC-21).
STORY_SHIELD_HOURS = 6


@dataclass
class Settings:
    survival: str = DEFAULT_SURVIVAL
    raid_pressure: str = DEFAULT_RAID_PRESSURE
    story_mode: bool = False                          # CC-50 chronological option
    active_stories: list[str] = field(default_factory=list)   # story ids in progress; kept sorted, acts as a set

    def validate(self) -> None:
        if self.survival not in SURVIVAL_PRESETS:
            raise ValueError(f"unknown survival preset {self.survival!r}, want one of {SURVIVAL_PRESET_NAMES}")
        if self.raid_pressure not in RAID_PRESSURE_MULTIPLIER:
            raise ValueError(f"unknown raid pressure {self.raid_pressure!r}, want one of {RAID_PRESSURE_NAMES}")
        if not isinstance(self.story_mode, bool):
            raise ValueError("story_mode must be a bool")
        if (not isinstance(self.active_stories, (list, tuple))
                or not all(isinstance(s, str) for s in self.active_stories)):
            raise ValueError("active_stories must be a list of story ids")
        self.active_stories = sorted(set(self.active_stories))   # a saved tuple becomes a list here

    def survival_preset(self) -> SurvivalPreset:
        return SURVIVAL_PRESETS[self.survival]

    def raid_multiplier(self) -> float:
        return RAID_PRESSURE_MULTIPLIER[self.raid_pressure]

    def story_active(self, story: str | None) -> bool:
        """True when story mode is on and `story` is in progress."""
        return self.story_mode and story is not None and story in self.active_stories

    def start_story(self, story: str) -> None:
        if story not in self.active_stories:
            self.active_stories = sorted(self.active_stories + [story])

    def finish_story(self, story: str) -> None:
        self.active_stories = [s for s in self.active_stories if s != story]

    def to_dict(self) -> dict:
        return {"survival": self.survival, "raid_pressure": self.raid_pressure,
                "story_mode": self.story_mode, "active_stories": list(self.active_stories)}

    @classmethod
    def from_dict(cls, d: dict | None) -> "Settings":
        """Build from a saved dict; missing keys take defaults (a version-1 save has no settings at all)."""
        d = d or {}
        s = cls(survival=d.get("survival", DEFAULT_SURVIVAL),
                raid_pressure=d.get("raid_pressure", DEFAULT_RAID_PRESSURE),
                story_mode=d.get("story_mode", False),
                active_stories=d.get("active_stories", []))
        s.validate()                                   # also rejects a str here; list() would split it
        return s


assert set(SURVIVAL_PRESETS) == set(SURVIVAL_PRESET_NAMES)
assert set(RAID_PRESSURE_MULTIPLIER) == set(RAID_PRESSURE_NAMES)
