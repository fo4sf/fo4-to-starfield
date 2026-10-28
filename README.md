# Fallout 4 → Starfield

**Fallout 4, running inside Starfield's engine, built by a toolchain instead of by hand.** The converters read your own
copies of both games and turn Fallout 4's terrain, buildings, interiors, doors, objects, actors and scripts into
Creation Engine 2 data that the stock Starfield executable loads as a mod. The playable Commonwealth exterior, a set of
interiors and the first mission already run in Starfield on the owner's test PC; a Vault 111 start is built and waits
for its first run. The full game is unfinished, and on top of it a second way to play is taking shape: a living
Commonwealth where settlements grow and factions fight over the map.

**Not offered for download or play for now.** On 19 October 2026 the owner withdrew the play and install guides, for
legal reasons and so nobody's hopes are raised early; a letter asking Bethesda about the project went out the same
day, and the repository is private. This page records progress. No game files or conversion pack are distributed:
everything is generated on the player's own PC from the player's own installs, and the in-game screenshots here depict
Bethesda-owned visuals, excluded from the project's code license.

Reviewing or forking with an AI assistant? Point it at [docs/ai/for-ai-reviewers.md](docs/ai/for-ai-reviewers.md) first.

[Where it stands](#where-it-stands-28-october-2026) · [Two ways to play](#two-ways-to-play) · [How it works](#how-it-works) ·
[Roadmap](docs/ROADMAP.md) · [Journal](docs/JOURNAL.md) · [Status thread #32](https://github.com/fo4sf/fo4-to-starfield/issues/32) ·
[Progress dashboard](https://claude.ai/artifact/SjY6rgmjtdmN8ryjxAUxAp) · [Contribute](CONTRIBUTING.md)

## Where it stands (28 October 2026)

**Phase 0, the Commonwealth test slice, is done by the owner's word (24 October).** Its exit gates were ticked in
game: the mission's pull request merged after review; the automated door rounds passed (29 of 30 round-trip legs, 0
failures; the one non-pass was the border popup); with the border switch on, the Vault 95 exit landed and the owner
walked west and south of Red Rocket with no wall; and the owner's own hand checks of the mission, the map markers and
the doors were done. Since then the work has moved to the combined core (below)
and to the next phase of the single-game conversion. Every row here says whether it was seen in the game or only in
offline tests; dates are UTC.

| Area | State | Seen |
|---|---|---|
| **Commonwealth exterior** | the 64 × 64 cell core as native terrain with 648,358 placed objects; the owner walked from Red Rocket to the Diamond City gate with no crash and no boundary | in game, 17 Oct |
| **No walls** | an SFSE plugin (`FO4SFBorder`) switches Starfield's landing border off inside our world only; with it on the owner walked west and south of Red Rocket and hit no wall, and the first-load flicker that left the border on is fixed | in game, 24 Oct |
| **Interiors** | 16 interiors reached in game so far (Vault 111, Vault 81, the Red Rocket cave, Vault 114, the Prydwen, Hotel Rexford, the Boston Public Library, Parsons and more), with working stairs, hinged and sliding doors and posed props; 253 more (the 251 planned base-game interiors and Automatron's 2; 4 odd hook cells are left out) are built in batches and held for install | in game (16), offline (253 more) |
| **Load doors with animation** | load doors that open before the trip (`FO4SF_AnimatedLoadDoor`); the port carrying them is installed and its automated door rounds are queued | installed 28 Oct, rounds pending |
| **First mission** | a cut-down "When Freedom Calls" ran to completion: stages 20, 30 (5 of 5 raiders), 40, 200 and complete | in game, 19 Oct |
| **Codsworth** | a robot stand-in at his Sanctuary spot, rendering with plain shader blocks (the fix that solved the Red Rocket crash); 20 of his voice lines converted from the owner's files; his spawn on an existing save is on the defect list | in game, 22 to 23 Oct |
| **Map markers** | the four markers (Red Rocket, Sanctuary, Vault 111, Concord) draw on the surface map and fast travel lands on them; the icons that do not load are the owner's named map issue for the next phase | in game, 22 Oct |
| **New game** | a Vault 111 cryo-pod start that is meant to skip Starfield's intro, built and staged against the installed core; by the record it has not yet run in game | staged 23 Oct, in-game run pending |
| **Launcher** | a desktop window that finds both games, reports and fixes the load order and starts Starfield through SFSE; it is meant to ship no assets and build the port from the player's own Fallout 4, and it still needs the current Steam build of Fallout 4 added to its version check | started the game, by the owner's word, 22 Oct |
| **Combined core, offline** | the Commonwealth seeded from the owner's own Fallout 4 and all six DLC: 487 locations read, 243 places kept, 42 settlements, 7 factions; a 90-day, 5-seed balance run passes every scale bound | offline, 28 Oct |
| **Combined core, in game** | engine probes P2, P3 (keyword half), P4, P6, P7, P8 and P10 passed on the test PC and P5 recorded its timings: keyword data persists across save and load, actors materialize and dissolve without growing the save, leveled lists and conditions read our data, our Story Manager branch starts our quest; P3's cell half and P9 (long-route pathing) run again after a restage; P1 not yet run | in game, 28 Oct |
| **Tests and CI** | 3,592 synthetic-fixture tests at #560's merge (28 Oct, recorded in the [journal](docs/JOURNAL.md)) and the asset guard run on every pull request | CI |

What is next, in the owner's order: the combined core's simulation ported to C++ inside our SFSE plugin, a 20-place
slice of it in game, then the map icons, the new game's exit test and the launcher's support for the current Steam
build of Fallout 4. The full ledger, with evidence for every row, is [docs/ROADMAP.md](docs/ROADMAP.md); the day-by-day
record is [docs/JOURNAL.md](docs/JOURNAL.md); the owner's own findings are
[docs/owner/playtest-issues.md](docs/owner/playtest-issues.md). The front page's earlier progress tables are kept in
[docs/history/readme-progress-2026-10.md](docs/history/readme-progress-2026-10.md).

## Two ways to play

**Fallout 4 as itself.** The conversion carries Fallout 4's world and content into Starfield piece by piece: terrain
and placed objects, interiors with their doors and stairs, actors on a converted navmesh, the quests, starting with the
Vault 111 start and "When Freedom Calls". The approved phases, in the owner's order of 19 October: the new game, load
doors with enter and exit animations, all interiors, then a launcher that builds the port on the player's PC. All
Fallout 4 DLC are required; SFSE is required; nothing is shipped but code.

**The combined core.** A GAMMA-style second way to play, built like S.T.A.L.K.E.R. GAMMA on Anomaly: one curated
Fallout on Starfield's engine, for players who own the games. Its pillars are settlements that grow, factions that act
and hold territory, and a connected wasteland, with survival as one layer. The world runs offline as a deterministic
simulation seeded from the player's own Fallout 4 data (`src/fo4sf/combined/`), and the game shows what happens near
the player: squads, caravans, garrisons, radiant jobs, terminal and radio news. The owner's calls of 25 October shape
it: travel by corridors and a capped map pick, with vertibirds for long trips; two modes, Warfare (pick a faction and
one of its bases) and Survival (story on or off); after death in Warfare the player goes on as another member of the
faction; ghoul play; and no language model or online service anywhere in gameplay. Design:
[docs/combined-core.md](docs/combined-core.md); the C++ port plan:
[docs/combined-core-cpp-port.md](docs/combined-core-cpp-port.md); the in-game probes:
[docs/spikes/combined-core-probes.md](docs/spikes/combined-core-probes.md).

## How it works

Starfield's executable cannot be rebuilt, so the project is a **total conversion on the stock executable**: Fallout 4's
data is converted into Starfield's formats and loaded as a plugin with loose files, with SFSE plugins where Papyrus
cannot reach. Fallout 4's own engine is not replaced; only its data is carried across. The method is in
[docs/PLAN.md](docs/PLAN.md); the risks and the spikes that answered them are in [docs/RISKS.md](docs/RISKS.md) and
[docs/spikes/](docs/spikes/).

| Stage | What runs | Where |
|---|---|---|
| **Read** | Fallout 4's plugins, archives, meshes, materials, collision, terrain and navmesh, read from the player's install | `src/fo4sf/` (`nif.py`, `ba2.py`, `fo4land.py`, `hkpackfile.py`, `navmesh.py`, …) |
| **Convert** | meshes to NIF metadata plus `.mesh` geometry, materials to `.mat`, Havok packfiles to tagfiles, FO4 land to an overlay worldspace on `.btd` terrain, navmeshes cut at Starfield's cell lines, doors re-rigged with their own clips | `src/fo4sf/`, `scripts/terrain/`, `scripts/slice/` |
| **Write records** | the Starfield plugins: the terrain core, the interiors port, map markers, the mission, the new game, the probes; built with Mutagen in .NET | `dotnet/` (`Fo4Export`, `Fo4Land`, `MapMarkers`, `CombinedProbe`, …) |
| **Script and hook** | Papyrus scripts for doors, the mission, the bridge and the probes; SFSE plugins for what Papyrus cannot do (the per-world border switch, the combined core's sidecar) | `scripts/bridge/`, `scripts/mission/`, `scripts/newgame/`, `sfse/` |
| **Stage, deploy, roll back** | every build is staged with pinned hashes and installed or removed as a unit on the test PC | `scripts/deploy_starfield.py`, `scripts/testing/` |
| **Test in game** | a runner on the test PC launches Starfield through SFSE, drives the console, reads the game's own log through the bridge and judges each test (door rounds, walks, terrain probes, the engine probes); the owner's hand checks follow the test sheet | `scripts/game/`, `src/fo4sf/combined/probes.py`, `docs/owner/in-game-test-sheet.md` |
| **Launch** | a desktop launcher that detects both games, fixes the load order and starts the game | `src/fo4sf/launcher/`, `scripts/launcher.py` |

Every claim in the docs is labelled **in-game verified**, **offline tested** or an **unverified hypothesis**, and the
journal is append-only: corrections are new entries, never edits. The guard (`scripts/guard.py`) fails any commit that
carries game data or a path from someone's machine.

## See the work

**Red Rocket at the end of the Sanctuary walk** (experimental core, 15 October).

![Red Rocket exterior at the end of the Sanctuary walk](docs/media/walk-s2rr-end-1015.jpg)

**Vault 111 during an observation-bridge session** (14 October).

![Converted Vault 111 during observation-bridge testing](docs/media/bridge-vault111-1014.jpg)

**Hotel Rexford: a native hinged door.**

![Hotel Rexford door opened in Starfield](docs/media/rexford-door-native.jpg)

**Parsons: the same door from both sides.**

![Parsons hinged door route, side A](docs/media/route-parsons-door-bothsides-a.jpg)

[Opposite side](docs/media/route-parsons-door-bothsides-b.jpg) · [First textured chair](docs/media/fo4-chair-textured-in-starfield.png) ·
[Vault 111 stairs](docs/media/vault111-stairs-catwalk-in-starfield.png) · [Vault 111 first light](docs/spikes/WP10-vault111-first-light.md) ·
[More interiors](docs/spikes/WP10-more-interiors.md) · [Collision](docs/spikes/S6-collision.md) · [All captures](docs/media/)

## Repository map

| Folder | Holds |
|---|---|
| `src/fo4sf/` | the converters and format readers; `combined/` the combined core's model, simulation, seed and probe judges; `core/` the build-and-test orchestrator; `launcher/` the launcher |
| `scripts/` | build, stage, deploy and test tools: `terrain/`, `slice/`, `bridge/`, `mission/`, `newgame/`, `mapmarkers/`, `combined_probes/`, `game/` (the PC test runner), `guard.py` |
| `dotnet/` | the Mutagen-based plugin writers and in-game probes |
| `sfse/` | the SFSE plugins: `FO4SFBorder`, `FOCCSidecar` |
| `docs/` | [PLAN](docs/PLAN.md), [ROADMAP](docs/ROADMAP.md), [JOURNAL](docs/JOURNAL.md), [RISKS](docs/RISKS.md), [FORMAT-GAP](docs/FORMAT-GAP.md); `spikes/` the research spikes; `terrain/`, `actors/`, `mission/`, `newgame/` the per-area notes; `research/framework/` the next-phase framework; `owner/` the owner's test sheet and findings; `ai/` the agents' decisions and rules |
| `tests/` | synthetic-fixture tests (no game data) |

## Why conversion is difficult

| Format area | Fallout 4 | Starfield |
|---|---|---|
| Plugin form version | 131 | 581 |
| Shared record fields | Sampled overlap is mostly 25–60% | Different record model and fields |
| Terrain | 37,020 `LAND` records in the measured sample | `.btd` terrain and procedural planets |
| Meshes | NIF geometry | NIF metadata plus external `.mesh` geometry |
| Materials | `.bgsm` / `.bgem` | JSON `.mat`, compiled into `.cdb` |
| Collision | Havok 2014 packfile | Havok tagfile and `hknp` shapes |

These are measured research notes, not promises of complete format support. Methods and sources: [format gap](docs/FORMAT-GAP.md), [spikes](docs/spikes/), and [measurement scripts](scripts/).

## Safety and project rules

- **No raw game assets or extracted files in Git or releases.** Do not submit `.esm`, `.ba2`, `.nif`, `.dds`, `.mesh`, `.hkx`, audio, executables, or converted outputs. The repository currently includes a limited set of screenshots captured in-game; these depict third-party visuals, are excluded from the MIT grant, and do not establish permission for reuse. The guard and CI check for raw assets and local paths.
- Converters read local files selected by the user; generated outputs stay local. The project does not distribute a conversion pack.
- Tests use synthetic fixtures. Offline passes do not prove that an asset works in-game.
- This is for offline, single-player modding research. It does not modify either game's executable.
- Do not commit credentials, personal machine paths, or private game data. Report suspected vulnerabilities using [GitHub's private reporting option](https://github.com/fo4sf/fo4-to-starfield/security/advisories/new) when available; see [SECURITY.md](SECURITY.md).

## Legal and license

This repository is unofficial and is not affiliated with or endorsed by Bethesda Softworks or ZeniMax Media. Fallout, Starfield, Creation Engine, and related names and materials belong to their respective owners. **The MIT license in this repository applies only to original project code and documentation; it does not grant rights to Bethesda software, game assets, trademarks, screenshots, or user-generated outputs.**

The project does not provide legal advice or establish that any particular extraction, conversion, or use is permitted. Check the current [Bethesda Terms of Service](https://bethesda.net/data/tos/en.html), the applicable [game EULA](https://bethesda.net/data/eula/en.html), and laws where you live; seek qualified legal advice if you need a determination for your circumstances. Avoid uploading or sharing game-derived outputs unless you have confirmed you have the necessary rights.

## Contributing and attribution

Read [CONTRIBUTING.md](CONTRIBUTING.md), choose an open issue, and use its acceptance criteria. Every change must pass the synthetic tests and asset guard. Identify whether a result is **in-game verified**, **offline tested**, or an **unverified hypothesis**.

The project is led by the repository owner and built with AI agents under the rules in [AGENTS.md](AGENTS.md). Work is signed by role: **Claude** and **Claude-cloud** (conversion pipeline, the combined core, in-game testing), **Codex** (deployment, recovery, persistent identities, output verification and independent review), and **Grok** (acceptance criteria, evidence gates and diagnostics). Agent labels and commit subjects identify work; these names do not represent separate human contributors or endorsements.
