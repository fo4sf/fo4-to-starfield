# Stations: FO4 settlement workshops -> Starfield build stations, FO4 crafting benches -> vanilla Starfield benches

Author: Claude, 2026-10-16. Status: **offline only**. Nothing deployed, nothing run in game; the queue below is
planned, not run. Labels as in the other terrain docs: **verified** = read from files, **supported** = hypothesis with
evidence, **unresolved** = open. The record facts come from a raw walk of `Starfield.esm` (1.16.244) and
`Fallout4.esm` (1.10.163) with `src/fo4sf/fo4station.py` over `fo4land`; the localized names from
`Starfield - Localization.ba2`.

## Path

```
python scripts/terrain/make_cluster.py workshops --work <core64c work> --build <core64h> --fo4 <Fallout4.esm> --out workshops.json
python scripts/terrain/make_cluster.py benches   --work <core64c work> --build <core64h> --fo4 <Fallout4.esm> --table scripts/terrain/clusters/bench_table.json --out benches.json
python scripts/terrain/make_cluster.py merge --out cluster.json containers.json items.json activators.json terminals.json lights.json workshops.json benches.json
python scripts/terrain/make_core64c.py stage ... --cluster cluster.json --navmesh <navmesh.json> --sf-esm <Starfield.esm>
python scripts/terrain/make_core64c.py check ... --sf-data <Starfield Data>        # the station records need Starfield.esm
python scripts/terrain/make_core64c.py compare-ids --out <new build> --against <input build>
```

1. **`make_cluster.py workshops`** lists every placed FO4 Container reference whose base carries the `workshopscript`
   VMAD script in `Fallout4.esm` (`fo4station.vmad_scripts` parses the script names; the band exports carry no
   script). In the core that is CONT `0C1AEB` WorkshopWorkbench (28 references) and `246F86`
   WorkshopWorkbenchNonSettlement (1): both carry `WorkshopKeyword 054BA7` first in their KWDA (**verified**); the
   22 other `Workshop*` container bases (resource containers, office desk, metal box) carry no script and stay
   containers. Each entry: `src`, `name` "Workshop", `radius` 250 (metres), the FO4 base and editor id, `slot`.
   **The container table drops these two bases** (`container_table.json` `{"skip": ...}` entries): a source in two
   classes is refused by `cluster_promote`.
