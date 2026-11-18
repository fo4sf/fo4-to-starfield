# Lane B Lead Verification Cards — DLC Interiors & Staged Batch Look Test (`gemini/dlc-and-interiors`)

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**.

---

## Card 1 — `D4` Self-Contained `FO4DLC.esm` Swap Session (`TEST-STATION`)

**Scope & Label:** `FO4DLC.esm` (`9,446,134` B, `49` net-new DLC interior cells, `103,009` placed references, `4,673` lights, `18` interior-to-interior linked teleports, self-contained over `Starfield.esm` only) + `FO4DLC - Main.ba2`, `FO4DLC - Textures.ba2`, `FO4DLCTextures2.esm` + BA2, and `FO4DLCTextures3.esm` + BA2 (each `< 4 GiB`).
- **Why `TEST-STATION`:** `47` of the `54` load-door-reachable DLC cells enter from Far Harbor, Nuka-World, or other DLC interiors whose exterior doors are not wired yet, so entry is by console `coc` only.
- **5 Excluded Overlapping Cells (owned by `FO4Port.esm` / staged base batch; omitted from `FO4DLC.esm`):**
  1. `DLC01FortHagenSatelliteArray01`
  2. `DLC01Lair01` *(tested from the staged base interior build instead)*
  3. `DmndValentines01`
  4. `GeneralAtomicsFactory01`
  5. `RailroadHQ01`

### Swap-Session Steps (Game Closed for Install / Rollback)
1. Install the staged `FO4DLC` package (`FO4DLC.esm`, `FO4DLCTextures2.esm`, `FO4DLCTextures3.esm` + their BA2 archives) in a swap session and record pre/post install receipts.
2. Launch a clean test save and enter at least three cells owned exclusively by `FO4DLC.esm`:
   - Far Harbor — Acadia: `coc FO4DLC_DLC03Acadia` (`2,605` refs, `211` lights)
   - Nuka-World interior: `coc FO4DLC_DLC04BradbertonsOffice01` (`1,269` refs, `70` lights)
   - Vault-Tec Workshop vault: `coc FO4DLC_DLC06VaultWorkshop` (`6,037` refs, `631` lights)
3. Walk the floor in each cell, inspect multi-part companion texture rendering (`FO4DLCTextures2` / `FO4DLCTextures3`), and test an internal DLC-to-DLC door pair where present.
4. Close the game, uninstall, and verify byte-identical receipt restoration.

### Pass Criteria & Owner Test Judgments
- **Technical PASS:** All three `FO4DLC_*` cells load with zero crash, solid floor collision (no fall-through), and textures from companion archives (`FO4DLCTextures2` / `FO4DLCTextures3`) render without missing-texture magenta.
- **OWNER TEST (Visual):** Room lighting balance (neither pitch-black nor washed out) and material roughness/tint look across converted DLC meshes and the `58` recovered Automatron `SCOL` static-collection meshes (`D5`).

---

## Card 2 — `I2` Staged Base Interior Batch Look Test & Animated-Door Chain (`TEST-STATION` / `TOOLING`)

### Part A — Offline `adopt-core` & Animated-Door `--prev` Dry Run (`TOOLING`, Verified Offline)
- `python scripts/terrain/interior_batch.py adopt-core --stage <b10-stage> --out <adopted-meta>` records `pins.core_plugin` from `port/doors_check.json` (`49/49` door checks pass; `deploy_starfield.py install --batch --dry-run` accepts the stage without `--other-core`).
- `python scripts/terrain/interior_batch.py build --dry-run --batch 10 --prev <b10-stage> --base <doors-anim-b00-port> --compare-installed <doors-anim-b00-port> --animated-doors` reports:
  - `pass: true`, `cells: 16 base + 253 batch = 269 total`
  - `installed_count: 55706`, **`installed_moved: 0`** (zero installed FormIDs move)

### Part B — Swap-Session Console Look Test of Staged Base Batch (`TEST-STATION`)
1. With owner release, swap-install the `269`-cell staged interior batch (`FO4Port.esm` + `FO4PortTextures2.esm`).
2. Enter `coc FO4Port_ConcordMuseum01`, `coc FO4Port_SanctuaryBasementJahani`, `coc FO4Port_CorvegaAssemblyPlant01`, `coc FO4Port_DLC01Lair01`, and one cell whose textures reside in `FO4PortTextures2 - Textures.ba2`.
3. Confirm room load, collision, lighting, and companion-archive texture rendering, then roll back to the `16`-cell animated-doors port and verify the SHA-256 receipt matches.

---

## Explicitly `NOT BUILT` in `gemini/dlc-and-interiors` This Round
- Exterior door delta for the `13` start-path Commonwealth doors (`I3` — owned by `gemini/world-own-space`).
- Fallout 4 `CNTO`/`LVLI` container loot and usable beds/workbenches inside start-path interiors (`NEXT`).
- Folding `--interactive-fidelity` (`XESP`/`XLOC`/`XLKR`/`XAPR`) into the batch build, remaining `334` Commonwealth exterior doors, interior `NAVM` walk meshes, per-light FO4 color/spot carry-over, and exterior doors into DLC interiors (`NEXT`).
- Repo UI extractor, startup/interface low-priority texture archives, and first-person Pip-Boy arm mesh note (`Task 6 NEXT`).
