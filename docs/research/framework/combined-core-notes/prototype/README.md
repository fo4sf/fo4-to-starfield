# Combined core prototype (G5 and G6): world state and off-screen simulation on paper

Pure Python (stdlib only), no game data, no PC. Placeholder names in `scenario.py` are not game facts. Purpose: make
the L1 world-state model concrete and tune L2's rules before any game work, so the shape that has to be right early
(where state lives, how packs add worlds, what replays from a save) is tested now.

- `worldstate.py`: L1 model: places (holder, story lock), settlements (population, six roles, five goods, morale,
  stage, beds), factions (strength, home, aggression, relations), squads (attack, caravan), routes (game hours),
  New Vegas-style reputation (fame, infamy), an event log. `load_pack` only adds, never replaces.
- `sim.py`: L2 tick every 6 game hours, seeded from (seed, hour) so a run resumed from a saved state replays exactly:
  production and consumption, growth and decline, caravans between same-holder settlements, faction attacks on
  neighbouring places, capture, news that spreads along routes at travel speed, reputation spill to enemies.
- `test_sim.py`: 9 tests: determinism, save and resume, story places and faction homes never change hands, the world
  does change, values stay in range, one region runs alone and a second plugs in, packs only add, news speed,
  reputation spill.
- `demo.py`: 90-day summary per seed.

Run: `cd` here, then `python3 -m unittest test_sim -v` and `python3 demo.py 4`. Result 2026-10-19: 9 tests OK.

## What the prototype already taught (supported hypotheses from a toy model, not balance)

1. **Growth needs a role rule.** Filling the scarcest role first starved every settlement within weeks; growth must
   keep food ahead of mouths. Fixed: a new settler farms until food covers population plus two.
2. **Growth needs a cap.** Without beds a quiet settlement reached 92 people in 90 days. Fixed with `beds` (default 20);
   in game this is the player's building plus our stage prefabs (CC-10).
3. **Faction strength needs a sink.** Strength piled up to the cap for passive factions. Next: daily upkeep per held
   place, so holding more costs more (GAMMA and Anomaly's Warfare lessons to be compared in gamma-anatomy.md).
4. **A region whose only targets are faction homes freezes.** The second synthetic region never changed, because its
   only settlement is a home. Each pack needs contestable places, and region gateways should be reachable targets.
   Feeds CC-20 and the Commonwealth seed tables (G7).
5. **Capture must hurt the settlement, not just flip a flag.** Without it, raiders inherited thriving farms. Fixed:
   half the settlers flee and morale drops.
6. **Determinism and save replay are cheap if every random draw is seeded from (seed, hour).** Worth keeping as a hard
   rule for the real L2 (tests can replay a player's save offline).

## Next

Upkeep sink; retaking lost places; caravan raiding on routes; player actions (help defend, trade) beyond reputation;
then the Commonwealth seed tables (G7) generated from the player's FO4 data by a reader tested on synthetic fixtures.
