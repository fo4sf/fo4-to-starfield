# Core Settlements, Junk Scrapping (`CMPO -> IRES`), Bench Recipes, and Portable C.A.M.P.s (`CF-9`)

`FO4SFWorkshop.esm` promotes the proven `WorkshopProbe` findings (`PlaceAtMe` + `MoveTo` `2.5 m` ahead activating both the terrain core's settlement workbench `0x0A2ECD` and vanilla `OutpostBeaconActivator` `0x002C60E9`) into an installable core plugin with save-reload persistence, deterministic `CMPO -> IRES -> MISC` junk scrapping, clean-room FO4 `COBJ` + FNV `RCPE` bench recipes, and portable C.A.M.P. deployment/relocation.

## 1. Deliverables & Layout

| Component | Path | Purpose |
|---|---|---|
| Plugin generator & checker | `dotnet/WorkshopCore/Program.cs` | `build`, `check`, `fixture` (`full`/`minimal`), `selftest` (17 tamper negative controls) |
| Quest & persistence controller | `scripts/workshop/FO4SF_WorkshopCoreQuest.psc` | Save-reload tracking, `CMPO -> IRES` scrapping, recipe audit, portable C.A.M.P. deploy/exclusion/pack-up |
| Stager, folder, verifier & log CLI | `scripts/workshop/make_workshop_core.py` | `precheck`, `stage`, `fold` (`--hardlink`), `verify`, `log`, `console` |
| Ride-along installer | `scripts/workshop/workshop_core_install.py` | Reversible install/uninstall via `Data/FO4SFWorkshop.install.json` |
| Log parser & reference math | `src/fo4sf/workshop/core_log.py` | `FO4SFWSCORE` parser, rotated `.1.log` + `.0.log` reload stitching, `PASS`/`FAIL` report |
| Unit & contract tests | `tests/test_workshop_core.py` | FormID sync, `CMPO` math, binary header/record checks, `selftest`, `stage`/`fold`/`verify`, redaction |

### Master & Override Discipline
- `FO4SFWorkshop.esm` is flagged `Master`, lists **`[Starfield.esm, FO4SFCoreValues.esm]` as its masters**, adds **42** own records (`0x000800..0x000858`), overrides **2** unlocalized Outpost category `FormList` records (`0x058606` and `0x1A5507`, `44` major records total), and emits `0` `LCTN`, `STDT`, or `PNDT` overrides (`HeaderFlag.Localized` cleared).
- `FO4TerrainCore.esm` / `FO4TerrainCore_Mars.esm` is never added as a master and no core cell is ever overridden: `FO4SF_WorkshopCoreQuest` resolves the terrain core's workshop base (`0x0A2ECD`) dynamically via `Game.GetFormFromFile` (falling back to `Starfield.esm` `WorkbenchIndustrial` `0x1F50AD` in standalone environments).
- `FO4SF_WorkshopCoreQuest` (`0x000800`) carries **1 script property (`TestModeGlobal` -> `000860:FO4SFCoreValues.esm`)**, keeping base lookups non-persistent while storing active world references in persistent quest script arrays (`TrackedWorkshops`, `TrackedBeacons`, `TrackedStations`) serialized in the save file.

---

## 2. Deterministic FormID Contract (`FO4SFWorkshop.esm`)

| Local ID | Type | EditorID | Role |
|---|---|---|---|
| `0x000800` | `QUST` | `FO4SF_WorkshopCoreQuest` | `StartGameEnabled`, Priority `30`, stages `[5, 10, 15, 20, 30, 40, 50, 60]` |
| `0x000801` | `GLOB` | `FO4SF_CAMPExclusionRadiusM` | Minimum distance (`45.0 m` default) from existing workshops/C.A.M.P.s |
| `0x000802` | `GLOB` | `FO4SF_ActiveCAMPCount` | Active portable C.A.M.P. beacon count |
| `0x000803` | `GLOB` | `FO4SF_TrackedWorkshopCount` | Active script-tracked settlement workbench count |
| `0x000804` | `GLOB` | `FO4SF_TrackedStationCount` | Active built crafting station count |
| `0x000810` | `MISC` | `FO4SF_CAMPKit` | Droppable Portable C.A.M.P. Kit (`OutpostBeaconActivator` `0x2C60E9` `2.5 m` ahead) |
| `0x000811` | `MISC` | `FO4SF_CAMPPackToken` | Droppable C.A.M.P. Pack-Up Token (relocates beacon back into `FO4SF_CAMPKit`) |
| `0x000812` | `MISC` | `FO4SF_SettlementKit` | Droppable Settlement Workbench Kit (`0x0A2ECD` `2.5 m` ahead) |
| `0x000818` | `FLST` | `FO4SF_CmpoIresList` | 18-entry `FormList` of resolved `Starfield.esm` `IRES` resource records |
| `0x000819` | `FLST` | `FO4SF_CmpoMiscList` | 18-entry `FormList` of resolved `Starfield.esm` `MISC` resource items |
| `0x00081A` | `FLST` | `FO4SF_ScrapJunkList` | 4-entry `FormList` of salvage junk `MISC` items (`0x000820..0x000823`) |
| `0x00081B` | `MISC` | `FO4SF_ScrapToken` | Droppable Field Scrapper Kit converting inventory junk into `MISC`/`IRES` |
| `0x00081C` | `FLST` | `FO4SF_BenchRecipesList` | 8-entry `FormList` of FO4 `COBJ` + FNV `RCPE` bench recipes (`0x000840..0x000847`; `0x000843` gated on `FO4SF_TestModeEnabled != 0.0 // until owner Q6`) |
| `0x00081D` | `FLST` | `FO4SF_KitFilterList` | 4-entry `FormList` bound via `AddInventoryEventFilter` |
| `0x000848` | `KYWD` | `FO4SF_WorkshopCategorySanctuary` | Clean `Sanctuary` category keyword (`RecipeFilter`, appended to `0x058606`/`0x1A5507`) |
| `0x000849` | `ACTI` | `FO4SF_SanctuaryWorkshopBench` | Opt-in clean Sanctuary bench (`workbenchgarage01.nif`, `0x84A` swap switch, default OFF) |
| `0x00084A` | `GLOB` | `FO4SF_SanctuaryCleanBenchSwap` | Clean bench swap switch (`0.0` default OFF) |
| `0x00084B..0x00084D` | `FURN`/`CONT` | `FO4SF_Sanctuary_WoodChair` / `SleepingCot` / `StorageCrate` | 3 clean Sanctuary outpost placeables (swap-gated via `0x00084E..0x000850` on `0x84A == 1.0`, zero skill gates) |
| `0x000858` | `GLOB` | `FO4SF_WorkshopStartViaScript` | WS0a opening-toast candidate switch (`0.0` default OFF; when `1.0`, blocks E native build trigger and runs `StartWorkshop(true)` after release) |

---

## 3. `CMPO -> IRES -> MISC` Mapping & Salvage Junk

`dotnet/WorkshopCore` dynamically resolves all **18** Fallout 4 scrap component archetypes against `Starfield.esm` `IRES` (`Resource`) and `MISC` (`MiscItem`) records:

| Index | Archetype | `Starfield.esm` `IRES` | `Starfield.esm` `MISC` |
|---:|---|---|---|
| `0` | Steel | `ResInorgCommonIron` | `InorgCommonIron` |
| `1` | Wood | `ResOrgCommonStructural` | `OrgCommonStructural` |
| `2` | Aluminum | `ResInorgCommonAluminum` | `InorgCommonAluminum` |
| `3` | Adhesive | `ResOrgRareAdhesive` | `OrgRareAdhesive` |
| `4` | Screws | `ResInorgUncommonTungsten` | `InorgUncommonTungsten` |
| `5` | Copper | `ResInorgCommonCopper` | `InorgCommonCopper` |
| `6` | Circuitry | `ResMfg_Tier01_ZeroWire` | `Mfg_Tier01_ZeroWire` |
| `7` | NuclearMaterial | `ResInorgCommonUranium` | `InorgCommonUranium` |
| `8` | Lead | `ResInorgCommonLead` | `InorgCommonLead` |
| `9` | Gears | `ResMfg_Tier01_AdaptiveFrame` | `Mfg_Tier01_AdaptiveFrame` |
| `10` | Springs | `ResInorgRareTitanium` | `InorgRareTitanium` |
| `11` | Oil | `ResOrgExoticLubricant` | `OrgExoticLubricant` |
| `12` | Cloth | `ResOrgCommonFiber` | `OrgCommonFiber` |
| `13` | Glass | `ResOrgUncommonCosmetic` | `OrgUncommonCosmetic` |
| `14` | Plastic | `ResOrgExoticPolymer` | `OrgExoticPolymer` |
| `15` | Rubber | `ResOrgCommonSealant` | `OrgCommonSealant` |
| `16` | Ceramic | `ResInorgUncommonChlorosilanes_L` | `InorgUncommonChlorosilanes` |
| `17` | Antiseptic | `ResOrgUncommonAntimicrobial` | `OrgUncommonAntimicrobial` |

### Clean-Room Salvage Junk Items (`0x000820..0x000823`)
Each junk item carries native `MiscItem.Resources` (`ItemResource` links to `IRES`) and scraps deterministically into `FO4SF_CmpoMiscList` items:
- `0x000820` `FO4SF_Junk_DeskFan`: Steel (`#0`) x2, Gears (`#9`) x2, Screws (`#4`) x2
- `0x000821` `FO4SF_Junk_DuctTape`: Adhesive (`#3`) x2, Cloth (`#12`) x1
- `0x000822` `FO4SF_Junk_HotPlate`: Copper (`#5`) x2, Circuitry (`#6`) x1, Screws (`#4`) x1
- `0x000823` `FO4SF_Junk_TinCan`: Steel (`#0`) x2, Aluminum (`#2`) x2

Scrapping `4` of each item (stage `20`) yields `16 Iron` and `8 Aluminum` (more than the `3 Iron, 4 Aluminum` required to build an `Industrial Workbench` in Workshop Build Mode) plus `8 Adhesive`, `12 Tungsten`, `8 Copper`, `4 ZeroWire`, `8 AdaptiveFrame`, and `4 Fiber` for bench recipes.

---

## 4. Clean-Room FO4 `COBJ` & FNV `RCPE` Bench Recipes (`0x000840..0x000847`)

All 8 recipes use resolved `Starfield.esm` `IRES` components, `LearnMethod = DefaultOrConditions`, and `0` condition/perk locks:

| Local ID | EditorID | Origin | Workbench Keyword | Output | `IRES` Cost |
|---|---|---|---|---|---|
| `0x000840` | `FO4SF_COBJ_FO4_FieldMedkit` | FO4 `COBJ` | `WorkbenchChemlabRecipeKeyword` | `1x FO4SF_Craft_FieldMedkit` (`0x830`) | Antiseptic x2, Steel x1, Cloth x1 |
| `0x000841` | `FO4SF_COBJ_FO4_WeaponPartsKit` | FO4 `COBJ` | `WorkbenchIndustrialKeyword` | `1x FO4SF_Craft_WeaponPartsKit` (`0x831`) | Steel x3, Adhesive x2, Screws x2, Aluminum x2 |
| `0x000842` | `FO4SF_COBJ_FO4_SensorModule` | FO4 `COBJ` | `WorkbenchIndustrialKeyword` | `1x FO4SF_Craft_SensorModule` (`0x832`) | Copper x2, Circuitry x2, Glass x1 |
| `0x000843` | `FO4SF_COBJ_FO4_PortableCAMPKit` | FO4 `COBJ` | `WorkbenchIndustrialKeyword` | `1x FO4SF_CAMPKit` (`0x810`) | Steel x4, Aluminum x3, Gears x2, Circuitry x1 (`TestMode != 0.0` gated // until owner Q6) |
| `0x000844` | `FO4SF_RCPE_NV_SurgicalBag` | FNV `RCPE` | `WorkbenchChemlabRecipeKeyword` | `1x FO4SF_Craft_SurgicalBag` (`0x833`) | Antiseptic x2, Cloth x2, Rubber x1 |
| `0x000845` | `FO4SF_RCPE_NV_CombatBlend` | FNV `RCPE` | `WorkbenchChemlabRecipeKeyword` | `1x FO4SF_Craft_CombatBlend` (`0x834`) | Antiseptic x2, Plastic x1, Lead x1 |
| `0x000846` | `FO4SF_RCPE_NV_HandLoad777` | FNV `RCPE` | `WorkbenchIndustrialKeyword` | `12x Ammo777mm` | Lead x2, Copper x2, Oil x1 |
| `0x000847` | `FO4SF_RCPE_NV_TrailRation` | FNV `RCPE` | `WorkbenchCookingKeyword` | `1x FO4SF_Craft_TrailRation` (`0x835`) | Wood x1, Antiseptic x1, Ceramic x1 |

---

## 5. PC Verification Card (Including Named Throwaway Save-Quit-Reload)

### Offline Precheck, Stage, Hardlink Fold, and Verify (Game Closed)
```powershell
python scripts/workshop/make_workshop_core.py precheck --content-resources "<starfield_dir>/Tools/ContentResources.zip" --out "<work_dir>/precheck.json"
python scripts/workshop/make_workshop_core.py stage --out "<work_dir>/stage-v1" --starfield "<starfield_dir>/Data/Starfield.esm" --compiler "<starfield_dir>/Tools/Papyrus Compiler/PapyrusCompiler.exe" --content-resources "<starfield_dir>/Tools/ContentResources.zip"
python scripts/workshop/make_workshop_core.py fold --stage "<work_dir>/stage-v1" --core-dir "<clean_core_dir>" --out "<work_dir>/folded-clean-core-v1" --starfield "<starfield_dir>/Data/Starfield.esm" --hardlink
python scripts/workshop/make_workshop_core.py verify --exp-dir "<work_dir>/folded-clean-core-v1" --plan "<work_dir>/stage-v1/plan.json" --starfield "<starfield_dir>/Data/Starfield.esm"
```
Expected offline terminal line: `verify: ok`.

### In-Game & Save-Quit-Reload Verification Steps (Claude PC)
1. **Install** (game closed) using either the folded core experiment or ride-along installer:
   ```powershell
   python scripts/workshop/workshop_core_install.py install --dir "<work_dir>/stage-v1" --starfield "<starfield_dir>"
   ```
2. **Launch & Stand in Open Ground:** Load an exterior test position at least `50 m` away from any pre-placed settlement workshop. Print exact console commands from the live quest FormID:
   ```powershell
   python scripts/workshop/make_workshop_core.py console
   ```
3. **Run Pre-Reload Verification Stages (`15`, `10`, `20`, `30`):**
   - `setstage <XX>000800 15` — Deploys persistent Portable C.A.M.P. beacon (`OutpostBeaconActivator` `0x2C60E9`) `2.5 m` ahead (`camp_deployed`), then immediately attempts a second C.A.M.P. deployment at the same spot and verifies the `45 m` exclusion rule blocks it and refunds `FO4SF_CAMPKit` (`camp_blocked`).
   - `setstage <XX>000800 10` — Places persistent settlement workbench (`0x0A2ECD`) `2.5 m` ahead + `3.5 m` right (`bench_placed`).
   - `setstage <XX>000800 20` — Adds `4x` each salvage junk item (`DeskFan`, `DuctTape`, `HotPlate`, `TinCan`) and scraps all `16` items into `Starfield.esm` `MISC`/`IRES` resources (`16 Iron`, `8 Aluminum`, `8 Adhesive`, `12 Tungsten`, `8 Copper`, `4 ZeroWire`, `8 AdaptiveFrame`, `4 Fiber`).
   - `setstage <XX>000800 30` — Audits all `18` `CMPO -> IRES -> MISC` pairs and all `8` FO4 `COBJ` + FNV `RCPE` bench recipes (`recipe_audit`).
4. **Build Station & Craft at Bench:**
   - Look at the settlement bench (`WORKSHOP / BUILD [E]`) or C.A.M.P. beacon (`OUTPOST BEACON / BUILD [E]`), press `E` to enter Build Mode, place an `Industrial Workbench` on open ground using the scrapped `Iron` and `Aluminum`, and press `Esc` once to exit Build Mode.
   - Use the placed `Industrial Workbench` to verify `Machined Receiver Kit` (`FO4SF_COBJ_FO4_WeaponPartsKit`) and `Portable C.A.M.P. Kit` (`FO4SF_COBJ_FO4_PortableCAMPKit`) appear ready to craft.
5. **Named Throwaway Save -> Quit -> Relaunch -> Reload:**
   - Open the console and create the named throwaway save:
     ```text
     save FO4SF_Throwaway_WorkshopCAMP_DeleteMe
     ```
   - Quit Starfield completely to desktop.
   - Relaunch Starfield and load **`FO4SF_Throwaway_WorkshopCAMP_DeleteMe`**.
   - Confirm visually that the settlement workbench, C.A.M.P. beacon, and built `Industrial Workbench` are still standing with live `WORKSHOP / BUILD [E]` / `OUTPOST BEACON / BUILD [E]` prompts (`Actor.OnPlayerLoadGame` automatically logs `reload_audit when=reload` and `when=reload+2s`).
6. **Post-Reload Audit, C.A.M.P. Pack-Up, Cleanup, and Throwaway Save Deletion:**
   - Run post-reload console stages:
     - `setstage <XX>000800 50` (explicit post-reload persistence audit `when=stage50`)
     - `setstage <XX>000800 40` (packs up active C.A.M.P. beacon and refunds `FO4SF_CAMPKit`)
     - `setstage <XX>000800 60` (disables/deletes script-spawned benches and beacons)
   - Quit Starfield **without saving**.
   - **Delete the throwaway save `FO4SF_Throwaway_WorkshopCAMP_DeleteMe`** (`FO4SF_Throwaway_WorkshopCAMP_DeleteMe*.sfs`) from the Starfield `Saves` folder so zero persistent test state remains.
   - Evaluate the stitched session logs (`FO4SFWorkshopCore.1.log` + `FO4SFWorkshopCore.0.log`):
     ```powershell
     python scripts/workshop/make_workshop_core.py log
     ```
   - Uninstall ride-along files when finished:
     ```powershell
     python scripts/workshop/workshop_core_install.py uninstall --starfield "<starfield_dir>"
     ```

### Expected `make_workshop_core.py log` Output (`PASS` Lines)
```text
PASS settlement_bench
PASS portable_camp
PASS camp_exclusion
PASS cmpo_scrap
PASS bench_recipes
PASS save_reload_persistence
PASS camp_packup
VERDICT: PASS
```
