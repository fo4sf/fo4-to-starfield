# Lane B Lead Verification Cards — `FO4DLC.esm` Swap & Interior Batch 11 Build (`gemini/dlc-and-interiors`)

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**.

---

## Card 1 — `D4` Self-Contained `FO4DLC.esm` Swap Session (`TEST-STATION`)

- **Stage path placeholder:** `<fo4dlc-stage>` (containing `result.json` and `port\`)
- **Disk space need:** `--min-free-gb 40` free-space floor on `<starfield-dir>`'s drive after copying the ~`7.1 GB` stage (`FO4DLC.esm` `9,446,134` B + `FO4DLC - Main.ba2` + `FO4DLC - Textures.ba2` + `FO4DLCTextures2.esm`/`FO4DLCTextures2 - Textures.ba2` + `FO4DLCTextures3.esm`/`FO4DLCTextures3 - Textures.ba2`, every archive `< 4 GiB`).
- **`Plugins.txt` load list:** `*FO4DLC.esm`, `*FO4DLCTextures2.esm`, `*FO4DLCTextures3.esm` appended in number order right after the active `*FO4Port.esm` set (`FO4DLC.esm` masters `Starfield.esm` only and installs side-by-side without replacing `FO4Port.esm`).
- **Why `TEST-STATION`:** `49` net-new DLC interior cells (`103,009` placed references, `4,673` lights, `18` interior-to-interior linked teleports) enter from Far Harbor, Nuka-World, or unwired Commonwealth doors, so entry is by console `coc` only.
- **5 Excluded Overlapping Cells (owned by `FO4Port.esm` / staged base batch; omitted from `FO4DLC.esm`):**
  `DLC01FortHagenSatelliteArray01`, `DLC01Lair01`, `DmndValentines01`, `GeneralAtomicsFactory01`, `RailroadHQ01`.

### Install Commands (Game Closed)

```sh
python scripts/deploy_starfield.py install --batch <fo4dlc-stage> --starfield <starfield-dir> --min-free-gb 40 --dry-run
python scripts/deploy_starfield.py install --batch <fo4dlc-stage> --starfield <starfield-dir> --min-free-gb 40
```

### In-Game Console Checks (`TEST-STATION`)

Launch a clean test save, walk the floor, verify collision and companion-archive texture rendering (`FO4DLCTextures2` / `FO4DLCTextures3`), and test an internal DLC-to-DLC door pair where present:

```console
coc FO4DLC_DLC03Acadia
coc FO4DLC_DLC04BradbertonsOffice01
coc FO4DLC_DLC06VaultWorkshop
```

### Undo / Rollback Commands (Game Closed)

> **CRITICAL (`--plugin-name FO4DLC.esm` required):** Always pass `--plugin-name FO4DLC.esm` on `uninstall`. Without `--plugin-name FO4DLC.esm`, `deploy_starfield.py uninstall` defaults to `FO4Port.esm` (`FO4Port.deploy.json`) and acts on the owner's installed `FO4Port.esm` port instead of `FO4DLC.esm`.

```sh
python scripts/deploy_starfield.py uninstall --starfield <starfield-dir> --plugin-name FO4DLC.esm
python scripts/deploy_starfield.py verify --starfield <starfield-dir>
```

### Card 1 PASS Lines

```text
install batch <fo4dlc-stage>: ['FO4DLC.esm', 'FO4DLC - Main.ba2', 'FO4DLC - Textures.ba2', 'FO4DLCTextures2.esm', 'FO4DLCTextures2 - Textures.ba2', 'FO4DLCTextures3.esm', 'FO4DLCTextures3 - Textures.ba2'] -> <starfield-dir>\Data (<gb> GB)
Plugins.txt (<plugins-txt>): *FO4DLC.esm then ['*FO4DLCTextures2.esm', '*FO4DLCTextures3.esm']
installed. Undo with: python deploy_starfield.py uninstall --starfield <game dir> --plugin-name FO4DLC.esm
removing ['FO4DLC.esm', 'FO4DLC - Main.ba2', 'FO4DLC - Textures.ba2', 'FO4DLCTextures2.esm', 'FO4DLCTextures2 - Textures.ba2', 'FO4DLCTextures3.esm', 'FO4DLCTextures3 - Textures.ba2'] and Plugins.txt entries ['*FO4DLC.esm', '*FO4DLCTextures2.esm', '*FO4DLCTextures3.esm']
uninstalled
installed port as recorded: FO4Port.esm <sha8>
```

- **Technical PASS:** All three `FO4DLC_*` cells load with zero crash, solid floor collision, and zero missing-texture magenta across `FO4DLCTextures2` / `FO4DLCTextures3`; rollback removes only `FO4DLC*` files and leaves `verify` passing on `FO4Port.esm`.
- **OWNER TEST (Visual):** Room lighting balance and material roughness/tint look across the converted DLC interiors in `FO4DLC.esm` (note: none of the `49` selected `FO4DLC.esm` cells places the `58` recovered Automatron `SCOL` meshes, and the `269`-cell base-port look test was already completed on 18 Nov).

---

## Card 2 — `I2` + `D6` Offline Build of Interior Batch 11 (`TOOLING`)

- **Stage path placeholder:** `<b11-stage>` (with fresh work staging `<new-work-dir>` and dry-run output `<b11-dry-out>`)
- **Disk space need:** `--min-free-gb 40` free-space floor on `<new-work-dir>` and `<b11-stage>` drives after work-staging conversion plus ~`4.5 GB` packed archives; `--min-free-gb 40` on `<starfield-dir>`'s drive if `<b11-stage>` is later swap-installed.
- **`Plugins.txt` load list** (recorded in `<b11-stage>/result.json` `install.plugins_txt`; the offline build touches neither `<starfield-dir>` nor `Plugins.txt`): `*FO4Port.esm`, `*FO4PortTextures2.esm` (and any further `*FO4PortTexturesN.esm` companion in number order right after `*FO4Port.esm`).
- **`D6` Automatron `SCOL` recovery under default `fo4port` prefix:** The `58` recovered Automatron `SCOL` (`CM*.NIF`) static-collection meshes belong to base-port-owned Automatron cells (`DLC01Lair01`, `DLC01FortHagenSatelliteArray01`) and are **in no built plugin yet**. Passing `--dlc-data <dlcrobot-plugin-data>` (plus a second `--dlc-data <dlcrobot-archives-data>` when `DLCRobot.esm` and `DLCRobot - *.ba2` live in separate depot folders; pass one `--dlc-data` when both sit in one folder), `--dlc-plugins DLCRobot.esm`, and a fresh `--work <new-work-dir>` converts all `58` `SCOL` meshes under the default `fo4port` prefix (`FO4Port_cm*` / `fo4port\scol\...`) while preserving `<b10-stage>`'s work folder untouched.
- **`D3` `--dry-run` seed-check note:** `interior_batch.py build --dry-run` performs a **seed check** (`"check_kind": "seed_check"`, `"compares_run": false`, `"check": "seed_id_map_only"`) against reconciled `seed_ids` (`16` base + `253` batch = `269` cells, `0` installed FormIDs moved). The two full plugin compares (`--compare-installed` -> `port/compare_installed.json` and `--prev` -> `port/compare_prev.json`) run only in the real build.

### Offline Build Commands (`TOOLING` — Nothing Installed)

Optional non-destructive `adopt-core` helper (records `pins.core_plugin` from `port/doors_check.json` on an older stage without modifying `--stage`):

```sh
python scripts/terrain/interior_batch.py adopt-core --stage <b10-stage> --out <b10-adopted-stage>
```

Seed-check dry run (`D3`) followed by the real offline Batch 11 build (`I2` + `D6`):

```sh
python scripts/terrain/interior_batch.py build --dry-run --plan docs/terrain/data/interior-batches.json --batch 10 --base <installed-anim-doors-port> --base-exports <base-exports-dir> --prev <b10-stage> --compare-installed <installed-anim-doors-port> --core <installed-core-stage> --work <new-work-dir> --out <b11-dry-out> --fo4-data <fo4-data-dir> --dlc-data <dlcrobot-plugin-data> --dlc-data <dlcrobot-archives-data> --dlc-plugins DLCRobot.esm --census docs/terrain/data/interior-census.json --starfield <starfield-dir> --content-resources <content-resources-zip> --texconv <texconv-exe> --collision-template <collision-template-nif> --fo4export <fo4export-dll> --pluginspike <pluginspike-dll> --spec-mask-roughness --convert-arg=--door-anim-dll --convert-arg=<door-anim-dll> --convert-arg=--mass-scale --convert-arg=0.2 --promote-arg=--names --promote-arg=<fo4-names-json> --promote-arg=--furniture --promote-arg=<fo4-furniture-json> --promote-arg=--fo4-data --promote-arg=<fo4-data-dir> --animated-doors --animated-pex <animated-load-door-pex> --door-flags --doorsounds <doorsounds-tsv> --min-free-gb 40
python scripts/terrain/interior_batch.py build --plan docs/terrain/data/interior-batches.json --batch 10 --base <installed-anim-doors-port> --base-exports <base-exports-dir> --prev <b10-stage> --compare-installed <installed-anim-doors-port> --core <installed-core-stage> --work <new-work-dir> --out <b11-stage> --fo4-data <fo4-data-dir> --dlc-data <dlcrobot-plugin-data> --dlc-data <dlcrobot-archives-data> --dlc-plugins DLCRobot.esm --census docs/terrain/data/interior-census.json --starfield <starfield-dir> --content-resources <content-resources-zip> --texconv <texconv-exe> --collision-template <collision-template-nif> --fo4export <fo4export-dll> --pluginspike <pluginspike-dll> --spec-mask-roughness --convert-arg=--door-anim-dll --convert-arg=<door-anim-dll> --convert-arg=--mass-scale --convert-arg=0.2 --promote-arg=--names --promote-arg=<fo4-names-json> --promote-arg=--furniture --promote-arg=<fo4-furniture-json> --promote-arg=--fo4-data --promote-arg=<fo4-data-dir> --animated-doors --animated-pex <animated-load-door-pex> --door-flags --doorsounds <doorsounds-tsv> --min-free-gb 40
```

### Future Swap-Session Install & Undo Commands (Only After Owner Release; Uninstall Replaces Installed `FO4Port.esm` First)

```sh
python scripts/deploy_starfield.py uninstall --starfield <starfield-dir> --plugin-name FO4Port.esm
python scripts/deploy_starfield.py install --batch <b11-stage> --starfield <starfield-dir> --plugin-name FO4Port.esm --min-free-gb 40
python scripts/deploy_starfield.py uninstall --starfield <starfield-dir> --plugin-name FO4Port.esm
```

### Card 2 PASS Lines

```text
"check_kind": "seed_check"
"compares_run": false
"seed_check_pass": true
"check": "seed_id_map_only"
"seed_installed_moved": 0
"batch": 10,
"pass": true,
"error": null,
"compare_installed": { "pass": true, "ids": { "missing": 0, "renumbered": 0 } }
"compare_prev": { "pass": true }
```

---

## Part 2 Offline Tooling — `IB1` Start-Path Switches & `IB2` Install-Record Report (`TOOLING`)

- **`IB1` start-path interior switches (`TOOLING`, off by default on `interior_batch.py build` for the batch after Batch 11; in no built plugin yet):**
  - `--fo4-loot`: populates `CONT` bases from Fallout 4 `CNTO` / `LVLI` records wherever a converted item model exists in `<work>/manifest.json`, logging unconverted/empty fallbacks to `plugin/loot_fallbacks.json`.
  - `--usable-beds-benches`: promotes Fallout 4 beds (`Bed_Single01` `1FA770`) and weapon/armor/chem/cooking workbenches (`2B6A63` / `2B6A62` / `2B6A61` / `2B6A65`).
  - `--interactive-fidelity`: passes `--interactive-fidelity` (`XLOC` locks, `XESP` enable-parents, `XLKR` linked references, `XAPR` multi-target activation chains) to `PluginSpike`.
- **`IB1` per-cell start-path census & `IB2` read-only install-record report (`TOOLING`, 100% read-only on game state):**

```sh
python scripts/terrain/interior_start_census.py --stage <next-batch-stage> --start-path-only
python scripts/terrain/port_install_report.py --starfield <starfield-dir> --out <owner-tests-dir>/ib2-install-record-report.json --counts-only
```

---

## Explicitly `NOT BUILT` in `gemini/dlc-and-interiors` This Round

- **58 recovered Automatron `SCOL` meshes (`D6`):** Converted by `convert_batch.py` / `interior_batch.py` once Card 2 builds `<b11-stage>`, and **in no built plugin yet** (`DLC01Lair01` and `DLC01FortHagenSatelliteArray01` are base-port-owned and excluded from `FO4DLC.esm`).
- **DLC edits to the 3 base-game cells excluded from `FO4DLC.esm` (`D7`, `NOT BUILT`):**
  1. `DmndValentines01` (`001E47:Fallout4.esm`, edited by `DLCCoast.esm`): `2` added `REFR`s (`0141AB:DLCCoast.esm`, `04BA1A:DLCCoast.esm`; `342 -> 344` `REFR`, `2` `ACHR` unchanged, `0` vanilla `REFR` overrides). Base port pins the `Fallout4.esm`-only export (`342` `REFR`).
  2. `GeneralAtomicsFactory01` (`04280D:Fallout4.esm`, edited by `DLCRobot.esm`): `44` `DLCRobot.esm` child reference records (`19` `REFR` [`3` added: `00FF9C:DLCRobot.esm`, `00FFA7:DLCRobot.esm`, `00FFA8:DLCRobot.esm` + `16` overridden vanilla `REFR`s] and `25` `ACHR` [`12` added + `13` overridden vanilla `ACHR`s], plus encounter zone `011363:DLCRobot.esm`; net `6,136 -> 6,139` `REFR`, `13 -> 25` `ACHR`). Exported merged in uninstalled `interiors_b10`, not in the installed `16`-cell `FO4Port.esm` yet.
  3. `RailroadHQ01` (`092B21:Fallout4.esm`, edited by `DLCCoast.esm`): `1` added `ACHR` (`18 -> 19` `ACHR`; `1,542 -> 1,542` `REFR` with `0` `REFR` additions or overrides). Exported from `Fallout4.esm` only in `interiors_b10` (and `ACHR` actors are deferred).
- Exterior door delta for the `13` start-path Commonwealth doors (`I3` — owned by `gemini/world-own-space`) and exterior doors into `FO4DLC.esm` interiors (`WB5b`).
- Guarded repair command for `FO4Port.deploy.json` (explicitly deferred by `IB2` until after the read-only report is reviewed).
