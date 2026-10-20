# Every interior: census, batch plan and staged batch builds

Author: Claude-cloud, 2026-10-19 (roadmap phase 3, "all interiors", approved by the owner 07:23Z). Status: **census
and plan done offline; build tooling written and unit tested; no batch built yet; nothing installed or queued.**
Labels as in docs/ai/research-log.md: **verified** = read from the files or commands named here; **supported** =
a hypothesis with evidence; **unresolved**. Offline checks are not in-game acceptance.

Data: [data/interior-census.json](data/interior-census.json) (every interior cell),
[data/interior-batches.json](data/interior-batches.json) (the plan),
[data/interior-door-rounds.json](data/interior-door-rounds.json) (each batch's door selection).
Tools: `scripts/terrain/interior_census.py`, `interior_batches.py`, `interior_batch.py` (tests:
`tests/test_interior_census.py`); `vmad_patch.py port --keep-markers` (tests: `tests/test_vmad_patch.py`).

## Answer first

- **Fallout4.esm holds 1,194 interior cells; 271 are reached by a load door** (**verified**, census over Fallout4.esm
  330,745,373 B, sha256 ae7be31a..., the same file as interior-backlog.md). 247 are entered from a worldspace, 24 only
  through other interiors. The other 923 have no load door leading in: 354 `COPYnnnn` cells, 231 without an editor
  id, the `zUnused*` cells, `NavMeshGenCell`, `BoSAliasCell` and similar holding or editor cells (22,720 references
  in all). They are left out (listed in the census with `reach` = `no_load_door`; reaching them takes a script move).
- **Of the 271: 16 are in the installed port, 251 are planned, 4 are left out.** The 251 are interior-backlog.md's
  190 Commonwealth cells and its 26 second-hop cells, plus **39 the backlog could not see**: the backlog starts from the
  Commonwealth's doors, and 33 Diamond City interiors and 6 Goodneighbor interiors are entered from those cities'
  own worldspaces. Left out: `CTEST`, `ccTOSFO4001`, `ccTOSFO4002Interior01`, `ccZSEFO4002Interior01` (Creation Club
  hook cells whose door bases have no model in this Fallout4.esm, interior-backlog.md "Odd cells").
- **Plan: 9 batches of 21 to 30 interiors** (about 40,000 to 60,000 references each), one cumulative FO4Port.esm, every
  earlier FormID kept, so each staged batch can replace the installed port without breaking saves or the installed
  core's doors (below).
- **Disk** (**supported**, estimated from the installed port's archives): the final port's archives are about 5.7 GB;
  the peak on D: (one work staging plus the latest batch and one rollback) is about 23 GB at batch 9, leaving about
  44 GB of the 67 GB free measured this morning, so the 40 GB floor holds. Every build re-checks the real free space
  first and refuses below the floor.
- **The long pole is still the door gate.** A new interior's Commonwealth doors work only after a core build whose door
  cluster was made against the new port (`make_cluster.py doors` + `make_core64c.py stage`, docs/terrain/scripted-doors.md).
  The installed core must not change while the v6e test runs, so the batches are staged with the 16 installed doors
  re-applied and the new cells reachable by `coc FO4Port_<Cell>`; each batch's door rounds are planned for the wired
  build (data/interior-door-rounds.json).

## The batches

Order: 0) the cells behind interiors the port already holds (Parsons, Vault 114, Prydwen, Kellogg's memory, Vault
111 before the war); 1) the Commonwealth interiors within 1 km of Red Rocket or Sanctuary, nearest first (Sanctuary's
Jahani basement, the four Concord cells, Gorski cabin, ...: the backlog doc's recommendation, the walkable
Commonwealth grows from Red Rocket); 2) interior-backlog.md's ranking, each second-hop cell right after the last cell
it is reached from; 3) the Diamond City and Goodneighbor interiors (coc only until those worldspaces are built).

