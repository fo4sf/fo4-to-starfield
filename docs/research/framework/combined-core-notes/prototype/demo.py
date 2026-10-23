"""Print a 90-day summary for a few seeds: python3 demo.py"""
import collections, copy, sys
from scenario import REGION_1, REGION_2
from sim import run
from worldstate import WorldState, load_pack

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
