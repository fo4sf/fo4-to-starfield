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
| L4 player systems | reputation UI, settlement management, survival, RP SPECIAL | `reputation.py`, `modes.py`, `manage.py` (data, no UI) |
| L3 presentation | materialize squads and caravans near the player, radiant quests, radio and terminal news | `present.py`, `news.py`, `jobs.py` (data, no spawns) |
| L2 simulation | faction AI, settlement growth, supply and trade, events; coarse ticks, deterministic per seed | `sim.py` |
| L1 world-state model | places, holders, settlements, factions, routes, events; game-neutral data | `model.py` (schema 2) |
| engine edge | records the save keeps, plus the plugin's sidecar (CC-02 C') | `adapter.py`, `sidecar.py` (plan and codec only) |
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

## Implemented now (M2, still offline, pure Python stdlib)

- `present.py`: the L3 presence planner. `plan(ws, player_place)` lists what to materialize within a route radius of
  the player as abstract spawn slots under an actor budget (attackers, garrisons, settlers, squads, caravans);
  `diff(old, new)` says what a replan spawns, keeps and dissolves. Nothing is spawned; it is data for an adapter.
- `news.py`: L3 terminal news. The simulation's events, as reached along the routes (`sim.news_for`), become short
  lines in our own words; `terminal_page` wraps them for a terminal. Text only, no voice, quotes no game's writing.
- `reputation.py`: L4 New Vegas-style fame and infamy per faction (two scales, four levels each, tiered gains cited
  from `settlements-factions-precedents.md`), an optional per-region layer (CC-22) that is empty in a one-world game,
  and abstract effects (price, refusal, hostility) as placeholder tiers for probe P7.
- `modes.py`: L4 play settings stored in the save (schema 2): survival presets off/light/full (data only, no needs
  model yet), raid pressure low/normal/high scaling the attack and raid rolls, and the chronological story mode
  (CC-50), which shields places near an active story's locked place from attack.
- `adapter.py`: the engine edge as a record plan, not records: `record_plan(ws)` names the `FOCC_` slots a pack
  needs (one keyword per place for holder keyword data, our choice where the note plans a single `FOCC_Holder`
  keyword, probe P2; one global per faction for the reputation tier;
  globals for the settings), `game_view(ws)` gives each slot's value, `changes(old, new)` the minimal writes.
  Holder codes are small ints from sorted faction ids. Nothing writes a plugin.
- `sidecar.py`: the reference codec for the per-save file an SFSE plugin would keep (no co-save exists; SFSE's
  save and load messages carry the save name, `engine-feasibility.md`): a sanitised file name per save, JSON body
  with a sha256 of the canonical state, atomic `write`, `read` that refuses a wrong format, schema or checksum, and
  `orphans` that lists sidecars whose save is gone and never deletes.

## Implemented now (M3, still offline, pure Python stdlib)

- `jobs.py`: L3 radiant work. `offers(ws, place)` lists what the faction holding the place asks of the player right
  now (defend, escort, retake, resupply, clear), each derived from something the simulation is doing; `complete`
  goes through the simulation's player hooks (defend, escort, resupply) or a logged direct change of holder (retake,
  clear) so the next tick runs on a changed world, following the verified criticism in `gamma-anatomy.md` 2.6 and
  our own anti-lesson 1 (section 5, H) that faction tasks should change territory or supply state. A cleared place
  counts as lost to its old holder everywhere (`sim.holder_changes`). No money, no quest records, our own text.
- `manage.py`: L4 settlement management as pure functions: `assign_role`, `add_beds`, `set_priority` (a production
  focus the simulation honours), `send_supplies` (a caravan the simulation resolves and raiders may hit), `threats`,
  `status`. Every action validates, then logs an event the news (`news.TEMPLATES` has a line for each) and a resumed
  save see.
- `balance.py`: the tuning harness. `metrics(ws)` reads one finished world (places changing hands per 30 days,
  attacks per day, caravans raided share, empty settlements, mean morale, per-faction share of time landless and
  home-only, story-lock and home violations, frozen regions); `sweep(packs, seeds, days, overrides)` runs fresh
  worlds per seed with `sim` constants overridden inside a context manager that always restores them (a value of
  the wrong kind, a string for a number, is refused before the sweep runs);
  `check(aggregate, bounds)` lists the bounds broken. `DEFAULT_BOUNDS` is a placeholder envelope around the fixture
  baseline below, not a balance decision. `__main__.py` gains `balance`, `news` and `present` (Run it, below).