2. **`make_cluster.py benches`** lists every placed FO4 Furniture reference whose base has a `WBDT` bench type
   (`Fallout4.esm`, raw) and a kind from `bench_table.json` (editor id, exact or `prefix*` -> `weapon` / `armor` /
   `chem` / `cooking`). The table's kind must agree with the base's bench type (`bench_reason`), else the station is
   listed under `bench_skipped` with the reason; so are power armor stations (`kind: null` with the table's reason)
   and bench types without a table entry ("unknown kind", never guessed). Furniture without a bench type (6,392
   references: beds, seats, markers, the supermutant cauldron) is counted, not listed.
3. **`make_core64c.py stage --cluster`** (`cluster_workshops`, `cluster_benches`, `cluster_promote` over all six
   classes on one unpromoted list): a workshop entry gets edid `FO4Core_wkshp_<6 hex>_<plugin>`, the converted
   workbench model, its name and radius (entries of one edid must agree); a bench entry gets its kind's vanilla base
   (`BENCH_VANILLA`) and keeps `fo4_model` for the record. Both keep the reference's cell / position / rotation /
   scale and original `reference_index`.
4. **`TerrainOverlays`** writes, after the TERM + TMLM block, one ACTI per workshop edid: `FULL` the name, `MODL`
   the converted model, `KWDA` = `WorkshopKeyword` (00054BA7) followed by the `OutpostCategory*` keywords the vanilla
   `OutpostPlayerHouseActivator` (00024DC7) carries, in its order, **read from the master at write time** (never
   typed): Crafting, Furniture, Decorations, TestAssets, Displays, Power_InteriorLights, MiscInterior; `PRPS` one
   object property `OutpostBuildAreaRadius` (AVIF 00063FC5) = the radius; no VMAD; PNAM / FNAM / JNAM as every ACTI
   of the build. The REFR is temporary in its exterior cell, in its reserved slot. A bench writes **no record**: its
   REFR names the vanilla FURN of its kind, checked on the master (a FURN with a bench type). `formids.json` gets
   `"workshops": {src: {"base", "ref"}}` and `"benches": {src: {"base": "<6 hex>:Starfield.esm", "ref", "kind"}}`.
5. **`check`** adds: slots retained for both classes (`check_reference_slots`: a bench declares its kind's vanilla
   base, a workshop base follows every reserved slot and is no other class's); `ACTI` count = distinct activator +
   workshop edids; `0 FURN of our own`; every workshop REFR's base carries `WorkshopKeyword`, the radius property and
   no VMAD (`workshop_problems`, raw); every bench REFR names its vanilla FURN (file-local, master 0); and against
   `Starfield.esm` itself (`station_master_check`, needs `--sf-data`): the workshop KWDA equals WorkshopKeyword +
   00024DC7's OutpostCategory set in order, the PRPS names OutpostBuildAreaRadius, each bench kind's vanilla FURN has
   the kind's bench type and recipe keyword. `compare-ids` reports every `formids.json` section against the input
   build (identical / changed with counts / shifted by a constant).

## Why these records (evidence)

**The workshop.** Starfield has no container workshop. Build mode opens on activating a reference whose base carries
`WorkshopKeyword` (no script does it: the beacon's `OutpostBeaconScript` has no OnActivate, the player-house activator
has no script at all). The vanilla pre-placed pattern is ACTI 00024DC7 `OutpostPlayerHouseActivator` ("Decorate",
model `SetDressing\GenericLever01\GenericLever01.nif`, no VMAD): KWDA MustPersist, WorkshopKeyword,
OutpostCategoryCrafting, OutpostCategoryFurniture, OutpostCategoryDecorations, OutpostCategoryTestAssets,
WorkshopUseDecorateTextKeyword, OutpostBlockFlycam, OutpostCategoryDisplays, OutpostCategoryPower_InteriorLights,
OutpostCategoryMiscInterior; PRPS `c5 3f 06 00 | 00 00 7a 43 | 00 00 00 00` = (OutpostBuildAreaRadius, 250.0, no
curve); placed three times, once in an exterior worldspace (REFR 0037099A Neon_PlayerCrateWorkshopRef) (**verified**).
Our ACTI takes WorkshopKeyword and that activator's OutpostCategory* set and radius, not its MustPersist /
DecorateText / BlockFlycam keywords and not the beacon's script (the beacon's mandatory quest properties are a later
step). Starfield kept Fallout 4's workshop keyword ids: `WorkshopKeyword 054BA7` is the same record in both games
(**verified**: FO4 CONT 0C1AEB KWDA starts with `a7 4b 05 00`). The OutpostCategory keywords' localized names
(`FULL` through `starfield_en.strings`, **verified**): Crafting, Furniture, Decorations, Test Assets, Displays,
Power, Quest (the MiscInterior one).

**The benches.** Starfield's crafting menu needs no script: a FURN with a `WBDT` bench type whose `KWDA` holds the
keyword its recipes (COBJ) name. The four vanilla stations and FO4's benches share bench types and, for three kinds,
the recipe keyword id itself (**verified**, raw):

| kind | FO4 bases (WBDT, keyword) | Starfield base (WBDT, keyword) | Starfield name |
|---|---|---|---|
| weapon | workbenchWeaponsA 17B3A4, workbenchWeaponsB 17E787 (02; AnimFurnWorkbenchWeapons 17B3A2) | 2B6A63 WorkbenchWeapon (02; WorkbenchWeaponKeyword 2CE1C0, Starfield-only) | Weapon Workbench |
| armor | WorkbenchArmorA 12EA9B (07; 0657FF) | 2B6A62 WorkbenchArmor (07; WorkbenchArmorKeyword 0657FF) | Spacesuit Workbench |
| chem | WorkbenchChemistryA 12F2F5, WorkbenchChemistryB 1487C1 (05; 102158) | 2B6A61 WorkbenchChem (05; WorkbenchChemlabRecipeKeyword 102158) | Pharmaceutical Lab |
| cooking | WorkbenchCookingFire 10C3B6, CookingFireWorkshop 2476B7, CookingGroundPot 0C79B4, CookingSpit 14FBCD, CookingStove 1865B9 (05; 102152) | 2B6A65 WorkbenchFood (05; WorkbenchCookingKeyword 102152) | Cooking Station |
| power armor | WorkbenchPowerArmor 157FEB, WorkbenchPowerArmorSmall 13BD08 and the power armor frames (08) | none: Starfield has no bench type 8 (2B6A64 WorkbenchRobotStation is DONOTUSE) | stays a static |

First pass = option (a) of the research: the vanilla record, model, animation, collision and menu at the FO4 slot
(vanilla benches sit as plain temporary REFRs in POI overlay worldspaces, e.g. OESF008World); zero new records, so no
FormID moves for the benches. The orientation hypothesis (both games' benches extend to +Y with the actor on the -Y
side; FO4 rotation kept as is) is **supported** by the OBND / marker offsets and settles with the first screenshot.
Option (b), our own FURN with the converted FO4 mesh and the vanilla furniture block, is the second step.

## Reference identities

- Every promoted source keeps its REFR slot (`ReferenceIdentityPlan.Order` over the six classes; the synthetic writer
  test compares the REFRs byte for byte but for `NAME`).
- The workshops' ACTI bases are allocated after the TERM + TMLM block, so the records after them (the NAVMs, the
  light block) move up by the number of workshop bases (2 in the core), as any added base does
  (docs/terrain/exterior-lights.md, the known limit until a persistent allocator, #227).
- Taking the 29 workshop sources out of the container class removes their two CONT bases: every CONT allocated after
  `FO4Core_cont_0c1aeb_fallout4` moves down by one (two after `..._246f86_...`), and the MISC / ACTI / TERM bases
  with them. The REFR ids of all 5,156 remaining containers are unchanged. `compare-ids` states this per section.
- A bench adds no record: its REFR's `NAME` is the master's id (`00 2B6A63`), as the COC marker's and the anchor's.

## Acceptance (planned, not run)

Queue `core64i_stations_1016` (`testqueue.py plan-terrain --staging integ_1016 --exp-dir core64i_stations
--bridge bridge_t0 --fresh`), two terrain tests at the Red Rocket arrival with the existing activate step (`prid <ref>`,
`GetIsID <base>` must reply 1, `activate player`, `activate.png` OCR'd, held Tab to leave): the workshop REFR
(`0200D272`, base the workshop ACTI at load index 02) with the expectation words of the build HUD = the category names
the ACTI carries (Crafting, Furniture, Decorations, Displays), and the garage's weapon bench (`0206AC07` on
`002B6A63`) with "Weapon Workbench". The judge shows which words the OCR read; it never judges on them (the terrain
verdict stays). The owner's E at the workbench and at the bench is the interaction acceptance.

## Not done / open

- Nothing in game: whether build mode opens from a station ref in our overlay (the persistent-ref coordinate question
  of docs/terrain/overlay-records.md), whether built objects survive save / load, and whether `activate player` from
  the console enters a FURN are all **unresolved**.
- The build radius (250 m, the player house's) is a circle; FO4's settlement border polygon is not carried.
- No FO4 link targets (centre / sandbox / spawn markers), no XOWN, no VMAD: crew, attacks and the LocTypeOutpost
  keyword are a later step.
- Interiors (FO4Port.esm, dotnet/PluginSpike) are another writer: the 20 interior benches are not covered.
