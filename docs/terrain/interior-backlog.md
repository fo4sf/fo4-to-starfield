# The interior conversion backlog: every interior a core load door leads into, ranked and measured

Author: Claude, 2026-10-16. Branch `claude/interior-backlog` (on main 51a162c). Status: **offline census, export,
ranking and dry-run conversion done; nothing deployed, nothing queued, no game launched.** Data:
[data/interior-backlog.json](data/interior-backlog.json) (all 203 interiors and the 27 behind them, every field below). Tool:
`scripts/terrain/interior_backlog.py` (tests: `tests/test_interior_backlog.py`).
Labels: **verified** = read from the files or commands named here; **supported** = supported hypothesis
(an extrapolation from measured numbers); **unresolved**. Offline checks are not in-game acceptance.

## Answer first

- **The backlog is 190 interiors behind 350 exterior load doors** (**verified**). The core's band exports hold 1,286
  exterior doors; 373 are load doors; 368 lead into 203 interiors; 18 of those doors lead into the 13 interiors
  `FO4Port.esm` (integ_1011) already converts; 5 lead into worldspaces, not interiors (Diamond City x2, Goodneighbor
  x1, and two Brotherhood vertibird doors that lead back into the Commonwealth). This reproduces the journal's count of
  2026-10-16 (373 / 18 / 355) from the files, with the tool.
- **Behind them, 26 more interiors not converted are reached only through other interiors** (**verified**, 43 load
  doors inside interiors, 46,068 references; section "Second hop" below): 19 behind backlog cells (29 doors, for example
  MassFusion02 behind rank 7 MassFusion01, seven Institute cells behind rank 79 InstituteConcourse) and 7 behind
  interiors FO4Port.esm already converts (14 doors, for example ParsonsState02 and 03 behind ParsonsState01). They are
  not ranked (no exterior door leads into them) and the totals below are for the 190 unless they say otherwise. With
  them the conversion needs **5,863 models** (306 more), about 15 minutes at the measured rate.
- **Conversion time is not the long pole** (**supported**). The 190 cells need **5,557 models** that integ_1011 has not
  converted (distinct over the whole backlog: the per-cell sum is 16,065, so shared kit pieces cut the work by 65%). The
  dry runs converted at **0.151 s per model** in fresh stagings, so the whole backlog's models are about **14 minutes**
  of conversion. A typical backlog interior already has 77% of its models converted (median). Placing the 384,378
  references is seconds per cell (PluginSpike: 1.5 to 2.2 s per run below).
