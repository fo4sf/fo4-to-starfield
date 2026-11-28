# WS0a Design Architecture: Categories, Store, Layering, Bench Identity & WS1 Retirement

- **Status:** **Design only (Rule 12).** Labelled defaults reflect the agreed plan baseline and owner answers; no unapproved FO4 runtime settlement simulation code ships in WS0a (`Task 6 c` stands).
- **Labels:** `VERIFIED` = directly verified in `Starfield.esm`, `Fallout4.esm`, or this repository; `UNVERIFIED` = awaits in-game probe verification (`WS0a` Tier 1–3 probes).

---

## 1. FO4 Menu -> Starfield Category Map (**Recommended Default**)

With `Route C` (`docs/workshop/ws0a-tab-and-bench-decision.md`, pending `P18`), FO4 top-level `WorkshopMenuMain` (`FLST 0x00106DA2`, `VERIFIED`) branches map onto existing Starfield `FLST 0x058606` (`OutpostRecipeCategories`, `VERIFIED` 15 keywords) using prefixed sort orders (`MenuSortOrder`) and clean display prefixes (`FO4 ...` or category prefixes) so FO4 items group predictably without overriding `0x058606`:

| FO4 Top Category (`00106DA2`) | Starfield Target Filter (`058606`) | Sort Order Band | Name Prefix |
|---|---|---|---|
| `WorkshopMenu01Build` (`00106DA3`: Wood/Metal/Concrete/Barn/Warehouse) | `OutpostCategoryStructures` (`002A7578`) | `100.0–199.0` | `Structure - ` (none if sub-prefixed in WS1+) |
| `WorkshopMenu01Furniture` (`001B4AAE`: Beds, Chairs, Tables, Shelves, Misc) | `OutpostCategoryFurniture` (`002BE3B5`) | `200.0–299.0` | `Furniture - ` |
| `WorkshopMenu01Decor` (`00106DA4`: Wall/Floor/Misc/Signs/Paintings/Lights) | `OutpostCategoryDecorations` (`00293ADF`) | `300.0–399.0` | `Decor - ` |
| `WorkshopMenu01Power` (`00118F60`: Generators, Connectors, Lights, Traps) | `OutpostCategoryPower` (`0005A6DE`) | `400.0–499.0` | `Power - ` |
| `WorkshopMenu01Resource` (`00106DA7`: Water/Food) | `OutpostCategoryBuilders` (`002731A0`) / `Miscellaneous` (`0006D72D`) | `500.0–549.0` | `Resource - ` |
| `WorkshopMenu01Resource02Defense` (`001DE913`) | `OutpostCategoryDefenses` (`001E6641`) | `550.0–599.0` | `Defense - ` |
| `WorkshopMenu01Vendors` (`00118F65`) + Special (`0012E2C7`) | `OutpostCategoryCrafting` (`002CFDE6`) / `Storage` (`0027319A`) | `600.0–699.0` | `Station - ` / `Store - ` |
| `WorkshopMenu01Cages` / `Raider` (`DLC`/optional) | `OutpostCategoryMiscellaneous` (`0006D72D`) | `700.0–799.0` | `Misc - ` |
| `WorkshopMenu01CreationClub` (`0024A0DC`) | **Excluded** (not mapped) | — | — |

---

## 2. One Settlement Store (**Recommended Default Architecture**)

- **Single authoritative store:** One global workshop state coordinator (`FO4SF_WorkshopParent`, replacing ad-hoc globals) owns per-settlement state indexed by `SettlementId` (`0..N`):
  - **Fields per settlement:** `WorkshopRef` (stable core/title bench reference), `LocationId`, `OwnedByPlayer`, `IsPortableCamp`, `Population`, `Happiness`, `Beds`, `Water`, `Food`, `Power`, `Safety`, `AttackDaysSince`, `AllowAttacks`, `SupplyLinkTargets[]`, `StorageRef`, `BuiltBedRefs[]`, `LastUpdatedRealTime`.
  - **Single writer:** Only `FO4SF_WorkshopParent` mutates settlement rating fields and persists across save/load (Papyrus quest arrays/structs paired with serialized SFSE cosave backup if needed past 128 array cap).
  - **Readers:** `FO4SF_Sanctuary01Quest` (`Min01` beds/water/food/defense progress), Pip-Boy `DATA > WORKSHOPS` page, Warfare settlement management screen (`#32` `7155932648`), and radiator/attack schedulers are **read-only consumers** of the store.
- **Labelled Cross-Mode & Progression Defaults (`Rule 12`):**
  1. **FULL-route persistence:** Built FULL-route settlements stay in the shared world across story chapters so subsequent characters encounter prior builds.
  2. **No Atomic Shop items:** Strictly base FO4 + approved story-order DLC buildables (`0024A0DC` Creation Club excluded by default).
  3. **Story-order DLC sets:** DLC workshop packs (Automatron, Wasteland Workshop, Contraptions, Vault-Tec, Far Harbor, Nuka-World) unlock/appear in story order after the base FO4 set.
  4. **Per-game story flags:** Settlement gating, quest prerequisites, and C.A.M.P./settlement availability key on per-game story flags (`FO4SF_StoryFlags_*`), **not** a coarse global `FO4SF_GameMode` switch alone.

