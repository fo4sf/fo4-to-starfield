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
  (deploy_starfield.py's packer, no install).
- **result.json**: per cell converted / checked / failed with the reason, PluginSpike's placed / lights / skipped, the
  failed models, the pins (commit, sha256 of the plan, the installed port's plugin and map, the new plugin), times,
  sizes and free space. `prune --keep 2 --delete` removes older `interiors_bNN` folders this tool made (result.json
  with `installed: false`), never anything else.

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

## Door rounds per batch

`interior_batch.py doors` lists, per batch, the cells with Commonwealth doors (`door_rounds.py stage --only`
`FO4Port_<Cell>,...`), the doors, the cells only coc reaches (city interiors, cells behind interiors). They run only on
a wired set: this batch's port installed with a core build whose door cluster was made against it. In the installed
core v6c/v6e only the 16 base cells' doors are wired. Batch 1: 47 Commonwealth doors into 20 cells, 7 cells coc only.

## DLC

The PC has DLCRobot and DLCworkshop01 only. Their interiors need (**unresolved**, not built here): the census run with
both plugins after Fallout4.esm (the tool takes them; the DLC depots are outside the folders read today),
dotnet/Fo4Export loading a DLC plugin with Fallout4.esm as master, and convert_batch.py reading the DLC's own
archives. They become a batch after batch 9.

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
python scripts/terrain/interior_batch.py prune --staging-root D:\Modding\staging --keep 2 --delete
```

## Results

| Batch | Built | Converted | Checked | Failed (reason) | Compare | Archives | Notes |
|---|---|---|---|---|---|---|---|
| 0 | run 1 failed (1e9945b) | 16 | | | removed 2,684 (names, flags) | | fresh work staging, flags missing |
| 0 | 2026-10-19 PASS (5ecb8a7) | 16 | 16 | 0 | pass: 55,049 records, all identical, none changed/added/removed | not packed | convert 807 s, total 825 s; D: 61.5 to 57.8 GB free; teleports Linked 2, DestinationNotInBuild 28 |
| 1 | 2026-10-19 PASS (5ecb8a7) | 27 | 27 | 0 cells; 15 models in 8 cells (below) | pass: 55,044 base records identical, 5 changed, 51,437 added | Main 152,387,704 B, Textures 2,708,113,806 B | plugin 297b0f33 (7,899,352 B); convert 704 s, total 815 s; D: 57.8 to 54.1 GB free; teleports Linked 22, Pairs 11 |
| 2 | 2026-10-19 PASS (5ecb8a7) | 48 (27 + 21) | 48 | 0 cells; 7 models in 4 new cells | pass: same 5 base doors changed, 103,899 added | Main 177,735,013 B, Textures 3,104,207,280 B | plugin 23edf959 (11,520,178 B); convert 618 s, total 726 s; D: 54.0 to 50.1 GB free; teleports Linked 24 |
| 3 to 9 | not yet | | | | | | |

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