- **The long poles are elsewhere**: the door gate (still open: commonwealth-build-plan.md section 1, item 2; the core's
  load doors and FO4Port.esm's interiors are separate plugins), the converter's open quality issues that apply to every
  converted cell
  (the owner's log, docs/owner/playtest-issues.md rows 1 to 6: door animations, skinned props, the impact crash), and
  in-game acceptance: batch_full planned 33 to 147 tests per converted cell (median 113) at a median of 61 s between
  results, about 1.9 hours of game time per cell, so about 360 hours for 190 cells at that depth, about 410 hours with
  the 26 second-hop cells (**supported**, read from `C:\Modding\testqueue\batch_full`, not run here).
- **Dry run of the top 3 smallest high-value cells** (ranks 8, 19, 20): 443 models in 86.8 s, **0 failures**, three
  plugins written. **The five interiors nearest the slice** (Sanctuary's Jahani basement and the four Concord cells,
  98 to 230 m from Red Rocket / Sanctuary) as one batch: 1,175 models in 157.8 s, **1 failure** (an effect-shader-only
  furniture mesh, the same failure class integ_1011 has 3 of), 7,056 references, one plugin with 5 cells.
- **Recommendation** (the owner's call): after the door gate passes, convert the near-slice batch first (measured
  above, ranks 14 to 17 and 99) because a walkable Commonwealth grows from Red Rocket, then follow the ranking.

## How it was counted

1. **Doors** (`interior_backlog.py doors`, **verified**): every reference of the 11 band exports
   (`terrain_core64c_work\export\band_*.json`, dotnet/Fo4Land `export-exterior`, 701,754 references) with a teleport
   destination. Its destination cell is the band's `teleport_dependencies` entry for it: the CELL record Fallout4.esm
   stores the destination door in (dotnet/Fo4Export/TeleportDependencies.cs walks every cell's temporary and persistent
   references, so this is the parent cell, not a guess from editor ids). Each door records whether the latest full
   build placed it (`terrain_core64g\objects.json`, by source key), its model kind (a visible model, an editor marker,
   or no model), its disabled flag and enable parent. Landmarks are read from the bands: the Red Rocket building
   `0211C0` and the Sanctuary map marker `072A48` (the references make_cw_overlays.py uses).
2. **Exports** (**verified**): each of the 203 destination interiors exported with the unchanged dotnet/Fo4Export
   (`export <EditorID>`, the way integ_1011's `<Cell>.json` were made; build.ps1 there reads `exports_1011\*.json`), 6.4
   to 7.3 s per cell alone (the three timed below), 568 s for all 203 (two, later four, at a time). Every destination
   door the census put in a cell is in that cell's export (the tool refuses otherwise). Repeat exports of the three
   dry-run cells are byte-identical. The exports in `exports_1011` were made by an exporter with one more field
   (`ragdoll`, from eafae4c on the `codex/xrgd-export` branch, not on main): 4 of RedRocket01's 795 references carry it
   (OilCan01, NukaColaEmpty, SkeletonBareBody01, SkeletonBareBodyHeadless); every other field of its references, its
   deferred placements and its teleport dependencies are identical to today's export. convert_batch and PluginSpike do
   not read the field, so no count here changes; the posed-props work (b9fa8b6, references with FO4 ragdoll data in
   their own pose) would need every export here redone with that exporter.
3. **Measures per interior** (`interior_backlog.py plan`): references, deferred placements (actors), lights, distinct
   models; the **convertible models** = the meshes `convert_batch.py --cell-json` converts for that export
   (`convert_batch.cell_candidates`, now one function both use: the default base types, no editor markers, no top-level
   `effects\`, no placed water planes `Water\`); how many integ_1011's `manifest.json` converted or failed; how many the exterior build converted
   (core64g's bases); how many no FO4 mesh archive holds; the load doors inside that lead on to other interiors.
   Check (**verified**): for each of the 13 converted cells, convertible = converted + failed in integ_1011 and new = 0,
   so the rule reproduces the integ build's model set exactly.
4. **Ranking** (the requested keys, in order): more exterior doors into the cell; then nearer to Red Rocket or
   Sanctuary, in 1 km rings of the straight-line distance from the cell's nearest exterior door to the nearer landmark
   (exact metres would leave the third key nothing to break); then the larger fraction already converted; then the
   exact distance. In rank order the JSON also gives `adds_models` (what the cell adds given every higher-ranked cell
   is converted first) and `cumulative_new_models`.
5. **Effort** per cell: `new_models`, `refs_to_place`, `actors_deferred`, `load_doors_in_cell` (every load door inside
   the cell, its exits back out included; `leads_to_interiors` has the ones that lead on), `convert_s_est` (new
   models x the measured 0.151 s) and a class, a judgment: **S** <= 300 references and <= 50 new models, **M** <= 1,500
   and <= 200, **L** <= 5,000 and <= 600, else **XL**. The backlog: S 35, M 68, L 65, XL 22.
6. **Enterable**: a cell is enterable when at least one of its exterior doors is not initially disabled and is placed
   by the core or is an `AutoLoadMarker01.nif` door (the converter never places marker models; decisions.md 2026-10-12
   writes those as Starfield's `AutoloadDoor_Cave`; other marker doors, such as `InvisibleDoor01.nif`, have no recorded
   path). Four backlog cells are not (below). The dry run takes the 3 smallest by references among the first 20 ranked
   cells that are enterable ("high value" = the top 20).
7. **Second hop**: from every measured export (backlog and converted), each load door into an interior no exterior door
   leads into is followed, and that interior exported and measured the same way, until no new interior turns up (here
   after hop 3; hop 1 = the cells exterior doors lead into; 27 exports, 78 s, the same Fo4Export build). Each such cell
   gets `reached_from` (the interiors whose doors lead into it), `hop`, `after_rank` (the rank of the earliest-ranked
   backlog cell it is behind; 0 = behind a converted interior), and `adds_models` / `cumulative_new_models` counted
   after the whole ranked backlog, in `after_rank` order.

## The ranking (top 30 of 190; all in the JSON)

Doors (placed) = exterior load doors into the cell (placed by core64g). Nearest m = straight line from its nearest
exterior door to Red Rocket or Sanctuary. Models = distinct models of the cell; Convertible = convert_batch's
candidates; Converted = of those, in integ_1011's manifest; New = neither converted nor failed there; Adds = new models
no higher-ranked cell already brings. Leads on to = interiors its own load doors lead into.

| # | Interior | Doors (placed) | Nearest m | Refs | Models | Convertible | Converted | New | Adds | Class | Leads on to |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | zInstituteRotunda | 8 (8) | 1328 | 2,774 | 382 | 370 | 258 (70%) | 112 | 112 | L | - |
| 2 | CorvegaAssemblyPlant01 | 6 (5) | 797 | 10,980 | 951 | 898 | 586 (65%) | 311 | 310 | XL | - |
| 3 | FaneuilHall01 | 6 (6) | 1837 | 4,431 | 677 | 649 | 500 (77%) | 149 | 144 | L | - |
| 4 | USSConstitution01 | 6 (6) | 1680 | 2,071 | 400 | 373 | 261 (70%) | 112 | 99 | L | - |
| 5 | TheaterHub360 | 6 (6) | 1929 | 1,455 | 404 | 387 | 186 (48%) | 201 | 187 | L | CTEST, ccTOSFO4001 |
| 6 | TheaterMassBayMedicalCenter01 | 5 (5) | 1958 | 3,101 | 632 | 599 | 457 (76%) | 142 | 102 | L | TheaterMassBayMedicalCenter02 |
| 7 | MassFusion01 | 5 (4) | 1765 | 10,195 | 769 | 732 | 528 (72%) | 204 | 143 | XL | MassFusion02 |
| 8 | CambridgeCollegeAdminBuilding | 4 (4) | 1135 | 571 | 205 | 194 | 165 (85%) | 29 | 20 | M | - |
| 9 | Financial14 | 4 (4) | 1852 | 694 | 242 | 232 | 194 (84%) | 38 | 26 | M | - |
| 10 | FensParkviewApartments02 | 4 (4) | 1684 | 930 | 275 | 256 | 186 (73%) | 70 | 53 | M | - |
| 11 | CambridgePlumbing01 | 4 (4) | 1198 | 660 | 203 | 195 | 133 (68%) | 62 | 57 | M | - |
| 12 | CTEST (no arrival) | 4 (0) | 1651 | 26 | 16 | 15 | 10 (67%) | 5 | 4 | S | TheaterHub360 |
| 13 | CambridgeMonsignorPlaza01 | 4 (4) | 1459 | 2,781 | 696 | 661 | 381 (58%) | 280 | 197 | L | - |
| 14 | ConcordSpeakeasy | 3 (3) | 181 | 859 | 296 | 283 | 238 (84%) | 45 | 34 | M | - |
| 15 | ConcordFactory | 3 (3) | 159 | 598 | 210 | 207 | 142 (69%) | 65 | 56 | M | - |
| 16 | ConcordCivicAccess01 | 3 (3) | 152 | 1,980 | 348 | 314 | 199 (63%) | 115 | 98 | L | - |
| 17 | ConcordMuseum01 | 3 (3) | 230 | 3,402 | 615 | 585 | 359 (61%) | 226 | 172 | L | - |
| 18 | ccZSEFO4002Interior01 (no arrival) | 3 (0) | 1200 | 5 | 2 | 1 | 1 (100%) | 0 | 0 | S | - |
| 19 | CambridgeEastCITRaiderCamp01 | 3 (3) | 1427 | 272 | 97 | 91 | 78 (86%) | 13 | 5 | S | - |
| 20 | FensCafeBuilding | 3 (3) | 1635 | 423 | 164 | 158 | 134 (85%) | 24 | 11 | M | - |
| 21 | LaytonTowers01 | 3 (3) | 1866 | 2,349 | 516 | 493 | 417 (85%) | 76 | 39 | L | - |
| 22 | CambridgePD01 | 3 (3) | 1150 | 2,154 | 463 | 429 | 360 (84%) | 69 | 26 | L | - |
| 23 | EastBostonPrep01 | 3 (3) | 1885 | 4,868 | 700 | 656 | 536 (82%) | 120 | 65 | L | - |
| 24 | GeneralAtomicsGalleria01 | 3 (3) | 1090 | 3,477 | 654 | 632 | 504 (80%) | 128 | 75 | L | - |
| 25 | Financial07 | 3 (3) | 1775 | 1,426 | 431 | 414 | 330 (80%) | 84 | 31 | M | - |
| 26 | DBTechHighSchool01 | 3 (3) | 1972 | 7,476 | 1,024 | 969 | 718 (74%) | 250 | 126 | XL | DBTechHighSchool02 |
| 27 | HardwareTown01 | 3 (3) | 1750 | 2,958 | 585 | 555 | 410 (74%) | 145 | 75 | L | - |
| 28 | MassPikeTunnel01 | 3 (3) | 1702 | 2,740 | 460 | 420 | 298 (71%) | 121 | 75 | L | - |
| 29 | WestonWaterTreatment01 | 3 (3) | 1168 | 5,996 | 746 | 717 | 507 (71%) | 209 | 88 | XL | - |
| 30 | TrinityChurch01 | 3 (3) | 1777 | 2,619 | 492 | 476 | 331 (70%) | 145 | 68 | L | - |

Cumulative new models along the ranking: top 10 1,196; top 25 2,066; top 50 3,052; top 100 4,434; all 190 5,557;
with the 26 second-hop cells 5,863.

The first key counts every exterior load door. The JSON's `entrances` counts distinct positions of the doors that are
not initially disabled; it differs for 5 cells: USSConstitution01 (rank 4) 6 doors / 4 entrances (two pairs of
stacked quest-state doors), BostonAirportRuins01 (37) 3 / 2, TheCastle01 (95) 2 / 1, InstituteConcourse (79) 2 / 0 and
InstituteReactor (158) 1 / 0. Ranked on entrances, USSConstitution01 would fall to rank 10; the ranking keeps the
requested key.

## Second hop: the interiors reached only through other interiors

27 interiors are reached only through the load doors of other interiors: 26 not converted (below) and `Vault81`
(converted in integ_1011, behind rank 108 `Vault81Entry`). After rank = reachable once that ranked cell is converted
(0: behind an interior FO4Port.esm already converts; FO4Port.esm does not hold the far end). Adds = models no ranked
cell and no earlier row brings.

| After rank | Interior | Hop | Reached from (doors) | Refs | Convertible | Converted | New | Adds | Class |
|---|---|---|---|---|---|---|---|---|---|
| 0 | MQ203KelloggsBrain | 2 | GoodneighborTheMemoryDen x2, PrewarVault111, Vault111Cryo | 1,923 | 316 | 178 (56%) | 137 | 40 | L |
| 0 | ParsonsState02 | 2 | ParsonsState01, ParsonsState03 | 2,848 | 595 | 480 (81%) | 115 | 17 | L |
| 0 | ParsonsState03 | 2 | ParsonsState01, ParsonsState02 | 2,139 | 449 | 299 (67%) | 150 | 11 | L |
| 0 | PrydwenHull03 | 2 | PrydwenHull01 | 111 | 53 | 53 (100%) | 0 | 0 | S |
| 0 | Vault11402 | 2 | Vault114 x2 | 4,248 | 579 | 520 (90%) | 59 | 40 | L |
| 0 | GoodneighborTheMemoryDen | 3 | MQ203KelloggsBrain x2 | 1,522 | 340 | 261 (77%) | 79 | 13 | L |
| 0 | PrewarVault111 | 3 | MQ203KelloggsBrain | 970 | 98 | 95 (97%) | 3 | 2 | M |
| 5 | ccTOSFO4001 | 2 | TheaterHub360 | 1 | 1 | 0 (0%) | 1 | 0 | S |
| 7 | MassFusion02 | 2 | MassFusion01 | 4,311 | 498 | 363 (73%) | 135 | 4 | L |
| 76 | SaugusIronworks02 | 2 | SaugusIronworks01 | 787 | 200 | 124 (62%) | 76 | 12 | M |
| 77 | RailroadHQ01 | 2 | OldNorthChurch01, RailroadHQEscapeTunnel | 1,542 | 410 | 269 (66%) | 141 | 44 | L |
| 79 | InstituteAdvSystems | 2 | InstituteConcourse, InstituteReactor | 626 | 71 | 13 (18%) | 58 | 6 | M |
| 79 | InstituteBioScience | 2 | InstituteConcourse, InstituteFEVlab x2, InstituteOldRobotics01 | 1,532 | 162 | 72 (44%) | 90 | 19 | L |
| 79 | InstituteCave | 2 | InstituteConcourse | 401 | 56 | 39 (70%) | 16 | 3 | M |
| 79 | InstituteOldRobotics01 | 2 | InstituteBioScience, InstituteConcourse | 2,641 | 407 | 235 (58%) | 172 | 22 | L |
| 79 | InstituteRobotics | 2 | InstituteConcourse | 222 | 23 | 8 (35%) | 15 | 5 | S |
| 79 | InstituteSRB | 2 | InstituteConcourse | 525 | 65 | 19 (29%) | 46 | 7 | M |
| 79 | InstituteFEVlab | 3 | InstituteBioScience x2 | 1,354 | 241 | 187 (78%) | 54 | 7 | M |
| 105 | RelayTowerInt15B | 2 | RelayTowerInt15A | 163 | 88 | 72 (82%) | 16 | 2 | S |
| 108 | Vault81Secret | 2 | Vault81, Vault81Entry | 3,989 | 557 | 514 (92%) | 42 | 23 | L |
| 108 | Vault81HoldingCell | 3 | Vault81 | 31 | 6 | 5 (83%) | 1 | 0 | S |
| 131 | TheBigDig01 | 2 | GoodneighborBobbisPlace, NHMFreightDepot01 | 7,631 | 869 | 622 (72%) | 247 | 17 | XL |
| 131 | GoodneighborBobbisPlace | 3 | TheBigDig01 | 614 | 229 | 194 (85%) | 35 | 4 | M |
| 137 | MedTekResearch02 | 2 | MedTekResearch01 x2 | 3,521 | 434 | 342 (79%) | 92 | 3 | L |
| 166 | FortStrong02 | 2 | FortStrong01 | 2,281 | 427 | 333 (78%) | 94 | 4 | L |
| 173 | RelayTowerInt17 | 2 | ShawHighSchool01 | 135 | 64 | 47 (73%) | 17 | 1 | S |

- **verified**: behind backlog cells 19 interiors, 29 doors, 32,307 references, 183 added models; behind converted
  interiors 7, 14 doors, 13,761 references, 123 added models. Every second-hop candidate model is in the FO4 mesh
  archives. Effort classes: S 6, M 7, L 12, XL 1.
- The seven Institute cells (after rank 79) sit behind `InstituteConcourse`, whose exterior doors are all initially
  disabled (not enterable, below), so they wait on the enable-parent work as well as on rank 79.

## The interiors nearest the slice

The ranking puts the door count first, so the cells next to Red Rocket sit at ranks 14 to 17 and the closest one at 99.
Seven backlog interiors lie within 500 m, 19 within 1 km, 61 within 1.5 km.

| Interior | Nearest m | Doors (placed) | Refs | New models | Converted | Rank | Class |
|---|---|---|---|---|---|---|---|
| SanctuaryBasementJahani | 98 (Sanctuary) | 1 (1) | 217 | 12 | 83% | 99 | S |
| ConcordCivicAccess01 | 152 (Red Rocket) | 3 (3) | 1,980 | 115 | 63% | 16 | L |
| ConcordFactory | 159 (Red Rocket) | 3 (3) | 598 | 65 | 69% | 15 | M |
| ConcordSpeakeasy | 181 (Red Rocket) | 3 (3) | 859 | 45 | 84% | 14 | M |
| ConcordMuseum01 | 230 (Red Rocket) | 3 (3) | 3,402 | 226 | 61% | 17 | L |
| GorskiCabin01 | 317 (Red Rocket) | 1 (1) | 623 | 42 | 81% | 100 | M |
| USAFSatellite01 | 428 (Red Rocket) | 1 (1) | 1,831 | 61 | 84% | 98 | L |
| WaldenPond01 | 549 (Red Rocket) | 2 (2) | 1,071 | 54 | 82% | 39 | M |
| Switchboard | 610 (Red Rocket) | 2 (2) | 3,274 | 142 | 76% | 42 | L |
| zLexingtonGarage | 667 (Red Rocket) | 2 (2) | 447 | 31 | 68% | 43 | M |

## Dry run (fresh stagings in `C:\Modding\scratch\interior-backlog`, nothing deployed)

Each cell: export (timed, compared with the census export), `convert_batch.py --cell-json <export> --limit 100000`
with the integ_1011 build's flags (`--starfield-data` for rigged doors and movable items; no `--resume`, so every
model converts), then PluginSpike into `<staging>\plugin`. The near-slice batch merges the five exports into one
`--cell-json`, as integ_1011's build.ps1 does. Code: main 51a162c plus this branch's refactor of `cell_candidates`.

| Cell (rank) | Refs | Export s | Models converted / attempted | Convert s (manifest) | s / model | Failures | Plugin: placed + lights, skipped | Plugin s |
|---|---|---|---|---|---|---|---|---|
| CambridgeEastCITRaiderCamp01 (19) | 272 | 7.2 | 91 / 91 | 28.3 | 0.311 | 0 | 240 + 7, 17 | 2.2 |
| FensCafeBuilding (20) | 423 | 7.3 | 158 / 158 | 28.3 | 0.179 | 0 | 324 + 9, 68 | 1.5 |
| CambridgeCollegeAdminBuilding (8) | 571 | 6.4 | 194 / 194 | 30.2 | 0.156 | 0 | 469 + 25, 47 | 1.5 |
| Near-slice batch: SanctuaryBasementJahani, ConcordCivicAccess01, ConcordFactory, ConcordSpeakeasy, ConcordMuseum01 | 7,056 | - | 1,174 / 1,175 | 157.8 | 0.134 | 1 | 5,548 + 254, 846 | 2.2 |

- **verified**: 0 failures in the three picked cells; 1 in the batch: `Furniture\Invisible\DeskTerminalFurniture01.nif`,
  "only effect-shader shapes (glass/glow), skipped" (integ_1011 has the same reason for 3 models).
- **verified**: the tool's placed / skipped counts equal PluginSpike's own log line for all 8 cells (the writer's rule:
  a reference is placed when its model converted; the COC marker and lights are counted apart; lights within 3 m merge).
- **verified**: PluginSpike linked no teleports in these builds ("destinations not in this build": 3, 3, 4 and 13): the
  far ends are exterior doors of the core, which a separate plugin holds. Joining them is the door gate.
- The near-slice batch converted 2 water planes (`Water\Water1024.nif`, `Water\TroughBathWater.nif`) with a fallback
  material; the exterior path leaves placed water out (exterior.py `WATER_RE`, an opaque sheet otherwise), the
  interior path did not (**verified** in the manifest). They do look wrong in game (owner playtest 2026-10-17, Vault 111
  gear pit): the plane draws as a flat grey sheet AND the player stands on it, because its L_WATER body is solid (see
  JOURNAL 2026-10-17). `convert_batch.cell_candidates` now drops placed `Water\` models like the exterior path does, so
  the "convertible = converted + failed" check above holds for integ_1011 and earlier builds, not for a rebuild: it
  no longer lists Water1024 (5 of the 16 interior exports place one).
- The rate varies with the models (0.31 s per model for the rubble-heavy raider camp, 0.13 in the batch); a run's
  seconds include opening the archives and templates once, so a batch costs less per model than single cells.

## Odd cells and limits

- **No arrival** (4 cells): `CTEST` (a 26-reference test cell, 4 doors) and `ccZSEFO4002Interior01` (5 references, 3
  doors). Their 7 exterior doors have `ccZSEF...` / `cEEJFO4002...` bases (FormIDs 0x24A1xx) whose base records carry no
  model, and the depot's archives hold no such meshes (**verified**: no `cc` / `cEEJ` path among 159,856 mesh names).
  They look like Creation Club hooks in this Fallout4.esm, not base-game interiors (**supported**). `TheaterHub360`
  (rank 5) also leads on into `CTEST` and `ccTOSFO4001`. `InstituteConcourse` (rank 79: `1868BC` AutoloadDoor and
  `1EB12C` InvisibleLoad01HiddenMinUse) and `InstituteReactor` (rank 158: `1EB12D` InvisibleLoad01HiddenMinUse): every
  exterior door is initially disabled (**verified** in the bands), and `InvisibleDoor01.nif` is not the AutoloadDoor
  path decisions.md records. Neither Institute cell is in the top 20, so the dry-run pick is unchanged.
- **Quest-gated doors**: all 8 exterior doors of rank 1 `zInstituteRotunda` have enable parents; 24 backlog doors have
  one, 4 are initially disabled. Enable parents are not translated yet (docs/CELL-EXPORT.md; build plan section 3), so
  the core places those 8 doors without their condition. Eight backlog editor ids start with `z` (Bethesda's habit for
  deprecated forms; whether these are reachable in the game as shipped is **unresolved**).
- **Missing models**: `HardwareTown01` places 2 models no FO4 mesh archive holds (`TempInsaneBricks`,
  `TempDiamondCitySpeaker01`); they would fail conversion. Every other backlog cell's candidates exist.
- **Interiors behind worldspaces or other interiors**: 3 of integ_1011's 16 interiors are not reached from the core
  at all: `DmndValentines01` (its doors lead into the DiamondCity worldspace), `GoodneighborHotelRexford` (Goodneighbor
  worldspace) and `Vault81` (reached through `Vault81Entry`, a backlog cell). 33 backlog cells lead on into further
  interiors (44 doors, the "Leads on to" column): of their 39 targets, 20 are ranked and 2 converted (they also have
  exterior doors); the other 17 are second-hop cells above (16 not converted, and `Vault81`).
- **Converted models**: 2,954 of the 5,557 new models were converted by the exterior build (core64g, `fo4core` prefix),
  so the converter handles them; FO4Port.esm would convert its own copies (another prefix, another archive).
- The ranking's distance is a straight line from the door, not a walking route. DLC interiors are not included (no
  DLC plugins in the depot). integ_1011 was converted at commit a5bc92e; the dry runs used main's converter.

## Reproduce

```
python scripts/terrain/interior_backlog.py doors --work <core64c work> --build <terrain_core64g> --out <scratch>\doors.json --cells-txt <scratch>\cells.txt
# each line of cells.txt (dotnet build -c Release in dotnet/Fo4Export first):
dotnet dotnet/Fo4Export/bin/Release/net9.0/Fo4Export.dll <Fallout4.esm> export <EditorID> <scratch>\exports\<EditorID>.json
python scripts/convert_batch.py --fo4-data <FO4 Data> --staging <scratch>\dryrun\<Cell> --content-resources <ContentResources.zip> --texconv <Texconvx64.exe> --collision-template <template.nif> --starfield-data <Starfield Data> --cell-json <scratch>\exports\<Cell>.json --limit 100000
dotnet dotnet/PluginSpike/bin/Release/net9.0/PluginSpike.dll <scratch>\dryrun\<Cell>\plugin <scratch>\dryrun\<Cell>\manifest.json <scratch>\exports\<Cell>.json   # STARFIELD_DATA=<Starfield Data>
# the near-slice batch: the five exports' refs merged into one {"cell": "merged", "refs": [...]} file, one convert_batch
# --cell-json <merged.json> into <scratch>\dryrun_batch\near_slice, then PluginSpike with that manifest and all five exports
python scripts/terrain/interior_backlog.py plan --doors <scratch>\doors.json --exports <scratch>\exports --manifest <integ_1011>\manifest.json --converted <integ_1011> --core-build <terrain_core64g> --fo4-data <FO4 Data> --dryrun <scratch>\dryrun\<Cell> ... --json docs/terrain/data/interior-backlog.json --md-table <scratch>\plan.md --next-cells-txt <scratch>\next.txt
# export each line of next.txt (the second-hop interiors without an export) the same way and re-run plan, until it is empty
```

The tool's placed / skipped count is in the JSON only for a staging named after its cell (the three single-cell dry
runs); the batch's per-cell counts were compared with its `plugin.log` outside the tool.

Inputs used (read-only): Fallout4.esm 330,745,373 B (sha256 ae7be31a..., the same file as the navmesh inventories),
the depot's `Fallout4 - Meshes*.ba2`, `terrain_core64c_work\export` (11 bands), `terrain_core64g\objects.json`,
`integ_1011\manifest.json` (sha256 in the JSON's `inputs`) and its 16 `<Cell>.json`.
