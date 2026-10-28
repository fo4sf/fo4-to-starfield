# Combined core: porting the simulation to C++ (plan, 28 October 2026)

This is a plan. Nothing in it has run in game. It carries out the 28 October decision in `docs/ai/decisions.md`:
the in-game sim is a C++ port inside our SFSE plugin, and the Python model in `src/fo4sf/combined/` stays the
reference. The owner's order (28 October): the GAMMA core comes first, with probes P1 to P10, then the seed rerun
with all DLC, then a 20-place slice in game. The rerun is done ("Real pack, all DLC" in `docs/combined-core.md`).

## 1. What moves to C++ and what stays Python

Stays Python. These run offline, or at install time on the player's machine, where the converters already run:
- `seed` and `seedpack` (pack generation);
- `pack` (validation);
- `balance`, the probe judges in `probes.py`, and the `sidecar.py` reference codec.

The plugin starts from a world state that Python wrote (`WorldState.to_json`, schema 2). It never reads a pack.

Moves to C++, in this order. Each step is one PR with its own parity tests:

| Step | Python | Lines | In game it does |
|---|---|---|---|
| C1 | `model.py` (state, JSON), `modes.py`, `reputation.py`, `sim.py` (`tick`, `_distances`, player hooks) | about 990 | the 6-hour tick |
| C2 | `adapter.py` (`game_view`, `changes`) | 159 | which keyword data and globals Papyrus must write |
| C3 | `present.py` (`plan`, `diff`) | 187 | what to spawn and dissolve near the player |
| C4 | `manage.py`, `jobs.py` | 519 | the player's settlement actions and radiant jobs |
| C5 | `news.py` | 149 | terminal text (later; dynamic terminal text has its own engine question) |

## 2. The parity contract

"The same results" means byte-identical state:
- Same input: one state JSON, one number of ticks, and the same player actions at the same hours.
- Same output: byte-identical canonical JSON after every tick (`json.dumps(..., sort_keys=True)` with the default
  separators, as `WorldState.to_json` writes it).
- The harness compares a sha256 per tick, and prints both texts at the first tick that differs.

The test worlds are all synthetic, so they are in the repo:
- the fixtures (`fixtures.py`);
- the Commonwealth-scale draft (`tests/test_combined_seedpack.py`, `commonwealth_scale_draft()`, through
  `seedpack.generate`);
- variants of each: raid pressure low and high, and story mode on with an active story;
- a scripted list of player actions (defend, trade, help) at fixed hours.

Each world runs seeds 0 to 9 for 90 days.

The real pack is derived from the owner's files, so it never enters the repo. Its parity check runs on the PC
only.

The harness is a Python unittest. It compiles the portable core (no Windows, no SFSE) with `g++` on CI, which runs
on ubuntu-24.04, and compares the output against Python. That makes it the repo's first compiled test.
`sfse/FOCCSidecar/codec.h` was only checked by hand (its README, "Verified offline"); this harness should cover it
too. On the PC the same core is built with `cl.exe` by the plugin's `build.ps1`, and the parity run is repeated
there once.

## 3. What the port must copy exactly

**RNG.** The sim draws from `random.Random(seed * 1_000_003 + hour)`. That is Python's MT19937 with these parts:
- seeding: `init_by_array` over the absolute seed, split into 32-bit words, low word first;
- `random()`: two draws, `(a >> 5) * 67108864 + (b >> 6)`, divided by 2^53;
- `choice`: `_randbelow(n)`, which takes `getrandbits(k)` with k = n's bit length and rejects results until one is
  below n.

`std::mt19937` seeds differently, so the port carries its own 40-line generator. **Verified 28 Oct 2026:** that
generator matched Python 3.13 on 300 mixed `random()` and `randrange` draws for 10 seeds from 0 to 2^64 - 1. The
prototype and its checker are in the project folder, `research/combined-core/cpp-port/`. CI's Python 3.12 uses the
same algorithm, and the parity tests pin it.

**Seed range.** `seed * 1_000_003 + hour` must fit in 64 unsigned bits. The port refuses a state outside that. The
Python model should refuse it too: `WorldState` accepts any integer today. That is a small change in its own PR.

**Floats.** Three comparisons use doubles:
- the attack roll in `_faction_tick` (`rng.random() * 100 > aggression * 0.25 * pressure`);
- the raid chance in `_raider`;
- the capture roll in `_resolve_arrivals`.

Write each one in Python's left-to-right order. Build with `-ffp-contract=off` (GCC and Clang) and `/fp:precise`
without `/fp:contract` (MSVC), so no fused multiply-add changes a rounding.

**Integer division.** Python's `//` floors; C++'s `/` truncates toward zero. Every `//` in the sim has
non-negative operands today. The port still uses a floor-division helper, and asserts.

