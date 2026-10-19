# Dependencies across the framework

Part of the [next-phase framework](README.md). Wave 3, 2026-10-19.

This file maps which framework questions block which. It adds no new facts. Every ID, quote and recommendation comes
from the twelve files it links. Recommendations stay recommendations; the owner decides.

How IDs are written here:

| Prefix | File | Example |
|---|---|---|
| WP | [world-and-planet.md](world-and-planet.md) | WP-01 |
| PS | [people-and-story.md](people-and-story.md) | PS-08 |
| REL | [release-community-legal.md](release-community-legal.md) | REL-26 |
| TT | [tooling-and-testing.md](tooling-and-testing.md) | TT-04 |
| AP | [asset-pipeline.md](asset-pipeline.md) | AP-40 |
| VM | [versions-and-maintenance.md](versions-and-maintenance.md) | VM-17 |
| MG | [multi-game-future.md](multi-game-future.md) | MG-07 |
| NG | [newgame.md](newgame.md) | NG-M1 |
| Door | [door-animations.md](door-animations.md), section 6, letter plus question number | Door E24 |
| Int | [interiors.md](interiors.md), section 8 tables (N, C, P, E, D, L, T) and leads (X) | Int N9 |
| Lau | [launcher.md](launcher.md), decisions (D) and questions (S, T, B, I, A, M, L) | Lau D1 |
| EM | [engine-mechanics.md](engine-mechanics.md), cross-cutting (X), leads (L), area keys | EM X1, EM UI 1.1, EM quests L1 |

Phases use the README's names: New game, Door animations, All interiors, Launcher, World, People and story, Fallout
systems, Release, Multi-game.

## Critical path per phase

Each list is in order. A step needs the steps above it. "Blocks" lines in the cross-cutting files and the phase files'
own "cheapest first" orders set the order.

### New game

1. **NG-M1, NG-M2** (does our quest stop MQ00 before it sets MQ101Debug; what MQ101 stage 9000 does). Offline. They
   test the current build ([newgame.md](newgame.md) "Cheapest first").
2. **NG-M3** (let MQ00 run, set MQ101Debug, or override 002EEA4D). Owner, after step 1.
3. **VM-17 / TT-04 / NG-D1** (data-only core or SFSE). VM-17 blocks New game. NG-D1 says it "decides the whole UI
   plan". [versions-and-maintenance.md](versions-and-maintenance.md), [tooling-and-testing.md](tooling-and-testing.md).
   NG-J4 (start with no SFSE) is then proved by the first in-game run.
4. **VM-02 then VM-01** (which Fallout 4 data versions; canonical Vault 111 and MQ101 records). Both block New game.
   AP-52 and TT-06 (BA2 v7/v8 reader) sit under them.
5. **VM-08 / NG-J5** (do our start-quest overrides survive a Starfield patch). Blocks New game.
6. **REL-26 / NG-G2 / NG-I1** (voice policy for the opening). REL-26 blocks New game. REL-20 (our own text) also blocks it.
7. **PS-01 / NG-I2** (choice list shows prompt, full line or both), **PS-04**, **PS-05 / NG-I3** (silent-player
   lines), **PS-07 / AP-45 / NG-I5** (silent voice files), **PS-31** (SEQ file). All list New game in "Blocks".
8. **MG-28 / NG-A11** (start-world hook or selector). Cheap now, costly later. Blocks New game.
9. **WP-19** (local time at the Vault 111 exit). Blocks New game.
10. **TT-25, TT-27 / NG-J2** (Debug functions; unattended new game). Block New game. Then **NG-J1** (scripted run
    with checkpoints).
11. **REL-51 / NG-F5 / NG-L2** (save versioning from v1). REL-51 blocks New game.
12. First in-game proof: NG-A4, A5, A9, B2, B3, B5, B7, C1, C2, C6, C7 in one session, on the owner's word.

### Door animations

1. **VM-17** (SFSE or not). Blocks Door animations. The handed question "Do door hooks rely on SFSE or runtime
   addresses?" (TT and VM hand-off tables) is answered by the VM E8 repo read.
