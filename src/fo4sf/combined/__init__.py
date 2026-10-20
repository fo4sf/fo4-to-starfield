"""Combined core: the GAMMA-style way to play (design: docs/combined-core.md).

Game runtime model, not the leader core (fo4sf.core is the build-and-test orchestrator). Pure Python, no numpy, no
game or engine imports, so everything here runs on Linux CI:

- model: the L1 world state (places, holders, settlements, factions, squads, routes, reputation, events).
- pack: content packs (L5) as validated JSON that only ever add to the world.
- sim: the L2 off-screen simulation, deterministic for a seed so a saved state replays exactly.
- seed: a read-only reader that drafts a pack from the player's own Fallout 4 plugins (output stays on that PC).
- present: the L3 planner, what the simulation says is near the player as abstract spawn slots, plus plan diffs.
- news: L3 terminal and radio text, the event feed as short lines of our own writing.
- reputation: L4 faction standing from the player hooks, as tiers and placeholder effects.
- modes: L4 play settings stored in the save: survival presets, raid pressure, the chronological story mode.
- adapter: the engine edge as a record plan (which FOCC_ slots a pack needs and their values), not records.
- sidecar: the reference codec for the per-save file an SFSE plugin would keep beside each game save.
"""