---

## 3. Bench Identity in the Workshop Core & `Min01` Beds Counting Design

- **Core bench identity (`VERIFIED`):** All `29` pre-placed Commonwealth core workshop references (`REFR`, incl. Sanctuary `0x005C50`) use one of the two converted core bench `ACTI` bases (`0x0A2ECD` `FO4Core_wkshp_0c1aeb_fallout4` or the base built from FO4 `00246F86`), with `0` `LCTN`, `STDT`, or `PNDT` overrides in `FO4SFWorkshop.esm`.
- **`Min01` Beds-from-World Design (Zero Runtime Code in WS0a, Pending Task 6 b2 Probe):**
  - **If `OnWorkshopObjectPlaced` / `OnWorkshopObjectRemoved` fires on pre-placed core bench `04005C50`:**
    1. `FO4SF_WorkshopParent` registers for `OnWorkshopObjectPlaced` / `OnWorkshopObjectRemoved` on Sanctuary `04005C50`.
    2. Whenever a bed base carrying our Bed actor value (`PRPS`) is placed/removed inside Sanctuary's radius, `FO4SF_WorkshopParent` updates `BuiltBedRefs` and writes `Min01BedCount` -> `Min01BedPercent`.
    3. `FO4SF_Sanctuary01Quest` reads the count from the settlement store, while retaining the legacy `+1` message-box menu (`RunWorkbenchBuildMenu`, `FO4SF_Sanctuary01Quest.psc:1099-1163`) strictly behind an explicit TestMode / fallback switch (`FO4SF_Min01BoxFallback = 0.0` default off in production).

---

## 4. Plugin Layering for FO4 Buildables & `SFBGS00D.esm`

1. **Terrain Core Layer (`FO4TerrainCore*.esm` / `#858`):** Masters `["Starfield.esm"]` only (`make_core64c.py:3302`). Holds static architecture/world refs and the `29` core bench refs on their two clean bases.
2. **Core Values & Workshop Rules (`FO4SFCoreValues.esm`, `FO4SFWorkshop.esm`):** Masters `["Starfield.esm", "FO4SFCoreValues.esm"]`. Zero terrain-core master, zero `LCTN`/`STDT`/`PNDT` overrides, zero probe records.
3. **Buildables Pack (`FO4SFBuildPieces` / `FO4SFWorkshopBuildables.esm`):** Holds converted FO4 settlement `STAT`/`FURN`/`CONT`/`ACTI`/`LIGH` shells, `COBJ` recipes, and our `KYWD`/`AVIF` rating forms; masters `Starfield.esm` + `FO4SFCoreValues.esm` + `FO4SFWorkshop.esm` (reads models/paths cleanly without touching core terrain cells).
4. **Optional `SFBGS00D.esm` Linked Storage Extension (`FO4SFWorkshop_SharedStorage.esm`, Recommended Default: isolated optional addon):** Because `SFBGS00D.esm` (`CONT 0x0102AF77` Shared Outpost Container / `COBJ 0x0102AF79`) is a Starfield Creation/update ESM rather than base `Starfield.esm`, keep any direct `SFBGS00D.esm` Master reference out of `FO4SFWorkshop.esm` core plugins so base installs never break if `SFBGS00D.esm` is absent; test its sharing behavior offline first in `P6` (`FO4SFWorkshopProbe.esm`).

---

## 5. Retiring Clean-Bench Stand-Ins `0x84B–0x84D` in WS1

- **Current WS0a state (`#852` parity):** `0x00084B` (`FO4SF_Sanctuary_WoodChair`), `0x00084C` (`FO4SF_Sanctuary_SleepingCot`), and `0x00084D` (`FO4SF_Sanctuary_StorageCrate`) plus their `COBJ`s (`0x84E–0x850`, gated on `0x84A == 1.0`) stay intact in WS0a because they reuse Starfield models (`AK_Chair_Wood_01.nif`, `FoundScrapCot01.nif`, `ToolBox_SetA_03.nif`).
- **WS1 retirement plan:** Once real converted FO4 furniture/container meshes ship under `FO4SFWorkshopBuildables.esm` (`WS1`), supersede `0x84B–0x84D` by either (a) swapping their `MODL` + FormList category onto the FO4 buildables `Route C` workbench filter and retiring `0x84E–0x850`, or (b) marking `0x84E–0x850` uncraftable (`Conditions = impossible` for save compatibility) rather than deleting their FormIDs so existing saves keep placed refs cleanly.