### Balance baseline (before-number, per AGENTS.md's measured-before-and-after rule)

Fixtures, 20 seeds x 90 days, `PYTHONPATH=src python3 -m fo4sf.combined balance --seeds 20 --days 90` (under a
second). "Before" is the M3 constants, 2026-10-20; "after" is the same command on 2026-10-21 with the two settlement
rules added below (`sim.REROLE_ON_SHORTAGE`, `sim.RESETTLE_*`), everything else unchanged. Later tuning changes add a
column the same way.

| Metric | Before (2026-10-20) | After (2026-10-21) | Reads as |
|---|---|---|---|
| changes_per_30_days | 15.0 | 12.5 | places change hands about every two and a half days across 11 places |
| attacks_per_day | 1.08 | 1.09 | about one attack squad launched per game day (unchanged) |
| caravans_raided_share | 0.13 | 0.10 | one caravan in ten is intercepted |
| empty_settlements | 1.6 of 4 | 0.0 of 4 | no run ends with an empty settlement |
| settlements_emptied (new) | 2.3 | 2.35 | a settlement still falls empty about twice per run (per 4 settlements, 90 days) |
| resettlements (new) | 0 | 1.75 | and is resettled; the rest refill through the older arrival rule |
| empty_share (new) | 0.32 | 0.024 | share of settlement-hours with nobody home: a third of the run, now one fortieth |
| mean_morale | 48.2 | 85.9 | settlers were flat or starving; now most settlements are fed and growing |
| landless_share_max | 0.0 | 0.0 | 0 by construction while homes never change hands |
| home_only_share | slavers 1.0, traders 0.62, order 0.53, raiders 0.35, settlers 0.0 | slavers 1.0, traders 0.62, order 0.47, raiders 0.40, settlers 0.0 | see note |
| story_lock_violations, home_violations | 0, 0 | 0, 0 | invariants hold over all seeds |
| frozen_regions | none | none | both regions saw a change of holder in every seed |

The three new metrics are rebuilt from two new event kinds, `settlement_emptied` (the last settler leaves, or a
capture removes the last people; carries `holder`) and `settlement_resettled` (carries `faction`, the holder), so a
resumed save measures the same; a save from before 2026-10-21 has neither and measures `empty_share` 0 until
something happens. The "before" column's new metrics come from the same command with the rules switched off
(`--set sim.REROLE_ON_SHORTAGE=0 --set sim.RESETTLE_SAFE_HOURS=1000000000`).

**Diagnosis of the 1.6 (traces in the per-seed harness, 20 seeds x 90 days, old rules).** 40 emptyings: 31 were
the last settler leaving after a morale collapse, 8 a capture removing the last one or two people, 1 both. The
collapse was always starvation after capture: `_remove_settler` takes from the biggest role, which on a farm is
the farmers, so a capture of `farm_a` (3 farmers, 1 guard, 1 trader) removed all three farmers, the guard and
trader ate the stock down (seed 9: dead at hour 126), and nothing could recover because the arrival rule needs
morale 70 and a surplus. Once empty, 96% of the empty settlement-hours had food or water at 0, and with nobody
producing and no caravan going to a raider-held farm, morale stays frozen and the place is dead for the rest of
the run (32% of all settlement-hours were empty). Not beds (20, never the cap at the time), not raided caravans
(13%). Judged a rule problem: people do not starve beside a field, and an empty place a faction holds should be
able to be lived in again.