| Batch | Cells | Refs | New models (est) | Archives GB (est) | Peak GB (est) | First interiors (all in the JSON) |
|---|---|---|---|---|---|---|
| 1 | 27 | 58,199 | 1,183 | 2.93 | 11.7 | GoodneighborTheMemoryDen, MQ203KelloggsBrain, ParsonsState02, ParsonsState03, PrewarVault111, PrydwenHull03, Vault11402, SanctuaryBasementJahani, ConcordCivicAccess01, ConcordFactory, ConcordSpeakeasy, ConcordMuseum01, ... |
| 2 | 21 | 59,715 | 1,560 | 3.79 | 15.16 | FaneuilHall01, USSConstitution01, TheaterHub360, TheaterMassBayMedicalCenter01, MassFusion01, MassFusion02, ... |
| 3 | 29 | 59,313 | 723 | 4.19 | 16.76 | WestonWaterTreatment01, TrinityChurch01, CambridgeChurchGraveyard01, CambridgeMassChemical01, HestersRobotics01, GNN01, ... |
| 4 | 27 | 57,944 | 929 | 4.7 | 18.81 | IrishPrideShipyard01, TrinityTower01, AtomatoysCorporateHQ01, Financial21, PickmanGallery01, HalluciGen01, ... |
| 5 | 30 | 50,948 | 397 | 4.92 | 19.69 | SuffolkCountyCharterSchool01, Waterfront12, MiltonGeneral01, FederalSurvCenter01, PoseidonEnergy01, ShamrockTaphouse01, ... |
| 6 | 30 | 53,018 | 260 | 5.07 | 20.27 | BADTFL01, CharlestownHouse01, zPOIJoel06, FensKenmoreStation, GreenetechGenetics02, BostonPublicLibrary01, ... |
| 7 | 29 | 57,376 | 524 | 5.36 | 21.43 | GreenetechGenetics01, BunkerHill01, SlocumsJoeHQOffice, RelayTowerInt04, BeaconHillPub, BackBayTallOffice01, ... |
| 8 | 30 | 39,953 | 376 | 5.57 | 22.26 | WestRoxburyStation01, ShawHighSchool01, RelayTowerInt17, PoseidonEnergy02, DanversHideout, GNN02, ... |
| 9 | 28 | 11,529 | 320 | 5.74 | 22.97 | DmndGreenhouse01, DmndJohnsHouse01, DmndMoeCroninsHouse01, DmndOutfieldShengsHouse01, DmndPembrokesHouse01, DmndPlayerHouse01, ... |

New models: the backlog's measured `adds_models` where it has them (all Commonwealth cells), else the cell's distinct
bases times the measured new fraction (the 39 city cells): **supported** estimates; the build's manifest gives the real
count. Archive bytes: the installed port's archives (Textures 2,156,974,881 B and Main 113,096,481 B for about 4,100
models, **verified** sizes on D:, model count **supported** from the manifest size) per model; the loose work staging
taken as twice the archives (a judgment).

## How a batch is built (`interior_batch.py build`)

Batch N = the installed port's 16 cells + every cell of batches 1..N, built into a NEW folder
(`D:\Modding\staging\interiors_bNN`): exports (the 16 base cells' exports copied from the pinned port staging, every
other cell exported with dotnet/Fo4Export into the work staging and kept), one `convert_batch.py --resume` into a
growing work staging (`--starfield-data` for rigged doors and movables, as the integ builds), `port_promote.py`,
PluginSpike seeded with the installed port's `formids.json` and `lighting.json`, then:

- **Doors** (`vmad_patch.py port --keep-markers <installed port>\doors.json`, new): the 16 installed scripted doors are
  re-applied with the **same** interior marker ids (00E175 to 00E183 in integ_v6_specmask_doors_c) that the installed
  core's exterior doors name, which must be free in the grown plugin; the seeded formids.json keeps them reserved.
  Without this, a grown port would shift the markers and the installed exterior doors would land nowhere.
  `vmad_patch.py check` then proves every other record byte-identical to PluginSpike's output.
