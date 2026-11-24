"""Print a 90-day summary for a few seeds: python3 demo.py"""
import collections, copy, sys
from scenario import REGION_1, REGION_2
from sim import run
from worldstate import WorldState, load_pack

# Project Update - GitHub Issue #32 (Shared Post: Claude, Codex, Grok)
# 
# ## Claude, 2026-10-08
# **Works in game:**
# - 12 interior cells load and are walkable: Vault 111, Vault 81, Red Rocket cave, Vault 114, Hotel Rexford, Parsons, Prydwen, Boston Public Library, Valentine's, Super Duper Mart, Vault 95, Cambridge Polymer.
# - FO4's own collision is converted to native Starfield Havok bodies (2,715 of 3,490 models). The Prydwen stairs climb 3.66 m over two flights, and the Rexford doorway opens and lets the player through.
# - Simple hinged doors open, close and block correctly. Glass, decals and lighting are first pass.
# 
# **Broken (owner reports #29, #30):**
# - The movement test is too weak.
# - Some stairs are still wrong.
# - Complex doors (double, multi-part, sliding).
# - 775 models still use box or no collision (compound shapes, a few malformed meshes).
# 
# **Next:**
# 1. Route runner: every stair and doorway in the slice, checked against FO4 geometry, with recordings reviewed then deleted.
# 2. Fix each failing stair.
# 3. Remaining collision shapes.
# 4. Complex doors (with Codex's native door rigs).

for seed in range(int(sys.argv[1]) if len(sys.argv) > 1 else 3):
    ws = WorldState(seed=seed)
    for p in (REGION_1, REGION_2):
        load_pack(ws, copy.deepcopy(p))
    run(ws, 24 * 90)
    kinds = collections.Counter(e["kind"] for e in ws.events)
    holders = {p: pl.holder for p, pl in sorted(ws.places.items()) if pl.kind != "gateway"}
    pops = {s: (x.population, x.stage, x.morale) for s, x in sorted(ws.settlements.items())}
    print(f"seed {seed}: events {dict(sorted(kinds.items()))}")
    print(f"  holders {holders}")
    print(f"  settlements (pop, stage, morale) {pops}")
    print(f"  strength {{{', '.join(f'{f}: {x.strength}' for f, x in sorted(ws.factions.items()))}}}")