**Order.** Every Python walk is sorted. `std::map<std::string, ...>` orders bytes, which matches Python for ASCII
ids. `pack._is_id` accepts any non-empty string, so validation should also require ASCII. The places that need
explicit comparators:
- tuple sorts: targets `(place, hours, origin)`, squads by `(is garrison, id)`, neighbours `(place, hours)`;
- `max` and `min` ties: Python keeps the first in sorted order.

**Events.** Each event is an open dict: `hour`, `kind`, `place`, `region`, plus per-kind fields that can hold
null, a bool or a cargo dict. The port stores a small typed variant and writes it as canonical JSON.

The sim reads its own log. `_lost_places` scans every holder change, and `_resettle_safe` scans back 48 hours.
Trimming the log would therefore change results. The port keeps the whole log first. Trimming it later needs two
indexes, proved equal by the parity tests:
- the places each faction has lost;
- the last hour of fighting at each place.

The log's growth sets the sidecar's size. Measure it in Python on the real pack over one game year before the
port.

**JSON.** The plugin reads only world-state JSON that our Python wrote, and writes canonical JSON. A small reader
of our own for that one shape will do, like `codec.h`'s envelope reader. No third-party library.

## 4. The blocker: Papyrus cannot call our plugin through SFSE's public API

**Verified 28 Oct 2026.** SFSE's `PluginAPI.h` at the commit `fetch_pluginapi.ps1` pins (`48535cc`) offers four
interfaces: messaging, trampoline, menu and task. It has no Papyrus native registration and no access to game
data. SFSE has had custom Papyrus natives since 0.1.1
(`docs/research/framework/combined-core-notes/engine-feasibility.md`), but not through that header.

The in-game sim needs to:
- read game time and the player's location;
- have Papyrus call it for the player's actions;
- hand back the `changes()` list for Papyrus to apply.

That needs a Papyrus bridge. The usual route is CommonLibSF, which offers Papyrus native registration and game
types. The tool verdict (`docs/ai/decisions.md`, 28 October, "which outside tools we use") put CommonLibSF under "later,
for a named job", and this is that job. Its costs:
- **Licence:** GPL with exceptions, reviewed before anything built on it ships.
- **Addresses:** it relies on community reverse-engineered addresses for runtime 1.16.244, which a game update can
  break.
- **A second player dependency:** it usually needs the Address Library plugin, which players would install like
  SFSE. The owner's "SFSE required" decision covers SFSE only, so this one is the owner's call before anything
  ships.

**Step B0, a spike before any in-game port:**
- One native, `FOCC_Ping(int) -> int`, registered through CommonLibSF on 1.16.244 and called from a test quest
  script.
- Pass: the value comes back, and the native still works after a save and a load.
- Setup: it needs CommonLibSF's build tools on the PC. Installing those is the owner's call.

**If B0 fails, or the licence does not fit:**
- The 20-place slice runs in Papyrus, if P5 shows a Papyrus tick over 20 places is fast enough.
- The full Commonwealth (about 230 places) stays offline until a bridge exists.
- A Papyrus port cannot match the Python rolls, because Papyrus floats are 32-bit. The three rolls would become
  integer rolls in the reference model first, with a new balance baseline.

## 5. Steps

Each step is one PR, with green CI and an independent review.

1. **Offline (Python):** the seed-range and ASCII-id checks; the event-log growth over one game year on a
   synthetic Commonwealth-scale world.
2. **Offline, C1:** a portable core in `sfse/FOCCSim/`, with no Windows or SFSE code. It holds the generator, the
   state with its JSON reader and writer, and the tick. Plus the parity harness and its unittest.
3. **Offline, C2 to C4:** each step with its parity tests.
4. **PC:** probes P2 to P10, then P1 (queued 28 Oct; the probe stage is `D:\Modding\staging\focc_probe_20261028a`).
5. **PC:** bridge spike B0, after the owner's OK for the build tools.
6. **PC:** the 20-place slice.
   - Python slices the real pack to the 20 places nearest the Commonwealth slice.
   - The plugin keeps the state in the save's sidecar (P1) and ticks every 6 game hours.
   - Papyrus applies `changes()` to keyword data (P2) or globals.
   - One encounter comes from `present.plan`.
   - Pass: save, leave and return, and the world has moved on.
7. **Later:** the whole Commonwealth in game, after the slice's tick cost is measured. Tracy comes in here, as the
   tool verdict says.

## 6. What the owner decides, and when

- Nothing for steps 1 to 4.
- Before step 5: installing CommonLibSF's build tools on the PC.
- Before shipping anything built on it: the Address Library as a player dependency, and the CommonLibSF licence
  check.
