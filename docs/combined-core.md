# The combined core (GAMMA-style way to play): what is in the repo

The design lives in the project's framework, `docs/research/framework/combined-core.md` (draft PR #408; until it
merges, the Combined core thread holds it). This page says what `src/fo4sf/combined/` implements today and how to
run it. Owner of the design, quoted from its header: "the Combined core thread (Claude-cloud)".

## What it is

The second way to play: one curated Fallout on Starfield's engine, built like S.T.A.L.K.E.R. GAMMA on Anomaly, for
players who own every included game plus Starfield. Its pillars are settlements that grow, factions that act and hold
territory, and a connected wasteland; survival is one layer. Everything is built on the player's PC from their own
installs; nothing of Bethesda's is shipped, and `scripts/guard.py` fails the build if game data lands in the repo.

It is **not** the leader core: `src/fo4sf/core/` is the build-and-test orchestrator (ledger, lease, preflight).
The combined core is game runtime; its records and packages are kept apart from the leader core's.

## Layer map (from the design)

| Layer | Content | Here now |
|---|---|---|
| L5 content packs | Commonwealth pack first, other worlds and community packs later; packs only add data | `pack.py`, `fixtures.py` (synthetic) |
| L4 player systems | reputation UI, settlement management, survival, RP SPECIAL | no |
| L3 presentation | materialize squads and caravans near the player, radiant quests, radio and terminal news | no |
| L2 simulation | faction AI, settlement growth, supply and trade, events; coarse ticks, deterministic per seed | `sim.py` |
| L1 world-state model | places, holders, settlements, factions, routes, events; game-neutral data | `model.py` |
| L0 converted worlds | per-game modules from the single-game pipeline | the rest of the repo |

## Implemented now (M1, all offline, pure Python stdlib)

- `model.py`: L1 dataclasses and `WorldState` with a versioned JSON round trip.
- `pack.py`: `validate_pack` and `load_pack`; a pack is JSON that only adds; a second region plugs into the first
  through a gateway place without the first knowing about it.
- `sim.py`: L2 ticks of 6 game hours; the RNG is seeded from (seed, hour), so a state saved and resumed replays
  exactly. Invariants kept: story-locked places and faction homes never change hands; values stay in range.
- `seed.py`: a read-only reader that drafts a pack from the player's own Fallout 4 plugins (LCTN, FACT, KYWD, LCRT;
  field layouts cited from xEdit dev-4.1.6 in the module docstring). Settlement and faction classification are
  regex guesses, labelled unverified until the first real run's report. Its output stays on the player's PC.
- `__main__.py`: the command line below.

## Not implemented (and not claimed)

No game runtime, no Papyrus, no SFSE plugin, nothing installed or deployed, no engine adapter, no presentation
layer. The fixtures use placeholder names (`farm_a`, `raiders`); they are not game facts.

## Run it

```
python3 -m unittest discover -s tests -p 'test_combined*'
python3 scripts/guard.py
python3 -m fo4sf.combined demo --seed 3 --days 30
python3 -m fo4sf.combined simulate --pack r1.json --pack r2.json --seed 5 --days 20 --out state.json
python3 -m fo4sf.combined simulate --resume state.json --days 10
python3 -m fo4sf.combined seed OUT_DIR Fallout4.esm DLCRobot.esm ...   # read-only; writes two JSON files
```

Run the module with `src/` on `PYTHONPATH` (the tests insert it themselves). `seed` writes
`commonwealth_seed.draft.json` (places and factions with their evidence) and `seed_report.json` (counts of every
keyword and ref type locations use, overrides, deleted records, compressed records, odd input). `seed.to_pack()` strips a draft to the
pack shape; a human fills holders and faction homes before `load_pack` accepts it.

## Waiting on the PC (on the owner's word, after the v6e test)

- The seed reader's read-only run on the player's `Fallout4.esm` and DLC: the report decides whether the regex
  guesses in `seed.CLASSIFY` stand, and the draft becomes the first Commonwealth pack.
- Probes P1 to P10 from the design (one at a time, read-only or staged): P1 SFSE sidecar on save and load, P2 keyword
  data persistence, P3 location data on our interiors, P4 squad spawn and dissolve over 20 cycles, P5 Papyrus tick
  over 50 places, P6 leveled list conditioned on location keyword data, P7 vendor refusal by reputation tier,
  P8 enable-parent stage swap at a converted settlement, P9 a caravan on a travel package across 4 exterior cells,
  P10 SendStoryEvent starting our quest. P1 to P3 decide where the world state lives (CC-02).