- **Compare** (`interior_batch.py compare`, the port's compare-ids): every key of the installed port's formids.json
  keeps its FormID, no installed record is removed or changes signature; byte-identical and changed records are
  counted by signature (a changed record of an old cell means the converter or tables changed since the installed
  build: listed, not failed). Any renumbered, missing or removed id fails the batch.
- **Pack**: `FO4Port - Main.ba2` and `FO4Port - Textures.ba2` from the work staging with Starfield's Archive2
  (deploy_starfield.py's packer, no install). An archive of 4,095 MiB (4,293,918,720 bytes) or more fails the batch;
  one over 90% of that is listed under `near_limit`. Every vanilla Starfield archive stays under 4 GiB, and whether the
  engine reads a larger one is unresolved. Measured (verified, D:\Modding\staging\interiors_b04\port): batch 4's
  Textures.ba2 is 3,590,442,691 bytes and Main.ba2 230,547,923, which is 0.81 of the plan's 4.70 GB estimate. At that
  ratio, the textures archive reaches about 90% of the limit at batch 5 or 6 and passes it at batch 7 (supported
  estimate). Before then the textures need a split: a second archive (whose auto-load name is unverified), a small
  companion plugin carrying its own `- Textures.ba2`, or a smaller texture set. That choice is open and goes in
  docs/ai/decisions.md.
- **result.json**: per cell converted / checked / failed with the reason, PluginSpike's placed / lights / skipped, the
  failed models, the pins (commit, sha256 of the plan, the installed port's plugin and map, the new plugin), times,
  sizes and free space. A stage is deleted in two steps.

  First, `release` marks one stage as safe to delete. It refuses:
  - a failed build, which is evidence and is deleted by hand once archived;
  - a stage with no passed `--successor` built from it with `--prev` and a passing compare, which is the proof that its
    ids and records carry forward;
  - a stage whose FO4Port.esm is the one in Starfield's Data folder;
  - a stage named by any text file under the `--check-refs` folders. Pass the queue, recovery-receipt and install-log
    folders there, not the staging root, because later stages name their `--prev`.
  - any check that cannot run, such as a missing folder or an unreadable file.

  It copies every file except the port's FO4Port.esm and its two BA2s to `--archive`/<name>/<generation>/, whatever the size. A generation is named by the tree's digest and never
  overwritten: a changed stage released again gets a new one, and an existing one with other bytes refuses the release (each copy is published exclusively, so a file another
  writer puts there first is kept and verified, never replaced), and
  verifies the copies. Those three are covered by the successor: its own plugin and BA2s must match the sha256s pinned when it
  was built (result.json pins.plugin and steps.pack.sha256), at release and again at prune. A batch built before
  0156f14's successor, with no archive sha256s, cannot stand in. It then writes release.json with the whole tree's sha256s; any file not
  covered by one of the two refuses deletion.

  Second, `prune --keep 2 --delete` repeats every check right before deleting: the same tree (a log added later keeps
  the stage), intact archive copies, the successor and its port still intact, nothing installed or named. It deletes only the
  stages that still pass, and lists the rest with the reason they stay. The build-time `installed: false` in result.json
  is never taken as a release (Codex's reviews on #396).

**Batch 0** builds only the 16 installed cells and compares them with the installed port: it shows whether today's
converter reproduces the installed port before anything grows it. Its change counts are the baseline every later
batch's old-cell counts are read against.

The installed port's flags (**verified**, D:\Modding\scratch\v6\build_v6.ps1 and its log.md, 2026-10-18 14:16Z,
worktree wt_v6): convert_batch `--door-anim-dll C:\Modding\research\sf_animation_io\CALUMI.Animation.dll
--spec-mask-roughness --mass-scale 0.2`; port_promote `--names C:\Modding\scratch\acti-term\fo4_names.json
--furniture D:\Modding\staging\furn\fo4-furniture.json --fo4-data <FO4 Data>` plus the two tables. A batch passes them
with `--convert-arg=...` and `--promote-arg=...` (one token each, `=` form). Batch 0's first run (1e9945b) left them
out and used a fresh work staging, so its compare failed (2,684 base records "removed": 2,662 editor-id case renames,
11 rigged doors written as STAT without the animation dll, 11 chairs without the furniture table); cd78ab1 seeds the
base's editorids.json and the rerun passes the flags.

## Locations

Every converted cell gets a Starfield location (LCTN, the cell's XLCN) in FO4Port.esm, carrying the Fallout 4
encounter zone's level band, so the leveled-actor and cleared-state systems have a place to attach to
(interiors.md C4, C10, D1; the decision is in docs/ai/decisions.md, 2026-10-20). Everything below is **verified** in
unit tests on synthetic records (`dotnet/Fo4Export.Tests`, `dotnet/PluginSpike.Tests`, `tests/test_interior_census.py`)
and **unresolved** in game: no batch with locations has been built or loaded yet.

**Mapping rule: one Starfield LCTN per FO4 LCTN, shared by its cells** (28 FO4 locations own 65 census cells, Vault 81
and Parsons State three cells each). A cell without XLCN (960 of the 1,225 census cells) gets its own.

| FO4 cell | Starfield LCTN | formids.json key | EditorID |
|---|---|---|---|
| has XLCN | one per FO4 LCTN, shared | `LCTN:FO4Port_<FO4 LCTN editor id>` | `FO4Port_<FO4 LCTN editor id>` |
| has XLCN, the FO4 LCTN has no editor id | one per FO4 LCTN | `LCTN:FO4Port_LCTN_<formkey, ':' as '_'>` | the same without `LCTN:` |
| no XLCN (or it does not resolve) | one per cell | `LCTN:FO4Port_<cell editor id>Location` | `FO4Port_<cell editor id>Location` |
| (root, once per plugin) | `FO4Port_InteriorsLocation`, parent `SSol_PMars_Surface` 01B736:Starfield.esm | `LCTN:FO4Port_InteriorsLocation` | `FO4Port_InteriorsLocation` |

Every interior LCTN's parent is the root; FO4's own parent chain (CommonwealthLocation and the like) is exported
(`location.parent_chain`) but not replicated. Name = the FO4 LCTN's FULL, else the cell's. The keys are deterministic
from FO4 data, never ordinal, so the chained formids.json fixes each LCTN's FormID the first time a batch touches it.

**Leveling** (`encounter_zone`, the FO4 cell's XEZN -> ECZN DATA): min and max level and the flags
(NeverResets 1, MatchPcBelowMinimumLevel 2, DisableCombatBoundary 4, Workshop 8, the same four bits in Starfield's
LocationOwnerData) fold into the LCTN's Owner data; levels are clamped to 127 (Starfield's are signed bytes) and the
FO4 owner faction is dropped. A cell with a zone but no LCTN keeps the zone's leveling on its per-cell LCTN (never the
zone's own location, which may be an exterior one); an LCTN without a zone has no leveling; when cells sharing one LCTN
carry different zones, the first cell in PluginSpike's argument order wins (the pinned base cells sorted by editor id,
then the batch's cells in plan order, so a cell moving between the two sets can change the pick) and PluginSpike logs
the other. No keywords are written
(FO4's LocType keywords have no verified Starfield mapping; the export keeps them for a later pass).

**Where the FO4 data comes from.** `Fo4Export export` writes schema 3 (`docs/CELL-EXPORT.md`): `cell_data` (flags,
name), `location`, `encounter_zone`. The 16 base cells' exports are pinned copies that predate schema 3, so
`interior_batch.py build` runs `Fo4Export <plugin> [--master ...] locations plugin\locations.json <cell>...` for them
(one run per source plugin, DLC cells with `--master Fallout4.esm` as `export_cell` does) before PluginSpike, which
reads a cell's keys from its own export first, then from `locations.json`, else writes a per-cell LCTN with no
leveling. A failed locations run fails the batch (`locations failed`); result.json records
`steps.locations = {exit, seconds, cells}`. The census (`interior_census.py`) shows the same data per cell:
`location` (the FO4 LCTN editor id) and `encounter_zone` (`min_level`, `max_level`, `flags`, `rank`, the zone's location).

**`LOCATION_AS_NAME`**: the CELL flag bit 0x10000 ("Use Location as Name", which Mutagen alpha.67 has no member for)
is off by default, because which source the "Enter X" prompt reads is unresolved (interiors.md D2). The per-cell
lighting.json-style setting `LOCATION_AS_NAME` = `"1"` sets it on one cell for the test (the cell's entry or `"*"` in
`plugin\lighting.json`; unlike the lighting keys it is never read from the environment, so a stray variable cannot flip
every cell of a batch).

**Compare.** A batch built after this change shows every base CELL under `records.changed` (it gained its XLCN; the
record is otherwise the same) and the LCTNs under `records.added`; `cells_added` scans `CELL:` keys only. Neither is
a problem: the compare fails only on a missing, renumbered or removed base id or a changed signature, and
`tests/test_interior_census.py` pins that a base cell gaining XLCN plus added LCTNs passes, that an LCTN key renumbered
by the next batch fails, and that the `LCTN:` keys ride the `--prev` chain. Expect the next batch's compare against the
installed port to list the 16 base CELLs as changed and, added, the root plus one LCTN per FO4 location (or per
cell without one) of every cell in the build. Open (**unresolved**, PC tests in interiors.md):
whether a save made on batch 4 carries to a batch whose base cells gained a location, and whether a location chain
that bypasses the overlay location satisfies the cleared-state system (C10).

## Door rounds per batch

`interior_batch.py doors` lists, per batch, the cells with Commonwealth doors (`door_rounds.py stage --only`
`FO4Port_<Cell>,...`), the doors, the cells only coc reaches (city interiors, cells behind interiors). They run only on
a wired set: this batch's port installed with a core build whose door cluster was made against it. In the installed
core v6c/v6e only the 16 base cells' doors are wired. Batch 1: 47 Commonwealth doors into 20 cells, 7 cells coc only.

## DLC

The PC has two DLC plugins (Automatron = DLCRobot.esm, 8,012,051 B, sha256 e71e04ac...; Wasteland Workshop =
DLCworkshop01.esm, 633,592 B, sha256 82914c20...; copied read-only to D:\Modding\research\dlc on 2026-10-19).
Census over Fallout4.esm + both (**verified**, interior_census.py, the data files above now hold it):

- **2 new interiors, both Automatron's, both entered from the Commonwealth:** `DLC01Lair01` (the Mechanist's Lair,
  28,395 references, 3 Commonwealth doors) and `DLC01FortHagenSatelliteArray01` (7,797 references, 1 door). They are
  **batch 10** (36,291 references); batches 1 to 9 are unchanged byte for byte (`interior_batches.py --after`).
- Wasteland Workshop adds no reachable interior (only test and holding cells). The other 29 DLC cells have no load
  door in (holding, test, door-storage cells).
- Automatron also adds 44 references to `GeneralAtomicsFactory01` (batch 8: 6,150 in Fallout4.esm, 6,194 with
  the DLC). The batches export that cell from Fallout4.esm only, so those 44 are not in the port yet
  (**unresolved**: an override-cell merge in the exporter; small).

What a DLC cell needs, and what is done:
- **Export:** `Fo4Export <DLCRobot.esm> --master <Fallout4.esm> export <cell>` (new `--master`, repeatable): the DLC
  cell's bases and its door targets resolve through Fallout4.esm. **Verified** on both cells in the cloud: without
  the master 7,615 and 26,333 references have no base; with it every base resolves and every door names the
  Commonwealth's persistent cell 018AA2.
- **Models:** `convert_batch.py --extra-data <DLC Data folder>` reads its `DLC*.ba2` (Main and Textures) after the base
  game's archives, so base-game models convert exactly as before (unit tested; not yet run on the real archives).
- **Batch:** `interior_batch.py build --dlc-data <depot_435871\Data> --dlc-data <depot_435880\Data>` exports a
  DLC cell from its own plugin (the plan's formkey says which) and passes the folders to the converter.
- **Not done:** the Commonwealth side. Automatron's exterior doors (and the satellite array's outside structure) are
  DLCRobot.esm references in the Commonwealth, which the core does not convert; wiring batch 10's doors needs a
  core built with the DLC's Commonwealth references. The DLC chairs are not in the furniture table either
  (Fo4Land's export reads Fallout4.esm), so they stay static.

## Reproduce

```
python scripts/terrain/interior_census.py --out <census.json> --backlog docs/terrain/data/interior-backlog.json --port-cells <installed port staging> <Fallout4.esm>
python scripts/terrain/interior_batches.py --census <census.json> --backlog docs/terrain/data/interior-backlog.json --out <batches.json> --md <batches.md> --free-gb <D: free>
python scripts/terrain/interior_batch.py doors --plan <batches.json> --census <census.json> --batch N --out <door_rounds.json>
python scripts/terrain/interior_batch.py build --plan docs/terrain/data/interior-batches.json --batch N ^
  --base D:\Modding\staging\integ_v6_specmask_doors_c --base-exports D:\Modding\staging\integ_v6_specmask ^
  --core D:\Modding\staging\terrain_core64v6c_l125 --work D:\Modding\interiors_work --out D:\Modding\staging\interiors_bNN ^
  --fo4-data <FO4 Data> --starfield D:\SteamLibrary\steamapps\common\Starfield ^
  --content-resources <Starfield>\Tools\ContentResources.zip --texconv <Texconvx64.exe> --collision-template <template.nif> ^
  --fo4export <Fo4Export.dll> --pluginspike <PluginSpike.dll> --spec-mask-roughness ^
  --convert-arg=--door-anim-dll --convert-arg=<CALUMI.Animation.dll> --convert-arg=--mass-scale --convert-arg=0.2 ^
  --promote-arg=--names --promote-arg=<fo4_names.json> --promote-arg=--furniture --promote-arg=<fo4-furniture.json> ^
  --promote-arg=--fo4-data --promote-arg=<FO4 Data>
python scripts/terrain/interior_batch.py release --dir D:\Modding\staging\interiors_b03 --reason "superseded by b05" ^
  --successor D:\Modding\staging\interiors_b04 --archive <evidence archive folder> --check-refs <queue folder> --check-refs <recovery receipts folder> --starfield <Starfield>
python scripts/terrain/interior_batch.py prune --staging-root D:\Modding\staging --keep 2 --delete
```

## Results

| Batch | Built | Converted | Checked | Failed (reason) | Compare | Archives | Notes |
|---|---|---|---|---|---|---|---|
| 0 | run 1 failed (1e9945b) | 16 | | | removed 2,684 (names, flags) | | fresh work staging, flags missing |
| 0 | 2026-10-19 PASS (5ecb8a7) | 16 | 16 | 0 | pass: 55,049 records, all identical, none changed/added/removed | not packed | convert 807 s, total 825 s; D: 61.5 to 57.8 GB free; teleports Linked 2, DestinationNotInBuild 28 |
| 1 | 2026-10-19 PASS (5ecb8a7) | 27 | 27 | 0 cells; 15 models in 8 cells (below) | pass: 55,044 base records identical, 5 changed, 51,437 added | Main 152,387,704 B, Textures 2,708,113,806 B | plugin 297b0f33 (7,899,352 B); convert 704 s, total 815 s; D: 57.8 to 54.1 GB free; teleports Linked 22, Pairs 11 |
| 2 | 2026-10-19 PASS (5ecb8a7) | 48 (27 + 21) | 48 | 0 cells; 7 models in 4 new cells | pass: same 5 base doors changed, 103,899 added | Main 177,735,013 B, Textures 3,104,207,280 B | plugin 23edf959 (11,520,178 B); convert 618 s, total 726 s; D: 54.0 to 50.1 GB free; teleports Linked 24 |
| 3 | 2026-10-19 PASS (7fc0caa, --prev b02) | 77 | 77 | 0 cells; 6 cells with trap/glass models | pass; vs b02 pass (no b02 record changed) | Main 191,448,321 B, Textures 3,282,063,253 B | plugin 1db0e61e (15,074,712 B); convert 663 s, total 792 s; D: 53.8 to 49.8 GB free |
| 4 | 2026-10-19 PASS (7fc0caa, --prev b03) | 104 | 104 | 0 cells; 7 cells with trap/gnat/water models | pass, 6 base doors changed; vs b03 pass, 1 changed (010045AA) | Main 230,547,923 B, Textures 3,590,442,691 B | plugin 1b94d270 (18,444,707 B); total 815 s; D: 49.8 to 45.1 GB free; teleports Linked 48 |
| 5 to 9 | held | | | | | | D: near the 40 GB floor until the owner deletes superseded folders |
| 10 (DLC) | not yet | | | | | | Automatron's 2 interiors; needs the DLC Data folders readable by the build |

Batch 1 notes (**verified** from interiors_b01's result.json, port\compare.json and both plugins):
- The 5 changed base records are load doors of installed cells (REFR 010062BB, 010062BE, 010045AE, 0100383E,
  01003840) that gain an XTEL now that the interior behind them is in the build (Parsons, Vault 114, Prydwen and
  the like); nothing else in them changed. This is the expected change, and it is why teleports went from 2 to 22 linked.
- Models that did not convert (the refs are left out, the cells work): `traps\oiltrappuddle01.nif` (5 cells),
  `traps\gastrap01.nif` (2), `setdressing\dc_graffiti\dc_graffiti_welcome01.nif`, `dc_graffiti_arrow01.nif`,
  `interiors\brain\deadneuron01.nif`, `deadneuron02.nif`, `setdressing\signage\signgeneralopen.nif`,
  `furniture\invisible\deskterminalfurniture01.nif`, `setdressing\quest\bs101\dn017_hallwaysmoke.nif`.
  Traps, decals, smoke and an invisible marker: none is a wall or floor (**supported**, from the paths; the
  convert log has each reason).

Batch 2 failed models (new cells): `traps\gastrap01.nif`, `traps\oiltrappuddle01.nif`,
`setdressing\kitchen\beerglassgwinnett01.nif`, `architecture\diamondcity\dext\tempdiamondcityspeaker01.nif`,
`interiors\steamt\temp\tempinsanebricks.nif` (the last two are Bethesda "temp" models).

Batch 1 against batch 2 (**verified**, `interior_batch.py compare --old interiors_b01\port --new interiors_b02\port`,
2026-10-19): FAIL, 51,435 of batch 1's new ids renumbered (the installed port's ids were all kept). Batches 1 and 2
were each seeded with the installed port's formids.json only, so PluginSpike numbered each batch's new cells afresh.
Harmless while nothing past the installed port is installed, but a save made on one staged batch would not carry
to the next. Fixed: `build --prev <previous batch>` seeds PluginSpike with the previous batch's port\formids.json and
also compares against it (port\compare_prev.json; it must pass). The chain starts at batch 2: batch 3 is built with
`--prev interiors_b02`. Batch 1 is superseded.

Disk check: batch 3 was refused by the first preflight (free 53.8 GB minus the plan's 16.76 GB peak), though batches
1 and 2 each took about 4 GB. The plan's peak counts the work staging and two batches from nothing; the preflight now
counts what the batch adds (`disk_need`: its packed folder plus the work staging's growth, about 5 GB for batch 3).

Batch 4: base door REFR 010045AA gained an XTEL to REFR 0104044C, a door in one of batch 4's new cells (**verified**,
b03 and b04 plugins diffed); nothing else in it changed. Batch 4 failed models also include the Institute's water
planes (`interiors\institute\main\insmainbasefloorwater01.nif`, `insterracewater01.nif`) and `critters\gnat\gnatswarm01.nif`.