2. **REL-19** (may derived data such as animation timings measured from FO4 clips ever ship). Blocks Door animations.
3. **Door A2** (what ends the engine's wait before an XTEL trip). PC read, then in game.
4. **Door D13** (FNAM flags on load-door bases). PC read. Then **Door G28** fix path (XNDP navmesh door links).
5. **Door B8** (refuse the trip on a locked door, offline), then **Door B7** (OnOpen or polling, in game).
6. **Door C11** (one animated DOOR or the vanilla elevator pattern). PC read, then owner. Needs TT-11 (CK loads our
   door PackIns).
7. **Door D15** (XTEL Transition Interior). PC read, then one test cell.
8. **Door E24** (moving refs onto `_XtelLoad` breaks a save?). In game A/B.
9. **Door I36** (50-trip soak).
10. Release side: **REL-05 / Door J39** (CALUMI LGPL), **REL-01 / Door J38** (licence), **VM-09** (vanilla door clip
    paths after patches), **AP-21, AP-22 / Door H33** (new clips, CALUMI size), **AP-31 / Door F25 to F27** (sounds),
    **REL-50** (videos).

### All interiors

1. **VM-03 / TT-06** (BA2 v7/v8). VM-03 blocks "any build on a current install". VM-02 blocks All interiors.
2. **TT-22 / VM-24 / AP-55 / Int X3** (one archive past 4 GiB). Int X3: the textures archive "passes 4,095 MiB
   around batch 7". Splitting is open.
3. **VM-25 / TT-19 / Int X2** (medium or full masters). Type "cannot be changed later". See the conflict below.
4. **TT-11 / Int T8 / Int E10** (does the CK open FO4Port.esm). Gates every CK step.
5. **TT-07 / Int N9 / Int T11 / Int X1** (CK batch navmesh) with **Int N1, N2** (no navmesh; door links without the
   CK). Offline first: **TT-35 / Int X6 / Int N3** (reachability checker).
6. **AP-05** (convert everything, count failures) and **AP-01** (vertex limit). Block All interiors.
7. **VM-27 / Int E1 / TT-31 / AP-48** (frame time on the densest interiors, Mechanist's Lair).
8. **REL-10** (are CK-tool-built plugins a "Game Mod"). Blocks All interiors.
9. **PS-17** (generic NPC faces at run time). Blocks All interiors.
10. **REL-42, REL-44 / Int P4 to P6, TT-28, TT-29, TT-38** (report bar, milestone, "done" rubric, smoke and review).

### Launcher

1. **REL-01 / Lau D8** (licence of the launcher binary). Blocks Launcher.
2. **VM-04, Lau S1, S9** (identify Fallout 4 data version, store and language from data). Then **VM-02 / Lau S3**
   (record diff), then **VM-01 / Lau D1 / AP-52** (which versions to accept).
3. **VM-17 / TT-04 / TT-39 / PS-35** (SFSE default). Blocks Launcher via TT-39 and PS-35.
4. **TT-13 / Lau T4 / Lau L3 / REL-10 / AP-50** (Archive2 and Papyrus compiler: player's CK or open tools).
5. **AP-30 / REL-04 / TT-09** (Wwise on the player's PC). Then **PS-08 / AP-40** (FaceFX unattended), **PS-09 /
   AP-41**, **PS-10 / AP-43**, **PS-11 / AP-42**.
6. **VM-12 / TT-01 / Lau D3 / Lau T1** (what happens on a Starfield update). Then **VM-19, VM-20**.
7. **REL-56 / Lau L2b** (refuse FO4 DLC the player does not own). **REL-14** (no store credentials).
8. **REL-32 / Lau D7** (internet use in the Nexus build).
9. **AP-49 / VM-30 / VM-31 / Lau B9** (time, disk, minimum spec). **Lau B1, B5** (determinism).
10. **PS-36 / REL-54 / REL-55 / VM-39** (languages). **VM-07 / AP-54 / Lau S7** (CC files).
11. **TT-23 / VM-33 / Lau A12, TT-24 / Lau A11** (crash logger, support bundle).

### World

1. **WP-05, WP-24, WP-44, WP-09, WP-10** (planet and overlay census). PC read-only. Feeds WP-01, WP-08, WP-13.
2. **WP-08** (overlays through `EOVR`) with **WP-23, WP-26, WP-28** in one island-overlay probe.
3. **WP-01** (host planet), then **WP-04** (planet master), **WP-02** (new game for a clone). **REL-12** (add-on
   planet or total conversion) also blocks World.
4. **WP-14** (real geography or compact), **WP-15** (Nuka-World site), **WP-27** (the ship) after WP-28 and WP-29.
5. **WP-13** (keep Planet Content Manager POIs out).
6. **WP-34 / TT-21 / VM-23** (archive and slot budget), **VM-25** (full masters for worlds).
7. **WP-45 / TT-41 / AP-47 / AP-59** (object LOD), then **WP-16** (outer ring).
8. **WP-33 / WP-31 / TT-31 / VM-28** (streaming 650k refs), **WP-36 / AP-25 / VM-29** (texture caps).
9. **WP-35 / VM-08** (overrides after patches). **REL-56** (Far Harbor and Nuka-World only if owned). **VM-07**.
10. **WP-38 / REL-52** (walkable-world release first).

### People and story

1. **REL-26** (voice policy), with **REL-27** (codsworth_voice.py) and **REL-30** (ask Bethesda). Block People and story.
2. **VM-17 / TT-04 / PS-35** (SFSE default).
3. Offline scan: **PS-04, PS-05, PS-13, PS-24, PS-30**.
4. **AP-30 / REL-04** (Wwise), then the FaceFX probe: **PS-08 to PS-11 / AP-40 to AP-43 / TT-08**.
5. Choice-scene probe: **PS-01, PS-03, PS-07, PS-12, PS-13, PS-31**.
6. **PS-15 / PS-16 / PS-17 / AP-09 / AP-10** (faces). Then **PS-18** (legal side of face values).
7. **PS-20 / AP-06** (skeleton), then **PS-19 / AP-07** and **PS-21 / AP-08** (clothing, bodies).
8. **TT-07** (navmesh, blocks People and story), **TT-25, TT-26, TT-30** (in-game testing).
9. **AP-20 / AP-21** (animation route), **PS-22, PS-25** (companion commands, fence Starfield companions).
10. **PS-36** (languages), **PS-32, PS-37** (new voice, voiced player).

### Fallout systems

1. **VM-17 / TT-04** (data-only core), then **VM-18** (what an SFSE feature does when a patch breaks it) and
   **TT-14** (where SFSE-plugin state lives).
2. **EM X1** (which FO4 systems need SFSE natives; 77 missing function names).
3. **EM UI 1.1 to 1.3 / EM L3 / EM X6** (UI stack and Pip-Boy). **REL-25** (Pip-Boy art) blocks Fallout systems.
4. **PS-27 / MG-27** (game-neutral names) and **EM X4** (namespacing). Cheap now.
5. **AP-20 / AP-21 / EM animation B1, B2** (new idles and graphs). **AP-31 / EM animation H2** (new sound events).
   **AP-33 / EM L2** (radio).
6. **PS-20 / AP-06** (skeleton) before **EM character A1 to A4** (power armor route).
7. **EM UI 11.1** (full VATS or bullet time). **REL-07** (licence of our own SFSE plugins).
8. **WP-27, WP-29, WP-22** (ship, star map, Glowing Sea) and **PS-06, PS-22, PS-24, PS-30** (Fallout-side rules).
9. **MG-07, MG-10, MG-12, MG-13** only when Multi-game starts.

### Release

1. **REL-30, REL-31** (contact Bethesda and Nexus). REL-52's recommendation puts the first release after them.
2. **REL-26, REL-27** (voice). **REL-01, REL-02, REL-08** (licences, source, permissions).
3. **REL-56** (DLC), **REL-57** (AI tag), **REL-32** (offline Nexus build).
4. **TT-01 / VM-12 / VM-36** (patch policy and support matrix), **VM-21 / REL-11** (Game Pass).
5. **VM-14 / REL-51** (save promise), **TT-05 / VM-13** (saves across Starfield patches).
6. **TT-23 / VM-33** (crash logger), **REL-24** (guard on release zips).
7. **TT-36, TT-37, TT-38, REL-42, REL-43** (labels, testers, review).
8. **WP-38 / REL-52 / REL-44** (what ships first).

### Multi-game

1. **MG-26, MG-27 / PS-27, MG-28** (reserve names, prefixes, start-world hook). Cheap now (R1 to R5).
2. **MG-01** (go/no-go timing), **MG-02** (FO76 and older games).
3. **MG-22, MG-20, MG-08** (Mutagen reads FO3/NV; ObScript text; skill-check counts). One PC read-only probe.
4. **MG-07** (whose rule set wins), then **MG-09 / PS-26, MG-10, MG-12, MG-13**.
5. **MG-03 / REL-18** (voice and legal check per game), **MG-04** (TTW contact), **MG-05** (separate module).
6. **WP-01, WP-04** then **WP-39 / MG-14 / WP-14** (planet and positions), **MG-15 / WP-30** (travel, arrival handler).
7. **MG-17 / WP-42** (how many landings one save carries).
8. **MG-25** (launcher per-game checks), **MG-29** (one-playthrough test).

## Same question, different files

"Owner file" is a suggestion for where the question should live. The others should point to it.

| Topic | IDs | Owner file |
|---|---|---|
| Data-only core or SFSE required | TT-04, TT-39, VM-17, VM-18, PS-35, AP-45, NG-D1, NG-J4, EM X1, EM decision 3 | versions-and-maintenance.md (VM-17) |
| Starfield update response and pin | TT-01, VM-12, VM-19, Lau D3, Lau T1, NG-F3, NG-L9, Int P7 | versions-and-maintenance.md (VM-12) |
| Patch-day checklist and duty | TT-02, VM-34, VM-37, AP-03 | versions-and-maintenance.md (VM-34) |
| Support matrix and patch promise | VM-36, Lau L11, Lau A5b | versions-and-maintenance.md (VM-36) |
| Overrides and vanilla paths after a patch | WP-35, VM-08, VM-09, AP-03, NG-J5, Lau T10 | versions-and-maintenance.md (VM-08) |
| Build cache keyed to Starfield runtime | VM-11, AP-56, Lau B7 | launcher.md (B7) |
| Previous runtime profile, beta branch | TT-03, VM-16, VM-22 | versions-and-maintenance.md |
| Saves across Starfield patches | TT-05, VM-13 | versions-and-maintenance.md (VM-13) |
| CK version matches the game | TT-12, VM-15 | tooling-and-testing.md (TT-12) |
| Fallout 4 data versions accepted | VM-01, VM-02, AP-52, Lau D1, Lau S3 | versions-and-maintenance.md (VM-01) |
| BA2 v7/v8 reader and fixtures | TT-06, VM-03, VM-06, AP-52, Lau S9 | versions-and-maintenance.md (VM-03) |
| FO4 version, store, language detection | VM-04, VM-05, Lau S1, Lau S4, Lau S8, REL-55 | launcher.md (S1 to S8) |
| Creation Club and HD pack | VM-07, AP-54, Lau S7 | versions-and-maintenance.md (VM-07) |
| Game Pass and other stores | VM-21, REL-11, Lau D2, Lau T11, NG-F9, TT-39 | versions-and-maintenance.md (VM-21) |
| Languages | PS-36, REL-54, REL-55, VM-39, Lau S4 | versions-and-maintenance.md (VM-39) |
| Archives past 4 GiB | WP-34, TT-22, VM-24, AP-55, Lau T3, Int X3, Int E11 | tooling-and-testing.md (TT-22) |
| Archive and plugin slot budget | WP-34, TT-21, VM-23, AP-55, Lau T2, Int X4 | tooling-and-testing.md (TT-21) |
| Medium or full masters | TT-19, TT-20, VM-25, NG-H5, Int X2, Lau M3, EM decision 9 | versions-and-maintenance.md (VM-25) |
| Precombines and dense-cell cost | TT-10, VM-26, VM-27, VM-28, WP-33, AP-48, Int E1, Int T9, Int T10 | tooling-and-testing.md (TT-31) |
| Performance protocol | TT-31, WP-31, WP-33, VM-27, VM-28, Int E7 | tooling-and-testing.md (TT-31) |
| Texture caps per VRAM tier | WP-36, AP-25, VM-29, TT-34 | asset-pipeline.md (AP-25) |
| Build time, disk, minimum spec | AP-49, VM-30, VM-31, TT-34, Lau B9, NG-H11 | launcher.md (B9) |
| Object LOD from the CK | WP-45, TT-10, TT-41, AP-47, AP-59 | asset-pipeline.md (AP-47); TT-41 and AP-59 are the same question |
| CK batch navmesh | TT-07, Int N9, Int T11, Int X1, MG-24 | interiors.md (N9) |
| Offline navmesh check | TT-35, Int X6, Int N3, Int P5 | interiors.md (X6) |
| Navmesh door links | Door G28, Int D4, Int N2 | door-animations.md (G28) |
| CK opens our plugins | TT-11, Int T8, Int E10 | tooling-and-testing.md (TT-11) |
| CK command-line switches | TT-08, AP-40, PS-08, NG-H6, Int T9, EM tools 6.1, EM job 18 | engine-mechanics.md (job 18) |
| FaceFX unattended and time | PS-08, AP-40, TT-08, EM quests L1, EM X5, NG-H10 | people-and-story.md (PS-08) |
| FaceFX resume and determinism | PS-09, AP-41 | people-and-story.md (PS-09) |
| FaceFX path rules | PS-10, AP-43 | people-and-story.md (PS-10) |
| FaceFX WAV only | PS-11, AP-42 | people-and-story.md (PS-11) |
| Voice type and lips | PS-12, AP-44 | people-and-story.md (PS-12) |
| Silent voice files | PS-07, AP-45, NG-I5, EM V5, EM D6 | people-and-story.md (PS-07) |
| Offline lip sync check | PS-14, AP-46 | people-and-story.md (PS-14) |
| Wwise on the player's PC | AP-30, REL-04, TT-09, Door F27 | asset-pipeline.md (AP-30) technical; REL-04 legal |
| New sound events | AP-31, EM animation H2, Door F25, Int L15 | asset-pipeline.md (AP-31) |
| Named-cast faces | PS-15, AP-10, NG-M9, EM character F1 | people-and-story.md (PS-15) |
| Facegen pre-baked or run time | PS-16, PS-17, AP-09, AP-11 | asset-pipeline.md (AP-09) |
| Skeleton name map | PS-20, AP-06 | asset-pipeline.md (AP-06) |
| Body weight to morphs | PS-21, AP-08 | asset-pipeline.md (AP-08) |
| Outfits: stand-ins or converted | PS-19, AP-07 | people-and-story.md (PS-19) |
| Choice list text | PS-01, NG-I2, EM quests D3 | people-and-story.md (PS-01) |
| Wheel slots in a list | PS-03, EM quests D2 | people-and-story.md (PS-03) |
| Silent-player lines | PS-05, NG-I3 | people-and-story.md (PS-05); NG-I3 is the MQ101/MQ102 case |
| Voice policy | REL-26, REL-27, MG-03, NG-G2, NG-I1, Int P2, EM decision 1, EM quests A1 | release-community-legal.md (REL-26) |
| Voiced-player option | PS-37, REL-58 | release-community-legal.md (REL-58) |
| AI voice | REL-28, PS-32, EM quests A2 | release-community-legal.md (REL-28) |
| Alignment (karma, reputation, affinity) | PS-26, MG-09 | multi-game-future.md (MG-09) |
| Game-neutral names | PS-27, MG-26, MG-27, EM X4 | multi-game-future.md (MG-27) |
| Cross-world factions and story | PS-28, PS-29, MG-19 | multi-game-future.md (MG-19) |
| Companion commands | PS-22, EM companions C1 | engine-mechanics.md |
| Affinity events | PS-24, EM companions A1, A2 | engine-mechanics.md |
| Radiant quests and Story Manager | PS-30, NG-E1, EM quests R1 | people-and-story.md (PS-30) |
| SEQ files | PS-31, EM job 18 (`-GenerateSEQ`) | people-and-story.md (PS-31) |
| Arrival handler for every route | WP-30, MG-15 (R6) | world-and-planet.md (WP-30) |
| Geography of later games | WP-14, WP-39, MG-14 | world-and-planet.md (WP-14) |
| Anchorage and Zeta | WP-40, MG-14 | multi-game-future.md (MG-14) |
| Weather for DC and Mojave | WP-41, MG-16 | multi-game-future.md (MG-16) |
| Landings per save | WP-42, MG-17 | multi-game-future.md (MG-17) |
| Start-world hook and selector | MG-28, MG-18, NG-A10, NG-A11 | newgame.md (NG-A11) |
| First public release scope | WP-38, REL-52, REL-44, Int P6 | release-community-legal.md (REL-52) |
| Save promise across our builds | VM-14, REL-51, Lau D9, Lau I5 to I7, NG-F5, NG-L2, NG-L4, Int P8, Door E24 | versions-and-maintenance.md (VM-14) |
| Plugins.txt reset | VM-10, Lau T5, NG-L1, NG-F7, REL-41 | versions-and-maintenance.md (VM-10) |
| sTestFile and INI rules | NG-F6, NG-L8, Lau T6 | launcher.md (T6) |
| Crash logger | TT-23, VM-33, Lau A12, Int T16, NG-H9 | tooling-and-testing.md (TT-23) |
| Support bundle | TT-24, REL-41, Lau A11 | launcher.md (A11) |
| Debug functions in retail | TT-25, NG-J3, EM L1 | tooling-and-testing.md (TT-25) |
| Unattended new game | TT-27, NG-J2, NG-F10 | newgame.md (NG-J2) |
| Mutagen pin | TT-17, VM-35, NG-H1, Int T1, EM tools 3.1 | tooling-and-testing.md (TT-17) |
| Spriggit diffs | TT-15, TT-16, Int T6, Int T7 | tooling-and-testing.md (TT-15) |
| xEdit error gate | TT-18, Int T3, Int T4 | tooling-and-testing.md (TT-18) |
| Material oracle (SFME) | TT-42, AP-26 | asset-pipeline.md (AP-26) |
| Bethesda tools on the player's PC | TT-13, AP-50, REL-03, REL-10, Lau T4, Lau L3, EM M1 | launcher.md (T4, L3) technical; REL-10 legal |
| Bundling third-party tools | AP-51, REL-03, Int T17, Lau B4 | asset-pipeline.md (AP-51) |
| CALUMI licence | REL-05, Door J39 | release-community-legal.md (REL-05) |
| Licence split | REL-01, Lau D8, Door J38, NG-G6 | release-community-legal.md (REL-01) |
| Contact Bethesda | REL-30, Lau D6, Lau L2, Int P3, NG-G3 | release-community-legal.md (REL-30) |
| Contact Nexus | REL-31, Lau L1, Lau D5, Int P3 | release-community-legal.md (REL-31) |
| Internet use | REL-32, Lau D7, Lau A5 | release-community-legal.md (REL-32) |
| DLC ownership | REL-56, MG-25, Lau L2b, Lau S10 | release-community-legal.md (REL-56) |
| Naming and trademarks | REL-25, Lau L5 | release-community-legal.md (REL-25) |
| Donations | REL-37, Lau L6 | release-community-legal.md (REL-37) |
| Acceptance screen | REL-15, Lau L7 | release-community-legal.md (REL-15) |
| Add-ons on the core | REL-21, REL-22, Lau D13, Lau M4 | release-community-legal.md (REL-21) |
| FormID determinism and lock file | REL-21, Lau B1 to B3, Lau L4 | launcher.md (B1, B2) |
| Hosting | REL-34, NG-G4, Lau D5, Lau L9, REL-38 | release-community-legal.md (REL-34) |
| AI disclosure | REL-57, Lau D12 | release-community-legal.md (REL-57) |
| Code signing | REL-36, Lau D11, Lau A3 | launcher.md (D11) |
| Tester pool and labels | TT-36, TT-37, TT-38, REL-42, REL-43, Int X9 | tooling-and-testing.md (TT-37) |
| Outreach to tool authors | PS-33, AP-53, REL-33, MG-04, Int P11, EM L4 | release-community-legal.md (owner-only outreach) |

## Conflicting recommendations

Each row quotes both sides. None is settled here.

1. **SFSE required or data-only core.**
   - TT-39: "require CK and SFSE for release 1, Game Pass out of scope until TT-04 lands".
   - TT-04: "yes, SFSE optional per system; it is the cheapest to maintain and keeps a Game Pass tier possible".
     VM-17: "a data and Papyrus core with SFSE features as optional add-ons". PS-35: "SFSE-free base, optional SFSE
     modules". AP-45: "keeping SFSE optional ... data-only survives patches better".
   - AP-20: "SFSE glTF players for idles and scenes first ... SFSE is allowed". EM decision 3: "menus, radio outside
     Wwise and a faithful VATS need it".
   - [Added 2026-10-19] Job 34 census (verified, papyrus-and-script-extenders.md on PR #404): only 36 of the 229
     missing FO4 script functions are engine natives; the rest port as our scripts. The natives FO4 calls most are
     dismemberment, AddSpell, Pip-Boy and SPECIAL menus, cleared locations and workshop. Dismemberment is VM-40.
   - What it means: TT-39 and AP-20 lean toward SFSE now; TT-04, VM-17, PS-35 and AP-45 keep it optional. VM-17 is
     the one decision that settles all of them.

2. **Medium masters for interiors.**
   - VM-25: "medium masters only for interior clusters under 65k records". TT-19: "interiors fit in clusters under
     65k records".
   - Int X2: "should interiors be split into medium masters? Not for us: FO4Port.esm holds about 600k records and must
     stay a full master". Int X2 also still describes "the conflict over the medium master's limit (65,535 forms per
     Bethesda, ObjectIDs up to 0xFF per one MO2 plugin)", which TT-19 and VM-25 call answered (65,536 ObjectIDs; 0xFF
     is the slot count).

3. **Which Fallout 4 data to accept first.**
   - Lau D1: "1.10.163 first (what the owner has), then add 1.11.240 once a record diff shows how far it differs".
   - VM-01: "accepting 1.10.163 and the current Steam runtime (1.11.240) through data-version detection, once VM-02
     and VM-03 show the size of the difference". AP-52 / AP-54: "accepting 1.10.163 and 1.11.240 data with detection".
   - Both wait for the record diff. They differ on whether 1.11.240 is in the first release.

4. **Does the Starfield CK EULA give an approval route for cross-game mods?**
   - REL-30: "the Starfield CK EULA names an approval route for cross-game mods". REL "In short" and REL-30's
     recommendation rely on it.
   - Lau D6 correction: clause (ii) "ends 'to be distributed through Bethesda Creations ...', so it is the
     paid-Creations route only". Lau L2: "clause (ii) is paid Creations only".
   - Both still lean toward a written contact. The reason given differs.
   - **Resolved 2026-10-19:** release-community-legal.md now carries the correction (clause (ii) is paid Creations only;
     REL-30 keeps the written contact, with the reason "no licence text covers what we do").

5. **Bethesda tools in the build.**
   - TT-13: "use the player's CK install (already allowed); revisit open tools only if CK install friction shows".
     AP-50: "CK required". TT-39: "require CK".
   - Lau L3: "The cleaner route: our own BA2 packer (the 0BSD `ba2` crate, T4) and the community Papyrus compiler
     Caprica, so the build calls no Bethesda tool at all".
   - NG-H7: "Official Papyrus compiler only (Caprica unproven in game ...). Already our route."
   - REL-10 lists both routes without a recommendation.

6. **Crash logger.**
   - TT-23: sf-crash-logger had "four releases in one month, last v0.4.0 on 10 Jul 2026"; recommend it "for test
     runs ... Engine Fixes' logger as the player default".
   - Lau A12: "sf-crash-logger is GPL-3 and the most detailed but has no releases"; "Trainwreck is 'all rights
     reserved' ... reported not logging in 2026".
   - VM-33 options: "Trainwreck (version-independent); Starfield Engine Fixes' logger".

7. **Nexus AI disclosure.**
   - REL-57: "the AI-Generated Content tag, with the agent-prefixed commit history as evidence".
   - Lau D12: "a plain AI-assisted disclosure on the release page".

8. **Code signing.**
   - REL-36: "published hashes, a VirusTotal link and source builds first; signing later".
   - Lau D11: "apply to SignPath Foundation (free for open source); paid signing only if it refuses".

9. **Save promise.**
   - VM-14: "no promise before 1.0, stated in every changelog". REL-51: "no save promise before 1.0".
   - Lau D9: "0.y.z with a 'save compatible: yes/no' line per release; the launcher blocks a core swap under a save
     when same-ids says IDS_DIFFER".
   - These can coexist, but the defaults read differently on a release page.

10. **Mutagen version.**
    - TT-17: Synthesis pins 0.54.4, "a data point for staying on stable 0.54.4".
    - NG-H1: "We build on 0.55.0-alpha.67; alpha.75 came out 19 Oct; stable is 0.54.4". Door E22 and EM tools 3.1 use
      alpha.67. Int T1 tests "alpha.67 to alpha.75".
    - All agree to pin one version. They point at different lines.

11. **Wwise free terms.**
    - REL-04 / AP-30: "free trial is non-commercial with a 200 media-asset limit".
    - Door F27: "a Non-commercial key covers 'totally free games (no monetisation at all)' with no asset limit".
    - The two may describe different licences (trial and Non-Commercial key). Both send the per-player question to
      Audiokinetic.

12. **Plugins.txt handling.**
    - NG-L1: "how we keep the prompt from switching us off (separate profile or launcher swap instead of editing their
      Plugins.txt)".
    - Lau T5: "re-assert our own lines before each launch, never move plugins we don't own".

13. **The ship.**
    - WP-27: "fence the ship out for v1".
    - NG-B4: "`MQ_TutorialQuest` fails silently with no `PlayerShip.GetShipRef()`"; No Ship Fast Start "makes a hidden
      placeholder ship".
    - Not opposite defaults. Fencing the ship out still needs NG-B4's answer.

14. **Takedown evidence.**
    - REL-16: searches "found no verifiable case".
    - NG-G5: "A press report (not primary, unverified) says Bethesda sent a cease-and-desist this month to an AI-built
      Fallout project."
    - Not contradictory as labelled, but REL-16 does not mention NG-G5's report.

15. **Stale status on CK switches.**
    - EM "PC check" (job 18, verified): the Starfield CK names `-CompileFaceFXAnims` and `-GenerateSEQ`, and has "No
      `-GenerateLips`".
    - NG section M: "lip, SEQ and precombine switches unresolved". TT experiment 1 and AP experiment 6 still plan the
      strings scan. PS-31 lists "drive the CK" without the switch name.
    - [Added 2026-10-19] Precombines: wave 2's "no bake step" (TT-10, VM-26 marked answered, AP-48, WP-33) conflicts
      with Int T9: the Starfield CK has the GUI actions "Generate Precombined Visibility for Current Cell" and "... All
      Loaded Cells" (no precombine or previs switch). Those files now carry corrections; VM-26 is open again; what the
      bake writes and whether it matters for performance is unresolved. `-MockWorldSpaceLOD` waited on job 20, which
      settled it: it exists in the Starfield CK (verified, job 20), usage "-MockWorldSpaceLOD:(ESMFilename)
      (WorldSpaceName0) [WorldSpaceName1] [...]".

16. **Update check timing in the launcher.**
    - Lau D7: "update check only on the player's click". Lau A5: "check at start only".
    - REL-32: "GitHub build allowed an opt-in update check".

17. **[Added 2026-10-19] Disagreements inside the phase files** (found by the Questions page thread; sent to the
    owning threads, which settle them in their own files):
    - Int C5 versus Door E22 on `PlacedObject.Lock`.
    - Door J40 versus door-animations.md's own lesson 9 on Creations.
    - NG-C2 still says "on leaving the Lodge", which the file's later sections no longer support.
    - Mechanics notes: Tools 6.1, 6.2 and 3.5 and UI 1.2 disagree with other files' answers.
    - Fixed in the cross-cutting files the same day: TT-08, AP-40 and PS-08 now all read "proven offline, in game
      open" for lip sync (the note had landed on PS-01); WP-40 now points at MG-14's partial answer.

## Experiments that close questions in several files

Ranked by how many questions across files each one closes or narrows. Kinds: **offline** (cloud, repo, files we
have), **PC read-only** (reads files on the PC, writes nothing in the game), **PC in-game** (runs the game, owner's
word). Counts include "narrows". "Feeds" are not counted.

| Rank | Experiment | Kind | Closes or narrows | Count |
|---|---|---|---|---|
| 1 | Licence reading pass: GPL-3 s6, Wwise EULA, DirectXTex, xEdit/BSArch, Address Library, CALUMI, game EULA, MSA, video policy, Donation Points, Creations AI rule, Steam Community-Made Mod rules, CK EULA on the PC. Partly done in Lau eula.md | offline (CK EULA: PC read-only) | REL-02, REL-03, REL-04, REL-05, REL-07, REL-09, REL-11, REL-23, REL-28, REL-37, REL-59, AP-51, Door J39, Int P1, Int T17 | 15 |
| 2 | Frame time, VRAM and RAM at 3 fixed spots (downtown, wasteland, interior), vanilla vs core vs core-with-LOD; route walk 4 passes; texture caps halved; 5-shot screenshot noise floor | PC in-game | WP-31, WP-33, WP-36, TT-29, TT-31, TT-34, VM-26, VM-27, VM-28, VM-29, AP-25, AP-48, Int E1, Int T10 | 14 |
| 3 | One converted choice scene: three list variants, a shared-silent-WEM line, an angry line, VTYP ANAM on and off, an SGE greeting quest with and without our `.seq` | PC in-game | PS-01, PS-03, PS-07, PS-12, PS-13, PS-31, AP-44, AP-45, NG-I2, NG-I5, EM quests D2, D3, V5, D6 | 14 |
| 4 | First fresh new game: newgame's first in-game proof plus WP's local-time read and `GetDayLength()` | PC in-game | NG-A4, NG-A5, NG-A9, NG-B2, NG-B3, NG-B5, NG-B7, NG-C1, NG-C2, NG-C6, NG-C7, NG-M1 (hunger check), WP-18, WP-19 | 14 |
| 5 | 1,000-line FaceFX run from a space-free staging folder: time, resume, 20 lines twice for hashes, WAV only; also `LipGenerator.exe` direct and `-CompileFaceFXAnims` (EM job 18) | PC, writes to a scratch folder | PS-08, PS-09, PS-10, PS-11, AP-40, AP-41, AP-42, AP-43, TT-08, EM quests L1, EM quests L2, EM X5, NG-H10 | 13 |
| 6 | CK session: load our ESM, batch navmesh on 3 cells and a Pathing Test, `-MockWorldSpaceLOD` on a 4-cell test worldspace (`.esm` vs `.esp`, timed), then 64 cells | PC, writes test data | TT-07, TT-10, TT-11, TT-35, TT-41, WP-45, AP-47, AP-59, Int N9, Int T8, Int T11, Int E10, Int X1 | 13 |
| 7 | Synthetic limits spike: 5 GiB BA2, two numbered archives, medium master near 60,000 records, Engine Fixes BA2 counter; loose vs v3 texture BA2 | PC in-game | WP-34, TT-19, TT-21, TT-22, VM-23, VM-24, VM-25, AP-55, AP-58, Lau T3, Int X3, Int E11 | 12 |
| 8 | Current Steam FO4 install: first 8 bytes of each `Fallout4 - *.ba2` and `cc*.ba2`, `.esm` hashes and sizes, `cc*` list, DLC files present, language files, CK exe version; plus the synthetic v7/v8 fixture and one-line `ba2.py` fix | PC read-only, plus offline unittest | TT-06, TT-12, VM-02, VM-03, VM-04, VM-06, VM-07, AP-52, Lau S1, Lau S9, REL-54, REL-56 | 12 |
| 9 | Fallout4.esm record census: empty RNAM, monologue INFOs, emotion keywords, SMQN/SMEN events, reaction triggers, GetIsSex conditions, disabled refs, LVLI leaves, TERM depth, traps | offline | PS-04, PS-05, PS-13, PS-24, PS-30, NG-I3, NG-C8, Int C1, Int C3, Int C7, Int C9 | 11 |
| 10 | Determinism and save swap: build twice and diff FormIDs, then two PCs or varied settings; load one save across two builds | offline, then PC in-game | REL-21, REL-51, VM-14, Lau B1, Lau B3, Lau B5, Lau I6, Lau I7, Door E24, Int P8 | 10 |
| 11 | Spriggit `serialize` and `standardize`, Mutagen round trip on current ESMs, on 0.54.4 and the alpha line | offline (Int T7: PC run) | TT-15, TT-16, TT-17, VM-35, NG-H1, Int T1, Int T6, Int T7, TT-18 | 9 |
| 12 | Diff every Starfield record we override and every vanilla path we reference across 1.16.236, .242, .244 | offline | WP-35, VM-08, VM-09, VM-11, VM-34, TT-02, AP-03, NG-J5, Lau T10 | 9 |
| 13 | Planet and component census of Starfield.esm, ShatteredSpace.esm, SFBGS00x; layers and LOD flags of a vanilla unique overlay | PC read-only | WP-05, WP-09, WP-10, WP-24, WP-44, WP-45, TT-41, AP-59 | 8 |
| 14 | Plugins.txt and `Starfield.ccc` diff before launch, at the menu, after the first save load; on patch day also the CK version and a 1.16.244 save | PC in-game | VM-10, VM-13, VM-15, TT-05, TT-12, Lau T5, NG-F7, NG-L1 | 8 |
| 15 | One `Debug` probe launch with remote debugging on: the TT-25 list via `cgf`, a DAP client reads one variable | PC in-game | TT-25, TT-26, NG-J3, EM L1, TT-27, TT-33, NG-J2 | 7 |
| 16 | Crash logger A/B on the Havok assert (vault cart case), plus a second different crash | PC in-game | TT-23, VM-33, Lau A12, Int T16, NG-H9, TT-24, TT-32 | 7 |
| 17 | Record-level diff of base and DLC masters, 1.10.163 vs 1.11.240 (after rank 8) | offline | VM-01, VM-02, VM-06, AP-52, Lau S3, Lau D1 | 6 |
| 18 | Whole or 15-cell build with peak disk, peak RSS and time; then a memory cap and fewer cores | PC or cloud VM | AP-49, VM-30, VM-31, Lau B9, NG-H11, TT-34 | 6 |
| 19 | Repo audit: Mutagen-linked binaries, CK tool calls, SFSE and runtime-address calls (VM E8), codsworth_voice.py reachability, guard over a mock release zip | offline | REL-01, REL-10, REL-24, REL-27, VM-17, VM-18 | 6 |
| 20 | Non-English pass: synthetic German STRINGS through the writer; one build from a non-English FO4 STRINGS set and voice folder through FaceFX | offline, then PC | REL-54, REL-55, VM-04, VM-39, PS-36, Lau S4 | 6 |
| 21 | Read xEdit FO3/FNV definitions (DOOR/XTEL, CLMT/WTHR, CREA, perk entry points) and write mapping tables | offline | MG-11, MG-13, MG-16, MG-21, MG-24, WP-41 | 6 |
| 22 | Face probe: new NPC_ with custom morphs and no facegen; the same after both CK bakes; a Use Traits NPC; an FO4 head as ARMO speaking | PC in-game | PS-15, PS-16, PS-17, AP-09, AP-10 | 5 |
| 23 | One terrain-only island overlay registered by `EOVR` alone, `GNAM` 2.63, 0 m water in an Ocean biome, one map marker | PC in-game | WP-08, WP-17, WP-23, WP-26, WP-28 (feeds MG-15, NG-B5) | 5 |
| 24 | Offline NAVM reachability checker between door markers | offline | TT-35, Int X6, Int N3, Int P5 | 4 |
| 25 | Load Fallout3.esm and FalloutNV.esm with Mutagen and xEdit: unread subrecords, SCTX filled, skill-condition counts | PC read-only | MG-08, MG-20, MG-22 (feeds MG-07) | 3 |
| 26 | Terrain-only landings stress test | PC in-game | WP-42, MG-17, MG-15 | 3 |
| 27 | Read-only dump of both games' `skeleton.nif` | offline if reachable, else PC read-only | PS-20, AP-06 (feeds PS-19, PS-21, AP-08) | 2 |
| 28 | WwiseConsole on the CK's `Starfield.wproj` without the GUI | PC, writes test data | AP-30, TT-09 (feeds AP-50) | 2 |
| 29 | SFME export of vanilla materials diffed with our `.mat` | offline | TT-42, AP-26 | 2 |

Not ranked, because they close nothing until someone answers: **draft letters to Bethesda, Nexus and Audiokinetic**
(offline drafting; the owner decides whether to send). They frame REL-04, REL-10, REL-19, REL-20, REL-21, REL-25,
REL-26, REL-30, REL-31, REL-32, REL-57, REL-58, AP-30, AP-50, Lau D6, Lau L1, MG-03, NG-G2, NG-I1 and Int P3.

Already done, so do not repeat: the CK strings scan for lip, SEQ, anim-info and compile switches (EM job 18). The
open part is face-bake switches (AP experiment 6) and precombine strings (Int T9). [Update 2026-10-19: job 20 found
`-ExportFaceGenData` in both CKs (bake or export only is unresolved) and no precombine or previs switch in the
Starfield CK, only the GUI actions (Int T9).]

## Owner decisions by phase

**Owner's answers recorded 2026-10-19** (submitted 21:37Z on the Questions page; full copy
/mnt/project-files/research/framework-page/submissions/2026-10-19-owner-answers.md). The last column holds the
page answer for each row; "(changed)" means the owner picked something other than the recommendation or answered
one that had none. The 25 "talk through first" items were all decided with the owner in this thread
(21:52Z to 22:07Z); "(talk)" marks them. Each cross-cutting question carries the same answer
and the owner's note in its Status line. RE-7 and RE-8 were settled in the talk-through: ship no assets and send Bethesda an informational letter
first (drafted by Claude, sent only on the owner's approval of the exact text). On the RE-1 note: nobody has
contacted Bethesda or Nexus; nothing goes out until the owner approves the exact text. Ten page questions that
had no row here were added at the end of the table.

**Forward priority (owner decision, 2026-10-19 23:19Z and 23:24Z):** "let's continue work towards my second idea of a stalker gamma style thing because that has more value of being made without the stuff with legal implications" and "I still want to get the stories working let's continue where we're at but forward focus on building these other things first instead of the other one for now". So: the GAMMA-style combined core (settlements, factions, a connected wasteland) is the forward focus; story work continues where it stands but comes second for now. The approved phases (new game, doors, interiors, launcher) stay in order as shared foundations, with the core's design and PC-free groundwork beside them. The GAMMA-style combined core thread owns [combined-core.md](combined-core.md) and combined-core-notes/.

What the answers change on the critical path (inference from the answers, not tested):
- **LA-7 Require all DLC:** the launcher refuses a Fallout 4 install without every DLC. The owner's own FO4 data
  holds only DLCRobot and DLCworkshop01 (project notes), so a full DLC install is now a precondition for any
  end-to-end launcher test on their PC.
- **NG-1 / VM-17 decided in the talk-through: SFSE required.** The gate is settled: SFSE-based UI, Pip-Boy and
  door hooks are allowed from phase 1, the launcher blocks the game when a patch breaks SFSE, and Game Pass players
  are excluded (SFSE does not support it). FS-6 dismemberment becomes our first own SFSE plugin.
- **NG-13 Fallout-style HUD and NG-20 in-game menu entry:** both add UI work to phase 1 (new game) that the
  recommended "as is" path did not have; how they are built depends on the same SFSE talk (NG-1, NG-11).
- **IN-9 rebuild terminal unlocking now** and **IN-7/IN-8/IN-10 converted loot, FO4 levels, refills:** the
  interiors phase grows from walkable cells to working terminals and leveled lists.
- **RE-10 wait for a fuller game:** no "walkable world" public release; the first release moves behind people
  and story. **PE-3 our own face-file writer:** a face-file format spike moves ahead of the people phase.


This table is the authoritative list of owner decisions for the framework (the Questions page reads it). Answers the
owner submits are recorded here and on the question in its own file.

"Needed by" names the first phase that cannot move without the decision and the point where it is needed.

| Decision | IDs in every file | Needed by | Owner, 2026-10-19 |
|---|---|---|---|
| Data-only core, SFSE optional or required | VM-17, VM-18, TT-04, TT-39, PS-35, AP-20, AP-45, NG-D1, EM decision 3, EM companions R2 | New game, before the Pip-Boy and UI plan (NG-D2); Door animations before door hooks ship | NG-1: SFSE required, block when broken (talk); NG-17: Our own silent voice files (talk); PE-2: SFSE glTF players first, .af later (talk) |
| MQ101 end state and the MQ101Debug route | NG-A5, NG-M3 | New game, after NG-M1 and NG-M2, before the first in-game proof | NG-2: Set the debug setting ourselves (changed); NG-3: Stopped (talk) |
| Start quest: fixed, hub or selector; start-world hook | NG-A10, NG-A11, MG-18, MG-28 | New game, before the start quest's design is frozen | NG-8: Vault 111, start-world hook built in |
| Ship or no ship | NG-B4, WP-27, MG-15 | New game (tutorial quest needs a ship ref); World before travel is built | NG-9: No usable ship, fenced out (talk) |
| Character creator scope, SPECIAL, quick start | NG-C3, NG-C4, NG-C9, NG-K7 | New game, before the first in-game proof | NG-4: Looks only (changed); NG-5: At a vault terminal (talk); NG-6: Yes, in phase 1 (changed) |
| Pip-Boy, cog door, HUD | NG-D2, NG-D3, NG-D4, NG-K6, EM X6, EM UI 1.1 to 1.3, EM L3, EM L5 | New game (phase 1 minimum); Fallout systems for the full Pip-Boy | NG-11: None yet (talk); NG-12: Console opens it, as now (talk); NG-13: Fallout-style reskin (changed) |
| Published vault-exit stages | NG-B8, NG-K5 | New game, before later phases listen to them | NG-14: Yes, fixed stages as a contract |
| Voice policy and codsworth_voice.py | REL-26, REL-27, MG-03, NG-G2, NG-I1, Int P2, EM decision 1, EM quests A1 | New game (voiced opening); People and story before any voice work; Release before any build | RE-1: No: subtitles only, for now; owner 22:38Z: FO3 and NV voice reuse known nos (22:54Z), FO4/76 open until Bethesda answers |
| AI voice; new voice; voiced-player option | REL-28, REL-58, PS-32, PS-37, EM quests A2 | People and story, before bridging lines are planned | RE-2: No new voice in early releases; RE-3: FO4 player lines, unchanged only |
| Dialogue UI: prompt or full line, own SWF | PS-01, PS-02, PS-03, NG-I2, EM quests D2, D3 | New game, before the first converted scene | NG-16: Full line, no own menu file |
| Silent voice route | PS-07, AP-45, NG-I5 | New game, before text-only lines ship | NG-1: SFSE required, block when broken (talk); NG-17: Our own silent voice files (talk) |
| Named-cast faces, face values, outfits | PS-15, PS-18, PS-19, AP-07, AP-10, NG-M9 | People and story, after the face probe | PE-3: Our own face-file writer (changed); PE-4: Ship values, bake on player's PC only (talk); PE-5: Converted FO4 outfits (changed) |
| Companion commands; fence Starfield companions | PS-22, PS-25, EM companions C1, F2 | People and story, before companion conversion | PE-6: Dialogue orders first, command mode later; PE-7: Fence them out |
| Animation route (SFSE glTF or `.af` retarget) | AP-20, EM animation B1, B2 | People and story and Fallout systems, before idles and creatures | NG-1: SFSE required, block when broken (talk); PE-2: SFSE glTF players first, .af later (talk) |
| Power armor route; VATS shape | EM character A1 to A4, EM UI 11.1 | Fallout systems, at design start | FS-5: Full VATS (queue shots on limbs) (changed) |
| Contact Bethesda and Nexus; what to ask | REL-30, REL-31, Lau D5, Lau D6, Lau L1, Int P3 | Release, before the Nexus upload; REL-52 puts the first public release after it | RE-7: Ship no assets; ask Bethesda first (talk); RE-8: Informational letter, specific questions (talk); RE-9: Yes, written questions first |
| Outreach to community and tool authors | REL-33, PS-33, AP-53, MG-04, Int P11, EM L4 | People and story (PS-08 is the largest unknown); Multi-game before FO3/NV work | RE-4: Yes, all the named authors |
| Licence split and source delivery; CALUMI (LGPL-3) shipped or user-supplied | REL-01, REL-02, REL-05, REL-08, Lau D8, Lau L8, Door J38, Door J39, NG-G6 | Launcher, before the first binary release | DA-6: Player supplies the DLL (changed); LA-2: Bundle permissive and (L)GPL tools; LA-11: MIT launcher plus separate GPL-3 tools; LA-12: Source zip on the same release; LA-13: Copy where useful, mark GPL-3 (talk) |
| Build-from-own-install policy; derived data | NG-G1, REL-19, REL-20 | Door animations (derived timings); New game (FO4 strings); before any release | DA-1: Generate everything at build time; DA-2: Build FO4 text from player's files; RE-7: Ship no assets; ask Bethesda first (talk) |
| Bethesda tools on the player's PC; bundling | TT-13, AP-50, AP-51, REL-03, REL-10, Lau T4, Lau L3, Int T17 | Launcher, before the build pipeline is fixed; All interiors (REL-10) | LA-1: Player's own Creation Kit; LA-2: Bundle permissive and (L)GPL tools |
| Wwise | AP-30, REL-04, TT-09, Door F27 | People and story, before any `.wem` conversion | DA-4: Allow new sounds after licence check (changed); PE-1: Yes, after Audiokinetic confirms in writing |
| Fallout 4 data versions | VM-01, AP-52, Lau D1, Lau S5 | Launcher and New game, after the VM-02 diff | LA-3: 1.10.163 now, add 1.11.240 after diff (talk); LA-4: Accept depots, merge in fixed order (talk) |
| Fallout 4 stores and CC files | VM-05, VM-07, AP-54, Lau D2, Lau S7, MG-25 | Launcher, before detect is released | LA-5: Steam, then GOG; refuse others; LA-6: Opt in per file (talk); LA-7: Require all DLC (changed); RE-12: Steam only for v1, say so (talk) |
| Languages | PS-36, REL-54, VM-39 | Launcher, after one non-English test; Release support matrix | LA-8: English first, pass through 4 more |
| DLC ownership | REL-56, MG-25, Lau L2b | Launcher; World before Far Harbor and Nuka-World | LA-5: Steam, then GOG; refuse others; LA-7: Require all DLC (changed); LA-17: One-time screen plus plugin marker |
| Starfield update policy and pin | TT-01, VM-12, VM-19, Lau D3, Lau T1, NG-F3, NG-L9, Int P7 | Launcher, before the first public build | LA-15: Refuse until we list it as good; LA-16: Refuse, advise 'update only when launched' |
| Support matrix and patch-follow promise; patch-day duty | VM-36, VM-37, TT-02, Lau L11, Lau A5b | Release | RE-13: "Use previous build"; no time promise |
| Game Pass | VM-21, REL-11, Lau D2, NG-F9 | Release, after the SFSE decision | LA-5: Steam, then GOG; refuse others; RE-12: Steam only for v1, say so (talk) |
| Save promise and save versioning | VM-14, REL-51, Lau D9, NG-F5, NG-L2, NG-L4 | New game (save version from v1); Release | NG-15: Yes, and launcher blocks unsafe swaps; NG-22: No promise before 1.0 |
| Plugin type per output plugin | VM-25, NG-H5, Int X2, Lau M3, EM decision 9 | All interiors and World, before any release (type cannot change) | IN-1: main plugins stay normal (full); small add-ons decided when there are any (confirmed in talk) |
| Internet use and updates | REL-32, Lau D7 | Launcher, before the Nexus build | LA-18: Offline; update check on click |
| Code signing | REL-36, Lau D11, Lau A3 | Launcher, before the first binary release | LA-14: Hashes now, apply to SignPath |
| How the player picks our game; undo | NG-F1, NG-F4, Lau D4, Lau I4 | Launcher and New game, before public install | NG-20: In-game menu entry (changed); NG-21: Own install, snapshot and restore |
| Host planet, planet master, add-on or total conversion | WP-01, WP-02, WP-04, REL-12 | World, after the census and island probe | WO-1: Earth if the probe works, else clone; WO-2: Own small planet master; WO-3: Add the planet, keep Starfield; strip step by step (talk) |
| Layout, Nuka-World site, day length, outer ring | WP-14, WP-15, WP-16, WP-18 | World, before Far Harbor and Nuka-World landings | WO-4: Real coordinates (talk); WO-5: Lore location, if FO4 data gives one (changed); WO-6: Procedural Earth biome (talk); WO-7: Real 24 hours |
| First public release | WP-38, REL-52, REL-44, Int P6, REL-50 | Release; All interiors for the interiors milestone | RE-10: Wait for a fuller game (changed); RE-11: Closed tester beta; RE-22: No dates; "what works now" |
| Story cells, loot, level bands, terminal locks, respawn, first combat room | Int C2, Int C3, Int C4, Int C6, Int C10, Int C11 | All interiors, step E | IN-6: Ship as walkable scenery (changed); IN-7: Converted FO4 items (changed); IN-8: FO4's levels per location (changed); IN-9: Rebuild now (changed); IN-10: Yes, refill like FO4 (changed); IN-11: Yes, that room (changed) |
| Crash logger | TT-23, VM-33, Lau A12 | Release; all in-game testing (TT-23 blocks it) | RE-5: Engine Fixes' crash logger |
| Debug whitelist | TT-25, NG-J3 | New game, before unattended runs | NG-10: Only the one probe list |
| Spriggit snapshot storage | TT-15 | All interiors and World, before build diffs are adopted | IN-2: Off GitHub, local or PC only |
| Testers, labels, review minutes | TT-36, TT-37, TT-38, REL-42, REL-43, Int X9 | All interiors (QA budget); Release | IN-3: Both (changed); IN-4: Changed-screenshot sheet only; IN-5: Cell, position, build hash (changed); IN-12: Add those two labels; IN-13: Small closed pool, clean profile |
| Naming, Pip-Boy art | REL-25, Lau L5 | Fallout systems (UI art); Launcher and Release (names) | RE-6: Fallout name and art (changed) |
| AI tag | REL-57, Lau D12 | Release, before the Nexus page | RE-2: No new voice in early releases; RE-14: AI-Generated Content |
| Add-on rules, pre-built packs | REL-21, REL-22, Lau D13, Lau M4 | Release | RE-15: Original data plus references only; RE-16: Pinned statement plus report template |
| Money and store listings | REL-37, REL-38, REL-59, Lau L6, Lau L9 | Release | RE-17: No money; no store before 1.0 (talk) |
| Community home, triage, contributors, succession, dates | REL-39, REL-40, REL-45, REL-46, REL-47, REL-48, REL-49, PS-34 | Release | RE-18: GitHub only (changed); RE-19: AI drafts, you approve in bulk; RE-20: Yes, sign-off plus asset records; RE-21: Name a second caretaker; RE-22: No dates; "what works now" |
| Game-neutral names and namespaces | PS-27, MG-26, MG-27, EM X4 | Fallout systems and People and story, now (cheap now, costly later) | FS-1: FO4 names, rename later (changed); FS-2: Yes: FO4SF_, FO3SF_, FNVSF_, shared FOSF_ |
| Reuse BACUP's GPL-3 code for three ideas (zero an unbuilt door's transition cell, keep FO4 lighting templates, per-quadrant land-texture layering) or write our own | AP-60, EM BACUP item | World, All interiors (comparison done 2026-10-19: nothing else to borrow) | WO-8: Reuse BACUP's code, GPL-3, with credit (talk) |
| Keep FO4 dismemberment (small SFSE plugin) or drop it | VM-40, EM job 34 census | People and story, after VM-17 | FS-6: Keep it with a small SFSE plugin (changed) |
| Multi-game timing, scope, rules | MG-01, MG-02, MG-05, MG-07, MG-09, MG-10, MG-12, PS-26, PS-28, PS-29, MG-19, WP-39, WP-40, MG-14 | Multi-game; MG-01 recommends a spike after phase 1 ships | MU-1: 1-week research spike after phase 1; MU-2: 76 story and places for the combined core; 1, 2, Tactics open (talk); 76 terms read: conflicts with ToS as written, waits on Bethesda (REL-60); MU-3: Two cores: per-game modules plus a combined all-games core (talk); MU-4: Own rules per game; superset in the combined core (talk); MU-5: Same planet, real relative positions; MU-6: Light flags only (dialogue variants) |
| Phase 1: recreate Kellogg scene, spouse pod, pod corpses and ring? [added 2026-10-19 from the page] | NG-K10 | Before the first in-game proof | NG-7: Leave all out of phase 1 (changed) |
| Lines that answer the player's unspoken words: keep, cut or rewrite? [added 2026-10-19 from the page] | NG-I3, PS-05 | Before the opening scenes are converted | NG-18: keep as text (blank, note: changes nothing) |
| Fence off Starfield content that starts its own quests (Shattered Space, Unity, NG+)? [added 2026-10-19 from the page] | NG-E3, NG-E4, NG-N2 | Before the first public start | NG-19: Block them (changed) |
| Do Vault 111's cog door and exit elevator stay with the new-game work? [added 2026-10-19 from the page] | Door 21 | Door animations, now | DA-3: Yes, new-game thread owns them |
| Outside doors: one animated door, or Starfield's elevator-style door pair? [added 2026-10-19 from the page] | Door 11 | Door animations, step C | DA-5: Team decides after the PC read (changed) |
| Rule out Bethesda Creations for good? [added 2026-10-19 from the page] | Door J40, REL-13 | Release | DA-7: Yes, never publish on Creations |
| What should the launcher look like: command line, window, or both? [added 2026-10-19 from the page] | Lau D10, Lau A1 | Launcher, before the window is built | LA-9: Command line first, then a window (talk) |
| Is Linux and Steam Deck a target? [added 2026-10-19 from the page] | Lau L10 | Launcher, before new build steps are written | LA-10: Not a target, keep it possible |
| Locks: use Starfield's digipick game, or build a bobby-pin game? [added 2026-10-19 from the page] | EM UI 7.1 | All interiors (locked doors and containers) | FS-3: Rebuild FO4's bobby-pin game (changed) |
| How should power armor work? [added 2026-10-19 from the page] | EM character A1, EM character A2, EM character A3, EM character A4 | Fallout systems, at design start | FS-4: Per game: worn suit (FO3/NV), climb-in (FO4, combined core) (talk) |
| Forward priority: GAMMA-style combined core first, stories continue but second for now | MG-01, MG-05, MG-07, MG-09, MG-10, PS-26, combined-core.md | All later phases; approved phases 1 to 4 stay as shared foundations | Owner, 23:19Z and 23:24Z: GAMMA-style core first (decided) |
