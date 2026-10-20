"""Combined core: the GAMMA-style way to play (design: docs/combined-core.md).

Game runtime model, not the leader core (fo4sf.core is the build-and-test orchestrator). Pure Python, no numpy, no
game or engine imports, so everything here runs on Linux CI:

- model: the L1 world state (places, holders, settlements, factions, squads, routes, reputation, events).
- pack: content packs (L5) as validated JSON that only ever add to the world.
- sim: the L2 off-screen simulation, deterministic for a seed so a saved state replays exactly.
- seed: a read-only reader that drafts a pack from the player's own Fallout 4 plugins (output stays on that PC).
"""