**Rules added (placeholder constants in `sim.py`, overridable in sweeps):**
- `REROLE_ON_SHORTAGE = 1`: on a tick short of food or water, one settler of the biggest non-farmer role takes up
  farming while `3 * farmers < population + 2` (the food rule `_add_settler` grows by). Logged as `roles_changed`
  with the same fields as `manage.set_roles`. Capture still halves the population and caps morale at 30, and the
  larder still drains for a tick or two (the `resupply` job window stays), but the place feeds itself again.
  Rejected alternative, measured: taking non-farmers first on removal gave the same emptiness numbers but no
  shortage ever, so `resupply` jobs never appeared and caravans grew to 74 goods (which also exposed that
  `jobs.Offer.reward_tier` stores points, not a 1..5 tier, so a cargo of 30 or more fails the offer-shape test; a `jobs.py` finding for its owner, not reached by the rules kept).
- `RESETTLE_SAFE_HOURS = 48`, `RESETTLE_KIT = 6`, `RESETTLE_MORALE = 50`: an empty settlement a faction holds (and
  with beds) draws one wanderer on a day tick when no attack squad is bound for it and no `place_taken`,
  `attack_failed` or `place_cleared` touched it within the window; the wanderer is a farmer, brings the kit in
  food and water, and morale restarts at no less than 50. Logged as `settlement_resettled`. No random draw, so
  the RNG sequence of every other rule is unchanged.

Variants measured for the decision (same command, 20 seeds x 90 days): re-role only gives empty_share 0.031 and
resettlements 0 (the older arrival rule refills a place that still has stock); resettle only gives 0.037 with 4.45
emptyings and 3.65 resettlements per run (farms keep dying and being reseeded); both give 0.024 with 2.35 and 1.75.
`DEFAULT_BOUNDS` tightened to match: `empty_settlements` at most 1.0 (was 2.5), `empty_share` at most 0.15 (new).

Findings for the lead, not fixed here: `slavers` never leave home because `slaver_pit`'s one route leads to
`river_town`, the traders' home, which can never be attacked (fixture shape, so `home_only_share` is reported but
not bounded). `market` never grows past its starting 6 in any seed under either rule set: its two farmers make exactly
the 6 water its 6 settlers drink, and caravans carry only food, so the morale rule's surplus test (`stock > 2 * need`
for both goods) never passes; `river_town` reaches its 20 beds at hour 432 (day 18) in every seed and stays there (slavers cannot attack a home). Both are fixture-shape
findings; a water cargo or a lower morale threshold would be a tuning question. Mean morale 86 reads as generous:
whether settlements should thrive this easily between raids is for the lead to judge against the design, and
`RAID`/`ATTACK` pressure and `REROLE_ON_SHORTAGE` are the knobs.

## Not implemented (and not claimed)

No game runtime, no Papyrus, no SFSE plugin, no plugin records written (the adapter is a plan), nothing installed or
deployed, no UI, no spawning, no voice, no quest records behind the job offers, no player-needs model behind the
survival presets, no reputation globals per region, only one tuning pass (empty settlements, see "Balance baseline"; the other constants are
still the first prototype's placeholders). Whether keyword data survives a save (P2) and the sidecar's behaviour under SFSE (P1) are untested on the PC.
The fixtures use placeholder names (`farm_a`, `raiders`); they are not game facts.

## Run it

```
python3 -m unittest discover -s tests -p 'test_combined*'
python3 scripts/guard.py
python3 -m fo4sf.combined demo --seed 3 --days 30
python3 -m fo4sf.combined simulate --pack r1.json --pack r2.json --seed 5 --days 20 --out state.json
python3 -m fo4sf.combined simulate --resume state.json --days 10
python3 -m fo4sf.combined seed OUT_DIR Fallout4.esm DLCRobot.esm ...   # read-only; writes two JSON files
python3 -m fo4sf.combined balance --seeds 20 --days 90                    # fixtures; exit 1 when a bound breaks
python3 -m fo4sf.combined balance --seeds 20 --days 90 --pack r1.json --set sim.UPKEEP_PER_PLACE=2
python3 -m fo4sf.combined news --resume state.json --place market         # the terminal page at a place
python3 -m fo4sf.combined present --resume state.json --place market      # present.plan(...) as JSON
```

`balance` prints aggregate metrics, overrides and broken bounds as JSON; `--set NAME=VALUE` takes a bare `sim`
constant or `sim.NAME`, with the value as JSON (a value that is not JSON is an error, not a string). `news` and
`present` also take repeatable `--pack`.

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
